"""HEDGE-TIMING arm — does a mechanical trigger pick the day the bear hedge beats the ladder?

Pre-registered 2026-08-28. Registration:
`research/pre-registrations/f4_deployment/hedge_timing.md`, where
`scripts/study_review/` reads it. Read it before quoting anything printed here.

The operator deploys the bear-debit hedge sleeve on three discretionary
triggers: the market looks choppy, SPY gaps up, or SPY has closed lower 4-5
sessions in a row. This module asks whether any of those, made mechanical,
identifies a day on which the hedge earns more than the SAME DAY's
ladder-eligible long — and, for the streak rule specifically, whether the book
can answer that question at all.

It cannot. A strict 4-session SPY down-run occurs on ~11 of the era's ~457
trading days and the book samples 2 of them, so the strict-run arms carry a
verdict FIXED IN ADVANCE (UNDERPOWERED) and no direction is ever quoted from
them. That is a sampling limit of the book, not a fact about the market, and it
is itself this study's decision-relevant output for trigger (c).

Arms (one per trigger FAMILY: CHOP, GAP, DECLINE):

  ARM H0  POWER CENSUS. Runs first and returns BEFORE any outcome column is
          read. A failed floor early-returns UNDERPOWERED from every arm below
          without computing a single statistic.
  ARM H1  Between-date separation of bear R, trigger vs non-trigger. NOT the
          primary: a date either fires or does not, so no within-date pairing
          exists and a positive is confounded with "the market fell".
  ARM H2  The SAME separation computed on the deployed ladder — the beta
          control. `h2_mirrors` fires when the long book moves the opposite way
          by a comparable amount, which makes H1 a read on the tape.
  ARM H3  PRIMARY. The operator's counterfactual, within-date paired
          (`bear_deploy` D4's proven method): date-mean bear R minus date-mean
          tier-A/B long R, and the headline is the DIFFERENCE between that
          paired mean on trigger dates and on non-trigger dates.
  ARM H4  Do-nothing baseline, in dollars: sleeve policies over the deployed
          ladder's daily dollars, judged by `bear_deploy` D3's criterion (max
          drawdown AND worst single date both no worse than f=0).

What this is NOT: not a re-run of `bear_deploy` D5 (its regime gates failed
year-stability and are not re-tested; `mech_direction = RANGE` is printed as a
flagged SECONDARY with no verdict), not a re-opening of bear selection (B1/D1
nulls stand), and not a market-timing study — ARM H2 exists to catch exactly
that confound.

Nothing ships from this study under any outcome. R only in H1-H3, dollars only
in H4.

Run:
    source .venv/bin/activate
    python -m scripts.backtest_study run hedge_timing
    python -m scripts.backtest_study run hedge_timing --era v3   # the disclosed replication
"""
from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import triggers as TRIG  # noqa: E402
from scripts.backtest_study.lib import underlying_features as UF  # noqa: E402
from scripts.backtest_study.lib.book import CREDIT_PROD, DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.underlying import Bar, load_bars  # noqa: E402

# G2 (the SPY series cross-check) refuses rather than fails. 2 and 3 belong to
# lib/era.py's thin-era and era-mismatch refusals; this study numbers from 4.
EXIT_SERIES_MISMATCH = 4
DESIGNED_REFUSAL_EXIT_CODES = frozenset({EXIT_SERIES_MISMATCH})

# The sleeve this study is about. `bear_arm.BEAR_STRUCTURES` also carries
# `bear_call_spread`, which is a CREDIT structure and tier-VETO'd at intake —
# it is not part of the debit hedge the operator deploys, so it is not here.
BEAR_DEBIT_STRUCTURES = ("bear_put_spread", "long_put")

# ── pre-registered floors (registration §"Bar for a candidate") ──────────────
FLOOR_TRIGGER_DATES = 25    # every date-clustered arm
FLOOR_ROWS = 60             # additionally, for any row-level cell
FLOOR_H4_DAYS = 25          # gated days; raised deliberately from D5's informal 10

# ── pre-registered trigger constants (closed at registration; NOT swept) ─────
CHOP_WINDOW = UF.EFF_WINDOW          # the standing 20-session constant
CHOP_SENSITIVITY = 0.30
GAP_PRIMARY = 0.003
GAP_SENSITIVITY = 0.002
GAP_DECLARED_UNDERPOWERED = 0.005
DECLINE_STRICT_NS = (3, 4, 5)
DECLINE_BROAD_K = 3
DECLINE_BROAD_WINDOW = 5

SLEEVE_FRACTIONS = (0.5, 1.0)

# The hand cut: rows in NEITHER dominant window. `protocol.window_cuts` yields
# the two separately and never their intersection, so this is computed here.
EX_BOTH_MONTHS = frozenset(m for months in P.DOMINANT_WINDOWS.values() for m in months)

# G2 thresholds.
SERIES_MIN_CORR = 0.99
SERIES_MIN_SIGN_AGREE = 0.99

# Multiplicity, fixed at registration: 3 families x 3 verdicted arms.
HEADLINE_TESTS = 9

BOOT_SEED = 20260828

FAMILIES = ("CHOP", "GAP", "DECLINE")

VERDICTS = ("NOT EVALUABLE", "UNDERPOWERED", "TIMING-CANDIDATE",
            "MARKET-TIMING-PROXY", "CONTRARY", "UNSTABLE", "NULL")


# ════════════════════════════════════════════════════════════════════════════
# printing helpers (shape copied from bear_deploy.py, 2026-08-11)
# ════════════════════════════════════════════════════════════════════════════

def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


def fmean(vals):
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else float("nan")


def _same_sign(a: float, b: float) -> bool:
    """Both strictly positive or both strictly negative. A zero, or a nan from
    an EMPTY cut, is NOT the same sign as anything — this fails CLOSED, the
    lesson `bear_deploy.cuts_pass` was rewritten for on 2026-08-24."""
    if a != a or b != b:
        return False
    return (a > 0 and b > 0) or (a < 0 and b < 0)


# ════════════════════════════════════════════════════════════════════════════
# SPY series + triggers — every one causal, reading only bars on or before D
# ════════════════════════════════════════════════════════════════════════════

