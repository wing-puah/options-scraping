"""Unit tests for `scripts/backtest_study/lib/ladder_targets.py`.

Covers the pre-registered target-derivation primitives shared by
`fetch_ladder_legs.py` (pre-scrape) and `overlay_campaign.py` (post-scrape,
cached-only expiries): `third_fridays`, `eligible_expiries` (pinned equal to
`financed_spread.near_expiry_for`'s window), `roll_chain`, `target_strikes`,
`ticker_ladder` (pinned equal to `fetch_financing_legs.ticker_ladder` on a
shared fixture), `cached_strikes`, `core_of` and `ladder_targets`.

Everything is synthetic and written to tmp_path; no network, no real cache.
"""
from datetime import date, timedelta

import pytest

from scripts.backtest.legs import Leg
from scripts.backtest_study.f3_structure import bear_rewrap as BR
from scripts.backtest_study.f3_structure import financed_spread as FS
from scripts.backtest_study.lib import ladder_targets as LT
from scripts.backtest_study.lib.underlying import Bar
from scripts.collector import fetch_financing_legs as ffl


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """One option-cache directory shared by `ladder_targets`, `financed_spread`
    (`cached_calls`) and `bear_rewrap` (`cached_puts`, `entry_date_for`'s own
    lookups) — all three import `HISTORY_CACHE` as a separate module-level
    binding, so all three need patching."""
    cache = tmp_path / "opt_cache"
    cache.mkdir()
    monkeypatch.setattr(LT, "HISTORY_CACHE", cache)
    monkeypatch.setattr(FS, "HISTORY_CACHE", cache)
    monkeypatch.setattr(BR, "HISTORY_CACHE", cache)
    yield cache


def _write_contract(cache_dir, ticker, expiry, strike, cp):
    fname = f"{ticker}_{expiry.strftime('%Y%m%d')}_{strike:.2f}{cp}.csv"
    (cache_dir / fname).write_text("Time,Open,High,Low,Latest\n2024-06-03,1,1,1,1\n")


class _FakeTrade:
    def __init__(self, legs, grid, structure="bull_call_spread"):
        self.legs = legs
        self.grid = grid
        self.structure = structure


def _rec(legs, grid, structure="bull_call_spread"):
    return {"t": _FakeTrade(legs, grid, structure)}


E0 = date(2024, 6, 3)     # entry day used throughout
CORE_EXP = date(2024, 8, 16)


def _bull_legs(ticker="AAA", exp=CORE_EXP, lo=100.0, hi=110.0):
    return [Leg(1, ticker, exp, lo, "Call"), Leg(-1, ticker, exp, hi, "Call")]


def _grid(n=60, start=E0):
    return [start + timedelta(days=i) for i in range(n)]


# --- third_fridays -----------------------------------------------------------

def test_third_fridays_known_month():
    # 2024-06: Fridays are 6/7, 6/14, 6/21, 6/28 -> third is 6/21
    out = LT.third_fridays(date(2024, 6, 1), date(2024, 6, 30))
    assert out == [date(2024, 6, 21)]


def test_third_fridays_spans_multiple_months():
    # June third Friday 6/21, July third Friday 7/19
    out = LT.third_fridays(date(2024, 6, 1), date(2024, 7, 31))
    assert out == [date(2024, 6, 21), date(2024, 7, 19)]


def test_third_fridays_excludes_a_third_friday_outside_the_range():
    # range ends BEFORE June's third Friday
    out = LT.third_fridays(date(2024, 6, 1), date(2024, 6, 20))
    assert out == []


def test_third_fridays_inclusive_at_the_exact_boundary():
    third = date(2024, 6, 21)
    assert LT.third_fridays(third, third) == [third]


# --- eligible_expiries: pinned equal to financed_spread.near_expiry_for -----

@pytest.mark.parametrize("day,remaining_dte,expiries", [
    (E0, 60, [date(2024, 6, 14), date(2024, 6, 21), date(2024, 7, 3)]),
    (E0, 60, [date(2024, 6, 6), date(2024, 6, 21)]),      # 7-day floor excludes 6/6
    (E0, 60, [date(2024, 6, 10)]),                         # exactly the floor
    (E0, 60, [date(2024, 7, 3)]),                          # exactly half-DTE
    (E0, 60, [date(2024, 7, 4)]),                          # just past half-DTE
    (E0, 12, [date(2024, 6, 14)]),                         # window is empty
    (E0, 60, []),                                           # nothing cached
])
def test_eligible_expiries_first_element_matches_near_expiry_for(day, remaining_dte, expiries):
    elig = LT.eligible_expiries(day, remaining_dte, expiries)
    expected = FS.near_expiry_for(day, remaining_dte, expiries)
    if expected is None:
        assert elig == []
    else:
        assert elig[0] == expected


