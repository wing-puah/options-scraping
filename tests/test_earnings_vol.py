"""earnings_vol (research/pre-registrations/f3_structure/earnings_vol.md): the
verdict grammar, the season-cluster bootstrap, halves, the calendar credit
refusal, straddle and double-calendar P&L, no-lookahead, the seal and the PBO
matrix, on synthetic data only.

No figure here comes from the cache or an export: each test writes its own
option files into a temporary directory.
"""
from __future__ import annotations

import csv
import math
from datetime import date, timedelta

import numpy as np

from scripts.backtest_study.f3_structure import earnings_vol as V
from scripts.backtest_study.lib import era
from scripts.collector.study_legs import fetch_earnings_legs as FEL


def _sessions(start=date(2025, 1, 6), n=80):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


SESS = _sessions()


def _plan(ann=date(2025, 2, 11), e=date(2025, 2, 12), close=100.0, candidates=None,
          front=date(2025, 2, 14), back=date(2025, 3, 14)):
    """`candidates` defaults to the planner's own ladder for `close`."""
    entry = SESS[SESS.index(e) - 5]
    cands = FEL.strike_ladder(close) if candidates is None else candidates
    return FEL.EventPlan("TST", ann, "amc", e, entry, e, close, front, back, cands, close)


def _event(**kw):
    p = _plan(**kw)
    return V.Event("TST", p.ann_date, "amc", p, SESS[SESS.index(p.e) - 1])


def _write(tmp, expiry, strike, right, quotes: dict):
    """`quotes`: {date: (bid, ask)}; rows written newest first, like Barchart."""
    path = FEL.cache_path(tmp, "TST", expiry, strike, "Call" if right == "C" else "Put")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Time", "Latest", "Price~", "Bid", "Ask"])
        for d in sorted(quotes, reverse=True):
            b, a = quotes[d]
            w.writerow([d.isoformat(), round((b + a) / 2, 4), 100.0, b, a])
    return path


def _flat(ev, mid, days=None):
    days = days or [d for d in SESS if ev.plan.entry <= d <= ev.plan.e]
    return {d: (mid - 0.05, mid + 0.05) for d in days}


# ── verdict grammar ───────────────────────────────────────────────────────────

def test_verdict_grammar():
    good = {"H1": (10, 0.05), "H2": (8, 0.02)}
    assert V.verdict((0.01, 0.20), good, -0.05) == V.EDGE
    assert V.verdict((0.01, 0.20), good, 0.0) == V.EDGE              # <= 0 passes
    assert V.verdict((0.01, 0.20), good, 0.05) == V.REWRAP
    assert V.verdict((0.01, 0.20), good, 0.05, bar=0.10) == V.EDGE
    assert V.verdict((-0.30, -0.01), good, -0.5) == V.CONTRARY
    assert V.verdict((-0.10, 0.20), good, -0.5) == V.NULL
    assert V.verdict((0.01, 0.20), {"H1": (10, 0.05), "H2": (8, -0.01)}, -0.5) == V.NULL
    assert V.verdict((0.01, 0.20), good, float("nan")) == V.NULL     # G1 not evaluable
    assert V.verdict((float("nan"), float("nan")), good, -0.5) == V.NULL


# ── seasons, halves, cluster bootstrap ────────────────────────────────────────

def test_seasons_and_halves_split_by_report_date():
    assert len(V.SEASONS) == 11 and V.SEASONS[0] == (2024, 1) and V.SEASONS[-1] == (2026, 3)
    assert [V.half_of(s) for s in V.SEASONS].count("H1") == 6
    assert [V.half_of(s) for s in V.SEASONS].count("H2") == 5
    assert V.half_of((2025, 2)) == "H1" and V.half_of((2025, 3)) == "H2"
    # an amc report on 2025-06-30 has E on 07-01, but its season is the report's
    ev = _event()
    ev.ann_date = date(2025, 6, 30)
    assert ev.season == (2025, 2) and V.half_of(ev.season) == "H1"


