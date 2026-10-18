"""
Planner + resumable fetcher for the option legs the `earnings_vol` study needs
(research/pre-registrations/f3_structure/earnings_vol.md, "The fetch").

WHY A NEW FILE
--------------
The existing collectors derive their targets from the BOOK (`load_book`) and
only reuse `fetch_sweep_legs`' manifest and scrape loop. This study's targets
come from an earnings calendar, so the target builder is new; the loop,
manifest and cache convention are IMPORTED from `fetch_sweep_legs`, as
`fetch_far_legs` does. Own manifest: `backtests/sweep_cache/earnings_legs_manifest.csv`.

THE RULE (all of it decided from data on or before the entry day)
-----------------------------------------------------------------
* Event session E: the report date for `bmo`, the next session for `amc` and
  `dmh`. `unknown` is dropped (and counted) unless `include_unknown` (-> amc).
* Entry = session E-5, exit = session E.
* Front expiry = first listed expiry after E. Back = first listed expiry at
  least 28 calendar days after the front.
* Listed expiries: weekly Fridays, a holiday Friday moving to the prior
  session. This is an ASSUMPTION (no chain listing is stored); cached files
  only confirm it.

THE ENTRY CLOSE, ON THE OPTION CHAIN'S BASIS (`basis_factor`)
-------------------------------------------------------------
The closes (agent-trading `data/history`, `backtests/underlying_ohlc_cache`)
are SPLIT-ADJUSTED; strikes and the option files' `Price~` are not (NFLX x10
before 2025-11-17, NVDA x10 before 2024-06-10, AVGO x10 before 2024-07-15).
For each session d from the entry back 5 sessions, the day's ratio is the
median `Price~` across the ticker's cached files on d over the adjusted close
on d. A ratio within 5% of 1 votes 1; one within 5% of a split factor (2, 3,
4, 5, 10, 15, 20 or a reciprocal) votes that factor; anything else is no
vote. The factor is the most common day vote; a tie that includes 1 keeps the
close, any other tie goes to the most recent day (so the entry day leads). A
factor other than 1 must have two observations behind it (two days, or two
files on its day); otherwise the close is kept and the event counted
`basis_unconfirmed`. This guards against a bad `Price~`: one bad
file is outvoted by the median, and a whole-chain glitch day (SPY 177.54 on
2025-11-28) by its neighbours. With no vote at all, a ticker listed in
`underlying_ohlc_cache/rescaled_tickers.txt` drops as `no_unadjusted_close`;
any other ticker keeps its close (`basis_unchecked`). A factor other than 1
multiplies the close and counts the event `close_rebased`. Only rows dated on
or before the entry day enter.

THE STRIKE: A CANDIDATE LADDER, NOT AN INFERRED STEP (`strike_ladder`)
---------------------------------------------------------------------
The registration's ATM is "the listed strike nearest the underlying's close at
entry". No chain listing is stored, so the candidates are, for each increment
in {0.5, 1, 2.5, 5, 10}, its multiples nearest the close on each side, kept
within 3% of the close and ranked by |K - close| (ties lower). That is at most
10 strikes, and the listed nearest strike is always among them whenever the
listed grid near the money is one of those increments and lies within 3%: it
is a multiple of the grid's increment on one side of the close. The ladder
depends on the close alone, so the plan no longer reads the cache index (the
old inferred step did, which is why it needed a pre-fetch index).

ATM (`resolve_atm`, shared with the study): walk the ladder; the first
candidate whose front call AND put both have an entry-day row is the ATM. A
candidate is passed over when either leg is `failed` in the manifest, in
`_unlisted.jsonl`, or cached without an entry-day row. A candidate neither
confirmed nor passed over (a leg never fetched) stops the walk: the ATM is
pending, and the study drops the event `front_not_fetched` rather than skip a
strike that may be listed.

THE PASSES (`--phase`)
----------------------
1. `--phase front` (default). Per event, walk the ladder and target the call
   and put of up to `--width` (default 4) unresolved candidates, stopping at a
   confirmed one. Run it, fetch, and RE-RUN it until it targets nothing: each
   pass resolves the nearest candidates, and an event whose nearest `--width`
   all prove unlisted gets the next ones in the following pass. Width 4 covers
   a 0.5/1/2.5 grid in one pass; a 5- or 10-wide grid near the money can sit
   5th to 6th in the ladder (e.g. close 901.30: 901.50, 901, 902, 902.50, then
   900), so it may take a second pass.
2. `--phase back`. Per event whose ATM is now confirmed, target the back call
   and put at THAT strike only. Events still pending get their back legs in a
   later back pass, after a front pass resolves them.

Contracts already cached are never refetched (any file counts, with or without
the day needed). A contract recorded `failed` in the manifest stays failed
and is passed over; `--retry-failed` treats it as unfetched, so it is targeted
again only if the walk reaches it under this rule, and only those rows are
reset to pending. `--retry-unlisted` ignores `_unlisted.jsonl` likewise.

Dry run is the DEFAULT and touches neither the network nor the manifest; it
prints both phases. `--execute` fetches the chosen phase (needs
BARCHART_EMAIL/BARCHART_PASSWORD). Resumable via the manifest, `--limit N`
caps fetch attempts. Research-tier, run by hand, under `caffeinate`; run
`scripts/backup_research_caches.py push` afterwards.

Usage:
  python3 scripts/collector/study_legs/fetch_earnings_legs.py                                  # dry run
  caffeinate -i python3 scripts/collector/study_legs/fetch_earnings_legs.py --phase front --execute
  caffeinate -i python3 scripts/collector/study_legs/fetch_earnings_legs.py --phase back --execute
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402

log = logging.getLogger("fetch_earnings_legs")

MANIFEST_PATH = ROOT / "backtests" / "sweep_cache" / "earnings_legs_manifest.csv"
CATEGORY = "earnings"
AGENT_TRADING = Path.home() / "claude_playground" / "agent-trading" / "data"
EARNINGS_DIR = AGENT_TRADING / "earnings"
HISTORY_DIRS = (AGENT_TRADING / "history", ROOT / "backtests" / "underlying_ohlc_cache")
RESCALED_FILE = ROOT / "backtests" / "underlying_ohlc_cache" / "rescaled_tickers.txt"

UNIVERSE_FILE = (
    "AAPL AMD AMZN ASML AVGO COST GOOGL INTC JPM LLY META MSFT MU NFLX NVDA QCOM TSLA TSM UNH")
UNIVERSE_ADDED = "BA BAC COIN DIS PLTR UBER"
UNIVERSE = tuple(UNIVERSE_FILE.split())
ADDED = tuple(UNIVERSE_ADDED.split())

WINDOW_START = date(2024, 1, 1)
WINDOW_END = date(2026, 9, 30)
SEAL_START = date(2026, 9, 23)          # mirrors scripts/backtest_study/lib/era.py::SEAL_START
ENTRY_OFFSET = 5                        # entry = session E - 5
BACK_GAP_DAYS = 28
SECONDS_PER_CONTRACT = 2.1              # median of the repo's manifests' fetched_at gaps (1-2 s) + 0.4 s sleep

LADDER_INCREMENTS = (0.5, 1.0, 2.5, 5.0, 10.0)
LADDER_BAND = 0.03                      # candidates within 3% of the entry close
PROBE_WIDTH = 4                         # unresolved candidates targeted per event per front pass

SPLIT_FACTORS = (2, 3, 4, 5, 10, 15, 20)
PLAUSIBLE_FACTORS = tuple(sorted({1.0} | {float(f) for f in SPLIT_FACTORS}
                                 | {1.0 / f for f in SPLIT_FACTORS}))
BASIS_TOL = 0.05
BASIS_LOOKBACK = 5                      # sessions before the entry that may vote

RIGHTS = ("C", "P")

# Leg statuses, shared with the study.
OK, NOT_QUOTED, UNLISTED, FAILED, NOT_FETCHED = (
    "ok", "not_quoted", "unlisted", "failed", "not_fetched")
BAD = frozenset({NOT_QUOTED, UNLISTED, FAILED})


# ─── Sessions and expiries ─────────────────────────────────────────────────────

def _is_weekday(d: date) -> bool:
    return d.weekday() < 5


def is_session(d: date, sessions: set[date], last: date | None) -> bool:
    """A session if the calendar says so; past the calendar's end, any weekday."""
    if last is not None and d > last:
        return _is_weekday(d)
    return d in sessions if sessions else _is_weekday(d)


