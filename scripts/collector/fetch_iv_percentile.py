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
full series), picks the values AS OF D (exact date, else the most recent within
a staleness window), and APPENDS these columns to every row of that ticker:

    iv        IV level as of D            (points, e.g. 55.32)
    iv_rank   IV rank as of D             (decimal fraction, e.g. 0.62)
    iv_pct    IV percentile as of D       (decimal fraction, e.g. 0.71) — the scored read
    iv_pct_enriched_on   the run date     (provenance + resume marker)
    iv_pct_status        why those cells look the way they do (lib/iv_history):
                         ok | stale_fallback | out_of_window | empty_series | fetch_error

`out_of_window` is the one that matters for backfills: the feed's history window is
measured from the RUN date, so an old enough trade date falls off the far end and its
IVpct can never be filled. Without the status that is indistinguishable from a blank —
and a blank IVpct is not inert, it flips the framework's Step-4 structure choice toward
credit. When enough of a date's tickers come back that way the run prints a DEPTH
EXHAUSTED banner (DEPTH_EXHAUSTED_SHARE).

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
from lib.iv_history import (
    IV_ALL_COLUMNS,
    IV_MARKER_COLUMN,
    IV_STATUS_COLUMN,
    IV_STATUS_EMPTY,
    IV_STATUS_ERROR,
    IV_STATUS_OUT_OF_WINDOW,
    as_of_iv_cells_with_status,
)
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

# Share of a date's PENDING tickers coming back `out_of_window` above which the run
# prints a DEPTH EXHAUSTED banner. The feed's history window is measured from the
# RUN date, so retention falls off the far end for the WHOLE market at once, not name by
# name: a few names missing is ordinary thin coverage, a THIRD of the book missing means
# the retention edge has moved past this trade date and the date's IVpct can never be
# enriched again — the enrichment should be treated as unavailable, not merely blank.
# Set well below 1.0 because the first date past the edge still returns some names
# (staggered listings), and the operator needs to see it on that date, not three
# backfill dates later.
DEPTH_EXHAUSTED_SHARE = 0.33

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
                        timeout_ms: int) -> tuple[dict[str, dict], str]:
    """Scrape one ticker's options-overview IV history for a window → (series, status).

    Empty dict on any failure (the ticker is still marked attempted by the caller). The
    status separates the two blank-producing failures the row could never tell apart:
    ``fetch_error`` (the scrape raised) vs ``empty_series`` (the feed answered with
    nothing). ``""`` means the series is usable and the as-of pick decides the status.
    """
    try:
        feed = await session.fetch_options_overview_history(ticker, start, end, timeout_ms)
    except Exception as e:
        log.error("Barchart options-history scrape failed for %s: %s", ticker, safe_err(e))
        return {}, IV_STATUS_ERROR
    series = parse_iv_history(feed) if feed else {}
    return series, "" if series else IV_STATUS_EMPTY


async def _scrape_and_fill(
    client, prefix: str, date_str: str, rows: list[dict], pending: list[str],
    run_date: str, *, headless: bool, file_name: str,
    checkpoint_every: int = CHECKPOINT_EVERY, timeout_ms: int = 30000,
    sleep_s: float = 0.4, session=None,
) -> dict:
    """Scrape each pending ticker, fill its rows with as-of-D IV cells, and persist.

    The compiled file is re-uploaded every ``checkpoint_every`` tickers and once more in
    a finally block (so an interrupt/error still saves scraped work). Every attempted
    ticker gets IV_MARKER_COLUMN set so resume skips it next time, and IV_STATUS_COLUMN
    set to WHY its cells came out the way they did (see lib.iv_history). A ``session``
    may be injected for tests; otherwise a BarchartSession is opened (needs
    BARCHART/PASSWORD).
    """
    rows_by_sym: dict[str, list[dict]] = {}
    for row in rows:
        sym = str(row.get("Symbol", "")).strip().upper()
        if sym:
            rows_by_sym.setdefault(sym, []).append(row)

    anchor = date.fromisoformat(date_str)
    start = (anchor - timedelta(days=WINDOW_DAYS)).isoformat()
    stats = {"with_iv": 0, "processed": 0, "by_status": {}}

    async def run(sess) -> None:
        for i, sym in enumerate(pending, 1):
            series, fetch_status = await _fetch_series(sess, sym, start, date_str, timeout_ms)
            cells, pick_status = as_of_iv_cells_with_status(series, date_str)
            # A failed/empty fetch already knows why; otherwise the as-of pick decides.
            status = fetch_status or pick_status
            cells[IV_MARKER_COLUMN] = run_date
            cells[IV_STATUS_COLUMN] = status
            if cells.get("iv_pct"):
                stats["with_iv"] += 1
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            for row in rows_by_sym.get(sym, []):
                row.update(cells)
            stats["processed"] += 1
            log.info("[%d/%d] %s %s: %s iv_pct=%s (%s)", i, len(pending), prefix, date_str,
                     sym, cells.get("iv_pct") or "—", status)
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

