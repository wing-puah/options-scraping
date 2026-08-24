"""Does entry TIMING degrade a play — re-emission (ARM P) or fill lag (ARM L)?

PRE-REGISTERED 2026-08-19 in research/pre-registrations/f1_selection/emission_timing.md
BEFORE this file was written. Read that file first; nothing here may drift from
it. In brief:

  ARM P (persistence)  first emission = the earliest signal DATE per
       (ticker, structure) in the era book; ordinal capped {1,2,3,4+}. The
       estimand is the WITHIN-DATE paired Delta(mean R), repeat minus first,
       computed inside each date that carries BOTH, aggregated by
       `protocol.boot_ci_paired_by_date`. Frozen sub-cuts: consecutive-date
       repeats vs gapped; repeats split by whether the underlying had already
       moved the play's way since first emission (SRC_OHLC / SRC_TILDE split
       PRINTED, never pooled).
  ARM L (fill lag)     a synthetic `Trade` per lag L in {0,1,2,3} replayed
       through the FROZEN `harness.replay` under the SHIPPED exit profiles.
       L = 0 (a day-0 CLOSE fill) is the BASELINE for every comparison, so the
       close-vs-open basis cancels and the estimand is lag-only; the stored
       book prints as a REFERENCE line only. Reported pooled and within
       pre-signal `price_vector` terciles cut on the FULL book and FROZEN.

Admissibility: selection reopens on NEW COLUMNS ONLY, and this study introduces
exactly two — the emission ordinal and the pre-signal `price_vector`. The day-0
underlying move is NOT re-tested here under any arm; `next_day_move` ARM C
stands. Gate G3 enforces that by assertion, not by intention.

Gates, in order: G0 POWER (>= MIN_AFFECTED_DATES affected DATES per cell, the
per-tercile lag cells checked INDIVIDUALLY; a cell under the floor is
UNDERPOWERED, printed with its n, and no criterion is evaluated on it) ->
G1 CONSTRUCTION (every synthetic satisfies len(marks) == len(grid); ANY
construction failure FAILS the run non-zero; the padded-row count prints) ->
G2 SIZING CENSUS (contract distribution per lag; NO dollar figure is quoted
across lags anywhere) -> G3 NO-DAY-0-MOVE ASSERTION (frozen conditioning
allowlist + an assertion that every bar-derived conditioning value reads only
sessions on or before the SIGNAL date).

Verdicts, worded in the registration: STALE-ENTRY-PENALTY (candidate intake
rule, queued for an independent window — never a ship) / LAG-TOLERANT
(publishable operational finding) / LAG-SENSITIVE / NULL / UNDERPOWERED.

R is quoted, never dollars, across lags or ordinals. No annualised figure,
Sharpe, or time-to-recover anywhere. Worst-decile cells are FORBIDDEN as
criteria and are not computed.
"""
from __future__ import annotations

import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest.helpers import _max_loss_per_unit, _weekday_grid  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import prod_profile_for  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402
from scripts.backtest_study.lib.book import CREDIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import PATH_CAP_DAYS, Trade, replay  # noqa: E402

# The runner promotes -latest.txt on these codes instead of deleting it. It
# finds this by AST parse, so it must stay a PLAIN SET LITERAL — a
# frozenset(...) call is invisible to ast.literal_eval and the refusal would be
# misfiled as a failure. {2, 3} are `lib/era.py`'s two refusals (thin era /
# era mismatch); nothing else in this module is a designed refusal — a gate
# failure here is a REAL failure and must delete the report.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# The repo's standing date-level power floor (selection_order.MIN_AFFECTED_DATES,
# declared 2026-08-13 before any count here was knowable), restated by the
# pre-registration as G0's floor.
MIN_AFFECTED_DATES = 25

# FROZEN by the pre-registration. May not grow after any result is seen.
LAGS = (0, 1, 2, 3)
ORDINAL_CAP = 4
N_TERCILES = 3
BOOT_SEED = 20260819

# G3 — the FROZEN allowlist of conditioning variables. Every cut in this module
# routes its key through `assert_conditioning`, so a future arm cannot quietly
# start conditioning on something the registration did not name. The day-0
# underlying move is deliberately ABSENT: `next_day_move` ARM C tested it, that
# result stands, and re-testing it under a new study name would be a second
# look at a closed question.
CONDITIONING_ALLOWLIST = frozenset({
    "emission_ordinal",        # ARM P: 1st / 2nd / 3rd / 4th+
    "emission_gap",            # ARM P sub-cut 1: consecutive vs gapped repeat
    "pre_signal_move",         # ARM P sub-cut 2: move since FIRST emission
    "price_vector_tercile",    # ARM L conditioning
})

# Structure direction for the "did the underlying already move the play's way"
# sub-cut. The registration words it "bull_* = up, bear_* = down"; `long_call` /
# `long_put` carry no such prefix and are mapped explicitly because their
# direction is unambiguous. Everything else (straddle / strangle / short_put)
# has NO single direction and is excluded from that cut and counted — never
# assigned a guess.
STRUCTURE_SIGN = {
    "bull_call_spread": +1, "bull_put_spread": +1, "long_call": +1,
    "bear_put_spread": -1, "bear_call_spread": -1, "long_put": -1,
}

# Production sizing constants, transcribed from config/backtest.yml
# (simulation.portfolio_value / risk_per_trade_pct / stop_loss). The same two
# numbers are what `harness.MAX_LOSS_ABS` is built from, which is why sizing is
# not cosmetic here — see `size_contracts`.
PORTFOLIO_VALUE = 50000.0
RISK_PER_TRADE_PCT = 0.02
DEBIT_STOP_LOSS = 0.75

