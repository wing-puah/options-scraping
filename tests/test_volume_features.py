"""Unit tests for the volume-feature study tier.

Three things under test, all pure / mock-only — no real caches, no network:

  * `scripts/backtest_study/lib/underlying.py` — `Bar.v` (share volume), added on
    the OHLC loader path only; the `Price~` fallback never carries one.
  * `scripts/backtest_study/lib/volume_features.py` — the three as-of-entry
    volume features (`os_ratio`, `rvolz20`, `amihud20`), the split-artifact
    window cleaner, the rescaled-ticker withholding, and the tercile helpers.
  * `scripts/backtest_study/f2_management/volume_signal.py` — the study's pure population
    predicates and its one frozen exit variant (`keyed_profile`), whose leak
    guard (only non-bear debit + HIGH os_ratio may ever change) is the single
    most important property in the file.
"""
from __future__ import annotations

import math
import statistics
from datetime import date, timedelta

import pytest

from scripts.backtest_study.lib import underlying as und
from scripts.backtest_study.lib import volume_features as VF
from scripts.backtest_study.f2_management import volume_signal as VS
from scripts.backtest_study.lib.underlying import Bar, SRC_OHLC

START = date(2024, 1, 1)


def _days(n: int, start: date = START) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def _bars(closes: list[float], volumes: list[float | None] | None = None,
          source: str = SRC_OHLC) -> dict[date, Bar]:
    """`{date: Bar}` from parallel closes/volumes lists, on consecutive days."""
    if volumes is None:
        volumes = [None] * len(closes)
    return {d: Bar(c=c, v=v, source=source)
            for d, c, v in zip(_days(len(closes)), closes, volumes)}


def _alternating_closes(n: int, r: float = 0.01, start: float = 100.0) -> list[float]:
    closes, c = [start], start
    for i in range(n - 1):
        c *= math.exp(r if i % 2 == 0 else -r)
        closes.append(c)
    return closes


# 20 baseline volumes with real dispersion (a constant baseline would make
# rvolz20's stdev 0 and every test degenerate to the "no variance" case).
BASE_VOLS = [1000, 1200, 800, 1100, 900, 1050, 950, 1150, 850, 1000,
             1200, 800, 1100, 900, 1050, 950, 1150, 850, 1000, 1200]
assert len(BASE_VOLS) == 20


# ═══════════════════════════════════════════════════════════════════════════
# 1. scripts/backtest_study/lib/underlying.py — Bar.v
# ═══════════════════════════════════════════════════════════════════════════

OHLC_HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
               "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")


def _ohlc_csv(rows) -> str:
    """rows = [(date, open, high, low, close, volume|None)] -> OHLC cache CSV."""
    out = [OHLC_HEADER]
    for d, o, h, l, c, v in rows:
        vol_field = "" if v is None else str(v)
        out.append(f"{d.isoformat()},{o},{h},{l},{c},0,0%,{vol_field},0,,,,,,,,,,")
    return "\n".join(out) + "\n"


def _tilde_csv(rows) -> str:
    """rows = [(date, price_tilde)] -> an option-cache CSV carrying `Price~`."""
    out = [OHLC_HEADER]
    for d, p in rows:
        out.append(f"{d.isoformat()},1,1,1,1,0,0%,10,0,,,,,,,,{p},,")
    return "\n".join(out) + "\n"


@pytest.fixture
def _isolate_underlying_caches(tmp_path, monkeypatch):
    """Point OHLC_CACHE/HISTORY_CACHE at tmp_path and clear the lru_caches.

    Same pattern as tests/test_underlying_ohlc.py's `_isolate_caches` fixture.
    """
    ohlc = tmp_path / "ohlc"
    opts = tmp_path / "opts"
    ohlc.mkdir()
    opts.mkdir()
    monkeypatch.setattr(und, "OHLC_CACHE", ohlc)
    monkeypatch.setattr(und, "RESCALED_FILE", ohlc / "rescaled_tickers.txt")
    monkeypatch.setattr(und, "HISTORY_CACHE", opts)
    for fn in (und._load_ohlc_cache, und._load_tilde, und.rescaled_tickers):
        fn.cache_clear()
    yield ohlc, opts
    for fn in (und._load_ohlc_cache, und._load_tilde, und.rescaled_tickers):
        fn.cache_clear()


def test_ohlc_cache_parses_the_volume_column_into_bar_v(_isolate_underlying_caches):
    ohlc, _ = _isolate_underlying_caches
    (ohlc / "AAA.csv").write_text(
        _ohlc_csv([(date(2024, 3, 5), 10, 12, 9, 11, 123456)]))
    bar = und.load_bars("AAA")[date(2024, 3, 5)]
    assert bar.v == 123456.0


