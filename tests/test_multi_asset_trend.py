"""multi_asset_trend: signal dating, execution lag, cost netting, the GR replay, window
rebasing, the cut and the verdict table, on synthetic series. No market data is read."""
from __future__ import annotations

import contextlib
import io
from datetime import date, timedelta

import numpy as np
import pytest

from scripts.backtest_study.f4_deployment import multi_asset_trend as M

NT = len(M.TICKERS)


def _weekdays(start: str, end: str) -> list[str]:
    d, e = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _inputs(start="2005-01-03", end="2026-11-20", seed=7) -> M.Inputs:
    rng = np.random.default_rng(seed)
    dates = _weekdays(start, end)
    n = len(dates)
    etf = {}
    for i, t in enumerate(M.TICKERS):
        px = 50 * np.exp(np.cumsum(rng.normal(0.0002 * (i % 3), 0.01 + 0.002 * i, n)))
        etf[t] = M.Series(list(dates), px.copy(), px.copy())
    irx = M.Series(list(dates), 2.0 + rng.normal(0, 0.05, n), np.full(n, np.nan))
    return M.Inputs(etf, irx, None, "synthetic")


def _perturb_after(inp: M.Inputs, cut: str, seed=99) -> M.Inputs:
    rng = np.random.default_rng(seed)
    etf = {}
    for t, s in inp.etf.items():
        k = np.searchsorted(np.array(s.dates), cut, side="right")
        f = np.ones(len(s.dates))
        f[k:] = rng.uniform(0.5, 1.5, len(s.dates) - k)
        etf[t] = M.Series(list(s.dates), s.close * f, s.adj * f)
    s = inp.irx
    k = np.searchsorted(np.array(s.dates), cut, side="right")
    c = s.close.copy()
    c[k:] = rng.uniform(0, 9, len(c) - k)
    return M.Inputs(etf, M.Series(list(s.dates), c, s.adj.copy()), None, "synthetic")


@pytest.fixture(scope="module")
def inp():
    return _inputs()


@pytest.fixture(scope="module")
def built(inp):
    P = M.build_panel(inp, M.IN_SAMPLE_END)
    me = M.month_end_idx(P.dates)
    j0 = M.first_common_decision(P, me)
    return P, me, j0


# ── calendar and dating ──────────────────────────────────────────────────────

def test_last_row_is_never_a_decision_close():
    dates = ["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-28"]
    assert M.month_end_idx(dates) == [1]
    # cutting at a month-end close never makes that close a decision
    assert 1 not in M.month_end_idx(dates[:2])


def test_first_common_decision_waits_for_twelve_month_ends(built):
    P, me, j0 = built
    assert j0 == M.MAX_LOOKBACK            # every synthetic series starts together
    assert P.dates[me[j0]][:7] == "2006-01"


def test_targets_ignore_every_close_after_the_decision(inp, built):
    """GX: change every close (and every ^IRX quote) after decision t; the targets at t
    and at every earlier decision must not move."""
    P, me, j0 = built
    for j in (j0, j0 + 37, j0 + 120):
        t = me[j]
        cut = P.dates[t]
        Q = M.build_panel(_perturb_after(inp, cut), M.IN_SAMPLE_END)
        for cell in M.CELLS:
            a = M.decision_table(P, me, j0, cell)
            b = M.decision_table(Q, me, j0, cell)
            for k in [x for x in a if x <= t + 1]:
                assert np.array_equal(a[k][0], b[k][0]) and np.array_equal(a[k][1], b[k][1])


def test_decision_refuses_arrays_that_run_past_its_close(built):
    P, me, j0 = built
    t = me[j0]
    with pytest.raises(AssertionError):
        M.targets(P.adj[:t + 2], P.tb[:t + 2], me[:j0 + 1], M.HEADLINE)


def test_tb_rule_ties_are_out_and_sma_reads_month_end_closes():
    n = 300
    dates = _weekdays("2010-01-01", "2012-12-31")[:n]
    me = M.month_end_idx(dates)
    adj = np.full((n, NT), 100.0)
    tb = np.zeros(n)
    j = 12
    t = me[j]
    st, w = M.targets(adj[:t + 1], tb[:t + 1], me[:j + 1], "TB-12-EW")
    assert not st.any() and w.sum() == 0.0          # flat price, zero T-bill: tie is OUT
    adj2 = adj.copy()
    adj2[t, 0] = 101.0
    st, w = M.targets(adj2[:t + 1], tb[:t + 1], me[:j + 1], "SMA-6-EW")
    assert st[0] and not st[1:].any() and w[0] == pytest.approx(1 / NT)


# ── execution and cost ───────────────────────────────────────────────────────

def _tiny_panel(n=8, r0=0.02, rate=0.0):
    dates = _weekdays("2020-01-01", "2020-03-31")[:n]
    adj = np.ones((n, NT)) * 100.0
    adj[:, 0] = 100.0 * (1 + r0) ** np.arange(n)
    adj[:, 1] = 100.0 * (1 - r0) ** np.arange(n)
    tb = np.full(n, rate)
    tb[0] = np.nan
    return M.Panel(dates, adj, adj[:, 0].copy(), np.zeros(n), np.zeros(n, dtype=int), tb)


