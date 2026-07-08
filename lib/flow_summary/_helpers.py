"""Small stateless helpers for the flow-summary package.

Parsing, money/IV formatting, DTE & moneyness bucketing, extrinsic-value
stripping, and the Barchart flow-CSV column-name constants. These are
low-churn building blocks — `core.py` is where the aggregation logic lives.
"""
from __future__ import annotations

from lib.parsing import to_float


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _to_float(x: str | float | int | None) -> float:
    """Parse a Barchart numeric cell to float, 0.0 on failure.

    Thin wrapper over :func:`lib.parsing.to_float` that keeps this package's
    0.0-default contract (many call sites rely on a numeric, not None).
    """
    return to_float(x, 0.0)


def _to_int(x: str | float | int | None) -> int:
    return int(_to_float(x))


def _wmean(weighted_sum: float, weight: float) -> float | None:
    """Weighted mean, or None when no weight was accumulated."""
    return (weighted_sum / weight) if weight > 0 else None


def _classify_sentiment(opt_type: str, side: str) -> str:
    """Apply Barchart's bullish/bearish rules (see config/barchart-reference.md).

    - Call on ask  → bullish
    - Put  on bid  → bullish
    - Call on bid  → bearish
    - Put  on ask  → bearish
    - anything on mid → neutral
    """
    t = (opt_type or "").strip().lower()
    s = (side or "").strip().lower()
    if t == "call" and s == "ask":
        return "bullish"
    if t == "put" and s == "bid":
        return "bullish"
    if t == "call" and s == "bid":
        return "bearish"
    if t == "put" and s == "ask":
        return "bearish"
    return "neutral"


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _fmt_money(x: float) -> str:
    """Compact dollar formatter: 10300100 → '$10.3M', 850000 → '$850K'."""
    if x is None:
        return "$0"
    ax = abs(x)
    sign = "-" if x < 0 else ""
    if ax >= 1_000_000_000:
        return f"{sign}${ax / 1_000_000_000:.2f}B"
    if ax >= 1_000_000:
        return f"{sign}${ax / 1_000_000:.2f}M"
    if ax >= 1_000:
        return f"{sign}${ax / 1_000:.0f}K"
    return f"{sign}${ax:.0f}"


def _fmt_ratio(num: float, den: float) -> str:
    if den <= 0:
        return "∞" if num > 0 else "—"
    return f"{num / den:.2f}"


def _fmt_iv_pts(x: float | None) -> str:
    """Signed IV points for the IVspr / IVskew columns: 12.3 → '+12', None → '—'."""
    if x is None:
        return "—"
    return f"{x:+.0f}"


def _biggest_trade_str(big) -> str:
    """Render a (premium, type, strike, side, dte, time) biggest-trade tuple."""
    if not big:
        return ""
    prem, opt_type, strike, side, dte, _ = big
    return f"{_fmt_money(prem)} {opt_type} ${strike} {side} {int(dte)}d"


# ---------------------------------------------------------------------------
# Barchart flow-CSV column names
# ---------------------------------------------------------------------------

_FLOW_SYMBOL    = "Symbol"
_FLOW_UPRICE    = "Price~"   # underlying price at trade time
_FLOW_TRADE     = "Trade"    # option trade price (per contract)
_FLOW_TYPE      = "Type"
_FLOW_STRIKE    = "Strike"
_FLOW_EXPIRY    = "Expires"   # ISO datetime, e.g. "2026-12-18T16:30:00-06:00"
_FLOW_DTE       = "DTE"
_FLOW_SIDE      = "Side"
_FLOW_PREMIUM   = "Premium"
_FLOW_SIZE      = "Size"
_FLOW_IV        = "IV"
_FLOW_DELTA     = "Delta"
_FLOW_OI        = "Open Int"
_FLOW_OPENFLAG  = "*"
_FLOW_CODE      = "Code"
_FLOW_TIME      = "Time"

# Columns dropped from raw trade rows — low signal for LLM analysis.
# Price~ is in the rollup context; Expires duplicates DTE;
# Bid/Ask x Size and Trade price add noise; Time is not useful at this level.
_RAW_DROP_COLUMNS = frozenset({
    "Price~", "Expires", "Bid x Size", "Ask x Size", "Trade", "Time",
    # Enriched columns: hide from raw trade tables; OI signal is shown as
    # normalized per-ticker aggregates in the breakdown section instead.
    "oi_d", "oi_prev", "oi_change", "vol_d",
    "eod_iv", "eod_delta", "eod_gamma", "eod_vega", "oi_enriched_on",
})