def test_ohlc_cache_volume_is_none_when_the_column_is_blank(_isolate_underlying_caches):
    ohlc, _ = _isolate_underlying_caches
    (ohlc / "AAA.csv").write_text(
        _ohlc_csv([(date(2024, 3, 5), 10, 12, 9, 11, None)]))
    bar = und.load_bars("AAA")[date(2024, 3, 5)]
    assert bar.v is None


@pytest.mark.parametrize("bad_volume", [0, -50])
def test_ohlc_cache_volume_is_none_when_nonpositive(_isolate_underlying_caches, bad_volume):
    ohlc, _ = _isolate_underlying_caches
    (ohlc / "AAA.csv").write_text(
        _ohlc_csv([(date(2024, 3, 5), 10, 12, 9, 11, bad_volume)]))
    bar = und.load_bars("AAA")[date(2024, 3, 5)]
    assert bar.v is None


def test_tilde_fallback_bars_never_carry_a_volume(_isolate_underlying_caches):
    """`Price~` is a quote off an option row — there is no share count to read,
    and fabricating one would silently widen volume_features' denominator."""
    _, opts = _isolate_underlying_caches
    (opts / "AAA_20240315_100.00C.csv").write_text(
        _tilde_csv([(date(2024, 3, 5), 42.0)]))
    bar = und.load_bars("AAA")[date(2024, 3, 5)]
    assert bar.source == und.SRC_TILDE
    assert bar.v is None


# ═══════════════════════════════════════════════════════════════════════════
# 2. scripts/backtest_study/lib/volume_features.py
# ═══════════════════════════════════════════════════════════════════════════

# --- os_ratio -----------------------------------------------------------------

def test_os_ratio_is_contracts_times_100_over_same_day_volume():
    bars = _bars([100.0], [10000.0])
    d = sorted(bars)[0]
    assert VF.os_ratio(bars, d, 50) == pytest.approx(50 * 100.0 / 10000.0)


def test_os_ratio_none_when_contracts_missing_or_nonpositive():
    bars = _bars([100.0], [10000.0])
    d = sorted(bars)[0]
    assert VF.os_ratio(bars, d, None) is None
    assert VF.os_ratio(bars, d, 0) is None
    assert VF.os_ratio(bars, d, -5) is None


def test_os_ratio_none_when_no_bar_on_the_exact_date():
    bars = _bars([100.0], [10000.0])
    missing_day = START + timedelta(days=99)
    assert VF.os_ratio(bars, missing_day, 10) is None


def test_os_ratio_none_when_the_bar_has_no_usable_volume():
    d = START
    assert VF.os_ratio(_bars([100.0], [None]), d, 10) is None
    assert VF.os_ratio(_bars([100.0], [0.0]), d, 10) is None
    assert VF.os_ratio(_bars([100.0], [-5.0]), d, 10) is None


# --- rvolz20 --------------------------------------------------------------------

def test_rvolz20_baseline_excludes_the_scored_day():
    """The trailing window ends the PRIOR session — the scored day's own
    volume must feed only the numerator, never the baseline mean/stdev."""
    closes = [100.0] * (len(BASE_VOLS) + 1)
    bars = _bars(closes, BASE_VOLS + [3000.0])
    as_of = sorted(bars)[-1]

    z = VF.rvolz20(bars, as_of)
    logs = [math.log(v) for v in BASE_VOLS]
    mean, sd = statistics.fmean(logs), statistics.pstdev(logs)
    assert z == pytest.approx((math.log(3000.0) - mean) / sd)

    # Swap ONLY the scored day's own volume for something wildly different.
    # If the baseline included it, mean/sd (and therefore the denominator)
    # would shift; the property under test is that they do not.
    bars_swapped = dict(bars)
    bars_swapped[as_of] = Bar(c=100.0, v=50000.0, source=SRC_OHLC)
    z2 = VF.rvolz20(bars_swapped, as_of)
    assert z2 == pytest.approx((math.log(50000.0) - mean) / sd)
    assert (z2 - z) == pytest.approx((math.log(50000.0) - math.log(3000.0)) / sd)


def test_rvolz20_none_when_the_scored_day_has_no_volume():
    closes = [100.0] * (len(BASE_VOLS) + 1)
    bars = _bars(closes, BASE_VOLS + [None])
    as_of = sorted(bars)[-1]
    assert VF.rvolz20(bars, as_of) is None


