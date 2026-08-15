"""
Pre-registered backtest evaluation: regime-gap re-read (2026-07-22 snapshot).

Reads the three exported CSVs under backtests/to_evaluate/, builds the pooled
priced book, derives the post-13c flag via a join to AnalysisClaude, and
prints the numeric report specified in the task. No interpretation — numbers
only.
"""

import re
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, mannwhitneyu

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)

# Repo-root-anchored so the study runs from any CWD (it used to depend on
# being launched from the repo root, which broke silently under the runner).
ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = f"{ROOT}/backtests/to_evaluate"
AC_PATH = f"{DATA_DIR}/analysis - AnalysisClaude.csv"
BR_PATH = f"{DATA_DIR}/analysis - BacktestResults.csv"
BP_PATH = f"{DATA_DIR}/analysis - BacktestProxy.csv"

NEW_DATES = [
    "2024-11-01", "2024-11-04", "2024-11-06", "2024-11-07", "2024-12-18",
    "2025-04-03", "2025-05-05", "2025-08-12", "2025-11-20",
    "2026-03-06", "2026-03-12", "2026-03-20", "2026-03-27",
]
POST13C_CUTOFF = pd.Timestamp("2026-07-13")

DEBIT_STRUCTS = {"bull_call_spread", "bear_put_spread", "long_call", "straddle", "strangle"}
CREDIT_STRUCTS = {"bull_put_spread", "bear_call_spread", "short_put"}

NUMERIC_COLS = [
    "realized_pnl_pct", "mfe_pct", "mae_pct", "delta", "dte_entry",
    "iv_spread", "iv_skew", "iv_pct", "oi_confirm_pct", "cpir",
    "score_total", "score_flow", "score_dealer", "score_price",
    "score_vol", "score_catalyst", "price_vector",
]


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


def spearman_report(x, y):
    """Return (n, rho, p) on pairwise-complete rows."""
    mask = x.notna() & y.notna()
    n = int(mask.sum())
    if n < 2:
        return n, np.nan, np.nan
    rho, p = spearmanr(x[mask], y[mask], nan_policy="omit")
    return n, rho, p


def cell_stats(df, mask=None):
    """n, mean realized_pnl_pct, win rate for a (masked) subset."""
    sub = df if mask is None else df[mask]
    r = sub["realized_pnl_pct"].dropna()
    n = int(r.shape[0])
    mean = float(r.mean()) if n else np.nan
    win = float((r > 0).mean()) if n else np.nan
    return n, mean, win


def fmt_cell(label, n, mean, win):
    mean_s = f"{mean:8.4f}" if pd.notna(mean) else "     nan"
    win_s = f"{win:6.4f}" if pd.notna(win) else "   nan"
    print(f"    {label:40s} n={n:5d}  mean={mean_s}  win={win_s}")


def fmt_spearman(label, n, rho, p):
    rho_s = f"{rho:7.4f}" if pd.notna(rho) else "    nan"
    p_s = f"{p:7.4f}" if pd.notna(p) else "    nan"
    print(f"    {label:55s} n={n:5d}  rho={rho_s}  p={p_s}")


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


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

ac = pd.read_csv(AC_PATH)
br = pd.read_csv(BR_PATH)
bp = pd.read_csv(BP_PATH)

ac = coerce_numeric_cols(ac, NUMERIC_COLS)
br = coerce_numeric_cols(br, NUMERIC_COLS)
bp = coerce_numeric_cols(bp, NUMERIC_COLS)

ac["created_datetime"] = pd.to_datetime(ac["created_datetime"], errors="coerce")
br["created_datetime"] = pd.to_datetime(br["created_datetime"], errors="coerce")
bp["created_datetime"] = pd.to_datetime(bp["created_datetime"], errors="coerce")

# ---------------------------------------------------------------------------
# Pooled priced book
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# post13c join: (date == AC.date, ticker, normalized first-60-char play)
# ---------------------------------------------------------------------------

ac_join = ac.copy()
ac_join["join_key"] = ac_join["date"].astype(str) + "|" + ac_join["ticker"].astype(str) + "|" + ac_join["play"].apply(norm_play)
# dedupe: keep the earliest-created AC row per key (stable, avoids merge fan-out)
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
# keep post13c as nullable-boolean-like object (True/False/NaN)

join_coverage_n = int(joined_mask.sum())
join_coverage_total = int(len(pooled))

# fill iv_spread / iv_skew / iv_pct from AC join where native pooled value missing
for native, ac_col in [("iv_spread", "ac_iv_spread"), ("iv_skew", "ac_iv_skew"), ("iv_pct", "ac_iv_pct")]:
    if native not in pooled.columns:
        pooled[native] = np.nan
    pooled[native] = pooled[native].where(pooled[native].notna(), pooled[ac_col])

