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


# ── Per-tab schemas (2026-09-02) ─────────────────────────────────────────────────
# The script targeted ROW_COLUMNS for every tab, so the two backtest tabs were
# never checked against their own writers' key order. That gap is how
# `exit_basis` reached the v3 export as a nameless 47th column.

from align_tab_headers import BACKTEST_TABS, DEFAULT_TABS, schema_for  # noqa: E402
from scripts.analysis_pipeline import config as ap_config  # noqa: E402
from scripts.backtest.core import _KEY_ORDER  # noqa: E402
from scripts.backtest.proxy import _PROXY_KEY_ORDER  # noqa: E402


def test_backtest_tabs_target_their_own_writer_key_order():
    assert schema_for("BacktestResults") == list(_KEY_ORDER)
    assert schema_for("BacktestProxy") == list(_PROXY_KEY_ORDER)


def test_versioned_backtest_renames_keep_their_schema():
    # `v3_BacktestResults` is a prompt-version rename, not a different column set.
    assert schema_for("v3_BacktestResults") == list(_KEY_ORDER)
    assert schema_for("v2_BacktestProxy") == list(_PROXY_KEY_ORDER)


def test_analysis_tabs_still_target_row_columns():
    assert schema_for("AnalysisClaude") == list(ap_config.ROW_COLUMNS)
    assert schema_for("v3_AnalysisClaude") == list(ap_config.ROW_COLUMNS)


def test_default_sweep_covers_the_backtest_tabs():
    # The whole point of the fix: a bare --dry-run must check them.
    assert set(BACKTEST_TABS) <= set(DEFAULT_TABS)


def test_exit_basis_is_in_both_backtest_schemas():
    # The column the gap dropped. Pinned here as well as in test_mech_regime.py
    # so widening either key order without fixing the tab header is caught.
    assert "exit_basis" in schema_for("BacktestResults")
    assert "exit_basis" in schema_for("BacktestProxy")
