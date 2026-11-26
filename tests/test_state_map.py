"""state_map — research/pre-registrations/f1_selection/regime/state_map.md.

Synthetic data only: no cached market file and no option cache is read, and no
figure below comes from real data. Covers the episodes (onset, trigger, merge,
the dropped-unclosed rule, exclusion zones, follow-ons), the calm-day controls,
each candidate as of its close, the parametrised labeler pinned to MechLabeler,
the Q3 onsets and clusters, every verdict word, the Holm sizes, the in-sample
cut, Q4's selection and pricing, and Q5's population.
"""
from __future__ import annotations

import ast
import math
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from lib import mech_regime as MR
from scripts.backtest_study import run as runner
from scripts.backtest_study.f1_selection.benchmark import mechanical_baseline as MBL
from scripts.backtest_study.f1_selection.regime import state_map as S
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF


# ── synthetic calendars ─────────────────────────────────────────────────────

def weekdays(n: int, start: str = "2005-01-03") -> list[str]:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def mk_cal(close, vix=None, vix3m=None, credit=None, adj=None, start="2005-01-03", dates=None) -> S.Cal:
    close = np.asarray(close, float)
    n = len(close)
    nan = np.full(n, np.nan)
    return S.Cal(dates=dates or weekdays(n, start), close=close,
                 adj=np.asarray(adj if adj is not None else close, float),
                 vix=np.asarray(vix, float) if vix is not None else nan.copy(),
                 vix3m=np.asarray(vix3m, float) if vix3m is not None else nan.copy(),
                 credit=np.asarray(credit, float) if credit is not None else nan.copy())


def nodes(points, n):
    xs, ys = zip(*points)
    return np.interp(np.arange(n), xs, ys)


def fall_cal(points, n, vix=15.0) -> S.Cal:
    return mk_cal(nodes(points, n), vix=np.full(n, vix), start="2016-01-04")


def crashy_cal(start: str, end: str, seed: int = 3, every: int = 230) -> S.Cal:
    """A random walk with a 12% fall every `every` sessions and a VIX that jumps in each."""
    rng = np.random.default_rng(seed)
    d, dates = date.fromisoformat(start), []
    while d <= date.fromisoformat(end):
        if d.weekday() < 5:
            dates.append(d.isoformat())
        d += timedelta(days=1)
    n = len(dates)
    r = rng.normal(0.0004, 0.008, n)
    vix = 14 + 4 * rng.random(n)
    for s0 in range(120, n - 40, every):
        r[s0:s0 + 14] -= 0.0095
        vix[s0:s0 + 20] += np.linspace(8, 22, 20)
    px = 100 * np.exp(np.cumsum(r))
    adj = px * np.linspace(0.6, 1.0, n)
    credit = 1.0 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    return mk_cal(px, vix=vix, vix3m=vix * 1.05, credit=credit, adj=adj, dates=dates)


# ── episodes: onset, trigger, merge, unclosed ───────────────────────────────

BASE = [(0, 100.0), (80, 108.0), (95, 96.0), (115, 106.0), (140, 112.0)]


def test_episode_onset_trigger_trough_and_closed():
    cal = fall_cal(BASE, 150)
    eps = S.build_episodes(cal, "E-DD8")
    assert len(eps) == 1
    e = eps[0]
    assert (e.p, e.trough, e.closed) == (80, 95, True)
    # g: the first session at or below 0.92 x the peak close, not the trough
    line = 0.92 * cal.close[80]
    assert e.g == next(i for i in range(81, 150) if cal.close[i] <= line)
    assert cal.close[e.g - 1] > line and 80 < e.g < e.trough


def test_a_smaller_fall_is_an_e_dd5_episode_only():
    cal = fall_cal([(0, 100.0), (80, 108.0), (95, 101.5), (115, 108.0), (140, 112.0)], 150)
    assert S.build_episodes(cal, "E-DD8") == []
    assert len(S.build_episodes(cal, "E-DD5")) == 1


def test_two_falls_off_one_high_merge_to_the_earliest_peak_and_first_trigger():
    pts = [(0, 100.0), (80, 108.0), (95, 96.0), (112, 107.0), (128, 94.0), (150, 100.0), (175, 112.0)]
    cal = fall_cal(pts, 190)
    eps = S.build_episodes(cal, "E-DD8")
    assert len(eps) == 1
    e = eps[0]
    assert e.p == 80
    first_g = next(i for i in range(81, 190) if cal.close[i] <= 0.92 * cal.close[80])
    assert e.g == first_g                      # the first sub-episode's trigger
    assert cal.close[e.trough] == cal.close[128]   # the deeper trough is kept
    assert e.trough == 128


def test_unclosed_episode_is_flagged_and_dropped_from_the_graded_cells():
    cal = fall_cal([(0, 100.0), (80, 108.0), (100, 94.0)], 101)
    eps = S.build_episodes(cal, "E-DD8")
    assert len(eps) == 1 and eps[0].closed is False
    assert S.split_eps(eps, eps[0].win) == []


def test_an_episode_with_no_trigger_session_is_dropped_and_counted(monkeypatch):
    cal = fall_cal([(0, 100.0), (50, 100.0)], 60)
    fake = SimpleNamespace(peak_i=59, trough_i=59, closed=False)
    monkeypatch.setattr(S.IBH, "episodes", lambda s, name, defs=None: [fake])
    counter = S.Counter()
    assert S.build_episodes(cal, "E-DD8", counter=counter) == []
    assert counter["no_trigger"] == 1


def test_an_episode_ends_before_the_recovery_and_done_covers_peak_to_end():
    from scripts.backtest_study.f5_hedging import index_bear_hedge as IBH
    cal = fall_cal(BASE, 150)
    e = S.build_episodes(cal, "E-DD8")[0]
    dd = IBH.drawdowns(cal.close.tolist(), 63)
    r = next(j for j in range(e.trough + 1, 150) if dd[j] > -0.02)
    assert e.end == r - 1 and e.end > e.trough
    assert S.episode_of([e], e.trough + 3) is e and S.episode_of([e], e.end) is e
    assert S.episode_of([e], e.end + 1) is None and S.episode_of([e], e.p - 1) is None


def test_episode_window_code_follows_the_onset_date():
    cal = fall_cal(BASE, 150)
    assert S.build_episodes(cal, "E-DD8")[0].win == 1        # 2016 is the test window
    early = mk_cal(nodes(BASE, 150), vix=np.full(150, 15.0), start="2005-01-03")
    assert S.build_episodes(early, "E-DD8")[0].win == 0


def test_the_episode_code_is_imported_not_restated():
    from scripts.backtest_study.f5_hedging import index_bear_hedge as IBH
    assert S.IBH is IBH
    assert S.gate_hash() == []


# ── exclusion zones, follow-ons, the control-window rule ────────────────────

def test_zone_runs_from_p_minus_21_to_trough_plus_21_and_an_unclosed_one_to_the_end():
    n = 600
    e = S.Ep("E-DD8", 300, 310, 320, True)
    z = S.zone_mask([e], n)
    assert z[279] and z[341] and not z[278] and not z[342]
    u = S.Ep("E-DD8", 500, 510, 520, False)
    zu = S.zone_mask([u], n)
    assert zu[479] and zu[n - 1] and not zu[478]


def test_follow_on_is_an_episode_whose_lead_window_touches_an_earlier_zone():
    n = 2000
    a = S.Ep("E-DD8", 300, 310, 320, True)           # zone to 341
    b = S.Ep("E-DD8", 350, 360, 370, True)           # lead window 340..349 touches 341
    c = S.Ep("E-DD8", 700, 710, 720, True)           # far away
    d = S.Ep("E-DD8", 352, 360, 370, True)           # lead window starts at 342: clear of a's zone
    S.mark_follow_ons([a, b, c], n)
    assert [x.follow_on for x in (a, b, c)] == [False, True, False]
    S.mark_follow_ons([a, d], n)
    assert d.follow_on is False


def _flat_ctx(n=700, val=None, win=None):
    cal = mk_cal(np.ones(n))
    v = np.zeros(n) if val is None else val
    return S.Ctx(cal, {k: v.copy() for k in S.CANDS}, np.ones(n, dtype=int) if win is None else win)


