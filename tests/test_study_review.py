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
    load_errata,
    load_pre_registration,
    read_persona,
    run_with_retries,
)


# ─────────────────────────────── resolve_report ─────────────────────────────
#
# A DESIGNED refusal exits the STUDY 2 but the RUNNER 0 — correctly, since a
# refusal is not a failure. That makes the report itself the only place the
# refusal is visible, and grading one costs three headless model calls to
# replicate a study that declined to conclude.

def _write_report(dir_path, study, body, exit_code):
    path = dir_path / f"{study}-latest.txt"
    path.write_text(
        "==============================================================\n"
        f"STUDY: {study}\n"
        "==============================================================\n"
        "  run at    2026-08-19 11:30:10\n"
        "==============================================================\n"
        f"{body}\n"
        "==============================================================\n"
        f"exit code {exit_code} after 5.2s\n"
    )
    return path


def test_resolve_report_refuses_to_grade_a_refused_report(tmp_path, monkeypatch):
    out = tmp_path / "study_output"
    out.mkdir()
    _write_report(out, "somestudy",
                  "REFUSED — the book has 34 signal dates but NOT ONE dense episode.",
                  exit_code=2)
    monkeypatch.setattr(core.config, "STUDY_OUTPUT_DIR", out)

    with pytest.raises(SystemExit) as exc:
        core.resolve_report("somestudy", skip_run=True, run_args=[])
    msg = str(exc.value)
    assert "REFUSED (exit 2)" in msg
    assert "not a failure" in msg
    assert "NOT ONE dense episode" in msg     # the study's own words, not ours


def test_resolve_report_grades_a_report_that_concluded(tmp_path, monkeypatch):
    out = tmp_path / "study_output"
    out.mkdir()
    path = _write_report(out, "somestudy", "  verdict: feasible", exit_code=0)
    monkeypatch.setattr(core.config, "STUDY_OUTPUT_DIR", out)

    assert core.resolve_report("somestudy", skip_run=True, run_args=[]) == path


def test_resolve_report_reads_the_refusal_from_the_directory_it_was_given(
        tmp_path, monkeypatch):
    """`summarize()` defaults to the study map's own OUT_DIR. If study_review
    let it, this check would read a DIFFERENT report than the one it returns."""
    out = tmp_path / "study_output"
    out.mkdir()
    _write_report(out, "somestudy", "REFUSED — nothing to conclude from.", exit_code=2)
    monkeypatch.setattr(core.config, "STUDY_OUTPUT_DIR", out)
    monkeypatch.setattr(core.study_summary, "OUT_DIR", tmp_path / "somewhere-else")

    with pytest.raises(SystemExit, match="REFUSED"):
        core.resolve_report("somestudy", skip_run=True, run_args=[])


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

def test_load_pre_registration_reads_per_study_file(tmp_path, monkeypatch):
    pre_reg_dir = tmp_path / "pre-registrations"
    (pre_reg_dir / "f1_selection").mkdir(parents=True)
    (pre_reg_dir / "f1_selection" / "foo_study.md").write_text(
        "## 2026-08-13 — `foo_study`: PRE-REGISTRATION (written BEFORE)\n\n"
        "Criterion 1: something measurable.\n"
        "Criterion 2: something else.\n"
    )
    monkeypatch.setattr(core.config, "PRE_REG_DIR", pre_reg_dir)

    heading, body = load_pre_registration("foo_study", None)
    assert heading == "2026-08-13 — `foo_study`: PRE-REGISTRATION (written BEFORE)"
    assert "Criterion 1: something measurable." in body
    assert "Criterion 2: something else." in body
    assert not body.startswith("##")  # heading line stripped off the body


