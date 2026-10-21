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
    # `backtest.shared.history`, the module core.py imported — NOT
    # `scripts.backtest.shared.history`, a second copy whose HISTORY_CACHE core
    # never reads (this test used to plan against the real cache).
    from backtest.shared import history
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
    # Reaches back past the signal date (start check) and was fetched today,
    # after the contract expired (forward check: final).
    path.write_text('Time,Open,High,Low,Latest,Change,%Change,Volume,"Open Int",IV,Delta,'
                    "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask\n"
                    "2026-06-24,10,10,10,10,0,0%,1,1,0.3,0.5,0.01,-0.02,0.05,0.01,"
                    "10,250,9.9,10.1\n")

    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv), "--dry-run"])
    core.main()

    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "2 distinct — 1 cached, 1 would be scraped" in out


# ── Open rows are re-priced in place (2026-10-21) ──────────────────────────────
# A row stored `open_at_data_end` ran out of price data before an exit fired.
# It is the one exception to "backtested once": it stays a candidate, and its
# new row replaces the old only when it says something new.

_OPEN = {"signal_date": "6/25/2026", "ticker": "NVDA", "play": "Long call 250",
         "path_status": "open_at_data_end", "path_data_end": "2026-07-10",
         "exit_reason": "cap_open", "realized_pnl_pct": 0.1}
_DONE = {"signal_date": "6/25/2026", "ticker": "AMD", "play": "Long call 150",
         "path_status": "complete", "path_data_end": "2026-07-02",
         "exit_reason": "profit_target"}


def _rargs(**kw):
    return SimpleNamespace(**{"redo": False, "dry_run": False, "retry_proxied": False,
                              "no_reprice_open": False, **kw})


def test_open_row_is_a_reprice_candidate_and_a_complete_row_is_skipped(monkeypatch):
    monkeypatch.setattr(identity.sheets_client, "get_all_rows",
                        _two_tabs([_OPEN, _DONE], []))
    candidates = [_cand(), _cand(ticker="AMD", play="Long call 150")]

    remaining, redo_keys, reprice = core._split_already_backtested(
        candidates, _cfg(), _rargs())

    assert [c["ticker"] for c in remaining] == ["NVDA"]
    assert redo_keys == set()
    assert set(reprice) == {identity.identity_key(date(2026, 6, 25), "NVDA", "Long call 250")}


def test_no_reprice_open_restores_the_skip(monkeypatch):
    monkeypatch.setattr(identity.sheets_client, "get_all_rows",
                        _two_tabs([_OPEN, _DONE], []))
    candidates = [_cand(), _cand(ticker="AMD", play="Long call 150")]

    remaining, _, reprice = core._split_already_backtested(
        candidates, _cfg(), _rargs(no_reprice_open=True))

    assert remaining == [] and reprice == {}


def test_redo_is_unchanged_by_repricing(monkeypatch):
    monkeypatch.setattr(identity.sheets_client, "get_all_rows",
                        _two_tabs([_OPEN, _DONE], []))
    candidates = [_cand(), _cand(ticker="AMD", play="Long call 150")]

    remaining, redo_keys, reprice = core._split_already_backtested(
        candidates, _cfg(), _rargs(redo=True))

    assert len(remaining) == 2 and len(redo_keys) == 2 and reprice == {}


def _new_row(**kw):
    return {"signal_date": "2026-06-25", "ticker": "NVDA", "play": "Long call 250",
            "realized_pnl_pct": 0.1, "path_status": "open_at_data_end",
            "path_data_end": "2026-07-10", "exit_reason": "cap_open", **kw}


@pytest.mark.parametrize("new, kept", [
    (_new_row(), False),                                         # nothing new
    (_new_row(path_data_end="2026-08-21"), True),                # data reaches further
    (_new_row(path_status="complete", exit_reason="profit_target"), True),
    (_new_row(path_data_end="2026-08-21", realized_pnl_pct=""), False),  # not priced now
])
def test_reprice_changed(new, kept):
    assert identity.reprice_changed(new, _OPEN) is kept


def test_split_repriced_passes_new_plays_through():
    k = identity.identity_key(date(2026, 6, 25), "NVDA", "Long call 250")
    fresh = {"signal_date": "2026-06-26", "ticker": "TSLA", "play": "x", "realized_pnl_pct": 0}
    kept, replace = identity.split_repriced(
        [fresh, _new_row(path_data_end="2026-08-21")], {k: _OPEN})
    assert len(kept) == 2 and replace == {k}
    kept, replace = identity.split_repriced([fresh, _new_row()], {k: _OPEN})
    assert kept == [fresh] and replace == set()


