"""Time-staged exit: by session X, if the position is +/-Y against ENTRY, act; else continue shipped.

PRE-REGISTERED 2026-08-19 in `research/pre-registrations/staged_exit.md`, BEFORE
this file was written. That document is BINDING; nothing here may drift from it.
Read it first. In brief:

  THE OVERLAP, NAMED FIRST. This repo has already tested drawdown-from-peak
  trailing exits three times (Attempts 1, 2, 10) and they failed three times: a
  trail is REACTIVE — it re-arms on every new peak, fires on noise, and all 21
  debit trail exits sold continuations. A time-staged switch is a different
  object: it evaluates ONCE, at a fixed session X, on P&L measured against the
  ORIGINAL entry, and it CANNOT re-fire. That single-evaluation, entry-anchored
  property is the entire distinction and the only reason this study is
  admissible after three failures.

  The corollary is registered as a failure mode rather than discovered later:
  any post-X action that tightens a stop or arms a trail REINTRODUCES the
  reactive mechanism on the tail. ARM T does exactly that, deliberately, as a
  transfer test — and is therefore guarded by G2, which is a PASS CRITERION and
  not a footnote.

  ARM E — terminal "exit now". Pure COMPOSITION around the FROZEN
      `harness.replay` (the `next_day_move` precedent): replay the shipped
      profile untouched, then, if `days_held > X` and the band condition holds
      at `pnl_of(marks[X-1])`, override the outcome to `(staged_exit, X, that
      pnl)`. No fork, no copy, no edit to `harness.py`. The headline is read
      from ARM E.

  ARM T — tighten / arm-trail. `harness.replay`'s loop body is COPIED into this
      module as `replay_staged(t, stage1, stage2, switch_day)` — the profile
      swaps at `i >= switch_day`, `peak` and the trail latch carry ACROSS the
      swap. `harness.py`'s own docstring mandates copy-not-edit; this is a copy
      and the harness is NOT modified. G-FORK gates it.

Gates, in the registered order: G0 power census (blocks every read) -> G1 leak
guard (zero rows changed outside the population) -> G-FORK (ARM T only: with
`stage1 == stage2` the fork must reproduce `harness.replay` EXACTLY on every
book row at every grid X) -> G2 continuation diagnostic AS A PASS CRITERION (a
cell whose staged exits are MAJORITY followed by a post-exit path max >
realized + 0.30 R FAILS regardless of DeltaR). Then the standard conjunction,
paired against the SHIPPED book — never against a clean `DEBIT_PROD`.

Grid is FROZEN by the registration: X in {5, 10, 15, 20}; conditions R >= +0.50,
R >= +0.25, R <= -0.25, R <= -0.50, with a parallel dollar cut at +/-$250 and
+/-$500; ARM T actions = tighten stop to -0.40 OR arm trail 0.50/0.50 (the
shipped BEAR_HE values, a TRANSFER test, not a new knob); else-branch always
"continue shipped profile". Nothing here is swept and no cell may be added
after a number is seen. Every cell is reported regardless of outcome.

Verdicts: CANDIDATE / REACTIVE-AGAIN / NULL / UNDERPOWERED. Nothing ships from
a research-tier study. Read-only; touches no config. Run:

    python -m scripts.backtest_study run staged_exit --era v3
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import (  # noqa: E402
    hdr, prod_profile_for, sub,
)
from scripts.backtest_study.lib.book import CREDIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import MAX_LOSS_ABS, Trade, replay  # noqa: E402

# The runner promotes `-latest.txt` on these codes instead of deleting it. It
# finds them by AST parse, so this MUST stay a PLAIN SET LITERAL — a
# `frozenset(...)` call is invisible to `ast.literal_eval` and the refusal would
# be misfiled as a failure. {2, 3} are `era.EXIT_THIN_ERA` / `EXIT_ERA_MISMATCH`,
# raised by `load_book` when the exports on disk are not the era asked for.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# --- FROZEN GRID (pre-registration §"Frozen grid"). May not move. ------------

SWITCH_SESSIONS = (5, 10, 15, 20)

# Each condition is (label, basis, side, threshold). `basis` "R" reads the mark
# P&L at session X directly; "$" reads `t.dollars(pnl)` — the parallel dollar
# cut, run over the SAME grid and reported alongside R. R is what every
# conclusion is quoted in; contracts are identical across arms (nothing is
# re-sized here), which is what makes the dollar cut admissible at all.
R_CONDITIONS = (
    ("R >= +0.50", "R", "profit", 0.50),
    ("R >= +0.25", "R", "profit", 0.25),
    ("R <= -0.25", "R", "loss", -0.25),
    ("R <= -0.50", "R", "loss", -0.50),
)
DOLLAR_CONDITIONS = (
    ("$ >= +250", "$", "profit", 250.0),
    ("$ >= +500", "$", "profit", 500.0),
    ("$ <= -250", "$", "loss", -250.0),
    ("$ <= -500", "$", "loss", -500.0),
)
CONDITIONS = R_CONDITIONS + DOLLAR_CONDITIONS

# ARM T actions: the SHIPPED BEAR_HE values, used unchanged. `trig` AND `trail`
# are both set on the trail action on purpose — a `trail` without a `trig` never
# arms and silently no-ops (the trap logged in Attempt 12 and pinned by
# tests/test_harness_replay.py::test_trail_without_a_trigger_is_a_no_op...).
ARM_T_ACTIONS = (
    ("tighten stop to -0.40", {"sl": 0.40}),
    ("arm trail 0.50/0.50", {"trig": 0.50, "trail": 0.50}),
)
ARM_E_ACTIONS = (("exit now", None),)

# --- Gate constants, all declared before any count was known -----------------

MIN_AFFECTED_DATES = 25      # G0 floor, and criterion 6
MIN_AFFECTED_ROWS = 60       # G0 floor, and criterion 6
MIN_CELL_N = 20              # descriptive cells thinner than this are NOT READ
CONTINUATION_MARGIN = 0.30   # G2: post-exit path max > realized + this = a continuation
CONTINUATION_MAJORITY = 0.50  # G2 fails a cell strictly above this share
BOOT_N = P.BOOT_N            # 10000, alpha = .05

EXIT_GATE_FAILURE = 1        # a real failure, NOT a designed refusal

# The two windows `protocol.window_cuts` drops ONE AT A TIME. Criterion 3 also
# requires the ex-BOTH cut, added by hand here: `window_cuts()` leaves a gap
# through which a result carried by the union of the two windows walks, and the
# vol_sleeve straddle died precisely in that gap.
_BOTH_WINDOW_MONTHS = {m for months in P.DOMINANT_WINDOWS.values() for m in months}


# --- conditions ---------------------------------------------------------------

def condition_holds(t: Trade, pnl: float, basis: str, side: str, thr: float) -> bool:
    """Does the band condition hold for a mark P&L of `pnl` on trade `t`?

    `pnl` is the ROUNDED (10dp) mark P&L against the ORIGINAL entry, the same
    clamp `harness.replay` applies — see its inline comment about the 4-decimal
    CSV round-trip. The dollar basis goes through `Trade.dollars`, which is
    `pnl * abs(entry_net) * 100 * contracts`, so it is signed the same way
    (positive = profit) for debits and credits alike.
    """
    value = t.dollars(pnl) if basis == "$" else pnl
    return value >= thr if side == "profit" else value <= thr


def cond_label(cond) -> str:
    return cond[0]


# --- the shipped book ---------------------------------------------------------

def shipped_profile(rec: dict) -> dict:
    """The exit profile PRODUCTION would actually have run on this row.

    Debits take the SHIPPED merge (base -> structure_exit -> regime_exit) via
    `bear_giveback.prod_profile_for(rec, 0.50, True)` — the same function whose
    calibration is already published, so there is no second source of truth for
    the production knobs. Credits take `CREDIT_PROD` and reach NEITHER overlay:
    `config/backtest.yml` states the structure_exit and regime_exit merges are
    debit-only. Routing a credit row through `prod_profile_for` would replay it
    under debit knobs.

    The registration is explicit that the paired baseline is THIS, never a clean
    `DEBIT_PROD`: comparing against a baseline production does not run has
    changed a decision twice in this repo's history.
    """
    if rec["credit"]:
        return dict(CREDIT_PROD)
    return prod_profile_for(rec, 0.50, True)


def mark_pnl_at(t: Trade, session: int):
    """Rounded mark P&L at 1-based grid session `session`, or None if unpriced.

    None is a real answer, not a zero: an unpriced day inside the path is
    skipped by `replay` without evaluating a rule, and a staged switch cannot
    read a band off a mark that does not exist. Such a row continues the shipped
    profile and is counted in the census as `no_mark_at_X`.
    """
    if session < 1 or session > len(t.marks):
        return None
    m = t.marks[session - 1]
    if m is None:
        return None
    return round(t.pnl_of(m), 10)


def post_exit_max(t: Trade, days_held: int):
    """Max rounded mark P&L over the row's own grid AFTER `days_held`, or None.

    G2's measurement: what the position went on to do once the staged switch
    had sold it. None when nothing priced remains (the exit was the last mark),
    in which case the row cannot be a continuation sale and is counted as such.
    """
    vals = [round(t.pnl_of(m), 10)
            for i, m in enumerate(t.marks, start=1)
            if i > days_held and m is not None]
    return max(vals) if vals else None


# =============================================================================
# ARM T's fork of the FROZEN replay engine — gated by G-FORK
# =============================================================================

def replay_staged(t: Trade, stage1: dict, stage2: dict, switch_day: int) -> dict:
    """`harness.replay`'s loop body, VERBATIM, with the profile swapped at X.

    THIS IS A DELIBERATE LOCAL COPY, not a shared helper and not a promotion to
    `lib/`. `harness.py`'s docstring says: "If the exit mechanism itself needs to
    change, that is a new study with its own calibration gate — copy this
    module, don't edit it in place." This is that copy, and G-FORK is that gate.

    Semantics of the swap, fixed by the pre-registration:
      * `stage1` governs sessions `i < switch_day`; `stage2` governs
        `i >= switch_day`. The action therefore applies FROM session X onward,
        including at X itself — the condition and the tightened rule read the
        SAME close, so acting on it is not lookahead.
      * `peak` and the `trailing_active` latch carry ACROSS the swap. That is
        the point of a staged trail: it arms off the peak the position already
        made, not off a peak restarted at X.
      * `te_day` and the underlying breach thresholds are per-profile and are
        precomputed for both stages; every clamp, comparison ORDER and rounding
        below is byte-identical to the frozen engine. Do not "tidy" any of it.

    Profiles are dicts; a missing key reads as None, exactly as `replay`'s
    keyword defaults do when a caller writes `replay(t, **profile)`.
    """
    def _prep(p: dict):
        tef = p.get("tef")
        und_buffer = p.get("und_buffer")
        te_day = int(t.dte_entry * tef) if tef else None
        ths = t.breach_thresholds(und_buffer) if und_buffer is not None else []
        return te_day, ths

    te1, ths1 = _prep(stage1)
    te2, ths2 = _prep(stage2)

    peak = -1e18
    trailing_active = False
    for i, (day, m) in enumerate(zip(t.grid, t.marks), start=1):
        if i >= switch_day:
            prof, te_day, ths = stage2, te2, ths2
        else:
            prof, te_day, ths = stage1, te1, ths1
        pt = prof.get("pt")
        sl = prof.get("sl")
        trig = prof.get("trig")
        trail = prof.get("trail")
        be_after = prof.get("be_after")

        if m is None:
            continue
        d = (day - t.signal_date).days
        # round away 1-ulp float noise from the 4-decimal CSV round-trip: e.g.
        # (0.3500-1.4)/1.4 = -0.7499999999999999, which misses the sl=0.75
        # boundary production hit when computing from the unrounded scrape.
        pl = round(t.pnl_of(m), 10)
        peak = max(peak, pl)
        if trig is not None and peak >= trig:
            trailing_active = True

        if pt is not None and pl >= pt:
            return dict(exit_reason="profit_target", days_held=i, pnl_pct=pl)
        if trailing_active and trail is not None and pl <= peak - trail:
            return dict(exit_reason="trailing_stop", days_held=i, pnl_pct=pl)
        if ths:
            s = t.underlying.get(day)
            if s is not None and any(
                    (dr == "above" and s > lvl) or (dr == "below" and s < lvl)
                    for dr, lvl in ths):
                return dict(exit_reason="underlying_stop", days_held=i, pnl_pct=pl)
        if t.dollars(pl) <= -MAX_LOSS_ABS:
            return dict(exit_reason="dollar_stop", days_held=i, pnl_pct=pl)
        if be_after is not None and peak >= be_after and pl <= 0:
            return dict(exit_reason="be_stop", days_held=i, pnl_pct=pl)
        if sl is not None and pl <= -sl:
            return dict(exit_reason="stop_loss", days_held=i, pnl_pct=pl)
        if te_day is not None and d >= te_day:
            return dict(exit_reason="time_exit", days_held=i, pnl_pct=pl)

    priced = [(i, m) for i, m in enumerate(t.marks, start=1) if m is not None]
    i, m = priced[-1]
    return dict(exit_reason="expired" if t.cap_reached_expiry else "cap_open",
                days_held=i, pnl_pct=t.pnl_of(m))


# =============================================================================
# The two arms
# =============================================================================

def staged_outcome(rec: dict, x: int, cond, action) -> dict:
    """The staged outcome for one row, or the SHIPPED result unchanged.

    The keying — "only rows whose shipped replay survives past session X" — is
    evaluated INSIDE this function, never by pre-filtering the caller's list.
    That is what makes G1 a real test: the leak guard hands this the whole book
    and asserts nothing outside the population moved. A pre-filtered rule could
    not touch a row it was never handed, which would make the guard vacuous
    (the `next_day_move` precedent, stated the same way there).

    `action is None` is ARM E (terminal exit-now, pure composition around the
    frozen `replay`); a dict is ARM T (the fork, with `stage2 = shipped |
    action`).
    """
    t = rec["t"]
    base = rec["_shipped"]
    if base["days_held"] <= x:
        return base                       # outside the population; untouched
    pnl_x = mark_pnl_at(t, x)
    if pnl_x is None:
        return base                       # no mark at X: nothing to read a band off
    _label, basis, side, thr = cond
    if not condition_holds(t, pnl_x, basis, side, thr):
        return base                       # else-branch: continue shipped profile
    if action is None:
        return dict(exit_reason="staged_exit", days_held=x, pnl_pct=pnl_x)
    profile = rec["_profile"]
    return replay_staged(t, profile, {**profile, **action}, x)


def cell_outcomes(recs: list[dict], x: int, cond, action) -> dict:
    """`{id(rec): staged_result}` over the WHOLE book (see `staged_outcome`)."""
    return {id(rec): staged_outcome(rec, x, cond, action) for rec in recs}


def changed(a: dict, b: dict) -> bool:
    """The registration's identity triple: exit_reason, days_held, round(pnl, 10)."""
    return (a["exit_reason"], a["days_held"], round(a["pnl_pct"], 10)) != \
           (b["exit_reason"], b["days_held"], round(b["pnl_pct"], 10))


