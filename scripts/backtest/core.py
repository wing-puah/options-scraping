import argparse
import asyncio
import csv
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from lib.logger import setup_logging
from lib import sheets_client
from lib import barchart_options
from lib.barchart import BarchartSession

from .config import RESULTS_PATH, HISTORY_CACHE
from .helpers import _parse_analysis_date, _contract_key, _num
from .classify import classify_play, _identify_contract, _entry_row_from_history
from .legs import legs_from_structure, iron_condor_legs, merge_legs
from .simulate import _simulate, _iron_condor_strikes

log = logging.getLogger("backtest")

_KEY_ORDER = [
    "signal_date", "ticker", "structure", "legs", "entry_leg_detail", "contracts",
    "dte_entry", "iv_entry_pct", "delta", "entry_underlying",
    "entry_option_price", "entry_premium_total", "entry_source",
    "market_regime", "regime", "play",
    "realized_pnl_pct", "realized_pnl_abs", "days_held", "exit_reason",
    "mfe_pct", "mfe_abs", "mfe_day", "mae_pct", "mae_abs", "mae_day", "pnl_at_cap_pct", "pct_real_days",
    "daily_price_csv",
    "created_datetime",
    # Per-ticker flow-rollup context joined from audit/<date>-rollup.csv (the same
    # date's scored rollup the analysis ran on). Appended at the END so existing
    # sheet rows stay column-aligned. See _attach_rollup_metrics / _ROLLUP_METRIC_COLS.
    "oi_confirm_pct", "cpir", "iv_spread",
]

ROOT = Path(__file__).resolve().parent.parent.parent
AUDIT_DIR = ROOT / "audit"

# backtest result key -> rollup CSV column (lib/flow_summary FLOW_CSV_COLUMNS).
_ROLLUP_METRIC_COLS = {
    "oi_confirm_pct": "OIConfirmPct",
    "cpir": "CPIR",
    "iv_spread": "IVSpread",
}


def _load_rollup_metrics(date_str: str) -> dict[str, dict]:
    """Read ``audit/<date>-rollup.csv`` → ``{SYMBOL: {oi_confirm_pct, cpir, iv_spread}}``.

    Returns ``{}`` when the rollup file is missing (older backtested dates may have
    no audit file). The rollup carries one row per ticker per section (stocks/etfs);
    we key by upper-cased ``Symbol`` (last write wins on the rare cross-section
    overlap)."""
    path = AUDIT_DIR / f"{date_str}-rollup.csv"
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get("Symbol") or "").strip().upper()
            if not sym:
                continue
            out[sym] = {k: (row.get(col) or "").strip()
                        for k, col in _ROLLUP_METRIC_COLS.items()}
    return out


def _attach_rollup_metrics(candidates: list[dict]) -> None:
    """Backfill per-ticker rollup metrics (OIConfirmPct/CPIR/IVSpread) for candidates
    whose analysis row predates these columns.

    Newer analysis rows already carry the metrics (joined at analysis time — see
    analysis_pipeline.core.analysis_to_rows); those are authoritative and left as-is.
    Only candidates with all three blank are filled from that date's
    ``audit/<date>-rollup.csv``. Rollups are read once per date."""
    cache: dict[str, dict] = {}
    backfilled = 0
    for c in candidates:
        if any(c.get(k) for k in _ROLLUP_METRIC_COLS):
            continue  # already on the analysis row — authoritative
        d = c["date"]
        if d not in cache:
            cache[d] = _load_rollup_metrics(d)
        metrics = cache[d].get(c["ticker"].upper(), {})
        if metrics:
            backfilled += 1
        for k in _ROLLUP_METRIC_COLS:
            c[k] = metrics.get(k, "")
    log.info("Backfilled rollup metrics from audit CSV for %d/%d candidates "
             "(rest carried on the analysis row)", backfilled, len(candidates))


def _regime_prefix(regime: str) -> str:
    """Return the regime label up to (but not including) the first em-dash."""
    import re
    return re.split(r"[—–]", regime, maxsplit=1)[0].strip()


def _anchor_idx(legs) -> int:
    """The leg whose real flow Trade seeds entry pricing: first long, else first."""
    for i, leg in enumerate(legs):
        if leg.qty > 0:
            return i
    return 0


