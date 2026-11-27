"""spy_put_write — does a weekly SPY put credit spread pay beyond its SPY beta?

Registration: `research/pre-registrations/f3_structure/spy_put_write.md`
(accepted by the operator 2026-11-27, second read passed). That file is the
spec; this module implements it and adds nothing to its bar. Where the build
needed a ruling the file did not give, the ruling is folded into the
registration beside the clause it amends, tagged `Resolved at build
(2026-11-27)`. RESEARCH TIER: nothing ships from this study.

THE RULE. On the first NYSE session of each ISO week (signal date D), sell one
SPY put credit spread on the standard monthly expiry with DTE of 21 or more
from the planned fill day (the session after D), nearest 37 DTE. The short
strike sits at spot, 3% or 5% below; the long strike 5% or 10% of spot lower.
Strikes snap to the $5 grid from D's spot (`mechanical_benchmark.UniverseSpot`).
Both legs fill at the fill day's closing quote on one clock. Two exits: hold
to expiry (settle at intrinsic on the SPY close), or close at 50% of the
credit (checked from the session after the fill, filled at the next session's
mark) with a 21-DTE time close. Twelve cells; the PRIMARY is at spot, width
10%, hold.

TWO GRADED OBJECTS.
  ARM Z  the primary cell's mean net R per monthly expiry cycle, against zero
  ARM H  the primary cell's monthly Jensen alpha against SPY shares, on the
         `mtm_curve.book_curves` mark-to-market account at $25,000 reference

REUSED, NEVER COPIED
--------------------
Pricing is production's shared functions from `scripts/backtest/simulate.py`:
`entry_day_fill` (closing mid, junk-quote rule), `entry_close_days` and
`common_entry_day` inside `entry_window_end`, `_refuse_credit_priced_to_debit`,
`_entry_outside_bounds` on `helpers._defined_risk_bounds`,
`_monotonicity_violation`, `_cost_knobs`, and the daily mark's barchart branch
(`_snap_asof`, `_is_junk_quote`, `junk_day_mark`, `_close_mid`). Selection reads
`mechanical_benchmark`'s `UniverseSpot`, `listed_by` and `monthly_expiries`,
`mechanical_baseline`'s session calendar, and `narrow_to_fit`'s cache loader
and skip-list. The statistics are `lib/ruin_walk.stationary_indices`,
`lib/pbo.cscv` with `ratio_metric` and `pad_head`, and `lib/confidence_sequence`
with `refuse_floor_forward`'s constants.

CACHED QUOTES ONLY. No code here fetches, and no model price exists: a leg
without a real quote is unpriced. `--dry-run` prints the census (coverage per
cell and per year, the drop census and the selection print) and prices
nothing.

Usage:
  python3 -m scripts.backtest_study run spy_put_write
  python3 -m scripts.backtest_study.f3_structure.spy_put_write --dry-run
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import logging
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest import simulate as SIM  # noqa: E402
from scripts.backtest.helpers import _defined_risk_bounds  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_baseline as MBL  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f3_structure import structure_sweep as SS  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.f4_deployment import refuse_floor_forward as FWD  # noqa: E402
from scripts.backtest_study.lib import confidence_sequence as CS  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as MC  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib import ruin_walk as RW  # noqa: E402

# No export is read, so the era refusals never fire; declared as siblings do.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
# Header provenance the runner reads by ast (docs/architecture.md, study module contract).
HEADER_ERA = "none (option cache and market closes only)"
HEADER_INPUTS = ["backtests/mech_regime/spy_base_rate_daily.csv",
                 "backtests/mech_regime/spy_vix_daily_full.csv", "config/backtest.yml",
                 "backtests/option_history_cache/_unlisted.jsonl"]
HEADER_CACHE = [("SPY", "backtests/option_history_cache/SPY_*.csv")]

REGISTRATION = "research/pre-registrations/f3_structure/spy_put_write.md"
ACCEPTED = "2026-11-27"

# ── registered constants (the registration's numbers; never re-chosen) ──────
TICKER = "SPY"
STRUCTURE = "bull_put_spread"
TARGET_DTE = 37
MIN_DTE = 21
GRID = 5.0
#: How many $5 steps the strike walk may take from its target before giving up.
WALK_REACH = 10
SHORT_MULTS = (1.00, 0.97, 0.95)
WIDTHS = (0.05, 0.10)
HOLD, TARGET = "hold", "target"
EXITS = (HOLD, TARGET)
TARGET_FRAC = 0.50
CLOSE_DTE = 21
BOOT_N = 10_000
SEED = 20261127
Z_BLOCK = 3
Z_ALT_BLOCKS = (2, 4)
WEEK_BLOCK = 8
H_BLOCK = 3
C0A_ALL = 0.75
C0A_YEAR = 0.50
C0B_TRADES = 120
C0B_CYCLES = 24
C0B_MONTHS = 24
PBO_S = 16
PBO_MIN_TRADES = 60
PBO_MIN_CELLS = 6
PBO_MAX = 0.50
FORWARD_START = date(2026, 11, 27)
#: The in-sample window ends on the last signal date BEFORE this day.
WINDOW_BEFORE = date(2026, 11, 27)
FORWARD_MIN_WEEKS = 30
STOP_DOLLARS = 1000.0
#: `account_sim`'s capital, the fixed reference for ARM H's monthly return.
REF_CAPITAL = 25_000.0
STRESS = (("W1", date(2022, 1, 1), date(2022, 12, 31)),
          ("W2", date(2024, 8, 1), date(2024, 8, 31)),
          ("W3", date(2025, 3, 1), date(2025, 4, 30)),
          ("W4", date(2026, 2, 1), date(2026, 4, 30)))

# ── tokens ───────────────────────────────────────────────────────────────────
UNDERPOWERED = "UNDERPOWERED"
POSITIVE, NEGATIVE, NULL = "POSITIVE", "NEGATIVE", "NULL"
ALPHA, NEG_ALPHA, NO_ALPHA = "ALPHA", "NEGATIVE-ALPHA", "NO-ALPHA"
UNCOVERED = "UNCOVERED"
LOSES, PBO_VETO = "LOSES", "PBO-VETO"
PUT_WRITE_ALPHA, BETA_ONLY = "PUT-WRITE-ALPHA", "BETA-ONLY"
NOT_COMPUTABLE = "not computable"

# ── statuses ─────────────────────────────────────────────────────────────────
BUILT = "built"
UNCACHED = "UNCACHED"
NO_SPOT = "no_spot"
NO_MONTHLY = "no_monthly"
NO_LISTED = "no_listed_strike"
COLLISION = "collision"
EXPIRY_CLOSE_MISSING = "expiry_close_missing"
NO_FILL_DAY_QUOTE = "no_fill_day_quote"
CENSUS_ORDER = (BUILT, UNCACHED, NO_SPOT, NO_FILL_DAY_QUOTE, COLLISION,
                EXPIRY_CLOSE_MISSING, NO_MONTHLY, NO_LISTED)

# ── refusals at pricing ──────────────────────────────────────────────────────
DTE_AFTER_MOVE = "dte_below_21_after_move"
ZERO_CREDIT = "zero_credit"

#: Every price tag a real quote can carry here. Anything else is a model price.
ENTRY_TAGS = frozenset({SIM.CLOSE_MID_TAG, SIM.CLOSE_MID_WIDE_TAG, SIM.CLOSE_SIDE_TAG})
MARK_TAGS = frozenset({"close_mid", "carried", "barchart_last", "barchart_stale",
                       "zero_bid_ceiling", "barchart_print"})

CACHE_DIR = ROOT / "backtests" / "option_history_cache"
OUT_DIR = ROOT / "backtests" / "study_output"
TRADES_CSV = OUT_DIR / "spy_put_write-trades.csv"

log = logging.getLogger("spy_put_write")
hdr = MB.hdr


class ModelPrice(RuntimeError):
    """A leg reached a price that is not a real quote (gate 3)."""


# ════════════════════════════════════════════════════════════════════════════
# Cells
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass(frozen=True)
class Cell:
    short: float
    width: float
    exit: str

    @property
    def geom(self) -> tuple[float, float]:
        return (self.short, self.width)

    @property
    def label(self) -> str:
        s = "at spot" if self.short == 1.0 else f"{round((1 - self.short) * 100)}% below"
        return f"{s:<9} w{round(self.width * 100):>2}% {self.exit}"


PRIMARY = Cell(1.00, 0.10, HOLD)
CELLS = (PRIMARY,) + tuple(Cell(s, w, e) for s in SHORT_MULTS for w in WIDTHS
                           for e in EXITS if Cell(s, w, e) != PRIMARY)
GEOMS = tuple(dict.fromkeys(c.geom for c in CELLS))


# ════════════════════════════════════════════════════════════════════════════
# Calendar and window — pure
# ════════════════════════════════════════════════════════════════════════════

def rule_expiry(fill: date) -> date | None:
    """The monthly expiry with DTE >= 21 from `fill`, nearest 37, ties to the
    earlier. The band only bounds the search: a monthly past 74 DTE is never
    nearer 37 than the first one at or past 21, since monthlies are at most
    35 days apart."""
    return MB.monthly_for(fill, TARGET_DTE, (MIN_DTE, 2 * TARGET_DTE + 1))


def signal_weeks(sessions: list[date]) -> list[date]:
    """First session of each ISO week that has a next session, in order."""
    weekly = MBL.weekly_dates(sessions)
    return [d for d in sessions[:-1] if d in weekly]


def in_sample_window(weeks: list[date], nxt: dict[date, date], first_monthly: date,
                     last_quote: date, before: date = WINDOW_BEFORE
                     ) -> tuple[list[date], int, int]:
    """`(window weeks, excluded before, excluded after)`.

    The window starts at the first signal date whose planned expiry is on or
    after the first cached monthly, and ends at the last signal date before
    `before` whose planned expiry is on or before the last cached put quote
    date. Calendar and cache range only: no trade's outcome can move an end.
    """
    planned = {d: rule_expiry(nxt[d]) for d in weeks}
    ok_lo = [d for d in weeks if planned[d] is not None and planned[d] >= first_monthly]
    ok_hi = [d for d in weeks if d < before and planned[d] is not None
             and planned[d] <= last_quote]
    if not ok_lo or not ok_hi:
        return [], 0, 0
    lo, hi = ok_lo[0], ok_hi[-1]
    win = [d for d in weeks if lo <= d <= hi]
    after = sum(1 for d in weeks if d > hi and d < before)
    return win, sum(1 for d in weeks if d < lo), after


# ════════════════════════════════════════════════════════════════════════════
# Selection — reads D's rows and nothing later
# ════════════════════════════════════════════════════════════════════════════

def put_leg(expiry: date, strike: float, qty: int) -> Leg:
    return Leg(qty, TICKER, expiry, float(strike), "Put")


def grid_walk(target: float, step: float = GRID, reach: int = WALK_REACH) -> list[float]:
    """$5 multiples near `target`, nearest first, ties to the lower strike."""
    n0 = math.floor(target / step)
    pts = {round((n0 + i) * step, 4) for i in range(-reach, reach + 2) if n0 + i > 0}
    return sorted(pts, key=lambda k: (abs(k - target), k))


@dataclasses.dataclass(frozen=True)
class Walk:
    status: str            # built | UNCACHED | no_listed_strike
    strike: float | None
    steps: int             # skip-list steps taken
    detail: str = ""


def walk_strike(chain, evidence: set[str], expiry: date, target: float,
                asof: date) -> Walk:
    """The registration's walk. Nearest $5 strike first; a skip-listed one is
    stepped past; a cached one with a row on or before `asof` is chosen; any
    other (not cached, or cached with no row by `asof`) is UNCACHED and the
    walk stops there. Never steps onto a $1 strike."""
    steps = 0
    for k in grid_walk(target):
        if NTF.contract_stem(TICKER, expiry, k, "Put") in evidence:
            steps += 1
            continue
        if chain.cached(TICKER, expiry, k, "Put"):
            if MB.listed_by(chain, put_leg(expiry, k, 1), asof):
                return Walk(BUILT, k, steps)
            return Walk(UNCACHED, k, steps, "cached_no_row_by_D")
        return Walk(UNCACHED, k, steps, "not_cached")
    return Walk(NO_LISTED, None, steps)


@dataclasses.dataclass
class Pick:
    """One cell geometry's trade on one signal week, chosen on D."""
    signal: date
    fill: date                       # planned fill: the session after D
    expiry: date | None
    short: float
    width: float
    status: str
    reason: str = ""
    spot: float | None = None
    k_s: float | None = None
    k_l: float | None = None
    steps: int = 0
    uncached: tuple = ()             # (leg, strike, detail)

    @property
    def priceable(self) -> bool:
        return self.status in (BUILT, NO_FILL_DAY_QUOTE)


