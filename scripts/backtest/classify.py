import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import _UNSUPPORTED_PATTERNS
from .helpers import _num, _opt_price, _row_iv, _parse_expiration, _short_strike

log = logging.getLogger("backtest")

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


# ─── Play text extraction ──────────────────────────────────────────────────────

def _extract_expiration(play_text: str, ref: date) -> date | None:
    """Pull the expiration the play names, e.g. 'Jun 18'. Year inferred from signal date."""
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
    """Pull the strike(s) the play names: 4-strike IC, 2-strike spread, or single."""
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


def _extract_horizon_dte(play_text: str) -> int | None:
    """
    Extract a DTE estimate for expiry approximation when no explicit date is in text.
    Priority: inline range → inline single → bracket bucket boundary.
    """
    m = re.search(r'\(?(\d+)\s*[-–]\s*(\d+)\s*DTE\)?', play_text, re.IGNORECASE)
    if m:
        return (int(m.group(1)) + int(m.group(2))) // 2
    m = re.search(r'\(?(\d+)\s*DTE\)?', play_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r'\[(?:[^\]]*\|){2}\s*(\d+)\s*\]', play_text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


# ─── Play classification ───────────────────────────────────────────────────────

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

    # Iron condor must be checked before the generic "condor" unsupported pattern.
    if "iron condor" in text:
        return {"structure": "iron_condor", "option_type": None, "strikes": strikes, "is_credit": True}

    for pat in _UNSUPPORTED_PATTERNS:
        if pat in text:
            return {"structure": "unsupported", "option_type": None, "strikes": [], "is_credit": False}

    # Named credit spreads before generic "call/put spread" fallbacks.
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

    # Long single-leg.
    bullish = "call" in text or "bull" in text
    bearish = "put" in text or "bear" in text
    if bullish and not bearish:
        return {"structure": "long_call", "option_type": "Call", "strikes": strikes[:1], "is_credit": False}
    if bearish and not bullish:
        return {"structure": "long_put", "option_type": "Put", "strikes": strikes[:1], "is_credit": False}

    return {"structure": "unsupported", "option_type": None, "strikes": [], "is_credit": False}


# ─── Contract identification ───────────────────────────────────────────────────

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
) -> tuple[tuple, tuple | None]:
    """
    Identify (K, expiration_date, opt_type, K_short) from the play text.
    Returns (result_tuple, None) on success, (None, (category, reason)) on failure.

    Expiry resolution: explicit month/day in play text first, then cache scan.
    """
    structure = cls.get("structure")
    is_ic = structure == "iron_condor"

    if is_ic:
        opt_type = "Put"
        ic_strikes = cls.get("strikes", [])
        if not ic_strikes:
            return None, ("no_strike", "iron condor: no strikes in play text")
        K = ic_strikes[1] if len(ic_strikes) >= 4 else ic_strikes[0]
    else:
        opt_type = cls.get("option_type")
        if not opt_type:
            return None, ("no_strike", "no option_type resolved")
        play_strikes = cls.get("strikes", [])
        if not play_strikes:
            return None, ("no_strike", "no strikes in play text")
        K = play_strikes[0]

    exp = _extract_expiration(candidate["play"], candidate["signal_date"])
    if exp is None:
        exp = _nearest_cached_expiry(
            cache_dir, candidate["ticker"], opt_type, K,
            candidate["signal_date"], _extract_horizon_dte(candidate["play"]),
        )
        if exp is None:
            return None, ("no_expiry", f"no expiry found for {candidate['ticker']} {opt_type} {K}")

    K_short = None if is_ic else _short_strike(structure, K, cls.get("strikes", []), spread_pct)
    return (K, exp, opt_type, K_short), None


# ─── Entry row from Barchart history cache ─────────────────────────────────────

def _entry_row_from_history(
    barchart_details: dict[tuple, dict],
    contract_key: tuple,
    signal_date: date,
    K: float,
    expiration_date: date,
) -> dict | None:
    """Build a synthetic entry_row dict from the Barchart per-contract history cache."""
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


# ─── Flow entry matching (kept for tests; not called by main) ──────────────────

def _match_entry(candidate: dict, option_type: str, flow_rows: list[dict],
                 match_side: str, long_strike: float | None = None,
                 target_exp: date | None = None):
    """
    Find the real flow contract a play refers to. When strike/expiry are named,
    pick the row closest on those; otherwise pick by largest premium.
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
        row, strike = rs
        strike_term = abs(strike - long_strike) / long_strike if long_strike else 0.0
        exp_term = 0.0
        if target_exp is not None:
            rexp = _parse_expiration(row.get("Expires", row.get("Expiration Date", "")))
            exp_term = abs((rexp - target_exp).days) / 30 if rexp else 1000.0
        return strike_term + exp_term

    return min(candidates, key=score)[0]
