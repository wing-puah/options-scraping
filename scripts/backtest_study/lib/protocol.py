"""Validation protocol for the tuning studies — splits, CIs, replay, metrics.

Kept separate from any model or feature code on purpose: every conclusion in
research/ rests on these four things being right, and the failure
modes they defend against have all already happened in this project's history.

  - **Date clustering.** Rows inside a signal_date share the tape, so the
    effective sample is the DATE count (~118), not the row count (~1,100). Every
    CI here resamples dates, never rows.
  - **Purging + embargo.** Outcome windows overlap (path_cap_days = 120), so a
    train row's label can be realised after a test row's entry. Un-embargoed CV
    leaks the label and flatters every model. Expanding walk-forward with a
    120-calendar-day gap between train end and test start (Lopez de Prado).
  - **Same-dates comparison.** A model is only ever compared with the benchmark
    on the dates where both produced a pick; otherwise "beats the ladder" can be
    a difference in which days were traded.
  - **Window dominance.** Any headline is re-cut ex-Mar-Apr-2025 and
    ex-Feb-Apr-2026 — the two windows that have each carried an effect single-
    handedly before.

Pure functions over lists of dicts / DataFrames; no I/O, no globals, no model
imports.
"""
from __future__ import annotations

import random
import statistics
from datetime import date as _date
from datetime import timedelta

# The two windows that have each dominated a result before (see current.md).
DOMINANT_WINDOWS = {
    "ex_2025_mar_apr": ("2025-03", "2025-04"),
    "ex_2026_feb_apr": ("2026-02", "2026-03", "2026-04"),
}

PATH_CAP_DAYS = 120         # config/backtest.yml simulation.path_cap_days
BOOT_N = 10000


def _iso(d: str) -> _date:
    return _date.fromisoformat(str(d)[:10])


# ── splits ──────────────────────────────────────────────────────────────────

def walk_forward_splits(dates, block: int = 15, embargo_days: int = PATH_CAP_DAYS,
                        min_train_dates: int = 40):
    """Expanding-window, purged walk-forward over sorted unique `dates`.

    Yields `(train_dates, test_dates)`. The train set is every date at least
    `embargo_days` BEFORE the first test date, so no training label can still be
    open when the test block starts. Blocks are contiguous runs of `block`
    trading dates; a block whose purged train set is smaller than
    `min_train_dates` is skipped rather than fitted on too little history.
    """
    uniq = sorted(set(str(d) for d in dates))
    for start in range(0, len(uniq), block):
        test = uniq[start:start + block]
        if not test:
            continue
        cutoff = _iso(test[0]) - timedelta(days=embargo_days)
        train = [d for d in uniq[:start] if _iso(d) <= cutoff]
        if len(train) < min_train_dates:
            continue
        yield train, test


def year_epoch_split(dates, test_year: str = "2026", embargo_days: int = PATH_CAP_DAYS):
    """`(train_dates, test_dates)` for the strict 'train ≤ prior years' epoch."""
    uniq = sorted(set(str(d) for d in dates))
    test = [d for d in uniq if d[:4] == test_year]
    if not test:
        return [], []
    cutoff = _iso(test[0]) - timedelta(days=embargo_days)
    return [d for d in uniq if _iso(d) <= cutoff], test


# ── uncertainty ─────────────────────────────────────────────────────────────

def boot_ci_by_date(rows, key="E", n: int = BOOT_N, seed: int = 20260811,
                    alpha: float = 0.05):
    """Date-clustered bootstrap CI of the mean of `key`.

    Resamples DATES with replacement (keeping each date's rows together), which
    is the only honest unit here — see module docstring.
    """
    vals = [(str(r["date"]), r[key]) for r in rows if r.get(key) is not None]
    if not vals:
        return (float("nan"), float("nan"))
    by: dict[str, list[float]] = {}
    for d, v in vals:
        by.setdefault(d, []).append(float(v))
    dates = list(by)
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        pool = []
        for _ in range(len(dates)):
            pool.extend(by[rng.choice(dates)])
        means.append(statistics.fmean(pool))
    means.sort()
    return (means[int(alpha / 2 * n)], means[int((1 - alpha / 2) * n)])


def boot_ci_paired_by_date(rows, key_a: str, key_b: str, n: int = BOOT_N,
                           seed: int = 20260811, alpha: float = 0.05):
    """Date-clustered CI of mean(key_a) - mean(key_b) on the SAME rows.

    Paired, because a model and the benchmark are compared on identical dates —
    an unpaired CI of two book means would mostly measure which days each traded.
    """
    by: dict[str, list[tuple[float, float]]] = {}
    for r in rows:
        if r.get(key_a) is None or r.get(key_b) is None:
            continue
        by.setdefault(str(r["date"]), []).append((float(r[key_a]), float(r[key_b])))
    if not by:
        return (float("nan"), float("nan"))
    dates = list(by)
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        a_pool, b_pool = [], []
        for _ in range(len(dates)):
            for a, b in by[rng.choice(dates)]:
                a_pool.append(a)
                b_pool.append(b)
        diffs.append(statistics.fmean(a_pool) - statistics.fmean(b_pool))
    diffs.sort()
    return (diffs[int(alpha / 2 * n)], diffs[int((1 - alpha / 2) * n)])


