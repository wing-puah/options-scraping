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
import csv
import logging
from datetime import date, datetime, timedelta, timezone

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
          "last_date": "2024-06-20", "attempts": "0", "first_attempt_at": "", "reason": "",
          "timestamp": "2026-09-01T00:00:00+00:00"}
    bc.append_manifest_row(manifest_path, row)
    loaded = bc.load_manifest(manifest_path)
    assert loaded[("SPY", "2024-06-21", "450.00", "C")] == row


# --- item 5 (re-review): newline repair before an append ------------------------

def test_append_repairs_a_truncated_final_line_before_appending(_isolate):
    _, manifest_path, _ = _isolate
    manifest_path.write_text(
        ",".join(bc.MANIFEST_FIELDS) + "\nSPY,2024-06-21,450.00")  # no trailing newline
    row = {"symbol": "QQQ", "expiration": "2024-06-21", "strike": "400.00", "right": "P",
          "outcome": "fetched", "rows": "5", "first_date": "2024-01-02",
          "last_date": "2024-06-20", "attempts": "0", "first_attempt_at": "", "reason": "",
          "timestamp": "2026-09-01T00:01:00+00:00"}
    bc.append_manifest_row(manifest_path, row)
    text = manifest_path.read_text()
    assert "450.00\nQQQ,2024-06-21,400.00" in text  # separated, not concatenated
    loaded = bc.load_manifest(manifest_path)
    assert loaded[("QQQ", "2024-06-21", "400.00", "P")]["outcome"] == "fetched"


def test_append_writes_header_when_file_exists_but_empty(_isolate):
    _, manifest_path, _ = _isolate
    manifest_path.touch()
    row = {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00", "right": "C",
          "outcome": "fetched", "rows": "1", "first_date": "", "last_date": "",
          "attempts": "0", "first_attempt_at": "", "timestamp": "t"}
    bc.append_manifest_row(manifest_path, row)
    lines = manifest_path.read_text().splitlines()
    assert lines[0].startswith("symbol,")
    assert len(lines) == 2


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


# --- item 1 (re-review): HTTP error is sticky, not last-message-wins -----------

def test_429_then_fallback_no_rows_is_blocked_not_no_bars(_isolate):
    """The exact failure the re-review found: a 'Re-issued feed HTTP 429'
    followed by the fallback navigation logging 'History feed returned no
    rows' must NOT resolve to a confirmed-empty no_bars that resets the fail
    counter — the 429 must decide the outcome."""
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            _SESSION_LOG.warning("Re-issued feed HTTP %d for '%s' — re-navigating", 429, url)
            _SESSION_LOG.warning("History feed returned no rows for '%s'", url)
            return None

    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=_Session()))
    assert stats["stopped_http_429"] == 1
    assert "no_bars" not in stats


def test_empty_after_an_http_error_from_a_different_attempt_is_unaffected():
    """The signal is per-fetch (a fresh _HistorySignal each _fetch_one call)
    — an http_error from one contract must never leak into the next."""
    signal_a = bc._HistorySignal()
    handler_a = bc._HistorySniffHandler(signal_a)
    handler_a.emit(logging.LogRecord("lib.barchart.session", logging.WARNING, "", 0,
                                     "History feed returned HTTP %d for '%s'",
                                     (429, "url1"), None))
    signal_b = bc._HistorySignal()
    handler_b = bc._HistorySniffHandler(signal_b)
    handler_b.emit(logging.LogRecord("lib.barchart.session", logging.WARNING, "", 0,
                                     "History feed returned no rows for '%s'", ("url2",), None))
    assert signal_a.kind == "http_error" and signal_b.kind == "empty"


# --- item 2 (re-review): near-the-money guard + no_bars consecutive stop -------

def test_near_the_money_empty_is_failed_not_no_bars(_isolate):
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")

    class _EmptyFeedSession:
        async def fetch_history_fast(self, url, timeout_ms):
            _SESSION_LOG.warning("History feed returned no rows for '%s'", url)
            return None

    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0,
                              session=_EmptyFeedSession(),
                              near_money={contract: True}))
    assert stats["failed"] == 1
    assert "no_bars" not in stats
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "failed"


