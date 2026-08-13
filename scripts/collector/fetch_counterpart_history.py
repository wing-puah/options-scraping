"""
Cache the OPPOSITE-TYPE counterpart of every book entry leg, to make volatility
structures priceable.

WHY THIS EXISTS
---------------
The engine's book is 96% directional verticals. Classifying all 1,607 analysis
plays on primary text gives 21 straddle/strangle rows (1.3%), of which 3 ever
reached BacktestResults, and ZERO calendar or diagonal rows have ever been
priced. So there is no evidence at all about whether a volatility sleeve would
diversify the book — not weak evidence, none. The blocker is data: a straddle
needs a call AND a put at the same strike and expiry, and the option cache was
built from directional legs, so it holds a same-strike pair on only 15 of the
481 (ticker, expiry) groups the book actually entered — 3%.

This collector fetches the missing mirror of each entry leg: same ticker, same
expiry, same strike, opposite type. Measured on the 2026-08-12 book that is
**1,250 contracts** (1,337 mirrors, 87 already cached), and it takes
straddle-ability from 15/481 groups to 481/481.

WHERE IT WRITES, AND WHY THAT IS THE WHOLE DESIGN
-------------------------------------------------
Files go to ``backtests/option_history_cache/`` under the EXISTING
``{TICKER}_{YYYYMMDD}_{STRIKE}{C|P}.csv`` convention, via
``lib.barchart.options.cache_path`` — the same function the backtest reads
through. Nothing downstream needs a code change to see them: ``simulate.py``,
``harness.py``, and the study tier all resolve a contract by that path and will
find these exactly as if the real backtest had scraped them.

A mirror is a real Barchart contract fetched from the real feed, so these rows
are REAL-priced, not modelled. That matters because ``bs_options_hist`` proxy
rows were dropped as evidence on 2026-08-11 for being priced from the same
model that scores them; nothing in this cache has that problem.

WHAT THE DATE FLAGS GOVERN
--------------------------
Same semantics as ``fetch_underlying_ohlc.py``: the feed returns a contract's
whole series in one response, so a window saves no round trip. It selects WHICH
LEGS are mirrored and drives the coverage gate. A mirror whose cached file does
not span its leg's required window is re-fetched even under ``--skip-existing``,
because a short file silently reads downstream as "this structure could not be
priced" rather than "this was never fetched" — a wrong denominator in the
coverage line a vol-sleeve study would be judged on.

``--limit`` exists because 1,250 requests is a long scrape. The run is
resumable by construction: each file is written as it arrives and
``--skip-existing`` (the default) picks up where the last one stopped.

Needs BARCHART_EMAIL/PASSWORD. Nothing here touches Drive or Sheets, and
nothing here is scheduled — this is research-tier, run by hand.

Usage:
  python3 scripts/collector/fetch_counterpart_history.py --dry-run
  python3 scripts/collector/fetch_counterpart_history.py --limit 200
  python3 scripts/collector/fetch_counterpart_history.py --date 2026-04-07
  python3 scripts/collector/fetch_counterpart_history.py --tickers NVDA,SPY
  python3 scripts/collector/fetch_counterpart_history.py --force
"""
import argparse
import asyncio
import csv
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.barchart import BarchartSession  # noqa: E402
from lib.barchart.options import (  # noqa: E402
    cache_path, option_history_url, parse_history_details,
)
from lib.logger import safe_err, setup_logging  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402

log = logging.getLogger("fetch_counterpart_history")

BOOK_CSVS = (
    ROOT / "backtests" / "to_evaluate" / "analysis - BacktestResults.csv",
    ROOT / "backtests" / "to_evaluate" / "analysis - BacktestProxy.csv",
)

# The position path window (config/backtest.yml simulation.path_cap_days). A
# mirror only has to cover from the signal to wherever the path would end, so a
# contract expiring long after the cap does not need bars out to expiry.
PATH_CAP_DAYS = 120

