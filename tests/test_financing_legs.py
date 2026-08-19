"""Unit tests for `scripts/collector/fetch_financing_legs.py`.

Covers the pre-registered target-derivation rule (`financed_spread.md`
§Anti-tuning): for every (ticker, expiry) row-group the pooled book entered a
leg into, the 2 nearest cached-ladder strikes strictly above the group's
highest leg strike (Call, fin_call_above) and strictly below its lowest leg
strike (Put, fin_put_below) — candidate strikes always come from the
ticker's OWN observed cached-ladder (union across all expiries/types),
never an invented increment — plus cache-presence skip/count
(`split_cached`), the manifest's resume semantics (fetched/failed rows are
never clobbered, --limit is honored, --retry-failed gating), and that the
financing manifest path is a SEPARATE constant from `fetch_sweep_legs.py`'s
legs manifest (calendar_hedge ARM S depends on that one).

Everything is synthetic and written to tmp_path; no network, no real cache.
"""
import asyncio
from datetime import date, timedelta

import pytest

from lib.barchart.options import cache_path
from scripts.backtest.legs import Leg
from scripts.collector import fetch_financing_legs as ffl
from scripts.collector import fetch_sweep_legs as fsl

E1 = date(2024, 6, 21)   # near expiry
E2 = date(2024, 7, 19)   # a later expiry (unused by financing targets, kept
                         # for parity with a second-group test)

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
          "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")


def _history_csv(days) -> str:
    rows = [HEADER]
    for d in days:
        rows.append(f"{d.isoformat()},1.0,1.1,0.9,1.0,0,0%,10,5,,,,,,,,100,0.95,1.05")
    return "\n".join(rows) + "\n"


class _FakeTrade:
    """Stand-in for `harness.Trade`: only `.legs` is touched by
    `leg_strike_groups`, so a real Trade (which needs a full BacktestResults
    row) would be pure overhead here."""
    def __init__(self, legs):
        self.legs = legs


def _rec(legs):
    return {"t": _FakeTrade(legs)}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    cache = tmp_path / "opt_cache"
    cache.mkdir()
    monkeypatch.setattr(ffl, "HISTORY_CACHE", cache)
    yield cache


# --- distinct manifest paths -----------------------------------------------------

def test_financing_manifest_path_is_distinct_from_legs_manifest_path():
    """calendar_hedge --arm S depends on legs_manifest.csv; this collector
    must never read or write it."""
    assert ffl.MANIFEST_PATH != fsl.MANIFEST_PATH
    assert ffl.MANIFEST_PATH.name == "financing_manifest.csv"
    assert fsl.MANIFEST_PATH.name == "legs_manifest.csv"
    assert ffl.MANIFEST_FIELDS == fsl.MANIFEST_FIELDS


# --- leg_strike_groups ------------------------------------------------------------

def test_leg_strike_groups_reads_lowest_and_highest_strike_per_ticker_expiry():
    legs = [Leg(1, "AAA", E1, 100.0, "Call"), Leg(-1, "AAA", E1, 110.0, "Call"),
            Leg(1, "AAA", E1, 95.0, "Put")]
    groups = ffl.leg_strike_groups([_rec(legs)])
    assert groups == {("AAA", E1): (95.0, 110.0)}


def test_leg_strike_groups_each_leg_expiration_is_its_own_group():
    legs = [Leg(-1, "AAA", E1, 100.0, "Call"), Leg(1, "AAA", E2, 105.0, "Call")]
    groups = ffl.leg_strike_groups([_rec(legs)])
    assert groups == {("AAA", E1): (100.0, 100.0), ("AAA", E2): (105.0, 105.0)}


def test_leg_strike_groups_pools_strikes_across_multiple_records():
    legs1 = [Leg(1, "AAA", E1, 100.0, "Call")]
    legs2 = [Leg(-1, "AAA", E1, 90.0, "Call"), Leg(1, "AAA", E1, 120.0, "Call")]
    groups = ffl.leg_strike_groups([_rec(legs1), _rec(legs2)])
    assert groups == {("AAA", E1): (90.0, 120.0)}


def test_leg_strike_groups_skips_records_with_no_trade():
    assert ffl.leg_strike_groups([{"t": None}]) == {}


