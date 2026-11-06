"""daily_vol_structure — daily straddles and 1x2 ratios on QQQ and SMH, read against features.

Registration: `research/pre-registrations/f3_structure/daily_vol_structure.md`
(accepted by default 2026-11-06, before any QQQ or SMH option outcome was read).
That file is the spec; every constant and verdict word here is its. RESEARCH
TIER: nothing ships from this study.

WHAT IT COMPUTES. Every session D in the window, on each of QQQ and SMH and on
each of two tenors, it opens three structures: a long ATM straddle (S), a call
ratio (RC) and a put ratio (RP). Features are known at D's close; every leg
fills at the D+1 closing mid; each trade closes a fixed number of sessions
later. That gives 12 outcome series. T30 and T7 are labels: true DTE at the fill
runs 21-53 and 6-11.

ONE SIGNED SERIES. On the same strikes a front ratio is exactly minus a back
ratio at mid, before commission. So each ratio series stores the BACK ratio's
gross P&L, and the front ratio is `-y`. Every correlation is run once on that
series. To keep the identity exact each leg has ONE price: the closing mid from
`simulate.entry_day_fill(row, +1)`. A bought-side call returns the mid for a
normal or a wide two-sided quote and refuses a quote with no bid, so a junk leg
cannot price differently for the two sides. Commission, the strict touch and the
front-only side-aware print differ by side and are computed per side.

OWN FIXED EXIT. `run_trade` closes every leg at the exit session's mark. It
never calls the frozen harness or `_simulate`, so a credit entry cannot reach
the `CREDIT_PROD` exit profile.

THE GATE. `Book.price` and `Book.option_row` raise until `Book.open_outcomes`
has seen no problem: no trade in ANY ticker and tenor awaiting a contract, OHLC
reaching the window's end, and `Price~` agreeing with the closes. It is
all-or-nothing, so a partly cached leg set cannot produce a partial figure.
While it is shut the run prints coverage counts and `NOT BUILT — AWAITING
SCRAPE`, and writes nothing.

THE TEST. Discovery ranks the 144 price, vol and volume cells by Spearman against
a circular-shift null (`forward_drawdown.circular_shift_null`), which keeps both
series' own autocorrelation, then Benjamini-Hochberg. Confirmation reads the same
null on later dates with cuts frozen on discovery rows. The 108 analysis cells
are outside all of this and print as `RETRO-ONLY`. Three MARKET features have
their own LIVE-rows read.

REUSED, NEVER COPIED. Entry: `simulate.entry_day_fill`,
`_monotonicity_violation`. Exit mark: `selloff_put_diagonal.leg_mark` (shared
`_snap_asof`, `_is_junk_quote`, `junk_day_mark`). Grid: `mechanical_benchmark`'s
`grid_around`, `listed_by`, `monthly_expiries`. Label and lag:
`market_read.parse_label`, `lag_bin`. BH: `regime_map.bh_q`. Holm:
`selloff_put_diagonal.holm`. Statistics: `lib/forward_drawdown` and
`lib/pbo.py::cscv`. Era and seal: `lib/era.py`.
`E-VOL`: `lib/mech_regime.py`, unchanged. No model price anywhere.

Usage:
  python3 -m scripts.backtest_study run daily_vol_structure
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import math
import random
import re
import statistics
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import MechLabeler  # noqa: E402
from scripts.backtest import simulate as SIM  # noqa: E402
from lib.barchart.options import cache_path  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_baseline as MBL  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f1_selection.regime import market_read as MR  # noqa: E402
from scripts.backtest_study.f1_selection.regime import regime_map as RM  # noqa: E402
from scripts.backtest_study.f1_selection.regime import selloff_put_diagonal as SPD  # noqa: E402
from scripts.backtest_study.f3_structure import index_vrp as IV  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import forward_drawdown as FD  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib import underlying as UND  # noqa: E402

REGISTRATION = "research/pre-registrations/f3_structure/daily_vol_structure.md"
ACCEPTED = "2026-11-06"

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# ── registered constants (the registration's numbers; never re-chosen) ──────
TICKERS = ("QQQ", "SMH")
WINDOW = (date(2024, 3, 15), date(2026, 9, 22))
FORWARD_START = date(2026, 9, 23)
#: First signal date of the last 40% of the window's 632 sessions (index 379).
FIRST_CONFIRM = date(2025, 9, 19)
DISCOVERY_SHARE = 0.60
COMMISSION = 0.65            # $ per contract per side
SEED = 20261106
BOOT_N = 10_000
SHIFT_N = 1_000              # circular-shift draws per test
MIN_SHIFT = 21               # sessions; every rotation moves x this far from its y
BLOCK = 21                   # rows; at least the hold of both tenors
BH_Q = 0.10
#: Every confirming read, confirmation and the LIVE read, uses this bar.
CONFIRM_Q = 0.05
ALPHA = 0.05
PBO_S = 16
ANALYSIS_ERA = "v4"
ERA_MIN_DATES = 60
#: Power floors, per cell.
MIN_DATES = 60
MIN_BLOCKS = 6
MIN_ARM_DATES = 12
MIN_ARM_BLOCKS = 3
#: A position's arm needs three full blocks, or its block bootstrap p means little.
MIN_POSITION_ROWS = 63
#: Above this share of a series or an arm, exit drops are re-graded at the adverse
#: touch: UNDERPOWERED if the verdict changes, or a short leg has no ask to bound it.
EXIT_DROP_MAX = 0.05
EXIT_DROPS = ("no_exit_quote", "stale_exit_mark")
#: T30's DTE buckets; T7's are the fill's weekday. A bucket counts when each arm
#: has this many rows, and the clause needs two buckets. The row-weighted average
#: of the buckets' contrasts must keep at least this share of the overall contrast.
DTE_BUCKETS = ((21, 30), (31, 38), (39, 53))
BUCKET_MIN_ARM = 5
BUCKET_MIN_N = 2
CYCLE_MIN_SHARE = 0.5
#: Prior sessions a 20-session mean needs.
MEAN_MIN_PRIOR = 15
#: A weekly expiry with no cached row by the decision day is proven unlisted once
#: this many distinct strikes within `NEAR_ATM` of spot are skip-listed on
#: evidence. The rule never applies to a monthly.
EXPIRY_UNLISTED_PROOF = 3
NEAR_ATM = 0.02
#: A cached file written before the scraper's range fix (2026-09-09) may be
#: shallow, so a missing early row means re-fetch it, not "not listed yet".
DEPTH_TRUST = date(2026, 9, 9)
#: A re-fetch asks for this many days before D, past `history`'s 5-day tolerance.
REFETCH_MARGIN = 6
#: `Price~` against the close: a run this long, this far off 1, refuses.
SPLIT_TOL = 0.10
SPLIT_RUN = 3
#: Two sell-off windows, by signal date. Removed in a printed robustness line.
SELLOFF_WINDOWS = ((date(2025, 3, 1), date(2025, 4, 30)),
                   (date(2026, 2, 1), date(2026, 4, 30)))

NOT_BUILT = "NOT BUILT — AWAITING SCRAPE"
CANDIDATE, CONTRARY, NULL, UNDERPOWERED = "CANDIDATE", "CONTRARY", "NULL", "UNDERPOWERED"
STILL_OPEN = "STILL-OPEN"
RETRO_ONLY = "RETRO-ONLY"
FRONT_CAVEAT = ("On a front ratio, `CANDIDATE` means a positive sample mean only. It says "
                "nothing about tail loss, margin or return on capital.")
STRADDLE_CAVEAT = ("A long-straddle `CONTRARY` is not evidence for selling straddles, because "
                   "no such side is graded.")

VIX_TABLE = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"
BASELINE_CSV = ROOT / "backtests" / "to_evaluate" / "analysis - BaselineDaily.csv"
OUT_DIR = ROOT / "backtests" / "study_output"
TRADES_CSV = OUT_DIR / "daily_vol_structure-trades.csv"


@dataclasses.dataclass(frozen=True)
class Tenor:
    name: str
    target_dte: int
    min_dte: int
    hold: int
    weekly: bool


T30 = Tenor("T30", 30, 21, 5, False)
T7 = Tenor("T7", 7, 5, 2, True)
TENORS = (T30, T7)
WING = {("QQQ", "T30"): 0.05, ("SMH", "T30"): 0.09,
        ("QQQ", "T7"): 0.025, ("SMH", "T7"): 0.045}
#: The fixed strike step, frozen against cache growth (Resolved at build).
STEP = {("QQQ", "T30"): 1.0, ("QQQ", "T7"): 1.0, ("SMH", "T30"): 2.5, ("SMH", "T7"): 2.5}
STRUCTURES = ("S", "RC", "RP")
#: The sides of a series. The ratio series stores the back ratio.
SIDES = {"S": ("long",), "RC": ("back", "front"), "RP": ("back", "front")}
CONTRACTS = {"S": 2, "RC": 3, "RP": 3}


class AwaitingScrape(RuntimeError):
    """The gate is shut: no outcome may be computed."""


# ════════════════════════════════════════════════════════════════════════════
# The feature list, fixed here
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass(frozen=True)
class Feature:
    """`kind`: `rank` (top minus bottom tercile by rank) or `cut` (top means
    x >= hi, bottom means x <= lo). A discrete feature is a `cut`, because a
    rank tercile would split tied values by position."""
    name: str
    group: str
    kind: str = "rank"
    lo: float | None = None
    hi: float | None = None
    qqq_only: bool = False
    source: str = "market"        # market | option | analysis_market | analysis_ticker | baseline

    @property
    def is_analysis(self) -> bool:
        return self.source.startswith("analysis")


FEATURES = (
    Feature("ret1", "price"),
    Feature("ret5", "price"),
    Feature("ret20", "price"),
    Feature("dist50", "price"),
    Feature("range_atr", "price"),
    Feature("evol", "price", "cut", 0, 1),
    Feature("rv5_rv20", "vol"),
    Feature("iv_rv20", "vol", source="option"),
    Feature("iv_chg5", "vol", source="option"),
    Feature("und_vol", "volume"),
    Feature("opt_vol", "volume", source="option"),
    Feature("qqq_prem", "volume", qqq_only=True, source="baseline"),
    Feature("qqq_cp", "volume", qqq_only=True, source="baseline"),
    Feature("mkt_dir", "analysis", "cut", 0, 1, source="analysis_market"),
    Feature("mkt_vol", "analysis", "cut", 2, 3, source="analysis_market"),
    Feature("mkt_risk", "analysis", "cut", 0, 1, source="analysis_market"),
    Feature("mkt_hp", "analysis", "cut", 0, 1, source="analysis_market"),
    Feature("mkt_hp_score", "analysis", source="analysis_market"),
    Feature("mkt_flow", "analysis", "cut", 2, 4, source="analysis_market"),
    Feature("tk_dir", "analysis", "cut", 0, 1, source="analysis_ticker"),
    Feature("tk_vol", "analysis", "cut", 2, 3, source="analysis_ticker"),
    Feature("tk_flow", "analysis", "cut", 3, 4, source="analysis_ticker"),
)
FEATURE_BY_NAME = {f.name: f for f in FEATURES}
#: Frozen before any outcome: the MARKET features with a LIVE-rows read.
SHORTLIST = ("mkt_dir", "mkt_vol", "mkt_hp_score")


def features_for(ticker: str) -> list[Feature]:
    return [f for f in FEATURES if ticker == "QQQ" or not f.qqq_only]


def series_keys() -> list[tuple[str, str, str]]:
    return [(tk, t.name, s) for tk in TICKERS for t in TENORS for s in STRUCTURES]


def all_cells() -> list[tuple[str, str, str, str]]:
    return [(tk, tn, s, f.name) for tk, tn, s in series_keys() for f in features_for(tk)]


def graded_cells() -> list[tuple[str, str, str, str]]:
    """The 144 cells in the BH family: price, vol and volume."""
    return [c for c in all_cells() if not FEATURE_BY_NAME[c[3]].is_analysis]


def analysis_cells() -> list[tuple[str, str, str, str]]:
    """The 108 cells that only print, as `RETRO-ONLY`."""
    return [c for c in all_cells() if FEATURE_BY_NAME[c[3]].is_analysis]


def shortlist_cells() -> list[tuple[str, str, str, str]]:
    """The 36 cells of the LIVE-rows read."""
    return [c for c in all_cells() if c[3] in SHORTLIST]


# ════════════════════════════════════════════════════════════════════════════
# Calendar and expiries
# ════════════════════════════════════════════════════════════════════════════

def split_index(n: int) -> int:
    """How many of `n` chronological dates form the discovery set."""
    return int(n * DISCOVERY_SHARE)


def in_selloff_window(d: date) -> bool:
    return any(a <= d <= b for a, b in SELLOFF_WINDOWS)


def dte_bucket(dte: int) -> int | None:
    for i, (a, b) in enumerate(DTE_BUCKETS):
        if a <= dte <= b:
            return i
    return None


def cycle_bucket(tenor_name: str, row: dict):
    """The bucket the expiry-cycle clause reads: DTE on T30, the fill's weekday on T7."""
    return dte_bucket(row["dte"]) if tenor_name == "T30" else row["wd"]


