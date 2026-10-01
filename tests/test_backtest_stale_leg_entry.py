"""The entry window and the `stale_leg_at_entry` refusal (operator ruling 2026-10-01).

"If there is no real quote after the signal appears, allow a window of N=5
trading days for entry; if no real quote arrives within that window, flag the
row out." Two stored rows prompted it: GLD bull_call_spread (signal 2026-09-18)
filled its short leg off a 08-14 mark, FSLR bear_put_spread (signal 09-15) off
a 07-06 one.

Day 0 is the signal day; a trading day is a weekday. Synthetic rows only.
"""
from datetime import date

import pytest

import backtest as bt
from backtest import simulate as sim

SIGNAL = date(2026, 6, 1)           # Monday
ENTRY = date(2026, 6, 2)            # the anchor's day under next_open
EXP = date(2026, 7, 17)
LONG_KEY = ("IWM", "Call", 70.0, "2026-07-17")
SHORT_KEY = ("IWM", "Call", 75.0, "2026-07-17")

# Trading days after SIGNAL (Mon 06-01): 1=06-02 ... 4=06-05, 5=06-08, 6=06-09.
DAY = {0: date(2026, 6, 1), 1: date(2026, 6, 2), 3: date(2026, 6, 4),
       5: date(2026, 6, 8), 6: date(2026, 6, 9)}


def _row(mark, open_=""):
    return {"Open": open_, "_mark": mark, "Bid": f"{mark - 0.05:g}",
            "Ask": f"{mark + 0.05:g}"}


def _run(short_days, cfg_extra=None, refusal=None):
    """A bull call spread whose long leg quotes every day from the signal and
    whose short leg quotes only on ``short_days``."""
    long_rows = {d: _row(5.0, open_="5.0") for d in
                 [date(2026, 5, 20)] + [DAY[k] for k in (0, 1, 3, 5, 6)]}
    short_rows = {d: _row(2.0, open_="2.0") for d in short_days}
    details = {LONG_KEY: long_rows, SHORT_KEY: short_rows}
    series = {k: sorted((d, r["_mark"]) for d, r in rows.items())
              for k, rows in details.items()}
    legs = [bt.Leg(1, "IWM", EXP, 70.0, "Call"), bt.Leg(-1, "IWM", EXP, 75.0, "Call")]
    cand = {"ticker": "IWM", "signal_date": SIGNAL, "play": "bull call spread",
            "market_regime": ""}
    entry_row = {"Strike": 70.0, "DTE": (EXP - ENTRY).days, "IV": "30",
                 "Price~": "72.0", "Trade": 5.0, "Expires": EXP.isoformat(),
                 "Delta": "0.5", "_entry_date": ENTRY}
    cfg = {"profit_target": None, "stop_loss": None, "contracts": 1,
           "path_cap_days": 20, "entry_sources": ["barchart"],
           "exit_sources": ["barchart"], **(cfg_extra or {})}
    return sim._simulate(cand, legs, entry_row, {}, series, cfg,
                         structure="bull_call_spread", barchart_details=details,
                         refusal=refusal)


def test_window_end_counts_weekdays_from_the_signal_day():
    assert sim.entry_window_end(SIGNAL, 5) == DAY[5]          # over a weekend
    assert sim.entry_window_end(SIGNAL, 0) == SIGNAL
    assert sim.STALE_ENTRY_MAX_TRADING_DAYS == 5


def test_a_quote_on_day_0_enters_on_the_anchor_day():
    res = _run([DAY[0]])
    assert res
    assert res["dte_entry"] == (EXP - ENTRY).days     # entry did not move


def test_a_quote_on_the_entry_day_is_unchanged():
    res = _run([date(2026, 5, 20), DAY[1]])
    assert res and res["dte_entry"] == (EXP - ENTRY).days


def test_a_first_quote_on_trading_day_5_enters_that_day():
    refusal = {}
    res = _run([DAY[5]], refusal=refusal)
    assert res and not refusal
    assert res["dte_entry"] == (EXP - DAY[5]).days    # the whole entry waited
    # the days before the slipped entry are unpriced, as any pre-entry day is
    assert res["daily_source_csv"].split(",")[:4] == ["pre_entry"] * 4


def test_a_pre_signal_quote_then_a_day_3_quote_waits_for_day_3():
    """The old engine filled this leg off its 05-20 mark on day 1."""
    res = _run([date(2026, 5, 20), DAY[3]])
    assert res and res["dte_entry"] == (EXP - DAY[3]).days


def test_a_first_quote_on_trading_day_6_after_a_pre_signal_quote_refuses():
    refusal = {}
    assert _run([date(2026, 5, 20), DAY[6]], refusal=refusal) == {}
    assert refusal["reason"] == sim.STALE_LEG_REFUSAL == "stale_leg_at_entry"
    assert "2026-05-20" in refusal["detail"]


def test_last_quote_before_the_signal_refuses_the_gld_shape():
    """GLD 2026-09-18: the short leg's last real quote was weeks before."""
    refusal = {}
    assert _run([date(2026, 5, 14), date(2026, 5, 20)], refusal=refusal) == {}
    assert refusal["reason"] == "stale_leg_at_entry"


def test_a_leg_with_no_quote_at_all_keeps_its_old_refusal():
    refusal = {}
    assert _run([DAY[6]], refusal=refusal) == {}
    assert refusal["reason"] == sim.NO_REAL_ENTRY_PRICE


def test_null_turns_the_gate_off():
    res = _run([date(2026, 5, 20)], cfg_extra={"stale_entry_max_trading_days": None})
    assert res and res["dte_entry"] == (EXP - ENTRY).days


def test_the_refusal_is_tallied_and_listed_first():
    assert sim.ENTRY_REFUSALS[0] == sim.STALE_LEG_REFUSAL
    from backtest.plays import build_matched_plays
    _p, _c, _n, skipped = build_matched_plays([], 0.02)
    assert skipped[sim.STALE_LEG_REFUSAL] == 0


@pytest.mark.parametrize("days,expected", [
    ([[SIGNAL], [DAY[1]]], (ENTRY, None)),
    ([[SIGNAL], [DAY[5]]], (DAY[5], None)),
    ([[SIGNAL], [date(2026, 5, 1), DAY[6]]], (None, 1)),
    ([[SIGNAL], []], (ENTRY, None)),                  # no quote: not judged here
])
def test_fresh_entry_date_unit(days, expected):
    assert sim.fresh_entry_date(days, SIGNAL, ENTRY, 5) == expected
