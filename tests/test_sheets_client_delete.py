"""delete_rows_where issues ONE batchUpdate, never one write per row.

A per-row loop hit the Sheets 60-writes/min quota on 2026-09-23 after 66 rows of
a whole-tab --redo, leaving BacktestResults half-deleted.
"""
from __future__ import annotations

from lib import sheets_client


class _Ws:
    id = 7

    def __init__(self, rows):
        self._rows = rows

    def get_all_records(self):
        return self._rows

    def delete_rows(self, *a, **k):
        raise AssertionError("per-row delete: one API write per row")


class _Ss:
    def __init__(self):
        self.bodies = []

    def batch_update(self, body):
        self.bodies.append(body)


def _run(monkeypatch, rows, match):
    ss = _Ss()
    monkeypatch.setattr(sheets_client, "_get_spreadsheet", lambda: ss)
    monkeypatch.setattr(sheets_client, "_ensure_tab", lambda s, tab: _Ws(rows))
    n = sheets_client.delete_rows_where("T", match)
    return n, ss.bodies


def test_one_batch_with_contiguous_rows_merged_bottom_up(monkeypatch):
    rows = [{"k": k} for k in "xxyxxxyx"]  # data rows 0..7 → sheet rows 2..9
    n, bodies = _run(monkeypatch, rows, lambda r: r["k"] == "x")

    assert n == 6
    assert len(bodies) == 1
    ranges = [(q["deleteDimension"]["range"]["startIndex"],
               q["deleteDimension"]["range"]["endIndex"]) for q in bodies[0]["requests"]]
    # sheet rows 9 | 5-7 | 2-3, as 0-based half-open ranges, bottom-up
    assert ranges == [(8, 9), (4, 7), (1, 3)]
    assert all(q["deleteDimension"]["range"]["sheetId"] == 7 for q in bodies[0]["requests"])


def test_no_match_writes_nothing(monkeypatch):
    n, bodies = _run(monkeypatch, [{"k": "y"}], lambda r: r["k"] == "x")
    assert n == 0 and bodies == []
