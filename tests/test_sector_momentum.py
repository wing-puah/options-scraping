"""sector_momentum: decision keys, formation and skip windows, pairing, EW-9 rebalance, cost,
ties, the PBO metric, gate GK's bound and ordering, GB's peer check, GE's date rule, the cut
and negative ^IRX quotes, on synthetic panels. No market data is read.

Each registered mechanics test names in its docstring the one-step mutation it must fail
under (registration, "Mechanics tests the build must include")."""
from __future__ import annotations

import contextlib
import io
from datetime import date, timedelta

import numpy as np
import pytest

from scripts.backtest_study.f1_selection.signal import sector_momentum as S

NT = S.NT


def _weekdays(start: str, end: str) -> list[str]:
    d, e = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _inputs(start="1998-12-01", end="2026-11-20", seed=7, irx_end=None) -> S.Inputs:
    rng = np.random.default_rng(seed)
    dates = _weekdays(start, end)
    n = len(dates)
    etf = {}
    for i, t in enumerate(S.TICKERS):
        px = 30 * np.exp(np.cumsum(rng.normal(0.0002, 0.012 + 0.001 * i, n)))
        etf[t] = S.Series(list(dates), px.copy(), px.copy())
    spy = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.011, n)))
    irx_dates = [d for d in dates if irx_end is None or d <= irx_end]
    irx = S.Series(irx_dates, 2.0 + rng.normal(0, 0.05, len(irx_dates)),
                   np.full(len(irx_dates), np.nan))
    return S.Inputs(etf, S.Series(list(dates), spy.copy(), spy.copy()), irx, None, None, {})


def _token():
    return S.GKPass(S._GK_KEY, S.BLOCK, [], {S.COST_BP: 0.0})


# ── 1. decision keys ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def panel():
    inp = _inputs().cut(S.IN_SAMPLE_END)
    P = S.build_panel(inp)
    M = S.months_from_panel(P)
    return inp, P, M, S.first_decision(M)


def test_decision_keys_are_the_first_session_after_a_month_end(panel):
    """Mutation: keying the decision table on the month-end itself."""
    _, P, M, j0 = panel
    tab = S.decision_table(P, M, j0, S.HEADLINE)
    me = set(S.month_end_idx(P.dates))
    assert len(tab) >= 300
    for k in tab:
        assert (k - 1) in me
        assert P.dates[k][:7] != P.dates[k - 1][:7]


def test_last_row_of_a_cut_series_is_never_a_month_end():
    d = ["2024-01-30", "2024-01-31"]
    assert S.month_end_idx(d) == []
    assert S.month_end_idx(d + ["2024-02-01"]) == [1]


# ── 2-3. formation window and skip month ─────────────────────────────────────

def _ladder(j: int) -> np.ndarray:
    """Month-end levels where ETF i grows a little faster than ETF i+1 every month, so the
    top three are XLB, XLE, XLF and ETF 4 (XLK) sits fifth."""
    L = np.ones((j + 1, NT))
    for m in range(1, j + 1):
        L[m] = L[m - 1] * (1.0 + 0.01 * (NT - np.arange(NT)) / NT)
    return L


def _sel(L, j, cell):
    lb, skip, k = S.parse_cell(cell)
    return S.top_k(S.formation(L, j, lb, skip), k)


def test_formation_window_reads_m12_to_m1_only():
    """Mutation: the window start one month early (M_-13) or late (M_-11)."""
    j = 20
    L = _ladder(j)
    before = L.copy()
    before[j - 12:, 4] *= 1.5          # a return only in the month ending at M_-12
    after = L.copy()
    after[j - 11:, 4] *= 1.5           # a return only in the month after M_-12
    base = _sel(L, j, "12-1-T3")
    assert np.array_equal(_sel(before, j, "12-1-T3"), base)
    assert not np.array_equal(_sel(after, j, "12-1-T3"), base)
    assert _sel(after, j, "12-1-T3")[4]


def test_skip_month_moves_12_0_but_not_12_1():
    """Mutation: dropping the skip (12-1 read to M_0)."""
    j = 20
    L = _ladder(j)
    last = L.copy()
    last[j, 4] *= 1.5                  # a return only in the month ending at M_0
    assert np.array_equal(_sel(last, j, "12-1-T3"), _sel(L, j, "12-1-T3"))
    assert not np.array_equal(_sel(last, j, "12-0-T3"), _sel(L, j, "12-0-T3"))


