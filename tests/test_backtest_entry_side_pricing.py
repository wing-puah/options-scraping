"""Side-aware ENTRY pricing on a one-sided quote, and the debit-priced-to-a-credit
gate (2026-09-19; extended over the entry-day `Open` print 2026-09-22).

The failure both fixes answer is one proxy row: HYG 2025-04-09. The short 72P had
no bar on the fill day, so the entry fell through to a six-day-old `bid 0 / ask
2.68` snap; `_zero_bid_mark` — a LIQUIDATION rule — re-marked it to 1.34 and
handed a leg being SOLD that much as premium RECEIVED. The bear put spread's
entry went to −0.37, `_exit_basis` keyed it CREDIT, and it booked +100%.

Two separate claims are pinned here:

  entry  a leg whose entry-day quote is ONE-SIDED is priced on the side it
         trades — bid (0) when sold — even when the day printed an `Open`
         (since 2026-09-22). Since 2026-09-24 a one-sided quote is a JUNK
         quote (tests/test_backtest_junk_quotes.py): a BOUGHT leg no longer
         pays the ask; it fills at the day's trade or is refused. A clean
         two-sided quote, and a row with no quote data at all, price exactly
         as they did before, Open print first.
  gate   a structure whose NAME fixes it as a debit, priced to a net credit, is
         refused rather than written, and the refusal is recorded.

Everything runs on synthetic rows — no network, no option-history cache.
"""
from datetime import date, timedelta

import pytest

import backtest as bt
from backtest import simulate as sim
from backtest.classify import DEBIT_STRUCTURES
from backtest.proxy import _note_refusal

SIGNAL = date(2026, 6, 1)           # Monday
ENTRY = date(2026, 6, 2)            # the next weekday — entry_timing "next_open"
EXP = date(2026, 7, 17)
LONG_KEY = ("IWM", "Put", 76.0, "2026-07-17")
SHORT_KEY = ("IWM", "Put", 72.0, "2026-07-17")


def _cand():
    return {"ticker": "IWM", "signal_date": SIGNAL, "play": "bear put spread",
            "market_regime": ""}


def _entry_row():
    return {"Strike": 76.0, "DTE": (EXP - ENTRY).days, "IV": "30",
            "Price~": "78.0", "Trade": 1.0, "Expires": EXP.isoformat(),
            "Delta": "-0.40", "_entry_date": ENTRY}


def _row(mark, bid=None, ask=None, open_="", latest=None, volume=None):
    """A Barchart history row. A bid/ask left as None means the COLUMN IS ABSENT —
    the older-cache / no-quote-data case, which must never read as a zero bid.
    ``volume``/``latest`` make the day a TRADED one for the junk-quote rule."""
    row = {"Open": open_, "_mark": mark}
    if latest is not None:
        row["Latest"] = str(latest)
    if volume is not None:
        row["Volume"] = str(volume)
    if bid is not None:
        row["Bid"] = str(bid)
    if ask is not None:
        row["Ask"] = str(ask)
    return row


def _legs(*specs):
    return [bt.Leg(int(q), "IWM", EXP, float(k), "Put") for (q, k) in specs]


def _cfg(**kw):
    base = {"profit_target": None, "stop_loss": None, "contracts": 1,
            "path_cap_days": 3, "entry_sources": ["barchart"],
            "exit_sources": ["barchart"]}
    base.update(kw)
    return base


def _run(legs, details, cfg=None, structure="bear_put_spread", refusal=None):
    series = {k: sorted((d, r["_mark"]) for d, r in rows.items())
              for k, rows in details.items()}
    return sim._simulate(_cand(), legs, _entry_row(), {}, series, cfg or _cfg(),
                         structure=structure,
                         barchart_details=details, refusal=refusal)


def _entry_net(result) -> float:
    """The position's net entry price, read back off the result row."""
    return float(result["entry_option_price"])


# ── The unit: which quotes the side-aware rule claims, and which it leaves alone ──

