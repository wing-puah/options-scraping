"""selloff_put_diagonal — on a SPY sell-off, does a near put plus a long-dated call diagonal pay?

Registration: `research/pre-registrations/f1_selection/regime/selloff_put_diagonal.md`
(drafted and accepted by default 2026-11-01). That file is the spec; this module
implements it and adds nothing to its bar. Where the build needed a ruling the
file did not give, the ruling is folded into the registration beside the clause
it amends, tagged `Resolved at build (2026-11-01)`. RESEARCH TIER: nothing ships
from this study.

THE RULE (`ARM K`). SPY only. The rule ARMS on a session whose close is at
least 5% below its 63-session high (`index_bear_hedge.EPISODE_DEFS["E-DD5"]`,
imported and hash-checked) and DISARMS on the first close back above -2%. The
arming session is trigger day D. On D+1's closing mid it buys:

  * the near put: 1 long put, strike nearest spot x 1.00, the standard monthly
    nearest 30 DTE; out on the first of a disarm, 75% of its DTE, or expiry;
  * the call diagonal: 1 long call nearest spot x 0.90 on the monthly nearest
    365 DTE, and 1 short call nearest spot x 1.05 on the put's expiry, rolled
    at each short expiry's close for three cycles, then closed whole.

R is the package's P&L over its combined entry debit, net of commission.

REUSED, NEVER COPIED
--------------------
Selection reads `mechanical_benchmark`'s listing grid (`grid_step`,
`grid_around`, `listed_by`, `monthly_expiries`) and `mechanical_baseline`'s
calendar (`load_closes`, `rule_expiry`). The strike walk here differs from
`mechanical_benchmark.nearest_listed` only in taking the option type; a test
pins it to the call walk. Pricing is production's shared functions from
`scripts/backtest/simulate.py`: `entry_day_fill` (closing mid, junk-quote
rule), `common_entry_day` inside `entry_window_end` (the five-session entry
window), `junk_day_mark` and `_snap_asof` (the daily mark, with the B5
zero-bid ceiling), `_monotonicity_violation`, and `_cost_knobs`. The
defined-risk clamp is `helpers._defined_risk_bounds`; it returns None for
every leg set here (two expiries, or one leg) except the printed-only bear put
spread cell's vertical, where it bounds the net put value and the run counts
the values it actually moved.

THE LEG-PATH WALKER. The frozen harness replays one single-expiry debit path
against exit thresholds; this package has rolls, a put with its own exit and a
diagonal across two expiries. `walk_package` prices it leg by leg on the
fixed event days instead: entry, put exit, each roll, the final close. It
never reads a mark between events, so no exit threshold exists to replay.

THE AWAIT GATE. While any PRIMARY trade (`ARM K` or `ARM C`, in-sample) awaits
a fetch, the run prints its census and `NOT BUILT — AWAITING SCRAPE` and stops.
`Book.price` refuses until `Book.open_outcomes` has seen no primary trade
await, so no outcome number can be computed early.

No code here fetches. The fetch plan is `plan()`, imported by
`scripts/collector/study_legs/fetch_selloff_put_diagonal_legs.py`.

Usage:
  python3 -m scripts.backtest_study run selloff_put_diagonal
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import logging
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest import simulate as SIM  # noqa: E402
from scripts.backtest.helpers import _defined_risk_bounds  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest.proxy import _strike_step  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_baseline as MBL  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f3_structure import structure_sweep as SS  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.f5_hedging import index_bear_hedge as IBH  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/selloff_put_diagonal.md"
ACCEPTED = "2026-11-01"

# ── registered constants (the registration's numbers; never re-chosen) ──────
TICKER = "SPY"
IN_SAMPLE = (date(2022, 3, 1), date(2026, 9, 22))
FORWARD_START = date(2026, 11, 1)
#: In-sample trades are graded only if their diagonal closes on or before this
#: day, the data end at registration. A fixed date, so the graded set never
#: grows as later sessions arrive (resolved at build 2026-11-01, operator).
CLOSE_BY = date(2026, 10, 22)
SUNSET = date(2029, 11, 1)
SEAL_START = date.fromisoformat(era_mod.SEAL_START)
PRIMARY_TRIGGER = "E-DD5"
#: The `E-DD8` threshold is the registered trigger parameter cell.
ALT_TRIGGER = "E-DD8"
#: ARM C: within this fraction of the 63-session high.
CALM_WITHIN = -0.02
PUT_DTE = 30
LONG_DTE = 365
LONG_MIN_DTE = 270
PUT_MULT = 1.00
#: Put-leg cell: the bear put spread's short put at spot x 0.95.
PUT_SPREAD_SHORT_MULT = 0.95
CALL_LONG_MULT, CALL_SHORT_MULT = 0.90, 1.05
#: OD1 secondary (ARM PD): long put at spot x 1.00, short put at spot x 0.95.
PUT_LONG_MULT, PUT_SHORT_MULT = 1.00, 0.95
CYCLES = 3
PUT_TIME_FRACTION = 0.75
COMMISSION = 0.65
#: The nine in-sample trigger days (plan-time table) and the calm-week count.
REGISTERED_TRIGGERS = tuple(date.fromisoformat(d) for d in (
    "2022-08-26", "2022-12-16", "2023-03-01", "2023-09-21", "2024-04-19",
    "2024-08-02", "2025-03-04", "2025-11-20", "2026-03-19"))
REGISTERED_CALM_WEEKS = 154
#: C3: triggers #1 and #7 carry most of the fall.
BIG_EPISODES = (date(2022, 8, 26), date(2025, 3, 4))
#: C0 floors.
C0_K = 8
C0_C = 60
BOOT_N = 10_000
SEED = 20261101
PBO_MAX = 0.5
FORWARD_MIN = 3
#: Tokens.
NOT_BUILT = "NOT BUILT — AWAITING SCRAPE"
UNDERPOWERED = "UNDERPOWERED"
UNWORDED = "UNWORDED"
NULL = "NULL"
PROVISIONAL = " (PROVISIONAL)"

OUT_DIR = ROOT / "backtests" / "study_output"
TRADES_CSV = OUT_DIR / "selloff_put_diagonal-trades.csv"
FETCH_CMD = "python3 scripts/collector/study_legs/fetch_selloff_put_diagonal_legs.py"

log = logging.getLogger("selloff_put_diagonal")
hdr = MB.hdr

#: Arms. K, K-diag and K-put are views of ONE priced package.
ARM_K, ARM_C = "K", "C"


class AwaitingScrape(RuntimeError):
    """An outcome was asked for while a primary trade awaits a fetch."""


# ════════════════════════════════════════════════════════════════════════════
# Cells — the primary and the parameters printed both ways
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass(frozen=True)
class Geom:
    """What a package is built from. `n_puts` is a view, not a geometry."""
    trigger: str = PRIMARY_TRIGGER
    direction: str = "call"            # OD1: call (PRIMARY) | put (ARM PD)
    cycles: int = CYCLES
    put_mult: float = PUT_MULT
    fill: str = "D+1"                  # D+1 (PRIMARY) | D
    put_spread: bool = False           # put leg: naked (PRIMARY) | bear put spread


@dataclasses.dataclass(frozen=True)
class Cell:
    name: str
    geom: Geom
    n_puts: int = 1


PRIMARY = Cell("PRIMARY", Geom())
#: One deviation from the primary per row of "Parameters printed both ways".
CELLS = (
    PRIMARY,
    Cell("diagonal put (ARM PD)", Geom(direction="put")),
    Cell("horizon 1 cycle", Geom(cycles=1)),
    Cell("horizon 6 cycles", Geom(cycles=6)),
    Cell("put strike x0.95", Geom(put_mult=0.95)),
    Cell("puts per diagonal 0 (ARM K-diag)", Geom(), n_puts=0),
    Cell("puts per diagonal 2", Geom(), n_puts=2),
    Cell("trigger -8% (E-DD8)", Geom(trigger=ALT_TRIGGER)),
    Cell("fill D close", Geom(fill="D")),
    Cell("put leg = bear put spread", Geom(put_spread=True)),
)
GEOMS = tuple(dict.fromkeys(c.geom for c in CELLS))


# ════════════════════════════════════════════════════════════════════════════
# G-HASH, the trigger and the calm weeks — pure
# ════════════════════════════════════════════════════════════════════════════

def gate_hash() -> list[str]:
    """G-HASH failures: the imported episode definitions must hash to the
    registered `EPISODE_DEFS_SHA256`."""
    got = IBH.episode_defs_hash()
    if got != IBH.EPISODE_DEFS_SHA256:
        return [f"EPISODE_DEFS hash {got[:12]} is not the registered "
                f"{IBH.EPISODE_DEFS_SHA256[:12]}"]
    return []


def thresholds(name: str) -> tuple[int, float, float]:
    """`(lookback, trigger, recover)` of an imported episode definition."""
    p = IBH.EPISODE_DEFS[name]
    return p["lookback"], p["trigger"], p["recover"]


@dataclasses.dataclass
class RuleState:
    """The real-time armed/disarmed state of one trigger definition.

    `armed[i]` is the state after session i's close. `triggers` are the
    sessions that armed it; `disarms` the sessions that disarmed it.
    """
    sessions: list[date]
    dd: list[float | None]
    armed: list[bool]
    triggers: list[date]
    disarms: list[date]

    def __post_init__(self):
        self.pos = {d: i for i, d in enumerate(self.sessions)}

    def armed_on(self, d: date) -> bool:
        return self.armed[self.pos[d]]


def arm_states(dd: list[float | None], trigger: float, recover: float
               ) -> tuple[list[bool], list[int], list[int]]:
    """`(armed, trigger_idx, disarm_idx)` on a drawdown series.

    Armed on the first close at or below `trigger` while disarmed; disarmed on
    the first close above `recover` while armed. Knowable on the day: it reads
    each close once, in order, and nothing after it.
    """
    armed, trig, dis, state = [], [], [], False
    for i, x in enumerate(dd):
        if x is not None:
            if state and x > recover:
                state = False
                dis.append(i)
            elif not state and x <= trigger:
                state = True
                trig.append(i)
        armed.append(state)
    return armed, trig, dis


def rule_state(closes: dict[date, float], name: str) -> RuleState:
    """The rule on the whole SPY calendar (from 1993), so the state on the
    in-sample start is already settled."""
    sessions = sorted(closes)
    lb, trig, rec = thresholds(name)
    dd = IBH.drawdowns([closes[d] for d in sessions], lb)
    armed, ti, di = arm_states(dd, trig, rec)
    return RuleState(sessions, dd, armed, [sessions[i] for i in ti],
                     [sessions[i] for i in di])


def trigger_days(rs: RuleState, lo: date, hi: date | None = None) -> list[date]:
    """Trigger days in `[lo, hi]` that have a next session."""
    last = rs.sessions[-1]
    return [d for d in rs.triggers if lo <= d and (hi is None or d <= hi) and d < last]


def calm_days(rs: RuleState, lo: date, hi: date | None = None) -> list[date]:
    """ARM C's entry dates: per ISO week, the first session that is disarmed and
    within 2% of the 63-session high (Resolved at build 2026-11-01)."""
    out: dict[tuple, date] = {}
    last = rs.sessions[-1]
    for i, d in enumerate(rs.sessions):
        if d < lo or (hi is not None and d > hi) or d >= last:
            continue
        x = rs.dd[i]
        if rs.armed[i] or x is None or x < CALM_WITHIN:
            continue
        out.setdefault(d.isocalendar()[:2], d)
    return sorted(out.values())


def disarm_after(rs: RuleState, after: date, upto: date) -> date | None:
    """The first disarm session in `(after, upto]`, or None."""
    for d in rs.disarms:
        if after < d <= upto:
            return d
    return None


# ════════════════════════════════════════════════════════════════════════════
# Selection — reads the decision day and nothing later
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass(frozen=True)
class Sel:
    """One strike choice. `status`: built | await | drop."""
    status: str
    strike: float | None = None
    reason: str = ""
    fetch: tuple = ()                  # ((opt, expiry, strike), ...)


def _leg(opt: str, expiry: date, strike: float, qty: int = 1) -> Leg:
    return Leg(qty, TICKER, expiry, float(strike), opt)


def cached_strikes(chain, expiry: date, opt: str) -> list[float]:
    return sorted(k for k in chain.strikes(TICKER, expiry)
                  if chain.cached(TICKER, expiry, k, opt))


def nearest_listed(chain, evidence: set[str], expiry: date, target: float,
                   spot: float, asof: date, opt: str) -> Sel:
    """The listed `opt` strike nearest `target`, walked nearest-first.

    `mechanical_benchmark.nearest_listed` with the option type as a parameter
    (a test pins the two together on calls). Skip-listed on evidence: step on.
    Cached with a row on or before `asof`: chosen. Cached without one: not
    listed yet, step on. Neither: AWAIT, it could be the nearest listed one.
    """
    cached = cached_strikes(chain, expiry, opt)
    step = MB.grid_step(spot, cached)
    for k in MB.grid_around(target, step, cached):
        if NTF.contract_stem(TICKER, expiry, k, opt) in evidence:
            continue
        if chain.cached(TICKER, expiry, k, opt):
            if MB.listed_by(chain, _leg(opt, expiry, k), asof):
                return Sel("built", k)
            continue
        return Sel("await", k, "strike_not_cached", ((opt, expiry, k),))
    return Sel("drop", reason="no_listed_strike")


class Listing:
    """Is a monthly expiry listed by a date? Memoised first-row dates."""

    def __init__(self, chain):
        self.chain = chain
        self._first: dict[date, date | None] = {}

    def first_row(self, expiry: date) -> date | None:
        if expiry not in self._first:
            best = None
            for k, cps in self.chain.idx.get((TICKER, expiry), {}).items():
                for cp in cps:
                    series, details = self.chain.history(
                        _leg("Call" if cp == "C" else "Put", expiry, k))
                    days = [d for d, _ in series] + list(details)
                    if days:
                        m = min(days)
                        best = m if best is None else min(best, m)
            self._first[expiry] = best
        return self._first[expiry]

    def state(self, evidence: set[str], expiry: date, opt: str, target: float,
              spot: float, asof: date) -> tuple[str, tuple]:
        """`("yes"|"no"|"await", fetch)` (Resolved at build 2026-11-01).

        Listed when any cached contract of the expiry has a row on or before
        `asof`. Not listed when contracts of it are cached and none has such a
        row (a cached history runs back to the contract's first quote), or when
        nothing of it is cached and the standard-grid strike nearest `target`
        is skip-listed on evidence. Otherwise unknown: fetch that strike.
        """
        first = self.first_row(expiry)
        if first is not None:
            return ("yes" if first <= asof else "no"), ()
        step = _strike_step(spot)
        k0 = round(round(target / step) * step, 4)
        if NTF.contract_stem(TICKER, expiry, k0, opt) in evidence:
            return "no", ()
        return "await", ((opt, expiry, k0),)


#: The longest long-leg expiry walked, in calendar days. A LEAP is allowed; this
#: only bounds the walk, which stops at the first expiry listed by the decision day.
LONG_MAX_WALK_DTE = 1100


def long_expiries(entry: date) -> list[date]:
    """The long leg's expiries in walk order: every monthly of at least 270 DTE,
    nearest 365 DTE first, with no upper cap (Resolved at build 2026-11-01: the
    operator approved longer-dated calls). A tie goes to the nearer expiry."""
    cands = MB.monthly_expiries(entry + timedelta(days=LONG_MIN_DTE),
                                entry + timedelta(days=LONG_MAX_WALK_DTE))
    return sorted(cands, key=lambda e: (abs((e - entry).days - LONG_DTE), e))


def select_long(chain, evidence, listing: Listing, opt: str, entry: date,
                target: float, spot: float, asof: date) -> tuple[Sel, date | None, bool]:
    """`(sel, expiry, substituted)` for the diagonal's long leg; substituted =
    the expiry is not the nearest-365 monthly."""
    for i, e in enumerate(long_expiries(entry)):
        st, fetch = listing.state(evidence, e, opt, target, spot, asof)
        if st == "await":
            return Sel("await", None, "long_expiry_unknown", fetch), e, i > 0
        if st == "no":
            continue
        s = nearest_listed(chain, evidence, e, target, spot, asof, opt)
        if s.status == "drop":
            continue
        return s, e, i > 0
    return Sel("drop", reason="no_long_expiry_ge270"), None, False


@dataclasses.dataclass
class Package:
    """One rule trade's legs, chosen on its decision days. `status`: built |
    await | drop | open (its diagonal closes after the calendar's end)."""
    arm: str
    signal: date
    entry: date                        # planned entry: D+1, or D under fill D
    geom: Geom
    status: str
    reason: str = ""
    put: tuple | None = None           # (opt, expiry, strike)
    put_short: tuple | None = None     # the put spread's short put, else None
    long: tuple | None = None
    shorts: list = dataclasses.field(default_factory=list)   # [(opt, expiry, strike)]
    rolls: list = dataclasses.field(default_factory=list)    # [E_1, ..., E_n]
    subst: bool = False
    fetch: tuple = ()

    @property
    def exit_day(self) -> date | None:
        return self.rolls[-1] if self.rolls else None


def roll_days(entry: date, cycles: int) -> list[date | None]:
    """`[E_1 .. E_n]`: E_1 is the monthly nearest 30 DTE from the entry day;
    each next one is the monthly nearest 30 DTE from the last."""
    out, cur = [], entry
    for _ in range(cycles):
        e = MBL.rule_expiry(cur, PUT_DTE)
        out.append(e)
        if e is None:
            break
        cur = e
    return out


def select(chain, evidence, listing: Listing, closes: dict[date, float],
           sessions: set[date], last: date, geom: Geom, arm: str,
           signal: date, entry: date) -> Package:
    """The package's strikes and expiries. Each choice reads its own decision
    day (D, or the roll day) and nothing later. No pricing."""
    pk = Package(arm, signal, entry, geom, "drop")
    rolls = roll_days(entry, geom.cycles)
    if any(e is None for e in rolls):
        pk.reason = "no_monthly"
        return pk
    pk.rolls = rolls
    if rolls[-1] > last:
        pk.status, pk.reason = "open", "open_at_data_end"
        return pk
    if any(e not in sessions for e in rolls):
        pk.reason = "expiry_not_a_session"
        return pk
    spot = closes[signal]
    call = geom.direction == "call"
    dopt = "Call" if call else "Put"
    l_mult, s_mult = ((CALL_LONG_MULT, CALL_SHORT_MULT) if call
                      else (PUT_LONG_MULT, PUT_SHORT_MULT))
    e1 = rolls[0]
    sels: list[Sel] = []
    put = nearest_listed(chain, evidence, e1, spot * geom.put_mult, spot, signal, "Put")
    sels.append(put)
    pshort = None
    if geom.put_spread:
        pshort = nearest_listed(chain, evidence, e1, spot * PUT_SPREAD_SHORT_MULT, spot,
                                signal, "Put")
        sels.append(pshort)
    lng, l_exp, pk.subst = select_long(chain, evidence, listing, dopt, entry,
                                       spot * l_mult, spot, signal)
    sels.append(lng)
    shorts = []
    decide, s_spot = signal, spot
    for e in rolls:
        s = nearest_listed(chain, evidence, e, s_spot * s_mult, s_spot, decide, dopt)
        sels.append(s)
        shorts.append(s)
        decide, s_spot = e, closes[e]
    for s in sels:
        if s.status == "drop":
            pk.reason = s.reason
            return pk
    if (pshort is not None and pshort.status == "built" and put.status == "built"
            and pshort.strike >= put.strike):
        pk.reason = "put_spread_degenerate"
        return pk
    fetch = tuple(f for s in sels for f in s.fetch)
    if any(s.status == "await" for s in sels):
        pk.status, pk.fetch = "await", fetch
        pk.reason = next(s.reason for s in sels if s.status == "await")
        return pk
    pk.status, pk.reason = "built", ""
    pk.put = ("Put", e1, put.strike)
    if pshort is not None:
        pk.put_short = ("Put", e1, pshort.strike)
    pk.long = (dopt, l_exp, lng.strike)
    pk.shorts = [(dopt, e, s.strike) for e, s in zip(rolls, shorts)]
    return pk


# ════════════════════════════════════════════════════════════════════════════
# The leg-path walker — production's shared pricing functions, leg by leg
# ════════════════════════════════════════════════════════════════════════════

def intrinsic(opt: str, strike: float, spot: float) -> float:
    return max(0.0, spot - strike) if opt == "Call" else max(0.0, strike - spot)


def leg_fill(chain, leg: Leg, day: date):
    """`entry_day_fill` on the leg's own closing quote of `day`."""
    _series, details = chain.history(leg)
    return SIM.entry_day_fill(details.get(day), leg.qty)


def fill_day(chain, legs: list[Leg], start: date, decided: date) -> date | None:
    """Production's entry day: the first day in `[start, window end]` on which
    every leg has a closing quote (`common_entry_day`, `entry_window_end`)."""
    days = [SIM.entry_close_days(chain.history(lg)[1], lg.qty) for lg in legs]
    return SIM.common_entry_day(days, start, SIM.entry_window_end(decided))


def leg_mark(chain, leg: Leg, day: date, spot: float | None,
             max_carry: int | None = SIM._DEFAULT_MAX_CARRY_DAYS):
    """`(price, tag)` to close `leg` at `day`'s close, or None.

    On the leg's expiry day: the closing mid, or intrinsic value when the quote
    fails the junk-quote rule or is missing (registration, and Resolved at
    build 2026-11-01 for a missing row). Any other day: production's daily mark
    (`simulate._price_leg`'s barchart branch, from the shared `_snap_asof`,
    `_is_junk_quote` and `junk_day_mark`), carried marks tagged stale past
    `max_carry` days.
    """
    series, details = chain.history(leg)
    if day >= leg.expiration:
        row = details.get(leg.expiration)
        if row is not None and not SIM._is_junk_quote(row):
            mid = SIM._close_mid(row)
            if mid is not None:
                return mid, "close_mid"
        if spot is None:
            return None
        return intrinsic(leg.opt_type, leg.strike, spot), "intrinsic"
    p, snap = SIM._snap_asof({"k": series}, "k", day, leg.expiration)
    if p is None:
        return None
    row, q_day = details.get(snap), snap
    if snap != day:
        today = details.get(day)
        if today is not None and SIM._is_junk_quote(today):
            row, q_day = today, day
    tag = "barchart"
    if SIM._is_junk_quote(row):
        marked = SIM.junk_day_mark(row, q_day, series, details, leg.expiration)
        if marked is None:
            return None
        p, tag, snap = marked
        if tag == "barchart_stale":
            return p, tag
    if max_carry is not None and snap is not None and (day - snap).days > max_carry:
        tag = "barchart_stale"
    return p, tag


@dataclasses.dataclass
class Priced:
    """One package, 1 contract per leg, prices in option points."""
    pk: Package
    entry_day: date
    put_in: float
    put_out: float
    put_exit: date
    put_reason: str
    long_in: float
    long_out: float
    short_in: list                     # sale price per cycle
    short_out: list                    # buy-back price per cycle
    tags: Counter
    clamp_bound: int                   # leg sets the defined-risk clamp bounded
    put_legs: int = 1                  # 1 naked put, 2 bear put spread
    clamp_hit: int = 0                 # put-spread values the clamp actually moved
    put_short_in: float | None = None  # put spread only: the short put's sale price
    put_short_out: float | None = None

    @property
    def put_debit(self) -> float:
        return self.put_in

    @property
    def diag_debit(self) -> float:
        return self.long_in - self.short_in[0]

    @property
    def put_pnl(self) -> float:
        return self.put_out - self.put_in

    @property
    def diag_pnl(self) -> float:
        return (self.long_out - self.long_in) + sum(
            a - b for a, b in zip(self.short_in, self.short_out))

    def sides(self, n_puts: int) -> int:
        """Leg-sides traded: the put in and out, the long in and out, and
        every short sold and bought back."""
        return 2 * self.put_legs * n_puts + 2 + 2 * len(self.short_in)


def put_exit_day(rs: RuleState, sessions: list[date], signal: date, entry: date,
                 expiry: date) -> tuple[date | None, str]:
    """The put's exit session: the first session after its entry day on which a
    disarm has happened since D, 75% of its DTE has elapsed, or it is the put's
    expiry (Resolved at build 2026-11-01)."""
    te = int((expiry - entry).days * PUT_TIME_FRACTION)
    for s in sessions:
        if s <= entry:
            continue
        if disarm_after(rs, signal, s) is not None:
            return s, "disarm"
        if s >= expiry:
            return (s if s == expiry else None), "expiry"
        if (s - entry).days >= te:
            return s, "time_75"
    return None, "open"


def walk_package(chain, pk: Package, rs: RuleState, sessions: list[date],
                 closes: dict[date, float], max_carry=SIM._DEFAULT_MAX_CARRY_DAYS
                 ) -> Priced | str:
    """Price a built package on its event days. `Priced`, or a drop reason.

    1. Entry: put, long and first short fill on ONE day, production's window
       from the planned entry day, off that day's closing quotes.
    2. The put exits on `put_exit_day`'s close (`leg_mark`).
    3. At each short expiry E_i the short is bought back (`leg_mark` on its
       expiry: mid, or intrinsic on a junk quote) and, before the last, the
       next short is sold on E_i's close, or the first day of production's
       window after it on which it has a closing quote.
    4. At E_n the long is closed on `leg_mark`.
    """
    if pk.status != "built":
        raise ValueError(f"cannot price a {pk.status} package")
    tags: Counter = Counter()
    p_leg = _leg(*pk.put, qty=1)
    l_leg = _leg(*pk.long, qty=1)
    s_legs = [_leg(*s, qty=-1) for s in pk.shorts]
    ps_leg = _leg(*pk.put_short, qty=-1) if pk.put_short else None
    entry_legs = [p_leg, l_leg, s_legs[0]] + ([ps_leg] if ps_leg else [])
    day = fill_day(chain, entry_legs, pk.entry, pk.signal)
    if day is None:
        return SIM.NO_COMMON_ENTRY_DAY
    fills = [leg_fill(chain, lg, day) for lg in entry_legs]
    if any(f is None for f in fills):
        return "no_entry_quote"
    if any(f[0] is None for f in fills):
        return SIM.JUNK_ENTRY_REFUSAL
    prices, ftags = [f[0] for f in fills], [f[1] for f in fills]
    tags.update(ftags)
    if SIM._monotonicity_violation(entry_legs, prices, ftags):
        return SIM.NON_MONOTONIC_REFUSAL
    put_in, long_in, short_in0 = prices[:3]
    ps_in = prices[3] if ps_leg else 0.0
    clamp, hit = int(_defined_risk_bounds(entry_legs) is not None), 0
    bounds = _defined_risk_bounds([p_leg, ps_leg]) if ps_leg else None
    if ps_leg:
        clamp += int(bounds is not None)
    net_in = put_in - ps_in
    if net_in <= 0:
        return "put_priced_at_zero"
    if bounds is not None and net_in > bounds[1]:
        net_in, hit = bounds[1], hit + 1
    if long_in - short_in0 <= 0:
        return "diagonal_priced_to_credit"
    # 2. the put
    pe, why = put_exit_day(rs, sessions, pk.signal, day, p_leg.expiration)
    if pe is None:
        return "put_exit_after_data_end"
    m = leg_mark(chain, p_leg, pe, closes.get(pe), max_carry)
    if m is None:
        return "put_unmarked"
    put_out = m[0]
    tags[m[1]] += 1
    ps_out = None
    if ps_leg:
        m2 = leg_mark(chain, ps_leg, pe, closes.get(pe), max_carry)
        if m2 is None:
            return "put_unmarked"
        ps_out = m2[0]
        tags[m2[1]] += 1
        put_out = put_out - ps_out
        if bounds is not None and not bounds[0] <= put_out <= bounds[1]:
            put_out, hit = min(max(put_out, bounds[0]), bounds[1]), hit + 1
    # 3. the rolls
    short_in, short_out = [short_in0], []
    for i, (s_leg, e) in enumerate(zip(s_legs, pk.rolls)):
        if i > 0:
            d = fill_day(chain, [s_leg], pk.rolls[i - 1], pk.rolls[i - 1])
            if d is None:
                return "roll_unfilled"
            f = leg_fill(chain, s_leg, d)
            if f is None or f[0] is None:
                return "roll_unfilled"
            short_in.append(f[0])
            tags[f[1]] += 1
        m = leg_mark(chain, s_leg, e, closes.get(e), max_carry)
        if m is None:
            return "short_unmarked"
        short_out.append(m[0])
        tags[m[1]] += 1
        clamp += int(_defined_risk_bounds([l_leg, s_leg]) is not None)
    # 4. the long
    m = leg_mark(chain, l_leg, pk.exit_day, closes.get(pk.exit_day), max_carry)
    if m is None:
        return "long_unmarked"
    tags[m[1]] += 1
    return Priced(pk=pk, entry_day=day, put_in=net_in, put_out=put_out, put_exit=pe,
                  put_reason=why, long_in=long_in, long_out=m[0], short_in=short_in,
                  short_out=short_out, tags=tags, clamp_bound=clamp,
                  put_legs=2 if ps_leg else 1, clamp_hit=hit,
                  put_short_in=ps_in if ps_leg else None, put_short_out=ps_out)


# ── the graded unit ─────────────────────────────────────────────────────────

def package_R(p: Priced, n_puts: int = 1, diag: bool = True, net: bool = True,
              commission: float = COMMISSION) -> float:
    """The package's P&L over its combined entry debit (registration, Pricing
    and costs). `n_puts` puts per diagonal; `diag=False` is the put alone.
    Net subtracts `commission` per contract per leg-side."""
    if not diag and n_puts == 0:
        raise ValueError("an empty package has no R")
    debit = n_puts * p.put_debit + (p.diag_debit if diag else 0.0)
    pnl = n_puts * p.put_pnl + (p.diag_pnl if diag else 0.0)
    gross = pnl * 100.0
    if net:
        sides = 2 * p.put_legs * n_puts + ((2 + 2 * len(p.short_in)) if diag else 0)
        gross -= commission * sides
    return gross / (debit * 100.0)


def hold_R(closes: dict[date, float], entry: date, exit_day: date) -> float | None:
    """ARM H: SPY shares bought at the entry close, sold at the diagonal's exit
    close. Same dollars as the package, so the R is the return."""
    a, b = closes.get(entry), closes.get(exit_day)
    if a is None or b is None:
        return None
    return b / a - 1.0


# ════════════════════════════════════════════════════════════════════════════
# The book — selection memoised; pricing gated
# ════════════════════════════════════════════════════════════════════════════

class Book:
    """Every package, memoised by `(geom, arm, signal)`.

    `price()` refuses until `open_outcomes()` has seen no primary trade await.
    That is the await gate, by construction: no figure can be computed early.
    """

    def __init__(self, chain, evidence, closes: dict[date, float],
                 sim_cfg: dict | None = None):
        self.chain, self.evidence, self.closes = chain, evidence, closes
        self.sim_cfg = sim_cfg or {}
        self.sessions = sorted(closes)
        self.session_set = set(self.sessions)
        self.nxt = {a: b for a, b in zip(self.sessions, self.sessions[1:])}
        self.listing = Listing(chain)
        self.rules = {n: rule_state(closes, n) for n in (PRIMARY_TRIGGER, ALT_TRIGGER)}
        self._sel: dict[tuple, Package] = {}
        self._px: dict[tuple, Priced | str] = {}
        self._open = False

    def dates(self, geom: Geom, arm: str, lo: date, hi: date | None) -> list[date]:
        rs = self.rules[geom.trigger]
        return trigger_days(rs, lo, hi) if arm == ARM_K else calm_days(rs, lo, hi)

    def package(self, geom: Geom, arm: str, signal: date, frozen: bool = True) -> Package:
        """`frozen`: an in-sample trade must close by `CLOSE_BY`, else it is
        `open` with reason `closes_after_freeze`. `frozen=False` is the
        all-calm-weeks check, which is printed and never graded."""
        frozen = frozen and signal <= IN_SAMPLE[1]
        key = (geom, arm, signal, frozen)
        if key not in self._sel:
            entry = signal if geom.fill == "D" else self.nxt[signal]
            last = min(self.sessions[-1], CLOSE_BY) if frozen else self.sessions[-1]
            pk = select(self.chain, self.evidence, self.listing, self.closes,
                        self.session_set, last, geom, arm, signal, entry)
            if pk.status == "open" and last < self.sessions[-1] \
                    and pk.rolls and pk.rolls[-1] <= self.sessions[-1]:
                pk.reason = "closes_after_freeze"
            self._sel[key] = pk
        return self._sel[key]

    def packages(self, geom: Geom, arm: str, lo: date = IN_SAMPLE[0],
                 hi: date | None = IN_SAMPLE[1], frozen: bool = True) -> list[Package]:
        return [self.package(geom, arm, d, frozen) for d in self.dates(geom, arm, lo, hi)]

    def freeze_check(self) -> list[Package]:
        """The primary ARM C weeks the freeze leaves out, built without it."""
        return [self.package(PRIMARY.geom, ARM_C, p.signal, frozen=False)
                for p in self.packages(PRIMARY.geom, ARM_C) if p.status == "open"]

    def primary_awaiting(self) -> list[Package]:
        return [p for arm in (ARM_K, ARM_C) for p in self.packages(PRIMARY.geom, arm)
                if p.status == "await"]

    def open_outcomes(self) -> None:
        aw = self.primary_awaiting()
        if aw:
            raise AwaitingScrape(f"{len(aw)} primary trades await a fetch")
        self._open = True

    def price(self, pk: Package) -> Priced | str:
        """`Priced` or a drop reason. Raises while the await gate is shut."""
        if not self._open:
            raise AwaitingScrape("outcomes are closed until no primary trade awaits")
        key = (pk.geom, pk.arm, pk.signal)
        if key not in self._px:
            rs = self.rules[pk.geom.trigger]
            carry = self.sim_cfg.get("max_price_carry_days", SIM._DEFAULT_MAX_CARRY_DAYS)
            self._px[key] = walk_package(self.chain, pk, rs, self.sessions, self.closes,
                                         carry)
        return self._px[key]


# ════════════════════════════════════════════════════════════════════════════
# Census — counts only
# ════════════════════════════════════════════════════════════════════════════

def census_counts(pks: list[Package]) -> dict:
    c = Counter(n=0, built=0, await_=0, drop=0, open=0, subst=0)
    fetch: set = set()
    by_year: Counter = Counter()
    for p in pks:
        c["n"] += 1
        if p.status == "await":
            c["await_"] += 1
            fetch |= {(o, e, round(float(k), 4)) for o, e, k in p.fetch}
        elif p.status == "drop":
            c["drop"] += 1
            by_year[(p.signal.year, p.reason)] += 1
        elif p.status == "open":
            c["open"] += 1
            by_year[(p.signal.year, p.reason)] += 1
        else:
            c["built"] += 1
        if p.subst and p.status == "built":
            c["subst"] += 1
            by_year[(p.signal.year, "long_expiry_not_nearest_365")] += 1
    return dict(c=c, fetch=fetch, by_year=by_year)


def census_line(label: str, arm: str, k: dict) -> str:
    c = k["c"]
    return (f"  {label:<34} ARM {arm:<2} n {c['n']:>4}  built {c['built']:>4}  "
            f"await {c['await_']:>4}  drop {c['drop']:>3}  open {c['open']:>3}  "
            f"subst {c['subst']:>3}  contracts-to-fetch {len(k['fetch']):>4}")


def fetch_targets(book: Book, scope: str = "primary") -> list[dict]:
    """Unique uncached contracts the awaiting in-sample trades name.

    `scope`: `primary` (the primary cell, ARM K and ARM C) or `all` (every
    parameter cell, both arms). A contract two trades name is listed once,
    under the first. The collector imports this; a re-run re-targets."""
    cells = [PRIMARY] if scope == "primary" else list(CELLS)
    seen: dict = {}
    for cell in cells:
        for arm in (ARM_K, ARM_C):
            for p in book.packages(cell.geom, arm):
                if p.status != "await":
                    continue
                for o, e, k in p.fetch:
                    seen.setdefault((o, e, round(float(k), 4)),
                                    f"{cell.name.split(' (')[0].replace(' ', '_')}:{arm}")
    if scope == "all":
        for p in book.freeze_check():
            if p.status == "await":
                for o, e, k in p.fetch:
                    seen.setdefault((o, e, round(float(k), 4)), "freeze_check:C")
    return [dict(ticker=TICKER, expiration=e, strike=k, opt_type=o, category=cat)
            for (o, e, k), cat in sorted(seen.items(),
                                         key=lambda kv: (kv[0][1], kv[0][0], kv[0][2]))]


def build_book(sim_cfg: dict | None = None) -> Book:
    return Book(NTF.Chain(), NTF.unlisted_evidence(), MBL.load_closes(), sim_cfg)


def plan(scope: str = "primary") -> list[dict]:
    """The collector's entry point: the fetch plan on the cache as it stands.
    Selection only; nothing is priced and no network is touched."""
    return fetch_targets(build_book(), scope)


# ════════════════════════════════════════════════════════════════════════════
# Grading — pure functions on rows (tested on synthetic rows)
# ════════════════════════════════════════════════════════════════════════════

def _sign(v: float) -> int:
    return (v > 0) - (v < 0)


def excludes_zero(ci) -> bool:
    lo, hi = ci
    return (lo > 0) or (hi < 0)


def _mean(rows, key="R") -> float:
    return statistics.fmean(r[key] for r in rows)


def draws_p(draws: list[float]) -> float:
    """Two-sided bootstrap p that the statistic is zero, from sorted draws:
    twice the smaller tail, with a +1 so it is never exactly 0."""
    n = len(draws)
    le = sum(1 for d in draws if d <= 0)
    ge = sum(1 for d in draws if d >= 0)
    return min(1.0, 2.0 * (min(le, ge) + 1) / (n + 1))


def _ci_of(draws: list[float], alpha: float = 0.05) -> tuple[float, float]:
    n = len(draws)
    return draws[int(alpha / 2 * n)], draws[int((1 - alpha / 2) * n)]


def boot_draws_independent(a: list[float], b: list[float], n: int = BOOT_N,
                           seed: int = SEED) -> list[float]:
    """Sorted draws of mean(a) - mean(b), each arm resampled on its own."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        sa = [a[rng.randrange(len(a))] for _ in a]
        sb = [b[rng.randrange(len(b))] for _ in b]
        out.append(statistics.fmean(sa) - statistics.fmean(sb))
    out.sort()
    return out


def boot_ci_independent(a: list[float], b: list[float], n: int = BOOT_N,
                        seed: int = SEED, alpha: float = 0.05) -> tuple[float, float]:
    """CI of mean(a) - mean(b), each arm resampled on its own (C1 for
    `ARM K` vs `ARM C`)."""
    return _ci_of(boot_draws_independent(a, b, n, seed), alpha)


def boot_draws_by_date(rows: list[dict], key: str, n: int = BOOT_N,
                       seed: int = SEED) -> list[float]:
    """Sorted draws of the mean, resampling dates as `protocol.boot_ci_by_date`
    does (the same random sequence, so the interval is the same one)."""
    by: dict[str, list[float]] = {}
    for r in rows:
        if r.get(key) is not None:
            by.setdefault(str(r["date"]), []).append(float(r[key]))
    dates = list(by)
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        pool = []
        for _ in range(len(dates)):
            pool.extend(by[rng.choice(dates)])
        out.append(statistics.fmean(pool))
    out.sort()
    return out


def boot_draws_paired(rows: list[dict], n: int = BOOT_N, seed: int = SEED) -> list[float]:
    """Sorted draws of mean(R_T) - mean(R_C) over resampled dates (the same
    sequence as `protocol.boot_ci_paired_by_date`)."""
    by: dict[str, list[tuple[float, float]]] = {}
    for r in rows:
        by.setdefault(str(r["date"]), []).append((float(r["R_T"]), float(r["R_C"])))
    dates = list(by)
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        a_pool, b_pool = [], []
        for _ in range(len(dates)):
            for a, b in by[rng.choice(dates)]:
                a_pool.append(a)
                b_pool.append(b)
        out.append(statistics.fmean(a_pool) - statistics.fmean(b_pool))
    out.sort()
    return out


def _big_cut(rows: list[dict]) -> list[dict]:
    big = {d.isoformat() for d in BIG_EPISODES}
    return [r for r in rows if r["date"] not in big]


def grade_vs_zero(rows: list[dict], key: str = "R", floor: int = C0_K,
                  n: int = BOOT_N, seed: int = SEED) -> dict:
    """C0-C3 on `{date, R}` rows; a date is one trigger day."""
    g = dict(n=len(rows), c0=len(rows) >= floor)
    if not g["c0"]:
        return g
    g["mean"] = _mean(rows, key)
    dr = boot_draws_by_date(rows, key, n=n, seed=seed)
    g["ci"], g["p"] = _ci_of(dr), draws_p(dr)
    g["c1"] = excludes_zero(g["ci"])
    folds = [_mean([r for r in rows if r["date"] != x["date"]], key) for x in rows]
    g["loo"] = (min(folds), max(folds))
    g["c2"] = all(_sign(f) == _sign(g["mean"]) for f in folds)
    cut = _big_cut(rows)
    g["cut_n"] = len(cut)
    g["cut_mean"] = _mean(cut, key) if cut else float("nan")
    g["c3"] = bool(cut) and _sign(g["cut_mean"]) == _sign(g["mean"])
    return g


def grade_vs_calm(k_rows: list[dict], c_rows: list[dict], key: str = "R",
                  n: int = BOOT_N, seed: int = SEED) -> dict:
    """`ARM K` vs `ARM C`: the difference of means, each arm resampled on its
    own. LOO and the big-episode cut drop trigger days; the calm arm stays."""
    g = dict(n=len(k_rows), n_c=len(c_rows),
             c0=len(k_rows) >= C0_K and len(c_rows) >= C0_C)
    if not g["c0"]:
        return g
    a, b = [r[key] for r in k_rows], [r[key] for r in c_rows]
    g["mean_T"], g["mean_C"] = statistics.fmean(a), statistics.fmean(b)
    g["gain"] = g["mean_T"] - g["mean_C"]
    dr = boot_draws_independent(a, b, n=n, seed=seed)
    g["ci"], g["p"] = _ci_of(dr), draws_p(dr)
    g["c1"] = excludes_zero(g["ci"])
    folds = [_mean([r for r in k_rows if r["date"] != x["date"]], key) - g["mean_C"]
             for x in k_rows]
    g["loo"] = (min(folds), max(folds))
    g["c2"] = all(_sign(f) == _sign(g["gain"]) for f in folds)
    cut = _big_cut(k_rows)
    g["cut_n"] = len(cut)
    g["cut_gain"] = (_mean(cut, key) - g["mean_C"]) if cut else float("nan")
    g["c3"] = bool(cut) and _sign(g["cut_gain"]) == _sign(g["gain"])
    return g


def grade_paired(rows: list[dict], n: int = BOOT_N, seed: int = SEED) -> dict:
    """The put contribution: `{date, R_T, R_C}` rows on the same trigger
    days, gain = T - C, CI resampling trigger days."""
    g = dict(n=len(rows), c0=len(rows) >= C0_K)
    if not g["c0"]:
        return g
    g["mean_T"], g["mean_C"] = _mean(rows, "R_T"), _mean(rows, "R_C")
    g["gain"] = g["mean_T"] - g["mean_C"]
    dr = boot_draws_paired(rows, n=n, seed=seed)
    g["ci"], g["p"] = _ci_of(dr), draws_p(dr)
    g["c1"] = excludes_zero(g["ci"])
    folds = [statistics.fmean(r["R_T"] - r["R_C"] for r in rows if r["date"] != x["date"])
             for x in rows]
    g["loo"] = (min(folds), max(folds))
    g["c2"] = all(_sign(f) == _sign(g["gain"]) for f in folds)
    cut = _big_cut(rows)
    g["cut_n"] = len(cut)
    g["cut_gain"] = (statistics.fmean(r["R_T"] - r["R_C"] for r in cut)
                     if cut else float("nan"))
    g["c3"] = bool(cut) and _sign(g["cut_gain"]) == _sign(g["gain"])
    return g


def token(g: dict, pos: str, neg: str, value: str = "gain") -> str:
    """The registered tokens: UNDERPOWERED, NULL, `neg`, `pos`, or UNWORDED."""
    if not g.get("c0"):
        return UNDERPOWERED
    if not g["c1"]:
        return NULL
    if g[value] < 0:
        return neg
    if g["c2"] and g["c3"]:
        return pos
    return UNWORDED


def criteria_met(g: dict) -> str:
    return " ".join(c.upper() for c in ("c0", "c1", "c2", "c3") if g.get(c))


def study_token(k: str, kc: str, put: str, dk: str | None, dkc: str | None) -> str:
    """The study-level token (registration, Verdicts). `dk`/`dkc` are
    `ARM K-diag` vs zero and vs the calm weeks' diagonal alone."""
    if NOT_BUILT in (k, kc, put):
        return NOT_BUILT
    if k == "PAYS" and kc == "SELLOFF-ENTRY-HELPS" and put != "PUT-COSTS":
        return "CANDIDATE" + PROVISIONAL
    if dk == "PAYS" and dkc == "SELLOFF-ENTRY-HELPS" and put == "PUT-COSTS":
        return "DIAGONAL-ONLY" + PROVISIONAL
    return "NO-EDGE" + PROVISIONAL


def forward_token(provisional: str, k_rs: list[float], diffs: list[float]) -> str:
    """The forward read: `k_rs` are closed forward triggers' net R, `diffs`
    each one's `ARM K` minus same-quarter `ARM C` mean."""
    if len(k_rs) < FORWARD_MIN:
        return "STILL-OPEN"
    m = statistics.fmean(k_rs)
    if m <= 0:
        return "NO-EDGE"
    if provisional.startswith("CANDIDATE") and diffs and statistics.fmean(diffs) > 0:
        return "CONFIRMED"
    return "STILL-OPEN"


SECONDARY = " (SECONDARY)"
FAMILY_ALPHA = 0.05
WRAP_TOKENS = ("WRAP-BEATS-SHARES", "SHARES-BEAT-WRAP")


def holm(pvals: dict[str, float], alpha: float = FAMILY_ALPHA) -> dict[str, tuple[float, bool]]:
    """Holm-Bonferroni step-down: `{name: (adjusted p, rejected)}`. The i-th
    smallest of m p-values is scaled by (m - i); the adjusted values are made
    monotone and capped at 1."""
    order = sorted(pvals, key=lambda k: (pvals[k], k))
    m, run, out = len(order), 0.0, {}
    for i, k in enumerate(order):
        run = max(run, min(1.0, (m - i) * pvals[k]))
        out[k] = (run, run < alpha)
    return out


def secondary_family(objs: dict[str, dict]) -> dict[str, dict]:
    """Re-grade one question's secondary objects under Holm. An object below
    its C0 floor stays out of the family. Each result is a copy of its grade
    with `c1` replaced by the family decision and `raw_p`, `adj_p` added."""
    powered = {k: g for k, g in objs.items() if g.get("c0")}
    h = holm({k: g["p"] for k, g in powered.items()})
    out = {}
    for k, g in objs.items():
        if k in powered:
            adj, rej = h[k]
            out[k] = dict(g, c1=rej, raw_p=g["p"], adj_p=adj)
        else:
            out[k] = dict(g)
    return out


def secondary_standing(k: str, kc: str, put: str | None, pbo: float | None) -> str:
    """`CANDIDATE (SECONDARY)` needs PAYS, SELLOFF-ENTRY-HELPS, a put that is not
    PUT-COSTS, and a PBO below 0.5 across the full cell set. Never a promotion."""
    if NOT_BUILT in (k, kc):
        return NOT_BUILT
    if not (k == "PAYS" and kc == "SELLOFF-ENTRY-HELPS" and put != "PUT-COSTS"):
        return "-"
    if pbo is None or pbo >= PBO_MAX:
        return "BLOCKED (PBO)"
    return "CANDIDATE" + SECONDARY


def quarter(d: date) -> tuple[int, int]:
    return d.year, (d.month - 1) // 3 + 1


def pbo_matrix(rows_by_cell: dict, lo: date = IN_SAMPLE[0], hi: date = IN_SAMPLE[1]):
    """`T quarters x N cells` of summed net R per signal-date quarter."""
    import numpy as np
    qs, cur = [], quarter(lo)
    while cur <= quarter(hi):
        qs.append(cur)
        cur = (cur[0] + 1, 1) if cur[1] == 4 else (cur[0], cur[1] + 1)
    idx = {q: i for i, q in enumerate(qs)}
    cells = list(rows_by_cell)
    M = np.zeros((len(qs), len(cells)))
    for j, c in enumerate(cells):
        for r in rows_by_cell[c]:
            i = idx.get(quarter(date.fromisoformat(r["date"])))
            if i is not None:
                M[i, j] += r["R"]
    return M


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def _f(v, fmt="+.3f") -> str:
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else format(v, fmt)


def print_grade(name: str, g: dict, tok: str, floor_note: str) -> None:
    if not g.get("c0"):
        print(f"  {name}: {UNDERPOWERED} — {floor_note}; census only")
        return
    yn = lambda v: "Y" if v else "n"  # noqa: E731
    if "mean_T" in g:
        head = (f"meanR {_f(g['mean_T'])} vs {_f(g['mean_C'])}  diff {_f(g['gain'])} "
                f"CI95 [{_f(g['ci'][0])}, {_f(g['ci'][1])}]  "
                f"no #1/#7 {_f(g['cut_gain'])}")
    else:
        head = (f"n {g['n']}  meanR {_f(g['mean'])} CI95 [{_f(g['ci'][0])}, "
                f"{_f(g['ci'][1])}]  no #1/#7 {_f(g['cut_mean'])}")
    print(f"  {name}: {head}")
    print(f"     LOO [{_f(g['loo'][0])}, {_f(g['loo'][1])}]  C0 Y  C1 {yn(g['c1'])}  "
          f"C2 {yn(g['c2'])}  C3 {yn(g['c3'])}  ->  {tok}"
          + (f" (criteria met: {criteria_met(g)})" if tok == UNWORDED else ""))


def operator_steps() -> None:
    print("  Operator-run steps, in order (none runs from here):")
    print(f"    1. {FETCH_CMD} --dry-run   (then --limit N)")
    print("    2. python3 scripts/backup_research_caches.py push")
    print("    3. re-run this study; a fetch can expose a nearer strike or prove an")
    print("       expiry unlisted, so steps 1-3 repeat until no primary trade awaits")
    print("  It does not run beside another option-cache writer: one writer.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)
    logging.getLogger("backtest").setLevel(logging.ERROR)
    logging.getLogger("scripts.backtest").setLevel(logging.ERROR)

    hdr("selloff_put_diagonal — on a SPY sell-off, does a near put plus a long-dated "
        "call diagonal pay?")
    sim_cfg = SS.load_sim_cfg()
    comm, slip = SIM._cost_knobs(sim_cfg)
    print(f"""  Registration {REGISTRATION}
  (accepted by default {ACCEPTED}). NOTHING SHIPS FROM THIS STUDY.
  PRIMARY: SPY; trigger E-DD5 (-5% vs 63-session high, disarm above -2%); D+1 closing
  mid; near ATM put (monthly nearest {PUT_DTE} DTE) + call diagonal (long x{CALL_LONG_MULT} \
nearest {LONG_DTE} DTE, short x{CALL_SHORT_MULT} on the put's expiry, {CYCLES} cycles).
  windows  in-sample {IN_SAMPLE[0]} -> {IN_SAMPLE[1]} (PROVISIONAL)  ·  forward from \
{FORWARD_START}  ·  sunset {SUNSET}
  era      reads no analysis row; the in-sample window stops before the seal ({SEAL_START})
  costs    commission ${comm:.2f}/contract/leg/side, slippage {slip:g} (config/backtest.yml; \
registered ${COMMISSION:.2f}, 0)""")
    if slip:
        print("  REFUSED: the registration fixes slippage at 0. Exit 1.")
        return 1
    if abs(comm - COMMISSION) > 1e-9:
        print(f"  NOTE: config commission ${comm:.2f} differs from the registered "
              f"${COMMISSION:.2f}; R uses the registered figure.")

    # ── G-HASH ───────────────────────────────────────────────────────────────
    bad_hash = gate_hash()
    print(f"\n  G-HASH (EPISODE_DEFS vs EPISODE_DEFS_SHA256 "
          f"{IBH.EPISODE_DEFS_SHA256[:12]}): {'PASS' if not bad_hash else 'FAIL'}")
    if bad_hash:
        for b in bad_hash:
            print(f"     {b}")
        hdr("GATE FAILURE — G-HASH")
        print("  No census, no outcome. Exit 1.")
        return 1
    lb, trig, rec = thresholds(PRIMARY_TRIGGER)
    print(f"     E-DD5: lookback {lb}, trigger {trig:+.2f}, recover {rec:+.2f}  ·  "
          f"E-DD8 trigger {thresholds(ALT_TRIGGER)[1]:+.2f}")

    book = build_book(sim_cfg)
    print(f"  calendar {book.sessions[0]} -> {book.sessions[-1]}  ({len(book.sessions)} "
          f"sessions, SPY close tables in backtests/mech_regime/)")

    # ── G-CENSUS: triggers and calm weeks, before any option price ──────────
    hdr("G-CENSUS — trigger days and calm weeks (market data only)")
    rs = book.rules[PRIMARY_TRIGGER]
    trigs = trigger_days(rs, *IN_SAMPLE)
    calm = calm_days(rs, *IN_SAMPLE)
    print("  In-sample trigger days (E-DD5), with the disarm that follows each:")
    for i, d in enumerate(trigs, 1):
        dis = disarm_after(rs, d, book.sessions[-1])
        dd = rs.dd[rs.pos[d]]
        print(f"    #{i}  {d}  dd {dd:+.3f}  disarm {dis or 'not yet'}")
    alt = trigger_days(book.rules[ALT_TRIGGER], *IN_SAMPLE)
    print(f"  E-DD8 trigger days (parameter cell): {', '.join(map(str, alt)) or 'none'}")
    print(f"  ARM C calm weeks (first disarmed session within 2% of the high, per ISO "
          f"week): {len(calm)}")
    fwd = trigger_days(rs, FORWARD_START)
    state_now = "ARMED" if rs.armed[-1] else "disarmed"
    print(f"  Forward (from {FORWARD_START}): {len(fwd)} trigger days; the rule is "
          f"{state_now} at {book.sessions[-1]} (dd {rs.dd[-1]:+.3f})")
    ok_trig = tuple(trigs) == REGISTERED_TRIGGERS
    ok_calm = len(calm) == REGISTERED_CALM_WEEKS
    print(f"  G-CENSUS trigger list = the nine registered dates: "
          f"{'PASS' if ok_trig else 'FAIL'};  calm weeks = {REGISTERED_CALM_WEEKS}: "
          f"{'PASS' if ok_calm else 'FAIL'}")
    seal_bad = [d for d in trigs + calm if d >= SEAL_START]
    print(f"  G-SEAL no in-sample signal date on or after {SEAL_START}: "
          f"{'PASS' if not seal_bad else 'FAIL'}")
    if not (ok_trig and ok_calm) or seal_bad:
        hdr("GATE FAILURE — G-CENSUS / G-SEAL")
        print("  No outcome printed. Exit 1.")
        return 1

    # ── fetch census, counts only ────────────────────────────────────────────
    hdr("CENSUS — every cell, ARM K and ARM C, in-sample (counts only; no price read)")
    cens = {}
    for cell in CELLS:
        for arm in (ARM_K, ARM_C):
            pks = book.packages(cell.geom, arm)
            cens[(cell.geom, arm)] = (pks, census_counts(pks))
            print(census_line(cell.name, arm, cens[(cell.geom, arm)][1]))
        if cell == PRIMARY:
            print("  -- parameter cells (a cell sharing the primary geometry repeats "
                  "its counts) --")
    print("\n  PRIMARY drops, opens and substitutions by year")
    for arm in (ARM_K, ARM_C):
        by = cens[(PRIMARY.geom, arm)][1]["by_year"]
        if not by:
            print(f"    ARM {arm}: none")
        for (yr, why), n in sorted(by.items()):
            print(f"    ARM {arm}  {yr}  {why:<26} {n:>4}")
    n_plan = len(fetch_targets(book, "primary"))
    n_all = len(fetch_targets(book, "all"))
    print(f"\n  fetch plan: primary {n_plan} unique uncached contracts; every cell {n_all}")
    print("  (one round: each awaiting leg names its nearest open strike; a fetch can "
          "expose the next)")

    # ── THE AWAIT GATE ───────────────────────────────────────────────────────
    try:
        book.open_outcomes()
    except AwaitingScrape as exc:
        hdr(f"VERDICT: {NOT_BUILT}")
        print(f"  PRIMARY: {NOT_BUILT} — {exc}.")
        print("  No outcome was computed for any arm: no R, no P&L, no CI.")
        operator_steps()
        return 0
    return outcomes(book, cens, comm)


def outcomes(book: Book, cens: dict, comm: float) -> int:
    """Everything past the await gate. `book.price` raises if it was not opened."""
    def priced(geom, arm):
        out, drops = [], Counter()
        for pk in cens[(geom, arm)][0]:
            if pk.status != "built":
                continue
            p = book.price(pk)
            if isinstance(p, str):
                drops[(pk.signal.year, p)] += 1
            else:
                out.append(p)
        return out, drops

    def rows(ps, n_puts=1, diag=True, net=True):
        return [dict(date=p.pk.signal.isoformat(),
                     R=package_R(p, n_puts, diag, net, COMMISSION)) for p in ps]

    def awaits(geom):
        return any(cens[(geom, a)][1]["c"]["await_"] for a in (ARM_K, ARM_C))

    pk_k, dk = priced(PRIMARY.geom, ARM_K)
    pk_c, dc = priced(PRIMARY.geom, ARM_C)
    hdr("PRICING — primary drops at pricing, by year")
    for arm, d in (("K", dk), ("C", dc)):
        if not d:
            print(f"    ARM {arm}: none")
        for (yr, why), n in sorted(d.items()):
            print(f"    ARM {arm}  {yr}  {why:<26} {n:>4}")
    clamp = sum(p.clamp_bound for p in pk_k + pk_c)
    tags = sum((p.tags for p in pk_k + pk_c), Counter())
    print(f"  defined-risk clamp bounded {clamp} leg sets (two expiries or one leg: "
          f"None by construction)")
    print("  price tags: " + "  ".join(f"{k}={v}" for k, v in sorted(tags.items())))
    late = sum(1 for p in pk_k + pk_c if p.entry_day != p.pk.entry)
    print(f"  entries moved off the planned day inside production's window: {late}")

    k_net, c_net = rows(pk_k), rows(pk_c)
    kd_net, cd_net = rows(pk_k, 0), rows(pk_c, 0)
    kp_net = rows(pk_k, 1, diag=False)
    hdr("PRIMARY OBJECTS (net R; in-sample tokens are PROVISIONAL)")
    g_k = grade_vs_zero(k_net)
    t_k = token(g_k, "PAYS", "LOSES", "mean")
    print_grade("ARM K vs zero", g_k, t_k, f"{len(k_net)} built trigger trades "
                f"(needs {C0_K})")
    g_kc = grade_vs_calm(k_net, c_net)
    t_kc = token(g_kc, "SELLOFF-ENTRY-HELPS", "SELLOFF-ENTRY-HURTS")
    print_grade("ARM K vs ARM C", g_kc, t_kc, f"{len(k_net)} trigger / {len(c_net)} calm "
                f"(needs {C0_K} / {C0_C})")
    put_rows = [dict(date=a["date"], R_T=a["R"], R_C=b["R"]) for a, b in zip(k_net, kd_net)]
    g_p = grade_paired(put_rows)
    t_p = token(g_p, "PUT-ADDS", "PUT-COSTS")
    print_grade("put contribution (ARM K - ARM K-diag)", g_p, t_p,
                f"{len(put_rows)} pairs (needs {C0_K})")
    g_dk = grade_vs_zero(kd_net)
    t_dk = token(g_dk, "PAYS", "LOSES", "mean")
    g_dkc = grade_vs_calm(kd_net, cd_net)
    t_dkc = token(g_dkc, "SELLOFF-ENTRY-HELPS", "SELLOFF-ENTRY-HURTS")
    fc = book.freeze_check()
    hdr("CHECK — ARM C with the calm weeks the freeze leaves out (printed, never graded)")
    still = sum(p.status == "open" for p in fc)
    wait = sum(p.status == "await" for p in fc)
    if not fc:
        print("  the freeze leaves out no calm week")
    elif still or wait:
        print(f"  {len(fc)} calm weeks left out by CLOSE_BY {CLOSE_BY}: {still} still open, "
              f"{wait} await a fetch (run the collector with --scope all). Check waits.")
    else:
        extra = [p for p in (book.price(pk) for pk in fc if pk.status == "built")
                 if not isinstance(p, str)]
        g_full = grade_vs_calm(k_net, c_net + rows(extra))
        if "gain" in g_full and "gain" in g_kc:
            same = _sign(g_full["gain"]) == _sign(g_kc["gain"])
            print(f"  all calm weeks: {len(c_net) + len(extra)}  ARM K - ARM C "
                  f"{g_full['gain']:+.3f}  graded {g_kc['gain']:+.3f}  "
                  f"{'same sign' if same else 'SIGN DIFFERS from the graded comparison'}")
        else:
            print("  all calm weeks: not computed (an arm is empty)")
    print_grade("ARM K-diag vs zero (DIAGONAL-ONLY test)", g_dk, t_dk, "below the floor")
    print_grade("ARM K-diag vs calm diagonal (DIAGONAL-ONLY test)", g_dkc, t_dkc,
                "below the floor")

    hdr("PRINTED ARMS — no verdict")
    gross = rows(pk_k, net=False)
    print(f"  ARM K gross meanR {_f(statistics.fmean(r['R'] for r in gross) if gross else None)}"
          f"  net {_f(statistics.fmean(r['R'] for r in k_net) if k_net else None)}")
    print(f"  ARM K-put meanR {_f(statistics.fmean(r['R'] for r in kp_net) if kp_net else None)}"
          f"  (put alone, n {len(kp_net)})")
    hs = [hold_R(book.closes, p.pk.entry, p.pk.exit_day) for p in pk_k]
    hs = [h for h in hs if h is not None]
    print(f"  ARM H (SPY shares, same horizon) mean return {_f(statistics.fmean(hs) if hs else None)}"
          f"  n {len(hs)}")
    print("  per trigger:  date        R_K     R_Kdiag  R_Kput   R_H     put exit")
    for p in pk_k:
        print(f"    {p.pk.signal}  {package_R(p):+.3f}  {package_R(p, 0):+.3f}  "
              f"{package_R(p, 1, diag=False):+.3f}  "
              f"{_f(hold_R(book.closes, p.pk.entry, p.pk.exit_day))}  "
              f"{p.put_exit} {p.put_reason}")

    hdr("PARAMETERS PRINTED BOTH WAYS — raw, uncorrected; graded under SECONDARY GRADES")
    rows_by_cell, cell_data = {}, {}
    for cell in CELLS:
        if awaits(cell.geom):
            print(f"  {cell.name:<34} {NOT_BUILT}")
            continue
        pk_, _ = priced(cell.geom, ARM_K)
        pc_, _ = priced(cell.geom, ARM_C)
        if cell.n_puts == 0:
            kr, cr = rows(pk_, 0), rows(pc_, 0)
        else:
            kr, cr = rows(pk_, cell.n_puts), rows(pc_, cell.n_puts)
        rows_by_cell[cell.name] = kr
        cell_data[cell.name] = dict(
            cell=cell, kr=kr, cr=cr,
            pr=([dict(date=a["date"], R_T=a["R"], R_C=b["R"])
                 for a, b in zip(kr, rows(pk_, 0))] if cell.n_puts else None))
        gk = grade_vs_zero(kr)
        gkc = grade_vs_calm(kr, cr)
        line = (f"  {cell.name:<34} K n {len(kr):>2} {token(gk, 'PAYS', 'LOSES', 'mean'):<12} "
                f"vs C {token(gkc, 'SELLOFF-ENTRY-HELPS', 'SELLOFF-ENTRY-HURTS')}")
        if cell.n_puts:
            pr = [dict(date=a["date"], R_T=a["R"], R_C=b["R"])
                  for a, b in zip(kr, rows(pk_, 0))]
            line += f"  put {token(grade_paired(pr), 'PUT-ADDS', 'PUT-COSTS')}"
        if cell.geom.put_spread:
            hits = sum(p.clamp_hit for p in pk_ + pc_)
            line += (f"  [put-spread clamp moved {hits} of "
                     f"{sum(1 for p in pk_ + pc_ if p.put_legs == 2)} values]")
        print(line)

    hdr("C4 OVERFITTING — PBO by CSCV across the trade-level cells, quarter blocks")
    pbo = None
    if len(rows_by_cell) < 2:
        print("  not computed: fewer than two cells built")
    else:
        M = pbo_matrix(rows_by_cell)
        S = M.shape[0] + (M.shape[0] % 2)
        Mp, padded = PBO.pad_head(M, S)
        res = PBO.cscv(Mp, S=S, metric=PBO.total_metric)
        print(f"  cells {len(rows_by_cell)}  quarters {M.shape[0]} (+{padded} zero pad)  "
              f"S {S}  PBO {res.pbo:.3f}  "
              f"({'no non-primary cell may be promoted' if res.pbo >= PBO_MAX else 'below 0.5'})")
        pbo = res.pbo
    secondary_report(book, pk_k, kp_net, cell_data, pbo)

    hdr("VERDICT")
    st = study_token(t_k, t_kc, t_p, t_dk, t_dkc)
    print(f"  ARM K vs zero          {t_k}{PROVISIONAL}")
    print(f"  ARM K vs ARM C         {t_kc}{PROVISIONAL}")
    print(f"  put contribution       {t_p}{PROVISIONAL}")
    print(f"  STUDY                  {st}")
    f_r, f_d, f_n = forward_rows(book)
    print(f"  FORWARD                {forward_token(st, f_r, f_d)}  ({f_n} forward triggers, "
          f"{len(f_r)} closed and priced; confirmation needs {FORWARD_MIN})")
    print("  Nothing ships from this study.")
    write_trades(book, pk_k + pk_c)
    return 0


def secondary_report(book: Book, pk_k: list, kp_net: list, cell_data: dict,
                     pbo: float | None) -> None:
    """The secondary grades (registration, Secondary grades): every non-primary
    cell, `ARM K-put` and `ARM K` vs `ARM H`, each under Holm within its question."""
    hdr("SECONDARY GRADES — Holm–Bonferroni within each question, family alpha 0.05")
    cells = {n: d for n, d in cell_data.items() if d["cell"] != PRIMARY}
    zero = {n: grade_vs_zero(d["kr"]) for n, d in cells.items()}
    zero["ARM K-put"] = grade_vs_zero(kp_net)
    calm = {n: grade_vs_calm(d["kr"], d["cr"]) for n, d in cells.items()}
    put = {n: grade_paired(d["pr"]) for n, d in cells.items() if d["pr"]}
    wrap_rows = []
    for p in pk_k:
        h = hold_R(book.closes, p.pk.entry, p.pk.exit_day)
        if h is not None:
            wrap_rows.append(dict(date=p.pk.signal.isoformat(), R_T=package_R(p), R_C=h))
    wrap = {"ARM K vs ARM H": grade_paired(wrap_rows)}
    fam = {"vs zero": (secondary_family(zero), "PAYS", "LOSES", "mean"),
           "vs own ARM C": (secondary_family(calm), "SELLOFF-ENTRY-HELPS",
                            "SELLOFF-ENTRY-HURTS", "gain"),
           "put contribution": (secondary_family(put), "PUT-ADDS", "PUT-COSTS", "gain"),
           "wrap vs shares": (secondary_family(wrap), *WRAP_TOKENS, "gain")}
    toks: dict = {}
    print(f"  {'question':<17}{'object':<36}{'n':>3}  {'token':<34}{'raw p':>7}{'adj p':>7}")
    for q, (gs, pos, neg, val) in fam.items():
        for name, g in gs.items():
            t = token(g, pos, neg, val)
            toks[(q, name)] = t
            shown = t if t == UNDERPOWERED else t + SECONDARY
            rp = _f(g.get("raw_p"), ".3f")
            ap = _f(g.get("adj_p"), ".3f")
            print(f"  {q:<17}{name:<36}{g['n']:>3}  {shown:<34}{rp:>7}{ap:>7}")
    print("  standing (never a promotion; needs PBO < 0.5, forward confirmation and a new "
          "registration):")
    for name in cells:
        k, kc = toks[("vs zero", name)], toks[("vs own ARM C", name)]
        pt = toks.get(("put contribution", name))
        print(f"    {name:<36}{secondary_standing(k, kc, pt, pbo)}")


def forward_rows(book: Book) -> tuple[list[float], list[float], int]:
    """`(net R, ARM K minus same-quarter ARM C, n triggers)` of the forward
    triggers whose diagonal has closed and priced. Past the await gate only."""
    ks = book.packages(PRIMARY.geom, ARM_K, FORWARD_START, None)
    cs = book.packages(PRIMARY.geom, ARM_C, FORWARD_START, None)
    calm_q: dict = defaultdict(list)
    for pk in cs:
        if pk.status == "built":
            p = book.price(pk)
            if not isinstance(p, str):
                calm_q[quarter(pk.signal)].append(package_R(p))
    rs, diffs = [], []
    for pk in ks:
        if pk.status != "built":
            continue
        p = book.price(pk)
        if isinstance(p, str):
            continue
        r = package_R(p)
        rs.append(r)
        q = calm_q.get(quarter(pk.signal))
        if q:
            diffs.append(r - statistics.fmean(q))
    return rs, diffs, len(ks)


def write_trades(book: Book, ps: list[Priced]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["arm", "signal", "entry_day", "put", "long", "shorts", "put_in", "put_out",
            "put_short_in", "put_short_out", "put_exit", "put_reason", "long_in", "long_out", "short_in", "short_out",
            "R_K_net", "R_K_gross", "R_Kdiag_net", "R_Kput_net", "R_H"]
    with open(TRADES_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for p in ps:
            w.writerow(dict(
                arm=p.pk.arm, signal=p.pk.signal, entry_day=p.entry_day,
                put=f"{p.pk.put[1]} {p.pk.put[2]:g}P", long=f"{p.pk.long[1]} {p.pk.long[2]:g}",
                shorts=" ".join(f"{e} {k:g}" for _o, e, k in p.pk.shorts),
                put_in=p.put_in, put_out=p.put_out, put_short_in=p.put_short_in,
                put_short_out=p.put_short_out, put_exit=p.put_exit,
                put_reason=p.put_reason, long_in=p.long_in, long_out=p.long_out,
                short_in=" ".join(f"{v:g}" for v in p.short_in),
                short_out=" ".join(f"{v:g}" for v in p.short_out),
                R_K_net=round(package_R(p), 6), R_K_gross=round(package_R(p, net=False), 6),
                R_Kdiag_net=round(package_R(p, 0), 6),
                R_Kput_net=round(package_R(p, 1, diag=False), 6),
                R_H=hold_R(book.closes, p.pk.entry, p.pk.exit_day)))
    print(f"  trades -> {TRADES_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
