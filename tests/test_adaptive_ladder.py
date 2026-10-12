"""adaptive_ladder (research/pre-registrations/f1_selection/regime/adaptive_ladder.md):
no lookahead, the switching margin, the warm-up, the verdict grammar and the
menu gating, on synthetic data only. No figure here comes from an export.
"""
from __future__ import annotations

import math

import numpy as np

from scripts.backtest_study.f1_selection.regime import adaptive_ladder as A
from scripts.backtest_study.f1_selection.regime import dip_buy as DB


def _row(d, R, known, tier="A", score=10.0, dip=DB.ABOVE, structure="bull_call_spread",
         ticker="AAA"):
    return dict(date=d, R=R, known=known, tier=tier, score=score, dip=dip,
                structure=structure, ticker=ticker)


# ── no lookahead ─────────────────────────────────────────────────────────────

def test_a_position_known_on_or_after_the_rebalance_never_enters_the_score():
    book = {"2025-01-02": [(_row("2025-01-02", 1.0, "2025-01-30"), 1.0)],
            "2025-01-03": [(_row("2025-01-03", -1.0, "2025-02-03"), 1.0)],
            "2025-01-06": [(_row("2025-01-06", 5.0, "2025-02-10"), 1.0)]}
    s = A.trailing_score(book, "2025-02-03", window=None)
    assert s.n == 1 and s.mean == 1.0          # exit ON the rebalance date is excluded
    s = A.trailing_score(book, "2025-02-04", window=None)
    assert s.n == 2 and s.mean == 0.0          # known the day before: included
    s = A.trailing_score(book, "2025-02-10", window=None)
    assert s.n == 2                            # exit on 02-10 still excluded on 02-10


def test_an_open_position_is_never_known():
    book = {"2025-01-02": [(_row("2025-01-02", 9.0, None), 1.0)]}
    assert A.trailing_score(book, "2030-01-01", window=None).n == 0


def test_window_drops_positions_known_before_its_start():
    book = {"2025-01-02": [(_row("2025-01-02", 1.0, "2025-01-10"), 1.0)],
            "2025-03-03": [(_row("2025-03-03", 3.0, "2025-04-01"), 1.0)]}
    s = A.trailing_score(book, "2025-05-01", window=60)
    assert s.n == 1 and s.mean == 3.0
    assert A.trailing_score(book, "2025-05-01", window=None).n == 2


def test_known_date_reads_the_exit_session_and_refuses_open_rows():
    from datetime import date

    class T:
        grid = [date(2025, 1, 3), date(2025, 1, 6), date(2025, 1, 7)]
        row = {"path_status": ""}
    assert A.known_date(dict(t=T, days_held=2)) == "2025-01-06"
    T.row = {"path_status": "open_at_data_end"}
    assert A.known_date(dict(t=T, days_held=2)) is None


def test_the_adapter_never_reads_an_outcome_after_its_rebalance():
    """A huge future outcome for M5 must not move the switch before it is known."""
    days = {}
    for i, d in enumerate(["2025-01-02", "2025-02-03", "2025-03-03"]):
        days[d] = [_row(d, 0.0, "2025-01-10", tier="B", score=1.0, structure="bull_put_spread"),
                   _row(d, 100.0, "2025-12-31", tier="B", score=2.0, ticker="BBB")]
    books = A.menu_books(days)
    held, switches = A.run_adapter(books, list(days), "monthly", None, "mean", min_n=1)
    assert switches == [] and set(held.values()) == {"M0"}
    # The positive control: the same outcome known in time does move it.
    for d in days:
        days[d][1]["known"] = "2025-01-10"
    books = A.menu_books(days)
    held, switches = A.run_adapter(books, list(days), "monthly", None, "mean", min_n=1)
    assert switches and switches[0][0] == "2025-02-03" and switches[0][2] == "M5"


# ── switching margin ─────────────────────────────────────────────────────────

def _scores(**kw):
    out = {m: A.Score(float("nan"), float("nan"), 0.0) for m in A.MENU}
    out.update(kw)
    return out


def test_margin_lb_needs_the_lower_bound_above_the_incumbent_mean():
    sc = _scores(M0=A.Score(0.10, 0.0, 50), M1=A.Score(0.30, 0.05, 50))
    assert A.choose("M0", sc, "lb") == "M0"
    assert A.choose("M0", sc, "mean") == "M1"
    sc["M1"] = A.Score(0.30, 0.15, 50)
    assert A.choose("M0", sc, "lb") == "M1"


def test_minimum_n_blocks_a_thin_challenger():
    sc = _scores(M0=A.Score(0.0, -1, 50), M5=A.Score(1.0, 0.9, 19))
    assert A.choose("M0", sc, "lb") == "M0"
    sc["M5"] = A.Score(1.0, 0.9, 20)
    assert A.choose("M0", sc, "lb") == "M5"


