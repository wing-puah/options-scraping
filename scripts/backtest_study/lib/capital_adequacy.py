"""Outcome-blind capital-adequacy census — step 0c of
`research/account-sim-feasibility-plan.md`.

Answers ONE question: "what capital does this book need", by looking only at
the per-play one-contract MAX LOSS of every play the ladder EMITTED (real +
tweak rows from `lib/book.py::load_book`, before `top_k_per_day`/`ordered_by_day`
narrow it to what a day's ranked walk would pick, and long before
`account_sim.simulate()` decides what it actually took). It never reads a P&L
column, an exit reason, or which plays the walk took — that is what makes it
outcome-blind, and it is a DISCLOSURE, never a criterion: nothing here is a
pre-registered gate and nothing here may be adopted on P&L.

Pure module: every function takes plain sequences and returns plain
dataclasses. No file I/O, no `load_book` import, no printing — `account_sim.py`
(owned by another agent) wires this to the real book and prints
`format_block()`'s lines itself.

The fit test — `cost <= budget + EPS` — mirrors
`scripts/backtest_study/f4_deployment/account_sim.py`'s own EPS-tolerant
boundary convention (`admission()`, lines ~517-521: `... > cfg.per_pos_cap *
eq + EPS` fails, so `<= budget + EPS` is what passes) and its own `EPS = 1e-9`.
`risk_contracts()` in that module (`max(1, int(budget / max_loss))`) is
consistent with the same convention: a cost exactly equal to the budget still
returns >=1 contract, i.e. it fits.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

# Same value as account_sim.py's own EPS — see module docstring.
EPS = 1e-9


@dataclass(frozen=True)
class CostStats:
    """One population's per-contract cost distribution, in dollars."""
    n: int
    min: float
    q1: float
    median: float
    q3: float
    p90: float
    max: float


@dataclass(frozen=True)
class CostCensus:
    """`cost_census()`'s return value.

    `n_total` is every cost handed in, including excluded ones. `overall` is
    `None` only when there is not a single usable cost. `by_group` /
    `excluded_by_group` are `None` unless `groups` was passed to
    `cost_census()`; a group with no usable cost still appears in both, with
    `by_group[g] is None`.
    """
    n_total: int
    n_excluded: int
    overall: Optional[CostStats]
    by_group: Optional[Mapping[str, Optional[CostStats]]]
    excluded_by_group: Optional[Mapping[str, int]]


@dataclass(frozen=True)
class LadderRung:
    """One capital's row on the adequacy curve."""
    capital: float
    budget: float
    n_fit: int
    share: Optional[float]      # None only when there is no usable cost at all


@dataclass(frozen=True)
class AdequacyCurve:
    """`adequacy_curve()`'s return value.

    `share`/`n_fit` in `ladder` and every value in `smallest_capital_for_target`
    / `exact_capital_for_target` are computed against `n_usable`
    (`n_total - n_excluded`), never against `n_total` — an excluded play has no
    known cost, so it can neither be said to fit nor to not fit a budget; it is
    disclosed via `n_excluded`, not folded into the share's denominator.
    """
    risk_pct: float
    n_total: int
    n_usable: int
    n_excluded: int
    ladder: Sequence[LadderRung]
    smallest_capital_for_target: Mapping[float, Optional[float]]
    exact_capital_for_target: Mapping[float, Optional[float]]
    #: The share ACTUALLY reached at `exact_capital_for_target[t]`, i.e.
    #: `n_fit(that capital) / n_usable`. Always `>= t` (ties can push it
    #: above), and printed beside the capital so the claim "90% share" is
    #: checkable rather than taken on trust — an interpolated quantile used to
    #: land one play short of it.
    exact_share_for_target: Mapping[float, Optional[float]]


def _usable(cost) -> bool:
    """A cost counts iff it is not None and strictly positive — never treat
    None as 0, and never treat a non-positive figure as a real cost."""
    return cost is not None and cost > 0


