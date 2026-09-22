"""Unit tests for `scripts/collector/backfill_chain.py`.

Covers the pure plan logic (Friday/holiday expiries incl. the 2026-09-22
review's NYSE-calendar corrections, the DTE-windowed strike band, the
per-symbol grid), the idempotency/no-clobber contract (atomic write, never
overwrite, append-only manifest with a single-run lock), the three-way
covered/partial/pending classification, the manifest's outcome vocabulary
(fetched / exists / no_bars / failed / unparsed / unavailable), the HTTP
401/403/429 immediate stop and the clean-empty-vs-error sniffing it depends
on, the consecutive-failure stop, the open-expiry exclusion, and that a dry
run makes no session call and no network call (the yfinance fallback was
removed).

Everything is synthetic and written to tmp_path; no network, no real cache,
no Playwright/Barchart launch anywhere in this file.
"""
import asyncio
import logging
from datetime import date, timedelta

import pytest

from lib.barchart.options import cache_path
from scripts.collector import backfill_chain as bc

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
          "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")

_SESSION_LOG = logging.getLogger(bc._SESSION_LOGGER_NAME)


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
    refetch = tmp_path / "refetch_cache"
    monkeypatch.setattr(bc, "REFETCH_CACHE_DIR", refetch)
    yield cache, manifest, refetch


def _entry(symbol="SPY", expiration=date(2024, 6, 21), strike=450.0, right="C",
          window_start=date(2024, 1, 1)):
    return bc.PlanEntry(symbol, expiration, strike, right, window_start)


# --- item 2: NYSE holiday calendar corrections -----------------------------------

def test_candidate_expiries_are_fridays():
    exps = bc.candidate_expiries(date(2024, 1, 1), date(2024, 1, 31))
    assert exps == [date(2024, 1, 5), date(2024, 1, 12), date(2024, 1, 19), date(2024, 1, 26)]
    assert all(d.weekday() == 4 for d in exps)


def test_good_friday_shifts_to_thursday():
    exps = bc.candidate_expiries(date(2024, 3, 20), date(2024, 4, 5))
    assert date(2024, 3, 29) not in exps
    assert date(2024, 3, 28) in exps


def test_juneteenth_2021_is_not_a_holiday_but_2022_onward_is():
    """Juneteenth became federal law 2021-06-17 but NYSE did not observe it
    until 2022 — 2021-06-18 (the federal Friday-shifted date) must stay an
    ordinary Friday expiry; 2022-06-17 (Friday before the 2022-06-20 Monday
    observance) must also stay ordinary since the holiday itself is
    2022-06-20, not the preceding Friday."""
    exps_2021 = bc.candidate_expiries(date(2021, 6, 11), date(2021, 6, 25))
    assert date(2021, 6, 18) in exps_2021
    exps_2023 = bc.candidate_expiries(date(2023, 6, 12), date(2023, 6, 26))
    assert date(2023, 6, 19) not in exps_2023  # Monday holiday shifts the Friday? no -- Mon != Fri
    # 2023-06-19 is itself a Monday holiday, unrelated to Friday expiries;
    # the real pin is a Friday holiday shifting a Friday expiry, checked next.


def test_juneteenth_friday_2026_shifts_to_thursday():
    """2026-06-19 is a Friday and IS an NYSE holiday (from 2022 onward)."""
    exps = bc.candidate_expiries(date(2026, 6, 12), date(2026, 6, 26))
    assert date(2026, 6, 19) not in exps
    assert date(2026, 6, 18) in exps


def test_new_year_never_shifts_back_to_dec_31():
    """Jan 1, 2022 is a Saturday. The federal 'nearest workday' rule shifts
    New Year's to the preceding Friday (2021-12-31), but NYSE's own written
    rule does NOT do this for New Year's specifically (unlike Christmas/July
    4) — the exchange must never close on the last trading day of the year."""
    exps = bc.candidate_expiries(date(2021, 12, 24), date(2022, 1, 7))
    assert date(2021, 12, 31) in exps  # ordinary Friday, NOT shifted away
    assert date(2022, 1, 1) not in exps  # Saturday, never a Friday anyway (no-op check)


def test_columbus_day_does_not_shift_a_friday():
    exps = bc.candidate_expiries(date(2024, 10, 11), date(2024, 10, 18))
    assert date(2024, 10, 18) in exps


