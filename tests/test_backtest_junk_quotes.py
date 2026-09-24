"""The junk-quote rule (operator ruling 2026-09-24).

A quote is JUNK when `bid <= 0` or `ask - bid > mid`. One predicate,
`simulate._is_junk_quote`, feeds three consumers:

  cost   a junk leg-side is charged commission only, and `cost_basis` says
         `no_spread_<side>`
  marks  a junk day marks at that day's Latest when the contract traded, else
         carries the last good mark (tagged `barchart_stale`), capped by the B5
         liquidation mark when the quote has no bid
  entry  a junk quote never fills at its ask or mid: sold into no bid → 0,
         traded → the print, sold with a bid → the bid, bought → refused

The HYG rows are copied from HYG_20240719_74.00P.csv, the file that charged a
1-day bull put spread $1,250 of slippage. Everything runs on synthetic rows.
"""
from datetime import date

import pytest

import backtest as bt
from backtest import simulate as sim

SIGNAL = date(2026, 6, 1)           # Monday
ENTRY = date(2026, 6, 2)
EXP = date(2026, 7, 17)
KEY = ("HYG", "Put", 74.0, "2026-07-17")
D = {n: date(2026, 6, n) for n in (2, 3, 4, 5, 8)}


def _row(mark, bid=None, ask=None, latest=None, volume=None, open_=""):
    row = {"Open": open_, "_mark": mark}
    for col, v in (("Bid", bid), ("Ask", ask), ("Latest", latest), ("Volume", volume)):
        if v is not None:
            row[col] = str(v)
    return row


# ── the predicate ─────────────────────────────────────────────────────────────

def test_legacy_width_table():
    bids = (0.5, 1.99, 2.0, 4.99, 5.0, 9.99, 10.0, 19.99, 20.0, 500.0)
    assert [sim._legacy_width(b) for b in bids] == \
        [0.25, 0.25, 0.40, 0.40, 0.50, 0.50, 0.80, 0.80, 1.00, 1.00]
    assert sim.QUOTE_WIDTH_MULTIPLE == 2.0


@pytest.mark.parametrize("bid,ask,junk", [
    ("0.09", "5.00", True),     # HYG 74P 2024-05-16: Latest 0.11
    ("0.00", "4.80", True),     # HYG 74P 2024-05-21: Latest 0.07
    ("0.08", "5", True),        # HYG 74P 2024-05-24: no volume
    ("0.00", "0.00", True),     # nothing bid, nothing offered
    (None, "0.40", True),       # a blank bid with a live ask is no bid
    ("0.05", "0.08", False),    # a legitimate cheap quote: spread 0.03 < mid 0.065
    ("0.08", "0.09", False),    # HYG 74P 2024-05-22
    ("0.10", "0.30", False),    # ask = 3 × bid is the mid boundary: spread 0.20 = mid
    ("0.10", "0.31", True),
    ("1.00", "1.50", False),    # width boundary: 0.50 = 2 x 0.25
    ("1.00", "1.51", True),
    # The legacy Cboe width line (2x W(bid)), 2026-09-24.
    ("1.88", "5.00", True),     # HYG 76P 2024-04-15: 3.12 > 2 x 0.25
    ("0.66", "5.00", True),
    ("2.10", "2.40", False),    # 0.30 < 2 x 0.40
    ("12.00", "12.90", False),  # 0.90 < 2 x 0.80
    ("12.00", "13.70", True),   # 1.70 > 1.60
    ("0.02", "0.07", True),     # only the mid line catches this one
    (None, None, False),        # NO QUOTE is not junk
    ("0.10", None, False),
])
def test_junk_predicate(bid, ask, junk):
    assert sim._is_junk_quote(_row(1.0, bid=bid, ask=ask)) is junk


