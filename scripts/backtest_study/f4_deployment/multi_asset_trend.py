"""multi_asset_trend — does monthly trend across nine ETFs beat holding all nine?

REGISTRATION: research/pre-registrations/f4_deployment/multi_asset_trend.md (registered
2026-11-27, second read passed, committed 23336bb). Every constant, floor, seed, window
and verdict word below is that file's. Read it before changing anything here.

WHAT IT ASKS
------------
Nine sleeves (SPY QQQ IWM EFA EEM TLT IEF GLD DBC), each IN (holds its ETF) or OUT
(holds T-bills) after each month-end decision close, traded at the next session's close
with 5 bp per side on every sleeve, the T-bill sleeve included. Headline cell TB-12-EW
(12-month return above T-bills, equal weight) against EW-9 (all nine, equal weight,
rebalanced at every execution close). Graded on the holdout 2017-01..2026-08 on the
Sharpe ratio and the maximum drawdown of monthly equity, with a discovery sign check.
Eleven more cells exist only for PBO. A descriptive options arm prices the SPY sleeve as
a call vertical from the cached quotes and grades nothing.

DATA
----
yfinance, auto_adjust=False, cached in backtests/multi_asset_trend/<TICKER>.csv (date,
close, adj_close). Fetched only with `--refresh`; without it a missing file refuses
(exit 3). `^IRX` is read from backtests/multi_asset_trend/IRX.csv when it exists, else
from backtests/trend_overlay/IRX.csv, which this module never writes. No close after
2026-09-22 enters the in-sample run; the forward read opens with 2026-12.

Nothing ships from this study. Run:

    python -m scripts.backtest_study.f4_deployment.multi_asset_trend --refresh
    python -m scripts.backtest_study run multi_asset_trend
"""
from __future__ import annotations

import argparse
import bisect
import csv
import math
import random
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib.path_bootstrap import _resample_indices  # noqa: E402

REGISTRATION = "research/pre-registrations/f4_deployment/multi_asset_trend.md"
NAME = "multi_asset_trend"
CACHE_DIR = ROOT / "backtests" / "multi_asset_trend"
IRX_TREND_OVERLAY = ROOT / "backtests" / "trend_overlay" / "IRX.csv"
OPTION_CACHE = ROOT / "backtests" / "option_history_cache"
BACKTEST_YML = ROOT / "config" / "backtest.yml"

TICKERS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC")
FETCH_START = "1993-01-01"
IRX_SYMBOL, IRX_START = "^IRX", "1960-01-01"

IN_SAMPLE_END = "2026-09-22"
DISCOVERY_END = "2016-12"
HOLDOUT = ("2017-01", "2026-08")
FORWARD_START = "2026-12"
FORWARD_MIN_MONTHS = 36
FORWARD_READ_AFTER = "2029-11"

LOOKBACKS = (6, 10, 12)
RULES = ("TB", "SMA")
WEIGHTS = ("EW", "IV")
CELLS = tuple(f"{r}-{L}-{w}" for r in RULES for L in LOOKBACKS for w in WEIGHTS)
HEADLINE = "TB-12-EW"
IV_DAYS = 60
MAX_LOOKBACK = max(LOOKBACKS)

COST_BP = 5.0
COST_SENS = (0.0, 15.0)
BLOCK = 12
BLOCK_SENS = (6, 24)
BOOT_N = 5_000
SEED = 20261127
PBO_S = 16
PBO_VETO = 0.50
PBO_FRAGILE = 0.25
EPISODE_DD = 0.10
MIN_MONTHS = 96
MIN_EPISODES = 2
NW_LAGS = 12
TRADING_DAYS = 252

GI_IRX_CARRY = 5
GI_IRX_AGREE = 0.01          # points
GB_RATIO_FALL = 1e-4         # adj/close may fall at most 0.01% between sessions
GB_RATIO_STEP = 0.05         # and never jump by more than 5%
GB_RET = 0.25                # no daily adjusted return beyond +-25%
GB_ADJ_RET = 0.03            # and the adjusted close's ex-date return must be within 3 points of zero
GB_DIV_MATCH = 0.001         # a >5% jump passes only if a feed distribution implies it (build ruling)
GX_SAMPLES = 24
GR_TOL = 1e-12

OPT_DTE = 65
OPT_OTM = 1.05
OPT_LEGS = 2

EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH        # 3
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

SQRT12 = math.sqrt(12.0)


class Refused(Exception):
    def __init__(self, code: int, message: str, reason: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.reason = reason or message.split(":")[0]


# ════════════════════════════════════════════════════════════════════════════
# Data
# ════════════════════════════════════════════════════════════════════════════

def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.csv"


def fetch_series(name: str, end: str | None = None) -> Path:
    """yfinance -> `backtests/multi_asset_trend/<name>.csv`. `end` is exclusive, so
    today's bar is never fetched."""
    import pandas as pd
    import yfinance as yf
    sym, start = (IRX_SYMBOL, IRX_START) if name == "IRX" else (name, FETCH_START)
    end = end or date.today().isoformat()
    df = yf.download(sym, start=start, end=end, auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise Refused(EXIT_INPUT, f"GI: yfinance returned no rows for {sym}. Exit 3.")

    def col(c):
        x = df[c]
        return x.iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else x

    close, adj = col("Close"), col("Adj Close")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(name)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "close", "adj_close"])
        for d, c, a in zip(close.index, close.values, adj.values):
            if c == c:
                w.writerow([pd.Timestamp(d).strftime("%Y-%m-%d"), repr(float(c)),
                            repr(float(a)) if a == a else ""])
    tmp.replace(path)
    print(f"fetched {sym} -> {path.relative_to(ROOT)} ({len(close)} rows)")
    if name != "IRX":
        fetch_dividends(name)
    return path


def _div_path(name: str) -> Path:
    return CACHE_DIR / f"{name}_dividends.csv"


def fetch_dividends(name: str) -> Path:
    """yfinance's cash-distribution feed -> `backtests/multi_asset_trend/<name>_dividends.csv`
    (date, dividend). Read only by gate GB's distribution check (Resolved at build
    2026-11-27)."""
    import pandas as pd
    import yfinance as yf
    d = yf.Ticker(name).dividends
    path = _div_path(name)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "dividend"])
        for ts, v in zip(d.index, d.values):
            w.writerow([pd.Timestamp(ts).strftime("%Y-%m-%d"), repr(float(v))])
    tmp.replace(path)
    return path


def read_dividends(name: str) -> dict[str, float] | None:
    p = _div_path(name)
    if not p.exists():
        return None
    with p.open(newline="") as fh:
        return {r["date"][:10]: float(r["dividend"]) for r in csv.DictReader(fh)}


def read_series(path: Path, yield_series: bool = False) -> list[tuple[str, float, float | None]]:
    """(date, close, adj_close) rows, ascending, finite positive closes only. A yield
    series (`^IRX`) keeps zero and negative quotes: the 13-week bill quoted below zero
    in March 2020, and dropping those rows would invent a carry."""
    out = []
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                c = float(r["close"])
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(c) and (c > 0 or yield_series)):
                continue
            try:
                a = float(r.get("adj_close") or "nan")
            except ValueError:
                a = float("nan")
            out.append((r["date"][:10], c, a if math.isfinite(a) and a > 0 else None))
    return sorted(out)


@dataclass
class Series:
    dates: list[str]
    close: np.ndarray
    adj: np.ndarray            # NaN where absent

    def cut(self, end: str) -> "Series":
        k = bisect.bisect_right(self.dates, end)
        return Series(self.dates[:k], self.close[:k].copy(), self.adj[:k].copy())


def to_series(rows) -> Series:
    return Series([r[0] for r in rows], np.array([r[1] for r in rows], dtype=float),
                  np.array([r[2] if r[2] is not None else np.nan for r in rows], dtype=float))


@dataclass
class Inputs:
    etf: dict                  # ticker -> Series
    irx: Series                # the copy the module reads
    irx_alt: Series | None     # trend_overlay's copy when both exist (GI agreement)
    irx_source: str = ""

    def cut(self, end: str) -> "Inputs":
        return Inputs({t: s.cut(end) for t, s in self.etf.items()}, self.irx.cut(end),
                      self.irx_alt.cut(end) if self.irx_alt is not None else None,
                      self.irx_source)