def test_holdings_ignore_every_level_after_the_decision():
    """GX: changing every later month-end level leaves the earlier decisions unchanged."""
    rng = np.random.default_rng(3)
    L = np.cumprod(1 + rng.normal(0.005, 0.05, (60, NT)), axis=0)
    W = S.rule_weights(L, S.HEADLINE, 12)
    L2 = L.copy()
    L2[31:] *= rng.uniform(0.5, 1.5, L2[31:].shape)
    W2 = S.rule_weights(L2, S.HEADLINE, 12)
    assert np.array_equal(W[12:31], W2[12:31])


# ── 4. headline sign ─────────────────────────────────────────────────────────

def test_headline_sign_planted_top_three_gain():
    """Mutation: computing EW-9 minus the rule."""
    rng = np.random.default_rng(11)
    J, j0 = 300, 12
    B = np.ones((J + 1, NT))
    A = np.ones((J + 1, NT))
    L = np.ones((J + 1, NT))
    for j in range(1, J + 1):
        g = 1.0 + rng.normal(0.006, 0.01, NT)
        if j - 1 >= j0:
            top = S.top_k(S.formation(L, j - 1, 12, 1), 3)
            g = g + 0.01 * top
        A[j] = g
        L[j] = L[j - 1] * g
    W = S.rule_weights(L, S.HEADLINE, j0)
    r, _ = S.simulate_rule(B, A, W, j0, 0.0)
    re_, _ = S.simulate_ew(B, A, j0, 0.0)
    d = S.graded_excess(r, re_, _token())[j0 + 1:]
    xs = 12 * d.mean()
    assert xs > 0
    assert xs == pytest.approx(0.08, abs=0.012)       # 1% x 6/9 x 12


# ── 5. pairing ───────────────────────────────────────────────────────────────

def test_new_holdings_earn_from_the_close_after_execution():
    """Mutation: shifting holdings one session (trade before the execution session's return)
    or one month (W[j] or W[j-2])."""
    J, j0 = 16, 12
    B = np.ones((J + 1, NT))
    A = np.ones((J + 1, NT))
    W = np.full((J + 1, NT), np.nan)
    W[j0:] = 0.0
    W[j0, :3] = 1 / 3                 # held in month j0+1
    W[j0 + 1:, 3:6] = 1 / 3            # decided at j0+1, held from month j0+2
    B[j0 + 2, 3] = 2.0                 # the session into the execution close: old holdings'
    B[j0 + 2, 0] = 1.3                 # ...and the old holdings do earn it
    A[j0 + 2, 3] = 1.1                 # after the execution close: new holdings'
    r, _ = S.simulate_rule(B, A, W, j0, 0.0)
    assert r[j0 + 1] == pytest.approx(0.0)
    assert r[j0 + 2] == pytest.approx((1 + 0.3 / 3) * (1 + 0.1 / 3) - 1)


# ── 6. rebalance ─────────────────────────────────────────────────────────────

def test_ew9_is_back_at_one_ninth_after_the_next_execution_and_pays_for_it():
    """Mutation: letting EW-9 drift (no trade back to 1/9)."""
    J, j0 = 15, 12
    B = np.ones((J + 1, NT))
    A = np.ones((J + 1, NT))
    A[j0 + 1, 0] = 2.0
    trace = []
    r, turn = S.simulate_ew(B, A, j0, 5.0, trace)
    j, w_post, cost = trace[0]
    assert j == j0 + 2
    assert np.allclose(w_post, 1 / 9)
    drift = np.array([2 / 9] + [1 / 9] * 8) / (10 / 9)
    traded = np.abs(1 / 9 - drift).sum()          # equity is rebased to 1 at each month-end
    assert cost == pytest.approx(5e-4 * traded)
    assert turn[j0 + 2] == pytest.approx(traded)
    assert r[j0 + 2] == pytest.approx(-5e-4 * traded)


# ── 7. cost ──────────────────────────────────────────────────────────────────

