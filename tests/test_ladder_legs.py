"""Unit tests for `scripts/collector/fetch_ladder_legs.py`.

Covers the pre-registered target-derivation flow (`ladder_overlay.md` /
`research/pre-registrations/f3_structure/ladder_overlay.md`'s §E and the
approved plan's §E): `core_expiries` (cached ∪ third-Friday union),
`ladder_target_records`'s per-core census and its "Call"/"Put" -> "C"/"P"
conversion at the manifest boundary, the manifest's resume semantics reused
BY IMPORT from `fetch_financing_legs.py` (never clobbering fetched/failed
rows), and that `--category` is a selection filter only.

Everything is synthetic and written to tmp_path; no network, no real cache.
"""
import asyncio
from datetime import date, timedelta

import pytest

from scripts.backtest.legs import Leg
from scripts.backtest_study.f3_structure import bear_rewrap as BR
from scripts.backtest_study.f3_structure import financed_spread as FS
from scripts.backtest_study.lib import ladder_targets as LT
from scripts.backtest_study.lib.underlying import Bar
from scripts.collector import fetch_ladder_legs as fll
from scripts.collector import fetch_financing_legs as ffl

E0 = date(2024, 6, 3)
CORE_EXP = date(2025, 6, 20)   # far out, so core_expiries/eligible windows stay open

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
          "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")


def _history_csv(days) -> str:
    rows = [HEADER]
    for d in days:
        rows.append(f"{d.isoformat()},1.0,1.1,0.9,1.0,0,0%,10,5,,,,,,,,100,0.95,1.05")
    return "\n".join(rows) + "\n"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """`ladder_targets`, `financed_spread` and `bear_rewrap` each bind their
    own `HISTORY_CACHE`; `fetch_ladder_legs` reuses `fetch_financing_legs`'s
    cache-path helpers, which bind a fourth. All four must point at the same
    tmp directory for a fetch/manifest round trip to see a written contract."""
    cache = tmp_path / "opt_cache"
    cache.mkdir()
    monkeypatch.setattr(LT, "HISTORY_CACHE", cache)
    monkeypatch.setattr(FS, "HISTORY_CACHE", cache)
    monkeypatch.setattr(BR, "HISTORY_CACHE", cache)
    monkeypatch.setattr(ffl, "HISTORY_CACHE", cache)
    # cached_ticker_expiries memoizes per ticker at module scope; every test
    # here reuses ticker "AAA" against a fresh tmp cache, so the memo must be
    # reset per test or a later test would read an earlier test's cache.
    monkeypatch.setattr(FS, "_ticker_expiries_cache", {})
    yield cache


def _write_contract(cache_dir, ticker, expiry, strike, cp):
    fname = f"{ticker}_{expiry.strftime('%Y%m%d')}_{strike:.2f}{cp}.csv"
    (cache_dir / fname).write_text("Time,Open,High,Low,Latest\n2024-06-03,1,1,1,1\n")


class _FakeTrade:
    def __init__(self, legs, grid, structure="bull_call_spread"):
        self.legs = legs
        self.grid = grid
        self.structure = structure


def _rec(legs, grid, structure="bull_call_spread"):
    return {"structure": structure, "t": _FakeTrade(legs, grid, structure)}


def _bull_legs(ticker="AAA", exp=CORE_EXP, lo=100.0, hi=110.0):
    return [Leg(1, ticker, exp, lo, "Call"), Leg(-1, ticker, exp, hi, "Call")]


def _grid(n, start=E0):
    return [start + timedelta(days=i) for i in range(n)]


@pytest.fixture()
def _fixed_entry(monkeypatch):
    monkeypatch.setattr(LT.BR, "entry_date_for", lambda legs, grid: E0)
    monkeypatch.setattr(LT, "load_bars", lambda ticker: {E0: Bar(c=105.0)})
    return E0


# --- distinct manifest path ---------------------------------------------------

