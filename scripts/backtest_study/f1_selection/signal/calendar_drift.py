"""calendar_drift — do the pre-FOMC drift and the turn of the month still pay on SPY after publication?

REGISTERED 2026-11-27: research/pre-registrations/f1_selection/signal/calendar_drift.md.
Every constant, window, floor, seed and verdict word below is that file's. Read
it before changing anything here. The registration is immutable in substance.

WHAT IT ASKS
------------
Two fixed calendar windows on SPY shares, net of 2 bps a side:

  PF   r_D, the close-to-close return of each SCHEDULED FOMC decision day D.
  TOM  r_L, r_F1, r_F2, r_F3: the last session of a month and the first three
       of the next (McConnell and Xu's interval).

Statistic per arm: Delta = mean net in-window daily return - mean out-of-window
daily return, on the GRADED years after each paper (PF 2012 on, TOM 2009 on).
The PRIOR years print as the published prior; FORWARD events start after the
registration date. Cycle bootstrap (10,000 draws, seed 20261127), Holm m = 2.
Robustness for a positive result: GL leave-one-year-out, GP placebo (PF 6
sessions later, TOM 10 earlier), GV overlap removal.

DATA
----
SPY daily bars from yfinance, auto_adjust=False, cached in
`backtests/calendar_drift/SPY.csv` (date, close, adj_close), fetched ONLY with
`--refresh`. A session finished today is kept only after 16:30 New York time.
FOMC decision days: `config/fomc-history.yml` (1994-01 to 2023-05, hand
transcribed from federalreserve.gov) plus the scheduled `fomc` entries of
`config/macro-events.yml` from 2023-06 on.

Window membership reads only the session calendar and the FOMC dates, never a
price (gate GX, pinned by tests/test_calendar_drift.py).

The holdout seal does not apply: no flow signal, play or backtest row is read.
Nothing ships from this study. Run:

    python -m scripts.backtest_study run calendar_drift
    python -m scripts.backtest_study run calendar_drift --refresh
"""
from __future__ import annotations

import argparse
import bisect
import csv
import math
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection.benchmark.ticker_class import holm  # noqa: E402
from scripts.backtest_study.f1_selection.regime.tail_breach import ratio_problems  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib.macro_calendar import MacroCalendar  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/signal/calendar_drift.md"
REGISTERED: str | None = "2026-11-27"

# --- constants fixed by the registration -------------------------------------
COST = 0.0004                    # round trip: 2 bps per side
WINDOW_N = {"PF": 1, "TOM": 4}   # window sessions; each window day pays COST / n
PLACEBO_SHIFT = {"PF": 6, "TOM": -10}
BOOT_N = 10_000
SEED = 20261127
ALPHA = 0.05
MIN_EVENTS = 40                  # GN
MIN_YEARS = {"GRADED": 5, "FORWARD": 3}
TRADING_DAYS = 252
ARMS = ("PF", "TOM")
POPS = ("PRIOR", "GRADED", "FORWARD")
# Event populations by first session; out-of-window days by their own date.
POP_RANGES = {
    "PF": {"PRIOR": ("1994-01-01", "2011-12-31"), "GRADED": ("2012-01-01", REGISTERED)},
    "TOM": {"PRIOR": ("1993-01-29", "2008-12-31"), "GRADED": ("2009-01-01", REGISTERED)},
}
UNION_RANGES = {"GRADED": ("2012-01-01", REGISTERED), "PRIOR": ("1994-01-01", "2008-12-31")}

# GE / GF
SPY_START_LATEST = "1993-02-01"
HISTORY_START, HISTORY_END = "1994-01-01", "2023-05-31"
GF_YEARS = (1994, 2022)
DECISIONS_PER_YEAR = 8
JOIN_MAX_DAYS = 70

CACHE_DIR = ROOT / "backtests" / "calendar_drift"
SPY_CSV = CACHE_DIR / "SPY.csv"
HISTORY_YML = ROOT / "config" / "fomc-history.yml"
HISTORY_REL = "config/fomc-history.yml"
MACRO_YML = ROOT / "config" / "macro-events.yml"
SPY_FETCH_START = "1993-01-01"
NY_CLOSE_SETTLED = "16:30"       # a bar dated today is kept only after this NY time

STILL_PAYS, FRAGILE, NULL, REVERSED = "STILL-PAYS", "FRAGILE", "NULL", "REVERSED"
UNDERPOWERED, STILL_OPEN = "UNDERPOWERED", "STILL-OPEN"
BANNER = {
    "PF": "SPY decision-day close-to-close return, net 2 bps a side, vs other days, 2012 on, Holm m=2",
    "TOM": "SPY last session plus first three of the month, net 2 bps a side, vs other days, "
           "2009 on, Holm m=2",
}
RULE = "=" * 78

# Exit 2: any era but `current`. Exit 3: GE, GB or GF.
EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
# Header provenance the runner reads by ast (docs/architecture.md, study module contract).
HEADER_ERA = "none (market closes and the FOMC calendar only)"
HEADER_INPUTS = ["backtests/calendar_drift/SPY.csv", "config/fomc-history.yml",
                 "config/macro-events.yml"]


