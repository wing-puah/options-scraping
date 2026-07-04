#!/usr/bin/env python3
"""Render meaningful charts from a BacktestResults export.

Reads the BacktestResults CSV (one row per play) and writes:
  · backtest_dashboard.png — P&L vs holding period, win rate, regime, structure…
  · backtest_ev.png        — expected value by strategy × DTE
  · backtest_paths.png     — daily-path analysis (continuous hold curve, profit-
                             target × stop-loss EV sweep, MFE/MAE, exit mix).
                             Only emitted when the new `daily_price_csv` column is
                             present; the script falls back gracefully otherwise.

Usage:
    python3 scripts/chart_backtest.py [--csv PATH] [--out DIR]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

# Trading-day holding horizons sampled from the daily price path (replaces the
# old calendar-day d{N}_* checkpoint columns; the backtest now stores only the
# full per-day path in `daily_price_csv`).
TD_CHECKPOINTS = [1, 3, 5, 10, 21, 42]

# Profit-capture threshold (%) for the first-passage chart. Mirrors the
# backtest's default profit_target (config/backtest.yml: 0.90 = +90%).
TARGET_PCT = 90

# Dollar profit-capture threshold for the occupancy chart's "target" line — the
# fixed-fractional dollar risk unit (config/backtest.yml: portfolio_value ×
# risk_per_trade_pct = 50000 × 0.02 = $1,000), which lines up with what
# profit_target=0.90 realizes on a typical entry premium.
TARGET_DOLLAR = 1000

# muted, print-friendly palette
C_BULL = "#2e7d32"
C_RANGE = "#c62828"
C_LINE = "#1f4e79"
C_MED = "#e08a1e"
C_BAR = "#5b8db8"
GRID = "#dddddd"


def _parse_path(cell) -> list[float]:
    """Split a daily_price_csv cell ('8.0,11.0,,16.0') into floats, dropping
    empty (no-data) days."""
    if not isinstance(cell, str) or not cell.strip():
        return []
    out = []
    for tok in cell.split(","):
        tok = tok.strip()
        if tok:
            try:
                out.append(float(tok))
            except ValueError:
                pass
    return out


def pnl_path(row: pd.Series) -> list[float]:
    """Per-day P&L % path derived from the stored daily price marks vs entry.
    Marks (`daily_price_csv`) and `entry_option_price` are both signed net values
    (negative = credit), so a single formula handles debit and credit positions:
    `(mark − entry) / abs(entry)`. Empty when no daily series is stored."""
    prices = _parse_path(row.get("daily_price_csv"))
    entry = row.get("entry_option_price")
    if not prices or not entry or entry == 0:
        return []
    return [(p - entry) / abs(entry) * 100 for p in prices]


def dollar_pnl_path(row: pd.Series) -> list[float]:
    """Per-day dollar P&L path: pnl_pct / 100 × entry_premium_total."""
    pct_path = pnl_path(row)
    premium = row.get("entry_premium_total")
    if not pct_path or not premium or premium == 0:
        return []
    return [v / 100 * abs(premium) for v in pct_path]


def pnl_at(path: list[float], n: int) -> float:
    """P&L % after holding n trading days, sampled from the daily path. Carries
    the last available mark forward when the path ended before day n."""
    if not path:
        return np.nan
    return path[n - 1] if len(path) >= n else path[-1]


def _regime_label(s: str) -> str | None:
    """Extract BULL/BEAR/RANGE from any regime string."""
    import re
    if not isinstance(s, str) or not s:
        return None
    m = re.search(r"\b(BULL|BEAR|RANGE)\b", s.upper())
    return m.group(1) if m else None


def _parse_pct_col(series: pd.Series) -> pd.Series:
    """Percent columns arrive either as a Sheets-exported display string
    ('27.57%') or a raw decimal fraction (0.2757, from a native pipeline CSV /
    Sheets API read) — same value, two encodings. Normalize both to
    percentage points (27.57) since every chart below plots/annotates this
    column at that scale (PercentFormatter's default xmax=100, `+.0f%`)."""
    s = series.astype(str).str.strip()
    is_str_pct = s.str.endswith("%")
    numeric = pd.to_numeric(s.str.rstrip("%"), errors="coerce")
    return numeric.where(is_str_pct, numeric * 100)


def load(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df["regime_label"] = df["regime"].str.extract(r"^(BULL|BEAR|RANGE)")
    # Structured labels extracted from the free-text regime columns for grouping.
    df["mkt_label"] = df["market_regime"].apply(_regime_label)
    df["play_label"] = df["regime"].apply(_regime_label)
    df["hp_flag"] = df["market_regime"].str.contains("HP", na=False)
    df["regime_aligned"] = df["mkt_label"] == df["play_label"]
    # The backtest writes the authoritative realized exit; all P&L is path-derived.
    df["realized_pnl"] = _parse_pct_col(df["realized_pnl_pct"])
    df["realized_abs"] = pd.to_numeric(df.get("realized_pnl_abs"), errors="coerce")
    df["pnl_path"] = df.apply(pnl_path, axis=1)
    df["dollar_pnl_path"] = df.apply(dollar_pnl_path, axis=1)
    return df


DTE_BUCKETS = [(0, 21, "≤21d"), (21, 45, "22–45d"),
               (45, 90, "46–90d"), (90, 10000, ">90d")]


def dte_bucket(dte: float) -> str:
    for lo, hi, label in DTE_BUCKETS:
        if lo < dte <= hi:
            return label
    return ">90d"


def build_ev(df: pd.DataFrame, out: Path) -> Path:
    """Expected value by strategy, with DTE as the third feature."""
    df = df.copy()
    r = df["realized_pnl"].dropna()
    q1, q3 = r.quantile(0.25), r.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    n_before = df["realized_pnl"].notna().sum()
    df = df[df["realized_pnl"].isna() | df["realized_pnl"].between(lo, hi)]
    n_removed = n_before - df["realized_pnl"].notna().sum()
    df["dte_bucket"] = df["dte_entry"].apply(dte_bucket)
    bucket_order = [b[2] for b in DTE_BUCKETS]

    # rank strategies by sample size for stable ordering
    structs = df["structure"].value_counts().index.tolist()
    struct_colors = {"bull_call_spread": C_BULL, "bear_put_spread": C_RANGE,
                     "bull_put_spread": "#6a1b9a", "long_call": "#00838f"}

    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    excl = f"  ·  {n_removed} outlier(s) removed (IQR)" if n_removed else ""
    fig.suptitle(
        f"Expected Value by Strategy  ·  third feature: days-to-expiry (DTE){excl}",
        fontsize=16, fontweight="bold", y=0.995,
    )

    # ---- A: EV$ per strategy, decomposed into win/loss contributions ---
    ax = axes[0, 0]
    rows = []
    for s in structs:
        sub = df[df["structure"] == s]
        r = sub["realized_abs"].dropna()
        if r.empty:
            continue
        p_win = (r > 0).mean()
        avg_win = r[r > 0].mean() if (r > 0).any() else 0.0
        avg_loss = r[r <= 0].mean() if (r <= 0).any() else 0.0
        win_contrib = p_win * avg_win
        loss_contrib = (1 - p_win) * avg_loss
        rows.append((s, win_contrib, loss_contrib, win_contrib + loss_contrib,
                     len(r), p_win * 100))
    labels = [r[0].replace("_", "\n") for r in rows]
    x = np.arange(len(rows))
    win_c = [r[1] for r in rows]
    loss_c = [r[2] for r in rows]
    ev = [r[3] for r in rows]
    ax.bar(x, win_c, color=C_BULL, label="p(win)·avg win")
    ax.bar(x, loss_c, color=C_RANGE, label="p(loss)·avg loss")
    ax.plot(x, ev, "D", color="black", ms=9, label="EV (net)", zorder=5)
    for xi, r in zip(x, rows):
        ax.annotate(f"EV ${r[3]:+,.0f}\nn={r[4]} · win {r[5]:.0f}%",
                    (xi, r[3]), textcoords="offset points",
                    xytext=(0, 12 if r[3] >= 0 else -28),
                    ha="center", fontsize=8, fontweight="bold")
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Per-trade contribution to EV ($)")
    ax.set_title("A · EV decomposition by strategy (realized exits)",
                 fontweight="bold")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(axis="y", color=GRID)

    # ---- B: EV$ heatmap  strategy × DTE bucket -------------------------
    ax = axes[0, 1]
    piv = df.pivot_table(index="structure", columns="dte_bucket",
                         values="realized_abs", aggfunc="mean")
    cnt = df.pivot_table(index="structure", columns="dte_bucket",
                         values="realized_abs", aggfunc="count")
    piv = piv.reindex(index=structs, columns=bucket_order)
    cnt = cnt.reindex(index=structs, columns=bucket_order)
    vmax = np.nanmax(np.abs(piv.values))
    im = ax.imshow(piv.values, cmap="RdYlGn", vmin=-vmax, vmax=vmax,
                   aspect="auto")
    ax.set_xticks(range(len(bucket_order)))
    ax.set_xticklabels(bucket_order)
    ax.set_yticks(range(len(structs)))
    ax.set_yticklabels(structs, fontsize=8)
    for i in range(len(structs)):
        for j in range(len(bucket_order)):
            v = piv.values[i, j]
            n = cnt.values[i, j]
            if np.isnan(v):
                ax.text(j, i, "—", ha="center", va="center", color="#999")
            else:
                ax.text(j, i, f"${v:+,.0f}\nn={int(n)}", ha="center",
                        va="center", fontsize=8, fontweight="bold",
                        color="black")
    ax.set_title("B · Mean EV $ — strategy × DTE", fontweight="bold")
    ax.set_xlabel("Days to expiry at entry")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="EV ($)")

    # ---- C: bubble — DTE vs realized P&L, colored by strategy ----------
    ax = axes[1, 0]
    for s in structs:
        sub = df[df["structure"] == s].dropna(subset=["realized_abs"])
        if sub.empty:
            continue
        sizes = np.clip(sub["entry_premium_total"] / 4, 15, 600)
        ax.scatter(sub["dte_entry"], sub["realized_abs"], s=sizes,
                   color=struct_colors.get(s, "#555"), alpha=0.6,
                   edgecolor="white", linewidth=0.5, label=s)
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xscale("log")
    ax.set_xticks([2, 5, 10, 21, 45, 90, 200, 500, 955])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("DTE at entry (log scale) — bubble size ∝ premium $")
    ax.set_ylabel("Realized P&L ($)")
    ax.set_title("C · Outcome vs DTE (bubble = position size)",
                 fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(color=GRID)

    # ---- D: dollar EV per trade, strategy × DTE bucket (grouped bar) ---
    ax = axes[1, 1]
    dpiv = df.pivot_table(index="dte_bucket", columns="structure",
                          values="realized_abs", aggfunc="mean")
    dpiv = dpiv.reindex(index=bucket_order, columns=structs)
    x = np.arange(len(bucket_order))
    w = 0.8 / max(len(structs), 1)
    for k, s in enumerate(structs):
        vals = dpiv[s].values
        ax.bar(x + k * w, np.nan_to_num(vals), width=w,
               color=struct_colors.get(s, "#555"), label=s)
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xticks(x + w * (len(structs) - 1) / 2)
    ax.set_xticklabels(bucket_order)
    ax.set_xlabel("Days to expiry at entry")
    ax.set_ylabel("Mean realized $ P&L per trade")
    ax.set_title("D · Dollar EV per trade — DTE × strategy",
                 fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(axis="y", color=GRID)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_ev.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def build(df: pd.DataFrame, out: Path) -> Path:
    df = df.copy()
    # Per-trading-day-checkpoint P&L in dollars, sampled from each play's daily path.
    dollar_fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}")
    cp = {n: df["dollar_pnl_path"].apply(lambda p, _n=n: pnl_at(p, _n)) for n in TD_CHECKPOINTS}

    fig, axes = plt.subplots(3, 2, figsize=(15, 16))
    fig.suptitle(
        f"Options Backtest — {len(df)} plays, "
        f"{df.signal_date.min():%b %Y}–{df.signal_date.max():%b %Y}",
        fontsize=17,
        fontweight="bold",
        y=0.995,
    )

    # ---- A: mean & median P&L $ vs holding horizon ---------------------
    ax = axes[0, 0]
    xs = TD_CHECKPOINTS
    means = [cp[n].mean() for n in xs]
    meds = [cp[n].median() for n in xs]
    ax.axhline(0, color="#999", lw=0.8)
    ax.plot(xs, means, "-o", color=C_LINE, lw=2, label="Mean")
    ax.plot(xs, meds, "--s", color=C_MED, lw=2, label="Median")
    for x, m in zip(xs, means):
        ax.annotate(f"${m:+,.0f}", (x, m), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8, color=C_LINE)
    ax.set_title("A · P&L $ vs holding period (all plays)", fontweight="bold")
    ax.set_xlabel("Trading days held")
    ax.set_ylabel("P&L ($)")
    ax.set_xticks(xs)
    ax.yaxis.set_major_formatter(dollar_fmt)
    ax.legend()
    ax.grid(color=GRID)

    # ---- B: win rate by checkpoint -------------------------------------
    ax = axes[0, 1]
    labels = [f"{n}d" for n in TD_CHECKPOINTS]
    wins = [(cp[n] > 0).mean() * 100 for n in TD_CHECKPOINTS]
    ns = [cp[n].notna().sum() for n in TD_CHECKPOINTS]
    bars = ax.bar(labels, wins, color=C_BAR)
    ax.axhline(50, color="#999", ls="--", lw=1)
    for b, w, n in zip(bars, wins, ns):
        ax.text(b.get_x() + b.get_width() / 2, w + 1, f"{w:.0f}%\nn={n}",
                ha="center", va="bottom", fontsize=8)
    ax.set_title("B · Win rate by holding period", fontweight="bold")
    ax.set_ylabel("% of plays in profit")
    ax.set_ylim(0, max(wins) + 14)
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.grid(axis="y", color=GRID)

    def _cp_means(sub):
        sp = sub["dollar_pnl_path"]
        return [sp.apply(lambda p, _n=n: pnl_at(p, _n)).mean() for n in TD_CHECKPOINTS]

    # ---- C: regime comparison ------------------------------------------
    ax = axes[1, 0]
    ax.axhline(0, color="#999", lw=0.8)
    for label, color in [("BULL", C_BULL), ("RANGE", C_RANGE)]:
        sub = df[df["regime_label"] == label]
        if sub.empty:
            continue
        ax.plot(xs, _cp_means(sub), "-o", color=color, lw=2,
                label=f"{label} (n={len(sub)})")
    ax.set_title("C · Mean P&L $ by regime read", fontweight="bold")
    ax.set_xlabel("Trading days held")
    ax.set_ylabel("Mean P&L ($)")
    ax.set_xticks(xs)
    ax.yaxis.set_major_formatter(dollar_fmt)
    ax.legend()
    ax.grid(color=GRID)

    # ---- D: structure comparison ---------------------------------------
    ax = axes[1, 1]
    ax.axhline(0, color="#999", lw=0.8)
    struct_colors = {"bull_call_spread": C_BULL, "bear_put_spread": C_RANGE,
                     "bull_put_spread": "#6a1b9a", "long_call": "#00838f"}
    for struct, color in struct_colors.items():
        sub = df[df["structure"] == struct]
        if len(sub) < 2:
            continue
        ax.plot(xs, _cp_means(sub), "-o", color=color, lw=2,
                label=f"{struct} (n={len(sub)})")
    ax.set_title("D · Mean P&L $ by structure", fontweight="bold")
    ax.set_xlabel("Trading days held")
    ax.set_ylabel("Mean P&L ($)")
    ax.set_xticks(xs)
    ax.yaxis.set_major_formatter(dollar_fmt)
    ax.legend(fontsize=8)
    ax.grid(color=GRID)

    # ---- E: realized exit P&L $ distribution --------------------------
    ax = axes[2, 0]
    r = df["realized_abs"].dropna()
    # dynamic bins so all plays are visible regardless of scale
    r_lo, r_hi = r.quantile(0.02), r.quantile(0.98)
    bin_step = max(50, round((r_hi - r_lo) / 25 / 50) * 50)
    bins = np.arange(np.floor(r_lo / bin_step) * bin_step,
                     np.ceil(r_hi / bin_step) * bin_step + bin_step,
                     bin_step)
    ax.hist(r, bins=bins, color=C_BAR, edgecolor="white")
    ax.axvline(0, color="#999", lw=1)
    ax.axvline(r.mean(), color=C_MED, lw=2,
               label=f"mean ${r.mean():+,.0f}")
    ax.axvline(r.median(), color=C_LINE, lw=2, ls="--",
               label=f"median ${r.median():+,.0f}")
    win = (r > 0).mean() * 100
    ax.set_title(f"E · Realized exit P&L $  (win {win:.0f}%, n={len(r)})",
                 fontweight="bold")
    ax.set_xlabel("Realized P&L $ (first close, else last open mark)")
    ax.set_ylabel("Plays")
    ax.xaxis.set_major_formatter(dollar_fmt)
    ax.legend()
    ax.grid(axis="y", color=GRID)

    # ---- F: per-ticker mean realized P&L $ -----------------------------
    ax = axes[2, 1]
    by_t = df.groupby("ticker")["realized_abs"].mean().sort_values()
    colors = [C_BULL if v >= 0 else C_RANGE for v in by_t.values]
    ax.barh(by_t.index, by_t.values, color=colors)
    ax.axvline(0, color="#999", lw=0.8)
    ax.set_title("F · Mean realized P&L $ by ticker", fontweight="bold")
    ax.set_xlabel("Mean realized P&L ($)")
    ax.xaxis.set_major_formatter(dollar_fmt)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(axis="x", color=GRID)

    fig.tight_layout(rect=(0, 0, 1, 0.985))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_dashboard.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def _replay(path: list[float], pt: float, sl: float) -> float:
    """Replay one daily P&L path against a (profit_target, stop_loss) rule, both
    in %. First crossing wins; otherwise the last day's mark."""
    for v in path:
        if v >= pt:
            return v
        if v <= -sl:
            return v
    return path[-1] if path else np.nan


def build_paths(df: pd.DataFrame, out: Path) -> Path | None:
    """Charts that only the day-by-day path unlocks: a continuous hold curve, a
    profit-target × stop-loss EV sweep, MFE-vs-MAE, and the exit-reason mix."""
    paths = [p for p in df.get("pnl_path", pd.Series([], dtype=object)) if p]
    if not paths:
        return None

    fig, axes = plt.subplots(3, 2, figsize=(15, 16))
    fig.suptitle("Daily-path analysis — realized exits, excursions, exit tuning",
                 fontsize=16, fontweight="bold", y=0.995)

    dollar_fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}")

    # ---- A: mean P&L $ vs trading days held (continuous), with IQR band -------
    ax = axes[0, 0]
    dpaths_all = [p for p in df["dollar_pnl_path"] if p]
    use_paths = dpaths_all if dpaths_all else paths  # fall back to % if no dollar paths
    use_dollar = bool(dpaths_all)
    maxlen = max(len(p) for p in use_paths)
    horizon = min(maxlen, 63)  # ~3 months of sessions keeps the tail readable
    days = np.arange(1, horizon + 1)
    mean_c, lo_c, hi_c, n_c = [], [], [], []
    for i in range(horizon):
        vals = np.array([p[i] for p in use_paths if len(p) > i])
        mean_c.append(vals.mean())
        lo_c.append(np.percentile(vals, 25))
        hi_c.append(np.percentile(vals, 75))
        n_c.append(len(vals))
    ax.axhline(0, color="#999", lw=0.8)
    ax.fill_between(days, lo_c, hi_c, color=C_BAR, alpha=0.25, label="IQR (25–75%)")
    ax.plot(days, mean_c, "-", color=C_LINE, lw=2, label="Mean P&L")
    peak = int(np.argmax(mean_c))
    peak_label = f"${mean_c[peak]:+,.0f}" if use_dollar else f"{mean_c[peak]:+.0f}%"
    ax.plot(peak + 1, mean_c[peak], "o", color=C_MED, ms=8,
            label=f"peak day {peak + 1} ({peak_label})")
    ax.set_title("A · Mean live P&L $ vs trading days held", fontweight="bold")
    ax.set_xlabel("Trading days since entry")
    ax.set_ylabel("P&L ($)" if use_dollar else "P&L %")
    if use_dollar:
        ax.yaxis.set_major_formatter(dollar_fmt)
    else:
        ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.legend(fontsize=8)
    ax.grid(color=GRID)

    # ---- B: profit-target × stop-loss EV heatmap (path replay) ---------------
    ax = axes[0, 1]
    targets = [25, 50, 75, 100, 150, 200]
    stops = [30, 50, 70, 100]
    ev = np.array([[np.nanmean([_replay(p, pt, sl) for p in paths])
                    for pt in targets] for sl in stops])
    vmax = np.nanmax(np.abs(ev))
    im = ax.imshow(ev, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(targets)))
    ax.set_xticklabels([f"+{t}%" for t in targets])
    ax.set_yticks(range(len(stops)))
    ax.set_yticklabels([f"-{s}%" for s in stops])
    best = np.unravel_index(np.nanargmax(ev), ev.shape)
    for i in range(len(stops)):
        for j in range(len(targets)):
            ax.text(j, i, f"{ev[i, j]:+.0f}", ha="center", va="center", fontsize=8,
                    fontweight="bold" if (i, j) == best else "normal", color="black")
    ax.add_patch(plt.Rectangle((best[1] - 0.5, best[0] - 0.5), 1, 1, fill=False,
                               edgecolor="black", lw=2.5))
    ax.set_title(f"B · EV % by exit rule (best: +{targets[int(best[1])]}% / "
                 f"-{stops[int(best[0])]}%)", fontweight="bold")
    ax.set_xlabel("Profit target")
    ax.set_ylabel("Stop loss")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Mean EV %")

    # ---- C: MFE vs MAE scatter, colored by realized outcome ------------------
    ax = axes[1, 0]
    mfe_col = "mfe_abs" if "mfe_abs" in df.columns else ("mfe_pct" if "mfe_pct" in df.columns else None)
    mae_col = "mae_abs" if "mae_abs" in df.columns else ("mae_pct" if "mae_pct" in df.columns else None)
    if mfe_col and mae_col:
        mfe = pd.to_numeric(df[mfe_col], errors="coerce")
        mae = pd.to_numeric(df[mae_col], errors="coerce")
        win = df["realized_pnl"] > 0
        ax.scatter(mae[win], mfe[win], s=30, color=C_BULL, alpha=0.6,
                   edgecolor="white", linewidth=0.5, label="realized win")
        ax.scatter(mae[~win], mfe[~win], s=30, color=C_RANGE, alpha=0.6,
                   edgecolor="white", linewidth=0.5, label="realized loss")
        ax.axhline(0, color="#999", lw=0.8)
        ax.axvline(0, color="#999", lw=0.8)
        ax.set_title("C · Max favorable vs max adverse excursion", fontweight="bold")
        xlabel = "MAE $ (worst the trade got)" if mfe_col == "mfe_abs" else "MAE % (worst the trade got)"
        ylabel = "MFE $ (best the trade got)" if mfe_col == "mfe_abs" else "MFE % (best the trade got)"
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=8)
        ax.grid(color=GRID)
    else:
        ax.set_visible(False)

    # ---- E: mean realized P&L $ by exit reason ----------------------------
    ax = axes[2, 0]
    if "exit_reason" in df.columns and "realized_abs" in df.columns:
        order = ["profit_target", "stop_loss", "expired", "cap_open", "no_data"]
        er_colors = {"profit_target": C_BULL, "stop_loss": C_RANGE, "expired": "#888",
                     "cap_open": "#00838f", "no_data": "#cccccc"}
        er_mean = df.groupby("exit_reason")["realized_abs"].mean()
        er_n = df.groupby("exit_reason")["realized_abs"].count()
        labels_e = [r for r in order if r in er_mean.index]
        vals_e = [er_mean[r] for r in labels_e]
        ns_e = [er_n[r] for r in labels_e]
        bar_e = ax.bar(labels_e, vals_e,
                       color=[er_colors.get(r, "#888") for r in labels_e])
        for b, v, n in zip(bar_e, vals_e, ns_e):
            ax.text(b.get_x() + b.get_width() / 2,
                    v + (max(vals_e) - min(vals_e)) * 0.02 * (1 if v >= 0 else -1),
                    f"${v:+,.0f}\nn={n}", ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=8)
        ax.axhline(0, color="#999", lw=0.8)
        ax.set_title("E · Mean realized P&L $ by exit reason", fontweight="bold")
        ax.set_ylabel("Mean realized P&L ($)")
        ax.yaxis.set_major_formatter(dollar_fmt)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", color=GRID)
    else:
        ax.set_visible(False)

    # ---- D: exit-reason mix + hold-time -------------------------------------
    ax = axes[1, 1]
    if "exit_reason" in df.columns:
        order = ["profit_target", "stop_loss", "expired", "cap_open", "no_data"]
        counts = df["exit_reason"].value_counts()
        labels = [r for r in order if r in counts.index]
        vals = [counts[r] for r in labels]
        colors = {"profit_target": C_BULL, "stop_loss": C_RANGE, "expired": "#888",
                  "cap_open": "#00838f", "no_data": "#cccccc"}
        ax.bar(labels, vals, color=[colors.get(r, "#888") for r in labels])
        for i, v in enumerate(vals):
            ax.text(i, v, str(v), ha="center", va="bottom", fontsize=9)
        held = pd.to_numeric(df.get("days_held"), errors="coerce").dropna()
        sub = f"  ·  median hold {held.median():.0f} sessions" if len(held) else ""
        ax.set_title(f"D · Exit reason mix{sub}", fontweight="bold")
        ax.set_ylabel("Plays")
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", color=GRID)
    else:
        ax.set_visible(False)

    # ---- F: year-over-year mean P&L $ path (A-style, one line per entry year) -
    ax = axes[2, 1]
    df["entry_year"] = df["signal_date"].dt.year
    years = sorted(df["entry_year"].dropna().unique().astype(int))
    year_colors = plt.cm.tab10(np.linspace(0, 0.9, len(years)))  # pylint: disable=no-member
    any_year = False
    path_col = "dollar_pnl_path" if use_dollar else "pnl_path"
    for yr, color in zip(years, year_colors):
        ypaths = [p for p in df.loc[df["entry_year"] == yr, path_col] if p]
        if not ypaths:
            continue
        any_year = True
        ylen = min(max(len(p) for p in ypaths), horizon)
        ymean = [np.array([p[i] for p in ypaths if len(p) > i]).mean()
                 for i in range(ylen)]
        ax.plot(np.arange(1, ylen + 1), ymean, "-", color=color, lw=1.8,
                label=f"{yr} (n={len(ypaths)})")
    if any_year:
        ax.axhline(0, color="#999", lw=0.8)
        ax.set_title("F · Mean P&L $ path by entry year", fontweight="bold")
        ax.set_xlabel("Trading days since entry")
        ax.set_ylabel("Mean P&L ($)" if use_dollar else "Mean P&L %")
        if use_dollar:
            ax.yaxis.set_major_formatter(dollar_fmt)
        else:
            ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
        ax.legend(fontsize=8)
        ax.grid(color=GRID)
    else:
        ax.set_visible(False)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_paths.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def _draw_occupancy_panels(axes, df: pd.DataFrame,
                           letters=("A", "B", "C", "D", "E", "F")) -> int | None:
    """Draws the 6 hold-timing panels onto the 6 supplied Axes, in A–F order.
    `axes` may be any array-like of 6 Axes (a 2×3 grid flattens row-major, or a
    hand-picked list for a custom layout — e.g. pairing with MAE panels).

      A · Profit occupancy curve — share of LIVE trades above P&L thresholds by
          trading day held (+ live-trade count on a twin axis).
      B · MFE $ distribution — histogram of each trade's best mark, split by
          eventual win/loss outcome.
      C · Aggregate give-back curve — every trade aligned at its peak day (day 0),
          mean P&L in the sessions after the peak → decay after the top.
      D · MAE-day histogram — which trading day the worst drawdown lands on.
      E · MFE-day histogram — which trading day peak profit lands on.
      F · Days in profit vs loss — per trade, share of held sessions spent
          above $0, split by eventual win/loss outcome.

    Returns the trade count (for the caller's title), or None if there's no
    daily-path data to draw.
    """
    paths = [p for p in df.get("pnl_path", pd.Series([], dtype=object)) if p]
    if not paths:
        return None

    maxlen = max(len(p) for p in paths)
    horizon = min(maxlen, 63)  # ~3 months of sessions, matches build_paths
    days = np.arange(1, horizon + 1)
    n_total = len(paths)
    dollar_fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}")
    win_all = df["realized_pnl"] > 0
    ax_A, ax_B, ax_C, ax_D, ax_E, ax_F = np.asarray(axes, dtype=object).ravel()[:6]

    # ---- A: profit occupancy curve (dollar thresholds) ---------------------
    ax = ax_A
    dpaths = [p for p in df.get("dollar_pnl_path", pd.Series([], dtype=object)) if p]
    apaths = dpaths if dpaths else paths  # fall back to % if no dollar paths
    use_dollar = bool(dpaths)
    thresholds = ([(0, ">$0 (in profit)", C_LINE),
                   (250, "≥$250", C_BAR),
                   (500, "≥$500", C_MED),
                   (TARGET_DOLLAR, f"≥${TARGET_DOLLAR:,} (target)", C_BULL)]
                  if use_dollar else
                  [(0, ">0% (in profit)", C_LINE),
                   (25, "≥+25%", C_BAR),
                   (50, "≥+50%", C_MED),
                   (TARGET_PCT, f"≥+{TARGET_PCT}% (target)", C_BULL)])
    a_horizon = min(max(len(p) for p in apaths), 63)
    a_days = np.arange(1, a_horizon + 1)
    live = np.array([sum(1 for p in apaths if len(p) > i) for i in range(a_horizon)])
    min_sample = 3  # below this the share is 1–2 trades of noise → don't draw it
    for thr, label, color in thresholds:
        share = []
        for i in range(a_horizon):
            alive = [p[i] for p in apaths if len(p) > i]
            share.append(100 * sum(1 for v in alive if v > thr) / len(alive)
                         if len(alive) >= min_sample else np.nan)
        ax.plot(a_days, share, "-", color=color, lw=1.8, label=label)
    ax.axhline(50, color="#ccc", lw=0.7, ls=":")
    ax.set_ylim(0, 100)
    ax.set_title(f"{letters[0]} · Profit occupancy — share of live trades above P&L level",
                 fontweight="bold")
    ax.set_xlabel("Trading days since entry")
    ax.set_ylabel("Share of live trades")
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax2 = ax.twinx()
    ax2.fill_between(a_days, 0, live, color="#bbb", alpha=0.18, zorder=0)
    ax2.set_ylabel("# live trades", color="#888")
    ax2.tick_params(axis="y", labelcolor="#888")
    ax2.set_ylim(0, len(apaths) * 1.05)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(color=GRID)

    # ---- B: MFE $ distribution, split by eventual outcome ------------------
    ax = ax_B
    mfe = pd.to_numeric(df.get("mfe_abs"), errors="coerce")
    mfe_valid = mfe.dropna()
    if len(mfe_valid):
        bins = np.linspace(min(mfe_valid.min(), 0), mfe_valid.max(), 25)
        ax.hist(mfe[win_all].dropna(), bins=bins, color=C_BULL, alpha=0.6,
                edgecolor="white", label=f"eventual win (n={int(win_all.sum())})")
        ax.hist(mfe[~win_all].dropna(), bins=bins, color=C_RANGE, alpha=0.6,
                edgecolor="white", label=f"eventual loss (n={int((~win_all).sum())})")
        med = mfe_valid.median()
        ax.axvline(med, color="#333", lw=1.5, ls="--", label=f"median ${med:,.0f}")
        ax.axvline(0, color="#999", lw=0.8)
        ax.legend(fontsize=8)
    ax.set_title(f"{letters[1]} · MFE $ distribution (best mark per trade)", fontweight="bold")
    ax.set_xlabel("MFE ($)")
    ax.set_ylabel("Trades")
    ax.xaxis.set_major_formatter(dollar_fmt)
    ax.grid(axis="y", color=GRID)

    # ---- C: aggregate give-back curve (aligned at peak day, dollar) --------
    ax = ax_C
    gb_dollar_fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}")
    K = min(horizon, 21)  # sessions after the peak to trace
    aligned = []
    for p in apaths:
        peak_idx = int(np.argmax(p))  # 0-based day of this trade's MFE
        tail = p[peak_idx:peak_idx + K + 1]
        aligned.append(tail)
    rel_days = np.arange(0, K + 1)
    mean_gb, lo_gb, hi_gb, n_gb = [], [], [], []
    for k in range(K + 1):
        vals = np.array([t[k] for t in aligned if len(t) > k])
        if len(vals):
            mean_gb.append(vals.mean())
            lo_gb.append(np.percentile(vals, 25))
            hi_gb.append(np.percentile(vals, 75))
            n_gb.append(len(vals))
        else:
            mean_gb.append(np.nan); lo_gb.append(np.nan)
            hi_gb.append(np.nan); n_gb.append(0)
    ax.fill_between(rel_days, lo_gb, hi_gb, color=C_BAR, alpha=0.2, label="IQR (25–75%)")
    ax.plot(rel_days, mean_gb, "-", color=C_LINE, lw=2, label="Mean P&L")
    peak_label = f"${mean_gb[0]:+,.0f}" if use_dollar else f"{mean_gb[0]:+.0f}%"
    ax.plot(0, mean_gb[0], "o", color=C_MED, ms=8, label=f"peak (mean {peak_label})")
    if len(mean_gb) > 1 and not np.isnan(mean_gb[-1]):
        giveback = mean_gb[0] - mean_gb[-1]
        gb_label = f"gives back ${giveback:,.0f}" if use_dollar else f"gives back {giveback:.0f} pts"
        ax.annotate(f"{gb_label} over {K} sessions",
                    (rel_days[-1], mean_gb[-1]), textcoords="offset points",
                    xytext=(-5, 8), ha="right", fontsize=8, color="#333")
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_title(f"{letters[2]} · Give-back after the peak (trades aligned at their MFE day)",
                 fontweight="bold")
    ax.set_xlabel("Trading days after peak")
    ax.set_ylabel("Mean P&L ($)" if use_dollar else "Mean P&L %")
    if use_dollar:
        ax.yaxis.set_major_formatter(gb_dollar_fmt)
    else:
        ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(color=GRID)

    # ---- D: MAE-day histogram ----------------------------------------------
    ax = ax_D
    if "mae_day" in df.columns:
        mae_day = pd.to_numeric(df["mae_day"], errors="coerce").dropna()
    else:
        mae_day = pd.Series([int(np.argmin(p)) + 1 for p in paths], dtype=float)
    mae_day = mae_day[mae_day <= horizon]
    if len(mae_day):
        bins = np.arange(1, min(int(mae_day.max()), horizon) + 2)
        ax.hist(mae_day, bins=bins, color=C_RANGE, edgecolor="white", align="left")
        m = mae_day.median()
        ax.axvline(m, color=C_LINE, lw=1.5, ls="--", label=f"median day {m:.0f}")
        ax.legend(fontsize=8)
    ax.set_title(f"{letters[3]} · When the worst drawdown lands (MAE day distribution)",
                 fontweight="bold")
    ax.set_xlabel("Trading day of worst drawdown (MAE)")
    ax.set_ylabel("Trades")
    ax.grid(axis="y", color=GRID)

    # ---- E: MFE-day histogram ------------------------------------------------
    ax = ax_E
    if "mfe_day" in df.columns:
        mfe_day = pd.to_numeric(df["mfe_day"], errors="coerce").dropna()
    else:
        mfe_day = pd.Series([int(np.argmax(p)) + 1 for p in paths], dtype=float)
    mfe_day = mfe_day[mfe_day <= horizon]
    if len(mfe_day):
        bins = np.arange(1, min(int(mfe_day.max()), horizon) + 2)
        ax.hist(mfe_day, bins=bins, color=C_BAR, edgecolor="white", align="left")
        m = mfe_day.median()
        ax.axvline(m, color=C_RANGE, lw=1.5, ls="--", label=f"median day {m:.0f}")
        ax.legend(fontsize=8)
    ax.set_title(f"{letters[4]} · When peak profit lands (MFE day distribution)", fontweight="bold")
    ax.set_xlabel("Trading day of peak profit (MFE)")
    ax.set_ylabel("Trades")
    ax.grid(axis="y", color=GRID)

    # ---- F: days in profit vs loss, per trade -------------------------------
    ax = ax_F
    path_col = "dollar_pnl_path" if use_dollar else "pnl_path"
    has_path = df[path_col].apply(lambda p: isinstance(p, list) and len(p) > 0)
    sub = df.loc[has_path]
    frac_profit = pd.Series(
        [100 * sum(1 for v in p if v > 0) / len(p) for p in sub[path_col]], dtype=float)
    win_sub = (sub["realized_pnl"] > 0).reset_index(drop=True)
    bins = np.linspace(0, 100, 21)
    ax.hist(frac_profit[win_sub], bins=bins, color=C_BULL, alpha=0.6,
            edgecolor="white", label=f"eventual win (n={int(win_sub.sum())})")
    ax.hist(frac_profit[~win_sub], bins=bins, color=C_RANGE, alpha=0.6,
            edgecolor="white", label=f"eventual loss (n={int((~win_sub).sum())})")
    med = frac_profit.median()
    ax.axvline(med, color="#333", lw=1.5, ls="--", label=f"median {med:.0f}%")
    ax.axvline(50, color="#999", lw=0.8, ls=":")
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.set_title(f"{letters[5]} · Share of held days spent in profit (per trade)",
                 fontweight="bold")
    ax.set_xlabel("% of trading days held above $0")
    ax.set_ylabel("Trades")
    ax.legend(fontsize=8)
    ax.grid(axis="y", color=GRID)

    return n_total


