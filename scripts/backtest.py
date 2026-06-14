"""
Analysis-driven backtesting engine for options plays.

Reads LLM analysis from Google Sheets (AnalysisClaude / AnalysisGPT), identifies
the option contract from each play's text, and prices the trade using the locally
cached Barchart per-contract price history (backtests/option_history_cache/).

Pricing philosophy (real data first, model last):
  Entry  — Barchart per-contract history (mid bid/ask) on/after the signal date.
  Exit   — Barchart per-contract history on each subsequent trading day.
           Falls back to Black-Scholes when history is absent for a day.
Every trade is tagged with entry_source / exit_source so the win rate can be
reported on the real-data subset separately from the modelled one.

Usage:
  python3 scripts/backtest.py --config config/backtest.yml
  python3 scripts/backtest.py --config config/backtest.yml --tab AnalysisGPT
  python3 scripts/backtest.py --config config/backtest.yml --start 2026-01-01 --end 2026-04-30
  python3 scripts/backtest.py --config config/backtest.yml --dry-run
"""
import argparse
import asyncio
import csv
import logging
import math
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import yfinance as yf
from dotenv import load_dotenv
from scipy.stats import norm

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.logger import setup_logging
from lib import sheets_client
from lib import barchart_options
from lib.barchart import BarchartSession

log = logging.getLogger("backtest")

RESULTS_PATH = Path(__file__).parent.parent / "backtests"
HISTORY_CACHE = RESULTS_PATH / "option_history_cache"

_EXPIRATION_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d")

# Structures that remain unsupported (too complex or involve stock positions).
# Iron condor, short puts/calls, and credit spreads are now handled separately.
_UNSUPPORTED_PATTERNS = (
    "condor",     # regular (non-iron) condor
    "strangle", "straddle", "calendar", "diagonal",
    "covered",    # covered calls/puts involve a stock leg we cannot model
    "butterfly",
)


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


def _bs_spread_price(S, K_long, K_short, T, r, sigma, option_type) -> float:
    return _bs_price(S, K_long, T, r, sigma, option_type) - _bs_price(S, K_short, T, r, sigma, option_type)


def _short_strike(structure: str, K_long: float, play_strikes: list, spread_pct: float):
    """
    The contra-leg strike for a spread. For debit spreads K_long is the bought leg;
    for credit spreads it is the sold leg. Returns None for non-spread / iron condor.
    Used by both pass-1 (contract registration) and _simulate so the key matches.
    """
    short_from_play = play_strikes[1] if len(play_strikes) >= 2 else None
    # Debit spreads: K_long = bought leg; contra = sold leg (further OTM).
    if structure == "bull_call_spread":
        return short_from_play if short_from_play else K_long * (1 + spread_pct)
    if structure == "bear_put_spread":
        return short_from_play if short_from_play else K_long * (1 - spread_pct)
    # Credit spreads: K_long = sold leg; contra = protection/hedge leg (further OTM).
    if structure == "bear_call_spread":
        return short_from_play if short_from_play else K_long * (1 + spread_pct)
    if structure == "bull_put_spread":
        return short_from_play if short_from_play else K_long * (1 - spread_pct)
    return None


# ─── Field parsing helpers ─────────────────────────────────────────────────────

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


def _parse_expiration(raw: str, fallback: date | None = None) -> date | None:
    """
    Parse the flow row's expiration. The `Expires` column is an ISO datetime with
    offset, e.g. '2026-06-18T16:30:00-05:00'; the leading 10 chars are the date.
    Also handles a few bare date formats.
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
    Try ISO first, then day-first, then month-first.
    """
    s = str(raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ─── Play classification ───────────────────────────────────────────────────────

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def _extract_expiration(play_text: str, ref: date) -> date | None:
    """
    Pull the expiration the play names, e.g. 'Jun 18', 'June 26', 'Jul 17'. Year is
    inferred from the signal date (rolls to next year if the month already passed).
    """
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})",
                  play_text, re.IGNORECASE)
    if not m:
        return None
    mon, day = _MONTHS[m.group(1)[:3].lower()], int(m.group(2))
    try:
        d = date(ref.year, mon, day)
    except ValueError:
        return None
    return d if d >= ref else date(ref.year + 1, mon, day)


def _extract_strikes(play_text: str) -> list[float]:
    """
    Pull the strike(s) the play names.
    - 4-strike: 'Iron condor 480/490/510/520' → [480, 490, 510, 520]
    - 2-strike: 'Bull call spread 485/510'    → [485, 510]
    - 1-strike: 'Long calls 225'              → [225]
    """
    m4 = re.search(
        r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)",
        play_text,
    )
    if m4:
        return [float(m4.group(i)) for i in range(1, 5)]
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", play_text)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    m = re.search(r"(?:calls?|puts?)\s+(\d+(?:\.\d+)?)", play_text, re.IGNORECASE)
    if m:
        return [float(m.group(1))]
    return []


