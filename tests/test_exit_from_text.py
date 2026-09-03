"""Unit tests for the `exit_from_text` study's three arms.

WHY THESE AND NOT OTHERS
------------------------
`research/pre-registrations/f2_management/exit_from_text.md` §Build notes
requires this file to cover "E1 parity on a synthetic path against the harness
exit vocabulary, the invalidation/trigger parser edge cases (including the
straddle breakeven path) and the unparseable buckets". Everything here is
asserted on SYNTHETIC trades and SYNTHETIC bars, never on the live exports:
the study's own report is the place where the book is read, and a test that
depends on `backtests/to_evaluate/` fails for the wrong reason the moment the
tabs are re-exported (`lib/era.py`'s whole subject).

The frozen harness is IMPORTED, never forked: every expectation about a
shipped exit below comes from `harness.replay` itself, so a test can never
encode a second opinion about what production does.

WHAT IS PINNED
--------------
  * E1 fires on the RIGHT session at each buffer in the frozen grid, and the
    buffer moves the threshold in the direction that makes the stop HARDER to
    fire (Attempt 9's marginal-touch lesson);
  * E1 does not fire on the wrong side — the direction comes from the
    STRUCTURE, so a long-delta position ignores a rally and a short-delta one
    exits into it;
  * the straddle/strangle BREAKEVEN path, including both unusable buckets a
    vol structure can land in;
  * the EARLIER-OF composition against a shipped exit, in all three
    orderings (text stop earlier / later / same session);
  * the `level == a strike` split at its fixed tolerance;
  * E2's met / not-met at both N, including the holiday case that makes the
    window a SESSION count rather than a calendar one;
  * E3's survival-control bucketing;
  * the AFFECTED-dates LOO median rule on a zero-inflated delta — the 2026-07-22
    correction, whose whole point is that a whole-population median is
    untrippable there.
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta

import pytest

from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study.lib import protocol as P
from scripts.backtest_study.lib.harness import Trade, replay
from scripts.backtest_study.lib.underlying import Bar
from scripts.backtest_study.f2_management.exit_from_text import (
    BUFFERS,
    STRIKE_TOL_ABS,
    STRIKE_TOL_REL,
    breakeven_levels,
    changed,
    e1_outcome,
    horizon_of,
    horizon_tef,
    level_is_a_strike,
    loo_fold_gains,
    stop_levels,
    stop_session,
    strikes_of,
    structure_side,
    tercile_label,
    terciles,
    trigger_direction,
    trigger_met,
)

SIGNAL = date(2025, 1, 6)          # a Monday, so the grid starts 2025-01-07
EXPIRY = date(2025, 2, 21)


def _trade(legs: str, entry: float, marks: list[float | None],
           signal: date = SIGNAL, expiry: date = EXPIRY,
           structure: str = "bull_call_spread") -> Trade:
    """A synthetic `Trade` whose mark series is exactly as long as its grid.

    `Trade.__init__` asserts that, so the padding is not cosmetic: it is what
    makes the object legal at all. Marks past the caller's list carry the last
    value forward, which is what an untouched position looks like.
    """
    grid = _weekday_grid(signal, expiry)
    full = (list(marks) + [marks[-1]] * len(grid))[:len(grid)]
    return Trade({
        "signal_date": signal.isoformat(),
        "ticker": "TEST",
        "structure": structure,
        "entry_option_price": str(entry),
        "contracts": "1",
        "dte_entry": str((expiry - signal).days),
        "legs": legs,
        "daily_price_csv": ",".join("" if m is None else str(m) for m in full),
    }, load_underlying=False)


def _rec(t: Trade, structure: str, credit: bool, level: float | None) -> dict:
    """The subset of a `load_corpus` record the E1 helpers actually read."""
    return dict(t=t, structure=structure, credit=credit,
                features={"invalidation_level": level})


def _bars(t: Trade, closes: list[float]) -> dict:
    """`{grid date: Bar}` — one synthetic session per grid day, real-OHLC source."""
    return {d: Bar(c=c, o=c, h=c, l=c) for d, c in zip(t.grid, closes)}


# ── E1: the stop fires on the right session, at every buffer ────────────────

@pytest.mark.parametrize("buffer,want_session", [(0.0, 2), (0.01, 3), (0.02, 4)])
def test_e1_fires_on_the_right_session_at_each_buffer(buffer, want_session):
    """Level 100, long delta -> the stop is a close BELOW 100 * (1 - buffer).

    Closes are chosen so each grid value in the FROZEN buffer grid picks a
    different session: 99.0 clears 0% only, 98.5 clears 1% too, 97.5 clears all
    three. That is the Attempt 9 shape stated in the registration — a bigger
    buffer clips marginal touches, so the stop fires LATER, never earlier.
    """
    t = _trade("TEST:2025-02-21:100:C +1\nTEST:2025-02-21:110:C -1", 3.0,
               [3.0, 3.0, 3.0, 3.0, 3.0, 3.0])
    rec = _rec(t, "bull_call_spread", credit=False, level=100.0)
    bars = _bars(t, [101.0, 99.0, 98.5, 97.5, 97.0, 96.0])
    levels, basis, reason = stop_levels(rec, buffer)
    assert reason is None and basis == "text_level"
    assert levels == [("below", 100.0 * (1 - buffer))]
    assert stop_session(t, levels, bars) == (want_session, None)


def test_e1_buffer_grid_is_the_registered_three_values():
    assert BUFFERS == (0.0, 0.01, 0.02)


def test_e1_does_not_fire_on_the_wrong_side():
    """A rally is not an invalidation for a long-delta position — and IS one for
    a short-delta position with the same level and the same closes.

    The direction is inferred from the STRUCTURE, never from the outcome, so
    the identical price path has to produce opposite answers for the two sides.
    """
    t = _trade("TEST:2025-02-21:100:C +1\nTEST:2025-02-21:110:C -1", 3.0,
               [3.0] * 6)
    bars = _bars(t, [101.0, 102.0, 103.0, 104.0, 105.0, 106.0])

    long_rec = _rec(t, "bull_call_spread", credit=False, level=100.0)
    levels, _b, _r = stop_levels(long_rec, 0.0)
    assert stop_session(t, levels, bars) == (None, None)   # never fired

    short_rec = _rec(t, "bear_put_spread", credit=False, level=100.0)
    levels, _b, _r = stop_levels(short_rec, 0.0)
    assert levels == [("above", 100.0)]
    assert stop_session(t, levels, bars) == (1, None)


def test_e1_structure_side_vocabulary():
    assert structure_side("bull_put_spread", credit=True) == "long"
    assert structure_side("long_put", credit=False) == "short"
    assert structure_side("straddle", credit=True) == "vol"
    # Neither delta-directional nor covered by the breakeven bullet.
    assert structure_side("iron_condor", credit=True) is None


def test_e1_a_close_exactly_on_the_level_does_not_fire():
    """The comparison is strict, matching `harness.replay`'s own breach test."""
    t = _trade("TEST:2025-02-21:100:C +1", 3.0, [3.0] * 4)
    rec = _rec(t, "bull_call_spread", credit=False, level=100.0)
    levels, _b, _r = stop_levels(rec, 0.0)
    assert stop_session(t, levels, _bars(t, [100.0, 100.0, 100.0, 99.9])) == (4, None)


