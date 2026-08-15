"""
Tests for `scripts/journal/reconcile.py` — Step 2 of the daily trade journal.

Fully offline: every raw pull is built inline (no network, no journal/ reads).
The recurring theme, same as test_journal_core.py, is "never guess silently" —
a dropped settlement row is counted, an unresolved open/close flag becomes
PARTIAL rather than a coin-flip OPEN/CLOSE, and the market regime always comes
off the MARKET row even when a play row on the same date carries a different
(bogus) one.
"""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from scripts.journal import analysis as A
from scripts.journal import rawpull, reconcile
from scripts.journal.config import DELTA_SOURCE_IBKR

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _contract(symbol, expiry, strike, right, multiplier=100):
    return {"symbol": symbol, "sec_type": "OPT", "strike": strike,
            "expiry": expiry, "right": right, "multiplier": multiplier}


def _fill(exec_id, conid, symbol, side, size, price, *, commission=1.0,
          trade_time="2026-08-14T14:30:00Z", order_id=None, open_close="O",
          realized_pnl=None):
    return {"exec_id": exec_id, "conid": conid, "symbol": symbol, "side": side,
            "size": size, "price": price, "commission": commission,
            "net_amount": None, "realized_pnl": realized_pnl,
            "trade_time": trade_time, "order_id": order_id,
            "open_close": open_close}


def _raw(trades, contracts, *, positions=None, greeks=None,
         underlying_prices=None, trade_date="2026-08-14"):
    return {
        "schema_version": rawpull.SCHEMA_VERSION,
        "pulled_at_utc": "2026-08-14T20:15:03Z",
        "trade_date": trade_date,
        "source": "ibkr-cpapi",
        "account_id": "U1",
        "net_liquidation": 100000.0,
        "trades": trades,
        "positions": positions or [],
        "contracts": contracts,
        "greeks": greeks or {},
        "underlying_prices": underlying_prices or {},
        "_path": "ibkr-2026-08-14-1615.json",
    }


def _empty_ac():
    return A._normalise(pd.DataFrame())


# --------------------------------------------------------------------------
# grouping + structure
# --------------------------------------------------------------------------


def test_two_leg_bull_call_spread_reconstructs_as_one_event():
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C"),
                 "2": _contract("NVDA", "2026-10-16", 180.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "BUY", 2, 5.0, order_id="ORD1"),
              _fill("e2", 2, "NVDA", "SELL", 2, 2.0, order_id="ORD1")]
    raw = _raw(trades, contracts)

    events = reconcile.reconcile(raw, ac_df=_empty_ac())

    assert len(events) == 1
    ev = events[0]
    assert ev.ticker == "NVDA"
    assert ev.structure == "bull_call_spread"
    assert ev.contracts == 2
    assert ev.net_price == pytest.approx(3.0)
    assert ev.action == "OPEN"
    assert len(ev.legs) == 2


def test_legs_sharing_a_fill_price_but_different_conid_stay_separate():
    """Conid identity, not a price join, decides grouping.

    Both legs fill at an identical $5.00 — a stage1-style price join could
    plausibly conflate them — but they carry different conids/order_ids/
    underlyings, so they must reconstruct as two separate events.
    """
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C"),
                 "2": _contract("AMD", "2026-10-16", 150.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "BUY", 1, 5.0, order_id="ORD1",
                    trade_time="2026-08-14T14:30:00Z"),
              _fill("e2", 2, "AMD", "BUY", 1, 5.0, order_id="ORD2",
                    trade_time="2026-08-14T15:00:00Z")]
    raw = _raw(trades, contracts)

    events = reconcile.reconcile(raw, ac_df=_empty_ac())

    assert len(events) == 2
    by_ticker = {ev.ticker: ev for ev in events}
    assert set(by_ticker) == {"NVDA", "AMD"}
    assert by_ticker["NVDA"].legs[0].conid == 1
    assert by_ticker["AMD"].legs[0].conid == 2


# --------------------------------------------------------------------------
# action classification
# --------------------------------------------------------------------------


def test_action_open():
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "BUY", 1, 5.0, order_id="ORD1", open_close="O")]
    raw = _raw(trades, contracts)

    ev = reconcile.reconcile(raw, ac_df=_empty_ac())[0]

    assert ev.action == "OPEN"


