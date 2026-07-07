import argparse
import asyncio
import csv
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from lib.logger import setup_logging

from .plays import build_matched_plays
from .plays import _choose_anchor  # noqa: F401 — re-exported for tests
from .shared.analysis_io import load_analysis as _load_analysis
from .shared.history import fetch_option_histories
from .shared.results_io import write_results

log = logging.getLogger("backtest")

_KEY_ORDER = [
    "signal_date", "ticker", "structure", "legs", "entry_leg_detail", "contracts",
    "dte_entry", "iv_entry_pct", "delta", "entry_underlying",
    "entry_option_price", "entry_premium_total", "entry_source",
    "market_regime", "regime", "play",
    # `horizon` mirrors the analysis row's dedicated column, kept beside `play`.
    "horizon",
    "realized_pnl_pct", "realized_pnl_abs", "days_held", "exit_reason",
    "mfe_pct", "mfe_abs", "mfe_day", "mae_pct", "mae_abs", "mae_day", "pnl_at_cap_pct", "pct_real_days",
    "daily_price_csv", "daily_source_csv",
    "created_datetime",
    # Per-ticker flow-rollup context joined from audit/<date>-rollup.csv (the same
    # date's scored rollup the analysis ran on). Appended at the END so existing
    # sheet rows stay column-aligned. See _attach_rollup_metrics / _ROLLUP_METRIC_COLS.
    "oi_confirm_pct", "cpir", "iv_spread", "iv_skew", "iv_pct",
    # Per-single-contract dollar P&L per trading day, same grid as daily_price_csv.
    # Kept before the structural-risk columns below (not last anymore) for sheet
    # append-alignment (see _summarize_path / backtest-reference.md).
    "daily_pnl_csv",
    # Credit/debit structural risk (scripts/backtest/simulate.py _simulate). Appended
    # at the VERY END, after daily_pnl_csv — Sheets append is positional and
    # append_rows only writes a header on an empty tab, so inserting mid-schema
    # would misalign every existing row. See config/backtest-reference.md.
    "max_loss_per_contract", "pnl_on_risk_pct",
    # Model evidence-quality score, component breakdown + summed total, carried
    # straight off the analysis row. Appended at the VERY END (positional append)
    # so each factor can be measured against realized P&L and pruned later.
    "score_total", "score_flow", "score_dealer", "score_price", "score_vol",
    "score_catalyst",
]

ROOT = Path(__file__).resolve().parent.parent.parent
AUDIT_DIR = ROOT / "audit"

# backtest result key -> rollup CSV column (lib/flow_summary FLOW_CSV_COLUMNS).
_ROLLUP_METRIC_COLS = {
    "oi_confirm_pct": "OIConfirmPct",
    "cpir": "CPIR",
    "iv_spread": "IVSpread",
    "iv_skew": "IVSkew",
    "iv_pct": "IVPct",
}


def _load_rollup_metrics(date_str: str) -> dict[str, dict]:
    """Read ``audit/<date>-rollup.csv`` → ``{SYMBOL: {oi_confirm_pct, cpir, iv_spread, iv_skew, iv_pct}}``.

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
    """Backfill per-ticker rollup metrics (OIConfirmPct/CPIR/IVSpread/IVSkew/IVPct) for
    candidates whose analysis row predates these columns.

    Newer analysis rows already carry the metrics (joined at analysis time — see
    analysis_pipeline.core.analysis_to_rows); those are authoritative and left as-is.
    Only candidates with all metrics blank are filled from that date's
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


# ─── Analysis loading, Barchart history fetch ──────────────────────────────────
# Moved to scripts/backtest/shared/{analysis_io,history}.py so a sibling module
# (e.g. a future proxy.py) can reuse them without importing this core module.
# ``_load_analysis`` and ``fetch_option_histories`` are imported above.


# ─── Output ────────────────────────────────────────────────────────────────────

