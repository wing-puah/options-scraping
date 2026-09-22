"""
Backfill a near-the-money option-CHAIN history into the shared Barchart cache
so a separate simulated desk (``~/claude_playground/agent-trading``) can
backtest on REAL quotes only, instead of a modelled/Black-Scholes proxy.

WHY THIS EXISTS
---------------
``fetch_counterpart_history.py`` and ``fetch_sweep_legs.py``/``fetch_far_legs.py``/
``fetch_financing_legs.py`` all fill the cache from THIS book's own trade
legs (mirrors, calendar/diagonal/condor targets anchored on an entry). They
have no reason to fetch a strike this book never touched. The other desk's
backtester has no book to anchor on at all — it needs a plain near-the-money
CHAIN across time: every Friday expiry, a band of strikes around the
underlying's close, for every date that expiry was tradeable inside a normal
swing-trade DTE window. This script derives THAT universe directly from an
underlying's daily close history rather than from any book export, and fills
the same shared cache.

REUSE (cite, don't copy)
-------------------------
  - ``lib.barchart.session.BarchartSession.fetch_history_fast`` — one fetch
    returns a contract's WHOLE daily history since 2020-01-01
    (``HISTORY_START_DATE``, pinned by ``_augment_history_url``); a window
    flag on this script would buy nothing, same reasoning as
    ``fetch_underlying_ohlc.py`` and ``fetch_counterpart_history.py``.
  - ``lib.barchart.options.option_history_url`` — the contract URL.
  - ``lib.barchart.options.cache_path`` — the shared
    ``{TICKER}_{YYYYMMDD}_{STRIKE}{C|P}.csv`` convention; ``contract_path``
    below mirrors ``fetch_counterpart_history.py``'s helper of the same name
    (documented pattern: ``fetch_sweep_legs.py`` does the same mirroring
    rather than importing a function bound to another module's globals).
  - ``lib.barchart.options.parse_history_details`` — used to count usable
    bars and pull first/last date, exactly as
    ``fetch_counterpart_history.py._scrape`` does.
  - ``scripts.collector.fetch_counterpart_history.MIN_USABLE_BARS`` — a
    contract that never traded returns a valid CSV with a header and no
    rows; writing that would satisfy "this exists" forever while pricing
    nothing. Imported, not re-defined, so the two collectors can never
    silently disagree about the threshold.
  - The BARCHART_EMAIL / BARCHART_PASSWORD / COOKIES_PATH env-var reads and
    the ``fetched / failed / no_bars / unparsed`` outcome vocabulary mirror
    ``fetch_counterpart_history.py._scrape`` verbatim.

Nothing in ``fetch_counterpart_history.py`` or ``lib/barchart/session.py``
is modified — both are imported and used exactly as they already exist.

THE PLAN (contract universe)
-----------------------------
For each symbol:
  1. Expiries = every Friday (weekly + monthly are the same list; Barchart
     doesn't need told which) whose DTE window ``[expiry - dte_max,
     expiry - dte_min]`` intersects ``[--from, --to]``. A Friday landing on
     an NYSE holiday resolves to the Thursday before it (see
     ``_NYSEHolidayCalendar`` — an ASSUMPTION, documented there).
  2. For each such expiry, the quote-date window is that DTE span clipped to
     ``[--from, --to]``. The underlying's daily CLOSE range over exactly
     those quote dates (not the whole span) sets the strike band — a strike
     that was only ever near-the-money outside this expiry's DTE window is
     not this expiry's business.
  3. Strikes run ``[min_close*(1-band), max_close*(1+band)]`` on the
     PER-SYMBOL grid table below (an assumption — see its docstring).
  4. Puts and/or calls per ``--rights``.

Underlying closes come from ``~/claude_playground/agent-trading/data/history/
<SYM>.csv`` (read-only — this script never writes there) when that file
exists and covers the window; otherwise yfinance, itself cached under
``backtests/underlying_close_cache/<SYM>.csv`` so a second run never re-hits
the network for the same symbol. The yfinance path is NOT exercised by the
2021-12-01..2026-09-18 SPY/QQQ/IWM/GLD/TLT/SMH/XLE/XLF dry run this script
ships with — the desk's CSVs already cover that whole span for all eight.

IDEMPOTENCY / APPEND-ONLY
--------------------------
Unlike ``fetch_counterpart_history.py`` (which overwrites), this collector
NEVER overwrites an existing cache file — a contract already in
``option_history_cache/`` is skipped outright. A manifest CSV,
``backtests/option_history_cache_backfill_manifest.csv`` (a sibling of
``option_history_cache/``, not inside it — CLAUDE.md's cache-loss incident
notes at ~187-192 are about files INSIDE that directory getting unlinked
before a refetch; this manifest is never in the fetch path of any other
script), records every attempted contract with its outcome. A contract
already marked ``fetched`` or ``no_bars`` in the manifest is never
re-requested — ``no_bars`` means "confirmed, via a real request, that this
strike never listed," and re-asking doesn't change that answer. ``failed``/
``unparsed`` rows ARE retried on the next run (those usually mean a
transient network/parse hiccup, not "this doesn't exist").

SAFETY
------
The fetch loop stops cleanly after ``--fail-stop`` (default 10) consecutive
``failed``/``unparsed`` outcomes, or immediately if ``BarchartSession``
raises a login failure (``RuntimeError`` from ``__aenter__``) — in both
cases the manifest already reflects every contract attempted so far, so
re-running the SAME command resumes exactly where it stopped.
``--max-contracts`` caps how many contracts (cached/attempted or not) the
PLAN itself considers, applied after sorting by (symbol, expiry, strike,
right) so it is deterministic across runs. Run
``python3 scripts/backup_research_caches.py push`` BY HAND after any real
(``--execute``) run that wrote new cache files (CLAUDE.md; that script is
hand-run by design, never auto-invoked by a collector).

Usage:
  python3 scripts/collector/backfill_chain.py --symbols SPY,QQQ \\
      --from 2021-12-01 --to 2026-09-18
  python3 scripts/collector/backfill_chain.py --symbols SPY --from 2024-01-01 \\
      --to 2024-06-01 --execute --max-contracts 50
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import math
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
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
from scripts.collector.fetch_counterpart_history import MIN_USABLE_BARS  # noqa: E402

log = logging.getLogger("backfill_chain")

MANIFEST_PATH = ROOT / "backtests" / "option_history_cache_backfill_manifest.csv"
MANIFEST_FIELDS = ("symbol", "expiration", "strike", "right", "outcome",
                   "rows", "first_date", "last_date", "timestamp")

# Manifest outcomes that must never be re-requested: "fetched" is on disk
# already, "no_bars" is a real, already-asked answer of "never listed."
_TERMINAL_OUTCOMES = frozenset({"fetched", "no_bars"})

TYPE_NAME = {"C": "Call", "P": "Put"}

_DEFAULT_COOKIES = str(ROOT / "cookies" / "barchart_session.json")

# A rough, documented assumption for the dry-run duration estimate: the
# default --sleep (0.4s) plus an observed round trip for fetch_history_fast's
# re-issued feed request (no full page navigation) in the 2026-09-22 probe.
# Not a promise — a real run may be faster (session warm) or slower (retries).
SECONDS_PER_CONTRACT = 2.0

AGENT_TRADING_HISTORY_DIR = Path.home() / "claude_playground" / "agent-trading" / "data" / "history"
UNDERLYING_CLOSE_CACHE = ROOT / "backtests" / "underlying_close_cache"


# ─── Per-symbol strike grid (ASSUMPTION) ───────────────────────────────────────
#
# {symbol: (threshold, below_grid, above_grid)} — strikes below `threshold`
# are spaced `below_grid` apart, strikes >= `threshold` are spaced
# `above_grid` apart. This is a documented ASSUMPTION about which strikes
# Barchart actually lists, not something read off a chain: SPY/QQQ list $1
# strikes too (skipped here on purpose — the desk's spreads in
# ~/claude_playground/agent-trading are $5-wide, so a $1 grid would multiply
# the fetch volume ~5x for strikes the desk never trades) and list only $5
# strikes above $200, which both symbols have stayed above for this whole
# backfill span, so their `below_grid` value is unreachable in practice and
# included only for symmetry. IWM/GLD/TLT/SMH/XLE/XLF list $1 strikes below
# $200 and $5 above it, and DO cross that boundary within 2021-2026.
STRIKE_GRID: dict[str, tuple[float, float, float]] = {
    "SPY": (200.0, 5.0, 5.0),
    "QQQ": (200.0, 5.0, 5.0),
    "IWM": (200.0, 1.0, 5.0),
    "GLD": (200.0, 1.0, 5.0),
    "TLT": (200.0, 1.0, 5.0),
    "SMH": (200.0, 1.0, 5.0),
    "XLE": (200.0, 1.0, 5.0),
    "XLF": (200.0, 1.0, 5.0),
}


def strike_grid(symbol: str, lo: float, hi: float) -> list[float]:
    """Grid-aligned strikes in ``[lo, hi]`` per ``STRIKE_GRID`` (see its docstring)."""
    if symbol not in STRIKE_GRID:
        raise KeyError(f"no strike grid entry for {symbol!r} — add one to STRIKE_GRID")
    if lo > hi:
        return []
    threshold, below, above = STRIKE_GRID[symbol]
    strikes: set[float] = set()

    seg_hi = min(hi, threshold - below)
    if lo <= seg_hi + 1e-9:
        k = math.ceil((lo - 1e-9) / below) * below
        while k <= seg_hi + 1e-9:
            strikes.add(round(k, 2))
            k += below

    seg_lo = max(lo, threshold)
    if seg_lo <= hi + 1e-9:
        k = math.ceil((seg_lo - 1e-9) / above) * above
        while k <= hi + 1e-9:
            strikes.add(round(k, 2))
            k += above

    return sorted(strikes)


# ─── NYSE holiday calendar (ASSUMPTION) ────────────────────────────────────────

def _nyse_holidays(lo: date, hi: date) -> set[date]:
    """NYSE holidays in ``[lo, hi]``, approximated from the federal calendar.

    ASSUMPTION: ``pandas_market_calendars`` is not installed in this
    environment and this task makes no network request (so it cannot be
    pip-installed here either). This approximates the NYSE calendar as the
    US federal holiday calendar (already a `pandas` dependency — no new
    install) MINUS Columbus Day and Veterans Day (federal holidays the NYSE
    stays open for) PLUS Good Friday (an NYSE closure with no federal
    holiday). It does not model one-off closures (9/11, hurricane closures,
    a funeral) since those aren't derivable from a rule — only the Friday
    expiries this script's plan touches are ever checked against it, and a
    misclassified one-off would at most shift one expiry by a day.
    """
    from pandas.tseries.holiday import AbstractHolidayCalendar, GoodFriday, USFederalHolidayCalendar

    class _NYSEHolidayCalendar(AbstractHolidayCalendar):
        rules = [r for r in USFederalHolidayCalendar.rules
                if r.name not in ("Columbus Day", "Veterans Day")] + [GoodFriday]

    idx = _NYSEHolidayCalendar().holidays(start=str(lo), end=str(hi))
    return {d.date() if hasattr(d, "date") else d for d in idx}


def candidate_expiries(lo: date, hi: date) -> list[date]:
    """Every Friday in ``[lo, hi]``, holiday-adjusted to the prior Thursday."""
    holidays = _nyse_holidays(lo - timedelta(days=3), hi)
    first_friday = lo + timedelta(days=(4 - lo.weekday()) % 7)
    out: list[date] = []
    d = first_friday
    while d <= hi:
        out.append(d - timedelta(days=1) if d in holidays else d)
        d += timedelta(days=7)
    return sorted(set(out))


# ─── Underlying closes ──────────────────────────────────────────────────────────

def _read_agent_trading_closes(symbol: str):
    """A pandas Series {date: close} from the desk's read-only history CSV,
    or None if it doesn't exist / isn't readable. Never writes there."""
    path = AGENT_TRADING_HISTORY_DIR / f"{symbol}.csv"
    if not path.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_csv(path, usecols=["date", "close"])
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df.set_index("date")["close"]
    except Exception as e:
        log.warning("%s: agent-trading history unreadable (%s) — falling back", symbol, e)
        return None


def _read_yfinance_closes(symbol: str, lo: date, hi: date):
    """Fallback when the desk's CSV is absent/unreadable, cached to
    ``backtests/underlying_close_cache/<SYM>.csv`` so a second call never
    re-hits the network. NOT exercised by this script's default dry run —
    every symbol it ships with is fully covered by the desk's CSVs."""
    import pandas as pd

    cache_file = UNDERLYING_CLOSE_CACHE / f"{symbol}.csv"
    if cache_file.exists():
        df = pd.read_csv(cache_file)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df.set_index("date")["close"]

    import yfinance as yf  # imported lazily — never needed by the shipped dry run
    data = yf.download(symbol, start=str(lo), end=str(hi + timedelta(days=1)), progress=False)
    if data is None or data.empty:
        return None
    closes = data["Close"]
    if hasattr(closes, "squeeze"):
        closes = closes.squeeze()
    out = pd.DataFrame({"date": [d.date() for d in closes.index], "close": closes.values})
    UNDERLYING_CLOSE_CACHE.mkdir(parents=True, exist_ok=True)
    out.to_csv(cache_file, index=False)
    return out.set_index("date")["close"]


