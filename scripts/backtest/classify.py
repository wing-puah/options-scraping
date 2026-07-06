import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import _UNSUPPORTED_PATTERNS
from .helpers import _to_float, _opt_price, _row_iv, _parse_expiration
from .legs import parse_legs

log = logging.getLogger("backtest")

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


# ─── Play text extraction ──────────────────────────────────────────────────────

def _primary_text(play_text: str) -> str:
    """The play text with the 'Alt:' alternative-interpretation section stripped.

    The Alt line describes what the flow might OTHERWISE be (e.g. 'covered-call
    financing'), so its structure keywords, strikes, and dates must never feed
    classification or contract resolution.
    """
    return re.split(r"\n\s*Alt:", play_text or "", maxsplit=1)[0]


def _extract_expiration(play_text: str, ref: date) -> date | None:
    """Pull the expiration the play names, e.g. 'Jun 18'. Year inferred from signal date."""
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})",
                  _primary_text(play_text), re.IGNORECASE)
    if not m:
        return None
    mon, day = _MONTHS[m.group(1)[:3].lower()], int(m.group(2))
    try:
        d = date(ref.year, mon, day)
    except ValueError:
        return None
    return d if d >= ref else date(ref.year + 1, mon, day)


def _extract_all_expirations(play_text: str, ref: date) -> list[date]:
    """Return all expiration dates mentioned in play text, sorted ascending (duplicates removed).

    Used by the calendar/diagonal classifier which needs near + far expirations.
    """
    seen: set[date] = set()
    results: list[date] = []
    for m in re.finditer(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})",
        _primary_text(play_text), re.IGNORECASE,
    ):
        mon = _MONTHS[m.group(1)[:3].lower()]
        day = int(m.group(2))
        try:
            d = date(ref.year, mon, day)
        except ValueError:
            continue
        if d < ref:
            d = date(ref.year + 1, mon, day)
        if d not in seen:
            seen.add(d)
            results.append(d)
    return sorted(results)


_PC = r"[PCpc]?"  # optional put/call suffix after a strike digit


def _extract_strikes(play_text: str) -> list[float]:
    """Pull the strike(s) the play names: 4-strike IC, 2-strike spread, or single.

    Handles both slash-separated quads (A/B/C/D) and IC-pair format
    (short A[P]/B[C], long C[P]/D[C]) where strikes carry optional P/C suffixes.
    """
    play_text = _primary_text(play_text)
    # IC-pair format: "short NNNp/NNNc, long NNNp/NNNc"
    m4_ic = re.search(
        rf"(\d+(?:\.\d+)?){_PC}\s*/\s*(\d+(?:\.\d+)?){_PC}\s*,\s*\w+\s+(\d+(?:\.\d+)?){_PC}\s*/\s*(\d+(?:\.\d+)?){_PC}",
        play_text,
    )
    if m4_ic:
        return [float(m4_ic.group(i)) for i in range(1, 5)]
    # Slash-separated quad: A/B/C/D (with optional P/C suffix on each)
    m4 = re.search(
        rf"(\d+(?:\.\d+)?){_PC}\s*/\s*(\d+(?:\.\d+)?){_PC}\s*/\s*(\d+(?:\.\d+)?){_PC}\s*/\s*(\d+(?:\.\d+)?){_PC}",
        play_text,
    )
    if m4:
        return [float(m4.group(i)) for i in range(1, 5)]
    # Triple-strike: A/B/C (butterfly)
    m3 = re.search(
        rf"(\d+(?:\.\d+)?){_PC}\s*/\s*(\d+(?:\.\d+)?){_PC}\s*/\s*(\d+(?:\.\d+)?){_PC}",
        play_text,
    )
    if m3:
        return [float(m3.group(i)) for i in range(1, 4)]
    # 2-strike spread (with optional P/C suffix)
    m = re.search(rf"(\d+(?:\.\d+)?){_PC}\s*/\s*(\d+(?:\.\d+)?){_PC}", play_text)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    m = re.search(r"(?:calls?|puts?|straddle|strangle|butterfly|condor|at|@)\s+(\d+(?:\.\d+)?)",
                  play_text, re.IGNORECASE)
    if m:
        return [float(m.group(1))]
    # Number immediately before call/put keyword (e.g. "500 call calendar")
    m = re.search(r"(\d+(?:\.\d+)?)\s+(?:calls?|puts?)", play_text, re.IGNORECASE)
    if m:
        return [float(m.group(1))]
    return []


