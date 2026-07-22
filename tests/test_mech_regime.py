"""Mechanical regime labels + the debit-only exit override they key."""

import csv

import pytest

from lib.mech_regime import MechLabeler, cell_for_date, compute_mech_table
from scripts.backtest.simulate import _effective_sim_cfg, _exit_basis, _MECH_LABELERS


def _write_series(tmp_path, spy, vix, start_index=0):
    """SPY/VIX table with sequential fake trading dates (2024-01-01 + n days)."""
    from datetime import date, timedelta
    p = tmp_path / "spy_vix.csv"
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "spy_close", "vix_close"])
        d0 = date(2024, 1, 1)
        for i, (s, v) in enumerate(zip(spy, vix)):
            w.writerow([(d0 + timedelta(days=i + start_index)).isoformat(), s, v])
    return p


def test_no_label_before_sma_lookback(tmp_path):
    """Fewer than 50 closes → dir_ok False, and callers must get no override."""
    p = _write_series(tmp_path, [400.0] * 30, [15.0] * 30)
    lab = MechLabeler.from_csv(p)
    direction, vol, ok, _ = lab.label("2024-01-25")
    assert (direction, vol, ok) == (None, None, False)
    assert lab.cell("2024-01-25") is None


def test_bear_high_vol_cell(tmp_path):
    """Falling SPY under its 50-SMA with VIX >= 20 → BEAR_HE."""
    spy = [500.0] * 50 + [500.0 - 2 * i for i in range(1, 31)]
    vix = [15.0] * 50 + [22.0] * 30
    lab = MechLabeler.from_csv(_write_series(tmp_path, spy, vix))
    assert lab.cell("2024-03-20") == "BEAR_HE"


def test_vix_spike_is_evol_even_below_30(tmp_path):
    """5-day VIX change >= +25% is E-VOL regardless of level."""
    spy = [500.0] * 50 + [500.0 - 2 * i for i in range(1, 11)]
    vix = [15.0] * 55 + [21.0] * 5
    lab = MechLabeler.from_csv(_write_series(tmp_path, spy, vix))
    direction, vol, ok, _ = lab.label("2024-02-28")
    assert ok and vol == "E-VOL"


def test_rows_without_spy_close_are_dropped(tmp_path):
    """A VIX-only trailing row must not shift the rolling windows."""
    p = tmp_path / "s.csv"
    p.write_text("date,spy_close,vix_close\n2024-01-01,400,15\n2024-01-02,,16\n")
    table = compute_mech_table(p)
    assert [r["date"] for r in table] == ["2024-01-01"]


def test_asof_uses_most_recent_prior_trading_day(tmp_path):
    spy = [500.0] * 50 + [500.0 - 2 * i for i in range(1, 11)]
    vix = [25.0] * 60
    lab = MechLabeler.from_csv(_write_series(tmp_path, spy, vix))
    # A weekend/holiday date maps back to the last labelled day.
    assert lab.cell("2024-06-01") == lab.cell(lab.last_date)


# ── the exit override ────────────────────────────────────────────────────────

BASE = {
    "profit_target": 0.90,
    "stop_loss": 0.75,
    "trailing_stop_trigger": None,
    "trailing_stop_pct": None,
    "time_exit_dte_fraction": 0.75,
    "credit": {"profit_target": 0.65, "stop_loss": None,
               "time_exit_dte_fraction": None},
}


@pytest.fixture
def bear_cfg(tmp_path):
    spy = [500.0] * 50 + [500.0 - 2 * i for i in range(1, 31)]
    vix = [15.0] * 50 + [22.0] * 30
    p = _write_series(tmp_path, spy, vix)
    _MECH_LABELERS.clear()
    cfg = {**BASE, "regime_exit": {
        "enabled": True, "spy_vix_csv": str(p),
        "cells": {"BEAR_HE": {"trailing_stop_trigger": 0.50,
                              "trailing_stop_pct": 0.50}},
    }}
    yield cfg
    _MECH_LABELERS.clear()


