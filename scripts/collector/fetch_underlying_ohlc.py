"""
Cache each backtest-book ticker's Barchart UNDERLYING (stock) OHLC history.

The book already has a daily underlying series — ``Price~`` (one value per day)
read off the cached OPTION history files — but no stock open/high/low anywhere.
The ``Open,High,Low,Latest`` columns in ``backtests/option_history_cache/*.csv``
belong to the OPTION contract, not to the stock. Any study that needs the move
over the session it entered on (open→close), an intraday high/low, or the
signal-close→entry-open gap has to have real stock bars, and this is where they
come from.

One request per ticker, via the same plumbing ``fetch_price_catalyst`` uses
(``lib.barchart.underlying.stock_history_url`` +
``BarchartSession.fetch_history_fast``), written verbatim to

    backtests/underlying_ohlc_cache/{TICKER}.csv

in the standard Barchart history schema, so ``lib.barchart.options`` parses it
unchanged. Reads are handled by ``scripts/backtest_study/lib/underlying.py``.

WHAT THE DATE FLAGS GOVERN
--------------------------
The feed returns the whole series in one response (``limit=1000`` daily bars,
~4 years — more than the book spans), so a date window saves no round trip. It
governs three other things:

  1. TICKER SELECTION — only tickers with book rows inside the window are
     fetched, so ``--date 2026-04-07`` is a cheap top-up after a new analysis
     date lands rather than a 103-ticker re-scrape.
  2. THE COVERAGE GATE — a cached file that does not span the ticker's required
     window is re-fetched EVEN under --skip-existing. Without this, a cache
     written during a narrow run silently under-covers a later window and the
     study reads the gap as "no OHLC available" rather than "never fetched" —
     a wrong denominator in the coverage line the whole report is judged on.
  3. The comparison window of the split gate below.

Windowing the FEED itself is deliberately not done: ``_windowed_history_url``
documents its ``startDate``/``endDate`` params as an unverified guess, and a
silently-ignored window returns recent rows that look like a successful
historical fetch.

THE SPLIT / ADJUSTMENT GATE
---------------------------
Barchart's stock history is served CURRENTLY-ADJUSTED; the cached ``Price~``
values were captured unadjusted, at the time. A split between then and now
misaligns the two series by exactly the split ratio — silently, since both look
like plausible prices. Every fetched ticker is therefore compared against its
own cached ``Price~`` on overlapping dates, and a median relative difference
over SPLIT_FLAG_THRESHOLD is recorded in ``rescaled_tickers.txt``.

That file is a BASIS WARNING, not a quarantine. Measured on the 2026-08-12
scrape it caught 6 of 104 tickers at ratios of exactly 2.000 (XLE), 5.000 (CVNA)
and 10.000 (AVGO, MSTR, NFLX, SMCI), with AVGO and MSTR stepping 10 -> 1 at
their ex-dates. A constant exact ratio is an adjustment; it is also proof the
series is internally consistent, so any RATIO taken off it — which is every
window the study measures — is unaffected. What breaks is absolute dollars and
any comparison mixing these bars with the book's unadjusted prices, so consumers
drop those rows from $-denominated cells only. See
``scripts/backtest_study/lib/underlying.py`` for the consuming side.

Needs BARCHART_EMAIL/PASSWORD. Nothing here touches Drive or Sheets.

Usage:
  python3 scripts/collector/fetch_underlying_ohlc.py                    # every book date
  python3 scripts/collector/fetch_underlying_ohlc.py --date 2026-04-07
  python3 scripts/collector/fetch_underlying_ohlc.py --start 2026-01-02 --end 2026-04-07
  python3 scripts/collector/fetch_underlying_ohlc.py --tickers NVDA,SPY --dry-run
  python3 scripts/collector/fetch_underlying_ohlc.py --force            # re-fetch everything
"""
import argparse
import asyncio
import csv
import logging
import os
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.barchart import BarchartSession  # noqa: E402
from lib.barchart import underlying as barchart_underlying  # noqa: E402
from lib.barchart.options import parse_history_details  # noqa: E402
from lib.logger import safe_err, setup_logging  # noqa: E402
from lib.parsing import to_float  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402

log = logging.getLogger("fetch_underlying_ohlc")

OHLC_CACHE = ROOT / "backtests" / "underlying_ohlc_cache"
RESCALED_FILE = OHLC_CACHE / "rescaled_tickers.txt"