def test_controls_exclude_zones_their_lead_windows_and_the_far_range():
    n = 700
    ctx = _flat_ctx(n)
    e = S.Ep("E-DD8", 300, 310, 320, True)
    zone = S.zone_mask([e], n)
    fd = S.controls(ctx, zone, "C1", e, 10, "lead")
    # d in 48..552; out: d in 279..341 and d with d-10..d-1 touching it, 279..351
    assert len(fd) == (552 - 48 + 1) - (351 - 279 + 1)


def test_controls_stay_in_the_episodes_own_window():
    n = 700
    win = np.where(np.arange(n) < 200, 0, 1)
    ctx = _flat_ctx(n, win=win)
    e = S.Ep("E-DD8", 300, 310, 320, True, win=1)
    zone = S.zone_mask([e], n)
    fd = S.controls(ctx, zone, "C1", e, 10, "lead")
    assert len(fd) == (552 - 200 + 1) - (351 - 279 + 1)


def test_coincident_controls_also_keep_their_whole_window_out_of_zones():
    n = 700
    ctx = _flat_ctx(n)
    e = S.Ep("E-DD8", 300, 330, 340, True)
    zone = S.zone_mask([e], n)                        # 279..361
    lead = S.controls(ctx, zone, "C1", e, 10, "lead")
    coin = S.controls(ctx, zone, "C1", e, 10, "coin")
    assert len(coin) < len(lead)
    # a coincident window d .. d+30 may not reach 279, so d = 248 is out, d = 247 is in
    d = np.arange(48, 553)
    ok = ~zone[d] & ~S.zone_any(zone, d - 10, d - 1) & ~S.zone_any(zone, d, d + 30)
    assert len(coin) == int(ok.sum())


def test_an_episode_with_under_20_controls_leaves_the_cell_and_is_counted():
    n = 700
    ctx = _flat_ctx(n)
    eps = [S.Ep("E-DD8", 300, 310, 320, True)]
    z = np.ones(n, dtype=bool)
    z[:5] = False
    xs, kept, drops = S.cell_xs(ctx, z, eps, "C1", 10, "lead")
    assert len(xs) == 0 and drops["few_controls"] == 1


def test_an_episode_with_a_missing_value_in_its_window_leaves_that_candidate_only():
    n = 700
    val = np.zeros(n)
    val[295] = np.nan
    ctx = _flat_ctx(n, val=val)
    e = S.Ep("E-DD8", 300, 310, 320, True)
    zone = S.zone_mask([e], n)
    assert S.lift(ctx, zone, "C1", e, 10, "lead") == (None, "missing")
    ctx2 = _flat_ctx(n)
    x, why = S.lift(ctx2, zone, "C1", e, 10, "lead")
    assert why == "ok" and x == 0.0


def test_lift_is_the_lead_share_minus_the_mean_control_share():
    n = 700
    val = np.zeros(n)
    val[290:300] = 1.0                                  # on for the whole 10-session lead window
    ctx = _flat_ctx(n, val=val)
    e = S.Ep("E-DD8", 300, 310, 320, True)
    zone = S.zone_mask([e], n)
    x, _ = S.lift(ctx, zone, "C1", e, 10, "lead")
    assert x == pytest.approx(1.0)                      # controls are all off


# ── candidates, as of the close ─────────────────────────────────────────────

def test_c1_c3_c4_thresholds_are_the_mech_label_lines():
    vix = np.full(30, 18.0)
    vix[10] = 20.0
    vix3m = np.full(30, 19.0)
    cal = mk_cal(np.full(30, 100.0), vix=vix, vix3m=vix3m)
    assert S.cand_at(cal, 10)["C1"] == 1.0 and S.cand_at(cal, 9)["C1"] == 0.0     # 20 exactly is on
    up = mk_cal(np.full(30, 100.0), vix=np.array([20.0] * 5 + [25.0] + [20.0] * 24))
    assert S.cand_at(up, 5)["C3"] == 1.0                                          # +25% exactly is on
    assert S.cand_at(up, 6)["C3"] == 0.0 and math.isnan(S.cand_at(up, 4)["C3"])
    assert S.cand_at(cal, 5)["C4"] == 0.0 and S.cand_at(mk_cal(np.ones(30), vix=vix, vix3m=vix - 1), 5)["C4"] == 1.0


def test_price_candidates_c5_c6_c7_and_the_history_they_need():
    px = np.concatenate([np.full(210, 100.0), np.full(5, 90.0)])
    cal = mk_cal(px)
    assert math.isnan(S.cand_at(cal, 48)["C5"]) and not math.isnan(S.cand_at(cal, 49)["C5"])
    assert math.isnan(S.cand_at(cal, 198)["C6"]) and not math.isnan(S.cand_at(cal, 199)["C6"])
    assert math.isnan(S.cand_at(cal, 19)["C7"]) and S.cand_at(cal, 20)["C7"] == 0.0
    got = S.cand_at(cal, 214)
    assert (got["C5"], got["C6"], got["C7"]) == (1.0, 1.0, 1.0)


def test_c2_is_a_midrank_percentile_over_the_252_prior_sessions():
    n = 300
    vix = np.arange(n, dtype=float) % 50 + 10.0
    cal = mk_cal(np.full(n, 100.0), vix=vix)
    assert math.isnan(S.cand_at(cal, 251)["C2"]) and not math.isnan(S.cand_at(cal, 252)["C2"])
    win = vix[0:252]
    share = (np.sum(win < vix[252]) + 0.5 * np.sum(win == vix[252])) / 252
    assert S.cand_at(cal, 252)["C2"] == (1.0 if share >= 0.80 else 0.0)
    high = vix.copy()
    high[260] = 500.0
    assert S.cand_at(mk_cal(np.full(n, 100.0), vix=high), 260)["C2"] == 1.0


def test_c8_compares_21_session_realised_vol_with_the_vix_close():
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.01, 60)
    adj = 100 * np.exp(np.cumsum(r))
    t = 50
    seg = np.log(adj[t - 20:t + 1] / adj[t - 21:t])
    rv = math.sqrt(float(np.mean(seg * seg))) * math.sqrt(252) * 100
    lo = mk_cal(adj, vix=np.full(60, rv - 1.0), adj=adj)
    hi = mk_cal(adj, vix=np.full(60, rv + 1.0), adj=adj)
    assert S.cand_at(lo, t)["C8"] == 1.0 and S.cand_at(hi, t)["C8"] == 0.0
    assert math.isnan(S.cand_at(lo, 20)["C8"])


def test_c9_credit_line_is_strict_after_rounding():
    cr = np.full(40, 100.0)
    cr[25] = 99.0                                        # exactly -1.0% over 20 sessions: not on
    assert S.cand_at(mk_cal(np.ones(40), credit=cr), 25)["C9"] == 0.0
    cr3 = np.full(40, 100.0)
    cr3[25] = 98.9
    assert S.cand_at(mk_cal(np.ones(40), credit=cr3), 25)["C9"] == 1.0
    assert math.isnan(S.cand_at(mk_cal(np.ones(40)), 25)["C9"])


def test_no_candidate_reads_a_later_close():
    cal = crashy_cal("2010-01-04", "2012-12-31")
    full = S.cand_series(cal)
    bumped = S.Cal(cal.dates, cal.close.copy(), cal.adj.copy(), cal.vix.copy(), cal.vix3m.copy(),
                   cal.credit.copy())
    t = 400
    for arr in (bumped.close, bumped.adj, bumped.vix, bumped.vix3m, bumped.credit):
        arr[t + 1:] *= 3.0
    again = S.cand_series(bumped)
    for k in S.CANDS:
        a, b = full[k][:t + 1], again[k][:t + 1]
        assert np.array_equal(a, b, equal_nan=True), k
    # removing every later close changes nothing either
    cut = S.cut_cal(cal, cal.dates[t])
    for k, arr in S.cand_series(cut).items():
        assert np.array_equal(arr, full[k][:t + 1], equal_nan=True), k


