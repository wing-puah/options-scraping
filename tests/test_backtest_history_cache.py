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
import json
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


# ── the underlying-mismatch guard (2026-09-23) ─────────────────────────────────

def _one_row(price_tilde: str) -> str:
    return _HEADER + (
        "2025-03-19,1.00,1.10,0.95,1.05,0.05,5.00%,100,500,"
        f"0.30,-0.40,0.01,-0.02,0.05,0.01,1.04,{price_tilde},1.00,1.10\n"
    )


def _sibling(cache_dir, strike, price_tilde):
    p = bo.cache_path(cache_dir, SYMBOL, EXP, strike, OPT)
    p.write_text(_one_row(price_tilde), encoding="utf-8")
    return p


def _creds(monkeypatch, csv_text):
    monkeypatch.setenv("BARCHART_EMAIL", "x@example.com")
    monkeypatch.setenv("BARCHART_PASSWORD", "pw")
    monkeypatch.setattr(history, "BarchartSession", _fake_session(lambda: csv_text))


def test_a_refetch_whose_price_tilde_is_not_this_ticker_is_rejected(
        stale_cache, cache_dir, monkeypatch):
    """META_20270115_630.00P held another contract's data: Price~ ~$155 against
    ~$640 on every sibling of the same expiry. A fetch like that must not be
    cached, and the shallow file already on disk must survive untouched."""
    sib = _sibling(cache_dir, 70.0, "78.00")
    _creds(monkeypatch, _one_row("19.50"))

    series_map, details = _run()

    assert series_map[KEY] == []
    assert KEY not in details
    assert stale_cache.read_text(encoding="utf-8") == _shallow_csv()
    assert sorted(cache_dir.iterdir()) == sorted([stale_cache, sib])


def test_a_split_ticker_fetch_that_agrees_with_its_siblings_is_kept(
        stale_cache, cache_dir, monkeypatch):
    """SPLIT CASE. The underlying OHLC cache is split-ADJUSTED; option `Price~` is
    as-traded. A pre-split NVDA file reads ~10x the adjusted close, and so do all
    its siblings. The guard compares against SIBLINGS only, so this good file is
    cached. A guard keyed on the OHLC cache would reject every one of them."""
    _sibling(cache_dir, 70.0, "780.00")         # as-traded, pre-10:1-split scale
    _creds(monkeypatch, _one_row("781.50"))     # the OHLC cache would say ~78

    series_map, _details = _run()

    assert series_map[KEY]
    assert "781.50" in stale_cache.read_text(encoding="utf-8")


def test_mismatch_guard_passes_agreement_and_missing_evidence():
    rows = {date(2025, 3, 19): {"Price~": "78.1"}, date(2025, 3, 20): {"Price~": "77.9"}}
    sibs = {date(2025, 3, 19): 78.0, date(2025, 3, 20): 78.0}
    assert history.underlying_mismatch(rows, sibs) is None
    # No sibling / no overlapping date: no evidence, no block.
    assert history.underlying_mismatch(rows, {}) is None
    assert history.underlying_mismatch(rows, {date(2024, 1, 2): 10.0}) is None
    assert history.underlying_mismatch(rows, {date(2025, 3, 19): 155.0 * 4})


def test_the_guard_never_reads_the_split_adjusted_ohlc_cache():
    """Regression pin for the 2026-09-23 correction: the OHLC cache disagrees with
    as-traded `Price~` by exact split multiples on 2,112 files."""
    import inspect
    from backtest import simulate
    for mod in (history, simulate):
        assert "underlying_ohlc" not in inspect.getsource(mod).replace(
            "`backtests/underlying_ohlc_cache/`", "")


# ── the negative cache: contracts Barchart does not list (2026-09-27) ─────────
#
# A contract that never returned rows was never cached, so every run re-probed
# it at ~15s a time. `shared/unlisted.py` remembers it — but ONLY on positive
# evidence (the page loaded 2xx, logged in, promptly, and fired no feed) and
# only once the browser is shown to be online around it. Network, DNS, SSL,
# HTTP and login failures must never be recorded: the 2026-09-25 outage alone
# produced hundreds of net::ERR_INTERNET_DISCONNECTED failures.

from datetime import timedelta  # noqa: E402

from playwright.async_api import Error as PlaywrightError  # noqa: E402
from playwright.async_api import TimeoutError as PlaywrightTimeoutError  # noqa: E402

