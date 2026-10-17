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
    """Order is the whole contract: local CSV, then delete, then append. If the
    append landed first, --redo would produce exactly the duplicate it exists to
    prevent; if the delete ran before the CSV, a Sheets failure in it would lose
    the whole simulated run (2026-09-23)."""
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
    from scripts.backtest.shared import results_io
    monkeypatch.setattr(results_io, "ROOT", tmp_path)
    monkeypatch.setattr(results_io, "RESULTS_PATH", tmp_path / "backtests")
    real_writer = results_io.csv.DictWriter

    class _RecordingWriter(real_writer):
        def writeheader(self):
            calls.append(("csv",))
            return super().writeheader()

    monkeypatch.setattr(results_io.csv, "DictWriter", _RecordingWriter)
    monkeypatch.setattr(results_io.sheets_client, "append_rows",
                        lambda tab, rows: calls.append(("append", tab, len(rows))))
    monkeypatch.setattr(core, "_print_summary", lambda results: None)
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

    assert calls == [("csv",), ("delete", "BacktestResults", True),
                     ("append", "BacktestResults", 1)]


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


# ── The proxy tab: plays that could not be priced before (2026-10-17) ──────────
# An unbounded run re-fetched every play that had ever gone to the proxy: a fetch
# that returns no rows writes no cache file, so its contracts were scraped again
# each run (2,204 plays / 3,632 fetches against 193 / 251 bounded).

def _two_tabs(results_rows, proxy_rows):
    def _rows(tab):
        if tab == "BacktestResults":
            return results_rows
        if tab == "BacktestProxy":
            return proxy_rows
        raise AssertionError(f"read unexpected tab {tab!r}")
    return _rows


def _pargs(redo=False, retry_proxied=False):
    return SimpleNamespace(redo=redo, dry_run=False, retry_proxied=retry_proxied)


_PROXIED = {"signal_date": "6/25/2026", "ticker": "AMD", "play": "Long call 150"}
_RESULT = {"signal_date": "6/25/2026", "ticker": "NVDA", "play": "Long call 250"}


def test_proxied_plays_are_dropped_by_default(monkeypatch, caplog):
    monkeypatch.setattr(identity.sheets_client, "get_all_rows",
                        _two_tabs([_RESULT], [_PROXIED]))
    candidates = [_cand(), _cand(ticker="AMD", play="Long call 150"), _cand(ticker="TSLA")]

    with caplog.at_level("INFO", logger="backtest"):
        remaining, redo_keys = core._drop_already_backtested(candidates, _cfg(), _pargs())

    assert [c["ticker"] for c in remaining] == ["TSLA"]
    assert redo_keys == set()
    # Logged separately from the results-tab count.
    assert "SKIPPING 1 play(s) already on 'BacktestResults'" in caplog.text
    assert "SKIPPING 1 play(s) already on 'BacktestProxy'" in caplog.text


def test_proxy_tab_name_comes_from_config(monkeypatch):
    seen = []

    def _rows(tab):
        seen.append(tab)
        return []
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", _rows)
    cfg = {**_cfg(), "proxy": {"sheet_tab": "v4_BacktestProxy"}}

    core._drop_already_backtested([_cand()], cfg, _pargs())

    assert seen == ["BacktestResults", "v4_BacktestProxy"]


def test_retry_proxied_keeps_them(monkeypatch):
    monkeypatch.setattr(identity.sheets_client, "get_all_rows",
                        _two_tabs([_RESULT], [_PROXIED]))
    candidates = [_cand(), _cand(ticker="AMD", play="Long call 150")]

    remaining, _ = core._drop_already_backtested(candidates, _cfg(),
                                                 _pargs(retry_proxied=True))

    # The results-tab guard still applies; only the proxy drop is lifted.
    assert [c["ticker"] for c in remaining] == ["AMD"]


