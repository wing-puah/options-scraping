"""
Deterministic price/catalyst scoring for the Step-5 confidence rubric.

Grounds `score_price`/`score_catalyst` in fetched data (Barchart underlying
price history + corporate actions) instead of the model's own recall of a
ticker's chart/calendar. NO-LOOK-AHEAD INVARIANT: `as_of_price_cells` only ever
uses bars on/before `trade_date` — the score must reflect what was knowable
when the play was proposed, not future price action.

`_score_price` is a weighted blend of research-backed sub-signals rather than a
single level check: key level held/broken (Brock/Lakonishok/LeBaron 1992
trading-range breakout), graded nearness to the recent high/low over the 50-bar
window with a 20-bar fallback (George & Hwang 2004 — nearness to the high
dominates past-return momentum), price-vs-SMA20 and SMA20-vs-SMA50 trend
alignment (Han/Yang/Zhou 2013 MA timing), and a deliberately small 5d
follow-through term (raw 1-week returns REVERT on average — Jegadeesh 1990 /
Lehmann 1990 — so it earns weight only as flow-conditioned breakout
confirmation). Neutral plays grade distance-to-pin with linear decay plus
structure-intact checks. Sub-components whose inputs are missing are dropped
and the remaining weights renormalized, so unenriched or partially enriched
rows are never penalized for absent data.

The window lengths, band widths, and weight decimals below are tunable pending
a backtest pass, same treatment as the `OIConfirmPct` bands in
`config/conviction-score.md` — the research fixes the component set and the
ordering (level > nearness > trend ≈ follow-through), not the exact decimals.

Shape mirrors `lib/iv_history.py`: enrichment column constants, an
`as_of_*_cells` picker, and a `*_from_flow_rows` read-back reader. The
enrichment columns are appended to the compiled flow file by a (separate,
not-yet-written) `scripts/collector/fetch_price_catalyst.py`, which must write
`next_earnings`/`last_earnings` as ISO `YYYY-MM-DD` strings and the price
columns as plain decimal strings for `price_catalyst_from_flow_rows` to read
back.

Two deterministic, play-independent per-ticker reads are derived from the same
enriched cells and computed ONCE at rollup time (surfaced to the analysis, then
reused by the scorers — one source of truth):

- `price_read` collapses the four non-key directional sub-signals (the same ones
  `_score_price` weights) into a single signed **price vector in [-1, +1]**: the
  sign is direction (+ bullish / − bearish / ≈0 range-bound) and `|value|` is
  trend strength. `_score_price` shares the sub-signal computation
  (`_directional_subsignals`) and adds only the play-specific key-level term, so
  the rollup vector and the price score never disagree.
- `catalyst_read` exposes earnings proximity as day-deltas from the trade date;
  `_score_catalyst` reads those deltas rather than re-deriving from the raw dates.

Sources
George & Hwang, "The 52-Week High and Momentum Investing",
    J. Finance 2004 — https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2004.00695.x
Han, Yang & Zhou, "A New Anomaly: The Cross-Sectional Profitability of Technical Analysis",
    JFQA 2013 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1656460
Brock, Lakonishok & LeBaron, "Simple Technical Trading Rules and the Stochastic Properties of Stock Returns",
    J. Finance 1992 — https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1992.tb04681.x
Jegadeesh (1990) / Lehmann (1990) short-term reversal — e.g. https://www3.nd.edu/~zda/Reversal.pdf ;
    news-conditioned exception (drift after news): https://www.sciencedirect.com/science/article/abs/pii/S0378426621000261
"""
from __future__ import annotations

import math
from datetime import date

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

# Tunable: _score_price sub-component weights for bullish/bearish plays; must sum to
# 1.0 (missing-input components are dropped and the survivors renormalized, so the
# sum only anchors the fully-enriched case). Weight ordering is research-fixed:
#   key level held/broken (BLL 1992 trading-range breakout; also the play's own
#     stated thesis level) > nearness to the recent high/low (George & Hwang 2004 —
#     nearness to the high dominates past-return momentum) > MA trend checks
#     (Han/Yang/Zhou 2013) ≈ 5d follow-through (small ON PURPOSE: raw 1-week returns
#     revert — Jegadeesh 1990 / Lehmann 1990 — it survives only as flow-conditioned
#     breakout confirmation, never an equal partner to the level check again).
_W_DIR_KEY_LEVEL = 0.30
_W_DIR_NEARNESS_HIGH = 0.25
_W_DIR_TREND_VS_SMA20 = 0.15
_W_DIR_SMA20_VS_SMA50 = 0.15
_W_DIR_FOLLOWTHROUGH_5D = 0.15

