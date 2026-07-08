"""
Counterpart IV: settlement-IV for the option legs that DIDN'T trade.

The paper-faithful IV spread (Cremers/Weinbaum, via Lin/Lu/Driessen 2013) needs
BOTH a call and a put at the SAME (strike, expiration) to form a matched pair.
The traded-flow subset almost never carries both legs — so `iv_spread` is ~98%
blank on flow alone (see config/rollup-reference.md "Validity concern").

Barchart's per-contract price-history endpoint exposes a full daily series
INCLUDING settlement IV / OI / volume for any listed contract, whether or not it
traded in the flow. So for each single-sided (strike, expiration) that DID trade,
we can fetch the missing opposite leg's settlement IV *as of the trade date D* and
complete the pair. `scripts/collector/fetch_counterpart_iv.py` scrapes those legs and stores
them in a per-date sidecar on Drive; this module holds the pure logic both the producer
(the script) and the consumer (`lib/flow_summary/core._flow_ticker_rows`) share so
the contract keys and units always agree.

Everything is keyed to the exact trade date D (from the compiled filename), so the
same date-indexed lookup serves the backtest (historical D) and a live run
(latest D) through one code path.
"""
from __future__ import annotations

from datetime import date

# The paper-filter constants (DTE window, IV bounds, minimum underlying /
# option price — Lin/Lu/Driessen 2013 appendix, after Xing/Zhang/Zhao 2010)
# live in lib/flow_summary/_helpers (the common leaf module of this producer
# and the core.py consumer) and are re-exported here as this module's public
# names. Only in-window contracts can form a scored pair, so only their
# counterparts are worth fetching; legs failing the other filters are dropped
# at consumption (`build_iv_lookup` here, the traded-leg gate in core.py).
from lib.flow_summary._helpers import (  # noqa: F401 — DTE/filters re-exported
    DTE_HI,
    DTE_LO,
    IV_MAX_PTS,
    IV_MIN_PTS,
    MIN_OPTION_PRICE,
    MIN_UNDERLYING,
    _FLOW_DTE,
    _FLOW_EXPIRY,
    _FLOW_STRIKE,
    _FLOW_SYMBOL,
    _FLOW_TYPE,
    _FLOW_UPRICE,
    _to_float,
)

# Sidecar CSV schema. One row per fetched counterpart contract; `iv` is settlement
# IV in POINTS (e.g. 107.86), matching the flow feed's intraday IV units, so the
# rollup can mix traded and counterpart legs without a unit conversion (NB:
# enrich_oi's `eod_iv` column stores the same Barchart field as a FRACTION —
# `_settlement_iv` in core.py rescales it). `price` is the day-D mark
# (mid(Bid,Ask) → Latest) used for the paper's $0.125 minimum-price filter; blank
# in sidecars written before the column existed (treated as pass). `fetched_on`
# is the run date (provenance + resume marker: a contract with a non-blank
# `fetched_on` is never re-fetched, even when Barchart returned nothing for it).
COUNTERPART_COLUMNS = [
    "Symbol", "Type", "Strike", "Expires", "trade_date",
    "iv", "oi", "vol", "delta", "price", "fetched_on",
]


def sidecar_name(date_str: str) -> str:
    """Per-date counterpart-IV sidecar file name (one file spans all flow prefixes).

    Stored in the date folder on Drive; read back by the analysis fetch step and,
    transitively, the backtest (which reads the IVSpread already written onto the
    analysis row). Date-keyed so backtest (historical D) and live (latest D) share
    one path.
    """
    return f"counterpart-iv-{date_str.replace('-', '')}.csv"


def _expiry_date(value) -> date | None:
    """Parse a flow ``Expires`` cell (ISO datetime or date) into a date."""
    s = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def contract_key(symbol: str, opt_type: str, strike: float, expiry: date | str) -> tuple:
    """Canonical contract identity shared by producer and consumer.

    ``(UPPER_SYMBOL, 'call'|'put', round(strike, 4), 'YYYY-MM-DD')``. The rollup's
    matched-pair grouping keys on ``(round(strike, 4), 'YYYY-MM-DD')`` within a
    symbol, so this stays aligned with it.
    """
    exp = expiry.isoformat() if isinstance(expiry, date) else str(expiry)[:10]
    return (symbol.upper().strip(), opt_type.strip().lower(), round(float(strike), 4), exp)