def test_cluster_bootstrap_resamples_whole_seasons():
    # season A: 99 events at 0; season B: 1 event at 1. Resampling EVENTS would
    # put the CI near 0.01; resampling SEASONS draws B whole half the time.
    vals = [0.0] * 99 + [1.0]
    cl = [(2024, 1)] * 99 + [(2024, 2)]
    lo, hi, k = V.cluster_ci(vals, cl, n=2000, seed=1)
    # draws are AA (0), AB (1/100) or BB (1): a quarter of them hold B twice
    assert k == 2 and lo == 0.0 and hi == 1.0


def test_cluster_ci_single_season_is_nan():
    lo, hi, k = V.cluster_ci([0.1, 0.2, 0.3], [(2024, 1)] * 3)
    assert k == 1 and math.isnan(lo) and math.isnan(hi)


def test_loso_reports_the_minimum():
    m, s = V.loso([1.0, 1.0, -5.0, 2.0], [(2024, 1), (2024, 1), (2024, 2), (2024, 3)])
    # removing 2024-Q1 leaves (-5+2)/2 = -1.5, the minimum
    assert s == (2024, 1) and m == -1.5


# ── trades: P&L math, credit refusal, drops ───────────────────────────────────

def test_straddle_pnl_math(tmp_path):
    ev = _event()
    p = ev.plan
    for r, (m0, m1) in (("C", (3.0, 6.0)), ("P", (2.0, 0.5))):
        q = _flat(ev, m0)
        q[p.e] = (m1 - 0.05, m1 + 0.05)
        _write(tmp_path, p.front, 100.0, r, q)
    q = V.Quotes(tmp_path)
    k, why = V.pick_atm(ev, q)
    assert (k, why) == (100.0, "")
    t = V.run_trade(ev, "S", "mid", "E", k, why, q, SESS)
    assert t.status == "ok"
    assert math.isclose(t.debit, 5.0)
    # (6.0 + 0.5 - 5.0) * 100 - 2 legs x 0.65 x 2 sides
    assert math.isclose(t.pnl, 150.0 - 2.6)
    assert math.isclose(t.ret, (150.0 - 2.6) / 500.0)
    assert math.isclose(t.marks[p.entry], -1.3)
    # natural: buy at the ask, sell at the bid
    tn = V.run_trade(ev, "S", "natural", "E", k, why, q, SESS)
    assert math.isclose(tn.debit, 5.1)
    # close: both longs sold at the bid
    assert math.isclose(tn.pnl, (5.95 + 0.45 - 5.1) * 100 - 2.6)


def test_double_calendar_pnl_math(tmp_path):
    ev = _event()
    p = ev.plan
    # front call/put 2.0 -> 0.5 (crush), back call/put 4.0 -> 3.6
    for x, m0, m1 in ((p.front, 2.0, 0.5), (p.back, 4.0, 3.6)):
        for r in ("C", "P"):
            q = _flat(ev, m0)
            q[p.e] = (m1 - 0.05, m1 + 0.05)
            _write(tmp_path, x, 100.0, r, q)
    q = V.Quotes(tmp_path)
    t = V.run_trade(ev, "K", "mid", "E", 100.0, "", q, SESS)
    assert t.status == "ok"
    assert math.isclose(t.debit, 4.0)                 # 2 x (4.0 - 2.0)
    value_exit = 2 * (3.6 - 0.5)
    assert math.isclose(t.pnl, (value_exit - 4.0) * 100 - 2 * 4 * 0.65)
    # natural: long backs bought at the ask, short fronts sold at the bid
    tn = V.run_trade(ev, "K", "natural", "E", 100.0, "", q, SESS)
    assert math.isclose(tn.debit, 2 * (4.05 - 1.95))
    # close: backs sold at the bid, fronts bought back at the ask
    assert math.isclose(tn.pnl, (2 * (3.55 - 0.55) - tn.debit) * 100 - 5.2)


