"""
Tests for the journal's shared core: the pull schema, risk maths and writer.

The recurring theme is the MISSING/ZERO invariant. A greek the broker never sent
is not a zero greek, and every layer here has to keep those apart — the pull
refuses to mark a null delta as sourced, risk excludes an unpriced position
instead of counting it as delta-neutral, and the writer renders a real 0.0 as 0.0
while rendering None as blank. Each of those is a separate opportunity to
silently understate exposure, so each is tested separately.
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone

import pytest

from scripts.journal import analysis as A
from scripts.journal import rawpull, risk, writer
from scripts.journal.config import (DELTA_SOURCE_BARCHART, DELTA_SOURCE_IBKR,
                                    DELTA_SOURCE_UNAVAILABLE, JOURNAL_COLUMNS,
                                    Greeks, Leg, PositionEvent)

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _leg(conid=1, qty=1, strike=170.0, right="C", symbol="NVDA", price=5.0):
    return Leg(conid=conid, symbol=symbol, expiry=date(2026, 10, 16), strike=strike,
               right=right, qty=qty, fill_price=price, commission=1.0,
               exec_id=f"e{conid}", fill_time=datetime(2026, 8, 14, 14, 30,
                                                       tzinfo=timezone.utc),
               open_close="O")


def _event(**kw):
    defaults = dict(date="2026-08-14", trade_datetime_utc="2026-08-14T14:30:00Z",
                    ticker="NVDA", structure="bull_call_spread", action="OPEN",
                    legs=[_leg(1, 1, 170.0), _leg(2, -1, 180.0)], contracts=1,
                    net_price=3.2, commission=2.0, net_cash=-322.0,
                    source_ref="ibkr-2026-08-14-1615.json:e1,e2")
    defaults.update(kw)
    return PositionEvent(**defaults)


def _raw(**kw):
    base = {
        "schema_version": rawpull.SCHEMA_VERSION,
        "pulled_at_utc": "2026-08-14T20:15:03Z",
        "trade_date": "2026-08-14",
        "source": "ibkr-cpapi",
        "account_id": "U1",
        "net_liquidation": 100000.0,
        "trades": [{"exec_id": "e1", "conid": 1, "symbol": "NVDA", "side": "BUY",
                    "size": 1, "price": 5.0, "commission": 1.0,
                    "trade_time": "2026-08-14T14:30:00Z", "open_close": "O"}],
        "positions": [],
        "contracts": {"1": {"symbol": "NVDA", "sec_type": "OPT", "strike": 170.0,
                            "expiry": "2026-10-16", "right": "C", "multiplier": 100}},
        "greeks": {},
        "underlying_prices": {},
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# rawpull
# --------------------------------------------------------------------------


def test_validate_accepts_a_well_formed_pull():
    rawpull.validate(_raw())


@pytest.mark.parametrize("missing", ["trade_date", "trades", "contracts", "positions"])
def test_validate_rejects_a_pull_missing_a_required_key(missing):
    raw = _raw()
    del raw[missing]
    with pytest.raises(rawpull.RawPullError, match="missing required key"):
        rawpull.validate(raw)


def test_validate_rejects_a_foreign_schema_version():
    with pytest.raises(rawpull.RawPullError, match="schema_version"):
        rawpull.validate(_raw(schema_version=99))


def test_validate_rejects_a_fill_whose_contract_was_never_resolved():
    """The whole point of conid identity is that strike/expiry are never guessed."""
    with pytest.raises(rawpull.RawPullError, match="no contract detail"):
        rawpull.validate(_raw(contracts={}))


def test_validate_rejects_a_null_delta_claiming_to_be_sourced():
    raw = _raw(greeks={"1": {"delta": None, "source": DELTA_SOURCE_IBKR}})
    with pytest.raises(rawpull.RawPullError, match="null delta"):
        rawpull.validate(raw)


def test_a_genuine_zero_delta_is_a_valid_sourced_greek():
    rawpull.validate(_raw(greeks={"1": {"delta": 0.0, "source": DELTA_SOURCE_IBKR}}))


def test_save_refuses_to_overwrite_an_existing_pull(tmp_path):
    p = tmp_path / "pull.json"
    rawpull.save(_raw(), p)
    with pytest.raises(rawpull.RawPullError, match="immutable"):
        rawpull.save(_raw(), p)


def test_saved_pull_round_trips_through_load(tmp_path):
    p = tmp_path / "pull.json"
    rawpull.save(_raw(), p)
    back = rawpull.load(p)
    assert back["trade_date"] == "2026-08-14"
    assert json.loads(p.read_text())["schema_version"] == rawpull.SCHEMA_VERSION


@pytest.mark.parametrize("side,expected_sign", [("BUY", 1), ("SELL", -1)])
def test_fill_to_leg_takes_its_sign_from_the_side_not_the_size(side, expected_sign):
    raw = _raw()
    fill = dict(raw["trades"][0], side=side, size=3)
    leg = rawpull.fill_to_leg(raw, fill)
    assert leg.qty == 3 * expected_sign


def test_greeks_map_preserves_missing_as_none():
    raw = _raw(greeks={"1": {"delta": None, "source": DELTA_SOURCE_UNAVAILABLE}})
    g = rawpull.greeks_map(raw)[1]
    assert g.delta is None and not g.has_delta


# --------------------------------------------------------------------------
# risk
# --------------------------------------------------------------------------


def test_position_delta_is_all_or_nothing_across_legs():
    """A spread priced on one leg is not partially known — it is wrong.

    The unpriced leg is precisely the hedge, so a half-priced spread would report
    the naked long's delta and overstate exposure badly.
    """
    legs = [_leg(1, 1), _leg(2, -1)]
    both = {1: Greeks(1, delta=0.55, source=DELTA_SOURCE_IBKR),
            2: Greeks(2, delta=0.35, source=DELTA_SOURCE_IBKR)}
    assert risk.position_delta(legs, both) == pytest.approx(0.20)
    half = {1: Greeks(1, delta=0.55, source=DELTA_SOURCE_IBKR), 2: Greeks(2)}
    assert risk.position_delta(legs, half) is None


def test_delta_notional_matches_the_account_sim_formula():
    """signed_dn = delta x 100 x contracts x underlying."""
    legs = [_leg(1, 2)]
    g = {1: Greeks(1, delta=0.50, source=DELTA_SOURCE_IBKR)}
    p = risk.mark_position("1", "NVDA", "long_call", 2, legs, g, underlying_price=175.0)
    assert p.delta_notional == pytest.approx(0.50 * 100 * 2 * 175.0)


def test_short_leg_delta_picks_the_binding_leg():
    legs = [_leg(1, 1, 170.0), _leg(2, -1, 180.0), _leg(3, -1, 190.0)]
    g = {1: Greeks(1, delta=0.6, source=DELTA_SOURCE_IBKR),
         2: Greeks(2, delta=0.35, source=DELTA_SOURCE_IBKR),
         3: Greeks(3, delta=0.15, source=DELTA_SOURCE_IBKR)}
    assert risk.short_leg_delta(legs, g) == pytest.approx(0.35)


def test_short_leg_delta_is_none_when_there_is_no_short_leg():
    assert risk.short_leg_delta([_leg(1, 1)], {1: Greeks(1, delta=0.6,
                                                         source=DELTA_SOURCE_IBKR)}) is None


def test_a_delta_neutral_position_is_priced_not_excluded():
    """0.0 net delta is a real answer; only an ABSENT delta excludes a position."""
    legs = [_leg(1, 1), _leg(2, -1)]
    g = {1: Greeks(1, delta=0.5, source=DELTA_SOURCE_IBKR),
         2: Greeks(2, delta=0.5, source=DELTA_SOURCE_IBKR)}
    p = risk.mark_position("k", "NVDA", "calendar", 1, legs, g, underlying_price=175.0)
    assert p.priced is True
    assert p.delta_notional == 0.0


def test_an_unpriced_position_is_excluded_and_flips_complete():
    caps = risk.load_caps(net_liq=100000)
    priced = risk.mark_position("a", "NVDA", "long_call", 1, [_leg(1, 1)],
                                {1: Greeks(1, delta=0.5, source=DELTA_SOURCE_IBKR)}, 175.0)
    unpriced = risk.mark_position("b", "AMD", "long_call", 1, [_leg(9, 1)],
                                  {9: Greeks(9)}, 175.0)
    book = risk.assess([priced, unpriced], caps)
    assert book.complete is False
    assert len(book.unpriced) == 1
    assert book.net_delta_notional == pytest.approx(0.5 * 100 * 175.0)


# --------------------------------------------------------------------------
# Delta provenance
# --------------------------------------------------------------------------
# `delta_source` reaches the permanent TradeJournal row, and it is what a later
# reader uses to judge how far to trust the exposure. It was hardcoded to
# "ibkr" for every priced position, which labelled the Flex path's
# Barchart-scraped deltas as broker-sourced — a claim about the quality of the
# evidence that was simply untrue.
def test_a_barchart_delta_is_not_reported_as_broker_sourced():
    p = risk.mark_position("a", "NVDA", "long_call", 1, [_leg(1, 1)],
                           {1: Greeks(1, delta=0.5, source=DELTA_SOURCE_BARCHART)}, 175.0)
    assert p.delta_source == DELTA_SOURCE_BARCHART


def test_a_broker_delta_still_reports_ibkr():
    p = risk.mark_position("a", "NVDA", "long_call", 1, [_leg(1, 1)],
                           {1: Greeks(1, delta=0.5, source=DELTA_SOURCE_IBKR)}, 175.0)
    assert p.delta_source == DELTA_SOURCE_IBKR


def test_legs_marked_from_different_feeds_are_reported_as_mixed():
    """Not collapsed to one name: a spread half-marked from another feed is
    exactly the case a reader should notice rather than average over."""
    legs = [_leg(1, 1), _leg(2, -1)]
    g = {1: Greeks(1, delta=0.5, source=DELTA_SOURCE_IBKR),
         2: Greeks(2, delta=0.3, source=DELTA_SOURCE_BARCHART)}
    p = risk.mark_position("a", "NVDA", "bull_call_spread", 1, legs, g, 175.0)
    assert p.delta_source == "barchart+ibkr"


def test_an_unpriceable_position_claims_no_source():
    legs = [_leg(1, 1), _leg(2, -1)]
    p = risk.mark_position("a", "NVDA", "bull_call_spread", 1, legs,
                           {1: Greeks(1, delta=0.5, source=DELTA_SOURCE_IBKR)}, 175.0)
    assert p.delta_source == DELTA_SOURCE_UNAVAILABLE
    assert p.priced is False


def test_missing_underlying_price_leaves_a_position_unpriced():
    p = risk.mark_position("a", "NVDA", "long_call", 1, [_leg(1, 1)],
                           {1: Greeks(1, delta=0.5, source=DELTA_SOURCE_IBKR)}, None)
    assert p.priced is False


def test_caps_bind_against_live_equity_not_the_studys_capital():
    """config/account-sim.yml's $25k is the STUDY's denominator, not the account's."""
    caps = risk.load_caps(net_liq=200000)
    assert caps.per_position_dollars == pytest.approx(0.25 * 200000)
    assert caps.net_dollars == pytest.approx(2.50 * 200000)