def test_action_close():
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "SELL", 1, 8.0, order_id="ORD1",
                    open_close="C", realized_pnl=300.0)]
    raw = _raw(trades, contracts)

    ev = reconcile.reconcile(raw, ac_df=_empty_ac())[0]

    assert ev.action == "CLOSE"
    assert ev.realized_pnl == pytest.approx(300.0)


def test_action_roll_when_a_group_has_both_opening_and_closing_legs():
    """Rolling NVDA calls from Aug'26 to Oct'26 in one combo order."""
    contracts = {"1": _contract("NVDA", "2026-08-21", 170.0, "C"),
                 "2": _contract("NVDA", "2026-10-16", 180.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "SELL", 1, 6.0, order_id="ORDR",
                    open_close="C", realized_pnl=100.0),
              _fill("e2", 2, "NVDA", "BUY", 1, 4.0, order_id="ORDR", open_close="O")]
    raw = _raw(trades, contracts)

    ev = reconcile.reconcile(raw, ac_df=_empty_ac())[0]

    assert ev.action == "ROLL"


def test_action_partial_when_the_open_close_flag_is_unresolved():
    """A '?' flag with no realized P&L to corroborate is a genuine unknown —
    reconcile() must say PARTIAL, not silently guess OPEN or CLOSE."""
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "BUY", 1, 5.0, order_id="ORD1",
                    open_close="?", realized_pnl=None)]
    raw = _raw(trades, contracts)

    ev = reconcile.reconcile(raw, ac_df=_empty_ac())[0]

    assert ev.action == "PARTIAL"
    assert "unresolved" in ev.notes


# --------------------------------------------------------------------------
# analysis matching
# --------------------------------------------------------------------------


def test_matches_analysis_play_at_lag_zero():
    ac = A._normalise(pd.DataFrame({
        "date": ["2026-08-07"], "ticker": ["NVDA"],
        "play": ["bull call spread 170/180, 45-60 DTE"],
        "regime": ["ticker-specific BULL"]}))
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C"),
                 "2": _contract("NVDA", "2026-10-16", 180.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "BUY", 1, 5.0, order_id="O1",
                    trade_time="2026-08-10T14:30:00Z"),
              _fill("e2", 2, "NVDA", "SELL", 1, 2.0, order_id="O1",
                    trade_time="2026-08-10T14:30:00Z")]
    raw = _raw(trades, contracts, trade_date="2026-08-10")

    ev = reconcile.reconcile(raw, ac_df=ac)[0]

    assert ev.signal_date == "2026-08-07"
    assert ev.entry_lag_days == 0
    assert ev.match_confidence == "EXACT"
    assert ev.ac_play is not None


def test_matches_analysis_play_at_lag_two():
    """No NVDA play on the two nearer candidate dates; the match is 2 book-dates
    back, so entry_lag_days must be 2, not a calendar day-count."""
    ac = A._normalise(pd.DataFrame({
        "date": ["2026-08-05", "2026-08-06", "2026-08-07"],
        "ticker": ["NVDA", "MARKET", "MARKET"],
        "play": ["bull call spread 170/180, 45-60 DTE", "", ""],
        "regime": ["ticker-specific BULL", "RANGE + L-VOL", "RANGE + L-VOL"]}))
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C"),
                 "2": _contract("NVDA", "2026-10-16", 180.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "BUY", 1, 5.0, order_id="O1",
                    trade_time="2026-08-10T14:30:00Z"),
              _fill("e2", 2, "NVDA", "SELL", 1, 2.0, order_id="O1",
                    trade_time="2026-08-10T14:30:00Z")]
    raw = _raw(trades, contracts, trade_date="2026-08-10")

    ev = reconcile.reconcile(raw, ac_df=ac)[0]

    assert ev.signal_date == "2026-08-05"
    assert ev.entry_lag_days == 2
    assert ev.match_confidence == "EXACT"


def test_market_regime_comes_from_the_market_row_never_a_play_row():
    ac = A._normalise(pd.DataFrame({
        "date": ["2026-08-07", "2026-08-07"], "ticker": ["MARKET", "NVDA"],
        "play": ["", "bull call spread 170/180, 45-60 DTE"],
        "regime": ["BEAR + H-VOL", "ticker-specific BULL (not the market read)"]}))
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C"),
                 "2": _contract("NVDA", "2026-10-16", 180.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "BUY", 1, 5.0, order_id="O1",
                    trade_time="2026-08-10T14:30:00Z"),
              _fill("e2", 2, "NVDA", "SELL", 1, 2.0, order_id="O1",
                    trade_time="2026-08-10T14:30:00Z")]
    raw = _raw(trades, contracts, trade_date="2026-08-10")

    ev = reconcile.reconcile(raw, ac_df=ac)[0]

    assert ev.signal_date == "2026-08-07"
    assert ev.market_regime == "BEAR + H-VOL"