# Quoted in ARM L's reference line so a reader can see WHY the stored book and
# the L = 0 close-fill baseline land close together, without the study leaning
# on it: research/archive/11-exit-conditioning.md section 6 (the next_day_move
# study's clean null) measured the signal-close -> entry-open gap at an overall
# mean of +0.06% (-0.01 sigma) across 787 rows.
OVERNIGHT_GAP_NOTE = ("recorded prior finding (research/archive/11-exit-conditioning.md "
                      "s6): the signal-close -> entry-open gap means +0.06% (-0.01 sigma) "
                      "on this book — quoted for context, nothing here rests on it")


def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


def n_dates(rows) -> int:
    return len({str(r["date"]) for r in rows})


def fail(msg: str) -> None:
    """A REAL failure (not a designed refusal): the run must exit non-zero and
    the runner must delete `-latest.txt`."""
    print(f"\n*** GATE FAILURE: {msg} ***")
    sys.exit(1)


def assert_conditioning(name: str) -> str:
    """G3 — every conditioning variable must be on the frozen allowlist."""
    if name not in CONDITIONING_ALLOWLIST:
        fail(f"G3: conditioning variable {name!r} is not on the frozen allowlist "
             f"{sorted(CONDITIONING_ALLOWLIST)}. The day-0 underlying move is "
             f"closed (next_day_move ARM C) and may not be reopened here.")
    return name


# ── G3 helper: bar reads that cannot see past the signal date ────────────────

def close_asof(bars: dict, d: _date, signal_date: _date):
    """`(close, source, bar_date)` for the last session on or before `d`.

    G3 ASSERTION, not a convention: the bar actually used must be on or before
    the SIGNAL date. Every conditioning value in this module that touches the
    underlying goes through here, so no arm can read the signal day's own
    forward move without tripping the gate.
    """
    if d > signal_date:
        fail(f"G3: a conditioning read asked for a bar at {d}, after the signal "
             f"date {signal_date}. No arm may read a post-signal underlying move.")
    if not bars:
        return None, None, None
    if d in bars:
        b = bars[d]
        return b.c, b.source, d
    earlier = [x for x in bars if x <= d]
    if not earlier:
        return None, None, None
    used = max(earlier)
    if used > signal_date:              # unreachable by construction; asserted anyway
        fail(f"G3: resolved bar {used} is after the signal date {signal_date}.")
    return bars[used].c, bars[used].source, used


# ── ARM P: emission index ────────────────────────────────────────────────────

def emission_index(recs: list[dict]) -> dict:
    """Attach the emission ordinal and its companions to every record.

    Ordinal is the rank of the row's signal DATE among the DISTINCT signal dates
    that (ticker, structure) appears on in the era book. Ranking distinct DATES
    is the same-day duplicate guard the registration froze: `book.py`'s
    analysis join already collapses duplicate emissions with
    `created_datetime`-sorted keep-first, and ranking dates rather than rows
    means a session that still carries two rows for one (ticker, structure)
    contributes ONE ordinal step and cannot fake a repeat. Without this a single
    duplicated session would manufacture the entire effect.

    `consecutive` = the previous emission of that (ticker, structure) fell on
    the IMMEDIATELY PRECEDING date present in the era book. The book is the
    session calendar here — the repo has no holiday calendar — so this is the
    "re-emitted the very next session we have" cut. The stricter calendar
    next-weekday count prints alongside as a diagnostic; it is not the cut.
    """
    assert_conditioning("emission_ordinal")
    assert_conditioning("emission_gap")

    book_dates = sorted({r["date"] for r in recs})
    date_ix = {d: i for i, d in enumerate(book_dates)}

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in recs:
        groups[(r["ticker"], r["structure"])].append(r)

    dup_groups = Counter()
    for key, rows in groups.items():
        per_date = Counter(r["date"] for r in rows)
        for d, c in per_date.items():
            if c > 1:
                dup_groups[(key, d)] = c
        dates = sorted(per_date)
        rank = {d: i + 1 for i, d in enumerate(dates)}
        for r in rows:
            k = rank[r["date"]]
            r["emission_ordinal"] = k
            r["emission_ordinal_capped"] = min(k, ORDINAL_CAP)
            r["first_emission_date"] = dates[0]
            r["prev_emission_date"] = dates[k - 2] if k > 1 else None
            r["n_emissions"] = len(dates)

    n_consecutive = 0
    n_next_weekday = 0
    for r in recs:
        prev = r["prev_emission_date"]
        if prev is None:
            r["consecutive"] = None
            r["gap_book_sessions"] = None
            continue
        gap = date_ix[r["date"]] - date_ix[prev]
        r["gap_book_sessions"] = gap
        r["consecutive"] = gap == 1
        n_consecutive += int(gap == 1)
        d = _date.fromisoformat(prev)
        while True:
            d = _date.fromordinal(d.toordinal() + 1)
            if d.weekday() < 5:
                break
        n_next_weekday += int(d.isoformat() == r["date"])

    return {
        "n_pairs": len(groups),
        "dup_rows": sum(c - 1 for c in dup_groups.values()),
        "dup_cells": len(dup_groups),
        "n_consecutive": n_consecutive,
        "n_next_weekday": n_next_weekday,
    }


def paired_by_date(rows: list[dict], is_repeat, is_first=None) -> list[dict]:
    """WITHIN-DATE paired rows: one entry per date carrying BOTH sides.

    `a` = mean R of the repeat side inside the date, `b` = mean R of the first
    side, `d` = a - b. Handing `protocol.boot_ci_paired_by_date` one row per
    date makes its date-clustered resample reproduce exactly the registered
    estimand: the mean over dates of the within-date delta. This is
    `bear_deploy`'s D4 method, chosen because it cancels the date's own return
    level — the dominant nuisance variable in this book.
    """
    if is_first is None:
        def is_first(r):
            return r["emission_ordinal_capped"] == 1
    by: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    for r in rows:
        if r.get("R") is None:
            continue
        if is_repeat(r):
            by[r["date"]][0].append(float(r["R"]))
        elif is_first(r):
            by[r["date"]][1].append(float(r["R"]))
    out = []
    for d in sorted(by):
        rep, fst = by[d]
        if not rep or not fst:
            continue
        a, b = statistics.fmean(rep), statistics.fmean(fst)
        out.append(dict(date=d, a=a, b=b, d=a - b, n_a=len(rep), n_b=len(fst)))
    return out


