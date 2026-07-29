"""Analyse the cleaned options book: performance, edge, and position charts.

Reads ``portfolio/output/cleaned_trades.csv`` (written by ``01_cleanup.py``),
rolls the executions up to one row per strategy, and writes summary CSVs plus
chart boards to ``portfolio/output/``.

Charts are grouped into five boards — one PNG per question (book over time,
trade profile, strategy edge, strategy × DTE, underlyings) rather than one PNG
per plot, so related panels are read side by side.

Run ``01_cleanup.py`` first.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: write PNGs, never open a window

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CHART_DIR = OUTPUT_DIR / "charts"
CLEANED_PATH = OUTPUT_DIR / "cleaned_trades.csv"

# A strategy needs this many closed trades before it earns a row in the
# per-strategy edge charts — below it, the mean is one trade wearing a costume.
MIN_TRADES_STRATEGY = 5
MIN_TRADES_EXPECTANCY = 10
# Same idea per ticker: totals are readable at any n, but a rate or a
# per-trade average needs a denominator before it means anything.
MIN_TRADES_TICKER = 5

# Days to nearest expiry at entry. 0DTE is its own bucket rather than being
# swallowed by the short-term bin, and the top bin is open-ended so LEAPS count.
DTE_BINS = [-1, 0, 14, 45, np.inf]
DTE_LABELS = ["0DTE", "1-14d", "15-45d", "45d+"]

# --------------------------------------------------
# Style — validated palette, see the dataviz reference
# --------------------------------------------------

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e3e2df"

PROFIT = "#2a78d6"   # blue
LOSS = "#e34948"     # red
ACCENT = "#eb6834"   # orange
NEUTRAL = "#8a8985"

# Diverging (polarity, centred on zero) and sequential (magnitude) ramps.
DIVERGING = LinearSegmentedColormap.from_list("pnl", [LOSS, "#f0efec", PROFIT])
SEQUENTIAL = LinearSegmentedColormap.from_list("rate", ["#cde2fb", "#0d366b"])

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_MUTED,
    "axes.titlecolor": INK,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlepad": 12,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "text.color": INK,
    "font.size": 10,
    "legend.frameon": False,
    "figure.dpi": 110,
})


def style_axes(ax, grid_axis="both"):
    """Recessive frame: no top/right spines, grid on the measure axis only."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)

    ax.grid(False)
    if grid_axis in ("x", "both"):
        ax.xaxis.grid(True)
    if grid_axis in ("y", "both"):
        ax.yaxis.grid(True)

    ax.tick_params(length=0)  # the grid already locates the values


def save(fig, name):
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = CHART_DIR / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  board → {path.name}")


def clear_charts():
    """Charts are regenerated output — drop stale PNGs so old names never linger."""
    if CHART_DIR.exists():
        for stale in CHART_DIR.glob("*.png"):
            stale.unlink()


def board(figsize, title):
    """A board is one PNG holding several related panels."""
    fig = plt.figure(figsize=figsize, layout="constrained")
    fig.suptitle(title, fontsize=16, fontweight="bold", color=INK,
                 x=0.008, ha="left")

    return fig


def sign_colors(values):
    return [PROFIT if v >= 0 else LOSS for v in values]


def label_bars(ax, values, labels, fmt="{:,.0f}"):
    """Direct-label horizontal bars just outside the bar end."""
    span = max(abs(v) for v in values) if len(values) else 1
    pad = span * 0.02

    for y, (value, text) in enumerate(zip(values, labels)):
        offset = pad if value >= 0 else -pad
        ax.text(
            value + offset, y, text,
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=9, color=INK_MUTED,
        )


def add_expectancy(df):
    """Attach loss_rate + expectancy to a frame with win_rate/avg_win/avg_loss."""
    df = df.copy()
    df["avg_win"] = df["avg_win"].fillna(0)
    df["avg_loss"] = df["avg_loss"].fillna(0)
    df["loss_rate"] = 1 - df["win_rate"]
    df["expectancy"] = (
        df["win_rate"] * df["avg_win"] + df["loss_rate"] * df["avg_loss"]
    )
    return df


