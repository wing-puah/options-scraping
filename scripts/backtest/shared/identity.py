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
import math
from datetime import date, datetime, timedelta
from pathlib import Path

from lib import sheets_client
from lib.barchart.options import cache_path

from ..config import HISTORY_CACHE, RESULTS_PATH
from ..helpers import _parse_analysis_date
from ..legs import parse_legs

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
# `path_status = open_at_data_end`. It is one of the TWO exceptions to "a play
# is backtested once per tab" (the other: a row whose cache changed, below):
# both writers re-price it in place, and replace the stored row only when the
# re-price says something new (`reprice_changed`). Both writers import these,
# so they agree on what "open", "stale" and "changed" mean.

OPEN_AT_DATA_END = "open_at_data_end"


def open_keys(rows: dict) -> set:
    """Keys of ``{key: row}`` whose stored row is ``open_at_data_end``."""
    return {k for k, r in rows.items()
            if str(r.get("path_status", "")).strip() == OPEN_AT_DATA_END}


#: The columns a simulation writes, on BOTH tabs. A re-priced row replaces the
#: stored one only when one of these differs. Left out on purpose: the identity
#: (`signal_date`, `ticker`, `play`), the bookkeeping `created_datetime`, and
#: what is copied off the analysis row rather than priced (`structure`,
#: `regime`, `market_regime`, `horizon`, the rollup and `score_*` columns, the
#: proxy's `skip_reason`/`proxy_detail`/`legs_original`). A column a writer does
#: not produce (`proxy_method` on BacktestResults) is simply not compared.
SIMULATED_COLUMNS = (
    "legs", "entry_leg_detail", "contracts", "dte_entry", "iv_entry_pct", "delta",
    "entry_underlying", "entry_option_price", "entry_premium_total", "entry_source",
    "realized_pnl_pct", "realized_pnl_abs", "days_held", "exit_reason",
    "mfe_pct", "mfe_abs", "mfe_day", "mae_pct", "mae_abs", "mae_day",
    "pnl_at_cap_pct", "pct_real_days", "daily_price_csv", "daily_source_csv",
    "daily_pnl_csv", "max_loss_per_contract", "pnl_on_risk_pct", "exit_basis",
    "pct_stale_days", "cost_total", "cost_basis", "exit_fill",
    "path_status", "path_data_end", "proxy_method",
)


def _same_cell(a, b) -> bool:
    """One stored cell against one simulated value. Sheets hands numbers back
    as numbers and blanks as ``""``; a simulation may hold ``None``. Numbers
    compare as numbers, dates as dates, everything else as stripped text."""
    sa = "" if a is None else str(a).strip()
    sb = "" if b is None else str(b).strip()
    if sa == sb:
        return True
    try:
        fa, fb = float(sa.replace(",", "")), float(sb.replace(",", ""))
    except ValueError:
        da, db = _parse_analysis_date(sa), _parse_analysis_date(sb)
        return da is not None and da == db
    return math.isclose(fa, fb, rel_tol=1e-9, abs_tol=1e-9)


def changed_columns(new: dict, old: dict) -> list[str]:
    """The :data:`SIMULATED_COLUMNS` the new row produces that differ from the
    stored row."""
    return [c for c in SIMULATED_COLUMNS if c in new and not _same_cell(new[c], old.get(c))]


def reprice_changed(new: dict, old: dict) -> bool:
    """Should a re-priced row replace the stored one?

    Only a PRICED re-price can (``realized_pnl_pct`` set): a re-price that now
    prices nothing keeps the old row. A re-price whose ``path_data_end`` is
    EARLIER than the stored one is a regression (a refetch that came back
    shorter) and keeps the old row too. Otherwise it replaces the stored row
    when any :data:`SIMULATED_COLUMNS` cell differs — a later data end, a new
    exit, or only different marks. An identical re-price would delete and
    append the same row, so it is dropped and the run stays idempotent.
    """
    if new.get("realized_pnl_pct") in (None, ""):
        return False
    new_end = _parse_analysis_date(new.get("path_data_end", ""))
    old_end = _parse_analysis_date(old.get("path_data_end", ""))
    if new_end is not None and old_end is not None and new_end < old_end:
        return False
    return bool(changed_columns(new, old))


# ─── Re-pricing rows whose price cache changed (2026-10-21) ───────────────────
# A finished row is priced from cache files that other plays share. When a
# later run refetches one of those files (a forward refresh for an open row,
# say), the finished row still carries the marks of the old, shorter file, and
# every study that rebuilds it from the cache disagrees with it. Such a row is
# re-simulated from the cache as it stands, with no fetch, and replaced only
# when `reprice_changed` says so.

def parse_created(raw) -> datetime | None:
    """A row's ``created_datetime`` (written as local-time ISO; Sheets hands it
    back as ``YYYY-MM-DD HH:MM:SS``). ``None`` when blank or unparseable."""
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def leg_cache_files(row: dict, cache_dir: Path | None = None) -> list[Path]:
    """The cache files a stored row's ``legs`` were priced from."""
    legs = parse_legs(row.get("legs", "")) or []
    return [cache_path(cache_dir or HISTORY_CACHE, lg.ticker, lg.expiration, lg.strike,
                       lg.opt_type) for lg in legs]


def watch_keys(rows: dict) -> set:
    """Keys of stored rows a cache change could move: PRICED rows that are not
    ``open_at_data_end`` (open rows are re-priced anyway)."""
    return {k for k, r in rows.items()
            if r.get("realized_pnl_pct") not in (None, "")
            and str(r.get("path_status", "")).strip() != OPEN_AT_DATA_END}


def cache_changed_keys(rows: dict, cache_dir: Path | None = None) -> set:
    """Keys of ``{key: row}`` whose leg cache file(s) were rewritten AFTER the
    row was written: a file mtime at least one second past ``created_datetime``
    (which is truncated to the second). Both are local wall-clock time.

    The mtime is the only signature available: a row records no hash of the
    files it read. A restore that resets mtimes (`backup_research_caches.py
    pull` keeps the archived ones) would make every row a candidate; that
    costs one re-simulation per row and writes nothing where nothing changed.
    A row with no parseable ``created_datetime`` is never a candidate.
    """
    out = set()
    for k, r in rows.items():
        created = parse_created(r.get("created_datetime"))
        if created is None:
            continue
        cutoff = (created + timedelta(seconds=1)).timestamp()
        for f in leg_cache_files(r, cache_dir):
            try:
                if f.stat().st_mtime >= cutoff:
                    out.add(k)
                    break
            except FileNotFoundError:
                continue
    return out


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
            log.info("re-price replaces %s %s %s: %s", k[0], k[1], k[2][:30],
                     ", ".join(changed_columns(r, reprice_rows[k])))
            kept.append(r)
            replace.add(k)
    return kept, replace


def find_untested(candidates: list[dict], tested: set) -> list[dict]:
    """Candidates whose identity key is not in ``tested``."""
    return [c for c in candidates
            if identity_key(c["signal_date"], c["ticker"], c.get("play", "")) not in tested]