def test_load_pre_registration_no_leading_heading_uses_filename_as_label(tmp_path, monkeypatch):
    pre_reg_dir = tmp_path / "pre-registrations"
    (pre_reg_dir / "f2_management").mkdir(parents=True)
    (pre_reg_dir / "f2_management" / "foo_study.md").write_text("Just a plan, no heading line.\n")
    monkeypatch.setattr(core.config, "PRE_REG_DIR", pre_reg_dir)

    heading, body = load_pre_registration("foo_study", None)
    assert heading == "foo_study.md"
    assert "Just a plan, no heading line." in body


def test_load_pre_registration_missing_file_raises_systemexit_listing_available(tmp_path, monkeypatch):
    pre_reg_dir = tmp_path / "pre-registrations"
    (pre_reg_dir / "f2_management").mkdir(parents=True)
    (pre_reg_dir / "f2_management" / "other_study.md").write_text(
        "## other_study: PRE-REGISTRATION\n\nBody.\n")
    # Top-level README (folder index) and a per-family README must both stay
    # out of the "available studies" listing.
    (pre_reg_dir / "README.md").write_text("Not a study — must be excluded from the listing.\n")
    (pre_reg_dir / "f2_management" / "README.md").write_text("Also not a study.\n")
    monkeypatch.setattr(core.config, "PRE_REG_DIR", pre_reg_dir)

    with pytest.raises(SystemExit) as exc_info:
        load_pre_registration("unknown_study", None)
    msg = str(exc_info.value)
    assert "other_study" in msg
    assert "README" not in msg
    assert "--pre-reg" in msg


def test_load_pre_registration_empty_file_raises_systemexit(tmp_path, monkeypatch):
    pre_reg_dir = tmp_path / "pre-registrations"
    (pre_reg_dir / "f3_structure").mkdir(parents=True)
    (pre_reg_dir / "f3_structure" / "foo_study.md").write_text("   \n")
    monkeypatch.setattr(core.config, "PRE_REG_DIR", pre_reg_dir)

    with pytest.raises(SystemExit) as exc_info:
        load_pre_registration("foo_study", None)
    assert "empty" in str(exc_info.value).lower()


def test_load_pre_registration_override_path_bypasses_pre_reg_dir(tmp_path, monkeypatch):
    pre_reg_dir = tmp_path / "pre-registrations"
    pre_reg_dir.mkdir()
    monkeypatch.setattr(core.config, "PRE_REG_DIR", pre_reg_dir)

    override_path = tmp_path / "archived" / "foo_study_old.md"
    override_path.parent.mkdir()
    override_path.write_text("## archived — foo_study: PRE-REGISTRATION\n\nArchived body.\n")

    heading, body = load_pre_registration("foo_study", str(override_path))
    assert heading == "archived — foo_study: PRE-REGISTRATION"
    assert "Archived body." in body


def test_load_pre_registration_override_missing_file_raises_systemexit(tmp_path, monkeypatch):
    pre_reg_dir = tmp_path / "pre-registrations"
    (pre_reg_dir / "f4_deployment").mkdir(parents=True)
    (pre_reg_dir / "f4_deployment" / "foo_study.md").write_text(
        "## foo_study: PRE-REGISTRATION\n\nBody.\n")
    monkeypatch.setattr(core.config, "PRE_REG_DIR", pre_reg_dir)

    with pytest.raises(SystemExit):
        load_pre_registration("foo_study", str(tmp_path / "does-not-exist.md"))


def test_load_pre_registration_ambiguous_across_families_raises_systemexit(tmp_path, monkeypatch):
    pre_reg_dir = tmp_path / "pre-registrations"
    (pre_reg_dir / "f1_selection").mkdir(parents=True)
    (pre_reg_dir / "f2_management").mkdir(parents=True)
    (pre_reg_dir / "f1_selection" / "dup_study.md").write_text("## dup A\n\nBody A.\n")
    (pre_reg_dir / "f2_management" / "dup_study.md").write_text("## dup B\n\nBody B.\n")
    monkeypatch.setattr(core.config, "PRE_REG_DIR", pre_reg_dir)

    with pytest.raises(SystemExit) as exc_info:
        load_pre_registration("dup_study", None)
    msg = str(exc_info.value)
    assert "f1_selection/dup_study.md" in msg
    assert "f2_management/dup_study.md" in msg
    assert "--pre-reg" in msg