def session_index(sessions: list[date]) -> dict[date, int]:
    return {d: i for i, d in enumerate(sessions)}


def event_session(ann_date: date, session: str, sessions: list[date]) -> date | None:
    """The first session whose open reflects the report. None: unreadable."""
    if session not in ("bmo", "amc", "dmh"):
        return None
    if ann_date not in session_index(sessions):
        return None
    if session == "bmo":
        return ann_date
    after = [d for d in sessions if d > ann_date]
    return after[0] if after else None


def entry_session(e: date, sessions: list[date], offset: int = ENTRY_OFFSET) -> date | None:
    idx = session_index(sessions).get(e)
    if idx is None or idx - offset < 0:
        return None
    return sessions[idx - offset]


def weekly_fridays(start: date, end: date, sessions: set[date] | None = None,
                   last: date | None = None) -> list[date]:
    """Friday expiries in [start, end]; a Friday that is not a session moves to
    the prior session (holiday Thursday)."""
    sess = sessions or set()
    out = []
    d = start + timedelta(days=(4 - start.weekday()) % 7)
    while d <= end:
        x = d
        while not is_session(x, sess, last):
            x -= timedelta(days=1)
        out.append(x)
        d += timedelta(days=7)
    return out


def pick_expiries(e: date, listed: Iterable[date],
                  gap_days: int = BACK_GAP_DAYS) -> tuple[date, date] | None:
    """(front, back): first listed expiry after E; first at least `gap_days`
    calendar days after the front."""
    ex = sorted(set(listed))
    front = next((x for x in ex if x > e), None)
    if front is None:
        return None
    back = next((x for x in ex if x >= front + timedelta(days=gap_days)), None)
    return (front, back) if back else None


