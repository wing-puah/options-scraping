"""tail_rebound_etf — research/pre-registrations/f1_selection/regime/tail_rebound_etf.md.

Synthetic data only: the volatility source each calendar carries (VXN, VIX,
RV20), no lookahead in RV20 or in event A under it, the GB basis gate with
its annual-dividend allowance, the SPY-relative return, and the Holm m = 4
co-primary family with a gated arm. The triggers, episodes, clusters and the
bootstrap are tail_rebound's and are tested in tests/test_tail_rebound.py.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.backtest_study.f1_selection.regime import tail_rebound_etf as M
from tests.test_tail_breach_intraday import _dates, _ical, _random_ical


def _rows(close, adj=None, start="2005-01-03"):
    adj = adj if adj is not None else close
    return [(d, c, c * 1.01, c * 0.99, c, a) for d, c, a in zip(_dates(len(close), start), close, adj)]


# ── volatility selection ────────────────────────────────────────────────────

def test_etf_cal_puts_vxn_in_the_vix_slot():
    rows = _rows([100.0, 101.0, 102.0])
    d = [r[0] for r in rows]
    cal = M.etf_cal(rows, {d[0]: 30.0, d[2]: 25.0})
    assert cal.vix[0] == 30.0 and math.isnan(cal.vix[1]) and cal.vix[2] == 25.0
    s = M.T.implied_sigma(cal)
    assert s[1] == pytest.approx(30.0 / 100 / math.sqrt(252))
    assert math.isnan(s[2])          # VXN(s-1) missing -> event A undefined
    assert math.isnan(M.R.intraday_breach(cal)[2])


def test_vxn_and_vix_give_different_triggers():
    """A 3% intraday drop breaches 2 x VIX 16 but not 2 x VXN 40."""
    adj = [100.0] * 3
    low = [100.0, 97.0, 100.0]
    vxn = _ical(adj, [40.0] * 3, low=low)
    vix = M.with_vol(vxn, [16.0] * 3)
    assert M.R.intraday_breach(vxn)[1] == 0.0
    assert M.R.intraday_breach(vix)[1] == 1.0
    assert vxn.vix[0] == 40.0            # with_vol leaves the original alone


def test_rv20_is_the_sd_of_the_twenty_returns_before_s():
    cal = _random_ical(n=60, seed=5)
    v = M.rv20_points(cal)
    assert all(math.isnan(x) for x in v[:M.RV_WINDOW])
    lr = np.log(cal.adj[1:] / cal.adj[:-1])
    i = 40
    want = np.std(lr[i - 20:i], ddof=1) * math.sqrt(252) * 100
    assert v[i] == pytest.approx(want)
    # sigma on session s reads returns ending at closes s-20 .. s-1
    s_ = 41
    sig = M.T.implied_sigma(M.with_vol(cal, v))[s_]
    rets = [math.log(cal.adj[j] / cal.adj[j - 1]) for j in range(s_ - 20, s_)]
    assert sig == pytest.approx(np.std(rets, ddof=1))


def test_rv20_undefined_on_a_missing_close():
    cal = _random_ical(n=60, seed=6)
    cal.adj[30] = np.nan
    v = M.rv20_points(cal)
    assert all(math.isnan(v[i]) for i in range(30, 51))
    assert math.isfinite(v[51])


def test_no_lookahead_in_rv20_or_event_a_under_it():
    """GX: changing every session after s leaves RV20-sigma and event A at s alone."""
    cal = _random_ical(n=200, seed=3)
    full_sig = M.T.implied_sigma(M.with_vol(cal, M.rv20_points(cal)))
    full_a = M.R.intraday_breach(M.with_vol(cal, M.rv20_points(cal)))
    rng = np.random.default_rng(11)
    for s in (25, 80, 150, 199):
        adj, low = cal.adj.copy(), cal.low_raw.copy()
        later = slice(s + 1, None)
        adj[later] *= rng.uniform(0.5, 1.5, len(adj[later]))
        low[later] *= rng.uniform(0.3, 1.0, len(low[later]))
        changed = _ical(adj, cal.vix, low=low, high=cal.high_raw, close=cal.close)
        c2 = M.with_vol(changed, M.rv20_points(changed))
        assert np.array_equal(M.T.implied_sigma(c2)[:s + 1], full_sig[:s + 1], equal_nan=True)
        assert np.array_equal(M.R.intraday_breach(c2)[:s + 1], full_a[:s + 1], equal_nan=True)


def test_no_lookahead_on_a_series_cut_at_s():
    """GX: event A (VXN, VIX, RV20) and event B on a series cut at s match the full series."""
    cal = _random_ical(n=200, seed=12)
    cal.low_raw = cal.low_raw * (1 - 0.05 * (np.arange(cal.n) % 23 == 0))
    alt = 30 + 10 * np.random.default_rng(2).random(cal.n)

    def triggers(c, other):
        return [M.R.intraday_breach(c), M.R.intraday_breach(M.with_vol(c, other)),
                M.R.intraday_breach(M.with_vol(c, M.rv20_points(c))), M.R.completed_fall(c)]
    full = triggers(cal, alt)
    for s in (10, 30, 120, 199):
        cut = _ical(cal.adj[:s + 1], cal.vix[:s + 1], low=cal.low_raw[:s + 1],
                    high=cal.high_raw[:s + 1], close=cal.close[:s + 1])
        for f, c in zip(full, triggers(cut, alt[:s + 1])):
            assert np.array_equal(c, f[:s + 1], equal_nan=True)


def test_rv20_ignores_session_s_itself():
    """A crash in session s's close must not raise sigma_s."""
    cal = _random_ical(n=40, seed=8)
    base = M.T.implied_sigma(M.with_vol(cal, M.rv20_points(cal)))[30]
    cal.adj[30] *= 0.5
    assert M.T.implied_sigma(M.with_vol(cal, M.rv20_points(cal)))[30] == pytest.approx(base)


