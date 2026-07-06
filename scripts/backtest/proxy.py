"""Proxy-backtest of untested analysis plays → the ``BacktestProxy`` tab.

The real backtest (``python3 -m scripts.backtest``) only produces a result row
for a play whose exact contracts have Barchart history. Many plays never get
tested — the reason is only logged, never persisted. This sibling workflow:

  1. diffs the analysis tab against ``BacktestResults`` to find untested plays,
  2. records WHY each went untested (``skip_reason``), and
  3. proxy-evaluates each via a fallback chain, writing one row per untested
     play to a new ``BacktestProxy`` tab (+ local CSV mirror), reusing the real
     backtest's exit engine so the numbers are comparable.

Fallback chain (interpretable ``proxy_method``):

  1. ``strike_expiry_tweak`` — snap EVERY leg to the nearest listed contract that
     has history (bounded by ``max_strike_steps`` / ``max_expiry_deviation_days``)
     and price via the normal real-first path. Tweaks recorded ``orig → used``.
  2. ``bs_options_hist`` — Black-Scholes the play's ACTUAL legs each day, using a
     nearby cached contract's daily ``Price~`` as the underlying and ``IV/100`` as
     sigma (the ÷100 ``enrich_oi`` convention), via ``_simulate``'s ``iv_fn``.
  3. ``underlying_trend`` — direction-only verdict from ``Price~`` when no usable
     option data exists: map structure → bullish/bearish, compare the underlying
     move over the path. ``exit_reason="direction_only"``; P&L columns blank.
  4. ``unevaluable`` — no options history at all, or the play never built
     (unsupported / no_strike / no_expiry): identity + ``skip_reason`` only.

Contract discovery is cache-first, scrape-fallback: nearby-contract lookup scans
``backtests/option_history_cache/`` first, and when the cache has no usable
neighbor (and ``proxy.probe_barchart`` is on / ``--cache-only`` is off) scrapes
Barchart for bounded nearby candidates so later runs are offline.

This module imports ONLY from the shared subpackage and the non-``core`` package
modules, so it never pulls in ``core.py``'s CLI wiring.
"""
import argparse
import asyncio
import logging
import os
from datetime import date, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from lib import barchart_options, sheets_client
from lib.logger import setup_logging

from .classify import _entry_row_from_history, _nearest_friday
from .config import HISTORY_CACHE
from .helpers import _contract_key, _to_float
from .legs import Leg, format_legs, merge_legs
from .plays import _choose_anchor
from .shared.analysis_io import load_analysis
from .shared.build import classify_and_build
from .shared.history import fetch_option_histories
from .shared.results_io import write_results
from .simulate import _simulate

log = logging.getLogger("backtest")


# ─── Tab schema ─────────────────────────────────────────────────────────────────
# Identity + reason/method, then the SAME result columns as BacktestResults (same
# canonical names, so the two tabs union downstream). ``legs`` = the tweaked/used
# legs; ``legs_original`` = the play's own legs (both in the sheet-safe
# ``TKR:YYYY-MM-DD:STRIKE:C|P ±qty`` form from scripts/backtest/legs.py).
_IDENTITY_COLS = [
    "signal_date", "ticker", "structure", "legs", "legs_original",
    "play", "regime", "market_regime",
]
_REASON_COLS = ["skip_reason", "proxy_method", "proxy_detail"]
_RESULT_COLS = [
    "entry_leg_detail", "contracts", "dte_entry", "iv_entry_pct", "delta",
    "entry_underlying", "entry_option_price", "entry_premium_total", "entry_source",
    "realized_pnl_pct", "realized_pnl_abs", "days_held", "exit_reason",
    "mfe_pct", "mfe_abs", "mfe_day", "mae_pct", "mae_abs", "mae_day",
    "pnl_at_cap_pct", "pct_real_days",
    "daily_price_csv", "daily_source_csv", "daily_pnl_csv",
    "max_loss_per_contract", "pnl_on_risk_pct",
    "created_datetime",
]
_PROXY_KEY_ORDER = _IDENTITY_COLS + _REASON_COLS + _RESULT_COLS