def weekly_expiries(lo: date, hi: date, sessions: set[date], last_session: date) -> list[date]:
    """Friday expiries in `[lo, hi]`, moved to Thursday when the Friday is a
    holiday. A Friday past the calendar's last session is taken as listed."""
    out, d = [], lo - timedelta(days=1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    while d <= hi + timedelta(days=1):
        e = d
        if d <= last_session and d not in sessions:
            e = d - timedelta(days=1)
        if lo <= e <= hi:
            out.append(e)
        d += timedelta(days=7)
    return out


def pick_expiry(tenor: Tenor, fill: date, sessions: set[date], last_session: date) -> date | None:
    """The expiry nearest the target DTE, counted from the fill, at or above the
    minimum DTE. Ties go to the earlier expiry."""
    lo, hi = fill + timedelta(days=tenor.min_dte), fill + timedelta(days=tenor.min_dte + 70)
    cands = (weekly_expiries(lo, hi, sessions, last_session) if tenor.weekly
             else MB.monthly_expiries(lo, hi))
    if not cands:
        return None
    return min(cands, key=lambda e: (abs((e - fill).days - tenor.target_dte), e))


# ════════════════════════════════════════════════════════════════════════════
# Strike walk — probed, never inferred from a sparse cache
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass
class Sel:
    """One strike choice. `status`: built | await | drop."""
    status: str
    strike: float | None = None
    reason: str = ""
    fetch: tuple = ()                  # ((opt, expiry, strike), ...)
    refetch: tuple = ()                # the part of `fetch` that is a shallow cached file


def _leg(ticker: str, opt: str, expiry: date, strike: float, qty: int = 1) -> Leg:
    return Leg(qty, ticker, expiry, float(strike), opt)


def file_fetched_on(ticker: str, expiry: date, strike: float, opt: str) -> date | None:
    """The cached file's write date (`history.is_forward_stale` also reads mtime)."""
    p = cache_path(HISTORY_CACHE, ticker, expiry, strike, opt)
    return date.fromtimestamp(p.stat().st_mtime) if p.exists() else None


def depth_trusted(ticker: str, expiry: date, strike: float, opt: str) -> bool:
    on = file_fetched_on(ticker, expiry, strike, opt)
    return on is not None and on >= DEPTH_TRUST


def walk_strike(chain, evidence: set[str], ticker: str, expiry: date, target: float,
                step: float, asof: date, opts: tuple[str, ...]) -> Sel:
    """The multiple of the fixed `step` nearest `target` that lists every type in
    `opts`, nearest first. The cache never changes the grid, so a later fetch by
    any study cannot move a strike.

    Cached with a row on or before `asof`: chosen, before the skip-list is read, so a
    later skip-list entry cannot move a strike on a date with real rows. Skip-listed
    on evidence: step on. Cached without such a row: a file fetched after the range
    fix was not listed yet, so step on; an older one may be shallow, so AWAIT a
    re-fetch. Uncached: AWAIT.
    """
    for k in MB.grid_around(target, step, []):
        all_cached = all(chain.cached(ticker, expiry, k, o) for o in opts)
        if all_cached and all(MB.listed_by(chain, _leg(ticker, o, expiry, k), asof) for o in opts):
            return Sel("built", k)
        if any(NTF.contract_stem(ticker, expiry, k, o) in evidence for o in opts):
            continue
        missing = tuple((o, expiry, k) for o in opts if not chain.cached(ticker, expiry, k, o))
        if missing:
            return Sel("await", k, "strike_not_cached", missing)
        unlisted = [o for o in opts if not MB.listed_by(chain, _leg(ticker, o, expiry, k), asof)]
        shallow = tuple((o, expiry, k) for o in unlisted
                        if not depth_trusted(ticker, expiry, k, o))
        if shallow:
            return Sel("await", k, "shallow_refetch", shallow, shallow)
    return Sel("drop", reason="no_listed_strike")


class Listing:
    """Is an expiry listed by a date? Memoised first-row dates, and the strikes
    skip-listed per expiry."""

    def __init__(self, chain, evidence: set[str]):
        self.chain = chain
        self._first: dict[tuple[str, date], date | None] = {}
        self.proven: dict[tuple[str, str], set[float]] = {}
        for stem in evidence:
            parts = stem.split("_")
            if len(parts) == 3:
                try:
                    self.proven.setdefault((parts[0], parts[1]), set()).add(float(parts[2][:-1]))
                except ValueError:
                    continue

    def first_row(self, ticker: str, expiry: date) -> date | None:
        key = (ticker, expiry)
        if key not in self._first:
            best = None
            for k, cps in self.chain.idx.get(key, {}).items():
                for cp in cps:
                    series, details = self.chain.history(
                        _leg(ticker, "Call" if cp == "C" else "Put", expiry, k))
                    days = [d for d, _ in series] + list(details)
                    if days:
                        m = min(days)
                        best = m if best is None else min(best, m)
            self._first[key] = best
        return self._first[key]

    def state(self, ticker: str, expiry: date, asof: date, spot: float) -> str:
        """`yes`, `no` or `unknown`. Unknown means walk the strikes; the walk names
        the contracts to fetch. `no` applies to a weekly only: a missing strike is
        not a missing expiry, so it takes three near-ATM strikes skip-listed on
        evidence. A monthly is always walked."""
        first = self.first_row(ticker, expiry)
        if first is not None and first <= asof:
            return "yes"
        if expiry in MB.monthly_expiries(expiry, expiry):
            return "unknown"
        near = {k for k in self.proven.get((ticker, expiry.strftime("%Y%m%d")), ())
                if abs(k / spot - 1.0) <= NEAR_ATM}
        return "no" if len(near) >= EXPIRY_UNLISTED_PROOF else "unknown"


@dataclasses.dataclass
class Trade:
    ticker: str
    tenor: Tenor
    signal: date
    fill: date | None
    exit: date | None
    status: str                        # built | await | drop | open
    reason: str = ""
    expiry: date | None = None
    spot: float | None = None          # D's close
    atm: float | None = None
    wing_c: float | None = None
    wing_p: float | None = None
    fetch: tuple = ()
    refetch: tuple = ()                # the part of `fetch` that is a shallow cached file
    found: tuple = ()                  # contracts this trade needs that are cached


def select_trade(chain, evidence, listing: Listing, ticker: str, tenor: Tenor, signal: date,
                 sessions: list[date], index: dict[date, int], bars: dict) -> Trade:
    """Strikes and expiry for one signal date. Reads only D's close and the
    listing as of D. No price, and nothing dated after D."""
    i = index.get(signal)
    if i is None or i + 1 + tenor.hold >= len(sessions):
        return Trade(ticker, tenor, signal, None, None, "open", "open_at_data_end")
    fill, exit_day = sessions[i + 1], sessions[i + 1 + tenor.hold]
    tr = Trade(ticker, tenor, signal, fill, exit_day, "drop")
    bar = bars.get(signal)
    if bar is None:
        tr.reason = "no_bar"
        if not bars or signal > max(bars):
            tr.status, tr.reason = "await", "no_ohlc_bar"
        return tr
    spot = bar.c
    tr.spot = spot
    expiry = pick_expiry(tenor, fill, set(sessions), sessions[-1])
    if expiry is None:
        tr.reason = "no_expiry"
        return tr
    tr.expiry = expiry
    if listing.state(ticker, expiry, signal, spot) == "no":
        tr.reason = "expiry_not_listed"
        return tr
    x = WING[(ticker, tenor.name)]
    step = STEP[(ticker, tenor.name)]
    atm = walk_strike(chain, evidence, ticker, expiry, spot, step, signal, ("Call", "Put"))
    wc = walk_strike(chain, evidence, ticker, expiry, spot * (1 + x), step, signal, ("Call",))
    wp = walk_strike(chain, evidence, ticker, expiry, spot * (1 - x), step, signal, ("Put",))
    sels = (atm, wc, wp)
    for s in sels:
        if s.status == "drop":
            tr.reason = s.reason
            return tr
    tr.fetch = tuple(f for s in sels for f in s.fetch)
    tr.refetch = tuple(f for s in sels for f in s.refetch)
    found = []
    if atm.status == "built":
        found += [("Call", expiry, atm.strike), ("Put", expiry, atm.strike)]
    else:
        found += [(o, expiry, atm.strike) for o in ("Call", "Put")
                  if chain.cached(ticker, expiry, atm.strike, o)]
    if wc.status == "built":
        found.append(("Call", expiry, wc.strike))
    if wp.status == "built":
        found.append(("Put", expiry, wp.strike))
    tr.found = tuple(found)
    if tr.fetch:
        tr.status = "await"
        tr.reason = next(s.reason for s in sels if s.status == "await")
        return tr
    if not wp.strike < atm.strike < wc.strike:
        tr.reason = "wing_degenerate"
        return tr
    tr.status, tr.reason = "built", ""
    tr.atm, tr.wing_c, tr.wing_p = atm.strike, wc.strike, wp.strike
    return tr


# ════════════════════════════════════════════════════════════════════════════
# Pricing — one price per leg, fixed exit
# ════════════════════════════════════════════════════════════════════════════

def structure_legs(tr: Trade, structure: str) -> list[Leg]:
    """The series' legs: S long; RC and RP as the BACK ratio (-1 ATM, +2 wing)."""
    t, e = tr.ticker, tr.expiry
    if structure == "S":
        return [_leg(t, "Call", e, tr.atm, 1), _leg(t, "Put", e, tr.atm, 1)]
    if structure == "RC":
        return [_leg(t, "Call", e, tr.atm, -1), _leg(t, "Call", e, tr.wing_c, 2)]
    if structure == "RP":
        return [_leg(t, "Put", e, tr.atm, -1), _leg(t, "Put", e, tr.wing_p, 2)]
    raise ValueError(f"unknown structure {structure!r}")


def side_sign(side: str) -> int:
    return -1 if side == "front" else 1


def risk_points(structure: str, side: str, atm: float, wing: float | None,
                debit: float) -> float | None:
    """Max loss in option points, per one structure, at expiry. `debit` is the
    series' signed entry (back ratio or long straddle); a credit is negative.
    None where the risk is undefined: the front call ratio."""
    if structure == "S":
        return debit
    width = abs(wing - atm)
    if side == "back":
        return width + debit
    if structure == "RC":
        return None
    return 2 * wing - atm - debit


@dataclasses.dataclass
class Priced:
    tr: Trade
    structure: str
    entry: dict                        # strike and type -> mid at the fill
    exit: dict
    debit: float                       # series' signed entry, points; negative is a credit
    gross: float                       # series' gross P&L, points
    comm: float                        # round-trip commission, points
    touch: dict                        # side -> net P&L at the strict touch, points, or None
    front_aware: float | None          # front ratio, side-aware entry fill, net points
    tags: Counter

    @property
    def spot(self) -> float:
        return self.tr.spot

    @property
    def y(self) -> float:
        """The signed series, as a share of spot, before commission."""
        return self.gross / self.spot

    def net(self, side: str) -> float:
        return (side_sign(side) * self.gross - self.comm) / self.spot

    def touch_net(self, side: str) -> float | None:
        v = self.touch[side]
        return None if v is None else v / self.spot

    def r(self, side: str) -> float | None:
        """Net P&L over max loss, where the risk is defined and positive."""
        wing = {"RC": self.tr.wing_c, "RP": self.tr.wing_p}.get(self.structure)
        risk = risk_points(self.structure, side, self.tr.atm, wing, self.debit)
        if risk is None or risk <= 0:
            return None
        return (side_sign(side) * self.gross - self.comm) / risk


def strict_touch(row, sold: bool) -> float | None:
    """The side a leg trades on, with no fallback: a sale at the bid (0 with no
    bid), a purchase at the ask (None with no ask). A wide quote stays wide."""
    bid, ask = SIM._bid_ask(row)
    if sold:
        return bid if bid is not None and bid > 0 else 0.0
    return ask


def _entry_mids(chain, tr: Trade, legs: list[Leg]):
    """`(rows, prices, tags)` on one clock, or a drop reason. Every leg takes the
    bought-side call, so it has one price whichever side holds it."""
    rows, prices, tags = [], [], []
    for lg in legs:
        row = chain.history(lg)[1].get(tr.fill)
        fill = SIM.entry_day_fill(row, 1)
        if fill is None:
            return "no_entry_quote"
        if fill[0] is None:
            return SIM.JUNK_ENTRY_REFUSAL
        rows.append(row)
        prices.append(fill[0])
        tags.append(fill[1])
    if SIM._monotonicity_violation(legs, prices, tags):
        return SIM.NON_MONOTONIC_REFUSAL
    return rows, prices, tags


def _touch_pnl(legs, in_rows, out_rows, side: str, comm: float) -> float | None:
    s, pnl = side_sign(side), 0.0
    for lg, r_in, r_out in zip(legs, in_rows, out_rows):
        q = s * lg.qty
        px_in, px_out = strict_touch(r_in, sold=q < 0), strict_touch(r_out, sold=q > 0)
        if px_in is None or px_out is None:
            return None
        pnl += q * (px_out - px_in)
    return pnl - comm


def _front_aware(legs, in_rows, marks, comm: float) -> float | None:
    """The front ratio with `entry_day_fill(row, -1)` on each sold leg: the bid on
    a wide quote. `y` stays on the mirror; this is a print."""
    pnl = 0.0
    for lg, row, m in zip(legs, in_rows, marks):
        q = -lg.qty
        fill = SIM.entry_day_fill(row, 1 if q > 0 else -1)
        if fill is None or fill[0] is None:
            return None
        pnl += q * (m - fill[0])
    return pnl - comm


def run_trade(chain, tr: Trade, structure: str) -> Priced | str:
    """Price one built trade. `Priced`, or a printed drop reason.

    Entry: `_entry_mids`, on the fill day only. No leg moves to another day.
    Exit: `selloff_put_diagonal.leg_mark` on the exit session; a leg with no row
    that day, or only a carried mark, drops the row. Never the harness.
    """
    if tr.status != "built":
        raise ValueError(f"cannot price a {tr.status} trade")
    legs = structure_legs(tr, structure)
    entered = _entry_mids(chain, tr, legs)
    if isinstance(entered, str):
        return entered
    in_rows, prices, ftags = entered
    tags = Counter(ftags)
    out_rows, marks = [], []
    for lg in legs:
        row = chain.history(lg)[1].get(tr.exit)
        if row is None:
            return "no_exit_quote"
        m = SPD.leg_mark(chain, lg, tr.exit, None, None)
        if m is None:
            return "no_exit_quote"
        if m[1] == "barchart_stale":
            return "stale_exit_mark"
        out_rows.append(row)
        marks.append(m[0])
        tags[m[1]] += 1
    debit = sum(lg.qty * p for lg, p in zip(legs, prices))
    gross = sum(lg.qty * (m - p) for lg, m, p in zip(legs, marks, prices))
    comm = COMMISSION * 2 * CONTRACTS[structure] / 100.0
    touch = {side: _touch_pnl(legs, in_rows, out_rows, side, comm) for side in SIDES[structure]}
    aware = _front_aware(legs, in_rows, marks, comm) if structure != "S" else None
    return Priced(tr, structure,
                  {(lg.opt_type, lg.strike): p for lg, p in zip(legs, prices)},
                  {(lg.opt_type, lg.strike): m for lg, m in zip(legs, marks)},
                  debit, gross, comm, touch, aware, tags)


def adverse_bound(chain, tr: Trade, structure: str) -> dict[str, float | None]:
    """Each side's net share of spot on a row that dropped at the exit, closed at
    the adverse touch: a long leg at its bid or 0, a short leg at its ask. None
    where a short leg has no ask to bound it."""
    legs = structure_legs(tr, structure)
    entered = _entry_mids(chain, tr, legs)
    out: dict[str, float | None] = {side: None for side in SIDES[structure]}
    if isinstance(entered, str):
        return out
    _rows, prices, _tags = entered
    comm = COMMISSION * 2 * CONTRACTS[structure] / 100.0
    for side in SIDES[structure]:
        s, pnl = side_sign(side), 0.0
        for lg, p in zip(legs, prices):
            q = s * lg.qty
            px = strict_touch(chain.history(lg)[1].get(tr.exit), sold=q > 0)
            if px is None:
                pnl = None
                break
            pnl += q * (px - p)
        out[side] = None if pnl is None else (pnl - comm) / tr.spot
    return out


def adverse_y(chain, tr: Trade, structure: str) -> tuple[float | None, float | None]:
    """`(lowest, highest)` gross `y` of a row that dropped at the exit, from its exit
    touch. Lowest closes a long leg at its bid or 0, a short leg at its ask; highest is
    the reverse. None where the needed ask is missing."""
    legs = structure_legs(tr, structure)
    entered = _entry_mids(chain, tr, legs)
    if isinstance(entered, str):
        return None, None
    prices = entered[1]
    out = []
    for adverse_low in (True, False):
        pnl = 0.0
        for lg, p in zip(legs, prices):
            px = strict_touch(chain.history(lg)[1].get(tr.exit), sold=(lg.qty > 0) == adverse_low)
            if px is None:
                pnl = None
                break
            pnl += lg.qty * (px - p)
        out.append(None if pnl is None else pnl / tr.spot)
    return out[0], out[1]


# ════════════════════════════════════════════════════════════════════════════
# Features — every one reads D's close or earlier
# ════════════════════════════════════════════════════════════════════════════

def _to_float(v) -> float | None:
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def price_features(bars: list) -> dict[str, float | None]:
    """The features read off the underlying's bars. `bars` ends at D, so nothing
    after D is reachable from here."""
    out: dict[str, float | None] = {k: None for k in (
        "ret1", "ret5", "ret20", "dist50", "range_atr", "rv5_rv20", "und_vol", "rv20")}
    if not bars:
        return out
    c = [b.c for b in bars]
    for k, name in ((1, "ret1"), (5, "ret5"), (20, "ret20")):
        if len(c) > k:
            out[name] = c[-1] / c[-1 - k] - 1.0
    if len(c) >= 50:
        out["dist50"] = c[-1] / statistics.fmean(c[-50:]) - 1.0
    if len(bars) >= 21:
        trs = []
        for a, b in zip(bars[-21:], bars[-20:]):
            if b.h is None or b.l is None:
                break
            trs.append(max(b.h - b.l, abs(b.h - a.c), abs(b.l - a.c)))
        if len(trs) == 20 and sum(trs) > 0:
            out["range_atr"] = (bars[-1].h - bars[-1].l) / statistics.fmean(trs)
        rv20 = IV.realized_vol(c[-21:])
        rv5 = IV.realized_vol(c[-6:])
        out["rv20"] = rv20
        if rv20 and rv5 is not None:
            out["rv5_rv20"] = rv5 / rv20
        v = [b.v for b in bars[-21:]]
        if all(x is not None for x in v):
            prior = statistics.fmean(v[:-1])
            out["und_vol"] = v[-1] / prior if prior > 0 else None
    return out


def option_features(iv: dict[date, float], vol: dict[date, float], sessions: list[date],
                    i: int, rv20: float | None) -> dict[str, float | None]:
    """`iv_rv20`, `iv_chg5`, `opt_vol` at session `i`, from each session's own ATM
    pair read on that session's row. `sessions[i]` is D."""
    d = sessions[i]
    out: dict[str, float | None] = {"iv_rv20": None, "iv_chg5": None, "opt_vol": None}
    now = iv.get(d)
    if now is not None and rv20 is not None:
        out["iv_rv20"] = now - rv20
    if now is not None and i >= 5 and iv.get(sessions[i - 5]) is not None:
        out["iv_chg5"] = now - iv[sessions[i - 5]]
    if d in vol and i >= 20:
        prior = [vol[s] for s in sessions[i - 20:i] if s in vol]
        if len(prior) >= MEAN_MIN_PRIOR and statistics.fmean(prior) > 0:
            out["opt_vol"] = vol[d] / statistics.fmean(prior)
    return out


# ── the analysis page: deterministic parsing, no model call ─────────────────

_HP_FORMS = (
    re.compile(r"hedge[- ]pressure[^\n.]{0,40}?(\d{1,3})\s*/\s*100", re.I),
    re.compile(r"hedge[- ]pressure(?:\s+score)?\s+(\d{1,3})\b", re.I),
    re.compile(r"(\d{1,3})\s*/\s*100[^\n.]{0,20}?hedge[- ]pressure", re.I),
)
DIR_CODE = {"BULL": 1, "RANGE": 0, "BEAR": -1}
VOL_CODE = {"C-VOL": 0, "L-VOL": 1, "H-VOL": 2, "E-VOL": 3}
RISK_CODE = {"RISK-ON": 1, "RISK-OFF": 0}
FLOW_TAG = "[FLOW]"


def hp_score(signal) -> int | None:
    """The hedge-pressure score in a MARKET signal: the first of three frozen
    forms, in order, in 0 to 100. Anything else is missing."""
    s = signal if isinstance(signal, str) else ""
    for rx in _HP_FORMS:
        m = rx.search(s)
        if m:
            v = int(m.group(1))
            return v if 0 <= v <= 100 else None
    return None


def flow_count(signal) -> int | None:
    s = signal if isinstance(signal, str) else ""
    if not s.strip() or s.strip().lower() == "nan":
        return None
    return s.count(FLOW_TAG)


def parse_tokens(raw) -> dict[str, int | None]:
    """`market_read.parse_label` mapped to codes. A field with no token is
    None, which means missing: an unparsed row is never imputed."""
    lb = MR.parse_label(raw)
    return {"dir": DIR_CODE.get(lb.dir), "vol": VOL_CODE.get(lb.vol),
            "risk": RISK_CODE.get(lb.risk), "hp": (1 if lb.hp else 0) if lb.head else None}


lag_bin = MR.lag_bin


def load_analysis(path: Path | None = None) -> tuple[dict, dict]:
    """`(index, census)`, through `lib/era.py` as era v4, with the seal respected.

    `index[(ticker, D)]` holds the coded fields and the row's lag bin, for
    MARKET and for each study ticker. Refuses (exit 3) anything but v4."""
    era = era_mod.requested_era()
    paths = era_mod.resolve_paths(era)
    actual = era_mod.enforce(era, paths)
    if actual != ANALYSIS_ERA:
        era_mod._refuse(era_mod.EXIT_ERA_MISMATCH,
                        f"daily_vol_structure reads analysis rows as era {ANALYSIS_ERA}; "
                        f"the exports are {actual!r}.")
    csv.field_size_limit(10 ** 8)
    with open(path or paths["analysis"], newline="") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r.get("ticker") in ("MARKET",) + TICKERS]
    kept, info = era_mod.drop_sealed(rows, date_key="date")
    index: dict = {}
    seen: Counter = Counter()
    for r in kept:
        seen[(r["ticker"], str(r["date"])[:10])] += 1
    for r in kept:
        d = str(r["date"])[:10]
        if seen[(r["ticker"], d)] > 1:
            continue
        f = parse_tokens(r.get("regime"))
        f["flow"] = flow_count(r.get("signal"))
        f["hp_score"] = hp_score(r.get("signal")) if r["ticker"] == "MARKET" else None
        f["lag"] = lag_bin(r.get("created_datetime"), d)
        index[(r["ticker"], d)] = f
    return index, dict(era=actual, seal=era_mod.seal_line(info),
                       dup=sum(1 for n in seen.values() if n > 1))


