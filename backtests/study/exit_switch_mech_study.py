"""
Per-regime EXIT-SWITCH study, conditioned on MECHANICAL regime labels (2026-07-22).

Question: a per-regime exit switch failed leave-one-out (LOO) robustness twice
when keyed on the MODEL's free-text regime label. The hypothesis here is that
exit behaviour depends on the trailing PATH environment, so keying the same
switch on a deterministic mechanical regime label ("mech_regime", a pure
function of SPY/^VIX history as-of the signal-date close) might be stable where
the model-keyed version was not. A clean "still fails LOO" is a fully
acceptable — and valuable — answer (it would close the per-regime exit
question).

This is NOT a new exit-mechanism search. Exit configs are drawn ONLY from the
frozen grid already validated by backtests/study/exit_mechanism_study.py, whose
replay engine (Trade / replay / calibrate) is IMPORTED, not reimplemented.

--- Scope note (important) -------------------------------------------------
The pre-registered switch modifies ONLY the DEBIT side (see CELL_VARIANTS):
BEAR+{H,E}-VOL -> debit trail .50/.50 (credit kept PROD); L-VOL -> debit
tef-null (credit PROD already has tef=None, so no-op on credit); {RANGE,BULL}+
E-VOL -> debit pt 1.10. Credit is therefore PROD in ALL THREE configs and
cancels out of every switch-vs-PROD comparison. The study is consequently run
on the DEBIT book only. This also cleanly resolves harness validation: the
accumulated BacktestResults sheet mixes credit rows generated before AND after
the Attempt-13 credit-stop removal (sl 1x -> null), so no single credit PROD
reproduces the whole credit book — but every DEBIT row reproduces DEBIT_PROD
exactly (see Step 2 output).

--- Data ------------------------------------------------------------------
The replay harness needs daily_price_csv / legs / entry_option_price. The
harness's own results.csv is a stale 5-row artefact and results_proxy.csv is
absent, so combined_exit_study.py cannot be rerun literally; the live priced
book is the exported Sheets under backtests/to_evaluate/ (BacktestResults +
BacktestProxy), which carry the same replay columns. Pooled priced book =
BacktestResults(real) + BacktestProxy(tweak, real-priced) + BacktestProxy(bs,
model-priced), each path-replayable and calibrated to DEBIT_PROD; proxy rows
that do not reproduce DEBIT_PROD are excluded (designed handling), as are
proxy rows duplicating a real-row identity.

Run:
    source .venv/bin/activate
    python3 backtests/study/exit_switch_mech_study.py | tee backtests/exit_switch_mech_study_output.txt

Does NOT modify config/, scripts/, lib/, or existing backtests/*.py. SPY/VIX
is fetched (start 2023-06-01) to backtests/mech_regime/spy_vix_daily_full.csv
if that file is missing; otherwise the cached file is reused.
"""

import bisect
import csv
import re
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # backtests/ (sibling import)

from exit_mechanism_study import Trade, replay, _pct, _to_float  # noqa: E402

# ── production exit profiles (source of truth: config/backtest.yml + Attempt 13) ──
# NOTE: exit_mechanism_study.CREDIT_PROD still carries the pre-Attempt-13 sl=1.00.
# Attempt 13 (2026-07-13, see MEMORY) removed the credit stop -> sl=None. Credit is
# never varied by this switch, but we state the current PROD explicitly for honesty.
DEBIT_PROD = dict(pt=0.90, sl=0.75, trig=None, trail=None, tef=0.75)
CREDIT_PROD = dict(pt=0.65, sl=None, trig=None, trail=None, tef=None)

# ── frozen exit-grid variants keyed per mech/model cell (from DEBIT_VARIANTS) ──
V_TRAIL = {**DEBIT_PROD, "trig": 0.50, "trail": 0.50}          # BEAR + H/E-VOL
V_TEFNULL = {**DEBIT_PROD, "trig": None, "trail": None, "tef": None}  # L-VOL
V_PT110 = {**DEBIT_PROD, "pt": 1.10, "trig": None, "trail": None}     # RANGE/BULL + E-VOL

# cell name -> (predicate on (direction, vol), variant config)
SWITCH_CELLS = ("BEAR_HE", "LVOL", "RB_EVOL")