# --- ticker_ladder ------------------------------------------------------------------

def test_ticker_ladder_unions_strikes_across_expiries_and_types():
    idx = {
        ("AAA", E1): {100.0: {"C"}, 105.0: {"P"}},
        ("AAA", E2): {110.0: {"C", "P"}},
        ("BBB", E1): {50.0: {"C"}},
    }
    ladder = ffl.ticker_ladder(idx)
    assert ladder["AAA"] == [100.0, 105.0, 110.0]
    assert ladder["BBB"] == [50.0]


def test_ticker_ladder_empty_for_ticker_with_no_cache_at_all():
    assert ffl.ticker_ladder({}) == {}


# --- _candidates_for_group: the strictly-above / strictly-below 2-nearest rule ----

def test_candidates_above_take_the_2_nearest_ladder_strikes_strictly_above_hi():
    ladder = [90.0, 95.0, 100.0, 105.0, 110.0, 115.0, 120.0]
    out = ffl._candidates_for_group("AAA", E1, lo=100.0, hi=100.0, ladder=ladder)
    above = [(r["strike"], r["opt_type"], r["category"]) for r in out
             if r["category"] == "fin_call_above"]
    assert above == [(105.0, "C", "fin_call_above"), (110.0, "C", "fin_call_above")]


def test_candidates_below_take_the_2_nearest_ladder_strikes_strictly_below_lo():
    ladder = [90.0, 95.0, 100.0, 105.0, 110.0]
    out = ffl._candidates_for_group("AAA", E1, lo=100.0, hi=100.0, ladder=ladder)
    below = [(r["strike"], r["opt_type"], r["category"]) for r in out
             if r["category"] == "fin_put_below"]
    assert below == [(95.0, "P", "fin_put_below"), (90.0, "P", "fin_put_below")]


def test_candidates_exclude_strikes_equal_to_lo_or_hi():
    """STRICTLY above / below: a strike exactly at the row-group's bound is
    never a target even though it's on the ladder."""
    ladder = [95.0, 100.0, 110.0, 120.0]
    out = ffl._candidates_for_group("AAA", E1, lo=100.0, hi=100.0, ladder=ladder)
    strikes = {r["strike"] for r in out}
    assert 100.0 not in strikes


def test_candidates_never_invents_a_strike_when_fewer_than_2_exist():
    """Only 1 strike above hi on the ladder -> exactly 1 fin_call_above
    target, never a fabricated second one."""
    ladder = [90.0, 100.0, 105.0]
    out = ffl._candidates_for_group("AAA", E1, lo=100.0, hi=100.0, ladder=ladder)
    above = [r for r in out if r["category"] == "fin_call_above"]
    below = [r for r in out if r["category"] == "fin_put_below"]
    assert [r["strike"] for r in above] == [105.0]
    assert [r["strike"] for r in below] == [90.0]


def test_candidates_empty_when_ladder_has_nothing_beyond_the_bounds():
    ladder = [100.0]
    out = ffl._candidates_for_group("AAA", E1, lo=100.0, hi=100.0, ladder=ladder)
    assert out == []


def test_candidates_carry_the_group_ticker_and_expiry():
    ladder = [90.0, 100.0, 105.0, 110.0]
    out = ffl._candidates_for_group("AAA", E1, lo=100.0, hi=100.0, ladder=ladder)
    assert all(r["ticker"] == "AAA" and r["expiration"] == E1 for r in out)


# --- financing_target_records / financing_targets ---------------------------------

def test_financing_target_records_combines_groups_and_ladder():
    idx = {("AAA", E1): {90.0: {"C"}, 100.0: {"C", "P"}, 105.0: {"P"}, 110.0: {"C"}}}
    legs = [Leg(1, "AAA", E1, 100.0, "Call")]
    recs = ffl.financing_target_records([_rec(legs)], idx)
    keys = {(r["ticker"], r["expiration"], r["strike"], r["opt_type"]) for r in recs}
    assert (("AAA", E1, 105.0, "C") in keys)   # nearest above 100 on the ladder
    assert (("AAA", E1, 110.0, "C") in keys)   # 2nd nearest above
    assert (("AAA", E1, 90.0, "P") in keys)    # nearest below 100 on the ladder