def test_cost_is_five_bp_on_traded_notional_and_zero_at_target():
    """Mutation: charging one side only (buys only)."""
    J, j0 = 14, 12
    B = np.ones((J + 1, NT))
    A = np.ones((J + 1, NT))
    W = np.full((J + 1, NT), np.nan)
    W[j0:] = 0.0
    W[j0:, :3] = 1 / 3
    r0, t0 = S.simulate_rule(B, A, W, j0, 5.0)
    assert t0[j0 + 2] == 0.0 and r0[j0 + 2] == 0.0
    W2 = W.copy()
    W2[j0 + 1] = 0.0
    W2[j0 + 1, 3:6] = 1 / 3            # sell three, buy three: traded notional 2
    r, t = S.simulate_rule(B, A, W2, j0, 5.0)
    assert t[j0 + 2] == pytest.approx(2.0)
    assert r[j0 + 2] == pytest.approx(-5e-4 * 2.0)


# ── 8. ties ──────────────────────────────────────────────────────────────────

def test_ties_take_the_alphabetical_order():
    """Mutation: reversing the tie-break."""
    F = np.zeros(NT)
    assert list(np.where(S.top_k(F, 3))[0]) == [0, 1, 2]
    F[8] = 1e-13                        # within 1e-12: still a tie
    assert list(np.where(S.top_k(F, 3))[0]) == [0, 1, 2]
    F[8] = 1e-9                         # beyond it: XLY leads
    assert list(np.where(S.top_k(F, 3))[0]) == [0, 1, 8]


# ── 9. PBO metric ────────────────────────────────────────────────────────────

def test_pbo_metric_is_the_column_mean_of_d_m(monkeypatch):
    """Mutation: passing a Sharpe metric to cscv."""
    seen = {}

    def fake(M, S=16, metric=None, report_metric=None, **kw):
        seen["metric"], seen["report"] = metric, report_metric

        class R:
            pbo = 0.5
        return R()

    monkeypatch.setattr(S.PBO, "cscv", fake)
    X = np.random.default_rng(1).normal(0.001, 0.02, (64, 12))
    S.run_pbo(X, [f"m{i}" for i in range(64)])
    assert np.allclose(seen["metric"](X), X.mean(axis=0))
    assert np.allclose(seen["report"](X), X.mean(axis=0))


# ── 10. GK ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def null_set(panel):
    _, P, M, j0 = panel
    wins = dict(zip(("graded", "early", "late"), S.windows_of(M, j0)))
    rb = S.real_basis(P, M, j0, wins["graded"].hi - 1)
    ns = S.simulate_null("G-IID", rb, 120, costs=(0.0, S.COST_BP))
    return ns, wins, M.labels[:wins["graded"].hi]


def test_gk_refuses_a_narrow_bootstrap_and_passes_the_real_one(null_set):
    """Mutation: removing the bound check."""
    ns, wins, lab = null_set

    def narrow(d, block, boot_n):
        dr = S.bootstrap_draws(d, block, boot_n)
        pt = 12.0 * d.mean(axis=0)
        return pt + 0.2 * (dr - pt)

    tok, gens = S.gate_calibration([ns], wins, lab, S.BLOCK, 1000, narrow, verbose=False,
                                   power_costs=(S.COST_BP,))
    assert gens[0].size > S.GK_BOUND
    assert tok is None
    tok, gens = S.gate_calibration([ns], wins, lab, S.BLOCK, 1000, verbose=False,
                                   power_costs=(S.COST_BP,))
    assert gens[0].size <= S.GK_BOUND
    assert isinstance(tok, S.GKPass)


def test_no_real_statistic_without_the_gk_token():
    with pytest.raises(RuntimeError):
        S.graded_excess(np.zeros(5), np.zeros(5), None)
    with pytest.raises(RuntimeError):
        S.GKPass(object(), 6, [], {})


def test_a_gk_refusal_prints_no_real_statistic(monkeypatch):
    monkeypatch.setattr(S, "gate_calibration", lambda *a, **k: (None, []))
    monkeypatch.setattr(S, "print_gk", lambda *a, **k: None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), pytest.raises(S.Refused):
        S.run_in_sample(_inputs(), n_paths=4, boot_n=50)
    text = buf.getvalue()
    assert "XS" not in text and "PBO" not in text


def test_delta80_is_the_first_grid_value_reaching_eighty_percent():
    rates = np.zeros(len(S.DELTA_GRID))
    assert S.d80_of(rates) == float("inf")
    rates[7:] = 0.8
    assert S.d80_of(rates) == S.DELTA_GRID[7] == 0.02


# ── 11. GB peer check ────────────────────────────────────────────────────────

