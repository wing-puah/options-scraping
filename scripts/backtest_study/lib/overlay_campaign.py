"""Roll-capable short-option overlay campaigns, composed AROUND the frozen harness.

`financed_spread` ARM F4 sells ONE delta-targeted short leg at a nearer expiry, at
entry only, never rolled; its registration says twice that "a rolling campaign is a
separate future registration". This module is the engine for that registration
(`ladder_overlay`): the same tranche sold on a TRIGGER, ROLLED after it settles,
and managed through a BREACH policy — with a naked-put arm on the same machinery.

WHAT IS BORROWED AND WHAT IS NEW
--------------------------------
Borrowed verbatim BY IMPORT, never copied: `bear_rewrap.leg_details / leg_series /
entry_price_of`, `financed_spread.cached_ticker_expiries / DIAG_*`,
`lib.greeks.leg_greek`, `helpers._price_asof / _defined_risk_bounds`,
`harness.Trade`. `scripts.backtest_study.lib.ladder_targets` owns "which contracts does a
campaign owe a core?" (`eligible_expiries`, `cached_strikes`, `core_of`, `CoreSpec`,
`roll_chain`) and is reached through `_lt()` so the collector and the engine can
never disagree about the target set.

New here: the tranche lifecycle (trigger -> sale -> breach -> settlement -> roll),
the multi-tranche net-mark algebra, and the MODEL pricing tier. The Black-Scholes
formula that tier needs is defined HERE (`_bs_price`), not borrowed: production
(`scripts/backtest/`) deleted its copy on 2026-09-23, when model prices were
abolished from the backtest. It lives on only in this research sensitivity tier.

`harness.py` IS NOT EDITED AND IS NOT REPLACED. It prices nothing — it replays a
mark series — so a campaign is expressed the `bear_rewrap` way: a SYNTHETIC ROW
(core legs, core entry net, campaign-aware daily marks) fed to the same frozen
`Trade`/`replay`.

THREE DECISIONS THAT ARE NOT THIS MODULE'S TO MAKE, TRANSCRIBED FROM THE PLAN
-----------------------------------------------------------------------------
* DENOMINATOR. `entry_net` for a ladder cell is the CORE debit, NOT F4's
  credit-folded net. A T-GAP tranche sold on day 12 cannot be in the entry net, and
  folding the T0 credit in while leaving the T-GAP credit out would make the two
  arms' R incomparable. Gate G1b therefore pins the MARK series against F4, not R.
* CONTRACTS. The baseline core's production count, for every cell, at a 1:1 overlay
  ratio. `harness.replay`'s dollar_stop is an ABSOLUTE cap, so a cell left at a
  different count is handed a different effective stop.
* THE CORE DOES NOT CAP THE NET. A short call beyond the spread's hi strike is
  uncovered above its own strike, so `_defined_risk_bounds` is applied to the CORE
  value ONLY, and only on days with NO live tranche. See `campaign_net_marks`.

TIER ISOLATION
--------------
`ModelPrices` is a SENSITIVITY tier, never evidence. Every row it produces must
carry `tier="model"`, and `assert_not_model()` is the guard the study calls before
any criterion reads a cell. A model row that reaches a gate is the same class of
error as pooling two prompt versions into one population.

Pure library: no network, no writes, no config mutation, no study logic.
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Iterable, Protocol, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scipy.stats import norm  # noqa: E402

from lib.parsing import to_float  # noqa: E402
from scripts.backtest.helpers import (  # noqa: E402
    _defined_risk_bounds, _price_asof,
)
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.f3_structure import bear_rewrap as BR  # noqa: E402
from scripts.backtest_study.f3_structure import financed_spread as FS  # noqa: E402
from scripts.backtest_study.lib import greeks as GK  # noqa: E402
from scripts.backtest_study.lib import underlying as UL  # noqa: E402
from scripts.backtest_study.lib.harness import Trade  # noqa: E402

# ── frozen constants (registration values; do not tune after a number is seen) ──

TGAP_MIN_GAP = 0.015        # T-GAP: open(D) >= 1.015 x close(D-1)
TRUN_MIN_RUN = 0.04         # T-RUN: close(D) >= 1.04 x close(entry)
TRUN_RISING_CLOSES = 3      # ... AND the last 3 closes strictly rising
# A BREACHED tranche with no real mark within this many grid sessions of its own
# expiry settles at intrinsic instead of at that stale mark.
SETTLE_STALE_SESSIONS = 3

#: Candidate-set width and delta tolerance are F4's, imported rather than restated
#: so a change there can never leave the two constructions disagreeing.
N_CANDIDATES = FS.DIAG_N_CANDIDATES     # 4 nearest cached strikes beyond the outer
DELTA_TOL = FS.DIAG_DELTA_TOL           # 0.10; closest candidate further off -> excluded

#: The rate the MODEL tier prices at. It was transcribed from
#: `simulation.risk_free_rate` in config/backtest.yml; that key was removed on
#: 2026-09-23 with the production Black-Scholes pricer, so this is now the only
#: copy. The registration's value, unchanged.
RISK_FREE_RATE = 0.05


def _bs_price(S: float, K: float, T: float, r: float, sigma: float,
              option_type: str) -> float:
    """Black-Scholes option price, T in years — the `[MODEL]` tier's pricer ONLY.

    Moved here verbatim from `scripts/backtest/helpers.py` on 2026-09-23, when
    the operator abolished model prices from the backtest. Nothing in production
    may import it. Every mark it produces is tagged `tier="model"` and kept out
    of every criterion by `assert_not_model`.
    """
    if T <= 0 or sigma <= 0:
        return max(0, S - K) if option_type == "Call" else max(0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == "Call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


# spec vocabularies
T0, TGAP, TRUN, TNEVER = "T0", "TGAP", "TRUN", "TNEVER"
TRIGGERS = (T0, TGAP, TRUN, TNEVER)
#: Triggers that OBSERVE a market event and therefore sell on the NEXT grid day.
#: `T0` is not an observation — it is "sell at entry" — and shifting it would both
#: delay the fill the operator actually makes and break gate G1b, whose whole point
#: is that the T0/R0 cell reproduces F4's entry-day sale.
SHIFT_TRIGGERS = (TGAP, TRUN)

R0, R1 = "R0", "R1"
ROLLS = (R0, R1)

BHOLD, BBUY, BUP = "BHOLD", "BBUY", "BUP"
BREACH_POLICIES = (BHOLD, BBUY, BUP)

CALL, PUT = "Call", "Put"

# tranche close reasons
BREACH_BUYBACK = "breach_buyback"
SETTLE_MARK = "settle_mark"
SETTLE_INTRINSIC = "settle_intrinsic"
SETTLE_NO_MARK = "settle_no_mark"
OPEN_AT_GRID_END = "open_at_grid_end"

# census keys — the first five are `financed_spread`'s own, verbatim
SKIP_NO_NEAR_EXPIRY = "skip_no_near_expiry"
SKIP_NO_CACHED_CANDIDATE = "skip_no_cached_candidate"
SKIP_GREEKS_ABSENT = "skip_greeks_absent"
SKIP_NO_ENTRY_DELTA = "skip_no_entry_delta"
SKIP_TARGET_UNREACHABLE = "skip_target_unreachable"
# ... and three this module adds, because a ROLLED campaign can fail in ways a
# single entry-day sale cannot. They are named in the same shape on purpose.
SKIP_NO_GRID_DAY = "skip_no_grid_day"        # the sale day is past the core's path window
SKIP_NO_SPOT = "skip_no_spot"                # put arm: no underlying close to hang strikes off
SKIP_NO_ENTRY_PRICE = "skip_no_entry_price"  # the picked contract could not be filled

# pricing tiers
CACHE_TIER = "cache"
MODEL_TIER = "model"


class ModelTierLeak(AssertionError):
    """A `[MODEL]` sensitivity row reached a place only evidence may reach."""


# ── the ladder_targets seam ──────────────────────────────────────────────────
#
# `scripts/backtest_study/lib/ladder_targets.py` is the ONE owner of the target set and is
# written alongside this module. It is reached lazily through `_lt()` rather than
# imported at module scope for two reasons: this module must stay importable while
# that file is being written, and a test can substitute a stub by setting the
# single module attribute `_LT` — no `sys.modules` surgery, no duplicate definition
# of `eligible_expiries` / `cached_strikes` living here to go stale.

_LT = None


def _lt():
    """The `ladder_targets` module. Monkeypatch `_LT` to stub it in a test."""
    global _LT
    if _LT is None:
        from scripts.backtest_study.lib import ladder_targets as _mod
        _LT = _mod
    return _LT


# ── data structures ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Tranche:
    """One short option sold against the core, from sale to settlement.

    Frozen: a lifecycle step returns a NEW tranche (`dataclasses.replace`) rather
    than mutating one, so a mark series computed from a list of tranches can never
    depend on when in the walk it was computed.

      leg           the short contract (qty NEGATIVE, per unit of the core)
      open_day      the grid day it was actually sold — the first grid day on or
                    after the trigger's sale day on which the contract printed a
                    session. Never a carried quote.
      credit        per-contract entry credit, POSITIVE, on `entry_price_of`'s
                    production fill convention (Open -> mark -> carried prior mark)
      close_day     the grid day the leg stops being marked. None while live and for
                    a tranche still open when the grid ends.
      close_cost    per-contract cost to close, POSITIVE. From `close_day` onward the
                    leg contributes `leg.qty * close_cost` as a REALIZED CONSTANT.
      close_reason  breach_buyback | settle_mark | settle_intrinsic | settle_no_mark
                    | open_at_grid_end
      breached      STICKY: the underlying closed through the short strike at least
                    once while the tranche was live. Recorded under every breach
                    policy, including BHOLD, because it is a census fact (G4) before
                    it is an action.
    """

    leg: Leg
    open_day: date
    credit: float
    close_day: date | None = None
    close_cost: float | None = None
    close_reason: str | None = None
    breached: bool = False

    @property
    def closed(self) -> bool:
        return self.close_day is not None

    def live_on(self, day: date) -> bool:
        """Is the leg marked-to-market on `day`?

        Half-open `[open_day, close_day)`: on the close day itself the leg is a
        realized constant. That is what makes the series continuous — see
        `campaign_net_marks`.
        """
        if day < self.open_day:
            return False
        return self.close_day is None or day < self.close_day


@dataclass(frozen=True)
class CampaignSpec:
    """One cell's campaign: when to sell, whether to roll, what a breach does.

      trigger   T0 (at entry) | TGAP | TRUN | TNEVER (the no-overlay comparison)
      roll      R0 (sell once) | R1 (re-arm after each settlement)
      breach    BHOLD (record only) | BBUY (buy back) | BUP (buy back and roll up-and-out)
      target    the per-contract |Delta| the strike is picked at (0.20 | 0.30)
      opt_type  "Call" (ladder arm) | "Put" (naked-put arm)
    """

    trigger: str = T0
    roll: str = R0
    breach: str = BHOLD
    target: float = 0.20
    opt_type: str = CALL

    def __post_init__(self) -> None:
        if self.trigger not in TRIGGERS:
            raise ValueError(f"trigger {self.trigger!r} not in {TRIGGERS}")
        if self.roll not in ROLLS:
            raise ValueError(f"roll {self.roll!r} not in {ROLLS}")
        if self.breach not in BREACH_POLICIES:
            raise ValueError(f"breach {self.breach!r} not in {BREACH_POLICIES}")
        if self.opt_type not in (CALL, PUT):
            raise ValueError(f"opt_type {self.opt_type!r} not in {(CALL, PUT)}")

    @property
    def label(self) -> str:
        return (f"{self.trigger}/{self.roll}/{self.breach}/"
                f"d{int(round(self.target * 100))}/{self.opt_type[0]}")


@dataclass(frozen=True)
class CostModel:
    """The production transaction-cost knobs, `simulate._cost_knobs`' two numbers.

    BOTH DEFAULT TO 0, exactly as `config/backtest.yml` ships them: zero charges
    nothing, so a campaign priced with the default reproduces the gross number and
    turning costs on stays a deliberate act with its own before/after.
    """

    commission_per_contract: float = 0.0
    slippage_frac_of_spread: float = 0.0


@dataclass(frozen=True)
class CampaignCosts:
    """What the campaign's round trips cost, and on what basis."""

    commission: float
    slippage: float
    total: float
    opens: int
    closes: int
    basis: str

    def net(self, gross_dollars: float) -> float:
        """`gross_dollars` less the campaign's transaction costs."""
        return gross_dollars - self.total


