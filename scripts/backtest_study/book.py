"""Pooled cross-structure book loader.

Generalises `load_debit_trades()` from `scripts/backtest_study/exit_switch_mech_study.py`
(ported 2026-08-11) from "debit rows only" to "every structure the analysis
pipeline emits" — every prior study built its own debit-only slice of this
same book, and a future credit-side or all-structure study needs the pooled
version as tracked infrastructure rather than another gitignored one-off.

Sources, in priority order:
  - `BacktestResults` ("real"): rows the real backtest actually priced.
  - `BacktestProxy` ("tweak" / "bs"): rows the real backtest skipped
    (untested plays), backfilled by `scripts/backtest/proxy.py`'s
    fallback chain. `strike_expiry_tweak` rows are REAL-priced (a nearby
    strike/expiry substitution); `bs_options_hist` rows are MODEL-priced
    (Black-Scholes). A proxy row whose `(signal_date, ticker, structure)`
    already exists in the real book is a duplicate and dropped.

`include_bs` defaults to **False**: `bs_options_hist` rows were dropped as
evidence on 2026-08-11 (see MEMORY: attenuating + replay-contaminating —
they are priced FROM the replay model that scores them, which biases any
study that includes them). Pass `include_bs=True` only when a study
specifically needs the larger, noisier book and says why.

--- Calibration gate: a real asymmetry, not an implementation shortcut -----
The replay harness (`scripts/backtest_study/harness.py`) can only be trusted where
it's been checked against a PROD profile that actually governed the stored
row:

  DEBIT — `DEBIT_PROD` (pt=0.90, sl=0.75, tef=0.75, no trail) has been the
  production debit profile since Attempt 10 (2026-07-04) and every debit row
  in `BacktestResults` was generated under it. Real debit rows are always
  kept (the gate is diagnostic: exact / near-rounding-tie / hard mismatch,
  tallied in `diag["debit_calib"]`), but a PROXY debit row is only admitted
  if it reproduces `(exit_reason, days_held, realized_pnl_pct)` EXACTLY —
  a proxy row that doesn't replay to the stored outcome was priced or dated
  in a way the harness can't reconstruct, and including it anyway would
  silently mix un-vetted rows into every downstream mean.

  `require_proxy_calibration=False` opens that gate (measured 2026-08-13).
  The excluded set is NOT what the paragraph above assumes: all 19 non-exact
  `tweak` debit rows carry a stored `exit_reason` of `trailing_stop`, a rule
  REMOVED from `DEBIT_PROD` by Attempt 10 (2026-07-04). They are rows exported
  under a superseded exit config, not rows the harness cannot price — their
  price paths replay fine, they simply disagree with a stored outcome that no
  longer reflects production. Opening the gate is therefore sound ONLY for a
  caller that re-replays every row itself under a current profile and never
  reads the stored `R`/`exit_reason` (`account_sim` does exactly this); a
  caller that consumes stored outcomes must leave the gate shut. Admitted
  rows keep `calibrated=False`, so `calibrated`-keyed logic (e.g. that study's
  G2) still skips them, and the count lands in
  `diag["n_proxy_admitted_non_exact"]`.

  CREDIT — there is no single credit PROD that calibrates the accumulated
  sheet. Attempt 13 (2026-07-13) removed the credit stop (sl 1x -> None);
  `CREDIT_PROD` below is the POST-Attempt-13 profile, but `BacktestResults`
  /`BacktestProxy` contain credit rows written both before and after that
  date, generated under two different stop rules. Gating credit rows against
  `CREDIT_PROD` would incorrectly reject every pre-Attempt-13 row. Credit
  rows are therefore admitted WITHOUT the exact-replay gate — `calibrated`
  is `False` on every credit record, and the count is in
  `diag["n_credit_ungated"]`. This is a real evidence-quality caveat: treat
  credit exit-mechanism numbers from this loader as unvalidated until the
  book is split (or re-run) per credit-stop era.

--- Mechanical regime -------------------------------------------------------
Labelled via the PRODUCTION `lib.mech_regime.MechLabeler` (`.from_csv` +
`.cell()`), not a reimplementation — the spec is frozen (see that module's
docstring) and this loader must not drift from it. `mech_cell` is the string
"PROD" whenever `.cell()` returns None, which covers BOTH "date predates the
50-SMA lookback" and "labelled fine, but the regime doesn't map to a switch
cell" — matching how every prior study's `cell_of(...) if mok else "PROD"`
collapsed the same two cases. If `backtests/mech_regime/spy_vix_daily_full.csv`
is missing, or its last row is older than the book's last signal date, a
warning is printed (stderr) and `diag["mech_table_warning"]` is set — refresh
with `make mech-regime`.

--- What counts as "credit" -------------------------------------------------
`credit` is derived from the SIGN of `entry_option_price` (negative = credit
received), the same signal `exit_mechanism_study.load_trades` uses to split
debit/credit — not a fixed set of structure names, because a handful of
rows (bull_put_spread priced positive, bear_put_spread priced negative) are
already contradictory in the sheet and the sign is what actually drove which
PROD profile priced the row historically.

Run as a module for diagnostics:
    python -m scripts.backtest_study.book --validate
    python -m scripts.backtest_study.book --validate --include-bs
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.mech_regime import MechLabeler  # noqa: E402
from scripts.backtest_study.harness import Trade, _pct, _to_float, replay  # noqa: E402

DEFAULT_RESULTS_CSV = ROOT / "backtests" / "to_evaluate" / "analysis - BacktestResults.csv"
DEFAULT_PROXY_CSV = ROOT / "backtests" / "to_evaluate" / "analysis - BacktestProxy.csv"
DEFAULT_ANALYSIS_CSV = ROOT / "backtests" / "to_evaluate" / "analysis - AnalysisClaude.csv"
MECH_TABLE_CSV = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"

# Production exit profiles (source of truth: config/backtest.yml + Attempt 13,
# see docstring above for the credit-side calibration caveat).
DEBIT_PROD = dict(pt=0.90, sl=0.75, trig=None, trail=None, tef=0.75)
CREDIT_PROD = dict(pt=0.65, sl=None, trig=None, trail=None, tef=None)

NEAR_MISS_TOL = 0.0001

# Ported verbatim from scripts/backtest_study/exit_switch_mech_study.py (2026-08-11): the
# join-key join used to flag rows written after the Attempt-13c prompt change.
POST13C_CUTOFF = pd.Timestamp("2026-07-13")


# --- small ported helpers (verbatim from scripts/backtest_study/exit_switch_mech_study.py
#     and scripts/backtest_study/bear_position_study.py) -----------------------------------

def norm_play(s) -> str:
    """60-char lowercased play prefix, used as the join key against AnalysisClaude."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())[:60]