def expectancy_of(df):
    """Expectancy of a set of trades, for period-stability checks."""
    win_rate = (df.pnl > 0).mean()
    avg_win = df.loc[df.pnl > 0, "pnl"].mean()
    avg_loss = df.loc[df.pnl < 0, "pnl"].mean()

    return win_rate * np.nan_to_num(avg_win) + (1 - win_rate) * np.nan_to_num(avg_loss)


# --------------------------------------------------
# Load and roll up to one row per strategy
# --------------------------------------------------


def load_trades():
    if not CLEANED_PATH.exists():
        raise SystemExit(
            f"{CLEANED_PATH} not found — run 01_cleanup.py first."
        )

    df = pd.read_csv(CLEANED_PATH)
    df["FifoPnlRealized"] = pd.to_numeric(df["FifoPnlRealized"], errors="coerce")
    df["DTE"] = pd.to_numeric(df["DTE"], errors="coerce")
    df["DateTime"] = pd.to_datetime(df["DateTime"], format="%Y-%m-%d;%H%M%S")
    df["Expiry"] = pd.to_datetime(df["Expiry"])

    return df


def build_trade_frame(df):
    """One row per strategy: entry/exit, P&L, and whether the position is flat."""
    # Horizon of the position = nearest expiry on the opening execution.
    opens = df[df["lifecycle"] == "OPEN"]
    entry_dte = opens.groupby("strategyId")["DTE"].min()

    trades = df.groupby("strategyId").agg(
        ticker=("UnderlyingSymbol", "first"),
        Strategy=("StrategyLabel", "first"),
        pnl=("FifoPnlRealized", "sum"),
        net_qty=("Quantity", "sum"),
        legs=("Quantity", "size"),
        entry_time=("DateTime", "min"),
        exit_time=("DateTime", "max"),
        last_expiry=("Expiry", "max"),
    )

    trades["DTE"] = entry_dte
    trades["holding_days"] = (
        trades["exit_time"] - trades["entry_time"]
    ).dt.total_seconds() / 86400
    trades["win"] = trades["pnl"] > 0

    # A position is still on only if it has residual quantity AND has not expired.
    today = pd.Timestamp.today().normalize()
    trades["is_open"] = (trades["net_qty"] != 0) & (trades["last_expiry"] >= today)

    trades["DTE_bucket"] = pd.cut(trades["DTE"], bins=DTE_BINS, labels=DTE_LABELS)

    return trades.reset_index()


# --------------------------------------------------
# Summary tables
# --------------------------------------------------


def strategy_summary(closed):
    summary = closed.groupby("Strategy").agg(
        trades=("pnl", "count"),
        total_pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        median_pnl=("pnl", "median"),
        max_pnl=("pnl", "max"),
        min_pnl=("pnl", "min"),
        win_rate=("win", "mean"),
        avg_win=("pnl", lambda s: s[s > 0].mean()),
        avg_loss=("pnl", lambda s: s[s < 0].mean()),
        avg_holding_days=("holding_days", "mean"),
    )

    return add_expectancy(summary).sort_values("total_pnl", ascending=False)


def ticker_summary(closed):
    summary = closed.groupby("ticker").agg(
        trades=("pnl", "count"),
        total_pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        max_win=("pnl", "max"),
        max_loss=("pnl", "min"),
        win_rate=("win", "mean"),
        avg_win=("pnl", lambda s: s[s > 0].mean()),
        avg_loss=("pnl", lambda s: s[s < 0].mean()),
    )

    return add_expectancy(summary).sort_values("total_pnl", ascending=False)