# ── the full conjunction ─────────────────────────────────────────────────────

def _ex_both(paired):
    months = {m for ms in P.DOMINANT_WINDOWS.values() for m in ms}
    return [p for p in paired if str(p["date"])[:7] not in months]


def conjunction(label: str, paired: list[dict], tier_paired: dict[str, list],
                min_dates: int = MIN_AFFECTED_DATES) -> dict | None:
    """The registration's SIX-part bar, all of it, printed pass/fail.

      1. paired date-clustered bootstrap CI excluding zero (BOOT_N, alpha .05)
      2. every LOO-by-date fold on the point estimate's side (read `min_gain`)
      3. survives `protocol.window_cuts` AND the ex-BOTH cut added BY HAND —
         `window_cuts()` drops one window at a time, and the vol_sleeve straddle
         died precisely in the gap that leaves
      4. positive in every calendar year present (`sign_stable`)
      5. right-signed on BOTH pricing tiers (real and tweak)
      6. >= `min_dates` affected dates, re-checked on the evaluated set

    Failing any one is failing. Returns None when the cell is UNDERPOWERED.
    """
    nd = n_dates(paired)
    if nd < min_dates:
        print(f"  {label:<44} n={len(paired):>4} pairs / {nd:>3}d  "
              f"UNDERPOWERED (floor {min_dates}) — census only, no criterion read")
        return None
    point = statistics.fmean(p["d"] for p in paired)
    sgn = 1 if point > 0 else -1
    lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=P.BOOT_N, seed=BOOT_SEED)
    ci_ok = bool(lo > 0 or hi < 0)
    _, share, min_gain, nfolds = P.loo_by_date(paired, lambda p: p["a"], lambda p: p["b"])
    loo_ok = bool(share == 1.0) if sgn > 0 else bool(share == 0.0)

    cuts = P.window_cuts(paired)
    cuts["ex_BOTH"] = _ex_both(paired)
    cut_means = {}
    cuts_ok = True
    for name, rows in cuts.items():
        if not rows:
            cut_means[name] = float("nan")
            cuts_ok = False
            continue
        m = statistics.fmean(p["d"] for p in rows)
        cut_means[name] = m
        if (m > 0) != (sgn > 0):
            cuts_ok = False

    stable, npos, ymeans = P.sign_stable(paired, key="d")
    years_ok = bool(stable and ymeans
                    and all((m > 0) == (sgn > 0) for m in ymeans.values()))

    tier_means = {}
    tiers_ok = True
    for t in ("real", "tweak"):
        rows = tier_paired.get(t) or []
        if not rows:
            tier_means[t] = float("nan")
            tiers_ok = False
            continue
        m = statistics.fmean(p["d"] for p in rows)
        tier_means[t] = m
        if (m > 0) != (sgn > 0):
            tiers_ok = False

    candidate = all([ci_ok, loo_ok, cuts_ok, years_ok, tiers_ok, nd >= min_dates])
    star = "  ** CANDIDATE" if candidate else ""
    print(f"\n  {label}")
    print(f"    n={len(paired)} pairs / {nd} dates   mean delta {point:+.4f}   "
          f"CI[{lo:+.4f},{hi:+.4f}] {'EXCLUDES 0' if ci_ok else 'includes 0'}{star}")
    print(f"    1 CI excludes zero      : {'PASS' if ci_ok else 'FAIL'}")
    print(f"    2 LOO every fold signed : {'PASS' if loo_ok else 'FAIL'}  "
          f"(share_positive {share:.3f}, min_gain {min_gain:+.4f}, folds {nfolds})")
    cut_s = "  ".join(f"{k} {v:+.4f}" for k, v in cut_means.items())
    year_s = "  ".join(f"{y} {m:+.4f}" for y, m in ymeans.items())
    tier_s = "  ".join(f"{k} {v:+.4f}" for k, v in tier_means.items())
    print(f"    3 window cuts + ex-BOTH : {'PASS' if cuts_ok else 'FAIL'}  {cut_s}")
    print(f"    4 sign stable by year   : {'PASS' if years_ok else 'FAIL'}  {year_s}")
    print(f"    5 both pricing tiers    : {'PASS' if tiers_ok else 'FAIL'}  {tier_s}")
    print(f"    6 >= {min_dates} affected dates : "
          f"{'PASS' if nd >= min_dates else 'FAIL'}  ({nd})")
    return dict(point=point, lo=lo, hi=hi, ci_ok=ci_ok, loo_ok=loo_ok,
                cuts_ok=cuts_ok, years_ok=years_ok, tiers_ok=tiers_ok,
                n_dates=nd, n_pairs=len(paired), candidate=candidate)


# ── ARM L: the lag-L synthetic ───────────────────────────────────────────────