def test_calendar_priced_to_a_credit_is_refused(tmp_path):
    ev = _event()
    p = ev.plan
    for x, m in ((p.front, 5.0), (p.back, 4.0)):
        for r in ("C", "P"):
            _write(tmp_path, x, 100.0, r, _flat(ev, m))
    q = V.Quotes(tmp_path)
    t = V.run_trade(ev, "K", "mid", "E", 100.0, "", q, SESS)
    assert t.status == "calendar_credit" and t.ret is None and not t.marks


def test_back_leg_not_quoted_at_entry_is_its_own_reason(tmp_path):
    ev = _event()
    p = ev.plan
    for r in ("C", "P"):
        _write(tmp_path, p.front, 100.0, r, _flat(ev, 2.0))
        later = [d for d in SESS if p.entry < d <= p.e]          # listed after entry
        _write(tmp_path, p.back, 100.0, r, _flat(ev, 4.0, later))
    q = V.Quotes(tmp_path)
    assert V.run_trade(ev, "K", "mid", "E", 100.0, "", q, SESS).status == \
        "back_not_quoted_at_entry"
    assert V.run_trade(ev, "S", "mid", "E", 100.0, "", q, SESS).status == "ok"


def test_back_leg_not_fetched_and_unlisted(tmp_path):
    ev = _event()
    p = ev.plan
    for r in ("C", "P"):
        _write(tmp_path, p.front, 100.0, r, _flat(ev, 2.0))
    q = V.Quotes(tmp_path)
    assert V.run_trade(ev, "K", "mid", "E", 100.0, "", q, SESS).status == "back_not_fetched"
    key = V.UL.contract_id(dict(symbol="TST", expiration=p.back, strike=100.0, opt_type="Call"))
    q2 = V.Quotes(tmp_path, {key: {}})
    assert V.run_trade(ev, "K", "mid", "E", 100.0, "", q2, SESS).status == "back_unlisted"


def test_missing_exit_row_drops(tmp_path):
    ev = _event()
    p = ev.plan
    no_exit = [d for d in SESS if p.entry <= d < p.e]
    _write(tmp_path, p.front, 100.0, "C", _flat(ev, 2.0, no_exit))
    _write(tmp_path, p.front, 100.0, "P", _flat(ev, 2.0))
    q = V.Quotes(tmp_path)
    assert V.run_trade(ev, "S", "mid", "E", 100.0, "", q, SESS).status == "front_missing_exit"
    # the run-up exit (E-1) still has its row
    assert V.run_trade(ev, "S", "mid", "E-1", 100.0, "", q, SESS).status == "ok"


# ── ATM strike ─────────────────────────────────────────────────────────────────

def test_atm_nearest_close_ties_lower(tmp_path):
    ev = _event(close=102.25)                        # 0.25 from both 102 and 102.5
    for k in (102.0, 102.5):
        for r in ("C", "P"):
            _write(tmp_path, ev.plan.front, k, r, _flat(ev, 2.0))
    assert V.pick_atm(ev, V.Quotes(tmp_path)) == (102.0, "")
    ev2 = _event(close=102.4)
    assert V.pick_atm(ev2, V.Quotes(tmp_path)) == (102.5, "")


def test_atm_passes_over_unlisted_failed_and_unquoted_nearer_candidates(tmp_path):
    ev = _event(close=101.2)                         # ladder 101, 101.5, 102, 100, 102.5
    p = ev.plan
    assert p.candidates == (101.0, 101.5, 102.0, 100.0, 102.5)
    later = [d for d in SESS if p.entry < d <= p.e]
    for r in ("C", "P"):
        _write(tmp_path, p.front, 102.0, r, _flat(ev, 2.0, later))   # no entry-day row
        _write(tmp_path, p.front, 100.0, r, _flat(ev, 2.0))
    unl = {V.UL.contract_id(dict(symbol="TST", expiration=p.front, strike=101.0,
                                 opt_type="Call")): {}}
    failed = {FEL.contract_stem("TST", p.front, 101.5, "P")}
    q = V.Quotes(tmp_path, unl, failed)
    assert V.pick_atm(ev, q) == (100.0, "")
    # without the failure record, 101.5 is simply unfetched: drop, never move the strike
    assert V.pick_atm(ev, V.Quotes(tmp_path, unl)) == (None, "front_not_fetched")
    # every candidate passed over
    q3 = V.Quotes(tmp_path, unl, failed | {FEL.contract_stem("TST", p.front, 100.0, "C")})
    FEL.cache_path(tmp_path, "TST", p.front, 100.0, "Call").unlink()
    for r in ("C", "P"):
        _write(tmp_path, p.front, 102.5, r, _flat(ev, 2.0, later))
    assert V.pick_atm(ev, q3) == (None, "front_no_candidate")


