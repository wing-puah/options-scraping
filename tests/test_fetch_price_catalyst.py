"""Tests for scripts/fetch_price_catalyst.py's yfinance next-earnings fallback
gating (_is_near_live) and lookup (_fetch_next_earnings_yfinance). Pure/mocked,
no network."""
from datetime import date

from fetch_price_catalyst import _fetch_next_earnings_yfinance, _is_near_live


# ---------------------------------------------------------------------------
# _is_near_live
# ---------------------------------------------------------------------------

def test_is_near_live_today():
    assert _is_near_live(date(2026, 7, 8), today=date(2026, 7, 8))


def test_is_near_live_within_window():
    assert _is_near_live(date(2026, 7, 6), today=date(2026, 7, 8))


def test_is_near_live_exactly_at_edge_inclusive():
    assert _is_near_live(date(2026, 7, 5), today=date(2026, 7, 8))  # 3 days


def test_is_near_live_outside_window():
    assert not _is_near_live(date(2026, 6, 1), today=date(2026, 7, 8))


# ---------------------------------------------------------------------------
# _fetch_next_earnings_yfinance
# ---------------------------------------------------------------------------

def test_fetch_next_earnings_yfinance_picks_earliest(monkeypatch):
    import yfinance as yf

    class FakeTicker:
        def __init__(self, ticker):
            self.calendar = {"Earnings Date": [date(2026, 8, 4), date(2026, 8, 1)]}

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    assert _fetch_next_earnings_yfinance("AAPL") == date(2026, 8, 1)


def test_fetch_next_earnings_yfinance_no_earnings_date_key(monkeypatch):
    import yfinance as yf

    class FakeTicker:
        def __init__(self, ticker):
            self.calendar = {}

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    assert _fetch_next_earnings_yfinance("AAPL") is None


def test_fetch_next_earnings_yfinance_none_calendar(monkeypatch):
    import yfinance as yf

    class FakeTicker:
        def __init__(self, ticker):
            self.calendar = None

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    assert _fetch_next_earnings_yfinance("AAPL") is None


def test_fetch_next_earnings_yfinance_exception_returns_none(monkeypatch):
    import yfinance as yf

    class FakeTicker:
        def __init__(self, ticker):
            raise RuntimeError("boom")

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    assert _fetch_next_earnings_yfinance("AAPL") is None