pooled["price_vector"] = pooled["ac_price_vector"]  # only ever available via join

pooled["abs_delta"] = pooled["delta"].abs()

post13c_true = pooled["post13c"] == True  # noqa: E712 (explicit vs NaN)
post13c_df = pooled[post13c_true].copy()

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

print("REGIME GAP RE-READ — 2026-07-22 snapshot")
print(f"AnalysisClaude rows: {len(ac)}")
print(f"BacktestResults rows: {len(br)}")
print(f"BacktestProxy rows: {len(bp)}  (proxy_method counts: {dict(bp['proxy_method'].value_counts())})")
print(f"Pooled priced book: {len(pooled)}  (real tier: {(pooled['tier']=='real').sum()}, model tier: {(pooled['tier']=='model').sum()})")
print(f"post13c join coverage: {join_coverage_n}/{join_coverage_total} rows joined to an AnalysisClaude row")
print(f"post13c == True: {int(post13c_true.sum())}   post13c == False: {int((pooled['post13c']==False).sum())}   post13c == NaN (join failed): {int(pooled['post13c'].isna().sum())}")

# ---- Section 0: COVERAGE -----------------------------------------------
hdr("0. COVERAGE")
print(f"{'date':12s}  {'AC_rows':>8s}  {'pooled_priced':>14s}  {'unevaluable':>12s}  flag")
for d in NEW_DATES:
    ac_n = int((ac["date"] == d).sum())
    pooled_n = int((pooled["date"] == d).sum())
    bp_date = bp[bp["signal_date"] == d]
    unevaluable_n = int(bp_date["proxy_method"].isin(["unevaluable", "underlying_trend"]).sum())
    flag = ""
    if ac_n == 0:
        flag += " ZERO_ANALYSIS"
    if pooled_n == 0:
        flag += " ZERO_PRICED_BACKTEST"
    print(f"{d:12s}  {ac_n:8d}  {pooled_n:14d}  {unevaluable_n:12d}  {flag}")

# ---- Section 1: QUEUE ITEM A --------------------------------------------
hdr("1. QUEUE ITEM A — score_flow / score_dealer null re-test (post-13c only)")

targets = ["realized_pnl_pct", "mfe_pct", "mae_pct"]
scores = ["score_flow", "score_dealer"]

subhdr("1a. Within side (debit, credit) — post-13c")
for score in scores:
    for side in ["debit", "credit"]:
        sub = post13c_df[post13c_df["side"] == side]
        for tgt in targets:
            n, rho, p = spearman_report(sub[score], sub[tgt])
            fmt_spearman(f"{score} vs {tgt} | side={side}", n, rho, p)

subhdr("1b. Within structure (bull_call_spread, bear_put_spread, bull_put_spread) — post-13c")
for score in scores:
    for struct in ["bull_call_spread", "bear_put_spread", "bull_put_spread"]:
        sub = post13c_df[post13c_df["structure"] == struct]
        for tgt in targets:
            n, rho, p = spearman_report(sub[score], sub[tgt])
            fmt_spearman(f"{score} vs {tgt} | structure={struct}", n, rho, p)

subhdr("1c. score_vol vs realized_pnl_pct within credit — post-13c (context only)")
sub = post13c_df[post13c_df["side"] == "credit"]
n, rho, p = spearman_report(sub["score_vol"], sub["realized_pnl_pct"])
fmt_spearman("score_vol vs realized_pnl_pct | side=credit", n, rho, p)

subhdr("1d. score_dealer vs mae_pct — FULL POOLED BOOK (continuity check vs old -0.15 read)")
n, rho, p = spearman_report(pooled["score_dealer"], pooled["mae_pct"])
fmt_spearman("score_dealer vs mae_pct | all rows", n, rho, p)

# ---- Section 2: BULL_PUT PROVISIONAL RE-READ ----------------------------
hdr("2. BULL_PUT PROVISIONAL RE-READ — real-priced bull_put_spread rows only (tier=='real')")

bp_real = pooled[(pooled["structure"] == "bull_put_spread") & (pooled["tier"] == "real")].copy()
bp_real_post13c = bp_real[bp_real["post13c"] == True]  # noqa: E712

delta_bins = [
    ("<=0.05", lambda d: d <= 0.05),
    ("0.05-0.08", lambda d: (d > 0.05) & (d <= 0.08)),
    ("0.08-0.12", lambda d: (d > 0.08) & (d <= 0.12)),
    ("0.12-0.20", lambda d: (d > 0.12) & (d <= 0.20)),
    (">0.20", lambda d: d > 0.20),
]

subhdr("2a. |delta| bins — all real-priced bull_put_spread rows")
for label, fn in delta_bins:
    mask = fn(bp_real["abs_delta"])
    n, mean, win = cell_stats(bp_real, mask)
    fmt_cell(f"|delta| {label}", n, mean, win)

