"""structure_sweep: the deterministic pieces, on tiny fixtures. No network, no
real cache read — `bear_rewrap.leg_details` is replaced where a view reads."""
from __future__ import annotations

import os
from datetime import date

import numpy as np
import pytest

from scripts.backtest.legs import Leg
from scripts.backtest_study.f3_structure import index_vrp as IV
from scripts.backtest_study.f3_structure import structure_sweep as S

ED = date(2026, 3, 2)
EXP = date(2026, 4, 17)


def _row(delta, price=100.0):
    return {"Delta": str(delta), "Price~": str(price), "_mark": 1.0}


def _chain():
    """Calls and puts at 90..110 by 5 on the entry day, spot 100.4."""
    ch = IV.Chain("XYZ", EXP)
    deltas_c = {90: 0.85, 95: 0.70, 100: 0.50, 105: 0.30, 110: 0.15}
    deltas_p = {90: -0.14, 95: -0.30, 100: -0.50, 105: -0.70, 110: -0.85}
    for k, dl in deltas_c.items():
        ch.rows[("C", float(k))] = {ED: _row(dl, 100.4)}
    for k, dl in deltas_p.items():
        ch.rows[("P", float(k))] = {ED: _row(dl, 100.4)}
    return ch


# ── strike pickers ───────────────────────────────────────────────────────────

def test_pick_strikes_on_a_tiny_chain():
    pk = S.pick_strikes(_chain(), ED)
    assert pk.spot == 100.4
    assert pk.kb == 100.0                        # nearest spot with both types
    assert (pk.kc, pk.kp) == (110.0, 90.0)       # |Delta| nearest 0.16
    # wings: short +/- 0.03 x spot = +/- 3.012 -> nearest listed 105 / 95 for B
    assert (pk.wc_b, pk.wp_b) == (105.0, 95.0)
    # C's wings land past the listed range: 113 -> 110 is the short itself and
    # nothing lies beyond it, so the side has no wing.
    assert pk.wc_c is None and pk.wp_c is None
    legs, why = S.chain_legs("C", "XYZ", EXP, pk)
    assert legs is None and why == "no_wing"


def test_butterfly_straddle_strangle_legs():
    pk = S.pick_strikes(_chain(), ED)
    b, _ = S.chain_legs("B", "XYZ", EXP, pk)
    assert sorted((lg.strike, lg.opt_type, lg.qty) for lg in b) == [
        (95.0, "Put", 1), (100.0, "Call", -1), (100.0, "Put", -1), (105.0, "Call", 1)]
    d, _ = S.chain_legs("D", "XYZ", EXP, pk)
    assert {(lg.strike, lg.opt_type, lg.qty) for lg in d} == {
        (100.0, "Call", 1), (100.0, "Put", 1)}
    g, _ = S.chain_legs("G", "XYZ", EXP, pk)
    s, _ = S.chain_legs("S", "XYZ", EXP, pk)
    assert {(lg.strike, lg.qty) for lg in g} == {(110.0, 1), (90.0, 1)}
    assert {(lg.strike, lg.qty) for lg in s} == {(110.0, -1), (90.0, -1)}


def test_atm_ties_go_to_the_lower_strike():
    calls = {100.0: {}, 102.0: {}}
    puts = {100.0: {}, 102.0: {}}
    assert IV.select_atm(calls, puts, 101.0) == 100.0


def test_wing_on_the_short_moves_one_listed_strike_out():
    assert IV.select_wing([100, 105, 110], 105, 106, "C") == 110
    assert IV.select_wing([90, 95, 100], 95, 94, "P") == 90


def test_no_spot_leaves_every_chain_arm_unpriced():
    ch = IV.Chain("XYZ", EXP)
    pk = S.pick_strikes(ch, ED)
    for arm in ("C", "B", "D", "G", "S"):
        assert S.chain_legs(arm, "XYZ", EXP, pk) == (None, "no_spot")


def test_calendar_back_expiry_needs_fourteen_days():
    front = date(2026, 4, 17)
    cands = [date(2026, 4, 24), date(2026, 5, 1), date(2026, 5, 15)]
    assert S.calendar_back_expiry(front, cands) == date(2026, 5, 1)
    assert S.calendar_back_expiry(front, [date(2026, 4, 24)]) is None


# ── leg construction ─────────────────────────────────────────────────────────

def _bull_call():
    return [Leg(1, "XYZ", EXP, 100.0, "Call"), Leg(-1, "XYZ", EXP, 110.0, "Call")]


def test_flip_negates_every_quantity():
    f = S.flip_legs(_bull_call())
    assert [(lg.strike, lg.qty) for lg in f] == [(100.0, -1), (110.0, 1)]
    assert all(lg.opt_type == "Call" for lg in f)


def test_type_swap_keeps_direction_and_strikes():
    t = S.type_swap_legs(_bull_call())
    # bull call 100/110 -> bull put 100/110: long the low put, short the high put
    assert [(lg.strike, lg.opt_type, lg.qty) for lg in t] == [
        (100.0, "Put", 1), (110.0, "Put", -1)]
    bear_put = [Leg(1, "XYZ", EXP, 110.0, "Put"), Leg(-1, "XYZ", EXP, 100.0, "Put")]
    assert [(lg.strike, lg.opt_type, lg.qty) for lg in S.type_swap_legs(bear_put)] == [
        (110.0, "Call", 1), (100.0, "Call", -1)]