def _reprice_main(tmp_path, monkeypatch, sim_results, extra_argv=()):
    """Drive core.main() over two open rows (NVDA, TSLA) with a stubbed
    simulation; returns the ordered write calls."""
    cfg_path = _write_cfg(tmp_path, monkeypatch)
    rows_csv = tmp_path / "rows.csv"
    rows_csv.write_text(
        "date,ticker,regime,signal,play,horizon\n"
        "2026-06-25,NVDA,BULL,sweep,Long call 250,swing\n"
        "2026-06-25,TSLA,BULL,sweep,Long call 300,swing\n")
    tsla_open = {**_OPEN, "ticker": "TSLA", "play": "Long call 300"}
    monkeypatch.setattr(identity.sheets_client, "get_all_rows",
                        _two_tabs([_OPEN, tsla_open], []))

    calls = []
    monkeypatch.setattr(core.sheets_client, "delete_rows_where",
                        lambda tab, fn: calls.append(
                            ("delete", sorted(r["ticker"] for r in (_OPEN, tsla_open)
                                              if fn(r)))))
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
                        lambda tab, rows: calls.append(
                            ("append", sorted(r["ticker"] for r in rows))))
    monkeypatch.setattr(core, "_print_summary", lambda results: None)
    monkeypatch.setattr(core, "_attach_rollup_metrics", lambda c: None)
    seen = []
    monkeypatch.setattr(core, "build_matched_plays",
                        lambda cands, *a, **k: (seen.extend(c["ticker"] for c in cands)
                                                or [], {}, {}, {}))
    monkeypatch.setattr(core, "_run_simulations", lambda *a, **k: list(sim_results))
    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv), *extra_argv])
    try:
        core.main()
    except SystemExit as e:
        assert e.code == 0
    return calls, seen


def test_reprice_writes_csv_then_deletes_only_replaced_keys_then_appends(
        tmp_path, monkeypatch):
    sims = [_new_row(path_data_end="2026-08-21", path_status="complete",
                     exit_reason="expired"),                       # NVDA: changed
            _new_row(ticker="TSLA", play="Long call 300")]         # TSLA: unchanged
    calls, seen = _reprice_main(tmp_path, monkeypatch, sims)
    assert sorted(seen) == ["NVDA", "TSLA"]
    assert calls == [("csv",), ("delete", ["NVDA"]), ("append", ["NVDA"])]


def test_unchanged_reprice_deletes_and_appends_nothing(tmp_path, monkeypatch):
    calls, _ = _reprice_main(tmp_path, monkeypatch,
                             [_new_row(), _new_row(ticker="TSLA", play="Long call 300")])
    assert not any(c[0] in ("delete", "append") for c in calls)


def test_reprice_that_now_prices_nothing_keeps_the_old_row(tmp_path, monkeypatch):
    calls, _ = _reprice_main(tmp_path, monkeypatch, [])
    assert not any(c[0] in ("delete", "append") for c in calls)


def test_no_reprice_open_flag_skips_open_rows(tmp_path, monkeypatch):
    calls, seen = _reprice_main(tmp_path, monkeypatch, [_new_row(path_data_end="2026-08-21")],
                                extra_argv=["--no-reprice-open"])
    assert seen == [] and calls == []


def test_build_needed_ends_takes_the_latest_path_end_capped_at_the_last_session():
    from backtest.plays import build_needed_ends
    exp = date(2026, 8, 21)
    p1 = SimpleNamespace(c={"signal_date": date(2026, 6, 1)},
                         contracts=[("NVDA", "Call", 250.0, exp)])
    p2 = SimpleNamespace(c={"signal_date": date(2026, 3, 2)},          # cap: 2026-06-30
                         contracts=[("NVDA", "Call", 250.0, exp)])
    p3 = SimpleNamespace(c={"signal_date": date(2026, 10, 1)},
                         contracts=[("SPY", "Put", 500.0, date(2027, 1, 15))])
    ends = build_needed_ends([p1, p2, p3], 120, today=date(2026, 10, 21))
    from backtest.helpers import _contract_key
    assert ends[_contract_key("NVDA", "Call", 250.0, exp.isoformat())] == exp
    assert ends[_contract_key("SPY", "Put", 500.0, "2027-01-15")] == date(2026, 10, 20)


# ── Finished rows whose price cache changed are re-priced (2026-10-21) ─────────
# A finished row is priced from cache files other plays share. When a later run
# refetches one (a forward refresh for an open row), the finished row still
# carries the old file's marks. It is re-simulated from the cache, never
# fetched for, and replaced only when a simulated column changed.