from backtest.shared import unlisted  # noqa: E402
from lib.barchart import session as bs  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_tracker():
    unlisted.TRACKER.reset()
    yield
    unlisted.TRACKER.reset()


def _contract(strike, exp=date(2028, 9, 15), sym="DRAM", opt="Call"):
    return {"key": (sym, exp, strike, opt), "symbol": sym, "opt_type": opt,
            "strike": strike, "expiration": exp}


class _Clock:
    """`unlisted._now` stand-in: each fetch advances it by ``step`` seconds."""
    def __init__(self, step=150.0):
        self.t, self.step = 1_000_000.0, step

    def __call__(self):
        return self.t


def _scripted_session(script, clock, calls=None):
    """A `BarchartSession` whose fetch_history_csv plays ``script``:
    {strike: outcome}. OK returns one row; everything else returns None."""
    class _S:
        def __init__(self, *a, **k):
            self.last_history_outcome = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def fetch_history_csv(self, url, timeout_ms):
            clock.t += clock.step
            strike = float(url.split("%7C")[-1].split("/")[0][:-1])
            if calls is not None:
                calls.append(strike)
            outcome = script[strike]
            self.last_history_logged_in = None
            if isinstance(outcome, tuple):          # (outcome, logged_in)
                outcome, self.last_history_logged_in = outcome
            self.last_history_outcome = outcome
            return _one_row("1.00") if outcome == bs.HISTORY_OK else None

    return _S


def _fetch(cache_dir, monkeypatch, contracts, script, clock=None, calls=None, **kw):
    clock = clock or _Clock()
    monkeypatch.setattr(unlisted, "_now", clock)
    monkeypatch.setenv("BARCHART_EMAIL", "x@example.com")
    monkeypatch.setenv("BARCHART_PASSWORD", "pw")
    monkeypatch.delenv(unlisted.RETRY_ENV, raising=False)
    monkeypatch.setattr(history, "BarchartSession", _scripted_session(script, clock, calls))
    return asyncio.run(history.fetch_option_histories(contracts, headless=True, **kw))


def _entries(cache_dir):
    return unlisted.load(cache_dir / unlisted.FILENAME)


def test_a_clean_no_feed_between_live_fetches_is_recorded(cache_dir, monkeypatch):
    cs = [_contract(50.0), _contract(59.0), _contract(60.0)]
    script = {50.0: bs.HISTORY_OK, 59.0: bs.HISTORY_NO_FEED, 60.0: bs.HISTORY_OK}

    series, details = _fetch(cache_dir, monkeypatch, cs, script)

    e = _entries(cache_dir)
    assert list(e) == ["DRAM_20280915_59.00C"]
    rec = e["DRAM_20280915_59.00C"]
    assert (rec["ticker"], rec["right"], rec["strike"], rec["expiry"]) == (
        "DRAM", "C", 59.0, "2028-09-15")
    assert rec["n_checks"] == 1 and rec["reason"] == bs.HISTORY_NO_FEED
    assert rec["first_seen"] == rec["last_checked"]
    # This run still prices it as a failed fetch.
    assert series[cs[1]["key"]] == [] and cs[1]["key"] not in details
    assert not (cache_dir / (unlisted.FILENAME + ".tmp")).exists()


@pytest.mark.parametrize("failure", [
    bs.HISTORY_NAV_ERROR, bs.HISTORY_HTTP_ERROR, bs.HISTORY_SESSION,
    bs.HISTORY_ERROR, bs.HISTORY_NO_ROWS, None])
def test_a_failed_fetch_is_never_recorded(cache_dir, monkeypatch, failure):
    cs = [_contract(50.0), _contract(59.0), _contract(60.0)]
    script = {50.0: bs.HISTORY_OK, 59.0: failure, 60.0: bs.HISTORY_OK}

    _fetch(cache_dir, monkeypatch, cs, script)

    assert _entries(cache_dir) == {}


@pytest.mark.parametrize("failure", [
    bs.HISTORY_NAV_ERROR, bs.HISTORY_HTTP_ERROR, bs.HISTORY_SESSION, bs.HISTORY_ERROR])
