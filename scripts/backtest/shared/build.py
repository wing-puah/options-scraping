"""Re-export of the per-candidate classify+build step.

``classify_and_build`` lives in ``scripts/backtest/plays.py`` (it needs that
module's ``_REGISTRY`` of :class:`Play` subclasses and ``apply_tf_s_override``).
Defining it there and re-exporting it here — rather than importing plays.py's
registry INTO this module — avoids a circular import: ``plays.py`` does not
need to import anything back from ``shared``.
"""
from ..plays import classify_and_build  # noqa: F401