def load_inputs(refresh: bool = False) -> Inputs:
    etf = {}
    for t in TICKERS:
        p = _cache_path(t)
        if refresh:
            fetch_series(t)
        if not p.exists():
            raise Refused(EXIT_INPUT, f"GI: {p.relative_to(ROOT)} is missing; fetch it with "
                                      f"--refresh. Exit 3.")
        rows = read_series(p)
        if not rows:
            raise Refused(EXIT_INPUT, f"GI: {p.relative_to(ROOT)} is empty. Exit 3.")
        etf[t] = to_series(rows)
    own = _cache_path("IRX")
    if refresh:
        fetch_series("IRX")
    alt = None
    if own.exists():
        irx, src = to_series(read_series(own, True)), own
        if IRX_TREND_OVERLAY.exists():
            alt = to_series(read_series(IRX_TREND_OVERLAY, True))
    elif IRX_TREND_OVERLAY.exists():
        irx, src = to_series(read_series(IRX_TREND_OVERLAY, True)), IRX_TREND_OVERLAY
    else:
        raise Refused(EXIT_INPUT, "GI: no ^IRX file (neither copy exists). Exit 3.")
    return Inputs(etf, irx, alt, str(src.relative_to(ROOT)))


# ════════════════════════════════════════════════════════════════════════════
# The panel: one row per SPY session
# ════════════════════════════════════════════════════════════════════════════

def month_end_idx(dates: list[str]) -> list[int]:
    """Indices of the last session of each calendar month. The last row is never one:
    whether it ends its month is known only from the next session, so a cut series
    never invents a decision."""
    return [i for i in range(len(dates) - 1) if dates[i][:7] != dates[i + 1][:7]]


@dataclass
class Panel:
    dates: list[str]           # SPY sessions
    adj: np.ndarray            # sessions x 9, NaN where an ETF has no close
    spy_close: np.ndarray      # unadjusted SPY close (option strikes only)
    irx_c: np.ndarray          # ^IRX close, last close carried forward
    irx_carry: np.ndarray      # sessions since the last real ^IRX close
    tb: np.ndarray             # daily T-bill return on session k (from close k-1)


def build_panel(inp: Inputs, end: str) -> Panel:
    spy = inp.etf["SPY"].cut(end)
    dates = list(spy.dates)
    n = len(dates)
    adj = np.full((n, len(TICKERS)), np.nan)
    for i, t in enumerate(TICKERS):
        s = inp.etf[t]
        m = dict(zip(s.dates, s.adj))
        adj[:, i] = [m.get(d, np.nan) for d in dates]
    irx = inp.irx
    irx_c = np.full(n, np.nan)
    carry = np.zeros(n, dtype=int)
    j = 0
    last, run = np.nan, 0
    for k, d in enumerate(dates):
        hit = False
        while j < len(irx.dates) and irx.dates[j] <= d:
            if irx.dates[j] == d:
                hit = True
            last = irx.close[j]
            j += 1
        run = 0 if hit else run + 1
        irx_c[k] = last
        carry[k] = run if last == last else 10 ** 6
    tb = np.full(n, np.nan)
    tb[1:] = irx_c[:-1] / 100.0 / TRADING_DAYS
    return Panel(dates, adj, spy.close.copy(), irx_c, carry, tb)


def first_common_decision(P: Panel, me: list[int]) -> int | None:
    """Index into `me` of the first month-end at which all 12 cells are defined for all
    nine ETFs, from the data."""
    for j in range(MAX_LOOKBACK, len(me)):
        t = me[j]
        if t < IV_DAYS:
            continue
        pts = [me[j - MAX_LOOKBACK]] + me[j - MAX_LOOKBACK + 1:j + 1]
        if (np.isfinite(P.adj[pts]).all() and np.isfinite(P.adj[t - IV_DAYS:t + 1]).all()
                and np.isfinite(P.tb[me[j - MAX_LOOKBACK] + 1:t + 1]).all()):
            return j
    return None


# ════════════════════════════════════════════════════════════════════════════
# The rule — one decision reads only the arrays it is handed, which end at t
# ════════════════════════════════════════════════════════════════════════════

def parse_cell(cell: str) -> tuple[str, int, str]:
    r, L, w = cell.split("-")
    return r, int(L), w


def targets(adj_h: np.ndarray, tb_h: np.ndarray, me_h: list[int], cell: str
            ) -> tuple[np.ndarray, np.ndarray]:
    """(IN states, ETF weights) at the decision close t = me_h[-1] = len(adj_h) - 1.

    `adj_h` and `tb_h` are the panel cut at t, so no later close can be read. An OUT
    sleeve's weight goes to T-bills (the weights returned are ETF weights only). Ties
    are OUT."""
    rule, L, wt = parse_cell(cell)
    t = me_h[-1]
    assert t == len(adj_h) - 1, "a decision must be handed arrays that end at its close"
    if rule == "TB":
        t0 = me_h[-1 - L]
        r_etf = adj_h[t] / adj_h[t0] - 1.0
        r_tb = float(np.prod(1.0 + tb_h[t0 + 1:t + 1]) - 1.0)
        states = r_etf > r_tb
    elif rule == "SMA":
        mc = adj_h[me_h[-L:]]
        states = adj_h[t] > mc.mean(axis=0)
    else:
        raise ValueError(f"unknown rule {rule!r}")
    if wt == "EW":
        base = np.full(len(TICKERS), 1.0 / len(TICKERS))
    elif wt == "IV":
        lr = np.diff(np.log(adj_h[t - IV_DAYS:t + 1]), axis=0)
        inv = 1.0 / lr.std(axis=0, ddof=1)
        base = inv / inv.sum()
    else:
        raise ValueError(f"unknown weights {wt!r}")
    states = np.asarray(states, dtype=bool)
    return states, np.where(states, base, 0.0)


def decision_table(P: Panel, me: list[int], j0: int, cell: str | None) -> dict:
    """{execution session k: (states, ETF weights)} for every decision j >= j0 whose
    execution session exists. `cell=None` forces every sleeve IN at EW weights."""
    out = {}
    n = len(P.dates)
    for j in range(j0, len(me)):
        t = me[j]
        if t + 1 >= n:
            break
        if cell is None:
            st = np.ones(len(TICKERS), dtype=bool)
            w = np.full(len(TICKERS), 1.0 / len(TICKERS))
        else:
            st, w = targets(P.adj[:t + 1], P.tb[:t + 1], me[:j + 1], cell)
        out[t + 1] = (st, w)
    return out


# ════════════════════════════════════════════════════════════════════════════
# Simulation
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Exec:
    k: int
    date: str
    states: np.ndarray | None
    w: np.ndarray              # ETF target weights
    turnover: float            # traded notional / equity (0 at the start)
    initial: bool


@dataclass
class Curve:
    label: str
    g: np.ndarray              # growth factor of session k over k-1; NaN at or before start
    start: int
    execs: list = field(default_factory=list)


def simulate(P: Panel, table: dict, label: str, cost_bp: float = COST_BP) -> Curve:
    """Nine ETF sleeves plus a T-bill sleeve. Starts at 1.0 at the first execution close
    at its target weights, no entry cost. Weights drift between executions. At an
    execution close the traded notional is sum |target - drifted| x equity over all ten
    sleeves, charged `cost_bp` per side."""
    n = len(P.dates)
    ks = sorted(table)
    e0 = ks[0]
    g = np.full(n, np.nan)
    st, w = table[e0]
    h = np.append(w, 1.0 - w.sum())
    execs = [Exec(e0, P.dates[e0], st, w.copy(), 0.0, True)]
    E = 1.0
    c = cost_bp / 1e4
    for k in range(e0 + 1, n):
        f = np.append(P.adj[k] / P.adj[k - 1], 1.0 + P.tb[k])
        h = h * f
        E_new = float(h.sum())
        if k in table:
            st, w = table[k]
            tgt = np.append(w, 1.0 - w.sum())
            traded = float(np.abs(tgt - h / E_new).sum()) * E_new
            execs.append(Exec(k, P.dates[k], st, w.copy(), traded / E_new, False))
            E_new -= c * traded
            h = tgt * E_new
        g[k] = E_new / E
        E = E_new
    return Curve(label, g, e0, execs)


