"""tail_breach_intraday — does SPY's low breach 2x its VIX move, or fall 5% in a week, and is either forecastable?

REGISTERED 2026-11-14, accepted by default the same day:
research/pre-registrations/f1_selection/regime/tail_breach_intraday.md. Every
constant, floor, seed and verdict word below is that file's. Read it before
changing anything here. The intraday twin of `tail_breach`: it imports that
module's predictors, row split, model, metric and verdict words unchanged, and
adds only the intraday events, the OHLC fetch and the OHLC gates.

WHAT IT ASKS
------------
Event A, intraday 2-sigma breach, on session t: ln(L_t / A_{t-1}) below
-k x VIX(t-1)/100/sqrt(252), k = 2 (1.5 and 2.5 printed). L is the session's
low on the total-return basis, A the adjusted close.

Event B, a 5% fall, indexed by its first session t (origin t-1): the low of
any of sessions t..t+4 at or below 0.95 x A_{t-1}. Printed beside it: the close
basis, the 1-session version, an upside 5% move and either direction.

Part 1 counts both per calendar year 2024, 2025, 2026 YTD. Part 2 forecasts
each from the four `tail_breach` vol-state predictors at the origin close:
PA (four predictors, any A breach in t..t+4) and PB (four predictors, B) are
co-primaries, Holm m = 2; SA1-SA4 and SB1-SB4 are one-predictor secondaries,
Holm m = 4 each; NA1 is PA's model on the next session. Coefficients are fitted
on outcome windows that end before 2024-01-02 and never refitted. Metric: Brier
skill score against the training base rate, 95% moving-block bootstrap CI
(block 21, 10,000 draws).

DATA
----
yfinance, auto_adjust=False, cached in `backtests/tail_breach_intraday/<name>.csv`
(date, open, high, low, close, adj_close). The total-return low is the raw low
times that session's adj_close / close, the factor yfinance's own auto_adjust
applies to every OHLC field, so the low and the prior adjusted close share one
basis and an ex-dividend drop is not a fall. The raw twin prints as BASIS.
Today's bar is never fetched (yfinance's `end` is exclusive).

The holdout seal does not apply: no flow signal, play or backtest row is read.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run tail_breach_intraday
    python -m scripts.backtest_study run tail_breach_intraday -- --refresh
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection.benchmark.ticker_class import holm  # noqa: E402
from scripts.backtest_study.f1_selection.regime import tail_breach as T  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/tail_breach_intraday.md"
# The registration date. Test rows: last outcome session on or before it.
# Forward rows: origin after it. None would mean an unaccepted draft.
REGISTERED: str | None = "2026-11-14"

# --- constants fixed by the registration -------------------------------------
K = 2.0                     # event A: multiple of the VIX-implied 1-day move
K_PARAMS = (1.5, 2.5)       # printed beside it, no verdict
MOVE = 0.05                 # event B: a 5% move from the origin close
B_WINDOW = 5                # event B: sessions t..t+4
HORIZON = 5                 # A's Y5: any breach in t..t+4
TEST_START = T.TEST_START   # 2024-01-02, shared with tail_breach
YEARS = T.YEARS
BLOCK, BLOCK_SENS, BOOT_N, SEED = 21, (10, 42), 10_000, 20261114
ALPHA = 0.05
MIN_TRAIN_ROWS = 2_500      # GT
MIN_TRAIN_EPISODES = 30     # GT, per event
MIN_TEST_EPISODES = 10      # GN, per event
FWD_MIN_ROWS = 250          # FORWARD
FWD_MIN_EPISODES = 10       # FORWARD
OHLC_FROM = "2006-07-17"    # GO checks sessions from the first VIX3M close
OHLC_TOL = 1e-6             # GO: relative slack for float rounding
CROSS_TOL = 0.005           # GC: yfinance raw low vs the Barchart cache, relative

CACHE_DIR = ROOT / "backtests" / "tail_breach_intraday"
BARCHART_SPY = ROOT / "backtests" / "underlying_ohlc_cache" / "SPY.csv"
BASE_RATE_CSV = T.BASE_RATE_CSV
SERIES = T.SERIES           # SPY, ^VIX, ^VIX3M and their start dates

PREDICTORS = T.PREDICTORS
PRED_NAME = T.PRED_NAME
SINGLES = T.SINGLES

PREDICTABLE, NO_FORECAST = T.PREDICTABLE, T.NO_FORECAST
UNDERPOWERED, STILL_OPEN = T.UNDERPOWERED, T.STILL_OPEN

EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
Refused = T.Refused


# ════════════════════════════════════════════════════════════════════════════
# Data
# ════════════════════════════════════════════════════════════════════════════

def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.csv"


def fetch_ohlc(name: str, end: str | None = None) -> Path:
    """yfinance -> `backtests/tail_breach_intraday/<name>.csv`. `end` is exclusive."""
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

    cols = [col(c) for c in ("Open", "High", "Low", "Close", "Adj Close")]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(name)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "open", "high", "low", "close", "adj_close"])
        for i, d in enumerate(cols[3].index):
            vals = [float(c.values[i]) for c in cols]
            if vals[3] != vals[3]:
                continue
            w.writerow([pd.Timestamp(d).strftime("%Y-%m-%d"),
                        *[repr(v) if v == v else "" for v in vals]])
    print(f"fetched {sym} -> {path.relative_to(ROOT)} ({len(cols[3])} rows)")
    return path


def read_ohlc(path: Path) -> list[tuple]:
    """(date, open, high, low, close, adj_close) rows, ascending. A row needs a
    finite positive close; any other missing field reads as None."""
    out = []
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            vals = []
            for k in ("open", "high", "low", "close", "adj_close"):
                try:
                    v = float(r.get(k) or "nan")
                except ValueError:
                    v = float("nan")
                vals.append(v if math.isfinite(v) and v > 0 else None)
            if vals[3] is None:
                continue
            out.append((r["date"][:10], *vals))
    return sorted(out)


@dataclass
class ICal(T.Cal):
    """`tail_breach`'s calendar plus the session's raw high and low. `T.Cal`
    holds close (raw), adj (total return), vix and vix3m."""
    high_raw: np.ndarray | None = None
    low_raw: np.ndarray | None = None

    @property
    def factor(self) -> np.ndarray:
        """adj_close / close: the session's total-return adjustment factor."""
        return self.adj / self.close

    def low(self, basis: str = "adj") -> np.ndarray:
        return self.low_raw * self.factor if basis == "adj" else self.low_raw

    def high(self, basis: str = "adj") -> np.ndarray:
        return self.high_raw * self.factor if basis == "adj" else self.high_raw

    def ref(self, basis: str = "adj") -> np.ndarray:
        """The close an event is measured from, on the same basis as the low."""
        return self.adj if basis == "adj" else self.close


