"""
Deterministic price/catalyst scoring for the Step-5 confidence rubric.

Grounds `score_price`/`score_catalyst` in fetched data (Barchart underlying
price history + corporate actions) instead of the model's own recall of a
ticker's chart/calendar. NO-LOOK-AHEAD INVARIANT: `as_of_price_cells` only ever
uses bars on/before `trade_date` — the score must reflect what was knowable
when the play was proposed, not future price action.

The 5-bar/20-bar/50-bar windows and the neutral pin-band width below are tunable
pending a backtest pass, same treatment as the `OIConfirmPct` bands in
`config/conviction-score.md` — not load-bearing choices, just reasonable
defaults to start from. The 50-bar window (`price_50d_high`/`price_50d_low`/
`price_sma50`) is enrichment-only, same as the 20-bar one — neither is wired
into `_score_price` yet.

Shape mirrors `lib/iv_history.py`: enrichment column constants, an
`as_of_*_cells` picker, and a `*_from_flow_rows` read-back reader. The
enrichment columns are appended to the compiled flow file by a (separate,
not-yet-written) `scripts/collector/fetch_price_catalyst.py`, which must write
`next_earnings`/`last_earnings` as ISO `YYYY-MM-DD` strings and the price
columns as plain decimal strings for `price_catalyst_from_flow_rows` to read
back.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from lib.parsing import to_float

PRICE_CATALYST_ENRICH_COLUMNS = [
    "price_d", "price_5d_ago", "price_20d_high", "price_20d_low", "price_sma20",
    "price_50d_high", "price_50d_low", "price_sma50",
    "next_earnings", "last_earnings",
]
PRICE_CATALYST_MARKER_COLUMN = "price_catalyst_enriched_on"

# Tunable: how many trailing bars "5 sessions ago" / the high-low-SMA windows look back.
_LOOKBACK_BARS = 5
_TRAILING_WINDOW = 20
_TRAILING_WINDOW_50 = 50

# Tunable: how close price_d must sit to key_level (as a fraction of key_level) for a
# `neutral` play's "structure intact" check to earn full credit.
_NEUTRAL_PIN_BAND_PCT = 0.03

_VOLATILITY = "VOLATILITY"


def _parse_iso_date(value) -> date | None:
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def as_of_price_cells(series: list[tuple[date, float]], trade_date: date) -> dict:
    """Price cells derived ONLY from bars on/before `trade_date` (no look-ahead).

    `series` is a sorted `[(date, mark)]` list (the shape
    `lib.barchart.options.parse_history_series` returns). Returns
    `{price_d, price_5d_ago, price_20d_high, price_20d_low, price_sma20,
    price_50d_high, price_50d_low, price_sma50}`, each `float | None`.
    """
    keys = ("price_d", "price_5d_ago", "price_20d_high", "price_20d_low", "price_sma20",
            "price_50d_high", "price_50d_low", "price_sma50")
    trailing = sorted((d, v) for d, v in (series or []) if d <= trade_date)
    if not trailing:
        return {k: None for k in keys}

    price_d = trailing[-1][1]
    price_5d_ago = trailing[-(_LOOKBACK_BARS + 1)][1] if len(trailing) >= _LOOKBACK_BARS + 1 else None
    window = [v for _, v in trailing[-_TRAILING_WINDOW:]]
    window50 = [v for _, v in trailing[-_TRAILING_WINDOW_50:]]

    return {
        "price_d": price_d,
        "price_5d_ago": price_5d_ago,
        "price_20d_high": max(window),
        "price_20d_low": min(window),
        "price_sma20": sum(window) / len(window),
        "price_50d_high": max(window50),
        "price_50d_low": min(window50),
        "price_sma50": sum(window50) / len(window50),
    }


def as_of_earnings_cells(actions: list[dict], trade_date: date) -> dict:
    """`{next_earnings, last_earnings}` (each `date | None`) from
    `lib.barchart.corporate_actions.parse_corporate_actions` output, filtered to
    `event_type == "Earnings"`. `next_earnings` is the earliest Earnings date
    strictly after `trade_date`; `last_earnings` is the latest on or before it.
    """
    earnings = sorted(
        a["date"] for a in (actions or []) if a.get("event_type") == "Earnings" and a.get("date") is not None
    )
    next_earnings = next((d for d in earnings if d > trade_date), None)
    past = [d for d in earnings if d <= trade_date]
    last_earnings = past[-1] if past else None
    return {"next_earnings": next_earnings, "last_earnings": last_earnings}


def price_catalyst_from_flow_rows(flow_rows: list[dict]) -> dict[str, dict]:
    """`{UPPER_SYMBOL: {...cells...}}` read off enriched flow rows.

    Mirrors `lib.iv_history.iv_pct_from_flow_rows`: keyed by the upper-cased
    `Symbol` column, first occurrence per symbol wins (enrichment writes the
    same value onto every row of a ticker). Price columns are parsed as plain
    floats; `next_earnings`/`last_earnings` as ISO `YYYY-MM-DD` dates. Blank
    cells parse to `None` rather than being skipped.
    """
    out: dict[str, dict] = {}
    for r in flow_rows or []:
        sym = str(r.get("Symbol") or "").strip().upper()
        if not sym or sym in out:
            continue
        out[sym] = {
            "price_d": to_float(r.get("price_d")),
            "price_5d_ago": to_float(r.get("price_5d_ago")),
            "price_20d_high": to_float(r.get("price_20d_high")),
            "price_20d_low": to_float(r.get("price_20d_low")),
            "price_sma20": to_float(r.get("price_sma20")),
            "price_50d_high": to_float(r.get("price_50d_high")),
            "price_50d_low": to_float(r.get("price_50d_low")),
            "price_sma50": to_float(r.get("price_sma50")),
            "next_earnings": _parse_iso_date(r.get("next_earnings")),
            "last_earnings": _parse_iso_date(r.get("last_earnings")),
        }
    return out


def _score_catalyst(cells: dict, flow_intent: str, trade_date: date, horizon_days: int | None) -> int:
    max_catalyst = 20 if flow_intent == _VOLATILITY else 15
    if horizon_days is None:
        return 0

    cells = cells or {}
    next_earnings = cells.get("next_earnings")
    if next_earnings is not None and trade_date < next_earnings <= trade_date + timedelta(days=horizon_days):
        return max_catalyst

    last_earnings = cells.get("last_earnings")
    if last_earnings is not None and trade_date - timedelta(days=horizon_days) <= last_earnings <= trade_date:
        return max_catalyst // 2

    return 0


def _score_price(cells: dict, play: dict, flow_intent: str) -> int:
    max_price = 10 if flow_intent == _VOLATILITY else 20

    key_level = to_float(play.get("key_level"))
    if key_level is None:
        return 0

    cells = cells or {}
    price_d = cells.get("price_d")
    if price_d is None:
        return 0

    direction = str(play.get("direction") or "").strip().lower()
    price_5d_ago = cells.get("price_5d_ago")
    half = max_price // 2
    other_half = max_price - half

    if direction == "bullish":
        score = 0
        if price_d >= key_level:
            score += half
        if price_5d_ago is not None and price_d > price_5d_ago:
            score += other_half
        return score

    if direction == "bearish":
        score = 0
        if price_d <= key_level:
            score += half
        if price_5d_ago is not None and price_d < price_5d_ago:
            score += other_half
        return score

    # neutral (or missing/unrecognized — treat as neutral): structure-intact pin check.
    band = abs(key_level) * _NEUTRAL_PIN_BAND_PCT
    return max_price if abs(price_d - key_level) <= band else 0


def compute_play_scores(cells: dict, play: dict, trade_date: date) -> dict:
    """`{"score_price": int, "score_catalyst": int}` for one play, per the Step-5
    rubric maxima (price 20/10, catalyst 15/20 for DIRECTIONAL-or-HEDGE-or-
    SYNTHETIC-STOCK vs VOLATILITY). `cells` is one ticker's dict from
    `price_catalyst_from_flow_rows` (or `{}`/`None` if unenriched) — missing
    data is never penalized beyond 0.
    """
    flow_intent = str(play.get("flow_intent") or "").strip().upper()
    try:
        horizon_days = int(play.get("horizon"))
    except (TypeError, ValueError):
        horizon_days = None

    return {
        "score_price": _score_price(cells, play, flow_intent),
        "score_catalyst": _score_catalyst(cells, flow_intent, trade_date, horizon_days),
    }