def test_debit_in_bear_he_gets_the_trail(bear_cfg):
    eff = _effective_sim_cfg(bear_cfg, entry_net=2.50, signal_date="2024-03-20")
    assert eff["trailing_stop_trigger"] == 0.50
    assert eff["trailing_stop_pct"] == 0.50
    # Unnamed keys keep their PROD values.
    assert eff["profit_target"] == 0.90
    assert eff["time_exit_dte_fraction"] == 0.75


def test_debit_outside_the_cell_is_untouched(bear_cfg):
    """Early dates have no 50-SMA lookback → PROD, no trail."""
    eff = _effective_sim_cfg(bear_cfg, entry_net=2.50, signal_date="2024-01-10")
    assert eff["trailing_stop_trigger"] is None
    assert eff["trailing_stop_pct"] is None


def test_credit_is_never_regime_switched(bear_cfg):
    """Same BEAR_HE date, credit position — credit block wins, no trail."""
    eff = _effective_sim_cfg(bear_cfg, entry_net=-1.20, signal_date="2024-03-20")
    assert eff["profit_target"] == 0.65
    assert eff["stop_loss"] is None
    assert eff["trailing_stop_trigger"] is None


def test_disabled_flag_is_a_no_op(bear_cfg):
    bear_cfg["regime_exit"]["enabled"] = False
    eff = _effective_sim_cfg(bear_cfg, entry_net=2.50, signal_date="2024-03-20")
    assert eff["trailing_stop_trigger"] is None


def test_missing_csv_disables_override(bear_cfg, tmp_path):
    bear_cfg["regime_exit"]["spy_vix_csv"] = str(tmp_path / "nope.csv")
    _MECH_LABELERS.clear()
    eff = _effective_sim_cfg(bear_cfg, entry_net=2.50, signal_date="2024-03-20")
    assert eff["trailing_stop_trigger"] is None


def test_no_signal_date_falls_back_to_prod(bear_cfg):
    eff = _effective_sim_cfg(bear_cfg, entry_net=2.50, signal_date=None)
    assert eff["trailing_stop_trigger"] is None


def test_legacy_two_arg_call_still_works(bear_cfg):
    """Callers that predate the regime switch must keep PROD behaviour."""
    eff = _effective_sim_cfg(bear_cfg, 2.50)
    assert eff["trailing_stop_trigger"] is None


# ── exit_basis: the column that makes a pooled read unambiguous ───────────────

def test_exit_basis_names_the_cell_that_fired(bear_cfg):
    assert _exit_basis(bear_cfg, 2.50, "2024-03-20") == "BEAR_HE"


def test_exit_basis_is_prod_outside_the_cell(bear_cfg):
    assert _exit_basis(bear_cfg, 2.50, "2024-01-10") == "PROD"


def test_exit_basis_credit_is_never_a_regime_cell(bear_cfg):
    """Same BEAR_HE date — a credit must report CREDIT, not the cell, because
    the credit block (not the override) governed its exit."""
    assert _exit_basis(bear_cfg, -1.20, "2024-03-20") == "CREDIT"


def test_exit_basis_is_prod_when_override_disabled(bear_cfg):
    bear_cfg["regime_exit"]["enabled"] = False
    assert _exit_basis(bear_cfg, 2.50, "2024-03-20") == "PROD"


def test_exit_basis_agrees_with_the_config_actually_used(bear_cfg):
    """The label must never claim a basis the merge didn't apply."""
    for entry_net, d in [(2.50, "2024-03-20"), (2.50, "2024-01-10"),
                         (-1.20, "2024-03-20")]:
        eff = _effective_sim_cfg(bear_cfg, entry_net, d)
        basis = _exit_basis(bear_cfg, entry_net, d)
        trailed = eff["trailing_stop_trigger"] is not None
        assert trailed == (basis == "BEAR_HE")