_ENTRY_STALENESS_DAYS = 5  # same near-entry rule the real backtest applies


# ─── Small pure helpers ─────────────────────────────────────────────────────────

def _regime_prefix(regime: str) -> str:
    """Regime label up to (but not including) the first em/en-dash (mirrors
    ``core._regime_prefix`` without importing core)."""
    import re
    return re.split(r"[—–]", regime or "", maxsplit=1)[0].strip()


def _play_prefix(play: str) -> str:
    """Normalized play-text prefix used to disambiguate multiple plays on the same
    ticker/date. Whitespace-collapsed, lower-cased, first 60 chars."""
    return " ".join(str(play or "").split())[:60].lower()


def _identity_key(signal_date, ticker: str, play: str) -> tuple:
    """(date, TICKER, play-prefix) — the row identity shared by the untested join
    and the ``BacktestProxy`` dedup. ``signal_date`` may be a ``date`` or any string
    the analysis-date parser accepts (absorbs the Sheets locale reparse)."""
    from .helpers import _parse_analysis_date
    d = signal_date if isinstance(signal_date, date) else _parse_analysis_date(signal_date)
    return (d, str(ticker or "").strip().upper(), _play_prefix(play))


def _strike_step(strike: float) -> float:
    """A sane strike increment when the grid can't be inferred from the cache."""
    if strike < 25:
        return 0.5
    if strike < 100:
        return 1.0
    if strike < 250:
        return 2.5
    if strike < 1000:
        return 5.0
    return 10.0


def _infer_strike_step(strikes: list[float]) -> float | None:
    """Smallest positive gap between distinct cached strikes — the ticker's grid."""
    uniq = sorted({round(s, 4) for s in strikes})
    gaps = [round(b - a, 4) for a, b in zip(uniq, uniq[1:]) if b - a > 1e-9]
    return min(gaps) if gaps else None


# ─── Cache pool + per-contract history ──────────────────────────────────────────

_details_cache: dict[str, dict] = {}


def _load_details(path: Path) -> dict:
    """``{date: row}`` for one cached contract CSV (row carries a ``_mark`` key),
    memoized by path so repeated neighbor probing is cheap."""
    key = str(path)
    if key not in _details_cache:
        try:
            _details_cache[key] = barchart_options.parse_history_details(
                path.read_text(encoding="utf-8"))
        except OSError:
            _details_cache[key] = {}
    return _details_cache[key]


def _cache_contracts(ticker: str) -> list[dict]:
    """Glob the history cache for a ticker → pool of
    ``{strike, expiration(date), opt_type, path}`` dicts."""
    pool: list[dict] = []
    for p in HISTORY_CACHE.glob(f"{ticker.upper()}_*.csv"):
        parts = p.stem.split("_")
        if len(parts) != 3 or parts[0] != ticker.upper():
            continue
        exp_raw, strike_raw = parts[1], parts[2]
        cp = strike_raw[-1:].upper()
        if cp not in ("C", "P"):
            continue
        try:
            exp = datetime.strptime(exp_raw, "%Y%m%d").date()
            strike = float(strike_raw[:-1])
        except ValueError:
            continue
        pool.append({"strike": strike, "expiration": exp,
                     "opt_type": "Call" if cp == "C" else "Put", "path": p})
    return pool


def _covering_entry_row(cand: dict, signal_date: date, K: float, exp: date):
    """The synthetic entry_row a cached contract yields at the signal window, or
    ``None`` when its history doesn't reach ``signal_date`` (≤5d stale). ``K``/``exp``
    are the TARGET leg's — so a donor's IV/Price~/Delta are read against the leg's
    own strike/DTE."""
    details = _load_details(cand["path"])
    if not details:
        return None
    key = _contract_key(cand["path"].stem.split("_")[0], cand["opt_type"], K, exp.isoformat())
    return _entry_row_from_history({key: details}, key, signal_date, K, exp)


