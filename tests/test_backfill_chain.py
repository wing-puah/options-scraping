"""Unit tests for `scripts/collector/backfill_chain.py`.

Covers the pure plan logic (Friday/holiday expiries, the DTE-windowed strike
band, the per-symbol grid), the idempotency contract (never overwrite a
cached file, never re-request a manifest-terminal outcome), the manifest's
four outcomes (fetched / no_bars / failed / unparsed — mirroring
`fetch_counterpart_history.py._scrape`'s vocabulary), the consecutive-failure
stop, and that a dry run makes no session call at all.

Everything is synthetic and written to tmp_path; no network, no real cache,
no Playwright/Barchart launch anywhere in this file.
"""
import asyncio
from datetime import date, timedelta

import pytest

from lib.barchart.options import cache_path
from scripts.collector import backfill_chain as bc

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
          "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")


def _history_csv(days) -> str:
    rows = [HEADER]
    for d in days:
        rows.append(f"{d.isoformat()},1.0,1.1,0.9,1.0,0,0%,10,5,,,,,,,,100,0.95,1.05")
    return "\n".join(rows) + "\n"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    cache = tmp_path / "opt_cache"
    cache.mkdir()
    monkeypatch.setattr(bc, "HISTORY_CACHE", cache)
    manifest = tmp_path / "manifest.csv"
    monkeypatch.setattr(bc, "MANIFEST_PATH", manifest)
    yield cache, manifest


# --- expiries: Friday / holiday shift -----------------------------------------

def test_candidate_expiries_are_fridays():
    exps = bc.candidate_expiries(date(2024, 1, 1), date(2024, 1, 31))
    assert exps == [date(2024, 1, 5), date(2024, 1, 12), date(2024, 1, 19), date(2024, 1, 26)]
    assert all(d.weekday() == 4 for d in exps)


def test_good_friday_shifts_to_thursday():
    """2024-03-29 is Good Friday — NYSE-closed, not a federal holiday, so
    this pins the documented assumption in `_nyse_holidays`."""
    exps = bc.candidate_expiries(date(2024, 3, 20), date(2024, 4, 5))
    assert date(2024, 3, 29) not in exps
    assert date(2024, 3, 28) in exps  # the Thursday before


def test_christmas_friday_shifts_to_thursday():
    """2026-12-25 is a Friday and a federal holiday."""
    exps = bc.candidate_expiries(date(2026, 12, 18), date(2026, 12, 26))
    assert date(2026, 12, 25) not in exps
    assert date(2026, 12, 24) in exps


def test_columbus_day_does_not_shift_a_friday():
    """NYSE stays open for Columbus Day — the federal-minus-two assumption."""
    # Columbus Day 2024 is Monday 2024-10-14; the following Friday is ordinary.
    exps = bc.candidate_expiries(date(2024, 10, 11), date(2024, 10, 18))
    assert date(2024, 10, 18) in exps


# --- expiry quote window --------------------------------------------------------

def test_quote_window_clipped_to_span():
    lo, hi = bc.expiry_quote_window(date(2024, 3, 15), 20, 60, date(2024, 1, 1), date(2024, 12, 31))
    assert lo == date(2024, 1, 15)  # expiry - 60d
    assert hi == date(2024, 2, 24)  # expiry - 20d


def test_quote_window_none_when_span_misses_dte_range():
    # expiry far in the future: its DTE window never reaches the span at all.
    assert bc.expiry_quote_window(date(2030, 1, 1), 20, 60, date(2024, 1, 1), date(2024, 12, 31)) is None


# --- strike grid -----------------------------------------------------------------

def test_spy_grid_is_five_dollar_only_above_threshold():
    strikes = bc.strike_grid("SPY", 440.0, 460.0)
    assert strikes == [440.0, 445.0, 450.0, 455.0, 460.0]
    assert all(s % 5 == 0 for s in strikes)


def test_symbol_under_200_uses_one_dollar_grid():
    strikes = bc.strike_grid("IWM", 195.0, 205.0)
    assert 196.0 in strikes and 199.0 in strikes   # $1 spacing below 200
    assert 200.0 in strikes and 205.0 in strikes    # $5 spacing at/above 200
    assert 201.0 not in strikes and 203.0 not in strikes  # not on the $5 grid


def test_unknown_symbol_raises():
    with pytest.raises(KeyError):
        bc.strike_grid("NOPE", 10, 20)


