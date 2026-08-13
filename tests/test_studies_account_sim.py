"""Tests for the $25k account-simulation study's pure machinery.

No CSV, no book, no Sheets export: every test builds its own dicts (and one
hand-made `Trade`) so the properties pinned here are the ones the study's
conclusions rest on —

  * the ledger accounting identity (G3) actually detects a leak,
  * the dollar-stop SCALING IDENTITY is exact (replaying at contracts x 2 under
    the frozen $1,000 harness stop is a $500 stop at the true size, and halving
    the dollars recovers the true P&L),
  * cap admission attributes a breach to exactly ONE constraint (A4), and
  * the ARM D downsize solves for the largest integer that fits every cap.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_study.account_sim import (  # noqa: E402
    Cfg, Ledger, admission, dense_episodes, replay_sized, risk_contracts,
    sessions_between, signed_dn, solve_contracts,
)
from scripts.backtest_study.harness import MAX_LOSS_ABS, Trade  # noqa: E402


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

def _hand_trade(marks, contracts, entry=2.00, dte=30):
    """A one-leg long call whose marks are exactly the weekday grid."""
    signal = date(2025, 1, 6)              # Monday
    exp = signal + timedelta(days=dte)
    row = {
        "signal_date": signal.isoformat(), "ticker": "TEST",
        "structure": "long_call", "contracts": str(contracts),
        "dte_entry": str(dte), "entry_option_price": str(entry),
        "legs": f"TEST:{exp.isoformat()}:100:C +1",
        "daily_price_csv": ",".join(str(m) for m in marks),
    }
    return row


def _grid_len(dte=30):
    signal = date(2025, 1, 6)
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

def _cfg(**kw):
    return Cfg(label="t", capital=25_000.0, per_pos_cap=0.25, net_cap=1.50, **kw)


def _cfg_pp(per_pos: float):
    return Cfg(label="t", capital=25_000.0, per_pos_cap=per_pos, net_cap=1.50)


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
    cfg = Cfg(label="t", capital=25_000.0, per_pos_cap=float("inf"),
              net_cap=float("inf"), enforce_cash=False)
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


# ── population helpers ──────────────────────────────────────────────────────

def test_sessions_between_counts_weekdays_only():
    assert sessions_between("2025-01-06", "2025-01-07") == 1      # Mon -> Tue
    assert sessions_between("2025-01-03", "2025-01-06") == 1      # Fri -> Mon
    assert sessions_between("2025-01-06", "2025-01-06") == 0


def test_dense_episodes_splits_on_a_gap_and_drops_short_runs():
    run_a = [f"2025-03-{d:02d}" for d in range(3, 15)]     # 12 weekday-ish dates
    run_b = ["2025-06-02", "2025-06-03"]                   # too short
    eps = dense_episodes(run_a + run_b)
    assert len(eps) == 1 and eps[0][0] == run_a[0]
    assert len(eps[0]) == len(run_a)


def test_dense_episodes_keeps_a_run_across_a_five_session_gap():
    dates = ["2025-03-03", "2025-03-10"]                   # 5 sessions apart
    assert sessions_between(*dates) == 5
    dates += [f"2025-03-{d}" for d in range(11, 21)]
    eps = dense_episodes(dates)
    assert len(eps) == 1 and len(eps[0]) == 12
