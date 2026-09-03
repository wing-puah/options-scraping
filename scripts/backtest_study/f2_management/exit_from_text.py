"""exit_from_text — do the model's own trigger / invalidation / horizon lines beat the shipped exits?

PRE-REGISTERED 2026-09-02 in
`research/pre-registrations/f2_management/exit_from_text.md`, BEFORE this file
was written. That document is BINDING; nothing here may drift from it. Read it
first. In brief:

  Every emitted play states an entry TRIGGER, an INVALIDATION and a HORIZON;
  the backtest ignores all three. Three arms, frozen, no fourth:

  E1  invalidation-as-stop — exit at the close of the first session whose
      UNDERLYING close is beyond the parsed invalidation level, in the
      direction the STRUCTURE SIDE implies (long-delta below, short-delta
      above), buffer grid {0%, 1%, 2%}, fired AHEAD of the PROD stops with the
      rest of the shipped profile live behind it. Straddles and strangles use
      BREAKEVEN levels, never a strike.
  E2  trigger-as-entry-filter — the entry counts only if the trigger's price
      level was met within N in {1, 3} sessions of the signal date. A
      SELECTION effect, quoted as one, never as an exit improvement.
  E3  horizon-as-time-exit — replace PROD's `time_exit_dte_fraction 0.75` with
      the emitted `horizon`, everything else the shipped profile. The SURVIVAL
      CONTROL runs BEFORE any monotone claim.

  THE HARNESS IS NOT TOUCHED AND NOT COPIED. Every arm is pure COMPOSITION
  around the FROZEN `lib/harness.replay` (the `next_day_move` / `staged_exit`
  ARM E pattern): E1 replays the shipped profile and then, if the text stop
  fires STRICTLY EARLIER, overrides the outcome to `(text_stop, session, pnl
  at that session)`; E3 hands `replay` a different `tef` and reads what comes
  back; E2 changes no exit rule at all. `staged_exit`'s ARM T fork is NOT
  needed here and is not reproduced.

  CALIBRATION GATE FIRST. Every row is replayed under the profile PRODUCTION
  would actually have run on it (the shipped debit merge, `CREDIT_PROD` for
  credits) and classified by `lib/replay_basis.classify`. Only rows that
  REPRODUCE (exact / near / boundary_tie) enter the variant arms; superseded
  and HARD rows are excluded and counted. A variant read off a row whose
  baseline does not reproduce is a finding about the replay, not about the
  text.

Verdicts, per the registration's grammar: UNDERPOWERED / NULL / CANDIDATE /
CONTRARY / SURVIVAL-ARTIFACT (E3 only) / NO PRE-REGISTERED VERDICT MATCHES.
Nothing ships from a research-tier study. Read-only; touches no config. Run:

    python -m scripts.backtest_study run exit_from_text
    STUDY_ERA=v3 python -m scripts.backtest_study run exit_from_text --era v3

BUILD-TIME DEVIATIONS, all appended to the registration as dated wording
corrections rather than resolved silently here:

  1. E3's horizon is mapped to a CALENDAR-DAY count, not a session count. The
     frozen harness's time exit compares `(day - signal_date).days >= int(
     dte_entry * tef)` — calendar days — so a session-count mapping is
     unreachable without forking the engine, which the registration forbids.
     `horizon_tef` inverts that expression exactly.
  2. A text stop that fires on the SAME session as the shipped exit leaves the
     outcome unchanged (the variant is the EARLIER of the two). On a tie the
     pnl and days_held are identical by construction and only the label would
     move; counting a label-only change as AFFECTED would zero-inflate the
     affected set, which is precisely what criterion 2's affected-dates median
     exists to defend against.
  3. LONG-VOL (debit) straddles / strangles have no breakeven-beyond stop side
     — beyond a breakeven is where such a position WINS — so they go to the
     unusable bucket `long_vol_no_stop_side` and are reported there, rather
     than being given a stop that fires on the profit side.
  4. `iron_condor` / `butterfly` / `calendar` are neither delta-directional nor
     covered by the straddle/strangle breakeven bullet; they go to the
     `no_structure_side` bucket and are reported.
"""
from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import (  # noqa: E402
    hdr, prod_profile_for, sub,
)
from scripts.backtest_study.lib.book import CREDIT_PROD  # noqa: E402
from scripts.backtest_study.lib.harness import Trade, replay  # noqa: E402
from scripts.backtest_study.lib.replay_basis import classify, unreachable_reasons  # noqa: E402
from scripts.backtest_study.lib.text_corpus import load_corpus  # noqa: E402

# The runner promotes `-latest.txt` on these codes instead of deleting it. It
# finds them by AST parse, so this MUST stay a PLAIN SET LITERAL — a
# `frozenset(...)` call is invisible to `ast.literal_eval` and the refusal would
# be misfiled as a failure. {2, 3} are `era.EXIT_THIN_ERA` / `EXIT_ERA_MISMATCH`,
# raised by `load_book` when the exports on disk are not the era asked for.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

OUT_DIR = ROOT / "backtests" / "study_output"

# --- FROZEN GRID (pre-registration §Arms). May not move. ---------------------

BUFFERS = (0.0, 0.01, 0.02)      # E1 buffer grid, frozen at three values
TRIGGER_N = (1, 3)               # E2 "met within N sessions", frozen at two
HORIZON_BUCKETS = (14, 60, 180, 720)   # E3, the v4 numeric horizon vocabulary

# --- Gate constants, all declared before any count was known -----------------

MIN_AFFECTED_ROWS = 60           # power floor, and criterion 6
MIN_AFFECTED_DATES = 25          # power floor, and criterion 6
BOOT_N = P.BOOT_N                # 10000, alpha = .05

# The `level == a strike` tolerance, FIXED HERE BEFORE THE RUN as the
# registration requires ("tolerance fixed in the module before the run"). A
# level is "a strike" when it lands within 0.5% of any strike in the position's
# own legs, floored at one cent so a $2 strike is not matched by a $0.01 band
# that rounds to nothing. Relative, because a 0.5-point gap means something
# different on a $9 name and a $900 one.
STRIKE_TOL_REL = 0.005
STRIKE_TOL_ABS = 0.01

# The two windows `protocol.window_cuts` drops ONE AT A TIME. Criterion 3 also
# requires the ex-BOTH cut, added by hand here: `window_cuts()` leaves a gap
# through which a result carried by the union of the two windows walks.
_BOTH_WINDOW_MONTHS = {m for months in P.DOMINANT_WINDOWS.values() for m in months}

# --- structure sides ----------------------------------------------------------
#
# Inferred from the STRUCTURE, never from the outcome (registration §E1). The
# lists are the canonical `structure` vocabulary `scripts/backtest/classify.py`
# writes; an unknown name falls to `no_structure_side` and is COUNTED, never
# guessed at.

LONG_DELTA = ("bull_call_spread", "bull_put_spread", "long_call", "short_put")
SHORT_DELTA = ("bear_put_spread", "bear_call_spread", "long_put", "short_call")
VOL_STRUCTURES = ("straddle", "strangle")

EXIT_GATE_FAILURE = 1            # a real failure, NOT a designed refusal


# =============================================================================
# text parsing that is NOT in lib/text_corpus.py
# =============================================================================
#
# `lib/text_corpus.py` is a FROZEN INPUT here: it supplies `invalidation_level`,
# `trigger_level`, `trigger_conditional` and `parsed.structure_text`. What it
# does NOT supply is a DIRECTION for a trigger level, which E2 needs ("in scope
# only if the trigger parses to a numeric price level WITH A DIRECTION"). That
# parse lives here, in the study that needs it, rather than being added to a
# shared module another study already reads.

_ABOVE_WORDS = re.compile(
    r"(?i)\b(above|over|holds?|holding|reclaims?|retakes?|clears?|through|"
    r"break(?:s|ing)?\s+(?:out\s+)?above|trades?\s+above|closes?\s+above|"
    r"back\s+above|>=?|at\s+or\s+above)\b|>")
_BELOW_WORDS = re.compile(
    r"(?i)\b(below|under|loses?|losing|breaks?\s+down|break(?:s|ing)?\s+below|"
    r"trades?\s+below|closes?\s+below|back\s+below|fails?|<=?|at\s+or\s+below)\b|<")

# How far back of the level token a direction word may sit and still be read as
# governing it. "ETHA holds 34 on a daily close" is 6 characters; "a daily close
# below the 32 shelf" is 22. 60 covers the clause without reaching the previous
# sentence.
_DIRECTION_WINDOW = 60


def _level_tokens(level: float) -> list[str]:
    """The string forms a level may appear as in the source text.

    `parse_price_levels` returns floats, so 34 comes back as 34.0 and the
    literal "34" has to be reconstructed to be located again.
    """
    out = [f"{level:g}"]
    if float(level).is_integer():
        out.append(str(int(level)))
    else:
        out.append(f"{level:.2f}".rstrip("0").rstrip("."))
    return list(dict.fromkeys(out))


