from datetime import date

from scrape_flow import trading_days


def test_full_week_returns_five_days():
    # 2026-06-01 (Mon) to 2026-06-07 (Sun)
    days = trading_days(date(2026, 6, 1), date(2026, 6, 7))
    assert len(days) == 5
    assert days[0] == date(2026, 6, 1)
    assert days[-1] == date(2026, 6, 5)


def test_excludes_saturday_and_sunday():
    days = trading_days(date(2026, 5, 30), date(2026, 5, 31))  # Sat, Sun
    assert days == []


def test_single_weekday():
    days = trading_days(date(2026, 6, 2), date(2026, 6, 2))  # Tuesday
    assert days == [date(2026, 6, 2)]


def test_single_weekend_day():
    days = trading_days(date(2026, 6, 6), date(2026, 6, 6))  # Saturday
    assert days == []


def test_all_weekdays_in_result():
    days = trading_days(date(2026, 6, 1), date(2026, 6, 30))
    assert all(d.weekday() < 5 for d in days)


def test_start_equals_end_on_monday():
    days = trading_days(date(2026, 6, 1), date(2026, 6, 1))
    assert days == [date(2026, 6, 1)]


def test_multi_week_span():
    # Two full weeks: 10 trading days
    days = trading_days(date(2026, 6, 1), date(2026, 6, 14))
    assert len(days) == 10
