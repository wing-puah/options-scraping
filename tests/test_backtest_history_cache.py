"""The option-history cache survives a failed refetch.

Until 2026-09-19 a cache file whose earliest row did not reach back far enough
was UNLINKED before the refetch that was meant to replace it. When that refetch
returned nothing the file was simply gone: the scraper was re-issuing the page's
default three-month `startDate`, which is empty for an expired contract, and 178
files were destroyed that way between the 2026-09-05 snapshot and 2026-09-08.
The range is fixed in `lib/barchart/session.py`, so the trigger is gone, but
`backtests/option_history_cache/` has no git history to recover from — a shallow
file is still the only copy of that contract's scraped history that exists.

These tests pin the two halves of the fix: nothing is unlinked on the way in,
and a fetched file is staged and `os.replace`d so an existing cache is only ever
superseded by a complete fetch.
"""
import asyncio
from datetime import date

import pytest

from backtest.shared import history
from lib.barchart import options as bo

SYMBOL, EXP, STRIKE, OPT = "HYG", date(2025, 4, 17), 72.0, "Put"
KEY = (SYMBOL, EXP, STRIKE, OPT)

_HEADER = ('Time,Open,High,Low,Latest,Change,%Change,Volume,"Open Int",IV,Delta,Gamma,'
           "Theta,Vega,Rho,Theo,Price~,Bid,Ask\n")


def _shallow_csv() -> str:
    """One row, dated well AFTER the signal date the test asks for — the exact
    shape that trips the staleness check."""
    return _HEADER + (
        "2025-04-10,1.20,1.30,1.10,1.25,0.05,4.00%,100,500,"
        "0.30,-0.40,0.01,-0.02,0.05,0.01,1.24,1.25,0.00,2.68\n"
    )


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    d = tmp_path / "option_history_cache"
    d.mkdir()
    monkeypatch.setattr(history, "HISTORY_CACHE", d)
    return d


@pytest.fixture
def stale_cache(cache_dir):
    p = bo.cache_path(cache_dir, SYMBOL, EXP, STRIKE, OPT)
    p.write_text(_shallow_csv(), encoding="utf-8")
    return p


_CONTRACT = [{"key": KEY, "symbol": SYMBOL, "opt_type": OPT,
              "strike": STRIKE, "expiration": EXP}]
# Three weeks before the only cached row, so the cache is stale by well over
# the 5-day `_STALENESS_DAYS` allowance.
_NEEDED = {KEY: date(2025, 3, 20)}


def _run(**kw):
    return asyncio.run(history.fetch_option_histories(
        _CONTRACT, headless=True, needed_dates=_NEEDED, **kw))


def test_stale_cache_survives_when_no_credentials_are_configured(stale_cache, monkeypatch):
    """The refetch never even starts without Barchart credentials. The file must
    still be on disk: the run has no replacement for it."""
    monkeypatch.delenv("BARCHART_EMAIL", raising=False)
    monkeypatch.delenv("BARCHART_PASSWORD", raising=False)

    series_map, _details = _run()

    assert stale_cache.exists()
    assert stale_cache.read_text(encoding="utf-8") == _shallow_csv()
    # The shallow series is still dropped from THIS run, so a play that needed
    # the earlier dates prices as no-data exactly as it did before the fix.
    assert KEY not in series_map


def test_stale_cache_survives_a_refetch_that_returns_nothing(stale_cache, monkeypatch):
    """The 178-file loss, reproduced: the fetch succeeds as a call and returns no
    rows. Nothing is written, and the old file must be untouched."""
    monkeypatch.setenv("BARCHART_EMAIL", "x@example.com")
    monkeypatch.setenv("BARCHART_PASSWORD", "pw")
    monkeypatch.setattr(history, "BarchartSession", _fake_session(lambda: ""))

    series_map, _details = _run()

    assert stale_cache.exists()
    assert stale_cache.read_text(encoding="utf-8") == _shallow_csv()
    assert series_map[KEY] == []


def test_stale_cache_survives_a_refetch_that_raises(stale_cache, monkeypatch):
    monkeypatch.setenv("BARCHART_EMAIL", "x@example.com")
    monkeypatch.setenv("BARCHART_PASSWORD", "pw")

    def _boom():
        raise RuntimeError("barchart timed out")

    monkeypatch.setattr(history, "BarchartSession", _fake_session(_boom))

    _run()

    assert stale_cache.exists()
    assert stale_cache.read_text(encoding="utf-8") == _shallow_csv()


def test_a_complete_refetch_replaces_the_cache_and_leaves_no_temp_file(
        stale_cache, cache_dir, monkeypatch):
    deep = _HEADER + (
        "2025-03-19,1.00,1.10,0.95,1.05,0.05,5.00%,100,500,"
        "0.30,-0.40,0.01,-0.02,0.05,0.01,1.04,1.05,1.00,1.10\n"
    )
    monkeypatch.setenv("BARCHART_EMAIL", "x@example.com")
    monkeypatch.setenv("BARCHART_PASSWORD", "pw")
    monkeypatch.setattr(history, "BarchartSession", _fake_session(lambda: deep))

    series_map, _details = _run()

    assert stale_cache.read_text(encoding="utf-8") == deep
    assert series_map[KEY]  # the deeper history is what this run prices on
    # Staged under `.csv.tmp` and os.replace'd — the staging file is consumed by
    # the replace, never left behind for the next run to read as a cache.
    assert list(cache_dir.iterdir()) == [stale_cache]


def _fake_session(csv_fn):
    """Stand-in for `BarchartSession` — an async context manager whose
    `fetch_history_csv` calls ``csv_fn``. Keeps Playwright out of the test."""
    class _S:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def fetch_history_csv(self, url, timeout_ms):
            return csv_fn()

    return _S