@pytest.mark.parametrize("bid,ask,qty,expected", [
    # A REAL zero bid: the quote exists and its bid side is 0.
    ("0.00", "2.68", -1, 0.0),      # sold into a 0 bid → nothing is received
    ("0.00", "2.68", +1, 2.68),     # bought → pays the ask
    ("0.00", "0.00", -1, 0.0),      # 0 × 0 → worthless either way
    ("0.00", "0.00", +1, 0.0),
    # A bid column present but blank, with a live offer: no bid is quoted.
    (None, "2.68", -1, 0.0),
    (None, "2.68", +1, 2.68),
    # A genuine two-sided quote — pricing is UNCHANGED, both signs.
    ("1.90", "2.10", -1, None),
    ("1.90", "2.10", +1, None),
    # NO QUOTE DATA. Not a zero bid, and must never be read as one.
    (None, None, -1, None),
    (None, None, +1, None),
    ("1.90", None, -1, None),       # a bid with no ask says nothing about the fill
])
def test_entry_side_mark_branches(bid, ask, qty, expected):
    assert sim._entry_side_mark(_row(3.0, bid=bid, ask=ask), qty) == expected


def test_entry_side_mark_and_zero_bid_mark_disagree_by_sign():
    """The whole point of the split: the liquidation rule is sign-independent, the
    entry rule is not. `_zero_bid_mark` stays what it is — it is the daily mark."""
    row = _row(0.45, bid="0.00", ask="2.68")
    assert sim._zero_bid_mark(row) == 1.34            # the HYG number, unchanged
    assert sim._entry_side_mark(row, -1) == 0.0       # but not what a SELL fills at
    assert sim._entry_side_mark(row, +1) == 2.68


# ── (a)/(b) the entry path, on a carried quote with no bar on the fill day ───────
#
# This is the HYG shape exactly: the leg has no row on the entry day, so entry
# pricing falls through to `_price_leg`'s carry-forward and the quote it re-marks
# is an older snap.

def _carried_quote_case(short_qty_first=True, bid="0.00", ask="2.68"):
    long_rows = {ENTRY: _row(0.97, bid="0.90", ask="1.04", open_="0.97")}
    short_rows = {date(2026, 5, 27): _row(0.45, bid=bid, ask=ask)}
    details = {LONG_KEY: long_rows, SHORT_KEY: short_rows}
    for rows in (long_rows, short_rows):
        for d in (date(2026, 6, 3), date(2026, 6, 4)):
            rows.setdefault(d, _row(1.0, bid="0.90", ask="1.10"))
    return details


def test_short_leg_with_a_zero_bid_contributes_nothing_at_entry():
    details = _carried_quote_case()
    res = _run(_legs(("+1", 76), ("-1", 72)), details)
    # Long 0.97 at its Open print, short 0.00 at a bid of 0 → a 0.97 DEBIT.
    # Before the fix the short leg came in at ask/2 = 1.34 and the spread priced
    # to a −0.37 CREDIT.
    assert _entry_net(res) == pytest.approx(0.97)
    assert res["exit_basis"] != "CREDIT"


def _bought_zero_bid_carried(**long_kw):
    details = {LONG_KEY: {date(2026, 5, 27): _row(0.45, bid="0.00", ask="2.68", **long_kw)},
               SHORT_KEY: {ENTRY: _row(0.30, bid="0.25", ask="0.35", open_="0.30")}}
    for d in (date(2026, 6, 3), date(2026, 6, 4)):
        details[LONG_KEY][d] = _row(1.0, bid="0.90", ask="1.10")
        details[SHORT_KEY][d] = _row(0.4, bid="0.35", ask="0.45")
    return details


def test_long_leg_on_a_junk_quote_with_no_trade_is_refused():
    """Until 2026-09-24 a bought leg into `bid 0 / ask 2.68` paid the ask. A
    bid-less quote is JUNK, and its ask is not a price anyone paid — with no
    trade that day there is no real entry price, so the play is refused."""
    refusal = {}
    res = _run(_legs(("+1", 76), ("-1", 72)), _bought_zero_bid_carried(),
               refusal=refusal)
    assert res == {}
    assert refusal["reason"] == sim.JUNK_ENTRY_REFUSAL == "junk_entry_quote"


def test_long_leg_on_a_junk_quote_that_traded_fills_at_the_trade():
    """The same carried junk quote on a day the contract TRADED at 0.45: the
    fill is that Latest (never the carried day's Open), the short leg its own
    two-sided Open."""
    res = _run(_legs(("+1", 76), ("-1", 72)),
               _bought_zero_bid_carried(latest="0.45", volume="12"))
    assert _entry_net(res) == pytest.approx(0.15)
    assert res["entry_source"] == "barchart_last+barchart_open"


