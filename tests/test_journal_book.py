"""
Tests for open-book reassembly — turning the broker's flat leg list into positions.

The interesting cases are all about NOT lying: a multi-expiry holding must be
split rather than fused into a fictional structure, an unbalanced group must not
claim a size it does not have, and a position with no spot price must drop out
of the totals instead of being valued at zero.
"""

from __future__ import annotations

from datetime import date

import pytest

from scripts.journal.lib import book
from scripts.journal.config import DELTA_SOURCE_IBKR, Greeks

AS_OF = date(2026, 8, 14)


def _raw(positions, contracts, prices=None):
    return {
        "schema_version": 1, "pulled_at_utc": "x", "trade_date": "2026-08-14",
        "source": "test", "trades": [], "positions": positions,
        "contracts": contracts, "underlying_prices": prices or {},
    }


def _c(symbol, strike, expiry, right="C"):
    return {"symbol": symbol, "sec_type": "OPT", "strike": strike,
            "expiry": expiry, "right": right}


def _g(conid, delta):
    return Greeks(conid, delta=delta, source=DELTA_SOURCE_IBKR)


def test_a_vertical_reassembles_into_one_position():
    raw = _raw(
        [{"conid": 1, "position": 1, "avg_cost": 700.0},
         {"conid": 2, "position": -1, "avg_cost": 300.0}],
        {"1": _c("NVDA", 170.0, "2026-10-16"), "2": _c("NVDA", 180.0, "2026-10-16")},
        {"NVDA": 175.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6), 2: _g(2, 0.35)}, as_of=AS_OF)
    assert len(pos) == 1
    assert pos[0].structure == "bull_call_spread"
    assert pos[0].contracts == 1
    assert pos[0].position_delta == pytest.approx(0.25)


def test_a_calendar_is_split_across_expiries_and_the_split_is_reported():
    """Splitting is the honest choice; fusing unrelated legs would misreport both."""
    raw = _raw(
        [{"conid": 1, "position": 1, "avg_cost": 700.0},
         {"conid": 2, "position": -1, "avg_cost": 300.0}],
        {"1": _c("NVDA", 170.0, "2026-10-16"), "2": _c("NVDA", 170.0, "2026-12-18")},
        {"NVDA": 175.0})
    pos, notes = book.open_positions(raw, {1: _g(1, 0.6), 2: _g(2, 0.5)}, as_of=AS_OF)
    assert len(pos) == 2
    assert any("2 expiries" in n for n in notes)


def test_splitting_a_calendar_leaves_net_delta_notional_unchanged():
    """The claim the note makes must actually hold: delta-notional is additive."""
    contracts = {"1": _c("NVDA", 170.0, "2026-10-16"), "2": _c("NVDA", 170.0, "2026-12-18")}
    raw = _raw([{"conid": 1, "position": 1, "avg_cost": 700.0},
                {"conid": 2, "position": -1, "avg_cost": 300.0}],
               contracts, {"NVDA": 175.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6), 2: _g(2, 0.5)}, as_of=AS_OF)
    total = sum(p.delta_notional for p in pos)
    assert total == pytest.approx((0.6 - 0.5) * 100 * 175.0)


def test_an_unbalanced_group_reports_the_smaller_count():
    raw = _raw(
        [{"conid": 1, "position": 3, "avg_cost": 700.0},
         {"conid": 2, "position": -1, "avg_cost": 300.0}],
        {"1": _c("NVDA", 170.0, "2026-10-16"), "2": _c("NVDA", 180.0, "2026-10-16")},
        {"NVDA": 175.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6), 2: _g(2, 0.35)}, as_of=AS_OF)
    assert pos[0].contracts == 1


def test_a_zero_quantity_row_is_not_a_position():
    raw = _raw([{"conid": 1, "position": 0, "avg_cost": 700.0}],
               {"1": _c("NVDA", 170.0, "2026-10-16")}, {"NVDA": 175.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6)}, as_of=AS_OF)
    assert pos == []


def test_a_symbol_with_no_spot_is_excluded_and_named():
    raw = _raw([{"conid": 1, "position": 1, "avg_cost": 700.0}],
               {"1": _c("AMD", 170.0, "2026-10-16")}, {})
    pos, notes = book.open_positions(raw, {1: _g(1, 0.6)}, as_of=AS_OF)
    assert pos[0].priced is False
    assert any("No spot price for AMD" in n for n in notes)
    assert any("NOT counted as zero" in n for n in notes)