# ── price sources ────────────────────────────────────────────────────────────

class PriceSource(Protocol):
    """How a campaign reads a contract. Two implementations, never mixed in a cell.

    `tier` is not decoration: it is what `assert_not_model` reads, and every row a
    study builds from a source must carry it.
    """

    tier: str

    def mark(self, leg: Leg, day: date) -> float | None:
        """`leg`'s value on `day`, carry-forward (`_price_asof` semantics)."""

    def entry(self, leg: Leg, day: date) -> float | None:
        """`leg`'s FILL on `day` — the production entry convention, not a mark."""

    def has_real_row(self, leg: Leg, day: date) -> bool:
        """Did the contract print a session on `day`? Never a carried quote."""

    def spread(self, leg: Leg, day: date) -> float | None:
        """Quoted Ask-Bid in option points on `day`, or None when not two-sided."""


class CachePrices:
    """The evidence tier: `bear_rewrap`'s pricing path, unchanged.

    `mark` is `_price_asof` over the contract's real bars, bounded by its own
    expiration — the carry-forward production applies. `entry` is
    `entry_price_of`, which mirrors `_simulate._entry_price_leg` in all three of
    its branches (Open -> that day's mark -> the last mark on or before the day).
    """

    tier = CACHE_TIER

    def mark(self, leg: Leg, day: date) -> float | None:
        return _price_asof({"k": BR.leg_series(leg)}, "k", day, leg.expiration)

    def entry(self, leg: Leg, day: date) -> float | None:
        return BR.entry_price_of(leg, day)

    def has_real_row(self, leg: Leg, day: date) -> bool:
        return day in BR.leg_details(leg)

    def spread(self, leg: Leg, day: date) -> float | None:
        return _row_spread(BR.leg_details(leg).get(day))


