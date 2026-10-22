"""One clock for every leg of an entry (operator ruling 2026-10-23).

"The separate fill should never happen. It should always be open on the same
time." The operator enters a spread as ONE combo order at mid. Barchart's daily
history has no simultaneous opening quote: each leg's `Open` is its own first
trade and `Latest` its own last, at times nobody recorded. The one snapshot
every leg shares is the entry day's CLOSING bid/ask, so every leg fills there:

  1. a two-sided, non-junk closing quote → its mid (`barchart_close_mid`)
  2. a one-sided quote is always junk (`_is_junk_quote`), so rule 3 owns it
  3. a junk closing quote → a sold leg at its bid, 0 with none
     (`barchart_close_side`); a bought leg at the mid when a bid exists
     (`barchart_close_mid_wide`, ruling "option C"), refused with no bid
     (`junk_entry_quote`)
  4. a leg with no closing quote on the entry day never borrows an earlier
     day's snap: the entry moves to the first day in the window on which
     every leg has one, else the play is refused
  5. a bounded structure whose net entry is outside its payoff range is
     refused (`entry_outside_bounds`)

Synthetic rows only: no network, no option-history cache.
"""
from datetime import date, timedelta

import pytest

import backtest as bt
from backtest import simulate as sim

SIGNAL = date(2026, 6, 1)           # Monday
DAY1 = date(2026, 6, 2)             # the anchor's day under next_open
DAY2 = date(2026, 6, 3)
DAY3 = date(2026, 6, 4)
EXP = date(2026, 7, 17)
K100 = ("XYZ", "Call", 100.0, "2026-07-17")
K105 = ("XYZ", "Call", 105.0, "2026-07-17")

# Sentinels no bid/ask-derived price in these fixtures can equal.
OPEN_PRINT, LATEST_PRINT = 77.77, 88.88


def _row(bid=None, ask=None, *, open_=OPEN_PRINT, latest=LATEST_PRINT, volume="25"):
    """A history row with a TRADED Open and Latest that must never fill."""
    row = {"Open": str(open_), "Latest": str(latest), "Volume": volume,
           "_mark": latest}
    if bid is not None:
        row["Bid"] = str(bid)
    if ask is not None:
        row["Ask"] = str(ask)
    if bid is not None and ask is not None and float(bid) > 0 and float(ask) > 0:
        row["_mark"] = (float(bid) + float(ask)) / 2
    return row


def _legs(long_k=100.0, short_k=105.0):
    return [bt.Leg(1, "XYZ", EXP, long_k, "Call"), bt.Leg(-1, "XYZ", EXP, short_k, "Call")]


def _run(details, legs=None, structure="bull_call_spread", refusal=None, **cfg_kw):
    series = {k: sorted((d, r["_mark"]) for d, r in rows.items())
              for k, rows in details.items()}
    entry_row = {"Strike": 100.0, "DTE": (EXP - DAY1).days, "IV": "30",
                 "Price~": "101", "_entry_date": DAY1}
    cfg = {"profit_target": None, "stop_loss": None, "contracts": 1,
           "path_cap_days": 5, "entry_sources": ["barchart"],
           "exit_sources": ["barchart"], **cfg_kw}
    cand = {"ticker": "XYZ", "signal_date": SIGNAL, "play": "bull call spread"}
    return sim._simulate(cand, legs or _legs(), entry_row, {}, series, cfg,
                         structure=structure, barchart_details=details,
                         refusal=refusal)


def _later(rows_100, rows_105):
    """Pad both legs with clean quotes after DAY2 so the path has marks."""
    for rows, (b, a) in ((rows_100, ("3.9", "4.1")), (rows_105, ("1.9", "2.1"))):
        rows.setdefault(DAY3, _row(b, a))
    return {K100: rows_100, K105: rows_105}


# ── rule 1: a clean closing quote fills at its true bid/ask mid ───────────────

