"""index_vrp (research/pre-registrations/f3_structure/index_vrp.md): strike
selection, the VIX tercile, settlement, condor max loss, the verdict grammar and
the cycle calendar, on synthetic data only.

No figure here comes from the cache or an export: each test builds its own chain.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from scripts.backtest_study.f3_structure import index_vrp as V
from scripts.backtest_study.lib import era


def _days(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _row(bid, ask, delta=0.0, iv=20.0, spot=100.0, latest=None):
    return {"Bid": str(bid), "Ask": str(ask), "Latest": str(latest if latest is not None else (bid + ask) / 2),
            "Delta": str(delta), "IV": str(iv), "Price~": str(spot), "Volume": "10"}


def _chain(days, spot_path, strikes=range(80, 121, 5), expiry=None):
    """A chain whose every contract quotes every day at a tight 0.10 spread.

    Deltas fall linearly with moneyness so the 0.16 call sits at 110 and the
    -0.16 put at 90 on a 100 spot.
    """
    ch = V.Chain("TST", expiry or days[-1])
    for k in strikes:
        for typ in ("C", "P"):
            by = {}
            for d, s in zip(days, spot_path):
                val = max(0.05, V.intrinsic(typ, k, s) + 1.0)
                m = (k - s) / s
                dlt = max(0.01, 0.5 - 3.4 * m) if typ == "C" else -max(0.01, 0.5 + 3.4 * m)
                by[d] = _row(round(val - 0.05, 2), round(val + 0.05, 2), dlt, 20.0, s)
            ch.rows[(typ, float(k))] = by
    return ch


# ── selection uses entry-day rows only ────────────────────────────────────────

def test_short_and_wing_pick_ignores_future_rows():
    days = _days(date(2024, 1, 2), 25)
    ch = _chain(days, [100.0] * len(days))
    legs, why = V.build_legs(ch, days[0], "C", 0.16, 100.0)
    assert why == "ok"
    picked = [(lg.typ, lg.strike) for lg in legs]
    # A future row with an absurd delta and price at a strike that is far off
    # target on the entry day must not move the pick.
    ch.rows[("C", 100.0)][days[5]] = _row(500.0, 600.0, delta=0.16, spot=100.0)
    ch.rows[("P", 120.0)][days[5]] = _row(500.0, 600.0, delta=-0.16, spot=100.0)
    legs2, _ = V.build_legs(ch, days[0], "C", 0.16, 100.0)
    assert [(lg.typ, lg.strike) for lg in legs2] == picked


def test_select_delta_skips_zero_and_wrong_sign():
    rows = {100.0: _row(1, 1.1, delta=0.0), 105.0: _row(1, 1.1, delta=0.20),
            110.0: _row(1, 1.1, delta=0.14), 115.0: _row(1, 1.1, delta=-0.16)}
    assert V.select_delta(rows, 0.16) == 110.0


def test_wing_landing_on_short_moves_one_strike_out():
    assert V.select_wing([100.0, 105.0, 110.0], 105.0, 106.0, "C") == 110.0
    assert V.select_wing([95.0, 100.0, 105.0], 100.0, 99.0, "P") == 95.0
    assert V.select_wing([100.0, 105.0], 105.0, 106.0, "C") is None


def test_atm_ties_to_the_lower_strike():
    calls = {95.0: {}, 100.0: {}, 105.0: {}}
    assert V.select_atm(calls, dict(calls), 102.5) == 100.0


# ── VIX tercile is past-only ──────────────────────────────────────────────────

def test_vix_percentile_ignores_future_values():
    days = _days(date(2020, 1, 1), 900)
    vix = [10.0 + (i % 50) for i in range(900)]
    mk = V.Market(days, [100.0] * 900, list(vix))
    d = days[800]
    base = V.vix_percentile(mk, d)
    for i in range(801, 900):
        mk.vix[i] = 1e6
    assert V.vix_percentile(mk, d) == base
    mk.vix[700] = 1e6          # a past value inside the window does move it
    assert V.vix_percentile(mk, d) != base


def test_vix_percentile_needs_a_full_window_and_splits_terciles():
    days = _days(date(2020, 1, 1), 10)
    mk = V.Market(days, [1.0] * 10, [float(i) for i in range(10)])
    assert V.vix_percentile(mk, days[5], window=756)[1] is None
    _v, p = V.vix_percentile(mk, days[9], window=10)
    assert p == 1.0 and V.tercile(p) == "high"
    assert V.tercile(0.2) == "low" and V.tercile(0.5) == "mid" and V.tercile(None) is None


# ── settlement and max loss ───────────────────────────────────────────────────

def test_straddle_settles_at_intrinsic_on_expiry_spot():
    days = _days(date(2024, 1, 2), 20)
    path = [100.0] * 19 + [108.0]
    ch = _chain(days, path)
    c = V.run_cycle(ch, "TST", days[0] - timedelta(days=3), days[0], days[-1], days,
                    "S", "mid")
    assert c.status == "ok" and c.legs[0].strike == 100.0
    # entry mid: call 1.0 + put 1.0 = 2.0 per share
    assert c.credit == pytest.approx(2.0)
    owed = 8.0
    assert c.pnl == pytest.approx((2.0 - owed) * 100 - 4 * V.COMMISSION)
    assert c.vrp_price() == pytest.approx((2.0 - 8.0) / 100.0)
    assert c.mae == c.pnl and c.marks[days[0]] == pytest.approx(-2 * V.COMMISSION)


def test_condor_max_loss_and_capped_settlement():
    days = _days(date(2024, 1, 2), 20)
    path = [100.0] * 19 + [120.0]
    ch = _chain(days, path)
    c = V.run_cycle(ch, "TST", days[0] - timedelta(days=3), days[0], days[-1], days,
                    "C", "mid", 0.16)
    assert c.status == "ok"
    sc, lc, sp, lp = (lg.strike for lg in c.legs)
    width = max(lc - sc, sp - lp)
    assert c.max_loss == pytest.approx((width - c.credit) * 100)
    # far through the call wing: the loss is capped at the max loss plus commission
    assert c.pnl == pytest.approx(-c.max_loss - 8 * V.COMMISSION)


def test_missing_sessions_carry_then_drop():
    days = _days(date(2024, 1, 2), 20)
    ch = _chain(days, [100.0] * 20)
    del ch.rows[("C", 100.0)][days[3]]
    c = V.run_cycle(ch, "TST", days[0] - timedelta(days=3), days[0], days[-1], days,
                    "S", "mid")
    assert c.status == "ok" and c.n_carried == 1
    for d in days[4:6]:
        del ch.rows[("C", 100.0)][d]
    c = V.run_cycle(ch, "TST", days[0] - timedelta(days=3), days[0], days[-1], days,
                    "S", "mid")
    assert c.status == "leg_missing_sessions"


def test_junk_quote_falls_back_to_latest():
    assert V.mid_mark(_row(1.0, 1.2))[1] == "mid"
    px, tag = V.mid_mark(_row(0.05, 4.0, latest=0.30))
    assert tag == "junk" and px == 0.30
    assert V.natural_fill(_row(0.0, 0.10), sold=True) == (0.0, "nobid")
    assert V.natural_fill(_row(1.0, 1.2), sold=False) == (1.2, "natural")


def test_bad_spot_print_is_rejected():
    assert V.accept_spot(101.0, 100.0)
    assert not V.accept_spot(25.0, 100.0)
    assert not V.accept_spot(None, 100.0)


# ── calendar ──────────────────────────────────────────────────────────────────

def test_cycles_do_not_overlap_and_use_the_holiday_thursday():
    days = _days(date(2022, 1, 1), 400)
    good_friday = date(2022, 4, 15)
    days = [d for d in days if d != good_friday]
    tset = set(days)
    cyc = V.cycles((2022, 3), date(2022, 12, 31), tset)
    assert cyc[0][1] == date(2022, 3, 18)
    assert date(2022, 4, 14) in [e for _p, e in cyc]
    prev_exp = None
    for p, e in cyc:
        entry = V.pick_entry(days, p, e)
        assert p < entry < e
        if prev_exp is not None:
            assert entry > prev_exp
        prev_exp = e


def test_pick_entry_ties_to_the_earlier_day():
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(60)]
    e = date(2024, 2, 20)
    got = V.pick_entry([d for d in days if (e - d).days in (29, 31)], date(2023, 12, 1), e)
    assert (e - got).days == 31


# ── statistics and the verdict ────────────────────────────────────────────────

def test_tail_mean_reads_the_books_worst_sessions():
    import numpy as np
    book = np.array([-100.0, 5, 6, 7, 8, 9, 10, 11, 12, 13] * 2)
    sleeve = np.where(book < 0, -50.0, 1.0)
    assert V.tail_mean(book, sleeve, 0.10) == pytest.approx(-50.0)
    ts = V.tail_stats(book, sleeve, block=2, n_paths=200)
    assert ts.t1 == pytest.approx(-50.0)


def test_verdict_loses_together():
    w = {"W2": (-1.0, -1.0), "W3": (-1.0, -2.0), "W4": (-1.0, +3.0)}
    assert V.verdict(w, (-10.0, -1.0), 0.3, 0.2)[0] == V.LOSES
    assert V.verdict(w, (-10.0, +1.0), 0.3, 0.2)[0] == V.NO_LINK


def test_verdict_diversifies_and_no_link():
    w = {"W2": (-1.0, +1.0), "W3": (-1.0, +2.0), "W4": (+1.0, -3.0)}
    assert V.verdict(w, (+1.0, +5.0), 0.3, 0.2)[0] == V.DIVERSIFIES
    assert V.verdict(w, (+1.0, +5.0), 0.3, 0.4)[0] == V.NO_LINK
    assert V.verdict(w, (-1.0, +5.0), 0.3, 0.2)[0] == V.NO_LINK


def test_verdict_with_fewer_than_two_losing_windows():
    w = {"W3": (-1.0, -1.0)}
    tok, note = V.verdict(w, (-10.0, -1.0), 0.3, 0.2)
    assert tok == V.NO_LINK and "cannot be met" in note
    tok, _ = V.verdict({"W2": (-1.0, -1.0), "W3": (+1.0, -1.0)}, (+1.0, +2.0), 0.3, 0.2)
    assert tok == V.DIVERSIFIES


def test_premium_token():
    assert V.premium_token(0.001) == V.PREMIUM
    assert V.premium_token(-0.001) == V.NO_PREMIUM
    assert V.premium_token(math.nan) == V.NO_PREMIUM


def test_not_a_sealed_reader():
    assert "index_vrp" not in era.SEALED_READERS
    assert V.DESIGNED_REFUSAL_EXIT_CODES == {2, 3}