# Tunable: _score_price sub-component weights for neutral (pin/range) plays; must sum
# to 1.0, same renormalize-on-missing rule. The graded pin stays dominant (0.50, vs.
# 1.0 all-or-nothing before); the rest are structure-intact checks — short-term
# reversal (Jegadeesh/Lehmann) is itself the evidence that ranges persist.
_W_NEU_PIN = 0.50
_W_NEU_NEAR_SMA20 = 0.20
_W_NEU_LEVEL_IN_20D_RANGE = 0.15
_W_NEU_LOW_DRIFT_5D = 0.15

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


def catalyst_read(cells: dict, trade_date: date) -> dict:
    """Earnings proximity for one ticker's enriched cells, as day-deltas from
    `trade_date`: ``{next_earnings, last_earnings, days_to_next_earnings,
    days_since_last_earnings}``.

    `days_to_next_earnings` is strictly positive (``next_earnings`` is always
    after `trade_date` per `as_of_earnings_cells`); `days_since_last_earnings` is
    ``>= 0``. Either delta is ``None`` when that earnings date is absent.
    Play-independent — surfaced in the rollup (``days_to_next_earnings`` as the
    Earn column) and consumed by `_score_catalyst` so the score and the displayed
    proximity come from the same numbers.
    """
    cells = cells or {}
    next_earnings = cells.get("next_earnings")
    last_earnings = cells.get("last_earnings")
    return {
        "next_earnings": next_earnings,
        "last_earnings": last_earnings,
        "days_to_next_earnings": (next_earnings - trade_date).days if next_earnings is not None else None,
        "days_since_last_earnings": (trade_date - last_earnings).days if last_earnings is not None else None,
    }


def _score_catalyst(cat: dict, flow_intent: str, horizon_days: int | None) -> int:
    max_catalyst = 20 if flow_intent == _VOLATILITY else 15
    if horizon_days is None:
        return 0

    cat = cat or {}
    # Next earnings strictly ahead and within the horizon window -> full credit.
    days_to_next = cat.get("days_to_next_earnings")
    if days_to_next is not None and 0 < days_to_next <= horizon_days:
        return max_catalyst

    # Last earnings on/before the trade date and within the horizon lookback -> half.
    days_since_last = cat.get("days_since_last_earnings")
    if days_since_last is not None and 0 <= days_since_last <= horizon_days:
        return max_catalyst // 2

    return 0


def _weighted_fraction(components: list[tuple[float, float | None]]) -> float:
    """`components` = [(weight, value in [0,1] or None)]. Entries whose value is
    None (input data missing) are dropped and the surviving weights renormalized,
    so missing sub-signals never lower the achievable maximum — only checks that
    FAIL do."""
    present = [(w, v) for w, v in components if v is not None]
    total_w = sum(w for w, _ in present)
    if total_w <= 0:
        return 0.0
    return sum(w * v for w, v in present) / total_w


def _round_half_up(x: float) -> int:
    # Built-in round() is round-half-to-even (round(4.5) == 4), which would quietly
    # shortchange plays landing exactly on a .5 boundary — easy to hit at the
    # VOLATILITY max of 10. A scoring rubric should never round a boundary down.
    return math.floor(x + 0.5)


def _directional_subsignals(cells: dict, bullish: bool) -> dict:
    """The four non-key directional price sub-signals in the requested frame, each
    ``1.0`` (confirms) / ``0.0`` (fails) / ``None`` (input missing):
    ``{nearness, trend_vs_sma20, sma_align, followthrough}``.

    Extracted so the two consumers stay in lock-step: `_score_price` calls it in
    the play's own direction (bullish/bearish) and adds the play-specific
    key-level term; `price_read` calls it in the bullish frame and collapses these
    four into the signed rollup vector. `None` `price_d` -> all `None`.
    """
    cells = cells or {}
    price_d = cells.get("price_d")
    if price_d is None:
        return {"nearness": None, "trend_vs_sma20": None, "sma_align": None, "followthrough": None}

    price_5d_ago = cells.get("price_5d_ago")
    sma20 = cells.get("price_sma20")
    sma50 = cells.get("price_sma50")

    followthrough = None
    if price_5d_ago is not None:
        followthrough = 1.0 if (price_d > price_5d_ago if bullish else price_d < price_5d_ago) else 0.0

    trend_vs_sma20 = None
    if sma20 is not None:
        trend_vs_sma20 = 1.0 if (price_d > sma20 if bullish else price_d < sma20) else 0.0

    sma_align = None
    if sma20 is not None and sma50 is not None:
        sma_align = 1.0 if (sma20 > sma50 if bullish else sma20 < sma50) else 0.0

    # Nearness to the recent high (bearish: low) — 50d window preferred, 20d
    # fallback for rows enriched before the 50d columns existed.
    nearness = None
    high, low = cells.get("price_50d_high"), cells.get("price_50d_low")
    if high is None or low is None:
        high, low = cells.get("price_20d_high"), cells.get("price_20d_low")
    if high is not None and low is not None:
        if high == low:
            nearness = 0.5  # flat window: no directional information either way
        else:
            pos = min(1.0, max(0.0, (price_d - low) / (high - low)))
            nearness = pos if bullish else 1.0 - pos

    return {"nearness": nearness, "trend_vs_sma20": trend_vs_sma20,
            "sma_align": sma_align, "followthrough": followthrough}


