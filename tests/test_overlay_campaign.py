"""Unit tests for the roll-capable overlay engine,
`scripts/backtest_study/lib/overlay_campaign.py`.

The `ladder_overlay` registration turns `financed_spread` ARM F4's single
entry-day short leg into a CAMPAIGN: sold on a trigger, rolled after it settles,
managed through a breach policy. What is pinned here is everything a report cannot
show you — the schedule (which trigger day fires into which empty slot, and which
grid day the sale lands on), the settlement rule, the multi-tranche net-mark
algebra and its continuity at every roll boundary, the MODEL tier's refusal to
price off a zero-vol sentinel, and gate G1b: that the T0/R0/BHOLD cell reproduces
`financed_spread.f4_net_marks` exactly.

Everything is synthetic — a fake per-contract cache injected over
`bear_rewrap.leg_details` (the `tests/test_financed_spread_f4.py` pattern), fake
OHLC bars, and a stub for `scripts/backtest_study/lib/ladder_targets.py`, which is the ONE
owner of the target set and is imported through the `_LT` seam. No network, no real
option history, no `backtests/` reads.
"""
from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from scripts.backtest.legs import Leg
from scripts.backtest_study.f3_structure import bear_rewrap as BR
from scripts.backtest_study.f3_structure import financed_spread as FS
from scripts.backtest_study.lib import greeks as GK
from scripts.backtest_study.lib import overlay_campaign as OC
from scripts.backtest_study.lib.underlying import Bar

TK = "AAA"
FAR = date(2024, 9, 20)       # the core's expiry
NEAR = date(2024, 7, 19)      # the first tranche's expiry
NEAR2 = date(2024, 8, 16)     # the roll's expiry
NEAR_B = date(2024, 7, 26)    # the BUP roll-out's expiry (one week beyond NEAR)
ENTRY = date(2024, 6, 3)

CORE = [Leg(1, TK, FAR, 100.0, "Call"), Leg(-1, TK, FAR, 110.0, "Call")]


# ── fixtures ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FakeCore:
    """Duck-typed stand-in for `ladder_targets.CoreSpec` (which module 1 owns)."""

    ticker: str
    expiry: date
    lo: float
    hi: float
    entry_day: date
    grid: tuple
    spot_entry: float | None = None


def _rows(marks: dict, iv="30.0", bid=None, ask=None):
    """`{date: row}` in `parse_history_details`' shape. `Open` is 0 so
    `entry_price_of` falls through to the mark and the arithmetic stays readable."""
    out = {}
    for d, m in marks.items():
        row = {"_mark": m, "Open": "0", "IV": iv}
        if bid is not None:
            row["Bid"], row["Ask"] = str(bid), str(ask)
        out[d] = row
    return out


@pytest.fixture()
def cache(monkeypatch):
    """A per-leg fake option cache keyed by contract identity."""
    store: dict[tuple, dict] = {}

    def put(leg, marks, iv="30.0", bid=None, ask=None):
        store[(leg.ticker, leg.expiration, leg.strike, leg.opt_type)] = \
            _rows(marks, iv, bid, ask)

    def leg_details(leg):
        return store.get((leg.ticker, leg.expiration, leg.strike, leg.opt_type), {})

    monkeypatch.setattr(BR, "leg_details", leg_details)
    put.store = store
    return put


class FakeLadderTargets:
    """The two `ladder_targets` entry points the engine actually calls.

    `eligible_expiries` reproduces the contract's window (and therefore
    `financed_spread.near_expiry_for`'s) so a test exercises the real geometry
    rather than a hand-picked answer.
    """

    def __init__(self, strikes=(115.0, 120.0, 125.0), puts=None):
        self.strikes = list(strikes)
        self.puts = list(puts or [])

    def eligible_expiries(self, day, remaining_dte, expiries):
        lo = day + timedelta(days=FS.DIAG_MIN_DAYS)
        hi = day + timedelta(days=int(remaining_dte * FS.DIAG_MAX_DTE_FRAC))
        return sorted(e for e in expiries if lo <= e <= hi)

    def cached_strikes(self, ticker, expiry, opt_type):
        return list(self.puts) if opt_type == "Put" else list(self.strikes)

    def core_of(self, rec):
        return rec.get("_core")


@pytest.fixture()
def ladder(monkeypatch):
    stub = FakeLadderTargets()
    monkeypatch.setattr(OC, "_LT", stub)
    return stub


@pytest.fixture()
def deltas(monkeypatch):
    """Per-strike per-contract |Delta|, signed short the way `leg_greek` returns it."""
    table = {115.0: 0.34, 120.0: 0.21, 125.0: 0.08}

    def leg_greek(leg, day, name):
        if leg.strike not in table:
            return None
        return -table[leg.strike] * abs(leg.qty)

    monkeypatch.setattr(GK, "leg_greek", leg_greek)
    return table