# ─── The close basis ───────────────────────────────────────────────────────────

def nearest_factor(ratio: float) -> float | None:
    """The plausible factor (1, a split factor or its reciprocal) within
    `BASIS_TOL` of `ratio`; None when there is none (a bad print)."""
    if not ratio or ratio <= 0 or not math.isfinite(ratio):
        return None
    f = min(PLAUSIBLE_FACTORS, key=lambda x: abs(math.log(ratio / x)))
    return f if abs(ratio / f - 1) <= BASIS_TOL else None


@dataclass
class Basis:
    factor: float | None        # None: no vote at all
    votes: int = 0              # observations behind `factor`
    status: str = ""            # "" | basis_unconfirmed | basis_unchecked


def basis_factor(entry: date, sessions: list[date], closes: dict[date, float],
                 prices: dict[date, list[float]]) -> Basis:
    """The factor that puts the adjusted close on the option chain's basis,
    from `Price~` rows dated on or before `entry` only (see module doc)."""
    i = session_index(sessions).get(entry)
    if i is None:
        return Basis(None, 0, "basis_unchecked")
    window = sessions[max(0, i - BASIS_LOOKBACK): i + 1][::-1]     # entry first
    day_votes: list[tuple[float, int]] = []                          # (factor, files agreeing)
    for d in window:
        adj, ps = closes.get(d), [p for p in prices.get(d, ()) if p and p > 0]
        if not adj or adj <= 0 or not ps:
            continue
        f = nearest_factor(statistics.median(ps) / adj)
        if f is None:
            continue
        day_votes.append((f, sum(1 for p in ps if nearest_factor(p / adj) == f)))
    if not day_votes:
        return Basis(None, 0, "basis_unchecked")
    cnt = Counter(f for f, _ in day_votes)
    top = max(cnt.values())
    tied = [x for x, _ in day_votes if cnt[x] == top]
    f = 1.0 if 1.0 in tied else tied[0]                  # ties: no rebase, else the most recent day
    if f == 1.0:
        return Basis(1.0, top)
    support = top if top >= 2 else next(n for x, n in day_votes if x == f)
    if support < 2:
        return Basis(1.0, support, "basis_unconfirmed")
    return Basis(f, support)


# ─── Strikes ───────────────────────────────────────────────────────────────────

def strike_ladder(close: float, increments: Iterable[float] = LADDER_INCREMENTS,
                  band: float = LADDER_BAND) -> tuple[float, ...]:
    """Candidate strikes: each increment's multiples nearest the close on each
    side, within `band` of the close, ranked by |K - close| (ties lower)."""
    out = set()
    for inc in increments:
        q = round(close / inc, 9)
        for k in (math.floor(q) * inc, math.ceil(q) * inc):
            k = round(k, 2)
            if k > 0 and abs(k - close) <= band * close + 1e-9:
                out.add(k)
    return tuple(sorted(out, key=lambda k: (round(abs(k - close), 6), k)))


@dataclass
class EventPlan:
    ticker: str
    ann_date: date
    session: str
    e: date
    entry: date
    exit: date
    close: float                       # entry close on the option chain's basis
    front: date
    back: date
    candidates: tuple[float, ...] = ()
    close_adj: float | None = None     # the adjusted close as read
    factor: float = 1.0
    basis: str = ""                    # "" | basis_unconfirmed | basis_unchecked

    @property
    def rebased(self) -> bool:
        return self.factor != 1.0