def closes_in_window(symbol: str, lo: date, hi: date, *, cache: dict,
                     close_provider=None) -> list[float]:
    """Daily closes for ``symbol`` within ``[lo, hi]`` inclusive.

    ``close_provider(symbol) -> Series | None`` is injectable (tests pass a
    synthetic one); it defaults to agent-trading's CSV, then yfinance,
    memoised per symbol in ``cache`` for the life of one process/plan.
    """
    if symbol not in cache:
        provider = close_provider or _read_agent_trading_closes
        series = provider(symbol)
        if (series is None or len(series) == 0) and close_provider is None:
            series = _read_yfinance_closes(symbol, lo, hi)
        cache[symbol] = series
    series = cache[symbol]
    if series is None:
        return []
    window = series[(series.index >= lo) & (series.index <= hi)]
    return [float(v) for v in window.values]


# ─── Contract identity / cache path (mirrors fetch_counterpart_history.py) ────

def contract_path(symbol: str, expiration: date, strike: float, right: str) -> Path:
    return cache_path(HISTORY_CACHE, symbol, expiration, strike, TYPE_NAME[right])


def _key(symbol: str, expiration: date, strike: float, right: str) -> tuple:
    return (symbol.upper(), expiration.isoformat(), f"{strike:.2f}", right)