def print_headline(closed):
    total = closed["pnl"].sum()
    wins = closed[closed.pnl > 0]
    losses = closed[closed.pnl < 0]

    print("\n--- Book ---")
    print(f"Closed trades:      {len(closed)}")
    print(f"Total realized P&L: {total:,.2f}")
    print(f"Win rate:           {closed['win'].mean():.1%}")
    print(f"Average win:        {wins['pnl'].mean():,.2f}")
    print(f"Average loss:       {losses['pnl'].mean():,.2f}")
    print(f"Expectancy/trade:   {expectancy_of(closed):,.2f}")
    print(f"Avg hold, winners:  {wins['holding_days'].mean():.1f} days")
    print(f"Avg hold, losers:   {losses['holding_days'].mean():.1f} days")

    # Edge stability: split chronologically, not by the frame's sort order.
    half = len(closed) // 2
    print("\n--- Edge stability (chronological) ---")
    print(f"First half expectancy:  {expectancy_of(closed.iloc[:half]):,.2f}")
    print(f"Second half expectancy: {expectancy_of(closed.iloc[half:]):,.2f}")

    for i, bounds in enumerate(np.array_split(np.arange(len(closed)), 4), start=1):
        part = closed.iloc[bounds]
        print(f"Q{i} expectancy: {expectancy_of(part):,.2f}  (n={len(part)})")


# --------------------------------------------------
# Panels — book level
#
# Every panel draws onto axes handed to it; the boards below own the figures.
# --------------------------------------------------


def panel_pnl_distribution(closed, ax_full, ax_trimmed):
    ax_full.hist(closed["pnl"], bins=50, color=PROFIT, edgecolor=SURFACE, linewidth=0.5)
    ax_full.set_title("Full P&L distribution")

    lower = closed["pnl"].quantile(0.02)
    upper = closed["pnl"].quantile(0.98)
    trimmed = closed[(closed.pnl >= lower) & (closed.pnl <= upper)]

    ax_trimmed.hist(trimmed["pnl"], bins=50, color=PROFIT, edgecolor=SURFACE,
                    linewidth=0.5)
    ax_trimmed.set_title("P&L distribution (2–98th percentile)")

    for ax in (ax_full, ax_trimmed):
        ax.axvline(0, color=INK_MUTED, linewidth=1)
        ax.set_xlabel("P&L per trade ($)")
        ax.set_ylabel("Trades")
        style_axes(ax, grid_axis="y")


def panel_equity_curve(closed, ax_equity, ax_drawdown):
    """Cumulative P&L on calendar time, with the drawdown underneath."""
    curve = closed.sort_values("exit_time")
    cum = curve["pnl"].cumsum()
    drawdown = cum - cum.cummax()

    ax_equity.plot(curve["exit_time"], cum, color=PROFIT, linewidth=2)
    ax_equity.axhline(0, color=INK_MUTED, linewidth=1)
    ax_equity.set_ylabel("Cumulative P&L ($)")
    ax_equity.set_title("Equity curve and drawdown")
    ax_equity.tick_params(labelbottom=False)  # the drawdown panel carries the dates
    ax_equity.annotate(
        f"closes at ${cum.iloc[-1]:,.0f}",
        xy=(curve["exit_time"].iloc[-1], cum.iloc[-1]),
        xytext=(-8, 26), textcoords="offset points",
        ha="right", fontsize=11, fontweight="bold", color=PROFIT,
        bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 2},
    )

    ax_drawdown.fill_between(curve["exit_time"], drawdown, 0, color=LOSS, alpha=0.35)
    ax_drawdown.plot(curve["exit_time"], drawdown, color=LOSS, linewidth=1.5)
    ax_drawdown.set_ylabel("Drawdown ($)")
    ax_drawdown.set_xlabel("Exit date")
    ax_drawdown.annotate(
        f"max ${drawdown.min():,.0f}",
        xy=(curve["exit_time"].iloc[drawdown.values.argmin()], drawdown.min()),
        xytext=(6, -2), textcoords="offset points",
        fontsize=9, color=LOSS,
    )

    for ax in (ax_equity, ax_drawdown):
        style_axes(ax, grid_axis="y")


