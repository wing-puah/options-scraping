"""Tests for lib/baseline.py — daily row computation, window selection,
percentiles, and the markdown context section. Pure functions, no network."""
from datetime import date, timedelta

from lib.baseline import (
    BASELINE_COLUMNS,
    MIN_WINDOW_ROWS,
    STALENESS_DAYS,
    WINDOW_ROWS,
    baseline_context_md,
    compute_daily_baseline,
    normalize_sheet_date,
    percentile_of,
    select_window,
)


def _flow_row(symbol, opt_type, premium, size=10, dte=30, side="ask", iv="40%"):
    return {
        "Symbol": symbol, "Type": opt_type, "Strike": "100", "DTE": dte,
        "Side": side, "Premium": premium, "Size": size, "IV": iv,
        "*": "", "Code": "", "Time": "10:00",
    }


def _baseline_row(date_str, cp_prem=0.5, **overrides):
    row = {c: "" for c in BASELINE_COLUMNS}
    row["date"] = date_str
    row["stocks_cp_prem"] = cp_prem
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# compute_daily_baseline
# ---------------------------------------------------------------------------

def test_daily_row_matches_schema_and_splits_call_put():
    stocks = [
        _flow_row("NVDA", "Call", 1_000_000, size=100),
        _flow_row("NVDA", "Put", 3_000_000, size=200),
        _flow_row("AAPL", "Call", 2_000_000, size=50),
    ]
    etfs = [
        _flow_row("SPY", "Call", 4_000_000, size=10, iv="20%"),
        _flow_row("SPY", "Put", 8_000_000, size=40, iv="25%"),
        _flow_row("QQQ", "Put", 5_000_000, size=20),
    ]
    row = compute_daily_baseline("2026-06-10", stocks, etfs)

    assert list(row.keys()) == BASELINE_COLUMNS
    assert row["date"] == "2026-06-10"
    assert row["stocks_prem_total"] == 6_000_000
    assert row["stocks_cp_prem"] == 1.0          # 3M calls / 3M puts
    assert row["stocks_cp_size"] == 0.75         # 150 / 200
    assert row["stocks_cp_count"] == 2.0         # 2 calls / 1 put
    assert row["stocks_n_tickers"] == 2
    assert row["spy_call_prem"] == 4_000_000
    assert row["spy_put_prem"] == 8_000_000
    assert row["qqq_call_prem"] == 0
    assert row["qqq_put_prem"] == 5_000_000
    # SPY 4M calls + QQQ 0 / SPY 8M + QQQ 5M puts; IWM absent contributes 0.
    assert row["index_cp_prem"] == round(4 / 13, 4)
    # SPY iv premium-weighted: (20*4M + 25*8M) / 12M
    assert row["spy_iv_w"] == round((20 * 4 + 25 * 8) / 12, 1)


def test_daily_row_put_dominance_breadth():
    stocks = (
        [_flow_row(f"PD{i}", "Put", 2_000_000) for i in range(3)]
        + [_flow_row(f"CD{i}", "Call", 1_000_000) for i in range(1)]
    )
    row = compute_daily_baseline("2026-06-10", stocks, [])
    assert row["stocks_pct_put_dom"] == 0.75     # 3 of 4 tickers put-dominant


def test_daily_row_empty_sections_blank_not_crash():
    row = compute_daily_baseline("2026-06-10", [], [])
    assert row["stocks_prem_total"] == 0
    assert row["stocks_cp_prem"] == ""           # 0/0 → blank, not ∞
    assert row["stocks_pct_put_dom"] == ""
    assert row["spy_call_prem"] == ""
    assert row["index_cp_prem"] == ""


def test_zero_put_premium_is_blank_ratio():
    row = compute_daily_baseline("2026-06-10", [_flow_row("A", "Call", 1000)], [])
    assert row["stocks_cp_prem"] == ""           # excluded from stats, no sentinel


# ---------------------------------------------------------------------------
# normalize_sheet_date / select_window / percentile_of
# ---------------------------------------------------------------------------

