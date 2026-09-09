"""
P1 — closing a spread must not invert its label.

THE BUG (robustness-review §Production loop, row P1). `s02_reconcile.py`
presented every fill's SIGNED QUANTITY to `mapping.classify_structure()` as if
it were a POSITION. On an opening fill the two coincide; on a CLOSING fill they
are opposites, so unwinding a bull call spread (sell the 170, buy back the 180)
was named from the fill signs and journalled as a `bear_call_spread` — which
`ladder_tier()` then vetoes outright. Real rows carry it, e.g.

    2026-08-28 GLD bear_call_spread CLOSE  GLD:2027-01-15:405:C -1 ...:440:C +1
    2026-08-31 IWM bull_put_spread  CLOSE  IWM:2026-10-16:270:P +1 ...:290:P -1

THE FIX. The label names the position the fill group ACTS ON. On a CLOSE
`mapping.position_legs(legs, closing=True)` inverts every leg's sign before the
group is classified, so the structure, the core decomposition, the overlay test
and the tier all describe the position that was closed. There is still one
`ladder_tier()` and one `CONFIDENCES`.

Fully offline — every pull is built inline, nothing reads journal/ or Sheets.
"""

from __future__ import annotations

import csv

import pandas as pd
import pytest

from scripts.journal import s02_reconcile as reconcile
from scripts.journal import s04a_report as report
from scripts.journal import s04b_page as page
from scripts.journal.lib import analysis as A
from scripts.journal.lib import rawpull
from scripts.journal.lib import relabel
from scripts.journal.s03_risk import BookRisk

from scripts.journal.lib import mapping


# --------------------------------------------------------------------------
# helpers (mirrors tests/test_journal_reconcile.py so the two read alike)
# --------------------------------------------------------------------------
def _contract(symbol, expiry, strike, right, multiplier=100):
    return {"symbol": symbol, "sec_type": "OPT", "strike": strike,
            "expiry": expiry, "right": right, "multiplier": multiplier}


def _fill(exec_id, conid, symbol, side, size, price, *, commission=1.0,
          trade_time="2026-08-28T14:30:00Z", order_id=None, open_close="C",
          realized_pnl=None):
    return {"exec_id": exec_id, "conid": conid, "symbol": symbol, "side": side,
            "size": size, "price": price, "commission": commission,
            "net_amount": None, "realized_pnl": realized_pnl,
            "trade_time": trade_time, "order_id": order_id,
            "open_close": open_close}


def _raw(trades, contracts, *, positions=None, greeks=None,
         trade_date="2026-08-28"):
    return {
        "schema_version": rawpull.SCHEMA_VERSION,
        "pulled_at_utc": "2026-08-28T20:15:03Z",
        "trade_date": trade_date,
        "source": "ibkr-cpapi",
        "account_id": "U1",
        "net_liquidation": 100000.0,
        "trades": trades,
        "positions": positions or [],
        "contracts": contracts,
        "greeks": greeks or {},
        "underlying_prices": {},
        "_path": f"ibkr-{trade_date}-1615.json",
    }


def _empty_ac():
    return A._normalise(pd.DataFrame())


def _nvda_contracts():
    return {"1": _contract("NVDA", "2026-10-16", 170.0, "C"),
            "2": _contract("NVDA", "2026-10-16", 180.0, "C")}


def _open_bull_call():
    """The opening order: BUY 170C / SELL 180C."""
    return [_fill("o1", 1, "NVDA", "BUY", 1, 8.0, order_id="ORD1",
                  open_close="O", trade_time="2026-08-14T14:30:00Z"),
            _fill("o2", 2, "NVDA", "SELL", 1, 3.0, order_id="ORD1",
                  open_close="O", trade_time="2026-08-14T14:30:00Z")]


def _close_bull_call():
    """The closing order: SELL the 170C back, BUY the 180C back."""
    return [_fill("c1", 1, "NVDA", "SELL", 1, 11.0, order_id="ORD2",
                  open_close="C", realized_pnl=300.0),
            _fill("c2", 2, "NVDA", "BUY", 1, 5.0, order_id="ORD2",
                  open_close="C", realized_pnl=-200.0)]