# ── (c)/(d) everything else at entry is byte-for-byte what it was ───────────────

def test_two_sided_entry_quote_is_unchanged():
    details = {LONG_KEY: {ENTRY: _row(1.00, bid="0.95", ask="1.05", open_="1.00")},
               SHORT_KEY: {ENTRY: _row(0.40, bid="0.35", ask="0.45", open_="0.40")}}
    for d in (date(2026, 6, 3), date(2026, 6, 4)):
        details[LONG_KEY][d] = _row(1.0, bid="0.95", ask="1.05")
        details[SHORT_KEY][d] = _row(0.4, bid="0.35", ask="0.45")
    res = _run(_legs(("+1", 76), ("-1", 72)), details)
    assert _entry_net(res) == pytest.approx(0.60)
    assert "barchart_side" not in res["entry_leg_detail"]


def test_a_row_with_no_quote_columns_is_not_treated_as_a_zero_bid():
    """An older cache file carries no Bid/Ask at all. That is NO QUOTE DATA, and
    the existing fallback (the row's own mark) must still decide — a short leg
    here must NOT be handed a fabricated 0."""
    details = {LONG_KEY: {date(2026, 5, 27): _row(1.10)},
               SHORT_KEY: {date(2026, 5, 27): _row(0.50)}}
    for d in (ENTRY, date(2026, 6, 3), date(2026, 6, 4)):
        details[LONG_KEY][d] = _row(1.10)
        details[SHORT_KEY][d] = _row(0.50)
    res = _run(_legs(("+1", 76), ("-1", 72)), details)
    assert _entry_net(res) == pytest.approx(0.60)     # 1.10 − 0.50, the marks


def _open_print_case(long_quote, short_quote):
    """Both legs PRINTED an Open on the entry day; the quotes are the variable."""
    details = {LONG_KEY: {ENTRY: _row(0.97, open_="0.97", **long_quote)},
               SHORT_KEY: {ENTRY: _row(0.45, open_="0.45", **short_quote)}}
    for d in (date(2026, 6, 3), date(2026, 6, 4)):
        details[LONG_KEY][d] = _row(1.0, bid="0.90", ask="1.10")
        details[SHORT_KEY][d] = _row(0.4, bid="0.35", ask="0.45")
    return details


def test_a_sold_leg_with_a_zero_bid_is_not_filled_at_its_open_print():
    """next-steps §0 item 9, decided 2026-09-22. The short leg printed 0.45 at the
    open, but the day's own quote is `0 × 2.68`: nothing is bid, so nothing is
    received. The side rule now PRECEDES the Open print. Before, this entry was
    0.97 − 0.45 = 0.52 — the shape of the 49 stored `Open`-fill rows."""
    details = _open_print_case(dict(bid="0.90", ask="1.04"),
                               dict(bid="0.00", ask="2.68"))
    res = _run(_legs(("+1", 76), ("-1", 72)), details)
    assert _entry_net(res) == pytest.approx(0.97)     # long at its Open, short at 0
    assert res["entry_source"] == "barchart_open+barchart_side"


def test_a_bought_leg_with_a_zero_bid_fills_at_the_open_only_if_it_traded():
    """2026-09-24: a bought leg on a junk quote no longer pays the ask. With
    volume that day it fills at the Open print; without, it is refused."""
    traded = _open_print_case(dict(bid="0.00", ask="1.20", volume="7", latest="0.95"),
                              dict(bid="0.40", ask="0.50"))
    res = _run(_legs(("+1", 76), ("-1", 72)), traded)
    assert _entry_net(res) == pytest.approx(0.97 - 0.45)   # both Open prints
    assert res["entry_source"] == "barchart_open+barchart_open"

    refusal = {}
    untraded = _open_print_case(dict(bid="0.00", ask="1.20"),
                                dict(bid="0.40", ask="0.50"))
    assert _run(_legs(("+1", 76), ("-1", 72)), untraded, refusal=refusal) == {}
    assert refusal["reason"] == "junk_entry_quote"