import os  # noqa: E402

_LEGS = "NVDA:2026-08-21:250:C +1\nNVDA:2026-08-21:270:C -1"
_FINISHED = {"signal_date": "6/25/2026", "ticker": "NVDA", "play": "Long call 250",
             "legs": _LEGS, "path_status": "complete", "path_data_end": "2026-07-10",
             "exit_reason": "profit_target", "realized_pnl_pct": 0.5, "mfe_abs": 120,
             "daily_price_csv": "1.0,1.5", "created_datetime": "2026-09-24 13:06:02"}


def _touch_legs(cache, row, when: str):
    """Write the row's leg cache files with mtime ``when`` (local time)."""
    from datetime import datetime as _dt
    ts = _dt.fromisoformat(when).timestamp()
    for f in identity.leg_cache_files(row, cache):
        f.write_text("x")
        os.utime(f, (ts, ts))


@pytest.mark.parametrize("when, stale", [
    ("2026-10-21 14:01:29", True),      # rewritten after the row
    ("2026-09-24 13:06:02", False),     # same second as the row: not later
    ("2026-09-23 11:00:00", False),     # older than the row
])
def test_cache_changed_keys_compares_leg_mtime_to_created(tmp_path, when, stale):
    k = identity.identity_key("6/25/2026", "NVDA", "Long call 250")
    _touch_legs(tmp_path, _FINISHED, when)
    assert (identity.cache_changed_keys({k: _FINISHED}, tmp_path) == {k}) is stale


def test_cache_changed_keys_ignores_missing_files_and_blank_created(tmp_path):
    k = identity.identity_key("6/25/2026", "NVDA", "Long call 250")
    assert identity.cache_changed_keys({k: _FINISHED}, tmp_path) == set()
    _touch_legs(tmp_path, _FINISHED, "2026-10-21 14:01:29")
    blank = {**_FINISHED, "created_datetime": ""}
    assert identity.cache_changed_keys({k: blank}, tmp_path) == set()


def test_watch_keys_are_priced_rows_that_are_not_open():
    rows = {1: _FINISHED, 2: {**_FINISHED, "path_status": "open_at_data_end"},
            3: {**_FINISHED, "realized_pnl_pct": ""}}
    assert identity.watch_keys(rows) == {1}


@pytest.mark.parametrize("new, kept", [
    ({**_FINISHED, "realized_pnl_pct": "0.5", "mfe_abs": 120.0}, False),  # same, reformatted
    ({**_FINISHED, "mfe_abs": 180}, True),                               # marks moved
    ({**_FINISHED, "daily_price_csv": "1.0,1.5,1.7"}, True),
    ({**_FINISHED, "mfe_abs": 180, "path_data_end": "2026-07-01"}, False),  # shorter: regression
    ({**_FINISHED, "created_datetime": "2026-10-21 15:00:00"}, False),   # bookkeeping only
    ({**_FINISHED, "regime": "BEAR"}, False),                            # analysis copy, not priced
])
def test_reprice_changed_on_a_finished_row(new, kept):
    assert identity.reprice_changed(new, _FINISHED) is kept


