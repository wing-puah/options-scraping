"""
Core logic for the study-review two-analyst replication harness.

    resolve report  → run/locate scripts.backtest_study's <study>-latest.txt   (deterministic)
    load artifacts  → pre-registration section, positions CSV, personas       (deterministic)
    grade           → Analyst A + Analyst B headless calls, in PARALLEL       (LLM, isolated)
    validate        → validator headless call, reading both analyst outputs  (LLM, isolated)
    digest          → plain-language write-up headless call                  (LLM, isolated)

This automates Mode 1 of research/replication-protocol.md — the
orchestration that document describes the main session performing by hand
(spawn analyst A + B together, then the validator) is instead run here as four
headless `claude -p` calls, each from a neutral tempfile cwd so the repo's
CLAUDE.md / skills never load into the isolated session (same reasoning as
scripts/analysis_pipeline/core.py's `_invoke_claude`). The only LLM
touchpoints are those four calls; report resolution, pre-registration lookup,
prompt assembly, and file writes are all deterministic.

Determinism note: as with analysis_pipeline, there is no temperature knob over
the headless CLI, so expect run-to-run variation in analyst/validator/digest
text. We constrain it with fixed, artifact-only prompts and retry on failure,
nothing more.
"""
import argparse
import contextlib
import json
import logging
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

from . import config

load_dotenv(config.ROOT / ".env")
sys.path.insert(0, str(config.ROOT))

from lib.logger import setup_logging  # noqa: E402  (after sys.path insert, mirrors analysis_pipeline)

log = logging.getLogger("study_review")

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


def read_persona(path: Path) -> tuple[str | None, str]:
    """Strip a persona file's `---\\n...\\n---` YAML frontmatter and pull out
    its `model:` value if present. Returns (model, body) — model is None when
    there is no frontmatter or no `model:` key; body is the persona text with
    the frontmatter removed (or the whole file, unchanged, when there was none
    to strip)."""
    text = path.read_text()
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    model = None
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("model:"):
            model = line.split(":", 1)[1].strip()
            break
    return model, text[m.end():].lstrip("\n")


def resolve_report(study: str, skip_run: bool, run_args: list[str]) -> Path:
    """Run (unless skipped) `python -m scripts.backtest_study run <study>` and
    return the resulting `<study>-latest.txt` path.

    A nonzero exit is a hard stop (SystemExit) — a gate-failed report isn't
    worth grading. Output streams live (no capture) so the operator watches
    the study run the same way `python -m scripts.backtest_study run` prints
    it directly."""
    if not skip_run:
        # --no-handoff: the runner's normal footer tells the operator to paste the
        # report into Claude for a write-up. That's the manual workflow this module
        # replaces — the analyst/validator/digest calls below do it here.
        cmd = [sys.executable, "-u", "-m", "scripts.backtest_study", "run", study,
               "--no-handoff", *run_args]
        log.info("Running study: %s", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=config.ROOT)
        if proc.returncode != 0:
            raise SystemExit(
                f"study run failed (rc={proc.returncode}): {' '.join(cmd)}\n"
                "A gate-failed report isn't worth grading — fix the study run, "
                "or pass --skip-run to grade an existing report as-is.")
    report_path = config.STUDY_OUTPUT_DIR / f"{study}-latest.txt"
    if not report_path.exists():
        raise SystemExit(
            f"No report found at {report_path}. Run `python -m scripts.backtest_study "
            f"run {study}` first, or check the study name (see `python -m "
            "scripts.backtest_study list`).")
    return report_path


def _study_from_report_path(report_path: Path) -> str:
    """`<study>-latest.txt` → `<study>` (resolve_report's naming convention)."""
    stem = report_path.stem  # "<study>-latest"
    return stem[:-len("-latest")] if stem.endswith("-latest") else stem


