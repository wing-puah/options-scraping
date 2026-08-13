"""Unit tests for `scripts/backtest_study/underlying_features.py`.

Bars are constructed directly rather than written to a cache and re-read — the
module takes `{date: Bar}` and does no I/O of its own except the SPY series,
which is monkeypatched. Nothing here touches the real (gitignored) caches under
backtests/ or the network.

The tests that matter most are the invariant ones: no look-ahead, OHLC-only
features staying None on the close-only path, and the units of `vrp`. Each of
those three is a silent-wrong-answer failure rather than a crash.
"""
import math
from datetime import date, timedelta

import pytest

from scripts.backtest_study import underlying_features as uf
from scripts.backtest_study.underlying import SRC_OHLC, SRC_TILDE, Bar

START = date(2024, 1, 1)
ANN = math.sqrt(252)


def _days(n: int, start: date = START) -> list[date]:
    """`n` consecutive calendar days. Weekends are irrelevant — every function
    here counts BARS, and the bar series is the calendar (see underlying.py)."""
    return [start + timedelta(days=i) for i in range(n)]


def _from_closes(closes, source=SRC_OHLC, hl=None) -> dict[date, Bar]:
    """`{date: Bar}` from a close series; `hl` = (high_add, low_sub) for OHLC bars."""
    out = {}
    for d, c in zip(_days(len(closes)), closes):
        if source == SRC_OHLC and hl is not None:
            out[d] = Bar(c=c, o=c, h=c + hl[0], l=c - hl[1], source=SRC_OHLC)
        elif source == SRC_OHLC:
            out[d] = Bar(c=c, o=c, h=c, l=c, source=SRC_OHLC)
        else:
            out[d] = Bar(c=c, source=SRC_TILDE)
    return out


def _alternating(n: int, r: float = 0.01, start: float = 100.0) -> list[float]:
    """Closes whose log returns alternate +r / -r, so pstdev(returns) == r exactly."""
    closes, c = [start], start
    for i in range(n - 1):
        c *= math.exp(r if i % 2 == 0 else -r)
        closes.append(c)
    return closes


def _monotone(n: int, r: float = 0.005, start: float = 100.0) -> list[float]:
    closes, c = [start], start
    for _ in range(n - 1):
        c *= math.exp(r)
        closes.append(c)
    return closes


# --- the no-look-ahead invariant ---------------------------------------------

def test_trailing_bars_never_reads_past_as_of():
    bars = _from_closes(list(range(100, 130)))
    days = sorted(bars)
    got = uf.trailing_bars(bars, days[10], 5)
    assert [b.c for b in got] == [106, 107, 108, 109, 110]
    assert all(b.c <= 110 for b in got)


def test_features_ignore_bars_after_as_of():
    """A violent move AFTER the entry date must not change any feature."""
    calm = _alternating(40, r=0.005)
    bars_calm = _from_closes(calm)
    as_of = sorted(bars_calm)[25]

    spiked = list(calm)
    for i in range(26, 40):                       # everything after as_of
        spiked[i] = spiked[i] * (3.0 if i % 2 else 0.4)
    bars_spiked = _from_closes(spiked)

    assert uf.rv20(bars_calm, as_of) == uf.rv20(bars_spiked, as_of)
    assert uf.eff_ratio(bars_calm, as_of) == uf.eff_ratio(bars_spiked, as_of)


def test_trailing_bars_on_empty_series():
    assert uf.trailing_bars({}, START, 5) == []


# --- realized vol -------------------------------------------------------------

def test_rv20_matches_the_closed_form_on_alternating_returns():
    bars = _from_closes(_alternating(uf.RV_WINDOW + 1, r=0.01))
    assert uf.rv20(bars, max(bars)) == pytest.approx(0.01 * ANN, rel=1e-9)


def test_rv20_is_zero_on_a_flat_series():
    bars = _from_closes([100.0] * (uf.RV_WINDOW + 1))
    assert uf.rv20(bars, max(bars)) == pytest.approx(0.0)


def test_rv20_returns_none_below_the_observation_floor():
    bars = _from_closes(_alternating(uf._MIN_RV_OBS))   # one return short
    assert uf.rv20(bars, max(bars)) is None


