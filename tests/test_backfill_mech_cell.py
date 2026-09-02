"""Unit tests for the mech_cell backfill planner.

Only `plan_tab` is exercised — it is deliberately pure (header + rows in, column
values out), so the whole decision table is testable without Sheets.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backfill_mech_cell import _norm_date, plan_tab  # noqa: E402

HEADER = ["date", "ticker", "play", "mech_cell"]


@pytest.fixture
def table(tmp_path):
    """SPY/VIX table labelling 2024-03-20 BEAR_HE, ending there.

    Deep drawdown + VIX 25 => BEAR + H-VOL. Copied from tests/test_mech_regime.py
    so both suites move together if the frozen spec ever changes.
    """
    rows = ["date,spy_close,vix_close"]
    for i in range(60):
        day = f"2024-01-{i + 1:02d}" if i < 31 else f"2024-02-{i - 30:02d}"
        rows.append(f"{day},500,15")
    rows.append("2024-03-20,400,25")
    p = tmp_path / "spy_vix.csv"
    p.write_text("\n".join(rows) + "\n")
    return p


def test_blank_and_no_data_cells_are_filled(table):
    rows = [
        ["2024-03-20", "NVDA", "buy calls", ""],          # pre-column row
        ["2024-03-20", "AMD", "buy calls", "NO_DATA"],    # table was stale then
    ]
    values, stats = plan_tab(HEADER, rows, table, force=False)
    assert values == ["BEAR_HE", "BEAR_HE"]
    assert stats["filled"] == 2
    assert stats["drift"] == 0


def test_matching_label_is_left_alone(table):
    values, stats = plan_tab(HEADER, [["2024-03-20", "NVDA", "p", "BEAR_HE"]],
                             table, force=False)
    assert values == ["BEAR_HE"]
    assert stats["unchanged"] == 1


def test_drift_is_kept_unless_forced(table):
    rows = [["2024-03-20", "NVDA", "p", "LVOL"]]
    values, stats = plan_tab(HEADER, rows, table, force=False)
    assert values == ["LVOL"], "a stored label must never be silently replaced"
    assert stats["drift"] == 1 and stats["overwritten"] == 0

    values, stats = plan_tab(HEADER, rows, table, force=True)
    assert values == ["BEAR_HE"]
    assert stats["overwritten"] == 1


def test_date_past_the_table_end_stays_no_data(table):
    values, stats = plan_tab(HEADER, [["2026-01-02", "NVDA", "p", ""]],
                             table, force=False)
    assert values == ["NO_DATA"], "never label off a stale close"
    assert stats["no_data"] == 1


def test_row_with_an_unparseable_date_is_not_labelled(table):
    values, stats = plan_tab(HEADER, [["", "NVDA", "p", ""],
                                      ["last week", "AMD", "p", "BEAR_HE"]],
                             table, force=False)
    assert values == ["NO_DATA", "BEAR_HE"]
    assert stats["no_date"] == 2


def test_tab_without_the_column_yet_is_planned_from_the_date_alone(table):
    header = ["date", "ticker", "play"]
    values, stats = plan_tab(header, [["2024-03-20", "NVDA", "p"]], table, force=False)
    assert values == ["BEAR_HE"]
    assert stats["filled"] == 1


def test_short_rows_do_not_crash(table):
    """Sheets returns ragged rows — trailing empties are simply absent."""
    values, _ = plan_tab(HEADER, [["2024-03-20", "NVDA"]], table, force=False)
    assert values == ["BEAR_HE"]


def test_norm_date_accepts_iso_and_us_and_rejects_the_rest():
    assert _norm_date("2026-04-21") == "2026-04-21"
    assert _norm_date(" 2026-04-21 ") == "2026-04-21"
    assert _norm_date("4/21/2026") == "2026-04-21"
    assert _norm_date("21/04/2026") is None   # ambiguous — never guessed
    assert _norm_date("") is None


def test_no_data_never_contradicts_a_stored_label(table):
    """A hole in the feed keeps the stored label and is not drift.

    The table ends 2024-03-20, so a later date cannot be answered. Failing the
    job (exit 2) over that would make one missing ^VIX close a permanent red
    workflow — see lib/mech_regime.cell_for_date.
    """
    rows = [["2026-01-02", "NVDA", "p", "LVOL"]]
    values, stats = plan_tab(HEADER, rows, table, force=False)
    assert values == ["LVOL"], "a label written when the table could answer wins"
    assert stats["drift"] == 0 and stats["held"] == 1
    assert stats["filled"] == 0 and stats["overwritten"] == 0


def test_no_data_still_fills_a_blank(table):
    """Holding a concrete label must not stop blanks getting the sentinel."""
    values, stats = plan_tab(HEADER, [["2026-01-02", "NVDA", "p", ""]],
                             table, force=False)
    assert values == ["NO_DATA"]
    assert stats["filled"] == 1 and stats["held"] == 0