def test_a_clean_closing_quote_fills_at_its_mid_not_the_rows_mark():
    # `_mark` is what `lib/barchart/options._mark` stored; it may be a Latest.
    # The fill is computed from Bid and Ask, whatever `_mark` holds.
    row = {**_row("2.00", "2.20"), "_mark": LATEST_PRINT}
    assert sim.entry_day_fill(row, +1) == (pytest.approx(2.10), sim.CLOSE_MID_TAG)
    assert sim.entry_day_fill(row, -1) == (pytest.approx(2.10), sim.CLOSE_MID_TAG)


@pytest.mark.parametrize("bid,ask", [
    (None, None),          # no quote columns (an older cache file)
    ("2.00", None),        # a bid with no ask
    ("2.20", "2.00"),      # crossed
])
def test_a_row_without_a_usable_two_sided_quote_is_no_fill(bid, ask):
    assert sim.entry_day_fill(_row(bid, ask), +1) is None
    assert sim.entry_day_fill(_row(bid, ask), -1) is None


def test_no_row_is_no_fill():
    assert sim.entry_day_fill(None, +1) is None


# ── rules 2 and 3: one-sided and junk quotes, on the side the leg trades ──────

@pytest.mark.parametrize("bid,ask,qty,expected", [
    ("0", "0.05", -1, (0.0, "barchart_close_side")),     # sold, no bid: nothing received
    ("0", "0", -1, (0.0, "barchart_close_side")),
    ("0.09", "5.00", -1, (0.09, "barchart_close_side")),  # sold into junk: its bid
    ("0", "0.05", +1, (None, "junk_entry_quote")),        # bought, no bid: refused
    (None, "0.05", +1, (None, "junk_entry_quote")),       # bid column blank: refused
    ("0.09", "5.00", +1, (2.545, "barchart_close_mid_wide")),  # bought, wide: its mid
])
def test_one_sided_and_junk_closing_quotes(bid, ask, qty, expected):
    price, tag = sim.entry_day_fill(_row(bid, ask), qty)
    assert tag == expected[1]
    assert price == (None if expected[0] is None else pytest.approx(expected[0]))


def test_a_bought_leg_into_a_one_sided_quote_never_pays_the_ask():
    """`_entry_side_mark` still answers `ask` for a bought leg, but every
    one-sided quote with an ask is junk, so `entry_day_fill` refuses first."""
    row = _row("0", "0.05")
    assert sim._is_junk_quote(row)
    assert sim._entry_side_mark(row, +1) == 0.05
    assert sim.entry_day_fill(row, +1) == (None, sim.JUNK_ENTRY_REFUSAL)


def test_a_spread_with_a_sold_leg_at_no_bid_is_tagged_by_side():
    details = _later({DAY1: _row("3.90", "4.10")}, {DAY1: _row("0", "0.05")})
    res = _run(details)
    assert float(res["entry_option_price"]) == pytest.approx(4.0)
    assert res["entry_source"] == "barchart_close_mid+barchart_close_side"


def test_a_bought_leg_on_a_wide_two_sided_quote_fills_at_the_closing_mid():
    """Operator ruling 2026-10-23, option C: the spread is one combo order at
    mid, so a bought leg whose quote is junk only by width fills at its mid,
    and the tag keeps such rows identifiable."""
    details = _later({DAY1: _row("3.00", "5.00")}, {DAY1: _row("1.90", "2.10")})
    assert sim._is_junk_quote(details[K100][DAY1])
    res = _run(details)
    assert float(res["entry_option_price"]) == pytest.approx(4.0 - 2.0)
    assert res["entry_source"] == "barchart_close_mid_wide+barchart_close_mid"


def test_a_bought_leg_with_no_bid_refuses_the_play():
    refusal = {}
    details = _later({DAY1: _row("0", "4.10")}, {DAY1: _row("1.90", "2.10")})
    assert _run(details, refusal=refusal) == {}
    assert refusal["reason"] == "junk_entry_quote"
    assert "no bid" in refusal["detail"]