def test_load_pre_registration_flat_file_is_not_resolved(tmp_path, monkeypatch):
    # A stray copy at the old flat location must NOT be found — there is
    # deliberately no flat-path fallback, so it errors instead of silently
    # shadowing the family-foldered file.
    pre_reg_dir = tmp_path / "pre-registrations"
    (pre_reg_dir / "f1_selection").mkdir(parents=True)
    (pre_reg_dir / "flat_study.md").write_text("## flat_study: PRE-REGISTRATION\n\nBody.\n")
    monkeypatch.setattr(core.config, "PRE_REG_DIR", pre_reg_dir)

    with pytest.raises(SystemExit) as exc_info:
        load_pre_registration("flat_study", None)
    assert "No pre-registration" in str(exc_info.value)


# ─────────────────────────────── prompt builders ────────────────────────────

def _report_path():
    return core.config.ROOT / "backtests" / "study_output" / "foo_study-latest.txt"


def test_build_analyst_prompt_contains_required_artifacts():
    prompt = build_analyst_prompt(
        "A", "PERSONA BODY MARKER", "HEADING MARKER", "SECTION BODY MARKER",
        None, _report_path(), "REPORT TEXT MARKER", "TICKER,QTY\nSPY,10\n")
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
        None, _report_path(), "REPORT TEXT", None)
    assert "## Positions CSV" not in prompt


def test_build_analyst_prompt_a_and_b_differ_only_by_role():
    kwargs = dict(
        persona_body="PERSONA", section_heading="HEADING", section_body="SECTION BODY",
        errata=None, report_path=_report_path(), report_text="REPORT TEXT",
        positions_csv_text="TICKER,QTY\nSPY,10\n")
    prompt_a = build_analyst_prompt("A", **kwargs)
    prompt_b = build_analyst_prompt("B", **kwargs)
    assert prompt_a != prompt_b
    assert prompt_a.replace("Analyst A", "Analyst B") == prompt_b


def test_build_validator_prompt_contains_both_analyst_outputs():
    prompt = build_validator_prompt(
        "VALIDATOR PERSONA", "HEADING", "SECTION BODY", None, _report_path(), "REPORT TEXT",
        None, "ANALYST A VERDICT TABLE", "ANALYST B VERDICT TABLE")
    assert "ANALYST A VERDICT TABLE" in prompt
    assert "ANALYST B VERDICT TABLE" in prompt
    assert "## Analyst A output" in prompt
    assert "## Analyst B output" in prompt
    assert "source-check" in prompt.lower()
    assert "## Isolated session" in prompt


def test_build_analyst_prompt_inlines_errata_as_authority():
    """The hole this closes: without the errata block, a grader can only check a
    ratification against the report's own quoted account of it."""
    errata = (core.config.ROOT / "research" / "foo-study-errata.md", "ERRATUM 1 MARKER")
    prompt = build_analyst_prompt(
        "A", "PERSONA", "HEADING", "SECTION BODY", errata,
        _report_path(), "REPORT TEXT", None)
    assert "## Errata and fix plan (research/foo-study-errata.md)" in prompt
    assert "ERRATUM 1 MARKER" in prompt
    assert "AUTHORITY" in prompt
    # authority order: registration, then errata, then the artifact being graded
    assert prompt.index("## Pre-registration") < prompt.index("## Errata and fix plan")
    assert prompt.index("## Errata and fix plan") < prompt.index("## Study report")


def test_build_analyst_prompt_omits_errata_block_when_none():
    prompt = build_analyst_prompt(
        "A", "PERSONA", "HEADING", "SECTION BODY", None,
        _report_path(), "REPORT TEXT", None)
    assert "## Errata" not in prompt


