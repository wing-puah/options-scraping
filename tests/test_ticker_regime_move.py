"""ticker_regime_move — the registered rows, windows, own-trend flag, strata and verdict
words (research/pre-registrations/f1_selection/regime/ticker_regime_move.md)."""
from __future__ import annotations

import math
from collections import Counter
from datetime import date, timedelta

import pytest

from scripts.backtest_study.f1_selection.regime import market_read as MR
from scripts.backtest_study.f1_selection.regime import ticker_regime_move as T
from scripts.backtest_study.lib import era
from scripts.backtest_study.lib.underlying import Bar


def _sessions(n: int, start: date = date(2025, 1, 1)) -> list[date]:
    return [start + timedelta(days=k) for k in range(n)]


def _cal(sessions, closes=None) -> MR.Calendar:
    closes = closes or [100.0] * len(sessions)
    return MR.Calendar.from_pairs((s.isoformat(), c) for s, c in zip(sessions, closes))


def _bars(sessions, closes) -> dict:
    return {s: Bar(c=c) for s, c in zip(sessions, closes)}


# ── helpers are imported, not copied ─────────────────────────────────────────

def test_parse_and_lag_are_market_reads_own_functions():
    assert T.MR.parse_label is MR.parse_label
    assert T.MR.lag_bin is MR.lag_bin
    assert T.BLOCK == MR.BLOCK == 21


# ── rows ─────────────────────────────────────────────────────────────────────

def test_dedupe_keeps_first_agreeing_row_and_drops_a_disagreeing_pair():
    rows = [
        {"date": "2025-01-02", "ticker": "AAA", "regime": "BULL + E-VOL — one", "k": 1},
        {"date": "2025-01-02", "ticker": "AAA", "regime": "BULL + L-VOL — two", "k": 2},
        {"date": "2025-01-02", "ticker": "BBB", "regime": "BULL — one"},
        {"date": "2025-01-02", "ticker": "BBB", "regime": "BEAR — two"},
    ]
    kept, ambiguous = T.dedupe(rows)
    assert [r["k"] for r in kept] == [1]
    assert ambiguous == 1


def test_build_drops_market_spy_other_and_off_calendar(monkeypatch):
    monkeypatch.setattr(era, "SEAL_LIFTED", "2026-11-26")
    ss = _sessions(80)
    cal = _cal(ss)
    bars = _bars(ss, [50.0 + 0.1 * k for k in range(80)])
    d = ss[60].isoformat()
    rows = [
        {"date": d, "ticker": "MARKET", "regime": "BULL"},
        {"date": d, "ticker": "SPY", "regime": "BULL"},
        {"date": d, "ticker": "AAA", "regime": "spot near highs"},
        {"date": "2030-01-01", "ticker": "BBB", "regime": "BULL"},
        {"date": d, "ticker": "CCC", "regime": "BEAR + C-VOL — text",
         "signal": "[FLOW] puts", "created_datetime": d + " 10:00"},
    ]
    b = T.build(rows, cal, load_bars=lambda tk: bars, beta=lambda bars, d: (1.0, 1.0))
    assert [(r.ticker, r.label.dir, r.lag, r.signal_tag) for r in b.recs] == [
        ("CCC", "BEAR", "LIVE", "FLOW")]
    c = b.counts
    assert (c["play_rows"], c["spy"], c["other"], c["off_calendar"]) == (4, 1, 1, 1)
    assert c["date_ticker_rows"] - c["spy"] - c["other"] - c["off_calendar"] == len(b.recs)


# ── windows: no lookahead, gaps, splits ──────────────────────────────────────

def test_window_return_reads_only_the_window():
    ss = _sessions(40)
    closes = [100.0 + k for k in range(40)]
    r, why = T.window_return(_bars(ss, closes), ss, 5, 10)
    assert why == "" and r == pytest.approx(math.log(115.0 / 105.0))
    # a bar after the window's last session cannot change it
    closes2 = closes[:16] + [999.0] * 24
    assert T.window_return(_bars(ss, closes2), ss, 5, 10)[0] == pytest.approx(r)


