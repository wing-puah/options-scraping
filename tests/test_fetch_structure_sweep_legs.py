"""structure_sweep S2 fetch planner: target strikes and candidate ladders, on a
synthetic cache. No network, no real cache."""
import math
import statistics
from datetime import date, timedelta

from scripts.backtest.legs import Leg
from scripts.collector.study_legs import fetch_structure_sweep_legs as fs

DAY = date(2026, 9, 10)
EXP = date(2026, 10, 16)
SPOT = 200.0


def _write(cache_dir, t, x, k, typ, delta=None, spot=SPOT, iv=40.0, day=DAY):
    path = fs.cache_path(cache_dir, t, x, k, typ)
    d = "" if delta is None else delta
    path.write_text("Time,IV,Delta,Price~\n" f"{day.isoformat()},{iv},{d},{spot}\n")


def _cache(tmp_path, evidence=()):
    return fs.Cache(tmp_path, evidence=set(evidence))


def _con(k, typ="Call", t="XYZ", x=EXP):
    return (t, x, float(k), typ)


# --- targeting arithmetic ----------------------------------------------------

def _bs_delta(spot, k, iv_pts, days, typ):
    sig_t = iv_pts / 100 * math.sqrt(days / 365)
    d1 = (math.log(spot / k) + sig_t * sig_t / 2) / sig_t
    nd = statistics.NormalDist()
    return nd.cdf(d1) if typ == "Call" else nd.cdf(-d1)


def test_bs_target_strike_inverts_the_delta():
    for typ in ("Call", "Put"):
        k = fs.bs_target_strike(SPOT, 40.0, 36, 0.16, typ)
        assert abs(_bs_delta(SPOT, k, 40.0, 36, typ) - 0.16) < 1e-6
    assert fs.bs_target_strike(SPOT, 40.0, 36, 0.16, "Call") > SPOT
    assert fs.bs_target_strike(SPOT, 40.0, 36, 0.16, "Put") < SPOT


def test_bs_shift_moves_the_right_way_for_each_type():
    # A call at 0.30 is too deep for 0.16: the target is a HIGHER strike.
    assert fs.bs_shift_strike(210.0, 0.30, 0.16, 40.0, 36, "Call") > 210.0
    # A put at 0.30 |delta| is too deep for 0.16: the target is a LOWER strike.
    assert fs.bs_shift_strike(190.0, 0.30, 0.16, 40.0, 36, "Put") < 190.0
    # Too shallow goes the other way.
    assert fs.bs_shift_strike(230.0, 0.05, 0.16, 40.0, 36, "Call") < 230.0
    assert fs.bs_shift_strike(170.0, 0.05, 0.16, 40.0, 36, "Put") > 170.0


def test_bs_shift_agrees_with_target_strike_from_the_spot_strike_family():
    k_true = fs.bs_target_strike(SPOT, 40.0, 36, 0.16, "Call")
    d_at = _bs_delta(SPOT, k_true * 0.95, 40.0, 36, "Call")
    est = fs.bs_shift_strike(k_true * 0.95, d_at, 0.16, 40.0, 36, "Call")
    assert abs(est - k_true) / k_true < 1e-6


# --- candidate ladders -------------------------------------------------------

def test_lattice_tracks_the_price_and_the_standard_step_is_always_a_candidate():
    assert fs.lattice(20.0) == 0.5 and fs.lattice(120.0) == 1.0 and fs.lattice(900.0) == 2.5
    cands = fs.ladder(203.3, 5.0, 203.3)
    assert {203.0, 204.0, 202.5, 205.0} <= set(cands)      # 1.0 lattice + 2.5 step
    assert 203.5 not in cands                              # no half dollars at $203
    assert fs.ladder(20.3, 1.0, 20.3)[:2] == [20.5, 20.0]  # nearest first, 0.5 lattice


def test_ladder_orders_nearest_first_and_ties_go_lower():
    cands = fs.ladder(100.0, 3.0, 100.0)
    assert cands[0] == 100.0
    assert cands[1:3] == [99.0, 101.0]                     # tie -> lower first
    d = [abs(k - 100.0) for k in cands]
    assert d == sorted(d)