def select_strikes(chain, evidence: set[str], spot_u, signal: date, fill: date,
                   short: float, width: float) -> Pick:
    """Expiry, spot and both strikes, read on D only. No fill-day and no
    settlement read: those are `classify`'s."""
    exp = rule_expiry(fill)
    if exp is None:
        return Pick(signal, fill, None, short, width, NO_MONTHLY, NO_MONTHLY)
    spot = spot_u(TICKER, signal, exp)
    if spot is None:
        return Pick(signal, fill, exp, short, width, NO_SPOT, NO_SPOT)
    p = Pick(signal, fill, exp, short, width, BUILT, spot=spot)
    ws = walk_strike(chain, evidence, exp, spot * short, signal)
    p.steps = ws.steps
    if ws.status != BUILT:
        p.status, p.reason = ws.status, f"short_{ws.detail or ws.status}"
        if ws.status == UNCACHED:
            p.uncached = (("short", ws.strike, ws.detail),)
        return p
    p.k_s = ws.strike
    wl = walk_strike(chain, evidence, exp, ws.strike - width * spot, signal)
    p.steps += wl.steps
    if wl.status != BUILT:
        p.status, p.reason = wl.status, f"long_{wl.detail or wl.status}"
        if wl.status == UNCACHED:
            p.uncached = (("long", wl.strike, wl.detail),)
        return p
    p.k_l = wl.strike
    if abs(p.k_l - p.k_s) < 1e-9:
        p.status, p.reason = COLLISION, COLLISION
    return p


def classify(chain, pick: Pick, closes: dict[date, float]) -> Pick:
    """Census-only facts past D: a missing settlement close drops the trade;
    a leg with no row on the planned fill day is flagged (row dates only, no
    price read). Returns `pick`, updated."""
    if pick.status != BUILT:
        return pick
    if pick.expiry not in closes:
        pick.status, pick.reason = EXPIRY_CLOSE_MISSING, EXPIRY_CLOSE_MISSING
        return pick
    for k in (pick.k_s, pick.k_l):
        _series, details = chain.history(put_leg(pick.expiry, k, 1))
        if pick.fill not in details:
            pick.status, pick.reason = NO_FILL_DAY_QUOTE, NO_FILL_DAY_QUOTE
            return pick
    return pick


# ════════════════════════════════════════════════════════════════════════════
# Pricing — production's shared functions, real quotes only
# ════════════════════════════════════════════════════════════════════════════

def leg_mark(series, details, day: date, expiration: date,
             max_carry: int | None = SIM._DEFAULT_MAX_CARRY_DAYS):
    """`(price, tag)` for one leg at `day`'s close, or None.

    Production's daily mark (`simulate._simulate._price_leg`, barchart branch):
    the newest snap on or before `day` (`_snap_asof`); the day's own row is
    judged when it is junk; a junk quote marks by `junk_day_mark`; a carried
    snap is tagged stale past `max_carry` days. Tags here split what that
    branch calls `barchart`: `close_mid` (the day's own two-sided closing
    mid), `carried` (an earlier snap inside `max_carry`), `zero_bid_ceiling`
    (junk with no bid, `junk_day_mark`'s B5 branch) and `barchart_print` (the
    day's own non-junk row with no mid, read as its series mark).
    """
    p, snap = SIM._snap_asof({"k": series}, "k", day, expiration)
    if p is None:
        return None
    row, q_day = details.get(snap), snap
    if snap != day and day <= expiration:
        today = details.get(day)
        if today is not None and SIM._is_junk_quote(today):
            row, q_day = today, day
    if SIM._is_junk_quote(row):
        marked = SIM.junk_day_mark(row, q_day, series, details, expiration)
        if marked is None:
            return None
        p, tag, snap = marked
        if tag == "barchart":
            tag = "zero_bid_ceiling"
        if tag != "barchart_stale" and max_carry is not None and snap is not None \
                and (day - snap).days > max_carry:
            tag = "barchart_stale"
        return p, tag
    if max_carry is not None and snap is not None and (day - snap).days > max_carry:
        return p, "barchart_stale"
    if snap != day:
        return p, "carried"
    return p, ("close_mid" if SIM._close_mid(row) is not None else "barchart_print")


