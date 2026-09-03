"""`load_analysis_csv` — the local analysis source for prompt-evaluation runs.

Both loaders must produce byte-identical candidates: the CSV path exists so a
candidate prompt's rows can be backtested without ever being appended to
AnalysisClaude, not to introduce a second, subtly different reading of a row.
"""
import csv
from datetime import date

import pytest

from analysis_pipeline import ROW_COLUMNS
from backtest.shared import analysis_io


def _row(**kw):
    row = {c: "" for c in ROW_COLUMNS}
    row.update(kw)
    return row


_ROWS = [
    _row(date="2026-06-01", ticker="MARKET", regime="BULL — short gamma", signal="[FLOW] x"),
    _row(date="2026-06-01", ticker="NVDA", regime="BULL", signal="[FLOW] sweeps",
         play="[DIRECTIONAL]\nbull call spread 120/130", horizon="2-4 weeks",
         invalidation="close < 112", oi_confirm_pct="0.62", cpir="1.4",
         iv_spread="2.1", iv_skew="-0.3", iv_pct="55",
         score_total="31", score_price="10", score_vol="9", score_catalyst="12"),
    _row(date="2026-06-02", ticker="AMD", regime="NEUTRAL", play="long call 160"),
    # No play text → dropped by both loaders.
    _row(date="2026-06-02", ticker="TSLA", regime="BEAR"),
]


@pytest.fixture
def rows_csv(tmp_path):
    path = tmp_path / "2026-06-01-rows.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ROW_COLUMNS))
        w.writeheader()
        w.writerows(_ROWS)
    return path


def test_csv_and_sheets_loaders_agree(monkeypatch, rows_csv):
    monkeypatch.setattr(analysis_io.sheets_client, "get_all_rows", lambda tab: _ROWS)
    from_tab = analysis_io.load_analysis("AnalysisClaude", None, None)
    from_csv = analysis_io.load_analysis_csv(rows_csv, None, None)
    assert from_csv == from_tab


def test_csv_loader_extracts_candidates_and_market_regime(rows_csv):
    candidates, market_regime = analysis_io.load_analysis_csv(rows_csv, None, None)

    assert market_regime == {"2026-06-01": "BULL — short gamma"}
    assert [c["ticker"] for c in candidates] == ["NVDA", "AMD"]
    nvda = candidates[0]
    assert nvda["signal_date"] == date(2026, 6, 1)
    assert nvda["horizon"] == "2-4 weeks"
    assert nvda["iv_spread"] == "2.1"
    assert nvda["score_total"] == "31"
    # v4 dropped these components; the columns survive as blanks.
    assert nvda["score_flow"] == ""


def test_csv_loader_honours_the_date_window(rows_csv):
    candidates, market_regime = analysis_io.load_analysis_csv(
        rows_csv, date(2026, 6, 2), None)
    assert [c["ticker"] for c in candidates] == ["AMD"]
    assert market_regime == {}


def test_csv_loader_makes_no_sheets_call(monkeypatch, rows_csv):
    def explode(*a, **kw):
        raise AssertionError("load_analysis_csv must not read Sheets")

    monkeypatch.setattr(analysis_io.sheets_client, "get_all_rows", explode)
    candidates, _ = analysis_io.load_analysis_csv(rows_csv, None, None)
    assert candidates
