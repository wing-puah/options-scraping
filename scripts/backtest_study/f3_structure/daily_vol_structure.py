"""daily_vol_structure — daily straddles and 1x2 ratios on QQQ and SMH, read against features.

Registration: `research/pre-registrations/f3_structure/daily_vol_structure.md`
(accepted by default 2026-11-06, before any QQQ or SMH option outcome was read).
That file is the spec; every constant and verdict word here is its. RESEARCH
TIER: nothing ships from this study.

WHAT IT COMPUTES. Every session D in the window, on each of QQQ and SMH and on
each of two tenors, it opens three structures: a long ATM straddle (S), a call
ratio (RC) and a put ratio (RP). Features are known at D's close; every leg
fills at the D+1 closing mid; each trade closes a fixed number of sessions
later. That gives 12 outcome series.

ONE SIGNED SERIES. On the same strikes a front ratio is exactly minus a back
ratio at mid, before commission. So each ratio series stores the BACK ratio's
gross P&L, and the front ratio is `-y`. Every correlation is run once on that
series. To keep the identity exact each leg has ONE price: the closing mid from
`simulate.entry_day_fill(row, +1)`. A bought-side call returns the mid for a
normal or a wide two-sided quote and refuses a quote with no bid, so a junk leg
cannot price differently for the two sides. Commission and the natural fill
differ by side and are computed per side.

OWN FIXED EXIT. `run_trade` closes every leg at the exit session's mark. It
never calls the frozen harness or `_simulate`, so a credit entry cannot reach
the `CREDIT_PROD` exit profile.

THE GATE. `Book.price` and `Book.option_row` raise until `Book.open_outcomes`
has seen no problem: no trade in ANY ticker and tenor awaiting a contract, OHLC
reaching the window's end, and `Price~` agreeing with the closes. It is
all-or-nothing, so a partly cached leg set cannot produce a partial figure.
While it is shut the run prints coverage counts and `NOT BUILT — AWAITING
SCRAPE`, and writes nothing.

REUSED, NEVER COPIED. Entry: `simulate.entry_day_fill`,
`_monotonicity_violation`. Exit mark: `selloff_put_diagonal.leg_mark` (shared
`_snap_asof`, `_is_junk_quote`, `junk_day_mark`). Touch price:
`index_vrp.natural_fill`. Grid: `mechanical_benchmark`'s `grid_step`,
`grid_around`, `listed_by`, `monthly_expiries`. Label and lag:
`market_read.parse_label`, `lag_bin`. FDR: `regime_map.bh_q`. Statistics:
`lib/forward_drawdown` and `lib/pbo.py::cscv`. Era and seal: `lib/era.py`.
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
DISC_BOOT_N = 2_000
BLOCK = 21                   # rows; at least the hold of both tenors
BH_Q = 0.10
PBO_MAX = 0.5
PBO_S = 16
ANALYSIS_ERA = "v4"
ERA_MIN_DATES = 60
#: C0 power floors, per cell.
MIN_DATES = 60
MIN_BLOCKS = 6
MIN_ARM_DATES = 12
MIN_ARM_BLOCKS = 3
#: Prior sessions an option-volume mean needs, out of 20.
OPT_VOL_MIN_PRIOR = 15
#: An expiry with no cached row by the decision day is proven unlisted once this
#: many of its strikes are skip-listed on evidence.
EXPIRY_UNLISTED_PROOF = 3
#: `Price~` against the close: a run this long, this far off 1, refuses.
SPLIT_TOL = 0.10
SPLIT_RUN = 3
#: `vol_sleeve`'s two windows, by signal date.
VOL_SLEEVE_WINDOWS = ((date(2025, 3, 1), date(2025, 4, 30)),
                      (date(2026, 2, 1), date(2026, 4, 30)))

NOT_BUILT = "NOT BUILT — AWAITING SCRAPE"
CANDIDATE, CONTRARY, NULL, UNDERPOWERED = "CANDIDATE", "CONTRARY", "NULL", "UNDERPOWERED"
STILL_OPEN = "STILL-OPEN"

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


def features_for(ticker: str) -> list[Feature]:
    return [f for f in FEATURES if ticker == "QQQ" or not f.qqq_only]


def series_keys() -> list[tuple[str, str, str]]:
    return [(tk, t.name, s) for tk in TICKERS for t in TENORS for s in STRUCTURES]


def all_cells() -> list[tuple[str, str, str, str]]:
    return [(tk, tn, s, f.name) for tk, tn, s in series_keys() for f in features_for(tk)]


# ════════════════════════════════════════════════════════════════════════════
# Calendar and expiries
# ════════════════════════════════════════════════════════════════════════════

def split_index(n: int) -> int:
    """How many of `n` chronological dates form the discovery set."""
    return int(n * DISCOVERY_SHARE)


def in_sleeve_window(d: date) -> bool:
    return any(a <= d <= b for a, b in VOL_SLEEVE_WINDOWS)


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


def _leg(ticker: str, opt: str, expiry: date, strike: float, qty: int = 1) -> Leg:
    return Leg(qty, ticker, expiry, float(strike), opt)


def walk_strike(chain, evidence: set[str], ticker: str, expiry: date, target: float,
                spot: float, asof: date, opts: tuple[str, ...]) -> Sel:
    """The strike nearest `target` that lists every type in `opts`, nearest first.

    `selloff_put_diagonal.nearest_listed` with the ticker and a set of types as
    parameters (a test pins them together). Skip-listed on evidence: step on.
    Cached with a row on or before `asof`: chosen. Cached without one: not
    listed yet, step on. Otherwise AWAIT: it could be the nearest listed one.
    """
    cached = sorted(k for k in chain.strikes(ticker, expiry)
                    if all(chain.cached(ticker, expiry, k, o) for o in opts))
    step = MB.grid_step(spot, cached)
    for k in MB.grid_around(target, step, cached):
        if any(NTF.contract_stem(ticker, expiry, k, o) in evidence for o in opts):
            continue
        missing = tuple((o, expiry, k) for o in opts if not chain.cached(ticker, expiry, k, o))
        if missing:
            return Sel("await", k, "strike_not_cached", missing)
        if all(MB.listed_by(chain, _leg(ticker, o, expiry, k), asof) for o in opts):
            return Sel("built", k)
    return Sel("drop", reason="no_listed_strike")


class Listing:
    """Is an expiry listed by a date? Memoised first-row dates, and the count of
    skip-listed strikes per expiry."""

    def __init__(self, chain, evidence: set[str]):
        self.chain = chain
        self._first: dict[tuple[str, date], date | None] = {}
        self.proven: Counter = Counter()
        for stem in evidence:
            parts = stem.split("_")
            if len(parts) == 3:
                self.proven[(parts[0], parts[1])] += 1

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

    def state(self, ticker: str, expiry: date, asof: date) -> str:
        """`yes`, `no` or `unknown`. Unknown means walk the strikes; the walk names
        the contracts to fetch. `no` needs three strikes skip-listed on evidence. A
        cached file that starts after `asof` proves nothing, because older fetches
        hold shallow histories."""
        first = self.first_row(ticker, expiry)
        if first is not None and first <= asof:
            return "yes"
        if self.proven[(ticker, expiry.strftime("%Y%m%d"))] >= EXPIRY_UNLISTED_PROOF:
            return "no"
        return "unknown"


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
    if listing.state(ticker, expiry, signal) == "no":
        tr.reason = "expiry_not_listed"
        return tr
    x = WING[(ticker, tenor.name)]
    atm = walk_strike(chain, evidence, ticker, expiry, spot, spot, signal, ("Call", "Put"))
    wc = walk_strike(chain, evidence, ticker, expiry, spot * (1 + x), spot, signal, ("Call",))
    wp = walk_strike(chain, evidence, ticker, expiry, spot * (1 - x), spot, signal, ("Put",))
    sels = (atm, wc, wp)
    for s in sels:
        if s.status == "drop":
            tr.reason = s.reason
            return tr
    tr.fetch = tuple(f for s in sels for f in s.fetch)
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
    natural: dict                      # side -> net P&L at the touch, points
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

    def natural_net(self, side: str) -> float:
        return self.natural[side] / self.spot

    def r(self, side: str) -> float | None:
        """Net P&L over max loss, where the risk is defined and positive."""
        wing = {"RC": self.tr.wing_c, "RP": self.tr.wing_p}.get(self.structure)
        risk = risk_points(self.structure, side, self.tr.atm, wing, self.debit)
        if risk is None or risk <= 0:
            return None
        return (side_sign(side) * self.gross - self.comm) / risk


def run_trade(chain, tr: Trade, structure: str) -> Priced | str:
    """Price one built trade. `Priced`, or a printed drop reason.

    Entry: every leg's closing mid on the fill day, on `entry_day_fill(row, +1)`
    so each leg has one price whichever side holds it. No leg moves to another
    day. Exit: `selloff_put_diagonal.leg_mark` on the exit session; a leg with no
    row that day, or only a carried mark, drops the row. Never the harness.
    """
    if tr.status != "built":
        raise ValueError(f"cannot price a {tr.status} trade")
    legs = structure_legs(tr, structure)
    tags: Counter = Counter()
    in_rows, prices, ftags = [], [], []
    for lg in legs:
        row = chain.history(lg)[1].get(tr.fill)
        fill = SIM.entry_day_fill(row, 1)
        if fill is None:
            return "no_entry_quote"
        if fill[0] is None:
            return SIM.JUNK_ENTRY_REFUSAL
        in_rows.append(row)
        prices.append(fill[0])
        ftags.append(fill[1])
        tags[fill[1]] += 1
    if SIM._monotonicity_violation(legs, prices, ftags):
        return SIM.NON_MONOTONIC_REFUSAL
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
    natural = {}
    for side in SIDES[structure]:
        s = side_sign(side)
        pnl = 0.0
        for lg, r_in, r_out in zip(legs, in_rows, out_rows):
            q = s * lg.qty
            px_in, _ = IV.natural_fill(r_in, sold=q < 0)
            px_out, _ = IV.natural_fill(r_out, sold=q > 0)
            pnl += q * (px_out - px_in)
        natural[side] = pnl - comm
    return Priced(tr, structure,
                  {(lg.opt_type, lg.strike): p for lg, p in zip(legs, prices)},
                  {(lg.opt_type, lg.strike): m for lg, m in zip(legs, marks)},
                  debit, gross, comm, natural, tags)


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
        if len(prior) >= OPT_VOL_MIN_PRIOR and statistics.fmean(prior) > 0:
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
    """`{D: {qqq_prem, qqq_cp}}` from BaselineDaily. A blank or a zero put is missing."""
    out: dict[str, dict[str, float | None]] = {}
    if not path.exists():
        return out
    with open(path, newline="") as fh:
        rows, _ = era_mod.drop_sealed(list(csv.DictReader(fh)), date_key="date")
    for r in rows:
        c, p = _to_float(r.get("qqq_call_prem")), _to_float(r.get("qqq_put_prem"))
        out[str(r["date"])[:10]] = {
            "qqq_prem": c + p if c is not None and p is not None else None,
            "qqq_cp": c / p if c is not None and p else None}
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
                found, awaited = set(), set()
                for tr in self.trades(tk, t):
                    c[tr.status] += 1
                    c[f"why:{tr.reason}"] += bool(tr.reason)
                    found |= set(tr.found)
                    awaited |= set(tr.fetch)
                out[(tk, t.name)] = dict(c=c, found=len(found), awaited=len(awaited))
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
    """Unique uncached contracts the awaiting trades name. A contract two trades
    name is listed once. The collector imports this; a re-run re-targets.
    `scope`: `window` (the graded dates) or `forward` (from 2026-09-23)."""
    lo, hi = (WINDOW[0], WINDOW[1]) if scope == "window" else (FORWARD_START, None)
    seen: dict = {}
    for tk in TICKERS:
        for t in TENORS:
            for tr in book.trades(tk, t, lo, hi):
                if tr.status != "await":
                    continue
                for o, e, k in tr.fetch:
                    seen.setdefault((tk, o, e, round(float(k), 4)), f"{tk}:{t.name}")
    return [dict(ticker=tk, expiration=e, strike=k, opt_type=o, category=cat)
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


def build_dataset(book: Book, index: dict, baseline: dict, labeler: MechLabeler,
                  lo: date = WINDOW[0], hi: date | None = WINDOW[1]) -> Dataset:
    """Past the gate only: `Book.price` and `Book.option_row` raise otherwise."""
    book._require_open()
    rows, feats, drops = {}, {}, {}
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
                fv.update(baseline.get(iso) or {"qqq_prem": None, "qqq_cp": None})
                fv.update(analysis_features(index, tk, iso))
                fmap[iso] = fv
            feats[(tk, t.name)] = fmap
            for s in STRUCTURES:
                out, drop = [], Counter()
                for tr in trades:
                    if tr.status != "built":
                        drop[tr.reason or tr.status] += 1
                        continue
                    p = book.price(tr, s)
                    if isinstance(p, str):
                        drop[p] += 1
                        continue
                    out.append(dict(
                        d=tr.signal, date=tr.signal.isoformat(), exit=tr.exit,
                        si=book.index[tr.signal], y=p.y,
                        net={sd: p.net(sd) for sd in SIDES[s]},
                        natural={sd: p.natural_net(sd) for sd in SIDES[s]},
                        r={sd: p.r(sd) for sd in SIDES[s]}, debit=p.debit,
                        expiry=tr.expiry, atm=tr.atm, wing=(tr.wing_c if s == "RC" else
                                                            tr.wing_p if s == "RP" else None)))
                rows[(tk, t.name, s)] = out
                drops[(tk, t.name, s)] = drop
    return Dataset(rows, feats, index, drops)


# ════════════════════════════════════════════════════════════════════════════
# Statistics — pure functions on synthetic-testable rows
# ════════════════════════════════════════════════════════════════════════════

def mean_stat(_x, y) -> float:
    """The mean of the usable y, in `block_bootstrap`'s `(x, y)` form."""
    v = [float(b) for b in y if b is not None]
    return statistics.fmean(v) if v else float("nan")