def intrinsic(k_s: float, k_l: float, spot: float) -> float:
    """The put spread's value at expiry, per share."""
    return max(0.0, k_s - spot) - max(0.0, k_l - spot)


@dataclasses.dataclass
class Entry:
    """A filled entry and its daily marks over `[fill, expiry]`."""
    pick: Pick
    fill: date
    credit: float
    width: float
    fill_tags: tuple
    sessions: list                   # [fill .. expiry], close-table sessions
    marks: list                      # clamped spread value per session, None = unmarked
    mark_tags: list                  # per session: (short tag, long tag) or None
    settle: float                    # intrinsic at the expiry close

    @property
    def max_loss(self) -> float:
        return (self.width - self.credit) * 100.0


def price_entry(chain, pick: Pick, sessions: list[date], closes: dict[date, float],
                max_carry: int | None = SIM._DEFAULT_MAX_CARRY_DAYS) -> Entry | str:
    """Fill both legs on one day's closing quotes and mark the path.

    `Entry`, or a refusal code. The fill day is the first day from the planned
    fill, inside production's window from D, on which both legs have a closing
    quote `entry_day_fill` can judge (`common_entry_day`).
    """
    if not pick.priceable:
        raise ValueError(f"cannot price a {pick.status} pick")
    short = put_leg(pick.expiry, pick.k_s, -1)
    long_ = put_leg(pick.expiry, pick.k_l, +1)
    legs = [short, long_]
    hist = [chain.history(lg) for lg in legs]
    days = [SIM.entry_close_days(h[1], lg.qty) for h, lg in zip(hist, legs)]
    day = SIM.common_entry_day(days, pick.fill, SIM.entry_window_end(pick.signal))
    if day is None:
        return SIM.NO_COMMON_ENTRY_DAY
    if (pick.expiry - day).days < MIN_DTE:
        return DTE_AFTER_MOVE
    fills = [SIM.entry_day_fill(h[1].get(day), lg.qty) for h, lg in zip(hist, legs)]
    if any(f is None for f in fills):
        return SIM.NO_REAL_ENTRY_PRICE
    if any(f[0] is None for f in fills):
        return SIM.JUNK_ENTRY_REFUSAL
    prices, tags = [f[0] for f in fills], [f[1] for f in fills]
    bad = [t for t in tags if t not in ENTRY_TAGS]
    if bad:
        raise ModelPrice(f"entry tag(s) {bad} on {pick.signal} {pick.k_s}/{pick.k_l}")
    entry_net = sum(lg.qty * p for lg, p in zip(legs, prices))   # negative = credit
    width = pick.k_s - pick.k_l
    if SIM._refuse_credit_priced_to_debit(STRUCTURE, entry_net):
        return SIM.CREDIT_DEBIT_REFUSAL
    credit = -entry_net
    if credit <= 1e-9:
        return ZERO_CREDIT
    if SIM._entry_outside_bounds(_defined_risk_bounds(legs), entry_net) \
            or credit >= width - 1e-9:
        return SIM.OUTSIDE_BOUNDS_REFUSAL
    if SIM._monotonicity_violation(legs, prices, tags):
        return SIM.NON_MONOTONIC_REFUSAL
    path = [s for s in sessions if day <= s <= pick.expiry]
    marks, mtags = [], []
    for s in path:
        ms = leg_mark(hist[0][0], hist[0][1], s, pick.expiry, max_carry)
        ml = leg_mark(hist[1][0], hist[1][1], s, pick.expiry, max_carry)
        if ms is None or ml is None:
            marks.append(None)
            mtags.append(None)
            continue
        for _p, t in (ms, ml):
            if t not in MARK_TAGS:
                raise ModelPrice(f"mark tag {t} on {s}")
        marks.append(min(max(ms[0] - ml[0], 0.0), width))
        mtags.append((ms[1], ml[1]))
    settle = intrinsic(pick.k_s, pick.k_l, closes[pick.expiry])
    return Entry(pick, day, credit, width, tuple(tags), path, marks, mtags, settle)


# ── exits ────────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class Outcome:
    """One cell's trade: entry, exit and the marked path to the exit."""
    cell: Cell
    entry: Entry
    exit_day: date
    exit_value: float               # spread value paid to close, per share
    exit_reason: str
    path_days: list                 # sessions [fill .. exit]
    path_pnl: list                  # gross cumulative $ per session (None carried)
    commission: float

    @property
    def gross(self) -> float:
        return (self.entry.credit - self.exit_value) * 100.0

    @property
    def net(self) -> float:
        return self.gross - self.commission

    @property
    def R(self) -> float:
        return self.net / self.entry.max_loss

    @property
    def R_gross(self) -> float:
        return self.gross / self.entry.max_loss

    @property
    def signal(self) -> date:
        return self.entry.pick.signal

    @property
    def expiry(self) -> date:
        return self.entry.pick.expiry

    def filled_pnl(self) -> list[float]:
        """`path_pnl` with unmarked days carried (0.0 before any mark)."""
        out, last = [], 0.0
        for v in self.path_pnl:
            if v is not None:
                last = v
            out.append(last)
        return out

    @property
    def mfe(self) -> float:
        return max(self.filled_pnl()) / self.entry.max_loss

    @property
    def mae(self) -> float:
        return min(self.filled_pnl()) / self.entry.max_loss


def _pnl(credit: float, value: float | None) -> float | None:
    return None if value is None else (credit - value) * 100.0


def _next_marked(e: Entry, i: int) -> int | None:
    """First index at or after `i` with a mark, or None."""
    for j in range(i, len(e.sessions)):
        if e.marks[j] is not None:
            return j
    return None


def exit_hold(e: Entry, cell: Cell, commission: float) -> Outcome:
    """Held to expiry and settled at intrinsic on the expiry close. The last
    path value is the settlement."""
    pnl = [_pnl(e.credit, m) for m in e.marks[:-1]] + [_pnl(e.credit, e.settle)]
    return Outcome(cell, e, e.pick.expiry, e.settle, "expiry", list(e.sessions), pnl,
                   commission)


def exit_target(e: Entry, cell: Cell, commission: float) -> Outcome:
    """50% of the credit, checked on each close from the session after the
    fill and filled at the next session's mark; else the 21-DTE close at the
    first session after the fill with DTE <= 21. An unmarked fill session
    moves the close to the next session with a mark; none before expiry
    settles at intrinsic."""
    exp = e.pick.expiry
    c21 = next((i for i, s in enumerate(e.sessions) if i > 0 and (exp - s).days <= CLOSE_DTE),
               len(e.sessions) - 1)
    fire_at, reason = c21, "dte21"
    for i in range(1, c21):
        m = e.marks[i]
        if m is not None and m <= TARGET_FRAC * e.credit + 1e-12:
            fire_at, reason = i + 1, "target"
            break
    j = _next_marked(e, fire_at)
    if j is None or e.sessions[j] >= exp:
        j, value, reason = len(e.sessions) - 1, e.settle, reason + "_settled"
    else:
        value = e.marks[j]
    pnl = [_pnl(e.credit, m) for m in e.marks[:j]] + [_pnl(e.credit, value)]
    return Outcome(cell, e, e.sessions[j], value, reason, e.sessions[:j + 1], pnl,
                   commission)


def exit_of(e: Entry, cell: Cell, commission: float) -> Outcome:
    return exit_hold(e, cell, commission) if cell.exit == HOLD \
        else exit_target(e, cell, commission)


