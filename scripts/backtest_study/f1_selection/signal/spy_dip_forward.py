"""spy_dip_forward — do SPY entries on dip dates do better over the next month, 1993 on?

REGISTERED 2026-11-27, accepted by default, second-read the same day:
research/pre-registrations/f1_selection/signal/spy_dip_forward.md. Every
constant, window, floor, seed and verdict word below is that file's. Read it
before changing anything here. The registration is immutable in substance.

WHAT IT ASKS
------------
A dip date D is a session on which SPY's UNADJUSTED close is strictly below the
mean of the 50 unadjusted closes ending at D: the live rule's flag, computed by
`lib/mech_regime.py::compute_mech_table` unchanged (`spy_below_sma`). Every
flagged session is an entry at the close of D+1 (the book's one clock). For
horizon h the net forward excess return is

    X_h(e) = A_{e+h} / A_e - prod_{k=e+1..e+h} (1 + y_{k-1} / 100 / 252) - 0.0004

with A the adjusted close and y the ^IRX close, carried forward.

  P  Delta_21 = mean X_21 over dip entries - mean over non-dip entries
  T  q10(MAE_21 | dip) - q10(MAE_21 | non-dip), MAE the worst close in the hold
  Z  mean X_21 of dips at or above the 200-session SMA - dips below it

Graded on HOLDOUT (signal dates 2010-2025), Holm m = 3. P also needs a positive
point estimate on DISCOVERY (to 2009) and PRE-BOOK (2010-2023) and a PBO of at
most 0.50 over a 4-definition x 3-horizon grid. Moving-block bootstrap on the
entry sequence, whole rows, L = max(63, 2h), 10,000 draws, seed 20261127.
2026 prints apart as contaminated; FORWARD entries start after the registration.

DATA
----
SPY daily bars from yfinance, auto_adjust=False, cached in
`backtests/spy_dip_forward/SPY.csv` (date, close, adj_close), fetched ONLY with
`--refresh`; a bar dated today is kept only after 16:30 New York time. ^IRX
from `backtests/spy_dip_forward/IRX.csv` (written by `--refresh`) when it
exists, else `backtests/trend_overlay/IRX.csv` (read only). Negative or zero
^IRX quotes are data. Gates GS and GM read `backtests/mech_regime/`.

Every flag reads closes at or before D only (gate GX at run time, pinned by
tests/test_spy_dip_forward.py). Episodes read later sessions, so they feed the
power floor and the ORDINAL print only.

The holdout seal does not apply: no play is read. Nothing ships. Run:

    python -m scripts.backtest_study run spy_dip_forward
    python -m scripts.backtest_study run spy_dip_forward -- --refresh
"""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import compute_mech_table  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark.ticker_class import holm  # noqa: E402
from scripts.backtest_study.f1_selection.regime.tail_breach import (  # noqa: E402
    base_rate_problems, block_indices, ratio_problems)
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib.pbo import cscv  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/signal/spy_dip_forward.md"
REGISTERED: str | None = "2026-11-27"

# --- constants fixed by the registration -------------------------------------
COST = 0.0004                     # round trip: 2 bps per side
TRADING_DAYS = 252
HORIZONS = (5, 21, 63)
H = 21                            # primary horizon
DEFS = ("SMA50", "SMA20", "PB5", "DN3")
PRIMARY = "SMA50"
SMA_SHORT = 20
SMA_LONG = 200                    # the 200-day regime
PB_LOOKBACK, PB_LEVEL = 20, 0.95
DN_RUN = 3
VOL_WINDOW = 21                   # log returns ending at D for VOL-SCALED
EPISODE_GAP = 5                   # an episode ends after MORE than 5 non-dip sessions in a row
QUANTILE = 10                     # T's percentile, numpy's default linear rule
BOOT_N = 10_000
SEED = 20261127
ALPHA = 0.05
NAN_SHARE_MAX = 0.01              # more NaN draws than this: the CI is not finite
CHUNK = 500                       # draws expanded at once for the quantile arm (memory only)
MIN_EPISODES, MIN_DIP, MIN_NONDIP, MAX_EPISODE_SHARE = 20, 250, 250, 1.0 / 3.0   # GN
Z_MIN_EPISODES, Z_MIN_ENTRIES = 10, 100                                        # GN for Z
PBO_S, PBO_VETO, PBO_FRAGILE = 16, 0.50, 0.25
PBO_END = "2025-12-31"
SPACED_STEP, SPACED_BLOCK = 21, 3
WEEKLY_BLOCK = 13
NW_LAGS = 42

WINDOW_ORDER = ("DISCOVERY", "HOLDOUT", "PRE-BOOK", "2026", "FORWARD")
FAR_PAST, FAR_FUTURE = "0000-01-01", "9999-12-31"

# Gates
SPY_START_LATEST = "1993-02-01"                     # GE
GE_AFTER, GE_MIN_AFTER = "2025-12-31", 64           # GE
GB_MAX_RET = 0.25                                   # GB: |daily adjusted return|
GM_EXCEPTIONS = (("2001-09-11", "2001-09-14"),      # 9/11 closures
                 ("2007-01-01", "2007-01-02"),      # New Year's Day, then the Ford day of mourning
                 ("2012-10-29", "2012-10-30"))      # Hurricane Sandy
GS_BAND = 0.0005                                    # GS: |close / SMA - 1| below this is a tie band
GI_MAX_CARRY, GI_TOL = 5, 0.01                      # GI
GX_SAMPLE = 60                                      # GX

CACHE_DIR = ROOT / "backtests" / "spy_dip_forward"
SPY_CSV = CACHE_DIR / "SPY.csv"
IRX_OWN = CACHE_DIR / "IRX.csv"
IRX_TREND = ROOT / "backtests" / "trend_overlay" / "IRX.csv"
MECH_DIR = ROOT / "backtests" / "mech_regime"
VIX_FULL_CSV = MECH_DIR / "spy_vix_daily_full.csv"
BASE_RATE_CSV = MECH_DIR / "spy_base_rate_daily.csv"
FETCH = {"SPY": ("SPY", "1993-01-01"), "IRX": ("^IRX", "1993-01-01")}
NY_CLOSE_SETTLED = "16:30"

SUPPORTED, PBO_VETO_W, CONTRARY, NULL = "SUPPORTED", "PBO-VETO", "CONTRARY", "NULL"
DEEPER, SHALLOWER = "DEEPER-DRAWDOWN", "SHALLOWER-DRAWDOWN"
ABOVE_BETTER, BELOW_BETTER = "ABOVE-200-BETTER", "BELOW-200-BETTER"
UNDERPOWERED, STILL_OPEN = "UNDERPOWERED", "STILL-OPEN"
P_WORDS = {SUPPORTED, PBO_VETO_W, CONTRARY, NULL, UNDERPOWERED}
T_WORDS = {DEEPER, SHALLOWER, NULL, UNDERPOWERED}
Z_WORDS = {ABOVE_BETTER, BELOW_BETTER, NULL, UNDERPOWERED}
BANNER = {
    "P": "SPY 21-session excess return, entry the close after a close below the 50-day SMA, "
         "vs other entries, holdout 2010-2025, Holm m=3",
    "T": "worst-decile 21-session drawdown, dip minus non-dip, holdout, Holm m=3",
    "Z": "dips above minus below the 200-day SMA, 21 sessions, holdout, Holm m=3",
}
RULE = "=" * 78

# Exit 2: any era but `current`. Exit 3: GE, GB, GM, GS, GI or GX.
EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}