def _stale_main(tmp_path, monkeypatch, cache_when, sim_row, extra_argv=()):
    """Drive core.main() over one FINISHED row with real mtime checks and a
    stubbed plan/fetch/simulation; returns (write calls, plays simulated,
    contracts held off the scrape queue)."""
    from backtest.shared.history import FetchPlan
    cfg_path = _write_cfg(tmp_path, monkeypatch)
    rows_csv = tmp_path / "rows.csv"
    rows_csv.write_text("date,ticker,regime,signal,play,horizon\n"
                        "2026-06-25,NVDA,BULL,sweep,Long call 250,swing\n")
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(identity, "HISTORY_CACHE", cache)
    if cache_when:
        _touch_legs(cache, _FINISHED, cache_when)
    monkeypatch.setattr(identity.sheets_client, "get_all_rows", _two_tabs([_FINISHED], []))

    calls, simulated, held = [], [], []
    monkeypatch.setattr(core.sheets_client, "delete_rows_where",
                        lambda tab, fn: calls.append(("delete", fn(_FINISHED))))
    from scripts.backtest.shared import results_io
    monkeypatch.setattr(results_io, "ROOT", tmp_path)
    monkeypatch.setattr(results_io, "RESULTS_PATH", tmp_path / "backtests")
    monkeypatch.setattr(results_io.sheets_client, "append_rows",
                        lambda tab, rows: calls.append(("append", len(rows))))
    monkeypatch.setattr(core, "_print_summary", lambda results: None)
    monkeypatch.setattr(core, "_attach_rollup_metrics", lambda c: None)
    exp = date(2026, 8, 21)
    contracts = {("NVDA", "Call", 250.0, exp.isoformat()): None,
                 ("NVDA", "Call", 270.0, exp.isoformat()): None}

    def fake_build(cands, *a, **k):
        plays = [SimpleNamespace(c=c, contracts=[("NVDA", "Call", 250.0, exp),
                                                 ("NVDA", "Call", 270.0, exp)])
                 for c in cands]
        return plays, {k_: {"key": k_} for k_ in contracts}, {}, {}

    class _Plan(FetchPlan):
        def hold(self, keys):
            held.extend(keys)
            return super().hold(keys)

    def fake_plan(contracts_, needed_dates, **kw):
        assert needed_dates == {} and kw["needed_ends"] == {}   # a watched row adds no demand
        return _Plan(to_scrape=list(contracts_))                 # as if both were missing

    async def fake_fetch(*a, plan=None, **k):
        assert plan.to_scrape == []                              # held: no fetch
        return {}, {}

    monkeypatch.setattr(core, "build_matched_plays", fake_build)
    monkeypatch.setattr(core, "plan_option_histories", fake_plan)
    monkeypatch.setattr(core, "fetch_option_histories", fake_fetch)
    monkeypatch.setattr(core, "_run_simulations",
                        lambda plays, *a, **k: (simulated.extend(p.c["ticker"] for p in plays)
                                                or [dict(sim_row)] if plays else []))
    monkeypatch.setattr("sys.argv", ["backtest", "--config", str(cfg_path),
                                     "--analysis-csv", str(rows_csv), *extra_argv])
    try:
        core.main()
    except SystemExit as e:
        assert e.code == 0
    return calls, simulated, held


def test_cache_newer_than_row_and_changed_result_replaces_it(tmp_path, monkeypatch):
    calls, simulated, held = _stale_main(tmp_path, monkeypatch, "2026-10-21 14:01:29",
                                         {**_FINISHED, "mfe_abs": 180})
    assert simulated == ["NVDA"] and len(held) == 2
    assert calls == [("delete", True), ("append", 1)]


def test_cache_newer_than_row_and_unchanged_result_writes_nothing(tmp_path, monkeypatch):
    calls, simulated, _ = _stale_main(tmp_path, monkeypatch, "2026-10-21 14:01:29",
                                      dict(_FINISHED))
    assert simulated == ["NVDA"]
    assert not any(c[0] in ("delete", "append") for c in calls)


def test_cache_older_than_row_is_not_resimulated(tmp_path, monkeypatch):
    calls, simulated, _ = _stale_main(tmp_path, monkeypatch, "2026-09-23 11:00:00",
                                      {**_FINISHED, "mfe_abs": 180})
    assert simulated == [] and calls == []


def test_no_reprice_stale_skips_finished_rows(tmp_path, monkeypatch):
    calls, simulated, _ = _stale_main(tmp_path, monkeypatch, "2026-10-21 14:01:29",
                                      {**_FINISHED, "mfe_abs": 180},
                                      extra_argv=["--no-reprice-stale"])
    assert simulated == [] and calls == []


def test_cache_changed_reprice_on_other_legs_keeps_the_stored_row(tmp_path, monkeypatch):
    moved = {**_FINISHED, "mfe_abs": 180,
             "legs": "NVDA:2026-08-07:250:C +1\nNVDA:2026-08-07:270:C -1"}
    calls, simulated, _ = _stale_main(tmp_path, monkeypatch, "2026-10-21 14:01:29", moved)
    assert simulated == ["NVDA"]
    assert not any(c[0] in ("delete", "append") for c in calls)


def test_pin_stored_expiry_beats_the_cache_scan(tmp_path):
    from backtest.classify import _resolve_expiry
    c = {"ticker": "NVDA", "play": "bull call spread 250/270", "horizon": "swing",
         "signal_date": date(2026, 6, 25)}
    identity.pin_stored_expiry(c, _FINISHED)
    assert c["expiry_pin"] == date(2026, 8, 21)
    exp, skip = _resolve_expiry(c, "Call", 250.0, tmp_path)   # empty cache: no scan hit
    assert exp == date(2026, 8, 21) and skip is None
    calendar = {**_FINISHED, "legs": "NVDA:2026-08-21:250:C -1\nNVDA:2026-09-18:250:C +1"}
    c2 = {}
    identity.pin_stored_expiry(c2, calendar)                  # two expiries: no pin
    assert "expiry_pin" not in c2