def test_ladder_includes_cached_strikes_in_range_only():
    cands = fs.ladder(100.0, 2.0, 100.0, extra=[100.25, 150.0])
    assert 100.25 in cands and 150.0 not in cands


def test_on_std_grid_follows_the_standard_step():
    assert fs.on_std_grid(202.5, 203.0) and not fs.on_std_grid(203.0, 203.0)
    assert fs.on_std_grid(1030.0, 1027.0) and not fs.on_std_grid(1027.5, 1027.0)


def test_wing_target_sits_three_percent_out_on_the_right_side():
    assert fs.wing_target(200.0, 200.0, "Call") == 206.0
    assert fs.wing_target(200.0, 200.0, "Put") == 194.0


# --- walks -------------------------------------------------------------------

def test_atm_walk_names_the_nearest_candidates_when_nothing_is_cached(tmp_path):
    c = _cache(tmp_path)
    w = fs.atm_walk(c, "XYZ", EXP, DAY, 203.3)
    assert w.status == "await"
    names = [(k, t[0]) for _t, _x, k, t in w.fetch]
    assert names[:2] == [(203.0, "C"), (203.0, "P")]       # nearest first, both types
    assert max(k for _t, _x, k, _ty in w.fetch) <= 205.0   # stops at the 202.5 grid strike


def test_atm_walk_is_built_only_on_a_strike_with_both_types_quoted(tmp_path):
    _write(tmp_path, "XYZ", EXP, 200.0, "Call")
    c = _cache(tmp_path)
    assert fs.atm_walk(c, "XYZ", EXP, DAY, 200.2).status == "await"   # the put is open
    _write(tmp_path, "XYZ", EXP, 200.0, "Put")
    c = _cache(tmp_path)
    w = fs.atm_walk(c, "XYZ", EXP, DAY, 200.2)
    assert (w.status, w.strike, w.fetch) == ("built", 200.0, ())


def test_atm_walk_proves_a_nearer_strike_before_taking_a_farther_cached_one(tmp_path):
    # 205 is cached with both types, but 200 (nearer) is not: the walk must probe it.
    for typ in ("Call", "Put"):
        _write(tmp_path, "XYZ", EXP, 205.0, typ)
    c = _cache(tmp_path)
    w = fs.atm_walk(c, "XYZ", EXP, DAY, 200.4)
    assert w.status == "await" and (("XYZ", EXP, 200.0, "Call") in w.fetch)


def test_atm_walk_passes_an_evidenced_unlisted_strike_without_a_probe(tmp_path):
    ev = {fs.stem_of(_con(200)), fs.stem_of(_con(200, "Put"))}
    c = _cache(tmp_path, evidence=ev)
    w = fs.atm_walk(c, "XYZ", EXP, DAY, 200.2)
    assert all(k != 200.0 for _t, _x, k, _ty in w.fetch)
    assert w.seen[_con(200)] == fs.UNLISTED


def test_a_file_without_an_entry_day_row_is_dead_not_open(tmp_path):
    _write(tmp_path, "XYZ", EXP, 200.0, "Call", day=DAY + timedelta(days=3))
    c = _cache(tmp_path)
    assert c.state(_con(200), DAY) == fs.NOQUOTE
    assert c.state(_con(195), DAY) == fs.OPEN
    c.attempted.add(fs.stem_of(_con(195)))
    assert c.state(_con(195), DAY) == fs.FAILED            # asked once this run


def test_delta_walk_with_nothing_known_probes_around_the_bs_estimate(tmp_path):
    _write(tmp_path, "XYZ", EXP, 200.0, "Call", delta=0.5)   # a call is known; no PUT is
    w = fs.delta_walk(_cache(tmp_path), "XYZ", EXP, DAY, SPOT, "Put", 40.0)
    est = fs.bs_target_strike(SPOT, 40.0, (EXP - DAY).days, 0.16, "Put")
    assert w.status == "await" and w.reason == "no_delta_known"
    assert all(ty == "Put" for _t, _x, _k, ty in w.fetch)
    assert min(abs(k - est) for _t, _x, k, _ty in w.fetch) < 3.0


