"""dip_buy (research/pre-registrations/f1_selection/dip_buy.md): the dip label,
the gating, the tie-break and the verdict grammar, on synthetic data only.

No figure here comes from an export: each test builds its own rows.
"""
from __future__ import annotations

import csv
import math
from datetime import date, timedelta

import pytest

from lib.mech_regime import MechLabeler, compute_mech_table
from scripts.backtest_study.f1_selection import dip_buy as D
from scripts.backtest_study.lib import era


def _table(tmp_path, spy):
    p = tmp_path / "spy_vix.csv"
    d0 = date(2024, 1, 1)
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "spy_close", "vix_close"])
        for i, s in enumerate(spy):
            w.writerow([(d0 + timedelta(days=i)).isoformat(), s, 15.0])
    return p, [(d0 + timedelta(days=i)).isoformat() for i in range(len(spy))]


# ── the dip label ────────────────────────────────────────────────────────────

def test_below_sma_flag_tracks_the_close_against_its_50_day_mean(tmp_path):
    p, days = _table(tmp_path, [100.0] * 50 + [90.0, 120.0])
    rows = {r["date"]: r for r in compute_mech_table(p)}
    assert rows[days[48]]["spy_below_sma"] is None      # no 50-day runway yet
    assert rows[days[49]]["spy_below_sma"] is False     # equal to its SMA: not below
    assert rows[days[50]]["spy_below_sma"] is True      # 90 < mean of the last 50
    assert rows[days[51]]["spy_below_sma"] is False


def test_dip_label_is_as_of_and_refuses_a_date_past_the_table(tmp_path):
    p, days = _table(tmp_path, [100.0] * 50 + [90.0])
    lab = MechLabeler.from_csv(p)
    assert D.dip_label(lab, days[50]) == D.BELOW
    assert D.dip_label(lab, days[49]) == D.ABOVE
    assert D.dip_label(lab, days[10]) is None            # no runway
    later = (date.fromisoformat(days[-1]) + timedelta(days=3)).isoformat()
    assert D.dip_label(lab, later) is None               # table does not reach it


# ── tier and preparation ─────────────────────────────────────────────────────

def _rec(d, structure="bull_call_spread", regime="RANGE + L-VOL", R=0.1, score=10.0,
         ticker="AAA", trusted=True):
    return dict(date=d, ticker=ticker, structure=structure, market_regime=regime,
                dte=30.0, delta=None, R=R, score_total=score, cpir=0.5,
                fill_trusted=trusted, tier="A")


def test_tier_comes_from_the_production_mapping():
    assert D.tier_of(_rec("2025-01-02")) == "A"                              # RANGE
    assert D.tier_of(_rec("2025-01-02", regime="BULL + L-VOL")) == "B"
    assert D.tier_of(_rec("2025-01-02", structure="bear_call_spread")) == "VETO"


def test_prepare_drops_and_counts(tmp_path):
    p, days = _table(tmp_path, [100.0] * 50 + [90.0])
    lab = MechLabeler.from_csv(p)
    recs = [_rec(days[50]), _rec(days[50], R=None), _rec(days[50], trusted=False),
            _rec(days[50], structure="bear_call_spread"), _rec(days[5])]
    rows, counts = D.prepare(recs, lab)
    assert len(rows) == 1 and rows[0]["dip"] == D.BELOW
    assert counts == {"R_missing": 1, "fill_untrusted": 1, "veto": 1, "dip_unlabelled": 1}


def test_split_window_uses_the_date_it_is_given(monkeypatch):
    rows = [dict(date="2026-09-22"), dict(date="2026-09-23"), dict(date="2026-10-01")]
    ins, fwd = D.split_window(rows, era.SEAL_START)
    assert all(r["date"] < era.SEAL_START for r in ins)
    assert all(r["date"] >= era.SEAL_START for r in fwd)
    assert len(ins) + len(fwd) == 3


