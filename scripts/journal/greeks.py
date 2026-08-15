"""
Barchart fallback for the open book's greeks, when the broker pull carries none.

PRODUCTION TIER. `pull.py`'s IBKR path gets `delta`/`gamma`/`theta`/`vega`/`iv`
straight from the Client Portal snapshot endpoint. An IBKR **Flex CSV** export is
a second, offline way to build a `RawPull` (exact fills and positions, conid-keyed
identity) but it carries NO greeks at all — Flex is a settlement/activity export,
not a market-data feed. This module is what fills that gap for the OPEN BOOK: for
every open position it looks up the matching Barchart option-history row as of the
trade date and reads the settlement greeks off it, the same per-contract feed
`scripts/collector/fetch_counterpart_iv.py` already scrapes for a different reason
(the IV spread rather than the open book).

THE INVARIANT THIS MODULE EXISTS TO HONOUR (see the "missing greek" section of
CLAUDE.md and the module docstring of `config.py`): a delta the broker/feed never
returned is `None`, NEVER `0.0`. A genuinely flat 0.0 delta is real information; a
gap in coverage is not, and confusing the two silently understates the book. Every
contract Barchart has nothing for ends up `delta=None,
source=DELTA_SOURCE_UNAVAILABLE` — never a zero standing in for "we don't know".

NO LOOKAHEAD. Barchart's settlement row for date D is only known once D's session
has closed, so `enrich()` never reads a row dated AFTER `as_of` — that would be
marking today's book off tomorrow's close, an error this repo treats as a
correctness bug (the same posture `scripts/backtest_study/harness.py` takes on
entry pricing). When the exact `as_of` row is absent, the fetch falls back to the
latest row ON OR BEFORE it and the staleness is logged (not stored — the rawpull
`Greek` shape has no field for it; `rawpull.py` is not this file's to change).

IV UNIT CONVENTION: Barchart's `IV` column is a percent string (e.g. "45.20%").
Most %/share-type fields in this repo are stored as decimal fractions (the
`feedback_percentages_decimal` convention), but IV is the documented exception —
`lib/counterpart_iv.py` keeps it in POINTS ("iv is settlement IV in POINTS,
matching the flow feed's intraday IV units") and `scripts/journal/report.py`'s
`iv_fmt()` says the same thing plainly: "IV is the one share-type field the repo
keeps in POINTS, not a fraction." This module follows suit: `to_float("45.20%")`
strips the `%` and is stored as `45.20`, unchanged — no /100.

TESTABILITY. The real path opens a `BarchartSession` (a Playwright browser) and
must not run in a unit test. Every network call in `enrich()` funnels through one
async `session.fetch_history_fast(url, timeout_ms)` call, and `session` is an
injectable keyword — tests pass a small fake object with that one async method
(the same convention `tests/test_counterpart_history.py` uses for
`scripts/collector/fetch_counterpart_history.py`) and drive it with
`asyncio.run(...)`, so the test suite never opens a browser or hits the network.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date
from pathlib import Path

from lib.barchart import options as barchart_options
from lib.barchart import underlying as barchart_underlying
from lib.barchart.session import BarchartSession
from lib.parsing import to_float

from . import rawpull
from .config import DELTA_SOURCE_BARCHART, DELTA_SOURCE_UNAVAILABLE

log = logging.getLogger(__name__)

_TIMEOUT_MS = 30000
_SLEEP_S = 0.4  # matches fetch_counterpart_iv.py's between-contract pacing
_DEFAULT_COOKIES = Path(__file__).resolve().parents[2] / "cookies" / "barchart_session.json"


def _blank_greek() -> dict:
    """The 'we have nothing' Greek row — every field None, never a zero fill-in."""
    return {"delta": None, "gamma": None, "theta": None, "vega": None, "iv": None,
            "source": DELTA_SOURCE_UNAVAILABLE}


def _opt_type(right: str) -> str:
    """rawpull's Contract stores 'C'/'P'; lib.barchart.options wants 'Call'/'Put'."""
    return "Call" if str(right).upper().startswith("C") else "Put"


def _parse_contract(conid: int, c: dict) -> tuple[str, date, float, str] | None:
    """(symbol, expiry, strike, opt_type) from a rawpull Contract dict, or None.

    A contract detail that fails to parse is exactly as unpriceable as one that
    is missing outright — both land the conid in `unavailable`, never in a crash
    that would drop the whole enrichment for one bad row.
    """
    try:
        symbol = str(c["symbol"]).upper().strip()
        expiry = date.fromisoformat(str(c["expiry"])[:10])
        strike = float(c["strike"])
        opt_type = _opt_type(c["right"])
        if not symbol:
            raise ValueError("blank symbol")
        return symbol, expiry, strike, opt_type
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("conid %d: unusable contract detail (%s) — treating as unpriceable",
                    conid, exc)
        return None


