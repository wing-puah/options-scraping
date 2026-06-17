"""
Enrich a day's compiled flow file with next-day open-interest change and EOD greeks.

When unusual flow prints on trade date D, the trade alone can't say whether it
OPENED a new position or CLOSED an existing one. Open interest settles overnight,
so the OI change visible on D+1 is the confirmation: a rise of ~the trade size
means the flow genuinely opened conviction. This is the signal in
references/references_key_insight item 03 (Short-Lived Options).

For every distinct option contract in a compiled flow file ({prefix}-YYYYMMDD-
compiled.csv, where the filename date is the trade date D), this script scrapes
the Barchart per-contract price-history daily series and APPENDS these columns to
every row of that contract:

    oi_d       open interest on D            (exact price-history row on D)
    oi_next    open interest on D+1          (next trading day present in series)
    oi_change  oi_next - oi_d               (the next-day OI change)
    vol_d      traded volume on D
    eod_iv / eod_delta / eod_gamma / eod_vega   end-of-D settlement greeks

The EOD greeks are deliberately prefixed to distinguish them from the intraday
snapshot IV/Delta already carried in the flow row. The enriched CSV is uploaded
in place, replacing the compiled file.

Scraping uses BarchartSession.fetch_history_csv (the background API), NOT the
metered Download button, so tracking every contract is fine. Price histories are
cached in the same dir the backtest uses, so a contract pulled by either tool is
free for the other.

Idempotent: a compiled file that already has the columns is skipped (use --force
to override). Enriching D needs D+1 to exist, so the latest/today's date is never
targeted until the next day lands; --backfill self-heals any missed days. Note
that re-running compile_flow.py for a date regenerates the compiled file from raw
snapshots and DROPS these columns — the next --backfill re-enriches it.

Usage:
  python3 scripts/enrich_oi.py                         # latest enrichable date
  python3 scripts/enrich_oi.py --date 2026-06-09
  python3 scripts/enrich_oi.py --start 2026-06-01 --end 2026-06-10
  python3 scripts/enrich_oi.py --backfill              # every enrichable date
  python3 scripts/enrich_oi.py --backfill --dry-run    # report, no upload
  python3 scripts/enrich_oi.py --date 2026-06-09 --cache-only
"""
import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from lib import barchart_options
from lib.barchart import BarchartSession
from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client
from lib.logger import setup_logging
from backtest.config import HISTORY_CACHE
from backtest.helpers import _contract_key, _num, _parse_expiration
from compile_flow import FLOW_PREFIXES, compiled_name

log = logging.getLogger("enrich_oi")

# Columns appended to every flow row, in this order. Lowercase + underscores so the
# header is robust to whitespace/case quirks when the CSV is read back.
ENRICH_COLUMNS = ["oi_d", "oi_next", "oi_change", "vol_d",
                  "eod_iv", "eod_delta", "eod_gamma", "eod_vega"]


# ─── Drive helpers ──────────────────────────────────────────────────────────────

def _compiled_id(client, prefix: str, date_str: str) -> str | None:
    """Drive file ID of the compiled file for prefix/date, or None if absent."""
    name = compiled_name(prefix, date_str)
    for f in client.list_files(prefix):
        if f["name"] == name:
            return f["id"]
    return None


def _compiled_dates(client) -> list[str]:
    """Every trading date (YYYY-MM-DD) with a compiled file in Drive, oldest → newest."""
    dates: set[str] = set()
    for prefix in FLOW_PREFIXES:
        pat = re.compile(rf"^{re.escape(prefix)}-(\d{{8}})-compiled\.csv$")
        for f in client.list_files(prefix):
            m = pat.match(f["name"])
            if m:
                c = m.group(1)
                dates.add(f"{c[:4]}-{c[4:6]}-{c[6:8]}")
    return sorted(dates)


