"""trigger_entry — does entering only ON the model's stated trigger beat entering unconditionally?

PRE-REGISTERED 2026-09-04 in
`research/pre-registrations/f1_selection/trigger_entry.md`, BEFORE this file
was written. That document is BINDING; nothing here may drift from it. Read it
first. In brief:

  Production enters every non-vetoed play unconditionally at the next session's
  OPEN (`config/backtest.yml` `entry_timing: next_open`); the stated trigger is
  ignored. `exit_from_text` ARM E2 censused "trigger level met within N
  sessions" and found the ENTERED subset far above the NOT-ENTERED one — but
  E2 KEPT the next-open entry price, so the favourable early move that
  satisfied the trigger sits INSIDE the ENTERED number. This study PAYS FOR THE
  CONFIRMATION: it fills at the crossing session's own close and re-prices the
  whole trade through the FROZEN harness.

  ARM T (headline)  first session k in [1..N] whose underlying CLOSE crosses
       the stated level in the stated direction (inclusive, per the imported
       `exit_from_text.trigger_met`); fill at that session's close mark via
       `emission_timing.synth_trade`, contracts re-sized, dte shifted, shipped
       profile replayed through the UNMODIFIED `harness.replay`. Never crossing
       within N -> NOT ENTERED. N in {1, 3, 5}, frozen.
  ARM L (control)   every in-scope row at a FIXED session k in {1, 3}, no gate.
       ARM T moves two things at once (WHEN and WHICH); ARM L holds the
       selection constant, so a delta ARM L reproduces is a LAG finding.
  ARM C (confound)  ARM T's delta stratified by entry-session conformity band,
       reusing `next_day_move.DAY0_PNL_BANDS` and `MIN_CELL_N` VERBATIM.
  ARM D (deployment) the shipped top-3/day ladder with NOT-ENTERED rows
       INELIGIBLE (the slot frees), trigger-priced vs shipped picks. R only.

  THE HARNESS IS NOT TOUCHED AND NOT COPIED. Every arm is pure COMPOSITION
  around the frozen `lib/harness.replay`. `staged_exit`'s replay fork is not
  needed here and is not reproduced.

  NOT `lib/triggers.py`. That module holds ROLLBACK triggers for shipped rules
  and has nothing whatever to do with the model's entry-trigger prose.

Gates, in the registered order: G0 POWER (blocks every read) -> G1 PARSE CENSUS
-> G2 CONSTRUCTION / G-SYNTH (a `Trade` failure FAILS the run) -> G3 LEAK GUARD
-> G4 SIZING CENSUS -> G5 DEADLINE DIAGNOSTIC.

Verdicts, worded in the registration and EXHAUSTIVE: CANDIDATE /
CONFOUND-EXPLAINED / LATE-ENTRY / LAG-EXPLAINED / CONTRARY / NULL /
UNDERPOWERED. Nothing ships from a research-tier study. Read-only; touches no
config. Run:

    python -m scripts.backtest_study run trigger_entry            # PRIMARY v4
    python -m scripts.backtest_study run trigger_entry --era v3   # SECONDARY

R is the unit of every conclusion. NO DOLLAR FIGURE IS QUOTED ACROSS ARMS —
contracts are RE-SIZED when the entry price moves. No annualised figure,
Sharpe, or time-to-recover; worst-decile reads are FORBIDDEN as criteria and
are not computed.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection.emission_timing import (  # noqa: E402
    profile_for, synth_trade,
)
from scripts.backtest_study.f2_management.bear_giveback import hdr, sub  # noqa: E402
from scripts.backtest_study.f2_management.exit_from_text import (  # noqa: E402
    calibration_gate, changed, source_split, trigger_direction, trigger_met,
)
from scripts.backtest_study.f2_management.next_day_move import (  # noqa: E402
    DAY0_PNL_BANDS, MIN_CELL_N, day0_mark_pnl,
)
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402
from scripts.backtest_study.lib.harness import replay  # noqa: E402
from scripts.backtest_study.lib.text_corpus import load_corpus  # noqa: E402

# The runner promotes `-latest.txt` on these codes instead of deleting it. It
# finds them by AST parse, so this MUST stay a PLAIN SET LITERAL — a
# `frozenset(...)` call is invisible to `ast.literal_eval` and the refusal would
# be misfiled as a failure. {2, 3} are `era.EXIT_THIN_ERA` / `EXIT_ERA_MISMATCH`,
# raised by `load_book` when the exports on disk are not the era asked for.
# Nothing else in this module is a designed refusal — a gate failure here is a
# REAL failure and must delete the report.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

EXIT_GATE_FAILURE = 1

# --- FROZEN GRID (pre-registration §"Frozen grid"). May not move. ------------

TRIGGER_N = (1, 3, 5)        # ARM T window, frozen at three
ARM_L_LAGS = (1, 3)          # ARM L fixed SESSION numbers, frozen at two
TOP_K = 3                    # ARM D: the shipped card's depth

# --- Gate constants, all declared before any count was known -----------------

MIN_AFFECTED_DATES = 25      # G0 floor and criterion 6
MIN_AFFECTED_ROWS = 60       # G0 floor and criterion 6
BOOT_N = P.BOOT_N            # 10000, alpha = .05
BOOT_SEED = 20260904

# `window_cuts` drops ONE window at a time; criterion 3 also requires the
# ex-BOTH cut, added BY HAND here — a result carried by the UNION of the two
# windows walks straight through the gap `window_cuts()` leaves.
_BOTH_WINDOW_MONTHS = {m for months in P.DOMINANT_WINDOWS.values() for m in months}

# The registered verdict vocabulary. EXHAUSTIVE — `verdict_for` may return
# nothing else, and the summary tally is checked against it.
VERDICTS = ("CANDIDATE", "CONFOUND-EXPLAINED", "LATE-ENTRY", "LAG-EXPLAINED",
            "CONTRARY", "NULL", "UNDERPOWERED")


def fail(msg: str) -> None:
    """A REAL failure (not a designed refusal): exit non-zero so the runner
    DELETES `-latest.txt` rather than promoting a report nobody may read."""
    print(f"\n*** GATE FAILURE: {msg} ***")
    sys.exit(EXIT_GATE_FAILURE)


def n_dates(rows) -> int:
    return len({str(r["date"]) for r in rows})


def meanR(rows, key="_shipped") -> float:
    vals = [r[key]["pnl_pct"] for r in rows]
    return statistics.fmean(vals) if vals else float("nan")


# =============================================================================
# the indexing rule — the one place session numbers meet grid indices
# =============================================================================

def first_cross(bars: dict, entry_day, level: float, direction: str,
                n: int) -> int | None:
    """The 1-BASED session k in [1..n] whose CLOSE first crosses `level`, or None.

    THE INDEXING RULE, RECONCILED. Sessions are counted exactly the way
    `exit_from_text.trigger_met` counts them — `underlying.sessions_from(bars,
    entry_day, n)`, i.e. on the BAR SERIES, so a market holiday inside the
    window does NOT consume one of the n. "Crosses" is INCLUSIVE (`>=` above,
    `<=` below), the same convention `trigger_met` uses: a trigger reading
    "holds 34" is met by a close of exactly 34.

    Session k = 1 is `underlying.entry_day`, which is `t.grid[0]` —
    `_weekday_grid` is documented "weekdays AFTER the signal date", so
    `marks[0]` is already the fill session and there is no pre-entry mark to
    skip. A crossing at session k therefore fills at
    `emission_timing.synth_trade(rec, k - 1)`.

    That mapping is exact whenever `entry_day == grid[0]` and no market holiday
    falls inside the window. It is NOT exact otherwise, because the grid is
    WEEKDAY-based while the sessions here are BAR dates: a holiday makes the
    k-th session land at grid index > k - 1. `grid_lag()` below resolves the
    crossing session's OWN grid index, which is the mark actually paid, and G2
    prints how many rows the two disagree on. This function returns k, so that
    `first_cross(...) is not None` is identical to `trigger_met(...)` by
    construction — pinned in tests/test_trigger_entry.py.
    """
    for k, d in enumerate(U.sessions_from(bars, entry_day, n), start=1):
        c = bars[d].c
        if (c >= level) if direction == "above" else (c <= level):
            return k
    return None


def session_date(bars: dict, entry_day, k: int):
    """The bar DATE of the 1-based session `k`, or None past the end of the series."""
    days = U.sessions_from(bars, entry_day, k)
    return days[k - 1] if len(days) >= k else None


def grid_lag(t, day) -> int | None:
    """`day`'s index in the trade's weekday grid — the lag `synth_trade` takes.

    None when the session lies beyond the end of the grid (a short-dated row
    whose path ran out before the trigger fired). Such a row is a COUNTED
    construction exclusion, never silently re-anchored to a session it did not
    cross on.
    """
    try:
        return t.grid.index(day)
    except ValueError:
        return None


# =============================================================================
# scope
# =============================================================================

def in_scope(rec: dict, bars_by_ticker: dict) -> tuple[dict | None, str]:
    """`(scope dict, bucket)` — E2's exclusion-bucket logic, reused verbatim.

    The buckets are `exit_from_text.run_e2`'s, with the same names, so the two
    studies' parse censuses are directly comparable. Nothing here guesses a
    side: a trigger with no direction word is `no_direction` and is COUNTED.
    """
    trig_text = (rec.get("text") or {}).get("trigger") or ""
    level = (rec.get("features") or {}).get("trigger_level")
    if not trig_text.strip():
        return None, "no_trigger_text"
    if level is None:
        return None, "conditional_unparseable: no level"
    direction = trigger_direction(trig_text, level)
    if direction is None:
        return None, "conditional_unparseable: no direction"
    bars = bars_by_ticker.get(rec["ticker"]) or {}
    if not bars:
        return None, "no_bars"
    ed = U.entry_day(rec["t"], sessions=set(bars))
    if ed is None:
        return None, "no_entry_session"
    src = next(iter({b.source for b in bars.values()}), None)
    return dict(level=float(level), direction=direction, entry_day=ed,
                bars=bars, bar_source=src), "in scope (level + direction)"


# =============================================================================
# the outcome function — G3's leak guard lives INSIDE it
# =============================================================================

def arm_t_outcome(rec: dict, n: int) -> dict:
    """`{status, out, k, lag, pad}` for one row under ARM T at window `n`.

    THE KEYING IS EVALUATED IN HERE, on purpose. The whole admitted book is
    handed to this function, so a row that is out of scope, or that never
    crosses, is decided here and returned UNCHANGED — `out is rec["_shipped"]`.
    Pre-filtering to the in-scope list would make G3 vacuous: the rule could
    not touch a row it was never handed.

    `status` is one of: `out_of_scope` (no readable trigger), `not_entered`
    (readable, never crossed within n), `entered`, or a construction-exclusion
    reason from `synth_trade`.
    """
    sc = rec.get("_scope")
    if sc is None:
        return dict(status="out_of_scope", out=rec["_shipped"], k=None,
                    lag=None, pad=0)
    k = first_cross(sc["bars"], sc["entry_day"], sc["level"], sc["direction"], n)
    if k is None:
        return dict(status="not_entered", out=rec["_shipped"], k=None,
                    lag=None, pad=0)
    day = session_date(sc["bars"], sc["entry_day"], k)
    lag = grid_lag(rec["t"], day) if day is not None else None
    if lag is None:
        return dict(status="cross_past_grid_end", out=rec["_shipped"], k=k,
                    lag=None, pad=0)
    st, pad, status = synth_trade(rec, lag)
    if st is None:
        return dict(status=status, out=rec["_shipped"], k=k, lag=lag, pad=0)
    return dict(status="entered", out=replay(st, **rec["_profile"]), k=k,
                lag=lag, pad=pad, t=st)


def arm_l_outcome(rec: dict, k: int) -> dict:
    """ARM L: the same synthetic at a FIXED session `k`, no gate. In-scope rows
    only — the control has to run on ARM T's population or it controls nothing."""
    if rec.get("_scope") is None:
        return dict(status="out_of_scope", out=rec["_shipped"], lag=None, pad=0)
    st, pad, status = synth_trade(rec, k - 1)
    if st is None:
        return dict(status=status, out=rec["_shipped"], lag=k - 1, pad=0)
    return dict(status="entered", out=replay(st, **rec["_profile"]), lag=k - 1,
                pad=pad, t=st)