def test_a_junk_ask_is_never_an_entry_fill():
    """The HYG 74P shape: `bid 0.09 / ask 5.00` on an option that trades near
    1. A bought leg fills at its traded Open, never the ask or the mid; the
    leg-side is charged commission only and the row says `no_spread_entry`."""
    details = _open_print_case(dict(bid="0.09", ask="5.00", volume="28", latest="0.99"),
                               dict(bid="0.40", ask="0.50"))
    res = _run(_legs(("+1", 76), ("-1", 72)), details,
               cfg=_cfg(commission_per_contract=0.65, slippage_frac_of_spread=0.25))
    # The bought 76P fills at its 0.97 Open print, not the 5.00 ask or 2.545 mid.
    assert _entry_net(res) == pytest.approx(0.97 - 0.45)
    assert res["entry_source"] == "barchart_open+barchart_open"
    assert res["cost_basis"].startswith("no_spread_entry")


def test_an_open_print_still_wins_over_a_two_sided_quote():
    """The extension claims ONLY a one-sided quote. A two-sided quote on the
    entry day keeps the Open fill — this is not touch pricing."""
    details = _open_print_case(dict(bid="0.90", ask="1.04"),
                               dict(bid="0.40", ask="0.50"))
    res = _run(_legs(("+1", 76), ("-1", 72)), details)
    assert _entry_net(res) == pytest.approx(0.52)     # 0.97 − 0.45, both prints
    assert res["entry_source"] == "barchart_open+barchart_open"


def test_an_open_print_still_wins_when_the_row_has_no_quote_data():
    """No Bid/Ask columns is NO QUOTE DATA, not a zero bid: the Open print fills."""
    details = _open_print_case({}, {})
    res = _run(_legs(("+1", 76), ("-1", 72)), details)
    assert _entry_net(res) == pytest.approx(0.52)
    assert "barchart_side" not in res["entry_source"]


def test_the_side_rule_over_the_open_can_still_reach_the_debit_credit_gate():
    """A bought leg on a junk `0 × 0` quote that traded fills at its 0.30 Open;
    with the short leg's two-sided 0.45 Open above it, the debit spread prices
    to a credit and is refused rather than written."""
    details = _open_print_case(dict(bid="0.00", ask="0.00", volume="3", latest="0.30"),
                               dict(bid="0.40", ask="0.50"))
    details[LONG_KEY][ENTRY]["Open"] = "0.30"
    refusal = {}
    assert _run(_legs(("+1", 76), ("-1", 72)), details, refusal=refusal) == {}
    assert refusal["reason"] == "debit_priced_to_credit"


# ── (f) the daily marks are still the liquidation rule ─────────────────────────

def test_daily_marks_still_use_the_zero_bid_liquidation_rule():
    """B5 is untouched for mark-to-market. A single long leg quoted 0 × 2.00 on a
    later day marks at 1.00 — not the ask, and not 0."""
    details = {LONG_KEY: {ENTRY: _row(10.0, bid="9.90", ask="10.10", open_="10.00"),
                          date(2026, 6, 3): _row(8.0, bid="0.00", ask="2.00"),
                          date(2026, 6, 4): _row(8.0, bid="0.00", ask="0.00")}}
    res = _run(_legs(("+1", 76)), details, structure="long_put")
    assert _entry_net(res) == pytest.approx(10.0)
    assert res["daily_price_csv"].split(",") == ["10.0000", "1.0000", "0.0000"]


# ── (e) the debit-priced-to-a-credit gate ──────────────────────────────────────

def test_debit_structure_set_comes_from_the_canonical_names():
    from lib.structure_names import canonical_debit_spreads
    assert {n.replace(" ", "_") for n in canonical_debit_spreads()} <= DEBIT_STRUCTURES
    assert "bear_put_spread" in DEBIT_STRUCTURES and "long_call" in DEBIT_STRUCTURES
    # Credit structures are NOT gated, and neither are the name-ambiguous ones.
    for s in ("bull_put_spread", "bear_call_spread", "short_put", "short_call",
              "straddle", "strangle", "butterfly", "condor", "calendar",
              "diagonal", "explicit_legs", "iron_condor"):
        assert s not in DEBIT_STRUCTURES