# The book. Both exports are read because BacktestProxy carries ~45 tickers the
# real book never priced, and the study pools both.
BOOK_CSVS = (
    ROOT / "backtests" / "to_evaluate" / "analysis - BacktestResults.csv",
    ROOT / "backtests" / "to_evaluate" / "analysis - BacktestProxy.csv",
)

# A row's required span runs past its signal date: the study needs the entry day
# (signal + 1 trading day) and the day after it. 7 calendar days clears a long
# weekend plus a holiday.
COVERAGE_PAD_DAYS = 7

# Median |scraped close − cached Price~| / Price~ above which a ticker is
# recorded as sitting on a rescaled (split-adjusted) basis. A genuine
# intraday-vs-settlement gap is a few basis points — the 2026-08-12 scrape put
# 98 of 104 tickers at a median of 0.000% — while a split is 50-90%. 1% is far
# outside the former and far inside the latter.
SPLIT_FLAG_THRESHOLD = 0.01

# Cached option files sampled per ticker to build the Price~ comparison series.
# One contract already covers every date it traded; a handful covers the span
# without walking hundreds of files for a check that only needs a median.
MAX_COMPARISON_FILES = 8

_DEFAULT_COOKIES = str(ROOT / "cookies" / "barchart_session.json")


# ─── Book inspection: which tickers, over which dates ────────────────────────────

def book_ticker_windows(start: str | None = None, end: str | None = None,
                        include_bs: bool = False) -> dict[str, tuple[str, str]]:
    """``{ticker: (first_signal_date, last_signal_date)}`` over the book.

    Restricted to rows whose ``signal_date`` falls inside [start, end] when given.
    The per-ticker span — not the global one — is what the coverage gate checks:
    a ticker that only appears in 2026 does not need 2024 bars to be complete.

    ``bs_options_hist`` proxy rows are excluded by default, matching
    ``scripts.backtest_study.lib.book.load_book(include_bs=False)``: they were
    dropped as evidence on 2026-08-11, so scraping the ~59 tickers only they
    contribute is 59 requests spent on rows no study reads.
    """
    spans: dict[str, tuple[str, str]] = {}
    for path in BOOK_CSVS:
        if not path.exists():
            log.warning("book export not found, skipping: %s", path)
            continue
        with open(path) as fh:
            for row in csv.DictReader(fh):
                sym = str(row.get("ticker", "")).strip().upper()
                d = str(row.get("signal_date", "")).strip()
                if not sym or not d:
                    continue
                if (start and d < start) or (end and d > end):
                    continue
                if not include_bs and row.get("proxy_method") == "bs_options_hist":
                    continue
                if not str(row.get("daily_price_csv", "")).strip():
                    continue  # never priced — load_book drops it, so it needs no bars
                lo, hi = spans.get(sym, (d, d))
                spans[sym] = (min(lo, d), max(hi, d))
    return spans


# ─── The cache: span, coverage gate ──────────────────────────────────────────────

def cache_path(ticker: str) -> Path:
    return OHLC_CACHE / f"{ticker.upper().strip()}.csv"


def cache_span(ticker: str) -> tuple[date, date] | None:
    """(first, last) bar date in a ticker's cached file, or None if unusable."""
    path = cache_path(ticker)
    if not path.exists():
        return None
    try:
        details = parse_history_details(path.read_text(), require_mark=False)
    except Exception as e:
        log.warning("%s: cached OHLC unreadable (%s) — treating as absent", ticker, safe_err(e))
        return None
    if not details:
        return None
    days = sorted(details)
    return days[0], days[-1]


def needs_fetch(ticker: str, required: tuple[str, str], *,
                force: bool, skip_existing: bool) -> tuple[bool, str]:
    """``(fetch?, reason)`` for one ticker against its required book span.

    The reason string is logged verbatim, so it is also the operator's evidence
    that the coverage gate ran — "skipped" and "re-fetch (cache spans …)" are
    different outcomes and a run that only ever prints the first is suspicious.
    """
    if force:
        return True, "forced"
    span = cache_span(ticker)
    if span is None:
        return True, "no cache"
    if not skip_existing:
        return True, "skip-existing off"
    need_lo = date.fromisoformat(required[0])
    need_hi = date.fromisoformat(required[1]) + timedelta(days=COVERAGE_PAD_DAYS)
    have_lo, have_hi = span
    if have_lo > need_lo or have_hi < need_hi:
        return True, (f"re-fetch (cache spans {have_lo}..{have_hi}, "
                      f"need {need_lo}..{need_hi})")
    return False, f"skipped (cache spans {have_lo}..{have_hi})"