# ── E1: the straddle / strangle breakeven path ──────────────────────────────

def test_short_straddle_uses_breakevens_never_a_strike():
    """A SHORT straddle's stop is `strike +/- credit`, buffered outward.

    Registration §E1: "Straddles and strangles use BREAKEVEN levels, never a
    strike (Attempt 9: a strike basis fires day 1 when the short strike is
    ~ATM)." With the 100 strike ~ATM, a strike basis would fire on session 1;
    the breakeven basis does not.
    """
    t = _trade("TEST:2025-02-21:100:C -1\nTEST:2025-02-21:100:P -1", -5.0,
               [5.0] * 6, structure="straddle")
    rec = _rec(t, "straddle", credit=True, level=None)
    levels, basis, reason = stop_levels(rec, 0.0)
    assert reason is None and basis == "breakeven"
    assert levels == [("above", 105.0), ("below", 95.0)]
    # 100.5 is past the strike but inside the breakevens: a strike basis fires
    # here, the registered breakeven basis does not.
    assert stop_session(t, levels, _bars(t, [100.5, 101.0, 106.0, 106.0, 106.0, 106.0])) \
        == (3, None)
    # ... and the buffer pushes the breakeven further out, as on the directional path.
    lv1, _b, _r = stop_levels(rec, 0.01)
    assert lv1 == [("above", 105.0 * 1.01), ("below", 95.0 * 0.99)]
    assert stop_session(t, lv1, _bars(t, [100.5, 101.0, 106.0, 106.0, 106.0, 106.0])) \
        == (None, None)