def test_gx_gate_passes_on_a_causal_label_and_catches_a_peek(monkeypatch):
    cal = crashy_cal("2010-01-04", "2011-06-30")
    assert S.gate_lookahead(cal) > 0
    real = S.mech_table

    def peeking(dates, spy, vix, sma=50):
        rows = real(dates, spy, vix, sma)
        for i in range(len(rows) - 1):                   # reads the next close
            rows[i]["spy_below_sma"] = bool(spy[i + 1] > spy[i])
        return rows

    monkeypatch.setattr(S, "mech_table", peeking)
    with pytest.raises(AssertionError):
        S.gate_lookahead(cal)


# ── the labeler, pinned ─────────────────────────────────────────────────────

def _write_mech_fixture(tmp_path, n=330, seed=5):
    rng = np.random.default_rng(seed)
    spy = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, n)))
    vix = 14 + 25 * rng.random(n)
    vix[40] = np.nan
    vix[200] = np.nan
    dates = weekdays(n, "2018-01-02")
    p = tmp_path / "mech.csv"
    p.write_text("date,spy_close,vix_close\n" + "\n".join(
        f"{d},{float(s)!r},{'' if v != v else repr(float(v))}" for d, s, v in zip(dates, spy, vix)) + "\n")
    return p, dates, spy, vix


def test_parametrised_labeler_at_length_50_equals_mechlabeler_on_every_session(tmp_path):
    p, dates, spy, vix = _write_mech_fixture(tmp_path)
    ref = MR.compute_mech_table(p)
    mine = S.mech_table(dates, spy, vix, 50)
    assert len(ref) == len(mine)
    for a, b in zip(ref, mine):
        assert a == b
    lab = MR.MechLabeler.from_csv(p)
    got = S.labels_from_labeler(p, dates)
    for i, d in enumerate(dates):
        direction, vol, ok, _ = lab.label(d)
        assert (got.direction[i], got.vol[i], bool(got.ok[i])) == (direction if ok else None,
                                                                   vol if ok else None, ok)


def test_the_200_day_twin_changes_only_the_sma_length(tmp_path):
    p, dates, spy, vix = _write_mech_fixture(tmp_path, n=330)
    t50, t200 = S.mech_table(dates, spy, vix, 50), S.mech_table(dates, spy, vix, 200)
    assert [r["dir_ok"] for r in t200[:199]] == [False] * 199 and t200[199]["dir_ok"]
    assert [r["mech_vol"] for r in t50] == [r["mech_vol"] for r in t200]      # vol part unchanged
    i = 250
    sma = sum(spy[i - 199:i + 1]) / 200
    ret = spy[i] / spy[i - 20] - 1
    want = "BEAR" if spy[i] < sma and ret < 0 else "BULL" if spy[i] > sma and ret > 0 else "RANGE"
    assert t200[i]["mech_direction"] == want


def test_the_missing_vix_session_has_a_direction_and_no_vol(tmp_path):
    p, dates, spy, vix = _write_mech_fixture(tmp_path)
    lab = S.labels_from_table(S.mech_table(dates, spy, vix, 50))
    assert lab.ok[200] and lab.vol[200] is None and lab.direction[200] is not None
    assert not lab.ok[10] and lab.direction[10] is None


# ── Q1 ──────────────────────────────────────────────────────────────────────

def test_run_lengths_break_on_an_unlabelled_session():
    runs = S.run_lengths(["A", "A", None, "A", "B", "B", "B"])
    assert runs == {"A": [2, 1], "B": [3]}
    st = S.run_stats([1, 2, 3, 10])
    assert st["count"] == 4 and st["median"] == 2.5 and st["longest"] == 10


def test_transitions_count_only_labelled_pairs():
    c = S.transitions(["A", "A", None, "B", "A"])
    assert c == {("A", "A"): 1, ("B", "A"): 1}


# ── Q3: onsets, entry, clusters ─────────────────────────────────────────────

def test_onset_needs_ten_quiet_labelled_sessions_before_it():
    n = 80
    holds = np.zeros(n, dtype=bool)
    holds[[30, 35, 41, 52, 63]] = True
    has = np.ones(n, dtype=bool)
    # 35 and 41 each have a held session in the 10 before them; 52 and 63 do not
    assert S.onsets(holds, has) == [30, 52, 63]


def test_the_rearm_parameter_changes_the_onset_set():
    n = 80
    holds = np.zeros(n, dtype=bool)
    holds[[30, 37]] = True
    has = np.ones(n, dtype=bool)
    assert S.onsets(holds, has, 10) == [30]
    assert S.onsets(holds, has, 5) == [30, 37]


def test_an_unlabelled_session_inside_the_rearm_blocks_the_onset():
    n = 60
    holds = np.zeros(n, dtype=bool)
    holds[30] = True
    has = np.ones(n, dtype=bool)
    has[25] = False
    assert S.onsets(holds, has) == []
    assert S.onsets(np.r_[np.zeros(5, bool), np.ones(1, bool), np.zeros(54, bool)], np.ones(60, bool)) == []  # D < 10


def test_entry_is_the_next_close_and_a_window_past_the_data_is_nan():
    adj = np.array([100.0, 101.0, 103.0, 102.0, 106.0, 107.0])
    r = S.fwd_log_return(adj, 2)
    assert r[0] == pytest.approx(math.log(adj[3] / adj[1]))           # D = 0 enters at A[1], exits at A[3]
    assert r[2] == pytest.approx(math.log(adj[5] / adj[3]))
    assert np.isnan(r[4]) and np.isnan(r[5])
    r0 = S.fwd_log_return(adj, 2, lag=0)
    assert r0[0] == pytest.approx(math.log(adj[2] / adj[0]))


def test_further_fall_is_the_worst_close_after_entry_capped_at_zero():
    adj = np.array([100.0, 100.0, 98.0, 95.0, 99.0, 104.0, 105.0, 106.0])
    ff = S.further_fall(adj, 3)
    assert ff[0] == pytest.approx(95.0 / 100.0 - 1.0)
    assert ff[3] == 0.0                                                # nothing below the entry close


def test_q3_cell_clusters_onsets_by_calendar_month_and_blocks_other_days():
    n = 120
    dates = weekdays(n, "2020-01-01")
    R = np.linspace(-0.01, 0.01, n)
    ons = [5, 8 + 10, 60]
    cell = S.q3_cell(R, dates, ons, 0, n - 1)
    months = {dates[d][:7] for d in ons}
    assert cell.n_on == 3 and cell.n_clusters == len(months)
    assert cell.cl_cnt.sum() == 3 and cell.n_other == n - 3
    assert cell.bl_cnt.sum() == n - 3
    assert cell.mean_on == pytest.approx(np.mean(R[ons]))
    assert cell.mean_other == pytest.approx(np.mean(np.delete(R, ons)))
    assert cell.D == pytest.approx(cell.mean_on - cell.mean_other)
    c42 = S.q3_cell(R, dates, ons, 0, n - 1, block=42)
    assert len(c42.bl_cnt) < len(cell.bl_cnt)


def test_other_days_exclude_every_onset_but_an_onset_without_a_closed_window_is_not_counted():
    n = 50
    dates = weekdays(n, "2020-01-01")
    R = np.full(n, 0.01)
    R[45:] = np.nan
    cell = S.q3_cell(R, dates, [20, 46], 0, n - 1)
    assert cell.n_on == 1 and cell.n_truncated == 1      # the 46 onset has no outcome, and is counted
    assert cell.n_other == 44                   # 50 sessions - 5 NaN (45..49) - the 20 onset (46 sits in the NaNs)


# ── Q3 end to end on a constructed book ─────────────────────────────────────

def _onset_book(sign: float, months: int = 14, n_per: int = 30):
    """A calendar with one onset a month and a steady move after each onset's entry."""
    n = months * n_per + 60
    dates = weekdays(n, "2016-02-01")
    r = np.zeros(n)
    holds = np.zeros(n, dtype=bool)
    has = np.ones(n, dtype=bool)
    for m in range(months):
        d = 40 + m * n_per
        holds[d] = True
        r[d + 2:d + 23] = sign * 0.004
    adj = 100 * np.exp(np.cumsum(r))
    cal = mk_cal(adj, dates=dates)
    flags = {s: (holds, has) for s in ("S-BEAR", "S-EVOL", "S-BEAR200", "S-BOTH")}
    return cal, flags