class ModelPrices:
    """The `[MODEL]` sensitivity tier: every leg repriced by Black-Scholes.

    S = the underlying's OHLC close, K/type from the leg, T = (expiry - day)/365,
    r = `RISK_FREE_RATE` (the production constant, not an invented one), and sigma =
    the leg's ENTRY-DAY cached IV / 100, HELD CONSTANT for the leg's whole life and
    scaled by `sigma_scale` ({1.00, 0.75, 1.25} in the registration). Holding sigma
    constant is the point of the arm: it answers "what would this campaign have done
    with the vol path taken out", which a cached mark cannot.

    A LEG WITH NO USABLE ENTRY IV PRICES TO None, NEVER TO sigma=0. Barchart writes
    sentinel sessions with IV/Delta/Gamma/Theta/Vega/Rho/Theo all literally 0 while
    the mark is real; read literally, sigma=0 collapses `_bs_price` to intrinsic and
    a deep-ITM contract silently prices as if it had no time value at all. The repo
    invariant is that a missing greek is None, never 0.0, so a falsy IV — absent
    cell or sentinel row, the same test `lib/greeks.leg_greek` uses — makes the leg
    unpriceable for the whole arm.

    ENTRY DAY. `register(leg, day)` pins it, and `run_campaign` /
    `campaign_net_marks` do not call it — the study registers the core legs at the
    core's entry day and each tranche at its `open_day`. Unregistered, the leg falls
    back to the FIRST cached row date, which is the earliest day the contract could
    have been entered. The fallback deliberately does NOT hunt for the first row
    with a usable IV: that would route around the None rule above.

    `has_real_row` still reads the CACHE. Whether a contract printed a session is a
    fact about the data, not about the pricer, and a model tier that could open a
    tranche on a day the contract did not trade would be inventing liquidity.
    """

    tier = MODEL_TIER

    def __init__(self, sigma_scale: float, bars: dict,
                 entry_days: dict | None = None, rate: float | None = None) -> None:
        self.sigma_scale = float(sigma_scale)
        self.bars = bars or {}
        self.rate = RISK_FREE_RATE if rate is None else float(rate)
        self._entry_days: dict[tuple, date] = dict(entry_days or {})

    # -- registration --------------------------------------------------------

    def register(self, leg: Leg, day: date) -> None:
        self._entry_days[_leg_key(leg)] = day

    def register_all(self, legs: Iterable[Leg], day: date) -> None:
        for leg in legs:
            self.register(leg, day)

    # -- pricing -------------------------------------------------------------

    def sigma_of(self, leg: Leg) -> float | None:
        rows = BR.leg_details(leg)
        day = self._entry_days.get(_leg_key(leg))
        if day is None:
            if not rows:
                return None
            day = min(rows)
        row = rows.get(day)
        if row is None:
            return None
        iv = to_float(row.get("IV"))
        if not iv:                       # absent cell OR the all-zero sentinel row
            return None
        return iv / 100.0 * self.sigma_scale

    def spot(self, day: date) -> float | None:
        return _close_asof(self.bars, day)

    def mark(self, leg: Leg, day: date) -> float | None:
        s = self.spot(day)
        sigma = self.sigma_of(leg)
        if s is None or s <= 0 or sigma is None or sigma <= 0:
            return None
        T = (leg.expiration - day).days / 365.0
        return _bs_price(s, leg.strike, T, self.rate, sigma, leg.opt_type)

    def entry(self, leg: Leg, day: date) -> float | None:
        return self.mark(leg, day)

    def has_real_row(self, leg: Leg, day: date) -> bool:
        return day in BR.leg_details(leg)

    def spread(self, leg: Leg, day: date) -> float | None:
        return None                      # a model has no quotes to give up


def assert_not_model(rows: Iterable, *, require_tier: bool = True) -> Iterable:
    """Refuse a row set that carries a `[MODEL]` row. Returns `rows` for chaining.

    The study calls this before EVERY criterion. `require_tier` (default on) also
    refuses an UNTAGGED row: an untagged row is indistinguishable from a model row
    that lost its label, and the point of the guard is that the sensitivity tier can
    never be read as evidence by accident.
    """
    materialised = list(rows)
    for i, row in enumerate(materialised):
        tier = row.get("tier") if isinstance(row, dict) else getattr(row, "tier", None)
        if tier == MODEL_TIER:
            raise ModelTierLeak(
                f"row {i} carries tier={MODEL_TIER!r}: the MODEL tier is sensitivity, "
                "never evidence, and may not reach a criterion")
        if require_tier and tier is None:
            raise ModelTierLeak(
                f"row {i} carries no `tier`: an untagged row cannot be shown to be "
                "evidence rather than a MODEL row that lost its label")
    return materialised