# --------------------------------------------------------------------------
# 1. Reproduction — the fill-sign reading is what produced `bear_call_spread`
# --------------------------------------------------------------------------
def test_reproduce_fill_sign_classification_inverts_a_closed_bull_call():
    """Pins the OLD behaviour at its source: sign-of-fill, not sign-of-position.

    This is the pre-fix reading written out literally — classifying the closing
    fills WITHOUT `position_legs(..., closing=True)` — so the regression this
    file guards is visible rather than asserted by absence. The fills' own signs
    name the MIRROR of the position that was closed.
    """
    closing_legs, _dropped = reconcile._fills_to_legs(
        _raw(_close_bull_call(), _nvda_contracts()))
    legs = [leg for _fill_dict, leg in closing_legs]

    label, *_rest = mapping.classify_structure(legs)
    assert label == "bear_call_spread", "the documented P1 symptom"

    # ...and orienting the same legs to the position they close names it right
    oriented = mapping.position_legs(legs, closing=True)
    assert mapping.classify_structure(oriented)[0] == "bull_call_spread"

    # and that label is what the ladder vetoes
    tier, _partial, reason = mapping.ladder_tier(label, "RANGE + L-VOL")
    assert (tier, reason) == ("VETO", "bear_call_spread intake veto")


# --------------------------------------------------------------------------
# 2. The fix — the CLOSE event names the position it closed
# --------------------------------------------------------------------------
def test_closing_a_bull_call_spread_is_labelled_bull_call_spread():
    raw = _raw(_close_bull_call(), _nvda_contracts())

    events = reconcile.reconcile(raw, ac_df=_empty_ac())

    assert len(events) == 1
    ev = events[0]
    assert ev.action == "CLOSE"
    assert ev.structure == "bull_call_spread"
    assert ev.tier != "VETO"
    assert "closes" in ev.notes


def test_close_event_keeps_the_fills_own_cash_not_the_positions_price():
    """Orientation renames the structure; it must never re-sign the money.

    Selling the 170C at 11 and buying the 180C back at 5 is a $6 CREDIT. The
    label flips, `net_price` and `net_cash` do not.
    """
    raw = _raw(_close_bull_call(), _nvda_contracts())

    ev = reconcile.reconcile(raw, ac_df=_empty_ac())[0]

    assert ev.net_price == pytest.approx(-6.0)
    assert ev.net_cash == pytest.approx(600.0 - 2.0)
    assert ev.realized_pnl == pytest.approx(100.0)


def test_open_then_close_of_one_position_agree_on_the_structure():
    """The round trip is the point: both halves must name the same spread."""
    contracts = _nvda_contracts()
    opened = reconcile.reconcile(_raw(_open_bull_call(), contracts,
                                      trade_date="2026-08-14"),
                                 ac_df=_empty_ac())[0]
    closed = reconcile.reconcile(_raw(_close_bull_call(), contracts),
                                 ac_df=_empty_ac())[0]

    assert (opened.action, closed.action) == ("OPEN", "CLOSE")
    assert opened.structure == closed.structure == "bull_call_spread"
    assert opened.conid_key() == closed.conid_key()


def test_closing_a_bear_put_spread_is_not_renamed_bull_put_spread():
    """The real 2026-08-31 IWM row: +270P / -290P closing a LONG put spread."""
    contracts = {"1": _contract("IWM", "2026-10-16", 270.0, "P"),
                 "2": _contract("IWM", "2026-10-16", 290.0, "P")}
    trades = [_fill("c1", 1, "IWM", "BUY", 1, 1.2, order_id="ORD9",
                    realized_pnl=-50.0),
              _fill("c2", 2, "IWM", "SELL", 1, 9.4, order_id="ORD9",
                    realized_pnl=420.0)]

    ev = reconcile.reconcile(_raw(trades, contracts), ac_df=_empty_ac())[0]

    assert ev.action == "CLOSE"
    assert ev.structure == "bear_put_spread"