subhdr("2a. |delta| bins — post-13c only")
for label, fn in delta_bins:
    mask = fn(bp_real_post13c["abs_delta"])
    n, mean, win = cell_stats(bp_real_post13c, mask)
    fmt_cell(f"|delta| {label}", n, mean, win)

dte_bins = [
    ("<=22", lambda d: d <= 22),
    ("22-45", lambda d: (d > 22) & (d <= 45)),
    ("45-59", lambda d: (d > 45) & (d <= 59)),
    ("59-75", lambda d: (d > 59) & (d <= 75)),
    (">75", lambda d: d > 75),
]

subhdr("2b. dte_entry bins — all real-priced bull_put_spread rows")
for label, fn in dte_bins:
    mask = fn(bp_real["dte_entry"])
    n, mean, win = cell_stats(bp_real, mask)
    fmt_cell(f"dte {label}", n, mean, win)

subhdr("2b. dte_entry bins — post-13c only")
for label, fn in dte_bins:
    mask = fn(bp_real_post13c["dte_entry"])
    n, mean, win = cell_stats(bp_real_post13c, mask)
    fmt_cell(f"dte {label}", n, mean, win)

subhdr("2c. Shipped band (0.08<=|delta|<=0.20 AND dte<=59) vs violators")
band_mask_all = (bp_real["abs_delta"] >= 0.08) & (bp_real["abs_delta"] <= 0.20) & (bp_real["dte_entry"] <= 59)
n, mean, win = cell_stats(bp_real, band_mask_all)
fmt_cell("band | all rows", n, mean, win)
n, mean, win = cell_stats(bp_real, ~band_mask_all)
fmt_cell("violators | all rows", n, mean, win)

band_mask_p13 = (bp_real_post13c["abs_delta"] >= 0.08) & (bp_real_post13c["abs_delta"] <= 0.20) & (bp_real_post13c["dte_entry"] <= 59)
n, mean, win = cell_stats(bp_real_post13c, band_mask_p13)
fmt_cell("band | post-13c", n, mean, win)
n, mean, win = cell_stats(bp_real_post13c, ~band_mask_p13)
fmt_cell("violators | post-13c", n, mean, win)

# ---- Section 3: LADDER (score-free) -------------------------------------
hdr("3. LADDER (score-free version)")


def ladder_tier(row):
    structure = row["structure"]
    regime = row["market_regime"] if pd.notna(row["market_regime"]) else ""
    side = row["side"]
    delta = row["abs_delta"]
    dte = row["dte_entry"]

    has_bear = "BEAR" in regime
    has_hvol = "H-VOL" in regime
    has_range = "RANGE" in regime
    has_lvol = "L-VOL" in regime
    has_evol = "E-VOL" in regime

    if structure == "bear_call_spread" or (has_bear and has_hvol) or (side == "credit" and has_range and has_lvol):
        return "VETO"
    if structure == "bull_call_spread" and (has_range or has_evol):
        return "A"
    if structure == "bull_call_spread" or (
        structure == "bull_put_spread" and pd.notna(delta) and pd.notna(dte) and 0.08 <= delta <= 0.20 and dte <= 59
    ):
        return "B"
    return "C"


pooled["ladder_tier"] = pooled.apply(ladder_tier, axis=1)
tier_order = ["A", "B", "C", "VETO"]


def print_ladder_cut(label, df):
    subhdr(label)
    means = {}
    for t in tier_order:
        n, mean, win = cell_stats(df, df["ladder_tier"] == t)
        fmt_cell(f"tier={t}", n, mean, win)
        means[t] = mean
    present_order = [means[t] for t in tier_order if pd.notna(means[t])]
    monotone = all(present_order[i] > present_order[i + 1] for i in range(len(present_order) - 1)) if len(present_order) > 1 else None
    print(f"    A>B>C>VETO monotone in means: {monotone}  (means present: { {t: means[t] for t in tier_order} })")


print_ladder_cut("3a. Pooled (all tiers)", pooled)
print_ladder_cut("3b. Real-priced only (tier=='real')", pooled[pooled["tier"] == "real"])
print_ladder_cut("3c. post-13c only", post13c_df.assign(ladder_tier=post13c_df.apply(ladder_tier, axis=1)))

subhdr("3d. Mann-Whitney A vs B on post-13c realized_pnl_pct")
p13_ladder = post13c_df.copy()
p13_ladder["ladder_tier"] = p13_ladder.apply(ladder_tier, axis=1)
a_vals = p13_ladder.loc[p13_ladder["ladder_tier"] == "A", "realized_pnl_pct"].dropna()
b_vals = p13_ladder.loc[p13_ladder["ladder_tier"] == "B", "realized_pnl_pct"].dropna()
if len(a_vals) >= 1 and len(b_vals) >= 1:
    stat, p = mannwhitneyu(a_vals, b_vals, alternative="two-sided")
    print(f"    n_A={len(a_vals)}  n_B={len(b_vals)}  U={stat:.4f}  p={p:.4f}")
