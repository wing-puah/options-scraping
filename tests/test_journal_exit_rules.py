"""
Tests for scripts/journal/lib/exit_rules.py — the §5 time-exit rule expressed
as an absolute calendar date.

Pure logic, no I/O beyond the yaml config file `time_exit_fraction` reads, so
everything here runs offline. The recurring theme is the same missing/zero
discipline the rest of the journal enforces: every function returns `None`
on a missing/unusable input rather than guessing, and `is_debit` returns
`None` (not `False`) for a structure it does not recognise.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from scripts.journal.lib import exit_rules
from scripts.live_loop.mapping import SIDE


# --------------------------------------------------------------------------
# exit_by_date()
# --------------------------------------------------------------------------
def test_exit_by_date_hand_table_60_day_span_at_075():
    """entry 2026-01-05, expiry 2026-03-06 is a 60-calendar-day span;
    int(60 * 0.75) = 45 calendar days from entry lands on 2026-02-19."""
    got = exit_rules.exit_by_date(date(2026, 1, 5), date(2026, 3, 6), 0.75)
    assert got == date(2026, 2, 19)


def test_exit_by_date_floors_a_short_span_to_the_entry_date():
    """A 1-day span at fraction 0.75: int(1 * 0.75) == 0, so the deadline is
    the entry date itself, never negative and never rounded up."""
    entry = date(2026, 6, 1)
    got = exit_rules.exit_by_date(entry, date(2026, 6, 2), 0.75)
    assert got == entry


def test_exit_by_date_is_none_for_a_same_day_span():
    got = exit_rules.exit_by_date(date(2026, 6, 1), date(2026, 6, 1), 0.75)
    assert got is None


def test_exit_by_date_is_none_for_a_negative_span():
    """Expiry before entry — a wrong-order pull, never a guessable deadline."""
    got = exit_rules.exit_by_date(date(2026, 6, 2), date(2026, 6, 1), 0.75)
    assert got is None


@pytest.mark.parametrize("entry,expiry,fraction", [
    (None, date(2026, 3, 6), 0.75),
    (date(2026, 1, 5), None, 0.75),
    (date(2026, 1, 5), date(2026, 3, 6), None),
    (None, None, None),
])
def test_exit_by_date_is_none_on_any_missing_input(entry, expiry, fraction):
    assert exit_rules.exit_by_date(entry, expiry, fraction) is None


# --------------------------------------------------------------------------
# projected_exit_by()
# --------------------------------------------------------------------------
def test_projected_exit_by_ranges_the_dte_span():
    entry = date(2026, 1, 5)
    got = exit_rules.projected_exit_by(entry, 45.0, 60.0, 0.75)
    assert got == (entry + timedelta(days=int(45 * 0.75)),
                   entry + timedelta(days=int(60 * 0.75)))


def test_projected_exit_by_scalar_dte_collapses_to_one_date():
    entry = date(2026, 1, 5)
    got = exit_rules.projected_exit_by(entry, 60.0, 60.0, 0.75)
    assert got[0] == got[1]


def test_projected_exit_by_sorts_a_swapped_lo_hi():
    entry = date(2026, 1, 5)
    swapped = exit_rules.projected_exit_by(entry, 60.0, 45.0, 0.75)
    ordered = exit_rules.projected_exit_by(entry, 45.0, 60.0, 0.75)
    assert swapped == ordered
    assert swapped[0] <= swapped[1]


@pytest.mark.parametrize("entry,lo,hi,fraction", [
    (None, 45.0, 60.0, 0.75),
    (date(2026, 1, 5), None, 60.0, 0.75),
    (date(2026, 1, 5), 45.0, None, 0.75),
    (date(2026, 1, 5), 45.0, 60.0, None),
])
def test_projected_exit_by_is_none_on_any_missing_input(entry, lo, hi, fraction):
    assert exit_rules.projected_exit_by(entry, lo, hi, fraction) is None


def test_projected_exit_by_is_none_when_hi_is_zero_or_negative():
    entry = date(2026, 1, 5)
    assert exit_rules.projected_exit_by(entry, -10.0, 0.0, 0.75) is None
    assert exit_rules.projected_exit_by(entry, -20.0, -10.0, 0.75) is None


# --------------------------------------------------------------------------
# time_exit_fraction() — lru_cached on the path STRING, so every case below
# writes to its OWN tmp file (a shared filename would read the first case's
# cached answer forever).
# --------------------------------------------------------------------------
def test_time_exit_fraction_reads_the_configured_value(tmp_path):
    p = tmp_path / "a.yml"
    p.write_text("simulation:\n  time_exit_dte_fraction: 0.75\n", encoding="utf-8")
    assert exit_rules.time_exit_fraction(p) == 0.75


def test_time_exit_fraction_is_none_when_explicitly_null(tmp_path):
    p = tmp_path / "b.yml"
    p.write_text("simulation:\n  time_exit_dte_fraction: null\n", encoding="utf-8")
    assert exit_rules.time_exit_fraction(p) is None


def test_time_exit_fraction_is_none_when_the_key_is_absent(tmp_path):
    p = tmp_path / "c.yml"
    p.write_text("simulation:\n  other_setting: 1\n", encoding="utf-8")
    assert exit_rules.time_exit_fraction(p) is None


def test_time_exit_fraction_is_none_when_the_simulation_block_is_absent(tmp_path):
    p = tmp_path / "d.yml"
    p.write_text("unrelated: true\n", encoding="utf-8")
    assert exit_rules.time_exit_fraction(p) is None


def test_time_exit_fraction_is_none_for_an_unreadable_path(tmp_path):
    p = tmp_path / "does-not-exist.yml"
    assert exit_rules.time_exit_fraction(p) is None


# --------------------------------------------------------------------------
# is_debit() — every key in the shared SIDE table, plus the "cannot say" cases
# --------------------------------------------------------------------------
@pytest.mark.parametrize("structure", [s for s, side in SIDE.items() if side == "debit"])
def test_is_debit_true_for_every_debit_structure(structure):
    assert exit_rules.is_debit(structure) is True


@pytest.mark.parametrize("structure", [s for s, side in SIDE.items() if side == "credit"])
def test_is_debit_false_for_every_credit_structure(structure):
    assert exit_rules.is_debit(structure) is False


@pytest.mark.parametrize("structure", ["unclassified", None, ""])
def test_is_debit_is_none_for_an_unrecognised_structure(structure):
    assert exit_rules.is_debit(structure) is None


# classify_structure's single-leg labels are not SIDE keys, but their side is
# unambiguous from the label prefix alone — a held long single is a debit, a
# short one is not, with or without the "(overlay)" suffix a financing leg
# carries.
@pytest.mark.parametrize("structure", [
    "single long put",
    "single long call",
    "single long put (overlay)",
])
def test_is_debit_true_for_a_single_long_label(structure):
    assert exit_rules.is_debit(structure) is True


@pytest.mark.parametrize("structure", [
    "single short call",
    "single short put",
    "single short call (overlay)",
])
def test_is_debit_false_for_a_single_short_label(structure):
    assert exit_rules.is_debit(structure) is False