def test_best_qualifying_challenger_wins_and_an_empty_incumbent_scores_cash():
    sc = _scores(M3=A.Score(float("nan"), float("nan"), 0),
                 M1=A.Score(0.2, 0.01, 30), M2=A.Score(0.4, 0.02, 30))
    assert A.choose("M3", sc, "lb") == "M2"
    sc["M1"] = A.Score(0.2, -0.01, 30)
    sc["M2"] = A.Score(0.4, -0.02, 30)
    assert A.choose("M3", sc, "lb") == "M3"


# ── warm-up ──────────────────────────────────────────────────────────────────

def test_warmup_is_six_calendar_months_from_the_first_month():
    assert A.warmup_end(["2024-01-10", "2024-02-01"]) == "2024-07-01"
    assert A.warmup_end(["2024-09-17"]) == "2025-03-01"


def test_walk_grades_only_dates_after_warmup_and_before_the_cut():
    rows = [_row(d, 0.1, d) for d in ["2024-01-10", "2024-06-28", "2024-07-01",
                                      "2024-08-01", "2026-09-23"]]
    W = A.walk(rows, "x", graded_until="2026-09-23")
    assert W["graded"] == ["2024-07-01", "2024-08-01"]


# ── verdict grammar ──────────────────────────────────────────────────────────

def test_verdict_grammar():
    assert A.verdict(0.01, 0.2) == "ADAPTS"
    assert A.verdict(-0.2, -0.01) == "HURTS"
    assert A.verdict(-0.1, 0.1) == "NULL"
    assert A.verdict(0.0, 0.0) == "NULL"
    assert A.verdict(float("nan"), 1.0) == "NULL"


def test_forward_is_still_open_below_either_floor():
    assert A.forward_verdict(29, 100, 0.1, 0.2) == "STILL-OPEN"
    assert A.forward_verdict(30, 59, 0.1, 0.2) == "STILL-OPEN"
    assert A.forward_verdict(30, 60, 0.1, 0.2) == "ADAPTS"


def test_month_block_bootstrap_is_zero_width_on_identical_books():
    dates = ["2025-01-02", "2025-01-03", "2025-02-03", "2025-02-04", "2025-03-03", "2025-03-04"]
    d, lo, hi = A.boot_month_mean(np.zeros(6), dates)
    assert (d, lo, hi) == (0.0, 0.0, 0.0)


# ── menu gating ──────────────────────────────────────────────────────────────

def _day(dip):
    return [_row("2025-01-02", 0.1, None, tier="A", score=5, dip=dip, ticker="A1"),
            _row("2025-01-02", 0.2, None, tier="A", score=1, dip=dip, ticker="A2"),
            _row("2025-01-02", 0.3, None, tier="B", score=3, dip=dip, ticker="B1",
                 structure="bull_put_spread"),
            _row("2025-01-02", 0.4, None, tier="B", score=9, dip=dip, ticker="B2"),
            _row("2025-01-02", 0.5, None, tier="B", score=2, dip=dip, ticker="B3")]


def _tickers(picks):
    return [r["ticker"] for r, _w in picks]


def test_tie_break_orders_within_tier_and_keeps_a_first():
    assert _tickers(A.select(_day(DB.ABOVE), "M0")) == ["A1", "A2", "B2"]
    assert _tickers(A.select(_day(DB.ABOVE), "M1")) == ["A2", "A1", "B3"]


def test_dip_gate_sits_out_above_dates():
    assert A.select(_day(DB.ABOVE), "M3") == []
    assert _tickers(A.select(_day(DB.BELOW), "M3")) == ["A2", "A1", "B3"]


def test_sit_out_keeps_tier_a_only_on_above_dates():
    assert _tickers(A.select(_day(DB.ABOVE), "M4")) == ["A2", "A1"]
    assert _tickers(A.select(_day(DB.BELOW), "M4")) == ["A2", "A1", "B3"]


def test_bull_call_only_rule_is_tier_blind_and_ascending():
    assert _tickers(A.select(_day(DB.ABOVE), "M5")) == ["A2", "B3", "A1"]


def test_random_rule_is_the_exact_expectation():
    picks = A.select(_day(DB.ABOVE), "M2")
    w = {r["ticker"]: wt for r, wt in picks}
    assert w["A1"] == w["A2"] == 1.0
    assert all(math.isclose(w[t], 1 / 3) for t in ("B1", "B2", "B3"))
    assert math.isclose(sum(w.values()), 3.0)


def test_slot_r_counts_a_sat_out_date_as_zero():
    book = {"2025-01-02": [], "2025-01-03": [(_row("2025-01-03", 0.6, None), 1.0)]}
    assert np.allclose(A.slot_r(book, ["2025-01-02", "2025-01-03"]), [0.0, 0.2])