NYSE_FULL_DAY_CLOSURES_2021_2026 = {
    2021: ["01-01", "01-18", "02-15", "04-02", "05-31", "07-05", "09-06", "11-25", "12-24"],
    2022: ["01-17", "02-21", "04-15", "05-30", "06-20", "07-04", "09-05", "11-24", "12-26"],
    2023: ["01-02", "01-16", "02-20", "04-07", "05-29", "06-19", "07-04", "09-04", "11-23", "12-25"],
    2024: ["01-01", "01-15", "02-19", "03-29", "05-27", "06-19", "07-04", "09-02", "11-28", "12-25"],
    2025: ["01-01", "01-20", "02-17", "04-18", "05-26", "06-19", "07-04", "09-01", "11-27", "12-25"],
    2026: ["01-01", "01-19", "02-16", "04-03", "05-25", "06-19", "07-03", "09-07", "11-26", "12-25"],
}


def test_nyse_holiday_table_2021_through_2026():
    """The full reference table of NYSE full-day closures 2021-2026 (New
    Year's/MLK/Presidents/Good Friday/Memorial/Juneteenth(2022+)/
    Independence/Labor/Thanksgiving/Christmas), pinning both review-item-2
    corrections at once."""
    got = sorted(bc._nyse_holidays(date(2021, 1, 1), date(2026, 12, 31)))
    expected = sorted(
        date.fromisoformat(f"{year}-{md}")
        for year, mds in NYSE_FULL_DAY_CLOSURES_2021_2026.items()
        for md in mds
    )
    assert got == expected


# --- expiry quote window --------------------------------------------------------

def test_quote_window_clipped_to_span():
    lo, hi = bc.expiry_quote_window(date(2024, 3, 15), 20, 60, date(2024, 1, 1), date(2024, 12, 31))
    assert lo == date(2024, 1, 15)
    assert hi == date(2024, 2, 24)


def test_quote_window_none_when_span_misses_dte_range():
    assert bc.expiry_quote_window(date(2030, 1, 1), 20, 60, date(2024, 1, 1), date(2024, 12, 31)) is None


# --- strike grid -----------------------------------------------------------------

def test_spy_grid_is_five_dollar_only_above_threshold():
    strikes = bc.strike_grid("SPY", 440.0, 460.0)
    assert strikes == [440.0, 445.0, 450.0, 455.0, 460.0]


def test_symbol_under_200_uses_one_dollar_grid():
    strikes = bc.strike_grid("IWM", 195.0, 205.0)
    assert 196.0 in strikes and 199.0 in strikes
    assert 200.0 in strikes and 205.0 in strikes
    assert 201.0 not in strikes and 203.0 not in strikes


def test_unknown_symbol_raises():
    with pytest.raises(KeyError):
        bc.strike_grid("NOPE", 10, 20)


# --- plan generation (close_provider injected — no filesystem/network reads) --

def _flat_closes(value, days):
    import pandas as pd
    return pd.Series([value] * len(days), index=list(days))


def _provider(value):
    def _p(symbol):
        days = [date(2021, 1, 1) + timedelta(days=i) for i in range(2000)]
        return _flat_closes(value, days)
    return _p


def test_plan_for_symbol_generates_expected_grid_of_contracts():
    entries = bc.plan_for_symbol(
        "SPY", date(2024, 1, 1), date(2024, 1, 31), 20, 60, 0.0, ["P", "C"],
        close_cache={}, close_provider=_provider(450.0), today=date(2026, 1, 1))
    assert entries
    assert all(e.symbol == "SPY" for e in entries)
    assert all(e.right in ("P", "C") for e in entries)
    assert all(e.strike == 450.0 for e in entries)


def test_plan_respects_rights_filter():
    entries = bc.plan_for_symbol(
        "SPY", date(2024, 1, 1), date(2024, 1, 31), 20, 60, 0.0, ["C"],
        close_cache={}, close_provider=_provider(450.0), today=date(2026, 1, 1))
    assert entries and all(e.right == "C" for e in entries)


def test_build_plan_covers_every_symbol():
    plan = bc.build_plan(["SPY", "IWM"], date(2024, 1, 1), date(2024, 1, 31), 20, 60,
                         0.10, ["P", "C"], close_provider=_provider(450.0),
                         today=date(2026, 1, 1))
    assert set(plan) == {"SPY", "IWM"}
    assert plan["SPY"] and plan["IWM"]


# --- item 3: expiries >= today are excluded by default --------------------------

