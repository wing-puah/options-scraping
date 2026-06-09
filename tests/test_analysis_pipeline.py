"""Tests for the pure logic in the scripts/analysis_pipeline package (no Drive / no claude needed)."""
import argparse

import pytest

from analysis_pipeline import (
    ENGINES,
    ROW_COLUMNS,
    _RUNNERS,
    _dates_to_process,
    _extract_json,
    _strip_output_section,
    analysis_to_rows,
)


def _ns(**kw):
    base = {"date": None, "start": None, "end": None}
    base.update(kw)
    return argparse.Namespace(**base)


def test_analysis_to_rows_market_row_first_and_schema():
    analysis = {
        "regime": "BEAR + H-VOL + RISK-OFF — broad hedging.",
        "signals": ["[FLOW] QQQ put sweeps", "[VEGA] VIX calls"],
        "sector_focus": "Semis weak.",
        "plays": [],
    }
    rows = analysis_to_rows(analysis, "2026-04-21", "2026-04-15", "2026-04-21")
    assert len(rows) == 1
    market = rows[0]
    assert list(market.keys()) == ROW_COLUMNS  # positional write contract
    assert market["ticker"] == "MARKET"
    assert market["regime"].startswith("BEAR")
    assert "[FLOW] QQQ put sweeps | [VEGA] VIX calls" in market["signal"]
    assert "Sector focus: Semis weak." in market["signal"]
    assert market["data_window_start"] == "2026-04-15"
    assert market["data_window_end"] == "2026-04-21"


def test_analysis_to_rows_expands_plays_and_drops_blank_ticker():
    analysis = {
        "regime": "BEAR",
        "signals": "",
        "plays": [
            {"ticker": "nvda", "pattern": "HP", "structure": "bear put 180/170",
             "thesis": "hedge pressure", "trigger": "lose 180", "invalidation": "close > 185"},
            {"ticker": "", "structure": "junk"},  # dropped: no ticker
        ],
    }
    rows = analysis_to_rows(analysis, "2026-04-21", "2026-04-21", "2026-04-21")
    assert len(rows) == 2  # MARKET + NVDA only
    nvda = rows[1]
    assert nvda["ticker"] == "NVDA"  # upcased
    assert nvda["play"] == "HP | bear put 180/170 | hedge pressure. Trigger: lose 180"
    assert nvda["invalidation"] == "close > 185"
    assert nvda["signal"] == ""  # signals live on the MARKET row only


def test_analysis_to_rows_handles_missing_market_signal():
    rows = analysis_to_rows({"regime": "RANGE", "plays": []}, "2026-04-21", "2026-04-21", "2026-04-21")
    assert rows[0]["signal"] == ""  # no signals, no sector_focus → empty, no "Sector focus:" suffix


def test_extract_json_tolerates_fences_and_prose():
    assert _extract_json('```json\n{"regime":"x"}\n```')["regime"] == "x"
    assert _extract_json('here you go {"regime": "y", "plays": []} done')["regime"] == "y"


def test_extract_json_raises_without_object():
    with pytest.raises(ValueError):
        _extract_json("no json here")


def test_strip_output_section_removes_flat_schema():
    fw = "# Framework\n\n## Step 1\nstuff\n\n## Output Format\n{flat schema}\n"
    stripped = _strip_output_section(fw)
    assert "## Output Format" not in stripped
    assert "## Step 1" in stripped


def test_dates_to_process_single_date_needs_no_client():
    assert _dates_to_process(_ns(date="2026-04-21"), client=None) == ["2026-04-21"]


def test_dates_to_process_range_is_weekdays_only():
    # Fri 2026-04-17 → Mon 2026-04-20 spans a weekend.
    out = _dates_to_process(_ns(start="2026-04-17", end="2026-04-20"), client=None)
    assert out == ["2026-04-17", "2026-04-20"]


def test_engine_registry_covers_both_engines():
    assert set(ENGINES) == {"claude", "codex"}
    assert set(_RUNNERS) == set(ENGINES)  # every engine has a runner
    assert ENGINES["claude"].tab == "AnalysisClaude"
    assert ENGINES["codex"].tab == "AnalysisGPT"
    assert ENGINES["claude"].default_model == "opus"
    assert ENGINES["codex"].default_model is None  # falls back to codex's config


def test_engine_method_files_exist():
    for cfg in ENGINES.values():
        assert cfg.method_file.exists(), cfg.method_file
