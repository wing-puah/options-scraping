"""Tests for the $25k account-simulation study's pure machinery.

No CSV, no book, no Sheets export: every test builds its own dicts (and one
hand-made `Trade`) so the properties pinned here are the ones the study's
conclusions rest on —

  * the module is config-driven and holds no rebindable state: `Settings` is
    read once from YAML (or built in-memory here) and threaded explicitly,
  * the ledger accounting identity (G3) actually detects a leak,
  * the dollar-stop SCALING IDENTITY is exact (replaying at contracts x 2 under
    the frozen $1,000 harness stop is a $500 stop at the true size, and halving
    the dollars recovers the true P&L),
  * cap admission attributes a breach to exactly ONE constraint (A4), and
  * the ARM D downsize solves for the largest integer that fits every cap.
"""
import copy
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
import yaml  # noqa: E402

from scripts.backtest_study import account_sim  # noqa: E402
from scripts.backtest_study.account_sim import (  # noqa: E402
    BlindRec, Cfg, ConfigError, Ledger, LOOKAHEAD_REC_KEYS,
    LOOKAHEAD_ROW_COLUMNS, LookaheadError, Pos, Settings, Sim,
    POSITIONS_CSV_COLUMNS, admission, blind_records, book_signature,
    dense_episodes, load_settings, mark_key, new_cache, positions_rows,
    replay_sized, risk_contracts, sessions_between, signed_dn, simulate,
    sizing_budget, solve_contracts, write_positions_csv,
)
from scripts.backtest_study.harness import MAX_LOSS_ABS, Trade  # noqa: E402


# ── building a Settings without touching disk ───────────────────────────────

def make_settings(**over) -> Settings:
    base = dict(capital=25_000.0, risk_pct=0.02, max_per_day=3,
                per_pos_cap=0.25, net_cap=1.50,
                per_pos_grid=(0.15, 0.25, 0.40, float("inf")),
                net_grid=(1.00, 1.50, 2.50, float("inf")),
                capital_ladder=(25_000.0, 35_000.0, 50_000.0),
                hedge_risk_fraction=0.5, episode_max_gap=5,
                episode_min_dates=10, attrition_floor=0.60,
                maxdd_fraction=0.25, ratio_tolerance=0.15,
                g1_positions=220, g1_dates=90, g1_dollars=63_553.0,
                g1_dollar_tol=1.0, compound_enabled=False,
                mark_interval="month", budget_ceiling=1_000.0,
                source=Path("test.yml"),
                source_text="account:\n  capital: 25000\n")
    return Settings(**{**base, **over})


def _cfg(**kw):
    """A `Cfg` with every required field defaulted to the pre-registered
    values, any of which a test may override by keyword."""
    base = dict(label="t", capital=25_000.0, per_pos_cap=0.25, net_cap=1.50,
                risk_pct=0.02, max_per_day=3)
    base.update(kw)
    return Cfg(**base)


def _cfg_pp(per_pos: float):
    return _cfg(per_pos_cap=per_pos)


# ── ledger ──────────────────────────────────────────────────────────────────

def test_ledger_identity_holds_over_a_scripted_sequence():
    led = Ledger(25_000)
    led.open(4_000, "a")
    led.open(1_500, "b")
    assert led.cash == 19_500 and led.reserved == 5_500
    led.close(4_000, +900, "a")           # winner
    led.open(3_000, "c")
    led.close(1_500, -1_500, "b")         # full loss of the reserve
    led.close(3_000, +250, "c")
    assert not led.violations
    assert led.realized == -350
    assert abs(led.cash - (25_000 - 350)) < 1e-9
    assert led.reserved == 0
    assert led.checks == 6


def test_ledger_detects_a_leak():
    led = Ledger(25_000)
    led.open(1_000)
    led._leak = 1.0                        # the --selftest-gates injection
    led.close(1_000, +100)
    assert led.violations, "a $1 leak must break the identity"


def test_ledger_flags_negative_cash():
    led = Ledger(1_000)
    assert led.can_open(1_500) is False
    led.open(1_500)                        # forced past admission
    assert any("cash negative" in v for v in led.violations)


# ── scaling identity ────────────────────────────────────────────────────────

def _hand_trade(marks, contracts, entry=2.00, dte=30, signal=date(2025, 1, 6)):
    """A one-leg long call whose marks are exactly the weekday grid."""
    exp = signal + timedelta(days=dte)
    row = {
        "signal_date": signal.isoformat(), "ticker": "TEST",
        "structure": "long_call", "contracts": str(contracts),
        "dte_entry": str(dte), "entry_option_price": str(entry),
        "entry_underlying": "200",
        "legs": f"TEST:{exp.isoformat()}:100:C +1",
        "daily_price_csv": ",".join(str(m) for m in marks),
    }
    return row


def _grid_len(dte=30, signal=date(2025, 1, 6)):
    end = signal + timedelta(days=dte)
    d, n = signal + timedelta(days=1), 0
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def test_scaling_identity_gives_a_500_dollar_stop_and_exact_dollars():
    """1 contract, entry $2.00 (denom 2.0, $200 of premium per contract).

    A mark of 0.60 is pnl = (0.60-2.00)/2.00 = -0.70 -> -$140 at 1 contract:
    no stop either way. A mark of 0.20 is pnl = -0.90 -> -$180 at 1 contract...
    so scale the position instead: at 3 contracts a -0.90 pnl is -$540, which a
    $500 stop must catch and a $1,000 stop must not.
    """
    n = _grid_len()
    marks = [1.90] * n
    marks[2] = 0.20                        # -0.90 pnl on day 3
    row = _hand_trade(marks, contracts=3)

    rec = {"t": Trade(row), "credit": False, "structure": "long_call",
           "mech_cell": "PROD", "max_loss_per_contract": 200.0, "delta": 0.5}
    prof = dict(pt=None, sl=None, trig=None, trail=None, tef=None)

    # $500 stop (the study's): must fire on day 3 at -$540.
    got = replay_sized(rec, 3, 500.0, profile=prof)
    assert got["stop_exact"] is True
    assert got["exit_reason"] == "dollar_stop" and got["days_held"] == 3
    assert abs(got["R"] - (-0.90)) < 1e-9
    assert abs(got["dollars"] - (-0.90 * 2.0 * 100 * 3)) < 1e-6   # -$540 exactly

    # $1,000 stop (the frozen harness): must NOT fire; the path runs to the end.
    loose = replay_sized(rec, 3, MAX_LOSS_ABS, profile=prof)
    assert loose["exit_reason"] != "dollar_stop"
    assert abs(loose["dollars"] - (-0.05 * 2.0 * 100 * 3)) < 1e-6  # 1.90 mark, last day


