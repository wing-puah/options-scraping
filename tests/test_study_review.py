"""Tests for scripts/study_review (no network, no real `claude` calls).

Mirrors tests/test_analysis_pipeline.py's approach: exercise the deterministic
plumbing (persona parsing, pre-registration lookup, prompt assembly, retry
loop, CLI wiring) with monkeypatched config paths and a stubbed
subprocess.run — never a real headless engine call.
"""
import json
import logging
import subprocess
import time

import pytest

from study_review import core
from study_review.core import (
    build_analyst_prompt,
    build_validator_prompt,
    invoke_claude_text,
    load_pre_registration,
    read_persona,
    run_with_retries,
)


# ─────────────────────────────── read_persona ───────────────────────────────

def test_read_persona_strips_frontmatter_and_extracts_model(tmp_path):
    path = tmp_path / "persona.md"
    path.write_text(
        "---\n"
        "name: research-analyst\n"
        "description: some description\n"
        "tools: Read, Grep\n"
        "model: opus\n"
        "---\n"
        "\n"
        "You are one of two independent analysts in this repo's protocol.\n"
    )
    model, body = read_persona(path)
    assert model == "opus"
    assert "You are one of two independent analysts" in body
    assert "---" not in body
    assert "name: research-analyst" not in body


def test_read_persona_no_model_in_frontmatter(tmp_path):
    path = tmp_path / "persona.md"
    path.write_text("---\nname: x\ndescription: y\n---\n\nBody text only.\n")
    model, body = read_persona(path)
    assert model is None
    assert "Body text only." in body


def test_read_persona_no_frontmatter_returns_whole_file(tmp_path):
    path = tmp_path / "persona.md"
    text = "Just a plain persona body, no frontmatter fence at all.\n"
    path.write_text(text)
    model, body = read_persona(path)
    assert model is None
    assert body == text


# ────────────────────────── load_pre_registration ───────────────────────────

def test_load_pre_registration_single_match(tmp_path, monkeypatch):
    current_md = tmp_path / "current.md"
    current_md.write_text(
        "# Tuning log\n\n"
        "## 2026-08-13 — `foo_study`: PRE-REGISTRATION (written BEFORE)\n\n"
        "Criterion 1: something measurable.\n"
        "Criterion 2: something else.\n\n"
        "## 2026-08-13 — `foo_study` RUN: results are in\n\n"
        "Not a pre-registration, must not be picked up.\n"
    )
    monkeypatch.setattr(core.config, "CURRENT_MD", current_md)

    heading, body = load_pre_registration("foo_study", None)
    assert heading == "2026-08-13 — `foo_study`: PRE-REGISTRATION (written BEFORE)"
    assert "Criterion 1: something measurable." in body
    assert "Criterion 2: something else." in body
    assert "RUN: results are in" not in body  # stopped at the next heading


def test_load_pre_registration_two_matches_raises_systemexit_listing_both(tmp_path, monkeypatch):
    current_md = tmp_path / "current.md"
    heading_1 = "2026-08-13 — `foo_study`: PRE-REGISTRATION (attempt 1)"
    heading_2 = "2026-08-14 — `foo_study`: PRE-REGISTRATION (attempt 2)"
    current_md.write_text(
        f"## {heading_1}\n\nBody 1.\n\n"
        f"## {heading_2}\n\nBody 2.\n"
    )
    monkeypatch.setattr(core.config, "CURRENT_MD", current_md)

    with pytest.raises(SystemExit) as exc_info:
        load_pre_registration("foo_study", None)
    msg = str(exc_info.value)
    assert heading_1 in msg
    assert heading_2 in msg
    assert "--pre-reg-section" in msg


def test_load_pre_registration_no_match_raises_systemexit(tmp_path, monkeypatch):
    current_md = tmp_path / "current.md"
    current_md.write_text("## 2026-08-13 — `other_study`: PRE-REGISTRATION\n\nBody.\n")
    monkeypatch.setattr(core.config, "CURRENT_MD", current_md)

    with pytest.raises(SystemExit) as exc_info:
        load_pre_registration("unknown_study", None)
    assert "--pre-reg-section" in str(exc_info.value)