def _w(**kw):
    w = np.zeros(NT)
    for k, v in kw.items():
        w[M.TICKERS.index(k)] = v
    return w


def test_new_weights_earn_from_the_session_after_execution():
    P = _tiny_panel(rate=0.001)
    st = np.zeros(NT, dtype=bool)
    table = {1: (st, _w(SPY=1.0)), 4: (st, _w())}       # execute at k=1, then go to cash at k=4
    cv = M.simulate(P, table, "x", cost_bp=0.0)
    assert np.isnan(cv.g[1])                            # the start close
    assert cv.g[2] == pytest.approx(1.02)
    assert cv.g[4] == pytest.approx(1.02)               # session 4 still earns the OLD weights
    assert cv.g[5] == pytest.approx(1.001)              # first return at the new weights


def test_cost_is_five_bp_per_side_on_every_sleeve_including_cash():
    P = _tiny_panel()
    st = np.zeros(NT, dtype=bool)
    cv = M.simulate(P, {1: (st, _w(SPY=1.0)), 4: (st, _w())}, "x", cost_bp=5.0)
    # SPY 1.0 -> 0 and cash 0 -> 1.0: traded notional 2 x equity, 5 bp per side
    assert cv.g[4] == pytest.approx(1.02 * (1 - 2 * 5e-4))
    assert cv.execs[1].turnover == pytest.approx(2.0)
    assert cv.execs[0].turnover == 0.0                 # the start carries no entry cost


def test_drifted_weights_set_the_traded_notional():
    P = _tiny_panel()
    st = np.zeros(NT, dtype=bool)
    half = _w(SPY=0.5, QQQ=0.5)
    cv = M.simulate(P, {1: (st, half), 4: (st, half)}, "x", cost_bp=5.0)
    a, b = 0.5 * 1.02 ** 3, 0.5 * 0.98 ** 3
    E = a + b
    traded = abs(0.5 - a / E) + abs(0.5 - b / E)
    assert cv.execs[1].turnover == pytest.approx(traded)
    assert np.prod(cv.g[2:5]) == pytest.approx(E * (1 - traded * 5e-4))


# ── GR replay and the cut ────────────────────────────────────────────────────

def test_always_in_equal_weight_cell_reproduces_ew9(built):
    P, me, j0 = built
    forced = M.simulate(P, M.decision_table(P, me, j0, None), "forced", M.COST_BP)
    ks = sorted(M.decision_table(P, me, j0, None))
    ew = M.benchmark_rebalanced(P, {t: 1 / NT for t in M.TICKERS}, ks, "EW-9", M.COST_BP)
    grid = M.month_grid(P, ks[0])
    a, b = M.monthly(forced.g, grid), M.monthly(ew.g, grid)
    assert np.max(np.abs(a - b)) <= M.GR_TOL
    assert M.gate_replay(a, b)[0].endswith("PASS")
    with pytest.raises(M.Refused):
        M.gate_replay(a, b + 1e-6)


def test_in_sample_report_ignores_every_close_after_the_cut(inp, tmp_path):
    """GC: the whole in-sample report is identical when every close after 2026-09-22
    changes."""
    def run(x):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            M.run_in_sample(x, boot_n=20, opt_dir=tmp_path, commission=0.65, divs={})
        return buf.getvalue()
    a = run(inp)
    b = run(_perturb_after(inp, M.IN_SAMPLE_END))
    assert a == b
    assert "GR replay" in a and "PASS" in a


# ── windows ──────────────────────────────────────────────────────────────────

def test_mdd_peak_starts_at_the_rebased_one():
    assert M.mdd(np.array([-0.10, 0.05])) == pytest.approx(0.10)
    assert M.mdd(np.array([0.10, -0.10])) == pytest.approx(0.10)
    assert M.mdd(np.array([0.05, 0.05])) == 0.0


def test_window_reads_only_its_own_months(built):
    P, me, j0 = built
    ks = sorted(M.decision_table(P, me, j0, None))
    grid = M.month_grid(P, ks[0])
    w = M.make_window(grid, "h", *M.HOLDOUT)
    assert w.months[0] == "2017-01" and w.months[-1] == "2026-08"
    r = np.zeros(len(grid.months))
    r[: w.lo] = -0.5                       # a crash before the window
    r[w.lo] = 0.10
    r[w.lo + 1] = -0.05
    assert M.mdd(w.sl(r)) == pytest.approx(0.05)
    assert M.cagr(w.sl(r)) == pytest.approx((1.10 * 0.95) ** (12 / w.n) - 1)


def test_months_are_complete_only(built):
    P, me, j0 = built
    ks = sorted(M.decision_table(P, me, j0, None))
    grid = M.month_grid(P, ks[0])
    assert grid.months[-1] == "2026-08"   # the cut month 2026-09 is incomplete
    assert grid.months[0] == P.dates[ks[0]][:7]