def _mark_series(details: dict) -> list[tuple[date, float]]:
    return sorted((d, row["_mark"]) for d, row in details.items() if row.get("_mark") is not None)


def _field_series(details: dict, field: str) -> list[tuple[date, float]]:
    out = []
    for d, row in details.items():
        v = _to_float(row.get(field))
        if v is not None:
            out.append((d, v))
    out.sort()
    return out


def _asof(series: list[tuple[date, float]], day: date):
    """Carry-forward as-of lookup (most recent on/before ``day``), falling back to
    the earliest value so an entry on the signal date is always priced."""
    if not series:
        return None
    best = None
    for d, v in series:
        if d > day:
            break
        best = v
    return best if best is not None else series[0][1]


# ─── Neighbor / donor discovery ─────────────────────────────────────────────────

def _rank_candidates(pool: list[dict], leg: Leg, cfg: dict, step: float,
                     require_exp: date | None = None):
    """Same-type pool contracts within the strike/expiry bounds, ordered by
    (strike steps, expiry days) from the leg's own strike/expiry. ``require_exp``
    pins the expiration exactly — used to keep same-expiration structures on one
    snapped expiry."""
    max_steps = cfg.get("max_strike_steps", 6)
    max_days = cfg.get("max_expiry_deviation_days", 14)
    ranked = []
    for cand in pool:
        if cand["opt_type"] != leg.opt_type:
            continue
        if require_exp is not None and cand["expiration"] != require_exp:
            continue
        steps = round(abs(cand["strike"] - leg.strike) / step) if step else 0
        days = abs((cand["expiration"] - leg.expiration).days)
        if steps > max_steps or days > max_days:
            continue
        ranked.append((steps, days, cand))
    ranked.sort(key=lambda t: (t[0], t[1]))
    return ranked


def _probe_pool(leg: Leg, signal_date: date, cfg: dict, sim_cfg: dict,
                step: float) -> list[dict]:
    """Scrape Barchart for bounded nearby candidates around a leg (nearest strikes
    outward + nearest Friday expiries within bounds) via the shared fetch path, so
    the CSVs land in HISTORY_CACHE; returns the refreshed pool. A no-op returning
    the current pool when credentials are missing (fetch_option_histories warns)."""
    max_steps = cfg.get("max_strike_steps", 6)
    max_days = cfg.get("max_expiry_deviation_days", 14)
    strikes = {round(leg.strike + i * step, 2) for i in range(-max_steps, max_steps + 1)
               if leg.strike + i * step > 0}
    # Nearest listed-style expiries: the leg's own date + neighboring Fridays.
    exps = {leg.expiration}
    for delta in (-14, -7, 0, 7, 14):
        f = _nearest_friday(leg.expiration.fromordinal(leg.expiration.toordinal() + delta))
        if abs((f - leg.expiration).days) <= max_days and f > signal_date:
            exps.add(f)

    contracts, needed = [], {}
    for exp in sorted(exps):
        for K in sorted(strikes):
            key = _contract_key(leg.ticker, leg.opt_type, K, exp.isoformat())
            cache = barchart_options.cache_path(HISTORY_CACHE, leg.ticker, exp, K, leg.opt_type)
            if cache.exists():
                continue
            contracts.append({"key": key, "symbol": leg.ticker, "opt_type": leg.opt_type,
                              "strike": K, "expiration": exp})
            needed[key] = signal_date
    contracts = contracts[:36]  # bound the scrape volume per leg
    if not contracts:
        return _cache_contracts(leg.ticker)

    headless = os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
    timeout_ms = int(sim_cfg.get("history_timeout_ms", 15000))
    log.info("Probing Barchart for %d nearby contract(s) around %s",
             len(contracts), format_legs([leg]))
    try:
        asyncio.run(fetch_option_histories(contracts, headless, timeout_ms, needed,
                                           cache_only=False))
    except Exception:
        log.exception("Barchart probe failed for %s", leg.ticker)
    _details_cache.clear()  # freshly-scraped files must be re-read
    return _cache_contracts(leg.ticker)