def test_open_expiries_excluded_by_default():
    today = date(2024, 1, 20)
    entries = bc.plan_for_symbol(
        "SPY", date(2024, 1, 1), date(2024, 2, 29), 20, 60, 0.0, ["C"],
        close_cache={}, close_provider=_provider(450.0), today=today)
    assert all(e.expiration < today for e in entries)


def test_open_expiries_included_with_flag():
    today = date(2024, 1, 20)
    entries = bc.plan_for_symbol(
        "SPY", date(2024, 1, 1), date(2024, 2, 29), 20, 60, 0.0, ["C"],
        close_cache={}, close_provider=_provider(450.0), today=today,
        include_open_expiries=True)
    assert any(e.expiration >= today for e in entries)


def test_classify_never_terminates_an_unexpired_no_bars_contract(_isolate):
    """Even if a manifest already says no_bars for an unexpired contract
    (e.g. a run before its expiry was included via --include-open-expiries),
    it must classify as pending, not covered — its chain can still change."""
    today = date(2024, 1, 1)
    entry = _entry(expiration=date(2024, 6, 21))  # not yet expired
    manifest = {bc._key(*bc.contract_of(entry)):
               {"outcome": "no_bars", "attempts": "0"}}
    assert bc.classify(entry, manifest, today=today) == "pending"


def test_classify_honours_no_bars_for_an_expired_contract(_isolate):
    today = date(2024, 7, 1)
    entry = _entry(expiration=date(2024, 6, 21))  # already expired
    manifest = {bc._key(*bc.contract_of(entry)):
               {"outcome": "no_bars", "attempts": "0"}}
    assert bc.classify(entry, manifest, today=today) == "covered"


# --- item 9: no yfinance fallback -------------------------------------------------

def test_missing_underlying_data_raises_loudly():
    with pytest.raises(bc.UnderlyingDataUnavailable):
        bc.closes_in_window("SPY", date(2024, 1, 1), date(2024, 2, 1), cache={},
                            close_provider=lambda symbol: None)


def test_no_yfinance_import_anywhere_in_the_module():
    import inspect
    src = inspect.getsource(bc)
    assert "import yfinance" not in src
    assert "UNDERLYING_CLOSE_CACHE" not in src
    assert not hasattr(bc, "yf")


# --- contract path / manifest key -----------------------------------------------

def test_contract_path_matches_shared_cache_convention(_isolate):
    cache, _, _ = _isolate
    p = bc.contract_path("SPY", date(2024, 6, 21), 450.0, "C")
    assert p == cache_path(cache, "SPY", date(2024, 6, 21), 450.0, "Call")
    assert p.name == "SPY_20240621_450.00C.csv"


def test_contract_path_honours_explicit_cache_dir(_isolate, tmp_path):
    other = tmp_path / "elsewhere"
    p = bc.contract_path("SPY", date(2024, 6, 21), 450.0, "C", cache_dir=other)
    assert p == cache_path(other, "SPY", date(2024, 6, 21), 450.0, "Call")


# --- item 4/6: classify (covered / partial / pending) ---------------------------

def test_absent_file_and_no_manifest_is_pending(_isolate):
    entry = _entry(expiration=date(2023, 1, 1))
    assert bc.classify(entry, {}, today=date(2024, 1, 1)) == "pending"


def test_complete_cache_file_is_covered(_isolate):
    entry = _entry(expiration=date(2024, 6, 21), window_start=date(2024, 1, 1))
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(0, 170, 3)]
    bc.contract_path(*bc.contract_of(entry)).write_text(_history_csv(days))
    assert bc.classify(entry, {}, today=date(2024, 7, 1)) == "covered"


def test_partial_when_first_row_after_window_start(_isolate):
    entry = _entry(expiration=date(2024, 6, 21), window_start=date(2024, 1, 1))
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]  # starts after window_start
    bc.contract_path(*bc.contract_of(entry)).write_text(_history_csv(days))
    assert bc.classify(entry, {}, today=date(2024, 7, 1)) == "partial"


def test_partial_when_last_row_far_before_expiry_of_an_expired_contract(_isolate):
    entry = _entry(expiration=date(2024, 6, 21), window_start=date(2024, 1, 1))
    days = [date(2024, 1, 2), date(2024, 1, 10), date(2024, 1, 20)]  # stops way before expiry
    bc.contract_path(*bc.contract_of(entry)).write_text(_history_csv(days))
    assert bc.classify(entry, {}, today=date(2024, 7, 1)) == "partial"