def price_read(cells: dict) -> float | None:
    """Deterministic, play-independent per-ticker **price vector** in ``[-1, +1]``.

    Sign is direction (+ bullish / − bearish / ≈0 range-bound), ``|value|`` is
    trend strength. Blends the same four non-key sub-signals `_score_price` uses
    (via `_directional_subsignals`, bullish frame), renormalized over whichever
    are present, into ``bull_fraction ∈ [0,1]``; the vector is
    ``2*bull_fraction - 1``. The play-specific key-level term is deliberately
    excluded — it needs a play's `key_level`, so it can't live in a ticker-level
    read; `_score_price` adds it back per play.

    Returns ``None`` when `price_d` is absent OR every sub-signal is missing, so a
    row with no usable price history reads "—" rather than a spurious −1.
    """
    sub = _directional_subsignals(cells or {}, bullish=True)
    components = [
        (_W_DIR_NEARNESS_HIGH, sub["nearness"]),
        (_W_DIR_TREND_VS_SMA20, sub["trend_vs_sma20"]),
        (_W_DIR_SMA20_VS_SMA50, sub["sma_align"]),
        (_W_DIR_FOLLOWTHROUGH_5D, sub["followthrough"]),
    ]
    if all(v is None for _, v in components):
        return None
    return 2.0 * _weighted_fraction(components) - 1.0


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

    if direction in ("bullish", "bearish"):
        bullish = direction == "bullish"

        key_held = 1.0 if (price_d >= key_level if bullish else price_d <= key_level) else 0.0
        sub = _directional_subsignals(cells, bullish)

        fraction = _weighted_fraction([
            (_W_DIR_KEY_LEVEL, key_held),
            (_W_DIR_NEARNESS_HIGH, sub["nearness"]),
            (_W_DIR_TREND_VS_SMA20, sub["trend_vs_sma20"]),
            (_W_DIR_SMA20_VS_SMA50, sub["sma_align"]),
            (_W_DIR_FOLLOWTHROUGH_5D, sub["followthrough"]),
        ])
        return _round_half_up(fraction * max_price)

    # neutral (or missing/unrecognized — treat as neutral): graded pin + structure checks.
    price_5d_ago = cells.get("price_5d_ago")
    sma20 = cells.get("price_sma20")
    band = abs(key_level) * _NEUTRAL_PIN_BAND_PCT
    distance = abs(price_d - key_level)
    if band <= 0:
        pin = 1.0 if distance == 0 else 0.0  # key_level == 0: exact match only, no division
    else:
        pin = min(1.0, max(0.0, 2.0 - distance / band))  # 1.0 inside band, linear to 0 at 2×

    near_sma20 = None
    if sma20 is not None:
        near_sma20 = 1.0 if abs(price_d - sma20) <= band else 0.0

    level_in_range = None
    high20, low20 = cells.get("price_20d_high"), cells.get("price_20d_low")
    if high20 is not None and low20 is not None:
        level_in_range = 1.0 if low20 <= key_level <= high20 else 0.0

    low_drift = None
    if price_5d_ago is not None:
        low_drift = 1.0 if abs(price_d - price_5d_ago) <= band else 0.0

    fraction = _weighted_fraction([
        (_W_NEU_PIN, pin),
        (_W_NEU_NEAR_SMA20, near_sma20),
        (_W_NEU_LEVEL_IN_20D_RANGE, level_in_range),
        (_W_NEU_LOW_DRIFT_5D, low_drift),
    ])
    return _round_half_up(fraction * max_price)


def compute_play_scores(cells: dict, play: dict, trade_date: date) -> dict:
    """`{"score_price": int, "score_catalyst": int}` for one play, per the Step-5
    rubric maxima (price 20/10, catalyst 15/20 for DIRECTIONAL-or-HEDGE-or-
    SYNTHETIC-STOCK vs VOLATILITY). `cells` is one ticker's dict from
    `price_catalyst_from_flow_rows` (or `{}`/`None` if unenriched) — missing
    data is never penalized beyond 0: price sub-components whose inputs are
    absent are dropped and the remaining weights renormalized.
    """
    flow_intent = str(play.get("flow_intent") or "").strip().upper()
    try:
        horizon_days = int(play.get("horizon"))
    except (TypeError, ValueError):
        horizon_days = None

    return {
        "score_price": _score_price(cells, play, flow_intent),
        "score_catalyst": _score_catalyst(catalyst_read(cells, trade_date), flow_intent, horizon_days),
    }
