"""Unit tests for `scripts/collector/fetch_sweep_legs.py`.

Covers the pure target-derivation rules (which put_calendar / put_diagonal /
condor_wing contracts a synthetic cache/book pair implies are missing,
including the "never invent a strike/expiry that isn't already evidenced in
the cache" rule), the manifest's resume semantics (fetched/failed rows are
never clobbered, --limit is honored, a crash-mid-run leaves a manifest a
later run can pick back up from), and the cache filename convention that is
the entire integration with the existing pricing path.

Everything is synthetic and written to tmp_path; no network, no real cache.
"""
import asyncio
from datetime import date, timedelta

import pytest

from lib.barchart.options import cache_path
from scripts.backtest.legs import Leg
from scripts.collector import fetch_sweep_legs as fsl

E1 = date(2024, 6, 21)   # near expiry
E2 = date(2024, 7, 19)   # far expiry
E3 = date(2024, 8, 16)   # further-out expiry (used to test "next" selection)

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
          "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")


def _history_csv(days) -> str:
    rows = [HEADER]
    for d in days:
        rows.append(f"{d.isoformat()},1.0,1.1,0.9,1.0,0,0%,10,5,,,,,,,,100,0.95,1.05")
    return "\n".join(rows) + "\n"


class _FakeTrade:
    """Stand-in for `harness.Trade`: only `.legs` and `.row` are touched by
    `entered_groups`, so a real Trade (which needs a full BacktestResults row)
    would be pure overhead here."""
    def __init__(self, legs, entry_underlying):
        self.legs = legs
        self.row = {"entry_underlying": str(entry_underlying)}


def _rec(legs, spot):
    return {"t": _FakeTrade(legs, spot)}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    cache = tmp_path / "opt_cache"
    cache.mkdir()
    monkeypatch.setattr(fsl, "HISTORY_CACHE", cache)
    yield cache


# --- entered_groups -----------------------------------------------------------

def test_entered_groups_reads_ticker_expiry_spot_off_legs():
    legs = [Leg(1, "AAA", E1, 100.0, "Call"), Leg(-1, "AAA", E1, 105.0, "Call")]
    groups = fsl.entered_groups([_rec(legs, 101.5)])
    assert groups == {("AAA", E1): 101.5}


def test_entered_groups_skips_missing_or_nonpositive_spot():
    legs = [Leg(1, "AAA", E1, 100.0, "Call")]
    assert fsl.entered_groups([_rec(legs, "")]) == {}
    assert fsl.entered_groups([_rec(legs, "0")]) == {}
    assert fsl.entered_groups([{"t": _FakeTrade(legs, None)}]) == {}


def test_entered_groups_takes_the_median_spot_across_records():
    legs = [Leg(1, "AAA", E1, 100.0, "Call")]
    groups = fsl.entered_groups([_rec(legs, 100.0), _rec(legs, 110.0), _rec(legs, 90.0)])
    assert groups[("AAA", E1)] == 100.0


def test_entered_groups_each_leg_expiration_is_its_own_group():
    """A record with legs at two expirations (e.g. an already-entered calendar)
    contributes BOTH expirations as independent anchors, per the task spec."""
    legs = [Leg(-1, "AAA", E1, 100.0, "Call"), Leg(1, "AAA", E2, 100.0, "Call")]
    groups = fsl.entered_groups([_rec(legs, 100.0)])
    assert set(groups) == {("AAA", E1), ("AAA", E2)}


# --- K* selection ---------------------------------------------------------------

def test_k_star_prefers_a_paired_strike_over_a_wider_call_only_strike():
    idx = {("AAA", E1): {95.0: {"C", "P"}, 101.0: {"C"}}}
    assert fsl._k_star(idx, "AAA", E1, 100.0) == 95.0


def test_k_star_falls_back_to_any_cached_strike_when_no_pair_exists():
    idx = {("AAA", E1): {90.0: {"C"}, 110.0: {"P"}}}
    assert fsl._k_star(idx, "AAA", E1, 100.0) == 90.0


def test_k_star_is_none_when_nothing_cached_for_the_expiry():
    assert fsl._k_star({}, "AAA", E1, 100.0) is None


