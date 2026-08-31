"""Stage-1 statistics for a "does book state PREDICT forward drawdown" read.

Built for `hedge_concentration` ARM K, kept free of that study's constants: the
horizon H, the number of groups, the draw counts and every seed are parameters.
Nothing here knows what a session, a cluster or a hedge is — it sees two
parallel series, x (a state read at session s) and y (an outcome over the
sessions AFTER s), and answers whether the two are related in a way that
survives the fact that neighbouring y's overlap.

Four objects, in the order a study uses them:

  * `forward_drawdown(levels, h)` — for each index s, the MINIMUM of
    `levels[t] - levels[s]` over `s < t <= s + h`, capped at 0.0, or `None`
    when fewer than `h` sessions follow s. A full window is required: a
    partial one would make the last H sessions look systematically shallower.
  * `tercile_contrast(x, y)` / `spearman(x, y)` — the two reads. Terciles are
    assigned by RANK over EVERY x (ties broken by position, so the three groups
    differ in size by at most one); y may hold `None` where no window exists,
    and those rows are dropped from the means and the correlation but NOT from
    the tercile assignment, so "the top tercile" means the top third of the
    whole series, not of the usable part.
  * `block_bootstrap(x, y, stat_fn, block, ...)` — a CI from resampling
    NON-OVERLAPPING blocks of `block` consecutive rows with replacement. The
    forward windows overlap by construction, so a row-level resample would
    treat H nearly-identical outcomes as H independent ones and understate the
    variance; a block the length of the window keeps each outcome inside the
    block that generated it.
  * `circular_shift_null(x, y, stat_fn, min_shift, ...)` — the time-structure
    null. x is rotated against y by a random offset of at least `min_shift`
    rows in either direction; both series keep their own autocorrelation, which
    a shuffle would destroy. The 5th/95th percentiles of the rotated statistic
    are the band a real relationship must fall outside.

Every random draw takes an explicit seed, and every result carries it.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Callable, Sequence

Rows = Sequence[float | None]
StatFn = Callable[[Sequence[float], Rows], float]


# ════════════════════════════════════════════════════════════════════════════
# The outcome series
# ════════════════════════════════════════════════════════════════════════════

def forward_drawdown(levels: Sequence[float], h: int) -> list[float | None]:
    """y[s] = min(0, min_{s < t <= s+h} levels[t] - levels[s]); None if the
    window would run past the end of `levels`."""
    if h < 1:
        raise ValueError(f"horizon must be >= 1, got {h}")
    lv = [float(v) for v in levels]
    n = len(lv)
    out: list[float | None] = []
    for s in range(n):
        if s + h >= n:
            out.append(None)
            continue
        base = lv[s]
        worst = min(lv[t] - base for t in range(s + 1, s + h + 1))
        out.append(min(0.0, worst))
    return out


# ════════════════════════════════════════════════════════════════════════════
# The two reads
# ════════════════════════════════════════════════════════════════════════════

def rank_groups(x: Sequence[float], n_groups: int = 3) -> list[int]:
    """Group label 0..n_groups-1 for each x by rank, lowest x -> 0.

    Ties are broken by position (a stable sort), so group sizes differ by at
    most one however many values coincide. Assigned over EVERY x it is given.
    """
    if n_groups < 2:
        raise ValueError(f"n_groups must be >= 2, got {n_groups}")
    n = len(x)
    order = sorted(range(n), key=lambda i: (x[i], i))
    labels = [0] * n
    for rank, i in enumerate(order):
        labels[i] = min(n_groups - 1, rank * n_groups // n) if n else 0
    return labels


def _usable(x: Sequence[float], y: Rows) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for a, b in zip(x, y):
        if b is not None:
            xs.append(float(a))
            ys.append(float(b))
    return xs, ys


def group_counts(x: Sequence[float], y: Rows, n_groups: int = 3) -> list[int]:
    """Usable rows (y not None) per rank group — what a power gate counts."""
    labels = rank_groups(x, n_groups)
    counts = [0] * n_groups
    for lab, b in zip(labels, y):
        if b is not None:
            counts[lab] += 1
    return counts


def tercile_contrast(x: Sequence[float], y: Rows, n_groups: int = 3) -> float:
    """mean(y | top group) - mean(y | bottom group), groups by rank of x over
    ALL rows, means over the usable rows only. NaN if either group is empty."""
    labels = rank_groups(x, n_groups)
    top = [float(b) for lab, b in zip(labels, y)
           if b is not None and lab == n_groups - 1]
    bot = [float(b) for lab, b in zip(labels, y) if b is not None and lab == 0]
    if not top or not bot:
        return float("nan")
    return statistics.fmean(top) - statistics.fmean(bot)


def _avg_ranks(vals: Sequence[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Rows) -> float:
    """Spearman rank correlation over the usable rows (average ranks on ties).
    NaN with fewer than 3 usable rows or a constant series."""
    xs, ys = _usable(x, y)
    if len(xs) < 3:
        return float("nan")
    rx, ry = _avg_ranks(xs), _avg_ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if not dx or not dy:
        return float("nan")
    return num / (dx * dy)


def within_group_stats(x: Sequence[float], y: Rows, g: Sequence[float],
                       stat_fn: StatFn, n_groups: int = 3) -> list[float]:
    """`stat_fn(x, y)` re-read INSIDE each rank group of a third series `g`.

    The control read: if a relationship between x and y is really a
    relationship between g and y wearing x's clothes, it vanishes once g is
    held roughly constant. Returns one statistic per g-group, lowest g first.
    """
    labels = rank_groups(g, n_groups)
    out = []
    for grp in range(n_groups):
        xs = [a for a, lab in zip(x, labels) if lab == grp]
        ys = [b for b, lab in zip(y, labels) if lab == grp]
        out.append(stat_fn(xs, ys))
    return out


def sign_kept(values: Sequence[float], sign: float) -> int:
    """How many of `values` share the sign of `sign` (NaN never counts)."""
    if sign == 0 or sign != sign:
        return 0
    return sum(1 for v in values if v == v and (v < 0) == (sign < 0) and v != 0)


# ════════════════════════════════════════════════════════════════════════════
# Intervals and nulls
# ════════════════════════════════════════════════════════════════════════════

def pctile(vals: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile of the finite values; NaN if none."""
    s = sorted(v for v in vals if v == v)
    if not s:
        return float("nan")
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * (q / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


@dataclass(frozen=True)
class BootResult:
    point: float
    lo: float
    hi: float
    n_boot: int
    block: int
    n_blocks: int
    seed: int
    alpha: float

    @property
    def excludes_zero(self) -> bool:
        return (self.lo == self.lo and self.hi == self.hi
                and (self.hi < 0.0 or self.lo > 0.0))


def block_starts(n: int, block: int) -> list[int]:
    """Start index of every non-overlapping block of `block` rows over n rows;
    the last block may be short."""
    if block < 1:
        raise ValueError(f"block must be >= 1, got {block}")
    return list(range(0, n, block))


def resample_blocks(n: int, block: int, rng: random.Random) -> list[int]:
    """Row indices of one block-bootstrap resample: as many blocks as the
    series has, drawn WITH replacement, each kept in its original order."""
    starts = block_starts(n, block)
    out: list[int] = []
    for _ in starts:
        s = rng.choice(starts)
        out.extend(range(s, min(s + block, n)))
    return out


def block_bootstrap(x: Sequence[float], y: Rows, stat_fn: StatFn, block: int,
                    n_boot: int, seed: int, alpha: float = 0.05) -> BootResult:
    """Percentile CI of `stat_fn(x, y)` over `n_boot` block resamples."""
    if n_boot < 1:
        raise ValueError(f"n_boot must be >= 1, got {n_boot}")
    n = len(x)
    if len(y) != n:
        raise ValueError("x and y differ in length")
    point = stat_fn(x, y)
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(n_boot):
        idx = resample_blocks(n, block, rng)
        draws.append(stat_fn([x[i] for i in idx], [y[i] for i in idx]))
    return BootResult(point=point, lo=pctile(draws, 100 * alpha / 2),
                      hi=pctile(draws, 100 * (1 - alpha / 2)), n_boot=n_boot,
                      block=block, n_blocks=len(block_starts(n, block)),
                      seed=seed, alpha=alpha)


@dataclass(frozen=True)
class ShiftNull:
    point: float
    p05: float
    p95: float
    draws: int
    min_shift: int
    seed: int
    values: tuple[float, ...]

    def beats_low(self) -> bool:
        """The point is BELOW the null's 5th percentile (a negative effect
        that the time structure alone does not produce)."""
        return self.point == self.point and self.p05 == self.p05 and self.point < self.p05

    def beats_high(self) -> bool:
        return self.point == self.point and self.p95 == self.p95 and self.point > self.p95


def circular_shift(x: Sequence, k: int) -> list:
    """x rotated LEFT by k: element i of the result is x[(i + k) mod n]."""
    n = len(x)
    if not n:
        return []
    k %= n
    return list(x[k:]) + list(x[:k])


def circular_shift_null(x: Sequence[float], y: Rows, stat_fn: StatFn,
                        min_shift: int, draws: int, seed: int) -> ShiftNull:
    """`stat_fn` recomputed `draws` times with x rotated against y by a random
    offset k, `min_shift <= k <= n - min_shift`, so every rotation moves each
    x at least `min_shift` rows away from its own y in both directions."""
    n = len(x)
    if len(y) != n:
        raise ValueError("x and y differ in length")
    if draws < 1:
        raise ValueError(f"draws must be >= 1, got {draws}")
    if min_shift < 1 or n < 2 * min_shift + 1:
        raise ValueError(f"need n >= 2*min_shift+1 rows (n={n}, min_shift={min_shift})")
    point = stat_fn(x, y)
    rng = random.Random(seed)
    vals: list[float] = []
    for _ in range(draws):
        k = rng.randint(min_shift, n - min_shift)
        vals.append(stat_fn(circular_shift(x, k), y))
    return ShiftNull(point=point, p05=pctile(vals, 5), p95=pctile(vals, 95),
                     draws=draws, min_shift=min_shift, seed=seed,
                     values=tuple(vals))