def _days(n, start=ENTRY):
    return [start + timedelta(days=i) for i in range(n)]


def _bars(closes: dict, opens: dict | None = None):
    return {d: Bar(c=c, o=(opens or {}).get(d)) for d, c in closes.items()}


def _core(grid, entry_day=None, expiry=FAR, spot_entry=None):
    return FakeCore(ticker=TK, expiry=expiry, lo=100.0, hi=110.0,
                    entry_day=entry_day or grid[0], grid=tuple(grid),
                    spot_entry=spot_entry)


def _flat_core(cache, grid, values):
    """Price the core legs so their NET is `values[i]`: the long leg carries the
    whole net, the short leg is worth 0."""
    cache(CORE[0], dict(zip(grid, values)))
    cache(CORE[1], {d: 0.0 for d in grid})


# ── triggers ─────────────────────────────────────────────────────────────────

def test_tnever_never_fires_and_t0_fires_once_at_entry():
    grid = _days(5)
    core = _core(grid)
    assert OC.trigger_days(core, OC.CampaignSpec(trigger=OC.TNEVER), {}, grid[0]) == []
    assert OC.trigger_days(core, OC.CampaignSpec(trigger=OC.T0), {}, grid[0]) == [grid[0]]


def test_tgap_fires_only_when_the_open_gaps_through_the_threshold():
    grid = _days(4)
    closes = {grid[0]: 100.0, grid[1]: 100.0, grid[2]: 100.0, grid[3]: 100.0}
    opens = {grid[1]: 101.4,        # +1.4% — under the 1.5% bar
             grid[2]: 101.5,        # +1.5% — exactly at it, fires
             grid[3]: 105.0}        # well through it
    got = OC.trigger_days(_core(grid), OC.CampaignSpec(trigger=OC.TGAP),
                          _bars(closes, opens), grid[0])
    assert got == [grid[2], grid[3]]


def test_tgap_never_invents_an_open_on_the_close_only_fallback_path():
    """The `Price~` fallback series has no open. A day with no open does not
    qualify — it is never filled in from the neighbouring session."""
    grid = _days(3)
    closes = {grid[0]: 100.0, grid[1]: 100.0, grid[2]: 100.0}
    assert OC.trigger_days(_core(grid), OC.CampaignSpec(trigger=OC.TGAP),
                           _bars(closes), grid[0]) == []


def test_trun_needs_both_the_level_and_three_strictly_rising_closes():
    grid = _days(6)
    # day 3 is +4.2% on entry but the run is not strictly rising (day2 == day1)
    # day 5 is +5.0% and days 3,4,5 rise strictly.
    closes = dict(zip(grid, [100.0, 101.0, 101.0, 104.2, 104.5, 105.0]))
    got = OC.trigger_days(_core(grid), OC.CampaignSpec(trigger=OC.TRUN),
                          _bars(closes), grid[0])
    assert got == [grid[4], grid[5]]


def test_trun_does_not_fire_below_the_level_however_long_the_run():
    grid = _days(5)
    closes = dict(zip(grid, [100.0, 100.5, 101.0, 101.5, 102.0]))
    assert OC.trigger_days(_core(grid), OC.CampaignSpec(trigger=OC.TRUN),
                           _bars(closes), grid[0]) == []


# ── selling one tranche ──────────────────────────────────────────────────────

def test_the_pick_is_the_candidate_closest_to_the_delta_target(cache, ladder, deltas):
    grid = _days(6)
    for k in (115.0, 120.0, 125.0):
        cache(Leg(-1, TK, NEAR, k, "Call"), {grid[0]: 1.0})
    tranche, why = OC.sell_tranche(_core(grid), grid[0], OC.CampaignSpec(target=0.20),
                                   OC.CachePrices(), [NEAR])
    assert why == "ok"
    assert tranche.leg.strike == 120.0 and tranche.open_day == grid[0]
    assert tranche.credit == pytest.approx(1.0)


def test_a_candidate_that_never_printed_is_skipped_and_the_open_day_is_never_carried(
        cache, ladder, deltas):
    """`120C` only prints on grid day 2, so that — not the sale day — is when it
    can be sold. A carried quote is not a fill."""
    grid = _days(6)
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {grid[2]: 0.90})
    tranche, why = OC.sell_tranche(_core(grid), grid[0], OC.CampaignSpec(target=0.20),
                                   OC.CachePrices(), [NEAR])
    assert why == "ok" and tranche.open_day == grid[2]