def test_ladder_manifest_path_is_distinct_from_the_others():
    assert fll.MANIFEST_PATH.name == "ladder_manifest.csv"
    assert fll.MANIFEST_PATH != ffl.MANIFEST_PATH
    assert fll.MANIFEST_PATH.parent == ffl.MANIFEST_PATH.parent


# --- core_expiries: cached-set union third-Fridays ----------------------------

def test_core_expiries_unions_cached_and_third_fridays(_isolate):
    _write_contract(_isolate, "AAA", date(2024, 6, 21), 100.0, "C")   # cached expiry
    out = fll.core_expiries("AAA", E0)
    assert date(2024, 6, 21) in out           # from the cache
    assert date(2024, 7, 19) in out           # a standard third Friday, not cached
    assert out == sorted(set(out))            # deduped and sorted


def test_core_expiries_empty_ticker_still_gets_the_monthly_calendar(_isolate):
    out = fll.core_expiries("ZZZ", E0)
    assert date(2024, 6, 21) in out


# --- ladder_target_records: population / census / opt_type conversion --------

def test_ladder_target_records_only_admits_bull_call_spread_structure(_fixed_entry):
    other = _rec(_bull_legs(), _grid(400), structure="bear_put_spread")
    out, census = fll.ladder_target_records([other])
    assert out == []
    assert census["population"] == 0


def test_ladder_target_records_counts_population_and_targeted(_fixed_entry):
    recs = [_rec(_bull_legs(), _grid(400))]
    out, census = fll.ladder_target_records(recs)
    assert census["population"] == 1
    assert census["targeted"] == 1
    assert census["skip_no_core"] == 0
    assert len(out) > 0


def test_ladder_target_records_counts_skip_no_core(monkeypatch, _isolate):
    monkeypatch.setattr(LT.BR, "entry_date_for", lambda legs, grid: None)   # no common entry day
    recs = [_rec(_bull_legs(), _grid(400))]
    out, census = fll.ladder_target_records(recs)
    assert out == []
    assert census["population"] == 1
    assert census["skip_no_core"] == 1
    assert census["targeted"] == 0


def test_ladder_target_records_counts_no_eligible_expiry_but_still_targets(_fixed_entry):
    """A core with nothing eligible in its expiry window still contributes its
    unconditional ladder_put_core row and is counted `targeted`, not skipped —
    only `no_eligible_expiry` distinguishes it."""
    near_core_exp = E0 + timedelta(days=10)   # window collapses: nothing 7..5 days out
    recs = [_rec(_bull_legs(exp=near_core_exp), _grid(30))]
    out, census = fll.ladder_target_records(recs)
    assert census["no_eligible_expiry"] == 1
    assert census["targeted"] == 1
    assert [r["category"] for r in out] == ["ladder_put_core"]


def test_ladder_target_records_converts_call_put_to_single_letter_opt_type(_fixed_entry):
    recs = [_rec(_bull_legs(), _grid(400))]
    out, _census = fll.ladder_target_records(recs)
    assert out
    assert {r["opt_type"] for r in out} <= {"C", "P"}
    assert not any(r["opt_type"] in ("Call", "Put") for r in out)


def test_ladder_target_records_dedupes_across_recs_sharing_a_core(_fixed_entry):
    recs = [_rec(_bull_legs(), _grid(400)), _rec(_bull_legs(), _grid(400))]
    out, census = fll.ladder_target_records(recs)
    assert census["population"] == 2
    keys = [(r["ticker"], r["expiration"], r["strike"], r["opt_type"]) for r in out]
    assert len(keys) == len(set(keys))


def test_ladder_target_records_are_sorted_and_manifest_shaped(_fixed_entry):
    recs = [_rec(_bull_legs(), _grid(400))]
    out, _census = fll.ladder_target_records(recs)
    assert out == sorted(out, key=lambda r: (r["ticker"], r["expiration"], r["strike"], r["opt_type"]))
    row = ffl._row_from_target(out[0])
    assert row["status"] == "pending" and row["opt_type"] in ("C", "P")


# --- manifest resume semantics, reused by import ------------------------------

