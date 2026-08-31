"""`lib/forward_drawdown.py` — the Stage-1 statistics `hedge_concentration`
ARM K reads, pinned as code-behaviour claims.

What is claimed here is the METHOD, not any figure: that the outcome series
needs a full window and is capped at zero, that the terciles are assigned over
the whole series and only the means drop the unusable rows, that the bootstrap
resamples BLOCKS in their original order, and that the shift null rotates x
against y by at least the horizon in both directions.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_study.lib import forward_drawdown as F  # noqa: E402


# ── forward_drawdown ─────────────────────────────────────────────────────────

def test_forward_drawdown_is_the_worst_change_inside_the_window():
    levels = [0, 5, 2, -3, 4, 1]
    y = F.forward_drawdown(levels, 2)
    # s=0: min(5-0, 2-0) -> 2, capped at 0
    # s=1: min(2-5, -3-5) -> -8
    # s=2: min(-3-2, 4-2) -> -5
    # s=3: min(4+3, 1+3) -> 4 -> 0
    assert y[:4] == [0.0, -8.0, -5.0, 0.0]


def test_forward_drawdown_requires_a_full_window():
    y = F.forward_drawdown([0, 1, 2, 3, 4], 3)
    assert y[0] is not None and y[1] is not None
    assert y[2:] == [None, None, None]


def test_forward_drawdown_refuses_a_zero_horizon():
    with pytest.raises(ValueError):
        F.forward_drawdown([0, 1], 0)


def test_forward_drawdown_never_exceeds_zero():
    assert all(v <= 0 for v in F.forward_drawdown(list(range(30)), 5) if v is not None)


# ── terciles and contrast ────────────────────────────────────────────────────

def test_rank_groups_split_evenly_and_break_ties_by_position():
    labels = F.rank_groups([1, 1, 1, 1, 1, 1])
    assert labels == [0, 0, 1, 1, 2, 2]
    labels = F.rank_groups([9, 1, 5, 7, 3, 8, 2])
    assert sorted(labels) == [0, 0, 0, 1, 1, 2, 2]
    assert labels[1] == 0 and labels[0] == 2


def test_contrast_uses_every_x_for_the_groups_but_only_usable_y_for_the_means():
    x = [1, 2, 3, 4, 5, 6]
    y = [-1.0, -2.0, -3.0, -4.0, None, None]
    # groups over all six x: bottom {1,2}, top {5,6}; top has no usable y
    assert math.isnan(F.tercile_contrast(x, y))
    y = [-1.0, -2.0, -3.0, -4.0, -10.0, None]
    assert F.tercile_contrast(x, y) == pytest.approx(-10.0 - (-1.5))


def test_group_counts_count_only_usable_rows():
    assert F.group_counts([1, 2, 3, 4, 5, 6], [0, 0, None, 0, None, 0]) == [2, 1, 1]


def test_spearman_is_minus_one_on_a_reversed_series_and_ignores_none():
    x = [1, 2, 3, 4, 5]
    assert F.spearman(x, [5, 4, 3, 2, 1]) == pytest.approx(-1.0)
    assert F.spearman(x, [1, 2, 3, 4, None]) == pytest.approx(1.0)
    assert math.isnan(F.spearman(x, [1, None, None, None, None]))
    assert math.isnan(F.spearman(x, [1, 1, 1, 1, 1]))


def test_within_group_stats_reads_the_statistic_inside_each_control_group():
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    y = [-x_ for x_ in x]
    g = [1, 1, 1, 2, 2, 2, 3, 3, 3]
    out = F.within_group_stats(x, y, g, F.spearman)
    assert len(out) == 3 and all(v == pytest.approx(-1.0) for v in out)


def test_sign_kept_counts_agreeing_signs_and_never_a_nan_or_zero():
    assert F.sign_kept([-1.0, -2.0, 0.5], -3.0) == 2
    assert F.sign_kept([float("nan"), 0.0, -1.0], -1.0) == 1
    assert F.sign_kept([-1.0], 0.0) == 0


# ── block bootstrap ──────────────────────────────────────────────────────────

def test_blocks_are_non_overlapping_and_the_last_may_be_short():
    assert F.block_starts(10, 4) == [0, 4, 8]


def test_a_resample_keeps_each_block_in_its_original_order():
    rng = random.Random(1)
    idx = F.resample_blocks(12, 4, rng)
    assert len(idx) == 12
    for b in range(0, 12, 4):
        chunk = idx[b:b + 4]
        assert chunk == list(range(chunk[0], chunk[0] + 4))
        assert chunk[0] % 4 == 0


def test_block_bootstrap_is_seeded_and_reproducible():
    x = list(range(40))
    y = [-v + (v % 3) for v in x]
    a = F.block_bootstrap(x, y, F.tercile_contrast, block=5, n_boot=50, seed=7)
    b = F.block_bootstrap(x, y, F.tercile_contrast, block=5, n_boot=50, seed=7)
    assert a == b
    assert a.point == pytest.approx(F.tercile_contrast(x, y))
    assert a.lo <= a.point <= a.hi
    assert a.n_blocks == 8 and a.seed == 7


def test_block_bootstrap_ci_excludes_zero_only_when_both_ends_agree():
    r = F.BootResult(point=-1, lo=-2, hi=-0.5, n_boot=1, block=1, n_blocks=1,
                     seed=0, alpha=0.05)
    assert r.excludes_zero
    r2 = F.BootResult(point=-1, lo=-2, hi=0.5, n_boot=1, block=1, n_blocks=1,
                      seed=0, alpha=0.05)
    assert not r2.excludes_zero
    r3 = F.BootResult(point=-1, lo=float("nan"), hi=-0.5, n_boot=1, block=1,
                      n_blocks=1, seed=0, alpha=0.05)
    assert not r3.excludes_zero


def test_block_bootstrap_refuses_mismatched_series():
    with pytest.raises(ValueError):
        F.block_bootstrap([1, 2, 3], [1, 2], F.spearman, 1, 5, 0)


# ── circular-shift null ──────────────────────────────────────────────────────

def test_circular_shift_rotates_left():
    assert F.circular_shift([1, 2, 3, 4], 1) == [2, 3, 4, 1]
    assert F.circular_shift([1, 2, 3, 4], 5) == [2, 3, 4, 1]
    assert F.circular_shift([], 3) == []


def test_every_shift_moves_x_at_least_min_shift_from_its_own_y():
    n, ms = 30, 5
    seen = set()

    def probe(xs, ys):
        # xs is the rotated identity, so xs[0] IS the offset used
        seen.add(int(xs[0]))
        return 0.0

    F.circular_shift_null(list(range(n)), [0.0] * n, probe, ms, 200, seed=3)
    seen.discard(0)          # the point estimate, computed unrotated
    assert seen and min(seen) >= ms and max(seen) <= n - ms


def test_shift_null_bands_a_real_relationship_and_reports_the_point():
    n = 120
    x = [math.sin(i / 4.0) for i in range(n)]
    y = [-v for v in x]
    res = F.circular_shift_null(x, y, F.spearman, 20, 200, seed=11)
    assert res.point == pytest.approx(-1.0)
    assert res.beats_low() and not res.beats_high()
    assert res.p05 > -1.0
    assert len(res.values) == 200


def test_shift_null_refuses_a_series_too_short_for_the_shift():
    with pytest.raises(ValueError):
        F.circular_shift_null([1, 2, 3], [1, 2, 3], F.spearman, 2, 5, 0)


def test_pctile_interpolates_and_ignores_nan():
    assert F.pctile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert F.pctile([float("nan"), 5.0], 50) == 5.0
    assert math.isnan(F.pctile([], 50))
