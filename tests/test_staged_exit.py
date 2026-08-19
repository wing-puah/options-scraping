"""G-FORK: the `staged_exit` fork of the frozen replay engine must BE that engine.

WHY THIS EXISTS
---------------
`research/pre-registrations/staged_exit.md` registers this test BEFORE the fork
existed, and makes it a precondition rather than a nicety:

    "G-FORK (registered here, before the copy exists). With `stage1 == stage2`
    the fork must reproduce `harness.replay` EXACTLY — `(exit_reason,
    days_held, round(pnl, 10))` — on all 795 rows at every grid value of X, AND
    on the full `tests/test_harness_replay.py` fixture. One disagreement fails
    the run. A forked replay that has drifted from the frozen engine is not a
    finding about exits; it is a finding about the fork."

    "`tests/test_staged_exit.py` must exist and must parametrise the G-FORK
    equivalence over the existing `test_harness_replay.py` fixture BEFORE ARM T
    is trusted."

The study module runs the book half of that gate at run time. This file runs
the FIXTURE half, and it is the stronger of the two: the book exercises only
the knob combinations the shipped profiles happen to contain, while
`tests/fixtures/harness_replay.csv` was assembled to hit all nine reachable
exit reasons, both signs of entry, six exit-PRIORITY cases where only the
comparison ORDER decides the answer, three rounding cases sensitive to
`replay`'s `round(..., 10)` clamp, the `int()` truncation in `te_day`, an
unpriced day inside the path, a `trail` set without a `trig` (which must
silently no-op), and the `und_buffer` rule with a control. Reusing that fixture
is deliberate: a fork that survives it has not drifted in any branch anyone has
managed to reach.

The fixture and its loaders are imported from `tests/test_harness_replay.py`
rather than re-read here, so the two files can never disagree about what the
frozen expectations are — and a case added there is automatically covered here.

WHAT ELSE IS PINNED
-------------------
Two properties of ARM E, which is pure composition around the frozen `replay`
and therefore has no machinery gate of its own:

  * the override fires ONLY when the band condition holds at session X, and
    when it fires it returns exactly `(staged_exit, X, pnl at X)`;
  * the leak guard — a row whose SHIPPED replay exited on or before X is
    returned byte-identical, even when the condition would have held at X.

Both are asserted on synthetic trades, so they test the RULE rather than
whatever the current book happens to contain.
"""
from __future__ import annotations

from datetime import date

import pytest

from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study.f2_management.staged_exit import (
    SWITCH_SESSIONS,
    changed,
    cell_outcomes,
    mark_pnl_at,
    post_exit_max,
    replay_staged,
    staged_outcome,
)
from scripts.backtest_study.lib.harness import Trade, replay
from tests.test_harness_replay import CASES, _profile, _trade


def _triple(res: dict) -> tuple:
    """The registration's identity: exit_reason, days_held, round(pnl, 10)."""
    return (res["exit_reason"], res["days_held"], round(res["pnl_pct"], 10))


# ── G-FORK: the fixture half of the gate ─────────────────────────────────────

@pytest.mark.parametrize("switch_day", SWITCH_SESSIONS)
@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_fork_reproduces_the_frozen_engine_when_nothing_is_staged(case, switch_day):
    """`replay_staged(t, prof, prof, X) == replay(t, **prof)`, exactly.

    A failure here means `replay_staged` has drifted from `lib/harness.py` —
    the loop body is supposed to be a verbatim copy with only the per-session
    profile selection added. Fix the fork; never the fixture, and never
    `harness.py` (its docstring forbids editing it in place, which is why this
    copy exists at all).
    """
    t = _trade(case)
    prof = _profile(case)
    want = replay(t, **prof)
    got = replay_staged(t, prof, prof, switch_day)
    assert _triple(got) == _triple(want), \
        f'{case["case_id"]} at X={switch_day}: {case["why"]}'


def test_the_fork_gate_actually_covers_the_whole_fixture():
    """Guard the guard: the parametrisation must not quietly shrink.

    If the fixture is ever loaded differently (a filter, a sample) this test
    fails rather than letting G-FORK pass by checking three rows.
    """
    assert len(CASES) >= 28, f"fixture shrank to {len(CASES)} cases"
    assert set(SWITCH_SESSIONS) == {5, 10, 15, 20}, \
        "the switch-session grid is FROZEN by the pre-registration"