# ── GB basis gate ───────────────────────────────────────────────────────────

def test_gb_allows_an_annual_dividend_up_to_three_percent():
    close = [100.0] * 6
    adj = [100.0, 100.0, 100.0, 100.0 / 0.979, 100.0 / 0.979, 100.0 / 0.979]   # close/adj -2.1%
    assert M.gb_problems(_rows(close, adj)) == []
    assert M.ratio_steps(_rows(close, adj))           # beyond tail_breach's 2%: printed
    adj_big = [100.0, 100.0, 100.0, 100.0 / 0.96, 100.0 / 0.96, 100.0 / 0.96]  # -4%
    assert M.gb_problems(_rows(close, adj_big))


def test_gb_at_two_percent_matches_tail_breach_ratio_problems(monkeypatch):
    """GB re-implements tail_breach.ratio_problems with the limit as a parameter."""
    rng = np.random.default_rng(4)
    close = list(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300))))
    ratio = np.cumprod(np.where(rng.random(300) < 0.03, 1 - rng.uniform(0, 0.04, 300), 1.0))
    ratio[150] *= 1.001                               # one step up
    adj = list(np.array(close) / ratio)
    rows = _rows(close, adj)
    want = M.T.ratio_problems([(r[0], r[4], r[5]) for r in rows])
    monkeypatch.setattr(M, "GB_STEP_MAX", M.T.RATIO_STEP_MAX)
    got = M.gb_problems(rows)
    assert want and [g.split()[0] for g in got] == [w.split()[0] for w in want]


def test_gb_refuses_a_ratio_step_up_and_an_unadjusted_split():
    close = [100.0] * 4
    adj = [100.0, 100.0, 99.0, 99.0]                  # close/adj rises
    assert M.gb_problems(_rows(close, adj))
    split = [100.0, 100.0, 50.0, 50.0]
    assert any("raw close" in p for p in M.gb_problems(_rows(split, split)))