def _enrichable_dates(client) -> list[str]:
    """Compiled dates that have a strictly-later compiled date (so D+1 data exists).

    Equivalently every compiled date except the most recent one — which is skipped
    until its own next day lands.
    """
    return _compiled_dates(client)[:-1]


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
    matches the backtest's _contract_key so cached histories are shared.
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
    """Build the eight enrichment columns for one contract.

    `details` is {date: row_dict} from parse_history_details. oi_d / vol_d / greeks
    require an exact row on the trade date (no carry-forward — these are EOD-of-D
    settlement values). oi_next is the first series date strictly after D (the next
    trading day, so weekends/holidays are skipped). oi_change needs both ends.
    """
    blank = {c: "" for c in ENRICH_COLUMNS}
    if not details:
        return blank

    day = details.get(trade_date)
    oi_d = _num(day.get("Open Int")) if day else None
    vol_d = _num(day.get("Volume")) if day else None

    later = sorted(d for d in details if d > trade_date)
    oi_next = _num(details[later[0]].get("Open Int")) if later else None

    oi_change = oi_next - oi_d if (oi_next is not None and oi_d is not None) else None

    return {
        "oi_d": _fmt_int(oi_d),
        "oi_next": _fmt_int(oi_next),
        "oi_change": _fmt_int(oi_change),
        "vol_d": _fmt_int(vol_d),
        "eod_iv": _fmt(_num(day.get("IV")) if day else None),
        "eod_delta": _fmt(_num(day.get("Delta")) if day else None),
        "eod_gamma": _fmt(_num(day.get("Gamma")) if day else None),
        "eod_vega": _fmt(_num(day.get("Vega")) if day else None),
    }


def _already_enriched(rows: list[dict]) -> bool:
    """True if the compiled file already carries every enrichment column."""
    return bool(rows) and all(c in rows[0] for c in ENRICH_COLUMNS)


def _apply_enrichment(rows: list[dict], enrichment: dict[tuple, dict]) -> list[dict]:
    """Append the enrichment columns to each row, joined on its contract key."""
    blank = {c: "" for c in ENRICH_COLUMNS}
    out = []
    for row in rows:
        c = _row_contract(row)
        cols = enrichment.get(c["key"], blank) if c else blank
        out.append({**row, **cols})
    return out


# ─── Barchart history fetch (forward-staleness variant) ─────────────────────────