def _extract_horizon_dte(play_text: str) -> int | None:
    """
    Extract a DTE estimate for expiry approximation when no explicit date is in text.
    Priority: inline range → inline single → bracket bucket boundary.
    """
    play_text = _primary_text(play_text)
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
                    | iron_condor | straddle | strangle | butterfly | condor
                    | explicit_legs | unsupported
      option_type — Call | Put | None (None for iron_condor only)
      strikes     — parsed strikes (may be empty); sorted ascending for multi-leg
      is_credit   — True for premium-selling structures (net credit at entry)
      legs        — present only for structure == "explicit_legs": the parsed legs

    An explicit leg-string (e.g. "+3 AMD:2025-10-16:130:C") is recognised first and
    short-circuits the freeform heuristics — and the _UNSUPPORTED_PATTERNS gate — so
    that calendar / diagonal / ratio spreads spelled out as legs are accepted.
    """
    explicit = parse_legs(play_text)
    if explicit:
        return {"structure": "explicit_legs", "option_type": None, "strikes": [],
                "is_credit": False, "legs": explicit}

    # Keyword matching sees only the primary play line — the Alt: section's
    # alternative reads ('covered-call', 'straddle', …) must not classify.
    text = _primary_text(play_text).lower()
    if not text.strip():
        return {"structure": "unsupported", "option_type": None, "strikes": [], "is_credit": False}

    strikes = _extract_strikes(play_text)

    # Iron condor must be checked before the generic "condor" unsupported pattern.
    if "iron condor" in text:
        return {"structure": "iron_condor", "option_type": None, "strikes": strikes, "is_credit": True}

    _credit_words = frozenset(("credit", "sell", "short", "write", "sold"))
    has_credit = bool(_credit_words & set(text.split()))

    if "straddle" in text:
        opt_type = "Put" if ("put" in text and "call" not in text) else "Call"
        return {"structure": "straddle", "option_type": opt_type,
                "strikes": strikes[:1], "is_credit": has_credit}

    if "strangle" in text:
        opt_type = "Put" if ("call" not in text) else "Call"
        return {"structure": "strangle", "option_type": opt_type,
                "strikes": sorted(strikes[:2]), "is_credit": has_credit}

    if "butterfly" in text:
        opt_type = "Put" if ("put" in text and "call" not in text) else "Call"
        return {"structure": "butterfly", "option_type": opt_type,
                "strikes": sorted(strikes[:3]), "is_credit": has_credit}

    if "condor" in text:
        opt_type = "Put" if ("put" in text and "call" not in text) else "Call"
        return {"structure": "condor", "option_type": opt_type,
                "strikes": sorted(strikes[:4]), "is_credit": has_credit}

    if "calendar" in text:
        opt_type = "Put" if ("put" in text and "call" not in text) else "Call"
        return {"structure": "calendar", "option_type": opt_type,
                "strikes": strikes[:1], "is_credit": has_credit}

    if "diagonal" in text:
        opt_type = "Put" if ("put" in text and "call" not in text) else "Call"
        return {"structure": "diagonal", "option_type": opt_type,
                "strikes": sorted(strikes[:2]), "is_credit": has_credit}

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
    if "call spread" in text:
        structure = "bear_call_spread" if has_credit else "bull_call_spread"
        return {"structure": structure, "option_type": "Call", "strikes": strikes, "is_credit": has_credit}
    if "put spread" in text:
        structure = "bull_put_spread" if has_credit else "bear_put_spread"
        return {"structure": structure, "option_type": "Put", "strikes": strikes, "is_credit": has_credit}

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

def _nearest_friday(d: date) -> date:
    """Return d if it's a Friday, else advance to the next Friday."""
    days_ahead = (4 - d.weekday()) % 7  # Friday is weekday 4
    return d + timedelta(days=days_ahead)


_MAX_EXPIRY_DEVIATION_DAYS = 45  # reject cache hits more than ~1.5 monthly cycles off target


def _nearest_cached_expiry(
    cache_dir: Path, ticker: str, opt_type: str, K: float,
    signal_date: date, horizon_dte: int | None,
) -> date | None:
    """Scan cache for contracts matching ticker/opt_type/K; pick expiry closest to signal_date + horizon_dte.

    A cache hit is only accepted when it falls within _MAX_EXPIRY_DEVIATION_DAYS of the
    target date so that, e.g., a Sep LEAP is not used for a play that specified 35-60 DTE.
    When no qualifying cache entry exists the expiry is synthesised as the nearest Friday
    on or after signal_date + horizon_dte (requires horizon_dte to be known).
    """
    cp = "C" if opt_type == "Call" else "P"
    matches = list(cache_dir.glob(f"{ticker.upper()}_*_{K:.2f}{cp}.csv"))
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
    if best is not None and (best_delta or 0) <= _MAX_EXPIRY_DEVIATION_DAYS:
        return best
    # No qualifying cache hit — synthesise from horizon_dte
    if horizon_dte is None:
        return None
    synth = _nearest_friday(target)
    if best is not None:
        log.debug(
            "cache hit for %s %s %.2f expiry=%s is %d days off target (limit %d); "
            "synthesising expiry %s from horizon_dte=%d",
            ticker, opt_type, K, best, best_delta, _MAX_EXPIRY_DEVIATION_DAYS, synth, horizon_dte,
        )
    else:
        log.debug("no cache for %s %s %.2f; synthesising expiry %s from horizon_dte=%d",
                  ticker, opt_type, K, synth, horizon_dte)
    return synth