def test_financing_target_records_dedupes_across_overlapping_groups():
    idx = {("AAA", E1): {90.0: {"C"}, 100.0: {"C"}, 110.0: {"C"}}}
    legs1 = [Leg(1, "AAA", E1, 100.0, "Call")]
    legs2 = [Leg(-1, "AAA", E1, 100.0, "Call")]
    recs = ffl.financing_target_records([_rec(legs1), _rec(legs2)], idx)
    keys = [(r["ticker"], r["expiration"], r["strike"], r["opt_type"]) for r in recs]
    assert len(keys) == len(set(keys))


def test_financing_targets_returns_sorted_plain_tuples():
    idx = {("AAA", E1): {90.0: {"C"}, 100.0: {"C"}, 110.0: {"C"}}}
    legs = [Leg(1, "AAA", E1, 100.0, "Call")]
    out = ffl.financing_targets([_rec(legs)], idx)
    assert out == sorted(out)
    assert all(isinstance(t, tuple) and len(t) == 4 for t in out)


# --- split_cached: skip targets already present in the cache, but count them ------

def test_split_cached_separates_already_cached_from_missing():
    idx = {("AAA", E1): {105.0: {"C"}}}   # 105C already cached
    targets = [
        dict(ticker="AAA", expiration=E1, strike=105.0, opt_type="C", category="fin_call_above"),
        dict(ticker="AAA", expiration=E1, strike=110.0, opt_type="C", category="fin_call_above"),
    ]
    cached, missing = ffl.split_cached(targets, idx)
    assert [r["strike"] for r in cached] == [105.0]
    assert [r["strike"] for r in missing] == [110.0]


def test_split_cached_all_missing_when_nothing_cached():
    idx = {}
    targets = [dict(ticker="AAA", expiration=E1, strike=105.0, opt_type="C",
                   category="fin_call_above")]
    cached, missing = ffl.split_cached(targets, idx)
    assert cached == []
    assert missing == targets


# --- cache filename convention ---------------------------------------------------

def test_contract_path_matches_the_backtest_cache_convention(_isolate):
    target = ("AAA", E1, 105.0, "C")
    assert ffl.contract_path(target) == cache_path(_isolate, "AAA", E1, 105.0, "Call")
    assert ffl.contract_path(target).name == "AAA_20240621_105.00C.csv"


# --- manifest: round trip + merge semantics --------------------------------------

def test_manifest_round_trip(tmp_path):
    path = tmp_path / "financing_manifest.csv"
    rows = {ffl._key("AAA", E1, 105.0, "C"): dict(
        ticker="AAA", expiration=E1.isoformat(), strike="105.00", opt_type="C",
        category="fin_call_above", status="pending", fetched_at="", reason="")}
    ffl.write_manifest(path, rows)
    loaded = ffl.load_manifest(path)
    assert loaded == rows


def test_merge_manifest_adds_new_targets_as_pending():
    target = dict(ticker="AAA", expiration=E1, strike=105.0, opt_type="C",
                 category="fin_call_above")
    merged = ffl.merge_manifest({}, [target])
    row = merged[ffl._key("AAA", E1, 105.0, "C")]
    assert row["status"] == "pending" and row["category"] == "fin_call_above"


def test_merge_manifest_never_clobbers_fetched_or_failed_rows():
    key = ffl._key("AAA", E1, 105.0, "C")
    existing = {key: dict(ticker="AAA", expiration=E1.isoformat(), strike="105.00",
                          opt_type="C", category="fin_call_above", status="fetched",
                          fetched_at="2026-08-19T00:00:00+00:00", reason="")}
    target = dict(ticker="AAA", expiration=E1, strike=105.0, opt_type="C",
                 category="fin_call_above")
    merged = ffl.merge_manifest(existing, [target])
    assert merged[key]["status"] == "fetched"
    assert merged[key]["fetched_at"] == "2026-08-19T00:00:00+00:00"

    existing[key]["status"] = "failed"
    existing[key]["reason"] = "no data"
    merged = ffl.merge_manifest(existing, [target])
    assert merged[key]["status"] == "failed" and merged[key]["reason"] == "no data"