def test_a_position_with_no_delta_is_unpriced_not_zero():
    raw = _raw([{"conid": 1, "position": 1, "avg_cost": 700.0}],
               {"1": _c("AMD", 170.0, "2026-10-16")}, {"AMD": 175.0})
    pos, _ = book.open_positions(raw, {1: Greeks(1)}, as_of=AS_OF)
    assert pos[0].priced is False
    assert pos[0].delta_notional is None


def test_dte_is_measured_from_the_as_of_date():
    raw = _raw([{"conid": 1, "position": 1, "avg_cost": 700.0}],
               {"1": _c("NVDA", 170.0, "2026-10-16")}, {"NVDA": 175.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6)}, as_of=AS_OF)
    assert pos[0].dte == pytest.approx((date(2026, 10, 16) - AS_OF).days)


def test_a_leg_without_strike_or_expiry_is_excluded_rather_than_guessed():
    raw = _raw([{"conid": 1, "position": 1, "avg_cost": 700.0}],
               {"1": {"symbol": "NVDA", "sec_type": "OPT", "strike": None,
                      "expiry": None, "right": "C"}}, {"NVDA": 175.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6)}, as_of=AS_OF)
    assert pos == []


def test_positions_on_different_symbols_never_merge():
    raw = _raw(
        [{"conid": 1, "position": 1, "avg_cost": 700.0},
         {"conid": 2, "position": -1, "avg_cost": 300.0}],
        {"1": _c("NVDA", 170.0, "2026-10-16"), "2": _c("AMD", 170.0, "2026-10-16")},
        {"NVDA": 175.0, "AMD": 160.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6), 2: _g(2, 0.5)}, as_of=AS_OF)
    assert {p.ticker for p in pos} == {"NVDA", "AMD"}


# --------------------------------------------------------------------------
# §5 entry_date grouping — feeds mark_position()'s exit-by projection
# --------------------------------------------------------------------------
def test_two_legs_sharing_an_entry_date_are_not_flagged_mixed():
    raw = _raw(
        [{"conid": 1, "position": 1, "avg_cost": 700.0, "entry_date": "2026-08-01"},
         {"conid": 2, "position": -1, "avg_cost": 300.0, "entry_date": "2026-08-01"}],
        {"1": _c("NVDA", 170.0, "2026-10-16"), "2": _c("NVDA", 180.0, "2026-10-16")},
        {"NVDA": 175.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6), 2: _g(2, 0.35)}, as_of=AS_OF)
    assert pos[0].entry_date == date(2026, 8, 1)
    assert pos[0].entry_date_mixed is False


def test_two_legs_opened_on_different_dates_use_the_earliest_and_flag_mixed():
    raw = _raw(
        [{"conid": 1, "position": 1, "avg_cost": 700.0, "entry_date": "2026-08-05"},
         {"conid": 2, "position": -1, "avg_cost": 300.0, "entry_date": "2026-08-01"}],
        {"1": _c("NVDA", 170.0, "2026-10-16"), "2": _c("NVDA", 180.0, "2026-10-16")},
        {"NVDA": 175.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6), 2: _g(2, 0.35)}, as_of=AS_OF)
    assert pos[0].entry_date == date(2026, 8, 1)      # the EARLIEST leg
    assert pos[0].entry_date_mixed is True


def test_one_leg_with_no_entry_date_makes_the_whole_group_unknown_not_mixed():
    """All-or-nothing like the delta: a spread dated off one leg is a wrong
    date, not a partial one, and it is not "mixed" — mixed means BOTH dates
    are known and disagree."""
    raw = _raw(
        [{"conid": 1, "position": 1, "avg_cost": 700.0, "entry_date": "2026-08-01"},
         {"conid": 2, "position": -1, "avg_cost": 300.0}],  # no entry_date at all
        {"1": _c("NVDA", 170.0, "2026-10-16"), "2": _c("NVDA", 180.0, "2026-10-16")},
        {"NVDA": 175.0})
    pos, _ = book.open_positions(raw, {1: _g(1, 0.6), 2: _g(2, 0.35)}, as_of=AS_OF)
    assert pos[0].entry_date is None
    assert pos[0].entry_date_mixed is False