def stop_R(o: Outcome, stop: float = STOP_DOLLARS) -> float:
    """R with a $1,000 stop: a close at or below -$1,000 on session t closes
    at session t+1's path value (descriptive, no verdict)."""
    pnl = o.filled_pnl()
    for i, v in enumerate(pnl):
        if v <= -stop:
            k = min(i + 1, len(pnl) - 1)
            return (pnl[k] - o.commission) / o.entry.max_loss
    return o.R


# ════════════════════════════════════════════════════════════════════════════
# Grading — pure functions on outcomes (tested on synthetic rows)
# ════════════════════════════════════════════════════════════════════════════

def _sign(v: float) -> int:
    return (v > 0) - (v < 0)


def excludes_zero(ci) -> bool:
    return ci[0] > 0 or ci[1] < 0


def cycle_means(outs: list[Outcome], cycles: list[date]) -> list[float | None]:
    """Mean net R per expiry in `cycles` order; None for an empty cycle."""
    by: dict[date, list[float]] = defaultdict(list)
    for o in outs:
        by[o.expiry].append(o.R)
    return [statistics.fmean(by[c]) if by.get(c) else None for c in cycles]


def mean_of_means(means: list[float | None]) -> float | None:
    vals = [m for m in means if m is not None]
    return statistics.fmean(vals) if vals else None


def stationary_ci(values: list[float | None], block: float, n: int = BOOT_N,
                  seed: int = SEED) -> tuple[float, float]:
    """CI95 by percentile of the mean of the non-empty slots, over a
    stationary block bootstrap of the ordered slots. A draw holding only
    empty slots is skipped."""
    vals = np.array([np.nan if v is None else float(v) for v in values])
    idx = RW.stationary_indices(len(vals), len(vals), block, n, np.random.default_rng(seed))
    sub = vals[idx]
    ok = ~np.all(np.isnan(sub), axis=1)
    with np.errstate(invalid="ignore"):
        draws = np.nanmean(sub[ok], axis=1)
    if draws.size == 0:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(lo), float(hi)


def hold_overlaps(o: Outcome, lo: date, hi: date) -> bool:
    return o.entry.fill <= hi and o.exit_day >= lo


def grade_z(outs: list[Outcome], cycles: list[date], n: int = BOOT_N,
            seed: int = SEED) -> dict:
    """ARM Z on the cycle unit: C0b (120 trades, 24 non-empty cycles), C1-C3."""
    means = cycle_means(outs, cycles)
    n_cyc = sum(1 for m in means if m is not None)
    g = dict(n=len(outs), cycles=n_cyc, slots=len(cycles),
             c0=len(outs) >= C0B_TRADES and n_cyc >= C0B_CYCLES)
    g["mean"] = mean_of_means(means)
    if not g["c0"] or g["mean"] is None:
        g["token"] = UNDERPOWERED
        return g
    g["ci"] = stationary_ci(means, Z_BLOCK, n, seed)
    g["alt"] = {b: stationary_ci(means, b, n, seed) for b in Z_ALT_BLOCKS}
    g["c1"] = excludes_zero(g["ci"])
    years = sorted({c.year for c in cycles})
    g["loyo"] = {}
    for y in years:
        m = mean_of_means([v for c, v in zip(cycles, means) if c.year != y])
        g["loyo"][y] = m
    g["c2"] = all(m is not None and _sign(m) == _sign(g["mean"]) for m in g["loyo"].values())
    g["stress"] = {}
    for name, lo, hi in STRESS:
        hit = {o.expiry for o in outs if hold_overlaps(o, lo, hi)}
        g["stress"][name] = mean_of_means([v for c, v in zip(cycles, means) if c not in hit])
    g["c3"] = all(m is not None and _sign(m) == _sign(g["mean"])
                  for m in g["stress"].values())
    g["token"] = z_token(g)
    return g


def z_token(g: dict) -> str:
    if not g.get("c0"):
        return UNDERPOWERED
    if g["c1"] and g["c2"] and g["c3"] and g["mean"] > 0:
        return POSITIVE
    if g["c1"] and g["mean"] < 0:
        return NEGATIVE
    return NULL


def first_failed(g: dict) -> str:
    for c in ("c1", "c2", "c3"):
        if not g.get(c):
            return c.upper()
    return "C1 (sign)"


def week_series(outs: list[Outcome], weeks: list[date]) -> list[float | None]:
    by = {o.signal: o.R for o in outs}
    return [by.get(w) for w in weeks]


def ols(xs, ys) -> tuple[float, float]:
    """`(intercept, slope)` of y on x."""
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    return my - slope * mx, slope


def alpha_draws(months: list[tuple], block: float = H_BLOCK, n: int = BOOT_N,
                seed: int = SEED) -> tuple[np.ndarray, np.ndarray]:
    """Stationary-bootstrap draws of `(alpha, beta)` over the ordered months."""
    T = len(months)
    x = np.array([m[2] for m in months])
    y = np.array([m[1] for m in months])
    idx = RW.stationary_indices(T, T, block, n, np.random.default_rng(seed))
    xs, ys = x[idx], y[idx]
    mx, my = xs.mean(axis=1, keepdims=True), ys.mean(axis=1, keepdims=True)
    sxx = ((xs - mx) ** 2).sum(axis=1)
    ok = sxx > 1e-18
    beta = ((xs - mx) * (ys - my)).sum(axis=1)[ok] / sxx[ok]
    alpha = my[ok, 0] - beta * mx[ok, 0]
    return alpha, beta


def grade_h(months: list[tuple], n: int = BOOT_N, seed: int = SEED) -> dict:
    """ARM H on `[("YYYY-MM", account return, SPY return)]`: C0b (24 months),
    alpha and beta with CI95, C2 leave-one-year-out, C3 stress months out."""
    g = dict(n=len(months), c0=len(months) >= C0B_MONTHS)
    if not g["c0"]:
        g["token"] = UNDERPOWERED
        return g
    xs = [m[2] for m in months]
    ys = [m[1] for m in months]
    g["alpha"], g["beta"] = ols(xs, ys)
    a, b = alpha_draws(months, H_BLOCK, n, seed)
    g["ci"] = tuple(float(v) for v in np.percentile(a, [2.5, 97.5]))
    g["beta_ci"] = tuple(float(v) for v in np.percentile(b, [2.5, 97.5]))
    g["c1"] = excludes_zero(g["ci"])

    def refit(keep):
        rest = [m for m in months if keep(m)]
        if len(rest) < 3:
            return None
        return ols([m[2] for m in rest], [m[1] for m in rest])[0]

    g["loyo"] = {y: refit(lambda m, y=y: not m[0].startswith(f"{y:04d}-"))
                 for y in sorted({int(m[0][:4]) for m in months})}
    g["c2"] = all(v is not None and _sign(v) == _sign(g["alpha"]) for v in g["loyo"].values())
    g["stress"] = {}
    for name, lo, hi in STRESS:
        out = {f"{y:04d}-{mo:02d}" for y, mo in month_range(lo, hi)}
        g["stress"][name] = refit(lambda m, out=out: m[0] not in out)
    g["c3"] = all(v is not None and _sign(v) == _sign(g["alpha"])
                  for v in g["stress"].values())
    g["acct_total"] = sum(ys)
    g["spy_line_total"] = sum(g["beta"] * x for x in xs)
    g["token"] = h_token(g)
    return g


def h_token(g: dict) -> str:
    if not g.get("c0"):
        return UNDERPOWERED
    if g["c1"] and g["c2"] and g["c3"] and g["alpha"] > 0:
        return ALPHA
    if g["c1"] and g["alpha"] < 0:
        return NEG_ALPHA
    return NO_ALPHA


def month_range(lo: date, hi: date) -> list[tuple[int, int]]:
    out, (y, m) = [], (lo.year, lo.month)
    while (y, m) <= (hi.year, hi.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def month_end(y: int, m: int) -> date:
    return (date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)) - timedelta(days=1)


@dataclasses.dataclass
class Pos:
    """A position as `mtm_curve.book_curves` reads one: marks attached."""
    rec: dict
    mtm_sessions: list
    mtm_dollars: list
    dollars: float
    contracts: int = 1

    @property
    def days_held(self) -> int:
        return len(self.mtm_sessions)