# --- put_calendar -----------------------------------------------------------------

def test_put_calendar_targets_missing_near_and_far_put_at_k_star():
    idx = {
        ("AAA", E1): {100.0: {"C"}},              # near: call cached, put missing
        ("AAA", E2): {100.0: {"C"}},               # far: call cached (evidence), put missing
    }
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    calendar = [r for r in out if r["category"] == "put_calendar"]
    assert {(r["expiration"], r["strike"], r["opt_type"]) for r in calendar} == {
        (E1, 100.0, "P"), (E2, 100.0, "P")}


def test_put_calendar_no_target_when_already_fully_cached():
    idx = {
        ("AAA", E1): {100.0: {"C", "P"}},
        ("AAA", E2): {100.0: {"C", "P"}},
    }
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    assert [r for r in out if r["category"] == "put_calendar"] == []


def test_put_calendar_skips_far_leg_when_no_later_call_expiry_exists():
    """The never-invent rule: with no later expiry evidencing a call at K*,
    nothing about the far leg (or the near leg, which only matters as half of
    a calendar) may be targeted."""
    idx = {("AAA", E1): {100.0: {"C"}}}   # no E2/E3 at all
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    assert [r for r in out if r["category"] == "put_calendar"] == []


def test_put_calendar_uses_the_first_later_expiry_with_a_call_at_k_star():
    """E2 has no call at K* (100) — only E3 does — so the far leg must be E3,
    not E2, even though E2 is chronologically first."""
    idx = {
        ("AAA", E1): {100.0: {"C"}},
        ("AAA", E2): {90.0: {"C", "P"}},     # no strike 100 at all here
        ("AAA", E3): {100.0: {"C"}},
    }
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    calendar = [r for r in out if r["category"] == "put_calendar"]
    assert {(r["expiration"], r["strike"]) for r in calendar} == {(E1, 100.0), (E3, 100.0)}


# --- put_diagonal -----------------------------------------------------------------

def test_put_diagonal_targets_put_at_nearest_below_strike_with_call_but_no_put():
    idx = {
        ("AAA", E1): {100.0: {"C"}},
        ("AAA", E2): {100.0: {"C"}, 95.0: {"C"}},   # 95 below K*: call cached, put missing
    }
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    diag = [r for r in out if r["category"] == "put_diagonal"]
    assert diag == [dict(ticker="AAA", expiration=E2, strike=95.0, opt_type="P",
                         category="put_diagonal")]


def test_put_diagonal_no_target_when_below_strike_already_has_a_put():
    idx = {
        ("AAA", E1): {100.0: {"C"}},
        ("AAA", E2): {100.0: {"C"}, 95.0: {"C", "P"}},
    }
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    assert [r for r in out if r["category"] == "put_diagonal"] == []


def test_put_diagonal_never_invents_a_strike_below_k_star():
    """No strike below K* is cached at the far expiry at all -> nothing to
    anchor a diagonal far leg on, so no target (not even a guess strike)."""
    idx = {
        ("AAA", E1): {100.0: {"C"}},
        ("AAA", E2): {100.0: {"C"}},   # nothing below 100
    }
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    assert [r for r in out if r["category"] == "put_diagonal"] == []


# --- condor_wing -----------------------------------------------------------------

def test_condor_wing_targets_the_missing_side_at_nearest_above_and_below():
    idx = {("AAA", E1): {
        100.0: {"C", "P"},   # K*
        105.0: {"C"},        # nearest above: put missing
        95.0: {"P"},         # nearest below: call missing
        110.0: {"C", "P"},   # further above -> not the nearest, ignored
    }}
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    wings = {(r["strike"], r["opt_type"]) for r in out if r["category"] == "condor_wing"}
    assert wings == {(105.0, "P"), (95.0, "C")}


def test_condor_wing_no_target_when_wing_strikes_already_fully_cached():
    idx = {("AAA", E1): {100.0: {"C", "P"}, 105.0: {"C", "P"}, 95.0: {"C", "P"}}}
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    assert [r for r in out if r["category"] == "condor_wing"] == []


