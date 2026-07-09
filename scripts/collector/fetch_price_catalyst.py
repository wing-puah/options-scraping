"""
Enrich a day's compiled flow file with each ticker's Barchart price history and
corporate-actions (earnings) calendar — the deterministic feed backing the
Step-5 score_price/score_catalyst rubric (see lib/price_catalyst.py).

For every distinct TICKER in a compiled flow file ({prefix}-YYYYMMDD-compiled.csv,
whose filename date is the trade date D), this scrapes:

  - the ticker's Barchart underlying price history
    (lib.barchart.underlying.stock_history_url + BarchartSession.fetch_history_fast,
    parsed via lib.barchart.options.parse_history_series)
  - the ticker's Barchart corporate actions / earnings calendar
    (BarchartSession.fetch_corporate_actions, parsed via
    lib.barchart.corporate_actions.parse_corporate_actions) — SKIPPED for the
    etfs-flow file, since ETFs don't report earnings

picks the as-of-D cells (lib.price_catalyst.as_of_price_cells /
as_of_earnings_cells — NO LOOK-AHEAD: only bars/events on or before D are ever
used).

Barchart's corporate-actions feed lags on announcing the NEXT earnings date for
recent/live tickers — it's often only visible on the ticker's
barchart.com/stocks/quotes/<ticker>/overview page, not the corporateActions API
feed this scrapes. When `as_of_earnings_cells` comes back with no `next_earnings`
AND the trade date is near-live (within _YFINANCE_FALLBACK_WINDOW_DAYS of today —
see _is_near_live), this falls back to yfinance's forward earnings calendar
(Ticker.calendar). The fallback is intentionally NOT applied to older/backfilled
trade dates: yfinance's calendar only reflects TODAY's forward-looking view, so
using it for a historical trade_date would leak a future earnings date onto a
past row and violate the no-look-ahead invariant above.

APPENDS these columns to every row of that ticker:

    price_d / price_5d_ago / price_20d_high / price_20d_low / price_sma20
    price_50d_high / price_50d_low / price_sma50
    next_earnings / last_earnings
    price_catalyst_enriched_on   the run date (provenance + resume marker)

This is the same enrich-in-place pattern as fetch_iv_percentile/enrich_oi (the
compiled file on Drive is the only store — no separate cache tab): the enriched
file is re-uploaded every CHECKPOINT_EVERY tickers and once more on exit (incl.
KeyboardInterrupt / error), so an interrupted run never loses scraped work.
Resume is per-ticker — any ticker whose rows carry price_catalyst_enriched_on is
skipped (incl. ones Barchart returned nothing for, marked attempted so they
aren't re-fetched forever); --force clears the columns and re-scrapes.

Unlike enrich_oi, this needs NO next-day data, so the LATEST compiled date is
enriched too. --backfill enriches every compiled date. Note a later compile_flow
re-run regenerates the compiled file and DROPS these columns; the next
--backfill re-enriches. Needs BARCHART_EMAIL/PASSWORD.

Usage:
  python3 scripts/collector/fetch_price_catalyst.py                       # latest compiled date
  python3 scripts/collector/fetch_price_catalyst.py --date 2026-06-10
  python3 scripts/collector/fetch_price_catalyst.py --start 2026-06-01 --end 2026-06-10
  python3 scripts/collector/fetch_price_catalyst.py --backfill            # every compiled date
  python3 scripts/collector/fetch_price_catalyst.py --backfill --dry-run  # report, no scrape/upload
  python3 scripts/collector/fetch_price_catalyst.py --date 2026-06-10 --force   # re-scrape from scratch
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
from lib.barchart import options as barchart_options, underlying as barchart_underlying
from lib.barchart import BarchartSession
from lib.barchart.corporate_actions import parse_corporate_actions
from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client
from lib.logger import safe_err, setup_logging
from lib.price_catalyst import (
    PRICE_CATALYST_ENRICH_COLUMNS,
    PRICE_CATALYST_MARKER_COLUMN,
    as_of_earnings_cells,
    as_of_price_cells,
)
from compile_flow import FLOW_PREFIXES
from enrich_oi import _compiled_dates, _latest_compiled_date, _source_file, _upload_rows, _weekday_range

log = logging.getLogger("fetch_price_catalyst")

# All columns this script owns on a flow row: the data columns plus the resume marker.
ALL_COLUMNS = PRICE_CATALYST_ENRICH_COLUMNS + [PRICE_CATALYST_MARKER_COLUMN]

# Re-upload the compiled file to Drive every this-many tickers, bounding how much
# scraping an interruption can cost.
CHECKPOINT_EVERY = 50

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
    """Add any missing price/catalyst/marker columns (blank) in place, preserving values."""
    for row in rows:
        for col in ALL_COLUMNS:
            row.setdefault(col, "")


def _clear_columns(rows: list[dict]) -> None:
    """Reset every price/catalyst/marker column to blank (used by --force)."""
    for row in rows:
        for col in ALL_COLUMNS:
            row[col] = ""


def _done_tickers(rows: list[dict]) -> set[str]:
    """Tickers already attempted — their rows carry a non-blank marker."""
    return {str(row.get("Symbol", "")).strip().upper()
            for row in rows if str(row.get(PRICE_CATALYST_MARKER_COLUMN, "")).strip()} - {""}


# ─── Cell formatting (as_of_* dicts → CSV-safe strings) ──────────────────────────

def _fmt_price(v) -> str:
    return "" if v is None else str(round(v, 4))


def _fmt_date(v) -> str:
    return "" if v is None else v.isoformat()


def _format_cells(price_cells: dict, earnings_cells: dict) -> dict:
    """Merge the as_of price + earnings cells into plain strings for the CSV.

    price_catalyst_from_flow_rows expects price columns as plain decimal strings
    and next_earnings/last_earnings as ISO YYYY-MM-DD strings — this is the only
    place that formatting contract is honored.
    """
    out = {k: _fmt_price(price_cells.get(k)) for k in
           ("price_d", "price_5d_ago", "price_20d_high", "price_20d_low", "price_sma20",
            "price_50d_high", "price_50d_low", "price_sma50")}
    out["next_earnings"] = _fmt_date(earnings_cells.get("next_earnings"))
    out["last_earnings"] = _fmt_date(earnings_cells.get("last_earnings"))
    return out


# ─── Barchart fetch ──────────────────────────────────────────────────────────────

async def _fetch_price_series(session, ticker: str, timeout_ms: int) -> list[tuple[date, float]]:
    """Scrape one ticker's underlying price history → parsed series.

    Empty list on any failure (the ticker is still marked attempted by the caller).
    """
    try:
        csv_text = await session.fetch_history_fast(
            barchart_underlying.stock_history_url(ticker), timeout_ms)
    except Exception as e:
        log.error("Barchart price-history scrape failed for %s: %s", ticker, safe_err(e))
        return []
    return barchart_options.parse_history_series(csv_text) if csv_text else []


async def _fetch_corporate_actions(session, ticker: str, timeout_ms: int) -> list[dict]:
    """Scrape one ticker's corporate actions → parsed [{date, event_type, value}].

    Empty list on any failure (the ticker is still marked attempted by the caller).
    """
    try:
        rows = await session.fetch_corporate_actions(ticker, timeout_ms)
    except Exception as e:
        log.error("Barchart corporate-actions scrape failed for %s: %s", ticker, safe_err(e))
        return []
    return parse_corporate_actions(rows) if rows else []


# ─── yfinance next-earnings fallback (near-live dates only) ──────────────────────

# Tunable: how close trade_date must be to today for the yfinance fallback to
# apply. yfinance's calendar only reflects TODAY's forward view, so this bounds
# the fallback to enrichment runs where "today's forward calendar" and "what was
# knowable on trade_date" are close enough to be the same thing.
_YFINANCE_FALLBACK_WINDOW_DAYS = 3


def _is_near_live(trade_date: date, today: date | None = None) -> bool:
    """True when trade_date is within _YFINANCE_FALLBACK_WINDOW_DAYS of today."""
    return (today or date.today()) - trade_date <= timedelta(days=_YFINANCE_FALLBACK_WINDOW_DAYS)


def _fetch_next_earnings_yfinance(ticker: str) -> date | None:
    """Best-effort next earnings date from yfinance's forward calendar.

    Returns None on any failure (missing key, network error, delisted ticker,
    etc.) — never raises, never blocks the ticker's other cells. Only meaningful
    for near-live trade dates (see _is_near_live) since this reflects TODAY's
    forward view, not an as-of-trade_date one.
    """
    try:
        import yfinance as yf

        calendar = yf.Ticker(ticker).calendar or {}
        dates = calendar.get("Earnings Date") or []
        return min(dates) if dates else None
    except Exception as e:
        log.error("yfinance next-earnings lookup failed for %s: %s", ticker, safe_err(e))
        return None


# ─── Barchart fetch + incremental fill ───────────────────────────────────────────

async def _scrape_and_fill(
    client, prefix: str, date_str: str, rows: list[dict], pending: list[str],
    run_date: str, *, headless: bool, file_name: str,
    checkpoint_every: int = CHECKPOINT_EVERY, timeout_ms: int = 30000,
    sleep_s: float = 0.4, session=None,
) -> dict:
    """Scrape each pending ticker, fill its rows with as-of-D price/catalyst cells,
    and persist.

    The compiled file is re-uploaded every ``checkpoint_every`` tickers and once
    more in a finally block (so an interrupt/error still saves scraped work). Every
    attempted ticker gets PRICE_CATALYST_MARKER_COLUMN set so resume skips it next
    time. A ``session`` may be injected for tests; otherwise a BarchartSession is
    opened (needs BARCHART_EMAIL/PASSWORD).
    """
    rows_by_sym: dict[str, list[dict]] = {}
    for row in rows:
        sym = str(row.get("Symbol", "")).strip().upper()
        if sym:
            rows_by_sym.setdefault(sym, []).append(row)

    trade_date = date.fromisoformat(date_str)
    near_live = _is_near_live(trade_date)
    is_etf = prefix == "etfs-flow"
    stats = {"with_price": 0, "with_earnings": 0, "with_earnings_yfinance": 0, "processed": 0}

    async def run(sess) -> None:
        for i, sym in enumerate(pending, 1):
            series = await _fetch_price_series(sess, sym, timeout_ms)
            price_cells = as_of_price_cells(series, trade_date)
            if is_etf:
                # ETFs don't report earnings — skip the corporate-actions scrape
                # and the yfinance fallback entirely.
                earnings_cells = {"next_earnings": None, "last_earnings": None}
            else:
                actions = await _fetch_corporate_actions(sess, sym, timeout_ms)
                earnings_cells = as_of_earnings_cells(actions, trade_date)
                if earnings_cells.get("next_earnings") is None and near_live:
                    fallback = _fetch_next_earnings_yfinance(sym)
                    if fallback is not None:
                        earnings_cells = {**earnings_cells, "next_earnings": fallback}
                        stats["with_earnings_yfinance"] += 1
            cells = _format_cells(price_cells, earnings_cells)
            cells[PRICE_CATALYST_MARKER_COLUMN] = run_date
            if price_cells.get("price_d") is not None:
                stats["with_price"] += 1
            if earnings_cells.get("next_earnings") is not None or earnings_cells.get("last_earnings") is not None:
                stats["with_earnings"] += 1
            for row in rows_by_sym.get(sym, []):
                row.update(cells)
            stats["processed"] += 1
            log.info("[%d/%d] %s %s: %s price_d=%s next_earnings=%s", i, len(pending), prefix, date_str,
                     sym, cells.get("price_d") or "—", cells.get("next_earnings") or "—")
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
    """Enrich one flow type for one date with per-ticker price/catalyst cells."""
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
                "pending": len(pending), "processed": 0, "with_price": 0, "with_earnings": 0,
                "with_earnings_yfinance": 0}

    run_date = date.today().isoformat()
    stats = asyncio.run(_scrape_and_fill(
        client, prefix, date_str, rows, pending, run_date,
        headless=headless, file_name=file_name))

    log.info("%s %s: %d row(s), %d ticker(s), %d pending, %d processed, %d with price, "
             "%d with earnings (%d via yfinance fallback)",
             prefix, date_str, len(rows), len(tickers), len(pending),
             stats["processed"], stats["with_price"], stats["with_earnings"],
             stats["with_earnings_yfinance"])
    return {**base, "status": "enriched", "rows": len(rows), "tickers": len(tickers),
            "pending": len(pending), "processed": stats["processed"],
            "with_price": stats["with_price"], "with_earnings": stats["with_earnings"],
            "with_earnings_yfinance": stats["with_earnings_yfinance"]}


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
    log.info("Fetch price catalyst%s — %d date(s)", " (dry-run)" if args.dry_run else "", len(targets))

    results = [enrich_prefix(client, prefix, d, headless=headless, dry_run=args.dry_run,
                             force=args.force)
               for d in targets for prefix in FLOW_PREFIXES]

    enriched = [r for r in results if r["status"] == "enriched"]
    print(f"\nFetch price catalyst {'dry-run' if args.dry_run else 'run'} summary")
    print(f"  dates targeted:   {len(targets)}")
    print(f"  type/dates done:  {len(enriched)}")
    for r in results:
        if r["status"] == "enriched":
            print(f"  {r['date']}  {r['prefix']:<12} "
                  f"tickers={r['tickers']:>4}  pending={r['pending']:>4}  "
                  f"processed={r['processed']:>4}  with_price={r['with_price']:>4}  "
                  f"with_earnings={r['with_earnings']:>4}  "
                  f"yfinance_fallback={r['with_earnings_yfinance']:>4}"
                  + ("  (dry-run)" if args.dry_run else ""))
        else:
            print(f"  {r['date']}  {r['prefix']:<12} {r['status']}")

    if not enriched:
        avail = _compiled_dates(client)
        print(f"\n  Nothing enriched. Compiled dates in Drive: "
              f"{', '.join(avail) if avail else '(none)'}")


if __name__ == "__main__":
    main()