# ── small shared helpers ─────────────────────────────────────────────────────

def _leg_key(leg: Leg) -> tuple:
    return (leg.ticker, leg.expiration, leg.strike, leg.opt_type)


def _row_spread(row: dict | None) -> float | None:
    """Ask - Bid in option points, or None when the row is not two-sided."""
    if not row:
        return None
    bid, ask = to_float(row.get("Bid")), to_float(row.get("Ask"))
    if bid is None or ask is None or ask < bid:
        return None
    return ask - bid


def _close_asof(bars: dict, day: date) -> float | None:
    """The underlying close on `day`, else the last bar's close before it.

    Carrying back matters because the core grid is a WEEKDAY grid: a market holiday
    is a grid day with no bar, and treating it as "no price" would silently skip a
    breach check rather than repeat the last known close.
    """
    bar = bars.get(day)
    if bar is not None:
        return bar.c
    earlier = [d for d in bars if d < day]
    return bars[max(earlier)].c if earlier else None


def _trailing_sessions(bars: dict, day: date, n: int) -> list[date]:
    """The `n` bar dates ending AT `day` (fewer if the series runs out)."""
    if day not in bars:
        return []
    return sorted(d for d in bars if d <= day)[-n:]


def _next_grid_day(grid: Sequence[date], day: date) -> date | None:
    return next((d for d in grid if d > day), None)


def _sessions_between(grid: Sequence[date], after: date, through: date) -> int:
    """Grid sessions in `(after, through]` — how stale a mark is, in sessions."""
    return sum(1 for d in grid if after < d <= through)


def last_real_mark(leg: Leg, on_or_before: date) -> tuple[date | None, float | None]:
    """`(day, mark)` of the leg's last REAL bar at or before `on_or_before`.

    Real bars only, never a carried quote — the same series `f4_last_short_mark`
    settles against.
    """
    series = [(d, m) for d, m in BR.leg_series(leg) if d <= on_or_before]
    return series[-1] if series else (None, None)


def _intrinsic(leg: Leg, spot: float) -> float:
    return max(0.0, spot - leg.strike) if leg.opt_type == CALL \
        else max(0.0, leg.strike - spot)


def core_unit(rec: dict, default: int = 1) -> int:
    """The core's per-unit LONG quantity — the 1:1 overlay ratio's `1`.

    `CoreSpec` deliberately carries no quantity (it describes a strike geometry, not
    a size), so the ratio is read off the book record's own legs the way
    `financed_spread.build_f4` reads it.
    """
    legs = getattr(rec.get("t"), "legs", None) or []
    return abs(next((lg.qty for lg in legs if lg.qty > 0), default)) or default


# ── triggers ─────────────────────────────────────────────────────────────────

def trigger_days(core, spec: CampaignSpec, bars: dict,
                 entry_day: date | None) -> list[date]:
    """Every grid day on which `spec`'s trigger CONDITION holds.

    This is the condition, not the schedule: `run_campaign` decides which of these
    days actually fires (one per empty tranche slot) and on which day the sale lands.

      TNEVER  []. The no-overlay comparison cell.
      T0      [entry_day]. "Sell at entry", the F4 construction.
      TGAP    open(D) >= (1 + TGAP_MIN_GAP) x close(D-1) on the CORE TICKER'S own
              bars — two numbers, both stamped on or before D, so the sale a session
              later reads nothing it could not have known. `t_gap`'s shape.
      TRUN    close(D) >= (1 + TRUN_MIN_RUN) x close(entry) AND the last
              TRUN_RISING_CLOSES closes strictly rising. Both halves end AT D.

    A day whose bar is missing (or, for TGAP, whose bar has no open — the close-only
    `Price~` fallback path) simply does not qualify. It is never filled in from the
    neighbouring session: a fabricated open is a fabricated trigger.
    """
    if spec.trigger == TNEVER:
        return []
    if spec.trigger == T0:
        return [entry_day] if entry_day is not None else []

    grid = list(core.grid)
    out: list[date] = []

    if spec.trigger == TGAP:
        for day in grid:
            bar = bars.get(day)
            if bar is None or bar.o is None:
                continue
            earlier = [d for d in bars if d < day]
            if not earlier:
                continue
            prev_close = bars[max(earlier)].c
            if not prev_close or prev_close <= 0:
                continue
            if bar.o >= prev_close * (1.0 + TGAP_MIN_GAP):
                out.append(day)
        return out

    # TRUN
    base = bars.get(entry_day) if entry_day is not None else None
    if base is None or not base.c or base.c <= 0:
        return []
    for day in grid:
        bar = bars.get(day)
        if bar is None or bar.c is None:
            continue
        if bar.c < base.c * (1.0 + TRUN_MIN_RUN):
            continue
        days = _trailing_sessions(bars, day, TRUN_RISING_CLOSES)
        if len(days) < TRUN_RISING_CLOSES:
            continue
        closes = [bars[d].c for d in days]
        if all(b > a for a, b in zip(closes, closes[1:])):
            out.append(day)
    return out


# ── selling one tranche ──────────────────────────────────────────────────────

