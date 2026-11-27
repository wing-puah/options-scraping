"""vol_managed_spy — does cutting SPY exposure when volatility is high beat a constant SPY and T-bill mix?

REGISTRATION: research/pre-registrations/f4_deployment/vol_managed_spy.md (registered
2026-11-27, second read passed, committed 2b528c7). Every constant, floor, seed, window
and verdict word below is that file's. Read it before changing anything here.

WHAT IT ASKS
------------
At each month-end close the rule sets one weight in SPY, the rest in T-bills:
`w = min(1, target / sigma)` (VOL) or `min(1, (target / sigma)^2)` (VAR), where sigma is
the annualised sample sd of the last N daily log returns of the SPY adjusted close,
ending with the return into the decision close. The portfolio trades to `w` at the next
session's close, 5 bp per side on the SPY notional traded only. Headline cell VOL-21-12
against MIX, a constant mix at the rule's own mean weight in the window graded. Graded
on the holdout 2010-01..2026-08 by a Holm family of two (dSharpe, dMDD) with a discovery
sign check; ARM R grades the Moreira-Muir alpha on SPY with its own word. Eleven more
cells exist only for PBO.

DATA
----
yfinance, auto_adjust=False. `backtests/vol_managed_spy/SPY.csv` (date, close,
adj_close) is fetched only with `--refresh`; without it a missing file refuses (exit 3).
`--refresh` also writes `backtests/vol_managed_spy/IRX.csv` and `GSPC.csv`; the module
reads those copies when they exist, else `backtests/trend_overlay/`'s, which it never
writes, and gate GI checks the two copies against each other. Zero and negative ^IRX
quotes are data. No close after 2026-09-22 enters the in-sample run; the forward read
opens with 2026-12.

Nothing ships from this study. Run:

    python -m scripts.backtest_study.f4_deployment.vol_managed_spy --refresh
    python -m scripts.backtest_study run vol_managed_spy
"""
from __future__ import annotations

import argparse
import bisect
import csv
import math
import random
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib.path_bootstrap import _resample_indices  # noqa: E402

REGISTRATION = "research/pre-registrations/f4_deployment/vol_managed_spy.md"
NAME = "vol_managed_spy"
CACHE_DIR = ROOT / "backtests" / "vol_managed_spy"
TREND_DIR = ROOT / "backtests" / "trend_overlay"

SYMBOLS = {"SPY": ("SPY", "1993-01-01"), "IRX": ("^IRX", "1960-01-01"),
           "GSPC": ("^GSPC", "1948-01-01")}
SPY_START = "1993-01-29"

IN_SAMPLE_END = "2026-09-22"
DISCOVERY_END = "2009-12"
HOLDOUT = ("2010-01", "2026-08")
POSTPUB = ("2017-01", "2026-08")
FORWARD = ("2026-12", "2029-11")
FORWARD_MIN_MONTHS = 36
SUNSET = "2030-11-30"

SCALINGS = ("VOL", "VAR")
WINDOWS_N = (21, 63)
TARGETS = (0.10, 0.12, 0.15)
CELLS = tuple(f"{s}-{n}-{int(round(t * 100))}" for s in SCALINGS for n in WINDOWS_N
              for t in TARGETS)
HEADLINE = "VOL-21-12"
MAX_N = max(WINDOWS_N)
CAP = 1.0

COST_BP = 5.0
COST_SENS = (0.0, 15.0)
BLOCK = 12
BLOCK_SENS = (6, 24)
FORWARD_BLOCK = 6
BOOT_N = 5_000
SEED = 20261127
HOLM_FIRST = 0.0125
HOLM_SECOND = 0.025
PBO_S = 16
PBO_VETO = 0.50
PBO_FRAGILE = 0.25
EPISODE_DD = 0.15
MIN_MONTHS = 96
MIN_EPISODES = 2
NW_LAGS = 12
TRADING_DAYS = 252
CVAR_Q = 0.05

GI_IRX_CARRY = 5
GI_AGREE = 0.01              # points
GB_RATIO_FALL = 1e-4         # adj/close may fall at most 0.01% between sessions
GB_RATIO_STEP = 0.02         # and never jump by more than 2%
GB_RET = 0.25                # no daily adjusted return beyond +-25%
GX_SAMPLES = 24
GR_TOL = 1e-12

HEADLINE_WORDS = ("UNDERPOWERED", "PBO-VETO", "BEATS-MIX", "DRAWDOWN-ONLY", "SHARPE-ONLY",
                  "CONTRARY", "NULL")
ARM_R_WORDS = ("UNDERPOWERED", "PBO-VETO", "ALPHA", "NEGATIVE-ALPHA", "NO-ALPHA")

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
    """yfinance -> `backtests/vol_managed_spy/<name>.csv`. `end` is exclusive, so today's
    bar is never fetched. A row with no close is not written (a missing session)."""
    import pandas as pd
    import yfinance as yf
    sym, start = SYMBOLS[name]
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
    return path


