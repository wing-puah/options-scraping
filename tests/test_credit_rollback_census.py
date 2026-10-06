"""Pins the row filter of the credit sl-none rollback trigger.

Registration: research/pre-registrations/f2_management/rollback_triggers.md,
trigger 4 — "fresh window" = bull_put rows signal-dated AFTER 2026-07-13,
floor 15 rows. The census lives in
exit_mechanism_study.py::credit_rollback_census; this test feeds it a
synthetic book and checks which rows it counts, so a drift in the filter
(the ship date itself admitted, another credit structure admitted, the floor
moved) fails here rather than silently changing the census.
"""
from datetime import date, timedelta

from scripts.backtest_study.f2_management import exit_mechanism_study as ems


class _T:
    def __init__(self, structure, d, pnl=0.1):
        self.structure = structure
        self.signal_date = d
        self.pnl = pnl

    def dollars(self, pl):
        return pl * 100


def _fake_replay(t, sl=None, **_):
    return {"pnl_pct": t.pnl if sl is None else t.pnl - 0.05,
            "exit_reason": "x", "days_held": 1}


def _run(monkeypatch, capsys, trades):
    monkeypatch.setattr(ems, "replay", _fake_replay)
    monkeypatch.setattr(ems.triggers, "affected", lambda *a, **k: ([], []))
    ems.credit_rollback_census(trades)
    return capsys.readouterr().out


def test_fresh_filter_is_bull_put_strictly_after_ship_date(monkeypatch, capsys):
    ship = date(2026, 7, 13)
    assert ems.ATTEMPT13_SHIP == ship
    book = [
        _T("bull_put_spread", ship),                        # ship date: NOT fresh
        _T("bull_put_spread", ship - timedelta(days=30)),   # pre-window
        _T("bear_call_spread", ship + timedelta(days=3)),   # fresh date, wrong structure
        _T("bull_put_spread", ship + timedelta(days=1)),    # fresh
        _T("bull_put_spread", ship + timedelta(days=1)),    # fresh, same date
        _T("bull_put_spread", ship + timedelta(days=9)),    # fresh
    ]
    out = _run(monkeypatch, capsys, book)
    assert "fresh bull_put rows (signal_date > 2026-07-13): 3" in out
    assert "n_rows=3  n_dates=2  floor=15 rows  -> UNDERPOWERED" in out
    assert "fresh window (n=" not in out          # no reading below the floor


def test_floor_is_fifteen_rows_and_reading_follows(monkeypatch, capsys):
    d = date(2026, 8, 1)
    out = _run(monkeypatch, capsys, [_T("bull_put_spread", d) for _ in range(15)])
    assert "n_rows=15  n_dates=1  floor=15 rows  -> FLOOR MET" in out
    assert "fresh window (n=15)" in out
    assert "Δ$=-75" in out                         # sl-1x variant replayed, not PROD twice