def cell_of(direction, vol):
    """Map a (direction, vol) label pair to a pre-registered switch cell, or
    'PROD' for everything else. Cells are mutually exclusive by construction."""
    if direction == "BEAR" and vol in ("H-VOL", "E-VOL"):
        return "BEAR_HE"
    if vol == "L-VOL":
        return "LVOL"
    if direction in ("RANGE", "BULL") and vol == "E-VOL":
        return "RB_EVOL"
    return "PROD"


CELL_VARIANT = {"BEAR_HE": V_TRAIL, "LVOL": V_TEFNULL, "RB_EVOL": V_PT110}

POST13C_CUTOFF = pd.Timestamp("2026-07-13")

DATA_DIR = ROOT / "backtests" / "to_evaluate"
AC_PATH = DATA_DIR / "analysis - AnalysisClaude.csv"
BR_PATH = DATA_DIR / "analysis - BacktestResults.csv"
BP_PATH = DATA_DIR / "analysis - BacktestProxy.csv"
SPY_VIX_FULL = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"

NEAR_MISS_TOL = 0.0001


def hdr(t):
    print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)


def sub(t):
    print("\n" + "-" * 90 + f"\n{t}\n" + "-" * 90)


# ════════════════════════════════════════════════════════════════════════════
# SPY/VIX + mechanical labels (FROZEN spec, restated from mech_regime_recut.py)
# ════════════════════════════════════════════════════════════════════════════

def ensure_spy_vix():
    if SPY_VIX_FULL.exists():
        return
    import yfinance as yf
    start, end = "2023-06-01", "2026-07-22"
    end_p = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    spy = yf.download("SPY", start=start, end=end_p, auto_adjust=False, progress=False)
    vix = yf.download("^VIX", start=start, end=end_p, auto_adjust=False, progress=False)

    def gc(df):
        return df["Close"].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
    sc, vc = gc(spy), gc(vix)
    out = pd.DataFrame({"date": pd.to_datetime(sc.index).strftime("%Y-%m-%d"), "spy_close": sc.values})
    vd = pd.DataFrame({"date": pd.to_datetime(vc.index).strftime("%Y-%m-%d"), "vix_close": vc.values})
    out = out.merge(vd, on="date", how="outer").sort_values("date").reset_index(drop=True)
    out.to_csv(SPY_VIX_FULL, index=False)


def compute_mech_table(sma_window=50, ret_window=20, vix_hvol=20.0,
                       vix_evol_level=30.0, vix_evol_pct=0.25):
    """FROZEN spec (mech_regime_recut.py): direction BEAR if SPY<50-SMA AND 20d
    ret<0; BULL if both>0; else RANGE. vol E-VOL if VIX>=30 or 5d VIX chg>=+25%,
    else H-VOL if VIX>=20, else L-VOL. All as-of the row's close (causal)."""
    t = pd.read_csv(SPY_VIX_FULL).dropna(subset=["spy_close"]).sort_values("date").reset_index(drop=True)
    t["date"] = t["date"].astype(str)
    t["sma"] = t["spy_close"].rolling(sma_window, min_periods=sma_window).mean()
    t["ret_n"] = t["spy_close"] / t["spy_close"].shift(ret_window) - 1.0
    t["vix_5ago"] = t["vix_close"].shift(5)
    t["vix_5d_chg"] = t["vix_close"] / t["vix_5ago"] - 1.0

    def direction(r):
        if pd.isna(r["sma"]) or pd.isna(r["ret_n"]):
            return None
        if r["spy_close"] < r["sma"] and r["ret_n"] < 0:
            return "BEAR"
        if r["spy_close"] > r["sma"] and r["ret_n"] > 0:
            return "BULL"
        return "RANGE"

    def vol(r):
        if pd.isna(r["vix_close"]):
            return None
        if r["vix_close"] >= vix_evol_level or (pd.notna(r["vix_5d_chg"]) and r["vix_5d_chg"] >= vix_evol_pct):
            return "E-VOL"
        if r["vix_close"] >= vix_hvol:
            return "H-VOL"
        return "L-VOL"

    t["mech_direction"] = t.apply(direction, axis=1)
    t["mech_vol"] = t.apply(vol, axis=1)
    t["dir_ok"] = t["sma"].notna() & t["ret_n"].notna()
    return t