def test_load_caps_refuses_a_nonpositive_equity():
    with pytest.raises(ValueError, match="positive"):
        risk.load_caps(net_liq=0)


def test_every_per_position_breach_is_reported_not_just_the_first():
    caps = risk.load_caps(net_liq=10000)   # per-position cap = $2,500
    big = [risk.mark_position(str(i), f"T{i}", "long_call", 1, [_leg(i, 1)],
                              {i: Greeks(i, delta=0.9, source=DELTA_SOURCE_IBKR)}, 500.0)
           for i in (1, 2)]
    book = risk.assess(big, caps)
    assert sum("exceeds the per-position cap" in b for b in book.breaches) == 2


def test_headroom_checks_per_position_before_net():
    caps = risk.load_caps(net_liq=100000)
    book = risk.assess([], caps)
    assert risk.headroom_for(book, 10**9) == (False, "per_pos_delta")
    assert risk.headroom_for(book, 1000) == (True, None)


# --------------------------------------------------------------------------
# risk — the per-position cap binds on a TICKER's signed total
#
# `book.py` groups open legs by (underlying, expiry), so a core vertical and the
# shorter-dated short leg sold to finance it land in two groups. The financing
# leg exists to cut the ticker's directional exposure; checking each group alone
# reports a breach the operator has already hedged. These pin the netting.
# --------------------------------------------------------------------------
def _priced(ticker, structure, dn, conid):
    """A PositionRisk carrying exactly `dn` of delta-notional."""
    return risk.mark_position(
        f"{ticker}:{conid}", ticker, structure, 1, [_leg(conid, 1)],
        {conid: Greeks(conid, delta=dn / (100 * 100.0), source=DELTA_SOURCE_IBKR)},
        100.0)