# --------------------------------------------------------------------------
# deployment-ladder tier
# --------------------------------------------------------------------------


def _bull_put_spread_raw(greeks=None):
    # 50 DTE from the 2026-08-14 fill: 2026-08-14 -> 2026-10-03 is 50 days.
    contracts = {"10": _contract("NVDA", "2026-10-03", 90.0, "P"),
                 "11": _contract("NVDA", "2026-10-03", 100.0, "P")}
    trades = [_fill("e10", 10, "NVDA", "BUY", 1, 1.0, order_id="ORDP",
                    trade_time="2026-08-14T14:30:00Z"),
              _fill("e11", 11, "NVDA", "SELL", 1, 3.0, order_id="ORDP",
                    trade_time="2026-08-14T14:30:00Z")]
    return _raw(trades, contracts, greeks=greeks)


def test_bull_put_spread_with_a_real_short_leg_delta_is_tier_b_verified():
    greeks = {
        "10": {"delta": 0.55, "gamma": None, "theta": None, "vega": None,
               "iv": None, "underlying_price": None, "source": DELTA_SOURCE_IBKR},
        "11": {"delta": -0.14, "gamma": None, "theta": None, "vega": None,
               "iv": None, "underlying_price": None, "source": DELTA_SOURCE_IBKR},
    }
    raw = _bull_put_spread_raw(greeks)

    ev = reconcile.reconcile(raw, ac_df=_empty_ac())[0]

    assert ev.structure == "bull_put_spread"
    assert ev.dte_at_entry == pytest.approx(50.0)
    assert ev.tier == "B"
    assert ev.tier_verified is True


def test_bull_put_spread_with_no_delta_available_is_unverified():
    raw = _bull_put_spread_raw(greeks={})

    ev = reconcile.reconcile(raw, ac_df=_empty_ac())[0]

    assert ev.tier in ("B", "C")
    assert ev.tier_verified is False


# --------------------------------------------------------------------------
# settlement rows + source_ref
# --------------------------------------------------------------------------


def test_settlement_rows_are_dropped_and_counted(caplog):
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C")}
    trades = [
        # zero-price, no realized P&L -> expiry/assignment bookkeeping, drop it
        _fill("e1", 1, "NVDA", "BUY", 1, 0.0, order_id="ORD1", open_close="?",
              realized_pnl=0),
        _fill("e2", 1, "NVDA", "SELL", 1, 5.0, order_id="ORD2", open_close="O"),
    ]
    raw = _raw(trades, contracts)

    with caplog.at_level(logging.INFO):
        events = reconcile.reconcile(raw, ac_df=_empty_ac())

    assert len(events) == 1
    assert "e1" not in events[0].source_ref
    assert any("Dropped 1 zero-price settlement row" in r.message
               for r in caplog.records)


def test_a_zero_price_row_with_realized_pnl_is_kept_as_real_expiration_pnl():
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "SELL", 1, 0.0, order_id="ORD1",
                    open_close="C", realized_pnl=-500.0)]
    raw = _raw(trades, contracts)

    events = reconcile.reconcile(raw, ac_df=_empty_ac())

    assert len(events) == 1
    assert events[0].realized_pnl == pytest.approx(-500.0)


# --------------------------------------------------------------------------
# merging legs that share a conid (a contract filled in several parts)
# --------------------------------------------------------------------------
# The broker reports FILLS; the operator runs POSITIONS. Before this merge, a
# 2-contract HYG 77/80 vertical filled in four executions was journalled as a
# "4-leg combo (credit)" at 1 contract and twice the true net price, and three
# fills of one KWEB call as a "3-leg combo". Legs with DISTINCT conids (CRWV)
# are a genuine multi-leg structure and must survive untouched.

# The real 2026-07-24 HYG pull, reduced to its four executions. The exec ids and
# the pull filename are the REAL ones — `test_hyg_source_ref_is_byte_identical_
# to_the_key_already_in_trades_csv` pins the dedup key they produce.
_HYG_PULL = "ibkr-2026-07-24-1648.json"