def _fake_distribution(P: S.Panel, i: int, k: int, rise: float) -> dict:
    """Lift the adjusted close by `rise` from session k on with no fall in Close, and list
    a matching distribution in the feed."""
    P.adj[k:, i] *= 1.0 + rise
    cp = P.close[k - 1, i]
    return {S.TICKERS[i]: {P.dates[k]: cp * rise / (1.0 + rise)}}


def test_gb_peer_check_flags_a_fake_listed_distribution(panel):
    """Mutation: dropping the peer check (a feed match alone passes)."""
    _, P0, _, _ = panel
    P = S.Panel(P0.dates, P0.adj.copy(), P0.close.copy(), P0.spy, P0.irx_c, P0.irx_carry, P0.tb)
    divs = _fake_distribution(P, 1, 2000, 0.06)
    lines, flags = S.gate_basis(P, divs)
    assert len(flags) == 1 and flags[0].ticker == "XLE" and flags[0].k == 2000
    assert S.settle_flags("NULL", [("XLE x", "BEATS-EW")]).startswith("gate: GB-flagged row XLE x")
    assert S.settle_flags("NULL", [("XLE x", "NULL")]) is None


def test_gb_real_distribution_passes_and_unlisted_rise_refuses(panel):
    _, P0, _, _ = panel
    P = S.Panel(P0.dates, P0.adj.copy(), P0.close.copy(), P0.spy, P0.irx_c, P0.irx_carry, P0.tb)
    k, i = 2000, 2
    cp = P.close[k - 1, i]
    D = cp * 0.05
    P.close[k:, i] *= 1 - 0.05                 # the raw close drops; adjusted stays smooth
    _, flags = S.gate_basis(P, {"XLF": {P.dates[k]: D}})
    assert flags == []
    with pytest.raises(S.Refused):
        S.gate_basis(P, {})


# ── 12. GE dates ─────────────────────────────────────────────────────────────

def test_ge_needs_a_session_after_the_cut():
    """Mutation: comparing with "on or after" the cut."""
    with pytest.raises(S.Refused):
        S.gate_dates(_inputs(end="2026-09-22"))
    assert "PASS" in S.gate_dates(_inputs(end="2026-09-23"))[0]


# ── 13. the cut ──────────────────────────────────────────────────────────────

def _perturb_after(inp: S.Inputs, cut: str, seed=99) -> S.Inputs:
    rng = np.random.default_rng(seed)
    etf = {}
    for t, s in inp.etf.items():
        k = int(np.searchsorted(np.array(s.dates), cut, side="right"))
        f = np.ones(len(s.dates))
        f[k:] = rng.uniform(0.5, 1.5, len(s.dates) - k)
        etf[t] = S.Series(s.dates + ["2026-11-23"], np.append(s.close * f, 1.0),
                          np.append(s.adj * f, 1.0))
    sp = inp.spy
    k = int(np.searchsorted(np.array(sp.dates), cut, side="right"))
    f = np.ones(len(sp.dates))
    f[k:] = rng.uniform(0.5, 1.5, len(sp.dates) - k)
    spy = S.Series(sp.dates + ["2026-11-23"], np.append(sp.close * f, 1.0), np.append(sp.adj * f, 1.0))
    c = inp.irx.close.copy()
    k = int(np.searchsorted(np.array(inp.irx.dates), cut, side="right"))
    c[k:] = rng.uniform(-1, 9, len(c) - k)
    irx = S.Series(list(inp.irx.dates), c, inp.irx.adj.copy())
    return S.Inputs(etf, spy, irx, None, None, {})


def _report(inp) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = S.run_in_sample(inp, n_paths=8, boot_n=100, best_month=True)
    return buf.getvalue(), out


def test_in_sample_report_ignores_every_row_after_the_cut():
    """Mutation: reading the uncut series."""
    inp = _inputs()
    a, out = _report(inp)
    b, _ = _report(_perturb_after(inp, S.IN_SAMPLE_END))
    assert a == b
    assert out["first"] == "2000-01"
    assert out["wins"]["graded"].labels[-1] == "2026-08"
    assert out["wins"]["graded"].n == 320


# ── 14. negative ^IRX ────────────────────────────────────────────────────────

