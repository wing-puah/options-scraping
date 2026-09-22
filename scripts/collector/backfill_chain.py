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
  - The BARCHART_EMAIL / BARCHART_PASSWORD / COOKIES_PATH env-var reads
    mirror ``fetch_counterpart_history.py._scrape`` verbatim.

Nothing in ``fetch_counterpart_history.py`` or ``lib/barchart/session.py``
is modified — both are imported and used exactly as they already exist. The
2026-09-22 independent review's item 7/8 fixes read ``lib.barchart.session``'s
WARNING/ERROR log records (see ``_HistorySniffHandler``) rather than change
its return values, specifically so that file stays untouched.

THE PLAN (contract universe)
-----------------------------
For each symbol:
  1. Expiries = every Friday (weekly + monthly are the same list; Barchart
     doesn't need told which) whose DTE window ``[expiry - dte_max,
     expiry - dte_min]`` intersects ``[--from, --to]``. A Friday landing on
     an NYSE holiday resolves to the Thursday before it (``_nyse_holidays``
     — an ASSUMPTION, documented there; corrected 2026-09-22 for Juneteenth
     pre-2022 and the New Year's Saturday shift, see its docstring).
     Expiries on or after today are EXCLUDED by default (``--include-open-
     expiries`` to include them) — the chain for a contract that hasn't
     expired yet can still change, so it must never be marked terminal.
  2. For each such expiry, the quote-date window is that DTE span clipped to
     ``[--from, --to]``. The underlying's daily CLOSE range over exactly
     those quote dates (not the whole span) sets the strike band — a strike
     that was only ever near-the-money outside this expiry's DTE window is
     not this expiry's business.
  3. Strikes run ``[min_close*(1-band), max_close*(1+band)]`` on the
     PER-SYMBOL grid table below (an assumption — see its docstring).
  4. Puts and/or calls per ``--rights``.

Underlying closes come ONLY from ``~/claude_playground/agent-trading/data/
history/<SYM>.csv`` (read-only — this script never writes there). There is
no network fallback (removed 2026-09-22, review item 9 — the previous
yfinance fallback cached only the FIRST expiry's window forever, silently
mis-covering every later one, and any fallback risks a dry run quietly
reaching the network): a missing/empty desk CSV for a requested symbol is a
loud ``UnderlyingDataUnavailable``, not a silently narrower plan.

IDEMPOTENCY / APPEND-ONLY
--------------------------
Unlike ``fetch_counterpart_history.py`` (which overwrites), this collector
NEVER overwrites an existing cache file. A contract's outcome is one of:
``fetched`` (new file written), ``exists`` (the file appeared — another run,
a race — between planning and the write; nothing lost, nothing touched),
``no_bars`` (a REAL request confirmed 0 rows — never re-requested),
``failed``/``unparsed`` (an ambiguous or transient miss — retried on the
next run), ``unavailable`` (``failed``/``unparsed`` on 2 SEPARATE runs —
terminal; see item 7 below). "Terminal" (never re-requested) is: the cache
file exists AND is COMPLETE (see ``file_completeness``), OR the manifest's
last recorded outcome for it is ``no_bars``/``unavailable`` AND the contract
has already expired (item 3/4).

A manifest, ``backtests/option_history_cache_backfill_manifest.csv`` (a
sibling of ``option_history_cache/``, not inside it — CLAUDE.md's cache-loss
incident notes at ~187-192 are about files INSIDE that directory getting
unlinked before a refetch; this manifest is never in the fetch path of any
other script), is an APPEND-ONLY log — one CSV line per attempt, fsync'd
immediately, never rewritten wholesale (2026-09-22 review item 5). The
loader takes the LAST recorded outcome per contract and tolerates a
truncated final line (a crash mid-append). A single-run ``fcntl.flock`` over
a sibling ``.lock`` file refuses a second concurrent ``run_fetch``.

PARTIAL FILES (review item 6)
------------------------------
A pre-existing cache file whose last row sits > 10 calendar days before an
ALREADY-EXPIRED contract's expiry, or whose first row starts after its
planned DTE window began, is real data but not full coverage. It is reported
in the dry run as ``partial`` (a column of its own, separate from
``covered``/``pending``), is NEVER overwritten, and is left alone by a real
run UNLESS ``--refetch-partial`` is given — which fetches it into a SIBLING
directory, ``backtests/option_history_cache_refetch/`` (same filenames, same
no-clobber atomic write), for an operator to decide how to merge later.

SAFETY
------
The fetch loop stops cleanly (without raising) after ``--fail-stop``
(default 10) CONSECUTIVE ambiguous failures (an exception, a non-blocking
HTTP error, or an unclassifiable ``None`` — never a confirmed ``no_bars``),
or immediately — before ``--fail-stop`` is ever reached — on a BLOCKING HTTP
status (401/403/429, sniffed from ``lib.barchart.session``'s own log
records, see item 7/8) or a ``BarchartSession`` login failure (``RuntimeError``
from ``__aenter__``). In every case the manifest already reflects every
contract attempted so far, so re-running the SAME command resumes exactly
where it stopped. ``--max-contracts`` caps how many PENDING (not yet
covered/partial) contracts one invocation fetches — already-covered or
partial contracts never count against it, and a dry run reports how many of
the total pending set that cap would leave for a later run. Run
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
import contextlib
import csv
import fcntl
import logging
import math
import os
import sys
import uuid
from collections import Counter, namedtuple
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
                   "rows", "first_date", "last_date", "attempts",
                   "first_attempt_at", "timestamp")

