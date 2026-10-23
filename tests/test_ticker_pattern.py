"""ticker_pattern — the scoring, permutation and verdict mechanics on synthetic books.

No export is read here. Registration:
research/pre-registrations/f1_selection/benchmark/ticker_pattern.md.
"""
from __future__ import annotations

import itertools
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from scripts.backtest_study.f1_selection.benchmark import ticker_class as TC
from scripts.backtest_study.f1_selection.benchmark import ticker_pattern as TP
from scripts.backtest_study.lib import pbo as PBO


def _row(name: int, d: str, R: float, direction: str = "bull", side: str = "debit") -> dict:
    return dict(name=name, ticker=TP.TEN[name], date=d, week=TP.iso_week(d), month=d[:7],
                dir=direction, side=side, credit=side == "credit", R=float(R),
                structure="bull_call_spread", source="real", path="complete")


def _weekly_book(n_weeks: int, effect: float, seed: int, names=range(5)) -> list[dict]:
    """One row per name per week, all bull debits, R ~ N(0, 1) + effect on name 0."""
    rng = np.random.default_rng(seed)
    start = date(2025, 1, 6)                   # a Monday
    rows = []
    for w in range(n_weeks):
        d = (start + timedelta(weeks=w)).isoformat()
        for j in names:
            rows.append(_row(j, d, rng.normal() + (effect if j == 0 else 0.0)))
    return rows


# ── scores ─────────────────────────────────────────────────────────────────

def test_scores_sum_to_zero_per_stratum_and_ties_get_midranks():
    codes = np.array([0, 0, 0, 1, 1])
    vals = np.array([1.0, 1.0, 3.0, 5.0, 2.0])
    a = TP.stratum_scores(codes, vals)
    # stratum 0: ranks 1.5, 1.5, 3 over n_s = 3 -> /4 - 0.5
    assert a[:3] == pytest.approx([1.5 / 4 - 0.5, 1.5 / 4 - 0.5, 3 / 4 - 0.5])
    # stratum 1: 5.0 ranks 2, 2.0 ranks 1, n_s = 2 -> /3 - 0.5
    assert a[3:] == pytest.approx([2 / 3 - 0.5, 1 / 3 - 0.5])
    rng = np.random.default_rng(1)
    codes = np.sort(rng.integers(0, 12, 200))
    vals = rng.integers(0, 5, 200).astype(float)          # heavy ties
    a = TP.stratum_scores(codes, vals)
    for c in np.unique(codes):
        assert a[codes == c].sum() == pytest.approx(0.0, abs=1e-12)


def test_single_name_strata_are_dropped():
    rows = [_row(0, "2025-01-06", 1.0), _row(0, "2025-01-07", 2.0),          # one name only
            _row(0, "2025-01-13", 1.0), _row(1, "2025-01-14", 2.0)]          # two names
    d = TP.build_design(rows, TP.KEY_PRIMARY[1])
    assert d.n_graded == 4 and d.n_inf == 2
    assert d.n_strata == 2 and d.n_inf_strata == 1
    assert {r["week"] for r in d.rows} == {TP.iso_week("2025-01-13")}


# ── the permutation p ──────────────────────────────────────────────────────

def _toy():
    """3 strata x 3 rows, at least two names in each, one tie."""
    codes = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
    labels = np.array([0, 1, 2, 0, 0, 1, 1, 2, 2])
    R = np.array([1.0, 2.0, 3.0, 5.0, 1.0, 3.0, 2.0, 2.0, 7.0])
    return codes, labels, R