def cut_stat(lo: float, hi: float) -> Callable:
    """mean(y | x >= hi) - mean(y | x <= lo), `block_bootstrap`'s form. A discrete
    feature needs this: `tercile_contrast` splits tied x by position."""
    def stat(x, y) -> float:
        top = [float(b) for a, b in zip(x, y) if b is not None and a >= hi]
        bot = [float(b) for a, b in zip(x, y) if b is not None and a <= lo]
        if not top or not bot:
            return float("nan")
        return statistics.fmean(top) - statistics.fmean(bot)
    return stat


def contrast_fn(f: Feature) -> Callable:
    return FD.tercile_contrast if f.kind == "rank" else cut_stat(f.lo, f.hi)


def spearman_draws(x, y, n_boot: int, seed: int, block: int = BLOCK) -> list[float]:
    """The draws `block_bootstrap(x, y, spearman, ...)` makes (same indices)."""
    rng = random.Random(seed)
    out = []
    for _ in range(n_boot):
        idx = FD.resample_blocks(len(x), block, rng)
        out.append(FD.spearman([x[i] for i in idx], [y[i] for i in idx]))
    return out


def boot_p(point: float, draws: list[float]) -> float:
    """Two-sided normal p from the block-bootstrap standard error. Continuous, so
    a small draw count puts no floor under the FDR step."""
    v = [d for d in draws if d == d]
    if point != point or len(v) < 2:
        return float("nan")
    se = statistics.stdev(v)
    if se <= 0:
        return float("nan")
    return math.erfc(abs(point / se) / math.sqrt(2))