def test_eligible_expiries_is_sorted():
    out = LT.eligible_expiries(E0, 60, [date(2024, 7, 3), date(2024, 6, 14), date(2024, 6, 21)])
    assert out == sorted(out)


# --- roll_chain --------------------------------------------------------------

# A far core expiry + a full year of monthly (third-Friday) expiries: the
# window (7 days .. half the REMAINING dte) stays wide through many rolls,
# which is what actually exercises a multi-slot chain — a near core expiry
# only a couple of months out closes the window down to one slot almost
# immediately (see test_roll_chain_single_slot_when_only_one_expiry_ever_eligible).
FAR_CORE_EXP = E0 + timedelta(days=380)
MONTHLY_EXPIRIES = LT.third_fridays(E0, E0 + timedelta(days=400))


def test_roll_chain_advances_to_the_first_grid_day_strictly_after_near():
    grid = _grid(400)
    chain = LT.roll_chain(grid, E0, FAR_CORE_EXP, MONTHLY_EXPIRIES)
    assert len(chain) >= 2
    first_roll_day, first_near = chain[0]
    assert first_roll_day == E0
    second_roll_day, _second_near = chain[1]
    expected_next = min(d for d in grid if d > first_near)
    assert second_roll_day == expected_next


def test_roll_chain_stops_at_grid_end():
    grid = _grid(20)   # short grid: truncates the chain well before FAR_CORE_EXP
    chain = LT.roll_chain(grid, E0, FAR_CORE_EXP, MONTHLY_EXPIRIES)
    assert all(rd in grid for rd, _near in chain)
    last_roll_day, last_near = chain[-1]
    assert not any(d > last_near for d in grid)   # nothing left in the grid to roll into


def test_roll_chain_empty_when_nothing_eligible_at_entry():
    grid = _grid(90)
    assert LT.roll_chain(grid, E0, CORE_EXP, []) == []


def test_roll_chain_single_slot_when_only_one_expiry_ever_eligible():
    grid = _grid(90)
    expiries = [date(2024, 6, 14)]
    chain = LT.roll_chain(grid, E0, CORE_EXP, expiries)
    assert chain == [(E0, date(2024, 6, 14))]


# --- target_strikes ------------------------------------------------------------

def test_target_strikes_call_takes_nearest_above_ascending():
    ladder = [90.0, 95.0, 100.0, 105.0, 110.0, 115.0, 120.0]
    out = LT.target_strikes(ladder, 100.0, "Call")
    assert out == [105.0, 110.0, 115.0, 120.0]


def test_target_strikes_put_takes_nearest_below_descending():
    ladder = [80.0, 85.0, 90.0, 95.0, 100.0]
    out = LT.target_strikes(ladder, 100.0, "Put")
    assert out == [95.0, 90.0, 85.0, 80.0]


def test_target_strikes_excludes_the_outer_strike_itself():
    ladder = [95.0, 100.0, 105.0]
    out = LT.target_strikes(ladder, 100.0, "Call")
    assert 100.0 not in out


def test_target_strikes_never_invents_a_strike_to_reach_n():
    ladder = [95.0, 100.0, 105.0]
    out = LT.target_strikes(ladder, 100.0, "Call", n=4)
    assert out == [105.0]


def test_target_strikes_respects_n():
    ladder = [101.0, 102.0, 103.0, 104.0, 105.0]
    out = LT.target_strikes(ladder, 100.0, "Call", n=2)
    assert out == [101.0, 102.0]


# --- ticker_ladder: own scan, pinned against fetch_financing_legs.ticker_ladder --

def test_ticker_ladder_unions_strikes_across_expiries_and_types(_isolate):
    _write_contract(_isolate, "AAA", date(2024, 6, 21), 100.0, "C")
    _write_contract(_isolate, "AAA", date(2024, 7, 19), 105.0, "P")
    _write_contract(_isolate, "AAA", date(2024, 7, 19), 110.0, "C")
    _write_contract(_isolate, "BBB", date(2024, 6, 21), 50.0, "C")
    assert LT.ticker_ladder("AAA") == [100.0, 105.0, 110.0]
    assert LT.ticker_ladder("BBB") == [50.0]