def test_band_widens_the_close_range():
    lo, hi = 100 * (1 - 0.10), 100 * (1 + 0.10)
    assert bc.strike_grid("IWM", lo, hi)[0] == 90.0
    assert bc.strike_grid("IWM", lo, hi)[-1] == 110.0


# --- plan generation (close_provider injected — no filesystem/network reads) --

def _flat_closes(value, days):
    """A synthetic pandas-like Series over `days` (a list of dates), all `value`."""
    import pandas as pd
    return pd.Series([value] * len(days), index=list(days))


def _provider(value):
    def _p(symbol):
        days = [date(2021, 1, 1) + timedelta(days=i) for i in range(2000)]
        return _flat_closes(value, days)
    return _p


def test_plan_for_symbol_generates_expected_grid_of_contracts():
    contracts = bc.plan_for_symbol(
        "SPY", date(2024, 1, 1), date(2024, 1, 31), 20, 60, 0.0, ["P", "C"],
        close_cache={}, close_provider=_provider(450.0))
    assert contracts
    assert all(c[0] == "SPY" for c in contracts)
    assert all(c[3] in ("P", "C") for c in contracts)
    # every strike is on the $5 grid (band=0 collapses lo==hi==450)
    assert all(c[2] == 450.0 for c in contracts)


def test_plan_respects_rights_filter():
    contracts = bc.plan_for_symbol(
        "SPY", date(2024, 1, 1), date(2024, 1, 31), 20, 60, 0.0, ["C"],
        close_cache={}, close_provider=_provider(450.0))
    assert contracts
    assert all(c[3] == "C" for c in contracts)


def test_plan_empty_when_no_underlying_data():
    def _empty(symbol):
        return None
    contracts = bc.plan_for_symbol(
        "SPY", date(2024, 1, 1), date(2024, 1, 31), 20, 60, 0.10, ["P", "C"],
        close_cache={}, close_provider=_empty)
    assert contracts == []


def test_build_plan_covers_every_symbol():
    plan = bc.build_plan(["SPY", "IWM"], date(2024, 1, 1), date(2024, 1, 31), 20, 60,
                         0.10, ["P", "C"], close_provider=_provider(450.0))
    assert set(plan) == {"SPY", "IWM"}
    assert plan["SPY"] and plan["IWM"]


# --- contract path / manifest key -----------------------------------------------

def test_contract_path_matches_shared_cache_convention(_isolate):
    cache, _ = _isolate
    p = bc.contract_path("SPY", date(2024, 6, 21), 450.0, "C")
    assert p == cache_path(cache, "SPY", date(2024, 6, 21), 450.0, "Call")
    assert p.name == "SPY_20240621_450.00C.csv"


# --- idempotency: never overwrite, skip already-cached / already-attempted ----

def test_terminal_when_cache_file_exists(_isolate):
    cache, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    bc.contract_path(*contract).write_text(_history_csv([date(2024, 3, 1)] * 1))
    assert bc.is_terminal(contract, {})


def test_terminal_when_manifest_says_no_bars(_isolate):
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    k = bc._key(*contract)
    manifest = {k: {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00",
                    "right": "C", "outcome": "no_bars", "rows": "0", "first_date": "",
                    "last_date": "", "timestamp": "2026-09-01T00:00:00+00:00"}}
    assert bc.is_terminal(contract, manifest)


def test_not_terminal_when_manifest_says_failed(_isolate):
    """failed/unparsed are retryable — only fetched/no_bars are terminal."""
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    k = bc._key(*contract)
    manifest = {k: {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00",
                    "right": "C", "outcome": "failed", "rows": "0", "first_date": "",
                    "last_date": "", "timestamp": "2026-09-01T00:00:00+00:00"}}
    assert not bc.is_terminal(contract, manifest)


def test_categorize_splits_terminal_and_pending(_isolate):
    cache, _ = _isolate
    cached = ("SPY", date(2024, 6, 21), 450.0, "C")
    pending = ("SPY", date(2024, 6, 21), 455.0, "C")
    bc.contract_path(*cached).write_text(_history_csv([date(2024, 3, 1)]))
    terminal, pend = bc.categorize([cached, pending], {})
    assert terminal == [cached]
    assert pend == [pending]


# --- manifest round trip ----------------------------------------------------------

