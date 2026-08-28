"""
The §5 time-exit rule, expressed as an absolute calendar date.

The rule itself lives in config/backtest.yml (`simulation.time_exit_dte_fraction`)
and is replayed by the frozen research harness as `te_day = int(dte_entry * tef)`
counted in CALENDAR days from entry. This module is the one place production
converts that fraction into an operator-facing date:

    exit_by = entry + int((expiry - entry).days * fraction) calendar days

— the same floor arithmetic, so the printed date can never disagree with what
the backtest would have done. Flooring is also the conservative direction: the
date is at worst one session early, never late. No weekend/holiday roll on
purpose — §5 states a DEADLINE ("exit on or before"), so a Saturday deadline is
satisfied by Friday, and the repo deliberately has no holiday calendar.

DISPLAY-ONLY by contract: nothing here feeds a risk verdict, a cap check, or a
study. Every function returns None when an input is missing (rendered as an em
dash), never a guess — the same missing/zero discipline the greeks get.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import BACKTEST_YML


def time_exit_fraction(path: str | Path | None = None) -> float | None:
    """`simulation.time_exit_dte_fraction` from config/backtest.yml, or None.

    None when the file is unreadable, the key is absent, or it is explicitly
    `null` (the credit block disables the rule exactly that way). NEVER a
    hardcoded 0.75 fallback — a default here would keep printing dates for a
    rule the config no longer carries.
    """
    p = Path(path) if path is not None else BACKTEST_YML
    return _fraction_from(str(p))


@lru_cache(maxsize=None)
def _fraction_from(path_str: str) -> float | None:
    try:
        cfg = yaml.safe_load(Path(path_str).read_text(encoding="utf-8")) or {}
    except OSError:
        return None
    v = (cfg.get("simulation") or {}).get("time_exit_dte_fraction")
    return float(v) if v is not None else None


def is_debit(structure: str | None) -> bool | None:
    """True/False from the shared `mapping.SIDE` table; None for a label it
    does not know.

    None, not False: an unknown structure is "cannot say", and collapsing it to
    False would silently suppress the date on a debit whose label merely
    drifted. Callers must test `is True`, never truthiness of the table hit.
    """
    try:
        from scripts.live_loop.mapping import SIDE
    except ImportError:  # pragma: no cover - alternate sys.path layout
        from live_loop.mapping import SIDE
    label = str(structure or "")
    side = SIDE.get(label)
    if side is not None:
        return side == "debit"
    # classify_structure's single-leg labels ("single long put", "single short
    # call", optionally "(overlay)"-suffixed) are not SIDE keys but their side
    # is unambiguous: a held long single is a debit position, a short one is
    # not. Anything else stays None.
    if label.startswith("single long "):
        return True
    if label.startswith("single short "):
        return False
    return None


def exit_by_date(entry: date | None, expiry: date | None,
                 fraction: float | None) -> date | None:
    """The absolute §5 time-exit deadline for a held position."""
    if entry is None or expiry is None or fraction is None:
        return None
    span = (expiry - entry).days
    if span <= 0:
        return None
    return entry + timedelta(days=int(span * fraction))


def projected_exit_by(entry: date | None, dte_lo: float | None,
                      dte_hi: float | None,
                      fraction: float | None) -> tuple[date, date] | None:
    """The deploy card's projection for a play known only as a DTE range.

    Returns (earliest, latest); a scalar DTE arrives as lo == hi and the two
    collapse to the same date.
    """
    if entry is None or fraction is None or dte_lo is None or dte_hi is None:
        return None
    lo, hi = sorted((float(dte_lo), float(dte_hi)))
    if hi <= 0:
        return None
    return (entry + timedelta(days=int(lo * fraction)),
            entry + timedelta(days=int(hi * fraction)))
