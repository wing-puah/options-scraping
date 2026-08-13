"""Unit tests for `scripts/collector/fetch_counterpart_history.py`.

Covers the pure selection logic — which legs are read out of the book, what
their mirrors are, and when the coverage gate re-fetches — plus the two guards
that would otherwise fail SILENTLY:

  - a contract that never traded must NOT be written (an empty file satisfies
    the coverage gate forever while pricing nothing)
  - mirrors must land on the EXACT `{TICKER}_{YYYYMMDD}_{STRIKE}{C|P}.csv`
    path the backtest already reads, since that is the entire integration

Everything is synthetic and written to tmp_path; no network, no real cache.
"""
import asyncio
from datetime import date, timedelta

import pytest

from lib.barchart.options import cache_path
from scripts.collector import fetch_counterpart_history as fch

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
          "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")

SIGNAL = "2024-03-04"
EXPIRY = date(2024, 6, 21)


def _history_csv(days) -> str:
    rows = [HEADER]
    for d in days:
        rows.append(f"{d.isoformat()},1.0,1.1,0.9,1.0,0,0%,10,5,,,,,,,,100,0.95,1.05")
    return "\n".join(rows) + "\n"


def _book_csv(path, rows) -> None:
    """rows = [(signal_date, ticker, legs, daily_price_csv, proxy_method)]"""
    lines = ["signal_date,ticker,legs,daily_price_csv,proxy_method"]
    for d, tk, legs, marks, method in rows:
        lines.append(f'{d},{tk},"{legs}",{marks},{method}')
    path.write_text("\n".join(lines) + "\n")


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    cache = tmp_path / "opt_cache"
    cache.mkdir()
    monkeypatch.setattr(fch, "HISTORY_CACHE", cache)
    results = tmp_path / "results.csv"
    proxy = tmp_path / "proxy.csv"
    monkeypatch.setattr(fch, "BOOK_CSVS", (results, proxy))
    yield cache, results, proxy


# --- book inspection ---------------------------------------------------------

def test_entry_legs_parsed_from_both_book_exports(_isolate):
    _, results, proxy = _isolate
    _book_csv(results, [(SIGNAL, "AAA",
                         "AAA:2024-06-21:100:P +1\nAAA:2024-06-21:90:P -1", "1.0,1.1", "")])
    _book_csv(proxy, [("2024-04-01", "BBB", "BBB:2024-06-21:50:C +1", "2.0",
                       "strike_expiry_tweak")])
    legs = fch.book_entry_legs()
    assert set(legs) == {("AAA", EXPIRY, 100.0, "P"),
                         ("AAA", EXPIRY, 90.0, "P"),
                         ("BBB", EXPIRY, 50.0, "C")}


def test_unpriced_and_bs_rows_are_excluded(_isolate):
    """The same two filters `load_book(include_bs=False)` applies — scraping a
    mirror for a row no study reads is a wasted request."""
    _, results, proxy = _isolate
    _book_csv(results, [(SIGNAL, "AAA", "AAA:2024-06-21:100:P +1", "", "")])
    _book_csv(proxy, [(SIGNAL, "BBB", "BBB:2024-06-21:50:C +1", "2.0", "bs_options_hist")])
    assert fch.book_entry_legs() == {}
    assert set(fch.book_entry_legs(include_bs=True)) == {("BBB", EXPIRY, 50.0, "C")}


def test_date_window_selects_legs(_isolate):
    _, results, proxy = _isolate
    _book_csv(results, [(SIGNAL, "AAA", "AAA:2024-06-21:100:P +1", "1.0", ""),
                        ("2024-05-01", "BBB", "BBB:2024-06-21:50:C +1", "1.0", "")])
    _book_csv(proxy, [])
    assert set(fch.book_entry_legs("2024-04-01", "2024-06-01")) == {
        ("BBB", EXPIRY, 50.0, "C")}


def test_leg_spans_merge_across_rows(_isolate):
    """The same contract entered on two dates needs the UNION of their windows."""
    _, results, proxy = _isolate
    _book_csv(results, [("2024-03-04", "AAA", "AAA:2024-06-21:100:P +1", "1.0", ""),
                        ("2024-05-06", "AAA", "AAA:2024-06-21:100:P +1", "1.0", "")])
    _book_csv(proxy, [])
    assert fch.book_entry_legs()[("AAA", EXPIRY, 100.0, "P")] == ("2024-03-04", "2024-05-06")


# --- mirroring ---------------------------------------------------------------

def test_mirror_flips_type_and_keeps_strike_and_expiry():
    legs = {("AAA", EXPIRY, 100.0, "P"): ("2024-03-04", "2024-03-04"),
            ("AAA", EXPIRY, 50.0, "C"): ("2024-03-04", "2024-03-04")}
    assert set(fch.mirrors_of(legs)) == {("AAA", EXPIRY, 100.0, "C"),
                                         ("AAA", EXPIRY, 50.0, "P")}


def test_mirror_spans_merge_when_two_legs_share_a_mirror():
    legs = {("AAA", EXPIRY, 100.0, "P"): ("2024-03-04", "2024-03-04"),
            ("AAA", EXPIRY, 100.0, "C"): ("2024-01-02", "2024-05-06")}
    mirrors = fch.mirrors_of(legs)
    assert mirrors[("AAA", EXPIRY, 100.0, "C")] == ("2024-03-04", "2024-03-04")
    assert mirrors[("AAA", EXPIRY, 100.0, "P")] == ("2024-01-02", "2024-05-06")