def size_contracts(entry_net: float, legs: list) -> int:
    """Production fixed-fractional sizing, ported from `simulate.py::_size_contracts`.

    THIS IS NOT COSMETIC, and the reason is worth stating where the code is:
    `harness.replay`'s dollar_stop fires on `t.dollars(pl) = pl * |entry| * 100 *
    contracts <= -MAX_LOSS_ABS`, so the CONTRACT COUNT decides at what R the
    dollar stop bites. Leaving the stored count on a synthetic whose entry price
    moved would drift that threshold with the lag and the ladder would be
    measuring a sizing artifact instead of the lag. Re-sizing at the lagged entry
    price holds the dollar stop at the same effective R (~ -0.75 on the debit
    side, where `floor(1000 / (entry*100*0.75))` makes `entry*100*contracts` land
    just under 1000/0.75), so every rung of the ladder is stopped on the same
    rule. G2 prints the resulting census; no dollar figure is quoted across lags.
    """
    dollar_risk = PORTFOLIO_VALUE * RISK_PER_TRADE_PCT
    if entry_net < 0:                       # credit: STRUCTURAL max loss
        mlpu = _max_loss_per_unit(legs, entry_net)
        if mlpu is not None and mlpu > 0:
            return max(1, math.floor(dollar_risk / (mlpu * 100)))
        return 1                            # unbounded / uncomputable -> 1, as production
    loss_per_contract = entry_net * 100 * DEBIT_STOP_LOSS
    if loss_per_contract <= 0:
        return 1
    return max(1, math.floor(dollar_risk / loss_per_contract))


def synth_trade(rec: dict, lag: int) -> tuple[Trade | None, int, str]:
    """`(Trade, n_padded_fields, status)` for the lag-`lag` synthetic.

    THE OFF-BY-ONE, RESOLVED AND DOCUMENTED. `Trade` builds its grid as
    `_weekday_grid(signal_date, end)` — "weekdays AFTER the signal date" — so
    `grid[0]` is already the fill session and `marks[i]` is the mark on
    `grid[i]`. A lag-L fill at `marks[L]` therefore has to be anchored so that
    the recomputed grid STARTS at `grid[L]`, which means the synthetic's
    `signal_date` is `grid[L-1]` (and the ORIGINAL signal date at L = 0), not
    `grid[L]`. Anchoring at `grid[L]` would make the recomputed grid start at
    `grid[L+1]` while the marks start at `grid[L]` — every mark shifted one
    session late, and `len(marks) == len(grid)` off by one on every
    non-truncated row, which is G1 failing for a construction bug rather than a
    data one.

    With the anchor at `grid[L-1]`:
      signal_date   <- grid[L-1]  (L = 0: unchanged)
      entry         <- marks[L]   (a day-L CLOSE fill)
      daily_price_csv <- marks[L:], right-padded with EMPTY fields
      dte_entry     <- reduced by the calendar days the ANCHOR moved, so the
                       time-exit clock and its threshold stay on the same basis
                       (L = 0 therefore reproduces the stored trade's timing
                       exactly, and differs from it ONLY in the fill price)
      contracts     <- re-sized by the production formula at the lagged entry

    PADDING. 262 of 795 v3 rows are 120-day cap-truncated, so for those the
    recomputed grid for a LATER anchor runs further than the stored path and the
    mark list must be right-padded with blanks. That is behaviour-neutral —
    `replay` skips a `None` mark, and the shipped profiles cannot fire on one —
    whereas DROPPING the truncated rows would bias the population toward
    short-dated trades, which is exactly the population the lag question is most
    sensitive to. The padded-row count PRINTS in G1. The padding is only ever
    additive: `end_new >= end_old` always, so a negative pad is a construction
    bug and fails the run.
    """
    t = rec["t"]
    grid, marks = t.grid, t.marks
    if lag >= len(marks):
        return None, 0, "grid_shorter_than_lag"
    entry = marks[lag]
    if entry is None:
        return None, 0, "no_mark_at_lag"
    if entry == 0.0:
        return None, 0, "degenerate_zero_entry"

    anchor = t.signal_date if lag == 0 else grid[lag - 1]
    shift = (anchor - t.signal_date).days
    new_dte = int(t.dte_entry) - shift
    if new_dte <= 0:
        return None, 0, "dte_exhausted"

    nearest = min((leg.expiration - anchor).days for leg in t.legs)
    end = anchor + timedelta(days=min(nearest, PATH_CAP_DAYS))
    new_grid = _weekday_grid(anchor, end)
    path = marks[lag:]
    pad = len(new_grid) - len(path)
    if pad < 0:
        fail(f"G1: {rec['ticker']} {rec['date']} lag {lag}: recomputed grid "
             f"({len(new_grid)}) is SHORTER than the remaining marks "
             f"({len(path)}) — padding can only ever be additive.")

    csv_path = ",".join("" if m is None else f"{m:.10g}" for m in path)
    if pad:
        csv_path += "," * pad

    row = dict(t.row)
    row["signal_date"] = anchor.isoformat()
    row["entry_option_price"] = f"{entry:.10g}"
    row["dte_entry"] = str(new_dte)
    row["contracts"] = str(size_contracts(entry, t.legs))
    row["daily_price_csv"] = csv_path
    try:
        st = Trade(row)
    except (AssertionError, ValueError, KeyError) as exc:
        fail(f"G1: Trade construction failed for {rec['ticker']} {rec['date']} "
             f"lag {lag}: {exc!r}. A silently dropped row would make the lag "
             f"ladder a comparison between different populations.")
        return None, 0, "unreachable"
    return st, pad, "ok"


def profile_for(rec: dict) -> dict:
    """The SHIPPED exit profile for this row: the debit merge (base ->
    structure_exit -> regime_exit) via `bear_giveback.prod_profile_for` at the
    shipped be_after 0.50 suppressed in BEAR_HE, or `book.CREDIT_PROD`."""
    return dict(CREDIT_PROD) if rec["credit"] else prod_profile_for(rec, 0.50, True)


# ── gates ────────────────────────────────────────────────────────────────────