def build_icals(spy: list[tuple], vix: dict[str, float], vix3m: dict[str, float]) -> ICal:
    rows = [r for r in spy if r[5] is not None]
    nan = float("nan")
    return ICal(dates=[r[0] for r in rows],
                close=np.array([r[4] for r in rows], dtype=float),
                adj=np.array([r[5] for r in rows], dtype=float),
                vix=np.array([vix.get(r[0], nan) for r in rows], dtype=float),
                vix3m=np.array([vix3m.get(r[0], nan) for r in rows], dtype=float),
                high_raw=np.array([r[2] if r[2] is not None else nan for r in rows], dtype=float),
                low_raw=np.array([r[3] if r[3] is not None else nan for r in rows], dtype=float))


# ════════════════════════════════════════════════════════════════════════════
# Events. Each returns a float array: 1.0, 0.0, or NaN (undefined).
# ════════════════════════════════════════════════════════════════════════════

def intraday_down(cal: ICal, k: float = K, basis: str = "adj") -> np.ndarray:
    """Event A on session t: ln(low_t / ref_{t-1}) < -k x VIX(t-1)/100/sqrt(252)."""
    lo, ref = cal.low(basis), cal.ref(basis)
    r = np.full(cal.n, np.nan)
    if cal.n > 1:
        with np.errstate(invalid="ignore", divide="ignore"):
            r[1:] = np.log(lo[1:] / ref[:-1])
    s = T.implied_sigma(cal)
    ok = np.isfinite(r) & np.isfinite(s) & (s > 0)
    with np.errstate(invalid="ignore"):
        return T._flag(r < -k * s, ok)


