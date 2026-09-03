"""Local-only analysis runs (`--output-dir`) — the prompt-evaluation path.

The invariant under test: a run that names an output dir writes its artefacts to
disk and NEVER reaches ``sheets_client.append_rows``. AnalysisClaude has no date
dedup, so a stray append from a candidate-prompt run would silently double that
date's rows with no undo — the guard has to be structural, not a --dry-run habit.
"""
import csv
import json

import pytest

from analysis_pipeline import ROW_COLUMNS
from analysis_pipeline import core


_ANALYSIS = {
    "regime": "BULL — dealers short gamma",
    "signals": ["[FLOW] call sweeps in semis"],
    "plays": [
        {"ticker": "NVDA", "asset_class": "stock", "flow_intent": "directional",
         "pattern": "call sweep", "structure": "bull call spread 120/130",
         "thesis": "momentum", "trigger": "break 118", "invalidation": "close < 112",
         "horizon": "2-4 weeks", "regime": "BULL", "signal": "[FLOW] sweeps"},
    ],
}

_SENTINEL_FRAMEWORK = "SENTINEL-FRAMEWORK-XYZ"
_SENTINEL_METHOD = "SENTINEL-METHOD-XYZ"


@pytest.fixture
def stub_pipeline(monkeypatch, tmp_path):
    """Stub every side-effecting edge of ``core.main``: Drive, fetch, the engine,
    the score/regime lookups, and Sheets (which is wired to EXPLODE)."""
    monkeypatch.setattr(core, "get_drive_client", lambda: object())
    monkeypatch.setattr(core, "fetch_data",
                        lambda **kw: "## stocks-flow\n\nsome markdown\n")
    monkeypatch.setattr(core, "_compute_play_scores", lambda analysis, d: {})
    monkeypatch.setattr(core, "_load_rollup_metrics", lambda p: {})
    monkeypatch.setattr(core, "_mech_cell", lambda d: "NEUTRAL")

    captured = {}

    def fake_run_engine(engine, prompt, model):
        captured["prompt"] = prompt
        return _ANALYSIS, '{"regime": "BULL — dealers short gamma"}'

    monkeypatch.setattr(core, "run_engine", fake_run_engine)

    def explode(*a, **kw):
        raise AssertionError("sheets_client.append_rows must never be called")

    monkeypatch.setattr(core.sheets_client, "append_rows", explode)
    return captured


@pytest.fixture
def prompt_files(tmp_path):
    fw = tmp_path / "candidate-framework.md"
    fw.write_text(f"# Candidate framework\n{_SENTINEL_FRAMEWORK}\n")
    me = tmp_path / "candidate-method.md"
    me.write_text(f"# Candidate method\n{_SENTINEL_METHOD}\n")
    return fw, me


def _manifest(out_dir):
    lines = (out_dir / "manifest.jsonl").read_text().strip().splitlines()
    return [json.loads(ln) for ln in lines]


# ── 1. The full local run ───────────────────────────────────────────────────────

def test_output_dir_writes_artifacts_and_never_touches_sheets(stub_pipeline, tmp_path):
    out = tmp_path / "run"
    core.main(["--date", "2026-06-01", "--output-dir", str(out)])

    assert (out / "2026-06-01.json").exists()
    assert (out / "2026-06-01-prompt.md").exists()
    assert (out / "2026-06-01-response.json").exists()
    assert (out / "2026-06-01-rows.csv").exists()
    assert (out / "manifest.jsonl").exists()

    assert json.loads((out / "2026-06-01.json").read_text())["regime"].startswith("BULL")
    assert "BULL" in json.loads((out / "2026-06-01-response.json").read_text())["raw"]


def test_rows_csv_header_is_exactly_row_columns(stub_pipeline, tmp_path):
    out = tmp_path / "run"
    core.main(["--date", "2026-06-01", "--output-dir", str(out)])

    with (out / "2026-06-01-rows.csv").open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == list(ROW_COLUMNS)
        rows = list(reader)
    # Same shape Sheets would have received: MARKET row first, then one per play.
    assert [r["ticker"] for r in rows] == ["MARKET", "NVDA"]
    assert rows[0]["date"] == "2026-06-01"


def test_manifest_records_the_run_inputs(stub_pipeline, prompt_files, tmp_path):
    fw, me = prompt_files
    out = tmp_path / "run"
    core.main(["--date", "2026-06-01", "--output-dir", str(out),
               "--framework-file", str(fw), "--method-file", str(me)])

    entries = _manifest(out)
    assert len(entries) == 1
    e = entries[0]
    assert e["date"] == "2026-06-01"
    assert e["engine"] == "claude"
    assert e["n_rows"] == 2
    assert e["framework_file"] == str(fw)
    assert e["method_file"] == str(me)
    assert len(e["framework_sha256"]) == 12
    assert e["framework_sha256"] != e["method_sha256"]
    assert "--output-dir" in e["argv"]


def test_audit_csv_is_redirected_into_the_output_dir(monkeypatch, stub_pipeline, tmp_path):
    seen = {}

    def fake_fetch(**kw):
        seen["audit"] = kw["audit_csv_path"]
        return "## stocks-flow\n\nsome markdown\n"

    monkeypatch.setattr(core, "fetch_data", fake_fetch)
    out = tmp_path / "run"
    core.main(["--date", "2026-06-01", "--output-dir", str(out)])
    assert seen["audit"] == out / "audit" / "2026-06-01-rollup.csv"


# ── 2. Prompt-file overrides ────────────────────────────────────────────────────

def test_override_prompt_files_reach_the_assembled_prompt(stub_pipeline, prompt_files, tmp_path):
    fw, me = prompt_files
    out = tmp_path / "run"
    core.main(["--date", "2026-06-01", "--output-dir", str(out),
               "--framework-file", str(fw), "--method-file", str(me)])

    prompt = (out / "2026-06-01-prompt.md").read_text()
    assert _SENTINEL_FRAMEWORK in prompt
    assert _SENTINEL_METHOD in prompt
    # And what was archived is exactly what the engine was shown.
    assert prompt == stub_pipeline["prompt"]


def test_missing_override_file_exits_rather_than_falling_back(stub_pipeline, tmp_path):
    with pytest.raises(SystemExit) as exc:
        core.main(["--date", "2026-06-01", "--output-dir", str(tmp_path / "run"),
                   "--framework-file", str(tmp_path / "nope.md")])
    assert exc.value.code == 2


# ── 3. --skip-llm + --output-dir = prompt snapshot only ─────────────────────────

def test_skip_llm_with_output_dir_writes_prompt_and_manifest_only(
        monkeypatch, stub_pipeline, prompt_files, tmp_path):
    def no_engine(*a, **kw):
        raise AssertionError("--skip-llm must not call the engine")

    monkeypatch.setattr(core, "run_engine", no_engine)
    fw, me = prompt_files
    out = tmp_path / "run"
    core.main(["--date", "2026-06-01", "--output-dir", str(out), "--skip-llm",
               "--framework-file", str(fw), "--method-file", str(me)])

    assert (out / "2026-06-01-prompt.md").exists()
    assert (out / "manifest.jsonl").exists()
    assert not (out / "2026-06-01.json").exists()
    assert not (out / "2026-06-01-response.json").exists()
    assert not (out / "2026-06-01-rows.csv").exists()

    entry = _manifest(out)[0]
    assert entry["skip_llm"] is True
    assert entry["n_rows"] == 0
    assert _SENTINEL_FRAMEWORK in (out / "2026-06-01-prompt.md").read_text()