def benchmark_rebalanced(P: Panel, weights: dict, exec_ks: list[int], label: str,
                         cost_bp: float = COST_BP) -> Curve:
    """Fixed weights in named ETFs, rebalanced at every execution close, the same per-side
    cost. Written apart from `simulate` (no states, no cash sleeve) so that gate GR is a
    real replay check."""
    cols = [TICKERS.index(t) for t in weights]
    wv = np.array([weights[t] for t in weights], dtype=float)
    n = len(P.dates)
    e0 = exec_ks[0]
    rebal = set(exec_ks[1:])
    g = np.full(n, np.nan)
    val = wv.copy()
    full_w = np.zeros(len(TICKERS))
    full_w[cols] = wv
    execs = [Exec(e0, P.dates[e0], None, full_w.copy(), 0.0, True)]
    prev = 1.0
    for k in range(e0 + 1, n):
        val = val * (P.adj[k, cols] / P.adj[k - 1, cols])
        eq = float(val.sum())
        if k in rebal:
            drift = val / eq
            traded = float(np.abs(wv - drift).sum()) * eq
            execs.append(Exec(k, P.dates[k], None, full_w.copy(), traded / eq, False))
            eq = eq - traded * cost_bp / 1e4
            val = wv * eq
        g[k] = eq / prev
        prev = eq
    return Curve(label, g, e0, execs)


def benchmark_hold(P: Panel, ticker: str, e0: int, label: str) -> Curve:
    """One ETF bought once at the first execution close and held."""
    i = TICKERS.index(ticker)
    g = np.full(len(P.dates), np.nan)
    g[e0 + 1:] = P.adj[e0 + 1:, i] / P.adj[e0:-1, i]
    w = np.zeros(len(TICKERS))
    w[i] = 1.0
    return Curve(label, g, e0, [Exec(e0, P.dates[e0], None, w, 0.0, True)])


# ════════════════════════════════════════════════════════════════════════════
# Months and windows
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class MonthGrid:
    months: list[str]          # complete calendar months after the start close
    spans: list[tuple[int, int]]   # (first session k, last session k) per month


def month_grid(P: Panel, e0: int) -> MonthGrid:
    """Complete months only: a month is complete when its last session is a month-end
    (the next session falls in a later month)."""
    me = set(month_end_idx(P.dates))
    months, spans = [], []
    k = e0 + 1
    n = len(P.dates)
    while k < n:
        m = P.dates[k][:7]
        k1 = k
        while k1 + 1 < n and P.dates[k1 + 1][:7] == m:
            k1 += 1
        if k1 in me:
            months.append(m)
            spans.append((k, k1))
        k = k1 + 1
    return MonthGrid(months, spans)


def monthly(g: np.ndarray, grid: MonthGrid) -> np.ndarray:
    return np.array([float(np.prod(g[a:b + 1])) - 1.0 for a, b in grid.spans])


def monthly_tbill(P: Panel, grid: MonthGrid) -> np.ndarray:
    return np.array([float(np.prod(1.0 + P.tb[a:b + 1])) - 1.0 for a, b in grid.spans])


@dataclass
class Window:
    name: str
    months: list[str]
    lo: int                    # slice into the grid's months
    hi: int

    @property
    def n(self) -> int:
        return self.hi - self.lo

    def sl(self, x: np.ndarray) -> np.ndarray:
        return x[self.lo:self.hi]


def make_window(grid: MonthGrid, name: str, first: str | None, last: str) -> Window:
    idx = [i for i, m in enumerate(grid.months)
           if (first is None or m >= first) and m <= last]
    if not idx:
        return Window(name, [], 0, 0)
    return Window(name, grid.months[idx[0]:idx[-1] + 1], idx[0], idx[-1] + 1)


# ════════════════════════════════════════════════════════════════════════════
# Metrics
# ════════════════════════════════════════════════════════════════════════════

def sharpe(ex: np.ndarray) -> float:
    if len(ex) < 2:
        return float("nan")
    s = float(np.std(ex, ddof=1))
    return SQRT12 * float(np.mean(ex)) / s if s > 0 else float("nan")


def mdd(r: np.ndarray) -> float:
    """Largest fall of compounded equity from its running peak, the peak starting at the
    rebased 1.0."""
    if not len(r):
        return 0.0
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return float((1.0 - eq / peak).max())


def cagr(r: np.ndarray) -> float:
    if not len(r):
        return float("nan")
    return float(np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0)


def nw_ols(y: np.ndarray, x: np.ndarray, lags: int = NW_LAGS) -> tuple[float, float, float, float]:
    """OLS y = a + b x with Newey-West (Bartlett) errors. (a, se_a, b, se_b)."""
    X = np.column_stack([np.ones(len(x)), x])
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    u = y - X @ beta
    Xu = X * u[:, None]
    S = Xu.T @ Xu
    for lag in range(1, min(lags, len(y) - 1) + 1):
        wl = 1.0 - lag / (lags + 1.0)
        G = Xu[lag:].T @ Xu[:-lag]
        S += wl * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    return float(beta[0]), float(se[0]), float(beta[1]), float(se[1])


@dataclass
class Stats:
    sharpe: float
    mdd: float
    mdd_daily: float
    cagr: float
    turnover: float
    tim: float
    worst_year: str
    alpha: float
    alpha_se: float
    beta: float
    beta_se: float
    sleeve_in: np.ndarray | None


def window_stats(curve: Curve, r: np.ndarray, tbm: np.ndarray, ew: np.ndarray,
                 grid: MonthGrid, w: Window) -> Stats:
    rw, tw, ewm = w.sl(r), w.sl(tbm), w.sl(ew)
    a, b = grid.spans[w.lo][0], grid.spans[w.hi - 1][1]
    gd = curve.g[a:b + 1]
    eq = np.cumprod(gd)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    mdd_d = float((1.0 - eq / peak).max())
    months = set(w.months)
    ex = [e for e in curve.execs if e.date[:7] in months]
    turn = sum(e.turnover for e in ex if not e.initial) * 12.0 / w.n
    held = ex or [e for e in curve.execs if e.date[:7] < w.months[0]][-1:]
    tim = float(np.mean([e.w.sum() for e in held])) if held else float("nan")
    sl = None
    st = [e.states for e in ex if e.states is not None]
    if st:
        sl = np.mean(np.vstack(st), axis=0)
    years: dict[str, list[float]] = {}
    for m, x in zip(w.months, rw):
        years.setdefault(m[:4], []).append(x)
    yr = {y: float(np.prod(1.0 + np.array(v)) - 1.0) for y, v in years.items()}
    wy = min(yr, key=yr.get)
    wlab = f"{wy} {yr[wy]:+.1%}" + (" (partial)" if len(years[wy]) < 12 else "")
    al, al_se, be, be_se = nw_ols(rw - tw, ewm - tw)
    return Stats(sharpe(rw - tw), mdd(rw), mdd_d, cagr(rw), turn, tim, wlab,
                 al * 12.0, al_se * 12.0, be, be_se, sl)


# ── episodes ─────────────────────────────────────────────────────────────────

@dataclass
class Episode:
    peak: int                  # month index in the window; -1 is the rebased base
    trough: int
    recovery: int | None
    depth: float
    cell_dd: float


def episodes(r_ew: np.ndarray, r_cell: np.ndarray) -> list[Episode]:
    """EW-9 falls of EPISODE_DD or more from its running peak, peak to recovery (the first
    later month at or above the peak) or window end. The cell's deepest drawdown inside
    the same months beside each."""
    eq = np.concatenate([[1.0], np.cumprod(1.0 + r_ew)])
    ce = np.concatenate([[1.0], np.cumprod(1.0 + r_cell)])
    out: list[Episode] = []
    n = len(eq)
    peak_i, peak_v, trough_i, depth = 0, 1.0, None, 0.0

    def close(rec):
        end = rec if rec is not None else n - 1
        seg = ce[peak_i:end + 1]
        cdd = float((1.0 - seg / np.maximum.accumulate(seg)).max())
        out.append(Episode(peak_i - 1, trough_i - 1, (rec - 1) if rec is not None else None,
                           depth, cdd))

    for i in range(1, n):
        if eq[i] >= peak_v:
            if trough_i is not None and depth >= EPISODE_DD:
                close(i)
            peak_i, peak_v, trough_i, depth = i, eq[i], None, 0.0
        else:
            d = 1.0 - eq[i] / peak_v
            if d > depth:
                depth, trough_i = d, i
    if trough_i is not None and depth >= EPISODE_DD:
        close(None)
    return out


# ── bootstrap ────────────────────────────────────────────────────────────────

def boot_index(n: int, block: int, draws: int = BOOT_N, seed: int = SEED) -> np.ndarray:
    """draws x n month orders from path_bootstrap._resample_indices, one seeded stream."""
    rng = random.Random(seed)
    return np.array([_resample_indices(n, block, rng) for _ in range(draws)], dtype=np.int64)