def load_baseline(path: Path = BASELINE_CSV) -> dict[str, dict[str, float | None]]:
    """`{D: {qqq_total, qqq_cp}}` from the daily flow totals tab. A blank or a zero put
    is missing."""
    out: dict[str, dict[str, float | None]] = {}
    if not path.exists():
        return out
    with open(path, newline="") as fh:
        rows, _ = era_mod.drop_sealed(list(csv.DictReader(fh)), date_key="date")
    for r in rows:
        c, p = _to_float(r.get("qqq_call_prem")), _to_float(r.get("qqq_put_prem"))
        out[str(r["date"])[:10]] = {
            "qqq_total": c + p if c is not None and p is not None else None,
            "qqq_cp": c / p if c is not None and p else None}
    return out


def baseline_features(baseline: dict, sessions: list[date], i: int) -> dict[str, float | None]:
    """`qqq_prem` is D's total over the mean of the prior 20 sessions, as `und_vol` is:
    the raw total doubled across the window. `qqq_cp` is D's call/put ratio."""
    today = baseline.get(sessions[i].isoformat()) or {}
    total = today.get("qqq_total")
    out = {"qqq_prem": None, "qqq_cp": today.get("qqq_cp")}
    if total is None or i < 20:
        return out
    prior = [(baseline.get(s.isoformat()) or {}).get("qqq_total") for s in sessions[i - 20:i]]
    prior = [v for v in prior if v is not None]
    if len(prior) >= MEAN_MIN_PRIOR and statistics.fmean(prior) > 0:
        out["qqq_prem"] = total / statistics.fmean(prior)
    return out