# =============================================================================
# the conjunction
# =============================================================================

def evaluate(paired: list[dict]) -> dict:
    """Criteria 1-6 for one cell of paired rows `{date, a, b, source}`.

    Criteria 7 (no sign flip across N) and 8 (ARM C bands) are properties of
    the GRID and of another arm, so they are computed by the caller and merged
    in. Every criterion is evaluated TOWARD THE OBSERVED SIGN, which is what
    makes a reliably negative cell a CONTRARY finding rather than a passed one.
    """
    out: dict = {"n": len(paired), "n_dates": n_dates(paired)}
    out["mean_shipped"] = statistics.fmean(p["b"] for p in paired)
    out["mean_variant"] = statistics.fmean(p["a"] for p in paired)
    out["delta"] = out["mean_variant"] - out["mean_shipped"]
    positive = out["delta"] > 0

    lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=BOOT_N, seed=BOOT_SEED)
    out["ci"] = (lo, hi)

    _m, share, loo_min, n_folds = P.loo_by_date(paired, lambda p: p["a"],
                                                lambda p: p["b"])
    out["loo_min"], out["loo_share"], out["loo_folds"] = loo_min, share, n_folds

    cuts = P.window_cuts(paired)
    cuts["ex_BOTH"] = [p for p in paired
                       if str(p["date"])[:7] not in _BOTH_WINDOW_MONTHS]
    out["cuts"] = {k: (len(rs),
                       statistics.fmean(p["a"] - p["b"] for p in rs) if rs else None)
                   for k, rs in cuts.items()}
    out["years"] = {y: (len(rs), statistics.fmean(p["a"] - p["b"] for p in rs))
                    for y, rs in P.by_year(paired).items()}
    out["tiers"] = {}
    for tier in ("real", "tweak"):
        rs = [p for p in paired if p["source"] == tier]
        if rs:
            out["tiers"][tier] = (len(rs),
                                  statistics.fmean(p["a"] - p["b"] for p in rs))

    def right(v):
        return v is not None and ((v > 0) if positive else (v < 0))

    out["c1_ci"] = (lo > 0) if positive else (hi < 0)
    out["c2_loo"] = bool(n_folds) and (share == 1.0 if positive else share == 0.0)
    out["c3_windows"] = bool(out["cuts"]) and all(right(v) for _n, v in out["cuts"].values())
    out["c4_years"] = bool(out["years"]) and all(right(v) for _n, v in out["years"].values())
    out["c5_tiers"] = bool(out["tiers"]) and all(right(v) for _n, v in out["tiers"].values())
    out["c6_power"] = (len(paired) >= MIN_AFFECTED_ROWS
                       and out["n_dates"] >= MIN_AFFECTED_DATES)
    return out