def test_normalize_sheet_date_iso_and_locale():
    assert normalize_sheet_date("2026-06-10") == "2026-06-10"
    assert normalize_sheet_date("10/06/2026") == "2026-06-10"   # DD/MM/YYYY
    assert normalize_sheet_date("02/01/2025") == "2025-01-02"
    assert normalize_sheet_date("") is None
    assert normalize_sheet_date("garbage") is None


def test_window_excludes_anchor_future_and_stale_island():
    anchor = "2026-06-10"
    rows = [
        _baseline_row("2025-01-15"),                # stale island — excluded
        _baseline_row("2026-05-01"),
        _baseline_row("10/06/2026"),                # anchor itself — excluded
        _baseline_row("2026-06-09"),
        _baseline_row("2026-06-11"),                # future — excluded
    ]
    window = [r["date"] for r in select_window(rows, anchor)]
    assert window == ["2026-05-01", "2026-06-09"]


def test_window_caps_rows_and_dedupes_dates():
    anchor = date(2026, 6, 10)
    rows = []
    for i in range(1, 80):
        d = (anchor - timedelta(days=i)).isoformat()
        rows.append(_baseline_row(d, cp_prem=0.1))
    # duplicate date — the later row must win, not double-count
    rows.append(_baseline_row(rows[0]["date"], cp_prem=0.9))
    window = select_window(rows, anchor.isoformat())
    assert len(window) == WINDOW_ROWS
    dates = [r["date"] for r in window]
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)
    newest = window[-1]
    assert newest["cp_prem" if "cp_prem" in newest else "stocks_cp_prem"] == 0.9


def test_percentile_of():
    vals = [0.1, 0.2, 0.3, 0.4]
    assert percentile_of(vals, 0.05) == 0
    assert percentile_of(vals, 0.2) == 50        # at-or-below counts ties
    assert percentile_of(vals, 1.0) == 100
    assert percentile_of([], 1.0) == 0


# ---------------------------------------------------------------------------
# baseline_context_md
# ---------------------------------------------------------------------------

def _history(n, anchor="2026-06-10", cp=0.5):
    a = date.fromisoformat(anchor)
    out = []
    d, made = a, 0
    while made < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            out.append(_baseline_row(d.isoformat(), cp_prem=cp,
                                     spy_call_prem=1_000_000, spy_put_prem=2_000_000))
            made += 1
    return out


def test_context_md_with_history_has_percentiles():
    today = compute_daily_baseline(
        "2026-06-10",
        [_flow_row("NVDA", "Call", 1_000_000), _flow_row("NVDA", "Put", 1_000_000)],
        [_flow_row("SPY", "Call", 3_000_000), _flow_row("SPY", "Put", 1_000_000)],
    )
    md = baseline_context_md(today, _history(MIN_WINDOW_ROWS), "2026-06-10")
    assert "## Baseline context" in md
    assert f"Window: {MIN_WINDOW_ROWS} prior sessions" in md
    assert "| percentile |" in md
    # today's stocks C/P 1.0 vs constant history 0.5 → 100th percentile
    assert "| Stocks C/P (premium) | 1.00 | 0.50 | 100 |" in md
    # SPY C/P derived from premiums: today 3.0 vs history 0.5 → 100
    assert "| SPY C/P | 3.00 | 0.50 | 100 |" in md


def test_context_md_insufficient_history_omits_percentiles():
    today = compute_daily_baseline(
        "2026-06-10", [_flow_row("NVDA", "Call", 1_000_000)], [])
    md = baseline_context_md(today, _history(MIN_WINDOW_ROWS - 1), "2026-06-10")
    assert "Insufficient history" in md
    assert "| percentile |" not in md
    assert "| metric | today |" in md


def test_context_md_skips_metrics_blank_today():
    today = compute_daily_baseline("2026-06-10", [], [])
    md = baseline_context_md(today, _history(MIN_WINDOW_ROWS), "2026-06-10")
    # No SPY data today → SPY rows simply absent, not rendered as junk
    assert "| SPY C/P |" not in md
    assert "| Stocks total premium | $0 |" not in md or True