def _hyg_raw():
    """2 contracts of a 77/80 bull put spread, each leg filled in two parts."""
    contracts = {"700001": _contract("HYG", "2026-09-18", 77.0, "P"),
                 "700002": _contract("HYG", "2026-09-18", 80.0, "P")}
    trades = [
        _fill("112365669", 700001, "HYG", "BUY", 1, 0.60, order_id="ORDH",
              commission=None, trade_time="2026-07-24T09:40:12Z"),
        _fill("112365782", 700002, "HYG", "SELL", 1, 1.60, order_id="ORDH",
              commission=None, trade_time="2026-07-24T09:40:12Z"),
        _fill("112365808", 700001, "HYG", "BUY", 1, 0.66, order_id="ORDH",
              commission=None, trade_time="2026-07-24T09:40:13Z"),
        _fill("112365899", 700002, "HYG", "SELL", 1, 1.72, order_id="ORDH",
              commission=None, trade_time="2026-07-24T09:40:13Z"),
    ]
    raw = _raw(trades, contracts, trade_date="2026-07-24")
    raw["_path"] = _HYG_PULL
    return raw


def _kweb_raw(commissions=(None, None, None)):
    """3 contracts of ONE long call, filled in three parts on one conid."""
    contracts = {"800001": _contract("KWEB", "2027-01-15", 32.0, "C")}
    trades = [
        _fill(f"k{i}", 800001, "KWEB", "BUY", 1, price, order_id="ORDK",
              commission=comm, trade_time=f"2026-08-14T14:3{i}:00Z")
        for i, (price, comm) in enumerate(zip((0.80, 0.83, 0.86), commissions))
    ]
    return _raw(trades, contracts)


def test_hyg_four_fills_on_two_conids_merge_into_a_two_leg_spread():
    ev = reconcile.reconcile(_hyg_raw(), ac_df=_empty_ac())[0]

    assert ev.structure == "bull_put_spread"
    assert len(ev.legs) == 2
    assert ev.contracts == 2
    # classify_structure sums per-leg prices with NO qty weighting, so this is
    # the price of ONE spread (was -2.06 when each fill was its own leg).
    assert ev.net_price == pytest.approx(-1.03)
    assert {lg.conid: lg.qty for lg in ev.legs} == {700001: 2, 700002: -2}
    # signed-quantity-weighted average of the two parts of each leg
    assert {lg.conid: lg.fill_price for lg in ev.legs} == {
        700001: pytest.approx(0.63), 700002: pytest.approx(1.66)}
    assert "4 fills merged into 2 leg(s)" in ev.notes


def test_merging_leaves_net_cash_untouched(monkeypatch):
    """The arithmetic guard: signed-qty weighting makes merging cash-neutral.

    `qty_merged * price_merged == sum(qty_i * price_i)` exactly, so the same
    fixture reconciled with the merge disabled must report the SAME net_cash.
    What merging changes is the split between net_price and contracts, never
    the total cash.
    """
    merged = reconcile.reconcile(_hyg_raw(), ac_df=_empty_ac())[0]

    monkeypatch.setattr(reconcile, "_merge_legs_by_conid",
                        lambda legs: (legs, []))
    control = reconcile.reconcile(_hyg_raw(), ac_df=_empty_ac())[0]

    assert len(control.legs) == 4 and len(merged.legs) == 2
    assert control.contracts == 1 and merged.contracts == 2
    assert merged.net_cash == pytest.approx(control.net_cash)
    assert merged.net_cash == pytest.approx(206.0)


def test_kweb_three_fills_on_one_conid_are_three_contracts_of_a_single_call():
    ev = reconcile.reconcile(_kweb_raw(), ac_df=_empty_ac())[0]

    assert ev.structure == "single long call"
    assert len(ev.legs) == 1
    assert ev.contracts == 3
    assert ev.net_price == pytest.approx(0.83)
    assert ev.net_cash == pytest.approx(-249.0)


def test_a_genuine_three_leg_combo_on_distinct_conids_is_not_collapsed():
    """CRWV 110C/135C/150C — three different contracts, so three real legs."""
    contracts = {"1": _contract("CRWV", "2027-01-15", 110.0, "C"),
                 "2": _contract("CRWV", "2027-01-15", 135.0, "C"),
                 "3": _contract("CRWV", "2026-09-18", 150.0, "C")}
    trades = [_fill("c1", 1, "CRWV", "BUY", 1, 20.0, order_id="ORDC"),
              _fill("c2", 2, "CRWV", "SELL", 1, 8.0, order_id="ORDC"),
              _fill("c3", 3, "CRWV", "SELL", 1, 4.0, order_id="ORDC")]

    ev = reconcile.reconcile(_raw(trades, contracts), ac_df=_empty_ac())[0]

    assert ev.structure == "3-leg combo (debit)"
    assert len(ev.legs) == 3
    assert ev.contracts == 1
    assert "merged" not in ev.notes


