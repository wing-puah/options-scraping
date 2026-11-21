"""state_map — which market states come before SPY sell-offs, and is the confirmed bear state too late?

REGISTRATION: research/pre-registrations/f1_selection/regime/state_map.md (accepted by
default, commit d512219). Every constant, floor, seed, window and verdict word below is
that file's. Read it before changing anything here.

WHAT IT ASKS
------------
Q1  Days per mechanical state, run lengths, transitions. Descriptive.
Q2  Before an E-DD8 sell-off peak, is any of nine state variables (C1-C9) on more often
    than on matched calm days? Lift on a 10-session lead window; episodes are the unit.
Q3  Once the mech BEAR or E-VOL state prints, does SPY keep falling (ROOM-LEFT) or is the
    move done (TOO-LATE)? Entry at the next close; calendar-month clusters.
Q4  A fixed SPY put spread on each Q3 signal from 2022, at real cached prices. Prints
    AWAITING SCRAPE until every contract is cached. Descriptive, THIN-flagged.
Q5  The book's bear and bull rows by market state at entry. Descriptive.

DATA
----
yfinance, auto_adjust=False, cached in backtests/state_map/<NAME>.csv (date, close,
adj_close) for SPY, ^VIX, ^VIX3M, HYG and IEF. Today's bar is never fetched (yfinance's
`end` is exclusive). `--refresh` refetches. Q1-Q4 read unversioned market closes; Q5 reads
the book with the holdout seal applied. No close after 2026-09-22 enters the in-sample
run; the forward read opens 2026-11-21.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run state_map
    python -m scripts.backtest_study run state_map -- --refresh
"""
from __future__ import annotations

import argparse
import bisect
import contextlib
import csv
import io
import math
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import mech_regime as MR  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark.ticker_class import direction as tc_direction  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark.ticker_class import holm  # noqa: E402
from scripts.backtest_study.f1_selection.regime import tail_breach as TB  # noqa: E402
from scripts.backtest_study.f5_hedging import index_bear_hedge as IBH  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib.ruin_walk import wilson  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/state_map.md"
# The registration commit's stamp. The file's own date line is still blank.
REGISTERED = "2026-11-21"

# --- constants fixed by the registration -------------------------------------
IN_SAMPLE_END = "2026-09-22"         # no close after this enters the in-sample run
DISCOVERY_END = "2015-12-31"
TEST_START = "2016-01-01"
FORWARD_START = "2026-11-21"
FORWARD_ANCHOR_DATE = "2026-11-20"   # the last session before the forward window
GAP_START = "2026-09-23"             # the registration's gap line: first day after the in-sample cut
HEADLINE_DEF, SECONDARY_DEF = "E-DD8", "E-DD5"
LEAD_W = 10
LEAD_WS = (5, 10, 21)
ZONE_PAD = 21                        # exclusion zone: p - 21 to trough + 21
CONTROL_RANGE = 252
MIN_CONTROLS = 20
FLOOR = 10                           # Q2 episodes, Q3 clusters, Q4 trades, forward cells
Q5_MIN_ROWS, Q5_MIN_DATES = 20, 10
REARM = 10
REARM_ALT = 5
HORIZONS = (5, 10, 21)
BLOCK = 21                           # other-day bootstrap block, i // 21
BLOCK_SENS = 42
BOOT_N = 10_000
SEED = 20261121
ALPHA = 0.05
TURN_ON_FOLLOW = 21                  # TURN-ON: a trigger within this many sessions
C2_LINE = 0.80
C2_WINDOW = 252
C9_FLOOR = -0.01
C9_WINDOW = 20
RV_WINDOW = 21
TRADING_DAYS = 252
SMA_HEADLINE, SMA_LONG = MR.SMA_WINDOW, 200
PBO_YEARS = tuple(range(1995, 2027))     # T = 32, S = 16 blocks of two years
PBO_S = 16
PBO_VETO, PBO_FRAGILE = 0.50, 0.25
Q4_START = "2022-02-01"
Q4_DTE = 30
Q4_LONG_MULT, Q4_SHORT_MULT = 1.00, 0.95
GL_MAX_DISAGREE = 0.01
GX_SAMPLE = 60
GR_SKIP_SESSIONS = 63
BASIS_TOL = TB.BASIS_TOL

CANDS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9")
COIN_FAMILY = ("C1", "C2", "C3", "C4", "C8", "C9")
MECH_COIN = ("C5", "C6", "C7")
Q3_CELLS = (("B5", "S-BEAR", 5), ("B10", "S-BEAR", 10), ("B21", "S-BEAR", 21),
            ("V5", "S-EVOL", 5), ("V10", "S-EVOL", 10), ("V21", "S-EVOL", 21))
Q3_GRADED = ("S-BEAR", "S-EVOL")
Q3_PRINTED = ("S-BEAR200", "S-BOTH")
CAND_NAME = {
    "C1": "VIX >= 20", "C2": "VIX 252-session percentile >= 0.80", "C3": "VIX up >= 25% in 5 sessions",
    "C4": "VIX > VIX3M", "C5": "SPY < 50-day SMA", "C6": "SPY < 200-day SMA",
    "C7": "SPY < its close 20 sessions ago", "C8": "21-session realised vol > VIX",
    "C9": "HYG/IEF down > 1% in 20 sessions"}
BUCKETS = (("Low", -math.inf, 15.0), ("Mid", 15.0, 20.0), ("High", 20.0, 30.0), ("Extreme", 30.0, math.inf))
DIRS = ("BULL", "RANGE", "BEAR")
VOLS = ("L-VOL", "H-VOL", "E-VOL")
LAG_BINS = ("LIVE", "NEAR", "RETRO", "UNKNOWN")

LEADS, COINCIDENT, COINCIDENT_MECH = "LEADS", "COINCIDENT", "COINCIDENT (mechanical)"
NO_FORECAST, UNDERPOWERED, STILL_OPEN = "NO-FORECAST", "UNDERPOWERED", "STILL-OPEN"
ROOM_LEFT, TOO_LATE, NULL = "ROOM-LEFT", "TOO-LATE", "NULL"
AWAITING = "AWAITING SCRAPE"
RULE = "=" * 78

CACHE_DIR = ROOT / "backtests" / "state_map"
MECH_CSV = CACHE_DIR / "spy_vix_mech.csv"
BASE_RATE_CSV = ROOT / "backtests" / "mech_regime" / "spy_base_rate_daily.csv"
FULL_CSV = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"
WATCH_CSV = ROOT / "backtests" / "regime_watch" / "history.csv"
SERIES = {
    "SPY": ("SPY", "1993-01-01"),
    "VIX": ("^VIX", "1990-01-01"),
    "VIX3M": ("^VIX3M", "2006-01-01"),
    "HYG": ("HYG", "2007-01-01"),
    "IEF": ("IEF", "2002-01-01"),
}

# Exit 2: thin era (Q5). Exit 3: an input missing, a gate failed, or a wrong era (Q5).
# Exit 5: the episode definitions hash moved (GH), a real failure, as in index_bear_hedge.
EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH
EXIT_GHASH = IBH.EXIT_GHASH
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
    """yfinance -> `backtests/state_map/<name>.csv`. `end` is exclusive."""
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


read_series = TB.read_series        # (date, close, adj_close) rows, ascending


@dataclass
class Cal:
    """The SPY session calendar with the other four series aligned by exact date."""
    dates: list[str]
    close: np.ndarray          # unadjusted SPY close
    adj: np.ndarray            # dividend-adjusted SPY close (total return)
    vix: np.ndarray            # NaN where VIX has no close on that session
    vix3m: np.ndarray
    credit: np.ndarray         # HYG/IEF Adj Close ratio; NaN where either has no close
    pos: dict = field(default_factory=dict)

    def __post_init__(self):
        self.pos = {d: i for i, d in enumerate(self.dates)}

    @property
    def n(self) -> int:
        return len(self.dates)


def build_cal(spy: list[tuple], vix: dict, vix3m: dict, hyg: dict, ief: dict) -> Cal:
    """`hyg` and `ief` map date -> Adj Close. A session with no SPY adj close is dropped."""
    rows = [r for r in spy if r[2] is not None]
    nan = float("nan")

    def ratio(d):
        a, b = hyg.get(d), ief.get(d)
        return a / b if a is not None and b else nan

    return Cal(dates=[r[0] for r in rows],
               close=np.array([r[1] for r in rows], dtype=float),
               adj=np.array([r[2] for r in rows], dtype=float),
               vix=np.array([vix.get(r[0], nan) for r in rows], dtype=float),
               vix3m=np.array([vix3m.get(r[0], nan) for r in rows], dtype=float),
               credit=np.array([ratio(r[0]) for r in rows], dtype=float))


def cut_cal(cal: Cal, end: str) -> Cal:
    """Sessions on or before `end`. Everything in-sample is computed on this."""
    k = bisect.bisect_right(cal.dates, end)
    return Cal(cal.dates[:k], cal.close[:k].copy(), cal.adj[:k].copy(), cal.vix[:k].copy(),
               cal.vix3m[:k].copy(), cal.credit[:k].copy())


def idx_on_or_before(cal: Cal, d: str) -> int:
    """Index of the last session on or before `d`, or -1."""
    return bisect.bisect_right(cal.dates, d) - 1


def idx_from(cal: Cal, d: str) -> int:
    """Index of the first session on or after `d` (n when none)."""
    return bisect.bisect_left(cal.dates, d)


def window_codes(cal: Cal) -> np.ndarray:
    """0 discovery, 1 test, 2 gap, 3 forward, per session."""
    out = np.empty(cal.n, dtype=int)
    for i, d in enumerate(cal.dates):
        out[i] = 0 if d <= DISCOVERY_END else 1 if d <= IN_SAMPLE_END else 2 if d < FORWARD_START else 3
    return out


# ════════════════════════════════════════════════════════════════════════════
# The mechanical state. MechLabeler is read unchanged; BEAR200 needs a copy of
# `compute_mech_table` with the SMA length as a parameter (the registration says
# so). tests/test_state_map.py pins the copy at length 50 to MechLabeler.
# ════════════════════════════════════════════════════════════════════════════

def mech_table(dates, spy, vix, sma_window: int = SMA_HEADLINE) -> list[dict]:
    """`lib.mech_regime.compute_mech_table` on arrays, SMA length a parameter.

    Same thresholds (imported), same rows. `vix` may hold NaN for a missing close."""
    rows = [{"date": str(d), "spy": float(s), "vix": (None if v is None or v != v else float(v))}
            for d, s, v in zip(dates, spy, vix)]
    out = []
    for i, r in enumerate(rows):
        sma = None
        if i + 1 >= sma_window:
            window = [x["spy"] for x in rows[i + 1 - sma_window:i + 1]]
            sma = sum(window) / sma_window
        ret_n = None
        if i >= MR.RET_WINDOW:
            prior = rows[i - MR.RET_WINDOW]["spy"]
            if prior:
                ret_n = r["spy"] / prior - 1.0
        if sma is None or ret_n is None:
            direction = None
        elif r["spy"] < sma and ret_n < 0:
            direction = "BEAR"
        elif r["spy"] > sma and ret_n > 0:
            direction = "BULL"
        else:
            direction = "RANGE"
        v = r["vix"]
        if v is None:
            vol = None
        else:
            chg5 = None
            if i >= 5:
                prior_vix = rows[i - 5]["vix"]
                if prior_vix:
                    chg5 = v / prior_vix - 1.0
            if v >= MR.VIX_EVOL_LEVEL or (chg5 is not None and chg5 >= MR.VIX_EVOL_PCT):
                vol = "E-VOL"
            elif v >= MR.VIX_HVOL:
                vol = "H-VOL"
            else:
                vol = "L-VOL"
        out.append({"date": r["date"], "mech_direction": direction, "mech_vol": vol,
                    "dir_ok": sma is not None and ret_n is not None,
                    "spy_below_sma": (r["spy"] < sma) if sma is not None else None})
    return out


@dataclass
class Labels:
    """One state per session. `ok` is the label's `ok`: false means no state at all."""
    direction: list
    vol: list
    ok: np.ndarray

    @property
    def n(self) -> int:
        return len(self.direction)


def labels_from_table(table: list[dict]) -> Labels:
    d = [r["mech_direction"] if r["dir_ok"] else None for r in table]
    v = [r["mech_vol"] if r["dir_ok"] else None for r in table]
    return Labels(d, v, np.array([bool(r["dir_ok"]) for r in table], dtype=bool))