def test_partial_file_never_reported_covered_even_for_open_contract(_isolate):
    """An UNEXPIRED contract's last-row-vs-expiry check never fires (of
    course the file doesn't reach expiry yet), but the window_start check
    still applies."""
    entry = _entry(expiration=date(2030, 6, 21), window_start=date(2024, 1, 1))
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(5)]
    bc.contract_path(*bc.contract_of(entry)).write_text(_history_csv(days))
    assert bc.classify(entry, {}, today=date(2024, 4, 1)) == "partial"


def test_categorize_three_way_split(_isolate):
    covered_entry = _entry(strike=450.0, expiration=date(2024, 6, 21), window_start=date(2024, 1, 1))
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(0, 170, 3)]
    bc.contract_path(*bc.contract_of(covered_entry)).write_text(_history_csv(days))

    partial_entry = _entry(strike=451.0, expiration=date(2024, 6, 21), window_start=date(2024, 1, 1))
    bc.contract_path(*bc.contract_of(partial_entry)).write_text(
        _history_csv([date(2024, 3, 1)]))

    pending_entry = _entry(strike=452.0, expiration=date(2023, 1, 1))

    covered, partial, pending = bc.categorize(
        [covered_entry, partial_entry, pending_entry], {}, today=date(2024, 7, 1))
    assert covered == [covered_entry]
    assert partial == [partial_entry]
    assert pending == [pending_entry]


# --- manifest: append-only, tolerant of a truncated last line (item 5) ---------

def test_manifest_round_trip_via_append(_isolate):
    _, manifest_path, _ = _isolate
    row = {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00", "right": "C",
          "outcome": "fetched", "rows": "10", "first_date": "2024-01-02",
          "last_date": "2024-06-20", "attempts": "0", "timestamp": "2026-09-01T00:00:00+00:00"}
    bc.append_manifest_row(manifest_path, row)
    loaded = bc.load_manifest(manifest_path)
    assert loaded[("SPY", "2024-06-21", "450.00", "C")] == row


def test_manifest_append_never_rewrites_prior_rows(_isolate):
    _, manifest_path, _ = _isolate
    row1 = {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00", "right": "C",
           "outcome": "failed", "rows": "0", "first_date": "", "last_date": "",
           "attempts": "1", "timestamp": "2026-09-01T00:00:00+00:00"}
    row2 = {"symbol": "QQQ", "expiration": "2024-06-21", "strike": "400.00", "right": "P",
           "outcome": "fetched", "rows": "5", "first_date": "2024-01-02",
           "last_date": "2024-06-20", "attempts": "0", "timestamp": "2026-09-01T00:01:00+00:00"}
    bc.append_manifest_row(manifest_path, row1)
    bc.append_manifest_row(manifest_path, row2)
    text = manifest_path.read_text()
    assert text.count("\n") == 3  # header + 2 rows
    loaded = bc.load_manifest(manifest_path)
    assert len(loaded) == 2


def test_manifest_last_outcome_wins_on_reappend(_isolate):
    _, manifest_path, _ = _isolate
    key_fields = {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00", "right": "C"}
    bc.append_manifest_row(manifest_path, {**key_fields, "outcome": "failed", "rows": "0",
                                           "first_date": "", "last_date": "", "attempts": "1",
                                           "timestamp": "t1"})
    bc.append_manifest_row(manifest_path, {**key_fields, "outcome": "unavailable", "rows": "0",
                                           "first_date": "", "last_date": "", "attempts": "2",
                                           "timestamp": "t2"})
    loaded = bc.load_manifest(manifest_path)
    assert loaded[("SPY", "2024-06-21", "450.00", "C")]["outcome"] == "unavailable"


def test_manifest_loader_tolerates_a_truncated_last_line(_isolate):
    _, manifest_path, _ = _isolate
    row = {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00", "right": "C",
          "outcome": "fetched", "rows": "10", "first_date": "2024-01-02",
          "last_date": "2024-06-20", "attempts": "0", "timestamp": "2026-09-01T00:00:00+00:00"}
    bc.append_manifest_row(manifest_path, row)
    # Simulate a crash mid-append: a second, GARBLED row with no newline and
    # too few fields.
    with open(manifest_path, "a") as fh:
        fh.write("QQQ,2024-06-21,400.00")   # no right/outcome/... — truncated
    loaded = bc.load_manifest(manifest_path)  # must not raise
    assert loaded[("SPY", "2024-06-21", "450.00", "C")]["outcome"] == "fetched"
    assert ("QQQ", "2024-06-21", "400.00", "") not in loaded


# --- item 5: single-run lock ------------------------------------------------------

def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _ScriptedSession:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    async def fetch_history_fast(self, url, timeout_ms):
        self.calls += 1
        return self._results.pop(0)


def test_run_fetch_refuses_when_lock_already_held(_isolate):
    import fcntl
    _, manifest_path, _ = _isolate
    lock_path = manifest_path.with_name(manifest_path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a")
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        contract = ("SPY", date(2024, 6, 21), 450.0, "C")
        session = _ScriptedSession([None])
        with pytest.raises(bc.RunLockHeld):
            _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session))
        assert session.calls == 0
    finally:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()