# Entry is the next trading day and the study reads the day after it; 7 calendar
# days clears a long weekend plus a holiday. Same constant, same reason, as
# fetch_underlying_ohlc.COVERAGE_PAD_DAYS.
COVERAGE_PAD_DAYS = 7

# Minimum parsed bars for a fetched file to count as usable. A contract that
# never traded returns a valid CSV with a header and nothing else, and writing
# that would satisfy the coverage gate forever while pricing nothing.
MIN_USABLE_BARS = 2

_LEG_RE = re.compile(
    r"\s*([A-Z][A-Z.\-]*)\s*:\s*(\d{4}-\d{2}-\d{2})\s*:\s*([\d.]+)\s*:\s*([CP])\s*([+-]?\d+)")

_DEFAULT_COOKIES = str(ROOT / "cookies" / "barchart_session.json")

OPP = {"C": "P", "P": "C"}
TYPE_NAME = {"C": "Call", "P": "Put"}


# ─── Book inspection: which contracts need a mirror ──────────────────────────────

def book_entry_legs(start: str | None = None, end: str | None = None,
                    include_bs: bool = False) -> dict[tuple, tuple[str, str]]:
    """``{(ticker, expiration, strike, cp): (first_signal, last_signal)}``.

    Only legs of rows the book actually PRICED (non-empty ``daily_price_csv``)
    are returned, and ``bs_options_hist`` rows are excluded by default — the
    same two filters ``load_book(include_bs=False)`` applies, so this never
    scrapes a mirror for a row no study reads.
    """
    out: dict[tuple, tuple[str, str]] = {}
    for path in BOOK_CSVS:
        if not path.exists():
            log.warning("book export not found, skipping: %s", path)
            continue
        with open(path) as fh:
            for row in csv.DictReader(fh):
                d = str(row.get("signal_date", "")).strip()
                if not d or (start and d < start) or (end and d > end):
                    continue
                if not include_bs and row.get("proxy_method") == "bs_options_hist":
                    continue
                if not str(row.get("daily_price_csv", "")).strip():
                    continue
                for line in str(row.get("legs", "")).split("\n"):
                    m = _LEG_RE.match(line)
                    if not m:
                        continue
                    tk, exp, strike, cp, _qty = m.groups()
                    try:
                        key = (tk.upper(), date.fromisoformat(exp), float(strike), cp)
                    except ValueError:
                        continue
                    lo, hi = out.get(key, (d, d))
                    out[key] = (min(lo, d), max(hi, d))
    return out


def mirrors_of(legs: dict[tuple, tuple[str, str]]) -> dict[tuple, tuple[str, str]]:
    """The opposite-type, same-strike counterpart of each leg, spans merged.

    A leg that is ALREADY somebody else's mirror is not special-cased — the
    coverage gate below decides what to fetch, and a contract the book itself
    entered is simply already cached.
    """
    out: dict[tuple, tuple[str, str]] = {}
    for (tk, exp, strike, cp), (lo, hi) in legs.items():
        key = (tk, exp, strike, OPP[cp])
        have = out.get(key)
        out[key] = (min(lo, have[0]), max(hi, have[1])) if have else (lo, hi)
    return out


# ─── The cache: span, coverage gate ──────────────────────────────────────────────

def contract_path(key: tuple) -> Path:
    tk, exp, strike, cp = key
    return cache_path(HISTORY_CACHE, tk, exp, strike, TYPE_NAME[cp])


def cache_span(key: tuple) -> tuple[date, date] | None:
    """(first, last) bar date of a cached contract, or None if absent/unusable."""
    path = contract_path(key)
    if not path.exists():
        return None
    try:
        details = parse_history_details(path.read_text(), require_mark=False)
    except Exception as e:
        log.warning("%s: cached history unreadable (%s) — treating as absent",
                    path.name, safe_err(e))
        return None
    if len(details) < MIN_USABLE_BARS:
        return None
    days = sorted(details)
    return days[0], days[-1]