def test_rvolz20_none_below_the_minimum_baseline_observations():
    """Only 10 baseline sessions, short of `_MIN_RV_OBS` (15)."""
    vols = [1000.0] * 10 + [3000.0]
    bars = _bars([100.0] * len(vols), vols)
    as_of = sorted(bars)[-1]
    assert VF.rvolz20(bars, as_of) is None


def test_rvolz20_none_when_the_baseline_has_zero_dispersion():
    vols = [1000.0] * 20 + [3000.0]
    bars = _bars([100.0] * len(vols), vols)
    as_of = sorted(bars)[-1]
    assert VF.rvolz20(bars, as_of) is None


# --- amihud20 -------------------------------------------------------------------

def test_amihud20_matches_the_closed_form_on_alternating_prices():
    n = 21
    vol = 1_000_000.0
    closes = _alternating_closes(n, r=0.01)
    bars = _bars(closes, [vol] * n)
    as_of = sorted(bars)[-1]

    got = VF.amihud20(bars, as_of)
    ratios = [abs(math.log(cur / prev)) / (cur * vol)
              for prev, cur in zip(closes, closes[1:])]
    expected = statistics.fmean(ratios) * 1e9
    assert got == pytest.approx(expected, rel=1e-9)


def test_amihud20_none_below_the_minimum_observations():
    n = 11  # 10 return/volume pairs, short of _MIN_RV_OBS (15)
    bars = _bars([100.0] * n, [1000.0] * n)
    as_of = sorted(bars)[-1]
    assert VF.amihud20(bars, as_of) is None


# --- _clean_window (split-artifact guard) ---------------------------------------

def test_clean_window_drops_a_split_step_and_re_anchors_to_the_last_kept_close():
    """A bar following a dropped one is tested against the last KEPT close, not
    the dropped bar — otherwise a legitimate follow-on bar would cascade-drop."""
    bars_list = [
        Bar(c=100.0),   # kept: no prior close to test
        Bar(c=1000.0),  # 10x step from 100 -> dropped (artifact)
        Bar(c=101.0),   # tested against the last KEPT close (100), not 1000 -> kept
    ]
    out = VF._clean_window(bars_list)
    assert [b.c for b in out] == [100.0, 101.0]


def test_clean_window_keeps_a_series_with_no_artifacts():
    bars_list = [Bar(c=c) for c in [100.0, 101.0, 102.0, 101.5]]
    assert [b.c for b in VF._clean_window(bars_list)] == [100.0, 101.0, 102.0, 101.5]


def test_clean_window_drops_bars_with_missing_or_nonpositive_close():
    bars_list = [Bar(c=100.0), Bar(c=0.0), Bar(c=None), Bar(c=101.0)]
    assert [b.c for b in VF._clean_window(bars_list)] == [100.0, 101.0]


# --- features() aggregate --------------------------------------------------------

def test_features_withholds_window_features_for_a_rescaled_ticker_but_keeps_os_ratio(monkeypatch):
    monkeypatch.setattr(VF, "rescaled_tickers", lambda: frozenset({"AAA"}))
    bars = _bars([100.0], [10000.0])
    d = sorted(bars)[0]
    out = VF.features(bars, d, "aaa", contracts=50)
    assert out["vol_rescaled"] is True
    assert out["rvolz20"] is None and out["amihud20"] is None
    assert out["os_ratio"] == pytest.approx(50 * 100.0 / 10000.0)
    assert out["has_contracts"] is True


def test_features_computes_window_features_for_a_non_rescaled_ticker(monkeypatch):
    monkeypatch.setattr(VF, "rescaled_tickers", lambda: frozenset())
    closes = _alternating_closes(len(BASE_VOLS) + 1, r=0.01)
    bars = _bars(closes, BASE_VOLS + [3000.0])
    as_of = sorted(bars)[-1]
    out = VF.features(bars, as_of, "bbb", contracts=None)
    assert out["vol_rescaled"] is False
    assert out["rvolz20"] is not None
    assert out["amihud20"] is not None
    assert out["os_ratio"] is None       # no contracts supplied
    assert out["has_contracts"] is False


# --- terciles / tercile_of -------------------------------------------------------

def test_terciles_returns_the_one_third_two_third_cut_points():
    rows = [{"x": float(i)} for i in range(9)]
    assert VF.terciles(rows, "x") == (3.0, 6.0)


def test_terciles_none_below_three_usable_values():
    rows = [{"x": 1.0}, {"x": 2.0}]
    assert VF.terciles(rows, "x") is None


def test_terciles_ignores_none_and_nan_entries():
    rows = ([{"x": float(i)} for i in range(9)]
            + [{"x": None}] * 5 + [{"x": float("nan")}] * 5)
    assert VF.terciles(rows, "x") == (3.0, 6.0)