def test_near_the_money_too_few_bars_is_failed_not_no_bars(_isolate):
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    session = _ScriptedSession([HEADER + "\n"])  # 0 parsed bars
    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session,
                              near_money={contract: True}))
    assert stats["failed"] == 1
    assert "no_bars" not in stats


def test_far_from_money_empty_is_still_no_bars(_isolate):
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")

    class _EmptyFeedSession:
        async def fetch_history_fast(self, url, timeout_ms):
            _SESSION_LOG.warning("History feed returned no rows for '%s'", url)
            return None

    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0,
                              session=_EmptyFeedSession(), near_money={contract: False}))
    assert stats["no_bars"] == 1


def test_plan_marks_strikes_within_3pct_of_a_window_close_as_near_money():
    entries = bc.plan_for_symbol(
        "SPY", date(2024, 1, 1), date(2024, 1, 31), 20, 60, 0.10, ["C"],
        close_cache={}, close_provider=_provider(450.0), today=date(2026, 1, 1))
    near = {e.strike: e.near_money for e in entries}
    assert near[450.0] is True                    # exactly at the close
    far_strikes = [s for s in near if abs(s - 450.0) / 450.0 > 0.03]
    assert far_strikes and all(near[s] is False for s in far_strikes)


def test_consecutive_no_bars_stop(_isolate):
    _, manifest_path, _ = _isolate
    contracts = [("SPY", date(2024, 6, 21), 450.0 + i, "C") for i in range(10)]

    class _EmptyFeedSession:
        async def fetch_history_fast(self, url, timeout_ms):
            _SESSION_LOG.warning("History feed returned no rows for '%s'", url)
            return None

    stats = _run(bc.run_fetch(contracts, {}, manifest_path, sleep_s=0, no_bars_stop=3,
                              session=_EmptyFeedSession()))
    assert stats["no_bars"] == 3
    assert stats["stopped_consecutive_no_bars"] == 1


# --- item 1 (third review): manifest schema migration --------------------------

_LEGACY_171419C_HEADER = ("symbol", "expiration", "strike", "right", "outcome", "rows",
                          "first_date", "last_date", "attempts", "timestamp")


def _write_legacy_manifest(path, rows):
    """A manifest in the EXACT 171419c-era 10-column format (no
    first_attempt_at, no reason) — what the running pilot still writes."""
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=_LEGACY_171419C_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({f: r.get(f, "") for f in _LEGACY_171419C_HEADER})


def test_load_manifest_warns_but_correctly_parses_a_legacy_171419c_file(_isolate, caplog):
    _, manifest_path, _ = _isolate
    _write_legacy_manifest(manifest_path, [
        {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00", "right": "C",
         "outcome": "failed", "rows": "0", "first_date": "", "last_date": "",
         "attempts": "2", "timestamp": "2026-09-01T00:00:00+00:00"}])
    with caplog.at_level(logging.WARNING):
        loaded = bc.load_manifest(manifest_path)
    row = loaded[("SPY", "2024-06-21", "450.00", "C")]
    assert row["outcome"] == "failed" and row["attempts"] == "2"
    assert row["first_attempt_at"] == ""   # the bug: absent under the old schema
    assert any("schema mismatch" in r.message for r in caplog.records)
    # load_manifest only reads — the file on disk must be untouched.
    assert bc._read_manifest_header(manifest_path) == _LEGACY_171419C_HEADER


def test_migrate_manifest_schema_rewrites_header_and_backfills_first_attempt_at(_isolate):
    _, manifest_path, _ = _isolate
    _write_legacy_manifest(manifest_path, [
        {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00", "right": "C",
         "outcome": "failed", "rows": "0", "first_date": "", "last_date": "",
         "attempts": "2", "timestamp": "2026-09-20T00:00:00+00:00"}])
    migrated = bc.migrate_manifest_schema(manifest_path)
    assert migrated is True
    assert bc._read_manifest_header(manifest_path) == bc.MANIFEST_FIELDS
    loaded = bc.load_manifest(manifest_path)
    row = loaded[("SPY", "2024-06-21", "450.00", "C")]
    assert row["attempts"] == "2"
    assert row["first_attempt_at"] == "2026-09-20T00:00:00+00:00"  # backfilled from timestamp
    assert row["reason"] == ""