# ── gating and the tie-break ─────────────────────────────────────────────────

def _row(d, tier, score, dip, R=0.0, structure="bull_call_spread"):
    return dict(date=d, tier=tier, score=score, dip=dip, R=R, structure=structure,
                ticker=f"{tier}{score}", cpir=None)


def test_dip_gate_deploys_only_on_below_dates():
    rows = [_row("d1", "A", 1, D.BELOW), _row("d2", "A", 1, D.ABOVE),
            _row("d2", "B", 2, D.ABOVE)]
    assert {r["date"] for r in D.top_k(rows, "desc", gate=D.BELOW)} == {"d1"}
    assert len(D.top_k(rows, "desc")) == 3


def test_tie_break_orders_within_tier_and_never_across_it():
    rows = [_row("d", "B", 99, D.BELOW), _row("d", "A", 1, D.BELOW),
            _row("d", "A", 5, D.BELOW), _row("d", "A", None, D.BELOW),
            _row("d", "C", 100, D.BELOW)]
    desc = [r["score"] for r in D.top_k(rows, "desc", k=4)]
    asc = [r["score"] for r in D.top_k(rows, "asc", k=4)]
    assert desc == [5, 1, None, 99]   # A first, unscored last in its tier, then B; C never
    assert asc == [1, 5, None, 99]


def test_random_null_takes_the_book_count_per_date():
    rows = [_row("d1", "A", 1, D.BELOW, R=1.0), _row("d1", "C", 1, D.BELOW, R=1.0),
            _row("d1", "C", 1, D.BELOW, R=-1.0, structure="bull_put_spread")]
    null = D.random_bcs_null(rows, {"d1"}, {"d1": 2}, sims=50)
    assert (null == 1.0).all()        # only the two bull_call_spreads are eligible


# ── statistics and the verdict grammar ───────────────────────────────────────

def _arm(dip, n_dates, per_date, R):
    return [dict(date=f"{dip}-{i:03d}", R=R, dip=dip)
            for i in range(n_dates) for _ in range(per_date)]


def test_boot_diff_of_constant_arms_is_exact():
    d, lo, hi = D.boot_diff(_arm("b", 5, 2, 1.0), _arm("a", 5, 2, -1.0), n=200)
    assert (d, lo, hi) == (2.0, 2.0, 2.0)


@pytest.mark.parametrize("lo, hi, want", [
    (0.1, 0.5, "SUPPORTED"), (-0.5, -0.1, "CONTRARY"), (-0.1, 0.2, "NULL"),
    (float("nan"), float("nan"), "STILL-OPEN")])
def test_verdict_grammar_past_the_floor(lo, hi, want):
    b, a = _arm("b", 30, 2, 0.0), _arm("a", 30, 2, 0.0)
    assert D.verdict(b, a, lo, hi) == want


@pytest.mark.parametrize("dates, per_date", [(29, 3), (30, 1)])
def test_either_floor_short_is_still_open(dates, per_date):
    short = _arm("b", dates, per_date, 1.0)
    full = _arm("a", 40, 2, 0.0)
    assert D.verdict(short, full, 0.5, 0.9) == "STILL-OPEN"
    assert D.verdict(full, short, 0.5, 0.9) == "STILL-OPEN"


def test_registered_floors_and_median_are_the_registrations():
    assert (D.MIN_DATES, D.MIN_POS, D.CPIR_MEDIAN, D.TOP_K) == (30, 60, 0.92, 3)


def test_no_forward_read_while_the_seal_stands():
    """The study is not a named reader: load_book withholds sealed dates for it."""
    assert "dip_buy" not in era.SEALED_READERS
    if not era.SEAL_LIFTED:
        assert era.is_withheld(era.SEAL_START)


def test_empty_forward_arms_print_no_number():
    assert all(math.isnan(x) for x in D.boot_mean([]))
    assert D.verdict([], [], float("nan"), float("nan")) == "STILL-OPEN"
