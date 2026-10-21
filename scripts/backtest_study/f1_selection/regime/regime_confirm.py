"""regime_confirm — does a confirmed mech BEAR flip predict a real sell-off better than the flip alone?

REGISTERED 2026-10-21, accepted by default the same day:
research/pre-registrations/f1_selection/regime/regime_confirm.md. Every floor,
constant and verdict word below is that file's. Read it before changing
anything here.

WHY IT EXISTS
-------------
A 2026-10-21 exploratory pass on SPY 1993-2026 found that most mech BEAR flips
fade within days, and that flips which persist while other stress signs agree
were followed by a 10% sell-off more often. That pass chose the rule, so SPY
1993-2026 (`RC-IS`) is spent: it prints, labelled post hoc, and is never graded.
The rule is graded on ^GSPC before SPY existed (`RC-H1`, the clean holdout), on
QQQ and IWM (`RC-H2`, a correlated replication) and on flips after 2026-10-21
(`RC-FWD`, forward).

WHAT IT COMPUTES
----------------
Labels. BEAR is `lib/mech_regime.py::compute_mech_table` on the flip ticker's
own unadjusted closes (fed as the `spy_close` column of a temporary CSV). Never
re-implemented, and `lib/regime_watch.py` is not imported.

Flip. The first BEAR session after 20 labelled sessions with no BEAR. A session
with no label breaks the look-back. Streak: consecutive BEAR sessions from the
flip, the flip counted as day 1. Decision date: the flip for flip rules, the
k-th BEAR session for a rule that waits for a streak of k.

Real shift. The lowest close over the 60 sessions after the decision close is
10% or more below it, on the flip ticker's own closes. Fewer than 60 sessions
after the decision date: censored, excluded, counted. On `RC-H1` the window
must also close on or before 1993-01-28.

Conditions, read at the decision close. `C-200` SPY below its 200-day SMA;
`C-CR` the HYG/IEF ratio of Adj Close down more than 1% over 20 sessions;
`C-IWM` IWM below its 200-day SMA; `C-VIX` VIX close at or above 20. A
condition with no data counts as not met. Own 200-day: the flip ticker's own.
Adj Close carries later dividends as one factor on every earlier close, so the
factor cancels in the ratio's 20-session change and `C-CR` stays causal.

Arms: RC0 every flip (control), RC1 streak 3 + 2 of 4, RC-200 streak 3 + own
200-day, RC-P streak 3, RC-C 2 of 4 at the flip. Cuts: RC-10 streak 10, RC-TS
RC0 split by VIX/VIX3M above 1.

Statistic. Arm real-shift rate minus RC0's, same scope. Events chained into
clusters (decision dates within 60 sessions on the NYSE calendar). 95%
percentile bootstrap over clusters, both rates from one draw, 10,000 draws,
seed 20260811.

Gates. RC-G0 data (exit 2), RC-G1 causality (asserted per event), RC-G2 floors.

Build rulings (tagged `Resolved at build (2026-10-21)` in the registration):
session counts for clusters use the ^GSPC (NYSE) calendar; a comparison's
clusters chain the arm's and RC0's events together, and the floor counts the
clusters holding an arm event; RC-G0's gap is missing ^GSPC sessions between
closes (weekdays for ^GSPC itself) over each series' whole fetched span; a
condition reads the last close on or before the decision date and is missing
only with no such close or too short a runway; BH p-values are two-sided from
the same bootstrap draws, an UNDERPOWERED member at p = 1; recall counts a
real-shift flip as caught when the arm acts on that flip; a flip still BEAR at
the data end, short of k, is pending and counted, not an event.

DATA
----
yfinance, auto_adjust=False, cached in `backtests/regime_confirm/<name>.csv`
(date, close, adj_close). A missing file is fetched; `--refresh` refetches all.
A forward read needs `--refresh`, or the cache ends where it was last fetched.
Today's bar is never fetched (yfinance's `end` is exclusive and set to today),
so every close is a finished session.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run regime_confirm
    python -m scripts.backtest_study run regime_confirm -- --refresh
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import compute_mech_table  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/regime_confirm.md"
ACCEPTED = "2026-10-21"

# --- registered constants (the registration, not defaults) -------------------
QUIET = 20                 # sessions with no BEAR before a flip
STREAK = 3                 # RC1 / RC-200 / RC-P wait
STREAK_LONG = 10           # RC-10, descriptive
WINDOW = 60                # outcome window, sessions
DROP = 0.10                # real shift: lowest close >= 10% below the decision close
CLUSTER_GAP = 60           # sessions between decision dates that chain a cluster
SMA_LONG = 200
CREDIT_WINDOW = 20
CREDIT_FLOOR = -0.01
VIX_LEVEL = 20.0
CONFIRM_MIN = 2            # "2 or more of the four"
MIN_EVENTS = 20            # per arm per scope, uncensored
MIN_CLUSTERS = 12
MIN_CONTROL = 60           # RC0 uncensored events
BOOT_N = 10_000
SEED = 20260811
BH_Q = 0.05
MAX_GAP_SESSIONS = 5       # RC-G0

RC_IS = ("1993-01-29", "2026-10-21")
RC_H1 = ("1950-01-03", "1992-12-31")
RC_H1_WINDOW_END = "1993-01-28"   # the day before SPY's first close
RC_H2_END = "2026-10-21"
FWD_AFTER = "2026-10-21"          # RC-FWD: flip date strictly after
EXCLUDED_CASE = ("SPY", "2026-10-19")

CACHE_DIR = ROOT / "backtests" / "regime_confirm"
MECH_TABLE_CSV = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"

# name -> (yfinance symbol, first fetch date)
SERIES = {
    "GSPC": ("^GSPC", "1950-01-01"),
    "SPY": ("SPY", "1993-01-01"),
    "QQQ": ("QQQ", "1999-01-01"),
    "IWM": ("IWM", "2000-01-01"),
    "HYG": ("HYG", "2007-01-01"),
    "IEF": ("IEF", "2002-01-01"),
    "VIX": ("^VIX", "1990-01-01"),
    "VIX3M": ("^VIX3M", "2006-01-01"),
}
CONDITIONS = ("C-200", "C-CR", "C-IWM", "C-VIX")

# RC-G0 refusal; the runner promotes the report as a designed refusal.
DESIGNED_REFUSAL_EXIT_CODES = {2}


class GateRefusal(Exception):
    """RC-G0 failed: the run refuses with exit 2."""


# ════════════════════════════════════════════════════════════════════════════
# Data
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Series:
    name: str
    dates: np.ndarray              # str 'YYYY-MM-DD', ascending
    close: np.ndarray
    adj: np.ndarray

    def asof(self, d: str) -> int | None:
        """Index of the last row dated on or before `d`, or None."""
        i = int(np.searchsorted(self.dates, d, side="right")) - 1
        return i if i >= 0 else None

    def index_of(self, d: str) -> int | None:
        i = int(np.searchsorted(self.dates, d))
        return i if i < len(self.dates) and self.dates[i] == d else None


def series_from_rows(name: str, rows: list[tuple[str, float, float]]) -> Series:
    rows = sorted(r for r in rows if r[1] is not None and math.isfinite(r[1]))
    return Series(name, np.array([r[0] for r in rows]),
                  np.array([r[1] for r in rows], dtype=float),
                  np.array([r[2] if r[2] is not None else np.nan for r in rows], dtype=float))


def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.csv"


def fetch_series(name: str, end: str | None = None) -> Path:
    """yfinance -> `backtests/regime_confirm/<name>.csv`. `end` is exclusive."""
    import pandas as pd
    import yfinance as yf
    sym, start = SERIES[name]
    end = end or date.today().isoformat()
    df = yf.download(sym, start=start, end=end, auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise GateRefusal(f"RC-G0: yfinance returned no rows for {sym}")

    def col(c):
        x = df[c]
        return x.iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else x

    close, adj = col("Close"), col("Adj Close")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(name)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "close", "adj_close"])
        for d, c, a in zip(close.index, close.values, adj.values):
            if c == c:
                w.writerow([pd.Timestamp(d).strftime("%Y-%m-%d"), repr(float(c)),
                            repr(float(a)) if a == a else ""])
    print(f"fetched {sym} -> {path.relative_to(ROOT)} ({len(close)} rows)")
    return path


def load_series(name: str) -> Series:
    rows = []
    with _cache_path(name).open(newline="") as fh:
        for r in csv.DictReader(fh):
            c = float(r["close"]) if r["close"] else None
            a = float(r["adj_close"]) if r["adj_close"] else None
            rows.append((r["date"], c, a))
    return series_from_rows(name, rows)


def load_all(refresh: bool) -> dict[str, Series]:
    out = {}
    for name in SERIES:
        if refresh or not _cache_path(name).exists():
            fetch_series(name)
        out[name] = load_series(name)
    return out


# ════════════════════════════════════════════════════════════════════════════
# Labels, flips, streaks
# ════════════════════════════════════════════════════════════════════════════

def mech_directions(s: Series) -> list[str | None]:
    """`compute_mech_table`'s direction for each of `s`'s sessions, aligned."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "spy_close", "vix_close"])
        for d, c in zip(s.dates, s.close):
            w.writerow([d, repr(float(c)), ""])
        tmp = fh.name
    try:
        table = compute_mech_table(tmp)
    finally:
        Path(tmp).unlink(missing_ok=True)
    by = {r["date"]: r["mech_direction"] for r in table}
    return [by.get(d) for d in s.dates]


