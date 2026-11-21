"""trend_overlay — does a slow trend rule cut drawdown, and at what cost?

REGISTRATION: research/pre-registrations/f4_deployment/trend_overlay.md (accepted by
default 2026-11-21). Every constant, floor, seed, window and verdict word below is that
file's. Read it before changing anything here.

WHAT IT ASKS
------------
A   On a 1x long S&P 500 position, does switching to cash while ^GSPC is below its
    trend cut the maximum drawdown, and what does it cost in return? Headline rule
    T-10M (Faber's 10-month SMA, month-end), with T-200D and T-12M printed beside it.
    Discovery 1993-02-01 to 2026-09-22 on SPY total return; holdout 1950-01-03 to
    1992-12-31 on ^GSPC price only. Graded separately.
B   On the account_sim book (v4, pre-seal), does cutting the net cap from 2.50 to 1.00
    on entries while T-10M is OUT cut the book's drawdown? In-sample, secondary.

It is a payoff-shape test, not a forecast test: earlier trend tests in this repo
(regime_confirm RC-200, state_map C6 and Q3, the 2026-10-29 label review) asked whether
a trend break forecasts returns and were all null.

DATA
----
yfinance, auto_adjust=False, cached in backtests/trend_overlay/<NAME>.csv (date, close,
adj_close) for ^GSPC (from 1948), SPY and ^IRX. Today's bar is never fetched (yfinance's
`end` is exclusive). `--refresh` refetches. No close after 2026-09-22 enters the
in-sample run; the forward read opens 2026-11-21 and closes at the 2029-11-21 sunset.

Population B calls account_sim.simulate in this process and never runs account_sim.main,
so it writes no account_sim report, CSV or page (gate GA proves it).

Nothing ships from this study. Run:

    python -m scripts.backtest_study run trend_overlay
    python -m scripts.backtest_study run trend_overlay -- --refresh
"""
from __future__ import annotations

import argparse
import bisect
import contextlib
import csv
import hashlib
import io
import math
import random
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib.path_bootstrap import _resample_indices  # noqa: E402

REGISTRATION = "research/pre-registrations/f4_deployment/trend_overlay.md"
CACHE_DIR = ROOT / "backtests" / "trend_overlay"
SERIES = {
    "GSPC": ("^GSPC", "1948-01-01"),
    "SPY": ("SPY", "1993-01-01"),
    "IRX": ("^IRX", "1960-01-01"),
}

IN_SAMPLE_END = "2026-09-22"
FORWARD_START = "2026-11-21"
SUNSET = "2029-11-21"
GSPC_FIRST = "1948-01-02"
DISCOVERY = ("1993-02-01", IN_SAMPLE_END)
HOLDOUT = ("1950-01-03", "1992-12-31")

RULES = ("T-10M", "T-200D", "T-12M")
HEADLINE = "T-10M"
SMA_DAYS = 200
SMA_MONTHS = 10
MOM_MONTHS = 12

COST_BP = 10.0
COST_SENS = (0.0, 25.0)
WHIPSAW_N = 63
EPISODE_DD = 0.20
CAGR_LIMIT = -0.02           # points a year, as a fraction
BLOCK = 252
BLOCK_SENS = (63, 504)
BOOT_N = 5_000
SEED = 20261121
PBO_S = 16
MIN_EPISODES = 2
FWD_MDD_MARGIN = 0.05
TRADING_DAYS = 252

B_NET_OUT = 1.00
B_MIN_DATES = 20
B_MIN_SPELLS = 2
B_BLOCK = 10

GB_RATIO_FALL = 1e-4         # SPY adj/close may only rise (dividends), 0.01% slack
GB_RATIO_STEP = 0.02         # and never moves more than 2% in one session
GB_SPY_GSPC = 0.03           # SPY close within 3% of ^GSPC / 10
GX_SAMPLES = 60

EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH        # 3
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
    """yfinance -> `backtests/trend_overlay/<name>.csv`. `end` is exclusive."""
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


def load_inputs(refresh: bool = False) -> dict[str, Series]:
    out = {}
    for name in SERIES:
        p = _cache_path(name)
        if refresh or not p.exists():
            fetch_series(name)
        rows = read_series(p)
        if not rows:
            raise Refused(EXIT_INPUT, f"GE: {p.relative_to(ROOT)} is empty. Exit 3.")
        out[name] = to_series(rows)
    return out


# ════════════════════════════════════════════════════════════════════════════
# The rules — decision closes and states
# ════════════════════════════════════════════════════════════════════════════

def month_end_idx(dates: list[str]) -> list[int]:
    """Indices of the last session of each calendar month. The last session of the
    series is never one: whether it ends its month is known only from the next session."""
    return [i for i in range(len(dates) - 1) if dates[i][:7] != dates[i + 1][:7]]


def decisions(sig: Series, rule: str) -> tuple[list[str], list[bool]]:
    """(decision dates, IN state at each) for `rule` on the signal series. A decision
    reads only closes on or before its own date. Ties are OUT."""
    c = sig.close
    d = sig.dates
    if rule == "T-200D":
        if len(c) < SMA_DAYS:
            return [], []
        cs = np.concatenate([[0.0], np.cumsum(c)])
        idx = list(range(SMA_DAYS - 1, len(c)))
        states = [bool(c[i] > (cs[i + 1] - cs[i + 1 - SMA_DAYS]) / SMA_DAYS) for i in idx]
        return [d[i] for i in idx], states
    me = month_end_idx(d)
    mc = c[me]
    if rule == "T-10M":
        js = range(SMA_MONTHS - 1, len(me))
        states = [bool(mc[j] > mc[j - SMA_MONTHS + 1:j + 1].mean()) for j in js]
    elif rule == "T-12M":
        js = range(MOM_MONTHS, len(me))
        states = [bool(mc[j] > mc[j - MOM_MONTHS]) for j in js]
    else:
        raise ValueError(f"unknown rule {rule!r}")
    return [d[me[j]] for j in js], states