def loo_by_date(rows, value_fn, baseline_fn):
    """Leave-one-date-out gain of `value_fn` over `baseline_fn`.

    Returns `(mean_gain, share_of_folds_positive, min_gain, n_folds)`.

    A rule SURVIVES only when **every** fold stays positive (share == 1.0). The
    signature of a one-date effect is not a low share — it is a share just under
    1 with a `min_gain` far below the mean: the single fold that drops the
    carrying date is the one that flips. This is the test that killed the
    per-regime exit switch twice, so read `min_gain`, not the average.
    """
    dates = sorted({str(r["date"]) for r in rows})
    if len(dates) < 3:
        return (float("nan"), float("nan"), float("nan"), 0)
    gains = []
    for d in dates:
        kept = [r for r in rows if str(r["date"]) != d]
        if not kept:
            continue
        gains.append(statistics.fmean([value_fn(r) for r in kept])
                     - statistics.fmean([baseline_fn(r) for r in kept]))
    if not gains:
        return (float("nan"), float("nan"), float("nan"), 0)
    return (statistics.fmean(gains),
            sum(1 for g in gains if g > 0) / len(gains),
            min(gains), len(gains))


# ── selection replay ────────────────────────────────────────────────────────

def top_k_per_day(rows, rank_fn, k: int = 3, eligible_fn=None):
    """The k rows each date would actually be deployed, by `rank_fn` (higher first).

    Mirrors docs/deployment-rules.md: 1-3 positions per day, taken in tier
    order. `eligible_fn` filters first (the ladder's VETO/C exclusion); dates
    with no eligible row simply contribute nothing.
    """
    by: dict[str, list] = {}
    for r in rows:
        if eligible_fn is not None and not eligible_fn(r):
            continue
        by.setdefault(str(r["date"]), []).append(r)
    picked = []
    for d in sorted(by):
        day = sorted(by[d], key=rank_fn, reverse=True)
        picked.extend(day[:k])
    return picked


def ordered_by_day(rows, rank_fn, eligible_fn=None):
    """`[(date, candidates ranked best-first)]` — the ordering `top_k_per_day`
    applies, exposed so a STATEFUL caller (an account simulation walking a
    capital/exposure ledger) can traverse the same ladder and stop early.

    `top_k_per_day` is deliberately left untouched — every recorded conclusion
    rests on it — and the two are pinned equal by a test
    (tests/test_studies_protocol.py::test_ordered_by_day_matches_top_k_per_day).
    """
    by: dict[str, list] = {}
    for r in rows:
        if eligible_fn is not None and not eligible_fn(r):
            continue
        by.setdefault(str(r["date"]), []).append(r)
    return [(d, sorted(by[d], key=rank_fn, reverse=True)) for d in sorted(by)]


def ladder_rank(r):
    """A-then-B ordering for the shipped ladder, deterministic tie-break.

    `score_total` is the tie-break ONLY (2026-07-21: the score is decision-
    irrelevant for selection, and pre-13c scores anti-select), applied inside a
    tier, never across tiers.
    """
    tier_rank = {"A": 3, "B": 2, "C": 1, "VETO": 0}.get(r.get("tier"), 0)
    score = r.get("score_total")
    tie = float(score) if score not in (None, "") and r.get("post13c") else 0.0
    return (tier_rank, tie)


def ladder_eligible(r):
    """Deployed tiers only — A and B (C and VETO are never taken)."""
    return r.get("tier") in ("A", "B")


def replay_stats(picked, r_key="R", dollar_key="R_dol", e_key="E"):
    """Book summary for a set of picked rows."""
    if not picked:
        return dict(n=0, dates=0, dollars=0.0, mean_R=float("nan"),
                    mean_E=float("nan"), win=float("nan"))
    r_vals = [float(p[r_key]) for p in picked if p.get(r_key) is not None]
    e_vals = [float(p[e_key]) for p in picked if p.get(e_key) is not None]
    dollars = sum(float(p[dollar_key]) for p in picked if p.get(dollar_key) is not None)
    return dict(n=len(picked), dates=len({str(p["date"]) for p in picked}),
                dollars=dollars,
                mean_R=statistics.fmean(r_vals) if r_vals else float("nan"),
                mean_E=statistics.fmean(e_vals) if e_vals else float("nan"),
                win=(sum(1 for v in r_vals if v > 0) / len(r_vals)) if r_vals else float("nan"))


# ── standard cuts ───────────────────────────────────────────────────────────

def window_cuts(rows):
    """`{cut_name: rows}` for ALL + the two mandatory ex-window cuts."""
    cuts = {"ALL": rows}
    for name, months in DOMINANT_WINDOWS.items():
        cuts[name] = [r for r in rows if str(r["date"])[:7] not in months]
    return cuts