def test_merge_manifest_refreshes_an_existing_pending_row():
    key = ffl._key("AAA", E1, 105.0, "C")
    existing = {key: dict(ticker="AAA", expiration=E1.isoformat(), strike="105.00",
                          opt_type="C", category="fin_call_above", status="pending",
                          fetched_at="", reason="")}
    target = dict(ticker="AAA", expiration=E1, strike=105.0, opt_type="C",
                 category="fin_put_below")
    merged = ffl.merge_manifest(existing, [target])
    assert merged[key]["category"] == "fin_put_below"
    assert merged[key]["status"] == "pending"


def test_sync_cache_status_marks_fetched_without_a_request(_isolate):
    key = ffl._key("AAA", E1, 105.0, "C")
    rows = {key: dict(ticker="AAA", expiration=E1.isoformat(), strike="105.00",
                      opt_type="C", category="fin_call_above", status="pending",
                      fetched_at="", reason="")}
    ffl.contract_path(("AAA", E1, 105.0, "C")).write_text(_history_csv([E1]))
    n = ffl.sync_cache_status(rows)
    assert n == 1
    assert rows[key]["status"] == "fetched"


def test_sync_cache_status_leaves_uncached_rows_pending(_isolate):
    key = ffl._key("AAA", E1, 105.0, "C")
    rows = {key: dict(ticker="AAA", expiration=E1.isoformat(), strike="105.00",
                      opt_type="C", category="fin_call_above", status="pending",
                      fetched_at="", reason="")}
    n = ffl.sync_cache_status(rows)
    assert n == 0
    assert rows[key]["status"] == "pending"


# --- run_fetch: the resumable scrape loop -----------------------------------------

def _run(coro):
    """Drive a coroutine to completion (repo convention; pytest-asyncio isn't
    configured here — same helper as test_sweep_legs.py)."""
    return asyncio.new_event_loop().run_until_complete(coro)


def _pending_row(ticker="AAA", exp=E1, strike=105.0, cp="C", category="fin_call_above"):
    key = ffl._key(ticker, exp, strike, cp)
    row = dict(ticker=ticker, expiration=exp.isoformat(), strike=f"{strike:.2f}",
              opt_type=cp, category=category, status="pending", fetched_at="", reason="")
    return key, row


def test_run_fetch_writes_the_file_and_marks_the_row_fetched(tmp_path, _isolate):
    key, row = _pending_row()
    rows = {key: row}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            assert "AAA" in url and "105.00C" in url
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(ffl.run_fetch(rows, manifest, sleep_s=0, session=_Session()))
    assert stats.get("fetched") == 1
    assert rows[key]["status"] == "fetched" and rows[key]["fetched_at"]
    assert ffl.contract_path(ffl.target_of_row(rows[key])).exists()
    # flushed to disk, not just held in memory
    assert ffl.load_manifest(manifest)[key]["status"] == "fetched"


def test_run_fetch_marks_failed_on_no_data_and_writes_nothing(tmp_path, _isolate):
    key, row = _pending_row()
    rows = {key: row}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return None

    stats = _run(ffl.run_fetch(rows, manifest, sleep_s=0, session=_Session()))
    assert stats.get("failed") == 1
    assert rows[key]["status"] == "failed" and rows[key]["reason"]
    assert not ffl.contract_path(ffl.target_of_row(rows[key])).exists()


def test_run_fetch_never_traded_contract_is_marked_failed_not_written(tmp_path, _isolate):
    key, row = _pending_row()
    rows = {key: row}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return HEADER + "\n"   # header only, zero bars

    stats = _run(ffl.run_fetch(rows, manifest, sleep_s=0, session=_Session()))
    assert stats.get("no_bars") == 1
    assert rows[key]["status"] == "failed"
    assert not ffl.contract_path(ffl.target_of_row(rows[key])).exists()