def plan_event(ticker: str, ann_date: date, session: str, *, sessions: list[date],
               closes: dict[date, float], expiries: Callable[[date, date], list[date]],
               prices: dict[date, list[float]] | None = None, rescaled: bool = False,
               ) -> tuple[EventPlan | None, str]:
    """`(plan, why)`. `why` is "" for a plan, else the drop reason:
    unknown_session / no_event_session / no_entry_session / no_close /
    no_unadjusted_close / no_expiry / no_candidate.

    Inputs dated after the entry day are never consulted: `closes` and
    `prices` are read on or before `entry` only, and `expiries(entry, e)` is
    told only the entry and E.
    """
    if session not in ("bmo", "amc", "dmh"):
        return None, "unknown_session"
    e = event_session(ann_date, session, sessions)
    if e is None:
        return None, "no_event_session"
    entry = entry_session(e, sessions)
    if entry is None:
        return None, "no_entry_session"
    adj = closes.get(entry)
    if adj is None or adj <= 0:
        return None, "no_close"
    b = basis_factor(entry, sessions, closes, prices or {})
    if b.factor is None and rescaled:
        return None, "no_unadjusted_close"
    factor = b.factor or 1.0
    close = round(adj * factor, 4)
    picked = pick_expiries(e, expiries(entry, e))
    if picked is None:
        return None, "no_expiry"
    cands = strike_ladder(close)
    if not cands:
        return None, "no_candidate"
    front, back = picked
    return EventPlan(ticker, ann_date, session, e, entry, e, close, front, back, cands,
                     adj, factor, b.status), ""


# ─── Leg status and the ATM walk (shared with the study) ───────────────────────

def contract_stem(t: str, x: date, k: float, r: str) -> str:
    return cache_path(Path("."), t, x, k, "Call" if r == "C" else "Put").stem


class LegStatus:
    """`status(t, x, k, r, d)` from the cache: ok (a file with a row on d) /
    not_quoted (a file, no row on d) / failed (manifest) / unlisted
    (`_unlisted.jsonl`, whatever its age) / not_fetched."""

    def __init__(self, cache_dir: Path = HISTORY_CACHE, unlisted: Iterable[str] = (),
                 failed: Iterable[str] = ()):
        self.cache_dir = Path(cache_dir)
        self.unlisted, self.failed = set(unlisted), set(failed)
        self._days: dict[Path, set[date] | None] = {}

    def days(self, t, x, k, r) -> set[date] | None:
        p = cache_path(self.cache_dir, t, x, k, "Call" if r == "C" else "Put")
        if p not in self._days:
            self._days[p] = cached_days(p) if p.exists() else None
        return self._days[p]

    def __call__(self, t: str, x: date, k: float, r: str, d: date) -> str:
        ds = self.days(t, x, k, r)
        if ds is not None:
            return OK if d in ds else NOT_QUOTED
        stem = contract_stem(t, x, k, r)
        if stem in self.failed:
            return FAILED
        return UNLISTED if stem in self.unlisted else NOT_FETCHED


@dataclass
class AtmPick:
    strike: float | None
    reason: str                                          # "" | front_not_fetched | front_no_candidate
    passed: list[tuple[float, str]] = field(default_factory=list)


def resolve_atm(plan: EventPlan, status: Callable) -> AtmPick:
    """The first ladder candidate whose front call and put both have an
    entry-day row. A candidate with a bad leg (failed / unlisted / no entry-day
    row) is passed over; one with an unfetched leg and no bad one stops the walk
    (`front_not_fetched`). Reads entry-day rows only."""
    pick = AtmPick(None, "front_no_candidate")
    for k in plan.candidates:
        sts = [status(plan.ticker, plan.front, k, r, plan.entry) for r in RIGHTS]
        if all(s == OK for s in sts):
            pick.strike, pick.reason = k, ""
            return pick
        bad = [s for s in sts if s in BAD]
        if bad:
            pick.passed.append((k, bad[0]))
            continue
        pick.reason = "front_not_fetched"
        return pick
    return pick


@dataclass
class FrontWalk:
    targets: list[tuple] = field(default_factory=list)   # (ticker, expiry, strike, right)
    cached: int = 0
    failed: int = 0
    unlisted: int = 0
    resolved: bool = False


def front_walk(plan: EventPlan, status: Callable, width: int = PROBE_WIDTH) -> FrontWalk:
    """The front contracts one pass targets: the unfetched legs of up to
    `width` unresolved candidates, walked in ladder order, stopping at the
    first confirmed candidate."""
    w, n_unres = FrontWalk(), 0
    for k in plan.candidates:
        sts = {r: status(plan.ticker, plan.front, k, r, plan.entry) for r in RIGHTS}
        w.cached += sum(s in (OK, NOT_QUOTED) for s in sts.values())
        w.failed += sum(s == FAILED for s in sts.values())
        w.unlisted += sum(s == UNLISTED for s in sts.values())
        if all(s == OK for s in sts.values()):
            w.resolved = True
            return w
        if any(s in BAD for s in sts.values()):
            continue
        w.targets += [(plan.ticker, plan.front, k, r) for r, s in sts.items() if s == NOT_FETCHED]
        n_unres += 1
        if n_unres >= width:
            break
    return w


