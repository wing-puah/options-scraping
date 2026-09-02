"""Shared backtest internals — pure enough (or side-effecting-but-generic enough)
to be imported by sibling modules (e.g. a future ``proxy.py``) WITHOUT pulling in
``scripts/backtest/core.py``. ``core.py`` itself now imports from here too, so
these are the single source of truth for analysis loading, Barchart history
fetching, results output, and per-candidate classify+build.
"""
from .build import classify_and_build  # noqa: F401