def _snap_leg(leg: Leg, pool: list[dict], signal_date: date, cfg: dict,
              sim_cfg: dict, step: float, allow_probe: bool,
              require_exp: date | None = None):
    """Nearest same-type listed contract (with history covering the signal window)
    to ``leg``. Consults the cache pool first, then probes Barchart. Returns
    ``(new_leg, "orig → used", details, pool)`` or ``(None, None, None, pool)``.
    ``require_exp`` restricts candidates to one expiration (see _rank_candidates)."""
    def _best(p):
        for _steps, _days, cand in _rank_candidates(p, leg, cfg, step, require_exp):
            details = _load_details(cand["path"])
            if not details:
                continue
            key = _contract_key(leg.ticker, leg.opt_type, cand["strike"], cand["expiration"].isoformat())
            if _entry_row_from_history({key: details}, key, signal_date,
                                       cand["strike"], cand["expiration"]) is not None:
                return cand, details
        return None, None

    cand, details = _best(pool)
    if cand is None and allow_probe:
        pool = _probe_pool(leg, signal_date, cfg, sim_cfg, step)
        cand, details = _best(pool)
    if cand is None:
        return None, None, None, pool
    new_leg = leg._replace(strike=round(cand["strike"], 4), expiration=cand["expiration"])
    tweak = "" if (new_leg.strike == leg.strike and new_leg.expiration == leg.expiration) \
        else f"{format_legs([leg])} → {format_legs([new_leg])}"
    return new_leg, tweak, details, pool


def _rank_donors(pool: list[dict], anchor_leg: Leg, step: float):
    """All pool contracts ranked as ``Price~``/``IV`` donors — UNBOUNDED (a donor only
    supplies the strike-independent underlying path plus an IV proxy, so a far strike
    is still valid). Prefers the anchor's option type, then nearest strike, then
    nearest expiry."""
    ranked = []
    for cand in pool:
        mismatch = 0 if cand["opt_type"] == anchor_leg.opt_type else 1
        steps = round(abs(cand["strike"] - anchor_leg.strike) / step) if step else 0
        days = abs((cand["expiration"] - anchor_leg.expiration).days)
        ranked.append((mismatch, steps, days, cand))
    ranked.sort(key=lambda t: (t[0], t[1], t[2]))
    return ranked


def _best_donor(anchor_leg: Leg, pool: list[dict], signal_date: date, cfg: dict,
                sim_cfg: dict, step: float, allow_probe: bool):
    """A cached contract that supplies a daily ``Price~``/``IV`` series for the BS /
    trend methods. Prefers the anchor leg's option type + nearest strike/expiry, but
    unbounded (see :func:`_rank_donors`). Returns ``(cand, details, pool)`` or
    ``(None, None, pool)``."""
    def _best(p):
        for _mismatch, _steps, _days, cand in _rank_donors(p, anchor_leg, step):
            details = _load_details(cand["path"])
            if not details:
                continue
            if _covering_entry_row(cand, signal_date, anchor_leg.strike, anchor_leg.expiration) is not None:
                return cand, details
        return None, None

    cand, details = _best(pool)
    if cand is None and allow_probe:
        pool = _probe_pool(anchor_leg, signal_date, cfg, sim_cfg, step)
        cand, details = _best(pool)
    return cand, details, pool


# ─── Skip-reason classification ─────────────────────────────────────────────────

def _anchor_contract(play):
    """The play's anchor contract ``(ticker, opt_type, strike, exp)`` for cache
    inspection — the declared anchor, else the first leg, else the first
    registered contract (iron condors, whose legs are deferred)."""
    if play.anchor:
        return play.anchor
    if play.legs:
        L = play.legs[0]
        return (L.ticker, L.opt_type, L.strike, L.expiration)
    if play.contracts:
        return play.contracts[0]
    return None


