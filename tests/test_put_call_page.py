"""The ETF put/call page: ratio direction, gaps, the seal, and refusals."""
import csv
from datetime import date
from types import SimpleNamespace

from lib.baseline import BASELINE_COLUMNS
from scripts.put_call_page import build as b


def _export(path, rows, columns=BASELINE_COLUMNS):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def _row(d, **cells):
    return {"date": d, **cells}


def _bars(closes=None):
    closes = closes or {}
    return lambda sym: {date.fromisoformat(d): SimpleNamespace(c=c) for d, c in closes.get(sym, {}).items()}


def _spy(d):
    return next(e for e in d["etfs"] if e["sym"] == "SPY")


def test_ratio_is_put_over_call():
    assert b.ratio(300.0, 100.0) == 3.0


def test_ratio_is_blank_when_either_side_is_zero_or_missing():
    assert b.ratio(0.0, 100.0) is None
    assert b.ratio(100.0, 0.0) is None
    assert b.ratio(None, 100.0) is None


def test_gather_aligns_flow_and_price_on_sorted_dates(tmp_path):
    path = _export(tmp_path / "x.csv", [
        _row("2026-01-06", spy_call_prem="100", spy_put_prem="300"),
        _row("2026-01-05", spy_call_prem="200", spy_put_prem="100"),
    ])
    d = b.gather(path, _bars({"SPY": {"2026-01-05": 500.0, "2026-01-06": 505.0}}))
    spy = _spy(d)
    assert d["dates"] == ["2026-01-05", "2026-01-06"]
    assert spy["ratio"] == [0.5, 3.0]
    assert spy["close"] == [500.0, 505.0]
    assert spy["last_price"] == "2026-01-06"


def test_a_blank_row_is_a_gap_not_a_zero(tmp_path):
    path = _export(tmp_path / "x.csv", [
        _row("2026-01-05", spy_call_prem="", spy_put_prem=""),
        _row("2026-01-06", spy_call_prem="100", spy_put_prem="0"),
    ])
    spy = _spy(b.gather(path, _bars()))
    assert spy["call"][0] is None and spy["put"][0] is None and spy["ratio"][0] is None
    assert spy["put"][1] == 0.0 and spy["ratio"][1] is None
    assert spy["n_blank"] == 1 and spy["n_no_ratio"] == 1


def test_a_session_with_a_price_and_no_flow_row_stays_on_the_axis(tmp_path):
    path = _export(tmp_path / "x.csv", [
        _row("2026-01-05", spy_call_prem="1", spy_put_prem="1"),
        _row("2026-01-07", spy_call_prem="1", spy_put_prem="1"),
    ])
    d = b.gather(path, _bars({"SPY": {"2026-01-06": 500.0}}))
    assert d["dates"] == ["2026-01-05", "2026-01-06", "2026-01-07"]
    assert _spy(d)["call"][1] is None and _spy(d)["close"][1] == 500.0


def test_recent_dates_are_shown(tmp_path):
    path = _export(tmp_path / "x.csv", [
        _row("2026-09-22", spy_call_prem="1", spy_put_prem="1"),
        _row("2026-10-22", spy_call_prem="1", spy_put_prem="2"),
    ])
    d = b.gather(path, _bars({"SPY": {"2026-10-22": 501.0}}))
    assert d["last"] == "2026-10-22" and _spy(d)["ratio"][-1] == 2.0 and _spy(d)["close"][-1] == 501.0


def test_a_changed_header_is_refused(tmp_path):
    path = _export(tmp_path / "x.csv", [_row("2026-01-05")], columns=BASELINE_COLUMNS + ["extra"])
    d = b.gather(path, _bars())
    assert d["ok"] is False and "header" in d["why"]


def test_a_missing_export_gives_a_no_data_page(tmp_path):
    d = b.gather(tmp_path / "absent.csv", _bars())
    assert d["ok"] is False and "export_tabs" in d["why"]
    assert "No data" in b.fragment(d) and "__PUT_CALL__" not in b.fragment(d)


def test_the_payload_cannot_close_its_script_tag(tmp_path):
    path = _export(tmp_path / "x.csv", [_row("2026-01-05", spy_call_prem="1", spy_put_prem="1")])
    d = b.gather(path, _bars())
    d["etfs"][0]["name"] = "</script>"
    assert "</script>\"" not in b.fragment(d)


def test_write_page_uses_the_dashboard_wrapper(tmp_path):
    path = _export(tmp_path / "x.csv", [_row("2026-01-05", spy_call_prem="1", spy_put_prem="1")])
    seen = {}

    def document(frag, active, pages):
        seen.update(active=active, pages=pages)
        return frag

    dest = b.write_page(tmp_path, document, {"dashboard.html"}, path, _bars())
    assert dest.name == b.PAGE_NAME and "ETF put/call" in dest.read_text()
    assert seen == {"active": "putcall", "pages": {"dashboard.html"}}