def test_closing_a_short_call_is_a_short_call_not_a_long_one():
    """The real 2026-08-28 GLD row: a BUY that closes a SOLD call."""
    contracts = {"1": _contract("GLD", "2026-09-18", 445.0, "C")}
    trades = [_fill("c1", 1, "GLD", "BUY", 1, 0.4, order_id="ORD7",
                    realized_pnl=180.0)]

    ev = reconcile.reconcile(_raw(trades, contracts), ac_df=_empty_ac())[0]

    assert ev.action == "CLOSE"
    assert ev.structure == "single short call"


def test_selling_to_close_a_long_call_stays_a_long_call():
    contracts = {"1": _contract("TSM", "2026-09-11", 470.0, "C")}
    trades = [_fill("c1", 1, "TSM", "SELL", 1, 12.0, order_id="ORD8",
                    realized_pnl=300.0)]

    ev = reconcile.reconcile(_raw(trades, contracts), ac_df=_empty_ac())[0]

    assert ev.structure == "single long call"


# --------------------------------------------------------------------------
# 3. Nothing else moves
# --------------------------------------------------------------------------
def test_opening_fills_are_untouched_by_the_orientation_rule():
    ev = reconcile.reconcile(_raw(_open_bull_call(), _nvda_contracts(),
                                  trade_date="2026-08-14"),
                             ac_df=_empty_ac())[0]

    assert ev.structure == "bull_call_spread"
    assert ev.action == "OPEN"
    assert ev.net_price == pytest.approx(5.0)
    assert "closes" not in ev.notes


def test_a_roll_is_not_oriented_and_says_so():
    """A ROLL opens one leg while closing another — there is no single position
    for the label to name, so the fill-sign reading stands and is disclosed."""
    contracts = _nvda_contracts()
    trades = [_fill("r1", 1, "NVDA", "SELL", 1, 11.0, order_id="ORDR",
                    open_close="C", realized_pnl=300.0),
              _fill("r2", 2, "NVDA", "BUY", 1, 5.0, order_id="ORDR",
                    open_close="O")]

    ev = reconcile.reconcile(_raw(trades, contracts), ac_df=_empty_ac())[0]

    assert ev.action == "ROLL"
    assert "fill signs" in ev.notes


def test_a_partial_is_not_oriented():
    contracts = _nvda_contracts()
    trades = [_fill("p1", 1, "NVDA", "SELL", 1, 11.0, order_id="ORDP",
                    open_close="?"),
              _fill("p2", 2, "NVDA", "BUY", 1, 5.0, order_id="ORDP",
                    open_close="?")]

    ev = reconcile.reconcile(_raw(trades, contracts), ac_df=_empty_ac())[0]

    assert ev.action == "PARTIAL"
    assert "fill signs" in ev.notes


# --------------------------------------------------------------------------
# 4. The financed multi-leg case still tiers off `core_structure`
# --------------------------------------------------------------------------
def _crwv_financed_contracts():
    return {"1": _contract("CRWV", "2027-01-15", 110.0, "C"),
            "2": _contract("CRWV", "2027-01-15", 135.0, "C"),
            "3": _contract("CRWV", "2026-09-18", 150.0, "C")}


def test_closing_a_financed_spread_recovers_the_core_vertical():
    """Unwinding the 110/135 core plus buying back the 150 financing leg."""
    trades = [_fill("c1", 1, "CRWV", "SELL", 1, 30.0, order_id="ORDC"),
              _fill("c2", 2, "CRWV", "BUY", 1, 20.0, order_id="ORDC"),
              _fill("c3", 3, "CRWV", "BUY", 1, 5.0, order_id="ORDC")]

    ev = reconcile.reconcile(_raw(trades, _crwv_financed_contracts()),
                             ac_df=_empty_ac())[0]

    assert ev.action == "CLOSE"
    assert ev.core_structure == "bull_call_spread"
    # tiered off the core, not off "3-leg combo (...)" -> Tier-C residual
    assert ev.tier in {"A", "B"}
    assert ev.net_price == pytest.approx(-5.0)