def test_condor_wing_never_invents_a_wing_strike_with_no_cache_at_all():
    """Only K* is cached; there is no strike above or below on the chain at
    all, so no wing target is emitted (nothing to anchor it on)."""
    idx = {("AAA", E1): {100.0: {"C", "P"}}}
    out = fsl._targets_for_group("AAA", E1, 100.0, idx)
    assert [r for r in out if r["category"] == "condor_wing"] == []


# --- group-level: nothing cached at all -----------------------------------------

def test_no_cache_at_all_for_the_expiry_yields_no_targets():
    assert fsl._targets_for_group("AAA", E1, 100.0, {}) == []


# --- sweep_target_records / sweep_targets ---------------------------------------

def test_sweep_target_records_dedupes_across_overlapping_groups():
    """Two different (ticker, near_expiry) anchors both derive the SAME far
    put_calendar target — it must appear once, keeping the first category
    seen."""
    idx = {
        ("AAA", E1): {100.0: {"C"}},
        ("AAA", E2): {100.0: {"C"}},
    }
    legs1 = [Leg(1, "AAA", E1, 100.0, "Call")]
    legs2 = [Leg(1, "AAA", E2, 100.0, "Call")]
    records = [_rec(legs1, 100.0), _rec(legs2, 100.0)]
    recs = fsl.sweep_target_records(records, idx)
    keys = [(r["ticker"], r["expiration"], r["strike"], r["opt_type"]) for r in recs]
    assert len(keys) == len(set(keys))
    assert ("AAA", E2, 100.0, "P") in keys


def test_sweep_targets_returns_sorted_plain_tuples():
    idx = {("AAA", E1): {100.0: {"C"}}, ("AAA", E2): {100.0: {"C"}}}
    legs = [Leg(1, "AAA", E1, 100.0, "Call")]
    out = fsl.sweep_targets([_rec(legs, 100.0)], idx)
    assert out == sorted(out)
    assert all(isinstance(t, tuple) and len(t) == 4 for t in out)
    assert ("AAA", E1, 100.0, "P") in out


# --- cache filename convention ---------------------------------------------------

def test_contract_path_matches_the_backtest_cache_convention(_isolate):
    target = ("AAA", E1, 100.0, "C")
    assert fsl.contract_path(target) == cache_path(_isolate, "AAA", E1, 100.0, "Call")
    assert fsl.contract_path(target).name == "AAA_20240621_100.00C.csv"


# --- manifest: round trip + merge semantics --------------------------------------

def test_manifest_round_trip(tmp_path):
    path = tmp_path / "legs_manifest.csv"
    rows = {fsl._key("AAA", E1, 100.0, "C"): dict(
        ticker="AAA", expiration=E1.isoformat(), strike="100.00", opt_type="C",
        category="condor_wing", status="pending", fetched_at="", reason="")}
    fsl.write_manifest(path, rows)
    loaded = fsl.load_manifest(path)
    assert loaded == rows


def test_merge_manifest_adds_new_targets_as_pending():
    target = dict(ticker="AAA", expiration=E1, strike=100.0, opt_type="C", category="condor_wing")
    merged = fsl.merge_manifest({}, [target])
    row = merged[fsl._key("AAA", E1, 100.0, "C")]
    assert row["status"] == "pending" and row["category"] == "condor_wing"


def test_merge_manifest_never_clobbers_fetched_or_failed_rows():
    key = fsl._key("AAA", E1, 100.0, "C")
    existing = {key: dict(ticker="AAA", expiration=E1.isoformat(), strike="100.00",
                          opt_type="C", category="condor_wing", status="fetched",
                          fetched_at="2026-08-13T00:00:00+00:00", reason="")}
    target = dict(ticker="AAA", expiration=E1, strike=100.0, opt_type="C", category="condor_wing")
    merged = fsl.merge_manifest(existing, [target])
    assert merged[key]["status"] == "fetched"
    assert merged[key]["fetched_at"] == "2026-08-13T00:00:00+00:00"

    existing[key]["status"] = "failed"
    existing[key]["reason"] = "no data"
    merged = fsl.merge_manifest(existing, [target])
    assert merged[key]["status"] == "failed" and merged[key]["reason"] == "no data"


