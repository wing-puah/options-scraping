"""The already-backtested guard on `python3 -m scripts.backtest`.

`append_rows` appends. Re-running a date the results tab already holds used to
leave both runs' rows on it — and they are not copies: a re-run reprices the
same play on today's exit config and today's cache, so the two rows can disagree
about the exit, the basis and the P&L. That is how the 2025-12-22 SPY duplicate
and 15 older ones came to exist.

These pin the guard's contract, and pin that the real backtest and the proxy
share ONE encoding of row identity — two copies would let them disagree about
what a duplicate is.
"""
from datetime import date
from types import SimpleNamespace

import pytest
import yaml

import backtest as bt
import backtest.core as core
import backtest.proxy as proxy
from backtest.shared import identity


def _args(redo=False, dry_run=False):
    return SimpleNamespace(redo=redo, dry_run=dry_run)


def _cand(ticker="NVDA", play="Long call 250", signal=date(2026, 6, 25)):
    return {"signal_date": signal, "date": signal.isoformat(), "ticker": ticker, "play": play}


def _cfg(sheet_tab="BacktestResults"):
    return {"output": {"sheet_tab": sheet_tab, "local_csv": "backtests/results.csv"}}


# ── One identity encoding, shared by both writers ──────────────────────────────

def test_core_and_proxy_key_on_the_same_identity():
    """Not a tautology worth deleting: it is the whole point of shared/identity.py.
    If either module ever grows its own key again, one writer's 'duplicate' stops
    being the other's and the two tabs drift apart silently."""
    args = (date(2026, 6, 25), "NVDA", "Long call 250")
    assert proxy._identity_key(*args) == identity.identity_key(*args)
    assert bt._identity_key(*args) == identity.identity_key(*args)


def test_identity_key_survives_the_sheets_locale_reparse():
    # The tab hands back "6/25/2026" where the candidate carries a date object.
    assert (identity.identity_key("6/25/2026", "nvda", "  Long   call 250  ")
            == identity.identity_key(date(2026, 6, 25), "NVDA", "Long call 250"))


def test_identity_key_separates_two_plays_on_one_ticker_and_date():
    assert (identity.identity_key(date(2026, 6, 25), "NVDA", "Long call 250")
            != identity.identity_key(date(2026, 6, 25), "NVDA", "Bull call spread 250/260"))


# ── The guard itself ───────────────────────────────────────────────────────────

def test_drops_candidates_already_on_the_results_tab(monkeypatch):
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", lambda tab: [
        {"signal_date": "6/25/2026", "ticker": "NVDA", "play": "Long call 250"},
    ])
    candidates = [_cand(), _cand(play="Bull call spread 250/260"),
                  _cand(signal=date(2026, 6, 26))]

    remaining, redo_keys = core._drop_already_backtested(candidates, _cfg(), _args())

    assert [c["play"] for c in remaining] == ["Bull call spread 250/260", "Long call 250"]
    assert remaining[1]["signal_date"] == date(2026, 6, 26)
    assert redo_keys == set()


def test_keeps_everything_when_the_tab_is_empty(monkeypatch):
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", lambda tab: [])
    candidates = [_cand(), _cand(ticker="AMD")]

    remaining, redo_keys = core._drop_already_backtested(candidates, _cfg(), _args())

    assert remaining == candidates
    assert redo_keys == set()


def test_redo_keeps_the_duplicates_and_marks_them_for_deletion(monkeypatch):
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", lambda tab: [
        {"signal_date": "6/25/2026", "ticker": "NVDA", "play": "Long call 250"},
    ])
    candidates = [_cand(), _cand(ticker="AMD")]

    remaining, redo_keys = core._drop_already_backtested(candidates, _cfg(), _args(redo=True))

    # --redo re-simulates everything; only the rows that ALREADY exist are deleted.
    assert remaining == candidates
    assert redo_keys == {identity.identity_key(date(2026, 6, 25), "NVDA", "Long call 250")}


def test_local_only_run_never_reads_sheets(monkeypatch):
    """`output.sheet_tab: null` is a local-only run. Its only destination is the
    local CSV, which this CLI REWRITES rather than appends, so it cannot
    accumulate a duplicate — and must not demand Sheets credentials to be told so."""
    def _boom(tab):
        raise AssertionError(f"read tab {tab!r} on a local-only run")
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", _boom)
    candidates = [_cand()]

    remaining, redo_keys = core._drop_already_backtested(candidates, _cfg(sheet_tab=None), _args())

    assert remaining == candidates
    assert redo_keys == set()


# ── CLI contract ───────────────────────────────────────────────────────────────

def test_redo_refuses_to_run_unbounded(monkeypatch, capsys):
    """An unbounded --redo would delete and rewrite the whole tab. That is a
    re-backtest of the book, not a repair, so it must be asked for by date —
    the same bound proxy.py's --redo carries."""
    monkeypatch.setattr("sys.argv", ["backtest", "--redo"])
    with pytest.raises(SystemExit) as e:
        core.main()
    assert e.value.code == 2
    assert "date bound" in capsys.readouterr().err


