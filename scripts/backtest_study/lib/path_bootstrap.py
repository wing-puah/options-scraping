"""Path bootstrap for `account_sim`'s A3 max drawdown — measures the noise in
ONE realized number, licenses no decision.

`account_sim.py::a3_no_blowup` reads a single max drawdown off a single path:
`equity_curve(sim.signal_pos)` books each position's dollar P&L on its EXIT
session (`session -> sum of dollars that session`), and
`mtm_curve.max_drawdown` walks the CUMULATIVE SUM of that per-session series
with the running peak seeded at 0.0 (never at starting capital). A3 then
divides the dollar result by `sim.cfg.capital` — the account's STARTING
capital, never the path's own peak equity — to get the percentage the report
prints. This module mirrors both pieces exactly:

  * `max_drawdown` is a re-export of `mtm_curve.max_drawdown`, the SAME
    function object A3 calls (like `hedge_criteria.py` and `hedge_timing.py`
    already re-export it) — not a second implementation that could drift.
  * `max_drawdown_fraction(pnl, capital)` is `abs(max_drawdown(pnl)) /
    capital`, the same starting-capital denominator A3 and `print_equity`
    use.

Resampling is a MOVING/CIRCULAR block bootstrap (Politis and Romano 1992):
each block's start is drawn uniformly over every row in the series (not a
fixed grid), and a block that runs past the end wraps back to row 0.
`lib/forward_drawdown.py` already has a block bootstrap
(`block_bootstrap`/`resample_blocks`), but it resamples PAIRED (x, y) rows
from a FIXED grid of non-overlapping block starts — built to CI a
state-vs-outcome statistic, not to rebuild an ordered P&L path. It is
deliberately not reused or bent here for the resampling itself; only its
generic `pctile` helper is (a plain percentile of a list of floats, with no
opinion about what produced them).

Degenerate case, pinned by `test_path_bootstrap.py`: a block length >= the
series length is CLAMPED to the series length, and the one resulting block is
taken deterministically at row 0 — NOT drawn circularly. That is what makes
"block length == n" reproduce the realized path, and its drawdown, exactly;
it is the module's own sanity check, not an edge case bolted on afterwards.

An empty P&L series is refused (`ValueError`): there is no realized drawdown
to measure noise around, and a silently-returned 0.0 would read as "no risk"
rather than "no data".

Caveats this module's own report lines carry (see `format_block`), and that
any caller printing these numbers elsewhere must keep:

  (a) the resample holds each session's dollar P&L AS REALIZED — sizing, cap
      refusals and the dollar stop are NOT re-simulated, so a resampled path
      could not have happened under this account's rules; it is a
      reordering of what did happen, not a new simulation.
  (b) a single max drawdown is a noisy order statistic (Magdon-Ismail, Atiya,
      Pratap, Abu-Mostafa, 2004) — this block measures that noise.
  (c) NO DECISION RULE: a wide band never licenses a pass. 25% (or any other
      figure) is the operator's own tolerance, not an estimate this module
      produces.

Nothing here prints or returns an annualised figure, a Sharpe ratio, or a
time-to-recover — those are out of scope by design, not oversight.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from scripts.backtest_study.lib.forward_drawdown import pctile
from scripts.backtest_study.lib.mtm_curve import max_drawdown  # noqa: F401  (re-export; SAME function A3 uses)

DEFAULT_BLOCKS: tuple[int, ...] = (5, 10, 20)


# ════════════════════════════════════════════════════════════════════════════
# The A3 measure, mirrored exactly
# ════════════════════════════════════════════════════════════════════════════

def max_drawdown_fraction(pnl: Sequence[float], capital: float) -> float:
    """abs(max_drawdown(pnl)) / capital — A3's own percentage basis.

    `capital` is the account's STARTING capital (`sim.cfg.capital`), a fixed
    constant, never the path's peak equity — A3 and `print_equity` both
    divide by it directly. The return is a non-negative fraction (0.35 ==
    35%), 0.0 for a path that never falls below its starting level.
    """
    if capital is None or capital <= 0:
        raise ValueError(f"capital must be positive, got {capital!r}")
    return abs(max_drawdown(pnl)) / capital


# ════════════════════════════════════════════════════════════════════════════
# Resampling
# ════════════════════════════════════════════════════════════════════════════

def _resample_indices(n: int, block: int, rng: random.Random) -> list[int]:
    """One moving/circular block-bootstrap resample's row order.

    Blocks are drawn WITH replacement, each start uniform over every row
    (0..n-1), wrapping past the end back to row 0, until at least `n` indices
    are collected; the result is truncated to exactly `n`.

    `block` is CLAMPED to `n`. When the clamp makes `block == n` there is
    only one possible block, and it is taken deterministically at row 0 (no
    wraparound) — the identity ordering, not a random rotation. That is the
    degenerate case the module's sanity test pins.
    """
    if n == 0:
        return []
    b = min(block, n)
    if b >= n:
        return list(range(n))
    idx: list[int] = []
    while len(idx) < n:
        start = rng.randrange(n)
        idx.extend((start + k) % n for k in range(b))
    return idx[:n]


# ════════════════════════════════════════════════════════════════════════════
# The distribution
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DrawdownBand:
    """One block length's resampled max-drawdown distribution.

    `p5`..`p95` and `realized_fraction` are FRACTIONS of `capital` (0.35 ==
    35%) — the same basis A3 reports on, never dollars and never a peak-
    equity percentage. `reference_shares[label]` is
    `(at_or_below, above)`: the share of the `n_resamples` resampled paths
    whose drawdown fraction is <= that reference depth, and the share
    strictly deeper than it. The two always sum to 1.0.

    `block` is the block length the caller asked for; `block_effective` is
    what actually ran after the >= n clamp (see `_resample_indices`).
    """
    block: int
    block_effective: int
    n_resamples: int
    seed: int
    n_sessions: int
    realized_fraction: float
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    reference_shares: dict[str, tuple[float, float]] = field(default_factory=dict)


def bootstrap_drawdown(pnl: Sequence[float], capital: float, block: int,
                       n_resamples: int, seed: int,
                       reference_depths: Mapping[str, float] | None = None,
                       ) -> DrawdownBand:
    """Block-bootstrap `pnl` (the per-exit-session dollar P&L series, ordered,
    zeros included for a no-exit session if that is what the caller's
    `session_series`/`equity_curve` yielded) and summarize the resampled max
    drawdown's distribution, on the SAME fraction-of-starting-capital basis
    A3 uses.

    `reference_depths` names depths (fractions, e.g. `{"realized": 0.350,
    "25% bar": 0.25}`) to score the resampled paths against; each key becomes
    a `reference_shares` entry. Omit it for the percentile summary alone.
    """
    pnl = [float(v) for v in pnl]
    n = len(pnl)
    if n == 0:
        raise ValueError(
            "bootstrap_drawdown needs a non-empty P&L series — an empty "
            "book has no realized drawdown to measure noise around")
    if block < 1:
        raise ValueError(f"block must be >= 1, got {block}")
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1, got {n_resamples}")
    if capital is None or capital <= 0:
        raise ValueError(f"capital must be positive, got {capital!r}")

    realized_fraction = max_drawdown_fraction(pnl, capital)
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(n_resamples):
        idx = _resample_indices(n, block, rng)
        path = [pnl[i] for i in idx]
        draws.append(max_drawdown_fraction(path, capital))

    shares: dict[str, tuple[float, float]] = {}
    for label, depth in (reference_depths or {}).items():
        at_or_below = sum(1 for d in draws if d <= depth) / n_resamples
        shares[label] = (at_or_below, 1.0 - at_or_below)

    return DrawdownBand(
        block=block, block_effective=min(block, n), n_resamples=n_resamples,
        seed=seed, n_sessions=n, realized_fraction=realized_fraction,
        p5=pctile(draws, 5), p25=pctile(draws, 25), p50=pctile(draws, 50),
        p75=pctile(draws, 75), p95=pctile(draws, 95),
        reference_shares=shares)


def bootstrap_drawdown_blocks(pnl: Sequence[float], capital: float,
                              n_resamples: int, seed: int,
                              blocks: Sequence[int] = DEFAULT_BLOCKS,
                              reference_depths: Mapping[str, float] | None = None,
                              ) -> dict[int, DrawdownBand]:
    """Convenience wrapper: `bootstrap_drawdown` at every block length in
    `blocks` (default 5, 10, 20), same `pnl`/`capital`/`n_resamples`/`seed`
    for each — one RNG stream per block length, seeded identically, so the
    block lengths are directly comparable and the whole run is reproducible
    from the one seed printed."""
    return {b: bootstrap_drawdown(pnl, capital, b, n_resamples, seed,
                                  reference_depths=reference_depths)
            for b in blocks}


# ════════════════════════════════════════════════════════════════════════════
# Report lines (account_sim report style — caller prints them, this module
# never writes to stdout itself)
# ════════════════════════════════════════════════════════════════════════════

def format_block(bands: Mapping[int, DrawdownBand], label: str = "") -> list[str]:
    """Printable lines, account_sim report style. Prints the seed, the
    resample count, the block lengths, the percentile band and any
    reference-depth shares per block length, and the three caveats verbatim
    in substance: sizing/caps/stop are not re-simulated, a single max
    drawdown is a noisy order statistic, and this is not a decision rule.

    Never prints an annualised figure, a Sharpe ratio, or a time-to-recover.
    """
    lines: list[str] = []
    if not bands:
        lines.append("  path bootstrap — no block lengths run.")
        return lines
    first = next(iter(bands.values()))
    tag = f" [{label}]" if label else ""
    lines.append(
        f"  path bootstrap{tag} — seed {first.seed}, {first.n_resamples} "
        f"resamples, block lengths {', '.join(str(b) for b in bands)} "
        f"({first.n_sessions} exit sessions)")
    lines.append(f"  {'block':>6} {'realized':>9} {'p5':>7} {'p25':>7} "
                 f"{'p50':>7} {'p75':>7} {'p95':>7}")
    for b, band in bands.items():
        note = "" if band.block_effective == band.block else \
            f"  (clamped to {band.block_effective})"
        lines.append(
            f"  {b:>6} {band.realized_fraction:>8.1%} {band.p5:>6.1%} "
            f"{band.p25:>6.1%} {band.p50:>6.1%} {band.p75:>6.1%} "
            f"{band.p95:>6.1%}{note}")
    any_refs = any(band.reference_shares for band in bands.values())
    if any_refs:
        lines.append("  share of resampled paths at-or-below / above each "
                     "reference depth:")
        for b, band in bands.items():
            for ref_label, (at_or_below, above) in band.reference_shares.items():
                # ROUNDED ONCE: the pair partitions the resamples, so it has to
                # read as a partition. Formatting both halves independently
                # printed 82.0% / 18.1% off one split, which invites a reader
                # to look for the missing 0.1% of paths.
                below_pct = round(at_or_below * 100.0, 1)
                lines.append(
                    f"    block {b:>3}  {ref_label:<14} "
                    f"at-or-below {below_pct:>5.1f}%  "
                    f"above {round(100.0 - below_pct, 1):>5.1f}%")
    lines.append("")
    lines.append(
        "  (a) the resample holds each session's dollar P&L AS REALIZED — "
        "sizing, cap refusals and the dollar stop are NOT re-simulated.")
    lines.append(
        "  (b) a single max drawdown is a noisy order statistic "
        "(Magdon-Ismail, Atiya, Pratap, Abu-Mostafa 2004) — this block "
        "measures that noise, nothing more.")
    lines.append(
        "  (c) NO DECISION RULE: a wide band never licenses a pass. 25% is "
        "the operator's own tolerance, not an estimate.")
    return lines