def exposure(ret_dates: list[str], dec_dates: list[str], dec_states: list[bool]) -> np.ndarray:
    """IN (1.0) / OUT (0.0) / undefined (NaN) for each return-calendar session `k`.

    A decision at close `t` executes at the next session's close, so the first return
    earned at the new state is the one after the execution session. The exposure for
    session `k` is therefore the state of the latest decision dated strictly before the
    date of session `k - 1`: it reads no close after `k - 2`."""
    out = np.full(len(ret_dates), np.nan)
    for k in range(1, len(ret_dates)):
        j = bisect.bisect_left(dec_dates, ret_dates[k - 1]) - 1
        if j >= 0:
            out[k] = 1.0 if dec_states[j] else 0.0
    return out


# ════════════════════════════════════════════════════════════════════════════
# Curves and metrics
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Window:
    name: str
    dates: list[str]           # window sessions
    r: np.ndarray              # long session return
    cash: np.ndarray           # T-bill cash return per session (sensitivity)
    expo: dict                 # rule -> exposure array over the window sessions
    nxt: dict                  # rule -> exposure of the session after each window session (NaN past end)


def build_window(name: str, ret: Series, use_adj: bool, sig: Series, irx: Series,
                 start: str, end: str) -> Window:
    prices = ret.adj if use_adj else ret.close
    i0 = bisect.bisect_left(ret.dates, start)
    i1 = bisect.bisect_right(ret.dates, end)
    if i0 < 1:
        raise Refused(EXIT_INPUT, f"GE: {name} has no close before {start}. Exit 3.")
    r = prices[i0:i1] / prices[i0 - 1:i1 - 1] - 1.0
    irx_map = dict(zip(irx.dates, irx.close))
    cash = np.array([irx_map.get(d, 0.0) / 100.0 / TRADING_DAYS for d in ret.dates[i0:i1]])
    expo, nxt = {}, {}
    for rule in RULES:
        dd, ss = decisions(sig, rule)
        e = exposure(ret.dates, dd, ss)
        expo[rule] = e[i0:i1]
        nx = np.full(i1 - i0, np.nan)
        nx[:-1] = e[i0 + 1:i1]
        if i1 < len(ret.dates):
            nx[-1] = e[i1]
        # A change executed at the window's last close is outside the window: its cost
        # and its new state belong to sessions the window does not hold.
        nx[-1] = np.nan
        nxt[rule] = nx
    return Window(name, ret.dates[i0:i1], r, cash, expo, nxt)


def overlay_growth(w: Window, rule: str, cost_bp: float = COST_BP,
                   tbill: bool = False) -> np.ndarray:
    """Per-session growth factors of the overlay: the long return while IN, cash while
    OUT, times (1 - cost) on a session whose close executes a change of state."""
    e = w.expo[rule]
    if np.isnan(e).any():
        raise Refused(EXIT_INPUT, f"GE: {rule} is undefined inside {w.name}. Exit 3.")
    cash = w.cash if tbill else np.zeros_like(w.r)
    g = np.where(e > 0.5, 1.0 + w.r, 1.0 + cash)
    nx = w.nxt[rule]
    switch = (~np.isnan(nx)) & (nx != e)
    return g * np.where(switch, 1.0 - cost_bp / 1e4, 1.0)


def switch_mask(w: Window, rule: str) -> np.ndarray:
    nx = w.nxt[rule]
    return (~np.isnan(nx)) & (nx != w.expo[rule])


def drawdown_path(g: np.ndarray) -> np.ndarray:
    eq = np.cumprod(g)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return 1.0 - eq / peak


def mdd(g: np.ndarray) -> float:
    return float(drawdown_path(g).max()) if len(g) else 0.0


def cagr(g: np.ndarray) -> float:
    if not len(g):
        return float("nan")
    return float(np.exp(np.log(g).sum() * TRADING_DAYS / len(g)) - 1.0)


def longest_run(mask: np.ndarray) -> int:
    best = cur = 0
    for m in mask:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best


@dataclass
class Metrics:
    mdd: float
    avg_dd: float
    cdar95: float
    tuw: float
    tuw_longest: int
    cagr: float
    calmar: float
    switches: int
    out_share: float
    end_equity: float


def metrics(g: np.ndarray, switches: int = 0, out_share: float = 0.0) -> Metrics:
    dd = drawdown_path(g)
    k = max(1, math.ceil(0.05 * len(dd)))
    worst = np.sort(dd)[-k:]
    m = float(dd.max())
    c = cagr(g)
    under = dd > 1e-12
    return Metrics(mdd=m, avg_dd=float(dd.mean()), cdar95=float(worst.mean()),
                   tuw=float(under.mean()), tuw_longest=longest_run(under), cagr=c,
                   calmar=(c / m) if m > 0 else float("inf"), switches=switches,
                   out_share=out_share, end_equity=float(np.prod(g)))


def rule_metrics(w: Window, rule: str, g: np.ndarray) -> Metrics:
    return metrics(g, int(switch_mask(w, rule).sum()), float((w.expo[rule] < 0.5).mean()))


# ── whipsaw and episodes ─────────────────────────────────────────────────────

@dataclass
class Spell:
    start: int                 # index of the exit's execution session (-1: OUT at window start)
    end: int | None            # index of the re-entry's execution session (None: open at end)
    cost: float                # ln(overlay growth) - ln(long growth) over start..end


def out_spells(w: Window, rule: str, g_ov: np.ndarray) -> list[Spell]:
    e, nx = w.expo[rule], w.nxt[rule]
    lr = np.log(g_ov) - np.log1p(w.r)
    spells: list[Spell] = []
    cur: int | None = -1 if e[0] < 0.5 else None
    for k in range(len(e)):
        if cur is None and e[k] > 0.5 and nx[k] == 0.0:
            cur = k
        elif cur is not None and e[k] < 0.5 and nx[k] == 1.0:
            s = max(cur, 0)
            spells.append(Spell(cur, k, float(lr[s:k + 1].sum())))
            cur = None
    if cur is not None:
        s = max(cur, 0)
        spells.append(Spell(cur, None, float(lr[s:].sum())))
    return spells


@dataclass
class Whipsaw:
    n_spells: int
    n_whipsaw: int
    cost: float                # summed log points, whipsaw spells
    cost_losing: float         # summed log points, losing whipsaw spells only
    per_year: float
    n_open_end: int
    n_open_start: int