def test_a_financing_overlay_nets_against_its_core_so_no_breach_is_reported():
    """The real GLD case from the 2026-08-14 book: the core alone breaches, the
    ticker's net does not, and only the net is a real risk statement."""
    caps = risk.Caps(per_position=0.25, net=2.50, net_liq=31000.0)  # cap = $7,750
    book = risk.assess([_priced("GLD", "bull_call_spread", 8529.58, 1),
                        _priced("GLD", "single short call", -2226.37, 2)], caps)
    assert book.ticker_exposure["GLD"] == pytest.approx(6303.21)
    assert book.breaches == []


def test_a_ticker_still_breaches_when_the_overlay_does_not_cover_it():
    """The real NVDA case: netting shrinks the breach but does not clear it."""
    caps = risk.Caps(per_position=0.25, net=2.50, net_liq=31000.0)
    book = risk.assess([_priced("NVDA", "single long call", 14204.42, 1),
                        _priced("NVDA", "single short call", -2305.30, 2)], caps)
    assert len(book.breaches) == 1
    b = book.breaches[0]
    assert "exceeds the per-position cap" in b
    # the constituents are named, so the netting is auditable from the report
    assert "single long call +14,204" in b and "single short call -2,305" in b


def test_positions_on_different_tickers_never_net_against_each_other():
    caps = risk.Caps(per_position=0.25, net=2.50, net_liq=31000.0)
    book = risk.assess([_priced("NVDA", "single long call", 9000.0, 1),
                        _priced("TSM", "single short call", -9000.0, 2)], caps)
    assert sorted(book.ticker_exposure) == ["NVDA", "TSM"]
    assert len(book.breaches) == 2


