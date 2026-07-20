"""
Enrich a day's compiled flow file with each ticker's Barchart IV percentile.

The framework's Step-4 structure ladder needs a per-NAME "rich vs cheap" read to pick
a debit spread (TF, cheap IV) vs a credit spread (TF-S, rich IV). Barchart's
options-overview history carries, per historical date, that name's **IV**, **IV rank**
and **IV percentile** (percentile = share of the prior-1yr days with IV below today's;
already computed — nothing to compute here, see lib/barchart/iv_history.py).

For every distinct TICKER in a compiled flow file ({prefix}-YYYYMMDD-compiled.csv,
whose filename date is the trade date D), this scrapes that name's options-overview
history for a small window around D (via startDate/endDate — a handful of rows, not the
full ~2-year series), picks the values AS OF D (exact date, else the most recent within
a staleness window), and APPENDS these columns to every row of that ticker:

    iv        IV level as of D            (points, e.g. 55.32)
    iv_rank   IV rank as of D             (decimal fraction, e.g. 0.62)
    iv_pct    IV percentile as of D       (decimal fraction, e.g. 0.71) — the scored read
    iv_pct_enriched_on   the run date     (provenance + resume marker)

This is the same enrich-in-place pattern as enrich_oi (the compiled file on Drive is
the only store — no separate cache tab): the enriched file is re-uploaded every
CHECKPOINT_EVERY tickers and once more on exit (incl. KeyboardInterrupt / error), so an
interrupt never loses scraped work. Resume is per-ticker — any ticker whose rows carry
`iv_pct_enriched_on` is skipped (incl. ones Barchart returned nothing for, marked
attempted so they aren't re-fetched forever); --force clears the columns and re-scrapes.

Unlike enrich_oi, this needs NO next-day data, so the LATEST compiled date is enriched
too (IV as of D is published EOD of D). --backfill enriches every compiled date. Note a
later compile_flow re-run regenerates the compiled file and DROPS these columns; the
next --backfill re-enriches. Needs BARCHART_EMAIL/PASSWORD.

Usage:
  python3 scripts/collector/fetch_iv_percentile.py                       # latest compiled date
  python3 scripts/collector/fetch_iv_percentile.py --date 2026-06-10
  python3 scripts/collector/fetch_iv_percentile.py --start 2026-06-01 --end 2026-06-10
  python3 scripts/collector/fetch_iv_percentile.py --backfill            # every compiled date
  python3 scripts/collector/fetch_iv_percentile.py --backfill --dry-run  # report, no scrape/upload
  python3 scripts/collector/fetch_iv_percentile.py --date 2026-06-10 --force   # re-scrape from scratch
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(0, str(Path(__file__).parents[1]))
from lib.barchart import BarchartSession
from lib.barchart.iv_history import parse_iv_history
from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client
from lib.iv_history import IV_ALL_COLUMNS, IV_MARKER_COLUMN, as_of_iv_cells
from lib.logger import safe_err, setup_logging
from compile_flow import FLOW_PREFIXES
from enrich_oi import _compiled_dates, _latest_compiled_date, _source_file, _upload_rows, _weekday_range

log = logging.getLogger("fetch_iv_percentile")

# Re-upload the compiled file to Drive every this-many tickers, bounding how much
# scraping an interruption can cost.
CHECKPOINT_EVERY = 50

# Calendar-day window fetched around the trade date. Covers the staleness fallback
# (LOOKUP_STALENESS_DAYS) plus weekend/holiday gaps so the as-of-D pick always has a
# candidate; the feed still returns only a handful of rows.
WINDOW_DAYS = 12

_DEFAULT_COOKIES = str(Path(__file__).parents[2] / "cookies" / "barchart_session.json")


# ─── Ticker identification + row state ───────────────────────────────────────────

def _distinct_tickers(rows: list[dict]) -> list[str]:
    """Distinct non-blank Symbols in file order."""
    seen: dict[str, None] = {}
    for row in rows:
        sym = str(row.get("Symbol", "")).strip().upper()
        if sym:
            seen.setdefault(sym, None)
    return list(seen)


def _ensure_columns(rows: list[dict]) -> None:
    """Add any missing IV/marker columns (blank) in place, preserving values."""
    for row in rows:
        for col in IV_ALL_COLUMNS:
            row.setdefault(col, "")


def _clear_columns(rows: list[dict]) -> None:
    """Reset every IV/marker column to blank (used by --force)."""
    for row in rows:
        for col in IV_ALL_COLUMNS:
            row[col] = ""


def _done_tickers(rows: list[dict]) -> set[str]:
    """Tickers already attempted — their rows carry a non-blank marker."""
    return {str(row.get("Symbol", "")).strip().upper()
            for row in rows if str(row.get(IV_MARKER_COLUMN, "")).strip()} - {""}


# ─── Barchart fetch + incremental fill ───────────────────────────────────────────

async def _fetch_series(session, ticker: str, start: str, end: str,
                        timeout_ms: int) -> dict[str, dict]:
    """Scrape one ticker's options-overview IV history for a window → parsed series.

    Empty dict on any failure (the ticker is still marked attempted by the caller).
    """
    try:
        feed = await session.fetch_options_overview_history(ticker, start, end, timeout_ms)
    except Exception as e:
        log.error("Barchart options-history scrape failed for %s: %s", ticker, safe_err(e))
        return {}
    return parse_iv_history(feed) if feed else {}


async def _scrape_and_fill(
    client, prefix: str, date_str: str, rows: list[dict], pending: list[str],
    run_date: str, *, headless: bool, file_name: str,
    checkpoint_every: int = CHECKPOINT_EVERY, timeout_ms: int = 30000,
    sleep_s: float = 0.4, session=None,
) -> dict:
    """Scrape each pending ticker, fill its rows with as-of-D IV cells, and persist.

    The compiled file is re-uploaded every ``checkpoint_every`` tickers and once more in
    a finally block (so an interrupt/error still saves scraped work). Every attempted
    ticker gets IV_MARKER_COLUMN set so resume skips it next time. A ``session`` may be
    injected for tests; otherwise a BarchartSession is opened (needs BARCHART/PASSWORD).
    """
    rows_by_sym: dict[str, list[dict]] = {}
    for row in rows:
        sym = str(row.get("Symbol", "")).strip().upper()
        if sym:
            rows_by_sym.setdefault(sym, []).append(row)

    anchor = date.fromisoformat(date_str)
    start = (anchor - timedelta(days=WINDOW_DAYS)).isoformat()
    stats = {"with_iv": 0, "processed": 0}

    async def run(sess) -> None:
        for i, sym in enumerate(pending, 1):
            series = await _fetch_series(sess, sym, start, date_str, timeout_ms)
            cells = as_of_iv_cells(series, date_str)
            cells[IV_MARKER_COLUMN] = run_date
            if cells.get("iv_pct"):
                stats["with_iv"] += 1
            for row in rows_by_sym.get(sym, []):
                row.update(cells)
            stats["processed"] += 1
            log.info("[%d/%d] %s %s: %s iv_pct=%s", i, len(pending), prefix, date_str,
                     sym, cells.get("iv_pct") or "—")
            if stats["processed"] % checkpoint_every == 0:
                _upload_rows(client, date_str, rows, file_name)
                log.info("%s %s checkpoint: %d/%d tickers persisted to Drive",
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
                            "%d ticker(s) deferred to a later run", len(pending))
                return stats
            cookies_path = Path(os.getenv("COOKIES_PATH", _DEFAULT_COOKIES))
            async with BarchartSession(email, password, cookies_path, headless) as sess:
                await run(sess)
    finally:
        if stats["processed"]:
            _upload_rows(client, date_str, rows, file_name)
            log.info("%s %s flush: %d ticker(s) persisted to Drive",
                     prefix, date_str, stats["processed"])

    return stats


# ─── Per-date driver ─────────────────────────────────────────────────────────────

def enrich_prefix(
    client, prefix: str, date_str: str, *,
    headless: bool, dry_run: bool, force: bool,
) -> dict:
    """Enrich one flow type for one date with per-ticker IV percentile."""
    base = {"prefix": prefix, "date": date_str}
    file_id, file_name = _source_file(client, prefix, date_str)
    if not file_id:
        log.info("%s %s: no compiled file and no single raw snapshot — skipping", prefix, date_str)
        return {**base, "status": "no-compiled"}

    rows = parse_csv(client.download(file_id, name=file_name))
    if not rows:
        log.warning("%s %s: source file is empty — skipping", prefix, date_str)
        return {**base, "status": "empty"}

    _ensure_columns(rows)
    tickers = _distinct_tickers(rows)

    if force:
        _clear_columns(rows)
        done: set[str] = set()
    else:
        done = _done_tickers(rows)

    pending = [t for t in tickers if t not in done]
    if not pending:
        log.info("%s %s: all %d ticker(s) already enriched — skipping (use --force to redo)",
                 prefix, date_str, len(tickers))
        return {**base, "status": "complete", "rows": len(rows), "tickers": len(tickers)}

    if dry_run:
        log.info("%s %s: (dry-run) would scrape %d pending ticker(s) of %d",
                 prefix, date_str, len(pending), len(tickers))
        return {**base, "status": "enriched", "rows": len(rows), "tickers": len(tickers),
                "pending": len(pending), "processed": 0, "with_iv": 0}

    run_date = date.today().isoformat()
    stats = asyncio.run(_scrape_and_fill(
        client, prefix, date_str, rows, pending, run_date,
        headless=headless, file_name=file_name))

    log.info("%s %s: %d row(s), %d ticker(s), %d pending, %d processed, %d with IV%%ile",
             prefix, date_str, len(rows), len(tickers), len(pending),
             stats["processed"], stats["with_iv"])
    return {**base, "status": "enriched", "rows": len(rows), "tickers": len(tickers),
            "pending": len(pending), "processed": stats["processed"],
            "with_iv": stats["with_iv"]}


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="Single trading date (YYYY-MM-DD).")
    parser.add_argument("--start", help="Range start (YYYY-MM-DD), weekdays only.")
    parser.add_argument("--end", help="Range end (YYYY-MM-DD), weekdays only.")
    parser.add_argument("--backfill", action="store_true",
                        help="Target every compiled date in Drive.")
    parser.add_argument("--dry-run", action="store_true", help="Report; do not scrape/upload.")
    parser.add_argument("--force", action="store_true",
                        help="Clear the columns and re-scrape every ticker from scratch.")
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
        latest = _latest_compiled_date(client)  # latest compiled (no next-day hold-back)
        targets = [latest] if latest else []

    headless = os.getenv("SCRAPE_HEADLESS", "true").lower() != "false" and not args.no_headless
    log.info("Fetch IV percentile%s — %d date(s)", " (dry-run)" if args.dry_run else "", len(targets))

    results = []
    for d in targets:
        for prefix in FLOW_PREFIXES:
            try:
                results.append(enrich_prefix(client, prefix, d, headless=headless,
                                             dry_run=args.dry_run, force=args.force))
            except Exception:
                log.exception("%s %s: enrichment failed — skipping (already-scraped tickers "
                               "for this date remain checkpointed; re-run to retry)", prefix, d)
                results.append({"prefix": prefix, "date": d, "status": "error"})

    enriched = [r for r in results if r["status"] == "enriched"]
    print(f"\nFetch IV percentile {'dry-run' if args.dry_run else 'run'} summary")
    print(f"  dates targeted:   {len(targets)}")
    print(f"  type/dates done:  {len(enriched)}")
    for r in results:
        if r["status"] == "enriched":
            print(f"  {r['date']}  {r['prefix']:<12} "
                  f"tickers={r['tickers']:>4}  pending={r['pending']:>4}  "
                  f"processed={r['processed']:>4}  with_iv={r['with_iv']:>4}"
                  + ("  (dry-run)" if args.dry_run else ""))
        else:
            print(f"  {r['date']}  {r['prefix']:<12} {r['status']}")

    if not enriched:
        avail = _compiled_dates(client)
        print(f"\n  Nothing enriched. Compiled dates in Drive: "
              f"{', '.join(avail) if avail else '(none)'}")


if __name__ == "__main__":
    main()
