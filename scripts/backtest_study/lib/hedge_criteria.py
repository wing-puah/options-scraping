"""The hedge programme's shared criteria: contribution, sizing, drawdown.

--- Why this module exists ---------------------------------------------------
The hedge question is asked by six study modules across `f3_structure/` and
`f4_deployment/`, and until 2026-09-07 each carried its own body of the same
two rules. `research/hedge-programme-plan.md` §"The shared criteria library"
counts them: the contribution rule six times, the sizing rule four, the
drawdown function three. None of the copies was tested against the others, and
two of them say in their own docstrings that they were copied rather than
imported so that a change elsewhere could not move their recorded numbers.

That is a commitment about NUMBERS, not about intent, so this module is the
copies' origin transcribed rather than re-derived. **The reference is
`f4_deployment/bear_deploy.py`** — `D2` at its `daily_series`/`d2_hedge` and
`D3` at its `_sleeve_dollars`/`_sweep`/`_verdict`/`d3_sizing` — because it is
the origin the other modules name. Every threshold, tie-break and comparison
below is that module's, moved without an "improvement": the `max(3, n // 10)`
decile floor, the `max(2, n // 4)` per-year tail, the six-date minimum before a
year is evaluated, the `1e-9` slack on both sizing comparisons, and `max()`'s
first-wins tie-break on both the sleeve picker and the least-harmful size.

--- What is NOT here ---------------------------------------------------------
**No printing.** Each study keeps its own printed shape, because each report's
layout is quoted verbatim in `research/study-results/` and a merged format
would silently rewrite what those records mean. The functions here return the
figures; the study prints them.

**No grid.** A study that narrows its fraction grid is making a registered
choice (`bear_deploy` D3 sweeps four fractions, `hedge_timing` ARM H4 two), so
the grid is a parameter and never a default.

**No second drawdown body.** `max_drawdown` is imported from `lib/mtm_curve.py`
and re-exported here, so a caller reaching for it through this module gets the
SAME function object — which is what `tests/test_mtm_curve.py` pins.

Pinned by `tests/test_hedge_criteria.py` against the committed fixture
`tests/fixtures/hedge_criteria.csv`, the way `lib/harness.py` is pinned by
`tests/test_harness_replay.py`.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from scripts.backtest_study.lib.mtm_curve import max_drawdown  # noqa: F401  (re-export)

# ── the criteria's constants, all of them bear_deploy's ──────────────────────

#: A cell below this many overlapping dates is not evaluated at all.
MIN_COMMON_DATES = 20
#: A year below this many overlapping dates is reported but not counted.
MIN_YEAR_DATES = 6
#: Worst-decile cut: `max(DECILE_MIN, n // 10)`.
DECILE_MIN = 3
#: Worst-quartile cut: `max(QUARTILE_MIN, n // 4)`.
QUARTILE_MIN = 3
#: Per-year worst-quartile cut: `max(YEAR_TAIL_MIN, n // 4)`.
YEAR_TAIL_MIN = 2
#: The contribution rule needs the tail positive in at least this many years.
MIN_TAIL_YEARS = 2
#: Slack on the two sizing comparisons, so an exactly-equal path still counts.
EPS = 1e-9


def _fmean(vals):
    """Mean of the non-None values, `nan` on an empty cut.

    The `nan` is load-bearing: every comparison against it is False, so a cut
    with nothing in it FAILS the rule rather than passing it vacuously.
    """
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else float("nan")


# ════════════════════════════════════════════════════════════════════════════
# The daily series both criteria read
# ════════════════════════════════════════════════════════════════════════════

def daily_series(rows, r_key, dol_key, date_key="date"):
    """date -> (mean return, total dollars, n) for a sleeve.

    A row missing `r_key` is not in the series at all; a row missing `dol_key`
    is in it but contributes no dollars. Keys are parameters because the
    studies name the same two quantities differently (`R`/`R_dol` for the
    deployed book, `Rb`/`Rb_dol` for the bear sleeve).
    """
    by = defaultdict(list)
    for r in rows:
        if r.get(r_key) is not None:
            by[str(r[date_key])].append(r)
    return {d: (_fmean([x[r_key] for x in rs]),
                sum(x[dol_key] for x in rs if x.get(dol_key) is not None),
                len(rs))
            for d, rs in by.items()}


def common_dates(dep, bear) -> list[str]:
    """The dates both sleeves are on, in date order."""
    return sorted(set(dep) & set(bear))


# ════════════════════════════════════════════════════════════════════════════
# The hedge-contribution criterion (bear_deploy D2)
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Bucket:
    """One outcome cut of the deployed book's dates, and what bear did on it."""
    name: str
    dates: list[str]
    dep_r: float
    bear_r: float
    bear_dollars: float
    bear_win_rate: float