# ─── Plan ───────────────────────────────────────────────────────────────────────

def expiry_quote_window(expiry: date, dte_min: int, dte_max: int,
                        from_date: date, to_date: date) -> tuple[date, date] | None:
    """The quote-date window this expiry needs closes for, clipped to
    ``[from_date, to_date]`` — or None if the DTE window doesn't reach into
    the requested span at all."""
    win_lo = expiry - timedelta(days=dte_max)
    win_hi = expiry - timedelta(days=dte_min)
    qd_lo, qd_hi = max(win_lo, from_date), min(win_hi, to_date)
    return (qd_lo, qd_hi) if qd_lo <= qd_hi else None


def plan_for_symbol(symbol: str, from_date: date, to_date: date, dte_min: int,
                    dte_max: int, band: float, rights: list[str], *,
                    close_cache: dict, close_provider=None) -> list[tuple]:
    """Every ``(symbol, expiration, strike, right)`` this symbol's plan wants,
    sorted. Expiries with no underlying-close coverage in their quote window
    contribute nothing (never invent a strike band from no data)."""
    contracts: set[tuple] = set()
    expiries = candidate_expiries(from_date + timedelta(days=dte_min),
                                  to_date + timedelta(days=dte_max))
    for expiry in expiries:
        window = expiry_quote_window(expiry, dte_min, dte_max, from_date, to_date)
        if window is None:
            continue
        closes = closes_in_window(symbol, window[0], window[1], cache=close_cache,
                                  close_provider=close_provider)
        if not closes:
            continue
        lo, hi = min(closes) * (1 - band), max(closes) * (1 + band)
        for strike in strike_grid(symbol, lo, hi):
            for right in rights:
                contracts.add((symbol, expiry, strike, right))
    return sorted(contracts, key=lambda c: (c[0], c[1], c[2], c[3]))