def test_the_fork_is_not_trivially_equal_to_the_shipped_replay():
    """The fork must be able to DISAGREE when the stages actually differ.

    Without this, every assertion above could be satisfied by a `replay_staged`
    that ignored `stage2` entirely — which is exactly the bug G-FORK would then
    be blind to.
    """
    by_id = {c["case_id"]: c for c in CASES}
    case = by_id["debit_trailing_stop_beats_time_exit"]
    t, prof = _trade(case), _profile(case)
    off = {**prof, "trig": None, "trail": None}
    # stage1 = the shipped knobs, stage2 = the same trade with the trail
    # removed from session 1 onward -> a different book, or the swap is a no-op.
    assert _triple(replay_staged(t, off, off, 1)) != _triple(replay(t, **prof))


# ── synthetic trades for the ARM E / leak-guard units ────────────────────────

SIGNAL = date(2025, 1, 6)          # a Monday
EXPIRY = date(2025, 2, 14)


def _synthetic(marks: list) -> Trade:
    """A one-contract, $1.00-entry trade whose marks are handed in directly.

    `entry_option_price = 1.00` makes `denom` 1.0, so `pnl_of(m) == m - 1` and
    every band threshold in the frozen grid is readable straight off the mark.
    `contracts = 1` makes `dollars(pnl) == pnl * 100`.
    """
    grid = _weekday_grid(SIGNAL, EXPIRY)
    assert len(marks) <= len(grid), "test wants more marks than the grid holds"
    padded = list(marks) + [marks[-1]] * (len(grid) - len(marks))
    return Trade({
        "signal_date": SIGNAL.isoformat(),
        "ticker": "TEST",
        "structure": "bull_call_spread",
        "entry_option_price": "1.00",
        "contracts": "1",
        "dte_entry": str((EXPIRY - SIGNAL).days),
        "legs": f"TEST:{EXPIRY.isoformat()}:100:C +1\nTEST:{EXPIRY.isoformat()}:110:C -1",
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in padded),
    }, load_underlying=False)


# No profit target, no stop, no time exit: the shipped replay on a flat path
# runs to the end of the grid, so every row is inside the population at every
# X in the frozen grid and the staged switch is the only thing that can move it.
NO_RULES = dict(pt=None, sl=None, trig=None, trail=None, tef=None)
# A profit target that a spiking path hits early — used to build a row OUTSIDE
# the population (shipped days_held <= X) for the leak guard.
QUICK_PT = dict(pt=0.90, sl=0.75, trig=None, trail=None, tef=None)

COND_UP_50 = ("R >= +0.50", "R", "profit", 0.50)
COND_DOWN_25 = ("R <= -0.25", "R", "loss", -0.25)
COND_DOLLARS_UP = ("$ >= +250", "$", "profit", 250.0)


def _rec(t: Trade, profile: dict) -> dict:
    """The minimal record shape `staged_outcome` reads."""
    return dict(t=t, date=SIGNAL.isoformat(), ticker="TEST", source="real",
                credit=False, _profile=profile, _shipped=replay(t, **profile))


# ── ARM E: the override ──────────────────────────────────────────────────────

def test_arm_e_fires_at_X_with_the_day_X_pnl_when_the_band_holds():
    """Condition met at X -> `(staged_exit, X, pnl at X)` and nothing else.

    The mark at session 5 is 1.60 (R = +0.60, clearing R >= +0.50); every other
    session sits at 1.30. If the override read the wrong index, or re-derived
    the P&L from the exit day rather than session X, the reported R would be
    +0.30 and this fails.
    """
    t = _synthetic([1.30, 1.30, 1.30, 1.30, 1.60, 1.30, 1.30, 1.30])
    rec = _rec(t, NO_RULES)
    assert rec["_shipped"]["days_held"] > 5           # inside the population
    res = staged_outcome(rec, 5, COND_UP_50, None)
    assert _triple(res) == ("staged_exit", 5, 0.60)


def test_arm_e_leaves_the_row_alone_when_the_band_does_not_hold():
    """Condition NOT met at X -> the SHIPPED result, byte-identical.

    The else-branch is registered as "always continue shipped profile" — there
    is no third outcome in any arm.
    """
    t = _synthetic([1.30] * 8)
    rec = _rec(t, NO_RULES)
    res = staged_outcome(rec, 5, COND_UP_50, None)
    assert _triple(res) == _triple(rec["_shipped"])
    assert res is rec["_shipped"], "the untouched branch must return the shipped result"


def test_arm_e_reads_the_loss_side_and_the_dollar_basis_off_the_same_mark():
    """The loss band and the parallel dollar cut are the same evaluation.

    At session 5 the mark is 0.60 -> R = -0.40 and dollars = -40. The loss
    condition R <= -0.25 fires; the profit dollar cut $ >= +250 does not. Both
    read `pnl_of(marks[4])`, which is what makes the dollar column a parallel
    TRIGGER basis rather than a different rule.
    """
    t = _synthetic([1.00, 1.00, 1.00, 1.00, 0.60, 1.00, 1.00, 1.00])
    rec = _rec(t, NO_RULES)
    fired = staged_outcome(rec, 5, COND_DOWN_25, None)
    assert _triple(fired) == ("staged_exit", 5, -0.40)
    assert t.dollars(-0.40) == pytest.approx(-40.0)
    assert _triple(staged_outcome(rec, 5, COND_DOLLARS_UP, None)) == \
        _triple(rec["_shipped"])