def _sharpe_rows(ex: np.ndarray) -> np.ndarray:
    s = ex.std(axis=1, ddof=1)
    return np.where(s > 0, SQRT12 * ex.mean(axis=1) / np.where(s > 0, s, 1.0), np.nan)


def _mdd_rows(r: np.ndarray) -> np.ndarray:
    eq = np.cumprod(1.0 + r, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.ones((len(r), 1)), eq], axis=1), axis=1)
    return (1.0 - eq / peak[:, 1:]).max(axis=1)


def boot_deltas(idx: np.ndarray, r_cell: np.ndarray, r_ew: np.ndarray, tbm: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray]:
    """Paired: a month's cell return, EW-9 return and T-bill return travel together."""
    rc, re_, rt = r_cell[idx], r_ew[idx], tbm[idx]
    d_s = _sharpe_rows(rc - rt) - _sharpe_rows(re_ - rt)
    d_m = _mdd_rows(re_) - _mdd_rows(rc)
    return d_s, d_m


def ci(draws: np.ndarray) -> tuple[float, float]:
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


# ── PBO ──────────────────────────────────────────────────────────────────────

def sharpe_metric(sub: np.ndarray) -> np.ndarray:
    """PBO metric: sqrt(12) x mean / sample sd of the rows given. Zero sd gives NaN,
    which cscv ranks worst."""
    s = sub.std(axis=0, ddof=1)
    return np.where(s > 0, SQRT12 * sub.mean(axis=0) / np.where(s > 0, s, 1.0), np.nan)


def run_pbo(M: np.ndarray, months: list[str]):
    """Trim the oldest months until S divides the row count (never pad)."""
    drop = M.shape[0] % PBO_S
    res = PBO.cscv(M[drop:], S=PBO_S, metric=sharpe_metric)
    return res, months[:drop]


# ════════════════════════════════════════════════════════════════════════════
# Verdicts
# ════════════════════════════════════════════════════════════════════════════

def counts(disc_point: float, hold_lo: float) -> bool:
    return hold_lo > 0 and disc_point > 0


def clearly_worse(hold_hi: float) -> bool:
    return hold_hi < 0


def headline_word(powered: bool, pbo: float, ds_disc: float, ds_hold_ci: tuple,
                  dm_disc: float, dm_hold_ci: tuple, refused: str | None = None
                  ) -> tuple[str, list[str]]:
    """The registered table; the first matching row wins. Returns (word, notes)."""
    if refused is not None:
        return f"REFUSED ({refused})", []
    if not powered:
        return "UNDERPOWERED", []
    cs = counts(ds_disc, ds_hold_ci[0])
    cm = counts(dm_disc, dm_hold_ci[0])
    ws = clearly_worse(ds_hold_ci[1])
    wm = clearly_worse(dm_hold_ci[1])
    notes: list[str] = []
    if PBO_FRAGILE < pbo <= PBO_VETO:
        notes.append("selection fragile")
    if (cs or cm) and pbo > PBO_VETO:
        return "PBO-VETO", notes
    if cs and cm:
        return "BEATS-EW", notes
    if cm:
        return "DRAWDOWN-ONLY", notes + (["Sharpe clearly worse"] if ws else [])
    if cs:
        return "SHARPE-ONLY", notes + (["drawdown clearly worse"] if wm else [])
    if ws or wm:
        return "CONTRARY", notes
    if (ds_hold_ci[0] > 0 and ds_disc <= 0) or (dm_hold_ci[0] > 0 and dm_disc <= 0):
        notes.append("holdout gain, discovery sign disagrees")
    return "NULL", notes


def forward_word(d_sharpe: float, d_mdd: float) -> str:
    a, b = d_sharpe > 0, d_mdd > 0
    if a and b:
        return "FORWARD-AGREES"
    if a or b:
        return "FORWARD-SPLIT"
    return "FORWARD-AGAINST"


def pbo_note(p: float) -> str:
    if p > PBO_VETO:
        return "veto"
    if p > PBO_FRAGILE:
        return "selection fragile"
    return ""


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def gate_inputs(inp: Inputs, P: Panel, s0: int) -> list[str]:
    """GI. The ETF caches cover the first decision's lookback to the cut; every SPY session
    in that range has a close for all nine; no ^IRX carry beyond 5 sessions; the two ^IRX
    copies agree within 0.01 points."""
    d0 = P.dates[s0]
    for t in TICKERS:
        s = inp.etf[t]
        if not s.dates or s.dates[0] > d0 or s.dates[-1] < IN_SAMPLE_END:
            raise Refused(EXIT_INPUT, f"GI: {t} must cover {d0} to {IN_SAMPLE_END}; has "
                                      f"{s.dates[:1]} .. {s.dates[-1:]}. Exit 3.",
                          f"GI {t} coverage")
    gaps = np.argwhere(~np.isfinite(P.adj[s0:]))
    if len(gaps):
        k, i = gaps[0]
        raise Refused(EXIT_INPUT, f"GI: {len(gaps)} missing ETF closes on SPY sessions from "
                                  f"{d0}; first {TICKERS[i]} on {P.dates[s0 + k]}. Exit 3.",
                      "GI missing close")
    worst = int(P.irx_carry[s0:].max())
    if worst > GI_IRX_CARRY:
        k = int(np.argmax(P.irx_carry[s0:])) + s0
        raise Refused(EXIT_INPUT, f"GI: ^IRX carried {worst} sessions to {P.dates[k]} "
                                  f"(limit {GI_IRX_CARRY}). Exit 3.", "GI IRX carry")
    agree = "one copy only"
    if inp.irx_alt is not None:
        m = dict(zip(inp.irx_alt.dates, inp.irx_alt.close))
        diffs = [(d, abs(c - m[d])) for d, c in zip(inp.irx.dates, inp.irx.close)
                 if d in m and d <= IN_SAMPLE_END]
        bad = [x for x in diffs if x[1] > GI_IRX_AGREE]
        if bad:
            raise Refused(EXIT_INPUT, f"GI: the two ^IRX copies differ by more than "
                                      f"{GI_IRX_AGREE} points on {len(bad)} dates (first "
                                      f"{bad[0][0]}, {bad[0][1]:.4f}). Exit 3.", "GI IRX copies")
        agree = (f"copies agree on {len(diffs)} common dates, worst "
                 f"{max((x[1] for x in diffs), default=0.0):.4f} points")
    return [f"  GI inputs: nine ETFs cover {d0} .. {IN_SAMPLE_END}; every SPY session has a "
            f"close for all nine; worst ^IRX carry {worst} sessions; {agree}   PASS"]


def confirmed_distribution(close_prev: float, step: float, div: float | None,
                           adj_ret: float) -> bool:
    """GB's distribution check (Resolved at build 2026-11-27): an adj/close jump above 5%
    passes only when the dividend feed lists a cash distribution on that ex-date whose
    implied jump, close_prev / (close_prev - D) - 1, matches the observed step within
    0.1 points. The feed match alone is circular on yfinance data, which builds Adj Close
    from the same feed (Resolved after review 2026-11-28), so the adjusted close's one-session
    return on the ex-date must also be within GB_ADJ_RET of zero: a real distribution drops
    the raw close and leaves the adjusted series smooth."""
    if div is None or not (0 < div < close_prev):
        return False
    if not (abs(adj_ret) <= GB_ADJ_RET):
        return False
    return abs(close_prev / (close_prev - div) - 1.0 - step) <= GB_DIV_MATCH