def test_migrate_manifest_schema_is_a_noop_on_the_current_schema(_isolate):
    _, manifest_path, _ = _isolate
    bc.append_manifest_row(manifest_path, {"symbol": "SPY", "expiration": "2024-06-21",
                                           "strike": "450.00", "right": "C", "outcome": "fetched",
                                           "rows": "1", "first_date": "", "last_date": "",
                                           "attempts": "0", "first_attempt_at": "", "reason": "",
                                           "timestamp": "t"})
    before = manifest_path.read_text()
    assert bc.migrate_manifest_schema(manifest_path) is False
    assert manifest_path.read_text() == before


def test_append_refuses_to_write_onto_a_mismatched_header(_isolate):
    _, manifest_path, _ = _isolate
    _write_legacy_manifest(manifest_path, [])
    with pytest.raises(bc.ManifestSchemaMismatch):
        bc.append_manifest_row(manifest_path, {"symbol": "SPY", "expiration": "2024-06-21",
                                                "strike": "450.00", "right": "C",
                                                "outcome": "fetched"})


def test_run_fetch_migrates_a_legacy_manifest_before_fetching_and_unavailable_now_works(_isolate):
    """End-to-end: the exact bug the third review found. Against a
    171419c-format manifest whose row already has attempts=2 and a
    timestamp >24h old, a fresh run_fetch (a) migrates the file, (b) reloads
    the caller's `manifest` dict in place, and (c) a third failed attempt
    NOW correctly promotes to `unavailable` — before this fix it never
    would have, because first_attempt_at kept resetting to "now"."""
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    stale = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
    _write_legacy_manifest(manifest_path, [
        {"symbol": "SPY", "expiration": "2024-06-21", "strike": "450.00", "right": "C",
         "outcome": "failed", "rows": "0", "first_date": "", "last_date": "",
         "attempts": "2", "timestamp": stale}])

    manifest = bc.load_manifest(manifest_path)  # main()'s pre-lock read, BEFORE migration
    stats = _run(bc.run_fetch([contract], manifest, manifest_path, sleep_s=0,
                              session=_ScriptedSession([None])))

    assert stats["unavailable"] == 1
    assert bc._read_manifest_header(manifest_path) == bc.MANIFEST_FIELDS
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "unavailable" and row["attempts"] == "3"
    # the caller's dict (passed by reference) was updated in place too
    assert manifest[bc._key(*contract)]["outcome"] == "unavailable"


# --- item 2 (third review): the non-existent-expiry wall -----------------------

def test_expiry_wall_skips_the_rest_without_fetching(_isolate):
    _, manifest_path, _ = _isolate
    expiry = date(2024, 6, 21)
    contracts = [("SPY", expiry, 440.0 + i, "C") for i in range(8)]
    near_money = {c: True for c in contracts}

    class _EmptyFeedSession:
        def __init__(self):
            self.calls = 0

        async def fetch_history_fast(self, url, timeout_ms):
            self.calls += 1
            _SESSION_LOG.warning("History feed returned no rows for '%s'", url)
            return None

    session = _EmptyFeedSession()
    stats = _run(bc.run_fetch(contracts, {}, manifest_path, sleep_s=0, fail_stop=100,
                              session=session, near_money=near_money,
                              expiry_empty_streak_stop=4))
    assert session.calls == 4          # only the streak-establishing 4 were fetched
    assert stats["skipped_expiry_wall"] == 4
    assert stats["failed"] == 8        # 4 fetched-empty + 4 skipped, all `failed`

    rows = bc.load_manifest(manifest_path)
    reasons = [rows[bc._key(*c)]["reason"] for c in contracts[4:]]
    assert all(r == "expiry_empty" for r in reasons)
    assert all(rows[bc._key(*c)]["attempts"] == "1" for c in contracts)  # all count as attempts


