"""cost_sensitivity arithmetic and gates.

Registration: research/pre-registrations/f2_management/cost_sensitivity.md
(accepted by default 2026-10-09), §Build notes: the per-leg charge, the
twice-not-once rule, the expired-leg exemption and the fallback ladder's order.
All fixtures are synthetic; nothing reads the real exports.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from scripts.backtest.legs import parse_legs
from scripts.backtest_study.f2_management import cost_sensitivity as cs

VERTICAL = parse_legs("SPY:2026-01-16:500:C +1\nSPY:2026-01-16:510:C -1")
RATIO = parse_legs("SPY:2026-01-16:500:C +1\nSPY:2026-01-16:510:C -2")


# ── registered constants ───────────────────────────────────────────────────

def test_registered_points():
    assert cs.ARM_X == (0.65, 0.0)
    assert cs.SW_COMMISSIONS == (0.00, 0.65, 1.00, 1.50)
    assert cs.SW_FRACTIONS == (0.00, 0.25, 0.50, 1.00)
    assert cs.G4_MAX_SHARE == 0.25
    assert (cs.C0_MIN_DATES, cs.C0_MIN_POSITIONS) == (25, 40)
    assert cs.THRESHOLD_EXITS == {"profit_target", "trailing_stop", "underlying_stop",
                                  "dollar_stop", "be_stop", "stop_loss"}
    assert dict(cs.GAP_TICKS) == {"headline": 0.05, "secondary": 0.01}
    assert dict(cs.C4_UNGRADED_MODES) == {"headline": "fails", "secondary": "drops"}


# ── per-leg charge, twice not once, expired exemption ──────────────────────

def test_commission_is_per_leg_per_side():
    # 2 legs x 2 sides x $0.65 = $2.60 per contract on a $2.00 debit -> 2.60 / 200
    assert cs.commission_r(0.65, VERTICAL, 2.0, "profit_target") == pytest.approx(0.013)


def test_commission_scales_with_qty():
    # ratio: units 1 + 2 = 3 per side
    assert cs.commission_r(1.0, RATIO, 1.0, "time_exit") == pytest.approx(3 * 2 / 100)


def test_expired_is_charged_at_entry_only():
    both = cs.commission_r(0.65, VERTICAL, 2.0, "stop_loss")
    once = cs.commission_r(0.65, VERTICAL, 2.0, "expired")
    assert once == pytest.approx(both / 2)
    assert cs.sides_for("expired") == 1
    assert cs.sides_for("cap_open") == 2      # open at the data end: still charged twice


@pytest.mark.parametrize("reason", ["profit_target", "cap_open", "time_exit", "expired", ""])
def test_charge_events_match_the_independent_count(reason):
    assert len(cs.charge_events(VERTICAL, reason)) == \
        cs.expected_charge_count(len(VERTICAL), reason)


def test_gross_r_undoes_production_charge():
    # production: net = gross - cost / (denom*100*contracts)
    denom, contracts, cost = 2.0, 3, 7.80
    gross = 0.25
    net = round(gross - cost / (denom * 100 * contracts), 4)
    assert cs.gross_r(net, cost, denom, contracts) == pytest.approx(gross, abs=1e-4)
    assert cs.gross_r(net, "", denom, contracts) == net


def test_stored_cost_expected_matches_apply_costs_formula():
    # config/backtest.yml comment: 2-leg spread, 3 contracts, $0.65 -> $7.80
    assert cs.stored_cost_expected(0.65, VERTICAL, 3) == 7.80


def test_arm_x_on_stored_basis_equals_stored_r_except_expired():
    denom, contracts = 2.0, 1
    cost = cs.stored_cost_expected(0.65, VERTICAL, contracts)
    stored = 0.10
    for reason, bump in (("profit_target", 0.0), ("expired", 0.65 * 2 / 200)):
        p = dict(gross_R=cs.gross_r(stored, cost, denom, contracts), legs=VERTICAL,
                 denom=denom, exit_reason=reason, spreads={})
        assert cs.net_r(p, *cs.ARM_X) == pytest.approx(stored + bump)


# ── slippage and the fallback ladder ───────────────────────────────────────

def test_slippage_charges_qty_times_spread():
    spreads = {(0, "entry"): 0.10, (1, "entry"): 0.20, (0, "exit"): 0.10, (1, "exit"): 0.20}
    assert cs.slippage_r(0.5, VERTICAL, 2.0, spreads) == pytest.approx(0.5 * 0.6 / 2.0)
    assert cs.slippage_r(0.0, VERTICAL, 2.0, {(0, "entry"): None}) == 0.0


def test_uncostable_leg_makes_position_uncostable_never_zero():
    spreads = {(0, "entry"): 0.10, (1, "entry"): None}
    assert cs.slippage_r(0.25, VERTICAL, 2.0, spreads) is None
    p = dict(gross_R=0.1, legs=VERTICAL, denom=2.0, exit_reason="time_exit", spreads=spreads)
    assert cs.net_r(p, 0.65, 0.25) is None
    assert cs.net_r(p, 0.65, 0.0) is not None     # ARM X reads no quote


def test_fallback_ladder_order():
    assert cs.resolve_spread(0.10, [0.5], [0.9]) == (0.10, cs.DIRECT)
    assert cs.resolve_spread(None, [0.2, None, 0.4], [0.9]) == (pytest.approx(0.3), cs.FB1)
    assert cs.resolve_spread(None, [None], [0.9, 0.7, None]) == (pytest.approx(0.8), cs.FB2)
    assert cs.resolve_spread(None, [], []) == (None, cs.UNCOSTABLE)


def test_fallback_lists_are_lazy():
    def boom():
        raise AssertionError("evaluated a fallback the ladder never reached")
    assert cs.resolve_spread(0.1, boom, boom)[1] == cs.DIRECT
    assert cs.resolve_spread(None, lambda: [0.2], boom)[1] == cs.FB1


@pytest.mark.parametrize("bid,ask,usable", [
    ("1.00", "1.10", True),
    ("1.00", "1.00", False),     # Ask <= Bid
    ("1.10", "1.00", False),
    ("0", "0.05", False),        # Bid = 0
    ("", "1.10", False),         # Bid absent
    ("1.00", "", False),         # Ask absent
    ("0.09", "5.00", False),     # production's junk-quote rule
])
def test_usable_spread(bid, ask, usable):
    s = cs.usable_spread({"Bid": bid, "Ask": ask})
    assert (s is not None) is usable


def test_g4_share():
    c = Counter({cs.DIRECT: 70, cs.FB1: 5, cs.FB2: 20, cs.UNCOSTABLE: 5})
    assert cs.g4_share(c) == pytest.approx(0.25)
    assert cs.g4_share(Counter()) == 0.0


# ── ARM GAP ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("reason,charged", [
    ("profit_target", True), ("dollar_stop", True), ("be_stop", True),
    ("underlying_stop", True), ("time_exit", False), ("expired", False), ("cap_open", False),
])
def test_gap_tick_only_on_threshold_exits(reason, charged):
    v = cs.gap_r(0.05, VERTICAL, 2.0, reason)
    assert v == (pytest.approx(0.05 * 2 / 2.0) if charged else 0.0)


# ── gates ───────────────────────────────────────────────────────────────────

def _pos(**kw):
    base = dict(date="2026-01-02", ticker="SPY", structure="bull_call_spread",
                exit_reason="profit_target", legs=VERTICAL, n_detail=2, contracts=1,
                cost_total=2.60, cost_basis="commission_only", has_cost_col=True)
    base.update(kw)
    return base


def test_g3_refuses_an_export_without_cost_basis():
    with pytest.raises(cs.GateRefusal) as e:
        cs.gate_g3([_pos(), _pos(has_cost_col=False, cost_basis="")])
    assert e.value.code == cs.EXIT_G3_PROVENANCE
    with pytest.raises(cs.GateRefusal):
        cs.gate_g3([_pos(cost_basis="")])
    assert cs.gate_g3([_pos()])["n"] == 1


def test_g2_reconciles_stored_cost():
    assert cs.gate_g2([_pos(), _pos(exit_reason="expired")], 0.65, 0.0)["expired"] == 1
    with pytest.raises(cs.GateRefusal) as e:
        cs.gate_g2([_pos(cost_total=2.00)], 0.65, 0.0)
    assert e.value.code == cs.EXIT_G2_MISMATCH


def test_g2_refuses_a_leg_count_mismatch():
    with pytest.raises(cs.GateRefusal):
        cs.gate_g2([_pos(n_detail=3)], 0.65, 0.0)


def test_g2_skips_cost_reconcile_on_other_bases():
    out = cs.gate_g2([_pos(cost_basis="full", cost_total=9.99)], 0.65, 0.25)
    assert out["cost_checked"] == 0


def test_designed_refusals():
    assert cs.EXIT_G3_PROVENANCE in cs.DESIGNED_REFUSAL_EXIT_CODES
    assert cs.EXIT_G2_MISMATCH not in cs.DESIGNED_REFUSAL_EXIT_CODES


def test_stored_knobs_read_from_config():
    c, s = cs.stored_knobs()
    assert c >= 0 and s >= 0


# ── verdicts ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("c0,cm,c3,c4,mode,want", [
    (False, None, None, None, "fails", "UNDERPOWERED"),
    (True, False, None, None, "fails", "VANISHES"),
    (True, True, True, True, "fails", "SURVIVES"),
    (True, True, False, True, "fails", "FRAGILE"),
    (True, True, True, False, "drops", "FRAGILE"),
    (True, True, True, None, "fails", "FRAGILE"),     # headline: ungraded C4 does not hold
    (True, True, True, None, "drops", "SURVIVES"),    # declared secondary
    (True, True, False, None, "drops", "FRAGILE"),
])
def test_tier_verdict(c0, cm, c3, c4, mode, want):
    assert cs.tier_verdict(c0, cm, c3, c4, mode) == want


def test_c0_floor():
    assert cs.c0_passes(25, 40)
    assert not cs.c0_passes(24, 400)
    assert not cs.c0_passes(100, 39)


def test_loo_min_names_the_carrying_unit():
    rows = [{"date": "d1", "ticker": "A", "net": 1.0},
            {"date": "d2", "ticker": "B", "net": -0.2},
            {"date": "d3", "ticker": "C", "net": -0.2}]
    worst, who, n = cs.loo_min(rows, "date")
    assert who == "d1" and worst == pytest.approx(-0.2) and n == 3


def test_implied_dollars():
    assert cs.implied_dollars(0.65, 0.0, None) == 0.65
    assert cs.implied_dollars(0.65, 0.5, 0.10) == pytest.approx(5.65)
    assert cs.implied_dollars(0.65, 0.5, None) is None


# ── quotes off a synthetic cache ────────────────────────────────────────────

def test_quotebook_reads_cache(tmp_path):
    leg_l, leg_s = VERTICAL
    header = "Time,Open,High,Low,Latest,Change,Bid,Ask,Volume,Open Int\n"
    for leg, rows in ((leg_l, {"2025-12-01": ("1.00", "1.10"), "2025-12-03": ("1.20", "1.40")}),
                      (leg_s, {"2025-12-01": ("0.50", "0.56")})):
        body = "".join(f"{d},0,0,0,{b},0,{b},{a},1,1\n" for d, (b, a) in rows.items())
        from lib.barchart.options import cache_path
        cache_path(tmp_path, leg.ticker, leg.expiration, leg.strike, leg.opt_type) \
            .write_text(header + body)
    qb = cs.QuoteBook(tmp_path)
    assert qb.spread(leg_l, date(2025, 12, 1)) == pytest.approx(0.10)
    assert qb.spread(leg_l, date(2025, 12, 2)) is None
