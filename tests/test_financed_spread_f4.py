"""Unit tests for ARM F4's construction and pricing in
`scripts/backtest_study/f3_structure/financed_spread.py`.

F4 (`financed_spread.md` §AMENDMENT 1) finances a book debit vertical with ONE
short-dated, delta-targeted naked short leg at a NEARER expiry, and §AMENDMENT
2 MANAGES that leg — bought back at 50% of the credit or at $100 on the
tranche, stopped at 2x credit against, and closed at its LAST REAL MARK if it
is still open at its near expiry.

What is pinned here is the part a report cannot show you: the two-segment
net-mark algebra (`Trade.pnl_of` must read the debit's move plus the leg's
REALIZED gain once it is closed), the trigger rules, and the guard that keeps a
zero-filled Barchart greek row from being read as a 0.00-delta candidate.

Everything is synthetic — a fake per-contract cache injected over
`bear_rewrap.leg_details`, no network, no real option history.
"""
from datetime import date, timedelta

import pytest

from scripts.backtest.legs import Leg
from scripts.backtest_study.f3_structure import bear_rewrap as BR
from scripts.backtest_study.f3_structure import financed_spread as FS
from scripts.backtest_study.lib import greeks as GK

TK = "AAA"
FAR = date(2024, 9, 20)      # the debit's expiry
NEAR = date(2024, 7, 19)     # the financing leg's expiry
ENTRY = date(2024, 6, 3)

BASE = [Leg(1, TK, FAR, 100.0, "Call"), Leg(-1, TK, FAR, 110.0, "Call")]
SHORT = Leg(-1, TK, NEAR, 120.0, "Call")


def _grid(n=10, start=ENTRY):
    return [start + timedelta(days=i) for i in range(n)]


def _bars(marks: dict, iv="30.0"):
    """`{date: row}` in the shape `parse_history_details` returns. `Open` is
    left at 0 so `entry_price_of` falls back to the mark, which keeps the
    entry credit equal to the entry-day mark and the arithmetic readable."""
    return {d: {"_mark": m, "Open": "0", "IV": iv} for d, m in marks.items()}


@pytest.fixture()
def cache(monkeypatch):
    """A per-leg fake cache keyed by the leg's contract identity."""
    store: dict[tuple, dict] = {}

    def put(leg, marks, iv="30.0"):
        store[(leg.ticker, leg.expiration, leg.strike, leg.opt_type)] = _bars(marks, iv)

    def leg_details(leg):
        return store.get((leg.ticker, leg.expiration, leg.strike, leg.opt_type), {})

    monkeypatch.setattr(BR, "leg_details", leg_details)
    put.store = store
    return put


def _flat_debit(cache, grid, values):
    """Price the two debit legs so their NET is `values[i]` on grid day i: the
    long leg carries the whole net, the short leg is worth 0."""
    cache(BASE[0], dict(zip(grid, values)))
    cache(BASE[1], {d: 0.0 for d in grid})


# ── the net-mark algebra ─────────────────────────────────────────────────────

def test_alive_segment_is_the_debit_minus_the_live_short_leg(cache):
    grid = _grid(4)
    _flat_debit(cache, grid, [3.0, 3.5, 3.6, 3.7])
    cache(SHORT, dict(zip(grid, [0.80, 0.30, 0.25, 0.20])))
    marks = FS.f4_net_marks(BASE, SHORT, grid, (None, None, "open_at_grid_end"))
    assert marks == pytest.approx([2.20, 3.20, 3.35, 3.50])


def test_after_buyback_the_leg_contributes_a_constant_realized_cost(cache):
    """The worked example in `f4_net_marks`'s docstring, executed: entry_net
    2.20, pt50 fires at 0.30 on day 1, and day 2's mark is the debit's 3.60
    minus the FROZEN 0.30 — not the live 0.25, and not zero."""
    grid = _grid(4)
    _flat_debit(cache, grid, [3.0, 3.5, 3.6, 3.7])
    cache(SHORT, dict(zip(grid, [0.80, 0.30, 0.25, 0.20])))
    marks = FS.f4_net_marks(BASE, SHORT, grid, (grid[1], 0.30, "pt50"))
    assert marks == pytest.approx([2.20, 3.20, 3.30, 3.40])

    entry_net = 2.20
    pnl = (marks[2] - entry_net) / abs(entry_net)
    # debit +0.60, leg's +0.50 realized and frozen, on a 2.20 basis
    assert pnl == pytest.approx((0.60 + 0.50) / 2.20)


