"""spy_put_write on SYNTHETIC quotes only. No figure here comes from a real quote.

Pins the registration's rules: strikes from D's spot on the $5 grid, the fill
on the next session's close on one clock, the 21-DTE expiry floor, the
calendar-only window, UNCACHED versus skip-listed strikes, the 50% target
checked from the session after the fill and filled at t+1, settlement at
intrinsic, commission, cycle means, PBO's two channels and the verdict
table's first-match order.
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.backtest import simulate as SIM
from scripts.backtest_study.f3_structure import spy_put_write as S
from scripts.backtest_study.f3_structure import structure_sweep as SS
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF

D = date(2024, 5, 13)            # a Monday
FILL = date(2024, 5, 14)
EXP = date(2024, 6, 21)


def weekdays(lo: date, hi: date) -> list[date]:
    out, d = [], lo
    while d <= hi:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


SESSIONS = weekdays(date(2024, 5, 1), EXP)


def row(bid: float, ask: float, latest: float | None = None) -> dict:
    return {"Bid": str(bid), "Ask": str(ask),
            "Latest": str(latest if latest is not None else (bid + ask) / 2),
            "Price~": "500"}


class FakeChain:
    """The two calls the study makes on a chain: `cached` and `history`.
    `asof` cuts every contract's rows after a date (the look-ahead check)."""

    def __init__(self, quotes: dict, asof: date | None = None):
        self.quotes = quotes          # {(expiry, strike): {date: row}}
        self.asof = asof
        self.idx: dict = {}           # `Study` builds a UniverseSpot over it; spot is replaced

    def cached(self, ticker, expiry, strike, opt):
        return opt == "Put" and (expiry, float(strike)) in self.quotes

    def history(self, leg):
        rows = {d: r for d, r in self.quotes.get((leg.expiration, float(leg.strike)), {}).items()
                if self.asof is None or d <= self.asof}
        series = []
        for d in sorted(rows):
            mid = SIM._close_mid(rows[d])
            series.append((d, mid if mid is not None else float(rows[d]["Latest"])))
        return series, rows


def spot_on_d_only(spot: float, day: date = D):
    def f(ticker, d, expiry):
        if d != day:
            raise AssertionError(f"spot read on {d}, not on D {day}")
        return spot
    return f


def flat_quotes(strikes, days, bid_ask) -> dict:
    return {(EXP, float(k)): {d: row(*bid_ask[k]) for d in days} for k in strikes}


# ── expiry and calendar ──────────────────────────────────────────────────────

def test_expiry_is_nearest_37_with_a_21_dte_floor_and_ties_to_the_earlier():
    # Jun 21 at 24 DTE beats Jul 19 at 52.
    assert S.rule_expiry(date(2024, 5, 28)) == date(2024, 6, 21)
    # Jun 21 at 18 DTE is under the floor, so Jul 19 (46 DTE) is taken.
    assert S.rule_expiry(date(2024, 6, 3)) == date(2024, 7, 19)
    # 23 and 51 DTE are both 14 from 37: the earlier wins.
    assert S.rule_expiry(date(2024, 5, 29)) == date(2024, 6, 21)


def test_signal_weeks_are_the_first_session_of_each_iso_week():
    sessions = [d for d in weekdays(date(2024, 5, 13), date(2024, 5, 31)) if d != date(2024, 5, 27)]
    assert S.signal_weeks(sessions) == [date(2024, 5, 13), date(2024, 5, 20), date(2024, 5, 28)]