def test_episodes_need_a_ten_percent_fall_and_end_at_recovery():
    ew = np.array([0.0, -0.06, -0.06, 0.07, 0.07, -0.05])
    cell = np.zeros_like(ew)
    eps = M.episodes(ew, cell)
    assert len(eps) == 1
    e = eps[0]
    assert e.peak == 0 and e.trough == 2 and e.depth == pytest.approx(1 - 0.94 ** 2)
    assert e.recovery == 4 and e.cell_dd == 0.0
    assert M.episodes(np.array([-0.05, 0.01]), np.zeros(2)) == []


# ── verdicts ─────────────────────────────────────────────────────────────────

POS, NEG, STRADDLE = (0.1, 0.3), (-0.3, -0.1), (-0.1, 0.2)


@pytest.mark.parametrize("kw, word, notes", [
    (dict(refused="GI"), "REFUSED (GI)", []),
    (dict(powered=False, ds_hold_ci=POS, dm_hold_ci=POS), "UNDERPOWERED", []),
    (dict(pbo=0.6, ds_hold_ci=STRADDLE, dm_hold_ci=POS), "PBO-VETO", []),
    (dict(pbo=0.6, ds_hold_ci=STRADDLE, dm_hold_ci=STRADDLE), "NULL", []),
    (dict(ds_hold_ci=POS, dm_hold_ci=POS), "BEATS-EW", []),
    (dict(ds_hold_ci=STRADDLE, dm_hold_ci=POS), "DRAWDOWN-ONLY", []),
    (dict(ds_hold_ci=NEG, dm_hold_ci=POS), "DRAWDOWN-ONLY", ["Sharpe clearly worse"]),
    (dict(ds_hold_ci=POS, dm_hold_ci=STRADDLE), "SHARPE-ONLY", []),
    (dict(ds_hold_ci=POS, dm_hold_ci=NEG), "SHARPE-ONLY", ["drawdown clearly worse"]),
    (dict(ds_hold_ci=NEG, dm_hold_ci=STRADDLE), "CONTRARY", []),
    (dict(ds_hold_ci=STRADDLE, dm_hold_ci=STRADDLE), "NULL", []),
    (dict(ds_disc=-0.1, ds_hold_ci=POS, dm_hold_ci=STRADDLE), "NULL",
     ["holdout gain, discovery sign disagrees"]),
    (dict(dm_disc=0.0, ds_hold_ci=STRADDLE, dm_hold_ci=POS), "NULL",
     ["holdout gain, discovery sign disagrees"]),
    (dict(pbo=0.4, ds_hold_ci=POS, dm_hold_ci=POS), "BEATS-EW", ["selection fragile"]),
    (dict(pbo=0.5, ds_hold_ci=POS, dm_hold_ci=POS), "BEATS-EW", ["selection fragile"]),
    (dict(pbo=0.25, ds_hold_ci=POS, dm_hold_ci=POS), "BEATS-EW", []),
    (dict(ds_disc=-0.1, ds_hold_ci=POS, dm_hold_ci=NEG), "CONTRARY", []),
])
def test_headline_word_first_match(kw, word, notes):
    args = dict(powered=True, pbo=0.1, ds_disc=0.1, ds_hold_ci=STRADDLE, dm_disc=0.1,
                dm_hold_ci=STRADDLE)
    args.update(kw)
    w, n = M.headline_word(**args)
    assert w == word and n == notes


def test_forward_words():
    assert M.forward_word(0.1, 0.1) == "FORWARD-AGREES"
    assert M.forward_word(0.1, -0.1) == "FORWARD-SPLIT"
    assert M.forward_word(0.0, 0.0) == "FORWARD-AGAINST"


# ── GB distribution check and the options-arm pickers ────────────────────────

def test_gb_distribution_check_matches_the_implied_jump():
    close_prev, div = 20.0, 1.0
    step = close_prev / (close_prev - div) - 1.0
    assert M.confirmed_distribution(close_prev, step, div)
    assert not M.confirmed_distribution(close_prev, step + 0.01, div)
    assert not M.confirmed_distribution(close_prev, step, None)


def test_expiry_and_strike_pickers():
    # 2022-01-12 -> 2022-03-18 is 65 calendar days
    assert M.pick_expiry("2022-01-12", ["2022-03-18", "2022-02-18"]) == "2022-03-18"
    # third Fridays only: 2022-04-14 is a Thursday, 2022-04-22 a fourth Friday
    assert not M.is_third_friday("2022-04-14") and not M.is_third_friday("2022-04-22")
    assert M.pick_expiry("2022-02-10", ["2022-04-14", "2022-04-22"]) is None
    # 51 and 79 days from 2021-12-01: a DTE tie takes the later expiry
    assert M.pick_expiry("2021-12-01", ["2022-01-21", "2022-02-18"]) == "2022-02-18"
    # an expiry on or before the entry day cannot be opened
    assert M.pick_expiry("2022-03-18", ["2022-03-18"]) is None
    strikes = ["99", "101", "105"]
    assert M.pick_strike(strikes, 100.0, tie_high=False) == "99"
    assert M.pick_strike(strikes, 100.0, tie_high=True) == "101"
