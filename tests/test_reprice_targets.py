"""The re-price census's set membership (next-steps §0 items 6, 7, 9).

Pure functions only, on synthetic rows: no export, no cache, no network.
"""
from datetime import date

from scripts.backtest.legs import Leg
from scripts.backtest_study.lib import reprice_targets as RT

EXP = date(2025, 5, 30)


def _row(**kw):
    base = {"signal_date": "2025-04-09", "ticker": "HYG", "structure": "bear_put_spread",
            "legs": "HYG:2025-05-30:76:P +1\nHYG:2025-05-30:72:P -1",
            "dte_entry": str((EXP - date(2025, 4, 10)).days), "days_held": "5",
            "entry_leg_detail": ("HYG:2025-05-30:76:P +1  px=0.97 iv=20% delta=-0.4 "
                                 "[barchart_open]\n"
                                 "HYG:2025-05-30:72:P -1  px=0.45 iv=20% delta=-0.2 "
                                 "[barchart_open]")}
    base.update(kw)
    return base


def test_entry_leg_tags_reads_each_leg_and_its_tag():
    tags = RT.entry_leg_tags(_row()["entry_leg_detail"])
    assert [t for _, t in tags] == ["barchart_open", "barchart_open"]
    assert tags[1][0] == Leg(-1, "HYG", EXP, 72.0, "Put")


def test_recorded_entry_day_is_anchor_expiry_minus_dte():
    assert RT.recorded_entry_day(_row()) == date(2025, 4, 10)


def test_prefill_is_an_exit_before_the_recorded_fill():
    # Fill on 04-14 = grid position 3 (04-10, 04-11, 04-14); an exit on day 2 is
    # before it, an exit on day 3 is not.
    dte = str((EXP - date(2025, 4, 14)).days)
    assert RT.is_prefill(_row(dte_entry=dte, days_held="2"))
    assert not RT.is_prefill(_row(dte_entry=dte, days_held="3"))
    assert not RT.is_prefill(_row(days_held=""))          # no exit index: unanswerable


class _FakeCache:
    def __init__(self, rows):
        self.rows = rows

    def details(self, leg):
        return self.rows.get(leg.strike)


def test_every_open_fill_with_a_row_is_claimed():
    """Since 2026-10-23 production fills every leg off the entry day's closing
    quote (`entry_day_fill`), so a stored Open-print leg is never what it does
    today: one-sided, two-sided, wide or traded, each is claimed."""
    day = date(2025, 4, 10)
    clean = {"Bid": "0.90", "Ask": "1.04", "Open": "0.97", "_mark": 0.97}
    cases = [
        {76.0: {day: clean},
         72.0: {day: {"Bid": "0.00", "Ask": "2.68", "Open": "0.45", "_mark": 1.34}}},
        {76.0: {day: clean},
         72.0: {day: {"Bid": "0.40", "Ask": "0.50", "Open": "0.45", "_mark": 0.45}}},
        {76.0: {day: {"Bid": "0.20", "Ask": "1.90", "Open": "0.97", "_mark": 1.05,
                      "Volume": "0"}},
         72.0: {day: {"Bid": "0.40", "Ask": "0.50", "Open": "0.45", "_mark": 0.45}}},
        {76.0: {day: {"Bid": "0.00", "Ask": "1.90", "Open": "0.97", "_mark": 0.95,
                      "Volume": "5", "Latest": "0.98"}},
         72.0: {day: clean}},
    ]
    for rows in cases:
        assert RT.open_fill_legs(_row(), _FakeCache(rows)) == (2, 0)


def test_open_fill_reports_a_leg_it_cannot_check():
    """No cached row on the fill day is UNDETERMINABLE, never a miss."""
    day = date(2025, 4, 10)
    partial = {76.0: {day: {"Bid": "0.90", "Ask": "1.04", "Open": "0.97", "_mark": 0.97}}}
    assert RT.open_fill_legs(_row(), _FakeCache(partial)) == (1, 1)


def test_a_same_day_entry_open_fill_is_claimed():
    """An entry on the signal day never filled at the Open either."""
    day = date(2025, 4, 9)
    same_day = _row(dte_entry=str((EXP - day).days))
    rows = {76.0: {day: {"Bid": "0.90", "Ask": "1.04", "Open": "0.97", "_mark": 0.97}},
            72.0: {day: {"Bid": "0.40", "Ask": "0.50", "Open": "0.45", "_mark": 0.45}}}
    assert RT.open_fill_legs(same_day, _FakeCache(rows)) == (2, 0)


def test_a_leg_not_filled_at_the_open_is_not_an_open_fill():
    day = date(2025, 4, 10)
    detail = _row()["entry_leg_detail"].replace("[barchart_open]\nHYG", "[barchart]\nHYG")
    rows = {76.0: {day: {"Bid": "0.00", "Ask": "1.04", "Open": "0.97", "_mark": 0.52}},
            72.0: {day: {"Bid": "0.40", "Ask": "0.50", "Open": "0.45", "_mark": 0.45}}}
    # Only the leg stored as `[barchart_open]` (the 72P) is counted.
    assert RT.open_fill_legs(_row(entry_leg_detail=detail), _FakeCache(rows)) == (1, 0)


def test_redo_plan_is_date_bounded_results_first():
    report = [{"tab": RT.RESULTS, "signal_date": "2024-11-26", "target_sets": "wrong_strike"},
              {"tab": RT.PROXY, "signal_date": "2024-02-06", "target_sets": "wrong_strike"},
              {"tab": RT.PROXY, "signal_date": "2024-02-07", "target_sets": ""}]
    plan = RT.redo_plan(report)
    assert plan == [
        "python3 -m scripts.backtest --config config/backtest.yml --date 2024-02-06 --redo",
        "python3 -m scripts.backtest --config config/backtest.yml --date 2024-11-26 --redo",
        "python3 -m scripts.backtest.proxy --config config/backtest.yml --date 2024-02-06 --redo",
        "python3 -m scripts.backtest.proxy --config config/backtest.yml --date 2024-11-26 --redo",
    ]
