"""Pins `scripts/backtest_study/lib/confidence_sequence.py`.

Two fixtures, as `refuse_floor_forward`'s registration asks:

1. values computed by hand from Waudby-Smith et al. (2024) Theorem 2.2,
   Eq. (8), with `rho` from Appendix B.2, Eq. (50);
2. a coverage simulation on synthetic data: over many independent sequences,
   the running intersection, read at EVERY step from the start count onward,
   excludes the true mean in at most about `alpha` of them. A fixed-sample CI
   read the same way fails that, which is the point of the module.
"""
from __future__ import annotations

import math
import random

import pytest

from scripts.backtest_study.lib import confidence_sequence as CS


# ── 1. hand-computed fixture ─────────────────────────────────────────────────
# alpha = 0.05, t* = 10.
#   -2 log 0.05                 = 5.991464547
#   log(5.991464547 + 1)        = 1.944690055
#   rho^2 = (5.991464547 + 1.944690055) / 10 = 0.793615460
#
# xs = [1.0, -0.5, 0.25, 0.75]
#   t = 2: mean 0.25, var (1 + 0.25)/2 - 0.0625 = 0.5625, sd 0.75
#          A = 2 * 0.793615460 + 1 = 2.587230920
#          k = 2A / (4 rho^2) * log(sqrt(A) / 0.05) = 1.629979 * 3.471022 = 5.657870
#          half-width = 0.75 * sqrt(5.657870) = 1.783971
#   t = 4: mean 0.375, var (1 + 0.25 + 0.0625 + 0.5625)/4 - 0.140625 = 0.328125
#          A = 4.174461841, k = 2A / (16 rho^2) * log(sqrt(A)/0.05) = 2.439499
#          half-width = sqrt(0.328125) * sqrt(2.439499) = 0.894685
ALPHA, T_STAR = 0.05, 10
XS = [1.0, -0.5, 0.25, 0.75]


def test_rho_matches_eq_50_by_hand():
    assert CS.rho_for(ALPHA, T_STAR) ** 2 == pytest.approx(0.793615460, abs=1e-9)


def test_half_width_matches_eq_8_by_hand():
    rho = CS.rho_for(ALPHA, T_STAR)
    assert CS.half_width(2, 0.75, ALPHA, rho) == pytest.approx(1.783971, abs=1e-6)
    assert CS.half_width(4, math.sqrt(0.328125), ALPHA, rho) == pytest.approx(0.894685,
                                                                              abs=1e-6)


def test_sequence_steps_match_the_hand_values():
    steps = CS.sequence(XS, ALPHA, T_STAR, start=2)
    assert [s.t for s in steps] == [1, 2, 3, 4]
    s2, s4 = steps[1], steps[3]
    assert (s2.mean, s2.sd) == pytest.approx((0.25, 0.75))
    assert (s2.lo, s2.hi) == pytest.approx((0.25 - 1.783971, 0.25 + 1.783971), abs=1e-6)
    assert (s4.mean, s4.sd) == pytest.approx((0.375, math.sqrt(0.328125)))
    assert (s4.lo, s4.hi) == pytest.approx((0.375 - 0.894685, 0.375 + 0.894685), abs=1e-6)


def test_sd_uses_divisor_t():
    s = CS.sequence([1.0, 3.0], ALPHA, T_STAR)[-1]
    assert s.sd == pytest.approx(1.0)          # divisor t-1 would give sqrt(2)


def test_running_intersection_starts_at_start_and_only_narrows():
    steps = CS.sequence(XS, ALPHA, T_STAR, start=2)
    assert steps[0].run_lo is None and steps[0].run_hi is None
    for prev, cur in zip(steps[1:], steps[2:]):
        assert cur.run_lo >= prev.run_lo and cur.run_hi <= prev.run_hi
    assert steps[-1].run_lo == pytest.approx(max(s.lo for s in steps[1:]))
    assert steps[-1].run_hi == pytest.approx(min(s.hi for s in steps[1:]))