def test_manifest_merge_never_clobbers_fetched_or_failed_rows():
    target = dict(ticker="AAA", expiration=date(2024, 6, 21), strike=115.0,
                  opt_type="C", category="ladder_call_t0")
    key = ffl._key("AAA", date(2024, 6, 21), 115.0, "C")
    existing = {key: dict(ticker="AAA", expiration="2024-06-21", strike="115.00",
                          opt_type="C", category="ladder_call_t0", status="fetched",
                          fetched_at="2026-09-01T00:00:00+00:00", reason="")}
    merged = ffl.merge_manifest(existing, [target])
    assert merged[key]["status"] == "fetched"
    assert merged[key]["fetched_at"] == "2026-09-01T00:00:00+00:00"

    existing[key]["status"] = "failed"
    existing[key]["reason"] = "no data"
    merged = ffl.merge_manifest(existing, [target])
    assert merged[key]["status"] == "failed" and merged[key]["reason"] == "no data"


def test_manifest_merge_adds_new_ladder_targets_as_pending():
    target = dict(ticker="AAA", expiration=date(2024, 6, 21), strike=115.0,
                  opt_type="C", category="ladder_call_t0")
    merged = ffl.merge_manifest({}, [target])
    row = merged[ffl._key("AAA", date(2024, 6, 21), 115.0, "C")]
    assert row["status"] == "pending" and row["category"] == "ladder_call_t0"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _pending_row(ticker="AAA", exp=date(2024, 6, 21), strike=115.0, cp="C",
                 category="ladder_call_t0"):
    key = ffl._key(ticker, exp, strike, cp)
    row = dict(ticker=ticker, expiration=exp.isoformat(), strike=f"{strike:.2f}",
               opt_type=cp, category=category, status="pending", fetched_at="", reason="")
    return key, row


def test_run_fetch_resumes_correctly_through_the_shared_manifest_path(tmp_path, _isolate):
    """`fetch_ladder_legs.py` writes its OWN manifest file but reuses
    `fetch_financing_legs.run_fetch` unmodified — a crash/resume round trip
    must behave identically to that module's own tests."""
    key, row = _pending_row()
    rows = {key: row}
    manifest = tmp_path / "ladder_manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            assert "AAA" in url and "115.00C" in url
            return _history_csv([E0, E0 - timedelta(days=1)])

    stats = _run(ffl.run_fetch(rows, manifest, sleep_s=0, session=_Session()))
    assert stats.get("fetched") == 1
    assert rows[key]["status"] == "fetched"
    assert ffl.contract_path(ffl.target_of_row(rows[key])).exists()


# --- --category: selection only, never rewrites or drops a row ---------------

def test_wanted_rows_category_filter_selects_ladder_categories_only():
    rows = {}
    for strike, cat in ((100.0, "ladder_call_t0"), (105.0, "ladder_put_core"),
                        (110.0, "ladder_put_short")):
        k, r = _pending_row(strike=strike, category=cat)
        rows[k] = r
    picked = ffl.wanted_rows(rows, categories={"ladder_put_core"})
    assert {rows[k]["category"] for k in picked} == {"ladder_put_core"}
    assert len(rows) == 3   # nothing dropped from the manifest itself


def test_run_fetch_category_filter_leaves_other_categories_pending(tmp_path, _isolate):
    k1, r1 = _pending_row(strike=100.0, category="ladder_call_t0")
    k2, r2 = _pending_row(strike=101.0, category="ladder_put_core")
    rows = {k1: r1, k2: r2}
    manifest = tmp_path / "manifest.csv"

    class _Session:
        async def fetch_history_fast(self, url, timeout_ms):
            return _history_csv([E0, E0 - timedelta(days=1)])

    stats = _run(ffl.run_fetch(rows, manifest, sleep_s=0, session=_Session(),
                               categories={"ladder_call_t0"}))
    assert stats.get("fetched") == 1
    assert rows[k1]["status"] == "fetched"
    assert rows[k2]["status"] == "pending"
