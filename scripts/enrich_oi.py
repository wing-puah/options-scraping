"""
Enrich a day's compiled flow file with prev-day open-interest change and EOD greeks.

When unusual flow prints on trade date D, comparing OI on D to OI on D-1 (the
prior trading day) reveals whether new positions were opened: a rise of ~the trade
size on D versus D-1 means the flow genuinely opened conviction. This is the signal
in references/references_key_insight item 03 (Short-Lived Options).

For every distinct option contract in a compiled flow file ({prefix}-YYYYMMDD-
compiled.csv, where the filename date is the trade date D), this script scrapes
the Barchart per-contract price-history daily series and APPENDS these columns to
every row of that contract:

    oi_d       open interest on D            (exact price-history row on D)
    oi_prev    open interest on D-1          (last trading day before D in the series)
    oi_change  oi_d - oi_prev               (the OI change on trade day D)
    vol_d      traded volume on D
    eod_iv / eod_delta / eod_gamma / eod_vega   end-of-D settlement greeks
    oi_enriched_on   the date this row was scraped (provenance + resume marker)

The EOD greeks are deliberately prefixed to distinguish them from the intraday
snapshot IV/Delta already carried in the flow row.

Persistence & resume — the compiled file on Drive IS the only store. There is NO
per-contract local cache: a contract's price history is scraped, the handful of
fields above are extracted into its rows, and the raw history is discarded. The
enriched compiled file is re-uploaded to Drive as we go:

  * after every CHECKPOINT_EVERY contracts, and
  * once more on exit (including KeyboardInterrupt / error),

so an interrupted run never loses the contracts it already scraped. On the next
run, any contract whose rows already carry `oi_enriched_on` is skipped — including
contracts Barchart returned nothing for (they're marked attempted, so they aren't
re-fetched forever). Use --force to clear the columns and re-scrape everything.

All compiled dates are enrichable (D-1 is always in the series for any non-first
trading day); --backfill self-heals any missed days. Note that re-running
compile_flow.py for a date regenerates the compiled file from raw snapshots and
DROPS these columns — the next --backfill re-enriches it from scratch.

Usage:
  python3 scripts/enrich_oi.py                         # latest enrichable date
  python3 scripts/enrich_oi.py --date 2026-06-09
  python3 scripts/enrich_oi.py --start 2026-06-01 --end 2026-06-10
  python3 scripts/enrich_oi.py --backfill              # every enrichable date
  python3 scripts/enrich_oi.py --backfill --dry-run    # report, no scrape/upload
  python3 scripts/enrich_oi.py --date 2026-06-09 --force   # re-scrape from scratch
"""
import argparse
import asyncio
import logging
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from lib import barchart_options
from lib.barchart import BarchartSession, _safe_err
from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client
from lib.logger import setup_logging
from backtest.helpers import _contract_key, _num, _parse_expiration
from compile_flow import FLOW_PREFIXES, compiled_name

log = logging.getLogger("enrich_oi")

# Data columns appended to every flow row, in this order. Lowercase + underscores
# so the header is robust to whitespace/case quirks when the CSV is read back.
ENRICH_COLUMNS = ["oi_d", "oi_prev", "oi_change", "vol_d",
                  "eod_iv", "eod_delta", "eod_gamma", "eod_vega"]
# Provenance + resume marker: set to the run date for every contract we ATTEMPT
# (even when Barchart returns nothing), so resume can tell "scraped, empty" from
# "not yet scraped" and never re-fetches an empty contract.
MARKER_COLUMN = "oi_enriched_on"
ALL_COLUMNS = ENRICH_COLUMNS + [MARKER_COLUMN]

# Re-upload the compiled file to Drive every this-many contracts, bounding how
# much scraping an interruption can cost.
CHECKPOINT_EVERY = 50

_DEFAULT_COOKIES = str(Path(__file__).parent.parent / "cookies" / "barchart_session.json")


# ─── Drive helpers ──────────────────────────────────────────────────────────────

def _compiled_id(client, prefix: str, date_str: str) -> str | None:
    """Drive file ID of the compiled file for prefix/date, or None if absent.

    Looks DIRECTLY inside that date's folder rather than running a global, unpaginated
    `name contains` search across every folder (which truncates at the first results
    page and silently drops older compiled files).
    """
    folder_id = client.find_date_folder(date_str)
    if folder_id is None:
        return None
    return client.file_exists(compiled_name(prefix, date_str), folder_id)