def model_direction(regime_str):
    """Pull BULL/BEAR/RANGE out of a free-text regime string, or None."""
    if not isinstance(regime_str, str):
        return None
    for d in ("BULL", "BEAR", "RANGE"):
        if d in regime_str:
            return d
    return None


def model_vol(regime_str):
    """Pull E-VOL/H-VOL/L-VOL/C-VOL out of a free-text regime string, or None."""
    if not isinstance(regime_str, str):
        return None
    for v in ("E-VOL", "H-VOL", "L-VOL", "C-VOL"):
        if v in regime_str:
            return v
    return None


def ladder_tier(rec: dict) -> str:
    """VETO / A / B / C per config/deployment-rules.md. Verbatim port of
    `ladder_tier()` from scripts/backtest_study/bear_position_study.py — keyed off the
    MODEL regime (market_regime free text), not the mechanical regime."""
    st, mr = rec["structure"], rec.get("market_regime") or ""
    mdir, mvol = model_direction(mr), model_vol(mr)
    if st == "bear_call_spread":
        return "VETO"
    if mdir == "BEAR" and mvol == "H-VOL":
        return "VETO"
    if st == "bull_call_spread":
        return "A" if (mdir == "RANGE" or mvol == "E-VOL") else "B"
    if st == "bull_put_spread":
        d, dte = rec["delta"], rec["dte"]
        if d is not None and dte is not None and 0.08 <= abs(d) <= 0.20 and dte <= 59:
            return "B"
    return "C"