def test_run_fetch_honors_limit(tmp_path, _isolate):
    rows = {}
    for strike in (100.0, 101.0, 102.0):
        k, r = _pending_row(strike=strike)
        rows[k] = r
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(ffl.run_fetch(rows, manifest, limit=2, sleep_s=0, session=_Session()))
    fetched = sum(1 for r in rows.values() if r["status"] == "fetched")
    assert fetched == 2
    assert stats.get("fetched") == 2
    still_pending = sum(1 for r in rows.values() if r["status"] == "pending")
    assert still_pending == 1


def test_run_fetch_skip_existing_before_the_loop_costs_no_request(tmp_path, _isolate):
    key, row = _pending_row(strike=100.0)
    key2, row2 = _pending_row(strike=101.0)
    rows = {key: row, key2: row2}
    manifest = tmp_path / "manifest.csv"
    ffl.contract_path(ffl.target_of_row(row)).write_text(
        _history_csv([E1, E1 - timedelta(days=1)]))

    calls = []

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            calls.append(url)
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(ffl.run_fetch(rows, manifest, limit=1, sleep_s=0, session=_Session()))
    assert rows[key]["status"] == "fetched"     # resolved via the upfront sync
    assert rows[key2]["status"] == "fetched"    # the ONE real attempt limit=1 allowed
    assert len(calls) == 1
    assert stats.get("fetched") == 1


def test_run_fetch_retries_failed_rows_only_when_flag_set(tmp_path, _isolate):
    key, row = _pending_row()
    row["status"], row["reason"] = "failed", "no data"
    rows = {key: row}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(ffl.run_fetch(dict(rows), manifest, sleep_s=0, session=_Session()))
    assert stats.get("fetched") is None
    assert rows[key]["status"] == "failed"

    stats = _run(ffl.run_fetch(rows, manifest, retry_failed=True, sleep_s=0, session=_Session()))
    assert stats.get("fetched") == 1
    assert rows[key]["status"] == "fetched"


def test_run_fetch_resumes_after_a_simulated_crash(tmp_path, _isolate):
    """The manifest is flushed after every contract, so a second run reading
    the same manifest file picks up exactly where an interrupted first run
    left off — nothing is re-fetched, nothing is skipped."""
    manifest = tmp_path / "manifest.csv"
    rows = {}
    for strike in (100.0, 101.0, 102.0):
        k, r = _pending_row(strike=strike)
        rows[k] = r
    ffl.write_manifest(manifest, rows)

    seen_urls = []

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            seen_urls.append(url)
            return _history_csv([E1, E1 - timedelta(days=1)])

    rows1 = ffl.load_manifest(manifest)
    _run(ffl.run_fetch(rows1, manifest, limit=1, sleep_s=0, session=_Session()))
    on_disk = ffl.load_manifest(manifest)
    assert sum(1 for r in on_disk.values() if r["status"] == "fetched") == 1

    rows2 = ffl.load_manifest(manifest)
    _run(ffl.run_fetch(rows2, manifest, sleep_s=0, session=_Session()))
    final = ffl.load_manifest(manifest)
    assert all(r["status"] == "fetched" for r in final.values())
    assert len(seen_urls) == 3   # one per distinct contract, never repeated
    assert len(set(seen_urls)) == 3


# ═══ ARM F4 — the diagonal (fin_diag) target derivation, amendment 1 ═══════════
#
# Registered rule (`financed_spread.md` §AMENDMENT 1): per BOOK ROW (a two-leg
# single-expiry debit vertical), the near expiry is the NEAREST expiry in the
# ticker's cached expiry set that is >= 7 calendar days after the row's entry
# session AND <= 1/2 the debit's DTE at entry; a row with nothing in that
# window is counted `no_near_expiry` and targeted with nothing. Targets are the
# 4 nearest cached-ladder strikes STRICTLY beyond the debit's outer leg — calls
# above for a bull base, puts below for a bear base — AT THAT NEAR EXPIRY.

E0 = date(2024, 6, 3)    # a stand-in entry session for the window tests

DIAG_LADDER = [80.0, 85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 115.0, 120.0, 125.0]


class _FakeDebitTrade(_FakeTrade):
    """`_FakeTrade` plus the `.grid` `diag_target_records` hands to
    `entry_date_for`. The entry day itself is stubbed in the tests: which day a
    leg set first prices on is `bear_rewrap`'s contract, not this collector's."""
    def __init__(self, legs, grid=None):
        super().__init__(legs)
        self.grid = grid or [E0]