# =============================================================================
# G-FORK — the fork must BE the frozen engine when nothing is staged
# =============================================================================

def g_fork(recs: list[dict]) -> int:
    """`replay_staged(t, p, p, X)` == `replay(t, **p)` on every row, every X.

    Registered BEFORE the copy existed: "A forked replay that has drifted from
    the frozen engine is not a finding about exits; it is a finding about the
    fork." One disagreement fails the run.

    Run over each row's OWN shipped profile — the profile that actually governs
    it — so the equivalence is checked on the knob combinations the study
    actually uses, not on one synthetic profile. `tests/test_staged_exit.py`
    carries the other half of the registration: the same equivalence
    parametrised over the whole `tests/test_harness_replay.py` fixture, which
    covers all nine exit reasons, both signs of entry, the priority cases and
    the rounding clamps.
    """
    hdr("G-FORK — the ARM T fork reproduces the FROZEN engine exactly (stage1 == stage2)")
    print("""  Checked on every book row at every grid X, against each row's OWN shipped
  profile. The identity is (exit_reason, days_held, round(pnl, 10)) — exact,
  never approximate: the rounding is part of what is being pinned.

  The fixture half of this gate (all nine exit reasons, both entry signs, the
  six priority cases, the three rounding cases) lives in
  tests/test_staged_exit.py and must pass before ARM T is trusted.""")
    bad = []
    for rec in recs:
        t, prof = rec["t"], rec["_profile"]
        want = replay(t, **prof)
        for x in SWITCH_SESSIONS:
            got = replay_staged(t, prof, prof, x)
            if changed(got, want):
                bad.append((rec["date"], rec["ticker"], x, want, got))
    print(f"\n  rows checked {len(recs)}  x  X in {list(SWITCH_SESSIONS)}  "
          f"= {len(recs) * len(SWITCH_SESSIONS)} comparisons")
    if bad:
        print(f"\n  *** G-FORK FAILED: {len(bad)} disagreement(s). ***")
        for d, tick, x, want, got in bad[:20]:
            print(f"    {d} {tick} X={x}: harness {want} vs fork {got}")
        print("  The fork has drifted from lib/harness.py. Nothing below may be read.")
        return EXIT_GATE_FAILURE
    print("  G-FORK: PASS — 0 disagreements.")
    return 0