def _inverted_case():
    """Both legs print, two-sided, but the SHORT leg prints above the long — the
    SMH 2024-07-17 / IWM 2024-03-25 shape. Side-aware pricing does not touch it;
    the gate is what catches it."""
    details = {LONG_KEY: {ENTRY: _row(0.97, bid="0.90", ask="1.04", open_="0.97")},
               SHORT_KEY: {ENTRY: _row(1.34, bid="1.30", ask="1.40", open_="1.34")}}
    for d in (date(2026, 6, 3), date(2026, 6, 4)):
        details[LONG_KEY][d] = _row(1.0, bid="0.90", ask="1.10")
        details[SHORT_KEY][d] = _row(1.3, bid="1.25", ask="1.35")
    return details


def test_a_debit_structure_priced_to_a_credit_is_refused():
    refusal = {}
    res = _run(_legs(("+1", 76), ("-1", 72)), _inverted_case(), refusal=refusal)
    assert res == {}
    assert refusal["reason"] == sim.DEBIT_CREDIT_REFUSAL == "debit_priced_to_credit"
    assert "-0.3700" in refusal["detail"] or "-0.37" in refusal["detail"]


def test_the_refused_row_can_never_be_labelled_credit():
    """The gate runs BEFORE `_effective_sim_cfg` / `_exit_basis`, so no refused
    position can take the credit sizing profile or carry a CREDIT basis."""
    assert _run(_legs(("+1", 76), ("-1", 72)), _inverted_case()) == {}
    # The same quotes under a CREDIT label are refused too (2026-09-23): the 72P
    # is priced above the 76P, which is a bad quote whatever the position is
    # called. The polarity gates pass (a credit that priced to a credit), so the
    # strike-order check is what catches it.
    refusal = {}
    res = _run(_legs(("+1", 76), ("-1", 72)), _inverted_case(),
               structure="bull_put_spread", refusal=refusal)
    assert res == {}
    assert refusal["reason"] == sim.NON_MONOTONIC_REFUSAL


def test_a_debit_structure_priced_to_a_debit_is_untouched():
    details = {LONG_KEY: {ENTRY: _row(1.34, bid="1.30", ask="1.40", open_="1.34")},
               SHORT_KEY: {ENTRY: _row(0.97, bid="0.90", ask="1.04", open_="0.97")}}
    for d in (date(2026, 6, 3), date(2026, 6, 4)):
        details[LONG_KEY][d] = _row(1.3, bid="1.25", ask="1.35")
        details[SHORT_KEY][d] = _row(0.9, bid="0.85", ask="0.95")
    refusal = {}
    res = _run(_legs(("+1", 76), ("-1", 72)), details, refusal=refusal)
    assert refusal == {} and _entry_net(res) == pytest.approx(0.37)


def test_the_gate_predicate_is_narrow():
    assert sim._refuse_debit_priced_to_credit("bear_put_spread", -0.37)
    assert sim._refuse_debit_priced_to_credit("long_call", -0.01)
    assert not sim._refuse_debit_priced_to_credit("bear_put_spread", 0.37)
    assert not sim._refuse_debit_priced_to_credit("bull_put_spread", -0.37)
    assert not sim._refuse_debit_priced_to_credit("explicit_legs", -0.37)


# ── the refusal reaches BOTH writers' records ──────────────────────────────────

def test_core_tallies_the_refusal_under_its_own_reason():
    """`_run_simulations` must not pool a refusal into `unpriced`: the data was
    there and was wrong, which is a different fact."""
    from backtest.core import _run_simulations

    class _FakePlay:
        c = {"date": "2026-06-01", "signal_date": SIGNAL, "ticker": "IWM"}
        refusal = {"reason": "debit_priced_to_credit", "detail": "x"}

        def simulate(self, *a, **kw):
            return None

    skipped = {"unpriced": 0, "debit_priced_to_credit": 0}
    assert _run_simulations([_FakePlay()], {}, {}, {}, _cfg(), 0.1, skipped) == []
    assert skipped == {"unpriced": 0, "debit_priced_to_credit": 1}


def test_proxy_row_records_the_refusal_as_its_skip_reason():
    class _P:
        refusal = {"reason": "debit_priced_to_credit",
                   "detail": "bear_put_spread priced to a net CREDIT of -0.3700 at entry"}

    row = _note_refusal({"skip_reason": "unpriced", "proxy_detail": "direction only"}, _P())
    assert row["skip_reason"] == "debit_priced_to_credit"
    assert "debit_priced_to_credit:" in row["proxy_detail"]
    assert row["proxy_detail"].startswith("direction only | ")

    clean = _note_refusal({"skip_reason": "unpriced", "proxy_detail": "ok"},
                          type("P", (), {"refusal": {}})())
    assert clean == {"skip_reason": "unpriced", "proxy_detail": "ok"}


