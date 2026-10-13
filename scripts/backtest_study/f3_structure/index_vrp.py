"""index_vrp — does short index vol lose in the same weeks as the long-delta ladder?

REGISTERED 2026-10-12, accepted by default the same day, before the first run:
research/pre-registrations/f3_structure/index_vrp.md. Every constant, window and
verdict word below is that file's. Read it before changing anything here.

WHAT IT COMPUTES
----------------
A monthly short-vol sleeve on real cached end-of-day quotes, one cycle per
standard monthly expiry from 2022-03, entered at the trading day nearest 30
calendar DTE and held to expiry:

    ARM S   short ATM straddle (descriptive; undefined risk, no verdict)
    ARM C   short iron condor, shorts at |delta| 0.16, wings 3% of spot out
            (graded on SPY, mid fill; 0.30 delta printed beside it)

M1 prints the variance risk premium per underlying and VIX tercile (context,
`PREMIUM` / `NO-PREMIUM`). M2 prints each arm's P&L with MFE and MAE (context).
M3 grades the SPY condor's daily mark-to-market against the deployed ladder
book's daily marked P&L (`account_sim` at the registered cell, then
`mtm_curve.book_curves(target=TARGET_POSITION)`): T1 tail mean, T2 stress
windows, T3 correlations, T4 drawdown, T5 the O2 total-loss overlay.

Verdict (registered): `LOSES-TOGETHER`, `DIVERSIFIES` or `NO-TAIL-LINK`. The
GLD condor, the natural fill, the stored book and v3 print their own tokens as
secondaries. Nothing ships from this study.

No network. Option quotes come from `backtests/option_history_cache/` only;
VIX from `backtests/mech_regime/spy_base_rate_daily.csv`. No model price.

Run:

    python -m scripts.backtest_study run index_vrp
"""
from __future__ import annotations

import csv
import math
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest.simulate import _bid_ask, _is_junk_quote  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as MC  # noqa: E402
from scripts.backtest_study.lib import path_bootstrap as PB  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import ruin_walk as RW  # noqa: E402

REGISTRATION = "research/pre-registrations/f3_structure/index_vrp.md"
ACCEPTED = "2026-10-12"

# --- registered constants ------------------------------------------------------
SEED = 20261012
BOOT_N = 10_000
BLOCK = 10
ALT_BLOCKS = (5, 20)
DD_BLOCKS = (5, 10, 20)
COMMISSION = 0.65            # $ per contract per side
TARGET_DTE = 30
#: Build ruling, not in the registration: a day-to-day spot move larger than
#: this is a bad `Price~` print and the day has no spot (see `accept_spot`).
SPOT_JUMP_MAX = 0.25
SHORT_DELTA = 0.16
ALT_DELTA = 0.30
WING_FRAC = 0.03
VIX_WINDOW = 756
FIRST_CYCLE = (2022, 3)
MAX_MISSING = 2
STOP_DOLLARS = 1000.0
T1_TAIL = 0.05
T3_TAIL = 0.10
UNDERLYINGS = ("SPY", "GLD")
GRADED_UNDERLYING = "SPY"
#: The registered account_sim cell (pre-registered 2026-08-13: $25,000, 2%,
#: per-position 0.25x, net 1.50x). config/account-sim.yml now carries net 2.50.
REGISTERED_NET_CAP = 1.50

WINDOWS = (
    ("W1", "2022 bear", "2022-01-01", "2022-12-31"),
    ("W2", "Aug 2024", "2024-08-01", "2024-08-31"),
    ("W3", "Mar-Apr 2025", "2025-03-01", "2025-04-30"),
    ("W4", "Feb-Apr 2026", "2026-02-01", "2026-04-30"),
)
GRADED_WINDOWS = ("W2", "W3", "W4")

CACHE_DIR = ROOT / "backtests" / "option_history_cache"
VIX_CSV = ROOT / "backtests" / "mech_regime" / "spy_base_rate_daily.csv"
OUT_CSV = ROOT / "backtests" / "study_output" / "index_vrp-latest.csv"
BACKTEST_YML = ROOT / "config" / "backtest.yml"

LOSES, DIVERSIFIES, NO_LINK = "LOSES-TOGETHER", "DIVERSIFIES", "NO-TAIL-LINK"
PREMIUM, NO_PREMIUM = "PREMIUM", "NO-PREMIUM"
TERCILES = ("low", "mid", "high")

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
EXIT_GMTM = 4


# ════════════════════════════════════════════════════════════════════════════
# Calendar and cycles
# ════════════════════════════════════════════════════════════════════════════

def third_friday(y: int, m: int) -> date:
    d = date(y, m, 15)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def monthly_expiry(y: int, m: int, trading: set[date]) -> date:
    """The standard monthly expiry: the third Friday, or the Thursday before it
    when that Friday is not a trading day (the holiday Thursday)."""
    f = third_friday(y, m)
    return f if f in trading else f - timedelta(days=1)


def _prev_month(y: int, m: int) -> tuple[int, int]:
    return (y - 1, 12) if m == 1 else (y, m - 1)


def cycles(first: tuple[int, int], last_quote: date, trading: set[date]) -> list[tuple[date, date]]:
    """`(previous expiry, expiry)` for every monthly cycle from `first` whose
    expiry is on or before `last_quote`."""
    out = []
    y, m = first
    while True:
        exp = monthly_expiry(y, m, trading)
        if exp > last_quote:
            break
        py, pm = _prev_month(y, m)
        out.append((monthly_expiry(py, pm, trading), exp))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def pick_entry(trading_days: list[date], prev_exp: date, exp: date,
               target: int = TARGET_DTE) -> date | None:
    """The trading day after `prev_exp` and before `exp` whose calendar DTE is
    nearest `target`, ties to the earlier day. Cycles therefore never overlap."""
    cands = [d for d in trading_days if prev_exp < d < exp]
    if not cands:
        return None
    return min(cands, key=lambda d: (abs((exp - d).days - target), d))


# ════════════════════════════════════════════════════════════════════════════
# Quotes
# ════════════════════════════════════════════════════════════════════════════

def _num(v) -> float | None:
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


@dataclass
class Chain:
    """Every cached contract of one (ticker, expiry): `rows[(type, strike)][date]`."""
    ticker: str
    expiry: date
    rows: dict = field(default_factory=dict)

    def on(self, d: date, typ: str) -> dict[float, dict]:
        """`{strike: row}` of `typ` contracts with a row on `d` — that day only."""
        return {k: r[d] for (t, k), r in self.rows.items() if t == typ and d in r}

    def row(self, typ: str, strike: float, d: date) -> dict | None:
        return self.rows.get((typ, strike), {}).get(d)

    def spot(self, d: date) -> float | None:
        """The most common positive `Price~` across the chain's rows on `d`
        (ties to the lower value); None when no row carries one."""
        cnt = Counter(v for r in self.rows.values() if d in r
                      for v in [_num(r[d].get("Price~"))] if v and v > 0)
        if not cnt:
            return None
        top = max(cnt.values())
        return min(v for v, n in cnt.items() if n == top)