async def _fetch_histories(
    contracts: list[dict], trade_date: date, headless: bool,
    cache_only: bool = False, timeout_ms: int = 15000,
) -> dict[tuple, dict]:
    """Scrape (and cache) each contract's price history, return {key: {date: row}}.

    A cached file is re-scraped when its latest row is on-or-before the trade date
    — i.e. it does not yet reach forward to D+1, the next-day OI we need. Mirrors
    backtest.core._fetch_option_histories but with the staleness check inverted.
    """
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    email = os.getenv("BARCHART_EMAIL", "")
    password = os.getenv("BARCHART_PASSWORD", "")
    cookies_path = Path(os.getenv(
        "COOKIES_PATH", str(HISTORY_CACHE.parent / "cookies" / "barchart_session.json")))

    details_map: dict[tuple, dict] = {}
    to_scrape: list[dict] = []

    for c in contracts:
        cache = barchart_options.cache_path(
            HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
        if cache.exists():
            details = barchart_options.parse_history_details(cache.read_text(encoding="utf-8"))
            details_map[c["key"]] = details
            if cache_only:
                continue
            latest = max(details, default=None)
            if latest is None or latest <= trade_date:
                log.info("Cache for %s latest=%s, need >%s — refetching",
                         c["key"], latest, trade_date)
                details_map.pop(c["key"], None)
                cache.unlink()
                to_scrape.append(c)
        elif not cache_only:
            to_scrape.append(c)
        else:
            log.debug("--cache-only: no cache for %s, skipping", c["key"])

    log.info("Barchart history: %d cached, %d to scrape", len(details_map), len(to_scrape))
    if not to_scrape:
        return details_map
    if not (email and password):
        log.warning("BARCHART_EMAIL/PASSWORD not set — scraping skipped; "
                    "%d contract(s) left blank", len(to_scrape))
        return details_map

    async with BarchartSession(email, password, cookies_path, headless) as session:
        for i, c in enumerate(to_scrape, 1):
            url = barchart_options.option_history_url(
                c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            log.info("[%d/%d] Barchart history: %s", i, len(to_scrape), url)
            try:
                csv_text = await session.fetch_history_csv(url, timeout_ms)
            except Exception:
                log.exception("Barchart history scrape failed for %s", c["key"])
                csv_text = None
            if not csv_text:
                details_map.setdefault(c["key"], {})
                continue
            cache = barchart_options.cache_path(
                HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            cache.write_text(csv_text, encoding="utf-8")
            details_map[c["key"]] = barchart_options.parse_history_details(csv_text)
            await asyncio.sleep(2)

    return details_map


# ─── Per-date driver ────────────────────────────────────────────────────────────

def enrich_prefix(
    client, prefix: str, date_str: str, *,
    headless: bool, dry_run: bool, cache_only: bool, force: bool,
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

    if _already_enriched(rows) and not force:
        log.info("%s %s: already enriched — skipping (use --force to redo)", prefix, date_str)
        return {**base, "status": "already-enriched", "rows": len(rows)}

    contracts, unparseable = _distinct_contracts(rows)
    trade_date = date.fromisoformat(date_str)
    details_map = asyncio.run(_fetch_histories(
        list(contracts.values()), trade_date, headless, cache_only=cache_only))

    enrichment = {key: _compute_enrichment(details_map.get(key, {}), trade_date)
                  for key in contracts}
    with_next = sum(1 for e in enrichment.values() if e["oi_next"] != "")
    new_rows = _apply_enrichment(rows, enrichment)

    if not dry_run:
        name = compiled_name(prefix, date_str)
        folder_id = client.get_or_create_date_folder(date_str)
        tmp = Path(f"/tmp/{name}")
        # Stable column order: original columns first, ENRICH_COLUMNS appended.
        pd.DataFrame(new_rows).to_csv(tmp, index=False)
        client.upload(tmp, name, folder_id)
        tmp.unlink(missing_ok=True)

    log.info("%s %s: %d row(s), %d contract(s), %d with next-day OI%s",
             prefix, date_str, len(rows), len(contracts), with_next,
             " (dry-run)" if dry_run else "")
    return {**base, "status": "enriched", "rows": len(rows),
            "contracts": len(contracts), "with_next": with_next,
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
    parser.add_argument("--cache-only", action="store_true",
                        help="Use cached histories only; never scrape Barchart.")
    parser.add_argument("--force", action="store_true",
                        help="Re-enrich even if the columns are already present.")
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
        enrichable = _enrichable_dates(client)
        targets = enrichable[-1:]  # latest enrichable

    headless = os.getenv("SCRAPE_HEADLESS", "true").lower() != "false" and not args.no_headless
    log.info("Enrich OI%s — %d date(s)", " (dry-run)" if args.dry_run else "", len(targets))

    results = [enrich_prefix(client, prefix, d, headless=headless, dry_run=args.dry_run,
                             cache_only=args.cache_only, force=args.force)
               for d in targets for prefix in FLOW_PREFIXES]

    enriched = [r for r in results if r["status"] == "enriched"]
    print(f"\nEnrich OI {'dry-run' if args.dry_run else 'run'} summary")
    print(f"  dates targeted:   {len(targets)}")
    print(f"  type/dates done:  {len(enriched)}")
    for r in results:
        if r["status"] == "enriched":
            print(f"  {r['date']}  {r['prefix']:<12} "
                  f"contracts={r['contracts']:>4}  with_next={r['with_next']:>4}  "
                  f"unparseable={r['unparseable']:>3}"
                  + ("  (dry-run)" if args.dry_run else ""))
        elif r["status"] not in ("no-compiled",):
            print(f"  {r['date']}  {r['prefix']:<12} {r['status']}")


if __name__ == "__main__":
    main()