# review item 3 (2026-09-26 re-review): `unavailable` requires BOTH at least
# this many recorded attempts AND at least this much wall-clock time between
# the first and the most recent one — two runs during one short outage must
# never permanently blacklist a contract.
UNAVAILABLE_MIN_ATTEMPTS = 3
UNAVAILABLE_MIN_SPAN = timedelta(hours=24)

# review item 2: a strike within this fraction of ANY close in its expiry's
# DTE window is near-the-money and, on a liquid underlying, always listed —
# a confirmed-empty or near-empty response for one is more likely a stale
# session/listing lag than a genuinely unlisted strike, so it must never be
# recorded `no_bars` (permanently skip-worthy); it is `failed` instead.
NEAR_MONEY_BAND = 0.03

# Manifest outcomes that make a contract terminal PURELY off the manifest
# (i.e. when the cache file itself is absent). "fetched"/"exists" are NOT
# here — item 4 of the 2026-09-22 review: terminality for those comes from
# the file actually being present and complete, not from the manifest row,
# so a `fetched` row whose file later went missing is pending again.
_TERMINAL_OUTCOMES = frozenset({"no_bars", "unavailable"})

# HTTP statuses that mean "stop the whole run now," not "this one contract
# failed" (2026-09-22 review item 8) — sniffed from lib.barchart.session's
# log records (see _HistorySniffHandler); never raised as exceptions by that
# module, so this can't be caught via a try/except on fetch_history_fast.
_BLOCKING_HTTP_STATUSES = frozenset({401, 403, 429})

TYPE_NAME = {"C": "Call", "P": "Put"}

_DEFAULT_COOKIES = str(ROOT / "cookies" / "barchart_session.json")

# A rough, documented assumption for the dry-run duration estimate: the
# default --sleep (0.4s) plus an observed round trip for fetch_history_fast's
# re-issued feed request (no full page navigation) in the 2026-09-22 probe.
# Not a promise — a real run may be faster (session warm) or slower (retries).
SECONDS_PER_CONTRACT = 2.0

AGENT_TRADING_HISTORY_DIR = Path.home() / "claude_playground" / "agent-trading" / "data" / "history"

# Sibling of HISTORY_CACHE, never the same directory — review item 6.
REFETCH_CACHE_DIR = ROOT / "backtests" / "option_history_cache_refetch"

# A planned contract plus the quote-date window its expiry needs closes for
# (review item 6's "first row is after the start of the planned DTE window"
# check needs this; review item 3's "exclude expiries >= today" needs
# `expiration`; review item 2's near-the-money guard needs `near_money`).
# `contract_of()` strips it back to the bare 4-field identity every
# cache/manifest/fetch function keys on. `near_money` defaults False so
# existing 5-positional-arg construction (tests, mainly) keeps working.
PlanEntry = namedtuple("PlanEntry", "symbol expiration strike right window_start near_money",
                       defaults=(False,))


def contract_of(entry: "PlanEntry") -> tuple:
    return (entry.symbol, entry.expiration, entry.strike, entry.right)


class UnderlyingDataUnavailable(RuntimeError):
    """No readable close history for a symbol (review item 9 — the yfinance
    fallback that used to paper over this was removed; a missing/empty desk
    CSV is now a loud failure, not a silently narrower plan)."""


