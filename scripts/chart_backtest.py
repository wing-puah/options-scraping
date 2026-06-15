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

# muted, print-friendly palette
C_BULL = "#2e7d32"
C_RANGE = "#c62828"
C_LINE = "#1f4e79"
C_MED = "#e08a1e"
C_BAR = "#5b8db8"
GRID = "#dddddd"


_CREDIT_STRUCTURES = {"bull_put_spread", "bear_call_spread", "short_put",
                      "short_call", "iron_condor"}


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
    """Per-day P&L % path derived from the stored daily price marks vs entry,
    respecting credit-structure sign. Empty when no daily series is stored."""
    prices = _parse_path(row.get("daily_price_csv"))
    entry = row.get("entry_option_price")
    if not prices or not entry or entry == 0:
        return []
    is_credit = row.get("structure") in _CREDIT_STRUCTURES
    if is_credit:
        return [(entry - p) / entry * 100 for p in prices]
    return [(p - entry) / entry * 100 for p in prices]


def pnl_at(path: list[float], n: int) -> float:
    """P&L % after holding n trading days, sampled from the daily path. Carries
    the last available mark forward when the path ended before day n."""
    if not path:
        return np.nan
    return path[n - 1] if len(path) >= n else path[-1]


def load(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df["regime_label"] = df["regime"].str.extract(r"^(BULL|BEAR|RANGE)")
    # The backtest writes the authoritative realized exit; all P&L is path-derived.
    df["realized_pnl"] = pd.to_numeric(df["realized_pnl_pct"], errors="coerce")
    df["realized_abs"] = pd.to_numeric(df.get("realized_pnl_abs"), errors="coerce")
    df["pnl_path"] = df.apply(pnl_path, axis=1)
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
    # Per-trading-day-checkpoint P&L, sampled from each play's daily path.
    cp = {n: df["pnl_path"].apply(lambda p: pnl_at(p, n)) for n in TD_CHECKPOINTS}

    fig, axes = plt.subplots(3, 2, figsize=(15, 16))
    fig.suptitle(
        f"Options Backtest — {len(df)} plays, "
        f"{df.signal_date.min():%b %Y}–{df.signal_date.max():%b %Y}",
        fontsize=17,
        fontweight="bold",
        y=0.995,
    )

    # ---- A: mean & median P&L vs holding horizon -----------------------
    ax = axes[0, 0]
    xs = TD_CHECKPOINTS
    means = [cp[n].mean() for n in xs]
    meds = [cp[n].median() for n in xs]
    ax.axhline(0, color="#999", lw=0.8)
    ax.plot(xs, means, "-o", color=C_LINE, lw=2, label="Mean")
    ax.plot(xs, meds, "--s", color=C_MED, lw=2, label="Median")
    for x, m in zip(xs, means):
        ax.annotate(f"{m:+.0f}%", (x, m), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8, color=C_LINE)
    ax.set_title("A · P&L vs holding period (all plays)", fontweight="bold")
    ax.set_xlabel("Trading days held")
    ax.set_ylabel("P&L %")
    ax.set_xticks(xs)
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
    ax.grid(axis="y", color=GRID)

    def _cp_means(sub):
        sp = sub["pnl_path"]
        return [sp.apply(lambda p: pnl_at(p, n)).mean() for n in TD_CHECKPOINTS]

    # ---- C: regime comparison ------------------------------------------
    ax = axes[1, 0]
    ax.axhline(0, color="#999", lw=0.8)
    for label, color in [("BULL", C_BULL), ("RANGE", C_RANGE)]:
        sub = df[df["regime_label"] == label]
        if sub.empty:
            continue
        ax.plot(xs, _cp_means(sub), "-o", color=color, lw=2,
                label=f"{label} (n={len(sub)})")
    ax.set_title("C · Mean P&L by regime read", fontweight="bold")
    ax.set_xlabel("Trading days held")
    ax.set_ylabel("Mean P&L %")
    ax.set_xticks(xs)
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
    ax.set_title("D · Mean P&L by structure", fontweight="bold")
    ax.set_xlabel("Trading days held")
    ax.set_ylabel("Mean P&L %")
    ax.set_xticks(xs)
    ax.legend(fontsize=8)
    ax.grid(color=GRID)

    # ---- E: realized exit P&L distribution -----------------------------
    ax = axes[2, 0]
    r = df["realized_pnl"].dropna()
    ax.hist(r, bins=np.arange(-110, 340, 20), color=C_BAR, edgecolor="white")
    ax.axvline(0, color="#999", lw=1)
    ax.axvline(r.mean(), color=C_MED, lw=2,
               label=f"mean {r.mean():+.0f}%")
    ax.axvline(r.median(), color=C_LINE, lw=2, ls="--",
               label=f"median {r.median():+.0f}%")
    win = (r > 0).mean() * 100
    ax.set_title(f"E · Realized exit P&L  (win {win:.0f}%, n={len(r)})",
                 fontweight="bold")
    ax.set_xlabel("Realized P&L % (first close, else last open mark)")
    ax.set_ylabel("Plays")
    ax.legend()
    ax.grid(axis="y", color=GRID)

    # ---- F: per-ticker mean realized P&L -------------------------------
    ax = axes[2, 1]
    by_t = df.groupby("ticker")["realized_pnl"].mean().sort_values()
    colors = [C_BULL if v >= 0 else C_RANGE for v in by_t.values]
    ax.barh(by_t.index, by_t.values, color=colors)
    ax.axvline(0, color="#999", lw=0.8)
    ax.set_title("F · Mean realized P&L by ticker", fontweight="bold")
    ax.set_xlabel("Mean realized P&L %")
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(axis="x", color=GRID)

    # percent on the value axes only (not the E histogram count or F x-tickers)
    for ax in (axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1]):
        ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    axes[2, 0].xaxis.set_major_formatter(PercentFormatter(decimals=0))
    axes[2, 1].xaxis.set_major_formatter(PercentFormatter(decimals=0))

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

    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    fig.suptitle("Daily-path analysis — realized exits, excursions, exit tuning",
                 fontsize=16, fontweight="bold", y=0.995)

    # ---- A: mean P&L vs trading days held (continuous), with IQR band --------
    ax = axes[0, 0]
    maxlen = max(len(p) for p in paths)
    horizon = min(maxlen, 63)  # ~3 months of sessions keeps the tail readable
    days = np.arange(1, horizon + 1)
    mean_c, lo_c, hi_c, n_c = [], [], [], []
    for i in range(horizon):
        vals = np.array([p[i] for p in paths if len(p) > i])
        mean_c.append(vals.mean())
        lo_c.append(np.percentile(vals, 25))
        hi_c.append(np.percentile(vals, 75))
        n_c.append(len(vals))
    ax.axhline(0, color="#999", lw=0.8)
    ax.fill_between(days, lo_c, hi_c, color=C_BAR, alpha=0.25, label="IQR (25–75%)")
    ax.plot(days, mean_c, "-", color=C_LINE, lw=2, label="Mean P&L")
    peak = int(np.argmax(mean_c))
    ax.plot(peak + 1, mean_c[peak], "o", color=C_MED, ms=8,
            label=f"peak day {peak + 1} ({mean_c[peak]:+.0f}%)")
    ax.set_title("A · Mean live P&L vs trading days held", fontweight="bold")
    ax.set_xlabel("Trading days since entry")
    ax.set_ylabel("P&L %")
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
    ax.set_title(f"B · EV % by exit rule (best: +{targets[best[1]]}% / "
                 f"-{stops[best[0]]}%)", fontweight="bold")
    ax.set_xlabel("Profit target")
    ax.set_ylabel("Stop loss")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Mean EV %")

    # ---- C: MFE vs MAE scatter, colored by realized outcome ------------------
    ax = axes[1, 0]
    if "mfe_pct" in df.columns and "mae_pct" in df.columns:
        mfe = pd.to_numeric(df["mfe_pct"], errors="coerce")
        mae = pd.to_numeric(df["mae_pct"], errors="coerce")
        win = df["realized_pnl"] > 0
        ax.scatter(mae[win], mfe[win], s=30, color=C_BULL, alpha=0.6,
                   edgecolor="white", linewidth=0.5, label="realized win")
        ax.scatter(mae[~win], mfe[~win], s=30, color=C_RANGE, alpha=0.6,
                   edgecolor="white", linewidth=0.5, label="realized loss")
        ax.axhline(0, color="#999", lw=0.8)
        ax.axvline(0, color="#999", lw=0.8)
        ax.set_title("C · Max favorable vs max adverse excursion", fontweight="bold")
        ax.set_xlabel("MAE % (worst the trade got)")
        ax.set_ylabel("MFE % (best the trade got)")
        ax.legend(fontsize=8)
        ax.grid(color=GRID)
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

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "backtest_paths.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="downloads/analysis - BacktestResults.csv")
    ap.add_argument("--out", default="downloads/charts")
    args = ap.parse_args()
    df = load(Path(args.csv))
    print(f"Wrote {build(df, Path(args.out))}")
    print(f"Wrote {build_ev(df, Path(args.out))}")
    paths_png = build_paths(df, Path(args.out))
    if paths_png:
        print(f"Wrote {paths_png}")
    else:
        print("No daily_price_csv column found — skipping path charts "
              "(re-run the backtest with the new engine to populate it).")


if __name__ == "__main__":
    main()