def _compiled_dates(client, folders: dict[str, str] | None = None) -> list[str]:
    """Every trading date with a compiled flow file, oldest → newest.

    Enumerates the date folders under the root (one query) and checks each folder
    directly for a compiled file — no global cross-folder file search.
    """
    folders = folders if folders is not None else client.list_date_folders()
    out: list[str] = []
    for d in sorted(folders):
        if any(client.file_exists(compiled_name(p, d), folders[d]) for p in FLOW_PREFIXES):
            out.append(d)
    return out


def _enrichable_dates(client) -> list[str]:
    """All compiled dates. D-1 is always present in the price-history series for any
    non-first trading day, so every compiled date is immediately enrichable."""
    folders = client.list_date_folders()
    return _compiled_dates(client, folders)


def _weekday_range(start_iso: str, end_iso: str) -> list[str]:
    d, end = date.fromisoformat(start_iso), date.fromisoformat(end_iso)
    out = []
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# ─── Contract identification ────────────────────────────────────────────────────

def _row_contract(row: dict) -> dict | None:
    """Parse a flow row into a contract dict, or None if strike/expiry won't parse.

    Returns {key, symbol, opt_type, strike(float), expiration(date)} where `key`
    matches the backtest's _contract_key.
    """
    symbol = str(row.get("Symbol", "")).strip()
    opt_type = str(row.get("Type", "")).strip()
    strike = _num(row.get("Strike"))
    expiration = _parse_expiration(row.get("Expires", ""))
    if not symbol or not opt_type or strike is None or expiration is None:
        return None
    return {
        "key": _contract_key(symbol, opt_type, strike, expiration.isoformat()),
        "symbol": symbol,
        "opt_type": opt_type,
        "strike": strike,
        "expiration": expiration,
    }


def _distinct_contracts(rows: list[dict]) -> tuple[dict[tuple, dict], int]:
    """Map of contract_key → contract dict, plus a count of unparseable rows."""
    contracts: dict[tuple, dict] = {}
    unparseable = 0
    for row in rows:
        c = _row_contract(row)
        if c is None:
            unparseable += 1
            continue
        contracts.setdefault(c["key"], c)
    return contracts, unparseable


# ─── Enrichment computation ─────────────────────────────────────────────────────

def _fmt(v) -> str:
    return "" if v is None else str(v)


def _fmt_int(v) -> str:
    return "" if v is None else str(int(round(v)))


def _compute_enrichment(details: dict[date, dict], trade_date: date) -> dict:
    """Build the eight data columns for one contract.

    `details` is {date: row_dict} from parse_history_details. oi_d / vol_d / greeks
    require an exact row on the trade date (no carry-forward — these are EOD-of-D
    settlement values). oi_prev is the most recent series date strictly before D
    (weekends/holidays are absent, so it's the prior trading day). oi_change needs
    both ends.
    """
    blank = {c: "" for c in ENRICH_COLUMNS}
    if not details:
        return blank

    day = details.get(trade_date)
    oi_d = _num(day.get("Open Int")) if day else None
    vol_d = _num(day.get("Volume")) if day else None

    earlier = sorted(d for d in details if d < trade_date)
    oi_prev = _num(details[earlier[-1]].get("Open Int")) if earlier else None

    oi_change = oi_d - oi_prev if (oi_d is not None and oi_prev is not None) else None

    return {
        "oi_d": _fmt_int(oi_d),
        "oi_prev": _fmt_int(oi_prev),
        "oi_change": _fmt_int(oi_change),
        "vol_d": _fmt_int(vol_d),
        "eod_iv": _fmt(_num(day.get("IV")) if day else None),
        "eod_delta": _fmt(_num(day.get("Delta")) if day else None),
        "eod_gamma": _fmt(_num(day.get("Gamma")) if day else None),
        "eod_vega": _fmt(_num(day.get("Vega")) if day else None),
    }


# ─── Row state (columns, resume marker) ──────────────────────────────────────────

def _ensure_columns(rows: list[dict]) -> None:
    """Add any missing enrichment/marker columns (blank) in place, preserving values.

    Makes partial state representable so a checkpoint upload has a consistent header.
    """
    for row in rows:
        for col in ALL_COLUMNS:
            row.setdefault(col, "")


def _clear_columns(rows: list[dict]) -> None:
    """Reset every enrichment/marker column to blank (used by --force)."""
    for row in rows:
        for col in ALL_COLUMNS:
            row[col] = ""


def _done_keys(rows: list[dict]) -> set[tuple]:
    """Contract keys already attempted — their rows carry a non-blank marker."""
    done: set[tuple] = set()
    for row in rows:
        if str(row.get(MARKER_COLUMN, "")).strip():
            c = _row_contract(row)
            if c:
                done.add(c["key"])
    return done


