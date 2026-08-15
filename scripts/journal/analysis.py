"""
Load the analysis book — the shared source of AnalysisClaude rows.

PRODUCTION TIER. Both `reconcile.py` (what did I trade, and which play was it?)
and `recommend.py` (what should I trade next?) read the book through here, so
they can never disagree about which rows exist or what a date's market regime
was.

TWO SOURCES, IN ORDER. Live Sheets first, because a fill has to be matched
against the analysis that actually preceded it and the tab is the live record.
The `backtests/to_evaluate/*.csv` export is the fallback — the same file
`scripts/live_loop/stage1_map_fills.py` reads — so the pipeline still runs with
no credentials, offline, or when Sheets is down. Which source was used is
returned alongside the data and printed in the report; a journal built off a
stale CSV export must never be mistaken for one built off the live book.

THE MARKET-ROW INVARIANT. Each date's analysis has one `ticker == "MARKET"` row
carrying the top-level regime, plus one row per play. A play row's own `regime`
and `signal` are ticker-specific and are NEVER the market values — see the
invariant comment on `analysis_to_rows()` in scripts/analysis_pipeline/core.py.
So the deployment ladder's "model regime", which is a MARKET-level read, must be
taken from the MARKET row via `market_regime_by_date()` and never from the play
row that happens to be in hand.
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from .config import AC_CSV_FALLBACK, MAX_SIGNAL_AGE_DAYS, SIGNAL_LOOKBACK_DAYS

log = logging.getLogger(__name__)

DEFAULT_TAB = "AnalysisClaude"
MARKET_TICKER = "MARKET"


def load(tab: str = DEFAULT_TAB, *, csv_path=None,
         prefer_sheets: bool = True) -> tuple[pd.DataFrame, str]:
    """Return `(dataframe, source)` where source is 'sheets' or a CSV path.

    Never raises on a Sheets failure — falls back and says so. An empty book is
    returned as an empty frame rather than an exception, because "no analysis for
    this date" is a legitimate state that the report should show as an unmatched
    trade, not a crash.
    """
    csv_path = csv_path or AC_CSV_FALLBACK
    if prefer_sheets:
        try:
            from lib import sheets_client
            rows = sheets_client.get_all_rows(tab)
            if rows:
                log.info("Loaded %d analysis row(s) from Sheets tab '%s'", len(rows), tab)
                return _normalise(pd.DataFrame(rows)), "sheets"
            log.warning("Sheets tab '%s' is empty — falling back to %s", tab, csv_path)
        except Exception as exc:  # noqa: BLE001 - fallback is the whole point
            log.warning("Could not read Sheets tab '%s' (%s) — falling back to %s",
                        tab, exc, csv_path)

    if not csv_path.exists():
        log.error("No analysis available: Sheets unavailable and %s missing", csv_path)
        return _normalise(pd.DataFrame()), "none"

    df = pd.read_csv(csv_path)
    log.info("Loaded %d analysis row(s) from %s", len(df), csv_path)
    return _normalise(df), str(csv_path)


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce the columns the journal depends on to predictable types."""
    for col in ("date", "ticker", "play", "regime", "signal", "mech_cell",
                "horizon", "score_total", "invalidation", "trigger"):
        if col not in df.columns:
            df[col] = "" if col != "score_total" else pd.NA
    df["date"] = df["date"].astype(str).str.strip().str[:10]
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["play"] = df["play"].astype(str)
    return df


def market_regime_by_date(df: pd.DataFrame) -> dict[str, str]:
    """`{date: market regime}` from the MARKET row — the ladder's model regime."""
    if df.empty:
        return {}
    mkt = df[df["ticker"] == MARKET_TICKER]
    return dict(zip(mkt["date"], mkt["regime"].astype(str)))


def mech_cell_by_date(df: pd.DataFrame) -> dict[str, str]:
    """`{date: mech_cell}`, read off the rows rather than recomputed.

    `mech_cell` is written onto every analysis row by the pipeline
    (`scripts/analysis_pipeline/core.py::_mech_cell`) and is market-level, so any
    row for the date carries it. Reading it back keeps the journal consistent
    with what the operator saw at deploy time, even if the SPY/VIX table has
    since been refreshed.
    """
    if df.empty:
        return {}
    out: dict[str, str] = {}
    for d, grp in df.groupby("date"):
        vals = [v for v in grp["mech_cell"].astype(str) if v and v.lower() != "nan"]
        if vals:
            out[str(d)] = vals[0]
    return out


def plays_for_date(df: pd.DataFrame, d: str) -> pd.DataFrame:
    """The play rows for one date — the MARKET row excluded."""
    if df.empty:
        return df
    return df[(df["date"] == str(d)) & (df["ticker"] != MARKET_TICKER)]


def analysis_dates(df: pd.DataFrame) -> list[str]:
    """Every date the book has analysis for, ascending."""
    if df.empty:
        return []
    return sorted({d for d in df["date"] if d and d.lower() != "nan"})


def latest_date(df: pd.DataFrame) -> str | None:
    dates = analysis_dates(df)
    return dates[-1] if dates else None


def candidate_signal_dates(df: pd.DataFrame, fill_date: str,
                           lookback: int = SIGNAL_LOOKBACK_DAYS,
                           max_age_days: int = MAX_SIGNAL_AGE_DAYS) -> list[str]:
    """Dates a fill on `fill_date` could plausibly be acting on, nearest first.

    Derived from the dates the BOOK actually has rather than from a synthetic
    business-day calendar, so market holidays need no separate table and cannot
    silently shift a signal date onto a day that never traded.

    deployment-rules.md §0 fixes the entry basis at the next session's open, so
    the nearest prior analysis date is the expected one; the rest of the window
    exists because a play entered a day or two late is still that play, and
    scoring it NONE would throw away a real match.

    TWO bounds, and the second is not redundant. `lookback` counts BOOK dates,
    which is what makes holidays a non-issue. But if the book has a gap — a
    prompt-version cut-over, a stretch where the pipeline did not run — the three
    nearest prior dates can be YEARS earlier, and a fill would be stamped with a
    signal date from a different era and a different prompt version. So
    `max_age_days` bounds the window in calendar time too. Anything older is not
    a plausible cause of this trade and is dropped, leaving the event honestly
    unmatched rather than falsely attributed.
    """
    try:
        fill = datetime.strptime(str(fill_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        log.warning("Unparseable fill date %r — no signal candidates", fill_date)
        return []

    prior = []
    for d in analysis_dates(df):
        if d >= str(fill_date):
            continue
        try:
            age = (fill - datetime.strptime(d, "%Y-%m-%d").date()).days
        except ValueError:
            continue
        if age <= max_age_days:
            prior.append(d)
    return list(reversed(prior[-lookback:]))