def test_window_comes_from_the_calendar_and_the_cache_range_only():
    sessions = weekdays(date(2024, 1, 1), date(2024, 12, 31))
    weeks = S.signal_weeks(sessions)
    nxt = dict(zip(sessions, sessions[1:]))
    first_monthly, last_quote = date(2024, 3, 15), date(2024, 9, 20)
    win, before, after = S.in_sample_window(weeks, nxt, first_monthly, last_quote,
                                            before=date(2024, 12, 1))
    planned = {d: S.rule_expiry(nxt[d]) for d in weeks}
    assert planned[win[0]] >= first_monthly
    assert planned[weeks[weeks.index(win[0]) - 1]] < first_monthly
    assert planned[win[-1]] <= last_quote
    assert planned[weeks[weeks.index(win[-1]) + 1]] > last_quote
    assert before == weeks.index(win[0])
    assert after == sum(1 for d in weeks if win[-1] < d < date(2024, 12, 1))
    # Every week between the ends is in, whatever its trade would do: the
    # function takes no outcome, so an outcome cannot choose the sample.
    assert win == [d for d in weeks if win[0] <= d <= win[-1]]


# ── selection ────────────────────────────────────────────────────────────────

def test_strikes_come_from_d_spot_on_the_5_dollar_grid_ties_lower():
    q = flat_quotes((500, 450), [D, FILL], {500: (5.0, 5.2), 450: (1.0, 1.1)})
    chain = FakeChain(q)
    # Spot 502.5: 500 and 505 tie, the lower wins. Long target 500 - 50.25.
    p = S.select_strikes(chain, set(), spot_on_d_only(502.5), D, FILL, 1.00, 0.10)
    assert (p.status, p.k_s, p.k_l, p.expiry) == (S.BUILT, 500.0, 450.0, EXP)


def test_selection_reads_nothing_after_d():
    days = weekdays(D, EXP)
    q = flat_quotes((500, 450), days, {500: (5.0, 5.2), 450: (1.0, 1.1)})
    full = S.select_strikes(FakeChain(q), set(), spot_on_d_only(501), D, FILL, 1.0, 0.10)
    cut = S.select_strikes(FakeChain(q, asof=D), set(), spot_on_d_only(501), D, FILL, 1.0, 0.10)
    assert (full.status, full.k_s, full.k_l) == (cut.status, cut.k_s, cut.k_l)


def test_skip_listed_strike_is_stepped_past_but_an_uncached_one_stops_the_walk():
    # 500 is nearest. Skip-listed: the walk steps to 505 (cached, listed).
    q = flat_quotes((505, 495), [D], {505: (5, 5.2), 495: (4, 4.2)})
    chain = FakeChain(q)
    stem = NTF.contract_stem("SPY", EXP, 500.0, "Put")
    w = S.walk_strike(chain, {stem}, EXP, 501.0, D)
    assert (w.status, w.strike, w.steps) == (S.BUILT, 505.0, 1)
    # Not skip-listed and not cached: UNCACHED, never built on cached 505.
    w = S.walk_strike(chain, set(), EXP, 501.0, D)
    assert (w.status, w.strike) == (S.UNCACHED, 500.0)
    # Cached with no row by D counts as not cached.
    late = FakeChain({(EXP, 500.0): {FILL: row(5, 5.2)}})
    w = S.walk_strike(late, set(), EXP, 501.0, D)
    assert (w.status, w.detail) == (S.UNCACHED, "cached_no_row_by_D")


def test_uncached_long_leg_makes_the_trade_uncached():
    q = flat_quotes((500,), [D], {500: (5, 5.2)})
    p = S.select_strikes(FakeChain(q), set(), spot_on_d_only(500), D, FILL, 1.0, 0.10)
    assert p.status == S.UNCACHED and p.uncached[0][0] == "long"


# ── fills ────────────────────────────────────────────────────────────────────

def _pick(k_s=500.0, k_l=450.0) -> S.Pick:
    return S.Pick(D, FILL, EXP, 1.0, 0.10, S.BUILT, spot=500.0, k_s=k_s, k_l=k_l)