def test_breakeven_levels_need_both_a_call_and_a_put():
    t = _trade("TEST:2025-02-21:100:C -1\nTEST:2025-02-21:110:C +1", -2.0,
               [2.0] * 4, structure="strangle")
    assert breakeven_levels(t, 0.0) is None
    rec = _rec(t, "strangle", credit=True, level=105.0)
    assert stop_levels(rec, 0.0) == (None, "", "no_breakeven")


def test_long_vol_and_unknown_structures_land_in_their_own_buckets():
    """The two registered-by-deviation buckets, counted rather than fabricated.

    A DEBIT straddle wins beyond its breakevens, so a breakeven-beyond stop
    would fire on the profit side; an iron condor is neither delta-directional
    nor covered by the straddle bullet. Both are reported buckets, never given
    a fallback level.
    """
    t = _trade("TEST:2025-02-21:100:C +1\nTEST:2025-02-21:100:P +1", 5.0,
               [5.0] * 4, structure="straddle")
    assert stop_levels(_rec(t, "straddle", credit=False, level=None), 0.0) \
        == (None, "", "long_vol_no_stop_side")
    assert stop_levels(_rec(t, "iron_condor", credit=True, level=100.0), 0.0) \
        == (None, "", "no_structure_side")


def test_a_missing_invalidation_level_is_its_own_bucket():
    t = _trade("TEST:2025-02-21:100:C +1", 3.0, [3.0] * 4)
    assert stop_levels(_rec(t, "bull_call_spread", False, None), 0.0) \
        == (None, "", "no_level")


# ── E1: the earlier-of composition around the frozen replay ────────────────

def test_e1_takes_the_earlier_of_the_text_stop_and_the_shipped_exit():
    """Three orderings, one of them the registered tie case.

    The shipped exit here is produced by the FROZEN `replay`, not asserted by
    hand, so this pins the composition rather than a second opinion about
    production.
    """
    t = _trade("TEST:2025-02-21:100:C +1\nTEST:2025-02-21:110:C -1", 2.0,
               [2.0, 2.0, 2.0, 0.4, 0.4, 0.4])
    profile = dict(pt=0.90, sl=0.75, trig=None, trail=None, tef=0.75)
    shipped = replay(t, **profile)
    assert (shipped["exit_reason"], shipped["days_held"]) == ("stop_loss", 4)
    rec = dict(t=t, _shipped=shipped)

    # earlier -> the text stop wins and carries that session's mark P&L
    got = e1_outcome(rec, 2)
    assert (got["exit_reason"], got["days_held"]) == ("text_stop", 2)
    assert got["pnl_pct"] == pytest.approx(round(t.pnl_of(t.marks[1]), 10))
    assert changed(got, shipped)

    # same session -> unchanged (deviation 2: a label-only change is not affected)
    assert e1_outcome(rec, 4) is shipped
    # later -> unchanged; PROD's stops stay live behind the text rule
    assert e1_outcome(rec, 5) is shipped
    assert not changed(e1_outcome(rec, 5), shipped)


def test_e1_never_exits_on_a_session_with_no_mark():
    """An unpriced session cannot be exited at, so the scan continues past it.

    `replay` skips an unpriced day without evaluating a rule; the text stop
    does the same, because a position cannot be closed at a mark that does not
    exist.
    """
    t = _trade("TEST:2025-02-21:100:C +1", 3.0, [3.0, None, 3.0, 3.0])
    rec = _rec(t, "bull_call_spread", credit=False, level=100.0)
    levels, _b, _r = stop_levels(rec, 0.0)
    # session 2 breaches but has no mark; session 3 breaches and does.
    assert stop_session(t, levels, _bars(t, [101.0, 98.0, 98.0, 98.0])) == (3, None)


# ── the binding `level == a strike` split ──────────────────────────────────

