"""`lib/path_bootstrap.py` — pins the resampling scheme and the A3-identical
drawdown measure, on synthetic series only. No figure from any export.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_study.lib import path_bootstrap as PB  # noqa: E402
from scripts.backtest_study.lib.mtm_curve import max_drawdown as MC_max_drawdown  # noqa: E402


# ── max_drawdown_fraction mirrors A3 exactly ─────────────────────────────────

def test_max_drawdown_is_the_same_function_object_a3_uses():
    # hedge_criteria.py and hedge_timing.py both pin this identity for their
    # own re-export; path_bootstrap makes the same claim.
    assert PB.max_drawdown is MC_max_drawdown


def test_max_drawdown_fraction_divides_by_starting_capital_not_peak_equity():
    # cumulative path: 100 -> 300 -> -100 -> 50 (peak seeded at 0.0)
    pnl = [100.0, 200.0, -400.0, 150.0]
    dollar_mdd = MC_max_drawdown(pnl)
    assert dollar_mdd == -400.0  # peak 300 (after first two), trough -100 -> -400
    # fraction is against a FIXED starting capital, never the $300 peak
    assert PB.max_drawdown_fraction(pnl, 1000.0) == pytest.approx(0.4)


def test_max_drawdown_fraction_refuses_nonpositive_capital():
    with pytest.raises(ValueError):
        PB.max_drawdown_fraction([1.0, -2.0], 0.0)
    with pytest.raises(ValueError):
        PB.max_drawdown_fraction([1.0, -2.0], -100.0)


# ── determinism ───────────────────────────────────────────────────────────────

def test_same_seed_reproduces_the_distribution():
    pnl = [50.0, -30.0, 80.0, -120.0, 10.0, -5.0, 200.0, -90.0, 15.0, -60.0]
    a = PB.bootstrap_drawdown(pnl, 10_000.0, block=3, n_resamples=200, seed=7)
    b = PB.bootstrap_drawdown(pnl, 10_000.0, block=3, n_resamples=200, seed=7)
    assert a == b


def test_different_seed_moves_the_distribution():
    pnl = [50.0, -30.0, 80.0, -120.0, 10.0, -5.0, 200.0, -90.0, 15.0, -60.0]
    a = PB.bootstrap_drawdown(pnl, 10_000.0, block=3, n_resamples=200, seed=1)
    b = PB.bootstrap_drawdown(pnl, 10_000.0, block=3, n_resamples=200, seed=2)
    assert (a.p5, a.p25, a.p50, a.p75, a.p95) != (b.p5, b.p25, b.p50, b.p75, b.p95)
    # the realized figure never moves with the seed — it is not resampled
    assert a.realized_fraction == b.realized_fraction


# ── the identity invariant: block == n, non-circular, reproduces the realized
#    path's drawdown exactly ──────────────────────────────────────────────────

def test_block_equal_to_n_reproduces_the_realized_drawdown_every_draw():
    pnl = [120.0, -300.0, 400.0, -250.0, 60.0, -400.0, 500.0]
    band = PB.bootstrap_drawdown(pnl, 5_000.0, block=len(pnl), n_resamples=50,
                                 seed=3)
    realized = PB.max_drawdown_fraction(pnl, 5_000.0)
    assert band.realized_fraction == pytest.approx(realized)
    # every resampled path is the identity ordering -> zero spread
    assert band.p5 == band.p25 == band.p50 == band.p75 == band.p95
    assert band.p50 == pytest.approx(realized)


def test_block_longer_than_n_is_clamped_not_refused_and_still_identity():
    pnl = [10.0, -40.0, 30.0, -60.0]
    band = PB.bootstrap_drawdown(pnl, 1_000.0, block=999, n_resamples=25, seed=1)
    assert band.block == 999           # requested value kept for reporting
    assert band.block_effective == 4   # clamped to n
    realized = PB.max_drawdown_fraction(pnl, 1_000.0)
    assert band.p50 == pytest.approx(realized)
    assert band.p5 == band.p95 == pytest.approx(realized)


# ── all-positive series never draws down, under any reordering ──────────────

def test_all_positive_series_has_zero_drawdown_at_every_block_length():
    pnl = [10.0, 25.0, 5.0, 40.0, 15.0, 8.0, 30.0, 12.0]
    for block in (1, 2, 3, len(pnl)):
        band = PB.bootstrap_drawdown(pnl, 2_000.0, block=block, n_resamples=100,
                                     seed=5)
        assert band.realized_fraction == 0.0
        assert band.p5 == band.p25 == band.p50 == band.p75 == band.p95 == 0.0


# ── empty series is refused ──────────────────────────────────────────────────

def test_empty_series_is_refused():
    with pytest.raises(ValueError):
        PB.bootstrap_drawdown([], 10_000.0, block=5, n_resamples=100, seed=1)


# ── other input guards ───────────────────────────────────────────────────────

def test_block_below_one_is_refused():
    with pytest.raises(ValueError):
        PB.bootstrap_drawdown([1.0, -2.0], 1_000.0, block=0, n_resamples=10, seed=1)


def test_n_resamples_below_one_is_refused():
    with pytest.raises(ValueError):
        PB.bootstrap_drawdown([1.0, -2.0], 1_000.0, block=1, n_resamples=0, seed=1)


# ── reference depth shares ───────────────────────────────────────────────────

def test_reference_shares_sum_to_one_and_bracket_correctly():
    pnl = [50.0, -30.0, 80.0, -120.0, 10.0, -5.0, 200.0, -90.0, 15.0, -60.0]
    band = PB.bootstrap_drawdown(
        pnl, 10_000.0, block=3, n_resamples=300, seed=11,
        reference_depths={"realized": 1.0, "impossible": -1.0, "always": 10.0})
    for label, (at_or_below, above) in band.reference_shares.items():
        assert at_or_below + above == pytest.approx(1.0)
        assert 0.0 <= at_or_below <= 1.0
    # a depth deeper than any possible drawdown -> every path is at-or-below
    assert band.reference_shares["always"][0] == pytest.approx(1.0)
    # a depth of -1.0 (shallower than a 0.0 drawdown can ever be) -> none qualify
    assert band.reference_shares["impossible"][0] == pytest.approx(0.0)


# ── convenience wrapper over block lengths ───────────────────────────────────

def test_bootstrap_drawdown_blocks_runs_every_requested_block_length():
    pnl = [50.0, -30.0, 80.0, -120.0, 10.0, -5.0, 200.0, -90.0, 15.0, -60.0,
           40.0, -20.0, 5.0, -75.0, 100.0]
    out = PB.bootstrap_drawdown_blocks(pnl, 10_000.0, n_resamples=150, seed=9,
                                       blocks=(5, 10, 20))
    assert set(out) == {5, 10, 20}
    for b, band in out.items():
        assert band.block == b
        assert band.n_resamples == 150
        assert band.seed == 9
    # block 20 > n=15 -> clamped, identity
    assert out[20].block_effective == 15


# ── format_block ──────────────────────────────────────────────────────────────

def test_format_block_prints_seed_n_resamples_blocks_and_all_three_caveats():
    pnl = [50.0, -30.0, 80.0, -120.0, 10.0, -5.0, 200.0, -90.0, 15.0, -60.0]
    bands = PB.bootstrap_drawdown_blocks(
        pnl, 10_000.0, n_resamples=100, seed=42, blocks=(5, 10),
        reference_depths={"realized": 0.35, "25% bar": 0.25})
    lines = PB.format_block(bands, label="PRIMARY")
    text = "\n".join(lines)
    assert "seed 42" in text
    assert "100 resamples" in text
    # The block lengths, as the header states them — "5" and "10" appear in
    # every percentile on the page and asserted nothing.
    assert "block lengths 5, 10" in text
    assert "PRIMARY" in text
    # caveat (a): sizing/caps/stop not re-simulated
    assert "NOT re-simulated" in text
    # caveat (b): noisy order statistic, cited
    assert "noisy order statistic" in text
    assert "Magdon-Ismail" in text
    # caveat (c): no decision rule
    assert "NO DECISION RULE" in text
    # never an annualised figure, Sharpe, or time-to-recover
    lowered = text.lower()
    assert "annualiz" not in lowered and "annualis" not in lowered
    assert "sharpe" not in lowered
    assert "time-to-recover" not in lowered and "time under water" not in lowered


def test_format_block_handles_empty_bands():
    lines = PB.format_block({})
    assert lines  # does not crash, says something


def test_format_block_reference_shares_sum_to_one_hundred_percent():
    """The pair partitions the resamples, so the printed halves must too.
    Formatted independently, one split printed 82.0% / 18.1%."""
    pnl = [10.0, -40.0, 25.0, -15.0, 30.0, -70.0, 5.0, 45.0, -20.0]
    for depth in (0.001 * k for k in range(1, 60)):
        bands = PB.bootstrap_drawdown_blocks(
            pnl, 1_000.0, n_resamples=999, seed=7, blocks=(3,),
            reference_depths={"ref": depth})
        for line in PB.format_block(bands):
            if "at-or-below" not in line or not line.startswith("    block"):
                continue
            below = float(line.split("at-or-below")[1].split("%")[0])
            above = float(line.split("above")[1].split("%")[0])
            assert below + above == pytest.approx(100.0, abs=1e-9)