def write_mech_csv(cal: Cal, path: Path = MECH_CSV) -> Path:
    """`date, spy_close, vix_close`: the one input `MechLabeler.from_csv` reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "spy_close", "vix_close"])
        for d, c, v in zip(cal.dates, cal.close, cal.vix):
            w.writerow([d, repr(float(c)), "" if v != v else repr(float(v))])
    return path


def labels_from_labeler(path: Path, dates: list[str]) -> Labels:
    """Headline labels: `MechLabeler.from_csv(path)`, read per session date."""
    lab = MR.MechLabeler.from_csv(path)
    d, v, ok = [], [], []
    for day in dates:
        direction, vol, good, _ = lab.label(day)
        d.append(direction if good else None)
        v.append(vol if good else None)
        ok.append(bool(good))
    return Labels(d, v, np.array(ok, dtype=bool))


def mech_labels(cal: Cal, sma_window: int) -> Labels:
    return labels_from_table(mech_table(cal.dates, cal.close, cal.vix, sma_window))


def state_flags(lab50: Labels, lab200: Labels) -> dict:
    """`{signal: (holds, has_state)}`. A session has a state when its label's `ok` is true."""
    bear = np.array([x == "BEAR" for x in lab50.direction], dtype=bool)
    evol = np.array([x == "E-VOL" for x in lab50.vol], dtype=bool)
    bear200 = np.array([x == "BEAR" for x in lab200.direction], dtype=bool)
    return {"S-BEAR": (bear, lab50.ok), "S-EVOL": (evol, lab50.ok),
            "S-BEAR200": (bear200, lab200.ok), "S-BOTH": (bear & evol, lab50.ok)}


# ════════════════════════════════════════════════════════════════════════════
# Candidates C1-C9. Each reads closes on or before t, never later: every array
# is sliced to [:t + 1] before use (GX).
# ════════════════════════════════════════════════════════════════════════════

def _flag(cond: bool) -> float:
    return 1.0 if cond else 0.0


def cand_at(cal: Cal, t: int) -> dict:
    """C1-C9 at the close of session `t`: 1.0, 0.0 or NaN (too little history)."""
    upto = t + 1
    close, adj, vix = cal.close[:upto], cal.adj[:upto], cal.vix[:upto]
    vix3m, credit = cal.vix3m[:upto], cal.credit[:upto]
    out = {k: float("nan") for k in CANDS}
    v = float(vix[t])
    vfin = math.isfinite(v)
    if vfin:
        out["C1"] = _flag(v >= MR.VIX_HVOL)
        if t >= C2_WINDOW:
            win = vix[t - C2_WINDOW:t]
            if np.all(np.isfinite(win)):
                out["C2"] = _flag(TB.midrank_share(win, v) >= C2_LINE)
        if t >= 5 and math.isfinite(vix[t - 5]) and vix[t - 5]:
            out["C3"] = _flag(v / float(vix[t - 5]) - 1.0 >= MR.VIX_EVOL_PCT)
        v3 = float(vix3m[t])
        if math.isfinite(v3):
            out["C4"] = _flag(v > v3)
        if t >= RV_WINDOW:
            a = adj[t - RV_WINDOW:upto]
            r = np.log(a[1:] / a[:-1])
            if np.all(np.isfinite(r)):
                rv = math.sqrt(float(np.mean(r * r))) * math.sqrt(TRADING_DAYS) * 100.0
                out["C8"] = _flag(rv > v)
    c = float(close[t])
    if t + 1 >= SMA_HEADLINE:
        out["C5"] = _flag(c < sum(close[t + 1 - SMA_HEADLINE:upto].tolist()) / SMA_HEADLINE)
    if t + 1 >= SMA_LONG:
        out["C6"] = _flag(c < sum(close[t + 1 - SMA_LONG:upto].tolist()) / SMA_LONG)
    if t >= MR.RET_WINDOW:
        out["C7"] = _flag(c < float(close[t - MR.RET_WINDOW]))
    if t >= C9_WINDOW:
        a, b = float(credit[t]), float(credit[t - C9_WINDOW])
        if math.isfinite(a) and math.isfinite(b) and b:
            out["C9"] = _flag(round(a / b - 1.0, 9) < C9_FLOOR)
    return out


def cand_series(cal: Cal) -> dict:
    """`{k: array}` of `cand_at` over every session."""
    arrs = {k: np.full(cal.n, np.nan) for k in CANDS}
    for t in range(cal.n):
        for k, x in cand_at(cal, t).items():
            arrs[k][t] = x
    return arrs


# ════════════════════════════════════════════════════════════════════════════
# Episodes: index_bear_hedge's code, imported
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Ep:
    definition: str
    p: int                      # onset: the session of the 63-session high
    g: int                      # trigger: the first session at or below the trigger line
    trough: int
    closed: bool
    follow_on: bool = False
    win: int = 1                # window code of p
    end: int = -1               # last session of the episode (before the recovery, or 42 after the last trigger)


def ibh_series(cal: Cal):
    return IBH.Series(list(cal.dates), cal.close.tolist(),
                      [None if v != v else float(v) for v in cal.vix])


def build_episodes(cal: Cal, name: str, win: np.ndarray | None = None,
                   counter: Counter | None = None) -> list[Ep]:
    """Every episode of definition `name` on `cal`, merged, with `g` and the
    follow-on flag. Unclosed episodes are included and flagged `closed=False`. An
    episode with no trigger session is dropped and counted in `counter["no_trigger"]`."""
    s = ibh_series(cal)
    defs = IBH.EPISODE_DEFS[name]
    dd = IBH.drawdowns(s.spy, defs["lookback"])
    win = window_codes(cal) if win is None else win
    out = []
    for e in IBH.episodes(s, name):
        g = next((j for j in range(e.peak_i + 1, cal.n)
                  if dd[j] is not None and dd[j] <= defs["trigger"]), None)
        if g is None:
            if counter is not None:
                counter["no_trigger"] += 1
            continue
        r = next((j for j in range(e.trough_i + 1, cal.n)
                  if dd[j] is not None and dd[j] > defs["recover"]), None)
        stop = r if r is not None else cal.n
        last_trig = max([j for j in range(g, stop) if dd[j] is not None and dd[j] <= defs["trigger"]] or [g])
        end = max(e.trough_i, min(stop - 1, last_trig + defs["trough_max"]))
        out.append(Ep(name, e.peak_i, g, e.trough_i, bool(e.closed), False, int(win[e.peak_i]), end))
    out.sort(key=lambda x: x.p)
    mark_follow_ons(out, cal.n)
    return out


def zone_bounds(e: Ep, n: int) -> tuple[int, int]:
    """Sessions p - 21 to trough + 21. An unclosed episode's zone runs to the data end."""
    hi = n - 1 if not e.closed else min(n - 1, e.trough + ZONE_PAD)
    return max(0, e.p - ZONE_PAD), hi


def zone_mask(eps: list[Ep], n: int) -> np.ndarray:
    z = np.zeros(n, dtype=bool)
    for e in eps:
        lo, hi = zone_bounds(e, n)
        z[lo:hi + 1] = True
    return z


def mark_follow_ons(eps: list[Ep], n: int) -> None:
    """A follow-on's 10-session lead window touches an earlier episode's zone."""
    for i, e in enumerate(eps):
        e.follow_on = any(e.p - LEAD_W <= zone_bounds(x, n)[1] for x in eps[:i])


# ════════════════════════════════════════════════════════════════════════════
# Lift machinery
# ════════════════════════════════════════════════════════════════════════════

class Ctx:
    """Candidate arrays with prefix sums, the window codes and the calendar."""

    def __init__(self, cal: Cal, cands: dict, win: np.ndarray):
        self.cal, self.n, self.win, self.val = cal, cal.n, win, cands
        self.dc, self.oc = {}, {}
        for k, v in cands.items():
            fin = np.isfinite(v)
            self.dc[k] = np.concatenate([[0], np.cumsum(fin)])
            self.oc[k] = np.concatenate([[0], np.cumsum(np.where(fin, v, 0.0))])

    def share(self, k: str, a, b):
        """Share of sessions a..b (inclusive, arrays) on which `k` is on, and a validity mask."""
        a, b = np.asarray(a), np.asarray(b)
        inb = (a >= 0) & (b < self.n) & (b >= a)
        aa, bb = np.clip(a, 0, self.n - 1), np.clip(b, 0, self.n - 1)
        length = b - a + 1
        full = (self.dc[k][bb + 1] - self.dc[k][aa]) == length
        ok = inb & full
        on = self.oc[k][bb + 1] - self.oc[k][aa]
        return np.where(ok, on / np.maximum(length, 1), np.nan), ok


def zone_any(zone: np.ndarray, a, b) -> np.ndarray:
    zc = np.concatenate([[0], np.cumsum(zone)])
    n = len(zone)
    aa, bb = np.clip(np.asarray(a), 0, n - 1), np.clip(np.asarray(b), 0, n - 1)
    return (zc[bb + 1] - zc[aa]) > 0


def ep_window(e: Ep, w: int, kind: str) -> tuple[int, int]:
    """The episode's own window for a lift of this kind."""
    if kind == "lead":
        return e.p - w, e.p - 1
    if kind == "coin":
        return e.p, e.g
    return e.g - w, e.g - 1


def controls(ctx: Ctx, zone: np.ndarray, k: str, e: Ep, w: int, kind: str) -> np.ndarray:
    """Control shares `f_d` for episode `e`: the sessions that meet every calm-day rule.

    kind `lead` and `glead`: control windows d - w .. d - 1. kind `coin`: windows
    d .. d + (g - p), with the lead window of length LEAD_W also zone-free. The
    value rule is joint: a control window must have every candidate value the
    episode's own window has (Resolved at build 2026-11-21)."""
    n = ctx.n
    d = np.arange(max(0, e.p - CONTROL_RANGE), min(n - 1, e.p + CONTROL_RANGE) + 1)
    wc = LEAD_W if kind == "coin" else w
    la, lb = d - wc, d - 1
    m = (ctx.win[d] == ctx.win[e.p]) & ~zone[d] & (la >= 0) & ~zone_any(zone, la, lb)
    ca, cb = (d, d + (e.g - e.p)) if kind == "coin" else (la, lb)
    if kind == "coin":
        m &= (cb <= n - 1) & ~zone_any(zone, ca, cb)
    a_e, b_e = ep_window(e, w, kind)
    need = [x for x in CANDS if ctx.share(x, [a_e], [b_e])[1][0] or x == k]
    for x in need:
        m &= ctx.share(x, ca, cb)[1]
    fd, _ = ctx.share(k, ca, cb)
    return fd[m]


def lift(ctx: Ctx, zone: np.ndarray, k: str, e: Ep, w: int, kind: str):
    """`(x_e, reason)`: the episode's lift, or None with 'missing' / 'few_controls'."""
    a, b = ep_window(e, w, kind)
    sh, ok = ctx.share(k, [a], [b])
    if not ok[0]:
        return None, "missing"
    fd = controls(ctx, zone, k, e, w, kind)
    if len(fd) < MIN_CONTROLS:
        return None, "few_controls"
    return float(sh[0] - fd.mean()), "ok"


def cell_xs(ctx: Ctx, zone: np.ndarray, eps: list[Ep], k: str, w: int, kind: str):
    """`(xs, kept episodes, drop counts)` over `eps` for one candidate cell."""
    xs, kept, drops = [], [], Counter()
    for e in eps:
        x, why = lift(ctx, zone, k, e, w, kind)
        if x is None:
            drops[why] += 1
        else:
            xs.append(x)
            kept.append(e)
    return np.array(xs, dtype=float), kept, drops


# ════════════════════════════════════════════════════════════════════════════
# Bootstrap: shared draws, one set per unit type, each cell using its members
# ════════════════════════════════════════════════════════════════════════════

class Draws:
    """Uniform draws shared by every cell. A cell of n units reads the first n
    columns and maps them to indices 0..n-1, so cells share their randomness."""

    def __init__(self, n_boot: int, seed: int, ep: int, cl: int, blk: int):
        rng = np.random.default_rng(seed)
        self.n_boot = n_boot
        self.u = {"ep": rng.random((n_boot, max(ep, 1)), dtype=np.float32),
                  "cl": rng.random((n_boot, max(cl, 1)), dtype=np.float32),
                  "blk": rng.random((n_boot, max(blk, 1)), dtype=np.float32)}

    def idx(self, which: str, n: int) -> np.ndarray:
        u = self.u[which]
        if n > u.shape[1]:
            raise ValueError(f"draws hold {u.shape[1]} {which} columns, a cell needs {n}")
        return np.minimum((u[:, :n] * n).astype(np.int64), n - 1)