def find_flips(dirs: list[str | None], quiet: int = QUIET) -> list[int]:
    """Indices of BEAR sessions preceded by `quiet` labelled, non-BEAR sessions."""
    out = []
    for i in range(quiet, len(dirs)):
        if dirs[i] != "BEAR":
            continue
        prior = dirs[i - quiet:i]
        if all(p is not None and p != "BEAR" for p in prior):
            out.append(i)
    return out


def streak_from(dirs: list[str | None], i: int) -> tuple[int, bool]:
    """(consecutive BEAR sessions from `i`, the flip counted as day 1;
    True when the streak has ended inside the data, False when the data ends
    while it is still BEAR)."""
    n = 0
    j = i
    while j < len(dirs) and dirs[j] == "BEAR":
        n += 1
        j += 1
    return n, j < len(dirs)


PENDING = "pending"


def decision_index(dirs, flip_i: int, k: int):
    """Decision index for a rule that waits for a streak of k (k=1: the flip).

    None when the streak ended short of k; PENDING when the data ends first.
    """
    if k <= 1:
        return flip_i
    n, ended = streak_from(dirs, flip_i)
    if n >= k:
        return flip_i + k - 1
    return None if ended else PENDING


# ════════════════════════════════════════════════════════════════════════════
# Outcome and conditions
# ════════════════════════════════════════════════════════════════════════════