def test_a_zero_filled_greek_row_is_counted_absent_not_read_as_zero_delta(
        cache, ladder, monkeypatch):
    """Barchart writes IV/Delta/... all literally 0 on a real-priced session. Read
    literally, a deep-ITM contract lands inside the 0.20 tolerance and gets sold as
    financing. A missing greek is None, never 0.0."""
    grid = _days(4)
    for k in (115.0, 120.0, 125.0):
        cache(Leg(-1, TK, NEAR, k, "Call"), {grid[0]: 40.0}, iv="0")
    monkeypatch.setattr(GK, "leg_greek", lambda leg, day, name: 0.0)
    tranche, why = OC.sell_tranche(_core(grid), grid[0], OC.CampaignSpec(target=0.20),
                                   OC.CachePrices(), [NEAR])
    assert tranche is None and why == OC.SKIP_GREEKS_ABSENT


def test_an_unreachable_target_is_excluded_and_counted(cache, ladder, deltas):
    grid = _days(4)
    cache(Leg(-1, TK, NEAR, 115.0, "Call"), {grid[0]: 3.0})
    ladder.strikes = [115.0]              # |Delta| 0.34 vs a 0.20 target: gap 0.14 > 0.10
    tranche, why = OC.sell_tranche(_core(grid), grid[0], OC.CampaignSpec(target=0.20),
                                   OC.CachePrices(), [NEAR])
    assert tranche is None and why == OC.SKIP_TARGET_UNREACHABLE


def test_no_expiry_in_the_window_is_the_f4_census_key(cache, ladder, deltas):
    grid = _days(4)
    tranche, why = OC.sell_tranche(_core(grid), grid[0], OC.CampaignSpec(),
                                   OC.CachePrices(), [FAR])   # past the half-DTE bound
    assert tranche is None and why == OC.SKIP_NO_NEAR_EXPIRY


def test_calls_hang_off_the_core_hi_strike_and_puts_off_the_days_spot(
        cache, ladder, monkeypatch):
    grid = _days(4)
    ladder.strikes = [105.0, 115.0]       # 105 is BELOW the core's hi: not a candidate
    ladder.puts = [80.0, 95.0, 130.0]     # 130 is above spot: not a candidate
    for k in (105.0, 115.0):
        cache(Leg(-1, TK, NEAR, k, "Call"), {grid[0]: 1.0})
    for k in (80.0, 95.0, 130.0):
        cache(Leg(-1, TK, NEAR, k, "Put"), {grid[0]: 1.0})
    monkeypatch.setattr(GK, "leg_greek", lambda leg, day, name: -0.20 * abs(leg.qty))

    call, _ = OC.sell_tranche(_core(grid), grid[0], OC.CampaignSpec(opt_type="Call"),
                              OC.CachePrices(), [NEAR])
    assert call.leg.strike == 115.0
    put, _ = OC.sell_tranche(_core(grid), grid[0], OC.CampaignSpec(opt_type="Put"),
                             OC.CachePrices(), [NEAR], spot=100.0)
    assert put.leg.strike == 95.0         # nearest strictly below spot


def test_the_put_arm_refuses_rather_than_guessing_a_spot(cache, ladder, deltas):
    grid = _days(4)
    ladder.puts = [95.0]
    tranche, why = OC.sell_tranche(_core(grid), grid[0], OC.CampaignSpec(opt_type="Put"),
                                   OC.CachePrices(), [NEAR])
    assert tranche is None and why == OC.SKIP_NO_SPOT


# ── the campaign walk: roll mechanics ────────────────────────────────────────

def _two_expiry_cache(cache, grid, near_marks, near2_marks):
    _flat_core(cache, grid, [3.0] * len(grid))
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), near_marks)
    cache(Leg(-1, TK, NEAR2, 120.0, "Call"), near2_marks)


def test_r0_sells_exactly_once_even_when_the_slot_reopens(cache, ladder, deltas):
    grid = [ENTRY + timedelta(days=i) for i in range(0, 90)]
    _two_expiry_cache(cache, grid,
                      {d: 1.0 for d in grid if d <= NEAR},
                      {d: 1.0 for d in grid if d <= NEAR2})
    tranches, census = OC.run_campaign(
        _core(grid), OC.CampaignSpec(trigger=OC.T0, roll=OC.R0), OC.CachePrices(),
        {}, [NEAR, NEAR2])
    assert len(tranches) == 1
    assert tranches[0].close_reason == OC.SETTLE_MARK
    assert census["tranche_opened"] == 1


def test_r1_opens_the_next_tranche_on_the_first_grid_day_after_the_expiry(
        cache, ladder, deltas):
    grid = [ENTRY + timedelta(days=i) for i in range(0, 90)]
    _two_expiry_cache(cache, grid,
                      {d: 1.0 for d in grid if d <= NEAR},
                      {d: 0.9 for d in grid if d <= NEAR2})
    tranches, census = OC.run_campaign(
        _core(grid), OC.CampaignSpec(trigger=OC.T0, roll=OC.R1), OC.CachePrices(),
        {}, [NEAR, NEAR2])
    first_after_near = next(d for d in grid if d > NEAR)
    assert len(tranches) == 2
    assert tranches[0].close_day == first_after_near
    assert tranches[1].open_day == first_after_near
    assert tranches[1].leg.expiration == NEAR2
    assert census["tranche_opened"] == 2