def panel_monthly_pnl(closed, ax):
    monthly = (
        closed.set_index("exit_time")["pnl"]
        .resample("ME").sum()
    )
    labels = monthly.index.strftime("%b %y")

    ax.bar(labels, monthly.values, color=sign_colors(monthly.values), width=0.7)
    ax.axhline(0, color=INK_MUTED, linewidth=1)
    ax.set_title("Realized P&L by month")
    ax.set_ylabel("P&L ($)")
    ax.tick_params(axis="x", rotation=45)
    style_axes(ax, grid_axis="y")

    for x, value in enumerate(monthly.values):
        ax.text(
            x, value, f"{value:,.0f}",
            ha="center", va="bottom" if value >= 0 else "top",
            fontsize=8, color=INK_MUTED,
        )


def panel_pnl_concentration(closed, ax):
    """How much of the book comes from how few trades.

    Trades ranked best to worst, cumulated. The curve peaks at total gross
    profit, then the losers drag it down to the net result — so the gap between
    the peak and the net line is what the losing trades cost.
    """
    ranked = closed.sort_values("pnl", ascending=False).reset_index(drop=True)
    cum = ranked["pnl"].cumsum()
    gross_profit = closed.loc[closed.pnl > 0, "pnl"].sum()
    net = closed["pnl"].sum()
    x = np.arange(1, len(ranked) + 1)

    ax.plot(x, cum, color=PROFIT, linewidth=2)
    ax.axhline(net, color=INK_MUTED, linewidth=1, linestyle="--")
    ax.annotate(
        f"net book ${net:,.0f}",
        xy=(len(ranked), net), xytext=(-4, 8), textcoords="offset points",
        ha="right", fontsize=9, color=INK_MUTED,
    )

    peak = int(cum.values.argmax())
    ax.annotate(
        f"gross profit ${gross_profit:,.0f} after {peak + 1} winners",
        xy=(peak + 1, cum.iloc[peak]), xytext=(0, 14), textcoords="offset points",
        ha="center", fontsize=9, color=INK_MUTED,
    )

    ax.set_title("P&L concentration: trades ranked best to worst, cumulated")
    ax.set_xlabel("Trades ranked best to worst")
    ax.set_ylabel("Cumulative P&L ($)")
    style_axes(ax, grid_axis="y")

    for n in (10, 25):
        if n <= len(ranked):
            value = cum.iloc[n - 1]
            ax.plot([n], [value], marker="o", markersize=8, color=ACCENT,
                    markeredgecolor=SURFACE, markeredgewidth=2)
            ax.annotate(
                f"top {n}: ${value:,.0f} ({value / gross_profit:.0%} of gross profit)",
                xy=(n, value), xytext=(12, -10), textcoords="offset points",
                fontsize=9, color=INK_MUTED,
            )


def panel_holding_days(closed, ax):
    """Are winners cut short and losers held? The classic behaviour check.

    Holding time is heavily right-skewed, so it is bucketed on uneven edges and
    drawn as paired bars — overlapping histograms just muddy into one colour.
    """
    edges = [0, 1, 2, 3, 5, 7, 10, 14, 21, 30, 45, np.inf]
    labels = ["<1d", "1-2d", "2-3d", "3-5d", "5-7d", "7-10d",
              "10-14d", "14-21d", "21-30d", "30-45d", "45d+"]

    bucket = pd.cut(closed["holding_days"], bins=edges, labels=labels,
                    right=False, include_lowest=True)
    counts = pd.crosstab(bucket, closed["win"])
    winners = counts.get(True, pd.Series(0, index=labels)).reindex(labels, fill_value=0)
    losers = counts.get(False, pd.Series(0, index=labels)).reindex(labels, fill_value=0)

    x = np.arange(len(labels))
    width = 0.4

    ax.bar(x - width / 2 - 0.01, winners.values, width, color=PROFIT, label="Winners")
    ax.bar(x + width / 2 + 0.01, losers.values, width, color=LOSS, label="Losers")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title("Holding period: winners vs losers")
    ax.set_xlabel("Holding time")
    ax.set_ylabel("Trades")
    ax.legend()
    style_axes(ax, grid_axis="y")

    win_median = closed.loc[closed.pnl > 0, "holding_days"].median()
    loss_median = closed.loc[closed.pnl < 0, "holding_days"].median()
    ax.text(
        0.98, 0.86,
        f"Median hold — winners {win_median:.1f}d · losers {loss_median:.1f}d",
        transform=ax.transAxes, ha="right", fontsize=10, color=INK_MUTED,
    )