class Refused(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════════════════════════════════════════════════════════════
# Data
# ════════════════════════════════════════════════════════════════════════════

def _ny_now() -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def fetch_spy(path: Path = SPY_CSV) -> Path:
    """yfinance -> `backtests/calendar_drift/SPY.csv`. Overwrites the file in
    place. A bar dated today is dropped unless New York time is past 16:30."""
    import pandas as pd
    import yfinance as yf
    now = _ny_now()
    today = now.date()
    end = (today + timedelta(days=1)).isoformat()
    df = yf.download("SPY", start=SPY_FETCH_START, end=end, auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise Refused(EXIT_INPUT, "GE: yfinance returned no rows for SPY. Exit 3.")

    def col(c):
        x = df[c]
        return x.iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else x

    close, adj = col("Close"), col("Adj Close")
    keep_today = now.strftime("%H:%M") >= NY_CLOSE_SETTLED
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "close", "adj_close"])
        for d, c, a in zip(close.index, close.values, adj.values):
            ds = pd.Timestamp(d).strftime("%Y-%m-%d")
            if ds > today.isoformat() or (ds == today.isoformat() and not keep_today):
                continue
            if c == c:
                w.writerow([ds, repr(float(c)), repr(float(a)) if a == a else ""])
                n += 1
    print(f"fetched SPY -> {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} "
          f"({n} rows)")
    return path


def read_spy(path: Path) -> list[tuple[str, float, float | None]]:
    """(date, close, adj_close) rows, ascending, finite positive closes only."""
    out = []
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                c = float(r["close"])
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(c) and c > 0):
                continue
            try:
                a = float(r.get("adj_close") or "nan")
            except ValueError:
                a = float("nan")
            out.append((r["date"][:10], c, a if math.isfinite(a) and a > 0 else None))
    return sorted(out)


@dataclass
class Cal:
    """The SPY session calendar (sessions with an Adj Close) and its returns."""
    dates: list[str]
    adj: np.ndarray
    r: np.ndarray = field(init=False)
    pos: dict = field(init=False)

    def __post_init__(self):
        self.adj = np.asarray(self.adj, dtype=float)
        self.r = daily_returns(self.adj)
        self.pos = {d: i for i, d in enumerate(self.dates)}

    @property
    def n(self) -> int:
        return len(self.dates)


def build_cal(spy: list[tuple]) -> Cal:
    rows = [x for x in spy if x[2] is not None]
    return Cal([x[0] for x in rows], np.array([x[2] for x in rows], dtype=float))


def daily_returns(adj: np.ndarray) -> np.ndarray:
    """r[i] = adj[i] / adj[i-1] - 1; NaN at 0 (undefined)."""
    out = np.full(len(adj), np.nan)
    if len(adj) > 1:
        out[1:] = adj[1:] / adj[:-1] - 1.0
    return out


# ════════════════════════════════════════════════════════════════════════════
# FOMC calendar
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Fomc:
    history: list[str]                 # decision days, 1994-01 to 2023-05
    macro: list[str]                   # scheduled macro-events.yml fomc dates
    exceptions: dict                   # {year: reason}
    horizon: str                       # macro-events verified_through.fomc

    @property
    def decisions(self) -> list[str]:
        return sorted(set(self.history) | set(self.macro))


def load_history(path: Path = HISTORY_YML) -> tuple[list[str], dict]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    dates = [str(e["date"]) for e in raw.get("decisions") or []]
    exc = {int(k): v for k, v in ((raw.get("meta") or {}).get("exceptions") or {}).items()}
    return dates, exc


def load_fomc(history_path: Path = HISTORY_YML, macro_path: Path = MACRO_YML) -> Fomc:
    hist, exc = load_history(history_path)
    mc = MacroCalendar.from_yaml(macro_path)
    macro = [e.date.isoformat() for e in mc.events(("fomc",)) if not e.unscheduled]
    return Fomc(hist, macro, exc, mc.verified_through("fomc").isoformat())


def gf_calendar_problems(fomc: Fomc, years: tuple[int, int] = GF_YEARS) -> list[str]:
    """GF's content checks: eight per year or a listed exception with a reason,
    sorted unique history dates on weekdays within the history span, and a join
    to macro-events.yml with no overlap and a gap under 70 days."""
    out = []
    h = fomc.history
    if h != sorted(h) or len(set(h)) != len(h):
        out.append("fomc-history.yml decisions are not sorted and unique")
    for d in h:
        dd = date.fromisoformat(d)
        if dd.weekday() >= 5:
            out.append(f"{d} is a weekend day")
        if not (HISTORY_START <= d <= HISTORY_END):
            out.append(f"{d} is outside {HISTORY_START}..{HISTORY_END}")
    for y in range(years[0], years[1] + 1):
        n = sum(1 for d in h if d[:4] == str(y))
        if n != DECISIONS_PER_YEAR:
            reason = fomc.exceptions.get(y)
            if not (isinstance(reason, str) and reason.strip()):
                out.append(f"{y}: {n} scheduled decisions, not {DECISIONS_PER_YEAR}, "
                           f"and no meta.exceptions reason")
    if not h or not fomc.macro:
        out.append("a FOMC source is empty")
        return out
    first_macro = min(fomc.macro)
    if not h[-1] < first_macro:
        out.append(f"history ends {h[-1]}, not before the first macro decision {first_macro}")
    gap = (date.fromisoformat(first_macro) - date.fromisoformat(h[-1])).days
    if gap >= JOIN_MAX_DAYS:
        out.append(f"join gap {gap} days (limit {JOIN_MAX_DAYS})")
    return out


def gf_session_problems(fomc: Fomc, cal: Cal) -> list[str]:
    """Every decision day up to the last session in the data is a SPY session."""
    last = cal.dates[-1]
    return [f"{d} is not a SPY session" for d in fomc.decisions
            if d <= last and d not in cal.pos]


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


def gf_git_problems() -> list[str]:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", HISTORY_REL], cwd=ROOT,
                             capture_output=True, text=True).returncode == 0
    if not tracked:
        return [f"{HISTORY_REL} is not tracked by git"]
    if _git("status", "--porcelain", "--", HISTORY_REL):
        return [f"{HISTORY_REL} is modified in the working tree or index"]
    return []


