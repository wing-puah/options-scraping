"""tail_breach_intraday — research/pre-registrations/f1_selection/regime/tail_breach_intraday.md.

Synthetic data only: the intraday event definitions and their price basis, the
5% window event, no lookahead, the OHLC gates and the co-primary Holm step. The
predictors, split, model and metric are `tail_breach`'s and are tested in
tests/test_tail_breach.py.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.backtest_study.f1_selection.regime import tail_breach_intraday as M
from tests.test_tail_breach import _dates


def _ical(adj, vix, low=None, high=None, close=None, vix3m=None, start="2005-01-03") -> M.ICal:
    adj = np.asarray(adj, float)
    n = len(adj)
    close = np.asarray(close if close is not None else adj, float)
    return M.ICal(dates=_dates(n, start), close=close, adj=adj, vix=np.asarray(vix, float),
                  vix3m=np.asarray(vix3m if vix3m is not None else vix, float),
                  high_raw=np.asarray(high if high is not None else close, float),
                  low_raw=np.asarray(low if low is not None else close, float))


def _random_ical(n=400, seed=1, start="2005-01-03") -> M.ICal:
    rng = np.random.default_rng(seed)
    adj = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    vix = 15 + 5 * rng.random(n)
    low = adj * (1 - 0.02 * rng.random(n))
    high = adj * (1 + 0.02 * rng.random(n))
    return _ical(adj, vix, low=low, high=high, vix3m=vix * 1.1, start=start)


SIG16 = 16.0 / 100 / math.sqrt(252)


# ── event A ─────────────────────────────────────────────────────────────────

def test_intraday_down_reads_the_low_not_the_close():
    """The close is flat; the low alone breaches."""
    adj = [100.0, 100.0, 100.0]
    low = [100.0, 100.0 * math.exp(-2.01 * SIG16), 100.0 * math.exp(-1.99 * SIG16)]
    cal = _ical(adj, [16.0, 16.0, 16.0], low=low)
    a = M.intraday_down(cal, 2.0)
    assert math.isnan(a[0])
    assert a[1] == 1.0 and a[2] == 0.0
    assert M.intraday_down(cal, 1.5)[2] == 1.0
    assert M.T.breach_down(cal)[1] == 0.0        # the close-basis event does not fire


def test_intraday_down_uses_prior_vix_only():
    adj, low = [100.0, 100.0], [100.0, 100.0 * math.exp(-2.5 * SIG16)]
    assert M.intraday_down(_ical(adj, [16.0, 10.0], low=low))[1] == 1.0
    assert M.intraday_down(_ical(adj, [16.0, 80.0], low=low))[1] == 1.0
    assert M.intraday_down(_ical(adj, [40.0, 16.0], low=low))[1] == 0.0
    assert math.isnan(M.intraday_down(_ical(adj, [np.nan, 16.0], low=low))[1])


def test_intraday_down_is_strict():
    adj, low = [100.0, 100.0], [100.0, 100.0 * math.exp(-2.0 * SIG16)]
    cal = _ical(adj, [16.0, 16.0], low=low)
    cal.low_raw[1] = 100.0 * math.exp(-2.0 * SIG16) * (1 + 1e-12)
    assert M.intraday_down(cal)[1] == 0.0


def test_ex_dividend_drop_is_not_a_fall_on_the_adjusted_basis():
    """Raw close drops by a 2% dividend; the total-return price does not move.
    The raw low equals the raw close, so a holder lost nothing."""
    close = [100.0, 98.0]
    adj = [98.0, 98.0]                           # adj = close x factor; factor 0.98 then 1.0
    low = [99.5, 98.0]
    cal = _ical(adj, [12.0, 12.0], low=low, close=close)
    assert M.intraday_down(cal, basis="raw")[1] == 1.0     # 2% raw drop > 2 x 0.76%
    assert M.intraday_down(cal, basis="adj")[1] == 0.0
    assert cal.low("adj")[1] == pytest.approx(98.0)
    assert cal.low("adj")[0] == pytest.approx(99.5 * 0.98)


# ── event B ─────────────────────────────────────────────────────────────────

def test_window_move_indexed_by_first_session_and_inclusive():
    adj = [100.0] * 10
    low = [100.0] * 10
    low[7] = 95.0                                # exactly 5% below every earlier close
    cal = _ical(adj, [20.0] * 10, low=low)
    b = M.window_move(cal)
    assert math.isnan(b[0])                      # no origin
    assert b[1] == 0.0 and b[2] == 0.0           # windows 1..5 and 2..6 miss session 7
    assert b[3] == 1.0 and b[5] == 1.0           # windows 3..7 and 5..9 hold it
    assert math.isnan(b[6])                      # window 6..10 runs past the data
    low[7] = 95.0001
    assert M.window_move(_ical(adj, [20.0] * 10, low=low))[3] == 0.0


def test_window_move_reads_origin_close_not_later_peak():
    adj = [100.0, 103.0, 103.0, 103.0, 103.0, 103.0, 103.0]
    low = [100.0, 103.0, 103.0, 96.0, 103.0, 103.0, 103.0]
    cal = _ical(adj, [20.0] * 7, low=low)
    b = M.window_move(cal)
    assert b[1] == 0.0                           # 96 vs origin 100: -4%
    assert b[2] == 1.0                           # origin 103: 96/103 = -6.8%


def test_window_move_variants():
    adj = [100.0, 100.0, 100.0, 95.5, 100.0, 100.0, 100.0]
    low = [100.0, 99.0, 99.0, 94.0, 99.0, 99.0, 99.0]
    high = [100.0, 101.0, 101.0, 101.0, 106.0, 101.0, 101.0]
    cal = _ical(adj, [20.0] * 7, low=low, high=high)
    assert M.window_move(cal)[1] == 1.0
    assert M.window_move(cal, basis="close")[1] == 0.0      # closes never 5% down
    assert M.window_move(cal, w=1)[3] == 1.0 and M.window_move(cal, w=1)[2] == 0.0
    assert M.window_move(cal, side="up")[1] == 1.0          # 106 on session 4
    assert M.window_move(cal, w=1, side="up")[4] == 1.0 and M.window_move(cal, w=1, side="up")[5] == 0.0
    e = M.window_move(cal, side="either")
    assert e[1] == 1.0
    with pytest.raises(ValueError):
        M.window_move(cal, side="sideways")


def test_window_move_uses_total_return_low():
    """An ex-dividend raw drop inside the window is not a 5% fall."""
    close = [100.0, 94.0, 94.0, 94.0, 94.0, 94.0]
    adj = [94.0, 94.0, 94.0, 94.0, 94.0, 94.0]   # a 6% "dividend" for the test
    cal = _ical(adj, [20.0] * 6, low=close, high=close, close=close)
    assert M.window_move(cal)[1] == 0.0


def test_reflection_rate_and_move_reference():
    assert M.reflection_rate(2.0) == pytest.approx(2 * 0.02275, abs=1e-5)
    assert M.reflection_rate(0.0) == 1.0
    cal = _ical([100.0] * 10, [20.0] * 10)
    idx = list(range(1, 6))
    dn = M.move_reference(cal, idx)
    s = 20.0 / 100 / math.sqrt(252) * math.sqrt(5)
    assert dn == pytest.approx(M.reflection_rate(-math.log(0.95) / s))
    assert M.move_reference(cal, idx, side="either") == pytest.approx(
        min(1.0, dn + M.move_reference(cal, idx, side="up")))
    assert M.move_reference(cal, idx, basis="close") < dn


# ── no lookahead ────────────────────────────────────────────────────────────

def test_predictors_and_earlier_events_ignore_every_later_price():
    cal = _random_ical(400)
    o = 320
    before = M.T.predictors_at(cal, o)
    a0, b0 = M.intraday_down(cal).copy(), M.window_move(cal).copy()
    assert before is not None
    cal.adj[o + 1:] *= 0.5
    cal.close[o + 1:] *= 0.5
    cal.low_raw[o + 1:] *= 0.3
    cal.high_raw[o + 1:] *= 2.0
    cal.vix[o + 1:] = 80.0
    cal.vix3m[o + 1:] = 10.0
    assert M.T.predictors_at(cal, o) == before
    a1, b1 = M.intraday_down(cal), M.window_move(cal)
    np.testing.assert_array_equal(a1[:o + 1], a0[:o + 1])
    # B at first session t reads t..t+4: the flags whose window ends by o are unchanged
    np.testing.assert_array_equal(b1[:o - 3], b0[:o - 3])


def test_predictors_never_read_high_or_low():
    cal = _random_ical(400)
    o = 300
    before = M.T.predictors_at(cal, o)
    cal.low_raw[:] = 1.0
    cal.high_raw[:] = 1e6
    assert M.T.predictors_at(cal, o) == before


def test_outcome_rows_start_after_origin():
    cal = _random_ical(1400, start="2019-06-03")
    preds = [M.T.predictors_at(cal, o) for o in range(cal.n)]
    b = np.zeros(cal.n)
    b[700] = 1.0
    yb = M.outcome_from_first(b)
    assert yb(699) == 1.0 and yb(700) == 0.0    # origin 699 -> first session 700
    reg = cal.dates[1300]
    ev = M.fit_event("YB", b, yb, 5, preds, cal, first_only=True, registered=reg)
    assert all(cal.dates[o + 5] <= reg for o, _, _ in ev.rows.test)
    assert all(cal.dates[o + 5] < M.TEST_START for o, _, _ in ev.rows.train)
    assert all(cal.dates[o] > reg for o, _, _ in ev.rows.fwd)
    assert max(o + 5 for o, _, _ in ev.rows.test) < min(o + 1 for o, _, _ in ev.rows.fwd)
    # h = 5 for YB: the last training origin's window ends before 2024-01-02
    assert ev.rows.drops["straddle"] == 4


def test_episodes_in_rows_first_session_vs_every_session():
    b = np.zeros(40)
    b[[10, 11, 12, 30]] = 1.0
    part = [(o, None, 0.0) for o in range(0, 34)]
    assert M.episodes_in_rows(b, part, 5, first_only=True) == 2
    assert M.episodes_in_rows(b, part, 5, first_only=False) == 2
    assert M.episodes_in_rows(b, [(9, None, 1.0)], 5, first_only=True) == 1
    assert M.episodes_in_rows(b, [(5, None, 1.0)], 5, first_only=True) == 0


# ── gates ───────────────────────────────────────────────────────────────────

def test_ohlc_problems():
    ok = [("2020-01-02", 100.0, 101.0, 99.0, 100.5, 99.0)]
    assert M.ohlc_problems(ok) == []
    assert M.ohlc_problems([("2020-01-02", 100.0, 101.0, 100.6, 100.5, 99.0)])   # low above close
    assert M.ohlc_problems([("2020-01-02", 100.0, 100.2, 99.0, 100.5, 99.0)])    # high below close
    assert M.ohlc_problems([("2020-01-02", 100.0, None, 99.0, 100.5, 99.0)])
    assert M.ohlc_problems([("2000-01-03", 100.0, None, 99.0, 100.5, 99.0)]) == []  # before 2006-07-17


def test_cross_feed_problems(tmp_path):
    f = tmp_path / "SPY.csv"
    f.write_text("Time,Open,High,Low,Latest\n2024-01-02,1,1,99.0,1\n2024-01-03,1,1,50.0,1\n")
    spy = [("2024-01-02", 1, 1, 99.1, 1, 1), ("2024-01-03", 1, 1, 99.0, 1, 1)]
    probs, n = M.cross_feed_problems(spy, f)
    assert n == 2 and len(probs) == 1 and probs[0].startswith("2024-01-03")
    assert M.cross_feed_problems(spy, tmp_path / "missing.csv") == ([], 0)


def test_read_ohlc_round_trip(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("date,open,high,low,close,adj_close\n2020-01-03,1,2,0.5,1.5,1.4\n"
                 "2020-01-02,1,,0.5,1.5,1.4\n2020-01-06,1,2,0.5,,1.4\n")
    rows = M.read_ohlc(f)
    assert [r[0] for r in rows] == ["2020-01-02", "2020-01-03"]
    assert rows[0][2] is None and rows[1][2] == 2.0


# ── verdict words ───────────────────────────────────────────────────────────

def _res(lo, hi, p):
    return M.T.Result((lo + hi) / 2, lo, hi, p, 700, 30)


def test_co_primaries_holm_m2():
    res = {"PA": _res(0.01, 0.2, 0.03), "PB": _res(-0.1, 0.2, 0.6)}
    graded, plain, adj = M.co_primary_words(res, {"PA": True, "PB": True})
    assert adj["PA"] == pytest.approx(0.06)
    assert plain["PA"] == M.PREDICTABLE and graded["PA"] == M.NO_FORECAST
    assert graded["PB"] == M.NO_FORECAST
    res["PA"] = _res(0.01, 0.2, 0.01)
    graded, _, _ = M.co_primary_words(res, {"PA": True, "PB": False})
    assert graded["PA"] == M.PREDICTABLE and graded["PB"] == M.UNDERPOWERED
    # a gated arm enters with p = 1: PA's adjusted p is still doubled
    assert M.co_primary_words({"PA": _res(0.01, 0.2, 0.03), "PB": _res(0.01, 0.2, 0.001)},
                              {"PA": True, "PB": False})[2]["PA"] == pytest.approx(0.06)


def test_era_refusal(monkeypatch):
    monkeypatch.setenv("STUDY_ERA", "v3")
    with pytest.raises(M.Refused) as exc:
        M.check_era()
    assert exc.value.code == 2


def test_registered_date_stamped():
    assert M.REGISTERED == "2026-11-14"
