import logging
import math
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from scipy.stats import norm

from lib.barchart_options import _to_float

from .config import _EXPIRATION_FORMATS

log = logging.getLogger("backtest")


# ─── Black-Scholes (exit fallback only) ────────────────────────────────────────

def _bs_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Black-Scholes option price. T in years."""
    if T <= 0 or sigma <= 0:
        intrinsic = max(0, S - K) if option_type == "Call" else max(0, K - S)
        return intrinsic
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == "Call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def _bs_delta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Black-Scholes delta. T in years. Used only to surface a per-leg model delta
    for validation; the trade's own anchor delta still comes from the flow row."""
    if T <= 0 or sigma <= 0:
        if option_type == "Call":
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm.cdf(d1) if option_type == "Call" else norm.cdf(d1) - 1.0


# ─── Field parsing ─────────────────────────────────────────────────────────────

def _opt_price(row: dict):
    """Actual option trade price from a flow row (the `Trade` column)."""
    for key in ("Trade", "Trade Price", "Last"):
        v = _to_float(row.get(key))
        if v and v > 0:
            return v
    return None


def _row_iv(row: dict):
    iv = _to_float(row.get("IV", row.get("Imp Vol")))
    return iv / 100 if iv is not None else None


def _contract_key(symbol: str, opt_type: str, strike: float, expiration: str) -> tuple:
    return (symbol.upper().strip(), opt_type.strip().title(), round(strike, 4), str(expiration).strip())


def _defined_risk_bounds(legs: list) -> tuple[float, float] | None:
    """Arbitrage-free value clamp for a single-expiration defined-risk structure.

    Independent per-leg pricing from different scrape timestamps can produce a net
    position value outside the structure's possible range — e.g. a debit vertical
    marked below zero, or a butterfly worth more than its wing width. Returns
    (v_min, v_max) to clamp daily marks, or None when the position has no finite
    bound (ratios, naked extra legs) or its payoff is not a single-expiration
    intrinsic function (calendars / diagonals).

    The structure is bounded iff the net call quantity is zero (otherwise the
    value runs to ±∞ as S→∞); the put side is always finite at S→0. When bounded,
    the position value over its whole life stays within the min/max of its
    expiration payoff P(S) = Σ qty·intrinsic(S, K, type), a piecewise-linear
    function whose extrema sit at the strikes (and S=0). Generalises the old
    1:1-vertical [0, width] / [-width, 0] clamp to butterflies, condors, boxes,
    and explicit iron condors.
    """
    if len(legs) < 2:
        return None
    if len({leg.expiration for leg in legs}) != 1:
        return None  # calendar / diagonal: payoff not a single-expiration function
    if sum(leg.qty for leg in legs if leg.opt_type == "Call") != 0:
        return None  # unbounded as S→∞ (ratio, extra naked call)

    def payoff(S: float) -> float:
        total = 0.0
        for leg in legs:
            intrinsic = max(0.0, S - leg.strike) if leg.opt_type == "Call" \
                else max(0.0, leg.strike - S)
            total += leg.qty * intrinsic
        return total

    breakpoints = [0.0] + [leg.strike for leg in legs]
    values = [payoff(S) for S in breakpoints]
    v_min, v_max = min(values), max(values)
    if v_min == v_max:
        return None  # degenerate (e.g. box collapses to a constant — no clamp needed)
    return (v_min, v_max)


def _payoff_floor(legs: list) -> float | None:
    """Minimum expiration payoff min_S Σ qty·intrinsic(S, K, type) of a single-
    expiration position, or None when the downside is unbounded (net short calls
    → payoff → −∞ as S→∞) or the payoff is not a single-expiration intrinsic
    function (calendars / diagonals).

    Deliberately looser than _defined_risk_bounds, which gates the daily-mark
    CLAMP and needs both bounds finite (len≥2, net call qty == 0). Sizing only
    needs the floor, which is finite iff the net call quantity is >= 0 (the
    payoff's final slope is non-negative, so the min sits at S=0 or a strike).
    Single-leg positions are allowed — a naked short put floors at S=0.
    """
    if len({leg.expiration for leg in legs}) != 1:
        return None
    if sum(leg.qty for leg in legs if leg.opt_type == "Call") < 0:
        return None

    def payoff(S: float) -> float:
        return sum(
            leg.qty * (max(0.0, S - leg.strike) if leg.opt_type == "Call"
                       else max(0.0, leg.strike - S))
            for leg in legs)

    return min(payoff(S) for S in [0.0] + [leg.strike for leg in legs])