def _choose_anchor(legs, barchart_details, signal_date):
    """Pick the anchor leg for an explicit structure and build its entry row.

    The anchor seeds the position's entry IV / underlying / DTE from its Barchart
    history. Legs are tried in priority order — long legs first, then by descending
    |qty| — and the first whose history yields a valid entry row wins, so a play is
    no longer dropped just because one (e.g. illiquid) wing has no data. Returns
    (anchor_idx, entry_row) or (None, None) when no leg has usable history.
    """
    order = sorted(range(len(legs)), key=lambda i: (legs[i].qty <= 0, -abs(legs[i].qty)))
    for i in order:
        leg = legs[i]
        key = _contract_key(leg.ticker, leg.opt_type, leg.strike, leg.expiration.isoformat())
        row = _entry_row_from_history(barchart_details, key, signal_date, leg.strike, leg.expiration)
        if row is not None:
            return i, row
    return None, None


def _register(contracts: dict, needed_dates: dict, ticker: str, opt_type: str,
              strike: float, exp_date, sig) -> None:
    """Record a distinct contract to fetch Barchart history for, tracking the
    earliest signal date that needs it."""
    key = _contract_key(ticker, opt_type, strike, exp_date.isoformat())
    contracts.setdefault(key, {"key": key, "symbol": ticker, "opt_type": opt_type,
                               "strike": strike, "expiration": exp_date})
    if key not in needed_dates or sig < needed_dates[key]:
        needed_dates[key] = sig


# ─── Analysis loading ──────────────────────────────────────────────────────────

def _load_analysis(tab: str, start: date | None, end: date | None) -> tuple[list[dict], dict]:
    """Read the analysis tab. Returns (candidate trades, market_regime_by_date)."""
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
        d = d_date.isoformat()

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
            # Per-ticker rollup context now stored on the analysis row itself (blank
            # on rows written before this column existed; _attach_rollup_metrics
            # backfills those from the audit rollup CSV).
            "oi_confirm_pct": str(row.get("oi_confirm_pct", "")).strip(),
            "cpir": str(row.get("cpir", "")).strip(),
            "iv_spread": str(row.get("iv_spread", "")).strip(),
        })

    log.info("Loaded %d candidate plays from '%s' (%d market-regime dates)",
             len(candidates), tab, len(market_regime))
    return candidates, market_regime


# ─── Barchart historical option prices ─────────────────────────────────────────