def analysis_features(index: dict, ticker: str, d: str) -> dict[str, float | None]:
    m = index.get(("MARKET", d)) or {}
    t = index.get((ticker, d)) or {}
    return {"mkt_dir": m.get("dir"), "mkt_vol": m.get("vol"), "mkt_risk": m.get("risk"),
            "mkt_hp": m.get("hp"), "mkt_hp_score": m.get("hp_score"), "mkt_flow": m.get("flow"),
            "tk_dir": t.get("dir"), "tk_vol": t.get("vol"), "tk_flow": t.get("flow")}


def feature_lag(index: dict, feature: Feature, ticker: str, d: str) -> str | None:
    key = ("MARKET", d) if feature.source == "analysis_market" else (ticker, d)
    row = index.get(key)
    return row["lag"] if row else None


# ════════════════════════════════════════════════════════════════════════════
# The book — selection memoised; pricing gated
# ════════════════════════════════════════════════════════════════════════════

def off_runs(ratios: list[tuple[date, float]], tol: float = SPLIT_TOL,
             min_run: int = SPLIT_RUN) -> tuple[int, list[tuple[date, date, float]]]:
    """`(glitch days, runs)` of `Price~` / close off 1 by more than `tol`. A run
    of `min_run` or more consecutive observations is a split-basis problem; a
    shorter one is a bad print, counted and otherwise ignored."""
    runs, cur, glitches = [], [], 0
    for d, r in sorted(ratios) + [(date.max, 1.0)]:
        if abs(r - 1.0) > tol:
            cur.append((d, r))
            continue
        if len(cur) >= min_run:
            runs.append((cur[0][0], cur[-1][0], statistics.median(x[1] for x in cur)))
        else:
            glitches += len(cur)
        cur = []
    return glitches, runs


class Book:
    """Every trade, memoised. `price` and `option_row` raise until `open_outcomes`
    has found no problem: that is the gate, by construction."""

    def __init__(self, chain, evidence: set[str], closes: dict[date, float], bars: dict):
        self.chain, self.evidence = chain, evidence
        self.bars = bars
        self.sessions = sorted(closes)
        self.index = {d: i for i, d in enumerate(self.sessions)}
        self.listing = Listing(chain, evidence)
        self._tr: dict = {}
        self._px: dict = {}
        self._open = False

    def signals(self, lo: date = WINDOW[0], hi: date | None = WINDOW[1]) -> list[date]:
        return [d for d in self.sessions if lo <= d and (hi is None or d <= hi)]

    def trades(self, ticker: str, tenor: Tenor, lo: date = WINDOW[0],
               hi: date | None = WINDOW[1]) -> list[Trade]:
        out = []
        for d in self.signals(lo, hi):
            key = (ticker, tenor.name, d)
            if key not in self._tr:
                self._tr[key] = select_trade(self.chain, self.evidence, self.listing, ticker,
                                             tenor, d, self.sessions, self.index,
                                             self.bars.get(ticker, {}))
            out.append(self._tr[key])
        return out

    def coverage(self) -> dict:
        """Counts per ticker and tenor. No quote value is read."""
        out = {}
        for tk in TICKERS:
            for t in TENORS:
                c = Counter()
                found, awaited, refetch = set(), set(), set()
                for tr in self.trades(tk, t):
                    c[tr.status] += 1
                    c[f"why:{tr.reason}"] += bool(tr.reason)
                    found |= set(tr.found)
                    awaited |= set(tr.fetch)
                    refetch |= set(tr.refetch)
                out[(tk, t.name)] = dict(c=c, found=len(found), awaited=len(awaited),
                                         refetch=len(refetch))
        return out

    def split_census(self) -> dict[str, tuple[int, list]]:
        """`Price~` on D's row of each built trade's ATM call, against D's close.
        Reads that one column and no option price."""
        out = {}
        for tk in TICKERS:
            ratios = []
            for t in TENORS:
                for tr in self.trades(tk, t):
                    if tr.status != "built":
                        continue
                    row = self.chain.history(
                        _leg(tk, "Call", tr.expiry, tr.atm))[1].get(tr.signal)
                    px = _to_float(row.get("Price~")) if row else None
                    if px and tr.spot:
                        ratios.append((tr.signal, px / tr.spot))
            out[tk] = off_runs(sorted(set(ratios)))
        return out

    def gate_problems(self) -> list[str]:
        problems = []
        for (tk, tn), k in self.coverage().items():
            n = k["c"]["await"]
            if n:
                problems.append(f"{tk} {tn}: {n} trades await a contract or an OHLC bar")
        for tk in TICKERS:
            bars = self.bars.get(tk, {})
            if not bars or max(bars) < WINDOW[1]:
                last = max(bars) if bars else "no file"
                problems.append(f"{tk}: OHLC ends {last}, before the window's end {WINDOW[1]}")
        for tk, (_g, runs) in self.split_census().items():
            for a, b, r in runs:
                problems.append(f"{tk}: Price~ is {r:.2f}x the close from {a} to {b}")
        return problems

    def open_outcomes(self) -> None:
        problems = self.gate_problems()
        if problems:
            raise AwaitingScrape("; ".join(problems))
        self._open = True

    def _require_open(self) -> None:
        if not self._open:
            raise AwaitingScrape("outcomes are closed until the coverage gate passes")

    def price(self, tr: Trade, structure: str) -> Priced | str:
        """`Priced` or a drop reason. Raises while the gate is shut."""
        self._require_open()
        key = (tr.ticker, tr.tenor.name, tr.signal, structure)
        if key not in self._px:
            self._px[key] = run_trade(self.chain, tr, structure)
        return self._px[key]

    def option_row(self, tr: Trade, opt: str) -> dict | None:
        """D's row of the trade's ATM leg. Raises while the gate is shut."""
        self._require_open()
        return self.chain.history(_leg(tr.ticker, opt, tr.expiry, tr.atm))[1].get(tr.signal)


def fetch_targets(book: Book, scope: str = "window") -> list[dict]:
    """Unique contracts the awaiting trades name. A contract two trades name is listed
    once. The collector imports this; a re-run re-targets. A shallow cached file carries
    `needed`, the date that makes `fetch_option_histories` re-fetch it.
    `scope`: `window` (the graded dates) or `forward` (from 2026-09-23)."""
    lo, hi = (WINDOW[0], WINDOW[1]) if scope == "window" else (FORWARD_START, None)
    seen: dict = {}
    needed: dict = {}
    for tk in TICKERS:
        for t in TENORS:
            for tr in book.trades(tk, t, lo, hi):
                if tr.status != "await":
                    continue
                for o, e, k in tr.fetch:
                    key = (tk, o, e, round(float(k), 4))
                    seen.setdefault(key, f"{tk}:{t.name}")
                    if (o, e, k) in tr.refetch:
                        d = tr.signal - timedelta(days=REFETCH_MARGIN)
                        needed[key] = min(needed.get(key, d), d)
    return [dict(ticker=tk, expiration=e, strike=k, opt_type=o, category=cat,
                 needed=needed.get((tk, o, e, k)))
            for (tk, o, e, k), cat in sorted(seen.items(), key=lambda kv: (
                kv[0][0], kv[0][2], kv[0][1], kv[0][3]))]


def build_book() -> Book:
    return Book(NTF.Chain(), NTF.unlisted_evidence(), MBL.load_closes(),
                {tk: UND.load_bars(tk) for tk in TICKERS})


def plan(scope: str = "window") -> list[dict]:
    """The collector's entry point: the fetch plan on the cache as it stands.
    Selection only; nothing is priced and no network is touched."""
    return fetch_targets(build_book(), scope)


# ════════════════════════════════════════════════════════════════════════════
# The dataset
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass
class Dataset:
    """Rows per series, and feature values per `(ticker, tenor, D)`."""
    rows: dict                         # (ticker, tenor, structure) -> list[row]
    features: dict                     # (ticker, tenor) -> {D iso: {name: value}}
    index: dict                        # the analysis index
    drops: dict                        # (ticker, tenor, structure) -> Counter
    exit_drops: dict = dataclasses.field(default_factory=dict)  # same key -> list[row]


def build_dataset(book: Book, index: dict, baseline: dict, labeler: MechLabeler,
                  lo: date = WINDOW[0], hi: date | None = WINDOW[1]) -> Dataset:
    """Past the gate only: `Book.price` and `Book.option_row` raise otherwise."""
    book._require_open()
    rows, feats, drops, exits = {}, {}, {}, {}
    for tk in TICKERS:
        bars = book.bars[tk]
        days = sorted(bars)
        pos = {d: i for i, d in enumerate(days)}
        for t in TENORS:
            iv, vol = {}, {}
            trades = book.trades(tk, t, lo, hi)
            for tr in trades:
                if tr.status != "built":
                    continue
                rc, rp = book.option_row(tr, "Call"), book.option_row(tr, "Put")
                if rc is None or rp is None:
                    continue
                ivc, ivp = _to_float(rc.get("IV")), _to_float(rp.get("IV"))
                if ivc and ivp and ivc > 0 and ivp > 0:
                    iv[tr.signal] = (ivc + ivp) / 2
                vc, vp = _to_float(rc.get("Volume")), _to_float(rp.get("Volume"))
                if vc is not None and vp is not None:
                    vol[tr.signal] = vc + vp
            fmap = {}
            for tr in trades:
                d = tr.signal
                iso = d.isoformat()
                pf = (price_features([bars[x] for x in days[max(0, pos[d] - 60):pos[d] + 1]])
                      if d in pos else {})
                fv = {k: v for k, v in pf.items() if k != "rv20"}
                fv.update(option_features(iv, vol, book.sessions, book.index[d], pf.get("rv20")))
                _dir, mvol, ok, mapped = labeler.label(iso)
                fv["evol"] = (1 if mvol == "E-VOL" else 0) if ok and mapped == iso and mvol else None
                fv.update(baseline_features(baseline, book.sessions, book.index[d]))
                fv.update(analysis_features(index, tk, iso))
                fmap[iso] = fv
            feats[(tk, t.name)] = fmap
            for s in STRUCTURES:
                out, drop, ex = [], Counter(), []
                for tr in trades:
                    if tr.status != "built":
                        drop[tr.reason or tr.status] += 1
                        continue
                    p = book.price(tr, s)
                    a, b = bars.get(tr.fill), bars.get(tr.exit)
                    if isinstance(p, str):
                        drop[p] += 1
                        if p in EXIT_DROPS:
                            lo_y, hi_y = adverse_y(book.chain, tr, s)
                            ex.append(dict(d=tr.signal, date=tr.signal.isoformat(), reason=p,
                                           exit=tr.exit, si=book.index[tr.signal],
                                           dte=(tr.expiry - tr.fill).days, wd=tr.fill.weekday(),
                                           up=(b.c > a.c) if a and b else None,
                                           y_low=lo_y, y_high=hi_y,
                                           bound=adverse_bound(book.chain, tr, s)))
                        continue
                    out.append(dict(
                        d=tr.signal, date=tr.signal.isoformat(), exit=tr.exit,
                        si=book.index[tr.signal], y=p.y,
                        net={sd: p.net(sd) for sd in SIDES[s]},
                        touch={sd: p.touch_net(sd) for sd in SIDES[s]},
                        r={sd: p.r(sd) for sd in SIDES[s]}, debit=p.debit,
                        front_aware=None if p.front_aware is None else p.front_aware / p.spot,
                        wide=p.tags[SIM.CLOSE_MID_WIDE_TAG] > 0,
                        dte=(tr.expiry - tr.fill).days, wd=tr.fill.weekday(),
                        held=(tr.exit - tr.fill).days,
                        atm_d=abs(tr.atm / tr.spot - 1.0),
                        atm_fill=abs(tr.atm / a.c - 1.0) if a else None,
                        expiry=tr.expiry, atm=tr.atm, wing=(tr.wing_c if s == "RC" else
                                                            tr.wing_p if s == "RP" else None)))
                rows[(tk, t.name, s)] = out
                drops[(tk, t.name, s)] = drop
                exits[(tk, t.name, s)] = ex
    return Dataset(rows, feats, index, drops, exits)