def trigger_direction(text: str | None, level: float | None) -> str | None:
    """"above" / "below" for the direction the trigger names, or None.

    Read off the words IMMEDIATELY BEFORE the level's first occurrence, which
    is where this corpus puts them ("holds 34 on a daily close", "only if it
    closes below 290"). The NEAREST direction word wins — a clause can contain
    both ("above 34, skip if it opens below 33") and the one attached to THIS
    level is the last one before it.

    None is a real answer and its rows go to the `no_direction` bucket; nothing
    here guesses a side.
    """
    if not isinstance(text, str) or not text.strip() or level is None:
        return None
    pos = -1
    for tok in _level_tokens(level):
        i = text.find(tok)
        if i != -1 and (pos == -1 or i < pos):
            pos = i
    if pos == -1:
        return None
    window = text[max(0, pos - _DIRECTION_WINDOW):pos]
    last_above = max((m.start() for m in _ABOVE_WORDS.finditer(window)), default=-1)
    last_below = max((m.start() for m in _BELOW_WORDS.finditer(window)), default=-1)
    if last_above == last_below == -1:
        return None
    return "above" if last_above > last_below else "below"


def structure_side(structure: str, credit: bool) -> str | None:
    """"long" / "short" / "vol" for a canonical structure name, else None.

    "long" and "short" are DELTA sides, which is what E1's direction rule keys
    on. "vol" is the straddle/strangle family, which the registration routes to
    the breakeven basis instead. `credit` is not consulted for the directional
    families — a bull put spread is long delta whether or not it was opened for
    a credit — and is used only by `breakeven_levels`.
    """
    if structure in LONG_DELTA:
        return "long"
    if structure in SHORT_DELTA:
        return "short"
    if structure in VOL_STRUCTURES:
        return "vol"
    return None


def strikes_of(t: Trade) -> list[float]:
    """The strikes of the position's own legs — the trade, not the prose.

    `features["parsed"]["structure_text"]` carries the strikes the model WROTE;
    these are the strikes the backtest actually priced. The `level == a strike`
    split is a statement about the position, so it is taken from the legs.
    """
    return sorted({leg.strike for leg in t.legs})


def level_is_a_strike(level: float | None, strikes: list[float]) -> bool | None:
    """Is `level` one of `strikes`, within the tolerance fixed above?

    None when there is no level to test — distinct from False, which is the
    registered SECOND cell ("the result must be carried by the SECOND cell")
    and must not be padded with rows that have nothing to compare.
    """
    if level is None or not strikes:
        return None
    for k in strikes:
        if abs(level - k) <= max(STRIKE_TOL_ABS, STRIKE_TOL_REL * k):
            return True
    return False


def breakeven_levels(t: Trade, buffer: float) -> list[tuple[str, float]] | None:
    """[(direction, level)] — the SHORT-VOL breakevens, buffered outward.

    The registration: "Straddles and strangles use BREAKEVEN levels, never a
    strike (Attempt 9: a strike basis fires day 1 when the short strike is
    ~ATM)." A short straddle/strangle loses OUTSIDE its breakevens, so the two
    levels are `highest call strike + credit` (above) and `lowest put strike -
    credit` (below), each pushed a further `buffer` away — the same sense the
    directional buffer has, harder to fire rather than easier.

    `credit` here is `abs(entry_net)`, the per-unit net the harness itself
    denominates on (`Trade.denom`), so this matches `harness.breach_thresholds`'
    straddle branch exactly rather than inventing a second definition.

    None when the position has no call leg or no put leg — a breakeven cannot be
    computed and the row goes to the unusable bucket, never to a strike
    fallback.
    """
    calls = [leg.strike for leg in t.legs if leg.opt_type == "Call"]
    puts = [leg.strike for leg in t.legs if leg.opt_type == "Put"]
    if not calls or not puts:
        return None
    net = t.denom
    return [("above", (max(calls) + net) * (1 + buffer)),
            ("below", (min(puts) - net) * (1 - buffer))]


def stop_levels(rec: dict, buffer: float) -> tuple[list[tuple[str, float]] | None, str, str | None]:
    """`(levels, basis, unusable_reason)` for E1 on one row.

    `basis` is "text_level" or "breakeven"; `unusable_reason` names the bucket
    when no stop can be formed. Buckets, all counted and reported and none of
    them dropped:

      no_structure_side     — the structure is neither delta-directional nor a
                              straddle/strangle (iron_condor, butterfly,
                              calendar). Deviation 4 in the module docstring.
      long_vol_no_stop_side — a DEBIT straddle/strangle. Beyond a breakeven is
                              where it wins, so a breakeven-beyond stop would
                              fire on the profit side. Deviation 3.
      no_breakeven          — a straddle/strangle with no call or no put leg.
      no_level              — the prompt emitted an invalidation with no
                              parseable price level. THE prompt-robustness
                              finding, reported whatever else happens.
    """
    t = rec["t"]
    side = structure_side(rec["structure"], rec["credit"])
    if side is None:
        return None, "", "no_structure_side"
    if side == "vol":
        if not rec["credit"]:
            return None, "", "long_vol_no_stop_side"
        lv = breakeven_levels(t, buffer)
        if lv is None:
            return None, "", "no_breakeven"
        return lv, "breakeven", None
    level = (rec["features"] or {}).get("invalidation_level")
    if level is None:
        return None, "", "no_level"
    if side == "long":
        return [("below", level * (1 - buffer))], "text_level", None
    return [("above", level * (1 + buffer))], "text_level", None


# =============================================================================
# E1 — the stop itself
# =============================================================================

def stop_session(t: Trade, levels: list[tuple[str, float]],
                 bars: dict) -> tuple[int | None, str | None]:
    """`(1-based grid session the stop fires on, unusable_reason)`.

    Alignment, which is where this arm is easiest to get silently wrong:

      * the grid is `_weekday_grid` — WEEKDAYS after the signal date — and the
        option marks CARRY FORWARD across a market holiday, so a closed session
        looks like a perfectly good one. `underlying.entry_day(t, sessions=...)`
        is the repo's single answer to that (23 of 795 v3 rows resolve to
        Juneteenth 2024 or a mourning closure without it) and is used here;
        `MAX_ENTRY_LAG_DAYS` bounds the skip and returns None on a hole in the
        bar series.
      * a session is evaluated only when it has BOTH an underlying bar and an
        option mark. A day with no bar cannot be read; a day with no mark cannot
        be EXITED at — the position would have to be priced at a mark that does
        not exist. Such a session is skipped and the scan continues, exactly as
        `replay` skips an unpriced day without evaluating a rule.
      * the comparison is strict (`>` / `<`), matching `harness.replay`'s own
        underlying-breach test, so a close exactly ON the level does not fire.

    Returns `(None, reason)` when no stop can be evaluated at all, and
    `(None, None)` when the stop simply never fired.
    """
    if not bars:
        return None, "no_bars"
    ed = U.entry_day(t, sessions=set(bars))
    if ed is None:
        return None, "no_entry_session"
    for i, (day, m) in enumerate(zip(t.grid, t.marks), start=1):
        if day < ed or m is None:
            continue
        bar = bars.get(day)
        if bar is None:
            continue
        s = bar.c
        if any((d == "above" and s > lvl) or (d == "below" and s < lvl)
               for d, lvl in levels):
            return i, None
    return None, None


def e1_outcome(rec: dict, session: int | None) -> dict:
    """The E1 outcome for one row: the EARLIER of the text stop and PROD.

    Pure composition around the frozen replay — `rec["_shipped"]` is
    `harness.replay` under the row's own shipped profile and is returned
    UNCHANGED whenever the text stop does not strictly precede it. See
    deviation 2 in the module docstring for why a same-session fire is not a
    change.
    """
    base = rec["_shipped"]
    if session is None or session >= base["days_held"]:
        return base
    m = rec["t"].marks[session - 1]
    if m is None:                       # unreachable: `stop_session` requires a mark
        return base
    return dict(exit_reason="text_stop", days_held=session,
                pnl_pct=round(rec["t"].pnl_of(m), 10))


def post_exit_max(t: Trade, days_held: int) -> float | None:
    """Max rounded mark P&L over the row's own grid AFTER `days_held`.

    The MFE give-back measurement: what the position went on to do once the
    variant had sold it. None when nothing priced remains, in which case the
    row cannot be a give-back at all.
    """
    vals = [round(t.pnl_of(m), 10)
            for i, m in enumerate(t.marks, start=1)
            if i > days_held and m is not None]
    return max(vals) if vals else None


# =============================================================================
# E3 — horizon as a time exit
# =============================================================================