class MechLabeler:
    """As-of lookup: for signal date D use the most recent trading day <= D."""

    def __init__(self, table):
        self.dates = table["date"].tolist()
        self.dir = dict(zip(table["date"], table["mech_direction"]))
        self.vol = dict(zip(table["date"], table["mech_vol"]))
        self.dir_ok = dict(zip(table["date"], table["dir_ok"]))

    def asof(self, d):
        i = bisect.bisect_right(self.dates, d) - 1
        return self.dates[i] if i >= 0 else None

    def label(self, d):
        """(direction, vol, ok, mapped_trading_date). ok=False -> no 50-SMA lookback."""
        a = self.asof(d)
        if a is None or not self.dir_ok.get(a, False):
            return (None, None, False, a)
        return (self.dir[a], self.vol[a], True, a)


# ── model-label parse (restated from mech_regime_recut.py) ──

def model_direction(regime_str):
    if not isinstance(regime_str, str):
        return None
    for d in ("BULL", "BEAR", "RANGE"):
        if d in regime_str:
            return d
    return None


def model_vol(regime_str):
    if not isinstance(regime_str, str):
        return None
    for v in ("E-VOL", "H-VOL", "L-VOL", "C-VOL"):
        if v in regime_str:
            return v
    return None


# ════════════════════════════════════════════════════════════════════════════
# Load debit trades (real + proxy tweak + proxy bs), calibrate, dedup
# ════════════════════════════════════════════════════════════════════════════

def norm_play(s):
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())[:60]


def _calib(t, prod):
    rp = replay(t, **prod)
    want = (t.row["exit_reason"], int(float(t.row["days_held"])), round(_pct(t.row["realized_pnl_pct"]), 4))
    got = (rp["exit_reason"], rp["days_held"], round(rp["pnl_pct"], 4))
    exact = want == got
    near = (want[0] == got[0] and want[1] == got[1] and abs(want[2] - got[2]) <= NEAR_MISS_TOL + 1e-9)
    return exact, near, want, got


def load_debit_trades():
    """Returns (trades, diag). Each trade tagged .source (real/tweak/bs)."""
    diag = {}

    real = []
    for r in csv.DictReader(open(BR_PATH)):
        e = _to_float(r.get("entry_option_price"))
        if e is None or e <= 0 or not r.get("daily_price_csv"):
            continue
        t = Trade(r)
        t.source = "real"
        real.append(t)
    real_keys = {(t.signal_date.isoformat(), t.ticker, t.structure) for t in real}

    # real-book calibration (the harness-validation gate)
    ok = nm = hard = 0
    hard_rows = []
    stored = rep = 0.0
    for t in real:
        exact, near, want, got = _calib(t, DEBIT_PROD)
        if exact:
            ok += 1
        elif near:
            nm += 1
        else:
            hard += 1
            hard_rows.append((t, want, got))
        stored += float(t.row["realized_pnl_abs"])
        rep += t.dollars(replay(t, **DEBIT_PROD)["pnl_pct"])
    diag["real_calib"] = dict(n=len(real), ok=ok, near=nm, hard=hard, hard_rows=hard_rows,
                              stored=stored, replay=rep)

    # proxy rows
    prox_rows = list(csv.DictReader(open(BP_PATH)))
    tweak, bs = [], []
    n_dup = n_excl = n_nopath = 0
    excl_rows = []
    for r in prox_rows:
        method = r.get("proxy_method", "")
        if method not in ("strike_expiry_tweak", "bs_options_hist") or not r.get("daily_price_csv"):
            n_nopath += 1
            continue
        e = _to_float(r.get("entry_option_price"))
        if e is None or e <= 0:
            continue
        key = (r["signal_date"], r["ticker"], r["structure"])
        if key in real_keys:
            n_dup += 1
            continue
        try:
            t = Trade(r)
        except AssertionError:
            n_excl += 1
            continue
        exact, near, want, got = _calib(t, DEBIT_PROD)
        if not exact:  # proxy: any non-exact match excluded (designed handling)
            n_excl += 1
            excl_rows.append((t, want, got))
            continue
        t.source = "tweak" if method == "strike_expiry_tweak" else "bs"
        (tweak if t.source == "tweak" else bs).append(t)
    diag["proxy"] = dict(n_dup=n_dup, n_excl=n_excl, n_nopath=n_nopath,
                         n_tweak=len(tweak), n_bs=len(bs), excl_rows=excl_rows)

    trades = real + tweak + bs
    trades.sort(key=lambda t: (t.signal_date, t.ticker))
    return trades, diag


