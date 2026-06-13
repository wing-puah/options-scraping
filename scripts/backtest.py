"""
Analysis-driven backtesting engine for options plays.

Instead of re-filtering raw flow rows, this reads the LLM analysis already
written to Google Sheets (AnalysisClaude / AnalysisGPT) and treats every
non-MARKET ticker row with a play as a decision to open a position. It then
measures how that play would have performed.

Pricing philosophy (real data first, model last):
  Entry  — the actual option `Trade` price from the matching flow CSV row.
  Exit   — the actual `Trade` price when the same contract reappears in a later
           scrape on/after the checkpoint (we scrape 2x/day). Falls back to
           Black-Scholes only when the contract did not reappear.
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
from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client

log = logging.getLogger("backtest")

RESULTS_PATH = Path(__file__).parent.parent / "backtests"
HISTORY_CACHE = RESULTS_PATH / "option_history_cache"

FLOW_PREFIXES = ["stocks-flow", "etfs-flow"]

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


# ─── Flow loading (entry matching + exit reappearance) ─────────────────────────

def _load_flow(start: date | None, end: date | None, lookahead_days: int):
    """
    Load flow CSVs from Drive. Returns:
      flow_by_date     — { 'YYYY-MM-DD': [rows] }            (for entry matching)
      contract_index   — { contract_key: [(date, trade_price), ...] }  (for exits)
    """
    client = get_drive_client()
    date_re = re.compile(r"-(\d{8})-")
    window_end = (end + timedelta(days=lookahead_days)) if end else None

    flow_by_date: dict[str, list[dict]] = {}
    contract_index: dict[tuple, list[tuple]] = {}

    for prefix in FLOW_PREFIXES:
        try:
            files = client.list_files(prefix)
        except Exception:
            log.exception("Could not list Drive files for prefix '%s'", prefix)
            continue

        for f in files:
            m = date_re.search(f["name"])
            if not m:
                continue
            try:
                snap_date = datetime.strptime(m.group(1), "%Y%m%d").date()
            except ValueError:
                continue
            # Need files from signal dates through the exit lookahead window.
            if start and snap_date < start:
                continue
            if window_end and snap_date > window_end:
                continue

            try:
                content = client.download(f["id"])
            except Exception:
                log.exception("Could not download '%s'", f["name"])
                continue

            d_str = snap_date.isoformat()
            for row in parse_csv(content):
                flow_by_date.setdefault(d_str, []).append(row)

                price = _opt_price(row)
                strike = _num(row.get("Strike"))
                if price is None or strike is None:
                    continue
                key = _contract_key(
                    row.get("Symbol", ""), row.get("Type", ""), strike,
                    row.get("Expires", row.get("Expiration Date", "")),
                )
                contract_index.setdefault(key, []).append((snap_date, price))

    for key in contract_index:
        contract_index[key].sort(key=lambda t: t[0])

    log.info("Loaded flow for %d date(s); indexed %d distinct contracts",
             len(flow_by_date), len(contract_index))
    return flow_by_date, contract_index


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
        _get_prices(tk, candidate["signal_date"], max(sim_cfg.get("exit_days", [21]))), dt
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

    exit_days = sorted(sim_cfg.get("exit_days", [1, 3, 5, 10, 21]))
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
        "market_regime": candidate.get("market_regime", ""),
        "play": candidate["play"][:300],
    }

    exited = False
    for d in exit_days:
        checkpoint = signal_date + timedelta(days=d)
        prefix = f"d{d}"

        S_exit = price_fn(ticker, checkpoint)
        if S_exit is None:
            result[f"{prefix}_option_price"] = ""
            result[f"{prefix}_pnl_pct"] = ""
            result[f"{prefix}_pnl_abs"] = ""
            result[f"{prefix}_status"] = "no_data"
            result[f"{prefix}_exit_source"] = ""
            continue

        T_exit = max(0.0, (dte_entry - d) / 365)
        ksp_exit = _bs_price(S_exit, K_sp, T_exit, r, iv, "Put")
        klp_exit = _bs_price(S_exit, K_lp, T_exit, r, iv, "Put")
        ksc_exit = _bs_price(S_exit, K_sc, T_exit, r, iv, "Call")
        klc_exit = _bs_price(S_exit, K_lc, T_exit, r, iv, "Call")

        exit_cost = max(0.0, (ksp_exit - klp_exit) + (ksc_exit - klc_exit))
        pnl_pct = (entry_credit - exit_cost) / entry_credit
        pnl_abs = (entry_credit - exit_cost) * 100 * contracts

        if not exited:
            if pnl_pct >= profit_target:
                status, exited = "profit_target", True
            elif pnl_pct <= -stop_loss:
                status, exited = "stop_loss", True
            else:
                status = "open"
        else:
            status = "already_exited"

        result[f"{prefix}_option_price"] = round(exit_cost, 4)
        result[f"{prefix}_pnl_pct"] = round(pnl_pct * 100, 2)
        result[f"{prefix}_pnl_abs"] = round(pnl_abs, 2)
        result[f"{prefix}_status"] = status
        result[f"{prefix}_exit_source"] = "bs"

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
        _get_prices(tk, candidate["signal_date"], max(sim_cfg.get("exit_days", [21]))), dt))

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
            real = _reappearance_price(barchart_series, short_key, checkpoint, expiration_date)
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
    exit_days = sorted(sim_cfg.get("exit_days", [1, 3, 5, 10, 21]))
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
        "market_regime": candidate.get("market_regime", ""),
        "play": candidate["play"][:300],
    }

    def _real_long_leg(series, checkpoint, d):
        """
        Resolve a real long-leg price; for spreads, net out the short leg priced from
        real Barchart history (or BS fallback). Returns (net_price, short_source) or
        None when the long leg has no real price at this checkpoint.
        """
        real = _reappearance_price(series, contract_key, checkpoint, expiration_date)
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

    exited = False
    for d in exit_days:
        checkpoint = signal_date + timedelta(days=d)
        prefix = f"d{d}"

        exit_price = None
        exit_source = ""
        for src in exit_sources:
            priced = None
            if src == "barchart":
                priced = _real_long_leg(barchart_series, checkpoint, d)
            elif src == "reappearance":
                priced = _real_long_leg(contract_index, checkpoint, d)
            elif src == "bs":
                priced = _bs_exit(checkpoint, d)
            if priced is not None and priced[0] is not None:
                exit_price, short_src = priced
                exit_source = _tag.get(src, src)
                if K_short is not None and src != "bs":
                    exit_source += f"+{short_src}"
                break

        # Spread value (or cost-to-close for credit) cannot go below zero.
        if exit_price is not None and K_short is not None:
            exit_price = max(0.0, exit_price)

        if exit_price is None:
            result[f"{prefix}_option_price"] = ""
            result[f"{prefix}_pnl_pct"] = ""
            result[f"{prefix}_pnl_abs"] = ""
            result[f"{prefix}_status"] = "no_data"
            result[f"{prefix}_exit_source"] = ""
            continue

        # Credit: profit when the option/spread decays (exit_price < entry_price).
        # Debit: profit when the option/spread appreciates (exit_price > entry_price).
        if is_credit:
            pnl_pct = (entry_price - exit_price) / entry_price
            pnl_abs = (entry_price - exit_price) * 100 * contracts
        else:
            pnl_pct = (exit_price - entry_price) / entry_price
            pnl_abs = (exit_price - entry_price) * 100 * contracts

        if not exited:
            if pnl_pct >= profit_target:
                status, exited = "profit_target", True
            elif pnl_pct <= -stop_loss:
                status, exited = "stop_loss", True
            else:
                status = "open"
        else:
            status = "already_exited"

        result[f"{prefix}_option_price"] = round(exit_price, 4)
        result[f"{prefix}_pnl_pct"] = round(pnl_pct * 100, 2)
        result[f"{prefix}_pnl_abs"] = round(pnl_abs, 2)
        result[f"{prefix}_status"] = status
        result[f"{prefix}_exit_source"] = exit_source

    return result


# ─── Output ────────────────────────────────────────────────────────────────────

def _write_results(results, cfg, exit_days, dry_run) -> None:
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
        "market_regime", "play",
    ]
    for d in sorted(exit_days):
        key_order += [f"d{d}_option_price", f"d{d}_pnl_pct", f"d{d}_pnl_abs",
                      f"d{d}_status", f"d{d}_exit_source"]

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

    _print_summary(results, sorted(exit_days))


def _print_summary(results, exit_days) -> None:
    print(f"\n{'='*64}")
    print(f"BACKTEST SUMMARY  ({len(results)} plays simulated)")
    print(f"{'='*64}")

    for d in exit_days:
        pnl_col, src_col = f"d{d}_pnl_pct", f"d{d}_exit_source"
        rows = [r for r in results if isinstance(r.get(pnl_col), (int, float))]
        if not rows:
            continue
        arr = np.array([r[pnl_col] for r in rows])
        win = (arr > 0).sum()
        # "real" = long leg priced from actual data (Barchart or reappearance), not pure BS.
        real = [r[pnl_col] for r in rows
                if r.get(src_col) and not r[src_col].startswith("bs")]
        print(f"\nDay {d:>2} exit ({len(rows)} priced):")
        print(f"  Win rate:   {win/len(rows)*100:.1f}%  ({win}/{len(rows)})")
        print(f"  Avg P&L:    {arr.mean():+.2f}%   Median: {np.median(arr):+.2f}%")
        print(f"  Best/Worst: {arr.max():+.2f}% / {arr.min():+.2f}%")
        if real:
            ra = np.array(real)
            print(f"  ↳ real-exit subset: {(ra>0).sum()/len(ra)*100:.1f}% win, "
                  f"{ra.mean():+.2f}% avg  ({len(ra)} trades)")
        else:
            print("  ↳ real-exit subset: none (all Black-Scholes modelled)")

    first = exit_days[0]
    col = f"d{first}_pnl_pct"
    top = sorted([r for r in results if isinstance(r.get(col), (int, float))],
                 key=lambda x: x[col], reverse=True)[:5]
    if top:
        print(f"\nTop {len(top)} plays by Day-{first} P&L:")
        for r in top:
            print(f"  {r['signal_date']} {r['ticker']:6} {r['structure']:16} "
                  f"K={r['k_long']} → {r[col]:+.1f}%  [{r.get(f'd{first}_exit_source','')}]")


# ─── Barchart historical option prices ─────────────────────────────────────────

async def _fetch_option_histories(contracts: list[dict], headless: bool) -> dict[tuple, list]:
    """
    Scrape (and cache) per-contract Barchart price history.

    contracts: list of {key, symbol, opt_type, strike, expiration(date)}.
    Returns { contract_key: sorted [(date, price)] }. Cached CSVs are reused so
    re-runs do not re-scrape.
    """
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    email, password = os.getenv("BARCHART_EMAIL", ""), os.getenv("BARCHART_PASSWORD", "")
    cookies_path = Path(os.getenv("COOKIES_PATH", str(RESULTS_PATH.parent / "cookies" / "barchart_session.json")))

    series_map: dict[tuple, list] = {}
    to_scrape: list[dict] = []

    # Serve from cache first; only the rest need a browser session.
    for c in contracts:
        cache = barchart_options.cache_path(HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
        if cache.exists():
            series_map[c["key"]] = barchart_options.parse_history_series(cache.read_text(encoding="utf-8"))
        else:
            to_scrape.append(c)

    log.info("Barchart history: %d cached, %d to scrape", len(series_map), len(to_scrape))
    if not to_scrape:
        return series_map
    if not (email and password):
        log.warning("BARCHART_EMAIL/PASSWORD not set — skipping Barchart history (BS fallback will be used)")
        return series_map

    async with BarchartSession(email, password, cookies_path, headless) as session:
        for i, c in enumerate(to_scrape, 1):
            url = barchart_options.option_history_url(c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            log.info("[%d/%d] Barchart history: %s", i, len(to_scrape), url)
            try:
                # Scrape the price-history JSON feed (row-by-row data, no metered
                # Download button, full series in one call) — see fetch_history_csv.
                csv_text = await session.fetch_history_csv(url)
            except Exception:
                log.exception("Barchart history scrape failed for %s", c["key"])
                csv_text = None
            if not csv_text:
                series_map[c["key"]] = []
                continue
            cache = barchart_options.cache_path(HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            cache.write_text(csv_text, encoding="utf-8")
            series_map[c["key"]] = barchart_options.parse_history_series(csv_text)
            await asyncio.sleep(2)

    return series_map


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Backtest LLM analysis plays.")
    parser.add_argument("--config", default="config/backtest.yml")
    parser.add_argument("--tab", help="Analysis tab to backtest (overrides config)")
    parser.add_argument("--start", help="Earliest analysis date (YYYY-MM-DD)")
    parser.add_argument("--end", help="Latest analysis date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output files")
    args = parser.parse_args()

    cfg_path = Path(__file__).parent.parent / args.config
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)

    tab = args.tab or cfg.get("analysis", {}).get("tab", "AnalysisClaude")
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    sim_cfg = cfg["simulation"]
    entry_cfg = cfg.get("entry", {})
    match_side = entry_cfg.get("match_side", "any")
    exit_days = sim_cfg.get("exit_days", [1, 3, 5, 10, 21])
    spread_pct = sim_cfg.get("spread_width_pct", 0.02)

    log.info("Loading analysis plays from tab '%s'", tab)
    candidates, market_regime = _load_analysis(tab, start, end)
    if not candidates:
        log.warning("No plays found in '%s' — run /options analyze (range mode) first to populate it", tab)
        sys.exit(0)

    log.info("Loading flow data from Drive for entry matching + real exits")
    flow_by_date, contract_index = _load_flow(start, end, max(exit_days))

    # Pass 1 — classify each play and match it to its real flow contract.
    matched, contracts, skipped = [], {}, {"unsupported": 0, "no_entry_match": 0, "unpriced": 0}
    for c in candidates:
        c["market_regime"] = market_regime.get(c["date"], "")
        cls = classify_play(c["play"])
        if cls["structure"] == "unsupported":
            skipped["unsupported"] += 1
            continue

        structure = cls["structure"]
        is_ic = (structure == "iron_condor")

        # Iron condors match the short-put leg for S_entry / IV anchoring.
        match_opt_type = "Put" if is_ic else cls["option_type"]
        ic_strikes = cls.get("strikes", [])
        if is_ic:
            # Short put is strikes[1] in 4-strike notation, strikes[0] in 2-strike.
            long_strike = ic_strikes[1] if len(ic_strikes) >= 4 else (ic_strikes[0] if ic_strikes else None)
        else:
            long_strike = ic_strikes[0] if ic_strikes else None

        target_exp = _extract_expiration(c["play"], c["signal_date"])
        entry_row = _match_entry(c, match_opt_type, flow_by_date.get(c["date"], []),
                                 match_side, long_strike, target_exp)
        if entry_row is None:
            skipped["no_entry_match"] += 1
            continue

        K = _num(entry_row.get("Strike"))
        exp_raw = str(entry_row.get("Expires", entry_row.get("Expiration Date", ""))).strip()
        exp_date = _parse_expiration(exp_raw)
        matched.append((c, cls, entry_row))

        # Iron condors are fully BS-priced; no Barchart history needed for their legs.
        if not is_ic and K and exp_date:
            opt_type = cls["option_type"]
            key = _contract_key(c["ticker"], opt_type, K, exp_raw)
            contracts.setdefault(key, {"key": key, "symbol": c["ticker"],
                                       "opt_type": opt_type, "strike": K, "expiration": exp_date})
            # Register the contra leg so its real Barchart history is fetched/cached
            # and netted in _simulate (BS fallback when no history).
            K_short = _short_strike(structure, K, cls.get("strikes", []), spread_pct)
            if K_short is not None:
                skey = _contract_key(c["ticker"], opt_type, K_short, exp_raw)
                contracts.setdefault(skey, {"key": skey, "symbol": c["ticker"],
                                            "opt_type": opt_type, "strike": K_short,
                                            "expiration": exp_date})

    # Pass 2 — fetch real historical option prices from Barchart (cached) when enabled.
    barchart_series: dict[tuple, list] = {}
    if "barchart" in sim_cfg.get("exit_sources", ["barchart", "reappearance", "bs"]) and contracts:
        headless = os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
        log.info("Fetching Barchart history for %d distinct contract(s)", len(contracts))
        barchart_series = asyncio.run(_fetch_option_histories(list(contracts.values()), headless))

    # Pass 3 — simulate.
    log.info("Simulating %d matched plays", len(matched))
    results = []
    for c, cls, entry_row in matched:
        result = _simulate(c, cls, entry_row, contract_index, barchart_series, sim_cfg)
        if result:
            results.append(result)
        else:
            skipped["unpriced"] += 1

    log.info("Simulated %d plays (skipped: %d unsupported, %d no flow match, %d unpriced)",
             len(results), skipped["unsupported"], skipped["no_entry_match"], skipped["unpriced"])

    _write_results(results, cfg, exit_days, args.dry_run)


if __name__ == "__main__":
    main()