def classify_play(play_text: str) -> dict:
    """
    Determine the trade structure, direction, and strikes from a play string.

    Returns dict with:
      structure   — long_call | long_put | bull_call_spread | bear_put_spread
                    | bear_call_spread | bull_put_spread | short_call | short_put
                    | iron_condor | unsupported
      option_type — Call | Put | None
      strikes     — parsed strikes (may be empty); 4 for iron condors
      is_credit   — True for premium-selling structures (net credit at entry)
    """
    text = (play_text or "").lower()
    if not text.strip():
        return {"structure": "unsupported", "option_type": None, "strikes": [], "is_credit": False}

    strikes = _extract_strikes(play_text)

    # Iron condor must be checked before the "condor" unsupported pattern.
    if "iron condor" in text:
        return {"structure": "iron_condor", "option_type": None, "strikes": strikes, "is_credit": True}

    for pat in _UNSUPPORTED_PATTERNS:
        if pat in text:
            return {"structure": "unsupported", "option_type": None, "strikes": [], "is_credit": False}

    # Named credit spreads (before generic "call/put spread" fallbacks).
    if "bear call spread" in text:
        return {"structure": "bear_call_spread", "option_type": "Call", "strikes": strikes, "is_credit": True}
    if "bull put spread" in text:
        return {"structure": "bull_put_spread", "option_type": "Put", "strikes": strikes, "is_credit": True}

    # Named debit spreads.
    if "bull call spread" in text:
        return {"structure": "bull_call_spread", "option_type": "Call", "strikes": strikes, "is_credit": False}
    if "bear put spread" in text:
        return {"structure": "bear_put_spread", "option_type": "Put", "strikes": strikes, "is_credit": False}

    # Generic "call spread" / "put spread": infer debit vs credit from context.
    _credit_words = frozenset(("credit", "sell", "short", "write", "sold"))
    if "call spread" in text:
        is_credit = bool(_credit_words & set(text.split()))
        structure = "bear_call_spread" if is_credit else "bull_call_spread"
        return {"structure": structure, "option_type": "Call", "strikes": strikes, "is_credit": is_credit}
    if "put spread" in text:
        is_credit = bool(_credit_words & set(text.split()))
        structure = "bull_put_spread" if is_credit else "bear_put_spread"
        return {"structure": structure, "option_type": "Put", "strikes": strikes, "is_credit": is_credit}

    # Short single-leg options.
    _short_words = frozenset(("sell", "short", "write", "sold"))
    has_short = bool(_short_words & set(text.split()))
    is_csp = "cash secured" in text or "cash-secured" in text
    if has_short or is_csp:
        if "put" in text and "call" not in text:
            return {"structure": "short_put", "option_type": "Put", "strikes": strikes[:1], "is_credit": True}
        if "call" in text and "put" not in text:
            return {"structure": "short_call", "option_type": "Call", "strikes": strikes[:1], "is_credit": True}

    # Long single-leg (existing logic).
    bullish = "call" in text or "bull" in text
    bearish = "put" in text or "bear" in text
    if bullish and not bearish:
        return {"structure": "long_call", "option_type": "Call", "strikes": strikes[:1], "is_credit": False}
    if bearish and not bullish:
        return {"structure": "long_put", "option_type": "Put", "strikes": strikes[:1], "is_credit": False}

    return {"structure": "unsupported", "option_type": None, "strikes": [], "is_credit": False}


# ─── Analysis loading ──────────────────────────────────────────────────────────

def _load_analysis(tab: str, start: date | None, end: date | None) -> tuple[list[dict], dict]:
    """
    Read the analysis tab. Returns (candidate trades, market_regime_by_date).

    A candidate is any non-MARKET row with a non-empty play, within [start, end].
    """
    rows = sheets_client.get_all_rows(tab)
    market_regime: dict[str, str] = {}
    candidates: list[dict] = []

    for row in rows:
        d_date = _parse_analysis_date(row.get("date", ""))
        if d_date is None:
            continue
        if start and d_date < start:
            continue
        if end and d_date > end:
            continue
        d = d_date.isoformat()  # normalise to match flow_by_date keys

        ticker = str(row.get("ticker", "")).strip()
        if ticker.upper() == "MARKET":
            market_regime[d] = str(row.get("regime", "")).strip()
            continue
        if not str(row.get("play", "")).strip():
            continue

        candidates.append({
            "date": d,
            "signal_date": d_date,
            "ticker": ticker,
            "regime": str(row.get("regime", "")).strip(),
            "signal": str(row.get("signal", "")).strip(),
            "play": str(row.get("play", "")).strip(),
            "invalidation": str(row.get("invalidation", "")).strip(),
        })

    log.info("Loaded %d candidate plays from '%s' (%d market-regime dates)",
             len(candidates), tab, len(market_regime))
    return candidates, market_regime


# ─── Contract identification from play text ────────────────────────────────────