def test_a_row_with_no_mark_at_X_continues_the_shipped_profile():
    """An unpriced session X is not a zero, and not a trigger.

    `replay` skips an unpriced day without evaluating a rule; a staged switch
    likewise has no band to read, so the row continues shipped. Returning 0.0
    here would fabricate a flat-P&L exit out of missing data.
    """
    t = _synthetic([1.30, 1.30, 1.30, 1.30, None, 1.30, 1.30, 1.30])
    rec = _rec(t, NO_RULES)
    assert mark_pnl_at(t, 5) is None
    assert _triple(staged_outcome(rec, 5, COND_UP_50, None)) == _triple(rec["_shipped"])


# ── G1: the leak guard, as a unit ────────────────────────────────────────────

def test_a_row_that_already_exited_on_or_before_X_is_never_touched():
    """The population keying, asserted directly.

    The path spikes to 1.95 on session 2, so the shipped profile takes the
    profit target there (days_held = 2 <= 5). The band condition WOULD hold at
    session 5 (mark 1.60), so a rule that evaluated the condition before the
    population check would move this row — that is the leak G1 exists to catch.
    """
    t = _synthetic([1.30, 1.95, 1.30, 1.30, 1.60, 1.30, 1.30, 1.30])
    rec = _rec(t, QUICK_PT)
    assert rec["_shipped"]["exit_reason"] == "profit_target"
    assert rec["_shipped"]["days_held"] == 2
    assert mark_pnl_at(t, 5) == 0.60          # the band WOULD have held
    assert _triple(staged_outcome(rec, 5, COND_UP_50, None)) == _triple(rec["_shipped"])


def test_the_leak_guard_over_a_mixed_book_changes_nothing_outside_the_population():
    """The gate as the study runs it: whole book in, keying evaluated inside.

    Pre-filtering the list to the population would make this vacuous — the rule
    could not touch a row it was never handed. Here it is handed everything.
    """
    inside = _rec(_synthetic([1.30, 1.30, 1.30, 1.30, 1.60, 1.30, 1.30, 1.30]),
                  NO_RULES)
    outside = _rec(_synthetic([1.30, 1.95, 1.30, 1.30, 1.60, 1.30, 1.30, 1.30]),
                   QUICK_PT)
    book = [inside, outside]
    out = cell_outcomes(book, 5, COND_UP_50, None)

    leaked = [r for r in book
              if r["_shipped"]["days_held"] <= 5 and changed(out[id(r)], r["_shipped"])]
    assert leaked == [], "a row outside the population moved"
    # ...and the guard is not passing by moving nothing at all.
    assert changed(out[id(inside)], inside["_shipped"])


def test_arm_t_action_only_reaches_sessions_at_or_after_X():
    """ARM T's stage2 must not retro-apply to the sessions before the switch.

    The path dips to 0.55 on session 3 (R = -0.45), which the tightened stop of
    -0.40 would catch — but session 3 is before X = 5, so the shipped `sl` of
    0.75 governs there and the position is still open at X. If the fork applied
    stage2 from session 1, the exit would land on day 3.
    """
    t = _synthetic([1.00, 1.00, 0.55, 1.00, 0.70, 0.55, 1.00, 1.00])
    profile = dict(pt=None, sl=0.75, trig=None, trail=None, tef=None)
    rec = _rec(t, profile)
    assert rec["_shipped"]["days_held"] > 5
    res = staged_outcome(rec, 5, COND_DOWN_25, {"sl": 0.40})
    assert res["exit_reason"] == "stop_loss"
    assert res["days_held"] >= 5, "stage2 leaked backwards past the switch session"


# ── G2's measurement ─────────────────────────────────────────────────────────

def test_post_exit_max_reads_only_the_remainder_of_the_path():
    """G2's input: the best the position went on to show AFTER it was sold.

    Marks at or before the exit day must not enter the maximum, or a cell that
    sold the top would score as a continuation sale.
    """
    t = _synthetic([1.30, 1.90, 1.30, 1.30, 1.60, 1.30, 1.30, 1.30])
    assert post_exit_max(t, 5) == pytest.approx(0.30)   # 1.90 on day 2 excluded
    assert post_exit_max(t, 1) == pytest.approx(0.90)   # 1.90 on day 2 included
    assert post_exit_max(t, len(t.marks)) is None       # nothing left to see