def test_weekday_grid_assumption_holds():
    """The fixtures above assume 06-02/03/04 are the first three grid days."""
    grid = [SIGNAL + timedelta(days=i) for i in range(1, 4)]
    assert [d.weekday() for d in grid] == [1, 2, 3]


# ── (g) the mirror: a CREDIT structure priced to a net DEBIT (2026-09-23) ───────

def _tlt_case():
    """TLT 2025-04-04, bull_put_spread 90/85, reduced to its shape: the bought 85P
    fills at a stale Open print (1.61) far above its own two-sided quote
    (0.68/0.81), the sold 90P at a fair 1.26. The entry nets a +0.35 DEBIT, which
    `_size_contracts` used to divide the risk budget by — 38 contracts."""
    long_k = ("IWM", "Put", 85.0, "2026-07-17")
    short_k = ("IWM", "Put", 90.0, "2026-07-17")
    details = {long_k: {ENTRY: _row(0.745, bid="0.68", ask="0.81", open_="1.61")},
               short_k: {ENTRY: _row(1.26, bid="1.20", ask="1.32", open_="1.26")}}
    legs = [bt.Leg(1, "IWM", EXP, 85.0, "Put"), bt.Leg(-1, "IWM", EXP, 90.0, "Put")]
    return legs, details


def test_a_credit_structure_priced_to_a_debit_is_refused():
    legs, details = _tlt_case()
    refusal = {}
    res = _run(legs, details, structure="bull_put_spread", refusal=refusal)
    assert res == {}
    assert refusal["reason"] == sim.CREDIT_DEBIT_REFUSAL == "credit_priced_to_debit"
    assert "0.35" in refusal["detail"]


def test_credit_gate_predicate_is_narrow():
    assert sim._refuse_credit_priced_to_debit("bull_put_spread", 0.35)
    assert sim._refuse_credit_priced_to_debit("bear_call_spread", 0.01)
    assert not sim._refuse_credit_priced_to_debit("bull_put_spread", -0.35)
    assert not sim._refuse_credit_priced_to_debit("bull_call_spread", 0.35)
    assert not sim._refuse_credit_priced_to_debit("explicit_legs", 0.35)
    assert not sim._refuse_credit_priced_to_debit("iron_condor", 0.35)


def test_credit_structure_set_comes_from_the_canonical_names():
    from backtest.classify import CREDIT_STRUCTURES
    from lib.structure_names import canonical_credit_spreads
    assert {n.replace(" ", "_") for n in canonical_credit_spreads()} == \
        {"bull_put_spread", "bear_call_spread"}
    assert {"bull_put_spread", "bear_call_spread", "short_put", "short_call"} \
        == CREDIT_STRUCTURES
    assert not (CREDIT_STRUCTURES & DEBIT_STRUCTURES)


def test_core_tallies_every_entry_refusal_code():
    from backtest.plays import build_matched_plays
    _plays, _c, _n, skipped = build_matched_plays([], 0.02)
    for reason in sim.ENTRY_REFUSALS:
        assert skipped[reason] == 0


# ── (h) same-expiry legs priced against strike order ──────────────────────────

def test_monotonicity_refuses_a_put_priced_above_a_higher_strike_put():
    # A 3-leg put ladder whose far-OTM 68P is quoted above the 72P: no market can
    # hold that, so the entry is refused as a bad quote.
    legs = [bt.Leg(1, "IWM", EXP, 76.0, "Put"), bt.Leg(-1, "IWM", EXP, 72.0, "Put"),
            bt.Leg(-1, "IWM", EXP, 68.0, "Put")]
    k68 = ("IWM", "Put", 68.0, "2026-07-17")
    details = {LONG_KEY: {ENTRY: _row(3.0, bid="2.9", ask="3.1", open_="3.0")},
               SHORT_KEY: {ENTRY: _row(1.0, bid="0.9", ask="1.1", open_="1.0")},
               k68: {ENTRY: _row(1.2, bid="1.1", ask="1.3", open_="1.2")}}
    refusal = {}
    assert _run(legs, details, structure="explicit_legs", refusal=refusal) == {}
    assert refusal["reason"] == "non_monotonic_entry_quote"
    assert "68P@1.2" in refusal["detail"] and "72P@1" in refusal["detail"]