def test_zero_and_negative_irx_closes_are_used_as_printed(tmp_path):
    """Mutation: dropping non-positive rows when reading ^IRX."""
    p = tmp_path / "IRX.csv"
    p.write_text("date,close,adj_close\n2020-03-02,1.0,1.0\n2020-03-03,0.0,0.0\n"
                 "2020-03-04,-0.05,-0.05\n2020-03-05,,\n2020-03-06,0.5,0.5\n")
    irx = S.read_series(p, yield_series=True)
    assert list(irx.close) == [1.0, 0.0, -0.05, 0.5]
    dates = ["2020-03-02", "2020-03-03", "2020-03-04", "2020-03-05", "2020-03-06", "2020-03-09"]
    px = np.linspace(10, 11, len(dates))
    etf = {t: S.Series(list(dates), px.copy(), px.copy()) for t in S.TICKERS}
    P = S.build_panel(S.Inputs(etf, S.Series(list(dates), px.copy(), px.copy()), irx, None, p, {}))
    assert P.tb[2] == 0.0
    assert P.tb[3] == pytest.approx(-0.05 / 100 / 252)
    assert P.tb[4] == pytest.approx(-0.05 / 100 / 252)        # a session with no close carries
    assert P.irx_carry[3] == 1
    assert S.raw_nonpositive(p, "2020-03-01", "2020-03-31") == 2


# ── verdict table ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("g,pbo,d80,word", [
    (S.Graded(0.04, 0.01, 0.02, 0.05), 0.2, 0.02, "BEATS-EW"),
    (S.Graded(0.04, 0.01, 0.02, 0.05), 0.6, 0.05, "PBO-VETO"),
    (S.Graded(-0.04, 0.01, 0.02, -0.05), 0.2, 0.05, "CONTRARY"),
    (S.Graded(0.04, 0.01, -0.01, 0.05), 0.2, 0.05, "UNDERPOWERED-BY-DESIGN"),
    (S.Graded(0.01, 0.30, 0.01, 0.01), 0.2, 0.03, "NULL"),
    (S.Graded(0.01, 0.05, 0.01, 0.01), 0.2, 0.02, "NULL"),
])
def test_headline_word_first_match(g, pbo, d80, word):
    assert S.headline_word(True, pbo, g, d80)[0] == word
    assert S.headline_word(False, pbo, g, d80)[0] == "UNDERPOWERED"
    assert S.headline_word(True, pbo, g, d80, refused="gate")[0] == "REFUSED (gate)"


def test_beats_with_low_power_keeps_its_word_and_says_so():
    w, nt = S.headline_word(True, 0.2, S.Graded(0.04, 0.01, 0.02, 0.05), 0.05)
    assert w == "BEATS-EW" and any("low power" in x for x in nt)


# ── 9. null generators, power path, first-month pairing ──────────────────────

def test_first_graded_month_earns_only_the_rest_of_month_growth_for_both_arms():
    """Mutation: applying the execution-session return B in the first graded month
    (`j > j0` instead of `j > j0 + 1`) in simulate_rule or simulate_ew."""
    J, j0 = 15, 12
    B = np.ones((J + 1, NT))
    A = np.ones((J + 1, NT))
    W = np.full((J + 1, NT), np.nan)
    W[j0:] = 0.0
    W[j0:, :3] = 1 / 3
    B[j0 + 1, 0] = 2.0                 # earned before the entry close: nobody holds it yet
    B[j0 + 1, 3] = 3.0
    A[j0 + 1, 0] = 1.2
    A[j0 + 1, 3] = 1.9
    r, _ = S.simulate_rule(B, A, W, j0, 5.0)
    assert r[j0 + 1] == pytest.approx((1.2 + 1.0 + 1.0) / 3 - 1)
    re_, _ = S.simulate_ew(B, A, j0, 5.0)
    assert re_[j0 + 1] == pytest.approx((1.2 + 1.9 + 7.0) / 9 - 1)


def test_pass_rate_needs_the_shifted_draws_to_clear_zero_and_is_monotone_in_the_shift():
    """Mutation: flipping the sign of the shift applied to the sorted draws."""
    rng = np.random.default_rng(3)
    n_paths, n_draws = 40, 200
    srt = np.sort(rng.normal(-0.05, 0.01, (n_draws, n_paths)), axis=0)
    xs = {w: np.full(n_paths, -0.04) for w in ("graded", "early", "late")}
    shifts = [0.0, 0.02, 0.05, 0.10, 0.15]
    rates = S._pass_rates(xs, srt, shifts)
    assert rates[0] == 0.0                     # draws all below zero, XS negative
    assert rates[2] == 0.0                     # shifted draws straddle zero: cannot reject
    assert rates[4] == 1.0                     # shifted well clear of zero
    assert np.all(np.diff(rates) >= 0)