# ════════════════════════════════════════════════════════════════════════════
# Events and windows. Membership reads ONLY dates (calendar and FOMC), never a price.
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Event:
    arm: str
    days: tuple[int, ...]      # window session indices inside the data
    open: bool = False         # the window runs past the data, or its L is unsettled

    @property
    def first(self) -> int:
        return self.days[0]

    @property
    def last(self) -> int:
        return self.days[-1]


def pf_events(dates: list[str], decisions: list[str]) -> list[Event]:
    """One event per decision day that is a session in the data. Decision days
    after the data are future events with no day in the data: not returned."""
    pos = {d: i for i, d in enumerate(dates)}
    return [Event("PF", (pos[d],)) for d in sorted(decisions) if d in pos]


def tom_events(dates: list[str]) -> list[Event]:
    """L = the last session of a calendar month (the next session is in a later
    month); the window is L and the next three sessions. A window running past
    the data is open. The data's final session cannot be confirmed as its
    month's last, so it is an open (unsettled) event: in neither set. When that
    final session already sits inside an earlier open window it adds no event of
    its own (the session is counted once)."""
    n = len(dates)
    out = []
    for i in range(n):
        if i + 1 < n and dates[i + 1][:7] == dates[i][:7]:
            continue
        if i == n - 1 and any(i in e.days for e in out):
            continue
        days = tuple(j for j in range(i, i + WINDOW_N["TOM"]) if j < n)
        out.append(Event("TOM", days, open=(i + WINDOW_N["TOM"] - 1 >= n)))
    return out


def classify(e: Event, cal: Cal, arm: str, registered: str, horizon: str | None) -> str:
    """PRIOR / GRADED / FORWARD, or why the event is in neither: open, undefined
    (a window return undefined), gap (straddles the registration date), outside."""
    first, last = cal.dates[e.first], cal.dates[e.last]
    if e.open:
        return "open"
    if not all(math.isfinite(cal.r[d]) for d in e.days):
        return "undefined"
    if first <= registered < last:
        return "gap"
    if first > registered:
        if arm == "PF" and horizon is not None and last > horizon:
            return "outside"
        return "FORWARD"
    for pop, (a, b) in pop_ranges(arm, registered).items():
        if a <= first <= b:
            return pop
    return "outside"


def pop_session_range(arm: str, pop: str, registered: str, horizon: str | None,
                      last_date: str) -> tuple[str, str]:
    if pop == "FORWARD":
        nxt = (date.fromisoformat(registered) + timedelta(days=1)).isoformat()
        end = horizon if (arm == "PF" and horizon is not None) else last_date
        return nxt, end
    return pop_ranges(arm, registered)[pop]


def pop_ranges(arm: str, registered: str) -> dict:
    """PRIOR and GRADED first-session ranges; GRADED ends at `registered`."""
    return {"PRIOR": POP_RANGES[arm]["PRIOR"], "GRADED": (POP_RANGES[arm]["GRADED"][0], registered)}


@dataclass
class Book:
    """One arm on one population: counted events, net in-window values and the
    out-of-window days, all as session indices."""
    arm: str
    pop: str
    events: list[Event]
    in_vals: dict              # idx -> net return (r - COST / n)
    out_vals: dict             # idx -> r
    census: dict


def build_book(cal: Cal, arm: str, pop: str, all_events: list[Event], registered: str,
               horizon: str | None, cost: float = COST) -> Book:
    n_win = WINDOW_N[arm]
    labels = [classify(e, cal, arm, registered, horizon) for e in all_events]
    counted = [e for e, lab in zip(all_events, labels) if lab == pop]
    window_any = {d for e in all_events for d in e.days}
    in_vals = {d: float(cal.r[d]) - cost / n_win for e in counted for d in e.days}
    a, b = pop_session_range(arm, pop, registered, horizon, cal.dates[-1])
    out_vals = {i: float(cal.r[i]) for i, d in enumerate(cal.dates)
                if a <= d <= b and i not in window_any and math.isfinite(cal.r[i])}
    census = {lab: labels.count(lab) for lab in ("open", "undefined", "gap", "outside")}
    census["range"] = (a, b)
    return Book(arm, pop, counted, in_vals, out_vals, census)


# ════════════════════════════════════════════════════════════════════════════
# Statistic, cycles, bootstrap
# ════════════════════════════════════════════════════════════════════════════

def delta(in_vals: dict, out_vals: dict) -> float:
    if not in_vals or not out_vals:
        return float("nan")
    return float(np.mean(list(in_vals.values())) - np.mean(list(out_vals.values())))


def cycle_sums(in_vals: dict, out_vals: dict, boundaries: list[int]):
    """Cycles end at each event's last session (sorted `boundaries`); a cycle
    holds sessions after the previous boundary through its own. Days after the
    last boundary form one final cycle, dropped when empty. Returns per-cycle
    (sum_in, n_in, sum_out, n_out) arrays."""
    bnd = sorted(boundaries)
    k = len(bnd) + 1
    s_in, n_in, s_out, n_out = (np.zeros(k) for _ in range(4))
    for d, v in in_vals.items():
        c = bisect.bisect_left(bnd, d)
        s_in[c] += v
        n_in[c] += 1
    for d, v in out_vals.items():
        c = bisect.bisect_left(bnd, d)
        s_out[c] += v
        n_out[c] += 1
    if n_in[-1] + n_out[-1] == 0:
        s_in, n_in, s_out, n_out = s_in[:-1], n_in[:-1], s_out[:-1], n_out[:-1]
    return s_in, n_in, s_out, n_out