def test_exit_basis_in_both_key_orders():
    """Present, and LAST — Sheets append is positional (core.py:45-48)."""
    from scripts.backtest.core import _KEY_ORDER
    from scripts.backtest.proxy import _PROXY_KEY_ORDER
    assert _KEY_ORDER[-1] == "exit_basis"
    assert _PROXY_KEY_ORDER[-1] == "exit_basis"


# ── cell_for_date: the stored-column resolver ────────────────────────────────

def test_cell_for_date_returns_the_cell_and_no_warning(tmp_path):
    spy = [500.0] * 50 + [500.0 - 2 * i for i in range(1, 31)]
    vix = [15.0] * 50 + [22.0] * 30
    p = _write_series(tmp_path, spy, vix)
    assert cell_for_date(p, "2024-03-20") == ("BEAR_HE", None)


def test_cell_for_date_names_the_no_cell_case(tmp_path):
    """Labelled fine, but the regime maps to no override cell — NOT blank, so it
    is distinguishable from a row written before the column existed."""
    spy = [500.0] * 50 + [500.0 + 2 * i for i in range(1, 31)]
    vix = [15.0] * 80
    p = _write_series(tmp_path, spy, vix)
    value, warning = cell_for_date(p, "2024-03-20")
    assert value == "LVOL" and warning is None


def test_cell_for_date_refuses_to_answer_past_the_table_end(tmp_path):
    """The live failure this guards: an as-of lookup would happily label a date
    the table doesn't reach, from a stale close, with no signal that it did."""
    spy = [500.0] * 50 + [500.0 - 2 * i for i in range(1, 31)]
    vix = [15.0] * 50 + [22.0] * 30
    p = _write_series(tmp_path, spy, vix)
    # Same series, one day past the last row.
    assert MechLabeler.from_csv(p).cell("2029-01-01") == "BEAR_HE"  # as-of, silent
    value, warning = cell_for_date(p, "2029-01-01")
    assert value == "NO_DATA"
    assert "refresh" in warning


def test_cell_for_date_missing_table_is_no_data_not_a_crash(tmp_path):
    value, warning = cell_for_date(tmp_path / "absent.csv", "2024-03-20")
    assert value == "NO_DATA" and "not found" in warning


def test_mech_cell_is_last_in_the_analysis_row_schema():
    """Sheets append is positional — a new column must go at the very end or
    every existing tab row misaligns."""
    from scripts.analysis_pipeline.config import ROW_COLUMNS
    assert ROW_COLUMNS[-1] == "mech_cell"


def test_mech_cell_is_on_every_row_including_market():
    """Market-level value, unlike the per-ticker blocks that blank on MARKET."""
    from scripts.analysis_pipeline.core import analysis_to_rows
    analysis = {"regime": "BEAR", "plays": [{"ticker": "NVDA", "structure": "bull_call"}]}
    rows = analysis_to_rows(analysis, "2024-03-20", "2024-03-14", "2024-03-20",
                            mech_cell="BEAR_HE")
    assert [r["ticker"] for r in rows] == ["MARKET", "NVDA"]
    assert all(r["mech_cell"] == "BEAR_HE" for r in rows)


def test_in_progress_day_is_not_labelled(tmp_path):
    """Real case hit on 2026-07-22: VIX had printed but SPY hadn't closed, so the
    table's last row has a VIX and no SPY. That row is dropped, and the date must
    come back NO_DATA rather than labelled off a partial bar."""
    p = tmp_path / "s.csv"
    rows = ["date,spy_close,vix_close"]
    from datetime import date, timedelta
    d0 = date(2024, 1, 1)
    for i in range(80):
        rows.append(f"{(d0 + timedelta(days=i)).isoformat()},{500.0 - i},15.0")
    today = (d0 + timedelta(days=80)).isoformat()
    rows.append(f"{today},,17.5")          # VIX only — market still open
    p.write_text("\n".join(rows) + "\n")

    assert [r["date"] for r in compute_mech_table(p)][-1] != today
    value, warning = cell_for_date(p, today)
    assert value == "NO_DATA" and "ends" in warning
