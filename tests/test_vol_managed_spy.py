"""vol_managed_spy: the weight formula, signal dating, execution lag, SPY-leg cost, the GR
replay, the per-draw MIX re-match, Holm, the verdict tables and the gates, on synthetic
series. No market data is read."""
from __future__ import annotations

import contextlib
import dataclasses
import io
import math
from datetime import date, timedelta

import numpy as np
import pytest

from scripts.backtest_study.f4_deployment import vol_managed_spy as M


def _weekdays(start: str, end: str) -> list[str]:
    d, e = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _inputs(start=M.SPY_START, end="2026-11-20", seed=7) -> M.Inputs:
    rng = np.random.default_rng(seed)
    dates = _weekdays(start, end)
    n = len(dates)
    # volatility regimes, so weights move off the cap
    vol = np.where((np.arange(n) // 400) % 3 == 0, 0.025, 0.007)
    adj = 100 * np.exp(np.cumsum(rng.normal(0.0003, vol)))
    close = adj / 0.9
    spy = M.Series(list(dates), close, adj)
    irx_c = 2.0 + rng.normal(0, 0.05, n)
    irx_c[5000:5010] = [-0.05, 0.0, -0.01, 0.02, 0.0, -0.02, 0.01, 0.0, 0.0, -0.03]
    irx = M.Series(list(dates), irx_c, irx_c.copy())
    gspc = M.Series(list(dates), close * 10, close * 10)
    raw = [d for d, c in zip(dates, irx_c) if c <= 0]
    return M.Inputs(spy, irx, gspc, None, None, raw, {})


def _perturb_after(inp: M.Inputs, cut: str, seed=99) -> M.Inputs:
    rng = np.random.default_rng(seed)
    s = inp.spy
    k = int(np.searchsorted(np.array(s.dates), cut, side="right"))
    f = np.ones(len(s.dates))
    f[k:] = rng.uniform(0.5, 1.5, len(s.dates) - k)
    spy = M.Series(list(s.dates), s.close * f, s.adj * f)
    c = inp.irx.close.copy()
    c[k:] = rng.uniform(-1, 9, len(c) - k)
    irx = M.Series(list(inp.irx.dates), c, c.copy())
    gspc = M.Series(list(inp.gspc.dates), inp.gspc.close * f, inp.gspc.adj * f)
    return M.Inputs(spy, irx, gspc, None, None, list(inp.irx_nonpos_raw), {})


@pytest.fixture(scope="module")
def inp():
    return _inputs()


@pytest.fixture(scope="module")
def built(inp):
    cut = inp.cut(M.IN_SAMPLE_END)
    P = M.build_panel(cut, M.IN_SAMPLE_END)
    me = M.month_end_idx(P.dates)
    j0 = M.first_decision(P, me)
    return cut, P, me, j0


# ── the weight formula ───────────────────────────────────────────────────────

def test_weight_formula_both_forms_and_the_cap():
    assert M.weight_of(0.24, "VOL", 0.12) == pytest.approx(0.5)
    assert M.weight_of(0.24, "VAR", 0.12) == pytest.approx(0.25)
    assert M.weight_of(0.06, "VOL", 0.12) == 1.0          # target / sigma = 2, capped
    assert M.weight_of(0.10, "VAR", 0.12) == 1.0
    assert M.weight_of(0.12, "VOL", 0.12) == 1.0
    assert math.isnan(M.weight_of(0.0, "VOL", 0.12))
    assert math.isnan(M.weight_of(float("nan"), "VAR", 0.12))
    assert M.CELLS[0] == "VOL-21-10" and len(M.CELLS) == 12 and M.HEADLINE in M.CELLS
    assert M.parse_cell("VAR-63-15") == ("VAR", 63, 0.15)


def test_sigma_is_the_annualised_ddof1_sd_of_the_last_n_log_returns():
    lr = np.array([0.01, -0.02, 0.015, 0.0, -0.005] * 10)
    adj = 100 * np.exp(np.concatenate([[0.0], np.cumsum(lr)]))
    n = 21
    want = np.std(lr[-n:], ddof=1) * math.sqrt(252)
    assert M.sigma_hat(adj, n) == pytest.approx(want)
    w, sig = M.target_weight(adj, "VOL-21-12")
    assert sig == pytest.approx(want) and w == pytest.approx(min(1.0, 0.12 / want))
    assert math.isnan(M.sigma_hat(adj[:21], 21))          # 20 returns are not enough


def test_sigma_reads_closes_through_the_decision_close_only():
    rng = np.random.default_rng(3)
    adj = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 200)))
    t = 150
    for cell in M.CELLS:
        base = M.target_weight(adj[:t + 1], cell)
        later = adj.copy()
        later[t + 1:] *= rng.uniform(0.5, 1.5, len(adj) - t - 1)
        assert M.target_weight(later[:t + 1], cell) == base
    # the return INTO t is read; the close before the window is not
    a2 = adj.copy()
    a2[t] *= 1.05
    assert M.target_weight(a2[:t + 1], "VOL-21-12") != M.target_weight(adj[:t + 1], "VOL-21-12")
    a3 = adj.copy()
    a3[t - 22] *= 1.05
    assert M.target_weight(a3[:t + 1], "VOL-21-12") == M.target_weight(adj[:t + 1], "VOL-21-12")


