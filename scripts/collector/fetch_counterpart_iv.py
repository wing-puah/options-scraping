"""
Fetch the settlement IV of the counterpart option legs that DIDN'T trade, for the IV spread.

The paper-faithful IV spread (Cremers/Weinbaum, via Lin/Lu/Driessen 2013) needs a
matched call+put at the SAME (strike, expiration). The traded-flow subset almost
never carries both legs, so `iv_spread` is ~98% blank on flow alone. Barchart's
per-contract price-history endpoint exposes settlement IV / OI / volume for ANY
listed contract, traded or not, so for each single-sided in-window (10–60 DTE)
(strike, expiration) that DID trade we fetch the missing opposite leg's settlement
IV *as of the trade date D* (from the compiled filename) and complete the pair.

The results are stored in a per-date sidecar on Drive, `counterpart-iv-{YYYYMMDD}.csv`
(schema `lib.counterpart_iv.COUNTERPART_COLUMNS`), one row per fetched counterpart:

    Symbol, Type, Strike, Expires, trade_date, iv, oi, vol, delta, price, fetched_on

`fetched_on` (the run date) is the resume marker: any contract already present is
skipped — including ones Barchart returned nothing for (blank iv, marked attempted
so they aren't re-fetched forever). --force clears the sidecar and re-fetches.

Everything is keyed to the exact trade date D, so the same date-indexed sidecar
serves the backtest (historical D) and a live run (latest D). The rollup
(`lib/flow_summary/core._flow_ticker_rows` via `build_iv_lookup`) reads it back;
`scripts/analysis_pipeline/fetch.py` loads it at analysis time.

Usage:
  python3 scripts/collector/fetch_counterpart_iv.py                        # latest compiled date
  python3 scripts/collector/fetch_counterpart_iv.py --date 2026-06-26
  python3 scripts/collector/fetch_counterpart_iv.py --start 2026-06-01 --end 2026-06-10
  python3 scripts/collector/fetch_counterpart_iv.py --backfill             # every compiled date
  python3 scripts/collector/fetch_counterpart_iv.py --backfill --dry-run   # report scope, no scrape
  python3 scripts/collector/fetch_counterpart_iv.py --date 2026-06-26 --force   # re-fetch from scratch
"""
import argparse
import asyncio
import logging
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(0, str(Path(__file__).parents[1]))
from lib.barchart import options as barchart_options
from lib.barchart import BarchartSession
from lib.parsing import to_float
from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client
from lib.counterpart_iv import (
    COUNTERPART_COLUMNS,
    contract_key,
    needed_counterparts,
    sidecar_name,
)
from lib.logger import safe_err, setup_logging
from compile_flow import FLOW_PREFIXES, compiled_name

log = logging.getLogger("fetch_counterpart_iv")

CHECKPOINT_EVERY = 50
_DEFAULT_COOKIES = str(Path(__file__).parents[2] / "cookies" / "barchart_session.json")


def _fmt(v) -> str:
    return "" if v is None else str(v)


def _fmt_int(v) -> str:
    return "" if v is None else str(int(round(v)))


# ─── Drive helpers ──────────────────────────────────────────────────────────────

def _compiled_flow_rows(client, date_str: str) -> list[dict]:
    """All compiled flow rows for a date, across every flow prefix.

    Falls back to a single raw snapshot per prefix when no compiled file exists
    (historical dates that were scraped once and never merged).
    Returns [] when nothing is found.
    """
    folder = client.find_date_folder(date_str)
    if folder is None:
        return []
    rows: list[dict] = []
    for prefix in FLOW_PREFIXES:
        name = compiled_name(prefix, date_str)
        fid = client.file_exists(name, folder)
        if fid:
            rows += parse_csv(client.download(fid, name=name))
        else:
            snapshots = client.list_files_for_date(prefix, date_str)
            if len(snapshots) == 1:
                f = snapshots[0]
                log.info("%s: no compiled file for %s — using single snapshot %s",
                         date_str, prefix, f["name"])
                rows += parse_csv(client.download(f["id"], name=f["name"]))
    return rows


def _compiled_dates(client) -> list[str]:
    folders = client.list_date_folders()
    out = []
    for d in sorted(folders):
        has_compiled = any(client.file_exists(compiled_name(p, d), folders[d]) for p in FLOW_PREFIXES)
        has_single = any(len(client.list_files_for_date(p, d)) == 1 for p in FLOW_PREFIXES)
        if has_compiled or has_single:
            out.append(d)
    return out