def test_delta_walk_call_is_proven_by_a_known_neighbour_beyond_the_target(tmp_path):
    # |delta| 0.19 at 210 and 0.08 at 220, 0.16 between: nothing in between is
    # cached, so the walk meets open strikes first, awaits and names them.
    _write(tmp_path, "XYZ", EXP, 210.0, "Call", delta=0.19)
    _write(tmp_path, "XYZ", EXP, 220.0, "Call", delta=0.08)
    w = fs.delta_walk(_cache(tmp_path), "XYZ", EXP, DAY, SPOT, "Call", 40.0)
    assert w.status == "await" and w.strike == 210.0
    assert w.fetch and all(210.0 < k < 220.0 for _t, _x, k, _ty in w.fetch)
    # Fill every step between: 215 (0.15) is now proven nearest, 212.5 (0.17) is its neighbour.
    for k, d in ((212.5, 0.17), (215.0, 0.15), (217.5, 0.11)):
        _write(tmp_path, "XYZ", EXP, k, "Call", delta=d)
    w = fs.delta_walk(_cache(tmp_path), "XYZ", EXP, DAY, SPOT, "Call", 40.0)
    assert (w.status, w.strike, w.fetch) == ("built", 212.5, ())   # |0.17-0.16| = |0.15-0.16|, tie lower


def test_delta_walk_put_walks_downward_and_uses_the_signed_delta(tmp_path):
    # Put |delta| 0.30 at 190: too deep, so the target is a LOWER strike.
    _write(tmp_path, "XYZ", EXP, 190.0, "Put", delta=-0.30)
    c = _cache(tmp_path)
    w = fs.delta_walk(c, "XYZ", EXP, DAY, SPOT, "Put", 40.0)
    assert w.status == "await" and w.strike == 190.0
    assert all(k < 190.0 for _t, _x, k, _ty in w.fetch)
    # A positive Delta on a put file is not a usable put delta.
    _write(tmp_path, "XYZ", EXP, 185.0, "Put", delta=0.2)
    c = _cache(tmp_path)
    assert fs.delta_walk(c, "XYZ", EXP, DAY, SPOT, "Put", 40.0).strike == 190.0


def test_delta_walk_exact_hit_is_built(tmp_path):
    _write(tmp_path, "XYZ", EXP, 214.0, "Call", delta=0.16)
    w = fs.delta_walk(_cache(tmp_path), "XYZ", EXP, DAY, SPOT, "Call", 40.0)
    assert (w.status, w.strike) == ("built", 214.0)


def test_wing_walk_is_strictly_outside_the_short_and_nearest_the_target(tmp_path):
    c = _cache(tmp_path)
    w = fs.wing_walk(c, "XYZ", EXP, DAY, SPOT, 210.0, "Call")
    assert w.status == "await"
    assert all(k > 210.0 for _t, _x, k, _ty in w.fetch)
    assert w.fetch[0][2] == 216.0                           # 210 + 0.03 x 200
    wp = fs.wing_walk(c, "XYZ", EXP, DAY, SPOT, 190.0, "Put")
    assert all(k < 190.0 for _t, _x, k, _ty in wp.fetch)
    assert wp.fetch[0][2] == 184.0 and all(ty == "Put" for _t, _x, _k, ty in wp.fetch)


def test_wing_walk_builds_on_a_cached_wing_and_never_returns_the_short(tmp_path):
    _write(tmp_path, "XYZ", EXP, 216.0, "Call")
    w = fs.wing_walk(_cache(tmp_path), "XYZ", EXP, DAY, SPOT, 210.0, "Call")
    assert (w.status, w.strike) == ("built", 216.0)
    # A tiny target distance would land on the short: the walk still steps out.
    w = fs.wing_walk(_cache(tmp_path), "XYZ", EXP, DAY, 20.0, 20.0, "Call")
    assert all(k > 20.0 for _t, _x, k, _ty in w.fetch)


# --- ARM K and ARM T ---------------------------------------------------------

def test_back_expiry_candidates_start_fourteen_days_after_the_front(tmp_path):
    c = _cache(tmp_path)
    cands = fs.back_expiry_candidates(c, "XYZ", EXP)
    assert cands == sorted(cands)
    assert min(cands) >= EXP + timedelta(days=fs.BACK_GAP_DAYS)
    assert all(x.weekday() == 4 or x.weekday() == 3 for x in cands)     # Fri (or holiday Thu)
    assert EXP + timedelta(days=21) in cands                 # a Friday three weeks on


