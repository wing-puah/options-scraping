"""index_bear_hedge — the registered constants, the episode rules, the curve
arithmetic and the forward verdict grammar.

research/pre-registrations/f5_hedging/index_bear_hedge.md (accepted by default
2026-10-09, OD4 forward only). Every fixture is synthetic except the one
episode-census test, which reads the SPY/VIX market file when it is present
and reads no book column.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from scripts.backtest_study.f5_hedging import index_bear_hedge as IB


# ── registered constants ────────────────────────────────────────────────────

def test_registered_constants():
    assert IB.ACCEPTED == "2026-10-09"
    assert IB.SUNSET == "2029-10-09"
    assert (IB.FLOOR, IB.EARLY_FLOOR, IB.MIN_EP_SLEEVE, IB.MIN_EP_SESSIONS) == (5, 2, 3, 5)
    assert IB.OPEN_MAX == 0.25 and IB.MIN_SHIFT == 21 and IB.TOP_K == 3
    assert IB.EPISODE_DEFS["E-DD5"] == {
        "kind": "drawdown", "lookback": 63, "trigger": -0.05, "recover": -0.02,
        "trough_max": 42}
    assert IB.EPISODE_DEFS["_common"]["merge_gap"] == 10
    assert IB.EPISODE_DEFS["_common"]["buffer"] == 10


def test_g_hash_passes_and_moves_with_any_definition():
    assert IB.gate_hash() == []
    changed = {**IB.EPISODE_DEFS, "E-DD5": {**IB.EPISODE_DEFS["E-DD5"], "trigger": -0.06}}
    assert IB.episode_defs_hash(changed) != IB.EPISODE_DEFS_SHA256


# ── episodes ────────────────────────────────────────────────────────────────

def _series(closes, vix=None, start=date(2024, 1, 1)):
    days, d = [], start
    while len(days) < len(closes):
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    return IB.Series(days, list(closes), list(vix) if vix else [None] * len(closes))


def _dip(depth, n_down=5, n_up=5, base=100.0):
    down = [base * (1 - depth * (k + 1) / n_down) for k in range(n_down)]
    up = [base * (1 - depth) + (base - base * (1 - depth)) * (k + 1) / n_up
          for k in range(n_up)]
    return down + up


def test_drawdown_episode_peak_trough_and_buffer():
    closes = [100.0] * 70 + _dip(0.08) + [100.0] * 30
    s = _series(closes)
    eps = IB.episodes(s, "E-DD5")
    assert len(eps) == 1
    e = eps[0]
    assert e.peak_i == 69                  # ties on the 63-day high go to the latest date
    assert e.trough_i == 74                # the lowest close
    assert e.closed and e.buffer_end == s.dates[74 + 10]
    assert e.spy_move == pytest.approx(-0.08)
    deep = _series([100.0] * 70 + _dip(0.09) + [100.0] * 30)
    assert IB.episodes(deep, "E-DD8") != [] and IB.episodes(s, "E-DD8") == []
    shallow = _series([100.0] * 70 + _dip(0.04) + [100.0] * 30)
    assert IB.episodes(shallow, "E-DD5") == []


def test_drawdown_undefined_before_full_lookback():
    s = _series(_dip(0.10) + [100.0] * 80)
    assert IB.drawdowns(s.spy, 63)[61] is None
    assert IB.episodes(s, "E-DD5") == []


def test_close_episodes_merge_and_keep_the_lowest_close():
    closes = [100.0] * 70 + _dip(0.06) + [100.0] * 3 + _dip(0.09) + [100.0] * 30
    s = _series(closes)
    eps = IB.episodes(s, "E-DD5")
    assert len(eps) == 1
    assert eps[0].peak_i == 69
    assert s.spy[eps[0].trough_i] == pytest.approx(91.0)


def test_unclosed_episode_is_flagged():
    s = _series([100.0] * 70 + [99.0, 97.0, 94.0, 93.0])
    eps = IB.episodes(s, "E-DD5")
    assert len(eps) == 1 and not eps[0].closed and eps[0].buffer_end is None


def test_vix_episode_extends_back_over_the_20_stretch():
    vix = [15.0] * 10 + [21.0] * 3 + [26.0] * 2 + [15.0] * 20
    s = _series([100.0] * len(vix), vix)
    eps = IB.episodes(s, "E-VIX25")
    assert [(e.peak_i, e.trough_i) for e in eps] == [(10, 14)]


def test_return20_union_of_spans():
    closes = [100.0] * 30 + [94.0] + [100.0] * 30
    s = _series(closes)
    eps = IB.episodes(s, "E-20D5")
    assert len(eps) == 1 and (eps[0].peak_i, eps[0].trough_i) == (10, 30)


@pytest.mark.skipif(not IB.SPY_VIX_CSV.exists(), reason="market file is gitignored")
def test_market_file_reproduces_the_plan_time_census():
    s = IB.load_series()
    eps = [e for e in IB.episodes(s, "E-DD5") if e.peak < "2026-09-01"]
    assert [(e.peak, e.trough) for e in eps] == [
        ("2023-07-31", "2023-10-27"), ("2024-03-27", "2024-04-19"),
        ("2024-07-16", "2024-08-05"), ("2025-02-19", "2025-04-08"),
        ("2025-10-29", "2025-11-20"), ("2026-01-27", "2026-03-30")]


# ── session labels ──────────────────────────────────────────────────────────

def test_classify_window_buffer_outside_unclassified():
    closes = [100.0] * 70 + _dip(0.08) + [100.0] * 30
    s = _series(closes)
    eps = IB.episodes(s, "E-DD5")
    axis = [date.fromisoformat(d) for d in s.dates] + [date(2030, 1, 1)]
    lab = IB.classify(axis, eps, s)
    assert lab[0] == "unclassified"        # dd not defined yet
    assert lab[66] == "outside"
    assert lab[69] == "window" and lab[74] == "window"
    assert lab[75] == "buffer" and lab[84] == "buffer"
    assert lab[85] == "outside"
    assert lab[-1] == "unclassified"       # past the file


# ── curve arithmetic ────────────────────────────────────────────────────────

def test_window_dd_and_gain():
    daily = [0.0, 10.0, -30.0, 5.0, -10.0, 40.0]
    assert IB.window_dd(daily, [0, 1, 2, 3, 4]) == pytest.approx(-35.0)
    assert IB.window_gain(daily, [1, 2, 3]) == pytest.approx(-25.0)
    assert IB.window_dd(daily, [4, 5, 0, 1]) == pytest.approx(0.0)  # wrapped window
    assert IB.window_dd(daily, []) != IB.window_dd(daily, [])        # nan


def test_on_axis_carries_forward_and_sums_scaled_parts():
    d = [date(2025, 1, k) for k in range(1, 8)]
    cs = IB.CurveSet(parts=[([d[1], d[2]], [0.5, 1.0]), ([d[3]], [2.0])])
    assert IB.on_axis(cs, d) == [0.0, 0.5, 1.0, 3.0, 3.0, 3.0, 3.0]
    assert IB.to_daily([0.0, 0.5, 1.0, 3.0]) == [0.0, 0.5, 0.5, 2.0]


def test_unit_weights_one_unit_per_date():
    rows = [{"date": "2025-01-02"}, {"date": "2025-01-02"}, {"date": "2025-01-03"}]
    w = IB.unit_weights(rows)
    assert [w[id(r)] for r in rows] == [0.5, 0.5, 1.0]


def test_permutation_p_small_when_sleeve_pays_only_in_the_window():
    n = 120
    axis = [date(2025, 1, 1) + timedelta(days=k) for k in range(n)]
    b = [0.0] * n
    s = [0.0] * n
    for k in range(50, 60):
        b[k] = -10.0
        s[k] = 8.0
    e = IB.Episode("E-DD5", axis[50].isoformat(), axis[59].isoformat(), 50, 59, True)
    p, n_shift, t0 = IB.permutation_p(axis, b, s, [e])
    assert t0 > 0 and n_shift == n - 2 * IB.MIN_SHIFT + 1
    assert p == pytest.approx(1 / (1 + n_shift))


# ── the book split ─────────────────────────────────────────────────────────

def _rec(date_, ticker, structure, tier="A", score=1.0):
    return {"date": date_, "ticker": ticker, "structure": structure, "tier": tier,
            "score_total": score, "post13c": True}


def test_index_bear_and_stock_bear_membership():
    assert IB.is_index_bear(_rec("d", "SPY", "bear_put_spread"))
    assert not IB.is_index_bear(_rec("d", "SPY", "bull_call_spread"))
    assert not IB.is_index_bear(_rec("d", "SMH", "bear_put_spread"))   # G3, not G1
    assert IB.is_stock_bear(_rec("d", "NVDA", "bear_put_spread"))
    assert not IB.is_stock_bear(_rec("d", "IWM", "bear_put_spread"))


def test_deployed_drops_index_bears_without_backfill():
    day = "2025-03-03"
    recs = [_rec(day, "SPY", "bear_put_spread", score=9),
            _rec(day, "AAPL", "bull_call_spread", score=8),
            _rec(day, "MSFT", "bull_call_spread", score=7),
            _rec(day, "AMZN", "bull_call_spread", score=6)]
    picked = IB.deployed(recs)
    assert [r["ticker"] for r in picked] == ["AAPL", "MSFT"]


# ── the seal ────────────────────────────────────────────────────────────────

def test_seal_withholds_sealed_dates():
    rows = [{"date": "2026-09-22"}, {"date": "2026-09-23"}, {"date": "2026-10-20"}]
    kept, info = IB._apply_seal(rows)
    assert [r["date"] for r in kept] == ["2026-09-22"]
    assert info["rows"] == 2


# ── the forward verdict grammar (OD4) ──────────────────────────────────────

def test_verdict_below_floor_is_still_open_then_underpowered():
    assert IB.verdict(4, [1.0] * 4, 0.01, 10.0, True, True, False) == "STILL-OPEN"
    assert IB.verdict(4, [1.0] * 4, 0.01, 10.0, True, True, False,
                      before_sunset=False) == "UNDERPOWERED"


def test_verdict_rows_in_order():
    pos = [1.0] * 5
    assert IB.verdict(5, pos, 0.01, 10.0, True, True, False) == "EARNS ITS KEEP"
    assert IB.verdict(5, pos, 0.01, 10.0, True, True, True) == (
        "EARNS ITS KEEP — bear protection, not index-specific")
    assert IB.verdict(5, pos, 0.01, -1.0, True, True, False) == (
        "PROTECTS, COSTS MORE THAN IT SAVES")
    assert IB.verdict(5, [1, 1, 1, 1, -1.0], 0.2, 0.0, False, True, False) == (
        "PROTECTS, COSTS MORE THAN IT SAVES")
    assert IB.verdict(5, [1, 1, 1, -1.0, -1.0], 0.2, 5.0, False, True, False) == (
        "DOES NOT PROTECT")
    assert IB.verdict(5, [1, 1, 1, 1, -1.0], 0.2, 5.0, True, True, False) == "INDETERMINATE"
    # p above alpha blocks EARNS ITS KEEP even when everything else holds
    assert IB.verdict(5, pos, 0.2, 10.0, True, True, False) == "INDETERMINATE"


def test_early_read():
    assert IB.early_read([1.0], -1.0, -5.0) == "STILL-OPEN"
    assert IB.early_read([1.0, 2.0], -1.0, -5.0) == "PROTECTING"
    assert IB.early_read([1.0, 2.0], -9.0, -5.0) == "PROTECTS, CARRY TOO HIGH"
    assert IB.early_read([1.0, -2.0], -1.0, -5.0) == "NOT PROTECTING"
    assert IB.early_read([1.0, 2.0], -1.0, None) == "STILL-OPEN"


def test_forward_read_is_still_open_under_the_seal(monkeypatch, capsys):
    monkeypatch.setattr(IB, "seal_lifted", lambda: False)
    s = _series([100.0] * 5)
    ctx = IB.Context(axis=[], daily={}, all_eps={}, s=s, sleeve=[], book=[],
                     sleeve_real=[], book_real=[])
    fwd = [IB.Episode("E-DD5", "2026-11-02", "2026-11-20", 0, 1, True, "2026-12-04")]
    head, early = IB.forward_read(ctx, fwd, ins=None, today="2027-01-01")
    assert (head, early) == ("STILL-OPEN", "STILL-OPEN")
    out = capsys.readouterr().out
    assert "0 forward episodes graded" in out and "seal" in out
    head, _ = IB.forward_read(ctx, fwd, ins=None, today="2029-10-09")
    assert head == "UNDERPOWERED"