def n_blocks(si: list[int]) -> int:
    return len({i // BLOCK for i in si})


def arms(f: Feature, x: list[float], si: list[int]) -> list[list[int]]:
    """The session indices of the bottom and the top arm."""
    if f.kind == "rank":
        lab = FD.rank_groups(x)
        return [[i for i, g in zip(si, lab) if g == 0], [i for i, g in zip(si, lab) if g == 2]]
    return [[i for i, a in zip(si, x) if a <= f.lo], [i for i, a in zip(si, x) if a >= f.hi]]


def floors_met(f: Feature, x: list[float], si: list[int]) -> bool:
    """C0: the power floor every cell must meet on the dates it is read on."""
    if len(x) < MIN_DATES or n_blocks(si) < MIN_BLOCKS:
        return False
    return all(len(a) >= MIN_ARM_DATES and n_blocks(a) >= MIN_ARM_BLOCKS for a in arms(f, x, si))


def cell_xy(ds: Dataset, cell: tuple, keep: Callable[[dict], bool] | None = None,
            lag: str | None = None, feature_ticker: str | None = None,
            value: Callable[[dict], float] | None = None) -> tuple[list, list, list]:
    """`(x, y, si)` for one cell on the rows `keep` admits, in date order, on rows
    whose feature is present. `lag` keeps one lag bin of an analysis feature."""
    tk, tn, s, name = cell
    f = FEATURE_BY_NAME[name]
    ftk = feature_ticker or tk
    fmap = ds.features[(ftk, tn)]
    xs, ys, si = [], [], []
    for r in ds.rows[(tk, tn, s)]:
        if keep is not None and not keep(r):
            continue
        v = (fmap.get(r["date"]) or {}).get(name)
        if v is None:
            continue
        if lag is not None and feature_lag(ds.index, f, ftk, r["date"]) != lag:
            continue
        xs.append(float(v))
        ys.append(value(r) if value else r["y"])
        si.append(r["si"])
    return xs, ys, si


def in_discovery(r: dict) -> bool:
    """A discovery row is signalled, and closed, before the first confirmation
    date. A trade that closes on or after it would read a confirmation quote."""
    return r["d"] < FIRST_CONFIRM and r["exit"] < FIRST_CONFIRM


def in_confirmation(r: dict) -> bool:
    return r["d"] >= FIRST_CONFIRM


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
        v = self.rho if self.rho == self.rho else 0.0
        return (v > 0) - (v < 0)


def discover(ds: Dataset, n_boot: int = DISC_BOOT_N, seed: int = SEED) -> list[DiscCell]:
    """Spearman and top-minus-bottom on the discovery rows only, BH across every
    gradable cell. Sorted by q, then p. Reads no confirmation date."""
    out = []
    for cell in all_cells():
        f = FEATURE_BY_NAME[cell[3]]
        x, y, si = cell_xy(ds, cell, keep=in_discovery)
        ok = floors_met(f, x, si)
        if not ok:
            out.append(DiscCell(cell, len(x), False, float("nan"), float("nan"), float("nan")))
            continue
        rho = FD.spearman(x, y)
        out.append(DiscCell(cell, len(x), True, rho, contrast_fn(f)(x, y),
                            boot_p(rho, spearman_draws(x, y, n_boot, seed))))
    for c, q in zip(out, RM.bh_q([c.p for c in out])):
        c.q = q
    return sorted(out, key=lambda c: (not c.gradable, c.q if c.q == c.q else 2.0,
                                      c.p if c.p == c.p else 2.0, c.cell))


def ranked(cells: list[DiscCell]) -> list[DiscCell]:
    """The ranked list: gradable cells at BH q <= 0.10. Only these move on."""
    return [c for c in cells if c.gradable and c.q == c.q and c.q <= BH_Q]


def excludes_zero(lo: float, hi: float) -> bool:
    return lo == lo and hi == hi and (lo > 0 or hi < 0)


def other_ticker(tk: str) -> str:
    return "SMH" if tk == "QQQ" else "QQQ"


def _sign(v: float) -> int:
    return (v > 0) - (v < 0) if v == v else 0


def confirm_token(disc_sign: int, point: float, lo: float, hi: float, floors: bool,
                  other_floors: bool, other_sign: int, sleeve_sign: int,
                  pbo: float | None) -> str:
    """The cell's verdict. The first matching row wins (registration, Verdicts)."""
    if not floors or point != point:
        return UNDERPOWERED
    cleared = excludes_zero(lo, hi)
    if cleared and _sign(point) == -disc_sign:
        return CONTRARY
    if not (cleared and _sign(point) == disc_sign):
        return NULL
    if not other_floors:
        return UNDERPOWERED
    if other_sign != disc_sign or sleeve_sign != disc_sign:
        return NULL
    if pbo is None or not pbo < PBO_MAX:
        return NULL
    return CANDIDATE


@dataclasses.dataclass
class Confirmed:
    cell: tuple
    disc: DiscCell
    n: int
    point: float
    ci: tuple
    other_n: int
    other_point: float
    sleeve_point: float
    token: str
    natural: dict
    hold_ci: tuple


def confirm(ds: Dataset, cells: list[DiscCell], pbo: float | None, holds: dict | None = None,
            n_boot: int = BOOT_N, seed: int = SEED) -> list[Confirmed]:
    """Every clause of the bar, on confirmation rows. An analysis cell reads
    LIVE rows only, because only a LIVE label can confirm."""
    out = []
    holds = holds or {t.name: t.hold for t in TENORS}
    for d in cells:
        tk, tn, s, name = d.cell
        f = FEATURE_BY_NAME[name]
        lag = "LIVE" if f.is_analysis else None
        stat = contrast_fn(f)
        x, y, si = cell_xy(ds, d.cell, keep=in_confirmation, lag=lag)
        floors = floors_met(f, x, si)
        if x:
            b = FD.block_bootstrap(x, y, stat, BLOCK, n_boot, seed)
            point, ci = b.point, (b.lo, b.hi)
            h = FD.block_bootstrap(x, y, stat, holds[tn], n_boot, seed)
            hold_ci = (h.lo, h.hi)
        else:
            point, ci, hold_ci = float("nan"), (float("nan"), float("nan")), (float("nan"),) * 2
        o = other_ticker(tk)
        ox, oy, osi = cell_xy(ds, (o, tn, s, name), keep=in_confirmation, lag=lag,
                              feature_ticker=tk if f.qqq_only else None)
        other_ok = floors_met(f, ox, osi)
        other_point = stat(ox, oy) if ox else float("nan")
        wx, wy, _wsi = cell_xy(ds, d.cell, keep=lambda r: in_confirmation(r)
                               and not in_sleeve_window(r["d"]), lag=lag)
        sleeve_point = stat(wx, wy) if wx else float("nan")
        natural = {}
        for side in SIDES[s]:
            nx, ny, _ = cell_xy(ds, d.cell, keep=in_confirmation, lag=lag,
                                value=lambda r, sd=side: r["natural"][sd])
            natural[side] = stat(nx, ny) if nx else float("nan")
        token = confirm_token(d.sign, point, ci[0], ci[1], floors, other_ok,
                              _sign(other_point), _sign(sleeve_point), pbo)
        out.append(Confirmed(d.cell, d, len(x), point, ci, len(ox), other_point, sleeve_point,
                             token, natural, hold_ci))
    return out


def tercile_cuts(x: list[float]) -> tuple[float, float]:
    """The values bounding the bottom and top rank tercile of `x`."""
    lab = FD.rank_groups(x)
    return (max(a for a, g in zip(x, lab) if g == 0), min(a for a, g in zip(x, lab) if g == 2))


def pbo_matrix(ds: Dataset, cells: list[DiscCell], sessions: list[date]) -> np.ndarray:
    """T x 2N: per session, the cell's top-minus-bottom position times y, once
    each way, because the study may read a cell with either sign. Rank cuts come
    from discovery rows. A session outside both arms, or with no row, is 0."""
    pos = {d: i for i, d in enumerate(sessions)}
    gradable = [c for c in cells if c.gradable]
    M = np.zeros((len(sessions), 2 * len(gradable)))
    for j, c in enumerate(gradable):
        f = FEATURE_BY_NAME[c.cell[3]]
        if f.kind == "rank":
            lo, hi = tercile_cuts(cell_xy(ds, c.cell, keep=in_discovery)[0])
        else:
            lo, hi = f.lo, f.hi
        fmap = ds.features[(c.cell[0], c.cell[1])]
        for r in ds.rows[c.cell[:3]]:
            v = (fmap.get(r["date"]) or {}).get(f.name)
            if v is None or r["d"] not in pos:
                continue
            if v >= hi:
                M[pos[r["d"]], 2 * j] = r["y"]
            elif v <= lo:
                M[pos[r["d"]], 2 * j] = -r["y"]
    M[:, 1::2] = -M[:, 0::2]
    return M


def run_pbo(ds: Dataset, cells: list[DiscCell], sessions: list[date], S: int = PBO_S):
    M = pbo_matrix(ds, cells, sessions)
    if M.shape[1] < 2:
        return None
    Mp, _pad = PBO.pad_head(M, S)
    return PBO.cscv(Mp, S=S, metric=PBO.total_metric)


# ── the unconditional read ──────────────────────────────────────────────────

def worst_window(vals: list[float], width: int = BLOCK) -> float:
    if not vals:
        return float("nan")
    if len(vals) <= width:
        return sum(vals)
    return min(sum(vals[i:i + width]) for i in range(len(vals) - width + 1))


def unconditional_token(n: int, blocks: int, lo: float, hi: float, disc: float, conf: float,
                        sleeve: float) -> str:
    """`CANDIDATE` needs the CI above zero and the same sign in both halves and
    with the windows cut. `CONTRARY` needs the CI below zero."""
    if n < MIN_DATES or blocks < MIN_BLOCKS or lo != lo:
        return UNDERPOWERED
    if hi < 0:
        return CONTRARY
    if lo > 0 and disc > 0 and conf > 0 and sleeve > 0:
        return CANDIDATE
    return NULL


def unconditional(rows: list[dict], side: str, n_boot: int = BOOT_N, seed: int = SEED,
                  block: int = BLOCK) -> dict:
    v = [r["net"][side] for r in rows]
    si = [r["si"] for r in rows]
    if not v:
        return dict(n=0, token=UNDERPOWERED, mean=float("nan"), ci=(float("nan"),) * 2,
                    disc=float("nan"), conf=float("nan"), sleeve=float("nan"),
                    worst=float("nan"), worst_window=float("nan"), natural=float("nan"),
                    r=None, n_r=0)
    b = FD.block_bootstrap(v, v, mean_stat, block, n_boot, seed)

    def part(keep) -> float:
        return mean_stat(None, [r["net"][side] for r in rows if keep(r)])

    disc, conf = part(in_discovery), part(in_confirmation)
    sleeve = part(lambda r: not in_sleeve_window(r["d"]))
    rs = [r["r"][side] for r in rows if r["r"].get(side) is not None]
    return dict(n=len(v), mean=b.point, ci=(b.lo, b.hi), disc=disc, conf=conf, sleeve=sleeve,
                worst=min(v), worst_window=worst_window(v),
                natural=mean_stat(None, [r["natural"][side] for r in rows]),
                r=statistics.fmean(rs) if rs else None, n_r=len(rs),
                token=unconditional_token(len(v), n_blocks(si), b.lo, b.hi, disc, conf, sleeve))


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
          f"{'open':>6}   {'contracts found':>15}{'awaited':>9}")
    for (tk, tn), k in book.coverage().items():
        c = k["c"]
        n = c["built"] + c["await"] + c["drop"] + c["open"]
        print(f"  {tk:<7}{tn:<6}{n:>7}{c['built']:>7}{c['await']:>7}{c['drop']:>6}"
              f"{c['open']:>6}   {k['found']:>15}{k['awaited']:>9}")
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


def analysis_three_ways(ds: Dataset) -> None:
    hdr("ANALYSIS FEATURES, THREE WAYS — top minus bottom; only LIVE can confirm")
    print("  RETRO labels were written after the fact and read as descriptive.")
    print(f"  {'cell':<30}{'dates':<7}{'ALL n':>6}{'ALL':>10}{'LIVE n':>7}{'LIVE':>10}"
          f"{'RETRO n':>8}{'RETRO':>10}")
    for cell in all_cells():
        f = FEATURE_BY_NAME[cell[3]]
        if not f.is_analysis:
            continue
        stat = contrast_fn(f)
        for label, keep in (("disc", in_discovery), ("conf", in_confirmation)):
            parts = []
            for lag in (None, "LIVE", "RETRO"):
                x, y, _ = cell_xy(ds, cell, keep=keep, lag=lag)
                parts.append((len(x), stat(x, y) if x else float("nan")))
            print(f"  {cell_name(cell):<30}{label:<7}{parts[0][0]:>6}{pct(parts[0][1]):>10}"
                  f"{parts[1][0]:>7}{pct(parts[1][1]):>10}{parts[2][0]:>8}{pct(parts[2][1]):>10}")


def write_trades(ds: Dataset) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRADES_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ticker", "tenor", "structure", "signal", "exit", "expiry", "atm", "wing",
                    "debit", "y", "net_long_or_back", "net_front"])
        for (tk, tn, s), rows in ds.rows.items():
            for r in rows:
                w.writerow([tk, tn, s, r["date"], r["exit"], r["expiry"], r["atm"], r["wing"],
                            r["debit"], r["y"], r["net"].get("long", r["net"].get("back")),
                            r["net"].get("front", "")])
    print(f"  trades -> {TRADES_CSV.relative_to(ROOT)}")