def test_no_tranche_opens_past_the_end_of_the_grid(cache, ladder, deltas):
    """The core's path window is what bounds the campaign: once the last eligible
    expiry has settled there is nothing left to sell, and the census says so."""
    grid = [ENTRY + timedelta(days=i) for i in range(0, 90)]
    _two_expiry_cache(cache, grid,
                      {d: 1.0 for d in grid if d <= NEAR},
                      {d: 0.9 for d in grid if d <= NEAR2})
    tranches, census = OC.run_campaign(
        _core(grid), OC.CampaignSpec(trigger=OC.T0, roll=OC.R1), OC.CachePrices(),
        {}, [NEAR, NEAR2])
    assert len(tranches) == 2
    assert census[OC.SKIP_NO_NEAR_EXPIRY] >= 1
    assert all(t.open_day <= grid[-1] for t in tranches)


def test_a_gap_trigger_sells_on_the_next_grid_day(cache, ladder, deltas):
    grid = _days(30)
    _flat_core(cache, grid, [3.0] * len(grid))
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {d: 1.0 for d in grid})
    closes = {d: 100.0 for d in grid}
    opens = {grid[4]: 103.0}
    tranches, _ = OC.run_campaign(
        _core(grid), OC.CampaignSpec(trigger=OC.TGAP, roll=OC.R1), OC.CachePrices(),
        _bars(closes, opens), [NEAR])
    assert len(tranches) == 1
    assert tranches[0].open_day == grid[5]


def test_a_trigger_that_fires_while_a_tranche_is_live_is_lost_not_queued(
        cache, ladder, deltas):
    """One tranche per EMPTY slot. Two gaps three days apart open ONE tranche."""
    grid = _days(30)
    _flat_core(cache, grid, [3.0] * len(grid))
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {d: 1.0 for d in grid})
    closes = {d: 100.0 for d in grid}
    opens = {grid[4]: 103.0, grid[7]: 103.0}
    tranches, _ = OC.run_campaign(
        _core(grid), OC.CampaignSpec(trigger=OC.TGAP, roll=OC.R1), OC.CachePrices(),
        _bars(closes, opens), [NEAR])
    assert len(tranches) == 1 and tranches[0].open_day == grid[5]


# ── breach detection and the three policies ──────────────────────────────────

def _breach_setup(cache, ladder):
    """A core whose 120 short strike is breached on grid day 3 and stays breached."""
    grid = _days(60)
    _flat_core(cache, grid, [3.0] * len(grid))
    cache(Leg(-1, TK, NEAR, 120.0, "Call"),
          {d: 1.0 + 0.1 * i for i, d in enumerate(grid) if d <= NEAR})
    cache(Leg(-1, TK, NEAR_B, 120.0, "Call"), {d: 0.5 for d in grid if d <= NEAR_B})
    closes = {d: 100.0 for d in grid}
    for d in grid[3:]:
        closes[d] = 121.0                   # closes THROUGH the 120 short strike
    return grid, _bars(closes)


def test_bhold_records_the_breach_and_changes_nothing(cache, ladder, deltas):
    grid, bars = _breach_setup(cache, ladder)
    tranches, census = OC.run_campaign(
        _core(grid), OC.CampaignSpec(trigger=OC.T0, roll=OC.R0, breach=OC.BHOLD),
        OC.CachePrices(), bars, [NEAR, NEAR_B])
    assert len(tranches) == 1
    assert tranches[0].breached is True
    assert tranches[0].close_reason == OC.SETTLE_MARK
    assert census["breached"] == 1


def test_bbuy_buys_the_leg_back_at_that_days_mark(cache, ladder, deltas):
    grid, bars = _breach_setup(cache, ladder)
    tranches, _ = OC.run_campaign(
        _core(grid), OC.CampaignSpec(trigger=OC.T0, roll=OC.R0, breach=OC.BBUY),
        OC.CachePrices(), bars, [NEAR, NEAR_B])
    assert len(tranches) == 1
    assert tranches[0].close_day == grid[3]
    assert tranches[0].close_reason == OC.BREACH_BUYBACK
    assert tranches[0].close_cost == pytest.approx(1.0 + 0.1 * 3)