# ════════════════════════════════════════════════════════════════════════════
# Statistics — pure functions on synthetic-testable rows
# ════════════════════════════════════════════════════════════════════════════

def mean_stat(_x, y) -> float:
    """The mean of the usable y, in `block_bootstrap`'s `(x, y)` form."""
    v = [float(b) for b in y if b is not None]
    return statistics.fmean(v) if v else float("nan")


def cut_stat(lo: float, hi: float) -> Callable:
    """mean(y | x >= hi) - mean(y | x <= lo). The cuts are frozen on discovery rows,
    so later rows and every rotation read the same rule."""
    def stat(x, y) -> float:
        top = [float(b) for a, b in zip(x, y) if b is not None and a >= hi]
        bot = [float(b) for a, b in zip(x, y) if b is not None and a <= lo]
        if not top or not bot:
            return float("nan")
        return statistics.fmean(top) - statistics.fmean(bot)
    return stat


def tercile_cuts(x: list[float]) -> tuple[float, float]:
    """The values bounding the bottom and top rank tercile of `x`."""
    lab = FD.rank_groups(x)
    return (max(a for a, g in zip(x, lab) if g == 0), min(a for a, g in zip(x, lab) if g == 2))


def frozen_cuts(f: Feature, discovery_x: list[float]) -> tuple[float, float] | None:
    """A rank feature's cuts, from its discovery rows; a discrete feature's fixed
    ones. None when the discovery rows cannot separate two arms."""
    if f.kind == "cut":
        return f.lo, f.hi
    if len(discovery_x) < 3:
        return None
    lo, hi = tercile_cuts(discovery_x)
    return (lo, hi) if lo < hi else None


def shift_p(x, y, stat: Callable, draws: int = SHIFT_N, seed: int = SEED) -> tuple[float, float]:
    """`(point, two-sided p)` against `FD.circular_shift_null`, minimum shift 21. The
    z is the point over the rotated statistics' SD. It is not centred: the rotations
    leave out the lags nearest zero, so their mean leans against the point, and
    centring would inflate z. A rotation keeps both series' own autocorrelation,
    which a block resample of this length does not hold. NaN when the null is
    degenerate."""
    if len(x) < 2 * MIN_SHIFT + 1:
        return stat(x, y) if x else float("nan"), float("nan")
    null = FD.circular_shift_null(x, y, stat, MIN_SHIFT, draws, seed)
    v = [a for a in null.values if a == a]
    if null.point != null.point or len(v) < 2:
        return null.point, float("nan")
    sd = statistics.stdev(v)
    if sd <= 0:
        return null.point, float("nan")
    return null.point, math.erfc(abs(null.point) / sd / math.sqrt(2))