def test_opening_the_same_financed_spread_still_decomposes():
    trades = [_fill("o1", 1, "CRWV", "BUY", 1, 30.0, order_id="ORDO",
                    open_close="O"),
              _fill("o2", 2, "CRWV", "SELL", 1, 20.0, order_id="ORDO",
                    open_close="O"),
              _fill("o3", 3, "CRWV", "SELL", 1, 5.0, order_id="ORDO",
                    open_close="O")]

    ev = reconcile.reconcile(_raw(trades, _crwv_financed_contracts()),
                             ac_df=_empty_ac())[0]

    assert ev.action == "OPEN"
    assert ev.core_structure == "bull_call_spread"


# --------------------------------------------------------------------------
# 5. The match vocabulary is unchanged: CORE never becomes EXACT,
#    OVERLAY stays out of the matched/unmatched tally
# --------------------------------------------------------------------------
def _ac_book(rows):
    return A._normalise(pd.DataFrame(rows))


def test_core_is_not_promoted_to_exact_even_when_the_core_strikes_agree():
    book = _ac_book([
        {"date": "2026-08-27", "ticker": "MARKET", "play": "",
         "regime": "RANGE + L-VOL", "horizon": ""},
        {"date": "2026-08-27", "ticker": "CRWV",
         "play": "bull call spread 110/135, 120 DTE", "horizon": "120"},
    ])
    trades = [_fill("c1", 1, "CRWV", "SELL", 1, 30.0, order_id="ORDC"),
              _fill("c2", 2, "CRWV", "BUY", 1, 20.0, order_id="ORDC"),
              _fill("c3", 3, "CRWV", "BUY", 1, 5.0, order_id="ORDC")]

    ev = reconcile.reconcile(_raw(trades, _crwv_financed_contracts()),
                             ac_df=book)[0]

    assert ev.match_confidence == "CORE"
    assert ev.match_confidence in mapping.CONFIDENCES


def test_closing_an_overlay_is_still_reported_as_overlay():
    """Buying back a financing call sold over a spread at another expiry.

    The orientation rule makes the label say `single short call (overlay)` —
    the thing that was closed — and OVERLAY still keeps the row out of both
    sides of the matched/unmatched ratio.
    """
    contracts = {"1": _contract("CRWV", "2026-09-11", 116.0, "C"),
                 "2": _contract("CRWV", "2027-01-15", 110.0, "C")}
    positions = [{"conid": 2, "position": 1.0}]
    trades = [_fill("c1", 1, "CRWV", "BUY", 1, 0.5, order_id="ORDV",
                    realized_pnl=120.0)]

    ev = reconcile.reconcile(_raw(trades, contracts, positions=positions),
                             ac_df=_empty_ac())[0]

    assert ev.structure == "single short call (overlay)"
    assert ev.match_confidence == "OVERLAY"


def test_a_matched_close_says_it_is_not_a_fresh_play_attempt():
    """A side effect of the orientation fix, disclosed on the row itself.

    Before the fix a closed spread carried the mirror label and scored NONE by
    accident; now it matches the play it unwinds. The match is the more
    informative fact and it is kept, but a CLOSE is not a second attempt to
    trade that play — any "did I trade the plan" tally counts attempts on
    `action == OPEN`. The vocabulary is untouched: no new confidence value.
    """
    book = _ac_book([
        {"date": "2026-08-27", "ticker": "MARKET", "play": "",
         "regime": "RANGE + L-VOL", "horizon": ""},
        {"date": "2026-08-27", "ticker": "NVDA",
         "play": "bull call spread 170/180, 50 DTE", "horizon": "50"},
    ])

    ev = reconcile.reconcile(_raw(_close_bull_call(), _nvda_contracts()),
                             ac_df=book)[0]

    assert (ev.action, ev.structure) == ("CLOSE", "bull_call_spread")
    assert ev.match_confidence == "EXACT"
    assert ev.match_confidence in mapping.CONFIDENCES
    assert "not a fresh attempt to trade it" in ev.notes
    assert "action == OPEN" in ev.notes