def whipsaw(w: Window, rule: str, g_ov: np.ndarray) -> Whipsaw:
    sp = out_spells(w, rule, g_ov)
    closed = [s for s in sp if s.end is not None and s.start >= 0]
    ws = [s for s in closed if s.end - s.start <= WHIPSAW_N]
    tot = sum(s.cost for s in ws)
    return Whipsaw(n_spells=len(closed), n_whipsaw=len(ws), cost=tot,
                   cost_losing=sum(s.cost for s in ws if s.cost < 0),
                   per_year=tot * TRADING_DAYS / len(w.r),
                   n_open_end=sum(1 for s in sp if s.end is None),
                   n_open_start=sum(1 for s in sp if s.start < 0 and s.end is not None))


@dataclass
class Episode:
    peak: int                  # -1: the window's base close
    trough: int
    recovery: int | None       # None: not recovered by the window end
    depth: float
    ov_dd: float
    save_trough: float
    save_recovery: float


def episodes(g_long: np.ndarray, g_ov: np.ndarray) -> list[Episode]:
    """Drawdowns of the LONG curve of EPISODE_DD or more, peak to recovery."""
    eq = np.concatenate([[1.0], np.cumprod(g_long)])        # eq[0] = base close
    ov = np.concatenate([[1.0], np.cumprod(g_ov)])
    out: list[Episode] = []
    peak_i, peak_v = 0, 1.0
    trough_i, depth = None, 0.0
    n = len(eq)

    def close(rec):
        pk, tr = peak_i, trough_i
        end = rec if rec is not None else n - 1
        seg = ov[pk:end + 1]
        odd = float((1.0 - seg / np.maximum.accumulate(seg)).max())
        out.append(Episode(peak=pk - 1, trough=tr - 1,
                           recovery=(rec - 1) if rec is not None else None, depth=depth,
                           ov_dd=odd,
                           save_trough=float(np.log(ov[tr] / ov[pk]) - np.log(eq[tr] / eq[pk])),
                           save_recovery=float(np.log(ov[end] / ov[pk]) - np.log(eq[end] / eq[pk]))))

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


def outside_cost(g_long: np.ndarray, g_ov: np.ndarray, eps: list[Episode]) -> float:
    inside = np.zeros(len(g_long), dtype=bool)
    for e in eps:
        lo = e.peak + 1
        hi = (e.recovery if e.recovery is not None else len(g_long) - 1) + 1
        inside[lo:hi] = True
    lr = np.log(g_ov) - np.log(g_long)
    return float(lr[~inside].sum())


# ── bootstrap and PBO ────────────────────────────────────────────────────────

def boot_deltas(g_long: np.ndarray, arms: dict, block: int, n: int = BOOT_N,
                seed: int = SEED) -> dict:
    """Paired moving block bootstrap: per draw, the window's sessions are resampled in
    blocks (path_bootstrap._resample_indices) and every arm keeps its own session
    growth beside the long one. Returns arm -> (dMDD draws, dCAGR draws)."""
    rng = random.Random(seed)
    N = len(g_long)
    out = {a: (np.empty(n), np.empty(n)) for a in arms}
    for i in range(n):
        idx = np.fromiter(_resample_indices(N, block, rng), dtype=np.int64, count=N)
        gl = g_long[idx]
        ml, cl = mdd(gl), cagr(gl)
        for a, g in arms.items():
            go = g[idx]
            out[a][0][i] = ml - mdd(go)
            out[a][1][i] = cagr(go) - cl
    return out


def ci(draws: np.ndarray) -> tuple[float, float]:
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def calmar_log_metric(sub: np.ndarray) -> np.ndarray:
    """PBO metric: 252 x mean session log return over the rows / max fall of their
    cumulative log return (rows in the order given). Higher is better."""
    mean = sub.mean(axis=0) * TRADING_DAYS
    dd = PBO.max_drawdown(sub)
    return np.where(dd > 1e-12, mean / np.where(dd > 1e-12, dd, 1.0), np.inf * np.sign(mean))


def run_pbo(w: Window, cost_bp: float = COST_BP):
    M = np.column_stack([np.log(overlay_growth(w, r, cost_bp)) for r in RULES])
    M, pad = PBO.pad_head(M, PBO_S)
    return PBO.cscv(M, S=PBO_S, metric=calmar_log_metric), pad


# ════════════════════════════════════════════════════════════════════════════
# Verdicts
# ════════════════════════════════════════════════════════════════════════════

def verdict_a(n_episodes: int, d_mdd_lo: float, d_cagr: float, calmar_ov: float,
              calmar_long: float) -> str:
    if n_episodes < MIN_EPISODES:
        return "UNDERPOWERED"
    if d_mdd_lo <= 0:
        return "NO-DRAWDOWN-BENEFIT"
    if d_cagr < CAGR_LIMIT or calmar_ov <= calmar_long:
        return "TOO-COSTLY"
    if d_cagr < 0:
        return "CUTS-DRAWDOWN-AT-A-COST"
    return "CUTS-DRAWDOWN-NO-COST"


def agreement(disc: str, hold: str) -> str:
    if "UNDERPOWERED" in (disc, hold):
        return "NOT COMPARABLE"
    a, b = disc.startswith("CUTS-DRAWDOWN"), hold.startswith("CUTS-DRAWDOWN")
    return "AGREES" if a == b else "DISAGREES"


def pbo_reading(p: float) -> str:
    if p <= 0.25:
        return "supports a best-rule claim"
    if p <= 0.50:
        return "selection fragile"
    return "PBO veto"


def verdict_b(powered: bool, d_mdd_lo: float, d_dollars: float, d_mdd_point: float,
              inert: bool = False) -> str:
    if not powered:
        return "UNDERPOWERED"
    if inert:
        return "INERT"
    if d_mdd_lo <= 0:
        return "NO-BOOK-DRAWDOWN-BENEFIT"
    if -d_dollars > d_mdd_point:
        return "TOO-COSTLY"
    if d_dollars < 0:
        return "CUTS-BOOK-DRAWDOWN-AT-A-COST"
    return "CUTS-BOOK-DRAWDOWN-NO-COST"


