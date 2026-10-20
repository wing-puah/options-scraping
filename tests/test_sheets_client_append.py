"""
Tests for lib/sheets_client.append_rows — the header guard (robustness A2).

`append_rows` writes positionally, so a live header that has drifted from the
rows' keys mislabels every appended row and nothing says so. Since 2026-10-20
the live header is compared to `list(rows[0].keys())` and a mismatch is
refused BEFORE anything is appended. The fake worksheet below records what was
written so the test can assert "nothing".
"""
from __future__ import annotations

import pytest

from lib import sheets_client


class _FakeWorksheet:
    def __init__(self, header):
        self.header = list(header)
        self.appended: list[list] = []

    def row_values(self, n):
        assert n == 1
        return list(self.header)

    def append_row(self, values):
        self.header = list(values)

    def append_rows(self, values, value_input_option=None):
        self.appended.extend(values)


@pytest.fixture
def make_ws(monkeypatch):
    def _make(header):
        ws = _FakeWorksheet(header)
        monkeypatch.setattr(sheets_client, "_get_spreadsheet",
                            lambda spreadsheet_id=None: object())
        monkeypatch.setattr(sheets_client, "_ensure_tab",
                            lambda ss, tab, min_cols=None: ws)
        return ws
    return _make


ROWS = [{"date": "2026-10-20", "ticker": "SPY", "play": "x"}]


def test_matching_header_appends(make_ws):
    ws = make_ws(["date", "ticker", "play"])
    sheets_client.append_rows("T", ROWS)
    assert ws.appended == [["2026-10-20", "SPY", "x"]]


def test_empty_tab_gets_the_header_then_the_rows(make_ws):
    ws = make_ws([])
    sheets_client.append_rows("T", ROWS)
    assert ws.header == ["date", "ticker", "play"]
    assert ws.appended == [["2026-10-20", "SPY", "x"]]


@pytest.mark.parametrize("header,col,h,k", [
    (["date", "ticker"], 3, "<missing>", "play"),            # tab lags the schema
    (["date", "ticker", "play", "extra"], 4, "extra", "<no such key>"),
    (["date", "play", "ticker"], 2, "play", "ticker"),        # reordered
    (["date", "symbol", "play"], 2, "symbol", "ticker"),      # renamed
])
def test_drifted_header_is_refused_and_nothing_is_written(make_ws, header, col, h, k):
    ws = make_ws(header)
    with pytest.raises(sheets_client.HeaderMismatch) as e:
        sheets_client.append_rows("T", ROWS)
    msg = str(e.value)
    assert f"column {col}" in msg and repr(h) in msg and repr(k) in msg
    assert "align_tab_headers" in msg
    assert ws.appended == []
    assert ws.header == header  # the guard never rewrites a header either


def test_header_mismatch_is_a_value_error():
    assert issubclass(sheets_client.HeaderMismatch, ValueError)