def panel_open_exposure(trades, ax):
    """How many strategies (and underlyings) were live on any given day."""
    days = pd.date_range(
        trades["entry_time"].min().normalize(),
        trades["exit_time"].max().normalize(),
        freq="D",
    )

    live_strategies = []
    live_tickers = []
    entry = trades["entry_time"].values
    exit_ = trades["exit_time"].values

    for day in days:
        mask = (entry <= day.to_datetime64()) & (exit_ >= day.to_datetime64())
        live_strategies.append(int(mask.sum()))
        live_tickers.append(trades.loc[mask, "ticker"].nunique())

    ax.step(days, live_strategies, where="post", color=PROFIT, linewidth=1.8,
            label="Open strategies")
    ax.step(days, live_tickers, where="post", color=ACCENT, linewidth=1.8,
            label="Distinct underlyings")

    peak = int(np.max(live_strategies))
    peak_day = days[int(np.argmax(live_strategies))]
    ax.annotate(
        f"peak {peak} on {peak_day:%d %b %y}",
        xy=(peak_day, peak), xytext=(8, 4), textcoords="offset points",
        fontsize=9, color=INK_MUTED,
    )

    ax.set_title("Concurrent open positions over time")
    ax.set_ylabel("Count")
    ax.set_xlabel("Date")
    ax.legend()
    style_axes(ax, grid_axis="y")


# --------------------------------------------------
# Panels — strategy level
# --------------------------------------------------


def panel_strategy_pnl(summary, ax):
    data = summary.sort_values("total_pnl")

    ax.barh(data.index, data["total_pnl"], color=sign_colors(data["total_pnl"]),
            height=0.72)
    ax.axvline(0, color=INK_MUTED, linewidth=1)
    ax.set_title("Total P&L by strategy")
    ax.set_xlabel("Total P&L ($)")
    label_bars(ax, data["total_pnl"].values,
               [f"{v:,.0f}  (n={n})" for v, n in zip(data["total_pnl"], data["trades"])])
    ax.margins(x=0.18)
    style_axes(ax, grid_axis="x")


def panel_strategy_win_rate(summary, ax_rate, ax_profile):
    """Win rate and P&L profile as two panels — never two scales on one axis."""
    # A win rate needs a denominator: one-trade strategies would all read 0/100%.
    data = summary[summary["trades"] >= MIN_TRADES_STRATEGY].sort_values("win_rate")

    ax_rate.barh(data.index, data["win_rate"] * 100, color=PROFIT, height=0.72)
    ax_rate.axvline(50, color=INK_MUTED, linewidth=1, linestyle="--")
    ax_rate.set_title(f"Win rate by strategy (≥{MIN_TRADES_STRATEGY} trades)")
    ax_rate.set_xlabel("Win rate (%)")
    label_bars(ax_rate, (data["win_rate"] * 100).values,
               [f"{v:.0f}%  (n={n})" for v, n in zip(data["win_rate"] * 100, data["trades"])])
    ax_rate.margins(x=0.22)

    y = np.arange(len(data))
    ax_profile.hlines(y, data["min_pnl"], data["max_pnl"], color=GRID, linewidth=3)
    ax_profile.scatter(data["min_pnl"], y, color=LOSS, s=55, label="Worst trade",
                       edgecolor=SURFACE, linewidth=1.5, zorder=3)
    ax_profile.scatter(data["max_pnl"], y, color=PROFIT, s=55, label="Best trade",
                       edgecolor=SURFACE, linewidth=1.5, zorder=3)
    ax_profile.scatter(data["avg_pnl"], y, color=INK, s=45, marker="D", label="Average",
                       edgecolor=SURFACE, linewidth=1.5, zorder=4)
    ax_profile.axvline(0, color=INK_MUTED, linewidth=1)
    ax_profile.set_title("P&L profile")
    ax_profile.set_xlabel("P&L ($)")
    ax_profile.legend(loc="lower right")
    ax_profile.tick_params(labelleft=False)  # names already on the win-rate panel

    for ax in (ax_rate, ax_profile):
        style_axes(ax, grid_axis="x")