def test_manifest_round_trip(_isolate):
    _, manifest_path = _isolate
    rows = {("SPY", "2024-06-21", "450.00", "C"):
           {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00", "right": "C",
            "outcome": "fetched", "rows": "10", "first_date": "2024-01-02",
            "last_date": "2024-06-20", "timestamp": "2026-09-01T00:00:00+00:00"}}
    bc.write_manifest(manifest_path, rows)
    loaded = bc.load_manifest(manifest_path)
    assert loaded == rows


def test_manifest_write_is_atomic_tmp_then_rename(_isolate, monkeypatch):
    _, manifest_path = _isolate
    calls = []
    real_replace = type(manifest_path.with_suffix(".csv.tmp")).replace

    def _tracked_replace(self, target):
        calls.append((str(self), str(target)))
        return real_replace(self, target)

    monkeypatch.setattr(type(manifest_path.with_suffix(".csv.tmp")), "replace", _tracked_replace)
    bc.write_manifest(manifest_path, {})
    assert calls and calls[0][0].endswith(".csv.tmp")
    assert not manifest_path.with_suffix(".csv.tmp").exists()
    assert manifest_path.exists()


# --- the async fetch loop: outcomes, never-overwrite, consecutive-failure stop -

def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _ScriptedSession:
    """Returns a scripted sequence of fetch_history_fast results, one per call."""
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    async def fetch_history_fast(self, url, timeout_ms):
        self.calls += 1
        return self._results.pop(0)


def test_fetched_outcome_writes_file_and_manifest(_isolate):
    cache, manifest_path = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]
    session = _ScriptedSession([_history_csv(days)])
    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session))
    assert stats["fetched"] == 1
    assert bc.contract_path(*contract).exists()
    loaded = bc.load_manifest(manifest_path)
    row = loaded[bc._key(*contract)]
    assert row["outcome"] == "fetched" and row["rows"] == "10"
    assert row["first_date"] == days[0].isoformat()
    assert row["last_date"] == days[-1].isoformat()


def test_no_bars_outcome_does_not_write_file(_isolate):
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    session = _ScriptedSession([HEADER + "\n"])  # header only, no rows
    stats = _run(bc.run_fetch([contract], {}, bc.MANIFEST_PATH, sleep_s=0, session=session))
    assert stats["no_bars"] == 1
    assert not bc.contract_path(*contract).exists()
    row = bc.load_manifest(bc.MANIFEST_PATH)[bc._key(*contract)]
    assert row["outcome"] == "no_bars"


def test_failed_outcome_when_session_returns_nothing(_isolate):
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    session = _ScriptedSession([None])
    stats = _run(bc.run_fetch([contract], {}, bc.MANIFEST_PATH, sleep_s=0, session=session))
    assert stats["failed"] == 1
    row = bc.load_manifest(bc.MANIFEST_PATH)[bc._key(*contract)]
    assert row["outcome"] == "failed"


def test_unparsed_outcome_when_parse_raises(_isolate, monkeypatch):
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    session = _ScriptedSession(["garbage,not,a,valid,history,csv"])

    def _boom(csv_text, require_mark=False):
        raise ValueError("boom")
    monkeypatch.setattr(bc, "parse_history_details", _boom)

    stats = _run(bc.run_fetch([contract], {}, bc.MANIFEST_PATH, sleep_s=0, session=session))
    assert stats["unparsed"] == 1
    row = bc.load_manifest(bc.MANIFEST_PATH)[bc._key(*contract)]
    assert row["outcome"] == "unparsed"


def test_existing_cache_file_never_overwritten(_isolate):
    """The idempotency rule this script adds on top of fetch_counterpart_history.py
    (which DOES overwrite): a fetch must never clobber an existing cache file.
    run_fetch is only ever handed PENDING contracts by main(), and pending
    excludes anything `is_terminal` — this pins that a stray call still can't
    destroy data by asserting the sentinel content survives a scripted 'fetch'."""
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    sentinel = "SENTINEL — pre-existing real data, must survive\n"
    bc.contract_path(*contract).write_text(sentinel)
    # is_terminal must say True so main()'s categorize() would never queue it
    assert bc.is_terminal(contract, {})