def test_both_legs_fill_on_the_next_session_close_on_one_clock():
    days = weekdays(D, EXP)
    q = {(EXP, 500.0): {d: row(5.0, 5.2) for d in days},
         (EXP, 450.0): {d: row(1.0, 1.2) for d in days}}
    q[(EXP, 500.0)][D] = row(9.0, 9.2)            # D's own quote must not be used
    e = S.price_entry(FakeChain(q), _pick(), SESSIONS, {EXP: 520.0})
    assert e.fill == FILL
    assert e.credit == pytest.approx(5.1 - 1.1)
    assert e.max_loss == pytest.approx((50 - 4.0) * 100)


def test_a_missing_leg_moves_both_legs_to_the_first_common_day_or_refuses():
    days = weekdays(D, EXP)
    q = {(EXP, 500.0): {d: row(5.0, 5.2) for d in days},
         (EXP, 450.0): {d: row(1.0, 1.2) for d in days if d != FILL}}
    q[(EXP, 500.0)][date(2024, 5, 15)] = row(6.0, 6.2)
    e = S.price_entry(FakeChain(q), _pick(), SESSIONS, {EXP: 520.0})
    assert e.fill == date(2024, 5, 15)
    assert e.credit == pytest.approx(6.1 - 1.1)   # the short's 05-15 quote, not 05-14's
    # No common day inside five weekdays from D: refused.
    q2 = {(EXP, 500.0): {d: row(5.0, 5.2) for d in days},
          (EXP, 450.0): {d: row(1.0, 1.2) for d in days if d > date(2024, 5, 20)}}
    assert S.price_entry(FakeChain(q2), _pick(), SESSIONS, {EXP: 520.0}) == SIM.NO_COMMON_ENTRY_DAY


def test_a_net_debit_at_entry_is_refused():
    days = weekdays(D, EXP)
    q = {(EXP, 500.0): {d: row(1.0, 1.2) for d in days},
         (EXP, 450.0): {d: row(5.0, 5.2) for d in days}}
    assert S.price_entry(FakeChain(q), _pick(), SESSIONS, {EXP: 520.0}) in (
        SIM.CREDIT_DEBIT_REFUSAL, SIM.NON_MONOTONIC_REFUSAL)


# ── exits ────────────────────────────────────────────────────────────────────

def _entry(marks, credit=4.0, settle=0.0, sessions=None) -> S.Entry:
    sessions = sessions or SESSIONS[SESSIONS.index(FILL):]
    marks = list(marks) + [marks[-1]] * (len(sessions) - len(marks))
    return S.Entry(_pick(), FILL, credit, 50.0, ("barchart_close_mid",) * 2, sessions, marks,
                   [("close_mid", "close_mid")] * len(sessions), settle)


def test_target_is_checked_from_the_session_after_the_fill_and_filled_at_t_plus_1():
    cell = S.Cell(1.0, 0.10, S.TARGET)
    # The fill day's own mark is under 50% and must not fire it.
    marks = [1.0, 3.0, 1.9, 1.5, 1.0]
    o = S.exit_target(_entry(marks), cell, 2.6)
    assert o.exit_reason == "target"
    assert o.exit_day == o.entry.sessions[3] and o.exit_value == pytest.approx(1.5)
    # t+1 unmarked: the close moves to the next session with a mark.
    o = S.exit_target(_entry([3.0, 3.0, 1.9, None, 1.2, 1.2]), cell, 2.6)
    assert o.exit_day == o.entry.sessions[4] and o.exit_value == pytest.approx(1.2)


def test_untriggered_target_closes_at_the_first_session_after_the_fill_with_21_dte():
    o = S.exit_target(_entry([3.5] * 5), S.Cell(1.0, 0.10, S.TARGET), 2.6)
    first21 = next(s for s in o.entry.sessions[1:] if (EXP - s).days <= 21)
    assert (o.exit_reason, o.exit_day) == ("dte21", first21)


