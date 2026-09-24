"""`bear_rewrap`'s pricer mirrors production's zero-bid re-mark (robustness B5).

Production (`scripts/backtest/simulate.py::_zero_bid_mark`, 3e5c2dc) marks a
leg quoted `bid 0` at `ask/2`, or 0 when nothing is offered, on the daily path
AND on a zero-volume entry. `bear_rewrap.reconstructs` re-prices stored book
rows through its own mirror, and until 2026-09-17 that mirror kept the old
mid-else-Latest mark, so five post-fold rows failed `hedge_structure`'s R2.

A stored row written BEFORE the fold was priced without B5, so the mirror
follows the row's write time (`priced_with_b5`); everything priced fresh takes
the production rule.

Since commit 09aa02c there is a SECOND basis on the same pattern: a one-sided
ENTRY quote is filled on the side the leg trades (`_entry_side_mark` — sold at
the bid, bought at the ask), which displaced `_zero_bid_mark` at entry and left
the daily path alone. So a row has two write-time-keyed bases, and the entry
tests below pin all three regimes a stored row can be in: pre-B5/pre-side,
post-B5/pre-side, and post-side.

Since 2026-09-22 there is a THIRD: the side-aware fill PRECEDES the entry-day
`Open` print (`priced_with_open_side`). Before, a leg that printed an Open kept
it whatever its quote said.

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
    assert BR._entry_side_mark is SIM._entry_side_mark


@pytest.mark.parametrize("stamp,expected", [
    ("2026-09-08 22:02:15", False),   # last write before the side rule shipped
    ("2026-09-19 12:50:44", False),
    ("2026-09-19 12:50:45", True),    # commit 09aa02c
    ("2026-09-19 16:45:19", True),    # the 2025-04-09 re-price
    ("", True),                        # unstamped: current production rule
])
def test_priced_with_side_follows_the_row_write_time(stamp, expected):
    assert BR.SIDE_SINCE == datetime(2026, 9, 19, 12, 50, 45)
    assert BR.priced_with_side({"created_datetime": stamp}) is expected


def test_the_two_bases_are_independent():
    """A row written between the two commits is B5 on its marks and NOT
    side-aware on its entry — the reason there are two constants."""
    between = {"created_datetime": "2026-09-08 17:36:58"}
    assert BR.priced_with_b5(between) is True
    assert BR.priced_with_side(between) is False


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
    assert BR.entry_price_of(SHORT, D1, b5=False, side=False) == 0.45
    # Both bases agree here: nothing is offered, so the side rule's bid and the
    # liquidation rule's ask/2 are the same 0.
    assert BR.entry_price_of(SHORT, D1, side=True) == 0.0


def test_a_positive_open_wins_over_the_re_mark_before_the_open_side_basis(cache):
    cache(SHORT, {D1: _row(0.45, bid="0", ask="2.68", open_="0.65")})
    assert BR.entry_price_of(SHORT, D1, open_side=False) == 0.65
    assert BR.entry_price_of(SHORT, D1, side=False) == 0.65     # pre-side: same


def test_the_open_side_basis_fills_a_one_sided_quote_ahead_of_the_open(cache):
    """Mirror of production's `_entry_price_leg` since 2026-09-22."""
    cache(SHORT, {D1: _row(0.45, bid="0", ask="2.68", open_="0.65")})
    cache(LONG, {D1: _row(0.92, bid="0", ask="1.83", open_="0.97")})
    assert BR.entry_price_of(SHORT, D1) == 0.0           # the default is current
    assert BR.entry_price_of(SHORT, D1, open_side=True) == 0.0
    assert BR.entry_price_of(LONG, D1, open_side=True) == pytest.approx(1.83)
    # A two-sided quote keeps its Open on every basis.
    cache(LONG, {D1: _row(0.92, bid="0.01", ask="1.83", open_="0.97")})
    assert BR.entry_price_of(LONG, D1, open_side=True) == pytest.approx(0.97)
    # open_side implies side: without the side rule it cannot apply.
    assert BR.entry_price_of(SHORT, D1, side=False, open_side=True) == 0.65


