"""sector_momentum — does holding the three strongest SPDR sectors beat holding all nine?

REGISTRATION: research/pre-registrations/f1_selection/signal/sector_momentum.md (registered
2026-11-28, second read passed, committed 8e94d19). Every constant, floor, seed, window and
verdict word below is that file's. Read it before changing anything here.

WHAT IT ASKS
------------
At each month-end close rank the nine original SPDR sector ETFs by their 12-1 return
(Adj Close at M_-1 over M_-12) and hold the top three at 1/3 each, traded at the next
session's close with 5 bp per side. Graded against EW-9 (all nine, rebalanced to 1/9 at
every execution close, same cost) on XS = 12 x the mean monthly difference over the pooled
window 2000-01..2026-08, each half a sign check. Eleven more cells exist only for PBO.

ORDER OF WORK
-------------
Data gates (GE, GI, GB), GX, GC, GR, then gate GK: the module's own test run on simulated
panels with no cross-sectional predictability. The real XS is reachable only through a
`GKPass` token that `gate_calibration` alone can create, so no real-data statistic can be
computed or printed before GK has passed.

DATA
----
yfinance, auto_adjust=False, cached in backtests/sector_momentum/<TICKER>.csv (date, close,
adj_close) for the nine, SPY and IRX, plus <TICKER>_dividends.csv for the nine. Fetched only
with `--refresh`; without it a missing file refuses (exit 3). backtests/trend_overlay/IRX.csv
is read for gate GI's cross-check only and never written. No close after 2026-09-22 enters
the in-sample run.

Nothing ships from this study. Run:

    python3 -m scripts.backtest_study run sector_momentum --refresh
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import math
import random
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib.path_bootstrap import _resample_indices  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/signal/sector_momentum.md"
NAME = "sector_momentum"
CACHE_DIR = ROOT / "backtests" / "sector_momentum"
IRX_TREND_OVERLAY = ROOT / "backtests" / "trend_overlay" / "IRX.csv"

TICKERS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")   # alphabetical
NT = len(TICKERS)
FETCH_START = "1998-01-01"
IRX_SYMBOL, IRX_START = "^IRX", "1960-01-01"
NY_CLOSE_SETTLED = "16:30"

IN_SAMPLE_END = "2026-09-22"
GRADED_LAST = "2026-08"
EARLY_LAST = "2012-12"
LATE_FIRST = "2013-01"
FORWARD = ("2026-12", "2029-11")
FORWARD_MONTHS = 36
FORWARD_AFTER = "2029-11-30"
SUNSET = "2030-11-30"

FORMATIONS = {"12-1": (12, 1), "6-1": (6, 1), "3-1": (3, 1), "12-0": (12, 0)}   # (lookback, skip)
KS = (2, 3, 4)
CELLS = tuple(f"{f}-T{k}" for f in FORMATIONS for k in KS)
HEADLINE = "12-1-T3"
MAX_LB = max(lb for lb, _ in FORMATIONS.values())
TIE_TOL = 1e-12

COST_BP = 5.0
COST_SENS = (0.0, 15.0)
BLOCK = 6
BLOCK_FALLBACK = 12
BLOCK_SENS = (3, 12)
BOOT_N = 5_000
SEED = 20261128
ALPHA = 0.05
PBO_S = 16
PBO_VETO = 0.50
PBO_FRAGILE = 0.25
MIN_GRADED = 240
MIN_HALF = 120
NW_LAGS = 12
TRADING_DAYS = 252

GK_PATHS = 500
GK_BOUND = 0.075
GK_BATCH = 100
GARCH = dict(alpha=0.02, gamma=0.12, beta=0.90)
T_DF = 5
REF = 0.030
DELTA_GRID = tuple(round(0.0025 * i, 4) for i in range(1, 61))     # 0.25% .. 15.00%

GI_IRX_CARRY = 5
GI_IRX_AGREE = 0.01
GB_RATIO_FALL = 1e-4
GB_RATIO_RISE = 0.03
GB_DIV_MATCH = 0.001
GB_PEER = 0.03
GB_RET = 0.35
GX_SAMPLES = 24
GR_TOL = 1e-12

EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH        # 3
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
# Header provenance the runner reads by ast (docs/architecture.md, study runner).
HEADER_ERA = "current (inputs are unversioned market closes)"
HEADER_INPUTS = ["backtests/sector_momentum/*.csv"]

SQRT12 = math.sqrt(12.0)


class Refused(Exception):
    def __init__(self, code: int, message: str, reason: str = "gate"):
        super().__init__(message)
        self.code = code
        self.message = message
        self.reason = reason


# ════════════════════════════════════════════════════════════════════════════
# Data
# ════════════════════════════════════════════════════════════════════════════

def _cache_path(name: str, cache_dir: Path | None = None) -> Path:
    return (cache_dir or CACHE_DIR) / f"{name}.csv"


def _div_path(name: str, cache_dir: Path | None = None) -> Path:
    return (cache_dir or CACHE_DIR) / f"{name}_dividends.csv"


def _ny_now() -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def fetch_series(name: str) -> Path:
    """yfinance -> backtests/sector_momentum/<name>.csv. A bar dated today is kept only after
    16:30 New York time; yfinance's `end` is exclusive."""
    import pandas as pd
    import yfinance as yf
    sym, start = (IRX_SYMBOL, IRX_START) if name == "IRX" else (name, FETCH_START)
    now = _ny_now()
    today = now.date().isoformat()
    end = (now.date() + timedelta(days=1)).isoformat()
    df = yf.download(sym, start=start, end=end, auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise Refused(EXIT_INPUT, f"GE: yfinance returned no rows for {sym}. Exit 3.")

    def col(c):
        x = df[c]
        return x.iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else x

    close, adj = col("Close"), col("Adj Close")
    keep_today = now.strftime("%H:%M") >= NY_CLOSE_SETTLED
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(name)
    tmp = path.with_suffix(".tmp")
    n = 0
    with tmp.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "close", "adj_close"])
        for d, c, a in zip(close.index, close.values, adj.values):
            ds = pd.Timestamp(d).strftime("%Y-%m-%d")
            if ds > today or (ds == today and not keep_today):
                continue
            w.writerow([ds, repr(float(c)) if c == c else "", repr(float(a)) if a == a else ""])
            n += 1
    tmp.replace(path)
    print(f"fetched {sym} -> {path.relative_to(ROOT)} ({n} rows)")
    if name in TICKERS:
        d = yf.Ticker(name).dividends
        dp = _div_path(name)
        tmp = dp.with_suffix(".tmp")
        with tmp.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "dividend"])
            for ts, v in zip(d.index, d.values):
                w.writerow([pd.Timestamp(ts).strftime("%Y-%m-%d"), repr(float(v))])
        tmp.replace(dp)
    return path


def read_dividends(name: str, cache_dir: Path | None = None) -> dict[str, float]:
    p = _div_path(name, cache_dir)
    if not p.exists():
        return {}
    with p.open(newline="") as fh:
        return {r["date"][:10]: float(r["dividend"]) for r in csv.DictReader(fh)}