def test_hyg_source_ref_is_byte_identical_to_the_key_already_in_trades_csv():
    """The dedup key is computed from the PRE-merge legs, and must not move.

    This exact string is already in journal/trades.csv and the TradeJournal tab
    for the 2026-07-24 HYG event. Any other scheme (merged '+'-joined exec ids,
    a subset, a re-ordering) makes every historically-journalled multi-fill row
    look new and re-appends it.
    """
    ev = reconcile.reconcile(_hyg_raw(), ac_df=_empty_ac())[0]

    assert ev.source_ref == (
        "ibkr-2026-07-24-1648.json:"
        "112365669,112365782,112365808,112365899")


def test_opposite_sign_fills_on_one_conid_leave_the_whole_event_unmerged():
    """Refuse-to-merge: sum(qty) can be 0, and a signed-weighted average across
    opposite signs prices nothing. Better an over-labelled event than a
    fabricated price — and the refusal is stated, never silent."""
    contracts = {"1": _contract("HYG", "2026-09-18", 77.0, "P"),
                 "2": _contract("HYG", "2026-09-18", 80.0, "P")}
    trades = [_fill("x1", 1, "HYG", "BUY", 2, 1.00, order_id="ORDX",
                    commission=None),
              _fill("x2", 1, "HYG", "SELL", 1, 1.20, order_id="ORDX",
                    commission=None),
              _fill("x3", 2, "HYG", "SELL", 1, 2.00, order_id="ORDX",
                    commission=None),
              _fill("x4", 2, "HYG", "SELL", 1, 2.00, order_id="ORDX",
                    commission=None)]

    ev = reconcile.reconcile(_raw(trades, contracts), ac_df=_empty_ac())[0]

    # the WHOLE event is left unmerged, not just the offending conid
    assert len(ev.legs) == 4
    assert "UNMERGED" in ev.notes
    assert "conid(s) [1]" in ev.notes          # names the offender
    assert "merged into" not in ev.notes       # and claims no merge happened
    assert ev.net_cash == pytest.approx(320.0)


def test_a_merged_leg_missing_one_commission_leaves_the_event_uncosted():
    """All-or-nothing, the same rule the event level already applies: a group is
    only as costed as its least-costed part. Summing the known fills and calling
    the missing one zero would report a total that looks whole."""
    partial = reconcile.reconcile(_kweb_raw(commissions=(1.0, 1.0, None)),
                                  ac_df=_empty_ac())[0]
    complete = reconcile.reconcile(_kweb_raw(commissions=(1.0, 1.0, 1.0)),
                                   ac_df=_empty_ac())[0]

    assert partial.commission is None
    assert complete.commission == pytest.approx(3.0)
    assert complete.legs[0].commission == pytest.approx(3.0)


def test_conid_key_of_a_merged_event_carries_no_duplicate_conids():
    """The incidental bug this fixes: conid_key() joins sorted leg conids
    INCLUDING duplicates, so unmerged HYG keyed as '700001|700001|700002|700002'
    while book.py keys the same position '700001|700002'. They could never join,
    so writer.to_row() attached no risk mark to those rows."""
    ev = reconcile.reconcile(_hyg_raw(), ac_df=_empty_ac())[0]

    key = ev.conid_key()
    parts = key.split("|")
    assert parts == sorted(set(parts), key=int)
    # identical to the key book.py builds for the same two open contracts
    assert key == "|".join(str(c) for c in sorted([700002, 700001]))


def test_every_produced_event_has_a_nonempty_source_ref():
    contracts = {"1": _contract("NVDA", "2026-10-16", 170.0, "C"),
                 "2": _contract("AMD", "2026-10-16", 150.0, "C")}
    trades = [_fill("e1", 1, "NVDA", "BUY", 1, 5.0, order_id="ORD1"),
              _fill("e2", 2, "AMD", "BUY", 1, 5.0, order_id="ORD2")]
    raw = _raw(trades, contracts)

    events = reconcile.reconcile(raw, ac_df=_empty_ac())

    assert len(events) == 2
    for ev in events:
        assert ev.source_ref
        assert ev.source_ref.startswith("ibkr-2026-08-14-1615.json:")