def test_terciles_none_when_the_boundaries_collapse():
    rows = [{"x": 1.0}] * 10
    assert VF.terciles(rows, "x") is None


def test_tercile_of_boundary_semantics():
    bounds = (3.0, 6.0)
    assert VF.tercile_of(2.999, bounds) == "LOW"
    assert VF.tercile_of(3.0, bounds) == "MID"     # value == lo -> MID
    assert VF.tercile_of(5.999, bounds) == "MID"
    assert VF.tercile_of(6.0, bounds) == "HIGH"    # value >= hi -> HIGH
    assert VF.tercile_of(100.0, bounds) == "HIGH"


def test_tercile_of_none_propagates():
    assert VF.tercile_of(None, (1.0, 2.0)) is None
    assert VF.tercile_of(5.0, None) is None
    assert VF.tercile_of(None, None) is None


# --- load_contracts() -------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_load_contracts_cache():
    """`load_contracts` is `lru_cache(maxsize=1)` with no arguments — without
    an explicit clear, the first test to call it would pin every later test's
    result regardless of AUDIT_DIR."""
    VF.load_contracts.cache_clear()
    yield
    VF.load_contracts.cache_clear()


def test_load_contracts_parses_symbol_and_contracts_from_rollup_csvs(tmp_path, monkeypatch):
    monkeypatch.setattr(VF, "AUDIT_DIR", tmp_path)
    (tmp_path / "2026-08-01-rollup.csv").write_text(
        "Symbol,Contracts\nAAPL,120\nMSFT,0\nTSLA,-5\n,50\n")
    out = VF.load_contracts()
    assert out[("2026-08-01", "AAPL")] == 120.0
    assert ("2026-08-01", "MSFT") not in out   # Contracts <= 0 excluded
    assert ("2026-08-01", "TSLA") not in out   # negative excluded
    assert len(out) == 1


def test_load_contracts_first_occurrence_in_a_file_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(VF, "AUDIT_DIR", tmp_path)
    (tmp_path / "2026-08-01-rollup.csv").write_text(
        "Symbol,Contracts\nAAPL,50\nAAPL,999\n")
    out = VF.load_contracts()
    assert out[("2026-08-01", "AAPL")] == 50.0


def test_load_contracts_empty_when_audit_dir_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(VF, "AUDIT_DIR", tmp_path / "does-not-exist")
    assert VF.load_contracts() == {}


# ═══════════════════════════════════════════════════════════════════════════
# 3. scripts/backtest_study/f2_management/volume_signal.py (pure helpers only)
# ═══════════════════════════════════════════════════════════════════════════

# --- giveback ---------------------------------------------------------------

def test_giveback_true_inside_the_subarming_window_with_a_nonpositive_r():
    assert VS.giveback({"mfe": 0.10, "R": -0.05}) is True
    assert VS.giveback({"mfe": VS.GIVEBACK_LO, "R": 0.0}) is True   # lo inclusive, R==0 counts


def test_giveback_false_outside_the_window_or_when_r_is_positive():
    assert VS.giveback({"mfe": VS.GIVEBACK_HI, "R": -0.1}) is False   # hi is exclusive
    assert VS.giveback({"mfe": 0.005, "R": -0.1}) is False            # below lo
    assert VS.giveback({"mfe": 0.10, "R": 0.01}) is False             # R positive


def test_giveback_none_when_mfe_or_r_is_missing():
    assert VS.giveback({"mfe": None, "R": -0.1}) is None
    assert VS.giveback({"mfe": 0.1, "R": None}) is None
    assert VS.giveback({}) is None


# --- population predicates ---------------------------------------------------

def test_is_bear_debit_requires_a_bear_structure_and_no_credit():
    assert VS.is_bear_debit({"structure": "bear_put_spread", "credit": False})
    assert VS.is_bear_debit({"structure": "long_put", "credit": False})
    assert not VS.is_bear_debit({"structure": "bear_put_spread", "credit": True})
    assert not VS.is_bear_debit({"structure": "bull_call_spread", "credit": False})


def test_is_nonbear_debit_excludes_credit_and_bear_structures():
    assert VS.is_nonbear_debit({"structure": "bull_call_spread", "credit": False})
    assert not VS.is_nonbear_debit({"structure": "bull_call_spread", "credit": True})
    assert not VS.is_nonbear_debit({"structure": "bear_put_spread", "credit": False})
    assert not VS.is_nonbear_debit({"structure": "long_put", "credit": False})


# --- cell_stats ----------------------------------------------------------------