@dataclass
class Result:
    point: float
    lo: float
    hi: float
    p: float
    n: int

    @property
    def half(self) -> float:
        return (self.hi - self.lo) / 2.0


def summarize(point: float, draws: np.ndarray, n: int) -> Result:
    d = draws[np.isfinite(draws)]
    if len(d) == 0 or not math.isfinite(point):
        return Result(point, float("nan"), float("nan"), 1.0, n)
    lo, hi = np.percentile(d, [2.5, 97.5])
    p = min(1.0, 2.0 * min(float(np.mean(d <= 0)), float(np.mean(d >= 0))))
    return Result(point, float(lo), float(hi), p, n)


def boot_mean(xs: np.ndarray, draws: Draws) -> Result:
    """Mean of `xs`, episodes resampled with replacement."""
    if len(xs) == 0:
        return Result(float("nan"), float("nan"), float("nan"), 1.0, 0)
    idx = draws.idx("ep", len(xs))
    return summarize(float(xs.mean()), xs[idx].mean(axis=1), len(xs))


# ════════════════════════════════════════════════════════════════════════════
# Verdict words (first matching row wins)
# ════════════════════════════════════════════════════════════════════════════

def q2_word(k: str, n_lead: int, lead: Result | None, adj_lead: float, n_coin: int,
            coin: Result | None, adj_coin: float, disc_ok: bool, pbo_ok: bool,
            forward: bool = False) -> str:
    if n_lead < FLOOR or lead is None:
        return STILL_OPEN if forward else UNDERPOWERED
    if lead.lo > 0 and adj_lead < ALPHA and disc_ok and pbo_ok:
        return LEADS
    have_coin = coin is not None and n_coin >= FLOOR and math.isfinite(coin.lo)
    if k in COIN_FAMILY and have_coin and coin.lo > 0 and adj_coin < ALPHA and pbo_ok:
        return COINCIDENT
    return NO_FORECAST            # C5-C7 not LEADS: NO-FORECAST whatever the mechanical line prints


def q2_mech(k: str, n_coin: int, coin: Result | None, pbo_ok: bool) -> str:
    """The printed-only mechanical line for C5-C7: `COINCIDENT (mechanical)` or ''."""
    if k in MECH_COIN and coin is not None and n_coin >= FLOOR and math.isfinite(coin.lo) \
            and coin.lo > 0 and pbo_ok and coin.p < ALPHA:
        return COINCIDENT_MECH
    return ""


def q2_read(words: dict, forward: bool = False) -> str:
    vals = list(words.values())
    if LEADS in vals:
        return LEADS
    if COINCIDENT in vals:
        return COINCIDENT
    if all(w == (STILL_OPEN if forward else UNDERPOWERED) for w in vals):
        return STILL_OPEN if forward else UNDERPOWERED
    return NO_FORECAST


def q3_word(n_clusters: int, res: Result | None, mean_on: float, adj: float,
            disc_D: float, disc_clusters: int, pbo_ok: bool, forward: bool = False):
    """`(word, note)` for one Q3 cell."""
    if n_clusters < FLOOR or res is None or not math.isfinite(res.lo):
        return (STILL_OPEN if forward else UNDERPOWERED), ""
    waived = forward or disc_clusters < FLOOR or not math.isfinite(disc_D)
    neg = res.hi < 0 and adj < ALPHA and (waived or disc_D < 0) and pbo_ok
    if neg and mean_on < 0:
        return ROOM_LEFT, ""
    if res.lo > 0 and adj < ALPHA and (waived or disc_D > 0) and pbo_ok:
        return TOO_LATE, ""
    if neg:
        return NULL, "below normal drift, no fall"
    return NULL, ("PBO veto" if not pbo_ok else "")


def holm_family(pvals: dict, names: tuple) -> dict:
    """Holm over the whole family: a missing or unpowered cell enters at p = 1."""
    full = {k: float(pvals.get(k, 1.0)) for k in names}
    return {k: v[0] for k, v in holm(full).items()}


# ════════════════════════════════════════════════════════════════════════════
# Q2
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Q2Cand:
    k: str
    n_lead: int
    lead: Result | None
    n_coin: int
    coin: Result | None
    disc: Result | None
    n_disc: int
    adj_lead: float = 1.0
    adj_coin: float = 1.0
    word: str = UNDERPOWERED
    mech: str = ""
    drops: Counter = field(default_factory=Counter)


def split_eps(eps: list[Ep], win: int, keep_follow: bool = False) -> list[Ep]:
    return [e for e in eps if e.closed and e.win == win and (keep_follow or not e.follow_on)]


def grade_q2(ctx: Ctx, zone: np.ndarray, graded: list[Ep], disc: list[Ep], draws: Draws,
             pbo: float | None, forward: bool = False, w: int = LEAD_W) -> dict:
    """Per-candidate lead and coincident lifts, Holm over the two families, and the word."""
    cands = {}
    for k in CANDS:
        xs, _, dr = cell_xs(ctx, zone, graded, k, w, "lead")
        xc, _, dc = cell_xs(ctx, zone, graded, k, w, "coin")
        xd, _, _ = cell_xs(ctx, zone, disc, k, w, "lead") if disc else (np.array([]), [], None)
        lead = boot_mean(xs, draws) if len(xs) else None
        coin = boot_mean(xc, draws) if len(xc) else None
        dres = boot_mean(xd, draws) if len(xd) else None
        cands[k] = Q2Cand(k, len(xs), lead, len(xc), coin, dres, len(xd), drops=dr + dc)
    adj_l = holm_family({k: c.lead.p for k, c in cands.items() if c.n_lead >= FLOOR and c.lead}, CANDS)
    adj_c = holm_family({k: c.coin.p for k, c in cands.items()
                         if k in COIN_FAMILY and c.n_coin >= FLOOR and c.coin}, COIN_FAMILY)
    pbo_ok = True if forward or pbo is None else pbo <= PBO_VETO
    for k, c in cands.items():
        c.adj_lead, c.adj_coin = adj_l[k], adj_c.get(k, 1.0)
        waived = forward or c.n_disc < FLOOR or c.disc is None
        disc_ok = True if waived else c.disc.point > 0
        c.word = q2_word(k, c.n_lead, c.lead, c.adj_lead, c.n_coin, c.coin, c.adj_coin,
                         disc_ok, pbo_ok, forward)
        c.mech = q2_mech(k, c.n_coin, c.coin, pbo_ok)
    return cands


def q2_grid(ctx: Ctx, zone: np.ndarray, eps: list[Ep], cal: Cal) -> np.ndarray:
    """The Q2 PBO matrix: T years x 27 configs x [sum of lead lifts, episode count]."""
    year = {y: i for i, y in enumerate(PBO_YEARS)}
    cfgs = [(k, w) for k in CANDS for w in LEAD_WS]
    M = np.zeros((len(PBO_YEARS), len(cfgs), 2))
    pool = [e for e in eps if e.closed and not e.follow_on]
    for j, (k, w) in enumerate(cfgs):
        for e in pool:
            y = year.get(int(cal.dates[e.p][:4]))
            if y is None:
                continue
            x, _ = lift(ctx, zone, k, e, w, "lead")
            if x is not None:
                M[y, j, 0] += x
                M[y, j, 1] += 1
    return M


def pbo_text(pbo: float | None) -> str:
    if pbo is None:
        return "—"
    note = "  -> PBO veto" if pbo > PBO_VETO else "  -> selection fragile" if pbo > PBO_FRAGILE else ""
    return f"{pbo:.3f}{note}"


def pbo_of(M: np.ndarray) -> float | None:
    try:
        return float(PBO.cscv(M, S=PBO_S, metric=PBO.ratio_metric).pbo)
    except ValueError:
        return None


# ════════════════════════════════════════════════════════════════════════════
# Q3
# ════════════════════════════════════════════════════════════════════════════

def onsets(holds: np.ndarray, has_state: np.ndarray, rearm: int = REARM) -> list[int]:
    """Sessions D on which the state holds, none of the `rearm` sessions before D
    held it, and all of those sessions had a state."""
    out = []
    for d in range(rearm, len(holds)):
        if holds[d] and not holds[d - rearm:d].any() and has_state[d - rearm:d].all():
            out.append(d)
    return out


def fwd_log_return(adj: np.ndarray, h: int, lag: int = 1) -> np.ndarray:
    """`R[t] = ln(A[t + lag + h] / A[t + lag])`; NaN where the window runs past the data."""
    n = len(adj)
    out = np.full(n, np.nan)
    m = n - lag - h
    if m > 0:
        out[:m] = np.log(adj[lag + h:lag + h + m] / adj[lag:lag + m])
    return out


def further_fall(adj: np.ndarray, h: int) -> np.ndarray:
    """`ff[t] = min(0, min(A[t+2 .. t+1+h]) / A[t+1] - 1)`."""
    n = len(adj)
    out = np.full(n, np.nan)
    for t in range(n - 1 - h):
        out[t] = min(0.0, float(adj[t + 2:t + 2 + h].min() / adj[t + 1] - 1.0))
    return out


@dataclass
class Q3Cell:
    n_on: int
    n_clusters: int
    n_other: int
    mean_on: float
    mean_other: float
    cl_sum: np.ndarray
    cl_cnt: np.ndarray
    bl_sum: np.ndarray
    bl_cnt: np.ndarray
    n_truncated: int = 0        # onsets in the window with no closed outcome window

    @property
    def D(self) -> float:
        return self.mean_on - self.mean_other