def load_pre_registration(study: str, override: str | None) -> tuple[str, str]:
    """Read `pre-registrations/<study>.md` whole and return (heading, body).

    The pre-registration is what the analysts grade the run AGAINST, so the one
    property that matters is that it is still there and still says what it said.
    It therefore lives in its own file, read entire — no heading matching, no
    scanning of current.md. That log is pruned into archive/ on a rolling basis
    and its headings are edited for readability; keying this lookup off a `## `
    section inside it meant a routine prune or a reworded heading would break
    `study_review` at exactly the moment someone was re-grading an old study.

    `heading` is the file's first `## ` line (a label for the prompt);
    `body` is EVERYTHING after it. A study that re-registers appends a new dated
    section to the same file rather than overwriting, so a changed plan stays
    visible to the graders instead of being quietly replaced — which is why the
    whole file goes to them, not just the newest section.

    `override` is an explicit path, for grading against a pre-registration that
    is not the study's own file (a renamed study, or an archived copy).
    """
    path = Path(override) if override else config.PRE_REG_DIR / config.PRE_REG_PATTERN.format(study=study)
    if not path.is_file():
        available = sorted(p.stem for p in config.PRE_REG_DIR.glob("*.md") if p.stem != "README")
        listed = "\n".join(f"  - {s}" for s in available) or "  (none found)"
        raise SystemExit(
            f"No pre-registration for study {study!r} at {path}.\n"
            f"Studies with a pre-registration on file:\n{listed}\n"
            "Write one before grading a run, or pass --pre-reg <path> to point at "
            "a different file. A pre-registration is written BEFORE the study is "
            "run; grading a run against a plan reconstructed afterwards is not a "
            "replication check.")

    text = path.read_text().strip()
    if not text:
        raise SystemExit(f"Pre-registration {path} is empty — nothing to grade the run against.")

    first_line, _, rest = text.partition("\n")
    if first_line.startswith("## "):
        return first_line[len("## "):].strip(), rest.strip()
    # No leading heading: the whole file is the pre-registration and the path
    # is the only label available. Still perfectly gradeable.
    return path.name, text


def load_positions_csv(study: str, override: str | None, skip: bool) -> str | None:
    """Read a positions CSV verbatim, or return None with a stderr warning.

    Only account_sim produces one today, so a missing file for any other
    study is the expected, non-fatal case."""
    if skip:
        print("study_review: --no-positions-csv passed — skipping positions CSV", file=sys.stderr)
        return None
    path = Path(override) if override else (
        config.STUDY_OUTPUT_DIR / config.POSITIONS_CSV_PATTERN.format(study=study))
    if not path.exists():
        print(
            f"study_review: no positions CSV at {path} — continuing without it "
            "(only account_sim produces one today)", file=sys.stderr)
        return None
    return path.read_text()


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(config.ROOT))
    except ValueError:
        return str(path)


_NO_FILE_ACCESS_NOTE = (
    "## Isolated session — no file or tool access\n\n"
    "This is a headless, isolated session: you have NO filesystem access and NO "
    "tools beyond generating text. Work ONLY from the artifacts inlined below in "
    "this prompt. Where your persona instructions above reference a file by path "
    "(e.g. a report under backtests/study_output/, a file under "
    "research/pre-registrations/), treat the matching inlined "
    "block below as that file's content — there is nothing else to open."
)


def _artifact_blocks(section_heading: str, section_body: str, report_path: Path,
                     report_text: str, positions_csv_text: str | None) -> list[str]:
    """Artifact blocks shared by the analyst and validator prompts."""
    blocks = [
        f'## Pre-registration ("{section_heading}", from '
        f"research/pre-registrations/)\n\n{section_body}",
        f"## Study report ({_rel(report_path)})\n\n{report_text}",
    ]
    if positions_csv_text:
        study = _study_from_report_path(report_path)
        blocks.append(
            f"## Positions CSV (backtests/study_output/{study}-positions-latest.csv)\n\n"
            f"{positions_csv_text}")
    return blocks


def build_analyst_prompt(role: str, persona_body: str, section_heading: str, section_body: str,
                         report_path: Path, report_text: str,
                         positions_csv_text: str | None) -> str:
    """Assemble one analyst's (A or B) full prompt. A and B prompts are
    byte-identical except for the role letter substituted into "You are
    Analyst {role}." — the two-analyst protocol requires it that way."""
    parts = [
        persona_body.strip(),
        _NO_FILE_ACCESS_NOTE,
        f"You are Analyst {role}.",
        *_artifact_blocks(section_heading, section_body, report_path, report_text, positions_csv_text),
    ]
    return "\n\n".join(parts)