def positions(outs: list[Outcome]) -> list[Pos]:
    """One lot per trade, gross marks from the fill day to the exit."""
    return [Pos(rec=dict(date=o.signal.isoformat(), ticker=TICKER, structure=STRUCTURE),
                mtm_sessions=list(o.path_days), mtm_dollars=o.filled_pnl(),
                dollars=o.gross) for o in outs]


def monthly_series(outs: list[Outcome], closes: dict[date, float],
                   capital: float = REF_CAPITAL) -> tuple[list[tuple], object]:
    """`([("YYYY-MM", account return, SPY return)], BookCurves)`.

    The account's level at each month's last session on `book_curves`
    (TARGET_POSITION: the marks are the positions' own), net of each
    position's commission at its exit, over a fixed reference capital. Months
    run from the first full month after the first fill to the last calendar
    month ending on or before the last exit."""
    if not outs:
        return [], None
    bc = MC.book_curves(positions(outs), target=MC.TARGET_POSITION)
    curve = bc.mtm
    comm = sorted((o.exit_day, o.commission) for o in outs)
    first = min(o.entry.fill for o in outs)
    last = max(o.exit_day for o in outs)
    y, m = (first.year + 1, 1) if first.month == 12 else (first.year, first.month + 1)
    months = [ym for ym in month_range(date(y, m, 1), last) if month_end(*ym) <= last]
    days = sorted(closes)

    def last_session(d: date) -> date | None:
        got = [s for s in days if s <= d]
        return got[-1] if got else None

    def equity(d: date) -> float:
        lv = 0.0
        for s, v in zip(curve.sessions, curve.levels):
            if s <= d:
                lv = v
            else:
                break
        return lv - sum(c for s, c in comm if s <= d)

    out = []
    if not months:
        return out, bc
    py, pm = (months[0][0] - 1, 12) if months[0][1] == 1 else (months[0][0], months[0][1] - 1)
    prev = last_session(month_end(py, pm))
    for ym in months:
        cur = last_session(month_end(*ym))
        if prev is None or cur is None:
            break
        out.append((f"{ym[0]:04d}-{ym[1]:02d}", (equity(cur) - equity(prev)) / capital,
                    closes[cur] / closes[prev] - 1.0))
        prev = cur
    return out, bc


def pbo_matrix(outs_by_cell: dict, weeks: list[date]) -> np.ndarray:
    """`T weeks x N cells x 2`: (net R, 1) on a week with a priced trade,
    (0, 0) on one without. The same rows, in order, for every cell."""
    idx = {w: i for i, w in enumerate(weeks)}
    M = np.zeros((len(weeks), len(outs_by_cell), 2))
    for j, c in enumerate(outs_by_cell):
        for o in outs_by_cell[c]:
            i = idx.get(o.signal)
            if i is not None:
                M[i, j, 0] = o.R
                M[i, j, 1] = 1.0
    return M


def pbo_read(outs_by_cell: dict, weeks: list[date], primary: Cell = PRIMARY):
    """`(PBOResult | None, eligible cells, note)`. Only cells with at least
    60 priced trades enter; it needs at least six, the primary among them."""
    elig = {c: v for c, v in outs_by_cell.items() if len(v) >= PBO_MIN_TRADES}
    if primary not in elig or len(elig) < PBO_MIN_CELLS:
        why = ("primary below 60 trades" if primary not in elig
               else f"{len(elig)} cells reach 60 trades (needs {PBO_MIN_CELLS})")
        return None, list(elig), why
    order = [primary] + [c for c in elig if c != primary]
    M = pbo_matrix({c: elig[c] for c in order}, weeks)
    Mp, _pad = PBO.pad_head(M, PBO_S)
    return PBO.cscv(Mp, S=PBO_S, metric=PBO.ratio_metric), order, ""


def study_token(c0a: bool, z: dict | None, h: dict | None, pbo: float | None
                ) -> tuple[str, str]:
    """The study-level verdict, first matching row of the registration's
    table. `(token, beside)`: `beside` carries what the table says to print
    beside it."""
    if not c0a:
        return UNCOVERED, ""
    if z is None or h is None or not z.get("c0") or not h.get("c0"):
        return UNDERPOWERED, ""
    zt, ht = z["token"], h["token"]
    if zt == NEGATIVE:
        return LOSES, f"ARM H {ht}"
    if zt == POSITIVE and (pbo is None or pbo > PBO_MAX):
        return PBO_VETO, f"ARM H {ht}"
    if zt == POSITIVE and ht == ALPHA:
        return PUT_WRITE_ALPHA, ""
    if zt == POSITIVE:
        return BETA_ONLY, f"ARM H {ht}"
    return NULL, f"first failed criterion {first_failed(z)} (ARM Z); ARM H {ht}"


def forward_token(cycle_vals: list[float], closed_weeks: int, weeks_at: list[int]
                  ) -> tuple[str, object]:
    """The forward read: a confidence sequence on forward cycle means,
    `refuse_floor_forward`'s constants, entering at the cycle where the
    30-closed-week floor was reached (`weeks_at[i]`: closed weeks through
    cycle i)."""
    if closed_weeks < FORWARD_MIN_WEEKS or not cycle_vals:
        return "STILL-OPEN", None
    start = next(i + 1 for i, w in enumerate(weeks_at) if w >= FORWARD_MIN_WEEKS)
    step = CS.sequence(cycle_vals, FWD.ALPHA, FWD.T_STAR, start=start)[-1]
    if step.run_lo is not None and step.run_lo > 0:
        return "FORWARD-HOLDS", step
    if step.run_hi is not None and step.run_hi < 0:
        return "FORWARD-FAILS", step
    return "STILL-OPEN", step


def coverage_gate(by_year: dict[int, Counter]) -> tuple[bool, float, dict[int, float]]:
    """C0a: built weeks >= 75% of all signal weeks and >= 50% in every year."""
    tot = sum(c["n"] for c in by_year.values())
    built = sum(c[BUILT] for c in by_year.values())
    share = built / tot if tot else 0.0
    years = {y: (c[BUILT] / c["n"] if c["n"] else 0.0) for y, c in by_year.items()}
    ok = tot > 0 and share >= C0A_ALL and all(v >= C0A_YEAR for v in years.values())
    return ok, share, years


# ════════════════════════════════════════════════════════════════════════════
# The study object — selection memoised, pricing on demand
# ════════════════════════════════════════════════════════════════════════════

class Study:
    def __init__(self, chain=None, evidence=None, closes=None, sim_cfg=None):
        self.chain = chain if chain is not None else NTF.Chain()
        self.evidence = evidence if evidence is not None else NTF.unlisted_evidence()
        self.closes = closes if closes is not None else MBL.load_closes()
        self.sim_cfg = sim_cfg if sim_cfg is not None else SS.load_sim_cfg()
        self.sessions = sorted(d for d in self.closes if d >= date(2022, 1, 1))
        self.nxt = MBL.next_session(self.sessions)
        self.spot_u = MB.UniverseSpot(self.chain)
        self._pick: dict[tuple, Pick] = {}
        self._entry: dict[tuple, Entry | str] = {}
        self.max_carry = self.sim_cfg.get("max_price_carry_days", SIM._DEFAULT_MAX_CARRY_DAYS)

    def pick(self, d: date, geom: tuple[float, float]) -> Pick:
        key = (d, geom)
        if key not in self._pick:
            p = select_strikes(self.chain, self.evidence, self.spot_u, d, self.nxt[d], *geom)
            self._pick[key] = classify(self.chain, p, self.closes)
        return self._pick[key]

    def entry(self, d: date, geom) -> Entry | str | None:
        p = self.pick(d, geom)
        if not p.priceable:
            return None
        key = (d, geom)
        if key not in self._entry:
            self._entry[key] = price_entry(self.chain, p, self.sessions, self.closes,
                                           self.max_carry)
        return self._entry[key]

    # cache facts ------------------------------------------------------------
    def put_expiries(self) -> list[date]:
        return sorted(e for (tk, e), ks in self.chain.idx.items()
                      if tk == TICKER and any("P" in cps for cps in ks.values()))

    def first_cached_monthly(self) -> date | None:
        exps = set(self.put_expiries())
        if not exps:
            return None
        mons = MB.monthly_expiries(min(exps), max(exps))
        got = [e for e in mons if e in exps]
        return got[0] if got else None

    def last_put_quote(self, cache_dir: Path = CACHE_DIR) -> date | None:
        """The newest row date in any cached SPY put file (row dates only)."""
        best = None
        for p in cache_dir.glob(f"{TICKER}_*P.csv"):
            with open(p, encoding="utf-8", errors="replace") as fh:
                next(fh, None)
                for line in fh:
                    try:
                        d = date.fromisoformat(line[:10])
                    except ValueError:
                        continue
                    if best is None or d > best:
                        best = d
        return best


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
# ════════════════════════════════════════════════════════════════════════════