def _skip_reason(play, reason) -> str:
    """Why this play went untested in the real backtest. ``unsupported`` /
    ``no_strike`` / ``no_expiry`` when the play never built; otherwise inspect the
    anchor's cache file: ``no_history`` (no file, or data doesn't reach the signal
    window) vs ``unpriced`` (data present at signal but the real sim skipped it)."""
    if reason is not None:
        return reason[0]
    ac = _anchor_contract(play)
    if ac is None:
        return "no_history"
    ticker, ot, K, exp = ac
    path = barchart_options.cache_path(HISTORY_CACHE, ticker, exp, K, ot)
    if not path.exists():
        return "no_history"
    details = _load_details(path)
    key = _contract_key(ticker, ot, K, exp.isoformat())
    row = _entry_row_from_history({key: details}, key, play.c["signal_date"], K, exp)
    return "unpriced" if row is not None else "no_history"


# ─── The three proxy methods ────────────────────────────────────────────────────
# Each returns ``(method_name, detail, result_dict, used_legs_str)`` or ``None`` to
# fall through. ``result_dict`` holds the _RESULT_COLS a play produced.

_BULLISH = {"long_call", "bull_call_spread", "bull_put_spread", "short_put"}
_BEARISH = {"long_put", "bear_put_spread", "bear_call_spread", "short_call"}


def _method1(play, c, cfg, sim_cfg, spread_pct, pool, step, allow_probe):
    """Strike/expiry tweak: snap EVERY leg to a listed contract with history, then
    price via the normal real-first path (production exit_sources).

    Legs sharing an original expiration must land on ONE snapped expiration —
    the first leg of each expiry group snaps freely and pins the rest — so a
    vertical can't silently become a diagonal. Calendars/diagonals (distinct
    original expiries) keep their groups independent. A leg that can't snap under
    the pin fails the method (→ fall through to BS on the actual legs)."""
    if not play.legs:
        return None, pool
    snapped, tweaks, details_map, series_map = [], [], {}, {}
    group_exp: dict[date, date] = {}  # original expiration → snapped expiration
    for leg in play.legs:
        new_leg, tweak, details, pool = _snap_leg(
            leg, pool, c["signal_date"], cfg, sim_cfg, step, allow_probe,
            require_exp=group_exp.get(leg.expiration))
        if new_leg is None:
            return None, pool
        group_exp.setdefault(leg.expiration, new_leg.expiration)
        snapped.append(new_leg)
        if tweak:
            tweaks.append(tweak)
        key = _contract_key(new_leg.ticker, new_leg.opt_type, new_leg.strike,
                            new_leg.expiration.isoformat())
        details_map[key] = details
        series_map[key] = _mark_series(details)
    snapped = merge_legs(snapped)
    if not snapped:
        return None, pool
    anchor_idx, entry_row = _choose_anchor(snapped, details_map, c["signal_date"],
                                           timing=sim_cfg.get("entry_timing", "next_open"))
    if entry_row is None:
        return None, pool
    result = _simulate(c, snapped, entry_row, {}, series_map, sim_cfg,
                       structure=play.structure, anchor_idx=anchor_idx,
                       barchart_details=details_map)
    if not result:
        return None, pool
    detail = "; ".join(tweaks) if tweaks else "all legs had listed history"
    return ("strike_expiry_tweak", detail, result, format_legs(snapped)), pool