def by_year(rows):
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(str(r["date"])[:4], []).append(r)
    return dict(sorted(out.items()))


def sign_stable(rows, key="E", min_years: int = 2):
    """(all_years_same_sign, positive_year_count, per-year means).

    The 2026-08-08 screen standard: an effect that does not keep its sign in
    every year present is a window artifact until proven otherwise.
    """
    means = {y: statistics.fmean([float(r[key]) for r in rs if r.get(key) is not None])
             for y, rs in by_year(rows).items()}
    means = {y: m for y, m in means.items() if m == m}
    pos = sum(1 for m in means.values() if m > 0)
    return (pos == len(means) or pos == 0, pos, means)


# ── profit factor ───────────────────────────────────────────────────────────
#
# A PF claim must also clear the mean-R criterion — PF alone is gameable by
# fewer, larger wins. Print PF beside mean R, never alone.

def pf(rows, key: str = "R") -> float | None:
    """Profit factor: sum of positive `key` / |sum of negative `key`|.

    A PF claim must also clear the mean-R criterion — PF alone is gameable by
    fewer, larger wins. Print PF beside mean R, never alone.

    Returns **None when there are no negatives**, which is the honest answer:
    the ratio is undefined, not infinite, and a book with no losers is a book
    too small (or too filtered) to have a profit factor. `None` values of `key`
    are skipped, exactly as `boot_ci_by_date` skips them.
    """
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    losses = -sum(v for v in vals if v < 0)
    if losses <= 0:
        return None
    return sum(v for v in vals if v > 0) / losses


def pf_ci_by_date(rows, key: str = "R", n: int = BOOT_N, seed: int = 20260811,
                  alpha: float = 0.05):
    """`(point, lo, hi)` — date-clustered bootstrap CI of the profit factor.

    Resamples DATES with replacement keeping each date's rows together, the same
    unit as `boot_ci_by_date` and for the same reason (rows inside a date share
    the tape). A resample that draws no losing row has an undefined PF and is
    DROPPED rather than treated as infinite — with few losers that thins the
    distribution, so read a CI computed from a small book beside the count of
    negative rows, not on its own.

    A PF claim must also clear the mean-R criterion — PF alone is gameable by
    fewer, larger wins. Print PF beside mean R, never alone.
    """
    by: dict[str, list[float]] = {}
    for r in rows:
        if r.get(key) is None:
            continue
        by.setdefault(str(r["date"]), []).append(float(r[key]))
    point = pf(rows, key)
    if not by:
        return (None, float("nan"), float("nan"))
    dates = list(by)
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        pool = []
        for _ in range(len(dates)):
            pool.extend(by[rng.choice(dates)])
        losses = -sum(v for v in pool if v < 0)
        if losses > 0:
            vals.append(sum(v for v in pool if v > 0) / losses)
    if not vals:
        return (point, float("nan"), float("nan"))
    vals.sort()
    m = len(vals)
    return (point, vals[int(alpha / 2 * m)], vals[min(m - 1, int((1 - alpha / 2) * m))])


def pf_paired_by_date(rows_a, rows_b, key: str = "R", n: int = BOOT_N,
                      seed: int = 20260811, alpha: float = 0.05):
    """`(point_diff, lo, hi)` — CI of PF(a) - PF(b) under JOINT date resampling.

    The two books are resampled together over the UNION of their dates: a drawn
    date contributes its `a` rows to `a`'s pool and its `b` rows to `b`'s, so
    the comparison never becomes a difference in which days each side traded
    (the same-dates rule in the module docstring). A resample where either side
    has no losing row is dropped, as in `pf_ci_by_date`.

    A PF claim must also clear the mean-R criterion — PF alone is gameable by
    fewer, larger wins. Print PF beside mean R, never alone.
    """
    def _by(rows):
        out: dict[str, list[float]] = {}
        for r in rows:
            if r.get(key) is None:
                continue
            out.setdefault(str(r["date"]), []).append(float(r[key]))
        return out

    ba, bb = _by(rows_a), _by(rows_b)
    pa, pb = pf(rows_a, key), pf(rows_b, key)
    point = (pa - pb) if (pa is not None and pb is not None) else None
    dates = sorted(set(ba) | set(bb))
    if not dates:
        return (point, float("nan"), float("nan"))
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        pool_a, pool_b = [], []
        for _ in range(len(dates)):
            d = rng.choice(dates)
            pool_a.extend(ba.get(d, ()))
            pool_b.extend(bb.get(d, ()))
        la = -sum(v for v in pool_a if v < 0)
        lb = -sum(v for v in pool_b if v < 0)
        if la <= 0 or lb <= 0:
            continue
        diffs.append(sum(v for v in pool_a if v > 0) / la
                     - sum(v for v in pool_b if v > 0) / lb)
    if not diffs:
        return (point, float("nan"), float("nan"))
    diffs.sort()
    m = len(diffs)
    return (point, diffs[int(alpha / 2 * m)], diffs[min(m - 1, int((1 - alpha / 2) * m))])