def q3_cell(R: np.ndarray, dates: list[str], ons: list[int], i0: int, i1: int,
            block: int = BLOCK, exclude=None) -> Q3Cell:
    """Onsets with D in [i0, i1] and a closed window, against every other session
    of the window with an outcome. Clusters are calendar months of D; other days
    are blocks `i // block`. Onsets with no closed window are counted in `n_truncated`.
    `exclude` is the set of sessions kept out of the other days (default: `ons`); a
    caller that grades only some onsets passes every onset of the signal here."""
    on_set = set(ons) if exclude is None else set(exclude)
    trunc = 0
    cl: dict = defaultdict(lambda: [0.0, 0])
    on_vals = []
    for d in ons:
        if i0 <= d <= i1:
            if not math.isfinite(R[d]):
                trunc += 1
                continue
            c = cl[dates[d][:7]]
            c[0] += float(R[d])
            c[1] += 1
            on_vals.append(float(R[d]))
    bl: dict = defaultdict(lambda: [0.0, 0])
    oth = []
    for t in range(i0, i1 + 1):
        if t not in on_set and math.isfinite(R[t]):
            b = bl[t // block]
            b[0] += float(R[t])
            b[1] += 1
            oth.append(float(R[t]))
    nan = float("nan")
    return Q3Cell(len(on_vals), len(cl), len(oth),
                  float(np.mean(on_vals)) if on_vals else nan,
                  float(np.mean(oth)) if oth else nan,
                  np.array([v[0] for v in cl.values()]), np.array([v[1] for v in cl.values()], dtype=float),
                  np.array([v[0] for v in bl.values()]), np.array([v[1] for v in bl.values()], dtype=float), trunc)


def q3_boot(cell: Q3Cell, draws: Draws) -> Result:
    """Clusters and other-day blocks resampled in the same draw; D = onset mean - other mean."""
    if cell.n_clusters == 0 or len(cell.bl_cnt) == 0 or not math.isfinite(cell.D):
        return Result(cell.D, float("nan"), float("nan"), 1.0, cell.n_clusters)
    ci = draws.idx("cl", cell.n_clusters)
    bi = draws.idx("blk", len(cell.bl_cnt))
    on = cell.cl_sum[ci].sum(axis=1) / cell.cl_cnt[ci].sum(axis=1)
    ot = cell.bl_sum[bi].sum(axis=1) / cell.bl_cnt[bi].sum(axis=1)
    return summarize(cell.D, on - ot, cell.n_clusters)


def z_values(R: np.ndarray, ons: list[int], dates: list[str]) -> dict:
    """`{year: [sum z, onset count]}` with z = (m - r) / sd over every session."""
    fin = R[np.isfinite(R)]
    if len(fin) < 2:
        return {}
    m, sd = float(fin.mean()), float(fin.std(ddof=1))
    out: dict = defaultdict(lambda: [0.0, 0])
    if sd <= 0:
        return {}
    for d in ons:
        if math.isfinite(R[d]):
            c = out[int(dates[d][:4])]
            c[0] += (m - float(R[d])) / sd
            c[1] += 1
    return out


def q3_grid(cal: Cal, flags: dict, rearm: int = REARM) -> np.ndarray:
    """The Q3 PBO matrix: T years x 6 configs x [sum z, onset count]."""
    year = {y: i for i, y in enumerate(PBO_YEARS)}
    cfgs = [(s, h) for s in Q3_GRADED for h in HORIZONS]
    M = np.zeros((len(PBO_YEARS), len(cfgs), 2))
    for j, (s, h) in enumerate(cfgs):
        holds, has = flags[s]
        zs = z_values(fwd_log_return(cal.adj, h), onsets(holds, has, rearm), cal.dates)
        for y, (tot, cnt) in zs.items():
            if y in year:
                M[year[y], j] = (tot, cnt)
    return M


@dataclass
class Q3Out:
    label: str
    signal: str
    h: int
    cell: Q3Cell
    res: Result
    disc_cell: Q3Cell
    disc_res: Result
    adj: float = 1.0
    word: str = UNDERPOWERED
    note: str = ""


def grade_q3(cal: Cal, flags: dict, draws: Draws, pbo: float | None, i_test, i_disc,
             rearm: int = REARM, forward: bool = False) -> dict:
    """The six graded Q3 cells. `i_test` / `i_disc` are (i0, i1) index windows."""
    outs = {}
    empty = Result(float("nan"), float("nan"), float("nan"), 1.0, 0)
    for label, sig, h in Q3_CELLS:
        holds, has = flags[sig]
        ons = onsets(holds, has, rearm)
        R = fwd_log_return(cal.adj, h)
        cell = q3_cell(R, cal.dates, ons, *i_test)
        dcell = q3_cell(R, cal.dates, ons, *i_disc) if i_disc else cell
        outs[label] = Q3Out(label, sig, h, cell, q3_boot(cell, draws), dcell,
                            q3_boot(dcell, draws) if i_disc else empty)
    pv = {k: o.res.p for k, o in outs.items() if o.cell.n_clusters >= FLOOR and math.isfinite(o.res.lo)}
    adj = holm_family(pv, tuple(c[0] for c in Q3_CELLS))
    pbo_ok = True if forward or pbo is None else pbo <= PBO_VETO
    for k, o in outs.items():
        o.adj = adj[k]
        o.word, o.note = q3_word(o.cell.n_clusters, o.res, o.cell.mean_on, o.adj,
                                 o.disc_cell.D if i_disc else float("nan"),
                                 o.disc_cell.n_clusters if i_disc else 0, pbo_ok, forward)
    return outs


# ════════════════════════════════════════════════════════════════════════════
# Gates and inputs
# ════════════════════════════════════════════════════════════════════════════

def check_cuts(cal: Cal) -> None:
    if cal.n == 0 or cal.dates[idx_on_or_before(cal, IN_SAMPLE_END)] < IN_SAMPLE_END:
        raise Refused(EXIT_INPUT, f"GE: SPY does not reach {IN_SAMPLE_END}. Exit 3.")


def load_inputs(refresh: bool):
    for name in SERIES:
        if refresh or not _cache_path(name).exists():
            try:
                fetch_series(name)
            except Refused:
                raise
            except Exception as exc:  # network, yfinance schema
                raise Refused(EXIT_INPUT, f"GE: fetching {SERIES[name][0]} failed ({exc}). Exit 3.")
    rows = {name: read_series(_cache_path(name)) for name in SERIES}
    empty = [n for n, r in rows.items() if not r]
    if empty:
        raise Refused(EXIT_INPUT, f"GE: an input series is empty: {empty}. Exit 3.")
    spy = rows["SPY"]
    vix = {d: c for d, c, _ in rows["VIX"]}
    vix3m = {d: c for d, c, _ in rows["VIX3M"]}
    hyg = {d: a for d, _, a in rows["HYG"] if a is not None}
    ief = {d: a for d, _, a in rows["IEF"] if a is not None}
    return spy, vix, vix3m, hyg, ief, rows


def gate_basis(spy: list[tuple], vix: dict) -> tuple[list[str], list[str], int]:
    """GB: close/adj never steps like a split; the cached close and VIX agree with
    the base-rate file within 0.5% on every common date."""
    probs = TB.ratio_problems(spy)
    try:
        bprobs, n_common = TB.base_rate_problems(spy, vix, BASE_RATE_CSV)
    except TB.Refused as exc:
        raise Refused(EXIT_INPUT, exc.message)
    return probs, bprobs, n_common


def gate_hash() -> list[str]:
    """GH: the episode definitions hash equals the registered one."""
    if IBH.episode_defs_hash() != IBH.EPISODE_DEFS_SHA256:
        return [f"episode definitions hash {IBH.episode_defs_hash()[:12]} is not the "
                f"registered {IBH.EPISODE_DEFS_SHA256[:12]}"]
    return []


def gate_labels(cal: Cal, lab: Labels, full_csv: Path = FULL_CSV, watch_csv: Path = WATCH_CSV):
    """GL: `{source: (common dates, disagreements[list])}` for the study's labels
    against `spy_vix_daily_full.csv` through MechLabeler and `regime_watch/history.csv`,
    on common dates up to the cut. Only dates the other source labels are compared."""
    out = {}
    mine = {d: (lab.direction[i], lab.vol[i], bool(lab.ok[i])) for i, d in enumerate(cal.dates)
            if d <= IN_SAMPLE_END}
    if Path(full_csv).exists():
        other = MR.MechLabeler.from_csv(full_csv)
        n, bad = 0, []
        for d, (md, mv, mok) in mine.items():
            od, ov, ook, mapped = other.label(d)
            if mapped != d or not ook:
                continue
            n += 1
            if not mok or (od, ov) != (md, mv):
                bad.append(f"{d} study {md}/{mv} vs spy_vix_daily_full {od}/{ov}")
        out["spy_vix_daily_full"] = (n, bad)
    if Path(watch_csv).exists():
        n, bad = 0, []
        with Path(watch_csv).open(newline="") as fh:
            for r in csv.DictReader(fh):
                d = r["date"][:10]
                if d not in mine or d > IN_SAMPLE_END or not r.get("mech_direction") or not r.get("mech_vol"):
                    continue
                n += 1
                md, mv, _ = mine[d]
                if (r["mech_direction"], r["mech_vol"]) != (md, mv):
                    bad.append(f"{d} study {md}/{mv} vs regime_watch {r['mech_direction']}/{r['mech_vol']}")
        out["regime_watch"] = (n, bad)
    return out


def gate_episodes(cal: Cal, full_csv: Path = FULL_CSV) -> dict:
    """GR: on `spy_vix_daily_full.csv` cut at the in-sample end, the study's episodes match
    index_bear_hedge's on peak and trough. `{def: (compared, mismatches[list])}`. Only
    episodes whose peak is at least 63 sessions after the file's first session."""
    if not Path(full_csv).exists():
        return {}
    ref = IBH.load_series(full_csv)
    k = bisect.bisect_right(ref.dates, IN_SAMPLE_END)
    ref = IBH.Series(ref.dates[:k], ref.spy[:k], ref.vix[:k])
    mine_cal = cut_cal(cal, IN_SAMPLE_END)
    out = {}
    for name in (HEADLINE_DEF, SECONDARY_DEF):
        theirs = [e for e in IBH.episodes(ref, name) if e.peak_i >= GR_SKIP_SESSIONS]
        mine = {(mine_cal.dates[e.p]): mine_cal.dates[e.trough] for e in build_episodes(mine_cal, name)}
        bad = [f"{e.peak}: reference trough {e.trough}, study {mine.get(e.peak, 'no episode')}"
               for e in theirs if mine.get(e.peak) != e.trough]
        out[name] = (len(theirs), bad)
    return out


def gate_lookahead(cal: Cal) -> int:
    """GX, labels: the mech label at `t` (both SMA lengths) equals the label on a series cut
    at `t`, on 60 evenly spaced sessions. Returns the number checked; raises AssertionError
    on a difference.

    The candidates are not re-checked here: `cand_at` slices every array to `[:t + 1]`
    before reading it, so a run-time comparison against a cut series could never differ
    (it would compare the function with itself). `tests/test_state_map.py` changes and
    removes every later close and requires identical candidate values."""
    idx = sorted({int(x) for x in np.linspace(max(0, SMA_LONG), cal.n - 1, GX_SAMPLE)}) \
        if cal.n > SMA_LONG else list(range(0, cal.n))
    full_tab = {sma: mech_table(cal.dates, cal.close, cal.vix, sma) for sma in (SMA_HEADLINE, SMA_LONG)}
    for t in idx:
        cutc = cut_cal(cal, cal.dates[t])
        for sma, tab in full_tab.items():
            row = mech_table(cutc.dates, cutc.close, cutc.vix, sma)[-1]
            if row != tab[t]:
                raise AssertionError(f"GX: label (SMA {sma}) at {cal.dates[t]} differs on a series cut there")
    return len(idx)


# ════════════════════════════════════════════════════════════════════════════
# Q1 tables
# ════════════════════════════════════════════════════════════════════════════

def run_lengths(vals: list) -> dict:
    """`{value: [run lengths]}`; a None breaks a run and is never counted."""
    runs: dict = defaultdict(list)
    cur, ln = None, 0
    for v in list(vals) + [None]:
        if v is not None and v == cur:
            ln += 1
            continue
        if cur is not None:
            runs[cur].append(ln)
        cur, ln = v, (1 if v is not None else 0)
    return dict(runs)


def run_stats(lengths: list[int]) -> dict:
    a = np.array(lengths, dtype=float)
    return {"count": len(a), "median": float(np.median(a)), "mean": float(a.mean()),
            "p90": float(np.percentile(a, 90)), "longest": int(a.max())}


def transitions(vals: list) -> Counter:
    """Day-to-day `(from, to)` counts where both sessions carry a value."""
    c: Counter = Counter()
    for a, b in zip(vals, vals[1:]):
        if a is not None and b is not None:
            c[(a, b)] += 1
    return c


def cell_names(lab: Labels) -> list:
    return [f"{d}/{v}" if d is not None and v is not None else None
            for d, v in zip(lab.direction, lab.vol)]


# ════════════════════════════════════════════════════════════════════════════
# Q4: a fixed SPY put spread on each Q3 signal, at real cached prices
# ════════════════════════════════════════════════════════════════════════════

TICKER = "SPY"


@dataclass
class Q4Trade:
    signal: str
    D: int
    entry: date
    spot: float
    expiry: date | None
    status: str                    # built | await | drop
    reason: str = ""
    long_k: float | None = None
    short_k: float | None = None
    fetch: tuple = ()


def q4_select(chain, evidence, cal: Cal, signal: str, D: int) -> Q4Trade:
    """The put spread's strikes and expiry for an onset at `D`. No pricing."""
    from scripts.backtest_study.f1_selection.benchmark import mechanical_baseline as MBL
    from scripts.backtest_study.f1_selection.regime import selloff_put_diagonal as SPD
    entry = date.fromisoformat(cal.dates[D + 1])
    spot = float(cal.close[D + 1])
    t = Q4Trade(signal, D, entry, spot, None, "drop")
    exp = MBL.rule_expiry(entry, Q4_DTE)
    if exp is None:
        t.reason = "no_monthly"
        return t
    t.expiry = exp
    lo = SPD.nearest_listed(chain, evidence, exp, spot * Q4_LONG_MULT, spot, entry, "Put")
    sh = SPD.nearest_listed(chain, evidence, exp, spot * Q4_SHORT_MULT, spot, entry, "Put")
    for s in (lo, sh):
        if s.status == "drop":
            t.reason = s.reason
            return t
    fetch = tuple(f for s in (lo, sh) for f in s.fetch)
    if lo.status == "await" or sh.status == "await":
        t.status, t.fetch, t.reason = "await", fetch, "strike_not_cached"
        return t
    if sh.strike >= lo.strike:
        t.reason = "put_spread_degenerate"
        return t
    t.status, t.long_k, t.short_k = "built", lo.strike, sh.strike
    return t


def q4_trades(chain, evidence, cal: Cal, flags: dict, start: str = Q4_START) -> list[Q4Trade]:
    out = []
    for sig in Q3_GRADED:
        holds, has = flags[sig]
        for d in onsets(holds, has):
            if cal.dates[d] >= start and d + 1 < cal.n:
                out.append(q4_select(chain, evidence, cal, sig, d))
    return out


def q4_fetch_list(trades: list[Q4Trade]) -> list[dict]:
    """Unique uncached contracts the awaiting trades name (the study-legs collector's input)."""
    seen = {}
    for t in trades:
        for o, e, k in t.fetch:
            seen.setdefault((o, e, round(float(k), 4)), t.signal)
    return [dict(ticker=TICKER, expiration=e, strike=k, opt_type=o, category=f"state_map:{s}")
            for (o, e, k), s in sorted(seen.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2]))]