def _num(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def read_prices(path: Path) -> list[tuple[str, float, float]]:
    """(date, close, adj_close), ascending. EVERY row is kept; an empty or non-numeric
    field is NaN, so gate GI sees it rather than a silent drop."""
    with Path(path).open(newline="") as fh:
        rows = [(r["date"][:10], _num(r.get("close")), _num(r.get("adj_close")))
                for r in csv.DictReader(fh)]
    return sorted(rows)


def read_yield(path: Path) -> list[tuple[str, float, float]]:
    """^IRX rows with a finite close, ascending. A close at or below zero is DATA and is
    kept as printed; an empty or non-numeric close is no row (the panel carries)."""
    out = []
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            c = _num(r.get("close"))
            if math.isfinite(c):
                out.append((r["date"][:10], c, c))
    return sorted(out)


def raw_nonpositive_dates(path: Path) -> list[str]:
    """Dates of rows in the raw file whose close parses to a finite number at or below 0.
    Written apart from `read_yield` so gate GI's count is a real check."""
    out = []
    with Path(path).open(newline="") as fh:
        for line in fh.read().splitlines()[1:]:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            try:
                v = float(parts[1])
            except ValueError:
                continue
            if math.isfinite(v) and v <= 0:
                out.append(parts[0][:10])
    return sorted(out)


@dataclass
class Series:
    dates: list[str]
    close: np.ndarray
    adj: np.ndarray

    def cut(self, end: str) -> "Series":
        k = bisect.bisect_right(self.dates, end)
        return Series(self.dates[:k], self.close[:k].copy(), self.adj[:k].copy())

    def span(self) -> str:
        return f"{self.dates[0]} .. {self.dates[-1]}" if self.dates else "(empty)"


def to_series(rows) -> Series:
    return Series([r[0] for r in rows], np.array([r[1] for r in rows], dtype=float),
                  np.array([r[2] for r in rows], dtype=float))


@dataclass
class Inputs:
    spy: Series
    irx: Series                # the copy the module reads
    gspc: Series
    irx_alt: Series | None = None    # trend_overlay's copy when both exist
    gspc_alt: Series | None = None
    irx_nonpos_raw: list | None = None   # raw-file dates of finite closes <= 0
    sources: dict = field(default_factory=dict)

    def cut(self, end: str) -> "Inputs":
        c = lambda s: s.cut(end) if s is not None else None  # noqa: E731
        return Inputs(c(self.spy), c(self.irx), c(self.gspc), c(self.irx_alt),
                      c(self.gspc_alt),
                      None if self.irx_nonpos_raw is None
                      else [d for d in self.irx_nonpos_raw if d <= end],
                      dict(self.sources))


def _pick_copy(name: str, reader) -> tuple[Series, Series | None, Path]:
    own, theirs = _cache_path(name), TREND_DIR / f"{name}.csv"
    if own.exists():
        alt = to_series(reader(theirs)) if theirs.exists() else None
        return to_series(reader(own)), alt, own
    if theirs.exists():
        return to_series(reader(theirs)), None, theirs
    raise Refused(EXIT_INPUT, f"GI: no {name} file (neither {own.relative_to(ROOT)} nor "
                              f"{theirs.relative_to(ROOT)} exists). Exit 3.", f"GI {name} missing")


def load_inputs(refresh: bool = False) -> Inputs:
    if refresh:
        for name in SYMBOLS:
            fetch_series(name)
    p = _cache_path("SPY")
    if not p.exists():
        raise Refused(EXIT_INPUT, f"GI: {p.relative_to(ROOT)} is missing; fetch it with "
                                  f"--refresh. Exit 3.", "GI SPY missing")
    spy = to_series(read_prices(p))
    if not spy.dates:
        raise Refused(EXIT_INPUT, f"GI: {p.relative_to(ROOT)} is empty. Exit 3.", "GI SPY empty")
    irx, irx_alt, irx_src = _pick_copy("IRX", read_yield)
    gspc, gspc_alt, gspc_src = _pick_copy("GSPC", read_prices)
    return Inputs(spy, irx, gspc, irx_alt, gspc_alt, raw_nonpositive_dates(irx_src),
                  {"SPY": p, "IRX": irx_src, "GSPC": gspc_src})


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
    dates: list[str]
    adj: np.ndarray            # SPY adjusted close
    close: np.ndarray          # SPY close (gate GB only)
    irx_c: np.ndarray          # ^IRX close, last close carried forward
    irx_carry: np.ndarray      # sessions since the last real ^IRX close
    tb: np.ndarray             # daily T-bill return on session k (from ^IRX close k-1)


def build_panel(inp: Inputs, end: str) -> Panel:
    spy = inp.spy.cut(end)
    dates = list(spy.dates)
    n = len(dates)
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
    return Panel(dates, spy.adj.copy(), spy.close.copy(), irx_c, carry, tb)


def first_decision(P: Panel, me: list[int]) -> int | None:
    """Index into `me` of the first month-end with MAX_N daily returns into it, so all
    12 cells are defined, found from the data."""
    for j, t in enumerate(me):
        if t >= MAX_N and np.isfinite(P.adj[t - MAX_N:t + 1]).all():
            return j
    return None


# ════════════════════════════════════════════════════════════════════════════
# The rule — one decision reads only the array it is handed, which ends at t
# ════════════════════════════════════════════════════════════════════════════

def parse_cell(cell: str) -> tuple[str, int, float]:
    s, n, t = cell.split("-")
    return s, int(n), int(t) / 100.0


def sigma_hat(adj_h: np.ndarray, n: int) -> float:
    """Annualised sample sd (ddof 1) of the last `n` daily log returns, ending with the
    return into the last close of `adj_h`."""
    t = len(adj_h) - 1
    if t < n:
        return float("nan")
    lr = np.diff(np.log(adj_h[t - n:t + 1]))
    return float(np.std(lr, ddof=1) * math.sqrt(TRADING_DAYS))


def weight_of(sig: float, scaling: str, target: float) -> float:
    """The capped weight. A sigma that is not finite and above 0 gives NaN (gate GW)."""
    if not (math.isfinite(sig) and sig > 0):
        return float("nan")
    x = target / sig
    if scaling == "VAR":
        x = x * x
    elif scaling != "VOL":
        raise ValueError(f"unknown scaling {scaling!r}")
    return min(CAP, x)


def target_weight(adj_h: np.ndarray, cell: str) -> tuple[float, float]:
    """(w, sigma) at the decision close t = len(adj_h) - 1."""
    s, n, tgt = parse_cell(cell)
    sig = sigma_hat(adj_h, n)
    return weight_of(sig, s, tgt), sig


@dataclass
class Decision:
    t: int                     # decision close
    w: float
    sigma: float


def decision_table(P: Panel, me: list[int], j0: int, cell: str) -> dict[int, Decision]:
    """{execution session t + 1: Decision} for every decision j >= j0 whose execution
    session exists. Each decision is handed the adjusted closes cut at its own close."""
    out = {}
    n = len(P.dates)
    for j in range(j0, len(me)):
        t = me[j]
        if t + 1 >= n:
            break
        w, sig = target_weight(P.adj[:t + 1], cell)
        out[t + 1] = Decision(t, w, sig)
    return out


def forced_table(exec_ks: list[int], w: float) -> dict[int, Decision]:
    """A cell forced to one weight at every execution session. No volatility logic: the
    GR replay runs it through `simulate`."""
    return {k: Decision(k - 1, float(w), float("nan")) for k in exec_ks}


# ════════════════════════════════════════════════════════════════════════════
# Simulation
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Exec:
    k: int
    date: str
    w: float                   # target weight in SPY
    turnover: float            # SPY notional traded / pre-cost equity (0 at the start)
    initial: bool


@dataclass
class Curve:
    label: str
    g: np.ndarray              # growth factor of session k over k-1; NaN at or before start
    start: int
    execs: list = field(default_factory=list)


def simulate(P: Panel, table: dict, label: str, cost_bp: float = COST_BP) -> Curve:
    """SPY sleeve plus T-bill cash. Starts at 1.0 at the first execution close at its
    target weight, no entry cost. Weights drift between executions. At an execution
    close the SPY notional traded is |w - drifted SPY weight| x equity, charged
    `cost_bp` per side; the T-bill side is not charged."""
    n = len(P.dates)
    ks = sorted(table)
    e0 = ks[0]
    g = np.full(n, np.nan)
    w = table[e0].w
    s, c = w, 1.0 - w
    E = 1.0
    execs = [Exec(e0, P.dates[e0], w, 0.0, True)]
    cost = cost_bp / 1e4
    gs, gc = _growth(P)
    out = [float("nan")] * n
    for k in range(e0 + 1, n):
        s *= gs[k]
        c *= gc[k]
        E_pre = s + c
        E_new = E_pre
        if k in table:
            w = table[k].w
            traded = abs(w - s / E_pre) * E_pre
            execs.append(Exec(k, P.dates[k], w, traded / E_pre, False))
            E_new = E_pre - cost * traded
            s, c = w * E_new, (1.0 - w) * E_new
        out[k] = E_new / E
        E = E_new
    g[:] = out
    return Curve(label, g, e0, execs)


def _growth(P: Panel) -> tuple[list, list]:
    """Per-session SPY and T-bill growth factors as Python floats (index k: k-1 -> k)."""
    gs = [float("nan")] + (P.adj[1:] / P.adj[:-1]).tolist()
    gc = (1.0 + P.tb).tolist()
    return gs, gc


def benchmark_mix(P: Panel, wbar: float, exec_ks: list[int], label: str = "MIX",
                  cost_bp: float = COST_BP) -> Curve:
    """A fixed weight `wbar` in SPY, the rest in T-bills, traded back to `wbar` at every
    execution close at the same per-side cost on the SPY leg. Written apart from
    `simulate` so that gate GR is a real replay check."""
    n = len(P.dates)
    e0 = exec_ks[0]
    rebal = set(exec_ks[1:])
    g = np.full(n, np.nan)
    spy_v, cash_v = wbar, 1.0 - wbar
    execs = [Exec(e0, P.dates[e0], wbar, 0.0, True)]
    prev = 1.0
    gs, gc = _growth(P)
    out = [float("nan")] * n
    for k in range(e0 + 1, n):
        spy_v, cash_v = spy_v * gs[k], cash_v * gc[k]
        eq = spy_v + cash_v
        if k in rebal:
            traded = abs(wbar * eq - spy_v)
            execs.append(Exec(k, P.dates[k], wbar, traded / eq, False))
            eq = eq - traded * cost_bp / 1e4
            spy_v, cash_v = wbar * eq, (1.0 - wbar) * eq
        out[k] = eq / prev
        prev = eq
    g[:] = out
    return Curve(label, g, e0, execs)


def benchmark_hold(P: Panel, e0: int, label: str = "SPY") -> Curve:
    """SPY bought once at the first execution close and held."""
    g = np.full(len(P.dates), np.nan)
    g[e0 + 1:] = P.adj[e0 + 1:] / P.adj[e0:-1]
    return Curve(label, g, e0, [Exec(e0, P.dates[e0], 1.0, 0.0, True)])


# ════════════════════════════════════════════════════════════════════════════
# Months and windows
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class MonthGrid:
    months: list[str]
    spans: list[tuple[int, int]]


def month_grid(P: Panel, e0: int) -> MonthGrid:
    """Complete months after the start close: a month is complete when its last session
    is a month-end (the next session falls in a later month)."""
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


def month_weights(curve: Curve, grid: MonthGrid) -> np.ndarray:
    """The target weight of the execution in each grid month (NaN if none)."""
    by = {}
    for e in curve.execs:
        by.setdefault(e.date[:7], e.w)
    return np.array([by.get(m, np.nan) for m in grid.months])


@dataclass
class Window:
    name: str
    months: list[str]
    lo: int
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


def cvar(r: np.ndarray, q: float = CVAR_Q) -> float:
    """Mean of the worst ceil(q x n) monthly returns."""
    if not len(r):
        return float("nan")
    k = max(1, math.ceil(q * len(r)))
    return float(np.sort(r)[:k].mean())


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
    wbar: float
    at_cap: float
    turnover: float
    worst_year: str
    cvar: float


def window_stats(curve: Curve, r: np.ndarray, tbm: np.ndarray, grid: MonthGrid,
                 w: Window) -> Stats:
    rw, tw = w.sl(r), w.sl(tbm)
    a, b = grid.spans[w.lo][0], grid.spans[w.hi - 1][1]
    eq = np.cumprod(curve.g[a:b + 1])
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    mdd_d = float((1.0 - eq / peak).max())
    months = set(w.months)
    ex = [e for e in curve.execs if e.date[:7] in months]
    turn = sum(e.turnover for e in ex if not e.initial) * 12.0 / w.n
    # a buy-and-hold curve has no execution inside a later window: it holds its start weight
    held = ex or [e for e in curve.execs if e.date[:7] < w.months[0]][-1:]
    ws = np.array([e.w for e in held]) if held else np.array([np.nan])
    years: dict[str, list[float]] = {}
    for m, x in zip(w.months, rw):
        years.setdefault(m[:4], []).append(x)
    yr = {y: float(np.prod(1.0 + np.array(v)) - 1.0) for y, v in years.items()}
    wy = min(yr, key=yr.get)
    wlab = f"{wy} {yr[wy]:+.1%}" + (" (partial)" if len(years[wy]) < 12 else "")
    return Stats(sharpe(rw - tw), mdd(rw), mdd_d, cagr(rw), float(np.mean(ws)),
                 float(np.mean(ws >= CAP)), turn, wlab, cvar(rw))


# ── episodes ─────────────────────────────────────────────────────────────────

@dataclass
class Episode:
    peak: int                  # month index in the window; -1 is the rebased base
    trough: int
    recovery: int | None
    depth: float


def episodes(r_spy: np.ndarray) -> list[Episode]:
    """SPY falls of EPISODE_DD or more from its running peak (monthly equity, rebased at
    the window start), peak to recovery (the first later month at or above the peak) or
    window end. A new episode starts only after a recovery."""
    eq = np.concatenate([[1.0], np.cumprod(1.0 + r_spy)])
    out: list[Episode] = []
    n = len(eq)
    peak_i, peak_v, trough_i, depth = 0, 1.0, None, 0.0
    for i in range(1, n):
        if eq[i] >= peak_v:
            if trough_i is not None and depth >= EPISODE_DD:
                out.append(Episode(peak_i - 1, trough_i - 1, i - 1, depth))
            peak_i, peak_v, trough_i, depth = i, eq[i], None, 0.0
        else:
            d = 1.0 - eq[i] / peak_v
            if d > depth:
                depth, trough_i = d, i
    if trough_i is not None and depth >= EPISODE_DD:
        out.append(Episode(peak_i - 1, trough_i - 1, None, depth))
    return out


def dd_inside(r: np.ndarray, e: Episode) -> float:
    """A curve's deepest drawdown over the episode's months (peak to recovery or end)."""
    eq = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    end = (e.recovery + 1) if e.recovery is not None else len(eq) - 1
    seg = eq[e.peak + 1:end + 1]
    return float((1.0 - seg / np.maximum.accumulate(seg)).max())


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


def _alpha_rows(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    """OLS intercept per row, times 12."""
    xm, ym = x.mean(axis=1, keepdims=True), y.mean(axis=1, keepdims=True)
    vx = ((x - xm) ** 2).sum(axis=1)
    b = np.where(vx > 0, ((x - xm) * (y - ym)).sum(axis=1) / np.where(vx > 0, vx, 1.0), np.nan)
    return (ym[:, 0] - b * xm[:, 0]) * 12.0


def rematched_mix(r_mix: np.ndarray, tbm: np.ndarray, wm: np.ndarray, wbar: float
                  ) -> np.ndarray:
    """Second-read rule: each draw's MIX excess return over the T-bill is scaled by
    wbar_b / wbar, where wbar_b is the mean of the weights its months carry, and the
    T-bill return is added back. Rows are draws."""
    scale = wm.mean(axis=1, keepdims=True) / wbar
    return tbm + (r_mix - tbm) * scale


@dataclass
class Boot:
    d_sharpe: np.ndarray
    d_mdd: np.ndarray
    alpha: np.ndarray


def boot_draws(idx: np.ndarray, r_cell: np.ndarray, r_mix: np.ndarray, r_spy: np.ndarray,
               tbm: np.ndarray, wm: np.ndarray, wbar: float) -> Boot:
    """Paired: a month's managed, MIX, SPY and T-bill returns and its weight travel
    together. MIX is re-matched in every draw."""
    rc, rm, rs, rt, ww = r_cell[idx], r_mix[idx], r_spy[idx], tbm[idx], wm[idx]
    rmb = rematched_mix(rm, rt, ww, wbar)
    d_s = _sharpe_rows(rc - rt) - _sharpe_rows(rmb - rt)
    d_m = _mdd_rows(rmb) - _mdd_rows(rc)
    al = _alpha_rows(rc - rt, rs - rt)
    return Boot(d_s, d_m, al)


def ci(draws: np.ndarray) -> tuple[float, float]:
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def p_value(draws: np.ndarray) -> float:
    """One-sided: the share of draws at or below 0. A draw that is not finite counts as
    at or below 0 (it is no evidence of a benefit)."""
    d = np.asarray(draws, dtype=float)
    return float(np.mean(~(d > 0)))


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

def holm(p_sharpe: float, p_mdd: float) -> tuple[bool, bool, str]:
    """Holm step-down over the family {dSharpe, dMDD} at one-sided 0.025. The smaller
    p-value is tested first (a tie tests dSharpe first) against 0.0125; the second is
    tested against 0.025 only if the first passed. Returns (sharpe passes, mdd passes,
    the statistic tested first)."""
    first = "dMDD" if p_mdd < p_sharpe else "dSharpe"
    pf, ps = (p_mdd, p_sharpe) if first == "dMDD" else (p_sharpe, p_mdd)
    f_ok = pf < HOLM_FIRST
    s_ok = f_ok and ps < HOLM_SECOND
    return ((s_ok, f_ok, first) if first == "dMDD" else (f_ok, s_ok, first))


@dataclass
class Graded:
    """What a headline word reads for one cell against its own MIX."""
    ds_disc: float
    dm_disc: float
    p_s: float
    p_m: float
    ds_hi: float               # holdout 97.5th percentile
    dm_hi: float


def headline_word(powered: bool, pbo: float, g: Graded | None, refused: str | None = None
                  ) -> tuple[str, list[str]]:
    """The registered table; the first matching row wins. Returns (word, notes)."""
    if refused is not None:
        return f"REFUSED ({refused})", []
    if pbo is None or not math.isfinite(pbo):
        return "REFUSED (PBO undefined)", []
    if not powered:
        return "UNDERPOWERED", []
    hs, hm, _ = holm(g.p_s, g.p_m)
    cs = hs and g.ds_disc > 0
    cm = hm and g.dm_disc > 0
    ws = g.ds_hi < 0
    wm = g.dm_hi < 0
    notes: list[str] = []
    if PBO_FRAGILE < pbo <= PBO_VETO:
        notes.append("selection fragile")
    if (cs or cm) and pbo > PBO_VETO:
        return "PBO-VETO", notes
    if cs and cm:
        return "BEATS-MIX", notes
    if cm:
        return "DRAWDOWN-ONLY", notes + (["Sharpe clearly worse"] if ws else [])
    if cs:
        return "SHARPE-ONLY", notes + (["drawdown clearly worse"] if wm else [])
    if ws or wm:
        return "CONTRARY", notes
    if (hs and g.ds_disc <= 0) or (hm and g.dm_disc <= 0):
        notes.append("holdout gain, discovery sign disagrees")
    return "NULL", notes


def arm_r_word(powered: bool, pbo: float, alpha_disc: float, alpha_lo: float,
               alpha_hi: float, refused: str | None = None) -> str:
    if refused is not None:
        return f"REFUSED ({refused})"
    if pbo is None or not math.isfinite(pbo):
        return "REFUSED (PBO undefined)"
    if not powered:
        return "UNDERPOWERED"
    counts = alpha_lo > 0 and alpha_disc > 0
    if counts and pbo > PBO_VETO:
        return "PBO-VETO"
    if counts:
        return "ALPHA"
    if alpha_hi < 0:
        return "NEGATIVE-ALPHA"
    return "NO-ALPHA"


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

def _rows_block(rows: list[str], limit: int = 20) -> None:
    for r in rows[:limit]:
        print(r)
    if len(rows) > limit:
        print(f"    ... and {len(rows) - limit} more")


def _agree(a: Series, b: Series, label: str, end: str) -> str:
    m = dict(zip(b.dates, b.close))
    diffs = [(d, abs(c - m[d])) for d, c in zip(a.dates, a.close)
             if d in m and d <= end and math.isfinite(c) and math.isfinite(m[d])]
    bad = [x for x in diffs if not x[1] <= GI_AGREE]
    if bad:
        _rows_block([f"    {label} {d}: copies differ by {x:.4f} points" for d, x in bad])
        raise Refused(EXIT_INPUT, f"GI: the two {label} copies differ by more than {GI_AGREE} "
                                  f"points on {len(bad)} dates (rows above). Exit 3.",
                      f"GI {label} copies")
    return (f"{label} copies agree on {len(diffs)} common dates, worst "
            f"{max((x[1] for x in diffs), default=0.0):.4f} points")


def gate_inputs(inp: Inputs, P: Panel, end: str = IN_SAMPLE_END) -> list[str]:
    """GI on the in-sample range SPY_START .. `end`."""
    s = inp.spy
    if not s.dates or s.dates[0] > SPY_START or s.dates[-1] < end:
        raise Refused(EXIT_INPUT, f"GI: the SPY cache must run from {SPY_START} to at least "
                                  f"{end}; it has {s.span()}. Exit 3.", "GI SPY coverage")
    i0 = bisect.bisect_left(s.dates, SPY_START)
    i1 = bisect.bisect_right(s.dates, end)
    bad = [f"    SPY {d}: close {c!r} adj_close {a!r}"
           for d, c, a in zip(s.dates[i0:i1], s.close[i0:i1], s.adj[i0:i1])
           if not (math.isfinite(c) and c > 0 and math.isfinite(a) and a > 0)]
    if bad:
        _rows_block(bad)
        raise Refused(EXIT_INPUT, f"GI: {len(bad)} SPY rows with an empty, zero or negative "
                                  f"close or adjusted close (rows above). Exit 3.", "GI SPY values")
    spy_d = set(s.dates[i0:i1])
    g = inp.gspc
    g_d = {d for d, c in zip(g.dates, g.close)
           if SPY_START <= d <= end and math.isfinite(c) and c > 0}
    miss = ([f"    {d}: ^GSPC session with no SPY close" for d in sorted(g_d - spy_d)]
            + [f"    {d}: SPY session with no ^GSPC close" for d in sorted(spy_d - g_d)])
    if miss:
        _rows_block(miss)
        raise Refused(EXIT_INPUT, f"GI: {len(miss)} sessions differ between the SPY and ^GSPC "
                                  f"calendars (rows above). Exit 3.", "GI calendar")
    worst = int(P.irx_carry[1:].max()) if len(P.dates) > 1 else 0
    if worst > GI_IRX_CARRY:
        k = int(np.argmax(P.irx_carry[1:])) + 1
        raise Refused(EXIT_INPUT, f"GI: ^IRX carried {worst} sessions to {P.dates[k]} "
                                  f"(limit {GI_IRX_CARRY}). Exit 3.", "GI IRX carry")
    held = [d for d, c in zip(inp.irx.dates, inp.irx.close) if SPY_START <= d <= end and c <= 0]
    nonpos_note = "no raw file count (synthetic inputs)"
    if inp.irx_nonpos_raw is not None:
        raw = [d for d in inp.irx_nonpos_raw if SPY_START <= d <= end]
        if raw != held:
            raise Refused(EXIT_INPUT, f"GI: the ^IRX file holds {len(raw)} finite closes at or "
                                      f"below 0 in range, the module uses {len(held)}. Exit 3.",
                          "GI IRX nonpositive")
        nonpos_note = f"{len(held)} of {len(raw)} in the file used as printed"
    n_tb = int(np.sum(P.tb[1:] <= 0))
    agree = []
    if inp.irx_alt is not None:
        agree.append(_agree(inp.irx, inp.irx_alt, "^IRX", end))
    if inp.gspc_alt is not None:
        agree.append(_agree(inp.gspc, inp.gspc_alt, "^GSPC", end))
    return [f"  GI inputs: SPY {s.dates[0]} .. {s.dates[-1]} covers {SPY_START} .. {end}; "
            f"{len(spy_d)} sessions, no empty, zero or negative close; SPY and ^GSPC calendars "
            f"identical in range",
            f"  GI ^IRX: worst carry {worst} sessions (limit {GI_IRX_CARRY}); closes at or below "
            f"0: {nonpos_note}; sessions with a T-bill return at or below 0: {n_tb}",
            f"  GI copies: {'; '.join(agree) if agree else 'one copy of each file only'}   PASS"]


def gate_basis(inp: Inputs, end: str = IN_SAMPLE_END) -> list[str]:
    """GB on SPY_START .. `end`: adj/close never falls by more than 0.01% and never jumps
    by more than 2% between sessions; no daily adjusted return beyond +-25%."""
    s = inp.spy
    i0 = bisect.bisect_left(s.dates, SPY_START)
    i1 = bisect.bisect_right(s.dates, end)
    d = s.dates[i0:i1]
    ratio = s.adj[i0:i1] / s.close[i0:i1]
    step = ratio[1:] / ratio[:-1] - 1.0
    ret = s.adj[i0 + 1:i1] / s.adj[i0:i1 - 1] - 1.0
    bad = [f"    SPY {d[k]} -> {d[k + 1]}: adj/close step {step[k]:+.6f}"
           for k in np.where(~((step >= -GB_RATIO_FALL) & (step <= GB_RATIO_STEP)))[0]]
    bad += [f"    SPY {d[k]} -> {d[k + 1]}: adjusted return {ret[k]:+.4f}"
            for k in np.where(~(np.abs(ret) <= GB_RET))[0]]
    if bad:
        _rows_block(bad, 40)
        raise Refused(EXIT_INPUT, f"GB: {len(bad)} basis breaks (rows above). Exit 3.", "GB basis")
    return [f"  GB basis: SPY adj/close worst fall {np.min(step):+.6f} (bound "
            f"-{GB_RATIO_FALL:.4f}), worst jump {np.max(step):+.6f} (bound +{GB_RATIO_STEP:.2f}), "
            f"worst |daily adjusted return| {np.max(np.abs(ret)):.4f} (bound {GB_RET:.2f})   PASS"]


def gate_weights(tables: dict) -> list[str]:
    """GW: every target weight in [0, 1.0]; every sigma finite and above 0."""
    bad = []
    for cell, tab in tables.items():
        for k, dcs in tab.items():
            if not (math.isfinite(dcs.sigma) and dcs.sigma > 0
                    and math.isfinite(dcs.w) and 0.0 <= dcs.w <= CAP):
                bad.append(f"    {cell} decision {dcs.t}: sigma {dcs.sigma!r} w {dcs.w!r}")
    if bad:
        _rows_block(bad)
        raise Refused(EXIT_INPUT, f"GW: {len(bad)} decisions with a weight outside [0, 1] or a "
                                  f"sigma that is not finite and above 0. Exit 3.", "GW weights")
    n = sum(len(t) for t in tables.values())
    return [f"  GW weights: {n} decisions over {len(tables)} cells, every weight in [0, 1.0], "
            f"every sigma finite and above 0   PASS"]


def gate_lookahead(inp: Inputs, P: Panel, me: list[int], j0: int, tables: dict) -> list[str]:
    """GX at run time. Structural: every execution session is its decision close + 1, so
    the weight behind session k's return was decided at or before k - 2. Recomputed: 24
    evenly spaced decisions on series cut at that decision close must match exactly."""
    for cell, tab in tables.items():
        for k, dcs in tab.items():
            if dcs.t != k - 1 or dcs.t not in me:
                raise Refused(1, f"GX: {cell} executes at {k} on a decision at {dcs.t}. Exit 1.",
                              "GX lag")
    js_all = [j for j in range(j0, len(me)) if me[j] + 1 < len(P.dates)]
    js = sorted({js_all[i] for i in np.linspace(0, len(js_all) - 1, GX_SAMPLES).astype(int)})
    moved = 0
    for j in js:
        t = me[j]
        Pc = build_panel(inp.cut(P.dates[t]), P.dates[t])
        if Pc.dates != P.dates[:t + 1] or t in month_end_idx(Pc.dates):
            raise Refused(1, "GX: a cut series is not a prefix of the calendar, or its last "
                             "row became a decision close. Exit 1.", "GX calendar")
        for cell in CELLS:
            w, sig = target_weight(Pc.adj, cell)
            d0 = tables[cell][t + 1]
            if not (w == d0.w and sig == d0.sigma):
                moved += 1
    if moved:
        raise Refused(1, f"GX: {moved} decisions moved when the series were cut at the "
                         f"decision close. Exit 1.", "GX lookahead")
    return [f"  GX no lookahead: every execution is its decision close + 1 session; "
            f"{len(js)} decisions x {len(CELLS)} cells recomputed on series cut at the decision "
            f"close, 0 moved   PASS"]


def gate_replay(r_forced_one: np.ndarray, r_spy: np.ndarray, r_forced_w: np.ndarray,
                r_mix: np.ndarray, wbar: float) -> list[str]:
    """GR. A cell forced to 1.0 reproduces SPY's monthly returns; a cell forced to `wbar`
    reproduces MIX's. Largest monthly difference at most 1e-12."""
    d1 = float(np.max(np.abs(r_forced_one - r_spy))) if len(r_spy) else 0.0
    d2 = float(np.max(np.abs(r_forced_w - r_mix))) if len(r_mix) else 0.0
    if not (d1 <= GR_TOL and d2 <= GR_TOL):
        raise Refused(EXIT_INPUT, f"GR: forced 1.0 vs SPY worst {d1:.3e}, forced {wbar:.4f} vs "
                                  f"MIX worst {d2:.3e} (tolerance {GR_TOL:.0e}). Exit 3.",
                      "GR replay")
    return [f"  GR replay: forced 1.0 vs SPY over {len(r_spy)} months, worst |diff| {d1:.1e}; "
            f"forced {wbar:.4f} vs MIX at that weight, worst |diff| {d2:.1e}   PASS"]


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
# ════════════════════════════════════════════════════════════════════════════

def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


STATS_HEAD = (f"  {'curve':<11}{'Sharpe':>7}{'MDD':>7}{'dlyMDD':>7}{'CAGR':>7}{'dCAGR':>7}"
              f"{'dCAGR':>7}{'wbar':>6}{'@cap':>5}{'turn':>6}{'CVaR':>7}  worst year")
STATS_SUB = f"  {'':<11}{'':>7}{'':>7}{'':>7}{'':>7}{'vsMIX':>7}{'vsSPY':>7}"


def stats_row(label: str, s: Stats, mix_cagr: float, spy_cagr: float) -> str:
    return (f"  {label:<11}{s.sharpe:>7.3f}{s.mdd:>7.1%}{s.mdd_daily:>7.1%}{s.cagr:>7.2%}"
            f"{(s.cagr - mix_cagr) * 100:>+7.2f}{(s.cagr - spy_cagr) * 100:>+7.2f}"
            f"{s.wbar:>6.3f}{s.at_cap:>5.0%}{s.turnover:>6.2f}{s.cvar:>+7.2%}  {s.worst_year}")


def fmt_ci(x: tuple) -> str:
    return f"{x[0]:+.3f} [{x[1]:+.3f}, {x[2]:+.3f}]"


# ════════════════════════════════════════════════════════════════════════════
# One window, one cost
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class CellOut:
    wbar: float
    at_cap: float
    d_sharpe: tuple            # (point, lo, hi)
    d_mdd: tuple
    p_s: float
    p_m: float
    alpha: tuple               # (point, lo, hi) a year
    alpha_nw_se: float
    beta: float
    d_cagr: float              # vs MIX, points a year
    d_cagr_spy: float


@dataclass
class WindowOut:
    name: str
    first: str
    last: str
    n: int
    n_episodes: int
    powered: bool
    cells: dict                # cell -> CellOut


@dataclass
class Run:
    """Everything one cost level needs: the panel, the managed curves, the grid."""
    P: Panel
    grid: MonthGrid
    tbm: np.ndarray
    exec_ks: list
    curves: dict               # cell -> Curve
    mret: dict                 # cell -> monthly returns
    wm: dict                   # cell -> month weights
    spy: Curve
    r_spy: np.ndarray
    cost_bp: float
    _mix: dict = field(default_factory=dict)

    def mix(self, wbar: float) -> np.ndarray:
        if wbar not in self._mix:
            cv = benchmark_mix(self.P, wbar, self.exec_ks, "MIX", self.cost_bp)
            self._mix[wbar] = (cv, monthly(cv.g, self.grid))
        return self._mix[wbar][1]

    def mix_curve(self, wbar: float) -> Curve:
        self.mix(wbar)
        return self._mix[wbar][0]


def make_run(P: Panel, tables: dict, cost_bp: float, cells=CELLS) -> Run:
    curves = {c: simulate(P, tables[c], c, cost_bp) for c in cells}
    exec_ks = sorted(tables[HEADLINE])
    grid = month_grid(P, exec_ks[0])
    tbm = monthly_tbill(P, grid)
    spy = benchmark_hold(P, exec_ks[0])
    return Run(P, grid, tbm, exec_ks, curves,
               {c: monthly(cv.g, grid) for c, cv in curves.items()},
               {c: month_weights(cv, grid) for c, cv in curves.items()},
               spy, monthly(spy.g, grid), cost_bp)


def window_wbar(R: Run, w: Window, cell: str) -> float:
    return float(np.mean(w.sl(R.wm[cell])))


def cell_out(R: Run, w: Window, cell: str, idx: np.ndarray) -> CellOut:
    wbar = window_wbar(R, w, cell)
    rc, rm, rs, tw, wm = (w.sl(R.mret[cell]), w.sl(R.mix(wbar)), w.sl(R.r_spy), w.sl(R.tbm),
                          w.sl(R.wm[cell]))
    b = boot_draws(idx, rc, rm, rs, tw, wm, wbar)
    ps = sharpe(rc - tw) - sharpe(rm - tw)
    pm = mdd(rm) - mdd(rc)
    a, a_se, be, _ = nw_ols(rc - tw, rs - tw)
    return CellOut(wbar, float(np.mean(wm >= CAP)), (ps, *ci(b.d_sharpe)), (pm, *ci(b.d_mdd)),
                   p_value(b.d_sharpe), p_value(b.d_mdd), (a * 12.0, *ci(b.alpha)),
                   a_se * 12.0, be, (cagr(rc) - cagr(rm)) * 100, (cagr(rc) - cagr(rs)) * 100)


def mix_vol_weight(R: Run, w: Window, cell: str) -> float:
    """A fixed weight whose daily volatility over the window equals the managed rule's
    (fixed-point on the simulated MIX curve, four steps; printed only)."""
    a, b = R.grid.spans[w.lo][0], R.grid.spans[w.hi - 1][1]
    target = float(np.std(R.curves[cell].g[a:b + 1] - 1.0, ddof=1))
    wv = min(CAP, target / float(np.std(R.spy.g[a:b + 1] - 1.0, ddof=1)))
    for _ in range(4):
        cv = R.mix_curve(wv)
        sd = float(np.std(cv.g[a:b + 1] - 1.0, ddof=1))
        if not sd > 0:
            break
        wv = min(CAP, wv * target / sd)
    return wv


def window_block(R: Run, w: Window, boot_n: int, cells=CELLS, verbose: bool = True,
                 episodes_print: bool = True) -> WindowOut:
    grid = R.grid
    idx = boot_index(w.n, BLOCK, boot_n)
    outs = {c: cell_out(R, w, c, idx) for c in cells}
    eps = episodes(w.sl(R.r_spy))
    powered = w.n >= MIN_MONTHS and len(eps) >= MIN_EPISODES
    if not verbose:
        return WindowOut(w.name, w.months[0], w.months[-1], w.n, len(eps), powered, outs)
    print(f"  months {w.months[0]} .. {w.months[-1]} (N = {w.n}); equity rebased to 1.0 at the "
          f"window start; Sharpe on monthly excess returns over T-bills; MIX at each cell's own "
          f"wbar in this window")
    hw = outs[HEADLINE].wbar
    st = {c: window_stats(R.curves[c], R.mret[c], R.tbm, grid, w) for c in cells}
    mix_cv = R.mix_curve(hw)
    st["MIX"] = window_stats(mix_cv, R.mix(hw), R.tbm, grid, w)
    st["SPY"] = window_stats(R.spy, R.r_spy, R.tbm, grid, w)
    wv = mix_vol_weight(R, w, HEADLINE)
    st["MIX-VOL"] = window_stats(R.mix_curve(wv), R.mix(wv), R.tbm, grid, w)
    print("\n  Sharpe, monthly MDD, daily MDD, CAGR, dCAGR vs the cell's own MIX and vs SPY "
          "(points a year),\n  mean target weight, share of executions at the cap, turnover a "
          "year, monthly CVaR (worst 5%), worst calendar year")
    print(STATS_HEAD)
    print(STATS_SUB)
    for c in cells:
        mc = cagr(w.sl(R.mix(outs[c].wbar)))
        print(stats_row(c, st[c], mc, st["SPY"].cagr))
    for c in ("MIX", "SPY", "MIX-VOL"):
        print(stats_row(c, st[c], st["MIX"].cagr, st["SPY"].cagr))
    print(f"  MIX above is the headline's: wbar {hw:.4f}. MIX-VOL weight {wv:.4f} (daily "
          f"volatility matched to {HEADLINE}; printed only).")

    print(f"\n  SPY drawdown episodes ({EPISODE_DD:.0%}+ from its running peak, monthly equity), "
          f"{HEADLINE} and MIX beside each:")
    print(f"  {'peak':<10}{'trough':<10}{'recovery':<10}{'SPY depth':>10}{'cell DD':>9}"
          f"{'MIX DD':>8}")
    r_cell, r_mix = w.sl(R.mret[HEADLINE]), w.sl(R.mix(hw))
    wm = w.sl(R.wm[HEADLINE])
    for e in eps:
        pk = w.months[e.peak] if e.peak >= 0 else "(base)"
        rc = w.months[e.recovery] if e.recovery is not None else "(open)"
        print(f"  {pk:<10}{w.months[e.trough]:<10}{rc:<10}{e.depth:>10.1%}"
              f"{dd_inside(r_cell, e):>9.1%}{dd_inside(r_mix, e):>8.1%}")
        if episodes_print:
            end = (e.recovery + 1) if e.recovery is not None else w.n
            ws = " ".join(f"{w.months[i][2:]}:{wm[i]:.2f}" for i in range(e.peak + 1, end))
            print(f"    {HEADLINE} weight at each execution inside: {ws}")
    print(f"  episodes with a trough inside the window: {len(eps)} (floor {MIN_EPISODES})")
    print(f"  GN floors: {w.n} months (floor {MIN_MONTHS}), {len(eps)} episodes (floor "
          f"{MIN_EPISODES}) -> {'powered' if powered else 'UNDERPOWERED'}")

    print(f"\n  Paired moving block bootstrap on monthly returns: block {BLOCK}, {boot_n} draws, "
          f"seed {SEED}; MIX re-matched\n  in every draw (excess scaled by wbar_b / wbar). The rule "
          f"is not re-run on a resampled path; the dMDD\n  interval measures the noise in one "
          f"drawdown figure. p = share of draws at or below 0.")
    print(f"  {'cell':<11}{'dSharpe':>8}{'CI95':>18}{'p':>7}{'dMDD':>8}{'CI95':>18}{'p':>7}"
          f"{'alpha':>8}{'CI95':>18}{'beta':>6}{'dCAGR':>7}")
    for c in cells:
        o = outs[c]
        tag = "" if c == HEADLINE else "  (grid, not graded)"
        print(f"  {c:<11}{o.d_sharpe[0]:>+8.3f}  [{o.d_sharpe[1]:+.3f}, {o.d_sharpe[2]:+.3f}]"
              f"{o.p_s:>7.4f}{o.d_mdd[0]:>+8.3f}  [{o.d_mdd[1]:+.3f}, {o.d_mdd[2]:+.3f}]"
              f"{o.p_m:>7.4f}{o.alpha[0]:>+8.3f}  [{o.alpha[1]:+.3f}, {o.alpha[2]:+.3f}]"
              f"{o.beta:>6.2f}{o.d_cagr:>+7.2f}{tag}")
    o = outs[HEADLINE]
    print(f"  {HEADLINE} ARM R: alpha {o.alpha[0]:+.4f} a year (Newey-West se {o.alpha_nw_se:.4f}, "
          f"{NW_LAGS} lags), beta {o.beta:.3f}")
    for b in ("SPY", "MIX-VOL"):
        print(f"  {HEADLINE} vs {b} (printed, no word): dSharpe "
              f"{st[HEADLINE].sharpe - st[b].sharpe:+.3f}  dMDD {st[b].mdd - st[HEADLINE].mdd:+.3f}"
              f"  dCAGR {(st[HEADLINE].cagr - st[b].cagr) * 100:+.2f} points")
    return WindowOut(w.name, w.months[0], w.months[-1], w.n, len(eps), powered, outs)


def graded(disc: WindowOut, hold: WindowOut, cell: str) -> Graded:
    d, h = disc.cells[cell], hold.cells[cell]
    return Graded(d.d_sharpe[0], d.d_mdd[0], h.p_s, h.p_m, h.d_sharpe[2], h.d_mdd[2])


def _notes(nt: list[str]) -> str:
    return f" ({'; '.join(nt)})" if nt else ""


# ════════════════════════════════════════════════════════════════════════════
# In-sample run
# ════════════════════════════════════════════════════════════════════════════

def pbo_of(R: Run, ins: Window):
    M = np.column_stack([ins.sl(R.mret[c]) - ins.sl(R.tbm) for c in CELLS])
    return run_pbo(M, ins.months), M.shape[0]


def run_in_sample(inp_full: Inputs, boot_n: int = BOOT_N) -> dict:
    """Everything graded. Cuts every series at IN_SAMPLE_END before computing anything."""
    inp = inp_full.cut(IN_SAMPLE_END)
    P = build_panel(inp, IN_SAMPLE_END)
    me = month_end_idx(P.dates)
    j0 = first_decision(P, me)
    if j0 is None:
        raise Refused(EXIT_INPUT, f"GI: no month-end with {MAX_N} daily returns before it. "
                                  f"Exit 3.", "GI first decision")
    t0 = me[j0]
    print(f"  first decision {P.dates[t0]} (first month-end with {MAX_N} daily returns into it); "
          f"first execution close {P.dates[t0 + 1]}")
    g0 = month_grid(P, t0 + 1)
    wins = [make_window(g0, "discovery", None, DISCOVERY_END), make_window(g0, "h", *HOLDOUT),
            make_window(g0, "p", *POSTPUB)]
    if any(w.n == 0 for w in wins):
        raise Refused(EXIT_INPUT, "GI: a window holds no complete month. Exit 3.", "GI windows")
    print("  windows (actual): " + ", ".join(
        f"{lab} {w.months[0]} .. {w.months[-1]} ({w.n} months)"
        for lab, w in zip(("discovery", "holdout", "post-publication"), wins))
        + "; the first month starts at the first execution close")
    section("GATES")
    for line in gate_inputs(inp, P):
        print(line)
    for line in gate_basis(inp):
        print(line)
    tables = {c: decision_table(P, me, j0, c) for c in CELLS}
    for line in gate_weights(tables):
        print(line)
    for line in gate_lookahead(inp, P, me, j0, tables):
        print(line)
    print("  GX calendar: the last row of a cut series is never a decision close "
          "(month_end_idx; pinned in tests)   PASS")
    print(f"  GC the cut: every series is cut at {IN_SAMPLE_END} before any computation "
          f"(pinned in tests)")

    R = make_run(P, tables, COST_BP)
    grid = R.grid
    disc = make_window(grid, "discovery", None, DISCOVERY_END)
    hold = make_window(grid, "holdout", *HOLDOUT)
    post = make_window(grid, "post-publication", *POSTPUB)
    ins = make_window(grid, "in-sample", None, HOLDOUT[1])
    h_wbar = window_wbar(R, hold, HEADLINE)
    f1 = simulate(P, forced_table(R.exec_ks, 1.0), "forced-1", COST_BP)
    fw = simulate(P, forced_table(R.exec_ks, h_wbar), "forced-wbar", COST_BP)
    for line in gate_replay(monthly(f1.g, grid), R.r_spy, monthly(fw.g, grid), R.mix(h_wbar),
                            h_wbar):
        print(line)
    gaps = [m for c in CELLS for m, x in zip(grid.months, R.wm[c]) if not math.isfinite(x)]
    if gaps:
        raise Refused(EXIT_INPUT, f"GW: {len(gaps)} graded months carry no execution weight "
                                  f"(first {gaps[0]}). Exit 3.", "GW month weights")

    section(f"DISCOVERY {disc.months[0]} to {disc.months[-1]} (sign check)")
    rd = window_block(R, disc, boot_n)
    section(f"HOLDOUT {hold.months[0]} to {hold.months[-1]} (decides the verdict)")
    rh = window_block(R, hold, boot_n)
    section(f"POST-PUBLICATION {post.months[0]} to {post.months[-1]} (inside the holdout, printed "
            f"only, no word)")
    rp = window_block(R, post, boot_n, episodes_print=False)

    section("PBO / CSCV (12 cells, S=16, monthly excess returns over T-bills, in-sample)")
    (res, dropped), nrows = pbo_of(R, ins)
    print(f"  in-sample rows {nrows} ({ins.months[0]} .. {ins.months[-1]}) -> {res.n_rows} after "
          f"trimming {len(dropped)} oldest months ({', '.join(dropped) if dropped else 'none'}); "
          f"{res.n_combinations} splits")
    print(f"  PBO {res.pbo:.3f}  n_at_zero {res.n_at_zero}  {pbo_note(res.pbo)}")
    best = np.bincount(res.n_star, minlength=len(CELLS))
    print("  in-sample best cell, share of splits: "
          + "  ".join(f"{c} {best[i] / res.n_combinations:.0%}" for i, c in enumerate(CELLS)
                      if best[i]))
    print("  With 12 cells, pure noise gives a PBO near 0.50. PBO ranks cells by Sharpe and "
          "never selects a cell.")
    if not math.isfinite(res.pbo):
        raise Refused(EXIT_INPUT, "PBO undefined: the in-sample PBO is not finite. Exit 3.",
                      "PBO undefined")

    powered = rd.powered and rh.powered
    g = graded(rd, rh, HEADLINE)
    hs, hm, first = holm(g.p_s, g.p_m)
    hw, notes = headline_word(powered, res.pbo, g)
    o, od = rh.cells[HEADLINE], rd.cells[HEADLINE]
    aw = arm_r_word(powered, res.pbo, od.alpha[0], o.alpha[1], o.alpha[2])

    section("HOLM (the headline family of two, holdout)")
    print(f"  tested first: {first} (smaller p; a tie tests dSharpe first), threshold "
          f"{HOLM_FIRST}; second threshold {HOLM_SECOND}, tested only if the first passed")
    print(f"  dSharpe p {g.p_s:.4f} -> Holm {'pass' if hs else 'fail'}; discovery point "
          f"{g.ds_disc:+.3f} -> {'counts' if hs and g.ds_disc > 0 else 'does not count'}")
    print(f"  dMDD    p {g.p_m:.4f} -> Holm {'pass' if hm else 'fail'}; discovery point "
          f"{g.dm_disc:+.3f} -> {'counts' if hm and g.dm_disc > 0 else 'does not count'}")
    print(f"  clearly worse (holdout 97.5th percentile below 0): dSharpe "
          f"{'yes' if g.ds_hi < 0 else 'no'} ({g.ds_hi:+.3f}), dMDD "
          f"{'yes' if g.dm_hi < 0 else 'no'} ({g.dm_hi:+.3f})")

    section("WORDS BY THE SAME ROWS (printed only)")
    print("  Grid cells, each against its own MIX (grid, not graded):")
    for c in CELLS:
        if c == HEADLINE:
            continue
        wd, nt = headline_word(powered, res.pbo, graded(rd, rh, c))
        print(f"    {c:<10} {wd}{_notes(nt)}  (grid, not graded)")
    print(f"  Sensitivities for {HEADLINE} (printed only):")
    for blk in BLOCK_SENS:
        sd = window_block_light(R, disc, blk, boot_n)
        sh = window_block_light(R, hold, blk, boot_n)
        wd, nt = headline_word(powered, res.pbo, Graded(sd.d_sharpe[0], sd.d_mdd[0], sh.p_s,
                                                        sh.p_m, sh.d_sharpe[2], sh.d_mdd[2]))
        print(f"    block {blk:>2}: holdout dSharpe {fmt_ci(sh.d_sharpe)} p {sh.p_s:.4f} dMDD "
              f"{fmt_ci(sh.d_mdd)} p {sh.p_m:.4f} (5 bp PBO) -> {wd}{_notes(nt)}  (printed only)")
    for cbp in COST_SENS:
        Rc = make_run(P, tables, cbp)
        (rc_, _), _ = pbo_of(Rc, ins)
        sd = window_block_light(Rc, disc, BLOCK, boot_n)
        sh = window_block_light(Rc, hold, BLOCK, boot_n)
        wd, nt = headline_word(powered, float(rc_.pbo),
                               Graded(sd.d_sharpe[0], sd.d_mdd[0], sh.p_s, sh.p_m,
                                      sh.d_sharpe[2], sh.d_mdd[2]))
        print(f"    cost {cbp:>4.0f} bp (every cell and MIX): holdout dSharpe {fmt_ci(sh.d_sharpe)} "
              f"p {sh.p_s:.4f} dMDD {fmt_ci(sh.d_mdd)} p {sh.p_m:.4f} PBO {rc_.pbo:.3f} -> "
              f"{wd}{_notes(nt)}  (printed only)")
    return dict(disc=rd, hold=rh, post=rp, pbo=res, word=hw, notes=notes, arm_r=aw,
                first_decision=P.dates[t0])


def window_block_light(R: Run, w: Window, block: int, boot_n: int) -> CellOut:
    return cell_out(R, w, HEADLINE, boot_index(w.n, block, boot_n))


# ════════════════════════════════════════════════════════════════════════════
# Forward
# ════════════════════════════════════════════════════════════════════════════

def report_forward(inp: Inputs, boot_n: int = BOOT_N, today: str | None = None) -> str:
    section(f"FORWARD — {HEADLINE} vs MIX, {FORWARD[0]} to {FORWARD[1]} (one shot, "
            f"{FORWARD_MIN_MONTHS}-month floor, sunset {SUNSET})")
    today = today or date.today().isoformat()
    P = build_panel(inp, inp.spy.dates[-1])
    me = month_end_idx(P.dates)
    fwd_months = sorted({P.dates[k][:7] for k in me if FORWARD[0] <= P.dates[k][:7] <= FORWARD[1]})
    n = len(fwd_months)
    print(f"  data to {P.dates[-1]}; complete forward months: {n}")
    if n < FORWARD_MIN_MONTHS:
        if today > SUNSET:
            print(f"  the sunset {SUNSET} has passed with no read; nothing is concluded")
            return "LAPSED"
        word = f"STILL-OPEN ({n} forward months of {FORWARD_MIN_MONTHS})"
        print(f"  {word}. The read fires once, on the first run after {FORWARD[1]} is complete.")
        return word
    j0 = first_decision(P, me)
    tab = decision_table(P, me, j0, HEADLINE)
    ks = sorted(tab)
    if not (np.isfinite(P.adj[ks[0]:]).all() and np.isfinite(P.tb[ks[0] + 1:]).all()
            and int(P.irx_carry[ks[0]:].max()) <= GI_IRX_CARRY
            and all(math.isfinite(d.sigma) and d.sigma > 0 for d in tab.values())):
        print("  a close is missing, ^IRX is stale or a sigma is undefined past the cut; the "
              "forward line cannot be computed")
        return "REFUSED (forward data gap)"
    R = make_run(P, {HEADLINE: tab}, COST_BP, cells=(HEADLINE,))
    w = make_window(R.grid, "forward", *FORWARD)
    o = cell_out(R, w, HEADLINE, boot_index(w.n, FORWARD_BLOCK, boot_n))
    word = forward_word(o.d_sharpe[0], o.d_mdd[0])
    calm = not episodes(w.sl(R.r_spy))
    print(f"  forward months {w.months[0]} .. {w.months[-1]} (N = {w.n}), wbar {o.wbar:.4f}: "
          f"dSharpe {fmt_ci(o.d_sharpe)}  dMDD {fmt_ci(o.d_mdd)} (block-6 CIs) -> {word}")
    if calm:
        word += " (no forward episode)"
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
    if refused is not None:
        print(f">>> {NAME} HEADLINE ({HEADLINE} vs MIX, holdout {HOLDOUT[0]} to {HOLDOUT[1]}, "
              f"5 bp): REFUSED ({refused}) <<<")
        return
    rd, rh, rp = out["disc"], out["hold"], out["post"]
    print(f">>> {NAME} HEADLINE ({HEADLINE} vs MIX, holdout {rh.first} to {rh.last}, 5 bp): "
          f"{out['word']}{_notes(out['notes'])} <<<")

    def tail(o: CellOut) -> str:
        return f"wbar {o.wbar:.3f} at-cap {o.at_cap:.0%} dCAGR {o.d_cagr:+.2f} points"

    d = rd.cells[HEADLINE]
    print(f">>> {NAME} DISCOVERY ({rd.first} to {rd.last}): dSharpe {fmt_ci(d.d_sharpe)} dMDD "
          f"{fmt_ci(d.d_mdd)} {tail(d)} <<<")
    h = rh.cells[HEADLINE]
    print(f">>> {NAME} HOLDOUT ({rh.first} to {rh.last}): dSharpe {fmt_ci(h.d_sharpe)} p "
          f"{h.p_s:.4f} dMDD {fmt_ci(h.d_mdd)} p {h.p_m:.4f} {tail(h)} <<<")
    print(f">>> {NAME} ARM R (alpha on SPY, holdout): {out['arm_r']} alpha {fmt_ci(h.alpha)} "
          f"beta {h.beta:.2f} <<<")
    p = out["pbo"].pbo
    pn = pbo_note(p)
    print(f">>> {NAME} PBO (12 cells, S=16, in-sample): {p:.3f}"
          f"{' (' + pn + ')' if pn == 'selection fragile' else ''} <<<")
    q = rp.cells[HEADLINE]
    print(f">>> {NAME} POST-PUBLICATION ({rp.first} to {rp.last}, printed only): dSharpe "
          f"{fmt_ci(q.d_sharpe)} dMDD {fmt_ci(q.d_mdd)} alpha {fmt_ci(q.alpha)} <<<")
    print(f">>> {NAME} FORWARD ({HEADLINE} vs MIX from {FORWARD[0]}, {FORWARD_MIN_MONTHS}-month "
          f"floor, sunset {SUNSET}): {fwd} <<<")
    print("  A headline statistic counts when it passes its Holm test on the holdout and its "
          "discovery point estimate is above 0.")
    print(f"  Nothing ships from this study ({Path(REGISTRATION).name}).")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=NAME)
    ap.add_argument("--refresh", action="store_true", help="refetch SPY, ^IRX and ^GSPC")
    ap.add_argument("--boot-n", type=int, default=BOOT_N, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    print(f"{NAME} — does cutting SPY exposure when volatility is high beat a constant SPY and "
          f"T-bill mix?")
    print(f"  registration {REGISTRATION}")
    sha = _git("rev-parse", "--short", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    print(f"  git {sha or '?'} ({'dirty' if dirty else 'clean'} working tree)")
    print("  era: current (inputs are unversioned market closes)")
    print(f"  windows: discovery from the first month after the first decision to {DISCOVERY_END}, "
          f"holdout {HOLDOUT[0]} to {HOLDOUT[1]}, post-publication {POSTPUB[0]} to {POSTPUB[1]} "
          f"(inside the holdout), gap 2026-09 to 2026-11 (in no window), forward {FORWARD[0]} to "
          f"{FORWARD[1]}; in-sample cut {IN_SAMPLE_END}")
    print(f"  seal: starts {era_mod.SEAL_START}; binds play signal dates; this study reads no "
          f"play, flow signal or backtest row")
    print(f"  money: {COST_BP:.0f} bp per side on the SPY notional traded, T-bills not charged; "
          f"bootstrap block {BLOCK}, {args.boot_n} draws, seed {SEED}")
    try:
        check_era()
        inp = load_inputs(args.refresh)
        print(f"  input {inp.sources['SPY'].relative_to(ROOT)} (SPY): {len(inp.spy.dates)} rows, "
              f"{inp.spy.span()}")
        print(f"  input {inp.sources['IRX'].relative_to(ROOT)} (^IRX, read): {inp.irx.span()}")
        if inp.irx_alt is not None:
            print(f"  input {(TREND_DIR / 'IRX.csv').relative_to(ROOT)} (^IRX, GI agreement only): "
                  f"{inp.irx_alt.span()}")
        print(f"  input {inp.sources['GSPC'].relative_to(ROOT)} (^GSPC, calendar only): "
              f"{inp.gspc.span()}")
        if inp.gspc_alt is not None:
            print(f"  input {(TREND_DIR / 'GSPC.csv').relative_to(ROOT)} (^GSPC, GI agreement "
                  f"only): {inp.gspc_alt.span()}")
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