# ── rule 4: one day for every leg ─────────────────────────────────────────────

def test_a_leg_missing_on_day_1_moves_the_entry_to_day_2():
    """The 105C has no row on DAY1. It is not filled off the signal day's
    snap; the entry waits for DAY2, the first day both legs quote."""
    details = _later({SIGNAL: _row("3.40", "3.60"), DAY1: _row("3.90", "4.10"),
                      DAY2: _row("4.40", "4.60")},
                     {SIGNAL: _row("1.40", "1.60"), DAY2: _row("2.40", "2.60")})
    res = _run(details)
    assert float(res["entry_option_price"]) == pytest.approx(4.5 - 2.5)
    assert res["dte_entry"] == (EXP - DAY2).days
    assert res["daily_source_csv"].split(",")[0] == "pre_entry"
    assert "greeks@" not in res["entry_leg_detail"]     # every leg's own DAY2 row


def test_a_leg_without_a_quote_on_day_1_also_waits():
    """A row that exists but carries no closing quote counts as missing."""
    details = _later({DAY1: _row("3.90", "4.10"), DAY2: _row("4.40", "4.60")},
                     {DAY1: _row(None, None), DAY2: _row("2.40", "2.60")})
    res = _run(details)
    assert res["dte_entry"] == (EXP - DAY2).days


def test_legs_that_never_quote_on_the_same_day_are_refused():
    window = [DAY1 + timedelta(days=k) for k in range(8)]
    window = [d for d in window if d.weekday() < 5][:5]       # DAY1 … window end
    rows_100 = {d: _row("3.90", "4.10") for d in window[0::2]}
    rows_105 = {d: _row("1.90", "2.10") for d in window[1::2]}
    refusal = {}
    assert _run({K100: rows_100, K105: rows_105}, refusal=refusal) == {}
    assert refusal["reason"] == sim.NO_COMMON_ENTRY_DAY == "no_common_entry_day"
    assert "every leg has a closing quote" in refusal["detail"]


def test_a_leg_with_no_closing_quote_in_the_window_keeps_its_old_refusal():
    refusal = {}
    details = {K100: {DAY1: _row("3.90", "4.10")},
               K105: {DAY1: _row(None, None)}}
    assert _run(details, refusal=refusal) == {}
    assert refusal["reason"] == sim.NO_REAL_ENTRY_PRICE


def test_common_entry_day_unit():
    assert sim.common_entry_day([{DAY1, DAY2}, {DAY2}], DAY1, DAY3) == DAY2
    assert sim.common_entry_day([{DAY1}, {DAY2}], DAY1, DAY3) is None
    assert sim.common_entry_day([{DAY3}], DAY1, DAY2) is None          # past the end
    assert sim.common_entry_day([{SIGNAL, DAY3}], DAY1) == DAY3        # no end
    assert sim.common_entry_day([], DAY1, DAY3) is None


def test_entry_close_days_counts_a_junk_refusal_as_a_quote():
    rows = {DAY1: _row("0.10", "4.10"), DAY2: _row(None, None), DAY3: _row("1", "1.1")}
    assert sim.entry_close_days(rows, +1) == {DAY1, DAY3}


# ── no Open print and no Latest ever reaches an entry fill ────────────────────

@pytest.mark.parametrize("bid", [None, "0", "0.05", "0.90", "1.95", "9.0"])
@pytest.mark.parametrize("ask", [None, "0", "0.08", "1.04", "2.05", "15.0"])
@pytest.mark.parametrize("qty", [+1, -1, +2, -3])
def test_no_open_or_latest_ever_reaches_an_entry_fill(bid, ask, qty):
    fill = sim.entry_day_fill(_row(bid, ask), qty)
    if fill is not None:
        assert fill[0] not in (OPEN_PRINT, LATEST_PRINT)
        assert fill[1] in (sim.CLOSE_MID_TAG, sim.CLOSE_MID_WIDE_TAG,
                           sim.CLOSE_SIDE_TAG, sim.JUNK_ENTRY_REFUSAL)