def horizon_of(rec: dict) -> int | None:
    """The emitted horizon as an integer DTE, or None.

    v4 writes `horizon` NUMERIC (14 / 60 / 180 / 720); the analysis export
    carries it as "60.0". A value outside the frozen bucket vocabulary is
    returned as None and counted — the buckets are mapped ONCE and frozen, so
    an unseen value is a census line, not a new bucket.
    """
    raw = str(rec.get("horizon") or "").strip()
    if not raw:
        return None
    try:
        v = int(round(float(raw)))
    except ValueError:
        return None
    return v if v in HORIZON_BUCKETS else None


def horizon_tef(horizon_days: int, dte_entry: float) -> float | None:
    """The `tef` that makes the FROZEN harness time-exit at `horizon_days`.

    `replay` computes `te_day = int(dte_entry * tef)` and compares it against
    CALENDAR days since the signal. Handing it `(H + 0.5) / dte_entry` makes
    `int(...)` land on exactly H regardless of float error, without touching the
    engine. This is deviation 1 in the module docstring: the registration says
    "mapped to a session count", and a session count is unreachable through the
    frozen engine, whose time exit is calendar-day based.
    """
    if not dte_entry or dte_entry <= 0:
        return None
    return (horizon_days + 0.5) / dte_entry


def e3_outcome(rec: dict, horizon_days: int) -> dict:
    """Replay the shipped profile with PROD's `tef` replaced by the horizon."""
    tef = horizon_tef(horizon_days, rec["t"].dte_entry)
    if tef is None:
        return rec["_shipped"]
    return replay(rec["t"], **{**rec["_profile"], "tef": tef})


def terciles(values: list[float]) -> tuple[float, float]:
    """The two boundaries splitting `values` into terciles. Disclosed in the report."""
    vals = sorted(values)
    if len(vals) < 3:
        return (float("nan"), float("nan"))
    q = statistics.quantiles(vals, n=3, method="inclusive")
    return (q[0], q[1])


def tercile_label(days_held: float, t1: float, t2: float) -> str:
    """"T1" / "T2" / "T3" for a hold length against the disclosed boundaries.

    Boundaries are INCLUSIVE at the top of each tercile, which is what makes the
    printed "T1 <= t1 < T2 <= t2 < T3" line describe the bucketing exactly.
    `days_held` is an integer session count, so ties on a boundary land in the
    LOWER bucket rather than being split by a rule nobody can read off the
    header.
    """
    if days_held <= t1:
        return "T1"
    return "T2" if days_held <= t2 else "T3"


def trigger_met(bars: dict, entry_day, level: float, direction: str, n: int) -> bool:
    """Was `level` met on a close within `n` sessions from `entry_day` inclusive?

    "Met" is INCLUSIVE (`>=` above, `<=` below): a trigger reading "holds 34"
    is met by a close of exactly 34. That is the opposite convention from E1's
    strict breach, and deliberately so — E1 mirrors `harness.replay`'s own
    strict underlying test, while a trigger is a condition the operator would
    have called satisfied at the level.

    `entry_day` is `underlying.entry_day`'s answer — the session the position
    was actually filled in, which is the first session AFTER the signal date and
    skips a market holiday. Sessions are counted on the BAR SERIES, so a
    holiday inside the window does not consume one of the N.
    """
    days = U.sessions_from(bars, entry_day, n)
    return any(bars[d].c >= level if direction == "above" else bars[d].c <= level
               for d in days)


# =============================================================================
# metrics
# =============================================================================

def changed(a: dict, b: dict) -> bool:
    """`lib/triggers.py::is_affected`'s identity triple, both sides from a replay."""
    return (a["exit_reason"], a["days_held"], round(a["pnl_pct"], 10)) != \
           (b["exit_reason"], b["days_held"], round(b["pnl_pct"], 10))


def loo_fold_gains(rows: list[dict]) -> dict[str, float]:
    """`{left-out date: mean(a) - mean(b) over the rest}`.

    The same formula `protocol.loo_by_date` aggregates, exposed PER FOLD so the
    registration's corrected gate — "the LOO median fold gain > 0 AMONG
    AFFECTED DATES" (2026-07-22) — can be evaluated on the affected subset of
    folds. A whole-population median is untrippable on a zero-inflated delta,
    which is what that correction was for. `evaluate_cell` cross-checks the
    minimum of these against `protocol.loo_by_date`'s own `min_gain`, so the
    two can never silently disagree.
    """
    dates = sorted({str(r["date"]) for r in rows})
    if len(dates) < 3:
        return {}
    out = {}
    for d in dates:
        kept = [r for r in rows if str(r["date"]) != d]
        if not kept:
            continue
        out[d] = (statistics.fmean(r["a"] for r in kept)
                  - statistics.fmean(r["b"] for r in kept))
    return out


def source_split(rows: list[dict]) -> str:
    """The SRC_OHLC / SRC_TILDE census line. Printed, never pooled silently."""
    c = Counter(r.get("bar_source") or "no_bars" for r in rows)
    return "  ".join(f"{k}={v}" for k, v in sorted(c.items()))


def worst_decile_note(paired: list[dict]) -> str:
    """DESCRIPTIVE ONLY, marked NOT A CRITERION (the 2026-08-13 decile wall)."""
    by_date: dict[str, list[dict]] = {}
    for p in paired:
        by_date.setdefault(str(p["date"]), []).append(p)
    if not by_date:
        return "worst decile: no rows   NOT A CRITERION"
    ranked = sorted(by_date.items(),
                    key=lambda kv: statistics.fmean(p["b"] for p in kv[1]))
    k = max(1, len(ranked) // 10)
    worst = [p for _d, rs in ranked[:k] for p in rs]
    g = statistics.fmean(p["a"] - p["b"] for p in worst)
    return (f"worst decile of dates by shipped mean: {k} dates / {len(worst)} rows, "
            f"gain {g:+.3f}   NOT A CRITERION")


def evaluate_cell(paired: list[dict], affected_dates: set[str],
                  n_aff_rows: int, n_aff_dates: int,
                  c7: bool | None, c7_label: str) -> dict:
    """The full conjunction 1-7 for one powered cell. Returns every component.

    `paired` rows carry `date`, `a` (variant R), `b` (shipped R), `source`
    (pricing tier) and `bar_source`. `c7` is the arm's own seventh criterion —
    the E1 perturbation-flip check or E3's survival control — passed in because
    it is a property of the GRID, not of a single cell's rows.
    """
    out: dict = {}
    out["n"] = len(paired)
    out["mean_shipped"] = statistics.fmean(p["b"] for p in paired)
    out["mean_variant"] = statistics.fmean(p["a"] for p in paired)
    out["delta"] = out["mean_variant"] - out["mean_shipped"]

    lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=BOOT_N)
    out["ci"] = (lo, hi)

    # PF beside mean R, never alone (registration §Metrics, binding rule).
    out["pf_variant"] = P.pf([dict(date=p["date"], R=p["a"]) for p in paired])
    out["pf_shipped"] = P.pf([dict(date=p["date"], R=p["b"]) for p in paired])
    out["pf_paired"] = P.pf_paired_by_date(
        [dict(date=p["date"], R=p["a"]) for p in paired],
        [dict(date=p["date"], R=p["b"]) for p in paired], n=BOOT_N)

    _mean, _share, loo_min, n_folds = P.loo_by_date(
        paired, lambda p: p["a"], lambda p: p["b"])
    folds = loo_fold_gains(paired)
    # The two must agree — one formula, two call sites.
    if folds and n_folds:
        assert abs(min(folds.values()) - loo_min) < 1e-9, "LOO fold formulas disagree"
    aff_folds = [g for d, g in folds.items() if d in affected_dates]
    out["loo_min"], out["loo_folds"] = loo_min, n_folds
    out["loo_aff_median"] = statistics.median(aff_folds) if aff_folds else None
    out["loo_aff_n"] = len(aff_folds)

    cuts = P.window_cuts(paired)
    cuts["ex_BOTH"] = [p for p in paired if str(p["date"])[:7] not in _BOTH_WINDOW_MONTHS]
    out["cuts"] = {name: (len(rs),
                          statistics.fmean(p["a"] - p["b"] for p in rs) if rs else None)
                   for name, rs in cuts.items()}

    out["years"] = {y: (len(rs), statistics.fmean(p["a"] - p["b"] for p in rs))
                    for y, rs in P.by_year(paired).items()}
    out["tiers"] = {}
    for tier in ("real", "tweak"):
        rs = [p for p in paired if p["source"] == tier]
        if rs:
            out["tiers"][tier] = (len(rs), statistics.fmean(p["a"] - p["b"] for p in rs))
    out["bar_sources"] = {}
    for src in sorted({p.get("bar_source") for p in paired if p.get("bar_source")}):
        rs = [p for p in paired if p.get("bar_source") == src]
        out["bar_sources"][src] = (len(rs), statistics.fmean(p["a"] - p["b"] for p in rs))

    positive = out["delta"] > 0
    c1 = (lo > 0) if positive else (hi < 0)
    c2 = (n_folds > 0 and (loo_min > 0 if positive else max(folds.values()) < 0)
          and out["loo_aff_median"] is not None
          and (out["loo_aff_median"] > 0 if positive else out["loo_aff_median"] < 0))

    def _right(v):
        return v is not None and (v > 0 if positive else v < 0)
    c3 = all(_right(v) for _n, v in out["cuts"].values())
    c4 = bool(out["years"]) and all(_right(v) for _n, v in out["years"].values())
    c5 = bool(out["tiers"]) and all(_right(v) for _n, v in out["tiers"].values())
    c6 = n_aff_rows >= MIN_AFFECTED_ROWS and n_aff_dates >= MIN_AFFECTED_DATES
    c7v = bool(c7)
    out["criteria"] = {"1_ci": c1, "2_loo": c2, "3_windows": c3, "4_years": c4,
                       "5_tiers": c5, "6_power": c6, f"7_{c7_label}": c7v}
    out["conjunction"] = c1 and c2 and c3 and c4 and c5 and c6 and c7v

    if out["conjunction"] and positive:
        out["verdict"] = "CANDIDATE"
    elif c1 and not positive:
        # Powered, CI excludes zero, sign OPPOSITE the arm's hypothesis.
        out["verdict"] = "CONTRARY"
    elif not out["conjunction"]:
        out["verdict"] = "NULL"
    else:
        out["verdict"] = "NO PRE-REGISTERED VERDICT MATCHES"
    return out