def boot_deltas(sums, draws: int | None = None, seed: int | None = None) -> np.ndarray:
    draws = BOOT_N if draws is None else draws
    seed = SEED if seed is None else seed
    s_in, n_in, s_out, n_out = sums
    k = len(s_in)
    if k == 0:
        return np.full(draws, np.nan)
    idx = np.random.default_rng(seed).integers(0, k, size=(draws, k))
    si, ni, so, no = s_in[idx].sum(1), n_in[idx].sum(1), s_out[idx].sum(1), n_out[idx].sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = si / ni - so / no
    out[(ni == 0) | (no == 0)] = np.nan
    return out


@dataclass
class Result:
    point: float
    lo: float
    hi: float
    p: float
    cycles: int
    n_in: int
    n_out: int

    @property
    def finite(self) -> bool:
        return math.isfinite(self.lo) and math.isfinite(self.hi)


def summarize(point: float, draws: np.ndarray, cycles: int, n_in: int, n_out: int) -> Result:
    """CI = 2.5th/97.5th percentiles; p two-sided = twice the smaller tail share
    at or beyond 0, capped at 1 (the tail_breach convention)."""
    d = draws[np.isfinite(draws)]
    if len(d) == 0 or not math.isfinite(point):
        return Result(point, float("nan"), float("nan"), 1.0, cycles, n_in, n_out)
    lo, hi = np.percentile(d, [2.5, 97.5])
    p = min(1.0, 2.0 * min(float(np.mean(d <= 0)), float(np.mean(d >= 0))))
    return Result(point, float(lo), float(hi), p, cycles, n_in, n_out)


def measure(in_vals: dict, out_vals: dict, boundaries: list[int],
            draws: int | None = None, seed: int | None = None) -> Result:
    sums = cycle_sums(in_vals, out_vals, boundaries)
    return summarize(delta(in_vals, out_vals), boot_deltas(sums, draws, seed),
                     len(sums[0]), len(in_vals), len(out_vals))


def measure_book(book: Book, draws: int | None = None, seed: int | None = None) -> Result:
    return measure(book.in_vals, book.out_vals, [e.last for e in book.events], draws, seed)


# ════════════════════════════════════════════════════════════════════════════
# Gates GN, GL, GP, GV
# ════════════════════════════════════════════════════════════════════════════

def event_year(cal: Cal, e: Event) -> str:
    return cal.dates[e.last][:4]


def gn(book: Book, cal: Cal) -> tuple[bool, int, int]:
    years = {event_year(cal, e) for e in book.events}
    floor = MIN_YEARS.get(book.pop, MIN_YEARS["GRADED"])
    return len(book.events) >= MIN_EVENTS and len(years) >= floor, len(book.events), len(years)


def year_split(book: Book, cal: Cal) -> dict:
    """{year: (in_vals, out_vals)}: an event's days go to its last session's year,
    an out-of-window day to its own."""
    out: dict = {}
    for e in book.events:
        y = event_year(cal, e)
        out.setdefault(y, ({}, {}))
        for d in e.days:
            out[y][0][d] = book.in_vals[d]
    for d, v in book.out_vals.items():
        y = cal.dates[d][:4]
        out.setdefault(y, ({}, {}))
        out[y][1][d] = v
    return dict(sorted(out.items()))


def gl(book: Book, cal: Cal) -> tuple[bool, dict]:
    """Leave one calendar year out; passes when every estimate is above zero."""
    split = year_split(book, cal)
    est = {}
    for y in split:
        iv = {d: v for yy, (i, _) in split.items() if yy != y for d, v in i.items()}
        ov = {d: v for yy, (_, o) in split.items() if yy != y for d, v in o.items()}
        est[y] = delta(iv, ov)
    ok = bool(est) and all(math.isfinite(v) and v > 0 for v in est.values())
    return ok, est


def placebo(book: Book, other_window_days: set, own_window_days: set, cost: float = COST,
            cal: Cal | None = None) -> tuple[dict, dict, list[int], int]:
    """Shift every counted window by PLACEBO_SHIFT[arm] sessions. A shifted day
    stays only if it is one of this population's out-of-window days and not a
    window day of the other arm (that day stays an out-of-window day). Returns
    (placebo in_vals, reference out_vals = out-of-window less placebo days,
    placebo cycle boundaries, days dropped by the other-arm rule)."""
    s = PLACEBO_SHIFT[book.arm]
    n_win = WINDOW_N[book.arm]
    pin, bnd, dropped_other = {}, [], 0
    for e in book.events:
        shifted = [d + s for d in e.days]
        bnd.append(shifted[-1])
        for d in shifted:
            if d in own_window_days or d not in book.out_vals:
                continue
            if d in other_window_days:
                dropped_other += 1
                continue
            pin[d] = book.out_vals[d] - cost / n_win
    ref = {d: v for d, v in book.out_vals.items() if d not in pin}
    return pin, ref, bnd, dropped_other


def overlap_events(book: Book, tom_window_days: set, decision_idx: set) -> list[Event]:
    """Events of the arm that overlap the other: a PF decision day inside any TOM
    window, or a TOM window holding any decision day."""
    if book.arm == "PF":
        return [e for e in book.events if e.days[0] in tom_window_days]
    return [e for e in book.events if any(d in decision_idx for d in e.days)]


def ex_overlap(book: Book, tom_window_days: set, decision_idx: set) -> tuple[dict, dict, list[int], int]:
    """GV: remove overlapping events; their days leave the in-window set and do
    not join the out-of-window set."""
    drop = set(overlap_events(book, tom_window_days, decision_idx))
    keep = [e for e in book.events if e not in drop]
    iv = {d: book.in_vals[d] for e in keep for d in e.days}
    return iv, dict(book.out_vals), [e.last for e in keep], len(drop)