def test_hold_settles_at_intrinsic_on_the_expiry_close():
    assert S.intrinsic(500, 450, 470) == pytest.approx(30)
    assert S.intrinsic(500, 450, 440) == pytest.approx(50)
    assert S.intrinsic(500, 450, 510) == 0.0
    e = _entry([3.0] * 3, credit=4.0, settle=S.intrinsic(500, 450, 490))
    o = S.exit_hold(e, S.PRIMARY, 2.6)
    assert o.exit_day == EXP and o.exit_value == pytest.approx(10.0)
    assert o.path_pnl[-1] == pytest.approx((4.0 - 10.0) * 100)


def test_settlement_reads_the_close_table_on_the_expiry_date():
    days = weekdays(D, EXP)
    q = {(EXP, 500.0): {d: row(5.0, 5.2) for d in days},
         (EXP, 450.0): {d: row(1.0, 1.2) for d in days}}
    e = S.price_entry(FakeChain(q), _pick(), SESSIONS, {EXP: 480.0, FILL: 999.0})
    assert e.settle == pytest.approx(20.0)


def test_commission_is_two_sides_two_legs_and_r_is_net_of_it():
    cfg = {"commission_per_contract": 0.65, "slippage_frac_of_spread": 0}
    legs = [S.put_leg(EXP, 500, -1), S.put_leg(EXP, 450, 1)]
    comm = SS.commission_dollars(legs, 1, cfg)
    assert comm == pytest.approx(2.60)
    o = S.exit_hold(_entry([3.0] * 3, credit=4.0, settle=0.0), S.PRIMARY, comm)
    assert o.gross == pytest.approx(400.0)
    assert o.R == pytest.approx((400.0 - 2.60) / ((50 - 4.0) * 100))


def test_stop_closes_at_the_session_after_the_breach():
    e = _entry([3.0, 16.0, 20.0, 25.0], credit=4.0, settle=0.0)
    o = S.exit_hold(e, S.PRIMARY, 2.6)
    # Breach (-$1,200) on session 1, filled at session 2's -$1,600.
    assert S.stop_R(o) == pytest.approx((-1600.0 - 2.6) / o.entry.max_loss)


def test_a_non_real_price_tag_raises(monkeypatch):
    days = weekdays(D, EXP)
    q = {(EXP, 500.0): {d: row(5.0, 5.2) for d in days},
         (EXP, 450.0): {d: row(1.0, 1.2) for d in days}}
    monkeypatch.setattr(S.SIM, "entry_day_fill", lambda r, qty: (1.0, "bs"))
    with pytest.raises(S.ModelPrice):
        S.price_entry(FakeChain(q), _pick(), SESSIONS, {EXP: 520.0})


# ── grading ──────────────────────────────────────────────────────────────────

def _o(expiry, R, signal=None, fill=None, exit_day=None):
    return SimpleNamespace(expiry=expiry, R=R, signal=signal or expiry,
                           entry=SimpleNamespace(fill=fill or expiry), exit_day=exit_day or expiry)


def test_cycle_means_keep_empty_cycles_as_slots_and_average_the_rest():
    c1, c2, c3 = date(2024, 1, 19), date(2024, 2, 16), date(2024, 3, 15)
    outs = [_o(c1, 0.2), _o(c1, 0.4), _o(c3, -0.1)]
    means = S.cycle_means(outs, [c1, c2, c3])
    assert means[0] == pytest.approx(0.3) and means[1] is None and means[2] == pytest.approx(-0.1)
    assert S.mean_of_means(means) == pytest.approx(0.1)