def _debit_rec(legs, grid=None):
    """A pooled-book record shaped the way `financed_spread.population` reads
    it: `t` with legs, and the debit/credit sign flag."""
    return {"t": _FakeDebitTrade(legs, grid), "credit": False}


def _bull_legs(ticker="AAA", exp=None, lo=100.0, hi=110.0):
    exp = exp or date(2024, 8, 16)
    return [Leg(1, ticker, exp, lo, "Call"), Leg(-1, ticker, exp, hi, "Call")]


def _bear_legs(ticker="AAA", exp=None, lo=90.0, hi=100.0):
    exp = exp or date(2024, 8, 16)
    return [Leg(1, ticker, exp, hi, "Put"), Leg(-1, ticker, exp, lo, "Put")]


@pytest.fixture()
def _fixed_entry_day(monkeypatch):
    """Pin the entry session to E0 so the window tests read the RULE and not
    the option cache's coverage."""
    monkeypatch.setattr(ffl.BR, "entry_date_for", lambda legs, grid: E0)
    return E0


# --- ticker_expiries: the cached expiry set the window is drawn from -------------

def test_ticker_expiries_unions_expiries_across_strikes_and_types():
    idx = {("AAA", E1): {100.0: {"C"}}, ("AAA", E2): {105.0: {"P"}},
           ("BBB", E2): {50.0: {"C"}}}
    out = ffl.ticker_expiries(idx)
    assert out["AAA"] == [E1, E2]
    assert out["BBB"] == [E2]


def test_ticker_expiries_empty_for_an_uncached_ticker():
    assert ffl.ticker_expiries({}) == {}


# --- the near-expiry window: >= 7 days after entry AND <= 1/2 the debit's DTE ----

def test_near_expiry_takes_the_nearest_expiry_inside_the_window():
    # entry 2024-06-03, DTE 60 -> window [06-10, 07-03]
    expiries = [date(2024, 6, 14), date(2024, 6, 21), date(2024, 7, 3)]
    assert ffl.near_expiry_for(E0, 60, expiries) == date(2024, 6, 14)


def test_near_expiry_rejects_an_expiry_inside_the_7_day_floor():
    """A 3-day expiry is nearer, and is NOT the answer: the floor is the whole
    point of "expiring while the debit thesis is still developing"."""
    expiries = [date(2024, 6, 6), date(2024, 6, 21)]
    assert ffl.near_expiry_for(E0, 60, expiries) == date(2024, 6, 21)


def test_near_expiry_accepts_exactly_the_7_day_floor():
    assert ffl.near_expiry_for(E0, 60, [date(2024, 6, 10)]) == date(2024, 6, 10)


def test_near_expiry_accepts_exactly_half_the_debits_dte():
    # 1/2 of 60 -> entry + 30 = 2024-07-03, inclusive
    assert ffl.near_expiry_for(E0, 60, [date(2024, 7, 3)]) == date(2024, 7, 3)


def test_near_expiry_rejects_an_expiry_past_half_the_debits_dte():
    assert ffl.near_expiry_for(E0, 60, [date(2024, 7, 4)]) is None


def test_near_expiry_none_when_the_window_is_empty():
    """A short-dated debit closes the window entirely: DTE 12 -> [06-10, 06-09],
    which nothing can satisfy. Counted, never widened to fit."""
    assert ffl.near_expiry_for(E0, 12, [date(2024, 6, 14)]) is None


def test_near_expiry_never_invents_an_expiry_off_the_cached_set():
    assert ffl.near_expiry_for(E0, 60, []) is None


# --- candidate strikes: the 4 nearest, strictly beyond the outer leg -------------

def test_diag_candidates_bull_takes_the_4_nearest_strikes_strictly_above():
    out = ffl._diag_candidates_for_row("AAA", E1, outer=100.0, dirn="bull",
                                       ladder=DIAG_LADDER)
    assert [r["strike"] for r in out] == [105.0, 110.0, 115.0, 120.0]
    assert {r["opt_type"] for r in out} == {"C"}
    assert {r["category"] for r in out} == {"fin_diag_call"}