def criteria_vector(ev: dict) -> str:
    keys = ("c1_ci", "c2_loo", "c3_windows", "c4_years", "c5_tiers", "c6_power",
            "c7_no_flip", "c8_bands")
    names = ("1_ci", "2_loo", "3_windows", "4_years", "5_tiers", "6_power",
             "7_no_flip", "8_bands")
    return "  ".join(f"{nm}={'T' if ev.get(k) else 'F'}" for k, nm in zip(keys, names))


def verdict_for(ev: dict, census_reproduces: bool, l_sep: bool) -> str:
    """The registration's verdict grammar, in its registered ORDER, first match wins.

    EXHAUSTIVE by construction: the final `else` is NULL and no other string is
    reachable. Read §"Verdicts, worded now" before touching the order — it is
    the order that makes LATE-ENTRY (a null WITH a mechanism) distinct from a
    bare NULL, and LAG-EXPLAINED distinct from CANDIDATE.
    """
    if not ev.get("powered"):
        return "UNDERPOWERED"
    conj_1_7 = all(ev[k] for k in ("c1_ci", "c2_loo", "c3_windows", "c4_years",
                                   "c5_tiers", "c6_power", "c7_no_flip"))
    conj_all = conj_1_7 and ev["c8_bands"]
    if ev["delta"] <= 0 and census_reproduces:
        return "LATE-ENTRY"
    if ev["c1_ci"] and ev["delta"] < 0:
        return "CONTRARY"
    if ev["delta"] > 0 and conj_1_7 and not ev["c8_bands"]:
        return "CONFOUND-EXPLAINED"
    if ev["delta"] > 0 and conj_all and not l_sep:
        return "LAG-EXPLAINED"
    if ev["delta"] > 0 and conj_all and l_sep:
        return "CANDIDATE"
    return "NULL"


# =============================================================================
# report sections
# =============================================================================

def header(rows: list[dict], diag: dict, era: str) -> None:
    hdr(f"trigger_entry — ERA {era}   (pre-registration "
        f"research/pre-registrations/f1_selection/trigger_entry.md)")
    print(f"book: {len(rows)} rows  era={era}  date_range={diag['date_range']}  "
          f"n_dates={diag['n_dates']}  counts_by_source={diag['counts_by_source']}"
          f"  (bs excluded)")
    print(f"debit_calib: {diag['debit_calib']}")
    print(f"n_credit_ungated: {diag['n_credit_ungated']}  — CAVEAT: credit rows are "
          f"admitted WITHOUT the\n  exact-replay calibration gate in `load_book` "
          f"(Attempt 13 removed the credit stop\n  mid-book, so there is no single "
          f"credit PROD that calibrates the accumulated\n  sheet). This study runs "
          f"exit_from_text's OWN gate below under CREDIT_PROD, but\n  treat every "
          f"credit-side number as unvalidated until the book is split per\n  "
          f"credit-stop era.")
    print(f"text join: {diag['n_joined']} joined / {diag['n_unjoined']} unjoined "
          f"(an unjoined row has NO trigger text —\n  blank means 'column absent', "
          f"not 'the model said nothing')")
    n_unpriced = sum(diag["unpriced_by_reason"].values())
    print(f"unpriced analysis rows by reason: {dict(diag['unpriced_by_reason'])}")
    print(f"PRICEABILITY: {len(rows)} priced / {len(rows) + n_unpriced} analysis rows "
          f"= {len(rows) / (len(rows) + n_unpriced):.1%}\n  — every arm below is "
          f"CONDITIONED ON THIS. A trigger can only be re-priced on a row\n  that "
          f"priced; the unpriced remainder is not evidence for or against any arm.")
    print(f"feature coverage: trigger_level="
          f"{diag['feature_coverage']['trigger_level']:.1%}")

    years = sorted({str(r["date"])[:4] for r in rows})
    print(f"\n  calendar years present in this export: {years}")
    if "2026" not in years:
        print("""  THE 2026 NO-OP, DISCLOSED IN THE REGISTRATION: this export carries ZERO 2026
  signal dates, so protocol.window_cuts' `ex_2026_feb_apr` is IDENTICAL to ALL,
  the hand-added ex_BOTH cut collapses to `ex_2025_mar_apr`, and criterion 4
  ("sign-stable per calendar year") spans 2024/2025 ONLY. Every cut prints its n
  beside ALL's so a reader sees a no-op rather than a passed test.""")
    else:
        print("  This export DOES carry 2026 dates: both window cuts and the year "
              "cut bind.")


def g1_parse_census(recs: list[dict], buckets: Counter, scoped: list[dict]) -> None:
    hdr("G1 — PARSE CENSUS (a PROMPT-ROBUSTNESS finding in its own right)")
    total = len(recs)
    print(f"  buckets over {total} calibration-admitted rows "
          f"(exit_from_text's E2 bucket vocabulary, reused verbatim):")
    for k, v in sorted(buckets.items(), key=lambda kv: -kv[1]):
        print(f"    {k:<38} {v:>5}  ({v / total:.1%})")
    n_cond = sum(1 for r in recs
                 if (r.get("features") or {}).get("trigger_conditional"))
    print(f"    {'trigger is CONDITIONAL (text_corpus)':<38} {n_cond:>5}  "
          f"({n_cond / total:.1%})   [diagnostic, not a bucket]")
    print(f"\n  IN SCOPE: {len(scoped)} rows / {n_dates(scoped)} dates")
    print(f"  bar-tier split on the in-scope rows (PRINTED, never pooled silently): "
          f"{source_split([dict(bar_source=r['_scope']['bar_source']) for r in scoped])}")
    print("  A tilde close is a different measurement from a real bar — it is the "
          "underlying\n  quote stamped on an option row at the option's EOD "
          "snapshot. SRC_TILDE bars carry\n  NO open/high/low at all, which is one "
          "of the two reasons this study is CLOSE-ONLY.")


def g0_power(scoped: list[dict], arm_t: dict) -> dict:
    hdr("G0 — POWER CENSUS (runs FIRST and blocks every read below)")
    print(f"""  Floor, declared in the registration before any count was known: a cell with
  < {MIN_AFFECTED_DATES} affected DATES or < {MIN_AFFECTED_ROWS} affected ROWS is UNDERPOWERED —
  printed with its n, no criterion evaluated on it, nothing refuted, no re-run.
  "Affected" here is the ENTERED, RE-PRICED set: every entered row is re-priced
  at a different fill, so entering IS the change.""")
    print(f"\n  {'arm':<6}{'cell':<10}{'in scope':>9}{'entered':>9}{'dates':>7}"
          f"{'not entered':>13}{'excluded':>10}  status")
    powered = {}
    ns = n_dates(scoped)
    for n in TRIGGER_N:
        rows = arm_t[n]["entered"]
        ok = len(rows) >= MIN_AFFECTED_ROWS and n_dates(rows) >= MIN_AFFECTED_DATES
        powered[("T", n)] = ok
        print(f"  {'T':<6}{f'N={n}':<10}{len(scoped):>9}{len(rows):>9}"
              f"{n_dates(rows):>7}{arm_t[n]['n_not_entered']:>13}"
              f"{arm_t[n]['n_excluded']:>10}  {'powered' if ok else 'UNDERPOWERED'}")
    print(f"  (in-scope dates: {ns})")
    return powered