# |delta| at or above this is treated as a stock substitute (financing /
# conversion / replacement) — premium there is mostly intrinsic, not a bet on a
# move. Used for the per-ticker financing share, not to discard the direction.
_FINANCING_DELTA = 0.85

# Lin/Lu/Driessen (2013, appendix) data filters for the IV spread / IV skew,
# after Xing/Zhang/Zhao (2010). Applied to EVERY leg entering either measure —
# traded (lib/flow_summary/core) or backfilled counterpart
# (lib/counterpart_iv.build_iv_lookup). Defined here, the common leaf module of
# producer and consumer, to avoid an import cycle between them (counterpart_iv
# imports this module; importing counterpart_iv from core would re-enter the
# package __init__). The paper's filters (i) stock volume positive and
# (vi) option volume not missing are not observable / vacuous in this data
# source and are intentionally absent.
DTE_LO, DTE_HI = 10, 60              # (vii) time to maturity within 10–60 days
IV_MIN_PTS, IV_MAX_PTS = 3.0, 200.0  # (iii) option IV in [0.03, 2] — points here
MIN_UNDERLYING = 5.0                 # (ii) underlying stock price above $5
MIN_OPTION_PRICE = 0.125             # (iv) option price at least $0.125


# ---------------------------------------------------------------------------
# DTE & moneyness bucketing
# ---------------------------------------------------------------------------

# DTE maturity buckets (label, inclusive upper bound). Mirrors the method files'
# interpretive table: event/gamma, tactical, medium-term, strategic/LEAP.
_DTE_BUCKETS = (("event", 14), ("tact", 60), ("med", 180), ("strat", None))


def _dte_bucket(dte: float) -> str:
    for label, hi in _DTE_BUCKETS:
        if hi is None or dte <= hi:
            return label
    return _DTE_BUCKETS[-1][0]


_MONEYNESS_BANDS = ("deep-OTM", "OTM", "ATM", "ITM", "deep-ITM")


def _otm_pct(strike: float, spot: float, opt_type: str) -> float | None:
    """Signed % from at-the-money: positive = OTM, negative = ITM."""
    if not (strike and spot):
        return None
    if opt_type.lower() == "call":
        return (strike - spot) / spot * 100
    return (spot - strike) / spot * 100


def _expiry_key(row: dict) -> str:
    """Normalized expiration-date string for a flow row (contract identity key).

    The flow feed's ``Expires`` column is a full ISO datetime
    (``2026-12-18T16:30:00-06:00``); the leading 10 chars are the ISO date, which
    is the stable per-contract key. Used to group matched pairs and dedup the OI
    per-contract accumulator — both key on (…, expiration date).
    """
    return str(row.get(_FLOW_EXPIRY, "")).strip()[:10]


def _moneyness(strike: float, spot: float) -> float | None:
    """Strike-to-spot ratio K/S, or None when either input is missing.

    The paper (Lin/Lu/Driessen 2013, appendix A.2, after Xing/Zhang/Zhao 2010)
    defines the IV-skew bands on this ratio: OTM put K/S ∈ [0.80, 0.95], ATM
    call K/S ∈ [0.95, 1.05].
    """
    if not (strike and spot):
        return None
    return strike / spot


def _moneyness_band(otm_pct: float | None) -> str:
    if otm_pct is None:
        return "?"
    if otm_pct > 10:
        return "deep-OTM"
    if otm_pct > 2:
        return "OTM"
    if otm_pct > -2:
        return "ATM"
    if otm_pct > -10:
        return "ITM"
    return "deep-ITM"


def _trade_extrinsic(prem: float, opt_type: str, spot: float, strike: float, size: int) -> float:
    """Extrinsic (time-value) share of a trade's premium, floored at 0.

    Deep-ITM premium is mostly intrinsic — stock exposure, not optionality — so
    ranking on raw premium lets financing/conversion flow pose as conviction.
    When spot or strike is missing the trade is NOT discounted (extrinsic =
    full premium): absence of data is never treated as evidence of financing.
    """
    t = (opt_type or "").strip().lower()
    if spot <= 0 or strike <= 0 or size <= 0 or t not in ("call", "put"):
        return prem
    intrinsic_per_share = max(spot - strike, 0.0) if t == "call" else max(strike - spot, 0.0)
    return max(prem - intrinsic_per_share * size * 100, 0.0)