def coverage(recs: list[dict], diag: dict) -> None:
    hdr("COVERAGE — the denominators every number below is quoted against")
    print(f"  era={diag['era']}  rows={len(recs)}  dates={diag['n_dates']}  "
          f"range={diag['date_range']}  counts_by_source={diag['counts_by_source']}")
    print(f"  pricing tiers (returned): {dict(Counter(r['source'] for r in recs))}")
    print(f"  debit calibration: {diag['debit_calib']}")
    print(f"  credit rows admitted UNGATED (calibrated=False): "
          f"{diag['n_credit_ungated']}")
    print("  CREDIT-UNGATED CAVEAT: there is no single credit PROD that calibrates "
          "this sheet\n    (Attempt 13 removed the credit stop mid-book), so credit rows "
          "carry calibrated=False\n    and every credit-side number here is unvalidated "
          "until the book is split per credit-stop era.")
    struct_s = "  ".join(f"{k}={v}" for k, v in
                         Counter(r["structure"] for r in recs).most_common())
    print(f"  structures: {struct_s}")


def g3_selftest() -> None:
    hdr("G3 — NO-DAY-0-MOVE ASSERTION (runs first; it is a guard, not a report)")
    print(f"  frozen conditioning allowlist: {sorted(CONDITIONING_ALLOWLIST)}")
    print("  Every conditioning key in this module is routed through "
          "assert_conditioning(),\n  and every bar-derived value through "
          "close_asof(), which FAILS THE RUN if the session it\n  resolves is "
          "after the SIGNAL date. The day-0 underlying move is therefore not "
          "merely\n  unused here — it is unreachable. next_day_move ARM C "
          "stands and is NOT re-tested.")
    for name in sorted(CONDITIONING_ALLOWLIST):
        assert_conditioning(name)
    probe = {_date(2026, 1, 5): U.Bar(c=10.0, source=U.SRC_OHLC)}
    c, src, used = close_asof(probe, _date(2026, 1, 5), _date(2026, 1, 5))
    if c != 10.0 or used != _date(2026, 1, 5):
        fail("G3 self-test: close_asof did not resolve an on-signal-date bar.")
    print("  G3 self-test: allowlist membership OK; close_asof resolves an "
          "on-signal-date bar OK.")