def test_p_two_sided_is_twice_the_smaller_tail_capped_at_one():
    draws = np.array([[-3.0, 1.0, -1.0, 0.0],
                      [-2.0, 2.0, -1.0, 0.0],
                      [-1.0, 3.0, 1.0, 0.0],
                      [1.0, 4.0, 1.0, 0.0]])
    p = S.p_two_sided(draws)
    assert p[0] == pytest.approx(0.5)          # 1/4 at or above zero, doubled
    assert p[1] == pytest.approx(0.0)          # all positive
    assert p[2] == pytest.approx(1.0)          # symmetric
    assert p[3] == pytest.approx(1.0)          # all zero: both tails 1, doubled, capped


def test_real_basis_demeans_every_asset_to_one_common_mean():
    """Mutation: no demeaning (`Rd = R`), so the month-resampling null keeps each asset's own
    mean."""
    import dataclasses
    inp = _inputs(start="2019-12-01", end="2021-06-30")
    P = S.build_panel(inp)
    mus = np.linspace(-0.001, 0.004, NT)                 # clearly different daily means
    adj = 50.0 * np.cumprod(np.tile(1.0 + mus, (len(P.dates), 1)), axis=0)
    P = dataclasses.replace(P, adj=adj, close=adj.copy())
    M = S.months_from_panel(P)
    rb = S.real_basis(P, M, 1, len(M.me) - 1)
    assert rb.mu_bar == pytest.approx(mus.mean())
    assert np.ptp(rb.month_B[:, 0] - 1.0) < 1e-12 and np.ptp(rb.month_B.mean(axis=0)) > 0.004
    first = rb.month_Bd - 1.0
    assert np.allclose(first.mean(axis=0), rb.mu_bar)    # every asset's column mean is common
    last_a = rb.month_Ad[-1]
    assert np.allclose(last_a, last_a[0])


def test_garch_null_scale_has_unit_mean_variance():
    """Mutation: dropping `* math.sqrt(NT)` from the GARCH scale, so E[s2] falls from 1 to
    about 0.02."""
    T = 400
    sigma = 0.01
    rb = S.RealBasis(R=np.zeros((T, NT)), counts=[1] * T, month_B=None, month_A=None,
                     month_Bd=None, month_Ad=None, mu_bar=0.0,
                     cov=np.eye(NT) * sigma ** 2, J=T, j0=12)
    B, A = S.null_batch("G-GARCH", rb, np.random.default_rng(5), 150)
    x = B[:, 1:, :] - 1.0                                # one session per month
    ratio = float(np.mean(x * x) / sigma ** 2)
    assert 0.5 < ratio < 1.6
    assert np.allclose(A[:, 1:], 1.0)


def test_best_sector_month_finds_the_planted_jump():
    """Replacing the planted leader's best month by EW-9's returns lowers XS most."""
    dates = _weekdays("2019-01-01", "2021-06-30")
    n = len(dates)
    daily = np.ones((n, NT))
    daily[:, 3] = 1.002                                  # a steady leader, held by the rule
    daily[[k for k, d in enumerate(dates) if d.startswith("2020-03")], 3] = 1.02
    adj = 50.0 * np.cumprod(daily, axis=0)
    P = S.Panel(dates, adj, adj.copy(), adj[:, 0].copy(), np.zeros(n), np.zeros(n, dtype=bool),
                np.zeros(n))
    M = S.months_from_panel(P)
    j0 = S.first_decision(M)
    g_ew = np.ones(n)
    g_ew[1:] = (adj[1:] / adj[:-1]).mean(axis=1)
    gw = S.Window("graded", j0 + 1, len(M.me), M.labels[j0 + 1:])
    i, q, xs = S.best_sector_month(M, j0, gw, g_ew, _token())
    assert i == 3
    assert M.labels[gw.lo + q] == "2020-03"
    W = S.rule_weights(M.L, S.HEADLINE, j0)
    rr, _ = S.simulate_rule(M.B, M.A, W, j0, S.COST_BP)
    re_, _ = S.simulate_ew(M.B, M.A, j0, S.COST_BP)
    base = 12.0 * gw.sl(rr - re_).mean()
    assert 0 < xs < base                                 # the replacement removed some of the gain