def _status_summary(by_status: dict) -> str:
    """``iv_pct_status`` counts as one compact, deterministically ordered string."""
    if not by_status:
        return "no statuses"
    return " ".join(f"{s}={n}" for s, n in sorted(by_status.items()))


def _depth_exhausted(by_status: dict, pending: int) -> bool:
    """True when `out_of_window` covers enough of a date's pending tickers that the
    date is past Barchart's retention edge rather than merely thin — see
    DEPTH_EXHAUSTED_SHARE."""
    return bool(pending) and (by_status.get(IV_STATUS_OUT_OF_WINDOW, 0) / pending
                              > DEPTH_EXHAUSTED_SHARE)


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
                "pending": len(pending), "processed": 0, "with_iv": 0, "by_status": {}}

    run_date = date.today().isoformat()
    stats = asyncio.run(_scrape_and_fill(
        client, prefix, date_str, rows, pending, run_date,
        headless=headless, file_name=file_name))

    log.info("%s %s: %d row(s), %d ticker(s), %d pending, %d processed, %d with IV%%ile, %s",
             prefix, date_str, len(rows), len(tickers), len(pending),
             stats["processed"], stats["with_iv"], _status_summary(stats["by_status"]))
    return {**base, "status": "enriched", "rows": len(rows), "tickers": len(tickers),
            "pending": len(pending), "processed": stats["processed"],
            "with_iv": stats["with_iv"], "by_status": stats["by_status"]}


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

    # Built only on the branches that DISCOVER dates, then reused by the "nothing
    # enriched" tail — an explicit --date/--start never pays for a corpus scan.
    index = None
    if args.backfill:
        index = client.flow_corpus(FLOW_PREFIXES)
        targets = _compiled_dates(client, index)
    elif args.date:
        targets = [args.date]
    elif args.start:
        targets = _weekday_range(args.start, args.end)
    else:
        index = client.flow_corpus(FLOW_PREFIXES)
        # latest compiled (no next-day hold-back)
        latest = _latest_compiled_date(client, index)
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
    exhausted = []
    for r in results:
        if r["status"] == "enriched":
            by_status = r.get("by_status") or {}
            print(f"  {r['date']}  {r['prefix']:<12} "
                  f"tickers={r['tickers']:>4}  pending={r['pending']:>4}  "
                  f"processed={r['processed']:>4}  with_iv={r['with_iv']:>4}  "
                  f"{_status_summary(by_status)}"
                  + ("  (dry-run)" if args.dry_run else ""))
            if _depth_exhausted(by_status, r["pending"]):
                exhausted.append(r)
        else:
            print(f"  {r['date']}  {r['prefix']:<12} {r['status']}")

    # Loud, because a blank IVpct is NOT inert: per config/prompts/analysis-framework.md Step 4
    # it flips the structure choice toward credit. A date past the retention edge can
    # never be enriched by a later re-run, so the operator must decide now whether to
    # analyze it at all — silence here is how a whole backfill era acquires a hidden
    # debit/credit bias.
    if exhausted:
        print("\n" + "!" * 78)
        print("  DEPTH EXHAUSTED — Barchart's IV history no longer reaches these dates")
        for r in exhausted:
            n = (r.get("by_status") or {}).get(IV_STATUS_OUT_OF_WINDOW, 0)
            print(f"    {r['date']}  {r['prefix']:<12} {n}/{r['pending']} pending ticker(s) "
                  f"out_of_window (> {DEPTH_EXHAUSTED_SHARE:.0%})")
        print("  These rows carry iv_pct_status=out_of_window: their blank IVpct is a")
        print("  RETENTION artifact, not a market read. Split or exclude them in analysis.")
        print("!" * 78)

    if not enriched:
        # Only worth a corpus index when the operator did NOT name the dates.
        if args.date or args.start:
            print("\n  Nothing enriched for the requested date(s). Run with --backfill "
                  "(or no date flags) to list every compiled date in Drive.")
        else:
            avail = _compiled_dates(client, index)
            print(f"\n  Nothing enriched. Compiled dates in Drive: "
                  f"{', '.join(avail) if avail else '(none)'}")


if __name__ == "__main__":
    main()