def spy_series():
    """`(closes, opens, cache_closes)` — the two SPY series this study reads.

    `closes` come from `backtests/mech_regime/spy_vix_daily_full.csv` through
    `underlying_features.market_closes()`, which already drops a holiday row
    carrying only one leg (it refuses a row with no positive `spy_close` —
    2026-05-25 is such a row). `opens`/`cache_closes` come from the OHLC cache
    via `underlying.load_bars("SPY")`; SPY is not in `rescaled_tickers()`, so no
    split rescaling applies to either series.

    The two are cross-checked in `series_crosscheck` (G2) before any trigger is
    evaluated: the mech CSV is unadjusted and the cache is adjusted, and the
    gate's job is to prove that difference cannot move a trigger.
    """
    closes = dict(UF.market_closes())
    bars = load_bars("SPY")
    opens = {d: b.o for d, b in bars.items() if b.o is not None and b.o > 0}
    cache_closes = {d: b.c for d, b in bars.items() if b.c and b.c > 0}
    return closes, opens, cache_closes


def as_date(x):
    """A book date (an ISO string) as a `datetime.date`, so it can index the SPY
    series. Book records key on strings; both SPY series key on `date`."""
    return x if isinstance(x, _date) else _date.fromisoformat(str(x)[:10])


def _bars_from_closes(closes) -> dict:
    """A close-only `{date: Bar}` so `underlying_features.eff_ratio` can be
    reused verbatim rather than reimplemented — its `trailing_bars` is the one
    place in this repo where the `<= as_of` no-look-ahead comparison lives."""
    return {d: Bar(c=c) for d, c in closes.items() if c and c > 0}


def _trailing_days(series, d, n):
    """The last `n` dates of `series` on or before `d`, oldest first."""
    days = sorted(x for x in series if x <= d)
    return days[-n:]


def chop_value(closes, d):
    """SPY's Kaufman efficiency ratio at D over `CHOP_WINDOW` sessions."""
    return UF.eff_ratio(_bars_from_closes(closes), d)


def t_chop(closes, d, boundary) -> bool:
    """T-CHOP: efficiency ratio at or below `boundary` (chop, not trend).

    NOT `mech_direction = RANGE`: that was `bear_deploy` D5's best POST-HOC gate
    on 2026-08-27 and re-testing it here would be a disguised D5 re-run. RANGE
    is printed as a flagged SECONDARY carrying no verdict.
    """
    v = chop_value(closes, d)
    return v is not None and v <= boundary


def t_gap(closes, opens, d, g) -> bool:
    """T-GAP: `open(D) >= close(D-1) * (1 + g)`.

    Reads exactly two numbers, both stamped on or before D. Entry is the next
    session's open, so this is known a full session before money moves.
    """
    earlier = [x for x in closes if x < d]
    if not earlier or d not in opens:
        return False
    prev_close = closes[max(earlier)]
    if prev_close <= 0:
        return False
    return opens[d] >= prev_close * (1.0 + g)


def t_decline_strict(closes, d, n) -> bool:
    """T-DECLINE-STRICT(N): N consecutive lower SPY closes ending AT D.

    Verdict fixed in advance by the registration: UNDERPOWERED. The census
    prints; no direction is ever quoted from it.
    """
    days = _trailing_days(closes, d, n + 1)
    if len(days) < n + 1:
        return False
    return all(closes[b] < closes[a] for a, b in zip(days, days[1:]))


def t_decline_broad(closes, d, k=DECLINE_BROAD_K, window=DECLINE_BROAD_WINDOW) -> bool:
    """T-DECLINE-BROAD: SPY closed lower on >= k of the last `window` sessions ending at D.

    ASYMMETRIC READING RULE, pre-registered: a NULL here IS informative about
    the strict rule (if even the broad construct cannot separate, the narrow one
    is not worth waiting for); a POSITIVE here is NOT evidence for the
    operator's 4-5-day rule and may never be cited as such.
    """
    days = _trailing_days(closes, d, window + 1)
    if len(days) < window + 1:
        return False
    downs = sum(1 for a, b in zip(days, days[1:]) if closes[b] < closes[a])
    return downs >= k


