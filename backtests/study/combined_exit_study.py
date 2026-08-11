"""Combined exit-mechanism study: real + proxy-priced trades, one exit-rule table.

exit_mechanism_study.py answers "did the production exit rules reproduce
backtests/results.csv" and tunes variants on that REAL set alone. This script
extends the SAME validated replay engine (Trade/replay/calibrate/run_variant —
imported, not reimplemented) to a bigger TUNING SET: real rows plus the
proxy-priced rows from backtests/results_proxy.csv (backtest/proxy.py's
fallback-chain pricing for plays the real backtest never covered).

Proxy rows come in two qualities, tagged at load time:
  tweak — proxy_method == strike_expiry_tweak: legs snapped to the nearest
          LISTED contract with real Barchart history. Same pricing basis as a
          real row (barchart / barchart_open), just a substituted strike/expiry.
  bs    — proxy_method == bs_options_hist: Black-Scholes off a donor contract's
          IV history. Model-priced, not real fills — kept as a SEPARATE
          consistency check, never folded into the tuning-set headline delta.
Proxy rows with no daily_price_csv (skip_reason cases: unsupported/no_strike/
no_expiry/no_history/unpriced, or proxy_method == unevaluable) carry no path to
replay and are excluded up front (counted, not an error).

A proxy row whose (signal_date, ticker, structure) identity already exists in
results.csv is a duplicate of a real trade (the real backtest DID cover it in
a later run) — dropped in favor of the real row.

Calibration gate (same production rules, same replay() as exit_mechanism_study):
  - real rows must reproduce backtests/results.csv's own exit_reason/days_held/
    realized_pnl_pct — a HARD STOP if any row is wrong for a substantive reason.
    One known exception: replaying from the 4-decimal STORED daily_price_csv
    STRING occasionally lands exactly on a rounding tie the archived value
    (computed from the unrounded scrape) doesn't share — same exit_reason/
    days_held, pnl_pct off by <=0.0001. That is a documented precision artifact
    of the CSV round-trip design, not a rule mismatch; it does not hard-stop
    and the row is NOT excluded (every downstream number here comes from
    replay(), never from the archived text, so the tie doesn't propagate).
  - tweak/bs rows are proxy-priced by the SAME exit rules already (proxy.py
    shares config/backtest.yml's simulation:/credit: block), so most should
    reproduce their own stored exit outright; any that don't are excluded from
    every table below and printed — exclusion is the designed handling for a
    proxy row, not an error (bs rows especially: model-priced marks can land
    off a rule boundary the stored run resolved one way and replay resolves
    another).

Reporting, in order:
  1. Global re-baseline — prod vs every variant on REAL rows only (the
     Attempt-12 headline, unchanged from exit_mechanism_study's own table).
  2. Combined tuning-set table — same variants on real+tweak (deduped,
     calibrated), each variant's Δ broken down by provenance (real / tweak-open
     / tweak-close) plus the bs set's Δ computed independently as a
     consistency-only check (never mixed into the tuning-set total).
  3. Per-group tables (--group-by structure,trend,vol,intent,side; default
     all): same variants restricted to each group, own prod baseline, own
     leave-one-out and per-month concentration check, and a WINNER/no-robust-
     winner verdict per group.

Run from the repo root:
  python3 backtests/study/combined_exit_study.py --side debit
  python3 backtests/study/combined_exit_study.py --side credit
  python3 backtests/study/combined_exit_study.py --side debit --group-by structure,intent --min-n 20
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # backtests/ itself (sibling import)

from exit_mechanism_study import (  # noqa: E402
    Trade, replay, calibrate, run_variant, summarize, monthly_delta, flips,
    DEBIT_PROD, CREDIT_PROD, DEBIT_VARIANTS, CREDIT_VARIANTS, _pct, _to_float,
)

REAL_CSV = ROOT / "backtests" / "results.csv"
PROXY_CSV = ROOT / "backtests" / "results_proxy.csv"

# proxy_method -> tag used everywhere below (source/provenance)
ACCEPTED_PROXY_METHODS = {
    "strike_expiry_tweak": "tweak",
    "bs_options_hist": "bs",
}

NEAR_MISS_TOL = 0.0001  # one 4-decimal tick — the CSV round-trip precision tie


# ─── entry-basis / grouping tags ───────────────────────────────────────────────

def _entry_basis(entry_source: str) -> str:
    """'open' (barchart_open), 'close' (plain barchart), else 'bs'."""
    s = entry_source or ""
    if "barchart_open" in s:
        return "open"
    if "barchart" in s:
        return "close"
    return "bs"


def _structure_family(structure: str) -> str:
    if structure in ("bull_call_spread", "bear_put_spread"):
        return "debit_vertical"
    if structure in ("bull_put_spread", "bear_call_spread"):
        return "credit_vertical"
    return "other"


_VOL_RE = re.compile(r"([LMHE]-VOL)")
_INTENT_RE = re.compile(r"\[([^|\]]+)\|([^|\]]+)\|([^|\]]+)\]")


def _trend(market_regime: str) -> str:
    mr = (market_regime or "").strip()
    return (mr.split(" + ")[0].strip() or "?") if mr else "?"


def _vol(market_regime: str) -> str:
    m = _VOL_RE.search(market_regime or "")
    return m.group(1) if m else "?"


def _intent(play: str) -> str:
    m = _INTENT_RE.search(play or "")
    return m.group(2).strip().upper() if m else "?"


GROUP_DIMS = ("side", "structure", "trend", "vol", "intent")


def _group_key(dim: str, t: Trade, side: str) -> str:
    if dim == "side":
        return side
    if dim == "structure":
        return _structure_family(t.structure)
    if dim == "trend":
        return _trend(t.row.get("market_regime", ""))
    if dim == "vol":
        return _vol(t.row.get("market_regime", ""))
    if dim == "intent":
        return _intent(t.row.get("play", ""))
    raise ValueError(f"unknown --group-by dimension: {dim!r} (valid: {GROUP_DIMS})")


# ─── loading / merge ────────────────────────────────────────────────────────────

def load_combined(side: str, load_underlying: bool = False):
    """Real + eligible proxy(tweak/bs) trades for `side`, tagged .source
    ('real'/'tweak'/'bs') and .entry_basis ('open'/'close'/'bs'), deduped
    against real-row identities. Mirrors exit_mechanism_study.load_trades's
    side filter (sign of entry_option_price); prints coverage/dedup lines.
    Returns (real_trades, tweak_trades, bs_trades).
    """
    real_rows = list(csv.DictReader(open(REAL_CSV)))
    proxy_rows = list(csv.DictReader(open(PROXY_CSV)))

    real_trades = []
    for r in real_rows:
        e = _to_float(r.get("entry_option_price"))
        if e is None or not r.get("daily_price_csv"):
            continue
        if (side == "debit") != (e > 0):
            continue
        t = Trade(r, load_underlying=load_underlying)
        t.source, t.entry_basis = "real", _entry_basis(r.get("entry_source"))
        real_trades.append(t)
    real_keys = {(t.signal_date.isoformat(), t.ticker, t.structure) for t in real_trades}

    n_no_path = 0     # unevaluable / unsupported proxy_method / no daily_price_csv
    n_dropped_dup = 0
    n_excluded_assert = 0
    tweak_trades, bs_trades = [], []
    for r in proxy_rows:
        method = r.get("proxy_method", "")
        if method not in ACCEPTED_PROXY_METHODS or not r.get("daily_price_csv"):
            n_no_path += 1
            continue
        e = _to_float(r.get("entry_option_price"))
        if e is None:
            n_no_path += 1
            continue
        if (side == "debit") != (e > 0):
            continue
        key = (r["signal_date"], r["ticker"], r["structure"])
        if key in real_keys:
            n_dropped_dup += 1
            print(f"  DEDUP drop ({ACCEPTED_PROXY_METHODS[method]}): "
                  f"{r['signal_date']} {r['ticker']:5s} {r['structure']}")
            continue
        try:
            t = Trade(r, load_underlying=load_underlying)
        except AssertionError as ex:
            n_excluded_assert += 1
            print(f"  WARN grid assert failed, excluding: "
                  f"{r['signal_date']} {r['ticker']} {r['structure']}: {ex}")
            continue
        t.source, t.entry_basis = ACCEPTED_PROXY_METHODS[method], _entry_basis(r.get("entry_source"))
        (tweak_trades if t.source == "tweak" else bs_trades).append(t)

    for lst in (real_trades, tweak_trades, bs_trades):
        lst.sort(key=lambda t: (t.signal_date, t.ticker))

    print(f"coverage ({side}): {len(proxy_rows)} proxy rows total, {n_no_path} excluded "
          f"(no daily_price_csv / unsupported proxy_method), {n_dropped_dup} dropped as "
          f"real-row duplicates, {n_excluded_assert} excluded (grid assert) → "
          f"{len(tweak_trades)} tweak + {len(bs_trades)} bs eligible")
    return real_trades, tweak_trades, bs_trades


# ─── calibration split (exact match / near-miss / hard fail) ──────────────────

def _rowcheck(t: Trade, prod: dict):
    rep = replay(t, **prod)
    want = (t.row["exit_reason"], int(float(t.row["days_held"])), round(_pct(t.row["realized_pnl_pct"]), 4))
    got = (rep["exit_reason"], rep["days_held"], round(rep["pnl_pct"], 4))
    return want, got


def _is_near_miss(want, got) -> bool:
    return want[0] == got[0] and want[1] == got[1] and abs(want[2] - got[2]) <= NEAR_MISS_TOL + 1e-9


def classify_calibration(trades: list, prod: dict):
    """(ok, near_miss, hard_fail) — near_miss = same exit_reason/days_held,
    pnl_pct off by <= one 4-decimal tick only (see NEAR_MISS_TOL)."""
    ok, near_miss, hard_fail = [], [], []
    for t in trades:
        want, got = _rowcheck(t, prod)
        if want == got:
            ok.append(t)
        elif _is_near_miss(want, got):
            near_miss.append((t, want, got))
        else:
            hard_fail.append((t, want, got))
    return ok, near_miss, hard_fail


def gate_real(trades: list, prod: dict, side: str) -> list:
    """Real rows: exact-match calibration is the ground truth. Hard-stop on any
    substantive mismatch; a pure rounding-tie near-miss is reported and kept
    (see NEAR_MISS_TOL docstring at module top) — every trade is returned."""
    calibrate(trades, prod, f"real/{side}")
    _, near_miss, hard_fail = classify_calibration(trades, prod)
    if hard_fail:
        print(f"  CALIBRATION FAILED (real/{side}): {len(hard_fail)} row(s) mismatch for a "
              f"reason OTHER than the known rounding tie — constants likely out of sync with "
              f"config/backtest.yml. HARD STOP.")
        for t, want, got in hard_fail:
            print(f"    {t.signal_date} {t.ticker:5s} {t.structure:18s} want={want} got={got}")
        sys.exit(1)
    if near_miss:
        print(f"  NOTE: {len(near_miss)} real row(s) matched only to a CSV round-trip rounding "
              f"tie (pnl_pct off by <= {NEAR_MISS_TOL}, same exit_reason/days_held) — kept; "
              f"every table below is computed via replay(), never the archived text.")
    return trades


def gate_proxy(trades: list, prod: dict, side: str, label: str) -> list:
    """Proxy (tweak/bs) rows: ANY non-exact match is excluded from downstream
    tables (the designed handling for proxy-priced rows, not an error)."""
    calibrate(trades, prod, f"{label}/{side}")
    ok, near_miss, hard_fail = classify_calibration(trades, prod)
    excluded = near_miss + hard_fail
    if excluded:
        print(f"  excluding {len(excluded)} {label} row(s) from all tables:")
        for t, want, got in excluded:
            print(f"    {t.signal_date} {t.ticker:5s} {t.structure:18s} want={want} got={got}")
    return ok


# ─── group verdict machinery ───────────────────────────────────────────────────

def _delta_by_month(reps: list, base: list) -> dict:
    by_month = defaultdict(float)
    for r, b in zip(reps, base):
        by_month[r["trade"].signal_date.strftime("%Y-%m")] += r["dollars"] - b["dollars"]
    return dict(by_month)


def _delta_excluding_tweak_close(reps: list, base: list, trades: list) -> float:
    return sum(r["dollars"] - b["dollars"] for r, b, t in zip(reps, base, trades)
               if not (t.source == "tweak" and t.entry_basis == "close"))


def report_group_table(dim: str, trades: list, prod: dict, variants: list, side: str,
                        min_n: int) -> None:
    groups = defaultdict(list)
    for t in trades:
        groups[_group_key(dim, t, side)].append(t)

    print("=" * 100)
    print(f"GROUP-BY {dim} ({side}, tuning set = real+tweak)")
    print("=" * 100)
    for gname in sorted(groups):
        gtrades = groups[gname]
        n = len(gtrades)
        base = run_variant(gtrades, prod)
        if n < min_n:
            print(f"  [{gname}] N={n} — insufficient evidence, report only")
            summarize("    PROD", base, None)
            print()
            continue

        print(f"  [{gname}] N={n}")
        best_name, best_loo = None, float("-inf")
        for name, cfg in variants:
            reps = run_variant(gtrades, cfg)
            base_for_line = base if cfg is not prod else None
            summarize(f"    {name}", reps, base_for_line)
            if cfg is prod:
                print()
                continue
            monthly_delta(name, reps, base)

            deltas = [r["dollars"] - b["dollars"] for r, b in zip(reps, base)]
            d_tot = sum(deltas)
            d_loo = d_tot - max(deltas) if deltas else 0.0
            by_month = _delta_by_month(reps, base)
            max_month = max(by_month.values(), key=abs) if by_month else 0.0
            concentrated = abs(d_tot) > 1e-9 and abs(max_month) / abs(d_tot) > 0.80
            ex_close = _delta_excluding_tweak_close(reps, base, gtrades)
            print(f"      verdict inputs: Δ-LOO=${d_loo:+.0f}  "
                  f"month-concentration={'>80% single month' if concentrated else 'ok'}  "
                  f"Δ ex-tweak(close)=${ex_close:+.0f}")
            if d_loo > best_loo:
                best_loo, best_name = d_loo, name
                best_verdict = d_loo > 0 and not concentrated and ex_close > 0
            print()

        if best_name is None:
            print("    verdict: no robust winner (no variants evaluated)")
        elif best_verdict:
            print(f"    verdict: WINNER — {best_name}  (Δ-LOO=${best_loo:+.0f})")
        else:
            print(f"    verdict: no robust winner (best Δ-LOO=${best_loo:+.0f} — {best_name})")
        print()


# ─── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--side", choices=["debit", "credit"], required=True)
    ap.add_argument("--group-by", default=",".join(GROUP_DIMS),
                    help=f"comma-separated dims from {GROUP_DIMS} (default: all)")
    ap.add_argument("--min-n", type=int, default=15)
    args = ap.parse_args()

    side = args.side
    prod = DEBIT_PROD if side == "debit" else CREDIT_PROD
    variants = DEBIT_VARIANTS if side == "debit" else CREDIT_VARIANTS
    need_underlying = side == "credit"
    dims = [d.strip() for d in args.group_by.split(",") if d.strip()]
    for d in dims:
        if d not in GROUP_DIMS:
            ap.error(f"--group-by: unknown dimension {d!r} (valid: {GROUP_DIMS})")

    print(f"Loading {side} trades from {REAL_CSV.name} + {PROXY_CSV.name} "
          f"(load_underlying={need_underlying})")
    real_trades, tweak_trades, bs_trades = load_combined(side, load_underlying=need_underlying)
    print(f"  real={len(real_trades)}  tweak={len(tweak_trades)}  bs={len(bs_trades)}")

    # SANITY: replaying real rows under prod must reproduce their own stored total.
    stored_total = sum(float(t.row["realized_pnl_abs"]) for t in real_trades)
    prod_reps_real = run_variant(real_trades, prod)
    replay_total = sum(r["dollars"] for r in prod_reps_real)
    ok = abs(replay_total - stored_total) < 0.01
    print(f"SANITY prod replay total ${replay_total:,.2f} vs stored ${stored_total:,.2f}"
          f"  {'OK' if ok else 'MISMATCH'}")
    print()

    # ── calibration gates ──
    print("=" * 100)
    print("CALIBRATION GATES")
    print("=" * 100)
    gate_real(real_trades, prod, side)
    tweak_ok = gate_proxy(tweak_trades, prod, side, "tweak")
    bs_ok = gate_proxy(bs_trades, prod, side, "bs")
    print()

    tuning_set = sorted(real_trades + tweak_ok, key=lambda t: (t.signal_date, t.ticker))
    print(f"Tuning set (real+tweak, calibrated): {len(tuning_set)}   "
          f"bs consistency set (calibrated): {len(bs_ok)}")
    print()

    # ── 1. global re-baseline on REAL rows only ──
    print("=" * 100)
    print(f"1) GLOBAL RE-BASELINE ({side}) — REAL rows only, next_open basis")
    print("=" * 100)
    base_real = run_variant(real_trades, prod)
    for name, cfg in variants:
        reps = run_variant(real_trades, cfg)
        summarize(name, reps, base_real if cfg is not prod else None)
        if cfg is not prod:
            monthly_delta(name, reps, base_real)
            flips(name, reps, base_real)
        print()

    # ── 2. combined tuning-set table ──
    print("=" * 100)
    print(f"2) COMBINED TUNING SET ({side}) — real+tweak, bs Δ shown for consistency only")
    print("=" * 100)
    base_tuning = run_variant(tuning_set, prod)
    base_bs = run_variant(bs_ok, prod) if bs_ok else []
    for name, cfg in variants:
        reps = run_variant(tuning_set, cfg)
        summarize(name, reps, base_tuning if cfg is not prod else None)
        if cfg is not prod:
            real_d = sum(r["dollars"] - b["dollars"] for r, b, t in zip(reps, base_tuning, tuning_set)
                         if t.source == "real")
            tw_open_d = sum(r["dollars"] - b["dollars"] for r, b, t in zip(reps, base_tuning, tuning_set)
                            if t.source == "tweak" and t.entry_basis == "open")
            tw_close_d = sum(r["dollars"] - b["dollars"] for r, b, t in zip(reps, base_tuning, tuning_set)
                             if t.source == "tweak" and t.entry_basis == "close")
            bs_d = 0.0
            if bs_ok:
                bs_reps = run_variant(bs_ok, cfg)
                bs_d = sum(r["dollars"] - b["dollars"] for r, b in zip(bs_reps, base_bs))
            print(f"    Δ split: real=${real_d:+.0f} tweak(open)=${tw_open_d:+.0f} "
                  f"tweak(close)=${tw_close_d:+.0f}   bs Δ=${bs_d:+.0f} (consistency only)")
        print()

    # ── 3. per-group tables ──
    for dim in dims:
        report_group_table(dim, tuning_set, prod, variants, side, args.min_n)


if __name__ == "__main__":
    main()