def gate_basis(inp: Inputs, d0: str, divs: dict | None = None) -> list[str]:
    """GB. Per ETF, from the lookback start to the cut: adj/close never falls by more than
    0.01% and never jumps by more than 5% between sessions; no daily adjusted return
    beyond +-25%. Prints the offending rows on a failure. A jump above 5% that the
    dividend feed confirms as a cash distribution passes and is printed (Resolved at
    build 2026-11-27); the fall bound and the return bound have no exemption."""
    lines, bad, passed = [], [], []
    for t in TICKERS:
        s = inp.etf[t]
        i0 = bisect.bisect_left(s.dates, d0)
        i1 = bisect.bisect_right(s.dates, IN_SAMPLE_END)
        d = s.dates[i0:i1]
        ratio = s.adj[i0:i1] / s.close[i0:i1]
        step = ratio[1:] / ratio[:-1] - 1.0
        ret = s.adj[i0 + 1:i1] / s.adj[i0:i1 - 1] - 1.0
        dv = (divs or {}).get(t)
        for k in np.where((step < -GB_RATIO_FALL) | (step > GB_RATIO_STEP)
                          | ~np.isfinite(step))[0]:
            row = f"    {t} {d[k]} -> {d[k + 1]}: adj/close step {step[k]:+.6f}"
            D = dv.get(d[k + 1]) if dv else None
            if step[k] > GB_RATIO_STEP and confirmed_distribution(s.close[i0 + k], step[k], D, ret[k]):
                implied = s.close[i0 + k] / (s.close[i0 + k] - D) - 1.0
                raw = s.close[i0 + k + 1] / s.close[i0 + k] - 1.0
                passed.append(f"{row}; feed distribution {D:.4f} on {d[k + 1]} implies "
                              f"{implied:+.6f}; raw close return {raw:+.4f}, adjusted "
                              f"return {ret[k]:+.4f}: confirmed")
                continue
            bad.append(row + ("" if step[k] <= GB_RATIO_STEP else
                              f"; feed distribution {D if D is not None else 'none'}; raw "
                              f"close return {s.close[i0 + k + 1] / s.close[i0 + k] - 1.0:+.4f}, "
                              f"adjusted return {ret[k]:+.4f}"))
        for k in np.where((np.abs(ret) > GB_RET) | ~np.isfinite(ret))[0]:
            bad.append(f"    {t} {d[k]} -> {d[k + 1]}: adjusted return {ret[k]:+.4f}")
        lines.append(f"{t} fall {np.nanmin(step):+.6f} jump {np.nanmax(step):+.4f} "
                     f"|ret| {np.nanmax(np.abs(ret)):.3f}")
    if bad:
        for b in bad:
            print(b)
        raise Refused(EXIT_INPUT, f"GB: {len(bad)} basis breaks (rows above). Exit 3.",
                      "GB basis")
    out = ["  GB basis (worst adj/close fall, worst jump, worst |daily adjusted return|):"]
    for i in range(0, len(lines), 3):
        out.append("    " + ";  ".join(lines[i:i + 3]))
    if passed:
        out.append(f"  GB jumps above {GB_RATIO_STEP:.0%} confirmed as cash distributions by the "
                   f"dividend feed (Resolved at build 2026-11-27):")
        out.extend(passed)
    out.append("  GB   PASS")
    return out


def gate_lookahead(inp: Inputs, P: Panel, me: list[int], j0: int, tables: dict) -> list[str]:
    """GX at run time: 24 evenly spaced decisions are recomputed on every series cut at
    that decision close, and must match the run's targets exactly."""
    last = max(j for j in range(j0, len(me)) if me[j] + 1 < len(P.dates))
    js = sorted(set(np.linspace(j0, last, GX_SAMPLES).astype(int).tolist()))
    bad = 0
    for j in js:
        t = me[j]
        Pc = build_panel(inp.cut(P.dates[t]), P.dates[t])
        if Pc.dates != P.dates[:t + 1] or t in month_end_idx(Pc.dates):
            raise Refused(1, "GX: a cut series is not a prefix of the calendar, or its last "
                             "row became a decision close. Exit 1.", "GX calendar")
        for cell in CELLS:
            st, w = targets(Pc.adj, Pc.tb, me[:j + 1], cell)
            st0, w0 = tables[cell][t + 1]
            if not (np.array_equal(st, st0) and np.array_equal(w, w0)):
                bad += 1
    if bad:
        raise Refused(1, f"GX: {bad} decisions moved when the series were cut at the decision "
                         f"close. Exit 1.", "GX lookahead")
    return [f"  GX no lookahead: {len(js)} decisions x {len(CELLS)} cells recomputed on series "
            f"cut at the decision close; 0 moved   PASS"]


def gate_replay(r_forced: np.ndarray, r_ew: np.ndarray) -> list[str]:
    """GR. Every sleeve forced IN at EW weights reproduces EW-9's monthly returns."""
    diff = float(np.max(np.abs(r_forced - r_ew))) if len(r_ew) else 0.0
    if not (diff <= GR_TOL):
        raise Refused(EXIT_INPUT, f"GR: forced-IN EW cell differs from EW-9 by {diff:.3e} "
                                  f"in a month (tolerance {GR_TOL:.0e}). Exit 3.", "GR replay")
    return [f"  GR replay: forced-IN EW cell vs EW-9 over {len(r_ew)} months, worst |diff| "
            f"{diff:.1e} (float rounding only)   PASS"]


# ════════════════════════════════════════════════════════════════════════════
# The options arm (descriptive, never in a verdict)
# ════════════════════════════════════════════════════════════════════════════

_OPT_RE = re.compile(r"^SPY_(\d{8})_([0-9.]+)([CP])\.csv$")


def option_index(cache_dir: Path) -> tuple[dict, str | None]:
    """({expiry: sorted call strikes}, first cached SPY expiry of any right)."""
    calls: dict[str, set] = {}
    first = None
    if not Path(cache_dir).exists():
        return {}, None
    for p in Path(cache_dir).glob("SPY_*.csv"):
        m = _OPT_RE.match(p.name)
        if not m:
            continue
        e = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
        first = e if first is None or e < first else first
        if m.group(3) == "C":
            calls.setdefault(e, set()).add(m.group(2))
    return {e: sorted(s, key=float) for e, s in calls.items()}, first


def is_third_friday(d: str) -> bool:
    x = date.fromisoformat(d)
    return x.weekday() == 4 and 15 <= x.day <= 21


def pick_expiry(entry: str, expiries) -> str | None:
    """Third-Friday expiry with calendar DTE nearest 65; a tie takes the later one."""
    e0 = date.fromisoformat(entry)
    best = None
    for e in expiries:
        if e <= entry or not is_third_friday(e):
            continue
        key = (abs((date.fromisoformat(e) - e0).days - OPT_DTE), -date.fromisoformat(e).toordinal())
        if best is None or key < best[0]:
            best = (key, e)
    return best[1] if best else None


def pick_strike(strikes: list[str], target: float, tie_high: bool) -> str | None:
    best = None
    for s in strikes:
        v = float(s)
        key = (abs(v - target), -v if tie_high else v)
        if best is None or key < best[0]:
            best = (key, s)
    return best[1] if best else None


def _read_option_rows(path: Path) -> dict:
    out = {}
    with path.open(newline="") as fh:
        for r in csv.DictReader(fh):
            d = (r.get("Time") or "")[:10]
            if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
                out[d] = r
    return out


@dataclass
class OptTrade:
    entry: str
    exit: str | None
    expiry: str | None
    k_long: str | None
    k_short: str | None
    priced: bool
    why: str
    debit: float = float("nan")
    pnl: float = float("nan")
    rod: float = float("nan")
    spy_ret: float = float("nan")


def options_arm(P: Panel, execs: list[Exec], cache_dir: Path, commission: float
                ) -> tuple[list[OptTrade], int, str | None]:
    """One SPY call vertical per execution session where the headline holds SPY IN; exit
    at the next execution session. Returns (wanted trades, open trades, first expiry)."""
    from scripts.backtest import simulate as SIM
    calls, first_exp = option_index(cache_dir)
    rows_of = lru_cache(maxsize=None)(lambda p: _read_option_rows(p))
    spy = TICKERS.index("SPY")
    trades, n_open = [], 0
    for i, ex in enumerate(execs):
        if not ex.states[spy]:
            continue
        if i + 1 >= len(execs) or execs[i + 1].date > IN_SAMPLE_END:
            n_open += 1
            continue
        ent, xit = ex.date, execs[i + 1].date
        spot = float(P.spy_close[ex.k])
        exp = pick_expiry(ent, calls.keys())
        if exp is None:
            trades.append(OptTrade(ent, xit, None, None, None, False, "no expiry"))
            continue
        kl = pick_strike(calls[exp], spot, tie_high=False)
        ks = pick_strike(calls[exp], OPT_OTM * spot, tie_high=True)
        tr = OptTrade(ent, xit, exp, kl, ks, False, "")
        trades.append(tr)
        if kl == ks:
            # Resolved at build (2026-11-27): one strike for both legs is not a vertical.
            tr.why = "strikes coincide"
            continue
        ymd = exp.replace("-", "")
        rl = rows_of(Path(cache_dir) / f"SPY_{ymd}_{kl}C.csv")
        rs = rows_of(Path(cache_dir) / f"SPY_{ymd}_{ks}C.csv")
        fl = SIM.entry_day_fill(rl.get(ent), 1)
        fs = SIM.entry_day_fill(rs.get(ent), -1)
        if fl is None or fl[0] is None or fs is None or fs[0] is None:
            tr.why = "entry not priced"
            continue
        debit = float(fl[0]) - float(fs[0])
        if not debit > 0:
            tr.why = "debit not above 0"
            continue
        xl, xs = rl.get(xit), rs.get(xit)
        ml = SIM._close_mid(xl) if xl is not None and not SIM._is_junk_quote(xl) else None
        ms = SIM._close_mid(xs) if xs is not None and not SIM._is_junk_quote(xs) else None
        if ml is None or ms is None:
            tr.why = "exit not priced"
            continue
        comm = commission * OPT_LEGS * 2
        tr.priced, tr.why, tr.debit = True, "priced", debit
        tr.pnl = ((ml - ms) - debit) * 100.0 - comm
        tr.rod = tr.pnl / (debit * 100.0)
        k_x = P.dates.index(xit)
        tr.spy_ret = float(P.adj[k_x, spy] / P.adj[ex.k, spy] - 1.0)
    return trades, n_open, first_exp