def test_back_leg_failed_drops_arm_k_only(tmp_path):
    ev = _event()
    p = ev.plan
    for r in ("C", "P"):
        _write(tmp_path, p.front, 100.0, r, _flat(ev, 2.0))
    q = V.Quotes(tmp_path, None, {FEL.contract_stem("TST", p.back, 100.0, "C")})
    assert V.pick_atm(ev, q) == (100.0, "")
    assert V.run_trade(ev, "K", "mid", "E", 100.0, "", q, SESS).status == "back_failed"
    assert V.run_trade(ev, "S", "mid", "E", 100.0, "", q, SESS).status == "ok"


# ── no lookahead ───────────────────────────────────────────────────────────────

def test_future_quotes_cannot_change_strike_or_entry_mark(tmp_path):
    ev = _event(close=101.0, candidates=(101.0, 100.0))
    p = ev.plan
    # 101: quoted only AFTER entry (passed over); 100: quoted from entry on
    later = [d for d in SESS if p.entry < d <= p.e]
    for r in ("C", "P"):
        _write(tmp_path, p.front, 101.0, r, _flat(ev, 2.0, later))
    for k in (100.0,):
        for r in ("C", "P"):
            _write(tmp_path, p.front, k, r, _flat(ev, 2.0))
            _write(tmp_path, p.back, k, r, _flat(ev, 3.0))
    q = V.Quotes(tmp_path)
    k0 = V.pick_atm(ev, q)
    assert k0 == (100.0, "")
    t0 = V.run_trade(ev, "K", "mid", "E", k0[0], "", q, SESS)
    # rewrite every row AFTER entry with absurd prices
    for k in (100.0,):
        for r in ("C", "P"):
            for x in (p.front, p.back):
                quotes = _flat(ev, 2.0 if x == p.front else 3.0)
                for d in quotes:
                    if d > p.entry:
                        quotes[d] = (50.0, 50.1)
                _write(tmp_path, x, k, r, quotes)
    q2 = V.Quotes(tmp_path)
    assert V.pick_atm(ev, q2) == k0
    t1 = V.run_trade(ev, "K", "mid", "E", k0[0], "", q2, SESS)
    assert t1.debit == t0.debit and t1.marks[p.entry] == t0.marks[p.entry]


def test_planner_ignores_closes_and_prices_after_entry():
    sess = _sessions(date(2025, 1, 6), 200)
    closes = {d: 10.0 + 0.01 * i for i, d in enumerate(sess)}       # split-adjusted
    prices = {d: [10 * v] * 3 for d, v in closes.items()}           # chain basis x10
    events_by = {"TST": [(date(2025, 4, 8), "bmo")]}
    a, _ = V.plan_events(["TST"], sessions=sess, events_by=events_by,
                         closes_by={"TST": (closes, "x")}, prices_by={"TST": prices},
                         include_unknown=False)
    pa = a[0].plan
    assert pa.factor == 10.0 and pa.rebased
    entry = pa.entry
    later = {d: (v * 3 if d > entry else v) for d, v in closes.items()}
    later_px = {d: (v if d <= entry else [v[0] / 10] * 3) for d, v in prices.items()}
    b, _ = V.plan_events(["TST"], sessions=sess, events_by=events_by,
                         closes_by={"TST": (later, "x")}, prices_by={"TST": later_px},
                         include_unknown=False)
    pb = b[0].plan
    assert (pa.close, pa.factor, pa.candidates, pa.front, pa.back, pa.entry, pa.e) == \
        (pb.close, pb.factor, pb.candidates, pb.front, pb.back, pb.entry, pb.e)


