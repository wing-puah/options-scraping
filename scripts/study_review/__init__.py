"""Study-review harness — automates the two-analyst replication protocol.

Automates Mode 1 (replication grading) of
`research/replication-protocol.md`: run a `scripts.backtest_study`
report, grade it against its
`research/pre-registrations/<study>.md` pre-registration with
two isolated headless Analyst A/B calls plus a validator, then write a
plain-language digest. Run it as a module:

    python3 -m scripts.study_review <study>
    python3 -m scripts.study_review <study> --skip-run --dry-run

User-tunable settings (paths, retries, model defaults) live in `config.py`.
Implementation lives in `core.py`.
"""
from .config import (
    ANALYST_PERSONA_FILE,
    GLOSSARY_MD,
    POSITIONS_CSV_PATTERN,
    PRE_REG_DIR,
    PRE_REG_PATTERN,
    STUDY_OUTPUT_DIR,
    TUNING_DIR,
    VALIDATOR_PERSONA_FILE,
)
from .core import (
    build_analyst_prompt,
    build_digest_prompt,
    build_validator_prompt,
    invoke_claude_text,
    load_positions_csv,
    load_pre_registration,
    main,
    read_persona,
    resolve_report,
    run_with_retries,
)

__all__ = [
    "ANALYST_PERSONA_FILE", "GLOSSARY_MD", "POSITIONS_CSV_PATTERN",
    "PRE_REG_DIR", "PRE_REG_PATTERN",
    "STUDY_OUTPUT_DIR", "TUNING_DIR", "VALIDATOR_PERSONA_FILE",
    "build_analyst_prompt", "build_digest_prompt", "build_validator_prompt",
    "invoke_claude_text", "load_positions_csv", "load_pre_registration", "main",
    "read_persona", "resolve_report", "run_with_retries",
]