def _method2(play, c, cfg, sim_cfg, spread_pct, pool, step, allow_probe):
    """Black-Scholes the play's ACTUAL legs each day off a nearby donor's daily
    ``Price~`` (underlying) and ``IV/100`` (sigma)."""
    if not play.legs:
        return None, pool
    anchor_leg = play.legs[play.anchor_idx] if play.anchor_idx < len(play.legs) else play.legs[0]
    cand, details, pool = _best_donor(
        anchor_leg, pool, c["signal_date"], cfg, sim_cfg, step, allow_probe)
    if cand is None:
        return None, pool
    entry_row = _covering_entry_row(cand, c["signal_date"], anchor_leg.strike, anchor_leg.expiration)
    if entry_row is None:
        return None, pool

    price_series = _field_series(details, "Price~")
    iv_series = [(d, v / 100) for d, v in _field_series(details, "IV")]
    entry_iv = (_to_float(entry_row.get("IV")) or 0) / 100 or None

    def price_fn(_tk, day):
        return _asof(price_series, day)

    def iv_fn(day):
        return _asof(iv_series, day) or entry_iv

    bs_cfg = {**sim_cfg, "entry_sources": ["bs"], "exit_sources": ["bs"]}
    result = _simulate(c, play.legs, entry_row, {}, {}, bs_cfg,
                       structure=play.structure, anchor_idx=play.anchor_idx,
                       price_fn=price_fn, iv_fn=iv_fn)
    if not result:
        return None, pool
    sigma = _asof(iv_series, c["signal_date"]) or entry_iv or 0
    # BS entry stays at the signal date (entry@signal_eod): the donor series is EOD
    # closes, so there is no "next open" to price — unlike the barchart entry path.
    detail = (f"BS off donor {cand['strike']:g}{'C' if cand['opt_type'] == 'Call' else 'P'} "
              f"exp {cand['expiration'].isoformat()} (entry sigma {sigma:.3f}, entry@signal_eod)")
    return ("bs_options_hist", detail, result, format_legs(play.legs)), pool


def _method3(play, c, cfg, sim_cfg, spread_pct, pool, step, allow_probe):
    """Direction-only verdict from the donor's ``Price~``: underlying move over the
    path vs the structure's bullish/bearish bias. P&L columns blank."""
    if not play.legs:
        return None, pool
    if play.structure in _BULLISH:
        bullish = True
    elif play.structure in _BEARISH:
        bullish = False
    else:
        return None, pool  # neutral (straddle/condor/…) → unevaluable

    anchor_leg = play.legs[play.anchor_idx] if play.anchor_idx < len(play.legs) else play.legs[0]
    cand, details, pool = _best_donor(
        anchor_leg, pool, c["signal_date"], cfg, sim_cfg, step, allow_probe)
    if cand is None:
        return None, pool
    price_series = _field_series(details, "Price~")
    entry_px = _asof(price_series, c["signal_date"])
    if entry_px is None:
        return None, pool

    from datetime import timedelta
    nearest_dte = min((leg.expiration - c["signal_date"]).days for leg in play.legs)
    path_cap = sim_cfg.get("path_cap_days", 120)
    exit_day = c["signal_date"] + timedelta(days=min(nearest_dte, path_cap))
    exit_px = _asof(price_series, exit_day)
    if exit_px is None:
        return None, pool

    correct = (exit_px > entry_px) if bullish else (exit_px < entry_px)
    move = (exit_px - entry_px) / entry_px if entry_px else 0.0
    result = {
        "entry_underlying": round(entry_px, 4),
        "exit_reason": "direction_only",
        "created_datetime": "",  # set by caller
    }
    detail = (f"{'bullish' if bullish else 'bearish'} bias; underlying "
              f"{entry_px:g} → {exit_px:g} ({move:+.1%}); "
              f"direction_correct={correct}")
    return ("underlying_trend", detail, result, format_legs(play.legs)), pool


# ─── Per-play evaluation ────────────────────────────────────────────────────────

def _blank_row() -> dict:
    return {k: "" for k in _PROXY_KEY_ORDER}