def test_grade_z_needs_120_trades_on_24_cycles():
    cycles = [date(2022 + i // 12, i % 12 + 1, 15) for i in range(30)]
    few = [_o(c, 0.1) for c in cycles[:23] for _ in range(6)]
    assert S.grade_z(few, cycles, n=200)["token"] == S.UNDERPOWERED
    rng = np.random.default_rng(1)
    many = [_o(c, 0.5 + 0.01 * rng.standard_normal()) for c in cycles for _ in range(5)]
    g = S.grade_z(many, cycles, n=500)
    assert g["c0"] and g["c1"] and g["token"] == S.POSITIVE


def test_grade_h_recovers_alpha_and_beta_on_a_clean_series():
    rng = np.random.default_rng(2)
    months = []
    for i in range(36):
        x = 0.02 * rng.standard_normal()
        months.append((f"{2022 + i // 12:04d}-{i % 12 + 1:02d}", 0.01 + 2.0 * x, x))
    g = S.grade_h(months, n=300)
    assert g["alpha"] == pytest.approx(0.01) and g["beta"] == pytest.approx(2.0)
    assert g["token"] == S.ALPHA
    assert S.grade_h(months[:23], n=50)["token"] == S.UNDERPOWERED


def test_pbo_matrix_has_two_channels_and_zero_rows_for_empty_weeks():
    w = [date(2024, 1, 1), date(2024, 1, 8), date(2024, 1, 15)]
    a, b = S.Cell(1.0, 0.1, S.HOLD), S.Cell(1.0, 0.05, S.HOLD)
    M = S.pbo_matrix({a: [_o(w[0], 0.3, signal=w[0])], b: [_o(w[2], -0.2, signal=w[2])]}, w)
    assert M.shape == (3, 2, 2)
    assert list(M[0, 0]) == [0.3, 1.0] and list(M[1, 0]) == [0.0, 0.0]
    assert list(M[2, 1]) == [-0.2, 1.0] and list(M[0, 1]) == [0.0, 0.0]


def test_pbo_is_not_computable_below_six_cells_or_without_the_primary():
    w = [date(2024, 1, 1) + timedelta(weeks=i) for i in range(80)]
    full = [_o(d, 0.1, signal=d) for d in w]
    cells = {c: list(full) for c in S.CELLS[:5]}
    res, elig, why = S.pbo_read(cells, w)
    assert res is None and len(elig) == 5
    cells = {c: list(full) for c in S.CELLS}
    cells[S.PRIMARY] = full[:59]
    assert S.pbo_read(cells, w)[0] is None
    cells[S.PRIMARY] = full
    res, elig, _ = S.pbo_read(cells, w)
    assert res is not None and elig[0] == S.PRIMARY


def test_verdict_table_is_read_top_to_bottom():
    z = lambda t, **k: dict(c0=True, token=t, c1=k.get("c1", True), c2=k.get("c2", True),  # noqa: E731
                            c3=k.get("c3", True))
    h = lambda t: dict(c0=True, token=t)  # noqa: E731
    assert S.study_token(False, z(S.POSITIVE), h(S.ALPHA), 0.1)[0] == S.UNCOVERED
    assert S.study_token(True, dict(c0=False, token=S.UNDERPOWERED), h(S.ALPHA), 0.1)[0] \
        == S.UNDERPOWERED
    assert S.study_token(True, z(S.POSITIVE), dict(c0=False), 0.1)[0] == S.UNDERPOWERED
    assert S.study_token(True, z(S.NEGATIVE), h(S.ALPHA), 0.9)[0] == S.LOSES
    assert S.study_token(True, z(S.POSITIVE), h(S.ALPHA), 0.51)[0] == S.PBO_VETO
    assert S.study_token(True, z(S.POSITIVE), h(S.ALPHA), None)[0] == S.PBO_VETO
    assert S.study_token(True, z(S.POSITIVE), h(S.ALPHA), 0.50)[0] == S.PUT_WRITE_ALPHA
    word, beside = S.study_token(True, z(S.POSITIVE), h(S.NEG_ALPHA), 0.2)
    assert word == S.BETA_ONLY and S.NEG_ALPHA in beside
    word, beside = S.study_token(True, z(S.NULL, c1=True, c2=False), h(S.NO_ALPHA), 0.2)
    assert word == S.NULL and "C2" in beside and S.NO_ALPHA in beside


def test_coverage_gate_needs_75_percent_overall_and_50_in_every_year():
    from collections import Counter
    ok = {2024: Counter(n=50, built=45), 2025: Counter(n=50, built=30)}
    assert S.coverage_gate(ok)[0]
    thin_year = {2024: Counter(n=90, built=90), 2025: Counter(n=10, built=4)}
    assert not S.coverage_gate(thin_year)[0]
    thin_all = {2024: Counter(n=50, built=36), 2025: Counter(n=50, built=36)}
    assert not S.coverage_gate(thin_all)[0]


def test_twelve_cells_with_the_registered_primary_first():
    assert len(S.CELLS) == 12 and len(set(S.CELLS)) == 12
    assert S.CELLS[0] == S.Cell(1.00, 0.10, S.HOLD) == S.PRIMARY


# ── wiring: Study.pick, outcomes ─────────────────────────────────────────────

JUL19 = date(2024, 7, 19)


def _study(quotes: dict, sessions: list[date], spot: float = 500.0, day: date | None = None):
    st = S.Study(chain=FakeChain(quotes), evidence=set(),
                 closes={d: 500.0 for d in sessions}, sim_cfg={})
    st.spot_u = spot_on_d_only(spot, day) if day else (lambda ticker, d, expiry: spot)
    return st


def test_study_fills_on_the_session_after_the_decision_date_at_that_sessions_quotes():
    d = date(2024, 5, 17)                      # a Friday: the next session is Monday, not d+1
    fill = date(2024, 5, 20)
    days = weekdays(date(2024, 5, 1), EXP)
    q = {}
    for k, (on_d, on_fill, after) in {500.0: ((9.0, 9.2), (5.0, 5.2), (4.0, 4.2)),
                                      450.0: ((2.0, 2.2), (1.0, 1.2), (0.5, 0.7))}.items():
        q[(EXP, k)] = {x: row(*(on_d if x == d else on_fill if x == fill else after))
                       for x in days}
    st = _study(q, days, day=d)
    p = st.pick(d, (1.0, 0.10))
    assert (p.status, p.fill, p.k_s, p.k_l) == (S.BUILT, fill, 500.0, 450.0)
    assert p.fill == st.sessions[st.sessions.index(d) + 1]
    e = st.entry(d, (1.0, 0.10))
    assert e.fill == fill
    assert e.credit == pytest.approx(5.1 - 1.1)          # D's 9.1 - 2.1 = 7.0 would be wrong


def test_outcomes_groups_trades_by_expiry_cycle_and_keys_cycles_on_the_planned_fill(
        monkeypatch, tmp_path, capsys):
    """Weeks 05-13 and 05-20 plan Jun 21; 05-29 plans Jul 19 only because its
    fill (05-30) is past the Jun 21 nearest-37 tie, while 05-29 itself ties to
    Jun 21. So a cycle list built from the decision date would lose Jul 19."""
    monkeypatch.setattr(S, "OUT_DIR", tmp_path)
    monkeypatch.setattr(S, "TRADES_CSV", tmp_path / "trades.csv")
    days = weekdays(date(2024, 5, 1), JUL19)
    strikes = (500, 485, 475, 460, 450, 435, 425)
    q = {(e, float(k)): {x: row(k / 100, k / 100 + 0.1) for x in days}
         for e in (EXP, JUL19) for k in strikes}
    st = _study(q, days)
    weeks = [date(2024, 5, 13), date(2024, 5, 20), date(2024, 5, 29)]
    assert S.rule_expiry(weeks[2]) == EXP and S.rule_expiry(st.nxt[weeks[2]]) == JUL19
    cens = {g: S.census(st, weeks, g) for g in S.GEOMS}
    seen = []
    real = S.grade_z

    def spy(outs, cycles, *a, **k):
        seen.append((list(outs), list(cycles)))
        return real(outs, cycles, *a, **k)

    monkeypatch.setattr(S, "grade_z", spy)
    assert S.outcomes(st, weeks, cens, 2.6) == 0
    capsys.readouterr()
    outs, cycles = seen[0]                      # the primary cell
    assert cycles == [EXP, JUL19]
    assert [o.expiry for o in outs] == [EXP, EXP, JUL19]
    means = S.cycle_means(outs, cycles)
    assert means[0] == pytest.approx((outs[0].R + outs[1].R) / 2)
    assert means[1] == pytest.approx(outs[2].R)


def test_grade_z_follows_the_cycle_mean_not_the_per_trade_mean():
    cycles = [date(2022 + i // 12, i % 12 + 1, 15) for i in range(30)]
    # One crowded cycle at +0.5 (100 trades), 29 single-trade cycles at -0.2.
    outs = [_o(cycles[0], 0.5) for _ in range(100)] + [_o(c, -0.2) for c in cycles[1:]]
    assert sum(o.R for o in outs) / len(outs) > 0.3          # per-trade mean is clearly positive
    g = S.grade_z(outs, cycles, n=2000)
    assert g["mean"] == pytest.approx((0.5 - 0.2 * 29) / 30)
    assert g["mean"] < 0 and g["ci"][1] < 0
    assert g["token"] == S.NEGATIVE


# ── ARM H monthly series ─────────────────────────────────────────────────────

def _book_trade(fill: date, expiry: date, mark_on, commission: float) -> S.Outcome:
    """A $4.00-credit, $50-wide hold that settles at 0 (gross +$400), marked
    by `mark_on(day)` per session."""
    sessions = weekdays(fill, expiry)
    pick = S.Pick(fill, fill, expiry, 1.0, 0.10, S.BUILT, spot=500.0, k_s=500.0, k_l=450.0)
    e = S.Entry(pick, fill, 4.0, 50.0, ("close_mid",) * 2, sessions,
                [mark_on(s) for s in sessions], [("close_mid",) * 2] * len(sessions), 0.0)
    return S.exit_hold(e, S.PRIMARY, commission)


def _book():
    # A: open 05-14 -> 08-16, spread 3.0 to May 31 (+$100), 2.0 in June (+$200),
    #    5.0 in July (-$100), settles worthless on exit (+$400).
    a = _book_trade(date(2024, 5, 14), date(2024, 8, 16),
                    lambda s: 3.0 if s <= date(2024, 5, 31) else 2.0 if s < date(2024, 7, 1) else 5.0,
                    0.0)
    # B: open 06-03 -> 06-21, settles worthless (+$400), $2.60 commission at its exit.
    b = _book_trade(date(2024, 6, 3), EXP, lambda s: 3.5, 2.60)
    closes = {date(2024, 5, 31): 500.0, date(2024, 6, 28): 510.0, date(2024, 7, 1): 999.0,
              date(2024, 7, 31): 495.9, date(2024, 8, 16): 1.0}
    return [a, b], closes


def test_monthly_series_is_mtm_equity_change_net_of_commission_over_reference_capital():
    """Pinned: months run from the first full month after the first fill (May,
    the fill month, is dropped) to the last calendar month ending on or before
    the last exit (August, which ends after the 08-16 exit, is dropped). Each
    month is (equity at its last session - equity at the prior month's last
    session) / capital, equity = marked level of open trades + booked dollars of
    closed ones - commissions of trades exited on or before that day. The SPY
    return uses the last close on or before each month-end (07-01 is ignored)."""
    outs, closes = _book()
    months, bc = S.monthly_series(outs, closes)
    assert [m[0] for m in months] == ["2024-06", "2024-07"]
    # June: A marked +$200 (still open), B booked +$400, commission 2.60; May: A +$100.
    assert months[0][1] == pytest.approx((200 + 400 - 2.60 - 100) / 25_000)
    # July: A marked -$100 (open, MTM not realised), B unchanged; the commission is already in June.
    assert months[1][1] == pytest.approx((-100 - 200) / 25_000)
    assert months[0][2] == pytest.approx(510 / 500 - 1) and months[1][2] == pytest.approx(495.9 / 510 - 1)
    assert bc.n_positions == 2


def test_monthly_series_divides_by_the_capital_it_is_given_and_defaults_to_25000():
    outs, closes = _book()
    base = S.monthly_series(outs, closes)[0]
    assert S.REF_CAPITAL == 25_000.0
    half = S.monthly_series(outs, closes, capital=50_000.0)[0]
    assert [m[1] for m in half] == pytest.approx([m[1] / 2 for m in base])


def test_monthly_series_charges_commission_in_the_month_of_the_exit():
    outs, closes = _book()
    free = S.monthly_series([outs[0], _book_trade(date(2024, 6, 3), EXP, lambda s: 3.5, 0.0)],
                            closes)[0]
    paid = S.monthly_series(outs, closes)[0]
    assert free[0][1] - paid[0][1] == pytest.approx(2.60 / 25_000)
    assert free[1][1] == pytest.approx(paid[1][1])


def test_monthly_series_of_an_empty_book_or_a_book_with_no_full_month_is_empty():
    assert S.monthly_series([], {}) == ([], None)
    short = _book_trade(date(2024, 5, 14), EXP, lambda s: 3.0, 0.0)   # fills May, exits Jun 21
    assert S.monthly_series([short], {date(2024, 5, 31): 500.0})[0] == []


# ── leg mark and ARM H tokens ────────────────────────────────────────────────

def _history(day_rows: dict):
    q = {(EXP, 500.0): day_rows}
    return FakeChain(q).history(S.put_leg(EXP, 500.0, -1))


def test_leg_mark_is_the_closing_mid_on_a_clean_quote():
    series, details = _history({D: row(5.0, 5.2)})
    assert S.leg_mark(series, details, D, EXP) == (pytest.approx(5.1), "close_mid")


def test_leg_mark_carries_the_last_snap_on_a_day_without_a_row_and_none_before_any():
    series, details = _history({D: row(5.0, 5.2)})
    assert S.leg_mark(series, details, FILL, EXP) == (pytest.approx(5.1), "carried")
    assert S.leg_mark(series, details, date(2024, 5, 10), EXP) is None


def _months(alpha: float, noise: float, seed: int = 3) -> list[tuple]:
    rng = np.random.default_rng(seed)
    out = []
    for i in range(36):
        x = 0.02 * rng.standard_normal()
        out.append((f"{2022 + i // 12:04d}-{i % 12 + 1:02d}",
                    alpha + 2.0 * x + noise * rng.standard_normal(), x))
    return out


@pytest.mark.parametrize("alpha, noise, token", [
    (-0.01, 0.001, S.NEG_ALPHA),       # interval wholly below zero
    (0.01, 0.001, S.ALPHA),            # wholly above zero, stable by year and stress month
    (0.0, 0.05, S.NO_ALPHA),           # noise swamps a zero alpha: interval spans zero
])
def test_grade_h_token_follows_the_alpha_interval(alpha, noise, token):
    g = S.grade_h(_months(alpha, noise), n=500)
    if token == S.NO_ALPHA:
        assert g["ci"][0] < 0 < g["ci"][1]
    assert g["token"] == token


def test_h_token_needs_every_criterion_for_alpha_but_only_c1_for_negative():
    base = dict(c0=True, c1=True, c2=True, c3=True, alpha=0.01)
    assert S.h_token(base) == S.ALPHA
    assert S.h_token({**base, "c2": False}) == S.NO_ALPHA
    assert S.h_token({**base, "c3": False}) == S.NO_ALPHA
    assert S.h_token({**base, "alpha": -0.01, "c2": False}) == S.NEG_ALPHA
    assert S.h_token({**base, "c1": False}) == S.NO_ALPHA