# =============================================================================
# G0 — power census. Runs FIRST and blocks every read below it.
# =============================================================================

def survivor_census(recs: list[dict]) -> dict:
    """`{X: (rows, dates)}` — rows whose SHIPPED replay survives past session X.

    This is the paired population at that X. A row that already exited on or
    before X is untouched by every arm and is excluded from the paired test —
    including it is the zero-inflation that failed `exit_switch_mech`'s LOO
    median gate.
    """
    out = {}
    for x in SWITCH_SESSIONS:
        pop = [r for r in recs if r["_shipped"]["days_held"] > x]
        out[x] = (len(pop), len({r["date"] for r in pop}))
    return out


def g0(recs: list[dict], cells: dict) -> dict:
    """Print the census; return `{cell_key: powered}`."""
    hdr("G0 — POWER CENSUS (runs FIRST and blocks every read below)")
    print(f"""  Floor, declared in the registration before any count was known:
  a cell with < {MIN_AFFECTED_DATES} affected DATES or < {MIN_AFFECTED_ROWS} affected ROWS is UNDERPOWERED —
  printed with its n, no criterion evaluated on it, no re-run on these dates.

  ARM T counts below are produced by the fork validated at G-FORK above; a
  G-FORK failure exits non-zero and nothing here may be read.""")

    sub("population per X — rows whose SHIPPED replay survives past session X")
    surv = survivor_census(recs)
    print(f"  {'X':>3}  {'rows':>6}  {'dates':>6}   {'debit':>12}   {'credit':>12}"
          f"   {'no mark at X':>13}")
    for x in SWITCH_SESSIONS:
        n_rows, n_dates = surv[x]
        pop = [r for r in recs if r["_shipped"]["days_held"] > x]
        deb = [r for r in pop if not r["credit"]]
        cred = [r for r in pop if r["credit"]]
        nomark = sum(1 for r in pop if mark_pnl_at(r["t"], x) is None)
        print(f"  {x:>3}  {n_rows:>6}  {n_dates:>6}   "
              f"{len(deb):>5}/{len({r['date'] for r in deb}):<6}   "
              f"{len(cred):>5}/{len({r['date'] for r in cred}):<6}   {nomark:>13}")
    print("  (a row with no mark at X continues the shipped profile under every "
          "arm and\n   can never be an affected row — it is inside the "
          "population and inside the\n   paired test, contributing an exact zero.)")
    print("""  RECONCILING THE REGISTRATION'S DISCLOSED PLAN-TIME COUNTS. The
  pre-registration discloses "513 rows / 114 dates survive past session 5;
  415 / 110 past 10; 333 / 109 past 15; 265 / 102 past 20". Those figures
  reproduce EXACTLY on the DEBIT column above, not on the whole book — the
  plan-time measurement was taken on the debit slice. The registered
  POPULATION wording is the unrestricted one ("rows whose SHIPPED replay
  survives past session X", on `load_book(include_bs=False)`), and that is
  what this study runs: credit rows are in every population, priced under
  CREDIT_PROD. Both columns are printed so a reader can reconcile the two
  numbers instead of discovering the gap later. Nothing here narrows the
  population to make a disclosed figure come out right.""")

    sub("affected rows / dates per cell (arm x X x condition x action)")
    print(f"  {'arm':<4}{'X':>3}  {'condition':<12} {'action':<24} "
          f"{'aff rows':>9} {'aff dates':>10}  status")
    powered = {}
    for key, cell in cells.items():
        arm, x, cond, act_label = key
        n_rows = cell["n_affected_rows"]
        n_dates = cell["n_affected_dates"]
        ok = n_dates >= MIN_AFFECTED_DATES and n_rows >= MIN_AFFECTED_ROWS
        powered[key] = ok
        print(f"  {arm:<4}{x:>3}  {cond_label(cond):<12} {act_label:<24} "
              f"{n_rows:>9} {n_dates:>10}  {'powered' if ok else 'UNDERPOWERED'}")
    n_ok = sum(1 for v in powered.values() if v)
    print(f"\n  {n_ok} of {len(powered)} cells clear the floor; "
          f"{len(powered) - n_ok} are UNDERPOWERED.")
    return powered