def test_diag_candidates_bear_takes_the_4_nearest_strikes_strictly_below():
    out = ffl._diag_candidates_for_row("AAA", E1, outer=100.0, dirn="bear",
                                       ladder=DIAG_LADDER)
    assert [r["strike"] for r in out] == [95.0, 90.0, 85.0, 80.0]
    assert {r["opt_type"] for r in out} == {"P"}
    assert {r["category"] for r in out} == {"fin_diag_put"}


def test_diag_candidates_exclude_the_outer_strike_itself():
    out = ffl._diag_candidates_for_row("AAA", E1, outer=100.0, dirn="bull",
                                       ladder=DIAG_LADDER)
    assert 100.0 not in {r["strike"] for r in out}


def test_diag_candidates_never_invent_a_strike_to_reach_four():
    out = ffl._diag_candidates_for_row("AAA", E1, outer=100.0, dirn="bull",
                                       ladder=[95.0, 100.0, 105.0, 110.0])
    assert [r["strike"] for r in out] == [105.0, 110.0]


def test_diag_candidates_sit_at_the_near_expiry_not_the_debits():
    out = ffl._diag_candidates_for_row("AAA", E1, outer=100.0, dirn="bull",
                                       ladder=DIAG_LADDER)
    assert all(r["expiration"] == E1 for r in out)


def test_diag_candidate_count_is_the_registered_four():
    assert ffl.DIAG_N_CANDIDATES == 4


# --- diag_target_records: the whole derivation, with its census ------------------

def _diag_idx(ticker="AAA", expiries=(date(2024, 6, 14), date(2024, 8, 16)),
              strikes=tuple(DIAG_LADDER)):
    return {(ticker, e): {k: {"C", "P"} for k in strikes} for e in expiries}


def test_diag_target_records_targets_a_bull_row_above_its_outer_strike(_fixed_entry_day):
    # debit expires 2024-08-16, entry 2024-06-03 -> DTE 74, window ends 06-40 =
    # 2024-07-10, so the cached 2024-06-14 expiry is the near one.
    recs = [_debit_rec(_bull_legs())]
    out, census = ffl.diag_target_records(recs, _diag_idx())
    assert census["rows"] == 1 and census["targeted"] == 1
    assert {(r["expiration"], r["strike"], r["opt_type"], r["category"]) for r in out} == {
        (date(2024, 6, 14), 115.0, "C", "fin_diag_call"),
        (date(2024, 6, 14), 120.0, "C", "fin_diag_call"),
        (date(2024, 6, 14), 125.0, "C", "fin_diag_call"),
    }


def test_diag_target_records_targets_a_bear_row_below_its_outer_strike(_fixed_entry_day):
    recs = [_debit_rec(_bear_legs())]
    out, census = ffl.diag_target_records(recs, _diag_idx())
    assert census["targeted"] == 1
    assert [r["strike"] for r in out] == [80.0, 85.0]      # sorted output
    assert {r["category"] for r in out} == {"fin_diag_put"}
    assert all(r["expiration"] == date(2024, 6, 14) for r in out)


def test_diag_target_records_counts_no_near_expiry_and_targets_nothing(_fixed_entry_day):
    """The registered `no_near_expiry` exclusion: a debit whose whole window
    falls between two cached expiries is counted, not served a nearby expiry."""
    idx = {("AAA", date(2024, 8, 16)): {k: {"C"} for k in DIAG_LADDER}}
    out, census = ffl.diag_target_records([_debit_rec(_bull_legs())], idx)
    assert out == []
    assert census["no_near_expiry"] == 1 and census["targeted"] == 0


def test_diag_target_records_counts_a_row_with_no_ladder_beyond_the_outer(_fixed_entry_day):
    idx = _diag_idx(strikes=(90.0, 100.0, 110.0))          # nothing above 110
    out, census = ffl.diag_target_records([_debit_rec(_bull_legs())], idx)
    assert out == []
    assert census["no_ladder_beyond"] == 1 and census["targeted"] == 0