def _as_of_row(details: dict[date, dict], as_of: date) -> tuple[dict | None, int | None]:
    """(row, staleness_days) for the latest row on or before `as_of`, else (None, None).

    Never picks a date AFTER `as_of` — see the module docstring's no-lookahead
    note. `staleness_days` is 0 for an exact match; the caller logs it (there is
    nowhere in the rawpull schema to persist it).
    """
    candidates = [d for d in details if d <= as_of]
    if not candidates:
        return None, None
    picked = max(candidates)
    return details[picked], (as_of - picked).days


async def _fetch_cached(session, path: Path | None, url: str, timeout_ms: int) -> str | None:
    """Read `path` if it already exists, else fetch `url` and (if given) persist it.

    Same cache-first shape `scripts/collector/fetch_counterpart_history.py` and
    `fetch_underlying_ohlc.py` use: a re-run of the same trade date should not
    re-hit Barchart for a contract already on disk. `path=None` (the caller's
    `cache_dir=None`, the common case for a one-off daily run) simply disables
    the cache — every call fetches.
    """
    if path is not None and path.exists():
        return path.read_text(encoding="utf-8")
    csv_text = await session.fetch_history_fast(url, timeout_ms)
    if csv_text and path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(csv_text, encoding="utf-8")
    return csv_text


async def _enrich_greeks(session, raw: dict, as_of: date, cache_dir: Path | None,
                         timeout_ms: float, sleep_s: float) -> tuple[dict, list[int], list[int]]:
    """`{conid_str: Greek}` for every open-book conid, plus (sourced, unavailable) conid lists."""
    contracts = raw.get("contracts") or {}
    conids = sorted({int(p["conid"]) for p in raw.get("positions") or [] if p.get("conid")})

    greeks: dict[str, dict] = {}
    sourced: list[int] = []
    unavailable: list[int] = []

    for conid in conids:
        c = contracts.get(str(conid))
        parsed = _parse_contract(conid, c) if c is not None else None
        if parsed is None:
            greeks[str(conid)] = _blank_greek()
            unavailable.append(conid)
            continue

        symbol, expiry, strike, opt_type = parsed
        path = (barchart_options.cache_path(cache_dir, symbol, expiry, strike, opt_type)
                if cache_dir else None)
        url = barchart_options.option_history_url(symbol, expiry, strike, opt_type)
        csv_text = await _fetch_cached(session, path, url, timeout_ms)
        details = (barchart_options.parse_history_details(csv_text, require_mark=False)
                   if csv_text else {})
        row, staleness = _as_of_row(details, as_of)

        # `is None`, never truthiness — a genuinely flat 0.0 delta must survive.
        delta = to_float(row.get("Delta")) if row is not None else None
        if delta is None:
            greeks[str(conid)] = _blank_greek()
            unavailable.append(conid)
        else:
            if staleness:
                log.info("%s %s %s: no Barchart row for %s — using the %dd-stale "
                         "settlement instead", symbol, expiry.isoformat(), opt_type,
                         as_of.isoformat(), staleness)
            greeks[str(conid)] = {
                "delta": delta,
                "gamma": to_float(row.get("Gamma")),
                "theta": to_float(row.get("Theta")),
                "vega": to_float(row.get("Vega")),
                "iv": to_float(row.get("IV")),  # points, not a fraction — see module docstring
                "source": DELTA_SOURCE_BARCHART,
            }
            sourced.append(conid)

        if sleep_s:
            await asyncio.sleep(sleep_s)

    return greeks, sourced, unavailable