def test_expiry_wall_skips_do_not_count_toward_fail_stop(_isolate):
    _, manifest_path, _ = _isolate
    expiry = date(2024, 6, 21)
    contracts = [("SPY", expiry, 440.0 + i, "C") for i in range(20)]
    near_money = {c: True for c in contracts}

    # fail_stop=10 is bigger than the streak threshold (4) but far smaller
    # than the 20 near-money contracts: if the 16 SKIPPED ones counted
    # toward it, the run would stop long before reaching the (synthetic)
    # second expiry below. The 4 streak-ESTABLISHING contracts alone must
    # not exceed fail_stop either, so it must reach the second expiry.
    contracts_two_expiries = contracts + [("SPY", date(2024, 7, 19), 440.0, "C")]

    class _MixedSession:
        def __init__(self):
            self.calls = []

        async def fetch_history_fast(self, url, timeout_ms):
            self.calls.append(url)
            # Only the 4 streak-establishing contracts of the walled expiry
            # are ever actually fetched (the other 16 are skipped locally);
            # anything after that is the second expiry's own contract.
            if len(self.calls) <= 4:
                _SESSION_LOG.warning("History feed returned no rows for '%s'", url)
                return None
            return _history_csv([date(2024, 3, 1) + timedelta(days=i) for i in range(10)])

    session = _MixedSession()
    stats = _run(bc.run_fetch(contracts_two_expiries, {}, manifest_path, sleep_s=0,
                              fail_stop=10, session=session, near_money=near_money,
                              expiry_empty_streak_stop=4))
    assert "stopped_consecutive_failures" not in stats
    assert stats.get("fetched") == 1   # the second expiry's contract was reached and fetched


def test_http_error_among_near_money_contracts_breaks_the_streak_and_stops(_isolate):
    """A real outage (blocking HTTP) among the first N near-money contracts
    of an expiry must still stop the run immediately — the wall logic must
    never swallow it."""
    _, manifest_path, _ = _isolate
    expiry = date(2024, 6, 21)
    contracts = [("SPY", expiry, 440.0 + i, "C") for i in range(6)]
    near_money = {c: True for c in contracts}

    class _Session:
        def __init__(self):
            self.calls = 0

        async def fetch_history_fast(self, url, timeout_ms):
            self.calls += 1
            if self.calls == 2:
                _SESSION_LOG.warning("History feed returned HTTP %d for '%s'", 429, url)
            else:
                _SESSION_LOG.warning("History feed returned no rows for '%s'", url)
            return None

    session = _Session()
    stats = _run(bc.run_fetch(contracts, {}, manifest_path, sleep_s=0, session=session,
                              near_money=near_money, expiry_empty_streak_stop=4))
    assert stats["stopped_http_429"] == 1
    assert session.calls == 2   # stopped immediately, never reached a streak of 4


def test_far_from_money_contracts_do_not_participate_in_the_wall(_isolate):
    _, manifest_path, _ = _isolate
    expiry = date(2024, 6, 21)
    contracts = [("SPY", expiry, 440.0 + i, "C") for i in range(8)]
    near_money = {c: False for c in contracts}  # none near-the-money

    class _EmptyFeedSession:
        def __init__(self):
            self.calls = 0

        async def fetch_history_fast(self, url, timeout_ms):
            self.calls += 1
            _SESSION_LOG.warning("History feed returned no rows for '%s'", url)
            return None

    session = _EmptyFeedSession()
    stats = _run(bc.run_fetch(contracts, {}, manifest_path, sleep_s=0, session=session,
                              near_money=near_money, expiry_empty_streak_stop=4))
    assert session.calls == 8            # every contract fetched, no wall
    assert stats["no_bars"] == 8
    assert "skipped_expiry_wall" not in stats


# --- item 4: the sniffed message strings really are session.py's own ----------

