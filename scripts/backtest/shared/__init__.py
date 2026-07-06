"""Shared backtest internals — pure enough (or side-effecting-but-generic enough)
to be imported by sibling modules (e.g. a future ``proxy.py``) WITHOUT pulling in
``scripts/backtest/core.py``. ``core.py`` itself now imports from here too, so
these are the single source of truth for analysis loading, Barchart history
fetching, results output, and per-candidate classify+build.
"""
from .analysis_io import load_analysis, _load_analysis  # noqa: F401
from .history import fetch_option_histories  # noqa: F401
from .results_io import write_results  # noqa: F401
from .build import classify_and_build  # noqa: F401