def test_the_series_is_continuous_at_the_buyback_session(cache):
    """C(b) IS the buyback cost, so closing adds no step on the day itself —
    only afterwards, where the managed and held series diverge."""
    grid = _grid(4)
    _flat_debit(cache, grid, [3.0, 3.5, 3.6, 3.7])
    cache(SHORT, dict(zip(grid, [0.80, 0.30, 0.25, 0.20])))
    held = FS.f4_net_marks(BASE, SHORT, grid, (None, None, "open_at_grid_end"))
    managed = FS.f4_net_marks(BASE, SHORT, grid, (grid[1], 0.30, "pt50"))
    assert managed[1] == pytest.approx(held[1])
    assert managed[2] != pytest.approx(held[2])


def test_residual_is_paid_at_the_last_real_mark_never_dropped_to_zero(cache):
    """Amendment 2 supersedes amendment 1's drop-to-zero. A leg worth 0.20 at
    its near expiry costs 0.20 to close, so the net after it carries -0.20."""
    grid = _grid(4)
    _flat_debit(cache, grid, [3.0, 3.5, 3.6, 3.7])
    cache(SHORT, dict(zip(grid, [0.80, 0.30, 0.25, 0.20])))
    marks = FS.f4_net_marks(BASE, SHORT, grid, (grid[3], 0.20, "residual_expiry"))
    assert marks[3] == pytest.approx(3.7 - 0.20)


def test_the_clamp_applies_only_after_the_buyback(cache):
    """`_defined_risk_bounds` is a single-expiration function: while two
    expiries are live there is no such bound, and after the buyback it bounds
    the DEBIT's own value — the realized cost sits outside it, being cash."""
    grid = _grid(3)
    _flat_debit(cache, grid, [3.0, -1.0, -1.0])       # a negative net vertical mark
    cache(SHORT, dict(zip(grid, [0.80, 0.10, 0.10])))
    marks = FS.f4_net_marks(BASE, SHORT, grid, (grid[2], 0.10, "pt50"))
    assert marks[1] == pytest.approx(-1.10)           # open: unclamped
    assert marks[2] == pytest.approx(0.0 - 0.10)      # closed: clamped to [0,10], then cost


# ── the triggers ─────────────────────────────────────────────────────────────

def test_pt50_fires_on_the_first_session_at_or_below_half_the_credit(cache):
    grid = _grid(4)
    cache(SHORT, dict(zip(grid, [0.80, 0.45, 0.40, 0.20])))
    day, cost, why = FS.f4_buyback(SHORT, grid, ENTRY, 0.80, 1, "pt50")
    assert (day, cost, why) == (grid[2], 0.40, "pt50")


def test_d100_fires_on_the_tranche_dollar_threshold_and_scales_with_contracts(cache):
    grid = _grid(4)
    cache(SHORT, dict(zip(grid, [0.80, 0.60, 0.40, 0.20])))
    # 1 contract: needs (0.80 - m)*100 >= 100 -> m <= -0.20, so it never fires
    # (this grid stops short of the near expiry, so the leg is simply left open)
    day, _cost, why = FS.f4_buyback(SHORT, grid, ENTRY, 0.80, 1, "d100")
    assert why == "open_at_grid_end"
    # 5 contracts: (0.80-0.60)*100*5 = $100 on the first session
    day, cost, why = FS.f4_buyback(SHORT, grid, ENTRY, 0.80, 5, "d100")
    assert (day, cost, why) == (grid[1], 0.60, "d100")


def test_the_loss_stop_applies_to_both_mgmt_bases(cache):
    grid = _grid(3)
    cache(SHORT, dict(zip(grid, [0.80, 1.70, 0.10])))
    for mgmt in ("pt50", "d100"):
        day, cost, why = FS.f4_buyback(SHORT, grid, ENTRY, 0.80, 10, mgmt)
        assert (day, cost, why) == (grid[1], 1.70, "stop"), mgmt


def test_hold_never_triggers_and_closes_at_the_near_expiry(cache):
    grid = [NEAR - timedelta(days=2), NEAR, NEAR + timedelta(days=1)]
    cache(SHORT, dict(zip(grid[:2], [0.80, 0.05])))
    day, cost, why = FS.f4_buyback(SHORT, grid, grid[0], 0.80, 10, "hold")
    assert (day, cost, why) == (grid[2], 0.05, "residual_expiry")


def test_a_missing_mark_defers_to_the_next_priced_session(cache):
    """The trigger reads the leg's OWN bars, never a carried-forward quote: a
    day the contract did not print is not a trigger day."""
    grid = _grid(4)
    cache(SHORT, {grid[0]: 0.80, grid[3]: 0.30})      # grid[1], grid[2] unpriced
    day, cost, why = FS.f4_buyback(SHORT, grid, ENTRY, 0.80, 1, "pt50")
    assert (day, cost, why) == (grid[3], 0.30, "pt50")


def test_the_entry_session_never_triggers(cache):
    """The credit IS the entry session's fill; a trigger there would read an
    Open-vs-mark spread rather than decay."""
    grid = _grid(3)
    cache(SHORT, dict(zip(grid, [0.10, 0.90, 0.90])))   # entry mark already <= 0.5x
    day, _cost, why = FS.f4_buyback(SHORT, grid, grid[0], 0.80, 1, "pt50")
    assert day != grid[0] and why != "pt50"