def q4_price(chain, t: Q4Trade, cal: Cal, h: int, comm: float, close_of: dict):
    """`(R, reason)` for one built trade at horizon `h`: entry at the D + 1 closing mid
    (`entry_day_fill`), exit at the close of D + 1 + h (`leg_mark`, so `junk_day_mark`
    and intrinsic value at expiry), commission per leg-side, defined-risk clamp.
    `close_of` maps session date -> unadjusted SPY close."""
    from scripts.backtest import simulate as SIM
    from scripts.backtest.helpers import _defined_risk_bounds
    from scripts.backtest.legs import Leg
    from scripts.backtest_study.f1_selection.regime import selloff_put_diagonal as SPD
    legs = [Leg(1, TICKER, t.expiry, float(t.long_k), "Put"), Leg(-1, TICKER, t.expiry, float(t.short_k), "Put")]
    fills = [SPD.leg_fill(chain, lg, t.entry) for lg in legs]
    if any(f is None for f in fills):
        return None, "no_entry_quote"
    if any(f[0] is None for f in fills):
        return None, SIM.JUNK_ENTRY_REFUSAL
    prices, tags = [f[0] for f in fills], [f[1] for f in fills]
    if SIM._monotonicity_violation(legs, prices, tags):
        return None, SIM.NON_MONOTONIC_REFUSAL
    debit = prices[0] - prices[1]
    if debit <= 0:
        return None, "debit_priced_to_credit"
    bounds = _defined_risk_bounds(legs)
    if bounds is not None and debit > bounds[1]:
        debit = bounds[1]
    exit_i = t.D + 1 + h
    if exit_i >= cal.n:
        return None, "exit_after_data_end"
    day = date.fromisoformat(cal.dates[exit_i])
    if day >= t.expiry:
        day = t.expiry
    marks = [SPD.leg_mark(chain, lg, day, close_of.get(day)) for lg in legs]
    if any(m is None for m in marks):
        return None, "exit_unmarked"
    value = marks[0][0] - marks[1][0]
    if bounds is not None:
        value = min(max(value, bounds[0]), bounds[1])
    return ((value - debit) * 100.0 - comm * 4) / (debit * 100.0), "priced"


# ════════════════════════════════════════════════════════════════════════════
# Q5: the book by state at entry
# ════════════════════════════════════════════════════════════════════════════

def q5_population(records: list[dict]):
    """`(rows, counts)`: real and tweak rows, `fill_trusted`, not pending, every signal
    date before the seal. Every drop is counted."""
    counts: Counter = Counter()
    kept, sealed = era_mod.drop_sealed(records, "date")
    counts["sealed"] = sealed["rows"]
    rows = []
    for r in kept:
        if r.get("source") not in ("real", "tweak"):
            counts["source_out"] += 1
        elif r.get("pending"):
            counts["pending"] += 1
        elif not r.get("fill_trusted"):
            counts["not_fill_trusted"] += 1
        else:
            rows.append(r)
    return rows, counts


def q5_lag(rec: dict, lookup: dict) -> str:
    from scripts.backtest_study.f1_selection.regime.market_read import lag_bin
    from scripts.backtest_study.lib.book import norm_play
    row = rec["t"].row if rec.get("t") is not None else {}
    ac = lookup.get(f"{rec['date']}|{rec['ticker']}|{norm_play(row.get('play', ''))}")
    created = ac.get("created_datetime") if ac is not None else None
    return lag_bin(None if created is None or created != created else str(created), rec["date"])


def date_boot_ci(rows: list[dict], key: str, boot_n: int = BOOT_N, seed: int = SEED):
    """Date-clustered percentile CI of the mean of `key`: dates resampled with replacement."""
    by: dict = defaultdict(list)
    for r in rows:
        if r.get(key) is not None:
            by[str(r["date"])[:10]].append(float(r[key]))
    if not by:
        return float("nan"), float("nan")
    s = np.array([sum(v) for v in by.values()])
    c = np.array([len(v) for v in by.values()], dtype=float)
    idx = np.random.default_rng(seed).integers(0, len(s), size=(boot_n, len(s)))
    means = s[idx].sum(axis=1) / c[idx].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def q5_cell(rows: list[dict], boot_n: int = BOOT_N) -> dict:
    """Figures for one cell; THIN (figures withheld) under 20 rows or 10 signal dates."""
    dates = {str(r["date"])[:10] for r in rows}
    out = {"rows": len(rows), "dates": len(dates), "thin": len(rows) < Q5_MIN_ROWS or len(dates) < Q5_MIN_DATES}
    if out["thin"]:
        return out
    rs = [r["R"] for r in rows if r.get("R") is not None]
    both = [(r["R"], r["mfe"]) for r in rows if r.get("R") is not None and r.get("mfe") is not None]
    mfe = [r["mfe"] for r in rows if r.get("mfe") is not None]
    mae = [r["mae"] for r in rows if r.get("mae") is not None]
    den = sum(m for _, m in both)
    out.update(mean_R=float(np.mean(rs)) if rs else None,
               mean_mfe=float(np.mean(mfe)) if mfe else None,
               mean_mae=float(np.mean(mae)) if mae else None,
               capture=(sum(x for x, _ in both) / den) if both and den > 0 else None,
               ci=date_boot_ci(rows, "R", boot_n))
    return out


def q5_direction(rec: dict) -> str:
    d = tc_direction(rec.get("structure"))
    return d if d in ("bull", "bear") else "other"


def q5_tables(rows: list[dict], lags: dict, boot_n: int = BOOT_N) -> dict:
    """`{(table, lag cut, source, direction, state): cell}` for the three tables."""
    out = {}
    cuts = {"LIVE": lambda r: lags[id(r)] == "LIVE", "RETRO": lambda r: lags[id(r)] == "RETRO",
            "ALL": lambda r: True}
    states = {"mech_direction": lambda r: r.get("mech_direction"),
              "mech_vol": lambda r: r.get("mech_vol"),
              "cell": lambda r: (f"{r['mech_direction']}/{r['mech_vol']}"
                                 if r.get("mech_direction") and r.get("mech_vol") else None)}
    for cut, keep in cuts.items():
        sel = [r for r in rows if keep(r)]
        for src in ("real", "tweak"):
            for dirn in ("bull", "bear", "other"):
                part = [r for r in sel if r["source"] == src and q5_direction(r) == dirn]
                for tab, fn in states.items():
                    by = defaultdict(list)
                    for r in part:
                        s = fn(r)
                        if s is not None:
                            by[s].append(r)
                    for s, rs in by.items():
                        out[(tab, cut, src, dirn, s)] = q5_cell(rs, boot_n)
    return out


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
# ════════════════════════════════════════════════════════════════════════════

def section(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def pp(x: float, nd: int = 2) -> str:
    return "—" if x is None or not math.isfinite(x) else f"{100 * x:+.{nd}f}"


def res_txt(r: Result | None, scale: float = 100.0, nd: int = 2) -> str:
    if r is None or not math.isfinite(r.point):
        return "—"
    if not math.isfinite(r.lo):
        return f"{scale * r.point:+.{nd}f} [—]"
    return f"{scale * r.point:+.{nd}f} [{scale * r.lo:+.{nd}f}, {scale * r.hi:+.{nd}f}] ±{scale * r.half:.{nd}f}"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


def _inventory(path: Path) -> str:
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))[1:]
    mtime = datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    span = f"{rows[0][0][:10]} -> {rows[-1][0][:10]}" if rows else "empty"
    return f"  {len(rows):>6,} rows  {span}  {mtime}  {Path(path).resolve().relative_to(ROOT)}"


def print_header(era: str) -> None:
    print("state_map — which market states come before SPY sell-offs, and is the confirmed "
          "bear state too late?")
    print(f"registration: {REGISTRATION} (accepted by default; stamp {REGISTERED})")
    print(f"era: {era}" + (" (Q1-Q4 inputs are unversioned market closes; Q5 reads the book)"
                           if era == era_mod.CURRENT else " (Q5 only; Q1-Q4 were not re-run)"))
    print(f"windows: discovery first session -> {DISCOVERY_END}; test {TEST_START} -> {IN_SAMPLE_END}; "
          f"gap {GAP_START} -> {FORWARD_ANCHOR_DATE} (in no population); forward from {FORWARD_START}")
    if era_mod.SEAL_LIFTED:
        print(f"SEAL: lifted {era_mod.SEAL_LIFTED}; Q5 withholds nothing")
    else:
        print(f"SEAL: Q5 withholds every signal date from {era_mod.SEAL_START} (holdout_seal.md; this study "
              "is not in SEALED_READERS); Q1-Q4 read no play, flow signal or backtest row")
    dirty = "dirty" if _git("status", "--porcelain") else "clean"
    print(f"git: {_git('rev-parse', '--short', 'HEAD')} ({_git('rev-parse', '--abbrev-ref', 'HEAD')}, "
          f"working tree {dirty})")
    print(f"bootstrap: {BOOT_N} draws, seed {SEED}; episodes and month clusters are the units; "
          f"other days in {BLOCK}-session blocks")


# ════════════════════════════════════════════════════════════════════════════
# The run
# ════════════════════════════════════════════════════════════════════════════

def make_ctx(cal: Cal, cands: dict | None = None) -> Ctx:
    return Ctx(cal, cands if cands is not None else cand_series(cal), window_codes(cal))


def report_q1(cal: Cal, labs: dict) -> None:
    section("Q1 — the state map (descriptive, no verdict)")
    wins = {"discovery": (0, idx_on_or_before(cal, DISCOVERY_END)),
            "test": (idx_from(cal, TEST_START), cal.n - 1)}
    for name, lab in labs.items():
        for wname, (i0, i1) in wins.items():
            sl = slice(i0, i1 + 1)
            d, v = lab.direction[sl], lab.vol[sl]
            cells = cell_names(lab)[sl]
            n = i1 - i0 + 1
            print(f"\n  {name}, {wname} window ({cal.dates[i0]} -> {cal.dates[i1]}, {n} sessions)")
            cnt = Counter(c for c in cells if c is not None)
            no_vol = sum(1 for a, b in zip(d, v) if a is not None and b is None)
            unl = sum(1 for a in d if a is None)
            per_cell = "  ".join(f"{dd}/{vv} {cnt.get(f'{dd}/{vv}', 0)}" for dd in DIRS for vv in VOLS)
            print(f"    sessions per cell: {per_cell}")
            print(f"    labelled with no VIX close {no_vol}; unlabelled {unl}")
            for lbl, vals in (("direction", d), ("vol", v), ("cell", cells)):
                runs = run_lengths(vals)
                print(f"    runs, {lbl}: count / median / mean / p90 / longest")
                for key in sorted(runs):
                    s = run_stats(runs[key])
                    print(f"      {key:<14} {s['count']:>5} {s['median']:>6.1f} {s['mean']:>7.2f} "
                          f"{s['p90']:>6.1f} {s['longest']:>6}")
                tr = transitions(vals)
                tot = Counter()
                for (a, _b), c in tr.items():
                    tot[a] += c
                print(f"    transitions, {lbl} (count, share of the row):")
                for (a, b), c in sorted(tr.items()):
                    print(f"      {a:<14} -> {b:<14} {c:>6}  {c / tot[a]:.3f}")
            yrs = defaultdict(Counter)
            for i in range(i0, i1 + 1):
                if lab.direction[i] is not None:
                    yrs[cal.dates[i][:4]][lab.direction[i]] += 1
            print("    share of sessions in each direction by calendar year:")
            for y in sorted(yrs):
                tot = sum(yrs[y].values())
                print(f"      {y}  " + "  ".join(f"{dd} {yrs[y][dd] / tot:.2f}" for dd in DIRS))


def bucket_counts(vix_vals: list[float]) -> dict:
    out = Counter()
    for v in vix_vals:
        if math.isfinite(v):
            for name, lo, hi in BUCKETS:
                if lo <= v < hi:
                    out[name] += 1
    return out