def test_type_swap_refuses_a_non_vertical():
    straddle = [Leg(1, "XYZ", EXP, 100.0, "Call"), Leg(1, "XYZ", EXP, 100.0, "Put")]
    assert S.type_swap_legs(straddle) is None
    assert S.type_swap_legs([Leg(1, "XYZ", EXP, 100.0, "Call")]) is None
    diag = [Leg(1, "XYZ", EXP, 100.0, "Call"),
            Leg(-1, "XYZ", date(2026, 5, 15), 110.0, "Call")]
    assert S.type_swap_legs(diag) is None


def test_leg_str_round_trips_through_the_harness_grammar():
    from scripts.backtest.legs import parse_legs
    legs = _bull_call()
    assert parse_legs(S.leg_str(legs)) == legs


# ── the S1 cache view ────────────────────────────────────────────────────────

def _touch(path, mtime):
    path.write_text("Time,Latest\n")
    os.utime(path, (mtime, mtime))


def test_parse_cache_name():
    assert S.parse_cache_name("BRK.B_20260417_105.50C.csv") == (
        "BRK.B", date(2026, 4, 17), "C", 105.5)
    assert S.parse_cache_name("_unlisted.jsonl") is None
    assert S.parse_cache_name("XYZ_2026041_100.00C.csv") is None


def test_s1_view_refuses_a_file_newer_than_the_split(tmp_path, monkeypatch):
    old = tmp_path / "XYZ_20260417_100.00C.csv"
    new = tmp_path / "XYZ_20260417_105.00C.csv"
    _touch(old, S.SPLIT_EPOCH - 60)
    _touch(new, S.SPLIT_EPOCH + 60)
    idx = S.build_index(tmp_path)
    assert set(idx[("XYZ", EXP)]) == {("C", 100.0), ("C", 105.0)}

    reads = []

    def fake_details(leg):
        reads.append(leg.strike)
        return {ED: _row(0.5)}
    monkeypatch.setattr(S.BR, "leg_details", fake_details)

    s1 = S.CacheView(S.SPLIT_EPOCH, idx, "S1", cache_dir=tmp_path)
    full = S.CacheView(None, idx, "S2", cache_dir=tmp_path)
    assert s1.admits_path(old) and not s1.admits_path(new)
    assert full.admits_path(new)

    new_leg = Leg(1, "XYZ", EXP, 105.0, "Call")
    assert s1.details(new_leg) is None
    assert 105.0 not in reads                     # never read for S1
    assert set(s1.chain("XYZ", EXP).rows) == {("C", 100.0)}
    assert set(full.chain("XYZ", EXP).rows) == {("C", 100.0), ("C", 105.0)}


def test_split_epoch_is_the_registered_local_instant():
    assert S.SPLIT_LOCAL.timestamp() == S.SPLIT_EPOCH
    assert S.SPLIT_LOCAL.isoformat() == "2026-10-22T23:00:00+08:00"


# ── Holm, p-value, verdict tokens ────────────────────────────────────────────

def test_holm_step_down():
    adj = S.holm({"F": 0.01, "C": 0.04, "K": 0.03})
    assert adj["F"][0] == pytest.approx(0.03)
    assert adj["K"][0] == pytest.approx(0.06)
    assert adj["C"][0] == pytest.approx(0.06)      # monotone: never below K's
    assert S.ALPHA == 0.05


def test_two_sided_p():
    assert S.two_sided_p([1.0] * 99 + [-1.0]) == pytest.approx(0.02)
    assert S.two_sided_p([0.5, -0.5]) == pytest.approx(1.0)


def test_paired_test_reconciles_with_protocol():
    rows = [dict(date=f"2026-01-{d:02d}", a=0.1 * (d % 3), b=0.0) for d in range(1, 21)]
    out = S.paired_test(rows, n=500)
    assert out["n"] == 20 and out["dates"] == 20
    assert out["lo"] <= out["mean"] <= out["hi"]


def _s(n, mean, lo):
    return dict(n=n, dates=n, mean=mean, lo=lo, hi=lo + 1)


def test_arm_tokens():
    good_s1, good_s2 = _s(100, 0.2, 0.05), _s(40, 0.1, 0.01)
    assert S.arm_token(True, good_s1, 0.001, good_s2, 0.1) == S.THIN
    assert S.arm_token(False, good_s1, 0.01, good_s2, 0.1) == S.CANDIDATE
    assert S.arm_token(False, good_s1, 0.01, good_s2, 0.6) == S.S1_ONLY        # PBO fails
    assert S.arm_token(False, good_s1, 0.01, _s(29, 0.1, 0.01), 0.1) == S.S1_ONLY  # S2 thin
    assert S.arm_token(False, good_s1, 0.01, _s(40, 0.1, -0.01), 0.1) == S.S1_ONLY
    assert S.arm_token(False, _s(100, -0.2, -0.3), 0.01, good_s2, 0.1) == S.LOSES
    assert S.arm_token(False, good_s1, 0.2, good_s2, 0.1) == S.NULL
    assert S.arm_token(False, good_s1, None, good_s2, 0.1) == S.NULL
    assert S.study_token({"F": S.NULL, "B": S.CANDIDATE}) == S.STUDY_FOUND
    assert S.study_token({"F": S.NULL, "B": S.S1_ONLY}) == S.STUDY_NULL