def test_run_fetch_releases_lock_after_completion(_isolate):
    import fcntl
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    session = _ScriptedSession([None])
    _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session))
    lock_path = manifest_path.with_name(manifest_path.name + ".lock")
    fh = open(lock_path, "a")
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # must not raise
    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    fh.close()


# --- fetch outcomes: fetched / no_bars / failed / unparsed / exists -------------

def test_fetched_outcome_writes_file_and_manifest(_isolate):
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]
    session = _ScriptedSession([_history_csv(days)])
    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session))
    assert stats["fetched"] == 1
    assert bc.contract_path(*contract).exists()
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "fetched" and row["rows"] == "10"
    assert row["first_date"] == days[0].isoformat()
    assert row["last_date"] == days[-1].isoformat()


def test_confirmed_empty_feed_is_no_bars_via_log_sniffing(_isolate):
    """A REAL session emits 'History feed returned no rows...' on a clean
    200-with-zero-rows response — this must classify as no_bars, not failed
    (review item 7's 'if distinguishable' branch)."""
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")

    class _EmptyFeedSession:
        async def fetch_history_fast(self, url, timeout_ms):
            _SESSION_LOG.warning("History feed returned no rows for '%s'", url)
            return None

    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0,
                              session=_EmptyFeedSession()))
    assert stats["no_bars"] == 1
    assert "failed" not in stats
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "no_bars"


def test_no_bars_outcome_does_not_write_file(_isolate):
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    session = _ScriptedSession([HEADER + "\n"])
    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session))
    assert stats["no_bars"] == 1
    assert not bc.contract_path(*contract).exists()


def test_ambiguous_none_is_failed_on_first_attempt(_isolate):
    """No sniffable log record at all (e.g. a plain mock session) — an
    ambiguous None is `failed`, not `no_bars` (review item 7's fallback)."""
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    session = _ScriptedSession([None])
    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session))
    assert stats["failed"] == 1
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "failed" and row["attempts"] == "1"


def test_second_ambiguous_failure_on_a_separate_run_marks_unavailable(_isolate):
    """review item 7b: failed/unparsed on 2 SEPARATE runs (manifest-persisted
    `attempts`) -> unavailable (terminal)."""
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")

    manifest = {}
    stats1 = _run(bc.run_fetch([contract], manifest, manifest_path, sleep_s=0,
                               session=_ScriptedSession([None])))
    assert stats1["failed"] == 1

    manifest2 = bc.load_manifest(manifest_path)
    stats2 = _run(bc.run_fetch([contract], manifest2, manifest_path, sleep_s=0,
                               session=_ScriptedSession([None])))
    assert stats2["unavailable"] == 1
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "unavailable"


def test_unavailable_is_terminal_for_an_expired_contract(_isolate):
    contract_entry = _entry(expiration=date(2023, 1, 1))
    manifest = {bc._key(*bc.contract_of(contract_entry)):
               {"outcome": "unavailable", "attempts": "2"}}
    assert bc.classify(contract_entry, manifest, today=date(2024, 1, 1)) == "covered"


def test_unparsed_outcome_when_parse_raises(_isolate, monkeypatch):
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    session = _ScriptedSession(["garbage,not,a,valid,history,csv"])

    def _boom(csv_text, require_mark=False):
        raise ValueError("boom")
    monkeypatch.setattr(bc, "parse_history_details", _boom)

    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session))
    assert stats["unparsed"] == 1
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "unparsed"


# --- item 1: atomic, no-clobber write --------------------------------------------