def test_bup_buys_back_and_re_sells_the_next_expiry_out_on_the_next_grid_day(
        cache, ladder, deltas):
    grid, bars = _breach_setup(cache, ladder)
    tranches, _ = OC.run_campaign(
        _core(grid), OC.CampaignSpec(trigger=OC.T0, roll=OC.R0, breach=OC.BUP),
        OC.CachePrices(), bars, [NEAR, NEAR_B])
    assert len(tranches) == 2
    assert tranches[0].close_day == grid[3] and tranches[0].close_reason == OC.BREACH_BUYBACK
    assert tranches[1].open_day == grid[4]
    assert tranches[1].leg.expiration == NEAR_B   # strictly beyond the breached expiry


# ── settlement ───────────────────────────────────────────────────────────────

def test_settlement_defaults_to_the_last_real_mark_on_the_first_day_after_expiry(
        cache, ladder, deltas):
    grid = [ENTRY + timedelta(days=i) for i in range(0, 60)]
    _flat_core(cache, grid, [3.0] * len(grid))
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {d: 0.3 for d in grid if d <= NEAR})
    tranches, _ = OC.run_campaign(_core(grid), OC.CampaignSpec(), OC.CachePrices(),
                                  {}, [NEAR])
    assert tranches[0].close_day == next(d for d in grid if d > NEAR)
    assert tranches[0].close_reason == OC.SETTLE_MARK
    assert tranches[0].close_cost == pytest.approx(0.3)


def test_a_stale_mark_alone_still_settles_at_the_mark(cache, ladder, deltas):
    """An unbreached short that stopped printing is a quiet contract, not a hidden
    loss: intrinsic is NEVER paid on it."""
    grid = [ENTRY + timedelta(days=i) for i in range(0, 60)]
    _flat_core(cache, grid, [3.0] * len(grid))
    stale = [d for d in grid if d <= NEAR - timedelta(days=10)]
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {d: 0.3 for d in stale})
    closes = {d: 100.0 for d in grid}      # never through the strike
    tranches, census = OC.run_campaign(_core(grid), OC.CampaignSpec(), OC.CachePrices(),
                                       _bars(closes), [NEAR])
    assert tranches[0].close_reason == OC.SETTLE_MARK
    assert census[OC.SETTLE_INTRINSIC] == 0


def test_a_breached_tranche_with_no_recent_mark_settles_at_intrinsic(
        cache, ladder, deltas):
    grid = [ENTRY + timedelta(days=i) for i in range(0, 60)]
    _flat_core(cache, grid, [3.0] * len(grid))
    stale = [d for d in grid if d <= NEAR - timedelta(days=10)]
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {d: 0.3 for d in stale})
    closes = {d: 100.0 for d in grid}
    for d in grid:
        if d > NEAR - timedelta(days=5):
            closes[d] = 131.0              # through the 120 strike, and stays there
    tranches, census = OC.run_campaign(_core(grid), OC.CampaignSpec(), OC.CachePrices(),
                                       _bars(closes), [NEAR])
    assert tranches[0].breached is True
    assert tranches[0].close_reason == OC.SETTLE_INTRINSIC
    assert tranches[0].close_cost == pytest.approx(11.0)   # 131 - 120
    assert census[OC.SETTLE_INTRINSIC] == 1


def test_an_expiry_past_the_end_of_the_grid_leaves_the_tranche_open(
        cache, ladder, deltas):
    grid = _days(20)                       # ends long before NEAR
    _flat_core(cache, grid, [3.0] * len(grid))
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {d: 1.0 for d in grid})
    tranches, census = OC.run_campaign(_core(grid), OC.CampaignSpec(), OC.CachePrices(),
                                       {}, [NEAR])
    assert len(tranches) == 1
    assert tranches[0].close_day is None
    assert tranches[0].close_reason == OC.OPEN_AT_GRID_END
    assert census[OC.OPEN_AT_GRID_END] == 1


# ── the net-mark algebra ─────────────────────────────────────────────────────

def _tranche(strike, expiry, open_day, credit, close_day=None, close_cost=None,
             reason=None, breached=False):
    return OC.Tranche(leg=Leg(-1, TK, expiry, strike, "Call"), open_day=open_day,
                      credit=credit, close_day=close_day, close_cost=close_cost,
                      close_reason=reason, breached=breached)


def test_the_worked_example_in_the_docstring_executes(cache):
    """`campaign_net_marks`' hand-worked roll, day for day."""
    grid = _days(6)
    _flat_core(cache, grid, [3.00, 3.10, 3.30, 3.40, 3.50, 3.60])
    cache(Leg(-1, TK, NEAR, 120.0, "Call"),
          {grid[1]: 0.80, grid[2]: 0.45, grid[3]: 0.30})
    cache(Leg(-1, TK, NEAR2, 120.0, "Call"), {grid[4]: 0.60, grid[5]: 0.20})
    tranches = [
        _tranche(120.0, NEAR, grid[1], 0.80, close_day=grid[3], close_cost=0.30,
                 reason=OC.SETTLE_MARK),
        _tranche(120.0, NEAR2, grid[4], 0.60),
    ]
    marks = OC.campaign_net_marks(CORE, tranches, grid, OC.CachePrices())
    assert marks == pytest.approx([3.00, 2.30, 2.85, 3.10, 2.60, 3.10])