def test_scaling_identity_leaves_pnl_untouched_when_no_stop_fires():
    n = _grid_len()
    marks = [2.40] * n
    row = _hand_trade(marks, contracts=1)
    rec = {"t": Trade(row), "credit": False, "structure": "long_call",
           "mech_cell": "PROD", "max_loss_per_contract": 200.0, "delta": 0.5}
    prof = dict(pt=None, sl=None, trig=None, trail=None, tef=None)
    a = replay_sized(rec, 1, 500.0, profile=prof)
    b = replay_sized(rec, 1, MAX_LOSS_ABS, profile=prof)
    assert abs(a["R"] - 0.20) < 1e-9 and abs(b["R"] - 0.20) < 1e-9
    assert abs(a["dollars"] - 40.0) < 1e-9 and abs(b["dollars"] - 40.0) < 1e-9


def test_scaled_dollars_scale_linearly_in_contracts():
    n = _grid_len()
    marks = [2.40] * n
    rec1 = {"t": Trade(_hand_trade(marks, 1)), "credit": False,
            "structure": "long_call", "mech_cell": "PROD",
            "max_loss_per_contract": 200.0, "delta": 0.5}
    prof = dict(pt=None, sl=None, trig=None, trail=None, tef=None)
    one = replay_sized(rec1, 1, 500.0, profile=prof)["dollars"]
    two = replay_sized(rec1, 2, 500.0, profile=prof)["dollars"]
    assert abs(two - 2 * one) < 1e-9


def test_memo_does_not_collide_across_exit_profiles():
    """Two profiles, same (rec, contracts, stop) — the memo must not confuse them.

    The bug this pins (found 2026-08-13 by G5, at a $1,000 stop): the memo key
    omitted the profile, so G2's `DEBIT_PROD`-profile answer at stop
    `MAX_LOSS_ABS` was handed back to any simulate() whose own stop was also
    $1,000 — a $25k book at 4%, or the $50k rung of the capital ladder at 2%.
    """
    n = _grid_len()
    marks = [2.40] * n
    marks[1] = 3.00                        # +0.50 pnl on day 2
    rec = {"t": Trade(_hand_trade(marks, 1)), "credit": False,
           "structure": "long_call", "mech_cell": "PROD",
           "max_loss_per_contract": 200.0, "delta": 0.5}

    no_target = dict(pt=None, sl=None, trig=None, trail=None, tef=None)
    takes_profit = dict(pt=0.50, sl=None, trig=None, trail=None, tef=None)

    # Same rec, same contracts, same stop — only the profile differs.
    a = replay_sized(rec, 1, MAX_LOSS_ABS, profile=no_target)
    b = replay_sized(rec, 1, MAX_LOSS_ABS, profile=takes_profit)
    assert a["exit_reason"] != "profit_target"
    assert b["exit_reason"] == "profit_target" and b["days_held"] == 2
    assert abs(b["R"] - 0.50) < 1e-9

    # And re-asking for the first one must still return the first one.
    assert replay_sized(rec, 1, MAX_LOSS_ABS, profile=no_target) == a


# ── sizing ──────────────────────────────────────────────────────────────────

def test_risk_contracts_is_a_max_loss_basis_with_a_floor_of_one():
    assert risk_contracts(100.0, 500.0) == 5
    assert risk_contracts(3_321.0, 500.0) == 1        # the floor / budget breach
    assert risk_contracts(499.0, 500.0) == 1
    assert risk_contracts(None, 500.0) is None
    assert risk_contracts(0.0, 500.0) is None


def test_signed_delta_notional_keeps_the_sign():
    rec = {"t": type("T", (), {"row": {"entry_underlying": "200"}})(),
           "delta": -0.30}
    assert abs(signed_dn(rec, 2) + 0.30 * 100 * 2 * 200) < 1e-9


# ── cap admission ───────────────────────────────────────────────────────────

def test_admission_passes_inside_every_cap():
    ok, why = admission(reserved=500, dn_signed=5_000, cash=25_000,
                        net_open=0.0, cfg=_cfg())
    assert ok and why is None


def test_cash_breach_is_attributed_to_cash_alone():
    ok, why = admission(reserved=900, dn_signed=100, cash=800,
                        net_open=0.0, cfg=_cfg())
    assert not ok and why == "cash"


def test_per_position_breach_is_attributed_alone():
    # 0.25 x 25,000 = 6,250; 6,300 breaches per-pos but not the 37,500 net cap.
    ok, why = admission(reserved=100, dn_signed=6_300, cash=25_000,
                        net_open=0.0, cfg=_cfg())
    assert not ok and why == "per_pos_delta"


def test_net_breach_is_attributed_alone_when_the_position_itself_fits():
    # 6,000 is inside per-pos; 33,000 already open puts the book over 37,500.
    ok, why = admission(reserved=100, dn_signed=6_000, cash=25_000,
                        net_open=33_000, cfg=_cfg())
    assert not ok and why == "net_delta"


def test_net_cap_nets_opposing_deltas():
    """A hedge REDUCES |net|, so a short-delta add must pass where a long fails."""
    long_ok, _ = admission(100, +6_000, 25_000, 33_000, _cfg())
    hedge_ok, _ = admission(100, -6_000, 25_000, 33_000, _cfg())
    assert not long_ok and hedge_ok


def test_infinite_caps_never_bind():
    cfg = _cfg(per_pos_cap=float("inf"), net_cap=float("inf"),
               enforce_cash=False)
    ok, why = admission(1e9, 1e9, 0.0, 1e9, cfg)
    assert ok and why is None


# ── ARM D downsize ──────────────────────────────────────────────────────────

def test_downsize_solves_the_largest_integer_that_fits_every_cap():
    # unit dn 1,000 -> per-pos cap 6,250 allows 6 contracts;
    # cash 2,600 with unit reserve 500 allows 5. The binding one wins.
    c = solve_contracts(max_c=10, unit_reserved=500.0, unit_dn=1_000.0,
                        cash=2_600.0, net_open=0.0, cfg=_cfg())
    assert c == 5


def test_downsize_is_capped_by_the_requested_size():
    c = solve_contracts(max_c=3, unit_reserved=10.0, unit_dn=10.0,
                        cash=25_000.0, net_open=0.0, cfg=_cfg())
    assert c == 3


