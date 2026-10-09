"""bear_fast_exit — the arms are composition around the frozen replay, and the
cost is production's own `_apply_costs`.

Registration: research/pre-registrations/f2_management/bear_fast_exit.md.
Every test runs on synthetic trades, so it tests the RULE rather than whatever
the current book holds.
"""
from __future__ import annotations

from datetime import date

import pytest

from scripts.backtest import simulate as SIM
from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study.f2_management import bear_fast_exit as BFE
from scripts.backtest_study.lib.harness import Trade, replay

SIGNAL = date(2025, 1, 6)          # a Monday
EXPIRY = date(2025, 2, 14)


def _trade(marks: list, structure: str = "bear_put_spread", entry: str = "1.00",
           contracts: int = 2) -> Trade:
    """A $1.00-entry trade whose marks are handed in directly (pnl = mark - 1)."""
    grid = _weekday_grid(SIGNAL, EXPIRY)
    padded = list(marks) + [marks[-1]] * (len(grid) - len(marks))
    return Trade({
        "signal_date": SIGNAL.isoformat(),
        "ticker": "TEST",
        "structure": structure,
        "entry_option_price": entry,
        "contracts": str(contracts),
        "dte_entry": str((EXPIRY - SIGNAL).days),
        "legs": f"TEST:{EXPIRY.isoformat()}:100:P +1\nTEST:{EXPIRY.isoformat()}:90:P -1",
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in padded),
    }, load_underlying=False)


def _rec(t: Trade, credit: bool = False) -> dict:
    return dict(t=t, structure=t.structure, credit=credit, date=SIGNAL.isoformat())


SHIPPED = dict(pt=0.90, sl=0.75, trig=None, trail=None, tef=0.75, be_after=None)


# ── the arms are frozen ──────────────────────────────────────────────────────

def test_the_eight_arms_are_the_registered_ones():
    assert [(f, pt, n) for _, f, pt, n in BFE.ARMS] == [
        ("TP", 0.10, None), ("TP", 0.20, None), ("TP", 0.30, None),
        ("TS", None, 1), ("TS", None, 2), ("TS", None, 3), ("TS", None, 5),
        ("OP", 0.25, 5),
    ]
    assert (BFE.G0_MIN_DATES, BFE.G0_MIN_ROWS) == (25, 60)
    assert (BFE.C7_MIN_DATES, BFE.C7_MIN_ROWS) == (15, 30)
    assert BFE.G4_MAX_FALLBACK_SHARE == 0.25
    assert BFE.SECONDARY_SLIPPAGE == 0.25
    assert BFE.SEAL_START == "2026-09-23"


# ── ARM TP / TS / OP ─────────────────────────────────────────────────────────

def test_tp_replaces_only_the_profit_target():
    t = _trade([1.05, 1.12, 1.30, 1.95])
    res = BFE.arm_outcome(_rec(t), SHIPPED, 0.10, None)
    assert BFE.triple(res) == ("profit_target", 2, 0.12)
    assert BFE.triple(BFE.arm_outcome(_rec(t), SHIPPED, 0.90, None)) == \
        BFE.triple(replay(t, **SHIPPED))


def test_ts_exits_at_the_session_n_mark():
    t = _trade([1.05, 0.90, 0.80, 0.70, 1.20])
    res = BFE.arm_outcome(_rec(t), SHIPPED, None, 3)
    assert BFE.triple(res) == (BFE.TS_REASON, 3, -0.20)


def test_ts_falls_back_to_the_last_priced_mark_before_n():
    t = _trade([1.05, 0.90, None, 0.70, 1.20])
    res = BFE.arm_outcome(_rec(t), SHIPPED, None, 3)
    assert BFE.triple(res) == (BFE.TS_REASON, 2, -0.10)


def test_ts_keeps_the_shipped_result_when_nothing_is_priced_by_n():
    t = _trade([None, None, None, 1.10, 1.20])
    shipped = replay(t, **SHIPPED)
    res = BFE.arm_outcome(_rec(t), SHIPPED, None, 3)
    assert BFE.triple(res) == BFE.triple(shipped)


