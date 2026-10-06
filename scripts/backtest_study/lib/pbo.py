"""Probability of Backtest Overfitting by Combinatorially Symmetric
Cross-Validation (CSCV). PURE: arrays in, a dataclass out, nothing printed.

Source: Bailey, Borwein, López de Prado and Zhu, "The Probability of Backtest
Overfitting", Journal of Computational Finance 20(4), 2017, 39-69 (SSRN
2326253; the revised working paper of February 2015 was checked line by line
against this module on 2026-10-06). Section, step and equation numbers below
are that paper's.

What it answers. N configurations were tried on one history and one was kept
because it scored best. PBO is the probability that the configuration a
selection rule keeps in-sample (IS) ranks below the median of the N
out-of-sample (OOS) — Definition 2.2, Eq. (2.2).

Algorithm 2.3 (CSCV), as implemented by `cscv()`:

  1. `M` is a T x N matrix of per-period performance, rows synchronous across
     columns (condition i). A metric that needs more than one number per period
     (meanR needs a sum and a count) passes a T x N x K array; the metric then
     receives the K channels of each row it is given.
  2. The T rows are cut into S even, contiguous, equal blocks of T/S rows.
     `cscv()` REFUSES a T that S does not divide: the paper's blocks are of
     equal dimension, and a caller decides how to get there (the study pads
     with zero-P&L sessions before the first trade, which are true).
  3. Every combination of S/2 blocks is formed: C(S, S/2) of them, Eq. (2.3).
     C(16, 8) = 12,870. The paper prints 12,780; that is a typo, and the count
     here is computed.
  4. For each combination c:
       a) the training set J joins its S/2 blocks IN THEIR ORIGINAL ORDER;
       b) the testing set J-bar is the complement, also in original order. The
          paper notes the order matters for a drawdown-type statistic, which
          is why a max drawdown can be computed on J at all: it is the
          drawdown of the joined rows, read in time order;
       c) R^c = metric(J), the IS statistic of every column;
       d) R-bar^c = metric(J-bar), the OOS statistic;
       e) n* = argmax R^c. TIES: the lowest column index (np.argmax). The paper
          leaves ties open;
       f) omega-bar_c = rank of R-bar^c_{n*} among R-bar^c, divided by (N + 1),
          so omega lies in (0, 1). Ranks are ASCENDING (1 = worst) and ties
          take their AVERAGE rank. A NaN statistic ranks worst;
       g) lambda_c = ln(omega-bar_c / (1 - omega-bar_c)).
  5. f(lambda) is the relative frequency of the lambda_c, Eq. (2.4).

§3.1: PBO = phi = integral of f over (-inf, 0], estimated as the share of
combinations with lambda_c <= 0. lambda = 0 is an OOS rank exactly at the
median; it counts as overfit here, and `PBOResult.n_at_zero` says how many.

§3.2: performance degradation is the OLS slope beta of R-bar_{n*} on R_{n*}
across combinations; beta < 0 is the paper's "compensation effect". The
probability of loss is the share of combinations with R-bar_{n*} < 0.
Both are computed on `report_metric` (default: the selection metric). A
caller whose selection metric has no natural zero, such as a drawdown or a
lexicographic rule, selects on one statistic and reports loss and
degradation on another; the result names both.

Not implemented: §3.3 stochastic dominance.

CSCV assumes the S blocks are exchangeable. It is deterministic: the
combinations are enumerated in `itertools.combinations` order and there is
no random draw (§4, "fourth").
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

Metric = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class PBOResult:
    """Everything `cscv()` computed. Arrays are indexed by combination."""

    n_rows: int
    n_configs: int
    S: int
    n_combinations: int
    pbo: float
    n_at_zero: int
    logits: np.ndarray          # lambda_c
    omega: np.ndarray           # omega-bar_c
    n_star: np.ndarray          # IS-best column per combination
    is_perf: np.ndarray         # report_metric(J)[n*]
    oos_perf: np.ndarray        # report_metric(J-bar)[n*]
    slope: float                # degradation beta
    intercept: float
    prob_loss: float | None
    is_rank: np.ndarray | None  # combinations x N, ascending average ranks
    oos_rank: np.ndarray | None

    def logit_quantiles(self, qs=(0.05, 0.25, 0.5, 0.75, 0.95)) -> dict:
        finite = self.logits[np.isfinite(self.logits)]
        return {q: float(np.quantile(finite, q)) for q in qs} if finite.size else {}

    def selection_share(self) -> np.ndarray:
        """Share of combinations in which each column is the IS best."""
        return np.bincount(self.n_star, minlength=self.n_configs) / self.n_combinations


def _validate(M: np.ndarray, S: int) -> np.ndarray:
    M = np.asarray(M, dtype=float)
    if M.ndim not in (2, 3):
        raise ValueError(f"M must be T x N or T x N x K, got shape {M.shape}")
    if not isinstance(S, (int, np.integer)) or S < 2 or S % 2:
        raise ValueError(f"S must be an even integer >= 2, got {S!r}")
    T, N = M.shape[0], M.shape[1]
    if N < 2:
        raise ValueError(f"need at least 2 configurations, got {N}")
    if T < S:
        raise ValueError(f"T={T} rows cannot form S={S} blocks")
    if T % S:
        raise ValueError(f"T={T} is not divisible by S={S}; the blocks must be "
                         f"equal (Algorithm 2.3, second step). Pad or trim first")
    if not np.all(np.isfinite(M)):
        raise ValueError("M holds a non-finite value")
    return M


def avg_rank(v: np.ndarray) -> np.ndarray:
    """Ascending ranks 1..N, ties averaged, NaN ranked worst."""
    v = np.where(np.isnan(v), -np.inf, v)
    less = (v[None, :] < v[:, None]).sum(axis=1)
    equal = (v[None, :] == v[:, None]).sum(axis=1)
    return less + (equal + 1) / 2.0


def cscv(M, S: int = 16, metric: Metric | None = None, *,
         report_metric: Metric | None = None,
         keep_ranks: bool = False) -> PBOResult:
    """Run Algorithm 2.3 on `M` and return the §3 statistics.

    `metric(sub)` maps a row subset (rows x N, or rows x N x K) to an N-vector
    of statistics, higher better. Default: the column sum of a 2-D `M`.
    """
    M = _validate(M, S)
    metric = metric or total_metric
    report_metric = report_metric or metric
    T, N = M.shape[0], M.shape[1]
    blocks = np.arange(T).reshape(S, T // S)
    combos = list(itertools.combinations(range(S), S // 2))
    C = len(combos)
    assert C == math.comb(S, S // 2)

    logits = np.empty(C)
    omega = np.empty(C)
    n_star = np.empty(C, dtype=int)
    is_perf = np.empty(C)
    oos_perf = np.empty(C)
    is_rank = np.empty((C, N)) if keep_ranks else None
    oos_rank = np.empty((C, N)) if keep_ranks else None
    for i, c in enumerate(combos):
        chosen = set(c)
        rows_is = blocks[list(c)].ravel()            # original order (4a)
        rows_oos = blocks[[s for s in range(S) if s not in chosen]].ravel()
        r_is = np.asarray(metric(M[rows_is]), dtype=float)
        r_oos = np.asarray(metric(M[rows_oos]), dtype=float)
        if r_is.shape != (N,) or r_oos.shape != (N,):
            raise ValueError(f"metric must return a length-{N} vector")
        best = int(np.argmax(np.where(np.isnan(r_is), -np.inf, r_is)))
        ranks_oos = avg_rank(r_oos)
        w = ranks_oos[best] / (N + 1)
        n_star[i] = best
        omega[i] = w
        logits[i] = math.log(w / (1 - w))
        if report_metric is metric:
            is_perf[i], oos_perf[i] = r_is[best], r_oos[best]
        else:
            is_perf[i] = report_metric(M[rows_is])[best]
            oos_perf[i] = report_metric(M[rows_oos])[best]
        if keep_ranks:
            is_rank[i] = avg_rank(r_is)
            oos_rank[i] = ranks_oos

    ok = np.isfinite(is_perf) & np.isfinite(oos_perf)
    if ok.sum() >= 2 and np.var(is_perf[ok]) > 0:
        slope, intercept = (float(x) for x in np.polyfit(is_perf[ok], oos_perf[ok], 1))
    else:
        slope = intercept = float("nan")
    loss = float(np.mean(oos_perf[ok] < 0)) if ok.any() else None
    return PBOResult(
        n_rows=T, n_configs=N, S=S, n_combinations=C,
        pbo=float(np.mean(logits <= 0)), n_at_zero=int(np.sum(logits == 0)),
        logits=logits, omega=omega, n_star=n_star, is_perf=is_perf,
        oos_perf=oos_perf, slope=slope, intercept=intercept, prob_loss=loss,
        is_rank=is_rank, oos_rank=oos_rank)


# ── metrics on a row subset ──────────────────────────────────────────────────
# Each takes rows x N (or rows x N x K; channel 0 is P&L) and returns N values.

def _pnl(sub: np.ndarray) -> np.ndarray:
    return sub[..., 0] if sub.ndim == 3 else sub


def total_metric(sub: np.ndarray) -> np.ndarray:
    """Sum of per-period P&L. Decomposes over blocks."""
    return _pnl(sub).sum(axis=0)


def max_drawdown(sub: np.ndarray) -> np.ndarray:
    """Max peak-to-trough fall of the cumulative P&L of the rows AS GIVEN,
    peak seeded at 0 (as `mtm_curve.max_drawdown`). Returned >= 0."""
    cum = np.cumsum(_pnl(sub), axis=0)
    cum = np.vstack([np.zeros((1, cum.shape[1])), cum])
    return (np.maximum.accumulate(cum, axis=0) - cum).max(axis=0)


def neg_drawdown_metric(sub: np.ndarray) -> np.ndarray:
    """-max drawdown: the shallower drawdown ranks higher."""
    return -max_drawdown(sub)


def ratio_metric(sub: np.ndarray) -> np.ndarray:
    """Channel 0 summed over channel 1 summed (e.g. sum R / positions).
    NaN where the count is zero, which ranks worst."""
    num = sub[..., 0].sum(axis=0)
    den = sub[..., 1].sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)


def pad_head(M: np.ndarray, S: int) -> tuple[np.ndarray, int]:
    """Prepend zero rows so S divides T. Returns (padded, rows added).

    Correct only where a zero row is TRUE: periods before any configuration
    traded, when every account held cash and earned nothing.
    """
    M = np.asarray(M, dtype=float)
    k = (-M.shape[0]) % S
    if not k:
        return M, 0
    pad = np.zeros((k,) + M.shape[1:])
    return np.concatenate([pad, M], axis=0), k
