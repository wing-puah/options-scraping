"""
Mechanical-regime re-cut of the pooled backtest book (2026-07-22).

Tests whether a deterministic "mech_regime" label (pure function of SPY/VIX
price history at-or-before the signal date) improves on the deployment
ladder's model-free-text regime label. Pre-registered cuts only — see the
task spec for the full pre-registration. This script is self-contained and
rerunnable:

    source .venv/bin/activate
    python3 backtests/study/mech_regime_recut.py | tee backtests/mech_regime_recut_output.txt

Step 0 (book construction, pooling, post-13c join) is reused VERBATIM from
backtests/study/regime_gap_reread.py — see the block clearly marked below.
"""

import re
import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)

DATA_DIR = "backtests/to_evaluate"
AC_PATH = f"{DATA_DIR}/analysis - AnalysisClaude.csv"
BR_PATH = f"{DATA_DIR}/analysis - BacktestResults.csv"
BP_PATH = f"{DATA_DIR}/analysis - BacktestProxy.csv"
SPY_VIX_PATH = "backtests/mech_regime/spy_vix_daily.csv"

POST13C_CUTOFF = pd.Timestamp("2026-07-13")

DEBIT_STRUCTS = {"bull_call_spread", "bear_put_spread", "long_call", "straddle", "strangle"}
CREDIT_STRUCTS = {"bull_put_spread", "bear_call_spread", "short_put"}

NUMERIC_COLS = [
    "realized_pnl_pct", "mfe_pct", "mae_pct", "delta", "dte_entry",
    "iv_spread", "iv_skew", "iv_pct", "oi_confirm_pct", "cpir",
    "score_total", "score_flow", "score_dealer", "score_price",
    "score_vol", "score_catalyst", "price_vector",
]

MAR2026_DATES = ["2026-03-06", "2026-03-12", "2026-03-20", "2026-03-27"]
APR2025_DATES = None  # filled with a date-range predicate below


# ---------------------------------------------------------------------------
# helpers (shared style with regime_gap_reread.py)
# ---------------------------------------------------------------------------

def clean_numeric(series):
    def conv(v):
        if pd.isna(v):
            return np.nan
        if isinstance(v, (int, float, np.integer, np.floating)):
            return float(v)
        s = str(v).strip().replace("%", "").replace(",", "")
        if s == "" or s.lower() in ("nan", "none"):
            return np.nan
        try:
            return float(s)
        except ValueError:
            return np.nan
    return series.apply(conv)


def norm_play(s):
    if pd.isna(s):
        return ""
    s = re.sub(r"\s+", " ", str(s).strip().lower())
    return s[:60]


