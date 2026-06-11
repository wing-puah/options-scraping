"""
Market-level daily baseline: one row per trading date, accumulated in the
`BaselineDaily` Google Sheets tab, so the regime call can compare *today*
against a trailing distribution instead of reading a single day in isolation.

Index put premium dominating call premium is the unconditional norm (books are
hedged with puts every day), so "puts > calls" alone carries no regime
information. What does is where today's balance sits in its own recent history
— that is what this module computes.

Three layers, all pure functions over already-parsed CSV rows / sheet rows:

- `compute_daily_baseline(date, stocks_rows, etfs_rows)` — one sheet-row dict
  of market-level aggregates for a date (section C/P by premium / size / count,
  hedging breadth, key-ticker premiums, premium-weighted DTE / IV).
- `select_window(history, anchor)` — the trailing comparison window, staleness-
  aware: Drive history comes in islands (e.g. Jan-2025 + May-2026), and a
  16-month-old island must not pollute "recent" percentiles.
- `baseline_context_md(today, history, anchor)` — the `## Baseline context`
  markdown section injected into the LLM rollup by prepare_analysis.

Writing/reading the tab itself lives in scripts/build_baseline.py and
lib/sheets_client.py; nothing here touches the network.
"""
from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime
from statistics import median
from typing import Iterable

from lib.flow_summary import (
    _flow_ticker_rows,
    _fmt_money,
    _to_float,
    _to_int,
)

log = logging.getLogger(__name__)

BASELINE_TAB = "BaselineDaily"

# ETF tickers whose call/put premium is tracked individually per day.
KEY_TICKERS = ("SPY", "QQQ", "IWM", "HYG", "TLT", "GLD")
INDEX_TICKERS = ("SPY", "QQQ", "IWM")

# Window rules for percentile context.
WINDOW_ROWS = 60       # at most this many prior sessions
STALENESS_DAYS = 120   # ignore rows older than this many calendar days
MIN_WINDOW_ROWS = 10   # below this, show values but omit percentiles

# Top-N stock tickers (by total premium) over which put-dominance breadth is
# measured.
BREADTH_TOP_N = 50

# Sheet column order. append_rows writes dicts positionally from rows[0], so
# compute_daily_baseline must emit keys in exactly this order. Kept under 30
# columns — _ensure_tab creates new tabs with cols=30.
BASELINE_COLUMNS = [
    "date",
    "stocks_prem_total", "stocks_cp_prem", "stocks_cp_size", "stocks_cp_count",
    "stocks_pct_put_dom", "stocks_n_tickers", "stocks_dte_w",
    "etfs_prem_total", "etfs_cp_prem", "etfs_cp_size", "etfs_cp_count",
    "etfs_dte_w",
    "spy_call_prem", "spy_put_prem",
    "qqq_call_prem", "qqq_put_prem",
    "iwm_call_prem", "iwm_put_prem",
    "hyg_call_prem", "hyg_put_prem",
    "tlt_call_prem", "tlt_put_prem",
    "gld_call_prem", "gld_put_prem",
    "spy_iv_w",
    "index_cp_prem",
    "created_datetime",
]


# ---------------------------------------------------------------------------
# Daily row computation
# ---------------------------------------------------------------------------

# Flow CSV column names (same header constants as lib/flow_summary.py).
_COL_TYPE = "Type"
_COL_PREMIUM = "Premium"
_COL_SIZE = "Size"
_COL_DTE = "DTE"


def _section_agg(rows: Iterable[dict]) -> dict:
    """Section-wide call/put totals by premium, contracts, and trade count."""
    call_prem = put_prem = 0.0
    call_size = put_size = 0
    call_count = put_count = 0
    dte_prem_sum = 0.0
    for r in rows:
        t = (r.get(_COL_TYPE) or "").strip().lower()
        prem = _to_float(r.get(_COL_PREMIUM))
        size = _to_int(r.get(_COL_SIZE))
        dte_prem_sum += _to_float(r.get(_COL_DTE)) * prem
        if t == "call":
            call_prem += prem
            call_size += size
            call_count += 1
        elif t == "put":
            put_prem += prem
            put_size += size
            put_count += 1
    prem_total = call_prem + put_prem
    return {
        "prem_total": prem_total,
        "call_prem": call_prem,
        "put_prem": put_prem,
        "cp_prem": _ratio(call_prem, put_prem),
        "cp_size": _ratio(call_size, put_size),
        "cp_count": _ratio(call_count, put_count),
        "dte_w": round(dte_prem_sum / prem_total, 1) if prem_total > 0 else "",
    }


