"""Tests for scripts/collector/fetch_price_catalyst.py's yfinance next-earnings fallback
gating (_is_near_live) and lookup (_fetch_next_earnings_yfinance), and the
etfs-flow corporate-actions skip in _scrape_and_fill. Pure/mocked, no network."""
import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from fetch_price_catalyst import (
    _ensure_columns,
    _fetch_next_earnings_yfinance,
    _is_near_live,
    _scrape_and_fill,
)


@pytest.fixture(autouse=True)
def _restore_event_loop():
    """asyncio.run (via _scrape_and_fill) closes the loop and clears the global
    current loop on 3.11. Restore one after each test so later async-using
    modules (test_scraper, test_gc_flow) still find a current event loop."""
    yield
    asyncio.set_event_loop(asyncio.new_event_loop())


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


# ---------------------------------------------------------------------------
# _scrape_and_fill — etfs-flow skips the corporate-actions scrape
# ---------------------------------------------------------------------------

class _FakeSession:
    """Stands in for an entered BarchartSession; no price/earnings data, just
    records which feeds were hit per symbol."""

    def __init__(self):
        self.price_calls: list[str] = []
        self.corporate_actions_calls: list[str] = []

    async def fetch_history_fast(self, url, timeout_ms=15000):
        self.price_calls.append(url)
        return None

    async def fetch_corporate_actions(self, symbol, timeout_ms=15000):
        self.corporate_actions_calls.append(symbol)
        return None


def _catalyst_row(symbol: str) -> dict:
    return {"Symbol": symbol}


def test_scrape_and_fill_skips_corporate_actions_for_etfs_flow(monkeypatch):
    monkeypatch.setattr("fetch_price_catalyst._is_near_live", lambda *a, **k: False)
    client = MagicMock()
    rows = [_catalyst_row("SPY")]
    _ensure_columns(rows)
    session = _FakeSession()

    asyncio.run(_scrape_and_fill(
        client, "etfs-flow", "2026-06-09", rows, ["SPY"], "2026-06-17",
        headless=True, file_name="etfs-flow-20260609-compiled.csv",
        checkpoint_every=99, sleep_s=0, session=session))

    assert session.price_calls  # underlying price history is still fetched
    assert session.corporate_actions_calls == []  # earnings feed never hit
    assert rows[0]["next_earnings"] == "" and rows[0]["last_earnings"] == ""
    assert rows[0]["price_catalyst_enriched_on"] == "2026-06-17"


def test_scrape_and_fill_fetches_corporate_actions_for_stocks_flow():
    client = MagicMock()
    rows = [_catalyst_row("AAPL")]
    _ensure_columns(rows)
    session = _FakeSession()

    asyncio.run(_scrape_and_fill(
        client, "stocks-flow", "2026-06-09", rows, ["AAPL"], "2026-06-17",
        headless=True, file_name="stocks-flow-20260609-compiled.csv",
        checkpoint_every=99, sleep_s=0, session=session))

    assert session.corporate_actions_calls == ["AAPL"]