def back_targets(plan: EventPlan, strike: float, status: Callable) -> tuple[list[tuple], Counter]:
    """The back call and put at the confirmed ATM, less what is cached, failed
    or unlisted."""
    st = Counter()
    out = []
    for r in RIGHTS:
        s = status(plan.ticker, plan.back, strike, r, plan.entry)
        st[s] += 1
        if s == NOT_FETCHED:
            out.append((plan.ticker, plan.back, strike, r))
    return out, st


# ─── Inputs: calendar, closes, caches ──────────────────────────────────────────

def read_events(ticker: str, earnings_dir: Path = EARNINGS_DIR) -> list[tuple[date, str]]:
    """`[(ann_date, session)]` from agent-trading's earnings CSV; [] if absent."""
    p = earnings_dir / f"{ticker}.csv"
    if not p.exists():
        return []
    out = {}
    with open(p, newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                out[date.fromisoformat(row["ann_date"])] = (row.get("session") or "").strip()
            except (KeyError, ValueError):
                continue
    return sorted(out.items())


def read_closes(path: Path) -> dict[date, float]:
    """Closes from agent-trading's `date,close` files or the repo's own
    Barchart-schema `underlying_ohlc_cache` (`Time,...,Latest`)."""
    out = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            day = row.get("date") or row.get("Time")
            close = row.get("close") or row.get("Latest")
            try:
                out[date.fromisoformat(day[:10])] = float(close)
            except (TypeError, ValueError):
                continue
    return out


def read_rescaled(path: Path = RESCALED_FILE) -> set[str]:
    """Tickers whose scraped bars are split-adjusted against `Price~`."""
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.add(s.split()[0].upper())
    return out


_FILE_RE = re.compile(r"^(?P<t>[A-Z.\-]+)_(?P<x>\d{8})_(?P<k>[\d.]+)(?P<r>[CP])\.csv$")


def cache_index(cache_dir: Path = HISTORY_CACHE) -> dict[str, dict[date, set[float]]]:
    """`{ticker: {expiry: {strikes}}}` from file NAMES only (expiry confirmation)."""
    idx: dict[str, dict[date, set[float]]] = defaultdict(lambda: defaultdict(set))
    for name in os.listdir(cache_dir):
        m = _FILE_RE.match(name)
        if m:
            x = m["x"]
            idx[m["t"]][date(int(x[:4]), int(x[4:6]), int(x[6:]))].add(float(m["k"]))
    return idx


def price_index(ticker: str, cache_dir: Path = HISTORY_CACHE) -> dict[date, list[float]]:
    """`{day: [Price~ of every cached file of the ticker with a row that day]}`."""
    out: dict[date, list[float]] = defaultdict(list)
    for name in os.listdir(cache_dir):
        if not name.startswith(ticker + "_") or not _FILE_RE.match(name):
            continue
        with open(cache_dir / name) as fh:
            hdr = fh.readline().rstrip("\r\n").split(",")
            if "Price~" not in hdr or "Time" not in hdr:
                continue
            jt, jp = hdr.index("Time"), hdr.index("Price~")
            seen = set()
            for line in fh:
                p = line.rstrip("\r\n").split(",")
                try:
                    d, v = date.fromisoformat(p[jt][:10]), float(p[jp])
                except (ValueError, IndexError):
                    continue
                if v > 0 and d not in seen:
                    seen.add(d)
                    out[d].append(v)
    return dict(out)


def closes_from_option_files(ticker: str, cache_dir: Path = HISTORY_CACHE) -> dict[date, float]:
    """Last resort: the median `Price~` across cached option files per day."""
    return {d: statistics.median(v) for d, v in price_index(ticker, cache_dir).items()}


def load_closes(ticker: str, dirs: Iterable[Path] = HISTORY_DIRS,
                cache_dir: Path = HISTORY_CACHE) -> tuple[dict[date, float], str]:
    for d in dirs:
        p = Path(d) / f"{ticker}.csv"
        if p.exists():
            c = read_closes(p)
            if c:
                return c, str(Path(d).parent.name + "/" + Path(d).name)
    c = closes_from_option_files(ticker, cache_dir)
    return c, ("option Price~" if c else "")


def cached_days(path: Path) -> set[date]:
    out = set()
    try:
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    out.add(date.fromisoformat(row["Time"][:10]))
                except (KeyError, ValueError):
                    pass
    except OSError:
        pass
    return out


def manifest_failed(path: Path = MANIFEST_PATH) -> set[str]:
    """Stems of every contract the manifest records as failed."""
    if not path.exists():
        return set()
    out = set()
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("status") != "failed":
                continue
            try:
                out.add(contract_stem(r["ticker"], date.fromisoformat(r["expiration"]),
                                      float(r["strike"]), r["opt_type"]))
            except (KeyError, ValueError):
                continue
    return out


def unlisted_keys(cache_dir: Path = HISTORY_CACHE) -> set[str]:
    from scripts.backtest.shared import unlisted
    return set(unlisted.load(cache_dir / unlisted.FILENAME))


# ─── The planner ───────────────────────────────────────────────────────────────

@dataclass
class TickerPlan:
    ticker: str
    close_source: str = ""
    events_in_window: int = 0
    dropped: Counter = field(default_factory=Counter)
    sealed: list[tuple[date, str]] = field(default_factory=list)
    plans: list[EventPlan] = field(default_factory=list)
    expiry_confirmed: int = 0
    expiry_total: int = 0

    @property
    def rebased(self) -> int:
        return sum(p.rebased for p in self.plans)

    def basis_count(self, status: str) -> int:
        return sum(p.basis == status for p in self.plans)


def sessions_from_calendar(path: Path | None = None) -> list[date]:
    p = path or (AGENT_TRADING / "history" / "SPY.csv")
    if p.exists():
        return sorted(read_closes(p))
    return []


def plan_ticker(ticker: str, *, events: list[tuple[date, str]], sessions: list[date],
                closes: dict[date, float], close_source: str,
                prices: dict[date, list[float]] | None = None, rescaled: bool = False,
                idx: dict | None = None, include_unknown: bool = False) -> TickerPlan:
    """Plans every in-window event. `idx` (cache file names) only counts how
    many generated expiries a cached file confirms; it decides nothing."""
    tp = TickerPlan(ticker, close_source)
    sess_set, last = set(sessions), (sessions[-1] if sessions else None)
    t_idx = (idx or {}).get(ticker, {})

    def expiries(entry: date, e: date) -> list[date]:
        return weekly_fridays(entry, e + timedelta(days=BACK_GAP_DAYS + 14), sess_set, last)

    for ann, sess in events:
        if not (WINDOW_START <= ann <= WINDOW_END):
            continue
        tp.events_in_window += 1
        eff = "amc" if (include_unknown and sess == "unknown") else sess
        plan, why = plan_event(ticker, ann, eff, sessions=sessions, closes=closes,
                               expiries=expiries, prices=prices, rescaled=rescaled)
        if plan is None:
            tp.dropped[why] += 1
            continue
        if plan.e >= SEAL_START:
            tp.sealed.append((ann, sess))
            tp.dropped["sealed"] += 1
            continue
        tp.plans.append(plan)
        for x in (plan.front, plan.back):
            tp.expiry_total += 1
            tp.expiry_confirmed += x in t_idx
    return tp


@dataclass
class PhaseRow:
    """One ticker's two passes, as the dry run prints them."""
    resolved: int = 0          # events whose ATM is confirmed now
    pending: int = 0           # events waiting on a front fetch
    no_candidate: int = 0      # every candidate passed over
    front_cached: int = 0      # front legs the walk found cached
    front_failed: int = 0      # front legs the walk found failed (passed over)
    front_unlisted: int = 0
    front_fetch: int = 0       # phase 1 targets now
    back_cached: int = 0
    back_failed: int = 0
    back_fetch: int = 0        # phase 2 targets now (resolved events)
    back_later: int = 0        # 2 per pending event: phase 2 after a front pass


def plan_phases(tps: Iterable[TickerPlan], status: Callable, width: int = PROBE_WIDTH,
                ) -> tuple[dict[str, PhaseRow], set[tuple], set[tuple]]:
    """`(rows by ticker, front targets, back targets)` for the cache as it is now."""
    rows, front, back = {}, set(), set()
    for tp in tps:
        row = PhaseRow()
        for p in tp.plans:
            w = front_walk(p, status, width)
            row.front_cached += w.cached
            row.front_failed += w.failed
            row.front_unlisted += w.unlisted
            new = [c for c in w.targets if c not in front]
            front.update(new)
            row.front_fetch += len(new)
            pick = resolve_atm(p, status)
            if pick.strike is not None:
                row.resolved += 1
                tg, st = back_targets(p, pick.strike, status)
                row.back_cached += st[OK] + st[NOT_QUOTED]
                row.back_failed += st[FAILED]
                new = [c for c in tg if c not in back]
                back.update(new)
                row.back_fetch += len(new)
            elif pick.reason == "front_not_fetched":
                row.pending += 1
                row.back_later += 2
            else:
                row.no_candidate += 1
        rows[tp.ticker] = row
    return rows, front, back


def target_records(contracts: Iterable[tuple]) -> list[dict]:
    """Contracts in the shape `fetch_sweep_legs` manifests take."""
    out = [dict(ticker=t, expiration=x, strike=k, opt_type=r, category=CATEGORY)
           for t, x, k, r in contracts]
    return sorted(out, key=lambda r: (r["ticker"], r["expiration"], r["strike"], r["opt_type"]))


def build_plans(tickers: Iterable[str], *, earnings_dir: Path = EARNINGS_DIR,
                include_unknown: bool = False, cache_dir: Path = HISTORY_CACHE,
                ) -> list[TickerPlan]:
    sessions = sessions_from_calendar()
    idx = cache_index(cache_dir)
    rescaled = read_rescaled()
    out = []
    for t in tickers:
        events = read_events(t, earnings_dir)
        closes, src = load_closes(t, cache_dir=cache_dir) if events else ({}, "")
        prices = price_index(t, cache_dir) if events else {}
        out.append(plan_ticker(t, events=events, sessions=sessions, closes=closes,
                               close_source=src, prices=prices, rescaled=t in rescaled,
                               idx=idx, include_unknown=include_unknown))
    return out


# ─── Reporting ─────────────────────────────────────────────────────────────────

def print_dry_run(tps: list[TickerPlan], rows: dict[str, PhaseRow], missing_files: list[str],
                  width: int, retry_failed: bool) -> None:
    hdr = (f"{'name':6} {'ev':>3} {'unk':>3} {'seal':>4} {'drop':>4} {'kept':>4} {'rebas':>5} "
           f"{'atm':>4} {'pend':>4} {'none':>4} | {'f.cach':>6} {'f.fail':>6} {'f.unl':>5} "
           f"{'FETCH1':>6} | {'b.cach':>6} {'b.fail':>6} {'b.now':>5} {'b.later':>7}  close source")
    print(hdr)
    tot = Counter()
    for tp in tps:
        r = rows[tp.ticker]
        d = dict(ev=tp.events_in_window, unk=tp.dropped["unknown_session"],
                 seal=tp.dropped["sealed"],
                 drop=sum(v for k, v in tp.dropped.items() if k not in ("unknown_session", "sealed")),
                 kept=len(tp.plans), reb=tp.rebased, **vars(r))
        tot.update(d)
        print(f"{tp.ticker:6} {d['ev']:>3} {d['unk']:>3} {d['seal']:>4} {d['drop']:>4} "
              f"{d['kept']:>4} {d['reb']:>5} {r.resolved:>4} {r.pending:>4} {r.no_candidate:>4} | "
              f"{r.front_cached:>6} {r.front_failed:>6} {r.front_unlisted:>5} {r.front_fetch:>6} | "
              f"{r.back_cached:>6} {r.back_failed:>6} {r.back_fetch:>5} {r.back_later:>7}  "
              f"{tp.close_source or 'NONE'}")
    t = tot
    print(f"{'TOTAL':6} {t['ev']:>3} {t['unk']:>3} {t['seal']:>4} {t['drop']:>4} {t['kept']:>4} "
          f"{t['reb']:>5} {t['resolved']:>4} {t['pending']:>4} {t['no_candidate']:>4} | "
          f"{t['front_cached']:>6} {t['front_failed']:>6} {t['front_unlisted']:>5} "
          f"{t['front_fetch']:>6} | {t['back_cached']:>6} {t['back_failed']:>6} "
          f"{t['back_fetch']:>5} {t['back_later']:>7}")
    print(f"\nphase 1 (front, width {width}) to fetch now: {t['front_fetch']} contracts "
          f"~{t['front_fetch'] * SECONDS_PER_CONTRACT / 60:.0f} min; re-run until it targets 0")
    print(f"phase 2 (back) to fetch now: {t['back_fetch']} (events with a confirmed ATM); "
          f"after phase 1 resolves the pending events, up to {t['back_later']} more")
    print(f"failed legs met by the walk: front {t['front_failed']}, back {t['back_failed']} — "
          + ("RETRIED (--retry-failed)" if retry_failed
             else "passed over; --retry-failed re-targets them"))
    drops = Counter()
    for tp in tps:
        drops.update({k: v for k, v in tp.dropped.items() if k not in ("unknown_session", "sealed")})
    print(f"planner drops other than unknown/sealed: {dict(drops) or 0}")
    unconf = sum(tp.basis_count("basis_unconfirmed") for tp in tps)
    unchk = sum(tp.basis_count("basis_unchecked") for tp in tps)
    print(f"close basis: {t['reb']} event(s) close_rebased; {unconf} basis_unconfirmed and "
          f"{unchk} basis_unchecked kept their close")
    sealed = [(tp.ticker, a, s) for tp in tps for a, s in tp.sealed]
    print(f"sealed (E >= {SEAL_START}), dropped from the count: "
          + (", ".join(f"{tk} {a} {s}" for tk, a, s in sealed) or "none"))
    conf = sum(tp.expiry_confirmed for tp in tps)
    tot_x = sum(tp.expiry_total for tp in tps)
    print(f"expiries confirmed by a cached file for the ticker: {conf}/{tot_x} "
          "(generated Fridays are an assumption)")
    if missing_files:
        print("no earnings file (estimate only): " + ", ".join(missing_files))


# ─── CLI ───────────────────────────────────────────────────────────────────────

def status_for(cache_dir: Path = HISTORY_CACHE, *, retry_failed: bool = False,
               retry_unlisted: bool = False, manifest: Path = MANIFEST_PATH) -> LegStatus:
    return LegStatus(cache_dir,
                     unlisted=() if retry_unlisted else unlisted_keys(cache_dir),
                     failed=() if retry_failed else manifest_failed(manifest))


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from lib.logger import setup_logging
    setup_logging()
    log.setLevel(logging.INFO)
    logging.getLogger("fetch_sweep_legs").setLevel(logging.INFO)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", choices=("front", "back"), default="front",
                    help="front: probe ladder candidates (re-run until 0); back: back legs at "
                         "confirmed ATM strikes. The dry run prints both.")
    ap.add_argument("--width", type=int, default=PROBE_WIDTH,
                    help="Unresolved candidates targeted per event per front pass.")
    ap.add_argument("--execute", action="store_true",
                    help="Fetch from Barchart. Without it: dry run, no network, no manifest.")
    ap.add_argument("--limit", type=int, default=None, help="Fetch at most N contracts (resumable).")
    ap.add_argument("--names", default=",".join(UNIVERSE + ADDED), help="Comma list of tickers.")
    ap.add_argument("--earnings-dir", type=Path, default=EARNINGS_DIR)
    ap.add_argument("--include-unknown", action="store_true", help="Treat unknown session as amc.")
    ap.add_argument("--retry-unlisted", action="store_true", help="Ignore _unlisted.jsonl.")
    ap.add_argument("--retry-failed", action="store_true",
                    help="Treat manifest failures as unfetched; re-target those the walk reaches.")
    ap.add_argument("--no-headless", action="store_true")
    args = ap.parse_args()

    names = [n.strip().upper() for n in args.names.split(",") if n.strip()]
    have = [n for n in names if (args.earnings_dir / f"{n}.csv").exists()]
    absent = [n for n in names if n not in have]
    tps = build_plans(have, earnings_dir=args.earnings_dir, include_unknown=args.include_unknown)
    status = status_for(retry_failed=args.retry_failed, retry_unlisted=args.retry_unlisted)
    rows, front, back = plan_phases(tps, status, args.width)
    print_dry_run(tps, rows, absent, args.width, args.retry_failed)
    planned = front if args.phase == "front" else back
    targets = target_records(planned)

    if not args.execute:
        print("\ndry run: nothing fetched, manifest untouched. --execute to fetch.")
        return

    from scripts.collector.study_legs.fetch_sweep_legs import (
        _key, load_manifest, merge_manifest, print_summary, run_fetch, sync_cache_status,
        write_manifest)
    rows_m = merge_manifest(load_manifest(MANIFEST_PATH), targets)
    if args.retry_failed:
        # only the failed rows THIS rule planned again go back to pending; every
        # other failure stays recorded as failed
        for r in targets:
            k = _key(r["ticker"], r["expiration"], r["strike"], r["opt_type"])
            if rows_m[k].get("status") == "failed":
                rows_m[k]["status"], rows_m[k]["reason"] = "pending", "retry: " + rows_m[k]["reason"]
    sync_cache_status(rows_m)
    write_manifest(MANIFEST_PATH, rows_m)
    print_summary(rows_m)
    stats = asyncio.run(run_fetch(rows_m, MANIFEST_PATH, limit=args.limit, retry_failed=False,
                                  headless=not args.no_headless))
    log.info("fetch stats: %s", "  ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    print_summary(rows_m)


if __name__ == "__main__":
    main()