def test_a_no_feed_next_to_a_network_failure_is_not_recorded(cache_dir, monkeypatch, failure):
    """The outage case: a page that loaded but whose feed never fired, one
    fetch before a net::ERR_*. The browser was not demonstrably online."""
    cs = [_contract(k) for k in (50.0, 59.0, 60.0, 61.0)]
    script = {50.0: bs.HISTORY_OK, 59.0: bs.HISTORY_NO_FEED, 60.0: failure,
              61.0: bs.HISTORY_OK}

    _fetch(cache_dir, monkeypatch, cs, script, clock=_Clock(step=60.0))

    assert _entries(cache_dir) == {}


def test_no_feed_without_any_live_fetch_is_not_recorded(cache_dir, monkeypatch):
    """Nothing in the run observed the feed, so nothing proves the session works."""
    cs = [_contract(k) for k in (59.0, 60.0, 61.0)]
    _fetch(cache_dir, monkeypatch, cs, {k: bs.HISTORY_NO_FEED for k in (59.0, 60.0, 61.0)})

    assert _entries(cache_dir) == {}


def test_the_last_no_feed_of_a_run_waits_for_a_later_page_load(cache_dir, monkeypatch):
    """Nothing after it was seen, so it stays pending (and dies with the process)
    rather than being recorded on half the evidence."""
    cs = [_contract(50.0), _contract(59.0)]
    _fetch(cache_dir, monkeypatch, cs, {50.0: bs.HISTORY_OK, 59.0: bs.HISTORY_NO_FEED})

    assert _entries(cache_dir) == {}
    assert len(unlisted.TRACKER.pending) == 1


def test_a_session_that_fails_to_open_poisons_pending_no_feeds(cache_dir, monkeypatch):
    """A login refusal / dead browser in the NEXT probe is trouble around the
    previous probe's last NO_FEED."""
    clock = _Clock()
    _fetch(cache_dir, monkeypatch, [_contract(50.0), _contract(59.0)],
           {50.0: bs.HISTORY_OK, 59.0: bs.HISTORY_NO_FEED}, clock=clock)

    class _Refused:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            clock.t += 30
            raise bs.BarchartAuthError("Barchart authentication failed.")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(history, "BarchartSession", _Refused)
    with pytest.raises(bs.BarchartAuthError):
        asyncio.run(history.fetch_option_histories([_contract(70.0)], headless=True))

    assert _entries(cache_dir) == {}
    assert unlisted.TRACKER.pending == []


def test_a_known_unlisted_contract_is_skipped_like_a_failed_fetch(cache_dir, monkeypatch, caplog):
    dead = _contract(59.0)
    # What a failed fetch leaves behind today:
    failed_series, failed_details = _fetch(
        cache_dir, monkeypatch, [dead], {59.0: bs.HISTORY_NAV_ERROR})

    unlisted.apply(cache_dir / unlisted.FILENAME,
                   {"DRAM_20280915_59.00C": unlisted.recorded(None, dead, bs.HISTORY_NO_FEED)})
    calls = []
    caplog.set_level("INFO", logger="backtest")
    series, details = _fetch(cache_dir, monkeypatch, [dead], {59.0: bs.HISTORY_OK},
                             calls=calls)

    assert calls == []                       # no network call at all
    assert (series, details) == (failed_series, failed_details)
    assert "1 contracts skipped as known-unlisted" in caplog.text


def test_a_skipped_contract_with_a_stale_cache_prices_as_a_failed_refetch(
        stale_cache, cache_dir, monkeypatch):
    c = _CONTRACT[0]
    unlisted.apply(cache_dir / unlisted.FILENAME,
                   {"HYG_20250417_72.00P": unlisted.recorded(None, c, bs.HISTORY_NO_FEED)})
    calls = []
    series, details = _fetch(cache_dir, monkeypatch, _CONTRACT, {72.0: bs.HISTORY_OK},
                             calls=calls, needed_dates=_NEEDED)

    assert calls == []
    assert series[KEY] == [] and KEY not in details
    assert stale_cache.read_text(encoding="utf-8") == _shallow_csv()