def test_back_expiry_candidates_include_cached_expiries_in_reach(tmp_path):
    odd = EXP + timedelta(days=20)                           # a Thursday
    _write(tmp_path, "XYZ", odd, 150.0, "Call")
    assert odd in fs.back_expiry_candidates(_cache(tmp_path), "XYZ", EXP)


def test_back_walk_skips_a_listed_but_unquoted_weekly_and_takes_the_next(tmp_path):
    first = EXP + timedelta(days=14)                         # a Friday
    second = first + timedelta(days=7)
    _write(tmp_path, "XYZ", first, 200.0, "Call", day=DAY + timedelta(days=5))   # not yet quoting
    _write(tmp_path, "XYZ", second, 200.0, "Call")
    w = fs.back_walk(_cache(tmp_path), "XYZ", EXP, DAY, SPOT, 200.0)
    assert w.status == "built"
    assert w.seen[("XYZ", first, 200.0, "Call")] == fs.NOQUOTE


def test_swap_contracts_only_for_a_plain_vertical():
    bull = (Leg(1, "XYZ", EXP, 200.0, "Call"), Leg(-1, "XYZ", EXP, 220.0, "Call"))
    assert fs.swap_contracts(bull) == [("XYZ", EXP, 200.0, "Put"), ("XYZ", EXP, 220.0, "Put")]
    bear = (Leg(1, "XYZ", EXP, 200.0, "Put"), Leg(-1, "XYZ", EXP, 180.0, "Put"))
    assert [c[3] for c in fs.swap_contracts(bear)] == ["Call", "Call"]
    cal = (Leg(-1, "XYZ", EXP, 200.0, "Call"), Leg(1, "XYZ", EXP + timedelta(days=28), 200.0, "Call"))
    assert fs.swap_contracts(cal) == []
    assert fs.swap_contracts((Leg(1, "XYZ", EXP, 200.0, "Call"),)) == []


# --- the plan and the report -------------------------------------------------

def _ctx(legs=None):
    legs = legs or (Leg(1, "XYZ", EXP, 200.0, "Call"), Leg(-1, "XYZ", EXP, 220.0, "Call"))
    return fs.RowCtx("row", "XYZ", EXP, DAY, SPOT, 40.0, tuple(legs))


def test_plan_row_stages_dependents_as_provisional_and_never_requests_them(tmp_path):
    c = _cache(tmp_path)
    plan = fs.plan_row(c, _ctx())
    assert set(plan.walks) == set(fs.GROUPS)
    for g in ("C_wing", "B_wing", "K_back"):
        assert all(w.provisional for w in plan.walks[g])
    for g in ("CGS_delta", "BD_atm", "T_swap"):
        assert not any(w.provisional for w in plan.walks[g])
    now = fs.round_targets([plan])
    wings = {con for g in ("C_wing", "B_wing", "K_back") for w in plan.walks[g] for con in w.fetch}
    assert now and not (set(now) & wings)                    # round 1 holds no dependent contract


def test_round_targets_are_unique_and_the_groups_filter_applies(tmp_path):
    c = _cache(tmp_path)
    plans = [fs.plan_row(c, _ctx()), fs.plan_row(c, _ctx())]
    now = fs.round_targets(plans)
    assert len(now) == len(set(now))
    only = fs.round_targets([fs.plan_row(c, _ctx(), ("T_swap",))])
    assert only == [("XYZ", EXP, 200.0, "Put"), ("XYZ", EXP, 220.0, "Put")]


def test_census_counts_rows_needing_a_fetch_and_cached_contracts(tmp_path):
    for typ in ("Call", "Put"):
        _write(tmp_path, "XYZ", EXP, 200.0, typ)
    c = _cache(tmp_path)
    cs = fs.census([fs.plan_row(c, _ctx())])
    assert cs["BD_atm"].rows == 1 and cs["BD_atm"].rows_need == 0   # ATM pair is cached
    assert _con(200) in cs["BD_atm"].ok
    assert cs["T_swap"].rows_need == 1 and cs["T_swap"].now == {_con(220, "Put")}   # the 200 put is cached