def accept_spot(new: float | None, last: float | None) -> bool:
    """A day's spot is a bad print when it moves more than `SPOT_JUMP_MAX` from
    the last accepted one (Resolved at build: the cache carries whole-chain
    `Price~` glitches, e.g. SPY 177.54 on 2025-11-28 against 679.68 the day
    before)."""
    if new is None:
        return False
    return last is None or abs(new / last - 1) <= SPOT_JUMP_MAX


def load_chain(ticker: str, expiry: date, cache_dir: Path = CACHE_DIR) -> Chain:
    ch = Chain(ticker, expiry)
    tag = expiry.strftime("%Y%m%d")
    for f in cache_dir.glob(f"{ticker}_{tag}_*.csv"):
        stem = f.stem.split("_")[2]
        typ, strike = stem[-1], _num(stem[:-1])
        if typ not in ("C", "P") or strike is None:
            continue
        by: dict[date, dict] = {}
        with open(f, newline="") as fh:
            for r in csv.DictReader(fh):
                try:
                    d = date.fromisoformat(str(r.get("Time", ""))[:10])
                except ValueError:
                    continue
                by.setdefault(d, r)
        ch.rows[(typ, strike)] = by
    return ch


def mid_mark(row) -> tuple[float, str]:
    """`(price per share, tag)`: mid, or `Latest` when the shared junk-quote
    test (`scripts/backtest/simulate.py::_is_junk_quote`) fires or no ask is
    quoted."""
    bid, ask = _bid_ask(row)
    latest = _num(row.get("Latest"))
    if ask is None:
        return (latest if latest and latest > 0 else 0.0), "noquote"
    if _is_junk_quote(row):
        if latest and latest > 0:
            return latest, "junk"
        return ((bid or 0.0) + ask) / 2, "junk"
    return (bid + ask) / 2, "mid"


def natural_fill(row, sold: bool) -> tuple[float, str]:
    """Entry fill at the touch: a sold leg at the bid (0 with no bid), a bought
    leg at the ask; a junk quote falls back to `Latest`."""
    bid, ask = _bid_ask(row)
    latest = _num(row.get("Latest"))
    if sold and (bid is None or bid <= 0):
        return 0.0, "nobid"
    if ask is None or _is_junk_quote(row):
        if latest and latest > 0:
            return latest, "junk"
        if sold:
            return bid, "junk"
        return (ask if ask is not None else 0.0), "junk"
    return (bid if sold else ask), "natural"


def intrinsic(typ: str, strike: float, spot: float) -> float:
    return max(0.0, spot - strike) if typ == "C" else max(0.0, strike - spot)


# ════════════════════════════════════════════════════════════════════════════
# Strike selection — entry-day rows only
# ════════════════════════════════════════════════════════════════════════════

def select_atm(calls: dict[float, dict], puts: dict[float, dict], spot: float) -> float | None:
    """The strike nearest spot with both a call and a put row; ties to the lower."""
    both = sorted(set(calls) & set(puts))
    if not both:
        return None
    return min(both, key=lambda k: (abs(k - spot), k))


def select_delta(rows: dict[float, dict], target: float) -> float | None:
    """The strike whose cached `Delta` is nearest `target` (signed: +call, -put);
    rows with a zero or blank delta, or the wrong sign, are not candidates.
    Ties to the lower strike."""
    best = None
    for k in sorted(rows):
        dlt = _num(rows[k].get("Delta"))
        if dlt is None or dlt == 0 or (dlt > 0) != (target > 0):
            continue
        key = (abs(dlt - target), k)
        if best is None or key < best[0]:
            best = (key, k)
    return None if best is None else best[1]


def select_wing(strikes, short: float, target: float, side: str) -> float | None:
    """The listed strike nearest `target`; one listed strike further out when
    that lands on (or inside) the short strike. `side` is "C" or "P"."""
    ks = sorted(strikes)
    if not ks:
        return None
    k = min(ks, key=lambda x: (abs(x - target), x))
    if side == "C" and k <= short:
        out = [x for x in ks if x > short]
        return out[0] if out else None
    if side == "P" and k >= short:
        out = [x for x in ks if x < short]
        return out[-1] if out else None
    return k


# ════════════════════════════════════════════════════════════════════════════
# One cycle
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Leg:
    typ: str
    strike: float
    qty: int          # -1 sold, +1 bought


@dataclass
class Cycle:
    ticker: str
    arm: str          # "S" or "C"
    delta: float | None
    fill: str         # "mid" or "natural"
    prev_expiry: date
    entry: date
    expiry: date
    status: str = "ok"
    legs: list[Leg] = field(default_factory=list)
    spot_entry: float | None = None
    spot_T: float | None = None
    credit: float = 0.0           # per share
    max_loss: float | None = None  # $ per contract (condor only)
    marks: dict = field(default_factory=dict)   # date -> cumulative $ per contract
    pnl: float = 0.0
    mae: float = 0.0
    mfe: float = 0.0
    iv_entry: float | None = None
    rv: float | None = None
    vix: float | None = None
    vix_pct: float | None = None
    tercile: str | None = None
    n_junk: int = 0
    n_carried: int = 0
    n_bad_spot: int = 0

    @property
    def held(self) -> list[date]:
        return sorted(self.marks)

    @property
    def denom(self) -> float | None:
        """Max loss (condor) or credit (straddle), in $ per contract."""
        if self.arm == "C":
            return self.max_loss
        return self.credit * 100 if self.credit > 0 else None

    @property
    def size_1k(self) -> int:
        """The contract count whose max loss is nearest $1,000, minimum 1."""
        if not self.max_loss or self.max_loss <= 0:
            return 1
        return max(1, int(round(STOP_DOLLARS / self.max_loss)))

    def vrp_price(self) -> float | None:
        """`(straddle credit - |S_T - K|) / S_entry` (straddle cycles only)."""
        if self.arm != "S" or not self.spot_entry or self.spot_T is None:
            return None
        k = self.legs[0].strike
        return (self.credit - abs(self.spot_T - k)) / self.spot_entry

    def vrp_vol(self) -> float | None:
        if self.iv_entry is None or self.rv is None:
            return None
        return self.iv_entry - self.rv


def realized_vol(spots: list[float]) -> float | None:
    """Annualised close-to-close realized vol in vol points:
    `100 * sqrt(252 * mean(log-return^2))`."""
    r = [math.log(b / a) for a, b in zip(spots, spots[1:]) if a > 0 and b > 0]
    if not r:
        return None
    return 100.0 * math.sqrt(252.0 * sum(x * x for x in r) / len(r))


