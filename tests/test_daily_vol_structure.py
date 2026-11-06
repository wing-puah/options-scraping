"""daily_vol_structure: the mirror identity, the one-clock fill, the fixed exit, the
coverage gate, feature timing, the discovery split, the verdict words and the
collector's dry run.

Synthetic chains and bars only. No network, and no QQQ or SMH option file is read.
Two checks read committed-format calendars when present: the 60/40 date and the
frozen `E-VOL` label's coverage.
"""
from __future__ import annotations

import ast
import asyncio
import csv
import math
import random
import re
import statistics
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from scripts.backtest_study.f1_selection.regime import market_read as MR
from scripts.backtest_study.f1_selection.regime import selloff_put_diagonal as SPD
from scripts.backtest_study.f3_structure import daily_vol_structure as V
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF
from scripts.backtest_study.lib import era, forward_drawdown as FD
from scripts.backtest_study.lib.underlying import Bar
from scripts.collector.study_legs import fetch_daily_vol_structure_legs as F

D = date(2024, 6, 3)
FILL = date(2024, 6, 4)
EXIT_T7 = date(2024, 6, 6)
EXPIRY = date(2024, 6, 14)
SPOT = 450.0


def weekdays(lo: date, hi: date) -> list[date]:
    out, d = [], lo
    while d <= hi:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def row(bid, ask, **extra) -> dict:
    mid = (bid + ask) / 2 if ask is not None and bid else None
    out = {"Bid": bid, "Ask": ask, "Latest": extra.pop("latest", mid or 0.0),
           "Open": extra.pop("open", 999.0), "Volume": extra.pop("volume", 100),
           "IV": extra.pop("iv", 20.0), "Price~": extra.pop("px", SPOT), "_mark": mid}
    out.update(extra)
    return out


def chain_of(contracts: dict, ticker: str = "QQQ") -> NTF.Chain:
    """A Chain over `{(opt, expiry, strike): {date: row}}`, no files."""
    idx: dict = {}
    ch = NTF.Chain(idx=idx)
    for (opt, exp, k), rows in contracts.items():
        idx.setdefault((ticker, exp), {}).setdefault(float(k), set()).add(opt[0])
        series = [(d, r["_mark"]) for d, r in sorted(rows.items()) if r["_mark"] is not None]
        ch._memo[(ticker, exp, round(float(k), 4), opt)] = (series, dict(rows))
    return ch


def trade(ticker="QQQ", tenor=V.T7, atm=450.0, wc=460.0, wp=440.0) -> V.Trade:
    return V.Trade(ticker, tenor, D, FILL, EXIT_T7, "built", expiry=EXPIRY, spot=SPOT,
                   atm=atm, wing_c=wc, wing_p=wp)


def four_leg_chain(ac=(5.0, 5.2, 7.0, 7.2), ap=(4.0, 4.2, 3.0, 3.2), wc=(1.0, 1.2, 2.0, 2.2),
                   wp=(1.5, 1.7, 1.0, 1.2)) -> NTF.Chain:
    """Each tuple: fill bid, ask, exit bid, ask."""
    c = {}
    for (opt, k), (b0, a0, b1, a1) in {("Call", 450.0): ac, ("Put", 450.0): ap,
                                       ("Call", 460.0): wc, ("Put", 440.0): wp}.items():
        c[(opt, EXPIRY, k)] = {D: row(b0, a0), FILL: row(b0, a0), EXIT_T7: row(b1, a1)}
    return chain_of(c)


# ── the design ──────────────────────────────────────────────────────────────

def test_cell_count_and_series():
    assert len(V.series_keys()) == 12
    assert len(V.features_for("QQQ")) == 22
    assert len(V.features_for("SMH")) == 20
    assert len(V.all_cells()) == 6 * 22 + 6 * 20 == 252
    assert not [c for c in V.all_cells() if c[0] == "SMH" and c[3].startswith("qqq_")]


def test_analysis_cells_leave_the_family_and_the_shortlist_is_frozen():
    assert len(V.graded_cells()) == 144
    assert len(V.analysis_cells()) == 108
    assert not [c for c in V.graded_cells() if V.FEATURE_BY_NAME[c[3]].is_analysis]
    assert V.SHORTLIST == ("mkt_dir", "mkt_vol", "mkt_hp_score")
    assert len(V.shortlist_cells()) == 36
    assert all(V.FEATURE_BY_NAME[c[3]].source == "analysis_market" for c in V.shortlist_cells())


def test_the_block_is_at_least_the_hold_of_every_tenor():
    assert all(V.BLOCK >= t.hold for t in V.TENORS)
    assert V.T30.hold == 5 and V.T7.hold == 2
    assert V.WING[("SMH", "T30")] == 0.09 and V.WING[("QQQ", "T7")] == 0.025