def test_an_unpriced_position_does_not_contaminate_its_tickers_total():
    """A missing delta is unknown, not zero — it must not silently net down a
    ticker whose other leg IS priced."""
    caps = risk.Caps(per_position=0.25, net=2.50, net_liq=31000.0)
    unpriced = risk.mark_position("GLD:9", "GLD", "single short call", 1,
                                  [_leg(9, -1)], {}, 100.0)
    book = risk.assess([_priced("GLD", "bull_call_spread", 8529.58, 1), unpriced], caps)
    assert book.ticker_exposure["GLD"] == pytest.approx(8529.58)
    assert len(book.breaches) == 1
    assert book.complete is False


def test_headroom_nets_a_candidate_against_the_tickers_existing_exposure():
    caps = risk.Caps(per_position=0.25, net=2.50, net_liq=31000.0)  # cap = $7,750
    book = risk.assess([_priced("GLD", "bull_call_spread", 8529.58, 1),
                        _priced("GLD", "single short call", -2226.37, 2)], caps)
    # standalone: $2,000 fits under the cap on its own
    assert risk.headroom_for(book, 2000.0) == (True, None)
    # netted against GLD's existing $6,303 it does not
    assert risk.headroom_for(book, 2000.0, "GLD") == (False, "per_pos_delta")
    # and a ticker with nothing open is unaffected
    assert risk.headroom_for(book, 2000.0, "AMD") == (True, None)


# --------------------------------------------------------------------------
# writer
# --------------------------------------------------------------------------


def test_to_row_emits_exactly_the_contract_columns_in_order():
    row = writer.to_row(_event())
    assert list(row.keys()) == JOURNAL_COLUMNS


def test_to_row_blanks_none_but_keeps_a_real_zero():
    row = writer.to_row(_event(realized_pnl=None, net_price=0.0))
    assert row["realized_pnl"] == ""
    assert row["net_price"] == 0.0


def test_legs_serialise_in_the_backtest_leg_grammar():
    """A journal row must be re-parseable by scripts/backtest/legs.py."""
    from backtest.legs import parse_legs
    row = writer.to_row(_event())
    parsed = parse_legs(row["legs"].replace(" NVDA", "\nNVDA"))
    assert parsed and len(parsed) == 2


