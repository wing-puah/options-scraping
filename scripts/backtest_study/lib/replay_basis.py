"""The replay-basis classifier — ONE implementation of "does a stored row
reproduce under a given exit profile, and if not, why".

Extracted verbatim from `exit_switch_mech_study.py` (2026-08-24) so that
study's harness gate, `exit_mechanism_study.calibrate()`, and `lib/book.py`'s
`debit_calib` tally share a single definition and cannot drift. The replay
engine itself stays in `lib/harness.py` (FROZEN — see its docstring); this
module only interprets its output against a stored row.

Why the classification is mechanical, not a guess: `replay()` can only ever
emit an exit reason whose governing knob is set in the profile it is called
with (harness.py:119-170). So the set of exit reasons a profile CANNOT produce
is a property of the profile, and a stored row whose exit_reason falls in that
set was, by construction, written under a different exit configuration. That
is what `superseded-basis` means below, and it is why the classification needs
no date heuristic and no `exit_basis` column (see the note in `classify`).

THE STORED ROW'S OWN BASIS (operator rulings, 2026-09-28). Since the
2026-09-24 re-price a stored row differs from a frozen-harness replay in three
ways that are not pricing failures. Each is handled here, once, so every gate
that compares a replay with a stored row reads the same rule:

  - COST. `realized_pnl_pct` / `realized_pnl_abs` are NET of the row's
    `cost_total` (`simulate._apply_costs`); the harness is gross. A row whose
    `cost_basis` is non-blank is compared with the cost added back, in
    production's own arithmetic (`reproduces_pnl`). A pre-cost-model row
    (`cost_basis` blank) is compared as before. `lib/mtm_curve.py` makes the
    same TARGET_STORED / TARGET_POSITION split for the same reason.
  - DATA END. Production's exit scan stops at `path_data_end`; the marks after
    it are carried and a position still open there is booked `cap_open` on
    that day (`path_status` = `open_at_data_end`). `bounded(t)` is the Trade cut
    at that day, so a replay of it stops where production stopped. The harness
    itself is not edited: the cut is a loader-level view of the same row.
  - DEFERRED FILL. `exit_fill` = `deferred_<n>` rows filled on a later
    two-sided day than the trigger; the frozen harness fills on the trigger day
    and cannot know the later fill. `classify` puts them in their own
    `deferred_fill` bucket: a superseded basis, kept as outcomes, never HARD.
    `no_two_sided` rows are compared as normal, because production filled
    them on the trigger day's mark, which is what the harness does.
"""
from __future__ import annotations

import copy
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib.harness import Trade, _pct, _to_float, replay  # noqa: E402

NEAR_MISS_TOL = 0.0001

# Threshold nudge for the boundary-tie re-check in `classify`. Must sit between
# the two scales it separates: a rounding tie leaves the raw pnl within ~5e-11
# of the threshold (that is what makes `round(pl, 10)` land ON it), while the
# smallest GENUINE pnl-to-threshold gap is one 4-decimal mark tick over the
# entry denom — ≥ ~1e-6 even on a $100 spread. 1e-9 clears the first by 20x
# and the second by 1000x, so the nudge can only ever un-fire an exact tie.
TIE_EPS = 1e-9

_REASON_REQUIRES = {
    "profit_target": ("pt",),
    "trailing_stop": ("trig", "trail"),
    "underlying_stop": ("und_buffer",),
    "be_stop": ("be_after",),
    "stop_loss": ("sl",),
    "time_exit": ("tef",),
    # dollar_stop / expired / cap_open are unconditional in replay() — always reachable.
}


def unreachable_reasons(prod: dict) -> set[str]:
    """Exit reasons `replay(**prod)` can never emit, because the knob that
    produces them is unset. Under DEBIT_PROD (pt/sl/tef, no trail) this is
    {trailing_stop, underlying_stop, be_stop}."""
    return {reason for reason, knobs in _REASON_REQUIRES.items()
            if any(prod.get(k) is None for k in knobs)}


def _cell(t: Trade, field: str) -> str:
    v = t.row.get(field)
    return "" if v is None else str(v).strip()


def cost_charged(t: Trade) -> float:
    """The round-trip cost the stored P&L is net of, in dollars; 0.0 for a row
    written before the cost model (`cost_basis` blank), which is gross."""
    if not _cell(t, "cost_basis"):
        return 0.0
    return _to_float(t.row.get("cost_total")) or 0.0