def print_cell(label: str, ev: dict, n_aff_rows: int, n_aff_dates: int,
               c7_label: str, extra: str = "") -> None:
    sub(label)
    print(f"  population {ev['n']} rows   affected {n_aff_rows} rows / "
          f"{n_aff_dates} dates")
    pfv = "n/a" if ev["pf_variant"] is None else f"{ev['pf_variant']:.2f}"
    pfs = "n/a" if ev["pf_shipped"] is None else f"{ev['pf_shipped']:.2f}"
    print(f"  shipped meanR {ev['mean_shipped']:>+7.3f}   "
          f"variant meanR {ev['mean_variant']:>+7.3f}   "
          f"DeltaR {ev['delta']:>+7.3f}")
    pd_point, pd_lo, pd_hi = ev["pf_paired"]
    pdp = "n/a" if pd_point is None else f"{pd_point:+.2f}"
    print(f"  PF shipped {pfs}  variant {pfv}  paired diff {pdp} "
          f"[{pd_lo:+.2f}, {pd_hi:+.2f}]   (PF never stands without mean R)")
    lo, hi = ev["ci"]
    print(f"  1 CI95 (date-clustered, n={BOOT_N}) [{lo:+.3f}, {hi:+.3f}]"
          f"   {'PASS' if ev['criteria']['1_ci'] else 'FAIL'}")
    med = ev["loo_aff_median"]
    meds = "n/a" if med is None else f"{med:+.3f}"
    print(f"  2 LOO min fold {ev['loo_min']:>+7.3f} over {ev['loo_folds']} folds; "
          f"median among {ev['loo_aff_n']} AFFECTED-date folds {meds}"
          f"   {'PASS' if ev['criteria']['2_loo'] else 'FAIL'}")
    cutbits = "  ".join(f"{name} {('%+.3f' % v) if v is not None else '(none)'} (n={n})"
                        for name, (n, v) in ev["cuts"].items())
    print(f"  3 windows: {cutbits}   {'PASS' if ev['criteria']['3_windows'] else 'FAIL'}")
    yearbits = "  ".join(f"{y} {v:+.3f} (n={n})" for y, (n, v) in ev["years"].items())
    print(f"  4 years: {yearbits}   {'PASS' if ev['criteria']['4_years'] else 'FAIL'}")
    tierbits = "  ".join(f"{t} {v:+.3f} (n={n})" for t, (n, v) in ev["tiers"].items())
    print(f"  5 pricing tiers: {tierbits or '(none)'}"
          f"   {'PASS' if ev['criteria']['5_tiers'] else 'FAIL'}")
    print(f"  6 power: {n_aff_rows} rows / {n_aff_dates} dates"
          f"   {'PASS' if ev['criteria']['6_power'] else 'FAIL'}")
    print(f"  7 {c7_label}: {'PASS' if ev['criteria'][f'7_{c7_label}'] else 'FAIL'}")
    if ev["bar_sources"]:
        bits = "  ".join(f"{s} {v:+.3f} (n={n})" for s, (n, v) in ev["bar_sources"].items())
        print(f"  bar-source split (never pooled silently): {bits}")
    if extra:
        print(f"  {extra}")
    print(f"  {worst_decile_note(ev['_paired'])}")
    print(f"  VERDICT: {ev['verdict']}")
    if ev["verdict"] in ("CANDIDATE", "CONTRARY"):
        vec = "  ".join(f"{k}={'T' if v else 'F'}" for k, v in ev["criteria"].items())
        print(f"  criteria vector: {vec}")
        if ev["verdict"] == "CONTRARY":
            print("  (every criterion above is evaluated toward the OBSERVED sign, "
                  "which is\n   NEGATIVE here: the text-derived exit is reliably WORSE "
                  "than PROD on this\n   cell, stably across folds, windows, years and "
                  "both pricing tiers. That is\n   the registered CONTRARY finding, not "
                  "a passed CANDIDATE conjunction.)")


# =============================================================================
# cells
# =============================================================================

def cell_keys(rec: dict, extra: tuple = ()) -> list[tuple]:
    """The registered cell families a row belongs to.

    The registration cuts cells "per STRUCTURE and per `mech_cell`" and the
    power floor names the full cross "(arm x structure x mech_cell x grid
    value)". Both are reported: the two marginals AND the cross, each with the
    floor applied to it. The pooled headline is printed for orientation and is
    NOT A CRITERION, exactly as registered.
    """
    keys = [("ALL", "ALL"), ("STRUCT", rec["structure"]), ("MECH", rec["mech_cell"]),
            ("CROSS", f"{rec['structure']}|{rec['mech_cell']}")]
    return [(fam, val) + extra for fam, val in keys]


def census_and_evaluate(cells: dict, c7_by_cell: dict, c7_label: str,
                        title: str) -> dict:
    """Census every cell, then evaluate the powered ones. Returns verdicts.

    `cells[key] = dict(paired=[...], affected_dates=set, n_aff_rows=int)`.
    Every cell is reported regardless of outcome (registration §Anti-tuning);
    an underpowered cell prints its census line and nothing is read from it.
    """
    hdr(title)
    print(f"""  Floor, declared in the registration before any count was known: a cell
  with < {MIN_AFFECTED_DATES} affected DATES or < {MIN_AFFECTED_ROWS} affected ROWS is UNDERPOWERED — printed
  with its n, no criterion evaluated, nothing refuted. A 3-arm x structure x
  mech_cell x grid design on a v4 book UNDERPOWERS most cells; that is the
  expected outcome, not a failure.

  The ALL row is the POOLED headline: orientation only, NOT A CRITERION —
  Attempts 12 and 13b are explicit that exit behaviour is regime-conditional,
  so a pooled exit read is not interpretable.

  Every population below is a PRICEABLE subset (see the priceability line in the
  header): an exit rule replays only on a row that priced.""")
    print(f"\n  {'family':<7}{'cell':<40}{'grid':<10}{'pop':>6}{'aff rows':>10}"
          f"{'aff dates':>10}  status")
    powered = {}
    for key in sorted(cells, key=lambda k: (str(k[0]), str(k[1]), str(k[2:]))):
        c = cells[key]
        ok = (c["n_aff_rows"] >= MIN_AFFECTED_ROWS
              and len(c["affected_dates"]) >= MIN_AFFECTED_DATES)
        powered[key] = ok
        fam, val = key[0], key[1]
        grid = "/".join(str(x) for x in key[2:])
        print(f"  {fam:<7}{str(val)[:39]:<40}{grid:<10}{len(c['paired']):>6}"
              f"{c['n_aff_rows']:>10}{len(c['affected_dates']):>10}  "
              f"{'powered' if ok else 'UNDERPOWERED'}")
    n_ok = sum(1 for v in powered.values() if v)
    print(f"\n  {n_ok} of {len(powered)} cells clear the floor; "
          f"{len(powered) - n_ok} are UNDERPOWERED.")

    verdicts: dict = {}
    for key in sorted(cells, key=lambda k: (str(k[0]), str(k[1]), str(k[2:]))):
        c = cells[key]
        fam, val = key[0], key[1]
        grid = "/".join(str(x) for x in key[2:])
        label = f"{fam}  {val}  [{grid}]"
        if fam == "ALL":
            label += "   (POOLED — NOT A CRITERION)"
        if not powered[key]:
            verdicts[key] = "UNDERPOWERED"
            continue
        ev = evaluate_cell(c["paired"], c["affected_dates"], c["n_aff_rows"],
                           len(c["affected_dates"]), c7_by_cell.get(key), c7_label)
        ev["_paired"] = c["paired"]
        print_cell(label, ev, c["n_aff_rows"], len(c["affected_dates"]),
                   c7_label, extra=c.get("extra", ""))
        verdicts[key] = ("NOT A CRITERION (pooled): " + ev["verdict"]) if fam == "ALL" \
            else ev["verdict"]
    return verdicts