# ════════════════════════════════════════════════════════════════════════════
# Verdict
# ════════════════════════════════════════════════════════════════════════════

def verdict(res: Result, powered: bool, p_adj: float, gl_ok: bool, gp_ok: bool,
            gv_ok: bool, forward: bool = False) -> str:
    """The registration's table, read top to bottom; the first row that holds."""
    if not powered or not res.finite:
        return STILL_OPEN if forward else UNDERPOWERED
    if res.hi < 0 and p_adj < ALPHA:
        return REVERSED
    if res.lo > 0 and p_adj < ALPHA and gl_ok and gp_ok and gv_ok:
        return STILL_PAYS
    if res.lo > 0 and p_adj < ALPHA:
        return FRAGILE
    return NULL


# ════════════════════════════════════════════════════════════════════════════
# Printed-only metrics
# ════════════════════════════════════════════════════════════════════════════

def strategy_lines(book: Book, cal: Cal) -> dict:
    """ANNUAL, SHARPE and CAPTURE over the population's sessions (in-window and
    out-of-window days); the strategy holds cash at zero out of the window."""
    days = sorted(set(book.in_vals) | set(book.out_vals))
    if not days:
        return {"annual": float("nan"), "sharpe": float("nan"), "capture": None, "n": 0}
    s = np.array([book.in_vals.get(d, 0.0) for d in days])
    r = np.array([cal.r[d] for d in days])
    annual = float(np.prod(1.0 + s) ** (TRADING_DAYS / len(s)) - 1.0)
    sd = float(np.std(s, ddof=1)) if len(s) > 1 else 0.0
    sharpe = float(np.mean(s) / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else float("nan")
    den = float(np.sum(np.log1p(r)))
    capture = float(np.sum(np.log1p(s)) / den) if den > 0 else None
    return {"annual": annual, "sharpe": sharpe, "capture": capture, "n": len(s)}


def hit_lines(book: Book, cal: Cal, cost: float = COST) -> tuple[float, float, int]:
    """(share of events with a positive net return, SPY's share of positive gross
    returns over every same-length window starting in the population's range,
    that window count)."""
    n_win = WINDOW_N[book.arm]
    net = [float(np.prod([1.0 + cal.r[d] for d in e.days]) - 1.0 - cost) for e in book.events]
    hit = float(np.mean([x > 0 for x in net])) if net else float("nan")
    a, b = book.census["range"]
    base = []
    for i, d in enumerate(cal.dates):
        if not (a <= d <= b) or i + n_win > cal.n:
            continue
        rr = cal.r[i:i + n_win]
        if np.all(np.isfinite(rr)):
            base.append(float(np.prod(1.0 + rr) - 1.0) > 0)
    return hit, (float(np.mean(base)) if base else float("nan")), len(base)


def union_book(cal: Cal, books: dict, all_events: dict, rng: tuple[str, str],
               cost: float = COST) -> tuple[dict, dict, list[int]]:
    """Hold SPY in the union of both arms' counted windows whose first and last
    sessions fall in `rng`; one round-trip cost per contiguous holding, spread
    over its days. Out-of-window days: sessions in `rng` in no window of either
    arm."""
    a, b = rng
    days = sorted({d for bk in books.values() for e in bk.events
                   if a <= cal.dates[e.first] and cal.dates[e.last] <= b for d in e.days})
    runs, cur = [], []
    for d in days:
        if cur and d != cur[-1] + 1:
            runs.append(cur)
            cur = []
        cur.append(d)
    if cur:
        runs.append(cur)
    iv = {d: float(cal.r[d]) - cost / len(run) for run in runs for d in run}
    window_any = {d for evs in all_events.values() for e in evs for d in e.days}
    ov = {i: float(cal.r[i]) for i, d in enumerate(cal.dates)
          if a <= d <= b and i not in window_any and math.isfinite(cal.r[i])}
    return iv, ov, [run[-1] for run in runs]


# ════════════════════════════════════════════════════════════════════════════
# Inputs
# ════════════════════════════════════════════════════════════════════════════

def check_era() -> None:
    requested = era_mod.requested_era()
    if requested != era_mod.CURRENT:
        raise Refused(era_mod.EXIT_THIN_ERA,
                      f"calendar_drift reads yfinance market closes, which carry no era; era "
                      f"{requested!r} does not apply — run it without --era. Exit 2.")


def ge_problems(spy: list[tuple], registered: str) -> list[str]:
    """GE on the built calendar (sessions with an Adj Close). The last session
    must fall strictly AFTER the registration date: the final session is always
    an open TOM event, so the graded sets are final only once a later session
    exists. Duplicate dates are refused."""
    if not spy:
        return ["SPY.csv is empty"]
    out = []
    dup = sorted({a[0] for a, b in zip(spy, spy[1:]) if a[0] == b[0]})
    if dup:
        out.append(f"SPY has duplicate dates: {', '.join(dup[:5])}"
                   f"{' ...' if len(dup) > 5 else ''}")
    cal = build_cal(spy)
    if not cal.dates:
        return out + ["SPY has no row with an Adj Close"]
    if cal.dates[0] > SPY_START_LATEST:
        out.append(f"SPY starts {cal.dates[0]}, after {SPY_START_LATEST}")
    if cal.dates[-1] <= registered:
        out.append(f"SPY's last session with an Adj Close is {cal.dates[-1]}; GE needs at "
                   f"least one session after the registration date {registered}")
    return out


def load_spy(refresh: bool, path: Path = SPY_CSV) -> list[tuple]:
    if refresh:
        try:
            fetch_spy(path)
        except Refused:
            raise
        except Exception as exc:  # network, yfinance schema
            raise Refused(EXIT_INPUT, f"GE: fetching SPY failed ({exc}). Exit 3.")
    if not path.exists():
        raise Refused(EXIT_INPUT, f"GE: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} "
                                  "is missing; pass --refresh to fetch it. Exit 3.")
    return read_spy(path)


def _inventory(path: Path) -> str:
    with open(path, newline="") as fh:
        n = max(0, sum(1 for _ in fh) - 1)
    mtime = datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    rel = Path(path).resolve()
    rel = rel.relative_to(ROOT) if rel.is_relative_to(ROOT) else rel
    return f"  {n:>6,} lines  {mtime}  {rel}"


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
# ════════════════════════════════════════════════════════════════════════════

def section(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def bp(x: float) -> str:
    return "—" if x is None or not math.isfinite(x) else f"{x * 1e4:+.2f} bps"


def pct(x: float | None, nd: int = 2) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{100 * x:.{nd}f}%"


def res_txt(r: Result) -> str:
    if not math.isfinite(r.point):
        return "Delta —"
    ci = f"[{bp(r.lo)}, {bp(r.hi)}]" if r.finite else "[—]"
    return f"Delta {bp(r.point)} per day  CI95 {ci}  p {r.p:.4f}"


# ════════════════════════════════════════════════════════════════════════════
# The run
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class ArmRead:
    book: Book
    res: Result
    powered: bool
    n_events: int
    n_years: int
    gl_ok: bool = False
    gl_est: dict = field(default_factory=dict)
    gp_ok: bool = False
    gp_res: Result | None = None
    gp_dropped: int = 0
    gv_ok: bool = False
    gv_res: Result | None = None
    gv_dropped: int = 0
    ex_other: Result | None = None     # printed only, never graded


def measure_ex_other(book: Book, other_days: set) -> Result:
    """PRINTED ONLY, never graded: the arm's Delta with the other arm's window
    days removed from the out-of-window reference set; same cycles and bootstrap."""
    ref = {d: v for d, v in book.out_vals.items() if d not in other_days}
    return measure(book.in_vals, ref, [e.last for e in book.events])


def read_arm(cal: Cal, book: Book, other_days: set, own_days: set, tom_days: set,
             decision_idx: set) -> ArmRead:
    res = measure_book(book)
    powered, n_ev, n_yr = gn(book, cal)
    a = ArmRead(book, res, powered, n_ev, n_yr)
    a.gl_ok, a.gl_est = gl(book, cal)
    pin, ref, pb, a.gp_dropped = placebo(book, other_days, own_days)
    a.gp_res = measure(pin, ref, pb)
    a.gp_ok = a.gp_res.finite and a.gp_res.lo <= 0 <= a.gp_res.hi
    iv, ov, vb, a.gv_dropped = ex_overlap(book, tom_days, decision_idx)
    a.gv_res = measure(iv, ov, vb)
    a.gv_ok = math.isfinite(a.gv_res.point) and a.gv_res.point > 0
    a.ex_other = measure_ex_other(book, other_days)
    return a


def print_arm(arm: str, pop: str, a: ArmRead, cal: Cal, p_adj: float | None) -> None:
    bk = a.book
    head = "PRIOR (pre-publication, not graded)" if pop == "PRIOR" else pop
    print(f"\n  {arm} {head}")
    print(f"    sessions {bk.census['range'][0]} -> {bk.census['range'][1]}; events counted "
          f"{a.n_events} over {a.n_years} years; whole-calendar events in no population: open "
          f"{bk.census['open']}, undefined {bk.census['undefined']}, gap {bk.census['gap']}")
    print(f"    in-window days {a.res.n_in}, out-of-window days {a.res.n_out}, cycles {a.res.cycles}")
    holm_txt = f", Holm {p_adj:.4f}" if p_adj is not None else ""
    print(f"    {res_txt(a.res)}{holm_txt}")
    if pop != "PRIOR":
        floor = MIN_YEARS[pop]
        print(f"    GN: {a.n_events} events (floor {MIN_EVENTS}) over {a.n_years} years "
              f"(floor {floor}) — {'pass' if a.powered else 'FAIL'}")
    neg = [y for y, v in a.gl_est.items() if not (math.isfinite(v) and v > 0)]
    lo_y = min(a.gl_est.items(), key=lambda kv: kv[1] if math.isfinite(kv[1]) else -1e9) \
        if a.gl_est else ("—", float("nan"))
    print(f"    GL leave-one-year-out: {len(a.gl_est)} estimates, lowest {bp(lo_y[1])} "
          f"(without {lo_y[0]}); years whose removal leaves it at or below zero: "
          f"{', '.join(neg) if neg else 'none'} — "
          f"{'pass' if a.gl_ok else 'FAIL'}")
    print(f"    GP placebo ({PLACEBO_SHIFT[arm]:+d} sessions): {res_txt(a.gp_res)}; "
          f"{a.gp_res.n_in} placebo days, {a.gp_dropped} dropped as other-arm window days — "
          f"{'pass' if a.gp_ok else 'FAIL'} (passes when the CI contains 0)")
    print(f"    GV ex-overlap: {a.gv_dropped} overlapping events removed; {res_txt(a.gv_res)} — "
          f"{'pass' if a.gv_ok else 'FAIL'} (passes when Delta stays above 0)")


def print_printed_only(arm: str, pop: str, a: ArmRead, cal: Cal) -> None:
    bk = a.book
    head = "PRIOR (pre-publication, not graded)" if pop == "PRIOR" else pop
    n_win = WINDOW_N[arm]
    gross_in = {d: v + COST / n_win for d, v in bk.in_vals.items()}
    gross = delta(gross_in, bk.out_vals)
    st = strategy_lines(bk, cal)
    hit, base, nb = hit_lines(bk, cal)
    split = year_split(bk, cal)
    yd = {y: delta(i, o) for y, (i, o) in split.items()}
    pos_years = sum(1 for v in yd.values() if math.isfinite(v) and v > 0)
    print(f"\n  {arm} {head}")
    print(f"    GROSS      Delta {bp(gross)} per day (no cost)")
    print(f"    BREAKEVEN  round-trip cost {bp(n_win * gross)} (Delta reaches zero)")
    print(f"    ANNUAL     {pct(st['annual'])} a year, in-window only, cash at zero, net "
          f"({st['n']} sessions)")
    print(f"    SHARPE     {st['sharpe']:.3f}" if math.isfinite(st["sharpe"]) else "    SHARPE     —")
    if st["capture"] is None:
        print("    CAPTURE    n/a (SPY's summed log return over these sessions is zero or less)")
    else:
        print(f"    CAPTURE    {pct(st['capture'], 1)} of SPY's summed log return, same sessions")
    print(f"    HIT        {pct(hit, 1)} of {len(bk.events)} events net positive (net of cost); SPY "
          f"{pct(base, 1)} of {nb} {n_win}-session windows gross positive (base share is gross)")
    print(f"    YEARS      Delta above zero in {pos_years} of {len(yd)} years")
    print("      per-year deltas are net of cost; with no calendar effect about 0.45 of years "
          "print above 0, not 0.50 (pre-run simulation)")
    for y, v in yd.items():
        print(f"      {y}  {bp(v)}")
    print(f"    EX-OVERLAP {res_txt(a.gv_res)} ({a.gv_dropped} events removed)")
    print(f"    EX-OTHER-ARM (printed only, not graded) {res_txt(a.ex_other)}; the other arm's "
          f"window days removed from the out-of-window reference set")


def run(refresh: bool = False, spy_path: Path = SPY_CSV, history_path: Path = HISTORY_YML,
        macro_path: Path = MACRO_YML, registered: str | None = None,
        check_git: bool = True) -> int:
    registered = registered or REGISTERED
    check_era()
    spy = load_spy(refresh, spy_path)

    print("calendar_drift — do the pre-FOMC drift and the turn of the month still pay on SPY "
          "after publication?")
    print(f"registration: {REGISTRATION} (registered {registered})")
    print("era: current (inputs are unversioned market data)")
    dirty = "dirty" if _git("status", "--porcelain") else "clean"
    print(f"git: {_git('rev-parse', '--short', 'HEAD')} "
          f"({_git('rev-parse', '--abbrev-ref', 'HEAD')}, working tree {dirty})")
    print("inputs read:")
    for p in (spy_path, history_path, macro_path):
        if Path(p).exists():
            print(_inventory(p))
    blob = _git("rev-parse", f"HEAD:{HISTORY_REL}") if check_git else "(not checked)"
    print(f"{HISTORY_REL} git blob: {blob}")
    print("SEAL: not applied — no flow signal, play or backtest row is read")
    print(f"cost {COST * 1e4:.0f} bps round trip (2 a side), charged COST/n per window day; "
          f"cycle bootstrap {BOOT_N} draws, seed {SEED}")
    print("transcription fixes to config/fomc-history.yml after the first report: none")

    section("GATES — refusals (GE, GB, GF)")
    probs = ge_problems(spy, registered)
    if probs:
        for line in probs:
            print(f"  GE: {line}")
        raise Refused(EXIT_INPUT, "GE: the SPY input check failed. Exit 3.")
    cal = build_cal(spy)
    print(f"  GE: SPY {len(spy)} rows, {cal.dates[0]} -> {cal.dates[-1]} (last session with an "
          f"Adj Close, after {registered}) — pass")
    rp = ratio_problems(spy)
    if rp:
        for line in rp[:10]:
            print(f"    {line}")
        raise Refused(EXIT_INPUT, f"GB: {len(rp)} close/adj steps outside the dividend "
                                  "pattern. Exit 3.")
    print("  GB: close/adj_close ratio never steps like a split — pass")
    fomc = load_fomc(history_path, macro_path)
    gfp = (gf_git_problems() if check_git else []) + gf_calendar_problems(fomc) \
        + gf_session_problems(fomc, cal)
    if gfp:
        for line in gfp[:20]:
            print(f"  GF: {line}")
        raise Refused(EXIT_INPUT, "GF: the FOMC calendar check failed. Exit 3.")
    per_year = {}
    for d in fomc.history:
        per_year[d[:4]] = per_year.get(d[:4], 0) + 1
    print(f"  GF: {len(fomc.history)} history decision days ({fomc.history[0]} -> "
          f"{fomc.history[-1]}), {len(fomc.macro)} macro-events.yml decision days "
          f"({min(fomc.macro)} -> {max(fomc.macro)}); join gap "
          f"{(date.fromisoformat(min(fomc.macro)) - date.fromisoformat(fomc.history[-1])).days} days; "
          f"exceptions {fomc.exceptions or 'none'}; every decision day to {cal.dates[-1]} is a "
          f"session — pass")
    print("  GX: window membership reads only the session calendar and the FOMC dates "
          "(pinned by tests/test_calendar_drift.py)")
    print(f"  population: SPY sessions {cal.dates[0]} -> {cal.dates[-1]} ({cal.n}); PF forward "
          f"horizon {fomc.horizon} (macro-events.yml verified_through.fomc)")

    events = {"PF": pf_events(cal.dates, fomc.decisions), "TOM": tom_events(cal.dates)}
    win_days = {arm: {d for e in evs for d in e.days} for arm, evs in events.items()}
    decision_idx = {e.days[0] for e in events["PF"]}
    horizon = {"PF": fomc.horizon, "TOM": None}
    reads: dict = {pop: {} for pop in POPS}
    for pop in POPS:
        for arm in ARMS:
            bk = build_book(cal, arm, pop, events[arm], registered, horizon[arm])
            other = win_days["TOM" if arm == "PF" else "PF"]
            reads[pop][arm] = read_arm(cal, bk, other, win_days[arm], win_days["TOM"], decision_idx)

    words = {}
    for pop in ("GRADED", "FORWARD"):
        pv = {arm: (reads[pop][arm].res.p if reads[pop][arm].powered else 1.0) for arm in ARMS}
        adj = holm(pv)
        words[pop] = {}
        for arm in ARMS:
            a = reads[pop][arm]
            words[pop][arm] = (verdict(a.res, a.powered, adj[arm][0], a.gl_ok, a.gp_ok, a.gv_ok,
                                       forward=(pop == "FORWARD")), adj[arm][0])

    section("GRADED — events after publication, through the registration date")
    for arm in ARMS:
        print_arm(arm, "GRADED", reads["GRADED"][arm], cal, words["GRADED"][arm][1])
    print("\n  Holm family m = 2 (PF, TOM); an UNDERPOWERED arm enters with p = 1.")

    section("PRIOR — the published years (printed only, never graded)")
    for arm in ARMS:
        print_arm(arm, "PRIOR", reads["PRIOR"][arm], cal, None)

    section("PRINTED ONLY — no verdict")
    for pop in ("GRADED", "PRIOR"):
        for arm in ARMS:
            print_printed_only(arm, pop, reads[pop][arm], cal)
    for pop in ("GRADED", "PRIOR"):
        rng = UNION_RANGES[pop]
        iv, ov, ub = union_book(cal, {arm: reads[pop][arm].book for arm in ARMS}, events, rng)
        ures = measure(iv, ov, ub)
        ubk = Book("UNION", pop, [], iv, ov, {"range": rng})
        st = strategy_lines(ubk, cal)
        head = "PRIOR (pre-publication, not graded)" if pop == "PRIOR" else pop
        print(f"\n  UNION {head}: both arms' windows {rng[0]} -> {rng[1]}, one cost per "
              f"contiguous holding ({len(ub)} holdings)")
        print(f"    {res_txt(ures)}; ANNUAL {pct(st['annual'])}, SHARPE "
              f"{st['sharpe']:.3f}" if math.isfinite(st["sharpe"]) else f"    {res_txt(ures)}")

    section("FORWARD — events after the registration date")
    for arm in ARMS:
        a = reads["FORWARD"][arm]
        bk = a.book
        print(f"  {arm}: sessions {bk.census['range'][0]} -> {bk.census['range'][1]}; events "
              f"counted {a.n_events} over {a.n_years} years (floor {MIN_EVENTS} over "
              f"{MIN_YEARS['FORWARD']}); open {bk.census['open']}; in-window days {a.res.n_in}, "
              f"out-of-window days {a.res.n_out}")
        if a.powered:
            print(f"    {res_txt(a.res)}, Holm {words['FORWARD'][arm][1]:.4f}; GL "
                  f"{'pass' if a.gl_ok else 'FAIL'}, GP {'pass' if a.gp_ok else 'FAIL'}, GV "
                  f"{'pass' if a.gv_ok else 'FAIL'}")
        print(f"    forward: {words['FORWARD'][arm][0]}")

    section("VERDICT")
    g = reads["GRADED"]
    print(f"  GRADED: PF {g['PF'].n_events} decision days from {POP_RANGES['PF']['GRADED'][0]}, "
          f"TOM {g['TOM'].n_events} month turns from {POP_RANGES['TOM']['GRADED'][0]}, through "
          f"{registered}; SPY sessions to {cal.dates[-1]}; {BOOT_N} cycle draws, seed {SEED}")
    for arm in ARMS:
        w = words["GRADED"][arm][0]
        if w == FRAGILE:
            a = g[arm]
            failed = [n for n, ok in (("GL", a.gl_ok), ("GP", a.gp_ok), ("GV", a.gv_ok)) if not ok]
            print(f"  {arm} FRAGILE: failed {', '.join(failed)}")
    for pop in ("GRADED", "FORWARD"):
        for arm in ARMS:
            if words[pop][arm][0] == REVERSED:
                print(f"  {arm} {pop} REVERSED: read with the GROSS line: with no calendar effect "
                      f"the 2 bp cost alone makes REVERSED fire in about 3-4% of simulated paths, "
                      f"and the other arm's window days sit in this arm's reference set")
    print()
    for arm in ARMS:
        print(f"  >>> calendar_drift {arm} ({BANNER[arm]}): {words['GRADED'][arm][0]} <<<")
    print(f"  >>> calendar_drift FORWARD (events after the registration date): "
          f"PF {words['FORWARD']['PF'][0]} TOM {words['FORWARD']['TOM'][0]} <<<")
    print()
    print("  STILL-PAYS needs the CI wholly above 0, a Holm-adjusted p below 0.05, and GL, GP")
    print("  and GV all passing. PRIOR lines are never graded.")
    print("  Nothing ships from this study (calendar_drift.md).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="refetch SPY from yfinance into backtests/calendar_drift/ before the run")
    args = ap.parse_args(argv)
    try:
        return run(refresh=args.refresh)
    except Refused as exc:
        print(f"REFUSED — {exc.message}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
