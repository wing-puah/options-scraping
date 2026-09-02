"""Study-review harness — automates the two-analyst replication protocol.

Automates Mode 1 (replication grading) of
`research/replication-protocol.md`: run a `scripts.backtest_study`
report, grade it against its
`research/pre-registrations/<family>/<study>.md` pre-registration with
two isolated headless Analyst A/B calls plus a validator, then write a
plain-language digest. Run it as a module:

    python3 -m scripts.study_review <study>
    python3 -m scripts.study_review <study> --skip-run --dry-run

User-tunable settings (paths, retries, model defaults) live in `config.py`.
Implementation lives in `core.py`.
"""