# =============================================================================
# ARM E1
# =============================================================================

def run_e1(recs: list[dict], bars_by_ticker: dict, csv_rows: list) -> dict:
    hdr("E1 — INVALIDATION-AS-STOP")
    print("""  Rule (registration §E1): exit at the close of the first session whose
  UNDERLYING close is beyond the parsed invalidation level, in the direction
  the STRUCTURE SIDE implies — long-delta on a close BELOW, short-delta ABOVE.
  Direction is inferred from the structure, NEVER from the outcome. The rule
  fires AHEAD of the PROD stops, which stay live behind it unchanged, so the
  variant exit is the EARLIER of the text stop and the shipped exit.

  Buffer grid FROZEN at {0%, 1%, 2%}: 0% is the null arm and >=1% the expected
  shape, because Attempt 9's transferable observation is that a 0% level clips
  marginal touches (XOM, 109.72 against a 110 level). Declared there, not here.

  Straddles and strangles use BREAKEVEN levels, never a strike.

  The whipsaw caveat is REGISTERED, not discovered: Attempt 9's July-2024
  cluster showed an underlying stop does not rescue gap/whipsaw losers — it
  exits them where the mark stop does. Criterion 2 (every LOO fold positive,
  and the median positive among AFFECTED dates) is the mechanical guard.""")

    # --- parse / usability census (the prompt-robustness finding) ---
    buckets: Counter = Counter()
    usable: list[dict] = []
    for rec in recs:
        levels, basis, reason = stop_levels(rec, 0.0)
        if reason:
            buckets[reason] += 1
            continue
        bars = bars_by_ticker.get(rec["ticker"], {})
        _sess, why = stop_session(rec["t"], levels, bars)
        if why:
            buckets[why] += 1
            continue
        rec["_e1_basis"] = basis
        rec["_e1_bar_source"] = next(iter({b.source for b in bars.values()}), None) \
            if bars else None
        usable.append(rec)
    buckets["usable"] = len(usable)

    sub("PARSE / USABILITY CENSUS — reported as a PROMPT-ROBUSTNESS finding")
    total = len(recs)
    for k, v in sorted(buckets.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<24} {v:>5}  ({v / total:.1%} of {total} calibrated rows)")
    print("""  `no_level` is the prompt-robustness headline: the share of plays whose
  stated invalidation carries no parseable price level, i.e. an invalidation
  the operator cannot act on. It is counted, never dropped and never imputed.""")

    strikes_split = Counter()
    for rec in usable:
        eq = level_is_a_strike((rec["features"] or {}).get("invalidation_level"),
                               strikes_of(rec["t"])) if rec["_e1_basis"] == "text_level" else None
        rec["_e1_eq_strike"] = eq
        strikes_split[{True: "level == a strike", False: "level != any strike",
                       None: "no level (breakeven basis)"}[eq]] += 1
    sub("THE BINDING `level == a strike` SPLIT (registration §Known confounds)")
    print("""  The invalidation level often IS the short strike; where it is, E1 partly
  re-tests Attempt 9 rather than the model's judgement. The split is
  pre-declared and BINDING: the result must be carried by the SECOND cell
  (`level != any strike`). A CANDIDATE living only in the first cell is an
  Attempt-9 restatement, not a text finding.
  Tolerance, fixed in the module before the run: within """
          f"{STRIKE_TOL_REL:.1%} of a leg strike (floor ${STRIKE_TOL_ABS:.2f}).")
    for k, v in sorted(strikes_split.items()):
        print(f"  {k:<32} {v:>5}")

    # --- per-buffer outcomes ---
    cells: dict = defaultdict(lambda: dict(paired=[], affected_dates=set(), n_aff_rows=0))
    per_buffer_delta: dict = defaultdict(dict)
    fired = Counter()
    giveback: dict = defaultdict(list)
    for buf in BUFFERS:
        for rec in usable:
            levels, _basis, reason = stop_levels(rec, buf)
            if reason:                       # cannot happen: usable was screened at 0%
                continue
            bars = bars_by_ticker.get(rec["ticker"], {})
            sess, _why = stop_session(rec["t"], levels, bars)
            out = e1_outcome(rec, sess)
            aff = changed(out, rec["_shipped"])
            fired[(buf, sess is not None)] += 1
            if aff:
                pm = post_exit_max(rec["t"], out["days_held"])
                if pm is not None:
                    giveback[buf].append(pm - out["pnl_pct"])
            bar_src = None
            if bars:
                b = bars.get(rec["t"].grid[max(0, out["days_held"] - 1)])
                bar_src = b.source if b is not None else rec.get("_e1_bar_source")
            row = dict(date=rec["date"], a=out["pnl_pct"], b=rec["_shipped"]["pnl_pct"],
                       source=rec["source"], bar_source=bar_src)
            split = {True: "eq_strike", False: "ne_strike",
                     None: "breakeven"}[rec["_e1_eq_strike"]]
            for key in cell_keys(rec, (f"buf{buf:.0%}", split)):
                c = cells[key]
                c["paired"].append(row)
                if aff:
                    c["affected_dates"].add(rec["date"])
                    c["n_aff_rows"] += 1
            csv_rows.append(dict(
                arm="E1", grid=f"buffer={buf:.2f}", date=rec["date"],
                ticker=rec["ticker"], structure=rec["structure"],
                mech_cell=rec["mech_cell"], source=rec["source"], credit=rec["credit"],
                horizon=rec["horizon"], level_basis=rec["_e1_basis"],
                level=(rec["features"] or {}).get("invalidation_level"),
                eq_strike=rec["_e1_eq_strike"], bar_source=bar_src,
                stop_session=sess if sess is not None else "",
                shipped_reason=rec["_shipped"]["exit_reason"],
                shipped_days=rec["_shipped"]["days_held"],
                shipped_R=round(rec["_shipped"]["pnl_pct"], 6),
                variant_reason=out["exit_reason"], variant_days=out["days_held"],
                variant_R=round(out["pnl_pct"], 6), affected=aff))

    sub("FIRE RATES AND MFE GIVE-BACK per buffer (give-back is DESCRIPTIVE)")
    print(f"  {'buffer':<10}{'rows':>7}{'stop fired':>12}{'share':>9}"
          f"{'mean give-back':>16}{'n':>6}")
    for buf in BUFFERS:
        n_all = fired[(buf, True)] + fired[(buf, False)]
        gb = giveback[buf]
        gbm = f"{statistics.fmean(gb):+.3f}" if gb else "n/a"
        print(f"  {buf:<10.0%}{n_all:>7}{fired[(buf, True)]:>12}"
              f"{(fired[(buf, True)] / n_all if n_all else 0):>9.1%}{gbm:>16}{len(gb):>6}")
    print("""  Give-back = the post-exit path maximum over the rest of the row's own grid
  minus the R the variant realized, over AFFECTED rows only. Descriptive: a
  positive mean says the variant sold into a path that kept going.""")

    # --- criterion 7: no perturbation flip across the buffer grid ---
    for key, c in cells.items():
        fam, val, buf, split = key
        d = statistics.fmean(p["a"] - p["b"] for p in c["paired"]) if c["paired"] else 0.0
        per_buffer_delta[(fam, val, split)][buf] = d
    c7: dict = {}
    for key in cells:
        fam, val, buf, split = key
        signs = {b: (1 if v > 0 else (-1 if v < 0 else 0))
                 for b, v in per_buffer_delta[(fam, val, split)].items()}
        here = signs.get(buf, 0)
        # A flip is an ADJACENT grid value of the opposite sign. A zero is not a
        # flip — it is a cell the buffer switched off, which the census shows.
        c7[key] = not any(s != 0 and here != 0 and s != here for s in signs.values())
    sub("CRITERION 7 — no perturbation flip across the frozen buffer grid")
    print("""  A cell positive at one buffer and sign-flipped at an adjacent one in
  {0%, 1%, 2%} is a knob artifact and FAILS, whatever its CI says. The
  population is identical across the three buffers (only the threshold moves),
  so the signs are directly comparable.""")
    flips = sorted({(fam, val, split) for (fam, val, split), sg in per_buffer_delta.items()
                    if len({1 if v > 0 else (-1 if v < 0 else 0) for v in sg.values()}
                           - {0}) > 1})
    print(f"  cells with a sign flip across the grid: {len(flips)}")
    for fam, val, split in flips[:15]:
        bits = "  ".join(f"{b} {v:+.3f}" for b, v in
                         sorted(per_buffer_delta[(fam, val, split)].items()))
        print(f"    {fam} {val} [{split}]: {bits}")

    return census_and_evaluate(dict(cells), c7, "no_buffer_flip",
                               "E1 — CELL RESULTS (every cell, regardless of outcome)")