@pytest.mark.parametrize("how", ["flag", "env"])
def test_retry_unlisted_probes_again_and_forgets_a_contract_that_lists_now(
        cache_dir, monkeypatch, how):
    c = _contract(59.0)
    unlisted.apply(cache_dir / unlisted.FILENAME,
                   {"DRAM_20280915_59.00C": unlisted.recorded(None, c, bs.HISTORY_NO_FEED)})
    calls = []
    if how == "flag":
        series, _ = _fetch(cache_dir, monkeypatch, [c], {59.0: bs.HISTORY_OK},
                           calls=calls, retry_unlisted=True)
    else:
        clock = _Clock()
        monkeypatch.setattr(unlisted, "_now", clock)
        monkeypatch.setenv("BARCHART_EMAIL", "x@example.com")
        monkeypatch.setenv("BARCHART_PASSWORD", "pw")
        monkeypatch.setenv(unlisted.RETRY_ENV, "1")
        monkeypatch.setattr(history, "BarchartSession",
                            _scripted_session({59.0: bs.HISTORY_OK}, clock, calls))
        series, _ = asyncio.run(history.fetch_option_histories([c], headless=True))

    assert calls == [59.0]
    assert series[c["key"]]
    assert _entries(cache_dir) == {}


def test_a_recheck_that_confirms_again_counts_it(cache_dir, monkeypatch):
    cs = [_contract(50.0), _contract(59.0), _contract(60.0)]
    old = {**unlisted.recorded(None, cs[1], "seeded_from_log_2026-09-26"),
           "first_seen": "2026-08-01T00:00:00", "last_checked": "2026-08-01T00:00:00"}
    unlisted.apply(cache_dir / unlisted.FILENAME, {old["key"]: old})

    _fetch(cache_dir, monkeypatch, cs,
           {50.0: bs.HISTORY_OK, 59.0: bs.HISTORY_NO_FEED, 60.0: bs.HISTORY_OK})

    rec = _entries(cache_dir)[old["key"]]
    assert rec["n_checks"] == 2 and rec["first_seen"] == "2026-08-01T00:00:00"
    assert rec["last_checked"] > "2026-09" and rec["reason"] == bs.HISTORY_NO_FEED


def _entry(expiry, last, n=1):
    return {"key": "X", "expiry": expiry.isoformat(),
            "last_checked": last.isoformat() + "T12:00:00", "n_checks": n}


def test_ttl_unexpired_contract_is_rechecked_after_30_days():
    today = date(2026, 9, 27)
    far = date(2028, 9, 15)
    assert unlisted.should_skip(_entry(far, today - timedelta(days=29)), today)
    assert not unlisted.should_skip(_entry(far, today - timedelta(days=30)), today)
    # However many times it was confirmed: a LEAPS can be listed later.
    assert not unlisted.should_skip(_entry(far, today - timedelta(days=31), n=9), today)


def test_ttl_expired_contract_confirmed_twice_waits_longer():
    today = date(2026, 9, 27)
    gone = date(2026, 1, 16)
    assert not unlisted.should_skip(_entry(gone, today - timedelta(days=40), n=1), today)
    assert unlisted.should_skip(_entry(gone, today - timedelta(days=100), n=2), today)
    assert not unlisted.should_skip(_entry(gone, today - timedelta(days=180), n=2), today)
    assert not unlisted.should_skip(None, today)
    assert not unlisted.should_skip({"key": "X"}, today)   # malformed → probe


def test_apply_merges_with_a_concurrent_writer_and_skips_bad_lines(tmp_path):
    p = tmp_path / unlisted.FILENAME
    a = unlisted.recorded(None, _contract(1.0), bs.HISTORY_NO_FEED)
    b = unlisted.recorded(None, _contract(2.0), bs.HISTORY_NO_FEED)
    unlisted.apply(p, {a["key"]: a})
    p.write_text(p.read_text() + "not json\n")
    unlisted.apply(p, {b["key"]: b})
    assert set(unlisted.load(p)) == {a["key"], b["key"]}
    unlisted.apply(p, {a["key"]: None})
    assert set(unlisted.load(p)) == {b["key"]}


@pytest.mark.parametrize("bad", [
    {"n_checks": None}, {"n_checks": "2"}, {"expiry": "soon"},
    {"last_checked": None}, {"key": 7},
])
def test_a_json_line_with_bad_fields_is_skipped_not_crashed_on(tmp_path, bad):
    """Valid JSON is not enough: `recorded()` once raised int(None) inside the
    post-scrape commit and aborted the run after all its scraping was done."""
    p = tmp_path / unlisted.FILENAME
    c = _contract(1.0)
    good = unlisted.recorded(None, _contract(2.0), bs.HISTORY_PAGE_404)
    broken = {**unlisted.recorded(None, c, bs.HISTORY_PAGE_404), **bad}
    p.write_text(json.dumps(broken) + "\n" + json.dumps(good) + "\n")

    known = unlisted.load(p)
    assert set(known) == {good["key"]}
    t = unlisted.EvidenceTracker()
    t.note(bs.HISTORY_OK, _contract(3.0), t=0.0, logged_in=True)
    t.note(bs.HISTORY_PAGE_404, c, t=10.0, logged_in=True)
    assert unlisted.commit(t.confirmed(final=True), p) == 1
    assert unlisted.load(p)[unlisted.contract_id(c)]["n_checks"] == 1