def test_decision_table_ignores_every_close_after_the_decision(inp, built):
    """GX: change every close and ^IRX quote after decision t; every weight decided at or
    before t is identical."""
    _, P, me, j0 = built
    for j in (j0, j0 + 50, j0 + 300):
        t = me[j]
        Q = M.build_panel(_perturb_after(inp, P.dates[t]).cut(M.IN_SAMPLE_END), M.IN_SAMPLE_END)
        for cell in M.CELLS:
            a = M.decision_table(P, me, j0, cell)
            b = M.decision_table(Q, me, j0, cell)
            for k in [x for x in a if x <= t + 1]:
                assert a[k] == b[k]


# ── calendar ─────────────────────────────────────────────────────────────────

def test_last_row_is_never_a_decision_close():
    dates = ["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-28"]
    assert M.month_end_idx(dates) == [1]
    assert 1 not in M.month_end_idx(dates[:2])


def test_first_decision_has_63_returns_before_it(built):
    _, P, me, j0 = built
    assert me[j0] >= M.MAX_N and (j0 == 0 or me[j0 - 1] < M.MAX_N)


def test_execution_is_one_session_after_the_decision(built):
    _, P, me, j0 = built
    tab = M.decision_table(P, me, j0, M.HEADLINE)
    assert all(d.t == k - 1 and d.t in me for k, d in tab.items())
    assert sorted(tab)[0] == me[j0] + 1


# ── execution and cost ───────────────────────────────────────────────────────

def _tiny_panel(n=8, r0=0.02, rate=0.0):
    dates = _weekdays("2020-01-01", "2020-03-31")[:n]
    adj = 100.0 * (1 + r0) ** np.arange(n)
    tb = np.full(n, rate)
    tb[0] = np.nan
    return M.Panel(dates, adj, adj.copy(), np.zeros(n), np.zeros(n, dtype=int), tb)


def _tab(**kw):
    return {int(k[1:]): M.Decision(int(k[1:]) - 1, v, 0.2) for k, v in kw.items()}


def test_new_weight_earns_from_the_session_after_execution():
    P = _tiny_panel(rate=0.001)
    cv = M.simulate(P, _tab(k1=1.0, k4=0.0), "x", cost_bp=0.0)
    assert np.isnan(cv.g[1])                              # the start close
    assert cv.g[2] == pytest.approx(1.02)
    assert cv.g[4] == pytest.approx(1.02)                 # session 4 still earns the OLD weight
    assert cv.g[5] == pytest.approx(1.001)                # first return at the new weight


def test_cost_is_charged_on_the_spy_leg_only():
    P = _tiny_panel()
    cv = M.simulate(P, _tab(k1=1.0, k4=0.0), "x", cost_bp=5.0)
    # SPY 1.0 -> 0: SPY notional traded is 1 x equity; the T-bill side is not charged
    assert cv.g[4] == pytest.approx(1.02 * (1 - 5e-4))
    assert cv.execs[1].turnover == pytest.approx(1.0)
    assert cv.execs[0].turnover == 0.0 and cv.execs[0].initial