def test_downsize_returns_zero_when_even_one_contract_breaches():
    c = solve_contracts(max_c=4, unit_reserved=100.0, unit_dn=7_000.0,
                        cash=25_000.0, net_open=0.0, cfg=_cfg())
    assert c == 0


def test_downsize_respects_the_net_cap_against_an_open_book():
    # 30,000 open, net cap 37,500 -> 7,500 of headroom = 3 units of 2,500.
    # per-pos is widened out of the way so the NET cap is the one that binds.
    cfg = _cfg_pp(1.0)
    c = solve_contracts(max_c=10, unit_reserved=10.0, unit_dn=2_500.0,
                        cash=25_000.0, net_open=30_000.0, cfg=cfg)
    assert c == 3
    # ...and with the shipped 0.25 per-position cap it is per-pos that binds, at 2.
    assert solve_contracts(max_c=10, unit_reserved=10.0, unit_dn=2_500.0,
                           cash=25_000.0, net_open=30_000.0, cfg=_cfg()) == 2


# ── compounding: the OPT-IN sizing re-mark (post-hoc friction model) ────────
#
# `compound=False` is the FROZEN, pre-registered, path-independent book, so the
# regression guard below matters as much as the feature tests: turning the knob
# off must reproduce sizing that cannot see realized P&L at all.

def test_mark_key_buckets_months():
    assert mark_key(date(2025, 1, 31), "month") == (2025, 1)
    assert mark_key(date(2025, 2, 1), "month") == (2025, 2)
    # a year boundary is also a month boundary.
    assert mark_key(date(2025, 12, 31), "month") != \
        mark_key(date(2026, 1, 1), "month")


def test_mark_key_buckets_quarters():
    for m in (1, 2, 3):
        assert mark_key(date(2025, m, 15), "quarter") == (2025, 0)
    assert mark_key(date(2025, 4, 1), "quarter") == (2025, 1)
    assert mark_key(date(2025, 7, 1), "quarter") == (2025, 2)
    assert mark_key(date(2025, 10, 1), "quarter") == (2025, 3)
    assert mark_key(date(2026, 1, 1), "quarter") == (2026, 0)


def test_mark_key_buckets_years():
    assert mark_key(date(2025, 1, 1), "year") == (2025,)
    assert mark_key(date(2025, 12, 31), "year") == (2025,)
    assert mark_key(date(2026, 1, 1), "year") == (2026,)


def test_mark_key_accepts_an_iso_string_like_a_session():
    assert mark_key("2025-03-04", "month") == mark_key(date(2025, 3, 4), "month")


def test_mark_key_rejects_an_unknown_interval():
    with pytest.raises(ConfigError, match="mark_interval"):
        mark_key(date(2025, 1, 1), "fortnight")


def test_sizing_budget_without_a_ceiling_is_just_risk_pct():
    assert sizing_budget(25_000.0, 0.02, None) == pytest.approx(500.0)
    assert sizing_budget(80_000.0, 0.02, None) == pytest.approx(1_600.0)


def test_sizing_budget_ceiling_binds_only_above_it():
    assert sizing_budget(25_000.0, 0.02, 1_000.0) == pytest.approx(500.0)
    assert sizing_budget(50_000.0, 0.02, 1_000.0) == pytest.approx(1_000.0)
    assert sizing_budget(90_000.0, 0.02, 1_000.0) == pytest.approx(1_000.0)


def test_admission_caps_scale_with_an_explicit_equity():
    """0.25 x 25,000 = 6,250 rejects a 7,000 position; re-marked to 40,000 the
    same cap is 10,000 and admits it."""
    reject, why = admission(100, 7_000, 25_000, 0.0, _cfg())
    assert not reject and why == "per_pos_delta"
    ok, why2 = admission(100, 7_000, 25_000, 0.0, _cfg(), equity=40_000.0)
    assert ok and why2 is None
    # ...and a marked-DOWN account tightens it: 0.25 x 20,000 = 5,000.
    down, why3 = admission(100, 6_000, 25_000, 0.0, _cfg(), equity=20_000.0)
    assert not down and why3 == "per_pos_delta"


def test_admission_net_cap_also_scales_with_equity():
    # net cap 1.50 x 25,000 = 37,500; 33,000 open + 6,000 breaches it.
    tight, why = admission(100, 6_000, 25_000, 33_000, _cfg())
    assert not tight and why == "net_delta"
    # 1.50 x 40,000 = 60,000 leaves room.
    assert admission(100, 6_000, 25_000, 33_000, _cfg(),
                     equity=40_000.0) == (True, None)


@pytest.mark.parametrize("args", [
    (500, 5_000, 25_000, 0.0),          # inside every cap
    (900, 100, 800, 0.0),               # cash
    (100, 6_300, 25_000, 0.0),          # per_pos_delta
    (100, 6_000, 25_000, 33_000),       # net_delta
])
def test_admission_equity_none_reproduces_the_static_basis(args):
    """`equity=None` must be exactly today's behaviour — the frozen book's
    admission is `cfg.capital`, and nothing about it may move."""
    cfg = _cfg()
    assert admission(*args, cfg) == admission(*args, cfg, equity=None)
    assert admission(*args, cfg) == admission(*args, cfg,
                                              equity=cfg.capital)


def test_solve_contracts_forwards_equity_to_admission():
    # per-pos cap 0.25 x 25,000 = 6,250 -> 2 units of 2,500; at 50,000 -> 5.
    kw = dict(max_c=10, unit_reserved=10.0, unit_dn=2_500.0, cash=25_000.0,
              net_open=0.0, cfg=_cfg())
    assert solve_contracts(**kw) == 2
    assert solve_contracts(**kw, equity=50_000.0) == 5


# -- simulate()-level: the re-mark actually moves sizing --------------------

def _fat_rec(signal: date, mlpc=500.0, entry=50.0, mark=90.0, dte=5,
             underlying=50.0, delta=0.05):
    """A one-leg long call that runs flat and well in the money.

    Deliberately fat (entry $50, so `denom` is $50) so ONE position books
    thousands of dollars and a month boundary visibly re-marks the budget —
    the study's real book needs dozens of positions to move equity that far.
    """
    end = signal + timedelta(days=dte)
    d, n = signal + timedelta(days=1), 0
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    row = _hand_trade([mark] * n, contracts=1, entry=entry, dte=dte,
                      signal=signal)
    row["entry_underlying"] = str(underlying)
    return {"t": Trade(row), "credit": False, "structure": "long_call",
            "mech_cell": "PROD", "max_loss_per_contract": mlpc, "delta": delta,
            "date": signal.isoformat(), "ticker": "TEST"}