def load_commission() -> float:
    import yaml
    from scripts.backtest import simulate as SIM
    cfg = (yaml.safe_load(BACKTEST_YML.read_text()) or {}).get("simulation", {}) or {}
    comm, slip = SIM._cost_knobs(cfg)
    if slip:
        raise Refused(EXIT_INPUT, f"options arm: slippage_frac_of_spread={slip}; the "
                                  f"registration prices at 0 slippage. Exit 3.", "slippage")
    return comm


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
# ════════════════════════════════════════════════════════════════════════════

def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def f3(x: float) -> str:
    return f"{x:+.3f}" if x == x else "  n/a"


STATS_HEAD = (f"  {'curve':<11}{'Sharpe':>7}{'MDD':>7}{'dlyMDD':>7}{'CAGR':>7}{'dCAGR':>7}"
              f"{'turn':>6}{'TIM':>5}{'alpha':>7}{'(se)':>6}{'beta':>6}{'(se)':>5}  worst year")


def stats_row(label: str, s: Stats, ew_cagr: float) -> str:
    return (f"  {label:<11}{s.sharpe:>7.3f}{s.mdd:>7.1%}{s.mdd_daily:>7.1%}{s.cagr:>7.2%}"
            f"{(s.cagr - ew_cagr) * 100:>+7.2f}{s.turnover:>6.2f}{s.tim:>5.2f}"
            f"{s.alpha:>+7.3f}{s.alpha_se:>6.3f}{s.beta:>6.2f}{s.beta_se:>5.2f}  {s.worst_year}")


# ════════════════════════════════════════════════════════════════════════════
# In-sample run
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class WindowOut:
    name: str
    first: str
    last: str
    n: int
    n_episodes: int
    d_sharpe: dict             # cell -> (point, lo, hi)
    d_mdd: dict
    d_cagr: dict               # cell -> points a year
    alpha: dict
    beta: dict
    powered: bool


def curves_at(P: Panel, me: list[int], j0: int, tables: dict, cost_bp: float) -> dict:
    out = {c: simulate(P, tables[c], c, cost_bp) for c in CELLS}
    ks = sorted(tables[HEADLINE])
    out["EW-9"] = benchmark_rebalanced(P, {t: 1.0 / len(TICKERS) for t in TICKERS}, ks,
                                       "EW-9", cost_bp)
    return out


def window_block(P: Panel, grid: MonthGrid, w: Window, curves: dict, mret: dict,
                 tbm: np.ndarray, boot_n: int, extra: dict) -> WindowOut:
    ew = mret["EW-9"]
    print(f"  months {w.months[0]} .. {w.months[-1]} (N = {w.n}); equity rebased to 1.0 at the "
          f"window start; Sharpe on monthly excess returns over T-bills")
    st = {c: window_stats(curves[c], mret[c], tbm, ew, grid, w)
          for c in list(CELLS) + ["EW-9"] + list(extra)}
    ew_c = st["EW-9"].cagr
    print("\n  Sharpe, monthly MDD, daily MDD, CAGR, dCAGR vs EW-9 (points a year), turnover "
          "a year,\n  time in market, Jensen alpha a year and beta on EW-9 (Newey-West se, 12 "
          "lags), worst calendar year")
    print(STATS_HEAD)
    for c in [HEADLINE] + [x for x in CELLS if x != HEADLINE]:
        print(stats_row(c, st[c], ew_c))
    for c in ["EW-9"] + list(extra):
        print(stats_row(c, st[c], ew_c))
    sl = st[HEADLINE].sleeve_in
    print(f"  {HEADLINE} time IN per sleeve: "
          + "  ".join(f"{t} {sl[i]:.0%}" for i, t in enumerate(TICKERS)))

    eps = episodes(w.sl(ew), w.sl(mret[HEADLINE]))
    print(f"\n  EW-9 drawdown episodes ({EPISODE_DD:.0%}+ from its running peak), {HEADLINE} "
          f"beside each:")
    print(f"  {'peak':<10}{'trough':<10}{'recovery':<10}{'EW-9 depth':>11}{'cell DD':>9}"
          f"{'gap':>8}")
    for e in eps:
        pk = w.months[e.peak] if e.peak >= 0 else "(base)"
        rc = w.months[e.recovery] if e.recovery is not None else "(open)"
        print(f"  {pk:<10}{w.months[e.trough]:<10}{rc:<10}{e.depth:>11.1%}{e.cell_dd:>9.1%}"
              f"{e.depth - e.cell_dd:>+8.1%}")
    print(f"  episodes with a trough inside the window: {len(eps)} (floor {MIN_EPISODES})")
    powered = w.n >= MIN_MONTHS and len(eps) >= MIN_EPISODES
    print(f"  GN floors: {w.n} months (floor {MIN_MONTHS}), {len(eps)} episodes (floor "
          f"{MIN_EPISODES}) -> {'powered' if powered else 'UNDERPOWERED'}")

    print(f"\n  Paired moving block bootstrap on monthly returns: block {BLOCK}, {boot_n} draws, "
          f"seed {SEED}.\n  The rule is not re-run on a resampled path; the dMDD interval "
          f"measures the noise in one drawdown figure.")
    idx = boot_index(w.n, BLOCK, boot_n)
    tw = w.sl(tbm)
    d_s, d_m, d_c, al, be = {}, {}, {}, {}, {}
    print(f"  {'cell':<11}{'dSharpe':>8}{'CI95':>18}{'dMDD':>8}{'CI95':>18}{'dCAGR':>7}")
    for c in [HEADLINE] + [x for x in CELLS if x != HEADLINE]:
        bs, bm = boot_deltas(idx, w.sl(mret[c]), w.sl(ew), tw)
        ps = st[c].sharpe - st["EW-9"].sharpe
        pm = st["EW-9"].mdd - st[c].mdd
        d_s[c] = (ps, *ci(bs))
        d_m[c] = (pm, *ci(bm))
        d_c[c] = (st[c].cagr - ew_c) * 100
        al[c], be[c] = st[c].alpha, st[c].beta
        tag = "" if c == HEADLINE else "  (grid, not graded)"
        print(f"  {c:<11}{ps:>+8.3f}  [{d_s[c][1]:+.3f}, {d_s[c][2]:+.3f}]{pm:>+8.3f}  "
              f"[{d_m[c][1]:+.3f}, {d_m[c][2]:+.3f}]{d_c[c]:>+7.2f}{tag}")
    for b in extra:
        print(f"  {HEADLINE} vs {b} (printed, no word): dSharpe "
              f"{st[HEADLINE].sharpe - st[b].sharpe:+.3f}  dMDD {st[b].mdd - st[HEADLINE].mdd:+.3f}"
              f"  dCAGR {(st[HEADLINE].cagr - st[b].cagr) * 100:+.2f} points")
    return WindowOut(w.name, w.months[0], w.months[-1], w.n, len(eps), d_s, d_m, d_c, al, be,
                     powered)


def window_deltas(w: Window, mret: dict, tbm: np.ndarray, idx: np.ndarray, cell: str
                  ) -> tuple[tuple, tuple]:
    ew, rc, tw = w.sl(mret["EW-9"]), w.sl(mret[cell]), w.sl(tbm)
    bs, bm = boot_deltas(idx, rc, ew, tw)
    ps = sharpe(rc - tw) - sharpe(ew - tw)
    pm = mdd(ew) - mdd(rc)
    return (ps, *ci(bs)), (pm, *ci(bm))