@dataclass(frozen=True)
class YearTail:
    """One year's worst-quartile dates. `evaluated` False = too few dates."""
    year: str
    n_overlap: int
    evaluated: bool
    tail_dates: list[str] = field(default_factory=list)
    dep_r: float = float("nan")
    bear_r: float = float("nan")
    bear_dollars: float = 0.0


@dataclass(frozen=True)
class HedgeContribution:
    """The contribution criterion's figures. `met` is the pre-registered rule."""
    common: list[str]
    corr: float
    buckets: list[Bucket]
    tail: Bucket | None
    tail_r: float
    years: list[YearTail]
    ok_years: int
    tot_years: int
    met: bool


def _bucket(name, dates, dep, bear) -> Bucket:
    return Bucket(
        name=name,
        dates=list(dates),
        dep_r=_fmean([dep[d][0] for d in dates]),
        bear_r=_fmean([bear[d][0] for d in dates]),
        bear_dollars=sum(bear[d][1] for d in dates),
        bear_win_rate=sum(1 for d in dates if bear[d][0] > 0) / len(dates),
    )


def hedge_contribution(dep, bear, min_common: int = MIN_COMMON_DATES
                       ) -> HedgeContribution | None:
    """What the hedge sleeve does on the deployed book's LOSING dates.

    Returns None when the overlap is below `min_common` — the cell is under the
    power floor and nothing is concluded from it. Otherwise the date-level
    correlation of the two sleeves, the outcome buckets (EMPTY buckets are
    dropped, never reported as a zero), the per-year worst-quartile tails, and
    `met`: the tail positive AND the correlation negative AND the tail positive
    in at least `MIN_TAIL_YEARS` evaluable years. An undefined tail is `nan`,
    which is not `> 0`, so the rule fails closed.
    """
    common = common_dates(dep, bear)
    if len(common) < min_common:
        return None

    dep_r = [dep[d][0] for d in common]
    bear_r = [bear[d][0] for d in common]
    corr = (statistics.correlation(dep_r, bear_r) if len(common) > 2
            else float("nan"))

    order = sorted(common, key=lambda d: dep[d][0])
    n_dec = max(DECILE_MIN, len(common) // 10)
    cuts = [("worst decile", order[:n_dec]),
            ("worst quartile", order[:max(QUARTILE_MIN, len(common) // 4)]),
            ("negative dates", [d for d in order if dep[d][0] < 0]),
            ("positive dates", [d for d in order if dep[d][0] >= 0]),
            ("ALL", order)]
    buckets = [_bucket(name, ds, dep, bear) for name, ds in cuts if ds]
    tail = next((b for b in buckets if b.name == "worst decile"), None)
    tail_r = tail.bear_r if tail else float("nan")

    years, ok_years, tot_years = [], 0, 0
    for y in sorted({d[:4] for d in common}):
        ys = [d for d in common if d[:4] == y]
        if len(ys) < MIN_YEAR_DATES:
            years.append(YearTail(year=y, n_overlap=len(ys), evaluated=False))
            continue
        yorder = sorted(ys, key=lambda d: dep[d][0])
        ytail = yorder[:max(YEAR_TAIL_MIN, len(ys) // 4)]
        b_r = _fmean([bear[d][0] for d in ytail])
        tot_years += 1
        ok_years += 1 if b_r > 0 else 0
        years.append(YearTail(year=y, n_overlap=len(ys), evaluated=True,
                              tail_dates=list(ytail),
                              dep_r=_fmean([dep[d][0] for d in ytail]),
                              bear_r=b_r,
                              bear_dollars=sum(bear[d][1] for d in ytail)))

    met = (tail_r > 0) and (corr < 0) and (ok_years >= MIN_TAIL_YEARS)
    return HedgeContribution(common=common, corr=corr, buckets=buckets,
                             tail=tail, tail_r=tail_r, years=years,
                             ok_years=ok_years, tot_years=tot_years, met=met)


# ════════════════════════════════════════════════════════════════════════════
# The sizing criterion (bear_deploy D3)
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SweepRow:
    """One fraction of the sleeve, carried alongside the book."""
    f: float
    total: float
    mdd: float
    worst: float
    neg: int
    downside_dev: float


@dataclass(frozen=True)
class SizingVerdict:
    """`best` is the criterion's answer, None when no size clears it.

    `least_harmful` is the tested positive size whose drawdown is closest to
    (or above) the baseline — context for a NOT-MET report, never a fallback
    recommendation. It is None only when no positive fraction was swept.
    """
    best: SweepRow | None
    least_harmful: SweepRow | None


def sleeve_dollars(rows, picker, dol_key="Rb_dol", gate=None, date_key="date"):
    """date -> dollars of a 1-per-day sleeve chosen by `picker`.

    A row with no `dol_key` is not a candidate at all — it cannot be carried,
    whatever the picker thinks of it. `picker(row)` returning None drops that
    row; a day on which nothing is rankable is skipped entirely.
    `gate(date, rows)` may veto a day (the conditional sleeve); None means
    carry the sleeve every day a candidate exists. Ties go to the first row in
    the day's order, which is `max()`'s rule.
    """
    by_day = defaultdict(list)
    for r in rows:
        if r.get(dol_key) is not None:
            by_day[str(r[date_key])].append(r)
    out = {}
    for d, rs in by_day.items():
        if gate is not None and not gate(d, rs):
            continue
        keyed = [(picker(r), r) for r in rs]
        keyed = [(k, r) for k, r in keyed if k is not None]
        if not keyed:
            continue
        out[d] = max(keyed, key=lambda kr: kr[0])[1][dol_key]
    return out


def sweep(dep, sleeve, fractions) -> tuple[list[SweepRow], SweepRow | None, list[str]]:
    """The book carried at each fraction of the sleeve.

    Returns the rows, the `f == 0` baseline row (None if the grid has no zero,
    in which case there is nothing to compare against), and the union of dates
    the two series cover — a date the sleeve is on but the book is not still
    contributes its dollars, which is what makes an always-on hedge cost
    something on days the book was flat.
    """
    dates = sorted(set(dep) | set(sleeve))
    base, out = None, []
    for f in fractions:
        daily = [dep.get(d, (0, 0.0, 0))[1] + f * sleeve.get(d, 0.0) for d in dates]
        neg = sum(1 for v in daily if v < 0)
        row = SweepRow(
            f=f,
            total=sum(daily),
            mdd=max_drawdown(daily),
            worst=min(daily),
            neg=neg,
            downside_dev=((statistics.fmean([v * v for v in daily if v < 0]) ** 0.5)
                          if neg else 0.0),
        )
        if f == 0.0:
            base = row
        out.append(row)
    return out, base, dates


def qualifies(row: SweepRow, base: SweepRow, eps: float = EPS) -> bool:
    """The size rule for ONE fraction: no worse than carrying nothing.

    Both comparisons, drawdown and worst date, against the `f = 0` baseline
    with `eps` of slack so an exactly-equal path counts as unharmed.
    """
    return row.mdd >= base.mdd - eps and row.worst >= base.worst - eps


def sizing_verdict(rows, base: SweepRow, eps: float = EPS) -> SizingVerdict:
    """The largest positive fraction that leaves BOTH paths unharmed.

    `best` is None when none does — the rule fails closed and does not fall
    back to the least-harmful size, which is reported separately as context.
    """
    positive = [r for r in rows if r.f > 0]
    ok = [r for r in positive if qualifies(r, base, eps)]
    return SizingVerdict(
        best=max(ok, key=lambda r: r.f) if ok else None,
        least_harmful=max(positive, key=lambda r: r.mdd) if positive else None,
    )