def _ratio(num: float, den: float):
    """Numeric call/put ratio; blank when the denominator is zero (a blank is
    excluded from percentile stats, where an ∞ sentinel would poison them)."""
    if den <= 0:
        return ""
    return round(num / den, 4)


def compute_daily_baseline(
    date_str: str,
    stocks_rows: list[dict],
    etfs_rows: list[dict],
) -> dict:
    """One BaselineDaily sheet row for a date, from parsed flow CSV rows.

    Only the two flow sections are needed (premium flow carries the baseline);
    the unusual-activity sections do not contribute.
    """
    stocks = _section_agg(stocks_rows)
    etfs = _section_agg(etfs_rows)

    stock_tickers = _flow_ticker_rows(stocks_rows)  # sorted by premium desc
    top = stock_tickers[:BREADTH_TOP_N]
    put_dom = sum(1 for t in top if t["premium_put"] > t["premium_call"])
    pct_put_dom = round(put_dom / len(top), 3) if top else ""

    etf_tickers = {t["symbol"]: t for t in _flow_ticker_rows(etfs_rows)}

    row: dict = {
        "date": date_str,
        "stocks_prem_total": round(stocks["prem_total"]),
        "stocks_cp_prem": stocks["cp_prem"],
        "stocks_cp_size": stocks["cp_size"],
        "stocks_cp_count": stocks["cp_count"],
        "stocks_pct_put_dom": pct_put_dom,
        "stocks_n_tickers": len(stock_tickers),
        "stocks_dte_w": stocks["dte_w"],
        "etfs_prem_total": round(etfs["prem_total"]),
        "etfs_cp_prem": etfs["cp_prem"],
        "etfs_cp_size": etfs["cp_size"],
        "etfs_cp_count": etfs["cp_count"],
        "etfs_dte_w": etfs["dte_w"],
    }

    for tkr in KEY_TICKERS:
        agg = etf_tickers.get(tkr)
        row[f"{tkr.lower()}_call_prem"] = round(agg["premium_call"]) if agg else ""
        row[f"{tkr.lower()}_put_prem"] = round(agg["premium_put"]) if agg else ""

    spy = etf_tickers.get("SPY")
    row["spy_iv_w"] = round(spy["iv_w"], 1) if spy else ""

    idx_call = sum(_to_float(row[f"{t.lower()}_call_prem"]) for t in INDEX_TICKERS)
    idx_put = sum(_to_float(row[f"{t.lower()}_put_prem"]) for t in INDEX_TICKERS)
    row["index_cp_prem"] = _ratio(idx_call, idx_put)

    row["created_datetime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    assert list(row.keys()) == BASELINE_COLUMNS, "baseline row drifted from BASELINE_COLUMNS"
    return row


# ---------------------------------------------------------------------------
# Window selection + percentiles
# ---------------------------------------------------------------------------

def normalize_sheet_date(value) -> str | None:
    """Normalize a sheet date cell to ISO YYYY-MM-DD.

    Handles ISO strings and the DD/MM/YYYY display format Sheets' USER_ENTERED
    parsing produced for older tabs (confirmed DD/MM: Jan 2 2025 reads back as
    '02/01/2025'). Returns None when unparseable.
    """
    s = str(value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def select_window(history_rows: list[dict], anchor_iso: str) -> list[dict]:
    """The trailing comparison window: rows strictly before the anchor date,
    within STALENESS_DAYS of it, most recent WINDOW_ROWS, oldest → newest.

    Deduplicates by date (last row wins) so a re-appended day cannot double-
    count in the distribution.
    """
    try:
        anchor = _date.fromisoformat(anchor_iso)
    except ValueError:
        log.warning("Bad anchor date %r — empty baseline window", anchor_iso)
        return []

    by_date: dict[str, dict] = {}
    for r in history_rows:
        iso = normalize_sheet_date(r.get("date"))
        if not iso:
            continue
        d = _date.fromisoformat(iso)
        if d >= anchor or (anchor - d).days > STALENESS_DAYS:
            continue
        by_date[iso] = r
    ordered = [by_date[k] for k in sorted(by_date)]
    return ordered[-WINDOW_ROWS:]


def percentile_of(values: list[float], x: float) -> int:
    """Share of window values at or below x, as a 0-100 integer."""
    if not values:
        return 0
    return round(100 * sum(1 for v in values if v <= x) / len(values))


# ---------------------------------------------------------------------------
# Markdown context section
# ---------------------------------------------------------------------------

def _metric_cp(call_key: str, put_key: str):
    """Derived call/put-premium ratio metric over two row columns."""
    def get(row: dict):
        call = _to_float(row.get(call_key))
        put = _to_float(row.get(put_key))
        if put <= 0:
            return None
        return call / put
    return get


def _metric_col(key: str):
    """Direct numeric column metric; blank/zero-denominator cells → None."""
    def get(row: dict):
        v = row.get(key)
        if v is None or str(v).strip() == "":
            return None
        return _to_float(v)
    return get


def _fmt_num(x: float) -> str:
    return f"{x:.2f}"


def _fmt_pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def _fmt_days(x: float) -> str:
    return f"{x:.0f}d"


def _fmt_prem(x: float) -> str:
    return _fmt_money(x)


# (label, value-getter, formatter). Order is display order.
_CONTEXT_METRICS = [
    ("Stocks C/P (premium)", _metric_col("stocks_cp_prem"), _fmt_num),
    ("Stocks C/P (contracts)", _metric_col("stocks_cp_size"), _fmt_num),
    ("Stocks C/P (trade count)", _metric_col("stocks_cp_count"), _fmt_num),
    (f"Stocks put-dominant share (top {BREADTH_TOP_N})", _metric_col("stocks_pct_put_dom"), _fmt_pct),
    ("Stocks total premium", _metric_col("stocks_prem_total"), _fmt_prem),
    ("Stocks prem-wtd DTE", _metric_col("stocks_dte_w"), _fmt_days),
    ("ETFs C/P (premium)", _metric_col("etfs_cp_prem"), _fmt_num),
    ("ETFs C/P (contracts)", _metric_col("etfs_cp_size"), _fmt_num),
    ("ETFs total premium", _metric_col("etfs_prem_total"), _fmt_prem),
    ("ETFs prem-wtd DTE", _metric_col("etfs_dte_w"), _fmt_days),
    ("Index complex C/P (SPY+QQQ+IWM)", _metric_col("index_cp_prem"), _fmt_num),
    ("SPY C/P", _metric_cp("spy_call_prem", "spy_put_prem"), _fmt_num),
    ("QQQ C/P", _metric_cp("qqq_call_prem", "qqq_put_prem"), _fmt_num),
    ("IWM C/P", _metric_cp("iwm_call_prem", "iwm_put_prem"), _fmt_num),
    ("HYG C/P", _metric_cp("hyg_call_prem", "hyg_put_prem"), _fmt_num),
    ("TLT C/P", _metric_cp("tlt_call_prem", "tlt_put_prem"), _fmt_num),
    ("GLD C/P", _metric_cp("gld_call_prem", "gld_put_prem"), _fmt_num),
    ("SPY prem-wtd IV", _metric_col("spy_iv_w"), _fmt_num),
]


def baseline_context_md(today_row: dict, history_rows: list[dict], anchor_iso: str) -> str:
    """The `## Baseline context` markdown section for the LLM rollup.

    today_row comes from compute_daily_baseline (in-process, never read back
    from the sheet); history_rows are raw BaselineDaily sheet rows.
    """
    window = select_window(history_rows, anchor_iso)
    n = len(window)

    lines = ["## Baseline context — today vs trailing window", ""]

    if n >= MIN_WINDOW_ROWS:
        first = normalize_sheet_date(window[0].get("date"))
        last = normalize_sheet_date(window[-1].get("date"))
        lines += [
            f"Window: {n} prior sessions, {first} → {last} "
            f"(up to {WINDOW_ROWS} sessions within {STALENESS_DAYS} days of {anchor_iso}).",
            "",
            "> Percentile = share of the window at or below today's value. On a C/P",
            "> metric, a LOW percentile means more put-dominant than usual, HIGH means",
            "> more call-dominant. Index put premium exceeding call premium is the",
            "> everyday norm — only the percentile says whether today is unusual.",
            "",
            "| metric | today | window median | percentile |",
            "|---|---|---|---|",
        ]
        for label, get, fmt in _CONTEXT_METRICS:
            today_v = get(today_row)
            if today_v is None:
                continue
            hist = [v for r in window if (v := get(r)) is not None]
            if hist:
                med, pct = fmt(median(hist)), f"{percentile_of(hist, today_v)}"
            else:
                med, pct = "—", "—"
            lines.append(f"| {label} | {fmt(today_v)} | {med} | {pct} |")
    else:
        lines += [
            f"_Insufficient history ({n} prior usable sessions, need {MIN_WINDOW_ROWS}) "
            "— today's values shown without percentiles; do not treat raw put/call",
            "dominance as a regime signal on its own._",
            "",
            "| metric | today |",
            "|---|---|",
        ]
        for label, get, fmt in _CONTEXT_METRICS:
            today_v = get(today_row)
            if today_v is None:
                continue
            lines.append(f"| {label} | {fmt(today_v)} |")

    return "\n".join(lines) + "\n"
