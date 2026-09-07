"""The ONE row-identity encoding, shared by both backtest writers.

`scripts/backtest` (→ ``BacktestResults``) and `scripts/backtest.proxy`
(→ ``BacktestProxy``) both append to a Sheets tab. ``append_rows`` appends: no
upsert, no undo. So both must be able to ask "is this play already on my tab?"
and BOTH MUST GET THE SAME ANSWER — a second encoding of the key would let the
real backtest and the proxy disagree about what a duplicate even is, which is
the kind of drift that is only discovered months later in an export.

The key is ``(analysis date, TICKER, 60-char play prefix)``:

* the DATE is parsed on both sides, so the Sheets locale reparse (``6/25/2026``
  on the tab vs ``2026-06-25`` in the candidate) cannot cause a phantom re-test;
* the TICKER is upper-cased;
* the PLAY PREFIX disambiguates two plays proposed on the same ticker and date.
  It is a prefix rather than the whole text because a written row's ``play`` is
  the candidate's ``play``, but only the leading part is reliably byte-stable.

The prefix rule is deliberately the same 60-char lower-cased normalisation that
``scripts/backtest_study/lib/book.py::norm_play`` uses to join a book row back
to its ``AnalysisClaude`` row. That is not a coincidence to be tidied away: it
means "a row the studies can join" and "a row the writers call a duplicate" are
the same notion of row identity, in the writer and in the reader.

Lives here rather than in ``proxy.py`` because ``core.py`` must not import
``proxy.py`` — the proxy reads ``BacktestResults`` as an INPUT, so the
dependency only runs one way.
"""
from __future__ import annotations

import csv
import logging
from datetime import date
from pathlib import Path

from lib import sheets_client

from ..config import RESULTS_PATH
from ..helpers import _parse_analysis_date

log = logging.getLogger("backtest")

ROOT = RESULTS_PATH.parent


def play_prefix(play: str) -> str:
    """Normalized play-text prefix used to disambiguate multiple plays on the same
    ticker/date. Whitespace-collapsed, lower-cased, first 60 chars."""
    return " ".join(str(play or "").split())[:60].lower()


def identity_key(signal_date, ticker: str, play: str) -> tuple:
    """``(date, TICKER, play-prefix)`` — the row identity every duplicate check
    on both result tabs keys on. ``signal_date`` may be a ``date`` or any string
    the analysis-date parser accepts (absorbs the Sheets locale reparse)."""
    d = signal_date if isinstance(signal_date, date) else _parse_analysis_date(signal_date)
    return (d, str(ticker or "").strip().upper(), play_prefix(play))


def keys_from_tab(tab: str) -> set:
    """Identity keys already present on a results tab.

    ``get_all_rows`` auto-creates (and returns ``[]`` for) a missing tab, so a
    first run against a fresh tab reads as "nothing written yet" rather than an
    error.
    """
    return {identity_key(r.get("signal_date", ""), r.get("ticker", ""), r.get("play", ""))
            for r in sheets_client.get_all_rows(tab)}


def keys_from_csv(path) -> set:
    """Identity keys from a LOCAL results/proxy CSV — the offline counterpart of
    :func:`keys_from_tab`.

    A missing file is an EMPTY set, not an error: on a local-only run the CSV
    does not exist until the first write, and "nothing evaluated yet" is exactly
    what an absent file means.

    NOTE for callers: ``output.local_csv`` (the real backtest's
    ``backtests/results.csv``) is REWRITTEN each run, so it holds the last run's
    rows and NOT the accumulated book. Only a CSV that accumulates — or the tab
    itself — is a valid duplicate source for ``BacktestResults``.
    """
    csv_path = Path(path)
    if not csv_path.is_absolute():
        csv_path = ROOT / csv_path
    if not csv_path.exists():
        log.info("No local CSV at '%s' — treating as empty", csv_path)
        return set()
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {identity_key(r.get("signal_date", ""), r.get("ticker", ""), r.get("play", ""))
                for r in csv.DictReader(f)}


def find_untested(candidates: list[dict], tested: set) -> list[dict]:
    """Candidates whose identity key is not in ``tested``."""
    return [c for c in candidates
            if identity_key(c["signal_date"], c["ticker"], c.get("play", "")) not in tested]