def window_move(cal: ICal, move: float = MOVE, w: int = B_WINDOW, side: str = "down",
                basis: str = "low") -> np.ndarray:
    """Event B, indexed by its FIRST session t (origin t-1). Down: the minimum of
    sessions t..t+w-1 at or below (1 - move) x A_{t-1}. Up: the maximum at or
    above (1 + move) x A_{t-1}. Either: one or the other. `basis` "low" reads the
    total-return low and high; "close" reads adjusted closes. Undefined when
    t+w-1 is past the data or a value is missing."""
    if side not in ("down", "up", "either"):
        raise ValueError(side)
    lo = cal.low("adj") if basis == "low" else cal.adj
    hi = cal.high("adj") if basis == "low" else cal.adj
    out = np.full(cal.n, np.nan)
    for t in range(1, cal.n - w + 1):
        ref = cal.adj[t - 1]
        lw, hw = lo[t:t + w], hi[t:t + w]
        need = [lw] if side == "down" else [hw] if side == "up" else [lw, hw]
        if not (math.isfinite(ref) and all(np.all(np.isfinite(x)) for x in need)):
            continue
        down = side != "up" and float(np.min(lw)) <= (1.0 - move) * ref
        up = side != "down" and float(np.max(hw)) >= (1.0 + move) * ref
        out[t] = 1.0 if (down or up) else 0.0
    return out


def reflection_rate(k: float) -> float:
    """P(min of a driftless Brownian path over the day < -k sigma) = 2 x P(Z < -k).
    The reference for a low against a close-to-close sigma."""
    return min(1.0, 2.0 * T.normal_rate(k))


def move_reference(cal: ICal, idx: list[int], move: float = MOVE, w: int = B_WINDOW,
                   side: str = "down", basis: str = "low") -> float:
    """Mean over first sessions t in idx of the normal-law chance of event B at
    sigma_t x sqrt(w): reflection law for the low basis, the end-point law for
    the close basis (the close basis watches w closes, so this is a floor)."""
    s = T.implied_sigma(cal)
    law = reflection_rate if basis == "low" else T.normal_rate
    vals = []
    for t in idx:
        if not (math.isfinite(s[t]) and s[t] > 0):
            continue
        sw = s[t] * math.sqrt(w)
        p_dn = law(-math.log(1.0 - move) / sw)
        p_up = law(math.log(1.0 + move) / sw)
        vals.append(p_dn if side == "down" else p_up if side == "up" else min(1.0, p_dn + p_up))
    return float(np.mean(vals)) if vals else float("nan")


def episodes_of(b: np.ndarray, idx) -> int:
    """Independent episodes among the flagged sessions in idx (5-session chain)."""
    return T.episodes([i for i in idx if b[i] == 1.0])


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def check_era() -> None:
    requested = era_mod.requested_era()
    if requested != era_mod.CURRENT:
        raise Refused(era_mod.EXIT_THIN_ERA,
                      f"tail_breach_intraday reads yfinance market data, which carries no era; "
                      f"era {requested!r} does not apply — run it without --era. Exit 2.")


def ohlc_problems(spy: list[tuple], start: str = OHLC_FROM) -> list[str]:
    """GO: from `start`, every session has a high and a low, and
    low <= min(open, close) <= max(open, close) <= high, within OHLC_TOL."""
    out = []
    for d, o, h, lo, c, _ in spy:
        if d < start:
            continue
        if h is None or lo is None:
            out.append(f"{d} missing high or low")
            continue
        body = [x for x in (o, c) if x is not None]
        if lo > min(body) * (1 + OHLC_TOL) or h < max(body) * (1 - OHLC_TOL) or lo > h:
            out.append(f"{d} OHLC out of order: o {o} h {h} l {lo} c {c}")
    return out


def cross_feed_problems(spy: list[tuple], path: Path = BARCHART_SPY) -> tuple[list[str], int]:
    """GC: the raw yfinance low agrees with the Barchart cache's Low within
    CROSS_TOL on every common date. Skipped when the cache is missing."""
    if not Path(path).exists():
        return [], 0
    low = {r[0]: r[3] for r in spy}
    out, n = [], 0
    with Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            d = (r.get("Time") or "")[:10]
            try:
                want = float(r["Low"])
            except (KeyError, TypeError, ValueError):
                continue
            got = low.get(d)
            if got is None or not want > 0:
                continue
            n += 1
            if abs(got / want - 1.0) > CROSS_TOL:
                out.append(f"{d} low yfinance {got:.4f} vs Barchart {want:.4f}")
    return out, n