def _write_results(results, cfg, dry_run) -> None:
    """Thin wrapper over :func:`scripts.backtest.shared.results_io.write_results`,
    supplying this CLI's fixed schema/output config (unchanged behavior)."""
    write_results(
        results,
        key_order=_KEY_ORDER,
        local_csv=cfg["output"].get("local_csv"),
        sheet_tab=cfg["output"].get("sheet_tab"),
        dry_run=dry_run,
        summary_fn=_print_summary,
    )


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
    abs_arr = np.array([r["realized_pnl_abs"] for r in rz_abs])
    held = [r["days_held"] for r in rz if isinstance(r.get("days_held"), (int, float))]
    reasons = {}
    for r in rz:
        reasons[r.get("exit_reason", "")] = reasons.get(r.get("exit_reason", ""), 0) + 1

    def _capital_at_risk(r: dict) -> float | None:
        # Structural max loss (works for both debit and credit sizing) is the
        # true capital-at-risk denominator; entry premium is a debit-only fallback.
        mlpc, contracts = r.get("max_loss_per_contract"), r.get("contracts")
        if isinstance(mlpc, (int, float)) and mlpc > 0 and isinstance(contracts, (int, float)):
            return mlpc * contracts
        prem = r.get("entry_premium_total")
        return prem if isinstance(prem, (int, float)) and prem > 0 else None

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

    # Trade-level % (realized_pnl_pct) is only meaningful per-trade — averaging it
    # across trades with different capital at risk conflates "small % on big money"
    # with "big % on small money". Report $ totals plus one portfolio-level
    # dollar-weighted return (sum $pnl / sum capital at risk) instead.
    if has_abs:
        caps = [_capital_at_risk(r) for r in rz_abs]
        total_pnl = abs_arr.sum()
        total_cap = sum(c for c in caps if c is not None)
        cap_str = f"  on ${total_cap:,.0f} risked  (dollar-wtd return: {total_pnl/total_cap*100:+.1f}%)" if total_cap else ""
        print(f"  Total P&L:  ${total_pnl:+,.0f}{cap_str}")
        print(f"  Avg/Median $: ${abs_arr.mean():+,.0f} / ${float(np.median(abs_arr)):+,.0f}")
        i_max, i_min = abs_arr.argmax(), abs_arr.argmin()
        print(f"  Best/Worst: ${abs_arr[i_max]:+,.0f} / ${abs_arr[i_min]:+,.0f}")
    else:
        print(f"  Best/Worst: {arr.max()*100:+.2f}% / {arr.min()*100:+.2f}%")
    if held:
        print(f"  Avg hold:   {np.mean(held):.1f} trading days")
    print("  Exit mix:   " + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())))

    real_rows = [r for r in rz_abs
                 if isinstance(r.get("pct_real_days"), (int, float)) and r["pct_real_days"] > 0]
    if real_rows:
        ra = np.array([r["realized_pnl_abs"] for r in real_rows])
        win = (ra > 0).sum() / len(ra) * 100
        real_caps = [_capital_at_risk(r) for r in real_rows]
        real_cap_total = sum(c for c in real_caps if c is not None)
        wtd = f", dollar-wtd return: {ra.sum()/real_cap_total*100:+.1f}%" if real_cap_total else ""
        print(f"  ↳ real-data subset: {win:.1f}% win, ${ra.mean():+,.0f} avg{wtd}  ({len(ra)} trades)")
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


# ─── Pass 3: simulate ────────────────────────────────────────────────────────────

def _run_simulations(plays, barchart_series, barchart_details,
                     market_regime, sim_cfg, spread_pct, skipped) -> list[dict]:
    """Pass 3 — resolve each play's entry and simulate it.

    Structure-agnostic: every per-structure difference (anchor choice, iron-condor
    wing resolution) now lives in ``Play.simulate``. This loop only decorates the
    result with the run timestamp + market regime and tallies unpriced skips.
    """
    log.info("Simulating %d classified plays", len(plays))
    created_datetime = datetime.now().isoformat(timespec="seconds")
    results = []
    for play in plays:
        result = play.simulate(barchart_series, barchart_details, sim_cfg, spread_pct)
        if result is None:
            skipped["unpriced"] += 1
            continue
        result["created_datetime"] = created_datetime
        result["market_regime"] = _regime_prefix(market_regime.get(play.c["date"], ""))
        results.append(result)
    return results


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

    # Join per-ticker flow-rollup context (OIConfirmPct/CPIR/IVSpread/IVPct) onto each play.
    _attach_rollup_metrics(candidates)
    # The TF-S structure override gates on the market regime (positive-gamma grind),
    # so make that day's market read visible on the candidate before Pass 1.
    for c in candidates:
        c["market_regime"] = market_regime.get(c["date"], "")

    # Pass 1 — classify each play into a Play, build its legs, and register the
    # contracts whose Barchart history must be fetched. tf_s_override (config-gated,
    # default off) rewrites rich-IV TF debit verticals into TF-S credit spreads.
    tf_s_override = cfg.get("structure_override")
    plays, contracts, needed_dates, skipped = build_matched_plays(
        candidates, spread_pct, tf_s_override)

    # Pass 2 — fetch/cache Barchart history for all identified contracts.
    barchart_series: dict[tuple, list] = {}
    barchart_details: dict[tuple, dict] = {}
    if contracts:
        headless = os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
        history_timeout_ms = int(sim_cfg.get("history_timeout_ms", 15000))
        log.info("Fetching Barchart history for %d distinct contract(s)", len(contracts))
        barchart_series, barchart_details = asyncio.run(fetch_option_histories(
            list(contracts.values()), headless, history_timeout_ms, needed_dates,
            cache_only=args.cache_only))

    # Pass 3 — resolve entry + simulate each Play polymorphically.
    results = _run_simulations(plays, barchart_series, barchart_details,
                               market_regime, sim_cfg, spread_pct, skipped)

    log.info("Simulated %d plays (skipped: %d unsupported, %d no_strike, %d no_expiry, %d unpriced)",
             len(results), skipped["unsupported"], skipped["no_strike"], skipped["no_expiry"],
             skipped["unpriced"])

    _write_results(results, cfg, args.dry_run)