def test_the_series_is_continuous_at_every_close(cache):
    """Mark-in and cost-out are the SAME number on the day a tranche closes, so
    closing adds no step — it only stops the leg from moving afterwards."""
    grid = _days(6)
    _flat_core(cache, grid, [3.0] * 6)
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), dict(zip(grid, [0.8, 0.7, 0.6, 0.5, 0.4, 0.3])))
    held = OC.campaign_net_marks(CORE, [_tranche(120.0, NEAR, grid[0], 0.8)],
                                 grid, OC.CachePrices())
    for i in range(1, 6):
        closed = OC.campaign_net_marks(
            CORE, [_tranche(120.0, NEAR, grid[0], 0.8, close_day=grid[i],
                            close_cost=0.8 - 0.1 * i, reason=OC.SETTLE_MARK)],
            grid, OC.CachePrices())
        assert closed[i] == pytest.approx(held[i]), f"step at close day {i}"


def test_the_clamp_applies_only_on_days_with_no_live_tranche(cache):
    """`_defined_risk_bounds` is a single-expiration function. While a naked short
    at another expiry lives there IS no bound; once it is closed the core is a plain
    vertical again and the realized cost sits OUTSIDE the clamp, being cash."""
    grid = _days(3)
    _flat_core(cache, grid, [3.0, -1.0, -1.0])       # a negative net vertical mark
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), dict(zip(grid, [0.80, 0.10, 0.10])))
    marks = OC.campaign_net_marks(
        CORE, [_tranche(120.0, NEAR, grid[0], 0.80, close_day=grid[2], close_cost=0.10,
                        reason=OC.SETTLE_MARK)],
        grid, OC.CachePrices())
    assert marks[1] == pytest.approx(-1.10)          # live: unclamped
    assert marks[2] == pytest.approx(0.0 - 0.10)     # closed: core clamped to [0,10], then cost


def test_a_live_tranche_that_cannot_be_marked_makes_the_day_none(cache):
    """A short leg the market stopped quoting is not a short leg worth zero."""
    grid = _days(3)
    _flat_core(cache, grid, [3.0, 3.0, 3.0])
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {})      # never priced
    marks = OC.campaign_net_marks(CORE, [_tranche(120.0, NEAR, grid[0], 0.8)],
                                  grid, OC.CachePrices())
    assert marks == [None, None, None]


def test_a_tranche_contributes_nothing_before_it_is_sold(cache):
    grid = _days(3)
    _flat_core(cache, grid, [3.0, 3.0, 3.0])
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {grid[1]: 0.5, grid[2]: 0.4})
    marks = OC.campaign_net_marks(CORE, [_tranche(120.0, NEAR, grid[1], 0.5)],
                                  grid, OC.CachePrices())
    assert marks == pytest.approx([3.0, 2.5, 2.6])


# ── the synthetic trade ──────────────────────────────────────────────────────

def _book_trade():
    """A frozen-harness `Trade` for the core, priced flat at its 3.00 debit."""
    from scripts.backtest_study.lib.harness import Trade
    from scripts.backtest.helpers import _weekday_grid
    grid = _weekday_grid(ENTRY, FAR)
    row = {
        "signal_date": ENTRY.isoformat(), "ticker": TK,
        "structure": "bull_call_spread", "entry_option_price": "3.0000",
        "contracts": "2", "dte_entry": str((FAR - ENTRY).days),
        "legs": f"{TK}:{FAR.isoformat()}:100:C +1\n{TK}:{FAR.isoformat()}:110:C -1",
        "daily_price_csv": ",".join(["3.0000"] * len(grid)),
    }
    return Trade(row)


def test_the_synthetic_carries_the_core_legs_only_and_the_core_debit(cache):
    base = _book_trade()
    grid = list(base.grid)
    _flat_core(cache, grid, [3.0] * len(grid))
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {d: 0.5 for d in grid if d <= NEAR})
    tranches = [_tranche(120.0, NEAR, grid[0], 0.5)]
    trade = OC.campaign_trade({"t": base}, tranches, 3.0, 2, "ladder_bull_call")
    assert trade is not None
    assert {lg.expiration for lg in trade.legs} == {FAR}      # no tranche in the leg string
    assert trade.entry_net == pytest.approx(3.0)              # the CORE debit
    assert trade.contracts == 2
    assert len(trade.grid) == len(base.grid)                  # path window not truncated


# ── the MODEL tier ───────────────────────────────────────────────────────────