def _calib(t: Trade, prod: dict) -> tuple[bool, bool]:
    """(exact, near) — does replaying `t` under `prod` reproduce the row's
    stored (exit_reason, days_held, realized_pnl_pct)? Ported from
    exit_switch_mech_study.py's `_calib`."""
    rp = replay(t, **prod)
    want = (t.row["exit_reason"], int(float(t.row["days_held"])),
            round(_pct(t.row["realized_pnl_pct"]), 4))
    got = (rp["exit_reason"], rp["days_held"], round(rp["pnl_pct"], 4))
    exact = want == got
    near = (want[0] == got[0] and want[1] == got[1]
            and abs(want[2] - got[2]) <= NEAR_MISS_TOL + 1e-9)
    return exact, near


# --- AnalysisClaude join (post13c flag + the fields BacktestProxy lacks) -----

def _build_analysis_lookup(analysis_csv: Path) -> dict:
    """join_key -> first-written AnalysisClaude row (pandas Series), for the
    post13c cutoff flag and the columns BacktestProxy doesn't carry
    (price_vector, days_to_earnings; oi_confirm_pct/cpir/iv_spread/iv_skew/
    iv_pct for proxy-sourced rows). Missing file -> empty lookup (every
    dependent field comes back None), not an error — analysis_csv is
    optional infrastructure, not a hard dependency of the book itself."""
    if analysis_csv is None or not Path(analysis_csv).exists():
        return {}
    ac = pd.read_csv(analysis_csv)
    if "play" not in ac.columns or "date" not in ac.columns or "ticker" not in ac.columns:
        return {}
    ac["created_datetime"] = pd.to_datetime(ac.get("created_datetime"), errors="coerce")
    ac["join_key"] = (ac["date"].astype(str) + "|" + ac["ticker"].astype(str)
                      + "|" + ac["play"].apply(norm_play))
    ac = ac.sort_values("created_datetime").drop_duplicates(subset="join_key", keep="first")
    return {row["join_key"]: row for _, row in ac.iterrows()}


def _row_or_ac(row: dict, ac_row, field: str):
    """Prefer the row's own value; BacktestProxy rows don't carry the rollup
    columns (oi_confirm_pct/cpir/iv_spread/iv_skew/iv_pct/score_*) at all, so
    fall back to the AnalysisClaude join for those."""
    v = _to_float(row.get(field))
    if v is not None:
        return v
    if ac_row is not None:
        return _to_float(ac_row.get(field))
    return None


def _ac_only(ac_row, field: str):
    """Fields that exist ONLY on AnalysisClaude (price_vector, days_to_earnings)
    — neither BacktestResults nor BacktestProxy carries them."""
    return _to_float(ac_row.get(field)) if ac_row is not None else None


# --- mechanical-regime table --------------------------------------------------

def _load_mech_labeler(book_last_date: str | None):
    """(labeler | None, warning | None). Missing table -> every row unlabelled
    (mech_cell falls back to "PROD"); table older than the book -> still used
    (MechLabeler.label is as-of, correct for historical dates) but a warning
    is raised since the newest rows may be riding a stale close."""
    if not MECH_TABLE_CSV.exists():
        warning = f"mech-regime table not found at {MECH_TABLE_CSV} — run `make mech-regime`"
        print(f"WARNING: {warning}", file=sys.stderr)
        return None, warning
    lab = MechLabeler.from_csv(MECH_TABLE_CSV)
    warning = None
    if book_last_date is not None and (lab.last_date is None or lab.last_date < book_last_date):
        warning = (f"mech-regime table ends {lab.last_date}, before the book's last date "
                   f"{book_last_date} — run `make mech-regime` to refresh")
        print(f"WARNING: {warning}", file=sys.stderr)
    return lab, warning


