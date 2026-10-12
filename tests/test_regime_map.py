"""regime_map (research/pre-registrations/f1_selection/regime/regime_map.md): the
cell labels, the floors, the BH adjustment, the verdict grammar and the
replication rule, on synthetic data only.

No figure here comes from an export: each test builds its own rows.
"""
from __future__ import annotations

import csv
import math
from datetime import date, timedelta

import pytest

from lib.mech_regime import MechLabeler
from scripts.backtest_study.f1_selection.regime import regime_map as RM


def _table(tmp_path, spy, vix=15.0):
    p = tmp_path / "spy_vix.csv"
    d0 = date(2024, 1, 1)
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "spy_close", "vix_close"])
        for i, s in enumerate(spy):
            w.writerow([(d0 + timedelta(days=i)).isoformat(), s, vix])
    return p, [(d0 + timedelta(days=i)).isoformat() for i in range(len(spy))]


def _row(d, tier="A", R=0.1, labels=None, mfe=0.5, mae=-0.2):
    return dict(date=d, ticker="AAA", structure="bull_call_spread", tier=tier, R=R, Rg=R,
                R_dol=R * 100, mfe=mfe, mae=mae, labels=labels or {})


# ── labels ───────────────────────────────────────────────────────────────────

def test_mech_labels_refuse_a_date_past_the_table(tmp_path):
    p, days = _table(tmp_path, [100.0 + i for i in range(60)])
    lab = MechLabeler.from_csv(p)
    got = RM.mech_labels(lab, days[-1])
    assert got["RM-MDIR"] == "BULL" and got["RM-SMA"] == "above"
    assert got["RM-CELL"] == "LVOL"                      # VIX 15, rising tape
    later = (date.fromisoformat(days[-1]) + timedelta(days=5)).isoformat()
    assert all(v is None for v in RM.mech_labels(lab, later).values())


def test_a_labelled_date_with_no_cell_is_NONE_not_unlabelled(tmp_path):
    # Rising tape with VIX 22: BULL + H-VOL maps to no override cell.
    p, days = _table(tmp_path, [100.0 + i for i in range(60)], vix=22.0)
    lab = MechLabeler.from_csv(p)
    assert RM.mech_labels(lab, days[-1])["RM-CELL"] == "NONE"


def test_prepare_adds_cost_back_for_gross_and_keeps_veto():
    class T:
        row = {"cost_total": "10"}
        denom = 1.0
        contracts = 1

    class Lab:
        def covers(self, d):
            return False

    rec = dict(date="2025-01-02", ticker="AAA", structure="bear_call_spread",
               market_regime="RANGE + L-VOL", dte=30.0, delta=None, R=-0.2,
               fill_trusted=True, mfe=0.1, mae=-0.5, R_dol=-20.0, t=T(),
               model_dir="RANGE", model_vol="L-VOL")
    rows, counts = RM.prepare([rec, dict(rec, R=None)], Lab(), has_cost=True)
    assert counts == {"R_missing": 1}
    assert rows[0]["tier"] == "VETO"
    assert rows[0]["Rg"] == pytest.approx(-0.2 + 10 / 100)
    rows3, _ = RM.prepare([rec], Lab(), has_cost=False)
    assert rows3[0]["Rg"] == rows3[0]["R"]


# ── statistics ───────────────────────────────────────────────────────────────

def test_bh_q_matches_a_hand_computation_and_keeps_nan():
    q = RM.bh_q([0.01, 0.04, 0.03, 0.5, float("nan")])
    assert q[0] == pytest.approx(0.04)
    assert q[1] == pytest.approx(0.04 * 4 / 3)
    assert q[2] == pytest.approx(0.04 * 4 / 3)      # monotone: min(0.06, 0.0533)
    assert q[3] == pytest.approx(0.5)
    assert math.isnan(q[4])


def test_boot_p_is_small_when_every_date_is_positive():
    rows = [_row(f"2025-01-{d:02d}", R=0.2 + 0.01 * d) for d in range(1, 21)]
    _m, draws = RM.boot_draws(rows)
    assert RM.boot_p(draws) < 0.01


# ── verdict grammar and floors ───────────────────────────────────────────────