def forward_read(book: Book, index: dict, baseline: dict, labeler, candidates: list) -> list[str]:
    """Each CANDIDATE's confirmation statistic on dates from 2026-09-23. Rows
    need their own fetch; analysis and baseline cells wait for the seal to lift."""
    lines = []
    if not candidates:
        return ["  FORWARD  no CANDIDATE, so nothing to grade"]
    awaiting = sum(1 for tk in TICKERS for t in TENORS
                   for tr in book.trades(tk, t, FORWARD_START, None) if tr.status == "await")
    if awaiting:
        return [f"  FORWARD  {STILL_OPEN}: {awaiting} forward trades await a fetch"]
    ds = build_dataset(book, index, baseline, labeler, FORWARD_START, None)
    for c in candidates:
        f = FEATURE_BY_NAME[c.cell[3]]
        sealed = (f.is_analysis or f.source == "baseline") and not era_mod.SEAL_LIFTED
        x, y, si = cell_xy(ds, c.cell)
        if sealed or not floors_met(f, x, si):
            lines.append(f"  FORWARD  {cell_name(c.cell)}: {STILL_OPEN} ({len(x)} dates)")
            continue
        b = FD.block_bootstrap(x, y, contrast_fn(f), BLOCK, BOOT_N, SEED)
        tok = (CANDIDATE if excludes_zero(b.lo, b.hi) and _sign(b.point) == c.disc.sign else
               CONTRARY if excludes_zero(b.lo, b.hi) else NULL)
        lines.append(f"  FORWARD  {cell_name(c.cell)}: {tok} {pct(b.point)} "
                     f"[{pct(b.lo)}, {pct(b.hi)}]")
    return lines


