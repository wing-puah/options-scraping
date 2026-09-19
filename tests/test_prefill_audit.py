"""The exit-after-fill audit — scripts/backtest_study/lib/prefill_audit.py.

A row whose grid starts before its FILL could, until the robustness fold's B2
landed on 2026-09-08, book an exit on a day the position did not exist. This
module finds those rows in an already-stored book. Like `basis_audit`, it
REPORTS and never gates: nothing here may raise, drop a row, or change a
population — a study that re-replays from marks is unaffected either way, and
one that pools stored outcomes needs the flag, not a silently smaller book.

What it must REFUSE to flag matters as much as what it flags. The fill day is
read off `dte_entry`, never re-derived from the option cache, because the cache
has grown since these rows were priced; a row that cannot answer is `absent`,
never a conflict.
"""
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.lib import prefill_audit as pa  # noqa: E402

SIGNAL = date(2026, 6, 1)               # Monday
EXPIRY = date(2026, 7, 17)


def _grid(n=10):
    out, d = [], SIGNAL
    while len(out) < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out


class _FakeTrade:
    """Only what the audit touches: `legs`, `dte_entry`, `grid`."""

    def __init__(self, entry_day=None, dte=None, legs=None, grid=None):
        self.grid = _grid() if grid is None else grid
        self.legs = [Leg(1, "AAA", EXPIRY, 100.0, "Call")] if legs is None else legs
        if dte is None and entry_day is not None:
            dte = (EXPIRY - entry_day).days
        self.dte_entry = dte


# ── entry_index: the fill day is READ, not re-derived ────────────────────────

def test_entry_index_is_the_grid_position_of_the_recorded_fill_day():
    g = _grid()
    for i, day in enumerate(g[:5], start=1):
        assert pa.entry_index(_FakeTrade(entry_day=day)) == i


def test_entry_index_measures_from_the_anchor_leg_not_the_short_one():
    """`dte_entry` is stamped on the ANCHOR contract (`legs[0]`), so a position
    whose legs have different expiries must measure from the anchor's."""
    far = Leg(-1, "AAA", date(2026, 9, 18), 90.0, "Put")
    anchor = Leg(1, "AAA", EXPIRY, 100.0, "Call")
    day = _grid()[2]
    dte = (EXPIRY - day).days
    assert pa.entry_index(_FakeTrade(dte=dte, legs=[anchor, far])) == 3
    # Anchor first is what is measured; reversing the pair changes the answer,
    # which is why the order is load-bearing rather than incidental.
    assert pa.entry_index(_FakeTrade(dte=dte, legs=[far, anchor])) != 3


@pytest.mark.parametrize("trade", [
    _FakeTrade(legs=[]),                                   # no legs
    _FakeTrade(dte=None),                                  # no dte_entry
    _FakeTrade(dte="n/a"),                                 # unparseable
    _FakeTrade(dte=(EXPIRY - date(2026, 6, 6)).days),      # a Saturday: not on the grid
    _FakeTrade(grid=[]),                                   # no grid
])
def test_entry_index_is_none_when_the_row_cannot_answer(trade):
    assert pa.entry_index(trade) is None


# ── audit_trade ──────────────────────────────────────────────────────────────

def test_an_exit_on_the_fill_day_is_ok():
    g = _grid()
    t = _FakeTrade(entry_day=g[2])          # entry_index 3
    assert pa.audit_trade(t, 3) == "ok"


def test_an_exit_after_the_fill_day_is_ok():
    g = _grid()
    assert pa.audit_trade(_FakeTrade(entry_day=g[2]), 7) == "ok"


def test_an_exit_before_the_fill_day_is_the_defect():
    """The TLT 2025-04-01 shape: filled on grid day 3, exited on day 2."""
    g = _grid()
    assert pa.audit_trade(_FakeTrade(entry_day=g[2]), 2) == "pre_entry_exit"
    assert pa.audit_trade(_FakeTrade(entry_day=g[2]), 1) == "pre_entry_exit"


def test_a_row_filled_on_day_one_can_never_be_flagged():
    """The common case — the fill IS grid day 1, so no exit can precede it."""
    g = _grid()
    t = _FakeTrade(entry_day=g[0])
    for dh in range(1, 9):
        assert pa.audit_trade(t, dh) == "ok"


@pytest.mark.parametrize("days_held", [None, "", "n/a"])
def test_a_row_with_no_exit_index_is_absent_not_a_conflict(days_held):
    """An `underlying_trend` proxy row prices nothing and exits nowhere. It has
    no claim to check, and calling that a conflict would flag the whole tier."""
    g = _grid()
    assert pa.audit_trade(_FakeTrade(entry_day=g[2]), days_held) == "absent"


def test_an_unanswerable_fill_day_is_absent_even_with_an_exit():
    assert pa.audit_trade(_FakeTrade(dte=None), 1) == "absent"


def test_days_held_is_read_as_an_int_from_a_float_round_trip():
    """The book coerces through `_to_float`, so the audit receives 3.0, not 3."""
    g = _grid()
    assert pa.audit_trade(_FakeTrade(entry_day=g[2]), 3.0) == "ok"
    assert pa.audit_trade(_FakeTrade(entry_day=g[2]), 2.0) == "pre_entry_exit"


# ── audit() over records, and the header line ────────────────────────────────

def test_audit_tallies_and_returns_only_the_offenders():
    g = _grid()
    recs = [
        {"t": _FakeTrade(entry_day=g[0]), "days_held": 4},   # ok
        {"t": _FakeTrade(entry_day=g[2]), "days_held": 2},   # pre_entry_exit
        {"t": _FakeTrade(dte=None), "days_held": 1},         # absent
    ]
    tally, offenders = pa.audit(recs)
    assert tally == Counter({"ok": 1, "pre_entry_exit": 1, "absent": 1})
    # `absent` rows are unanswerable, not wrong — they never reach the list.
    assert [o["prefill_verdict"] for o in offenders] == ["pre_entry_exit"]


def test_audit_never_raises_on_a_record_missing_everything():
    tally, offenders = pa.audit([{}])
    assert tally == Counter({"absent": 1})
    assert offenders == []


def test_format_tally_names_the_conflict_bucket_at_zero():
    line = pa.format_tally(Counter({"ok": 1311, "pre_entry_exit": 14}), 1325)
    assert "pre_entry_exit" in line and "1311 ok" in line and "of 1325" in line
    # A clean book still prints the bucket, so a check that stops running is
    # visible as a missing line rather than as silence.
    assert "0 pre_entry_exit" in pa.format_tally(Counter({"ok": 5}), 5)


def test_trusted_is_only_ok():
    assert pa.TRUSTED == {"ok"}


def test_a_fill_at_or_before_the_grid_start_is_position_one():
    """`entry_timing: signal_eod` fills on the SIGNAL day, and the grid starts
    the weekday after it. The position exists for every grid day, so the row is
    `ok` for any exit — reporting `absent` would blank the audit on a whole
    timing convention rather than clear it."""
    g = _grid()
    for day in (SIGNAL, SIGNAL - timedelta(days=30)):
        t = _FakeTrade(dte=(EXPIRY - day).days)
        assert pa.entry_index(t) == 1
        assert pa.audit_trade(t, 1) == "ok"