def panel_strategy_expectancy(summary, ax):
    data = summary[summary["trades"] >= MIN_TRADES_EXPECTANCY].sort_values("expectancy")

    ax.barh(data.index, data["expectancy"], color=sign_colors(data["expectancy"]),
            height=0.7)
    ax.axvline(0, color=INK_MUTED, linewidth=1)
    ax.set_title(f"Expectancy per trade (strategies with ≥{MIN_TRADES_EXPECTANCY} trades)")
    ax.set_xlabel("Expectancy ($ per trade)")
    label_bars(ax, data["expectancy"].values,
               [f"{v:,.0f}  (n={n})" for v, n in zip(data["expectancy"], data["trades"])])
    ax.margins(x=0.2)
    style_axes(ax, grid_axis="x")


def panel_edge_map(summary, ax):
    data = summary[summary["trades"] >= MIN_TRADES_EXPECTANCY]

    ax.scatter(
        data["win_rate"] * 100, data["expectancy"],
        s=data["trades"] * 6, color=PROFIT, alpha=0.75,
        edgecolor=SURFACE, linewidth=2, zorder=3,
    )
    ax.axhline(0, color=INK_MUTED, linewidth=1)
    ax.axvline(50, color=INK_MUTED, linewidth=1, linestyle="--")

    # Label clear of the bubble radius, alternating above/below in win-rate order
    # so neighbouring points never put their labels on the same side.
    ordered = data.sort_values("win_rate")
    for i, (name, row) in enumerate(ordered.iterrows()):
        gap = 8 + np.sqrt(row["trades"] * 6) / 2
        above = i % 2 == 0
        ax.annotate(
            f"{name}\n(n={row['trades']:.0f})",
            xy=(row["win_rate"] * 100, row["expectancy"]),
            xytext=(0, gap if above else -gap - 4), textcoords="offset points",
            ha="center", va="bottom" if above else "top",
            fontsize=9, color=INK_MUTED,
        )

    ax.set_title("Strategy edge map — bubble size is trade count")
    ax.set_xlabel("Win rate (%)")
    ax.set_ylabel("Expectancy ($ per trade)")
    ax.margins(x=0.22, y=0.15)
    style_axes(ax)


def panel_heatmap(table, ax, title, fmt, cmap, center=None, cbar_label="",
                  show_names=True):
    sns.heatmap(
        table, annot=True, fmt=fmt, cmap=cmap, center=center,
        linewidths=2, linecolor=SURFACE, ax=ax,
        annot_kws={"fontsize": 9},
        cbar_kws={"label": cbar_label, "shrink": 0.8},
    )
    ax.set_title(title)
    ax.set_xlabel("Days to nearest expiry at entry")
    ax.set_ylabel("")
    ax.tick_params(left=False, bottom=False)
    if not show_names:  # side-by-side panels share one set of row labels
        ax.tick_params(labelleft=False)