def outcome(s: Series, d_i: int, window: int = WINDOW, drop: float = DROP,
            window_end_limit: str | None = None) -> dict | None:
    """Real shift and the secondaries from the decision close; None = censored.

    RC-G1: every close used is strictly after the decision date.
    """
    if d_i + window >= len(s.dates):
        return None
    if window_end_limit is not None and s.dates[d_i + window] > window_end_limit:
        return None
    base = s.close[d_i]
    path = s.close[d_i + 1:d_i + window + 1]
    assert all(dd > s.dates[d_i] for dd in s.dates[d_i + 1:d_i + window + 1]), "RC-G1"
    low = float(path.min()) / base - 1.0
    return {"real": bool(path.min() <= base * (1.0 - drop)), "maxdd": low,
            "ret20": float(s.close[d_i + 20]) / base - 1.0,
            "ret60": float(s.close[d_i + window]) / base - 1.0}


def below_sma(s: Series | None, d: str, window: int = SMA_LONG) -> bool | None:
    """Close below its `window`-day SMA as of `d`; None = no data (not met)."""
    if s is None:
        return None
    i = s.asof(d)
    if i is None or i + 1 < window:
        return None
    assert s.dates[i] <= d, "RC-G1"
    return bool(s.close[i] < s.close[i + 1 - window:i + 1].mean())


def credit_weak(hyg: Series | None, ief: Series | None, d: str) -> bool | None:
    """HYG/IEF Adj Close ratio, 20-session change below -1%, as of `d`."""
    if hyg is None or ief is None:
        return None
    common = np.intersect1d(hyg.dates[hyg.dates <= d], ief.dates[ief.dates <= d])
    if len(common) <= CREDIT_WINDOW:
        return None
    a, b = common[-1], common[-1 - CREDIT_WINDOW]
    r_now = hyg.adj[hyg.index_of(a)] / ief.adj[ief.index_of(a)]
    r_then = hyg.adj[hyg.index_of(b)] / ief.adj[ief.index_of(b)]
    if not (math.isfinite(r_now) and math.isfinite(r_then)):
        return None
    return bool(r_now / r_then - 1.0 < CREDIT_FLOOR)


def vix_high(vix: Series | None, d: str) -> bool | None:
    if vix is None:
        return None
    i = vix.asof(d)
    if i is None:
        return None
    return bool(vix.close[i] >= VIX_LEVEL)


def vix_term_inverted(vix: Series | None, vix3m: Series | None, d: str) -> bool | None:
    if vix is None or vix3m is None:
        return None
    i, j = vix.asof(d), vix3m.asof(d)
    if i is None or j is None:
        return None
    return bool(vix.close[i] / vix3m.close[j] > 1.0)


