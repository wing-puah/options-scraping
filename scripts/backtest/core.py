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
from .helpers import _parse_analysis_date, _contract_key
from .classify import classify_play, _identify_contract, _entry_row_from_history
from .simulate import _simulate

log = logging.getLogger("backtest")

_KEY_ORDER = [
    "signal_date", "ticker", "structure", "opt_type", "k_long", "k_short",
    "expiration", "dte_entry", "iv_entry_pct", "delta", "entry_underlying",
    "entry_option_price", "entry_premium_total", "entry_source",
    "regime", "play",
    "realized_pnl_pct", "realized_pnl_abs", "days_held", "exit_reason",
    "mfe_pct", "mfe_day", "mae_pct", "mae_day", "pnl_at_cap_pct", "pct_real_days",
    "daily_price_csv",
    "created_datetime",
]


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
        })

    log.info("Loaded %d candidate plays from '%s' (%d market-regime dates)",
             len(candidates), tab, len(market_regime))
    return candidates, market_regime


# ─── Barchart historical option prices ─────────────────────────────────────────

async def _fetch_option_histories(
    contracts: list[dict], headless: bool, timeout_ms: int = 15000,
) -> tuple[dict[tuple, list], dict[tuple, dict]]:
    """Scrape (and cache) per-contract Barchart price history.

    contracts: list of {key, symbol, opt_type, strike, expiration(date)}.
    Returns (series_map, details_map):
      series_map:  {contract_key: [(date, price), ...]}  — for _price_asof exit lookups
      details_map: {contract_key: {date: row_dict}}      — for building entry rows
    Cached CSVs are reused so re-runs do not re-scrape.
    """
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    email = os.getenv("BARCHART_EMAIL", "")
    password = os.getenv("BARCHART_PASSWORD", "")
    cookies_path = Path(os.getenv("COOKIES_PATH",
        str(RESULTS_PATH.parent / "cookies" / "barchart_session.json")))

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

    # Pass 1 — classify each play and identify its contract from play text.
    matched, contracts, skipped = [], {}, {"unsupported": 0, "no_strike": 0, "no_expiry": 0, "unpriced": 0}
    for c in candidates:
        c["regime"] = c.get("regime", "")
        cls = classify_play(c["play"])
        if cls["structure"] == "unsupported":
            skipped["unsupported"] += 1
            log.warning("SKIP unsupported  %s %s | structure=%s | play=%s",
                        c["date"], c["ticker"], cls["structure"], c["play"][:80])
            continue

        result, reason_info = _identify_contract(c, cls, HISTORY_CACHE, spread_pct)
        if result is None:
            skip_cat, reason_msg = reason_info
            skipped[skip_cat] += 1
            log.warning("SKIP %-12s %s %s | %s | play=%s",
                        skip_cat, c["date"], c["ticker"], reason_msg, c["play"][:80])
            continue

        K, exp_date, opt_type, K_short = result
        exp_raw = exp_date.isoformat()
        is_ic = cls["structure"] == "iron_condor"
        matched.append((c, cls, K, exp_date, opt_type, K_short))

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
    created_datetime = datetime.now().isoformat(timespec="seconds")
    results = []
    for c, cls, K, exp_date, opt_type, K_short in matched:
        is_ic = cls["structure"] == "iron_condor"
        exp_raw = exp_date.isoformat()
        anchor_type = "Put" if is_ic else opt_type
        anchor_key = _contract_key(c["ticker"], anchor_type, K, exp_raw)
        entry_row = _entry_row_from_history(barchart_details, anchor_key, c["signal_date"], K, exp_date)
        if entry_row is None:
            skipped["unpriced"] += 1
            log.warning("SKIP unpriced     %s %s | no history on/after signal date for %s",
                        c["signal_date"], c["ticker"], anchor_key)
            continue
        result = _simulate(c, cls, entry_row, {}, barchart_series, sim_cfg)
        if result:
            result["created_datetime"] = created_datetime
            results.append(result)
        else:
            skipped["unpriced"] += 1
            log.warning("SKIP simulate={}  %s %s | K=%s exp=%s",
                        c["signal_date"], c["ticker"], K, exp_date)

    log.info("Simulated %d plays (skipped: %d unsupported, %d no_strike, %d no_expiry, %d unpriced)",
             len(results), skipped["unsupported"], skipped["no_strike"], skipped["no_expiry"],
             skipped["unpriced"])

    _write_results(results, cfg, args.dry_run)