def build_plan(symbols: list[str], from_date: date, to_date: date, dte_min: int,
              dte_max: int, band: float, rights: list[str], *,
              close_provider=None) -> dict[str, list[tuple]]:
    """``{symbol: [contracts...]}`` — the full universe, before any
    already-cached/already-attempted/--max-contracts filtering."""
    close_cache: dict = {}
    return {
        symbol: plan_for_symbol(symbol, from_date, to_date, dte_min, dte_max, band,
                                rights, close_cache=close_cache, close_provider=close_provider)
        for symbol in symbols
    }


# ─── Manifest I/O ───────────────────────────────────────────────────────────────

def load_manifest(path: Path) -> dict[tuple, dict]:
    if not path.exists():
        return {}
    out = {}
    with open(path) as fh:
        for row in csv.DictReader(fh):
            k = (row["symbol"], row["expiration"], row["strike"], row["right"])
            out[k] = {f: row.get(f, "") or "" for f in MANIFEST_FIELDS}
    return out


def write_manifest(path: Path, rows: dict[tuple, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({f: rows[k].get(f, "") for f in MANIFEST_FIELDS})
    tmp.replace(path)  # atomic on the same filesystem: never a half-written manifest on disk


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_terminal(contract: tuple, manifest: dict[tuple, dict]) -> bool:
    """True if the contract must never be re-requested: it is already on
    disk, or the manifest already recorded a `fetched`/`no_bars` outcome for
    it (a real, already-asked answer)."""
    symbol, expiration, strike, right = contract
    if contract_path(symbol, expiration, strike, right).exists():
        return True
    row = manifest.get(_key(symbol, expiration, strike, right))
    return bool(row) and row.get("outcome") in _TERMINAL_OUTCOMES


def categorize(contracts: list[tuple], manifest: dict[tuple, dict]) -> tuple[list, list]:
    """``(terminal, pending)`` — split a contract list by whether it needs a
    request at all."""
    terminal, pending = [], []
    for c in contracts:
        (terminal if is_terminal(c, manifest) else pending).append(c)
    return terminal, pending


# ─── Fetch ────────────────────────────────────────────────────────────────────

async def _fetch_one(session, contract: tuple, timeout_ms: int) -> str | None:
    symbol, expiration, strike, right = contract
    try:
        return await session.fetch_history_fast(
            option_history_url(symbol, expiration, strike, TYPE_NAME[right]), timeout_ms)
    except Exception as e:
        log.error("history scrape failed for %s: %s",
                  contract_path(symbol, expiration, strike, right).stem, safe_err(e))
        return None


async def run_fetch(pending: list[tuple], manifest: dict[tuple, dict], manifest_path: Path, *,
                    fail_stop: int = 10, headless: bool = True, timeout_ms: int = 30000,
                    sleep_s: float = 0.4, session=None) -> dict:
    """Fetch every pending contract, writing its CSV to the cache (never
    overwriting) and the manifest row IMMEDIATELY after each attempt, so a
    crash or a clean stop loses at most the in-flight contract and a re-run
    resumes exactly where this one stopped.

    Stops cleanly (does not raise) after `fail_stop` CONSECUTIVE
    failed/unparsed outcomes, or if the session itself fails to log in
    (RuntimeError from BarchartSession.__aenter__, caught here when this
    function owns session construction).
    """
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    stats = Counter()

    async def run(sess) -> None:
        consecutive_failures = 0
        for i, contract in enumerate(pending, 1):
            symbol, expiration, strike, right = contract
            name = contract_path(symbol, expiration, strike, right).stem
            k = _key(symbol, expiration, strike, right)
            row = {"symbol": symbol, "expiration": expiration.isoformat(),
                  "strike": f"{strike:.2f}", "right": right, "timestamp": _now_iso()}

            csv_text = await _fetch_one(sess, contract, timeout_ms)
            if not csv_text:
                row.update(outcome="failed", rows="0", first_date="", last_date="")
                stats["failed"] += 1
                consecutive_failures += 1
                log.warning("[%d/%d] %s: no data", i, len(pending), name)
            else:
                try:
                    details = parse_history_details(csv_text, require_mark=False)
                except Exception as e:
                    row.update(outcome="unparsed", rows="0", first_date="", last_date="")
                    stats["unparsed"] += 1
                    consecutive_failures += 1
                    log.warning("[%d/%d] %s: unparseable (%s)", i, len(pending), name, safe_err(e))
                else:
                    if len(details) < MIN_USABLE_BARS:
                        row.update(outcome="no_bars", rows=str(len(details)),
                                  first_date="", last_date="")
                        stats["no_bars"] += 1
                        consecutive_failures = 0
                        log.info("[%d/%d] %s: no bars — not written", i, len(pending), name)
                    else:
                        contract_path(symbol, expiration, strike, right).write_text(csv_text)
                        days = sorted(details)
                        row.update(outcome="fetched", rows=str(len(details)),
                                  first_date=days[0].isoformat(), last_date=days[-1].isoformat())
                        stats["fetched"] += 1
                        consecutive_failures = 0
                        log.info("[%d/%d] %s: %d bars %s..%s", i, len(pending), name,
                                len(details), days[0], days[-1])

            manifest[k] = row
            write_manifest(manifest_path, manifest)

            if consecutive_failures >= fail_stop:
                remaining = len(pending) - i
                log.warning(
                    "stopping after %d consecutive failures — %d contract(s) remain; "
                    "the manifest at %s already reflects every attempt so far, so "
                    "re-running the same command resumes from here",
                    fail_stop, remaining, manifest_path)
                stats["stopped_consecutive_failures"] = 1
                return

            if sleep_s:
                await asyncio.sleep(sleep_s)

    if session is not None:
        await run(session)
    else:
        email = os.getenv("BARCHART_EMAIL", "")
        password = os.getenv("BARCHART_PASSWORD", "")
        if not (email and password):
            log.error("BARCHART_EMAIL/BARCHART_PASSWORD not set — cannot scrape")
            return dict(stats)
        cookies_path = Path(os.getenv("COOKIES_PATH", _DEFAULT_COOKIES))
        try:
            async with BarchartSession(email, password, cookies_path, headless) as sess:
                await run(sess)
        except RuntimeError as e:
            log.error(
                "login failed — stopping cleanly (%s). The manifest at %s already "
                "reflects every contract attempted before the failure; re-run the "
                "same command to resume", safe_err(e), manifest_path)
            stats["login_failure"] = 1
    return dict(stats)


# ─── Reporting ───────────────────────────────────────────────────────────────────

def print_dry_run(plan: dict[str, list[tuple]], manifest: dict[tuple, dict], *,
                  max_contracts: int | None, sleep_s: float) -> dict:
    """Per-symbol plan report: contract count, already-terminal, pending, and
    an estimated duration for the pending set. Returns the per-symbol stats
    dict (also useful to callers/tests, not just printed)."""
    report: dict[str, dict] = {}
    total_pending = 0
    for symbol, contracts in plan.items():
        terminal, pending = categorize(contracts, manifest)
        report[symbol] = {"universe": len(contracts), "already_covered": len(terminal),
                          "pending": len(pending)}
        total_pending += len(pending)
        log.info("%-6s  universe=%-5d  already_covered=%-5d  pending=%-5d",
                 symbol, len(contracts), len(terminal), len(pending))

    if max_contracts is not None and total_pending > max_contracts:
        log.info("--max-contracts %d: a real run would fetch only the first %d of %d "
                 "pending contracts (deterministic order: symbol, expiry, strike, right)",
                 max_contracts, max_contracts, total_pending)
        total_pending = min(total_pending, max_contracts)

    est_seconds = total_pending * max(sleep_s, 0) + total_pending * SECONDS_PER_CONTRACT
    log.info("total pending across symbols: %d  |  estimated duration at "
             "~%.1fs/contract (incl. --sleep %.2fs): ~%.0fs (%.1f min)",
             total_pending, SECONDS_PER_CONTRACT, sleep_s, est_seconds, est_seconds / 60)
    log.info("[dry-run] nothing scraped")
    return report


# ─── CLI ─────────────────────────────────────────────────────────────────────────

def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main() -> None:
    setup_logging()
    # backfill_chain isn't in lib.logger._OWN_LOGGERS (read-only allowlist in
    # lib/, per the note in fetch_sweep_legs.py) so INFO would otherwise be
    # silently dropped at the root's WARNING level.
    log.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--symbols", required=True,
                        help="Comma-separated tickers, e.g. SPY,QQQ,IWM.")
    parser.add_argument("--from", dest="from_date", required=True, type=_parse_date,
                        help="Quote-date span start (YYYY-MM-DD).")
    parser.add_argument("--to", dest="to_date", required=True, type=_parse_date,
                        help="Quote-date span end (YYYY-MM-DD).")
    parser.add_argument("--dte-min", type=int, default=20)
    parser.add_argument("--dte-max", type=int, default=60)
    parser.add_argument("--band", type=float, default=0.10, help="Moneyness band, e.g. 0.10 = ±10%%.")
    parser.add_argument("--rights", default="P,C", help="Comma-separated subset of P,C.")
    parser.add_argument("--max-contracts", type=int, default=None,
                        help="Cap on pending contracts a real run fetches this invocation.")
    parser.add_argument("--sleep", type=float, default=0.4, help="Seconds between fetches.")
    parser.add_argument("--fail-stop", type=int, default=10,
                        help="Stop after this many consecutive failures.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Default behaviour: print the plan, scrape nothing "
                             "(kept as an explicit flag for readability; --execute "
                             "is what actually turns scraping on).")
    parser.add_argument("--execute", action="store_true",
                        help="Actually fetch. Without this, the run is ALWAYS a dry "
                             "run regardless of --dry-run.")
    parser.add_argument("--no-headless", action="store_true", help="Visible browser.")
    args = parser.parse_args()

    if args.from_date > args.to_date:
        parser.error("--from must be on or before --to")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    rights = [r.strip().upper() for r in args.rights.split(",") if r.strip()]
    for r in rights:
        if r not in ("P", "C"):
            parser.error(f"--rights: {r!r} is not P or C")
    for s in symbols:
        if s not in STRIKE_GRID:
            parser.error(f"--symbols: no strike grid entry for {s!r} — add one to "
                         f"STRIKE_GRID in this file")

    plan = build_plan(symbols, args.from_date, args.to_date, args.dte_min, args.dte_max,
                      args.band, rights)
    manifest = load_manifest(MANIFEST_PATH)

    log.info("plan: %s .. %s  dte=[%d,%d]  band=%.2f  rights=%s",
             args.from_date, args.to_date, args.dte_min, args.dte_max, args.band, rights)

    if not args.execute:
        print_dry_run(plan, manifest, max_contracts=args.max_contracts, sleep_s=args.sleep)
        return

    all_pending: list[tuple] = []
    for symbol in symbols:
        _terminal, pending = categorize(plan[symbol], manifest)
        all_pending.extend(pending)
    all_pending.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
    if args.max_contracts is not None:
        all_pending = all_pending[:args.max_contracts]

    if not all_pending:
        log.info("Nothing to fetch — every planned contract is already cached or attempted.")
        return

    log.info("fetching %d contract(s)", len(all_pending))
    stats = asyncio.run(run_fetch(all_pending, manifest, MANIFEST_PATH,
                                  fail_stop=args.fail_stop, headless=not args.no_headless,
                                  sleep_s=args.sleep))
    log.info("done: %s", "  ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    log.info("remember to run `python3 scripts/backup_research_caches.py push` by hand "
             "now that the cache has grown")


if __name__ == "__main__":
    main()