def test_drifted_spy_weight_sets_the_traded_notional():
    P = _tiny_panel(rate=0.001)
    cv = M.simulate(P, _tab(k1=0.5, k4=0.5), "x", cost_bp=5.0)
    s, c = 0.5 * 1.02 ** 3, 0.5 * 1.001 ** 3
    E = s + c
    traded = abs(0.5 - s / E)
    assert cv.execs[1].turnover == pytest.approx(traded)
    assert np.prod(cv.g[2:5]) == pytest.approx(E * (1 - traded * 5e-4))
    mix = M.benchmark_mix(P, 0.5, [1, 4], cost_bp=5.0)
    assert np.allclose(mix.g[2:], cv.g[2:], rtol=0, atol=1e-15)


# ── GR replay ────────────────────────────────────────────────────────────────

def test_weight_one_reproduces_spy_and_a_fixed_weight_reproduces_mix(built):
    _, P, me, j0 = built
    ks = sorted(M.decision_table(P, me, j0, M.HEADLINE))
    grid = M.month_grid(P, ks[0])
    one = M.monthly(M.simulate(P, M.forced_table(ks, 1.0), "f1").g, grid)
    spy = M.monthly(M.benchmark_hold(P, ks[0]).g, grid)
    fw = M.monthly(M.simulate(P, M.forced_table(ks, 0.63), "fw").g, grid)
    mix = M.monthly(M.benchmark_mix(P, 0.63, ks).g, grid)
    assert np.max(np.abs(one - spy)) <= M.GR_TOL and np.max(np.abs(fw - mix)) <= M.GR_TOL
    assert M.gate_replay(one, spy, fw, mix, 0.63)[0].endswith("PASS")
    with pytest.raises(M.Refused):
        M.gate_replay(one, spy + 1e-9, fw, mix, 0.63)
    with pytest.raises(M.Refused):
        M.gate_replay(one, spy, fw, mix * 1.001, 0.63)


# ── the bootstrap and the per-draw MIX re-match ──────────────────────────────

def test_mix_is_rematched_by_the_draws_mean_weight():
    tbm = np.array([0.001, 0.002, 0.001])
    r_mix = np.array([0.03, -0.04, 0.02])
    wm = np.array([1.0, 0.4, 0.7])
    wbar = float(wm.mean())
    idx = np.array([[0, 1, 2], [0, 0, 2]])
    out = M.rematched_mix(r_mix[idx], tbm[idx], wm[idx], wbar)
    assert np.allclose(out[0], r_mix)                    # observed path: wbar_b = wbar
    scale = wm[[0, 0, 2]].mean() / wbar
    assert np.allclose(out[1], tbm[[0, 0, 2]] + (r_mix[[0, 0, 2]] - tbm[[0, 0, 2]]) * scale)


def test_rematch_moves_mdd_draws_and_leaves_sharpe_draws_alone():
    rng = np.random.default_rng(5)
    n = 60
    tbm = np.full(n, 0.001)
    r_spy = rng.normal(0.008, 0.05, n)
    wm = rng.uniform(0.3, 1.0, n)
    r_cell = tbm + wm * (r_spy - tbm)
    wbar = float(wm.mean())
    r_mix = tbm + wbar * (r_spy - tbm)
    idx = M.boot_index(n, 12, 200, seed=1)
    a = M.boot_draws(idx, r_cell, r_mix, r_spy, tbm, wm, wbar)
    flat = M.boot_draws(idx, r_cell, r_mix, r_spy, tbm, np.full(n, wbar), wbar)
    assert np.allclose(a.d_sharpe, flat.d_sharpe)
    assert not np.allclose(a.d_mdd, flat.d_mdd)
    # paired: the identity order reproduces the point estimates
    ident = M.boot_draws(np.arange(n)[None, :], r_cell, r_mix, r_spy, tbm, wm, wbar)
    assert ident.d_sharpe[0] == pytest.approx(M.sharpe(r_cell - tbm) - M.sharpe(r_mix - tbm))
    assert ident.d_mdd[0] == pytest.approx(M.mdd(r_mix) - M.mdd(r_cell))
    assert ident.alpha[0] == pytest.approx(M.nw_ols(r_cell - tbm, r_spy - tbm)[0] * 12)


