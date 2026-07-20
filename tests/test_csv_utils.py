from lib.csv_utils import parse_csv


def test_basic_rows():
    raw = "Symbol,Volume\nAAPL,1000\nGOOGL,500\n"
    rows = parse_csv(raw)
    assert len(rows) == 2
    assert rows[0] == {"Symbol": "AAPL", "Volume": "1000"}
    assert rows[1] == {"Symbol": "GOOGL", "Volume": "500"}


def test_stops_at_footer():
    raw = "Symbol,Volume\nAAPL,1000\nDownloaded from barchart.com,\nGOOGL,500\n"
    rows = parse_csv(raw)
    assert len(rows) == 1
    assert rows[0]["Symbol"] == "AAPL"


def test_footer_as_first_row_returns_empty():
    raw = "Symbol,Volume\nDownloaded from barchart.com,\n"
    assert parse_csv(raw) == []


def test_empty_string_returns_empty():
    assert parse_csv("") == []


def test_header_only_returns_empty():
    assert parse_csv("Symbol,Volume\n") == []


def test_preserves_all_columns():
    raw = "Symbol,Type,Strike,DTE,IV\nAAPL,Call,200,30,0.35\n"
    rows = parse_csv(raw)
    assert rows[0] == {"Symbol": "AAPL", "Type": "Call", "Strike": "200", "DTE": "30", "IV": "0.35"}


def test_multiple_rows_before_footer():
    raw = "Symbol,Volume\nAAPL,100\nMSFT,200\nNVDA,300\nDownloaded from barchart.com,\n"
    rows = parse_csv(raw)
    assert len(rows) == 3
    assert rows[2]["Symbol"] == "NVDA"


def test_blank_line_is_skipped_not_crashed_on():
    raw = "Symbol,Volume\nAAPL,100\n\nMSFT,200\n"
    rows = parse_csv(raw)
    assert len(rows) == 2
    assert rows[0]["Symbol"] == "AAPL"
    assert rows[1]["Symbol"] == "MSFT"