def load_inputs(refresh: bool) -> tuple[list, dict, dict]:
    for name in SERIES:
        if refresh or not _cache_path(name).exists():
            try:
                fetch_ohlc(name)
            except Refused:
                raise
            except Exception as exc:  # network, yfinance schema
                raise Refused(EXIT_INPUT, f"GE: fetching {SERIES[name][0]} failed ({exc}). Exit 3.")
    spy = read_ohlc(_cache_path("SPY"))
    vix = {r[0]: r[4] for r in read_ohlc(_cache_path("VIX"))}
    vix3m = {r[0]: r[4] for r in read_ohlc(_cache_path("VIX3M"))}
    if not spy or not vix or not vix3m:
        raise Refused(EXIT_INPUT, "GE: an input series is empty. Exit 3.")
    if spy[-1][0] < TEST_START:
        raise Refused(EXIT_INPUT, f"GE: SPY ends {spy[-1][0]}, before the test window. Exit 3.")
    return spy, vix, vix3m


# ════════════════════════════════════════════════════════════════════════════
# Arms
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class EventFit:
    """One event's rows, gates, four-predictor model and single-predictor models."""
    label: str
    rows: T.Rows
    flagged: np.ndarray          # the session-indexed flags episodes are counted on
    h: int
    tr_ep: int = 0
    te_ep: int = 0
    gt: bool = False
    gn: bool = False
    P: T.Model | None = None
    singles: dict | None = None
    idx: np.ndarray | None = None

    @property
    def powered(self) -> bool:
        return self.gt and self.gn


def outcome_from_first(b: np.ndarray):
    """YB at origin o reads B's flag at its first session o+1."""
    return lambda o: T.outcome_next(b, o)


def episodes_in_rows(b: np.ndarray, part: list, h: int, first_only: bool) -> int:
    """Episodes among a window's flagged sessions. For A (session events) every
    outcome session counts; for B (indexed by first session) the first only."""
    if first_only:
        return episodes_of(b, sorted({o + 1 for o, _, _ in part}))
    return episodes_of(b, sorted({o + j for o, _, _ in part for j in range(1, h + 1)}))


def fit_event(label: str, flagged: np.ndarray, outcome, h: int, preds: list, cal: ICal,
              first_only: bool, registered: str | None = REGISTERED) -> EventFit:
    rows = T.build_rows(cal, label, outcome, h, preds, registered)
    ev = EventFit(label, rows, flagged, h)
    _, Xtr, ytr = T.as_arrays(rows.train)
    _, _, yte = T.as_arrays(rows.test)
    ev.tr_ep = episodes_in_rows(flagged, rows.train, h, first_only)
    ev.te_ep = episodes_in_rows(flagged, rows.test, h, first_only)
    ev.gt = len(ytr) >= MIN_TRAIN_ROWS and ev.tr_ep >= MIN_TRAIN_EPISODES
    ev.gn = ev.te_ep >= MIN_TEST_EPISODES
    ev.P = T.fit_model(PREDICTORS, Xtr, ytr)
    ev.singles = {s: T.fit_model(c, Xtr, ytr) for s, c in SINGLES.items()}
    ev.idx = T.block_indices(len(yte), BLOCK, BOOT_N, SEED)
    return ev


def _nan_result() -> T.Result:
    return T.Result(float("nan"), float("nan"), float("nan"), 1.0, 0, 0)


def score_model(m: T.Model, part: list, L: int = BLOCK) -> tuple[T.Result, np.ndarray, np.ndarray]:
    _, X, y = T.as_arrays(part)
    if len(y) == 0:
        return _nan_result(), np.zeros(0), y
    p = m.prob(X)
    return T.score(p, y, m.clim, T.block_indices(len(y), L, BOOT_N, SEED)), p, y


def family_p(res: dict, powered: dict) -> dict:
    """A gated arm stays in its Holm family with p = 1, so m never shrinks."""
    return holm({k: (r.p if powered[k] else 1.0) for k, r in res.items()})


