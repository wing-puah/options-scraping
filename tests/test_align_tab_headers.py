"""Unit tests for the header-alignment planner (pure; no Sheets)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from align_tab_headers import plan  # noqa: E402

TARGET = ["date", "ticker", "iv_pct", "score_total", "mech_cell"]


def test_matching_header_needs_nothing():
    header = list(TARGET)
    assert plan(header, [["2026-01-02", "NVDA", "5", "70", "LVOL"]], TARGET) == ({}, [])


def test_column_present_but_misplaced_is_relocated():
    header = ["date", "ticker", "score_total", "mech_cell"]
    rows = [["2026-01-02", "NVDA", "70", "LVOL"],
            ["2026-01-03", "AMD", "60", "BEAR_HE"]]
    relocations, blockers = plan(header, rows, TARGET)
    assert blockers == []
    assert relocations == {"score_total": ["70", "60"], "mech_cell": ["LVOL", "BEAR_HE"]}


def test_empty_drifted_columns_are_not_relocated():
    header = ["date", "ticker", "score_total", "mech_cell"]
    rows = [["2026-01-02", "NVDA", "", "LVOL"]]
    relocations, _ = plan(header, rows, TARGET)
    assert "score_total" not in relocations
    assert relocations == {"mech_cell": ["LVOL"]}


def test_unknown_column_holding_data_blocks_the_repair():
    header = ["date", "ticker", "ConvictionScore"]
    rows = [["2026-01-02", "NVDA", "8"]]
    relocations, blockers = plan(header, rows, TARGET)
    assert relocations == {}
    assert len(blockers) == 1 and "ConvictionScore" in blockers[0]


def test_unknown_column_with_no_data_does_not_block():
    header = ["date", "ticker", "ConvictionScore"]
    _, blockers = plan(header, [["2026-01-02", "NVDA", ""]], TARGET)
    assert blockers == []


def test_ragged_rows_are_treated_as_empty_cells():
    header = ["date", "ticker", "mech_cell"]
    relocations, blockers = plan(header, [["2026-01-02", "NVDA"]], TARGET)
    assert (relocations, blockers) == ({}, [])
