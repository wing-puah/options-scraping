"""
Barchart per-symbol options-overview IV history (IV / IV rank / IV percentile).

Barchart's options-history page (``…/stocks/quotes/{SYM}/options-history``) renders a
DAILY series — up to ~2 years — of options-overview stats INCLUDING **IV rank** and
**IV percentile** (percentile = share of the prior-1-year days whose IV closed below
that day's IV; rank = (IV − 1yr-low)/(1yr-high − 1yr-low)×100). Unlike our own
premium-weighted ``eod_iv`` aggregate, this is Barchart's chain-level metric, already
computed per historical date, so it needs NO percentile math on our side — we just
read the value as of the trade date.

This module holds the pure pieces: the page URL and the feed-row parser. The
authenticated fetch (Playwright feed interception) lives on
``BarchartSession.fetch_options_overview_history``; ``scripts/fetch_iv_percentile.py``
picks the as-of-trade-date values from the parsed series (:mod:`lib.iv_history`) and
appends ``iv``/``iv_rank``/``iv_pct`` as columns onto the compiled flow file, which
``scripts/analysis_pipeline/fetch.py`` reads back per ticker.

FIELD MAPPING: the core-api ``options-historical/get`` feed's field names are known
from a live capture — the exact keys are first in each candidate list below, with a
few generic fallbacks kept for resilience. Values are read typed-top-level first,
else from the display-string ``raw`` sub-dict; ``_to_float`` strips a trailing ``%``.
IV rank / IV percentile are Barchart's 1-year measures on a 0–100 scale. A row is
kept only when at least one of iv / iv_rank / iv_pct parses.

The live feed URL (for reference):
  /proxies/core-api/v1/options-historical/get?symbol=NVDA
    &fields=date,averageVolatility1d,weightedImpliedVolatility,
            weightedImpliedVolatilityChange,impliedVolatilityRank1y,
            impliedVolatilityPercentile1y,putCallVolumeRatio,totalVolume,
            putCallOpenInterestRatio,totalOpenInterest,historicalLastPrice,…
    &orderBy=date&orderDir=desc&limit=65&raw=1
"""
from __future__ import annotations

from datetime import date, datetime

_BASE = "https://www.barchart.com/stocks/quotes"

# Candidate feed keys, exact name first (checked against both the row's typed
# top-level fields and its display-string ``raw`` sub-dict).
_DATE_KEYS = ("date", "tradeTime", "sessionDate", "symbolDate", "time")
_IV_KEYS = ("weightedImpliedVolatility", "impliedVolatility", "ivMean", "iv")
_IVRANK_KEYS = ("impliedVolatilityRank1y", "ivRank", "impliedVolatilityRank", "iv_rank")
_IVPCT_KEYS = ("impliedVolatilityPercentile1y", "ivPercentile",
               "impliedVolatilityPercentile", "iv_percentile")


def options_history_url(symbol: str) -> str:
    """The options-overview history page URL for a symbol."""
    return f"{_BASE}/{symbol.upper().strip()}/options-history"


def _to_float(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", "").replace("%", "").replace("$", "")
    if s in ("", "-", "N/A", "n/a", "NA", "null", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pick(d: dict, keys) -> object:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _field(row: dict, keys):
    """Value for the first matching key. Reads the row's top-level fields first, else
    its ``raw`` sub-dict. If a field is itself a ``{raw, value}`` dict, the formatted
    ``value`` is preferred (it carries the display scale, e.g. "71.00%"), then ``raw``.
    """
    val = _pick(row, keys)
    if val is None:
        val = _pick(row.get("raw") or {}, keys)
    if isinstance(val, dict):
        return val.get("value", val.get("raw"))
    return val


def _parse_date(value) -> date | None:
    s = str(value or "").strip()[:10]
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_iv_history(rows: list[dict]) -> dict[str, dict]:
    """Feed ``data`` rows → ``{YYYY-MM-DD: {"iv", "iv_rank", "iv_pct"}}``.

    ``iv``/``iv_rank``/``iv_pct`` are floats (or None when a field is absent). IV rank
    and IV percentile are on a 0–100 scale as Barchart reports them; ``iv`` is stored
    as returned (informational). Rows with no parseable IV field at all are dropped.
    """
    out: dict[str, dict] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        d = _parse_date(_field(row, _DATE_KEYS))
        if d is None:
            continue
        iv = _to_float(_field(row, _IV_KEYS))
        iv_rank = _to_float(_field(row, _IVRANK_KEYS))
        iv_pct = _to_float(_field(row, _IVPCT_KEYS))
        if iv is None and iv_rank is None and iv_pct is None:
            continue
        out[d.isoformat()] = {"iv": iv, "iv_rank": iv_rank, "iv_pct": iv_pct}
    return out