def build_validator_prompt(persona_body: str, section_heading: str, section_body: str,
                           report_path: Path, report_text: str, positions_csv_text: str | None,
                           analyst_a_output: str, analyst_b_output: str) -> str:
    """Assemble the validator's prompt: same artifacts as the analysts, plus
    both analyst outputs verbatim, plus an explicit note that "source-check"
    means re-checking numbers against the inlined blocks here — not opening
    any file."""
    parts = [
        persona_body.strip(),
        _NO_FILE_ACCESS_NOTE + (
            " In particular: wherever your instructions say to \"source-check\" a "
            "quoted number, that means re-checking it against the inlined artifact "
            "blocks in THIS prompt, not opening the report or CSV yourself."),
        *_artifact_blocks(section_heading, section_body, report_path, report_text, positions_csv_text),
        f"## Analyst A output\n\n{analyst_a_output}",
        f"## Analyst B output\n\n{analyst_b_output}",
    ]
    return "\n\n".join(parts)


def build_digest_prompt(study: str, report_path: Path, report_text: str,
                        glossary_text: str | None) -> str:
    """Assemble the plain-language digest prompt: audience is a
    non-statistician owner of this project. Walks every section of the report,
    defines metric terms only from the inlined glossary (or, when absent,
    instructs careful inline definitions), preserves the report's verdict and
    its own anti-tuning caveats, and outputs pure markdown."""
    if glossary_text is not None:
        glossary_block = (
            "## Glossary (research/glossary.md)\n\n"
            "Use ONLY these definitions for metric terms below — do not invent or "
            f"assume a different meaning.\n\n{glossary_text}")
    else:
        glossary_block = (
            "## Glossary\n\n"
            "No glossary.md file exists in this repo yet. Define every metric term "
            "(e.g. MFE, MAE, confidence interval, R multiple, p-value) carefully and "
            "precisely the first time you use it — do not assume the reader already "
            "knows it.")
    instructions = (
        "## Digest — plain-language write-up\n\n"
        f"Write a plain-language digest of the backtest tuning study report below "
        f"({study}) for a non-statistician owner of this options-trading project. "
        "Walk EVERY section of the report — every table, every number — in plain "
        "language: what it says and why it matters for the trading book. Preserve "
        "and explain the report's verdict; do not soften it or invent a different "
        "one. Carry forward the report's own anti-tuning caveats (multiple-"
        "comparisons risk, small-n warnings, any closed threads it name-checks) "
        "instead of dropping them for readability. Output pure markdown, nothing "
        "else before or after it.")
    return "\n\n".join([
        instructions,
        glossary_block,
        f"## Study report ({_rel(report_path)})\n\n{report_text}",
    ])


def invoke_claude_text(prompt: str, model: str, cwd: str) -> str:
    """One `claude -p` call. Prompt on stdin; stdout is a JSON array of
    events. Mirrors analysis_pipeline.core._invoke_claude's subprocess shape
    and result-event extraction, but returns the raw `result` string instead
    of parsing it as JSON — these prompts ask for prose/markdown, not a JSON
    contract."""
    proc = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", model],
        input=prompt, capture_output=True, text=True, cwd=cwd,
        timeout=config.REQUEST_TIMEOUT_S, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    parsed = json.loads(proc.stdout)
    # New Claude CLI emits a JSON array of events; find the result entry.
    if isinstance(parsed, list):
        result_events = [e for e in parsed if isinstance(e, dict) and e.get("type") == "result"]
        wrapper = result_events[-1] if result_events else {}
    else:
        wrapper = parsed
    if wrapper.get("is_error"):
        raise RuntimeError(f"claude reported error: {wrapper.get('result')}")
    return wrapper.get("result", "")


