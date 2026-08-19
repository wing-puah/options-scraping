"""Per-leg / per-position Greeks read from the cached option-history CSVs.

Pure infrastructure: reads the SAME per-contract cache `f3_structure/bear_rewrap.py`'s
`leg_details` reads (`lib.barchart.options.cache_path` + `parse_history_details`),
and does no scraping, sizing, or study logic of its own. `lib/` placement is
deliberate — a shared helper here stays out of `scripts.backtest_study.run`'s
discovery and `study_map.catalog`'s registry (no catalog entry, no verdict);
per repo layering rules this module MUST NOT import from any study module
(`f1_*`/`f2_*`/`f3_*`/`f4_*`), so the "first grid day every leg is cached" scan
`entry_date_for` performs in `bear_rewrap.py` is duplicated here rather than
imported.

Cached-CSV columns (see `lib/barchart/options.py` module docstring): `Time,
Open, High, Low, Latest, Change, %Change, Volume, Open Int, IV, Delta, Gamma,
Theta, Vega, Rho, Theo, Price~, Bid, Ask`. Greek columns are read by their
exact title-case header name (`"Delta"`, `"Gamma"`, `"Theta"`, `"Vega"`) and
parsed with `lib.parsing.to_float`, never a raw `float()` — the cache carries
Barchart's usual punctuation/sentinel cells (`"-"`, thousands commas, ...).

No caching layer is kept across calls (unlike `bear_rewrap._details_cache`):
this module is read rarely enough per study that a fresh read per lookup is
simpler and cannot go stale across a monkeypatched cache directory in tests.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path, parse_history_details  # noqa: E402
from lib.parsing import to_float  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402

GREEK_NAMES = ("Delta", "Gamma", "Theta", "Vega")


def _leg_rows(leg) -> dict[date, dict]:
    """`{date: row}` for one leg's cached history, or `{}` if the cache file
    is missing or unreadable. Mirrors `bear_rewrap.leg_details` minus its
    module-level cache."""
    path = cache_path(HISTORY_CACHE, leg.ticker, leg.expiration, leg.strike, leg.opt_type)
    if not path.exists():
        return {}
    try:
        return parse_history_details(path.read_text(), require_mark=False)
    except Exception:
        return {}


def leg_greek(leg, day: date, name: str) -> float | None:
    """The named greek ("Delta","Gamma","Theta","Vega") of one leg on `day`
    (datetime.date), SIGNED for direction (short leg -> negated) and scaled by
    abs(qty). None if the leg's cache file or that day's row/field is missing.
    """
    row = _leg_rows(leg).get(day)
    if row is None:
        return None
    # Barchart writes SENTINEL sessions with IV, Delta, Gamma, Theta, Vega,
    # Rho, Theo all literally 0 while the mark is real (e.g. COIN 2026-03-27
    # 255P on 2026-03-19: mark $53.25, every greek 0). A real option never
    # quotes zero implied vol, so a missing-or-zero IV marks the whole row's
    # greek block as absent -- and the repo invariant is that an absent greek
    # is None, never 0.0. Found 2026-08-19 when financed_spread's amendment-2
    # costing exposed a deep-ITM put picked as a "0.00-delta" candidate.
    iv = to_float(row.get("IV"))
    if not iv:
        return None
    raw = to_float(row.get(name))
    if raw is None:
        return None
    sign = -1.0 if leg.qty < 0 else 1.0
    return sign * abs(leg.qty) * raw


def entry_greeks(legs, day: date) -> dict:
    """Net signed greeks across legs at `day`:
    {"delta": float|None, "gamma": ..., "theta": ..., "vega": ...}.
    ALL-OR-NOTHING per greek: if ANY leg's value is missing, that greek is None,
    never a partial sum -- the repo invariant is 'a missing greek is None, never
    0.0' (see CLAUDE.md Invariants).
    """
    out: dict = {}
    for name in GREEK_NAMES:
        total = 0.0
        complete = True
        for leg in legs:
            g = leg_greek(leg, day, name)
            if g is None:
                complete = False
                break
            total += g
        out[name.lower()] = total if complete else None
    return out


def _common_entry_day(legs, grid: list[date]) -> date | None:
    """First grid day on which EVERY leg has a cached row (row presence only,
    not a specific greek) -- the same "common entry day" `bear_rewrap.
    entry_date_for` computes for pricing, duplicated here per the lib/
    layering rule above rather than imported. This is also the day production
    filled the structure's entry price, so it is the day the stored `delta`
    on a book record was measured against."""
    rows_by_leg = [_leg_rows(leg) for leg in legs]
    for day in grid:
        if all(day in rows for rows in rows_by_leg):
            return day
    return None


def delta_agreement(rec: dict) -> float | None:
    """|leg-sum delta - stored rec['delta']| at the record's common entry day.
    None if either side is unavailable. `rec` is a book record from
    scripts.backtest_study.lib.book.load_book (has rec["t"] with .legs and the
    entry day, and rec["delta"]).

    "The record's common entry day" is the first day of `rec["t"].grid` on
    which every leg has a cached row (see `_common_entry_day`) -- the day the
    stored `delta` was measured against, since that is also the day production
    priced the structure's entry.
    """
    t = rec.get("t")
    if t is None:
        return None
    legs = getattr(t, "legs", None)
    if not legs:
        return None
    stored = rec.get("delta")
    if stored is None:
        return None
    day = _common_entry_day(legs, t.grid)
    if day is None:
        return None
    leg_sum = entry_greeks(legs, day)["delta"]
    if leg_sum is None:
        return None
    return abs(leg_sum - stored)
