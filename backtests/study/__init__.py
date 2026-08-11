"""Tracked, rerunnable backtest-study infrastructure.

Everything under `backtests/` is gitignored (`backtests/*`), so the replay
harness and pooled-book loader that every exit-mechanism/deployment-ladder
study depends on used to exist on one laptop only. This package is the
tracked home for that data layer: `backtests/study/harness.py` (the replay
engine) and `backtests/study/book.py` (the pooled-book loader). Study SCRIPTS
that consume this layer still live under `backtests/` (untracked, one-off);
only the reusable infrastructure moved here.
"""