def test_redo_still_replaces_only_results_tab_rows(monkeypatch):
    """--redo is unchanged: it marks only BacktestResults rows for deletion. A
    play on BOTH tabs (a cross-tab duplicate) is still re-simulated, because it
    is the results tab's row; a proxy-only play stays dropped unless
    --retry-proxied."""
    both = {**_RESULT}
    monkeypatch.setattr(identity.sheets_client, "get_all_rows",
                        _two_tabs([_RESULT], [_PROXIED, both]))
    candidates = [_cand(), _cand(ticker="AMD", play="Long call 150")]

    remaining, redo_keys = core._drop_already_backtested(candidates, _cfg(),
                                                         _pargs(redo=True))
    assert [c["ticker"] for c in remaining] == ["NVDA"]
    assert redo_keys == {identity.identity_key(date(2026, 6, 25), "NVDA", "Long call 250")}

    remaining, redo_keys = core._drop_already_backtested(
        candidates, _cfg(), _pargs(redo=True, retry_proxied=True))
    assert [c["ticker"] for c in remaining] == ["NVDA", "AMD"]
    assert redo_keys == {identity.identity_key(date(2026, 6, 25), "NVDA", "Long call 250")}


def test_retry_proxied_flag_reaches_the_guard(tmp_path, monkeypatch):
    cfg_path = _write_cfg(tmp_path, monkeypatch)
    rows_csv = tmp_path / "rows.csv"
    rows_csv.write_text("date,ticker,regime,signal,play,horizon\n"
                        "2026-06-25,AMD,BULL,sweep,Long call 150,swing\n")
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", _two_tabs([], [_PROXIED]))
    reached = []
    monkeypatch.setattr(core, "_attach_rollup_metrics", lambda c: reached.append(len(c)))
    monkeypatch.setattr(core, "build_matched_plays", lambda *a, **k: ([], {}, {}, {}))
    monkeypatch.setattr(core, "_run_simulations", lambda *a, **k: [])
    monkeypatch.setattr(core, "_write_results", lambda *a, **k: None)

    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv)])
    with pytest.raises(SystemExit) as e:
        core.main()                      # dropped by default → nothing to simulate
    assert e.value.code == 0 and reached == []

    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv), "--retry-proxied"])
    core.main()
    assert reached == [1]


# ── --dry-run makes no Barchart call (2026-10-17) ──────────────────────────────

def test_dry_run_makes_no_barchart_call(tmp_path, monkeypatch, capsys):
    """A ~2,200-play preview used to start a ~3,600-fetch scrape and then discard
    it. Any browser session, scrape or write here fails the test."""
    from scripts.backtest.shared import history
    cache = tmp_path / "cache"
    monkeypatch.setattr(history, "HISTORY_CACHE", cache)
    cfg_path = _write_cfg(tmp_path, monkeypatch)
    rows_csv = tmp_path / "rows.csv"
    rows_csv.write_text(
        "date,ticker,regime,signal,play,horizon\n"
        "2026-06-25,NVDA,BULL,sweep,Long call 250 exp 2026-07-17,swing\n"
        "2026-06-25,AMD,BULL,sweep,Long call 150 exp 2026-07-17,swing\n")
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", lambda tab: [])

    def _boom(*a, **k):
        raise AssertionError("network or write on a --dry-run")
    for target, name in [(core, "fetch_option_histories"), (history, "_scrape"),
                         (history, "BarchartSession"), (history, "_open_session"),
                         (core, "_write_results"), (core, "_run_simulations")]:
        monkeypatch.setattr(target, name, _boom)
    monkeypatch.setattr(core, "_attach_rollup_metrics", lambda c: None)

    # One of the two contracts is cached; the other would be scraped.
    plays, contracts, needed, _ = core.build_matched_plays(
        [{"signal_date": date(2026, 6, 25), "date": "2026-06-25", "ticker": t,
          "play": f"Long call {k} exp 2026-07-17", "regime": "BULL", "horizon": "swing"}
         for t, k in (("NVDA", 250), ("AMD", 150))], 0.02)
    assert len(contracts) == 2, "fixture plays must classify"
    nvda = next(c for c in contracts.values() if c["symbol"] == "NVDA")
    path = history.barchart_options.cache_path(
        cache, "NVDA", nvda["expiration"], nvda["strike"], nvda["opt_type"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Time,Open,High,Low,Last,Change,%Chg,Volume,Open Int\n"
                    "06/24/2026,10,10,10,10,0,0%,1,1\n")

    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv), "--dry-run"])
    core.main()

    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "2 distinct — 1 cached, 1 would be scraped" in out