async def _fetch_option_histories(
    contracts: list[dict], headless: bool, timeout_ms: int = 15000,
    needed_dates: dict[tuple, date] | None = None,
    cache_only: bool = False,
) -> tuple[dict[tuple, list], dict[tuple, dict]]:
    """Scrape (and cache) per-contract Barchart price history.

    contracts: list of {key, symbol, opt_type, strike, expiration(date)}.
    needed_dates: {contract_key: earliest_signal_date} — if a cached file's earliest
      row is more than 5 days after the needed date, the cache is stale and re-scraped.
    Returns (series_map, details_map):
      series_map:  {contract_key: [(date, price), ...]}  — for _price_asof exit lookups
      details_map: {contract_key: {date: row_dict}}      — for building entry rows
    """
    _STALENESS_DAYS = 5
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    email = os.getenv("BARCHART_EMAIL", "")
    password = os.getenv("BARCHART_PASSWORD", "")
    cookies_path = Path(os.getenv(
        "COOKIES_PATH", str(RESULTS_PATH.parent / "cookies" / "barchart_session.json")))

    series_map: dict[tuple, list] = {}
    details_map: dict[tuple, dict] = {}
    to_scrape: list[dict] = []

    def _load_cache(c: dict, text: str) -> None:
        series_map[c["key"]] = barchart_options.parse_history_series(text)
        details_map[c["key"]] = barchart_options.parse_history_details(text)

    for c in contracts:
        cache = barchart_options.cache_path(
            HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
        if cache.exists():
            text = cache.read_text(encoding="utf-8")
            _load_cache(c, text)
            if cache_only:
                continue
            # Re-scrape if cache doesn't reach back to the earliest signal date.
            needed = needed_dates.get(c["key"]) if needed_dates else None
            if needed is not None:
                series = series_map.get(c["key"], [])
                earliest = min((d for d, _ in series), default=None)
                if earliest is None or (earliest - needed).days > _STALENESS_DAYS:
                    log.info(
                        "Cache for %s earliest=%s, needed=%s — refetching",
                        c["key"], earliest, needed,
                    )
                    series_map.pop(c["key"], None)
                    details_map.pop(c["key"], None)
                    cache.unlink()
                    to_scrape.append(c)
        elif not cache_only:
            to_scrape.append(c)
        else:
            log.debug("--cache-only: no cache for %s, skipping", c["key"])

    log.info("Barchart history: %d cached, %d to scrape", len(series_map), len(to_scrape))
    if not to_scrape:
        return series_map, details_map
    if not (email and password):
        log.warning("BARCHART_EMAIL/PASSWORD not set — skipping Barchart history (BS fallback will be used)")
        return series_map, details_map

    async with BarchartSession(email, password, cookies_path, headless) as session:
        for i, c in enumerate(to_scrape, 1):
            url = barchart_options.option_history_url(
                c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            log.info("[%d/%d] Barchart history: %s", i, len(to_scrape), url)
            try:
                csv_text = await session.fetch_history_csv(url, timeout_ms)
            except Exception:
                log.exception("Barchart history scrape failed for %s", c["key"])
                csv_text = None
            if not csv_text:
                series_map[c["key"]] = []
                continue
            cache = barchart_options.cache_path(
                HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            cache.write_text(csv_text, encoding="utf-8")
            _load_cache(c, csv_text)
            await asyncio.sleep(2)

    return series_map, details_map


# ─── Output ────────────────────────────────────────────────────────────────────

def _write_results(results, cfg, dry_run) -> None:
    if not results:
        log.warning("No results to write")
        return

    RESULTS_PATH.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    local_csv = cfg["output"].get("local_csv", f"backtests/results_{ts}.csv")
    csv_path = Path(__file__).resolve().parent.parent.parent / local_csv

    if not dry_run:
        if csv_path.exists():
            archive = csv_path.with_name(
                csv_path.stem + "_" + ts + csv_path.suffix)
            csv_path.rename(archive)
            log.info("Archived previous results to '%s'", archive.name)
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_KEY_ORDER, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        log.info("Wrote %d results to '%s'", len(results), csv_path)

        sheet_tab = cfg["output"].get("sheet_tab")
        if sheet_tab:
            sheets_client.append_rows(
                sheet_tab, [{k: r.get(k, "") for k in _KEY_ORDER} for r in results])
            log.info("Appended results to Google Sheets tab '%s'", sheet_tab)
    else:
        log.info("[dry-run] Would write %d results to '%s'", len(results), csv_path)

    _print_summary(results)


def _print_summary(results) -> None:
    print(f"\n{'='*64}")
    print(f"BACKTEST SUMMARY  ({len(results)} plays simulated)")
    print(f"{'='*64}")

    rz = [r for r in results if isinstance(r.get("realized_pnl_pct"), (int, float))]
    if not rz:
        print("\nNo priced plays.")
        return

    # Keep pct and abs aligned on the same rows.
    rz_abs = [r for r in rz if isinstance(r.get("realized_pnl_abs"), (int, float))]
    arr     = np.array([r["realized_pnl_pct"] for r in rz])
    arr_abs = np.array([r["realized_pnl_pct"] for r in rz_abs])
    abs_arr = np.array([r["realized_pnl_abs"] for r in rz_abs])
    held = [r["days_held"] for r in rz if isinstance(r.get("days_held"), (int, float))]
    reasons = {}
    for r in rz:
        reasons[r.get("exit_reason", "")] = reasons.get(r.get("exit_reason", ""), 0) + 1

    def _fmt(pct: float, abs_val: float | None = None) -> str:
        s = f"{pct*100:+.2f}%"
        if abs_val is not None:
            s += f"  (${abs_val:+,.0f})"
        return s

    def _play_line(r: dict) -> str:
        abs_val = r.get("realized_pnl_abs")
        abs_str = f"  (${abs_val:+,.0f})" if isinstance(abs_val, (int, float)) else ""
        leg_lines = [ln for ln in str(r.get("legs", "")).splitlines() if ln.strip()]
        legs_str = leg_lines[0] if leg_lines else ""
        if len(leg_lines) > 1:
            legs_str += f" (+{len(leg_lines) - 1})"
        return (f"  {r['signal_date']} {r['ticker']:6} {r['structure']:16} "
                f"{legs_str:28} → {r['realized_pnl_pct']*100:+.1f}%{abs_str}  [{r.get('exit_reason','')}]")

    has_abs = len(abs_arr) > 0
    print(f"\nRealized exit ({len(arr)} priced, first profit_target/stop_loss/expiry):")
    print(f"  Win rate:   {(arr>0).sum()/len(arr)*100:.1f}%  ({(arr>0).sum()}/{len(arr)})")
    abs_mean = abs_arr.mean() if has_abs else None
    abs_med  = float(np.median(abs_arr)) if has_abs else None
    print(f"  Avg P&L:    {_fmt(arr.mean(), abs_mean)}   Median: {_fmt(float(np.median(arr)), abs_med)}")
    if has_abs:
        i_max, i_min = abs_arr.argmax(), abs_arr.argmin()
        print(f"  Best/Worst: {_fmt(arr_abs[i_max], abs_arr[i_max])} / "
              f"{_fmt(arr_abs[i_min], abs_arr[i_min])}")
    else:
        print(f"  Best/Worst: {arr.max()*100:+.2f}% / {arr.min()*100:+.2f}%")
    if held:
        print(f"  Avg hold:   {np.mean(held):.1f} trading days")
    print("  Exit mix:   " + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())))

    real = [r["realized_pnl_pct"] for r in rz
            if isinstance(r.get("pct_real_days"), (int, float)) and r["pct_real_days"] > 0]
    if real:
        ra = np.array(real)
        print(f"  ↳ real-data subset: {(ra>0).sum()/len(ra)*100:.1f}% win, "
              f"{ra.mean()*100:+.2f}% avg  ({len(ra)} trades)")
    else:
        print("  ↳ real-data subset: none (all Black-Scholes modelled)")

    def _sort_key(r: dict):
        v = r.get("realized_pnl_abs")
        return v if isinstance(v, (int, float)) else r["realized_pnl_pct"]

    ranked = sorted(rz, key=_sort_key, reverse=True)
    top   = ranked[:5]
    worst = ranked[-5:]
    print("\nTop 5 plays by realized P&L ($):")
    for r in top:
        print(_play_line(r))
    print("\nWorst 5 plays by realized P&L ($):")
    for r in worst:
        print(_play_line(r))


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
    parser.add_argument("--cache-only", action="store_true",
                        help="Use cached Barchart history only; skip retrieval even if cache is stale or missing")
    args = parser.parse_args()

    cfg_path = Path(__file__).resolve().parent.parent.parent / args.config
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
        log.warning("No plays found in '%s' — run /options analyze first to populate it", tab)
        sys.exit(0)

    # Join per-ticker flow-rollup context (OIConfirmPct/CPIR/IVSpread) onto each play.
    _attach_rollup_metrics(candidates)

    # Pass 1 — classify each play, build its leg list, and register the contracts
    # whose Barchart history must be fetched.
    matched, contracts, needed_dates = [], {}, {}
    skipped = {"unsupported": 0, "no_strike": 0, "no_expiry": 0, "unpriced": 0}
    for c in candidates:
        c["regime"] = c.get("regime", "")
        cls = classify_play(c["play"])
        structure = cls["structure"]
        if structure == "unsupported":
            skipped["unsupported"] += 1
            log.warning("SKIP unsupported  %s %s | structure=%s | play=%s",
                        c["date"], c["ticker"], structure, c["play"][:80])
            continue

        sig = c["signal_date"]

        if structure == "explicit_legs":
            # Strikes/expirations are fully specified — every leg is a real contract.
            # The anchor is chosen in pass 3 from whichever leg has usable history.
            legs = merge_legs(cls["legs"])
            if not legs:
                skipped["unpriced"] += 1
                continue
            for leg in legs:
                _register(contracts, needed_dates, leg.ticker, leg.opt_type,
                          leg.strike, leg.expiration, sig)
            matched.append({"c": c, "structure": structure, "legs": legs,
                            "is_ic": False, "explicit": True, "cls": cls})
            continue

        result, reason_info = _identify_contract(c, cls, HISTORY_CACHE, spread_pct)
        if result is None:
            skip_cat, reason_msg = reason_info
            skipped[skip_cat] += 1
            log.warning("SKIP %-12s %s %s | %s | play=%s",
                        skip_cat, c["date"], c["ticker"], reason_msg, c["play"][:80])
            continue

        K, exp_date, opt_type, K_short = result
        is_ic = structure == "iron_condor"

        if is_ic:
            # Iron-condor wings depend on the entry underlying (resolved in pass 3);
            # only the short-put anchor needs Barchart history.
            _register(contracts, needed_dates, c["ticker"], "Put", K, exp_date, sig)
            matched.append({"c": c, "structure": structure, "legs": None,
                            "is_ic": True, "explicit": False, "anchor_idx": 1,
                            "anchor": (c["ticker"], "Put", K, exp_date), "cls": cls})
            continue

        legs = merge_legs(legs_from_structure(structure, opt_type, c["ticker"], exp_date, K,
                                              K_short, cls.get("is_credit", False)))
        # legs_from_structure puts the flow-matched leg (strike K) first; it is the
        # anchor regardless of its long/short sign (so credit spreads anchor on the
        # sold leg, the one Barchart history is keyed to).
        anchor = legs[0]
        for leg in legs:
            _register(contracts, needed_dates, leg.ticker, leg.opt_type,
                      leg.strike, leg.expiration, sig)
        matched.append({"c": c, "structure": structure, "legs": legs,
                        "is_ic": False, "explicit": False, "anchor_idx": 0,
                        "anchor": (anchor.ticker, anchor.opt_type, anchor.strike,
                                   anchor.expiration), "cls": cls})

    # Pass 2 — fetch/cache Barchart history for all identified contracts.
    barchart_series: dict[tuple, list] = {}
    barchart_details: dict[tuple, dict] = {}
    if contracts:
        headless = os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
        history_timeout_ms = int(sim_cfg.get("history_timeout_ms", 15000))
        log.info("Fetching Barchart history for %d distinct contract(s)", len(contracts))
        barchart_series, barchart_details = asyncio.run(_fetch_option_histories(
            list(contracts.values()), headless, history_timeout_ms, needed_dates,
            cache_only=args.cache_only))

    # Pass 3 — build entry row from cache, finalize legs, then simulate.
    log.info("Simulating %d classified plays", len(matched))
    created_datetime = datetime.now().isoformat(timespec="seconds")
    results = []
    for m in matched:
        c = m["c"]
        if m.get("explicit"):
            # Choose the anchor from whichever leg actually has Barchart history.
            legs = m["legs"]
            anchor_idx, entry_row = _choose_anchor(legs, barchart_details, c["signal_date"])
            if entry_row is None:
                skipped["unpriced"] += 1
                log.warning("SKIP unpriced     %s %s | no history on/after signal date for any leg",
                            c["signal_date"], c["ticker"])
                continue
            result = _simulate(c, legs, entry_row, {}, barchart_series, sim_cfg,
                               structure=m["structure"], anchor_idx=anchor_idx)
            if result:
                result["created_datetime"] = created_datetime
                result["market_regime"] = _regime_prefix(market_regime.get(c["date"], ""))
                results.append(result)
            else:
                skipped["unpriced"] += 1
                log.warning("SKIP simulate={}  %s %s | explicit legs", c["signal_date"], c["ticker"])
            continue

        a_ticker, a_type, a_K, a_exp = m["anchor"]
        anchor_key = _contract_key(a_ticker, a_type, a_K, a_exp.isoformat())
        entry_row = _entry_row_from_history(barchart_details, anchor_key, c["signal_date"], a_K, a_exp)
        if entry_row is None:
            skipped["unpriced"] += 1
            log.warning("SKIP unpriced     %s %s | no history on/after signal date for %s",
                        c["signal_date"], c["ticker"], anchor_key)
            continue

        legs, anchor_idx = m["legs"], m["anchor_idx"]
        if m["is_ic"]:
            # Resolve the four IC strikes now that the entry underlying is known.
            S_entry = _num(entry_row.get("Price~", entry_row.get("Price")))
            if not S_entry:
                skipped["unpriced"] += 1
                continue
            K_lp, K_sp, K_sc, K_lc = _iron_condor_strikes(
                m["cls"].get("strikes", []), a_K, S_entry, spread_pct)
            legs = iron_condor_legs(c["ticker"], a_exp, K_lp, K_sp, K_sc, K_lc)

        result = _simulate(c, legs, entry_row, {}, barchart_series, sim_cfg,
                           structure=m["structure"], anchor_idx=anchor_idx)
        if result:
            result["created_datetime"] = created_datetime
            result["market_regime"] = _regime_prefix(market_regime.get(c["date"], ""))
            results.append(result)
        else:
            skipped["unpriced"] += 1
            log.warning("SKIP simulate={}  %s %s | anchor=%s",
                        c["signal_date"], c["ticker"], anchor_key)

    log.info("Simulated %d plays (skipped: %d unsupported, %d no_strike, %d no_expiry, %d unpriced)",
             len(results), skipped["unsupported"], skipped["no_strike"], skipped["no_expiry"],
             skipped["unpriced"])

    _write_results(results, cfg, args.dry_run)
