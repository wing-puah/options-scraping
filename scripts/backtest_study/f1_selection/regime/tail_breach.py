"""tail_breach — how often does SPY fall more than twice its VIX-implied move, and can it be forecast?

REGISTERED 2026-11-14, accepted by default the same day:
research/pre-registrations/f1_selection/regime/tail_breach.md. Every constant,
floor, seed and verdict word below is that file's. Read it before changing
anything here. Test rows end on or before the registration date; forward rows
start after it; rows between are in neither window.

WHAT IT ASKS
------------
A down breach on session t is a log total return below -k x VIX(t-1)/100/sqrt(252),
k = 2: SPY fell more than twice the one-day move the prior close's VIX implied.

Part 1 measures: breach count and rate per calendar year 2024, 2025, 2026 YTD
(Wilson 95% CI) against the normal-law rate, and a clustering read (share of
breaches with another breach in the 5 sessions before, against independence).
Printed beside it: k = 1.5 and 2.5, a fixed -2% day, a 5-session window breach
and the upside mirror. Descriptive; no verdict.

Part 2 forecasts. From the close of t-1 (the origin), four predictors:
X1 VIX level, X2 VIX trailing-252-session midrank percentile, X3 VIX/VIX3M,
X4 20-session realized SPY vol / VIX. Outcome Y5: any down breach in t..t+4.
P is a logistic regression on all four (standardised on training rows); S1-S4
each predictor alone (Holm m = 4); N1 the four-predictor model on the next
session only. Coefficients are fitted on outcome windows that end before
2024-01-02 and never refitted. Metric: Brier skill score against the training
base rate, 95% moving-block bootstrap CI (block 21, 10,000 draws).

DATA
----
yfinance, auto_adjust=False (the fetch pattern of `regime_confirm` and
`scripts/regime_watch.py`), cached in `backtests/tail_breach/<name>.csv`
(date, close, adj_close). Returns use `adj_close` (dividend-adjusted total
return); the unadjusted close prints as a BASIS twin. GB checks the cached
unadjusted SPY close and VIX against `backtests/mech_regime/spy_base_rate_daily.csv`
and refuses a feed whose close/adj ratio steps like a split. A missing file is
fetched; `--refresh` refetches all three. Today's bar is never fetched
(yfinance's `end` is exclusive), so every close is a finished session.

The holdout seal does not apply: no flow signal, play or backtest row is read.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run tail_breach
    python -m scripts.backtest_study run tail_breach -- --refresh
"""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection.benchmark.ticker_class import holm  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib.ruin_walk import wilson  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/tail_breach.md"
# The registration date. Test rows: last outcome session on or before it.
# Forward rows: origin after it. None would mean an unaccepted draft.
REGISTERED: str | None = "2026-11-14"

# --- constants fixed by the registration -------------------------------------
K = 2.0                     # primary breach multiple of the VIX-implied 1-day move
K_PARAMS = (1.5, 2.5)       # printed beside it, no verdict
FIXED_DROP = -0.02          # secondary: simple total return below -2%
HORIZON = 5                 # Y5: any breach in t..t+4
WINDOW = 5                  # 5-session window breach
CLUSTER = 5                 # sessions back for the clustering read and episode chaining
PCT_WINDOW = 252            # X2's trailing window, sessions strictly before the origin
RV_WINDOW = 20              # X4's realized-vol window, returns ending at the origin
TRADING_DAYS = 252
TEST_START = "2024-01-02"
YEARS = ("2024", "2025", "2026")
BLOCK = 21                  # moving-block bootstrap block, sessions
BLOCK_SENS = (10, 42)       # printed only
BOOT_N = 10_000
SEED = 20261114
ALPHA = 0.05
MIN_TRAIN_ROWS = 2_500      # GT
MIN_TRAIN_EPISODES = 30     # GT
MIN_TEST_EPISODES = 10      # GN
FWD_MIN_ROWS = 250          # FORWARD
FWD_MIN_EPISODES = 10       # FORWARD
BASIS_TOL = 0.005           # GB: cached close vs spy_base_rate_daily, relative
RATIO_STEP_MAX = 0.02       # GB: largest day-to-day change in close/adj_close
RATIO_UP_TOL = 1e-4         # GB: close/adj_close may only fall (dividends)
GX_SAMPLE = 60              # GX: origins re-checked on a series cut at the origin

CACHE_DIR = ROOT / "backtests" / "tail_breach"
BASE_RATE_CSV = ROOT / "backtests" / "mech_regime" / "spy_base_rate_daily.csv"
SERIES = {
    "SPY": ("SPY", "1993-01-01"),
    "VIX": ("^VIX", "1990-01-01"),
    "VIX3M": ("^VIX3M", "2006-01-01"),
}

PREDICTORS = ("X1", "X2", "X3", "X4")
PRED_NAME = {"X1": "VIX level", "X2": "VIX 252-session percentile",
             "X3": "VIX/VIX3M", "X4": "20-session realized vol / VIX"}
SINGLES = {"S1": ("X1",), "S2": ("X2",), "S3": ("X3",), "S4": ("X4",)}

PREDICTABLE, NO_FORECAST = "PREDICTABLE", "NO-FORECAST"
UNDERPOWERED, STILL_OPEN = "UNDERPOWERED", "STILL-OPEN"
RULE = "=" * 78