# =============================================================================
# G1 — leak guard
# =============================================================================

def g1_leak(recs: list[dict], cells: dict) -> int:
    """Zero rows outside the population may move, in ANY cell.

    "Outside the population" = shipped `days_held <= X`. The whole book is fed
    to `staged_outcome` with the keying evaluated inside it, so a leak is
    genuinely reachable here and must not happen.
    """
    hdr("G1 — LEAK GUARD (a staged arm changes ZERO rows outside its population)")
    print("""  Every row whose SHIPPED replay exited on or before X must come back
  identical on (exit_reason, days_held, round(pnl, 10)). A single changed row
  means the switch is firing where it was never registered to, and fails the
  run. The whole book is handed to the rule with the keying evaluated INSIDE
  it — a pre-filtered list could not leak and would make this vacuous.""")
    leaks = []
    for key, cell in cells.items():
        arm, x, cond, act_label = key
        n_out = 0
        for rec in recs:
            if rec["_shipped"]["days_held"] > x:
                continue
            if changed(cell["out"][id(rec)], rec["_shipped"]):
                n_out += 1
        if n_out:
            leaks.append((key, n_out))
    print(f"\n  cells checked {len(cells)}   rows per cell {len(recs)}")
    if leaks:
        print(f"  *** G1 FAILED: {len(leaks)} cell(s) changed rows outside their "
              f"population. ***")
        for (arm, x, cond, act_label), n in leaks[:20]:
            print(f"    ARM {arm} X={x} {cond_label(cond)} / {act_label}: "
                  f"{n} rows outside the population changed")
        return EXIT_GATE_FAILURE
    print("  G1: PASS — 0 rows changed outside the population, in every cell.")
    return 0


