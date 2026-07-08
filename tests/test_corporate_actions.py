"""Tests for lib/barchart/corporate_actions.py (feed URL builder + row parser). Pure
functions, no network."""
from datetime import date

from lib.barchart.corporate_actions import corporate_actions_url, parse_corporate_actions


def test_corporate_actions_url():
    assert corporate_actions_url("mu") == (
        "https://www.barchart.com/stocks/quotes/MU/price-history/corporate-actions"
    )


def test_parse_corporate_actions_basic():
    rows = [
        {"date": "07/06/2026", "eventType": "Dividend", "value": "$0.1500"},
        {"date": "06/24/2026", "eventType": "Earnings", "value": "$25.11"},
        {"date": "03/18/2026", "eventType": "Earnings", "value": "$12.20"},
    ]
    out = parse_corporate_actions(rows)
    # sorted ascending by date
    assert [r["date"] for r in out] == [
        date(2026, 3, 18), date(2026, 6, 24), date(2026, 7, 6),
    ]
    assert out[0] == {"date": date(2026, 3, 18), "event_type": "Earnings", "value": 12.20}
    assert out[-1] == {"date": date(2026, 7, 6), "event_type": "Dividend", "value": 0.15}


def test_parse_corporate_actions_negative_eps_dollar_before_sign():
    rows = [{"date": "06/24/2026", "eventType": "Earnings", "value": "$-1.43"}]
    out = parse_corporate_actions(rows)
    assert out[0]["value"] == -1.43


def test_parse_corporate_actions_blank_value_is_none():
    rows = [{"date": "06/24/2026", "eventType": "Earnings", "value": ""}]
    out = parse_corporate_actions(rows)
    assert out[0]["value"] is None


def test_parse_corporate_actions_unparseable_date_skipped():
    rows = [
        {"date": "not-a-date", "eventType": "Earnings", "value": "$1.00"},
        {"date": "06/24/2026", "eventType": "Earnings", "value": "$1.00"},
    ]
    out = parse_corporate_actions(rows)
    assert len(out) == 1
    assert out[0]["date"] == date(2026, 6, 24)


def test_parse_corporate_actions_empty():
    assert parse_corporate_actions([]) == []
    assert parse_corporate_actions(None) == []