# ── descriptive labels and the PBO matrix ────────────────────────────────────

def test_pv_bucket_and_half():
    assert S.pv_bucket("bull_call_spread", 0.5) == "aligned"
    assert S.pv_bucket("bear_put_spread", 0.5) == "against"
    assert S.pv_bucket("straddle", 0.5) == "neutral"
    assert S.pv_bucket("bull_put_spread", None) == "neutral"
    assert S.half_of("2026-06-30") == "H1" and S.half_of("2026-07-01") == "H2"


def test_pbo_matrix_marks_missing_cells_absent():
    rows = {"P": [dict(date="d1", R=0.2), dict(date="d1", R=0.4), dict(date="d2", R=-0.1)],
            "F": [dict(date="d2", R=0.3)]}
    M, dates = S.pbo_matrix(rows, ("P", "F"))
    assert dates == ["d1", "d2"]
    assert M.shape == (2, 2, 2)
    assert np.allclose(M[0, 0], [0.3, 1.0]) and np.allclose(M[0, 1], [0.0, 0.0])
    assert np.allclose(M[1, 1], [0.3, 1.0])


# ── pick tolerances (Resolved at build 2026-10-22) ───────────────────────────

def _chain_of(calls: dict, puts: dict, spot: float = 100.0):
    ch = IV.Chain("XYZ", EXP)
    for k, dl in calls.items():
        ch.rows[("C", float(k))] = {ED: _row(dl, spot)}
    for k, dl in puts.items():
        ch.rows[("P", float(k))] = {ED: _row(dl, spot)}
    return ch


def test_delta_pick_off_target_is_refused():
    # The only cached call is deep in the money: nearest 0.16 is a 0.93 delta.
    pk = S.pick_strikes(_chain_of({60: 0.93}, {90: -0.15}), ED)
    assert pk.short_why == "delta_off_target"
    for arm in ("C", "G", "S"):
        assert S.chain_legs(arm, "XYZ", EXP, pk) == (None, "delta_off_target")
    # 0.21 is inside the 0.05 band, 0.22 is not.
    assert S.delta_on_target({"Delta": "0.21"}) and S.delta_on_target({"Delta": "-0.11"})
    assert not S.delta_on_target({"Delta": "0.22"})
    assert not S.delta_on_target({"Delta": ""})


def test_atm_pick_off_spot_is_refused():
    # Both types cached only at 90 with spot 100: 10% away, outside 3%.
    pk = S.pick_strikes(_chain_of({90: 0.8, 110: 0.15}, {90: -0.15, 80: -0.05}), ED)
    assert pk.kb == 90.0 and pk.atm_why == "atm_off_spot"
    for arm in ("B", "D"):
        assert S.chain_legs(arm, "XYZ", EXP, pk) == (None, "atm_off_spot")
    assert S.atm_on_spot(103.0, 100.0) and not S.atm_on_spot(103.5, 100.0)


def test_wing_off_target_is_refused():
    # ATM 100, wings 3 = 0.03 x 100 apart in target; 120 is 20 away (> 2x) and
    # 101 is 1 away (< 0.5x).
    far = S.pick_strikes(_chain_of({100: 0.5, 120: 0.1}, {100: -0.5, 97: -0.4}), ED)
    assert far.atm_why == "ok" and far.wing_b_why == "wing_off_target"
    assert S.chain_legs("B", "XYZ", EXP, far) == (None, "wing_off_target")
    assert S.wing_why(100.0, 101.0, 100.0) == "wing_off_target"
    assert S.wing_why(100.0, 101.5, 100.0) == "ok"         # 0.5 x 3 exactly
    assert S.wing_why(100.0, 106.0, 100.0) == "ok"         # 2.0 x 3 exactly
    assert S.wing_why(100.0, None, 100.0) == "no_wing"
    # D needs no wing, so a refused wing does not refuse the straddle.
    assert S.chain_legs("D", "XYZ", EXP, far)[1] == "ok"


def test_credit_ratio_and_bucket():
    fly = [Leg(-1, "XYZ", EXP, 100.0, "Call"), Leg(1, "XYZ", EXP, 105.0, "Call"),
           Leg(-1, "XYZ", EXP, 100.0, "Put"), Leg(1, "XYZ", EXP, 90.0, "Put")]
    assert S.widest_wing(fly) == 10.0
    assert S.credit_ratio(fly, -9.0) == pytest.approx(0.9)
    assert S.credit_ratio(fly, 1.0) is None
    assert [S.ratio_bucket(x) for x in (0.6, 0.7, 0.81)] == ["<=0.6", "0.6-0.8", ">0.8"]
