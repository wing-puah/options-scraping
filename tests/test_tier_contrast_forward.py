"""Mechanics tests for `tier_contrast_forward`, on SYNTHETIC rows only.

Each test names the one-step mutation it must fail under
(research/pre-registrations/f4_deployment/tier_contrast_forward.md,
Required mechanics tests). No test reads an export or writes the real
look log or stored read: both go to tmp_path.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pytest

from scripts.backtest_study.f4_deployment import tier_contrast_forward as T
from scripts.backtest_study.lib import book


def day(i: int) -> str:
    return (date(2026, 12, 1) + timedelta(days=i)).isoformat()


def mk(d, tier, R, pending=False, source="real", key=None):
    return dict(date=d, tier=tier, arm=T.arm_of(tier), R=R, R_capped=None,
                pending=pending, source=source, key=key or f"{d}|{tier}|{R}|{id(object())}")


def book_rows(n_dates=130, per_arm=4, effect=0.0, spread=1.0, seed=1):
    """Closed rows: `per_arm` AB and `per_arm` C rows on each of `n_dates` dates."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_dates):
        for j in range(per_arm):
            rows.append(mk(day(i), "A" if j % 2 else "B", effect + spread * rng.standard_normal(),
                           key=f"{day(i)}|AB|{j}"))
            rows.append(mk(day(i), "C", spread * rng.standard_normal(), key=f"{day(i)}|C|{j}"))
    return rows


SMALL = dict(boot_n=300, calib_n=20, perm_n=300)


def test_registered_constants():
    assert (T.START, T.SUNSET, T.MIN_POS, T.MIN_DATES) == ("2026-11-28", "2028-11-27", 377, 120)
    assert (T.BOOT_N, T.CALIB_N, T.PERM_N, T.CALIB_BOUND) == (10_000, 500, 10_000, 0.075)
    assert (T.SIGMA, T.DE, T.REF_EFFECT, T.STUDY_ERA) == (1.0, 1.5, 0.25, "v4")
    assert T.FORWARD_JSON.name == "tier_contrast_forward-forward-read.json"
    assert T.LOOKS_JSONL.name == "tier_contrast_forward-looks.jsonl"


# Mutation: the module recomputes the tier from score fields.
def test_tier_comes_from_ladder_tier(monkeypatch):
    calls = []

    def fake(structure, regime, dte_proxy=float("nan"), short_leg_delta=None):
        calls.append((structure, regime, dte_proxy, short_leg_delta))
        return "B", False, "fake"
    monkeypatch.setattr(book.mapping, "ladder_tier", fake)
    rec = dict(structure="long_call", market_regime="BEAR H-VOL", dte=30, delta=0.4,
               score_total=1, score_flow=0, date="2026-12-01", R=0.1, source="real", ticker="X")
    assert T.tier_of(rec) == "B"
    assert calls == [("long_call", "BEAR H-VOL", 30, 0.4)]
    assert T.row_of(rec)["tier"] == "B"


# Mutation: the date filter becomes `>= 2026-11-27`, or is removed.
def test_rows_dated_on_or_before_2026_11_27_are_out():
    rows = [mk("2026-11-26", "A", 1.0), mk("2026-11-27", "A", 1.0), mk("2026-11-28", "C", 0.0)]
    assert [r["date"] for r in T.forward_rows(rows)] == ["2026-11-28"]


# Mutation: the bootstrap resamples rows instead of dates.
def test_bootstrap_resamples_dates():
    rows = []
    for j in range(50):
        rows += [mk(day(0), "A", 1.0), mk(day(0), "C", 0.0),
                 mk(day(1), "A", 0.0), mk(day(1), "C", 1.0)]
    draws = T.boot_draws(rows, n=2000, seed=3)
    # Two dates: half the draws pick one date twice, so the contrast is exactly +-1.
    assert np.mean(np.isclose(np.abs(draws), 1.0)) > 0.35
    assert np.std(draws) > 0.5


# Mutation: the contrast is computed as C minus AB.
def test_sign_of_the_contrast_on_a_planted_ab_effect():
    rows = book_rows(n_dates=40, effect=0.5, spread=0.2)
    assert T.contrast(rows) == pytest.approx(0.5, abs=0.1)
    assert np.median(T.boot_draws(rows, n=500)) > 0.3


# Mutation: the floor check uses `>` 376 on rows only, or drops the date floor.
def test_floor_376_positions_or_119_dates_stays_open():
    assert not T.floors_met(376, 200)
    assert not T.floors_met(377, 119)
    assert T.floors_met(377, 120)
    # 119 dates x 4 AB rows = 476 positions: rows clear the floor, dates do not.
    rows = book_rows(n_dates=119, per_arm=4)
    prefix, _ = T.complete_prefix(rows)
    assert T.find_dstar(rows, prefix) is None


def test_floors_unmet_prints_counts_only_and_still_open(tmp_path, capsys):
    rows = book_rows(n_dates=119, per_arm=4)
    fwd, looks = tmp_path / "fwd.json", tmp_path / "looks.jsonl"
    tok = T.run(rows, "2026-12-30", forward_path=fwd, looks_path=looks,
                cache_fn=lambda: {"n_files": 1}, **SMALL)
    out = capsys.readouterr().out
    bare = out.replace("tier_contrast_forward", "")
    assert tok == T.STILL_OPEN and ">>> tier_contrast_forward STILL-OPEN <<<" in out
    assert "contrast" not in bare and "mean" not in bare.lower()
    assert not fwd.exists()
    look = json.loads(looks.read_text().splitlines()[-1])
    assert look["token"] == T.STILL_OPEN and look["counts"]["AB"] == [476, 119]