def test_open_then_close_of_the_same_matched_play_reports_one_attempt_not_two():
    """s04a_report.py §3's headline follow-on to the P1 fix.

    A CLOSE can now match EXACT/STRUCTURE/CORE/SUBSTITUTED same as an OPEN
    (the test above), and a naive "every event is an attempt" tally would
    report this one round-trip as 2/2. It is one attempt: open it, close it.
    `s04a_report.build()` must print 1/1, and `s04b_page.py`'s independent
    recomputation of the same figure must agree with it (no ReconcileError).
    """
    book = _ac_book([
        {"date": "2026-08-13", "ticker": "MARKET", "play": "",
         "regime": "RANGE + L-VOL", "horizon": ""},
        {"date": "2026-08-13", "ticker": "NVDA",
         "play": "bull call spread 170/180, 50 DTE", "horizon": "50"},
        {"date": "2026-08-27", "ticker": "MARKET", "play": "",
         "regime": "RANGE + L-VOL", "horizon": ""},
        {"date": "2026-08-27", "ticker": "NVDA",
         "play": "bull call spread 170/180, 50 DTE", "horizon": "50"},
    ])
    trades = _open_bull_call() + _close_bull_call()
    events = reconcile.reconcile(_raw(trades, _nvda_contracts()), ac_df=book)

    assert [e.action for e in events] == ["OPEN", "CLOSE"]
    # Both legs of the round trip match the same play — the scenario the old
    # "every event is an attempt" tally would have double-counted.
    assert all(e.match_confidence == "EXACT" for e in events)

    risk_book = BookRisk(positions=[], unpriced=[], caps=None)
    meta = dict(date="2026-08-28", pull_source="ibkr-cpapi",
               pull_file="ibkr-2026-08-28-1615.json", analysis_source="sheets",
               net_liquidation=100000.0)
    text = report.build(events, risk_book, meta)
    assert "**1/1 play attempt(s) matched an analysis play**" in text
    assert "2/2 play attempt(s)" not in text
    assert "(attempts counted on OPEN events only)" in text

    computed = page.compute_figures(events, risk_book)
    assert (computed["attempts"], computed["matched"]) == (1, 1)
    extracted = page.extract_report_figures(text)
    assert page.reconcile(computed, extracted) == []


def test_an_opening_match_carries_no_close_disclaimer():
    book = _ac_book([
        {"date": "2026-08-13", "ticker": "MARKET", "play": "",
         "regime": "RANGE + L-VOL", "horizon": ""},
        {"date": "2026-08-13", "ticker": "NVDA",
         "play": "bull call spread 170/180, 50 DTE", "horizon": "50"},
    ])

    ev = reconcile.reconcile(
        _raw(_open_bull_call(), _nvda_contracts(), trade_date="2026-08-14"),
        ac_df=book)[0]

    assert (ev.action, ev.match_confidence) == ("OPEN", "EXACT")
    assert "not a fresh attempt to trade it" not in ev.notes


# --------------------------------------------------------------------------
# 6. Offline re-derivation of rows already in journal/trades.csv
# --------------------------------------------------------------------------
_HEADER = ["date", "ticker", "structure", "action", "legs", "net_price",
           "ac_structure", "tier", "market_regime", "dte_at_entry"]


def _write_csv(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _HEADER})
    return path


def test_parse_legs_reads_the_canonical_leg_grammar():
    parsed = relabel.parse_legs(
        "GLD:2027-01-15:405:C -1 GLD:2027-01-15:440:C +1")
    assert [(p["strike"], p["right"], p["qty"]) for p in parsed] == [
        (405.0, "C", -1), (440.0, "C", 1)]
    assert relabel.parse_legs("garbage") is None