def test_p_value_is_the_share_at_or_below_zero():
    assert M.p_value(np.array([-1.0, 0.0, 1.0, 2.0])) == 0.5
    assert M.p_value(np.array([np.nan, 1.0])) == 0.5      # a non-finite draw is no benefit


# ── Holm ─────────────────────────────────────────────────────────────────────

def test_holm_order_and_thresholds():
    # the smaller p is tested first at 0.0125, the other at 0.025
    assert M.holm(0.020, 0.010) == (True, True, "dMDD")
    assert M.holm(0.010, 0.020) == (True, True, "dSharpe")
    # a tie tests dSharpe first
    assert M.holm(0.010, 0.010)[2] == "dSharpe"
    # first fails -> the second cannot pass, however small
    assert M.holm(0.013, 0.0125) == (False, False, "dMDD")
    assert M.holm(0.0125, 0.0125) == (False, False, "dSharpe")
    # first passes, second above 0.025
    assert M.holm(0.012, 0.025) == (True, False, "dSharpe")
    assert M.holm(0.30, 0.001) == (False, True, "dMDD")


# ── verdicts ─────────────────────────────────────────────────────────────────

GOOD, BAD = 0.001, 0.5          # holdout p-values


def _g(**kw):
    base = dict(ds_disc=0.1, dm_disc=0.1, p_s=BAD, p_m=BAD, ds_hi=0.3, dm_hi=0.3)
    base.update(kw)
    return M.Graded(**base)


@pytest.mark.parametrize("args, word, notes", [
    (dict(refused="GI"), "REFUSED (GI)", []),
    (dict(pbo=float("nan")), "REFUSED (PBO undefined)", []),
    (dict(powered=False, g=_g(p_s=GOOD, p_m=GOOD)), "UNDERPOWERED", []),
    (dict(pbo=0.6, g=_g(p_m=GOOD)), "PBO-VETO", []),
    (dict(pbo=0.6), "NULL", []),
    (dict(g=_g(p_s=GOOD, p_m=GOOD)), "BEATS-MIX", []),
    (dict(g=_g(p_m=GOOD)), "DRAWDOWN-ONLY", []),
    (dict(g=_g(p_m=GOOD, ds_hi=-0.1)), "DRAWDOWN-ONLY", ["Sharpe clearly worse"]),
    (dict(g=_g(p_s=GOOD)), "SHARPE-ONLY", []),
    (dict(g=_g(p_s=GOOD, dm_hi=-0.1)), "SHARPE-ONLY", ["drawdown clearly worse"]),
    (dict(g=_g(ds_hi=-0.1)), "CONTRARY", []),
    (dict(g=_g(dm_hi=-0.1)), "CONTRARY", []),
    (dict(), "NULL", []),
    (dict(g=_g(p_s=GOOD, ds_disc=-0.1)), "NULL", ["holdout gain, discovery sign disagrees"]),
    (dict(g=_g(p_m=GOOD, dm_disc=0.0)), "NULL", ["holdout gain, discovery sign disagrees"]),
    (dict(g=_g(p_s=GOOD, ds_disc=-0.1, dm_hi=-0.1)), "CONTRARY", []),
    (dict(pbo=0.4, g=_g(p_s=GOOD, p_m=GOOD)), "BEATS-MIX", ["selection fragile"]),
    (dict(pbo=0.5, g=_g(p_s=GOOD, p_m=GOOD)), "BEATS-MIX", ["selection fragile"]),
    (dict(pbo=0.25, g=_g(p_s=GOOD, p_m=GOOD)), "BEATS-MIX", []),
    # Holm: dSharpe tested first at p 0.02 fails, so dMDD at 0.02 cannot count
    (dict(g=_g(p_s=0.02, p_m=0.02)), "NULL", []),
    # dMDD first at 0.01 passes, then dSharpe at 0.02 passes
    (dict(g=_g(p_s=0.02, p_m=0.01)), "BEATS-MIX", []),
])
def test_headline_word_first_match(args, word, notes):
    kw = dict(powered=True, pbo=0.1, g=_g())
    kw.update(args)
    w, n = M.headline_word(**kw)
    assert w == word and n == notes
    # exactly one token: a registered word, or one REFUSED (reason)
    assert w in M.HEADLINE_WORDS or (w.startswith("REFUSED (") and w.endswith(")"))
    assert sum(1 for x in M.HEADLINE_WORDS if x in w.split()) == (0 if w.startswith("REFUSED")
                                                                  else 1)


