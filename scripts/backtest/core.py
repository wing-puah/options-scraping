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

from lib import sheets_client
from lib.logger import setup_logging

from .plays import build_matched_plays, build_needed_ends
from .plays import _choose_anchor  # noqa: F401 — re-exported for tests
from .shared.analysis_io import load_analysis as _load_analysis
from .shared.analysis_io import load_analysis_csv as _load_analysis_csv
from .shared.history import (EXIT_NETWORK_OUTAGE, PLAN_MISSING, PLAN_SCRAPES, PLAN_STALE,
                             PLAN_UNCACHED, PLAN_UNLISTED,
                             NetworkOutage, fetch_option_histories, plan_option_histories)
from .shared.identity import (find_untested, identity_key, keys_from_tab, open_keys,
                              rows_from_tab, split_repriced)
from .shared.results_io import write_results
from .simulate import validate_pricing_config

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
    # would misalign every existing row. See docs/backtest-reference.md.
    "max_loss_per_contract", "pnl_on_risk_pct",
    # Model evidence-quality score, component breakdown + summed total, carried
    # straight off the analysis row. Appended at the VERY END (positional append)
    # so each factor can be measured against realized P&L and pruned later.
    "score_total", "score_flow", "score_dealer", "score_price", "score_vol",
    "score_catalyst",
    # Exit profile this row was simulated on: PROD / CREDIT / a mech-regime cell
    # (BEAR_HE). EMPTY = written before 2026-07-22, i.e. PROD-basis by definition.
    # Appended at the VERY END for the positional-append reason above. Read this
    # when pooling rows across runs — the tab is append-only with no dedup, so a
    # full re-run leaves both bases on the sheet. See scripts/backtest/simulate.py
    # _exit_basis and research/current.md addendum 7.
    "exit_basis",
    # Robustness review B1/B3 (2026-09-07). Appended at the VERY END for the
    # positional-append reason above — the BacktestResults tab header must gain
    # these three, in this order (`python3 scripts/align_tab_headers.py --dry-run`).
    # `pct_stale_days` = share of priced leg-days whose Barchart mark was carried
    # past `simulation.max_price_carry_days`. `cost_total`/`cost_basis` are the
    # transaction-cost charge and what it could see; `cost_basis` is EMPTY when
    # both cost knobs are 0, i.e. the realized columns are gross. Reading a
    # realized figure without this pair is the un-labelled-basis failure
    # `exit_basis` exists for. See docs/backtest-reference.md.
    "pct_stale_days", "cost_total", "cost_basis",
    # How the realized exit was FILLED (2026-09-19). `same_day` = the trigger day
    # had a two-sided quote; `deferred_<n>` = it did not, so the fill was carried
    # n grid days to the next day that did and `days_held` is that later day;
    # `no_two_sided` = no fillable day ever arrived and the fill stayed on the
    # trigger mark, as it did before this rule. EMPTY = written before
    # 2026-09-19, when the exit always filled on the trigger day.
    # Appended at the VERY END for the positional-append reason above — the
    # BacktestResults tab header must gain it (`align_tab_headers.py --dry-run`).
    # See simulate.py::_summarize_path and docs/backtest-reference.md.
    "exit_fill",
    # Did the simulated path outlive the price data (2026-09-23)? `path_status` =
    # `complete` (the exit fired on a day every leg quoted), `carried` (it fired
    # on a day at least one leg's mark was carried into) or `open_at_data_end`
    # (the data ran out before any exit fired, so the row is marked at the last
    # real quote instead of at the cap). `path_data_end` is that last real
    # quote's date. BOTH EMPTY on every row written before 2026-09-23, where the
    # question was never asked — never backfill a value onto a stored row.
    # Appended at the VERY END for the positional-append reason above; the
    # BacktestResults tab header must gain both, in this order
    # (`python3 scripts/align_tab_headers.py --dry-run`).
    # See simulate.py::_leg_data_end and docs/backtest-reference.md.
    "path_status", "path_data_end",
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