def test_ticker_ladder_empty_for_an_uncached_ticker(_isolate):
    assert LT.ticker_ladder("ZZZ") == []


def test_ticker_ladder_matches_fetch_financing_legs_ticker_ladder(_isolate):
    """Same derivation, different signature (per-ticker vs whole-cache idx) —
    pinned equal on a shared fixture."""
    _write_contract(_isolate, "AAA", date(2024, 6, 21), 100.0, "C")
    _write_contract(_isolate, "AAA", date(2024, 7, 19), 105.0, "P")
    idx = {("AAA", date(2024, 6, 21)): {100.0: {"C"}},
           ("AAA", date(2024, 7, 19)): {105.0: {"P"}}}
    assert LT.ticker_ladder("AAA") == ffl.ticker_ladder(idx)["AAA"]


# --- cached_strikes: dispatch to financed_spread.cached_calls / BR.cached_puts --

def test_cached_strikes_call_dispatches_to_cached_calls(_isolate):
    _write_contract(_isolate, "AAA", date(2024, 6, 21), 100.0, "C")
    assert LT.cached_strikes("AAA", date(2024, 6, 21), "Call") == [100.0]


def test_cached_strikes_put_dispatches_to_cached_puts(_isolate):
    _write_contract(_isolate, "AAA", date(2024, 6, 21), 90.0, "P")
    assert LT.cached_strikes("AAA", date(2024, 6, 21), "Put") == [90.0]


# --- core_of -------------------------------------------------------------------

@pytest.fixture()
def _fixed_entry(monkeypatch):
    monkeypatch.setattr(LT.BR, "entry_date_for", lambda legs, grid: E0)
    return E0


def _fake_bars(spot):
    return {E0: Bar(c=spot)} if spot is not None else {}


def test_core_of_builds_a_spec_for_a_bull_call_spread(_fixed_entry, monkeypatch):
    monkeypatch.setattr(LT, "load_bars", lambda ticker: _fake_bars(105.0))
    grid = _grid(60)
    rec = _rec(_bull_legs(), grid)
    core = LT.core_of(rec)
    assert core is not None
    assert core.ticker == "AAA" and core.expiry == CORE_EXP
    assert core.lo == 100.0 and core.hi == 110.0
    assert core.entry_day == E0
    assert core.spot_entry == 105.0
    assert core.grid == tuple(grid)


def test_core_of_none_when_spot_bar_missing(_fixed_entry, monkeypatch):
    monkeypatch.setattr(LT, "load_bars", lambda ticker: _fake_bars(None))
    core = LT.core_of(_rec(_bull_legs(), _grid()))
    assert core is not None
    assert core.spot_entry is None


def test_core_of_none_for_non_bull_call_structure(_fixed_entry, monkeypatch):
    monkeypatch.setattr(LT, "load_bars", lambda ticker: _fake_bars(105.0))
    rec = _rec(_bull_legs(), _grid(), structure="bear_put_spread")
    assert LT.core_of(rec) is None


def test_core_of_none_for_multi_expiry_legs(_fixed_entry, monkeypatch):
    monkeypatch.setattr(LT, "load_bars", lambda ticker: _fake_bars(105.0))
    legs = [Leg(1, "AAA", CORE_EXP, 100.0, "Call"),
            Leg(-1, "AAA", date(2024, 9, 20), 110.0, "Call")]
    assert LT.core_of(_rec(legs, _grid())) is None


def test_core_of_none_when_geometry_is_not_a_bull_vertical(_fixed_entry, monkeypatch):
    """long strike must be BELOW the short strike for a bull call spread."""
    monkeypatch.setattr(LT, "load_bars", lambda ticker: _fake_bars(105.0))
    legs = [Leg(1, "AAA", CORE_EXP, 110.0, "Call"), Leg(-1, "AAA", CORE_EXP, 100.0, "Call")]
    assert LT.core_of(_rec(legs, _grid())) is None