def test_no_harness_no_model_price_in_the_module():
    tree = ast.parse(Path(V.__file__).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {node.module or ""} | {a.name for a in node.names}
        elif isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
    assert not names & {"harness", "greeks", "black_scholes", "book"}
    assert "pbo" in names
    src = Path(V.__file__).read_text()
    for banned in ("black_scholes(", "bs_price", "_simulate(", "CREDIT_PROD["):
        assert banned not in src


# ── the mirror identity ─────────────────────────────────────────────────────

@pytest.mark.parametrize("structure", ["RC", "RP"])
def test_front_is_minus_back_at_mid_before_commission(structure):
    p = V.run_trade(four_leg_chain(), trade(), structure)
    assert isinstance(p, V.Priced)
    back = p.net("back") * SPOT + p.comm
    front = p.net("front") * SPOT + p.comm
    assert front == pytest.approx(-back)
    assert back == pytest.approx(p.gross)
    assert p.y == pytest.approx(p.gross / SPOT)


def test_mirror_holds_on_a_wide_junk_leg_and_commission_is_per_side():
    wide = four_leg_chain(wc=(0.5, 6.0, 0.5, 6.0))     # ask more than 3x bid
    p = V.run_trade(wide, trade(), "RC")
    assert isinstance(p, V.Priced)
    # One price for the wing whichever side holds it: the bought-side closing mid.
    assert p.entry[("Call", 460.0)] == pytest.approx((0.5 + 6.0) / 2)
    # The side-aware call would fill a sold junk leg at its bid, breaking the mirror.
    sold = V.SIM.entry_day_fill(row(0.5, 6.0), -1)
    assert sold[0] == 0.5
    assert p.net("front") * SPOT + p.comm == pytest.approx(-(p.net("back") * SPOT + p.comm))
    assert p.comm == pytest.approx(0.65 * 6 / 100)
    assert V.run_trade(wide, trade(), "S").comm == pytest.approx(0.65 * 4 / 100)


def test_correlations_read_with_opposite_signs_for_the_mirror():
    rng = random.Random(3)
    x = [rng.random() for _ in range(90)]
    y = [a + rng.gauss(0, 0.5) for a in x]
    neg = [-v for v in y]
    assert FD.spearman(x, neg) == pytest.approx(-FD.spearman(x, y))
    assert FD.tercile_contrast(x, neg) == pytest.approx(-FD.tercile_contrast(x, y))


def test_strict_touch_has_no_latest_fallback_on_a_wide_quote():
    wide = row(0.5, 6.0, latest=3.0)
    assert V.SIM._is_junk_quote(wide)
    assert V.strict_touch(wide, sold=True) == 0.5
    assert V.strict_touch(wide, sold=False) == 6.0
    assert V.strict_touch(row(0, 1.2, latest=0.9), sold=True) == 0.0
    assert V.strict_touch({"Bid": None, "Ask": None}, sold=False) is None
    assert V.strict_touch(None, sold=True) == 0.0


def test_touch_prints_per_side_and_costs_more_than_mid():
    p = V.run_trade(four_leg_chain(), trade(), "RC")
    for side in ("back", "front"):
        assert p.touch[side] < V.side_sign(side) * p.gross - p.comm
    assert p.touch["back"] != pytest.approx(-p.touch["front"])
    assert p.touch_net("back") == pytest.approx(p.touch["back"] / SPOT)


def test_front_side_aware_print_sells_a_wide_leg_at_its_bid_and_leaves_y_alone():
    p = V.run_trade(four_leg_chain(wc=(0.5, 6.0, 2.0, 2.2)), trade(), "RC")
    # Front: buy 1 ATM at mid 5.1, sell 2 wings at the 0.5 bid, not the 3.25 mid.
    assert p.front_aware == pytest.approx((7.1 - 5.1) - 2 * (2.1 - 0.5) - p.comm)
    assert p.tags[V.SIM.CLOSE_MID_WIDE_TAG] == 1
    assert p.entry[("Call", 460.0)] == pytest.approx(3.25)
    assert V.run_trade(four_leg_chain(), trade(), "S").front_aware is None


# ── one clock, fixed exit ───────────────────────────────────────────────────

def test_every_leg_fills_at_the_fill_days_closing_mid():
    ch = four_leg_chain()
    p = V.run_trade(ch, trade(), "S")
    assert p.entry == {("Call", 450.0): pytest.approx(5.1), ("Put", 450.0): pytest.approx(4.1)}
    assert p.tr.fill > p.tr.signal


def test_a_leg_with_no_fill_row_drops_and_never_moves_the_entry():
    ch = four_leg_chain()
    series, det = ch._memo[("QQQ", EXPIRY, 460.0, "Call")]
    det.pop(FILL)
    assert V.run_trade(ch, trade(), "RC") == "no_entry_quote"
    # The other structures on the same day still price.
    assert isinstance(V.run_trade(ch, trade(), "S"), V.Priced)


def test_a_bought_side_no_bid_quote_is_refused():
    ch = four_leg_chain(wc=(0.0, 1.2, 2.0, 2.2))
    assert V.run_trade(ch, trade(), "RC") == V.SIM.JUNK_ENTRY_REFUSAL


def test_a_missing_or_carried_exit_quote_drops_the_row():
    ch = four_leg_chain()
    ch._memo[("QQQ", EXPIRY, 460.0, "Call")][1].pop(EXIT_T7)
    assert V.run_trade(ch, trade(), "RC") == "no_exit_quote"
    junk = four_leg_chain(wc=(1.0, 1.2, 0.4, 6.0))     # a junk exit quote that did not trade
    junk._memo[("QQQ", EXPIRY, 460.0, "Call")][1][EXIT_T7]["Latest"] = 0.0
    assert V.run_trade(junk, trade(), "RC") == "stale_exit_mark"


def test_a_priced_against_strike_order_entry_is_refused():
    ch = four_leg_chain(ac=(1.0, 1.2, 7.0, 7.2), wc=(5.0, 5.2, 2.0, 2.2))
    assert V.run_trade(ch, trade(), "RC") == V.SIM.NON_MONOTONIC_REFUSAL


def test_a_credit_entry_runs_the_fixed_exit_and_never_the_credit_route(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the production simulator was called")
    monkeypatch.setattr(V.SIM, "_simulate", boom)
    monkeypatch.setattr(V.SIM, "_exit_basis", boom, raising=False)
    # Back call ratio: sell 5.1, buy 2 x 1.1, a net credit of 2.9.
    p = V.run_trade(four_leg_chain(), trade(), "RC")
    assert p.debit == pytest.approx(-5.1 + 2 * 1.1)
    assert p.debit < 0
    # Closed at the exit day's marks: ATM 5.1 -> 7.1 costs 2.0; wings gain 2 x 1.0.
    assert p.gross == pytest.approx(-(7.1 - 5.1) + 2 * (2.1 - 1.1))


def test_risk_is_defined_except_on_the_front_call_ratio():
    assert V.risk_points("S", "long", 450, None, 9.2) == 9.2
    assert V.risk_points("RC", "back", 450, 460, -2.9) == pytest.approx(10 - 2.9)
    assert V.risk_points("RP", "back", 450, 440, -1.0) == pytest.approx(9.0)
    assert V.risk_points("RC", "front", 450, 460, -2.9) is None
    assert V.risk_points("RP", "front", 450, 440, -1.0) == pytest.approx(2 * 440 - 450 + 1.0)
    p = V.run_trade(four_leg_chain(), trade(), "RC")
    assert p.r("front") is None
    assert p.r("back") is not None


# ── expiries and the strike walk ────────────────────────────────────────────

def test_t30_is_the_monthly_nearest_30_with_21_days_at_fill():
    s = set(weekdays(date(2024, 1, 1), date(2024, 12, 31)))
    last = date(2024, 12, 31)
    assert V.pick_expiry(V.T30, date(2024, 6, 4), s, last) == date(2024, 7, 19)   # 45 v 10 DTE
    assert V.pick_expiry(V.T30, date(2024, 6, 21), s, last) == date(2024, 7, 19)  # 28 DTE
    e = V.pick_expiry(V.T30, date(2024, 6, 28), s, last)
    assert (e - date(2024, 6, 28)).days >= 21


def test_t7_is_the_friday_nearest_7_with_5_days_at_fill_and_holiday_moves():
    s = set(weekdays(date(2024, 1, 1), date(2024, 12, 31)))
    last = date(2024, 12, 31)
    assert V.pick_expiry(V.T7, date(2024, 6, 7), s, last) == date(2024, 6, 14)    # Friday: 7
    assert V.pick_expiry(V.T7, date(2024, 6, 3), s, last) == date(2024, 6, 14)    # Monday: 11, not 4
    assert V.pick_expiry(V.T7, date(2024, 6, 6), s, last) == date(2024, 6, 14)    # Thursday: 8
    s.discard(date(2024, 6, 14))
    assert V.pick_expiry(V.T7, date(2024, 6, 7), s, last) == date(2024, 6, 13)    # holiday Thursday


def test_walk_needs_both_types_and_names_what_is_missing():
    e = EXPIRY
    ch = chain_of({("Call", e, 450.0): {D: row(1, 2)}})
    s = V.walk_strike(ch, set(), "QQQ", e, 450.0, 5.0, D, ("Call", "Put"))
    assert s.status == "await" and s.fetch == (("Put", e, 450.0),)
    both = chain_of({("Call", e, 450.0): {D: row(1, 2)}, ("Put", e, 450.0): {D: row(1, 2)}})
    assert V.walk_strike(both, set(), "QQQ", e, 451.0, 5.0, D, ("Call", "Put")).strike == 450.0


def test_walk_steps_past_evidence():
    e = EXPIRY
    stem = NTF.contract_stem("QQQ", e, 450.0, "Call")
    s = V.walk_strike(chain_of({}), {stem}, "QQQ", e, 450.0, 5.0, D, ("Call",))
    assert s.status == "await" and s.strike == 445.0     # 445 and 455 tie: lower first


def test_a_later_skip_list_entry_cannot_move_a_strike_with_real_rows():
    e = EXPIRY
    stem = NTF.contract_stem("QQQ", e, 450.0, "Call")
    ch = chain_of({("Call", e, 450.0): {D: row(1, 2)}})
    s = V.walk_strike(ch, {stem}, "QQQ", e, 450.0, 5.0, D, ("Call",))
    assert s.status == "built" and s.strike == 450.0
    # With no row by D the skip-list still steps past it.
    before = D - timedelta(days=9)
    assert V.walk_strike(ch, {stem}, "QQQ", e, 450.0, 5.0, before, ("Call",)).strike == 445.0
    assert V.DEPTH_TRUST == date(2026, 9, 9)


def test_a_cached_finer_strike_never_moves_the_walk():
    """The step is fixed, so a later fetch by any study cannot change a strike."""
    e = EXPIRY
    rows = {D: row(1, 2)}
    sparse = chain_of({("Call", e, 450.0): rows})
    denser = chain_of({("Call", e, k): rows for k in (450.0, 451.0, 451.5, 452.0, 452.5)})
    for ch in (sparse, denser):
        assert V.walk_strike(ch, set(), "QQQ", e, 451.9, 5.0, D, ("Call",)).strike == 450.0
    assert V.STEP == {("QQQ", "T30"): 1.0, ("QQQ", "T7"): 1.0,
                      ("SMH", "T30"): 2.5, ("SMH", "T7"): 2.5}


def test_a_shallow_file_is_refetched_and_a_trusted_one_is_stepped_past(monkeypatch):
    e = EXPIRY
    late = chain_of({("Call", e, 450.0): {D + timedelta(days=30): row(1, 2)}})
    monkeypatch.setattr(V, "file_fetched_on", lambda *a: date(2026, 8, 1))
    s = V.walk_strike(late, set(), "QQQ", e, 450.0, 5.0, D, ("Call",))
    assert s.status == "await" and s.reason == "shallow_refetch"
    assert s.refetch == (("Call", e, 450.0),)
    monkeypatch.setattr(V, "file_fetched_on", lambda *a: V.DEPTH_TRUST)
    s = V.walk_strike(late, set(), "QQQ", e, 450.0, 5.0, D, ("Call",))
    assert s.strike == 445.0 and s.reason == "strike_not_cached" and s.refetch == ()


def test_fetch_targets_carry_a_refetch_date_past_historys_tolerance(monkeypatch):
    monkeypatch.setattr(V, "file_fetched_on", lambda *a: date(2026, 8, 1))
    book = gated_book()
    d = book.signals()[0]
    tr = V.Trade("QQQ", V.T7, d, d, d, "await", "shallow_refetch",
                 fetch=(("Call", EXPIRY, 450.0), ("Put", EXPIRY, 450.0)),
                 refetch=(("Call", EXPIRY, 450.0),))
    for tk in V.TICKERS:
        for t in V.TENORS:
            for x in book.signals():
                book._tr[(tk, t.name, x)] = V.Trade(tk, t, x, x, x, "drop", "x")
    book._tr[("QQQ", "T7", d)] = tr
    got = {t["opt_type"]: t for t in V.fetch_targets(book)}
    assert got["Put"]["needed"] is None
    assert got["Call"]["needed"] == d - timedelta(days=6)
    assert (d - got["Call"]["needed"]).days > 5


def test_walk_matches_the_selloff_walk_on_one_type_on_a_cached_grid(monkeypatch):
    monkeypatch.setattr(V, "file_fetched_on", lambda *a: V.DEPTH_TRUST)
    e = date(2024, 7, 19)
    rows = {D: row(1, 2)}
    spy = chain_of({("Put", e, 400.0): rows, ("Put", e, 405.0): rows}, ticker="SPY")
    for target in (401.0, 404.0, 412.0, 395.0):
        ours = V.walk_strike(spy, set(), "SPY", e, target, 5.0, D, ("Put",))
        theirs = SPD.nearest_listed(spy, set(), e, target, 400.0, D, "Put")
        assert (ours.status, ours.strike) == (theirs.status, theirs.strike)


def test_an_unlisted_expiry_needs_a_weekly_and_near_atm_strikes():
    weekly = date(2024, 6, 7)
    monthly = date(2024, 7, 19)
    near = {NTF.contract_stem("QQQ", weekly, k, "Call") for k in (448.0, 450.0, 452.0)}
    far = {NTF.contract_stem("QQQ", weekly, k, "Call") for k in (300.0, 310.0, 320.0)}
    assert V.Listing(chain_of({}), near).state("QQQ", weekly, D, 450.0) == "no"
    assert V.Listing(chain_of({}), far).state("QQQ", weekly, D, 450.0) == "unknown"
    # Two types of one strike are one strike.
    two = {NTF.contract_stem("QQQ", weekly, 450.0, o) for o in ("Call", "Put")}
    assert V.Listing(chain_of({}), two).state("QQQ", weekly, D, 450.0) == "unknown"
    # A monthly is never proven unlisted: a missing strike is not a missing expiry.
    mstems = {NTF.contract_stem("QQQ", monthly, k, "Call") for k in (452.0, 453.0, 454.0)}
    assert V.Listing(chain_of({}), mstems).state("QQQ", monthly, D, 450.0) == "unknown"


def test_a_sparse_cache_never_proves_an_expiry_unlisted():
    e = date(2024, 6, 7)
    shallow = chain_of({("Call", e, k): {D + timedelta(days=3): row(1, 2)}
                        for k in (440.0, 445.0, 450.0, 455.0)})
    assert V.Listing(shallow, set()).state("QQQ", e, D, 450.0) == "unknown"
    live = chain_of({("Call", e, 450.0): {D - timedelta(days=5): row(1, 2)}})
    assert V.Listing(live, set()).state("QQQ", e, D, 450.0) == "yes"


def test_select_trade_reads_only_the_signal_days_close():
    sessions = weekdays(date(2024, 5, 1), date(2024, 7, 31))
    index = {d: i for i, d in enumerate(sessions)}
    bars = {d: Bar(c=SPOT if d <= D else 9999.0) for d in sessions}
    ch = chain_of({})
    tr = V.select_trade(ch, set(), V.Listing(ch, set()), "QQQ", V.T7, D, sessions, index, bars)
    assert tr.status == "await" and tr.spot == SPOT and tr.fill == FILL
    # QQQ T7: step $1, wings 2.5% out, ties to the lower strike.
    assert {k for _o, _e, k in tr.fetch} == {450.0, 461.0, 439.0}
    assert tr.exit == sessions[index[FILL] + 2]


def test_a_date_past_the_ohlc_awaits_rather_than_drops():
    sessions = weekdays(date(2024, 5, 1), date(2024, 7, 31))
    index = {d: i for i, d in enumerate(sessions)}
    bars = {d: Bar(c=SPOT) for d in sessions if d < D}
    ch = chain_of({})
    tr = V.select_trade(ch, set(), V.Listing(ch, set()), "QQQ", V.T7, D, sessions, index, bars)
    assert tr.status == "await" and tr.reason == "no_ohlc_bar" and tr.fetch == ()


# ── features: dated before the fill ─────────────────────────────────────────

def make_bars(n: int = 80) -> list[Bar]:
    rng = random.Random(9)
    out, c = [], 100.0
    for _ in range(n):
        o = c
        c = c * (1 + rng.gauss(0, 0.01))
        out.append(Bar(c=c, o=o, h=max(o, c) + 0.5, l=min(o, c) - 0.5, v=1000 + rng.random() * 100))
    return out


def test_price_features_only_read_bars_through_d():
    bars = make_bars()
    upto = bars[:60]
    f = V.price_features(upto)
    assert f["ret1"] == pytest.approx(bars[59].c / bars[58].c - 1)
    assert f["ret20"] == pytest.approx(bars[59].c / bars[39].c - 1)
    assert f["dist50"] == pytest.approx(bars[59].c / (sum(b.c for b in bars[10:60]) / 50) - 1)
    assert f["und_vol"] == pytest.approx(bars[59].v / (sum(b.v for b in bars[39:59]) / 20))
    assert all(f[k] is not None for k in f)
    # The function is given no later bar, so a later bar cannot move it.
    poisoned = upto + [Bar(c=1e9, o=1e9, h=1e9, l=1e9, v=1e12)]
    assert V.price_features(poisoned[:60]) == f


def test_features_are_dated_before_the_fill_and_option_features_read_d():
    sessions = weekdays(date(2024, 1, 1), date(2024, 3, 29))
    iv = {d: 20.0 + i for i, d in enumerate(sessions)}
    vol = {d: 100.0 for d in sessions}
    i = 30
    d, fill = sessions[i], sessions[i + 1]
    assert d < fill
    f = V.option_features(iv, vol, sessions, i, rv20=15.0)
    assert f["iv_rv20"] == pytest.approx(iv[d] - 15.0)
    assert f["iv_chg5"] == pytest.approx(5.0)
    assert f["opt_vol"] == pytest.approx(1.0)
    # A changed fill-day figure cannot reach D's features.
    assert V.option_features({**iv, fill: 1e6}, {**vol, fill: 1e9}, sessions, i, 15.0) == f
    assert V.option_features(iv, vol, sessions, 3, 15.0)["iv_chg5"] is None
    thin = {s: 100.0 for s in sessions[i - 10:i + 1]}
    assert V.option_features(iv, thin, sessions, i, 15.0)["opt_vol"] is None


def test_option_rows_are_read_on_the_signal_day_past_the_gate():
    ch = four_leg_chain()
    ch._memo[("QQQ", EXPIRY, 450.0, "Call")][1][D]["IV"] = 33.0
    ch._memo[("QQQ", EXPIRY, 450.0, "Call")][1][FILL]["IV"] = 77.0
    book = gated_book(ch)
    book._open = True
    assert book.option_row(trade(), "Call")["IV"] == 33.0


# ── tokens and the lag ──────────────────────────────────────────────────────

@pytest.mark.parametrize("raw", ["spot ~ 725", "Below 400 - weak", "PxVec +0.9", "nan", "",
                                 None, "Rich IV"])
def test_non_standard_first_words_read_as_missing(raw):
    t = V.parse_tokens(raw)
    assert t["dir"] is None and t["vol"] is None and t["risk"] is None


def test_tokens_parse_the_standard_form_only_in_the_head():
    t = V.parse_tokens("BULL + L-VOL + RISK-OFF + HP — but BEAR E-VOL RISK-ON appear later")
    assert t == {"dir": 1, "vol": 1, "risk": 0, "hp": 1}
    e = V.parse_tokens("E-VOL")
    assert e["dir"] is None and e["vol"] == 3
    assert V.parse_tokens("BEAR + H-VOL")["dir"] == -1
    assert V.parse_tokens("RANGE→BEAR")["dir"] is not None


def test_hedge_pressure_forms_and_flow_count():
    assert V.hp_score("[FLOW] hedge-pressure 64/100 with indexes") == 64
    assert V.hp_score("Hedge pressure is only 31/100") == 31
    assert V.hp_score("Hedge-pressure score 46 (band)") == 46
    assert V.hp_score("extrinsic (hedge pressure 53)") == 53
    assert V.hp_score("at 21/100 hedge pressure it is") == 21
    assert V.hp_score("classic hedge pressure, protection") is None
    assert V.hp_score("hedge pressure 340/100") is None
    assert V.hp_score(None) is None
    assert V.flow_count("[FLOW] a\n[FLOW] b\n[VEGA] c") == 2
    assert V.flow_count("") is None and V.flow_count("nan") is None


def test_the_lag_bin_is_market_reads_own_function():
    assert V.lag_bin is MR.lag_bin
    assert V.lag_bin("2026-08-12 01:00:00", "2026-08-11") == "LIVE"
    assert V.lag_bin("2026-08-20", "2026-08-11") == "RETRO"


def test_analysis_comes_through_the_era_gate_and_seal(tmp_path, monkeypatch):
    p = tmp_path / "a.csv"
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, ["date", "ticker", "regime", "signal", "created_datetime"])
        w.writeheader()
        for d, tk in (("2026-09-22", "MARKET"), ("2026-09-23", "MARKET"), ("2026-09-22", "SPY")):
            w.writerow(dict(date=d, ticker=tk, regime="BULL + L-VOL", signal="[FLOW] x",
                            created_datetime="2026-09-23 01:00:00"))
    monkeypatch.setattr(V.era_mod, "resolve_paths", lambda e=None: {"analysis": p})
    monkeypatch.setattr(V.era_mod, "enforce", lambda e, paths: "v4")
    monkeypatch.setattr(V.era_mod, "SEAL_LIFTED", None)
    index, census = V.load_analysis()
    assert ("MARKET", "2026-09-22") in index
    assert ("MARKET", "2026-09-23") not in index
    assert ("SPY", "2026-09-22") not in index
    assert index[("MARKET", "2026-09-22")]["lag"] == "LIVE"
    assert census["era"] == "v4" and "SEAL" in census["seal"]
    monkeypatch.setattr(V.era_mod, "enforce", lambda e, paths: "v3")
    with pytest.raises(SystemExit) as exc:
        V.load_analysis()
    assert exc.value.code == era.EXIT_ERA_MISMATCH


def test_baseline_columns_and_qqq_prem_is_a_ratio_to_its_prior_mean(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text("date,qqq_call_prem,qqq_put_prem\n2024-03-15,60,40\n2024-03-18,,40\n"
                 "2024-03-19,10,0\n")
    b = V.load_baseline(p)
    assert b["2024-03-15"] == {"qqq_total": 100.0, "qqq_cp": 1.5}
    assert b["2024-03-18"] == {"qqq_total": None, "qqq_cp": None}
    assert b["2024-03-19"]["qqq_cp"] is None
    sessions = weekdays(date(2024, 1, 1), date(2024, 3, 29))
    base = {d.isoformat(): {"qqq_total": 100.0, "qqq_cp": 1.0} for d in sessions}
    base[sessions[30].isoformat()] = {"qqq_total": 250.0, "qqq_cp": 2.0}
    base[sessions[31].isoformat()] = {"qqq_total": 1e9, "qqq_cp": 2.0}      # after D: unread
    f = V.baseline_features(base, sessions, 30)
    assert f == {"qqq_prem": 2.5, "qqq_cp": 2.0}
    assert V.baseline_features(base, sessions, 19)["qqq_prem"] is None
    thin = {d.isoformat(): {"qqq_total": 100.0, "qqq_cp": 1.0} for d in sessions[20:]}
    assert V.baseline_features(thin, sessions, 30)["qqq_prem"] is None


def test_the_frozen_evol_label_covers_the_window_when_the_table_is_present():
    if not V.VIX_TABLE.exists():
        pytest.skip("no session table on this checkout")
    lab = V.MechLabeler.from_csv(V.VIX_TABLE)
    for d in ("2024-03-15", "2025-04-07", "2026-09-22"):
        _dir, vol, ok, mapped = lab.label(d)
        assert ok and mapped == d and vol in ("L-VOL", "H-VOL", "E-VOL")


# ── the bootstrap fits ──────────────────────────────────────────────────────

def test_block_bootstrap_fits_a_mean_and_a_tercile_difference():
    rng = random.Random(5)
    x = [rng.random() for _ in range(120)]
    y = [rng.gauss(0.01, 0.02) for _ in x]
    b = FD.block_bootstrap(x, y, V.mean_stat, V.BLOCK, 300, 1)
    assert b.point == pytest.approx(sum(y) / len(y))
    assert b.lo < b.point < b.hi
    t = FD.block_bootstrap(x, y, FD.tercile_contrast, V.BLOCK, 300, 1)
    assert t.lo < t.point < t.hi
    assert V.mean_stat(None, [None, 1.0, 3.0]) == 2.0


def test_mean_boot_uses_block_bootstraps_own_resampling():
    rng = random.Random(8)
    v = [rng.gauss(0.01, 0.02) for _ in range(100)]
    b = FD.block_bootstrap(v, v, V.mean_stat, V.BLOCK, 200, V.SEED)
    point, p = V.mean_boot(v, 200, V.SEED)
    assert point == pytest.approx(b.point)
    assert 0 < p <= 1


def persistent_null(rng: np.random.Generator, n: int = 370) -> tuple[list, list]:
    """The reader's worst case: a half-life-40 feature against a 5-day overlapping
    outcome with fat tails, vol clustering and a slow component. x and y are independent."""
    def ar(m: int, half_life: int) -> np.ndarray:
        phi = 0.5 ** (1 / half_life)
        e = rng.standard_normal(m + 200)
        out = np.zeros(m + 200)
        for i in range(1, m + 200):
            out[i] = phi * out[i - 1] + e[i]
        return out[200:]
    m = n + 205
    level = ar(m, 20)
    r = rng.standard_t(4, m) * np.exp(0.5 * level / level.std())
    y = np.convolve(r, np.ones(5) / 5, "valid")[200:200 + n]
    slow = ar(n, 40)
    y = y / y.std() * math.sqrt(0.8) + slow / slow.std() * math.sqrt(0.2)
    return ar(n, 40).tolist(), y.tolist()


def test_the_circular_shift_null_is_calibrated_on_a_persistent_feature():
    """The block-bootstrap p this replaced read p<.05 on about a quarter of these runs
    and p<.001 on about 6%. A rotation keeps each series' own structure."""
    rng = np.random.default_rng(20261106)
    ps = []
    for i in range(150):
        x, y = persistent_null(rng)
        ps.append(V.shift_p(x, y, FD.spearman, draws=100, seed=i)[1])
    assert sum(p < 0.05 for p in ps) / len(ps) <= 0.11
    assert sum(p < 0.001 for p in ps) / len(ps) <= 0.0134


def test_shift_p_finds_a_real_relation_and_goes_through_the_lib_helper(monkeypatch):
    rng = random.Random(1)
    x = [rng.gauss(0, 1) for _ in range(300)]
    y = [a + rng.gauss(0, 1) for a in x]
    calls = []
    real = FD.circular_shift_null

    def spy(*a, **k):
        calls.append(a[3])
        return real(*a, **k)
    monkeypatch.setattr(V.FD, "circular_shift_null", spy)
    point, p = V.shift_p(x, y, FD.spearman, draws=100)
    assert calls == [21] and point > 0.4 and p < 1e-6
    assert V.shift_p(x[:30], y[:30], FD.spearman, draws=10)[1] != V.shift_p(
        x[:30], y[:30], FD.spearman, draws=10)[1]            # too short: NaN


def test_shift_p_uses_the_point_over_the_sd_and_never_centres(monkeypatch):
    values = (0.4, 0.5, 0.6, 0.5, 0.4, 0.6)            # far off centre
    sd = statistics.stdev(values)

    def fake(x, y, stat, min_shift, draws, seed):
        return FD.ShiftNull(point=0.5, p05=0.4, p95=0.6, draws=6, min_shift=21, seed=1,
                            values=values)
    monkeypatch.setattr(V.FD, "circular_shift_null", fake)
    point, p = V.shift_p(list(range(60)), list(range(60)), FD.spearman)
    assert point == 0.5
    assert p == pytest.approx(math.erfc(0.5 / sd / math.sqrt(2)))
    assert p < 0.05                                    # centred it would read p near 1


def test_a_discrete_feature_reads_levels_not_positional_terciles():
    x = [0.0] * 30 + [1.0] * 30
    y = [1.0] * 15 + [0.0] * 15 + [3.0] * 30
    f = V.FEATURE_BY_NAME["evol"]
    assert V.cut_stat(*V.frozen_cuts(f, x))(x, y) == pytest.approx(3.0 - 0.5)
    # The rank tercile splits the tied zeros by position, so it reads another number.
    assert FD.tercile_contrast(x, y) != pytest.approx(3.0 - 0.5)
    assert math.isnan(V.cut_stat(0, 1)([0.0, 0.0], [1.0, 2.0]))


def test_frozen_cuts_come_from_discovery_rows_and_later_rows_cannot_move_them():
    ds = dataset()
    cell = ("QQQ", "T30", "S", "ret1")
    before = V.cell_cuts(ds, cell)
    for r in ds.rows[cell[:3]]:
        if not V.in_discovery(r):
            ds.features[cell[:2]][r["date"]]["ret1"] *= 1000.0
    assert V.cell_cuts(ds, cell) == before
    assert V.frozen_cuts(V.FEATURE_BY_NAME["ret1"], [1.0, 1.0, 1.0, 1.0]) is None
    assert V.frozen_cuts(V.FEATURE_BY_NAME["evol"], []) == (0, 1)


def test_power_floors():
    x = [float((i * 37) % 126) for i in range(126)]
    cuts = V.tercile_cuts(x)
    assert V.floors_met(x, list(range(126)), cuts)
    assert not V.floors_met(x[:59], list(range(59)), cuts)
    assert not V.floors_met(x, list(range(126)), None)
    # 60 rows inside two calendar blocks: the LIVE shape.
    assert not V.floors_met(x[:60], [0] * 30 + [21] * 30, cuts)
    # Terciles that sit in one stretch of time fail the arm's block floor.
    ramp = [float(i) for i in range(126)]
    assert not V.floors_met(ramp, list(range(126)), V.tercile_cuts(ramp))
    # A thin arm fails even with enough rows.
    assert not V.floors_met([0.0] * 120 + [1.0] * 6, list(range(126)), (0, 1))


# ── discovery never reads confirmation dates ────────────────────────────────

def dataset(n_days: int = 500, seed: int = 1) -> V.Dataset:
    """Every series on one synthetic book; a real relation on `ret1`."""
    rng = random.Random(seed)
    days = [d for d in weekdays(date(2024, 3, 15), date(2026, 9, 22))][:n_days]
    rows, feats = {}, {}
    for tk in V.TICKERS:
        for t in V.TENORS:
            fm = {}
            for d in days:
                fm[d.isoformat()] = {f.name: None for f in V.FEATURES}
                fm[d.isoformat()]["ret1"] = rng.gauss(0, 1)
                fm[d.isoformat()]["evol"] = float(rng.random() < 0.3)
            feats[(tk, t.name)] = fm
            for s in V.STRUCTURES:
                out = []
                for i, d in enumerate(days):
                    y = 0.002 * fm[d.isoformat()]["ret1"] + rng.gauss(0, 0.002)
                    out.append(dict(d=d, date=d.isoformat(), exit=d + timedelta(days=7), si=i, y=y,
                                    net={sd: V.side_sign(sd) * y - 1e-5 for sd in V.SIDES[s]},
                                    touch={sd: V.side_sign(sd) * y - 1e-3 for sd in V.SIDES[s]},
                                    r={sd: None for sd in V.SIDES[s]}, debit=1.0, expiry=d,
                                    dte=21 + i % 33, wd=d.weekday(), held=7, wide=False,
                                    atm_d=0.0, atm_fill=0.0, front_aware=None,
                                    atm=1.0, wing=None))
                rows[(tk, t.name, s)] = out
    return V.Dataset(rows, feats, {}, {})


def test_first_confirmation_date_is_the_60_percent_cut_of_the_window():
    assert V.split_index(632) == 379
    assert V.split_index(100) == 60
    if not V.VIX_TABLE.exists():
        pytest.skip("no session table on this checkout")
    sessions = V.MBL.load_closes()
    window = [d for d in sorted(sessions) if V.WINDOW[0] <= d <= V.WINDOW[1]]
    assert window[V.split_index(len(window))] == V.FIRST_CONFIRM


def test_a_trade_that_closes_after_the_cut_leaves_discovery():
    a = dict(d=date(2025, 9, 18), exit=date(2025, 9, 25))
    b = dict(d=date(2025, 9, 10), exit=date(2025, 9, 18))
    assert not V.in_discovery(a) and V.in_discovery(b)
    assert not V.in_confirmation(a) and V.in_confirmation(dict(d=V.FIRST_CONFIRM, exit=a["exit"]))


def test_discovery_never_reads_a_confirmation_date():
    ds = dataset()
    base = V.discover(ds, draws=30)
    assert V.ranked(base)
    for key, rows in ds.rows.items():
        for r in rows:
            if not V.in_discovery(r):
                r["y"] = float("nan")          # a read would poison every statistic
                r["net"] = None
                ds.features[key[:2]][r["date"]]["ret1"] = None
                ds.features[key[:2]][r["date"]]["evol"] = None
    after = V.discover(ds, draws=30)
    assert [repr((c.cell, c.rho, c.p, c.q)) for c in after] == [
        repr((c.cell, c.rho, c.p, c.q)) for c in base]


def test_no_analysis_cell_enters_discovery():
    disc = V.discover(dataset(n_days=200), draws=5)
    assert len(disc) == 144
    assert not [c for c in disc if V.FEATURE_BY_NAME[c.cell[3]].is_analysis]


def test_ranked_takes_gradable_cells_at_q_10_percent():
    cell = ("QQQ", "T30", "S", "ret1")
    c = lambda g, q: V.DiscCell(cell, 100, g, 0.3, 0.01, 0.01, q)  # noqa: E731
    assert len(V.ranked([c(True, 0.05), c(True, 0.2), c(False, 0.01), c(True, float("nan"))])) == 1


# ── verdict words ───────────────────────────────────────────────────────────

def test_confirm_token_truth_table():
    tok = V.confirm_token
    good = dict(floors=True, exit_ok=True, tradable=True, cycle=True)
    assert tok(1, 0.1, 0.05, **good) == V.CANDIDATE
    assert tok(1, -0.1, 0.05, **good) == V.CONTRARY
    assert tok(1, 0.1, 0.2, **good) == V.NULL
    assert tok(1, 0.1, float("nan"), **good) == V.NULL
    assert tok(1, 0.1, 0.05, **{**good, "floors": False}) == V.UNDERPOWERED
    assert tok(1, float("nan"), 0.05, **good) == V.UNDERPOWERED
    # Exit drops over the limit outrank everything else.
    assert tok(1, 0.1, 0.05, **{**good, "exit_ok": False}) == V.UNDERPOWERED
    # A cell whose favourable arm loses cannot be a CANDIDATE.
    assert tok(1, 0.1, 0.05, **{**good, "tradable": False}) == V.NULL
    assert tok(1, 0.1, 0.05, **{**good, "cycle": False}) == V.NULL
    assert tok(1, 0.1, 0.05, **{**good, "cycle": None}) == V.UNDERPOWERED
    # A lone ranked cell's q is its p: confirmation is at .05, not discovery's .10.
    assert tok(1, 0.1, 0.08, **good) == V.NULL


def arm_pairs(top_y, bot_y):
    def r(y):
        return dict(y=y, net=dict(long=y - 0.001, back=y - 0.001, front=-y - 0.001),
                    touch=dict(long=y - 0.01, back=y - 0.01, front=-y - 0.01))
    return [(1.0, r(y)) for y in top_y] + [(0.0, r(y)) for y in bot_y] + [(0.5, r(9.0))]


def test_arm_table_prints_top_bottom_all_at_mid_and_touch():
    t = V.arm_table(arm_pairs([0.01, 0.03], [0.05]), (0, 1), "long")
    assert t["top"][0] == 2 and t["top"][1] == pytest.approx(0.019)
    assert t["bottom"] == (1, pytest.approx(0.049), pytest.approx(0.04))
    assert t["all"][0] == 4


def noisy_pairs(top_mean, bot_mean, n=60, sd=0.01, seed=3):
    rng = random.Random(seed)

    def r(m):
        y = m + rng.gauss(0, sd)
        return dict(y=y, net=dict(long=y - 1e-4, back=y - 1e-4, front=-y - 1e-4),
                    touch=dict(long=y - 1e-3, back=y - 1e-3, front=-y - 1e-3))
    return [(1.0, r(top_mean)) for _ in range(n)] + [(0.0, r(bot_mean)) for _ in range(n)]


def test_a_position_must_clear_zero_for_straddles_and_ratios_alike():
    strong = noisy_pairs(0.02, -0.001)
    pos = V.best_position(strong, (0, 1), "S", 1, n_boot=300)
    assert pos["arm"] == "top" and pos["side"] == "long" and pos["ok"]
    assert pos["touch"] == pytest.approx(pos["mean"] + 1e-4 - 1e-3)
    assert not V.best_position(noisy_pairs(-0.01, -0.05), (0, 1), "S", 1, n_boot=300)["ok"]
    assert V.best_position(noisy_pairs(-0.05, 0.02), (0, 1), "S", -1, n_boot=300)["arm"] == "bottom"
    assert V.best_position(strong, (0, 1), "S", 0) is None
    # A ratio takes the position with the larger net mean: here, front in the low arm.
    pos = V.best_position(noisy_pairs(0.001, -0.02), (0, 1), "RC", 1, n_boot=300)
    assert (pos["arm"], pos["side"]) == ("bottom", "front") and pos["ok"]


def test_a_confirmed_ratio_contrast_with_an_arm_mean_near_zero_fails():
    """At mid front = -back, so one of the two positions always looks positive. The
    arms differ by more than commission here and neither mean is distinguishable from 0."""
    pairs = noisy_pairs(0.0005, -0.0005, n=90, sd=0.03, seed=5)
    point = V.cut_stat(0, 1)([x for x, _ in pairs], [r["y"] for _, r in pairs])
    sign = V._sign(point)
    pos = V.best_position(pairs, (0, 1), "RC", sign, n_boot=300)
    assert pos["mean"] > 0                              # the old clause passed here
    assert not pos["ok"]
    assert V.confirm_token(sign, point, 0.01, True, True, V.position_clears(pos), True) == V.NULL


def test_dte_buckets_are_fixed_and_t7_reads_the_weekday():
    assert V.DTE_BUCKETS == ((21, 30), (31, 38), (39, 53))
    assert [V.dte_bucket(d) for d in (21, 30, 31, 38, 39, 53, 54, 20)] == [
        0, 0, 1, 1, 2, 2, None, None]
    assert V.cycle_bucket("T30", dict(dte=35, wd=2)) == 1
    assert V.cycle_bucket("T7", dict(dte=9, wd=2)) == 2


def test_the_cycle_clause_reads_the_weighted_average_against_half_the_overall():
    pairs = []
    for dte, top, bot in ((25, 0.04, 0.0), (35, -0.01, 0.0), (45, 0.03, 0.0)):
        pairs += [(1.0, dict(y=top, dte=dte, wd=0)) for _ in range(6)]
        pairs += [(0.0, dict(y=bot, dte=dte, wd=0)) for _ in range(6)]
    c = V.bucket_contrasts(pairs, (0, 1), "T30")
    assert set(c) == {0, 1, 2} and c[1] == (pytest.approx(-0.01), 12)
    # One bucket flips, and the average still holds: the old every-bucket rule failed here.
    assert V.cycle_clause(c, 1, 0.02) is True
    # The overall contrast dwarfs the buckets': the cycle is what makes it.
    assert V.cycle_clause(c, 1, 0.05) is False
    assert V.cycle_clause(c, -1, 0.02) is False
    assert V.cycle_clause({0: (0.1, 10)}, 1, 0.1) is None
    thin = [(1.0, dict(y=1.0, dte=25, wd=0))] * 4 + [(0.0, dict(y=0.0, dte=25, wd=0))] * 6
    assert V.bucket_contrasts(thin, (0, 1), "T30") == {}


def test_exit_drop_limit_applies_to_the_series_and_each_arm():
    ds = dataset(n_days=100)
    key = ("QQQ", "T30", "S")
    tn = key[:2]
    rows = ds.rows[key]
    ds.exit_drops[key] = [dict(d=r["d"], date=r["date"], exit=r["exit"]) for r in rows[:5]]
    assert V.exit_share(ds, key) == pytest.approx(5 / 105)
    assert V.exit_limit_ok(0.05, {"top": 0.05, "bottom": 0.0})
    assert not V.exit_limit_ok(0.051, {"top": 0.0})
    assert not V.exit_limit_ok(0.01, {"top": 0.06, "bottom": 0.0})
    for r in rows:
        ds.features[tn][r["date"]]["evol"] = 1.0 if r in rows[:10] else 0.0
    shares = V.arm_exit_shares(ds, key + ("evol",), (0, 1), None)
    assert shares["top"] == pytest.approx(5 / 15)       # 10 rows kept plus 5 gone
    assert shares["bottom"] == 0.0


def test_an_adverse_bound_closes_long_at_bid_and_short_at_ask():
    ch = four_leg_chain()
    b = V.adverse_bound(ch, trade(), "RC")
    # Back: short the ATM closed at the 7.2 ask, long wings closed at the 2.0 bid.
    pts = -(7.2 - 5.1) + 2 * (2.0 - 1.1) - 0.039
    assert b["back"] == pytest.approx(pts / SPOT)
    # Front: long ATM closed at the 7.0 bid, short wings closed at the 2.2 ask.
    assert b["front"] == pytest.approx(((7.0 - 5.1) - 2 * (2.2 - 1.1) - 0.039) / SPOT)
    ch._memo[("QQQ", EXPIRY, 460.0, "Call")][1].pop(EXIT_T7)
    b = V.adverse_bound(ch, trade(), "RC")
    assert b["front"] is None                           # a short leg with no ask: no bound
    assert b["back"] == pytest.approx((-(7.2 - 5.1) + 2 * (0.0 - 1.1) - 0.039) / SPOT)


def test_unconditional_token():
    t = V.unconditional_token
    assert t(100, 8, 0.01, 0.1, 0.1, 0.1, 0.1) == V.CANDIDATE
    assert t(100, 8, 0.01, 0.1, 0.1, -0.1, 0.1) == V.NULL
    assert t(100, 8, 0.01, -0.1, -0.1, -0.1, -0.1) == V.CONTRARY
    assert t(100, 8, 0.2, 0.1, 0.1, 0.1, 0.1) == V.NULL
    assert t(59, 8, 0.01, 0.1, 0.1, 0.1, 0.1) == V.UNDERPOWERED
    assert t(100, 5, 0.01, 0.1, 0.1, 0.1, 0.1) == V.UNDERPOWERED
    assert t(100, 8, 0.01, 0.1, 0.1, 0.1, 0.1, exit_ok=False) == V.UNDERPOWERED


def drop_of(r, y_low=-0.01, y_high=0.01, bound=None):
    return dict(d=r["d"], date=r["date"], exit=r["exit"], si=r["si"], dte=r["dte"], wd=r["wd"],
                up=True, reason="stale_exit_mark", y_low=y_low, y_high=y_high,
                bound=bound if bound is not None else {s: y_low for s in r["net"]})


def test_an_over_limit_side_keeps_its_verdict_when_the_adverse_touch_does_not_change_it():
    ds = dataset()
    key = ("QQQ", "T30", "S")
    for r in ds.rows[key]:
        r["net"]["long"] = r["net"]["long"] * 0.0 + 0.001 + 0.001 * math.sin(r["si"])
    moved = ds.rows[key][::5]
    ds.rows[key] = [r for r in ds.rows[key] if r not in moved]
    ds.rows = {k: (v if k == key else []) for k, v in ds.rows.items()}   # one series in Holm
    # Mild drops: 25% of the series, closed just under the mean.
    ds.exit_drops[key] = [drop_of(r, bound={"long": 0.0009}) for r in moved]
    u = V.grade_unconditional(ds, n_boot=100)[key + ("long",)]
    assert u["exit_share"] > V.EXIT_DROP_MAX
    assert u["token"] == V.CANDIDATE
    # Severe drops flip the verdict, so it reads UNDERPOWERED.
    ds.exit_drops[key] = [drop_of(r, bound={"long": -0.05}) for r in moved]
    assert V.grade_unconditional(ds, n_boot=100)[key + ("long",)]["token"] == V.UNDERPOWERED
    # A short leg with no ask has no bound.
    ds.exit_drops[key] = [drop_of(r, bound={"long": None}) for r in moved]
    assert V.grade_unconditional(ds, n_boot=100)[key + ("long",)]["token"] == V.UNDERPOWERED


def test_bounded_pairs_close_against_the_cells_sign_and_flag_a_missing_ask():
    ds = dataset(n_days=100)
    cell = ("QQQ", "T30", "S", "evol")
    rows = ds.rows[cell[:3]]
    fm = ds.features[cell[:2]]
    a, b = rows[0], rows[1]
    fm[a["date"]]["evol"], fm[b["date"]]["evol"] = 1.0, 0.0
    ds.exit_drops[cell[:3]] = [drop_of(a), drop_of(b)]
    n0 = len(V.cell_pairs(ds, cell))
    pairs, unbounded = V.bounded_pairs(ds, cell, (0, 1), 1)
    assert not unbounded and len(pairs) == n0 + 2
    synth = {r["date"]: r["y"] for _, r in pairs if r.get("synth")}
    assert synth == {a["date"]: -0.01, b["date"]: 0.01}
    pairs, _ = V.bounded_pairs(ds, cell, (0, 1), -1)
    synth = {r["date"]: r["y"] for _, r in pairs if r.get("synth")}
    assert synth == {a["date"]: 0.01, b["date"]: -0.01}
    ds.exit_drops[cell[:3]] = [drop_of(a, y_low=None)]
    assert V.bounded_pairs(ds, cell, (0, 1), 1)[1] is True


def test_an_adverse_y_reads_the_low_and_high_touch():
    low, high = V.adverse_y(four_leg_chain(), trade(), "S")
    assert low == pytest.approx(((7.0 - 5.1) + (3.0 - 4.1)) / SPOT)
    assert high == pytest.approx(((7.2 - 5.1) + (3.2 - 4.1)) / SPOT)


def over_limit_ds():
    ds = dataset(seed=2)
    key = ("QQQ", "T30", "S")
    rows = ds.rows[key]
    gone = rows[::4]
    ds.rows[key] = [r for r in rows if r not in gone]
    return ds, key, gone


def test_an_unranked_over_limit_cell_reads_underpowered_not_null():
    ds, key, gone = over_limit_ds()
    disc = V.discover(ds, draws=20)
    i = next(n for n, c in enumerate(disc) if c.cell == key + ("ret1",))
    ds.exit_drops[key] = [drop_of(r) for r in gone]
    assert V.unranked_token(ds, disc, i) == V.UNDERPOWERED
    ds.exit_drops[key] = []
    assert V.unranked_token(ds, disc, i) == V.NULL
    j = next(n for n, c in enumerate(disc) if not c.gradable)
    assert V.unranked_token(ds, disc, j) == V.UNDERPOWERED


def test_over_the_limit_a_null_never_stands_in_any_read():
    assert V.can_stand_over_limit(V.CANDIDATE) and V.can_stand_over_limit(V.CONTRARY)
    assert not V.can_stand_over_limit(V.NULL)
    # Unconditional: a mean of zero is NULL under the limit and UNDERPOWERED over it.
    ds = dataset()
    key = ("QQQ", "T30", "S")
    ds.rows = {k: (v if k == key else []) for k, v in ds.rows.items()}
    for r in ds.rows[key]:
        r["net"]["long"] = 0.01 if r["si"] % 42 < 21 else -0.01
    assert V.grade_unconditional(ds, n_boot=100)[key + ("long",)]["token"] == V.NULL
    moved = ds.rows[key][::5]
    ds.rows[key] = [r for r in ds.rows[key] if r not in moved]
    ds.exit_drops[key] = [drop_of(r, bound={"long": 0.0}) for r in moved]
    assert V.grade_unconditional(ds, n_boot=100)[key + ("long",)]["token"] == V.UNDERPOWERED
    # A confirmed-cell NULL over the limit, with every drop boundable.
    ds2, k2, gone = over_limit_ds()
    d = V.DiscCell(k2 + ("ret1",), 100, True, 0.3, 0.01, 0.01, 0.01)
    ds2.exit_drops[k2] = [drop_of(r) for r in gone]
    c = V.confirm(ds2, [d], draws=20, n_boot=20)[0]
    assert c.token == V.UNDERPOWERED


def test_a_17_row_arm_reads_underpowered_not_tradable():
    pairs = noisy_pairs(0.02, 0.0, n=17, sd=0.001, seed=1)
    pos = V.best_position(pairs, (0, 1), "S", 1, n_boot=100)
    assert pos["n"] == 17 and pos["ok"]                 # its one-block p looks perfect
    assert V.position_clears(pos) is None
    assert V.confirm_token(1, 0.02, 0.01, True, True, V.position_clears(pos), True) == V.UNDERPOWERED
    assert V.forward_cell_token(True, 0.02, 0.01, 1, V.position_clears(pos)) == V.UNDERPOWERED
    base = dict(cell=("a",), point=0.1, p=0.001, floors=True, exit_ok=True, tradable=None)
    assert V.live_tokens([base])[("a",)] == V.UNDERPOWERED
    # A CONTRARY needs no position, and a failed test stays NULL.
    assert V.confirm_token(1, -0.02, 0.01, True, True, None, True) == V.CONTRARY
    assert V.confirm_token(1, 0.02, 0.2, True, True, None, True) == V.NULL
    # At three full blocks the test is read again.
    wide = noisy_pairs(0.02, 0.0, n=63, sd=0.001, seed=1)
    assert V.position_clears(V.best_position(wide, (0, 1), "S", 1, n_boot=100)) is True


def test_a_confirmed_cell_over_the_limit_reads_underpowered_when_unbounded():
    ds, key, gone = over_limit_ds()
    d = V.DiscCell(key + ("ret1",), 100, True, 0.3, 0.01, 0.01, 0.01)
    ds.exit_drops[key] = [drop_of(r, y_low=None) for r in gone]
    c = V.confirm(ds, [d], draws=20, n_boot=20)[0]
    assert c.token == V.UNDERPOWERED and "no ask" in c.exit_note
    ds.exit_drops[key] = []
    c = V.confirm(ds, [d], draws=20, n_boot=20)[0]
    assert c.exit_note == "within the limit"


def test_live_exit_shares_read_live_rows_only():
    ds = live_ds(100)
    key = ("QQQ", "T30", "S")
    rows = ds.rows[key]
    retro = [r for r in rows if ds.index[("MARKET", r["date"])]["lag"] == "RETRO"][:50]
    ds.rows[key] = [r for r in rows if r not in retro]
    ds.exit_drops[key] = [drop_of(r) for r in retro]
    cell = key + ("mkt_dir",)
    assert V.arm_exit_shares(ds, cell, (0, 1), None, lag="LIVE") == {"top": 0.0, "bottom": 0.0}
    assert V.arm_exit_shares(ds, cell, (0, 1), None)["top"] > 0


def test_holm_runs_across_the_12_series_not_the_sides():
    ps = {("Q", "T", str(i)): {"back": 0.004, "front": 0.5} for i in range(11)}
    ps[("Q", "T", "x")] = {"long": 0.04}
    adj = V.holm_series(ps)
    assert adj[("Q", "T", "0")]["back"] == pytest.approx(0.004 * 12)
    assert adj[("Q", "T", "x")]["long"] == pytest.approx(0.048)
    assert adj[("Q", "T", "0")]["front"] == 1.0
    lone = V.holm_series({("Q", "T", "S"): {"long": 0.02}})
    assert lone[("Q", "T", "S")]["long"] == 0.02


def test_forward_words():
    assert V.forward_mean_token(59, 8, 0.01, 0.1) == V.STILL_OPEN
    assert V.forward_mean_token(60, 6, 0.01, 0.1) == V.CANDIDATE
    assert V.forward_mean_token(60, 6, 0.01, -0.1) == V.CONTRARY
    assert V.forward_mean_token(60, 6, 0.2, 0.1) == V.NULL
    assert V.forward_mean_token(60, 6, 0.01, 0.1, exit_ok=False) == V.UNDERPOWERED
    assert V.forward_mean_token(59, 6, 0.01, 0.1, exit_ok=False) == V.STILL_OPEN
    assert V.forward_cell_token(False, 0.1, 0.01, 1, True) == V.STILL_OPEN
    assert V.forward_cell_token(True, 0.1, 0.01, 1, True) == V.CANDIDATE
    assert V.forward_cell_token(True, 0.1, 0.01, 1, False) == V.NULL
    assert V.forward_cell_token(True, -0.1, 0.01, 1, True) == V.CONTRARY
    assert V.forward_cell_token(True, 0.1, 0.01, 1, True, exit_ok=False) == V.UNDERPOWERED


def test_an_unconditional_candidate_reaches_the_forward_grade():
    book = gated_book()
    assert V.forward_read(book, None, {}, {}, None, [], []) == [
        "  FORWARD  no CANDIDATE, so nothing to grade"]
    lines = V.forward_read(book, None, {}, {}, None, [], [("QQQ", "T30", "S", "long")])
    assert V.STILL_OPEN in lines[0] and "await a fetch" in lines[0]


def live_ds(n_live: int) -> V.Dataset:
    ds = dataset()
    index = {}
    for iso, _ in ds.features[("QQQ", "T30")].items():
        index[("MARKET", iso)] = {"lag": "RETRO"}
    for tn, fmap in ds.features.items():
        for i, iso in enumerate(sorted(fmap)):
            fmap[iso]["mkt_dir"] = float(i % 2)
            fmap[iso]["mkt_vol"] = float(1 + 2 * (i % 2))
            fmap[iso]["mkt_hp_score"] = float((i * 37) % 100)
    for iso in sorted(fmap)[-n_live:] if n_live else []:
        index[("MARKET", iso)] = {"lag": "LIVE"}
    ds.index = index
    return ds


def test_the_live_read_is_underpowered_below_60_dates_and_ignores_retro_rows(monkeypatch):
    monkeypatch.setattr(V.era_mod, "SEAL_LIFTED", None)
    ds = live_ds(28)
    tokens, rows, awaiting = V.live_read(None, ds, ds.index, {}, None, draws=5, n_boot=20)
    assert len(rows) == 36 and awaiting == 0
    assert all(r["n"] == 28 for r in rows)
    assert set(tokens.values()) == {V.UNDERPOWERED}


def test_the_live_read_grades_once_the_floor_is_met(monkeypatch):
    monkeypatch.setattr(V.era_mod, "SEAL_LIFTED", None)
    ds = live_ds(150)
    tokens, rows, _ = V.live_read(None, ds, ds.index, {}, None, draws=5, n_boot=20)
    assert all(r["n"] == 150 for r in rows)
    assert V.UNDERPOWERED not in tokens.values()
    assert set(tokens.values()) <= {V.CANDIDATE, V.NULL}


def test_live_tokens_bh_runs_across_the_shortlist():
    base = dict(point=0.1, floors=True, tradable=True, exit_ok=True)
    rows = [dict(base, cell=("a", str(i)), p=0.001) for i in range(2)]
    rows.append(dict(base, cell=("b",), p=0.9))
    rows.append(dict(base, cell=("c",), p=0.001, tradable=False))
    rows.append(dict(base, cell=("d",), p=0.001, floors=False))
    rows.append(dict(base, cell=("e",), p=0.001, exit_ok=False))
    t = V.live_tokens(rows)
    assert t[("a", "0")] == V.CANDIDATE and t[("b",)] == V.NULL and t[("c",)] == V.NULL
    assert t[("d",)] == V.UNDERPOWERED and t[("e",)] == V.UNDERPOWERED


def test_the_live_read_uses_the_confirmation_bar():
    base = dict(point=0.1, floors=True, tradable=True, exit_ok=True)
    assert V.live_tokens([dict(base, cell=("a",), p=0.08)])[("a",)] == V.NULL
    assert V.live_tokens([dict(base, cell=("a",), p=0.05)])[("a",)] == V.CANDIDATE


def test_an_analysis_label_is_read_only_through_its_lag_bin():
    ds = live_ds(28)
    x, _y, _si = V.cell_xy(ds, ("QQQ", "T30", "S", "mkt_hp_score"), lag="LIVE")
    assert len(x) == 28
    x, _y, _si = V.cell_xy(ds, ("QQQ", "T30", "S", "mkt_hp_score"), lag="RETRO")
    assert len(x) == 472


def test_qqq_only_feature_reads_qqqs_value_on_smhs_series():
    ds = dataset()
    for iso, fv in ds.features[("QQQ", "T30")].items():
        fv["qqq_prem"] = fv["ret1"]
    x, _y, _si = V.cell_xy(ds, ("SMH", "T30", "S", "qqq_prem"), feature_ticker="QQQ")
    assert len(x) == 500
    assert V.cell_xy(ds, ("SMH", "T30", "S", "qqq_prem"))[0] == []


def test_confirm_prints_robustness_lines_that_are_not_in_the_bar():
    ds = dataset()
    disc = V.DiscCell(("QQQ", "T30", "S", "ret1"), 100, True, 0.3, 0.01, 0.01, 0.01)
    plain = V.confirm(ds, [disc], draws=30, n_boot=20)[0]
    assert plain.other_n > 0 and plain.window_point == plain.window_point
    # Flipping the other ticker cannot change the verdict.
    for r in ds.rows[("SMH", "T30", "S")]:
        r["y"] = -r["y"]
    flipped = V.confirm(ds, [disc], draws=30, n_boot=20)[0]
    assert flipped.token == plain.token
    assert V._sign(flipped.other_point) == -V._sign(plain.other_point)


def test_pbo_is_over_ranked_cells_only_at_unit_variance():
    ds = dataset(n_days=200)
    sessions = [r["d"] for r in ds.rows[("QQQ", "T30", "S")]]
    a = V.DiscCell(("QQQ", "T30", "S", "ret1"), 100, True, 0.3, 0.01, 0.01, 0.01)
    b = V.DiscCell(("SMH", "T30", "S", "ret1"), 100, True, -0.3, 0.01, 0.01, 0.01)
    for r in ds.rows[("SMH", "T30", "S")]:
        r["y"] *= 50.0                        # a high-variance series must not dominate
    M = V.pbo_matrix(ds, [a, b], sessions)
    assert M.shape == (200, 2)
    assert np.allclose(M.std(axis=0), 1.0)
    assert (M[:, 0] == 0).sum() > 40          # the middle tercile holds no position
    res, pad = V.run_pbo(ds, [a, b], sessions, S=6)
    assert 0 <= res.pbo <= 1 and res.n_configs == 2 and pad == (6 - 200 % 6) % 6
    assert V.run_pbo(ds, [a], sessions, S=6) is None


def test_unconditional_prints_side_figures_and_worst_windows():
    rows = dataset().rows[("QQQ", "T30", "RC")]
    b = V.unconditional(rows, "back", n_boot=30)
    f = V.unconditional(rows, "front", n_boot=30)
    assert b["n"] == f["n"] == 500
    assert b["mean"] == pytest.approx(-f["mean"] - 2e-5)
    assert b["worst"] == min(r["net"]["back"] for r in rows)
    assert b["worst_window"] == pytest.approx(
        min(sum(r["net"]["back"] for r in rows[i:i + V.BLOCK]) for i in range(len(rows) - V.BLOCK + 1)))
    assert V.unconditional([], "back", n_boot=5)["n"] == 0


# ── the coverage gate ───────────────────────────────────────────────────────

SESS = weekdays(date(2024, 1, 1), date(2026, 12, 31))


def gated_book(ch=None, bars=None, evidence=frozenset()) -> V.Book:
    full = {d: Bar(c=SPOT, o=SPOT, h=SPOT + 1, l=SPOT - 1, v=1000.0) for d in SESS}
    return V.Book(ch if ch is not None else chain_of({}), set(evidence),
                  {d: SPOT for d in SESS}, bars if bars is not None else
                  {"QQQ": full, "SMH": full})


def forbid_prices(monkeypatch) -> None:
    def boom(*a, **k):
        raise AssertionError("an option price was read before the gate")
    monkeypatch.setattr(V.SIM, "entry_day_fill", boom)
    monkeypatch.setattr(V.SPD, "leg_mark", boom)
    monkeypatch.setattr(V.IV, "natural_fill", boom)
    monkeypatch.setattr(V, "run_trade", boom)


def test_gate_blocks_pricing_before_it_opens(monkeypatch):
    forbid_prices(monkeypatch)
    book = gated_book()
    tr = book.trades("QQQ", V.T7)[0]
    assert tr.status == "await"
    with pytest.raises(V.AwaitingScrape):
        book.open_outcomes()
    with pytest.raises(V.AwaitingScrape):
        book.price(trade(), "S")
    with pytest.raises(V.AwaitingScrape):
        book.option_row(trade(), "Call")
    with pytest.raises(V.AwaitingScrape):
        V.build_dataset(book, {}, {}, None)


def test_one_awaiting_trade_anywhere_keeps_the_whole_gate_shut():
    book = gated_book()
    built = dict(status="built", fetch=(), found=(), reason="")
    for tk in V.TICKERS:
        for t in V.TENORS:
            for d in book.signals():
                book._tr[(tk, t.name, d)] = V.Trade(tk, t, d, d, d, **built)
    book.split_census = lambda: {tk: (0, []) for tk in V.TICKERS}
    book.open_outcomes()
    assert book._open
    # A partial cache: three of four pairs done, one trade awaiting on SMH T7.
    book._open = False
    last = book.signals()[-1]
    book._tr[("SMH", "T7", last)] = V.Trade("SMH", V.T7, last, last, last, "await",
                                            "strike_not_cached", fetch=(("Call", last, 1.0),))
    with pytest.raises(V.AwaitingScrape, match="SMH T7: 1 trades await"):
        book.open_outcomes()
    assert not book._open
    with pytest.raises(V.AwaitingScrape):
        book.price(book._tr[("QQQ", "T30", last)], "S")


def test_a_stale_ohlc_shuts_the_gate_even_with_no_trade_awaiting():
    bars = {d: Bar(c=SPOT) for d in SESS if d <= date(2026, 8, 11)}
    book = gated_book(bars={"QQQ": bars, "SMH": bars})
    for tk in V.TICKERS:
        for t in V.TENORS:
            for d in book.signals():
                book._tr[(tk, t.name, d)] = V.Trade(tk, t, d, d, d, "drop", "x")
    book.split_census = lambda: {tk: (0, []) for tk in V.TICKERS}
    assert any("OHLC ends 2026-08-11" in p for p in book.gate_problems())


def test_off_runs_tell_a_split_from_a_bad_print():
    days = weekdays(date(2024, 1, 1), date(2024, 1, 31))
    ok = [(d, 1.0) for d in days]
    glitch = [(d, 0.04 if i == 5 else 1.0) for i, d in enumerate(days)]
    split = [(d, 2.0 if i < 10 else 1.0) for i, d in enumerate(days)]
    assert V.off_runs(ok) == (0, [])
    assert V.off_runs(glitch) == (1, [])
    g, runs = V.off_runs(split)
    assert g == 0 and len(runs) == 1 and runs[0][2] == 2.0


def run_main(monkeypatch, book, capsys) -> str:
    monkeypatch.setattr(V, "load_analysis",
                        lambda: ({("MARKET", d.isoformat()): {} for d in book.signals()},
                                 dict(era="v4", seal="SEAL: x")))
    monkeypatch.setattr(V, "build_book", lambda: book)
    assert V.main([]) == 0
    return capsys.readouterr().out


def test_a_partial_cache_prints_not_built_coverage_and_no_return_figure(monkeypatch, capsys, tmp_path):
    forbid_prices(monkeypatch)
    monkeypatch.setattr(V, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(V, "TRADES_CSV", tmp_path / "out" / "t.csv")
    # Cached, usable legs on one date only: a partial cache.
    rows = {D: row(5, 5.2), FILL: row(5, 5.2), EXIT_T7: row(6, 6.2)}
    ch = chain_of({(o, EXPIRY, k): rows for o, k in (("Call", 450.0), ("Put", 450.0),
                                                     ("Call", 460.0), ("Put", 440.0))})
    out = run_main(monkeypatch, gated_book(ch), capsys)
    assert V.NOT_BUILT in out
    assert "contracts found" in out and "awaited" in out
    assert "No outcome was computed" in out
    assert not re.search(r"\d\s*%", out), "a percentage reached a NOT BUILT report"
    for word in ("mean", "CI95", "UNCONDITIONAL", "CANDIDATE", "PBO"):
        assert word not in out
    assert not (tmp_path / "out").exists()


# ── past the gate: the whole report, on synthetic quotes ────────────────────

def synthetic_chain() -> NTF.Chain:
    """Every contract a flat-spot walk names, quoted before each expiry, from a
    fixed seed, so each trade is built."""
    rng = random.Random(4)
    expiries = sorted({e for t in V.TENORS for d in SESS[:900]
                       for e in [V.pick_expiry(t, d, set(SESS), SESS[-1])] if e})
    idx: dict = {}
    ch = NTF.Chain(idx=idx)
    days = [d for d in SESS if date(2024, 1, 1) <= d <= date(2026, 11, 30)]
    # QQQ wings: T30 5%, T7 2.5% at $1. SMH wings: T30 9%, T7 4.5% at $2.5.
    legs = ((450.0, "Call"), (450.0, "Put"), (472.0, "Call"), (427.0, "Put"), (461.0, "Call"),
            (439.0, "Put"), (490.0, "Call"), (410.0, "Put"), (470.0, "Call"), (430.0, "Put"),
            (472.5, "Call"), (427.5, "Put"), (461.25, "Call"), (438.75, "Put"))
    for tk in V.TICKERS:
        for e in expiries:
            for k, o in legs:
                idx.setdefault((tk, e), {}).setdefault(k, set()).add(o[0])
                det, ser = {}, []
                base = 8.0 if k == 450.0 else 2.0
                for d in days:
                    if d > e:
                        break
                    if (e - d).days > 80:
                        continue
                    m = base + rng.random()
                    det[d] = row(round(m - 0.1, 2), round(m + 0.1, 2), iv=20 + rng.random())
                    ser.append((d, det[d]["_mark"]))
                ch._memo[(tk, e, k, o)] = (ser, det)
    return ch


def test_outcomes_run_end_to_end_on_synthetic_quotes(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(V, "OUT_DIR", tmp_path)
    monkeypatch.setattr(V, "TRADES_CSV", tmp_path / "t.csv")
    monkeypatch.setattr(V, "ROOT", tmp_path)
    monkeypatch.setattr(V.confirm, "__defaults__", (5, 5, V.SEED))
    monkeypatch.setattr(V.discover, "__defaults__", (5, V.SEED))
    monkeypatch.setattr(V.unconditional, "__defaults__", (5, V.SEED, V.BLOCK))
    monkeypatch.setattr(V.grade_unconditional, "__defaults__", (5, V.SEED))
    monkeypatch.setattr(V.live_read, "__defaults__", (5, 5))
    monkeypatch.setattr(V.run_pbo, "__defaults__", (4,))
    monkeypatch.setattr(V.era_mod, "SEAL_LIFTED", None)
    monkeypatch.setattr(V, "file_fetched_on", lambda *a: V.DEPTH_TRUST)
    rng = random.Random(2)
    closes, bars = {}, {}
    for d in SESS:
        bars[d] = Bar(c=SPOT, o=SPOT, h=SPOT + rng.random(), l=SPOT - rng.random(),
                      v=1000.0 + rng.random())
        closes[d] = SPOT
    book = V.Book(synthetic_chain(), set(), closes, {"QQQ": bars, "SMH": bars})
    baseline = {d.isoformat(): {"qqq_total": 1 + rng.random(), "qqq_cp": rng.random()} for d in SESS}
    lab = V.MechLabeler([dict(date=d.isoformat(), mech_direction="BULL", mech_vol="L-VOL",
                              dir_ok=True) for d in SESS])
    index = {("MARKET", d.isoformat()): {"dir": 1, "vol": 1, "risk": 1, "hp": 1, "hp_score": 40,
                                         "flow": 3, "lag": "RETRO"} for d in SESS}
    book.open_outcomes()
    assert V.outcomes(book, index, baseline, lab) == 0
    out = capsys.readouterr().out
    for title in ("1. UNCONDITIONAL", "2. DISCOVERY", "3. CONFIRMATION", "QUALITY", "LIVE READ",
                  "PBO", "VERDICT"):
        assert title in out
    assert out.count(">>> daily_vol_structure UNCONDITIONAL") == 20
    assert out.count(V.RETRO_ONLY) >= 108
    assert "cells (144):" in out and "analysis cells (108)" in out
    assert "Pays every day: " in out and "Moves with a known feature: " in out
    assert "LIVE read, its own forward test: " in out
    assert V.FRONT_CAVEAT in out and V.STRADDLE_CAVEAT in out
    assert "Nothing ships from this study." in out
    assert (tmp_path / "t.csv").exists()


# ── the collector ───────────────────────────────────────────────────────────

PLAN = [dict(ticker="QQQ", expiration=EXPIRY, strike=450.0, opt_type="Put", category="QQQ:T7",
             needed=None)]


@pytest.fixture
def no_network(monkeypatch):
    from scripts.backtest.shared import history

    async def boom(*a, **k):
        raise AssertionError("network fetch attempted")
    monkeypatch.setattr(history, "fetch_option_histories", boom)
    monkeypatch.setattr(F.DVS, "build_book", lambda: gated_book())
    monkeypatch.setattr(F.DVS, "fetch_targets", lambda book, scope="window": list(PLAN))


def test_collector_dry_run_is_offline_and_prints_counts(no_network, monkeypatch, capsys):
    def busy(*a, **k):
        raise AssertionError("the dry run must not consult the writer guard")
    monkeypatch.setattr(F, "other_writers", busy)
    assert F.main(["--dry-run", "--list"]) == 0
    out = capsys.readouterr().out
    assert "to fetch (window): 1" in out and "puts=1" in out and "450.00P" in out
    assert "re-fetches=0" in out
    assert "contracts found" in out and "[dry-run] nothing fetched" in out


def test_collector_refuses_beside_another_writer(no_network, monkeypatch, capsys):
    monkeypatch.setattr(F, "other_writers", lambda: [("1", "fetch")])
    assert F.main(["--limit", "1"]) == F.EXIT_OTHER_WRITER
    assert "REFUSED" in capsys.readouterr().err


def test_the_collector_passes_refetch_dates_to_the_history_fetch(monkeypatch):
    from scripts.backtest.shared import history
    seen = {}

    async def stub(contracts, headless, timeout_ms, needed_dates=None, retry_unlisted=None):
        seen["needed"] = needed_dates
        return {}, {}
    monkeypatch.setattr(history, "fetch_option_histories", stub)
    t = dict(PLAN[0], needed=date(2024, 5, 28))
    other = dict(PLAN[0], strike=455.0)
    asyncio.run(F.fetch([t, other], True, 1000))
    assert list(seen["needed"].values()) == [date(2024, 5, 28)]


def test_fetch_targets_are_unique_and_name_calls_and_puts():
    book = gated_book()
    targets = V.fetch_targets(book)
    keys = [(t["ticker"], t["opt_type"], t["expiration"], t["strike"]) for t in targets]
    assert len(keys) == len(set(keys))
    assert {t["opt_type"] for t in targets} == {"Call", "Put"}
    assert {t["ticker"] for t in targets} == {"QQQ", "SMH"}
    assert all(t["category"].split(":")[1] in ("T30", "T7") for t in targets)