def g2_construction(recs: list[dict], scoped: list[dict], arm_t: dict,
                    arm_l: dict) -> None:
    hdr("G2 — CONSTRUCTION (G-SYNTH). Any Trade construction failure FAILS the run.")
    print("""  G-SYNTH: `synth_trade(rec, 0)` must reproduce the STORED trade — same
  signal_date, same dte_entry, same weekday grid, same mark path — and differ
  ONLY in the fill price (a day-0 CLOSE mark instead of the stored next-open
  fill) and in the contract count (re-sized at that price). If lag 0 did not
  reproduce the stored trade's timing, every lag above it would be measuring a
  construction bug rather than a delay.

  Construction failures abort through the IMPORTED `emission_timing.synth_trade`,
  which raises its own gate label ("G1") before exiting non-zero — the label is
  that module's, the abort is this gate's. A silently dropped row would make the
  ladder a comparison between different populations.""")
    ok = bad = 0
    excl: Counter = Counter()
    price_moved = size_moved = 0
    for rec in scoped:
        st, _pad, status = synth_trade(rec, 0)
        if st is None:
            # NOT a reproduction failure: the row has no usable day-0 mark at
            # all (unpriced, or a degenerate 0.00), so there is nothing to
            # reproduce. Counted here and excluded from every arm, never
            # silently dropped and never counted as a pass.
            excl[status] += 1
            continue
        t = rec["t"]
        same = (st.signal_date == t.signal_date and st.dte_entry == t.dte_entry
                and st.grid == t.grid and st.marks == t.marks)
        ok += int(same)
        bad += int(not same)
        price_moved += int(st.entry_net != t.entry_net)
        size_moved += int(st.contracts != int(t.contracts))
    print(f"\n  G-SYNTH at lag 0 over {len(scoped)} in-scope rows: "
          f"{ok} reproduce the stored trade's signal_date / dte_entry / grid / "
          f"mark path,\n  {bad} do not, {sum(excl.values())} have no usable day-0 "
          f"mark to build from {dict(excl) or '{}'}.")
    print(f"  of the {ok} reproductions, {price_moved} differ in FILL PRICE and "
          f"{size_moved} in CONTRACT COUNT\n  — the two fields the registration "
          f"says may differ, and the only two that do.")
    if bad:
        fail(f"G2: {bad} in-scope rows do not reproduce their stored trade at lag 0.")
    print("  G2 G-SYNTH: PASS.")

    sub("padding census (right-padding with EMPTY fields only)")
    for n in TRIGGER_N:
        pads = [o["pad"] for o in arm_t[n]["out"].values() if o["status"] == "entered"]
        print(f"  ARM T N={n}: {sum(1 for p in pads if p)} padded rows "
              f"({sum(pads)} blank fields) of {len(pads)} entered")
    for k in ARM_L_LAGS:
        pads = [o["pad"] for o in arm_l[k]["out"].values() if o["status"] == "entered"]
        print(f"  ARM L k={k}: {sum(1 for p in pads if p)} padded rows "
              f"({sum(pads)} blank fields) of {len(pads)} filled")
    print("  `replay` skips a None mark and the shipped profiles cannot fire on "
          "one, so padding is\n  behaviour-neutral; DROPPING the cap-truncated rows "
          "instead would bias the population\n  toward short-dated trades.")

    sub("construction exclusions per cell (counted, never silently dropped)")
    for n in TRIGGER_N:
        excl = Counter(o["status"] for o in arm_t[n]["out"].values()
                       if o["status"] not in ("entered", "not_entered", "out_of_scope"))
        print(f"  ARM T N={n}: {dict(excl) or '{}'}")
    for k in ARM_L_LAGS:
        excl = Counter(o["status"] for o in arm_l[k]["out"].values()
                       if o["status"] not in ("entered", "out_of_scope"))
        print(f"  ARM L k={k}: {dict(excl) or '{}'}")

    sub("first_cross vs the IMPORTED trigger_met (one definition of 'met', asserted)")
    dis = 0
    for r in scoped:
        sc = r["_scope"]
        for n in TRIGGER_N:
            met = trigger_met(sc["bars"], sc["entry_day"], sc["level"],
                              sc["direction"], n)
            k = first_cross(sc["bars"], sc["entry_day"], sc["level"],
                            sc["direction"], n)
            dis += int(met != (k is not None))
    print(f"  rows x N where `first_cross(...) is not None` disagrees with "
          f"`exit_from_text.trigger_met`: {dis}")
    if dis:
        fail("G2: first_cross and the imported trigger_met disagree about what "
             "'met' means. There is one definition and it is trigger_met's.")
    print("  PASS — the two agree everywhere; inclusivity and the holiday-skipping "
          "session count\n  are trigger_met's, reused, not re-implemented.")

    sub("INDEXING RECONCILIATION — session k vs grid index (the registered k-1 rule)")
    off = sum(1 for r in scoped if r["_scope"]["entry_day"] != r["t"].grid[0])
    print(f"  rows whose entry_day is NOT grid[0] (a market holiday on the first "
          f"weekday after\n  the signal): {off} of {len(scoped)}")
    mismatch = Counter()
    for n in TRIGGER_N:
        m = sum(1 for o in arm_t[n]["out"].values()
                if o["status"] == "entered" and o["lag"] != o["k"] - 1)
        mismatch[n] = m
        print(f"  ARM T N={n}: {m} entered rows where the crossing session's grid "
              f"index != k-1")
    print("""  Where they differ the module uses the CROSSING SESSION'S OWN grid index —
  the mark actually paid — rather than k-1, which would fill on a different
  session than the one that crossed. The registered rule (k=1 is entry_day is
  marks[0], so a crossing at k fills at synth_trade(rec, k-1)) is exact on every
  row where the two agree, and the count above is the disclosure of the rest.""")


def g3_leak(recs: list[dict], arm_t: dict, arm_l: dict) -> None:
    hdr("G3 — LEAK GUARD (no row OUTSIDE the population may move, in ANY cell)")
    print("""  Every row that is NOT in scope — no trigger text, no level, no direction, no
  bars, no resolvable entry session — must come back byte-identical to its
  shipped replay on (exit_reason, days_held, round(pnl, 10)). The WHOLE admitted
  book is handed to the outcome function with the keying evaluated INSIDE it; a
  pre-filtered list could not leak and would make this gate vacuous. One changed
  row fails the run.""")
    out_rows = [r for r in recs if r.get("_scope") is None]
    leaks = []
    for n in TRIGGER_N:
        bad = sum(1 for r in out_rows
                  if changed(arm_t[n]["out"][id(r)]["out"], r["_shipped"]))
        if bad:
            leaks.append((f"ARM T N={n}", bad))
    for k in ARM_L_LAGS:
        bad = sum(1 for r in out_rows
                  if changed(arm_l[k]["out"][id(r)]["out"], r["_shipped"]))
        if bad:
            leaks.append((f"ARM L k={k}", bad))
    print(f"\n  out-of-scope rows checked: {len(out_rows)} in each of "
          f"{len(TRIGGER_N) + len(ARM_L_LAGS)} cells")
    if leaks:
        for label, bad in leaks:
            print(f"    {label}: {bad} out-of-scope rows CHANGED")
        fail("G3: a trigger arm moved rows outside its population.")
    print("  G3: PASS — 0 out-of-scope rows changed, in every cell.")