# --- record assembly ----------------------------------------------------------

def _build_record(t: Trade, source: str, calibrated: bool, ac_lookup: dict,
                  mech_labeler) -> dict:
    row = t.row
    d = t.signal_date.isoformat()
    jk = f"{d}|{t.ticker}|{norm_play(row.get('play', ''))}"
    ac_row = ac_lookup.get(jk)
    cdt = ac_row.get("created_datetime") if ac_row is not None else None
    post13c = (cdt >= POST13C_CUTOFF) if (cdt is not None and pd.notna(cdt)) else None

    E = _to_float(row.get("pnl_at_cap_pct"))
    R = _to_float(row.get("realized_pnl_pct"))
    is_credit = not (t.entry_net > 0)
    dh = _to_float(row.get("days_held"))
    market_regime = row.get("market_regime") or ""
    regime = row.get("regime") or ""

    if mech_labeler is not None:
        mdir, mvol, mok, _ = mech_labeler.label(d)
        cell = mech_labeler.cell(d)
    else:
        mdir, mvol, mok, cell = None, None, False, None

    rec = dict(
        date=d, month=d[:7], ticker=t.ticker, structure=t.structure,
        source=source, calibrated=calibrated,
        E=E, R=R,
        E_dol=t.dollars(E) if E is not None else None,
        R_dol=t.dollars(R) if R is not None else None,
        delta=_to_float(row.get("delta")),
        dte=_to_float(row.get("dte_entry")),
        iv_entry=_to_float(row.get("iv_entry_pct")),
        iv_spread=_row_or_ac(row, ac_row, "iv_spread"),
        iv_skew=_row_or_ac(row, ac_row, "iv_skew"),
        iv_pct=_row_or_ac(row, ac_row, "iv_pct"),
        oi_confirm_pct=_row_or_ac(row, ac_row, "oi_confirm_pct"),
        cpir=_row_or_ac(row, ac_row, "cpir"),
        mfe=_to_float(row.get("mfe_pct")),
        mae=_to_float(row.get("mae_pct")),
        mfe_day=_to_float(row.get("mfe_day")),
        mae_day=_to_float(row.get("mae_day")),
        exit_reason=row.get("exit_reason") or None,
        days_held=int(dh) if dh is not None else None,
        market_regime=market_regime,
        regime=regime,
        entry_premium_total=_to_float(row.get("entry_premium_total")),
        max_loss_per_contract=_to_float(row.get("max_loss_per_contract")),
        score_total=_row_or_ac(row, ac_row, "score_total"),
        score_flow=_row_or_ac(row, ac_row, "score_flow"),
        score_dealer=_row_or_ac(row, ac_row, "score_dealer"),
        score_price=_row_or_ac(row, ac_row, "score_price"),
        score_vol=_row_or_ac(row, ac_row, "score_vol"),
        score_catalyst=_row_or_ac(row, ac_row, "score_catalyst"),
        price_vector=_ac_only(ac_row, "price_vector"),
        days_to_earnings=_ac_only(ac_row, "days_to_earnings"),
        horizon=row.get("horizon") or "",
        credit=is_credit,
        mech_direction=mdir,
        mech_vol=mvol,
        mech_cell=cell if (mok and cell is not None) else "PROD",
        model_dir=model_direction(market_regime),
        model_vol=model_vol(market_regime),
        stock_dir=model_direction(regime),
        stock_vol=model_vol(regime),
        post13c=post13c,
        t=t,
    )
    rec["tier"] = ladder_tier(rec)
    return rec


# --- main loader ---------------------------------------------------------------

