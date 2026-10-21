"""Pure logic of `regime_confirm` on synthetic series: flips, streaks, decision
dates, the real-shift outcome, conditions, censoring and clustering."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.backtest_study.f1_selection.regime import regime_confirm as rc


def _series(name, closes, start="2020-01-01", adj=None):
    dates = pd.bdate_range(start, periods=len(closes)).strftime("%Y-%m-%d").tolist()
    adj = adj if adj is not None else closes
    return rc.series_from_rows(name, list(zip(dates, map(float, closes), map(float, adj))))


Q, B, R = "RANGE", "BEAR", "BULL"


# ── flips: the 20-quiet rule ──────────────────────────────────────────────────

def test_flip_needs_twenty_quiet_labelled_sessions():
    dirs = [R] * 20 + [B]
    assert rc.find_flips(dirs) == [20]
    assert rc.find_flips([R] * 19 + [B]) == []


def test_bear_inside_lookback_blocks_flip():
    dirs = [R] * 25 + [B] + [R] * 19 + [B]
    # second BEAR has only 19 quiet sessions after the first
    assert rc.find_flips(dirs) == [25]
    dirs2 = [R] * 25 + [B] + [R] * 20 + [B]
    assert rc.find_flips(dirs2) == [25, 46]


def test_unlabelled_session_breaks_lookback():
    dirs = [R] * 10 + [None] + [R] * 19 + [B]
    assert rc.find_flips(dirs) == []
    dirs = [None] * 5 + [R] * 20 + [B]
    assert rc.find_flips(dirs) == [25]


def test_consecutive_bear_is_one_flip():
    dirs = [Q] * 20 + [B, B, B, Q]
    assert rc.find_flips(dirs) == [20]


# ── streaks and decision dates ────────────────────────────────────────────────

def test_streak_counts_flip_as_day_one():
    dirs = [R] * 20 + [B, B, B, Q]
    assert rc.streak_from(dirs, 20) == (3, True)
    assert rc.streak_from([R] * 20 + [B], 20) == (1, False)


def test_decision_index_kth_bear_session():
    dirs = [R] * 20 + [B, B, B, B, Q]
    assert rc.decision_index(dirs, 20, 1) == 20
    assert rc.decision_index(dirs, 20, 3) == 22          # third BEAR session
    assert rc.decision_index(dirs, 20, 10) is None        # streak ended at 4


def test_decision_index_pending_at_data_end():
    dirs = [R] * 20 + [B, B]
    assert rc.decision_index(dirs, 20, 3) == rc.PENDING
    dirs = [R] * 20 + [B, B, Q]
    assert rc.decision_index(dirs, 20, 3) is None


# ── real-shift outcome and censoring ──────────────────────────────────────────

def test_real_shift_ten_percent_within_window():
    closes = [100.0] * 5 + [95.0] * 30 + [89.9] + [100.0] * 40
    s = _series("X", closes)
    out = rc.outcome(s, 4)
    assert out["real"] is True
    assert out["maxdd"] == pytest.approx(-0.101)
    assert out["ret20"] == pytest.approx(-0.05)
    assert out["ret60"] == pytest.approx(0.0)


def test_exactly_ten_percent_counts_and_less_does_not():
    s = _series("X", [100.0] + [90.0] + [100.0] * 70)
    assert rc.outcome(s, 0)["real"] is True
    s = _series("X", [100.0] + [90.01] + [100.0] * 70)
    assert rc.outcome(s, 0)["real"] is False


def test_drop_after_window_is_not_a_shift():
    closes = [100.0] * 61 + [50.0] * 10
    s = _series("X", closes)
    assert rc.outcome(s, 0)["real"] is False   # index 61 is session 61, outside


def test_outcome_measured_from_decision_close_not_flip():
    # 5% fall by the decision day, then a further 6%: 11% from the flip, ~6% from decision
    closes = [100.0, 97.0, 95.0] + [89.3] * 70
    s = _series("X", closes)
    assert rc.outcome(s, 0)["real"] is True
    assert rc.outcome(s, 2)["real"] is False


def test_censored_with_fewer_than_sixty_sessions_after():
    s = _series("X", [100.0] * 60)
    assert rc.outcome(s, 0) is None          # needs index 60
    s = _series("X", [100.0] * 61)
    assert rc.outcome(s, 0) is not None


def test_window_end_limit_censors():
    s = _series("X", [100.0] * 80, start="1992-10-01")
    end_date = s.dates[60]
    assert rc.outcome(s, 0, window_end_limit=end_date) is not None
    assert rc.outcome(s, 1, window_end_limit=end_date) is None


# ── conditions: missing counts as not met ─────────────────────────────────────

def test_missing_condition_is_not_met():
    assert rc.n_met({"C-200": None, "C-CR": None, "C-IWM": True, "C-VIX": True}) == 2
    assert rc.n_met({"C-200": None, "C-CR": None, "C-IWM": None, "C-VIX": True}) == 1


def test_below_sma_needs_full_runway():
    s = _series("X", [100.0] * 199 + [90.0])
    assert rc.below_sma(s, s.dates[198]) is None
    assert rc.below_sma(s, s.dates[199]) is True
    assert rc.below_sma(s, "2000-01-01") is None
    assert rc.below_sma(None, s.dates[199]) is None


def test_below_sma_is_causal():
    closes = [100.0] * 200 + [50.0]
    s = _series("X", closes)
    assert rc.below_sma(s, s.dates[199]) is False   # tomorrow's crash unseen


def test_credit_uses_adj_close_ratio():
    n = 30
    hyg_close = [100.0] * n                         # flat unadjusted
    hyg_adj = [100.0] * (n - 1) + [98.0]            # -2% adjusted on the last day
    hyg = _series("HYG", hyg_close, adj=hyg_adj)
    ief = _series("IEF", [100.0] * n)
    assert rc.credit_weak(hyg, ief, hyg.dates[-1]) is True
    assert rc.credit_weak(hyg, ief, hyg.dates[-2]) is False
    assert rc.credit_weak(hyg, ief, hyg.dates[10]) is None      # no 20-session runway


def test_vix_threshold_inclusive():
    v = _series("VIX", [19.99, 20.0])
    assert rc.vix_high(v, v.dates[0]) is False
    assert rc.vix_high(v, v.dates[1]) is True


# ── clustering, verdicts, BH ──────────────────────────────────────────────────

def test_chain_clusters_within_sixty_sessions():
    assert rc.chain_clusters([0, 60, 120, 181]) == [0, 0, 0, 1]
    assert rc.chain_clusters([181, 0, 60]) == [1, 0, 0]
    assert rc.chain_clusters([0, 61]) == [0, 1]


def test_token_floors_and_ci():
    assert rc.token(19, 12, 60, 0.1, 0.2) == "UNDERPOWERED"
    assert rc.token(20, 11, 60, 0.1, 0.2) == "UNDERPOWERED"
    assert rc.token(20, 12, 59, 0.1, 0.2) == "UNDERPOWERED"
    assert rc.token(20, 12, 60, 0.01, 0.2) == "SUPPORTED"
    assert rc.token(20, 12, 60, -0.2, -0.01) == "CONTRARY"
    assert rc.token(20, 12, 60, -0.1, 0.2) == "NULL"
    assert rc.forward_token("UNDERPOWERED") == "STILL-OPEN"


def test_retro_verdict_grammar():
    assert rc.retro_verdict("SUPPORTED", "SUPPORTED") == "RETRO-SUPPORTED"
    assert rc.retro_verdict("CONTRARY", "UNDERPOWERED") == "RETRO-CONTRARY"
    assert rc.retro_verdict("SUPPORTED", "UNDERPOWERED") == "UNDERPOWERED"
    assert rc.retro_verdict("NULL", "SUPPORTED") == "RETRO-NULL"


def test_bh_adjust():
    q = rc.bh_adjust([0.01, 0.04, 0.03, 1.0])
    assert q == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 1.0])


def _ev(day, real, ticker="X", lag=0.0):
    return rc.Event(ticker, f"2020-01-{day:02d}", f"2020-01-{day:02d}", lag,
                    {"real": real, "ret20": 0.0, "ret60": 0.0, "maxdd": -0.2 if real else 0.0})


def test_boot_same_draw_difference_and_recall():
    cal = np.array(pd.bdate_range("2020-01-01", periods=400).strftime("%Y-%m-%d"))
    ctrl = [rc.Event("X", d, d, 0.0, {"real": i % 4 == 0, "ret20": 0, "ret60": 0, "maxdd": 0})
            for i, d in enumerate(cal[::61][:6])]
    arm = [e for e in ctrl if e.out["real"]]
    b = rc.boot(arm, ctrl, cal, n=500)
    assert b["diff"] == pytest.approx(1.0 - 2 / 6)
    assert b["lo"] <= b["diff"] <= b["hi"]
    assert rc.recall(arm, ctrl) == 1.0
    assert rc.n_clusters(ctrl, cal) == 6


def test_build_events_streak_and_conditions():
    # 70 rising sessions, then a fall that flips and holds BEAR, then a crash
    closes = list(np.linspace(100, 130, 70)) + list(np.linspace(129, 110, 10)) + [95.0] * 70
    s = _series("SPY", closes)
    dirs = rc.mech_directions(s)
    flips = rc.find_flips(dirs)
    assert flips, dirs[60:85]
    ev, census = rc.build_events("SPY", s, dirs, flips[:1], {"SPY": s})
    f = flips[0]
    assert ev["RC0"][0].decision_date == s.dates[f]
    assert ev["RC-P"][0].decision_date == s.dates[f + 2]
    assert ev["RC-P"][0].lag < 0
    assert ev["RC1"] == []                    # SPY-only data: at most 1 condition
    assert census["RC0"]["missing"]["C-CR"] == 1