def conditions_at(data: dict[str, Series], d: str) -> dict[str, bool | None]:
    return {"C-200": below_sma(data.get("SPY"), d),
            "C-CR": credit_weak(data.get("HYG"), data.get("IEF"), d),
            "C-IWM": below_sma(data.get("IWM"), d),
            "C-VIX": vix_high(data.get("VIX"), d)}


def n_met(conds: dict[str, bool | None]) -> int:
    """A missing condition (None) counts as not met."""
    return sum(1 for v in conds.values() if v is True)


# ════════════════════════════════════════════════════════════════════════════
# Events
# ════════════════════════════════════════════════════════════════════════════

ARMS = ("RC0", "RC1", "RC-200", "RC-P", "RC-C", "RC-10")


@dataclass
class Event:
    ticker: str
    flip_date: str
    decision_date: str
    lag: float                       # decision close / flip close - 1
    out: dict | None                 # None = censored
    conds: dict = field(default_factory=dict)

    @property
    def censored(self) -> bool:
        return self.out is None


def arm_rule(arm: str):
    """(streak k, condition test on (conds, own200)) for an arm."""
    return {
        "RC0": (1, lambda c, o: True),
        "RC1": (STREAK, lambda c, o: n_met(c) >= CONFIRM_MIN),
        "RC-200": (STREAK, lambda c, o: o is True),
        "RC-P": (STREAK, lambda c, o: True),
        "RC-C": (1, lambda c, o: n_met(c) >= CONFIRM_MIN),
        "RC-10": (STREAK_LONG, lambda c, o: True),
    }[arm]


def build_events(ticker: str, s: Series, dirs, flips: list[int], data: dict[str, Series],
                 window_end_limit: str | None = None) -> tuple[dict[str, list[Event]], dict]:
    """Every arm's events for one ticker's flips, plus census counters."""
    ev = {a: [] for a in ARMS}
    census = {a: {"pending": 0, "missing": {c: 0 for c in CONDITIONS}} for a in ARMS}
    for f in flips:
        for a in ARMS:
            k, test = arm_rule(a)
            d_i = decision_index(dirs, f, k)
            if d_i is None:
                continue
            if d_i == PENDING:
                census[a]["pending"] += 1
                continue
            d = s.dates[d_i]
            conds = conditions_at(data, d)
            own = below_sma(s, d)
            if not test(conds, own):
                continue
            for c, v in conds.items():
                if v is None:
                    census[a]["missing"][c] += 1
            ev[a].append(Event(ticker, s.dates[f], d, float(s.close[d_i] / s.close[f] - 1.0),
                               outcome(s, d_i, window_end_limit=window_end_limit),
                               dict(conds, own200=own,
                                    ts=vix_term_inverted(data.get("VIX"), data.get("VIX3M"),
                                                         s.dates[f]))))
    return ev, census


# ════════════════════════════════════════════════════════════════════════════
# Clusters and bootstrap
# ════════════════════════════════════════════════════════════════════════════

def session_pos(calendar: np.ndarray, d: str) -> int:
    return int(np.searchsorted(calendar, d))


def chain_clusters(positions: list[int], gap: int = CLUSTER_GAP) -> list[int]:
    """Cluster id per position (input order): sorted, a new cluster when the
    next position is more than `gap` sessions after the previous one."""
    order = sorted(range(len(positions)), key=lambda i: positions[i])
    ids = [0] * len(positions)
    cid, prev = -1, None
    for i in order:
        if prev is None or positions[i] - prev > gap:
            cid += 1
        ids[i] = cid
        prev = positions[i]
    return ids


def joint_clusters(arm_ev: list[Event], ctrl_ev: list[Event], calendar) -> tuple[list[int], list[int]]:
    """Cluster ids for the arm's and the control's uncensored events, chained
    together so both rates resample from the same draw."""
    pos = [session_pos(calendar, e.decision_date) for e in arm_ev + ctrl_ev]
    ids = chain_clusters(pos)
    return ids[:len(arm_ev)], ids[len(arm_ev):]


def n_clusters(events: list[Event], calendar) -> int:
    """Clusters among one set of events alone."""
    if not events:
        return 0
    return len(set(chain_clusters([session_pos(calendar, e.decision_date) for e in events])))


def rate(events: list[Event]) -> float:
    return sum(e.out["real"] for e in events) / len(events) if events else float("nan")