def _two_month_day_lists():
    """One profitable January date, then a February date — the January
    position exits inside January, so February's mark sees its realized P&L."""
    jan, feb = date(2025, 1, 6), date(2025, 2, 3)
    return [(jan.isoformat(), [_fat_rec(jan)]),
            (feb.isoformat(), [_fat_rec(feb)])]


def test_compounding_re_marks_the_budget_after_a_profitable_month():
    day_lists = _two_month_day_lists()
    sim = simulate(day_lists, _cfg(compound=True, mark_interval="month",
                                   budget_ceiling=None))
    assert len(sim.marks) == 2
    (_, eq0, budget0, pp0, net0), (_, eq1, budget1, pp1, net1) = sim.marks

    # The first mark is the untouched starting basis: nothing has closed yet.
    assert eq0 == pytest.approx(25_000.0)
    assert budget0 == pytest.approx(500.0)
    assert (pp0, net0) == pytest.approx((0.25 * 25_000, 1.50 * 25_000))

    # January booked +$4,000 (R +0.80 x $50 denom x 100 x 1 contract).
    assert eq1 == pytest.approx(29_000.0)
    assert budget1 == pytest.approx(29_000.0 * 0.02)
    assert budget1 > budget0
    # BOTH delta caps scale with the mark; only the budget has a ceiling.
    assert (pp1, net1) == pytest.approx((0.25 * 29_000, 1.50 * 29_000))

    # The mark is a SIZING number only — the ledger keeps the STARTING capital,
    # which is what makes G3's identity meaningful.
    assert sim.ledger.capital == pytest.approx(25_000.0)
    assert not sim.ledger.violations


def test_compounding_budget_ceiling_clamps_the_re_marked_budget():
    day_lists = _two_month_day_lists()
    uncapped = simulate(day_lists, _cfg(compound=True, budget_ceiling=None))
    capped = simulate(day_lists, _cfg(compound=True, budget_ceiling=550.0))
    assert uncapped.marks[1][2] == pytest.approx(580.0)
    assert capped.marks[1][2] == pytest.approx(550.0)     # the ceiling binds
    # ...and the delta caps are NOT ceilinged — they still track the mark.
    assert capped.marks[1][3] == pytest.approx(uncapped.marks[1][3])
    assert capped.marks[1][4] == pytest.approx(uncapped.marks[1][4])


def test_compounding_ruin_guard_takes_nothing_and_keeps_the_a4_partition():
    """A wiped account opens nothing, and every candidate it refuses lands in
    its OWN census bucket — A4 asserts the buckets partition every candidate,
    so a ruined day that fell through to `taken`/`cash` would break the sum.

    Capital 0 is a degenerate account, chosen because it exercises the guard
    directly: the very first mark is `0 + realized 0 <= 0`.
    """
    day_lists = _two_month_day_lists()
    sim = simulate(day_lists, _cfg(capital=0.0, compound=True))
    assert sim.taken == []
    assert sim.census["ruined"] == 2
    assert [why for _, why, _ in sim.skipped] == ["ruined", "ruined"]
    assert all(m[1] <= 0 for m in sim.marks)
    # the ledger is untouched by the guard — no half-opened position.
    assert not sim.ledger.violations
    assert sim.ledger.reserved == 0.0

    # ...and the frozen path never fills that bucket at all: with no re-mark
    # there is no ruin to detect, and a broke account is refused on CASH.
    frozen = simulate(day_lists, _cfg(capital=100.0, compound=False))
    assert frozen.census["ruined"] == 0 and frozen.census["cash"] == 2


def test_compounding_quarter_interval_marks_less_often_than_month():
    """Two dates in the same quarter but different months: one mark, not two."""
    day_lists = _two_month_day_lists()
    monthly = simulate(day_lists, _cfg(compound=True, mark_interval="month"))
    quarterly = simulate(day_lists, _cfg(compound=True,
                                         mark_interval="quarter"))
    assert len(monthly.marks) == 2
    assert len(quarterly.marks) == 1


def test_compounding_off_is_path_independent_and_records_no_marks():
    """The REGRESSION GUARD. With the knob off, every position is sized off the
    static configured budget and no mark is taken — the frozen book."""
    day_lists = _two_month_day_lists()
    cfg = _cfg()
    assert cfg.compound is False and cfg.budget_ceiling is None
    sim = simulate(day_lists, cfg)
    assert sim.marks == []
    assert len(sim.taken) == 2
    for p in sim.taken:
        assert p.contracts == risk_contracts(
            p.rec["max_loss_per_contract"], cfg.budget)
    # ...and the book is byte-identical to one built without naming the knob.
    plain = Cfg(label="t", capital=25_000.0, per_pos_cap=0.25, net_cap=1.50,
                risk_pct=0.02, max_per_day=3)
    assert book_signature(sim) == book_signature(simulate(day_lists, plain))


def test_compounding_re_marked_caps_admit_a_position_the_frozen_cap_refuses():
    """The end-to-end proof that the re-mark reaches ADMISSION, not just the
    printed marks: February's position has $7,000 of delta-notional, over the
    frozen 0.25 x $25,000 = $6,250 cap and under the re-marked 0.25 x $29,000
    = $7,250 one."""
    jan, feb = date(2025, 1, 6), date(2025, 2, 3)
    day_lists = [(jan.isoformat(), [_fat_rec(jan)]),
                 (feb.isoformat(), [_fat_rec(feb, underlying=1_400.0)])]

    frozen = simulate(day_lists, _cfg(compound=False))
    assert len(frozen.signal_pos) == 1
    assert frozen.census["per_pos_delta"] == 1

    compounded = simulate(day_lists, _cfg(compound=True, budget_ceiling=None))
    assert len(compounded.signal_pos) == 2
    assert compounded.census["per_pos_delta"] == 0
    assert book_signature(frozen) != book_signature(compounded)


# ── population helpers ──────────────────────────────────────────────────────

def test_sessions_between_counts_weekdays_only():
    assert sessions_between("2025-01-06", "2025-01-07") == 1      # Mon -> Tue
    assert sessions_between("2025-01-03", "2025-01-06") == 1      # Fri -> Mon
    assert sessions_between("2025-01-06", "2025-01-06") == 0


def test_dense_episodes_splits_on_a_gap_and_drops_short_runs():
    run_a = [f"2025-03-{d:02d}" for d in range(3, 15)]     # 12 weekday-ish dates
    run_b = ["2025-06-02", "2025-06-03"]                   # too short
    eps = dense_episodes(run_a + run_b, max_gap=5, min_dates=10)
    assert len(eps) == 1 and eps[0][0] == run_a[0]
    assert len(eps[0]) == len(run_a)