def verdict_forward(have_episode: bool, mdd_long: float, mdd_ov: float, d_cagr: float) -> str:
    if not have_episode:
        return "NO-EPISODE"
    if mdd_long - mdd_ov >= FWD_MDD_MARGIN and d_cagr >= CAGR_LIMIT:
        return "CUTS-DRAWDOWN"
    return "NO-DRAWDOWN-BENEFIT"


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def gate_inputs(gspc: Series, spy: Series) -> list[str]:
    """GE. Returns the lines to print; raises Refused on a failure."""
    if not gspc.dates or gspc.dates[0] > GSPC_FIRST or gspc.dates[-1] < IN_SAMPLE_END:
        raise Refused(EXIT_INPUT, f"GE: ^GSPC must cover {GSPC_FIRST} to {IN_SAMPLE_END}; "
                                  f"has {gspc.dates[:1]} .. {gspc.dates[-1:]}. Exit 3.")
    if not spy.dates or spy.dates[0] >= DISCOVERY[0] or spy.dates[-1] < IN_SAMPLE_END:
        raise Refused(EXIT_INPUT, f"GE: SPY must cover {DISCOVERY[0]} to {IN_SAMPLE_END}. Exit 3.")
    gset = set(gspc.dates)
    missing = [d for d in spy.dates if DISCOVERY[0] <= d <= IN_SAMPLE_END and d not in gset]
    if missing:
        raise Refused(EXIT_INPUT, f"GE: {len(missing)} SPY sessions have no ^GSPC close "
                                  f"(first {missing[:3]}). Exit 3.")
    if np.isnan(spy.adj[bisect.bisect_left(spy.dates, DISCOVERY[0]) - 1:]).any():
        raise Refused(EXIT_INPUT, "GE: SPY adjusted close has gaps in discovery. Exit 3.")
    return [f"  GE inputs: ^GSPC {gspc.dates[0]} .. {gspc.dates[-1]}, SPY {spy.dates[0]} .. "
            f"{spy.dates[-1]}; every SPY session has a ^GSPC close   PASS"]


def gate_basis(gspc: Series, spy: Series) -> list[str]:
    """GB. SPY adj/close only rises (0.01% slack) and never steps more than 2%; SPY close
    within 3% of ^GSPC / 10 on every common date."""
    ratio = spy.adj / spy.close
    ok = ~np.isnan(ratio)
    rr = ratio[ok]
    steps = rr[1:] / rr[:-1] - 1.0
    worst_fall = float(steps.min()) if len(steps) else 0.0
    worst_step = float(np.abs(steps).max()) if len(steps) else 0.0
    if worst_fall < -GB_RATIO_FALL or worst_step > GB_RATIO_STEP:
        raise Refused(EXIT_INPUT, f"GB: SPY adj/close ratio step {worst_fall:+.5f} / "
                                  f"{worst_step:.5f} breaks the basis check. Exit 3.")
    gmap = dict(zip(gspc.dates, gspc.close))
    devs = [abs(c / (gmap[d] / 10.0) - 1.0) for d, c in zip(spy.dates, spy.close) if d in gmap]
    worst = max(devs) if devs else 0.0
    if worst > GB_SPY_GSPC:
        raise Refused(EXIT_INPUT, f"GB: SPY close is {worst:.2%} from ^GSPC/10 on some date "
                                  f"(limit {GB_SPY_GSPC:.0%}). Exit 3.")
    return [f"  GB basis: SPY adj/close worst fall {worst_fall:+.6f}, worst step {worst_step:.4f}; "
            f"SPY vs ^GSPC/10 worst {worst:.2%} on {len(devs)} dates   PASS"]


def gate_lookahead(sig: Series, ret_dates: list[str], start: str, end: str,
                   samples: int = GX_SAMPLES) -> list[str]:
    """GX at run time: for evenly spaced sessions k, every close after k - 2 is replaced
    by noise and the exposure at k must not move."""
    i0 = bisect.bisect_left(ret_dates, start)
    i1 = bisect.bisect_right(ret_dates, end)
    ks = np.linspace(i0, i1 - 1, samples).astype(int)
    base = {r: exposure(ret_dates, *decisions(sig, r)) for r in RULES}
    rng = np.random.default_rng(SEED)
    bad = 0
    for k in ks:
        cut_date = ret_dates[k - 2] if k >= 2 else ret_dates[0]
        j = bisect.bisect_right(sig.dates, cut_date)
        noisy = Series(sig.dates, sig.close.copy(), sig.adj.copy())
        noisy.close[j:] *= rng.uniform(0.5, 1.5, len(noisy.close) - j)
        for r in RULES:
            e = exposure(ret_dates, *decisions(noisy, r))
            a, b = base[r][k], e[k]
            if not ((np.isnan(a) and np.isnan(b)) or a == b):
                bad += 1
    if bad:
        raise Refused(1, f"GX: {bad} exposures moved when later closes changed. Exit 1.")
    return [f"  GX no lookahead: {len(ks)} sessions x {len(RULES)} rules re-run with every "
            f"close after k-2 replaced; 0 moved   PASS"]