def g4_sizing(scoped: list[dict], arm_t: dict, arm_l: dict) -> None:
    hdr("G4 — SIZING CENSUS (contracts per cell; NO DOLLAR FIGURE IS QUOTED "
        "ACROSS ARMS)")
    print("""  Contracts are RE-SIZED by the production formula at the new entry price
  (`emission_timing.size_contracts`, ported from simulate.py::_size_contracts).
  This is NOT cosmetic: `harness.replay`'s dollar_stop fires on
  `pl * |entry| * 100 * contracts <= -MAX_LOSS_ABS`, so the CONTRACT COUNT
  decides at what R the dollar stop bites. Leaving the stored count on a
  synthetic whose entry price moved would drift that threshold with the fill and
  the arms would be measuring a sizing artifact instead of the trigger.

  It is also exactly why NO DOLLAR FIGURE MAY BE QUOTED ACROSS ARMS: a dollar
  total compares two different position sizes. R is the unit of every conclusion
  in this study.""")
    print(f"\n  {'cell':<12}{'n':>6}{'mean':>9}{'median':>9}{'min':>6}{'max':>6}"
          f"{'== stored':>11}")
    stored = [int(r["t"].contracts) for r in scoped]
    print(f"  {'book':<12}{len(stored):>6}{statistics.fmean(stored):>9.2f}"
          f"{statistics.median(stored):>9.1f}{min(stored):>6}{max(stored):>6}"
          f"{'—':>11}   (stored counts, REFERENCE only)")
    for n in TRIGGER_N:
        cs, same = [], 0
        for r in scoped:
            o = arm_t[n]["out"][id(r)]
            if o["status"] != "entered":
                continue
            cs.append(o["t"].contracts)
            same += int(o["t"].contracts == int(r["t"].contracts))
        if cs:
            print(f"  {f'ARM T N={n}':<12}{len(cs):>6}{statistics.fmean(cs):>9.2f}"
                  f"{statistics.median(cs):>9.1f}{min(cs):>6}{max(cs):>6}{same:>11}")
    for k in ARM_L_LAGS:
        cs, same = [], 0
        for r in scoped:
            o = arm_l[k]["out"][id(r)]
            if o["status"] != "entered":
                continue
            cs.append(o["t"].contracts)
            same += int(o["t"].contracts == int(r["t"].contracts))
        if cs:
            print(f"  {f'ARM L k={k}':<12}{len(cs):>6}{statistics.fmean(cs):>9.2f}"
                  f"{statistics.median(cs):>9.1f}{min(cs):>6}{max(cs):>6}{same:>11}")


def g5_deadline(scoped: list[dict], arm_t: dict) -> None:
    hdr("G5 — DEADLINE DIAGNOSTIC (printed, NOT a second grid)")
    print("""  The synthetic's time exit RECOMPUTES from the new entry anchor: `synth_trade`
  reduces `dte_entry` by the calendar days the anchor moved, and `harness.replay`
  fires `time_exit` at `int(dte_entry * tef)` CALENDAR days from the (new)
  signal_date. That is production semantics — `scripts/journal/lib/exit_rules.py`
  measures the time exit from the position's own entry, not from the emission.

  The alternative — an ABSOLUTE deadline anchored to the ORIGINAL signal date,
  so waiting for the trigger eats into the holding period — is a DIAGNOSTIC
  here, not a second arm. Below: how many ARM T `time_exit` rows would exit on a
  DIFFERENT session under it. A large count means the deadline convention is
  load-bearing and any candidate must be re-read with that stated.""")
    print(f"\n  {'cell':<10}{'time_exit rows':>16}{'would move':>12}{'share':>9}")
    for n in TRIGGER_N:
        moved = tot = 0
        for r in scoped:
            o = arm_t[n]["out"][id(r)]
            if o["status"] != "entered" or o["out"]["exit_reason"] != "time_exit":
                continue
            st, t = o["t"], r["t"]
            tef = r["_profile"].get("tef")
            if not tef:
                continue
            tot += 1
            shift = (st.signal_date - t.signal_date).days
            recomputed = shift + int(st.dte_entry * tef)     # days from ORIGINAL signal
            absolute = int(t.dte_entry * tef)                # days from ORIGINAL signal
            day_r = _first_day_at_or_after(st.grid, t.signal_date, recomputed)
            day_a = _first_day_at_or_after(st.grid, t.signal_date, absolute)
            moved += int(day_r != day_a)
        share = (moved / tot) if tot else 0.0
        print(f"  {f'N={n}':<10}{tot:>16}{moved:>12}{share:>9.1%}")


def _first_day_at_or_after(grid, origin: _date, offset_days: int):
    """The first grid day at least `offset_days` calendar days after `origin`."""
    for d in grid:
        if (d - origin).days >= offset_days:
            return d
    return None


# =============================================================================
# arms
# =============================================================================

def build_arm_t(recs: list[dict]) -> dict:
    out: dict = {}
    for n in TRIGGER_N:
        res = {id(r): arm_t_outcome(r, n) for r in recs}
        entered = [r for r in recs if res[id(r)]["status"] == "entered"]
        out[n] = dict(
            out=res, entered=entered,
            n_not_entered=sum(1 for o in res.values() if o["status"] == "not_entered"),
            n_excluded=sum(1 for o in res.values()
                           if o["status"] not in ("entered", "not_entered",
                                                  "out_of_scope")),
        )
    return out


def build_arm_l(recs: list[dict]) -> dict:
    out: dict = {}
    for k in ARM_L_LAGS:
        res = {id(r): arm_l_outcome(r, k) for r in recs}
        out[k] = dict(out=res,
                      filled=[r for r in recs if res[id(r)]["status"] == "entered"])
    return out


def paired_rows(rows: list[dict], res: dict) -> list[dict]:
    return [dict(date=r["date"], a=res[id(r)]["out"]["pnl_pct"],
                 b=r["_shipped"]["pnl_pct"], source=r["source"],
                 bar_source=r["_scope"]["bar_source"], rec=r)
            for r in rows]