# ─── The already-backtested guard ──────────────────────────────────────────────
# `append_rows` appends. It does not upsert, and a Sheets tab has no undo, so a
# second run over a date this tab already holds leaves BOTH runs' rows on it —
# and they are not copies. A re-run reprices the same play on whatever the exit
# config, the cached Barchart history and the classifier say TODAY, so the two
# rows can disagree about the exit, the basis and the P&L while looking equally
# authoritative. `exit_basis` exists precisely because that happened: rows
# written before 2026-07-22 carry a different exit profile from rows written
# after it, on the same tab.
#
# It has already bitten. The 2025-12-22 SPY duplicate found on 2026-09-06 came
# from a re-run of this module, and 15 older duplicates came with it. Nothing
# stopped it, because until now this module never read its own destination.
#
# So a play already on the results tab is DROPPED before Pass 1 — before the
# Barchart fetch, which is the expensive step, for the same reason the analysis
# pipeline checks before its first LLM call: a guard that costs a run to reach
# is not a guard. `--redo` is the override and deletes the existing rows first
# rather than appending beside them, which is the same contract `proxy.py`'s
# `--redo` already has. The identity key is shared with the proxy
# (`shared/identity.py`) so both writers agree on what a duplicate is.
#
# A play already on the PROXY tab is dropped too, by default (2026-10-17). A
# play lands on `BacktestProxy` because this module could not price it: its
# contracts returned no history. A fetch that returns no rows writes no cache
# file, and only a 404 reaches the `_unlisted.jsonl` negative cache, so such a
# play stayed a candidate on every unbounded run and re-scraped every contract
# it had — 2,204 plays / 3,632 fetches on 2026-10-17 against 193 / 251 for the
# same run bounded with --start. It reprices to a proxy row again almost always,
# so retrying it by default costs a scrape per run for nothing. `--retry-proxied`
# is the opt-in for when Barchart has since listed the contract. The proxy tab
# is READ here through `keys_from_tab`, never through `proxy.py`: the proxy
# reads BacktestResults as an input, and that dependency stays one-way. Nothing
# on the proxy tab is ever deleted from here; `--redo` still deletes and
# replaces rows on the results tab only.

def _proxy_tab(cfg: dict) -> str | None:
    """The proxy's destination tab, resolved the way `proxy.py::main` resolves
    it (`proxy.sheet_tab`, default `BacktestProxy`; null = local-only proxy)."""
    return (cfg.get("proxy") or {}).get("sheet_tab", "BacktestProxy")


def _drop_already_proxied(candidates: list[dict], cfg: dict, args,
                          on_results: set) -> list[dict]:
    """Drop candidates already on the proxy tab, unless `--retry-proxied`.

    A key that is ALSO on the results tab is never dropped here: that play is
    the results tab's business (skipped by the guard, or replaced by --redo).
    """
    proxy_tab = _proxy_tab(cfg)
    if getattr(args, "retry_proxied", False):
        log.info("--retry-proxied: plays already on '%s' stay candidates", proxy_tab)
        return candidates
    if not proxy_tab:
        log.info("proxy.sheet_tab is null — no proxy tab to read; proxied plays are "
                 "not dropped")
        return candidates
    proxied = keys_from_tab(proxy_tab) - on_results
    remaining = find_untested(candidates, proxied)
    dropped = len(candidates) - len(remaining)
    (log.warning if dropped else log.info)(
        "SKIPPING %d play(s) already on '%s' (could not be priced before; a retry "
        "almost always proxies again). Pass --retry-proxied to re-fetch them.",
        dropped, proxy_tab)
    return remaining


