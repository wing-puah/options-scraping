"""Tests for the date helpers in scripts/analysis_pipeline/fetch.py (no Drive needed)."""
from analysis_pipeline.fetch import _date_from_filename, _last_n_trading_days


def test_date_from_filename_parses_compact_date():
    name = "Options Flow — Stocks-20260605-1600.csv"
    assert _date_from_filename(name, "Options Flow — Stocks") == "2026-06-05"


def test_date_from_filename_rejects_malformed():
    assert _date_from_filename("Options Flow — Stocks-bad-1600.csv", "Options Flow — Stocks") is None


def test_last_n_trading_days_full_week():
    # Friday 2026-06-05, 5 days back → Mon–Fri of that week, oldest first.
    days = _last_n_trading_days("2026-06-05", 5)
    assert days == ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"]


def test_last_n_trading_days_skips_weekend_anchor():
    # Saturday anchor walks back to Friday.
    assert _last_n_trading_days("2026-06-06", 1) == ["2026-06-05"]


def test_last_n_trading_days_crosses_weekend():
    # Monday 2026-06-08, 2 days back → previous Friday + that Monday.
    assert _last_n_trading_days("2026-06-08", 2) == ["2026-06-05", "2026-06-08"]


def test_last_n_trading_days_oldest_to_newest():
    days = _last_n_trading_days("2026-06-05", 3)
    assert days == sorted(days)