def report_census(ctx: Ctx, zone: np.ndarray, closed: list[Ep], kept: list[Ep],
                  test: list[Ep]) -> None:
    """Reconciles the episode census with the lift n of each candidate (printing only).

    An episode leaves a lead cell for one of two registered reasons: the candidate has no
    value on every session of its lead window ('missing': VIX3M starts in 2006, HYG in
    2007, C2 needs 252 sessions), or fewer than MIN_CONTROLS control sessions meet every
    calm-day rule ('few_controls')."""
    fo = len(closed) - len(kept)
    print(f"  Discovery census: {len(closed)} closed episodes, {fo} follow-on(s) out -> {len(kept)}; "
          f"an episode then leaves a candidate's cell for 'missing' (no value on the whole "
          f"10-session lead window) or 'few_controls' (under {MIN_CONTROLS} control sessions meet "
          "every calm-day rule, the joint value rule included):")
    for label, eps in (("discovery", kept), ("test", test)):
        for k in CANDS:
            xs, _, dr = cell_xs(ctx, zone, eps, k, LEAD_W, "lead")
            print(f"    {label:<9} {k}  {len(eps)} -> n {len(xs):>2}   missing {dr['missing']:>2}   "
                  f"few_controls {dr['few_controls']:>2}")


def report_q2(cal: Cal, ctx: Ctx, draws: Draws, pbo: float | None, flags: dict | None = None) -> dict:
    """Prints the Q2 section and returns what the banner needs."""
    section("Q2 — early warning: state variables before E-DD8 onsets (headline W = 10)")
    trunc: Counter = Counter()
    eps = {name: build_episodes(cal, name, ctx.win, trunc) for name in (HEADLINE_DEF, SECONDARY_DEF)}
    zones = {name: zone_mask(e, cal.n) for name, e in eps.items()}
    head, sec = eps[HEADLINE_DEF], eps[SECONDARY_DEF]
    z8 = zones[HEADLINE_DEF]
    unclosed = [e for e in head if not e.closed]
    graded = split_eps(head, 1)
    disc = split_eps(head, 0)
    print(f"  {HEADLINE_DEF} episodes: {len(head)} found; test {len(split_eps(head, 1, True))} closed "
          f"({len(graded)} after {sum(1 for e in head if e.follow_on and e.win == 1 and e.closed)} follow-ons "
          f"out); discovery {len(split_eps(head, 0, True))} ({len(disc)} after follow-ons); "
          f"unclosed at the cut, dropped: {len(unclosed)}; no trigger session, dropped (n_truncated): "
          f"{trunc['no_trigger']}")
    print("  Lift in percentage points of sessions: on-share in the lead window minus the matched "
          "calm days'. Controls are shared by nearby episodes, so lifts are not fully independent;")
    print("  the episode bootstrap does not remove that.")
    cands = grade_q2(ctx, z8, graded, disc, draws, pbo)
    report_census(ctx, z8, split_eps(head, 0, True), disc, graded)
    print(f"\n  {'':<4}{'candidate':<38}{'n':>3} {'lead lift L_k [CI]':<34}{'Holm p':>7} "
          f"{'coincident [CI]':<48}{'word'}")
    for k, c in cands.items():
        tag = " (mechanical)" if k in MECH_COIN else ""
        print(f"  {k:<4}{CAND_NAME[k]:<38}{c.n_lead:>3} {res_txt(c.lead):<34}{c.adj_lead:>7.3f} "
              f"{res_txt(c.coin) + tag:<48}{c.word}" + (f"  (printed beside: {c.mech})" if c.mech else ""))
        if c.drops:
            print(f"       dropped: {dict(c.drops)}")
    print(f"\n  Q2 PBO (27 configs, T = {len(PBO_YEARS)} years, S = {PBO_S}): "
          + pbo_text(pbo))
    print("  Coincident rows: the Holm family is C1-C4, C8, C9 (m = 6); C5-C7 are true by "
          "construction and the READ ignores them.")
    print("  Coincident p-values behind the COINCIDENT words (Holm family m = 6: C1-C4, C8, C9; "
          "C5-C7 are outside the family, raw p only):")
    for k, c in cands.items():
        raw = f"{c.coin.p:.4f}" if c.coin is not None else "—"
        if k in COIN_FAMILY:
            print(f"    {k}  coincident Holm p {c.adj_coin:.4f} (raw {raw}, n {c.n_coin})")
        else:
            print(f"    {k}  coincident raw p {raw} (outside the family, n {c.n_coin})")

    print("\n  PRINTED ONLY — discovery window lift (waived under 10 episodes)")
    for k, c in cands.items():
        waived = c.n_disc < FLOOR
        print(f"    {k}  n {c.n_disc:>3}  {res_txt(c.disc)}" + ("  (check waived)" if waived else ""))

    print("\n  PRINTED ONLY — W = 5 and W = 21, lead lift")
    for w in (5, 21):
        for k in CANDS:
            xs, _, _ = cell_xs(ctx, z8, graded, k, w, "lead")
            print(f"    W {w:>2} {k}  n {len(xs):>3}  {res_txt(boot_mean(xs, draws)) if len(xs) else '—'}")

    print("\n  PRINTED ONLY — the twin that keeps follow-on episodes (W = 10)")
    keep = split_eps(head, 1, True)
    for k in CANDS:
        xs, _, _ = cell_xs(ctx, z8, keep, k, LEAD_W, "lead")
        print(f"    {k}  n {len(xs):>3}  {res_txt(boot_mean(xs, draws)) if len(xs) else '—'}")

    print(f"\n  PRINTED ONLY — {SECONDARY_DEF} episodes, secondary, not graded (own words; PBO from the "
          f"{HEADLINE_DEF} grid)")
    g5, d5 = split_eps(sec, 1), split_eps(sec, 0)
    c5 = grade_q2(ctx, zones[SECONDARY_DEF], g5, d5, draws, pbo)
    print(f"    {len(g5)} test episodes, {len(d5)} discovery")
    for k, c in c5.items():
        print(f"    {k}  n {c.n_lead:>3}  {res_txt(c.lead):<34} secondary, not graded: {c.word}")

    print("\n  PRINTED ONLY — C5-C7 coincident lifts (mechanical)")
    for k in MECH_COIN:
        print(f"    {k}  n {cands[k].n_coin:>3}  {res_txt(cands[k].coin)}  "
              f"graded word {cands[k].word}; mechanical line {cands[k].mech or 'not met'}")

    print("\n  PRINTED ONLY — VIX level buckets (share of sessions)")
    lead_v, ctl_v = [], []
    for e in graded:
        lead_v += [float(x) for x in cal.vix[e.p - LEAD_W:e.p]]
        d = np.arange(max(0, e.p - CONTROL_RANGE), min(cal.n - 1, e.p + CONTROL_RANGE) + 1)
        for x in d:
            if ctx.win[x] == ctx.win[e.p] and not z8[x] and x - LEAD_W >= 0 \
                    and not z8[x - LEAD_W:x].any():
                ctl_v += [float(y) for y in cal.vix[x - LEAD_W:x]]
    for lbl, vs in (("lead windows", lead_v), ("control windows", ctl_v)):
        bc, tot = bucket_counts(vs), max(sum(bucket_counts(vs).values()), 1)
        print(f"    {lbl:<16} " + "  ".join(f"{b[0]} {bc.get(b[0], 0) / tot:.3f}" for b in BUCKETS)
              + f"  ({tot} sessions)")

    print("\n  PRINTED ONLY — per episode: onset p, trigger g, trough, C1 controls, lead on-share per candidate")
    print("    p            g            trough       ctl  " + "  ".join(f"{k:>5}" for k in CANDS))
    for e in graded:
        n_ctl = len(controls(ctx, z8, "C1", e, LEAD_W, "lead"))
        shares = []
        for k in CANDS:
            s, ok = ctx.share(k, [e.p - LEAD_W], [e.p - 1])
            shares.append(f"{s[0]:5.2f}" if ok[0] else "    —")
        print(f"    {cal.dates[e.p]}  {cal.dates[e.g]}  {cal.dates[e.trough]}  {n_ctl:>3}  " + "  ".join(shares))

    print("\n  PRINTED ONLY — the other side (no verdict, no Holm family, no PBO grid)")
    report_other_side(cal, ctx, head, z8, graded, disc, draws, flags)
    return {"cands": cands, "read": q2_read({k: c.word for k, c in cands.items()})}


POSTHOC_HORIZONS = (21, 10)


def posthoc_split(ons: list[int], trig_p: list[tuple[int, int]], n: int, h: int) -> dict:
    """Post-hoc, descriptive. Turn-ons at sessions `ons` against E-DD8 trigger sessions.

    `trig_p` is `[(g, p)]` sorted by g. A turn-on at t is *followed* when some trigger g
    satisfies t < g <= t + h. Its position is `before` the peak when t < p of that
    episode, and `mid` (between p and g, the fall already under way) when p <= t < g.
    Turn-ons with t + h > n - 1 are left out: the calendar `n` is the in-sample cut, so
    no close after it is read. Returns `{n, followed, before, mid}`."""
    gs = [g for g, _ in trig_p]
    out = {"n": 0, "followed": 0, "before": 0, "mid": 0}
    for t in ons:
        if t + h > n - 1:
            continue
        out["n"] += 1
        j = bisect.bisect_right(gs, t)
        if j < len(gs) and gs[j] <= t + h:
            out["followed"] += 1
            out["before" if t < trig_p[j][1] else "mid"] += 1
    return out


def _ph_cell(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k:>3} {k / n:.3f} [{lo:.3f}, {hi:.3f}]" if n else f"{k:>3}   —"


def report_posthoc_turn_on(cal: Cal, ctx: Ctx, head: list[Ep], flags: dict | None) -> None:
    """POST-HOC descriptive table: turn-ons over all sessions, no zone filter."""
    trig_p = sorted((e.g, e.p) for e in head)
    print()
    print("    POST-HOC (added 2026-11-21 after the first run; not registered; descriptive only) — "
          "TURN-ON, all sessions")
    print("    Every off-to-on turn-on counts, in or out of an exclusion zone. 'followed' = an E-DD8 "
          "trigger session within H sessions after the turn-on. 'before peak' = the turn-on is before "
          "that episode's peak p (a warning); 'peak-to-trigger' = p <= turn-on < g (the fall is already "
          "under way). Shares are of all turn-ons, Wilson 95% [lo, hi]. 'all sessions' is the same "
          "share over every session in the window. No verdict, no Holm family, no PBO grid.")
    sig_names = (("S-BEAR", "mech BEAR onset"), ("S-EVOL", "E-VOL onset"),
                 ("S-BEAR200", "SMA-200 BEAR onset"))
    rows = [(k, CAND_NAME[k], [t for t in range(1, cal.n)
                               if ctx.val[k][t] == 1.0 and ctx.val[k][t - 1] == 0.0]) for k in CANDS]
    if flags is not None:
        for sig, label in sig_names:
            holds, has = flags[sig]
            rows.append((sig, label, onsets(holds, has)))
    for wname, (i0, i1) in (("test", (idx_from(cal, TEST_START), cal.n - 1)),
                            ("discovery", (0, idx_on_or_before(cal, DISCOVERY_END)))):
        print(f"    window {wname}")
        for h in POSTHOC_HORIZONS:
            base = posthoc_split(list(range(i0, i1 + 1)), trig_p, cal.n, h)
            print(f"      H {h:>2}  all sessions: {base['n']} sessions  followed "
                  f"{_ph_cell(base['followed'], base['n'])}  before peak {_ph_cell(base['before'], base['n'])}  "
                  f"peak-to-trigger {_ph_cell(base['mid'], base['n'])}")
            for k, label, ons in rows:
                r = posthoc_split([t for t in ons if i0 <= t <= i1], trig_p, cal.n, h)
                print(f"      {k:<9} H {h:>2}  turn-ons {r['n']:>4}  followed {_ph_cell(r['followed'], r['n'])}"
                      f"  before peak {_ph_cell(r['before'], r['n'])}  "
                      f"peak-to-trigger {_ph_cell(r['mid'], r['n'])}  ({label})")
    print("    Hindsight caveat: turn-ons cluster, so these shares are not independent draws and the "
          "Wilson intervals are too narrow; and this table was specified after the first report had "
          "been read.")