def test_model_prices_price_off_the_entry_day_iv_held_constant(cache):
    grid = _days(4)
    leg = Leg(-1, TK, NEAR, 120.0, "Call")
    cache(leg, {grid[0]: 1.0, grid[1]: 1.0}, iv="40.0")
    bars = _bars({d: 100.0 for d in grid})
    mp = OC.ModelPrices(1.0, bars)
    mp.register(leg, grid[0])
    assert mp.sigma_of(leg) == pytest.approx(0.40)
    assert OC.ModelPrices(0.75, bars, {(TK, NEAR, 120.0, "Call"): grid[0]}).sigma_of(leg) \
        == pytest.approx(0.30)
    price = mp.mark(leg, grid[0])
    assert price is not None and price > 0
    # a lower sigma is a cheaper OTM call, on the same spot and the same day
    cheap = OC.ModelPrices(0.75, bars)
    cheap.register(leg, grid[0])
    assert cheap.mark(leg, grid[0]) < price


def test_model_prices_refuse_a_leg_with_no_entry_iv(cache):
    grid = _days(3)
    leg = Leg(-1, TK, NEAR, 120.0, "Call")
    cache(leg, {grid[0]: 1.0}, iv="")
    mp = OC.ModelPrices(1.0, _bars({d: 100.0 for d in grid}))
    mp.register(leg, grid[0])
    assert mp.sigma_of(leg) is None
    assert mp.mark(leg, grid[0]) is None


def test_model_prices_refuse_the_all_zero_greek_sentinel_rather_than_using_sigma_zero(cache):
    """sigma=0 collapses `_bs_price` to intrinsic, so a deep-ITM contract would
    price as if it had no time value. The sentinel is detected on IV, the same test
    `leg_greek` uses."""
    grid = _days(3)
    leg = Leg(-1, TK, NEAR, 90.0, "Call")            # deep ITM against a 100 spot
    cache(leg, {grid[0]: 12.0}, iv="0")
    mp = OC.ModelPrices(1.0, _bars({d: 100.0 for d in grid}))
    mp.register(leg, grid[0])
    assert mp.mark(leg, grid[0]) is None


def test_model_prices_still_read_real_rows_for_the_open_day(cache):
    """A model tier prices; it does not invent liquidity. Whether a contract traded
    is a fact about the data."""
    grid = _days(3)
    leg = Leg(-1, TK, NEAR, 120.0, "Call")
    cache(leg, {grid[1]: 1.0})
    mp = OC.ModelPrices(1.0, _bars({d: 100.0 for d in grid}))
    assert mp.has_real_row(leg, grid[0]) is False
    assert mp.has_real_row(leg, grid[1]) is True


def test_the_two_tiers_are_labelled_and_assert_not_model_refuses_a_leak():
    assert OC.CachePrices().tier == OC.CACHE_TIER
    assert OC.ModelPrices(1.0, {}).tier == OC.MODEL_TIER
    evidence = [{"cell": "L-T0", "tier": OC.CACHE_TIER}]
    assert OC.assert_not_model(evidence) == evidence
    with pytest.raises(OC.ModelTierLeak):
        OC.assert_not_model(evidence + [{"cell": "L-T0", "tier": OC.MODEL_TIER}])


def test_assert_not_model_refuses_an_untagged_row_by_default():
    with pytest.raises(OC.ModelTierLeak):
        OC.assert_not_model([{"cell": "L-T0"}])
    assert OC.assert_not_model([{"cell": "L-T0"}], require_tier=False) == [{"cell": "L-T0"}]


# ── transaction costs ────────────────────────────────────────────────────────

def test_commission_is_charged_on_every_open_and_every_close(cache):
    grid = _days(6)
    closed = _tranche(120.0, NEAR, grid[0], 0.8, close_day=grid[3], close_cost=0.3,
                      reason=OC.SETTLE_MARK)
    still_open = _tranche(120.0, NEAR2, grid[4], 0.6)
    costs = OC.costs_of([closed, still_open], contracts=3,
                        commission_per_contract=0.65, slippage_frac_of_spread=0.0,
                        prices=OC.CachePrices())
    # two opens + ONE close, 1 unit x 3 contracts each
    assert (costs.opens, costs.closes) == (2, 1)
    assert costs.commission == pytest.approx(0.65 * 3 * 3)
    assert costs.total == pytest.approx(5.85)
    assert costs.basis == "commission_only"