def test_recorded_tolerates_a_null_n_checks():
    prior = {**unlisted.recorded(None, _contract(1.0), bs.HISTORY_PAGE_404), "n_checks": None}
    assert unlisted.recorded(prior, _contract(1.0), bs.HISTORY_PAGE_404)["n_checks"] == 1


def test_a_commit_failure_after_the_scrape_never_raises(tmp_path, monkeypatch, caplog):
    from backtest.shared import history

    def boom(*a, **k):
        raise TypeError("bad entry")
    monkeypatch.setattr(unlisted, "commit", boom)
    history._commit_unlisted(unlisted.EvidenceTracker(), {}, {}, tmp_path / unlisted.FILENAME)
    assert "Could not update" in caplog.text


def test_concurrent_writers_lose_no_entries_and_leave_no_staging_file(tmp_path):
    """Two writers each merging 40 entries: the read-merge-replace is under a
    flock, so all 80 survive. Threads hold separate open file descriptions, so
    flock serialises them exactly as it does two processes."""
    import threading
    p = tmp_path / unlisted.FILENAME

    def writer(base):
        for i in range(40):
            e = unlisted.recorded(None, _contract(base + i), bs.HISTORY_PAGE_404)
            unlisted.apply(p, {e["key"]: e})

    ts = [threading.Thread(target=writer, args=(b,)) for b in (100.0, 200.0)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(unlisted.load(p)) == 80
    assert not list(tmp_path.glob("*.tmp"))


def test_both_entry_points_carry_the_escape_hatch():
    import inspect
    from backtest import core, proxy
    for mod in (core, proxy):
        assert '"--retry-unlisted"' in inspect.getsource(mod.main)


def test_the_file_is_protected_and_backed_up():
    """It lives INSIDE option_history_cache, so the cleaner never deletes it and
    backup_research_caches.py archives it with the cache."""
    from scripts.clean_generated import PROTECTED_PREFIXES
    from backtest.config import HISTORY_CACHE
    assert "backtests/option_history_cache" in PROTECTED_PREFIXES
    assert (HISTORY_CACHE / unlisted.FILENAME).parent == HISTORY_CACHE


# ── the session's outcome taxonomy ─────────────────────────────────────────────

class _Resp:
    def __init__(self, status):
        self.status = status


class _FakePage:
    def __init__(self, goto=None, url="https://www.barchart.com/stocks/quotes/X/price-history",
                 marker=True, nav_delay=0.0):
        self._goto, self.url, self._marker, self._delay = goto, url, marker, nav_delay

    def expect_request(self, _pred, timeout):
        class _Ctx:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, et, e, tb):
                if et is None:
                    raise PlaywrightTimeoutError(
                        'Timeout 15000ms exceeded while waiting for event "request"')
                return False
        return _Ctx()

    async def goto(self, url, wait_until, timeout):
        if self._delay:
            await asyncio.sleep(self._delay)
        if isinstance(self._goto, BaseException):
            raise self._goto
        return self._goto

    async def query_selector(self, _sel):
        return object() if self._marker else None


def _outcome(page, timeout_ms=15000):
    s = bs.BarchartSession("e", "p", None)
    s._page = page
    assert asyncio.run(s.fetch_history_csv("https://x/price-history", timeout_ms)) is None
    return s.last_history_outcome


def test_session_calls_a_loaded_silent_page_no_feed():
    assert _outcome(_FakePage(goto=_Resp(200))) == bs.HISTORY_NO_FEED