def dte_tables(closed, summary):
    """The three strategy × DTE views, keyed by the panel they feed."""
    keep = summary[summary["trades"] >= MIN_TRADES_STRATEGY].index
    data = closed[closed["Strategy"].isin(keep)]

    grouped = data.groupby(["Strategy", "DTE_bucket"], observed=True).agg(
        win_rate=("win", "mean"),
        avg_win=("pnl", lambda s: s[s > 0].mean()),
        avg_loss=("pnl", lambda s: s[s < 0].mean()),
    )

    return {
        "pnl": data.pivot_table(
            values="pnl", index="Strategy", columns="DTE_bucket",
            aggfunc="mean", observed=False,
        ),
        "win": data.pivot_table(
            values="win", index="Strategy", columns="DTE_bucket",
            aggfunc="mean", observed=False,
        ),
        "expectancy": add_expectancy(grouped).reset_index().pivot(
            index="Strategy", columns="DTE_bucket", values="expectancy",
        ),
    }


# --------------------------------------------------
# Panels — ticker level
# --------------------------------------------------


def panel_ticker(summary, ax, column, title, xlabel, fmt="{:,.0f}", top=10,
                 min_trades=1):
    eligible = summary[summary["trades"] >= min_trades]
    focus = pd.concat([
        eligible.nlargest(top, column),
        eligible.nsmallest(top, column),
    ])
    focus = focus[~focus.index.duplicated()].sort_values(column)

    ax.barh(focus.index, focus[column], color=sign_colors(focus[column]), height=0.72)
    ax.axvline(0, color=INK_MUTED, linewidth=1)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    label_bars(ax, focus[column].values,
               [f"{fmt.format(v)}  (n={n})" for v, n in zip(focus[column], focus["trades"])])
    ax.margins(x=0.2)
    style_axes(ax, grid_axis="x")


# --------------------------------------------------
# Boards — one PNG per question, panels grouped by what they answer
# --------------------------------------------------


def board_book_timeline(closed, trades):
    """Did the book make money, when, and how much was on at once?"""
    fig = board((13, 16), "Book over time")
    gs = fig.add_gridspec(4, 1, height_ratios=[2.2, 1.0, 1.6, 1.6])

    ax_equity = fig.add_subplot(gs[0])
    ax_drawdown = fig.add_subplot(gs[1], sharex=ax_equity)
    panel_equity_curve(closed, ax_equity, ax_drawdown)
    panel_monthly_pnl(closed, fig.add_subplot(gs[2]))
    panel_open_exposure(trades, fig.add_subplot(gs[3]))

    save(fig, "01_book_timeline")


def board_trade_profile(closed):
    """What does a single trade look like, and where does the P&L come from?"""
    fig = board((13, 16), "Trade profile — distribution, concentration, holding time")
    gs = fig.add_gridspec(3, 2, height_ratios=[1.1, 1.4, 1.3])

    panel_pnl_distribution(closed, fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]))
    panel_pnl_concentration(closed, fig.add_subplot(gs[1, :]))
    panel_holding_days(closed, fig.add_subplot(gs[2, :]))

    save(fig, "02_trade_profile")


def board_strategy_edge(summary):
    """Which structures actually carry an edge."""
    n_rate = int((summary["trades"] >= MIN_TRADES_STRATEGY).sum())
    n_exp = int((summary["trades"] >= MIN_TRADES_EXPECTANCY).sum())

    h_total = max(4.5, 0.30 * len(summary))
    h_rate = max(4.0, 0.34 * n_rate)
    h_exp = max(5.0, 0.42 * n_exp)

    fig = board((16, h_total + h_rate + h_exp + 2), "Strategy edge")
    gs = fig.add_gridspec(3, 2, height_ratios=[h_total, h_rate, h_exp])

    panel_strategy_pnl(summary, fig.add_subplot(gs[0, :]))

    ax_rate = fig.add_subplot(gs[1, 0])
    panel_strategy_win_rate(summary, ax_rate, fig.add_subplot(gs[1, 1], sharey=ax_rate))

    panel_strategy_expectancy(summary, fig.add_subplot(gs[2, 0]))
    panel_edge_map(summary, fig.add_subplot(gs[2, 1]))

    save(fig, "03_strategy_edge")