def build_legs(ch: Chain, entry: date, arm: str, delta: float | None,
               spot: float) -> tuple[list[Leg] | None, str]:
    calls, puts = ch.on(entry, "C"), ch.on(entry, "P")
    if arm == "S":
        k = select_atm(calls, puts, spot)
        if k is None:
            return None, "no_atm"
        return [Leg("C", k, -1), Leg("P", k, -1)], "ok"
    kc, kp = select_delta(calls, +delta), select_delta(puts, -delta)
    if kc is None or kp is None:
        return None, "no_short_delta"
    wc = select_wing(calls, kc, kc + WING_FRAC * spot, "C")
    wp = select_wing(puts, kp, kp - WING_FRAC * spot, "P")
    if wc is None or wp is None:
        return None, "no_wing"
    return [Leg("C", kc, -1), Leg("C", wc, +1), Leg("P", kp, -1), Leg("P", wp, +1)], "ok"


def run_cycle(ch: Chain, ticker: str, prev_exp: date, entry: date, exp: date,
              trading_days: list[date], arm: str, fill: str,
              delta: float | None = None) -> Cycle:
    """Enter at `entry` on that day's rows only, mark daily at mid, settle at
    intrinsic on the expiry-day `Price~`."""
    c = Cycle(ticker, arm, delta, fill, prev_exp, entry, exp)
    spot = ch.spot(entry)
    if spot is None:
        c.status = "no_entry_spot"
        return c
    c.spot_entry = spot
    legs, why = build_legs(ch, entry, arm, delta, spot)
    if legs is None:
        c.status = why
        return c
    c.legs = legs
    entry_rows = [ch.row(lg.typ, lg.strike, entry) for lg in legs]
    if any(r is None for r in entry_rows):
        c.status = "leg_missing_entry"
        return c
    held = [d for d in trading_days if entry < d <= exp]
    missing = [sum(1 for d in held if ch.row(lg.typ, lg.strike, d) is None) for lg in legs]
    if any(m > MAX_MISSING for m in missing):
        c.status = "leg_missing_sessions"
        return c
    last_ok = spot
    spot_by: dict[date, float] = {}
    for d in held:
        s_d = ch.spot(d)
        if accept_spot(s_d, last_ok):
            spot_by[d] = last_ok = s_d
    c.n_bad_spot = sum(1 for d in held if ch.spot(d) is not None and d not in spot_by)
    spot_T = spot_by.get(exp)
    if spot_T is None:
        c.status = "no_settlement_spot"
        return c
    c.spot_T = spot_T

    # entry
    credit, close_now = 0.0, 0.0
    for lg, r in zip(legs, entry_rows):
        m, tag = mid_mark(r)
        c.n_junk += tag != "mid"
        if fill == "natural":
            px, _ = natural_fill(r, sold=lg.qty < 0)
        else:
            px = m
        credit += -lg.qty * px
        close_now += -lg.qty * m
    c.credit = credit
    n_legs = len(legs)
    comm_in = COMMISSION * n_legs
    if arm == "C":
        width = max(legs[1].strike - legs[0].strike, legs[2].strike - legs[3].strike)
        c.max_loss = (width - credit) * 100
    if arm == "S":
        ivs = [_num(r.get("IV")) for r in entry_rows]
        ivs = [v for v in ivs if v and v > 0]
        c.iv_entry = sum(ivs) / len(ivs) if len(ivs) == 2 else None

    c.marks[entry] = (credit - close_now) * 100 - comm_in
    last = [mid_mark(r)[0] for r in entry_rows]
    spots = [spot]
    for d in held:
        if d in spot_by:
            spots.append(spot_by[d])
        if d == exp:
            owed = sum(-lg.qty * intrinsic(lg.typ, lg.strike, spot_T) for lg in legs)
            c.marks[d] = (credit - owed) * 100 - comm_in - COMMISSION * n_legs
            continue
        for i, lg in enumerate(legs):
            r = ch.row(lg.typ, lg.strike, d)
            if r is None:
                c.n_carried += 1
                continue
            m, tag = mid_mark(r)
            c.n_junk += tag != "mid"
            last[i] = m
        close = sum(-lg.qty * last[i] for i, lg in enumerate(legs))
        c.marks[d] = (credit - close) * 100 - comm_in
    if exp not in c.marks:
        c.status = "expiry_not_trading_day"
        return c
    c.rv = realized_vol(spots)
    vals = list(c.marks.values())
    c.pnl = c.marks[exp]
    c.mae, c.mfe = min(vals), max(vals)
    return c


# ════════════════════════════════════════════════════════════════════════════
# VIX tercile — past values only
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Market:
    dates: list[date]
    spy: list[float | None]
    vix: list[float | None]

    @property
    def trading(self) -> set[date]:
        return set(self.dates)


def load_market(path: Path = VIX_CSV) -> Market:
    rows = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                d = date.fromisoformat(str(r["date"])[:10])
            except (KeyError, ValueError):
                continue
            rows.append((d, _num(r.get("spy_close")), _num(r.get("vix_close"))))
    rows.sort()
    return Market([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows])


def vix_percentile(mk: Market, d: date, window: int = VIX_WINDOW) -> tuple[float | None, float | None]:
    """`(VIX on d, share of the trailing `window` sessions ending at d whose VIX
    is at or below it)`. Only closes on or before `d` enter."""
    i = bisect_right(mk.dates, d) - 1
    if i < 0 or mk.dates[i] != d or mk.vix[i] is None:
        return None, None
    lo = i - window + 1
    if lo < 0:
        return mk.vix[i], None
    hist = [v for v in mk.vix[lo:i + 1] if v is not None]
    return mk.vix[i], sum(1 for v in hist if v <= mk.vix[i]) / len(hist)


def tercile(p: float | None) -> str | None:
    if p is None:
        return None
    return "low" if p < 1 / 3 else "mid" if p < 2 / 3 else "high"


# ════════════════════════════════════════════════════════════════════════════
# Statistics
# ════════════════════════════════════════════════════════════════════════════

def iid_ci(vals, n: int = BOOT_N, seed: int = SEED) -> tuple[float, float]:
    v = np.asarray([x for x in vals if x is not None], dtype=float)
    if len(v) < 2:
        return float("nan"), float("nan")
    idx = np.random.default_rng(seed).integers(0, len(v), (n, len(v)))
    lo, hi = np.percentile(v[idx].mean(1), [2.5, 97.5])
    return float(lo), float(hi)


def premium_token(lo: float) -> str:
    return PREMIUM if math.isfinite(lo) and lo > 0 else NO_PREMIUM


def tail_k(n: int, share: float) -> int:
    return max(1, int(math.ceil(share * n)))


def tail_mean(book: np.ndarray, sleeve: np.ndarray, share: float = T1_TAIL) -> float:
    """Mean sleeve P&L on the book's worst `share` of sessions (ties: stable order)."""
    if not len(book):
        return float("nan")
    k = tail_k(len(book), share)
    sel = np.argsort(book, kind="stable")[:k]
    return float(sleeve[sel].mean())