def test_mirror_path_matches_the_backtest_cache_convention(_isolate):
    """The whole integration: nothing downstream changes because these files
    land exactly where `simulate.py` and `harness.py` already look."""
    cache, _, _ = _isolate
    key = ("AAA", EXPIRY, 100.0, "C")
    assert fch.contract_path(key) == cache_path(cache, "AAA", EXPIRY, 100.0, "Call")
    assert fch.contract_path(key).name == "AAA_20240621_100.00C.csv"


# --- the coverage gate -------------------------------------------------------

def test_absent_cache_is_fetched(_isolate):
    key = ("AAA", EXPIRY, 100.0, "C")
    do, why = fch.needs_fetch(key, (SIGNAL, SIGNAL), force=False, skip_existing=True)
    assert do and why == "no cache"


def test_covering_cache_is_skipped(_isolate):
    cache, _, _ = _isolate
    key = ("AAA", EXPIRY, 100.0, "C")
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(60)]
    fch.contract_path(key).write_text(_history_csv(days))
    do, why = fch.needs_fetch(key, (SIGNAL, SIGNAL), force=False, skip_existing=True)
    assert not do and why.startswith("skipped")


def test_cache_ending_before_the_window_is_refetched(_isolate):
    """The silent-failure case: a short file reads downstream as 'unpriceable'
    rather than 'never fetched', which is a wrong coverage denominator."""
    key = ("AAA", EXPIRY, 100.0, "C")
    fch.contract_path(key).write_text(
        _history_csv([date(2024, 1, 2) + timedelta(days=i) for i in range(5)]))
    do, why = fch.needs_fetch(key, (SIGNAL, SIGNAL), force=False, skip_existing=True)
    assert do and why.startswith("re-fetch")


def test_single_bar_cache_counts_as_absent(_isolate):
    key = ("AAA", EXPIRY, 100.0, "C")
    fch.contract_path(key).write_text(_history_csv([date(2024, 3, 5)]))
    do, why = fch.needs_fetch(key, (SIGNAL, SIGNAL), force=False, skip_existing=True)
    assert do and why == "no cache"


def test_force_and_no_skip_existing_override_a_good_cache(_isolate):
    key = ("AAA", EXPIRY, 100.0, "C")
    days = [date(2024, 3, 1) + timedelta(days=i) for i in range(60)]
    fch.contract_path(key).write_text(_history_csv(days))
    assert fch.needs_fetch(key, (SIGNAL, SIGNAL), force=True, skip_existing=True)[0]
    assert fch.needs_fetch(key, (SIGNAL, SIGNAL), force=False, skip_existing=False)[0]


def test_required_window_caps_at_the_path_window_not_expiry():
    """A LEAP must not be judged incomplete for bars no simulation would read."""
    leap = date(2026, 1, 16)
    lo, hi = fch.required_window(("AAA", leap, 100.0, "C"), (SIGNAL, SIGNAL))
    assert lo == date(2024, 3, 4)
    assert hi < leap
    near = date(2024, 3, 15)
    _, hi_near = fch.required_window(("AAA", near, 100.0, "C"), (SIGNAL, SIGNAL))
    assert hi_near == near + timedelta(days=fch.COVERAGE_PAD_DAYS)


# --- the never-traded guard --------------------------------------------------

def _run(coro):
    """Drive a coroutine to completion — the repo's convention (test_scraper.py);
    pytest-asyncio is not configured here."""
    return asyncio.new_event_loop().run_until_complete(coro)



def test_contract_with_no_bars_is_not_written(_isolate):
    """An empty file would satisfy the coverage gate forever while pricing
    nothing, so it must be counted and skipped, not cached."""
    key = ("AAA", EXPIRY, 100.0, "C")

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return HEADER + "\n"

    stats = _run(fch._scrape([key], headless=True, sleep_s=0, session=_Session()))
    assert stats.get("no_bars") == 1
    assert not fch.contract_path(key).exists()


def test_fetched_contract_is_written_to_the_shared_cache(_isolate):
    key = ("AAA", EXPIRY, 100.0, "C")
    days = [date(2024, 3, 5) + timedelta(days=i) for i in range(10)]

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            assert "AAA" in url and "100.00C" in url
            return _history_csv(days)

    stats = _run(fch._scrape([key], headless=True, sleep_s=0, session=_Session()))
    assert stats.get("fetched") == 1
    assert fch.contract_path(key).exists()
    assert fch.cache_span(key) == (days[0], days[-1])


def test_failed_fetch_is_counted_and_writes_nothing(_isolate):
    key = ("AAA", EXPIRY, 100.0, "C")

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return None

    stats = _run(fch._scrape([key], headless=True, sleep_s=0, session=_Session()))
    assert stats.get("failed") == 1
    assert not fch.contract_path(key).exists()


# --- the headline coverage number --------------------------------------------

def test_straddleable_counts_groups_with_a_same_strike_pair():
    legs = {
        ("AAA", EXPIRY, 100.0, "P"): (SIGNAL, SIGNAL),
        ("AAA", EXPIRY, 100.0, "C"): (SIGNAL, SIGNAL),   # pair -> counts
        ("BBB", EXPIRY, 50.0, "P"): (SIGNAL, SIGNAL),
        ("BBB", EXPIRY, 60.0, "C"): (SIGNAL, SIGNAL),    # different strikes -> no
    }
    assert fch.straddleable(legs) == (1, 2)


def test_mirroring_makes_every_group_straddleable():
    """The number this collector exists to move."""
    legs = {("AAA", EXPIRY, 100.0, "P"): (SIGNAL, SIGNAL),
            ("BBB", EXPIRY, 50.0, "C"): (SIGNAL, SIGNAL)}
    assert fch.straddleable(legs) == (0, 2)
    combined = {**legs, **fch.mirrors_of(legs)}
    assert fch.straddleable(combined) == (2, 2)