def run_in_sample(inp_full: Inputs, boot_n: int = BOOT_N, opt_dir: Path = OPTION_CACHE,
                  commission: float | None = None, divs: dict | None = None) -> dict:
    """Everything graded. Cuts every series at IN_SAMPLE_END before computing anything."""
    inp = inp_full.cut(IN_SAMPLE_END)
    P = build_panel(inp, IN_SAMPLE_END)
    me = month_end_idx(P.dates)
    j0 = first_common_decision(P, me)
    if j0 is None:
        raise Refused(EXIT_INPUT, "GI: no month-end at which all 12 cells are defined for all "
                                  "nine ETFs. Exit 3.", "GI first decision")
    t0 = me[j0]
    s0 = min(me[j0 - MAX_LOOKBACK], t0 - IV_DAYS)
    print(f"  first common decision {P.dates[t0]} (first execution close {P.dates[t0 + 1]}); "
          f"lookback start {P.dates[s0]}")
    section("GATES")
    for line in gate_inputs(inp, P, s0):
        print(line)
    divs = {t: read_dividends(t) for t in TICKERS} if divs is None else divs
    for line in gate_basis(inp, P.dates[s0], divs):
        print(line)
    tables = {c: decision_table(P, me, j0, c) for c in CELLS}
    for line in gate_lookahead(inp, P, me, j0, tables):
        print(line)
    print("  GX calendar: the last row of a cut series is never a decision close "
          "(month_end_idx; pinned in tests)   PASS")
    print(f"  GC the cut: every series is cut at {IN_SAMPLE_END} before any computation "
          f"(pinned in tests)")
    ks = sorted(tables[HEADLINE])
    curves = curves_at(P, me, j0, tables, COST_BP)
    curves["SPY"] = benchmark_hold(P, "SPY", ks[0], "SPY")
    curves["60-40"] = benchmark_rebalanced(P, {"SPY": 0.6, "IEF": 0.4}, ks, "60-40", COST_BP)
    grid = month_grid(P, ks[0])
    tbm = monthly_tbill(P, grid)
    mret = {c: monthly(cv.g, grid) for c, cv in curves.items()}
    forced = simulate(P, decision_table(P, me, j0, None), "forced-IN", COST_BP)
    for line in gate_replay(monthly(forced.g, grid), mret["EW-9"]):
        print(line)

    disc = make_window(grid, "discovery", None, DISCOVERY_END)
    hold = make_window(grid, "holdout", *HOLDOUT)
    extra = ("SPY", "60-40")
    section(f"DISCOVERY {disc.months[0]} to {disc.months[-1]} (sign check)")
    rd = window_block(P, grid, disc, curves, mret, tbm, boot_n, extra)
    section(f"HOLDOUT {hold.months[0]} to {hold.months[-1]} (decides the verdict)")
    rh = window_block(P, grid, hold, curves, mret, tbm, boot_n, extra)

    section("PBO / CSCV (12 cells, S=16, monthly excess returns over T-bills)")
    ins = make_window(grid, "in-sample", None, HOLDOUT[1])
    M = np.column_stack([ins.sl(mret[c]) - ins.sl(tbm) for c in CELLS])
    res, dropped = run_pbo(M, ins.months)
    print(f"  in-sample rows {M.shape[0]} -> {res.n_rows} after trimming {len(dropped)} oldest "
          f"months ({', '.join(dropped) if dropped else 'none'}); {res.n_combinations} splits")
    print(f"  PBO {res.pbo:.3f}  n_at_zero {res.n_at_zero}  {pbo_note(res.pbo)}")
    best = np.bincount(res.n_star, minlength=len(CELLS))
    print("  in-sample best cell, share of splits: "
          + "  ".join(f"{c} {best[i] / res.n_combinations:.0%}" for i, c in enumerate(CELLS)
                      if best[i]))
    Md = np.column_stack([disc.sl(mret[c]) - disc.sl(tbm) for c in CELLS])
    rdp, dropped_d = run_pbo(Md, disc.months)
    print(f"  discovery PBO (printed only): {rdp.pbo:.3f}  n_at_zero {rdp.n_at_zero}  "
          f"(rows {rdp.n_rows}, {len(dropped_d)} oldest months trimmed)")
    print("  With 12 cells, pure noise gives a PBO near 0.50. PBO never selects a cell.")

    powered = rd.powered and rh.powered
    hw, notes = headline_word(powered, res.pbo, rd.d_sharpe[HEADLINE][0], rh.d_sharpe[HEADLINE][1:],
                              rd.d_mdd[HEADLINE][0], rh.d_mdd[HEADLINE][1:])

    section("WORDS BY THE SAME ROWS (printed only)")
    print("  Grid cells (grid, not graded):")
    for c in CELLS:
        if c == HEADLINE:
            continue
        wd, nt = headline_word(powered, res.pbo, rd.d_sharpe[c][0], rh.d_sharpe[c][1:],
                               rd.d_mdd[c][0], rh.d_mdd[c][1:])
        print(f"    {c:<10} {wd}{' (' + '; '.join(nt) + ')' if nt else ''}  (grid, not graded)")
    print(f"  Sensitivities for {HEADLINE} (printed only):")
    for blk in BLOCK_SENS:
        sd, sh = [], []
        for w, rec in ((disc, sd), (hold, sh)):
            rec.extend(window_deltas(w, mret, tbm, boot_index(w.n, blk, boot_n), HEADLINE))
        wd, nt = headline_word(powered, res.pbo, sd[0][0], sh[0][1:], sd[1][0], sh[1][1:])
        print(f"    block {blk:>2}: holdout dSharpe {sh[0][0]:+.3f} [{sh[0][1]:+.3f}, "
              f"{sh[0][2]:+.3f}] dMDD {sh[1][0]:+.3f} [{sh[1][1]:+.3f}, {sh[1][2]:+.3f}] -> "
              f"{wd}{' (' + '; '.join(nt) + ')' if nt else ''}  (printed only)")
    for cbp in COST_SENS:
        cv = curves_at(P, me, j0, tables, cbp)
        mr = {c: monthly(x.g, grid) for c, x in cv.items()}
        Mc = np.column_stack([ins.sl(mr[c]) - ins.sl(tbm) for c in CELLS])
        rc_, _ = run_pbo(Mc, ins.months)
        sd = window_deltas(disc, mr, tbm, boot_index(disc.n, BLOCK, boot_n), HEADLINE)
        sh = window_deltas(hold, mr, tbm, boot_index(hold.n, BLOCK, boot_n), HEADLINE)
        wd, nt = headline_word(powered, rc_.pbo, sd[0][0], sh[0][1:], sd[1][0], sh[1][1:])
        print(f"    cost {cbp:>4.0f} bp (both curves): holdout dSharpe {sh[0][0]:+.3f} "
              f"[{sh[0][1]:+.3f}, {sh[0][2]:+.3f}] dMDD {sh[1][0]:+.3f} [{sh[1][1]:+.3f}, "
              f"{sh[1][2]:+.3f}] PBO {rc_.pbo:.3f} -> {wd}"
              f"{' (' + '; '.join(nt) + ')' if nt else ''}  (printed only)")

    section("OPTIONS ARM — the SPY sleeve as a call vertical (descriptive, not graded)")
    comm = load_commission() if commission is None else commission
    trades, n_open, first_exp = options_arm(P, curves[HEADLINE].execs, opt_dir, comm)
    priced = [t for t in trades if t.priced]
    late = [t for t in trades if first_exp and t.entry[:7] >= first_exp[:7]]
    late_p = [t for t in late if t.priced]
    print(f"  long call nearest the unadjusted SPY close, short call nearest {OPT_OTM:.2f}x, "
          f"third-Friday expiry nearest {OPT_DTE} DTE;\n  entry via simulate.entry_day_fill, "
          f"exit at each leg's closing mid on a two-sided non-junk quote;\n  commission "
          f"{comm:.2f} per leg per contract each side, slippage 0. Cached quotes only, no fetch.")
    print(f"  coverage, full in-sample window: {len(priced)}/{len(trades)} trades priced")
    print(f"  coverage, from the first cached SPY expiry ({first_exp or 'none'}): "
          f"{len(late_p)}/{len(late)} trades priced")
    print(f"  open at the cut (exit after {IN_SAMPLE_END}, not wanted): {n_open}")
    whys: dict[str, int] = {}
    for t in trades:
        whys[t.why] = whys.get(t.why, 0) + 1
    print("  by outcome: " + "  ".join(f"{k} {v}" for k, v in sorted(whys.items())))
    if priced:
        print(f"  {'entry':<11}{'exit':<11}{'expiry':<11}{'long':>8}{'short':>8}{'debit':>8}"
              f"{'P&L $':>9}{'RoD':>8}{'SPY adj':>9}")
        for t in priced:
            print(f"  {t.entry:<11}{t.exit:<11}{t.expiry:<11}{float(t.k_long):>8.1f}"
                  f"{float(t.k_short):>8.1f}{t.debit:>8.2f}{t.pnl:>9.2f}{t.rod:>+8.1%}"
                  f"{t.spy_ret:>+9.2%}")
        rods = np.array([t.rod for t in priced])
        pnls = np.array([t.pnl for t in priced])
        print(f"  mean return on debit {rods.mean():+.1%}; hit rate {(pnls > 0).mean():.0%}; "
              f"P&L per one vertical: total ${pnls.sum():,.2f}, mean ${pnls.mean():,.2f}")
    print("  The cache was filled for the book's plays, so these strikes and expiries are not a "
          "random sample.")
    return dict(disc=rd, hold=rh, pbo=res, pbo_disc=rdp, word=hw, notes=notes,
                opt=(len(priced), len(trades)), j0_date=P.dates[t0], s0_date=P.dates[s0])