# ─── Barchart history fetch + incremental fill ───────────────────────────────────

def _upload_rows(client, prefix: str, date_str: str, rows: list[dict]) -> None:
    """Write rows to the compiled file in Drive (in-place overwrite).

    Column order is stable: originals first (dict insertion order), then ALL_COLUMNS
    appended by _ensure_columns, so checkpoints and the final write match.
    """
    name = compiled_name(prefix, date_str)
    folder_id = client.get_or_create_date_folder(date_str)
    tmp = Path(f"/tmp/{name}")
    pd.DataFrame(rows).to_csv(tmp, index=False)
    client.upload(tmp, name, folder_id)
    tmp.unlink(missing_ok=True)


async def _fetch_details(session, contract: dict, timeout_ms: int) -> dict[date, dict]:
    """Scrape one contract's price history → {date: row}. Empty dict on failure.

    Uses fetch_history_fast: the first contract does a full navigation to capture the
    feed, every later one re-issues that feed directly (no per-contract page load).
    """
    url = barchart_options.option_history_url(
        contract["symbol"], contract["expiration"], contract["strike"], contract["opt_type"])
    try:
        csv_text = await session.fetch_history_fast(url, timeout_ms)
    except Exception as e:
        log.error("Barchart history scrape failed for %s: %s", contract["key"], _safe_err(e))
        return {}
    return barchart_options.parse_history_details(csv_text) if csv_text else {}


async def _scrape_and_fill(
    client, prefix: str, date_str: str, rows: list[dict], pending: list[dict],
    trade_date: date, run_date: str, *, headless: bool,
    checkpoint_every: int = CHECKPOINT_EVERY, timeout_ms: int = 15000,
    sleep_s: float = 0.4, session=None,
) -> dict:
    """Scrape each pending contract one at a time, fill its rows, and persist.

    The compiled file is re-uploaded every `checkpoint_every` contracts and once
    more in a finally block (so an interrupt/error still saves scraped work). Every
    attempted contract gets MARKER_COLUMN set so resume skips it next time. Returns
    {"with_next", "processed"}. A `session` may be injected for tests; otherwise a
    BarchartSession is opened here (needs BARCHART_EMAIL/PASSWORD).
    """
    rows_by_key: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        c = _row_contract(row)
        if c:
            rows_by_key[c["key"]].append(row)

    stats = {"with_next": 0, "processed": 0}

    async def run(sess) -> None:
        for i, c in enumerate(pending, 1):
            details = await _fetch_details(sess, c, timeout_ms)
            enrichment = _compute_enrichment(details, trade_date)
            enrichment[MARKER_COLUMN] = run_date
            if enrichment["oi_prev"]:
                stats["with_next"] += 1
            for row in rows_by_key.get(c["key"], []):
                row.update(enrichment)
            stats["processed"] += 1
            log.info("[%d/%d] %s %s: %s", i, len(pending), prefix, date_str, c["key"])
            if stats["processed"] % checkpoint_every == 0:
                _upload_rows(client, prefix, date_str, rows)
                log.info("%s %s checkpoint: %d/%d contracts persisted to Drive",
                         prefix, date_str, stats["processed"], len(pending))
            if sleep_s:
                await asyncio.sleep(sleep_s)

    try:
        if session is not None:
            await run(session)
        else:
            email = os.getenv("BARCHART_EMAIL", "")
            password = os.getenv("BARCHART_PASSWORD", "")
            if not (email and password):
                log.warning("BARCHART_EMAIL/PASSWORD not set — cannot scrape; "
                            "%d contract(s) deferred to a later run", len(pending))
                return stats
            cookies_path = Path(os.getenv("COOKIES_PATH", _DEFAULT_COOKIES))
            async with BarchartSession(email, password, cookies_path, headless) as sess:
                await run(sess)
    finally:
        # Persist whatever we scraped — including on KeyboardInterrupt / error.
        if stats["processed"]:
            _upload_rows(client, prefix, date_str, rows)
            log.info("%s %s flush: %d contract(s) persisted to Drive",
                     prefix, date_str, stats["processed"])

    return stats


# ─── Per-date driver ────────────────────────────────────────────────────────────