else:
    print(f"    n_A={len(a_vals)}  n_B={len(b_vals)}  insufficient data for Mann-Whitney")

# ---- Section 4: REGIME CELLS --------------------------------------------
hdr("4. REGIME CELLS — post-13c only")

subhdr("4a. Debit rows in BULL + L-VOL regimes")
regime_str = post13c_df["market_regime"].fillna("")
mask = (post13c_df["side"] == "debit") & regime_str.str.contains("BULL") & regime_str.str.contains("L-VOL")
n, mean, win = cell_stats(post13c_df, mask)
fmt_cell("debit AND regime contains BULL+L-VOL", n, mean, win)

subhdr("4b. The 13 new dates' rows within post-13c book")
new_rows = post13c_df[post13c_df["date"].isin(NEW_DATES)].copy()
print(f"    total new-date rows (post-13c): {len(new_rows)}")
for d in NEW_DATES:
    n, mean, win = cell_stats(new_rows, new_rows["date"] == d)
    fmt_cell(f"date={d}", n, mean, win)
n, mean, win = cell_stats(new_rows)
fmt_cell("ALL new-date rows (overall)", n, mean, win)

subhdr("4b-cont. Election-week (2024-11-*) vs Mar-2026 (2026-03-*) vs rest, within new-date rows")
is_election = new_rows["date"].str.startswith("2024-11")
is_mar2026 = new_rows["date"].str.startswith("2026-03")
is_rest = ~is_election & ~is_mar2026
for label, mask in [("election-week 2024-11-*", is_election), ("Mar-2026 2026-03-*", is_mar2026), ("rest", is_rest)]:
    n, mean, win = cell_stats(new_rows, mask)
    fmt_cell(label, n, mean, win)

subhdr("4b-cont. Ladder tier mix within new-date rows")
new_rows["ladder_tier"] = new_rows.apply(ladder_tier, axis=1)
tier_counts = new_rows["ladder_tier"].value_counts()
for t in tier_order:
    cnt = int(tier_counts.get(t, 0))
    pct = cnt / len(new_rows) if len(new_rows) else np.nan
    print(f"    tier={t:5s}  n={cnt:4d}  share={pct:.4f}" if len(new_rows) else f"    tier={t:5s}  n=0")

# ---- Section 5: WATCH ITEMS ---------------------------------------------
hdr("5. WATCH ITEMS")

subhdr("5a. price_vector vs realized/mfe/mae within bull_call_spread — all rows")
sub = pooled[pooled["structure"] == "bull_call_spread"]
for tgt in targets:
    n, rho, p = spearman_report(sub["price_vector"], sub[tgt])
    fmt_spearman(f"price_vector vs {tgt}", n, rho, p)

subhdr("5a. price_vector vs realized/mfe/mae within bull_call_spread — post-13c")
sub = post13c_df[post13c_df["structure"] == "bull_call_spread"]
for tgt in targets:
    n, rho, p = spearman_report(sub["price_vector"], sub[tgt])
    fmt_spearman(f"price_vector vs {tgt}", n, rho, p)

subhdr("5b. post-13c debit |delta| vs realized/mfe/mae")
sub = post13c_df[post13c_df["side"] == "debit"]
for tgt in targets:
    n, rho, p = spearman_report(sub["abs_delta"], sub[tgt])
    fmt_spearman(f"|delta| vs {tgt} | side=debit", n, rho, p)

subhdr("5c. real-priced bull_put iv_skew vs realized — all rows")
sub = bp_real
n, rho, p = spearman_report(sub["iv_skew"], sub["realized_pnl_pct"])
fmt_spearman("iv_skew vs realized_pnl_pct | real-priced bull_put_spread, all", n, rho, p)

subhdr("5c. real-priced bull_put iv_skew vs realized — post-13c")
sub = bp_real_post13c
n, rho, p = spearman_report(sub["iv_skew"], sub["realized_pnl_pct"])
fmt_spearman("iv_skew vs realized_pnl_pct | real-priced bull_put_spread, post-13c", n, rho, p)

subhdr("5d. bear_put_spread x iv_spread vs mae_pct — pooled (continuity check of Tier-C rule)")
sub = pooled[pooled["structure"] == "bear_put_spread"]
n, rho, p = spearman_report(sub["iv_spread"], sub["mae_pct"])
fmt_spearman("iv_spread vs mae_pct | bear_put_spread, pooled", n, rho, p)

print()
print("=" * 100)
print("END OF REPORT")
print("=" * 100)