def co_primary_words(res: dict, powered: dict) -> tuple[dict, dict, dict]:
    """PA and PB, Holm m = 2. Returns (graded words, unadjusted words, Holm p)."""
    adj = family_p(res, powered)
    graded = {k: T.word(r, powered[k], adj[k][0]) for k, r in res.items()}
    plain = {k: T.word(r, powered[k]) for k, r in res.items()}
    return graded, plain, {k: adj[k][0] for k in res}


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

section, pct, bss_txt = T.section, T.pct, T.bss_txt


def year_groups(cal: ICal) -> list[tuple[str, list[int]]]:
    groups = [(y, T.year_index(cal, y)) for y in YEARS]
    groups.append(("2024-26", [i for y in YEARS for i in T.year_index(cal, y)]))
    groups.append(("train*", [i for i, d in enumerate(cal.dates) if "2006-07-18" <= d < TEST_START]))
    return groups


def report_part1(cal: ICal, defs: dict) -> None:
    section("PART 1 — events per calendar year (descriptive, no verdict)")
    print("  Wilson 95% CI treats sessions as independent. B rows count overlapping windows by")
    print("  their first session; episodes chain flags within 5 sessions. 'closing' = Phi(-k);")
    print("  'reflection' = 2 x Phi(-k), the chance a driftless path dips below -k sigma at any time.")
    for label, (b, refs) in defs.items():
        print(f"\n  {label}")
        print("    year       sessions  events  rate     [Wilson 95%]        "
              + "  ".join(f"{name:>10}" for name in refs) + "  episodes")
        for y, idx in year_groups(cal):
            r = T.year_row(y, b, idx)
            ref_txt = "  ".join(f"{pct(f(idx) if callable(f) else f):>10}" for f in refs.values())
            print(f"    {y:<9} {r.n:>9} {r.k:>7}  {pct(r.rate):>7}  [{pct(r.lo)}, {pct(r.hi)}]  "
                  f"{ref_txt}  {r.episodes:>8}")
    print("\n  * train = 2006-07-18 to 2023-12-29, context only. 2026 is year to date.")