def test_merge_manifest_refreshes_an_existing_pending_row():
    key = fsl._key("AAA", E1, 100.0, "C")
    existing = {key: dict(ticker="AAA", expiration=E1.isoformat(), strike="100.00",
                          opt_type="C", category="put_calendar", status="pending",
                          fetched_at="", reason="")}
    target = dict(ticker="AAA", expiration=E1, strike=100.0, opt_type="C", category="condor_wing")
    merged = fsl.merge_manifest(existing, [target])
    assert merged[key]["category"] == "condor_wing"
    assert merged[key]["status"] == "pending"


def test_sync_cache_status_marks_fetched_without_a_request(_isolate):
    key = fsl._key("AAA", E1, 100.0, "C")
    rows = {key: dict(ticker="AAA", expiration=E1.isoformat(), strike="100.00",
                      opt_type="C", category="condor_wing", status="pending",
                      fetched_at="", reason="")}
    fsl.contract_path(("AAA", E1, 100.0, "C")).write_text(_history_csv([E1]))
    n = fsl.sync_cache_status(rows)
    assert n == 1
    assert rows[key]["status"] == "fetched"


def test_sync_cache_status_leaves_uncached_rows_pending(_isolate):
    key = fsl._key("AAA", E1, 100.0, "C")
    rows = {key: dict(ticker="AAA", expiration=E1.isoformat(), strike="100.00",
                      opt_type="C", category="condor_wing", status="pending",
                      fetched_at="", reason="")}
    n = fsl.sync_cache_status(rows)
    assert n == 0
    assert rows[key]["status"] == "pending"


# --- run_fetch: the resumable scrape loop -----------------------------------------

def _run(coro):
    """Drive a coroutine to completion (repo convention; pytest-asyncio isn't
    configured here — same helper as test_counterpart_history.py)."""
    return asyncio.new_event_loop().run_until_complete(coro)


def _pending_row(ticker="AAA", exp=E1, strike=100.0, cp="C", category="condor_wing"):
    key = fsl._key(ticker, exp, strike, cp)
    row = dict(ticker=ticker, expiration=exp.isoformat(), strike=f"{strike:.2f}",
              opt_type=cp, category=category, status="pending", fetched_at="", reason="")
    return key, row


def test_run_fetch_writes_the_file_and_marks_the_row_fetched(tmp_path, _isolate):
    key, row = _pending_row()
    rows = {key: row}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            assert "AAA" in url and "100.00C" in url
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(fsl.run_fetch(rows, manifest, sleep_s=0, session=_Session()))
    assert stats.get("fetched") == 1
    assert rows[key]["status"] == "fetched" and rows[key]["fetched_at"]
    assert fsl.contract_path(fsl.target_of_row(rows[key])).exists()
    # flushed to disk, not just held in memory
    assert fsl.load_manifest(manifest)[key]["status"] == "fetched"


def test_run_fetch_marks_failed_on_no_data_and_writes_nothing(tmp_path, _isolate):
    key, row = _pending_row()
    rows = {key: row}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return None

    stats = _run(fsl.run_fetch(rows, manifest, sleep_s=0, session=_Session()))
    assert stats.get("failed") == 1
    assert rows[key]["status"] == "failed" and rows[key]["reason"]
    assert not fsl.contract_path(fsl.target_of_row(rows[key])).exists()


def test_run_fetch_never_traded_contract_is_marked_failed_not_written(tmp_path, _isolate):
    key, row = _pending_row()
    rows = {key: row}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return HEADER + "\n"   # header only, zero bars

    stats = _run(fsl.run_fetch(rows, manifest, sleep_s=0, session=_Session()))
    assert stats.get("no_bars") == 1
    assert rows[key]["status"] == "failed"
    assert not fsl.contract_path(fsl.target_of_row(rows[key])).exists()