# ════════════════════════════════════════════════════════════════════════════
# post-13c flag via AnalysisClaude join (60-char play-prefix)
# ════════════════════════════════════════════════════════════════════════════

def build_post13c_lookup():
    ac = pd.read_csv(AC_PATH)
    ac["created_datetime"] = pd.to_datetime(ac["created_datetime"], errors="coerce")
    ac["join_key"] = (ac["date"].astype(str) + "|" + ac["ticker"].astype(str)
                      + "|" + ac["play"].apply(norm_play))
    ac = ac.sort_values("created_datetime").drop_duplicates(subset="join_key", keep="first")
    return dict(zip(ac["join_key"], ac["created_datetime"]))


# ════════════════════════════════════════════════════════════════════════════
# Enrich trades: labels, cells, precomputed pnl under PROD + each variant
# ════════════════════════════════════════════════════════════════════════════

def enrich(trades, labeler, post13c_lu):
    recs = []
    for t in trades:
        d = t.signal_date.isoformat()
        mdir, mvol, mok, mapped = labeler.label(d)
        pdir = model_direction(t.row.get("market_regime", ""))
        pvol = model_vol(t.row.get("market_regime", ""))
        jk = f"{d}|{t.ticker}|{norm_play(t.row.get('play', ''))}"
        cdt = post13c_lu.get(jk)
        post13c = (cdt >= POST13C_CUTOFF) if pd.notna(cdt) else None

        pnl_prod = replay(t, **DEBIT_PROD)["pnl_pct"]
        pnl_var = {c: replay(t, **CELL_VARIANT[c])["pnl_pct"] for c in SWITCH_CELLS}
        dol_prod = t.dollars(pnl_prod)
        dol_var = {c: t.dollars(pnl_var[c]) for c in SWITCH_CELLS}

        recs.append(dict(
            t=t, date=d, ticker=t.ticker, structure=t.structure, source=t.source,
            mech_dir=mdir, mech_vol=mvol, mech_ok=mok, mech_mapped=mapped,
            mech_cell=cell_of(mdir, mvol) if mok else "PROD",
            model_dir=pdir, model_vol=pvol,
            model_cell=cell_of(pdir, pvol),
            post13c=post13c,
            pnl_prod=pnl_prod, pnl_var=pnl_var, dol_prod=dol_prod, dol_var=dol_var,
        ))
    return recs


def relabel_mech_cell(recs, labeler):
    """Recompute only the mech_cell for a (perturbed) labeler; pnl precomputes
    are exit-config-only and unchanged."""
    for r in recs:
        mdir, mvol, mok, mapped = labeler.label(r["date"])
        r["mech_dir"], r["mech_vol"], r["mech_ok"] = mdir, mvol, mok
        r["mech_cell"] = cell_of(mdir, mvol) if mok else "PROD"


# ── fixed-switch P&L helpers ────────────────────────────────────────────────

def fixed_pnl(r, keying, unit):
    """pnl under the FIXED pre-registered switch for one record."""
    cell = r["mech_cell"] if keying == "mech" else r["model_cell"]
    prod = r["pnl_prod"] if unit == "pct" else r["dol_prod"]
    if cell in SWITCH_CELLS:
        return (r["pnl_var"][cell] if unit == "pct" else r["dol_var"][cell])
    return prod


def prod_pnl(r, unit):
    return r["pnl_prod"] if unit == "pct" else r["dol_prod"]


# ════════════════════════════════════════════════════════════════════════════
# Reporting
# ════════════════════════════════════════════════════════════════════════════

def global_table(recs, label):
    sub(f"Global three-config totals — {label} (n={len(recs)})")
    print(f"    {'config':16s}  {'total_pnl_pct':>13s}  {'total_$':>11s}  "
          f"{'mean_pnl_pct':>12s}  {'win':>6s}  {'n':>4s}")
    for name, key in [("PROD", None), ("model-switch", "model"), ("mech-switch", "mech")]:
        if key is None:
            pcts = [prod_pnl(r, "pct") for r in recs]
            dols = [prod_pnl(r, "dol") for r in recs]
        else:
            pcts = [fixed_pnl(r, key, "pct") for r in recs]
            dols = [fixed_pnl(r, key, "dol") for r in recs]
        n = len(pcts)
        tp = sum(pcts)
        td = sum(dols)
        mean = tp / n if n else float("nan")
        win = sum(1 for x in pcts if x > 0) / n if n else float("nan")
        print(f"    {name:16s}  {tp:13.4f}  {td:11.0f}  {mean:12.4f}  {win:6.4f}  {n:4d}")


