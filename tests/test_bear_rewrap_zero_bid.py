"""`bear_rewrap`'s pricer mirrors production's zero-bid re-mark (robustness B5).

Production (`scripts/backtest/simulate.py::_zero_bid_mark`, 3e5c2dc) marks a
leg quoted `bid 0` at `ask/2`, or 0 when nothing is offered, on the daily path
AND on a zero-volume entry. `bear_rewrap.reconstructs` re-prices stored book
rows through its own mirror, and until 2026-09-17 that mirror kept the old
mid-else-Latest mark, so five post-fold rows failed `hedge_structure`'s R2.

A stored row written BEFORE the fold was priced without B5, so the mirror
follows the row's write time (`priced_with_b5`); everything priced fresh takes
the production rule.

Synthetic cache only — `bear_rewrap.leg_details` is monkeypatched.
"""
from datetime import date, datetime, timedelta

import pytest

import scripts.backtest.simulate as SIM
from scripts.backtest.legs import Leg
from scripts.backtest_study.f3_structure import bear_rewrap as BR

EXP = date(2025, 5, 30)
LONG = Leg(1, "AAA", EXP, 76.0, "Put")
SHORT = Leg(-1, "AAA", EXP, 72.0, "Put")
D0 = date(2025, 4, 10)
D1 = D0 + timedelta(days=1)


def _row(mark, bid=None, ask=None, open_="0"):
    """A row as `parse_history_details(require_mark=False)` returns it."""
    return {"_mark": mark, "Bid": bid, "Ask": ask, "Open": open_}


@pytest.fixture()
def cache(monkeypatch):
    store: dict[tuple, dict] = {}

    def put(leg, rows):
        store[(leg.ticker, leg.expiration, leg.strike, leg.opt_type)] = rows

    monkeypatch.setattr(
        BR, "leg_details",
        lambda leg: store.get((leg.ticker, leg.expiration, leg.strike, leg.opt_type), {}))
    return put


def test_the_rule_is_imported_from_production_not_restated():
    assert BR._zero_bid_mark is SIM._zero_bid_mark


@pytest.mark.parametrize("row,expected", [
    (_row(0.45, bid="0", ask="2.68"), 1.34),       # bid-less: half the offer
    (_row(0.45, bid="0.00", ask="0.00"), 0.0),     # nothing bid, nothing offered
    (_row(2.00, bid="1.90", ask="2.10"), 2.00),    # two-sided: the row's own mark
    (_row(0.45), 0.45),                            # no quote columns: own mark
    (_row(None, bid="0", ask="2.68"), None),       # no mark at all: production never
])                                                 # loads the row, so no re-mark
def test_row_mark_applies_b5(row, expected):
    got = BR.row_mark(row)
    assert got == (None if expected is None else pytest.approx(expected))


def test_row_mark_without_b5_is_the_plain_mark():
    assert BR.row_mark(_row(0.45, bid="0", ask="2.68"), b5=False) == 0.45


def test_carried_forward_mark_is_the_re_mark(cache):
    # D0 is bid-less; D1 has no row, so the mark on D1 is D0's CARRIED re-mark —
    # production re-marks the snap it carries (`_price_leg`), not only fresh days.
    cache(SHORT, {D0: _row(0.45, bid="0", ask="2.68")})
    assert BR.leg_series(SHORT) == [(D0, pytest.approx(1.34))]
    assert BR.net_marks([SHORT], [D0, D1]) == [pytest.approx(-1.34)] * 2
    assert BR.net_marks([SHORT], [D0, D1], b5=False) == [pytest.approx(-0.45)] * 2


def test_zero_volume_entry_takes_the_re_mark_even_at_zero(cache):
    # 0x0 at entry is worth 0 and says so — it does not fall through to an
    # older day's mark (production `_entry_price_leg`, B5 branch).
    cache(SHORT, {D0: _row(0.80, bid="1.0", ask="1.2"),
                  D1: _row(0.45, bid="0", ask="0")})
    assert BR.entry_price_of(SHORT, D1) == 0.0
    assert BR.entry_price_of(SHORT, D1, b5=False) == 0.45


def test_a_positive_open_still_wins_over_the_re_mark(cache):
    cache(SHORT, {D1: _row(0.45, bid="0", ask="2.68", open_="0.65")})
    assert BR.entry_price_of(SHORT, D1) == 0.65


def test_entry_carry_forward_re_marks_the_carried_snap(cache):
    # The HYG 2025-04-09 shape: the long leg fills at its Open on D1, the short
    # has no row that day, and the carried D0 snap is bid 0 / ask 2.68.
    cache(LONG, {D1: _row(0.92, bid="0.01", ask="1.83", open_="0.97")})
    cache(SHORT, {D0: _row(0.45, bid="0", ask="2.68", open_="0.65")})
    assert BR.net_entry([LONG, SHORT], D1) == pytest.approx(-0.37)
    assert BR.net_entry([LONG, SHORT], D1, b5=False) == pytest.approx(0.52)


@pytest.mark.parametrize("stamp,expected", [
    ("2026-09-08 10:31:15", False),   # last pre-fold write on the 09-08 export
    ("2026-09-08 15:05:24", False),
    ("2026-09-08 15:05:25", True),    # the merge of 3e5c2dc
    ("2026-09-08 17:36:58", True),    # a retried queue-D date
    ("2026-08-14 20:42:47", False),
    ("", True),                        # unstamped: current production rule
])
def test_priced_with_b5_follows_the_row_write_time(stamp, expected):
    assert BR.B5_SINCE == datetime(2026, 9, 8, 15, 5, 25)
    assert BR.priced_with_b5({"created_datetime": stamp}) is expected


def test_basis_of_sets_the_default_for_every_pricer_inside_it(cache):
    cache(SHORT, {D0: _row(0.45, bid="0", ask="2.68")})
    pre = {"created_datetime": "2026-08-14 20:42:47"}
    post = {"created_datetime": "2026-09-08 17:36:58"}
    assert BR.entry_price_of(SHORT, D1) == pytest.approx(1.34)       # no basis: B5
    with BR.basis_of(pre):
        assert BR.entry_price_of(SHORT, D1) == pytest.approx(0.45)
        with BR.basis_of(post):
            assert BR.entry_price_of(SHORT, D1) == pytest.approx(1.34)
        assert BR.net_marks([SHORT], [D1]) == [pytest.approx(-0.45)]
        assert BR.entry_price_of(SHORT, D1, b5=True) == pytest.approx(1.34)  # explicit wins
    assert BR.entry_price_of(SHORT, D1) == pytest.approx(1.34)


def test_each_on_basis_restores_the_default_after_a_break(cache):
    cache(SHORT, {D0: _row(0.45, bid="0", ask="2.68")})
    rows = [{"created_datetime": "2026-08-14 20:42:47"}] * 3
    seen = []
    for row in BR.each_on_basis(rows, lambda r: r):
        seen.append(BR.entry_price_of(SHORT, D1))
        break
    assert seen == [pytest.approx(0.45)]
    assert BR.entry_price_of(SHORT, D1) == pytest.approx(1.34)