@contextlib.contextmanager
def progress(label: str, model: str, prompt_chars: int):
    """Announce a headless agent's start, heartbeat while it runs, report its
    outcome and elapsed time.

    Each `claude -p` call below is silent for minutes — without this an
    operator has no way to tell a working agent from a hung one, and the
    analysts run in parallel so plain sequencing wouldn't show which is which.
    The heartbeat is a daemon thread waiting on an Event, so it costs nothing
    and dies with the process on Ctrl-C."""
    log.info("▶ %s STARTED — model=%s, prompt=%s chars", label, model, f"{prompt_chars:,}")
    t0 = time.time()
    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(config.HEARTBEAT_S):
            log.info("· %s still running — %.0fs elapsed", label, time.time() - t0)

    if config.HEARTBEAT_S:
        threading.Thread(target=_beat, daemon=True).start()
    try:
        yield
    except BaseException:
        stop.set()
        log.error("✗ %s FAILED after %.0fs", label, time.time() - t0)
        raise
    else:
        stop.set()
        log.info("✓ %s DONE in %.0fs", label, time.time() - t0)


def run_with_retries(prompt: str, model: str, label: str = "claude call") -> str:
    """Retry loop around invoke_claude_text: MAX_ATTEMPTS attempts, a fresh
    neutral tempdir per attempt (so a failed attempt's cwd never bleeds into
    the retry), raising RuntimeError only after every attempt is exhausted.

    `label` names this agent in the progress output (e.g. "analyst A")."""
    last_err: Exception | None = None
    with progress(label, model, len(prompt)):
        for attempt in range(1, config.MAX_ATTEMPTS + 1):
            with tempfile.TemporaryDirectory() as neutral_cwd:
                log.info("%s — attempt %d/%d", label, attempt, config.MAX_ATTEMPTS)
                try:
                    return invoke_claude_text(prompt, model, neutral_cwd)
                except (subprocess.TimeoutExpired, json.JSONDecodeError, RuntimeError, OSError) as e:
                    last_err = e
                    log.warning("%s — attempt %d failed: %s", label, attempt, e)
                    continue
        raise RuntimeError(f"{label} failed after {config.MAX_ATTEMPTS} attempts: {last_err}")


def _resolve_model(cli_model: str | None, persona_model: str | None, default_model: str) -> str:
    """--model > persona frontmatter model > config default."""
    return cli_model or persona_model or default_model