def percell_table(recs, keying, label):
    sub(f"Per-cell PROD vs switch — {keying}-keyed, {label}")
    print(f"    {'cell':14s}  {'n':>4s}  {'mean_prod':>10s}  {'mean_switch':>11s}  "
          f"{'Δmean':>8s}  {'Δtotal_pct':>11s}  {'Δtotal_$':>10s}  {'win_prod':>8s}  {'win_sw':>7s}")
    cellkey = "mech_cell" if keying == "mech" else "model_cell"
    for cell in ("BEAR_HE", "LVOL", "RB_EVOL", "PROD"):
        rows = [r for r in recs if r[cellkey] == cell]
        if not rows:
            continue
        n = len(rows)
        mp = sum(r["pnl_prod"] for r in rows) / n
        if cell in SWITCH_CELLS:
            sw_pct = [r["pnl_var"][cell] for r in rows]
            sw_dol = [r["dol_var"][cell] for r in rows]
        else:
            sw_pct = [r["pnl_prod"] for r in rows]
            sw_dol = [r["dol_prod"] for r in rows]
        ms = sum(sw_pct) / n
        dtot_pct = sum(sw_pct) - sum(r["pnl_prod"] for r in rows)
        dtot_dol = sum(sw_dol) - sum(r["dol_prod"] for r in rows)
        wp = sum(1 for r in rows if r["pnl_prod"] > 0) / n
        ws = sum(1 for x in sw_pct if x > 0) / n
        print(f"    {cell:14s}  {n:4d}  {mp:10.4f}  {ms:11.4f}  {ms-mp:8.4f}  "
              f"{dtot_pct:11.4f}  {dtot_dol:10.0f}  {wp:8.4f}  {ws:7.4f}")


def loo_by_date(recs, keying, unit="pct"):
    """Out-of-fold: for each held-out date, pick each switch cell's config
    (PROD vs its designated variant) by the better TRAINING mean pnl_pct on the
    remaining dates; apply to the held-out date; accumulate switch-minus-PROD."""
    cellkey = "mech_cell" if keying == "mech" else "model_cell"
    dates = sorted({r["date"] for r in recs})
    by_date = {d: [r for r in recs if r["date"] == d] for d in dates}

    # precompute per-cell lists for fast leave-one-out training means
    fold_gains = {}
    for held in dates:
        train = [r for r in recs if r["date"] != held]
        choose = {}
        for cell in SWITCH_CELLS:
            crows = [r for r in train if r[cellkey] == cell]
            if not crows:
                choose[cell] = False
                continue
            mean_prod = sum(r["pnl_prod"] for r in crows) / len(crows)
            mean_var = sum(r["pnl_var"][cell] for r in crows) / len(crows)
            choose[cell] = mean_var > mean_prod
        gain = 0.0
        for r in by_date[held]:
            cell = r[cellkey]
            prod = prod_pnl(r, unit)
            if cell in SWITCH_CELLS and choose[cell]:
                sw = r["pnl_var"][cell] if unit == "pct" else r["dol_var"][cell]
            else:
                sw = prod
            gain += sw - prod
        fold_gains[held] = gain
    return fold_gains