def n_blocks(si: list[int]) -> int:
    return len({i // BLOCK for i in si})


def arm_blocks(x: list[float], si: list[int], cuts: tuple[float, float]) -> list[list[int]]:
    """The session indices of the bottom and the top arm."""
    lo, hi = cuts
    return [[i for i, a in zip(si, x) if a <= lo], [i for i, a in zip(si, x) if a >= hi]]


def floors_met(x: list[float], si: list[int], cuts: tuple[float, float] | None) -> bool:
    """The power floor every cell must meet on the dates it is read on."""
    if cuts is None or len(x) < MIN_DATES or n_blocks(si) < MIN_BLOCKS:
        return False
    return all(len(a) >= MIN_ARM_DATES and n_blocks(a) >= MIN_ARM_BLOCKS
               for a in arm_blocks(x, si, cuts))


def cell_pairs(ds: Dataset, cell: tuple, keep: Callable[[dict], bool] | None = None,
               lag: str | None = None, feature_ticker: str | None = None) -> list[tuple]:
    """`[(x, row)]` in date order, on rows whose feature is present. `lag` keeps one
    lag bin of an analysis feature."""
    tk, tn, s, name = cell
    f = FEATURE_BY_NAME[name]
    ftk = feature_ticker or tk
    fmap = ds.features[(ftk, tn)]
    out = []
    for r in ds.rows[(tk, tn, s)]:
        if keep is not None and not keep(r):
            continue
        v = (fmap.get(r["date"]) or {}).get(name)
        if v is None:
            continue
        if lag is not None and feature_lag(ds.index, f, ftk, r["date"]) != lag:
            continue
        out.append((float(v), r))
    return out


def cell_xy(ds: Dataset, cell: tuple, keep=None, lag=None, feature_ticker=None,
            value: Callable[[dict], float] | None = None) -> tuple[list, list, list]:
    """`(x, y, si)`: `cell_pairs` as three lists."""
    pairs = cell_pairs(ds, cell, keep, lag, feature_ticker)
    return ([x for x, _ in pairs], [value(r) if value else r["y"] for _, r in pairs],
            [r["si"] for _, r in pairs])


def in_discovery(r: dict) -> bool:
    """A discovery row is signalled, and closed, before the first confirmation
    date. A trade that closes on or after it would read a confirmation quote."""
    return r["d"] < FIRST_CONFIRM and r["exit"] < FIRST_CONFIRM


def in_confirmation(r: dict) -> bool:
    return r["d"] >= FIRST_CONFIRM


def cell_cuts(ds: Dataset, cell: tuple, feature_ticker: str | None = None):
    """The cell's frozen cuts: discovery rows only."""
    f = FEATURE_BY_NAME[cell[3]]
    return frozen_cuts(f, cell_xy(ds, cell, keep=in_discovery, feature_ticker=feature_ticker)[0])


@dataclasses.dataclass
class DiscCell:
    cell: tuple
    n: int
    gradable: bool
    rho: float
    contrast: float
    p: float
    q: float = float("nan")

    @property
    def sign(self) -> int:
        return _sign(self.rho)


def discover(ds: Dataset, draws: int = SHIFT_N, seed: int = SEED) -> list[DiscCell]:
    """Spearman and top minus bottom on the discovery rows only, for the 144 graded
    cells. The circular-shift null gives each p; BH runs across the gradable cells.
    Sorted by q, then p. Reads no confirmation date."""
    out = []
    for cell in graded_cells():
        x, y, si = cell_xy(ds, cell, keep=in_discovery)
        cuts = frozen_cuts(FEATURE_BY_NAME[cell[3]], x)
        if not floors_met(x, si, cuts):
            out.append(DiscCell(cell, len(x), False, float("nan"), float("nan"), float("nan")))
            continue
        rho, p = shift_p(x, y, FD.spearman, draws, seed)
        out.append(DiscCell(cell, len(x), True, rho, cut_stat(*cuts)(x, y), p))
    for c, q in zip(out, RM.bh_q([c.p for c in out])):
        c.q = q
    return sorted(out, key=lambda c: (not c.gradable, c.q if c.q == c.q else 2.0,
                                      c.p if c.p == c.p else 2.0, c.cell))


def ranked(cells: list[DiscCell]) -> list[DiscCell]:
    """The ranked list: gradable cells at BH q <= 0.10. Only these move on."""
    return [c for c in cells if c.gradable and c.q == c.q and c.q <= BH_Q]


def other_ticker(tk: str) -> str:
    return "SMH" if tk == "QQQ" else "QQQ"


def _sign(v: float) -> int:
    return (v > 0) - (v < 0) if v == v else 0


def _mean_or_nan(vals: list) -> float:
    v = [a for a in vals if a is not None]
    return statistics.fmean(v) if v else float("nan")


def arm_table(pairs: list[tuple], cuts: tuple[float, float], side: str) -> dict:
    """Top arm, bottom arm and all rows: `(n, net mean at mid, at the strict touch)`."""
    lo, hi = cuts
    arms = {"top": [r for x, r in pairs if x >= hi], "bottom": [r for x, r in pairs if x <= lo],
            "all": [r for _, r in pairs]}
    return {k: (len(v), _mean_or_nan([r["net"][side] for r in v]),
                _mean_or_nan([r["touch"][side] for r in v])) for k, v in arms.items()}


def best_position(pairs: list[tuple], cuts: tuple[float, float], structure: str, sign: int,
                  n_boot: int = BOOT_N, seed: int = SEED) -> dict | None:
    """The tradable position with the larger net mean in its arm, and whether that mean
    clears zero at p < .05. S is long in the higher arm. A ratio is the back ratio in the
    higher arm or the front ratio in the lower arm. At mid one of those two is positive
    whenever the arms differ, so a positive mean alone would prove nothing."""
    if sign == 0:
        return None
    lo, hi = cuts
    top = [r for x, r in pairs if x >= hi]
    bottom = [r for x, r in pairs if x <= lo]
    high, low = (("top", top), ("bottom", bottom)) if sign > 0 else (("bottom", bottom), ("top", top))
    opts = [(high, "long")] if structure == "S" else [(high, "back"), (low, "front")]
    opts = [o for o in opts if o[0][1]]
    if not opts:
        return None
    (arm, rows), side = max(opts, key=lambda o: statistics.fmean(r["net"][o[1]] for r in o[0][1]))
    v = [r["net"][side] for r in rows]
    mean, p = mean_boot(v, n_boot, seed)
    return dict(arm=arm, side=side, n=len(v), mean=mean, p=p, ok=mean > 0 and p < ALPHA,
                touch=_mean_or_nan([r["touch"][side] for r in rows]))


def position_clears(pos: dict | None) -> bool | None:
    """True or False, or None when the chosen arm is under three full blocks and the
    test cannot be read: on 21 rows or fewer its block bootstrap has one block."""
    if pos is None:
        return False
    if pos["n"] < MIN_POSITION_ROWS:
        return None
    return bool(pos["ok"])


def bucket_contrasts(pairs: list[tuple], cuts: tuple[float, float], tenor_name: str) -> dict:
    """`{bucket: (top minus bottom, rows in the two arms)}`, for each DTE bucket or
    weekday with enough rows per arm."""
    groups: dict = {}
    for x, r in pairs:
        groups.setdefault(cycle_bucket(tenor_name, r), []).append((x, r))
    out = {}
    lo, hi = cuts
    for b, ps in sorted(groups.items(), key=lambda kv: str(kv[0])):
        top = [r["y"] for x, r in ps if x >= hi]
        bot = [r["y"] for x, r in ps if x <= lo]
        if b is not None and len(top) >= BUCKET_MIN_ARM and len(bot) >= BUCKET_MIN_ARM:
            out[b] = (statistics.fmean(top) - statistics.fmean(bot), len(top) + len(bot))
    return out


def cycle_clause(contrasts: dict, sign: int, overall: float) -> bool | None:
    """The row-weighted average of the bucket contrasts has discovery's sign and is at
    least half the overall contrast, so the expiry cycle is not what makes it. None
    under two readable buckets."""
    if len(contrasts) < BUCKET_MIN_N:
        return None
    avg = sum(v * n for v, n in contrasts.values()) / sum(n for _v, n in contrasts.values())
    return _sign(avg) == sign and abs(avg) >= CYCLE_MIN_SHARE * abs(overall)


def exit_share(ds: Dataset, key: tuple) -> float:
    e, n = len(ds.exit_drops.get(key, ())), len(ds.rows[key])
    return e / (n + e) if n + e else 0.0


def arm_exit_shares(ds: Dataset, cell: tuple, cuts, keep, lag=None, feature_ticker=None) -> dict:
    """Exit drops as a share of each arm, on the dates and lag bin read."""
    tk, tn, s, name = cell
    f = FEATURE_BY_NAME[name]
    ftk = feature_ticker or tk
    fmap = ds.features[(ftk, tn)]
    pairs = cell_pairs(ds, cell, keep, lag, feature_ticker)
    lo, hi = cuts
    kept = {"top": sum(x >= hi for x, _ in pairs), "bottom": sum(x <= lo for x, _ in pairs)}
    gone = {"top": 0, "bottom": 0}
    for e in ds.exit_drops.get(cell[:3], ()):
        if keep is not None and not keep(e):
            continue
        v = (fmap.get(e["date"]) or {}).get(name)
        if v is None or (lag is not None and feature_lag(ds.index, f, ftk, e["date"]) != lag):
            continue
        gone["top"] += v >= hi
        gone["bottom"] += v <= lo
    return {k: gone[k] / (kept[k] + gone[k]) if kept[k] + gone[k] else 0.0 for k in kept}


def exit_limit_ok(series_share: float, arm_shares: dict) -> bool:
    return series_share <= EXIT_DROP_MAX and all(v <= EXIT_DROP_MAX for v in arm_shares.values())


def can_stand_over_limit(token: str) -> bool:
    """Over the exit limit only these words can stand. Closing dropped rows against the
    cell's sign can only weaken a result, so a `NULL` would nearly always hold."""
    return token in (CANDIDATE, CONTRARY)


def _synth_row(e: dict, y: float | None) -> dict:
    """A dropped row closed at the adverse touch, in a kept row's shape."""
    return dict(d=e["d"], date=e["date"], exit=e["exit"], si=e["si"], dte=e["dte"], wd=e["wd"],
                y=y, net=e["bound"], touch=e["bound"], r={}, synth=True)


def bounded_pairs(ds: Dataset, cell: tuple, cuts, sign: int, keep=None, lag=None,
                  feature_ticker=None) -> tuple[list[tuple], bool]:
    """`(pairs with dropped rows added, unbounded)`. Each dropped row closes at the touch
    against the cell's sign: low `y` in the arm the sign favours, high `y` in the other.
    `unbounded` is True when a dropped row in an arm has a short leg with no ask."""
    tk, tn, s, name = cell
    f = FEATURE_BY_NAME[name]
    ftk = feature_ticker or tk
    fmap = ds.features[(ftk, tn)]
    lo, hi = cuts
    pairs = list(cell_pairs(ds, cell, keep, lag, feature_ticker))
    unbounded = False
    for e in ds.exit_drops.get(cell[:3], ()):
        if keep is not None and not keep(e):
            continue
        v = (fmap.get(e["date"]) or {}).get(name)
        if v is None or (lag is not None and feature_lag(ds.index, f, ftk, e["date"]) != lag):
            continue
        favoured = (v >= hi) if sign >= 0 else (v <= lo)
        y = e["y_low"] if favoured else e["y_high"]
        if y is None or any(b is None for b in e["bound"].values()):
            unbounded = unbounded or v >= hi or v <= lo
            continue
        pairs.append((float(v), _synth_row(e, y)))
    return sorted(pairs, key=lambda p: p[1]["si"]), unbounded


def _with_replaced(ps: list[float], i: int, p: float) -> list[float]:
    return ps[:i] + [p] + ps[i + 1:]


def confirm_token(disc_sign: int, point: float, q: float, floors: bool, exit_ok: bool,
                  tradable: bool | None, cycle: bool | None) -> str:
    """The cell's verdict. The first matching row wins (registration, Verdicts)."""
    if not floors or point != point or not exit_ok:
        return UNDERPOWERED
    if q != q or q > CONFIRM_Q:
        return NULL
    if _sign(point) == -disc_sign:
        return CONTRARY
    if tradable is None:
        return UNDERPOWERED
    if not tradable:
        return NULL
    if cycle is None:
        return UNDERPOWERED
    return CANDIDATE if cycle else NULL


def _pairs_token(pairs: list[tuple], cuts, disc: "DiscCell", point: float, q: float,
                 floors: bool, n_boot: int, seed: int) -> str:
    """The verdict of one set of rows, with the exit-drop limit aside."""
    _tk, tn, s, _name = disc.cell
    pos = best_position(pairs, cuts, s, disc.sign, n_boot, seed)
    cycle = cycle_clause(bucket_contrasts(pairs, cuts, tn), disc.sign, point)
    return confirm_token(disc.sign, point, q, floors, True, position_clears(pos), cycle)


@dataclasses.dataclass
class Confirmed:
    cell: tuple
    disc: DiscCell
    n: int
    point: float
    p: float
    ci: tuple
    q: float
    other_n: int
    other_point: float
    window_point: float
    token: str
    position: dict | None
    arms: dict
    buckets: dict
    cycle: bool | None
    dte_corr: float
    series_exit: float
    arm_exit: dict
    exit_note: str

    @property
    def tradable(self) -> bool:
        return position_clears(self.position) is True


def confirm(ds: Dataset, cells: list[DiscCell], draws: int = SHIFT_N, n_boot: int = BOOT_N,
            seed: int = SEED) -> list[Confirmed]:
    """Every clause of the bar, on confirmation rows, with cuts frozen on discovery
    rows. BH runs across the ranked list. The other-ticker and sell-off-window signs
    print as robustness lines; neither is in the bar."""
    first = []
    for d in cells:
        cuts = cell_cuts(ds, d.cell)
        x, y, si = cell_xy(ds, d.cell, keep=in_confirmation)
        floors = floors_met(x, si, cuts)
        point, p = shift_p(x, y, cut_stat(*cuts), draws, seed) if cuts and x else (float("nan"),) * 2
        first.append((d, cuts, x, y, si, floors, point, p))
    raw = [f[7] if f[5] else float("nan") for f in first]
    qs = RM.bh_q(raw)
    out = []
    for i, ((d, cuts, x, y, si, floors, point, p), q) in enumerate(zip(first, qs)):
        tk, tn, s, name = d.cell
        f = FEATURE_BY_NAME[name]
        pairs = cell_pairs(ds, d.cell, keep=in_confirmation)
        ci = (float("nan"),) * 2
        arms, buckets, pos, cycle = {}, {}, None, None
        arm_ex = {"top": 0.0, "bottom": 0.0}
        if cuts and x:
            b = FD.block_bootstrap(x, y, cut_stat(*cuts), BLOCK, n_boot, seed)
            ci = (b.lo, b.hi)
            arms = {side: arm_table(pairs, cuts, side) for side in SIDES[s]}
            pos = best_position(pairs, cuts, s, d.sign, n_boot, seed)
            buckets = bucket_contrasts(pairs, cuts, tn)
            cycle = cycle_clause(buckets, d.sign, point)
            arm_ex = arm_exit_shares(ds, d.cell, cuts, in_confirmation)
        ser_ex = exit_share(ds, d.cell[:3])
        exit_ok, note = True, "within the limit"
        if cuts and x and not exit_limit_ok(ser_ex, arm_ex):
            pb, unbounded = bounded_pairs(ds, d.cell, cuts, d.sign, keep=in_confirmation)
            if unbounded:
                exit_ok, note = False, "over the limit, and a short leg has no ask"
            else:
                t0 = _pairs_token(pairs, cuts, d, point, q, floors, n_boot, seed)
                if not can_stand_over_limit(t0):
                    exit_ok, note = False, f"over the limit, and {t0} cannot stand"
                else:
                    bx, by = [a for a, _ in pb], [r["y"] for _, r in pb]
                    pt_b, p_b = shift_p(bx, by, cut_stat(*cuts), draws, seed)
                    q_b = RM.bh_q(_with_replaced(raw, i, p_b if floors else float("nan")))[i]
                    exit_ok = _pairs_token(pb, cuts, d, pt_b, q_b, floors, n_boot, seed) == t0
                    note = ("over the limit; the verdict holds at the adverse touch" if exit_ok
                            else "over the limit; the verdict changes at the adverse touch")
        o = other_ticker(tk)
        ftk = tk if f.qqq_only else None
        ox, oy, _ = cell_xy(ds, (o, tn, s, name), keep=in_confirmation, feature_ticker=ftk)
        ocuts = cell_cuts(ds, (o, tn, s, name), feature_ticker=ftk)
        other_point = cut_stat(*ocuts)(ox, oy) if ocuts and ox else float("nan")
        wx, wy, _ = cell_xy(ds, d.cell, keep=lambda r: in_confirmation(r)
                            and not in_selloff_window(r["d"]))
        window_point = cut_stat(*cuts)(wx, wy) if cuts and wx else float("nan")
        token = confirm_token(d.sign, point, q, floors, exit_ok, position_clears(pos), cycle)
        dte_corr = FD.spearman(x, [r["dte"] for _, r in pairs]) if x else float("nan")
        out.append(Confirmed(d.cell, d, len(x), point, p, ci, q, len(ox), other_point,
                             window_point, token, pos, arms, buckets, cycle, dte_corr,
                             ser_ex, arm_ex, note))
    return out


def unranked_token(ds: Dataset, disc: list[DiscCell], i: int) -> str:
    """The tally word of a cell that did not reach confirmation: `NULL`, or
    `UNDERPOWERED` below its floor or over the exit limit, where a `NULL` cannot stand."""
    c = disc[i]
    if not c.gradable:
        return UNDERPOWERED
    cuts = cell_cuts(ds, c.cell)
    if cuts is None:
        return UNDERPOWERED
    ok = exit_limit_ok(exit_share(ds, c.cell[:3]),
                       arm_exit_shares(ds, c.cell, cuts, in_discovery))
    return NULL if ok else UNDERPOWERED


def pbo_matrix(ds: Dataset, cells: list[DiscCell], sessions: list[date]) -> np.ndarray:
    """T x N over the ranked cells: per session, the cell's top-minus-bottom position
    times y, in discovery's sign, with each column scaled to unit variance. Cuts come
    from discovery rows. A session outside both arms, or with no row, is 0."""
    pos = {d: i for i, d in enumerate(sessions)}
    M = np.zeros((len(sessions), len(cells)))
    for j, c in enumerate(cells):
        cuts = cell_cuts(ds, c.cell)
        if cuts is None:
            continue
        lo, hi = cuts
        for x, r in cell_pairs(ds, c.cell):
            if r["d"] in pos:
                M[pos[r["d"]], j] = c.sign * (r["y"] if x >= hi else -r["y"] if x <= lo else 0.0)
        sd = M[:, j].std()
        if sd > 0:
            M[:, j] /= sd
    return M


def run_pbo(ds: Dataset, cells: list[DiscCell], sessions: list[date], S: int = PBO_S):
    """`(result, zero rows padded at the head)`, or None under two ranked cells."""
    if len(cells) < 2:
        return None
    Mp, pad = PBO.pad_head(pbo_matrix(ds, cells, sessions), S)
    return PBO.cscv(Mp, S=S, metric=PBO.total_metric), pad


# ── the unconditional read ──────────────────────────────────────────────────

def worst_window(vals: list[float], width: int = BLOCK) -> float:
    if not vals:
        return float("nan")
    if len(vals) <= width:
        return sum(vals)
    return min(sum(vals[i:i + width]) for i in range(len(vals) - width + 1))


def mean_boot(v: list[float], n_boot: int, seed: int, block: int = BLOCK) -> tuple[float, float]:
    """The block-bootstrap `(point, two-sided p)` of a mean. It uses the same
    resampling as `FD.block_bootstrap` and adds the draws' p, which it does not return."""
    rng = random.Random(seed)
    draws = []
    for _ in range(n_boot):
        draws.append(statistics.fmean(v[i] for i in FD.resample_blocks(len(v), block, rng)))
    le = sum(d <= 0 for d in draws)
    ge = sum(d >= 0 for d in draws)
    return statistics.fmean(v), min(1.0, 2.0 * (min(le, ge) + 1) / (n_boot + 1))


def unconditional(rows: list[dict], side: str, n_boot: int = BOOT_N, seed: int = SEED,
                  block: int = BLOCK) -> dict:
    v = [r["net"][side] for r in rows]
    if not v:
        return dict(n=0, blocks=0, mean=float("nan"), ci=(float("nan"),) * 2, p=float("nan"),
                    disc=float("nan"), conf=float("nan"), window=float("nan"),
                    worst=float("nan"), worst_window=float("nan"), touch=float("nan"),
                    r=None, n_r=0)
    b = FD.block_bootstrap(v, v, mean_stat, block, n_boot, seed)
    _pt, p = mean_boot(v, n_boot, seed, block)

    def part(keep) -> float:
        return mean_stat(None, [r["net"][side] for r in rows if keep(r)])

    rs = [r["r"][side] for r in rows if r["r"].get(side) is not None]
    return dict(n=len(v), blocks=n_blocks([r["si"] for r in rows]), mean=b.point, ci=(b.lo, b.hi),
                p=p, disc=part(in_discovery), conf=part(in_confirmation),
                window=part(lambda r: not in_selloff_window(r["d"])), worst=min(v),
                worst_window=worst_window(v),
                touch=_mean_or_nan([r["touch"][side] for r in rows]),
                r=statistics.fmean(rs) if rs else None, n_r=len(rs))


def holm_series(ps: dict[tuple, dict[str, float]]) -> dict[tuple, dict[str, float]]:
    """Holm across the series. A series' p is its smaller side's. A side's adjusted p
    is the series' adjusted p when it is that side, and otherwise its own raw p under
    the series' multiplier, never below the series' adjusted p."""
    usable = {k: min(v.values()) for k, v in ps.items() if all(p == p for p in v.values())}
    adj = SPD.holm({"|".join(k): p for k, p in usable.items()})
    order = sorted(usable, key=lambda k: (usable[k], "|".join(k)))
    out: dict = {k: {s: float("nan") for s in v} for k, v in ps.items()}
    for i, k in enumerate(order):
        base = adj["|".join(k)][0]
        for s, p in ps[k].items():
            out[k][s] = max(base, min(1.0, (len(order) - i) * p))
    return out


def unconditional_token(n: int, blocks: int, adj_p: float, mean: float, disc: float, conf: float,
                        window: float, exit_ok: bool = True) -> str:
    """`CANDIDATE` needs the Holm-adjusted p below 0.05, and a positive mean overall, in
    both halves and with the windows cut. `CONTRARY` needs the same p on a negative mean."""
    if n < MIN_DATES or blocks < MIN_BLOCKS or mean != mean or not exit_ok:
        return UNDERPOWERED
    if adj_p != adj_p or adj_p >= ALPHA:
        return NULL
    if mean < 0:
        return CONTRARY
    return CANDIDATE if disc > 0 and conf > 0 and window > 0 else NULL


def bounded_rows(ds: Dataset, key: tuple, side: str) -> list[dict] | None:
    """A series' rows plus its dropped rows closed at the side's adverse touch. None when
    a short leg has no ask to bound one."""
    extra = []
    for e in ds.exit_drops.get(key, ()):
        if e["bound"].get(side) is None:
            return None
        extra.append(_synth_row(e, None))
    return sorted(ds.rows[key] + extra, key=lambda r: r["si"])


def grade_unconditional(ds: Dataset, n_boot: int = BOOT_N, seed: int = SEED) -> dict:
    """`{series + side: result}`, each with its Holm-adjusted p and token. Over the exit
    limit, a side is re-graded at the adverse touch: `UNDERPOWERED` if its token changes
    or no ask bounds a dropped row."""
    res = {key: {s: unconditional(ds.rows[key], s, n_boot, seed) for s in SIDES[key[2]]}
           for key in series_keys()}
    raw = {k: {s: u["p"] for s, u in v.items()} for k, v in res.items()}
    adj = holm_series(raw)
    out = {}
    for key, sides in res.items():
        share = exit_share(ds, key)
        for s, u in sides.items():
            u["adj_p"] = adj[key][s]
            u["exit_share"] = share
            args = (u["n"], u["blocks"], u["adj_p"], u["mean"], u["disc"], u["conf"], u["window"])
            token = unconditional_token(*args)
            if share > EXIT_DROP_MAX:
                rows_b = bounded_rows(ds, key, s)
                if rows_b is None or not can_stand_over_limit(token):
                    token = UNDERPOWERED
                else:
                    b = unconditional(rows_b, s, n_boot, seed)
                    alt = holm_series({**raw, key: {**raw[key], s: b["p"]}})[key][s]
                    t_b = unconditional_token(b["n"], b["blocks"], alt, b["mean"], b["disc"],
                                              b["conf"], b["window"])
                    token = token if t_b == token else UNDERPOWERED
            u["token"] = token
            out[key + (s,)] = u
    return out


# ── the two forward reads ───────────────────────────────────────────────────

def forward_awaiting(book: Book) -> int:
    return sum(1 for tk in TICKERS for t in TENORS
               for tr in book.trades(tk, t, FORWARD_START, None) if tr.status == "await")


def forward_mean_token(n: int, blocks: int, p: float, mean: float, exit_ok: bool = True) -> str:
    if n < MIN_DATES or blocks < MIN_BLOCKS or mean != mean:
        return STILL_OPEN
    if not exit_ok:
        return UNDERPOWERED
    if p >= ALPHA:
        return NULL
    return CANDIDATE if mean > 0 else CONTRARY


def forward_cell_token(floors: bool, point: float, p: float, disc_sign: int,
                       tradable: bool | None, exit_ok: bool = True) -> str:
    if not floors or point != point:
        return STILL_OPEN
    if not exit_ok:
        return UNDERPOWERED
    if p != p or p >= ALPHA:
        return NULL
    if _sign(point) == -disc_sign:
        return CONTRARY
    if tradable is None:
        return UNDERPOWERED
    return CANDIDATE if tradable else NULL


def _forward_side(fwd: Dataset, key: tuple) -> str:
    rows = fwd.rows[key[:3]]
    v = [r["net"][key[3]] for r in rows]
    mean, p = mean_boot(v, BOOT_N, SEED) if v else (float("nan"), float("nan"))
    blocks = n_blocks([r["si"] for r in rows])
    tok = forward_mean_token(len(v), blocks, p, mean)
    if exit_share(fwd, key[:3]) > EXIT_DROP_MAX and tok not in (STILL_OPEN,):
        rows_b = bounded_rows(fwd, key[:3], key[3])
        ok = rows_b is not None and can_stand_over_limit(tok)
        if ok:
            vb = [r["net"][key[3]] for r in rows_b]
            mb, pb = mean_boot(vb, BOOT_N, SEED)
            ok = forward_mean_token(len(vb), blocks, pb, mb) == tok
        tok = forward_mean_token(len(v), blocks, p, mean, ok)
    return f"{tok} ({len(v)} dates, mean {pct(mean)})"


def _forward_cell(fwd: Dataset, c: "Confirmed", cuts) -> str:
    s = c.cell[2]
    pairs = cell_pairs(fwd, c.cell)
    x, y, si = cell_xy(fwd, c.cell)
    point, p = shift_p(x, y, cut_stat(*cuts)) if x else (float("nan"),) * 2
    floors = floors_met(x, si, cuts)
    trad = position_clears(best_position(pairs, cuts, s, c.disc.sign)) if pairs else False
    tok = forward_cell_token(floors, point, p, c.disc.sign, trad)
    if tok != STILL_OPEN and not exit_limit_ok(exit_share(fwd, c.cell[:3]),
                                               arm_exit_shares(fwd, c.cell, cuts, None)):
        pb, unbounded = bounded_pairs(fwd, c.cell, cuts, c.disc.sign)
        ok = not unbounded and can_stand_over_limit(tok)
        if ok:
            bx, by = [a for a, _ in pb], [r["y"] for _, r in pb]
            pt_b, p_b = shift_p(bx, by, cut_stat(*cuts))
            tb = position_clears(best_position(pb, cuts, s, c.disc.sign))
            ok = forward_cell_token(floors, pt_b, p_b, c.disc.sign, tb) == tok
        tok = forward_cell_token(floors, point, p, c.disc.sign, trad, ok)
    return f"{tok} ({len(x)} dates, {pct(point)})"


def forward_read(book: Book, ds: Dataset, index: dict, baseline: dict, labeler,
                 cells: list, sides: list) -> list[str]:
    """Each `CANDIDATE` on signal dates from 2026-09-23: a side's mean and a cell's
    frozen-cut contrast, under the same exit-drop rule. Forward legs need their own
    fetch; a daily-flow-tab cell also waits for the holdout to open."""
    if not cells and not sides:
        return ["  FORWARD  no CANDIDATE, so nothing to grade"]
    awaiting = forward_awaiting(book)
    if awaiting:
        return [f"  FORWARD  {STILL_OPEN}: {awaiting} forward trades await a fetch"]
    fwd = build_dataset(book, index, baseline, labeler, FORWARD_START, None)
    lines = [f"  FORWARD  {' '.join(key)}: {_forward_side(fwd, key)}" for key in sides]
    for c in cells:
        f = FEATURE_BY_NAME[c.cell[3]]
        cuts = cell_cuts(ds, c.cell)
        if (f.source == "baseline" and not era_mod.SEAL_LIFTED) or not cuts:
            lines.append(f"  FORWARD  {cell_name(c.cell)}: {STILL_OPEN}")
            continue
        lines.append(f"  FORWARD  {cell_name(c.cell)}: {_forward_cell(fwd, c, cuts)}")
    return lines


def live_tokens(rows: list[dict]) -> dict[tuple, str]:
    """The LIVE read's words. BH runs across the cells at their floor."""
    qs = RM.bh_q([r["p"] if r["floors"] else float("nan") for r in rows])
    out = {}
    for r, q in zip(rows, qs):
        if not r["floors"] or r["point"] != r["point"] or not r["exit_ok"]:
            out[r["cell"]] = UNDERPOWERED
        else:
            passed = q == q and q <= CONFIRM_Q
            out[r["cell"]] = (NULL if not passed else UNDERPOWERED if r["tradable"] is None
                              else CANDIDATE if r["tradable"] else NULL)
    return out


def _live_row(cell, pairs, cuts, draws: int, n_boot: int) -> dict:
    x, y = [a for a, _ in pairs], [r["y"] for _, r in pairs]
    si = [r["si"] for _, r in pairs]
    floors = floors_met(x, si, cuts)
    point, p = (shift_p(x, y, cut_stat(*cuts), draws) if floors else
                (cut_stat(*cuts)(x, y) if cuts and x else float("nan"), float("nan")))
    pos = best_position(pairs, cuts, cell[2], _sign(point), n_boot) if floors else None
    return dict(cell=cell, n=len(x), floors=floors, point=point, p=p,
                tradable=position_clears(pos), position=pos, exit_ok=True)


def live_read(book: Book, ds: Dataset, index: dict, baseline: dict, labeler,
              draws: int = SHIFT_N, n_boot: int = BOOT_N) -> tuple[dict, list[dict], int]:
    """The shortlist on LIVE rows only: `(tokens, rows, forward trades awaiting)`. Before
    the holdout opens it reads the window's LIVE rows, and they sit below the floor. After
    it, it reads every LIVE row once the forward legs are cached. Exit drops use the
    series' share and the arms' shares on LIVE rows."""
    fwd = ds
    awaiting = 0
    if era_mod.SEAL_LIFTED:
        awaiting = forward_awaiting(book)
        if not awaiting:
            fwd = build_dataset(book, index, baseline, labeler, WINDOW[0], None)
    rows = []
    for cell in shortlist_cells():
        cuts = cell_cuts(ds, cell)
        rows.append(_live_row(cell, cell_pairs(fwd, cell, lag="LIVE"), cuts, draws, n_boot))
    base = live_tokens(rows)
    for i, (cell, r) in enumerate(zip(shortlist_cells(), rows)):
        cuts = cell_cuts(ds, cell)
        if not r["floors"] or cuts is None or exit_limit_ok(
                exit_share(fwd, cell[:3]), arm_exit_shares(fwd, cell, cuts, None, lag="LIVE")):
            continue
        pb, unbounded = bounded_pairs(fwd, cell, cuts, _sign(r["point"]), lag="LIVE")
        if unbounded or not can_stand_over_limit(base[cell]):
            r["exit_ok"] = False
            continue
        alt = _live_row(cell, pb, cuts, draws, n_boot)
        r["exit_ok"] = live_tokens(rows[:i] + [alt] + rows[i + 1:])[cell] == base[cell]
    return live_tokens(rows), rows, awaiting


# ════════════════════════════════════════════════════════════════════════════
# The report
# ════════════════════════════════════════════════════════════════════════════

RULE = "=" * 78


def hdr(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def pct(v) -> str:
    return "n/a" if v is None or v != v else f"{v * 100:+.3f}%"


def cell_name(cell: tuple) -> str:
    return " ".join(cell)


def print_coverage(book: Book) -> None:
    """Counts only: trades and contracts, per ticker and tenor."""
    print(f"  {'ticker':<7}{'tenor':<6}{'trades':>7}{'built':>7}{'await':>7}{'drop':>6}"
          f"{'open':>6}   {'contracts found':>15}{'awaited':>9}{'re-fetch':>10}")
    for (tk, tn), k in book.coverage().items():
        c = k["c"]
        n = c["built"] + c["await"] + c["drop"] + c["open"]
        print(f"  {tk:<7}{tn:<6}{n:>7}{c['built']:>7}{c['await']:>7}{c['drop']:>6}"
              f"{c['open']:>6}   {k['found']:>15}{k['awaited']:>9}{k['refetch']:>10}")
        why = {w[4:]: v for w, v in sorted(c.items()) if w.startswith("why:") and v}
        if why:
            print("      " + "  ".join(f"{w}={v}" for w, v in why.items()))


def print_header(book: Book, census: dict) -> None:
    print("daily_vol_structure — daily straddles and 1x2 ratios on QQQ and SMH")
    print(f"Registration: {REGISTRATION} (accepted by default {ACCEPTED})")
    print(f"Era: analysis features are era {census['era']}; price, volume and option series "
          "are era-free.")
    print(census["seal"])
    sig = book.signals()
    print(f"Window: {WINDOW[0]} to {WINDOW[1]}, {len(sig)} sessions. "
          f"First confirmation date {FIRST_CONFIRM}. Forward from {FORWARD_START}.")
    print("T30 and T7 are labels: true DTE at the fill runs 21-53 and 6-11.")


def print_quality(ds: Dataset) -> None:
    hdr("QUALITY — exit drops, wide quotes and how far ATM sits from spot")
    print("  Above 5% a series is re-graded with dropped rows at the adverse touch; a changed")
    print("  verdict reads UNDERPOWERED. `bound` is that mean; `open` counts rows no ask can bound.")
    print(f"  {'series':<14}{'rows':>5}{'exit%':>7}{'up':>4}{'down':>5}{'wide%':>7}"
          f"{'|ATM/D|':>9}{'|ATM/fill|':>11}{'front aware':>13}   bound by side")
    for key in series_keys():
        rows = ds.rows[key]
        ex = ds.exit_drops.get(key, [])
        n = len(rows)
        wide = sum(r["wide"] for r in rows) / n if n else float("nan")
        aware = pct(_mean_or_nan([r["front_aware"] for r in rows])) if key[2] != "S" else "-"
        parts = []
        for side in SIDES[key[2]]:
            have = [e["bound"][side] for e in ex if e["bound"][side] is not None]
            mean = _mean_or_nan([r["net"][side] for r in rows] + have)
            parts.append(f"{side} {pct(mean)} open {len(ex) - len(have)}")
        print(f"  {' '.join(key):<14}{n:>5}{exit_share(ds, key) * 100:>6.1f}%"
              f"{sum(e['up'] is True for e in ex):>4}{sum(e['up'] is False for e in ex):>5}"
              f"{wide * 100:>6.1f}%{pct(_mean_or_nan([r['atm_d'] for r in rows])):>9}"
              f"{pct(_mean_or_nan([r['atm_fill'] for r in rows])):>11}{aware:>13}   "
              + "  ".join(parts))


def print_analysis(ds: Dataset) -> None:
    hdr(f"ANALYSIS FEATURES — {RETRO_ONLY}: description, outside every test and tally")
    print("  Discovery's labels were written after the fact. Top minus bottom, whole window.")
    print(f"  {'cell':<30}{'ALL n':>6}{'ALL':>10}{'LIVE n':>7}{'LIVE':>10}{'RETRO n':>8}{'RETRO':>10}"
          f"{'word':>12}")
    for cell in analysis_cells():
        cuts = cell_cuts(ds, cell)
        parts = []
        for lag in (None, "LIVE", "RETRO"):
            x, y, _ = cell_xy(ds, cell, lag=lag)
            parts.append((len(x), cut_stat(*cuts)(x, y) if cuts and x else float("nan")))
        print(f"  {cell_name(cell):<30}{parts[0][0]:>6}{pct(parts[0][1]):>10}"
              f"{parts[1][0]:>7}{pct(parts[1][1]):>10}{parts[2][0]:>8}{pct(parts[2][1]):>10}"
              f"{RETRO_ONLY:>12}")


def write_trades(ds: Dataset) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRADES_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ticker", "tenor", "structure", "signal", "exit", "expiry", "dte", "atm", "wing",
                    "debit", "y", "net_long_or_back", "net_front"])
        for (tk, tn, s), rows in ds.rows.items():
            for r in rows:
                w.writerow([tk, tn, s, r["date"], r["exit"], r["expiry"], r["dte"], r["atm"],
                            r["wing"], r["debit"], r["y"],
                            r["net"].get("long", r["net"].get("back")),
                            r["net"].get("front", "")])
    print(f"  trades -> {TRADES_CSV.relative_to(ROOT)}")


def print_confirmed(conf: list[Confirmed]) -> None:
    print(f"  {'cell':<30}{'n':>5}{'top-bot':>10}{'p':>8}{'q':>8}{'CI95':>22}{'token':>14}"
          f"  tradable at mid")
    for c in conf:
        print(f"  {cell_name(c.cell):<30}{c.n:>5}{pct(c.point):>10}{c.p:>8.3f}{c.q:>8.3f}"
              f"{'[' + pct(c.ci[0]) + ',' + pct(c.ci[1]) + ']':>22}{c.token:>14}"
              f"  {'yes' if c.tradable else 'no'}")
        if c.position:
            pos = c.position
            print(f"      position: {pos['side']} in the {pos['arm']} arm, n {pos['n']}, net at mid "
                  f"{pct(pos['mean'])} (p {pos['p']:.3f}), strict touch {pct(pos['touch'])}")
        for side, tab in c.arms.items():
            print(f"      {side:<6} net at mid / strict touch: " + "  ".join(
                f"{a} n {t[0]} {pct(t[1])} / {pct(t[2])}" for a, t in tab.items()))
        cyc = "  ".join(f"{b}: {pct(v[0])} n {v[1]}" for b, v in c.buckets.items()) or "none"
        print(f"      cycle: {cyc}"
              + f"   holds {c.cycle}   feature vs DTE rho {c.dte_corr:+.3f}")
        print(f"      exit drops: series {c.series_exit * 100:.1f}%  top "
              f"{c.arm_exit['top'] * 100:.1f}%  bottom {c.arm_exit['bottom'] * 100:.1f}%  "
              f"{c.exit_note}")
        print(f"      robustness, not replication and not in the bar: other ticker n {c.other_n} "
              f"{pct(c.other_point)};  sell-off windows cut {pct(c.window_point)}")
    print("  QQQ and SMH share episodes, so the other-ticker line is weak evidence.")


def outcomes(book: Book, index: dict, baseline: dict, labeler) -> int:
    """Everything past the gate."""
    ds = build_dataset(book, index, baseline, labeler)
    hdr("DROPS — per series, with the printed reason")
    for key, c in ds.drops.items():
        print(f"  {' '.join(key):<14} rows {len(ds.rows[key]):>4}  "
              + ("  ".join(f"{k}={v}" for k, v in sorted(c.items())) or "none"))
    print_quality(ds)

    hdr("1. UNCONDITIONAL — does it pay every day? Net of commission, share of spot")
    print("  Holm across the 12 series. Strict touch and R print and are never graded.")
    print(f"  {'series':<14}{'side':<7}{'n':>5}{'mean':>10}{'CI95':>22}{'adj p':>7}{'disc':>10}"
          f"{'conf':>10}{'no-win':>10}{'token':>14}{'touch':>10}{'R':>8}{'worst':>10}{'worst21':>10}")
    uncond = grade_unconditional(ds)
    for key, u in uncond.items():
        r = "n/a" if u["r"] is None else f"{u['r']:+.3f}"
        print(f"  {' '.join(key[:3]):<14}{key[3]:<7}{u['n']:>5}{pct(u['mean']):>10}"
              f"{'[' + pct(u['ci'][0]) + ',' + pct(u['ci'][1]) + ']':>22}{u['adj_p']:>7.3f}"
              f"{pct(u['disc']):>10}{pct(u['conf']):>10}{pct(u['window']):>10}{u['token']:>14}"
              f"{pct(u['touch']):>10}{r:>8}{pct(u['worst']):>10}{pct(u['worst_window']):>10}")
    print(f"  {FRONT_CAVEAT}")
    print(f"  {STRADDLE_CAVEAT}")

    hdr("2. DISCOVERY — first 60% of dates; Spearman against a circular-shift null, BH")
    disc = discover(ds)
    rk = ranked(disc)
    print(f"  cells {len(disc)}  gradable {sum(c.gradable for c in disc)}  "
          f"ranked (q <= {BH_Q}) {len(rk)}")
    print(f"  {'cell':<30}{'n':>5}{'rho':>8}{'top-bot':>10}{'p':>8}{'q':>8}")
    for c in disc:
        if c.gradable:
            print(f"  {cell_name(c.cell):<30}{c.n:>5}{c.rho:>+8.3f}{pct(c.contrast):>10}"
                  f"{c.p:>8.3f}{c.q:>8.3f}")
    print(f"  below the power floor on discovery dates: {sum(not c.gradable for c in disc)} cells")

    hdr("3. CONFIRMATION — last 40% of dates; only the ranked list")
    conf = confirm(ds, rk)
    print_confirmed(conf)

    hdr("PBO — printed over the ranked cells, each column at unit variance; not in the bar")
    res = run_pbo(ds, rk, book.signals())
    if res is None:
        print("  not computed: a lone ranked cell has nothing to be ranked against")
    else:
        r0, pad = res
        print(f"  configs {r0.n_configs}  rows {r0.n_rows} (+{pad} zero rows at the head)  "
              f"S {r0.S}  PBO {r0.pbo:.3f}")

    print_analysis(ds)

    hdr("LIVE READ — mkt_dir, mkt_vol, mkt_hp_score on LIVE rows only")
    live, live_rows, live_await = live_read(book, ds, index, baseline, labeler)
    for r in live_rows:
        pos = r["position"]
        extra = (f"  {pos['side']} {pos['arm']} net {pct(pos['mean'])} touch {pct(pos['touch'])}"
                 if pos else "")
        print(f"  {cell_name(r['cell']):<30}{r['n']:>4} LIVE dates {pct(r['point']):>10}  "
              f"{live[r['cell']]}{extra}")
    if live_await:
        print(f"  {live_await} forward trades await a fetch, so this reads the window's rows only.")
    print("  LIVE rows stop accumulating if the analysis pipeline is retired.")

    hdr("VERDICT")
    conf_by = {c.cell: c for c in conf}
    tally: Counter = Counter()
    for i, c in enumerate(disc):
        tally[conf_by[c.cell].token if c.cell in conf_by else unranked_token(ds, disc, i)] += 1
    u_t = Counter(u["token"] for u in uncond.values())
    pays = [" ".join(k) for k, u in uncond.items() if u["token"] == CANDIDATE]
    cand_cells = [c for c in conf if c.token == CANDIDATE]
    print(f"  Pays every day: {', '.join(pays) or 'none'}")
    print(f"  Moves with a known feature: {', '.join(cell_name(c.cell) for c in cand_cells) or 'none'}")
    live_cands = [r["cell"] for r in live_rows if live[r["cell"]] == CANDIDATE]
    print(f"  LIVE read, its own forward test: {', '.join(map(cell_name, live_cands)) or 'none'}")
    print("  cells (144): " + "  ".join(f"{k} {tally[k]}" for k in
                                        (CANDIDATE, CONTRARY, NULL, UNDERPOWERED)))
    print("  unconditional (20 sides): " + "  ".join(f"{k} {u_t[k]}" for k in
                                                     (CANDIDATE, CONTRARY, NULL, UNDERPOWERED)))
    print(f"  analysis cells (108): {RETRO_ONLY}, not tallied")
    for c in conf:
        print(f">>> daily_vol_structure {cell_name(c.cell)}: {c.token} | tradable at mid: "
              f"{'yes' if c.tradable else 'no'} <<<")
    for key, u in uncond.items():
        print(f">>> daily_vol_structure UNCONDITIONAL {' '.join(key)}: {u['token']} <<<")
    for cell in live_cands:
        print(f">>> daily_vol_structure LIVE {cell_name(cell)}: {CANDIDATE} <<<")
        print(f"  FORWARD  LIVE {cell_name(cell)}: the LIVE read is its own forward test")
    for line in forward_read(book, ds, index, baseline, labeler, cand_cells,
                             [k for k, u in uncond.items() if u["token"] == CANDIDATE]):
        print(line)
    print("  Nothing ships from this study. A CANDIDATE earns only a forward grade.")
    write_trades(ds)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    index, census = load_analysis()
    book = build_book()
    print_header(book, census)
    n_market = sum(1 for tk, d in index if tk == "MARKET" and WINDOW[0].isoformat() <= d
                   <= WINDOW[1].isoformat())
    era_mod.require_dates(n_market, census["era"], minimum=ERA_MIN_DATES,
                          what="MARKET dates in the window")

    hdr("COVERAGE — counts only; no option price is read before the gate")
    print_coverage(book)
    try:
        book.open_outcomes()
    except AwaitingScrape as exc:
        hdr(f"VERDICT: {NOT_BUILT}")
        for line in str(exc).split("; "):
            print(f"  {line}")
        print("  No outcome was computed for any series, and nothing was written.")
        return 0
    return outcomes(book, index, load_baseline(), MechLabeler.from_csv(VIX_TABLE))


if __name__ == "__main__":
    raise SystemExit(main())