# ─── The split / adjustment gate ─────────────────────────────────────────────────

def cached_price_tilde(ticker: str, limit: int = MAX_COMPARISON_FILES) -> dict[date, float]:
    """``{date: Price~}`` for a ticker, from its cached OPTION history files.

    This is the same underlying series the book has always used, and the only
    independent record of what the stock was actually trading at on those dates.
    """
    out: dict[date, float] = {}
    if not HISTORY_CACHE.exists():
        return out
    files = sorted(HISTORY_CACHE.glob(f"{ticker.upper().strip()}_*.csv"))[:limit]
    for path in files:
        try:
            details = parse_history_details(path.read_text(), require_mark=False)
        except Exception:
            continue
        for d, row in details.items():
            v = to_float(row.get("Price~"))
            if v is not None and v > 0:
                out.setdefault(d, v)
    return out


def split_check(ticker: str, csv_text: str) -> tuple[float | None, int]:
    """``(median_relative_diff, n_overlapping_dates)`` vs the cached ``Price~``.

    ``(None, 0)`` when there is no overlap to compare — no evidence either way,
    which is NOT the same as passing, and is reported as such.
    """
    tilde = cached_price_tilde(ticker)
    if not tilde:
        return None, 0
    try:
        bars = parse_history_details(csv_text, require_mark=False)
    except Exception:
        return None, 0
    diffs = []
    for d, ref in tilde.items():
        row = bars.get(d)
        if row is None:
            continue
        close = to_float(row.get("Latest"))
        if close is None or close <= 0:
            continue
        diffs.append(abs(close - ref) / ref)
    if not diffs:
        return None, 0
    return statistics.median(diffs), len(diffs)


def _read_rescaled_entries() -> dict[str, tuple[float, int]]:
    """Parse the existing ``rescaled_tickers.txt`` into ``{ticker: (median, n)}``.

    ``{}`` when the file is absent or empty — same "no evidence yet" reading
    ``rescaled_tickers()`` in ``scripts/backtest_study/lib/underlying.py`` gives it.
    """
    out: dict[str, tuple[float, int]] = {}
    if not RESCALED_FILE.exists():
        return out
    for line in RESCALED_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            out[parts[0].upper()] = (float(parts[1]), int(parts[2]))
        except ValueError:
            continue
    return out


def write_rescaled(rescaled: dict[str, tuple[float, int]], checked: set[str] = frozenset(),
                   *, full_rewrite: bool = False) -> None:
    """Record split-adjusted-basis tickers for consumers to handle.

    A run only ATTESTS the tickers it actually split-checked THIS run
    (``checked``): each of those gets this run's verdict — flagged with its
    numbers, or (no longer flagged) removed. Every ticker in the existing file
    that is NOT in ``checked`` — one a partial run never looked at, e.g. because
    --skip-existing left its cache untouched — keeps its prior line verbatim.
    A partial run must never erase evidence about a ticker it didn't check;
    that is what dropped AVGO/CVNA/MSTR/NFLX/SMCI/XLE on 2026-09-05.

    ``full_rewrite=True`` is for --recheck-rescaled only: it re-derives the
    flag for every cached ticker from disk, so there is nothing to merge —
    ``rescaled`` (whatever it flagged) becomes the whole file.

    Not written at all when there is nothing to attest to (nothing fetched,
    nothing checked, and not a full rewrite) — an empty run must not erase a
    previous run's findings.
    """
    if not full_rewrite and not checked:
        return
    if full_rewrite:
        merged = dict(rescaled)
        merged_prior = False
    else:
        prior = _read_rescaled_entries()
        merged = {sym: val for sym, val in prior.items() if sym not in checked}
        merged_prior = bool(merged)  # at least one untouched prior line survives
        merged.update(rescaled)
    OHLC_CACHE.mkdir(parents=True, exist_ok=True)
    lines = [f"# ticker  median_rel_diff  n_overlap   (threshold {SPLIT_FLAG_THRESHOLD:.1%})",
             "# Scraped bars are split-adjusted; cached Price~ is not. RATIOS off these",
             "# bars are valid (a constant factor cancels); absolute dollars and any",
             "# cross-series comparison are not. This is a basis warning, not a quarantine.",
             f"# written {date.today().isoformat()} by scripts/collector/fetch_underlying_ohlc.py"]
    if merged_prior:
        lines.append("# merged with prior entries not re-checked this run")
    for sym, (med, n) in sorted(merged.items()):
        lines.append(f"{sym}\t{med:.4f}\t{n}")
    RESCALED_FILE.write_text("\n".join(lines) + "\n")
    log.warning("%d ticker(s) on a rescaled basis recorded in %s",
                len(merged), RESCALED_FILE)