def summarize_folds(fold_gains, label):
    vals = list(fold_gains.values())
    n = len(vals)
    med = statistics.median(vals)
    pos = sum(1 for v in vals if v > 0)
    nonneg = sum(1 for v in vals if v >= 0)
    total = sum(vals)
    print(f"    {label:28s}  dates={n:4d}  median={med:+9.4f}  total={total:+11.4f}  "
          f">0={pos/n:6.2%}  >=0={nonneg/n:6.2%}")
    return dict(n=n, median=med, total=total, pos=pos / n, nonneg=nonneg / n)


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def main():
    ensure_spy_vix()
    labeler = MechLabeler(compute_mech_table())
    post13c_lu = build_post13c_lookup()

    hdr("STEP 1 — DATA & MECH-LABEL COVERAGE")
    trades, diag = load_debit_trades()
    recs = enrich(trades, labeler, post13c_lu)

    rc = diag["real_calib"]
    px = diag["proxy"]
    print(f"Debit priced book: real={rc['n']}  tweak={px['n_tweak']}  bs={px['n_bs']}  "
          f"-> pooled debit trades = {len(recs)}")
    print(f"Proxy exclusions: {px['n_dup']} real-dupes, {px['n_excl']} non-calibrating/grid, "
          f"{px['n_nopath']} no-path/unsupported")
    # do exclusions differ by regime cell? (pre-registration asks)
    from collections import Counter as _C
    excl_cells = _C()
    for t, _w, _g in px["excl_rows"]:
        mdir, mvol, mok, _ = labeler.label(t.signal_date.isoformat())
        excl_cells[cell_of(mdir, mvol) if mok else "PROD"] += 1
    print(f"Excluded proxy rows by mech cell: "
          + ("  ".join(f"{k}={v}" for k, v in excl_cells.most_common()) if excl_cells else "(none)"))

    # mech coverage
    n_unlab = sum(1 for r in recs if not r["mech_ok"])
    print(f"\nMech-label coverage: {len(recs) - n_unlab}/{len(recs)} rows labeled "
          f"({n_unlab} without 50-SMA lookback)")
    nontrading = [(r["date"], r["mech_mapped"]) for r in recs if r["date"] != r["mech_mapped"]]
    nt_dates = sorted({f"{d}->{m}" for d, m in nontrading})
    print(f"Signal dates mapped to a PRIOR trading day (non-trading signal date): "
          f"{len(set(d for d, _ in nontrading))} distinct")
    for s in nt_dates:
        print(f"    {s}")
    if n_unlab:
        for r in recs:
            if not r["mech_ok"]:
                print(f"    UNLABELED: {r['date']} {r['ticker']} (asof {r['mech_mapped']})")

    # cell distribution
    from collections import Counter
    mc = Counter(r["mech_cell"] for r in recs)
    print(f"\nMech-cell distribution (debit): " + "  ".join(f"{k}={v}" for k, v in mc.most_common()))
    modc = Counter(r["model_cell"] for r in recs)
    print(f"Model-cell distribution (debit): " + "  ".join(f"{k}={v}" for k, v in modc.most_common()))

    # ── Step 2: harness validation ──
    hdr("STEP 2 — HARNESS VALIDATION (DEBIT_PROD reproduces the real book)")
    print("combined_exit_study.py cannot be rerun literally: results.csv is a stale 5-row")
    print("artefact and results_proxy.csv is absent. Equivalent validation = its gate_real +")
    print("SANITY check applied to the live BacktestResults book (real debit rows):")
    print(f"    row calibration: {rc['ok']}/{rc['n']} exact, {rc['near']} rounding-tie, {rc['hard']} HARD")
    print(f"    PROD replay total ${rc['replay']:,.2f}  vs stored realized_pnl_abs ${rc['stored']:,.2f}"
          f"   diff ${rc['replay']-rc['stored']:,.2f}")
    if rc["hard"] or abs(rc["replay"] - rc["stored"]) >= 0.01:
        print("\n  *** HARNESS VALIDATION FAILED — STOPPING per pre-registration. ***")
        for t, want, got in rc["hard_rows"]:
            print(f"    HARD {t.signal_date} {t.ticker} {t.structure} want={want} got={got}")
        sys.exit(1)
    print("    -> PASS: every real debit row reproduces DEBIT_PROD; total matches to the cent.")
    if px["excl_rows"]:
        print(f"  ({len(px['excl_rows'])} proxy rows excluded for not reproducing DEBIT_PROD — "
              f"designed proxy handling, not folded into any table.)")

    post13c_recs = [r for r in recs if r["post13c"] is True]
    print(f"\npost-13c debit rows (AC-join): {len(post13c_recs)}  "
          f"(post13c False={sum(1 for r in recs if r['post13c'] is False)}, "
          f"join-miss={sum(1 for r in recs if r['post13c'] is None)})")

    # ── Step 3(a): global three-config + per-cell ──
    hdr("STEP 3(a) — GLOBAL THREE-CONFIG TABLE + PER-CELL (fixed switch)")
    global_table(recs, "POOLED (all debit)")
    global_table(post13c_recs, "POST-13c only")
    percell_table(recs, "mech", "POOLED")
    percell_table(post13c_recs, "mech", "POST-13c")
    percell_table(recs, "model", "POOLED (comparator keying)")

    # ── Step 3(b): LOO by date, mech vs model ──
    hdr("STEP 3(b) — LEAVE-ONE-OUT BY SIGNAL DATE (out-of-fold switch selection)")
    print("Per held-out date, each switch cell picks PROD vs its designated variant by the")
    print("better TRAINING mean pnl_pct on remaining dates; fold-gain = switch - PROD on the")
    print("held-out date. Distribution reported in pnl_pct units (and $).\n")
    results = {}
    for scope_label, scope in [("POOLED", recs), ("POST-13c", post13c_recs)]:
        sub(f"LOO — {scope_label}")
        for keying in ("mech", "model"):
            fg_pct = loo_by_date(scope, keying, "pct")
            fg_dol = loo_by_date(scope, keying, "dol")
            r_pct = summarize_folds(fg_pct, f"{keying}-keyed [pnl_pct]")
            r_dol = summarize_folds(fg_dol, f"{keying}-keyed [$]")
            results[(scope_label, keying)] = dict(pct=r_pct, dol=r_dol, fg_pct=fg_pct)

    # ── Step 3(c): time-split halves (fixed switch) ──
    hdr("STEP 3(c) — TIME-SPLIT AT MEDIAN SIGNAL DATE (fixed switch, pooled)")
    udates = sorted({r["date"] for r in recs})
    med_date = udates[len(udates) // 2]
    print(f"median signal date (of {len(udates)} unique): {med_date}")
    for half_label, pred in [("EARLY (date < median)", lambda d: d < med_date),
                             ("LATE  (date >= median)", lambda d: d >= med_date)]:
        half = [r for r in recs if pred(r["date"])]
        sub(f"{half_label} — n={len(half)}")
        for keying in ("mech", "model"):
            g_pct = sum(fixed_pnl(r, keying, "pct") - prod_pnl(r, "pct") for r in half)
            g_dol = sum(fixed_pnl(r, keying, "dol") - prod_pnl(r, "dol") for r in half)
            print(f"    {keying}-switch vs PROD:  Δpnl_pct={g_pct:+.4f}   Δ$={g_dol:+.0f}")

    # ── Step 3(d): date-clustered vs row-level (fixed mech switch) ──
    hdr("STEP 3(d) — DATE-CLUSTERED vs ROW-LEVEL (fixed mech switch, pooled)")
    per_date_gain = {}
    per_date_meanrow = {}
    for d in udates:
        rows = [r for r in recs if r["date"] == d]
        gains = [fixed_pnl(r, "mech", "pct") - prod_pnl(r, "pct") for r in rows]
        per_date_gain[d] = sum(gains)          # total contribution of the date
        per_date_meanrow[d] = statistics.mean(gains)  # one mean per date (clustered)
    row_gains = [fixed_pnl(r, "mech", "pct") - prod_pnl(r, "pct") for r in recs]
    print(f"    ROW-LEVEL:      n_rows={len(row_gains)}  total Δpnl_pct={sum(row_gains):+.4f}  "
          f"median_row={statistics.median(row_gains):+.4f}")
    dm = list(per_date_meanrow.values())
    print(f"    DATE-CLUSTERED: n_dates={len(dm)}  mean-of-date-means={statistics.mean(dm):+.4f}  "
          f"median-of-date-means={statistics.median(dm):+.4f}  "
          f"dates>0={sum(1 for v in dm if v>0)}/{len(dm)}")
    mar06 = [r for r in recs if r["date"] == "2026-03-06"]
    if mar06:
        g = sum(fixed_pnl(r, "mech", "pct") - prod_pnl(r, "pct") for r in mar06)
        print(f"    FLAG 2026-03-06 (double-analyzed, double-weighted at row level): "
              f"{len(mar06)} debit rows, Δpnl_pct={g:+.4f}")
    else:
        print("    FLAG 2026-03-06: no debit rows in book on this date.")

    # ── Step 3(e): mech-threshold perturbation ──
    hdr("STEP 3(e) — MECH-THRESHOLD PERTURBATION (does mech-switch-vs-PROD sign flip?)")
    perts = {
        "frozen (VIX H=20, SMA=50)": dict(),
        "VIX H-bound=18": dict(vix_hvol=18.0),
        "VIX H-bound=22": dict(vix_hvol=22.0),
        "SMA window=40": dict(sma_window=40),
        "SMA window=60": dict(sma_window=60),
    }
    print(f"    {'config':28s}  {'fixed Δpnl_pct':>14s}  {'fixed Δ$':>10s}  "
          f"{'LOO total_pct':>13s}  {'LOO med':>9s}  {'LOO>=0%':>8s}")
    frozen_fixed_sign = None
    frozen_loo_sign = None
    flips_found = []
    for pname, params in perts.items():
        lab_p = MechLabeler(compute_mech_table(**params))
        relabel_mech_cell(recs, lab_p)
        fixed_pct = sum(fixed_pnl(r, "mech", "pct") - prod_pnl(r, "pct") for r in recs)
        fixed_dol = sum(fixed_pnl(r, "mech", "dol") - prod_pnl(r, "dol") for r in recs)
        fg = loo_by_date(recs, "mech", "pct")
        loo_total = sum(fg.values())
        loo_med = statistics.median(fg.values())
        loo_nonneg = sum(1 for v in fg.values() if v >= 0) / len(fg)
        print(f"    {pname:28s}  {fixed_pct:14.4f}  {fixed_dol:10.0f}  "
              f"{loo_total:13.4f}  {loo_med:9.4f}  {loo_nonneg:8.2%}")
        fs = np.sign(fixed_pct)
        ls = np.sign(loo_total)
        if pname.startswith("frozen"):
            frozen_fixed_sign, frozen_loo_sign = fs, ls
        else:
            if fs != frozen_fixed_sign:
                flips_found.append(f"{pname}: fixed-switch sign flip ({frozen_fixed_sign}->{fs})")
            if ls != frozen_loo_sign:
                flips_found.append(f"{pname}: LOO-total sign flip ({frozen_loo_sign}->{ls})")
    print(f"\n    SIGN FLIPS vs frozen: {flips_found if flips_found else 'NONE'}")
    # restore frozen labels
    relabel_mech_cell(recs, labeler)

    # ── Ship gate ──
    hdr("SHIP-GATE EVALUATION (pre-registered) — MECH-KEYED SWITCH")
    pooled_loo = results[("POOLED", "mech")]["pct"]
    post_loo = results[("POST-13c", "mech")]["pct"]
    early_g = sum(fixed_pnl(r, "mech", "pct") - prod_pnl(r, "pct") for r in recs if r["date"] < med_date)
    late_g = sum(fixed_pnl(r, "mech", "pct") - prod_pnl(r, "pct") for r in recs if r["date"] >= med_date)

    checks = {
        "LOO median > 0 (pooled)": pooled_loo["median"] > 0,
        "LOO >=60% dates non-negative (pooled)": pooled_loo["nonneg"] >= 0.60,
        "LOO total > 0 (pooled)": pooled_loo["total"] > 0,
        "positive in BOTH time halves (fixed switch)": early_g > 0 and late_g > 0,
        "positive post-13c (LOO total > 0)": post_loo["total"] > 0,
        "no sign flip under ANY perturbation": len(flips_found) == 0,
    }
    for k, v in checks.items():
        print(f"    [{'PASS' if v else 'FAIL'}]  {k}")
    print(f"\n    pooled LOO(mech): median={pooled_loo['median']:+.4f}  total={pooled_loo['total']:+.4f}  "
          f"nonneg={pooled_loo['nonneg']:.2%}")
    print(f"    post-13c LOO(mech): median={post_loo['median']:+.4f}  total={post_loo['total']:+.4f}  "
          f"nonneg={post_loo['nonneg']:.2%}")
    print(f"    time halves (fixed mech): early Δ={early_g:+.4f}  late Δ={late_g:+.4f}")
    # model-keyed comparator LOO for the record
    m_pooled = results[("POOLED", "model")]["pct"]
    print(f"    [comparator] model-keyed pooled LOO: median={m_pooled['median']:+.4f}  "
          f"total={m_pooled['total']:+.4f}  nonneg={m_pooled['nonneg']:.2%}")

    verdict = "COMES OFF THE GATE" if all(checks.values()) else "STAYS GATED"
    print(f"\n    VERDICT: mech-keyed per-regime exit switch {verdict}.")

    print("\n" + "=" * 100 + "\nEND OF REPORT\n" + "=" * 100)


if __name__ == "__main__":
    main()
