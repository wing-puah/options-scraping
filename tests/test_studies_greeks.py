"""Tests for `scripts.backtest_study.lib.greeks` -- the shared per-leg Greeks
reader over the cached option-history CSVs.

Fixture cache CSVs are written under `tmp_path` with the same header
`lib/barchart/options.py` documents (`Time,Open,High,Low,Latest,Change,
%Change,Volume,Open Int,IV,Delta,Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask`),
named via the real `cache_path()` so the module under test reads them exactly
the way it reads the real cache. `greeks.HISTORY_CACHE` is monkeypatched to
the fixture directory -- the same pattern `tests/test_backtest_proxy.py`
uses for `proxy.HISTORY_CACHE`.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from lib.barchart.options import cache_path  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.lib import greeks  # noqa: E402

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,"
         "Delta,Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")

D1 = date(2025, 1, 6)
D2 = date(2025, 1, 7)


def _row(t, delta="", gamma="", theta="", vega=""):
    """One data row. Open/High/Low/Latest/Bid/Ask filled with plausible
    filler so `_mark`/`Open` parsing (unused by these tests) never explodes;
    the greek columns are the ones under test."""
    return (f"{t},1.00,1.10,0.90,1.05,0.05,5.0%,10,100,30.0,"
           f"{delta},{gamma},{theta},{vega},0.01,1.02,50.00,1.00,1.10")


def _write_cache(cache_dir: Path, ticker, expiration, strike, opt_type, rows: list[str]):
    path = cache_path(cache_dir, ticker, expiration, strike, opt_type)
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n")


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    d = tmp_path / "option_history_cache"
    d.mkdir()
    monkeypatch.setattr(greeks, "HISTORY_CACHE", d)
    return d


EXP = date(2025, 2, 21)


# ── leg_greek ────────────────────────────────────────────────────────────────

def test_leg_greek_long_call_delta(cache_dir):
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45", vega="0.12")])
    leg = Leg(qty=2, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call")
    assert greeks.leg_greek(leg, D1, "Delta") == pytest.approx(0.90)  # 2 * 0.45
    assert greeks.leg_greek(leg, D1, "Vega") == pytest.approx(0.24)   # 2 * 0.12


def test_leg_greek_short_leg_is_negated_and_scaled_by_abs_qty(cache_dir):
    _write_cache(cache_dir, "AAA", EXP, 110.0, "Call",
                [_row(D1.isoformat(), delta="0.30")])
    leg = Leg(qty=-3, ticker="AAA", expiration=EXP, strike=110.0, opt_type="Call")
    # sign = -1 (short), scaled by abs(qty)=3 -> -0.90, same as qty * raw.
    assert greeks.leg_greek(leg, D1, "Delta") == pytest.approx(-0.90)


def test_leg_greek_missing_cache_file_returns_none_not_raise(cache_dir):
    leg = Leg(qty=1, ticker="ZZZ", expiration=EXP, strike=999.0, opt_type="Put")
    assert greeks.leg_greek(leg, D1, "Delta") is None


def test_leg_greek_missing_day_returns_none(cache_dir):
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45")])
    leg = Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call")
    assert greeks.leg_greek(leg, D2, "Delta") is None


def test_leg_greek_missing_field_returns_none(cache_dir):
    # Row present for D1, but Delta cell itself is blank (a Barchart "-" sentinel
    # or empty cell in real data).
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="-", vega="0.12")])
    leg = Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call")
    assert greeks.leg_greek(leg, D1, "Delta") is None
    assert greeks.leg_greek(leg, D1, "Vega") == pytest.approx(0.12)


# ── entry_greeks ─────────────────────────────────────────────────────────────

def test_entry_greeks_signed_summation_long_and_short(cache_dir):
    # Long call at 100 (delta 0.45) + short call at 110 (delta 0.30, qty -1)
    # -> net delta = 0.45 - 0.30 = 0.15.
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45", vega="0.20")])
    _write_cache(cache_dir, "AAA", EXP, 110.0, "Call",
                [_row(D1.isoformat(), delta="0.30", vega="0.15")])
    legs = [
        Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call"),
        Leg(qty=-1, ticker="AAA", expiration=EXP, strike=110.0, opt_type="Call"),
    ]
    out = greeks.entry_greeks(legs, D1)
    assert out["delta"] == pytest.approx(0.15)
    assert out["vega"] == pytest.approx(0.05)  # 0.20 - 0.15
    # Gamma/Theta columns are blank in the fixture -> None per-greek, not a
    # partial/omitted sum.
    assert out["gamma"] is None
    assert out["theta"] is None


def test_entry_greeks_abs_qty_scaling(cache_dir):
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.50")])
    legs = [Leg(qty=4, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call")]
    assert greeks.entry_greeks(legs, D1)["delta"] == pytest.approx(2.0)


def test_entry_greeks_missing_leg_is_none_never_partial_sum(cache_dir):
    # One leg cached, the other's cache file is entirely absent.
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45")])
    legs = [
        Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call"),
        Leg(qty=-1, ticker="AAA", expiration=EXP, strike=105.0, opt_type="Call"),
    ]
    out = greeks.entry_greeks(legs, D1)
    assert out["delta"] is None
    assert out["gamma"] is None


def test_entry_greeks_missing_single_field_isolates_that_greek(cache_dir):
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45", gamma="", theta="-0.02", vega="0.10")])
    legs = [Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call")]
    out = greeks.entry_greeks(legs, D1)
    assert out["delta"] == pytest.approx(0.45)
    assert out["theta"] == pytest.approx(-0.02)
    assert out["vega"] == pytest.approx(0.10)
    assert out["gamma"] is None


# ── delta_agreement ──────────────────────────────────────────────────────────

class _FakeTrade:
    def __init__(self, legs, grid):
        self.legs = legs
        self.grid = grid


def test_delta_agreement_agreeing_case(cache_dir):
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45")])
    _write_cache(cache_dir, "AAA", EXP, 110.0, "Call",
                [_row(D1.isoformat(), delta="0.30")])
    legs = [
        Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call"),
        Leg(qty=-1, ticker="AAA", expiration=EXP, strike=110.0, opt_type="Call"),
    ]
    t = _FakeTrade(legs, grid=[D1, D2])
    rec = {"t": t, "delta": 0.15}
    agreement = greeks.delta_agreement(rec)
    assert agreement == pytest.approx(0.0)


def test_delta_agreement_disagreeing_case(cache_dir):
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45")])
    _write_cache(cache_dir, "AAA", EXP, 110.0, "Call",
                [_row(D1.isoformat(), delta="0.30")])
    legs = [
        Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call"),
        Leg(qty=-1, ticker="AAA", expiration=EXP, strike=110.0, opt_type="Call"),
    ]
    t = _FakeTrade(legs, grid=[D1, D2])
    rec = {"t": t, "delta": 0.50}  # stored delta far from the leg-sum (0.15)
    agreement = greeks.delta_agreement(rec)
    assert agreement == pytest.approx(0.35)


def test_delta_agreement_uses_first_common_grid_day(cache_dir):
    # Leg A cached from D1; leg B only cached from D2 -- the common entry day
    # is D2, not D1, and the stored delta must be compared there.
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45"), _row(D2.isoformat(), delta="0.40")])
    _write_cache(cache_dir, "AAA", EXP, 110.0, "Call",
                [_row(D2.isoformat(), delta="0.25")])
    legs = [
        Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call"),
        Leg(qty=-1, ticker="AAA", expiration=EXP, strike=110.0, opt_type="Call"),
    ]
    t = _FakeTrade(legs, grid=[D1, D2])
    rec = {"t": t, "delta": 0.15}  # 0.40 - 0.25, measured at D2
    assert greeks.delta_agreement(rec) == pytest.approx(0.0)


def test_delta_agreement_missing_stored_delta_returns_none(cache_dir):
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45")])
    legs = [Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call")]
    t = _FakeTrade(legs, grid=[D1])
    rec = {"t": t, "delta": None}
    assert greeks.delta_agreement(rec) is None


def test_delta_agreement_no_common_entry_day_returns_none(cache_dir):
    # Leg B is never cached at all -- no grid day has every leg present.
    _write_cache(cache_dir, "AAA", EXP, 100.0, "Call",
                [_row(D1.isoformat(), delta="0.45")])
    legs = [
        Leg(qty=1, ticker="AAA", expiration=EXP, strike=100.0, opt_type="Call"),
        Leg(qty=-1, ticker="AAA", expiration=EXP, strike=110.0, opt_type="Call"),
    ]
    t = _FakeTrade(legs, grid=[D1, D2])
    rec = {"t": t, "delta": 0.15}
    assert greeks.delta_agreement(rec) is None


def test_zero_iv_sentinel_row_reads_as_missing(cache_dir):
    """Barchart sentinel sessions carry IV=0 with every greek literally 0
    while the mark is real (e.g. COIN 255P on 2026-03-19, mark $53.25);
    leg_greek must return None (never 0.0) on such a row, and entry_greeks
    must go all-or-nothing None with it."""
    sentinel = (f"{D2.isoformat()},53.00,53.50,52.90,53.25,0.05,0.1%,10,100,0,"
                "0,0,0,0,0,0,50.00,53.00,53.50")
    _write_cache(cache_dir, "AAA", EXP, 255.0, "Put",
                 [_row(D1.isoformat(), delta="-0.9639", vega="0.02"), sentinel])
    leg = Leg(qty=-1, ticker="AAA", expiration=EXP, strike=255.0, opt_type="Put")
    assert greeks.leg_greek(leg, D2, "Delta") is None
    assert greeks.leg_greek(leg, D1, "Delta") is not None
    net = greeks.entry_greeks([leg], D2)
    assert all(v is None for v in net.values())