# Exit 2: any era but `current`. Exit 3: an input missing or unfetchable, or GB.
# The study has no era to mismatch; it reuses era.py's exit-3 code for input
# refusals so the runner files them as designed refusals.
EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}


class Refused(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════════════════════════════════════════════════════════════
# Data
# ════════════════════════════════════════════════════════════════════════════

def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.csv"


def fetch_series(name: str, end: str | None = None) -> Path:
    """yfinance -> `backtests/tail_breach/<name>.csv`. `end` is exclusive."""
    import pandas as pd
    import yfinance as yf
    sym, start = SERIES[name]
    end = end or date.today().isoformat()
    df = yf.download(sym, start=start, end=end, auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise Refused(EXIT_INPUT, f"GE: yfinance returned no rows for {sym}. Exit 3.")

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


def read_series(path: Path) -> list[tuple[str, float, float | None]]:
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
    """The SPY session calendar with VIX and VIX3M aligned by exact date."""
    dates: list[str]
    close: np.ndarray          # unadjusted SPY close
    adj: np.ndarray            # dividend-adjusted SPY close (total return)
    vix: np.ndarray            # NaN where VIX has no close on that session
    vix3m: np.ndarray          # NaN where VIX3M has no close on that session
    pos: dict = field(default_factory=dict)

    def __post_init__(self):
        self.pos = {d: i for i, d in enumerate(self.dates)}

    @property
    def n(self) -> int:
        return len(self.dates)


def build_cal(spy: list[tuple], vix: dict[str, float], vix3m: dict[str, float]) -> Cal:
    rows = [r for r in spy if r[2] is not None]
    return Cal(dates=[r[0] for r in rows],
               close=np.array([r[1] for r in rows], dtype=float),
               adj=np.array([r[2] for r in rows], dtype=float),
               vix=np.array([vix.get(r[0], np.nan) for r in rows], dtype=float),
               vix3m=np.array([vix3m.get(r[0], np.nan) for r in rows], dtype=float))


def log_returns(px: np.ndarray) -> np.ndarray:
    """ret[i] = ln(px[i] / px[i-1]); NaN at 0."""
    out = np.full(len(px), np.nan)
    if len(px) > 1:
        out[1:] = np.log(px[1:] / px[:-1])
    return out


# ════════════════════════════════════════════════════════════════════════════
# Breach definitions. Each returns a float array: 1.0, 0.0, or NaN (undefined).
# ════════════════════════════════════════════════════════════════════════════

def implied_sigma(cal: Cal) -> np.ndarray:
    """sigma[i] = VIX(i-1)/100/sqrt(252): the prior close's implied 1-day move."""
    s = np.full(cal.n, np.nan)
    if cal.n > 1:
        s[1:] = cal.vix[:-1] / 100.0 / math.sqrt(TRADING_DAYS)
    return s


def _flag(cond: np.ndarray, defined: np.ndarray) -> np.ndarray:
    out = np.where(cond, 1.0, 0.0)
    out[~defined] = np.nan
    return out


def breach_down(cal: Cal, k: float = K, basis: str = "adj") -> np.ndarray:
    r = log_returns(cal.adj if basis == "adj" else cal.close)
    s = implied_sigma(cal)
    ok = np.isfinite(r) & np.isfinite(s) & (s > 0)
    with np.errstate(invalid="ignore"):
        return _flag(r < -k * s, ok)


def breach_up(cal: Cal, k: float = K) -> np.ndarray:
    r = log_returns(cal.adj)
    s = implied_sigma(cal)
    ok = np.isfinite(r) & np.isfinite(s) & (s > 0)
    with np.errstate(invalid="ignore"):
        return _flag(r > k * s, ok)


def breach_fixed(cal: Cal, drop: float = FIXED_DROP) -> np.ndarray:
    r = log_returns(cal.adj)
    ok = np.isfinite(r)
    with np.errstate(invalid="ignore"):
        return _flag(r < math.log(1.0 + drop), ok)


def breach_window(cal: Cal, k: float = K, w: int = WINDOW) -> np.ndarray:
    """Indexed by the window's FIRST session t: ln(adj[t+w-1] / adj[t-1]) below
    -k x VIX(t-1)/100 x sqrt(w/252). Undefined when t+w-1 is past the data."""
    out = np.full(cal.n, np.nan)
    for t in range(1, cal.n - w + 1):
        v = cal.vix[t - 1]
        if not (math.isfinite(v) and v > 0):
            continue
        r = math.log(cal.adj[t + w - 1] / cal.adj[t - 1])
        out[t] = 1.0 if r < -k * v / 100.0 * math.sqrt(w / TRADING_DAYS) else 0.0
    return out


def normal_rate(k: float) -> float:
    """P(Z < -k) under a standard normal law."""
    return 0.5 * math.erfc(k / math.sqrt(2.0))


def fixed_implied_rate(cal: Cal, idx: list[int], drop: float = FIXED_DROP) -> float:
    """Mean over sessions of the normal-law chance of a -2% day at that session's sigma."""
    s = implied_sigma(cal)
    vals = [normal_rate(-math.log(1.0 + drop) / s[i]) for i in idx if math.isfinite(s[i]) and s[i] > 0]
    return float(np.mean(vals)) if vals else float("nan")


# ════════════════════════════════════════════════════════════════════════════
# Part 1 — measurement
# ════════════════════════════════════════════════════════════════════════════

def episodes(breach_idx: list[int], gap: int = CLUSTER) -> int:
    """Independent episodes: a breach starts a new one when the previous breach
    is more than `gap` sessions before it."""
    n, last = 0, None
    for i in sorted(breach_idx):
        if last is None or i - last > gap:
            n += 1
        last = i
    return n


def cluster_share(b: np.ndarray, idx: list[int], back: int = CLUSTER) -> tuple[int, int]:
    """(breaches with another breach in the `back` sessions before, breaches in idx)."""
    hits = [i for i in idx if b[i] == 1.0]
    near = sum(1 for i in hits if any(b[j] == 1.0 for j in range(max(0, i - back), i)))
    return near, len(hits)


def independent_share(p: float, back: int = CLUSTER) -> float:
    return 1.0 - (1.0 - p) ** back if math.isfinite(p) else float("nan")


@dataclass
class YearRow:
    label: str
    n: int
    k: int
    lo: float
    hi: float
    near: int
    episodes: int

    @property
    def rate(self) -> float:
        return self.k / self.n if self.n else float("nan")


def year_row(label: str, b: np.ndarray, idx: list[int]) -> YearRow:
    idx = [i for i in idx if math.isfinite(b[i])]
    k = int(sum(b[i] for i in idx))
    lo, hi = wilson(k, len(idx))
    near, _ = cluster_share(b, idx)
    return YearRow(label, len(idx), k, lo, hi, near, episodes([i for i in idx if b[i] == 1.0]))


def year_index(cal: Cal, year: str) -> list[int]:
    return [i for i, d in enumerate(cal.dates) if d[:4] == year]


# ════════════════════════════════════════════════════════════════════════════
# Part 2 — predictors (close of the origin or earlier), outcomes, rows
# ════════════════════════════════════════════════════════════════════════════

def midrank_share(window: np.ndarray, x: float) -> float:
    return (float(np.sum(window < x)) + 0.5 * float(np.sum(window == x))) / len(window)


def predictors_at(cal: Cal, o: int) -> dict | None:
    """X1-X4 at the close of session `o`. Reads ONLY sessions 0..o: every array
    is sliced to `[:o + 1]` before use, so no later close can enter."""
    upto = o + 1
    vix, vix3m, adj = cal.vix[:upto], cal.vix3m[:upto], cal.adj[:upto]
    v = vix[o]
    if not (math.isfinite(v) and v > 0):
        return None
    if o < PCT_WINDOW or o < RV_WINDOW:
        return None
    win = vix[o - PCT_WINDOW:o]
    if not np.all(np.isfinite(win)):
        return None
    v3 = vix3m[o]
    if not (math.isfinite(v3) and v3 > 0):
        return None
    r = np.log(adj[o - RV_WINDOW + 1:upto] / adj[o - RV_WINDOW:o])
    if len(r) != RV_WINDOW or not np.all(np.isfinite(r)):
        return None
    rv = math.sqrt(float(np.mean(r * r))) * math.sqrt(TRADING_DAYS) * 100.0
    return {"X1": float(v), "X2": midrank_share(win, v), "X3": float(v / v3), "X4": rv / float(v)}


def outcome_any(b: np.ndarray, o: int, h: int = HORIZON) -> float | None:
    """1.0 if any of sessions o+1..o+h breached; None if one is undefined or past the data."""
    s = b[o + 1:o + 1 + h]
    if len(s) < h or not np.all(np.isfinite(s)):
        return None
    return float(np.max(s))


def outcome_next(b: np.ndarray, o: int) -> float | None:
    if o + 1 >= len(b) or not math.isfinite(b[o + 1]):
        return None
    return float(b[o + 1])


@dataclass
class Rows:
    """One outcome's forecast rows, split into training, test and forward."""
    name: str
    h: int                       # last outcome session is origin + h
    train: list[tuple[int, np.ndarray, float]] = field(default_factory=list)
    test: list[tuple[int, np.ndarray, float]] = field(default_factory=list)
    fwd: list[tuple[int, np.ndarray, float]] = field(default_factory=list)
    drops: dict = field(default_factory=lambda: {"no_predictors": 0, "no_outcome": 0,
                                                  "straddle": 0, "gap": 0})


def split_of(cal: Cal, o: int, h: int, registered: str | None) -> str:
    """train: every outcome session before TEST_START. straddle: outcome
    sessions on both sides of TEST_START. test: first outcome session on or
    after TEST_START and last on or before `registered`. fwd: origin after
    `registered`. gap: origin on or before `registered`, last outcome session
    after it. With `registered` None (a draft), every later row is test."""
    first, last = cal.dates[o + 1], cal.dates[o + h]
    if last < TEST_START:
        return "train"
    if first < TEST_START:
        return "straddle"
    if registered is None:
        return "test"
    if cal.dates[o] > registered:
        return "fwd"
    if last > registered:
        return "gap"
    return "test"


def build_rows(cal: Cal, name: str, outcome, h: int, preds: list,
               registered: str | None = None) -> Rows:
    """`outcome(o)` -> 1.0 / 0.0 / None. `preds[o]` is `predictors_at(cal, o)`."""
    rows = Rows(name, h)
    for o in range(cal.n - h):
        x = preds[o]
        if x is None:
            rows.drops["no_predictors"] += 1
            continue
        y = outcome(o)
        if y is None:
            rows.drops["no_outcome"] += 1
            continue
        part = split_of(cal, o, h, registered)
        if part in ("straddle", "gap"):
            rows.drops[part] += 1
            continue
        vec = np.array([x[p] for p in PREDICTORS], dtype=float)
        getattr(rows, part).append((o, vec, y))
    return rows


class LookaheadError(RuntimeError):
    """GX failed: a predictor changed when the series was cut at its origin."""


def gx_check(cal: Cal, preds: list, n: int = GX_SAMPLE) -> int:
    """GX: recompute the predictors at `n` evenly spaced origins on a series cut
    at the origin, and raise unless they equal the full-series values. Returns
    the number of origins checked. A raise, not an `assert`, so `-O` keeps it."""
    have = [o for o, x in enumerate(preds) if x is not None and o + 1 < cal.n]
    if not have:
        return 0
    picks = sorted({have[int(j)] for j in np.linspace(0, len(have) - 1, min(n, len(have)))})
    for o in picks:
        cut = Cal(cal.dates[:o + 1], cal.close[:o + 1], cal.adj[:o + 1],
                  cal.vix[:o + 1], cal.vix3m[:o + 1])
        if predictors_at(cut, o) != preds[o] or not cal.dates[o] < cal.dates[o + 1]:
            raise LookaheadError(f"GX: predictors at origin {cal.dates[o]} read a later close")
    return len(picks)


def as_arrays(part: list) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not part:
        return np.zeros(0, dtype=int), np.zeros((0, len(PREDICTORS))), np.zeros(0)
    return (np.array([r[0] for r in part]), np.vstack([r[1] for r in part]),
            np.array([r[2] for r in part], dtype=float))


# ════════════════════════════════════════════════════════════════════════════
# Model and metric
# ════════════════════════════════════════════════════════════════════════════

def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35.0, 35.0)))


