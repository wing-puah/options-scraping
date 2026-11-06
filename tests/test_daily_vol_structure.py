"""daily_vol_structure: the mirror identity, the one-clock fill, the fixed exit, the
coverage gate, feature timing, the discovery split, the verdict words and the
collector's dry run.

Synthetic chains and bars only. No network, and no QQQ or SMH option file is read.
Two checks read committed-format calendars when present: the 60/40 date and the
frozen `E-VOL` label's coverage.
"""
from __future__ import annotations

import ast
import csv
import math
import random
import re
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


def test_natural_fill_prints_per_side_and_costs_more_than_mid():
    p = V.run_trade(four_leg_chain(), trade(), "RC")
    for side in ("back", "front"):
        mid_net = V.side_sign(side) * p.gross - p.comm
        assert p.natural[side] < mid_net
    # The natural print is each side's own, so it is not a mirror.
    assert p.natural["back"] != pytest.approx(-p.natural["front"])


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
    s = V.walk_strike(ch, set(), "QQQ", e, 450.0, 450.0, D, ("Call", "Put"))
    assert s.status == "await" and s.fetch == (("Put", e, 450.0),)
    both = chain_of({("Call", e, 450.0): {D: row(1, 2)}, ("Put", e, 450.0): {D: row(1, 2)}})
    assert V.walk_strike(both, set(), "QQQ", e, 451.0, 450.0, D, ("Call", "Put")).strike == 450.0


def test_walk_steps_past_evidence_and_not_yet_listed():
    e = EXPIRY
    stem = NTF.contract_stem("QQQ", e, 450.0, "Call")
    ch = chain_of({("Call", e, 455.0): {D + timedelta(days=30): row(1, 2)}})
    s = V.walk_strike(ch, {stem}, "QQQ", e, 450.0, 450.0, D, ("Call",))
    # 450 is skip-listed, then 445 is nearest-tied and uncached.
    assert s.status == "await" and s.strike == 445.0
    late = chain_of({("Call", e, 450.0): {D + timedelta(days=30): row(1, 2)}})
    assert V.walk_strike(late, set(), "QQQ", e, 450.0, 450.0, D, ("Call",)).strike != 450.0


def test_walk_matches_the_selloff_walk_on_one_type():
    e = date(2024, 7, 19)
    rows = {D: row(1, 2)}
    spy = chain_of({("Put", e, 400.0): rows, ("Put", e, 405.0): rows}, ticker="SPY")
    for target in (401.0, 404.0, 412.0, 395.0):
        ours = V.walk_strike(spy, set(), "SPY", e, target, 400.0, D, ("Put",))
        theirs = SPD.nearest_listed(spy, set(), e, target, 400.0, D, "Put")
        assert (ours.status, ours.strike) == (theirs.status, theirs.strike)


def test_a_sparse_cache_never_proves_an_expiry_unlisted():
    e = EXPIRY
    shallow = chain_of({("Call", e, k): {D + timedelta(days=5): row(1, 2)}
                        for k in (440.0, 445.0, 450.0, 455.0)})
    assert V.Listing(shallow, set()).state("QQQ", e, D) == "unknown"
    stems = {NTF.contract_stem("QQQ", e, k, "Call") for k in (440.0, 445.0, 450.0)}
    assert V.Listing(chain_of({}), stems).state("QQQ", e, D) == "no"
    assert V.Listing(chain_of({}), set(list(stems)[:2])).state("QQQ", e, D) == "unknown"
    live = chain_of({("Call", e, 450.0): {D - timedelta(days=5): row(1, 2)}})
    assert V.Listing(live, stems).state("QQQ", e, D) == "yes"


def test_select_trade_reads_only_the_signal_days_close():
    sessions = weekdays(date(2024, 5, 1), date(2024, 7, 31))
    index = {d: i for i, d in enumerate(sessions)}
    bars = {d: Bar(c=SPOT if d <= D else 9999.0) for d in sessions}
    ch = chain_of({})
    tr = V.select_trade(ch, set(), V.Listing(ch, set()), "QQQ", V.T7, D, sessions, index, bars)
    assert tr.status == "await" and tr.spot == SPOT and tr.fill == FILL
    assert {k for _o, _e, k in tr.fetch} == {450.0, 460.0, 440.0}
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