@pytest.mark.parametrize("err", [
    "net::ERR_INTERNET_DISCONNECTED at https://www.barchart.com/...",
    "net::ERR_NAME_NOT_RESOLVED at https://www.barchart.com/...",
    "net::ERR_SSL_PROTOCOL_ERROR at https://www.barchart.com/...",
    "net::ERR_CONNECTION_RESET at https://www.barchart.com/...",
    'Navigation to "https://..." is interrupted by another navigation to "chrome-error://chromewebdata/"',
    "Target page, context or browser has been closed",
])
def test_session_calls_a_failed_navigation_nav_error(err):
    assert _outcome(_FakePage(goto=PlaywrightError(err))) == bs.HISTORY_NAV_ERROR


def test_session_calls_a_navigation_timeout_nav_error():
    assert _outcome(_FakePage(goto=PlaywrightTimeoutError("Page.goto: Timeout"))) \
        == bs.HISTORY_NAV_ERROR


@pytest.mark.parametrize("status", [401, 403, 410, 429, 500, 502, 503])
def test_session_calls_an_http_error_page_http_error(status):
    assert _outcome(_FakePage(goto=_Resp(status))) == bs.HISTORY_HTTP_ERROR


def test_session_calls_a_login_redirect_or_logged_out_page_session():
    assert _outcome(_FakePage(goto=_Resp(200), url="https://www.barchart.com/login")) \
        == bs.HISTORY_SESSION
    assert _outcome(_FakePage(goto=_Resp(200), marker=False)) == bs.HISTORY_SESSION


def test_session_does_not_call_a_slow_page_no_feed():
    """A page that took most of the window to load might have fired the feed
    a moment later — not evidence."""
    assert _outcome(_FakePage(goto=_Resp(200), nav_delay=0.06), timeout_ms=100) \
        == bs.HISTORY_ERROR


# ── a PAGE 404 is evidence too (2026-09-27, first live run) ────────────────────
#
# The live run showed Barchart answers an unlisted contract's price-history page
# with a non-2xx status (DRAM|20280623|59.00C..62.00C came back http_error), so
# NO_FEED alone never fired. A PAGE-level 404 is now recorded under the same
# online proof, as reason `http_404`; 403/429/5xx and any FEED status never are.

def test_a_page_404_between_live_fetches_is_recorded_as_http_404(cache_dir, monkeypatch):
    cs = [_contract(50.0), _contract(59.0), _contract(60.0)]
    script = {50.0: bs.HISTORY_OK, 59.0: (bs.HISTORY_PAGE_404, True), 60.0: bs.HISTORY_OK}

    series, details = _fetch(cache_dir, monkeypatch, cs, script)

    rec = _entries(cache_dir)["DRAM_20280915_59.00C"]
    assert rec["reason"] == "http_404" and rec["n_checks"] == 1
    assert series[cs[1]["key"]] == [] and cs[1]["key"] not in details


def test_a_markerless_page_404_is_recorded_on_same_session_proof(cache_dir, monkeypatch):
    cs = [_contract(50.0), _contract(59.0), _contract(60.0)]
    script = {50.0: bs.HISTORY_OK, 59.0: (bs.HISTORY_PAGE_404, False), 60.0: bs.HISTORY_OK}

    _fetch(cache_dir, monkeypatch, cs, script)

    assert _entries(cache_dir)["DRAM_20280915_59.00C"]["reason"] == "http_404"


def test_a_markerless_page_404_needs_its_own_session_logged_in_earlier():
    """Tracker level: a 404 page without the account header counts only if the
    SAME session opened (login verified) or served a logged-in page before it."""
    t = unlisted.EvidenceTracker()
    other, mine = object(), object()
    c = _contract(59.0)
    t.note(unlisted.SESSION_OPEN, session=other, t=0.0)
    t.note(bs.HISTORY_OK, _contract(50.0), session=other, t=10.0)
    t.note(bs.HISTORY_PAGE_404, c, session=mine, logged_in=False, t=20.0)
    assert t.confirmed(final=True) == []

    t = unlisted.EvidenceTracker()
    t.note(unlisted.SESSION_OPEN, session=mine, t=0.0)
    t.note(bs.HISTORY_OK, _contract(50.0), session=mine, t=10.0)
    t.note(bs.HISTORY_PAGE_404, c, session=mine, logged_in=False, t=20.0)
    assert [r for _c, r, _p in t.confirmed(final=True)] == ["http_404"]