def outcomes(book: Book, index: dict, baseline: dict, labeler) -> int:
    """Everything past the gate."""
    ds = build_dataset(book, index, baseline, labeler)
    hdr("DROPS — per series, with the printed reason")
    for key, c in ds.drops.items():
        print(f"  {' '.join(key):<14} rows {len(ds.rows[key]):>4}  "
              + ("  ".join(f"{k}={v}" for k, v in sorted(c.items())) or "none"))

    hdr("1. UNCONDITIONAL — does it pay every day? Net of commission, share of spot")
    print("  Natural fill and R are printed and never graded. Block 21 rows.")
    print(f"  {'series':<14}{'side':<7}{'n':>5}{'mean':>10}{'CI95':>22}{'disc':>10}{'conf':>10}"
          f"{'no-win':>10}{'token':>14}{'natural':>10}{'R':>8}{'worst':>10}{'worst21':>10}")
    uncond = {}
    for key in series_keys():
        for side in SIDES[key[2]]:
            u = unconditional(ds.rows[key], side)
            uncond[key + (side,)] = u
            r = "n/a" if u["r"] is None else f"{u['r']:+.3f}"
            print(f"  {' '.join(key):<14}{side:<7}{u['n']:>5}{pct(u['mean']):>10}"
                  f"{'[' + pct(u['ci'][0]) + ',' + pct(u['ci'][1]) + ']':>22}{pct(u['disc']):>10}"
                  f"{pct(u['conf']):>10}{pct(u['sleeve']):>10}{u['token']:>14}"
                  f"{pct(u['natural']):>10}{r:>8}{pct(u['worst']):>10}"
                  f"{pct(u['worst_window']):>10}")
    print("  A front call ratio has no cap. Its worst figures understate a margin call, "
          "and none is sizing guidance.")

    hdr("2. DISCOVERY — first 60% of dates; Spearman and top minus bottom, BH across cells")
    disc = discover(ds)
    rk = ranked(disc)
    print(f"  cells {len(disc)}  gradable {sum(c.gradable for c in disc)}  "
          f"ranked (q <= {BH_Q}) {len(rk)}")
    print(f"  {'cell':<30}{'n':>5}{'rho':>8}{'top-bot':>10}{'p':>8}{'q':>8}")
    for c in disc:
        if c.gradable:
            print(f"  {cell_name(c.cell):<30}{c.n:>5}{c.rho:>+8.3f}{pct(c.contrast):>10}"
                  f"{c.p:>8.3f}{c.q:>8.3f}")
    print(f"  below the C0 floor on discovery dates: {sum(not c.gradable for c in disc)} cells")

    hdr("OVERFITTING — PBO by CSCV across the gradable cells, each read both ways")
    res = run_pbo(ds, disc, book.signals())
    pbo = None if res is None else res.pbo
    if res is None:
        print("  not computed: fewer than two gradable cells")
    else:
        print(f"  configs {res.n_configs}  rows {res.n_rows}  S {res.S}  PBO {res.pbo:.3f}")

    hdr("3. CONFIRMATION — last 40% of dates; only the ranked list")
    conf = confirm(ds, rk, pbo)
    print(f"  {'cell':<30}{'n':>5}{'top-bot':>10}{'CI95':>22}{'other n':>8}{'other':>10}"
          f"{'no-win':>10}{'token':>14}")
    for c in conf:
        print(f"  {cell_name(c.cell):<30}{c.n:>5}{pct(c.point):>10}"
              f"{'[' + pct(c.ci[0]) + ',' + pct(c.ci[1]) + ']':>22}{c.other_n:>8}"
              f"{pct(c.other_point):>10}{pct(c.sleeve_point):>10}{c.token:>14}")
        print("      natural fill, top minus bottom, net: "
              + "  ".join(f"{k} {pct(v)}" for k, v in c.natural.items())
              + f"   hold-length block CI [{pct(c.hold_ci[0])},{pct(c.hold_ci[1])}]")
    print("  QQQ and SMH share episodes, so the other-ticker clause is weak evidence.")

    analysis_three_ways(ds)

    hdr("VERDICT")
    tally: Counter = Counter()
    conf_by = {c.cell: c.token for c in conf}
    for c in disc:
        tally[conf_by.get(c.cell) or (NULL if c.gradable else UNDERPOWERED)] += 1
    print("  cells: " + "  ".join(f"{k} {tally[k]}" for k in
                                  (CANDIDATE, CONTRARY, NULL, UNDERPOWERED)))
    u_t = Counter(u["token"] for u in uncond.values())
    print("  unconditional: " + "  ".join(f"{k} {u_t[k]}" for k in
                                          (CANDIDATE, CONTRARY, NULL, UNDERPOWERED)))
    cands = [c for c in conf if c.token == CANDIDATE]
    for c in conf:
        print(f">>> daily_vol_structure {cell_name(c.cell)}: {c.token} <<<")
    for key, u in uncond.items():
        print(f">>> daily_vol_structure UNCONDITIONAL {' '.join(key)}: {u['token']} <<<")
    for line in forward_read(book, index, baseline, labeler, cands):
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