def test_junk_spread_is_the_sentinel_not_the_quoted_width():
    assert sim._leg_spread(_row(2.545, bid="0.09", ask="5.00")) == sim.JUNK_SPREAD
    assert sim._leg_spread(_row(0.065, bid="0.05", ask="0.08")) == pytest.approx(0.03)
    assert sim._leg_spread(_row(1.0)) is None


# ── cost ─────────────────────────────────────────────────────────────────────

def test_a_junk_leg_side_is_charged_commission_only():
    legs = [bt.Leg(-1, "HYG", EXP, 76.0, "Put"), bt.Leg(1, "HYG", EXP, 74.0, "Put")]
    res = {"days_held": 1, "realized_pnl_abs": 100.0, "realized_pnl_pct": 1.0}
    cfg = {"commission_per_contract": 0.65, "slippage_frac_of_spread": 0.25}
    # Entry: the 76P's 0.02 spread is charged; the junk 74P's is not.
    # Exit: both legs clean, 0.04 of spread.
    sim._apply_costs(res, cfg, legs, 5, -0.21, 0.02, [0.04],
                     entry_junk=True, grid_spread_junk=[False])
    commission = 0.65 * 2 * 5 * 2
    slippage = 0.25 * (0.02 + 0.04) * 100 * 5
    assert res["cost_total"] == pytest.approx(commission + slippage)
    assert res["cost_basis"] == "no_spread_entry"


def test_junk_on_both_sides_names_both():
    legs = [bt.Leg(1, "HYG", EXP, 74.0, "Put")]
    res = {"days_held": 1, "realized_pnl_abs": 0.0, "realized_pnl_pct": 0.0}
    cfg = {"commission_per_contract": 0.65, "slippage_frac_of_spread": 0.25}
    sim._apply_costs(res, cfg, legs, 5, 0.10, 0.0, [0.0],
                     entry_junk=True, grid_spread_junk=[True])
    assert res["cost_total"] == pytest.approx(0.65 * 5 * 2)
    assert res["cost_basis"] == "no_spread_entry_exit"


# ── daily marks ──────────────────────────────────────────────────────────────

def _run_long(rows, cfg=None):
    """One long 74P entered 06-02; ``rows`` = {date: row}. The series holds each
    row's `_mark` when it has one, as `parse_history_series` builds it."""
    legs = [bt.Leg(1, "HYG", EXP, 74.0, "Put")]
    series = {KEY: sorted((d, r["_mark"]) for d, r in rows.items()
                          if r["_mark"] is not None)}
    entry_row = {"Strike": 74.0, "DTE": (EXP - ENTRY).days, "IV": "9",
                 "Price~": "77", "Expires": EXP.isoformat(), "_entry_date": ENTRY}
    base = {"profit_target": None, "stop_loss": None, "contracts": 1,
            "path_cap_days": 7, "entry_sources": ["barchart"],
            "exit_sources": ["barchart"]}
    base.update(cfg or {})
    return sim._simulate({"ticker": "HYG", "signal_date": SIGNAL, "play": "long put"},
                         legs, entry_row, {}, series, base, structure="long_put",
                         barchart_details={KEY: rows})


def _marks(res):
    return [float(x) for x in res["daily_price_csv"].split(",")]


def test_a_junk_day_that_traded_marks_at_its_latest():
    res = _run_long({
        D[2]: _row(0.13, bid="0.12", ask="0.14", open_="0.13"),
        D[3]: _row(2.545, bid="0.09", ask="5.00", latest="0.11", volume="28"),
        D[4]: _row(0.10, bid="0.09", ask="0.11"),
        D[5]: _row(0.10, bid="0.09", ask="0.11"),
        D[8]: _row(0.10, bid="0.09", ask="0.11")})
    assert _marks(res)[1] == pytest.approx(0.11)          # not the 2.545 mid
    assert res["daily_source_csv"].split(",")[1] == "barchart_last"


