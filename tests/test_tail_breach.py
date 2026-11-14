"""tail_breach — research/pre-registrations/f1_selection/regime/tail_breach.md.

Synthetic data only: the breach definitions, the no-lookahead predictor
alignment, the train/test split, the metric and the verdict words.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from scripts.backtest_study.f1_selection.regime import tail_breach as T


def _dates(n: int, start: str = "2005-01-03") -> list[str]:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _cal(adj, vix, vix3m=None, close=None, start="2005-01-03") -> T.Cal:
    n = len(adj)
    return T.Cal(dates=_dates(n, start), close=np.asarray(close if close is not None else adj, float),
                 adj=np.asarray(adj, float), vix=np.asarray(vix, float),
                 vix3m=np.asarray(vix3m if vix3m is not None else vix, float))


def _random_cal(n=400, seed=1, start="2005-01-03") -> T.Cal:
    rng = np.random.default_rng(seed)
    adj = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    vix = 15 + 5 * rng.random(n)
    return _cal(adj, vix, vix * 1.1, start=start)


# ── breach definitions ──────────────────────────────────────────────────────

def test_breach_down_uses_prior_vix_and_k():
    sig = 16.0 / 100 / math.sqrt(252)            # VIX 16 -> about 1.008% a day
    adj = [100.0, 100.0 * math.exp(-2.01 * sig), 100.0 * math.exp(-2.01 * sig) * math.exp(-1.99 * sig)]
    cal = _cal(adj, [16.0, 16.0, 40.0])
    b = T.breach_down(cal, 2.0)
    assert math.isnan(b[0])                      # no prior close
    assert b[1] == 1.0                           # -2.01 sigma
    assert b[2] == 0.0                           # -1.99 sigma; reads VIX at t-1 (16), not t (40)
    assert T.breach_down(cal, 1.5)[2] == 1.0


def test_breach_down_reads_vix_at_t_minus_1_only():
    sig = 16.0 / 100 / math.sqrt(252)
    adj = [100.0, 100.0 * math.exp(-2.5 * sig)]
    low = _cal(adj, [16.0, 10.0])
    high = _cal(adj, [16.0, 80.0])               # same-day VIX must not matter
    assert T.breach_down(low)[1] == T.breach_down(high)[1] == 1.0
    assert T.breach_down(_cal(adj, [40.0, 16.0]))[1] == 0.0


def test_breach_undefined_without_prior_vix():
    cal = _cal([100.0, 90.0], [np.nan, 16.0])
    assert math.isnan(T.breach_down(cal)[1])


def test_breach_basis_adj_vs_close():
    """An ex-dividend drop in the unadjusted close is not a total-return loss."""
    sig = 12.0 / 100 / math.sqrt(252)
    close = [100.0, 100.0 * math.exp(-2.2 * sig)]
    adj = [100.0, 100.0]
    cal = _cal(adj, [12.0, 12.0], close=close)
    assert T.breach_down(cal, basis="close")[1] == 1.0
    assert T.breach_down(cal, basis="adj")[1] == 0.0


def test_breach_up_and_fixed():
    sig = 20.0 / 100 / math.sqrt(252)
    cal = _cal([100.0, 100.0 * math.exp(2.1 * sig), 100.0 * math.exp(2.1 * sig) * 0.979], [20.0] * 3)
    assert T.breach_up(cal)[1] == 1.0 and T.breach_up(cal)[2] == 0.0
    f = T.breach_fixed(cal)
    assert f[1] == 0.0 and f[2] == 1.0           # -2.1% simple
    assert T.breach_fixed(_cal([100.0, 98.1], [20.0, 20.0]))[1] == 0.0


def test_breach_window_indexed_by_first_session():
    v = 20.0
    thr = 2.0 * v / 100 * math.sqrt(5 / 252)
    adj = [100.0] * 7
    adj[5] = 100.0 * math.exp(-thr - 0.001)      # window t=1..5 ends at index 5
    adj[6] = adj[5]
    cal = _cal(adj, [v] * 7)
    w = T.breach_window(cal)
    assert w[1] == 1.0
    assert w[2] == 1.0                           # index 1..6 path: adj[6]/adj[1]
    assert math.isnan(w[3])                      # t+4 past the data


def test_normal_rate():
    assert T.normal_rate(2.0) == pytest.approx(0.02275, abs=1e-5)
    assert T.normal_rate(0.0) == pytest.approx(0.5)


# ── Part 1 helpers ──────────────────────────────────────────────────────────

def test_episodes_chain_within_five_sessions():
    assert T.episodes([]) == 0
    assert T.episodes([10, 15, 21]) == 2         # 15 is 5 after 10; 21 is 6 after 15
    assert T.episodes([10, 11, 12, 100]) == 2


def test_cluster_share_and_independence():
    b = np.zeros(30)
    b[[5, 8, 20]] = 1.0
    near, k = T.cluster_share(b, list(range(30)))
    assert (near, k) == (1, 3)
    assert T.independent_share(0.1) == pytest.approx(1 - 0.9 ** 5)


def test_year_row_wilson():
    b = np.zeros(10)
    b[3] = 1.0
    r = T.year_row("x", b, list(range(10)))
    assert (r.n, r.k, r.episodes) == (10, 1, 1)
    assert r.lo < 0.1 < r.hi


# ── no lookahead ────────────────────────────────────────────────────────────

def test_predictors_ignore_every_later_close():
    cal = _random_cal(400)
    o = 320
    before = T.predictors_at(cal, o)
    assert before is not None
    cal.adj[o + 1:] *= 0.5
    cal.vix[o + 1:] = 80.0
    cal.vix3m[o + 1:] = 10.0
    assert T.predictors_at(cal, o) == before


def test_predictors_equal_on_truncated_series():
    cal = _random_cal(400)
    o = 300
    cut = T.Cal(cal.dates[:o + 1], cal.close[:o + 1], cal.adj[:o + 1], cal.vix[:o + 1],
                cal.vix3m[:o + 1])
    assert T.predictors_at(cal, o) == T.predictors_at(cut, o)


def test_predictors_values():
    cal = _random_cal(400)
    o = 300
    x = T.predictors_at(cal, o)
    assert x["X1"] == cal.vix[o]
    assert x["X3"] == pytest.approx(cal.vix[o] / cal.vix3m[o])
    win = cal.vix[o - 252:o]
    assert x["X2"] == pytest.approx((np.sum(win < cal.vix[o]) + 0.5 * np.sum(win == cal.vix[o])) / 252)
    r = np.log(cal.adj[o - 19:o + 1] / cal.adj[o - 20:o])
    assert x["X4"] == pytest.approx(math.sqrt(np.mean(r * r)) * math.sqrt(252) * 100 / cal.vix[o])


def test_predictors_need_full_windows():
    cal = _random_cal(400)
    assert T.predictors_at(cal, 251) is None
    cal.vix3m[300] = np.nan
    assert T.predictors_at(cal, 300) is None


def test_outcome_starts_after_origin():
    b = np.zeros(20)
    b[5] = 1.0
    assert T.outcome_any(b, 5) == 0.0            # origin's own session is not an outcome
    assert T.outcome_any(b, 4) == 1.0
    assert T.outcome_any(b, 0) == 1.0            # sessions 1..5
    assert T.outcome_any(b, 16) is None          # runs past the data
    assert T.outcome_next(b, 4) == 1.0 and T.outcome_next(b, 5) == 0.0


def test_split_keeps_outcome_windows_on_one_side():
    cal = _random_cal(1400, start="2019-06-03")
    preds = [T.predictors_at(cal, o) for o in range(cal.n)]
    b = np.zeros(cal.n)
    rows = T.build_rows(cal, "Y5", lambda o: T.outcome_any(b, o), 5, preds, registered=None)
    assert rows.drops["straddle"] == 4
    assert all(cal.dates[o + 5] < T.TEST_START for o, _, _ in rows.train)
    assert all(cal.dates[o + 1] >= T.TEST_START for o, _, _ in rows.test)
    assert not rows.fwd
    reg = cal.dates[1300]
    rows2 = T.build_rows(cal, "Y5", lambda o: T.outcome_any(b, o), 5, preds, registered=reg)
    assert all(cal.dates[o + 5] <= reg for o, _, _ in rows2.test)
    assert rows2.fwd and all(cal.dates[o] > reg for o, _, _ in rows2.fwd)
    # origins 1296..1300 end after reg but start on or before it: neither window
    assert rows2.drops["gap"] == 5
    tested = {o for o, _, _ in rows2.test}
    fwd = {o for o, _, _ in rows2.fwd}
    assert not tested & fwd
    assert max(tested) == 1295 and min(fwd) == 1301
    # the windows never share an outcome session
    assert max(o + 5 for o in tested) < min(o + 1 for o in fwd)
    assert len(rows2.test) + len(rows2.fwd) + rows2.drops["gap"] == len(rows.test)


def test_gx_check_passes_and_catches_lookahead(monkeypatch):
    cal = _random_cal(400)
    preds = [T.predictors_at(cal, o) for o in range(cal.n)]
    assert T.gx_check(cal, preds) > 0
    real = T.predictors_at

    def peeking(c, o):
        x = real(c, o)
        if x is not None and o + 1 < c.n:
            x = dict(x, X1=float(c.vix[o + 1]))
        return x

    monkeypatch.setattr(T, "predictors_at", peeking)
    bad = [T.predictors_at(cal, o) for o in range(cal.n)]
    with pytest.raises(T.LookaheadError):
        T.gx_check(cal, bad)


# ── model and metric ────────────────────────────────────────────────────────

def test_logit_recovers_coefficients():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(20_000, 2))
    y = (rng.random(20_000) < T._sigmoid(-2.0 + 1.0 * X[:, 0])).astype(float)
    beta, ok = T.fit_logit(X, y)
    assert ok
    assert beta[0] == pytest.approx(-2.0, abs=0.1)
    assert beta[1] == pytest.approx(1.0, abs=0.1)
    assert abs(beta[2]) < 0.1


def test_brier_skill():
    y = np.array([0, 0, 0, 1.0])
    assert T.brier_skill(np.full(4, 0.25), y, 0.25) == pytest.approx(0.0)
    assert T.brier_skill(y.copy(), y, 0.25) == pytest.approx(1.0)
    assert T.brier_skill(np.full(4, 0.9), y, 0.25) < 0


def test_block_indices_are_runs():
    idx = T.block_indices(50, 10, 5, 1)
    assert idx.shape == (5, 50)
    assert idx.min() >= 0 and idx.max() <= 49
    for row in idx:
        for s in range(0, 50, 10):
            assert np.all(np.diff(row[s:s + 10]) == 1)


def test_auc():
    assert T.auc(np.array([0.1, 0.2, 0.8, 0.9]), np.array([0, 0, 1, 1.0])) == 1.0
    assert T.auc(np.array([0.5, 0.5]), np.array([0, 1.0])) == 0.5


# ── verdict words ───────────────────────────────────────────────────────────

def _res(lo, hi, point=None):
    return T.Result(point if point is not None else (lo + hi) / 2, lo, hi, 0.01, 700, 30)


def test_word_rules():
    assert T.word(_res(0.01, 0.2), True) == T.PREDICTABLE
    assert T.word(_res(-0.01, 0.2), True) == T.NO_FORECAST
    assert T.word(_res(-0.3, -0.1), True) == T.NO_FORECAST     # worse than climatology
    assert T.word(_res(0.01, 0.2), False) == T.UNDERPOWERED
    assert T.word(_res(float("nan"), float("nan")), True) == T.UNDERPOWERED
    assert T.word(_res(0.01, 0.2), True, p_adj=0.06) == T.NO_FORECAST
    assert T.word(_res(0.01, 0.2), True, p_adj=0.04) == T.PREDICTABLE


def test_forward_word():
    assert T.forward_word(None, False) == T.STILL_OPEN
    assert T.forward_word(_res(0.01, 0.2), False) == T.STILL_OPEN
    assert T.forward_word(_res(0.01, 0.2), True) == T.PREDICTABLE
    assert T.forward_word(_res(-0.1, 0.2), True) == T.NO_FORECAST


def test_verdict_on_synthetic_signal_and_noise():
    """A predictor that drives the breach chance earns PREDICTABLE; noise does not."""
    rng = np.random.default_rng(7)
    n_tr, n_te = 4000, 800
    x_tr, x_te = rng.normal(size=n_tr), rng.normal(size=n_te)
    p = lambda x: T._sigmoid(-3.0 + 1.5 * x)
    y_tr = (rng.random(n_tr) < p(x_tr)).astype(float)
    y_te = (rng.random(n_te) < p(x_te)).astype(float)
    pad = lambda x: np.column_stack([x, rng.normal(size=(len(x), 3))])
    m = T.fit_model(T.PREDICTORS, pad(x_tr), y_tr)
    idx = T.block_indices(n_te, T.BLOCK, 2000, 1)
    res = T.score(m.prob(pad(x_te)), y_te, m.clim, idx)
    assert T.word(res, True) == T.PREDICTABLE
    noise = T.fit_model(("X2",), pad(x_tr), y_tr)
    res_n = T.score(noise.prob(pad(x_te)), y_te, noise.clim, idx)
    assert T.word(res_n, True) == T.NO_FORECAST


# ── gates ───────────────────────────────────────────────────────────────────

def test_ratio_check_flags_split_and_accepts_dividends():
    ok = [("2020-01-02", 100.0, 99.0), ("2020-01-03", 101.0, 100.0), ("2020-01-06", 100.0, 99.4)]
    assert T.ratio_problems(ok) == []
    split = ok + [("2020-01-07", 50.0, 99.4)]
    assert T.ratio_problems(split)


def test_era_refusal(monkeypatch):
    monkeypatch.setenv("STUDY_ERA", "v3")
    with pytest.raises(T.Refused) as exc:
        T.check_era()
    assert exc.value.code == 2


def test_registered_date_stamped():
    assert T.REGISTERED == "2026-11-14"


def test_base_rate_missing_column_refuses(tmp_path):
    f = tmp_path / "base.csv"
    f.write_text("date,spy_close\n2020-01-02,100\n")
    with pytest.raises(T.Refused) as exc:
        T.base_rate_problems([("2020-01-02", 100.0, 99.0)], {"2020-01-02": 15.0}, f)
    assert exc.value.code == 3