def _f(v, fmt="+.3f") -> str:
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else format(v, fmt)


def _ci(ci, fmt="+.3f") -> str:
    return f"[{_f(ci[0], fmt)}, {_f(ci[1], fmt)}]" if ci else "[n/a]"


def yn(v) -> str:
    return "Y" if v else "n"


def census(st: Study, weeks: list[date], geom) -> tuple[dict[int, Counter], Counter]:
    """Per signal year: `n` and each status, plus skip-list steps. Row dates
    and filenames only; no price is read."""
    by_year: dict[int, Counter] = defaultdict(Counter)
    detail: Counter = Counter()
    for d in weeks:
        p = st.pick(d, geom)
        c = by_year[d.year]
        c["n"] += 1
        c[p.status] += 1
        c["steps"] += p.steps
        if p.status == UNCACHED:
            detail[p.reason] += 1
    return dict(by_year), detail


def print_census_cell(label: str, by_year: dict[int, Counter], detail: Counter,
                      per_year: bool) -> None:
    tot = Counter()
    for c in by_year.values():
        tot.update(c)
    share = tot[BUILT] / tot["n"] if tot["n"] else 0.0
    print(f"  {label:<20} weeks {tot['n']:>4}  built {tot[BUILT]:>4} ({share:5.1%})  "
          f"UNCACHED {tot[UNCACHED]:>4}  skip-steps {tot['steps']:>3}  no_spot "
          f"{tot[NO_SPOT]:>3}  no_fill_day_quote {tot[NO_FILL_DAY_QUOTE]:>3}  collision "
          f"{tot[COLLISION]:>2}  expiry_close_missing {tot[EXPIRY_CLOSE_MISSING]:>2}"
          + (f"  other {tot[NO_MONTHLY] + tot[NO_LISTED]}" if tot[NO_MONTHLY] + tot[NO_LISTED]
             else ""))
    if per_year:
        for y in sorted(by_year):
            c = by_year[y]
            print(f"      {y}  weeks {c['n']:>3}  built {c[BUILT]:>3} "
                  f"({(c[BUILT] / c['n'] if c['n'] else 0):5.1%})  UNCACHED {c[UNCACHED]:>3}  "
                  f"skip-steps {c['steps']:>3}  no_spot {c[NO_SPOT]:>2}  no_fill_day_quote "
                  f"{c[NO_FILL_DAY_QUOTE]:>2}  collision {c[COLLISION]:>2}  "
                  f"expiry_close_missing {c[EXPIRY_CLOSE_MISSING]:>2}")
        if detail:
            print("      UNCACHED by leg and cause: "
                  + "  ".join(f"{k}={v}" for k, v in sorted(detail.items())))


def selection_print(st: Study, weeks: list[date]) -> None:
    """Primary cell: per year, built against not built, SPY's return from the
    planned fill day to expiry and the spread's intrinsic at expiry on the
    target strikes (from the close-table close on D), in dollars per lot."""
    rows = defaultdict(lambda: {True: [], False: []})
    for d in weeks:
        p = st.pick(d, PRIMARY.geom)
        exp, fill = p.expiry, p.fill
        c0, c1, sd = st.closes.get(fill), st.closes.get(exp) if exp else None, st.closes.get(d)
        if exp is None or c0 is None or c1 is None or sd is None:
            continue
        ks = round(round(sd * PRIMARY.short / GRID) * GRID, 4)
        kl = round(round((ks - PRIMARY.width * sd) / GRID) * GRID, 4)
        rows[d.year][p.status == BUILT].append((c1 / c0 - 1.0, intrinsic(ks, kl, c1) * 100.0))
    print("  Per year, built vs not built (n · mean SPY return fill->expiry · mean spread "
          "intrinsic $ · share intrinsic > 0). No verdict.")
    for y in sorted(rows):
        parts = []
        for built in (True, False):
            v = rows[y][built]
            if v:
                parts.append(f"{'built' if built else 'not built'} n {len(v):>3} SPY "
                             f"{statistics.fmean(a for a, _ in v):+.4f} intrinsic "
                             f"${statistics.fmean(b for _, b in v):>7.0f} hit "
                             f"{sum(1 for _, b in v if b > 0) / len(v):4.0%}")
            else:
                parts.append(f"{'built' if built else 'not built'} n   0")
        print(f"    {y}  " + "   ·   ".join(parts))


def write_trades(outs_by_cell: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRADES_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cell", "signal", "fill", "expiry", "k_short", "k_long", "credit",
                    "width", "max_loss", "exit_day", "exit_reason", "exit_value", "gross",
                    "commission", "net", "R", "mfe_R", "mae_R"])
        for c, outs in outs_by_cell.items():
            for o in outs:
                e = o.entry
                w.writerow([c.label.strip(), o.signal, e.fill, o.expiry, e.pick.k_s, e.pick.k_l,
                            f"{e.credit:.4f}", f"{e.width:.2f}", f"{e.max_loss:.2f}",
                            o.exit_day, o.exit_reason, f"{o.exit_value:.4f}", f"{o.gross:.2f}",
                            f"{o.commission:.2f}", f"{o.net:.2f}", f"{o.R:.5f}",
                            f"{o.mfe:.5f}", f"{o.mae:.5f}"])


def blind_check(st: Study, weeks: list[date]) -> list[str]:
    """G-BLIND: every primary strike choice re-made on a cache cut at D must
    agree (spot, expiry and strikes read on D or earlier)."""
    bad = []
    for d in weeks:
        p = st.pick(d, PRIMARY.geom)
        cut = MB.AsOfChain(st.chain, d)
        again = select_strikes(cut, st.evidence, MB.UniverseSpot(cut), d, st.nxt[d],
                               *PRIMARY.geom)
        sel_status = BUILT if p.status in (EXPIRY_CLOSE_MISSING, NO_FILL_DAY_QUOTE) \
            else p.status
        if again.status != sel_status or (again.k_s, again.k_l) != (p.k_s, p.k_l):
            bad.append(f"{d}: full {p.status} {p.k_s}/{p.k_l} vs cut {again.status} "
                       f"{again.k_s}/{again.k_l}")
    return bad