def test_monte_carlo_p_matches_exact_enumeration():
    codes, labels, R = _toy()
    a = TP.stratum_scores(codes, R)
    n_t = np.bincount(labels, minlength=TP.N_NAMES)
    T_obs = TP.t_stat(TP.name_sums(labels, a), n_t)
    blocks = [np.flatnonzero(codes == c) for c in range(3)]
    Ts = []
    for perms in itertools.product(*(itertools.permutations(b) for b in blocks)):
        lp = labels.copy()
        for b, p in zip(blocks, perms):
            lp[b] = labels[list(p)]
        Ts.append(TP.t_stat(TP.name_sums(lp, a), n_t))
    Ts = np.array(Ts)
    assert len(Ts) == 216
    exact = float(np.mean(Ts >= T_obs - 1e-9))
    draws = TP.perm_draws(codes, labels, a, 20000, np.random.default_rng(TP.SEED))[0]
    mc = TP.perm_p(T_obs, TP.t_stat(draws, n_t))
    assert abs(mc - exact) < 0.015, (mc, exact)


def test_permutation_keeps_every_label_inside_its_stratum():
    codes, labels, R = _toy()
    rng = np.random.default_rng(3)
    base = codes.astype(float)
    for _ in range(50):
        perm = np.argsort(base + rng.random(len(codes)))
        assert (codes[perm] == codes).all()


def test_planted_effect_is_detected_with_its_sign():
    d = TP.build_design(_weekly_book(40, effect=1.0, seed=7), TP.KEY_PRIMARY[1])
    res = TP.omnibus(d, n_perm=2000)
    assert res["p"] < 0.05
    assert res["S"][0] > 0
    assert res["p_t"][0] < 0.05


def test_null_labels_do_not_reject_at_a_fixed_seed():
    d = TP.build_design(_weekly_book(40, effect=0.0, seed=11), TP.KEY_PRIMARY[1])
    assert TP.omnibus(d, n_perm=2000)["p"] > 0.05


def test_same_seed_same_p():
    d = TP.build_design(_weekly_book(20, effect=0.3, seed=5), TP.KEY_PRIMARY[1])
    a, b = TP.omnibus(d, n_perm=1000), TP.omnibus(d, n_perm=1000)
    assert a["p"] == b["p"] and (a["p_t"] == b["p_t"]).all()


def test_planted_power_gate_runs_and_finds_a_large_plant():
    d = TP.build_design(_weekly_book(40, effect=0.0, seed=13), TP.KEY_PRIMARY[1])
    assert TP.planted_power(d, target=0, plant=1.5, sims=20, perms=200) >= 0.9


# ── halves, PBO cells, verdicts ────────────────────────────────────────────

def test_halves_split_on_week_boundaries():
    weeks = [TP.iso_week((date(2025, 1, 6) + timedelta(days=k)).isoformat()) for k in range(0, 70, 2)]
    h1, h2 = TP.split_halves(weeks)
    assert not (h1 & h2) and (h1 | h2) == set(weeks)
    assert max(h1) < min(h2)
    assert len(h1) == len(set(weeks)) // 2


def test_blank_pbo_months_stay_blank():
    rows = [_row(0, "2025-01-06", 1.0), _row(1, "2025-01-07", 2.0),
            _row(0, "2025-02-03", 1.0), _row(2, "2025-02-04", 0.5)]
    d = TP.build_design(rows, TP.KEY_PRIMARY[1])
    M = TP.pbo_matrix(d, ["2025-01", "2025-02", "2025-03"])
    assert (M[0, 2] == 0).all() and (M[1, 1] == 0).all() and (M[2] == 0).all()
    assert M[0, 0, 1] == 1 and M[1, 2, 1] == 1
    stat = PBO.ratio_metric(M[2:3])
    assert np.isnan(stat).all()                         # a blank block ranks worst, never zero


def test_verdict_order():
    assert TP.p1_verdict(["GP0"], 0.9, 0.0001)[0] == "UNDERPOWERED"
    assert TP.p1_verdict(["GP2"], 0.1, 0.0001)[0] == "UNDERPOWERED"
    tok, note = TP.p1_verdict([], 0.9, 0.0001)
    assert tok == "NULL" and "veto" in note
    assert TP.p1_verdict([], float("nan"), 0.0001)[0] == "NULL"
    assert TP.p1_verdict([], 0.1, 0.5)[0] == "NULL"
    assert TP.p1_verdict([], 0.1, 0.05) == ("TICKER-EFFECT", "")
    assert TP.p1_verdict([], 0.4, 0.01) == ("TICKER-EFFECT", "selection fragile")