def print_cell(label: str, ev: dict, extra: str = "") -> None:
    lo, hi = ev["ci"]
    print(f"\n  {label}")
    print(f"    n={ev['n']} rows / {ev['n_dates']} dates    "
          f"shipped meanR {ev['mean_shipped']:+.4f}   "
          f"trigger meanR {ev['mean_variant']:+.4f}   "
          f"DeltaR {ev['delta']:+.4f}")
    print(f"    1 CI95 date-clustered   : {'PASS' if ev['c1_ci'] else 'FAIL'}  "
          f"[{lo:+.4f}, {hi:+.4f}]  (BOOT_N={BOOT_N}, alpha .05)")
    print(f"    2 LOO every fold signed : {'PASS' if ev['c2_loo'] else 'FAIL'}  "
          f"(share_positive {ev['loo_share']:.3f}, min_gain {ev['loo_min']:+.4f}, "
          f"folds {ev['loo_folds']})")
    cut_s = "  ".join(f"{k} {('%+.4f' % v) if v is not None else '(none)'} (n={n})"
                      for k, (n, v) in ev["cuts"].items())
    print(f"    3 window cuts + ex-BOTH : {'PASS' if ev['c3_windows'] else 'FAIL'}  "
          f"{cut_s}")
    yr_s = "  ".join(f"{y} {v:+.4f} (n={n})" for y, (n, v) in ev["years"].items())
    print(f"    4 sign stable by year   : {'PASS' if ev['c4_years'] else 'FAIL'}  "
          f"{yr_s}")
    ti_s = "  ".join(f"{t} {v:+.4f} (n={n})" for t, (n, v) in ev["tiers"].items())
    print(f"    5 both pricing tiers    : {'PASS' if ev['c5_tiers'] else 'FAIL'}  "
          f"{ti_s or '(none)'}")
    print(f"    6 floor on evaluated set: {'PASS' if ev['c6_power'] else 'FAIL'}  "
          f"({ev['n']} rows / {ev['n_dates']} dates vs {MIN_AFFECTED_ROWS}/"
          f"{MIN_AFFECTED_DATES})")
    print(f"    7 no sign flip across N : {'PASS' if ev.get('c7_no_flip') else 'FAIL'}")
    print(f"    8 ARM C bands survive   : {'PASS' if ev.get('c8_bands') else 'FAIL'}  "
          f"{ev.get('c8_note', '')}")
    if extra:
        print(f"    {extra}")


def e2_census(scoped: list[dict], arm_t: dict) -> dict:
    sub("E2-SHAPE SELECTION CENSUS at SHIPPED pricing — NOT A CRITERION")
    print("""  This is `exit_from_text` ARM E2's estimand, reprinted on this study's
  population so the selection claim and the RE-PRICED claim can be read side by
  side. It keeps the next-open entry price, which is exactly why it is NOT A
  CRITERION here: the favourable move that satisfied the trigger is inside the
  ENTERED number. Nothing in the verdict grammar reads it except LATE-ENTRY,
  which requires it to reproduce.

  IT KEYS ON "THE TRIGGER WAS MET", not on "ARM T could build a synthetic for
  it". A row that met the level but has no usable mark at the crossing session
  is a CONSTRUCTION exclusion (counted in G2), not a NOT-ENTERED row; putting it
  on the not-entered side would make this census disagree with E2's published
  figures for a reason that has nothing to do with selection. ARM T's evaluated
  n is smaller than ENTERED here by exactly that construction count, printed
  beside each row.""")
    all_dates = {r["date"] for r in scoped}
    reproduces = {}
    print(f"\n  {'N':<5}{'ENTERED':>24}{'NOT ENTERED':>24}{'excluded share':>26}"
          f"{'ARM T n':>10}")
    for n in TRIGGER_N:
        met_ids = {id(r) for r in scoped
                   if trigger_met(r["_scope"]["bars"], r["_scope"]["entry_day"],
                                  r["_scope"]["level"], r["_scope"]["direction"], n)}
        ent = [r for r in scoped if id(r) in met_ids]
        ne = [r for r in scoped if id(r) not in met_ids]
        m_ent, m_ne = meanR(ent), meanR(ne)
        ent_dates = {r["date"] for r in ent}
        ne_dates = {r["date"] for r in ne}
        reproduces[n] = m_ent > meanR(scoped)
        ent_s = f"{len(ent)} rows/{len(ent_dates)}d {m_ent:+.3f}"
        ne_s = f"{len(ne)} rows/{len(ne_dates)}d {m_ne:+.3f}"
        exc_s = (f"{len(ne) / len(scoped):.1%} rows, "
                 f"{1 - len(ent_dates) / len(all_dates):.1%} dates")
        print(f"  {f'N={n}':<5}{ent_s:>24}{ne_s:>24}{exc_s:>26}"
              f"{len(arm_t[n]['entered']):>10}")
    print(f"\n  full in-scope population at shipped pricing: {len(scoped)} rows / "
          f"{len(all_dates)} dates   mean R {meanR(scoped):+.3f}")
    print("  Selection effect, on R. NOT an exit result and NOT a criterion.")
    return reproduces


def arm_c_bands(entered: list[dict], res: dict, sign: int) -> tuple[bool, str, list]:
    """Criterion 8. `(passed, note, table)` over `next_day_move.DAY0_PNL_BANDS`."""
    rows = []
    for r in entered:
        sc = r["_scope"]
        d0 = day0_mark_pnl(r, sc["entry_day"])
        if d0 is None:
            continue
        rows.append((d0[1], r))
    table, read, ok = [], 0, True
    for lo, hi, band in DAY0_PNL_BANDS:
        br = [r for pnl, r in rows if lo <= pnl < hi]
        if not br:
            table.append((band, 0, None, "no rows"))
            continue
        d = statistics.fmean(res[id(r)]["out"]["pnl_pct"] - r["_shipped"]["pnl_pct"]
                             for r in br)
        if len(br) < MIN_CELL_N:
            table.append((band, len(br), d, f"n<{MIN_CELL_N}, NOT READ"))
            continue
        read += 1
        right = (d > 0) if sign > 0 else (d < 0)
        ok = ok and right
        table.append((band, len(br), d, "right-signed" if right else "WRONG SIGN"))
    if read == 0:
        return False, (f"no band clears MIN_CELL_N={MIN_CELL_N} — nothing survived "
                       f"to check, criterion 8 FAILS by registration"), table
    return ok, (f"{read} of {len(DAY0_PNL_BANDS)} bands read "
                f"(day-0 coverage {len(rows)}/{len(entered)})"), table


def run_arm_l(scoped: list[dict], arm_l: dict) -> dict:
    hdr("ARM L — UNCONDITIONAL LAG CONTROL (no gate; separates the delay from "
        "the selection)")
    print("""  Every in-scope row filled at a FIXED session k, with NO trigger gate at all.
  ARM T moves two things at once — WHEN the fill happens and WHICH rows are
  filled. ARM L holds the selection constant and moves only the delay, so a
  DeltaR that ARM L reproduces is a LAG finding and not a trigger finding
  (`emission_timing` ARM L already read this book LAG-TOLERANT within three
  sessions on v3; this is that control on THIS population and THIS basis).

  Session k here is the SAME numbering as ARM T's: k = 1 is entry_day = marks[0],
  so ARM L k fills at synth_trade(rec, k-1).""")
    out = {}
    for k in ARM_L_LAGS:
        rows = arm_l[k]["filled"]
        if not rows:
            print(f"\n  k={k}: no row filled — nothing to read.")
            out[k] = None
            continue
        ev = evaluate(paired_rows(rows, arm_l[k]["out"]))
        ev["powered"] = ev["c6_power"]
        ev["c7_no_flip"] = None
        ev["c8_bands"] = None
        lo, hi = ev["ci"]
        print(f"\n  k={k}  n={ev['n']} rows / {ev['n_dates']} dates   "
              f"shipped meanR {ev['mean_shipped']:+.4f}   lagged meanR "
              f"{ev['mean_variant']:+.4f}   DeltaR {ev['delta']:+.4f}   "
              f"CI[{lo:+.4f},{hi:+.4f}] "
              f"{'EXCLUDES 0' if ev['c1_ci'] else 'includes 0'}")
        print(f"     LOO min {ev['loo_min']:+.4f} over {ev['loo_folds']} folds; "
              f"tiers " + "  ".join(f"{t} {v:+.4f}" for t, (_n, v) in ev["tiers"].items()))
        out[k] = ev
    print("\n  ARM L carries NO verdict word of its own — it feeds L-SEP in the "
          "ARM T grammar.")
    return out