def load_book(results_csv: str | Path | None = None,
             proxy_csv: str | Path | None = None,
             analysis_csv: str | Path | None = None,
             include_bs: bool = False,
             sources: set[str] | None = None,
             require_proxy_calibration: bool = True) -> tuple[list[dict], dict]:
    """Load the pooled real+proxy book across ALL structures.

    Returns (records, diag). `diag["counts_by_source"]` reflects the FULL
    parsed book (real/tweak/bs all counted) before the `include_bs`/`sources`
    filter is applied to the returned `records` — use `len(records)` for the
    actually-returned count.

    `require_proxy_calibration=False` admits proxy debit rows that fail the
    exact-replay gate, with `calibrated=False` and a count in
    `diag["n_proxy_admitted_non_exact"]`. Read the module docstring's
    calibration-gate section before passing it: it is only sound for callers
    that re-replay every row and ignore the stored outcome. Orthogonal to
    `include_bs` — opening this gate does NOT re-admit `bs_options_hist` rows.
    """
    results_csv = Path(results_csv) if results_csv else DEFAULT_RESULTS_CSV
    proxy_csv = Path(proxy_csv) if proxy_csv else DEFAULT_PROXY_CSV
    analysis_csv = Path(analysis_csv) if analysis_csv else DEFAULT_ANALYSIS_CSV

    ac_lookup = _build_analysis_lookup(analysis_csv)

    diag = {
        "counts_by_source": {"real": 0, "tweak": 0, "bs": 0},
        "n_dup_dropped": 0,
        "n_excluded_no_path_or_method": 0,
        "n_trade_construction_failed": 0,
        "n_proxy_excluded_non_exact": 0,
        "n_proxy_admitted_non_exact": 0,
        "n_credit_ungated": 0,
        "require_proxy_calibration": require_proxy_calibration,
        "debit_calib": {"n": 0, "exact": 0, "near": 0, "hard": 0},
        "include_bs": include_bs,
    }

    # -- real book (BacktestResults): admits every structure, any sign --
    real_trades: list[Trade] = []
    real_keys: set[tuple] = set()
    if results_csv.exists():
        for r in csv.DictReader(open(results_csv)):
            e = _to_float(r.get("entry_option_price"))
            if e is None or not r.get("daily_price_csv"):
                diag["n_excluded_no_path_or_method"] += 1
                continue
            try:
                t = Trade(r)
            except (AssertionError, ValueError, KeyError):
                diag["n_trade_construction_failed"] += 1
                continue
            real_trades.append(t)
            real_keys.add((t.signal_date.isoformat(), t.ticker, t.structure))
    else:
        print(f"WARNING: results_csv not found at {results_csv}", file=sys.stderr)

    # -- proxy book (BacktestProxy): dup-dropped against the real book --
    prox_trades: list[tuple[Trade, str]] = []
    if proxy_csv.exists():
        for r in csv.DictReader(open(proxy_csv)):
            method = r.get("proxy_method", "")
            if method not in ("strike_expiry_tweak", "bs_options_hist") or not r.get("daily_price_csv"):
                diag["n_excluded_no_path_or_method"] += 1
                continue
            e = _to_float(r.get("entry_option_price"))
            if e is None:
                diag["n_excluded_no_path_or_method"] += 1
                continue
            key = (r.get("signal_date"), r.get("ticker"), r.get("structure"))
            if key in real_keys:
                diag["n_dup_dropped"] += 1
                continue
            try:
                t = Trade(r)
            except (AssertionError, ValueError, KeyError):
                diag["n_trade_construction_failed"] += 1
                continue
            src = "tweak" if method == "strike_expiry_tweak" else "bs"
            prox_trades.append((t, src))
    else:
        print(f"WARNING: proxy_csv not found at {proxy_csv}", file=sys.stderr)

    all_dates = [t.signal_date.isoformat() for t in real_trades] + \
                [t.signal_date.isoformat() for t, _ in prox_trades]
    book_last_date = max(all_dates) if all_dates else None
    mech_labeler, mech_warning = _load_mech_labeler(book_last_date)
    diag["mech_table_warning"] = mech_warning

    records: list[dict] = []

    for t in real_trades:
        is_credit = not (t.entry_net > 0)
        if is_credit:
            calibrated = False
            diag["n_credit_ungated"] += 1
        else:
            exact, near = _calib(t, DEBIT_PROD)
            calibrated = exact
            diag["debit_calib"]["n"] += 1
            diag["debit_calib"]["exact" if exact else ("near" if near else "hard")] += 1
        diag["counts_by_source"]["real"] += 1
        records.append(_build_record(t, "real", calibrated, ac_lookup, mech_labeler))

    for t, src in prox_trades:
        is_credit = not (t.entry_net > 0)
        if is_credit:
            calibrated = False
            diag["n_credit_ungated"] += 1
        else:
            exact, near = _calib(t, DEBIT_PROD)
            if not exact:
                if require_proxy_calibration:
                    diag["n_proxy_excluded_non_exact"] += 1
                    continue
                diag["n_proxy_admitted_non_exact"] += 1
            calibrated = exact
        diag["counts_by_source"][src] += 1
        records.append(_build_record(t, src, calibrated, ac_lookup, mech_labeler))

    allowed = set(sources) if sources is not None else (
        {"real", "tweak", "bs"} if include_bs else {"real", "tweak"})
    records = [r for r in records if r["source"] in allowed]

    dates = sorted({r["date"] for r in records})
    diag["date_range"] = (dates[0], dates[-1]) if dates else (None, None)
    diag["n_dates"] = len(dates)

    return records, diag


