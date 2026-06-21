import logging
import math
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from scipy.stats import norm

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

def _num(value, default=None):
    """Parse a possibly-formatted number ('$1,234', '71.8%') to float."""
    if value is None:
        return default
    s = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if s == "" or s in ("-", "N/A", "n/a"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _opt_price(row: dict):
    """Actual option trade price from a flow row (the `Trade` column)."""
    for key in ("Trade", "Trade Price", "Last"):
        v = _num(row.get(key))
        if v and v > 0:
            return v
    return None


def _row_iv(row: dict):
    iv = _num(row.get("IV", row.get("Imp Vol")))
    return iv / 100 if iv is not None else None


def _contract_key(symbol: str, opt_type: str, strike: float, expiration: str) -> tuple:
    return (symbol.upper().strip(), opt_type.strip().title(), round(strike, 4), str(expiration).strip())


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