def sell_tranche(core, day: date, spec: CampaignSpec, prices: PriceSource,
                 expiries: Sequence[date], *, unit: int = 1,
                 spot: float | None = None,
                 after_expiry: date | None = None) -> tuple[Tranche | None, str]:
    """`(Tranche, "ok")` or `(None, census key)` for ONE sale at `day`.

    `build_f4`'s pick rule, unchanged, applied at an arbitrary roll day instead of
    only at entry:

      EXPIRY     the first of `ladder_targets.eligible_expiries(day, remaining_dte,
                 expiries)` — the same window as `financed_spread.near_expiry_for`,
                 anchored on `day`, with `remaining_dte = (core.expiry - day).days`.
                 `after_expiry` (BUP's roll-out) restricts it to expiries strictly
                 beyond the breached tranche's.
      STRIKES    the N_CANDIDATES nearest CACHED strikes at that expiry, beyond the
                 position: calls strictly above `core.hi`; puts strictly below the
                 underlying close on the sale day (`spot`, falling back to
                 `core.spot_entry`). Never an invented increment, never a strike
                 borrowed from another expiry.
      OPEN DAY   per candidate, the first grid day on or after `day`, not past the
                 candidate's own expiry, on which the contract PRINTED A SESSION.
                 Never a carried quote. The delta is then read on that same day, so
                 the pick and the fill are one moment rather than two.
      PICK       the candidate whose per-contract |Delta| is closest to `spec.target`;
                 further off than DELTA_TOL is `skip_target_unreachable`, excluded and
                 counted, never silently filled.
      SENTINEL   a candidate whose open-day row carries no IV HAS NO MEASURED DELTA
                 and is skipped (`skip_greeks_absent`), because Barchart writes
                 all-zero greek blocks on real-priced sessions and a deep-ITM
                 contract read as 0.00 delta lands inside the tolerance. Detected on
                 IV, not on Delta: a genuinely far-OTM option may round its delta to
                 0.00 while still quoting an IV.
      CREDIT     `prices.entry(leg, open_day)` — the FILL, on production's
                 Open -> mark -> carried-mark convention, not a same-day mark.

    `unit` is the overlay ratio (1:1 with the core, per the plan). It scales the
    leg's qty and divides `leg_greek`'s qty-scaled delta back to a per-contract one.
    """
    search = [d for d in core.grid if d >= day]
    if not search:
        return None, SKIP_NO_GRID_DAY

    remaining = (core.expiry - day).days
    if remaining <= 0:
        return None, SKIP_NO_NEAR_EXPIRY

    eligible = [e for e in _lt().eligible_expiries(day, remaining, list(expiries))
                if after_expiry is None or e > after_expiry]
    if not eligible:
        return None, SKIP_NO_NEAR_EXPIRY
    expiry = eligible[0]

    strikes = list(_lt().cached_strikes(core.ticker, expiry, spec.opt_type))
    if spec.opt_type == CALL:
        candidates = [k for k in sorted(strikes) if k > core.hi][:N_CANDIDATES]
    else:
        ref = spot if spot is not None else core.spot_entry
        if ref is None:
            return None, SKIP_NO_SPOT
        candidates = [k for k in sorted(strikes, reverse=True) if k < ref][:N_CANDIDATES]
    if not candidates:
        return None, SKIP_NO_CACHED_CANDIDATE

    window = [d for d in search if d <= expiry]
    unit = max(1, int(unit))
    best: Leg | None = None
    best_gap: float | None = None
    best_open: date | None = None
    n_sentinel = 0
    for strike in candidates:
        leg = Leg(qty=-unit, ticker=core.ticker, expiration=expiry,
                  strike=strike, opt_type=spec.opt_type)
        open_day = next((d for d in window if prices.has_real_row(leg, d)), None)
        if open_day is None:
            continue
        row = BR.leg_details(leg).get(open_day)
        if row is not None and not to_float(row.get("IV")):
            n_sentinel += 1
            continue                     # zero-filled greek row: no measured delta
        delta = GK.leg_greek(leg, open_day, "Delta")
        if delta is None:
            continue
        gap = abs(abs(delta) / unit - spec.target)
        if best_gap is None or gap < best_gap:
            best, best_gap, best_open = leg, gap, open_day

    if best is None:
        return None, (SKIP_GREEKS_ABSENT if n_sentinel else SKIP_NO_ENTRY_DELTA)
    if best_gap > DELTA_TOL:
        return None, SKIP_TARGET_UNREACHABLE

    credit = prices.entry(best, best_open)
    if credit is None:
        return None, SKIP_NO_ENTRY_PRICE
    return Tranche(leg=best, open_day=best_open, credit=credit), "ok"


# ── the campaign walk ────────────────────────────────────────────────────────

def _breach_hit(tranche: Tranche, opt_type: str, spot: float | None) -> bool:
    if spot is None:
        return False
    return spot >= tranche.leg.strike if opt_type == CALL else spot <= tranche.leg.strike


def _settle(tranche: Tranche, day: date, bars: dict,
            grid: Sequence[date]) -> Tranche:
    """Close a tranche that has run past its own expiry, on `day`.

    `day` is the first grid day STRICTLY AFTER the expiry — `f4_buyback`'s
    `residual_expiry` session, kept identical so a T0/R0/BHOLD campaign reproduces
    F4's series day for day (gate G1b).

      settle_mark       the default: the leg's LAST REAL MARK on or before its
                        expiry. `financed_spread` amendment 2's precedent — never
                        dropped to zero, which would forgive assignment.
      settle_intrinsic  ONLY when the tranche was BREACHED and has no real mark
                        within SETTLE_STALE_SESSIONS grid sessions of expiry. A
                        breached short that stopped printing is exactly the case
                        where the last stale mark understates what closing costs, so
                        the OHLC close's intrinsic is paid instead. Counted, and
                        never applied to an unbreached tranche: there the stale mark
                        is a quiet contract, not a hidden loss.
      settle_no_mark    no real mark at all and no intrinsic available. Closes at the
                        credit, booking zero P&L on the leg rather than inventing one
                        (`f4_buyback`'s `residual_no_mark`, same value).
    """
    expiry = tranche.leg.expiration
    mark_day, mark = last_real_mark(tranche.leg, expiry)
    stale = mark_day is None or _sessions_between(grid, mark_day, expiry) > SETTLE_STALE_SESSIONS

    if tranche.breached and stale:
        spot = _close_asof(bars, expiry)
        if spot is not None:
            return replace(tranche, close_day=day,
                           close_cost=_intrinsic(tranche.leg, spot),
                           close_reason=SETTLE_INTRINSIC)
    if mark is None:
        return replace(tranche, close_day=day, close_cost=tranche.credit,
                       close_reason=SETTLE_NO_MARK)
    return replace(tranche, close_day=day, close_cost=mark, close_reason=SETTLE_MARK)