def test_a_page_404_next_to_a_network_failure_is_not_recorded(cache_dir, monkeypatch):
    cs = [_contract(k) for k in (50.0, 59.0, 60.0, 61.0)]
    script = {50.0: bs.HISTORY_OK, 59.0: (bs.HISTORY_PAGE_404, True),
              60.0: bs.HISTORY_NAV_ERROR, 61.0: bs.HISTORY_OK}

    _fetch(cache_dir, monkeypatch, cs, script, clock=_Clock(step=60.0))

    assert _entries(cache_dir) == {}


def test_session_calls_a_page_404_http_404_and_logs_the_page_status(caplog):
    s = bs.BarchartSession("e", "p", None)
    s._page = _FakePage(goto=_Resp(404), marker=False)
    caplog.set_level("WARNING", logger="lib.barchart.session")
    assert asyncio.run(s.fetch_history_csv("https://x/price-history", 15000)) is None
    assert s.last_history_outcome == bs.HISTORY_PAGE_404
    assert s.last_history_http == ("page", 404)
    assert s.last_history_logged_in is False
    assert "[outcome=http_404 page_status=404]" in caplog.text


@pytest.mark.parametrize("status", [403, 429, 500, 503])
def test_session_logs_the_page_status_on_http_error(status, caplog):
    s = bs.BarchartSession("e", "p", None)
    s._page = _FakePage(goto=_Resp(status))
    caplog.set_level("ERROR", logger="lib.barchart.session")
    asyncio.run(s.fetch_history_csv("https://x/price-history", 15000))
    assert s.last_history_http == ("page", status)
    assert f"[outcome=http_error page_status={status}]" in caplog.text


def test_session_calls_a_page_404_on_login_session():
    assert _outcome(_FakePage(goto=_Resp(404), url="https://www.barchart.com/login")) \
        == bs.HISTORY_SESSION


class _FeedPage(_FakePage):
    """The page loads and fires the feed; the re-issued FEED answers ``status``."""
    def __init__(self, status):
        super().__init__(goto=_Resp(200))
        feed_status = status

        class _Req:
            url = "https://www.barchart.com/proxies/core-api/v1/historical/get?symbol=X"

            async def all_headers(self):
                return {"referer": "x"}

        class _FeedResp:
            ok = False
            status = feed_status

        class _Request:
            async def get(self, url, headers, timeout):
                return _FeedResp()

        self._req, self.request = _Req(), _Request()

    def expect_request(self, _pred, timeout):
        req = self._req

        class _Ctx:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, *exc):
                return False

            @property
            def value(self_inner):
                async def _v():
                    return req
                return _v()
        return _Ctx()


@pytest.mark.parametrize("status", [404, 403, 500])
def test_session_calls_any_feed_status_http_error_never_http_404(status, caplog):
    s = bs.BarchartSession("e", "p", None)
    s._page = _FeedPage(status)
    caplog.set_level("WARNING", logger="lib.barchart.session")
    assert asyncio.run(s.fetch_history_csv("https://x/price-history", 15000)) is None
    assert s.last_history_outcome == bs.HISTORY_HTTP_ERROR
    assert s.last_history_http == ("feed", status)
    assert f"feed_status={status}" in caplog.text


# ── page 404: early exit, and the 404 is its own online proof (2026-09-27) ────
#
# Second live run: 33/33 of a probe round answered page 404, each still cost
# ~15s waiting for a feed that never comes, and none was recorded because no
# feed success fell inside the 30-minute window.


