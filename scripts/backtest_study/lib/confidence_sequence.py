"""Asymptotic confidence sequence for a running mean — valid under repeated looks.

A fixed-sample CI re-read after every new observation rejects a true null far
more often than its stated rate. A confidence sequence is an interval that
covers the true mean at EVERY time at once, with the stated probability, so it
can be read on every suite run with no correction for how often it was read.

The boundary is Theorem 2.2, Eq. (8), of Waudby-Smith, Arbour, Sinha, Kennedy,
Ramdas (2024), "Time-uniform central limit theory and asymptotic confidence
sequences", Annals of Statistics 52(6), 2613-2640 (arXiv:2103.06476):

    mu_t  +-  sigma_t * sqrt( 2(t rho^2 + 1) / (t^2 rho^2) * log( sqrt(t rho^2 + 1) / alpha ) )

with `mu_t` the sample mean of X_1..X_t and `sigma_t^2 = (1/t) sum X_i^2 - mu_t^2`
(divisor t). It is a TWO-SIDED (1 - alpha) asymptotic confidence sequence. The
tuning constant `rho` sets the time at which the interval is tightest; the
closed form in Appendix B.2, Eq. (50), tunes it to a target time t*:

    rho = sqrt( (-2 log alpha + log(-2 log alpha + 1)) / t* )

The boundary is Robbins' normal-mixture boundary (Howard, Ramdas, McAuliffe,
Sekhon 2021, Annals of Statistics 49(2), Eq. (14)) with the variance estimated
from the data. Its guarantee is asymptotic, which is why a caller starts the
running intersection only once its minimum counts are met.

THE RUNNING INTERSECTION. Any intersection of the intervals of a confidence
sequence covers wherever every one of them covers, so the running
intersection — the largest lower bound and the smallest upper bound seen from
`start` onward — keeps the coverage and makes a verdict, once reached,
permanent. An EMPTY intersection (lower above upper) is evidence the
assumptions failed; it is reported, never repaired.

Pure: a sequence of floats in, dataclasses out. No I/O, no printing, and no
verdict — the caller owns the bars. Pinned by
`tests/test_confidence_sequence.py` against a hand-computed fixture and a
coverage simulation across repeated looks.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def rho_for(alpha: float, t_star: float) -> float:
    """Eq. (50): the `rho` that makes the boundary tightest near `t_star`."""
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    if t_star <= 0:
        raise ValueError(f"t_star must be positive, got {t_star}")
    two_log = -2.0 * math.log(alpha)
    return math.sqrt((two_log + math.log(two_log + 1.0)) / t_star)


def half_width(t: int, sigma: float, alpha: float, rho: float) -> float:
    """Eq. (8)'s half-width at observation count `t` for standard deviation `sigma`."""
    if t < 1:
        raise ValueError("t must be at least 1")
    a = t * rho * rho + 1.0
    return sigma * math.sqrt(2.0 * a / (t * t * rho * rho) * math.log(math.sqrt(a) / alpha))


@dataclass(frozen=True)
class Step:
    """The sequence at one observation count `t` (1-indexed)."""
    t: int
    mean: float
    sd: float                      # divisor t
    lo: float                      # this step's own interval
    hi: float
    run_lo: float | None           # running intersection from `start`; None before it
    run_hi: float | None

    @property
    def empty(self) -> bool:
        return self.run_lo is not None and self.run_lo > self.run_hi


def sequence(xs, alpha: float, t_star: float, start: int = 1) -> list[Step]:
    """Every step of the confidence sequence over `xs`, in order.

    `start` is the first `t` (1-indexed) that enters the running intersection.
    Steps before it carry their own interval and `run_lo = run_hi = None`.
    """
    if start < 1:
        raise ValueError("start must be at least 1")
    rho = rho_for(alpha, t_star)
    out: list[Step] = []
    s = s2 = 0.0
    run_lo = run_hi = None
    for t, x in enumerate(xs, start=1):
        x = float(x)
        if not math.isfinite(x):
            raise ValueError(f"observation {t} is not finite: {x}")
        s += x
        s2 += x * x
        mean = s / t
        var = max(s2 / t - mean * mean, 0.0)
        sd = math.sqrt(var)
        hw = half_width(t, sd, alpha, rho)
        lo, hi = mean - hw, mean + hw
        if t >= start:
            run_lo = lo if run_lo is None else max(run_lo, lo)
            run_hi = hi if run_hi is None else min(run_hi, hi)
        out.append(Step(t, mean, sd, lo, hi, run_lo, run_hi))
    return out


def interval_at(xs, t: int, alpha: float, t_star: float, start: int = 1) -> Step | None:
    """The step at count `t` (None when `xs` is shorter than `t` or `t` < 1)."""
    if t < 1:
        return None
    steps = sequence(list(xs)[:t], alpha, t_star, start)
    return steps[-1] if len(steps) == t else None