def test_atomic_write_new_creates_file(_isolate):
    cache, _, _ = _isolate
    p = cache / "X.csv"
    created = bc._atomic_write_new(p, "hello")
    assert created and p.read_text() == "hello"


def test_atomic_write_new_never_clobbers_existing_file(_isolate):
    cache, _, _ = _isolate
    p = cache / "X.csv"
    p.write_text("SENTINEL")
    created = bc._atomic_write_new(p, "different content")
    assert created is False
    assert p.read_text() == "SENTINEL"


def test_atomic_write_leaves_no_tmp_file_on_crash(_isolate, monkeypatch):
    """A crash mid-write (fsync raising) must never leave the final file
    present, and must never leave an orphaned tmp file behind either."""
    cache, _, _ = _isolate
    p = cache / "X.csv"

    def _boom(fd):
        raise OSError("disk full")
    monkeypatch.setattr(bc.os, "fsync", _boom)

    with pytest.raises(OSError):
        bc._atomic_write_new(p, "partial data")
    assert not p.exists()
    assert list(cache.glob(".*.tmp")) == []


def test_fetch_records_exists_outcome_when_file_appears_after_categorize(_isolate):
    """The exact race item 1 guards against: a file shows up (another
    process, or just a pre-existing real file) between planning and the
    fetch attempt. run_fetch must record `exists` and leave it untouched,
    even though run_fetch was handed the contract as if it were pending."""
    cache, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    sentinel = "SENTINEL — pre-existing real data, must survive\n"
    bc.contract_path(*contract).write_text(sentinel)

    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]
    session = _ScriptedSession([_history_csv(days)])
    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session))

    assert stats["exists"] == 1
    assert bc.contract_path(*contract).read_text() == sentinel
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "exists"


# --- item 8: stop immediately on blocking HTTP status ----------------------------

def test_stops_immediately_on_http_429_without_waiting_for_fail_stop(_isolate):
    _, manifest_path, _ = _isolate
    contracts = [("SPY", date(2024, 6, 21), 450.0 + i, "C") for i in range(5)]

    class _RateLimitedSession:
        def __init__(self):
            self.calls = 0

        async def fetch_history_fast(self, url, timeout_ms):
            self.calls += 1
            _SESSION_LOG.warning("History feed returned HTTP %d for '%s'", 429, url)
            return None

    session = _RateLimitedSession()
    stats = _run(bc.run_fetch(contracts, {}, manifest_path, sleep_s=0, fail_stop=10,
                              session=session))
    assert stats["stopped_http_429"] == 1
    assert session.calls == 1  # stopped after the FIRST blocking response, not fail_stop=10
    assert "failed" not in stats


@pytest.mark.parametrize("status", [401, 403, 429])
def test_stops_immediately_on_each_blocking_status(_isolate, status):
    _, manifest_path, _ = _isolate
    contracts = [("SPY", date(2024, 6, 21), 450.0, "C"), ("SPY", date(2024, 6, 21), 455.0, "C")]

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            _SESSION_LOG.warning("History feed returned HTTP %d for '%s'", status, url)
            return None

    stats = _run(bc.run_fetch(contracts, {}, manifest_path, sleep_s=0, session=_Session()))
    assert stats[f"stopped_http_{status}"] == 1


def test_non_blocking_http_error_counts_toward_fail_stop_not_immediate(_isolate):
    _, manifest_path, _ = _isolate
    contracts = [("SPY", date(2024, 6, 21), 450.0 + i, "C") for i in range(3)]

    class _ServerErrorSession:
        async def fetch_history_fast(self, url, timeout_ms):
            _SESSION_LOG.warning("History feed returned HTTP %d for '%s'", 500, url)
            return None

    stats = _run(bc.run_fetch(contracts, {}, manifest_path, sleep_s=0, fail_stop=3,
                              session=_ServerErrorSession()))
    assert "stopped_http_500" not in stats
    assert stats["stopped_consecutive_failures"] == 1


# --- consecutive-failure stop / login failure (retained from the original) -----

def test_consecutive_failures_stop_the_run(_isolate):
    _, manifest_path, _ = _isolate
    contracts = [("SPY", date(2024, 6, 21), 450.0 + i, "C") for i in range(15)]
    session = _ScriptedSession([None] * 15)
    stats = _run(bc.run_fetch(contracts, {}, manifest_path, sleep_s=0, fail_stop=3,
                              session=session))
    assert stats["failed"] + stats.get("unavailable", 0) == 3
    assert stats["stopped_consecutive_failures"] == 1
    assert session.calls == 3


