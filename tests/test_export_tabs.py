"""`scripts/export_tabs.py` — the filename contract and the era grouping.

The claim worth pinning is not "it downloads a CSV" (that is the Sheets export
endpoint's job) but that what it WRITES is what the study tier READS: a study
resolves its inputs through `era.resolve_paths`, and a filename this script
invents independently would silently produce a file no study ever opens.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "export_tabs", ROOT / "scripts" / "export_tabs.py")
export_tabs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export_tabs)

from scripts.backtest_study.lib import era  # noqa: E402


def test_default_tabs_are_the_era_contract():
    """The bare pull must fetch exactly the exports a bare study run reads."""
    assert set(export_tabs.DEFAULT_TABS) == set(era.EXPORTS.values())


@pytest.mark.parametrize("key,tab", sorted(era.EXPORTS.items()))
def test_dest_matches_what_studies_open(key, tab):
    """Every default tab lands on the path `era.resolve_paths` resolves."""
    assert export_tabs._dest_for(tab, era.EVAL_DIR) == era.resolve_paths(era.CURRENT)[key]


@pytest.mark.parametrize("key,tab", sorted(era.EXPORTS.items()))
def test_prefixed_dest_matches_a_past_era(key, tab):
    """`--tabs v3_<Tab>` lands where `--era v3` looks for it."""
    dest = export_tabs._dest_for(f"v3_{tab}", era.EVAL_DIR)
    assert dest == era.resolve_paths("v3")[key]


def test_export_key_and_prefix():
    assert export_tabs._export_key("BacktestResults") == "results"
    assert export_tabs._export_key("v3_BacktestResults") == "results"
    assert export_tabs._export_key("BaselineDaily") is None  # not versioned

    assert export_tabs._prefix_of("BacktestResults") == ""
    assert export_tabs._prefix_of("v3_BacktestResults") == "v3_"
    assert export_tabs._prefix_of("BaselineDaily") == ""


def test_row_and_date_counts(tmp_path):
    csv = tmp_path / "x.csv"
    csv.write_text("signal_date,ticker\n2026-01-02,NVDA\n2026-01-02,AMD\n2026-01-05,X\n")
    assert export_tabs._row_count(csv) == 3
    assert export_tabs._date_count(csv) == 2

    headerless = tmp_path / "empty.csv"
    headerless.write_text("signal_date,ticker\n")
    assert export_tabs._row_count(headerless) == 0

    undated = tmp_path / "undated.csv"
    undated.write_text("ticker\nNVDA\n")
    assert export_tabs._date_count(undated) is None


def test_row_count_counts_records_not_lines(tmp_path):
    """A quoted embedded newline is ONE row — the play text carries them."""
    csv = tmp_path / "x.csv"
    csv.write_text('date,play\n2026-01-02,"buy the\ncall spread"\n')
    assert export_tabs._row_count(csv) == 1


def test_era_of_degrades_rather_than_raising(tmp_path):
    """An empty export gets a label, not an exception — the summary still prints
    so the operator can see WHICH file came back empty."""
    empty = tmp_path / "empty.csv"
    empty.write_text("score_flow,ticker\n")
    assert export_tabs._era_of(empty) == "?"
