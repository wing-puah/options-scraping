"""Local-only backtest + proxy runs — the second half of the prompt-evaluation path.

A derived config that names ``analysis.csv`` and sets ``sheet_tab: null`` must
complete WITHOUT a single Sheets call, in either direction: the candidate
analysis is read off disk and the results stay on disk. Both tests wire every
public ``sheets_client`` function to raise, so any surviving call is a failure
rather than a silent write to BacktestResults / BacktestProxy.
"""
import csv
from datetime import date
from pathlib import Path

import pytest
import yaml

import backtest.core as bt
import backtest.proxy as proxy
from analysis_pipeline import ROW_COLUMNS
from lib import sheets_client


_SHEETS_FNS = ("get_all_rows", "get_all_rows_preserving_formulas", "get_all_values",
               "append_rows", "delete_rows_where", "write_analysis",
               "add_or_update_column", "ensure_tab", "ensure_header", "set_meta")


@pytest.fixture
def no_sheets(monkeypatch):
    """Every public sheets_client entry point becomes a landmine."""
    for name in _SHEETS_FNS:
        def explode(*a, _n=name, **kw):
            raise AssertionError(f"sheets_client.{_n} must not be called on a local-only run")
        monkeypatch.setattr(sheets_client, name, explode)


@pytest.fixture
def analysis_csv(tmp_path):
    path = tmp_path / "rows.csv"
    rows = [
        {c: "" for c in ROW_COLUMNS} | {"date": "2026-06-01", "ticker": "MARKET",
                                        "regime": "BULL — short gamma"},
        {c: "" for c in ROW_COLUMNS} | {"date": "2026-06-01", "ticker": "NVDA",
                                        "regime": "BULL",
                                        "play": "[DIRECTIONAL]\nlong call 250 Jun 20"},
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ROW_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    return path


_ROOT = Path(__file__).resolve().parent.parent


def _base_cfg():
    with (_ROOT / "config" / "backtest.yml").open() as f:
        return yaml.safe_load(f)


def _write_cfg(tmp_path, cfg):
    path = tmp_path / "local.yml"
    path.write_text(yaml.safe_dump(cfg))
    return path


# ── 1. backtest core ────────────────────────────────────────────────────────────

def test_backtest_local_only_reads_csv_and_writes_no_sheets(
        monkeypatch, tmp_path, no_sheets, analysis_csv):
    cfg = _base_cfg()
    cfg["analysis"]["csv"] = str(analysis_csv)
    cfg["output"]["sheet_tab"] = None
    cfg["output"]["local_csv"] = str(tmp_path / "run" / "results.csv")
    cfg_path = _write_cfg(tmp_path, cfg)

    monkeypatch.setattr(bt, "_attach_rollup_metrics", lambda c: None)
    monkeypatch.setattr(bt, "build_matched_plays",
                        lambda *a, **kw: ([], {}, set(),
                                          {"unsupported": 0, "no_strike": 0, "no_expiry": 0,
                                           "unpriced": 0, "vetoed": 0}))
    monkeypatch.setattr(bt, "_run_simulations",
                        lambda *a, **kw: [{"signal_date": "2026-06-01", "ticker": "NVDA",
                                           "structure": "long call", "legs": "C250",
                                           "realized_pnl_pct": 0.2, "realized_pnl_abs": 200.0}])
    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path)])

    bt.main()

    out = tmp_path / "run" / "results.csv"
    assert out.exists()
    with out.open(newline="", encoding="utf-8") as f:
        written = list(csv.DictReader(f))
    assert [r["ticker"] for r in written] == ["NVDA"]


def test_backtest_analysis_csv_flag_overrides_the_tab(
        monkeypatch, tmp_path, no_sheets, analysis_csv):
    """--analysis-csv wins even when the config still names a tab."""
    cfg = _base_cfg()
    cfg["output"]["sheet_tab"] = None
    cfg["output"]["local_csv"] = str(tmp_path / "run" / "results.csv")
    cfg_path = _write_cfg(tmp_path, cfg)

    seen = {}
    monkeypatch.setattr(bt, "_attach_rollup_metrics", lambda c: seen.setdefault("candidates", c))
    monkeypatch.setattr(bt, "build_matched_plays",
                        lambda *a, **kw: ([], {}, set(),
                                          {"unsupported": 0, "no_strike": 0, "no_expiry": 0,
                                           "unpriced": 0, "vetoed": 0}))
    monkeypatch.setattr(bt, "_run_simulations", lambda *a, **kw: [])
    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(analysis_csv)])

    bt.main()
    assert [c["ticker"] for c in seen["candidates"]] == ["NVDA"]
    assert seen["candidates"][0]["signal_date"] == date(2026, 6, 1)


# ── 2. proxy ────────────────────────────────────────────────────────────────────

def test_proxy_local_only_reads_csv_sources_and_writes_no_sheets(
        monkeypatch, tmp_path, no_sheets, analysis_csv):
    results_csv = tmp_path / "run" / "results.csv"
    results_csv.parent.mkdir(parents=True, exist_ok=True)
    with results_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["signal_date", "ticker", "play"])
        w.writeheader()
        w.writerow({"signal_date": "2026-06-01", "ticker": "AMD", "play": "long put 100"})

    cfg = _base_cfg()
    cfg["analysis"]["csv"] = str(analysis_csv)
    cfg["proxy"]["sheet_tab"] = None
    cfg["proxy"]["results_source_csv"] = str(results_csv)
    cfg["proxy"]["local_csv"] = str(tmp_path / "run" / "proxy_results.csv")
    cfg_path = _write_cfg(tmp_path, cfg)

    monkeypatch.setattr(proxy, "_evaluate",
                        lambda *a, **kw: {"signal_date": "2026-06-01", "ticker": "NVDA",
                                          "play": "long call 250 Jun 20",
                                          "proxy_method": "strike_expiry_tweak",
                                          "proxy_detail": "stub"})
    monkeypatch.setattr("sys.argv", ["proxy", "--config", str(cfg_path)])

    proxy.main()

    out = tmp_path / "run" / "proxy_results.csv"
    assert out.exists()
    with out.open(newline="", encoding="utf-8") as f:
        written = list(csv.DictReader(f))
    assert [r["ticker"] for r in written] == ["NVDA"]


def test_proxy_local_only_second_run_is_idempotent_off_the_local_csv(
        monkeypatch, tmp_path, no_sheets, analysis_csv):
    """With sheet_tab null the "already evaluated" set comes from the local CSV,
    so a re-run finds nothing left to do (the Sheets-tab guard's local twin)."""
    proxy_csv = tmp_path / "run" / "proxy_results.csv"
    proxy_csv.parent.mkdir(parents=True, exist_ok=True)
    with proxy_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["signal_date", "ticker", "play"])
        w.writeheader()
        w.writerow({"signal_date": "2026-06-01", "ticker": "NVDA",
                    "play": "[DIRECTIONAL]\nlong call 250 Jun 20"})

    cfg = _base_cfg()
    cfg["analysis"]["csv"] = str(analysis_csv)
    cfg["proxy"]["sheet_tab"] = None
    cfg["proxy"]["results_source_csv"] = str(tmp_path / "missing.csv")  # absent = empty set
    cfg["proxy"]["local_csv"] = str(proxy_csv)
    cfg_path = _write_cfg(tmp_path, cfg)

    def explode(*a, **kw):
        raise AssertionError("nothing left to evaluate — _evaluate must not run")

    monkeypatch.setattr(proxy, "_evaluate", explode)
    monkeypatch.setattr("sys.argv", ["proxy", "--config", str(cfg_path)])

    proxy.main()