def _manage(tranche: Tranche, spec: CampaignSpec, day: date, prices: PriceSource,
            bars: dict, grid: Sequence[date]) -> Tranche:
    """One grid day of a live tranche: breach first, then settlement past expiry."""
    if day < tranche.open_day or tranche.closed:
        return tranche
    if day > tranche.leg.expiration:
        return _settle(tranche, day, bars, grid)

    if not tranche.breached and _breach_hit(tranche, spec.opt_type, _close_asof(bars, day)):
        tranche = replace(tranche, breached=True)
    if tranche.breached and spec.breach in (BBUY, BUP):
        cost = prices.mark(tranche.leg, day)
        if cost is not None:
            return replace(tranche, close_day=day, close_cost=cost,
                           close_reason=BREACH_BUYBACK)
        # No priceable mark: the leg cannot be bought back today. It stays live and
        # the policy re-tries tomorrow — never closed at a fabricated price.
    return tranche


def run_campaign(core, spec: CampaignSpec, prices: PriceSource, bars: dict,
                 expiries: Sequence[date], costs: CostModel | None = None, *,
                 unit: int = 1) -> tuple[list[Tranche], Counter]:
    """Walk the core's grid and return `(tranches, census)`.

    THE SCHEDULE

      * A trigger day fires ONLY into an EMPTY slot, at most once per slot. A
        qualifying day that lands while a tranche is live is lost, not queued —
        "one tranche per empty slot" is the registered rule.
      * TGAP / TRUN sell on the NEXT grid day after the day the condition held (the
        gap is read at the open, the run at the close; both are known a session
        before money moves). T0 sells ON its day — it is "at entry", not an
        observation, and shifting it would break the F4 identity gate.
      * R0 sells at most one tranche for the whole path. R1 re-arms when a tranche
        SETTLES: under T0 that is immediate, and since a settlement session is
        already the first grid day after the expiry, the next sale is that same day.
        Under TGAP/TRUN the slot simply reopens and waits for the next qualifying day.
      * BUP is the one policy that re-sells without a trigger: it buys the breached
        leg back and sells the next ELIGIBLE EXPIRY BEYOND IT at the target delta, on
        the next grid day. It is a BREACH policy, so R0 does not cap it — "buy it
        back and roll it up-and-out" is one management action on one tranche, not a
        second sale of the slot.
      * A tranche whose expiry is beyond the end of the grid — a long-dated core
        truncated by the 120-day path cap — is left `open_at_grid_end`, exactly as
        `f4_buyback` leaves it.

    `costs` is accepted so a caller has ONE call site for a cell, and is deliberately
    NOT applied here: no transaction cost may move a trigger, a strike or a
    settlement, or the mechanics would depend on the cost knobs and the gross/net
    split the report prints would stop being a split of the same campaign. Charge it
    with `costs_of()`.
    """
    grid = list(core.grid)
    census: Counter = Counter()
    tranches: list[Tranche] = []
    if spec.trigger == TNEVER or not grid:
        return tranches, census

    fires = set(trigger_days(core, spec, bars, core.entry_day))
    consumed: set[date] = set()
    live_idx: int | None = None
    pending: tuple[date, date | None, bool] | None = None

    for day in grid:
        # (a) manage the live tranche
        if live_idx is not None:
            managed = _manage(tranches[live_idx], spec, day, prices, bars, grid)
            tranches[live_idx] = managed
            if managed.closed:
                census[managed.close_reason] += 1
                if managed.breached:
                    census["breached"] += 1
                live_idx = None
                if managed.close_reason == BREACH_BUYBACK and spec.breach == BUP:
                    nxt = _next_grid_day(grid, day)
                    if nxt is not None:
                        pending = (nxt, managed.leg.expiration, True)
                elif spec.roll == R1 and spec.trigger == T0:
                    pending = (day, None, False)

        # (b) fire a trigger into an empty slot
        if live_idx is None and pending is None:
            exhausted = spec.roll == R0 and tranches
            if not exhausted and day in fires and day not in consumed:
                consumed.add(day)
                if spec.trigger in SHIFT_TRIGGERS:
                    nxt = _next_grid_day(grid, day)
                    if nxt is None:
                        census[SKIP_NO_GRID_DAY] += 1
                    else:
                        pending = (nxt, None, False)
                else:
                    pending = (day, None, False)

        # (c) execute a sale scheduled for today (or earlier)
        if live_idx is None and pending is not None and pending[0] <= day:
            sale_day, after_expiry, forced = pending
            pending = None
            # R0 caps the campaign at one TRIGGERED tranche. It does not cap BUP,
            # which is a BREACH policy: "buy it back and roll it up-and-out" is one
            # management action on one tranche, not a second sale of the slot, and
            # the two arms are orthogonal in the registration.
            if spec.roll == R0 and tranches and not forced:
                census["skip_roll_disabled"] += 1
            else:
                tranche, why = sell_tranche(
                    core, sale_day, spec, prices, expiries, unit=unit,
                    spot=_close_asof(bars, sale_day), after_expiry=after_expiry)
                census[why] += 1
                if tranche is not None:
                    tranches.append(tranche)
                    live_idx = len(tranches) - 1
                    census["tranche_opened"] += 1

    if live_idx is not None:
        left = tranches[live_idx]
        tranches[live_idx] = replace(left, close_reason=OPEN_AT_GRID_END)
        census[OPEN_AT_GRID_END] += 1
        if left.breached:
            census["breached"] += 1
    return tranches, census


# ── the net-mark algebra ─────────────────────────────────────────────────────