@pytest.mark.parametrize("args, word", [
    (dict(refused="GB basis"), "REFUSED (GB basis)"),
    (dict(pbo=float("inf")), "REFUSED (PBO undefined)"),
    (dict(powered=False, alpha_lo=0.01), "UNDERPOWERED"),
    (dict(pbo=0.51, alpha_lo=0.01), "PBO-VETO"),
    (dict(alpha_lo=0.01), "ALPHA"),
    (dict(alpha_lo=0.01, alpha_disc=-0.01), "NO-ALPHA"),
    (dict(alpha_lo=-0.05, alpha_hi=-0.01), "NEGATIVE-ALPHA"),
    (dict(pbo=0.9, alpha_lo=-0.05, alpha_hi=-0.01), "NEGATIVE-ALPHA"),
    (dict(), "NO-ALPHA"),
])
def test_arm_r_word_first_match(args, word):
    kw = dict(powered=True, pbo=0.1, alpha_disc=0.01, alpha_lo=-0.01, alpha_hi=0.03)
    kw.update(args)
    w = M.arm_r_word(**kw)
    assert w == word
    assert w in M.ARM_R_WORDS or w.startswith("REFUSED (")


def test_forward_words():
    assert M.forward_word(0.1, 0.1) == "FORWARD-AGREES"
    assert M.forward_word(0.1, -0.1) == "FORWARD-SPLIT"
    assert M.forward_word(-0.1, 0.1) == "FORWARD-SPLIT"
    assert M.forward_word(0.0, 0.0) == "FORWARD-AGAINST"


def test_forward_is_still_open_then_lapses(inp, capsys):
    assert M.report_forward(inp, boot_n=10, today="2026-11-27").startswith("STILL-OPEN (0 ")
    assert M.report_forward(inp, boot_n=10, today="2030-12-01") == "LAPSED"


# ── windows and episodes ─────────────────────────────────────────────────────

def test_mdd_peak_starts_at_the_rebased_one():
    assert M.mdd(np.array([-0.10, 0.05])) == pytest.approx(0.10)
    assert M.mdd(np.array([0.10, -0.10])) == pytest.approx(0.10)
    assert M.mdd(np.array([0.05, 0.05])) == 0.0


def test_months_are_complete_and_windows_are_registered(built):
    _, P, me, j0 = built
    ks = sorted(M.decision_table(P, me, j0, M.HEADLINE))
    grid = M.month_grid(P, ks[0])
    assert grid.months[-1] == "2026-08"                  # 2026-09 is cut mid-month
    assert grid.months[0] == P.dates[ks[0]][:7]
    h = M.make_window(grid, "h", *M.HOLDOUT)
    assert (h.months[0], h.months[-1], h.n) == ("2010-01", "2026-08", 200)
    d = M.make_window(grid, "d", None, M.DISCOVERY_END)
    assert d.months[-1] == "2009-12" and d.months[0] == grid.months[0]


def test_episodes_need_a_fifteen_percent_fall_and_end_at_recovery():
    r = np.array([0.0, -0.10, -0.08, 0.10, 0.10, -0.05])
    eps = M.episodes(r)
    assert len(eps) == 1
    e = eps[0]
    assert e.peak == 0 and e.trough == 2 and e.depth == pytest.approx(1 - 0.9 * 0.92)
    assert e.recovery == 4
    assert M.episodes(np.array([-0.14, 0.2])) == []
    cell = np.array([0.0, -0.05, 0.0, 0.0, 0.0, 0.0])
    assert M.dd_inside(cell, e) == pytest.approx(0.05)