def matched_k(n: int) -> int:
    """The ARM L cell ARM T at window `n` is compared against: min(n, deepest lag)."""
    return min(n, max(ARM_L_LAGS))


def run_arm_d(recs: list[dict], scoped: list[dict], arm_t: dict) -> None:
    hdr("ARM D — DEPLOYMENT READ (shipped top-3/day ladder; R ONLY, no dollars)")
    print(f"""  `protocol.top_k_per_day(rows, protocol.ladder_rank, k={TOP_K}, eligible_fn=...)` —
  the shipped card — run twice on the SAME book. Baseline: the shipped picks at
  shipped pricing. Variant: NOT-ENTERED rows are made INELIGIBLE, so the slot
  FREES to the next-ranked play, and every entered in-scope row is priced at its
  trigger fill. Rows the trigger cannot be read on (out of scope) stay eligible
  at shipped pricing in BOTH books — the gate can only bind where the text
  supports it.""")
    base_pick = P.top_k_per_day(recs, P.ladder_rank, k=TOP_K,
                                eligible_fn=P.ladder_eligible)
    base_by_date: dict = defaultdict(list)
    for r in base_pick:
        base_by_date[str(r["date"])].append(r["_shipped"]["pnl_pct"])

    print(f"\n  {'cell':<8}{'picks':>7}{'dates':>7}{'mean R':>10}"
          f"{'paired DeltaR':>15}{'CI95':>26}")
    bR = statistics.fmean(v for vs in base_by_date.values() for v in vs)
    print(f"  {'shipped':<8}{len(base_pick):>7}{len(base_by_date):>7}{bR:>10.4f}"
          f"{'—':>15}{'—':>26}")
    for n in TRIGGER_N:
        res = arm_t[n]["out"]

        def eligible(r, res=res):
            if not P.ladder_eligible(r):
                return False
            o = res[id(r)]
            return o["status"] in ("out_of_scope", "entered")

        pick = P.top_k_per_day(recs, P.ladder_rank, k=TOP_K, eligible_fn=eligible)
        by_date: dict = defaultdict(list)
        for r in pick:
            by_date[str(r["date"])].append(res[id(r)]["out"]["pnl_pct"])
        vR = statistics.fmean(v for vs in by_date.values() for v in vs)
        paired = [dict(date=d, a=statistics.fmean(by_date[d]),
                       b=statistics.fmean(base_by_date[d]))
                  for d in sorted(set(by_date) & set(base_by_date))]
        delta = statistics.fmean(p["a"] - p["b"] for p in paired) if paired else float("nan")
        lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=BOOT_N, seed=BOOT_SEED)
        print(f"  {f'N={n}':<8}{len(pick):>7}{len(by_date):>7}{vR:>10.4f}"
              f"{delta:>15.4f}{f'[{lo:+.4f}, {hi:+.4f}]':>26}")
    print("\n  ARM D is a READ, not a criterion: it says what the gate would have done "
          "to the card,\n  in R. No dollar figure, no annualised figure, no Sharpe.")


def run_arm_t(scoped: list[dict], arm_t: dict, arm_l_ev: dict, powered: dict,
              census: dict) -> dict:
    hdr("ARM T — TRIGGER-GATED ENTRY (HEADLINE: paired-by-date DeltaR, "
        "trigger-priced vs the SAME rows' shipped replay)")
    print("""  Estimand: on the ENTERED rows only, mean R of the synthetic filled at the
  crossing session's CLOSE (contracts re-sized, dte shifted, shipped profile
  replayed through the UNMODIFIED frozen harness) minus mean R of the SAME rows'
  shipped replay (the stored trade under the same profile), aggregated by
  `protocol.boot_ci_paired_by_date` over DATES.

  This is THE PRICE OF CONFIRMATION. A positive delta says the trigger picks
  better than it costs; a negative one says the move that satisfied the trigger
  was already in the option's price.""")

    # criterion 7 needs every cell's sign first
    evs: dict = {}
    for n in TRIGGER_N:
        rows = arm_t[n]["entered"]
        if not rows:
            evs[n] = None
            continue
        ev = evaluate(paired_rows(rows, arm_t[n]["out"]))
        ev["powered"] = bool(powered[("T", n)])
        evs[n] = ev
    signs = {n: (1 if evs[n]["delta"] > 0 else (-1 if evs[n]["delta"] < 0 else 0))
             for n in TRIGGER_N if evs[n]}
    flip = len({s for s in signs.values() if s}) > 1
    sub("CRITERION 7 — no sign flip across the frozen N grid {1, 3, 5}")
    print("  " + "  ".join(f"N={n} {evs[n]['delta']:+.4f}" for n in TRIGGER_N if evs[n]))
    print(f"  sign flip across the grid: {'YES — criterion 7 FAILS every cell' if flip else 'no'}")

    verdicts = {}
    for n in TRIGGER_N:
        ev = evs[n]
        if ev is None:
            verdicts[n] = "UNDERPOWERED"
            print(f"\n  N={n}: no entered rows — UNDERPOWERED")
            continue
        ev["c7_no_flip"] = not flip
        sign = 1 if ev["delta"] > 0 else -1
        c8, note, table = arm_c_bands(arm_t[n]["entered"], arm_t[n]["out"], sign)
        ev["c8_bands"], ev["c8_note"] = c8, note
        ev["_bands"] = table

        lk = matched_k(n)
        lev = arm_l_ev.get(lk)
        if lev is None:
            l_sep, l_note = False, f"ARM L k={lk} did not run — L-SEP cannot hold"
        else:
            l_right = lev["c1_ci"] and ((lev["delta"] > 0) == (ev["delta"] > 0))
            bigger = abs(ev["delta"]) > abs(lev["delta"]) and \
                (ev["delta"] > 0) == (sign > 0)
            l_sep = bool(bigger and not l_right)
            l_note = (f"L-SEP {'HOLDS' if l_sep else 'FAILS'}: ARM T {ev['delta']:+.4f} "
                      f"vs ARM L k={lk} {lev['delta']:+.4f} "
                      f"(ARM L CI {'excludes' if lev['c1_ci'] else 'includes'} 0)")
        ev["_l_sep"], ev["_l_note"] = l_sep, l_note

        if not ev["powered"]:
            print(f"\n  N={n}: {ev['n']} rows / {ev['n_dates']} dates — "
                  f"UNDERPOWERED (floor {MIN_AFFECTED_ROWS} rows / "
                  f"{MIN_AFFECTED_DATES} dates). Census only, nothing read.")
            verdicts[n] = "UNDERPOWERED"
            continue

        print_cell(f"ARM T  N={n}", ev, extra=l_note)
        srcs = Counter(r["_scope"]["bar_source"] for r in arm_t[n]["entered"])
        print(f"    bar-tier split of the entered rows (never pooled silently): "
              f"{dict(srcs)}")
        print(f"    ARM C band table (next_day_move.DAY0_PNL_BANDS, "
              f"MIN_CELL_N={MIN_CELL_N}, imported verbatim):")
        for band, nb, d, status in table:
            ds = "   —   " if d is None else f"{d:+.4f}"
            print(f"      {band:<26} n={nb:>4}  DeltaR {ds}   {status}")
        v = verdict_for(ev, census.get(n, False), l_sep)
        verdicts[n] = v
        print(f"    VERDICT: {v}")
        print(f"    criteria vector: {criteria_vector(ev)}")
    return verdicts