def test_atm_ignores_rows_after_entry(tmp_path):
    """A nearer candidate whose files gain rows only AFTER entry stays passed
    over; the ATM is decided by entry-day rows alone."""
    ev = _event(close=101.2)
    p = ev.plan
    for r in ("C", "P"):
        _write(tmp_path, p.front, 101.0, r, _flat(ev, 2.0, [d for d in SESS if d > p.entry]))
        _write(tmp_path, p.front, 101.5, r, _flat(ev, 2.0))
    assert V.pick_atm(ev, V.Quotes(tmp_path)) == (101.5, "")


def test_g1_alignment_uses_no_later_row():
    ev = _event()
    p = ev.plan
    t = V.Trade(ev, "S", "mid", "E", 100.0)
    t.debit = 5.0
    days = [d for d in SESS if p.entry <= d <= p.e]
    for i, d in enumerate(days):
        t.marks[d] = float(10 * i)
    t.pnl = t.marks[p.e]
    axis = days[:-1]
    base = V.IV.on_axis([t], axis, SESS)
    t2 = V.Trade(ev, "S", "mid", "E", 100.0)
    t2.debit, t2.marks = 5.0, dict(t.marks)
    t2.marks[p.e] = t2.pnl = 1e6                   # a change dated AFTER every axis session
    assert V.IV.on_axis([t2], axis, SESS) == base


# ── seal, seal readers, PBO ───────────────────────────────────────────────────

def test_sealed_events_are_not_in_sample():
    sess = _sessions(date(2026, 8, 3), 60)
    closes = {d: 100.0 for d in sess}
    events_by = {"TST": [(date(2026, 9, 8), "bmo"), (date(2026, 9, 23), "bmo"),
                         (date(2026, 9, 22), "amc")]}
    evs, tps = V.plan_events(["TST"], sessions=sess, events_by=events_by,
                             closes_by={"TST": (closes, "x")}, include_unknown=False)
    assert [e.ann_date for e in evs] == [date(2026, 9, 8)]
    assert all(e.plan.e < V.SEAL_START for e in evs)
    assert {a for a, _ in tps["TST"].sealed} == {date(2026, 9, 23), date(2026, 9, 22)}


def test_not_a_seal_reader():
    assert "earnings_vol" not in era.SEALED_READERS
    assert V.SEAL_START == date.fromisoformat(era.SEAL_START) == FEL.SEAL_START


def _trade_in(season_date, cfg, ret):
    ev = _event()
    ev.ann_date = season_date
    a, f, x = cfg
    t = V.Trade(ev, a, f, x, 100.0)
    t.debit, t.pnl = 1.0, ret * 100
    t.marks = {ev.plan.entry: 0.0, t.exit_day: t.pnl}
    return t


def test_pbo_matrix_shape_trim_and_pad():
    trades = {c: [_trade_in(date(y, 3 * q - 1, 15), c, 0.01 * (i + 1))
                  for y, q in V.SEASONS] for i, c in enumerate(V.CONFIGS)}
    M, trim, pad = V.pbo_matrix(trades)
    assert M.shape == (10, 8) and trim == 1 and pad == 0
    assert np.allclose(M[:, 0], 0.01)                  # 2024-Q1 trimmed from the head
    M7, trim7, pad7 = V.pbo_matrix(trades, seasons=V.SEASONS[:7])
    assert M7.shape == (10, 8) and trim7 == 0 and pad7 == 3
    assert np.all(M7[:3] == 0)
    # a season with no kept event scores 0, it is not dropped
    trades[V.CONFIGS[0]] = trades[V.CONFIGS[0]][1:]
    M2, _, _ = V.pbo_matrix(trades)
    assert M2.shape == (10, 8)
    assert len(V.CONFIGS) == 8