def _quantile(sorted_vals: Sequence[float], p: float) -> float:
    """Linear-interpolation quantile (numpy's default "linear" method) over an
    already-sorted, non-empty sequence. `p` in [0, 1]."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    idx = p * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def _stats(costs: Sequence[float]) -> Optional[CostStats]:
    if not costs:
        return None
    s = sorted(costs)
    return CostStats(
        n=len(s), min=s[0], q1=_quantile(s, 0.25), median=_quantile(s, 0.5),
        q3=_quantile(s, 0.75), p90=_quantile(s, 0.90), max=s[-1])


def cost_census(costs: Sequence[Optional[float]],
                groups: Optional[Sequence[Optional[str]]] = None) -> CostCensus:
    """Per-contract cost census over `costs` (one `max_loss_per_contract` per
    emitted play), optionally split by a caller-supplied `groups` label
    (e.g. `structure`) of the same length.

    A `None` or non-positive cost is EXCLUDED from every statistic and COUNTED
    in `n_excluded` (overall) / `excluded_by_group[g]` (per group) — it is
    never treated as a zero cost.
    """
    if groups is not None and len(groups) != len(costs):
        raise ValueError("groups must be the same length as costs")

    usable = [c for c in costs if _usable(c)]
    n_excluded = len(costs) - len(usable)
    overall = _stats(usable)

    by_group = None
    excluded_by_group = None
    if groups is not None:
        buckets: dict = defaultdict(list)
        exc: dict = defaultdict(int)
        for c, g in zip(costs, groups):
            if _usable(c):
                buckets[g].append(c)
            else:
                exc[g] += 1
        labels = sorted(set(buckets) | set(exc), key=lambda x: (x is None, x))
        by_group = {g: _stats(buckets.get(g, [])) for g in labels}
        excluded_by_group = {g: exc.get(g, 0) for g in labels}

    return CostCensus(n_total=len(costs), n_excluded=n_excluded, overall=overall,
                      by_group=by_group, excluded_by_group=excluded_by_group)


def adequacy_curve(costs: Sequence[Optional[float]], capitals: Sequence[float],
                   risk_pct: float,
                   target_shares: Sequence[float] = ()) -> AdequacyCurve:
    """For each capital in `capitals` (a caller-supplied ladder, any order —
    the returned `ladder` preserves that order), the share of USABLE plays
    whose one contract fits `capital * risk_pct` (the fit test, `cost <=
    budget + EPS`, mirrors `account_sim.py`'s boundary convention — see the
    module docstring).

    `target_shares` (e.g. `(0.5, 0.75, 0.9)`) drives two lookups, both `None`
    when there is no usable cost at all (or, for the ladder lookup, when no
    rung in `capitals` reaches the target):

      * `smallest_capital_for_target[t]` — the smallest value in `capitals`
        (searched in ascending order regardless of the order `capitals` was
        given in) at which the share is `>= t`.
      * `exact_capital_for_target[t]` — the SMALLEST capital at which the share
        actually reaches `t`, with no dependence on `capitals` at all: the
        `ceil(t * n)`-th smallest usable cost (a plain order statistic,
        1-indexed), divided by `risk_pct`. At that capital the budget covers
        that cost and every cost below it, i.e. at least `ceil(t * n)` of `n`
        plays, so the achieved share is `>= t`; and no smaller usable cost's
        capital reaches `t`, because a budget below it covers fewer than
        `ceil(t * n)` plays. `exact_share_for_target[t]` records what it
        actually reached.

        NOT an interpolated quantile. `_quantile` interpolates BETWEEN two
        order statistics, and whenever `t * (n - 1)` is non-integral the
        interpolated value sits below the cost of the play that would take the
        share over the line — so the "exact capital for a 90% share" bought
        89.9% instead (444 plays, t=0.9: 399 of 444). The interpolated
        quantile is still right for the DESCRIPTIVE census above; it is wrong
        as a capital requirement.
    """
    if risk_pct <= 0:
        raise ValueError("risk_pct must be positive")

    usable_costs = sorted(c for c in costs if _usable(c))
    n_total = len(costs)
    n_usable = len(usable_costs)
    n_excluded = n_total - n_usable

    def n_fit_at(capital: float) -> int:
        budget = capital * risk_pct
        return sum(1 for c in usable_costs if c <= budget + EPS)

    ladder = []
    for cap in capitals:
        budget = cap * risk_pct
        if n_usable == 0:
            ladder.append(LadderRung(capital=cap, budget=budget, n_fit=0, share=None))
            continue
        n_fit = n_fit_at(cap)
        ladder.append(LadderRung(capital=cap, budget=budget, n_fit=n_fit,
                                 share=n_fit / n_usable))

    smallest_capital_for_target = {}
    for t in target_shares:
        found = None
        if n_usable > 0:
            for cap in sorted(capitals):
                if n_fit_at(cap) / n_usable >= t - EPS:
                    found = cap
                    break
        smallest_capital_for_target[t] = found

    exact_capital_for_target = {}
    exact_share_for_target = {}
    for t in target_shares:
        if n_usable == 0:
            exact_capital_for_target[t] = None
            exact_share_for_target[t] = None
            continue
        # The ceil-index ORDER STATISTIC, 1-indexed and clamped into range: the
        # cheapest cost that leaves at least ceil(t*n) plays at or below it.
        k = min(n_usable - 1, max(0, math.ceil(t * n_usable) - 1))
        cap = usable_costs[k] / risk_pct
        exact_capital_for_target[t] = cap
        exact_share_for_target[t] = n_fit_at(cap) / n_usable

    return AdequacyCurve(risk_pct=risk_pct, n_total=n_total, n_usable=n_usable,
                         n_excluded=n_excluded, ladder=ladder,
                         smallest_capital_for_target=smallest_capital_for_target,
                         exact_capital_for_target=exact_capital_for_target,
                         exact_share_for_target=exact_share_for_target)


def _hdr_lines(title: str) -> list:
    # 78, the width `account_sim.hdr()` writes and the width
    # `scripts/study_charts/report.py::BANNER` splits sections on. A wider bar
    # still parses (the check is a prefix match) but prints a block that does
    # not line up with any other section of the report it is printed into.
    bar = "=" * 78
    return ["", bar, title, bar]


# The leading sentence when the caller does not supply one. It states the
# MEASURE and nothing about which plays were handed in — the caller knows its
# own population and says so through `population_note`, because one fixed
# sentence printed over two different cuts made the block contradict itself
# ("before ranking or sizing" above a set that IS the ranked candidate list).
DEFAULT_POPULATION_NOTE = (
    "  Each play's one-contract max loss. Answers only\n"
    "  \"what capital would this book need\" — see "
    "research/account-sim-feasibility-plan.md step 0c.")


def format_block(census: CostCensus, curve: AdequacyCurve, *, label: str = "",
                 population_note: str = DEFAULT_POPULATION_NOTE,
                 notes: Sequence[str] = ()) -> list:
    """The printable lines for this block, in the visual style of
    `account_sim.py`'s `print_granularity`/`print_capital_ladder` (a banner
    via `hdr()`, then aligned, indented columns). The caller prints them
    (e.g. `print("\\n".join(format_block(...)))`) — this module does no I/O.

    `population_note` is the leading sentence: WHICH plays these are, in the
    caller's own words, since this module is handed costs and cannot know.
    `notes` are extra lines printed straight after the count line — what a
    caller states about its DENOMINATOR (rows a loader dropped before the
    costs got here, say) belongs there, next to the count it qualifies.
    """
    prefix = f"[{label}] " if label else ""
    lines = _hdr_lines(
        f"{prefix}CAPITAL ADEQUACY — outcome-blind capital census, "
        f"a DISCLOSURE, not a criterion")
    lines.append(population_note)
    n_usable = census.n_total - census.n_excluded
    lines.append(
        f"  plays {census.n_total}   with usable max_loss {n_usable}   "
        f"unsizable {census.n_excluded}")
    lines.extend(notes)
    if census.overall is None:
        lines.append("  no play carries a usable max_loss — no cost census to report.")
    else:
        o = census.overall
        lines.append(
            f"  cost census ($/contract): n={o.n}  min ${o.min:,.0f}  Q1 ${o.q1:,.0f}  "
            f"median ${o.median:,.0f}  Q3 ${o.q3:,.0f}  p90 ${o.p90:,.0f}  max ${o.max:,.0f}")
    if census.by_group:
        lines.append("  by group:")
        for g, stats in census.by_group.items():
            exc = (census.excluded_by_group or {}).get(g, 0)
            label_g = "(none)" if g is None else str(g)
            if stats is None:
                lines.append(f"    {label_g:<28} n=0     unsizable {exc}")
            else:
                lines.append(
                    f"    {label_g:<28} n={stats.n:<4}  unsizable {exc:<4}  "
                    f"min ${stats.min:,.0f}  median ${stats.median:,.0f}  "
                    f"p90 ${stats.p90:,.0f}  max ${stats.max:,.0f}")
    lines.append("")
    lines.append(
        f"  CAPITAL-ADEQUACY CURVE at {curve.risk_pct:.0%} risk per position   "
        f"(fit test: cost <= budget + {EPS:g}, mirrors account_sim.py's "
        f"admission() boundary)")
    for rung in curve.ladder:
        share_txt = "n/a" if rung.share is None else f"{rung.share:>5.0%}"
        lines.append(
            f"    ${rung.capital:>10,.0f}  budget ${rung.budget:>9,.0f}  "
            f"fits {share_txt}  ({rung.n_fit}/{curve.n_usable})")
    for t in sorted(curve.smallest_capital_for_target):
        cap = curve.smallest_capital_for_target[t]
        cap_txt = f"${cap:,.0f}" if cap is not None else "none of the ladder"
        lines.append(f"    smallest ladder capital reaching {t:.0%} share: {cap_txt}")
    for t in sorted(curve.exact_capital_for_target):
        cap = curve.exact_capital_for_target[t]
        share = curve.exact_share_for_target.get(t)
        if cap is None:
            lines.append(f"    smallest capital reaching a {t:.0%} share: "
                         f"n/a (no usable plays)")
            continue
        # The achieved share is printed because it is the claim: it must be at
        # or above the target, and ties can carry it above.
        n_fit = int(round(share * curve.n_usable))
        lines.append(
            f"    smallest capital reaching a {t:.0%} share: ${cap:,.0f}  "
            f"(reaches {share:.1%}, {n_fit}/{curve.n_usable})")
    return lines
