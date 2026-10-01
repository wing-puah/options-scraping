"""`scripts.backtest` and `scripts.backtest.proxy` map NetworkOutage to
EXIT_NETWORK_OUTAGE and write nothing (2026-09-29)."""
from datetime import date

import pytest
import yaml

import backtest.core as core
import backtest.proxy as proxy
from backtest.shared import history, identity


def test_exit_code_is_distinct_from_auth_crash_and_usage():
    from lib.barchart.session import BARCHART_AUTH_EXIT_CODE
    assert history.EXIT_NETWORK_OUTAGE not in (0, 1, 2, BARCHART_AUTH_EXIT_CODE)


def _boom(*a, **k):
    raise history.NetworkOutage(12, 30)


def test_core_maps_a_network_outage_to_its_exit_code_without_writing(
        tmp_path, monkeypatch, caplog):
    cfg_path = tmp_path / "backtest.yml"
    cfg_path.write_text(yaml.safe_dump({
        "analysis": {"tab": "AnalysisClaude"},
        "simulation": {"contracts": 1, "spread_width_pct": 0.02},
        "output": {"sheet_tab": "BacktestResults", "local_csv": str(tmp_path / "r.csv")},
    }))
    rows_csv = tmp_path / "rows.csv"
    rows_csv.write_text("date,ticker,regime,signal,play,horizon\n"
                        "2026-06-25,NVDA,BULL,sweep,Long call 250,swing\n")
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", lambda tab: [])
    monkeypatch.setattr(core, "_attach_rollup_metrics", lambda c: None)
    monkeypatch.setattr(core, "build_matched_plays", lambda *a, **k: (
        [], {"k": {"key": "k"}}, {}, {}))
    monkeypatch.setattr(core, "fetch_option_histories", _boom)
    wrote = []
    monkeypatch.setattr(core, "_run_simulations", lambda *a, **k: wrote.append("sim"))
    monkeypatch.setattr(core, "_write_results", lambda *a, **k: wrote.append("write"))
    monkeypatch.setattr(core.sheets_client, "delete_rows_where",
                        lambda *a, **k: wrote.append("delete"))
    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv)])
    with pytest.raises(SystemExit) as e:
        core.main()
    assert e.value.code == history.EXIT_NETWORK_OUTAGE
    assert wrote == []
    assert "network outage: 12 of 30 fetches failed" in caplog.text
    assert "nothing was written" in caplog.text


def test_proxy_maps_a_network_outage_to_its_exit_code_without_writing(
        monkeypatch, caplog):
    cand = {"ticker": "NVDA", "play": "long call 250 Jun 20",
            "signal_date": date(2026, 6, 1), "date": "2026-06-01", "regime": "BULL"}
    monkeypatch.setattr(proxy, "load_analysis", lambda tab, s, e: ([cand], {}))
    monkeypatch.setattr(proxy, "_load_tested_keys", lambda tab: set())
    monkeypatch.setattr(proxy, "_load_proxy_keys", lambda tab: set())
    monkeypatch.setattr(proxy, "_evaluate", _boom)
    wrote = []
    monkeypatch.setattr(proxy, "write_results", lambda *a, **k: wrote.append(1))
    monkeypatch.setattr(proxy.sheets_client, "delete_rows_where",
                        lambda *a, **k: wrote.append(1))
    monkeypatch.setattr("sys.argv", ["proxy", "--date", "2026-06-01"])
    with pytest.raises(SystemExit) as e:
        proxy.main()
    assert e.value.code == history.EXIT_NETWORK_OUTAGE
    assert wrote == []
    assert "nothing was written" in caplog.text


def test_the_proxy_probe_lets_a_network_outage_through(monkeypatch, tmp_path):
    """`_probe_pool` swallows every other fetch failure; this one must escape."""
    import backtest as bt
    monkeypatch.setattr(proxy, "HISTORY_CACHE", tmp_path)
    monkeypatch.setenv("SCRAPE_HEADLESS", "true")

    async def _aboom(*a, **k):
        raise history.NetworkOutage(12, 30)
    monkeypatch.setattr(proxy, "fetch_option_histories", _aboom)
    leg = bt.Leg(1, "NVDA", date(2026, 6, 20), 250.0, "Call")
    with pytest.raises(history.NetworkOutage):
        proxy._probe_pool(leg, date(2026, 6, 1),
                          {"max_strike_steps": 2, "max_expiry_deviation_days": 14}, {}, 5.0)
