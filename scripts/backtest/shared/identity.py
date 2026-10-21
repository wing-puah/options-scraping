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


def _row_key(r: dict) -> tuple:
    return identity_key(r.get("signal_date", ""), r.get("ticker", ""), r.get("play", ""))


def rows_from_tab(tab: str) -> dict:
    """``{identity key: row}`` for a results tab — the ONE reader every key
    lookup on a tab goes through. A key on several rows (an old duplicate)
    maps to the LAST of them.

    ``get_all_rows`` auto-creates (and returns ``[]`` for) a missing tab, so a
    first run against a fresh tab reads as "nothing written yet" rather than an
    error.
    """
    return {_row_key(r): r for r in sheets_client.get_all_rows(tab)}


def keys_from_tab(tab: str) -> set:
    """Identity keys already present on a results tab (see :func:`rows_from_tab`)."""
    return set(rows_from_tab(tab))


def rows_from_csv(path) -> dict:
    """``{identity key: row}`` from a LOCAL results/proxy CSV — the offline
    counterpart of :func:`rows_from_tab`.

    A missing file is EMPTY, not an error: on a local-only run the CSV does not
    exist until the first write, and "nothing evaluated yet" is exactly what an
    absent file means.

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
        return {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {_row_key(r): r for r in csv.DictReader(f)}


def keys_from_csv(path) -> set:
    """Identity keys from a local CSV (see :func:`rows_from_csv`)."""
    return set(rows_from_csv(path))


# ─── Re-pricing open rows ──────────────────────────────────────────────────────
# A row whose price data ran out before any exit fired is stored
# `path_status = open_at_data_end`. It is the ONE exception to "a play is
# backtested once per tab": both writers re-price it in place, and replace the
# stored row only when the re-price says something new (`reprice_changed`).
# Both writers import these, so they agree on what "open" and "changed" mean.

OPEN_AT_DATA_END = "open_at_data_end"


def open_keys(rows: dict) -> set:
    """Keys of ``{key: row}`` whose stored row is ``open_at_data_end``."""
    return {k for k, r in rows.items()
            if str(r.get("path_status", "")).strip() == OPEN_AT_DATA_END}


def reprice_changed(new: dict, old: dict) -> bool:
    """Should a re-priced row replace the stored one?

    Only a PRICED re-price can (``realized_pnl_pct`` set): a re-price that now
    prices nothing keeps the old row. Then it must say something new — a later
    ``path_data_end``, or a different ``path_status`` or ``exit_reason``.
    Anything else would delete and append the same row, so it is dropped and
    the run stays idempotent.
    """
    if new.get("realized_pnl_pct") in (None, ""):
        return False
    new_end = _parse_analysis_date(new.get("path_data_end", ""))
    old_end = _parse_analysis_date(old.get("path_data_end", ""))
    if new_end is not None and (old_end is None or new_end > old_end):
        return True
    for col in ("path_status", "exit_reason"):
        if str(new.get(col, "") or "").strip() != str(old.get(col, "") or "").strip():
            return True
    return False


def split_repriced(results: list[dict], reprice_rows: dict) -> tuple[list[dict], set]:
    """``(results to write, keys to delete first)``.

    A result whose key is in ``reprice_rows`` is kept only when
    :func:`reprice_changed` says so, and only then is its key deleted. Every
    other result passes through untouched. A re-priced play with NO result
    (skipped, refused) is simply absent: its old row is never deleted.
    """
    kept, replace = [], set()
    for r in results:
        k = _row_key(r)
        if k not in reprice_rows:
            kept.append(r)
        elif reprice_changed(r, reprice_rows[k]):
            kept.append(r)
            replace.add(k)
    return kept, replace


def find_untested(candidates: list[dict], tested: set) -> list[dict]:
    """Candidates whose identity key is not in ``tested``."""
    return [c for c in candidates
            if identity_key(c["signal_date"], c["ticker"], c.get("play", "")) not in tested]