def test_cvar_is_the_mean_of_the_worst_five_percent():
    r = np.arange(40, dtype=float) / 100 - 0.1
    assert M.cvar(r) == pytest.approx(np.mean([-0.10, -0.09]))


# ── gates ────────────────────────────────────────────────────────────────────

def _with(inp, **kw):
    return dataclasses.replace(inp, **kw)


def _gi(x):
    c = x.cut(M.IN_SAMPLE_END)
    return M.gate_inputs(c, M.build_panel(c, M.IN_SAMPLE_END))


def test_gate_inputs_passes_on_clean_synthetic_data(inp):
    assert _gi(inp)[-1].endswith("PASS")


def test_gate_inputs_refuses_bad_spy_values(inp):
    for v in (0.0, -1.0, float("nan")):
        c = inp.spy.close.copy()
        c[100] = v
        with pytest.raises(M.Refused, match="GI"):
            _gi(_with(inp, spy=M.Series(list(inp.spy.dates), c, inp.spy.adj.copy())))
    a = inp.spy.adj.copy()
    a[200] = float("nan")
    with pytest.raises(M.Refused, match="GI"):
        _gi(_with(inp, spy=M.Series(list(inp.spy.dates), inp.spy.close.copy(), a)))


def test_gate_inputs_refuses_short_coverage_and_calendar_gaps(inp):
    with pytest.raises(M.Refused, match="GI"):
        _gi(_with(inp, spy=inp.spy.cut("2026-09-01")))
    g = inp.gspc
    keep = [i for i in range(len(g.dates)) if i != 3000]
    gs = M.Series([g.dates[i] for i in keep], g.close[keep], g.adj[keep])
    with pytest.raises(M.Refused, match="calendars"):
        _gi(_with(inp, gspc=gs))


def test_gate_inputs_refuses_a_long_irx_carry_but_not_a_short_one(inp):
    s = inp.irx

    def drop(lo, hi):
        keep = [i for i in range(len(s.dates)) if not lo <= i < hi]
        return M.Series([s.dates[i] for i in keep], s.close[keep], s.adj[keep])
    assert _gi(_with(inp, irx=drop(4000, 4005)))[-1].endswith("PASS")
    with pytest.raises(M.Refused, match="carried 6"):
        _gi(_with(inp, irx=drop(4000, 4006)))


def test_gate_inputs_refuses_copies_that_disagree(inp):
    c = inp.irx.close.copy()
    c[1234] += 0.02
    alt = M.Series(list(inp.irx.dates), c, c.copy())
    with pytest.raises(M.Refused, match="copies"):
        _gi(_with(inp, irx_alt=alt))
    ok = M.Series(list(inp.irx.dates), inp.irx.close + 0.005, inp.irx.adj.copy())
    assert _gi(_with(inp, irx_alt=ok))[-1].endswith("PASS")


def test_gate_inputs_refuses_a_dropped_nonpositive_irx_quote(inp):
    raw = list(inp.irx_nonpos_raw) + ["2000-01-03"]
    with pytest.raises(M.Refused, match="at or below 0"):
        _gi(_with(inp, irx_nonpos_raw=sorted(raw)))


def test_negative_and_zero_irx_quotes_are_kept(tmp_path):
    p = tmp_path / "IRX.csv"
    p.write_text("date,close,adj_close\n"
                 "2020-03-02,1.10,1.10\n2020-03-03,-0.05,-0.05\n2020-03-04,0.0,0.0\n"
                 "2020-03-05,,\n2020-03-06,abc,abc\n2020-03-09,0.02,0.02\n")
    rows = M.read_yield(p)
    assert [r[0] for r in rows] == ["2020-03-02", "2020-03-03", "2020-03-04", "2020-03-09"]
    assert [r[1] for r in rows] == [1.10, -0.05, 0.0, 0.02]
    assert M.raw_nonpositive_dates(p) == ["2020-03-03", "2020-03-04"]
    irx = M.to_series(rows)
    dates = ["2020-03-02", "2020-03-03", "2020-03-04", "2020-03-05", "2020-03-06", "2020-03-09"]
    spy = M.Series(dates, np.full(6, 100.0), np.full(6, 90.0))
    P = M.build_panel(M.Inputs(spy, irx, spy), dates[-1])
    assert P.tb[2] == pytest.approx(-0.05 / 100 / 252)   # session k pays close k-1, as printed
    assert P.tb[3] == 0.0
    assert P.tb[4] == 0.0 and P.irx_carry[4] == 2        # empty and non-numeric carry forward
    held = [d for d, c in zip(irx.dates, irx.close) if c <= 0]
    assert held == M.raw_nonpositive_dates(p)