# ════════════════════════════════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="census only: coverage per cell and per year; nothing priced")
    args = ap.parse_args(argv)
    logging.getLogger("backtest").setLevel(logging.ERROR)
    logging.getLogger("scripts.backtest").setLevel(logging.ERROR)

    hdr("spy_put_write — does a weekly SPY put credit spread pay beyond its SPY beta?")
    st = Study()
    SIM.validate_pricing_config(st.sim_cfg)
    comm, slip = SIM._cost_knobs(st.sim_cfg)
    commission = SS.commission_dollars([put_leg(date(2026, 1, 16), 1, -1),
                                        put_leg(date(2026, 1, 16), 1, 1)], 1, st.sim_cfg)
    first_monthly = st.first_cached_monthly()
    last_quote = st.last_put_quote()
    weeks_all = signal_weeks(st.sessions)
    weeks, n_before, n_after = in_sample_window(weeks_all, st.nxt, first_monthly, last_quote)
    print(f"""  Registration {REGISTRATION}
  (accepted by the operator {ACCEPTED}). NOTHING SHIPS FROM THIS STUDY.
  PRIMARY: SPY put credit spread, short at spot, width 10% of spot, monthly with DTE >= 21
  nearest 37, held to expiry, 1 lot. Twelve cells (3 short strikes x 2 widths x 2 exits).
  era      none (option cache only)
  quotes   backtests/option_history_cache/ (cached only; no fetch; no model price)
  closes   {MBL.SESSION_TABLES[0].relative_to(ROOT)}, extended by
           {MBL.SESSION_TABLES[1].relative_to(ROOT)} (unadjusted SPY closes)
  costs    commission ${comm:.2f}/contract/leg/side, slippage {slip:g}
           (config/backtest.yml) = ${commission:.2f} per one-lot round trip
  calendar {st.sessions[0]} -> {st.sessions[-1]}  ({len(st.sessions)} sessions)
  cache    first cached SPY monthly {first_monthly}  ·  last cached SPY put quote {last_quote}""")
    if not weeks:
        hdr(f"VERDICT: {UNCOVERED}")
        print("  No signal week falls inside the cache's range. Nothing priced.")
        return 0
    print(f"  WINDOW   signal weeks {weeks[0]} -> {weeks[-1]}  ({len(weeks)} weeks); "
          f"excluded: {n_before} before (planned expiry before the first cached monthly), "
          f"{n_after} after (planned expiry past the last cached quote)")

    # spot check: the close table against the option-implied spot on D
    diffs = []
    for d in weeks:
        p = st.pick(d, PRIMARY.geom)
        if p.spot and d in st.closes:
            diffs.append(abs(st.closes[d] / p.spot - 1.0))
    if diffs:
        print(f"  close table vs UniverseSpot on D: median |diff| {statistics.median(diffs):.4%}, "
              f"max {max(diffs):.4%} over {len(diffs)} weeks (an adjusted table would drift)")

    # ── CENSUS ───────────────────────────────────────────────────────────────
    hdr("CENSUS — coverage per cell and per year (row dates and filenames only; no price read)")
    cens = {}
    for geom in GEOMS:
        cens[geom] = census(st, weeks, geom)
    for geom in GEOMS:
        lab = Cell(geom[0], geom[1], "both exits").label
        print_census_cell(lab, *cens[geom], per_year=True)
        if geom == PRIMARY.geom:
            print("  (the exit does not change selection, so each geometry is one census row)")
    by_year_p, _ = cens[PRIMARY.geom]
    ok_a, share_a, years_a = coverage_gate(by_year_p)
    print(f"\n  C0a COVERAGE (primary): built {share_a:.1%} of {sum(c['n'] for c in by_year_p.values())} "
          f"weeks (floor {C0A_ALL:.0%}); per year "
          + "  ".join(f"{y} {v:.0%}" for y, v in sorted(years_a.items()))
          + f" (floor {C0A_YEAR:.0%})  ->  {'PASS' if ok_a else 'FAIL'}")
    print("  `built` excludes weeks with no planned-fill-day row on a leg; such weeks are still")
    print("  priced if a common day arrives inside the five-session window.")

    hdr("SELECTION PRINT — primary cell, built vs not built (no verdict)")
    selection_print(st, weeks)

    bad = blind_check(st, weeks)
    print(f"\n  G-BLIND (primary strikes re-chosen on a cache cut at D): "
          f"{'PASS' if not bad else 'FAIL'}  {len(bad)} choices differ")
    for b in bad[:10]:
        print(f"     {b}")

    if args.dry_run:
        hdr("DRY RUN — census only")
        print("  Nothing was priced: no fill, no mark, no R, no P&L.")
        return 0
    if not ok_a:
        hdr(f"VERDICT: {UNCOVERED}")
        print(f"  >>> spy_put_write PRIMARY ({PRIMARY.label.strip()}): {UNCOVERED} <<<")
        print("  C0a fails: too few weeks are cached. Census printed, nothing priced.")
        print("  Nothing ships.")
        return 0
    if bad:
        hdr("GATE FAILURE — G-BLIND: a choice read data after its signal date")
        print("  No outcome printed. Exit 1.")
        return 1
    return outcomes(st, weeks, cens, commission)