def _placeholder(prompt: str) -> str:
    return f"DRY RUN — no engine call. Prompt was {len(prompt)} chars."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="study_review",
        description="Automates the two-analyst independent-replication protocol's Mode 1 "
                    "(research/replication-protocol.md): run/locate a study "
                    "report, grade it against its pre-registration with two isolated headless "
                    "Analyst A/B calls plus a validator, and write a plain-language digest.")
    parser.add_argument("study", help="Study name, as passed to "
                        "`python -m scripts.backtest_study run <study>`.")
    parser.add_argument("--skip-run", action="store_true",
                        help="Don't re-run the study; grade the existing <study>-latest.txt "
                             "report as-is.")
    parser.add_argument("--run-args", default="",
                        help="Extra args passed through to the study run, shell-quoted "
                             "(e.g. --run-args '--side debit').")
    parser.add_argument("--pre-reg", default=None,
                        help="Path to the pre-registration file to grade against. Default: "
                             "research/pre-registrations/<study>.md.")
    parser.add_argument("--positions-csv", default=None,
                        help="Path to a positions CSV to inline. Default: "
                             "backtests/study_output/<study>-positions-latest.csv if present.")
    parser.add_argument("--no-positions-csv", action="store_true",
                        help="Skip inlining a positions CSV even if one is found.")
    parser.add_argument("--model", default=None,
                        help="Override the model for ALL roles (analyst A/B, validator, "
                             "digest). Default: each persona file's frontmatter `model:`, "
                             "falling back to this module's config.DEFAULT_*_MODEL.")
    parser.add_argument("--skip-digest", action="store_true",
                        help="Skip the plain-language digest step.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip every claude call; write clearly-labelled placeholder "
                             "files for all four outputs so path resolution / writing is "
                             "exercised token-free.")
    return parser


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = _build_parser().parse_args(argv)
    study = args.study

    report_path = resolve_report(study, args.skip_run, shlex.split(args.run_args))
    report_text = report_path.read_text()
    log.info("Report: %s", report_path)

    section_heading, section_body = load_pre_registration(study, args.pre_reg)
    log.info("Pre-registration section: %s", section_heading)

    positions_csv_text = load_positions_csv(study, args.positions_csv, args.no_positions_csv)

    analyst_persona_model, analyst_persona_body = read_persona(config.ANALYST_PERSONA_FILE)
    validator_persona_model, validator_persona_body = read_persona(config.VALIDATOR_PERSONA_FILE)

    analyst_model = _resolve_model(args.model, analyst_persona_model, config.DEFAULT_ANALYST_MODEL)
    validator_model = _resolve_model(args.model, validator_persona_model, config.DEFAULT_VALIDATOR_MODEL)
    digest_model = args.model or config.DEFAULT_DIGEST_MODEL
    log.info("Models — analyst=%s validator=%s digest=%s", analyst_model, validator_model, digest_model)

    prompt_a = build_analyst_prompt("A", analyst_persona_body, section_heading, section_body,
                                    report_path, report_text, positions_csv_text)
    prompt_b = build_analyst_prompt("B", analyst_persona_body, section_heading, section_body,
                                    report_path, report_text, positions_csv_text)

    config.STUDY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    a_path = config.STUDY_OUTPUT_DIR / f"{study}-review-analyst-a-latest.md"
    b_path = config.STUDY_OUTPUT_DIR / f"{study}-review-analyst-b-latest.md"
    validator_path = config.STUDY_OUTPUT_DIR / f"{study}-review-validator-latest.md"
    digest_path = config.STUDY_OUTPUT_DIR / f"{study}-digest-latest.md"

    written: list[Path] = []

    if args.dry_run:
        analyst_a_output = _placeholder(prompt_a)
        analyst_b_output = _placeholder(prompt_b)
        a_path.write_text(analyst_a_output)
        b_path.write_text(analyst_b_output)
        written += [a_path, b_path]
    else:
        results: dict[str, str] = {}
        errors: dict[str, Exception] = {}
        log.info("Step 1/%d — spawning analyst A + B in parallel, isolated sessions "
                 "(model=%s)", 3 if not args.skip_digest else 2, analyst_model)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(run_with_retries, prompt_a, analyst_model, "analyst A"): "A",
                pool.submit(run_with_retries, prompt_b, analyst_model, "analyst B"): "B",
            }
            for fut in futures:
                role = futures[fut]
                try:
                    results[role] = fut.result()
                except Exception as e:
                    errors[role] = e
                    log.error("Analyst %s failed: %s", role, e)

        # Write whichever succeeded before raising, so a single analyst's
        # failure doesn't discard the other's completed work.
        if "A" in results:
            a_path.write_text(results["A"])
            written.append(a_path)
        if "B" in results:
            b_path.write_text(results["B"])
            written.append(b_path)
        if errors:
            detail = "; ".join(f"{role}: {err}" for role, err in sorted(errors.items()))
            raise RuntimeError(f"analyst run(s) failed ({', '.join(sorted(errors))}): {detail}")

        analyst_a_output = results["A"]
        analyst_b_output = results["B"]

    prompt_validator = build_validator_prompt(
        validator_persona_body, section_heading, section_body, report_path, report_text,
        positions_csv_text, analyst_a_output, analyst_b_output)

    if args.dry_run:
        validator_output = _placeholder(prompt_validator)
    else:
        log.info("Step 2/%d — validator reads both analyst outputs",
                 3 if not args.skip_digest else 2)
        validator_output = run_with_retries(prompt_validator, validator_model, "validator")
    validator_path.write_text(validator_output)
    written.append(validator_path)

    if not args.skip_digest:
        glossary_text = config.GLOSSARY_MD.read_text() if config.GLOSSARY_MD.exists() else None
        prompt_digest = build_digest_prompt(study, report_path, report_text, glossary_text)
        if args.dry_run:
            digest_output = _placeholder(prompt_digest)
        else:
            log.info("Step 3/3 — plain-language digest")
            digest_output = run_with_retries(prompt_digest, digest_model, "digest")
        digest_path.write_text(digest_output)
        written.append(digest_path)

    print(f"\nstudy_review — {study}{' (dry-run)' if args.dry_run else ''}:")
    for p in written:
        print(f"  {p}")

    # The digest lands after the study runner already refreshed the map, so
    # refresh again to pick it up. Best-effort: a broken map must not fail a
    # review whose expensive LLM outputs are already on disk.
    from scripts.study_map.build import refresh_quietly
    mapped = refresh_quietly()
    if mapped:
        print(f"  {mapped}")