def test_split_artifact_return_is_dropped_not_clipped():
    """A 10x step is an unadjusted ex-split date, not a session move.

    Dropping it must leave the estimate equal to the clean series' — a clipped
    step would still inject a fabricated 30% session into the mean.
    """
    clean = _alternating(uf.RV_WINDOW + 1, r=0.01)
    rv_clean = uf.rv20(_from_closes(clean), max(_from_closes(clean)))

    stepped = list(clean)
    stepped[10:] = [c * 10 for c in stepped[10:]]      # one 10x step, then consistent
    bars = _from_closes(stepped)
    rv_stepped = uf.rv20(bars, max(bars))

    # Dropping costs one observation, so this is close to the clean estimate
    # rather than identical to it. What matters is that it stays THERE: a
    # clipped step would leave a fabricated 30% session in a 20-return window
    # and push the annualised estimate past 1.0.
    assert rv_stepped == pytest.approx(rv_clean, rel=0.02)
    assert rv_stepped < 0.25


# --- the OHLC-only pair -------------------------------------------------------

def test_parkinson_and_atr_are_none_on_the_close_only_path():
    """The coverage invariant: `Price~` bars have no high or low, so these two
    must be None rather than silently falling back to close-to-close."""
    bars = _from_closes(_alternating(40), source=SRC_TILDE)
    as_of = max(bars)
    assert uf.rv_parkinson(bars, as_of) is None
    assert uf.atr14_pct(bars, as_of) is None
    # ...while the close-only features still work on the same bars.
    assert uf.rv20(bars, as_of) is not None
    assert uf.eff_ratio(bars, as_of) is not None


def test_parkinson_matches_the_closed_form():
    bars = _from_closes([100.0] * (uf.RV_WINDOW + 1), hl=(1.0, 1.0))  # h=101, l=99
    expected = math.sqrt(math.log(101 / 99) ** 2 / (4 * math.log(2))) * ANN
    assert uf.rv_parkinson(bars, max(bars)) == pytest.approx(expected, rel=1e-9)


def test_atr14_pct_is_the_true_range_over_close():
    bars = _from_closes([100.0] * (uf.ATR_WINDOW + 1), hl=(1.0, 1.0))
    # Flat closes: TR = max(h-l, |h-prev_c|, |l-prev_c|) = max(2, 1, 1) = 2.
    assert uf.atr14_pct(bars, max(bars)) == pytest.approx(0.02, rel=1e-9)


# --- shape features -----------------------------------------------------------

def test_eff_ratio_is_one_on_a_straight_line():
    bars = _from_closes(_monotone(uf.EFF_WINDOW + 1))
    assert uf.eff_ratio(bars, max(bars)) == pytest.approx(1.0, rel=1e-9)


def test_eff_ratio_is_near_zero_on_pure_chop():
    """The give-back signature: a name that travels far and ends where it began."""
    bars = _from_closes(_alternating(uf.EFF_WINDOW + 1, r=0.02))
    assert uf.eff_ratio(bars, max(bars)) < 0.10


def test_semivar_dn_is_zero_when_nothing_fell():
    bars = _from_closes(_monotone(uf.RV_WINDOW + 1))
    assert uf.semivar_dn(bars, max(bars)) == pytest.approx(0.0)


def test_semivar_dn_ignores_upside_vol():
    """Two series with the SAME total vol but opposite skew must separate here,
    which is the entire reason this is not just `rv20`."""
    up = _from_closes(_monotone(uf.RV_WINDOW + 1, r=0.02))
    alt = _from_closes(_alternating(uf.RV_WINDOW + 1, r=0.02))
    assert uf.semivar_dn(up, max(up)) == pytest.approx(0.0)
    assert uf.semivar_dn(alt, max(alt)) > 0.0


# --- vrp ----------------------------------------------------------------------

def test_vrp_is_implied_minus_realized_in_matching_units():
    bars = _from_closes(_alternating(uf.RV_WINDOW + 1, r=0.01))
    realized = uf.rv20(bars, max(bars))            # ~0.1587 decimal fraction
    assert uf.vrp(bars, max(bars), 0.30) == pytest.approx(0.30 - realized, rel=1e-9)


def test_vrp_propagates_missing_iv_as_none():
    bars = _from_closes(_alternating(uf.RV_WINDOW + 1))
    as_of = max(bars)
    assert uf.vrp(bars, as_of, None) is None
    assert uf.vrp(bars, as_of, 0.0) is None


def test_vrp_is_none_when_realized_is_unavailable():
    bars = _from_closes(_alternating(5))           # too few bars for rv20
    assert uf.vrp(bars, max(bars), 0.30) is None


# --- market coupling ----------------------------------------------------------