def _extract_horizon_dte(play_text: str) -> int | None:
    """
    Extract a DTE estimate from play text for expiry approximation.

    Priority:
      1. Inline range: '(35-60 DTE)' or '35-60 DTE' → midpoint (47)
      2. Inline single: '(45 DTE)' or '45 DTE' → 45
      3. Bracket line: '[medium | hedge | 60]' → 60 (coarse bucket boundary)
    """
    # Range: (35-60 DTE) or 35-60 DTE (en-dash or hyphen)
    m = re.search(r'\(?(\d+)\s*[-–]\s*(\d+)\s*DTE\)?', play_text, re.IGNORECASE)
    if m:
        return (int(m.group(1)) + int(m.group(2))) // 2
    # Single value: (45 DTE) or 45 DTE
    m = re.search(r'\(?(\d+)\s*DTE\)?', play_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Bracket line fallback: [confidence | signal_type | 60]
    m = re.search(r'\[(?:[^\]]*\|){2}\s*(\d+)\s*\]', play_text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def _nearest_cached_expiry(
    cache_dir: Path, ticker: str, opt_type: str, K: float,
    signal_date: date, horizon_dte: int | None,
) -> date | None:
    """Scan cache for contracts matching ticker/opt_type/K; pick expiry closest to signal_date + horizon_dte."""
    cp = "C" if opt_type == "Call" else "P"
    matches = list(cache_dir.glob(f"{ticker.upper()}_*_{K:.2f}{cp}.csv"))
    if not matches:
        return None
    target = signal_date + timedelta(days=horizon_dte or 60)
    best: date | None = None
    best_delta: int | None = None
    for p in matches:
        parts = p.stem.split("_")
        if len(parts) < 2:
            continue
        try:
            exp = datetime.strptime(parts[1], "%Y%m%d").date()
        except ValueError:
            continue
        if exp <= signal_date:
            continue
        delta = abs((exp - target).days)
        if best_delta is None or delta < best_delta:
            best_delta, best = delta, exp
    return best


def _identify_contract(
    candidate: dict, cls: dict, cache_dir: Path, spread_pct: float,
) -> tuple[float, date, str, float | None] | None:
    """
    Identify (K, expiration_date, opt_type, K_short) from the play text.
    Returns None when the contract cannot be identified.

    Expiry resolution order:
      1. Explicit month/day in play text (_extract_expiration).
      2. Cache scan for matching ticker/type/strike, closest to signal_date + horizon_dte.
    """
    structure = cls.get("structure")
    is_ic = structure == "iron_condor"

    if is_ic:
        opt_type = "Put"  # short-put leg anchors IC pricing
        ic_strikes = cls.get("strikes", [])
        if not ic_strikes:
            return None
        K = ic_strikes[1] if len(ic_strikes) >= 4 else ic_strikes[0]
    else:
        opt_type = cls.get("option_type")
        if not opt_type:
            return None
        play_strikes = cls.get("strikes", [])
        if not play_strikes:
            return None
        K = play_strikes[0]

    exp = _extract_expiration(candidate["play"], candidate["signal_date"])
    if exp is None:
        exp = _nearest_cached_expiry(
            cache_dir, candidate["ticker"], opt_type, K,
            candidate["signal_date"], _extract_horizon_dte(candidate["play"]),
        )
    if exp is None:
        return None

    K_short = None if is_ic else _short_strike(structure, K, cls.get("strikes", []), spread_pct)
    return K, exp, opt_type, K_short


# ─── Entry row from Barchart history cache ─────────────────────────────────────

def _entry_row_from_history(
    barchart_details: dict[tuple, dict],
    contract_key: tuple,
    signal_date: date,
    K: float,
    expiration_date: date,
) -> dict | None:
    """
    Build a synthetic entry_row dict (same keys _simulate reads from a flow row)
    from the Barchart per-contract history cache. Returns None when no priced row
    exists on or after signal_date for this contract.
    """
    day_rows = barchart_details.get(contract_key)
    if not day_rows:
        return None
    for d in sorted(day_rows):
        if d >= signal_date:
            row = day_rows[d]
            return {
                "Strike": K,
                "DTE": max(0, (expiration_date - d).days),
                "IV": row.get("IV"),
                "Price~": row.get("Price~"),
                "Trade": row.get("_mark"),
                "Expires": expiration_date.isoformat(),
                "Delta": row.get("Delta"),
            }
    return None


# ─── Flow entry matching (kept for tests; no longer called by main) ────────────

def _match_entry(candidate: dict, option_type: str, flow_rows: list[dict],
                 match_side: str, long_strike: float | None = None,
                 target_exp: date | None = None):
    """
    Find the real flow contract a play refers to: same symbol + option type, with
    a tradeable IV (>0, excludes parity/junk rows). When the play names a long
    strike and/or expiration, pick the row closest on (strike, then expiry);
    otherwise the largest premium (the headline trade).
    """
    ticker = candidate["ticker"].upper()
    candidates = []
    for row in flow_rows:
        if row.get("Symbol", "").upper().strip() != ticker:
            continue
        if row.get("Type", "").strip().title() != option_type:
            continue
        if match_side != "any" and row.get("Side", "").strip().lower() != match_side.lower():
            continue
        strike = _num(row.get("Strike"))
        iv = _row_iv(row)
        if _opt_price(row) is None or strike is None or not iv or iv <= 0:
            continue
        candidates.append((row, strike))

    if not candidates:
        return None
    if long_strike is None and target_exp is None:
        return max(candidates, key=lambda rs: _num(rs[0].get("Premium"), 0) or 0)[0]

    def score(rs):
        # Weighted distance so neither key dominates absolutely: a normalised strike
        # gap (fraction of the strike) plus an expiry gap in ~weeks. This keeps an
        # exact strike at a wildly wrong expiry (e.g. a 2-year LEAP) from winning.
        row, strike = rs
        strike_term = abs(strike - long_strike) / long_strike if long_strike else 0.0
        exp_term = 0.0
        if target_exp is not None:
            rexp = _parse_expiration(row.get("Expires", row.get("Expiration Date", "")))
            exp_term = abs((rexp - target_exp).days) / 30 if rexp else 1000.0
        return strike_term + exp_term

    return min(candidates, key=score)[0]


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
    """Real price AS OF `day`: the most recent scrape on-or-before it (carry-forward).

    This is the daily-path counterpart of `_reappearance_price` (which looks
    forward to the next scrape). For a day-by-day mark we want the value known on
    that day, never a future one. `series[key]` is sorted ascending.
    """
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


def _weekday_grid(signal_date: date, end_inclusive: date) -> list[date]:
    """Trading-day grid: weekdays AFTER the signal date through end_inclusive.

    Holidays are not removed (the underlying close on a holiday simply carries to
    the next session via price_fn); real per-contract marks are looked up as-of so
    they self-align to actual sessions regardless.
    """
    out, d = [], signal_date + timedelta(days=1)
    while d <= end_inclusive:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _summarize_path(grid_marks, entry_price, is_credit, profit_target, stop_loss,
                    contracts, cap_reached_expiry) -> dict:
    """Turn a day-by-day price grid into the path string, realized exit, and MFE/MAE.

    grid_marks: list of (date, calendar_days_elapsed, price|None, source_str) — one
    entry per trading day, price None on days with no available mark. All P&L is
    derived from this daily path; the full series is stored as `daily_price_csv`.

    Realized exit = the FIRST day profit_target or stop_loss is crossed (frozen at
    that day's mark — this is the correct realized P&L, not a later live mark).
    MFE/MAE are measured over the WHOLE path (independent of the exit rule) so the
    target/stop can be tuned in analysis. If no trigger fires, the trade is held to
    the last priced day: 'expired' when the path ran to expiry, else 'cap_open'.
    """
    def pnl_of(p):
        signed = (entry_price - p) if is_credit else (p - entry_price)
        return signed / entry_price

    out = {"daily_price_csv": ",".join(
        "" if p is None else f"{p:.4f}" for (_, _, p, _) in grid_marks)}

    priced = [(dt, d, p, src) for (dt, d, p, src) in grid_marks if p is not None]
    if not priced:
        out.update({"realized_pnl_pct": "", "realized_pnl_abs": "", "days_held": "",
                    "exit_reason": "no_data", "mfe_pct": "", "mfe_day": "",
                    "mae_pct": "", "mae_day": "", "pnl_at_cap_pct": "",
                    "pct_real_days": ""})
        return out

    # Single forward pass: running MFE/MAE + first-trigger realized exit.
    mfe, mae, mfe_day, mae_day = -1e18, 1e18, None, None
    exit_reason = realized_p = None
    days_held = last_priced_idx = None
    for grid_idx, (dt, d, p, src) in enumerate(grid_marks, start=1):
        if p is None:
            continue
        last_priced_idx = grid_idx
        pl = pnl_of(p)
        if pl > mfe:
            mfe, mfe_day = pl, grid_idx
        if pl < mae:
            mae, mae_day = pl, grid_idx
        if exit_reason is None:
            if pl >= profit_target:
                exit_reason, realized_p, days_held = "profit_target", p, grid_idx
            elif pl <= -stop_loss:
                exit_reason, realized_p, days_held = "stop_loss", p, grid_idx

    if exit_reason is None:
        _, _, last_p, _ = priced[-1]
        realized_p, days_held = last_p, last_priced_idx
        exit_reason = "expired" if cap_reached_expiry else "cap_open"

    realized_pnl = pnl_of(realized_p)
    cap_p = priced[-1][2]
    real_days = sum(1 for (_, _, _, s) in priced if s and not s.startswith("bs"))

    out.update({
        "realized_pnl_pct": round(realized_pnl * 100, 2),
        "realized_pnl_abs": round(realized_pnl * entry_price * 100 * contracts, 2),
        "days_held": days_held,
        "exit_reason": exit_reason,
        "mfe_pct": round(mfe * 100, 2),
        "mfe_day": mfe_day,
        "mae_pct": round(mae * 100, 2),
        "mae_day": mae_day,
        "pnl_at_cap_pct": round(pnl_of(cap_p) * 100, 2),
        "pct_real_days": round(real_days / len(priced) * 100, 1),
    })
    return out


# ─── Iron condor helpers ───────────────────────────────────────────────────────

def _iron_condor_strikes(
    strikes: list, K_sp_anchor: float, S_entry: float, spread_pct: float
) -> tuple[float, float, float, float]:
    """
    Resolve all four iron condor strikes as (K_lp, K_sp, K_sc, K_lc) — ascending.
      K_lp = long put  (wing, further OTM)
      K_sp = short put (income leg)
      K_sc = short call (income leg)
      K_lc = long call  (wing, further OTM)

    Strike sources in priority order:
      4 explicit strikes in play text → sort and assign positions.
      2 explicit strikes (the shorts)  → synthesise wings at spread_pct.
      0 explicit strikes               → synthesise all from matched short-put anchor.
    """
    if len(strikes) >= 4:
        s = sorted(strikes)
        return s[0], s[1], s[2], s[3]
    if len(strikes) == 2:
        K_sp, K_sc = sorted(strikes)
        return K_sp * (1 - spread_pct), K_sp, K_sc, K_sc * (1 + spread_pct)
    # Synthesise: mirror the put-side distance to the call side.
    K_sp = K_sp_anchor
    d = abs(S_entry - K_sp) / S_entry if S_entry > 0 else spread_pct
    K_sc = S_entry * (1 + d)
    return K_sp * (1 - spread_pct), K_sp, K_sc, K_sc * (1 + spread_pct)


def _simulate_iron_condor(
    candidate, cls, entry_row, contract_index, barchart_series, sim_cfg, price_fn=None
):
    """
    Simulate a 4-leg iron condor (bear call spread + bull put spread).

    Entry: net credit = (K_sp_price - K_lp_price) + (K_sc_price - K_lc_price).
      K_sp entry uses the real flow Trade price when available; other legs use BS.
    Exit:  all four legs priced with Black-Scholes (exit_source = 'bs').
    P&L:   (entry_credit - exit_cost) / entry_credit.
    """
    price_fn = price_fn or (lambda tk, dt: _price_on_or_after(
        _get_prices(tk, candidate["signal_date"], sim_cfg.get("path_cap_days", 120)), dt
    ))

    ticker = candidate["ticker"]
    signal_date = candidate["signal_date"]
    r = sim_cfg.get("risk_free_rate", 0.05)
    contracts = sim_cfg.get("contracts", 1)
    spread_pct = sim_cfg.get("spread_width_pct", 0.02)

    K_sp_matched = _num(entry_row.get("Strike"))
    iv = _row_iv(entry_row)
    S_entry = _num(entry_row.get("Price~", entry_row.get("Price")))
    dte_entry = _num(entry_row.get("DTE"))
    expiration_raw = str(entry_row.get("Expires", entry_row.get("Expiration Date", ""))).strip()

    if not (K_sp_matched and iv and S_entry and dte_entry and dte_entry > 0):
        return {}
    dte_entry = int(dte_entry)
    T_entry = dte_entry / 365
    expiration_date = _parse_expiration(expiration_raw, signal_date + timedelta(days=dte_entry))

    K_lp, K_sp, K_sc, K_lc = _iron_condor_strikes(
        cls.get("strikes", []), K_sp_matched, S_entry, spread_pct
    )

    # All 4 legs priced with BS at entry so the spread credit is internally consistent.
    # Mixing a real flow price for one leg with BS prices for the others can produce
    # a spurious negative credit when IV implied by the flow price differs from the
    # IV column used for the BS legs.
    ksp_entry = _bs_price(S_entry, K_sp, T_entry, r, iv, "Put")
    klp_entry = _bs_price(S_entry, K_lp, T_entry, r, iv, "Put")
    ksc_entry = _bs_price(S_entry, K_sc, T_entry, r, iv, "Call")
    klc_entry = _bs_price(S_entry, K_lc, T_entry, r, iv, "Call")

    entry_credit = (ksp_entry - klp_entry) + (ksc_entry - klc_entry)
    if entry_credit <= 0:
        return {}

    entry_source = "bs"

    profit_target = sim_cfg.get("profit_target", 0.50)
    stop_loss = sim_cfg.get("stop_loss", 1.00)

    result = {
        "signal_date": signal_date.isoformat(),
        "ticker": ticker,
        "structure": "iron_condor",
        "opt_type": "IC",
        "k_long": round(K_sp, 2),
        "k_short": f"{K_lp:.2f}/{K_sc:.2f}/{K_lc:.2f}",
        "expiration": expiration_raw,
        "dte_entry": dte_entry,
        "iv_entry_pct": round(iv * 100, 2),
        "delta": "",
        "entry_underlying": S_entry,
        "entry_option_price": round(entry_credit, 4),
        "entry_premium_total": round(entry_credit * 100 * contracts, 2),
        "entry_source": entry_source,
        "regime": candidate.get("regime", ""),
        "play": candidate["play"][:300],
    }

    def _cost_on(day, d):
        """Cost-to-close the 4-leg condor on a single trading day (BS) → (cost|None, src)."""
        S_exit = price_fn(ticker, day)
        if S_exit is None:
            return None, ""
        T_exit = max(0.0, (dte_entry - d) / 365)
        ksp_exit = _bs_price(S_exit, K_sp, T_exit, r, iv, "Put")
        klp_exit = _bs_price(S_exit, K_lp, T_exit, r, iv, "Put")
        ksc_exit = _bs_price(S_exit, K_sc, T_exit, r, iv, "Call")
        klc_exit = _bs_price(S_exit, K_lc, T_exit, r, iv, "Call")
        return max(0.0, (ksp_exit - klp_exit) + (ksc_exit - klc_exit)), "bs"

    # Daily path: P&L = (entry_credit - cost_to_close) / entry_credit, i.e. a credit
    # structure marked against entry_credit. Reuse the shared summarizer.
    path_cap = sim_cfg.get("path_cap_days", 120)
    cap_reached_expiry = dte_entry <= path_cap
    end_date = signal_date + timedelta(days=min(dte_entry, path_cap))
    if expiration_date:
        end_date = min(end_date, expiration_date)

    grid_marks = []
    for day in _weekday_grid(signal_date, end_date):
        d = (day - signal_date).days
        cost, source = _cost_on(day, d)
        grid_marks.append((day, d, cost, source))

    result.update(_summarize_path(
        grid_marks, entry_credit, True, profit_target, stop_loss, contracts,
        cap_reached_expiry))
    return result


# ─── Simulation ────────────────────────────────────────────────────────────────

def _simulate(candidate, cls, entry_row, contract_index, barchart_series, sim_cfg, price_fn=None):
    """
    Simulate one play. Returns a result dict, or {} if it cannot be priced.

    Exit price is taken from the first available source in sim_cfg['exit_sources']:
      barchart     — real per-contract daily price scraped from Barchart
      reappearance — real Trade price when the contract recurs in a later flow scrape
      bs           — Black-Scholes model (last resort)
    barchart_series maps contract_key -> sorted [(date, price)].
    price_fn(ticker, date) -> float|None is injectable for testing (defaults to yfinance).
    """
    price_fn = price_fn or (lambda tk, dt: _price_on_or_after(
        _get_prices(tk, candidate["signal_date"], sim_cfg.get("path_cap_days", 120)), dt))

    if cls.get("structure") == "iron_condor":
        return _simulate_iron_condor(
            candidate, cls, entry_row, contract_index, barchart_series, sim_cfg, price_fn
        )

    ticker = candidate["ticker"]
    opt_type = cls["option_type"]
    structure = cls["structure"]
    is_credit = cls.get("is_credit", False)
    signal_date = candidate["signal_date"]
    r = sim_cfg.get("risk_free_rate", 0.05)
    contracts = sim_cfg.get("contracts", 1)

    K = _num(entry_row.get("Strike"))
    dte_entry = _num(entry_row.get("DTE"))
    iv = _row_iv(entry_row)
    S_entry = _num(entry_row.get("Price~", entry_row.get("Price")))
    real_entry_price = _opt_price(entry_row)
    expiration_raw = str(entry_row.get("Expires", entry_row.get("Expiration Date", ""))).strip()
    if not (K and dte_entry and dte_entry > 0 and iv and S_entry):
        return {}
    dte_entry = int(dte_entry)
    T_entry = dte_entry / 365
    expiration_date = _parse_expiration(expiration_raw, signal_date + timedelta(days=dte_entry))

    # Short-leg strike: prefer the one the play actually named; else synthesise
    # spread_width_pct away from the long strike. The short leg is just another
    # contract, so its real Barchart history (when present) is netted out below;
    # Black-Scholes is only the fallback.
    spread_pct = sim_cfg.get("spread_width_pct", 0.02)
    K_short = _short_strike(structure, K, cls.get("strikes", []), spread_pct)
    short_key = _contract_key(ticker, opt_type, K_short, expiration_raw) if K_short is not None else None

    # Guard against a degenerate spread where legs cross or collapse.
    if K_short is not None:
        if structure in ("bull_call_spread", "bear_call_spread") and K_short <= K:
            return {}
        if structure in ("bear_put_spread", "bull_put_spread") and K_short >= K:
            return {}

    def _short_leg_price(checkpoint, d, S_known=None):
        """
        Short-leg price at a checkpoint. The short leg is just another contract, so
        prefer its real Barchart history (mid); fall back to Black-Scholes only when
        that contract has no history. Returns (price, source) where source is one of
        the standard tokens 'barchart' or 'bs'; (None, None) if it cannot be priced.
        """
        if short_key is not None:
            real = _price_asof(barchart_series, short_key, checkpoint, expiration_date)
            if real is not None:
                return real, "barchart"
        S = S_known if S_known is not None else price_fn(ticker, checkpoint)
        if S is None:
            return None, None
        T = max(0, (dte_entry - d) / 365)
        return _bs_price(S, K_short, T, r, iv, opt_type), "bs"

    # Entry price.
    # Debit single-leg: premium paid = real flow price.
    # Credit single-leg: premium received = real flow price (P&L inverted later).
    # Spread (debit or credit): primary_leg - contra_leg. For debit spreads this is
    # the net cost paid; for credit spreads it is the net credit received. The same
    # arithmetic works because K is the primary matched leg in both cases.
    if K_short is None:
        entry_price = real_entry_price
        entry_source = "real"
        if entry_price is None:
            return {}
    else:
        primary_entry = real_entry_price or _bs_price(S_entry, K, T_entry, r, iv, opt_type)
        contra_entry, contra_src = _short_leg_price(signal_date, 0, S_entry)
        if contra_entry is None:
            return {}
        entry_price = primary_entry - contra_entry
        primary_tag = "real" if real_entry_price else "bs"
        entry_source = f"{primary_tag}+{contra_src}"
    if entry_price <= 0:
        return {}

    contract_key = _contract_key(ticker, opt_type, K, expiration_raw)
    profit_target = sim_cfg.get("profit_target", 0.50)
    stop_loss = sim_cfg.get("stop_loss", 1.00)
    exit_sources = sim_cfg.get("exit_sources", ["barchart", "reappearance", "bs"])

    result = {
        "signal_date": signal_date.isoformat(),
        "ticker": ticker,
        "structure": structure,
        "opt_type": opt_type,
        "k_long": K,
        "k_short": round(K_short, 2) if K_short else "",
        "expiration": expiration_raw,
        "dte_entry": dte_entry,
        "iv_entry_pct": round(iv * 100, 2),
        "delta": entry_row.get("Delta", ""),
        "entry_underlying": S_entry,
        "entry_option_price": round(entry_price, 4),
        "entry_premium_total": round(entry_price * 100 * contracts, 2),
        "entry_source": entry_source,
        "regime": candidate.get("regime", ""),
        "play": candidate["play"][:300],
    }

    def _real_long_leg(series, checkpoint, d):
        """
        Resolve a real long-leg price; for spreads, net out the short leg priced from
        real Barchart history (or BS fallback). Returns (net_price, short_source) or
        None when the long leg has no real price at this checkpoint.
        """
        real = _price_asof(series, contract_key, checkpoint, expiration_date)
        if real is None:
            return None
        if K_short is None:
            return real, ""
        short, short_src = _short_leg_price(checkpoint, d)
        if short is None:
            return None
        return real - short, short_src

    def _bs_exit(checkpoint, d):
        S_exit = price_fn(ticker, checkpoint)
        if S_exit is None:
            return None
        T_exit = max(0, (dte_entry - d) / 365)
        if K_short is None:
            return _bs_price(S_exit, K, T_exit, r, iv, opt_type), ""
        return _bs_spread_price(S_exit, K, K_short, T_exit, r, iv, opt_type), "bs"

    _tag = {"barchart": "barchart", "reappearance": "real", "bs": "bs"}

    def _mark_on(day, d):
        """Net option/spread mark on a single trading day → (price|None, source)."""
        for src in exit_sources:
            priced = None
            if src == "barchart":
                priced = _real_long_leg(barchart_series, day, d)
            elif src == "reappearance":
                priced = _real_long_leg(contract_index, day, d)
            elif src == "bs":
                priced = _bs_exit(day, d)
            if priced is not None and priced[0] is not None:
                price, short_src = priced
                source = _tag.get(src, src)
                if K_short is not None and src != "bs":
                    source += f"+{short_src}"
                if K_short is not None:  # spread/cost-to-close floored at zero
                    price = max(0.0, price)
                return price, source
        return None, ""

    # Walk every trading day from entry to min(expiration, cap). The full daily
    # path is the sole basis for realized exit / MFE / MAE and all reported P&L.
    path_cap = sim_cfg.get("path_cap_days", 120)
    cap_reached_expiry = dte_entry <= path_cap
    end_date = signal_date + timedelta(days=min(dte_entry, path_cap))
    if expiration_date:
        end_date = min(end_date, expiration_date)

    grid_marks = []
    for day in _weekday_grid(signal_date, end_date):
        d = (day - signal_date).days
        price, source = _mark_on(day, d)
        grid_marks.append((day, d, price, source))

    result.update(_summarize_path(
        grid_marks, entry_price, is_credit, profit_target, stop_loss, contracts,
        cap_reached_expiry))
    return result


# ─── Output ────────────────────────────────────────────────────────────────────

def _write_results(results, cfg, dry_run) -> None:
    if not results:
        log.warning("No results to write")
        return

    RESULTS_PATH.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    local_csv = cfg["output"].get("local_csv", f"backtests/results_{ts}.csv")
    csv_path = Path(__file__).parent.parent / local_csv

    key_order = [
        "signal_date", "ticker", "structure", "opt_type", "k_long", "k_short",
        "expiration", "dte_entry", "iv_entry_pct", "delta", "entry_underlying",
        "entry_option_price", "entry_premium_total", "entry_source",
        "regime", "play",
        # Path-derived summary (the real exit + excursions over the full daily path).
        "realized_pnl_pct", "realized_pnl_abs", "days_held", "exit_reason",
        "mfe_pct", "mfe_day", "mae_pct", "mae_day", "pnl_at_cap_pct", "pct_real_days",
        # Full day-by-day mark series (comma-separated; split on read for charts).
        # All P&L is computed from this path — there are no per-checkpoint columns.
        "daily_price_csv",
    ]

    if not dry_run:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=key_order, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        log.info("Wrote %d results to '%s'", len(results), csv_path)

        sheet_tab = cfg["output"].get("sheet_tab")
        if sheet_tab:
            sheets_client.append_rows(sheet_tab, [{k: r.get(k, "") for k in key_order} for r in results])
            log.info("Appended results to Google Sheets tab '%s'", sheet_tab)
    else:
        log.info("[dry-run] Would write %d results to '%s'", len(results), csv_path)

    _print_summary(results)


def _print_summary(results) -> None:
    print(f"\n{'='*64}")
    print(f"BACKTEST SUMMARY  ({len(results)} plays simulated)")
    print(f"{'='*64}")

    # Realized exits over the full daily path (the only result — all P&L is
    # derived from the day-by-day price path, no per-checkpoint columns).
    rz = [r for r in results if isinstance(r.get("realized_pnl_pct"), (int, float))]
    if not rz:
        print("\nNo priced plays.")
        return

    arr = np.array([r["realized_pnl_pct"] for r in rz])
    held = [r["days_held"] for r in rz if isinstance(r.get("days_held"), (int, float))]
    reasons = {}
    for r in rz:
        reasons[r.get("exit_reason", "")] = reasons.get(r.get("exit_reason", ""), 0) + 1
    print(f"\nRealized exit ({len(arr)} priced, first profit_target/stop_loss/expiry):")
    print(f"  Win rate:   {(arr>0).sum()/len(arr)*100:.1f}%  ({(arr>0).sum()}/{len(arr)})")
    print(f"  Avg P&L:    {arr.mean():+.2f}%   Median: {np.median(arr):+.2f}%")
    print(f"  Best/Worst: {arr.max():+.2f}% / {arr.min():+.2f}%")
    if held:
        print(f"  Avg hold:   {np.mean(held):.1f} trading days")
    print("  Exit mix:   " + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())))

    # Coverage: plays whose path was entirely real data (no Black-Scholes marks).
    real = [r["realized_pnl_pct"] for r in rz
            if isinstance(r.get("pct_real_days"), (int, float)) and r["pct_real_days"] > 0]
    if real:
        ra = np.array(real)
        print(f"  ↳ real-data subset: {(ra>0).sum()/len(ra)*100:.1f}% win, "
              f"{ra.mean():+.2f}% avg  ({len(ra)} trades)")
    else:
        print("  ↳ real-data subset: none (all Black-Scholes modelled)")

    top = sorted(rz, key=lambda x: x["realized_pnl_pct"], reverse=True)[:5]
    print(f"\nTop {len(top)} plays by realized P&L:")
    for r in top:
        print(f"  {r['signal_date']} {r['ticker']:6} {r['structure']:16} "
              f"K={r['k_long']} → {r['realized_pnl_pct']:+.1f}%  [{r.get('exit_reason','')}]")