def _identity_cols(c: dict, play) -> dict:
    return {
        "signal_date": c["signal_date"].isoformat(),
        "ticker": c["ticker"],
        "structure": play.structure if play is not None else "",
        "legs": "",
        "legs_original": format_legs(play.legs) if (play is not None and play.legs) else "",
        "play": str(c.get("play", ""))[:300],
        "regime": c.get("regime", ""),
        "market_regime": c.get("market_regime", ""),
    }


def _evaluate(play, reason, c, cfg, sim_cfg, spread_pct, created_datetime,
              allow_probe) -> dict:
    """Run the fallback chain for one candidate and return its ``BacktestProxy`` row."""
    row = _blank_row()
    row.update(_identity_cols(c, play))
    row["created_datetime"] = created_datetime

    if play is None:
        row["skip_reason"] = reason[0]
        row["proxy_method"] = "unevaluable"
        row["proxy_detail"] = reason[1]
        return row

    row["skip_reason"] = _skip_reason(play, None)

    pool = _cache_contracts(c["ticker"])
    step = _infer_strike_step([p["strike"] for p in pool]) or _strike_step(
        play.legs[0].strike if play.legs else 100.0)

    for method in (_method1, _method2, _method3):
        outcome, pool = method(play, c, cfg, sim_cfg, spread_pct, pool, step, allow_probe)
        if outcome is None:
            continue
        proxy_method, detail, result, used_legs = outcome
        for k in _RESULT_COLS:
            if k in result and result[k] != "":
                row[k] = result[k]
        row["created_datetime"] = created_datetime  # methods may blank it
        row["legs"] = used_legs
        row["proxy_method"] = proxy_method
        row["proxy_detail"] = detail
        return row

    row["proxy_method"] = "unevaluable"
    row["proxy_detail"] = "no usable options history for any fallback"
    row["legs"] = row["legs_original"]
    return row


# ─── Untested join + idempotency ────────────────────────────────────────────────

def _load_tested_keys(source_tab: str) -> set:
    """Identity keys already present in ``BacktestResults`` (dates normalized on
    both sides so the Sheets locale reparse doesn't cause phantom re-tests)."""
    keys = set()
    for r in sheets_client.get_all_rows(source_tab):
        keys.add(_identity_key(r.get("signal_date", ""), r.get("ticker", ""), r.get("play", "")))
    return keys


def _load_proxy_keys(proxy_tab: str) -> set:
    """Identity keys already in ``BacktestProxy`` — dropped so re-runs append
    nothing. ``get_all_rows`` auto-creates (and returns ``[]`` for) a missing tab."""
    keys = set()
    for r in sheets_client.get_all_rows(proxy_tab):
        keys.add(_identity_key(r.get("signal_date", ""), r.get("ticker", ""), r.get("play", "")))
    return keys


def _find_untested(candidates: list[dict], tested: set) -> list[dict]:
    """Candidates whose identity key is not in the tested set."""
    out = []
    for c in candidates:
        if _identity_key(c["signal_date"], c["ticker"], c.get("play", "")) not in tested:
            out.append(c)
    return out


# ─── Output ─────────────────────────────────────────────────────────────────────

def _print_proxy_summary(rows: list[dict]) -> None:
    dist: dict[str, int] = {}
    for r in rows:
        dist[r.get("proxy_method", "")] = dist.get(r.get("proxy_method", ""), 0) + 1
    print(f"\n{'=' * 64}")
    print(f"PROXY-BACKTEST SUMMARY  ({len(rows)} untested plays)")
    print(f"{'=' * 64}")
    print("  proxy_method: " + ", ".join(f"{k}={v}" for k, v in sorted(dist.items())))
    priced = [r for r in rows if isinstance(r.get("realized_pnl_pct"), (int, float))]
    if priced:
        wins = sum(1 for r in priced if r["realized_pnl_pct"] > 0)
        print(f"  priced (method 1/2): {len(priced)}  |  win rate {wins / len(priced) * 100:.1f}%")