def test_window_return_refuses_past_end_gap_and_split():
    ss = _sessions(30)
    closes = [100.0] * 30
    assert T.window_return(_bars(ss, closes), ss, 25, 10) == (None, "past_end")
    gap = _bars(ss, closes)
    del gap[ss[8]]
    assert T.window_return(gap, ss, 5, 10) == (None, "no_bar")
    split = closes[:10] + [25.0] * 20                 # 4-for-1
    assert T.window_return(_bars(ss, split), ss, 5, 10) == (None, "split_guard")
    crash = closes[:10] + [62.0] * 20                 # a real -38% gap stays in
    r, why = T.window_return(_bars(ss, crash), ss, 5, 10)
    assert why == "" and r == pytest.approx(math.log(0.62))


def test_split_step_needs_a_common_ratio():
    assert T.is_split_step(math.log(2.0)) and T.is_split_step(-math.log(10.0))
    assert T.is_split_step(math.log(1.5 * 1.04))
    assert not T.is_split_step(math.log(1.25))        # under the 0.30 cap
    assert not T.is_split_step(math.log(1.75))        # large, but no split ratio
    assert not T.is_split_step(-math.log(2.5))


def test_excess_return_subtracts_spy_over_the_same_sessions():
    ss = _sessions(40)
    spy = [100.0 * 1.001 ** k for k in range(40)]
    tk = [50.0 * 1.003 ** k for k in range(40)]
    out = T.outcomes(_bars(ss, tk), _cal(ss, spy), ss, 21, Counter(),
                     beta=lambda bars, d: (2.0, 1.0))
    assert out["exret10"] == pytest.approx(10 * (math.log(1.003) - math.log(1.001)))
    assert out["bres10"] == pytest.approx(10 * (math.log(1.003) - 2.0 * math.log(1.001)))
    assert "exret21" not in out            # 21 + 21 runs past the 40-session calendar


def test_a_row_without_beta_keeps_the_plain_excess_and_leaves_d():
    ss = _sessions(40)
    c = Counter()
    out = T.outcomes(_bars(ss, [50.0] * 40), _cal(ss), ss, 5, c,
                     beta=lambda bars, d: (None, None))
    assert "exret21" in out and "bres21" not in out and c["no_beta"] == 1


def test_absz10_scales_by_trailing_rv_and_ignores_later_bars():
    ss = _sessions(60)
    tk = [50.0 * (1.01 if k % 2 else 0.995) ** 1 * (1 + 0.001 * k) for k in range(60)]
    cal = _cal(ss)
    a = T.outcomes(_bars(ss, tk), cal, ss, 30, Counter(), beta=lambda bars, d: (1.0, 1.0))
    rv = T.UF.rv20(_bars(ss, tk), ss[30])
    assert a["absz10"] == pytest.approx(
        abs(math.log(tk[40] / tk[30])) / (rv * math.sqrt(10 / 252)))
    later = tk[:41] + [x * 1.02 for x in tk[41:]]
    assert T.UF.rv20(_bars(ss, later), ss[30]) == pytest.approx(rv)


# ── own-trend flag ───────────────────────────────────────────────────────────

def test_own_trend_uses_only_bars_on_or_before_the_date():
    ss = _sessions(70)
    up = [100.0 + k for k in range(70)]
    assert T.own_trend(_bars(ss, up), ss[55]) == "above"
    crash_after = up[:56] + [1.0] * 14
    assert T.own_trend(_bars(ss, crash_after), ss[55]) == "above"
    down = [200.0 - k for k in range(70)]
    assert T.own_trend(_bars(ss, down), ss[55]) == "below"


def test_own_trend_needs_fifty_bars_and_a_bar_on_the_date():
    ss = _sessions(70)
    bars = _bars(ss, [100.0 + k for k in range(70)])
    assert T.own_trend(bars, ss[48]) is None           # 49 bars
    assert T.own_trend(bars, ss[49]) == "above"        # exactly 50
    del bars[ss[60]]
    assert T.own_trend(bars, ss[60]) is None


# ── contrasts and words ──────────────────────────────────────────────────────