def _resolve_expiry(
    candidate: dict, opt_type: str, K: float, cache_dir: Path,
) -> tuple[date | None, tuple | None]:
    """Resolve the contract expiration: explicit month/day in play text first, then a
    cache scan for the nearest listed expiry.

    ``opt_type`` is used only to scan the cache for matching contracts. Returns
    ``(date, None)`` on success or ``(None, ("no_expiry", message))`` on failure.
    Shared by the generic identifier and by ``IronCondorPlay`` (which resolves its own
    short-put anchor).

    An explicit month/day is cross-checked against the play's declared horizon: a
    date whose DTE falls outside [H/4, 4·H] is a context date (e.g. an earnings
    print the flow is 'dated past'), not the intended expiry, and is discarded in
    favor of the horizon-derived expiry.
    """
    horizon_dte = _extract_horizon_dte(candidate["play"])
    exp = _extract_expiration(candidate["play"], candidate["signal_date"])
    if exp is not None and horizon_dte:
        dte = (exp - candidate["signal_date"]).days
        if not (horizon_dte / 4 <= dte <= horizon_dte * 4):
            log.debug(
                "explicit expiry %s (%dd) for %s contradicts horizon %dd; "
                "resolving from horizon instead",
                exp, dte, candidate["ticker"], horizon_dte,
            )
            exp = None
    if exp is None:
        exp = _nearest_cached_expiry(
            cache_dir, candidate["ticker"], opt_type, K,
            candidate["signal_date"], horizon_dte,
        )
    if exp is None:
        return None, ("no_expiry", f"no expiry found for {candidate['ticker']} {opt_type} {K}")
    return exp, None


# ─── Entry row from Barchart history cache ─────────────────────────────────────

def _entry_row_from_history(
    barchart_details: dict[tuple, dict],
    contract_key: tuple,
    signal_date: date,
    K: float,
    expiration_date: date,
    timing: str = "signal_eod",
) -> dict | None:
    """Build a synthetic entry_row dict from the Barchart per-contract history cache.

    timing picks the entry day (stamped on the row as ``_entry_date``):
      • ``signal_eod`` — first history day on-or-after the signal date (legacy).
      • ``next_open``  — first history day strictly AFTER the signal date (the fill
        happens at the next open); falls back to the signal day itself when no later
        day exists within the staleness window, so the play is still priced (at the
        signal day's EOD mark) rather than dropped.
    Either way the day must be within the staleness window of the signal date.
    """
    _ENTRY_STALENESS_DAYS = 5

    day_rows = barchart_details.get(contract_key)
    if not day_rows:
        return None
    days = sorted(day_rows)
    entry_day = None
    if timing == "next_open":
        d_after = next((d for d in days if d > signal_date), None)
        if d_after is not None and (d_after - signal_date).days <= _ENTRY_STALENESS_DAYS:
            entry_day = d_after
        elif signal_date in day_rows:
            entry_day = signal_date
    if entry_day is None:
        entry_day = next((d for d in days if d >= signal_date), None)
        if entry_day is None:
            return None
        if (entry_day - signal_date).days > _ENTRY_STALENESS_DAYS:
            log.warning(
                "SKIP no_history: %s — earliest data %s is %d days after signal %s; "
                "skipping (cannot be a true backtest without near-entry price)",
                contract_key, entry_day, (entry_day - signal_date).days, signal_date,
            )
            return None
    row = day_rows[entry_day]
    return {
        "Strike": K,
        "DTE": max(0, (expiration_date - entry_day).days),
        "IV": row.get("IV"),
        "Price~": row.get("Price~"),
        "Trade": row.get("_mark"),
        "Expires": expiration_date.isoformat(),
        "Delta": row.get("Delta"),
        "_entry_date": entry_day,
    }


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
        strike = _to_float(row.get("Strike"))
        iv = _row_iv(row)
        if _opt_price(row) is None or strike is None or not iv or iv <= 0:
            continue
        candidates.append((row, strike))

    if not candidates:
        return None
    if long_strike is None and target_exp is None:
        return max(candidates, key=lambda rs: _to_float(rs[0].get("Premium"), 0) or 0)[0]

    def score(rs):
        row, strike = rs
        strike_term = abs(strike - long_strike) / long_strike if long_strike else 0.0
        exp_term = 0.0
        if target_exp is not None:
            rexp = _parse_expiration(row.get("Expires", row.get("Expiration Date", "")))
            exp_term = abs((rexp - target_exp).days) / 30 if rexp else 1000.0
        return strike_term + exp_term

    return min(candidates, key=score)[0]
