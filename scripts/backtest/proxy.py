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
  2. ``underlying_trend`` — direction-only verdict from ``Price~`` when no usable
     option data exists: map structure → bullish/bearish, compare the underlying
     move over the path. ``exit_reason="direction_only"``; P&L columns blank.
  3. ``unevaluable`` — no options history at all, or the play never built
     (unsupported / no_strike / no_expiry): identity + ``skip_reason`` only.

There is no model-priced tier. ``bs_options_hist`` (Black-Scholes the play's
actual legs off a donor's ``Price~``/``IV``) sat between the two: switched off
behind ``proxy.bs_fallback`` on 2026-08-11 (its marks were tail-compressed and
never calibratable, so pooling them attenuated every effect), and DELETED on
2026-09-23 when the operator abolished model prices from the backtest. A config
that still sets ``proxy.bs_fallback: true`` is refused. Legacy ``bs_options_hist``
rows remain in frozen exports; studies drop them at read time (``lib/book.py``).

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

from lib import sheets_client
from lib.barchart import options as barchart_options
from lib.logger import setup_logging

from .classify import _entry_row_from_history, _nearest_friday
from .config import HISTORY_CACHE
from .helpers import _contract_key, _to_float
from .legs import Leg, format_legs, merge_legs
from .plays import _choose_anchor
from .shared.analysis_io import load_analysis, load_analysis_csv
from .shared.build import classify_and_build
from .shared.history import fetch_option_histories
from .shared.identity import (
    find_untested as _find_untested,
    identity_key as _identity_key,
    keys_from_csv as _keys_from_csv,
    keys_from_tab,
)
from .shared.results_io import write_results
from .simulate import _simulate, validate_pricing_config

log = logging.getLogger("backtest")


# ─── Tab schema ─────────────────────────────────────────────────────────────────
# Identity + reason/method, then the SAME result columns as BacktestResults (same
# canonical names, so the two tabs union downstream). ``legs`` = the tweaked/used
# legs; ``legs_original`` = the play's own legs (both in the sheet-safe
# ``TKR:YYYY-MM-DD:STRIKE:C|P ±qty`` form from scripts/backtest/legs.py).
_IDENTITY_COLS = [
    "signal_date", "ticker", "structure", "legs", "legs_original",
    # `horizon` mirrors the analysis row's dedicated column, kept beside `play`.
    "play", "horizon", "regime", "market_regime",
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
# Model evidence-quality score, carried straight off the analysis row (like
# regime/play — NOT produced by simulation). Trailing group so the column order
# mirrors BacktestResults' end-appended score block.
_SCORE_COLS = [
    "score_total", "score_flow", "score_dealer", "score_price", "score_vol",
    "score_catalyst",
]
# Exit profile each proxy row was simulated on — same values and same
# empty-means-pre-2026-07-22 convention as BacktestResults. Proxy rows run the
# SAME simulation:/credit:/regime_exit: rules, so the two tabs stay comparable.
_BASIS_COLS = ["exit_basis"]
# Quote-staleness + transaction-cost columns (robustness review B3/B1, 2026-09-07).
# `_simulate` stamps all three on every proxy row too, so the two tabs stay
# comparable; appended at the VERY END for the same positional-append reason, and
# the BacktestProxy tab header must gain them in this order. `cost_basis` empty =
# costs are off and the realized columns are GROSS. See docs/backtest-reference.md.
_COST_COLS = ["pct_stale_days", "cost_total", "cost_basis"]
# How the realized exit was filled — same values and same empty-means-pre-2026-09-19
# convention as BacktestResults. Proxy rows run the SAME simulation, so the two tabs
# stay comparable; appended at the VERY END for the positional-append reason above.
_FILL_COLS = ["exit_fill"]
# Whether the simulated path outlived the price data (2026-09-23) — same values
# and same empty-means-written-earlier convention as BacktestResults. Proxy rows
# run the SAME simulation and are MORE exposed to it: a proxy expiry past the
# last scrape is the normal case, so every one of the 30 plays evaluated locally
# on the June–July 2026 backfill sat past its data end. Appended at the VERY END
# for the positional-append reason above.
_PATH_COLS = ["path_status", "path_data_end"]
_PROXY_KEY_ORDER = (_IDENTITY_COLS + _REASON_COLS + _RESULT_COLS + _SCORE_COLS
                    + _BASIS_COLS + _COST_COLS + _FILL_COLS + _PATH_COLS)

_ENTRY_STALENESS_DAYS = 5  # same near-entry rule the real backtest applies


# ─── Small pure helpers ─────────────────────────────────────────────────────────

def _regime_prefix(regime: str) -> str:
    """Regime label up to (but not including) the first em/en-dash (mirrors
    ``core._regime_prefix`` without importing core)."""
    import re
    return re.split(r"[—–]", regime or "", maxsplit=1)[0].strip()


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
    """A cached contract that supplies a daily ``Price~`` series for the trend
    method. Prefers the anchor leg's option type + nearest strike/expiry, but
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

#: `skip_reason` for a play whose named anchor had no history when the chain
#: began, but which the strike/expiry snap (method 1) then priced from REAL
#: history — the named contract once the probe fetched it, or a listed neighbour
#: (`proxy_detail` shows `orig → used` when a leg moved). Replaces the pre-chain
#: `no_history`, which on such a row read as a failure (2026-09-24).
SNAP_PRICED = "snap_priced"

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
    window) vs ``unpriced`` (data present at signal but the real sim skipped it).

    This is the PRE-CHAIN reason. When method 1 then prices a ``no_history``
    play from real history, :func:`_evaluate` replaces it with ``SNAP_PRICED``,
    so a ``no_history`` on a written row means the chain found nothing to price
    real either.

    A priced tier may REFUSE the play afterwards for a more specific reason —
    one of ``simulate.ENTRY_REFUSALS`` — and :func:`_note_refusal` then overwrites what
    this returns. This function only ever sees the cache, so it cannot know that.
    """
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
    the pin fails the method (→ fall through to the direction-only verdict)."""
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
                       barchart_details=details_map, refusal=play.refusal)
    if not result:
        return None, pool
    detail = "; ".join(tweaks) if tweaks else "all legs had listed history"
    return ("strike_expiry_tweak", detail, result, format_legs(snapped)), pool


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
        # No exit rules run on this tier at all (direction verdict only), so it
        # is neither PROD- nor regime-basis. Named explicitly rather than left
        # blank — blank is reserved for pre-2026-07-22 rows.
        "exit_basis": "NONE",
    }
    detail = (f"{'bullish' if bullish else 'bearish'} bias; underlying "
              f"{entry_px:g} → {exit_px:g} ({move:+.1%}); "
              f"direction_correct={correct}")
    return ("underlying_trend", detail, result, format_legs(play.legs)), pool


# ─── Per-play evaluation ────────────────────────────────────────────────────────

def validate_proxy_config(proxy_cfg: dict) -> None:
    """Raise ``ValueError`` when the proxy config asks for the deleted
    Black-Scholes tier (`bs_fallback: true`, abolished 2026-09-23)."""
    if (proxy_cfg or {}).get("bs_fallback"):
        raise ValueError(
            "proxy.bs_fallback is set: the Black-Scholes tier (bs_options_hist) was "
            "deleted on 2026-09-23 — no model prices in the backtest. Remove the key.")


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
        "horizon": c.get("horizon", ""),
        "regime": c.get("regime", ""),
        "market_regime": c.get("market_regime", ""),
        # Analysis-row score context — carried onto every proxy row (incl.
        # unevaluable), sourced from the candidate like regime/play.
        **{k: c.get(k, "") for k in _SCORE_COLS},
    }


def _note_refusal(row: dict, play) -> dict:
    """Stamp a priced-tier REFUSAL onto the finished proxy row.

    `skip_reason` answers "why did the real backtest never test this play?". When
    a proxy method priced the entry and then refused it — one of
    `simulate.ENTRY_REFUSALS`: a leg with no real entry price, a polarity-fixed
    structure priced to the wrong side, or legs quoted against strike order —
    that refusal IS the answer, and it is more specific than the cache-derived
    `unpriced` this row started with, so it replaces it. The reason is also
    appended to `proxy_detail`, because the row can still carry a direction-only
    verdict from method 3 and the reader must see which tier refused and why.

    A play whose priced tiers all succeeded leaves `play.refusal` empty and the
    row untouched.
    """
    reason = play.refusal.get("reason") if play is not None else None
    if not reason:
        return row
    row["skip_reason"] = reason
    detail = play.refusal.get("detail", "")
    row["proxy_detail"] = f"{row['proxy_detail']} | {reason}: {detail}".strip(" |")
    return row


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
    play.refusal = {}

    pool = _cache_contracts(c["ticker"])
    step = _infer_strike_step([p["strike"] for p in pool]) or _strike_step(
        play.legs[0].strike if play.legs else 100.0)

    # No model-priced tier (module docstring): directional plays that cannot be
    # tweak-priced fall to method 3's direction-only verdict, neutral ones to
    # `unevaluable`.
    validate_proxy_config(cfg)
    for method in (_method1, _method3):
        outcome, pool = method(play, c, cfg, sim_cfg, spread_pct, pool, step, allow_probe)
        if outcome is None:
            continue
        proxy_method, detail, result, used_legs = outcome
        # _BASIS_COLS as well as _RESULT_COLS: `exit_basis` is declared in
        # _PROXY_KEY_ORDER and set by every method (_simulate stamps it on the
        # priced tiers; _method3 sets "NONE"), but it lived outside this copy
        # loop until 2026-09-02, so it never reached the row. The whole proxy
        # tab was blank in that column, in every era — a study stratifying by
        # exit profile would have silently read the proxy book as one basis.
        # _COST_COLS joined the loop 2026-09-19 for exactly the same reason:
        # declared in _PROXY_KEY_ORDER and stamped by _simulate on the priced
        # tiers, but left out of the copy, so all 1,665 proxy rows were blank in
        # `pct_stale_days` and `cost_total` while BacktestResults carried them.
        # `cost_basis` still writes empty while both cost knobs are 0 — that is
        # the same convention BacktestResults uses, not another gap.
        for k in _RESULT_COLS + _BASIS_COLS + _COST_COLS + _FILL_COLS + _PATH_COLS:
            if k in result and result[k] != "":
                row[k] = result[k]
        row["created_datetime"] = created_datetime  # methods may blank it
        row["legs"] = used_legs
        row["proxy_method"] = proxy_method
        row["proxy_detail"] = detail
        # The pre-chain `no_history` described the named anchor only; method 1
        # just priced the play from real history, so it is not a failure.
        if row["skip_reason"] == "no_history" and proxy_method == "strike_expiry_tweak":
            row["skip_reason"] = SNAP_PRICED
        return _note_refusal(row, play)

    row["proxy_method"] = "unevaluable"
    row["proxy_detail"] = "no usable options history for any fallback"
    row["legs"] = row["legs_original"]
    return _note_refusal(row, play)


# ─── Untested join + idempotency ────────────────────────────────────────────────

# The key itself, the tab/CSV readers and the join all live in
# `shared/identity.py` — see its docstring for why there is exactly one copy.
# These two names stay distinct because they read DIFFERENT tabs for DIFFERENT
# reasons: `BacktestResults` is this module's INPUT filter ("which plays did the
# real backtest never test?") and `BacktestProxy` is its own destination
# ("which of those have I already written?"). Collapsing them into one call
# would lose that distinction at every call site.

def _load_tested_keys(source_tab: str) -> set:
    """Identity keys already present in ``BacktestResults`` (dates normalized on
    both sides so the Sheets locale reparse doesn't cause phantom re-tests)."""
    return keys_from_tab(source_tab)


def _load_proxy_keys(proxy_tab: str) -> set:
    """Identity keys already in ``BacktestProxy`` — dropped so re-runs append
    nothing."""
    return keys_from_tab(proxy_tab)


def _in_bound(key: tuple, start: date | None, end: date | None) -> bool:
    """True when an identity key's date lies inside ``[start, end]`` (either end
    open when None). A key whose date did not parse is never in bound — a row we
    cannot date is never deleted on a date-bounded run."""
    d = key[0]
    if not isinstance(d, date):
        return False
    return (start is None or d >= start) and (end is None or d <= end)


def _cross_tab_duplicates(existing: set, tested: set,
                          start: date | None, end: date | None) -> set:
    """Proxy identity keys, inside the run's date bound, that are ALSO on the
    results tab.

    A play belongs on ONE tab. It reaches both when ``scripts.backtest --redo``
    re-prices a date and can now price a play the proxy had to stand in for
    (the history cache grew in between): the proxy's next run skips the play as
    tested, but its old proxy row is still there. ``--redo`` deletes these rows;
    a plain run only warns, because a plain run never deletes.
    """
    return {k for k in existing if k in tested and _in_bound(k, start, end)}


def _log_cross_tab(keys: set, proxy_tab: str, tested_source: str, verb: str) -> None:
    for d, ticker, prefix in sorted(keys, key=lambda k: (str(k[0]), k[1], k[2])):
        log.warning("%s '%s' row also on '%s': %s %s %r",
                    verb, proxy_tab, tested_source, d, ticker, prefix)


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
        print(f"  priced: {len(priced)}  |  win rate {wins / len(priced) * 100:.1f}%")


def _write_proxy(rows: list[dict], proxy_cfg: dict, dry_run: bool,
                 before_sheet=None) -> None:
    write_results(
        rows,
        key_order=_PROXY_KEY_ORDER,
        local_csv=proxy_cfg.get("local_csv"),
        sheet_tab=None if dry_run else proxy_cfg.get("sheet_tab"),
        dry_run=dry_run,
        summary_fn=_print_proxy_summary,
        before_sheet=before_sheet,
    )


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Proxy-backtest untested analysis plays → BacktestProxy tab.")
    parser.add_argument("--config", default="config/backtest.yml")
    parser.add_argument("--tab", help="Analysis tab to read (overrides config)")
    parser.add_argument("--analysis-csv",
                        help="Local analysis rows CSV to read instead of a Sheets tab "
                             "(overrides config analysis.csv, which itself wins over analysis.tab)")
    parser.add_argument("--date", help="Single analysis date YYYY-MM-DD (sets --start/--end)")
    parser.add_argument("--start", help="Earliest analysis date (YYYY-MM-DD)")
    parser.add_argument("--end", help="Latest analysis date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write sheet/CSV")
    parser.add_argument("--cache-only", action="store_true",
                        help="Cache-only contract discovery; never scrape Barchart")
    parser.add_argument("--redo", action="store_true",
                        help="Re-evaluate plays already in BacktestProxy, deleting their "
                             "existing rows first, and delete proxy rows whose play is now "
                             "on BacktestResults (requires --date or --start/--end)")
    args = parser.parse_args()
    if args.redo and not (args.date or args.start or args.end):
        parser.error("--redo requires --date or --start/--end to bound the re-evaluation")

    cfg_path = Path(__file__).resolve().parent.parent.parent / args.config
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)

    proxy_cfg = cfg.get("proxy", {})
    sim_cfg = cfg["simulation"]
    # Refused BEFORE any fetch or Sheets read: a config asking for a model price
    # must fail loudly, not after an hour of scraping.
    validate_proxy_config(proxy_cfg)
    validate_pricing_config(sim_cfg)
    spread_pct = sim_cfg.get("spread_width_pct", 0.02)
    analysis_cfg = cfg.get("analysis", {}) or {}
    tab = args.tab or analysis_cfg.get("tab", "AnalysisClaude")
    # A local CSV analysis source WINS over the tab (see scripts/backtest/core.py).
    analysis_csv = args.analysis_csv or analysis_cfg.get("csv")
    if args.date:
        start = end = date.fromisoformat(args.date)
    else:
        start = date.fromisoformat(args.start) if args.start else None
        end = date.fromisoformat(args.end) if args.end else None
    allow_probe = proxy_cfg.get("probe_barchart", True) and not args.cache_only

    if analysis_csv:
        log.info("analysis source: csv %s", analysis_csv)
        candidates, market_regime = load_analysis_csv(analysis_csv, start, end)
        source = str(analysis_csv)
    else:
        log.info("analysis source: tab %s", tab)
        candidates, market_regime = load_analysis(tab, start, end)
        source = tab
    if not candidates:
        log.warning("No plays found in '%s'", source)
        return
    for c in candidates:
        c["market_regime"] = _regime_prefix(market_regime.get(c["date"], ""))

    # "Already tested" set: a local results CSV when one is configured, else the
    # Sheets tab. results_source_csv wins so a local-only run never reads Sheets.
    results_source_csv = proxy_cfg.get("results_source_csv")
    if results_source_csv:
        tested = _keys_from_csv(results_source_csv)
        tested_source = str(results_source_csv)
    else:
        tested_source = proxy_cfg.get("results_source_tab", "BacktestResults")
        tested = _load_tested_keys(tested_source)
    untested = _find_untested(candidates, tested)
    log.info("%d/%d analysis plays are untested by '%s'",
             len(untested), len(candidates), tested_source)

    # `sheet_tab: null` = local-only mode: the idempotency set comes from the
    # local proxy CSV (absent on the first run) instead of the BacktestProxy tab.
    proxy_tab = proxy_cfg.get("sheet_tab", "BacktestProxy")
    if proxy_tab:
        existing = _load_proxy_keys(proxy_tab)
    else:
        existing = _keys_from_csv(proxy_cfg.get("local_csv") or "backtests/proxy_results.csv")
    # A proxy row whose play is now on the results tab is a cross-tab duplicate
    # (see _cross_tab_duplicates). --redo deletes it from the proxy TAB; a plain
    # run, a dry run and a local-only run (no sheet_tab) only report it.
    cross_tab = _cross_tab_duplicates(existing, tested, start, end)
    stale_keys: set = set()
    if args.redo:
        redo_keys = {k for k in (_identity_key(c["signal_date"], c["ticker"], c.get("play", ""))
                                 for c in untested) if k in existing}
        log.info("--redo: %d play(s) already in '%s' will be re-evaluated and replaced",
                 len(redo_keys), proxy_tab)
        if cross_tab and proxy_tab:
            stale_keys = cross_tab
            log.warning("--redo: %d '%s' row(s) are now priced on '%s' and will be deleted",
                        len(cross_tab), proxy_tab, tested_source)
            _log_cross_tab(cross_tab, proxy_tab, tested_source,
                           "Would delete (dry run)" if args.dry_run else "Deleting")
        elif cross_tab:
            log.warning("--redo: %d local proxy row(s) are ALSO in '%s'; local-only mode "
                        "(sheet_tab: null) deletes nothing", len(cross_tab), tested_source)
            _log_cross_tab(cross_tab, "local proxy CSV", tested_source, "Duplicate")
    else:
        redo_keys = set()
        if cross_tab:
            log.warning("%d '%s' row(s) in this date range are ALSO on '%s' — a play "
                        "belongs on one tab; re-run with --redo to delete the proxy copies",
                        len(cross_tab), proxy_tab, tested_source)
            _log_cross_tab(cross_tab, proxy_tab, tested_source, "Duplicate")
        untested = [c for c in untested
                    if _identity_key(c["signal_date"], c["ticker"], c.get("play", "")) not in existing]
        log.info("%d untested plays remain after dropping ones already in '%s'",
                 len(untested), proxy_tab)

    created = datetime.now().isoformat(timespec="seconds")
    structure_veto = (cfg.get("entry") or {}).get("structure_veto") or ()
    # NB: pass the proxy: sub-config — the snap bounds (max_strike_steps /
    # max_expiry_deviation_days) are read off this dict, not the full cfg.
    rows = [_evaluate(*classify_and_build(c, spread_pct, None, structure_veto), c, proxy_cfg,
                      sim_cfg, spread_pct, created, allow_probe)
            for c in untested]

    # One Sheets pass deletes both the rows being replaced and the cross-tab
    # duplicates. Both sets are empty on a plain run.
    # Runs after the local CSV is written and before the append (see
    # results_io.write_results), so a Sheets failure never loses the run.
    doomed = redo_keys | stale_keys
    delete_old = None
    if doomed and proxy_tab and not args.dry_run:
        def delete_old():
            n = sheets_client.delete_rows_where(
                proxy_tab,
                lambda r: _identity_key(r.get("signal_date", ""), r.get("ticker", ""),
                                        r.get("play", "")) in doomed)
            log.info("--redo: deleted %d row(s) from '%s' (%d to replace, %d now on '%s')",
                     n, proxy_tab, len(redo_keys), len(stale_keys), tested_source)

    _write_proxy(rows, proxy_cfg, args.dry_run, before_sheet=delete_old)


if __name__ == "__main__":
    main()