async def _enrich_underlying(session, raw: dict, as_of: date, cache_dir: Path | None,
                             timeout_ms: float, sleep_s: float) -> dict[str, float]:
    """`{SYMBOL: spot}` as of `as_of`, for every symbol behind an open position.

    A symbol Barchart has no as-of-or-before row for is left OUT of the dict
    entirely — never defaulted to 0.0, which would price every open position on
    that name at zero delta-notional, the exact understatement the missing/zero
    invariant forbids.
    """
    contracts = raw.get("contracts") or {}
    open_conids = {str(p["conid"]) for p in raw.get("positions") or [] if p.get("conid")}
    symbols = sorted({str(c["symbol"]).upper().strip()
                      for cid, c in contracts.items()
                      if cid in open_conids and c.get("symbol")})

    prices: dict[str, float] = {}
    for symbol in symbols:
        path = (cache_dir / f"{symbol}_underlying.csv") if cache_dir else None
        url = barchart_underlying.stock_history_url(symbol)
        csv_text = await _fetch_cached(session, path, url, timeout_ms)
        details = (barchart_options.parse_history_details(csv_text, require_mark=False)
                   if csv_text else {})
        row, staleness = _as_of_row(details, as_of)
        mark = row.get("_mark") if row is not None else None
        if mark is not None:
            if staleness:
                log.info("%s: no Barchart underlying row for %s — using the %dd-stale "
                         "close instead", symbol, as_of.isoformat(), staleness)
            prices[symbol] = mark
        if sleep_s:
            await asyncio.sleep(sleep_s)

    return prices


async def _aenrich(raw: dict, as_of: date, cache_dir: Path | None, session,
                   timeout_ms: float = _TIMEOUT_MS, sleep_s: float = _SLEEP_S) -> dict:
    greeks, sourced, unavailable = await _enrich_greeks(
        session, raw, as_of, cache_dir, timeout_ms, sleep_s)
    prices = await _enrich_underlying(session, raw, as_of, cache_dir, timeout_ms, sleep_s)

    log.info("Barchart greeks enrichment for %s: %d contract(s) sourced, %d unavailable%s",
             as_of.isoformat(), len(sourced), len(unavailable),
             f" ({', '.join(str(c) for c in unavailable)})" if unavailable else "")

    return {**raw, "greeks": greeks, "underlying_prices": prices}


async def _aenrich_new_session(raw: dict, as_of: date, cache_dir: Path | None,
                               timeout_ms: float, sleep_s: float) -> dict:
    """Open a real BarchartSession and run `_aenrich` through it. Not exercised by tests."""
    email = os.getenv("BARCHART_EMAIL", "")
    password = os.getenv("BARCHART_PASSWORD", "")
    if not (email and password):
        raise RuntimeError(
            "BARCHART_EMAIL/BARCHART_PASSWORD not set — cannot fetch Flex-CSV greeks "
            "from Barchart")
    cookies_path = Path(os.getenv("COOKIES_PATH", str(_DEFAULT_COOKIES)))
    headless = os.getenv("SCRAPE_HEADLESS", "true").lower() != "false"
    async with BarchartSession(email, password, cookies_path, headless) as session:
        return await _aenrich(raw, as_of, cache_dir, session, timeout_ms, sleep_s)


def enrich(raw: dict, *, as_of: date, cache_dir: Path | None = None,
           dry_run: bool = False, session=None) -> dict:
    """Barchart-source `greeks` and `underlying_prices` for `raw`'s open book.

    Returns a NEW raw-pull dict (the input is never mutated) with `greeks` and
    `underlying_prices` rebuilt from Barchart settlement data as of `as_of`, one
    entry per conid in `raw["positions"]`. `cache_dir`, when given, caches each
    fetched contract/underlying CSV on disk so a re-run of the same date does not
    re-hit Barchart (see `_fetch_cached`).

    `dry_run=True` performs no network call at all: it logs what would be
    fetched and returns `raw` unchanged. `session`, when given, replaces the real
    `BarchartSession` — an injection point that exists so tests can supply canned
    CSV text with zero network (see the module docstring).

    Calls `rawpull.validate()` before returning either way, so a malformed
    enrichment (e.g. a `DELTA_SOURCE_BARCHART` row with a null delta — should
    never happen given the logic above, but the invariant is cheap to check
    twice) fails loudly here rather than surfacing downstream in risk.py.
    """
    if dry_run:
        contracts = raw.get("contracts") or {}
        open_conids = sorted({int(p["conid"]) for p in raw.get("positions") or []
                              if p.get("conid")})
        symbols = sorted({str(contracts[str(c)]["symbol"]).upper()
                          for c in open_conids
                          if str(c) in contracts and contracts[str(c)].get("symbol")})
        log.info("[dry-run] would fetch Barchart greeks for %d open contract(s) "
                 "and underlying spot for %d symbol(s) as of %s: %s",
                 len(open_conids), len(symbols), as_of.isoformat(), ", ".join(symbols))
        rawpull.validate(raw)
        return raw

    if session is not None:
        result = asyncio.run(_aenrich(raw, as_of, cache_dir, session))
    else:
        result = asyncio.run(
            _aenrich_new_session(raw, as_of, cache_dir, _TIMEOUT_MS, _SLEEP_S))

    rawpull.validate(result)
    return result