def test_monotonicity_predicate_calls_and_ties():
    C = [bt.Leg(1, "X", EXP, 100.0, "Call"), bt.Leg(-1, "X", EXP, 110.0, "Call")]
    assert sim._monotonicity_violation(C, [5.0, 6.0], ["barchart", "barchart"])
    assert sim._monotonicity_violation(C, [5.0, 3.0], ["barchart", "barchart"]) is None
    assert sim._monotonicity_violation(C, [0.0, 0.0], ["barchart", "barchart"]) is None
    # A one-sided touch fill is an execution price, not a value: not judged.
    assert sim._monotonicity_violation(C, [5.0, 6.0], ["barchart", "barchart_side"]) is None
    # Different expiries are never compared.
    D = [bt.Leg(1, "X", EXP, 100.0, "Call"),
         bt.Leg(-1, "X", EXP + timedelta(days=28), 110.0, "Call")]
    assert sim._monotonicity_violation(D, [5.0, 6.0], ["barchart", "barchart"]) is None


# ── (i) per-leg entry greeks come from each leg's OWN row ─────────────────────

def _greek_row(mark, delta, iv, under):
    row = _row(mark, bid=str(mark - 0.05), ask=str(mark + 0.05), open_=str(mark))
    row.update({"Delta": delta, "IV": iv, "Price~": under})
    return row


def test_each_leg_uses_its_own_delta_iv_and_underlying():
    details = {LONG_KEY: {ENTRY: _greek_row(3.0, "-0.45", "31.5", "77.9")},
               SHORT_KEY: {ENTRY: _greek_row(1.5, "-0.25", "34.0", "78.1")}}
    res = _run(_legs(("+1", 76), ("-1", 72)), details)
    # Net = (+1)(-0.45) + (-1)(-0.25) — both REAL cached deltas, no model value.
    assert res["delta"] == pytest.approx(-0.20)
    lines = res["entry_leg_detail"].splitlines()
    assert "iv=31.5% delta=-0.450 S=77.9" in lines[0]
    assert "iv=34% delta=-0.250 S=78.1" in lines[1]
    # entry_underlying = the legs' median Price~ (never the OHLC cache).
    assert res["entry_underlying"] == pytest.approx(78.0)


def test_a_leg_without_a_real_delta_blanks_the_net_delta():
    details = {LONG_KEY: {ENTRY: _greek_row(3.0, "-0.45", "31.5", "77.9")},
               # Barchart's all-zero sentinel greek row: IV 0 means NO greeks.
               SHORT_KEY: {ENTRY: _greek_row(1.5, "0", "0", "78.1")}}
    res = _run(_legs(("+1", 76), ("-1", 72)), details)
    assert res["delta"] == ""                       # all-or-nothing, never 0.0
    assert "delta= " in res["entry_leg_detail"].splitlines()[1]


def test_entry_underlying_is_the_legs_median_on_a_split_ticker():
    """SPLIT CASE. NVDA split 10:1; the underlying OHLC cache is split-ADJUSTED
    and would read ~1/10 of an as-traded pre-split `Price~`. entry_underlying
    must stay on the legs' own as-traded basis."""
    import inspect
    assert sim._entry_underlying("NVDA", [1210.4, 1210.6, 1210.5]) == pytest.approx(1210.5)
    assert sim._entry_underlying("NVDA", []) is None
    # It takes no date and no ticker file: nothing to look the OHLC close up by.
    assert list(inspect.signature(sim._entry_underlying).parameters) == \
        ["ticker", "leg_prices", "signal_date"]


def test_entry_underlying_warns_when_legs_disagree(caplog):
    # One leg's file reads a ~$15 underlying against ~$78: the median of two is
    # still pulled, but the disagreement is logged — the META 630P shape.
    details = {LONG_KEY: {ENTRY: _greek_row(3.0, "-0.45", "31.5", "77.9")},
               SHORT_KEY: {ENTRY: _greek_row(1.5, "-0.25", "34.0", "15.0")}}
    with caplog.at_level("WARNING", logger="backtest"):
        _run(_legs(("+1", 76), ("-1", 72)), details)
    assert any("legs disagree on Price~" in r.getMessage() for r in caplog.records)