def cost_pct(t: Trade) -> float:
    """`cost_charged` on the pnl-pct scale, with production's denominator
    (`simulate._apply_costs`: abs(entry_net) x 100 x contracts)."""
    position_dollars = t.denom * 100 * t.contracts
    return cost_charged(t) / position_dollars if position_dollars else 0.0


def stored_gross_pct(t: Trade) -> float:
    """The stored `realized_pnl_pct` with the row's cost added back (4 dp)."""
    return round(_pct(t.row["realized_pnl_pct"]) + cost_pct(t), 4)


def stored_gross_dollars(t: Trade) -> float:
    """`realized_pnl_abs + cost_total`: the stored outcome on the replay's
    gross basis. For a pre-cost-model row this is `realized_pnl_abs`."""
    return float(t.row["realized_pnl_abs"]) + cost_charged(t)


def reproduces_pnl(t: Trade, got_pct: float) -> bool:
    """Does a GROSS replay pnl reproduce the stored row's `realized_pnl_pct`
    exactly? Production rounds the gross pnl to 4 dp, subtracts the cost pct,
    and rounds again; this applies the same two steps to the replay, so the
    comparison is exact equality on the stored figure, not a tolerance."""
    stored = round(_pct(t.row["realized_pnl_pct"]), 4)
    got4 = round(got_pct, 4)
    c = cost_pct(t)
    return (round(got4 - c, 4) if c else got4) == stored


def is_deferred_fill(t: Trade) -> bool:
    """`exit_fill` = `deferred_<n>`: the fill moved to a later day than the
    trigger, which the frozen harness cannot reproduce."""
    return _cell(t, "exit_fill").startswith("deferred_")


def data_end_index(t: Trade) -> int | None:
    """1-based grid index of the last day on or before `path_data_end`, exactly
    as `simulate._simulate` computes `data_end_idx`; None when the row carries
    no `path_data_end` (every row written before 2026-09-23)."""
    raw = _cell(t, "path_data_end")
    if not raw:
        return None
    end = date.fromisoformat(raw[:10])
    return sum(1 for day in t.grid if day <= end)


def bounded(t: Trade) -> Trade:
    """`t` cut at its data end, so a replay stops where production's exit scan
    stopped (`simulate._summarize_path`, "NO RULE MAY FIRE PAST THE LAST REAL
    QUOTE"). Returns `t` itself when there is nothing to cut.

    A copy, never an edit: the stored row, its full mark string and the frozen
    harness are unchanged. The cut copy has `cap_reached_expiry` False, because
    production books a truncated path `cap_open`, never `expired`. When the
    data ended before the first priced day, production marks the position on
    its first priced day, so the cut keeps that one day.
    """
    k = data_end_index(t)
    if k is None:
        return t
    later = [i for i, m in enumerate(t.marks, start=1) if m is not None and i > k]
    if not later:
        return t                      # nothing priced past the data end
    if not any(m is not None for m in t.marks[:k]):
        k = next(i for i, m in enumerate(t.marks, start=1) if m is not None)
    v = copy.copy(t)
    # The row's own per-day columns (`daily_pnl_csv`, `daily_source_csv`) keep
    # the full grid's length; a reader that checks them against the grid
    # checks against this, then reads only the first `len(v.grid)` tokens.
    v.uncut_grid_len = len(t.grid)
    v.grid = t.grid[:k]
    v.marks = t.marks[:k]
    v.cap_reached_expiry = False
    return v


def calib(t: Trade, prod: dict, replay_fn=replay):
    """(exact, near, want, got) — does replaying `t` under `prod` reproduce the
    row's stored (exit_reason, days_held, realized_pnl_pct)?

    On the row's own basis (module docstring): the replay runs on `bounded(t)`,
    and `want`'s pnl is the stored figure with the row's cost added back, so
    both sides of the tuple are gross. `exact` is decided by `reproduces_pnl`,
    production's own rounding of gross into net."""
    rp = replay_fn(bounded(t), **prod)
    want = (t.row["exit_reason"], int(float(t.row["days_held"])), stored_gross_pct(t))
    got = (rp["exit_reason"], rp["days_held"], round(rp["pnl_pct"], 4))
    same_exit = want[0] == got[0] and want[1] == got[1]
    exact = same_exit and reproduces_pnl(t, rp["pnl_pct"])
    near = same_exit and abs(want[2] - got[2]) <= NEAR_MISS_TOL + 1e-9
    return exact, near, want, got


def replay_dollars(t: Trade, prod: dict, replay_fn=replay) -> float:
    """Gross replay dollars on the row's data-bounded path — the figure a
    dollar reconciliation compares with `stored_gross_dollars(t)`."""
    return t.dollars(replay_fn(bounded(t), **prod)["pnl_pct"])