def test_baseline_columns(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text("date,qqq_call_prem,qqq_put_prem\n2024-03-15,60,40\n2024-03-18,,40\n"
                 "2024-03-19,10,0\n")
    b = V.load_baseline(p)
    assert b["2024-03-15"] == {"qqq_prem": 100.0, "qqq_cp": 1.5}
    assert b["2024-03-18"] == {"qqq_prem": None, "qqq_cp": None}
    assert b["2024-03-19"]["qqq_cp"] is None


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


def test_discovery_draws_are_block_bootstraps_own_draws():
    rng = random.Random(8)
    x = [rng.random() for _ in range(100)]
    y = [a + rng.gauss(0, 1) for a in x]
    b = FD.block_bootstrap(x, y, FD.spearman, V.BLOCK, 200, V.SEED)
    draws = V.spearman_draws(x, y, 200, V.SEED)
    assert FD.pctile(draws, 2.5) == pytest.approx(b.lo)
    assert FD.pctile(draws, 97.5) == pytest.approx(b.hi)
    assert 0 <= V.boot_p(b.point, draws) <= 1
    assert V.boot_p(float("nan"), draws) != V.boot_p(float("nan"), draws)


def test_a_discrete_feature_reads_levels_not_positional_terciles():
    x = [0.0] * 30 + [1.0] * 30
    y = [1.0] * 15 + [0.0] * 15 + [3.0] * 30
    f = V.FEATURE_BY_NAME["evol"]
    assert V.cut_stat(f.lo, f.hi)(x, y) == pytest.approx(3.0 - 0.5)
    # The rank tercile splits the tied zeros by position, so it reads another number.
    assert FD.tercile_contrast(x, y) != pytest.approx(3.0 - 0.5)
    assert V.contrast_fn(f) is not FD.tercile_contrast
    assert V.contrast_fn(V.FEATURE_BY_NAME["ret1"]) is FD.tercile_contrast
    assert math.isnan(V.cut_stat(0, 1)([0.0, 0.0], [1.0, 2.0]))


def test_power_floors():
    f = V.FEATURE_BY_NAME["ret1"]
    x = [float((i * 37) % 126) for i in range(126)]
    assert V.floors_met(f, x, list(range(126)))
    # Terciles that sit in one stretch of time fail the arm's block floor.
    assert not V.floors_met(f, [float(i) for i in range(126)], list(range(126)))
    assert not V.floors_met(f, x[:59], list(range(59)))
    # 60 rows inside two calendar blocks: the LIVE shape.
    assert not V.floors_met(f, x[:60], [0] * 30 + [21] * 30)
    e = V.FEATURE_BY_NAME["evol"]
    # A thin arm fails even with enough rows.
    assert not V.floors_met(e, [0.0] * 120 + [1.0] * 6, list(range(126)))


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
                                    natural={sd: V.side_sign(sd) * y - 1e-3 for sd in V.SIDES[s]},
                                    r={sd: None for sd in V.SIDES[s]}, debit=1.0, expiry=d,
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
    base = V.discover(ds, n_boot=30)
    assert V.ranked(base)
    for key, rows in ds.rows.items():
        for r in rows:
            if not V.in_discovery(r):
                r["y"] = float("nan")          # a read would poison every statistic
                r["net"] = None
                ds.features[key[:2]][r["date"]]["ret1"] = None
                ds.features[key[:2]][r["date"]]["evol"] = None
    after = V.discover(ds, n_boot=30)
    assert [repr((c.cell, c.rho, c.p, c.q)) for c in after] == [
        repr((c.cell, c.rho, c.p, c.q)) for c in base]


def test_ranked_takes_gradable_cells_at_q_10_percent():
    cell = ("QQQ", "T30", "S", "ret1")
    c = lambda g, q: V.DiscCell(cell, 100, g, 0.3, 0.01, 0.01, q)  # noqa: E731
    assert len(V.ranked([c(True, 0.05), c(True, 0.2), c(False, 0.01), c(True, float("nan"))])) == 1


# ── verdict words ───────────────────────────────────────────────────────────

def test_confirm_token_truth_table():
    tok = V.confirm_token
    good = dict(floors=True, other_floors=True, other_sign=1, sleeve_sign=1, pbo=0.2)
    assert tok(1, 0.1, 0.05, 0.2, **good) == V.CANDIDATE
    assert tok(1, -0.1, -0.2, -0.05, **good) == V.CONTRARY
    assert tok(1, 0.1, -0.05, 0.2, **good) == V.NULL
    assert tok(1, 0.1, 0.05, 0.2, **{**good, "floors": False}) == V.UNDERPOWERED
    assert tok(1, float("nan"), 0.05, 0.2, **good) == V.UNDERPOWERED
    assert tok(1, 0.1, 0.05, 0.2, **{**good, "other_floors": False}) == V.UNDERPOWERED
    assert tok(1, 0.1, 0.05, 0.2, **{**good, "other_sign": -1}) == V.NULL
    assert tok(1, 0.1, 0.05, 0.2, **{**good, "sleeve_sign": -1}) == V.NULL
    assert tok(1, 0.1, 0.05, 0.2, **{**good, "pbo": 0.5}) == V.NULL
    assert tok(1, 0.1, 0.05, 0.2, **{**good, "pbo": None}) == V.NULL


def test_unconditional_token():
    t = V.unconditional_token
    assert t(100, 8, 0.01, 0.02, 0.1, 0.1, 0.1) == V.CANDIDATE
    assert t(100, 8, 0.01, 0.02, 0.1, -0.1, 0.1) == V.NULL
    assert t(100, 8, -0.02, -0.01, -0.1, -0.1, -0.1) == V.CONTRARY
    assert t(100, 8, -0.02, 0.01, 0.1, 0.1, 0.1) == V.NULL
    assert t(59, 8, 0.01, 0.02, 0.1, 0.1, 0.1) == V.UNDERPOWERED
    assert t(100, 5, 0.01, 0.02, 0.1, 0.1, 0.1) == V.UNDERPOWERED


def test_an_analysis_cell_confirms_on_live_rows_only():
    ds = dataset()
    tn = ("QQQ", "T30")
    index = {}
    for iso, fv in ds.features[tn].items():
        fv["mkt_hp_score"] = random.Random(iso).random()
        index[("MARKET", iso)] = {"lag": "RETRO"}
    ds.index = index
    disc = V.DiscCell(("QQQ", "T30", "S", "mkt_hp_score"), 100, True, 0.3, 0.01, 0.01, 0.01)
    out = V.confirm(ds, [disc], pbo=0.1, n_boot=20)[0]
    assert out.n == 0 and out.token == V.UNDERPOWERED     # RETRO only: nothing can confirm
    assert V.FEATURE_BY_NAME["mkt_hp_score"].is_analysis


def test_qqq_only_feature_reads_qqqs_value_on_smhs_series():
    ds = dataset()
    for iso, fv in ds.features[("QQQ", "T30")].items():
        fv["qqq_prem"] = fv["ret1"]
    x, _y, _si = V.cell_xy(ds, ("SMH", "T30", "S", "qqq_prem"), feature_ticker="QQQ")
    assert len(x) == 500
    assert V.cell_xy(ds, ("SMH", "T30", "S", "qqq_prem"))[0] == []


def test_pbo_matrix_is_each_cell_both_ways_with_discovery_cuts():
    ds = dataset(n_days=200)
    sessions = [r["d"] for r in ds.rows[("QQQ", "T30", "S")]]
    cell = ("QQQ", "T30", "S", "ret1")
    c = V.DiscCell(cell, 100, True, 0.3, 0.01, 0.01, 0.01)
    M = V.pbo_matrix(ds, [c, V.DiscCell(("QQQ", "T30", "RC", "evol"), 1, False, 0, 0, 1, 1)], sessions)
    assert M.shape == (200, 2)
    assert np.allclose(M[:, 0], -M[:, 1])
    assert (M[:, 0] == 0).sum() > 40      # the middle tercile holds no position
    res = V.run_pbo(ds, [c, V.DiscCell(("SMH", "T30", "S", "ret1"), 100, True, .3, .01, .01, .01)],
                    sessions, S=6)
    assert 0 <= res.pbo <= 1 and res.n_configs == 4


def test_unconditional_prints_side_figures_and_worst_windows():
    rows = dataset().rows[("QQQ", "T30", "RC")]
    b = V.unconditional(rows, "back", n_boot=30)
    f = V.unconditional(rows, "front", n_boot=30)
    assert b["n"] == f["n"] == 500
    assert b["mean"] == pytest.approx(-f["mean"] - 2e-5)
    assert b["worst"] == min(r["net"]["back"] for r in rows)
    assert b["worst_window"] == pytest.approx(
        min(sum(r["net"]["back"] for r in rows[i:i + V.BLOCK]) for i in range(len(rows) - V.BLOCK + 1)))
    assert V.unconditional([], "back", n_boot=5)["token"] == V.UNDERPOWERED


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
    """Every contract that could be walked to, quoted every session, from a
    fixed seed. Grid strikes on a flat spot, so each trade is built."""
    rng = random.Random(4)
    expiries = sorted({e for t in V.TENORS for d in SESS[:900]
                       for e in [V.pick_expiry(t, d, set(SESS), SESS[-1])] if e})
    idx: dict = {}
    ch = NTF.Chain(idx=idx)
    days = [d for d in SESS if date(2024, 1, 1) <= d <= date(2026, 11, 30)]
    for tk in V.TICKERS:
        for e in expiries:
            for k, o in ((450.0, "Call"), (450.0, "Put"), (420.0, "Put"), (425.0, "Put"),
                         (430.0, "Put"), (440.0, "Put"), (410.0, "Put"), (480.0, "Call"),
                         (475.0, "Call"), (470.0, "Call"), (460.0, "Call"), (490.0, "Call")):
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
    monkeypatch.setattr(V, "BOOT_N", 5)
    monkeypatch.setattr(V, "DISC_BOOT_N", 5)
    monkeypatch.setattr(V, "PBO_S", 4)
    monkeypatch.setattr(V.confirm, "__defaults__", (None, 5, V.SEED))
    monkeypatch.setattr(V.discover, "__defaults__", (5, V.SEED))
    monkeypatch.setattr(V.unconditional, "__defaults__", (5, V.SEED, V.BLOCK))
    monkeypatch.setattr(V.run_pbo, "__defaults__", (4,))
    rng = random.Random(2)
    closes, bars = {}, {}
    for d in SESS:
        bars[d] = Bar(c=SPOT, o=SPOT, h=SPOT + rng.random(), l=SPOT - rng.random(),
                      v=1000.0 + rng.random())
        closes[d] = SPOT
    book = V.Book(synthetic_chain(), set(), closes, {"QQQ": bars, "SMH": bars})
    baseline = {d.isoformat(): {"qqq_prem": rng.random(), "qqq_cp": rng.random()} for d in SESS}
    lab = V.MechLabeler([dict(date=d.isoformat(), mech_direction="BULL", mech_vol="L-VOL",
                              dir_ok=True) for d in SESS])
    book.open_outcomes()
    assert V.outcomes(book, {}, baseline, lab) == 0
    out = capsys.readouterr().out
    assert "1. UNCONDITIONAL" in out and "2. DISCOVERY" in out and "3. CONFIRMATION" in out
    assert "THREE WAYS" in out and "VERDICT" in out
    assert out.count(">>> daily_vol_structure UNCONDITIONAL") == 20
    assert "Nothing ships from this study." in out
    assert (tmp_path / "t.csv").exists()


# ── the collector ───────────────────────────────────────────────────────────

PLAN = [dict(ticker="QQQ", expiration=EXPIRY, strike=450.0, opt_type="Put", category="QQQ:T7")]


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
    assert "contracts found" in out and "[dry-run] nothing fetched" in out


def test_collector_refuses_beside_another_writer(no_network, monkeypatch, capsys):
    monkeypatch.setattr(F, "other_writers", lambda: [("1", "fetch")])
    assert F.main(["--limit", "1"]) == F.EXIT_OTHER_WRITER
    assert "REFUSED" in capsys.readouterr().err


def test_fetch_targets_are_unique_and_name_calls_and_puts():
    book = gated_book()
    targets = V.fetch_targets(book)
    keys = [(t["ticker"], t["opt_type"], t["expiration"], t["strike"]) for t in targets]
    assert len(keys) == len(set(keys))
    assert {t["opt_type"] for t in targets} == {"Call", "Put"}
    assert {t["ticker"] for t in targets} == {"QQQ", "SMH"}
    assert all(t["category"].split(":")[1] in ("T30", "T7") for t in targets)