def needed_counterparts(flow_rows: list[dict]) -> list[dict]:
    """Counterpart legs to fetch so single-sided in-window pairs become matched.

    For each ``(symbol, strike, expiration)`` in the 10–60 DTE window that traded
    on exactly ONE side (call XOR put), the missing side is a candidate. Returns
    deduped contract dicts ``{symbol, opt_type, strike, expiration, key}`` where
    ``expiration`` is a ``date`` and ``key`` is :func:`contract_key`. A strike that
    already traded both sides needs nothing; a strike that traded neither is not a
    candidate (there is no flow anchor and no way to enumerate the chain here).
    Rows on a sub-$5 underlying are skipped — the paper's filter (ii) drops the
    whole name at consumption, so its counterparts aren't worth scraping.
    """
    sides: dict[tuple, set[str]] = {}
    anchor: dict[tuple, dict] = {}
    for r in flow_rows:
        sym = (r.get(_FLOW_SYMBOL) or "").strip()
        opt = (r.get(_FLOW_TYPE) or "").strip().lower()
        if not sym or opt not in ("call", "put"):
            continue
        spot = _to_float(r.get(_FLOW_UPRICE))
        if 0 < spot < MIN_UNDERLYING:  # unknown spot (0.0) passes
            continue
        dte = _to_float(r.get(_FLOW_DTE))
        if dte is None or not (DTE_LO <= dte <= DTE_HI):
            continue
        strike = _to_float(r.get(_FLOW_STRIKE))
        exp = _expiry_date(r.get(_FLOW_EXPIRY))
        if strike is None or exp is None:
            continue
        pk = (sym.upper(), round(strike, 4), exp)
        sides.setdefault(pk, set()).add(opt)
        anchor[pk] = {"symbol": sym, "strike": strike, "expiration": exp}

    out: list[dict] = []
    seen: set[tuple] = set()
    for pk, traded in sides.items():
        if len(traded) == 2:
            continue  # already a matched pair in the flow
        missing = "put" if "call" in traded else "call"
        a = anchor[pk]
        key = contract_key(a["symbol"], missing, a["strike"], a["expiration"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "symbol": a["symbol"], "opt_type": missing,
            "strike": a["strike"], "expiration": a["expiration"], "key": key,
        })
    return out


def build_iv_lookup(backfill_rows: list[dict]) -> dict[str, list[dict]]:
    """Sidecar rows → ``{UPPER_SYMBOL: [contract, ...]}`` for the rollup.

    Each contract is ``{opt_type, strike, expiry, iv, oi, vol}`` with ``iv`` in
    points, ``expiry`` an ISO date string, and ``oi``/``vol`` floats or None. Rows
    with no usable ``iv`` (Barchart returned nothing — kept only as resume markers)
    are dropped, as are legs failing the paper's filters: IV outside
    [IV_MIN_PTS, IV_MAX_PTS], non-positive open interest, or a known ``price``
    below MIN_OPTION_PRICE (a blank price — older sidecars — passes). The
    consumer only sees legs it can actually pair per the paper.
    """
    out: dict[str, list[dict]] = {}
    for r in backfill_rows:
        iv = _to_float(r.get("iv"))
        if not (IV_MIN_PTS <= iv <= IV_MAX_PTS):
            continue
        oi = _to_float(r.get("oi"))
        if oi <= 0:
            continue
        price = _to_float(r.get("price"))
        if 0 < price < MIN_OPTION_PRICE:  # unknown price (0.0 / old sidecars) passes
            continue
        sym = (r.get("Symbol") or "").strip().upper()
        opt = (r.get("Type") or "").strip().lower()
        strike = _to_float(r.get("Strike"))
        exp = _expiry_date(r.get("Expires"))
        if not sym or opt not in ("call", "put") or strike is None or exp is None:
            continue
        out.setdefault(sym, []).append({
            "opt_type": opt,
            "strike": round(strike, 4),
            "expiry": exp.isoformat(),
            "iv": iv,
            "oi": oi,
            "vol": _to_float(r.get("vol")),
        })
    return out