def test_gate_basis_refuses_ratio_and_return_breaks(inp):
    assert M.gate_basis(inp)[-1].endswith("PASS")
    s = inp.spy
    # dividing close by 1.03 makes adj/close JUMP 3%; multiplying by 1.0002 makes it FALL 0.02%
    for f in (1 / 1.03, 1.0002):
        c = s.close.copy()
        c[3000:] *= f
        with pytest.raises(M.Refused, match="GB"):
            M.gate_basis(_with(inp, spy=M.Series(list(s.dates), c, s.adj.copy())))
    a, c = s.adj.copy(), s.close.copy()
    a[4000:] *= 1.30
    c[4000:] *= 1.30
    with pytest.raises(M.Refused, match="GB"):
        M.gate_basis(_with(inp, spy=M.Series(list(s.dates), c, a)))


def test_gate_weights_refuses_a_zero_sigma():
    tab = {"VOL-21-12": {5: M.Decision(4, float("nan"), 0.0)}}
    with pytest.raises(M.Refused, match="GW"):
        M.gate_weights(tab)
    with pytest.raises(M.Refused, match="GW"):
        M.gate_weights({"VOL-21-12": {5: M.Decision(4, 1.2, 0.1)}})
    assert M.gate_weights({"VOL-21-12": {5: M.Decision(4, 1.0, 0.1)}})[0].endswith("PASS")


# ── the whole in-sample run ──────────────────────────────────────────────────

def _run(x, boot_n=20):
    """One in-sample run. Callers shrink PBO_S: S=16 has 12,870 splits per PBO, which only
    costs time, and the cut and the refusal do not depend on S."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = M.run_in_sample(x, boot_n=boot_n)
    return buf.getvalue(), out


def test_in_sample_report_ignores_every_close_after_the_cut(inp, monkeypatch):
    """GC: the whole in-sample report is identical when every close after 2026-09-22
    changes."""
    monkeypatch.setattr(M, "PBO_S", 6)
    a, out = _run(inp)
    b, _ = _run(_perturb_after(inp, M.IN_SAMPLE_END))
    assert a == b
    for gate in ("GI copies", "GB basis", "GW weights", "GX no lookahead", "GR replay"):
        assert any(gate in ln and ln.endswith("PASS") for ln in a.splitlines()), gate
    assert out["word"] in M.HEADLINE_WORDS and out["arm_r"] in M.ARM_R_WORDS


def test_non_finite_pbo_refuses(inp, monkeypatch):
    real = M.PBO.cscv

    def nan_cscv(*a, **k):
        return dataclasses.replace(real(*a, **k), pbo=float("nan"))
    monkeypatch.setattr(M.PBO, "cscv", nan_cscv)
    monkeypatch.setattr(M, "PBO_S", 6)
    with pytest.raises(M.Refused) as exc:
        _run(inp, boot_n=5)
    assert exc.value.reason == "PBO undefined" and exc.value.code in M.DESIGNED_REFUSAL_EXIT_CODES


def test_other_era_refuses_with_exit_2(monkeypatch, capsys):
    monkeypatch.setenv("STUDY_ERA", "v3")
    assert M.main([]) == 2
    out = capsys.readouterr().out
    assert ">>> vol_managed_spy HEADLINE (VOL-21-12 vs MIX, holdout 2010-01 to 2026-08, 5 bp): " \
           "REFUSED (era) <<<" in out