# --- CLI -------------------------------------------------------------------

def _print_validate(records: list[dict], diag: dict) -> None:
    print(f"Pooled book: {len(records)} rows")
    print("By source (returned): " +
          "  ".join(f"{k}={v}" for k, v in sorted(Counter(r["source"] for r in records).items())))
    print("By source (full parse, pre-filter): " +
          "  ".join(f"{k}={v}" for k, v in sorted(diag["counts_by_source"].items())))
    print("By structure: " +
          "  ".join(f"{k}={v}" for k, v in Counter(r["structure"] for r in records).most_common()))
    print("By year: " +
          "  ".join(f"{k}={v}" for k, v in sorted(Counter(r["date"][:4] for r in records).items())))
    print(f"n_dates={diag['n_dates']}  date_range={diag['date_range']}")
    print(f"dup dropped={diag['n_dup_dropped']}  "
          f"excluded (no path/method)={diag['n_excluded_no_path_or_method']}  "
          f"construction failures={diag['n_trade_construction_failed']}")
    dc = diag["debit_calib"]
    print(f"debit calibration: {dc['exact']}/{dc['n']} exact, {dc['near']} near-rounding-tie, "
          f"{dc['hard']} hard")
    print(f"proxy debit rows excluded (non-exact calibration)={diag['n_proxy_excluded_non_exact']}")
    print(f"credit rows admitted UNGATED (calibrated=False)={diag['n_credit_ungated']}")
    if diag.get("mech_table_warning"):
        print(f"WARNING: {diag['mech_table_warning']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate", action="store_true", help="print a diagnostics table")
    ap.add_argument("--include-bs", action="store_true",
                    help="include bs_options_hist (model-priced) proxy rows")
    ap.add_argument("--results-csv", default=None)
    ap.add_argument("--proxy-csv", default=None)
    ap.add_argument("--analysis-csv", default=None)
    args = ap.parse_args()

    records, diag = load_book(args.results_csv, args.proxy_csv, args.analysis_csv,
                              include_bs=args.include_bs)
    if args.validate:
        _print_validate(records, diag)
    else:
        print(f"Loaded {len(records)} rows. Pass --validate for a diagnostics table.")


if __name__ == "__main__":
    main()