@pytest.mark.parametrize("n,dates,mean,q,want", [
    (29, 20, 0.5, 0.001, RM.THIN),        # below the position floor
    (40, 9, 0.5, 0.001, RM.THIN),         # below the date floor
    (30, 10, 0.5, 0.001, RM.POSITIVE),
    (30, 10, -0.5, 0.001, RM.NEGATIVE),
    (30, 10, 0.5, 0.05, RM.NULL),         # q at the level is not below it
    (30, 10, 0.5, float("nan"), RM.NULL),
])
def test_verdict_grammar(n, dates, mean, q, want):
    assert RM.verdict(n, dates, mean, q) == want


def test_raw_token_reads_the_ci_alone():
    assert RM.raw_token(30, 10, 0.01, 0.4) == RM.POSITIVE
    assert RM.raw_token(30, 10, -0.4, -0.01) == RM.NEGATIVE
    assert RM.raw_token(30, 10, -0.1, 0.1) == RM.NULL
    assert RM.raw_token(10, 10, 0.1, 0.4) == RM.THIN


@pytest.mark.parametrize("a,b,want", [
    (RM.POSITIVE, RM.POSITIVE, "REPLICATED"),
    (RM.NEGATIVE, RM.NEGATIVE, "REPLICATED"),
    (RM.POSITIVE, RM.NEGATIVE, "CONTRADICTED"),
    (RM.NULL, RM.NULL, "-"),
    (RM.POSITIVE, RM.NULL, "-"),
    (RM.THIN, RM.THIN, "-"),
])
def test_replication_needs_the_same_non_null_token(a, b, want):
    assert RM.replication(a, b) == want


def test_build_map_grades_only_the_four_tiers_past_the_floors():
    lab = {"RM-CELL": "LVOL"}
    big = [_row(f"2025-02-{d:02d}", tier="A", R=0.3 + 0.01 * (d % 3), labels=lab)
           for d in range(1, 13) for _ in range(3)]
    thin = [_row("2025-03-01", tier="B", R=0.5, labels=lab)]
    cells = RM.build_map(big + thin)
    by = {(c["family"], c["tier"], c["level"]): c for c in cells}
    a = by[("RM-CELL", "A", "LVOL")]
    assert a["graded"] and a["verdict"] == RM.POSITIVE and math.isfinite(a["q"])
    assert by[("RM-CELL", "B", "LVOL")]["verdict"] == RM.THIN
    ab = by[("RM-CELL", "A+B", "LVOL")]
    assert not ab["graded"] and math.isnan(ab["q"]) and ab["verdict"] == "(not graded)"
    # a row with no label for a family never enters that family's cells
    assert by[("RM-MDIR", "A", "BULL")]["n"] == 0


def test_cell_stats_give_back_and_capture():
    rows = [_row("2025-01-02", R=0.2, mfe=0.5), _row("2025-01-03", R=-0.1, mfe=0.3),
            _row("2025-01-06", R=-0.4, mfe=-0.05)]
    st = RM.cell_stats(rows)
    assert st["giveback"] == pytest.approx(((0.5 - 0.2) + (0.3 + 0.1) + (-0.05 + 0.4)) / 3)
    assert st["capture"] == pytest.approx((0.2 - 0.1) / (0.5 + 0.3))   # MFE > 0 rows only
    assert st["pf"] == pytest.approx(0.2 / 0.5)


def test_forward_token_is_still_open_below_the_floor():
    assert RM.forward_token([], RM.POSITIVE)[0] == "STILL-OPEN"
    rows = [_row(f"2026-10-{d:02d}", R=0.4) for d in range(1, 13) for _ in range(3)]
    assert RM.forward_token(rows, RM.POSITIVE)[0] == "CONFIRMED"
    assert RM.forward_token(rows, RM.NEGATIVE)[0] == "NOT-CONFIRMED"


def test_stress_windows_are_the_registered_ones():
    assert RM.in_stress("2025-03-01") and RM.in_stress("2026-04-30")
    assert not RM.in_stress("2025-05-01") and not RM.in_stress("2026-01-31")


def test_raw_replication_reads_the_ci_tokens():
    a = dict(family="RM-SMA", tier="B", level="above", raw=RM.POSITIVE, mean=0.1, lo=0.01, hi=0.2)
    b = dict(a, mean=0.2)
    ab = dict(a, tier="A+B")
    got = RM.raw_replication([a, ab], [b, ab])
    assert [r[2] for r in got] == ["REPLICATED"]          # A+B is never graded
