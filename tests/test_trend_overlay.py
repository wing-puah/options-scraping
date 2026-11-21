"""trend_overlay: the rules, the execution lag, the curves and the verdict ladders, on
synthetic series. No market data is read."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from scripts.backtest_study.f4_deployment import trend_overlay as T


def _weekdays(start: str, n: int) -> list[str]:
    d = date.fromisoformat(start)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _series(n=900, seed=1, start="1990-01-01"):
    rng = np.random.default_rng(seed)
    dates = _weekdays(start, n)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    return T.Series(dates, close, close.copy())


def _window(sig, start, end):
    irx = T.Series([], np.array([]), np.array([]))
    return T.build_window("w", sig, False, sig, irx, start, end)


# ── calendar and rules ───────────────────────────────────────────────────────

def test_last_row_is_never_a_month_end():
    dates = ["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-28"]
    assert T.month_end_idx(dates) == [1]           # 2020-02-28 is the last row: not a decision


def test_cut_series_invents_no_decision():
    s = _series()
    cut = s.cut(s.dates[600])
    for rule in ("T-10M", "T-12M"):
        dd, _ = T.decisions(cut, rule)
        assert cut.dates[-1] not in dd


def test_sma200_state_and_tie_is_out():
    dates = _weekdays("2000-01-03", 200)
    c = np.full(200, 10.0)
    dd, ss = T.decisions(T.Series(dates, c, c), "T-200D")
    assert dd == [dates[-1]] and ss == [False]        # equal to its mean: OUT
    c2 = c.copy()
    c2[-1] = 11.0
    _, ss2 = T.decisions(T.Series(dates, c2, c2), "T-200D")
    assert ss2 == [True]


def test_ten_month_and_momentum_rules():
    s = _series(n=600)
    me = T.month_end_idx(s.dates)
    mc = s.close[me]
    dd, ss = T.decisions(s, "T-10M")
    assert dd[0] == s.dates[me[9]]
    assert ss[0] == bool(mc[9] > mc[:10].mean())
    dd, ss = T.decisions(s, "T-12M")
    assert dd[0] == s.dates[me[12]] and ss[0] == bool(mc[12] > mc[0])


# ── execution lag and lookahead ──────────────────────────────────────────────

def test_exposure_lag_is_two_sessions():
    dates = _weekdays("2001-01-01", 10)
    e = T.exposure(dates, [dates[3]], [True])
    # decision at close 3, executed at close 4, first earned return is session 5
    assert np.isnan(e[:5]).all() and (e[5:] == 1.0).all()


@pytest.mark.parametrize("rule", T.RULES)
def test_no_lookahead_every_later_close_changed(rule):
    s = _series(n=800, seed=3)
    base = T.exposure(s.dates, *T.decisions(s, rule))
    rng = np.random.default_rng(0)
    for k in range(300, 800, 37):
        j = k - 1                                  # closes from k-1 on may change
        noisy = T.Series(s.dates, s.close.copy(), s.adj.copy())
        noisy.close[j:] *= rng.uniform(0.3, 3.0, len(s.close) - j)
        e = T.exposure(s.dates, *T.decisions(noisy, rule))
        assert (np.isnan(base[k]) and np.isnan(e[k])) or base[k] == e[k]


def test_gate_lookahead_passes_on_synthetic():
    s = _series(n=900, seed=4)
    lines = T.gate_lookahead(s, s.dates, s.dates[400], s.dates[-1], samples=10)
    assert "PASS" in lines[0]


# ── curves ───────────────────────────────────────────────────────────────────

def test_overlay_growth_cost_and_cash():
    s = _series(n=900, seed=5)
    w = _window(s, s.dates[400], s.dates[-1])
    g0 = T.overlay_growth(w, "T-200D", cost_bp=0.0)
    g10 = T.overlay_growth(w, "T-200D", cost_bp=10.0)
    sw = T.switch_mask(w, "T-200D")
    assert np.allclose(g10[~sw], g0[~sw])
    assert np.allclose(g10[sw], g0[sw] * 0.999)
    out = w.expo["T-200D"] < 0.5
    assert np.allclose(g0[out], 1.0)                # cash 0%
    assert not sw[-1]                               # a change at the last close is outside


def test_metrics_known_path():
    g = np.array([1.1, 0.5, 1.0, 2.2])              # equity 1.1, .55, .55, 1.21
    m = T.metrics(g)
    assert m.mdd == pytest.approx(0.5)
    assert m.tuw_longest == 2
    assert m.end_equity == pytest.approx(1.21)


def test_episodes_and_savings():
    g_long = np.array([1.0, 0.7, 1.0, 1.5, 1.01])   # 30% fall, recovers at index 3
    g_ov = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    eps = T.episodes(g_long, g_ov)
    assert len(eps) == 1
    e = eps[0]
    assert (e.peak, e.trough, e.recovery) == (0, 1, 3)
    assert e.depth == pytest.approx(0.3)
    assert e.save_trough == pytest.approx(-np.log(0.7))


def test_spells_and_whipsaw():
    s = _series(n=1200, seed=6)
    w = _window(s, s.dates[400], s.dates[-1])
    g = T.overlay_growth(w, "T-200D")
    sp = T.out_spells(w, "T-200D", g)
    wp = T.whipsaw(w, "T-200D", g)
    closed = [x for x in sp if x.end is not None and x.start >= 0]
    assert wp.n_spells == len(closed)
    assert wp.n_whipsaw == sum(1 for x in closed if x.end - x.start <= T.WHIPSAW_N)


def test_bootstrap_identity_block_reproduces_point():
    s = _series(n=900, seed=7)
    w = _window(s, s.dates[400], s.dates[-1])
    gl = 1 + w.r
    g = T.overlay_growth(w, "T-10M")
    out = T.boot_deltas(gl, {"x": g}, block=len(gl), n=3)
    assert out["x"][0][0] == pytest.approx(T.mdd(gl) - T.mdd(g))


# ── verdict ladders ──────────────────────────────────────────────────────────

def test_verdict_a_ladder():
    assert T.verdict_a(1, 0.1, 0.0, 1, 0.5) == "UNDERPOWERED"
    assert T.verdict_a(3, 0.0, 0.0, 1, 0.5) == "NO-DRAWDOWN-BENEFIT"
    assert T.verdict_a(3, 0.1, -0.021, 1, 0.5) == "TOO-COSTLY"
    assert T.verdict_a(3, 0.1, -0.01, 0.4, 0.5) == "TOO-COSTLY"
    assert T.verdict_a(3, 0.1, -0.01, 0.6, 0.5) == "CUTS-DRAWDOWN-AT-A-COST"
    assert T.verdict_a(3, 0.1, 0.0, 0.6, 0.5) == "CUTS-DRAWDOWN-NO-COST"


def test_agreement():
    assert T.agreement("CUTS-DRAWDOWN-AT-A-COST", "CUTS-DRAWDOWN-NO-COST") == "AGREES"
    assert T.agreement("TOO-COSTLY", "NO-DRAWDOWN-BENEFIT") == "AGREES"
    assert T.agreement("CUTS-DRAWDOWN-AT-A-COST", "TOO-COSTLY") == "DISAGREES"
    assert T.agreement("UNDERPOWERED", "TOO-COSTLY") == "NOT COMPARABLE"


def test_verdict_b_ladder():
    assert T.verdict_b(False, 1, 0, 1) == "UNDERPOWERED"
    assert T.verdict_b(True, 1, 0, 1, inert=True) == "INERT"
    assert T.verdict_b(True, 0, 0, 1) == "NO-BOOK-DRAWDOWN-BENEFIT"
    assert T.verdict_b(True, 1, -500, 100) == "TOO-COSTLY"
    assert T.verdict_b(True, 1, -50, 100) == "CUTS-BOOK-DRAWDOWN-AT-A-COST"
    assert T.verdict_b(True, 1, 50, 100) == "CUTS-BOOK-DRAWDOWN-NO-COST"


def test_verdict_forward():
    assert T.verdict_forward(False, 0.3, 0.1, 0) == "NO-EPISODE"
    assert T.verdict_forward(True, 0.3, 0.2, -0.01) == "CUTS-DRAWDOWN"
    assert T.verdict_forward(True, 0.3, 0.27, 0) == "NO-DRAWDOWN-BENEFIT"
    assert T.verdict_forward(True, 0.3, 0.1, -0.03) == "NO-DRAWDOWN-BENEFIT"


# ── Population B wrapper ─────────────────────────────────────────────────────

def test_switch_cfg_net_cap_follows_the_date():
    class Base:
        net_cap = 2.5
        capital = 25000

    c = T.SwitchCfg(Base(), {"2025-04-01"}, 1.0)
    assert c.ranker("2025-03-31", ["a"]) == ["a"] and c.net_cap == 2.5
    c.ranker("2025-04-01", [])
    assert c.net_cap == 1.0 and c.capital == 25000


def test_in_sample_ignores_closes_after_the_cut(monkeypatch, capsys):
    """GC: the in-sample report is identical when every close after the cut changes."""
    n = 700
    dates = _weekdays("2020-01-01", n)
    rng = np.random.default_rng(9)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.015, n)))
    cut = dates[600]
    monkeypatch.setattr(T, "IN_SAMPLE_END", cut)
    monkeypatch.setattr(T, "DISCOVERY", (dates[400], cut))
    monkeypatch.setattr(T, "HOLDOUT", (dates[320], dates[390]))
    monkeypatch.setattr(T, "GSPC_FIRST", dates[0])
    monkeypatch.setattr(T, "gate_basis", lambda *a: [])

    def run(close):
        spy = T.Series(dates, close / 10, close / 10)
        inp = {"GSPC": T.Series(dates, close.copy(), close.copy()), "SPY": spy,
               "IRX": T.Series([], np.array([]), np.array([]))}
        T.run_in_sample(inp, boot_n=20)
        return capsys.readouterr().out

    a = run(c)
    c2 = c.copy()
    c2[601:] *= 1.7
    assert run(c2) == a