def _write_cfg(tmp_path, monkeypatch, sheet_tab="BacktestResults"):
    """A minimal backtest.yml, addressed the way core.main() addresses it: the
    --config path is resolved against the REPO ROOT, so hand it an absolute one."""
    cfg_path = tmp_path / "backtest.yml"
    cfg_path.write_text(yaml.safe_dump({
        "analysis": {"tab": "AnalysisClaude"},
        "simulation": {"contracts": 1, "spread_width_pct": 0.02},
        "output": {"sheet_tab": sheet_tab, "local_csv": str(tmp_path / "results.csv")},
    }))
    return cfg_path


def test_main_exits_before_the_barchart_fetch_when_every_play_is_a_duplicate(
        tmp_path, monkeypatch):
    """The guard has to be reached BEFORE the expensive step. A guard that costs
    a full Barchart fetch to reach is not a guard."""
    cfg_path = _write_cfg(tmp_path, monkeypatch)
    rows_csv = tmp_path / "rows.csv"
    rows_csv.write_text(
        "date,ticker,regime,signal,play,horizon\n"
        "2026-06-25,NVDA,BULL,sweep,Long call 250,swing\n")

    monkeypatch.setattr(identity.sheets_client, "get_all_rows", lambda tab: [
        {"signal_date": "2026-06-25", "ticker": "NVDA", "play": "Long call 250"},
    ])

    def _no_fetch(*a, **k):
        raise AssertionError("fetched Barchart history for an already-backtested play")
    monkeypatch.setattr(core, "fetch_option_histories", _no_fetch)
    monkeypatch.setattr(core, "build_matched_plays", _no_fetch)

    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv)])
    with pytest.raises(SystemExit) as e:
        core.main()
    assert e.value.code == 0


def test_redo_deletes_the_old_rows_before_appending_the_new_ones(tmp_path, monkeypatch):
    """Order is the whole contract: if the append landed first, --redo would
    produce exactly the duplicate it exists to prevent."""
    cfg_path = _write_cfg(tmp_path, monkeypatch)
    rows_csv = tmp_path / "rows.csv"
    rows_csv.write_text(
        "date,ticker,regime,signal,play,horizon\n"
        "2026-06-25,NVDA,BULL,sweep,Long call 250,swing\n")

    existing = {"signal_date": "2026-06-25", "ticker": "NVDA", "play": "Long call 250"}
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", lambda tab: [existing])

    calls = []
    monkeypatch.setattr(core.sheets_client, "delete_rows_where",
                        lambda tab, fn: calls.append(("delete", tab, fn(existing))))
    monkeypatch.setattr(core, "_write_results",
                        lambda results, cfg, dry_run: calls.append(("write", len(results))))
    monkeypatch.setattr(core, "_attach_rollup_metrics", lambda c: None)
    monkeypatch.setattr(core, "build_matched_plays",
                        lambda *a, **k: ([], {}, set(),
                                         {"unsupported": 0, "no_strike": 0, "no_expiry": 0,
                                          "unpriced": 0, "vetoed": 0}))
    monkeypatch.setattr(core, "_run_simulations", lambda *a, **k: [{"ticker": "NVDA"}])

    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv),
                                     "--date", "2026-06-25", "--redo"])
    core.main()

    assert calls == [("delete", "BacktestResults", True), ("write", 1)]


def test_redo_deletes_nothing_on_a_dry_run(tmp_path, monkeypatch):
    cfg_path = _write_cfg(tmp_path, monkeypatch)
    rows_csv = tmp_path / "rows.csv"
    rows_csv.write_text(
        "date,ticker,regime,signal,play,horizon\n"
        "2026-06-25,NVDA,BULL,sweep,Long call 250,swing\n")

    monkeypatch.setattr(identity.sheets_client, "get_all_rows", lambda tab: [
        {"signal_date": "2026-06-25", "ticker": "NVDA", "play": "Long call 250"}])

    def _boom(*a, **k):
        raise AssertionError("deleted rows on a --dry-run")
    monkeypatch.setattr(core.sheets_client, "delete_rows_where", _boom)
    monkeypatch.setattr(core, "_attach_rollup_metrics", lambda c: None)
    monkeypatch.setattr(core, "build_matched_plays",
                        lambda *a, **k: ([], {}, set(),
                                         {"unsupported": 0, "no_strike": 0, "no_expiry": 0,
                                          "unpriced": 0, "vetoed": 0}))
    monkeypatch.setattr(core, "_run_simulations", lambda *a, **k: [{"ticker": "NVDA"}])

    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv),
                                     "--date", "2026-06-25", "--redo", "--dry-run"])
    core.main()