def enrich_prefix(
    client, prefix: str, date_str: str, *,
    headless: bool, dry_run: bool, force: bool,
) -> dict:
    """Enrich one flow type for one date. Returns a stats dict with a `status`."""
    base = {"prefix": prefix, "date": date_str}
    file_id = _compiled_id(client, prefix, date_str)
    if not file_id:
        log.info("%s %s: no compiled file — skipping", prefix, date_str)
        return {**base, "status": "no-compiled"}

    rows = parse_csv(client.download(file_id, name=compiled_name(prefix, date_str)))
    if not rows:
        log.warning("%s %s: compiled file is empty — skipping", prefix, date_str)
        return {**base, "status": "empty"}

    _ensure_columns(rows)
    contracts, unparseable = _distinct_contracts(rows)

    if force:
        _clear_columns(rows)
        done: set[tuple] = set()
    else:
        done = _done_keys(rows)

    pending = [c for key, c in contracts.items() if key not in done]
    if not pending:
        log.info("%s %s: all %d contract(s) already enriched — skipping (use --force to redo)",
                 prefix, date_str, len(contracts))
        return {**base, "status": "complete", "rows": len(rows),
                "contracts": len(contracts), "unparseable": unparseable}

    if dry_run:
        # Preview only — report scope without scraping (no network, no upload).
        log.info("%s %s: (dry-run) would scrape %d pending contract(s) of %d",
                 prefix, date_str, len(pending), len(contracts))
        return {**base, "status": "enriched", "rows": len(rows),
                "contracts": len(contracts), "pending": len(pending),
                "processed": 0, "with_next": 0, "unparseable": unparseable}

    run_date = date.today().isoformat()
    stats = asyncio.run(_scrape_and_fill(
        client, prefix, date_str, rows, pending, date.fromisoformat(date_str),
        run_date, headless=headless))

    log.info("%s %s: %d row(s), %d contract(s), %d pending, %d processed, %d with next-day OI%s",
             prefix, date_str, len(rows), len(contracts), len(pending),
             stats["processed"], stats["with_next"], " (dry-run)" if dry_run else "")
    return {**base, "status": "enriched", "rows": len(rows),
            "contracts": len(contracts), "pending": len(pending),
            "processed": stats["processed"], "with_next": stats["with_next"],
            "unparseable": unparseable}


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="Single trading date (YYYY-MM-DD).")
    parser.add_argument("--start", help="Range start (YYYY-MM-DD), weekdays only.")
    parser.add_argument("--end", help="Range end (YYYY-MM-DD), weekdays only.")
    parser.add_argument("--backfill", action="store_true",
                        help="Target every enrichable date in Drive (all but the latest).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute and report; do not upload.")
    parser.add_argument("--force", action="store_true",
                        help="Clear the columns and re-scrape every contract from scratch.")
    parser.add_argument("--no-headless", action="store_true",
                        help="Run the scraper with a visible browser.")
    args = parser.parse_args()

    if args.date and (args.start or args.end or args.backfill):
        parser.error("--date is exclusive with --start/--end/--backfill")
    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be given together")

    client = get_drive_client()

    if args.backfill:
        targets = _enrichable_dates(client)
    elif args.date:
        targets = [args.date]
    elif args.start:
        targets = _weekday_range(args.start, args.end)
    else:
        targets = _enrichable_dates(client)[-1:]  # latest enrichable

    headless = os.getenv("SCRAPE_HEADLESS", "true").lower() != "false" and not args.no_headless
    log.info("Enrich OI%s — %d date(s)", " (dry-run)" if args.dry_run else "", len(targets))

    results = [enrich_prefix(client, prefix, d, headless=headless, dry_run=args.dry_run,
                             force=args.force)
               for d in targets for prefix in FLOW_PREFIXES]

    enriched = [r for r in results if r["status"] == "enriched"]
    print(f"\nEnrich OI {'dry-run' if args.dry_run else 'run'} summary")
    print(f"  dates targeted:   {len(targets)}")
    print(f"  type/dates done:  {len(enriched)}")
    for r in results:
        if r["status"] == "enriched":
            print(f"  {r['date']}  {r['prefix']:<12} "
                  f"contracts={r['contracts']:>4}  pending={r['pending']:>4}  "
                  f"processed={r['processed']:>4}  with_next={r['with_next']:>4}  "
                  f"unparseable={r['unparseable']:>3}"
                  + ("  (dry-run)" if args.dry_run else ""))
        else:
            # Always surface skips (incl. no-compiled) so a no-op is never silent.
            print(f"  {r['date']}  {r['prefix']:<12} {r['status']}")

    if not enriched:
        avail = _enrichable_dates(client)
        print(f"\n  Nothing enriched. Enrichable dates in Drive: "
              f"{', '.join(avail) if avail else '(none)'}")
        print("  (the latest compiled date is held back until its next trading day lands)")


if __name__ == "__main__":
    main()