def _latest_compiled_date(client) -> str | None:
    """Newest compiled (or single-snapshot) date, walking newest-first.

    _compiled_dates() walks every date oldest-first to build the full --backfill
    list; when a caller only wants the last element, that means a file_exists (+
    list_files_for_date) round trip per prefix per date all the way from the
    oldest folder. This stops at the first match instead.
    """
    folders = client.list_date_folders()
    for d in sorted(folders, reverse=True):
        has_compiled = any(client.file_exists(compiled_name(p, d), folders[d]) for p in FLOW_PREFIXES)
        has_single = any(len(client.list_files_for_date(p, d)) == 1 for p in FLOW_PREFIXES)
        if has_compiled or has_single:
            return d
    return None


def _load_sidecar(client, date_str: str) -> list[dict]:
    folder = client.find_date_folder(date_str)
    if folder is None:
        return []
    name = sidecar_name(date_str)
    fid = client.file_exists(name, folder)
    return parse_csv(client.download(fid, name=name)) if fid else []


def _upload_sidecar(client, date_str: str, rows: list[dict]) -> None:
    folder = client.get_or_create_date_folder(date_str)
    name = sidecar_name(date_str)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / name
        pd.DataFrame(rows, columns=COUNTERPART_COLUMNS).to_csv(tmp, index=False)
        client.upload(tmp, name, folder)


def _done_keys(sidecar_rows: list[dict]) -> set[tuple]:
    """Contract keys already attempted (row carries a non-blank fetched_on)."""
    done: set[tuple] = set()
    for r in sidecar_rows:
        if not str(r.get("fetched_on", "")).strip():
            continue
        strike = to_float(r.get("Strike"))
        if strike is None:
            continue
        done.add(contract_key(r.get("Symbol", ""), r.get("Type", ""),
                              strike, str(r.get("Expires", ""))[:10]))
    return done


# ─── Fetch ───────────────────────────────────────────────────────────────────────

async def _fetch_iv(session, contract: dict, trade_date: date, timeout_ms: int) -> dict:
    """Scrape one contract's price-history and extract its as-of-D settlement fields.

    Returns {iv, oi, vol, delta, price} as formatted strings (blank when Barchart
    returns nothing or has no row on D). `price` is the day's mark (mid(Bid,Ask) →
    Latest) — the paper's minimum-price filter input; a row with IV but no
    computable mark still yields its other fields (require_mark=False).
    """
    url = barchart_options.option_history_url(
        contract["symbol"], contract["expiration"], contract["strike"], contract["opt_type"])
    try:
        csv_text = await session.fetch_history_fast(url, timeout_ms)
    except Exception as e:
        log.error("Barchart scrape failed for %s: %s", contract["key"], safe_err(e))
        csv_text = None
    details = barchart_options.parse_history_details(csv_text, require_mark=False) if csv_text else {}
    day = details.get(trade_date)
    if not day:
        return {"iv": "", "oi": "", "vol": "", "delta": "", "price": ""}
    return {
        "iv": _fmt(to_float(day.get("IV"))),
        "oi": _fmt_int(to_float(day.get("Open Int"))),
        "vol": _fmt_int(to_float(day.get("Volume"))),
        "delta": _fmt(to_float(day.get("Delta"))),
        "price": _fmt(day.get("_mark")),
    }


def _sidecar_row(contract: dict, trade_date: date, fields: dict, run_date: str) -> dict:
    return {
        "Symbol": contract["symbol"],
        "Type": contract["opt_type"].title(),
        "Strike": contract["strike"],
        "Expires": contract["expiration"].isoformat(),
        "trade_date": trade_date.isoformat(),
        "fetched_on": run_date,
        **fields,
    }


async def _scrape_and_store(
    client, date_str: str, pending: list[dict], sidecar: list[dict],
    trade_date: date, run_date: str, *, headless: bool,
    checkpoint_every: int = CHECKPOINT_EVERY, timeout_ms: int = 15000,
    sleep_s: float = 0.4, session=None,
) -> dict:
    """Fetch each pending counterpart, append a sidecar row, checkpoint to Drive.

    The sidecar is re-uploaded every `checkpoint_every` contracts and once more in
    a finally block (so an interrupt/error still saves scraped work). A `session`
    may be injected for tests; otherwise a BarchartSession is opened here.
    """
    stats = {"processed": 0, "with_iv": 0}
    persisted = 0  # processed count at the last upload — skips a redundant final flush

    def checkpoint(label: str) -> None:
        nonlocal persisted
        _upload_sidecar(client, date_str, sidecar)
        persisted = stats["processed"]
        log.info("%s %s: %d/%d persisted", date_str, label, stats["processed"], len(pending))

    async def run(sess) -> None:
        for i, c in enumerate(pending, 1):
            fields = await _fetch_iv(sess, c, trade_date, timeout_ms)
            sidecar.append(_sidecar_row(c, trade_date, fields, run_date))
            stats["processed"] += 1
            if fields["iv"]:
                stats["with_iv"] += 1
            log.info("[%d/%d] %s %s", i, len(pending), date_str, c["key"])
            if stats["processed"] % checkpoint_every == 0:
                checkpoint("checkpoint")
            if sleep_s:
                await asyncio.sleep(sleep_s)

    try:
        if session is not None:
            await run(session)
        else:
            email, password = os.getenv("BARCHART_EMAIL", ""), os.getenv("BARCHART_PASSWORD", "")
            if not (email and password):
                log.warning("BARCHART_EMAIL/PASSWORD not set — cannot scrape; %d deferred", len(pending))
                return stats
            cookies_path = Path(os.getenv("COOKIES_PATH", _DEFAULT_COOKIES))
            async with BarchartSession(email, password, cookies_path, headless) as sess:
                await run(sess)
    finally:
        if stats["processed"] > persisted:
            checkpoint("flush")
    return stats