def test_the_strike_equality_split_at_its_fixed_tolerance():
    t = _trade("TEST:2025-02-21:100:C +1\nTEST:2025-02-21:110:C -1", 3.0, [3.0] * 4)
    assert strikes_of(t) == [100.0, 110.0]
    assert level_is_a_strike(110.0, strikes_of(t)) is True
    # inside the fixed relative tolerance (0.5% of 100 = 0.50)
    assert level_is_a_strike(100.0 - 0.4 * STRIKE_TOL_REL * 100 / 0.5,
                             strikes_of(t)) is True
    assert level_is_a_strike(99.0, strikes_of(t)) is False       # outside it
    assert level_is_a_strike(None, strikes_of(t)) is None        # nothing to compare
    assert level_is_a_strike(100.0, []) is None
    # the absolute floor keeps a cheap strike from having a vanishing band
    assert level_is_a_strike(2.0 + STRIKE_TOL_ABS, [2.0]) is True


# ── E2: met / not met within N sessions ────────────────────────────────────

def test_e2_met_within_n_sessions_at_both_grid_values():
    """The level is met on session 3 -> not entered at N=1, entered at N=3."""
    t = _trade("TEST:2025-02-21:100:C +1", 3.0, [3.0] * 6)
    bars = _bars(t, [98.0, 99.0, 101.0, 102.0, 103.0, 104.0])
    entry = t.grid[0]
    assert trigger_met(bars, entry, 100.0, "above", 1) is False
    assert trigger_met(bars, entry, 100.0, "above", 3) is True
    # the other direction, on the same path
    assert trigger_met(bars, entry, 99.0, "below", 1) is True
    assert trigger_met(bars, entry, 97.0, "below", 3) is False


def test_e2_met_is_inclusive_at_the_level():
    """"holds 34" is met by a close of exactly 34 — the opposite convention
    from E1's strict breach, and deliberately so."""
    t = _trade("TEST:2025-02-21:100:C +1", 3.0, [3.0] * 4)
    bars = _bars(t, [100.0, 100.0, 100.0, 100.0])
    assert trigger_met(bars, t.grid[0], 100.0, "above", 1) is True
    assert trigger_met(bars, t.grid[0], 100.0, "below", 1) is True


def test_e2_counts_sessions_on_the_bar_series_not_the_calendar():
    """A holiday inside the window does not consume one of the N sessions.

    The grid is weekday-based and option marks carry forward across a closed
    day, which is the trap `underlying.entry_day` exists for; the same reasoning
    applies to the trigger window, so the count is taken on the bars.
    """
    t = _trade("TEST:2025-02-21:100:C +1", 3.0, [3.0] * 6)
    bars = _bars(t, [98.0, 99.0, 101.0, 102.0, 103.0, 104.0])
    del bars[t.grid[1]]                       # session 2 is a market holiday
    # 101 is now the SECOND traded session, so N=2 reaches it and N=1 does not.
    assert trigger_met(bars, t.grid[0], 100.0, "above", 1) is False
    assert trigger_met(bars, t.grid[0], 100.0, "above", 2) is True


def test_trigger_direction_reads_the_nearest_word_before_the_level():
    assert trigger_direction("ETHA holds 34 on a daily close after the snapshot",
                             34.0) == "above"
    assert trigger_direction("no entry unless it closes below 290.", 290.0) == "below"
    assert trigger_direction("only if NVDA reclaims 122.50 intraday", 122.5) == "above"
    # a clause carrying both words: the one attached to THIS level wins
    assert trigger_direction("above 34, skip if it opens below 33", 33.0) == "below"
    # no direction word at all -> the conditional-unparseable bucket
    assert trigger_direction("watch 145 into the print", 145.0) is None
    assert trigger_direction("", 100.0) is None
    assert trigger_direction("closes above 100", None) is None


# ── E3: horizon mapping and the survival control's bucketing ───────────────

def test_horizon_maps_to_the_frozen_bucket_vocabulary():
    assert horizon_of({"horizon": "60.0"}) == 60
    assert horizon_of({"horizon": "720"}) == 720
    assert horizon_of({"horizon": ""}) is None
    assert horizon_of({"horizon": "90"}) is None      # not in the frozen vocabulary
    assert horizon_of({"horizon": "swing"}) is None


@pytest.mark.parametrize("horizon,dte", [(14, 45), (60, 45), (180, 60), (720, 30)])
def test_horizon_tef_lands_the_frozen_harness_on_the_exact_day(horizon, dte):
    """`replay` computes `int(dte_entry * tef)`; the mapping must invert it exactly."""
    assert int(dte * horizon_tef(horizon, dte)) == horizon