def required_window(key: tuple, span: tuple[str, str]) -> tuple[date, date]:
    """The dates a mirror must cover: signal → min(expiry, signal + path cap).

    Capping at the path window rather than at expiry is what keeps a LEAP-dated
    contract from being judged incomplete for bars no simulation would ever read.
    """
    _, exp, _, _ = key
    lo = date.fromisoformat(span[0])
    hi = min(exp, date.fromisoformat(span[1]) + timedelta(days=PATH_CAP_DAYS))
    return lo, hi + timedelta(days=COVERAGE_PAD_DAYS)


def needs_fetch(key: tuple, span: tuple[str, str], *, force: bool,
                skip_existing: bool) -> tuple[bool, str]:
    """``(fetch?, reason)`` for one mirror against the window its leg needs."""
    if force:
        return True, "forced"
    have = cache_span(key)
    if have is None:
        return True, "no cache"
    if not skip_existing:
        return True, "skip-existing off"
    need_lo, need_hi = required_window(key, span)
    # A contract legitimately has no bars before it listed or after it expired,
    # so the gate only asks that the cache reach INTO the required window at
    # both ends, not that it strictly contain it.
    if have[1] < min(need_lo, need_hi) or have[0] > need_hi:
        return True, f"re-fetch (cache spans {have[0]}..{have[1]}, need {need_lo}..{need_hi})"
    return False, f"skipped (cache spans {have[0]}..{have[1]})"


# ─── Scrape ──────────────────────────────────────────────────────────────────────

async def _fetch_one(session, key: tuple, timeout_ms: int) -> str | None:
    tk, exp, strike, cp = key
    try:
        return await session.fetch_history_fast(
            option_history_url(tk, exp, strike, TYPE_NAME[cp]), timeout_ms)
    except Exception as e:
        log.error("history scrape failed for %s: %s", contract_path(key).stem, safe_err(e))
        return None


async def _scrape(pending: list[tuple], *, headless: bool, timeout_ms: int = 30000,
                  sleep_s: float = 0.4, session=None) -> dict:
    """Fetch each pending mirror and write it into the shared option cache.

    Written as they arrive, so an interrupted run keeps everything scraped so
    far and ``--skip-existing`` resumes from there.
    """
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    stats = Counter()

    async def run(sess) -> None:
        for i, key in enumerate(pending, 1):
            name = contract_path(key).stem
            csv_text = await _fetch_one(sess, key, timeout_ms)
            if not csv_text:
                stats["failed"] += 1
                log.warning("[%d/%d] %s: no data", i, len(pending), name)
                continue
            try:
                details = parse_history_details(csv_text, require_mark=False)
            except Exception as e:
                stats["unparsed"] += 1
                log.warning("[%d/%d] %s: unparseable (%s)", i, len(pending), name,
                            safe_err(e))
                continue
            if len(details) < MIN_USABLE_BARS:
                # Never traded. NOT written: an empty file would satisfy the
                # coverage gate forever while pricing nothing.
                stats["no_bars"] += 1
                log.info("[%d/%d] %s: no bars — not written", i, len(pending), name)
                continue
            contract_path(key).write_text(csv_text)
            days = sorted(details)
            stats["fetched"] += 1
            log.info("[%d/%d] %s: %d bars %s..%s", i, len(pending), name,
                     len(details), days[0], days[-1])
            if sleep_s:
                await asyncio.sleep(sleep_s)

    if session is not None:
        await run(session)
    else:
        email = os.getenv("BARCHART_EMAIL", "")
        password = os.getenv("BARCHART_PASSWORD", "")
        if not (email and password):
            log.error("BARCHART_EMAIL/PASSWORD not set — cannot scrape")
            return dict(stats)
        cookies_path = Path(os.getenv("COOKIES_PATH", _DEFAULT_COOKIES))
        async with BarchartSession(email, password, cookies_path, headless) as sess:
            await run(sess)
    return dict(stats)


# ─── Coverage reporting ──────────────────────────────────────────────────────────