def campaign_net_marks(core_legs: Sequence[Leg], tranches: Sequence[Tranche],
                       grid: Sequence[date], prices: PriceSource, *,
                       credit_received: bool = False) -> list[float | None]:
    """Daily signed net over the core's grid for the whole campaign.

    Three contributions per day, and the third is what makes a ROLL readable:

      CORE          `sum(qty * carry-forward mark)` over the core legs. None on a
                    day any core leg cannot be priced — the whole day is then None,
                    never a partial sum.
      LIVE TRANCHES `sum(qty * mark)` over tranches with `open_day <= day < close_day`
                    (qty is NEGATIVE, so a live short subtracts its value). A live
                    tranche that cannot be marked makes the day None: a short leg
                    the market stopped quoting is not a short leg worth zero.
      CLOSED        `sum(qty * close_cost)` over tranches with `day >= close_day`, a
                    REALIZED CONSTANT from that day on — not zero, not a
                    carried-forward live mark.

    THE CLAMP. `_defined_risk_bounds` bounds a SINGLE-EXPIRATION defined-risk
    payoff. While a tranche is live the position has two expirations and a naked
    short beyond the core, so there IS no such bound and none is applied — that is
    G2's clause, "unclamped while a tranche lives", not a missing clamp. On a day
    with NO live tranche the position is a plain single-expiry core again, so the
    clamp applies TO THE CORE VALUE ONLY, with realized constants added OUTSIDE it:
    realized cash is not an option value and has no arbitrage bound.

    THE ALGEBRA, worked by hand across a ROLL boundary. `Trade.pnl_of(M) =
    (M - entry_net)/|entry_net|`, and for a ladder cell `entry_net` is the CORE
    debit D_e alone (the plan's denominator decision) — tranche credits are NOT
    folded in, they arrive through the mark series. With `u` the overlay unit, a
    tranche sold for C_o and closed for C_c contributes `u*(C_o - C_c)` of realized
    P&L, and that is exactly what `M(t) = D(t) - u*C_c + u*C_o` less D_e gives.

    THE `credit_received` FLAG decides whether the `+ u*C_o` term is in the series,
    and the two callers need opposite answers:

      * `credit_received=True` (`campaign_trade`, the study's own cells): the
        denominator is the bare core debit, so the credit the position TOOK IN
        must arrive through the marks or a tranche sold at entry prints
        `R = -u*C_o/D_e` on its own fill day when the true return is zero, and a
        naked put that expires worthless prints R = 0 instead of +credit.
      * `credit_received=False` (`f4_identity`, gate G1b): `financed_spread` folds
        the entry-day credit into `entry_net` instead, so ITS mark series carries
        only `leg.qty * C_c`, and the identity check must compare like with like.

    Numerically, D_e = 3.00, u = 1, core grid days 0..5, one tranche sold day 1 for
    0.80 and settling day 3 at 0.30, a second sold day 4 for 0.60, with
    `credit_received=False` (add +0.80 from day 1 and +0.60 from day 4 for True):

        day 0  core 3.00, no tranche      -> M = 3.00          (clamped: flat core)
        day 1  core 3.10, leg live @0.80  -> M = 3.10 - 0.80 = 2.30   (unclamped)
        day 2  core 3.30, leg live @0.45  -> M = 3.30 - 0.45 = 2.85   (unclamped)
        day 3  core 3.40, leg CLOSED @0.30 -> M = 3.40 - 0.30 = 3.10  (clamped core)
        day 4  core 3.50, tranche 2 live @0.60, tranche 1 realized -0.30
                                          -> M = 3.50 - 0.60 - 0.30 = 2.60 (unclamped)
        day 5  core 3.60, tranche 2 live @0.20, tranche 1 realized -0.30
                                          -> M = 3.60 - 0.20 - 0.30 = 3.10 (unclamped)

    CONTINUITY AT EVERY BOUNDARY. On the day a tranche closes, its mark-in and its
    cost-out are THE SAME NUMBER — a breach buyback books that day's mark, and an
    expiry settlement books the last real mark on or before expiry, which is exactly
    what `_price_asof` carries forward on the settlement session (it stops at the
    leg's own expiration). So closing adds no step to the series; it only stops the
    leg from moving afterwards. Day 3 above reads 3.40 - 0.30 whether the tranche is
    called live-at-0.30 or closed-at-0.30. The only discontinuity a close can
    introduce is the CLAMP switching on, which is a deliberate, tested behaviour
    (`_defined_risk_bounds` is meaningless while the naked leg lives) and not a
    property of the tranche arithmetic.
    """
    core_legs = list(core_legs)
    clamp = _defined_risk_bounds(core_legs)
    out: list[float | None] = []
    for day in grid:
        core_value = 0.0
        broken = False
        for leg in core_legs:
            price = prices.mark(leg, day)
            if price is None:
                broken = True
                break
            core_value += leg.qty * price
        if broken:
            out.append(None)
            continue

        live_value = 0.0
        realized = 0.0
        n_live = 0
        for tranche in tranches:
            if day < tranche.open_day:
                continue
            if credit_received:
                realized -= tranche.leg.qty * tranche.credit     # + u*C_o, qty < 0
            if tranche.closed and day >= tranche.close_day:
                if tranche.close_cost is None:
                    broken = True
                    break
                realized += tranche.leg.qty * tranche.close_cost
                continue
            mark = prices.mark(tranche.leg, day)
            if mark is None:
                broken = True
                break
            n_live += 1
            live_value += tranche.leg.qty * mark
        if broken:
            out.append(None)
            continue

        if n_live == 0 and clamp is not None:
            core_value = max(clamp[0], min(clamp[1], core_value))
        out.append(core_value + live_value + realized)
    return out


def campaign_trade(core_rec: dict, tranches: Sequence[Tranche], entry_net: float,
                   contracts: int, structure: str,
                   prices: PriceSource | None = None) -> Trade | None:
    """A frozen-harness `Trade` for the campaign synthetic, or None.

    `f4_synth_trade` with the plan's two decisions applied:

      * THE LEG STRING CARRIES THE CORE LEGS ONLY, for f4_synth_trade's reason:
        `Trade` rebuilds the path window from the leg string's NEAREST expiry, so
        handing it a tranche would truncate the core's life to the tranche's — the
        opposite of a rolled campaign, in which the core keeps running between
        tranches. The tranches live where the harness actually reads value: the
        marks. Nothing downstream reads `t.legs` for this study — `_defined_risk_bounds`
        and `_max_loss_per_unit` are called on the caller's own full leg list, and no
        exit profile used here sets `und_buffer`, the only harness rule that touches
        `t.short_legs`.
      * `entry_net` IS THE CORE DEBIT, not F4's credit-folded net, so ΔR is
        like-for-like across trigger arms. It is passed in rather than derived: the
        marks and the denominator have to be one simulation, not two.

    `contracts` is likewise passed in — the baseline core's production count, at
    which the harness's absolute dollar_stop lands where the baseline's did.
    """
    base: Trade = core_rec["t"]
    if not entry_net or abs(entry_net) <= 1e-9:
        return None
    source = prices if prices is not None else CachePrices()
    marks = campaign_net_marks(base.legs, tranches, base.grid, source,
                               credit_received=True)
    if all(m is None for m in marks):
        return None
    leg_str = "\n".join(
        f"{lg.ticker}:{lg.expiration.isoformat()}:{lg.strike:g}:"
        f"{'C' if lg.opt_type == CALL else 'P'} {lg.qty:+d}" for lg in base.legs)
    row = {
        "signal_date": base.signal_date.isoformat(),
        "ticker": base.ticker,
        "structure": structure,
        "entry_option_price": f"{entry_net:.4f}",
        "contracts": str(contracts),
        "dte_entry": str(base.dte_entry),
        "legs": leg_str,
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
    }
    try:
        return Trade(row)
    except (AssertionError, ValueError, KeyError):
        return None