def test_e3_time_exit_lands_on_the_horizon_through_the_frozen_engine():
    """End-to-end: a 14-day horizon exits on the first grid day 14+ calendar days out."""
    t = _trade("TEST:2025-02-21:100:C +1", 2.0, [2.0] * 40)
    out = replay(t, pt=0.90, sl=0.75, tef=horizon_tef(14, t.dte_entry))
    assert out["exit_reason"] == "time_exit"
    assert (t.grid[out["days_held"] - 1] - SIGNAL).days >= 14
    assert (t.grid[out["days_held"] - 2] - SIGNAL).days < 14


def test_survival_control_bucketing_by_hold_length_tercile():
    """Terciles are computed on the arm population and are inclusive at the top."""
    holds = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    t1, t2 = terciles(holds)
    assert (t1, t2) == (pytest.approx(11 / 3), pytest.approx(19 / 3))
    assert [tercile_label(h, t1, t2) for h in holds] == \
        ["T1", "T1", "T1", "T2", "T2", "T2", "T3", "T3", "T3"]
    # a hold exactly on a boundary lands in the LOWER bucket, as the header reads
    assert tercile_label(t1, t1, t2) == "T1"
    assert tercile_label(t2, t1, t2) == "T2"


# ── criterion 2: the AFFECTED-dates LOO median on a zero-inflated delta ────

def _paired(deltas: dict[str, float]) -> list[dict]:
    """One paired row per date, `a - b` equal to that date's delta."""
    return [dict(date=d, a=v, b=0.0, source="real", bar_source="ohlc")
            for d, v in deltas.items()]


def test_loo_fold_gains_match_the_protocol_aggregate():
    """One formula, two call sites — the study asserts this at run time too."""
    rows = _paired({f"2025-01-{i:02d}": (i % 5) - 2 for i in range(1, 21)})
    folds = loo_fold_gains(rows)
    _mean, _share, loo_min, n_folds = P.loo_by_date(
        rows, lambda r: r["a"], lambda r: r["b"])
    assert n_folds == len(folds) == 20
    assert min(folds.values()) == pytest.approx(loo_min)


def test_affected_dates_median_bites_where_the_whole_population_median_cannot():
    """The 2026-07-22 correction, demonstrated on a zero-inflated delta.

    16 of 20 dates are UNAFFECTED and contribute an exact zero. Leaving one of
    them out barely moves the mean, so the whole-population LOO median just
    reproduces the (positive) pooled sign and is untrippable. Restricted to the
    folds whose left-out date is AFFECTED, the median is NEGATIVE — the gain
    lives in one date, which is exactly what criterion 2 is there to catch.
    """
    deltas = {f"2025-01-{i:02d}": 0.0 for i in range(1, 17)}
    deltas["2025-01-17"] = +2.0
    deltas["2025-01-18"] = +2.0
    deltas["2025-01-19"] = +2.0
    deltas["2025-01-20"] = -5.5
    rows = _paired(deltas)
    affected = {d for d, v in deltas.items() if v != 0.0}

    folds = loo_fold_gains(rows)
    whole = statistics.median(folds.values())
    aff = statistics.median([g for d, g in folds.items() if d in affected])

    assert whole > 0            # untrippable on the zero-inflated population
    assert aff < 0              # the corrected gate refuses the cell
    assert len([d for d in folds if d in affected]) == 4


def test_changed_is_the_registered_identity_triple():
    base = dict(exit_reason="stop_loss", days_held=4, pnl_pct=-0.75)
    assert not changed(dict(base), dict(base))
    assert changed(dict(base, days_held=3), base)
    assert changed(dict(base, exit_reason="text_stop"), base)
    assert changed(dict(base, pnl_pct=-0.7500000001), base)


def test_grid_alignment_helper_is_self_consistent():
    """A guard on the fixtures themselves: marks and grid must be the same length,
    which is what `Trade.__init__` asserts on the real book."""
    t = _trade("TEST:2025-02-21:100:C +1", 3.0, [3.0, 3.0])
    assert len(t.marks) == len(t.grid)
    assert t.grid[0] == SIGNAL + timedelta(days=1)