def test_no_open_or_latest_reaches_a_simulated_entry():
    details = _later({DAY1: _row("3.90", "4.10")}, {DAY1: _row("0.09", "5.00")})
    res = _run(details)
    detail = res["entry_leg_detail"]
    assert str(OPEN_PRINT) not in detail and str(LATEST_PRINT) not in detail
    assert "barchart_open" not in res["entry_source"]
    assert "barchart_last" not in res["entry_source"]


def test_signal_eod_timing_fills_at_the_signal_days_close():
    details = _later({SIGNAL: _row("3.40", "3.60"), DAY1: _row("3.90", "4.10")},
                     {SIGNAL: _row("1.40", "1.60"), DAY1: _row("1.90", "2.10")})
    series = {k: sorted((d, r["_mark"]) for d, r in rows.items())
              for k, rows in details.items()}
    entry_row = {"Strike": 100.0, "DTE": (EXP - SIGNAL).days, "IV": "30",
                 "Price~": "101", "_entry_date": SIGNAL}
    cfg = {"profit_target": None, "stop_loss": None, "contracts": 1, "path_cap_days": 5,
           "entry_sources": ["barchart"], "exit_sources": ["barchart"],
           "entry_timing": "signal_eod"}
    res = sim._simulate({"ticker": "XYZ", "signal_date": SIGNAL, "play": "x"},
                        _legs(), entry_row, {}, series, cfg,
                        structure="bull_call_spread", barchart_details=details)
    assert float(res["entry_option_price"]) == pytest.approx(3.5 - 1.5)


# ── rule 5: the bounds gate ───────────────────────────────────────────────────

def test_a_debit_vertical_above_its_width_is_refused():
    """A 100/105 call spread is worth 0 to 5. Closing mids of 8.0 and 2.0 net
    6.0: a debit (the polarity gate passes) in strike order (the monotonic
    check passes), but no market pays 6 for a 5-wide spread."""
    refusal = {}
    details = _later({DAY1: _row("7.90", "8.10")}, {DAY1: _row("1.90", "2.10")})
    assert _run(details, refusal=refusal) == {}
    assert refusal["reason"] == sim.OUTSIDE_BOUNDS_REFUSAL == "entry_outside_bounds"
    assert "[0, 5]" in refusal["detail"]


def test_a_spread_inside_its_bounds_passes():
    details = _later({DAY1: _row("3.90", "4.10")}, {DAY1: _row("1.90", "2.10")})
    assert float(_run(details)["entry_option_price"]) == pytest.approx(2.0)


def test_the_bounds_predicate():
    assert sim._entry_outside_bounds((0.0, 5.0), 5.01)
    assert sim._entry_outside_bounds((-5.0, 0.0), 0.2)
    assert not sim._entry_outside_bounds((0.0, 5.0), 5.0)
    assert not sim._entry_outside_bounds(None, 99.0)        # unbounded: never refused


def test_the_new_refusals_are_tallied():
    for reason in (sim.NO_COMMON_ENTRY_DAY, sim.OUTSIDE_BOUNDS_REFUSAL):
        assert reason in sim.ENTRY_REFUSALS


# ── the research mirrors import the rule, never restate it ────────────────────

def test_the_mirrors_import_the_one_entry_fill():
    from scripts.backtest_study.f3_structure import bear_rewrap as BR
    from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF
    from scripts.backtest_study.lib import hedge_instrument as HI
    from scripts.backtest import simulate as SIM
    for mod in (BR, NTF, HI):
        assert mod.entry_day_fill is SIM.entry_day_fill
    assert not hasattr(SIM, "carried_entry_fill")