def _draws(cal, n_boot=400):
    return S.Draws(n_boot, S.SEED, 200, 200, cal.n // 21 + 5)


def test_room_left_is_reachable_and_needs_a_falling_mean():
    cal, flags = _onset_book(-1.0)
    outs = S.grade_q3(cal, flags, _draws(cal), None, (0, cal.n - 1), None)
    assert all(o.cell.n_clusters >= S.FLOOR for o in outs.values())
    assert outs["B10"].word == S.ROOM_LEFT and outs["B10"].res.hi < 0 and outs["B10"].cell.mean_on < 0
    assert outs["V10"].word == S.ROOM_LEFT


def test_too_late_is_reachable():
    cal, flags = _onset_book(+1.0)
    outs = S.grade_q3(cal, flags, _draws(cal), None, (0, cal.n - 1), None)
    assert outs["B10"].word == S.TOO_LATE and outs["B10"].res.lo > 0


def test_null_when_the_move_after_the_signal_looks_like_other_days():
    cal, flags = _onset_book(0.0)
    outs = S.grade_q3(cal, flags, _draws(cal), None, (0, cal.n - 1), None)
    assert all(o.word == S.NULL for o in outs.values())


def test_q3_below_the_cluster_floor_is_underpowered_and_at_the_floor_it_is_not():
    cal, flags = _onset_book(-1.0, months=S.FLOOR - 1)
    outs = S.grade_q3(cal, flags, _draws(cal), None, (0, cal.n - 1), None)
    assert all(o.cell.n_clusters == S.FLOOR - 1 and o.word == S.UNDERPOWERED for o in outs.values())
    cal2, flags2 = _onset_book(-1.0, months=S.FLOOR)
    outs2 = S.grade_q3(cal2, flags2, _draws(cal2), None, (0, cal2.n - 1), None)
    assert outs2["B10"].cell.n_clusters == S.FLOOR and outs2["B10"].word != S.UNDERPOWERED


def test_the_pbo_veto_turns_every_q3_cell_to_null():
    cal, flags = _onset_book(-1.0)
    outs = S.grade_q3(cal, flags, _draws(cal), 0.6, (0, cal.n - 1), None)
    assert all(o.word == S.NULL and o.note == "PBO veto" for o in outs.values())


def test_forward_q3_prints_still_open_under_the_floor():
    cal, flags = _onset_book(-1.0, months=3)
    outs = S.grade_q3(cal, flags, _draws(cal), None, (0, cal.n - 1), None, forward=True)
    assert all(o.word == S.STILL_OPEN for o in outs.values())


def res(point, lo, hi, p=0.001, n=12):
    return S.Result(point, lo, hi, p, n)


def test_q3_word_first_match_wins_and_the_drift_note():
    ok = dict(n_clusters=12, adj=0.01, disc_D=-0.01, disc_clusters=12, pbo_ok=True)
    assert S.q3_word(res=res(-0.02, -0.03, -0.01), mean_on=-0.01, **ok)[0] == S.ROOM_LEFT
    # CI below 0 but the onset mean is not a fall: NULL with the note
    assert S.q3_word(res=res(-0.02, -0.03, -0.01), mean_on=0.004, **ok) == (S.NULL, "below normal drift, no fall")
    # discovery sign disagrees
    assert S.q3_word(res=res(-0.02, -0.03, -0.01), mean_on=-0.01, **{**ok, "disc_D": 0.01})[0] == S.NULL
    # ... unless the discovery check is waived
    assert S.q3_word(res=res(-0.02, -0.03, -0.01), mean_on=-0.01, **{**ok, "disc_D": 0.01, "disc_clusters": 3})[0] \
        == S.ROOM_LEFT
    assert S.q3_word(res=res(0.02, 0.01, 0.03), mean_on=0.01, **{**ok, "disc_D": 0.01})[0] == S.TOO_LATE
    assert S.q3_word(res=res(0.02, 0.01, 0.03), mean_on=0.01, **{**ok, "adj": 0.2})[0] == S.NULL
    assert S.q3_word(res=res(0.0, -0.01, 0.01), mean_on=0.0, **ok)[0] == S.NULL
    assert S.q3_word(res=res(-0.02, -0.03, -0.01), mean_on=-0.01, **{**ok, "n_clusters": 9})[0] == S.UNDERPOWERED


# ── Q2 words, families and sizes ────────────────────────────────────────────

def q2w(k="C1", n_lead=12, lead=None, adj_lead=0.01, n_coin=12, coin=None, adj_coin=0.01,
        disc_ok=True, pbo_ok=True, forward=False):
    return S.q2_word(k, n_lead, lead, adj_lead, n_coin, coin, adj_coin, disc_ok, pbo_ok, forward)


def test_every_q2_word_is_reachable_and_first_match_wins():
    pos, none = res(0.2, 0.1, 0.3), res(0.0, -0.1, 0.1)
    assert q2w(lead=pos, coin=pos) == S.LEADS                          # beats COINCIDENT
    assert q2w(lead=none, coin=pos) == S.COINCIDENT
    assert q2w(lead=none, coin=none) == S.NO_FORECAST
    assert q2w(lead=pos, n_lead=9, coin=pos) == S.UNDERPOWERED         # under the floor beats everything
    assert q2w(lead=pos, n_lead=9, forward=True) == S.STILL_OPEN
    assert q2w(lead=pos, disc_ok=False, coin=none) == S.NO_FORECAST     # discovery sign disagrees
    assert q2w(lead=pos, adj_lead=0.2, coin=none) == S.NO_FORECAST      # Holm fails
    assert q2w(lead=pos, pbo_ok=False, coin=pos) == S.NO_FORECAST       # PBO veto kills both
    assert q2w(lead=none, coin=pos, adj_coin=0.2) == S.NO_FORECAST
    assert q2w(lead=none, coin=pos, n_coin=9) == S.NO_FORECAST          # too few coincident episodes


def test_c5_to_c7_are_no_forecast_unless_leads_and_the_mechanical_line_is_separate():
    pos, none = res(0.2, 0.1, 0.3, p=0.01), res(0.0, -0.1, 0.1)
    for k in S.MECH_COIN:
        assert q2w(k=k, lead=none, coin=pos, adj_coin=0.5) == S.NO_FORECAST      # whatever the line prints
        assert S.q2_mech(k, 12, pos, True) == S.COINCIDENT_MECH                  # raw p, not Holm
        assert S.q2_mech(k, 12, res(0.2, 0.1, 0.3, p=0.2), True) == ""
        assert S.q2_mech(k, 12, pos, False) == ""                                # PBO veto
        assert S.q2_mech(k, 9, pos, True) == ""                                  # under the floor
        assert q2w(k=k, lead=pos, coin=pos) == S.LEADS
    assert S.q2_mech("C1", 12, pos, True) == ""
    assert q2w(k="C1", lead=none, coin=pos, adj_coin=0.5) == S.NO_FORECAST


def test_q2_read_orders_leads_then_coincident_then_no_forecast():
    base = {k: S.NO_FORECAST for k in S.CANDS}
    assert S.q2_read({**base, "C3": S.LEADS, "C4": S.COINCIDENT}) == S.LEADS
    assert S.q2_read({**base, "C4": S.COINCIDENT}) == S.COINCIDENT
    assert S.q2_read(base) == S.NO_FORECAST
    assert S.q2_read({k: S.UNDERPOWERED for k in S.CANDS}) == S.UNDERPOWERED
    assert S.q2_read({**base, "C1": S.UNDERPOWERED}) == S.NO_FORECAST
    assert S.q2_read({k: S.STILL_OPEN for k in S.CANDS}, forward=True) == S.STILL_OPEN


def test_holm_family_sizes_are_9_6_and_6_with_unpowered_cells_entering_at_one():
    a = S.holm_family({"C1": 0.01}, S.CANDS)
    assert set(a) == set(S.CANDS) and a["C1"] == pytest.approx(0.09)
    b = S.holm_family({"C1": 0.01}, S.COIN_FAMILY)
    assert len(b) == 6 and b["C1"] == pytest.approx(0.06)
    c = S.holm_family({"B10": 0.01}, tuple(x[0] for x in S.Q3_CELLS))
    assert len(c) == 6 and c["B10"] == pytest.approx(0.06)
    assert S.COIN_FAMILY == ("C1", "C2", "C3", "C4", "C8", "C9")
    assert not set(S.COIN_FAMILY) & set(S.MECH_COIN)


def _lead_book(n_ep=12, gap=700):
    """`n_ep` well-separated episodes; C1 is on in every lead window and nowhere else."""
    n = n_ep * gap + 400
    val = np.zeros(n)
    eps = []
    for i in range(n_ep):
        p = 400 + i * gap
        val[p - 10:p] = 1.0
        eps.append(S.Ep("E-DD8", p, p + 10, p + 20, True, win=1))
    cands = {k: np.zeros(n) for k in S.CANDS}
    cands["C1"] = val
    cal = mk_cal(np.ones(n))
    ctx = S.Ctx(cal, cands, np.ones(n, dtype=int))
    S.mark_follow_ons(eps, n)
    return cal, ctx, eps, S.zone_mask(eps, n)


def test_grade_q2_calls_a_planted_lead_leads_and_the_rest_no_forecast():
    cal, ctx, eps, zone = _lead_book()
    draws = S.Draws(500, S.SEED, 100, 10, 10)
    out = S.grade_q2(ctx, zone, eps, [], draws, None)
    assert out["C1"].n_lead == 12 and out["C1"].lead.point == pytest.approx(1.0)
    assert out["C1"].word == S.LEADS
    assert all(out[k].word == S.NO_FORECAST for k in S.CANDS if k != "C1")
    assert out["C1"].adj_lead == pytest.approx(0.0, abs=1e-9)


def test_grade_q2_is_underpowered_under_ten_episodes_and_forward_says_still_open():
    cal, ctx, eps, zone = _lead_book(n_ep=9)
    draws = S.Draws(300, S.SEED, 100, 10, 10)
    out = S.grade_q2(ctx, zone, eps, [], draws, None)
    assert out["C1"].n_lead == 9 and all(c.word == S.UNDERPOWERED for c in out.values())
    fwd = S.grade_q2(ctx, zone, eps, [], draws, None, forward=True)
    assert all(c.word == S.STILL_OPEN for c in fwd.values())
    assert S.q2_read({k: c.word for k, c in out.items()}) == S.UNDERPOWERED


def test_the_pbo_veto_and_a_negative_discovery_sign_block_leads():
    cal, ctx, eps, zone = _lead_book()
    draws = S.Draws(300, S.SEED, 100, 10, 10)
    assert S.grade_q2(ctx, zone, eps, [], draws, 0.8)["C1"].word == S.NO_FORECAST
    assert S.grade_q2(ctx, zone, eps, [], draws, 0.3)["C1"].word == S.LEADS         # no discovery: waived


def _two_window_book(disc_sign: float, n_disc: int = 12, n_test: int = 12, gap: int = 700):
    """Discovery episodes (window 0) whose lead windows are on (+) or off (-) against an
    on-background, then test episodes (window 1) with C1 on only in the lead window."""
    n_d = n_disc * gap + 300
    n = n_d + 400 + n_test * gap
    val = np.zeros(n)
    win = np.where(np.arange(n) < n_d, 0, 1)
    eps_d, eps_t = [], []
    if disc_sign > 0:
        pass
    else:
        val[:n_d] = 1.0
    for i in range(n_disc):
        p = 400 + i * gap
        val[p - 10:p] = 1.0 if disc_sign > 0 else 0.0
        eps_d.append(S.Ep("E-DD8", p, p + 10, p + 20, True, win=0))
    for i in range(n_test):
        p = n_d + 400 + i * gap
        val[p - 10:p] = 1.0
        eps_t.append(S.Ep("E-DD8", p, p + 10, p + 20, True, win=1))
    cands = {k: np.zeros(n) for k in S.CANDS}
    cands["C1"] = val
    ctx = S.Ctx(mk_cal(np.ones(n)), cands, win)
    S.mark_follow_ons(eps_d + eps_t, n)
    return ctx, eps_d, eps_t, S.zone_mask(eps_d + eps_t, n)


def test_a_negative_discovery_lift_with_enough_episodes_blocks_leads():
    draws = S.Draws(300, S.SEED, 100, 10, 10)
    ctx, d_neg, tst, zone = _two_window_book(-1.0)
    out = S.grade_q2(ctx, zone, tst, d_neg, draws, 0.1)["C1"]
    assert out.n_disc >= S.FLOOR and out.disc.point < 0 and out.word == S.NO_FORECAST
    ctx, d_pos, tst, zone = _two_window_book(+1.0)
    out = S.grade_q2(ctx, zone, tst, d_pos, draws, 0.1)["C1"]
    assert out.n_disc >= S.FLOOR and out.disc.point > 0 and out.word == S.LEADS
    ctx, d_few, tst, zone = _two_window_book(-1.0, n_disc=S.FLOOR - 1)
    out = S.grade_q2(ctx, zone, tst, d_few, draws, 0.1)["C1"]
    assert out.n_disc == S.FLOOR - 1 and out.word == S.LEADS                       # waived under 10


def test_the_joint_control_rule_needs_every_candidate_value_the_episode_has():
    n = 700
    e = S.Ep("E-DD8", 300, 310, 320, True)
    zone = S.zone_mask([e], n)
    c4 = np.zeros(n)
    c4[400:552] = np.nan
    cands = {k: np.zeros(n) for k in S.CANDS}
    cands["C4"] = c4
    ctx = S.Ctx(mk_cal(np.ones(n)), cands, np.ones(n, dtype=int))
    assert len(S.controls(ctx, zone, "C1", e, 10, "lead")) == 432 - 152        # C4 is defined in the episode
    c4b = c4.copy()
    c4b[295] = np.nan                                                          # ... or it is not
    ctx2 = S.Ctx(mk_cal(np.ones(n)), {**cands, "C4": c4b}, np.ones(n, dtype=int))
    assert len(S.controls(ctx2, zone, "C1", e, 10, "lead")) == 432


def test_a_coincident_variable_is_called_coincident():
    n_ep, gap = 12, 700
    n = n_ep * gap + 400
    val = np.zeros(n)
    eps = []
    for i in range(n_ep):
        p = 400 + i * gap
        val[p + 3:p + 11] = 1.0                      # on during p .. g (g = p + 10), not before the top
        eps.append(S.Ep("E-DD8", p, p + 10, p + 20, True, win=1))
    cands = {k: np.zeros(n) for k in S.CANDS}
    cands["C1"] = val.copy()
    cands["C5"] = val.copy()
    ctx = S.Ctx(mk_cal(np.ones(n)), cands, np.ones(n, dtype=int))
    S.mark_follow_ons(eps, n)
    out = S.grade_q2(ctx, S.zone_mask(eps, n), eps, [], S.Draws(500, S.SEED, 100, 10, 10), None)
    assert out["C1"].word == S.COINCIDENT
    assert out["C5"].word == S.NO_FORECAST and out["C5"].mech == S.COINCIDENT_MECH
    assert S.q2_read({k: c.word for k, c in out.items()}) == S.COINCIDENT


# ── PBO grids ───────────────────────────────────────────────────────────────

def test_the_pbo_grids_have_32_years_and_27_or_6_configs():
    cal, ctx, eps, zone = _lead_book()
    assert len(S.PBO_YEARS) == 32 and S.PBO_YEARS[0] == 1995 and S.PBO_YEARS[-1] == 2026
    m3 = S.q3_grid(*_onset_book(-1.0))
    assert m3.shape == (32, 6, 2)
    flags = _onset_book(-1.0)[1]
    cal3 = _onset_book(-1.0)[0]
    assert S.q3_grid(cal3, flags).sum() != 0
    cal2 = crashy_cal("2010-01-04", "2014-12-31")
    ctx2 = S.make_ctx(cal2)
    eps2 = S.build_episodes(cal2, "E-DD8", ctx2.win)
    m2 = S.q2_grid(ctx2, S.zone_mask(eps2, cal2.n), eps2, cal2)
    assert m2.shape == (32, 27, 2)
    assert S.pbo_of(m2) is None or 0.0 <= S.pbo_of(m2) <= 1.0


def test_pbo_of_a_planted_selection_is_not_a_veto_and_noise_has_a_value():
    rng = np.random.default_rng(1)
    M = np.zeros((32, 6, 2))
    M[:, :, 1] = 1.0
    M[:, :, 0] = rng.normal(0, 1, (32, 6))
    M[:, 2, 0] += 5.0                                  # one config is better in every year
    assert S.pbo_of(M) <= S.PBO_FRAGILE
    assert "veto" in S.pbo_text(0.7) and "fragile" in S.pbo_text(0.4) and "veto" not in S.pbo_text(0.1)
    assert S.pbo_text(None) == "—"


# ── the in-sample cut ───────────────────────────────────────────────────────

def test_cut_cal_drops_every_close_after_the_cut():
    cal = crashy_cal("2024-01-02", "2024-12-31")
    k = S.cut_cal(cal, "2024-06-28")
    assert k.dates[-1] == "2024-06-28" and k.n == k.close.shape[0] == k.credit.shape[0]
    assert S.idx_on_or_before(cal, "2024-06-29") == k.n - 1


def _in_sample_text(capsys, cal, tmp_path, monkeypatch):
    monkeypatch.setattr(S, "MECH_CSV", tmp_path / "mech.csv")
    capsys.readouterr()
    S.analyse(cal, boot_n=120, q5=None, q4_environment=(_empty_chain(), set(), 0.65),
              q5_refusal="era current has 9 dates; this study needs 30")
    out = capsys.readouterr().out
    assert "Q5 REFUSED (era current has 9 dates; this study needs 30)" in out
    for banner in ("Q2 READ", "Q2 CANDIDATES", "Q3 READ", "Q3 CELLS", "PBO:", "Q4 (", "FORWARD ("):
        assert f">>> state_map {banner}" in out                  # a refused Q5 never costs the banner
    assert out.index("Q1 —") < out.index("Q5 REFUSED") < out.index(">>> state_map Q2 READ")
    return out.split("FORWARD — episodes and onsets")[0]


def _empty_chain():
    return NTF.Chain(idx={})


def test_the_in_sample_report_is_identical_when_every_later_close_changes(capsys, tmp_path, monkeypatch):
    cal = crashy_cal("2013-01-02", "2027-01-29", seed=9, every=210)
    assert cal.dates[-1] > S.IN_SAMPLE_END > cal.dates[0]
    before = _in_sample_text(capsys, cal, tmp_path, monkeypatch)
    k = S.idx_on_or_before(cal, S.IN_SAMPLE_END)
    other = S.Cal(cal.dates, cal.close.copy(), cal.adj.copy(), cal.vix.copy(), cal.vix3m.copy(), cal.credit.copy())
    rng = np.random.default_rng(1)
    for arr in (other.close, other.adj, other.vix, other.vix3m, other.credit):
        arr[k + 1:] = arr[k + 1:] * rng.uniform(0.3, 3.0, len(arr) - k - 1)
    after = _in_sample_text(capsys, other, tmp_path, monkeypatch)
    assert before == after
    assert "Q2 —" in before and "Q3 —" in before and "Q1 —" in before
    assert "Q4 —" in before and "AWAITING SCRAPE" in before


# ── Q4 ──────────────────────────────────────────────────────────────────────

def contract(quotes: dict):
    series, details = [], {}
    for d in sorted(quotes):
        bid, ask = quotes[d]
        mid = (bid + ask) / 2
        details[d] = {"Bid": bid, "Ask": ask, "Latest": mid, "Volume": 0, "_mark": mid}
        series.append((d, mid))
    return series, details


def chain_of(contracts: dict) -> NTF.Chain:
    idx: dict = {}
    for (opt, exp, k) in contracts:
        idx.setdefault(("SPY", exp), {}).setdefault(float(k), set()).add(opt[0])
    ch = NTF.Chain(idx=idx)
    for (opt, exp, k), q in contracts.items():
        ch._memo[("SPY", exp, round(float(k), 4), opt)] = contract(q)
    return ch


def _q4_cal():
    n = 80
    px = np.full(n, 400.0)
    return mk_cal(px, start="2024-01-02")


def _q4_setup(strikes=range(370, 421), put_mid=None):
    cal = _q4_cal()
    D = 30
    entry = date.fromisoformat(cal.dates[D + 1])
    exp = MBL.rule_expiry(entry, S.Q4_DTE)
    days = [date.fromisoformat(d) for d in cal.dates]
    mids = put_mid or {}
    q = {}
    for k in strikes:
        base = 5.0 if k == 400 else 1.5 if k == 380 else 2.0
        per_day = {}
        for i, d in enumerate(days):
            if d > exp:
                break
            bump = mids.get((k, i), 0.0)
            per_day[d] = (base + bump, base + bump + 0.1)
        q[("Put", exp, k)] = per_day
    return cal, D, exp, chain_of(q)


def test_q4_selects_the_nearest_listed_strikes_on_the_expiry_nearest_30_dte():
    cal, D, exp, chain = _q4_setup()
    t = S.q4_select(chain, set(), cal, "S-BEAR", D)
    entry = date.fromisoformat(cal.dates[D + 1])
    assert t.status == "built" and t.expiry == MBL.rule_expiry(entry, 30)
    assert (t.long_k, t.short_k) == (400.0, 380.0) and t.spot == 400.0
    assert t.entry == entry                                           # D + 1, never D


def test_q4_awaits_when_the_contracts_are_not_cached_and_names_them_once():
    cal = _q4_cal()
    trades = []
    for D in (30, 31):
        trades.append(S.q4_select(NTF.Chain(idx={}), set(), cal, "S-BEAR", D))
    assert all(t.status == "await" for t in trades)
    fetch = S.q4_fetch_list(trades)
    assert fetch and len({(f["expiration"], f["strike"], f["opt_type"]) for f in fetch}) == len(fetch)
    assert all(f["ticker"] == "SPY" and f["opt_type"] == "Put" for f in fetch)


def test_q4_report_prints_awaiting_scrape_with_a_count_and_prices_nothing(capsys, monkeypatch):
    cal = _q4_cal()
    monkeypatch.setattr(S, "onsets", lambda holds, has, rearm=S.REARM: [30])
    flags = {s: (np.zeros(cal.n, bool), np.ones(cal.n, bool)) for s in S.Q3_GRADED}
    word = S.report_q4(cal, flags, (NTF.Chain(idx={}), set(), 0.65))
    out = capsys.readouterr().out
    assert word == S.AWAITING and "contracts to fetch:" in out and "mean R" not in out
    assert "n_truncated" in out


def test_q4_prices_the_spread_at_the_entry_mid_and_the_exit_mark_net_of_commission():
    cal, D, exp, _ = _q4_setup()
    entry_i = D + 1
    exit_i = entry_i + 5
    bumps = {(400, exit_i): 2.0, (380, exit_i): -0.5}
    cal, D, exp, chain = _q4_setup(put_mid=bumps)
    t = S.q4_select(chain, set(), cal, "S-BEAR", D)
    close_of = {date.fromisoformat(d): float(c) for d, c in zip(cal.dates, cal.close)}
    r, why = S.q4_price(chain, t, cal, 5, 0.65, close_of)
    assert why == "priced"
    debit = 5.05 - 1.55
    value = (7.05) - (1.05)
    assert r == pytest.approx(((value - debit) * 100 - 0.65 * 4) / (debit * 100))


def test_q4_refuses_a_credit_and_marks_a_missing_exit_row_unpriced():
    cal, D, exp, chain = _q4_setup()
    t = S.q4_select(chain, set(), cal, "S-BEAR", D)
    close_of = {date.fromisoformat(d): float(c) for d, c in zip(cal.dates, cal.close)}
    swapped = S.Q4Trade(**{**t.__dict__, "long_k": t.short_k, "short_k": t.long_k})
    # long 380 / short 400 with the 400 put dearer prices to a credit: refused, never traded
    assert S.q4_price(chain, swapped, cal, 5, 0.65, close_of) == (None, "debit_priced_to_credit")
    assert S.q4_price(chain, t, cal, 500, 0.65, close_of)[1] == "exit_after_data_end"


def test_q4_expiry_before_the_exit_marks_at_intrinsic_when_the_expiry_quote_is_missing():
    cal, D, exp, chain = _q4_setup()
    t = S.q4_select(chain, set(), cal, "S-BEAR", D)
    close_of = {date.fromisoformat(d): float(c) for d, c in zip(cal.dates, cal.close)}
    for k in (400.0, 380.0):                       # drop the expiry-day rows
        series, details = chain._memo[("SPY", exp, k, "Put")]
        details.pop(exp, None)
        chain._memo[("SPY", exp, k, "Put")] = ([s for s in series if s[0] != exp], details)
    close_of[exp] = 395.0
    h = next(h for h in range(1, 60) if D + 1 + h < cal.n
             and date.fromisoformat(cal.dates[D + 1 + h]) >= exp)
    r, why = S.q4_price(chain, t, cal, h, 0.65, close_of)
    assert why == "priced"
    debit = 5.05 - 1.55
    value = (400.0 - 395.0) - max(0.0, 380.0 - 395.0)           # intrinsic of the spread at 395
    assert r == pytest.approx(((value - debit) * 100 - 0.65 * 4) / (debit * 100))


# ── Q5 ──────────────────────────────────────────────────────────────────────

def rec(d, src="real", structure="bull_call_spread", R=0.1, mfe=0.2, mae=-0.1, md="BULL", mv="L-VOL",
        trusted=True, pending=False, ticker="AAA", play="p"):
    return {"date": d, "ticker": ticker, "structure": structure, "source": src, "R": R, "mfe": mfe,
            "mae": mae, "mech_direction": md, "mech_vol": mv, "fill_trusted": trusted, "pending": pending,
            "t": SimpleNamespace(row={"play": play})}


def test_q5_population_drops_sealed_bs_pending_and_untrusted_rows_and_counts_them(monkeypatch):
    from scripts.backtest_study.lib import era as _era
    monkeypatch.setattr(_era, "SEAL_LIFTED", None)  # tests the sealed state
    rows = [rec("2026-01-05"), rec("2026-09-22"), rec("2026-09-23"), rec("2026-10-30"),
            rec("2026-02-02", src="bs"), rec("2026-02-03", pending=True), rec("2026-02-04", trusted=False)]
    kept, counts = S.q5_population(rows)
    assert [r["date"] for r in kept] == ["2026-01-05", "2026-09-22"]
    assert counts["sealed"] == 2 and counts["source_out"] == 1 and counts["pending"] == 1
    assert counts["not_fill_trusted"] == 1


def test_q5_cell_withholds_figures_when_thin_and_reports_capture_when_not():
    thin = S.q5_cell([rec(f"2026-01-{d:02d}") for d in range(1, 9)])
    assert thin["thin"] and "mean_R" not in thin and thin["rows"] == 8
    few_dates = S.q5_cell([rec("2026-01-05") for _ in range(25)])
    assert few_dates["thin"] and few_dates["dates"] == 1
    rows = [rec(f"2026-02-{1 + i % 15:02d}", R=0.1 if i % 2 else -0.05, mfe=0.2) for i in range(30)]
    cell = S.q5_cell(rows, boot_n=200)
    assert not cell["thin"] and cell["capture"] == pytest.approx(sum(r["R"] for r in rows) / (0.2 * 30))
    assert cell["ci"][0] - 1e-9 <= cell["mean_R"] <= cell["ci"][1] + 1e-9
    assert cell["mean_mae"] == pytest.approx(-0.1)


def test_q5_lag_bins_and_the_live_retro_split_come_first():
    lookup = {"2026-03-02|AAA|late": {"created_datetime": "2026-03-20 10:00"},
              "2026-03-02|AAA|live": {"created_datetime": "2026-03-03 06:00"}}
    a = rec("2026-03-02", play="late")
    b = rec("2026-03-02", play="live")
    c = rec("2026-03-02", play="missing")
    assert [S.q5_lag(x, lookup) for x in (a, b, c)] == ["RETRO", "LIVE", "UNKNOWN"]
    rows = [a, b, c]
    lags = {id(a): "RETRO", id(b): "LIVE", id(c): "UNKNOWN"}
    tabs = S.q5_tables(rows, lags, boot_n=50)
    assert ("mech_direction", "RETRO", "real", "bull", "BULL") in tabs
    assert tabs[("mech_direction", "RETRO", "real", "bull", "BULL")]["rows"] == 1
    assert tabs[("mech_direction", "ALL", "real", "bull", "BULL")]["rows"] == 3
    assert ("cell", "LIVE", "real", "bull", "BULL/L-VOL") in tabs


def test_q5_directions_use_ticker_class_and_other_rows_stay_separate():
    assert S.q5_direction(rec("2026-01-05", structure="bear_put_spread")) == "bear"
    assert S.q5_direction(rec("2026-01-05", structure="bull_call_spread")) == "bull"
    assert S.q5_direction(rec("2026-01-05", structure="iron_condor")) == "other"


def test_q5_gate_is_silent_and_returns_the_registrations_exit_code(monkeypatch, capsys):
    thin = [rec(f"2026-01-{d:02d}") for d in range(1, 10)]
    monkeypatch.setattr(S, "load_q5", lambda era: (thin, {"era": "current"}, {}))
    q5, why, code = S.q5_gate("current")
    assert q5 is None and code == 2 and "needs 30" in why
    assert capsys.readouterr().out == ""                       # nothing printed before the header

    def wrong_era(era):
        print("REFUSED — exports disagree")
        raise SystemExit(3)

    monkeypatch.setattr(S, "load_q5", wrong_era)
    q5, why, code = S.q5_gate("v4")
    assert (q5, code) == (None, 3) and "exports disagree" in why and capsys.readouterr().out == ""
    enough = [rec((date(2026, 1, 5) + timedelta(days=i)).isoformat()) for i in range(35)]
    monkeypatch.setattr(S, "load_q5", lambda era: (enough, {"era": "current"}, {}))
    q5, why, code = S.q5_gate("current")
    assert q5 is not None and why is None and code is None


def test_q5_report_prints_the_loaders_drops_and_the_units(capsys):
    rows = [rec((date(2026, 1, 5) + timedelta(days=i)).isoformat(), play=f"p{i}") for i in range(40)]
    diag = {"era": "current", "seal": {"rows": 0, "dates": 0, "reader": None}, "pending": {"n": 7},
            "n_proxy_excluded_non_exact": 11, "n_dup_dropped": 3, "n_excluded_no_path_or_method": 5}
    S.report_q5(rows, diag, {}, boot_n=50)
    out = capsys.readouterr().out
    assert "pending open rows 7" in out and "non-exact proxy debit rows 11" in out
    assert "percent of the position's entry cost" in out and "capture is sum R over sum MFE, a ratio" in out


# ── gates on small fixtures ─────────────────────────────────────────────────

def test_gl_agrees_with_the_mech_labeler_and_flags_a_tampered_label(tmp_path):
    p, dates, spy, vix = _write_mech_fixture(tmp_path, n=330)
    cal = mk_cal(spy, vix=vix, dates=dates)
    lab = S.labels_from_table(S.mech_table(dates, spy, vix, 50))
    out = S.gate_labels(cal, lab, full_csv=p, watch_csv=tmp_path / "absent.csv")
    n, bad = out["spy_vix_daily_full"]
    assert n > 200 and bad == []
    lab.direction[100] = "BEAR" if lab.direction[100] != "BEAR" else "BULL"
    n2, bad2 = S.gate_labels(cal, lab, full_csv=p, watch_csv=tmp_path / "absent.csv")["spy_vix_daily_full"]
    assert len(bad2) == 1 and dates[100] in bad2[0]


def test_gl_reads_the_regime_watch_history_columns(tmp_path):
    p, dates, spy, vix = _write_mech_fixture(tmp_path, n=330)
    cal = mk_cal(spy, vix=vix, dates=dates)
    tab = S.mech_table(dates, spy, vix, 50)
    lab = S.labels_from_table(tab)
    w = tmp_path / "history.csv"
    w.write_text("date,mech_direction,mech_vol\n"
                 f"{dates[250]},{tab[250]['mech_direction']},{tab[250]['mech_vol']}\n"
                 f"{dates[251]},BULL,NOPE\n")
    n, bad = S.gate_labels(cal, lab, full_csv=tmp_path / "absent.csv", watch_csv=w)["regime_watch"]
    assert n == 2 and len(bad) == 1


# ── the runner ──────────────────────────────────────────────────────────────

def test_the_runner_discovers_the_study_by_stem_and_reads_its_docstring_and_refusal_codes():
    found = runner.discover()
    assert found["state_map"].startswith("state_map — which market states come before SPY sell-offs")
    src = (S.ROOT / "scripts/backtest_study/f1_selection/regime/state_map.py").read_text()
    assert S.REGISTRATION in ast.get_docstring(ast.parse(src))
    assert (S.ROOT / S.REGISTRATION).exists()
    assert S.DESIGNED_REFUSAL_EXIT_CODES == {2, 3}


def test_the_module_writes_only_under_its_cache_directory():
    src = (S.ROOT / "scripts/backtest_study/f1_selection/regime/state_map.py").read_text()
    assert src.count(".open(\"w\"") == 2                    # the price caches and the mech csv, both under CACHE_DIR
    assert "study_output" not in src and "write_text" not in src
    assert S.MECH_CSV.parent == S.CACHE_DIR == S.ROOT / "backtests" / "state_map"


def test_q5_report_prints_all_three_tables_for_each_lag_cut(capsys):
    rows = []
    for i in range(40):
        d = (date(2026, 1, 5) + timedelta(days=i)).isoformat()
        rows.append(rec(d, structure="bear_put_spread" if i % 2 else "bull_call_spread",
                        md=("BEAR", "BULL", "RANGE")[i % 3], mv=("L-VOL", "H-VOL")[i % 2], R=0.01 * (i % 7 - 3),
                        ticker=f"T{i % 3}", play=f"play{i}"))
    S.report_q5(rows, {"era": "current", "seal": {"rows": 0, "dates": 0, "reader": None}}, {}, boot_n=50)
    out = capsys.readouterr().out
    for tab in ("mech_direction", "mech_vol", "cell"):
        for cut in ("LIVE", "RETRO", "ALL"):
            assert f"direction x {tab}, lag {cut}" in out
    assert "THIN" in out and "UNKNOWN 40" in out


def test_constants_match_the_registration_text():
    assert (S.IN_SAMPLE_END, S.DISCOVERY_END, S.TEST_START, S.FORWARD_START) == (
        "2026-09-22", "2015-12-31", "2016-01-01", "2026-11-21")
    assert (S.BOOT_N, S.SEED, S.FLOOR, S.MIN_CONTROLS, S.LEAD_W) == (10_000, 20261121, 10, 20, 10)
    assert S.LEAD_WS == (5, 10, 21) and S.HORIZONS == (5, 10, 21) and S.REARM == 10
    assert S.PBO_S == 16 and (S.PBO_VETO, S.PBO_FRAGILE) == (0.50, 0.25)
    assert S.SMA_HEADLINE == 50 and S.SMA_LONG == 200
    assert S.era_mod.SEAL_START == "2026-09-23" and S.era_mod.MIN_ERA_DATES == 30


# ── the forward read ────────────────────────────────────────────────────────

def _fwd_cal(rel_nodes, tail=150):
    dates = weekdays(500, "2026-01-05")
    a = dates.index(S.FORWARD_ANCHOR_DATE)
    n = a + tail
    pts = [(a + off, v) for off, v in rel_nodes]
    px = np.interp(np.arange(n), [0] + [x for x, _ in pts] + [n - 1], [100.0] + [v for _, v in pts] + [pts[-1][1]])
    return mk_cal(px, vix=np.full(n, 15.0), dates=dates[:n]), a


def _fwd_flags(cal, hold_offsets, a):
    holds = np.zeros(cal.n, dtype=bool)
    for off in hold_offsets:
        holds[a + off] = True
    has = np.ones(cal.n, dtype=bool)
    return {s: (holds, has) for s in ("S-BEAR", "S-EVOL", "S-BEAR200", "S-BOTH")}


def _fwd(cal, flags):
    n = cal.n
    return S.run_forward(cal, S.Draws(60, S.SEED, n // 20 + 10, n // 15 + 10, n // 21 + 5), flags)


WIGGLE = [(-60, 100.0), (-20, 101.0), (40, 99.0), (90, 103.0)]


def test_forward_onsets_need_a_clear_forward_rearm_window(capsys):
    cal, a = _fwd_cal(WIGGLE)
    # a-2 is a pre-anchor onset; a+6 and a+11 each have a hold in the 10 sessions before them;
    # a+30 does not. Only a+30 is a forward onset.
    out = _fwd(cal, _fwd_flags(cal, [-2, 6, 11, 30], a))
    assert all(c.n_on == 1 and c.n_truncated == 0 for c in out["cells"].values())


def test_forward_onsets_inside_the_current_zone_are_split_and_stay_out_of_other_days(capsys):
    nodes = [(-60, 100.0), (-20, 108.0), (15, 96.0), (40, 108.0), (120, 110.0)]
    cal, a = _fwd_cal(nodes)
    base = _fwd(cal, _fwd_flags(cal, [60], a))
    both = _fwd(cal, _fwd_flags(cal, [20, 60], a))
    assert base["in_zone"] == {"S-BEAR": 0, "S-EVOL": 0}
    assert both["in_zone"] == {"S-BEAR": 1, "S-EVOL": 1}
    for k in base["cells"]:
        assert both["cells"][k].n_on == base["cells"][k].n_on == 1
        assert both["cells"][k].n_other == base["cells"][k].n_other - 1       # the zone onset is no other day


def test_a_merged_pre_anchor_peak_is_not_a_forward_episode(capsys):
    nodes = [(-60, 100.0), (-30, 108.0), (5, 96.0), (15, 106.5), (30, 95.0), (70, 108.0), (140, 112.0)]
    cal, a = _fwd_cal(nodes)
    eps = S.build_episodes(cal, "E-DD8")
    assert len(eps) == 1 and eps[0].p == a - 30                 # one merged episode, earliest peak
    assert _fwd(cal, _fwd_flags(cal, [], a))["n_fwd_eps"] == 0


# --- post-hoc TURN-ON split (added 2026-11-21, descriptive only) -------------

class TestPosthocSplit:
    # One episode: peak p = 50, trigger g = 60. Calendar of 200 sessions.
    TRIG = [(60, 50)]

    def test_turn_on_before_peak(self):
        r = S.posthoc_split([45], self.TRIG, 200, 21)
        assert r == {"n": 1, "followed": 1, "before": 1, "mid": 0}

    def test_turn_on_between_peak_and_trigger(self):
        r = S.posthoc_split([55], self.TRIG, 200, 21)
        assert r == {"n": 1, "followed": 1, "before": 0, "mid": 1}

    def test_turn_on_at_the_peak_is_already_falling(self):
        assert S.posthoc_split([50], self.TRIG, 200, 21)["mid"] == 1

    def test_turn_on_with_no_trigger(self):
        r = S.posthoc_split([100, 20], self.TRIG, 200, 21)
        assert r == {"n": 2, "followed": 0, "before": 0, "mid": 0}

    def test_turn_on_at_the_trigger_is_not_followed(self):
        assert S.posthoc_split([60], self.TRIG, 200, 21)["followed"] == 0

    def test_horizon_boundary(self):
        # t + h == g is followed; t + h == g - 1 is not.
        assert S.posthoc_split([39], self.TRIG, 200, 21)["followed"] == 1
        assert S.posthoc_split([38], self.TRIG, 200, 21)["followed"] == 0
        assert S.posthoc_split([50], self.TRIG, 200, 10)["followed"] == 1
        assert S.posthoc_split([49], self.TRIG, 200, 10)["followed"] == 0

    def test_no_read_past_the_cut(self):
        # n = 70: t = 50 with h = 21 would need session 71, past the cut; it is left out.
        r = S.posthoc_split([50, 60], self.TRIG, 70, 21)
        assert r["n"] == 0
        r = S.posthoc_split([40, 48, 49], self.TRIG, 70, 21)
        assert r["n"] == 2 and r["followed"] == 2

    def test_split_adds_up(self):
        r = S.posthoc_split([40, 45, 55, 58, 150], self.TRIG, 200, 21)
        assert r["followed"] == r["before"] + r["mid"] == 4
        assert r["n"] == 5

    def test_nearest_trigger_decides_the_position(self):
        trig = [(60, 50), (120, 100)]
        r = S.posthoc_split([95, 110], trig, 300, 30)
        assert r == {"n": 2, "followed": 2, "before": 1, "mid": 1}