def test_slippage_is_charged_per_side_off_the_quoted_spread(cache):
    grid = _days(6)
    leg = Leg(-1, TK, NEAR, 120.0, "Call")
    cache(leg, {grid[0]: 0.8, grid[3]: 0.3}, bid=0.70, ask=0.90)   # spread 0.20
    tranche = _tranche(120.0, NEAR, grid[0], 0.8, close_day=grid[3], close_cost=0.3,
                       reason=OC.BREACH_BUYBACK)
    costs = OC.costs_of([tranche], contracts=2, commission_per_contract=0.0,
                        slippage_frac_of_spread=0.5, prices=OC.CachePrices())
    assert costs.slippage == pytest.approx(2 * (0.5 * 1 * 0.20 * 100 * 2))
    assert costs.basis == "full"


def test_a_side_with_no_two_sided_quote_is_charged_nothing_and_says_so(cache):
    grid = _days(6)
    cache(Leg(-1, TK, NEAR, 120.0, "Call"), {grid[0]: 0.8})         # no Bid/Ask
    tranche = _tranche(120.0, NEAR, grid[0], 0.8, close_day=grid[3], close_cost=0.3,
                       reason=OC.BREACH_BUYBACK)
    costs = OC.costs_of([tranche], contracts=1, commission_per_contract=0.0,
                        slippage_frac_of_spread=0.5, prices=OC.CachePrices())
    assert costs.slippage == 0.0
    assert costs.basis.startswith("no_spread_")


def test_zero_knobs_charge_nothing_and_gross_equals_net(cache):
    grid = _days(4)
    tranche = _tranche(120.0, NEAR, grid[0], 0.8, close_day=grid[2], close_cost=0.3,
                       reason=OC.SETTLE_MARK)
    costs = OC.costs_of([tranche], 4, 0.0, 0.0, OC.CachePrices())
    assert costs.total == 0.0 and costs.basis == ""
    assert OC.gross_vs_net(1234.0, costs) == (1234.0, 1234.0)
    charged = OC.CampaignCosts(commission=10.0, slippage=5.0, total=15.0, opens=1,
                               closes=1, basis="full")
    assert OC.gross_vs_net(100.0, charged) == (100.0, 85.0)


# ── gate G1b: the F4 identity ────────────────────────────────────────────────

def test_f4_identity_reproduces_financed_spreads_own_series(cache, ladder, deltas,
                                                            monkeypatch):
    """G1b. The T0/R0/BHOLD/d20 campaign IS `financed_spread`'s F4-d20 `hold` cell:
    same expiry window, same 4 cached candidates, same delta pick and IV-sentinel
    rule, same "close at the last real mark on the first grid day after the near
    expiry", same two-segment clamp. If these two series ever disagree, the campaign
    engine is a different simulator and nothing it prints can be read against F4's
    published cells."""
    base = _book_trade()
    grid = list(base.grid)
    core_values = [3.0 + 0.01 * i for i in range(len(grid))]
    _flat_core(cache, grid, core_values)
    for k in (115.0, 120.0, 125.0):
        cache(Leg(-1, TK, NEAR, k, "Call"),
              {d: 1.0 - 0.005 * i for i, d in enumerate(grid) if d <= NEAR})
    monkeypatch.setattr(FS, "cached_ticker_expiries", lambda tk: [NEAR])
    monkeypatch.setattr(FS, "cached_calls", lambda tk, exp: [115.0, 120.0, 125.0])

    rec = {"t": base, "_core": _core(grid, entry_day=grid[0])}

    # --- financed_spread's own F4-d20 hold series -----------------------------
    entry_day = BR.entry_date_for(base.legs, grid)
    plan = FS.f4_row_plan(rec, "bull", entry_day)
    legs, why = FS.build_f4(rec, plan, 0.20, entry_day)
    assert why == "ok"
    short_leg = legs[-1]
    credit = FS.f4_entry_credit(short_leg, entry_day)
    buyback = FS.f4_buyback(short_leg, grid, entry_day, credit, base.contracts, "hold")
    f4_marks = FS.f4_net_marks(base.legs, short_leg, grid, buyback)

    # --- the campaign's ------------------------------------------------------
    marks, tranches, census = OC.f4_identity(rec, OC.CachePrices(), expiries=[NEAR],
                                             bars={}, detail=True)
    assert len(tranches) == 1
    assert tranches[0].leg == short_leg
    assert tranches[0].open_day == entry_day
    assert tranches[0].credit == pytest.approx(credit)
    assert (tranches[0].close_day, tranches[0].close_cost) == (buyback[0], buyback[1])
    assert census[OC.SETTLE_INTRINSIC] == 0

    assert len(marks) == len(f4_marks)
    for i, (a, b) in enumerate(zip(marks, f4_marks)):
        if a is None or b is None:
            assert a is b, f"day {i}: {a!r} vs {b!r}"
        else:
            assert abs(a - b) <= 0.01, f"day {i}: {a} vs {b}"


def test_f4_identity_returns_none_when_the_record_is_not_a_core(ladder):
    assert OC.f4_identity({"t": _book_trade(), "_core": None}) is None