def test_the_mirror_and_production_agree_on_an_open_print_entry(cache):
    """Same one-sided-with-Open rows through `_simulate` and through the mirror."""
    rows_long = {D1: _row(0.92, bid="0", ask="1.83", open_="0.97")}
    rows_short = {D1: _row(0.30, bid="0.25", ask="0.35", open_="0.30")}
    cache(LONG, rows_long)
    cache(SHORT, rows_short)
    mirror = BR.net_entry([LONG, SHORT], D1)
    key = lambda leg: SIM._contract_key(leg.ticker, leg.opt_type, leg.strike,
                                        leg.expiration.isoformat())
    details = {key(LONG): rows_long, key(SHORT): rows_short}
    for rows in details.values():
        rows[D1 + timedelta(days=1)] = _row(1.0, bid="0.9", ask="1.1")
    series = {k: sorted((d, r["_mark"]) for d, r in v.items()) for k, v in details.items()}
    entry_row = {"Strike": 76.0, "DTE": (EXP - D1).days, "IV": "30", "Price~": "78",
                 "Delta": "-0.4", "_entry_date": D1}
    cand = {"ticker": "AAA", "signal_date": D0, "play": "bear put spread"}
    cfg = {"profit_target": None, "stop_loss": None, "contracts": 1, "path_cap_days": 3,
           "entry_sources": ["barchart"], "exit_sources": ["barchart"]}
    res = SIM._simulate(cand, [LONG, SHORT], entry_row, {}, series, cfg,
                        structure="bear_put_spread",
                        barchart_details=details)
    assert float(res["entry_option_price"]) == pytest.approx(mirror) == pytest.approx(1.53)


@pytest.mark.parametrize("stamp,expected", [
    ("2026-09-19 16:45:19", False),   # the 2025-04-09 re-price: side, not over Open
    ("2026-09-22 11:59:59", False),
    ("2026-09-22 12:00:00", True),
    ("", True),
])
def test_priced_with_open_side_follows_the_row_write_time(stamp, expected):
    assert BR.OPEN_SIDE_SINCE == datetime(2026, 9, 22, 12, 0, 0)
    assert BR.priced_with_open_side({"created_datetime": stamp}) is expected


def test_entry_carry_forward_re_marks_the_carried_snap(cache):
    # The HYG 2025-04-09 shape: the long leg fills at its Open on D1, the short
    # has no row that day, and the carried D0 snap is bid 0 / ask 2.68.
    cache(LONG, {D1: _row(0.92, bid="0.01", ask="1.83", open_="0.97")})
    cache(SHORT, {D0: _row(0.45, bid="0", ask="2.68", open_="0.65")})
    # Pre-side basis: the liquidation rule pays ask/2 as premium RECEIVED on a
    # leg being sold, which is what took the real HYG row to a -0.37 credit.
    assert BR.net_entry([LONG, SHORT], D1, side=False) == pytest.approx(-0.37)
    assert BR.net_entry([LONG, SHORT], D1, b5=False, side=False) == pytest.approx(0.52)
    # Side basis: nothing is bid, so nothing is received and the spread is the
    # 0.97 debit production now records. This is the reconstruction that
    # `hedge_structure`'s R2 needs, and it holds only through the CARRIED snap —
    # the short leg has no row on D1 at all.
    assert BR.net_entry([LONG, SHORT], D1, side=True) == pytest.approx(0.97)
    assert BR.net_entry([LONG, SHORT], D1) == pytest.approx(0.97)  # side is the default


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
    pre = {"created_datetime": "2026-08-14 20:42:47"}    # pre-B5, pre-side
    post = {"created_datetime": "2026-09-08 17:36:58"}   # post-B5, PRE-side
    side = {"created_datetime": "2026-09-19 16:45:19"}   # post-side
    assert BR.entry_price_of(SHORT, D1) == 0.0           # no basis: current rule
    with BR.basis_of(pre):
        assert BR.entry_price_of(SHORT, D1) == pytest.approx(0.45)
        with BR.basis_of(post):
            assert BR.entry_price_of(SHORT, D1) == pytest.approx(1.34)
        with BR.basis_of(side):
            assert BR.entry_price_of(SHORT, D1) == 0.0
        assert BR.net_marks([SHORT], [D1]) == [pytest.approx(-0.45)]
        # explicit wins over the basis, one flag at a time
        assert BR.entry_price_of(SHORT, D1, b5=True) == pytest.approx(1.34)
        assert BR.entry_price_of(SHORT, D1, side=True) == 0.0
    assert BR.entry_price_of(SHORT, D1) == 0.0
    # The daily mark is NOT side-aware on any basis: B5 still owns the path.
    with BR.basis_of(side):
        assert BR.net_marks([SHORT], [D1]) == [pytest.approx(-1.34)]