def test_rederive_reports_the_gld_and_iwm_rows_and_leaves_opens_alone(tmp_path):
    csv_path = _write_csv(tmp_path / "trades.csv", [
        {"date": "2026-08-28", "ticker": "GLD", "structure": "bear_call_spread",
         "action": "CLOSE", "net_price": "-4.0", "tier": "VETO",
         "market_regime": "RANGE + L-VOL", "dte_at_entry": "140",
         "legs": "GLD:2027-01-15:405:C -1 GLD:2027-01-15:440:C +1"},
        {"date": "2026-08-31", "ticker": "IWM", "structure": "bull_put_spread",
         "action": "CLOSE", "net_price": "8.2", "tier": "C",
         "market_regime": "RANGE + L-VOL", "dte_at_entry": "46",
         "legs": "IWM:2026-10-16:270:P +1 IWM:2026-10-16:290:P -1"},
        {"date": "2026-08-17", "ticker": "AMD", "structure": "bull_call_spread",
         "action": "OPEN", "net_price": "12.0", "tier": "A",
         "market_regime": "RANGE + L-VOL", "dte_at_entry": "60",
         "legs": "AMD:2026-10-16:510:C +1 AMD:2026-10-16:560:C -1"},
    ])

    diffs, summary = relabel.rederive(csv_path)

    assert summary["rows"] == 3
    assert summary["close_rows"] == 2
    assert summary["structure_changed"] == 2
    changed = {d.ticker: d for d in diffs}
    assert changed["GLD"].new_structure == "bull_call_spread"
    assert changed["GLD"].old_tier == "VETO"
    assert changed["GLD"].new_tier in {"A", "B"}
    assert changed["IWM"].new_structure == "bear_put_spread"
    assert "AMD" not in changed


def test_rederive_never_writes_to_the_csv_it_reads(tmp_path):
    csv_path = _write_csv(tmp_path / "trades.csv", [
        {"date": "2026-08-28", "ticker": "GLD", "structure": "bear_call_spread",
         "action": "CLOSE", "net_price": "-4.0", "tier": "VETO",
         "market_regime": "RANGE + L-VOL", "dte_at_entry": "140",
         "legs": "GLD:2027-01-15:405:C -1 GLD:2027-01-15:440:C +1"},
    ])
    before = csv_path.read_bytes()

    relabel.rederive(csv_path)

    assert csv_path.read_bytes() == before


def test_rederive_refuses_a_row_whose_label_needs_per_leg_prices(tmp_path):
    """A 3-leg group's core decomposition reads each leg's own price, and
    trades.csv records only the group's net. Reported, never guessed."""
    csv_path = _write_csv(tmp_path / "trades.csv", [
        {"date": "2026-08-28", "ticker": "CRWV",
         "structure": "3-leg combo (credit)", "action": "CLOSE",
         "net_price": "-5.0", "tier": "C", "market_regime": "RANGE + L-VOL",
         "dte_at_entry": "140",
         "legs": ("CRWV:2027-01-15:110:C -1 CRWV:2027-01-15:135:C +1 "
                  "CRWV:2026-09-18:150:C +1")},
    ])

    diffs, summary = relabel.rederive(csv_path)

    assert summary["not_rederivable"] == 1
    assert summary["structure_changed"] == 0
    assert diffs == []


def test_rederive_flips_the_debit_credit_token_from_the_recorded_net(tmp_path):
    """The real 2026-08-25 AMD row: two SELLs closing a LONG (debit) strangle.

    `mixed C/P vertical (...)` takes its side from the group's net, and the
    CSV records that net even though it records no per-leg price.
    """
    csv_path = _write_csv(tmp_path / "trades.csv", [
        {"date": "2026-08-25", "ticker": "AMD",
         "structure": "mixed C/P vertical (credit)", "action": "CLOSE",
         "net_price": "-4.05", "tier": "C", "market_regime": "RANGE + L-VOL",
         "dte_at_entry": "1",
         "legs": "AMD:2026-08-26:472.5:C -1 AMD:2026-08-26:432.5:P -1"},
    ])

    diffs, summary = relabel.rederive(csv_path)

    assert summary["structure_changed"] == 1
    assert diffs[0].new_structure == "mixed C/P vertical (debit)"