def report_other_side(cal: Cal, ctx: Ctx, head: list[Ep], z8: np.ndarray, graded: list[Ep],
                      disc: list[Ep], draws: Draws, flags: dict | None = None) -> None:
    trig = sorted(e.g for e in head)
    nxt = TURN_ON_FOLLOW

    def followed(t: int) -> bool:
        j = bisect.bisect_right(trig, t)
        return j < len(trig) and trig[j] <= t + nxt

    for wname, (i0, i1) in (("test", (idx_from(cal, TEST_START), cal.n - 1)),
                            ("discovery", (0, idx_on_or_before(cal, DISCOVERY_END)))):
        usable = [t for t in range(i0, i1 + 1) if t + nxt <= cal.n - 1]
        base = float(np.mean([followed(t) for t in usable])) if usable else float("nan")
        print(f"    TURN-ON, {wname}: share of all sessions followed by a trigger within {nxt}: "
              f"{base:.3f} ({len(usable)} sessions)")
        for k in CANDS:
            v = ctx.val[k]
            ons = [t for t in range(max(i0, 1), i1 + 1)
                   if v[t] == 1.0 and v[t - 1] == 0.0 and t + nxt <= cal.n - 1]
            inz = [t for t in ons if z8[t]]
            out = [t for t in ons if not z8[t]]
            share = float(np.mean([followed(t) for t in out])) if out else float("nan")
            print(f"      {k}  turn-ons {len(out):>4} (+{len(inz)} in an exclusion zone)  "
                  f"followed {share:.3f}")
    report_posthoc_turn_on(cal, ctx, head, flags)
    print("    G-LEAD, test: lift on the trigger-anchored lead window g - W to g - 1, same controls")
    for w in LEAD_WS:
        for k in CANDS:
            xs, _, _ = cell_xs(ctx, z8, graded, k, w, "glead")
            print(f"      W {w:>2} {k}  n {len(xs):>3}  {res_txt(boot_mean(xs, draws)) if len(xs) else '—'}")


def episode_of(eps: list[Ep], D: int):
    for e in eps:
        if e.p <= D <= max(e.end, e.trough):
            return e
    return None


def report_q3(cal: Cal, flags: dict, draws: Draws, pbo: float | None, eps_by_def: dict) -> dict:
    section("Q3 — after the signal: does SPY keep falling once the state prints?")
    i_test = (idx_from(cal, TEST_START), cal.n - 1)
    i_disc = (0, idx_on_or_before(cal, DISCOVERY_END))
    outs = grade_q3(cal, flags, draws, pbo, i_test, i_disc)
    print(f"  D = mean r_h over onsets minus mean r_h over other days, in percent; r_h = ln(A[D+1+h]/A[D+1]) "
          f"on Adj Close. Entry at the close of D + 1. Re-arm {REARM}.")
    print(f"  {'cell':<5}{'signal':<8}{'h':>3} {'onsets':>6} {'clusters':>8} {'mean r onset':>13} "
          f"{'mean r other':>13} {'D [CI]':<34}{'Holm p':>7}  word")
    for label, o in outs.items():
        print(f"  {label:<5}{o.signal:<8}{o.h:>3} {o.cell.n_on:>6} {o.cell.n_clusters:>8} "
              f"{pp(o.cell.mean_on):>13} {pp(o.cell.mean_other):>13} {res_txt(o.res):<34}{o.adj:>7.3f}  "
              f"{o.word}" + (f" ({o.note})" if o.note else "") + f"  half-width {100 * o.res.half:.2f}")
    print("  n_truncated (onsets in the window with no closed outcome window, left out): "
          + "  ".join(f"{k} {o.cell.n_truncated}" for k, o in outs.items()))
    print(f"\n  Q3 PBO (6 configs, T = {len(PBO_YEARS)}, S = {PBO_S}): "
          + pbo_text(pbo))
    print("\n  PRINTED ONLY — discovery window D")
    for label, o in outs.items():
        print(f"    {label:<4} clusters {o.disc_cell.n_clusters:>3}  {res_txt(o.disc_res)}"
              + ("  (check waived)" if o.disc_cell.n_clusters < FLOOR else ""))
    print("\n  PRINTED ONLY — S-BEAR200 and S-BOTH, test window")
    for sig in Q3_PRINTED:
        holds, has = flags[sig]
        ons = onsets(holds, has)
        for h in HORIZONS:
            cell = q3_cell(fwd_log_return(cal.adj, h), cal.dates, ons, *i_test)
            print(f"    {sig:<10} h {h:>2}  onsets {cell.n_on:>4}  clusters {cell.n_clusters:>3}  "
                  f"{res_txt(q3_boot(cell, draws))}")
    print("\n  PRINTED ONLY — further fall ff_h, same-close entry r_h^0, 5-session re-arm, 42-session blocks")
    for sig in Q3_GRADED:
        holds, has = flags[sig]
        ons, ons5 = onsets(holds, has), onsets(holds, has, REARM_ALT)
        for h in HORIZONS:
            ff = further_fall(cal.adj, h)
            c_ff = q3_cell(ff, cal.dates, ons, *i_test)
            ons_in = [d for d in ons if i_test[0] <= d <= i_test[1] and math.isfinite(ff[d])]
            s3 = np.mean([ff[d] <= -0.03 for d in ons_in]) if ons_in else float("nan")
            s5 = np.mean([ff[d] <= -0.05 for d in ons_in]) if ons_in else float("nan")
            c0 = q3_cell(fwd_log_return(cal.adj, h, lag=0), cal.dates, ons, *i_test)
            cr = q3_cell(fwd_log_return(cal.adj, h), cal.dates, ons5, *i_test)
            c42 = q3_cell(fwd_log_return(cal.adj, h), cal.dates, ons, *i_test, block=BLOCK_SENS)
            print(f"    {sig:<7} h {h:>2}  ff onset {pp(c_ff.mean_on)} vs other {pp(c_ff.mean_other)}; "
                  f"share ff<=-3% {s3:.2f}, <=-5% {s5:.2f}; r0 D {pp(c0.D)}; re-arm 5: onsets {cr.n_on} "
                  f"D {res_txt(q3_boot(cr, draws))}; 42-blocks {res_txt(q3_boot(c42, draws))}")
    print("\n  PRINTED ONLY — S-BEAR by VIX state at the onset (mean r_h, onsets)")
    holds, has = flags["S-BEAR"]
    ons = [d for d in onsets(holds, has) if i_test[0] <= d <= i_test[1]]
    vols = flags["_vol"]
    for h in HORIZONS:
        R = fwd_log_return(cal.adj, h)
        parts = []
        for v in VOLS:
            xs = [R[d] for d in ons if vols[d] == v and math.isfinite(R[d])]
            parts.append(f"{v} {pp(float(np.mean(xs))) if xs else '—'} (n {len(xs)})")
        print(f"    h {h:>2}  " + "   ".join(parts))
    print("\n  PRINTED ONLY — done: share of the episode's peak-to-trough fall already made at the entry close")
    for sig in Q3_GRADED:
        holds, has = flags[sig]
        ons = [d for d in onsets(holds, has) if i_test[0] <= d <= i_test[1] and d + 1 < cal.n]
        for name, eps in eps_by_def.items():
            vals = []
            for d in ons:
                e = episode_of([x for x in eps if x.closed], d)
                if e is not None and cal.close[e.p] != cal.close[e.trough]:
                    vals.append((cal.dates[d], float((cal.close[e.p] - cal.close[d + 1])
                                                     / (cal.close[e.p] - cal.close[e.trough]))))
            med = float(np.median([v for _, v in vals])) if vals else float("nan")
            print(f"    {sig:<7} {name}: {len(vals)} onsets inside an episode (peak to episode end), "
                  f"median done {med:.2f}")
            print("      " + "  ".join(f"{d} {v:.2f}" for d, v in vals))
    return {"outs": outs, "read": outs["B10"].word}


def q4_env():
    """`(chain, evidence, commission)`: the option-history cache, the skip-list evidence and
    the configured commission per contract per leg-side."""
    from scripts.backtest.simulate import _cost_knobs
    from scripts.backtest_study.f3_structure import structure_sweep as SS
    from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF
    comm, _ = _cost_knobs(SS.load_sim_cfg())
    return NTF.Chain(), NTF.unlisted_evidence(), comm


def report_q4(cal: Cal, flags: dict, env=None) -> str:
    section("Q4 — a fixed SPY put spread on each Q3 signal from 2022, real prices (descriptive, THIN-flagged)")
    try:
        chain, evidence, comm = env if env is not None else q4_env()
    except Exception as exc:
        print(f"  option cache unavailable ({type(exc).__name__}: {exc}); Q4 has nothing to price.")
        print(f"  {AWAITING}")
        return AWAITING
    trades = q4_trades(chain, evidence, cal, flags)
    cnt = Counter(t.status for t in trades)
    fetch = q4_fetch_list(trades)
    print(f"  onsets from {Q4_START}: {len(trades)}; strikes built {cnt['built']}, awaiting a fetch "
          f"{cnt['await']}, dropped {cnt['drop']} {dict(Counter(t.reason for t in trades if t.status == 'drop'))}")
    print(f"  contracts to fetch: {len(fetch)}")
    print("  n_truncated (onsets with D + 1 + h past the data, left out): "
          + "  ".join(f"h {h}: {sum(1 for x in trades if x.D + 1 + h >= cal.n)}" for h in HORIZONS))
    if cnt["await"]:
        print(f"  {AWAITING}: {len(fetch)} contracts. Q4 prices nothing until every trade has a cache "
              "file or a recorded refusal.")
        return AWAITING
    thin = False
    close_of = {date.fromisoformat(d): float(c) for d, c in zip(cal.dates, cal.close)}
    print(f"  commission ${comm:.2f} per contract per leg-side; R = P&L over the entry debit")
    for sig in Q3_GRADED:
        for h in HORIZONS:
            rs, why = [], Counter()
            for t in (x for x in trades if x.signal == sig and x.status == "built"
                      and x.D + 1 + h < cal.n):
                r, reason = q4_price(chain, t, cal, h, comm, close_of)
                if r is None:
                    why[reason] += 1
                else:
                    rs.append(r)
            flag = "THIN" if len(rs) < FLOOR else ""
            thin = thin or bool(flag)
            print(f"    {sig:<7} h {h:>2}  priced {len(rs):>3}  unpriced {sum(why.values()):>3} {dict(why)}  "
                  f"mean R {np.mean(rs) if rs else float('nan'):+.3f}  {flag}")
    return "DESCRIPTIVE, THIN" if thin else "DESCRIPTIVE"