def _write_proxy(rows: list[dict], proxy_cfg: dict, dry_run: bool) -> None:
    write_results(
        rows,
        key_order=_PROXY_KEY_ORDER,
        local_csv=proxy_cfg.get("local_csv"),
        sheet_tab=None if dry_run else proxy_cfg.get("sheet_tab"),
        dry_run=dry_run,
        summary_fn=_print_proxy_summary,
    )


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Proxy-backtest untested analysis plays → BacktestProxy tab.")
    parser.add_argument("--config", default="config/backtest.yml")
    parser.add_argument("--tab", help="Analysis tab to read (overrides config)")
    parser.add_argument("--date", help="Single analysis date YYYY-MM-DD (sets --start/--end)")
    parser.add_argument("--start", help="Earliest analysis date (YYYY-MM-DD)")
    parser.add_argument("--end", help="Latest analysis date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write sheet/CSV")
    parser.add_argument("--cache-only", action="store_true",
                        help="Cache-only contract discovery; never scrape Barchart")
    parser.add_argument("--redo", action="store_true",
                        help="Re-evaluate plays already in BacktestProxy, deleting their "
                             "existing rows first (requires --date or --start/--end)")
    args = parser.parse_args()
    if args.redo and not (args.date or args.start or args.end):
        parser.error("--redo requires --date or --start/--end to bound the re-evaluation")

    cfg_path = Path(__file__).resolve().parent.parent.parent / args.config
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)

    proxy_cfg = cfg.get("proxy", {})
    sim_cfg = cfg["simulation"]
    spread_pct = sim_cfg.get("spread_width_pct", 0.02)
    tab = args.tab or cfg.get("analysis", {}).get("tab", "AnalysisClaude")
    if args.date:
        start = end = date.fromisoformat(args.date)
    else:
        start = date.fromisoformat(args.start) if args.start else None
        end = date.fromisoformat(args.end) if args.end else None
    allow_probe = proxy_cfg.get("probe_barchart", True) and not args.cache_only

    log.info("Loading analysis plays from tab '%s'", tab)
    candidates, market_regime = load_analysis(tab, start, end)
    if not candidates:
        log.warning("No plays found in '%s'", tab)
        return
    for c in candidates:
        c["market_regime"] = _regime_prefix(market_regime.get(c["date"], ""))

    tested = _load_tested_keys(proxy_cfg.get("results_source_tab", "BacktestResults"))
    untested = _find_untested(candidates, tested)
    log.info("%d/%d analysis plays are untested by '%s'",
             len(untested), len(candidates), proxy_cfg.get("results_source_tab"))

    proxy_tab = proxy_cfg.get("sheet_tab", "BacktestProxy")
    existing = _load_proxy_keys(proxy_tab)
    if args.redo:
        redo_keys = {k for k in (_identity_key(c["signal_date"], c["ticker"], c.get("play", ""))
                                 for c in untested) if k in existing}
        log.info("--redo: %d play(s) already in '%s' will be re-evaluated and replaced",
                 len(redo_keys), proxy_tab)
    else:
        redo_keys = set()
        untested = [c for c in untested
                    if _identity_key(c["signal_date"], c["ticker"], c.get("play", "")) not in existing]
        log.info("%d untested plays remain after dropping ones already in '%s'",
                 len(untested), proxy_tab)

    created = datetime.now().isoformat(timespec="seconds")
    # NB: pass the proxy: sub-config — the snap bounds (max_strike_steps /
    # max_expiry_deviation_days) are read off this dict, not the full cfg.
    rows = [_evaluate(*classify_and_build(c, spread_pct, None), c, proxy_cfg, sim_cfg,
                      spread_pct, created, allow_probe)
            for c in untested]

    if redo_keys and not args.dry_run:
        sheets_client.delete_rows_where(
            proxy_tab,
            lambda r: _identity_key(r.get("signal_date", ""), r.get("ticker", ""),
                                    r.get("play", "")) in redo_keys)

    _write_proxy(rows, proxy_cfg, args.dry_run)


if __name__ == "__main__":
    main()