def straddleable(legs: dict[tuple, tuple[str, str]]) -> tuple[int, int]:
    """``(groups_with_a_same_strike_pair, total_groups)`` over the book's legs.

    The headline this collector exists to move, and the number any vol-sleeve
    study has to quote its denominator against.
    """
    groups: dict[tuple, set] = defaultdict(set)
    for tk, exp, strike, cp in legs:
        groups[(tk, exp)].add((strike, cp))
    ok = 0
    for members in groups.values():
        strikes = {k for k, _ in members}
        if any((k, "C") in members and (k, "P") in members for k in strikes):
            ok += 1
    return ok, len(groups)


def _cached_view(legs: dict, mirrors: dict) -> dict[tuple, tuple[str, str]]:
    """`legs` plus every mirror already present on disk — the post-fetch picture."""
    view = dict(legs)
    for key, span in mirrors.items():
        if cache_span(key) is not None:
            view[key] = span
    return view


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
    parser.add_argument("--limit", type=int, default=None,
                        help="Fetch at most N contracts this run (resumable).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be fetched; scrape nothing.")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch every selected mirror, cached or not.")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true",
                        default=True, help="Skip mirrors already covering the window "
                                           "(default).")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false",
                        help="Fetch even when the cache already covers the window.")
    parser.add_argument("--include-bs", action="store_true",
                        help="Also mirror legs contributed only by bs_options_hist "
                             "proxy rows (excluded by default, like load_book).")
    parser.add_argument("--no-headless", action="store_true", help="Visible browser.")
    args = parser.parse_args()

    if args.date and (args.start or args.end or args.backfill):
        parser.error("--date is exclusive with --start/--end/--backfill")
    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be given together")

    start, end = (args.date, args.date) if args.date else (args.start, args.end)
    legs = book_entry_legs(start, end, include_bs=args.include_bs)
    if not legs:
        log.info("No book legs selected — nothing to do.")
        return

    if args.tickers:
        wanted = {t.strip().upper() for t in args.tickers.split(",") if t.strip()}
        legs = {k: v for k, v in legs.items() if k[0] in wanted}
        if not legs:
            log.info("No book legs for those tickers — nothing to do.")
            return

    mirrors = mirrors_of(legs)
    decisions = {k: needs_fetch(k, span, force=args.force,
                                skip_existing=args.skip_existing)
                 for k, span in mirrors.items()}
    pending = [k for k, (do, _) in decisions.items() if do]
    pending.sort(key=lambda k: (k[0], k[1], k[2], k[3]))

    have, total = straddleable(legs)
    log.info("book legs %d over %d contracts; mirrors wanted %d",
             len(legs), len(legs), len(mirrors))
    log.info("straddle-able (ticker,expiry) groups now: %d/%d (%.0f%%)",
             have, total, 100 * have / total if total else 0)
    log.info("to fetch %d  |  already covered %d", len(pending), len(mirrors) - len(pending))

    if args.limit is not None and len(pending) > args.limit:
        log.info("--limit %d: fetching the first %d of %d this run (resumable)",
                 args.limit, args.limit, len(pending))
        pending = pending[:args.limit]

    if args.dry_run:
        for key in pending[:20]:
            log.info("  would fetch %s — %s", contract_path(key).stem,
                     decisions[key][1])
        if len(pending) > 20:
            log.info("  ... and %d more", len(pending) - 20)
        log.info("[dry-run] nothing scraped")
        return

    if not pending:
        log.info("Every mirror already covers its window — nothing to do.")
        return

    stats = asyncio.run(_scrape(pending, headless=not args.no_headless))
    log.info("done: %s", "  ".join(f"{k}={v}" for k, v in sorted(stats.items())))

    have_after, total_after = straddleable(_cached_view(legs, mirrors))
    log.info("straddle-able (ticker,expiry) groups after: %d/%d (%.0f%%)",
             have_after, total_after, 100 * have_after / total_after if total_after else 0)


if __name__ == "__main__":
    main()