def chop_boundary(closes, book_dates):
    """The bottom-tercile `eff_ratio` boundary over the ERA'S BOOK DATES.

    Computed from the SPY series alone — no outcome column is involved — and
    printed in the census before any R is read.
    """
    bars = _bars_from_closes(closes)
    vals = sorted(v for v in (UF.eff_ratio(bars, as_date(d)) for d in book_dates)
                  if v is not None and math.isfinite(v))
    if len(vals) < 9:
        return None
    return vals[len(vals) // 3]


# ════════════════════════════════════════════════════════════════════════════
# G2 — the two SPY series must agree
# ════════════════════════════════════════════════════════════════════════════

def series_crosscheck(mech_closes, cache_closes):
    """G2: the mech-CSV closes and the OHLC-cache closes must be the same tape.

    Pearson correlation of daily LOG RETURNS >= `SERIES_MIN_CORR`, and
    same-signed daily direction on >= `SERIES_MIN_SIGN_AGREE` of overlapping
    dates. Disagreeing dates are listed. Failure is NOT EVALUABLE, not a lean.
    """
    common = sorted(set(mech_closes) & set(cache_closes))
    a, b, disagree = [], [], []
    for prev, cur in zip(common, common[1:]):
        pa, ca = mech_closes[prev], mech_closes[cur]
        pb, cb = cache_closes[prev], cache_closes[cur]
        if min(pa, ca, pb, cb) <= 0:
            continue
        ra, rb = math.log(ca / pa), math.log(cb / pb)
        a.append(ra)
        b.append(rb)
        if (ra > 0) != (rb > 0) and (ra != 0 or rb != 0):
            disagree.append(cur)
    n = len(a)
    if n < 30:
        return dict(n=n, corr=float("nan"), sign_share=float("nan"),
                    disagree=disagree, ok=False,
                    why="fewer than 30 overlapping sessions to compare")
    try:
        corr = statistics.correlation(a, b)
    except statistics.StatisticsError:
        corr = float("nan")
    sign_share = 1.0 - len(disagree) / n
    ok = (corr == corr and corr >= SERIES_MIN_CORR
          and sign_share >= SERIES_MIN_SIGN_AGREE)
    return dict(n=n, corr=corr, sign_share=sign_share, disagree=disagree, ok=ok,
                why=None if ok else "the two SPY series do not describe the same tape")


# ════════════════════════════════════════════════════════════════════════════
# cuts + date-clustered contrast machinery
# ════════════════════════════════════════════════════════════════════════════

def ex_both_windows(rows):
    """Rows in NEITHER dominant window — the HAND cut.

    `protocol.window_cuts` yields `ex_2025_mar_apr` and `ex_2026_feb_apr`
    separately and never their intersection. On a v4 book with no 2026 signal
    dates this cut EQUALS `ex_2025_mar_apr`, and the report says so rather than
    presenting it as an independent check.
    """
    return [r for r in rows if str(r["date"])[:7] not in EX_BOTH_MONTHS]


def _boot_between_by_date(a_vals, b_vals, n=P.BOOT_N, seed=BOOT_SEED, alpha=0.05):
    """Date-clustered CI of `mean(a) - mean(b)` for two DISJOINT date groups.

    Copied in SHAPE from `protocol.boot_ci_by_date` (resample DATES with
    replacement, keep each date's value together) and extended to two
    INDEPENDENT groups, which `boot_ci_paired_by_date` cannot express: a date
    either fires the trigger or it does not, so there is nothing to pair. Not
    added to `protocol.py` — this is a between-group estimator specific to a
    trigger study, and the protocol module is what every recorded conclusion
    rests on.

    `a_vals`/`b_vals` are `{date: value}` — one value per date, already
    collapsed, so a date is one draw.
    """
    a_keys, b_keys = list(a_vals), list(b_vals)
    if len(a_keys) < 2 or len(b_keys) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        aa = statistics.fmean([a_vals[rng.choice(a_keys)] for _ in a_keys])
        bb = statistics.fmean([b_vals[rng.choice(b_keys)] for _ in b_keys])
        diffs.append(aa - bb)
    diffs.sort()
    return (diffs[int(alpha / 2 * n)], diffs[int((1 - alpha / 2) * n)])


def _contrast_stability(a_vals, b_vals, delta):
    """LOO / per-year / three-window stability of a between-date contrast.

    LOO is `protocol.loo_by_date` applied to one row per TRIGGER date carrying
    `a` = that date's value and `b` = the constant non-trigger mean, so dropping
    a fold drops a trigger date and recomputes the contrast — the same semantics
    `loo_by_date` has everywhere else in the package.
    """
    base = fmean(list(b_vals.values()))
    rows = [{"date": d, "a": v, "b": base} for d, v in a_vals.items()]
    _mean, share, loo_min, folds = P.loo_by_date(
        rows, lambda r: r["a"], lambda r: r["b"])
    if folds == 0 or share != share:
        loo_ok = False
    else:
        loo_ok = (share == 1.0) if delta > 0 else (share == 0.0 if delta < 0 else False)

    years = {}
    for d, v in a_vals.items():
        years.setdefault(str(d)[:4], []).append(v)
    year_means = {y: fmean(vs) - base for y, vs in sorted(years.items())}
    years_ok = bool(year_means) and all(_same_sign(m, delta) for m in year_means.values())

    cuts = {}
    for name, months in P.DOMINANT_WINDOWS.items():
        kept = [v for d, v in a_vals.items() if str(d)[:7] not in months]
        cuts[name] = (fmean(kept) - base) if kept else float("nan")
    kept_both = [v for d, v in a_vals.items() if str(d)[:7] not in EX_BOTH_MONTHS]
    cuts["ex_BOTH"] = (fmean(kept_both) - base) if kept_both else float("nan")
    cuts_n = {"ALL": len(a_vals),
              "ex_2025_mar_apr": sum(1 for d in a_vals
                                     if str(d)[:7] not in P.DOMINANT_WINDOWS["ex_2025_mar_apr"]),
              "ex_2026_feb_apr": sum(1 for d in a_vals
                                     if str(d)[:7] not in P.DOMINANT_WINDOWS["ex_2026_feb_apr"]),
              "ex_BOTH": len(kept_both)}
    cuts_ok = all(_same_sign(v, delta) for v in cuts.values())

    return dict(loo_min=loo_min, loo_share=share, loo_folds=folds, loo_ok=loo_ok,
                years=year_means, years_ok=years_ok,
                cuts=cuts, cuts_n=cuts_n, cuts_ok=cuts_ok)


def _print_stability(st):
    print("      years  " + "  ".join(f"{y}:{m:+.3f}" for y, m in st["years"].items())
          + f"   -> {'OK' if st['years_ok'] else 'FAILS'}")
    print("      cuts   " + "  ".join(f"{k.replace('ex_', '')}:{v:+.3f}(n={st['cuts_n'][k]})"
                                      for k, v in st["cuts"].items())
          + f"   -> {'OK' if st['cuts_ok'] else 'FAILS'}")
    print(f"      LOO    min {st['loo_min']:+.3f}  share {st['loo_share']:.2f} "
          f"over {st['loo_folds']} folds   -> {'OK' if st['loo_ok'] else 'FAILS'}")


# ════════════════════════════════════════════════════════════════════════════
# verdict grammar — TOTAL by construction
# ════════════════════════════════════════════════════════════════════════════

def verdict_for(c: dict) -> str:
    """The ONE verdict function, over the criterion vector
    `{evaluable, powered, ci_excludes_zero, positive, loo_all_same_sign,
      years_ok, cuts_ok, h2_mirrors}`.

    Total: every combination of the eight booleans returns exactly one token
    from `VERDICTS`. The trailing INDETERMINATE line is the catch-all so a
    malformed vector cannot fall through unlabelled — it prints the vector
    verbatim rather than guessing.
    """
    if not c.get("evaluable"):
        return "NOT EVALUABLE"
    if not c.get("powered"):
        return "UNDERPOWERED"
    full_bar = (c.get("ci_excludes_zero") and c.get("loo_all_same_sign")
                and c.get("years_ok") and c.get("cuts_ok"))
    if full_bar:
        if not c.get("positive"):
            return "CONTRARY"
        return "MARKET-TIMING-PROXY" if c.get("h2_mirrors") else "TIMING-CANDIDATE"
    if c.get("ci_excludes_zero"):
        return "UNSTABLE"
    if not c.get("ci_excludes_zero"):
        return "NULL"
    return "INDETERMINATE — " + repr(dict(sorted(c.items())))


# ════════════════════════════════════════════════════════════════════════════
# ARM H0 — power census. Runs FIRST, touches no outcome column.
# ════════════════════════════════════════════════════════════════════════════

def h0_census(label, trigger_fn, book_dates, bear_by_date, ladder_by_date):
    """Counts only: trigger dates, bear-carrying dates, bear rows, H3-paired
    dates — and the same four on non-trigger dates.

    Returns before any outcome column is read. Every arm below takes this dict
    and early-returns UNDERPOWERED off it, so a floor failure never reaches a
    statistic.
    """
    trig = sorted(d for d in book_dates if trigger_fn(d))
    non = sorted(d for d in book_dates if d not in set(trig))

    def tally(dates):
        bear_dates = [d for d in dates if bear_by_date.get(d)]
        rows = sum(len(bear_by_date.get(d, ())) for d in dates)
        paired = [d for d in dates if bear_by_date.get(d) and ladder_by_date.get(d)]
        return dict(dates=list(dates), n_dates=len(dates),
                    bear_dates=bear_dates, n_bear_dates=len(bear_dates),
                    n_bear_rows=rows, paired=paired, n_paired=len(paired))

    t, nt = tally(trig), tally(non)
    return dict(
        label=label, trigger=t, nontrigger=nt,
        # An arm is powered on the count it will actually resample.
        powered_h1=t["n_bear_dates"] >= FLOOR_TRIGGER_DATES,
        powered_h2=len([d for d in trig if ladder_by_date.get(d)]) >= FLOOR_TRIGGER_DATES,
        powered_h3=t["n_paired"] >= FLOOR_TRIGGER_DATES,
        rows_floor_met=t["n_bear_rows"] >= FLOOR_ROWS,
    )


def print_census(cen):
    t, nt = cen["trigger"], cen["nontrigger"]
    print(TRIG.census_line(f"{cen['label']} trigger dates", t["n_bear_rows"],
                           t["n_dates"], floor_dates=FLOOR_TRIGGER_DATES))
    print(TRIG.census_line(f"{cen['label']} bear-carrying", t["n_bear_rows"],
                           t["n_bear_dates"], floor_dates=FLOOR_TRIGGER_DATES))
    print(TRIG.census_line(f"{cen['label']} H3-paired", t["n_bear_rows"],
                           t["n_paired"], floor_dates=FLOOR_TRIGGER_DATES))
    print(TRIG.census_line(f"{cen['label']} bear rows", t["n_bear_rows"],
                           t["n_dates"], floor_rows=FLOOR_ROWS))
    print(f"    non-trigger contrast: dates={nt['n_dates']}  "
          f"bear-carrying={nt['n_bear_dates']}  bear rows={nt['n_bear_rows']}  "
          f"H3-paired={nt['n_paired']}")


# ════════════════════════════════════════════════════════════════════════════
# ARM H1 / ARM H2 — between-date separation, and the beta control
# ════════════════════════════════════════════════════════════════════════════

def _date_means(by_date, dates, key="R"):
    """`{date: date-mean of key}` over `dates` that carry at least one value."""
    out = {}
    for d in dates:
        vals = [r[key] for r in by_date.get(d, ()) if r.get(key) is not None]
        if vals:
            out[d] = statistics.fmean([float(v) for v in vals])
    return out


def _between_arm(arm, by_date, cen, powered_key, evaluable=True):
    """The shared body of ARM H1 and ARM H2 — one between-date contrast.

    The floor check happens BEFORE `_date_means` is ever called, so an
    underpowered arm returns without touching an outcome column and its result
    dict carries no statistic at all.
    """
    if not evaluable:
        return dict(arm=arm, verdict=verdict_for(dict(evaluable=False)), powered=False,
                    n_trigger_dates=cen["trigger"]["n_dates"])
    if not cen[powered_key]:
        return dict(arm=arm, verdict="UNDERPOWERED", powered=False,
                    n_trigger_dates=cen["trigger"]["n_dates"],
                    n_bear_dates=cen["trigger"]["n_bear_dates"],
                    n_paired=cen["trigger"]["n_paired"])

    a = _date_means(by_date, cen["trigger"]["dates"])
    b = _date_means(by_date, cen["nontrigger"]["dates"])
    delta = fmean(list(a.values())) - fmean(list(b.values()))
    lo, hi = _boot_between_by_date(a, b)
    st = _contrast_stability(a, b, delta)
    crit = dict(evaluable=evaluable, powered=True,
                ci_excludes_zero=(lo == lo and (lo > 0 or hi < 0)),
                positive=delta > 0, loo_all_same_sign=st["loo_ok"],
                years_ok=st["years_ok"], cuts_ok=st["cuts_ok"], h2_mirrors=False)
    return dict(arm=arm, powered=True, n_a=len(a), n_b=len(b), delta=delta,
                mean_trigger=fmean(list(a.values())),
                mean_non=fmean(list(b.values())), ci=(lo, hi), st=st,
                crit=crit, verdict=verdict_for(crit))


def h1_between(bear_by_date, cen, evaluable=True):
    """ARM H1 (one per trigger family) — bear R on trigger dates vs non-trigger dates.

    Named weakness, registered: no within-date pairing is possible and a
    positive is confounded with "the market fell". H1 is not the primary arm;
    ARM H3 is.
    """
    return _between_arm(f"H1-{cen['label']}", bear_by_date, cen, "powered_h1", evaluable)


def h2_between(ladder_by_date, cen, evaluable=True):
    """ARM H2 (one per trigger family) — the SAME separation on the deployed ladder (beta control)."""
    return _between_arm(f"H2-{cen['label']}", ladder_by_date, cen, "powered_h2", evaluable)


def h2_mirror(h1_delta, h2_delta) -> bool:
    """`h2_mirrors`: long R falls on trigger days by an amount COMPARABLE to
    bear R's rise — pre-registered as `|H2 delta| >= 0.5 * |H1 delta|` with the
    two deltas OPPOSITE-signed. When it fires, the trigger is reading the tape,
    not the hedge."""
    if h1_delta != h1_delta or h2_delta != h2_delta:
        return False
    if not ((h1_delta > 0 > h2_delta) or (h1_delta < 0 < h2_delta)):
        return False
    return abs(h2_delta) >= 0.5 * abs(h1_delta)


# ════════════════════════════════════════════════════════════════════════════
# ARM H3 — PRIMARY. Within-date paired, bear vs the same day's A/B long.
# ════════════════════════════════════════════════════════════════════════════

def h3_paired(bear_by_date, ladder_by_date, cen, evaluable=True):
    """ARM H3 (one per trigger family) — the operator's counterfactual.

    On each date carrying >=1 bear row AND >=1 ladder-eligible (tier A|B) row,
    `dR = date-mean bear R - date-mean A/B long R` — `bear_deploy` D4's proven
    within-date method, so the day is its own control and the level problem that
    sinks every B1/D1 subset cancels. The HEADLINE is the DIFFERENCE between
    that paired mean on trigger dates and on non-trigger dates, not the trigger
    arm's level.
    """
    arm = f"H3-{cen['label']}"
    if not evaluable:
        return dict(arm=arm, verdict=verdict_for(dict(evaluable=False)), powered=False,
                    n_paired=cen["trigger"]["n_paired"],
                    n_trigger_dates=cen["trigger"]["n_dates"])
    if not cen["powered_h3"]:
        return dict(arm=arm, verdict="UNDERPOWERED", powered=False,
                    n_paired=cen["trigger"]["n_paired"],
                    n_trigger_dates=cen["trigger"]["n_dates"])

    def dr(dates):
        bear = _date_means(bear_by_date, dates)
        lng = _date_means(ladder_by_date, dates)
        return {d: bear[d] - lng[d] for d in bear if d in lng}

    a, b = dr(cen["trigger"]["dates"]), dr(cen["nontrigger"]["dates"])
    delta = fmean(list(a.values())) - fmean(list(b.values()))
    lo, hi = _boot_between_by_date(a, b)
    st = _contrast_stability(a, b, delta)

    # The trigger arm's OWN paired CI, printed for context. `boot_ci_paired_by_date`
    # wants row dicts carrying both legs on the same date.
    paired_rows = []
    for d in sorted(a):
        bear = _date_means(bear_by_date, [d]).get(d)
        lng = _date_means(ladder_by_date, [d]).get(d)
        if bear is not None and lng is not None:
            paired_rows.append({"date": d, "bear": bear, "long": lng})
    p_lo, p_hi = P.boot_ci_paired_by_date(paired_rows, "bear", "long")

    crit = dict(evaluable=evaluable, powered=True,
                ci_excludes_zero=(lo == lo and (lo > 0 or hi < 0)),
                positive=delta > 0, loo_all_same_sign=st["loo_ok"],
                years_ok=st["years_ok"], cuts_ok=st["cuts_ok"], h2_mirrors=False)
    return dict(arm=arm, powered=True, n_a=len(a), n_b=len(b), delta=delta,
                paired_trigger=fmean(list(a.values())),
                paired_non=fmean(list(b.values())),
                ci=(lo, hi), own_ci=(p_lo, p_hi), st=st,
                crit=crit, verdict=verdict_for(crit))


# ════════════════════════════════════════════════════════════════════════════
# ARM H4 — do-nothing baseline, in DOLLARS (the only arm that may quote $)
# ════════════════════════════════════════════════════════════════════════════

def max_drawdown(series):
    """Max peak-to-trough drawdown of a cumulative dollar curve.

    COPIED VERBATIM from `f4_deployment/bear_deploy.py::max_drawdown`
    (2026-08-11) rather than imported: studies do not import each other's
    internals, so `bear_deploy`'s recorded D3 numbers can never move because
    this file changed.
    """
    peak, mdd = 0.0, 0.0
    cum = 0.0
    for v in series:
        cum += v
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    return mdd


def daily_dollars(rows, dol_key="R_dol"):
    """`{date: total dollars}` for a sleeve.

    Shape copied from `bear_deploy.py::daily_series` (2026-08-11), reduced to
    the dollar leg — this arm never quotes an R.
    """
    by = defaultdict(float)
    for r in rows:
        if r.get(dol_key) is not None:
            by[str(r["date"])] += float(r[dol_key])
    return dict(by)


def sleeve_pick(bear_by_date, dol_key="R_dol"):
    """`{date: dollars of ONE hedge that day}` — the day's widest `max_loss`.

    One hedge per day, per the registration. The picker is `bear_deploy` D3's
    lower-bound picker (widest max_loss), NOT its D4-adopted ranker: D4 lost the
    |delta|-descending rule outright on v4, so there is no adopted picker to
    inherit and this study does not re-open the pick question.
    """
    out = {}
    for d, rs in bear_by_date.items():
        keyed = [(r.get("max_loss_per_contract") or 0.0, r) for r in rs
                 if r.get(dol_key) is not None]
        if keyed:
            out[str(d)] = float(max(keyed, key=lambda kr: kr[0])[1][dol_key])
    return out


def policy_daily(dep_dollars, sleeve, f, gated_dates=None):
    """`[(date, dollars)]` for one sleeve policy over the deployed book.

    A date with NO bear row — or one the gate vetoes — is CARRIED AT f=0, never
    dropped. That is the `calendar_hedge` lesson made mechanical: a hedge
    unavailable exactly when it is needed is not a hedge, and dropping those
    days would quietly delete the evidence for it.
    """
    dates = sorted(set(dep_dollars) | set(sleeve))
    allowed = None if gated_dates is None else {str(d) for d in gated_dates}
    out = []
    for d in dates:
        hedge = sleeve.get(d, 0.0)
        if allowed is not None and d not in allowed:
            hedge = 0.0
        out.append((d, dep_dollars.get(d, 0.0) + f * hedge))
    return out


def _policy_stats(series):
    vals = [v for _d, v in series]
    return dict(total=sum(vals), mdd=max_drawdown(vals),
                worst=min(vals) if vals else 0.0)


def h4_portfolio(dep_dollars, sleeve, cen, evaluable=True):
    """ARM H4 (one per trigger family) — does gating the sleeve on the trigger leave the book unharmed?

    Criterion VERBATIM from `bear_deploy` D3: max drawdown AND worst single date
    both no worse than f=0. Disclosed: this reuses D5's estimator on new gates,
    so a pass HERE ALONE can never ship — D5's own gate family failed
    year-stability.
    """
    arm = f"H4-{cen['label']}"
    if not evaluable:
        return dict(arm=arm, verdict=verdict_for(dict(evaluable=False)), powered=False,
                    n_gated_days=0)
    gated = [d for d in cen["trigger"]["dates"] if str(d) in sleeve]
    if len(gated) < FLOOR_H4_DAYS:
        return dict(arm=arm, verdict="UNDERPOWERED", powered=False,
                    n_gated_days=len(gated))

    base = _policy_stats(policy_daily(dep_dollars, sleeve, 0.0))
    rows = []
    for label, f, gate in ([("always-on", f, None) for f in SLEEVE_FRACTIONS]
                           + [("trigger-gated", f, gated) for f in SLEEVE_FRACTIONS]):
        st = _policy_stats(policy_daily(dep_dollars, sleeve, f, gate))
        st.update(policy=label, f=f,
                  harmless=(st["mdd"] >= base["mdd"] - 1e-9
                            and st["worst"] >= base["worst"] - 1e-9))
        rows.append(st)

    gated_rows = [r for r in rows if r["policy"] == "trigger-gated"]
    best = max(gated_rows, key=lambda r: (r["harmless"], r["total"]))
    delta_total = best["total"] - base["total"]

    # LOO over the gated days, on the criterion's own currency.
    loo = []
    for d in gated:
        kept = [x for x in gated if x != d]
        st = _policy_stats(policy_daily(dep_dollars, sleeve, best["f"], kept))
        loo.append(st["total"] - base["total"])
    loo_ok = bool(loo) and all(_same_sign(v, delta_total) for v in loo)

    years = {}
    for d in gated:
        years.setdefault(str(d)[:4], []).append(sleeve[str(d)] * best["f"])
    year_totals = {y: sum(vs) for y, vs in sorted(years.items())}
    years_ok = bool(year_totals) and all(_same_sign(v, delta_total)
                                         for v in year_totals.values())

    ex_both = [d for d in gated if str(d)[:7] not in EX_BOTH_MONTHS]
    if ex_both:
        st = _policy_stats(policy_daily(dep_dollars, sleeve, best["f"], ex_both))
        cuts_ok = (st["mdd"] >= base["mdd"] - 1e-9
                   and st["worst"] >= base["worst"] - 1e-9)
    else:
        cuts_ok = False        # fail closed on an empty cut

    crit = dict(evaluable=evaluable, powered=True,
                ci_excludes_zero=best["harmless"], positive=delta_total > 0,
                loo_all_same_sign=loo_ok, years_ok=years_ok, cuts_ok=cuts_ok,
                h2_mirrors=False)
    return dict(arm=arm, powered=True, n_gated_days=len(gated), base=base,
                rows=rows, best=best, delta_total=delta_total,
                year_totals=year_totals, loo_min=(min(loo) if loo else float("nan")),
                crit=crit, verdict=verdict_for(crit))


# ════════════════════════════════════════════════════════════════════════════
# report
# ════════════════════════════════════════════════════════════════════════════

def _refusal_line(res, why):
    """The one wording for an arm that produced no statistic. NOT EVALUABLE and
    UNDERPOWERED are different refusals and must never be printed as each other."""
    if res["verdict"] == "NOT EVALUABLE":
        return ("NOT EVALUABLE — an upstream gate failed for this trigger family; "
                "no statistic was computed.")
    return f"{res['verdict']}: {why} — census printed above, NO direction quoted."


def _print_between(res, kind):
    print(f"\n  ARM {res['arm']} — {kind}")
    if not res["powered"]:
        print("    " + _refusal_line(res, f"n below the registered floor of "
                                          f"{FLOOR_TRIGGER_DATES} dates"))
        return
    print(f"    trigger {res['mean_trigger']:+.3f} (n={res['n_a']} dates)   "
          f"non-trigger {res['mean_non']:+.3f} (n={res['n_b']} dates)   "
          f"delta {res['delta']:+.3f}")
    print(f"    CI95 (date-clustered, between) [{res['ci'][0]:+.3f}, {res['ci'][1]:+.3f}]")
    _print_stability(res["st"])
    print(f"    VERDICT {res['arm']}: {res['verdict']}")


def _print_h3(res):
    print(f"\n  ARM {res['arm']} — PRIMARY: within-date paired bear vs same-day A/B long")
    if not res["powered"]:
        print("    " + _refusal_line(res, f"{res['n_paired']} paired dates against a "
                                          f"floor of {FLOOR_TRIGGER_DATES}"))
        return
    print(f"    paired dR on trigger dates    {res['paired_trigger']:+.3f} (n={res['n_a']})")
    print(f"    paired dR on non-trigger dates {res['paired_non']:+.3f} (n={res['n_b']})")
    print(f"    HEADLINE difference {res['delta']:+.3f}  "
          f"CI95 [{res['ci'][0]:+.3f}, {res['ci'][1]:+.3f}]")
    print(f"    (context, not the claim) trigger arm's own paired CI "
          f"[{res['own_ci'][0]:+.3f}, {res['own_ci'][1]:+.3f}]")
    _print_stability(res["st"])
    print(f"    VERDICT {res['arm']}: {res['verdict']}")


def _print_h4(res):
    print(f"\n  ARM {res['arm']} — do-nothing baseline (DOLLARS; the only arm that may quote $)")
    if not res["powered"]:
        print("    " + _refusal_line(res, f"{res['n_gated_days']} gated days against a "
                                          f"floor of {FLOOR_H4_DAYS}; no policy evaluated"))
        return
    b = res["base"]
    print(f"    {'policy':16s} {'f':>5s} {'total $':>12s} {'max DD $':>12s} "
          f"{'worst date $':>13s} {'unharmed':>9s}")
    print(f"    {'f=0 (baseline)':16s} {0.0:5.2f} {b['total']:>12,.0f} "
          f"{b['mdd']:>12,.0f} {b['worst']:>13,.0f} {'—':>9s}")
    for r in res["rows"]:
        print(f"    {r['policy']:16s} {r['f']:5.2f} {r['total']:>12,.0f} "
              f"{r['mdd']:>12,.0f} {r['worst']:>13,.0f} "
              f"{'YES' if r['harmless'] else 'no':>9s}")
    print(f"    best gated policy f={res['best']['f']:.2f}  "
          f"delta total ${res['delta_total']:+,.0f}  "
          f"LOO min ${res['loo_min']:+,.0f}")
    print("    years  " + "  ".join(f"{y}:${v:+,.0f}" for y, v in res["year_totals"].items()))
    print("    DISCLOSED: this reuses D5's estimator on new gates; a pass here ALONE")
    print("    can never ship, because D5's own gate family failed year-stability.")
    print(f"    VERDICT {res['arm']}: {res['verdict']}")


def _print_secondaries(book_dates, closes, opens, bear_by_date, ladder_by_date,
                       rows_by_date):
    sub("SECONDARY operationalisations — CENSUSED, NO VERDICT")
    print("  Each of these is a sensitivity or a flagged secondary. It may confirm a")
    print("  headline; it may never promote one. (Registration §Multiplicity.)")

    def census_only(label, fn):
        ds = [d for d in book_dates if fn(d)]
        bd = [d for d in ds if bear_by_date.get(d)]
        rows = sum(len(bear_by_date.get(d, ())) for d in ds)
        # H3 pairs a bear row against a LADDER-ELIGIBLE (tier A|B) long on the
        # same date, so the denominator is the deployed set, never all rows.
        paired = [d for d in ds if bear_by_date.get(d) and ladder_by_date.get(d)]
        print(TRIG.census_line(label, rows, len(ds), floor_dates=FLOOR_TRIGGER_DATES)
              + f"  bear-carrying={len(bd)}  H3-paired={len(paired)}")

    census_only(f"CHOP eff_ratio <= {CHOP_SENSITIVITY} (sensitivity)",
                lambda d: t_chop(closes, as_date(d), CHOP_SENSITIVITY))
    census_only(f"GAP g={GAP_SENSITIVITY} (sensitivity)",
                lambda d: t_gap(closes, opens, as_date(d), GAP_SENSITIVITY))
    census_only(f"GAP g={GAP_DECLARED_UNDERPOWERED} (declared UNDERPOWERED at registration)",
                lambda d: t_gap(closes, opens, as_date(d), GAP_DECLARED_UNDERPOWERED))
    for n in DECLINE_STRICT_NS:
        census_only(f"DECLINE-STRICT N={n} (verdict FIXED IN ADVANCE: UNDERPOWERED)",
                    lambda d, n=n: t_decline_strict(closes, as_date(d), n))
    print("  The strict-run arms are the operator's OWN trigger. No direction is quoted")
    print("  from them under any outcome: a strict 4-session SPY down-run occurs on ~11")
    print("  of the era's ~457 trading days and this book samples 2. Reaching a 25-date")
    print("  floor at the current emission density needs on the order of 3,000 further")
    print("  trading days. That is a sampling limit of the BOOK, not a market fact — and")
    print("  it is this study's decision-relevant output for trigger (c).")

    # The ENTRY-session gap: known only at the open of the session money moves.
    def entry_gap(d):
        dd = as_date(d)
        later = sorted(x for x in closes if x > dd)
        if not later or dd not in closes:
            return False
        nxt = later[0]
        return nxt in opens and closes[dd] > 0 and opens[nxt] >= closes[dd] * (1 + GAP_PRIMARY)

    census_only("GAP at the ENTRY session (requires an at-the-open decision)", entry_gap)

    # mech RANGE — bear_deploy D5's best post-hoc gate, deliberately NOT a primary.
    range_dates = [d for d in book_dates
                   if any(r.get("mech_direction") == "RANGE"
                          for r in rows_by_date.get(d, ()))]
    print(f"  CENSUS [mech_direction=RANGE — D5's best POST-HOC gate, FLAGGED SECONDARY]: "
          f"n_dates={len(range_dates)}  -> NO VERDICT")
    print("  Not a primary and not verdicted: re-testing D5's own gate here would be a")
    print("  disguised D5 re-run. mech_direction is also a residual category, was fitted")
    print("  for EXITS, and carried a provenance defect on 2026-08-27.")


# ════════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-bs", action="store_true",
                    help="NOT the registered population; diagnostics only")
    args = ap.parse_args()

    records, diag = load_book(include_bs=args.include_bs)
    rows = [r for r in records if r.get("R") is not None]
    bear = [r for r in rows
            if r["structure"] in BEAR_DEBIT_STRUCTURES and not r.get("credit")]
    deployed = P.top_k_per_day(rows, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)

    book_dates = sorted({str(r["date"]) for r in rows})
    bear_by_date = defaultdict(list)
    for r in bear:
        bear_by_date[str(r["date"])].append(r)
    ladder_by_date = defaultdict(list)
    for r in deployed:
        ladder_by_date[str(r["date"])].append(r)
    rows_by_date = defaultdict(list)
    for r in rows:
        rows_by_date[str(r["date"])].append(r)

    hdr("HEDGE_TIMING — pre-registered 2026-08-28 "
        "(pre-registrations/f4_deployment/hedge_timing.md)")
    print(f"  era {diag['era']}   book {len(rows)} priced rows / {len(book_dates)} dates "
          f"{diag['date_range'][0]} -> {diag['date_range'][1]}")
    print(f"  bear sleeve {len(bear)} rows / {len(bear_by_date)} dates "
          f"({', '.join(BEAR_DEBIT_STRUCTURES)}, debit only)")
    print(f"  deployed ladder {len(deployed)} rows / {len(ladder_by_date)} dates "
          f"(top-3/day, tiers A/B)")
    print(f"  outcome basis: stored R under the SHIPPED profiles "
          f"DEBIT_PROD={DEBIT_PROD} CREDIT_PROD={CREDIT_PROD}")
    print("  NO be_after variant anywhere — bear_arm B2's be_after 0.50 was reverted by")
    print("  its own rollback trigger on 2026-08-24, so pricing the sleeve under it would")
    print("  quote an exit the operator is not running.")
    print("  UNITS (G5): R only in H1-H3; dollars ONLY in H4.")

    # ── G1 ──────────────────────────────────────────────────────────────────
    sub("G1 — book calibration (lib/replay_basis.classify, via load_book)")
    dc = diag["debit_calib"]
    print(f"  debit rows {dc['n']}: exact {dc['exact']}  near-rounding-tie {dc['near']}  "
          f"boundary-tie {dc['boundary_tie']}  superseded {dc['superseded']}  hard {dc['hard']}")
    print(f"  proxy debit rows excluded (non-exact) {diag['n_proxy_excluded_non_exact']}   "
          f"credit rows admitted UNGATED {diag['n_credit_ungated']}")
    print("  boundary_tie is its OWN class (the 2026-08-27 HYG 1-ulp pt/sl tie, fixed in")
    print("  dee8201); it is reported here, never folded into `hard`.")

    # ── G2 ──────────────────────────────────────────────────────────────────
    closes, opens, cache_closes = spy_series()
    sub("G2 — the two SPY series must describe the same tape")
    xc = series_crosscheck(closes, cache_closes)
    print(f"  overlapping sessions {xc['n']}   log-return corr {xc['corr']:.5f} "
          f"(needs >= {SERIES_MIN_CORR})   same-signed direction "
          f"{xc['sign_share']:.4f} (needs >= {SERIES_MIN_SIGN_AGREE})")
    if xc["disagree"]:
        print(f"  disagreeing dates ({len(xc['disagree'])}): "
              + ", ".join(str(d) for d in xc["disagree"][:20])
              + (" ..." if len(xc["disagree"]) > 20 else ""))
    if not xc["ok"]:
        print(f"\n  G2 FAILED — {xc['why']}.")
        print("  VERDICT (all arms): NOT EVALUABLE. The mech CSV is unadjusted and the OHLC")
        print("  cache is adjusted; this gate exists to prove that difference cannot move a")
        print("  trigger, and it did not.")
        return EXIT_SERIES_MISMATCH
    print("  G2 PASSED.")

    # ── the primary triggers ────────────────────────────────────────────────
    boundary = chop_boundary(closes, book_dates)
    sub("Trigger boundaries — computed from the SPY series alone, before any R")
    print(f"  CHOP  bottom-tercile eff_ratio boundary over {len(book_dates)} book dates: "
          + (f"{boundary:.4f}" if boundary is not None else "UNCOMPUTABLE"))
    print(f"        window = EFF_WINDOW = {CHOP_WINDOW} sessions (standing constant, not swept)")
    print(f"  GAP   primary g = {GAP_PRIMARY}")
    print(f"  DECLINE-BROAD  >= {DECLINE_BROAD_K} lower closes of the last "
          f"{DECLINE_BROAD_WINDOW} sessions ending at D")

    if boundary is None:
        print("\n  CHOP boundary uncomputable from the series — ARM H1-CHOP / ARM H2-CHOP /")
        print("  ARM H3-CHOP / ARM H4-CHOP are NOT EVALUABLE.")

    trigger_fns = {
        "CHOP": (lambda d: boundary is not None and t_chop(closes, as_date(d), boundary)),
        "GAP": (lambda d: t_gap(closes, opens, as_date(d), GAP_PRIMARY)),
        "DECLINE": (lambda d: t_decline_broad(closes, as_date(d))),
    }
    evaluable = {"CHOP": boundary is not None, "GAP": True, "DECLINE": True}

    # ── ARM H0 ──────────────────────────────────────────────────────────────
    hdr("ARM H0 — POWER CENSUS (runs first; no outcome column is read)")
    print("  Counts only. Every arm below early-returns UNDERPOWERED off this census")
    print("  without computing a statistic, so a floor failure never reaches a number.")
    print(f"  Floors: {FLOOR_TRIGGER_DATES} trigger DATES per date-clustered arm, "
          f"{FLOOR_ROWS} ROWS for any row-level cell, {FLOOR_H4_DAYS} gated DAYS for H4.")
    censuses = {}
    for fam in FAMILIES:
        sub(f"{fam} (primary operationalisation)")
        cen = h0_census(fam, trigger_fns[fam], book_dates, bear_by_date, ladder_by_date)
        censuses[fam] = cen
        print_census(cen)

    print("\n  PLAN-TIME COUNTS vs THIS RUN. The registration's census table came from a")
    print("  script that APPROXIMATES load_book (it omits Trade() construction failures")
    print("  and the proxy calibration gate). The numbers above are the load_book-derived")
    print("  truth; any discrepancy against the registration table is a property of that")
    print("  approximation and must be explained in the write-up, never silently accepted.")

    _print_secondaries(book_dates, closes, opens, bear_by_date, ladder_by_date,
                       rows_by_date)

    # ── the verdicted arms ──────────────────────────────────────────────────
    dep_dollars = daily_dollars(deployed)
    sleeve = sleeve_pick(bear_by_date)
    results = {}
    for fam in FAMILIES:
        cen = censuses[fam]
        ev = evaluable[fam]
        hdr(f"{fam} — the three verdicted arms")
        h1 = h1_between(bear_by_date, cen, ev)
        h2 = h2_between(ladder_by_date, cen, ev)
        _print_between(h1, "between-date separation of BEAR R (NOT primary — confounded)")
        _print_between(h2, "beta control: the same separation on the DEPLOYED LADDER")
        mirrors = h2_mirror(h1.get("delta", float("nan")), h2.get("delta", float("nan")))
        print(f"\n  h2_mirrors = {mirrors}  (|H2 delta| >= 0.5 x |H1 delta|, opposite-signed)")
        if mirrors and h1.get("powered"):
            h1["crit"]["h2_mirrors"] = True
            h1["verdict"] = verdict_for(h1["crit"])
            print(f"    -> ARM {h1['arm']} re-read as {h1['verdict']}")

        h3 = h3_paired(bear_by_date, ladder_by_date, cen, ev)
        if h3.get("powered") and mirrors:
            h3["crit"]["h2_mirrors"] = True
            h3["verdict"] = verdict_for(h3["crit"])
        _print_h3(h3)

        h4 = h4_portfolio(dep_dollars, sleeve, cen, ev)
        _print_h4(h4)
        results[fam] = dict(h1=h1, h2=h2, h3=h3, h4=h4, mirrors=mirrors)

    # ── verdict block ───────────────────────────────────────────────────────
    hdr("VERDICT (pre-registered grammar, pre-registrations/f4_deployment/hedge_timing.md)")
    survivors = 0
    for fam in FAMILIES:
        r = results[fam]
        for key in ("h1", "h3", "h4"):
            v = r[key]["verdict"]
            print(f"  ARM {r[key]['arm']:14s} : {v}")
            if v == "TIMING-CANDIDATE":
                survivors += 1
        print(f"  ARM {r['h2']['arm']:14s} : {r['h2']['verdict']}   (control, not a headline)")
    print(f"\n  headline tests: {HEADLINE_TESTS} (3 families x H1/H3/H4, fixed at registration)")
    print(f"  TIMING-CANDIDATE survivors: {survivors}  "
          f"(~{0.05 * HEADLINE_TESTS:.2f} expected by chance at 5%)")
    print("  Sensitivities and secondaries carry NO verdict and may never promote one.")
    print("\n  NOTHING SHIPS FROM THIS STUDY UNDER ANY OUTCOME. A TIMING-CANDIDATE queues an")
    print("  independent-window confirmation; a CONTRARY drafts a deployment-rules §4")
    print("  prohibition and HOLDS it for the operator; an all-NULL/UNDERPOWERED read adds")
    print("  one subtraction sentence to §4 plus the standing census finding that the")
    print("  4-5-day streak rule is not testable at this book's emission density.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