def boot(arm_ev: list[Event], ctrl_ev: list[Event], calendar, n: int = BOOT_N,
         seed: int = SEED) -> dict:
    """Difference of real-shift rates (arm - control) with a cluster bootstrap,
    plus medians of the arm's secondaries on the same draws."""
    res = {"diff": rate(arm_ev) - rate(ctrl_ev), "lo": float("nan"), "hi": float("nan"),
           "p": float("nan"), "medians": {}}
    if not arm_ev or not ctrl_ev:
        return res
    ia, ic = joint_clusters(arm_ev, ctrl_ev, calendar)
    k = max(ia + ic) + 1
    a_real, a_n, c_real, c_n = (np.zeros(k) for _ in range(4))
    members: list[list[int]] = [[] for _ in range(k)]
    for j, (e, cid) in enumerate(zip(arm_ev, ia)):
        a_real[cid] += e.out["real"]
        a_n[cid] += 1
        members[cid].append(j)
    for e, cid in zip(ctrl_ev, ic):
        c_real[cid] += e.out["real"]
        c_n[cid] += 1
    idx = np.random.default_rng(seed).integers(0, k, (n, k))
    an, cn = a_n[idx].sum(1), c_n[idx].sum(1)
    ok = (an > 0) & (cn > 0)
    d = a_real[idx].sum(1)[ok] / an[ok] - c_real[idx].sum(1)[ok] / cn[ok]
    if len(d):
        res["lo"], res["hi"] = (float(x) for x in np.percentile(d, [2.5, 97.5]))
        res["p"] = float(min(1.0, 2 * min(np.mean(d <= 0), np.mean(d >= 0))))
    metrics = {"ret20": np.array([e.out["ret20"] for e in arm_ev]),
               "ret60": np.array([e.out["ret60"] for e in arm_ev]),
               "maxdd": np.array([e.out["maxdd"] for e in arm_ev]),
               "lag": np.array([e.lag for e in arm_ev])}
    mem = [np.array(m, dtype=int) for m in members]
    draws = {m: [] for m in metrics}
    for row in idx:
        sel = np.concatenate([mem[c] for c in row])
        if len(sel) == 0:
            continue
        for m, v in metrics.items():
            draws[m].append(np.median(v[sel]))
    for m, v in metrics.items():
        lo, hi = (np.percentile(draws[m], [2.5, 97.5]) if draws[m] else (np.nan, np.nan))
        res["medians"][m] = (float(np.median(v)), float(lo), float(hi))
    return res


def token(n_ev: int, n_cl: int, n_ctrl: int, lo: float, hi: float) -> str:
    """Per-arm, per-scope verdict word."""
    if n_ev < MIN_EVENTS or n_cl < MIN_CLUSTERS or n_ctrl < MIN_CONTROL:
        return "UNDERPOWERED"
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "UNDERPOWERED"
    if lo > 0:
        return "SUPPORTED"
    if hi < 0:
        return "CONTRARY"
    return "NULL"


def retro_verdict(rc1_h2: str, rc200_h1: str) -> str:
    pair = (rc1_h2, rc200_h1)
    if "CONTRARY" in pair:
        return "RETRO-CONTRARY"
    if all(t == "SUPPORTED" for t in pair):
        return "RETRO-SUPPORTED"
    if "UNDERPOWERED" in pair:
        return "UNDERPOWERED"
    return "RETRO-NULL"


def forward_token(t: str) -> str:
    return "STILL-OPEN" if t == "UNDERPOWERED" else t