def test_dense_episodes_keeps_a_run_across_a_five_session_gap():
    dates = ["2025-03-03", "2025-03-10"]                   # 5 sessions apart
    assert sessions_between(*dates) == 5
    dates += [f"2025-03-{d}" for d in range(11, 21)]
    eps = dense_episodes(dates, max_gap=5, min_dates=10)
    assert len(eps) == 1 and len(eps[0]) == 12


def test_dense_episodes_requires_explicit_max_gap_and_min_dates():
    """No defaults: a caller must state its own population thresholds — the
    settings this study runs with, never a module constant."""
    with pytest.raises(TypeError):
        dense_episodes(["2025-03-03"])


# ── outcome blindness (G5) ──────────────────────────────────────────────────
#
# The gate that matters most for the next consumer: an agent proposing live
# positions must not be able to lean on a number that would not exist yet.
# These pin the TRIPWIRE — that blinding actually raises — because a blind
# wrapper that silently returns None would let G5 pass while hiding a leak.

def _blindable_rec():
    n = _grid_len()
    row = _hand_trade([2.40] * n, contracts=1)
    row.update(realized_pnl_pct="0.20", exit_reason="profit_target",
               days_held="7", mfe_pct="0.55", mae_pct="-0.10",
               pnl_at_cap_pct="0.20", mfe_day="3", mae_day="1")
    return {"t": Trade(row), "credit": False, "structure": "long_call",
            "mech_cell": "PROD", "max_loss_per_contract": 200.0, "delta": 0.5,
            "date": "2025-01-06", "ticker": "TEST", "tier": "A",
            "R": 0.20, "exit_reason": "profit_target", "days_held": 7,
            "mfe": 0.55, "mae": -0.10, "R_dol": 40.0, "E": 0.20,
            "E_dol": 40.0, "mfe_day": 3, "mae_day": 1}


@pytest.mark.parametrize("key", sorted(LOOKAHEAD_REC_KEYS))
def test_blind_rec_raises_on_every_outcome_key(key):
    b = BlindRec(_blindable_rec())
    with pytest.raises(LookaheadError):
        b[key]
    with pytest.raises(LookaheadError):
        b.get(key)


def test_blind_rec_passes_through_decision_fields():
    """Blinding must not disturb the fields selection legitimately reads —
    a wrapper that broke `tier`/`delta` would fail G5 for the wrong reason."""
    b = BlindRec(_blindable_rec())
    assert b["tier"] == "A"
    assert b.get("delta") == 0.5
    assert b["max_loss_per_contract"] == 200.0
    assert b.get("missing_key") is None
    assert b.get("mech_cell", "X") == "PROD"
    # present, but unreadable — membership must NOT be what raises.
    assert "R" in b and "exit_reason" in b


def test_blind_records_strip_outcome_columns_from_the_trade_row():
    """Layer 2: a read that routes around the wrapper via rec['t'].row must
    also come up empty, or blindness is only skin deep."""
    src = _blindable_rec()
    assert set(LOOKAHEAD_ROW_COLUMNS) <= set(src["t"].row)   # fixture is loaded
    b = blind_records([src])[0]
    row = b["t"].row
    assert not (set(LOOKAHEAD_ROW_COLUMNS) & set(row))
    # ...while the entry side and the price path survive, so it still prices.
    assert float(row["entry_option_price"]) == 2.0 and row["daily_price_csv"]
    assert b["t"].contracts == 1


def test_blind_records_still_replay_to_the_same_outcome():
    """The blinded record must produce an identical replay — that equality is
    exactly what G5 asserts across the whole book."""
    src = _blindable_rec()
    prof = dict(pt=None, sl=None, trig=None, trail=None, tef=None)
    want = replay_sized(src, 1, 500.0, profile=prof)
    got = replay_sized(blind_records([src])[0], 1, 500.0, profile=prof)
    assert (want["R"], want["dollars"], want["exit_reason"]) == \
           (got["R"], got["dollars"], got["exit_reason"])


def test_book_signature_distinguishes_size_and_outcome():
    rec = _blindable_rec()
    base = Sim(cfg=_cfg(), taken=[_pos(rec)])
    assert book_signature(base) == book_signature(
        Sim(cfg=_cfg(), taken=[_pos(rec)]))
    assert book_signature(base) != book_signature(
        Sim(cfg=_cfg(), taken=[_pos(rec, contracts=3)]))
    assert book_signature(base) != book_signature(
        Sim(cfg=_cfg(), taken=[_pos(rec, dollars=1.0)]))


# ── positions CSV ───────────────────────────────────────────────────────────
#
# Column sourcing is the thing under test: sim-outcome fields (contracts,
# reserved, dn, entry_sess/exit_sess, days_held, R, dollars, exit_reason,
# downsized, hedge) come off the `Pos`/counterfactual dict; book-context
# fields (max_loss_per_contract, delta, dte, score_total, mfe, mae, the regime
# block, mech_cell) and `shipped_R`/`shipped_exit_reason` come off `rec` — and the
# two R/exit_reason pairs (this sim's replay vs the STORED $50k-book outcome)
# must stay distinct columns.

def _rec(**over):
    rec = dict(date="2026-03-10", ticker="NVDA", structure="bull_put",
               credit=True, tier="A", max_loss_per_contract=180.0,
               delta=0.14, dte=45, score_total=32, mfe=0.55, mae=-0.20,
               market_regime="RANGE / L-VOL / risk-on", model_dir="RANGE",
               model_vol="L-VOL", regime="BULL",
               mech_direction="BULL", mech_vol="L-VOL", mech_cell="PROD",
               R=0.41, exit_reason="profit_target")           # shipped outcome
    rec.update(over)
    return rec


def _pos(rec, **over):
    kw = dict(rec=rec, contracts=2, reserved=360.0, dn=1_200.0,
              entry_sess=date(2026, 3, 11), exit_sess=date(2026, 3, 15),
              days_held=3, R=0.55, dollars=396.0, exit_reason="dollar_stop",
              downsized=False, hedge=False)
    kw.update(over)
    return Pos(**kw)