def board_strategy_dte(closed, summary):
    """The same strategies cut by holding horizon — three reads, one grid."""
    tables = dte_tables(closed, summary)
    suffix = f"(≥{MIN_TRADES_STRATEGY} trades)"

    fig = board((20, max(5.5, 0.5 * len(tables["pnl"])) + 1.5),
                f"Strategy × DTE {suffix}")
    axes = fig.subplots(1, 3)

    panel_heatmap(tables["pnl"], axes[0], "Average P&L", ".0f", DIVERGING,
                  center=0, cbar_label="Avg P&L ($)")
    panel_heatmap(tables["win"], axes[1], "Win rate", ".2f", SEQUENTIAL,
                  cbar_label="Win rate", show_names=False)
    panel_heatmap(tables["expectancy"], axes[2], "Expectancy", ".0f", DIVERGING,
                  center=0, cbar_label="Expectancy ($)", show_names=False)

    save(fig, "04_strategy_dte")


def board_tickers(summary):
    """Where the money came from by underlying — total, then the per-trade reads."""
    # A total is meaningful at any trade count; the per-trade views are not.
    rate_note = f"≥{MIN_TRADES_TICKER} trades"

    win = summary.copy()
    win["win_rate_pct"] = win["win_rate"] * 100

    fig = board((18, 15), "Underlyings — top and bottom 10 on each measure")
    axes = fig.subplots(2, 2)

    panel_ticker(summary, axes[0][0], "total_pnl", "Total P&L by ticker",
                 "Total P&L ($)")
    panel_ticker(summary, axes[0][1], "avg_pnl",
                 f"Average P&L per trade ({rate_note})", "Average P&L ($)",
                 min_trades=MIN_TRADES_TICKER)
    panel_ticker(win, axes[1][0], "win_rate_pct", f"Win rate ({rate_note})",
                 "Win rate (%)", fmt="{:.0f}%", min_trades=MIN_TRADES_TICKER)
    panel_ticker(summary, axes[1][1], "expectancy", f"Expectancy ({rate_note})",
                 "Expectancy ($ per trade)", min_trades=MIN_TRADES_TICKER)

    save(fig, "05_tickers")


# --------------------------------------------------


def write_open_positions(df, trades):
    """The positions still on the book — a table, not a chart."""
    open_ids = trades.loc[trades["is_open"], "strategyId"]
    legs = df[df["strategyId"].isin(open_ids)].copy()

    columns = [
        "strategyId", "UnderlyingSymbol", "StrategyLabel", "Description",
        "Put/Call", "Strike", "Expiry", "Quantity", "TradePrice",
        "DateTime", "lifecycle", "FifoPnlRealized",
    ]
    legs = legs[columns].sort_values(["strategyId", "DateTime"])
    legs.to_csv(OUTPUT_DIR / "open_positions.csv", index=False)

    print(f"\n--- Open positions ({len(open_ids)}) ---")
    if len(open_ids):
        print(trades.loc[trades["is_open"], [
            "strategyId", "ticker", "Strategy", "net_qty", "pnl",
            "entry_time", "last_expiry",
        ]].to_string(index=False))


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    df = load_trades()
    trades = build_trade_frame(df)

    closed = trades[~trades["is_open"]].sort_values("exit_time").reset_index(drop=True)
    print(f"Strategies: {len(trades)}  ({len(closed)} closed, "
          f"{int(trades['is_open'].sum())} open)")

    print_headline(closed)

    strategies = strategy_summary(closed)
    tickers = ticker_summary(closed)

    trades.to_csv(OUTPUT_DIR / "trade_summary.csv", index=False)
    strategies.to_csv(OUTPUT_DIR / "strategy_summary.csv")
    tickers.to_csv(OUTPUT_DIR / "ticker_summary.csv")
    write_open_positions(df, trades)

    print("\n--- Charts ---")
    clear_charts()
    board_book_timeline(closed, trades)
    board_trade_profile(closed)
    board_strategy_edge(strategies)
    board_strategy_dte(closed, strategies)
    board_tickers(tickers)

    print(f"\nWritten to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