def test_build_validator_prompt_inlines_errata():
    errata = (core.config.ROOT / "research" / "foo-study-errata.md", "ERRATUM 1 MARKER")
    prompt = build_validator_prompt(
        "VALIDATOR PERSONA", "HEADING", "SECTION BODY", errata, _report_path(),
        "REPORT TEXT", None, "A OUTPUT", "B OUTPUT")
    assert "ERRATUM 1 MARKER" in prompt
    assert "## Errata and fix plan" in prompt


# ──────────────────────────────── load_errata ───────────────────────────────

def test_load_errata_finds_the_hyphenated_file_for_an_underscored_study(tmp_path, monkeypatch):
    monkeypatch.setattr(core.config, "ERRATA_DIR", tmp_path)
    (tmp_path / "hedge-exposure-errata.md").write_text("# errata body\n")
    path, text = load_errata("hedge_exposure", None, skip=False)
    assert path.name == "hedge-exposure-errata.md"
    assert text == "# errata body"


def test_load_errata_missing_is_non_fatal(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(core.config, "ERRATA_DIR", tmp_path)
    assert load_errata("account_sim", None, skip=False) is None
    assert "no errata file" in capsys.readouterr().err


def test_load_errata_skip_flag_returns_none_even_when_a_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(core.config, "ERRATA_DIR", tmp_path)
    (tmp_path / "foo_study-errata.md").write_text("body")
    assert load_errata("foo_study", None, skip=True) is None


def test_load_errata_empty_file_raises_systemexit(tmp_path, monkeypatch):
    monkeypatch.setattr(core.config, "ERRATA_DIR", tmp_path)
    (tmp_path / "foo_study-errata.md").write_text("   \n")
    with pytest.raises(SystemExit) as excinfo:
        load_errata("foo_study", None, skip=False)
    assert "empty" in str(excinfo.value)


def test_load_errata_ambiguous_underscore_and_hyphen_copies_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(core.config, "ERRATA_DIR", tmp_path)
    (tmp_path / "foo_study-errata.md").write_text("one")
    (tmp_path / "foo-study-errata.md").write_text("two")
    with pytest.raises(SystemExit) as excinfo:
        load_errata("foo_study", None, skip=False)
    assert "Ambiguous errata" in str(excinfo.value)


def test_load_errata_override_path_is_used_verbatim(tmp_path, monkeypatch):
    monkeypatch.setattr(core.config, "ERRATA_DIR", tmp_path)
    override = tmp_path / "elsewhere.md"
    override.write_text("OVERRIDE BODY")
    path, text = load_errata("foo_study", str(override), skip=False)
    assert path == override
    assert text == "OVERRIDE BODY"


def test_load_errata_override_missing_file_raises_systemexit(tmp_path, monkeypatch):
    monkeypatch.setattr(core.config, "ERRATA_DIR", tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        load_errata("foo_study", str(tmp_path / "nope.md"), skip=False)
    assert "--errata" in str(excinfo.value)


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

    pre_reg_dir = tmp_path / "pre-registrations"
    (pre_reg_dir / "f4_deployment").mkdir(parents=True)
    (pre_reg_dir / "f4_deployment" / "somestudy.md").write_text(
        "## 2026-08-13 — `somestudy`: PRE-REGISTRATION (written BEFORE)\n\n"
        "Gate 1: some criterion.\n"
    )

    analyst_persona = tmp_path / "research-analyst.md"
    analyst_persona.write_text("---\nmodel: opus\n---\n\nAnalyst persona body.\n")
    validator_persona = tmp_path / "research-validator.md"
    validator_persona.write_text("---\nmodel: sonnet\n---\n\nValidator persona body.\n")

    monkeypatch.setattr(core.config, "STUDY_OUTPUT_DIR", study_output_dir)
    monkeypatch.setattr(core.config, "PRE_REG_DIR", pre_reg_dir)
    monkeypatch.setattr(core.config, "ERRATA_DIR", tmp_path)
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