def test_positions_rows_taken_row_mixes_sim_outcome_and_book_context():
    rec = _rec()
    pos = _pos(rec)
    sim = Sim(cfg=_cfg(), taken=[pos])
    rows = positions_rows("primary", "RF1", sim)
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == set(POSITIONS_CSV_COLUMNS)
    assert row["population"] == "primary" and row["arm"] == "RF1"
    assert row["status"] == "taken"
    # sim-outcome fields come from Pos, NOT from rec's shipped values.
    assert row["contracts"] == 2 and row["reserved"] == 360.0
    assert row["dn"] == 1_200.0
    assert row["entry_sess"] == date(2026, 3, 11)
    assert row["exit_sess"] == date(2026, 3, 15)
    assert row["days_held"] == 3
    assert row["R"] == 0.55 and row["dollars"] == 396.0
    assert row["exit_reason"] == "dollar_stop"
    assert row["downsized"] is False and row["hedge"] is False
    assert row["reject_reason"] == ""
    # book-context + identity fields come straight off rec.
    assert row["date"] == "2026-03-10" and row["ticker"] == "NVDA"
    assert row["structure"] == "bull_put" and row["credit"] is True
    assert row["tier"] == "A"
    assert row["max_loss_per_contract"] == 180.0
    assert row["delta"] == 0.14 and row["dte"] == 45
    assert row["score_total"] == 32
    assert row["mfe"] == 0.55 and row["mae"] == -0.20
    # market regime (what the tier keys off) is carried SEPARATELY from the
    # per-play ticker regime — the two must never be conflated.
    assert row["market_regime"] == "RANGE / L-VOL / risk-on"
    assert row["model_dir"] == "RANGE" and row["model_vol"] == "L-VOL"
    assert row["regime"] == "BULL"
    assert row["mech_direction"] == "BULL" and row["mech_vol"] == "L-VOL"
    assert row["mech_cell"] == "PROD"
    # shipped_* is rec's STORED outcome, distinct from this sim's replay above.
    assert row["shipped_R"] == 0.41
    assert row["shipped_exit_reason"] == "profit_target"


def test_positions_rows_status_reflects_downsized_and_hedge():
    down = _pos(_rec(), downsized=True)
    hedge = _pos(_rec(), hedge=True, downsized=True)  # hedge status wins
    sim = Sim(cfg=_cfg(), taken=[down, hedge])
    rows = positions_rows("primary", "RF1", sim)
    assert rows[0]["status"] == "taken_downsized"
    assert rows[1]["status"] == "hedge"


def test_positions_rows_skipped_with_counterfactual_fills_outcome():
    rec = _rec()
    cf = dict(exit_reason="stop_loss", days_held=2, R=-0.30, dollars=-108.0,
              stop_exact=True)
    sim = Sim(cfg=_cfg(), skipped=[(rec, "cash", cf)])
    rows = positions_rows("primary", "RF1", sim)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "skipped:cash"
    assert row["reject_reason"] == "cash"
    assert row["exit_reason"] == "stop_loss" and row["days_held"] == 2
    assert row["R"] == -0.30 and row["dollars"] == -108.0
    # never-taken -> no contracts/reserved/dn/sizing fields.
    assert row["contracts"] is None and row["reserved"] is None
    # book-context still carried through even for a skip.
    assert row["max_loss_per_contract"] == 180.0
    assert row["shipped_R"] == 0.41


def test_positions_rows_skipped_without_counterfactual_leaves_outcome_blank():
    rec = _rec()
    sim = Sim(cfg=_cfg(), skipped=[(rec, "day3_cap", None)])
    rows = positions_rows("primary", "RF1", sim)
    row = rows[0]
    assert row["status"] == "skipped:day3_cap"
    assert row["reject_reason"] == "day3_cap"
    assert row["exit_reason"] is None and row["days_held"] is None
    assert row["R"] is None and row["dollars"] is None


def test_write_positions_csv_round_trips_both_populations(tmp_path):
    rec = _rec()
    primary = Sim(cfg=_cfg(label="p"), taken=[_pos(rec)],
                  skipped=[(rec, "day3_cap", None)])
    secondary = Sim(cfg=_cfg(label="s"), taken=[_pos(_rec(ticker="AMD"))])
    path = tmp_path / "account_sim-positions-latest.csv"
    n = write_positions_csv(path, {"primary": primary, "secondary": secondary})
    assert n == 3

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == POSITIONS_CSV_COLUMNS
        rows = list(reader)
    assert len(rows) == 3
    pops = {r["population"] for r in rows}
    assert pops == {"primary", "secondary"}
    tickers = {r["ticker"] for r in rows}
    assert tickers == {"NVDA", "AMD"}


# ── configuration surface (Settings / load_settings) ────────────────────────

def _full_config_dict() -> dict:
    """A minimal but complete config, structurally matching
    config/account-sim.yml — used only to prove the *shape* of the schema
    (required keys, null->inf grid entries); never to pin the shipped
    numbers, which are the operator's to move."""
    return {
        "account": {"capital": 25_000, "risk_per_trade_pct": 0.02,
                    "max_positions_per_day": 3},
        "caps": {"per_position": 0.25, "net": 1.50},
        "compounding": {"enabled": False, "mark_interval": "month",
                        "budget_ceiling": 1_000},
        "grids": {"per_position": [0.15, 0.25, 0.40, None],
                  "net": [1.00, 1.50, 2.50, None],
                  "capital_ladder": [25_000, 35_000, 50_000]},
        "hedge": {"risk_fraction": 0.5},
        "population": {"episode_max_gap": 5, "episode_min_dates": 10},
        "criteria": {"attrition_floor": 0.60, "maxdd_fraction": 0.25,
                     "ratio_tolerance": 0.15},
        "gates": {"book_calibration": {"expected_positions": 220,
                                       "expected_dates": 90,
                                       "expected_dollars": 63_553,
                                       "dollar_tolerance": 1.0}},
    }


def test_load_settings_reads_the_shipped_config():
    """Structural checks only — a legitimate re-point of the study at a
    different account must never fail this suite."""
    st = load_settings()
    raw = yaml.safe_load(account_sim.DEFAULT_CONFIG.read_text())
    assert st.capital == raw["account"]["capital"]
    assert st.risk_pct == raw["account"]["risk_per_trade_pct"]
    assert st.max_per_day == raw["account"]["max_positions_per_day"]
    assert st.per_pos_cap == raw["caps"]["per_position"]
    assert st.net_cap == raw["caps"]["net"]
    assert st.budget == pytest.approx(st.capital * st.risk_pct)
    assert st.capital > 0 and 0 < st.risk_pct < 1 and st.max_per_day >= 1
    assert st.per_pos_grid and st.net_grid and st.capital_ladder
    assert all(v > 0 for v in st.capital_ladder)
    assert list(st.capital_ladder) == sorted(st.capital_ladder)
    assert st.source == account_sim.DEFAULT_CONFIG