# ── transaction costs ────────────────────────────────────────────────────────

def _quote_day(leg: Leg, day: date | None) -> date | None:
    """The last day at or before `day` (and the leg's expiry) that the leg quoted."""
    if day is None:
        return None
    limit = min(day, leg.expiration)
    rows = BR.leg_details(leg)
    earlier = [d for d in rows if d <= limit]
    return max(earlier) if earlier else None


def costs_of(tranches: Sequence[Tranche], contracts: int,
             commission_per_contract: float, slippage_frac_of_spread: float,
             prices: PriceSource) -> CampaignCosts:
    """The campaign's round-trip transaction cost in DOLLARS.

    `simulate._apply_costs`' model, per TRANCHE instead of per position:

        commission = commission_per_contract x |leg.qty| x contracts, ONCE PER SIDE
        slippage   = slippage_frac_of_spread x |leg.qty| x spread x 100 x contracts,
                     once per side, always adverse

    EVERY OPEN AND EVERY CLOSE IS CHARGED — a rolled campaign's cost is the whole
    point of asking whether rolling pays, and charging one round trip for four
    tranches would understate it fourfold. A tranche left `open_at_grid_end` is
    charged ONE side, because that is all it traded.

    A side with no two-sided quote is charged NO slippage and says so in `basis`,
    never a guessed spread — the production rule. A `ModelPrices` source has no
    quotes at all, so a model-tier campaign is commission-only by construction and
    its basis records it.
    """
    contracts = max(1, int(contracts))
    commission = 0.0
    slippage = 0.0
    opens = closes = 0
    missing_open = missing_close = 0

    for tranche in tranches:
        units = abs(tranche.leg.qty) * contracts
        opens += 1
        commission += commission_per_contract * units
        if slippage_frac_of_spread:
            spread = prices.spread(tranche.leg, tranche.open_day)
            if spread is None:
                missing_open += 1
            else:
                slippage += slippage_frac_of_spread * abs(tranche.leg.qty) * spread \
                    * 100 * contracts
        if tranche.closed:
            closes += 1
            commission += commission_per_contract * units
            if slippage_frac_of_spread:
                quote_day = _quote_day(tranche.leg, tranche.close_day)
                spread = prices.spread(tranche.leg, quote_day) if quote_day else None
                if spread is None:
                    missing_close += 1
                else:
                    slippage += slippage_frac_of_spread * abs(tranche.leg.qty) * spread \
                        * 100 * contracts

    if not commission_per_contract and not slippage_frac_of_spread:
        basis = ""
    elif not slippage_frac_of_spread:
        basis = "commission_only"
    elif not (missing_open or missing_close):
        basis = "full"
    else:
        parts = ([f"open{missing_open}"] if missing_open else []) + \
                ([f"close{missing_close}"] if missing_close else [])
        basis = "no_spread_" + "_".join(parts)

    return CampaignCosts(commission=round(commission, 2), slippage=round(slippage, 2),
                         total=round(commission + slippage, 2), opens=opens,
                         closes=closes, basis=basis)


def gross_vs_net(gross_dollars: float, costs: CampaignCosts) -> tuple[float, float]:
    """`(gross, net)` — the pair the report prints side by side, never one alone."""
    return gross_dollars, costs.net(gross_dollars)


# ── gate G1b: the F4 identity ────────────────────────────────────────────────

F4_IDENTITY_TARGET = 0.20


def f4_identity(core_rec: dict, prices: PriceSource | None = None, *,
                expiries: Sequence[date] | None = None, bars: dict | None = None,
                target: float = F4_IDENTITY_TARGET, detail: bool = False):
    """The T0 / R0 / BHOLD campaign's net-mark series — gate G1b's left-hand side.

    G1b proves this simulator is a SUPERSET of `financed_spread` ARM F4 rather than
    a different engine that happens to agree: the series returned here must equal
    `financed_spread.f4_net_marks(base_legs, short_leg, grid, buyback)` for the
    F4-d20 `hold` cell to $0.01 a day on every shared row. Every piece is shared by
    construction — the same expiry window, the same 4 cached candidates, the same
    delta pick and IV-sentinel rule, the same "close at the last real mark on the
    first grid day after the near expiry", and the same two-segment clamp.

    `detail=True` returns `(marks, tranches, census)` instead of just `marks`, which
    is how the study reports WHY a row diverged. There is exactly one construction
    under which the two can legitimately disagree: a tranche that was BREACHED and
    whose last real mark is more than SETTLE_STALE_SESSIONS sessions before expiry
    settles at INTRINSIC here and at the stale mark in F4, which has no breach
    concept. Those rows carry `settle_intrinsic` in the census and must be reported,
    not averaged in. Passing `bars={}` reproduces the exact F4 construction (no bar,
    no breach, always `settle_mark`) and is the right call only for a diagnostic.
    """
    base: Trade = core_rec["t"]
    core = _lt().core_of(core_rec)
    if core is None:
        return (None, [], Counter({"skip_not_a_core": 1})) if detail else None

    source = prices if prices is not None else CachePrices()
    if expiries is None:
        expiries = FS.cached_ticker_expiries(core.ticker)
    if bars is None:
        bars = UL.load_bars(core.ticker)

    spec = CampaignSpec(trigger=T0, roll=R0, breach=BHOLD, target=target, opt_type=CALL)
    tranches, census = run_campaign(core, spec, source, bars, list(expiries),
                                    unit=core_unit(core_rec))
    marks = campaign_net_marks(base.legs, tranches, base.grid, source)
    return (marks, tranches, census) if detail else marks
