"""
User-tunable settings for the study-review two-analyst replication harness.

Automates research/replication-protocol.md's Mode 1 (replication
grading): resolve a study report, grade it with two isolated Analyst A/B
headless calls plus a validator, and write a plain-language digest. Wires the
protocol's persona files (`.claude/agents/research-analyst.md`,
`.claude/agents/research-validator.md`) into headless `claude -p` calls,
mirroring `scripts/analysis_pipeline`'s fetch → headless-engine → write shape.
This is the one file to edit for paths, model defaults, and retry/timeout
limits — the orchestration logic lives in `core.py`.
"""
from pathlib import Path

# Repo root (…/options-trading), derived from this file's location.
ROOT = Path(__file__).resolve().parents[2]

STUDY_OUTPUT_DIR = ROOT / "backtests" / "study_output"
TUNING_DIR = ROOT / "research"
# No longer read by load_pre_registration() (see PRE_REG_DIR below) — kept as
# a path constant in case a future write-up step wants to append/reference
# current.md directly. Not currently imported by anything outside this file.
CURRENT_MD = TUNING_DIR / "current.md"
GLOSSARY_MD = TUNING_DIR / "glossary.md"

# One file per study, holding that study's pre-registration verbatim. This is
# deliberately NOT current.md: that log is a rolling narrative that gets pruned
# into archive/, so keying a tool off a `## ` heading inside it meant a routine
# prune (or a heading reworded for readability) silently broke `study_review`.
# A pre-registration is an immutable artifact with its own lifecycle, so it gets
# its own file and is read whole — no heading matching anywhere.
PRE_REG_DIR = TUNING_DIR / "pre-registrations"
PRE_REG_PATTERN = "{study}.md"

# Persona files whose bodies are inlined verbatim into the headless prompts.
# Their YAML frontmatter `model:` field (when present) is the primary source
# for that role's model — see read_persona() / core.main()'s resolution order.
ANALYST_PERSONA_FILE = ROOT / ".claude" / "agents" / "research-analyst.md"
VALIDATOR_PERSONA_FILE = ROOT / ".claude" / "agents" / "research-validator.md"


# ──────────────────────────── Run behaviour ────────────────────────
MAX_ATTEMPTS = 3            # retries per headless claude call on failure / bad output
# Seconds between "still running" heartbeat lines while a headless call is in
# flight. These calls are silent for minutes at a time; without a heartbeat an
# operator can't tell a running agent from a hung one. 0 disables it.
HEARTBEAT_S = 60
# Bigger than analysis_pipeline's 600s — these prompts inline a full study
# report + a positions CSV + (for the validator) both analyst outputs.
REQUEST_TIMEOUT_S = 900

# Fallback models, used only when the role's persona frontmatter carries no
# `model:` AND the caller passed no --model. The persona frontmatter model
# wins whenever it is present — these are last-resort defaults.
DEFAULT_ANALYST_MODEL = "opus"
DEFAULT_VALIDATOR_MODEL = "sonnet"
DEFAULT_DIGEST_MODEL = "sonnet"

# {study} → backtests/study_output/<study>-positions-latest.csv. Only
# account_sim produces one today; other studies simply have none to inline.
POSITIONS_CSV_PATTERN = "{study}-positions-latest.csv"