def test_ts_leaves_a_row_that_already_exited_alone():
    t = _trade([1.95, 1.00])                       # pt fires on session 1
    res = BFE.arm_outcome(_rec(t), SHIPPED, None, 3)
    assert BFE.triple(res) == ("profit_target", 1, 0.95)


def test_ts_beyond_the_path_reproduces_the_baseline():
    t = _trade([1.05, 0.90, 0.80, 0.70, 1.20])
    assert BFE.triple(BFE.arm_outcome(_rec(t), SHIPPED, None, 10 ** 6)) == \
        BFE.triple(replay(t, **SHIPPED))


def test_op_composes_the_session_stop_on_the_tp_replay():
    up = _trade([1.05, 1.10, 1.26, 1.40])         # +0.26 on session 3 -> pt 0.25
    assert BFE.triple(BFE.arm_outcome(_rec(up), SHIPPED, 0.25, 5)) == \
        ("profit_target", 3, 0.26)
    flat = _trade([1.05, 1.10, 1.05, 1.00, 0.95, 0.90])
    assert BFE.triple(BFE.arm_outcome(_rec(flat), SHIPPED, 0.25, 5)) == \
        (BFE.TS_REASON, 5, -0.05)


@pytest.mark.parametrize("structure,credit", [
    ("bull_call_spread", False), ("bull_put_spread", True), ("bear_put_spread", True),
])
def test_leak_guard_non_bear_rows_are_never_touched(structure, credit):
    """G1's rule: the bear keying lives inside `arm_outcome`."""
    t = _trade([1.05, 1.12, 0.90, 0.80, 1.30], structure=structure)
    want = BFE.triple(replay(t, **SHIPPED))
    for _, _, pt, n in BFE.ARMS:
        assert BFE.triple(BFE.arm_outcome(_rec(t, credit), SHIPPED, pt, n)) == want


# ── the baseline is production's merge ───────────────────────────────────────

def test_harness_profile_maps_production_keys():
    eff = {"profit_target": 0.9, "stop_loss": 0.75, "time_exit_dte_fraction": 0.75,
           "trailing_stop_trigger": 0.5, "trailing_stop_pct": 0.5, "be_after": None}
    assert BFE.harness_profile(eff) == dict(pt=0.9, sl=0.75, trig=0.5, trail=0.5,
                                            tef=0.75, be_after=None)


def test_harness_profile_refuses_a_rule_the_harness_cannot_replay():
    with pytest.raises(ValueError):
        BFE.harness_profile({"trailing_stop_portfolio_trigger_pct": 0.02})


def test_production_profile_has_no_breakeven_stop_while_structure_exit_is_off():
    sim_cfg = BFE.load_sim_cfg()
    t = _trade([1.05])
    prof = BFE.production_profile(_rec(t), sim_cfg)
    if not sim_cfg["structure_exit"]["enabled"]:
        assert prof["be_after"] is None
    assert prof["pt"] == sim_cfg["profit_target"]


# ── cost: production's `_apply_costs` ────────────────────────────────────────

def test_cost_is_production_apply_costs():
    t = _trade([1.05])
    got = BFE.cost_dollars(t, "time_exit", 3, 0.65, 0.25, 0.10, [0.0, 0.0, 0.08])
    res = {"days_held": 3, "realized_pnl_abs": 0.0, "realized_pnl_pct": 0.0}
    SIM._apply_costs(res, {"commission_per_contract": 0.65, "slippage_frac_of_spread": 0.25},
                     t.legs, t.contracts, t.entry_net, 0.10, [0.0, 0.0, 0.08])
    assert got == res["cost_total"]
    # 2 legs x 2 contracts x 2 sides x 0.65 + 0.25 x (0.10 + 0.08) x 100 x 2
    assert got == pytest.approx(5.20 + 9.00)


def test_commission_only_cost_in_r():
    t = _trade([1.05])
    c = BFE.cost_dollars(t, "time_exit", 3, 0.65, 0.0)
    assert c == pytest.approx(5.20)
    assert BFE.cost_r(t, c) == pytest.approx(5.20 / 200)