def test_run_fetch_honors_limit(tmp_path, _isolate):
    rows = {}
    for i, strike in enumerate((100.0, 101.0, 102.0)):
        k, r = _pending_row(strike=strike)
        rows[k] = r
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(fsl.run_fetch(rows, manifest, limit=2, sleep_s=0, session=_Session()))
    fetched = sum(1 for r in rows.values() if r["status"] == "fetched")
    assert fetched == 2
    assert stats.get("fetched") == 2
    still_pending = sum(1 for r in rows.values() if r["status"] == "pending")
    assert still_pending == 1


def test_run_fetch_skip_existing_before_the_loop_costs_no_request(tmp_path, _isolate):
    """A file already on disk when `run_fetch` starts is resolved by the
    upfront `sync_cache_status` sweep — it never even enters the pending
    list, let alone consumes a `--limit` slot."""
    key, row = _pending_row(strike=100.0)
    key2, row2 = _pending_row(strike=101.0)
    rows = {key: row, key2: row2}
    manifest = tmp_path / "manifest.csv"
    fsl.contract_path(fsl.target_of_row(row)).write_text(
        _history_csv([E1, E1 - timedelta(days=1)]))

    calls = []

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            calls.append(url)
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(fsl.run_fetch(rows, manifest, limit=1, sleep_s=0, session=_Session()))
    assert rows[key]["status"] == "fetched"     # resolved via the upfront sync
    assert rows[key2]["status"] == "fetched"    # the ONE real attempt limit=1 allowed
    assert len(calls) == 1
    assert stats.get("fetched") == 1


def test_run_fetch_skip_existing_mid_run_costs_no_request_or_limit_budget(tmp_path, _isolate):
    """A file that appears WHILE the loop is running (e.g. another process
    fetching under the same cache convention) is caught by the per-row
    existence check right before the fetch — no second request, no limit
    spend, and the row still ends up `fetched`."""
    key, row = _pending_row(strike=100.0)
    key2, row2 = _pending_row(strike=101.0)
    rows = {key: row, key2: row2}
    manifest = tmp_path / "manifest.csv"
    calls = []

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            calls.append(url)
            # Simulate target2's file landing concurrently, after this run's
            # upfront sync already ran and found nothing.
            fsl.contract_path(fsl.target_of_row(row2)).write_text(
                _history_csv([E1, E1 - timedelta(days=1)]))
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(fsl.run_fetch(rows, manifest, sleep_s=0, session=_Session()))
    assert rows[key]["status"] == "fetched"
    assert rows[key2]["status"] == "fetched"
    assert len(calls) == 1   # only ONE real request; target2 resolved via skip-existing
    assert stats.get("skip_existing") == 1
    assert stats.get("fetched") == 1


def test_run_fetch_retries_failed_rows_only_when_flag_set(tmp_path, _isolate):
    key, row = _pending_row()
    row["status"], row["reason"] = "failed", "no data"
    rows = {key: row}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return _history_csv([E1, E1 - timedelta(days=1)])

    stats = _run(fsl.run_fetch(dict(rows), manifest, sleep_s=0, session=_Session()))
    assert stats.get("fetched") is None
    assert rows[key]["status"] == "failed"

    stats = _run(fsl.run_fetch(rows, manifest, retry_failed=True, sleep_s=0, session=_Session()))
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
    fsl.write_manifest(manifest, rows)

    seen_urls = []

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            seen_urls.append(url)
            return _history_csv([E1, E1 - timedelta(days=1)])

    # "Run 1": only gets through one contract before being cut off (limit=1
    # stands in for an interruption after the first flush).
    rows1 = fsl.load_manifest(manifest)
    _run(fsl.run_fetch(rows1, manifest, limit=1, sleep_s=0, session=_Session()))
    on_disk = fsl.load_manifest(manifest)
    assert sum(1 for r in on_disk.values() if r["status"] == "fetched") == 1

    # "Run 2": fresh process, reloads the manifest fetch left behind, and
    # finishes the rest without re-touching the already-fetched contract.
    rows2 = fsl.load_manifest(manifest)
    _run(fsl.run_fetch(rows2, manifest, sleep_s=0, session=_Session()))
    final = fsl.load_manifest(manifest)
    assert all(r["status"] == "fetched" for r in final.values())
    assert len(seen_urls) == 3   # one per distinct contract, never repeated
    assert len(set(seen_urls)) == 3