def test_a_near_expiry_beyond_the_path_leaves_the_leg_open(cache):
    grid = [NEAR - timedelta(days=3), NEAR - timedelta(days=2)]
    cache(SHORT, dict(zip(grid, [0.80, 0.79])))
    day, cost, why = FS.f4_buyback(SHORT, grid, grid[0], 0.80, 1, "hold")
    assert (day, cost, why) == (None, None, "open_at_grid_end")


# ── the candidate pick ───────────────────────────────────────────────────────

def _plan(strikes):
    return (NEAR, list(strikes), "Call", "ok")


def _rec():
    class _T:
        legs = BASE
    return {"t": _T()}


def test_pick_takes_the_candidate_closest_to_the_delta_target(cache, monkeypatch):
    for k in (115.0, 120.0, 125.0):
        cache(Leg(-1, TK, NEAR, k, "Call"), {ENTRY: 1.0})
    deltas = {115.0: 0.30, 120.0: 0.12, 125.0: 0.04}
    monkeypatch.setattr(GK, "leg_greek",
                        lambda leg, day, name: -deltas[leg.strike])
    legs, why = FS.build_f4(_rec(), _plan([115.0, 120.0, 125.0]), 0.10, ENTRY)
    assert why == "ok" and legs[-1].strike == 120.0


def test_a_zero_filled_greek_row_is_not_a_zero_delta_candidate(cache, monkeypatch):
    """The COIN 2026-03-27 255P case: Barchart writes IV/Delta/Gamma/Vega all
    literally 0 for a session, and read as a delta of 0.00 that deep-ITM put
    lands INSIDE the d10 tolerance and gets sold as `financing`. A missing
    greek is None, never 0.0 — the candidate is skipped, not believed."""
    sentinel = Leg(-1, TK, NEAR, 115.0, "Call")
    good = Leg(-1, TK, NEAR, 120.0, "Call")
    cache(sentinel, {ENTRY: 53.25}, iv="0")
    cache(good, {ENTRY: 0.40})
    monkeypatch.setattr(GK, "leg_greek",
                        lambda leg, day, name: 0.0 if leg.strike == 115.0 else -0.12)
    legs, why = FS.build_f4(_rec(), _plan([115.0, 120.0]), 0.10, ENTRY)
    assert why == "ok" and legs[-1].strike == 120.0


def test_an_all_sentinel_candidate_set_is_counted_not_built(cache, monkeypatch):
    for k in (115.0, 120.0):
        cache(Leg(-1, TK, NEAR, k, "Call"), {ENTRY: 53.25}, iv="0")
    monkeypatch.setattr(GK, "leg_greek", lambda leg, day, name: 0.0)
    legs, why = FS.build_f4(_rec(), _plan([115.0, 120.0]), 0.10, ENTRY)
    assert legs is None and why == "skip_greeks_absent"


def test_an_unreachable_target_is_excluded_and_counted(cache, monkeypatch):
    cache(Leg(-1, TK, NEAR, 115.0, "Call"), {ENTRY: 2.0})
    monkeypatch.setattr(GK, "leg_greek", lambda leg, day, name: -0.45)
    legs, why = FS.build_f4(_rec(), _plan([115.0]), 0.10, ENTRY)
    assert legs is None and why == "skip_target_unreachable"


# ── the cell grid ────────────────────────────────────────────────────────────

def test_f4_is_the_six_registered_cells_on_the_same_rows():
    f4 = [c for c in FS.CELLS if c[0] == "F4"]
    assert len(f4) == 6
    assert {c[1] for c in f4} == {10, 20}
    assert {c[2] for c in f4} == {"pt50", "d100", "hold"}
    assert [FS.cell_label(c) for c in f4[:3]] == [
        "F4-d10 pt50", "F4-d10 $100", "F4-d10 hold"]


def test_every_shape_prints_one_under_the_floor_token():
    """Amendment 1 split F4's wording from F0-F3's; the split is gone.

    The repo retired "POWER-STOPPED" on 2026-08-22, so there is a single token
    and no shape-dependent branch left to get wrong. Reports on disk from
    before that date still say POWER-STOPPED and are not rewritten.
    """
    assert FS.UNDERPOWERED == "UNDERPOWERED"
    assert FS.UNDERPOWERED in FS.VERDICTS
    assert not hasattr(FS, "underpowered_token")


def test_the_frozen_trigger_values_are_the_operators_stated_practice():
    """0.50, $100 and 2x may not be tuned after a number is seen."""
    assert (FS.PT50_FRAC, FS.PROFIT_DOLLARS, FS.LOSS_MULT) == (0.50, 100.0, 2.0)