# =============================================================================
# ARM E2
# =============================================================================

def run_e2(recs: list[dict], bars_by_ticker: dict, csv_rows: list) -> dict:
    hdr("E2 — TRIGGER-AS-ENTRY-FILTER  (a SELECTION effect, quoted as one)")
    print("""  Rule (registration §E2): the entry counts only if the trigger's price level
  was met within N in {1, 3} sessions of the signal date on the OHLC cache;
  rows not met are NOT ENTERED. Only PRICE-LEVEL triggers are testable — in
  scope only where the trigger parses to a numeric price level WITH a
  direction.

  THIS IS A SELECTION EFFECT AND IS QUOTED AS ONE. The estimand is mean R on
  the ENTERED subset versus the full population, with the excluded share (rows
  and dates) printed beside every number. NO E2 RESULT MAY BE DESCRIBED AS AN
  EXIT IMPROVEMENT, and E2 can never ship as an exit rule — if it clears, it is
  an INTAKE proposal and is labelled one. No trigger arm changes an exit rule;
  PROD exits run untouched on the entered set.""")

    buckets: Counter = Counter()
    scoped: list[dict] = []
    for rec in recs:
        trig_text = (rec["text"] or {}).get("trigger") or ""
        level = (rec["features"] or {}).get("trigger_level")
        if not trig_text.strip():
            buckets["no_trigger_text"] += 1
            continue
        if level is None:
            buckets["conditional_unparseable: no level"] += 1
            continue
        direction = trigger_direction(trig_text, level)
        if direction is None:
            buckets["conditional_unparseable: no direction"] += 1
            continue
        bars = bars_by_ticker.get(rec["ticker"], {})
        if not bars:
            buckets["no_bars"] += 1
            continue
        ed = U.entry_day(rec["t"], sessions=set(bars))
        if ed is None:
            buckets["no_entry_session"] += 1
            continue
        rec["_e2"] = dict(level=level, direction=direction, entry_day=ed, bars=bars)
        scoped.append(rec)
    buckets["in scope (level + direction)"] = len(scoped)

    sub("TRIGGER PARSE CENSUS — the second PROMPT-ROBUSTNESS finding")
    total = len(recs)
    for k, v in sorted(buckets.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<36} {v:>5}  ({v / total:.1%} of {total} calibrated rows)")
    n_cond = sum(1 for r in recs if (r["features"] or {}).get("trigger_conditional"))
    print(f"  rows whose trigger is CONDITIONAL by `text_corpus.trigger_conditional`: "
          f"{n_cond} ({n_cond / total:.1%})")
    print("""  Conditional-but-unparseable triggers are their own bucket, reported with
  their n, never folded into either side of the comparison.""")

    verdicts: dict = {}
    cells_by_n: dict = {}
    for n in TRIGGER_N:
        sub(f"N = {n} session(s) after the signal date")
        entered, not_entered = [], []
        for rec in scoped:
            e2 = rec["_e2"]
            met = trigger_met(e2["bars"], e2["entry_day"], e2["level"],
                              e2["direction"], n)
            rec[f"_e2_met_{n}"] = met
            (entered if met else not_entered).append(rec)
            csv_rows.append(dict(
                arm="E2", grid=f"N={n}", date=rec["date"], ticker=rec["ticker"],
                structure=rec["structure"], mech_cell=rec["mech_cell"],
                source=rec["source"], credit=rec["credit"], horizon=rec["horizon"],
                level_basis="trigger", level=e2["level"], eq_strike="",
                bar_source=next(iter({b.source for b in e2["bars"].values()}), None),
                stop_session="", shipped_reason=rec["_shipped"]["exit_reason"],
                shipped_days=rec["_shipped"]["days_held"],
                shipped_R=round(rec["_shipped"]["pnl_pct"], 6),
                variant_reason="entered" if met else "not_entered",
                variant_days=rec["_shipped"]["days_held"],
                variant_R=round(rec["_shipped"]["pnl_pct"], 6), affected=not met))

        def _meanR(rows):
            vals = [r["_shipped"]["pnl_pct"] for r in rows]
            return statistics.fmean(vals) if vals else float("nan")

        all_dates = {r["date"] for r in scoped}
        ent_dates = {r["date"] for r in entered}
        print(f"  in scope {len(scoped)} rows / {len(all_dates)} dates")
        print(f"  ENTERED      {len(entered):>5} rows / {len(ent_dates):>3} dates   "
              f"mean R {_meanR(entered):+.3f}")
        print(f"  NOT ENTERED  {len(not_entered):>5} rows / "
              f"{len({r['date'] for r in not_entered}):>3} dates   "
              f"mean R {_meanR(not_entered):+.3f}")
        print(f"  EXCLUDED SHARE: {len(not_entered) / len(scoped):.1%} of rows, "
              f"{1 - len(ent_dates) / len(all_dates):.1%} of dates "
              f"(the full in-scope population's mean R is {_meanR(scoped):+.3f})")
        print("  Selection effect, on R. Not an exit result.")

        # Date-level paired comparison: the entered book's date mean against the
        # full population's date mean, on the dates both exist. Rows inside a
        # date share the tape, and E2 changes WHICH rows a date contributes, so
        # the date is the only unit on which the two books are comparable.
        cells: dict = defaultdict(lambda: dict(paired=[], affected_dates=set(),
                                               n_aff_rows=0))
        for fam, valfn in (("ALL", lambda r: "ALL"), ("STRUCT", lambda r: r["structure"]),
                           ("MECH", lambda r: r["mech_cell"]),
                           ("CROSS", lambda r: f"{r['structure']}|{r['mech_cell']}")):
            groups: dict = defaultdict(list)
            for r in scoped:
                groups[valfn(r)].append(r)
            for val, rows in groups.items():
                by_date: dict = defaultdict(list)
                for r in rows:
                    by_date[r["date"]].append(r)
                key = (fam, val, f"N={n}")
                for d, rs in by_date.items():
                    ent = [r for r in rs if r[f"_e2_met_{n}"]]
                    if not ent:
                        continue          # a date with no entry contributes nothing
                    a = statistics.fmean(r["_shipped"]["pnl_pct"] for r in ent)
                    b = statistics.fmean(r["_shipped"]["pnl_pct"] for r in rs)
                    cells[key]["paired"].append(
                        dict(date=d, a=a, b=b, source=rs[0]["source"], bar_source=None))
                    if len(ent) != len(rs):
                        cells[key]["affected_dates"].add(d)
                        cells[key]["n_aff_rows"] += len(rs) - len(ent)
        cells_by_n[n] = dict(cells)

    # Criterion 7 for E2 is the N grid, the direct analogue of E1's buffer grid:
    # a cell positive at one N and sign-flipped at the other is a knob artifact.
    # (E3's analogue is the survival control; the registration names all three.)
    sub("CRITERION 7 — no perturbation flip across the frozen N grid {1, 3}")
    signs: dict = defaultdict(dict)
    for n, cells in cells_by_n.items():
        for key, c in cells.items():
            base = (key[0], key[1])
            d = statistics.fmean(p["a"] - p["b"] for p in c["paired"]) if c["paired"] else 0.0
            signs[base][n] = d
    flips = [b for b, sg in signs.items()
             if len({1 if v > 0 else (-1 if v < 0 else 0) for v in sg.values()} - {0}) > 1]
    print(f"  cells with a sign flip across N in {list(TRIGGER_N)}: {len(flips)}")
    for base in sorted(flips)[:15]:
        bits = "  ".join(f"N={n} {v:+.3f}" for n, v in sorted(signs[base].items()))
        print(f"    {base[0]} {base[1]}: {bits}")

    for n, cells in cells_by_n.items():
        c7 = {}
        for key in cells:
            base = (key[0], key[1])
            here = signs[base].get(n, 0.0)
            c7[key] = not any(
                v != 0 and here != 0 and (v > 0) != (here > 0)
                for v in signs[base].values())
        verdicts.update(census_and_evaluate(
            dict(cells), c7, "no_N_flip",
            f"E2 — CELL RESULTS, N={n} (SELECTION, never an exit claim; the "
            f"paired unit is a DATE, so `pop` counts DATES)"))
    return verdicts


# =============================================================================
# ARM E3
# =============================================================================