def terciles_full_book(recs: list[dict]) -> tuple[float, float] | None:
    """`price_vector` terciles cut on the FULL book and FROZEN before any lag
    result is read — not re-cut per lag, which would make the cells move under
    the comparison.

    THE NaN-TERCILE TRAP, guarded explicitly: `price_vector` comes off the
    pandas AnalysisClaude join, so a missing cell arrives as float('nan'), which
    sorts to a tercile EDGE silently and corrupts both cut points (2026-08-12:
    71 NaN iv_pct rows swept 69% of the population into the "bottom" tercile).
    The filter is `v == v` on the raw value, applied BEFORE the cut, and the
    excluded rows become their own printed cell — never imputed, never folded
    into a tercile.
    """
    assert_conditioning("price_vector_tercile")
    vals = sorted(float(r["price_vector"]) for r in recs
                  if r.get("price_vector") is not None
                  and float(r["price_vector"]) == float(r["price_vector"]))
    if len(vals) < 9:
        return None
    return vals[len(vals) // N_TERCILES], vals[2 * len(vals) // N_TERCILES]


def tercile_of(rec: dict, cuts) -> str:
    v = rec.get("price_vector")
    if cuts is None or v is None or float(v) != float(v):
        return "MISSING"
    v = float(v)
    return "T1_low" if v <= cuts[0] else ("T2_mid" if v <= cuts[1] else "T3_high")


def g0(recs: list[dict], em: dict, cuts) -> dict:
    hdr("G0 — POWER CENSUS (runs FIRST and blocks every read below)")
    print(f"  floor: {MIN_AFFECTED_DATES} affected DATES per cell "
          f"(selection_order.MIN_AFFECTED_DATES; pre-registered).")
    print("  The per-tercile lag cells must clear the floor INDIVIDUALLY — a "
          "pooled pass does\n  not license a tercile read. A cell under the "
          "floor is UNDERPOWERED: its n prints and\n  NO criterion is "
          "evaluated on it.")

    sub("ARM P — emission ordinal census")
    ordc = Counter(r["emission_ordinal_capped"] for r in recs)
    ord_s = "  ".join(f"{k if k < ORDINAL_CAP else '4+'}={ordc.get(k, 0)}"
                      for k in range(1, ORDINAL_CAP + 1))
    print(f"  ordinal (capped at 4+): {ord_s}")
    print(f"  distinct (ticker, structure) pairs: {em['n_pairs']}")
    print(f"  same-day duplicate emissions collapsed by the date-rank guard: "
          f"{em['dup_rows']} extra rows across {em['dup_cells']} (pair, date) cells")
    print(f"  consecutive-date repeats (previous emission on the immediately "
          f"preceding BOOK\n    session): {em['n_consecutive']}   "
          f"[stricter calendar next-weekday count: {em['n_next_weekday']}, "
          f"diagnostic only]")
    gapped = sum(1 for r in recs if r.get("consecutive") is False)
    print(f"  gapped repeats: {gapped}")

    paired = paired_by_date(recs, lambda r: r["emission_ordinal_capped"] > 1)
    nd_p = n_dates(paired)
    print(f"  dates carrying BOTH a first and a repeat emission: {nd_p} of "
          f"{len({r['date'] for r in recs})}  "
          f"{'POWERED' if nd_p >= MIN_AFFECTED_DATES else 'UNDERPOWERED'}")

    sub("ARM L — lag priceability census (before any Trade is built)")
    for L in LAGS:
        ok = sum(1 for r in recs
                 if L < len(r["t"].marks) and r["t"].marks[L] not in (None, 0.0))
        print(f"  lag {L}: {ok}/{len(recs)} rows carry a usable mark")

    sub("ARM L — pre-signal price_vector terciles (cut on the FULL book, FROZEN)")
    if cuts is None:
        print("  price_vector too sparse to cut terciles — every tercile cell is "
              "UNDERPOWERED.")
    else:
        print(f"  cut points: T1 <= {cuts[0]:+.4f} < T2 <= {cuts[1]:+.4f} < T3")
    tc = Counter(tercile_of(r, cuts) for r in recs)
    powered = {}
    for name in ("T1_low", "T2_mid", "T3_high", "MISSING"):
        rows = [r for r in recs if tercile_of(r, cuts) == name]
        nd = n_dates(rows)
        powered[name] = nd >= MIN_AFFECTED_DATES
        print(f"  {name:<9} n={tc.get(name, 0):>4} / {nd:>3} dates  "
              f"{'POWERED' if powered[name] else 'UNDERPOWERED (census only)'}")
    print("  MISSING is its own cell by registration — never imputed, never "
          "folded into a tercile.")
    powered["_ARM_P"] = nd_p >= MIN_AFFECTED_DATES
    return powered


def g1(recs: list[dict]) -> tuple[dict, dict]:
    hdr("G1 — CONSTRUCTION (any Trade construction failure FAILS the run)")
    synths: dict[int, dict[int, dict]] = {L: {} for L in LAGS}
    excl = {L: Counter() for L in LAGS}
    pad_rows = {L: 0 for L in LAGS}
    pad_fields = {L: 0 for L in LAGS}
    for r in recs:
        for L in LAGS:
            st, pad, status = synth_trade(r, L)
            if st is None:
                excl[L][status] += 1
                continue
            if len(st.marks) != len(st.grid):     # belt and braces: Trade asserts it too
                fail(f"G1: len(marks) != len(grid) survived Trade construction for "
                     f"{r['ticker']} {r['date']} lag {L}.")
            if pad:
                pad_rows[L] += 1
                pad_fields[L] += pad
            synths[L][id(r)] = dict(t=st, pad=pad, contracts=st.contracts,
                                    entry=st.entry_net)
    for L in LAGS:
        print(f"  lag {L}: {len(synths[L])} synthetics built, "
              f"{sum(excl[L].values())} excluded {dict(excl[L]) or '{}'}   "
              f"padded rows {pad_rows[L]} ({pad_fields[L]} blank fields)")
    print("  Every synthetic satisfies len(marks) == len(grid) (Trade asserts it, "
          "and the\n  assertion is re-checked here). Padding is right-padding "
          "with EMPTY fields only:\n  replay skips a None mark, so the shipped "
          "profiles cannot fire on one.")

    common = [r for r in recs if all(id(r) in synths[L] for L in LAGS)]
    print(f"\n  EVALUATED POPULATION: {len(common)}/{len(recs)} rows constructible "
          f"at ALL of {list(LAGS)}\n    ({len(recs) - len(common)} excluded and "
          f"counted above). One population across the whole ladder,\n    so no "
          f"rung is compared against a different book.")
    return synths, dict(common=common, excl=excl, pad_rows=pad_rows)


def g2(recs: list[dict], synths: dict, common: list[dict]) -> None:
    hdr("G2 — SIZING CENSUS (contracts per lag; NO dollar figure is quoted "
        "across lags, anywhere)")
    print(f"  {'lag':<5}{'n':>5}{'mean':>9}{'median':>9}{'min':>6}{'max':>6}"
          f"{'== stored':>11}")
    stored = [int(r["t"].contracts) for r in common]
    print(f"  {'book':<5}{len(stored):>5}{statistics.fmean(stored):>9.2f}"
          f"{statistics.median(stored):>9.1f}{min(stored):>6}{max(stored):>6}"
          f"{'—':>11}   (stored counts, REFERENCE only)")
    for L in LAGS:
        cs = [synths[L][id(r)]["contracts"] for r in common]
        same = sum(1 for r in common
                   if synths[L][id(r)]["contracts"] == int(r["t"].contracts))
        print(f"  {L:<5}{len(cs):>5}{statistics.fmean(cs):>9.2f}"
              f"{statistics.median(cs):>9.1f}{min(cs):>6}{max(cs):>6}{same:>11}")
    print("  Contracts are re-sized by the production formula at each lagged "
          "entry price so the\n  harness dollar_stop keeps biting at the same R "
          "on every rung — see size_contracts().")


# ── ARM P ────────────────────────────────────────────────────────────────────

def _tiers(rows, build):
    return {t: build([r for r in rows if r["source"] == t]) for t in ("real", "tweak")}


def arm_p(recs: list[dict], powered: dict) -> dict:
    hdr("ARM P — EMISSION PERSISTENCE (within-date paired Delta(mean R), "
        "repeat minus first)")
    print("  Estimand: inside each date carrying BOTH, mean R(repeats) - "
          "mean R(firsts);\n  aggregated by protocol.boot_ci_paired_by_date over "
          "DATES. A negative delta is the\n  'the signal is stale' hypothesis; a "
          "positive one is 'confirmation'.")

    sub("ordinal census with descriptive means (NOT a criterion)")
    for k in range(1, ORDINAL_CAP + 1):
        rows = [r for r in recs if r["emission_ordinal_capped"] == k
                and r.get("R") is not None]
        if not rows:
            continue
        label = f"{k}" if k < ORDINAL_CAP else "4+"
        print(f"  ordinal {label:<3} n={len(rows):>4} / {n_dates(rows):>3}d  "
              f"mean R {statistics.fmean(float(r['R']) for r in rows):+.4f}  "
              f"(descriptive; the paired test below is the estimand)")

    if not powered["_ARM_P"]:
        print("\n  ARM P VERDICT INPUT: UNDERPOWERED — fewer than "
              f"{MIN_AFFECTED_DATES} dates carry both sides.")
        return dict(verdict="UNDERPOWERED", headline=None)

    sub("HEADLINE — every repeat (ordinal >= 2) vs every first, within date")

    def build_all(rows):
        return paired_by_date(rows, lambda r: r["emission_ordinal_capped"] > 1)
    paired = build_all(recs)
    headline = conjunction("repeat vs first (ALL repeats)", paired,
                           _tiers(recs, build_all))

    sub("FROZEN SUB-CUT 1 — consecutive-date repeats vs gapped repeats")
    print("  A repeat the next session is a different object from a repeat three "
          "weeks later.\n  Both sides of each cut are compared against the SAME "
          "date's first emissions.")
    results = {}
    for name, pred in (("consecutive repeats", lambda r: r.get("consecutive") is True),
                       ("gapped repeats", lambda r: r.get("consecutive") is False)):
        def build(rows, pred=pred):
            return paired_by_date(rows, pred)
        results[name] = conjunction(name, build(recs), _tiers(recs, build))

    sub("FROZEN SUB-CUT 2 — repeats split by whether the underlying had ALREADY "
        "moved the play's way since first emission")
    move = arm_p_move_cut(recs)
    return dict(verdict=None, headline=headline, subcuts=results, move=move)


def arm_p_move_cut(recs: list[dict]) -> dict:
    """Sub-cut 2. 'The move already happened' stated as a measurable cut.

    Move = close on the row's SIGNAL date over close on the FIRST emission date,
    both resolved by `close_asof` (which fails the run on any read past the
    signal date — G3). Direction comes from the structure's sign; a structure
    with no single direction is excluded and counted, never guessed.

    The SRC_OHLC / SRC_TILDE split is PRINTED and the two sources are never
    pooled: a tilde-sourced move is a different measurement (an underlying quote
    stamped on an option row, close only) from a real stock bar.
    """
    assert_conditioning("pre_signal_move")
    stats = Counter()
    for r in recs:
        r["_moved_with"] = None
        r["_move_src"] = None
        if r["emission_ordinal_capped"] <= 1:
            continue
        sign = STRUCTURE_SIGN.get(r["structure"])
        if sign is None:
            stats["no_direction"] += 1
            continue
        bars = U.load_bars(r["ticker"])
        if not bars:
            stats["no_bars"] += 1
            continue
        sd = r["t"].signal_date
        fd = _date.fromisoformat(r["first_emission_date"])
        c1, s1, _ = close_asof(bars, fd, sd)
        c2, s2, _ = close_asof(bars, sd, sd)
        if c1 is None or c2 is None or c1 <= 0:
            stats["no_close"] += 1
            continue
        if s1 != s2:
            stats["mixed_source"] += 1
            continue
        pct = (c2 - c1) / c1
        r["_moved_with"] = (pct * sign) > 0
        r["_move_src"] = s1
        stats[f"ok_{s1}"] += 1
    print("  coverage: " + "  ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    print("  (a repeat with no directional structure, no bars, no close, or bars "
          "from two\n   different SOURCES is excluded and counted — never pooled "
          "and never guessed)")
    out = {}
    for src in (U.SRC_OHLC, U.SRC_TILDE):
        srows = [r for r in recs if r.get("_move_src") == src]
        if not srows:
            print(f"\n  source {src}: no repeats resolved — nothing to read.")
            continue
        print(f"\n  source {src}: {len(srows)} repeats resolved "
              f"({sum(1 for r in srows if r['_moved_with'])} already moved WITH "
              f"the play, {sum(1 for r in srows if not r['_moved_with'])} against)")
        for label, want in (("already moved WITH the play", True),
                            ("moved AGAINST the play", False)):
            def build(rows, want=want, src=src):
                return paired_by_date(
                    rows,
                    lambda r: (r.get("_move_src") == src
                               and r.get("_moved_with") is want))
            out[(src, want)] = conjunction(f"{src}: repeats that {label}",
                                           build(recs), _tiers(recs, build))
    return out


# ── ARM L ────────────────────────────────────────────────────────────────────

def arm_l(recs, synths, common, powered, cuts) -> dict:
    hdr("ARM L — SIGNAL-TO-FILL LAG (within-row paired Delta R vs the L=0 "
        "baseline, aggregated by DATE)")
    print("  L = 0 is a day-0 CLOSE fill constructed IDENTICALLY to L = 1..3, so "
          "the\n  close-vs-open basis change cancels and the estimand is "
          "LAG-ONLY. The stored book\n  prints below as a REFERENCE line only — "
          "it is not the comparator.")
    print(f"  {OVERNIGHT_GAP_NOTE}.")
    print("  INTRADAY FILLS REMAIN UNTESTABLE on this data: daily marks cannot "
          "represent a fill\n  inside the session, and nothing here may be read "
          "as evidence about intraday timing.")

    for r in common:
        prof = profile_for(r)
        for L in LAGS:
            s = synths[L][id(r)]
            rp = replay(s["t"], **prof)
            s["R"], s["exit"] = rp["pnl_pct"], rp["exit_reason"]

    sub("the ladder (R only — NO dollar figure is quoted across lags)")
    stored_r = [float(r["R"]) for r in common if r.get("R") is not None]
    print(f"  REFERENCE  stored book (next-open fill, stored exits): "
          f"n={len(stored_r)}  mean R {statistics.fmean(stored_r):+.4f}")
    for L in LAGS:
        vals = [synths[L][id(r)]["R"] for r in common]
        mix = Counter(synths[L][id(r)]["exit"] for r in common)
        print(f"  L={L}  n={len(vals)} / {n_dates(common)}d  "
              f"mean R {statistics.fmean(vals):+.4f}  "
              f"top exits {dict(mix.most_common(3))}")

    def build(rows, L):
        return [dict(date=r["date"], a=synths[L][id(r)]["R"],
                     b=synths[0][id(r)]["R"],
                     d=synths[L][id(r)]["R"] - synths[0][id(r)]["R"])
                for r in rows]

    sub("POOLED — each lag paired against L = 0")
    pooled = {}
    for L in LAGS[1:]:
        pooled[L] = conjunction(f"L={L} vs L=0 (pooled)", build(common, L),
                                {t: build([r for r in common if r["source"] == t], L)
                                 for t in ("real", "tweak")})

    sub("WITHIN pre-signal price_vector TERCILES (cut on the FULL book, FROZEN "
        "before any lag result was read)")
    per_tercile = {}
    for name in ("T1_low", "T2_mid", "T3_high", "MISSING"):
        rows = [r for r in common if tercile_of(r, cuts) == name]
        print(f"\n  {name}: {len(rows)} rows / {n_dates(rows)} dates")
        if not powered.get(name):
            print(f"    UNDERPOWERED (floor {MIN_AFFECTED_DATES} dates) — census "
                  f"only, no criterion evaluated.")
            for L in LAGS:
                if rows:
                    print(f"      L={L} mean R "
                          f"{statistics.fmean(synths[L][id(r)]['R'] for r in rows):+.4f}")
            continue
        for L in LAGS:
            print(f"    L={L} mean R "
                  f"{statistics.fmean(synths[L][id(r)]['R'] for r in rows):+.4f}")
        for L in LAGS[1:]:
            per_tercile[(name, L)] = conjunction(
                f"{name} L={L} vs L=0", build(rows, L),
                {t: build([r for r in rows if r["source"] == t], L)
                 for t in ("real", "tweak")})
    return dict(pooled=pooled, per_tercile=per_tercile)


# ── verdicts ─────────────────────────────────────────────────────────────────

def verdicts(p_out: dict, l_out: dict) -> None:
    hdr("VERDICTS (worded in the pre-registration; nothing here is a ship)")

    head = p_out.get("headline")
    if p_out.get("verdict") == "UNDERPOWERED" or head is None:
        p_verdict = ("UNDERPOWERED — census published, nothing read, no re-run "
                     "on these dates")
    elif head["candidate"] and head["point"] < 0:
        p_verdict = ("STALE-ENTRY-PENALTY (CANDIDATE, NOT A SHIP) — proposes a "
                     "candidate INTAKE rule\n      (prefer first emissions), "
                     "queued for an independent-window confirmation before it "
                     "may\n      reach deployment-rules.md")
    elif head["candidate"]:
        p_verdict = ("CONFIRMATION-SIGNED PASS — the conjunction clears but with "
                     "the OPPOSITE sign to the\n      stale hypothesis. The "
                     "registration words no rule for this direction; recorded as "
                     "\n      directional evidence only, proposes nothing.")
    elif head["ci_ok"]:
        p_verdict = "NULL — a CI cleared but the rest of the conjunction failed"
    else:
        p_verdict = ("NULL (no persistence effect) — no cell separates repeats "
                     "from firsts")
    print(f"  ARM P: {p_verdict}")

    pooled = l_out.get("pooled") or {}
    read = {L: v for L, v in pooled.items() if v is not None}
    if not read:
        l_verdict = "UNDERPOWERED — no lag cell cleared the date floor"
    elif any(v["candidate"] for v in read.values()):
        worse = all(v["point"] <= 0 for v in read.values() if v["candidate"])
        l_verdict = (("STALE-ENTRY-PENALTY (CANDIDATE, NOT A SHIP) — a lag "
                      "reliably loses under the full\n      conjunction; "
                      "proposes a candidate INTAKE rule (fill same session), "
                      "queued for an\n      independent-window confirmation")
                     if worse else
                     ("CONFIRMATION-SIGNED PASS — a lag cell clears the "
                      "conjunction in the direction that\n      says waiting "
                      "HELPS. No registered verdict proposes a rule from it; "
                      "recorded only."))
    else:
        pts = [read[L]["point"] for L in sorted(read)]
        monotone = all(b <= a for a, b in zip(pts, pts[1:]))
        if monotone and any(v["ci_ok"] for v in read.values()):
            l_verdict = ("LAG-SENSITIVE — the ladder degrades with L but fails "
                         "the conjunction; directional\n      evidence recorded, "
                         "no rule proposed")
        elif any(v["ci_ok"] for v in read.values()):
            l_verdict = ("NULL — a cell cleared a CI but failed the rest; window "
                         "artifact, recorded")
        else:
            l_verdict = ("LAG-TOLERANT (PUBLISHABLE OPERATIONAL FINDING) — no lag "
                         "in {1,2,3} separates from\n      L=0 under the "
                         "conjunction: THE SIGNAL DOES NOT DECAY WITHIN THREE "
                         "SESSIONS. A missed\n      same-day fill is not a lost "
                         "trade. This is a finding in its own right, not a null.")
    print(f"  ARM L: {l_verdict}")

    stopped = [k for k, v in (l_out.get("per_tercile") or {}).items() if v is None]
    if stopped:
        print(f"  tercile cells UNDERPOWERED: {sorted(set(k[0] for k in stopped))} "
              f"— census published, nothing read.")
    print("\n  Worst-decile reads are FORBIDDEN as criteria by the registration "
          "(the 2026-08-13\n  nine-date decile wall) and are not computed "
          "anywhere in this study.")
    print("  No annualised figure, Sharpe, or time-to-recover is printed above, "
          "by design.")


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    recs, diag = load_book(include_bs=False)
    coverage(recs, diag)
    g3_selftest()
    em = emission_index(recs)
    cuts = terciles_full_book(recs)
    powered = g0(recs, em, cuts)
    synths, g1_out = g1(recs)
    common = g1_out["common"]
    g2(recs, synths, common)
    p_out = arm_p(recs, powered)
    l_out = arm_l(recs, synths, common, powered, cuts)
    verdicts(p_out, l_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
