"""
Per-ticker IV percentile — the per-name "rich vs cheap" read the framework's Step-4
structure ladder needs to choose TF (debit) vs TF-S (credit).

Volatility regime today is market-level only (`lib/vol_snapshot.py`: VIX term
structure). The Step-4 ladder's "low IV / high IV" columns are *per-ticker* — a 40%
IV is cheap on NVDA, rich on KO — but no per-name "rich/cheap" metric existed, so the
model defaulted every trend play to a debit spread (TF). Rich IV is exactly where a
debit spread underperforms and where TF-S / credit should take over.

The source is Barchart's **options-overview history** (scraped by
`scripts/collector/fetch_iv_percentile.py` via `BarchartSession.fetch_options_overview_history` →
parsed by `lib/barchart/iv_history.py`): a daily series that already carries Barchart's
**IV rank** and **IV percentile** per historical date. So there is NO percentile to
compute here — we read the value AS OF the trade date and APPEND it, along with the IV
level and IV rank, as columns onto every row of that ticker in the compiled flow file
(the same enrich-in-place pattern as `scripts/collector/enrich_oi.py`; NOT a separate cache tab).
`scripts/analysis_pipeline/fetch.py` then reads `iv_pct` straight back off those rows.

This module is pure: the enrichment column names, the as-of-date series pick (with a
staleness fallback), and the flow-row → `{SYMBOL: iv_pct}` reader for the consumer.
Scrape + Drive I/O live in `scripts/collector/fetch_iv_percentile.py` (producer) and
`scripts/analysis_pipeline/fetch.py` (consumer).
"""
from __future__ import annotations

import logging
from datetime import date

from lib.parsing import to_float

log = logging.getLogger(__name__)

# Columns appended to every flow row, in this order. Lowercase + underscores so the
# header is robust to whitespace/case quirks when the CSV is read back (matches
# enrich_oi's convention).
# CONVENTION (see the project's percentages-as-decimals rule): `iv_rank` and `iv_pct`
# are stored as **decimal fractions** (0.71, not 71) so the Sheet cells format as %.
# `iv` is an IV *level* and stays in points (55.32), like iv_spread/iv_skew.
IV_ENRICH_COLUMNS = ["iv", "iv_rank", "iv_pct"]

# Provenance + resume marker: set to the run date for every ticker we ATTEMPT (even
# when Barchart returns nothing), so resume can tell "scraped, empty" from "not yet
# scraped" and never re-fetches an empty ticker.
IV_MARKER_COLUMN = "iv_pct_enriched_on"
IV_ALL_COLUMNS = IV_ENRICH_COLUMNS + [IV_MARKER_COLUMN]

# How stale an as-of-date pick may be: if the exact date has no row (e.g. a live run
# before the session's EOD row is published), fall back to the most recent row within
# this many calendar days on/before the anchor. Beyond that, treat as no data.
LOOKUP_STALENESS_DAYS = 5


def _fmt(v) -> str:
    return "" if v is None else str(v)


def _fmt_decimal(v) -> str:
    """A 0–100 rank/percentile → decimal-fraction string (71.0 → '0.71'), blank on None.

    Follows the project convention that %/share values are stored as decimals so the
    Sheet cell formats as a percentage."""
    return "" if v is None else str(round(v / 100.0, 4))


def as_of_iv_cells(series: dict[str, dict], anchor_iso: str,
                   staleness_days: int = LOOKUP_STALENESS_DAYS) -> dict[str, str]:
    """Formatted ``{iv, iv_rank, iv_pct}`` cells for a ticker as of ``anchor_iso``.

    ``series`` is ``{YYYY-MM-DD: {"iv", "iv_rank", "iv_pct"}}`` (rank/percentile on a
    0–100 scale) from :func:`lib.barchart.iv_history.parse_iv_history`. Uses the exact
    anchor-date row; if absent, the most recent row within ``staleness_days`` on/before
    the anchor (so a live run before the EOD row is published still gets yesterday's
    values). Returns blanks when nothing is in range. ``iv_rank``/``iv_pct`` come out as
    decimal-fraction strings; ``iv`` stays in points.
    """
    blank = {c: "" for c in IV_ENRICH_COLUMNS}
    try:
        anchor = date.fromisoformat(anchor_iso)
    except (TypeError, ValueError):
        return blank

    best_iso: str | None = None
    for iso in series:
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        if d > anchor or (anchor - d).days > staleness_days:
            continue
        if best_iso is None or iso > best_iso:
            best_iso = iso
    if best_iso is None:
        return blank

    v = series[best_iso]
    return {
        "iv": _fmt(v.get("iv")),
        "iv_rank": _fmt_decimal(v.get("iv_rank")),
        "iv_pct": _fmt_decimal(v.get("iv_pct")),
    }


def iv_pct_from_flow_rows(rows) -> dict[str, float]:
    """``{UPPER_SYMBOL: iv_pct}`` read off enriched flow rows' ``iv_pct`` column.

    The column is a decimal fraction (written by the enricher); one value per symbol
    (identical across a ticker's rows), first non-blank wins. Blanks are skipped — the
    caller then leaves IVpct blank and the framework falls back to the VIX proxy. This
    is how the analysis consumes the enrichment; no tab lookup.
    """
    out: dict[str, float] = {}
    for r in rows or []:
        sym = str(r.get("Symbol") or "").strip().upper()
        if not sym or sym in out:
            continue
        pct = to_float(r.get("iv_pct"))
        if pct is not None:
            out[sym] = pct
    return out