def _rowcorr(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a - a.mean(1, keepdims=True)
    b = b - b.mean(1, keepdims=True)
    den = np.sqrt((a * a).sum(1) * (b * b).sum(1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, (a * b).sum(1) / den, np.nan)


def corr(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return float("nan")
    return float(_rowcorr(a[None, :], b[None, :])[0])


def tail_corr(book: np.ndarray, sleeve: np.ndarray, share: float = T3_TAIL) -> float:
    k = tail_k(len(book), share)
    sel = np.argsort(book, kind="stable")[:k]
    return corr(book[sel], sleeve[sel])


@dataclass
class TailStats:
    n: int
    block: int
    t1: float
    t1_ci: tuple[float, float]
    r_all: float
    r_all_ci: tuple[float, float]
    r_tail: float
    r_tail_ci: tuple[float, float]


def tail_stats(book, sleeve, block: int = BLOCK, n_paths: int = BOOT_N,
               seed: int = SEED) -> TailStats:
    """T1 and T3 with stationary-block-bootstrap CI95s over sessions: each path
    is resampled whole, and the book's worst sessions are re-found inside it."""
    b, s = np.asarray(book, float), np.asarray(sleeve, float)
    n = len(b)
    nan2 = (float("nan"), float("nan"))
    if n < 3:
        return TailStats(n, block, tail_mean(b, s), nan2, float("nan"), nan2,
                         float("nan"), nan2)
    idx = RW.stationary_indices(n, n, block, n_paths, np.random.default_rng(seed))
    bb, ss = b[idx], s[idx]
    order = np.argsort(bb, axis=1, kind="stable")
    rows = np.arange(n_paths)[:, None]
    k1, k3 = tail_k(n, T1_TAIL), tail_k(n, T3_TAIL)
    t1_draw = ss[rows, order[:, :k1]].mean(1)
    r_all = _rowcorr(bb, ss)
    r_tail = _rowcorr(bb[rows, order[:, :k3]], ss[rows, order[:, :k3]])

    def ci(x):
        x = x[np.isfinite(x)]
        return tuple(float(v) for v in np.percentile(x, [2.5, 97.5])) if len(x) else nan2

    return TailStats(n, block, tail_mean(b, s), ci(t1_draw), corr(b, s), ci(r_all),
                     tail_corr(b, s), ci(r_tail))


def verdict(windows: dict[str, tuple[float, float]], t1_ci: tuple[float, float],
            dd_book: float, dd_combined: float) -> tuple[str, str]:
    """The registered grammar. `windows` maps each COVERED graded window to
    `(book sum, sleeve sum)`; drawdowns are positive fractions. Returns
    `(token, note)`."""
    losing = [w for w, (bk, _sl) in windows.items() if bk < 0]
    both = [w for w in losing if windows[w][1] < 0]
    lo, hi = t1_ci
    note = (f"book loses in {len(losing)} covered window(s) {losing or ''}; "
            f"sleeve loses in {len(both)} of them")
    if len(losing) < 2:
        note += ("; the book loses in fewer than 2 covered windows, so the window "
                 "clause cannot be met and the verdict is DIVERSIFIES or NO-TAIL-LINK alone")
    elif len(both) >= 2 and math.isfinite(hi) and hi < 0:
        return LOSES, note
    if math.isfinite(lo) and lo > 0 and dd_combined < dd_book:
        return DIVERSIFIES, note
    return NO_LINK, note


# ════════════════════════════════════════════════════════════════════════════
# The sleeve on a session axis
# ════════════════════════════════════════════════════════════════════════════

def sleeve_levels(cycles_: list[Cycle], days: list[date], sized: bool = False) -> list[float]:
    """Cumulative sleeve P&L on each of `days`: closed cycles at their final
    P&L, the open one at its latest mark on or before the day, later ones 0."""
    out = []
    srt = sorted(cycles_, key=lambda c: c.entry)
    held = [(c, c.held, c.size_1k if sized else 1) for c in srt]
    for d in days:
        tot = 0.0
        for c, h, n in held:
            if d < c.entry:
                break
            if d >= c.expiry:
                tot += c.pnl * n
            else:
                k = bisect_right(h, d) - 1
                tot += c.marks[h[k]] * n
        out.append(tot)
    return out


def open_on(cycles_: list[Cycle], d: date) -> Cycle | None:
    for c in cycles_:
        if c.entry <= d <= c.expiry:
            return c
    return None


def on_axis(cycles_: list[Cycle], axis: list[date], trading: list[date],
            sized: bool = False) -> list[float]:
    """Sleeve daily change on each axis session: its level at the last trading
    day on or before the session, differenced, starting from the level at the
    trading day before the first session."""
    if not axis:
        return []
    i0 = bisect_right(trading, axis[0]) - 1
    before = trading[i0 - 1] if i0 >= 1 else axis[0] - timedelta(days=1)
    pts = []
    for d in axis:
        k = bisect_right(trading, d) - 1
        pts.append(trading[k] if k >= 0 else d)
    lv = sleeve_levels(cycles_, [before] + pts, sized)
    return [b - a for a, b in zip(lv, lv[1:])]


# ════════════════════════════════════════════════════════════════════════════
# The book
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Book:
    label: str
    positions: list
    axis: list[date]
    daily: list[float]
    capital: float
    n_unmarkable: int
    mismatches: list
    marks: list = field(default_factory=list)   # per position: {session: $}


def make_book(label: str, positions, target: str, capital: float) -> Book:
    markable, bad, marks = [], 0, []
    for p in positions:
        try:
            sess, dol, _ = MC.position_marks(p)
        except (ValueError, KeyError, TypeError, IndexError):
            bad += 1
            continue
        markable.append(p)
        marks.append(dict(zip(sess, dol)))
    bc = MC.book_curves(markable, target=target)
    return Book(label, markable, list(bc.mtm.sessions), list(bc.mtm.daily), capital,
                bad, list(bc.mismatches), marks)


def deployed_book(recs, st, net_cap: float, label: str):
    from scripts.backtest_study.f4_deployment import account_sim as AS
    day_lists = P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)
    sim = AS.simulate(day_lists, st.cfg(label, compound=False, net_cap=net_cap),
                      cache=AS.new_cache())
    return make_book(label, sim.signal_pos, MC.TARGET_POSITION, st.capital)


def stored_book(recs, st):
    from scripts.backtest_study.f5_hedging.hedge_portfolio import book_positions
    picks = P.top_k_per_day(recs, P.ladder_rank, k=st.max_per_day,
                            eligible_fn=P.ladder_eligible)
    picks = [r for r in picks if r.get("days_held") is not None]
    return make_book("stored (TARGET_STORED, net)", book_positions(picks),
                     MC.TARGET_STORED, st.capital)


def o2_overlay(book: Book, sleeve: list[Cycle] | None, sized: bool = False) -> dict:
    """T5, computed directly: at the axis session where reserved capital is
    largest (book reserved plus the open condor's max loss), every open position
    is marked at minus its max loss. Returns the session and the loss as a share
    of the marked equity just before it."""
    axis = book.axis
    if not axis:
        return {}
    levels = np.cumsum(book.daily) if book.daily else np.array([])
    best = None
    for i, s in enumerate(axis):
        res = sum(p.reserved for p in book.positions if p.entry_sess <= s <= p.exit_sess)
        c = open_on(sleeve, s) if sleeve else None
        n = (c.size_1k if sized else 1) if c else 0
        if c is not None and c.max_loss:
            res += c.max_loss * n
        if best is None or res > best[0]:
            best = (res, i, c, n)
    res, i, c, n = best
    s = axis[i]
    prev = axis[i - 1] if i else None
    loss = 0.0
    n_open = 0
    for p, mk in zip(book.positions, book.marks):
        if p.entry_sess <= s <= p.exit_sess:
            n_open += 1
            m_prev = 0.0
            if prev is not None and p.entry_sess <= prev:
                ks = sorted(k for k in mk if k <= prev)
                m_prev = mk[ks[-1]] if ks else 0.0
            loss += m_prev + p.reserved
    eq = book.capital + (float(levels[i - 1]) if i else 0.0)
    if sleeve:
        prev_t = (prev if prev is not None else s - timedelta(days=1))
        eq += sleeve_levels(sleeve, [prev_t], sized)[0]
        if c is not None and c.max_loss:
            ks = [k for k in c.held if prev is not None and k <= prev]
            m_prev = c.marks[ks[-1]] * n if ks else 0.0
            loss += m_prev + c.max_loss * n
    return dict(session=s, reserved=res, open=n_open, condor=c is not None,
                equity=eq, loss=loss, share=loss / eq if eq > 0 else float("nan"))


def spy_returns(mk: Market) -> dict[date, float]:
    out = {}
    for i in range(1, len(mk.dates)):
        a, b = mk.spy[i - 1], mk.spy[i]
        if a and b:
            out[mk.dates[i]] = b / a - 1
    return out


def beta_fit(book: Book, rets: dict[date, float]) -> tuple[float, float, int]:
    xs, ys = [], []
    for s, v in zip(book.axis, book.daily):
        if s in rets:
            xs.append(rets[s])
            ys.append(v)
    if len(xs) < 3:
        return float("nan"), float("nan"), len(xs)
    beta, alpha = np.polyfit(np.asarray(xs), np.asarray(ys), 1)
    return float(beta), float(alpha), len(xs)


# ════════════════════════════════════════════════════════════════════════════
# One M3 read
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class M3:
    label: str
    common: int
    tail: TailStats
    alt: dict
    windows: dict
    covered: dict
    dd_book: float
    dd_comb: float
    dd_comb_1k: float
    token: str
    note: str


def in_window(d: date, a: str, b: str) -> bool:
    return date.fromisoformat(a) <= d <= date.fromisoformat(b)


def window_sleeve(sleeve: list[Cycle], trading: list[date], a: str, z: str) -> float:
    """Sleeve P&L over a window on its own trading days: the level at the last
    trading day on or before `z` less the level at the last one before `a`."""
    da, dz = date.fromisoformat(a), date.fromisoformat(z)
    i0 = bisect_right(trading, da - timedelta(days=1)) - 1
    i1 = bisect_right(trading, dz) - 1
    if i1 < 0:
        return 0.0
    start = trading[i0] if i0 >= 0 else da - timedelta(days=1)
    lv = sleeve_levels(sleeve, [start, trading[i1]])
    return lv[1] - lv[0]


def m3_read(label: str, book: Book, sleeve: list[Cycle], trading: list[date],
            alt_blocks=ALT_BLOCKS) -> M3:
    s_axis = np.asarray(on_axis(sleeve, book.axis, trading), float)
    s_axis_1k = np.asarray(on_axis(sleeve, book.axis, trading, sized=True), float)
    b = np.asarray(book.daily, float)
    opened = np.array([open_on(sleeve, d) is not None for d in book.axis], dtype=bool)
    bt, st_ = b[opened], s_axis[opened]
    tail = tail_stats(bt, st_, BLOCK)
    alt = {L: tail_stats(bt, st_, L) for L in alt_blocks}
    windows, covered = {}, {}
    for w, _name, a, z in WINDOWS:
        idx = [i for i, d in enumerate(book.axis) if in_window(d, a, z)]
        sl = window_sleeve(sleeve, trading, a, z)
        covered[w] = bool(idx)
        windows[w] = (float(b[idx].sum()) if idx else float("nan"), float(sl))
    graded = {w: windows[w] for w in GRADED_WINDOWS if covered[w]}
    cap = book.capital
    dd_b = PB.max_drawdown_fraction(b.tolist(), cap)
    dd_c = PB.max_drawdown_fraction((b + s_axis).tolist(), cap)
    dd_c1k = PB.max_drawdown_fraction((b + s_axis_1k).tolist(), cap)
    tok, note = verdict(graded, tail.t1_ci, dd_b, dd_c)
    return M3(label, int(opened.sum()), tail, alt, windows, covered, dd_b, dd_c, dd_c1k,
              tok, note)


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
# ════════════════════════════════════════════════════════════════════════════

def hdr(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _f(x, fmt="+.3f") -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return format(x, fmt)


def _ci(ci, fmt="+.2f") -> str:
    return f"[{_f(ci[0], fmt)}, {_f(ci[1], fmt)}]"


def print_m3(r: M3, full: bool = True) -> None:
    t = r.tail
    print(f"\n-- {r.label}")
    print(f"   common sessions with the sleeve open: {r.common}; worst 5% = "
          f"{tail_k(r.common, T1_TAIL)} sessions, worst decile = {tail_k(r.common, T3_TAIL)}")
    print(f"   T1 mean sleeve $/session on the book's worst 5%: {_f(t.t1, '+.2f')}  "
          f"CI95 {_ci(t.t1_ci)} (block {t.block})")
    print(f"   T3 corr all common sessions: {_f(t.r_all)}  CI95 {_ci(t.r_all_ci, '+.3f')};  "
          f"book's worst decile: {_f(t.r_tail)}  CI95 {_ci(t.r_tail_ci, '+.3f')}")
    for L, a in r.alt.items():
        print(f"      block {L:>2}: T1 CI95 {_ci(a.t1_ci)}  T3 all {_ci(a.r_all_ci, '+.3f')}  "
              f"T3 worst decile {_ci(a.r_tail_ci, '+.3f')}")
    print("   T2 windows (book $ on its sessions, sleeve $ on its own trading days):")
    for w, name, a, z in WINDOWS:
        bk, sl = r.windows[w]
        cov = "covered" if r.covered[w] else "no book"
        tag = " (beta proxy below; no verdict)" if w == "W1" else ""
        print(f"      {w} {name:<13} {a}..{z}  {cov:<8} book {_f(bk, '+,.0f'):>9}  "
              f"sleeve {_f(sl, '+,.0f'):>8}{tag}")
    print(f"   T4 realized max drawdown (fraction of $25,000): book {r.dd_book:.1%}  "
          f"book+sleeve(1) {r.dd_comb:.1%}  book+sleeve($1k size) {r.dd_comb_1k:.1%}")
    print(f"   {r.note}")
    print(f"   token: {r.token}")


def write_csv(path: Path, rows: list[Cycle]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["underlying", "arm", "short_delta", "fill", "status", "prev_expiry", "entry",
            "expiry", "dte", "spot_entry", "spot_expiry", "legs", "credit", "max_loss",
            "pnl", "mae", "mfe", "pnl_share", "mae_share", "mfe_share", "size_1k",
            "iv_entry", "rv", "vrp_price", "vrp_vol", "vix", "vix_pct", "vix_tercile",
            "junk_marks", "carried_marks", "bad_spot_days"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for c in rows:
            ok = c.status == "ok"
            dn = c.denom if ok else None
            w.writerow([
                c.ticker, c.arm, c.delta if c.delta is not None else "", c.fill, c.status,
                c.prev_expiry, c.entry, c.expiry, (c.expiry - c.entry).days,
                _r(c.spot_entry), _r(c.spot_T),
                " ".join(f"{'+' if lg.qty > 0 else '-'}{lg.strike:g}{lg.typ}" for lg in c.legs),
                _r(c.credit) if ok else "", _r(c.max_loss) if ok else "",
                _r(c.pnl) if ok else "", _r(c.mae) if ok else "", _r(c.mfe) if ok else "",
                _r(c.pnl / dn) if dn else "", _r(c.mae / dn) if dn else "",
                _r(c.mfe / dn) if dn else "", c.size_1k if ok and c.arm == "C" else "",
                _r(c.iv_entry), _r(c.rv), _r(c.vrp_price()), _r(c.vrp_vol()),
                _r(c.vix), _r(c.vix_pct), c.tercile or "", c.n_junk, c.n_carried,
                c.n_bad_spot])
    return len(rows)


def _r(x, nd=4):
    return "" if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(x, nd)


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def last_quote_date(ticker: str, cache_dir: Path = CACHE_DIR) -> date | None:
    best = None
    for f in cache_dir.glob(f"{ticker}_*_*.csv"):
        with open(f) as fh:
            fh.readline()
            line = fh.readline()
        try:
            d = date.fromisoformat(line[:10])
        except ValueError:
            continue
        best = d if best is None or d > best else best
    return best


def build_sleeve(mk: Market) -> tuple[dict, Counter, dict]:
    """Every (underlying, arm, delta, fill) -> list[Cycle], drop counts, last dates."""
    trading = mk.dates
    tset = mk.trading
    out: dict[tuple, list[Cycle]] = defaultdict(list)
    drops: Counter = Counter()
    lasts = {}
    variants = [("S", None, "mid"), ("S", None, "natural"),
                ("C", SHORT_DELTA, "mid"), ("C", SHORT_DELTA, "natural"),
                ("C", ALT_DELTA, "mid")]
    for t in UNDERLYINGS:
        last = last_quote_date(t)
        lasts[t] = last
        for prev, exp in cycles(FIRST_CYCLE, min(last, mk.dates[-1]), tset):
            entry = pick_entry(trading, prev, exp)
            ch = load_chain(t, exp)
            vix, pct = vix_percentile(mk, entry) if entry else (None, None)
            for arm, dl, fill in variants:
                if entry is None or not ch.rows:
                    c = Cycle(t, arm, dl, fill, prev, entry or exp, exp,
                              status="no_chain" if not ch.rows else "no_entry_day")
                else:
                    c = run_cycle(ch, t, prev, entry, exp, trading, arm, fill, dl)
                c.vix, c.vix_pct, c.tercile = vix, pct, tercile(pct)
                out[(t, arm, dl, fill)].append(c)
                drops[(t, arm, dl, fill, c.status)] += 1
    return out, drops, lasts


def ok(cs: list[Cycle]) -> list[Cycle]:
    return [c for c in cs if c.status == "ok"]


def print_m1(sleeve: dict) -> dict:
    hdr("M1 — THE VARIANCE RISK PREMIUM (context, no verdict)")
    print("   price form: (ATM straddle credit at mid - |S_T - K|) / S_entry, per cycle")
    print("   vol form:   IV_entry - RV in vol points (mean ATM IV; RV close-to-close,"
          " 252-day, zero-mean)")
    print(f"   CI95: iid bootstrap over cycles, {BOOT_N} draws, seed {SEED}")
    tokens = {}
    for t in UNDERLYINGS:
        cs = ok(sleeve[(t, "S", None, "mid")])
        print(f"\n   {t}  ({len(cs)} cycles)")
        print(f"   {'cut':<6}{'n':>4}  {'price mean':>11}{'median':>9}{'share+':>8}"
              f"{'CI95':>20}  {'vol mean':>9}{'median':>8}{'share+':>8}{'CI95':>18}")
        for cut in (None,) + TERCILES:
            sub = [c for c in cs if cut is None or c.tercile == cut]
            pv = [c.vrp_price() for c in sub if c.vrp_price() is not None]
            vv = [c.vrp_vol() for c in sub if c.vrp_vol() is not None]
            plo, phi = iid_ci(pv)
            vlo, vhi = iid_ci(vv)
            print(f"   {cut or 'all':<6}{len(sub):>4}  "
                  f"{_f(np.mean(pv) if pv else None, '+.4f'):>11}"
                  f"{_f(float(np.median(pv)) if pv else None, '+.4f'):>9}"
                  f"{_f(np.mean([x > 0 for x in pv]) if pv else None, '.2f'):>8}"
                  f"  [{_f(plo, '+.4f')}, {_f(phi, '+.4f')}]"
                  f"  {_f(np.mean(vv) if vv else None, '+.2f'):>9}"
                  f"{_f(float(np.median(vv)) if vv else None, '+.2f'):>8}"
                  f"{_f(np.mean([x > 0 for x in vv]) if vv else None, '.2f'):>8}"
                  f"  [{_f(vlo, '+.2f')}, {_f(vhi, '+.2f')}]")
            if cut is None:
                tokens[t] = premium_token(plo)
        n_noiv = sum(1 for c in cs if c.iv_entry is None)
        print(f"   cycles with no usable entry IV on both ATM legs (vol form blank): {n_noiv}")
        print(f"   {t} premium token: {tokens[t]}")
    return tokens


def print_m2(sleeve: dict) -> None:
    hdr("M2 — ARM P&L WITH MFE AND MAE (context, no verdict)")
    print("   $ per 1 contract (straddle: 1 call + 1 put). share = of max loss (condor)"
          " or of credit (straddle).")
    print(f"   {'und':<4}{'arm':<5}{'delta':<6}{'fill':<8}{'cut':<5}{'n':>4}{'mean $':>9}"
          f"{'win':>6}{'mean sh':>9}{'MAE sh':>8}{'MFE sh':>8}{'worst $':>10}{'sum $':>10}")
    for (t, arm, dl, fill), cs_all in sleeve.items():
        cs = ok(cs_all)
        for cut in (None,) + TERCILES:
            sub = [c for c in cs if cut is None or c.tercile == cut]
            if not sub:
                continue
            sh = [c.pnl / c.denom for c in sub if c.denom]
            mae = [c.mae / c.denom for c in sub if c.denom]
            mfe = [c.mfe / c.denom for c in sub if c.denom]
            print(f"   {t:<4}{arm:<5}{_f(dl, '.2f') if dl else '-':<6}{fill:<8}"
                  f"{cut or 'all':<5}{len(sub):>4}{np.mean([c.pnl for c in sub]):>+9.0f}"
                  f"{np.mean([c.pnl > 0 for c in sub]):>6.2f}{_f(np.mean(sh), '+.3f'):>9}"
                  f"{_f(np.mean(mae), '+.3f'):>8}{_f(np.mean(mfe), '+.3f'):>8}"
                  f"{min(c.pnl for c in sub):>+10.0f}{sum(c.pnl for c in sub):>+10.0f}")
    print("\n   worst 5 cycles per underlying x arm (mid fill, condor at 0.16), listed by date:")
    for t in UNDERLYINGS:
        for arm, dl in (("S", None), ("C", SHORT_DELTA)):
            cs = ok(sleeve[(t, arm, dl, "mid")])
            worst = sorted(sorted(cs, key=lambda c: c.pnl)[:5], key=lambda c: c.expiry)
            print(f"   {t} ARM {arm}:")
            for c in worst:
                legs = " ".join(f"{'+' if lg.qty > 0 else '-'}{lg.strike:g}{lg.typ}"
                                for lg in c.legs)
                print(f"      entry {c.entry} exp {c.expiry}  {legs:<34} credit "
                      f"{c.credit:6.2f}  pnl {c.pnl:+8.0f}  MAE {c.mae:+8.0f}  "
                      f"MFE {c.mfe:+6.0f}  VIX {_f(c.vix, '.1f')} ({c.tercile or '—'})")


def print_census(sleeve: dict, drops: Counter, lasts: dict) -> None:
    hdr("SLEEVE CENSUS — cycles built and dropped (read before any outcome)")
    for t in UNDERLYINGS:
        print(f"   {t}: last cached quote date {lasts[t]}")
    for key, cs in sleeve.items():
        t, arm, dl, fill = key
        st = Counter(c.status for c in cs)
        nok = st.pop("ok", 0)
        junk = sum(c.n_junk for c in ok(cs))
        carried = sum(c.n_carried for c in ok(cs))
        bad = sum(c.n_bad_spot for c in ok(cs))
        print(f"   {t} ARM {arm} {('d' + format(dl, '.2f')) if dl else 'ATM  '} {fill:<8}"
              f" cycles {len(cs)}  kept {nok}  dropped {dict(st) or 0}  "
              f"junk-quote marks {junk}  carried marks {carried}  bad-spot days {bad}")
    c0 = ok(sleeve[("SPY", "C", SHORT_DELTA, "mid")])
    if c0:
        print(f"   SPY condor first/last kept: entry {c0[0].entry} .. expiry {c0[-1].expiry}; "
              f"DTE at entry {Counter((c.expiry - c.entry).days for c in c0).most_common(4)}")
        mls = sorted(c.max_loss for c in c0)
        print(f"   SPY condor max loss $/contract: min {mls[0]:.0f}  median "
              f"{mls[len(mls) // 2]:.0f}  max {mls[-1]:.0f};  $1k size: "
              f"{dict(sorted(Counter(c.size_1k for c in c0).items()))}")
    tc = Counter(c.tercile for c in ok(sleeve[("SPY", "S", None, "mid")]))
    print(f"   SPY straddle cycles per VIX tercile: {dict(tc)}")


def main() -> int:
    from scripts.backtest_study.f4_deployment import account_sim as AS
    from scripts.backtest_study.lib.book import load_book

    print("index_vrp — does short index vol lose in the same weeks as the long-delta ladder?")
    print(f"registration: {REGISTRATION} (accepted by default {ACCEPTED})")
    print(f"seed {SEED}; bootstrap {BOOT_N} paths; T1/T3 stationary blocks mean {BLOCK} "
          f"(also {ALT_BLOCKS}); T4 blocks {DD_BLOCKS}")
    print(f"commission ${COMMISSION:.2f} per contract per side (entry and expiry), "
          f"fills at mid; natural printed beside")
    try:
        import yaml
        yml = yaml.safe_load(BACKTEST_YML.read_text()) or {}
        cpc = (yml.get("simulation") or {}).get("commission_per_contract")
        print(f"config/backtest.yml commission_per_contract: {cpc}")
    except Exception as exc:  # noqa: BLE001 — a print, never a gate
        print(f"config/backtest.yml not read ({exc.__class__.__name__})")
    print("Cache only, no fetch, no model price. Nothing ships from this study.")

    mk = load_market()
    trading = mk.dates
    print(f"VIX / SPY calendar: {VIX_CSV.relative_to(ROOT)}, {trading[0]} .. {trading[-1]}")

    sleeve, drops, lasts = build_sleeve(mk)
    print_census(sleeve, drops, lasts)

    # --- the book ---------------------------------------------------------
    st = AS.load_settings(AS.DEFAULT_CONFIG)
    recs, diag = load_book()
    era = diag.get("era")
    hdr(f"THE BOOK — era {era}")
    print(f"   {era_mod.seal_line(diag.get('seal', {'rows': 0, 'dates': 0}))}  "
          f"(this study is not a named seal reader)")
    print(f"   load_book: {len(recs)} rows on {len({r['date'] for r in recs})} signal dates")
    print(f"   account_sim: capital ${st.capital:,.0f}, risk {st.risk_pct:.0%}, per-position "
          f"{st.per_pos_cap:.2f}, net cap {REGISTERED_NET_CAP:.2f} (registered cell; the yml "
          f"carries {st.net_cap:.2f}, printed as an unregistered line below), ARM R, F1, no "
          f"compounding")
    book = deployed_book(recs, st, REGISTERED_NET_CAP, "deployed (TARGET_POSITION, gross)")
    print(f"   deployed book: {len(book.positions)} positions marked, {book.n_unmarkable} "
          f"unmarkable dropped; sessions {book.axis[0]} .. {book.axis[-1]} ({len(book.axis)})")
    print(f"   G-MTM (TARGET_POSITION): {'PASS' if not book.mismatches else 'FAIL'}"
          f" ({len(book.mismatches)} mismatches)")
    if book.mismatches:
        print("\nREFUSED — G-MTM failed on the graded book; the tolerance is never widened.")
        return EXIT_GMTM

    sleeve_spy = ok(sleeve[("SPY", "C", SHORT_DELTA, "mid")])
    tokens_m1 = print_m1(sleeve)
    print_m2(sleeve)

    hdr("M3 — TAIL OVERLAP WITH THE BOOK (graded: SPY condor, d0.16, mid, v4 deployed)")
    graded = m3_read(f"GRADED: SPY condor d0.16 mid vs {era} deployed book", book,
                     sleeve_spy, trading)
    print_m3(graded)

    # T4 bands
    s1 = np.asarray(on_axis(sleeve_spy, book.axis, trading), float)
    s1k = np.asarray(on_axis(sleeve_spy, book.axis, trading, sized=True), float)
    b = np.asarray(book.daily, float)
    print("\n   T4 block-bootstrap bands (path_bootstrap.bootstrap_drawdown_blocks, "
          f"capital ${book.capital:,.0f}, {BOOT_N} resamples, seed {SEED}):")
    for lab, series in (("book alone", b), ("book + sleeve (1 contract)", b + s1),
                        ("book + sleeve ($1k size)", b + s1k)):
        bands = PB.bootstrap_drawdown_blocks(series.tolist(), book.capital, BOOT_N, SEED,
                                             blocks=DD_BLOCKS)
        for line in PB.format_block(bands, lab):
            print("   " + line)

    # T5
    print("\n   T5 O2 total-loss overlay — computed directly (ruin_walk._shock is not"
          " reused: the book's ruin_walk.Table holds only ladder candidates and cannot"
          " carry a sleeve position)")
    for lab, sl, sized in (("book alone", None, False), ("book + sleeve (1)", sleeve_spy, False),
                           ("book + sleeve ($1k)", sleeve_spy, True)):
        o = o2_overlay(book, sl, sized)
        print(f"      {lab:<20} session {o['session']}  reserved ${o['reserved']:,.0f}  "
              f"open book positions {o['open']}  condor open {o['condor']}  equity before "
              f"${o['equity']:,.0f}  loss ${o['loss']:,.0f} = {o['share']:.1%} of equity")

    # W1 beta proxy
    rets = spy_returns(mk)
    beta, alpha, nfit = beta_fit(book, rets)
    w1 = [d for d in rets if in_window(d, "2022-01-01", "2022-12-31")]
    proxy = beta * sum(rets[d] for d in w1)
    print(f"\n   W1 beta proxy (descriptive, fitted on later data, no verdict): book $/session "
          f"= {alpha:+.1f} + {beta:,.0f} x SPY return over {nfit} sessions; applied to "
          f"{len(w1)} 2022 sessions: beta x sum(return) = ${proxy:+,.0f} (intercept left "
          f"out); sleeve W1 ${graded.windows['W1'][1]:+,.0f}")

    # --- secondaries -------------------------------------------------------
    hdr("SECONDARY TOKENS — printed, no verdict")
    secondary = {}
    sec_specs = [
        ("GLD condor d0.16 mid vs deployed", ok(sleeve[("GLD", "C", SHORT_DELTA, "mid")]), book),
        ("SPY condor d0.16 natural vs deployed",
         ok(sleeve[("SPY", "C", SHORT_DELTA, "natural")]), book),
        ("SPY condor d0.30 mid vs deployed (contested delta)",
         ok(sleeve[("SPY", "C", ALT_DELTA, "mid")]), book),
    ]
    stored = stored_book(recs, st)
    print(f"   stored book: {len(stored.positions)} positions, {stored.n_unmarkable} "
          f"unmarkable, G-MTM (TARGET_STORED) "
          f"{'PASS' if not stored.mismatches else f'FAIL ({len(stored.mismatches)})'}")
    if stored.mismatches:
        secondary["SPY condor d0.16 mid vs stored book"] = "NOT EVALUABLE (G-MTM)"
    else:
        sec_specs.append(("SPY condor d0.16 mid vs stored book", sleeve_spy, stored))
    yml_book = deployed_book(recs, st, st.net_cap, f"deployed at yml net {st.net_cap:.2f}")
    if not yml_book.mismatches and abs(st.net_cap - REGISTERED_NET_CAP) > 1e-9:
        sec_specs.append((f"SPY condor d0.16 mid vs deployed at yml net {st.net_cap:.2f} "
                          f"(NOT REGISTERED)", sleeve_spy, yml_book))
    try:
        recs3, diag3 = load_book(era="v3")
    except SystemExit as exc:
        print(f"   v3 not loaded: era refusal, exit {exc.code} (not an error)")
    else:
        b3 = deployed_book(recs3, st, REGISTERED_NET_CAP, "v3 deployed")
        print(f"   v3 deployed book: {len(b3.positions)} positions, sessions "
              f"{b3.axis[0]} .. {b3.axis[-1]}, G-MTM "
              f"{'PASS' if not b3.mismatches else f'FAIL ({len(b3.mismatches)})'}")
        if b3.mismatches:
            secondary["SPY condor d0.16 mid vs v3 deployed"] = "NOT EVALUABLE (G-MTM)"
        else:
            sec_specs.append((f"SPY condor d0.16 mid vs {diag3.get('era')} deployed (replication)",
                              sleeve_spy, b3))
    for lab, sl, bk in sec_specs:
        r = m3_read(lab, bk, sl, trading)
        print_m3(r)
        secondary[lab] = r.token
    for L in ALT_BLOCKS:
        a = graded.alt[L]
        g = {w: graded.windows[w] for w in GRADED_WINDOWS if graded.covered[w]}
        secondary[f"graded read at T1 block {L}"] = verdict(g, a.t1_ci, graded.dd_book,
                                                            graded.dd_comb)[0]

    # --- CSV ---------------------------------------------------------------
    n = write_csv(OUT_CSV, [c for cs in sleeve.values() for c in cs])
    print(f"\nper-cycle CSV: {OUT_CSV.relative_to(ROOT)} ({n} rows, every arm, fill and"
          f" delta, dropped cycles included with their status)")

    hdr("VERDICT")
    for t in UNDERLYINGS:
        print(f"  M1 premium (context) {t}: {tokens_m1[t]}")
    print(f"  {graded.note}")
    print(f"  T1 {_f(graded.tail.t1, '+.2f')} CI95 {_ci(graded.tail.t1_ci)}; T4 max DD book "
          f"{graded.dd_book:.1%} vs book+sleeve {graded.dd_comb:.1%}")
    print(f"  >>> index_vrp {graded.token} (SPY condor d0.16, mid fill, {era} deployed book) <<<")
    for lab, tok in secondary.items():
        print(f"  secondary, {lab}: {tok}")
    print("  Nothing ships.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