def test_load_settings_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError):
        load_settings(tmp_path / "does-not-exist.yml")


def test_load_settings_malformed_yaml_raises_config_error(tmp_path):
    p = tmp_path / "bad.yml"
    p.write_text("account: [1, 2\n  broken: true")
    with pytest.raises(ConfigError):
        load_settings(p)


def test_load_settings_non_mapping_top_level_raises_config_error(tmp_path):
    p = tmp_path / "list.yml"
    p.write_text("- 1\n- 2\n")
    with pytest.raises(ConfigError):
        load_settings(p)


@pytest.mark.parametrize("path", [
    ("account", "capital"),
    ("account", "risk_per_trade_pct"),
    ("account", "max_positions_per_day"),
    ("caps", "per_position"),
    ("caps", "net"),
    ("compounding", "enabled"),
    ("compounding", "mark_interval"),
    ("compounding", "budget_ceiling"),
    ("grids", "per_position"),
    ("grids", "net"),
    ("grids", "capital_ladder"),
    ("hedge", "risk_fraction"),
    ("population", "episode_max_gap"),
    ("population", "episode_min_dates"),
    ("criteria", "attrition_floor"),
    ("criteria", "maxdd_fraction"),
    ("criteria", "ratio_tolerance"),
    ("gates", "book_calibration", "expected_positions"),
    ("gates", "book_calibration", "expected_dates"),
    ("gates", "book_calibration", "expected_dollars"),
    ("gates", "book_calibration", "dollar_tolerance"),
])
def test_load_settings_raises_naming_a_missing_required_key(tmp_path, path):
    cfg = copy.deepcopy(_full_config_dict())
    node = cfg
    for k in path[:-1]:
        node = node[k]
    del node[path[-1]]
    p = tmp_path / "cfg.yml"
    p.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ConfigError, match=path[-1]):
        load_settings(p)


def test_load_settings_null_grid_entries_become_infinity(tmp_path):
    p = tmp_path / "cfg.yml"
    p.write_text(yaml.safe_dump(_full_config_dict()))
    st = load_settings(p)
    assert st.per_pos_grid[-1] == float("inf")
    assert st.net_grid[-1] == float("inf")
    # everything before the trailing null stays a plain float.
    assert st.per_pos_grid[:-1] == (0.15, 0.25, 0.40)
    assert st.net_grid[:-1] == (1.00, 1.50, 2.50)


def _write_cfg(tmp_path, **compounding) -> Path:
    cfg = copy.deepcopy(_full_config_dict())
    cfg["compounding"].update(compounding)
    p = tmp_path / "cfg.yml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def test_load_settings_reads_the_compounding_block(tmp_path):
    st = load_settings(_write_cfg(tmp_path, enabled=True,
                                  mark_interval="quarter",
                                  budget_ceiling=750))
    assert st.compound_enabled is True
    assert st.mark_interval == "quarter"
    assert st.budget_ceiling == 750.0


def test_load_settings_defaults_the_shipped_config_to_the_frozen_book():
    """The tracked config must stay the FROZEN, path-independent book — the
    basis every recorded conclusion rests on. The compounding ARM lives in its
    own config file, not in this one."""
    assert load_settings().compound_enabled is False


@pytest.mark.parametrize("interval", ["month", "quarter", "year"])
def test_load_settings_accepts_every_documented_interval(tmp_path, interval):
    st = load_settings(_write_cfg(tmp_path, mark_interval=interval))
    assert st.mark_interval == interval


def test_load_settings_rejects_an_unknown_mark_interval(tmp_path):
    with pytest.raises(ConfigError, match="month, quarter, year"):
        load_settings(_write_cfg(tmp_path, mark_interval="fortnight"))


def test_load_settings_treats_a_null_budget_ceiling_as_no_ceiling(tmp_path):
    st = load_settings(_write_cfg(tmp_path, budget_ceiling=None))
    assert st.budget_ceiling is None
    assert sizing_budget(1e9, 0.02, st.budget_ceiling) == pytest.approx(2e7)


@pytest.mark.parametrize("bad", [0, -1, -1_000.0])
def test_load_settings_rejects_a_non_positive_budget_ceiling(tmp_path, bad):
    with pytest.raises(ConfigError, match="budget_ceiling"):
        load_settings(_write_cfg(tmp_path, budget_ceiling=bad))


# ── the CONFIGURATION echo ──────────────────────────────────────────────────

def _config_text(st, capsys, name="config/account-sim.yml") -> str:
    account_sim.print_configuration(st, name)
    return capsys.readouterr().out


def _echoed_file(text: str) -> str:
    """The config file back out of the printed section, dedented.

    The same recovery `scripts/study_charts/report.py` performs, done here
    independently so the two sides cannot drift onto a shared bug.
    """
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith(f"--- {account_sim.CFG_FILE_GROUP} ")) + 1
    end = next(i for i, ln in enumerate(lines[start:], start)
               if ln.startswith("--- "))
    return "\n".join(ln[2:] if ln.startswith("  ") else ln
                     for ln in lines[start:end]).strip("\n")


def test_configuration_echo_prints_the_config_file_itself(capsys):
    """The section IS the file, not a rendering of it.

    A re-worded echo is a second copy of the setup, free to disagree with the
    file — and a knob added to account-sim.yml would be silently outside what
    the report (and so the charts page, which quotes it) shows. Every line of
    the file must come back out of the printed section unchanged.
    """
    st = load_settings()
    echoed = _echoed_file(_config_text(st, capsys))
    on_disk = account_sim.DEFAULT_CONFIG.read_text()
    for line in on_disk.splitlines():
        assert line.rstrip() in echoed.splitlines(), f"line dropped from the echo: {line!r}"
    # And it is still the same YAML: the report's indent-and-rstrip cannot have
    # re-nested a key or eaten a value.
    assert yaml.safe_load(echoed) == yaml.safe_load(on_disk)


def test_configuration_echo_prints_the_bytes_that_were_parsed(tmp_path, capsys):
    """`source_text` comes off the same read `load_settings` parsed, so a
    --config run cannot show one file and simulate another."""
    path = _write_cfg(tmp_path, enabled=True, mark_interval="quarter")
    st = load_settings(path)
    assert st.source_text == path.read_text()
    echoed = _echoed_file(_config_text(st, capsys, name=str(path)))
    assert yaml.safe_load(echoed) == yaml.safe_load(path.read_text())
    assert "enabled: true" in echoed


