"""Pins `ticker_class`'s code behaviour against its registration
(research/pre-registrations/f1_selection/ticker_class.md): the frozen group
table and its hash (GT3), the first-match order, the direction rule, the
direction-standardisation arithmetic, Holm, the GT4 reconcile, the maxDD
episode and the blank-not-zero PBO matrix. Synthetic frames only: no figure
from any export is asserted here.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_study.f1_selection import ticker_class as TC  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402


# ── GT3: the frozen table and its hash ──────────────────────────────────────

def test_embedded_table_hashes_to_the_registered_digest():
    digest = hashlib.sha256(TC.GROUPS_V1_SOURCE.encode("utf-8")).hexdigest()
    assert digest == TC.GROUPS_V1_SHA256
    assert digest.startswith(TC.REGISTERED_HASH_PREFIX) and TC.REGISTERED_HASH_PREFIX == "6ce7373e"
    assert TC.table_hash() == digest


def test_any_edit_to_the_table_changes_the_hash():
    edited = TC.GROUPS_V1_SOURCE.replace('"QQQ",', "")
    assert edited != TC.GROUPS_V1_SOURCE
    assert TC.table_hash(edited) != TC.GROUPS_V1_SHA256


# ── the group map ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("ticker, group", [
    ("SPY", TC.G1), ("QQQ", TC.G1), ("IWM", TC.G1), ("DIA", TC.G1),
    ("FXI", TC.G2), ("MCHI", TC.G2),
    ("SMH", TC.G3), ("DRAM", TC.G3),
    ("GLD", TC.G4), ("IBIT", TC.G4),
    ("NVDA", TC.G6), ("SKHY", TC.G6), ("AMD", TC.G6),
    ("TSLA", TC.G5), ("GOOG", TC.G5), ("META", TC.G5),
    ("SMCI", TC.G7), ("SNDK", TC.G7), ("SPCX", TC.G7), ("COIN", TC.G7), ("ZZZZ", TC.G7),
    (" spy ", TC.G1), ("nvda", TC.G6),
])
def test_group_of(ticker, group):
    assert TC.group_of(ticker) == group


def test_first_match_order_is_the_registered_one():
    names = [n for n, _ in TC.TABLE_ORDER]
    assert names == [TC.G1, TC.G2, TC.G3, TC.G4, TC.G6, TC.G5]


def test_explicit_sets_are_disjoint_so_every_ticker_has_one_group():
    seen = {}
    for name, members in TC.TABLE_ORDER:
        for t in members:
            assert t not in seen, f"{t} listed in {seen.get(t)} and {name}"
            seen[t] = name
            assert TC.explicit_memberships(t) == [name]
    assert TC.explicit_memberships("COIN") == []


def test_single_stock_set_excludes_every_etf_group():
    assert set(TC.SINGLE_STOCK) == {TC.G5, TC.G6, TC.G7}
    assert TC.GRADED_GROUPS == (TC.G1, TC.G2, TC.G5, TC.G6, TC.G7)
    assert TC.BEAR_PBO_GROUPS == (TC.G1, TC.G5, TC.G6, TC.G7)


# ── the direction rule ──────────────────────────────────────────────────────

@pytest.mark.parametrize("structure, d", [
    ("bull_call_spread", "bull"), ("bull_put_spread", "bull"), ("long_call", "bull"),
    ("short_put", "bull"), ("bear_put_spread", "bear"), ("bear_call_spread", "bear"),
    ("long_put", "bear"), ("straddle", "neutral"), ("strangle", "neutral"),
    ("iron_condor", "neutral"), ("butterfly", "neutral"), ("calendar", "neutral"),
    ("diagonal", "other"), ("", "other"), (None, "other"),
])
def test_direction(structure, d):
    assert TC.direction(structure) == d


# ── standardisation arithmetic ──────────────────────────────────────────────

def _row(date, d, R, group=TC.G1, ticker="SPY"):
    return dict(date=date, dir=d, R=R, Rg=R, hit=1.0 if R > 0 else 0.0,
                group=group, ticker=ticker, exit_date=date)


def _dirstrat(r):
    return r["dir"]


def test_std_point_weights_stratum_means_not_rows():
    rows = ([_row("2025-01-02", "bear", 1.0)] * 3 + [_row("2025-01-03", "bull", -1.0)] * 9)
    # raw mean would be -0.5; G1-mix 0.8/0.2 weighting gives 0.8*1 + 0.2*(-1)
    assert TC.std_point(rows, {"bear": 0.8, "bull": 0.2}, _dirstrat) == pytest.approx(0.6)


def test_std_point_renormalises_over_present_strata():
    rows = [_row("2025-01-02", "bear", 0.5)]
    assert TC.std_point(rows, {"bear": 0.8, "bull": 0.2}, _dirstrat) == pytest.approx(0.5)
    assert np.isnan(TC.std_point([], {"bear": 1.0}, _dirstrat))


def test_diff_point_uses_strata_present_on_both_sides():
    a = [_row("2025-01-02", "bear", 1.0), _row("2025-01-02", "bull", 3.0)]
    b = [_row("2025-01-02", "bear", 0.0)]
    # bull missing on b -> only bear is compared
    assert TC.diff_point(a, b, {"bear": 0.5, "bull": 0.5}, _dirstrat) == pytest.approx(1.0)


def _dates(n, month=1):
    return [f"2025-{month + i // 28:02d}-{i % 28 + 1:02d}" for i in range(n)]


def test_direction_weights_take_g1_mix_and_drop_thin_strata():
    g1 = [_row(d, "bear", 0.0) for d in _dates(40)] + [_row(d, "bull", 0.0) for d in _dates(10)]
    b = [_row(d, "bear", 0.0) for d in _dates(40)] + [_row(d, "bull", 0.0) for d in _dates(40)]
    w, raw, dropped = TC.direction_weights(g1, b)
    assert raw == pytest.approx({"bear": 0.8, "bull": 0.2})
    assert w == {"bear": 1.0}          # G1-bull has 10 dates < 30: dropped, renormalised
    assert dropped and dropped[0].startswith("bull")
    g1 += [_row(d, "bull", 0.0) for d in _dates(30, month=3)]
    w, raw, _ = TC.direction_weights(g1, b)
    assert w == pytest.approx({"bear": 0.5, "bull": 0.5})


def test_joint_boot_is_degenerate_on_a_constant_shift():
    a = [_row(d, "bear", 1.0) for d in _dates(30)]
    b = [_row(d, "bear", 0.25) for d in _dates(30)]
    draws, dropped = TC.joint_boot(a, b, {"bear": 1.0}, _dirstrat, n=200)
    assert dropped == 0 and len(draws) == 200
    assert np.allclose(draws, 0.75)
    assert TC.pct_ci(draws) == pytest.approx((0.75, 0.75))
    assert TC.boot_p(draws) == 0.0


def test_joint_boot_resamples_dates_jointly():
    # Each date's two sides move together: a joint resample keeps the paired
    # difference constant even though the levels vary across dates.
    a, b = [], []
    for i, d in enumerate(_dates(40)):
        a.append(_row(d, "bear", float(i)))
        b.append(_row(d, "bear", float(i) - 0.1))
    draws, _ = TC.joint_boot(a, b, {"bear": 1.0}, _dirstrat, n=300)
    assert np.allclose(draws, 0.1)


# ── Holm ─────────────────────────────────────────────────────────────────────

def test_holm_step_down():
    out = TC.holm({"S1": 0.01, "S2": 0.04, "S3": 0.03, "S4": 0.5})
    assert out["S1"] == (pytest.approx(0.04), 1, pytest.approx(0.0125))
    assert out["S3"] == (pytest.approx(0.09), 2, pytest.approx(0.05 / 3))
    assert out["S2"] == (pytest.approx(0.09), 3, pytest.approx(0.025))  # monotone: max(0.09, 0.08)
    assert out["S4"] == (pytest.approx(0.5), 4, pytest.approx(0.05))


# ── GT4 and the drawdown episode ────────────────────────────────────────────

def test_gt4_partition_reconciles():
    rows = [_row("2025-01-02", "bear", 0.3, group=g) for g in TC.ALL_GROUPS]
    rows += [_row("2025-01-03", "bull", -0.7, group=TC.G7)]
    by_g, book = TC.gt4_sums(rows)
    assert abs(by_g - book) <= TC.GT4_TOL


def test_gt4_would_catch_an_unmapped_group():
    rows = [_row("2025-01-02", "bear", 0.3), _row("2025-01-02", "bear", 0.2, group="G8_bogus")]
    by_g, book = TC.gt4_sums(rows)
    assert abs(by_g - book) > TC.GT4_TOL


def test_maxdd_episode_and_shares():
    rows = [
        _row("2025-01-02", "bull", 2.0, group=TC.G5),
        _row("2025-01-03", "bear", -1.5, group=TC.G1),
        _row("2025-01-06", "bull", -0.5, group=TC.G6),
        _row("2025-01-07", "bull", 1.0, group=TC.G6),
    ]
    depth, pk, tr, ep = TC.maxdd_episode(rows)
    assert depth == pytest.approx(2.0) and pk == "2025-01-02" and tr == "2025-01-06"
    assert {r["group"] for r in ep} == {TC.G1, TC.G6}
    sh = TC.dd_shares(ep, depth)
    assert sh[TC.G1] == (pytest.approx(0.75), pytest.approx(0.5))
    assert sh[TC.G6] == (pytest.approx(0.25), pytest.approx(0.5))


# ── PBO matrix: blank, never zero ───────────────────────────────────────────

def test_month_span_and_trim_are_by_date_only():
    months = TC.month_span("2024-01", "2026-08")
    assert len(months) == 32 and months[0] == "2024-01" and months[-1] == "2026-08"
    kept, trimmed = TC.trim_to_multiple(months, 16)
    assert kept == months and trimmed == []
    kept, trimmed = TC.trim_to_multiple(months[1:], 16)
    assert len(kept) == 16 and trimmed == months[1:16]


def test_monthly_matrix_leaves_empty_months_blank():
    rows = [_row("2025-01-10", "bear", 1.0, group=TC.G1),
            _row("2025-01-10", "bull", -1.0, group=TC.G1),
            _row("2025-02-10", "bear", 0.5, group=TC.G5)]
    M = TC.monthly_matrix(rows, (TC.G1, TC.G5), {"bear": 0.8, "bull": 0.2}, ["2025-01", "2025-02"])
    assert M[0, 0, 0] == pytest.approx(0.6) and M[0, 0, 1] == 1.0
    assert M[1, 0, 1] == 0.0          # G1 has no February position: blank
    assert M[0, 1, 1] == 0.0 and M[1, 1, 0] == pytest.approx(0.5)
    # the block statistic averages the non-blank months only
    stat = PBO.ratio_metric(M)
    assert stat[0] == pytest.approx(0.6) and stat[1] == pytest.approx(0.5)


def test_verdict_grammar_on_a_synthetic_contrast():
    c = TC.Contrast("P1", "x", [], [], "S", True)
    c.res = dict(underpowered=[], c4=True, c5=True, c6=True)
    assert TC.verdict_for(c, True, False, True, True, 0.20, False, True) == "INDEX-MORE-RELIABLE"
    assert TC.verdict_for(c, True, False, True, True, 0.40, False, True).endswith("selection fragile")
    assert TC.verdict_for(c, True, False, True, True, 0.60, False, True).startswith("NULL")
    assert TC.verdict_for(c, False, True, False, False, 0.20, False, True) == "INDEX-LESS-RELIABLE (CONTRARY)"
    assert TC.verdict_for(c, False, False, False, False, 0.20, True, False) == "MIX-ONLY"
    c.res["c5"] = False
    assert "failed criterion 5" in TC.verdict_for(c, True, False, True, True, 0.20, False, True)
    c.res["underpowered"] = ["thin"]
    assert TC.verdict_for(c, True, False, True, True, 0.20, False, True) == "UNDERPOWERED"
    s = TC.Contrast("S2", "x", [], [], "G6", False)
    s.res = dict(underpowered=[], c4=False, c5=True, c6=True)
    assert TC.verdict_for(s, False, False, False, False, 0.20, False, False) == "NULL vs G6"