def test_load_pre_registration_explicit_section_title(tmp_path, monkeypatch):
    current_md = tmp_path / "current.md"
    current_md.write_text(
        "## 2026-08-13 — `foo_study`: PRE-REGISTRATION (attempt 1)\n\nBody A.\n\n"
        "## 2026-08-14 — `foo_study`: PRE-REGISTRATION (attempt 2)\n\nBody B.\n"
    )
    monkeypatch.setattr(core.config, "CURRENT_MD", current_md)

    heading, body = load_pre_registration(
        "foo_study", "2026-08-14 — `foo_study`: PRE-REGISTRATION (attempt 2)")
    assert "Body B." in body
    assert "Body A." not in body


# ─────────────────────────────── prompt builders ────────────────────────────

def _report_path():
    return core.config.ROOT / "backtests" / "study_output" / "foo_study-latest.txt"


def test_build_analyst_prompt_contains_required_artifacts():
    prompt = build_analyst_prompt(
        "A", "PERSONA BODY MARKER", "HEADING MARKER", "SECTION BODY MARKER",
        _report_path(), "REPORT TEXT MARKER", "TICKER,QTY\nSPY,10\n")
    assert "PERSONA BODY MARKER" in prompt
    assert "HEADING MARKER" in prompt
    assert "SECTION BODY MARKER" in prompt
    assert "REPORT TEXT MARKER" in prompt
    assert "TICKER,QTY" in prompt
    assert "## Positions CSV" in prompt
    assert "foo_study-positions-latest.csv" in prompt
    assert "## Isolated session" in prompt
    assert "You are Analyst A." in prompt


def test_build_analyst_prompt_omits_positions_block_when_none():
    prompt = build_analyst_prompt(
        "A", "PERSONA", "HEADING", "SECTION BODY",
        _report_path(), "REPORT TEXT", None)
    assert "## Positions CSV" not in prompt


def test_build_analyst_prompt_a_and_b_differ_only_by_role():
    kwargs = dict(
        persona_body="PERSONA", section_heading="HEADING", section_body="SECTION BODY",
        report_path=_report_path(), report_text="REPORT TEXT",
        positions_csv_text="TICKER,QTY\nSPY,10\n")
    prompt_a = build_analyst_prompt("A", **kwargs)
    prompt_b = build_analyst_prompt("B", **kwargs)
    assert prompt_a != prompt_b
    assert prompt_a.replace("Analyst A", "Analyst B") == prompt_b


def test_build_validator_prompt_contains_both_analyst_outputs():
    prompt = build_validator_prompt(
        "VALIDATOR PERSONA", "HEADING", "SECTION BODY", _report_path(), "REPORT TEXT",
        None, "ANALYST A VERDICT TABLE", "ANALYST B VERDICT TABLE")
    assert "ANALYST A VERDICT TABLE" in prompt
    assert "ANALYST B VERDICT TABLE" in prompt
    assert "## Analyst A output" in prompt
    assert "## Analyst B output" in prompt
    assert "source-check" in prompt.lower()
    assert "## Isolated session" in prompt


# ────────────────────────────── invoke_claude_text ──────────────────────────