def bh_adjust(ps: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values (q-values), input order."""
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, ps[i] * m / rank)
        q[i] = prev
    return q


def recall(arm_ev: list[Event], ctrl_ev: list[Event]) -> float:
    """Share of RC0's real-shift flips (uncensored) the arm also acts on."""
    real = {(e.ticker, e.flip_date) for e in ctrl_ev if e.out["real"]}
    if not real:
        return float("nan")
    acted = {(e.ticker, e.flip_date) for e in arm_ev}
    return len(real & acted) / len(real)


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def max_gap_sessions(s: Series, calendar: np.ndarray) -> tuple[int, str]:
    """Largest count of calendar sessions missing between consecutive closes.

    `calendar` None measures weekdays between closes instead (for ^GSPC itself).
    """
    worst, where = 0, ""
    if calendar is None:
        ds = np.array(s.dates, dtype="datetime64[D]")
        gaps = np.busday_count(ds[:-1], ds[1:]) - 1
    else:
        pos = np.searchsorted(calendar, s.dates)
        gaps = np.diff(pos) - 1
    if len(gaps):
        j = int(np.argmax(gaps))
        worst, where = int(gaps[j]), f"{s.dates[j]} -> {s.dates[j + 1]}"
    return worst, where


def gate_g0(data: dict[str, Series], spy_dirs) -> list[str]:
    """RC-G0 lines; raises GateRefusal on failure."""
    lines = []
    cal = data["GSPC"].dates
    for name, s in data.items():
        if len(s.dates) == 0:
            raise GateRefusal(f"RC-G0: {name} has no rows")
        g, where = max_gap_sessions(s, None if name == "GSPC" else cal)
        lines.append(f"  {name:<6} {s.dates[0]} .. {s.dates[-1]}  rows={len(s.dates):6d}  "
                     f"largest gap {g} session(s) {where}")
        if g > MAX_GAP_SESSIONS:
            raise GateRefusal(f"RC-G0: {name} has a gap of {g} sessions ({where})")
    if not MECH_TABLE_CSV.exists():
        raise GateRefusal(f"RC-G0: repo mech table {MECH_TABLE_CSV} missing")
    repo = {r["date"]: r["mech_direction"] for r in compute_mech_table(MECH_TABLE_CSV)
            if r["mech_direction"] is not None}
    spy = data["SPY"]
    shared = mism = 0
    first_bad = None
    for d, lab in zip(spy.dates, spy_dirs):
        if lab is None or d not in repo:
            continue
        shared += 1
        if (lab == "BEAR") != (repo[d] == "BEAR"):
            mism += 1
            first_bad = first_bad or d
    lines.append(f"  SPY BEAR label vs repo mech table: {shared} shared labelled dates, "
                 f"{mism} mismatch(es)")
    if shared == 0:
        raise GateRefusal("RC-G0: no date shared with the repo mech table")
    if mism:
        raise GateRefusal(f"RC-G0: SPY BEAR label disagrees with the repo mech table on "
                          f"{mism} date(s), first {first_bad}")
    return lines


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def _f(x, fmt="+.3f"):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def _pct(x):
    return _f(x * 100 if x is not None and math.isfinite(x) else x, ".1f") + "%"


@dataclass
class Scope:
    code: str
    tickers: tuple[str, ...]
    lo: str | None
    hi: str | None
    strict_after: bool = False
    window_end_limit: str | None = None


SCOPES = (
    Scope("RC-IS", ("SPY",), *RC_IS),
    Scope("RC-H1", ("GSPC",), *RC_H1, window_end_limit=RC_H1_WINDOW_END),
    Scope("RC-H2", ("QQQ", "IWM"), None, RC_H2_END),
    Scope("RC-FWD", ("SPY", "QQQ", "IWM"), FWD_AFTER, None, strict_after=True),
)

GRADED = {  # (arm, scope) -> role
    ("RC1", "RC-H2"): "co-primary",
    ("RC-200", "RC-H1"): "co-primary",
    ("RC1", "RC-FWD"): "forward",
    ("RC-P", "RC-H1"): "secondary",
    ("RC-P", "RC-H2"): "secondary",
    ("RC-C", "RC-H2"): "secondary",
    ("RC-200", "RC-H2"): "secondary",
}


def in_scope(sc: Scope, flip_date: str) -> bool:
    if sc.strict_after:
        return flip_date > sc.lo
    return (sc.lo is None or flip_date >= sc.lo) and (sc.hi is None or flip_date <= sc.hi)


def scope_events(sc: Scope, data, dirs_by) -> tuple[dict[str, list[Event]], dict, int]:
    ev = {a: [] for a in ARMS}
    census = {a: {"pending": 0, "missing": {c: 0 for c in CONDITIONS}} for a in ARMS}
    n_flips = 0
    for t in sc.tickers:
        s, dirs = data[t], dirs_by[t]
        flips = [f for f in find_flips(dirs) if in_scope(sc, s.dates[f])]
        n_flips += len(flips)
        e, c = build_events(t, s, dirs, flips, data, sc.window_end_limit)
        for a in ARMS:
            ev[a].extend(e[a])
            census[a]["pending"] += c[a]["pending"]
            for k in CONDITIONS:
                census[a]["missing"][k] += c[a]["missing"][k]
    return ev, census, n_flips


def report_scope(sc: Scope, data, dirs_by, results: dict) -> None:
    cal = data["GSPC"].dates
    ev, census, n_flips = scope_events(sc, data, dirs_by)
    graded_here = any(s == sc.code for (_a, s) in GRADED)
    label = "POST HOC — printed as context, never graded" if sc.code == "RC-IS" else (
        "graded" if graded_here else "printed")
    print("\n" + "=" * 78)
    rng = (f"flip date > {sc.lo}" if sc.strict_after else
           f"flip dates {sc.lo or 'start'} .. {sc.hi or 'end'}")
    print(f"{sc.code} — {'+'.join(sc.tickers)}, {rng} — {label}")
    if sc.window_end_limit:
        print(f"  outcome window must close on or before {sc.window_end_limit}")
    print("=" * 78)
    print(f"  flips: {n_flips}")
    ctrl = [e for e in ev["RC0"] if not e.censored]
    print("\n  census (events, uncensored, censored, pending, clusters among the arm's own "
          "uncensored events):")
    for a in ARMS:
        unc = [e for e in ev[a] if not e.censored]
        print(f"    {a:<7} events={len(ev[a]):4d}  uncensored={len(unc):4d}  "
              f"censored={len(ev[a]) - len(unc):3d}  pending={census[a]['pending']:2d}  "
              f"clusters={n_clusters(unc, cal):3d}")
    print("  condition missing at the decision date (counted as not met), per arm:")
    for a in ("RC0", "RC1", "RC-C"):
        print(f"    {a:<7} " + "  ".join(f"{c}={census[a]['missing'][c]}" for c in CONDITIONS))

    print(f"\n  real-shift rate (lowest close within {WINDOW} sessions >= {DROP:.0%} below the "
          "decision close), arm minus RC0, cluster bootstrap 95% CI:")
    print(f"    {'RC0':<7} n={len(ctrl):4d}  clusters={n_clusters(ctrl, cal):3d}  "
          f"rate={_pct(rate(ctrl))}")
    for a in ARMS[1:]:
        unc = [e for e in ev[a] if not e.censored]
        b = boot(unc, ctrl, cal)
        ncl = len(set(joint_clusters(unc, ctrl, cal)[0])) if unc else 0
        role = GRADED.get((a, sc.code))
        tok = token(len(unc), ncl, len(ctrl), b["lo"], b["hi"])
        if sc.code == "RC-FWD" and role == "forward":
            tok = forward_token(tok)
        if a == "RC-10":
            tag = "descriptive cut, no token"
        elif sc.code == "RC-IS":
            tag = "post hoc, no token"
        elif role is None:
            tag = "not graded in this scope, no token"
        else:
            tag = f"{role}: {tok}"
        print(f"    {a:<7} n={len(unc):4d}  clusters={ncl:3d}  rate={_pct(rate(unc))}  "
              f"diff={_f(b['diff'])}  CI95 [{_f(b['lo'])}, {_f(b['hi'])}]  "
              f"p={_f(b['p'], '.4f')}  -> {tag}")
        results[(a, sc.code)] = dict(n=len(unc), clusters=ncl, n_ctrl=len(ctrl),
                                     rate=rate(unc), ctrl_rate=rate(ctrl), token=tok, role=role,
                                     **{k: b[k] for k in ("diff", "lo", "hi", "p")})

    print("\n  secondaries from each event's decision close (median [cluster-bootstrap 95% CI]); "
          "no verdict:")
    for a in ARMS:
        unc = [e for e in ev[a] if not e.censored]
        if not unc:
            print(f"    {a:<7} no uncensored events")
            continue
        b = boot(unc, ctrl, cal)
        md = b["medians"]
        lags = np.array([e.lag for e in unc])
        q1, q3 = np.percentile(lags, [25, 75])
        fa = 1 - rate(unc)
        print(f"    {a:<7} ret20 {_f(md['ret20'][0])} [{_f(md['ret20'][1])}, {_f(md['ret20'][2])}]  "
              f"ret60 {_f(md['ret60'][0])} [{_f(md['ret60'][1])}, {_f(md['ret60'][2])}]  "
              f"maxDD {_f(md['maxdd'][0])} [{_f(md['maxdd'][1])}, {_f(md['maxdd'][2])}]")
        print(f"    {'':<7} false-alarm {_pct(fa)}  recall {_pct(recall(unc, ctrl))}  "
              f"lag cost median {_f(md['lag'][0])} [{_f(md['lag'][1])}, {_f(md['lag'][2])}]  "
              f"quartiles [{_f(float(q1))}, {_f(float(q3))}]")

    ts = [e for e in ctrl if e.conds.get("ts") is not None]
    inv = [e for e in ts if e.conds["ts"]]
    norm = [e for e in ts if not e.conds["ts"]]
    print(f"\n  RC-TS (descriptive cut): RC0 flips with VIX/VIX3M at the flip known: {len(ts)}; "
          f"above 1: n={len(inv)} rate={_pct(rate(inv))}; at or below 1: n={len(norm)} "
          f"rate={_pct(rate(norm))}")


def report_case(data, dirs_by) -> None:
    t, d0 = EXCLUDED_CASE
    s, dirs = data[t], dirs_by[t]
    print("\n" + "=" * 78)
    print(f"CASE — the {t} flip of {d0}: before the registration, after the exploration; "
          "excluded from every graded scope")
    print("=" * 78)
    i = s.index_of(d0)
    if i is None or i not in find_flips(dirs):
        print(f"  {d0} is not a flip on the cached {t} series (cache ends {s.dates[-1]})")
        return
    n, ended = streak_from(dirs, i)
    print(f"  streak: {n} BEAR session(s), "
          f"{'ended' if ended else 'still BEAR at the data end'} (cache ends {s.dates[-1]})")
    for k, lbl in ((1, "at the flip"), (STREAK, f"at day {STREAK}")):
        di = decision_index(dirs, i, k)
        if di is None or di == PENDING:
            print(f"  {lbl}: {'not reached' if di is None else 'pending'}")
            continue
        c = conditions_at(data, s.dates[di])
        print(f"  {lbl} ({s.dates[di]}): " + "  ".join(f"{k2}={v}" for k2, v in c.items())
              + f"  met={n_met(c)}  own200={below_sma(s, s.dates[di])}  "
              f"lag={_f(float(s.close[di] / s.close[i] - 1))}")
    print("  outcome: window not closed; no outcome printed")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="refetch every cached series")
    args = ap.parse_args(argv)

    print("regime_confirm — does a confirmed mech BEAR flip predict a real sell-off better "
          "than the flip alone?")
    print(f"registration: {REGISTRATION} (accepted by default {ACCEPTED})")
    print(f"cache: {CACHE_DIR.relative_to(ROOT)}  (yfinance, auto_adjust=False)")
    print(f"floors: arm {MIN_EVENTS} uncensored events in {MIN_CLUSTERS}+ clusters; RC0 "
          f"{MIN_CONTROL} events.  bootstrap {BOOT_N} draws over clusters, seed {SEED}")

    try:
        data = load_all(args.refresh)
        dirs_by = {t: mech_directions(data[t]) for t in ("GSPC", "SPY", "QQQ", "IWM")}
        print("\nRC-G0 data:")
        for line in gate_g0(data, dirs_by["SPY"]):
            print(line)
    except GateRefusal as exc:
        print(f"\n{exc}\nREFUSED (exit 2)")
        return 2
    print("RC-G0: PASS")
    print("RC-G1: causality asserted per event (conditions on or before, outcomes strictly "
          "after the decision date)")

    results: dict = {}
    for sc in SCOPES:
        report_scope(sc, data, dirs_by, results)
    report_case(data, dirs_by)

    sec = [k for k, v in GRADED.items() if v == "secondary"]
    ps = [results[k]["p"] if results[k]["token"] != "UNDERPOWERED"
          and math.isfinite(results[k]["p"]) else 1.0 for k in sec]
    qs = bh_adjust(ps)

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    print("  RC-IS (SPY 1993-2026) is spent: post hoc context, no token.")
    print("  events and clusters per graded arm and scope:")
    for k, role in GRADED.items():
        r = results[k]
        print(f"    {k[0]:<7} on {k[1]:<7} ({role:<10}) events={r['n']:3d} clusters={r['clusters']:3d}  "
              f"rate {_pct(r['rate'])} vs RC0 {_pct(r['ctrl_rate'])} (RC0 n={r['n_ctrl']})  "
              f"diff {_f(r['diff'])} [{_f(r['lo'])}, {_f(r['hi'])}]")
    print("\n  secondary family, BH at q < 0.05 (printed, no verdict; an UNDERPOWERED member "
          "enters at p = 1):")
    for k, p, q in zip(sec, ps, qs):
        print(f"    {k[0]:<7} on {k[1]:<7} token {results[k]['token']:<12} p={_f(p, '.4f')}  "
              f"BH q={_f(q, '.4f')}  {'q < 0.05' if q < BH_Q else 'q >= 0.05'}")
    t1, t2 = results[("RC1", "RC-H2")]["token"], results[("RC-200", "RC-H1")]["token"]
    print(f"\n  >>> regime_confirm RC1 on RC-H2 (QQQ+IWM, co-primary): {t1} <<<")
    print(f"  >>> regime_confirm RC-200 on RC-H1 (^GSPC 1950-1992, co-primary): {t2} <<<")
    print(f"  >>> regime_confirm RETROSPECTIVE: {retro_verdict(t1, t2)} <<<")
    print(f"  >>> regime_confirm FORWARD (RC1 on RC-FWD, flips after {FWD_AFTER}): "
          f"{results[('RC1', 'RC-FWD')]['token']} <<<")
    print("  The verdict of record is the first run printing a retrospective token, and the "
          "first forward run printing a token other than STILL-OPEN (regime_confirm.md).")
    print("  Nothing ships from this study.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