def test_the_intersection_keeps_a_tighter_earlier_bound():
    # t = 3 has sd 0, so its interval is the point 0.1; the wide t = 4 interval
    # cannot widen the intersection back out.
    steps = CS.sequence([0.1, 0.1, 0.1, 5.0], ALPHA, T_STAR, start=3)
    assert steps[-1].lo < 0.1 < steps[-1].hi
    assert steps[-1].run_lo == pytest.approx(0.1) and steps[-1].run_hi == pytest.approx(0.1)


def test_an_empty_intersection_is_reported_not_repaired():
    xs = [0.0, 0.0] + [10.0] * 40
    steps = CS.sequence(xs, ALPHA, T_STAR, start=1)
    assert steps[-1].empty
    assert steps[-1].run_lo > steps[-1].run_hi


def test_interval_at_is_the_same_step_as_the_full_sequence():
    full = CS.sequence(XS, ALPHA, T_STAR, start=2)
    assert CS.interval_at(XS, 3, ALPHA, T_STAR, start=2) == full[2]
    assert CS.interval_at(XS, 9, ALPHA, T_STAR) is None
    assert CS.interval_at(XS, 0, ALPHA, T_STAR) is None


@pytest.mark.parametrize("alpha,t_star", [(0.0, 10), (1.0, 10), (0.05, 0)])
def test_bad_constants_raise(alpha, t_star):
    with pytest.raises(ValueError):
        CS.rho_for(alpha, t_star)


def test_non_finite_observation_raises():
    with pytest.raises(ValueError):
        CS.sequence([0.1, float("nan")], ALPHA, T_STAR)


# ── 2. coverage across repeated looks ────────────────────────────────────────
# The registered constants of refuse_floor_forward: alpha 0.0125 per sequence,
# t* = 150, the intersection starting at the 30-date minimum count.
REG_ALPHA, REG_T_STAR, REG_START = 0.0125, 150, 30
N_SEQ, LENGTH = 1500, 250
# A skewed, bounded R-like draw (mean +0.10), so the check is not leaning on
# normal data.
SUPPORT = (-1.0, -0.5, 0.2, 0.6, 1.3)
WEIGHTS = (0.25, 0.15, 0.20, 0.25, 0.15)
TRUE_MEAN = sum(s * w for s, w in zip(SUPPORT, WEIGHTS))


def _draws(rng: random.Random) -> list[float]:
    return [rng.choices(SUPPORT, WEIGHTS)[0] + rng.gauss(0.0, 0.1) for _ in range(LENGTH)]


def _misses(xs: list[float]) -> bool:
    last = CS.sequence(xs, REG_ALPHA, REG_T_STAR, start=REG_START)[-1]
    return not (last.run_lo <= TRUE_MEAN <= last.run_hi)


def _naive_misses(xs: list[float], z: float) -> bool:
    """A fixed-sample CI re-read at every look from the start count on."""
    s = s2 = 0.0
    for t, x in enumerate(xs, start=1):
        s += x
        s2 += x * x
        if t < REG_START:
            continue
        m = s / t
        sd = math.sqrt(max(s2 / t - m * m, 0.0))
        if abs(m - TRUE_MEAN) > z * sd / math.sqrt(t):
            return True
    return False


def test_running_intersection_covers_at_the_stated_rate_across_every_look():
    rng = random.Random(20261007)
    seqs = [_draws(rng) for _ in range(N_SEQ)]
    rate = sum(_misses(xs) for xs in seqs) / N_SEQ
    # The running intersection at the last step excludes the mean iff some
    # look from REG_START on excluded it, so this is the any-look error rate.
    bound = REG_ALPHA + 3 * math.sqrt(REG_ALPHA * (1 - REG_ALPHA) / N_SEQ)
    assert rate <= bound, f"any-look miss rate {rate:.4f} above {bound:.4f}"

    # The fixed-sample CI at the same per-look level fails across looks.
    z = 2.4977                                    # two-sided 1 - 0.0125
    naive = sum(_naive_misses(xs, z) for xs in seqs) / N_SEQ
    assert naive > 3 * REG_ALPHA, f"naive repeated-look miss rate only {naive:.4f}"