def _rec(i, dir_, flag, ex, vol=None, z=None, transition=False):
    lab = MR.Label(head=dir_, dir=dir_, vol=vol, risk=None, hp=False, transition=transition)
    out = {"bres21": ex}
    if z is not None:
        out["absz10"] = z
    return T.Rec(f"d{i:04d}", "X", dir_, lab, "RETRO", i, flag, out)


def _book(bull_ex, bear_ex, blocks=8, per=10):
    recs = []
    for b in range(blocks):
        for k in range(per):
            i = b * T.BLOCK + k
            for flag in T.STRATA:
                recs.append(_rec(i, "BULL", flag, bull_ex + 0.001 * (k % 3)))
                recs.append(_rec(i, "BEAR", flag, bear_ex - 0.001 * (k % 3)))
    return recs


def test_d_is_supported_when_bull_beats_bear_in_both_strata():
    g = T.grade(_book(0.03, -0.02))
    assert g["D"].point == pytest.approx(0.052, abs=0.002)
    assert g["wD"] == "IN-SAMPLE-ONLY" and T.READ[g["wD"]] == "IN-SAMPLE-ONLY"
    assert T.grade(_book(0.03, -0.02), forward=True)["wD"] == "SUPPORTED"
    assert g["wS"] == "UNDERPOWERED"                    # no absz10 rows at all


def test_d_is_contrary_when_the_sign_flips():
    assert T.grade(_book(-0.03, 0.02))["wD"] == "CONTRARY"


def test_d_is_underpowered_when_one_stratum_misses_the_floor():
    recs = [r for r in _book(0.03, -0.02) if not (r.flag == "below" and r.label.dir == "BEAR")]
    recs += [_rec(k, "BEAR", "below", -0.02) for k in range(T.D_ROWS - 1)]
    g = T.grade(recs)
    assert not g["D"].weights and g["wD"] == "UNDERPOWERED"
    assert T.READ[g["wD"]] == "UNDERPOWERED"


def test_stratum_weights_are_shares_of_bull_and_bear_rows():
    recs = _book(0.03, -0.02)
    recs += [_rec(k, "RANGE", "above", 9.9) for k in range(40)]     # RANGE is in neither arm
    recs += [_rec(k, "BEAR", "above", 9.9, transition=True) for k in range(40)]   # nor a transition
    g = T.grade(recs)
    assert g["D"].weights == {"above": 0.5, "below": 0.5}
    assert g["D"].point == pytest.approx(0.052, abs=0.002)


def test_a_significant_raw_word_falls_to_null_without_the_holm_p():
    assert T.final_word("SUPPORTED", 0.06) == "NULL"
    assert T.final_word("SUPPORTED", 0.04) == "IN-SAMPLE-ONLY"
    assert T.final_word("SUPPORTED", 0.04, forward=True) == "SUPPORTED"
    assert T.final_word("CONTRARY", 0.04) == "CONTRARY"
    assert T.final_word("UNDERPOWERED", 0.0) == "UNDERPOWERED"


def test_s_arms_are_evol_against_another_vol_token_only():
    e = _rec(0, "BULL", "above", 0.0, vol="E-VOL", z=1.0)
    c = _rec(0, "BULL", "above", 0.0, vol="C-VOL", z=1.0)
    n = _rec(0, "BULL", "above", 0.0, vol=None, z=1.0)
    assert T.is_evol(e) and not T.is_other_vol(e)
    assert T.is_other_vol(c) and not T.is_evol(c)
    assert not T.is_evol(n) and not T.is_other_vol(n)


# ── scope ────────────────────────────────────────────────────────────────────

def test_scope_freezes_in_sample_and_keeps_only_live_rows_forward():
    assert T.scope_of("2026-10-01", 100, "RETRO", 121) == "in"
    assert T.scope_of("2026-10-02", 101, "RETRO", 121) == "gap"      # window closes too late
    assert T.scope_of("2026-11-27", 140, "LIVE", 121) == "gap"
    assert T.scope_of("2026-11-30", 141, "LIVE", 121) == "fwd"
    assert T.scope_of("2026-11-30", 141, "RETRO", 121) == "fwd_not_live"
