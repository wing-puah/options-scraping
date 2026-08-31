"""Tests for `scripts.backtest_study.lib.hedge_instrument` — the hedge
INSTRUMENT layer of the `hedge_exposure` study (proxy put + ARM R underlying
short).

Fixture option CSVs are written under `tmp_path` with the header
`lib/barchart/options.py` documents, named via the real `cache_path()`, and
`hedge_instrument.HISTORY_CACHE` / `greeks.HISTORY_CACHE` are monkeypatched at
them — the same pattern `tests/test_studies_greeks.py` uses. Underlying bars
come from a fixture `underlying_ohlc_cache` behind `underlying.OHLC_CACHE`, so
`spot_on` is exercised through the real `load_bars`, not stubbed.

What these pin is the COMMITTED behaviour of
`research/pre-registrations/f4_deployment/hedge_exposure.md`: the two fill
rules and their windows, "return None rather than fabricate a fill", the
rescaled-ticker exclusion being a function call and not a name list, a missing
greek staying None, and ARM R being SHORT.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from lib.barchart.options import cache_path  # noqa: E402
from scripts.backtest_study.lib import greeks  # noqa: E402
from scripts.backtest_study.lib import hedge_instrument as HI  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,"
          "Delta,Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")

SESSION = date(2025, 1, 6)          # a Monday
LATER = date(2025, 1, 13)
E45 = date(2025, 2, 20)             # 45 DTE from SESSION
E30 = date(2025, 2, 5)              # 30 DTE
E60 = date(2025, 3, 7)              # 60 DTE
E10 = date(2025, 1, 16)             # 10 DTE — outside both windows
E200 = date(2025, 7, 25)            # 200 DTE — outside both windows

SPOT = 100.0


def _opt_row(t: str, *, bid="", ask="", latest="", iv="30.0", delta=""):
    return (f"{t},0,0,0,{latest},0,0%,10,100,{iv},"
            f"{delta},,,,,,{SPOT},{bid},{ask}")


def _bar_row(t: str, close: float):
    """One underlying bar. `load_bars` reads close off `Latest`."""
    return f"{t},{close},{close},{close},{close},0,0%,1000,,,,,,,,,,,"


@pytest.fixture
def caches(tmp_path, monkeypatch):
    """(option_cache_dir, ohlc_cache_dir) with every module-level cache reset."""
    opt = tmp_path / "option_history_cache"
    opt.mkdir()
    ohlc = tmp_path / "underlying_ohlc_cache"
    ohlc.mkdir()
    monkeypatch.setattr(HI, "HISTORY_CACHE", opt)
    monkeypatch.setattr(greeks, "HISTORY_CACHE", opt)
    monkeypatch.setattr(U, "HISTORY_CACHE", opt)
    monkeypatch.setattr(U, "OHLC_CACHE", ohlc)
    monkeypatch.setattr(U, "RESCALED_FILE", ohlc / "rescaled_tickers.txt")
    HI.clear_caches()
    U._load_ohlc_cache.cache_clear()
    U._load_tilde.cache_clear()
    U.rescaled_tickers.cache_clear()
    yield opt, ohlc
    HI.clear_caches()
    U._load_ohlc_cache.cache_clear()
    U._load_tilde.cache_clear()
    U.rescaled_tickers.cache_clear()


def _put(opt_dir: Path, ticker: str, expiry: date, strike: float, rows: list[str]):
    path = cache_path(opt_dir, ticker, expiry, strike, "Put")
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n")


def _bars(ohlc_dir: Path, ticker: str, rows: list[tuple[date, float]]):
    body = "\n".join(_bar_row(d.isoformat(), c) for d, c in rows)
    (ohlc_dir / f"{ticker}.csv").write_text(HEADER + "\n" + body + "\n")


def _std_bars(ohlc_dir: Path, ticker: str = "PRX", close: float = SPOT):
    _bars(ohlc_dir, ticker, [(SESSION, close), (LATER, close * 0.90)])


# ── spot and the instrument exclusion ────────────────────────────────────────

def test_spot_on_reads_the_sessions_close(caches):
    _, ohlc = caches
    _std_bars(ohlc)
    assert HI.spot_on("PRX", SESSION) == pytest.approx(SPOT)


def test_spot_on_is_none_when_the_session_has_no_bar(caches):
    _, ohlc = caches
    _std_bars(ohlc)
    assert HI.spot_on("PRX", date(2025, 1, 7)) is None


def test_the_exclusion_is_the_rescaled_list_not_a_name(caches):
    """XLE falls out because it is on `rescaled_tickers()`. Nothing here knows
    its name — put any ticker on the list and it is withheld the same way."""
    _, ohlc = caches
    (ohlc / "rescaled_tickers.txt").write_text("# t rel n\nPRX\t0.5000\t267\n")
    U.rescaled_tickers.cache_clear()
    assert HI.instrument_excluded("PRX") is True
    assert HI.instrument_excluded("QQQ") is False


def test_an_excluded_instrument_yields_no_pick_and_no_arm_r_position(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", E45, 100.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    (ohlc / "rescaled_tickers.txt").write_text("PRX\n")
    U.rescaled_tickers.cache_clear()
    pick, reason = HI.select_put_verbose("PRX", SESSION)
    assert pick is None and reason == HI.RESCALED
    assert HI.underlying_position("PRX", SESSION, -100) is None


# ── the BAND rule ────────────────────────────────────────────────────────────

def test_band_rule_takes_a_contract_inside_both_windows(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", E45, 98.0, [_opt_row(SESSION.isoformat(), bid="4.0", ask="6.0")])
    pick = HI.select_put("PRX", SESSION, HI.RULE_BAND)
    assert pick is not None
    assert (pick.expiry, pick.strike) == (E45, 98.0)
    assert pick.entry_mark == pytest.approx(5.0)     # mid(Bid,Ask)
    assert pick.dte == 45
    assert pick.moneyness == pytest.approx(0.02)


@pytest.mark.parametrize("expiry", [E10, E200])
def test_band_rule_refuses_an_expiry_outside_25_75_dte(caches, expiry):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", expiry, 100.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.select_put_verbose("PRX", SESSION, HI.RULE_BAND) == (None, HI.NO_CONTRACT)


@pytest.mark.parametrize("strike", [94.0, 106.0])
def test_band_rule_refuses_a_strike_outside_plus_minus_5_percent(caches, strike):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", E45, strike, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.select_put_verbose("PRX", SESSION, HI.RULE_BAND) == (None, HI.NO_CONTRACT)


def test_band_rule_ranks_by_expiry_anchor_then_nearest_strike(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    for expiry in (E30, E45, E60):
        for strike in (96.0, 100.0, 104.0):
            _put(opt, "PRX", expiry, strike,
                 [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    pick = HI.select_put("PRX", SESSION, HI.RULE_BAND)
    assert (pick.expiry, pick.strike) == (E45, 100.0)


def test_band_rule_skips_an_unpriced_contract_for_a_priced_one(caches):
    """The best-ranked contract with no usable price is not a fill — the rule
    falls through to the next one rather than fabricating a mark."""
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", E45, 100.0, [_opt_row(SESSION.isoformat(), bid="0", ask="0",
                                           latest="0")])
    _put(opt, "PRX", E45, 98.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    pick = HI.select_put("PRX", SESSION, HI.RULE_BAND)
    assert (pick.expiry, pick.strike) == (E45, 98.0)


def test_no_usable_price_anywhere_returns_none_not_a_fabricated_fill(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", E45, 100.0, [_opt_row(SESSION.isoformat(), bid="0", ask="0",
                                           latest="0")])
    assert HI.select_put_verbose("PRX", SESSION, HI.RULE_BAND) == (None, HI.NO_MARK)


def test_latest_is_the_fallback_when_there_is_no_two_sided_quote(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", E45, 100.0,
         [_opt_row(SESSION.isoformat(), bid="0", ask="0", latest="3.25")])
    assert HI.select_put("PRX", SESSION).entry_mark == pytest.approx(3.25)


def test_no_spot_means_no_pick(caches):
    opt, ohlc = caches
    _bars(ohlc, "PRX", [(LATER, SPOT)])          # no bar on SESSION
    _put(opt, "PRX", E45, 100.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.select_put_verbose("PRX", SESSION, HI.RULE_BAND) == (None, HI.NO_SPOT)


def test_an_unknown_rule_is_refused_not_silently_defaulted(caches):
    _, ohlc = caches
    _std_bars(ohlc)
    assert HI.select_put_verbose("PRX", SESSION, "atm") == (None, HI.BAD_RULE)


# ── the NEAREST-AVAILABLE rule ───────────────────────────────────────────────

def test_nearest_rule_takes_the_nearest_quoted_strike_at_or_below_spot(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    for strike in (90.0, 95.0, 105.0):
        _put(opt, "PRX", E45, strike, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    pick = HI.select_put("PRX", SESSION, HI.RULE_NEAREST)
    assert pick.strike == 95.0


def test_nearest_rule_reaches_outside_the_band_windows(caches):
    """A 20-DTE, 30%-out strike is a fill for NEAREST and not for BAND — which
    is the whole reason both rules are registered."""
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", date(2025, 1, 26), 70.0,
         [_opt_row(SESSION.isoformat(), bid="0.4", ask="0.6")])
    assert HI.select_put("PRX", SESSION, HI.RULE_BAND) is None
    assert HI.select_put("PRX", SESSION, HI.RULE_NEAREST).strike == 70.0


def test_nearest_rule_prefers_the_expiry_closest_to_45_dte(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    for expiry in (E30, E45, E60, E200):
        _put(opt, "PRX", expiry, 95.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.select_put("PRX", SESSION, HI.RULE_NEAREST).expiry == E45


def test_nearest_rule_refuses_an_expiry_outside_20_120_dte(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", E10, 95.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    _put(opt, "PRX", E200, 95.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.select_put_verbose("PRX", SESSION, HI.RULE_NEAREST) == (None, HI.NO_CONTRACT)


def test_nearest_rule_never_reaches_above_spot(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", E45, 105.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.select_put_verbose("PRX", SESSION, HI.RULE_NEAREST) == (None, HI.NO_CONTRACT)


# ── forward pricing ──────────────────────────────────────────────────────────

def _priced_pick(opt, ohlc, rows):
    _std_bars(ohlc)
    _put(opt, "PRX", E45, 100.0, rows)
    return HI.select_put("PRX", SESSION, HI.RULE_BAND)


def test_mark_on_carries_the_last_mark_forward(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6"),
                                    _opt_row(LATER.isoformat(), bid="7", ask="9")])
    assert HI.mark_on(pick, date(2025, 1, 9)) == pytest.approx(5.0)   # carried
    assert HI.mark_on(pick, LATER) == pytest.approx(8.0)
    assert HI.mark_on(pick, date(2025, 1, 20)) == pytest.approx(8.0)  # carried


def test_mark_on_is_none_before_the_entry_session(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.mark_on(pick, date(2025, 1, 2)) is None


def test_mark_on_never_carries_a_post_expiry_row(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6"),
                                    _opt_row("2025-03-10", bid="90", ask="92")])
    assert HI.mark_on(pick, date(2025, 3, 20)) == pytest.approx(5.0)


def test_pnl_path_is_none_on_an_unpriced_day_never_zero(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    path = HI.pnl_path(pick, [date(2025, 1, 2), SESSION], contracts=2)
    assert path[date(2025, 1, 2)] is None
    assert path[SESSION] == pytest.approx(0.0)


def test_pnl_and_cost_scale_by_contracts_and_100_shares(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6"),
                                    _opt_row(LATER.isoformat(), bid="7", ask="9")])
    assert HI.entry_cost(pick, 3) == pytest.approx(1500.0)
    assert HI.pnl_path(pick, [LATER], 3)[LATER] == pytest.approx(900.0)


def test_price_path_returns_none_rather_than_the_entry_price(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.price_path(pick, [date(2025, 1, 2)])[date(2025, 1, 2)] is None


# ── greeks: None, never 0.0 ──────────────────────────────────────────────────

def test_entry_delta_is_signed_and_scaled(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc,
                        [_opt_row(SESSION.isoformat(), bid="4", ask="6", delta="-0.40")])
    assert HI.entry_delta(pick, 2) == pytest.approx(-80.0)


def test_entry_delta_is_none_when_the_greek_is_absent(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.entry_delta(pick, 2) is None


def test_entry_delta_is_none_on_barcharts_all_zero_sentinel_row(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6",
                                             iv="0", delta="0")])
    assert HI.entry_delta(pick, 1) is None


# ── ARM R ────────────────────────────────────────────────────────────────────

def test_delta_equivalent_position_is_short(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc,
                        [_opt_row(SESSION.isoformat(), bid="4", ask="6", delta="-0.40")])
    pos = HI.delta_equivalent_short(pick, 2)
    assert pos.shares == pytest.approx(-80.0)
    assert pos.entry_price == pytest.approx(SPOT)
    assert pos.delta_notional == pytest.approx(-8000.0)


def test_delta_equivalent_short_is_none_when_the_delta_is_missing(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.delta_equivalent_short(pick, 2) is None


def test_short_gains_when_the_underlying_falls(caches):
    _, ohlc = caches
    _std_bars(ohlc)                                   # 100 -> 90 by LATER
    pos = HI.underlying_position("PRX", SESSION, -80.0)
    assert HI.short_pnl_path(pos, [LATER])[LATER] == pytest.approx(800.0)


def test_short_pnl_is_none_on_a_bar_less_day(caches):
    _, ohlc = caches
    _std_bars(ohlc)
    assert HI.short_pnl_path(HI.underlying_position("PRX", SESSION, -80.0),
                             [date(2025, 1, 8)])[date(2025, 1, 8)] is None


def test_short_for_delta_notional_keeps_the_callers_sign(caches):
    _, ohlc = caches
    _std_bars(ohlc)
    pos = HI.short_for_delta_notional("PRX", SESSION, -10_000.0)
    assert pos.shares == pytest.approx(-100.0)


def test_arm_r_is_fillable_where_the_put_is_not(caches):
    """ARM R exists so the study cannot terminate on fill coverage alone."""
    _, ohlc = caches
    _std_bars(ohlc)                                   # bars, but no option cache
    assert HI.select_put("PRX", SESSION, HI.RULE_BAND) is None
    assert HI.underlying_position("PRX", SESSION, -50.0) is not None


# ── the frozen harness ───────────────────────────────────────────────────────

def test_harness_trade_builds_a_replayable_trade(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6"),
                                    _opt_row(LATER.isoformat(), bid="7", ask="9")])
    t = HI.harness_trade(pick, 2)
    assert t is not None
    assert len(t.marks) == len(t.grid)                # the Trade's own assertion
    assert t.entry_net == pytest.approx(5.0)
    assert t.contracts == 2
    assert [leg.qty for leg in t.legs] == [1]             # a LONG put, one leg


def test_harness_trade_refuses_a_sub_one_contract_lot(caches):
    opt, ohlc = caches
    pick = _priced_pick(opt, ohlc, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    assert HI.harness_trade(pick, 0) is None


# ── G-FILL coverage ──────────────────────────────────────────────────────────

def test_fill_coverage_keeps_unfillable_sessions_in_the_denominator(caches):
    opt, ohlc = caches
    _bars(ohlc, "PRX", [(SESSION, SPOT), (LATER, SPOT)])
    _put(opt, "PRX", E45, 100.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    cov = HI.fill_coverage([(SESSION, "PRX"), (LATER, "PRX")], HI.RULE_BAND)
    assert (cov.n, cov.filled) == (2, 1)
    assert cov.rate == pytest.approx(0.5)
    assert cov.by_reason[HI.FILLED] == 1


def test_fill_coverage_counts_an_excluded_proxy_against_the_gate(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", E45, 100.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    (ohlc / "rescaled_tickers.txt").write_text("PRX\n")
    U.rescaled_tickers.cache_clear()
    cov = HI.fill_coverage([(SESSION, "PRX")], HI.RULE_BAND)
    assert (cov.n, cov.filled) == (1, 0)
    assert cov.by_reason == {HI.RESCALED: 1}
    assert cov.passes() is False


def test_the_fill_gate_is_the_committed_60_percent(caches):
    assert HI.FILL_GATE == 0.60
    cov = HI.FillCoverage(rule=HI.RULE_BAND, n=10, filled=6, by_proxy={}, by_reason={})
    assert cov.passes() is True
    assert HI.FillCoverage(rule=HI.RULE_BAND, n=10, filled=5,
                           by_proxy={}, by_reason={}).passes() is False


def test_coverage_table_reports_both_committed_rules_over_one_pair_set(caches):
    opt, ohlc = caches
    _std_bars(ohlc)
    _put(opt, "PRX", date(2025, 1, 26), 70.0,
         [_opt_row(SESSION.isoformat(), bid="0.4", ask="0.6")])
    table = HI.coverage_table([(SESSION, "PRX")])
    assert set(table) == set(HI.RULES)
    assert table[HI.RULE_BAND].rate == 0.0
    assert table[HI.RULE_NEAREST].rate == 1.0


def test_per_proxy_rates_are_broken_out(caches):
    opt, ohlc = caches
    _bars(ohlc, "PRX", [(SESSION, SPOT)])
    _bars(ohlc, "OTH", [(SESSION, SPOT)])
    _put(opt, "PRX", E45, 100.0, [_opt_row(SESSION.isoformat(), bid="4", ask="6")])
    cov = HI.fill_coverage([(SESSION, "PRX"), (SESSION, "OTH")], HI.RULE_BAND)
    assert cov.proxy_rate("PRX") == 1.0
    assert cov.proxy_rate("OTH") == 0.0


# ── the committed constants are not drifting ─────────────────────────────────

def test_the_committed_windows_are_what_the_preregistration_fixed():
    assert (HI.BAND_DTE_LO, HI.BAND_DTE_HI) == (25, 75)
    assert HI.BAND_STRIKE_PCT == 0.05
    assert (HI.NEAREST_DTE_LO, HI.NEAREST_DTE_HI) == (20, 120)
    assert HI.NEAREST_ANCHOR_DTE == 45