class RunLockHeld(RuntimeError):
    """Another run_fetch already holds the manifest's single-run lock
    (review item 5)."""


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
    holiday), with two corrections found by the 2026-09-22 independent
    review:

      - Juneteenth was only signed into federal law on 2021-06-17, but the
        NYSE did not add it to ITS holiday calendar until 2022 — the federal
        calendar's Friday-shifted 2021-06-18 observance was an ORDINARY
        NYSE trading day. The rule is applied only from 2022 onward here.
      - The federal "nearest workday" rule shifts New Year's Day back to
        the preceding Friday when Jan 1 falls on a Saturday (e.g.
        2021-12-31 for 2022's Jan 1). NYSE's own written rule explicitly
        does NOT do this for New Year's specifically — unlike Christmas and
        Independence Day, which DO shift Saturday->Friday — precisely so
        the exchange never closes on the last trading day of the year. Any
        Dec-31 date the federal rule produces (the only way one can appear
        here) is stripped.

    This still does not model one-off closures (9/11, hurricane closures, a
    funeral) since those aren't derivable from a rule — only the Friday
    expiries this script's plan touches are ever checked against it, and a
    misclassified one-off would at most shift one expiry by a day.
    """
    import pandas as pd
    from pandas.tseries.holiday import AbstractHolidayCalendar, GoodFriday, USFederalHolidayCalendar

    non_juneteenth = [r for r in USFederalHolidayCalendar.rules
                      if r.name not in ("Columbus Day", "Veterans Day",
                                       "Juneteenth National Independence Day")]
    juneteenth_rule = next(r for r in USFederalHolidayCalendar.rules
                           if r.name == "Juneteenth National Independence Day")

    class _NYSEHolidayCalendar(AbstractHolidayCalendar):
        rules = non_juneteenth + [GoodFriday]

    idx = _NYSEHolidayCalendar().holidays(start=str(lo), end=str(hi))
    out = {d.date() if hasattr(d, "date") else d for d in idx}

    june_start = max(lo, date(2022, 1, 1))
    if june_start <= hi:
        june = juneteenth_rule.dates(pd.Timestamp(june_start), pd.Timestamp(hi))
        out |= {d.date() if hasattr(d, "date") else d for d in june}

    out = {d for d in out if not (d.month == 12 and d.day == 31)}
    return out


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
        log.warning("%s: agent-trading history unreadable (%s)", symbol, e)
        return None


def closes_in_window(symbol: str, lo: date, hi: date, *, cache: dict,
                     close_provider=None) -> list[float]:
    """Daily closes for ``symbol`` within ``[lo, hi]`` inclusive.

    ``close_provider(symbol) -> Series | None`` is injectable (tests pass a
    synthetic one); it defaults to agent-trading's CSV — the ONLY source
    (review item 9: no network fallback). Raises ``UnderlyingDataUnavailable``
    if the symbol has no usable series at all; returns an empty list (not an
    error) when the series exists but this particular window has no rows in
    it — a normal, expected case for a window outside the CSV's covered span.
    """
    if symbol not in cache:
        provider = close_provider or _read_agent_trading_closes
        series = provider(symbol)
        if series is None or len(series) == 0:
            raise UnderlyingDataUnavailable(
                f"{symbol}: no readable close history (checked "
                f"{AGENT_TRADING_HISTORY_DIR / (symbol + '.csv')}) — the yfinance "
                "fallback was removed 2026-09-22 (review item 9); a dry run must "
                "never touch the network, so a missing/empty desk CSV is a loud "
                "failure now, not a silently narrower plan")
        cache[symbol] = series
    series = cache[symbol]
    window = series[(series.index >= lo) & (series.index <= hi)]
    return [float(v) for v in window.values]


# ─── Contract identity / cache path (mirrors fetch_counterpart_history.py) ────

def contract_path(symbol: str, expiration: date, strike: float, right: str, *,
                  cache_dir: Path | None = None) -> Path:
    return cache_path(cache_dir if cache_dir is not None else HISTORY_CACHE,
                      symbol, expiration, strike, TYPE_NAME[right])


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
                    close_cache: dict, close_provider=None,
                    today: date | None = None,
                    include_open_expiries: bool = False) -> list[PlanEntry]:
    """Every ``PlanEntry`` this symbol's plan wants, sorted. Expiries with no
    underlying-close coverage in their quote window contribute nothing
    (never invent a strike band from no data). Expiries on/after `today` are
    excluded unless `include_open_expiries` (review item 3)."""
    today = today or date.today()
    entries: set[PlanEntry] = set()
    expiries = candidate_expiries(from_date + timedelta(days=dte_min),
                                  to_date + timedelta(days=dte_max))
    if not include_open_expiries:
        expiries = [e for e in expiries if e < today]
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
            near = any(abs(strike - c) <= NEAR_MONEY_BAND * c for c in closes)
            for right in rights:
                entries.add(PlanEntry(symbol, expiry, strike, right, window[0], near))
    return sorted(entries, key=lambda e: (e.symbol, e.expiration, e.strike, e.right))


def build_plan(symbols: list[str], from_date: date, to_date: date, dte_min: int,
              dte_max: int, band: float, rights: list[str], *,
              close_provider=None, today: date | None = None,
              include_open_expiries: bool = False) -> dict[str, list[PlanEntry]]:
    """``{symbol: [PlanEntry...]}`` — the full universe, before any
    covered/partial/--max-contracts filtering."""
    close_cache: dict = {}
    return {
        symbol: plan_for_symbol(symbol, from_date, to_date, dte_min, dte_max, band,
                                rights, close_cache=close_cache, close_provider=close_provider,
                                today=today, include_open_expiries=include_open_expiries)
        for symbol in symbols
    }


# ─── Manifest I/O (append-only — review item 5) ────────────────────────────────

def load_manifest(path: Path) -> dict[tuple, dict]:
    """Reads the append-only manifest, keeping the LAST recorded row per
    contract (rows later in the file win — this is how "last outcome wins"
    is expressed without rewriting the file). Tolerates a truncated final
    line (a crash mid-append): a row missing a required identity field is
    silently skipped rather than raised."""
    if not path.exists():
        return {}
    out = {}
    with open(path) as fh:
        for row in csv.DictReader(fh):
            symbol = row.get("symbol")
            expiration = row.get("expiration")
            strike = row.get("strike")
            right = row.get("right")
            if not (symbol and expiration and strike and right):
                continue  # truncated/corrupt row — the prior good state stands
            k = (symbol, expiration, strike, right)
            out[k] = {f: (row.get(f) or "") for f in MANIFEST_FIELDS}
    return out


def append_manifest_row(path: Path, row: dict) -> None:
    """Appends one attempt as a single fsync'd CSV line — never rewrites the
    file (review item 5). Writes the header once, the first time the file is
    created (or the file exists but is empty). If the file exists, is
    non-empty, and does NOT end in a newline (a crash mid-append left a
    truncated final line — see ``load_manifest``'s tolerance for that), a
    newline is written first so the new row never gets concatenated onto the
    garbled fragment (re-review item 5, 2026-09-26)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = True
    if path.exists() and path.stat().st_size > 0:
        needs_header = False
        with open(path, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            last_byte = fh.read(1)
        if last_byte != b"\n":
            with open(path, "a", newline="") as fh:
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        if needs_header:
            w.writeheader()
        w.writerow({f: row.get(f, "") for f in MANIFEST_FIELDS})
        fh.flush()
        os.fsync(fh.fileno())


@contextlib.contextmanager
def _run_lock(manifest_path: Path):
    """A single-run advisory lock over manifest writes (review item 5).
    `flock` is process-scoped and released automatically if the process
    dies, so a crashed run never leaves a stale lock behind."""
    lock_path = manifest_path.with_name(manifest_path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        fh.close()
        raise RunLockHeld(
            f"another backfill_chain run already holds the lock at {lock_path} — "
            "refusing to start a second one concurrently") from e
    try:
        yield
    finally:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ─── Completeness / classification (review items 3, 4, 6) ─────────────────────

def file_completeness(path: Path, expiration: date, window_start: date, *,
                      today: date | None = None) -> str:
    """``"absent" | "complete" | "partial"`` (review item 6). A partial file
    is real data — NEVER overwritten by this script — but must not read as
    full coverage: a shallow file that stops well short of an
    already-expired contract's last trading day, or that starts after the
    DTE window it was meant to cover, silently reads downstream as "priced"
    when it isn't. An unreadable or near-empty (< MIN_USABLE_BARS) file is
    also reported partial rather than absent/complete — conservative: never
    claim covered, never treat as safe to blindly overwrite either."""
    if not path.exists():
        return "absent"
    try:
        details = parse_history_details(path.read_text(), require_mark=False)
    except Exception:
        return "partial"
    if len(details) < MIN_USABLE_BARS:
        return "partial"
    days = sorted(details)
    today = today or date.today()
    if expiration < today and (expiration - days[-1]).days > 10:
        return "partial"
    if days[0] > window_start:
        return "partial"
    return "complete"


def classify(entry: PlanEntry, manifest: dict[tuple, dict], *,
            today: date | None = None, retry_unavailable: bool = False) -> str:
    """``"covered" | "partial" | "pending"`` for one planned contract
    (review items 3, 4, 6). "covered" is the only status a real run treats
    as done; "partial" is real data on disk, never overwritten and never
    re-requested except via ``--refetch-partial``. ``retry_unavailable``
    (review item 3) makes an ``unavailable`` manifest row NOT terminal — an
    operator-requested re-check, unlike ``no_bars`` which is always terminal
    (a real confirmed answer, not a give-up)."""
    today = today or date.today()
    contract = contract_of(entry)
    status = file_completeness(contract_path(*contract), entry.expiration,
                               entry.window_start, today=today)
    if status == "complete":
        return "covered"
    if status == "partial":
        return "partial"
    # status == "absent": an unexpired contract's chain can still change, so
    # neither a no_bars nor an unavailable manifest row may terminate it
    # (review item 3) — it stays pending until it expires.
    if entry.expiration >= today:
        return "pending"
    row = manifest.get(_key(*contract))
    outcome = row.get("outcome") if row else None
    if outcome in _TERMINAL_OUTCOMES:
        if outcome == "unavailable" and retry_unavailable:
            return "pending"
        return "covered"
    return "pending"


def categorize(entries: list[PlanEntry], manifest: dict[tuple, dict], *,
              today: date | None = None, retry_unavailable: bool = False) -> tuple[list, list, list]:
    """``(covered, partial, pending)`` — the three-way split (review items 4, 6)."""
    covered, partial, pending = [], [], []
    buckets = {"covered": covered, "partial": partial, "pending": pending}
    for e in entries:
        buckets[classify(e, manifest, today=today, retry_unavailable=retry_unavailable)].append(e)
    return covered, partial, pending


# ─── Atomic, no-clobber cache write (review item 1) ────────────────────────────

def _atomic_write_new(path: Path, text: str) -> bool:
    """Writes ``text`` to ``path`` iff it doesn't already exist — atomically,
    and without ever truncating a file that appeared there since planning
    ran (review item 1). A unique tmp file is written and fsync'd first (so
    a crash mid-write never leaves a corrupt tmp mistaken for real data),
    then hard-linked onto ``path``: ``os.link`` is atomic and raises
    ``FileExistsError`` if the target already exists, so two processes
    racing on the same contract can never have one clobber the other.
    Returns True if this call created the file, False if it already existed
    (nothing lost either way — the existing file is untouched)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        with open(tmp, "w") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(tmp, path)
            return True
        except FileExistsError:
            return False
    finally:
        tmp.unlink(missing_ok=True)


# ─── HTTP-status / clean-empty sniffing (review items 7, 8) ───────────────────
#
# lib.barchart.session.BarchartSession.fetch_history_fast collapses an HTTP
# error, a clean 200-with-zero-rows response, and an internal exception all
# into the same bare `None` return — none of it is modified here (it isn't
# ours to touch), but its own WARNING/ERROR log calls DO distinguish these
# cases, so a Handler attached only for the duration of one fetch recovers
# that information without changing session.py's code or behaviour at all.

_SESSION_LOGGER_NAME = "lib.barchart.session"


class _HistorySignal:
    __slots__ = ("kind", "http_status")

    def __init__(self):
        self.kind: str | None = None   # None | "http_error" | "empty" | "exception"
        self.http_status: int | None = None


class _HistorySniffHandler(logging.Handler):
    """Watches ``lib.barchart.session``'s known WARNING/ERROR message shapes
    for the duration of one fetch.

    NOT last-message-wins (fixed 2026-09-26 re-review, item 1): an HTTP
    error (especially a blocking one) MUST decide the outcome even if the
    fast re-issue path then falls back to a full navigation
    (``fetch_history_csv``) that itself logs "no rows" — e.g. a 429 on the
    re-issue, followed by a clean-looking empty response on the fallback
    navigation, is a rate-limited/stale session, not a confirmed absence.
    ``kind`` therefore only ever moves UP the priority order
    ``empty < exception < http_error`` within one fetch; an ``http_error``
    is sticky against a later ``empty``/``exception``, and among multiple
    ``http_error`` records the LAST status code wins (the most recent
    attempt's own code)."""
    _HTTP_MSGS = ("History feed returned HTTP %d for '%s'",
                 "Re-issued feed HTTP %d for '%s' — re-navigating")
    _EMPTY_MSGS = ("History feed returned no rows for '%s'",
                  "Re-issued feed returned no rows for '%s' — re-navigating")
    _KIND_PRIORITY = {"empty": 0, "exception": 1, "http_error": 2}

    def __init__(self, signal: _HistorySignal):
        super().__init__(level=logging.WARNING)
        self._signal = signal

    def emit(self, record: logging.LogRecord) -> None:
        if record.msg in self._HTTP_MSGS and record.args:
            new_kind, new_status = "http_error", record.args[0]
        elif record.msg in self._EMPTY_MSGS:
            new_kind, new_status = "empty", None
        elif record.levelno >= logging.ERROR:
            new_kind, new_status = "exception", None
        else:
            return

        current = self._signal.kind
        if current is None or self._KIND_PRIORITY[new_kind] >= self._KIND_PRIORITY[current]:
            self._signal.kind = new_kind
            if new_kind == "http_error":
                self._signal.http_status = new_status


async def _fetch_one(session, contract: tuple, timeout_ms: int) -> tuple[str | None, _HistorySignal]:
    symbol, expiration, strike, right = contract
    signal = _HistorySignal()
    sniffer_logger = logging.getLogger(_SESSION_LOGGER_NAME)
    handler = _HistorySniffHandler(signal)
    sniffer_logger.addHandler(handler)
    try:
        csv_text = await session.fetch_history_fast(
            option_history_url(symbol, expiration, strike, TYPE_NAME[right]), timeout_ms)
    except Exception as e:
        signal.kind = "exception"
        log.error("history scrape failed for %s: %s",
                  contract_path(symbol, expiration, strike, right).stem, safe_err(e))
        csv_text = None
    finally:
        sniffer_logger.removeHandler(handler)
    return csv_text, signal


# ─── Fetch ────────────────────────────────────────────────────────────────────

def _ambiguous_outcome(prior_attempts: int, prior_first_attempt_at: str, now_iso: str,
                       fallback_outcome: str) -> tuple[str, int, str]:
    """``(outcome, new_attempts, first_attempt_at)`` for an ambiguous failure
    (review item 3, re-reviewed 2026-09-26): promotion to ``unavailable``
    (terminal) requires BOTH ``UNAVAILABLE_MIN_ATTEMPTS`` recorded attempts
    AND at least ``UNAVAILABLE_MIN_SPAN`` between the FIRST attempt and this
    one — so two runs during one short outage can never permanently
    blacklist a contract. ``first_attempt_at`` is set once (on the first
    attempt) and carried forward unchanged after that."""
    new_attempts = prior_attempts + 1
    first_attempt_at = prior_first_attempt_at or now_iso
    span_ok = False
    try:
        span_ok = (datetime.fromisoformat(now_iso) - datetime.fromisoformat(first_attempt_at)
                  ) >= UNAVAILABLE_MIN_SPAN
    except ValueError:
        span_ok = False
    outcome = ("unavailable" if new_attempts >= UNAVAILABLE_MIN_ATTEMPTS and span_ok
              else fallback_outcome)
    return outcome, new_attempts, first_attempt_at


async def run_fetch(pending: list[tuple], manifest: dict[tuple, dict], manifest_path: Path, *,
                    fail_stop: int = 10, no_bars_stop: int = 25, headless: bool = True,
                    timeout_ms: int = 30000, sleep_s: float = 0.4, session=None,
                    cache_dir: Path | None = None,
                    near_money: dict[tuple, bool] | None = None) -> dict:
    """Fetches every pending ``(symbol, expiration, strike, right)`` contract,
    writing its CSV to the cache (atomically, NEVER overwriting — review
    item 1) and appending one manifest row IMMEDIATELY after each attempt
    (review item 5), so a crash or a clean stop loses at most the in-flight
    contract and a re-run resumes exactly where this one stopped.

    Stops cleanly (does not raise) after ``fail_stop`` CONSECUTIVE ambiguous
    failures, or after ``no_bars_stop`` CONSECUTIVE confirmed-empty results
    (review item 2 — a near-the-money strike, per ``near_money``, is never
    confirmed-empty in the first place; see below). Stops IMMEDIATELY,
    before either counter is ever reached, on: a blocking HTTP status
    (401/403/429, sniffed via ``_HistorySniffHandler`` — review item 8); an
    ``OSError`` writing the cache file (disk full, read-only fs, ... — an
    environment problem, not a per-contract one; re-review item 3); or a
    session login failure (``RuntimeError`` from ``BarchartSession.__aenter__``,
    caught here when this function owns session construction). NEITHER a
    blocking-HTTP stop NOR a write-OSError stop counts as an "attempt" for
    that contract (its manifest ``attempts`` is left unchanged) — re-review
    item 3.

    A contract that never listed (a confirmed clean-empty feed OR a parsed
    response with too few bars) is recorded ``no_bars`` and does NOT count
    as an ambiguous failure — UNLESS ``near_money`` says this strike sat
    within ``NEAR_MONEY_BAND`` of a close during its DTE window, in which
    case a liquid underlying should always have listed it, so the miss is
    recorded ``failed`` (an ambiguous failure) instead (review item 2). An
    ambiguous failure (exception / non-blocking HTTP error / unclassifiable
    / a too-near-the-money "empty") is recorded ``failed``/``unparsed`` until
    BOTH ``UNAVAILABLE_MIN_ATTEMPTS`` attempts have accumulated ACROSS
    SEPARATE RUNS and ``UNAVAILABLE_MIN_SPAN`` has elapsed since the first
    one, then ``unavailable`` (terminal, unless a later run passes
    ``--retry-unavailable`` at the planning stage) — review item 3.

    Raises ``RunLockHeld`` immediately, before touching anything, if another
    run already holds the manifest's lock (review item 5).
    """
    resolved_cache_dir = cache_dir if cache_dir is not None else HISTORY_CACHE
    resolved_cache_dir.mkdir(parents=True, exist_ok=True)
    near_money = near_money or {}
    stats = Counter()

    async def run(sess) -> None:
        consecutive_failures = 0
        consecutive_no_bars = 0
        for i, contract in enumerate(pending, 1):
            symbol, expiration, strike, right = contract
            path = contract_path(symbol, expiration, strike, right, cache_dir=resolved_cache_dir)
            name = path.stem
            k = _key(symbol, expiration, strike, right)
            prior = manifest.get(k, {})
            prior_attempts = int((prior.get("attempts") or "0") or "0")
            prior_first_attempt_at = prior.get("first_attempt_at") or ""
            now_iso = _now_iso()
            row = {"symbol": symbol, "expiration": expiration.isoformat(),
                  "strike": f"{strike:.2f}", "right": right, "timestamp": now_iso}

            def _record_ambiguous(fallback_outcome: str) -> str:
                outcome, new_attempts, first_at = _ambiguous_outcome(
                    prior_attempts, prior_first_attempt_at, now_iso, fallback_outcome)
                row.update(outcome=outcome, rows="0", first_date="", last_date="",
                          attempts=str(new_attempts), first_attempt_at=first_at)
                return outcome

            csv_text, signal = await _fetch_one(sess, contract, timeout_ms)
            is_near_money = near_money.get(contract, False)

            if not csv_text:
                if signal.kind == "http_error" and signal.http_status in _BLOCKING_HTTP_STATUSES:
                    # Not this contract's fault — the SESSION is blocked.
                    # attempts/first_attempt_at are left exactly as they
                    # were (re-review item 3).
                    row.update(outcome="failed", rows="0", first_date="", last_date="",
                              attempts=str(prior_attempts), first_attempt_at=prior_first_attempt_at)
                    manifest[k] = row
                    append_manifest_row(manifest_path, row)
                    remaining = len(pending) - i
                    log.error(
                        "stopping immediately — HTTP %d fetching %s (%d/%d); "
                        "%d contract(s) remain; the manifest at %s reflects every "
                        "attempt up to here, so re-running the same command "
                        "resumes from here", signal.http_status, name, i, len(pending),
                        remaining, manifest_path)
                    stats[f"stopped_http_{signal.http_status}"] = 1
                    return
                if signal.kind == "empty" and not is_near_money:
                    row.update(outcome="no_bars", rows="0", first_date="", last_date="",
                              attempts="0", first_attempt_at="")
                    stats["no_bars"] += 1
                    consecutive_failures = 0
                    consecutive_no_bars += 1
                    log.info("[%d/%d] %s: no bars (confirmed empty feed) — not written",
                             i, len(pending), name)
                else:
                    outcome = _record_ambiguous("failed")
                    stats[outcome] += 1
                    consecutive_failures += 1
                    consecutive_no_bars = 0
                    near_note = " (near-the-money — a liquid underlying should list this)" \
                        if is_near_money and signal.kind != "http_error" else ""
                    log.warning("[%d/%d] %s: no data (%s)%s%s", i, len(pending), name,
                               signal.kind or "unclassified", near_note,
                               " — marked unavailable" if outcome == "unavailable" else "")
            else:
                try:
                    details = parse_history_details(csv_text, require_mark=False)
                except Exception as e:
                    outcome = _record_ambiguous("unparsed")
                    stats[outcome] += 1
                    consecutive_failures += 1
                    consecutive_no_bars = 0
                    log.warning("[%d/%d] %s: unparseable (%s)", i, len(pending), name, safe_err(e))
                else:
                    if len(details) < MIN_USABLE_BARS and not is_near_money:
                        row.update(outcome="no_bars", rows=str(len(details)),
                                  first_date="", last_date="", attempts="0", first_attempt_at="")
                        stats["no_bars"] += 1
                        consecutive_failures = 0
                        consecutive_no_bars += 1
                        log.info("[%d/%d] %s: no bars — not written", i, len(pending), name)
                    elif len(details) < MIN_USABLE_BARS:
                        outcome = _record_ambiguous("failed")
                        stats[outcome] += 1
                        consecutive_failures += 1
                        consecutive_no_bars = 0
                        log.warning("[%d/%d] %s: too few bars near-the-money — treating as a "
                                   "failure, not no_bars", i, len(pending), name)
                    else:
                        days = sorted(details)
                        try:
                            created = _atomic_write_new(path, csv_text)
                        except OSError as e:
                            # An environment problem (disk full, read-only
                            # fs, ...), not a per-contract one: stop the
                            # whole run rather than burn through fail_stop,
                            # and don't count it as an attempt (re-review
                            # item 3).
                            row.update(outcome="failed", rows="0", first_date="", last_date="",
                                      attempts=str(prior_attempts),
                                      first_attempt_at=prior_first_attempt_at)
                            manifest[k] = row
                            append_manifest_row(manifest_path, row)
                            remaining = len(pending) - i
                            log.error(
                                "stopping immediately — cache write failed for %s (%s); "
                                "%d contract(s) remain; the manifest at %s reflects every "
                                "attempt up to here, so re-running the same command "
                                "resumes from here", name, safe_err(e), remaining, manifest_path)
                            stats["stopped_write_error"] = 1
                            return
                        else:
                            outcome = "fetched" if created else "exists"
                            row.update(outcome=outcome, rows=str(len(details)),
                                      first_date=days[0].isoformat(),
                                      last_date=days[-1].isoformat(), attempts="0",
                                      first_attempt_at="")
                            stats[outcome] += 1
                            consecutive_failures = 0
                            consecutive_no_bars = 0
                            log.info("[%d/%d] %s: %s, %d bars %s..%s", i, len(pending), name,
                                    outcome, len(details), days[0], days[-1])

            manifest[k] = row
            append_manifest_row(manifest_path, row)

            if consecutive_failures >= fail_stop:
                remaining = len(pending) - i
                log.warning(
                    "stopping after %d consecutive failures — %d contract(s) remain; "
                    "the manifest at %s already reflects every attempt so far, so "
                    "re-running the same command resumes from here",
                    fail_stop, remaining, manifest_path)
                stats["stopped_consecutive_failures"] = 1
                return

            if consecutive_no_bars >= no_bars_stop:
                remaining = len(pending) - i
                log.warning(
                    "stopping after %d consecutive no_bars — %d contract(s) remain; "
                    "the manifest at %s already reflects every attempt so far, so "
                    "re-running the same command resumes from here",
                    no_bars_stop, remaining, manifest_path)
                stats["stopped_consecutive_no_bars"] = 1
                return

            if sleep_s:
                await asyncio.sleep(sleep_s)

    with _run_lock(manifest_path):
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

def print_dry_run(plan: dict[str, list[PlanEntry]], manifest: dict[tuple, dict], *,
                  max_contracts: int | None, sleep_s: float,
                  today: date | None = None, retry_unavailable: bool = False) -> dict:
    """Per-symbol plan report: universe / covered / partial / pending, and an
    estimated duration for the pending set. Returns the per-symbol stats
    dict (also useful to callers/tests, not just printed)."""
    report: dict[str, dict] = {}
    total_pending = 0
    for symbol, entries in plan.items():
        covered, partial, pending = categorize(entries, manifest, today=today,
                                                retry_unavailable=retry_unavailable)
        report[symbol] = {"universe": len(entries), "covered": len(covered),
                          "partial": len(partial), "pending": len(pending)}
        total_pending += len(pending)
        log.info("%-6s  universe=%-6d  covered=%-6d  partial=%-5d  pending=%-6d",
                 symbol, len(entries), len(covered), len(partial), len(pending))

    if max_contracts is not None and total_pending > max_contracts:
        log.info("--max-contracts %d caps the PENDING set a real run would fetch this "
                 "invocation to the first %d of %d (deterministic order: symbol, "
                 "expiry, strike, right) — covered/partial contracts never count "
                 "against it", max_contracts, max_contracts, total_pending)
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
                        help="Cap on PENDING contracts (not yet covered/partial) a "
                             "real run fetches this invocation.")
    parser.add_argument("--sleep", type=float, default=0.4, help="Seconds between fetches.")
    parser.add_argument("--fail-stop", type=int, default=10,
                        help="Stop after this many consecutive ambiguous failures.")
    parser.add_argument("--no-bars-stop", type=int, default=25,
                        help="Stop after this many consecutive confirmed-empty "
                             "(no_bars) results.")
    parser.add_argument("--include-open-expiries", action="store_true",
                        help="Include expiries on/after today (excluded by default — "
                             "review item 3, their chain can still change).")
    parser.add_argument("--refetch-partial", action="store_true",
                        help="Also fetch PARTIAL contracts, into the sibling "
                             "backtests/option_history_cache_refetch/ dir (never the "
                             "primary cache) — review item 6.")
    parser.add_argument("--retry-unavailable", action="store_true",
                        help="Treat a manifest `unavailable` row as pending again, "
                             "not terminal (an operator-requested re-check).")
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
                      args.band, rights, include_open_expiries=args.include_open_expiries)
    manifest = load_manifest(MANIFEST_PATH)

    log.info("plan: %s .. %s  dte=[%d,%d]  band=%.2f  rights=%s",
             args.from_date, args.to_date, args.dte_min, args.dte_max, args.band, rights)

    if not args.execute:
        print_dry_run(plan, manifest, max_contracts=args.max_contracts, sleep_s=args.sleep,
                      retry_unavailable=args.retry_unavailable)
        return

    all_pending: list[tuple] = []
    all_partial: list[tuple] = []
    near_money_map: dict[tuple, bool] = {}
    for symbol in symbols:
        _covered, partial, pending = categorize(plan[symbol], manifest,
                                                 retry_unavailable=args.retry_unavailable)
        for e in pending:
            c = contract_of(e)
            all_pending.append(c)
            near_money_map[c] = e.near_money
        for e in partial:
            c = contract_of(e)
            all_partial.append(c)
            near_money_map[c] = e.near_money
    all_pending.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
    all_partial.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
    if args.max_contracts is not None:
        all_pending = all_pending[:args.max_contracts]

    if not all_pending and not (args.refetch_partial and all_partial):
        log.info("Nothing to fetch — every planned contract is covered, partial, "
                 "or already attempted.")
        return

    if all_pending:
        log.info("fetching %d contract(s)", len(all_pending))
        stats = asyncio.run(run_fetch(all_pending, manifest, MANIFEST_PATH,
                                      fail_stop=args.fail_stop, no_bars_stop=args.no_bars_stop,
                                      headless=not args.no_headless, sleep_s=args.sleep,
                                      near_money=near_money_map))
        log.info("done: %s", "  ".join(f"{k}={v}" for k, v in sorted(stats.items())))

    if args.refetch_partial and all_partial:
        log.info("--refetch-partial: re-fetching %d partial contract(s) into %s "
                 "(never touching the primary cache)", len(all_partial), REFETCH_CACHE_DIR)
        stats2 = asyncio.run(run_fetch(all_partial, manifest, MANIFEST_PATH,
                                       fail_stop=args.fail_stop, no_bars_stop=args.no_bars_stop,
                                       headless=not args.no_headless, sleep_s=args.sleep,
                                       cache_dir=REFETCH_CACHE_DIR, near_money=near_money_map))
        log.info("refetch-partial done: %s", "  ".join(f"{k}={v}" for k, v in sorted(stats2.items())))

    if all_pending:
        log.info("remember to run `python3 scripts/backup_research_caches.py push` by "
                 "hand now that the cache has grown")


if __name__ == "__main__":
    main()