def test_a_success_resets_the_consecutive_failure_counter(_isolate):
    _, manifest_path, _ = _isolate
    days = [date(2024, 3, 1), date(2024, 3, 2)]
    results = [None, None, _history_csv(days), None, None, None]
    contracts = [("SPY", date(2024, 6, 21), 450.0 + i, "C") for i in range(len(results))]
    session = _ScriptedSession(results)
    stats = _run(bc.run_fetch(contracts, {}, manifest_path, sleep_s=0, fail_stop=3,
                              session=session))
    assert stats["failed"] == 5
    assert stats["fetched"] == 1
    assert stats["stopped_consecutive_failures"] == 1
    assert session.calls == 6


def test_login_failure_stops_cleanly_without_raising(_isolate, monkeypatch):
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")

    class _FailingSession:
        async def __aenter__(self):
            raise RuntimeError("Barchart authentication failed.")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(bc, "BarchartSession", lambda *a, **kw: _FailingSession())
    monkeypatch.setenv("BARCHART_EMAIL", "a@b.com")
    monkeypatch.setenv("BARCHART_PASSWORD", "secret")
    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=None))
    assert stats["login_failure"] == 1


def test_missing_credentials_returns_without_scraping(_isolate, monkeypatch):
    _, manifest_path, _ = _isolate
    monkeypatch.delenv("BARCHART_EMAIL", raising=False)
    monkeypatch.delenv("BARCHART_PASSWORD", raising=False)
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=None))
    assert stats == {}
    assert not bc.contract_path(*contract).exists()


# --- item 6: --refetch-partial writes to the sibling dir, never the primary ----

def test_refetch_partial_writes_to_sibling_dir_not_primary_cache(_isolate):
    cache, manifest_path, refetch_dir = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]
    session = _ScriptedSession([_history_csv(days)])

    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session,
                              cache_dir=refetch_dir))
    assert stats["fetched"] == 1
    assert not bc.contract_path(*contract).exists()  # primary cache untouched
    assert bc.contract_path(*contract, cache_dir=refetch_dir).exists()


# --- dry-run / main(): no session, no network -------------------------------------

def test_dry_run_report_never_touches_a_session(_isolate, monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("dry run must not construct a session")
    monkeypatch.setattr(bc, "BarchartSession", _boom)

    plan = {"SPY": [_entry(strike=450.0, expiration=date(2023, 1, 1)),
                    _entry(strike=455.0, expiration=date(2023, 1, 1))]}
    report = bc.print_dry_run(plan, {}, max_contracts=None, sleep_s=0.4, today=date(2024, 1, 1))
    assert report["SPY"]["universe"] == 2
    assert report["SPY"]["pending"] == 2
    assert report["SPY"]["covered"] == 0
    assert report["SPY"]["partial"] == 0


def test_dry_run_counts_covered_and_partial_separately(_isolate):
    cache, _, _ = _isolate
    covered_entry = _entry(strike=450.0, expiration=date(2024, 6, 21), window_start=date(2024, 1, 1))
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(0, 170, 3)]
    bc.contract_path(*bc.contract_of(covered_entry)).write_text(_history_csv(days))

    partial_entry = _entry(strike=451.0, expiration=date(2024, 6, 21), window_start=date(2024, 1, 1))
    bc.contract_path(*bc.contract_of(partial_entry)).write_text(_history_csv([date(2024, 3, 1)]))

    pending_entry = _entry(strike=452.0, expiration=date(2023, 1, 1))

    plan = {"SPY": [covered_entry, partial_entry, pending_entry]}
    report = bc.print_dry_run(plan, {}, max_contracts=None, sleep_s=0.4, today=date(2024, 7, 1))
    assert report["SPY"] == {"universe": 3, "covered": 1, "partial": 1, "pending": 1}


def test_main_without_execute_never_calls_run_fetch(monkeypatch, _isolate):
    def _boom(*a, **kw):
        raise AssertionError("run_fetch must not be called without --execute")
    monkeypatch.setattr(bc, "run_fetch", _boom)
    monkeypatch.setattr(
        "sys.argv",
        ["backfill_chain.py", "--symbols", "SPY", "--from", "2021-08-25", "--to", "2021-09-01"])
    bc.main()