def test_an_expired_position_pays_the_entry_side_only():
    t = _trade([1.05])
    full = BFE.cost_dollars(t, "time_exit", 3, 0.65, 0.25, 0.10, [0.0, 0.0, 0.08])
    exp = BFE.cost_dollars(t, "expired", 3, 0.65, 0.25, 0.10, [0.0, 0.0, 0.08])
    assert exp == pytest.approx(0.65 * 4 + 0.25 * 0.10 * 100 * 2)
    assert full - exp == pytest.approx(0.65 * 4 + 0.25 * 0.08 * 100 * 2)


# ── ARM Q's fallback ladder ──────────────────────────────────────────────────

class _Quotes:
    """A QuoteBook stand-in: `{(strike): {date: row}}`."""

    def __init__(self, by_strike):
        self.by_strike = by_strike

    def rows(self, leg):
        return self.by_strike.get(leg.strike, {})


def _q(bid, ask):
    return {"Bid": str(bid), "Ask": str(ask)}


def test_fallback_ladder_order():
    t = _trade([1.00, 1.00, 1.00])
    g = t.grid
    quotes = _Quotes({
        100.0: {g[0]: _q(1.00, 1.10), g[1]: _q(1.00, 1.20)},     # day 3 missing -> fb1
        90.0: {g[0]: _q(0.50, 0.55)},                           # day 2 missing; own path
    })
    sp = BFE.leg_spreads(t, quotes)
    assert sp[0][0] == (pytest.approx(0.10), BFE.Q_QUOTE)
    assert sp[0][2] == (pytest.approx(0.15), BFE.Q_FB1)       # median(0.10, 0.20)
    assert sp[1][1] == (pytest.approx(0.05), BFE.Q_FB1)


def test_fallback_two_then_uncostable():
    t = _trade([1.00, 1.00])
    g = t.grid
    quotes = _Quotes({100.0: {g[0]: _q(1.00, 1.10)}, 90.0: {}})
    sp = BFE.leg_spreads(t, quotes)
    # leg 90 has no usable quote on its whole path -> other leg that day
    assert sp[1][0] == (pytest.approx(0.10), BFE.Q_FB2)
    t2 = _trade([1.00])
    sp2 = BFE.leg_spreads(t2, _Quotes({}))
    assert sp2[0][0] == (None, BFE.Q_NONE)
    units, _ = BFE.side_units(t2, sp2, 0)
    assert units is None


def test_a_junk_quote_takes_the_ladder():
    """bid 0 is junk under production's rule: not a spread anyone pays."""
    assert BFE.usable_spread(_q(0, 0.40)) is None
    assert BFE.usable_spread(_q(1.00, 1.10)) == pytest.approx(0.10)


# ── verdict wording ──────────────────────────────────────────────────────────

def _cell(level_lo, delta_lo):
    cuts = {"x": (10, level_lo + 0.01, delta_lo + 0.01)}
    return dict(powered=True, level_ci=(level_lo, 1.0), delta_ci=(delta_lo, 1.0),
                level_loo_min=level_lo + 0.001, delta_loo_min=delta_lo + 0.001, cuts=cuts)


def _grid(level_lo, delta_lo):
    return {lab: _cell(level_lo, delta_lo) for lab, _, _, _ in BFE.ARMS}


def test_verdict_tokens():
    assert BFE.verdict(_grid(0.01, 0.01), _grid(0.01, 0.01))[0] == "PAYS (C7 PENDING)"
    assert BFE.verdict(_grid(-0.1, 0.01), _grid(-0.1, 0.01))[0] == "BLEED-CUT (C7 PENDING)"
    assert BFE.verdict(_grid(-0.1, -0.01), _grid(-0.1, 0.01))[0] == "NULL"
    under = {lab: dict(powered=False) for lab, _, _, _ in BFE.ARMS}
    assert BFE.verdict(under, under)[0] == "UNDERPOWERED"


def test_a_cut_that_fails_robustness_is_null_and_named():
    g = _grid(-0.1, 0.01)
    for c in g.values():
        c["delta_loo_min"] = -0.001
    v, notes = BFE.verdict(g, _grid(-0.1, 0.01))
    assert v == "NULL"
    assert notes and "fails C5 or C6" in notes[0]