def artifact_hashes() -> dict[str, str]:
    """GA's fingerprint of account_sim's report, CSV and page artifacts."""
    out = {}
    for pat_root, pat in ((ROOT / "backtests" / "study_output", "account_sim*"),
                          (ROOT / "site", "account_sim*.html")):
        if pat_root.exists():
            for p in sorted(pat_root.glob(pat)):
                if p.is_file():
                    out[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def pct(x: float) -> str:
    return f"{x:+.2%}" if x == x else "n/a"


def fmt_metrics_row(label: str, m: Metrics) -> str:
    cal = f"{m.calmar:6.3f}" if math.isfinite(m.calmar) else "   inf"
    return (f"  {label:<10}{m.mdd:>8.1%}{m.avg_dd:>8.1%}{m.cdar95:>8.1%}{m.tuw:>7.0%}"
            f"{m.tuw_longest:>7d}{m.cagr:>8.2%}{cal:>8}{m.switches:>6d}{m.out_share:>7.0%}")


METRIC_HEAD = (f"  {'curve':<10}{'MDD':>8}{'avgDD':>8}{'CDaR95':>8}{'TUW':>7}{'TUWmax':>7}"
               f"{'CAGR':>8}{'Calmar':>8}{'sw':>6}{'OUT':>7}")


@dataclass
class WindowResult:
    name: str
    words: dict                # rule -> word at the headline money
    d_mdd: dict                # rule -> (point, lo, hi)
    d_cagr: dict
    whip: dict
    n_episodes: int
    pbo: float


def report_window(w: Window, label: str, boot_n: int = BOOT_N) -> WindowResult:
    section(f"POPULATION A — {label}")
    g_long = 1.0 + w.r
    print(f"  sessions {w.dates[0]} .. {w.dates[-1]}  (N = {len(w.r)}); curves start at 1.0 at "
          f"the close before {w.dates[0]}")
    print(f"  headline money: {COST_BP:.0f} bp per switch, cash 0%. One-session execution lag.")
    m_long = metrics(g_long)
    arms = {r: overlay_growth(w, r) for r in RULES}
    ms = {r: rule_metrics(w, r, arms[r]) for r in RULES}
    print("\n  Metrics (MDD, average drawdown, CDaR95, time under water share and longest run in"
          "\n  sessions, CAGR, Calmar, switches, share of sessions OUT)")
    print(METRIC_HEAD)
    print(fmt_metrics_row("LONG", m_long))
    for r in RULES:
        print(fmt_metrics_row(r, ms[r]))
    yrs = len(w.r) / TRADING_DAYS
    print("  switches per year: " + "  ".join(f"{r} {ms[r].switches / yrs:.2f}" for r in RULES))

    eps = episodes(g_long, arms[HEADLINE])
    eps_in = [e for e in eps if e.peak >= 0]
    print(f"\n  Bear-market episodes (LONG falls {EPISODE_DD:.0%}+ from its running peak), "
          f"{HEADLINE} beside it:")
    print(f"  {'peak':<11}{'trough':<11}{'recovery':<11}{'LONG depth':>11}{'ovl DD':>8}"
          f"{'save pk>tr':>11}{'save pk>rec':>12}")
    for e in eps:
        pk = w.dates[e.peak] if e.peak >= 0 else "(base)"
        rc = w.dates[e.recovery] if e.recovery is not None else "(open)"
        print(f"  {pk:<11}{w.dates[e.trough]:<11}{rc:<11}{e.depth:>11.1%}{e.ov_dd:>8.1%}"
              f"{e.save_trough:>+11.3f}{e.save_recovery:>+12.3f}")
    apart = len(eps) - len(eps_in)
    print(f"  episodes counted: {len(eps_in)}  (peak before the window, counted apart: {apart})")
    print(f"  savings are overlay log return minus LONG log return; cost outside every episode: "
          f"{outside_cost(g_long, arms[HEADLINE], eps):+.3f} log points")
    for r in RULES:
        if r == HEADLINE:
            continue
        e2 = episodes(g_long, arms[r])
        print(f"  {r}: summed savings pk>tr {sum(x.save_trough for x in e2):+.3f}, pk>rec "
              f"{sum(x.save_recovery for x in e2):+.3f}; outside {outside_cost(g_long, arms[r], e2):+.3f}")

    print(f"\n  Whipsaw (OUT spells re-entering within {WHIPSAW_N} sessions; log points vs LONG,"
          f" switch costs included)")
    whips = {}
    for r in RULES:
        wp = whipsaw(w, r, arms[r])
        whips[r] = wp
        print(f"  {r:<7} spells {wp.n_spells:>3}  whipsaws {wp.n_whipsaw:>3}  cost {wp.cost:+.3f}"
              f"  losing only {wp.cost_losing:+.3f}  per year {wp.per_year:+.4f}"
              f"  open at end {wp.n_open_end}  OUT at start {wp.n_open_start}")

    print(f"\n  Paired moving block bootstrap: block {BLOCK} sessions, {boot_n} draws, seed {SEED}."
          f"\n  A resampled path keeps each session's realised exposure: it measures the noise in"
          f"\n  one drawdown figure, not a new test of the rule.")
    bd = boot_deltas(g_long, arms, BLOCK, boot_n)
    d_mdd, d_cagr, words = {}, {}, {}
    print(f"  {'rule':<8}{'dMDD':>8}{'CI95':>20}{'dCAGR':>9}{'CI95':>22}  word")
    for r in RULES:
        dm = m_long.mdd - ms[r].mdd
        dc = ms[r].cagr - m_long.cagr
        lo, hi = ci(bd[r][0])
        clo, chi = ci(bd[r][1])
        d_mdd[r], d_cagr[r] = (dm, lo, hi), (dc, clo, chi)
        words[r] = verdict_a(len(eps_in), lo, dc, ms[r].calmar, m_long.calmar)
        tag = "" if r == HEADLINE else "  (secondary, not graded)"
        print(f"  {r:<8}{dm:>+8.3f}  [{lo:+.3f}, {hi:+.3f}]{dc:>+9.4f}  [{clo:+.4f}, {chi:+.4f}]"
              f"  {words[r]}{tag}")

    print(f"\n  Sensitivities for {HEADLINE} (printed only; the headline word is not re-graded)")
    for blk in BLOCK_SENS:
        b2 = boot_deltas(g_long, {HEADLINE: arms[HEADLINE]}, blk, boot_n)
        lo, hi = ci(b2[HEADLINE][0])
        wd = verdict_a(len(eps_in), lo, d_cagr[HEADLINE][0], ms[HEADLINE].calmar, m_long.calmar)
        print(f"  block {blk:>3}: dMDD CI [{lo:+.3f}, {hi:+.3f}] -> {wd}  (printed only)")
    sens = [(f"cost {c:.0f} bp", c, False) for c in COST_SENS] + [("cash T-bill", COST_BP, True)]
    for lab, c, tb in sens:
        g = overlay_growth(w, HEADLINE, c, tb)
        gl = g_long
        m = rule_metrics(w, HEADLINE, g)
        b2 = boot_deltas(gl, {HEADLINE: g}, BLOCK, boot_n)
        lo, hi = ci(b2[HEADLINE][0])
        dc = m.cagr - m_long.cagr
        wd = verdict_a(len(eps_in), lo, dc, m.calmar, m_long.calmar)
        print(f"  {lab:<12} MDD {m.mdd:.1%}  CAGR {m.cagr:.2%}  dMDD {m_long.mdd - m.mdd:+.3f} "
              f"[{lo:+.3f}, {hi:+.3f}]  dCAGR {dc:+.4f}  -> {wd}  (printed only)")
    nz = int((w.cash > 0).sum())
    print(f"  T-bill cash: ^IRX on {nz} of {len(w.cash)} sessions; 0 where ^IRX has no close "
          f"(before 1960-01-04).")

    res, pad = run_pbo(w)
    print(f"\n  PBO / CSCV over {', '.join(RULES)}: S {PBO_S}, rows {res.n_rows} ({pad} zero rows "
          f"padded), {res.n_combinations} splits, metric Calmar on log returns")
    print(f"  PBO {res.pbo:.3f} -> {pbo_reading(res.pbo)}; n_at_zero {res.n_at_zero} (logit 0 counts"
          f" as overfit; pure noise over 3 rules gives about 0.67). It never changes the headline word.")
    best = np.bincount(res.n_star, minlength=len(RULES))
    print("  in-sample best rule, share of splits: "
          + "  ".join(f"{r} {best[i] / res.n_combinations:.0%}" for i, r in enumerate(RULES)))
    return WindowResult(label, words, d_mdd, d_cagr, whips, len(eps_in), res.pbo)


# ── Population B ─────────────────────────────────────────────────────────────

class SwitchCfg:
    """An account_sim `Cfg` whose net cap depends on the session's signal date.

    Every attribute but `net_cap` is the base `Cfg`'s. `today` is set by the ranker hook
    `simulate()` calls once per session before any admission, and the ranker returns the
    day's list unchanged, so who is chosen and in what order is the base run's."""

    def __init__(self, base, out_dates: set[str], cap_out: float):
        self._base = base
        self._out = out_dates
        self._cap_out = cap_out
        self.today: str | None = None

    def __getattr__(self, name):
        return getattr(self._base, name)

    @property
    def net_cap(self) -> float:
        return self._cap_out if self.today in self._out else self._base.net_cap

    def ranker(self, d, ranked, *_):
        self.today = str(d)
        return ranked


def b_switch_dates(day_lists, gspc_cut: Series) -> tuple[set[str], dict]:
    """Signal dates whose entry session follows a T-10M OUT month-end, and the OUT spell
    (index of its first OUT decision) each belongs to."""
    dd, ss = decisions(gspc_cut, HEADLINE)
    spell_of: dict[str, int] = {}
    spell_id = None
    first_out = {}
    for i, s in enumerate(ss):
        if not s:
            spell_id = spell_id if (i > 0 and not ss[i - 1]) else i
            first_out[i] = spell_id
    out: set[str] = set()
    for d, ranked in day_lists:
        k = ranked[0]["t"].grid[0]
        j = bisect.bisect_left(dd, str(k)[:10]) - 1
        if j >= 0 and not ss[j]:
            out.add(str(d))
            spell_of[str(d)] = first_out[j]
    return out, spell_of


def b_curve_stats(sim, capital: float, AS, MC) -> dict:
    sess, vals = AS.equity_curve(sim.signal_pos)
    mdd_r = AS.max_drawdown(vals)
    markable = []
    for p in sim.signal_pos:
        try:
            MC.position_marks(p)
        except (ValueError, KeyError, TypeError, IndexError):
            continue
        markable.append(p)
    bc = MC.book_curves(markable, target=MC.TARGET_POSITION)
    ps_r = MC.path_stats(bc.realized, capital)
    ps_m = MC.path_stats(bc.mtm, capital)
    return dict(n=len(sim.signal_pos), dollars=sim.dollars, mdd=mdd_r, sess=sess, vals=vals,
                ulcer_r=ps_r.ulcer, tuw_r=ps_r.tuw, mdd_m=ps_m.max_dd, ulcer_m=ps_m.ulcer,
                tuw_m=ps_m.tuw, n_mark=len(markable), net_refused=sim.census.get("net_delta", 0))


def weekday_axis(first, last) -> list:
    from datetime import timedelta
    out, d = [], first
    while d <= last:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def b_boot(c: dict, s: dict, first, block: int = B_BLOCK, n: int = BOOT_N, seed: int = SEED):
    """Paired block bootstrap of realised P&L on every weekday from the first entry to the
    last exit, 0 on a session with no exit."""
    from scripts.backtest_study.lib.mtm_curve import max_drawdown as mdd_dollars
    last = max(list(c["sess"]) + list(s["sess"]))
    axis = weekday_axis(first, last)
    cm = dict(zip(c["sess"], c["vals"]))
    sm = dict(zip(s["sess"], s["vals"]))
    a = np.array([cm.get(x, 0.0) for x in axis])
    b = np.array([sm.get(x, 0.0) for x in axis])
    rng = random.Random(seed)
    draws = np.empty(n)
    for i in range(n):
        idx = _resample_indices(len(axis), block, rng)
        draws[i] = abs(mdd_dollars(a[idx])) - abs(mdd_dollars(b[idx]))
    return ci(draws)


def b_gate(era: str):
    """`(payload, reason, code)`. load_book's era and thin-era refusals exit the process,
    so they are caught here and become a refusal line in the report."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            from scripts.backtest_study.lib.book import load_book
            recs, diag = load_book(era=era)
    except SystemExit as exc:
        lines = [x.strip() for x in buf.getvalue().splitlines() if x.strip()]
        reason = " ".join(x.replace("REFUSED — ", "") for x in lines) or "refused"
        return None, reason, int(exc.code or 0)
    return (recs, diag), None, None


def report_b(gspc_cut: Series, era: str, boot_n: int = BOOT_N) -> tuple[str, int | None]:
    section("POPULATION B — the account_sim book, net cap 2.50 -> 1.00 while T-10M is OUT")
    from scripts.backtest_study.f4_deployment import account_sim as AS
    from scripts.backtest_study.lib import mtm_curve as MC
    from scripts.backtest_study.lib import protocol as P

    before = artifact_hashes()
    payload, reason, code = b_gate(era)
    if payload is None:
        print(f"  B REFUSED ({reason})")
        return "REFUSED", code
    recs, diag = payload
    st = AS.load_settings(AS.DEFAULT_CONFIG)
    print(f"  era {diag.get('era', era)}; config {AS.DEFAULT_CONFIG.relative_to(ROOT)} unchanged; "
          f"capital ${st.capital:,.0f}, risk {st.risk_pct:.0%}, per-position cap {st.per_pos_cap:.2f}, "
          f"net cap {st.net_cap:.2f} (switch {B_NET_OUT:.2f})")
    seal = diag.get("seal")
    if seal:
        print(f"  seal: {era_mod.seal_line(seal)}")
    all_dates = {r["date"] for r in recs}
    print(f"  book: {len(recs)} records on {len(all_dates)} signal dates, "
          f"{min(all_dates)} .. {max(all_dates)}")
    verdict = "UNDERPOWERED"
    for label, dates_allowed in (("SECONDARY full book (headline)", all_dates),
                                 ("PRIMARY dense episodes (printed only)", None)):
        if dates_allowed is None:
            all_days = P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)
            eps = AS.dense_episodes((d for d, _ in all_days), max_gap=st.episode_max_gap,
                                    min_dates=st.episode_min_dates)
            dates_allowed = {d for ep in eps for d in ep}
        pop = [r for r in recs if r["date"] in dates_allowed]
        day_lists = P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible)
        out_dates, spell_of = b_switch_dates(day_lists, gspc_cut)
        n_spells = len(set(spell_of.values()))
        powered = len(out_dates) >= B_MIN_DATES and n_spells >= B_MIN_SPELLS
        cache = AS.new_cache()
        base = st.cfg("B-CONTROL")
        ctrl = AS.simulate(day_lists, base, cache=cache)
        null_cfg = SwitchCfg(st.cfg("B-SWITCH"), set(), B_NET_OUT)
        null = AS.simulate(day_lists, null_cfg, cache=cache, ranker=null_cfg.ranker)
        if AS.book_signature(null) != AS.book_signature(ctrl):
            raise Refused(EXIT_INPUT, "GW: the wrapper with no switched date changed the book. "
                                      "Exit 3.")
        print(f"\n  GW wrapper [{label}]: switch never firing reproduces B-CONTROL's "
              f"{len(ctrl.signal_pos)} positions exactly   PASS")
        sw_cfg = SwitchCfg(st.cfg("B-SWITCH"), out_dates, B_NET_OUT)
        sw = AS.simulate(day_lists, sw_cfg, cache=cache, ranker=sw_cfg.ranker)
        inert = AS.book_signature(sw) == AS.book_signature(ctrl)
        c = b_curve_stats(ctrl, st.capital, AS, MC)
        s = b_curve_stats(sw, st.capital, AS, MC)
        print(f"\n  [{label}]  signal dates {len(day_lists)}; under the switch {len(out_dates)} "
              f"in {n_spells} OUT spell(s)  (floor {B_MIN_DATES} dates in {B_MIN_SPELLS} spells)")
        if out_dates:
            print(f"  switched dates: {min(out_dates)} .. {max(out_dates)}")
        print(f"  {'arm':<11}{'pos':>5}{'net $':>11}{'maxDD $ (A3)':>14}{'of cap':>8}"
              f"{'ulcer':>7}{'TUW':>6}{'MTM maxDD $':>13}{'MTM ulcer':>10}{'net-cap refusals':>18}")
        for nm, x in (("B-CONTROL", c), ("B-SWITCH", s)):
            print(f"  {nm:<11}{x['n']:>5}{x['dollars']:>11,.0f}{x['mdd']:>14,.0f}"
                  f"{abs(x['mdd']) / st.capital:>8.1%}{x['ulcer_r']:>7.2f}{x['tuw_r']:>6.0%}"
                  f"{x['mdd_m']:>13,.0f}{x['ulcer_m']:>10.2f}{x['net_refused']:>18}")
        print(f"  marked positions: control {c['n_mark']}/{c['n']}, switch {s['n_mark']}/{s['n']}")
        d_mdd = abs(c["mdd"]) - abs(s["mdd"])
        d_dol = s["dollars"] - c["dollars"]
        if powered and inert:
            word = "INERT"
            print(f"  both arms took the same positions; d$ {d_dol:+,.0f} -> INERT")
        elif powered:
            first = min(p.entry_sess for p in ctrl.signal_pos + sw.signal_pos)
            lo, hi = b_boot(c, s, first, n=boot_n)
            word = verdict_b(True, lo, d_dol, d_mdd)
            print(f"  dMDD$ {d_mdd:+,.0f} [{lo:+,.0f}, {hi:+,.0f}] (block {B_BLOCK}, {boot_n} draws)"
                  f"  d$ {d_dol:+,.0f}  -> {word}")
        else:
            word = "UNDERPOWERED"
            print(f"  dMDD$ {d_mdd:+,.0f}  d$ {d_dol:+,.0f}  same positions: {inert}  -> "
                  f"UNDERPOWERED (census and figures printed, nothing concluded)")
        if label.startswith("SECONDARY"):
            verdict = word
    after = artifact_hashes()
    diff = sorted(set(before.items()) ^ set(after.items()))
    print(f"\n  GA artifacts: {len(before)} account_sim files hashed before and after; diff "
          f"{'empty' if not diff else diff}   {'PASS' if not diff else 'FAIL'}")
    if diff:
        raise Refused(EXIT_INPUT, "GA: account_sim artifacts changed during the run. Exit 3.")
    return verdict, None


# ── forward ──────────────────────────────────────────────────────────────────

def report_forward(gspc: Series, spy: Series, irx: Series, today: str) -> str:
    section(f"FORWARD — {HEADLINE} vs long SPY from {FORWARD_START} (one shot; sunset {SUNSET})")
    fwd = [d for d in spy.dates if d >= FORWARD_START]
    if not fwd:
        print(f"  forward sessions: 0 (data to {spy.dates[-1]}). STILL-OPEN.")
        return "STILL-OPEN"
    w = build_window("forward", spy, True, gspc, irx, fwd[0], spy.dates[-1])
    g_long = 1.0 + w.r
    g_ov = overlay_growth(w, HEADLINE)
    all_eps = [e for e in episodes(g_long, g_ov) if e.peak >= 0]
    eps = [e for e in all_eps if e.recovery is not None]
    sunset = today >= SUNSET
    print(f"  forward sessions {w.dates[0]} .. {w.dates[-1]} (N = {len(w.r)}); state at the first "
          f"session: {'IN' if w.expo[HEADLINE][0] > 0.5 else 'OUT'}")
    if not eps and not sunset:
        print("  no closed forward episode and the sunset has not come: STILL-OPEN "
              "(census only; no outcome printed)")
        return "STILL-OPEN"
    if eps:
        end = eps[0].recovery
        g_long, g_ov = g_long[:end + 1], g_ov[:end + 1]
    ml, mo = mdd(g_long), mdd(g_ov)
    dc = cagr(g_ov) - cagr(g_long)
    word = verdict_forward(bool(eps) or bool(all_eps), ml, mo, dc)
    wp = whipsaw(w, HEADLINE, overlay_growth(w, HEADLINE))
    print(f"  LONG MDD {ml:.1%}  overlay MDD {mo:.1%}  dCAGR {dc:+.4f}  whipsaw/yr {wp.per_year:+.4f}"
          f"  -> {word}")
    return word


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def run_in_sample(inp: dict[str, Series], boot_n: int = BOOT_N) -> dict:
    gspc = inp["GSPC"].cut(IN_SAMPLE_END)
    spy = inp["SPY"].cut(IN_SAMPLE_END)
    irx = inp["IRX"].cut(IN_SAMPLE_END)
    section("GATES")
    for line in gate_inputs(gspc, spy) + gate_basis(gspc, spy):
        print(line)
    for line in gate_lookahead(gspc, spy.dates, *DISCOVERY):
        print(line.replace("GX", "GX (discovery)"))
    for line in gate_lookahead(gspc, gspc.dates, *HOLDOUT):
        print(line.replace("GX", "GX (holdout)"))
    disc = build_window("discovery", spy, True, gspc, irx, *DISCOVERY)
    hold = build_window("holdout", gspc, False, gspc, irx, *HOLDOUT)
    rd = report_window(disc, f"DISCOVERY {DISCOVERY[0]} to {DISCOVERY[1]}, SPY total return",
                       boot_n)
    rh = report_window(hold, f"HOLDOUT {HOLDOUT[0]} to {HOLDOUT[1]}, ^GSPC price only", boot_n)
    return dict(disc=rd, hold=rh, gspc_cut=gspc)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="trend_overlay")
    ap.add_argument("--refresh", action="store_true", help="refetch the yfinance series")
    ap.add_argument("--boot-n", type=int, default=BOOT_N, help=argparse.SUPPRESS)
    ap.add_argument("--skip-b", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    era = era_mod.requested_era()
    today = date.today().isoformat()
    print("trend_overlay — does a slow trend rule cut drawdown, and at what cost?")
    print(f"  registration {REGISTRATION}")
    print("  era: current (inputs are unversioned market closes) for Population A; "
          f"{era} book for Population B")
    print(f"  windows: discovery {DISCOVERY[0]}..{DISCOVERY[1]}, holdout {HOLDOUT[0]}..{HOLDOUT[1]}, "
          f"gap 2026-09-23..2026-11-20 (in no population), forward from {FORWARD_START}, "
          f"sunset {SUNSET}")
    print(f"  seal: starts {era_mod.SEAL_START}; Population A reads no play row; Population B "
          f"loads the book with no sealed_read")
    try:
        inp = load_inputs(args.refresh)
        for name, s in inp.items():
            print(f"  input {_cache_path(name).relative_to(ROOT)}: {len(s.dates)} rows, "
                  f"{s.dates[0]} .. {s.dates[-1]} (in-sample reads to {IN_SAMPLE_END})")
        ins = run_in_sample(inp, args.boot_n)
    except Refused as exc:
        print(f"\nREFUSED — {exc.message}")
        return exc.code
    b_word, b_code = ("NOT RUN", None)
    if not args.skip_b:
        try:
            b_word, b_code = report_b(ins["gspc_cut"], era, args.boot_n)
        except Refused as exc:
            print(f"\nREFUSED — {exc.message}")
            return exc.code
    fwd = report_forward(inp["GSPC"], inp["SPY"], inp["IRX"], today)
    rd, rh = ins["disc"], ins["hold"]
    section("VERDICT")
    h = HEADLINE

    def line(r: WindowResult) -> str:
        dm, dc, wp = r.d_mdd[h], r.d_cagr[h], r.whip[h]
        return (f"dMDD {dm[0]:+.3f} [{dm[1]:+.3f}, {dm[2]:+.3f}]  dCAGR {dc[0]:+.4f} "
                f"[{dc[1]:+.4f}, {dc[2]:+.4f}]  whipsaw/yr {wp.per_year:+.4f}  "
                f"episodes {r.n_episodes}")
    print(f"  >>> trend_overlay A DISCOVERY (T-10M vs long SPY, {DISCOVERY[0]} to {DISCOVERY[1]}, "
          f"10 bp, cash 0%): {rd.words[h]} <<<")
    print(f"      {line(rd)}")
    print(f"  >>> trend_overlay A HOLDOUT (T-10M vs long ^GSPC price-only, {HOLDOUT[0]} to "
          f"{HOLDOUT[1]}, 10 bp, cash 0%): {rh.words[h]} <<<")
    print(f"      {line(rh)}")
    print(f"  >>> trend_overlay A AGREEMENT: {agreement(rd.words[h], rh.words[h])} <<<")
    sec = "  ".join(f"{r} {rd.words[r]}/{rh.words[r]}" for r in RULES if r != h)
    print(f"  >>> trend_overlay A SECONDARY (not graded): {sec} <<<")
    print(f"  >>> trend_overlay PBO: discovery {rd.pbo:.3f} holdout {rh.pbo:.3f} <<<")
    print(f"  >>> trend_overlay B (net cap 2.50 -> 1.00 while T-10M is OUT, v4 book to "
          f"{IN_SAMPLE_END}): {b_word} <<<")
    print(f"  >>> trend_overlay FORWARD (T-10M vs long SPY from {FORWARD_START}, sunset {SUNSET}): "
          f"{fwd} <<<")
    print("  CUTS-DRAWDOWN-* needs the dMDD CI above 0, dCAGR at or above -2.0 points a year and a "
          "Calmar above LONG's.")
    print(f"  Nothing ships from this study ({Path(REGISTRATION).name}).")
    return b_code or 0


if __name__ == "__main__":
    sys.exit(main())