class _FakeCompletedProcess:
    def __init__(self, returncode, stdout, stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_invoke_claude_text_returns_result_string(monkeypatch):
    events = [{"type": "system"}, {"type": "result", "is_error": False, "result": "FINAL ANSWER"}]
    monkeypatch.setattr(
        core.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(0, json.dumps(events)))
    assert invoke_claude_text("prompt", "opus", "/tmp") == "FINAL ANSWER"


def test_invoke_claude_text_is_error_raises_runtime_error(monkeypatch):
    events = [{"type": "result", "is_error": True, "result": "boom"}]
    monkeypatch.setattr(
        core.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(0, json.dumps(events)))
    with pytest.raises(RuntimeError):
        invoke_claude_text("prompt", "opus", "/tmp")


def test_invoke_claude_text_nonzero_returncode_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(
        core.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(1, "", stderr="fatal error"))
    with pytest.raises(RuntimeError):
        invoke_claude_text("prompt", "opus", "/tmp")


# ────────────────────────────── run_with_retries ─────────────────────────────

def test_run_with_retries_succeeds_after_one_failure(monkeypatch):
    calls = {"n": 0}

    def fake_invoke(prompt, model, cwd):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient failure")
        return "SECOND ATTEMPT RESULT"

    monkeypatch.setattr(core, "invoke_claude_text", fake_invoke)
    result = run_with_retries("prompt", "opus")
    assert result == "SECOND ATTEMPT RESULT"
    assert calls["n"] == 2


def test_run_with_retries_raises_after_exhausting_attempts(monkeypatch):
    def always_fails(prompt, model, cwd):
        raise RuntimeError("still failing")

    monkeypatch.setattr(core, "invoke_claude_text", always_fails)
    with pytest.raises(RuntimeError):
        run_with_retries("prompt", "opus")


# ───────────────────────────── progress feedback ─────────────────────────────
# These calls are silent for minutes; the operator's only signal that an agent
# was actually spawned (rather than the run hanging) is this logging.

def test_run_with_retries_logs_start_and_finish_with_label(monkeypatch, caplog):
    monkeypatch.setattr(core, "invoke_claude_text", lambda p, m, cwd: "OK")
    with caplog.at_level(logging.INFO, logger="study_review"):
        run_with_retries("prompt", "sonnet", "analyst A")
    messages = [r.getMessage() for r in caplog.records]
    assert any("analyst A STARTED" in m and "sonnet" in m for m in messages)
    assert any("analyst A DONE" in m for m in messages)


def test_run_with_retries_label_appears_in_failure(monkeypatch, caplog):
    def always_fails(prompt, model, cwd):
        raise RuntimeError("still failing")

    monkeypatch.setattr(core, "invoke_claude_text", always_fails)
    with caplog.at_level(logging.INFO, logger="study_review"):
        with pytest.raises(RuntimeError, match="validator"):
            run_with_retries("prompt", "opus", "validator")
    assert any("validator FAILED" in r.getMessage() for r in caplog.records)


def test_progress_heartbeats_while_a_call_is_in_flight(monkeypatch, caplog):
    monkeypatch.setattr(core.config, "HEARTBEAT_S", 0.05)
    monkeypatch.setattr(core, "invoke_claude_text",
                        lambda p, m, cwd: (time.sleep(0.2), "OK")[1])
    with caplog.at_level(logging.INFO, logger="study_review"):
        run_with_retries("prompt", "opus", "digest")
    assert any("digest still running" in r.getMessage() for r in caplog.records)


def test_progress_heartbeat_disabled_when_interval_is_zero(monkeypatch, caplog):
    monkeypatch.setattr(core.config, "HEARTBEAT_S", 0)
    monkeypatch.setattr(core, "invoke_claude_text",
                        lambda p, m, cwd: (time.sleep(0.15), "OK")[1])
    with caplog.at_level(logging.INFO, logger="study_review"):
        run_with_retries("prompt", "opus", "digest")
    assert not any("still running" in r.getMessage() for r in caplog.records)


# ────────────────────────────────────── main ─────────────────────────────────

def test_main_dry_run_writes_placeholders_and_never_calls_subprocess(tmp_path, monkeypatch):
    study_output_dir = tmp_path / "study_output"
    study_output_dir.mkdir()
    (study_output_dir / "somestudy-latest.txt").write_text("REPORT CONTENT HERE")

    current_md = tmp_path / "current.md"
    current_md.write_text(
        "## 2026-08-13 — `somestudy`: PRE-REGISTRATION (written BEFORE)\n\n"
        "Gate 1: some criterion.\n"
    )

    analyst_persona = tmp_path / "research-analyst.md"
    analyst_persona.write_text("---\nmodel: opus\n---\n\nAnalyst persona body.\n")
    validator_persona = tmp_path / "research-validator.md"
    validator_persona.write_text("---\nmodel: sonnet\n---\n\nValidator persona body.\n")

    monkeypatch.setattr(core.config, "STUDY_OUTPUT_DIR", study_output_dir)
    monkeypatch.setattr(core.config, "CURRENT_MD", current_md)
    monkeypatch.setattr(core.config, "ANALYST_PERSONA_FILE", analyst_persona)
    monkeypatch.setattr(core.config, "VALIDATOR_PERSONA_FILE", validator_persona)
    monkeypatch.setattr(core.config, "GLOSSARY_MD", tmp_path / "glossary-does-not-exist.md")

    def _forbidden(*a, **kw):
        raise AssertionError("subprocess.run must never be called in --dry-run")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(core.subprocess, "run", _forbidden)

    core.main(["somestudy", "--skip-run", "--dry-run"])

    a_path = study_output_dir / "somestudy-review-analyst-a-latest.md"
    b_path = study_output_dir / "somestudy-review-analyst-b-latest.md"
    validator_path = study_output_dir / "somestudy-review-validator-latest.md"
    digest_path = study_output_dir / "somestudy-digest-latest.md"

    for path in (a_path, b_path, validator_path, digest_path):
        assert path.exists(), path
        assert "DRY RUN" in path.read_text()