def fit_logit(X: np.ndarray, y: np.ndarray, max_iter: int = 100,
              tol: float = 1e-10) -> tuple[np.ndarray, bool]:
    """Unpenalised logistic regression by Newton steps. Returns (beta with the
    intercept first, converged)."""
    A = np.column_stack([np.ones(len(y)), X])
    beta = np.zeros(A.shape[1])
    for _ in range(max_iter):
        p = _sigmoid(A @ beta)
        W = p * (1.0 - p)
        H = A.T @ (A * W[:, None])
        g = A.T @ (y - p)
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            return beta, False
        beta = beta + step
        if float(np.max(np.abs(step))) < tol:
            return beta, True
    return beta, False


def predict(beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    return _sigmoid(np.column_stack([np.ones(len(X)), X]) @ beta)


@dataclass
class Model:
    cols: tuple[str, ...]
    mu: np.ndarray
    sd: np.ndarray
    beta: np.ndarray
    converged: bool
    clim: float                  # training base rate

    def prob(self, X: np.ndarray) -> np.ndarray:
        idx = [PREDICTORS.index(c) for c in self.cols]
        return predict(self.beta, (X[:, idx] - self.mu) / self.sd)


def fit_model(cols: tuple[str, ...], Xtr: np.ndarray, ytr: np.ndarray) -> Model:
    idx = [PREDICTORS.index(c) for c in cols]
    Z = Xtr[:, idx]
    mu, sd = Z.mean(axis=0), Z.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    beta, ok = fit_logit((Z - mu) / sd, ytr)
    return Model(cols, mu, sd, beta, ok, float(ytr.mean()) if len(ytr) else float("nan"))


def brier_skill(p: np.ndarray, y: np.ndarray, clim: float) -> float:
    den = float(np.mean((clim - y) ** 2)) if len(y) else 0.0
    if not den > 0:
        return float("nan")
    return 1.0 - float(np.mean((p - y) ** 2)) / den


def block_indices(n: int, L: int, draws: int, seed: int) -> np.ndarray:
    """Moving-block bootstrap: ceil(n/L) overlapping blocks of L consecutive rows,
    starts uniform on 0..n-L, concatenated and cut to n. Shape (draws, n)."""
    if n == 0:
        return np.zeros((draws, 0), dtype=int)
    L = max(1, min(L, n))
    nb = -(-n // L)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n - L + 1, size=(draws, nb))
    return (starts[:, :, None] + np.arange(L)[None, None, :]).reshape(draws, -1)[:, :n]


def boot_bss(p: np.ndarray, y: np.ndarray, clim: float, idx: np.ndarray) -> np.ndarray:
    P, Y = p[idx], y[idx]
    den = np.mean((clim - Y) ** 2, axis=1)
    num = np.mean((P - Y) ** 2, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = 1.0 - num / den
    out[~(den > 0)] = np.nan
    return out


@dataclass
class Result:
    point: float
    lo: float
    hi: float
    p: float                     # two-sided, from the draws
    n: int
    events: int
    discarded: int = 0

    @property
    def half(self) -> float:
        return (self.hi - self.lo) / 2.0


def summarize(point: float, draws: np.ndarray, n: int, events: int) -> Result:
    d = draws[np.isfinite(draws)]
    if len(d) == 0 or not math.isfinite(point):
        return Result(point, float("nan"), float("nan"), 1.0, n, events, len(draws) - len(d))
    lo, hi = np.percentile(d, [2.5, 97.5])
    p = min(1.0, 2.0 * min(float(np.mean(d <= 0)), float(np.mean(d >= 0))))
    return Result(point, float(lo), float(hi), p, n, events, len(draws) - len(d))


def score(p: np.ndarray, y: np.ndarray, clim: float, idx: np.ndarray) -> Result:
    return summarize(brier_skill(p, y, clim), boot_bss(p, y, clim, idx), len(y), int(y.sum()))


def auc(p: np.ndarray, y: np.ndarray) -> float:
    """Mann-Whitney AUC; ties count half."""
    pos, neg = p[y == 1.0], p[y == 0.0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    order = allv.argsort(kind="mergesort")
    ranks = np.empty(len(allv))
    sv = allv[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    r_pos = ranks[:len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg)))


# ════════════════════════════════════════════════════════════════════════════
# Verdict words
# ════════════════════════════════════════════════════════════════════════════

def word(res: Result, powered: bool, p_adj: float | None = None) -> str:
    """PREDICTABLE when powered and the CI lower bound is above 0 (and, in a Holm
    family, the adjusted p is below 0.05); NO-FORECAST otherwise."""
    if not powered or not (math.isfinite(res.lo) and math.isfinite(res.hi)):
        return UNDERPOWERED
    if res.lo > 0 and (p_adj is None or p_adj < ALPHA):
        return PREDICTABLE
    return NO_FORECAST


def forward_word(res: Result | None, powered: bool) -> str:
    if res is None or not powered:
        return STILL_OPEN
    w = word(res, True)
    return STILL_OPEN if w == UNDERPOWERED else w


# ════════════════════════════════════════════════════════════════════════════
# Gates and inputs
# ════════════════════════════════════════════════════════════════════════════

def check_era() -> None:
    requested = era_mod.requested_era()
    if requested != era_mod.CURRENT:
        raise Refused(era_mod.EXIT_THIN_ERA,
                      f"tail_breach reads yfinance market closes, which carry no era; era "
                      f"{requested!r} does not apply — run it without --era. Exit 2.")


def ratio_problems(spy: list[tuple]) -> list[str]:
    """GB, part 1: close/adj_close may only step down (a dividend), never by
    more than RATIO_STEP_MAX. A split or a mixed feed breaks it."""
    out, prev = [], None
    for d, c, a in spy:
        if a is None:
            continue
        r = c / a
        if prev is not None:
            step = r / prev - 1.0
            if step > RATIO_UP_TOL or abs(step) > RATIO_STEP_MAX:
                out.append(f"{d} close/adj step {step:+.4%}")
        prev = r
    return out


def base_rate_problems(spy: list[tuple], vix: dict[str, float], path: Path) -> tuple[list[str], int]:
    """GB, part 2: the cached unadjusted SPY close and VIX agree with
    spy_base_rate_daily.csv within BASIS_TOL on every common date."""
    if not Path(path).exists():
        return [], 0
    close = {d: c for d, c, _ in spy}
    out, n = [], 0
    with Path(path).open(newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in ("date", "spy_close", "vix_close") if c not in (reader.fieldnames or [])]
        if missing:
            raise Refused(EXIT_INPUT, f"GB: {Path(path).name} lacks column(s) {missing}. Exit 3.")
        for r in reader:
            d = r["date"][:10]
            for key, ref in (("spy_close", close), ("vix_close", vix)):
                try:
                    want = float(r[key])
                except (TypeError, ValueError):
                    continue
                got = ref.get(d)
                if got is None:
                    continue
                n += key == "spy_close"
                if abs(got / want - 1.0) > BASIS_TOL:
                    out.append(f"{d} {key} cache {got:.4f} vs base-rate {want:.4f}")
    return out, n


def load_inputs(refresh: bool) -> tuple[list, dict, dict]:
    for name in SERIES:
        if refresh or not _cache_path(name).exists():
            try:
                fetch_series(name)
            except Refused:
                raise
            except Exception as exc:  # network, yfinance schema
                raise Refused(EXIT_INPUT,
                              f"GE: fetching {SERIES[name][0]} failed ({exc}). Exit 3.")
    spy = read_series(_cache_path("SPY"))
    vix = {d: c for d, c, _ in read_series(_cache_path("VIX"))}
    vix3m = {d: c for d, c, _ in read_series(_cache_path("VIX3M"))}
    if not spy or not vix or not vix3m:
        raise Refused(EXIT_INPUT, "GE: an input series is empty. Exit 3.")
    if spy[-1][0] < TEST_START:
        raise Refused(EXIT_INPUT,
                      f"GE: SPY ends {spy[-1][0]}, before the test window. Exit 3.")
    return spy, vix, vix3m


def _inventory(path: Path) -> str:
    with open(path, newline="") as fh:
        n = max(0, sum(1 for _ in csv.reader(fh)) - 1)
    mtime = datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"  {n:>6,} rows  {mtime}  {Path(path).resolve().relative_to(ROOT)}"


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


def pct(x: float, nd: int = 2) -> str:
    return "—" if not math.isfinite(x) else f"{100 * x:.{nd}f}%"


def bss_txt(res: Result) -> str:
    if not math.isfinite(res.point):
        return "BSS —"
    if not math.isfinite(res.lo):
        return f"BSS {res.point:+.4f} [—]"
    return f"BSS {res.point:+.4f} [{res.lo:+.4f}, {res.hi:+.4f}] ±{res.half:.4f}"


def episodes_in(cal: Cal, b: np.ndarray, part: list, h: int) -> int:
    """Independent breach episodes among the outcome sessions of `part`'s rows."""
    sessions = sorted({o + j for o, _, _ in part for j in range(1, h + 1)})
    return episodes([i for i in sessions if b[i] == 1.0])


# ════════════════════════════════════════════════════════════════════════════
# The run
# ════════════════════════════════════════════════════════════════════════════

def report_part1(cal: Cal, defs: dict) -> None:
    section("PART 1 — breaches per calendar year (descriptive, no verdict)")
    print("  Wilson 95% CI treats sessions as independent. 'near' = breaches with another")
    print(f"  breach in the {CLUSTER} sessions before; 'indep' = 1-(1-rate)^{CLUSTER}, the share "
          "independence implies.")
    for label, (b, implied) in defs.items():
        print(f"\n  {label}")
        print("    year       sessions  breaches  rate     [Wilson 95%]        normal   "
              "near/breaches  indep   episodes")
        groups = [(y, year_index(cal, y)) for y in YEARS]
        groups.append(("2024-26", [i for y in YEARS for i in year_index(cal, y)]))
        groups.append(("train*", [i for i, d in enumerate(cal.dates) if "2006-07-18" <= d < TEST_START]))
        for y, idx in groups:
            r = year_row(y, b, idx)
            nr = implied(idx) if callable(implied) else implied
            share = r.near / r.k if r.k else float("nan")
            print(f"    {y:<9} {r.n:>9} {r.k:>9}  {pct(r.rate):>7}  [{pct(r.lo)}, {pct(r.hi)}]"
                  f"  {pct(nr):>7}   {r.near:>3}/{r.k:<3} {pct(share, 0):>5}  "
                  f"{pct(independent_share(r.rate), 0):>5}  {r.episodes:>6}")
    print("\n  * train = 2006-07-18 to 2023-12-29, context only. 2026 is year to date.")


def run(refresh: bool = False) -> int:
    check_era()
    spy, vix, vix3m = load_inputs(refresh)
    cal = build_cal(spy, vix, vix3m)

    print("tail_breach — how often does SPY fall more than twice its VIX-implied move, "
          "and can it be forecast?")
    print(f"registration: {REGISTRATION} "
          f"({'registered ' + REGISTERED if REGISTERED else 'DRAFT, not registered'})")
    print("era: current (inputs are unversioned market closes)")
    print(f"population: SPY sessions {cal.dates[0]} -> {cal.dates[-1]} ({cal.n}); "
          f"test window from {TEST_START}")
    dirty = "dirty" if _git("status", "--porcelain") else "clean"
    print(f"git: {_git('rev-parse', '--short', 'HEAD')} "
          f"({_git('rev-parse', '--abbrev-ref', 'HEAD')}, working tree {dirty})")
    print("inputs read:")
    for name in SERIES:
        print(_inventory(_cache_path(name)))
    if BASE_RATE_CSV.exists():
        print(_inventory(BASE_RATE_CSV))
    print("SEAL: not applied — no flow signal, play or backtest row is read")
    print(f"breach k={K} (printed {K_PARAMS}); returns on adj_close; blocks {BLOCK} sessions, "
          f"{BOOT_N} draws, seed {SEED}")

    # GB — basis
    probs = ratio_problems(spy)
    bprobs, n_common = base_rate_problems(spy, vix, BASE_RATE_CSV)
    section("GATES — inputs and basis")
    print(f"  GE: SPY {len(spy)} rows, VIX {len(vix)}, VIX3M {len(vix3m)} — pass")
    print(f"  GB ratio: {len(probs)} close/adj steps outside the dividend pattern")
    print(f"  GB base-rate: {n_common} common SPY dates, {len(bprobs)} disagreements over "
          f"{BASIS_TOL:.1%}" + ("" if BASE_RATE_CSV.exists() else " (file missing: skipped)"))
    if probs or bprobs:
        for line in (probs + bprobs)[:10]:
            print(f"    {line}")
        raise Refused(EXIT_INPUT, "GB: the price basis check failed. Exit 3.")
    miss_v = sum(1 for i in range(cal.n) if not math.isfinite(cal.vix[i]))
    miss_v3 = sum(1 for i, d in enumerate(cal.dates) if d >= "2006-07-17" and not math.isfinite(cal.vix3m[i]))
    print(f"  coverage: SPY sessions with no VIX close {miss_v}; since 2006-07-17 with no VIX3M "
          f"{miss_v3}")

    bd = breach_down(cal, K)
    defs = {
        f"DOWN k={K} (primary)": (bd, normal_rate(K)),
        **{f"DOWN k={k} (parameter)": (breach_down(cal, k), normal_rate(k)) for k in K_PARAMS},
        "FIXED -2% day (secondary)": (breach_fixed(cal), lambda idx: fixed_implied_rate(cal, idx)),
        f"WINDOW {WINDOW}-session, k={K} (secondary; overlapping windows, by first session)":
            (breach_window(cal, K), normal_rate(K)),
        f"UP k={K} (secondary, mirror)": (breach_up(cal, K), normal_rate(K)),
        f"BASIS twin: DOWN k={K} on the unadjusted close (printed only)":
            (breach_down(cal, K, basis="close"), normal_rate(K)),
    }
    report_part1(cal, defs)

    # ── Part 2 ──────────────────────────────────────────────────────────────
    preds = [predictors_at(cal, o) for o in range(cal.n)]
    y5 = build_rows(cal, "Y5", lambda o: outcome_any(bd, o), HORIZON, preds, REGISTERED)
    y1 = build_rows(cal, "Y1", lambda o: outcome_next(bd, o), 1, preds, REGISTERED)

    section("PART 2 — rows")
    for rows in (y5, y1):
        tr, te = rows.train, rows.test
        print(f"  {rows.name}: train {len(tr)} ({cal.dates[tr[0][0]] if tr else '—'} -> "
              f"{cal.dates[tr[-1][0]] if tr else '—'}), test {len(te)} "
              f"({cal.dates[te[0][0]] if te else '—'} -> {cal.dates[te[-1][0]] if te else '—'}), "
              f"forward {len(rows.fwd)}; dropped {rows.drops}")
    _, Xtr, ytr = as_arrays(y5.train)
    _, Xte, yte = as_arrays(y5.test)
    tr_ep = episodes_in(cal, bd, y5.train, HORIZON)
    te_ep = episodes_in(cal, bd, y5.test, HORIZON)
    gt = len(ytr) >= MIN_TRAIN_ROWS and tr_ep >= MIN_TRAIN_EPISODES
    gn = te_ep >= MIN_TEST_EPISODES
    print(f"  GT: {len(ytr)} training rows (floor {MIN_TRAIN_ROWS}), {tr_ep} training episodes "
          f"(floor {MIN_TRAIN_EPISODES}) — {'pass' if gt else 'FAIL'}")
    print(f"  GN: {te_ep} independent down-breach episodes in the test window "
          f"(floor {MIN_TEST_EPISODES}) — {'pass' if gn else 'FAIL'}")
    n_gx = gx_check(cal, preds)
    print(f"  GX: predictors equal on a series cut at the origin, {n_gx} origins checked — pass")
    powered = gt and gn

    # primary and singles on Y5, shared draws
    idx = block_indices(len(yte), BLOCK, BOOT_N, SEED)
    P = fit_model(PREDICTORS, Xtr, ytr)
    singles = {s: fit_model(c, Xtr, ytr) for s, c in SINGLES.items()}
    _, X1tr, y1tr = as_arrays(y1.train)
    _, X1te, y1te = as_arrays(y1.test)
    N1 = fit_model(PREDICTORS, X1tr, y1tr)
    section("PART 2 — fitted on training rows (standardised; intercept first)")
    for lab, m in (("P", P), *singles.items(), ("N1", N1)):
        coefs = "  ".join(f"{c} {b:+.3f}" for c, b in zip(("b0", *m.cols), m.beta))
        print(f"  {lab:<2} {coefs}   converged {m.converged}")
    print(f"  training base rate (climatology) Y5 {pct(P.clim)}, Y1 {pct(N1.clim)}")
    all_conv = P.converged and all(m.converged for m in singles.values())

    pte = P.prob(Xte) if len(yte) else np.zeros(0)
    resP = score(pte, yte, P.clim, idx)
    resS = {s: score(m.prob(Xte), yte, m.clim, idx) for s, m in singles.items()}
    adj = holm({s: r.p for s, r in resS.items()}) if resS else {}
    wP = word(resP, powered and P.converged)
    wS = {s: word(r, powered and singles[s].converged, adj[s][0]) for s, r in resS.items()}

    p1te = N1.prob(X1te) if len(y1te) else np.zeros(0)
    res1 = score(N1.prob(X1te), y1te, N1.clim,
                 block_indices(len(y1te), BLOCK, BOOT_N, SEED)) if len(y1te) else \
        Result(float("nan"), float("nan"), float("nan"), 1.0, 0, 0)
    w1 = word(res1, gt and gn and N1.converged)

    section("PART 2 — graded (test window, coefficients frozen)")
    print(f"  P   four predictors, Y5   {bss_txt(resP)}  n {resP.n}, events {resP.events}, "
          f"AUC {auc(pte, yte):.3f}  -> {wP}")
    for s, r in resS.items():
        print(f"  {s}  {PRED_NAME[SINGLES[s][0]]:<30} {bss_txt(r)}  p {r.p:.4f}, Holm {adj[s][0]:.4f}, "
              f"AUC {auc(singles[s].prob(Xte), yte):.3f}  -> {wS[s]}")
    print(f"  N1  four predictors, Y1   {bss_txt(res1)}  n {res1.n}, events {res1.events}, "
          f"AUC {auc(p1te, y1te):.3f}  -> {w1}")
    if not all_conv or not N1.converged:
        print("  a model did not converge: its word is UNDERPOWERED")

    section("PRINTED ONLY — base rate, years, block length")
    te_rate = float(yte.mean()) if len(yte) else float("nan")
    rate_draws = yte[idx].mean(axis=1) if len(yte) else np.zeros(0)
    lo, hi = (np.percentile(rate_draws, [2.5, 97.5]) if len(rate_draws) else (np.nan, np.nan))
    print(f"  Y5 base rate: train {pct(P.clim)}, test {pct(te_rate)} [{pct(lo)}, {pct(hi)}] "
          f"(block CI on the test rate)")
    print(f"  a constant forecast at the test window's own rate scores "
          f"BSS {brier_skill(np.full(len(yte), te_rate), yte, P.clim):+.4f} (oracle, not a model)")
    for y in YEARS:
        sel = np.array([cal.dates[o + 1][:4] == y for o, _, _ in y5.test], dtype=bool)
        if sel.sum() == 0:
            continue
        r = score(pte[sel], yte[sel], P.clim, block_indices(int(sel.sum()), BLOCK, BOOT_N, SEED))
        print(f"  P in {y}: {bss_txt(r)}  n {r.n}, events {r.events}")
    for L in BLOCK_SENS:
        r = score(pte, yte, P.clim, block_indices(len(yte), L, BOOT_N, SEED))
        print(f"  P with {L}-session blocks: {bss_txt(r)}")

    section("PRINTED ONLY — parameters and secondary breach definitions (P refitted per outcome)")
    alt = {f"DOWN k={k}, Y5": (lambda o, b=breach_down(cal, k): outcome_any(b, o), HORIZON)
           for k in K_PARAMS}
    bw, bf, bu = breach_window(cal, K), breach_fixed(cal), breach_up(cal, K)
    alt["FIXED -2%, Y5"] = (lambda o: outcome_any(bf, o), HORIZON)
    alt[f"WINDOW {WINDOW}-session t..t+4"] = (lambda o: outcome_next(bw, o), HORIZON)
    alt[f"UP k={K}, Y5"] = (lambda o: outcome_any(bu, o), HORIZON)
    for lab, (fn, h) in alt.items():
        rows = build_rows(cal, lab, fn, h, preds, REGISTERED)
        _, Xa, ya = as_arrays(rows.train)
        _, Xb, yb = as_arrays(rows.test)
        if len(ya) == 0 or len(yb) == 0:
            print(f"  {lab}: no rows")
            continue
        m = fit_model(PREDICTORS, Xa, ya)
        r = score(m.prob(Xb), yb, m.clim, block_indices(len(yb), BLOCK, BOOT_N, SEED))
        print(f"  {lab:<28} {bss_txt(r)}  train rate {pct(m.clim)}, test rate {pct(float(yb.mean()))}")

    section("FORWARD — forecast origins after the registration date")
    fwd_word = STILL_OPEN
    if REGISTERED is None:
        print("  registration not accepted: no forward window. forward: STILL-OPEN")
    else:
        _, Xf, yf = as_arrays(y5.fwd)
        f_ep = episodes_in(cal, bd, y5.fwd, HORIZON)
        f_pow = len(yf) >= FWD_MIN_ROWS and f_ep >= FWD_MIN_EPISODES
        print(f"  forward rows {len(yf)} (floor {FWD_MIN_ROWS}), episodes {f_ep} "
              f"(floor {FWD_MIN_EPISODES})")
        res_f = score(P.prob(Xf), yf, P.clim, block_indices(len(yf), BLOCK, BOOT_N, SEED)) \
            if f_pow else None
        fwd_word = forward_word(res_f, f_pow and P.converged)
        if res_f is not None:
            print(f"  forward P {bss_txt(res_f)}")
        print(f"  forward: {fwd_word}")

    section("VERDICT")
    print(f"  test window {TEST_START} -> {cal.dates[y5.test[-1][0]] if y5.test else '—'} "
          f"(origins); {len(yte)} rows, {te_ep} episodes; {BOOT_N} moving-block draws "
          f"(block {BLOCK}), seed {SEED}")
    print()
    print(f"  >>> tail_breach P (four-predictor logistic, any 2x-VIX down breach in the next 5 "
          f"sessions, test from {TEST_START}): {wP} <<<")
    print(f"  >>> tail_breach SECONDARY (each predictor alone, Holm m=4): "
          f"S1 {wS['S1']} S2 {wS['S2']} S3 {wS['S3']} S4 {wS['S4']} <<<")
    print(f"  >>> tail_breach N1 (four-predictor logistic, next-session breach): {w1} <<<")
    print(f"  >>> tail_breach FORWARD (forecast origins after the registration date): "
          f"{fwd_word} <<<")
    print()
    print("  PREDICTABLE needs the 95% CI on the Brier skill score wholly above 0; S1-S4 also")
    print("  need a Holm-adjusted p below 0.05. AUC is context only.")
    print("  Nothing ships from this study (tail_breach.md).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="refetch SPY, ^VIX and ^VIX3M from yfinance before the run")
    args = ap.parse_args(argv)
    try:
        return run(refresh=args.refresh)
    except Refused as exc:
        print(f"REFUSED — {exc.message}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
