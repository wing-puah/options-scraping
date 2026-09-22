"""Which stored backtest rows are priced wrong, and can each be re-priced offline?

A READ-ONLY census. It names every row on the two results tabs (from the
`backtests/to_evaluate/` exports) that falls in one of the three sets the
operator ruled on 2026-09-22 (research/next-steps.md §0 items 6, 7 and 9), then
re-prices every row on those rows' DATES in memory under current code, from the
option-history cache only. Nothing is written except the report CSV.

THE THREE SETS
--------------
  prefill       the stored exit (`days_held`) lands BEFORE the recorded fill
                (`prefill_audit.audit_trade`). Fixed in code by B2 (2026-09-08).
  wrong_strike  the current classifier builds different strikes from the ones
                the row was priced on (results: `legs`; proxy: `legs_original`,
                the pre-tweak parse). Fixed in code by 90bea63 (header strikes).
  open_fill     a leg was filled at its entry-day `Open` print
                (`[barchart_open]` in `entry_leg_detail`) while that day's quote
                was ONE-SIDED (`simulate._entry_side_mark` claims it). Fixed in
                code 2026-09-22: the side rule now precedes the Open print.

WHY WHOLE DATES
---------------
`--redo` is bounded by DATE, not by row: `scripts.backtest --date D --redo`
re-simulates every play of D and replaces every row of D it already holds, and
`scripts.backtest.proxy` does the same for the plays D leaves untested. So the
report re-prices every stored row on a target date, and marks the targets.

OFFLINE vs REFETCH
------------------
The in-memory re-price reads the cache as it is (`cache_only=True`). The real
`--redo` runs WITHOUT `--cache-only`, so it refetches any leg whose cache file is
missing or starts more than 5 days after the signal (`history.py`). A row with
such a leg `needs_refetch`: its offline price is provisional or absent.

SAFETY
------
`BarchartSession`, the proxy's probe fetch and every `sheets_client` mutator are
replaced by raisers before anything runs, and Barchart credentials are cleared
from the environment. The cache is only ever opened for reading.

    python3 -m scripts.backtest_study.lib.reprice_targets [--root PATH] [--out CSV]
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import yaml  # noqa: E402

from lib import sheets_client  # noqa: E402
from lib.barchart import options as bo  # noqa: E402
from scripts.backtest import plays as PL  # noqa: E402
from scripts.backtest import proxy as P  # noqa: E402
from scripts.backtest import simulate as SIM  # noqa: E402
from scripts.backtest.helpers import _weekday_grid  # noqa: E402
from scripts.backtest.legs import _parse_leg_line, format_legs, parse_legs  # noqa: E402
from scripts.backtest.plays import build_matched_plays, classify_and_build  # noqa: E402
from scripts.backtest.shared import history as H  # noqa: E402
from scripts.backtest.shared.analysis_io import load_analysis_csv  # noqa: E402
from scripts.backtest.shared.identity import identity_key  # noqa: E402
from scripts.backtest_study.lib.prefill_audit import audit_trade  # noqa: E402

log = logging.getLogger("reprice_targets")

RESULTS = "BacktestResults"
PROXY = "BacktestProxy"
SHALLOW_DAYS = 5                     # history.py's _STALENESS_DAYS

OUT_FIELDS = [
    "tab", "signal_date", "ticker", "structure", "target_sets", "prefill_flagged14",
    "stored_created", "stored_entry_source", "stored_entry", "stored_exit_reason",
    "stored_days_held", "stored_R", "stored_legs", "new_legs",
    "offline_status", "new_entry_source", "new_entry", "new_exit_reason",
    "new_days_held", "new_R", "moved", "legs_missing_cache", "legs_shallow_cache",
    "needs_refetch", "cross_tab", "detail", "play_prefix",
]

# The 14 pre-fill rows that reach the pooled book (prefill_audit via load_book).
# The raw tabs hold 17; the other three never join the book. Listed so the
# report can say which is which — the SET itself is recomputed, never read here.
FLAGGED14 = {
    ("2024-03-04", "TSM"), ("2024-03-07", "EEM"), ("2024-04-19", "NFLX"),
    ("2024-05-07", "NVDA"), ("2024-06-03", "NVDA"), ("2024-06-06", "MSTR"),
    ("2024-07-03", "HYG"), ("2024-07-09", "NFLX"), ("2024-07-17", "SMH"),
    ("2024-11-08", "KRE"), ("2024-12-10", "FXI"), ("2025-01-27", "HYG"),
    ("2025-03-03", "TLT"), ("2025-04-01", "TLT"),
}


# ── safety ───────────────────────────────────────────────────────────────────

def _forbidden(*_a, **_k):
    raise RuntimeError("reprice_targets is read-only: a network or Sheets write was attempted")


def lock_down(cache_dir: Path) -> None:
    """Point every pricer at `cache_dir` and make every writer raise."""
    os.environ.pop("BARCHART_EMAIL", None)
    os.environ.pop("BARCHART_PASSWORD", None)
    H.BarchartSession = _forbidden
    P.fetch_option_histories = _forbidden        # only reached through _probe_pool
    for name in ("append_rows", "delete_rows_where", "write_rows", "clear_tab",
                 "update_rows", "ensure_tab", "_ensure_tab"):
        if hasattr(sheets_client, name):
            setattr(sheets_client, name, _forbidden)
    for mod in (H, P, PL):
        mod.HISTORY_CACHE = cache_dir
    # The proxy globs the whole cache per candidate; memoise it per ticker.
    pools: dict[str, list] = {}
    orig = P._cache_contracts

    def _memo(ticker):
        t = ticker.upper()
        if t not in pools:
            pools[t] = orig(t)
        return pools[t]
    P._cache_contracts = _memo


# ── small parsers ────────────────────────────────────────────────────────────

def _f(v):
    try:
        s = str(v).strip().replace("%", "").replace(",", "")
        return float(s) if s else None
    except ValueError:
        return None


def _date(v) -> date | None:
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except ValueError:
        return None


def entry_leg_tags(detail: str) -> list[tuple]:
    """`[(Leg, tag)]` off an `entry_leg_detail` cell, one per leg line."""
    out = []
    for line in str(detail or "").splitlines():
        head, _, rest = line.partition("  px=")
        leg = _parse_leg_line(head)
        if leg is None:
            continue
        tag = rest[rest.rfind("[") + 1:rest.rfind("]")] if "[" in rest else ""
        out.append((leg, tag))
    return out


def recorded_entry_day(row: dict) -> date | None:
    """`legs[0].expiration - dte_entry` — the fill day production RECORDED."""
    legs = parse_legs(row.get("legs", "")) or []
    dte = _f(row.get("dte_entry"))
    if not legs or dte is None:
        return None
    return legs[0].expiration - timedelta(days=int(dte))


def strikes_of(legs) -> tuple:
    return tuple(sorted(float(leg.strike) for leg in legs or ()))


# ── the three sets ───────────────────────────────────────────────────────────

def is_prefill(row: dict) -> bool:
    legs = parse_legs(row.get("legs", "")) or []
    sig = _date(row.get("signal_date"))
    ed = recorded_entry_day(row)
    if not legs or sig is None or ed is None:
        return False
    grid = _weekday_grid(sig, max(ed, sig + timedelta(days=7)))
    trade = SimpleNamespace(legs=legs, dte_entry=row.get("dte_entry"), grid=grid)
    return audit_trade(trade, _f(row.get("days_held"))) == "pre_entry_exit"


class Cache:
    """Read-only per-contract history, parsed once."""

    def __init__(self, root: Path):
        self.root = root
        self._d: dict[tuple, dict | None] = {}

    def details(self, leg) -> dict | None:
        k = (leg.ticker, leg.expiration, leg.strike, leg.opt_type)
        if k not in self._d:
            p = bo.cache_path(self.root, leg.ticker, leg.expiration, leg.strike, leg.opt_type)
            self._d[k] = bo.parse_history_details(p.read_text(encoding="utf-8")) \
                if p.exists() else None
        return self._d[k]

    def state(self, leg, signal: date) -> str:
        """'ok' | 'missing' | 'shallow' — what a non-cache-only run would do."""
        d = self.details(leg)
        if d is None:
            return "missing"
        first = min(d, default=None)
        if first is None or (first - signal).days > SHALLOW_DAYS:
            return "shallow"
        return "ok"


def open_fill_legs(row: dict, cache: Cache) -> tuple[int, int]:
    """`(one_sided_open_legs, undeterminable_open_legs)` for one stored row."""
    ed = recorded_entry_day(row)
    hit = unknown = 0
    for leg, tag in entry_leg_tags(row.get("entry_leg_detail", "")):
        if tag != "barchart_open":
            continue
        day_row = (cache.details(leg) or {}).get(ed) if ed else None
        if day_row is None:
            unknown += 1
        elif SIM._entry_side_mark(day_row, leg.qty) is not None:
            hit += 1
    return hit, unknown


# ── re-pricing, in memory ────────────────────────────────────────────────────

def _key(c: dict) -> tuple:
    return identity_key(c["signal_date"], c["ticker"], c.get("play", ""))


def _row_key(r: dict) -> tuple:
    return identity_key(r.get("signal_date", ""), r.get("ticker", ""), r.get("play", ""))


def reprice_results(cands, cfg) -> dict[tuple, dict]:
    sim_cfg = cfg["simulation"]
    spread = sim_cfg.get("spread_width_pct", 0.02)
    veto = (cfg.get("entry") or {}).get("structure_veto") or ()
    plays, contracts, needed, _ = build_matched_plays(
        cands, spread, cfg.get("structure_override"), veto)
    series, details = asyncio.run(H.fetch_option_histories(
        list(contracts.values()), True, 15000, needed, cache_only=True))
    out = {}
    for play in plays:
        play.refusal = {}
        try:
            res = play.simulate(series, details, sim_cfg, spread)
        except Exception as e:  # noqa: BLE001 — a census reports, it never stops
            out[_key(play.c)] = {"status": "error", "detail": repr(e)[:120],
                                 "legs": play.legs}
            continue
        if res:
            out[_key(play.c)] = {"status": "priced", "res": res, "legs": play.legs}
        else:
            out[_key(play.c)] = {"status": play.refusal.get("reason") or "unpriced",
                                 "detail": (play.refusal.get("detail") or "")[:120],
                                 "legs": play.legs}
    for c in cands:
        if _key(c) not in out:
            _, skip = classify_and_build(c, spread, cfg.get("structure_override"), veto)
            out[_key(c)] = {"status": f"not_built:{skip[0] if skip else '?'}",
                            "detail": (skip[1] if skip else "")[:120], "legs": []}
    return out


def reprice_proxy(cands, cfg) -> dict[tuple, dict]:
    sim_cfg = cfg["simulation"]
    spread = sim_cfg.get("spread_width_pct", 0.02)
    veto = (cfg.get("entry") or {}).get("structure_veto") or ()
    created = datetime.now().isoformat(timespec="seconds")
    out = {}
    for c in cands:
        c = {**c, "market_regime": P._regime_prefix(c.get("market_regime", ""))}
        play, reason = classify_and_build(c, spread, None, veto)
        try:
            row = P._evaluate(play, reason, c, cfg.get("proxy", {}), sim_cfg, spread,
                              created, False)
        except Exception as e:  # noqa: BLE001
            out[_key(c)] = {"status": "error", "detail": repr(e)[:120],
                            "legs": play.legs if play else []}
            continue
        if _f(row.get("pnl_on_risk_pct")) is not None:
            status = "priced"
        elif row.get("skip_reason") == SIM.DEBIT_CREDIT_REFUSAL:
            status = SIM.DEBIT_CREDIT_REFUSAL
        else:
            status = row.get("proxy_method") or "unpriced"
        out[_key(c)] = {"status": status,
                        "res": row, "legs": play.legs if play else [],
                        "detail": str(row.get("proxy_detail", ""))[:120]}
    return out


# ── the census ───────────────────────────────────────────────────────────────

def load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def classify_sets(tab: str, rows: list[dict], cache: Cache,
                  built: dict[tuple, list]) -> dict[tuple, dict]:
    """`{row_key: {"sets": [...], "note": str}}` for every row in any set."""
    out = {}
    for r in rows:
        sets, notes = [], []
        if is_prefill(r):
            sets.append("prefill")
        stored_legs = parse_legs(r.get("legs_original") if tab == PROXY
                                 else r.get("legs")) or []
        new_legs = built.get(_row_key(r))
        priced = _f(r.get("pnl_on_risk_pct")) is not None
        if priced and stored_legs and new_legs is not None \
                and strikes_of(stored_legs) != strikes_of(new_legs):
            sets.append("wrong_strike")
            notes.append(f"strikes {strikes_of(stored_legs)} -> {strikes_of(new_legs)}")
        hit, unknown = open_fill_legs(r, cache)
        if hit:
            sets.append("open_fill")
        if unknown:
            notes.append(f"{unknown} Open leg(s) with no cached entry-day row")
        if sets:
            out[_row_key(r)] = {"sets": sets, "note": "; ".join(notes)}
    return out


def build_classification(cands, cfg, tf_s) -> dict[tuple, list]:
    """`{key: legs}` — what the CURRENT classifier builds for each candidate.

    `tf_s` is the structure override the WRITER applies: the results backtest
    passes `structure_override`, the proxy passes None.
    """
    sim_cfg = cfg["simulation"]
    spread = sim_cfg.get("spread_width_pct", 0.02)
    veto = (cfg.get("entry") or {}).get("structure_veto") or ()
    out = {}
    for c in cands:
        play, _ = classify_and_build(c, spread, tf_s, veto)
        out[_key(c)] = play.legs if play is not None else []
    return out


def census(root: Path) -> tuple[list[dict], dict]:
    to_eval = root / "backtests" / "to_evaluate"
    cache_dir = root / "backtests" / "option_history_cache"
    lock_down(cache_dir)
    cfg = yaml.safe_load((REPO / "config" / "backtest.yml").read_text())
    cache = Cache(cache_dir)

    stored = {RESULTS: load_rows(to_eval / "analysis - BacktestResults.csv"),
              PROXY: load_rows(to_eval / "analysis - BacktestProxy.csv")}
    all_cands, mkt = load_analysis_csv(to_eval / "analysis - AnalysisClaude.csv", None, None)
    for c in all_cands:
        c["market_regime"] = mkt.get(c["date"], "")
    by_key = {_key(c): c for c in all_cands}
    built = {RESULTS: build_classification(all_cands, cfg, cfg.get("structure_override")),
             PROXY: build_classification(all_cands, cfg, None)}

    targets = {tab: classify_sets(tab, rows, cache, built[tab])
               for tab, rows in stored.items()}
    dates = sorted({k[0].isoformat() for t in targets.values() for k in t if k[0]})
    date_set = set(dates)

    # Every stored row on a target date — what `--redo --date` will touch.
    touched = {tab: [r for r in rows if str(r.get("signal_date", ""))[:10] in date_set]
               for tab, rows in stored.items()}
    cands_on = [c for c in all_cands if c["date"] in date_set]
    new_results = reprice_results([dict(c) for c in cands_on], cfg)
    results_keys = {_row_key(r) for r in stored[RESULTS]}
    proxy_keys = {_row_key(r) for r in stored[PROXY]}
    # The proxy re-evaluates the plays the RESULTS redo leaves untested.
    now_tested = {k for k, v in new_results.items() if v["status"] == "priced"}
    proxy_cands = [dict(c) for c in cands_on if _key(c) not in now_tested]
    new_proxy = reprice_proxy(proxy_cands, cfg)

    report = []
    for tab, rows in touched.items():
        new = new_results if tab == RESULTS else new_proxy
        for r in rows:
            k = _row_key(r)
            t = targets[tab].get(k)
            n = new.get(k)
            if n is None and tab == PROXY and k in now_tested:
                n = {"status": "moves_to_results", "legs": new_results[k]["legs"],
                     "detail": "priced by the results redo; this proxy row is not "
                               "replaced by proxy --redo and must be deleted by hand"}
            elif n is None:
                n = {"status": "no_candidate" if k not in by_key else "not_evaluated",
                     "legs": []}
            res = n.get("res") or {}
            sig = _date(r.get("signal_date"))
            check_legs = list(parse_legs(r.get("legs", "")) or []) + list(n.get("legs") or [])
            states = Counter(cache.state(leg, sig) for leg in
                             {(lg.ticker, lg.expiration, lg.strike, lg.opt_type): lg
                              for lg in check_legs}.values()) if sig else Counter()
            cross = ""
            if tab == RESULTS and n["status"] != "priced":
                cross = "leaves_results"
            if tab == PROXY and n["status"] == "moves_to_results":
                cross = "duplicate_on_results"
            sR, nR = _f(r.get("pnl_on_risk_pct")), _f(res.get("pnl_on_risk_pct"))
            moved = not (n["status"] == "priced" and sR is not None and nR is not None
                         and abs(sR - nR) < 1e-6
                         and str(r.get("exit_reason")) == str(res.get("exit_reason"))
                         and _f(r.get("entry_option_price")) == _f(res.get("entry_option_price")))
            report.append({
                "tab": tab,
                "signal_date": str(r.get("signal_date", ""))[:10],
                "ticker": r.get("ticker", ""),
                "structure": r.get("structure", ""),
                "target_sets": "+".join(t["sets"]) if t else "",
                "prefill_flagged14": bool(
                    t and "prefill" in t["sets"]
                    and (str(r.get("signal_date", ""))[:10],
                         str(r.get("ticker", "")).upper()) in FLAGGED14),
                "stored_created": r.get("created_datetime", ""),
                "stored_entry_source": r.get("entry_source", ""),
                "stored_entry": r.get("entry_option_price", ""),
                "stored_exit_reason": r.get("exit_reason", ""),
                "stored_days_held": r.get("days_held", ""),
                "stored_R": r.get("pnl_on_risk_pct", ""),
                "stored_legs": " | ".join((r.get("legs") or "").splitlines()),
                "new_legs": " | ".join(format_legs(n.get("legs") or []).splitlines()),
                "offline_status": n["status"],
                "new_entry_source": res.get("entry_source", ""),
                "new_entry": res.get("entry_option_price", ""),
                "new_exit_reason": res.get("exit_reason", ""),
                "new_days_held": res.get("days_held", ""),
                "new_R": res.get("pnl_on_risk_pct", ""),
                "moved": moved,
                "legs_missing_cache": states.get("missing", 0),
                "legs_shallow_cache": states.get("shallow", 0),
                "needs_refetch": _needs_refetch(tab, n["status"], states),
                "cross_tab": cross,
                "detail": "; ".join(x for x in ((t or {}).get("note", ""),
                                                n.get("detail", "")) if x),
                "play_prefix": k[2],
            })
    # Plays the results redo newly prices that no tab held before.
    for k, v in new_results.items():
        if v["status"] == "priced" and k not in results_keys:
            c = by_key.get(k, {})
            report.append({
                "tab": RESULTS, "signal_date": k[0].isoformat(), "ticker": k[1],
                "structure": v["res"].get("structure", ""), "target_sets": "",
                "offline_status": "newly_priced",
                "new_entry": v["res"].get("entry_option_price", ""),
                "new_R": v["res"].get("pnl_on_risk_pct", ""),
                "new_legs": " | ".join(format_legs(v["legs"]).splitlines()),
                "cross_tab": "duplicate_on_proxy" if k in proxy_keys else "",
                "detail": "appended by the results redo"
                          + ("; its BacktestProxy row stays unless deleted"
                             if k in proxy_keys else ""),
                "play_prefix": k[2], "moved": True,
                "legs_missing_cache": 0, "legs_shallow_cache": 0, "needs_refetch": False,
                "prefill_flagged14": False,
            } | ({"ticker": c.get("ticker", k[1])} if c else {}))
    meta = {"dates": dates, "targets": targets}
    return report, meta


def _needs_refetch(tab: str, status: str, states: Counter) -> bool:
    """Would the real, networked `--redo` fetch something for this row?

    RESULTS: `history.py` refetches every leg whose cache file is missing or
    starts more than 5 days after the signal, so any such leg makes the offline
    price provisional. PROXY: `_method1` never refetches a shallow file; it
    only probes Barchart when nothing nearby is cached, so a proxy row needs the
    network only when it cannot be priced offline at all.
    """
    if tab == RESULTS:
        return bool(states.get("missing") or states.get("shallow"))
    return status not in ("priced", "moves_to_results")


def redo_plan(report: list[dict]) -> list[str]:
    """The date-bounded `--redo` commands, results first, one line per date."""
    by_tab = defaultdict(set)
    for r in report:
        if r["target_sets"]:
            by_tab[r["tab"]].add(r["signal_date"])
    dates = sorted(by_tab[RESULTS] | by_tab[PROXY])
    cmds = [f"python3 -m scripts.backtest --config config/backtest.yml --date {d} --redo"
            for d in dates]
    cmds += [f"python3 -m scripts.backtest.proxy --config config/backtest.yml --date {d} --redo"
             for d in dates]
    return cmds


def summarise(report: list[dict], meta: dict) -> str:
    lines = []
    tgt = [r for r in report if r["target_sets"]]
    lines.append(f"target rows: {len(tgt)} over {len(meta['dates'])} dates")
    for s in ("prefill", "wrong_strike", "open_fill"):
        rows = [r for r in tgt if s in r["target_sets"].split("+")]
        by_tab = Counter(r["tab"] for r in rows)
        refetch = sum(1 for r in rows if r["needs_refetch"])
        unpriced = sum(1 for r in rows if r["offline_status"] != "priced")
        lines.append(f"  {s:13} {len(rows):3}  ({by_tab.get(RESULTS, 0)} results, "
                     f"{by_tab.get(PROXY, 0)} proxy)  needs_refetch={refetch}  "
                     f"not priced offline={unpriced}")
    overlap = Counter(r["target_sets"] for r in tgt if "+" in r["target_sets"])
    if overlap:
        lines.append(f"  in two sets: {dict(overlap)}")
    lines.append(f"  target rows needing the refetch: {sum(r['needs_refetch'] for r in tgt)}")
    lines.append(f"  target rows not priced offline: "
                 f"{Counter(r['offline_status'] for r in tgt if r['offline_status'] != 'priced')}")
    other = [r for r in report if not r["target_sets"]]
    lines.append(f"collateral rows on the same dates: {len(other)}, "
                 f"moved {sum(1 for r in other if r['moved'])}, "
                 f"cross-tab {Counter(r['cross_tab'] for r in report if r['cross_tab'])}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=REPO,
                    help="checkout holding backtests/to_evaluate + option_history_cache")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.ERROR)
    report, meta = census(args.root)
    out = args.out or (args.root / "backtests" / "study_output"
                       / f"reprice-targets-{date.today().isoformat()}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    report.sort(key=lambda r: (not r["target_sets"], r["tab"], r["signal_date"], r["ticker"]))
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
        w.writeheader()
        for r in report:
            w.writerow({k: r.get(k, "") for k in OUT_FIELDS})
    print(summarise(report, meta))
    plan = redo_plan(report)
    plan_path = out.with_suffix(".redo-plan.txt")
    plan_path.write_text("# NOT RUN. Results first, then proxy; see the module docstring.\n"
                         + "\n".join(plan) + "\n", encoding="utf-8")
    print(f"\nwrote {out} ({len(report)} rows)")
    print(f"wrote {plan_path} ({len(plan)} commands, NOT run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