def test_write_refuses_rows_that_cannot_be_deduplicated(tmp_path):
    with pytest.raises(ValueError, match="no source_ref"):
        writer.write([_event(source_ref="")], skip_sheets=True,
                     csv_path=tmp_path / "trades.csv")


def test_write_is_idempotent_across_reruns(tmp_path):
    csv_path = tmp_path / "trades.csv"
    ev = [_event()]
    first = writer.write(ev, skip_sheets=True, csv_path=csv_path)
    second = writer.write(ev, skip_sheets=True, csv_path=csv_path)
    assert first["csv_written"] == 1
    assert second["csv_written"] == 0
    assert second["skipped_duplicate"] == 1
    with open(csv_path, newline="", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 1


def test_a_rerun_with_new_fills_appends_only_the_new_ones(tmp_path):
    csv_path = tmp_path / "trades.csv"
    writer.write([_event()], skip_sheets=True, csv_path=csv_path)
    summary = writer.write([_event(), _event(source_ref="ibkr-x.json:e3", ticker="AMD")],
                           skip_sheets=True, csv_path=csv_path)
    assert summary["csv_written"] == 1
    assert summary["skipped_duplicate"] == 1


def test_dry_run_writes_nothing(tmp_path):
    csv_path = tmp_path / "trades.csv"
    summary = writer.write([_event()], dry_run=True, skip_sheets=True, csv_path=csv_path)
    assert summary["would_write"] == 1
    assert not csv_path.exists()


def test_an_explicit_csv_path_never_touches_the_real_journal(tmp_path):
    """Guard against the default-argument trap that let a test write the real book."""
    from scripts.journal.config import TRADES_CSV as REAL
    before = REAL.exists()
    writer.write([_event()], skip_sheets=True, csv_path=tmp_path / "trades.csv")
    assert REAL.exists() == before


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------


def test_candidate_signal_dates_come_from_the_book_not_a_synthetic_calendar():
    """Holidays need no table: only dates the book actually has can be candidates."""
    import pandas as pd
    df = A._normalise(pd.DataFrame({
        "date": ["2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10"],
        "ticker": ["MARKET"] * 4, "play": [""] * 4, "regime": ["RANGE + L-VOL"] * 4}))
    assert A.candidate_signal_dates(df, "2026-08-10", lookback=3) == [
        "2026-08-07", "2026-08-06", "2026-08-05"]


def test_a_stale_analysis_date_across_a_book_gap_is_not_a_candidate():
    """A gap in the book must not become a multi-year lookback.

    The v4 tab cut-over left stray 2024 rows before the live 2026 ones. Counting
    only BOOK dates, the "3 nearest prior" dates for an early-2026 fill were those
    2024 rows — a different era and a different prompt version. Unmatched is the
    correct answer; falsely attributed is not.
    """
    import pandas as pd
    df = A._normalise(pd.DataFrame({
        "date": ["2024-01-10", "2024-01-16", "2024-01-24", "2026-08-11"],
        "ticker": ["MARKET"] * 4, "play": [""] * 4, "regime": ["RANGE + L-VOL"] * 4}))
    assert A.candidate_signal_dates(df, "2026-08-10") == []
    assert A.candidate_signal_dates(df, "2024-01-25") == [
        "2024-01-24", "2024-01-16"]


def test_a_weekend_gap_is_still_within_the_calendar_bound():
    """The calendar bound must not reject an ordinary Friday->Monday lag."""
    import pandas as pd
    df = A._normalise(pd.DataFrame({
        "date": ["2026-08-06", "2026-08-07"],
        "ticker": ["MARKET"] * 2, "play": [""] * 2, "regime": ["RANGE"] * 2}))
    assert A.candidate_signal_dates(df, "2026-08-10") == ["2026-08-07", "2026-08-06"]


def test_market_regime_comes_from_the_market_row_only():
    import pandas as pd
    df = A._normalise(pd.DataFrame({
        "date": ["2026-08-10", "2026-08-10"],
        "ticker": ["MARKET", "NVDA"],
        "play": ["", "bull call spread 170/180"],
        "regime": ["RANGE + L-VOL", "ticker-specific BULL"]}))
    assert A.market_regime_by_date(df)["2026-08-10"] == "RANGE + L-VOL"
    assert list(A.plays_for_date(df, "2026-08-10")["ticker"]) == ["NVDA"]