def recheck_rescaled() -> dict[str, tuple[float, int]]:
    """OFFLINE: re-derive the split flag for every cached ticker, from disk.

    No network call. Reads every ``backtests/underlying_ohlc_cache/<T>.csv``
    already on disk and runs it through the same ``split_check`` a live fetch
    uses (cached OHLC close vs. the cached option-history ``Price~``). This is
    the one path allowed to rewrite ``rescaled_tickers.txt`` in full, because
    it checks every ticker the cache holds, not just the ones a partial
    ``--tickers``/``--skip-existing`` run happened to touch.
    """
    rescaled: dict[str, tuple[float, int]] = {}
    if not OHLC_CACHE.exists():
        return rescaled
    for path in sorted(OHLC_CACHE.glob("*.csv")):
        sym = path.stem.upper()
        try:
            csv_text = path.read_text()
        except Exception as e:
            log.warning("%s: cannot read cached OHLC (%s) — skipping recheck", sym, safe_err(e))
            continue
        med, n_overlap = split_check(sym, csv_text)
        if med is None:
            log.info("%s: no Price~ overlap — UNCHECKED", sym)
        elif med > SPLIT_FLAG_THRESHOLD:
            rescaled[sym] = (med, n_overlap)
            log.info("%s: RESCALED basis (ratio ~%.1fx): median %.2f%% over %d days",
                     sym, 1 / (1 - med), med * 100, n_overlap)
        else:
            log.info("%s: split gate ok: median %.3f%% over %d days", sym, med * 100, n_overlap)
    return rescaled


# ─── Barchart fetch ──────────────────────────────────────────────────────────────

async def _fetch_ohlc(session, ticker: str, timeout_ms: int) -> str | None:
    """Scrape one ticker's stock price history → raw CSV text, or None on failure."""
    try:
        return await session.fetch_history_fast(
            barchart_underlying.stock_history_url(ticker), timeout_ms)
    except Exception as e:
        log.error("Barchart stock-history scrape failed for %s: %s", ticker, safe_err(e))
        return None


async def _scrape(pending: list[str], *, headless: bool, timeout_ms: int = 30000,
                  sleep_s: float = 0.4, session=None) -> dict:
    """Fetch each pending ticker, write its cache file, run the split gate.

    Files are written as they arrive, so an interrupt keeps everything already
    scraped. A ``session`` may be injected for tests; otherwise a BarchartSession
    is opened (needs BARCHART_EMAIL/PASSWORD).
    """
    OHLC_CACHE.mkdir(parents=True, exist_ok=True)
    stats = {"fetched": 0, "failed": 0, "no_overlap": 0}
    rescaled: dict[str, tuple[float, int]] = {}
    checked: set[str] = set()

    async def run(sess) -> None:
        for i, sym in enumerate(pending, 1):
            csv_text = await _fetch_ohlc(sess, sym, timeout_ms)
            if not csv_text:
                stats["failed"] += 1
                log.warning("[%d/%d] %s: no data", i, len(pending), sym)
                continue
            cache_path(sym).write_text(csv_text)
            span = cache_span(sym)
            med, n_overlap = split_check(sym, csv_text)
            if med is None:
                stats["no_overlap"] += 1
                flag = "no Price~ overlap — UNCHECKED"
            else:
                checked.add(sym)  # a real verdict — flagged or clean — was reached
                if med > SPLIT_FLAG_THRESHOLD:
                    rescaled[sym] = (med, n_overlap)
                    flag = (f"RESCALED basis (ratio ~{1 / (1 - med):.1f}x): median {med:.2%} "
                            f"over {n_overlap} days — ratios ok, dollars not")
                else:
                    flag = f"split gate ok: median {med:.3%} over {n_overlap} days"
            stats["fetched"] += 1
            log.info("[%d/%d] %s: %d bars %s — %s", i, len(pending), sym,
                     len(csv_text.splitlines()) - 1,
                     f"{span[0]}..{span[1]}" if span else "(unparsed)", flag)
            if sleep_s:
                await asyncio.sleep(sleep_s)

    if session is not None:
        await run(session)
    else:
        email = os.getenv("BARCHART_EMAIL", "")
        password = os.getenv("BARCHART_PASSWORD", "")
        if not (email and password):
            log.error("BARCHART_EMAIL/PASSWORD not set — cannot scrape")
            return stats
        cookies_path = Path(os.getenv("COOKIES_PATH", _DEFAULT_COOKIES))
        async with BarchartSession(email, password, cookies_path, headless) as sess:
            await run(sess)

    write_rescaled(rescaled, checked)
    stats["rescaled"] = len(rescaled)
    return stats