def test_rederive_refuses_a_side_it_cannot_recover(tmp_path):
    csv_path = _write_csv(tmp_path / "trades.csv", [
        {"date": "2026-08-25", "ticker": "AMD",
         "structure": "mixed C/P vertical (credit)", "action": "CLOSE",
         "net_price": "", "tier": "C", "market_regime": "RANGE + L-VOL",
         "dte_at_entry": "1",
         "legs": "AMD:2026-08-26:472.5:C -1 AMD:2026-08-26:432.5:P -1"},
    ])

    diffs, summary = relabel.rederive(csv_path)

    assert (diffs, summary["not_rederivable"]) == ([], 1)


def test_rederive_drops_an_overlay_suffix_it_cannot_recompute(tmp_path):
    """The REACHABLE shape: `_is_overlay()` only fires on a short leg, so a
    recorded `(overlay)` on a CLOSE came from a SELL-to-close — the position
    closed was LONG and cannot have been an overlay. Re-appending the suffix
    would print `single long call (overlay)`, which the live pipeline can never
    emit; the suffix is dropped and the row counted as `overlay_unknown`.
    """
    csv_path = _write_csv(tmp_path / "trades.csv", [
        {"date": "2026-08-28", "ticker": "CRWV",
         "structure": "single short call (overlay)", "action": "CLOSE",
         "net_price": "0.5", "tier": "C", "market_regime": "RANGE + L-VOL",
         "dte_at_entry": "14", "legs": "CRWV:2026-09-11:116:C -1"},
    ])

    diffs, summary = relabel.rederive(csv_path)

    assert len(diffs) == 1
    assert diffs[0].new_structure == "single long call"
    assert "(overlay)" not in diffs[0].new_structure
    assert diffs[0].overlay_dropped is True
    assert summary["overlay_unknown"] == 1


def test_rederive_never_reports_a_label_the_live_pipeline_cannot_emit(tmp_path):
    """`(overlay)` is only ever appended to a SHORT single leg, so a re-derived
    label pairing it with a long one would be fiction. Guarded on both signs.
    """
    csv_path = _write_csv(tmp_path / "trades.csv", [
        {"date": "2026-08-28", "ticker": "CRWV",
         "structure": "single short call (overlay)", "action": "CLOSE",
         "net_price": "0.5", "tier": "C", "market_regime": "RANGE + L-VOL",
         "dte_at_entry": "14", "legs": "CRWV:2026-09-11:116:C -1"},
        {"date": "2026-08-29", "ticker": "CRWV",
         "structure": "single long put (overlay)", "action": "CLOSE",
         "net_price": "0.5", "tier": "C", "market_regime": "RANGE + L-VOL",
         "dte_at_entry": "14", "legs": "CRWV:2026-09-11:116:P +1"},
    ])

    diffs, summary = relabel.rederive(csv_path)

    for d in diffs:
        assert not (d.new_structure.startswith("single long")
                    and d.new_structure.endswith("(overlay)"))
        assert "(overlay)" not in d.new_structure
    assert summary["overlay_unknown"] == 2


def test_rederive_leaves_a_close_without_a_recorded_suffix_unflagged(tmp_path):
    """The mirror case is under-reported on purpose: a genuine overlay close
    (BUY-to-close a short leg) was recorded WITHOUT a suffix and re-derives
    without one, so it is not counted — the bucket is recorded suffixes only.
    """
    csv_path = _write_csv(tmp_path / "trades.csv", [
        {"date": "2026-08-28", "ticker": "CRWV",
         "structure": "single long call", "action": "CLOSE",
         "net_price": "-0.5", "tier": "C", "market_regime": "RANGE + L-VOL",
         "dte_at_entry": "14", "legs": "CRWV:2026-09-11:116:C +1"},
    ])

    diffs, summary = relabel.rederive(csv_path)

    assert summary["overlay_unknown"] == 0
    assert all(d.overlay_dropped is False for d in diffs)
