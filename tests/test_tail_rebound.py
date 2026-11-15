"""tail_rebound — research/pre-registrations/f1_selection/regime/tail_rebound.md.

Synthetic data only: the completed-fall trigger and its lookahead, episode and
cluster construction, the windows, the excess and its cluster bootstrap, the
verdict words and Holm with a gated arm. Event A is `tail_breach_intraday`'s
and is tested in tests/test_tail_breach_intraday.py.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.backtest_study.f1_selection.regime import tail_rebound as M
from tests.test_tail_breach_intraday import _ical, _random_ical


def _flat(n=12, **kw):
    return _ical([100.0] * n, [16.0] * n, **kw)


# ── event B trigger ─────────────────────────────────────────────────────────

def test_completed_fall_reads_the_max_of_five_prior_closes():
    adj = [100, 104, 101, 100, 99, 98, 97, 97]
    low = list(adj)
    low[5] = 0.95 * 104 - 0.01           # 5% below the max (104), not the last close (99)
    low[6] = 0.95 * 104 + 0.5            # only 4.5% below the max
    b = M.completed_fall(_ical(adj, [16.0] * 8, low=low))
    assert all(math.isnan(x) for x in b[:5])
    assert b[5] == 1.0 and b[6] == 0.0
    low[7] = 0.95 * 101                  # max of sessions 2..6 is 101; inclusive
    assert M.completed_fall(_ical(adj, [16.0] * 8, low=low))[7] == 1.0


def test_completed_fall_undefined_on_missing_input():
    adj = [100.0] * 8
    low = [100.0] * 8
    low[6] = float("nan")
    b = M.completed_fall(_ical(adj, [16.0] * 8, low=low))
    assert math.isnan(b[6]) and b[7] == 0.0


def test_completed_fall_is_where_tail_breach_intraday_b_is_realized():
    cal = _random_ical(n=600, seed=7)
    cal.low_raw = cal.low_raw * (1 - 0.04 * (np.arange(cal.n) % 37 == 0))  # some deep lows
    b, lo = M.completed_fall(cal), cal.low("adj")
    for s in range(5, cal.n):
        want = any(lo[s] <= 0.95 * cal.adj[t - 1] for t in range(s - 4, s + 1))
        assert (b[s] == 1.0) == want
    w = M.TI.window_move(cal, side="down")
    for t in range(1, cal.n - 5):
        if w[t] == 1.0:
            assert any(b[s] == 1.0 for s in range(max(t, 5), t + 5))
    assert np.nansum(b) > 0


@pytest.mark.parametrize("trigger", [M.completed_fall, M.intraday_breach])
def test_no_lookahead_in_either_trigger(trigger):
    """GX: cutting the series at s, or changing every later session, leaves s alone."""
    cal = _random_ical(n=300, seed=3)
    full = trigger(cal)
    rng = np.random.default_rng(9)
    for s in (5, 40, 150, 299):
        cut = _ical(cal.adj[:s + 1], cal.vix[:s + 1], low=cal.low_raw[:s + 1],
                    high=cal.high_raw[:s + 1], close=cal.close[:s + 1])
        assert np.array_equal(trigger(cut)[:s + 1], full[:s + 1], equal_nan=True)
        later = slice(s + 1, None)
        adj, low, vix = cal.adj.copy(), cal.low_raw.copy(), cal.vix.copy()
        adj[later] *= rng.uniform(0.5, 1.5, len(adj[later]))
        low[later] *= rng.uniform(0.5, 1.0, len(low[later]))
        vix[later] = rng.uniform(5, 80, len(vix[later]))
        changed = _ical(adj, vix, low=low, high=cal.high_raw, close=cal.close)
        assert np.array_equal(trigger(changed)[:s + 1], full[:s + 1], equal_nan=True)


# ── episodes and clusters ───────────────────────────────────────────────────

def test_first_entries_chain_within_five_sessions():
    t = np.zeros(60)
    for i in (10, 12, 15, 21, 30, 35, 41):
        t[i] = 1.0
    t[3] = np.nan
    assert M.trigger_sessions(t) == [10, 12, 15, 21, 30, 35, 41]
    # 15 -> 21 is 6 apart: new episode. 30 -> 35 is exactly 5: chained. 35 -> 41: new.
    assert M.first_entries(t) == [10, 21, 30, 41]


def test_episode_chains_on_every_trigger_not_the_first():
    t = np.zeros(40)
    for i in (0, 4, 8, 12):                  # each within 5 of the one before, 12 from the first
        t[i] = 1.0
    assert M.first_entries(t) == [0]


def test_first_entries_match_tail_breach_episode_count():
    cal = _random_ical(n=800, seed=11)
    for t in (M.intraday_breach(cal, 1.0), M.completed_fall(cal, move=0.02)):
        assert len(M.first_entries(t)) == M.T.episodes(M.trigger_sessions(t))
        assert len(M.first_entries(t)) > 3


def test_clusters_join_only_when_windows_overlap():
    # 31 - 10 = 21: windows (10, 31] and (31, 52] do not overlap, so a new cluster
    assert M.clusters([10, 30, 51, 200], 21) == [[10, 30], [51], [200]]
    assert M.clusters([10, 31, 53], 63) == [[10, 31, 53]]
    assert M.clusters([10, 31], 21) == [[10], [31]]
    assert M.clusters([], 21) == []


# ── outcomes ────────────────────────────────────────────────────────────────

def test_log_return_and_open_and_excursions():
    adj = [100, 110, 99, 121, 100]
    cal = _ical(adj, [16.0] * 5, low=[100, 105, 90, 120, 95], high=[100, 115, 100, 130, 101])
    r = M.log_return(cal, 2)
    assert r[0] == pytest.approx(math.log(99 / 100)) and r[2] == pytest.approx(math.log(100 / 99))
    assert math.isnan(r[3]) and math.isnan(r[4])
    o = M.open_return(cal, np.array([100, 108, 98, 120, 101], float), 2)
    assert o[0] == pytest.approx(math.log(99 / 108))
    mae, mfe = M.excursions(cal, 2)
    assert mae[0] == pytest.approx(math.log(90 / 100))   # lows of sessions 1..2
    assert mfe[0] == pytest.approx(math.log(115 / 100))
    assert mae[2] == pytest.approx(math.log(95 / 99)) and math.isnan(mae[3])


def test_dividend_factor_scales_the_low():
    """Total-return low: an ex-dividend raw drop alone does not trigger B."""
    adj = [100.0] * 8
    close = [102.0] * 5 + [100.0] * 3        # raw close drops 2 on the ex-date; adj flat
    low = [102.0] * 5 + [96.0, 100.0, 100.0]
    cal = _ical(adj, [16.0] * 8, low=low, close=close)
    assert M.completed_fall(cal)[5] == 0.0    # 96/100 x 100 = 96 > 95


# ── windows ─────────────────────────────────────────────────────────────────

def test_window_of_sample_gap_forward_open():
    cal = _flat(n=30)                          # dates from 2005-01-03, business days
    reg = cal.dates[20]
    assert M.window_of(cal, 5, 5, reg) == "sample"
    assert M.window_of(cal, 15, 5, reg) == "sample"
    assert M.window_of(cal, 16, 5, reg) == "gap"
    assert M.window_of(cal, 21, 5, reg) == "forward"
    assert M.window_of(cal, 26, 5, reg) == "open"
    assert M.window_of(cal, 26, 5, None) == "open"
    assert M.window_of(cal, 20, 5, None) == "sample"


def test_build_arm_census_and_pool():
    n = 80
    cal = _ical(list(100 * np.exp(np.linspace(0, 0.1, n))), [16.0] * n)
    t = np.zeros(n)
    t[:2] = np.nan
    for i in (10, 40, 77):
        t[i] = 1.0
    a = M.build_arm("X5", cal, t, 5, None)
    assert a.entries == [10, 40, 77]
    assert a.census == {"sample": 2, "forward": 0, "gap": 0, "open": 1}
    assert a.sample == [10, 40]
    assert int(a.pool.sum()) == n - 2 - 5      # trigger defined and R_5 defined
    assert a.res.n_clusters == 2


# ── statistic and bootstrap ─────────────────────────────────────────────────

def test_excess_point_and_cluster_bootstrap():
    vals = np.zeros(200)
    pool = np.ones(200, bool)
    entries = [10, 12, 100, 150]               # h = 5: clusters [10, 12], [100], [150]
    vals[entries] = [0.10, 0.06, 0.02, 0.04]
    r = M.excess_ci(vals, entries, pool, 5, draws=2_000)
    assert r.n_entries == 4 and r.n_clusters == 3
    assert r.mean_entry == pytest.approx(0.055)
    assert r.uncond == pytest.approx(0.22 / 200)
    assert r.excess == pytest.approx(0.055 - 0.0011)
    assert r.lo > 0 and r.p == 0.0
    # a draw can only hold whole clusters: the 0.10/0.06 pair never splits, so no draw
    # mean exceeds 0.08 - uncond
    assert r.hi <= 0.08 - r.uncond + 1e-12


def test_excess_constant_values_give_zero_and_p_one():
    vals = np.full(100, 0.01)
    r = M.excess_ci(vals, [5, 50], np.ones(100, bool), 5, draws=500)
    assert r.excess == pytest.approx(0.0, abs=1e-12)


def test_gn_concentration_rule():
    vals = np.zeros(2000)
    pool = np.ones(2000, bool)
    spread = list(range(0, 1200, 100))                      # 12 one-entry clusters
    assert M.excess_ci(vals, spread, pool, 21, draws=100).powered
    lumped = spread + [1110, 1120, 1130, 1140, 1150, 1160]  # 1100 + six: 7 of 18 entries
    r = M.excess_ci(vals, lumped, pool, 21, draws=100)
    assert r.n_clusters == 12 and r.largest == 7
    assert r.largest_share > 1 / 3 and not r.powered
    few = list(range(0, 900, 100))                           # 9 clusters
    assert not M.excess_ci(vals, few, pool, 21, draws=100).powered


def test_excess_no_entries():
    r = M.excess_ci(np.zeros(10), [], np.ones(10, bool), 5)
    assert r.n_entries == 0 and not r.finite


# ── verdicts and Holm ───────────────────────────────────────────────────────

def _res(lo, hi, p=0.001, n=20):
    return M.Result(n, n, 0.0, 0.0, (lo + hi) / 2, lo, hi, p)


def test_words():
    assert M.word(_res(0.01, 0.03), True, 0.01) == M.REBOUND
    assert M.word(_res(-0.03, -0.01), True, 0.01) == M.CONTINUATION
    assert M.word(_res(0.01, 0.03), True, 0.06) == M.NO_EDGE      # Holm p fails
    assert M.word(_res(-0.01, 0.03), True, 0.01) == M.NO_EDGE
    assert M.word(_res(0.01, 0.03), False, 0.01) == M.UNDERPOWERED
    assert M.word(_res(float("nan"), 0.03), True, 0.01) == M.UNDERPOWERED
    assert M.word(_res(0.01, 0.03), True) == M.REBOUND             # no Holm step
    assert M.forward_word(None, False) == M.STILL_OPEN
    assert M.forward_word(_res(0.01, 0.03), True) == M.REBOUND


def test_holm_gated_arm_keeps_family_size():
    res = {"A21": _res(0.01, 0.03, p=0.02), "B21": _res(0.01, 0.03, p=0.0)}
    adj = M.family_p(res, {"A21": True, "B21": False})
    assert adj["A21"] == pytest.approx(0.04)   # m stays 2: 2 x 0.02
    assert adj["B21"] == 1.0                   # gated: enters with p = 1
    four = {k: _res(0.01, 0.03, p=0.02) for k in ("A5", "A63", "B5", "B63")}
    adj4 = M.family_p(four, {"A5": True, "A63": False, "B5": False, "B63": False})
    assert adj4["A5"] == pytest.approx(0.08)   # m stays 4
    assert M.word(four["A5"], True, adj4["A5"]) == M.NO_EDGE


def test_holm_both_powered():
    res = {"A21": _res(0.01, 0.03, p=0.01), "B21": _res(0.01, 0.03, p=0.03)}
    adj = M.family_p(res, {"A21": True, "B21": True})
    assert adj["A21"] == pytest.approx(0.02) and adj["B21"] == pytest.approx(0.03)


def test_era_refuses(monkeypatch):
    monkeypatch.setattr(M.era_mod, "requested_era", lambda: "v3")
    with pytest.raises(M.Refused) as e:
        M.check_era()
    assert e.value.code == 2