# ─── Entry point ─────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="Single signal date (YYYY-MM-DD).")
    parser.add_argument("--start", help="Window start (YYYY-MM-DD).")
    parser.add_argument("--end", help="Window end (YYYY-MM-DD).")
    parser.add_argument("--backfill", action="store_true",
                        help="Every date in the book. This is the default.")
    parser.add_argument("--tickers", help="Comma-separated ticker subset.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be fetched; scrape nothing.")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch every selected ticker, cached or not.")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true",
                        default=True, help="Skip tickers whose cache already spans "
                                           "the window (default).")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false",
                        help="Fetch even when the cache already covers the window.")
    parser.add_argument("--include-bs", action="store_true",
                        help="Also select tickers contributed only by bs_options_hist "
                             "proxy rows (excluded by default, like load_book).")
    parser.add_argument("--no-headless", action="store_true", help="Visible browser.")
    parser.add_argument("--recheck-rescaled", action="store_true",
                        help="OFFLINE — no network call. Re-derive the split-adjustment "
                             "flag for every cached backtests/underlying_ohlc_cache/<T>.csv "
                             "already on disk (vs. the cached option-history Price~) and "
                             "rewrite rescaled_tickers.txt IN FULL. Standalone: exclusive "
                             "with every selection/fetch flag.")
    args = parser.parse_args()

    if args.recheck_rescaled:
        if any([args.date, args.start, args.end, args.backfill, args.tickers,
               args.dry_run, args.force, args.include_bs]):
            parser.error("--recheck-rescaled is standalone (offline, whole-cache) — "
                         "it takes no other selection/fetch flags")
        rescaled = recheck_rescaled()
        write_rescaled(rescaled, full_rewrite=True)
        n_cached = sum(1 for _ in OHLC_CACHE.glob("*.csv"))
        log.info("Recheck done — %d of %d cached ticker(s) on a rescaled basis",
                 len(rescaled), n_cached)
        return

    if args.date and (args.start or args.end or args.backfill):
        parser.error("--date is exclusive with --start/--end/--backfill")
    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be given together")

    start, end = (args.date, args.date) if args.date else (args.start, args.end)
    spans = book_ticker_windows(start, end, include_bs=args.include_bs)

    if args.tickers:
        wanted = {t.strip().upper() for t in args.tickers.split(",") if t.strip()}
        missing = wanted - set(spans)
        # A ticker with no book rows in the window still gets fetched — an
        # explicit --tickers is an instruction, not a filter — but its required
        # span is the window itself, so the coverage gate still has something
        # to check.
        for sym in sorted(missing):
            if start and end:
                spans[sym] = (start, end)
            else:
                log.warning("%s has no book rows in the window and no window was "
                            "given — fetching with no coverage gate", sym)
                spans[sym] = (date.today().isoformat(), date.today().isoformat())
        spans = {k: v for k, v in spans.items() if k in wanted}

    if not spans:
        log.info("No tickers selected — nothing to do.")
        return

    decisions = {sym: needs_fetch(sym, span, force=args.force,
                                  skip_existing=args.skip_existing)
                 for sym, span in sorted(spans.items())}
    pending = [sym for sym, (fetch, _) in decisions.items() if fetch]

    log.info("Underlying OHLC%s — %d ticker(s) selected, %d pending%s",
             " (dry-run)" if args.dry_run else "", len(spans), len(pending),
             f", window {start}..{end}" if start else "")
    for sym, (fetch, reason) in decisions.items():
        log.info("  %-6s %-9s %s  (book %s..%s)", sym, "FETCH" if fetch else "skip",
                 reason, *spans[sym])

    if args.dry_run or not pending:
        return

    headless = os.getenv("SCRAPE_HEADLESS", "true").lower() != "false" and not args.no_headless
    stats = asyncio.run(_scrape(pending, headless=headless))
    log.info("Done — %d fetched, %d failed, %d unchecked (no Price~ overlap), "
             "%d on a rescaled basis",
             stats["fetched"], stats["failed"], stats["no_overlap"], stats.get("rescaled", 0))


if __name__ == "__main__":
    main()