class Refused(Exception):
    def __init__(self, code: int, message: str, gate: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.gate = gate


def refuse(gate: str, reason: str) -> Refused:
    return Refused(EXIT_INPUT, f"{gate}: {reason}", gate)


def windows(registered: str = REGISTERED) -> dict:
    """{name: (first, last)} signal-date ranges, inclusive. FORWARD starts the
    day after the registration date."""
    nxt = (date.fromisoformat(registered) + timedelta(days=1)).isoformat()
    return {"DISCOVERY": (FAR_PAST, "2009-12-31"), "HOLDOUT": ("2010-01-01", "2025-12-31"),
            "PRE-BOOK": ("2010-01-01", "2023-12-31"), "2026": ("2026-01-01", registered),
            "FORWARD": (nxt, FAR_FUTURE)}


# ════════════════════════════════════════════════════════════════════════════
# Data
# ════════════════════════════════════════════════════════════════════════════

def _ny_now() -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def _rel(path: Path) -> str:
    p = Path(path).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def fetch_series(name: str, path: Path) -> Path:
    """yfinance -> `path` (date, close, adj_close). A bar dated today is kept
    only after 16:30 New York time. ^IRX values at or below zero are written."""
    import pandas as pd
    import yfinance as yf
    sym, start = FETCH[name]
    now = _ny_now()
    today = now.date().isoformat()
    end = (now.date() + timedelta(days=1)).isoformat()
    df = yf.download(sym, start=start, end=end, auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise refuse("GE", f"yfinance returned no rows for {sym}")

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
            if ds > today or (ds == today and not keep_today):
                continue
            if c == c:
                w.writerow([ds, repr(float(c)), repr(float(a)) if a == a else ""])
                n += 1
    print(f"fetched {sym} -> {_rel(path)} ({n} rows)")
    return path


def read_spy(path: Path) -> list[tuple[str, float, float | None]]:
    """(date, close, adj_close) rows, ascending; finite positive closes only,
    adj_close None when missing or not positive."""
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


def read_irx(path: Path) -> dict[str, float]:
    """{date: close}. Every finite close is kept, INCLUDING zero and negative
    quotes (March 2020): they are data, not errors."""
    out = {}
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                v = float(r["close"])
            except (TypeError, ValueError):
                continue
            if math.isfinite(v):
                out[r["date"][:10]] = v
    return dict(sorted(out.items()))


def calendar_rows(spy: list[tuple]) -> list[tuple]:
    """The calendar: sessions with both a Close and an Adj Close."""
    return [r for r in spy if r[2] is not None]


# ════════════════════════════════════════════════════════════════════════════
# Flags. Each reads closes[0..i] only.
# ════════════════════════════════════════════════════════════════════════════

def mech_flags(dates: list[str], closes: list[float]) -> list[bool | None]:
    """SMA50: the shipped `compute_mech_table`, called unchanged on a CSV of the
    cached unadjusted closes as `spy_close` with `vix_close` blank."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "spy_close.csv"
        with p.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "spy_close", "vix_close"])
            for d, c in zip(dates, closes):
                w.writerow([d, repr(float(c)), ""])
        table = compute_mech_table(p)
    by = {r["date"]: r["spy_below_sma"] for r in table}
    return [by.get(d) for d in dates]


def sma_at(closes: list[float], i: int, n: int) -> float | None:
    """Mean of the n closes ending at i, summed as compute_mech_table sums them."""
    if i + 1 < n:
        return None
    return sum(closes[i + 1 - n:i + 1]) / n


def below_sma_at(closes: list[float], i: int, n: int) -> bool | None:
    s = sma_at(closes, i, n)
    return None if s is None else closes[i] < s


def pb5_at(closes: list[float], i: int) -> bool | None:
    if i + 1 < PB_LOOKBACK:
        return None
    return closes[i] <= PB_LEVEL * max(closes[i + 1 - PB_LOOKBACK:i + 1])


def dn3_at(closes: list[float], i: int) -> bool | None:
    if i < DN_RUN:
        return None
    return all(closes[i - j] < closes[i - j - 1] for j in range(DN_RUN))


def above200_at(closes: list[float], i: int) -> bool | None:
    s = sma_at(closes, i, SMA_LONG)
    return None if s is None else closes[i] >= s


def own_flags(closes: list[float]) -> dict[str, list]:
    """The module's own flags (every definition but SMA50) and the regime."""
    n = len(closes)
    return {"SMA20": [below_sma_at(closes, i, SMA_SHORT) for i in range(n)],
            "PB5": [pb5_at(closes, i) for i in range(n)],
            "DN3": [dn3_at(closes, i) for i in range(n)],
            "ABOVE200": [above200_at(closes, i) for i in range(n)]}


def all_flags(dates: list[str], closes: list[float]) -> dict[str, list]:
    out = {"SMA50": mech_flags(dates, closes)}
    out.update(own_flags(closes))
    return out


class LookaheadError(RuntimeError):
    """GX failed: a flag or the regime changed when the series was cut at D."""


def gx_check(dates: list[str], closes: list[float], flags: dict, n: int = GX_SAMPLE,
             mech=None) -> int:
    """GX: at `n` evenly spaced sessions D (with an SMA50 flag), recompute every
    flag and the 200-day regime on the series cut at D; raise unless they equal
    the full-series values. Returns the count checked."""
    mech = mech or mech_flags
    have = [i for i, v in enumerate(flags["SMA50"]) if v is not None]
    if not have:
        return 0
    picks = sorted({have[int(j)] for j in np.linspace(0, len(have) - 1, min(n, len(have)))})
    for i in picks:
        cut_d, cut_c = dates[:i + 1], closes[:i + 1]
        got = {"SMA50": mech(cut_d, cut_c)[i], "SMA20": below_sma_at(cut_c, i, SMA_SHORT),
               "PB5": pb5_at(cut_c, i), "DN3": dn3_at(cut_c, i),
               "ABOVE200": above200_at(cut_c, i)}
        for k, v in got.items():
            if v != flags[k][i]:
                raise LookaheadError(f"{k} on {dates[i]} differs on the series cut at D")
    return len(picks)


# ════════════════════════════════════════════════════════════════════════════
# T-bill and outcomes, indexed by signal session i (entry e = i + 1)
# ════════════════════════════════════════════════════════════════════════════

def tbill(dates: list[str], irx: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    """(y, own): y[j] = the last ^IRX close dated on or before session j (NaN
    before the first); own[j] = True when ^IRX has a close dated on j."""
    keys = list(irx)
    y = np.full(len(dates), np.nan)
    own = np.zeros(len(dates), dtype=bool)
    k, last = 0, float("nan")
    for j, d in enumerate(dates):
        while k < len(keys) and keys[k] <= d:
            last = irx[keys[k]]
            k += 1
        y[j] = last
        own[j] = d in irx
    return y, own


def growth(y: np.ndarray) -> np.ndarray:
    """g[k] = 1 + y[k-1] / 100 / 252: the T-bill pays for session k at the yield
    known before it. g[0] is undefined (NaN)."""
    g = np.full(len(y), np.nan)
    g[1:] = 1.0 + y[:-1] / 100.0 / TRADING_DAYS
    return g


def outcomes(adj: np.ndarray, y: np.ndarray, h: int, cost: float = COST) -> tuple[np.ndarray, np.ndarray]:
    """(X_h, MAE_h) per signal index i; entry e = i + 1 at A_e. NaN when e + h
    is past the data (open) or a T-bill factor is undefined."""
    n = len(adj)
    X = np.full(n, np.nan)
    M = np.full(n, np.nan)
    if n < h + 2:
        return X, M
    from numpy.lib.stride_tricks import sliding_window_view as swv
    g = growth(y)
    prod = swv(g, h).prod(axis=1)          # prod[k] = g[k] * ... * g[k+h-1]
    mins = swv(adj, h).min(axis=1)         # mins[k] = min adj[k..k+h-1]
    for i in range(n - h - 1):
        e = i + 1
        X[i] = adj[e + h] / adj[e] - prod[e + 1] - cost
        M[i] = mins[e + 1] / adj[e] - 1.0
    return X, M


def vol_at(adj: np.ndarray) -> np.ndarray:
    """sigma[i] = sample sd (ddof 1) of the 21 daily log adjusted returns ending at i."""
    n = len(adj)
    s = np.full(n, np.nan)
    if n < VOL_WINDOW + 1:
        return s
    lr = np.full(n, np.nan)
    lr[1:] = np.log(adj[1:] / adj[:-1])
    for i in range(VOL_WINDOW, n):
        s[i] = float(np.std(lr[i - VOL_WINDOW + 1:i + 1], ddof=1))
    return s


# ════════════════════════════════════════════════════════════════════════════
# Episodes (whole series; read later sessions — floors and ORDINAL only)
# ════════════════════════════════════════════════════════════════════════════

def episodes(flag: list) -> tuple[np.ndarray, np.ndarray]:
    """(episode id, ordinal) per session; -1 / 0 off a dip session. A dip
    session joins the running episode unless MORE than EPISODE_GAP non-dip
    sessions in a row separate it from the previous dip session (Resolved at
    build 2026-11-27: a run of exactly 5 continues the episode). The ordinal
    counts dip sessions within the episode, 1 first."""
    n = len(flag)
    ep = np.full(n, -1, dtype=int)
    ordn = np.zeros(n, dtype=int)
    eid, last, k = -1, None, 0
    for i, v in enumerate(flag):
        if v is not True:
            continue
        if last is None or i - last - 1 > EPISODE_GAP:
            eid += 1
            k = 0
        k += 1
        ep[i], ordn[i], last = eid, k, i
    return ep, ordn


# ════════════════════════════════════════════════════════════════════════════
# The study's data and the entry rows of a window
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Data:
    dates: list[str]
    close: list[float]
    adj: np.ndarray
    y: np.ndarray
    own_irx: np.ndarray
    flags: dict
    X: dict = field(default_factory=dict)
    MAE: dict = field(default_factory=dict)
    sigma: np.ndarray | None = None
    ep: np.ndarray | None = None
    ordn: np.ndarray | None = None

    @property
    def n(self) -> int:
        return len(self.dates)


def build_data(cal: list[tuple], irx: dict[str, float], flags: dict | None = None) -> Data:
    dates = [r[0] for r in cal]
    close = [float(r[1]) for r in cal]
    adj = np.array([r[2] for r in cal], dtype=float)
    y, own = tbill(dates, irx)
    flags = flags if flags is not None else all_flags(dates, close)
    d = Data(dates, close, adj, y, own, flags)
    for h in HORIZONS:
        d.X[h], d.MAE[h] = outcomes(adj, y, h)
    d.sigma = vol_at(adj)
    d.ep, d.ordn = episodes(flags[PRIMARY])
    return d


@dataclass
class Rows:
    """One window's whole-window entries for one definition and horizon, in
    date order. f = dip flag (1/0); reg = 1 at or above the 200-day SMA, 0
    below, NaN with no regime."""
    window: str
    defn: str
    h: int
    i: np.ndarray
    f: np.ndarray
    reg: np.ndarray
    x: np.ndarray
    mae: np.ndarray
    vs: np.ndarray
    ep: np.ndarray
    ordn: np.ndarray
    census: dict

    @property
    def n(self) -> int:
        return len(self.i)

    def subset(self, keep: np.ndarray) -> "Rows":
        return Rows(self.window, self.defn, self.h, self.i[keep], self.f[keep], self.reg[keep],
                    self.x[keep], self.mae[keep], self.vs[keep], self.ep[keep], self.ordn[keep],
                    dict(self.census))


def classify(d: Data, i: int, h: int, rng: tuple[str, str]) -> str:
    """counted / gap / open / no_entry for a flagged signal session i whose
    date is inside `rng`. Counted: D, the entry session and the h-window's
    last session all inside the window."""
    a, b = rng
    if i + 1 >= d.n:
        return "no_entry"
    if i + 1 + h >= d.n:
        return "open"
    if a <= d.dates[i + 1] <= b and a <= d.dates[i + 1 + h] <= b:
        return "counted"
    return "gap"


def build_rows(d: Data, window: str, h: int = H, defn: str = PRIMARY,
               registered: str = REGISTERED) -> Rows:
    rng = windows(registered)[window]
    flag = d.flags[defn]
    keep, census = [], {"counted": 0, "gap": 0, "open": 0, "no_entry": 0}
    for i, v in enumerate(flag):
        if v is None or not (rng[0] <= d.dates[i] <= rng[1]):
            continue
        lab = classify(d, i, h, rng)
        census[lab] += 1
        if lab == "counted":
            keep.append(i)
    idx = np.array(keep, dtype=int)
    f = np.array([1.0 if flag[i] else 0.0 for i in keep])
    reg = np.array([np.nan if d.flags["ABOVE200"][i] is None else float(d.flags["ABOVE200"][i])
                    for i in keep])
    x = d.X[h][idx] if len(idx) else np.zeros(0)
    mae = d.MAE[h][idx] if len(idx) else np.zeros(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        vs = x / (d.sigma[idx] * math.sqrt(h)) if len(idx) else np.zeros(0)
    vs = np.where(np.isfinite(vs), vs, np.nan)
    ep = d.ep[idx] if len(idx) else np.zeros(0, dtype=int)
    ordn = d.ordn[idx] if len(idx) else np.zeros(0, dtype=int)
    if defn != PRIMARY:
        ep = np.full(len(idx), -1, dtype=int)
        ordn = np.zeros(len(idx), dtype=int)
    census["first"] = d.dates[keep[0]] if keep else None
    census["last"] = d.dates[keep[-1]] if keep else None
    return Rows(window, defn, h, idx, f, reg, x, mae, vs, ep, ordn, census)


# ════════════════════════════════════════════════════════════════════════════
# Arms and the bootstrap
# ════════════════════════════════════════════════════════════════════════════

def _mean(v: np.ndarray) -> float:
    return float(np.mean(v)) if len(v) else float("nan")


def _q(v: np.ndarray) -> float:
    return float(np.percentile(v, QUANTILE)) if len(v) else float("nan")


def arm_p(x: np.ndarray, f: np.ndarray) -> float:
    return _mean(x[f == 1]) - _mean(x[f == 0])


def arm_t(mae: np.ndarray, f: np.ndarray) -> float:
    return _q(mae[f == 1]) - _q(mae[f == 0])


def arm_z(x: np.ndarray, f: np.ndarray, reg: np.ndarray) -> float:
    return _mean(x[(f == 1) & (reg == 1)]) - _mean(x[(f == 1) & (reg == 0)])


def boot_starts(n: int, L: int, draws: int, seed: int) -> tuple[np.ndarray, int]:
    """The block starts of `tail_breach.block_indices(n, L, draws, seed)`, drawn
    the same way from the same generator, so `expand` rebuilds its rows exactly
    (pinned by a test). Kept apart only so 10,000 x n indices need not sit in
    memory at once."""
    L = max(1, min(L, n))
    nb = -(-n // L)
    rng = np.random.default_rng(seed)
    return rng.integers(0, n - L + 1, size=(draws, nb)), L


def expand(starts: np.ndarray, n: int, L: int) -> np.ndarray:
    return (starts[:, :, None] + np.arange(L)[None, None, :]).reshape(len(starts), -1)[:, :n]


def draws_match_block_indices(n: int, L: int, draws: int = 50, seed: int = SEED) -> bool:
    """True when `expand(boot_starts(...))` rebuilds `tail_breach.block_indices`
    row for row (checked at run time on a small draw count)."""
    starts, Lc = boot_starts(n, L, draws, seed)
    return bool(np.array_equal(expand(starts, n, Lc), block_indices(n, L, draws, seed)))


def block_sums(v: np.ndarray, starts: np.ndarray, n: int, L: int) -> np.ndarray:
    """Per draw, the sum of v over the drawn rows (whole blocks, the last cut
    so the draw holds n rows), from prefix sums."""
    cs = np.concatenate([[0.0], np.cumsum(v)])
    r = n - (starts.shape[1] - 1) * L
    full = (cs[starts[:, :-1] + L] - cs[starts[:, :-1]]).sum(axis=1)
    return full + cs[starts[:, -1] + r] - cs[starts[:, -1]]


def boot_mean_diff(v: np.ndarray, g1: np.ndarray, g0: np.ndarray, starts: np.ndarray,
                   n: int, L: int) -> np.ndarray:
    """mean v over g1 rows - mean v over g0 rows, per draw; NaN where a group
    is empty. g1 and g0 are 0/1 row masks; the drawn rows carry v, g1 and g0
    together."""
    v0 = np.where(np.isfinite(v), v, 0.0)
    s1, n1 = block_sums(v0 * g1, starts, n, L), block_sums(g1.astype(float), starts, n, L)
    s0, n0 = block_sums(v0 * g0, starts, n, L), block_sums(g0.astype(float), starts, n, L)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = s1 / n1 - s0 / n0
    out[(np.round(n1) == 0) | (np.round(n0) == 0)] = np.nan
    return out


def q_rows(V: np.ndarray, q: float = QUANTILE) -> np.ndarray:
    """Row-wise q-th percentile of the finite values, numpy's linear rule; NaN
    for a row with none."""
    s = np.sort(V, axis=1)                      # NaN sorts last
    c = np.sum(np.isfinite(V), axis=1)
    out = np.full(len(V), np.nan)
    ok = c > 0
    if not ok.any():
        return out
    pos = (c[ok] - 1) * (q / 100.0)
    lo = np.floor(pos).astype(int)
    hi = np.minimum(lo + 1, c[ok] - 1)
    rows = np.nonzero(ok)[0]
    a, b = s[rows, lo], s[rows, hi]
    out[ok] = a + (pos - lo) * (b - a)
    return out


def boot_q_diff(v: np.ndarray, f: np.ndarray, starts: np.ndarray, n: int, L: int) -> np.ndarray:
    out = np.empty(len(starts))
    for c in range(0, len(starts), CHUNK):
        idx = expand(starts[c:c + CHUNK], n, L)
        vv, ff = v[idx], f[idx]
        out[c:c + CHUNK] = q_rows(np.where(ff == 1, vv, np.nan)) - q_rows(np.where(ff == 0, vv, np.nan))
    return out


@dataclass
class Result:
    point: float
    lo: float
    hi: float
    p: float
    nan_share: float
    n: int

    @property
    def finite(self) -> bool:
        return math.isfinite(self.lo) and math.isfinite(self.hi)


def summarize(point: float, draws: np.ndarray, n: int) -> Result:
    """CI = 2.5th/97.5th percentiles of the finite draws, not finite when more
    than 1% of draws are NaN. p two-sided = twice the smaller share at or
    beyond 0, capped at 1 (the tail_breach convention)."""
    fin = draws[np.isfinite(draws)]
    nan_share = 1.0 - len(fin) / len(draws) if len(draws) else 1.0
    if not len(fin) or not math.isfinite(point):
        return Result(point, float("nan"), float("nan"), 1.0, nan_share, n)
    p = min(1.0, 2.0 * min(float(np.mean(fin <= 0)), float(np.mean(fin >= 0))))
    if len(draws) - len(fin) > NAN_SHARE_MAX * len(draws):      # counts, not a float share
        return Result(point, float("nan"), float("nan"), p, nan_share, n)
    lo, hi = np.percentile(fin, [2.5, 97.5])
    return Result(point, float(lo), float(hi), p, nan_share, n)


def block_len(h: int) -> int:
    return max(63, 2 * h)


def measure(rows: Rows, arms=("P", "T", "Z"), L: int | None = None, value: str = "x",
            draws: int = BOOT_N, seed: int = SEED) -> dict[str, Result]:
    """P, T and Z on `rows`, all recomputed on the same drawn rows."""
    L = block_len(rows.h) if L is None else L
    n = rows.n
    v = getattr(rows, value)
    out = {}
    if n == 0:
        return {a: Result(float("nan"), float("nan"), float("nan"), 1.0, 1.0, 0) for a in arms}
    starts, Lc = boot_starts(n, L, draws, seed)
    f = rows.f
    if "P" in arms:
        out["P"] = summarize(arm_p(v, f), boot_mean_diff(v, f == 1, f == 0, starts, n, Lc), n)
    if "T" in arms:
        out["T"] = summarize(arm_t(rows.mae, f), boot_q_diff(rows.mae, f, starts, n, Lc), n)
    if "Z" in arms:
        up, dn = (f == 1) & (rows.reg == 1), (f == 1) & (rows.reg == 0)
        out["Z"] = summarize(arm_z(v, f, rows.reg), boot_mean_diff(v, up, dn, starts, n, Lc), n)
    return out


# ════════════════════════════════════════════════════════════════════════════
# Power
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Power:
    ok: bool
    episodes: int
    dip: int
    nondip: int
    largest: int


def gn(rows: Rows) -> Power:
    """At least 20 episodes, 250 dip and 250 non-dip entries; the largest
    episode holds at most a third of the window's dip entries. An episode
    counts when the window holds one of its dip entries."""
    dip = rows.f == 1
    eps = rows.ep[dip]
    counts = np.bincount(eps[eps >= 0]) if len(eps) else np.zeros(0, dtype=int)
    n_ep = int(np.sum(counts > 0))
    largest = int(counts.max()) if len(counts) else 0
    n_dip, n_non = int(dip.sum()), int((rows.f == 0).sum())
    ok = (n_ep >= MIN_EPISODES and n_dip >= MIN_DIP and n_non >= MIN_NONDIP
          and largest <= MAX_EPISODE_SHARE * n_dip)
    return Power(ok, n_ep, n_dip, n_non, largest)


@dataclass
class PowerZ:
    ok: bool
    ep_above: int
    ep_below: int
    n_above: int
    n_below: int


def gn_z(rows: Rows) -> PowerZ:
    up = (rows.f == 1) & (rows.reg == 1)
    dn = (rows.f == 1) & (rows.reg == 0)
    ea, eb = len({int(e) for e in rows.ep[up] if e >= 0}), len({int(e) for e in rows.ep[dn] if e >= 0})
    na, nb = int(up.sum()), int(dn.sum())
    ok = ea >= Z_MIN_EPISODES and eb >= Z_MIN_EPISODES and na >= Z_MIN_ENTRIES and nb >= Z_MIN_ENTRIES
    return PowerZ(ok, ea, eb, na, nb)


# ════════════════════════════════════════════════════════════════════════════
# PBO
# ════════════════════════════════════════════════════════════════════════════

CELLS = tuple((dfn, h) for dfn in DEFS for h in HORIZONS)


def cell_label(dfn: str, h: int) -> str:
    return f"{dfn}-{h}"


def pbo_matrix(d: Data, end: str = PBO_END) -> tuple[np.ndarray, list[int], int]:
    """(T x 12 x 2 array, signal indices kept, oldest rows dropped). Rows: D
    from the first session where all four definitions have a flag to the last D
    whose 63-session window ends on or before `end`. Channel 0 = the cell's net
    X_h for the entry at D+1, channel 1 = the cell's dip flag on D."""
    hmax = max(HORIZONS)
    first = next((i for i in range(d.n) if all(d.flags[k][i] is not None for k in DEFS)), None)
    if first is None:
        return np.zeros((0, len(CELLS), 2)), [], 0
    keep = [i for i in range(first, d.n) if i + 1 + hmax < d.n and d.dates[i + 1 + hmax] <= end]
    dropped = len(keep) % PBO_S
    keep = keep[dropped:]
    M = np.zeros((len(keep), len(CELLS), 2))
    idx = np.array(keep, dtype=int)
    for c, (dfn, h) in enumerate(CELLS):
        M[:, c, 0] = d.X[h][idx] if len(idx) else 0
        M[:, c, 1] = [1.0 if d.flags[dfn][i] else 0.0 for i in keep]
    return M, keep, dropped


def pbo_metric(sub: np.ndarray) -> np.ndarray:
    """Per cell: mean X over the cell's dip rows - mean over its non-dip rows,
    divided by h (Delta_h / h). NaN when a subset has no dip or no non-dip row."""
    x, f = sub[..., 0], sub[..., 1]
    n1, n0 = f.sum(axis=0), (1 - f).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        dlt = (x * f).sum(axis=0) / n1 - (x * (1 - f)).sum(axis=0) / n0
    dlt = np.where((n1 > 0) & (n0 > 0), dlt, np.nan)
    return dlt / np.array([h for _, h in CELLS], dtype=float)


def compute_pbo(M: np.ndarray):
    """(PBOResult or None, reason). None means not computable: it counts as
    above 0.50."""
    try:
        return cscv(M, S=PBO_S, metric=pbo_metric), ""
    except ValueError as exc:
        return None, str(exc)


# ════════════════════════════════════════════════════════════════════════════
# Verdicts
# ════════════════════════════════════════════════════════════════════════════

def p_word(hold: Result, powered: bool, p_adj: float, disc_point: float, pre_point: float,
           pbo: float | None) -> tuple[str, list[str]]:
    """P on HOLDOUT, the registration's table top to bottom. pbo None = not
    computable, which counts as above 0.50. Returns (token, notes)."""
    if not powered or not hold.finite:
        return UNDERPOWERED, []
    if hold.hi < 0 and p_adj < ALPHA:
        return CONTRARY, []
    gain = hold.lo > 0 and p_adj < ALPHA
    disc_ok = math.isfinite(disc_point) and disc_point > 0
    pre_ok = math.isfinite(pre_point) and pre_point > 0
    pbo_ok = pbo is not None and math.isfinite(pbo) and pbo <= PBO_VETO
    if gain and disc_ok and pre_ok and not pbo_ok:
        return PBO_VETO_W, []
    if gain and disc_ok and pre_ok and pbo_ok:
        return SUPPORTED, []
    notes = []
    if gain and not disc_ok:
        notes.append("holdout gain, discovery sign disagrees")
    if gain and not pre_ok:
        notes.append("holdout gain, pre-book sign disagrees")
    return NULL, notes


def t_word(res: Result, powered: bool, p_adj: float, forward: bool = False) -> str:
    if not powered or not res.finite:
        return STILL_OPEN if forward else UNDERPOWERED
    if res.hi < 0 and p_adj < ALPHA:
        return DEEPER
    if res.lo > 0 and p_adj < ALPHA:
        return SHALLOWER
    return NULL


def z_word(res: Result, powered: bool, p_adj: float, forward: bool = False) -> str:
    if not powered or not res.finite:
        return STILL_OPEN if forward else UNDERPOWERED
    if res.lo > 0 and p_adj < ALPHA:
        return ABOVE_BETTER
    if res.hi < 0 and p_adj < ALPHA:
        return BELOW_BETTER
    return NULL


def p_forward_word(res: Result, powered: bool, p_adj: float) -> str:
    """FORWARD P: CI and Holm clauses only; no PBO, discovery or pre-book."""
    if not powered or not res.finite:
        return STILL_OPEN
    if res.hi < 0 and p_adj < ALPHA:
        return CONTRARY
    if res.lo > 0 and p_adj < ALPHA:
        return SUPPORTED
    return NULL


def holm3(res: dict, powered: dict) -> dict:
    """Holm over P, T and Z; an arm without power (or a finite CI) enters with p = 1."""
    pv = {a: (res[a].p if powered[a] and res[a].finite else 1.0) for a in ("P", "T", "Z")}
    return {a: v[0] for a, v in holm(pv).items()}


# ════════════════════════════════════════════════════════════════════════════
# Printed-only helpers
# ════════════════════════════════════════════════════════════════════════════

def newey_west(y: np.ndarray, dummy: np.ndarray, lags: int = NW_LAGS) -> tuple[float, float, float]:
    """OLS of y on [1, dummy]; (slope, Newey-West se, t) with Bartlett weights."""
    n = len(y)
    if n < 3 or dummy.min() == dummy.max():
        return float("nan"), float("nan"), float("nan")
    Xm = np.column_stack([np.ones(n), dummy.astype(float)])
    xtx_inv = np.linalg.inv(Xm.T @ Xm)
    beta = xtx_inv @ Xm.T @ y
    u = y - Xm @ beta
    g = Xm * u[:, None]
    S = g.T @ g
    for lag in range(1, min(lags, n - 1) + 1):
        w = 1.0 - lag / (lags + 1.0)
        G = g[lag:].T @ g[:-lag]
        S += w * (G + G.T)
    V = xtx_inv @ S @ xtx_inv
    se = math.sqrt(V[1, 1]) if V[1, 1] > 0 else float("nan")
    return float(beta[1]), se, float(beta[1] / se) if se == se and se > 0 else float("nan")


def first_of_week(dates: list[str]) -> set[int]:
    """Indices of the first session of each ISO week."""
    out, seen = set(), set()
    for i, d in enumerate(dates):
        k = date.fromisoformat(d).isocalendar()[:2]
        if k not in seen:
            seen.add(k)
            out.add(i)
    return out


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def check_era() -> None:
    requested = era_mod.requested_era()
    if requested != era_mod.CURRENT:
        raise Refused(era_mod.EXIT_THIN_ERA,
                      f"spy_dip_forward reads yfinance market closes, which carry no era; era "
                      f"{requested!r} does not apply — run it without --era. Exit 2.")


def ge_problems(cal: list[tuple]) -> list[str]:
    if not cal:
        return ["SPY.csv is empty"]
    out = []
    if cal[0][0] > SPY_START_LATEST:
        out.append(f"SPY starts {cal[0][0]}, after {SPY_START_LATEST}")
    after = sum(1 for r in cal if r[0] > GE_AFTER)
    if after < GE_MIN_AFTER:
        out.append(f"{after} sessions after {GE_AFTER}, fewer than {GE_MIN_AFTER}")
    return out


def gb_return_problems(cal: list[tuple]) -> list[str]:
    out = []
    for (d0, _, a0), (d1, _, a1) in zip(cal, cal[1:]):
        r = a1 / a0 - 1.0
        if abs(r) > GB_MAX_RET:
            out.append(f"{d1} adjusted return {r:+.2%}")
    return out


def _excepted(run: list[str]) -> bool:
    return any(all(a <= d <= b for d in run) for a, b in GM_EXCEPTIONS)


def gm_calendar_problems(dates: list[str]) -> list[str]:
    """No run of more than one missing weekday between sessions, except the
    listed closures."""
    out = []
    for d0, d1 in zip(dates, dates[1:]):
        x, e, run = date.fromisoformat(d0) + timedelta(days=1), date.fromisoformat(d1), []
        while x < e:
            if x.weekday() < 5:
                run.append(x.isoformat())
            x += timedelta(days=1)
        if len(run) > 1 and not _excepted(run):
            out.append(f"{len(run)} missing weekdays {run[0]} -> {run[-1]}")
    return out


def base_dates(path: Path) -> list[str]:
    out = []
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                v = float(r.get("spy_close") or "nan")
            except ValueError:
                continue
            if math.isfinite(v):
                out.append(r["date"][:10])
    return sorted(out)


def gm_base_problems(dates: list[str], path: Path) -> list[str]:
    """Every session of spy_base_rate_daily.csv is in the cache over their
    common span."""
    if not Path(path).exists():
        return [f"{_rel(path)} is missing"]
    bd = base_dates(path)
    if not bd or not dates:
        return [f"{_rel(path)} or the cache is empty"]
    a, b = max(bd[0], dates[0]), min(bd[-1], dates[-1])
    have = set(dates)
    return [f"{d} is in {Path(path).name} but not the cache" for d in bd if a <= d <= b and d not in have]


@dataclass
class GsRead:
    common: int
    band: int
    hard: list[str]


def gs_compare(dates: list[str], closes: list[float], flag: list, table_flags: dict) -> GsRead:
    """Cache SMA50 flag against a shipped table's, on common dates where both
    are defined. A mismatch with |close / SMA - 1| >= 0.0005 is hard."""
    common, band, hard = 0, 0, []
    for i, d in enumerate(dates):
        t = table_flags.get(d)
        if t is None or flag[i] is None:
            continue
        common += 1
        if t == flag[i]:
            continue
        sma = sma_at(closes, i, 50)
        if sma and abs(closes[i] / sma - 1.0) < GS_BAND:
            band += 1
        else:
            hard.append(f"{d} cache {flag[i]} vs table {t}")
    return GsRead(common, band, hard)


def table_flags(path: Path) -> dict:
    return {r["date"][:10]: r["spy_below_sma"] for r in compute_mech_table(path)}


@dataclass
class GiRead:
    problems: list[str]
    max_carry: int
    span: tuple[str, str] | None
    common: int
    nonpositive: int


def gi_problems(d: Data, first_entry: int, last_end: int, irx: dict, other: dict | None) -> GiRead:
    """^IRX covers every session first_entry..last_end, no carry over 5
    sessions, and the two copies agree within 0.01 on common dates."""
    out = []
    if first_entry > last_end:
        return GiRead(["no entry session to cover"], 0, None, 0, 0)
    seg_y, seg_own = d.y[first_entry:last_end + 1], d.own_irx[first_entry:last_end + 1]
    if not np.all(np.isfinite(seg_y)):
        out.append(f"no ^IRX close on or before {d.dates[first_entry]}")
    run = mx = 0
    worst = None
    for j, o in enumerate(seg_own):
        run = 0 if o else run + 1
        if run > mx:
            mx, worst = run, d.dates[first_entry + j]
    if mx > GI_MAX_CARRY:
        out.append(f"^IRX carried {mx} sessions (to {worst}), more than {GI_MAX_CARRY}")
    common = 0
    if other is not None:
        for k, v in irx.items():
            w = other.get(k)
            if w is None:
                continue
            common += 1
            if abs(v - w) > GI_TOL + 1e-12:
                out.append(f"{k} ^IRX copies differ: {v:.4f} vs {w:.4f}")
    nonpos = sum(1 for k, v in irx.items() if v <= 0
                 and d.dates[first_entry] <= k <= d.dates[last_end])
    return GiRead(out, mx, (d.dates[first_entry], d.dates[last_end]), common, nonpos)


# ════════════════════════════════════════════════════════════════════════════
# Inputs
# ════════════════════════════════════════════════════════════════════════════

def load_inputs(refresh: bool) -> tuple[list, dict, dict | None, Path]:
    """(SPY rows, the ^IRX copy read, the other copy or None, path read)."""
    if refresh:
        for name, path in (("SPY", SPY_CSV), ("IRX", IRX_OWN)):
            try:
                fetch_series(name, path)
            except Refused:
                raise
            except Exception as exc:  # network, yfinance schema
                raise refuse("GE", f"fetching {FETCH[name][0]} failed ({exc})")
    if not SPY_CSV.exists():
        raise refuse("GE", f"{_rel(SPY_CSV)} is missing; pass --refresh to fetch it")
    spy = read_spy(SPY_CSV)
    if IRX_OWN.exists():
        irx_path, other = IRX_OWN, (read_irx(IRX_TREND) if IRX_TREND.exists() else None)
    elif IRX_TREND.exists():
        irx_path, other = IRX_TREND, None
    else:
        raise refuse("GI", "no ^IRX copy on disk; pass --refresh to fetch one")
    return spy, read_irx(irx_path), other, irx_path


def _span(path: Path, col: str = "date") -> str:
    first = last = None
    n = 0
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            d = (r.get(col) or "")[:10]
            if not d:
                continue
            n += 1
            first = d if first is None or d < first else first
            last = d if last is None or d > last else last
    mtime = datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"  {n:>6,} rows  {first} -> {last}  {mtime}  {_rel(path)}"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
# ════════════════════════════════════════════════════════════════════════════

def section(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def pp(x: float, nd: int = 3) -> str:
    return "—" if x is None or not math.isfinite(x) else f"{100 * x:+.{nd}f}%"


def ci(r: Result, fmt=pp) -> str:
    return f"[{fmt(r.lo)}, {fmt(r.hi)}]" if r.finite else "[—]"


def num(x: float, nd: int = 4) -> str:
    return "—" if x is None or not math.isfinite(x) else f"{x:+.{nd}f}"


def res_line(r: Result, fmt=pp) -> str:
    return f"{fmt(r.point)} {ci(r, fmt)}  p {r.p:.4f}  (n {r.n}, NaN draws {r.nan_share:.2%})"


def short(r: Result, fmt=pp) -> str:
    return f"{fmt(r.point)} {ci(r, fmt)}"


def print_refusal_banner(gate: str) -> None:
    section("VERDICT")
    for arm in ("P", "T", "Z"):
        print(f"  >>> spy_dip_forward {arm} ({BANNER[arm]}): REFUSED ({gate}) <<<")


# ════════════════════════════════════════════════════════════════════════════
# The run
# ════════════════════════════════════════════════════════════════════════════

def run_gates(spy: list, irx: dict, other: dict | None, irx_path: Path) -> Data:
    section("GATES — refusals (GE, GB, GM, GS, GI, GX)")
    cal = calendar_rows(spy)
    probs = ge_problems(cal)
    if probs:
        for line in probs:
            print(f"  GE: {line}")
        raise refuse("GE", "; ".join(probs))
    after = sum(1 for r in cal if r[0] > GE_AFTER)
    print(f"  GE: {len(cal)} sessions {cal[0][0]} -> {cal[-1][0]} ({len(spy) - len(cal)} "
          f"dropped with no Adj Close); {after} sessions after {GE_AFTER} (floor {GE_MIN_AFTER}) — PASS")

    rp = ratio_problems(cal) + gb_return_problems(cal)
    if rp:
        for line in rp[:10]:
            print(f"  GB: {line}")
        raise refuse("GB", f"{len(rp)} basis problems (first: {rp[0]})")
    print(f"  GB: close/adj ratio never steps like a split; no adjusted daily return beyond "
          f"±{GB_MAX_RET:.0%} — PASS")

    dates = [r[0] for r in cal]
    closes = [float(r[1]) for r in cal]
    gm = gm_calendar_problems(dates) + gm_base_problems(dates, BASE_RATE_CSV)
    if BASE_RATE_CSV.exists():
        bp_, n_bp = base_rate_problems(cal, {}, BASE_RATE_CSV)
        gm += bp_
    else:
        n_bp = 0
    if gm:
        for line in gm[:10]:
            print(f"  GM: {line}")
        raise refuse("GM", f"{len(gm)} calendar problems (first: {gm[0]})")
    print(f"  GM: no unlisted run of missing weekdays (listed: "
          f"{', '.join(a + '..' + b for a, b in GM_EXCEPTIONS)}); every base-rate session in "
          f"the cache over the common span; {n_bp} common closes within 0.5% — PASS")

    flags = all_flags(dates, closes)
    helper = [below_sma_at(closes, i, 50) for i in range(len(closes))]
    n_help = sum(1 for a, b in zip(helper, flags["SMA50"]) if a != b)
    hard_all = []
    for path in (VIX_FULL_CSV, BASE_RATE_CSV):
        if not Path(path).exists():
            raise refuse("GS", f"{_rel(path)} is missing")
        g = gs_compare(dates, closes, flags["SMA50"], table_flags(path))
        print(f"  GS: {Path(path).name}: {g.common} common flagged dates, {len(g.hard)} hard "
              f"mismatches, {g.band} inside the ±{GS_BAND} band (cache flag used)")
        hard_all += g.hard
    if hard_all:
        for line in hard_all[:10]:
            print(f"    {line}")
        raise refuse("GS", f"{len(hard_all)} SMA50 mismatches outside the band (first: {hard_all[0]})")
    print(f"  GS: SMA50 from compute_mech_table matches the shipped tables — PASS "
          f"(own helper at N=50 differs on {n_help} sessions)")

    d = build_data(cal, irx, flags)
    defined = [i for i in range(d.n) if any(flags[k][i] is not None for k in DEFS)]
    first_entry = defined[0] + 1 if defined else d.n
    gi = gi_problems(d, first_entry, d.n - 1, irx, other)
    if gi.problems:
        for line in gi.problems[:10]:
            print(f"  GI: {line}")
        raise refuse("GI", f"{len(gi.problems)} T-bill problems (first: {gi.problems[0]})")
    other_txt = (f"{gi.common} common dates with {_rel(IRX_TREND)}, all within {GI_TOL}"
                 if other is not None else "one copy on disk")
    print(f"  GI: ^IRX from {_rel(irx_path)} covers {gi.span[0]} -> {gi.span[1]}; longest carry "
          f"{gi.max_carry} sessions (limit {GI_MAX_CARRY}); {other_txt}; {gi.nonpositive} "
          f"quotes at or below zero used as printed — PASS")

    try:
        n_gx = gx_check(dates, closes, flags)
    except LookaheadError as exc:
        raise refuse("GX", str(exc))
    print(f"  GX: every flag and the 200-day regime equal on the series cut at D, {n_gx} "
          f"sessions checked — PASS")
    print("  era: current — PASS")
    return d


def census_line(r: Rows) -> str:
    c = r.census
    return (f"counted {c['counted']} (D {c['first']} -> {c['last']}), gap {c['gap']}, "
            f"open {c['open']}, no D+1 {c['no_entry']}")


def print_arms(label: str, res: dict, holm_adj: dict | None = None) -> None:
    for a in ("P", "T", "Z"):
        if a not in res:
            continue
        hj = f", Holm {holm_adj[a]:.4f}" if holm_adj else ""
        print(f"    {a}  {res_line(res[a])}{hj}")


def run(refresh: bool = False, registered: str | None = None) -> int:
    registered = registered or REGISTERED
    check_era()
    spy, irx, other, irx_path = load_inputs(refresh)
    win = windows(registered)

    print("spy_dip_forward — do SPY entries on dip dates do better over the next month, 1993 on?")
    print(f"registration: {REGISTRATION} (registered {registered})")
    print("era: current (inputs are unversioned market data)")
    dirty = "dirty" if _git("status", "--porcelain") else "clean"
    print(f"git: {_git('rev-parse', '--short', 'HEAD')} "
          f"({_git('rev-parse', '--abbrev-ref', 'HEAD')}, working tree {dirty})")
    print("inputs read:")
    for p in (SPY_CSV, irx_path, *([IRX_TREND] if other is not None else []),
              VIX_FULL_CSV, BASE_RATE_CSV):
        if Path(p).exists():
            print(_span(p))
    print("SEAL: not applied — no play, tier, R or backtest row is read")
    print(f"cost {COST * 1e4:.0f} bps round trip; block bootstrap L = max(63, 2h), {BOOT_N} "
          f"draws, seed {SEED}; Holm m = 3 (P, T, Z)")

    d = run_gates(spy, irx, other, irx_path)
    print(f"  SPY sessions {d.dates[0]} -> {d.dates[-1]} ({d.n}); first SMA50 flag "
          f"{d.dates[next(i for i, v in enumerate(d.flags[PRIMARY]) if v is not None)]}")

    # ── rows, power, arms ───────────────────────────────────────────────────
    rows = {w: build_rows(d, w, H, PRIMARY, registered) for w in WINDOW_ORDER}
    power = {w: gn(rows[w]) for w in WINDOW_ORDER}
    power_z = {w: gn_z(rows[w]) for w in WINDOW_ORDER}
    res = {w: measure(rows[w]) for w in ("DISCOVERY", "HOLDOUT", "PRE-BOOK", "2026")}

    section("WINDOWS — signal dates and entry census (SMA50, h = 21)")
    n_ep = int(d.ep.max()) + 1 if d.ep.max() >= 0 else 0
    print(f"  dip episodes on the whole series: {n_ep} (an episode ends after more than "
          f"{EPISODE_GAP} non-dip sessions in a row)")
    for w in WINDOW_ORDER:
        a, b = win[w]
        print(f"  {w:<9} D {a if a != FAR_PAST else 'first flag'} -> "
              f"{b if b != FAR_FUTURE else 'data end'}: {census_line(rows[w])}")
    for w in ("DISCOVERY", "HOLDOUT", "PRE-BOOK", "2026", "FORWARD"):
        for h in HORIZONS:
            if h == H:
                continue
            r = build_rows(d, w, h, PRIMARY, registered)
            print(f"    {w} h={h}: {census_line(r)}")

    section("POWER — GN per window (SMA50, h = 21)")
    for w in ("DISCOVERY", "HOLDOUT", "FORWARD"):
        pw, pz = power[w], power_z[w]
        print(f"  {w}: {pw.episodes} episodes (floor {MIN_EPISODES}), {pw.dip} dip entries "
              f"(floor {MIN_DIP}), {pw.nondip} non-dip (floor {MIN_NONDIP}), largest episode "
              f"{pw.largest} dip entries (cap {pw.dip / 3:.0f}) — {'pass' if pw.ok else 'FAIL'}")
        if w != "DISCOVERY":
            print(f"    GN for Z: episodes above-200 {pz.ep_above} / below-200 {pz.ep_below} "
                  f"(floor {Z_MIN_EPISODES} each), dip entries above {pz.n_above} / below "
                  f"{pz.n_below} (floor {Z_MIN_ENTRIES} each) — {'pass' if pz.ok else 'FAIL'}")

    if not draws_match_block_indices(rows["HOLDOUT"].n, block_len(H)):
        raise RuntimeError("bootstrap draws do not reproduce tail_breach.block_indices")
    print(f"  bootstrap: drawn rows reproduce tail_breach.block_indices (checked at n "
          f"{rows['HOLDOUT'].n}, L {block_len(H)})")

    hold = res["HOLDOUT"]
    powered = {"P": power["DISCOVERY"].ok and power["HOLDOUT"].ok and hold["P"].finite,
               "T": power["HOLDOUT"].ok and hold["T"].finite,
               "Z": power_z["HOLDOUT"].ok and hold["Z"].finite}
    adj = holm3(hold, powered)

    # ── PBO ─────────────────────────────────────────────────────────────────
    M, kept, dropped = pbo_matrix(d)
    pbo_res, pbo_err = compute_pbo(M)
    pbo_val = pbo_res.pbo if pbo_res is not None else None

    words = {}
    words["P"], p_notes = p_word(hold["P"], powered["P"], adj["P"], res["DISCOVERY"]["P"].point,
                                 res["PRE-BOOK"]["P"].point, pbo_val)
    words["T"] = t_word(hold["T"], powered["T"], adj["T"])
    words["Z"] = z_word(hold["Z"], powered["Z"], adj["Z"])

    section("HOLDOUT — graded (signal dates 2010-01-01 to 2025-12-31)")
    print(f"  {hold['P'].n} entries: {power['HOLDOUT'].dip} dip, {power['HOLDOUT'].nondip} non-dip; "
          f"L = {block_len(H)} rows")
    print_arms("HOLDOUT", hold, adj)
    print("  Holm family m = 3 (P, T, Z); an UNDERPOWERED arm enters with p = 1.")
    for a in ("P", "T", "Z"):
        print(f"    {a}: unadjusted p {hold[a].p:.4f}, Holm-adjusted p {adj[a]:.4f} -> {words[a]}")
    for note in p_notes:
        print(f"  P note: {note}")

    section("DISCOVERY and PRE-BOOK — sign checks for P only (CIs print, do not gate)")
    print(f"  DISCOVERY (to 2009-12-31), {res['DISCOVERY']['P'].n} entries:")
    print_arms("DISCOVERY", res["DISCOVERY"])
    print(f"  PRE-BOOK (2010-01-01 to 2023-12-31), {res['PRE-BOOK']['P'].n} entries:")
    print_arms("PRE-BOOK", res["PRE-BOOK"])

    section("PBO / CSCV — 12 cells (4 definitions x 3 horizons), S = 16, metric Delta_h / h")
    if kept:
        print(f"  rows: D {d.dates[kept[0]]} -> {d.dates[kept[-1]]} ({len(kept)} rows; "
              f"{dropped} oldest dropped so 16 divides the count); last 63-session window ends "
              f"{d.dates[kept[-1] + 1 + max(HORIZONS)]}")
    if pbo_res is None:
        print(f"  PBO not computable ({pbo_err}); counts as above {PBO_VETO:.2f} (veto)")
    else:
        bar = ("veto" if pbo_val > PBO_VETO else "selection fragile" if pbo_val > PBO_FRAGILE
               else "below the fragile bar")
        share = pbo_res.selection_share()
        top = sorted(range(len(CELLS)), key=lambda c: -share[c])[:4]
        print(f"  PBO {pbo_val:.4f} over {pbo_res.n_combinations} combinations "
              f"({pbo_res.n_at_zero} at lambda 0) — {bar}")
        print("  IS-best share: " + ", ".join(f"{cell_label(*CELLS[c])} {share[c]:.3f}" for c in top))
        print(f"  degradation slope {num(pbo_res.slope, 3)}; P(OOS loss) "
              f"{pbo_res.prob_loss if pbo_res.prob_loss is None else round(pbo_res.prob_loss, 4)}")

    # ── printed only ────────────────────────────────────────────────────────
    section("PRINTED ONLY — no verdict")
    print("  LEVELS  mean net X_h: dip / non-dip / all (SMA50)")
    for w in WINDOW_ORDER:
        for h in HORIZONS:
            r = rows[w] if h == H else build_rows(d, w, h, PRIMARY, registered)
            print(f"    {w:<9} h={h:<2}  {pp(_mean(r.x[r.f == 1]))} / {pp(_mean(r.x[r.f == 0]))} / "
                  f"{pp(_mean(r.x))}  (dip {int((r.f == 1).sum())}, non-dip {int((r.f == 0).sum())})")
    for w in ("DISCOVERY", "HOLDOUT", "PRE-BOOK"):
        r = rows[w]
        dip, non = r.f == 1, r.f == 0
        print(f"  {w}")
        print(f"    HIT        X_21 > 0: dip {_mean((r.x[dip] > 0).astype(float)):.3f}, non-dip "
              f"{_mean((r.x[non] > 0).astype(float)):.3f}")
        print(f"    TAIL-RET   q10 X_21 dip minus non-dip {pp(_q(r.x[dip]) - _q(r.x[non]))}")
        print(f"    MAE-MEAN   mean MAE_21 dip minus non-dip {pp(_mean(r.mae[dip]) - _mean(r.mae[non]))}")
    vol = {}
    for w in ("DISCOVERY", "HOLDOUT"):
        r = rows[w]
        ok = np.isfinite(r.vs)
        vol[w] = measure(r.subset(ok), arms=("P",), value="vs")["P"]
        print(f"  VOL-SCALED {w}: P on X_21 / (sigma_D x sqrt 21) {res_line(vol[w], num)}")
    fow = first_of_week(d.dates)
    for w in ("DISCOVERY", "HOLDOUT"):
        r = rows[w]
        keep = np.array([int(i) in fow for i in r.i], dtype=bool)
        wk = measure(r.subset(keep), arms=("P",), L=WEEKLY_BLOCK)["P"]
        sp = measure(r.subset(np.arange(r.n) % SPACED_STEP == 0), arms=("P",), L=SPACED_BLOCK)["P"]
        print(f"  WEEKLY {w}: P {res_line(wk)} (first session of each ISO week, blocks of "
              f"{WEEKLY_BLOCK})")
        print(f"  SPACED {w}: P {res_line(sp)} (every {SPACED_STEP}th entry, blocks of {SPACED_BLOCK})")
    for w in ("DISCOVERY", "HOLDOUT"):
        r = rows[w]
        dip = r.f == 1
        parts = []
        for lab, m in (("1st", r.ordn == 1), ("2nd-5th", (r.ordn >= 2) & (r.ordn <= 5)),
                       ("6th on", r.ordn >= 6)):
            parts.append(f"{lab} {pp(_mean(r.x[dip & m]))} (n {int((dip & m).sum())})")
        print(f"  ORDINAL {w}: mean X_21 by dip session within its episode: " + ", ".join(parts))
    for w in ("DISCOVERY", "HOLDOUT"):
        r = rows[w]
        cells = []
        for fl, fn in ((1, "dip"), (0, "non-dip")):
            for rg, rn in ((1, "above-200"), (0, "below-200")):
                m = (r.f == fl) & (r.reg == rg)
                cells.append(f"{fn}/{rn} {pp(_mean(r.x[m]))} (n {int(m.sum())})")
        print(f"  REGIME-2X2 {w}: " + "; ".join(cells))
    for w in ("DISCOVERY", "HOLDOUT"):
        r = rows[w]
        b, se, t = newey_west(r.x, r.f, NW_LAGS)
        print(f"  NW {w}: OLS slope on the dip dummy {pp(b)}, Newey-West se {pp(se)}, t {num(t, 3)} "
              f"({NW_LAGS} lags)")
    L0 = block_len(H)
    for L in (L0 // 2, 2 * L0):
        bl = measure(rows["HOLDOUT"], L=L)
        print(f"  BLOCKS HOLDOUT L={L}: P {short(bl['P'])}  T {short(bl['T'])}  Z {short(bl['Z'])}")
    for w in ("DISCOVERY", "HOLDOUT"):
        r = rows[w]
        years = sorted({d.dates[int(i)][:4] for i in r.i})
        yv = {}
        for y in years:
            m = np.array([d.dates[int(i)][:4] == y for i in r.i], dtype=bool)
            yv[y] = arm_p(r.x[m], r.f[m])
        pos = sum(1 for v in yv.values() if math.isfinite(v) and v > 0)
        fin = sum(1 for v in yv.values() if math.isfinite(v))
        print(f"  YEARS {w}: Delta_21 above 0 in {pos} of {fin} years with both groups")
        print("    " + "  ".join(f"{y} {pp(v, 2)}" for y, v in yv.items()))
    print("  GRID  Delta_h and Delta_h / h per cell, CI and unadjusted p; no token")
    for w in ("DISCOVERY", "HOLDOUT", "PRE-BOOK", "2026"):
        head = "2026 (contaminated, not graded)" if w == "2026" else w
        print(f"    {head}")
        for dfn, h in CELLS:
            r = build_rows(d, w, h, dfn, registered)
            g = measure(r, arms=("P",))["P"]
            print(f"      {cell_label(dfn, h):<9} {pp(g.point)} {ci(g)}  per session "
                  f"{pp(g.point / h, 4)}  p {g.p:.4f}  (dip {int((r.f == 1).sum())}, "
                  f"non-dip {int((r.f == 0).sum())})")

    section("2026 (contaminated, not graded)")
    r26 = rows["2026"]
    print(f"  {census_line(r26)}; dip {int((r26.f == 1).sum())}, non-dip {int((r26.f == 0).sum())}")
    print_arms("2026", res["2026"])

    section("FORWARD — entries after the registration date")
    rf = rows["FORWARD"]
    pf, pzf = power["FORWARD"], power_z["FORWARD"]
    print(f"  {census_line(rf)}; {pf.episodes} episodes, {pf.dip} dip, {pf.nondip} non-dip "
          f"entries (floors {MIN_EPISODES} / {MIN_DIP} / {MIN_NONDIP})")
    f_pow = {"P": pf.ok, "T": pf.ok, "Z": pzf.ok}
    if any(f_pow.values()):
        fres = measure(rf)
        f_pow = {a: f_pow[a] and fres[a].finite for a in f_pow}
        fadj = holm3(fres, f_pow)
        print_arms("FORWARD", fres, fadj)
        fw = {"P": p_forward_word(fres["P"], f_pow["P"], fadj["P"]),
              "T": t_word(fres["T"], f_pow["T"], fadj["T"], forward=True),
              "Z": z_word(fres["Z"], f_pow["Z"], fadj["Z"], forward=True)}
    else:
        fw = {"P": STILL_OPEN, "T": STILL_OPEN, "Z": STILL_OPEN}
    print(f"  forward: P {fw['P']} T {fw['T']} Z {fw['Z']}")

    # ── verdict ─────────────────────────────────────────────────────────────
    section("VERDICT")
    print(f"  HOLDOUT: {hold['P'].n} SMA50 entries (D {rows['HOLDOUT'].census['first']} -> "
          f"{rows['HOLDOUT'].census['last']}); SPY sessions to {d.dates[-1]}; {BOOT_N} block "
          f"draws (L {block_len(H)}), seed {SEED}")
    for note in p_notes:
        print(f"  {note}")
    if pbo_val is not None and PBO_FRAGILE < pbo_val <= PBO_VETO:
        print("  PBO: selection fragile")
    print()
    for a in ("P", "T", "Z"):
        print(f"  >>> spy_dip_forward {a} ({BANNER[a]}): {words[a]} <<<")
    disc = res["DISCOVERY"]
    print(f"  >>> spy_dip_forward DISCOVERY (to 2009-12-31): P {short(disc['P'])} "
          f"T {short(disc['T'])} Z {short(disc['Z'])} <<<")
    print(f"  >>> spy_dip_forward PRE-BOOK (2010-2023): P {short(res['PRE-BOOK']['P'])} <<<")
    pbo_txt = f"{pbo_val:.4f}" if pbo_val is not None else "not computable (veto)"
    print(f"  >>> spy_dip_forward PBO (12 cells, S=16, 1993-2025): {pbo_txt} <<<")
    print(f"  >>> spy_dip_forward 2026 (contaminated, not graded): P {short(res['2026']['P'])}, "
          f"{int((r26.f == 1).sum())} dip entries <<<")
    print(f"  >>> spy_dip_forward FORWARD (entries after the registration date): "
          f"P {fw['P']} T {fw['T']} Z {fw['Z']} <<<")
    print()
    print("  SUPPORTED needs the HOLDOUT CI wholly above 0 with a Holm-adjusted p below 0.05,")
    print("  positive DISCOVERY and PRE-BOOK point estimates, and a PBO of at most 0.50.")
    print("  Levels are net of 4 bps round trip, in excess of T-bills. Nothing ships from this")
    print("  study (spy_dip_forward.md).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="refetch SPY and ^IRX from yfinance into backtests/spy_dip_forward/")
    args = ap.parse_args(argv)
    try:
        return run(refresh=args.refresh)
    except Refused as exc:
        print(f"REFUSED ({exc.message})")
        if exc.gate:
            print_refusal_banner(exc.gate)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