def _num(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v if math.isfinite(v) else float("nan")


@dataclass
class Series:
    """Rows as read: an empty, zero or negative close is kept, so gate GI can see it."""
    dates: list[str]
    close: np.ndarray
    adj: np.ndarray
    n_dupes: int = 0

    def cut(self, end: str) -> "Series":
        k = bisect.bisect_right(self.dates, end)
        return Series(self.dates[:k], self.close[:k].copy(), self.adj[:k].copy(), self.n_dupes)


def read_series(path: Path, yield_series: bool = False) -> Series:
    """(date, close, adj_close) ascending. A yield series (`^IRX`) keeps every finite close,
    zero and negative included, and drops only rows with no close (those sessions carry)."""
    rows = []
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            c = _num(r.get("close"))
            a = _num(r.get("adj_close"))
            if yield_series and c != c:
                continue
            rows.append((r["date"][:10], c, a))
    rows.sort(key=lambda x: x[0])
    dates = [r[0] for r in rows]
    return Series(dates, np.array([r[1] for r in rows], dtype=float),
                  np.array([r[2] for r in rows], dtype=float), len(dates) - len(set(dates)))


def raw_nonpositive(path: Path, lo: str, hi: str) -> int:
    """Finite closes at or below zero in the file between lo and hi, counted from the text."""
    n = 0
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            c = _num(r.get("close"))
            if c == c and c <= 0 and lo <= r["date"][:10] <= hi:
                n += 1
    return n


@dataclass
class Inputs:
    etf: dict                  # ticker -> Series (the nine)
    spy: Series
    irx: Series
    irx_alt: Series | None
    irx_path: Path | None = None
    divs: dict = field(default_factory=dict)

    def cut(self, end: str) -> "Inputs":
        return Inputs({t: s.cut(end) for t, s in self.etf.items()}, self.spy.cut(end),
                      self.irx.cut(end), self.irx_alt.cut(end) if self.irx_alt is not None else None,
                      self.irx_path, self.divs)


def load_inputs(refresh: bool = False, cache_dir: Path | None = None) -> Inputs:
    if refresh:
        for t in TICKERS + ("SPY", "IRX"):
            fetch_series(t)
    out = {}
    for t in TICKERS + ("SPY", "IRX"):
        p = _cache_path(t, cache_dir)
        if not p.exists():
            raise Refused(EXIT_INPUT, f"GE: {p} is missing; fetch it with --refresh. Exit 3.")
        s = read_series(p, yield_series=(t == "IRX"))
        if not s.dates:
            raise Refused(EXIT_INPUT, f"GE: {p} is empty. Exit 3.")
        out[t] = s
    alt = read_series(IRX_TREND_OVERLAY, True) if IRX_TREND_OVERLAY.exists() else None
    divs = {t: read_dividends(t, cache_dir) for t in TICKERS}
    return Inputs({t: out[t] for t in TICKERS}, out["SPY"], out["IRX"], alt,
                  _cache_path("IRX", cache_dir), divs)


def first_common_session(inp: Inputs) -> str:
    return max(s.dates[0] for s in inp.etf.values())


# ════════════════════════════════════════════════════════════════════════════
# The panel: one row per SPY session from the first common session
# ════════════════════════════════════════════════════════════════════════════

def month_end_idx(dates: list[str]) -> list[int]:
    """Indices of the last session of each calendar month. The last row is never one, so a
    cut series never invents a decision."""
    return [i for i in range(len(dates) - 1) if dates[i][:7] != dates[i + 1][:7]]


@dataclass
class Panel:
    dates: list[str]
    adj: np.ndarray            # sessions x 9 (NaN where absent)
    close: np.ndarray          # sessions x 9
    spy: np.ndarray            # SPY adjusted close
    irx_c: np.ndarray          # ^IRX close, last close carried forward
    irx_carry: np.ndarray
    tb: np.ndarray             # daily T-bill return on session k, from close k-1


def build_panel(inp: Inputs, start: str | None = None) -> Panel:
    """Every SPY session of the inputs it is handed from `start` on. It never cuts: the
    caller hands it series already cut at IN_SAMPLE_END."""
    start = start or first_common_session(inp)
    spy = inp.spy
    keep = [i for i, d in enumerate(spy.dates) if start <= d]
    dates = [spy.dates[i] for i in keep]
    n = len(dates)
    adj = np.full((n, NT), np.nan)
    close = np.full((n, NT), np.nan)
    for i, t in enumerate(TICKERS):
        s = inp.etf[t]
        ma = dict(zip(s.dates, s.adj))
        mc = dict(zip(s.dates, s.close))
        adj[:, i] = [ma.get(d, np.nan) for d in dates]
        close[:, i] = [mc.get(d, np.nan) for d in dates]
    irx = inp.irx
    irx_c = np.full(n, np.nan)
    carry = np.zeros(n, dtype=int)
    j, last, run = 0, np.nan, 0
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
    return Panel(dates, adj, close, spy.adj[keep].copy(), irx_c, carry, tb)


# ════════════════════════════════════════════════════════════════════════════
# Months: everything graded runs on per-month aggregates of the daily panel
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Months:
    """Month-end j = 0..J. Month j (j >= 1) is the sessions after month-end j-1 through
    month-end j. B[j] is the growth on its first session (the execution session, earned on
    the old holdings); A[j] the growth over the rest. L[j] is the month-end level. Leading
    axes, when present, are paths."""
    labels: list[str]
    me: list[int]
    B: np.ndarray              # (..., J+1, 9), row 0 unused
    A: np.ndarray
    L: np.ndarray


def months_from_panel(P: Panel, adj: np.ndarray | None = None) -> Months:
    adj = P.adj if adj is None else adj
    me = month_end_idx(P.dates)
    J = len(me) - 1
    B = np.full((J + 1, NT), np.nan)
    A = np.full((J + 1, NT), np.nan)
    for j in range(1, J + 1):
        f, last = me[j - 1] + 1, me[j]
        B[j] = adj[f] / adj[f - 1]
        A[j] = adj[last] / adj[f]
    return Months([P.dates[k][:7] for k in me], me, B, A, adj[me].copy())


def month_growth(g: np.ndarray, me: list[int], j0: int) -> np.ndarray:
    """Monthly returns from a daily growth series; month j0+1 starts after the execution
    close me[j0]+1, so it is short by one session."""
    out = np.full(len(me), np.nan)
    for j in range(j0 + 1, len(me)):
        a = me[j0] + 2 if j == j0 + 1 else me[j - 1] + 1
        out[j] = float(np.prod(g[a:me[j] + 1])) - 1.0
    return out


# ════════════════════════════════════════════════════════════════════════════
# The rule
# ════════════════════════════════════════════════════════════════════════════

def parse_cell(cell: str) -> tuple[int, int, int]:
    f, k = cell.rsplit("-T", 1)
    lb, skip = FORMATIONS[f]
    return lb, skip, int(k)


def formation(L: np.ndarray, j, lookback: int, skip: int) -> np.ndarray:
    """Adj Close(M_-skip) / Adj Close(M_-lookback) - 1 at decision month-end j. Reads two
    month-end levels only."""
    return L[..., j - skip, :] / L[..., j - lookback, :] - 1.0


def top_k(F: np.ndarray, k: int) -> np.ndarray:
    """0/1 selection of the k largest along the last axis. Values within 1e-12 rank by
    ticker in alphabetical order, earlier first."""
    a = F[..., :, None]
    b = F[..., None, :]
    idx = np.arange(F.shape[-1])
    ahead = (b > a + TIE_TOL) | ((np.abs(b - a) <= TIE_TOL) & (idx[None, :] < idx[:, None]))
    rank = ahead.sum(axis=-1)
    sel = rank < k
    bad = sel.sum(axis=-1) != k
    if np.any(bad):                       # a tie chain longer than the tolerance: exact sort
        flat_F = F.reshape(-1, F.shape[-1])
        flat_s = sel.reshape(-1, F.shape[-1])
        for r in np.where(bad.reshape(-1))[0]:
            order = sorted(range(F.shape[-1]), key=lambda i: (-flat_F[r, i], i))
            flat_s[r] = False
            flat_s[r, order[:k]] = True
        sel = flat_s.reshape(sel.shape)
    return sel


def rule_weights(L: np.ndarray, cell: str, j0: int) -> np.ndarray:
    """Target weights decided at month-end j (held through month j+1), for j0 <= j < J."""
    lb, skip, k = parse_cell(cell)
    W = np.full(L.shape, np.nan)
    js = np.arange(j0, L.shape[-2] - 1)
    if len(js):
        F = formation(L, js, lb, skip)
        W[..., js, :] = top_k(F, k) / float(k)
    return W


def ew_weights(L: np.ndarray, j0: int) -> np.ndarray:
    W = np.full(L.shape, np.nan)
    W[..., j0:L.shape[-2] - 1, :] = 1.0 / NT
    return W


def first_decision(M: Months) -> int | None:
    for j in range(MAX_LB, len(M.me)):
        if np.isfinite(M.L[j - MAX_LB:j + 1]).all():
            return j
    return None


def decision_table(P: Panel, M: Months, j0: int, cell: str) -> dict:
    """{execution session index: target weights}. The key is the session after the
    month-end close the weights were decided at."""
    W = rule_weights(M.L, cell, j0)
    out = {M.me[j] + 1: W[j] for j in range(j0, len(M.me) - 1)}
    if M.me[-1] + 1 < len(P.dates):
        out[M.me[-1] + 1] = rule_last(M, cell)
    return out


def rule_last(M: Months, cell: str) -> np.ndarray:
    lb, skip, k = parse_cell(cell)
    j = len(M.me) - 1
    return top_k(formation(M.L, j, lb, skip), k) / float(k)


# ════════════════════════════════════════════════════════════════════════════
# Simulation on month aggregates (real data and null paths share these)
# ════════════════════════════════════════════════════════════════════════════

def simulate_rule(B: np.ndarray, A: np.ndarray, W: np.ndarray, j0: int, cost_bp: float
                  ) -> tuple[np.ndarray, np.ndarray]:
    """Monthly returns and turnover. Starts at 1.0 at the first execution close (month j0+1's
    first session) at W[j0], no entry cost. At each later execution the old holdings first
    earn B, then trade to W[j-1]: traded = sum |target - drifted| x pre-cost equity, cost
    c x traded, target weights applied to the equity after cost. Then the month earns A."""
    c = cost_bp / 1e4
    shp = B.shape[:-2]
    J = B.shape[-2] - 1
    r = np.full(shp + (J + 1,), np.nan)
    turn = np.zeros(shp + (J + 1,))
    h = W[..., j0, :].copy()
    e_prev = np.ones(shp)
    for j in range(j0 + 1, J + 1):
        if j > j0 + 1:
            h = h * B[..., j, :]
            e_pre = h.sum(axis=-1)
            tgt = W[..., j - 1, :]
            traded = np.abs(tgt * e_pre[..., None] - h).sum(axis=-1)
            turn[..., j] = traded / e_pre
            e_post = e_pre - c * traded
            h = tgt * e_post[..., None]
        h = h * A[..., j, :]
        e = h.sum(axis=-1)
        r[..., j] = e / e_prev - 1.0
        h = h / e[..., None]
        e_prev = np.ones(shp)
    return r, turn


def simulate_ew(B: np.ndarray, A: np.ndarray, j0: int, cost_bp: float, trace: list | None = None
                ) -> tuple[np.ndarray, np.ndarray]:
    """EW-9, rebalanced equal weight: 1/9 in each, traded back to 1/9 at every execution
    close at the same per-side cost. Written apart from `simulate_rule` (no ranking, no
    weight table), so gate GR is a real replay check. `trace` collects (month, post-trade
    weights, cost) when given."""
    c = cost_bp / 1e4
    shp = B.shape[:-2]
    J = B.shape[-2] - 1
    w = np.full(NT, 1.0 / NT)
    r = np.full(shp + (J + 1,), np.nan)
    turn = np.zeros(shp + (J + 1,))
    val = np.broadcast_to(w, shp + (NT,)).copy()
    for j in range(j0 + 1, J + 1):
        if j > j0 + 1:
            val = val * B[..., j, :]
            eq = val.sum(axis=-1)
            drift = val / eq[..., None]
            tr = np.abs(w - drift).sum(axis=-1) * eq
            turn[..., j] = tr / eq
            eq = eq - tr * c
            val = w * eq[..., None]
            if trace is not None:
                trace.append((j, val / eq[..., None], tr * c))
        val = val * A[..., j, :]
        r[..., j] = val.sum(axis=-1) - 1.0
        val = val / val.sum(axis=-1)[..., None]
    return r, turn


def daily_curve(G: np.ndarray, table: dict, cost_bp: float) -> np.ndarray:
    """Daily growth of a weight table on the daily panel (printed daily drawdowns and the
    best-sector-month replacement only). Same order as `simulate_rule`."""
    n = len(G)
    ks = sorted(table)
    e0 = ks[0]
    g = np.full(n, np.nan)
    h = table[e0].copy()
    E = 1.0
    c = cost_bp / 1e4
    for k in range(e0 + 1, n):
        h = h * G[k]
        E_new = float(h.sum())
        if k in table:
            tgt = table[k]
            traded = float(np.abs(tgt * E_new - h).sum())
            E_new -= c * traded
            h = tgt * E_new
        g[k] = E_new / E
        E = E_new
    return g


# ════════════════════════════════════════════════════════════════════════════
# Windows, bootstrap, metrics
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Window:
    name: str
    lo: int                    # month index j (inclusive)
    hi: int                    # exclusive
    labels: list[str]

    @property
    def n(self) -> int:
        return self.hi - self.lo

    def sl(self, x: np.ndarray) -> np.ndarray:
        return x[..., self.lo:self.hi]


def make_window(M: Months, j0: int, name: str, first: str | None, last: str) -> Window:
    idx = [j for j in range(j0 + 1, len(M.labels))
           if (first is None or M.labels[j] >= first) and M.labels[j] <= last]
    if not idx:
        return Window(name, 0, 0, [])
    return Window(name, idx[0], idx[-1] + 1, M.labels[idx[0]:idx[-1] + 1])


def windows_of(M: Months, j0: int) -> tuple[Window, Window, Window]:
    return (make_window(M, j0, "graded", None, GRADED_LAST),
            make_window(M, j0, "early", None, EARLY_LAST),
            make_window(M, j0, "late", LATE_FIRST, GRADED_LAST))


@lru_cache(maxsize=None)
def boot_counts(n: int, block: int, draws: int = BOOT_N, seed: int = SEED) -> np.ndarray:
    """draws x n: how often each month appears in each moving circular block resample
    (path_bootstrap._resample_indices, one seeded stream). A mean under the resample is
    counts @ series / n, so every path shares one matrix."""
    rng = random.Random(seed)
    idx = np.array([_resample_indices(n, block, rng) for _ in range(draws)], dtype=np.int64)
    flat = (np.arange(draws)[:, None] * n + idx).ravel()
    return np.bincount(flat, minlength=draws * n).reshape(draws, n).astype(float)


def xs_draws(d: np.ndarray, block: int, boot_n: int) -> np.ndarray:
    """Bootstrap draws of XS. `d` is (months,) or (months, paths); returns (draws, ...)."""
    n = d.shape[0]
    C = boot_counts(n, block, boot_n)
    return 12.0 * (C @ d) / n


def ir_draws(d: np.ndarray, block: int, boot_n: int) -> np.ndarray:
    n = d.shape[0]
    C = boot_counts(n, block, boot_n)
    m = (C @ d) / n
    v = ((C @ (d * d)) - n * m * m) / (n - 1)
    s = np.sqrt(np.maximum(v, 0.0))
    return np.where(s > 0, SQRT12 * m / np.where(s > 0, s, 1.0), np.nan)


def p_two_sided(draws: np.ndarray) -> np.ndarray:
    """Twice the smaller of the share of draws at or below 0 and at or above 0, capped at 1."""
    le = np.mean(draws <= 0, axis=0)
    ge = np.mean(draws >= 0, axis=0)
    return np.minimum(1.0, 2.0 * np.minimum(le, ge))


def ci(draws: np.ndarray) -> tuple[float, float]:
    d = draws[np.isfinite(draws)]
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def ir(d: np.ndarray) -> float:
    s = float(np.std(d, ddof=1)) if len(d) > 1 else 0.0
    return SQRT12 * float(np.mean(d)) / s if s > 0 else float("nan")


def sharpe(ex: np.ndarray) -> float:
    return ir(ex)


def mdd(r: np.ndarray) -> float:
    if not len(r):
        return 0.0
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return float((1.0 - eq / peak).max())


def mdd_daily(g: np.ndarray) -> float:
    eq = np.cumprod(g)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return float((1.0 - eq / peak).max())


def cagr(r: np.ndarray) -> float:
    return float(np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0) if len(r) else float("nan")


def nw_ols(y: np.ndarray, x: np.ndarray, lags: int = NW_LAGS) -> tuple[float, float, float, float]:
    """OLS y = a + b x with Newey-West (Bartlett) errors: (a, se_a, b, se_b)."""
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


def year_sums(d: np.ndarray, labels: list[str]) -> dict[str, tuple[float, int]]:
    out: dict[str, list] = {}
    for m, x in zip(labels, d):
        out.setdefault(m[:4], []).append(x)
    return {y: (float(np.sum(v)), len(v)) for y, v in out.items()}


def mean_metric(rows: np.ndarray) -> np.ndarray:
    """PBO metric: the column mean of the rows given (the graded statistic XS, up to 12)."""
    return rows.mean(axis=0)


def run_pbo(Dm: np.ndarray, labels: list[str]):
    """Rows: monthly d_m of the 12 cells over the graded window. Trim the oldest months
    until S divides the row count; never pad."""
    drop = Dm.shape[0] % PBO_S
    res = PBO.cscv(Dm[drop:], S=PBO_S, metric=mean_metric, report_metric=mean_metric)
    return res, labels[:drop]


# ════════════════════════════════════════════════════════════════════════════
# Verdict
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Graded:
    xs: float
    p: float
    xs_early: float
    xs_late: float


def counts(g: Graded) -> bool:
    return g.p < ALPHA and g.xs > 0 and g.xs_early > 0 and g.xs_late > 0


def clearly_worse(g: Graded) -> bool:
    return g.p < ALPHA and g.xs < 0


def headline_word(powered: bool, pbo: float, g: Graded | None, d80: float,
                  refused: str | None = None) -> tuple[str, list[str]]:
    """The registered table; the first matching row wins."""
    if refused is not None:
        return f"REFUSED ({refused})", []
    if not powered:
        return "UNDERPOWERED", []
    notes: list[str] = []
    if PBO_FRAGILE < pbo <= PBO_VETO:
        notes.append("selection fragile")
    if counts(g) and pbo > PBO_VETO:
        return "PBO-VETO", notes
    if counts(g):
        return "BEATS-EW", notes + (["low power: the estimate is likely inflated"]
                                    if d80 > REF else [])
    if clearly_worse(g):
        return "CONTRARY", notes
    if g.p < ALPHA and g.xs > 0:
        bad = [nm for nm, x in (("early half", g.xs_early), ("late half", g.xs_late)) if x <= 0]
        notes.append(f"pooled gain, {' and '.join(bad)} sign disagrees")
    if d80 > REF:
        return "UNDERPOWERED-BY-DESIGN", notes + ["could not see one: delta80 above REF"]
    return "NULL", notes


def forward_word(xs: float) -> str:
    return "FORWARD-AGREES" if xs > 0 else "FORWARD-AGAINST"


def fmt_d80(d: float) -> str:
    return "above 0.15" if not math.isfinite(d) else f"{d:.4f}"


def _notes(nt: list[str]) -> str:
    return f" ({'; '.join(nt)})" if nt else ""


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def _rows(rows: list[str], limit: int = 25) -> None:
    for r in rows[:limit]:
        print(r)
    if len(rows) > limit:
        print(f"    ... and {len(rows) - limit} more")


def gate_dates(inp: Inputs, forward: bool = False) -> list[str]:
    """GE on the uncut files: each of the 11 starts on or before the first common session
    and has a finite close after 2026-09-22 (adjusted close for the ten price files)."""
    d0 = first_common_session(inp)
    bad = []
    files = [(t, inp.etf[t], True) for t in TICKERS] + [("SPY", inp.spy, True),
                                                        ("IRX", inp.irx, False)]
    for t, s, use_adj in files:
        v = s.adj if use_adj else s.close
        after = [d for d, x in zip(s.dates, v) if d > IN_SAMPLE_END and x == x]
        if s.dates[0] > d0:
            bad.append(f"    {t}: first session {s.dates[0]} is after the first common session {d0}")
        if not after:
            bad.append(f"    {t}: no session with a finite close after {IN_SAMPLE_END} "
                       f"(last {s.dates[-1]})")
    if bad:
        _rows(bad)
        raise Refused(EXIT_INPUT, f"GE: {len(bad)} date failures (rows above). Exit 3.", "gate")
    return [f"  GE dates: all 11 files start on or before {d0} (first common session) and hold "
            f"a session past {IN_SAMPLE_END}   PASS"]


def gate_inputs(inp: Inputs, P: Panel, end: str = IN_SAMPLE_END) -> list[str]:
    """GI over the rows a statistic reads (first common session to `end`)."""
    d0 = P.dates[0]
    bad = []
    for t, s in list(inp.etf.items()) + [("SPY", inp.spy), ("IRX", inp.irx)]:
        if s.n_dupes:
            bad.append(f"    {t}: {s.n_dupes} duplicate dates")
    spy_set = set(P.dates)
    for i, t in enumerate(TICKERS):
        s = inp.etf[t]
        extra = [d for d in s.dates if d0 <= d <= end and d not in spy_set]
        if extra:
            bad.append(f"    {t}: {len(extra)} sessions SPY lacks (first {extra[0]})")
        for arr, nm in ((P.adj[:, i], "adjusted close"), (P.close[:, i], "close")):
            miss = np.where(~(arr > 0))[0]
            for k in miss[:5]:
                bad.append(f"    {t} {P.dates[k]}: {nm} {arr[k]!r} (missing, zero or negative)")
            if len(miss) > 5:
                bad.append(f"    {t}: {len(miss)} such {nm} rows in all")
    miss = np.where(~(P.spy > 0))[0]
    for k in miss[:5]:
        bad.append(f"    SPY {P.dates[k]}: adjusted close {P.spy[k]!r}")
    worst = int(P.irx_carry.max()) if len(P.irx_carry) else 0
    if worst > GI_IRX_CARRY:
        k = int(np.argmax(P.irx_carry))
        bad.append(f"    IRX: carried {worst} sessions to {P.dates[k]} (limit {GI_IRX_CARRY})")
    lo = inp.irx.dates[max(0, bisect.bisect_left(inp.irx.dates, d0) - 1)] if inp.irx.dates else d0
    used = int(np.sum([(c <= 0) for d, c in zip(inp.irx.dates, inp.irx.close) if lo <= d <= end]))
    in_file = raw_nonpositive(inp.irx_path, lo, end) if inp.irx_path is not None else used
    if used != in_file:
        bad.append(f"    IRX: {in_file} zero or negative closes in the file, {used} used")
    agree = "trend_overlay copy absent"
    if inp.irx_alt is not None:
        m = dict(zip(inp.irx_alt.dates, inp.irx_alt.close))
        diffs = [(d, abs(c - m[d])) for d, c in zip(inp.irx.dates, inp.irx.close)
                 if d in m and d <= IN_SAMPLE_END and m[d] == m[d]]
        far = [x for x in diffs if not x[1] <= GI_IRX_AGREE]
        for d, x in far[:10]:
            bad.append(f"    IRX {d}: copies differ by {x:.4f} points")
        agree = (f"agrees with backtests/trend_overlay/IRX.csv on {len(diffs)} common dates, worst "
                 f"{max((x[1] for x in diffs), default=0.0):.4f} points")
    if bad:
        _rows(bad)
        raise Refused(EXIT_INPUT, f"GI: {len(bad)} integrity failures (rows above). Exit 3.", "gate")
    return [f"  GI integrity: {len(P.dates)} SPY sessions {d0} .. {P.dates[-1]}, every one with a "
            f"close and adjusted close for all nine, none extra, no duplicates; worst ^IRX carry "
            f"{worst} sessions; {used} zero or negative ^IRX closes used (file holds {in_file}); "
            f"^IRX {agree}   PASS"]


@dataclass
class Flag:
    ticker: str
    k: int                     # panel session of the ex-date
    step: float
    line: str


def gate_basis(P: Panel, divs: dict) -> tuple[list[str], list[Flag]]:
    """GB over the panel rows. The adj/close ratio never falls by more than 0.01%; a rise up
    to 3% passes; a rise above 3% needs a feed distribution whose implied rise matches within
    0.1 points, then takes the peer check, whose failure flags the row. No adjusted daily
    return beyond +-35%."""
    bad, passed, flags, lines = [], [], [], []
    R = P.adj[1:] / P.adj[:-1] - 1.0
    for i, t in enumerate(TICKERS):
        ratio = P.adj[:, i] / P.close[:, i]
        step = ratio[1:] / ratio[:-1] - 1.0
        dv = divs.get(t) or {}
        for k in np.where((step < -GB_RATIO_FALL) | (step > GB_RATIO_RISE) | ~np.isfinite(step))[0]:
            d0, d1 = P.dates[k], P.dates[k + 1]
            row = f"    {t} {d0} -> {d1}: adj/close step {step[k]:+.6f}"
            D = dv.get(d1)
            cp = P.close[k, i]
            if step[k] > GB_RATIO_RISE and D is not None and 0 < D < cp and \
                    abs(cp / (cp - D) - 1.0 - step[k]) <= GB_DIV_MATCH:
                peers = np.delete(R[k], i)
                med = float(np.median(peers))
                raw = P.close[k + 1, i] / cp - 1.0
                desc = (f"{row}; feed distribution {D:.4f} implies {cp / (cp - D) - 1.0:+.6f}; raw "
                        f"close return {raw:+.4f}; adjusted return {R[k, i]:+.4f}, peer median "
                        f"{med:+.4f}")
                if abs(R[k, i] - med) <= GB_PEER:
                    passed.append(desc + ": passed")
                else:
                    flags.append(Flag(t, k + 1, float(step[k]), desc + ": FLAGGED by the peer check"))
                continue
            bad.append(row + (f"; feed distribution {D if D is not None else 'none'}"
                              if step[k] > GB_RATIO_RISE else ""))
        r = R[:, i]
        for k in np.where(~(np.abs(r) <= GB_RET))[0]:
            bad.append(f"    {t} {P.dates[k]} -> {P.dates[k + 1]}: adjusted return {r[k]:+.4f}")
        lines.append(f"{t} fall {np.nanmin(step):+.6f} rise {np.nanmax(step):+.4f} "
                     f"|ret| {np.nanmax(np.abs(r)):.3f}")
    if bad:
        _rows(bad)
        raise Refused(EXIT_INPUT, f"GB: {len(bad)} basis breaks (rows above). Exit 3.", "gate")
    out = ["  GB basis (worst adj/close fall, worst rise, worst |daily adjusted return|):"]
    for i in range(0, len(lines), 3):
        out.append("    " + ";  ".join(lines[i:i + 3]))
    out.append(f"  GB rises above {GB_RATIO_RISE:.0%} matched by a feed distribution: "
               f"{len(passed) + len(flags)} ({len(flags)} flagged by the peer check)")
    out.extend(passed)
    out.extend(f.line for f in flags)
    out.append("  GB   PASS" + (" (flagged rows are settled under VERDICT)" if flags else ""))
    return out, flags


def gate_lookahead(inp: Inputs, P: Panel, M: Months, j0: int, tables: dict) -> list[str]:
    """GX at run time: 24 evenly spaced decisions are recomputed on every series cut at the
    decision close, with the decision date given, and must match the run's holdings."""
    last = len(M.me) - 2
    js = sorted(set(np.linspace(j0, last, GX_SAMPLES).astype(int).tolist()))
    moved = 0
    for j in js:
        t = M.me[j]
        Pc = build_panel(inp.cut(P.dates[t]), P.dates[0])
        mec = month_end_idx(Pc.dates)
        if Pc.dates != P.dates[:t + 1] or t in mec:
            raise Refused(1, "GX: a cut series is not a prefix of the calendar, or its last row "
                             "became a decision close. Exit 1.", "gate")
        Lc = Pc.adj[mec + [t]]                  # the decision date is given
        for cell in CELLS:
            lb, skip, k = parse_cell(cell)
            w = top_k(formation(Lc, len(Lc) - 1, lb, skip), k) / float(k)
            if not np.array_equal(w, tables[cell][t + 1]):
                moved += 1
    if moved:
        raise Refused(1, f"GX: {moved} decisions moved when the series were cut at the decision "
                         f"close. Exit 1.", "gate")
    return [f"  GX no lookahead: {len(js)} decisions x {len(CELLS)} cells recomputed on series cut "
            f"at the decision close; 0 moved   PASS"]


def gate_replay(r_k9: np.ndarray, r_ew: np.ndarray, w: Window) -> list[str]:
    diff = float(np.nanmax(np.abs(w.sl(r_k9) - w.sl(r_ew))))
    if not diff <= GR_TOL:
        raise Refused(EXIT_INPUT, f"GR: the rule's code with K = 9 differs from EW-9 by {diff:.3e} "
                                  f"in a month (tolerance {GR_TOL:.0e}). Exit 3.", "gate")
    return [f"  GR replay: the rule's code with K = 9 vs EW-9 over {w.n} months, worst |diff| "
            f"{diff:.1e}   PASS"]


# ════════════════════════════════════════════════════════════════════════════
# Gate GK — calibration on null panels
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class RealBasis:
    """What the generators read from the real panel: the nine's daily returns from the
    first common session through the last graded month-end, and the month layout."""
    R: np.ndarray              # sessions x 9 daily returns
    counts: list[int]          # sessions per month j = 1..J
    month_B: np.ndarray        # (J, 9) real months, first-session growth
    month_A: np.ndarray        # (J, 9) rest-of-month growth
    month_Bd: np.ndarray       # demeaned to mu_bar
    month_Ad: np.ndarray
    mu_bar: float
    cov: np.ndarray
    J: int
    j0: int


def real_basis(P: Panel, M: Months, j0: int, last_j: int) -> RealBasis:
    """`last_j` is the month-end index of the last graded month (2026-08)."""
    me = M.me[:last_j + 1]
    R = P.adj[1:me[-1] + 1] / P.adj[:me[-1]] - 1.0           # returns of sessions 1..me[-1]
    mu = R.mean(axis=0)
    mu_bar = float(mu.mean())
    Rd = R - mu + mu_bar
    J = len(me) - 1

    def agg(X):
        Bm = np.empty((J, NT))
        Am = np.empty((J, NT))
        for j in range(1, J + 1):
            f, last = me[j - 1] + 1, me[j]                   # session f's return is X[f-1]
            Bm[j - 1] = 1.0 + X[f - 1]
            Am[j - 1] = np.prod(1.0 + X[f:last], axis=0)
        return Bm, Am

    Bm, Am = agg(R)
    Bd, Ad = agg(Rd)
    return RealBasis(R, [me[j] - me[j - 1] for j in range(1, J + 1)], Bm, Am, Bd, Ad, mu_bar,
                     np.cov(R.T), J, j0)


def _levels(B: np.ndarray, A: np.ndarray) -> np.ndarray:
    L = np.ones(B.shape)
    L[..., 1:, :] = np.cumprod(B[..., 1:, :] * A[..., 1:, :], axis=-2)
    return L


def _from_daily(X: np.ndarray, counts: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """(paths, sessions, 9) daily returns -> (paths, J+1, 9) B and A."""
    P_, _, _ = X.shape
    J = len(counts)
    cs = np.concatenate([np.zeros((P_, 1, NT)), np.cumsum(np.log1p(X), axis=1)], axis=1)
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    ends = starts + np.array(counts)
    B = np.full((P_, J + 1, NT), np.nan)
    A = np.full((P_, J + 1, NT), np.nan)
    B[:, 1:] = 1.0 + X[:, starts]
    A[:, 1:] = np.exp(cs[:, ends] - cs[:, starts + 1])
    return B, A


def null_batch(gen: str, rb: RealBasis, rng: np.random.Generator, n: int
               ) -> tuple[np.ndarray, np.ndarray]:
    """n null paths of month aggregates (n, J+1, 9). Every ETF has one common mean except in
    G-MEANS, which keeps each ETF's real mean and grades nothing."""
    J = rb.J
    if gen in ("G-MONTH", "G-MEANS"):
        pick = rng.integers(0, J, size=(n, J))
        Bsrc, Asrc = (rb.month_Bd, rb.month_Ad) if gen == "G-MONTH" else (rb.month_B, rb.month_A)
        B = np.full((n, J + 1, NT), np.nan)
        A = np.full((n, J + 1, NT), np.nan)
        B[:, 1:] = Bsrc[pick]
        A[:, 1:] = Asrc[pick]
        return B, A
    T = int(sum(rb.counts))
    Lc = np.linalg.cholesky(rb.cov)
    if gen == "G-IID":
        z = rng.standard_normal((n, T, NT))
        X = rb.mu_bar + z @ Lc.T
    elif gen == "G-GARCH":
        z = rng.standard_t(T_DF, size=(n, T, NT)) * math.sqrt((T_DF - 2) / T_DF)
        u = z.mean(axis=2) * math.sqrt(NT)
        a, g, b = GARCH["alpha"], GARCH["gamma"], GARCH["beta"]
        om = 1.0 - a - g / 2.0 - b
        s2 = np.empty((n, T))
        s2[:, 0] = 1.0
        for t in range(1, T):
            up = u[:, t - 1]
            s2[:, t] = om + (a + g * (up < 0)) * up * up + b * s2[:, t - 1]
        X = rb.mu_bar + np.sqrt(s2)[:, :, None] * (z @ Lc.T)
    else:
        raise ValueError(gen)
    return _from_daily(X, rb.counts)


@dataclass
class NullSet:
    name: str
    r_rule: dict               # cost -> (paths, J+1)
    r_ew: dict


def simulate_null(gen: str, rb: RealBasis, n_paths: int, costs=(0.0, COST_BP) + COST_SENS
                  ) -> NullSet:
    rng = np.random.default_rng(SEED)
    rr = {c: [] for c in costs}
    re_ = {c: [] for c in costs}
    left = n_paths
    while left > 0:
        m = min(GK_BATCH, left)
        B, A = null_batch(gen, rb, rng, m)
        W = rule_weights(_levels(B, A), HEADLINE, rb.j0)
        for c in costs:
            rr[c].append(simulate_rule(B, A, W, rb.j0, c)[0])
            re_[c].append(simulate_ew(B, A, rb.j0, c)[0])
        left -= m
    return NullSet(gen, {c: np.concatenate(v) for c, v in rr.items()},
                   {c: np.concatenate(v) for c, v in re_.items()})


def bootstrap_draws(d: np.ndarray, block: int, boot_n: int) -> np.ndarray:
    """The registered bootstrap: paired moving block resample of d_m, XS per draw."""
    return xs_draws(d, block, boot_n)


@dataclass
class GKGen:
    name: str
    size: float                # graded-window rejection rate at 0 bp
    size_early: float
    size_late: float
    fp_beats: float            # at 5 bp
    fp_contrary: float
    year_pos: float            # null share of graded calendar years with sum d_m > 0
    hit: float                 # null hit rate
    fwd_pos: float             # share of 36-month windows with XS > 0
    mean_xs0: float            # mean graded XS at 0 bp
    d80: dict                  # cost -> delta80 (inf when above the grid)


def _pass_rates(xs: dict, srt: dict, shifts) -> np.ndarray:
    """Share of paths where the rule counts after shifting d_m by delta/12 in every window.
    `xs[w]` is (paths,), `srt[w]` the graded draws sorted per path (draws, paths)."""
    D = srt.shape[0]
    sh = -np.asarray(shifts, dtype=float)
    n_le = np.stack([np.searchsorted(srt[:, p], sh, side="right") for p in range(srt.shape[1])])
    n_ge = D - np.stack([np.searchsorted(srt[:, p], sh, side="left") for p in range(srt.shape[1])])
    p = np.minimum(1.0, 2.0 * np.minimum(n_le, n_ge) / D)          # (paths, shifts)
    dl = np.asarray(shifts, dtype=float)[None, :]
    ok = ((p < ALPHA) & (xs["graded"][:, None] + dl > 0) & (xs["early"][:, None] + dl > 0)
          & (xs["late"][:, None] + dl > 0))
    return ok.mean(axis=0)


def d80_of(rates: np.ndarray) -> float:
    hit = np.where(rates >= 0.80)[0]
    return DELTA_GRID[hit[0]] if len(hit) else float("inf")


def gk_generator(ns: NullSet, wins: dict, labels: list[str], block: int, boot_n: int,
                 boot=bootstrap_draws, power_costs=(COST_BP,)) -> GKGen:
    res = {}
    for c in sorted(set((0.0, COST_BP) + tuple(power_costs))):
        d = ns.r_rule[c] - ns.r_ew[c]
        xs, p, srt = {}, {}, None
        for nm, w in wins.items():
            dw = w.sl(d).T                                   # (months, paths)
            dr = boot(dw, block, boot_n)
            xs[nm] = 12.0 * dw.mean(axis=0)
            p[nm] = p_two_sided(dr)
            if nm == "graded":
                srt = np.sort(dr, axis=0)
        res[c] = (d, xs, p, srt)
    d0, xs0, p0, _ = res[0.0]
    d5, xs5, p5, _ = res[COST_BP]
    g = wins["graded"]
    beats = (p5["graded"] < ALPHA) & (xs5["graded"] > 0) & (xs5["early"] > 0) & (xs5["late"] > 0)
    worse = (p5["graded"] < ALPHA) & (xs5["graded"] < 0)
    dg = g.sl(d5)
    yrs: dict[str, list[int]] = {}
    for i, m in enumerate(g.labels):
        yrs.setdefault(m[:4], []).append(i)
    ys = np.stack([dg[:, ix].sum(axis=1) for ix in yrs.values()], axis=1)
    if dg.shape[1] >= FORWARD_MONTHS:
        cs = np.concatenate([np.zeros((dg.shape[0], 1)), np.cumsum(dg, axis=1)], axis=1)
        roll = cs[:, FORWARD_MONTHS:] - cs[:, :-FORWARD_MONTHS]
        fwd = float((roll > 0).mean())
    else:
        fwd = float("nan")
    d80 = {c: d80_of(_pass_rates(res[c][1], res[c][3], DELTA_GRID)) for c in res}
    return GKGen(ns.name, float((p0["graded"] < ALPHA).mean()), float((p0["early"] < ALPHA).mean()),
                 float((p0["late"] < ALPHA).mean()), float(beats.mean()), float(worse.mean()),
                 float((ys > 0).mean()), float((dg > 0).mean()), fwd, float(xs0["graded"].mean()),
                 d80)


_GK_KEY = object()


class GKPass:
    """Proof that gate GK passed. Only `gate_calibration` can make one; every real-data
    statistic asks for it."""

    def __init__(self, key, block: int, gens: list, d80: dict):
        if key is not _GK_KEY:
            raise RuntimeError("a GKPass is made by gate_calibration alone")
        self.block = block
        self.gens = gens
        self.d80 = d80                 # cost -> study delta80 (largest of the three)

    def fp_beats(self) -> float:
        return max(g.fp_beats for g in self.gens)


def _require(token) -> None:
    if not isinstance(token, GKPass):
        raise RuntimeError("gate GK has not passed: no real-data statistic may be computed")


def gk_rates_line(gens: list, block: int) -> str:
    return (f"  GK 0 bp graded-window rejection rate, block {block}, bound {GK_BOUND}: "
            + "  ".join(f"{g.name} {g.size:.3f}" for g in gens))


def gate_calibration(nulls: list, wins: dict, labels: list[str], block: int, boot_n: int,
                     boot=bootstrap_draws, verbose: bool = True,
                     power_costs=(COST_BP,) + COST_SENS) -> tuple[GKPass | None, list]:
    """GK. Returns (token, per-generator results); the token is None when any generator's
    0 bp rejection rate exceeds 0.075."""
    gens = [gk_generator(ns, wins, labels, block, boot_n, boot, power_costs) for ns in nulls]
    if verbose:
        print(gk_rates_line(gens, block))
    if any(not (g.size <= GK_BOUND) for g in gens):
        return None, gens
    d80 = {c: max(g.d80[c] for g in gens) for c in gens[0].d80}
    return GKPass(_GK_KEY, block, gens, d80), gens


def print_gk(gens: list, block: int) -> None:
    print(f"  per generator (rates at 5 bp unless marked; block {block}):")
    print(f"  {'generator':<9}{'size 0bp':>9}{'early':>7}{'late':>7}{'BEATS fp':>9}{'CONTR fp':>9}"
          f"{'yrs>0':>7}{'hit':>6}{'36m>0':>7}{'meanXS 0bp':>11}{'d80 5bp':>9}")
    for g in gens:
        print(f"  {g.name:<9}{g.size:>9.3f}{g.size_early:>7.3f}{g.size_late:>7.3f}{g.fp_beats:>9.3f}"
              f"{g.fp_contrary:>9.3f}{g.year_pos:>7.3f}{g.hit:>6.3f}{g.fwd_pos:>7.3f}"
              f"{g.mean_xs0:>+11.4f}{fmt_d80(g.d80[COST_BP]):>9}")


# ════════════════════════════════════════════════════════════════════════════
# The real run
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Real:
    P: Panel
    M: Months
    j0: int
    G: np.ndarray              # daily growth, sessions x 9
    W: dict                    # cell -> weights by decision month
    r: dict                    # label -> monthly returns at COST_BP
    turn: dict
    spy_m: np.ndarray
    tb_m: np.ndarray


def run_cells(M: Months, j0: int, cost: float, W: dict | None = None):
    W = W or {c: rule_weights(M.L, c, j0) for c in CELLS}
    r, turn = {}, {}
    for c in CELLS:
        r[c], turn[c] = simulate_rule(M.B, M.A, W[c], j0, cost)
    r["EW-9"], turn["EW-9"] = simulate_ew(M.B, M.A, j0, cost)
    return W, r, turn


def graded_excess(r_cell: np.ndarray, r_ew: np.ndarray, token: GKPass) -> np.ndarray:
    """d_m, the rule's monthly return minus EW-9's. Needs GK's token."""
    _require(token)
    return r_cell - r_ew


def graded_of(d: np.ndarray, wins: dict, block: int, boot_n: int, token: GKPass
              ) -> tuple[Graded, dict]:
    _require(token)
    out = {}
    for nm, w in wins.items():
        dw = w.sl(d)
        dr = xs_draws(dw, block, boot_n)
        out[nm] = (12.0 * float(dw.mean()), *ci(dr), float(p_two_sided(dr)))
    return Graded(out["graded"][0], out["graded"][3], out["early"][0], out["late"][0]), out


def headline_from(M: Months, j0: int, wins: dict, cost: float, block: int, boot_n: int,
                  token: GKPass, d80: float, powered: bool):
    _require(token)
    _, r, _ = run_cells(M, j0, cost)
    D = {c: graded_excess(r[c], r["EW-9"], token) for c in CELLS}
    g, _ = graded_of(D[HEADLINE], wins, block, boot_n, token)
    res, _ = run_pbo(np.column_stack([wins["graded"].sl(D[c]) for c in CELLS]),
                     wins["graded"].labels)
    return headline_word(powered, res.pbo, g, d80) + (g, res.pbo)


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def pct(x: float) -> str:
    return f"{x:+.2%}" if x == x else "n/a"


def fmt_ci3(t: tuple) -> str:
    return f"{pct(t[0])} [{pct(t[1])}, {pct(t[2])}]"


def run_in_sample(inp_full: Inputs, n_paths: int = GK_PATHS, boot_n: int = BOOT_N,
                  boot=bootstrap_draws, best_month: bool = True) -> dict:
    """Everything graded. GE reads the uncut files; every series is then cut at
    IN_SAMPLE_END before anything is computed."""
    section("GATES")
    for line in gate_dates(inp_full):
        print(line)
    inp = inp_full.cut(IN_SAMPLE_END)
    P = build_panel(inp)
    for line in gate_inputs(inp, P):
        print(line)
    gb_lines, flags = gate_basis(P, inp.divs)
    for line in gb_lines:
        print(line)
    M = months_from_panel(P)
    j0 = first_decision(M)
    if j0 is None:
        raise Refused(EXIT_INPUT, "GI: no month-end at which all 12 cells are defined. Exit 3.")
    graded_w, early_w, late_w = windows_of(M, j0)
    wins = {"graded": graded_w, "early": early_w, "late": late_w}
    print(f"  first common session {P.dates[0]}; first decision {P.dates[M.me[j0]]} (execution "
          f"{P.dates[M.me[j0] + 1]}); first graded month {graded_w.labels[0]}")
    tables = {c: decision_table(P, M, j0, c) for c in CELLS}
    for line in gate_lookahead(inp, P, M, j0, tables):
        print(line)
    print("  GX calendar: the last row of a cut series is never a decision close (pinned in tests)"
          "   PASS")
    print(f"  GC the cut: GE reads the uncut files; every series is cut at {IN_SAMPLE_END} before "
          f"anything else (pinned in tests)   PASS")
    W, r, turn = run_cells(M, j0, COST_BP)
    r_k9, _ = simulate_rule(M.B, M.A, ew_weights(M.L, j0), j0, COST_BP)
    G = np.vstack([np.full(NT, np.nan), P.adj[1:] / P.adj[:-1]])
    g_rule = daily_curve(G, tables[HEADLINE], COST_BP)
    ew_tab = {k: np.full(NT, 1.0 / NT) for k in tables[HEADLINE]}
    g_ew = daily_curve(G, ew_tab, COST_BP)
    chk = max(float(np.nanmax(np.abs(month_growth(g_rule, M.me, j0) - r[HEADLINE]))),
              float(np.nanmax(np.abs(month_growth(g_ew, M.me, j0) - r["EW-9"]))))
    for line in gate_replay(r_k9, r["EW-9"], graded_w):
        print(line)
    print(f"  daily curves vs month aggregates (printed drawdowns only): worst |monthly diff| "
          f"{chk:.1e}")

    section("GATE GK — calibration on null panels (no real-data statistic before it passes)")
    last_j = graded_w.hi - 1
    rb = real_basis(P, M, j0, last_j)
    print(f"  real panel: {len(rb.R)} daily returns {P.dates[1]} .. {P.dates[M.me[last_j]]}, "
          f"{rb.J} months (warm-up kept), mu_bar {rb.mu_bar:.6f} a day; {n_paths} paths per "
          f"generator, seed {SEED}; bootstrap {boot_n} draws")
    lab = M.labels[:last_j + 1]
    wins_null = {k: Window(w.name, w.lo, w.hi, w.labels) for k, w in wins.items()}
    nulls = [simulate_null(g, rb, n_paths) for g in ("G-IID", "G-GARCH", "G-MONTH")]
    token, gens = gate_calibration(nulls, wins_null, lab, BLOCK, boot_n, boot)
    gk_first = gens
    block = BLOCK
    if token is None:
        print(f"  GK REFUSED at block {BLOCK}; the one registered fallback re-runs every window and "
              f"delta80 at block {BLOCK_FALLBACK}")
        print_gk(gens, BLOCK)
        token, gens = gate_calibration(nulls, wins_null, lab, BLOCK_FALLBACK, boot_n, boot)
        block = BLOCK_FALLBACK
        if token is None:
            print_gk(gens, BLOCK_FALLBACK)
            raise Refused(EXIT_INPUT, f"GK: the 0 bp rejection rate exceeds {GK_BOUND} at block "
                                      f"{BLOCK} and at the fallback block {BLOCK_FALLBACK}. Exit 3.",
                          "gate")
    print_gk(gens, block)
    d80 = token.d80[COST_BP]
    print(f"  GK   PASS at block {block}. delta80 per generator: "
          + "  ".join(f"{g.name} {fmt_d80(g.d80[COST_BP])}" for g in gens)
          + f"; study delta80 {fmt_d80(d80)} vs REF {REF:.3f}")
    gm = simulate_null("G-MEANS", rb, n_paths, costs=(COST_BP,))
    gmeans_xs = float((12.0 * graded_w.sl(gm.r_rule[COST_BP] - gm.r_ew[COST_BP]).mean(axis=1)).mean())

    # ── real statistics: everything below holds the GK token ────────────────
    D = {c: graded_excess(r[c], r["EW-9"], token) for c in CELLS}
    D["SPY"] = None
    spy_g = np.concatenate([[np.nan], P.spy[1:] / P.spy[:-1]])
    spy_m = month_growth(spy_g, M.me, j0)
    tb_m = month_growth(1.0 + P.tb, M.me, j0)
    D["SPY"] = graded_excess(spy_m, r["EW-9"], token)
    powered = graded_w.n >= MIN_GRADED and early_w.n >= MIN_HALF and late_w.n >= MIN_HALF
    print(f"\n  GN floors: graded {graded_w.n} months (floor {MIN_GRADED}), early {early_w.n}, late "
          f"{late_w.n} (floor {MIN_HALF}) -> {'powered' if powered else 'UNDERPOWERED'}")

    out_w = {}
    curves = {**{c: (r[c], turn[c]) for c in CELLS}, "EW-9": (r["EW-9"], turn["EW-9"]),
              "SPY": (spy_m, np.zeros_like(spy_m))}
    daily = {**{c: daily_curve(G, tables[c], COST_BP) for c in CELLS if c != HEADLINE},
             HEADLINE: g_rule, "EW-9": g_ew, "SPY": spy_g}
    for nm, w in wins.items():
        section(f"{nm.upper()} WINDOW {w.labels[0]} to {w.labels[-1]} (N = {w.n})"
                + ("  decides the verdict" if nm == "graded" else "  sign check"))
        print(f"  XS = 12 x mean monthly excess over EW-9 (both net of their own costs); IR with "
              f"block-{block} CI; Sharpe on excess over T-bills")
        print(f"  {'curve':<9}{'XS':>8}{'CI95':>20}{'p':>8}{'IR':>7}{'IR CI95':>17}{'Sharpe':>7}"
              f"{'CAGR':>7}{'MDD':>7}{'dlyMDD':>7}{'turn':>6}{'hit':>5}  worst year")
        a0 = M.me[w.lo - 1] + 1 if w.lo > j0 + 1 else M.me[j0] + 2
        a1 = M.me[w.hi - 1]
        rows = {}
        for c in (HEADLINE,) + tuple(x for x in CELLS if x != HEADLINE) + ("EW-9", "SPY"):
            rc, tc = curves[c]
            dw = w.sl(D[c]) if c != "EW-9" else np.zeros(w.n)
            dr = xs_draws(dw, block, boot_n)
            ird = ir_draws(dw, block, boot_n) if c != "EW-9" else np.full(2, np.nan)
            xs = 12.0 * float(dw.mean())
            p = float(p_two_sided(dr)) if c != "EW-9" else 1.0
            lo, hi = ci(dr) if c != "EW-9" else (0.0, 0.0)
            ilo, ihi = ci(ird) if c != "EW-9" else (float("nan"), float("nan"))
            rw = w.sl(rc)
            yr = {}
            for m_, x in zip(w.labels, rw):
                yr.setdefault(m_[:4], []).append(x)
            yc = {y: float(np.prod(1 + np.array(v)) - 1) for y, v in yr.items()}
            wy = min(yc, key=yc.get)
            dd = mdd_daily(daily[c][a0:a1 + 1]) if c in daily else float("nan")
            rows[c] = (xs, lo, hi, p)
            print(f"  {c:<9}{xs:>+8.2%}  [{lo:+.2%}, {hi:+.2%}]{p:>8.4f}{ir(dw):>7.3f}  "
                  f"[{ilo:+.3f}, {ihi:+.3f}]{sharpe(rw - w.sl(tb_m)):>7.3f}{cagr(rw):>7.2%}"
                  f"{mdd(rw):>7.1%}{dd:>7.1%}{w.sl(tc).sum() * 12.0 / w.n:>6.2f}"
                  f"{float((dw > 0).mean()):>5.0%}  {wy} {yc[wy]:+.1%}"
                  f"{' (partial)' if len(yr[wy]) < 12 else ''}"
                  + ("" if c in (HEADLINE, "EW-9", "SPY") else "  (grid, not graded)"))
        out_w[nm] = rows
        print(f"  max drawdown, monthly: {HEADLINE} {mdd(w.sl(r[HEADLINE])):.1%}  EW-9 "
              f"{mdd(w.sl(r['EW-9'])):.1%}  difference {mdd(w.sl(r['EW-9'])) - mdd(w.sl(r[HEADLINE])):+.1%}"
              f" (EW-9 minus rule; printed, not graded)")

    g, gtab = graded_of(D[HEADLINE], wins, block, boot_n, token)
    section(f"HEADLINE DETAIL — {HEADLINE} on the graded window")
    gw = graded_w
    ex_r = gw.sl(r[HEADLINE]) - gw.sl(tb_m)
    beta = {}
    for nm, bench in (("EW-9", r["EW-9"]), ("SPY", spy_m)):
        a, ase, b, bse = nw_ols(ex_r, gw.sl(bench) - gw.sl(tb_m))
        beta[nm] = (a * 12.0, ase * 12.0, b, bse)
        print(f"  vs {nm}: alpha {a * 12.0:+.2%} a year (se {ase * 12.0:.2%}), beta {b:.3f} "
              f"(se {bse:.3f}); Newey-West, {NW_LAGS} lags")
    held = np.nanmean(W[HEADLINE][gw.lo - 1:gw.hi - 1] > 0, axis=0)
    print("  share of graded months each ETF was held: "
          + "  ".join(f"{t} {held[i]:.0%}" for i, t in enumerate(TICKERS)))
    ys = year_sums(gw.sl(D[HEADLINE]), gw.labels)
    print("  per calendar year, sum of d_m (printed only; grades nothing):")
    items = list(ys.items())
    for i in range(0, len(items), 6):
        print("    " + "  ".join(f"{y} {s:+.2%}{'*' if n < 12 else ''}" for y, (s, n) in items[i:i + 6]))
    npos = sum(1 for s, _ in ys.values() if s > 0)
    print(f"  years with sum d_m above 0: {npos} of {len(ys)} ({npos / len(ys):.0%}); null base "
          f"rate " + "  ".join(f"{x.name} {x.year_pos:.0%}" for x in token.gens)
          + "  (* partial year)")
    print(f"  hit rate {float((gw.sl(D[HEADLINE]) > 0).mean()):.1%}; null base rate "
          + "  ".join(f"{x.name} {x.hit:.1%}" for x in token.gens))
    print(f"  G-MEANS (G-MONTH with each ETF's real mean kept, {n_paths} paths, printed only): "
          f"mean XS at 5 bp {gmeans_xs:+.2%} beside the real XS {g.xs:+.2%}")

    bsm = None
    if best_month:
        bsm = best_sector_month(M, j0, gw, g_ew, token)
        i, m, xs_after = bsm
        share = f"; share of the original kept {xs_after / g.xs:.0%}" if g.xs > 0 else ""
        print(f"  best sector-month removed: {TICKERS[i]} {gw.labels[m]} replaced by EW-9's daily "
              f"returns, ranks recomputed: XS {g.xs:+.2%} -> {xs_after:+.2%}{share}")

    section("PBO / CSCV (12 cells, S=16, metric mean d_m, graded window)")
    Dm = np.column_stack([gw.sl(D[c]) for c in CELLS])
    res, dropped = run_pbo(Dm, gw.labels)
    if not math.isfinite(res.pbo):
        raise Refused(EXIT_INPUT, "PBO is not finite. Exit 3.", "PBO undefined")
    print(f"  rows {Dm.shape[0]} -> {res.n_rows} after trimming {len(dropped)} oldest months "
          f"({', '.join(dropped) if dropped else 'none'}); {res.n_combinations} splits")
    note = "veto" if res.pbo > PBO_VETO else "selection fragile" if res.pbo > PBO_FRAGILE else ""
    print(f"  PBO {res.pbo:.3f}  n_at_zero {res.n_at_zero}  {note}")
    best = np.bincount(res.n_star, minlength=len(CELLS))
    print("  in-sample best cell, share of splits: "
          + "  ".join(f"{c} {best[i] / res.n_combinations:.0%}" for i, c in enumerate(CELLS) if best[i]))
    print("  With 12 cells, noise gives a PBO near 0.50. PBO never selects a cell.")

    word, notes = headline_word(powered, res.pbo, g, d80)

    section("WORDS BY THE SAME ROWS (printed only)")
    print("  Grid cells (grid, not graded; the headline's PBO and delta80):")
    for c in CELLS:
        if c == HEADLINE:
            continue
        gc, _ = graded_of(D[c], wins, block, boot_n, token)
        wd, nt = headline_word(powered, res.pbo, gc, d80)
        print(f"    {c:<8} XS {gc.xs:+.2%} p {gc.p:.4f} early {gc.xs_early:+.2%} late "
              f"{gc.xs_late:+.2%} -> {wd}{_notes(nt)}  (grid, not graded)")
    print(f"  Sensitivities for {HEADLINE} (printed only):")
    for cbp in COST_SENS:
        wd, nt, gs, pb = headline_from(M, j0, wins, cbp, block, boot_n, token, token.d80[cbp], powered)
        print(f"    cost {cbp:>4.0f} bp (every cell and EW-9): XS {gs.xs:+.2%} p {gs.p:.4f} PBO "
              f"{pb:.3f} delta80 {fmt_d80(token.d80[cbp])} -> {wd}{_notes(nt)}  (printed only)")
    for blk in BLOCK_SENS:
        tk, gs_b = gate_calibration(nulls, wins_null, lab, blk, boot_n, boot, verbose=False,
                                    power_costs=(COST_BP,))
        d80b = max(x.d80[COST_BP] for x in gs_b)
        gb_, _ = graded_of(D[HEADLINE], wins, blk, boot_n, token)
        wd, nt = headline_word(powered, res.pbo, gb_, d80b)
        print(f"    block {blk:>2}: GK size " + " ".join(f"{x.name} {x.size:.3f}" for x in gs_b)
              + f"{'' if tk is not None else ' (GK would refuse)'}; XS {gb_.xs:+.2%} p {gb_.p:.4f} "
              f"delta80 {fmt_d80(d80b)} -> {wd}{_notes(nt)}  (printed only)")

    flag_lines, settled = [], []
    if flags:
        section("GB FLAGGED ROWS — the headline with each flagged rise removed")
        for f in flags:
            adj = P.adj.copy()
            i = TICKERS.index(f.ticker)
            adj[f.k:, i] = adj[f.k:, i] / (1.0 + f.step)
            Mf = months_from_panel(P, adj)
            wd, nt, gs, pb = headline_from(Mf, j0, wins, COST_BP, block, boot_n, token, d80, powered)
            line = (f"  {f.ticker} {P.dates[f.k]}: with the rise removed XS {gs.xs:+.2%} p "
                    f"{gs.p:.4f} PBO {pb:.3f} -> {wd}; as data -> {word}")
            print(line)
            flag_lines.append(line)
            settled.append((f"{f.ticker} {P.dates[f.k]}", wd))
        flag_refuse = settle_flags(word, settled)
        if flag_refuse:
            word, notes = headline_word(powered, res.pbo, g, d80, refused="gate")
            notes = [flag_refuse]
    return dict(word=word, notes=notes, g=g, gtab=gtab, pbo=res.pbo, d80=d80, token=token,
                gens=gens, gk_first=gk_first, block=block, beta=beta, bsm=bsm, gmeans=gmeans_xs,
                first=graded_w.labels[0], wins=wins, ir=(ir(gw.sl(D[HEADLINE])),
                                                         *ci(ir_draws(gw.sl(D[HEADLINE]), block, boot_n))),
                mdd=(mdd(gw.sl(r[HEADLINE])), mdd(gw.sl(r["EW-9"]))), flags=flag_lines,
                months=M.labels, rows=out_w)


def settle_flags(word: str, settled: list[tuple[str, str]]) -> str | None:
    """GB flagged rows: when any row's removed-rise word differs from the word on the data
    as printed, the verdict is REFUSED (gate) with that row named."""
    for row, wd in settled:
        if wd != word:
            return f"gate: GB-flagged row {row} changes the word ({word} -> {wd})"
    return None


def best_sector_month(M: Months, j0: int, gw: Window, g_ew: np.ndarray, token: GKPass
                      ) -> tuple[int, int, float]:
    """For each sector i and graded month m, both arms are recomputed with sector i's daily
    returns in month m replaced by EW-9's daily returns in that month, ranks recomputed.
    Returns (sector, month offset in the window, graded XS after the replacement) for the
    replacement that lowers XS most. In the first graded month the execution session
    precedes the curve's start, so EW-9 has no return there and the sector keeps its own."""
    _require(token)
    best = (0, 0, float("inf"))
    js = np.arange(gw.lo, gw.hi)
    nm = len(js)
    for i in range(NT):
        B = np.broadcast_to(M.B, (nm,) + M.B.shape).copy()
        A = np.broadcast_to(M.A, (nm,) + M.A.shape).copy()
        for q, j in enumerate(js):
            f, last = M.me[j - 1] + 1, M.me[j]
            if j > j0 + 1:
                B[q, j, i] = g_ew[f]
            A[q, j, i] = float(np.prod(g_ew[f + 1:last + 1]))
        L = M.L[None].repeat(nm, axis=0)
        mg = B[:, :, i] * A[:, :, i]
        mg[:, 0] = 1.0
        L[:, :, i] = M.L[0, i] * np.cumprod(mg, axis=1)
        W = rule_weights(L, HEADLINE, j0)
        rr, _ = simulate_rule(B, A, W, j0, COST_BP)
        re_, _ = simulate_ew(B, A, j0, COST_BP)
        xs = 12.0 * gw.sl(graded_excess(rr, re_, token)).mean(axis=1)
        q = int(np.argmin(xs))
        if xs[q] < best[2]:
            best = (i, q, float(xs[q]))
    return best


# ════════════════════════════════════════════════════════════════════════════
# Forward
# ════════════════════════════════════════════════════════════════════════════

def report_forward(inp: Inputs, out: dict | None, boot_n: int = BOOT_N,
                   today: str | None = None) -> str:
    section(f"FORWARD — {HEADLINE} vs EW-9, {FORWARD[0]} to {FORWARD[1]} (one shot, sunset {SUNSET})")
    today = today or date.today().isoformat()
    P = build_panel(inp)
    me = month_end_idx(P.dates)
    n = len({P.dates[k][:7] for k in me if FORWARD[0] <= P.dates[k][:7] <= FORWARD[1]})
    print(f"  data to {P.dates[-1]}; complete forward months: {n} of {FORWARD_MONTHS}")
    if not any(d > FORWARD_AFTER for d in P.dates):
        if today > SUNSET:
            print(f"  the sunset {SUNSET} has passed with no read; nothing is concluded")
            return "LAPSED"
        word = f"STILL-OPEN ({n} complete forward months)"
        print(f"  {word}. The read fires once, on the first run whose cache holds a session after "
              f"{FORWARD_AFTER}.")
        return word
    end = next(d for d in P.dates if d > FORWARD_AFTER)
    Pf = build_panel(inp.cut(end))
    try:
        gate_inputs(inp.cut(end), Pf, end)
        gate_basis(Pf, inp.divs)
    except Refused as exc:
        print(f"  {exc.message}")
        return "REFUSED (forward data gate)"
    M = months_from_panel(Pf)
    j0 = first_decision(M)
    W = rule_weights(M.L, HEADLINE, j0)
    rr, _ = simulate_rule(M.B, M.A, W, j0, COST_BP)
    re_, _ = simulate_ew(M.B, M.A, j0, COST_BP)
    w = make_window(M, j0, "forward", *FORWARD)
    d = w.sl(rr - re_)
    xs = 12.0 * float(d.mean())
    lo, hi = ci(xs_draws(d, 6, boot_n))
    word = forward_word(xs)
    null = ("  ".join(f"{g.name} {g.fwd_pos:.0%}" for g in out["gens"]) if out else "n/a")
    print(f"  forward months {w.labels[0]} .. {w.labels[-1]} (N = {w.n}): XS {xs:+.2%} "
          f"[{lo:+.2%}, {hi:+.2%}] (block-6 CI) -> {word}; null share of 36-month windows above 0: "
          f"{null}")
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


def file_line(p: Path) -> str:
    rows, first, last = 0, "", ""
    with p.open(newline="") as fh:
        for r in csv.DictReader(fh):
            d = (r.get("date") or "")[:10]
            rows += 1
            first = first or d
            last = d
    sha = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    rel = p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
    return f"  input {rel}: {first} .. {last}, {rows} rows, sha256 {sha}"


def print_verdict(out: dict | None, fwd: str, refused: str | None = None) -> None:
    section("VERDICT")
    if refused is not None:
        print(f">>> {NAME} HEADLINE ({HEADLINE} vs EW-9, pooled 2000-01 to {GRADED_LAST}, 5 bp): "
              f"REFUSED ({refused}) <<<")
        return
    g, t = out["g"], out["gtab"]
    first = out["first"]
    print(f">>> {NAME} HEADLINE ({HEADLINE} vs EW-9, pooled {first} to {GRADED_LAST}, 5 bp): "
          f"{out['word']}{_notes(out['notes'])} <<<")
    gr = t["graded"]
    irr = out["ir"]
    print(f">>> {NAME} POOLED ({first} to {GRADED_LAST}): XS {pct(gr[0])} [{pct(gr[1])}, "
          f"{pct(gr[2])}] p {gr[3]:.4f} IR {irr[0]:+.3f} [{irr[1]:+.3f}, {irr[2]:+.3f}] <<<")
    e, l_ = t["early"], t["late"]
    print(f">>> {NAME} HALVES (sign checks): {first} to {EARLY_LAST} XS {pct(e[0])} [{pct(e[1])}, "
          f"{pct(e[2])}]; {LATE_FIRST} to {GRADED_LAST} XS {pct(l_[0])} [{pct(l_[1])}, {pct(l_[2])}] <<<")
    gens = out["gens"]
    print(f">>> {NAME} CALIBRATION (0 bp size, block {out['block']}, bound {GK_BOUND}): "
          + " ".join(f"{x.name} {x.size:.3f}" for x in gens) + " <<<")
    print(f">>> {NAME} POWER (delta80 {fmt_d80(out['d80'])} vs REF {REF:.3f}; BEATS-EW "
          f"false-positive {out['token'].fp_beats():.3f}) <<<")
    pb = out["pbo"]
    pn = " (selection fragile)" if PBO_FRAGILE < pb <= PBO_VETO else ""
    print(f">>> {NAME} PBO (12 cells, S=16, metric mean d_m, in-sample): {pb:.3f}{pn} <<<")
    print(f">>> {NAME} FORWARD ({HEADLINE} vs EW-9, {FORWARD[0]} to {FORWARD[1]}, sunset {SUNSET}): "
          f"{fwd} <<<")
    be = out["beta"]
    md = out["mdd"]
    print(f"  beside the word: max drawdown {HEADLINE} {md[0]:.1%}, EW-9 {md[1]:.1%}; alpha/beta vs "
          f"EW-9 {be['EW-9'][0]:+.2%}/{be['EW-9'][2]:.2f}, vs SPY {be['SPY'][0]:+.2%}/"
          f"{be['SPY'][2]:.2f}; G-MEANS mean XS {out['gmeans']:+.2%}")
    if out["bsm"] is not None:
        i, m, xa = out["bsm"]
        sh = f", {xa / g.xs:.0%} of the original" if g.xs > 0 else ""
        print(f"  best sector-month removed: {TICKERS[i]} {out['wins']['graded'].labels[m]}: XS "
              f"{xa:+.2%}{sh}")
    if out["word"] in ("NULL", "UNDERPOWERED-BY-DESIGN"):
        print(f"  {out['word']} means the test could not see one: delta80 {fmt_d80(out['d80'])} is "
              f"the smallest gain it would usually have seen. It never means no effect.")
    print("  The rule counts when graded p < 0.05, graded XS > 0 and both halves' XS > 0.")
    print(f"  Nothing ships from this study ({Path(REGISTRATION).name}).")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=NAME)
    ap.add_argument("--refresh", action="store_true", help="refetch the yfinance series")
    args = ap.parse_args(argv)
    print(f"{NAME} — does holding the three strongest SPDR sectors beat holding all nine?")
    print(f"  registration {REGISTRATION}")
    sha = _git("rev-parse", "--short", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    print(f"  git {sha or '?'} ({'dirty' if dirty else 'clean'} working tree)")
    print(f"  era: {HEADER_ERA}")
    print(f"  windows: graded from the first graded month (printed under GATES) to {GRADED_LAST}; "
          f"early half to {EARLY_LAST}; late half {LATE_FIRST} to {GRADED_LAST}; gap 2026-09 to "
          f"2026-11 (in no window); forward {FORWARD[0]} to {FORWARD[1]}; in-sample cut {IN_SAMPLE_END}")
    print(f"  seal: starts {era_mod.SEAL_START}; binds play signal dates; this study reads no "
          f"play, flow signal or backtest row")
    print(f"  money: {COST_BP:.0f} bp per side on both arms; bootstrap block {BLOCK}, {BOOT_N} "
          f"draws, seed {SEED}; GK {GK_PATHS} paths per generator, bound {GK_BOUND}; REF {REF}")
    try:
        check_era()
        inp = load_inputs(args.refresh)
        for p in sorted(CACHE_DIR.glob("*.csv")):
            print(file_line(p))
        if IRX_TREND_OVERLAY.exists():
            print(file_line(IRX_TREND_OVERLAY) + " (GI cross-check only)")
        out = run_in_sample(inp)
    except Refused as exc:
        print(f"\nREFUSED — {exc.message}")
        print_verdict(None, "", refused=exc.reason)
        return exc.code
    if out["word"].startswith("REFUSED"):
        print(f"\nREFUSED — {'; '.join(out['notes'])}")
        print_verdict(None, "", refused="; ".join(out["notes"]) or "gate")
        return EXIT_INPUT
    fwd = report_forward(inp, out)
    print_verdict(out, fwd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