def build_occupancy(df: pd.DataFrame, out: Path) -> Path | None:
    """Hold-timing page: when trades are in profit, when the move is captured,
    and how fast profit is given back after the peak. See _draw_occupancy_panels
    for the individual panel descriptions."""
    fig, axes = plt.subplots(2, 3, figsize=(21, 11))
    n_total = _draw_occupancy_panels(axes, df)
    if n_total is None:
        plt.close(fig)
        return None
    fig.suptitle(
        f"Hold-timing analysis — {n_total} trades with a daily path",
        fontsize=16, fontweight="bold", y=0.995,
    )

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_occupancy.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def build_time(df: pd.DataFrame, out: Path) -> Path:
    """Temporal analysis page: equity curve, annual bars, monthly heatmap."""
    df = df.copy()
    df = df.sort_values("signal_date")
    df["year"] = df["signal_date"].dt.year
    df["month"] = df["signal_date"].dt.month
    years = sorted(df["year"].dropna().unique().astype(int))

    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    fig.suptitle(
        f"Temporal analysis — {len(df)} plays, "
        f"{df.signal_date.min():%b %Y}–{df.signal_date.max():%b %Y}",
        fontsize=16, fontweight="bold", y=0.995,
    )

    # ---- A: cumulative realized P&L $ equity curve ----------------------
    ax = axes[0, 0]
    cum = df["realized_abs"].fillna(0).cumsum()
    ax.plot(df["signal_date"], cum, "-", color=C_LINE, lw=2)
    ax.fill_between(df["signal_date"], 0, cum,
                    where=(cum >= 0), color=C_BULL, alpha=0.15)
    ax.fill_between(df["signal_date"], 0, cum,
                    where=(cum < 0), color=C_RANGE, alpha=0.15)
    ax.axhline(0, color="#999", lw=0.8)
    # annotate year boundaries
    for yr in years[1:]:
        first = df.loc[df["year"] == yr, "signal_date"].min()
        ax.axvline(first, color="#bbb", lw=0.8, ls="--")
        ax.text(first, ax.get_ylim()[0], str(yr), fontsize=7,
                color="#888", ha="left", va="bottom")
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title("A · Cumulative realized P&L $ (equity curve)", fontweight="bold")
    ax.set_xlabel("Signal date")
    ax.grid(color=GRID)

    # ---- B: mean realized P&L % + win rate by year ----------------------
    ax = axes[0, 1]
    ax2 = ax.twinx()
    yr_mean = df.groupby("year")["realized_pnl"].mean()
    yr_win = df.groupby("year")["realized_pnl"].apply(lambda s: (s > 0).mean() * 100)
    yr_n = df.groupby("year")["realized_pnl"].count()
    x = np.arange(len(years))
    bar_colors = [C_BULL if yr_mean.get(y, 0) >= 0 else C_RANGE for y in years]
    ax.bar(x, [yr_mean.get(y, np.nan) for y in years],
           color=bar_colors, alpha=0.8, label="Mean P&L %")
    ax2.plot(x, [yr_win.get(y, np.nan) for y in years],
             "D--", color=C_MED, lw=1.5, ms=7, label="Win rate %")
    ax2.axhline(50, color="#ccc", lw=0.7, ls=":")
    for xi, y in enumerate(years):
        m = yr_mean.get(y, np.nan)
        n = yr_n.get(y, 0)
        if not np.isnan(m):
            ax.annotate(f"{m:+.0f}%\nn={n}", (xi, m),
                        textcoords="offset points",
                        xytext=(0, 6 if m >= 0 else -18),
                        ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_ylabel("Mean realized P&L %")
    ax2.set_ylabel("Win rate %")
    ax2.set_ylim(0, 110)
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.set_title("B · Annual performance — mean P&L & win rate", fontweight="bold")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper left")
    ax.grid(axis="y", color=GRID)

    # ---- C: monthly heatmap (year × month) of mean realized P&L % -------
    ax = axes[1, 0]
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    piv = df.pivot_table(index="year", columns="month",
                         values="realized_pnl", aggfunc="mean")
    cnt = df.pivot_table(index="year", columns="month",
                         values="realized_pnl", aggfunc="count")
    piv = piv.reindex(index=years, columns=range(1, 13))
    cnt = cnt.reindex(index=years, columns=range(1, 13))
    vmax = np.nanmax(np.abs(piv.values)) if not np.all(np.isnan(piv.values)) else 1
    im = ax.imshow(piv.values, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(12))
    ax.set_xticklabels(month_names, fontsize=8)
    ax.set_yticks(range(len(years)))
    ax.set_yticklabels(years)
    for i, yr in enumerate(years):
        for j, mo in enumerate(range(1, 13)):
            v = piv.loc[yr, mo] if mo in piv.columns else np.nan
            n = cnt.loc[yr, mo] if mo in cnt.columns else np.nan
            if not np.isnan(v):
                ax.text(j, i, f"{v:+.0f}\n({int(n)})",
                        ha="center", va="center", fontsize=7,
                        color="black")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04, label="Mean P&L %")
    ax.set_title("C · Monthly P&L heatmap (year × month)", fontweight="bold")

    # ---- D: play count by year + quarter breakdown ----------------------
    ax = axes[1, 1]
    df["quarter"] = df["signal_date"].dt.quarter
    q_colors = {1: "#4e79a7", 2: "#f28e2b", 3: "#59a14f", 4: "#e15759"}
    bottom = np.zeros(len(years))
    for q in range(1, 5):
        qcounts = [df[(df["year"] == y) & (df["quarter"] == q)].shape[0]
                   for y in years]
        ax.bar(range(len(years)), qcounts, bottom=bottom,
               color=q_colors[q], label=f"Q{q}", alpha=0.85)
        bottom += np.array(qcounts)
    for xi, y in enumerate(years):
        total = (df["year"] == y).sum()
        ax.text(xi, total + 0.3, str(total), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years)
    ax.set_ylabel("Number of plays")
    ax.set_title("D · Play count by year & quarter", fontweight="bold")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(axis="y", color=GRID)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_time.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def build_playbook(df: pd.DataFrame, out: Path) -> Path:
    """Validate whether the analysis is mapping the right structures to the right conditions.

    Four panels:
      A · Structure × regime count  — allocation: are bear spreads used in BEAR, etc.?
      B · Structure × regime P&L $  — does the allocation actually win?
      C · Structure × year P&L $    — which strategies worked in which periods?
      D · Structure × year win rate  — consistency across years
    """
    df = df.copy()
    dollar_fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:+,.0f}")

    STRUCTS = [
        s for s in ["bull_call_spread", "bear_put_spread",
                    "bull_put_spread", "bear_call_spread"]
        if (df["structure"] == s).sum() >= 2
    ]
    REGIMES = [r for r in ["BULL", "BEAR", "RANGE"]
               if (df["regime_label"] == r).sum() >= 2]
    years = sorted(df["signal_date"].dt.year.dropna().unique().astype(int))

    struct_colors = {
        "bull_call_spread": C_BULL,
        "bear_put_spread":  C_RANGE,
        "bull_put_spread":  "#6a1b9a",
        "bear_call_spread": "#00838f",
    }

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(
        "Playbook validation — structure × regime & year",
        fontsize=15, fontweight="bold", y=0.995,
    )

    def _annotated_heatmap(ax, matrix, row_labels, col_labels,
                           fmt_fn, cmap, title, vmin=None, vmax=None):
        vmax_ = vmax if vmax is not None else np.nanmax(np.abs(matrix.values))
        vmin_ = vmin if vmin is not None else -vmax_
        im = ax.imshow(matrix.values, cmap=cmap,
                       vmin=vmin_, vmax=vmax_, aspect="auto")
        ax.set_xticks(range(len(col_labels)))
        ax.set_xticklabels(col_labels, fontsize=8)
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels([s.replace("_", "\n") for s in row_labels], fontsize=7)
        for i in range(len(row_labels)):
            for j in range(len(col_labels)):
                v = matrix.values[i, j]
                if np.isnan(v):
                    ax.text(j, i, "—", ha="center", va="center",
                            color="#aaa", fontsize=8)
                else:
                    ax.text(j, i, fmt_fn(v), ha="center", va="center",
                            fontsize=8, fontweight="bold", color="black")
        ax.set_title(title, fontweight="bold")
        return im

    # ---- A: structure × regime count ------------------------------------
    ax = axes[0, 0]
    count_piv = df.groupby(["structure", "regime_label"]).size().unstack(fill_value=0)
    count_piv = count_piv.reindex(index=STRUCTS, columns=REGIMES, fill_value=0)
    im = _annotated_heatmap(
        ax, count_piv, STRUCTS, REGIMES,
        fmt_fn=lambda v: str(int(v)),
        cmap="Blues", title="A · Trade count — structure × regime",
        vmin=0, vmax=count_piv.values.max())
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="# trades")

    # ---- B: structure × regime mean P&L $ ------------------------------
    ax = axes[0, 1]
    pnl_piv = df.groupby(["structure", "regime_label"])["realized_abs"].mean().unstack()
    pnl_piv = pnl_piv.reindex(index=STRUCTS, columns=REGIMES)
    im = _annotated_heatmap(
        ax, pnl_piv, STRUCTS, REGIMES,
        fmt_fn=lambda v: f"${v:+,.0f}",
        cmap="RdYlGn", title="B · Mean P&L $ — structure × regime")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Mean P&L ($)")

    # ---- C: structure × year mean P&L $ (grouped bars) -----------------
    ax = axes[1, 0]
    x = np.arange(len(years))
    w = 0.8 / max(len(STRUCTS), 1)
    for k, s in enumerate(STRUCTS):
        vals = []
        for yr in years:
            sub = df[(df["structure"] == s) & (df["signal_date"].dt.year == yr)]
            vals.append(sub["realized_abs"].mean() if len(sub) else np.nan)
        ax.bar(x + k * w, np.nan_to_num(vals), width=w,
               color=struct_colors.get(s, "#555"), alpha=0.85,
               label=s.replace("_", " "))
        for xi, (v, n_sub) in enumerate(zip(vals, [
            len(df[(df["structure"] == s) & (df["signal_date"].dt.year == yr)]) for yr in years
        ])):
            if not np.isnan(v) and n_sub > 0:
                ax.text(xi + k * w, v + (20 if v >= 0 else -20),
                        f"n={n_sub}", ha="center", fontsize=6,
                        va="bottom" if v >= 0 else "top", color="#555")
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xticks(x + w * (len(STRUCTS) - 1) / 2)
    ax.set_xticklabels(years)
    ax.yaxis.set_major_formatter(dollar_fmt)
    ax.set_title("C · Mean P&L $ — structure × year", fontweight="bold")
    ax.set_xlabel("Entry year")
    ax.set_ylabel("Mean realized P&L ($)")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="y", color=GRID)

    # ---- D: structure × year win rate (heatmap) -------------------------
    ax = axes[1, 1]
    wr_rows = {}
    for s in STRUCTS:
        row = {}
        for yr in years:
            sub = df[(df["structure"] == s) & (df["signal_date"].dt.year == yr)]
            n = len(sub)
            row[yr] = (sub["realized_abs"] > 0).mean() * 100 if n >= 2 else np.nan
        wr_rows[s] = row
    wr_piv = pd.DataFrame(wr_rows).T.reindex(STRUCTS)[years]
    im = _annotated_heatmap(
        ax, wr_piv, STRUCTS, [str(y) for y in years],
        fmt_fn=lambda v: f"{v:.0f}%",
        cmap="RdYlGn", title="D · Win rate % — structure × year",
        vmin=0, vmax=100)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Win rate %")

    fig.tight_layout(rect=(0, 0, 1, 0.985))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_playbook.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def build_spaghetti(df: pd.DataFrame, out: Path) -> Path | None:
    """Spaghetti charts: individual P&L % paths, grouped four ways.

    Each panel draws every trade's raw daily path as a thin transparent line,
    then overlays the group mean as a bold line. Four groupings:
      A · Exit reason  — most diagnostic for exit-rule tuning
      B · Regime       — validates the panic=good / chop=bad thesis
      C · Win vs loss  — clearest signal: do winners look different early?
      D · Structure    — bear_put vs bull_call (only groups with ≥5 trades shown)
    """
    paths = df["dollar_pnl_path"].tolist()
    if not any(paths):
        return None

    dollar_fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:+,.0f}")
    HORIZON = 45  # trading days shown on x-axis

    def _draw(ax, groups, title, letter):
        """groups: list of (label, color, mask_series)"""
        ax.axhline(0, color="#999", lw=0.8)
        for label, color, mask in groups:
            subset_paths = [p for p, m in zip(df["dollar_pnl_path"], mask) if m and p]
            if not subset_paths:
                continue
            # individual paths
            for p in subset_paths:
                y = p[:HORIZON]
                ax.plot(range(1, len(y) + 1), y,
                        color=color, lw=0.6, alpha=0.12)
            # group mean
            mean_len = min(HORIZON, max(len(p) for p in subset_paths))
            mean_y = [np.nanmean([p[i] for p in subset_paths if len(p) > i])
                      for i in range(mean_len)]
            ax.plot(range(1, mean_len + 1), mean_y,
                    color=color, lw=2.2, label=f"{label} (n={len(subset_paths)})")
        ax.set_title(f"{letter} · {title}", fontweight="bold")
        ax.set_xlabel("Trading days since entry")
        ax.set_ylabel("P&L ($)")
        ax.yaxis.set_major_formatter(dollar_fmt)
        ax.set_xlim(1, HORIZON)
        ax.legend(fontsize=8)
        ax.grid(color=GRID)

    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle(
        f"Path spaghetti — {len(df)} trades  "
        f"(thin = individual, bold = group mean)",
        fontsize=15, fontweight="bold", y=0.995,
    )

    # ---- A: by exit reason -----------------------------------------------
    exit_cfg = [
        ("profit_target", C_BULL,  df["exit_reason"] == "profit_target"),
        ("time_exit",     C_LINE,  df["exit_reason"] == "time_exit"),
        ("stop_loss",     C_RANGE, df["exit_reason"] == "stop_loss"),
        ("dollar_stop",   "#8B0000", df["exit_reason"] == "dollar_stop"),
        ("cap_open",      C_MED,   df["exit_reason"].isin(["cap_open", "expired"])),
    ]
    _draw(axes[0, 0], exit_cfg, "Exit reason", "A")

    # ---- B: by regime ----------------------------------------------------
    regime_cfg = [
        ("BULL",  C_BULL,  df["regime_label"] == "BULL"),
        ("BEAR",  C_RANGE, df["regime_label"] == "BEAR"),
        ("RANGE", C_MED,   df["regime_label"] == "RANGE"),
    ]
    _draw(axes[0, 1], regime_cfg, "Regime", "B")

    # ---- C: win vs loss --------------------------------------------------
    win_mask  = df["realized_pnl"] > 0
    wl_cfg = [
        ("Win",  C_BULL,  win_mask),
        ("Loss", C_RANGE, ~win_mask),
    ]
    _draw(axes[1, 0], wl_cfg, "Win vs loss", "C")

    # ---- D: structure (only groups with ≥5 trades) -----------------------
    struct_colors = {
        "bull_call_spread": C_BULL,
        "bear_put_spread":  C_RANGE,
        "bull_put_spread":  "#6a1b9a",
        "bear_call_spread": "#00838f",
    }
    struct_cfg = [
        (s, c, df["structure"] == s)
        for s, c in struct_colors.items()
        if (df["structure"] == s).sum() >= 5
    ]
    _draw(axes[1, 1], struct_cfg, "Structure", "D")

    fig.tight_layout(rect=(0, 0, 1, 0.985))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_spaghetti.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def build_mfe_mae_dist(df: pd.DataFrame, out: Path) -> Path:
    """MFE (left column) and MAE (right column) side by side — 4×2 layout.
      Row 0 · By market-level label (BULL/BEAR/RANGE)
      Row 1 · By play (ticker) label
      Row 2 · Aligned vs drifted
      Row 3 · Key market × play combos (n ≥ 5)
    """
    df = df.copy()
    df["mfe"] = pd.to_numeric(df["mfe_abs"], errors="coerce")
    df["mae"] = pd.to_numeric(df["mae_abs"], errors="coerce")
    df_mfe = df[df["mkt_label"].notna() & df["play_label"].notna() & df["mfe"].notna()]
    df_mae = df[df["mkt_label"].notna() & df["play_label"].notna() & df["mae"].notna()]

    rng = np.random.default_rng(42)
    dollar_fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}")
    LABEL_COLORS = {"BULL": C_BULL, "BEAR": C_RANGE, "RANGE": C_MED}
    LABEL_ORDER = ["BULL", "BEAR", "RANGE"]

    def _order(groups):
        """Label list sorted by MFE median desc — used as the shared y-axis order."""
        cleaned = [(lb, s.dropna()) for lb, _, s in groups if not s.dropna().empty]
        return [lb for lb, _ in sorted(cleaned, key=lambda x: x[1].median(), reverse=True)]

    def _strip_box(ax, groups, title, letter, xlabel, sort_desc=True, label_order=None):
        groups = [(lb, c, s.dropna()) for lb, c, s in groups if not s.dropna().empty]
        if label_order is not None:
            lut = {lb: (c, s) for lb, c, s in groups}
            groups = [(lb, lut[lb][0], lut[lb][1]) for lb in label_order if lb in lut]
        else:
            groups = sorted(groups, key=lambda g: g[2].median(), reverse=sort_desc)
        for i, (_, color, vals) in enumerate(groups):
            y = np.full(len(vals), i)
            jitter = rng.uniform(-0.25, 0.25, len(vals))
            ax.scatter(vals, y + jitter, color=color, alpha=0.45, s=22,
                       edgecolor="white", linewidth=0.4, zorder=3)
            q1, med, q3 = vals.quantile([0.25, 0.5, 0.75])
            iqr = q3 - q1
            whislo = max(vals.min(), q1 - 1.5 * iqr)
            whishi = min(vals.max(), q3 + 1.5 * iqr)
            ax.broken_barh([(q1, q3 - q1)], (i - 0.18, 0.36),
                           facecolors=color, alpha=0.35, zorder=2)
            ax.plot([med, med], [i - 0.25, i + 0.25], color=color, lw=2.5, zorder=4)
            ax.plot([whislo, q1], [i, i], color=color, lw=1, zorder=2)
            ax.plot([q3, whishi], [i, i], color=color, lw=1, zorder=2)
            if sort_desc:
                ax.annotate(f"med ${med:+,.0f}  n={len(vals)}",
                            (whishi, i), textcoords="offset points", xytext=(5, 0),
                            va="center", fontsize=7.5, color="#333")
            else:
                ax.annotate(f"med ${med:+,.0f}  n={len(vals)}",
                            (whislo, i), textcoords="offset points", xytext=(-5, 0),
                            va="center", ha="right", fontsize=7.5, color="#333")
        ax.axvline(0, color="#999", lw=0.8, ls="--")
        ax.set_yticks(range(len(groups)))
        ax.set_yticklabels([g[0] for g in groups], fontsize=8)
        ax.set_xlabel(xlabel)
        ax.set_title(f"{letter} · {title}", fontweight="bold")
        ax.grid(axis="x", color=GRID)

    fig, axes = plt.subplots(4, 2, figsize=(18, 26))
    fig.suptitle(
        "MFE / MAE distribution by regime — absolute $  (left = MFE, right = MAE)",
        fontsize=16, fontweight="bold", y=0.995,
    )

    # ---- Row 0: by market label -------------------------------------------
    grp_mfe = [(lb, LABEL_COLORS[lb], df[df["mkt_label"] == lb]["mfe"]) for lb in LABEL_ORDER]
    grp_mae = [(lb, LABEL_COLORS[lb], df[df["mkt_label"] == lb]["mae"]) for lb in LABEL_ORDER]
    shared_order = _order(grp_mfe)
    _strip_box(axes[0, 0], grp_mfe, "MFE by market-level regime", "A", "MFE ($)",
               sort_desc=True, label_order=shared_order)
    axes[0, 0].xaxis.set_major_formatter(dollar_fmt)
    _strip_box(axes[0, 1], grp_mae, "MAE by market-level regime", "B", "MAE ($)",
               sort_desc=False, label_order=shared_order)
    axes[0, 1].xaxis.set_major_formatter(dollar_fmt)

    # ---- Row 1: by play label ---------------------------------------------
    grp_mfe = [(lb, LABEL_COLORS[lb], df[df["play_label"] == lb]["mfe"]) for lb in LABEL_ORDER]
    grp_mae = [(lb, LABEL_COLORS[lb], df[df["play_label"] == lb]["mae"]) for lb in LABEL_ORDER]
    shared_order = _order(grp_mfe)
    _strip_box(axes[1, 0], grp_mfe, "MFE by play (ticker) regime label", "C", "MFE ($)",
               sort_desc=True, label_order=shared_order)
    axes[1, 0].xaxis.set_major_formatter(dollar_fmt)
    _strip_box(axes[1, 1], grp_mae, "MAE by play (ticker) regime label", "D", "MAE ($)",
               sort_desc=False, label_order=shared_order)
    axes[1, 1].xaxis.set_major_formatter(dollar_fmt)

    # ---- Row 2: aligned vs drifted ----------------------------------------
    grp_mfe = [
        ("Aligned\n(market == play)", C_RANGE, df_mfe[df_mfe["regime_aligned"]]["mfe"]),
        ("Drifted\n(market ≠ play)",  C_BULL,  df_mfe[~df_mfe["regime_aligned"]]["mfe"]),
    ]
    grp_mae = [
        ("Aligned\n(market == play)", C_RANGE, df_mae[df_mae["regime_aligned"]]["mae"]),
        ("Drifted\n(market ≠ play)",  C_BULL,  df_mae[~df_mae["regime_aligned"]]["mae"]),
    ]
    shared_order = _order(grp_mfe)
    _strip_box(axes[2, 0], grp_mfe, "MFE — aligned vs counter-consensus", "E", "MFE ($)",
               sort_desc=True, label_order=shared_order)
    axes[2, 0].xaxis.set_major_formatter(dollar_fmt)
    _strip_box(axes[2, 1], grp_mae, "MAE — aligned vs counter-consensus", "F", "MAE ($)",
               sort_desc=False, label_order=shared_order)
    axes[2, 1].xaxis.set_major_formatter(dollar_fmt)

    # ---- Row 3: cross-tab combos ------------------------------------------
    combo_colors = plt.cm.tab10(np.linspace(0, 0.9, 9))  # pylint: disable=no-member
    cross_mfe, cross_mae = [], []
    for ci, (mkt, play) in enumerate(
        (m, p) for m in LABEL_ORDER for p in LABEL_ORDER
    ):
        sub_mfe = df_mfe[(df_mfe["mkt_label"] == mkt) & (df_mfe["play_label"] == play)]["mfe"]
        sub_mae = df_mae[(df_mae["mkt_label"] == mkt) & (df_mae["play_label"] == play)]["mae"]
        label = f"mkt={mkt}\nplay={play}"
        if sub_mfe.dropna().shape[0] >= 5:
            cross_mfe.append((label, combo_colors[ci], sub_mfe))
        if sub_mae.dropna().shape[0] >= 5:
            cross_mae.append((label, combo_colors[ci], sub_mae))
    shared_order = _order(cross_mfe)
    _strip_box(axes[3, 0], cross_mfe, "MFE by market × play combo (n ≥ 5)", "G", "MFE ($)",
               sort_desc=True, label_order=shared_order)
    axes[3, 0].xaxis.set_major_formatter(dollar_fmt)
    _strip_box(axes[3, 1], cross_mae, "MAE by market × play combo (n ≥ 5)", "H", "MAE ($)",
               sort_desc=False, label_order=shared_order)
    axes[3, 1].xaxis.set_major_formatter(dollar_fmt)

    fig.tight_layout(rect=(0, 0, 1, 0.985))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_mfe_mae_dist.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def _draw_mae_recovery_panels(axes, df: pd.DataFrame, letters=("A", "B", "C", "D")) -> int | None:
    """Draws the 4 MAE panels onto the 4 supplied Axes, in A–D order. `axes` may
    be any array-like of 4 Axes (a 2×2 grid flattens row-major, or a hand-picked
    list for a custom layout — e.g. pairing with the MFE panels).

      A · MAE $ distribution — histogram of each trade's worst mark, split by
          eventual win/loss outcome.
      B · Recovery path — trades aligned at their MAE (trough) day; mean $ P&L
          in the sessions after the trough → does the trade climb back.
      C · Cumulative recovery-to-breakeven — share of trades back above $0 by
          day t after their trough.
      D · Win rate by MAE severity quartile (worst → mildest) — does a deeper
          hole mean a lower chance of coming back a winner.

    Returns the trade count (for the caller's title), or None if there's no
    daily-path data to draw.
    """
    paths = df.get("dollar_pnl_path", pd.Series([], dtype=object)).tolist()
    mae = pd.to_numeric(df.get("mae_abs"), errors="coerce")
    win = df["realized_pnl"] > 0
    valid = [i for i, p in enumerate(paths) if p]
    if not valid:
        return None

    dollar_fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}")
    ax_A, ax_B, ax_C, ax_D = np.asarray(axes, dtype=object).ravel()[:4]

    # ---- A: MAE $ distribution, split by eventual outcome ------------------
    ax = ax_A
    mae_valid = mae.dropna()
    if len(mae_valid):
        bins = np.linspace(mae_valid.min(), max(mae_valid.max(), 0), 25)
        ax.hist(mae[win].dropna(), bins=bins, color=C_BULL, alpha=0.6,
                edgecolor="white", label=f"eventual win (n={int(win.sum())})")
        ax.hist(mae[~win].dropna(), bins=bins, color=C_RANGE, alpha=0.6,
                edgecolor="white", label=f"eventual loss (n={int((~win).sum())})")
        med = mae_valid.median()
        ax.axvline(med, color="#333", lw=1.5, ls="--", label=f"median ${med:,.0f}")
        ax.axvline(0, color="#999", lw=0.8)
        ax.legend(fontsize=8)
    ax.set_title(f"{letters[0]} · MAE $ distribution (worst mark per trade)", fontweight="bold")
    ax.set_xlabel("MAE ($)")
    ax.set_ylabel("Trades")
    ax.xaxis.set_major_formatter(dollar_fmt)
    ax.grid(axis="y", color=GRID)

    # ---- B: recovery path — trades aligned at their trough day -------------
    ax = ax_B
    K = 21  # sessions traced after the trough
    aligned = []
    for i in valid:
        p = paths[i]
        trough_idx = int(np.argmin(p))  # 0-based day of this trade's MAE
        aligned.append(p[trough_idx:trough_idx + K + 1])
    rel_days = np.arange(0, K + 1)
    mean_r, lo_r, hi_r = [], [], []
    for k in range(K + 1):
        vals = np.array([t[k] for t in aligned if len(t) > k])
        if len(vals):
            mean_r.append(vals.mean())
            lo_r.append(np.percentile(vals, 25))
            hi_r.append(np.percentile(vals, 75))
        else:
            mean_r.append(np.nan); lo_r.append(np.nan); hi_r.append(np.nan)
    ax.fill_between(rel_days, lo_r, hi_r, color=C_BAR, alpha=0.2, label="IQR (25–75%)")
    ax.plot(rel_days, mean_r, "-", color=C_LINE, lw=2, label="Mean P&L")
    ax.plot(0, mean_r[0], "o", color=C_RANGE, ms=8, label=f"trough (mean ${mean_r[0]:+,.0f})")
    if len(mean_r) > 1 and not np.isnan(mean_r[-1]):
        recovered = mean_r[-1] - mean_r[0]
        ax.annotate(f"recovers ${recovered:+,.0f} over {K} sessions",
                    (rel_days[-1], mean_r[-1]), textcoords="offset points",
                    xytext=(-5, 8), ha="right", fontsize=8, color="#333")
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_title(f"{letters[1]} · Recovery after the trough (trades aligned at their MAE day)",
                 fontweight="bold")
    ax.set_xlabel("Trading days after trough")
    ax.set_ylabel("Mean P&L ($)")
    ax.yaxis.set_major_formatter(dollar_fmt)
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(color=GRID)

    # ---- C: cumulative share back above breakeven after the trough --------
    ax = ax_C
    recovery_days = []
    for i in valid:
        p = paths[i]
        trough_idx = int(np.argmin(p))
        hit = None
        for j in range(trough_idx, len(p)):
            if p[j] > 0:
                hit = j - trough_idx
                break
        recovery_days.append(hit)
    cum_days = np.arange(0, K + 1)
    cum = [100 * sum(1 for d in recovery_days if d is not None and d <= t) / len(valid)
           for t in cum_days]
    ax.plot(cum_days, cum, "-", color=C_BULL, lw=2)
    ax.fill_between(cum_days, 0, cum, color=C_BULL, alpha=0.12)
    ever = sum(1 for d in recovery_days if d is not None)
    ax.axhline(100 * ever / len(valid), color=C_MED, lw=1, ls="--",
               label=f"ever recovers to $0+: {100 * ever / len(valid):.0f}%")
    ax.set_ylim(0, 100)
    ax.set_title(f"{letters[2]} · Cumulative recovery to breakeven after the trough", fontweight="bold")
    ax.set_xlabel("Trading days after trough")
    ax.set_ylabel("Share of trades back above $0")
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(color=GRID)

    # ---- D: win rate by MAE severity quartile -------------------------------
    ax = ax_D
    df_q = pd.DataFrame({"mae": mae, "win": win}).dropna(subset=["mae"])
    order = ["worst", "q2", "q3", "mildest"]
    try:
        df_q["bucket"] = pd.qcut(df_q["mae"], 4, labels=order, duplicates="drop")
    except ValueError:
        df_q["bucket"] = pd.cut(df_q["mae"], 4, labels=order)
    rates, ns = [], []
    for b in order:
        sub = df_q[df_q["bucket"] == b]
        rates.append(100 * sub["win"].mean() if len(sub) else np.nan)
        ns.append(len(sub))
    bars = ax.bar(order, rates, color=[C_RANGE, "#e08a1e", "#e0c01e", C_BULL])
    for b, r, n in zip(bars, rates, ns):
        if not np.isnan(r):
            ax.text(b.get_x() + b.get_width() / 2, r, f"{r:.0f}%\nn={n}",
                    ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_title(f"{letters[3]} · Win rate by MAE severity quartile (worst → mildest)", fontweight="bold")
    ax.set_xlabel("MAE severity quartile")
    ax.set_ylabel("Share of trades that ended a win")
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.grid(axis="y", color=GRID)

    return len(valid)


def build_mae_recovery(df: pd.DataFrame, out: Path) -> Path | None:
    """MAE-focused page: how bad the worst point gets, and what happens after
    it. See _draw_mae_recovery_panels for the individual panel descriptions."""
    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    n = _draw_mae_recovery_panels(axes, df)
    if n is None:
        plt.close(fig)
        return None
    fig.suptitle(
        f"MAE analysis — distribution and recovery after the worst point ({n} trades)",
        fontsize=16, fontweight="bold", y=0.995,
    )

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_mae_recovery.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def build_occupancy_mae(df: pd.DataFrame, out: Path) -> Path | None:
    """Combined page: hold-timing occupancy + MAE distribution/recovery, laid
    out as a 5×2 grid with each MFE panel directly beside its MAE counterpart
    for easy side-by-side comparison:
      row 0 · profit occupancy          | share of days in profit
      row 1 · MFE $ distribution        | MAE $ distribution
      row 2 · MFE-day distribution      | MAE-day distribution
      row 3 · give-back after the peak  | recovery after the trough
      row 4 · cumulative recovery to breakeven | win rate by MAE severity quartile
    """
    fig, axes = plt.subplots(5, 2, figsize=(15, 27))
    occ_axes = [axes[0, 0], axes[1, 0], axes[3, 0], axes[2, 1], axes[2, 0], axes[0, 1]]
    mae_axes = [axes[1, 1], axes[3, 1], axes[4, 0], axes[4, 1]]
    n_total = _draw_occupancy_panels(occ_axes, df)
    n_mae = _draw_mae_recovery_panels(mae_axes, df, letters=("G", "H", "I", "J"))
    if n_total is None and n_mae is None:
        plt.close(fig)
        return None
    fig.suptitle(
        f"Occupancy + MAE — hold-timing and worst-point recovery ({n_total or n_mae} trades)",
        fontsize=16, fontweight="bold", y=0.995,
    )

    fig.tight_layout(rect=(0, 0, 1, 0.98))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_occupancy_mae.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def build_regime(df: pd.DataFrame, out: Path) -> Path:
    """Regime & regime-drift analysis — four panels:
      A · Market-regime label (BULL/BEAR/RANGE) vs mean P&L % + win rate
      B · Play (ticker) regime label vs mean P&L % + win rate
      C · Regime drift: aligned (market == play) vs drifted (market ≠ play)
      D · Cross-tab heatmap: market_label × play_label — mean P&L %
    """
    df = df.copy()
    df_both = df[df["mkt_label"].notna() & df["play_label"].notna() & df["realized_pnl"].notna()]

    LABEL_ORDER = ["BULL", "BEAR", "RANGE"]
    LABEL_COLORS = {"BULL": C_BULL, "BEAR": C_RANGE, "RANGE": C_MED}

    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    fig.suptitle(
        "Regime & regime-drift analysis — does context affect P&L?",
        fontsize=16, fontweight="bold", y=0.995,
    )

    def _bar_with_winrate(ax, groups, title, letter):
        """Bar = mean P&L %, overlaid line = win rate. groups: list of (label, subset_df)."""
        labels, means, wins, ns = [], [], [], []
        for label, sub in groups:
            r = sub["realized_pnl"].dropna()
            if r.empty:
                continue
            labels.append(label)
            means.append(r.mean())
            wins.append((r > 0).mean() * 100)
            ns.append(len(r))

        x = np.arange(len(labels))
        colors = [LABEL_COLORS.get(lb, C_BAR) for lb in labels]
        ax2 = ax.twinx()
        bars = ax.bar(x, means, color=colors, alpha=0.8)
        ax2.plot(x, wins, "D--", color="#555", lw=1.5, ms=7, zorder=5, label="Win rate %")
        ax2.axhline(50, color="#ccc", lw=0.7, ls=":")
        ax2.set_ylim(0, 105)
        ax2.set_ylabel("Win rate %", fontsize=8)
        for i, (b, m, w, n) in enumerate(zip(bars, means, wins, ns)):
            ax.annotate(f"{m:+.1f}%\nn={n}",
                        (b.get_x() + b.get_width() / 2, m),
                        textcoords="offset points",
                        xytext=(0, 8 if m >= 0 else -22),
                        ha="center", fontsize=8)
            ax2.annotate(f"{w:.0f}%", (i, w),
                         textcoords="offset points", xytext=(0, 7),
                         ha="center", fontsize=7, color="#555")
        ax.axhline(0, color="#999", lw=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("Mean realized P&L %")
        ax.yaxis.set_major_formatter(PercentFormatter(decimals=1))
        ax.set_title(f"{letter} · {title}", fontweight="bold")
        ax.grid(axis="y", color=GRID)

    # ---- A: P&L by MARKET regime label ----------------------------------------
    ax = axes[0, 0]
    grp_mkt = [(lb, df[df["mkt_label"] == lb]) for lb in LABEL_ORDER]
    _bar_with_winrate(ax, grp_mkt, "P&L by market-level regime", "A")

    # ---- B: P&L by PLAY (ticker) regime label ---------------------------------
    ax = axes[0, 1]
    grp_play = [(lb, df[df["play_label"] == lb]) for lb in LABEL_ORDER]
    _bar_with_winrate(ax, grp_play, "P&L by play (ticker) regime label", "B")

    # ---- C: Drift — aligned vs counter-consensus ------------------------------
    ax = axes[1, 0]
    grp_drift = [
        ("Aligned\n(market == play)", df_both[df_both["regime_aligned"]]),
        ("Drifted\n(market ≠ play)",  df_both[~df_both["regime_aligned"]]),
        ("HP in market\nregime",       df[df["hp_flag"]]),
        ("No HP",                      df[~df["hp_flag"]]),
    ]
    drift_labels, drift_means, drift_wins, drift_ns = [], [], [], []
    for label, sub in grp_drift:
        r = sub["realized_pnl"].dropna()
        if r.empty:
            continue
        drift_labels.append(label)
        drift_means.append(r.mean())
        drift_wins.append((r > 0).mean() * 100)
        drift_ns.append(len(r))
    x = np.arange(len(drift_labels))
    drift_colors = [C_RANGE, C_BULL, "#6a1b9a", "#9e9e9e"]
    ax2 = ax.twinx()
    bars = ax.bar(x, drift_means, color=drift_colors[:len(drift_labels)], alpha=0.8)
    ax2.plot(x, drift_wins, "D--", color="#555", lw=1.5, ms=7, zorder=5)
    ax2.axhline(50, color="#ccc", lw=0.7, ls=":")
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("Win rate %", fontsize=8)
    for b, m, _, n in zip(bars, drift_means, drift_wins, drift_ns):
        ax.annotate(f"{m:+.1f}%\nn={n}",
                    (b.get_x() + b.get_width() / 2, m),
                    textcoords="offset points",
                    xytext=(0, 8 if m >= 0 else -22),
                    ha="center", fontsize=8)
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(drift_labels, fontsize=8)
    ax.set_ylabel("Mean realized P&L %")
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=1))
    ax.set_title("C · Regime drift — aligned vs counter-consensus vs HP", fontweight="bold")
    ax.grid(axis="y", color=GRID)

    # ---- D: Cross-tab heatmap — market_label × play_label --------------------
    ax = axes[1, 1]
    piv = df_both.pivot_table(
        index="mkt_label", columns="play_label",
        values="realized_pnl", aggfunc="mean",
    )
    cnt = df_both.pivot_table(
        index="mkt_label", columns="play_label",
        values="realized_pnl", aggfunc="count",
    )
    piv = piv.reindex(index=LABEL_ORDER, columns=LABEL_ORDER)
    cnt = cnt.reindex(index=LABEL_ORDER, columns=LABEL_ORDER)
    vmax = np.nanmax(np.abs(piv.values)) if not np.all(np.isnan(piv.values)) else 1
    im = ax.imshow(piv.values, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(LABEL_ORDER)))
    ax.set_xticklabels(LABEL_ORDER)
    ax.set_yticks(range(len(LABEL_ORDER)))
    ax.set_yticklabels(LABEL_ORDER)
    ax.set_xlabel("Play (ticker) regime label")
    ax.set_ylabel("Market regime label")
    for i, mkt in enumerate(LABEL_ORDER):
        for j, play in enumerate(LABEL_ORDER):
            v = piv.loc[mkt, play] if mkt in piv.index and play in piv.columns else np.nan
            n = cnt.loc[mkt, play] if mkt in cnt.index and play in cnt.columns else np.nan
            if not np.isnan(v):
                ax.text(j, i, f"{v:+.1f}%\nn={int(n)}", ha="center", va="center",
                        fontsize=9, fontweight="bold", color="black")
            else:
                ax.text(j, i, "—", ha="center", va="center", color="#aaa")
    ax.set_title("D · Mean P&L % heatmap — market × play regime", fontweight="bold")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Mean P&L %")

    fig.tight_layout(rect=(0, 0, 1, 0.985))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_regime.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="backtests/results.csv")
    ap.add_argument("--out", default="backtests/charts")
    args = ap.parse_args()
    df = load(Path(args.csv))
    print(f"Wrote {build(df, Path(args.out))}")
    print(f"Wrote {build_ev(df, Path(args.out))}")
    print(f"Wrote {build_playbook(df, Path(args.out))}")
    spaghetti_png = build_spaghetti(df, Path(args.out))
    if spaghetti_png:
        print(f"Wrote {spaghetti_png}")
    paths_png = build_paths(df, Path(args.out))
    if paths_png:
        print(f"Wrote {paths_png}")
    else:
        print("No daily_price_csv column found — skipping path charts "
              "(re-run the backtest with the new engine to populate it).")
    occ_mae_png = build_occupancy_mae(df, Path(args.out))
    if occ_mae_png:
        print(f"Wrote {occ_mae_png}")
    print(f"Wrote {build_time(df, Path(args.out))}")
    print(f"Wrote {build_regime(df, Path(args.out))}")
    print(f"Wrote {build_mfe_mae_dist(df, Path(args.out))}")


if __name__ == "__main__":
    main()