def _boundary_tie(t: Trade, prod: dict, replay_fn) -> bool:
    """Does the stored row reproduce once the pt/sl threshold is nudged
    TIE_EPS in the non-firing direction? If yes, the flat replay's mismatch is
    a 1-ulp threshold TIE production landed on the other side of, not a
    pricing failure.

    The mirror of the `round(pl, 10)` note in `harness.replay`: that rounding
    exists so a tie production DID fire (its unrounded pnl 1 ulp past the
    boundary — Attempt 13's XLF 2024-06-21) fires in replay too. But rounding
    collapses BOTH sides of the boundary onto it, so when production's
    unrounded pnl landed 1 ulp on the SURVIVING side, the replay fires a day
    early under every entry basis and no basis substitution can reconcile it.
    First seen 2024-08-15 HYG bear_put (export rounds entry 0.29−0.09 to
    "0.2"; day-17 mark 0.05 is exactly −0.75 on the rounded basis, 1 ulp shy
    of it on production's): stored dollar_stop day 18 replays as stop_loss
    day 17. Nudging the threshold un-fires only an exact tie (see TIE_EPS),
    after which the stored outcome must reproduce in full — reason, day and
    pnl — for the row to earn the bucket.
    """
    nudged = [{k: prod[k] + TIE_EPS for k in ("pt", "sl") if prod.get(k) is not None}]
    nudged += [{k: prod[k] + TIE_EPS} for k in ("pt", "sl") if prod.get(k) is not None]
    for delta in nudged:
        exact, near, _w, _g = calib(t, {**prod, **delta}, replay_fn)
        if exact or near:
            return True
    return False


KINDS = ("exact", "near", "superseded", "boundary_tie", "deferred_fill", "hard")


def classify(t: Trade, prod: dict, unreachable: set[str], replay_fn=replay):
    """'exact' | 'near' | 'superseded' | 'boundary_tie' | 'deferred_fill' |
    'hard', plus (want, got).

    superseded — the row replays fine; its STORED outcome was produced by an
      exit rule this profile does not contain, so the disagreement is a config
      difference, not a pricing failure. On this book that is the
      `regime_exit.cells.BEAR_HE` trail shipped 2026-07-22 (`31cb935`), the
      `structure_exit.bear_debit.be_after` breakeven stop shipped 2026-08-11, and, on
      older rows, the pre-Attempt-10 global trail.
    boundary_tie — the flat replay fires a pt/sl threshold on a day whose pnl
      is a 1-ulp rounding tie with it, while production's unrounded pnl
      survived the boundary; the stored outcome reproduces in full once the
      threshold is nudged TIE_EPS (see `_boundary_tie`). Benign, but excluded
      from calibrated-row dollar reconciliation the way superseded rows are —
      its flat replay still books a different (reason, day).
    deferred_fill — `exit_fill` is `deferred_<n>`: production filled the exit
      on a later two-sided day than the trigger. A superseded basis (operator
      ruling 2026-09-28): not compared, kept as an outcome, never HARD.
    hard — a genuine mismatch with no config explanation: the harness and the
      stored row disagree about a path both sides claim the same rules for.
      This is the only bucket that stops a study.

    NOT keyed on the `exit_basis` column, and that stays true now that the
    column is clean on v4 (see `simulate.py:_exit_basis`). Two reasons, neither
    of which the v4 repair touches:

    - This classifier must work on EVERY era. On v3 and earlier the column
      reaches the export unlabelled and scrambled (measured 2026-08-14: 7 of 13
      `CREDIT` tags on positive-entry-price rows, no `BEAR_HE` tag on a
      `trailing_stop` exit, all 12 provable-trail rows blank), and those exports
      are frozen. A column-keyed classifier would silently mis-bucket them.
    - The column names the profile the row was WRITTEN under. This function asks
      the different question of whether the row reproduces under the profile
      being tested — so it must be derived from the replay, not from a stored
      label that cannot be cross-checked.

    A study that wants to STRATIFY a v4 book by exit profile should read the
    column; a study that wants to know whether a row replays should not.
    """
    exact, near, want, got = calib(t, prod, replay_fn)
    if is_deferred_fill(t):
        return "deferred_fill", want, got
    if exact:
        return "exact", want, got
    if near:
        return "near", want, got
    if want[0] in unreachable:
        return "superseded", want, got
    if _boundary_tie(t, prod, replay_fn):
        return "boundary_tie", want, got
    return "hard", want, got