def run_e3(recs: list[dict], csv_rows: list) -> dict:
    hdr("E3 — HORIZON-AS-TIME-EXIT")
    print("""  Rule (registration §E3): replace PROD's `time_exit_dte_fraction 0.75` with
  the emitted `horizon` bucket, mapped ONCE and frozen; everything else is the
  shipped profile. v4 writes `horizon` NUMERIC (14 / 60 / 180 / 720 DTE), so
  the arm keys off that number directly.

  BUILD-TIME DEVIATION 1 (module docstring): the mapping is to a CALENDAR-day
  count, not a session count. The frozen harness compares
  `(day - signal_date).days >= int(dte_entry * tef)`, so a session mapping is
  unreachable without forking the engine. `horizon_tef` inverts that expression
  exactly, leaving `lib/harness.py` untouched.""")

    pop, no_h = [], Counter()
    for rec in recs:
        h = horizon_of(rec)
        if h is None:
            no_h[str(rec.get("horizon") or "(blank)")] += 1
            continue
        rec["_h"] = h
        rec["_e3"] = e3_outcome(rec, h)
        pop.append(rec)
    sub("HORIZON CENSUS")
    print(f"  rows with a horizon in the frozen bucket vocabulary: {len(pop)} "
          f"of {len(recs)}")
    if no_h:
        print(f"  rows with no usable horizon (own bucket, counted): {dict(no_h)}")
    print(f"  horizon distribution: "
          f"{dict(Counter(r['_h'] for r in pop))}")

    # ── the SURVIVAL CONTROL, run BEFORE any monotone claim ──
    sub("SURVIVAL CONTROL — RUN FIRST (registration §E3, the 2026-08-19 ARM X lesson)")
    print("""  `horizon` is mechanically coupled to hold length: a long-horizon play is
  only OBSERVED holding long. A monotone table whose bucketing variable is
  coupled to hold length is a COMPOSITION read until proven otherwise. The
  control, fixed in the registration: (i) recompute the horizon table WITHIN
  `days_held` terciles, boundaries computed on the arm population and
  disclosed; (ii) print the full horizon x hold-length census. Non-monotone
  within the control, or FLAT inside every hold-length tercile, means
  SURVIVAL-ARTIFACT and no follow-up is queued.""")
    holds = [r["_shipped"]["days_held"] for r in pop]
    t1, t2 = terciles(holds)
    print(f"\n  days_held terciles on the arm population (n={len(holds)}): "
          f"T1 <= {t1:.0f} < T2 <= {t2:.0f} < T3")

    def tercile_of(r):
        return tercile_label(r["_shipped"]["days_held"], t1, t2)

    print("\n  horizon x hold-length CENSUS (rows)")
    print(f"  {'horizon':>8}" + "".join(f"{t:>8}" for t in ("T1", "T2", "T3")) + f"{'all':>8}")
    for h in HORIZON_BUCKETS:
        rs = [r for r in pop if r["_h"] == h]
        cells = [sum(1 for r in rs if tercile_of(r) == t) for t in ("T1", "T2", "T3")]
        print(f"  {h:>8}" + "".join(f"{c:>8}" for c in cells) + f"{len(rs):>8}")

    def mean_delta(rows):
        vals = [r["_e3"]["pnl_pct"] - r["_shipped"]["pnl_pct"] for r in rows]
        return statistics.fmean(vals) if vals else None

    def monotone(seq):
        """True / False / None — None when the row has fewer than two populated
        buckets and monotonicity is simply not evaluable there. A tercile with
        one bucket is not evidence of a broken table."""
        vals = [v for v in seq if v is not None]
        if len(vals) < 2:
            return None
        return (all(b >= a for a, b in zip(vals, vals[1:]))
                or all(b <= a for a, b in zip(vals, vals[1:])))

    raw = [mean_delta([r for r in pop if r["_h"] == h]) for h in HORIZON_BUCKETS]
    print("\n  RAW horizon table — mean DeltaR (variant - shipped) by horizon")
    print("  " + "  ".join(f"{h}: " + ("n/a" if v is None else f"{v:+.3f}")
                           for h, v in zip(HORIZON_BUCKETS, raw)))
    raw_mono = monotone(raw)
    print(f"  raw table monotone in horizon: {raw_mono}")

    within = {}
    print("\n  WITHIN-TERCILE horizon tables — mean DeltaR")
    for terc in ("T1", "T2", "T3"):
        vals = [mean_delta([r for r in pop if r["_h"] == h and tercile_of(r) == terc])
                for h in HORIZON_BUCKETS]
        within[terc] = vals
        flat = all(v is None or abs(v) < 1e-12 for v in vals)
        print(f"  {terc}: " + "  ".join(
            f"{h}: " + ("n/a" if v is None else f"{v:+.3f}")
            for h, v in zip(HORIZON_BUCKETS, vals))
            + f"   monotone={monotone(vals)}  flat={flat}")
    all_flat = all(all(v is None or abs(v) < 1e-12 for v in vals)
                   for vals in within.values())
    any_nonmono = any(monotone(vals) is False for vals in within.values())
    # The registration's words, applied literally: "Non-monotone within the
    # control, or flat inside every hold-length tercile -> SURVIVAL-ARTIFACT."
    survival_ok = not (all_flat or any_nonmono)
    print(f"\n  SURVIVAL CONTROL: {'PASS' if survival_ok else 'FAIL'}"
          f"   (raw table monotone={raw_mono}, non-monotone in >=1 tercile="
          f"{any_nonmono}, flat in every tercile={all_flat})")
    print("""  A cell that does not survive this control FAILS criterion 7 regardless of
  its DeltaR — that is E3's registered analogue of E1's perturbation-flip
  check. The SURVIVAL-ARTIFACT verdict is narrower and is reserved for the case
  the registration names: a MONOTONE raw table that dies under the control. A
  raw table that was never monotone has no monotone claim to kill, so its cells
  keep their ordinary verdicts with criterion 7 failed.""")
    if raw_mono and not survival_ok:
        print("""  RAW TABLE MONOTONE AND DEAD UNDER THE CONTROL -> SURVIVAL-ARTIFACT. Per the
  2026-08-19 precedent, no follow-up is queued and no monotone claim may be
  written from this run.""")

    cells: dict = defaultdict(lambda: dict(paired=[], affected_dates=set(), n_aff_rows=0))
    for rec in pop:
        out = rec["_e3"]
        aff = changed(out, rec["_shipped"])
        row = dict(date=rec["date"], a=out["pnl_pct"], b=rec["_shipped"]["pnl_pct"],
                   source=rec["source"], bar_source=None)
        for key in cell_keys(rec, (f"h{rec['_h']}",)):
            c = cells[key]
            c["paired"].append(row)
            if aff:
                c["affected_dates"].add(rec["date"])
                c["n_aff_rows"] += 1
        csv_rows.append(dict(
            arm="E3", grid=f"horizon={rec['_h']}", date=rec["date"],
            ticker=rec["ticker"], structure=rec["structure"],
            mech_cell=rec["mech_cell"], source=rec["source"], credit=rec["credit"],
            horizon=rec["horizon"], level_basis="horizon", level=rec["_h"],
            eq_strike="", bar_source="", stop_session="",
            shipped_reason=rec["_shipped"]["exit_reason"],
            shipped_days=rec["_shipped"]["days_held"],
            shipped_R=round(rec["_shipped"]["pnl_pct"], 6),
            variant_reason=out["exit_reason"], variant_days=out["days_held"],
            variant_R=round(out["pnl_pct"], 6), affected=aff))

    c7 = {key: survival_ok for key in cells}
    verdicts = census_and_evaluate(dict(cells), c7, "survival_control",
                                   "E3 — CELL RESULTS (every cell, regardless of outcome)")
    if raw_mono and not survival_ok:
        verdicts = {k: ("UNDERPOWERED" if v == "UNDERPOWERED" else "SURVIVAL-ARTIFACT")
                    for k, v in verdicts.items()}
    return verdicts


# =============================================================================

CSV_FIELDS = ("arm", "grid", "date", "ticker", "structure", "mech_cell", "source",
              "credit", "horizon", "level_basis", "level", "eq_strike", "bar_source",
              "stop_session", "shipped_reason", "shipped_days", "shipped_R",
              "variant_reason", "variant_days", "variant_R", "affected")