def run(refresh: bool = False) -> int:
    check_era()
    spy, vix, vix3m = load_inputs(refresh)
    cal = build_icals(spy, vix, vix3m)

    print("tail_breach_intraday — does SPY's intraday low breach twice its VIX-implied move, "
          "or fall 5% within a week, and can either be forecast?")
    print(f"registration: {REGISTRATION} "
          f"({'registered ' + REGISTERED if REGISTERED else 'DRAFT, not registered'})")
    print("era: current (inputs are unversioned market data)")
    print(f"population: SPY sessions {cal.dates[0]} -> {cal.dates[-1]} ({cal.n}); "
          f"test window from {TEST_START}")
    dirty = "dirty" if T._git("status", "--porcelain") else "clean"
    print(f"git: {T._git('rev-parse', '--short', 'HEAD')} "
          f"({T._git('rev-parse', '--abbrev-ref', 'HEAD')}, working tree {dirty})")
    print("inputs read:")
    for name in SERIES:
        print(T._inventory(_cache_path(name)))
    for extra in (BASE_RATE_CSV, BARCHART_SPY):
        if extra.exists():
            print(T._inventory(extra))
    print("SEAL: not applied — no flow signal, play or backtest row is read")
    print(f"A: k={K} (printed {K_PARAMS}) on the total-return low; B: low within {B_WINDOW} sessions "
          f"at or below {1 - MOVE:.2f} x origin close; blocks {BLOCK}, {BOOT_N} draws, seed {SEED}")

    # ── gates ───────────────────────────────────────────────────────────────
    ca = [(r[0], r[4], r[5]) for r in spy]
    probs = T.ratio_problems(ca)
    bprobs, n_common = T.base_rate_problems(ca, vix, BASE_RATE_CSV)
    oprobs = ohlc_problems(spy)
    cprobs, n_cross = cross_feed_problems(spy)
    section("GATES — inputs and basis")
    print(f"  GE: SPY {len(spy)} rows, VIX {len(vix)}, VIX3M {len(vix3m)} — pass")
    print(f"  GB ratio: {len(probs)} close/adj steps outside the dividend pattern")
    print(f"  GB base-rate: {n_common} common SPY dates, {len(bprobs)} disagreements over 0.5%"
          + ("" if BASE_RATE_CSV.exists() else " (file missing: skipped)"))
    print(f"  GO: {len(oprobs)} sessions since {OHLC_FROM} with a missing or out-of-order high/low")
    print(f"  GC: {n_cross} sessions in the Barchart cache, {len(cprobs)} lows off by over "
          f"{CROSS_TOL:.1%}" + ("" if BARCHART_SPY.exists() else " (file missing: skipped)"))
    bad = probs + bprobs + oprobs + cprobs
    if bad:
        for line in bad[:10]:
            print(f"    {line}")
        raise Refused(EXIT_INPUT, "GB/GO/GC: the price basis check failed. Exit 3.")

    # ── events ──────────────────────────────────────────────────────────────
    ia = intraday_down(cal, K)
    bb = window_move(cal, side="down")
    rk = T.normal_rate
    a_refs = lambda k: {"closing": rk(k), "reflection": reflection_rate(k)}  # noqa: E731
    b_ref = lambda **kw: {"reflection": lambda idx: move_reference(cal, idx, **kw)}  # noqa: E731
    defs = {
        f"A k={K}: intraday low vs prior close (event A)": (ia, a_refs(K)),
        **{f"A k={k} (parameter)": (intraday_down(cal, k), a_refs(k)) for k in K_PARAMS},
        f"A-BASIS k={K}: raw low vs raw prior close (printed only)":
            (intraday_down(cal, K, basis="raw"), a_refs(K)),
        f"CLOSE k={K}: tail_breach's close-basis event (printed only)":
            (T.breach_down(cal, K), {"closing": rk(K)}),
        f"B: low {MOVE:.0%} below the origin close within {B_WINDOW} sessions (event B; by first session)":
            (bb, b_ref()),
        "B-CLOSE: adjusted close instead of low (printed only; reference is a floor)":
            (window_move(cal, basis="close"), {"end-point": lambda idx: move_reference(
                cal, idx, basis="close")}),
        "B-1: 5% intraday fall on one session (printed only)":
            (window_move(cal, w=1), b_ref(w=1)),
        "B-UP: high 5% above within 5 sessions (printed only)":
            (window_move(cal, side="up"), b_ref(side="up")),
        "B-EITHER: either direction within 5 sessions (printed only)":
            (window_move(cal, side="either"), b_ref(side="either")),
    }
    report_part1(cal, defs)

    # ── Part 2 ──────────────────────────────────────────────────────────────
    preds = [T.predictors_at(cal, o) for o in range(cal.n)]
    A = fit_event("YA5", ia, lambda o: T.outcome_any(ia, o), HORIZON, preds, cal, first_only=False)
    B = fit_event("YB", bb, outcome_from_first(bb), B_WINDOW, preds, cal, first_only=True)
    ya1 = T.build_rows(cal, "YA1", lambda o: T.outcome_next(ia, o), 1, preds, REGISTERED)
    _, X1tr, y1tr = T.as_arrays(ya1.train)
    NA1 = T.fit_model(PREDICTORS, X1tr, y1tr)

    section("PART 2 — rows and gates")
    for rows in (A.rows, B.rows, ya1):
        tr, te = rows.train, rows.test
        print(f"  {rows.name}: train {len(tr)} ({cal.dates[tr[0][0]] if tr else '—'} -> "
              f"{cal.dates[tr[-1][0]] if tr else '—'}), test {len(te)} "
              f"({cal.dates[te[0][0]] if te else '—'} -> {cal.dates[te[-1][0]] if te else '—'}), "
              f"forward {len(rows.fwd)}; dropped {rows.drops}")
    for ev, name in ((A, "A"), (B, "B")):
        print(f"  GT {name}: {len(ev.rows.train)} training rows (floor {MIN_TRAIN_ROWS}), {ev.tr_ep} "
              f"training episodes (floor {MIN_TRAIN_EPISODES}) — {'pass' if ev.gt else 'FAIL'}")
        print(f"  GN {name}: {ev.te_ep} independent episodes in the test window "
              f"(floor {MIN_TEST_EPISODES}) — {'pass' if ev.gn else 'FAIL'}")
    n_gx = T.gx_check(cal, preds)
    print(f"  GX: predictors equal on a series cut at the origin, {n_gx} origins checked — pass")

    section("PART 2 — fitted on training rows (standardised; intercept first)")
    models = [("PA", A.P), *((f"SA{s[1]}", m) for s, m in A.singles.items()), ("NA1", NA1),
              ("PB", B.P), *((f"SB{s[1]}", m) for s, m in B.singles.items())]
    for lab, m in models:
        coefs = "  ".join(f"{c} {b:+.3f}" for c, b in zip(("b0", *m.cols), m.beta))
        print(f"  {lab:<3} {coefs}   converged {m.converged}")
    print(f"  training base rate (climatology) YA5 {pct(A.P.clim)}, YA1 {pct(NA1.clim)}, "
          f"YB {pct(B.P.clim)}")

    # graded
    res, probs_te, ys = {}, {}, {}
    for key, ev in (("PA", A), ("PB", B)):
        res[key], probs_te[key], ys[key] = score_model(ev.P, ev.rows.test)
    powered = {"PA": A.powered and A.P.converged, "PB": B.powered and B.P.converged}
    w_co, w_plain, holm_p = co_primary_words(res, powered)

    sec = {}
    for tag, ev in (("A", A), ("B", B)):
        r = {f"S{tag}{s[1]}": score_model(m, ev.rows.test)[0] for s, m in ev.singles.items()}
        pw = {k: ev.powered and ev.singles[f"S{k[2]}"].converged for k in r}
        adj = family_p(r, pw)
        words = {k: T.word(v, pw[k], adj[k][0]) for k, v in r.items()}
        sec[tag] = (r, adj, words)

    resN, pN, yN = score_model(NA1, ya1.test)
    wN = T.word(resN, A.powered and NA1.converged)

    section("PART 2 — graded (test window, coefficients frozen)")
    for key, ev, what in (("PA", A, "any A breach in t..t+4"), ("PB", B, "B, 5% low within 5")):
        r = res[key]
        print(f"  {key}  four predictors, {what:<24} {bss_txt(r)}  n {r.n}, events {r.events}, "
              f"p {r.p:.4f}, Holm(m=2) {holm_p[key]:.4f}, AUC {T.auc(probs_te[key], ys[key]):.3f}"
              f"  -> {w_co[key]} (unadjusted: {w_plain[key]})")
    for tag, ev in (("A", A), ("B", B)):
        r, adj, words = sec[tag]
        _, Xte, yte = T.as_arrays(ev.rows.test)
        for k, v in r.items():
            m = ev.singles[f"S{k[2]}"]
            a = T.auc(m.prob(Xte), yte) if len(yte) else float("nan")
            print(f"  {k}  {PRED_NAME[m.cols[0]]:<30} {bss_txt(v)}  p {v.p:.4f}, Holm {adj[k][0]:.4f}, "
                  f"AUC {a:.3f}  -> {words[k]}")
    print(f"  NA1 four predictors, next-session A    {bss_txt(resN)}  n {resN.n}, events {resN.events}, "
          f"AUC {T.auc(pN, yN):.3f}  -> {wN}")
    if not all(m.converged for _, m in models):
        print("  a model did not converge: its word is UNDERPOWERED")

    section("PRINTED ONLY — base rate, years, block length")
    for key, ev in (("PA", A), ("PB", B)):
        y, p = ys[key], probs_te[key]
        te_rate = float(y.mean()) if len(y) else float("nan")
        draws = y[ev.idx].mean(axis=1) if len(y) else np.zeros(0)
        lo, hi = np.percentile(draws, [2.5, 97.5]) if len(draws) else (np.nan, np.nan)
        print(f"  {key} base rate: train {pct(ev.P.clim)}, test {pct(te_rate)} [{pct(lo)}, {pct(hi)}]; "
              f"a constant at the test rate scores "
              f"BSS {T.brier_skill(np.full(len(y), te_rate), y, ev.P.clim):+.4f} (oracle)")
        for yr in YEARS:
            sel = np.array([cal.dates[o + 1][:4] == yr for o, _, _ in ev.rows.test], dtype=bool)
            if sel.sum() == 0:
                continue
            r = T.score(p[sel], y[sel], ev.P.clim, T.block_indices(int(sel.sum()), BLOCK, BOOT_N, SEED))
            print(f"    {key} in {yr}: {bss_txt(r)}  n {r.n}, events {r.events}")
        for L in BLOCK_SENS:
            print(f"    {key} with {L}-session blocks: {bss_txt(score_model(ev.P, ev.rows.test, L)[0])}")

    section("PRINTED ONLY — parameters, raw basis and B variants (four predictors refitted per outcome)")
    alt = {f"A k={k}, any in t..t+4": (lambda o, b=intraday_down(cal, k): T.outcome_any(b, o), HORIZON)
           for k in K_PARAMS}
    ab = intraday_down(cal, K, basis="raw")
    alt[f"A-BASIS k={K}, any in t..t+4"] = (lambda o: T.outcome_any(ab, o), HORIZON)
    for lab, kw in (("B-CLOSE", {"basis": "close"}), ("B-1", {"w": 1}),
                    ("B-UP", {"side": "up"}), ("B-EITHER", {"side": "either"})):
        b = window_move(cal, **kw)
        alt[lab] = (outcome_from_first(b), kw.get("w", B_WINDOW))
    for lab, (fn, h) in alt.items():
        rows = T.build_rows(cal, lab, fn, h, preds, REGISTERED)
        _, Xa, ya = T.as_arrays(rows.train)
        _, _, yb = T.as_arrays(rows.test)
        if len(ya) == 0 or len(yb) == 0:
            print(f"  {lab}: no rows")
            continue
        m = T.fit_model(PREDICTORS, Xa, ya)
        r = score_model(m, rows.test)[0]
        print(f"  {lab:<28} {bss_txt(r)}  train rate {pct(m.clim)}, test rate {pct(float(yb.mean()))}, "
              f"test events {int(yb.sum())}")

    section("FORWARD — forecast origins after the registration date")
    fwd = {"PA": STILL_OPEN, "PB": STILL_OPEN}
    if REGISTERED is None:
        print("  registration not accepted: no forward window. forward: STILL-OPEN")
    else:
        for key, ev, first in (("PA", A, False), ("PB", B, True)):
            _, Xf, yf = T.as_arrays(ev.rows.fwd)
            f_ep = episodes_in_rows(ev.flagged, ev.rows.fwd, ev.h, first)
            f_pow = len(yf) >= FWD_MIN_ROWS and f_ep >= FWD_MIN_EPISODES
            res_f = score_model(ev.P, ev.rows.fwd)[0] if f_pow else None
            fwd[key] = T.forward_word(res_f, f_pow and ev.P.converged)
            print(f"  {key}: forward rows {len(yf)} (floor {FWD_MIN_ROWS}), episodes {f_ep} "
                  f"(floor {FWD_MIN_EPISODES})" + (f", {bss_txt(res_f)}" if res_f else "")
                  + f" -> {fwd[key]}")

    section("VERDICT")
    for key, ev in (("PA", A), ("PB", B)):
        te = ev.rows.test
        print(f"  {key} test window {TEST_START} -> {cal.dates[te[-1][0]] if te else '—'} (origins); "
              f"{len(te)} rows, {ev.te_ep} episodes")
    print(f"  {BOOT_N} moving-block draws (block {BLOCK}), seed {SEED}")
    print()
    print(f"  >>> tail_breach_intraday PA (four-predictor logistic, any intraday 2x-VIX breach in the "
          f"next 5 sessions, test from {TEST_START}): {w_co['PA']} <<<")
    print(f"  >>> tail_breach_intraday PB (four-predictor logistic, intraday low 5% below the origin "
          f"close within 5 sessions, test from {TEST_START}): {w_co['PB']} <<<")
    for tag in ("A", "B"):
        words = sec[tag][2]
        print(f"  >>> tail_breach_intraday SECONDARY {tag} (each predictor alone, Holm m=4): "
              + " ".join(f"{k} {w}" for k, w in words.items()) + " <<<")
    print(f"  >>> tail_breach_intraday NA1 (four-predictor logistic, next-session intraday breach): "
          f"{wN} <<<")
    print(f"  >>> tail_breach_intraday FORWARD (forecast origins after the registration date): "
          f"PA {fwd['PA']} PB {fwd['PB']} <<<")
    print()
    print("  PREDICTABLE needs the 95% CI on the Brier skill score wholly above 0 and a Holm-adjusted")
    print("  p below 0.05 (PA/PB m=2; SA/SB m=4). AUC is context only.")
    print("  Nothing ships from this study (tail_breach_intraday.md).")
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
