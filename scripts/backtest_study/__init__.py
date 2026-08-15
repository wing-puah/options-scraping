"""Backtest tuning studies — the research tier, kept apart from production.

`scripts/backtest/` prices the book. This package ARGUES about it: replays the
stored paths under alternative exit rules, screens selection subsets, and
validates the deployment ladder. Nothing here is imported by production code or
run on a schedule; every module ends in a plain-text report that becomes an
addendum in `research/current.md`.

Layout:
  run.py       — the runner (`python -m scripts.backtest_study list | run <name>`)
  harness.py   — the frozen exit-replay engine. DO NOT EDIT: every recorded
                 tuning conclusion was produced by exactly this logic.
  book.py      — pooled cross-structure book loader (real + proxy rows).
  protocol.py  — the validation protocol: purged walk-forward splits,
                 date-clustered bootstrap CIs, leave-one-date-out, window cuts.
  <everything else> — individual studies, each pre-registered in
                 research/ before it was run.

This code lived under `backtests/study/` until 2026-08-11 and needed a
gitignore exemption to survive there, since `backtests/*` is disposable scratch.
It is source, so it moved to `scripts/`; the scratch tree keeps only data —
inputs in `backtests/to_evaluate/`, reports in `backtests/study_output/`.
"""