def calibration_gate(rows: list[dict]) -> tuple[list[dict], Counter]:
    """Replay every row under the profile PRODUCTION would have run, and classify.

    The same classifier `exit_mechanism_study.calibrate` and `book.py`'s
    `debit_calib` use — `lib/replay_basis.classify` — so there is no second
    definition of "does this row reproduce". Rows that reproduce (exact / near /
    boundary_tie) enter the variant arms; `superseded` (the stored outcome came
    from an exit rule this profile does not contain) and `hard` (a genuine
    disagreement) are EXCLUDED and counted.

    Excluding rather than failing: this study composes AROUND the replay, so a
    row whose baseline does not reproduce would contribute a variant delta
    measured against a baseline production never ran. The run continues on the
    rows that do reproduce, and the census says how many did not.
    """
    tally: Counter = Counter()
    kept = []
    for rec in rows:
        prof = dict(CREDIT_PROD) if rec["credit"] else prod_profile_for(rec, 0.50, True)
        kind, want, got = classify(rec["t"], prof, unreachable_reasons(prof))
        tally[kind] += 1
        tally[("credit" if rec["credit"] else "debit", kind)] += 1
        if kind in ("exact", "near", "boundary_tie"):
            rec["_profile"] = prof
            rec["_shipped"] = replay(rec["t"], **prof)
            kept.append(rec)
        else:
            rec["_calib_reject"] = (kind, want, got)
    return kept, tally


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--era", default=None,
                    help="era to run (default: STUDY_ERA, else `current`). The "
                         "runner sets STUDY_ERA for the whole suite; this flag "
                         "is the per-study equivalent and is printed in the header.")
    ap.add_argument("--arms", default="123",
                    help="subset of 1/2/3 (E1/E2/E3). The registration freezes "
                         "the arms at three and adds no fourth.")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="DEV/BUILD SMOKE ONLY: cap the book at N rows. A capped "
                         "run carries NO conclusion and says so in its header.")
    a = ap.parse_args(argv)

    rows, unpriced, diag = load_corpus(era=a.era, include_bs=False)
    era = diag["era"]
    hdr(f"exit_from_text — ERA {era}"
        f"   (pre-registration research/pre-registrations/f2_management/exit_from_text.md)")
    print(f"book: {len(rows)} rows  era={era}  counts_by_source={diag['counts_by_source']}"
          f"  date_range={diag['date_range']}  n_dates={diag['n_dates']}  (bs excluded)")
    print(f"debit_calib: {diag['debit_calib']}")
    print(f"n_credit_ungated: {diag['n_credit_ungated']}  — CAVEAT: credit rows are "
          f"admitted WITHOUT the exact-replay\n  calibration gate in `load_book` (there is "
          f"no single credit PROD that calibrates the\n  accumulated sheet: Attempt 13 "
          f"removed the credit stop mid-book). This study runs its\n  OWN gate below, "
          f"under CREDIT_PROD, and drops credit rows that do not reproduce —\n  but treat "
          f"every credit-side number as unvalidated until the book is split per\n  "
          f"credit-stop era.")
    print(f"text join: {diag['n_joined']} joined / {diag['n_unjoined']} unjoined  "
          f"(an unjoined row has NO trigger/invalidation text — blank means "
          f"'column absent', not 'the model said nothing')")
    n_unpriced = sum(diag["unpriced_by_reason"].values())
    print(f"unpriced analysis rows by reason: {dict(diag['unpriced_by_reason'])}")
    print(f"PRICEABILITY: {len(rows)} priced / {len(rows) + n_unpriced} analysis rows "
          f"= {len(rows) / (len(rows) + n_unpriced):.1%}  — every arm that follows is "
          f"CONDITIONED ON THIS.\n  An exit rule replays only on a row that priced, so "
          f"every cell's population is a\n  priceable subset of what the prompt actually "
          f"emitted; the unpriced remainder is\n  not evidence for or against any arm.")
    print(f"feature coverage: "
          f"invalidation_level={diag['feature_coverage']['invalidation_level']:.1%}  "
          f"trigger_level={diag['feature_coverage']['trigger_level']:.1%}")
    if era == "v4":
        print("""
  THE v4 2026 NO-OP, declared in the registration: the v4 results export carries
  ZERO 2026 signal dates, so `ex_2026_feb_apr` == ALL and ex_BOTH ==
  ex_2025_mar_apr, and "positive in every calendar year" reduces to 2024 ^ 2025.
  Every cut prints its n beside ALL's so a reader sees a no-op, not a passed
  test.""")

    if a.max_rows is not None:
        rows = rows[:a.max_rows]
        print(f"\n  *** SMOKE RUN: book capped at {len(rows)} rows by --max-rows. "
              f"This is a BUILD\n      CHECK ONLY — no number below is a finding and "
              f"nothing here may be quoted. ***")

    hdr("CALIBRATION GATE — the baseline must reproduce before any variant is read")
    print("""  Every row is replayed under the profile PRODUCTION would actually have run
  on it — the shipped debit merge (base -> structure_exit -> regime_exit, via
  `bear_giveback.prod_profile_for`) for debits, `CREDIT_PROD` for credits —
  and classified by `lib/replay_basis.classify`, the same classifier
  `exit_mechanism_study.calibrate` and `book.py`'s `debit_calib` use.

  Only rows that REPRODUCE (exact / near-rounding-tie / boundary-tie) enter the
  variant arms. `superseded` and `hard` rows are excluded and counted: a
  variant delta measured against a baseline production never ran is a finding
  about the replay, not about the text.""")
    recs, tally = calibration_gate(rows)
    print(f"\n  {tally['exact']} exact, {tally['near']} near-rounding-tie, "
          f"{tally['superseded']} superseded-basis, {tally['boundary_tie']} boundary-tie, "
          f"{tally['hard']} HARD  of {len(rows)}")
    for side in ("debit", "credit"):
        bits = "  ".join(f"{k}={tally[(side, k)]}" for k in
                         ("exact", "near", "superseded", "boundary_tie", "hard"))
        print(f"  {side:<7} {bits}")
    print(f"  ADMITTED to the variant arms: {len(recs)} rows / "
          f"{len({r['date'] for r in recs})} dates "
          f"({len(recs) / len(rows):.1%} of the book)")
    rejected = [r for r in rows if "_calib_reject" in r]
    if rejected:
        print(f"  excluded: {len(rejected)} rows. First 15:")
        for r in rejected[:15]:
            kind, want, got = r["_calib_reject"]
            print(f"    {kind:<11} {r['date']} {r['ticker']:<6} {r['structure']:<18} "
                  f"stored={want} replay={got}")
    if not recs:
        print("  CALIBRATION GATE: no row reproduces — nothing below can be read.")
        return EXIT_GATE_FAILURE

    print(f"\n  shipped exit mix on the admitted rows: "
          f"{dict(Counter(r['_shipped']['exit_reason'] for r in recs))}")

    bars_by_ticker = {tk: U.load_bars(tk) for tk in sorted({r["ticker"] for r in recs})}
    src = Counter()
    for tk, bars in bars_by_ticker.items():
        src[next(iter({b.source for b in bars.values()}), "none") if bars else "none"] += 1
    print(f"  underlying bar coverage by ticker: {dict(src)}  "
          f"(SRC_OHLC='{U.SRC_OHLC}', SRC_TILDE='{U.SRC_TILDE}')")
    print("""  A tilde close is a different measurement from a real bar — it is the
  underlying quote stamped on an option row at the option's EOD snapshot — so
  the split is PRINTED beside every bar-using cell and never pooled silently.""")

    csv_rows: list[dict] = []
    verdicts: dict = {}
    if "1" in a.arms:
        verdicts.update({("E1",) + k: v
                         for k, v in run_e1(recs, bars_by_ticker, csv_rows).items()})
    if "2" in a.arms:
        verdicts.update({("E2",) + k: v
                         for k, v in run_e2(recs, bars_by_ticker, csv_rows).items()})
    if "3" in a.arms:
        verdicts.update({("E3",) + k: v for k, v in run_e3(recs, csv_rows).items()})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / f"exit_from_text-{era}-rows.csv"
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in csv_rows:
            w.writerow(r)

    hdr("VERDICT SUMMARY — every cell, every arm, regardless of outcome")
    print(f"  {'arm':<4}{'family':<7}{'cell':<38}{'grid':<18}verdict")
    for key in sorted(verdicts, key=lambda k: (k[0], k[1], str(k[2]), str(k[3:]))):
        arm, fam, val = key[0], key[1], key[2]
        grid = "/".join(str(x) for x in key[3:])
        print(f"  {arm:<4}{fam:<7}{str(val)[:37]:<38}{grid:<18}{verdicts[key]}")
    tally_v = Counter(v.split(":")[0] for v in verdicts.values())
    print(f"\n  tally: {dict(tally_v)}")
    print(f"""
  Verdict grammar (registration §Verdict grammar):
    UNDERPOWERED  a floor was not met; census published, nothing read.
    NULL          powered, conjunction not cleared; recorded.
    CANDIDATE     the whole conjunction clears. NOT a ship — it becomes a
                  written proposal with its own rollback trigger and an
                  independent-window confirmation first.
    CONTRARY      powered, CI excludes zero, sign OPPOSITE the arm's
                  hypothesis: the emitted invalidation/horizon is actively
                  MISLEADING. A real finding, fed to the PROMPT-ROBUSTNESS list.
    SURVIVAL-ARTIFACT (E3 only)  monotone raw table that dies under the control.
    NO PRE-REGISTERED VERDICT MATCHES  the catch-all, resolved by hand in
                  research/current.md.

  E2 can never ship as an exit rule; if it clears it is an INTAKE proposal and
  is labelled one. Every ALL row above is the POOLED headline and is NOT A
  CRITERION.

  No annualised figure, Sharpe, or time-to-recover is printed anywhere above,
  by design. R is the unit of every conclusion; PF never appears without mean R
  beside it.

  per-row variant outcomes: {out_csv}  ({len(csv_rows)} rows)""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