def test_diag_target_records_skips_credit_and_non_vertical_rows(_fixed_entry_day):
    """The population is `financed_spread.population` — two-leg single-expiry
    DEBIT verticals only — so the scrape targets exactly what the study can
    build on."""
    credit = _debit_rec(_bull_legs())
    credit["credit"] = True
    naked = _debit_rec([Leg(1, "AAA", date(2024, 8, 16), 100.0, "Call")])
    out, census = ffl.diag_target_records([credit, naked], _diag_idx())
    assert out == []
    assert census["rows"] == 0


def test_diag_target_records_dedupes_two_rows_owed_the_same_contract(_fixed_entry_day):
    recs = [_debit_rec(_bull_legs()), _debit_rec(_bull_legs())]
    out, census = ffl.diag_target_records(recs, _diag_idx())
    keys = [(r["ticker"], r["expiration"], r["strike"], r["opt_type"]) for r in out]
    assert census["rows"] == 2 and census["targeted"] == 2
    assert len(keys) == len(set(keys))


def test_diag_target_records_are_sorted_and_manifest_shaped(_fixed_entry_day):
    out, _ = ffl.diag_target_records([_debit_rec(_bull_legs())], _diag_idx())
    assert out == sorted(out, key=lambda r: (r["ticker"], r["expiration"],
                                             r["strike"], r["opt_type"]))
    row = ffl._row_from_target(out[0])
    assert row["category"] == "fin_diag_call" and row["status"] == "pending"


def test_diag_targets_reuse_the_vertical_cache_presence_split(_fixed_entry_day):
    """`split_cached` is category-agnostic: a fin_diag target already in the
    cache is counted, not re-fetched."""
    idx = _diag_idx()
    out, _ = ffl.diag_target_records([_debit_rec(_bull_legs())], idx)
    cached, missing = ffl.split_cached(out, idx)
    assert len(cached) == len(out) and missing == []   # _diag_idx caches C and P


def test_near_expiry_rule_is_imported_from_the_study_not_reimplemented():
    """One encoding of the frozen window: the collector imports the study's
    `near_expiry_for` so the scrape and the construction cannot drift apart."""
    from scripts.backtest_study.f3_structure import financed_spread as FS
    assert ffl.near_expiry_for is FS.near_expiry_for
    assert ffl.DIAG_N_CANDIDATES == FS.DIAG_N_CANDIDATES


# --- --category: one arm's targets per run ----------------------------------------

def test_wanted_rows_selects_only_the_named_categories():
    """The manifest is shared across arms. A closed arm's leftover pending rows
    must not eat the live arm's fetch budget — and the filter SELECTS, it never
    rewrites or drops a row."""
    rows = {}
    for strike, cat in ((100.0, "fin_call_above"), (105.0, "fin_diag_call"),
                        (110.0, "fin_diag_put")):
        k, r = _pending_row(strike=strike, category=cat)
        rows[k] = r
    assert len(ffl.wanted_rows(rows)) == 3
    picked = ffl.wanted_rows(rows, categories={"fin_diag_call", "fin_diag_put"})
    assert {rows[k]["category"] for k in picked} == {"fin_diag_call", "fin_diag_put"}
    assert len(rows) == 3          # nothing dropped from the manifest itself


def test_wanted_rows_category_filter_composes_with_retry_failed():
    k1, r1 = _pending_row(strike=100.0, category="fin_diag_call")
    r1["status"] = "failed"
    k2, r2 = _pending_row(strike=101.0, category="fin_call_above")
    r2["status"] = "failed"
    rows = {k1: r1, k2: r2}
    assert ffl.wanted_rows(rows, categories={"fin_diag_call"}) == []
    assert ffl.wanted_rows(rows, retry_failed=True,
                           categories={"fin_diag_call"}) == [k1]


def test_run_fetch_category_filter_leaves_other_categories_pending(tmp_path, _isolate):
    k1, r1 = _pending_row(strike=100.0, category="fin_diag_call")
    k2, r2 = _pending_row(strike=101.0, category="fin_call_above")
    rows = {k1: r1, k2: r2}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(ffl.run_fetch(rows, manifest, sleep_s=0, session=_Session(),
                               categories={"fin_diag_call"}))
    assert stats.get("fetched") == 1
    assert rows[k1]["status"] == "fetched"
    assert rows[k2]["status"] == "pending"