def _drop_already_backtested(candidates: list[dict], cfg: dict,
                             args) -> tuple[list[dict], set]:
    """Split candidates into (to simulate, keys to delete first).

    The two-value view of :func:`_split_already_backtested`; open rows being
    re-priced stay in the first value.
    """
    remaining, redo_keys, _ = _split_already_backtested(candidates, cfg, args)
    return remaining, redo_keys


def _split_already_backtested(candidates: list[dict], cfg: dict,
                              args) -> tuple[list[dict], set, dict]:
    """Split candidates into (to simulate, keys to delete first, open rows to
    re-price as ``{key: stored row}``).

    A play already on the tab is skipped, EXCEPT one stored
    `open_at_data_end`: its data ran out before an exit fired, so it stays a
    candidate and is re-priced in place (`--no-reprice-open` restores the
    skip). Whether its new row replaces the old is decided after simulating
    (`identity.split_repriced`).

    Skipped entirely when `output.sheet_tab` is null. That is local-only mode,
    where the only destination is `output.local_csv` — which this CLI REWRITES
    each run rather than appending to, so it cannot accumulate a duplicate and
    there is nothing for the guard to protect.
    """
    sheet_tab = (cfg.get("output") or {}).get("sheet_tab")
    if not sheet_tab:
        log.info("output.sheet_tab is null (local-only run) — the already-backtested "
                 "check is skipped; the local CSV is rewritten, not appended")
        return candidates, set(), {}

    rows = rows_from_tab(sheet_tab)
    existing = set(rows)
    if args.redo:
        redo_keys = {k for k in (identity_key(c["signal_date"], c["ticker"], c.get("play", ""))
                                 for c in candidates) if k in existing}
        log.warning("--redo: %d play(s) already on '%s' will be re-simulated and their "
                    "existing rows DELETED before the new ones are appended",
                    len(redo_keys), sheet_tab)
        return _drop_already_proxied(candidates, cfg, args, existing), redo_keys, {}

    reprice_rows: dict = {}
    if not getattr(args, "no_reprice_open", False):
        cand_keys = {identity_key(c["signal_date"], c["ticker"], c.get("play", ""))
                     for c in candidates}
        reprice_rows = {k: rows[k] for k in open_keys(rows) if k in cand_keys}
    remaining = find_untested(candidates, existing - set(reprice_rows))
    dropped = len(candidates) - len(remaining)
    if dropped:
        log.warning("SKIPPING %d play(s) already on '%s'. Re-simulating APPENDS a second "
                    "row that may disagree with the first about the exit, the basis and "
                    "the P&L. Pass --redo to replace them instead.", dropped, sheet_tab)
    if reprice_rows:
        log.info("RE-PRICING %d open_at_data_end play(s) already on '%s' in place "
                 "(--no-reprice-open to skip them)", len(reprice_rows), sheet_tab)
    log.info("%d/%d candidate plays are not yet on '%s'",
             len(remaining) - len(reprice_rows), len(candidates), sheet_tab)
    return (_drop_already_proxied(remaining, cfg, args, existing), set(), reprice_rows)


# ─── Output ────────────────────────────────────────────────────────────────────