def test_a_junk_day_with_no_trade_carries_the_last_good_mark_as_stale():
    res = _run_long({
        D[2]: _row(0.13, bid="0.12", ask="0.14", open_="0.13"),
        D[3]: _row(2.54, bid="0.08", ask="5.00", latest="0.13"),   # no volume
        D[4]: _row(0.10, bid="0.09", ask="0.11"),
        D[5]: _row(0.10, bid="0.09", ask="0.11"),
        D[8]: _row(0.10, bid="0.09", ask="0.11")})
    assert _marks(res)[1] == pytest.approx(0.13)          # 06-02's mid, carried
    assert res["daily_source_csv"].split(",")[1] == "barchart_stale"
    assert res["pct_stale_days"] == pytest.approx(1 / 5)


def test_a_bidless_junk_day_with_no_trade_is_capped_by_the_b5_mark():
    """B5's intent survives: a contract with no bid is worth about ask/2, so a
    `0 x 0.05` day does not carry an older 0.13 mark."""
    res = _run_long({
        D[2]: _row(0.13, bid="0.12", ask="0.14", open_="0.13"),
        D[3]: _row(0.13, bid="0.00", ask="0.05", latest="0.13"),
        D[4]: _row(None, bid="0.00", ask="0.01", latest="0"),   # no `_mark` at all
        D[5]: _row(0.13, bid="0.00", ask="4.80", latest="0.13")})
    marks = _marks(res)
    assert marks[1] == pytest.approx(0.025)               # ceiling binds
    assert marks[2] == pytest.approx(0.005)               # judged off its own row
    # A junk ask caps nothing: the last good mark (06-02's 0.13) is carried.
    assert marks[3] == pytest.approx(0.13)
    assert res["daily_source_csv"].split(",")[1:4] == [
        "barchart", "barchart", "barchart_stale"]


# ── entry ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("row,qty,expected", [
    (_row(2.545, bid="0.09", ask="5.00"), +1, (None, "junk_entry_quote")),
    (_row(2.545, bid="0.09", ask="5.00"), -1, (0.09, "barchart_side")),
    (_row(2.40, bid="0.00", ask="4.80", latest="0.07", volume="103"), -1,
     (0.0, "barchart_side")),                         # no bid: nothing received
    (_row(2.40, bid="0.00", ask="4.80", latest="0.07", volume="103", open_="0.09"),
     +1, (0.09, "barchart_open")),
    (_row(0.065, bid="0.05", ask="0.08", open_="0.06"), +1, None),   # not junk
])
def test_junk_entry_fill(row, qty, expected):
    assert sim._junk_entry_fill(row, qty) == expected


def test_a_carried_junk_row_never_fills_at_its_old_open():
    row = _row(2.40, bid="0.00", ask="4.80", latest="0.07", volume="103", open_="0.09")
    assert sim._junk_entry_fill(row, +1, open_print=False) == (0.07, "barchart_last")


def test_a_bought_leg_into_a_junk_ask_is_refused_not_filled():
    refusal = {}
    legs = [bt.Leg(1, "HYG", EXP, 74.0, "Put")]
    rows = {D[2]: _row(2.545, bid="0.09", ask="5.00", open_="0.10")}
    series = {KEY: [(D[2], 2.545)]}
    entry_row = {"Strike": 74.0, "DTE": 45, "IV": "9", "Price~": "77",
                 "Expires": EXP.isoformat(), "_entry_date": ENTRY}
    cfg = {"profit_target": None, "stop_loss": None, "contracts": 1,
           "path_cap_days": 3, "entry_sources": ["barchart"],
           "exit_sources": ["barchart"]}
    res = sim._simulate({"ticker": "HYG", "signal_date": SIGNAL, "play": "long put"},
                        legs, entry_row, {}, series, cfg, structure="long_put",
                        barchart_details={KEY: rows}, refusal=refusal)
    assert res == {}
    assert refusal["reason"] == "junk_entry_quote"
    assert "junk_entry_quote" in sim.ENTRY_REFUSALS