def test_core_of_none_when_no_common_entry_day(monkeypatch):
    monkeypatch.setattr(LT.BR, "entry_date_for", lambda legs, grid: None)
    monkeypatch.setattr(LT, "load_bars", lambda ticker: _fake_bars(105.0))
    assert LT.core_of(_rec(_bull_legs(), _grid())) is None


def test_core_of_none_for_a_dict_with_no_trade():
    assert LT.core_of({"t": None}) is None


# --- ladder_targets: category coverage, spot-None skip, put_core unconditional --

def _core(spot_entry=105.0, grid=None):
    return LT.CoreSpec(ticker="AAA", expiry=CORE_EXP, lo=100.0, hi=110.0,
                       entry_day=E0, grid=tuple(grid or _grid(90)), spot_entry=spot_entry)


LADDER = [80.0, 85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0]


def test_ladder_targets_produces_every_category_when_spot_is_known():
    core = LT.CoreSpec(ticker="AAA", expiry=FAR_CORE_EXP, lo=100.0, hi=110.0,
                       entry_day=E0, grid=tuple(_grid(400)), spot_entry=105.0)
    rows = LT.ladder_targets(core, MONTHLY_EXPIRIES, LADDER)
    cats = {r["category"] for r in rows}
    assert cats == {"ladder_call_t0", "ladder_call_roll", "ladder_put_short", "ladder_put_core"}


def test_ladder_targets_put_core_is_the_one_unconditional_row():
    rows = LT.ladder_targets(_core(spot_entry=None), [], LADDER)
    put_core = [r for r in rows if r["category"] == "ladder_put_core"]
    assert len(put_core) == 1
    r = put_core[0]
    assert (r["expiration"], r["strike"], r["opt_type"]) == (CORE_EXP, 100.0, "Put")


def test_ladder_targets_skips_put_short_when_spot_entry_is_none():
    expiries = [date(2024, 6, 14), date(2024, 6, 21), date(2024, 7, 19)]
    rows = LT.ladder_targets(_core(spot_entry=None), expiries, LADDER)
    assert not any(r["category"] == "ladder_put_short" for r in rows)
    # calls are unaffected by a missing spot
    assert any(r["category"] == "ladder_call_t0" for r in rows)


def test_ladder_targets_call_t0_takes_n_expiries_nearest_at_entry():
    expiries = [date(2024, 6, 14), date(2024, 6, 21), date(2024, 7, 19), date(2024, 6, 28)]
    rows = LT.ladder_targets(_core(), expiries, LADDER)
    t0_expiries = {r["expiration"] for r in rows if r["category"] == "ladder_call_t0"}
    assert len(t0_expiries) == LT.N_EXPIRIES


def test_ladder_targets_call_strikes_are_strictly_above_core_hi():
    expiries = [date(2024, 6, 14)]
    rows = LT.ladder_targets(_core(), expiries, LADDER)
    calls = [r for r in rows if r["opt_type"] == "Call" and r["category"] != "ladder_put_core"]
    assert all(r["strike"] > 110.0 for r in calls)


def test_ladder_targets_put_short_strikes_are_strictly_below_spot():
    expiries = [date(2024, 6, 14)]
    rows = LT.ladder_targets(_core(spot_entry=105.0), expiries, LADDER)
    puts = [r for r in rows if r["category"] == "ladder_put_short"]
    assert puts and all(r["strike"] < 105.0 for r in puts)


def test_ladder_targets_empty_expiries_still_yields_put_core_only():
    rows = LT.ladder_targets(_core(), [], LADDER)
    assert [r["category"] for r in rows] == ["ladder_put_core"]


def test_ladder_targets_no_duplicate_keys_across_categories():
    core = LT.CoreSpec(ticker="AAA", expiry=FAR_CORE_EXP, lo=100.0, hi=110.0,
                       entry_day=E0, grid=tuple(_grid(400)), spot_entry=105.0)
    rows = LT.ladder_targets(core, MONTHLY_EXPIRIES, LADDER)
    keys = [(r["expiration"], r["strike"], r["opt_type"]) for r in rows]
    assert len(keys) == len(set(keys))


def test_ladder_targets_sorted_output():
    expiries = [date(2024, 6, 14), date(2024, 6, 21), date(2024, 7, 19)]
    rows = LT.ladder_targets(_core(), expiries, LADDER)
    assert rows == sorted(rows, key=lambda r: (r["ticker"], r["expiration"], r["strike"],
                                               r["opt_type"], r["category"]))