def test_configuration_echo_prints_the_exit_policy_the_replay_will_apply(capsys):
    """The stop levels are read out of `profile_for`, not re-typed. A study that
    printed its own copy could describe exits the harness never ran."""
    text = _config_text(make_settings(), capsys)
    debit = account_sim.profile_for(
        dict(credit=False, structure="bull_call_spread", mech_cell="LVOL"))
    credit = account_sim.profile_for(
        dict(credit=True, structure="bull_put_spread", mech_cell="LVOL"))
    assert f"take profit {debit['pt']:+.0%}" in text
    assert f"stop {-debit['sl']:+.0%}" in text
    assert f"time exit at {debit['tef']:.0%} of DTE" in text
    assert f"take profit {credit['pt']:+.0%}" in text
    # the bear-debit ratchet and the BEAR_HE trail are separate rows
    assert f"breakeven ratchet once peak {account_sim.SHIPPED_BE_AFTER:+.0%}" in text
    assert "trail 50% once +50% is touched" in text


def test_configuration_echo_names_the_config_file_it_was_handed(capsys):
    """A --config run must describe itself, not the default file."""
    text = _config_text(make_settings(), capsys, name="config/my-account.yml")
    assert "CONFIGURATION — the account this run simulated (config/my-account.yml)" in text


def test_configuration_echo_resolves_the_dollar_stop_the_file_states_as_a_rate(capsys):
    """The file gives risk as a fraction; what stops a position out is dollars.

    It is the one resolved figure the section prints, so it must be the run's
    own arithmetic — a reader should not have to do the multiplication, and a
    stale hand-typed figure is exactly what would go unnoticed.
    """
    text = _config_text(make_settings(capital=60_000.0, risk_pct=0.03), capsys)
    assert "hard dollar stop at $1,800" in text


def test_configuration_echo_marks_the_dollar_stop_as_initial_under_compounding(capsys):
    """Compounding re-marks the stop, so printing it bare would contradict the
    `enabled: true` in the file printed directly above it."""
    off = _config_text(make_settings(), capsys)
    assert "hard dollar stop at $500 " in off and "re-marked" not in off
    on = _config_text(make_settings(compound_enabled=True, mark_interval="quarter"), capsys)
    assert "initial — re-marked each quarter" in on


def test_settings_cfg_threads_the_compounding_block_into_every_simulation():
    """`Settings.cfg()` is the single construction point, so an arm cannot be
    switched on for one simulation in the report and off for another by
    accident — only an explicit keyword (which `run_gates` uses to pin G1-G4
    to the frozen basis) may override it."""
    st = make_settings(compound_enabled=True, mark_interval="quarter",
                       budget_ceiling=750.0)
    cfg = st.cfg("arm")
    assert (cfg.compound, cfg.mark_interval, cfg.budget_ceiling) == \
        (True, "quarter", 750.0)
    assert st.cfg("gate basis", compound=False).compound is False
    # ...and the frozen settings never hand out a compounding cfg.
    assert make_settings().cfg("frozen").compound is False


def test_settings_cfg_carries_settings_values_with_overrides_winning():
    st = make_settings()
    cfg = st.cfg("mylabel")
    assert cfg.label == "mylabel"
    assert (cfg.capital, cfg.per_pos_cap, cfg.net_cap, cfg.risk_pct,
            cfg.max_per_day, cfg.hedge_risk_fraction) == (
        st.capital, st.per_pos_cap, st.net_cap, st.risk_pct, st.max_per_day,
        st.hedge_risk_fraction)

    overridden = st.cfg("other", capital=99_000.0, downsize=True)
    assert overridden.label == "other"
    assert overridden.capital == 99_000.0
    assert overridden.downsize is True
    # an untouched knob still comes from the settings.
    assert overridden.net_cap == st.net_cap


# ── module holds no rebindable state ─────────────────────────────────────────

def _day_rec(signal: date, mlpc=200.0, delta=0.05, contracts=1):
    # A small delta-notional per contract (0.05 x 100 x $50 = $250) keeps this
    # comfortably inside every cap tried below, at either cfg's contract count
    # — this fixture is about statelessness, not admission edge cases.
    n = _grid_len(signal=signal)
    row = _hand_trade([2.40] * n, contracts=contracts, signal=signal)
    row["entry_underlying"] = "50"
    return {"t": Trade(row), "credit": False, "structure": "long_call",
            "mech_cell": "PROD", "max_loss_per_contract": mlpc,
            "delta": delta, "date": signal.isoformat(), "ticker": "TEST"}


def _tiny_day_lists():
    d1, d2 = date(2025, 1, 6), date(2025, 1, 13)
    return [(d1.isoformat(), [_day_rec(d1)]), (d2.isoformat(), [_day_rec(d2)])]


def test_module_holds_no_rebindable_globals():
    assert not hasattr(account_sim, "ARM")
    assert not hasattr(account_sim, "_MEMO")


def test_simulate_with_one_cfg_is_unaffected_by_an_intervening_run():
    day_lists = _tiny_day_lists()
    cfg_a = _cfg(label="A", capital=25_000.0, risk_pct=0.02)
    cfg_b = _cfg(label="B", capital=50_000.0, risk_pct=0.04)

    sig_a1 = book_signature(simulate(day_lists, cfg_a))
    simulate(day_lists, cfg_b)                     # an unrelated run in between
    sig_a2 = book_signature(simulate(day_lists, cfg_a))

    assert sig_a1 and sig_a1 == sig_a2


def test_new_cache_returns_a_fresh_empty_dict_each_call():
    a, b = new_cache(), new_cache()
    assert a == {} and b == {}
    assert a is not b


def test_replay_sized_with_separate_caches_yields_equal_results_without_sharing():
    n = _grid_len()
    marks = [2.40] * n
    rec = {"t": Trade(_hand_trade(marks, 1)), "credit": False,
           "structure": "long_call", "mech_cell": "PROD",
           "max_loss_per_contract": 200.0, "delta": 0.5}
    prof = dict(pt=None, sl=None, trig=None, trail=None, tef=None)

    cache1, cache2 = new_cache(), new_cache()
    a = replay_sized(rec, 1, 500.0, profile=prof, cache=cache1)
    b = replay_sized(rec, 1, 500.0, profile=prof, cache=cache2)
    assert a == b
    assert cache1 and cache2 and cache1 is not cache2

    cache1[("sentinel", "poison")] = "leaked"
    assert ("sentinel", "poison") not in cache2