def test_lapsed_after_sunset_with_nothing_pending(tmp_path):
    rows = book_rows(n_dates=10)
    tok = T.run(rows, "2028-11-28", forward_path=tmp_path / "f.json",
                looks_path=tmp_path / "l.jsonl")
    assert tok == T.LAPSED
    assert T.open_token("2027-05-01", False, True) == T.LAPSED
    assert T.open_token("2027-05-01", False, False) == T.STILL_OPEN


# Mutation: D* is the run date's prefix end.
def test_dstar_is_the_earliest_prefix_date_meeting_the_floors():
    rows = book_rows(n_dates=200, per_arm=4)
    prefix, _ = T.complete_prefix(rows)
    assert prefix[-1] == day(199)
    assert T.find_dstar(rows, prefix) == day(119)


# Mutation: pending rows are dropped and later dates still count.
def test_a_pending_row_ends_the_prefix():
    rows = book_rows(n_dates=200, per_arm=4)
    rows.append(mk(day(50), "C", None, pending=True))
    prefix, stall = T.complete_prefix(rows)
    assert stall == day(50) and prefix[-1] == day(49)
    assert T.find_dstar(rows, prefix) is None


# Mutation: the calibration shuffle runs across the whole window.
def test_calibration_shuffles_within_date():
    rows = ([mk(day(0), "A", 1.0) for _ in range(5)] + [mk(day(1), "C", 0.0) for _ in range(5)]
            + [mk(day(2), "B", 0.3), mk(day(2), "C", 0.1), mk(day(2), "C", 0.2)])
    rng = np.random.default_rng(0)
    for _ in range(20):
        labels = T.shuffle_within_date(rows, rng)
        assert labels[:10] == ["AB"] * 5 + ["C"] * 5
        assert sorted(labels[10:]) == ["AB", "C", "C"]


# Mutation: a tripped G2 refuses, or keeps the bootstrap p-value.
def test_g2_fallback_grades_by_permutation_p(monkeypatch):
    rows = book_rows(n_dates=30, per_arm=2, effect=0.2)
    monkeypatch.setattr(T, "calibration_rate", lambda *a, **k: 0.2)
    monkeypatch.setattr(T, "permutation_p", lambda *a, **k: 0.5)
    figs = T.grade(rows, day(29), True, {"n_files": 1}, **SMALL)
    assert figs["token"] != T.REFUSED
    assert figs["p_source"].startswith("permutation") and figs["p"] == 0.5


# Mutation: the realized MDE comes from the frozen sigma.
def test_realized_mde_comes_from_the_bootstrap_se():
    draws = np.array([0.1, -0.2, 0.4, 0.0, 0.3])
    assert T.realized_mde(draws) == pytest.approx(2.80 * np.std(draws, ddof=1))
    rows = book_rows(n_dates=30, per_arm=2, spread=5.0)
    figs = T.grade(rows, day(29), True, {"n_files": 1}, **SMALL)
    assert figs["realized_mde"] > 3 * figs["planning_mde"]
    assert figs["realized_mde"] == pytest.approx(
        T.realized_mde(T.boot_draws(rows, SMALL["boot_n"])))


# Mutation: the refused run prints the contrast.
def test_a_refused_run_prints_no_contrast(tmp_path, capsys):
    rows = book_rows(n_dates=125, per_arm=4, effect=0.5)
    fwd, looks = tmp_path / "fwd.json", tmp_path / "looks.jsonl"
    tok = T.run(rows, "2027-09-01", forward_path=fwd, looks_path=looks,
                cache_fn=lambda: None, **SMALL)
    out = capsys.readouterr().out.replace("tier_contrast_forward", "")
    assert tok == T.REFUSED and "G4" in out
    assert "contrast" not in out and " p " not in out and "MDE" not in out
    assert not fwd.exists()
    assert "contrast" not in looks.read_text()


# Mutation: the second run recomputes from the export.
def test_one_shot_second_run_prints_the_stored_read(tmp_path, capsys, monkeypatch):
    fwd, looks = tmp_path / "fwd.json", tmp_path / "looks.jsonl"
    rows = book_rows(n_dates=125, per_arm=4, effect=0.5, spread=0.5)
    tok1 = T.run(rows, "2027-09-01", forward_path=fwd, looks_path=looks,
                 cache_fn=lambda: {"n_files": 1}, **SMALL)
    assert tok1 == T.SELECTS and fwd.exists()
    stored = fwd.read_text()
    capsys.readouterr()
    flipped = [dict(r, R=-r["R"]) for r in rows]

    def boom(*a, **k):
        raise AssertionError("regraded")
    monkeypatch.setattr(T, "grade", boom)
    tok2 = T.run(flipped, "2027-10-01", forward_path=fwd, looks_path=looks,
                 cache_fn=lambda: {"n_files": 1}, **SMALL)
    out = capsys.readouterr().out
    assert tok2 == tok1 and "stored read" in out and fwd.read_text() == stored
    assert [json.loads(x)["token"] for x in looks.read_text().splitlines()] == [tok1, tok1]


# Mutation: vetoed rows join arm C.
def test_vetoed_rows_are_in_neither_arm():
    rows = [mk(day(0), "A", 1.0), mk(day(0), "C", 0.0), mk(day(0), "VETO", -5.0),
            mk(day(0), "B", 0.5, source="tweak")]
    primary, proxy, census = T.split_rows(rows)
    assert [r["tier"] for r in primary] == ["A", "C"]
    assert [r["tier"] for r in proxy] == ["B"]
    assert census["tier_VETO"] == 1
    assert T.arm_of("VETO") is None
    assert T.contrast(primary) == pytest.approx(1.0)