def outcomes(st: Study, weeks: list[date], cens: dict, commission: float) -> int:
    """Everything past C0a: pricing, the two graded objects, PBO, verdict."""
    cycles = sorted({rule_expiry(st.nxt[d]) for d in weeks})
    outs_by_cell: dict[Cell, list[Outcome]] = {}
    refusals: dict[tuple, Counter] = {}
    for geom in GEOMS:
        ref = Counter()
        entries = []
        for d in weeks:
            e = st.entry(d, geom)
            if e is None:
                continue
            if isinstance(e, str):
                ref[e] += 1
            else:
                entries.append(e)
        refusals[geom] = ref
        for c in CELLS:
            if c.geom == geom:
                outs_by_cell[c] = [exit_of(e, c, commission) for e in entries]
    write_trades(outs_by_cell)

    hdr("PRICING — entries and refusals per geometry (refusals count against C0b)")
    for geom in GEOMS:
        bc = cens[geom][0]
        attempted = sum(c[BUILT] + c[NO_FILL_DAY_QUOTE] for c in bc.values())
        n = len(outs_by_cell[Cell(geom[0], geom[1], HOLD)])
        ref = refusals[geom]
        print(f"  {Cell(geom[0], geom[1], '').label:<16} attempted {attempted:>4}  priced {n:>4}  "
              f"refused " + ("  ".join(f"{k}={v}" for k, v in sorted(ref.items())) or "none"))

    # ── per-cell table ───────────────────────────────────────────────────────
    hdr("CELLS — net R per trade, dollars of one lot, exits (descriptive except the primary)")
    zg, hg = {}, {}
    for c in CELLS:
        outs = outs_by_cell[c]
        zg[c] = grade_z(outs, cycles)
        months, _bc = monthly_series(outs, st.closes)
        hg[c] = grade_h(months)
    for c in CELLS:
        outs = outs_by_cell[c]
        tag = "PRIMARY" if c == PRIMARY else "descr. "
        if not outs:
            print(f"  {tag} {c.label}  no priced trade")
            continue
        net = [o.net for o in outs]
        ex = Counter(o.exit_reason for o in outs)
        print(f"  {tag} {c.label}  n {len(outs):>3}  meanR net {_f(statistics.fmean(o.R for o in outs))} "
              f"gross {_f(statistics.fmean(o.R_gross for o in outs))}  cycle-mean "
              f"{_f(zg[c].get('mean'))}  ARM Z {zg[c]['token']}  ARM H {hg[c]['token']}"
              + (f" (alpha {_f(hg[c].get('alpha'), '+.5f')})" if hg[c].get('c0') else ""))
        print(f"          $/lot mean {statistics.fmean(net):+8.1f}  median {statistics.median(net):+8.1f}  "
              f"total {sum(net):+10.0f}  worst {min(net):+8.0f}  ·  exits "
              + "  ".join(f"{k}={v}" for k, v in sorted(ex.items())))

    # ── ARM Z ────────────────────────────────────────────────────────────────
    z = zg[PRIMARY]
    hdr("ARM Z — primary cell, mean net R per monthly expiry cycle, against zero")
    pouts = outs_by_cell[PRIMARY]
    print(f"  priced trades {z['n']} on {z['cycles']} non-empty cycles of {z['slots']} "
          f"(C0b needs {C0B_TRADES} trades on {C0B_CYCLES} cycles)")
    if not z.get("c0"):
        print(f"  ARM Z: {UNDERPOWERED}")
    else:
        print(f"  ARM Z: cycle-mean R {_f(z['mean'])}  CI95 {_ci(z['ci'])} (stationary, block "
              f"{Z_BLOCK} cycles, {BOOT_N} draws, seed {SEED})")
        print("     beside it: " + "  ".join(f"block {b} {_ci(v)}" for b, v in z["alt"].items()))
        print("     C2 leave-one-year-out (expiry year): "
              + "  ".join(f"{y} {_f(v)}" for y, v in z["loyo"].items()))
        print("     C3 stress windows out: "
              + "  ".join(f"{k} {_f(v)}" for k, v in z["stress"].items()))
        print(f"     C0b Y  C1 {yn(z['c1'])}  C2 {yn(z['c2'])}  C3 {yn(z['c3'])}  ->  ARM Z {z['token']}")
        wk = week_series(pouts, weeks)
        print(f"  beside it (no verdict): mean net R per trade {_f(statistics.fmean(o.R for o in pouts))} "
              f"CI95 {_ci(stationary_ci(wk, WEEK_BLOCK))} (stationary over signal weeks, block "
              f"{WEEK_BLOCK})")

    # ── ARM H ────────────────────────────────────────────────────────────────
    h = hg[PRIMARY]
    hdr("ARM H — primary cell, monthly Jensen alpha against SPY shares (MTM, $25,000 reference)")
    months, bc = monthly_series(pouts, st.closes)
    if bc is not None:
        print(f"  book_curves TARGET_POSITION: positions {bc.n_positions}  reconciled "
              f"{bc.n_reconciled}  mismatches {len(bc.mismatches)}  carried-forward days "
              f"{bc.n_carried_forward}")
    if months:
        print(f"  months {months[0][0]} -> {months[-1][0]}  ({len(months)}; C0b needs {C0B_MONTHS})")
    if not h.get("c0"):
        print(f"  ARM H: {UNDERPOWERED}")
    else:
        print(f"  ARM H: alpha/month {_f(h['alpha'], '+.5f')}  CI95 {_ci(h['ci'], '+.5f')}  "
              f"beta {_f(h['beta'], '+.4f')}  CI95 {_ci(h['beta_ci'], '+.4f')} (stationary, "
              f"block {H_BLOCK} months, {BOOT_N} draws, seed {SEED})")
        print("     C2 leave-one-year-out: "
              + "  ".join(f"{y} {_f(v, '+.5f')}" for y, v in h["loyo"].items()))
        print("     C3 stress months out: "
              + "  ".join(f"{k} {_f(v, '+.5f')}" for k, v in h["stress"].items()))
        print(f"     account total (sum of monthly returns) {h['acct_total']:+.4f}  vs  beta-matched "
              f"SPY line {h['spy_line_total']:+.4f}")
        print(f"     C0b Y  C1 {yn(h['c1'])}  C2 {yn(h['c2'])}  C3 {yn(h['c3'])}  ->  ARM H {h['token']}")

    # ── MFE / MAE / capture / tiers / stop ───────────────────────────────────
    hdr("MFE, MAE AND CAPTURE — every cell, in R (gross marks over max loss)")
    for c in CELLS:
        outs = outs_by_cell[c]
        if not outs:
            continue
        mfe = [o.mfe for o in outs]
        mae = [o.mae for o in outs]
        pos = [o for o in outs if o.mfe > 0]
        cap = (sum(o.R for o in pos) / sum(o.mfe for o in pos)) if pos else float("nan")
        half = sum(1 for v in mae if v <= -0.5) / len(outs)
        print(f"  {c.label}  MFE mean {statistics.fmean(mfe):+.3f} median {statistics.median(mfe):+.3f}"
              f"  MAE mean {statistics.fmean(mae):+.3f} median {statistics.median(mae):+.3f}  "
              f"capture {_f(cap)}  reached -0.5R {half:.0%}")

    hdr("PRICING TIERS — leg marks over each primary hold, and entry fills (no verdict)")
    for geom in GEOMS:
        mt, ft = Counter(), Counter()
        for o in outs_by_cell[Cell(geom[0], geom[1], HOLD)]:
            ft.update(o.entry.fill_tags)
            for t in o.entry.mark_tags:
                if t is None:
                    mt["unmarked"] += 1
                else:
                    mt.update(t)
        tot = sum(mt.values()) or 1
        print(f"  {Cell(geom[0], geom[1], '').label:<16} marks " + "  ".join(
            f"{k} {v / tot:.1%}" for k, v in mt.most_common()) + "  ·  fills " + "  ".join(
            f"{k}={v}" for k, v in sorted(ft.items())))

    hdr("SIZE — one lot against the operator's $1,000 stop (descriptive)")
    for c in CELLS:
        outs = outs_by_cell[c]
        if not outs:
            continue
        fit = sum(1 for o in outs if o.entry.max_loss <= STOP_DOLLARS) / len(outs)
        breach = sum(1 for o in outs if min(o.filled_pnl()) <= -STOP_DOLLARS) / len(outs)
        ml = [o.entry.max_loss for o in outs]
        print(f"  {c.label}  max loss/lot median ${statistics.median(ml):,.0f} "
              f"(min ${min(ml):,.0f})  fits $1,000 {fit:.0%}  worst close breached -$1,000 {breach:.0%}")
    if pouts:
        sr = [stop_R(o) for o in pouts]
        print(f"  PRIMARY with the $1,000 stop (breach on t closes at t+1): mean net R "
              f"{statistics.fmean(sr):+.3f} vs {statistics.fmean(o.R for o in pouts):+.3f} without")

    # ── C4 PBO ───────────────────────────────────────────────────────────────
    hdr(f"C4 OVERFITTING — PBO by CSCV across the cells with >= {PBO_MIN_TRADES} trades (S = {PBO_S})")
    res, elig, why = pbo_read(outs_by_cell, weeks)
    pbo = None
    print(f"  cells with >= {PBO_MIN_TRADES} priced trades: {len(elig)} of {len(CELLS)}")
    if res is None:
        print(f"  PBO {NOT_COMPUTABLE}: {why}")
    else:
        pbo = res.pbo
        share = res.selection_share()
        print(f"  T={len(weeks)} signal weeks (padded to {res.n_rows}), N={res.n_configs} cells, "
              f"metric mean net R per trade, {res.n_combinations} combinations")
        print(f"  PBO {pbo:.3f}  (bar <= {PBO_MAX:.2f})  ·  primary is the IS best in "
              f"{share[0]:.0%} of splits  ·  prob OOS loss of the IS best {_f(res.prob_loss, '.3f')}")

    # ── forward read ─────────────────────────────────────────────────────────
    hdr(f"FORWARD READ — primary cell, signal weeks from {FORWARD_START}")
    fwd_weeks = [d for d in signal_weeks(st.sessions) if d >= FORWARD_START]
    closed = []
    for d in fwd_weeks:
        e = st.entry(d, PRIMARY.geom)
        if isinstance(e, Entry) and e.pick.expiry <= st.sessions[-1]:
            closed.append(exit_of(e, PRIMARY, commission))
    fcyc = sorted({o.expiry for o in closed})
    fvals = [m for m in cycle_means(closed, fcyc) if m is not None]
    wat, run = [], 0
    for cdate in fcyc:
        run += sum(1 for o in closed if o.expiry == cdate)
        wat.append(run)
    ftok, _step = forward_token(fvals, len(closed), wat)
    print(f"  forward signal weeks on the calendar {len(fwd_weeks)}; with a closed trade "
          f"{len(closed)} (floor {FORWARD_MIN_WEEKS})  FORWARD: {ftok}")

    # ── verdict ──────────────────────────────────────────────────────────────
    word, beside = study_token(True, z, h, pbo)
    hdr(f"VERDICT: {word}")
    print(f"  window   signal weeks {weeks[0]} -> {weeks[-1]}; era none (option cache only)")
    print(f"  >>> spy_put_write PRIMARY ({PRIMARY.label.strip()}): {word} <<<"
          + (f"  ({beside})" if beside else ""))
    zl = (f"cycle-mean R {_f(z['mean'])} CI95 {_ci(z['ci'])} on {z['n']} trades, "
          f"{z['cycles']} cycles" if z.get("c0") else f"{z['n']} trades, {z['cycles']} cycles")
    print(f"  ARM Z {z['token']}: {zl}")
    hl = (f"alpha/month {_f(h['alpha'], '+.5f')} CI95 {_ci(h['ci'], '+.5f')}, beta "
          f"{_f(h['beta'], '+.4f')} CI95 {_ci(h['beta_ci'], '+.4f')}, {h['n']} months"
          if h.get("c0") else f"{h['n']} months")
    print(f"  ARM H {h['token']}: {hl}")
    print(f"  C4 PBO {_f(pbo, '.3f') if pbo is not None else NOT_COMPUTABLE}  ·  "
          f"C0a PASS  ·  FORWARD {ftok}")
    print("  Descriptive cells (no verdict): " + "  ".join(
        f"[{c.label.strip()}: Z {zg[c]['token']} H {hg[c]['token']}]" for c in CELLS if c != PRIMARY))
    print("  Nothing ships from the retrospective.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
