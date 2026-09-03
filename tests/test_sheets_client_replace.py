"""
Tests for lib/sheets_client.replace_rows — the MIRROR write.

`append_rows` accumulates; this one makes a tab hold exactly what it is given.
The range arithmetic is what decides whether a stale row survives, so it is
tested here rather than only through its caller (whose tests fake the whole
sheets_client module).
"""
from __future__ import annotations

import pytest

from lib import sheets_client

COLUMNS = ["a", "b", "c"]


class _FakeWorksheet:
    def __init__(self, rows=100, cols=10):
        self.row_count = rows
        self.col_count = cols
        self.updates: list[tuple[str, list]] = []
        self.cleared: list[list[str]] = []
        self.added_rows = 0

    def resize(self, rows=None, cols=None):
        if rows is not None:
            self.row_count = rows
        if cols is not None:
            self.col_count = cols

    def add_rows(self, n):
        self.added_rows += n
        self.row_count += n

    def update(self, rng, data, value_input_option=None):
        self.updates.append((rng, data, value_input_option))

    def batch_clear(self, ranges):
        self.cleared.append(list(ranges))


class _FakeSpreadsheet:
    def __init__(self, ws):
        self.ws = ws

    def worksheet(self, name):
        return self.ws


@pytest.fixture
def ws(monkeypatch):
    sheet = _FakeWorksheet()
    monkeypatch.setattr(sheets_client, "_get_spreadsheet",
                        lambda spreadsheet_id=None: _FakeSpreadsheet(sheet))
    return sheet


def _rows(n):
    return [{"a": i, "b": "x", "c": ""} for i in range(n)]


def test_the_header_is_written_with_the_rows_it_labels(ws):
    sheets_client.replace_rows("T", _rows(2), COLUMNS)
    rng, data, _ = ws.updates[0]
    assert rng == "A1"
    assert data[0] == COLUMNS
    assert len(data) == 3


def test_rows_below_the_new_block_are_cleared_so_nothing_stale_survives(ws):
    sheets_client.replace_rows("T", _rows(2), COLUMNS)
    # header + 2 rows occupy 1..3; everything from row 4 down goes.
    assert "A4:J100" in ws.cleared[0]


def test_the_new_block_is_written_before_anything_is_cleared(ws):
    """A clear-then-write leaves the tab empty in between, and an empty open
    book is a statement rather than a placeholder."""
    order = []
    ws.update = lambda *a, **kw: order.append("update")
    ws.batch_clear = lambda ranges: order.append("clear")
    sheets_client.replace_rows("T", _rows(2), COLUMNS)
    assert order == ["update", "clear"]


def test_columns_right_of_the_schema_are_cleared_too(ws):
    """What a tab written under a WIDER earlier layout leaves behind: a header
    with no data under it, which reads as a column the writer forgot to fill."""
    sheets_client.replace_rows("T", _rows(1), COLUMNS)
    assert "D1:J100" in ws.cleared[0]


def test_a_tab_already_exactly_the_schema_width_clears_no_extra_columns(monkeypatch):
    sheet = _FakeWorksheet(cols=len(COLUMNS))
    monkeypatch.setattr(sheets_client, "_get_spreadsheet",
                        lambda spreadsheet_id=None: _FakeSpreadsheet(sheet))
    sheets_client.replace_rows("T", _rows(1), COLUMNS)
    assert sheet.cleared[0] == ["A3:C100"]


def test_an_empty_row_list_clears_the_tab_to_its_header_alone(ws):
    assert sheets_client.replace_rows("T", [], COLUMNS) == 0
    rng, data, _ = ws.updates[0]
    assert data == [COLUMNS]
    assert "A2:J100" in ws.cleared[0]


def test_a_narrow_tab_is_widened_to_the_schema_before_the_write(monkeypatch):
    sheet = _FakeWorksheet(cols=2)
    monkeypatch.setattr(sheets_client, "_get_spreadsheet",
                        lambda spreadsheet_id=None: _FakeSpreadsheet(sheet))
    sheets_client.replace_rows("T", _rows(1), COLUMNS)
    assert sheet.col_count == len(COLUMNS)


def test_a_short_tab_gains_the_rows_it_needs_rather_than_truncating(monkeypatch):
    sheet = _FakeWorksheet(rows=3)
    monkeypatch.setattr(sheets_client, "_get_spreadsheet",
                        lambda spreadsheet_id=None: _FakeSpreadsheet(sheet))
    sheets_client.replace_rows("T", _rows(10), COLUMNS)
    assert sheet.row_count == 11          # header + 10
    assert sheet.added_rows == 8
    assert sheet.cleared == [["D1:J11"]]  # nothing below; only the stale columns


def test_raw_keeps_a_string_date_out_of_the_locale_parser(ws):
    sheets_client.replace_rows("T", _rows(1), COLUMNS, raw=True)
    assert ws.updates[0][2] == "RAW"
    ws.updates.clear()
    sheets_client.replace_rows("T", _rows(1), COLUMNS)
    assert ws.updates[0][2] == "USER_ENTERED"


def test_a_nan_is_written_blank_not_as_an_invalid_json_float(ws):
    sheets_client.replace_rows("T", [{"a": float("nan"), "b": 1, "c": 2}], COLUMNS)
    assert ws.updates[0][1][1] == ["", 1, 2]