def q5_gate(era: str):
    """`(q5, reason, code)`. The Q5 gate runs first and prints nothing: `load_book`'s era and
    thin-era refusals and `era.require_dates` exit the process, so they are caught here and
    become a refusal line in the report, with the registration's exit code (2 thin, 3 era)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            records, diag, lookup = load_q5(era)
            rows, _counts = q5_population(records)
            era_mod.require_dates(len({r["date"] for r in rows}), diag.get("era", era),
                                  what="Q5 needs 30 pre-seal signal dates")
    except SystemExit as exc:
        lines = [x.strip() for x in buf.getvalue().splitlines() if x.strip()]
        reason = " ".join(x.replace("REFUSED — ", "") for x in lines) or "refused"
        return None, reason, int(exc.code or 0)
    return (records, diag, lookup), None, None


def report_q5(records: list[dict], diag: dict, lookup: dict, boot_n: int = BOOT_N) -> None:
    section("Q5 — the book's bear and bull rows by market state at entry (descriptive, no verdict)")
    rows, counts = q5_population(records)
    print(f"  rows {len(rows)}; dropped here {dict(counts)}; era {diag.get('era')}; "
          f"seal: {era_mod.seal_line(diag.get('seal', {'rows': 0, 'dates': 0, 'reader': None}))}")
    pend = diag.get("pending", {})
    print(f"  dropped by the loader: pending open rows {pend.get('n', 0)}; non-exact proxy debit rows "
          f"{diag.get('n_proxy_excluded_non_exact', 0)}; duplicate proxy rows {diag.get('n_dup_dropped', 0)}; "
          f"rows with no path or method {diag.get('n_excluded_no_path_or_method', 0)}; "
          f"admitted as deferred fills {diag.get('n_proxy_admitted_deferred', 0)}")
    print("  R, MFE and MAE are in percent of the position's entry cost (stored as fractions); capture is "
          "sum R over sum MFE, a ratio")
    lags = {id(r): q5_lag(r, lookup) for r in rows}
    print("  lag bins: " + "  ".join(f"{b} {sum(1 for v in lags.values() if v == b)}" for b in LAG_BINS)
          + "  (a RETRO row came from a model that may know what came next)")
    tabs = q5_tables(rows, lags, boot_n)
    for tab in ("mech_direction", "mech_vol", "cell"):
        for cut in ("LIVE", "RETRO", "ALL"):
            print(f"\n  direction x {tab}, lag {cut}")
            keys = sorted(k for k in tabs if k[0] == tab and k[1] == cut)
            if not keys:
                print("    no rows")
            for _t, _c, src, dirn, s in keys:
                c = tabs[(tab, cut, src, dirn, s)]
                if c["thin"]:
                    print(f"    {src:<5} {dirn:<5} {s:<14} rows {c['rows']:>4} dates {c['dates']:>3}  THIN")
                else:
                    ci = c["ci"]
                    print(f"    {src:<5} {dirn:<5} {s:<14} rows {c['rows']:>4} dates {c['dates']:>3}  "
                          f"R {pp(c['mean_R'])}% [{pp(ci[0])}, {pp(ci[1])}]  MFE {pp(c['mean_mfe'])}% "
                          f"MAE {pp(c['mean_mae'])}%  capture {c['capture']:.2f}" if c["capture"] is not None
                          else f"R {pp(c['mean_R'])}% [{pp(ci[0])}, {pp(ci[1])}]  MFE {pp(c['mean_mfe'])}% "
                               f"MAE {pp(c['mean_mae'])}%  capture —")


def load_q5(era: str):
    """`(records, diag, analysis lookup)` via `load_book`, with no `sealed_read`."""
    from scripts.backtest_study.lib import book as BK
    paths = era_mod.resolve_paths(era)
    records, diag = BK.load_book(era=era)
    return records, diag, BK._build_analysis_lookup(paths["analysis"])


# ── forward ───────────────────────────────────────────────────────────────────

def run_forward(full: Cal, draws: Draws, flags_full: dict) -> dict:
    """The one-shot forward read on the uncut series: Q2 and Q3 on frozen definitions."""
    section("FORWARD — episodes and onsets after 2026-11-20 (one shot; STILL-OPEN until a cell reaches its floor)")
    anchor = idx_on_or_before(full, FORWARD_ANCHOR_DATE)
    ctx = make_ctx(full)
    eps = build_episodes(full, HEADLINE_DEF, ctx.win)
    zone = zone_mask(eps, full.n)
    fwd = [e for e in eps if e.closed and not e.follow_on and e.p >= anchor + LEAD_W + 1 and e.win == 3]
    print(f"  forward E-DD8 episodes (closed, p >= {anchor + LEAD_W + 1}): {len(fwd)} (floor {FLOOR}); "
          f"the current sell-off and its merges are out")
    cands = grade_q2(ctx, zone, fwd, [], draws, None, forward=True)
    cur = [e for e in eps if e.p <= anchor]
    cz = zone_bounds(cur[-1], full.n) if cur else None
    for k, c in cands.items():
        print(f"    {k}  n {c.n_lead:>3}  {res_txt(c.lead):<34} {c.word}")
    q2w = q2_read({k: c.word for k, c in cands.items()}, forward=True)
    i_fwd = (anchor + 1, full.n - 1)
    outs = {}
    for label, sig, h in Q3_CELLS:
        holds, has = flags_full[sig]
        every = onsets(holds, has)
        ons = [d for d in every if d >= anchor + REARM + 1 and not (cz and cz[0] <= d <= cz[1])]
        R = fwd_log_return(full.adj, h)
        cell = q3_cell(R, full.dates, ons, *i_fwd, exclude=every)
        outs[label] = (cell, q3_boot(cell, draws))
    pv = {k: o[1].p for k, o in outs.items() if o[0].n_clusters >= FLOOR and math.isfinite(o[1].lo)}
    adj = holm_family(pv, tuple(c[0] for c in Q3_CELLS))
    words = {}
    for k, (cell, res) in outs.items():
        words[k], _ = q3_word(cell.n_clusters, res, cell.mean_on, adj[k], float("nan"), 0, True, forward=True)
        print(f"    {k:<4} onsets {cell.n_on:>3} clusters {cell.n_clusters:>3} "
              f"n_truncated {cell.n_truncated:>2}  {res_txt(res):<34} {words[k]}")
    cur_on = {sig: [d for d in onsets(*flags_full[sig]) if d >= anchor + REARM + 1 and cz and cz[0] <= d <= cz[1]]
              for sig in Q3_GRADED}
    print(f"  forward onsets inside the current episode's exclusion zone (split, not graded): "
          f"{ {s: len(v) for s, v in cur_on.items()} }")
    print("  The first forward run in which a cell prints a word other than STILL-OPEN is its verdict of record.")
    return {"q2": q2w, "q3": words["B10"], "n_fwd_eps": len(fwd),
            "cells": {k: o[0] for k, o in outs.items()}, "in_zone": {s: len(v) for s, v in cur_on.items()}}


def analyse(full: Cal, boot_n: int = BOOT_N, q5=None, q4_environment=None, q5_refusal: str | None = None) -> dict:
    """Everything after the gates: Q1-Q5, the forward read and the banner. Every graded
    cell reads `full` cut at the in-sample end; only the forward read sees later closes."""
    cal = cut_cal(full, IN_SAMPLE_END)
    lab50 = labels_from_labeler(write_mech_csv(cal, MECH_CSV), cal.dates)
    lab200 = mech_labels(cal, SMA_LONG)
    ctx = make_ctx(cal)
    eps8 = build_episodes(cal, HEADLINE_DEF, ctx.win)
    eps5 = build_episodes(cal, SECONDARY_DEF, ctx.win)
    z8 = zone_mask(eps8, cal.n)
    flags = state_flags(lab50, lab200)
    flags["_vol"] = lab50.vol
    pbo2 = pbo_of(q2_grid(ctx, z8, eps8, cal))
    pbo3 = pbo_of(q3_grid(cal, flags))
    sizes = (cal.n // 20 + 10, cal.n // 15 + 10, cal.n // BLOCK + 5)
    draws = Draws(boot_n, SEED, *sizes)

    report_q1(cal, {"headline (SMA 50)": lab50, "BEAR200 (SMA 200)": lab200})
    q2 = report_q2(cal, ctx, draws, pbo2, flags)
    q3 = report_q3(cal, flags, draws, pbo3, {HEADLINE_DEF: eps8, SECONDARY_DEF: eps5})
    q4 = report_q4(cal, flags, q4_environment)
    if q5 is not None:
        report_q5(*q5, boot_n)
    else:
        section("Q5 — the book's bear and bull rows by market state at entry (descriptive, no verdict)")
        print(f"  Q5 REFUSED ({q5_refusal})" if q5_refusal else "  Q5 not run (no book supplied)")

    f_sizes = (full.n // 20 + 10, full.n // 15 + 10, full.n // BLOCK + 5)
    full50 = labels_from_table(mech_table(full.dates, full.close, full.vix, SMA_HEADLINE))
    full200 = labels_from_table(mech_table(full.dates, full.close, full.vix, SMA_LONG))
    fwd = run_forward(full, Draws(boot_n, SEED, *f_sizes), state_flags(full50, full200))

    section("VERDICT")
    w = {k: c.word for k, c in q2["cands"].items()}
    print(f"  >>> state_map Q2 READ (state variables before E-DD8 onsets, 10-session lead, test "
          f"{TEST_START} to {IN_SAMPLE_END}): {q2['read']} <<<")
    print("  >>> state_map Q2 CANDIDATES (Holm m=9): " + " ".join(f"{k} {w[k]}" for k in CANDS) + " <<<")
    print(f"  >>> state_map Q3 READ (B10: SPY 10 sessions after a mech BEAR onset vs other days, test "
          f"{TEST_START} to {IN_SAMPLE_END}): {q3['read']} <<<")
    print("  >>> state_map Q3 CELLS (Holm m=6): "
          + " ".join(f"{k} {o.word}" for k, o in q3["outs"].items()) + " <<<")
    print(f"  >>> state_map PBO: Q2 {'—' if pbo2 is None else f'{pbo2:.3f}'} "
          f"Q3 {'—' if pbo3 is None else f'{pbo3:.3f}'} <<<")
    print(f"  >>> state_map Q4 (SPY put spread on Q3 signals, 2022 on): {q4} <<<")
    print(f"  >>> state_map FORWARD (episodes and onsets after {FORWARD_ANCHOR_DATE}): "
          f"Q2 {fwd['q2']} Q3 {fwd['q3']} <<<")
    print()
    print("  LEADS needs the lead lift's CI above 0, a Holm p below 0.05, a positive discovery lift and PBO <= 0.50.")
    print("  Nothing ships from this study (state_map.md).")
    return {"q2": q2, "q3": q3, "q4": q4, "fwd": fwd, "pbo": (pbo2, pbo3)}


def run(refresh: bool = False, boot_n: int = BOOT_N) -> int:
    era = era_mod.requested_era()
    q5, why, code = q5_gate(era)       # silent; a refusal never blocks Q1-Q4, which read no play row
    print_header(era)
    if era != era_mod.CURRENT:
        if q5 is None:
            print(f"\n  Q5 REFUSED ({why})")
        else:
            report_q5(*q5, boot_n)
        print(f"\n  era {era}: Q5 only. Q1-Q4 were not re-run. Copy this report aside as -{era}-<date> "
              "before the current-era -latest.txt is restored.")
        return code or 0

    spy, vix, vix3m, hyg, ief, _rows = load_inputs(refresh)
    full = build_cal(spy, vix, vix3m, hyg, ief)
    check_cuts(full)
    cal = cut_cal(full, IN_SAMPLE_END)
    print("inputs read:")
    for name in SERIES:
        print(_inventory(_cache_path(name)))
    for extra in (BASE_RATE_CSV, FULL_CSV, WATCH_CSV):
        if extra.exists():
            print(_inventory(extra))
    print(f"series read: SPY {full.dates[0]} -> {full.dates[-1]} ({full.n} sessions); in-sample cut "
          f"{cal.dates[-1]} ({cal.n} sessions)")

    section("GATES")
    print(f"  GE: five series present and non-empty; SPY reaches {IN_SAMPLE_END} — pass")
    probs, bprobs, n_common = gate_basis(spy, vix)
    print(f"  GB ratio: {len(probs)} close/adj steps outside the dividend pattern; base-rate: {n_common} "
          f"common SPY dates, {len(bprobs)} disagreements over {BASIS_TOL:.1%}")
    if probs or bprobs:
        for line in (probs + bprobs)[:10]:
            print(f"    {line}")
        raise Refused(EXIT_INPUT, "GB: the price basis check failed. Exit 3.")
    bad_hash = gate_hash()
    print(f"  GH: episode definitions hash vs EPISODE_DEFS_SHA256 {IBH.EPISODE_DEFS_SHA256[:12]} — "
          f"{'pass' if not bad_hash else 'FAIL'}")
    if bad_hash:
        raise Refused(EXIT_GHASH, f"GH: {bad_hash[0]}. Exit 5.")

    lab50 = labels_from_labeler(write_mech_csv(cal, MECH_CSV), cal.dates)
    pin = labels_from_table(mech_table(cal.dates, cal.close, cal.vix, SMA_HEADLINE))
    if lab50.direction != pin.direction or lab50.vol != pin.vol:
        raise Refused(EXIT_INPUT, "GL: the parametrised labeler differs from MechLabeler at length 50. Exit 3.")
    for src, (n, bad) in gate_labels(cal, lab50).items():
        print(f"  GL {src}: {n} common dates, {len(bad)} disagreements")
        for line in bad:
            print(f"    {line}")
        if n and len(bad) / n > GL_MAX_DISAGREE:
            raise Refused(EXIT_INPUT, f"GL: more than {GL_MAX_DISAGREE:.0%} of {src} dates disagree. Exit 3.")
    for name, (n, bad) in gate_episodes(full).items():
        print(f"  GR {name}: {n} reference episodes compared, {len(bad)} mismatches")
        for line in bad:
            print(f"    {line}")
        if bad:
            raise Refused(EXIT_INPUT, f"GR: {name} episodes differ from index_bear_hedge's. Exit 3.")
    print(f"  GX: labels equal on a series cut at the session, {gate_lookahead(cal)} "
          "sessions checked — pass")
    print(f"  GC: the in-sample series is cut at {IN_SAMPLE_END} before anything is computed — pass")
    print(f"  GN: floors of {FLOOR} apply per cell; a cell below its floor prints {UNDERPOWERED}")
    analyse(full, boot_n, q5, q5_refusal=why)
    if code:
        print(f"\n  Q5 was refused; Q1-Q4 and the banner above are complete. Exit {code} (the registration's "
              "code for a thin or wrong-era book).")
    return code or 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="refetch SPY, ^VIX, ^VIX3M, HYG and IEF from yfinance before the run")
    args = ap.parse_args(argv)
    try:
        return run(refresh=args.refresh)
    except Refused as exc:
        print(f"REFUSED — {exc.message}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