# =============================================================================
# G2 + the full conjunction
# =============================================================================

def g2_continuation(cell: dict) -> dict:
    """The continuation diagnostic, as a PASS CRITERION.

    Over the rows the cell exits EARLIER than shipped, the share whose post-exit
    path max exceeds the realized exit P&L by more than `CONTINUATION_MARGIN`.
    A MAJORITY fails the cell regardless of DeltaR, CI, LOO or anything else —
    this is the measurement that separates a time-staged switch from Attempt 1,
    and it was registered as binding before any cell was computed.
    """
    early = [(rec, res) for rec, res in cell["early"]]
    n_cont = 0
    for rec, res in early:
        pm = post_exit_max(rec["t"], res["days_held"])
        if pm is not None and pm > res["pnl_pct"] + CONTINUATION_MARGIN:
            n_cont += 1
    n = len(early)
    share = (n_cont / n) if n else None
    # No early exits at all cannot be a continuation sale, and is not a pass by
    # merit either — such a cell is underpowered long before this is read.
    passed = True if share is None else share <= CONTINUATION_MAJORITY
    return dict(n_early=n, n_continuation=n_cont, share=share, passed=passed)


def evaluate_cell(cell: dict) -> dict:
    """The full conjunction for one powered cell. Returns every component."""
    paired = cell["paired"]
    out = {}
    out["mean_shipped"] = statistics.fmean(p["b"] for p in paired)
    out["mean_staged"] = statistics.fmean(p["a"] for p in paired)
    out["delta"] = out["mean_staged"] - out["mean_shipped"]

    lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=BOOT_N)
    out["ci"] = (lo, hi)
    _mean, _share, loo_min, n_folds = P.loo_by_date(
        paired, lambda p: p["a"], lambda p: p["b"])
    out["loo_min"], out["loo_folds"] = loo_min, n_folds

    cuts = P.window_cuts(paired)
    cuts["ex_BOTH"] = [p for p in paired
                       if str(p["date"])[:7] not in _BOTH_WINDOW_MONTHS]
    out["cuts"] = {name: (len(rows),
                          statistics.fmean(p["a"] - p["b"] for p in rows) if rows else None)
                   for name, rows in cuts.items()}

    years = P.by_year(paired)
    out["years"] = {y: (len(rs), statistics.fmean(p["a"] - p["b"] for p in rs))
                    for y, rs in years.items()}
    out["tiers"] = {}
    for tier in ("real", "tweak"):
        rs = [p for p in paired if p["source"] == tier]
        if rs:
            out["tiers"][tier] = (len(rs), statistics.fmean(p["a"] - p["b"] for p in rs))

    out["g2"] = g2_continuation(cell)

    # criteria 1-7, in the registration's order
    c1 = lo > 0
    c2 = loo_min > 0 if n_folds else False
    c3 = all(v is not None and v > 0 for _n, v in out["cuts"].values())
    c4 = bool(out["years"]) and all(v > 0 for _n, v in out["years"].values())
    c5 = bool(out["tiers"]) and all(v > 0 for _n, v in out["tiers"].values())
    c6 = (cell["n_affected_dates"] >= MIN_AFFECTED_DATES
          and cell["n_affected_rows"] >= MIN_AFFECTED_ROWS)
    c7 = out["g2"]["passed"]
    out["criteria"] = dict(c1_ci=c1, c2_loo=c2, c3_windows=c3, c4_years=c4,
                           c5_tiers=c5, c6_power=c6, c7_g2=c7)

    r_conjunction = c1 and c2 and c3 and c4 and c5 and c6
    if r_conjunction and c7:
        out["verdict"] = "CANDIDATE"
    elif r_conjunction:
        out["verdict"] = "REACTIVE-AGAIN"
    elif c1:
        out["verdict"] = "NULL"
    else:
        out["verdict"] = "-"
    return out