# ── SPY-relative return ─────────────────────────────────────────────────────

def test_spy_relative_is_etf_minus_spy_on_the_same_dates():
    adj = [100.0, 110.0, 121.0, 121.0]
    cal = _ical(adj, [20.0] * 4)
    spy = dict(zip(cal.dates, [200.0, 210.0, 220.0, 230.0]))
    d = M.spy_relative(cal, spy, 1)
    assert d[0] == pytest.approx(math.log(1.1) - math.log(210 / 200))
    assert math.isnan(d[3])
    del spy[cal.dates[2]]
    d = M.spy_relative(cal, spy, 1)
    assert math.isnan(d[1]) and math.isnan(d[2])     # no SPY match -> out of the pool


# ── Holm families ───────────────────────────────────────────────────────────

def _res(lo, hi, p, n_clusters=20, largest=1, n_entries=20):
    return M.R.Result(n_entries, n_clusters, 0.02, 0.0, 0.02, lo, hi, p, largest)


class _A:
    def __init__(self, res):
        self.res = res

    @property
    def powered(self):
        return self.res.powered


def test_holm_four_coprimaries_with_a_gated_arm():
    arms = {k: _A(_res(0.001, 0.03, p=0.01)) for k in M.PRIMARY_KEYS}
    arms["SMH-B21"] = _A(_res(0.001, 0.03, p=0.0, n_clusters=5))      # GN fails
    arms.update({k: _A(_res(-0.01, 0.01, p=0.5)) for k in M.SECONDARY_KEYS})
    words, plain, holm_p = M.grade(arms)
    assert len(M.PRIMARY_KEYS) == 4 and len(M.SECONDARY_KEYS) == 8
    # m stays 4: the three powered arms at p 0.01 adjust to 4 x, 3 x, 2 x -> max-cumulated 0.04, 0.04, 0.04
    for k in ("QQQ-A21", "QQQ-B21", "SMH-A21"):
        assert holm_p[k] == pytest.approx(0.04)
        assert words[k] == M.REBOUND
    assert holm_p["SMH-B21"] == 1.0
    assert words["SMH-B21"] == M.UNDERPOWERED
    assert all(words[k] == M.NO_EDGE for k in M.SECONDARY_KEYS)


def test_holm_family_of_four_can_strip_a_rebound():
    arms = {k: _A(_res(0.001, 0.03, p=0.02)) for k in M.PRIMARY_KEYS}
    arms["QQQ-B21"] = _A(_res(0.001, 0.03, p=0.0, n_clusters=3))      # gated, p = 1
    arms.update({k: _A(_res(-0.01, 0.01, p=0.5)) for k in M.SECONDARY_KEYS})
    words, plain, holm_p = M.grade(arms)
    assert holm_p["QQQ-A21"] == pytest.approx(0.08)                   # m stays 4: 4 x 0.02
    assert words["QQQ-A21"] == M.NO_EDGE and plain["QQQ-A21"] == M.REBOUND


def test_secondary_family_is_eight():
    arms = {k: _A(_res(-0.01, 0.01, p=0.5)) for k in M.PRIMARY_KEYS}
    arms.update({k: _A(_res(0.001, 0.03, p=0.006)) for k in M.SECONDARY_KEYS})
    _, _, holm_p = M.grade(arms)
    assert holm_p["QQQ-A5"] == pytest.approx(0.048)                   # 8 x 0.006, max-cumulated


def test_era_refuses(monkeypatch):
    monkeypatch.setattr(M.era_mod, "requested_era", lambda: "v3")
    with pytest.raises(M.Refused) as e:
        M.check_era()
    assert e.value.code == 2


def test_missing_cache_refuses(monkeypatch, tmp_path):
    monkeypatch.setattr(M, "CACHE_DIR", tmp_path)
    with pytest.raises(M.Refused) as e:
        M.load_inputs(refresh=False)
    assert e.value.code == 3 and "--refresh" in e.value.message