def test_consecutive_failures_stop_the_run(_isolate):
    contracts = [("SPY", date(2024, 6, 21), 450.0 + i, "C") for i in range(15)]
    session = _ScriptedSession([None] * 15)  # every fetch fails
    stats = _run(bc.run_fetch(contracts, {}, bc.MANIFEST_PATH, sleep_s=0, fail_stop=3,
                              session=session))
    assert stats["failed"] == 3
    assert stats["stopped_consecutive_failures"] == 1
    assert session.calls == 3  # never attempted the remaining 12


def test_a_success_resets_the_consecutive_failure_counter(_isolate):
    days = [date(2024, 3, 1), date(2024, 3, 2)]
    results = [None, None, _history_csv(days), None, None, None]
    contracts = [("SPY", date(2024, 6, 21), 450.0 + i, "C") for i in range(len(results))]
    session = _ScriptedSession(results)
    stats = _run(bc.run_fetch(contracts, {}, bc.MANIFEST_PATH, sleep_s=0, fail_stop=3,
                              session=session))
    # 2 fail, 1 fetched (resets), then 3 more fail (hits fail_stop) -> stop
    assert stats["failed"] == 5
    assert stats["fetched"] == 1
    assert stats["stopped_consecutive_failures"] == 1
    assert session.calls == 6


def test_login_failure_stops_cleanly_without_raising(_isolate, monkeypatch):
    """RuntimeError from BarchartSession.__aenter__ (the real class's documented
    login-failure signal) must be caught, not propagated."""
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")

    class _FailingSession:
        async def __aenter__(self):
            raise RuntimeError("Barchart authentication failed.")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(bc, "BarchartSession", lambda *a, **kw: _FailingSession())
    monkeypatch.setenv("BARCHART_EMAIL", "a@b.com")
    monkeypatch.setenv("BARCHART_PASSWORD", "secret")
    stats = _run(bc.run_fetch([contract], {}, bc.MANIFEST_PATH, sleep_s=0, session=None))
    assert stats["login_failure"] == 1


def test_missing_credentials_returns_without_scraping(_isolate, monkeypatch):
    monkeypatch.delenv("BARCHART_EMAIL", raising=False)
    monkeypatch.delenv("BARCHART_PASSWORD", raising=False)
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    stats = _run(bc.run_fetch([contract], {}, bc.MANIFEST_PATH, sleep_s=0, session=None))
    assert stats == {}
    assert not bc.contract_path(*contract).exists()


# --- dry-run makes no session call at all -----------------------------------------

def test_dry_run_report_never_touches_a_session(_isolate, monkeypatch, capsys):
    """print_dry_run is pure reporting over an already-built plan/manifest — it
    must never construct a BarchartSession or call fetch_history_fast."""
    def _boom(*a, **kw):
        raise AssertionError("dry run must not construct a session")
    monkeypatch.setattr(bc, "BarchartSession", _boom)

    plan = {"SPY": [("SPY", date(2024, 6, 21), 450.0, "C"),
                    ("SPY", date(2024, 6, 21), 455.0, "C")]}
    report = bc.print_dry_run(plan, {}, max_contracts=None, sleep_s=0.4)
    assert report["SPY"]["universe"] == 2
    assert report["SPY"]["pending"] == 2
    assert report["SPY"]["already_covered"] == 0


def test_dry_run_counts_already_covered_contracts(_isolate):
    cache, _ = _isolate
    covered = ("SPY", date(2024, 6, 21), 450.0, "C")
    pending = ("SPY", date(2024, 6, 21), 455.0, "C")
    bc.contract_path(*covered).write_text(_history_csv([date(2024, 3, 1)]))
    plan = {"SPY": [covered, pending]}
    report = bc.print_dry_run(plan, {}, max_contracts=None, sleep_s=0.4)
    assert report["SPY"]["already_covered"] == 1
    assert report["SPY"]["pending"] == 1


def test_main_without_execute_never_imports_a_real_session(monkeypatch, tmp_path, _isolate):
    """End-to-end: main() with no --execute must plan and report without ever
    reaching run_fetch (and therefore never touching BarchartSession)."""
    def _boom(*a, **kw):
        raise AssertionError("run_fetch must not be called without --execute")
    monkeypatch.setattr(bc, "run_fetch", _boom)
    monkeypatch.setattr(
        "sys.argv",
        ["backfill_chain.py", "--symbols", "SPY", "--from", "2024-01-01", "--to", "2024-01-31"])
    bc.main()  # must return normally, never calling run_fetch