def _max_loss_per_unit(legs: list, entry_net: float) -> float | None:
    """Structural worst-case loss per unit in option points (positive), or None
    when it cannot be bounded.

      debit  (entry_net > 0): max loss = premium paid = entry_net. (A net-debit
             ratio with naked short legs understates true risk — same convention
             as the existing premium×stop debit sizing.)
      credit (entry_net < 0): max loss = credit received − worst expiration
             payoff = entry_net − _payoff_floor. None when the floor is None
             (net short calls, multi-expiration credit).
    """
    if entry_net > 0:
        return entry_net
    floor = _payoff_floor(legs)
    if floor is None:
        return None
    return entry_net - floor


def _short_strike(structure: str, K_long: float, play_strikes: list, spread_pct: float):
    """
    The contra-leg strike for a spread. Returns None for non-spread / iron condor.
    Used by both pass-1 contract identification and _simulate so the key matches.
    """
    short_from_play = play_strikes[1] if len(play_strikes) >= 2 else None
    if structure == "bull_call_spread":
        return short_from_play if short_from_play else K_long * (1 + spread_pct)
    if structure == "bear_put_spread":
        return short_from_play if short_from_play else K_long * (1 - spread_pct)
    if structure == "bear_call_spread":
        return short_from_play if short_from_play else K_long * (1 + spread_pct)
    if structure == "bull_put_spread":
        return short_from_play if short_from_play else K_long * (1 - spread_pct)
    return None


# ─── Date / expiry parsing ─────────────────────────────────────────────────────

def _parse_expiration(raw: str, fallback: date | None = None) -> date | None:
    """
    Parse the flow row's expiration. The `Expires` column is an ISO datetime with
    offset, e.g. '2026-06-18T16:30:00-05:00'; the leading 10 chars are the date.
    """
    s = str(raw or "").strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    for fmt in _EXPIRATION_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return fallback


def _parse_analysis_date(raw: str) -> date | None:
    """
    Parse the analysis-tab date. We write ISO, but Sheets (USER_ENTERED) reparses
    it and renders per the spreadsheet locale, e.g. '02/06/2026' (DD/MM/YYYY).
    """
    s = str(raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ─── Underlying price (for BS exit fallback) ───────────────────────────────────

_price_cache: dict[str, pd.DataFrame] = {}


def _get_prices(ticker: str, signal_date: date, max_days: int) -> pd.DataFrame:
    end = signal_date + timedelta(days=max_days + 10)
    cache_key = f"{ticker}_{signal_date}_{max_days}"
    if cache_key in _price_cache:
        return _price_cache[cache_key]
    try:
        df = yf.download(ticker, start=signal_date.isoformat(), end=end.isoformat(),
                         auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        _price_cache[cache_key] = df
        return df
    except Exception:
        log.exception("yfinance error for '%s'", ticker)
        return pd.DataFrame()


def _price_on_or_after(prices: pd.DataFrame, target: date):
    if prices.empty:
        return None
    prices.index = pd.to_datetime(prices.index).normalize()
    candidates = prices[prices.index >= pd.Timestamp(target)]
    if candidates.empty:
        return None
    return float(candidates.iloc[0]["Close"])


def _reappearance_price(contract_index, key, checkpoint: date, expiration: date | None):
    """Real Trade price from the first scrape on/after the checkpoint (before expiry)."""
    snaps = contract_index.get(key)
    if not snaps:
        return None
    for snap_date, price in snaps:
        if snap_date >= checkpoint:
            if expiration and snap_date > expiration:
                return None
            return price
    return None


def _price_asof(series, key, day: date, expiration: date | None = None):
    """Real price AS OF `day`: the most recent scrape on-or-before it (carry-forward)."""
    snaps = series.get(key)
    if not snaps:
        return None
    best = None
    for snap_date, price in snaps:
        if snap_date > day:
            break
        if expiration and snap_date > expiration:
            break
        best = price
    return best


# ─── Trading-day grid ──────────────────────────────────────────────────────────

def _weekday_grid(signal_date: date, end_inclusive: date) -> list[date]:
    """Weekdays AFTER the signal date through end_inclusive."""
    out, d = [], signal_date + timedelta(days=1)
    while d <= end_inclusive:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out