class _TimedPage(_FakePage):
    """Records whether the feed wait was awaited (a clean block exit) or
    cancelled (an exception out of the block)."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self.awaited_feed = None

    def expect_request(self, _pred, timeout):
        page = self

        class _Ctx:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, et, e, tb):
                page.awaited_feed = et is None
                if et is None:
                    await asyncio.sleep(timeout / 1000)
                    raise PlaywrightTimeoutError("Timeout waiting for event \"request\"")
                return False
        return _Ctx()


def test_a_page_404_returns_at_once_without_waiting_for_the_feed(caplog):
    import time as _t
    s = bs.BarchartSession("e", "p", None)
    s._page = page = _TimedPage(goto=_Resp(404))
    caplog.set_level("WARNING", logger="lib.barchart.session")
    t0 = _t.monotonic()
    assert asyncio.run(s.fetch_history_csv("https://x/price-history", 2000)) is None
    assert _t.monotonic() - t0 < 1.0                 # the 2s feed wait never ran
    assert page.awaited_feed is False                # the waiter was cancelled
    assert s.last_history_outcome == bs.HISTORY_PAGE_404
    assert "[outcome=http_404 page_status=404]" in caplog.text


def test_a_page_404_on_login_still_exits_early_as_session():
    s = bs.BarchartSession("e", "p", None)
    s._page = page = _TimedPage(goto=_Resp(404), url="https://www.barchart.com/login")
    assert asyncio.run(s.fetch_history_csv("https://x/price-history", 2000)) is None
    assert page.awaited_feed is False and s.last_history_outcome == bs.HISTORY_SESSION


def test_a_page_403_still_waits_and_stays_http_error():
    s = bs.BarchartSession("e", "p", None)
    s._page = page = _TimedPage(goto=_Resp(403))
    asyncio.run(s.fetch_history_csv("https://x/price-history", 50))
    assert page.awaited_feed is True and s.last_history_outcome == bs.HISTORY_HTTP_ERROR


def test_page_404s_with_no_feed_success_anywhere_are_never_recorded(cache_dir, monkeypatch):
    """A run where EVERY contract 404s and no feed ever answers is what a
    Barchart route change or a URL-format regression looks like — nothing in it
    counts as trouble. Without feed proof, recording it would skip-list the
    whole universe; unproven 404s are re-probed instead (a 404 returns at once)."""
    ks = (59.0, 60.0, 61.0)
    cs = [_contract(k) for k in ks]
    _fetch(cache_dir, monkeypatch, cs, {k: (bs.HISTORY_PAGE_404, True) for k in ks})
    unlisted.flush_at_exit()

    assert _entries(cache_dir) == {}
    assert unlisted.TRACKER.pending == []


def test_page_404s_after_a_feed_success_are_recorded_and_flushed_at_exit(
        cache_dir, monkeypatch):
    """The same dead run, with one live fetch before it: the 404s are recorded
    once their 2-minute window closes; the last one, whose window the run never
    saw close, is flushed at process exit."""
    ks = (59.0, 60.0, 61.0)
    cs = [_contract(50.0)] + [_contract(k) for k in ks]
    script = {50.0: bs.HISTORY_OK, **{k: (bs.HISTORY_PAGE_404, False) for k in ks}}
    _fetch(cache_dir, monkeypatch, cs, script)
    unlisted.flush_at_exit()

    e = _entries(cache_dir)
    assert set(e) == {f"DRAM_20280915_{k:.2f}C" for k in ks}
    assert {r["reason"] for r in e.values()} == {"http_404"}
    assert unlisted.TRACKER.pending == []


@pytest.mark.parametrize("failure", [
    bs.HISTORY_NAV_ERROR, bs.HISTORY_HTTP_ERROR, bs.HISTORY_SESSION, bs.HISTORY_ERROR, None])
def test_a_page_404_within_two_minutes_of_a_failure_is_never_recorded(
        cache_dir, monkeypatch, failure):
    cs = [_contract(59.0), _contract(60.0)]
    _fetch(cache_dir, monkeypatch, cs,
           {59.0: (bs.HISTORY_PAGE_404, True), 60.0: failure}, clock=_Clock(step=60.0))
    unlisted.flush_at_exit()

    assert _entries(cache_dir) == {}


def test_a_failure_before_a_page_404_also_poisons_it(cache_dir, monkeypatch):
    cs = [_contract(59.0), _contract(60.0)]
    _fetch(cache_dir, monkeypatch, cs,
           {59.0: bs.HISTORY_NAV_ERROR, 60.0: (bs.HISTORY_PAGE_404, True)},
           clock=_Clock(step=60.0))
    unlisted.flush_at_exit()

    assert _entries(cache_dir) == {}


def test_exit_flush_drops_pending_no_feed(cache_dir, monkeypatch):
    """NO_FEED keeps its stricter proof: still unproven at exit, it is dropped."""
    _fetch(cache_dir, monkeypatch, [_contract(50.0), _contract(59.0)],
           {50.0: bs.HISTORY_OK, 59.0: bs.HISTORY_NO_FEED})
    unlisted.flush_at_exit()

    assert _entries(cache_dir) == {}
    assert unlisted.TRACKER.pending == []


def test_the_exit_flush_is_registered():
    import inspect
    assert "atexit.register(flush_at_exit)" in inspect.getsource(unlisted)