@pytest.fixture
def _market(monkeypatch):
    """A synthetic SPY series on the same calendar, monkeypatched in."""
    def _install(closes):
        series = dict(zip(_days(len(closes)), closes))
        monkeypatch.setattr(uf, "market_closes", lambda: series)
    uf.market_closes.cache_clear()
    yield _install
    uf.market_closes.cache_clear()


def test_beta_is_one_against_an_identical_market(_market):
    closes = _alternating(uf.BETA_WINDOW + 1, r=0.01)
    _market(closes)
    bars = _from_closes(closes)
    beta, corr = uf.beta_corr_spy(bars, max(bars))
    assert beta == pytest.approx(1.0, rel=1e-9)
    assert corr == pytest.approx(1.0, rel=1e-9)


def test_beta_is_two_when_the_name_moves_twice_as_hard(_market):
    mkt = _alternating(uf.BETA_WINDOW + 1, r=0.01)
    _market(mkt)
    bars = _from_closes(_alternating(uf.BETA_WINDOW + 1, r=0.02))
    beta, corr = uf.beta_corr_spy(bars, max(bars))
    assert beta == pytest.approx(2.0, rel=1e-6)
    assert corr == pytest.approx(1.0, rel=1e-6)


def test_beta_is_none_without_a_market_series(monkeypatch):
    monkeypatch.setattr(uf, "market_closes", dict)
    bars = _from_closes(_alternating(uf.BETA_WINDOW + 1))
    assert uf.beta_corr_spy(bars, max(bars)) == (None, None)


def test_beta_pairs_only_on_dates_both_series_traded(monkeypatch):
    """A holiday in one series must drop the date, not shift the alignment.

    Misaligned, the name's day-6 return would be fitted against the market's
    day-5 and the beta would collapse toward zero on an identical series.
    """
    closes = _alternating(uf.BETA_WINDOW + 2, r=0.01)
    series = dict(zip(_days(len(closes)), closes))
    del series[sorted(series)[5]]                  # market closed that day
    monkeypatch.setattr(uf, "market_closes", lambda: series)
    bars = _from_closes(closes)
    beta, corr = uf.beta_corr_spy(bars, max(bars))
    assert beta == pytest.approx(1.0, rel=1e-6)
    assert corr == pytest.approx(1.0, rel=1e-6)


# --- the aggregate ------------------------------------------------------------

def test_features_reports_source_and_ohlc_coverage():
    ohlc = uf.features(_from_closes(_alternating(40), hl=(1.0, 1.0)),
                       max(_from_closes(_alternating(40))), iv_entry=0.30)
    assert ohlc["source"] == SRC_OHLC and ohlc["has_ohlc"]
    assert all(ohlc[k] is not None for k in uf.FEATURE_KEYS if k not in
               ("beta_spy60", "corr_spy60"))

    tilde_bars = _from_closes(_alternating(40), source=SRC_TILDE)
    tilde = uf.features(tilde_bars, max(tilde_bars), iv_entry=0.30)
    assert tilde["source"] == SRC_TILDE and not tilde["has_ohlc"]
    assert all(tilde[k] is None for k in uf.OHLC_ONLY_KEYS)


def test_features_on_an_empty_series_is_all_none():
    out = uf.features({}, START, iv_entry=0.30)
    assert all(out[k] is None for k in uf.FEATURE_KEYS)
    assert out["n_bars"] == 0 and out["source"] is None


def test_coverage_separates_the_ohlc_only_denominator():
    rows = [{"rv20": 0.2, "rv_park": 0.2, "source": SRC_OHLC, "has_ohlc": True},
            {"rv20": 0.3, "rv_park": None, "source": SRC_TILDE, "has_ohlc": False}]
    cov = uf.coverage(rows)
    assert cov["n_rows"] == 2 and cov["has_ohlc"] == 1
    assert cov["by_source"] == {SRC_OHLC: 1, SRC_TILDE: 1}
    assert cov["rv20"]["n"] == 2 and not cov["rv20"]["ohlc_only"]
    assert cov["rv_park"]["n"] == 1 and cov["rv_park"]["ohlc_only"]


def test_terciles_split_the_population_and_refuse_thin_samples():
    rows = [{"x": float(i)} for i in range(9)]
    assert uf.terciles(rows, "x") == (3.0, 6.0)
    assert uf.terciles(rows[:8], "x") is None
    assert uf.terciles([{"x": None}] * 20, "x") is None