def test_cell_stats_summarizes_a_small_synthetic_population():
    rows = [
        {"R": 0.5, "mfe": 0.6, "mae": -0.1, "R_dol": 500.0},
        {"R": -0.3, "mfe": 0.2, "mae": -0.4, "R_dol": -300.0},
        {"R": None, "mfe": None, "mae": None, "R_dol": None},
    ]
    s = VS.cell_stats(rows)
    assert s["n"] == 3
    assert s["mean"] == pytest.approx((0.5 - 0.3) / 2)
    assert s["win"] == pytest.approx(0.5)                    # 1 of 2 R's is > 0
    assert s["dol"] == pytest.approx(200.0)
    assert s["mfe"] == pytest.approx((0.6 + 0.2) / 2)
    assert s["mae"] == pytest.approx((-0.1 - 0.4) / 2)
    assert s["gb"] == pytest.approx(0.5)                     # row2 is a giveback, row1 is not
    cap1, cap2 = 0.5 / 0.6, -0.3 / 0.2
    assert s["cap"] == pytest.approx((cap1 + cap2) / 2)


def test_cell_stats_on_an_empty_population_is_all_none_but_zero_dollars():
    s = VS.cell_stats([])
    assert s["n"] == 0
    assert s["mean"] is None and s["win"] is None and s["dol"] == 0
    assert s["mfe"] is None and s["mae"] is None
    assert s["gb"] is None and s["cap"] is None


# --- keyed_profile: the study's leak guard --------------------------------------

BOUNDS = (1.0, 2.0)   # LOW < 1.0 <= MID < 2.0 <= HIGH


def _rec(structure="bull_call_spread", credit=False, os_ratio=5.0, mech_cell="PROD"):
    return {"structure": structure, "credit": credit, "os_ratio": os_ratio,
            "mech_cell": mech_cell}


def test_keyed_profile_sets_be_after_only_for_nonbear_debit_in_the_high_tercile():
    rec = _rec(structure="bull_call_spread", credit=False, os_ratio=5.0)   # HIGH, nonbear, debit
    base = VS.keyed_profile(rec, BOUNDS, keyed=False)
    variant = VS.keyed_profile(rec, BOUNDS, keyed=True)
    assert base.get("be_after") is None
    assert variant["be_after"] == 0.50
    assert variant != base


def test_keyed_profile_leaves_bear_debit_rows_untouched_by_the_key():
    """The leak guard: bear-debit rows are structurally excluded from the
    variant no matter their os_ratio tercile."""
    rec = _rec(structure="bear_put_spread", credit=False, os_ratio=5.0)    # HIGH, but bear
    base = VS.keyed_profile(rec, BOUNDS, keyed=False)
    variant = VS.keyed_profile(rec, BOUNDS, keyed=True)
    assert variant == base


def test_keyed_profile_leaves_credit_rows_untouched_by_the_key():
    rec = _rec(structure="bull_put_spread", credit=True, os_ratio=5.0)     # HIGH, but credit
    base = VS.keyed_profile(rec, BOUNDS, keyed=False)
    variant = VS.keyed_profile(rec, BOUNDS, keyed=True)
    assert variant == base


def test_keyed_profile_leaves_nonbear_debit_rows_untouched_outside_the_high_tercile():
    low = _rec(structure="bull_call_spread", credit=False, os_ratio=0.5)   # LOW
    mid = _rec(structure="bull_call_spread", credit=False, os_ratio=1.5)   # MID
    for rec in (low, mid):
        assert VS.keyed_profile(rec, BOUNDS, keyed=True) == \
            VS.keyed_profile(rec, BOUNDS, keyed=False)


def test_keyed_profile_leaves_rows_with_missing_os_ratio_untouched():
    rec = _rec(structure="bull_call_spread", credit=False, os_ratio=None)
    assert VS.keyed_profile(rec, BOUNDS, keyed=True) == \
        VS.keyed_profile(rec, BOUNDS, keyed=False)


def test_keyed_profile_on_bear_he_regime_still_applies_the_shipped_suppression():
    """Sanity: keyed_profile always carries the SHIPPED merge underneath the
    variant — a BEAR_HE bear-debit row keeps its be_after suppressed to None
    and picks up the regime trail, independent of the `keyed` flag."""
    rec = _rec(structure="bear_put_spread", credit=False, os_ratio=5.0, mech_cell="BEAR_HE")
    for keyed in (False, True):
        cfg = VS.keyed_profile(rec, BOUNDS, keyed=keyed)
        assert cfg["be_after"] is None
        assert cfg["trig"] == 0.50 and cfg["trail"] == 0.50