def coerce_numeric_cols(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = clean_numeric(df[c])
    return df


def side_of(structure):
    if structure in DEBIT_STRUCTS:
        return "debit"
    if structure in CREDIT_STRUCTS:
        return "credit"
    return np.nan


def hdr(title):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def subhdr(title):
    print()
    print("-" * 90)
    print(title)
    print("-" * 90)


def cell_stats(df, mask=None):
    """n, mean realized_pnl_pct, win rate, mean mae_pct for a (masked) subset."""
    sub = df if mask is None else df[mask]
    r = sub["realized_pnl_pct"].dropna()
    n = int(r.shape[0])
    mean = float(r.mean()) if n else np.nan
    total = float(r.sum()) if n else np.nan
    win = float((r > 0).mean()) if n else np.nan
    mae = sub["mae_pct"].dropna()
    mae_mean = float(mae.mean()) if len(mae) else np.nan
    return n, mean, total, win, mae_mean


def fmt_cell(label, n, mean, total, win, mae_mean=None, width=46):
    mean_s = f"{mean:8.4f}" if pd.notna(mean) else "     nan"
    tot_s = f"{total:9.4f}" if pd.notna(total) else "      nan"
    win_s = f"{win:6.4f}" if pd.notna(win) else "   nan"
    line = f"    {label:{width}s} n={n:5d}  mean={mean_s}  total={tot_s}  win={win_s}"
    if mae_mean is not None:
        mae_s = f"{mae_mean:8.4f}" if pd.notna(mae_mean) else "     nan"
        line += f"  mae_mean={mae_s}"
    print(line)


# ===========================================================================
# STEP 0 — book construction (REUSED VERBATIM from backtests/study/regime_gap_reread.py)
# ===========================================================================

ac = pd.read_csv(AC_PATH)
br = pd.read_csv(BR_PATH)
bp = pd.read_csv(BP_PATH)

ac = coerce_numeric_cols(ac, NUMERIC_COLS)
br = coerce_numeric_cols(br, NUMERIC_COLS)
bp = coerce_numeric_cols(bp, NUMERIC_COLS)

ac["created_datetime"] = pd.to_datetime(ac["created_datetime"], errors="coerce")
br["created_datetime"] = pd.to_datetime(br["created_datetime"], errors="coerce")
bp["created_datetime"] = pd.to_datetime(bp["created_datetime"], errors="coerce")

br2 = br.copy()
br2["date"] = br2["signal_date"]
br2["tier"] = "real"
br2["book_source"] = "BacktestResults"

bp_priced = bp[
    bp["proxy_method"].isin(["strike_expiry_tweak", "bs_options_hist"])
    & bp["realized_pnl_pct"].notna()
].copy()
bp_priced["date"] = bp_priced["signal_date"]
bp_priced["tier"] = np.where(bp_priced["proxy_method"] == "strike_expiry_tweak", "real", "model")
bp_priced["book_source"] = "BacktestProxy"

common_cols = sorted(set(br2.columns) & set(bp_priced.columns))
pooled = pd.concat([br2[common_cols], bp_priced[common_cols]], ignore_index=True, sort=False)
pooled["side"] = pooled["structure"].apply(side_of)

# post13c join: (date == AC.date, ticker, normalized first-60-char play)
ac_join = ac.copy()
ac_join["join_key"] = ac_join["date"].astype(str) + "|" + ac_join["ticker"].astype(str) + "|" + ac_join["play"].apply(norm_play)
ac_join = ac_join.sort_values("created_datetime").drop_duplicates(subset="join_key", keep="first")
ac_lookup = ac_join.set_index("join_key")

pooled["join_key"] = pooled["date"].astype(str) + "|" + pooled["ticker"].astype(str) + "|" + pooled["play"].apply(norm_play)

join_cols = {
    "created_datetime": "ac_created_datetime",
    "iv_spread": "ac_iv_spread",
    "iv_skew": "ac_iv_skew",
    "iv_pct": "ac_iv_pct",
    "price_vector": "ac_price_vector",
}
ac_sub = ac_lookup[list(join_cols.keys())].rename(columns=join_cols)

pooled = pooled.merge(ac_sub, left_on="join_key", right_index=True, how="left")

joined_mask = pooled["ac_created_datetime"].notna()
pooled["post13c"] = np.where(
    joined_mask,
    pooled["ac_created_datetime"] >= POST13C_CUTOFF,
    np.nan,
)

join_coverage_n = int(joined_mask.sum())
join_coverage_total = int(len(pooled))

for native, ac_col in [("iv_spread", "ac_iv_spread"), ("iv_skew", "ac_iv_skew"), ("iv_pct", "ac_iv_pct")]:
    if native not in pooled.columns:
        pooled[native] = np.nan
    pooled[native] = pooled[native].where(pooled[native].notna(), pooled[ac_col])

pooled["price_vector"] = pooled["ac_price_vector"]
pooled["abs_delta"] = pooled["delta"].abs()

post13c_true = pooled["post13c"] == True  # noqa: E712
post13c_df = pooled[post13c_true].copy()

# END OF REUSED BLOCK
# ===========================================================================


# ---------------------------------------------------------------------------
# model regime parsing (direction / vol) from market_regime string
# ---------------------------------------------------------------------------

def parse_model_direction(regime_str):
    if pd.isna(regime_str):
        return np.nan
    for d in ["BULL", "BEAR", "RANGE"]:
        if d in regime_str:
            return d
    return np.nan


def parse_model_vol(regime_str):
    if pd.isna(regime_str):
        return np.nan
    for v in ["E-VOL", "H-VOL", "L-VOL", "C-VOL"]:
        if v in regime_str:
            return v
    return np.nan


pooled["model_direction"] = pooled["market_regime"].apply(parse_model_direction)
pooled["model_vol"] = pooled["market_regime"].apply(parse_model_vol)

# how many rows / dates does the double-analyzed 2026-03-06 date contribute?
mar06_n = int((pooled["date"] == "2026-03-06").sum())
mar06_regimes = pooled.loc[pooled["date"] == "2026-03-06", "market_regime"].value_counts()


# ===========================================================================
# STEP 1/2 — mech_regime: pure function of SPY/VIX history at/before D
# ===========================================================================

spy_vix = pd.read_csv(SPY_VIX_PATH)
spy_vix = spy_vix.dropna(subset=["spy_close"]).sort_values("date").reset_index(drop=True)
spy_vix["date"] = spy_vix["date"].astype(str)


def compute_mech_table(df, sma_window=50, ret_window=20, vix_hvol=20.0, vix_evol_level=30.0, vix_evol_pct=0.25):
    """Pure function of trailing SPY/VIX history; returns a date-indexed table
    of mech_direction / mech_vol plus lookback-sufficiency flags."""
    t = df.copy()
    t["sma"] = t["spy_close"].rolling(sma_window, min_periods=sma_window).mean()
    t["ret_n"] = t["spy_close"] / t["spy_close"].shift(ret_window) - 1.0
    t["vix_5ago"] = t["vix_close"].shift(5)
    t["vix_5d_chg"] = t["vix_close"] / t["vix_5ago"] - 1.0

    def direction(row):
        if pd.isna(row["sma"]) or pd.isna(row["ret_n"]):
            return np.nan
        if row["spy_close"] < row["sma"] and row["ret_n"] < 0:
            return "BEAR"
        if row["spy_close"] > row["sma"] and row["ret_n"] > 0:
            return "BULL"
        return "RANGE"

    def vol(row):
        if pd.isna(row["vix_close"]):
            return np.nan
        evol = row["vix_close"] >= vix_evol_level or (pd.notna(row["vix_5d_chg"]) and row["vix_5d_chg"] >= vix_evol_pct)
        if evol:
            return "E-VOL"
        if row["vix_close"] >= vix_hvol:
            return "H-VOL"
        return "L-VOL"

    t["mech_direction"] = t.apply(direction, axis=1)
    t["mech_vol"] = t.apply(vol, axis=1)
    t["mech_dir_ok"] = t["sma"].notna() & t["ret_n"].notna()
    t["mech_vol_ok"] = t["vix_5ago"].notna()  # vol label itself is defined even with NaN 5d-chg (falls back on level only), but flag partial info
    return t.set_index("date")[["spy_close", "vix_close", "sma", "ret_n", "vix_close", "vix_5d_chg",
                                 "mech_direction", "mech_vol", "mech_dir_ok"]]


mech_frozen = compute_mech_table(spy_vix)  # frozen spec: sma=50, ret=20, vix_hvol=20, evol=30/+25%


def attach_mech(pooled_df, mech_table, prefix="mech"):
    out = pooled_df.merge(
        mech_table[["mech_direction", "mech_vol", "mech_dir_ok"]],
        left_on="date", right_index=True, how="left",
    )
    # dates absent from the fetched SPY/VIX trading calendar (e.g. a market-closed
    # date like 2025-01-09, National Day of Mourning) merge to NaN, not False/True.
    out["mech_dir_ok"] = out["mech_dir_ok"].fillna(False).astype(bool)
    if prefix != "mech":
        out = out.rename(columns={"mech_direction": f"{prefix}_direction", "mech_vol": f"{prefix}_vol",
                                   "mech_dir_ok": f"{prefix}_dir_ok"})
    return out


pooled = attach_mech(pooled, mech_frozen)

n_no_lookback = int((~pooled["mech_dir_ok"]).sum())
dates_no_lookback = sorted(pooled.loc[~pooled["mech_dir_ok"], "date"].unique())

# post13c_df was sliced from `pooled` before model_direction/mech_* columns existed;
# re-slice now that all derived columns are attached.
post13c_df = pooled[pooled["post13c"] == True].copy()  # noqa: E712


# ===========================================================================
# REPORT
# ===========================================================================

print("MECHANICAL-REGIME RE-CUT — 2026-07-22 snapshot")
print(f"AnalysisClaude rows: {len(ac)}")
print(f"BacktestResults rows: {len(br)}")
print(f"BacktestProxy rows: {len(bp)}  (proxy_method counts: {dict(bp['proxy_method'].value_counts())})")
print(f"Pooled priced book: {len(pooled)}  (real tier: {(pooled['tier']=='real').sum()}, model tier: {(pooled['tier']=='model').sum()})")
print(f"post13c join coverage: {join_coverage_n}/{join_coverage_total} rows joined to an AnalysisClaude row")
print(f"post13c == True: {int(post13c_true.sum())}   post13c == False: {int((pooled['post13c']==False).sum())}   post13c == NaN (join failed): {int(pooled['post13c'].isna().sum())}")
print(f"unique signal dates in pooled book: {pooled['date'].nunique()}")
print(f"2026-03-06 double-analysis: {mar06_n} rows on this date, distinct model market_regime values: {dict(mar06_regimes)}")
print(f"rows with insufficient SPY lookback for 50-SMA/20d-return as of {SPY_VIX_PATH} fetch window (mech_direction=NaN): {n_no_lookback}")
print(f"  dates affected: {dates_no_lookback}")

# ---------------------------------------------------------------------------
# (a) Agreement matrix
# ---------------------------------------------------------------------------
hdr("(a) AGREEMENT MATRIX — model vs mech regime labels")

subhdr("(a) Direction — ROW level (n={})".format(len(pooled)))
dir_ct_row = pd.crosstab(pooled["model_direction"], pooled["mech_direction"], dropna=False)
print(dir_ct_row)
row_dir_valid = pooled["model_direction"].notna() & pooled["mech_direction"].notna()
row_dir_agree = (pooled.loc[row_dir_valid, "model_direction"] == pooled.loc[row_dir_valid, "mech_direction"]).mean()
print(f"row-level direction agreement rate (n={int(row_dir_valid.sum())}): {row_dir_agree:.4f}")

subhdr("(a) Vol — ROW level (n={})".format(len(pooled)))
vol_ct_row = pd.crosstab(pooled["model_vol"], pooled["mech_vol"], dropna=False)
print(vol_ct_row)
row_vol_valid = pooled["model_vol"].notna() & pooled["mech_vol"].notna()
row_vol_agree = (pooled.loc[row_vol_valid, "model_vol"] == pooled.loc[row_vol_valid, "mech_vol"]).mean()
print(f"row-level vol agreement rate (n={int(row_vol_valid.sum())}): {row_vol_agree:.4f}")

# date-level: unique (date, model_direction/vol) combos vs mech label for that date
# NOTE: 2026-03-06 has 2 distinct model regime reads (double-analysis) -> contributes
# 2 entries to the date-level table below (flagged, not deduped, per pre-registration).
date_level = pooled[["date", "model_direction", "model_vol", "mech_direction", "mech_vol"]].drop_duplicates()
subhdr(f"(a) Direction — DATE level (n={len(date_level)} date-regime combos, incl. 2026-03-06 double-count)")
dir_ct_date = pd.crosstab(date_level["model_direction"], date_level["mech_direction"], dropna=False)
print(dir_ct_date)
date_dir_valid = date_level["model_direction"].notna() & date_level["mech_direction"].notna()
date_dir_agree = (date_level.loc[date_dir_valid, "model_direction"] == date_level.loc[date_dir_valid, "mech_direction"]).mean()
print(f"date-level direction agreement rate (n={int(date_dir_valid.sum())}): {date_dir_agree:.4f}")

subhdr(f"(a) Vol — DATE level (n={len(date_level)} date-regime combos, incl. 2026-03-06 double-count)")
vol_ct_date = pd.crosstab(date_level["model_vol"], date_level["mech_vol"], dropna=False)
print(vol_ct_date)
date_vol_valid = date_level["model_vol"].notna() & date_level["mech_vol"].notna()
date_vol_agree = (date_level.loc[date_vol_valid, "model_vol"] == date_level.loc[date_vol_valid, "mech_vol"]).mean()
print(f"date-level vol agreement rate (n={int(date_vol_valid.sum())}): {date_vol_agree:.4f}")

print()
print(f"OVERALL date-level agreement rate (direction AND vol both match, n={int((date_dir_valid & date_vol_valid).sum())}): "
      f"{((date_level.loc[date_dir_valid & date_vol_valid, 'model_direction'] == date_level.loc[date_dir_valid & date_vol_valid, 'mech_direction']) & (date_level.loc[date_dir_valid & date_vol_valid, 'model_vol'] == date_level.loc[date_dir_valid & date_vol_valid, 'mech_vol'])).mean():.4f}")


# ---------------------------------------------------------------------------
# (b) Veto comparison
# ---------------------------------------------------------------------------

def veto_masks(df, dir_col_model="model_direction", vol_col_model="model_vol",
               dir_col_mech="mech_direction", vol_col_mech="mech_vol"):
    m_bear_hvol = (df[dir_col_model] == "BEAR") & (df[vol_col_model].isin(["H-VOL", "E-VOL"]))
    x_bear_hvol = (df[dir_col_mech] == "BEAR") & (df[vol_col_mech].isin(["H-VOL", "E-VOL"]))
    or_bear_hvol = m_bear_hvol | x_bear_hvol
    return {"model": m_bear_hvol, "mech": x_bear_hvol, "or": or_bear_hvol}


def run_veto_cut(df, label):
    subhdr(label)
    masks = veto_masks(df)
    for name in ["model", "mech", "or"]:
        m = masks[name]
        n, mean, total, win, mae_mean = cell_stats(df, m)
        fmt_cell(f"VETOED under {name}-label veto", n, mean, total, win, mae_mean)
        n2, mean2, total2, win2, mae2 = cell_stats(df, ~m)
        fmt_cell(f"  survivor book under {name}-veto", n2, mean2, total2, win2, mae2)
    return masks


hdr("(b) VETO COMPARISON — direction=BEAR AND vol in {H-VOL,E-VOL}")

subhdr_ctx = "pooled (all tiers)"
masks_pooled = run_veto_cut(pooled, f"(b) {subhdr_ctx}")

subhdr_ctx = "post-13c only"
masks_p13 = run_veto_cut(post13c_df, f"(b) {subhdr_ctx}")

subhdr_ctx = "pooled, tier split: real"
masks_real = run_veto_cut(pooled[pooled["tier"] == "real"], f"(b) {subhdr_ctx}")

subhdr_ctx = "pooled, tier split: model"
masks_model_tier = run_veto_cut(pooled[pooled["tier"] == "model"], f"(b) {subhdr_ctx}")

# Mar-2026 catch table
subhdr("(b) Mar-2026 signal dates — how much realized loss does each veto catch?")
print(f"{'date':12s}  {'n_rows':>7s}  {'total_pnl':>10s}  {'vetoed_model':>13s}  {'vetoed_mech':>12s}  {'vetoed_or':>10s}")
mar_totals = {"model": 0.0, "mech": 0.0, "or": 0.0}
grand_total = 0.0
for d in MAR2026_DATES:
    sub = pooled[pooled["date"] == d]
    masks_d = veto_masks(sub)
    total_pnl = sub["realized_pnl_pct"].sum()
    grand_total += total_pnl
    vals = {}
    for name in ["model", "mech", "or"]:
        m = masks_d[name]
        v = sub.loc[m, "realized_pnl_pct"].sum()
        vals[name] = v
        mar_totals[name] += v
    print(f"{d:12s}  {len(sub):7d}  {total_pnl:10.4f}  {vals['model']:13.4f}  {vals['mech']:12.4f}  {vals['or']:10.4f}")
print(f"{'TOTAL':12s}  {'':7s}  {grand_total:10.4f}  {mar_totals['model']:13.4f}  {mar_totals['mech']:12.4f}  {mar_totals['or']:10.4f}")
if grand_total != 0:
    print(f"  share of Mar-2026 total P&L caught: model={mar_totals['model']/grand_total:.4f}  mech={mar_totals['mech']/grand_total:.4f}  or={mar_totals['or']/grand_total:.4f}")


# ---------------------------------------------------------------------------
# (c) KILL CRITERION cell
# ---------------------------------------------------------------------------
hdr("(c) KILL CRITERION — model direction != BEAR but mech direction == BEAR")

disagree_mask = (pooled["model_direction"] != "BEAR") & (pooled["mech_direction"] == "BEAR") & pooled["model_direction"].notna() & pooled["mech_direction"].notna()
subhdr("(c) Overall direction-disagreement cell (model!=BEAR, mech==BEAR) — any vol")
n, mean, total, win, mae_mean = cell_stats(pooled, disagree_mask)
fmt_cell("model!=BEAR & mech==BEAR (any vol)", n, mean, total, win, mae_mean)

# subset the OR-veto would ACTUALLY newly veto: mech BEAR+H/E-VOL, but NOT model BEAR+H/E-VOL
masks_all = veto_masks(pooled)
newly_vetoed_mask = masks_all["mech"] & ~masks_all["model"]
subhdr("(c) Newly-vetoed-by-OR subset: mech BEAR+H/E-VOL AND NOT model BEAR+H/E-VOL")
n, mean, total, win, mae_mean = cell_stats(pooled, newly_vetoed_mask)
fmt_cell("newly-vetoed-by-OR subset", n, mean, total, win, mae_mean)
verdict = "OR-VETO REJECTED (newly-vetoed subset net-positive)" if (pd.notna(total) and total > 0) else "OR-veto passes this criterion (newly-vetoed subset net-negative or zero)"
print(f"    VERDICT RULE: {verdict}")

subhdr("(c) Apr-2025 (2025-04-01..2025-04-30) breakout within kill-criterion cell (direction-disagreement)")
apr2025_mask = (pooled["date"] >= "2025-04-01") & (pooled["date"] <= "2025-04-30")
n, mean, total, win, mae_mean = cell_stats(pooled, disagree_mask & apr2025_mask)
fmt_cell("Apr-2025 within direction-disagreement cell", n, mean, total, win, mae_mean)

subhdr("(c) Apr-2025 breakout within newly-vetoed-by-OR subset")
n, mean, total, win, mae_mean = cell_stats(pooled, newly_vetoed_mask & apr2025_mask)
fmt_cell("Apr-2025 within newly-vetoed-by-OR subset", n, mean, total, win, mae_mean)


# ---------------------------------------------------------------------------
# (d) Tier A re-cut
# ---------------------------------------------------------------------------
hdr("(d) TIER A RE-CUT — bull_call_spread AND regime in (RANGE or E-VOL)")

is_bcs = pooled["structure"] == "bull_call_spread"
current_a_regime = (pooled["model_direction"] == "RANGE") | (pooled["model_vol"] == "E-VOL")
and_a_regime = current_a_regime & ((pooled["mech_direction"] == "RANGE") | (pooled["mech_vol"] == "E-VOL"))

current_a = is_bcs & current_a_regime
and_a = is_bcs & and_a_regime
demoted = current_a & ~and_a

n_cur, mean_cur, tot_cur, win_cur, mae_cur = cell_stats(pooled, current_a)
n_and, mean_and, tot_and, win_and, mae_and = cell_stats(pooled, and_a)
n_dem, mean_dem, tot_dem, win_dem, mae_dem = cell_stats(pooled, demoted)

fmt_cell("current Tier A (model RANGE/E-VOL)", n_cur, mean_cur, tot_cur, win_cur, mae_cur)
fmt_cell("AND-rule Tier A (model AND mech RANGE/E-VOL)", n_and, mean_and, tot_and, win_and, mae_and)
fmt_cell("demoted (current-A but not AND-A)", n_dem, mean_dem, tot_dem, win_dem, mae_dem)

mean_diff = (mean_and - mean_cur) if (pd.notna(mean_and) and pd.notna(mean_cur)) else np.nan
n_retained_pct = (n_and / n_cur) if n_cur else np.nan
print(f"    mean_AND - mean_current = {mean_diff:.4f}   n retained = {n_and}/{n_cur} = {n_retained_pct:.4f}")
sharpens = pd.notna(mean_diff) and mean_diff >= 0.10
print(f"    AND sharpens mean by >= 0.10: {sharpens}")


# ---------------------------------------------------------------------------
# (e) Ladder replay under three configs
# ---------------------------------------------------------------------------
hdr("(e) LADDER REPLAY — current / hybrid / mech-only")


def ladder_tier_v2(row, config):
    side = row["side"]
    structure = row["structure"]
    delta = row["abs_delta"]
    dte = row["dte_entry"]
    model_dir, model_vol = row["model_direction"], row["model_vol"]
    mech_dir, mech_vol = row["mech_direction"], row["mech_vol"]

    def bhv(d, v):
        return d == "BEAR" and v in ("H-VOL", "E-VOL")

    def rng_or_evol(d, v):
        return d == "RANGE" or v == "E-VOL"

    def crl(d, v):
        return side == "credit" and d == "RANGE" and v == "L-VOL"

    if config == "current":
        veto = structure == "bear_call_spread" or bhv(model_dir, model_vol) or crl(model_dir, model_vol)
        a_ok = rng_or_evol(model_dir, model_vol)
    elif config == "mech":
        veto = structure == "bear_call_spread" or bhv(mech_dir, mech_vol) or crl(mech_dir, mech_vol)
        a_ok = rng_or_evol(mech_dir, mech_vol)
    elif config == "hybrid":
        # OR-veto (BEAR+H/E-VOL from either label) + AND-promote for A; model labels otherwise
        veto = structure == "bear_call_spread" or bhv(model_dir, model_vol) or bhv(mech_dir, mech_vol) or crl(model_dir, model_vol)
        a_ok = rng_or_evol(model_dir, model_vol) and rng_or_evol(mech_dir, mech_vol)
    else:
        raise ValueError(config)

    if veto:
        return "VETO"
    if structure == "bull_call_spread" and a_ok:
        return "A"
    if structure == "bull_call_spread" or (
        structure == "bull_put_spread" and pd.notna(delta) and pd.notna(dte) and 0.08 <= delta <= 0.20 and dte <= 59
    ):
        return "B"
    return "C"


TIER_RANK = {"A": 0, "B": 1, "C": 2}


def replay_top3_per_day(df, config):
    d = df.copy()
    d["ladder_tier"] = d.apply(lambda r: ladder_tier_v2(r, config), axis=1)
    d = d[d["ladder_tier"] != "VETO"].copy()
    d["tier_rank"] = d["ladder_tier"].map(TIER_RANK)
    d["_orig_order"] = np.arange(len(d))
    d = d.sort_values(["date", "tier_rank", "score_total", "_orig_order"], ascending=[True, True, False, True])
    selected = d.groupby("date", group_keys=False).head(3)
    total_pnl = selected["realized_pnl_pct"].sum()
    n = int(selected["realized_pnl_pct"].notna().sum())
    win = float((selected["realized_pnl_pct"] > 0).mean()) if n else np.nan
    return n, total_pnl, win, selected


for scope_label, scope_df in [("pooled", pooled), ("post-13c only", post13c_df)]:
    subhdr(f"(e) {scope_label}")
    for config in ["current", "hybrid", "mech"]:
        n, total_pnl, win, _ = replay_top3_per_day(scope_df, config)
        print(f"    config={config:8s}  n_selected={n:5d}  total_pnl={total_pnl:10.4f}  win_rate={win:.4f}" if n else f"    config={config:8s}  n_selected=0")


# ---------------------------------------------------------------------------
# (f) Threshold perturbation
# ---------------------------------------------------------------------------
hdr("(f) THRESHOLD PERTURBATION")

perturbations = {
    "frozen (VIX H=20, SMA=50)": dict(sma_window=50, vix_hvol=20.0),
    "VIX H-bound=18": dict(sma_window=50, vix_hvol=18.0),
    "VIX H-bound=22": dict(sma_window=50, vix_hvol=22.0),
    "SMA window=40": dict(sma_window=40, vix_hvol=20.0),
    "SMA window=60": dict(sma_window=60, vix_hvol=20.0),
}

perturb_results = {}
for pname, params in perturbations.items():
    mech_p = compute_mech_table(spy_vix, **params)
    pooled_p = attach_mech(pooled.drop(columns=["mech_direction", "mech_vol", "mech_dir_ok"]), mech_p)

    # (b) Mar-2026 catch
    mar_tot_p = {"model": 0.0, "mech": 0.0, "or": 0.0}
    grand_p = 0.0
    for d in MAR2026_DATES:
        sub = pooled_p[pooled_p["date"] == d]
        masks_d = veto_masks(sub)
        grand_p += sub["realized_pnl_pct"].sum()
        for name in ["model", "mech", "or"]:
            mar_tot_p[name] += sub.loc[masks_d[name], "realized_pnl_pct"].sum()

    # (c) newly-vetoed net P&L sign
    masks_p = veto_masks(pooled_p)
    newly_vetoed_p = masks_p["mech"] & ~masks_p["model"]
    newly_vetoed_total_p = pooled_p.loc[newly_vetoed_p, "realized_pnl_pct"].sum()

    # (d) AND-A mean minus current-A mean sign
    is_bcs_p = pooled_p["structure"] == "bull_call_spread"
    cur_a_p = is_bcs_p & ((pooled_p["model_direction"] == "RANGE") | (pooled_p["model_vol"] == "E-VOL"))
    and_a_p = cur_a_p & ((pooled_p["mech_direction"] == "RANGE") | (pooled_p["mech_vol"] == "E-VOL"))
    mean_cur_p = pooled_p.loc[cur_a_p, "realized_pnl_pct"].mean()
    mean_and_p = pooled_p.loc[and_a_p, "realized_pnl_pct"].mean()
    mean_diff_p = mean_and_p - mean_cur_p if pd.notna(mean_and_p) and pd.notna(mean_cur_p) else np.nan

    perturb_results[pname] = dict(
        mar_model=mar_tot_p["model"], mar_mech=mar_tot_p["mech"], mar_or=mar_tot_p["or"], mar_grand=grand_p,
        newly_vetoed_total=newly_vetoed_total_p, newly_vetoed_n=int(newly_vetoed_p.sum()),
        and_minus_cur=mean_diff_p, n_cur_a=int(cur_a_p.sum()), n_and_a=int(and_a_p.sum()),
    )

subhdr("(f) Perturbation table")
print(f"{'config':28s}  {'MarCatch(mech)':>14s}  {'MarCatch(or)':>13s}  {'newlyVeto_total':>15s}  {'newlyVeto_n':>11s}  {'AND-cur_mean':>12s}")
for pname, r in perturb_results.items():
    print(f"{pname:28s}  {r['mar_mech']:14.4f}  {r['mar_or']:13.4f}  {r['newly_vetoed_total']:15.4f}  {r['newly_vetoed_n']:11d}  {r['and_minus_cur']:12.4f}" if pd.notna(r['and_minus_cur']) else
          f"{pname:28s}  {r['mar_mech']:14.4f}  {r['mar_or']:13.4f}  {r['newly_vetoed_total']:15.4f}  {r['newly_vetoed_n']:11d}  {'nan':>12s}")

frozen = perturb_results["frozen (VIX H=20, SMA=50)"]
subhdr("(f) Sign-flip check vs frozen spec")


def sign(x):
    if pd.isna(x):
        return "nan"
    return "+" if x > 0 else ("-" if x < 0 else "0")


for pname, r in perturb_results.items():
    if pname.startswith("frozen"):
        continue
    flips = []
    if sign(r["newly_vetoed_total"]) != sign(frozen["newly_vetoed_total"]):
        flips.append("newly-vetoed net P&L sign")
    if sign(r["and_minus_cur"]) != sign(frozen["and_minus_cur"]):
        flips.append("AND-A minus current-A sign")
    print(f"    {pname:28s}  flips: {flips if flips else 'NONE'}")


# ---------------------------------------------------------------------------
# (g) Time-split
# ---------------------------------------------------------------------------
hdr("(g) TIME-SPLIT — median signal date")

unique_dates_sorted = sorted(pooled["date"].unique())
median_date = unique_dates_sorted[len(unique_dates_sorted) // 2]
print(f"median signal date (of {len(unique_dates_sorted)} unique dates): {median_date}")

early_mask = pooled["date"] < median_date
late_mask = pooled["date"] >= median_date
print(f"early half: {int(early_mask.sum())} rows, {sum(1 for d in unique_dates_sorted if d < median_date)} dates")
print(f"late half:  {int(late_mask.sum())} rows, {sum(1 for d in unique_dates_sorted if d >= median_date)} dates")

for half_label, half_mask in [("EARLY half", early_mask), ("LATE half", late_mask)]:
    subhdr(f"(g) {half_label} — cut (b) survivor book under each veto")
    half_df = pooled[half_mask]
    masks_half = veto_masks(half_df)
    for name in ["model", "mech", "or"]:
        m = masks_half[name]
        n, mean, total, win, mae_mean = cell_stats(half_df, ~m)
        fmt_cell(f"survivor under {name}-veto", n, mean, total, win, mae_mean)

    subhdr(f"(g) {half_label} — cut (c) newly-vetoed-by-OR subset sign")
    masks_all_half = veto_masks(half_df)
    newly_vetoed_half = masks_all_half["mech"] & ~masks_all_half["model"]
    n, mean, total, win, mae_mean = cell_stats(half_df, newly_vetoed_half)
    fmt_cell("newly-vetoed-by-OR subset", n, mean, total, win, mae_mean)
    print(f"    sign: {sign(total)}")

print()
print("=" * 100)
print("END OF REPORT")
print("=" * 100)