def _write_results(results, cfg, dry_run, before_sheet=None) -> None:
    """Thin wrapper over :func:`scripts.backtest.shared.results_io.write_results`,
    supplying this CLI's fixed schema/output config (unchanged behavior)."""
    write_results(
        results,
        key_order=_KEY_ORDER,
        local_csv=cfg["output"].get("local_csv"),
        sheet_tab=cfg["output"].get("sheet_tab"),
        dry_run=dry_run,
        summary_fn=_print_summary,
        before_sheet=before_sheet,
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
        cap_str = (f"  on ${total_cap:,.0f} risked  "
                   f"(dollar-wtd return: {total_pnl/total_cap*100:+.1f}%)") if total_cap else ""
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
        print("  ↳ real-data subset: none (no row carries a priced day)")

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


# ─── --dry-run ─────────────────────────────────────────────────────────────────

#: An unbounded run (no --date/--start/--end) that would scrape more contracts
#: than this logs a WARNING suggesting --start. It is not refused.
UNBOUNDED_SCRAPE_WARN = 500


def _print_dry_run(plays, plan, redo_keys: set, reprice_keys: set = frozenset()) -> None:
    """Per play, what a real run would do, and the contract totals.

    Reads only ``plan`` (built from disk by `plan_option_histories`): no
    Barchart call. Plays Pass 1 refused were already logged as SKIP lines.
    """
    from .helpers import _contract_key
    print(f"\n{'='*64}")
    print(f"DRY RUN  ({len(plays)} classified plays — nothing fetched, nothing written)")
    print(f"{'='*64}")
    for p in plays:
        keys = [_contract_key(t, o, k, e.isoformat()) for (t, o, k, e) in p.contracts]
        st = [plan.status.get(k) for k in keys]
        n_scrape = sum(s in PLAN_SCRAPES for s in st)
        n_dead = sum(s in (PLAN_UNLISTED, PLAN_UNCACHED) for s in st)
        n_cached = len(st) - n_scrape - n_dead
        verb = "scrape+simulate" if n_scrape else "simulate"
        if n_dead == len(st) and st:
            verb = "unpriceable (no history)"
        k = identity_key(p.c["signal_date"], p.c["ticker"], p.c.get("play", ""))
        redo = (" [replaces existing row]" if k in redo_keys
                else " [re-prices open row]" if k in reprice_keys else "")
        print(f"  {p.c['date']} {p.c['ticker']:6} {p.structure:22} {verb:24} "
              f"contracts: {n_cached} cached, {n_scrape} to scrape, {n_dead} no-data{redo}")
    n_scrape = len(plan.to_scrape)
    print(f"\nContracts: {len(plan.status)} distinct — "
          f"{len(plan.status) - n_scrape - plan.count(PLAN_UNLISTED, PLAN_UNCACHED)} cached, "
          f"{n_scrape} would be scraped "
          f"({plan.count(PLAN_MISSING)} missing, {plan.count(PLAN_STALE)} stale), "
          f"{plan.count(PLAN_UNLISTED)} known-unlisted, "
          f"{plan.count(PLAN_UNCACHED)} uncached under --cache-only")
    n_reprice = sum(1 for p in plays if identity_key(
        p.c["signal_date"], p.c["ticker"], p.c.get("play", "")) in reprice_keys)
    print(f"re-price open: {n_reprice} (stale-forward caches: {len(plan.stale_forward)})")


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
            # A REFUSAL is tallied under its own reason, not pooled into
            # `unpriced`: `debit_priced_to_credit` / `credit_priced_to_debit` /
            # `non_monotonic_entry_quote` mean the data was there and was wrong,
            # and `no_real_entry_price` names the leg that had none — each a
            # different thing from the anchor having no data.
            key = play.refusal.get("reason", "unpriced")
            skipped[key] = skipped.get(key, 0) + 1
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
    parser.add_argument("--analysis-csv",
                        help="Local analysis rows CSV to backtest instead of a Sheets tab "
                             "(overrides config analysis.csv, which itself wins over analysis.tab)")
    parser.add_argument("--date", help="Single analysis date YYYY-MM-DD (sets --start and --end)")
    parser.add_argument("--start", help="Earliest analysis date (YYYY-MM-DD)")
    parser.add_argument("--end", help="Latest analysis date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview: read the tabs, print per play what would happen and "
                             "how many contracts are cached vs would be scraped, then stop. "
                             "Makes NO Barchart call and writes nothing.")
    parser.add_argument("--cache-only", action="store_true",
                        help="Use cached Barchart history only; skip retrieval even if cache is stale or missing")
    parser.add_argument("--redo", action="store_true",
                        help="Re-simulate plays already on the results tab, DELETING their "
                             "existing rows first instead of appending beside them (requires "
                             "--date or --start/--end). Without it such plays are skipped: "
                             "the tab appends, and a re-priced row can disagree with the "
                             "first about the exit, the basis and the P&L.")
    parser.add_argument("--retry-proxied", action="store_true",
                        help="Keep plays already on the proxy tab (BacktestProxy) as "
                             "candidates and re-fetch their contracts. Without it they "
                             "are skipped: they could not be priced before, and a retry "
                             "almost always proxies again at the cost of a scrape.")
    parser.add_argument("--retry-unlisted", action="store_true",
                        help="Probe contracts recorded as unlisted on Barchart "
                             "(backtests/option_history_cache/_unlisted.jsonl) instead of "
                             "skipping them — an operator-requested re-check; "
                             "BACKTEST_RETRY_UNLISTED=1 does the same")
    parser.add_argument("--no-reprice-open", action="store_true",
                        help="Skip plays whose stored row is open_at_data_end like any "
                             "other already-backtested play. By default they are "
                             "re-priced, and the row is replaced only when the new "
                             "one reaches a later path_data_end or changes its "
                             "path_status/exit_reason.")
    args = parser.parse_args()
    # Same bound proxy.py's --redo carries: an unbounded --redo would delete and
    # rewrite the whole tab, which is a re-backtest of the book and not a repair.
    if args.redo and not (args.date or args.start or args.end):
        parser.error("--redo needs a date bound (--date, or --start/--end)")

    cfg_path = Path(__file__).resolve().parent.parent.parent / args.config
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)

    analysis_cfg = cfg.get("analysis", {}) or {}
    tab = args.tab or analysis_cfg.get("tab", "AnalysisClaude")
    # A local CSV source WINS over the tab: a prompt-evaluation run points at a
    # rows CSV written by `analysis_pipeline --output-dir` and must never read
    # (or, downstream, write) the production tabs.
    analysis_csv = args.analysis_csv or analysis_cfg.get("csv")
    if args.date:
        start = end = date.fromisoformat(args.date)
    else:
        start = date.fromisoformat(args.start) if args.start else None
        end = date.fromisoformat(args.end) if args.end else None
    sim_cfg = cfg["simulation"]
    # Refused before any Sheets read or Barchart fetch: a config that asks for a
    # model price (Black-Scholes, abolished 2026-09-23) must fail loudly.
    validate_pricing_config(sim_cfg)
    spread_pct = sim_cfg.get("spread_width_pct", 0.02)

    if analysis_csv:
        log.info("analysis source: csv %s", analysis_csv)
        candidates, market_regime = _load_analysis_csv(analysis_csv, start, end)
        source = str(analysis_csv)
    else:
        log.info("analysis source: tab %s", tab)
        candidates, market_regime = _load_analysis(tab, start, end)
        source = tab
    if not candidates:
        log.warning("No plays found in '%s' — run `python3 -m scripts.analysis_pipeline` "
                    "first to populate it", source)
        sys.exit(0)

    # Checked BEFORE the Barchart fetch and before any classification: a play
    # already on the results tab costs nothing to skip here, and everything to
    # discover after it has been appended a second time.
    candidates, redo_keys, reprice_rows = _split_already_backtested(candidates, cfg, args)
    if not candidates:
        log.warning("Nothing to simulate: every candidate play in '%s' is already on the "
                    "results tab or the proxy tab. Pass --redo to replace results rows, "
                    "--retry-proxied to re-fetch proxied plays.", source)
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
    structure_veto = (cfg.get("entry") or {}).get("structure_veto") or ()
    plays, contracts, needed_dates, skipped = build_matched_plays(
        candidates, spread_pct, tf_s_override, structure_veto)

    # Pass 2 — fetch/cache Barchart history for all identified contracts. The
    # plan is built from disk alone; it is what --dry-run prints, and the real
    # fetch is handed it so the cache is read once.
    retry_unlisted = args.retry_unlisted or None
    # needed_ends adds the FORWARD check: a cached file that stops short of
    # its play's path end is refetched (shared/history.py::is_forward_stale).
    needed_ends = build_needed_ends(plays, sim_cfg.get("path_cap_days", 120))
    plan = plan_option_histories(list(contracts.values()), needed_dates,
                                 cache_only=args.cache_only, retry_unlisted=retry_unlisted,
                                 needed_ends=needed_ends)
    n_scrape = len(plan.to_scrape)
    if n_scrape > UNBOUNDED_SCRAPE_WARN and not (args.date or args.start or args.end):
        log.warning("Unbounded run would scrape %d contract(s) from Barchart. Bound it with "
                    "--start YYYY-MM-DD (the dates since the last run) unless a full "
                    "re-scrape is intended.", n_scrape)
    if args.dry_run:
        # A preview must cost nothing: no browser, no Barchart call, no write.
        # It used to fetch every contract and then discard the result
        # (~3,600 scrapes for one preview, 2026-10-17).
        _print_dry_run(plays, plan, redo_keys, set(reprice_rows))
        return

    barchart_series: dict[tuple, list] = {}
    barchart_details: dict[tuple, dict] = {}
    if contracts:
        headless = os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
        history_timeout_ms = int(sim_cfg.get("history_timeout_ms", 15000))
        log.info("Fetching Barchart history for %d distinct contract(s)", len(contracts))
        try:
            barchart_series, barchart_details = asyncio.run(fetch_option_histories(
                list(contracts.values()), headless, history_timeout_ms, needed_dates,
                cache_only=args.cache_only, retry_unlisted=retry_unlisted, plan=plan,
                needed_ends=needed_ends))
        except NetworkOutage as e:
            # The only fetch of the run, and it precedes every write (the local
            # CSV, the --redo delete, append_rows): nothing has been written.
            log.error("network outage: %d of %d fetches failed with network errors "
                      "— nothing was written; re-run when online", e.n_failed, e.n_total)
            sys.exit(EXIT_NETWORK_OUTAGE)

    # Pass 3 — resolve entry + simulate each Play polymorphically.
    results = _run_simulations(plays, barchart_series, barchart_details,
                               market_regime, sim_cfg, spread_pct, skipped)

    log.info("Simulated %d plays (skipped: %s)", len(results),
             ", ".join(f"{n} {k}" for k, n in skipped.items()))

    # Re-priced open rows: keep a new row only when it says something new, and
    # delete only the keys it replaces. An unchanged re-price writes nothing;
    # a re-price that now prices nothing leaves the old row alone.
    replace_keys: set = set()
    if reprice_rows:
        n_back = sum(1 for r in results if identity_key(
            r.get("signal_date", ""), r.get("ticker", ""), r.get("play", "")) in reprice_rows)
        results, replace_keys = split_repriced(results, reprice_rows)
        log.info("re-price open: %d of %d replaced, %d unchanged (nothing written), "
                 "%d not priced now (old row kept)", len(replace_keys), len(reprice_rows),
                 n_back - len(replace_keys), len(reprice_rows) - n_back)

    # Local CSV, then delete, then append — in that order. Delete-before-append
    # keeps the new rows from ever landing beside the old ones (the failure
    # --redo exists to prevent); CSV-before-delete keeps a Sheets failure from
    # losing the simulated run.
    sheet_tab = (cfg.get("output") or {}).get("sheet_tab")
    delete_old = None
    doomed = redo_keys | replace_keys
    if doomed and sheet_tab and not args.dry_run:
        def delete_old():  # noqa: F811 — conditional definition over the None default
            sheets_client.delete_rows_where(
                sheet_tab,
                lambda r: identity_key(r.get("signal_date", ""), r.get("ticker", ""),
                                       r.get("play", "")) in doomed)

    _write_results(results, cfg, args.dry_run, before_sheet=delete_old)