def test_flag_status_needs_every_clause():
    ok = dict(graded=True, floor_ok=True, adj_p=0.01, n_h=(20, 20), s_h=(1.0, 2.0),
              s_full=3.0, s_real=1.0)
    assert TP.flag_status(**ok) == "FLAGGED"
    assert TP.flag_status(**{**ok, "graded": False}) == "not graded"
    assert TP.flag_status(**{**ok, "n_h": (14, 30)}) == "NOT REPLICABLE"
    assert TP.flag_status(**{**ok, "adj_p": 0.05}).startswith("NOT FLAGGED")
    assert TP.flag_status(**{**ok, "s_h": (-1.0, 2.0)}).startswith("NOT FLAGGED")
    assert TP.flag_status(**{**ok, "s_real": -0.5}).startswith("NOT FLAGGED")
    assert TP.flag_status(**{**ok, "floor_ok": False}).startswith("NOT FLAGGED")


def test_lag_classes():
    assert TP.lag_class("2026-03-02 10:00:00", "2026-03-02") == "LIVE"
    assert TP.lag_class("2026-03-03 10:00:00", "2026-03-02") == "LIVE"
    assert TP.lag_class("2026-03-09 10:00:00", "2026-03-02") == "NEAR"
    assert TP.lag_class("2026-03-10 10:00:00", "2026-03-02") == "RETRO"
    assert TP.lag_class("", "2026-03-02") == "UNKNOWN"
    assert TP.lag_class(None, "2026-03-02") == "UNKNOWN"
    assert TP.lag_class(float("nan"), "2026-03-02") == "UNKNOWN"
    assert TP.lag_class("2026-03-01 10:00:00", "2026-03-02") == "UNKNOWN"


def test_median_n_name_is_the_lower_median():
    n_t = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    assert TP.median_n_name(n_t) == 4                   # the 5th of 10 by ascending n


# ── fixed constants ────────────────────────────────────────────────────────

def test_the_ten_are_five_etfs_and_five_stocks():
    assert len(TP.ETFS) == 5 and len(TP.STOCKS) == 5
    assert not set(TP.ETFS) & set(TP.STOCKS)
    assert TP.TEN == TP.ETFS + TP.STOCKS and TP.N_NAMES == 10
    etf_groups = {"G1_index", "G2_country", "G3_sector", "G4_noneq"}
    assert all(TC.group_of(t) in etf_groups for t in TP.ETFS)
    assert all(TC.group_of(t) not in etf_groups for t in TP.STOCKS)
    assert not set(TP.NEXT_NAMES) & set(TP.TEN)


def test_constants_equal_ticker_class():
    assert TP.CSCV_S == TC.CSCV_S
    assert TP.PBO_SUPPORT == TC.PBO_SUPPORT
    assert TP.PBO_VETO == TC.PBO_VETO
    assert TP.ALPHA == TC.ALPHA


def test_registered_constants():
    assert (TP.N_PERM, TP.SEED, TP.POWER_SEED) == (20000, 20261023, 20261024)
    assert (TP.MIN_ROWS, TP.MIN_DATES, TP.HALF_MIN_ROWS) == (30, 20, 15)
    assert (TP.GP0_MIN_NAMES, TP.GP0_MIN_NAMES_V3, TP.GP1_MIN_SHARE) == (8, 4, 0.60)
    assert (TP.POWER_SIMS, TP.POWER_PERMS, TP.PLANT_R, TP.POWER_BAR) == (200, 500, 0.50, 0.80)
    assert TP.DESIGNED_REFUSAL_EXIT_CODES == {2, 3}


def test_study_is_not_a_seal_reader():
    src = Path(TP.__file__).read_text()
    assert "sealed_read" not in src
    assert "drop_sealed" in src                         # the analysis join applies the seal itself