# ─── Barchart historical option prices ─────────────────────────────────────────

async def _fetch_option_histories(
    contracts: list[dict], headless: bool, timeout_ms: int = 15000,
) -> tuple[dict[tuple, list], dict[tuple, dict]]:
    """
    Scrape (and cache) per-contract Barchart price history.

    contracts: list of {key, symbol, opt_type, strike, expiration(date)}.
    Returns (series_map, details_map):
      series_map:  {contract_key: [(date, price), ...]}  — for _price_asof exit lookups
      details_map: {contract_key: {date: row_dict}}      — for building entry rows
    Cached CSVs are reused so re-runs do not re-scrape.
    """
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    email, password = os.getenv("BARCHART_EMAIL", ""), os.getenv("BARCHART_PASSWORD", "")
    cookies_path = Path(os.getenv("COOKIES_PATH", str(RESULTS_PATH.parent / "cookies" / "barchart_session.json")))

    series_map: dict[tuple, list] = {}
    details_map: dict[tuple, dict] = {}
    to_scrape: list[dict] = []

    def _load_cache(c: dict, text: str) -> None:
        series_map[c["key"]] = barchart_options.parse_history_series(text)
        details_map[c["key"]] = barchart_options.parse_history_details(text)

    # Serve from cache first; only the rest need a browser session.
    for c in contracts:
        cache = barchart_options.cache_path(HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
        if cache.exists():
            _load_cache(c, cache.read_text(encoding="utf-8"))
        else:
            to_scrape.append(c)

    log.info("Barchart history: %d cached, %d to scrape", len(series_map), len(to_scrape))
    if not to_scrape:
        return series_map, details_map
    if not (email and password):
        log.warning("BARCHART_EMAIL/PASSWORD not set — skipping Barchart history (BS fallback will be used)")
        return series_map, details_map

    async with BarchartSession(email, password, cookies_path, headless) as session:
        for i, c in enumerate(to_scrape, 1):
            url = barchart_options.option_history_url(c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            log.info("[%d/%d] Barchart history: %s", i, len(to_scrape), url)
            try:
                csv_text = await session.fetch_history_csv(url, timeout_ms)
            except Exception:
                log.exception("Barchart history scrape failed for %s", c["key"])
                csv_text = None
            if not csv_text:
                series_map[c["key"]] = []
                continue
            cache = barchart_options.cache_path(HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            cache.write_text(csv_text, encoding="utf-8")
            _load_cache(c, csv_text)
            await asyncio.sleep(2)

    return series_map, details_map


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Backtest LLM analysis plays.")
    parser.add_argument("--config", default="config/backtest.yml")
    parser.add_argument("--tab", help="Analysis tab to backtest (overrides config)")
    parser.add_argument("--date", help="Single analysis date YYYY-MM-DD (sets --start and --end)")
    parser.add_argument("--start", help="Earliest analysis date (YYYY-MM-DD)")
    parser.add_argument("--end", help="Latest analysis date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output files")
    args = parser.parse_args()

    cfg_path = Path(__file__).parent.parent / args.config
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)

    tab = args.tab or cfg.get("analysis", {}).get("tab", "AnalysisClaude")
    if args.date:
        start = end = date.fromisoformat(args.date)
    else:
        start = date.fromisoformat(args.start) if args.start else None
        end = date.fromisoformat(args.end) if args.end else None
    sim_cfg = cfg["simulation"]
    spread_pct = sim_cfg.get("spread_width_pct", 0.02)

    log.info("Loading analysis plays from tab '%s'", tab)
    candidates, market_regime = _load_analysis(tab, start, end)
    if not candidates:
        log.warning("No plays found in '%s' — run /options analyze (range mode) first to populate it", tab)
        sys.exit(0)

    # Pass 1 — classify each play and identify its contract from play text.
    # No flow CSV download needed: strike and expiry come from the play text,
    # with expiry falling back to a cache scan when not explicit.
    matched, contracts, skipped = [], {}, {"unsupported": 0, "no_contract": 0, "unpriced": 0}
    for c in candidates:
        c["regime"] = c.get("regime", "")
        cls = classify_play(c["play"])
        if cls["structure"] == "unsupported":
            skipped["unsupported"] += 1
            continue

        result = _identify_contract(c, cls, HISTORY_CACHE, spread_pct)
        if result is None:
            skipped["no_contract"] += 1
            continue

        K, exp_date, opt_type, K_short = result
        exp_raw = exp_date.isoformat()
        is_ic = cls["structure"] == "iron_condor"
        matched.append((c, cls, K, exp_date, opt_type, K_short))

        # Register contracts for Barchart scraping/cache lookup.
        # Iron condors anchor on the short-put leg; other legs are BS-priced.
        anchor_type = "Put" if is_ic else opt_type
        key = _contract_key(c["ticker"], anchor_type, K, exp_raw)
        contracts.setdefault(key, {"key": key, "symbol": c["ticker"],
                                   "opt_type": anchor_type, "strike": K,
                                   "expiration": exp_date})
        if not is_ic and K_short is not None:
            skey = _contract_key(c["ticker"], opt_type, K_short, exp_raw)
            contracts.setdefault(skey, {"key": skey, "symbol": c["ticker"],
                                        "opt_type": opt_type, "strike": K_short,
                                        "expiration": exp_date})

    # Pass 2 — fetch/cache Barchart history for all identified contracts.
    barchart_series: dict[tuple, list] = {}
    barchart_details: dict[tuple, dict] = {}
    if contracts:
        headless = os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
        history_timeout_ms = int(sim_cfg.get("history_timeout_ms", 15000))
        log.info("Fetching Barchart history for %d distinct contract(s)", len(contracts))
        barchart_series, barchart_details = asyncio.run(_fetch_option_histories(
            list(contracts.values()), headless, history_timeout_ms))

    # Pass 3 — build entry row from cache then simulate.
    log.info("Simulating %d classified plays", len(matched))
    results = []
    for c, cls, K, exp_date, opt_type, K_short in matched:
        is_ic = cls["structure"] == "iron_condor"
        exp_raw = exp_date.isoformat()
        anchor_type = "Put" if is_ic else opt_type
        anchor_key = _contract_key(c["ticker"], anchor_type, K, exp_raw)
        entry_row = _entry_row_from_history(barchart_details, anchor_key, c["signal_date"], K, exp_date)
        if entry_row is None:
            skipped["unpriced"] += 1
            continue
        result = _simulate(c, cls, entry_row, {}, barchart_series, sim_cfg)
        if result:
            results.append(result)
        else:
            skipped["unpriced"] += 1

    log.info("Simulated %d plays (skipped: %d unsupported, %d no contract, %d unpriced)",
             len(results), skipped["unsupported"], skipped["no_contract"], skipped["unpriced"])

    _write_results(results, cfg, args.dry_run)


if __name__ == "__main__":
    main()