# ════════════════════════════════════════════════════════════════════════════
# Forward
# ════════════════════════════════════════════════════════════════════════════

def report_forward(inp: Inputs, boot_n: int = BOOT_N) -> str:
    section(f"FORWARD — {HEADLINE} vs EW-9 from {FORWARD_START} (one shot, "
            f"{FORWARD_MIN_MONTHS}-month minimum)")
    P = build_panel(inp, inp.etf["SPY"].dates[-1])
    me = month_end_idx(P.dates)
    fwd_months = sorted({P.dates[k][:7] for k in me if P.dates[k][:7] >= FORWARD_START})
    n = len(fwd_months)
    print(f"  data to {P.dates[-1]}; complete forward months: {n}")
    if n < FORWARD_MIN_MONTHS:
        word = f"STILL-OPEN ({n} forward months of {FORWARD_MIN_MONTHS})"
        print(f"  {word}. The read fires once, on the first run after {FORWARD_READ_AFTER} is "
              f"complete.")
        return word
    j0 = first_common_decision(P, me)
    tables = {HEADLINE: decision_table(P, me, j0, HEADLINE)}
    ks = sorted(tables[HEADLINE])
    if not np.isfinite(P.adj[ks[0] - 1:]).all() or not np.isfinite(P.tb[ks[0]:]).all():
        print("  a close is missing after the cut; the forward line cannot be computed")
        return "REFUSED (forward data gap)"
    cv = simulate(P, tables[HEADLINE], HEADLINE)
    ew = benchmark_rebalanced(P, {t: 1.0 / len(TICKERS) for t in TICKERS}, ks, "EW-9")
    grid = month_grid(P, ks[0])
    w = make_window(grid, "forward", FORWARD_START, "9999-12")
    tbm = monthly_tbill(P, grid)
    mret = {HEADLINE: monthly(cv.g, grid), "EW-9": monthly(ew.g, grid)}
    s6, m6 = window_deltas(w, mret, tbm, boot_index(w.n, 6, boot_n), HEADLINE)
    word = forward_word(s6[0], m6[0])
    print(f"  forward months {w.months[0]} .. {w.months[-1]} (N = {w.n}): dSharpe {s6[0]:+.3f} "
          f"[{s6[1]:+.3f}, {s6[2]:+.3f}]  dMDD {m6[0]:+.3f} [{m6[1]:+.3f}, {m6[2]:+.3f}] "
          f"(block-6 CIs) -> {word}")
    print("  The verdict of record is the first forward run that prints a word other than "
          "STILL-OPEN; later runs are descriptive.")
    return word


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=False).stdout.strip()
    except OSError:
        return ""


def check_era() -> None:
    requested = era_mod.requested_era()
    if requested != era_mod.CURRENT:
        raise Refused(era_mod.EXIT_THIN_ERA,
                      f"{NAME} reads yfinance market closes, which carry no era; era "
                      f"{requested!r} does not apply — run it without --era. Exit 2.", "era")


def print_verdict(out: dict | None, fwd: str, refused: str | None = None) -> None:
    section("VERDICT")
    hl = f"holdout {HOLDOUT[0]} to {HOLDOUT[1]}"
    if refused is not None:
        print(f">>> {NAME} HEADLINE (TB-12-EW vs EW-9, {hl}, 5 bp): REFUSED ({refused}) <<<")
        return
    rd, rh = out["disc"], out["hold"]
    hl = f"holdout {rh.first} to {rh.last}"
    notes = out["notes"]
    print(f">>> {NAME} HEADLINE (TB-12-EW vs EW-9, {hl}, 5 bp): {out['word']}"
          f"{' (' + '; '.join(notes) + ')' if notes else ''} <<<")

    def wl(r: WindowOut) -> str:
        s, m = r.d_sharpe[HEADLINE], r.d_mdd[HEADLINE]
        return (f"dSharpe {s[0]:+.3f} [{s[1]:+.3f}, {s[2]:+.3f}] dMDD {m[0]:+.3f} "
                f"[{m[1]:+.3f}, {m[2]:+.3f}] dCAGR {r.d_cagr[HEADLINE]:+.2f} points "
                f"alpha {r.alpha[HEADLINE]:+.3f} beta {r.beta[HEADLINE]:.2f}")
    print(f">>> {NAME} DISCOVERY ({rd.first} to {rd.last}): {wl(rd)} <<<")
    print(f">>> {NAME} HOLDOUT ({rh.first} to {rh.last}): {wl(rh)} <<<")
    p = out["pbo"].pbo
    pn = pbo_note(p)
    print(f">>> {NAME} PBO (12 cells, S=16, in-sample): {p:.3f}"
          f"{' (' + pn + ')' if pn == 'selection fragile' else ''} <<<")
    pr, wa = out["opt"]
    print(f">>> {NAME} OPTIONS ARM (descriptive, not graded): {pr}/{wa} trades priced <<<")
    print(f">>> {NAME} FORWARD (TB-12-EW vs EW-9 from {FORWARD_START}, 36-month minimum): "
          f"{fwd} <<<")
    print("  A statistic counts when its holdout CI lower bound is above 0 and its discovery "
          "point estimate is above 0.")
    print(f"  Nothing ships from this study ({Path(REGISTRATION).name}).")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=NAME)
    ap.add_argument("--refresh", action="store_true", help="refetch the yfinance series")
    ap.add_argument("--boot-n", type=int, default=BOOT_N, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    print(f"{NAME} — does monthly trend across nine ETFs beat holding all nine?")
    print(f"  registration {REGISTRATION}")
    sha = _git("rev-parse", "--short", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    print(f"  git {sha or '?'} ({'dirty' if dirty else 'clean'} working tree)")
    print("  era: current (inputs are unversioned market closes)")
    print(f"  windows: discovery from the first common decision month (printed under DISCOVERY) to "
          f"{DISCOVERY_END}, holdout {HOLDOUT[0]} to "
          f"{HOLDOUT[1]}, gap 2026-09 to 2026-11 (in no window), forward from {FORWARD_START}; "
          f"in-sample cut {IN_SAMPLE_END}")
    print(f"  seal: starts {era_mod.SEAL_START}; binds play signal dates; this study reads no "
          f"play, flow signal or backtest row")
    print(f"  money: {COST_BP:.0f} bp per side on every sleeve incl. T-bills; bootstrap block "
          f"{BLOCK}, {args.boot_n} draws, seed {SEED}")
    try:
        check_era()
        inp = load_inputs(args.refresh)
        for t, s in inp.etf.items():
            print(f"  input {_cache_path(t).relative_to(ROOT)}: {len(s.dates)} rows, "
                  f"{s.dates[0]} .. {s.dates[-1]}")
        print(f"  input {inp.irx_source} (^IRX, read): {inp.irx.dates[0]} .. {inp.irx.dates[-1]}")
        if inp.irx_alt is not None:
            print(f"  input {IRX_TREND_OVERLAY.relative_to(ROOT)} (^IRX, GI agreement only): "
                  f"{inp.irx_alt.dates[0]} .. {inp.irx_alt.dates[-1]}")
        out = run_in_sample(inp, args.boot_n)
    except Refused as exc:
        print(f"\nREFUSED — {exc.message}")
        print_verdict(None, "", refused=exc.reason)
        return exc.code
    fwd = report_forward(inp, args.boot_n)
    print_verdict(out, fwd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