def test_each_on_basis_restores_the_default_after_a_break(cache):
    cache(SHORT, {D0: _row(0.45, bid="0", ask="2.68")})
    rows = [{"created_datetime": "2026-08-14 20:42:47"}] * 3
    seen = []
    for row in BR.each_on_basis(rows, lambda r: r):
        seen.append(BR.entry_price_of(SHORT, D1))
        break
    assert seen == [pytest.approx(0.45)]
    assert BR.entry_price_of(SHORT, D1) == 0.0
    assert not BR._basis_stack and not BR._side_stack and not BR._open_side_stack


# ── the entry DAY is read off the row, never re-derived ──────────────────────


class _FakeTrade:
    """Just the three attributes `recorded_entry_date` touches."""

    def __init__(self, dte, legs=(LONG, SHORT)):
        self.row = {"dte_entry": dte}
        self.legs = list(legs)


@pytest.mark.parametrize("dte,expected", [
    (46, date(2025, 4, 14)),      # HYG 2025-04-09: exp 2025-05-30 - 46
    ("46", date(2025, 4, 14)),    # the CSV round-trip hands it back as a string
    ("46.0", date(2025, 4, 14)),
    (0, EXP),                     # filled on the expiry itself
])
def test_recorded_entry_date_reads_dte_entry(dte, expected):
    assert BR.recorded_entry_date(_FakeTrade(dte)) == expected


@pytest.mark.parametrize("dte", [None, "", "n/a"])
def test_recorded_entry_date_is_none_without_a_usable_stamp(dte):
    # The gate then falls back to the derived day rather than refusing the row.
    assert BR.recorded_entry_date(_FakeTrade(dte)) is None


def test_recorded_entry_date_uses_the_anchor_leg_not_the_short_one():
    """`dte_entry` is stamped on the ANCHOR contract (`legs[0]`), so a diagonal
    whose legs have different expiries must measure from the anchor's."""
    far = Leg(-1, "AAA", date(2025, 7, 18), 72.0, "Put")
    assert BR.recorded_entry_date(_FakeTrade(46, legs=(LONG, far))) == date(2025, 4, 14)
    assert BR.recorded_entry_date(_FakeTrade(46, legs=(far, LONG))) == date(2025, 6, 2)


def test_the_recorded_day_and_the_derived_day_can_disagree(cache):
    """The HYG 2025-04-09 shape, which is why the gate reads rather than derives.

    The long leg's first bar is D1 and the short leg's is D0, so production
    filled on D1 and carried the short leg forward. `entry_date_for` waits for a
    day BOTH legs have a bar on — D2 — and rebuilds a different spread. The
    cache gained the bars that make the two diverge only AFTER the row was
    priced, so the derived day cannot be trusted for a stored row.
    """
    D2 = D0 + timedelta(days=2)
    cache(LONG, {D1: _row(0.92, bid="0.01", ask="1.83", open_="0.97"),
                 D2: _row(0.75, bid="0", ask="2.90", open_="0.75")})
    cache(SHORT, {D0: _row(0.45, bid="0", ask="2.68", open_="0.65"),
                  D2: _row(0.28, bid="0", ask="2.39", open_="0.28")})

    assert BR.entry_date_for([LONG, SHORT], [D0, D1, D2]) == D2
    assert BR.recorded_entry_date(_FakeTrade((EXP - D1).days)) == D1

    # The derived day rebuilds a 0.47 debit; the recorded one the true 0.97.
    # The row was priced 2026-09-19, before the side rule preceded the Open.
    assert BR.net_entry([LONG, SHORT], D2, True, True, False) == pytest.approx(0.47)
    assert BR.net_entry([LONG, SHORT], D1, True, True, False) == pytest.approx(0.97)