# =============================================================================
# main
# =============================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--era", default=None,
                    help="era to run (default: STUDY_ERA, else `current`). The "
                         "runner sets STUDY_ERA for the whole suite; this flag "
                         "is the per-study equivalent and is printed in the header.")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="DEV/BUILD SMOKE ONLY: cap the book at N rows. A capped "
                         "run carries NO conclusion and says so in its header.")
    a = ap.parse_args(argv)

    rows, _unpriced, diag = load_corpus(era=a.era, include_bs=False)
    era = diag["era"]
    header(rows, diag, era)

    if a.max_rows is not None:
        rows = rows[:a.max_rows]
        print(f"\n  *** SMOKE RUN: book capped at {len(rows)} rows by --max-rows. "
              f"This is a BUILD\n      CHECK ONLY — no number below is a finding "
              f"and nothing here may be quoted. ***")

    hdr("CALIBRATION GATE — the baseline must reproduce before any variant is read")
    print("""  `exit_from_text.calibration_gate`, imported unchanged: every row is replayed
  under the profile PRODUCTION would actually have run on it (the shipped debit
  merge via `bear_giveback.prod_profile_for`, `CREDIT_PROD` for credits) and
  classified by `lib/replay_basis.classify`. Only rows that REPRODUCE (exact /
  near / boundary_tie) are admitted.

  Not a convenience: ARM T pairs a re-priced replay against the row's OWN
  shipped replay, so a row whose baseline does not reproduce would contribute a
  delta measured against a baseline production never ran. It is also what makes
  the E2 census below reproducible on this population.""")
    recs, tally = calibration_gate(rows)
    print(f"\n  {tally['exact']} exact, {tally['near']} near, "
          f"{tally['superseded']} superseded-basis, {tally['boundary_tie']} "
          f"boundary-tie, {tally['hard']} HARD  of {len(rows)}")
    print(f"  ADMITTED: {len(recs)} rows / {n_dates(recs)} dates "
          f"({len(recs) / len(rows):.1%} of the book)")
    if not recs:
        print("  CALIBRATION GATE: no row reproduces — nothing below can be read.")
        return EXIT_GATE_FAILURE
    # One profile definition, cross-checked against emission_timing's — the two
    # must agree or the arms and the baseline are on different bases.
    for r in recs:
        if profile_for(r) != r["_profile"]:
            fail(f"profile disagreement on {r['date']} {r['ticker']}: "
                 f"emission_timing.profile_for != calibration_gate's profile.")
    print(f"  shipped exit mix: "
          f"{dict(Counter(r['_shipped']['exit_reason'] for r in recs))}")

    bars_by_ticker = {tk: U.load_bars(tk) for tk in sorted({r["ticker"] for r in recs})}

    buckets: Counter = Counter()
    scoped: list[dict] = []
    for rec in recs:
        sc, bucket = in_scope(rec, bars_by_ticker)
        rec["_scope"] = sc
        buckets[bucket] += 1
        if sc is not None:
            scoped.append(rec)

    g1_parse_census(recs, buckets, scoped)
    if not scoped:
        print("\n  No row is in scope — nothing below can be read.")
        return EXIT_GATE_FAILURE

    arm_t = build_arm_t(recs)
    arm_l = build_arm_l(recs)

    powered = g0_power(scoped, arm_t)
    g2_construction(recs, scoped, arm_t, arm_l)
    g3_leak(recs, arm_t, arm_l)
    g4_sizing(scoped, arm_t, arm_l)
    g5_deadline(scoped, arm_t)

    hdr("SELECTION CENSUS + ARMS")
    census = e2_census(scoped, arm_t)
    arm_l_ev = run_arm_l(scoped, arm_l)
    verdicts = run_arm_t(scoped, arm_t, arm_l_ev, powered, census)
    run_arm_d(recs, scoped, arm_t)

    hdr("VERDICT SUMMARY — every cell in the frozen grid, regardless of outcome")
    print(f"  {'arm':<5}{'cell':<10}{'entered':>9}{'dates':>7}{'DeltaR':>10}  verdict")
    for n in TRIGGER_N:
        rows = arm_t[n]["entered"]
        d = (statistics.fmean(arm_t[n]["out"][id(r)]["out"]["pnl_pct"]
                              - r["_shipped"]["pnl_pct"] for r in rows)
             if rows else float("nan"))
        print(f"  {'T':<5}{f'N={n}':<10}{len(rows):>9}{n_dates(rows):>7}{d:>10.4f}  "
              f"{verdicts[n]}")
    tally_v = Counter(verdicts.values())
    print(f"\n  tally: {dict(tally_v)}")
    unknown = set(tally_v) - set(VERDICTS)
    if unknown:
        fail(f"verdict grammar violated: {sorted(unknown)} is not in the "
             f"registration's exhaustive list {list(VERDICTS)}.")
    print("""
  Verdict grammar (registration §"Verdicts, worded now"), EXHAUSTIVE and
  evaluated in this order, first match wins:
    UNDERPOWERED       a floor was not met; census published, nothing read.
    LATE-ENTRY         DeltaR <= 0 AND the E2-shape census reproduces at shipped
                       pricing: the signal works (the trigger sorts winners from
                       losers) but the confirmed entry comes AFTER the move it
                       selects on — the confirmation costs what it is worth.
    CONTRARY           CI excludes zero with DeltaR < 0 and no reproducing
                       census: the trigger is actively misleading. Fed to the
                       PROMPT-ROBUSTNESS list.
    CONFOUND-EXPLAINED criteria 1-7 clear, criterion 8 fails: the gain lives
                       outside the conformity bands, i.e. it is the day-0 move
                       `next_day_move` ARM C already owns.
    LAG-EXPLAINED      all eight clear but L-SEP fails: ARM L reproduces it with
                       no gate at all, so it is about WHEN, not WHICH.
    CANDIDATE          all eight clear AND L-SEP holds. An INTAKE proposal,
                       NEVER an exit rule and NEVER a ship: it becomes a written
                       proposal with its own rollback trigger and an
                       independent-window confirmation first.
    NULL               powered, nothing above matched. Recorded.

  ARM L, ARM C and ARM D carry no verdict word of their own; the E2-shape census
  carries none at all. R is the unit of every conclusion; NO dollar figure is
  quoted across arms, and no annualised figure, Sharpe or time-to-recover is
  printed anywhere above, by design.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
