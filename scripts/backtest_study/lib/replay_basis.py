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
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib.harness import Trade, _pct, replay  # noqa: E402

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


def calib(t: Trade, prod: dict, replay_fn=replay):
    """(exact, near, want, got) — does replaying `t` under `prod` reproduce the
    row's stored (exit_reason, days_held, realized_pnl_pct)?"""
    rp = replay_fn(t, **prod)
    want = (t.row["exit_reason"], int(float(t.row["days_held"])),
            round(_pct(t.row["realized_pnl_pct"]), 4))
    got = (rp["exit_reason"], rp["days_held"], round(rp["pnl_pct"], 4))
    exact = want == got
    near = (want[0] == got[0] and want[1] == got[1]
            and abs(want[2] - got[2]) <= NEAR_MISS_TOL + 1e-9)
    return exact, near, want, got


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


def classify(t: Trade, prod: dict, unreachable: set[str], replay_fn=replay):
    """'exact' | 'near' | 'superseded' | 'boundary_tie' | 'hard', plus
    (want, got).

    superseded — the row replays fine; its STORED outcome was produced by an
      exit rule this profile does not contain, so the disagreement is a config
      difference, not a pricing failure. On this book that is the
      `regime_exit.cells.BEAR_HE` trail shipped 2026-07-22 (`31cb935`), the
      `structure_exit.bear_debit.be_after` ratchet shipped 2026-08-11, and, on
      older rows, the pre-Attempt-10 global trail.
    boundary_tie — the flat replay fires a pt/sl threshold on a day whose pnl
      is a 1-ulp rounding tie with it, while production's unrounded pnl
      survived the boundary; the stored outcome reproduces in full once the
      threshold is nudged TIE_EPS (see `_boundary_tie`). Benign, but excluded
      from calibrated-row dollar reconciliation the way superseded rows are —
      its flat replay still books a different (reason, day).
    hard — a genuine mismatch with no config explanation: the harness and the
      stored row disagree about a path both sides claim the same rules for.
      This is the only bucket that stops a study.

    NOT keyed on the `exit_basis` column. That column exists in `_KEY_ORDER`
    (`scripts/backtest/core.py:61`) but reaches the export UNLABELLED and
    MISALIGNED — measured 2026-08-14: 7 of 13 `CREDIT`-tagged rows have a
    POSITIVE entry price (impossible per `simulate.py:_exit_basis`), no
    `BEAR_HE`-tagged row has a `trailing_stop` exit, and all 12 rows that
    provably ran the BEAR_HE trail are blank. The Sheets tab header was never
    given the column, so the values land in a nameless trailing field — exactly
    the hazard CLAUDE.md warns about. Re-key on it only after
    `scripts/align_tab_headers.py` has fixed the header AND the values have been
    re-verified against entry-price sign.
    """
    exact, near, want, got = calib(t, prod, replay_fn)
    if exact:
        return "exact", want, got
    if near:
        return "near", want, got
    if want[0] in unreachable:
        return "superseded", want, got
    if _boundary_tie(t, prod, replay_fn):
        return "boundary_tie", want, got
    return "hard", want, got