# ─── Per-date driver ────────────────────────────────────────────────────────────

def fetch_counterpart_date(client, date_str: str, *, headless: bool, dry_run: bool, force: bool) -> dict:
    base = {"date": date_str}
    flow_rows = _compiled_flow_rows(client, date_str)
    if not flow_rows:
        log.info("%s: no compiled flow file — skipping", date_str)
        return {**base, "status": "no-compiled"}

    wanted = needed_counterparts(flow_rows)
    sidecar = [] if force else _load_sidecar(client, date_str)
    done = _done_keys(sidecar)
    pending = [c for c in wanted if c["key"] not in done]

    already_done = len(wanted) - len(pending)

    if not pending:
        log.info("%s: all %d counterpart(s) already backfilled — skipping (use --force)",
                 date_str, len(wanted))
        return {**base, "status": "complete", "wanted": len(wanted)}

    if dry_run:
        log.info("%s: (dry-run) would fetch %d counterpart(s) of %d", date_str, len(pending), len(wanted))
        return {**base, "status": "backfilled", "wanted": len(wanted), "already_done": already_done,
                "fetched": 0, "with_iv": 0, "remaining": len(pending)}

    run_date = date.today().isoformat()
    stats = asyncio.run(_scrape_and_store(
        client, date_str, pending, sidecar, date.fromisoformat(date_str),
        run_date, headless=headless))
    remaining = len(pending) - stats["processed"]
    log.info("%s: %d wanted, %d already done, %d fetched, %d with IV, %d remaining",
             date_str, len(wanted), already_done, stats["processed"], stats["with_iv"], remaining)
    return {**base, "status": "backfilled", "wanted": len(wanted), "already_done": already_done,
            "fetched": stats["processed"], "with_iv": stats["with_iv"], "remaining": remaining}


def _weekday_range(start_iso: str, end_iso: str) -> list[str]:
    d, end = date.fromisoformat(start_iso), date.fromisoformat(end_iso)
    out = []
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="Single trading date (YYYY-MM-DD).")
    parser.add_argument("--start", help="Range start (YYYY-MM-DD), weekdays only.")
    parser.add_argument("--end", help="Range end (YYYY-MM-DD), weekdays only.")
    parser.add_argument("--backfill", action="store_true", help="Every compiled date in Drive.")
    parser.add_argument("--dry-run", action="store_true", help="Report scope; do not scrape/upload.")
    parser.add_argument("--force", action="store_true", help="Clear the sidecar and re-fetch.")
    parser.add_argument("--no-headless", action="store_true", help="Visible browser.")
    args = parser.parse_args()

    if args.date and (args.start or args.end or args.backfill):
        parser.error("--date is exclusive with --start/--end/--backfill")
    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be given together")

    client = get_drive_client()
    if args.backfill:
        targets = _compiled_dates(client)
    elif args.date:
        targets = [args.date]
    elif args.start:
        targets = _weekday_range(args.start, args.end)
    else:
        latest = _latest_compiled_date(client)
        targets = [latest] if latest else []

    headless = os.getenv("SCRAPE_HEADLESS", "true").lower() != "false" and not args.no_headless
    log.info("Fetch counterpart IV%s — %d date(s)", " (dry-run)" if args.dry_run else "", len(targets))

    results = [fetch_counterpart_date(client, d, headless=headless, dry_run=args.dry_run, force=args.force)
               for d in targets]
    done = [r for r in results if r["status"] == "backfilled"]
    print(f"\nFetch counterpart IV {'dry-run' if args.dry_run else 'run'} summary")
    print(f"  dates targeted: {len(targets)}   dates done: {len(done)}")
    for r in results:
        if r["status"] == "backfilled":
            print(f"  {r['date']}  wanted={r['wanted']:>4}  already_done={r['already_done']:>4}  "
                  f"fetched={r['fetched']:>4}  with_iv={r['with_iv']:>4}  remaining={r['remaining']:>4}"
                  + ("  (dry-run)" if args.dry_run else ""))
        else:
            print(f"  {r['date']}  {r['status']}")


if __name__ == "__main__":
    main()