def test_sniffed_messages_exist_verbatim_in_lib_barchart_session_source():
    import inspect
    from lib.barchart import session as barchart_session
    src = inspect.getsource(barchart_session)
    for msg in bc._HistorySniffHandler._HTTP_MSGS + bc._HistorySniffHandler._EMPTY_MSGS:
        assert msg in src, f"{msg!r} not found verbatim in lib/barchart/session.py"


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


def test_two_failed_runs_do_not_promote_to_unavailable(_isolate):
    """re-review item 3: two runs during one short outage must NOT
    permanently blacklist a contract — unavailable now needs >=3 attempts
    AND >=24h between the first and the last."""
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")

    manifest = {}
    stats1 = _run(bc.run_fetch([contract], manifest, manifest_path, sleep_s=0,
                               session=_ScriptedSession([None])))
    assert stats1["failed"] == 1

    manifest2 = bc.load_manifest(manifest_path)
    stats2 = _run(bc.run_fetch([contract], manifest2, manifest_path, sleep_s=0,
                               session=_ScriptedSession([None])))
    assert stats2["failed"] == 1
    assert "unavailable" not in stats2
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "failed" and row["attempts"] == "2"


def test_third_attempt_within_24h_still_does_not_promote(_isolate):
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    now = bc._now_iso()
    manifest = {bc._key(*contract): {"outcome": "failed", "attempts": "2",
                                     "first_attempt_at": now}}
    stats = _run(bc.run_fetch([contract], manifest, manifest_path, sleep_s=0,
                              session=_ScriptedSession([None])))
    assert stats["failed"] == 1
    assert "unavailable" not in stats


def test_third_attempt_after_24h_promotes_to_unavailable(_isolate):
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    stale = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
    manifest = {bc._key(*contract): {"outcome": "failed", "attempts": "2",
                                     "first_attempt_at": stale}}
    stats = _run(bc.run_fetch([contract], manifest, manifest_path, sleep_s=0,
                              session=_ScriptedSession([None])))
    assert stats["unavailable"] == 1
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["outcome"] == "unavailable" and row["attempts"] == "3"


def test_blocking_stop_does_not_increment_attempts(_isolate):
    """re-review item 3: a blocking HTTP status is the session's fault, not
    this contract's — its attempts count must not move."""
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    manifest = {bc._key(*contract): {"outcome": "failed", "attempts": "1",
                                     "first_attempt_at": bc._now_iso()}}

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            _SESSION_LOG.warning("History feed returned HTTP %d for '%s'", 429, url)
            return None

    _run(bc.run_fetch([contract], manifest, manifest_path, sleep_s=0, session=_Session()))
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["attempts"] == "1"


def test_write_oserror_stops_run_and_does_not_count_as_an_attempt(_isolate, monkeypatch):
    """re-review item 3: an OSError from the cache write is an environment
    problem, not a per-contract one — stop immediately, don't burn attempts."""
    _, manifest_path, _ = _isolate
    contract = ("SPY", date(2024, 6, 21), 450.0, "C")
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]

    def _boom(path, text):
        raise OSError("disk full")
    monkeypatch.setattr(bc, "_atomic_write_new", _boom)

    session = _ScriptedSession([_history_csv(days)])
    stats = _run(bc.run_fetch([contract], {}, manifest_path, sleep_s=0, session=session))
    assert stats["stopped_write_error"] == 1
    row = bc.load_manifest(manifest_path)[bc._key(*contract)]
    assert row["attempts"] == "0"
    assert not bc.contract_path(*contract).exists()


def test_retry_unavailable_flag_reincludes_it_as_pending(_isolate):
    entry = _entry(expiration=date(2023, 1, 1))
    manifest = {bc._key(*bc.contract_of(entry)): {"outcome": "unavailable", "attempts": "3"}}
    assert bc.classify(entry, manifest, today=date(2024, 1, 1)) == "covered"
    assert bc.classify(entry, manifest, today=date(2024, 1, 1),
                       retry_unavailable=True) == "pending"


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