def worst_decile_note(paired: list[dict]) -> str:
    """DESCRIPTIVE ONLY, marked NOT A CRITERION.

    118 dates cannot power a worst-decile read (the 2026-08-13 nine-date decile
    wall). It is printed with its n because the operator asks for it, and no
    criterion above touches it.
    """
    by_date: dict[str, list[dict]] = {}
    for p in paired:
        by_date.setdefault(str(p["date"]), []).append(p)
    ranked = sorted(by_date.items(),
                    key=lambda kv: statistics.fmean(p["b"] for p in kv[1]))
    k = max(1, len(ranked) // 10)
    worst = [p for _d, rs in ranked[:k] for p in rs]
    g = statistics.fmean(p["a"] - p["b"] for p in worst)
    thin = "  <- n<%d" % MIN_CELL_N if len(worst) < MIN_CELL_N else ""
    return (f"worst decile of dates by shipped mean: {k} dates / {len(worst)} rows, "
            f"gain {g:+.3f}{thin}   NOT A CRITERION")


def print_cell(key, cell: dict, ev: dict) -> None:
    arm, x, cond, act_label = key
    sub(f"ARM {arm}  X={x}  {cond_label(cond)}  ->  {act_label}")
    print(f"  population {cell['n_pop_rows']} rows / {cell['n_pop_dates']} dates   "
          f"affected {cell['n_affected_rows']} rows / {cell['n_affected_dates']} dates")
    print(f"  shipped meanR {ev['mean_shipped']:>+7.3f}   "
          f"staged meanR {ev['mean_staged']:>+7.3f}   "
          f"DeltaR {ev['delta']:>+7.3f}")
    lo, hi = ev["ci"]
    print(f"  1 CI95 (date-clustered, n={BOOT_N}) [{lo:+.3f}, {hi:+.3f}]"
          f"   {'PASS' if ev['criteria']['c1_ci'] else 'FAIL'}")
    print(f"  2 LOO-by-date min gain {ev['loo_min']:>+7.3f} over {ev['loo_folds']} folds"
          f"   {'PASS' if ev['criteria']['c2_loo'] else 'FAIL'}")
    cutbits = "  ".join(
        f"{name} {('%+.3f' % v) if v is not None else '(none)'} (n={n})"
        for name, (n, v) in ev["cuts"].items())
    print(f"  3 windows: {cutbits}"
          f"   {'PASS' if ev['criteria']['c3_windows'] else 'FAIL'}")
    yearbits = "  ".join(f"{y} {v:+.3f} (n={n})" for y, (n, v) in ev["years"].items())
    print(f"  4 years: {yearbits}"
          f"   {'PASS' if ev['criteria']['c4_years'] else 'FAIL'}")
    tierbits = "  ".join(f"{t} {v:+.3f} (n={n})" for t, (n, v) in ev["tiers"].items())
    print(f"  5 pricing tiers: {tierbits or '(none)'}"
          f"   {'PASS' if ev['criteria']['c5_tiers'] else 'FAIL'}")
    print(f"  6 power: {cell['n_affected_dates']} dates / {cell['n_affected_rows']} rows"
          f"   {'PASS' if ev['criteria']['c6_power'] else 'FAIL'}")
    g2 = ev["g2"]
    share = "n/a" if g2["share"] is None else f"{g2['share']:.0%}"
    print(f"  7 G2 continuation: {g2['n_continuation']}/{g2['n_early']} early exits "
          f"({share}) followed by a post-exit max > realized+{CONTINUATION_MARGIN:.2f}"
          f"   {'PASS' if g2['passed'] else 'FAIL'}")
    mix = Counter(res["exit_reason"] for _r, res in cell["early"])
    print(f"  exit mix on the affected rows: {dict(mix)}")
    print(f"  {worst_decile_note(cell['paired'])}")
    print(f"  VERDICT: {ev['verdict']}")


# =============================================================================
# cell construction
# =============================================================================

def build_cells(recs: list[dict], arms: str) -> dict:
    """Every cell in the frozen grid, computed once. Key = (arm, X, cond, action)."""
    cells: dict = {}
    plan = []
    if "E" in arms:
        plan.append(("E", ARM_E_ACTIONS))
    if "T" in arms:
        plan.append(("T", ARM_T_ACTIONS))
    for arm, actions in plan:
        for x in SWITCH_SESSIONS:
            pop = [r for r in recs if r["_shipped"]["days_held"] > x]
            for cond in CONDITIONS:
                for act_label, action in actions:
                    out = cell_outcomes(recs, x, cond, action)
                    aff = [r for r in pop if changed(out[id(r)], r["_shipped"])]
                    early = [(r, out[id(r)]) for r in aff
                             if out[id(r)]["days_held"] < r["_shipped"]["days_held"]]
                    paired = [dict(date=r["date"], a=out[id(r)]["pnl_pct"],
                                   b=r["_shipped"]["pnl_pct"], source=r["source"])
                              for r in pop]
                    cells[(arm, x, cond, act_label)] = dict(
                        out=out, paired=paired, early=early,
                        n_pop_rows=len(pop), n_pop_dates=len({r["date"] for r in pop}),
                        n_affected_rows=len(aff),
                        n_affected_dates=len({r["date"] for r in aff}),
                    )
    return cells


# =============================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", default="ET",
                    help="subset of E/T to run (default both; the registration "
                         "freezes the arms at two and adds none)")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="DEV/BUILD SMOKE ONLY: cap the book at N rows. A capped "
                         "run carries NO conclusion and says so in its header.")
    a = ap.parse_args(argv)

    recs, diag = load_book(include_bs=False)
    print(f"book: {len(recs)} rows  era={diag['era']}  "
          f"counts_by_source={diag['counts_by_source']}  "
          f"date_range={diag['date_range']}  (bs excluded)")
    print(f"debit_calib: {diag['debit_calib']}")
    print(f"n_credit_ungated: {diag['n_credit_ungated']}  — CAVEAT: credit rows are "
          f"admitted WITHOUT the exact-replay\n  calibration gate (there is no single "
          f"credit PROD that calibrates the accumulated\n  sheet: Attempt 13 removed "
          f"the credit stop mid-book). Treat every credit-side\n  exit number below as "
          f"unvalidated until the book is split per credit-stop era.")

    if a.max_rows is not None:
        recs = recs[:a.max_rows]
        print(f"\n  *** SMOKE RUN: book capped at {len(recs)} rows by --max-rows. "
              f"This is a BUILD\n      CHECK ONLY — no number below is a finding and "
              f"nothing here may be quoted. ***")

    # The shipped book, computed once. Every arm is paired against THIS.
    for rec in recs:
        rec["_profile"] = shipped_profile(rec)
        rec["_shipped"] = replay(rec["t"], **rec["_profile"])

    print(f"\n  shipped exit mix: "
          f"{dict(Counter(r['_shipped']['exit_reason'] for r in recs))}")
    print("  ARM T note: the 'tighten stop to -0.40' action INTRODUCES a stop on "
          "credit rows\n  (CREDIT_PROD carries sl=None since Attempt 13). That is "
          "the registered action\n  applied to the whole book, not a credit-specific "
          "knob; the credit caveat above\n  applies to those rows.")

    cells = build_cells(recs, a.arms)
    if not cells:
        print("\n  no arms selected — nothing to do.")
        return 0

    powered = g0(recs, cells)

    rc = g1_leak(recs, cells)
    if rc:
        return rc

    if any(key[0] == "T" for key in cells):
        rc = g_fork(recs)
        if rc:
            return rc
    else:
        hdr("G-FORK — SKIPPED (ARM T not selected; the fork is not exercised)")

    hdr("CELL RESULTS — every cell in the frozen grid, regardless of outcome")
    print("""  Paired against the SHIPPED book (bear_giveback.prod_profile_for for
  debits, CREDIT_PROD for credits) — NEVER against a clean DEBIT_PROD. The
  population at each X is the rows whose SHIPPED replay survives past X; rows
  that already exited are excluded, not zero-padded in.

  A cell is a CANDIDATE only on the FULL conjunction 1-7. Failing any one is
  failing. A cell that clears 1-6 but fails 7 is REACTIVE-AGAIN: the staged
  switch sold continuations exactly as the three trail attempts did, and the
  time-staging bought no immunity. A cell that clears the CI and fails LOO /
  ex-BOTH / sign stability is NULL (a window artifact). A cell that does not
  clear criterion 1 carries no verdict word — it is simply not a candidate,
  printed as '-'.

  CANDIDATE is NOT a ship: it is queued for an independent-window confirmation
  before it may even be proposed for docs/deployment-rules.md.""")

    verdicts = {}
    for key in cells:
        arm, x, cond, act_label = key
        cell = cells[key]
        if not powered[key]:
            sub(f"ARM {arm}  X={x}  {cond_label(cond)}  ->  {act_label}")
            print(f"  population {cell['n_pop_rows']} rows / {cell['n_pop_dates']} dates"
                  f"   affected {cell['n_affected_rows']} rows / "
                  f"{cell['n_affected_dates']} dates")
            print(f"  VERDICT: UNDERPOWERED  (floor {MIN_AFFECTED_DATES} dates / "
                  f"{MIN_AFFECTED_ROWS} rows; nothing read, no re-run on these dates)")
            verdicts[key] = "UNDERPOWERED"
            continue
        ev = evaluate_cell(cell)
        print_cell(key, cell, ev)
        verdicts[key] = ev["verdict"]

    hdr("VERDICT SUMMARY — every cell in the frozen grid")
    print(f"  {'arm':<4}{'X':>3}  {'condition':<12} {'action':<24} "
          f"{'aff rows':>9} {'aff dates':>10}  verdict")
    for key, v in verdicts.items():
        arm, x, cond, act_label = key
        cell = cells[key]
        print(f"  {arm:<4}{x:>3}  {cond_label(cond):<12} {act_label:<24} "
              f"{cell['n_affected_rows']:>9} {cell['n_affected_dates']:>10}  {v}")
    tally = Counter(verdicts.values())
    print(f"\n  tally: {dict(tally)}")
    print("  Nothing ships from a research-tier study. A CANDIDATE is queued for an\n"
          "  independent-window confirmation; REACTIVE-AGAIN closes the thread for\n"
          "  these dates; NULL is recorded as a window artifact; UNDERPOWERED\n"
          "  publishes its census and is not re-run on these dates.")
    print("\n  No annualised figure, Sharpe, or time-to-recover is printed anywhere\n"
          "  above, by design. R is the unit of every conclusion; the dollar cut is a\n"
          "  parallel trigger basis, reported alongside.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
