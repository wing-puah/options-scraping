"""direction_hit (research/pre-registrations/f1_selection/signal/direction_hit.md):
the hit's signal-date close, the walk-forward's training cut, the permutation
design, the verdict grammar and the floors, on synthetic data only.

No figure here comes from an export: each test builds its own rows.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from scripts.backtest_study.f1_selection.signal import direction_hit as D
from scripts.backtest_study.lib.underlying import SRC_TILDE, Bar


def _bars(start: date, closes, source="ohlc"):
    return {start + timedelta(days=i): Bar(c=c, source=source) for i, c in enumerate(closes)}


# ── the target: no lookahead past the signal-date close ─────────────────────

def test_hit_starts_from_the_signal_date_close_not_a_later_bar():
    d0 = date(2025, 1, 6)
    bars = _bars(d0, [100.0, 90.0, 95.0])         # signal 100, next day 90, exit 95
    hit, ret, why = D.hit_of(bars, d0, d0 + timedelta(days=2), +1)
    assert why is None and hit == 0 and ret == pytest.approx(-0.05)
    # measured from the next bar it would have been a hit; it must not be
    hit_bear, _, _ = D.hit_of(bars, d0, d0 + timedelta(days=2), -1)
    assert hit_bear == 1


def test_a_weekend_signal_uses_the_prior_close_never_the_next():
    fri = date(2025, 1, 3)
    bars = {fri: Bar(c=100.0), fri + timedelta(days=3): Bar(c=80.0),
            fri + timedelta(days=4): Bar(c=104.0)}
    hit, ret, _ = D.hit_of(bars, fri + timedelta(days=1), fri + timedelta(days=4), +1)
    assert hit == 1 and ret == pytest.approx(0.04)


def test_hit_refuses_stale_or_missing_bars_and_split_artifacts():
    d0 = date(2025, 1, 6)
    bars = _bars(d0, [100.0, 101.0])
    assert D.hit_of(bars, d0 + timedelta(days=30), d0 + timedelta(days=31), 1)[2] == "no_signal_bar"
    assert D.hit_of(bars, d0, d0, 1)[2] == "no_exit_bar"               # exit not after signal
    assert D.hit_of(bars, d0, d0 + timedelta(days=20), 1)[2] == "no_exit_bar"
    tilde = _bars(d0, [100.0, 10.0], source=SRC_TILDE)
    assert D.hit_of(tilde, d0, d0 + timedelta(days=1), 1)[2] == "split_artifact"
    assert D.hit_of(_bars(d0, [100.0, 10.0]), d0, d0 + timedelta(days=1), 1)[2] is None


def test_zero_move_is_a_miss():
    d0 = date(2025, 1, 6)
    assert D.hit_of(_bars(d0, [100.0, 100.0]), d0, d0 + timedelta(days=1), 1)[0] == 0


def test_own_return_and_sma_use_no_bar_after_the_signal():
    d0 = date(2025, 1, 1)
    closes = [100.0 + i for i in range(60)]
    bars = _bars(d0, closes)
    sig = d0 + timedelta(days=55)
    r, g = D.own_return(bars, sig), D.own_sma_gap(bars, sig)
    bars[sig + timedelta(days=1)] = Bar(c=10_000.0)               # a wild later bar
    assert D.own_return(bars, sig) == r and D.own_sma_gap(bars, sig) == g
    assert r == pytest.approx(closes[55] / closes[35] - 1)


def test_own_return_refuses_a_sparse_series():
    d0 = date(2025, 1, 1)
    bars = {d0 + timedelta(days=3 * i): Bar(c=100.0 + i) for i in range(30)}
    assert D.own_return(bars, d0 + timedelta(days=87)) is None    # 21 bars span 60 days


# ── alignment ────────────────────────────────────────────────────────────────

def test_alignment_signs():
    assert D.align("F15", 0.05, -1) == pytest.approx(-0.05)
    assert D.align("F11", 0.10, +1) == pytest.approx(-0.10)       # skew is bearish news
    assert D.align("F9", 0.70, -1) == pytest.approx(-0.20)
    assert D.align("F4", -1.0, -1) == 1.0 and D.align("F4", 1.0, -1) == 0.0
    assert D.align("F1", "BULL", +1) == "agrees" and D.align("F1", "BULL", -1) == "opposes"
    assert D.align("F1", "RANGE", -1) == "RANGE" and D.align("F1", None, 1) is None
    assert D.align("F6", 22.0, -1) == 22.0                         # not directional


# ── permutation design ───────────────────────────────────────────────────────

def test_within_date_shuffle_never_leaves_the_date():
    dc = np.array([0, 0, 0, 1, 1, 2, 3, 3, 3, 3])
    rng = np.random.default_rng(1)
    for _ in range(50):
        idx = D.shuffle_within_date(dc, rng)
        assert (dc[idx] == dc).all()


def test_across_dates_shuffle_keeps_one_value_per_date():
    dc = np.array([0, 0, 1, 1, 1, 2, 3])
    rng = np.random.default_rng(2)
    seen = set()
    for _ in range(50):
        idx = D.shuffle_across_dates(dc, rng)
        for code in range(4):
            assert len(set(dc[idx][dc == code])) == 1
        seen.add(tuple(idx))
    assert len(seen) > 1


def _rows(n_dates=40, per=4, signal=True, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n_dates):
        d = (date(2024, 1, 2) + timedelta(days=i * 3)).isoformat()
        for j in range(per):
            x = float(rng.normal())
            hit = int(x > 0) if signal else int(rng.random() > 0.5)
            out.append(dict(date=d, exit=(date.fromisoformat(d) + timedelta(days=10)).isoformat(),
                            direction=1, tier="A", hit=hit, hit10=hit, ret=0.01,
                            base={f: None for f in D.FEATURE_IDS} | {"F7": x, "F13": 30.0}))
    return out


def test_screen_finds_a_planted_row_feature_and_not_a_null_one():
    rows = _rows(signal=True)
    lift, p, n = D.screen_feature(rows, "F7", n_perm=200)
    assert lift > 0.5 and p < 0.02 and n == len(rows)
    lift0, p0, _ = D.screen_feature(_rows(signal=False, seed=3), "F7", n_perm=200)
    assert p0 > 0.05


# ── walk-forward: no future rows ─────────────────────────────────────────────

def test_training_mask_needs_signal_and_exit_before_the_cutoff():
    rows = [dict(date="2025-01-10", exit="2025-01-20"), dict(date="2025-01-25", exit="2025-02-03"),
            dict(date="2025-02-01", exit="2025-02-05")]
    assert D.training_mask(rows, "2025-02-01").tolist() == [True, False, False]


def test_walk_forward_never_trains_on_a_row_unknown_at_the_fold(monkeypatch):
    rows = []
    d0 = date(2024, 1, 2)
    for i in range(400):
        d = d0 + timedelta(days=2 * i)
        rows.append(dict(date=d.isoformat(), exit=(d + timedelta(days=45)).isoformat(),
                         direction=1, tier="A", hit=i % 2, hit10=i % 2, ret=0.0,
                         base={f: None for f in D.FEATURE_IDS}))
    seen = []

    def spy(train, test, fids, C, target="hit"):
        cutoff = min(r["date"] for r in test)
        m0 = D.month_start(cutoff)
        assert all(r["date"] < m0 and r["exit"] < m0 for r in train)
        assert all(r["date"] >= m0 for r in test)
        seen.append(len(train))
        return np.full(len(test), 0.5)

    monkeypatch.setattr(D, "fit_predict", spy)
    wf = D.walk_forward(rows, D.FEATURE_IDS)
    assert seen and wf["first"] == D.add_months("2024-01-01", D.WARMUP_MONTHS)
    assert min(wf["dates"]) >= wf["first"]


def test_walk_forward_skips_a_month_with_too_few_training_rows(monkeypatch):
    rows = [dict(date=(date(2024, 1, 2) + timedelta(days=7 * i)).isoformat(),
                 exit=(date(2024, 1, 3) + timedelta(days=7 * i)).isoformat(), direction=1,
                 tier="A", hit=i % 2, hit10=i % 2, ret=0.0, base={f: None for f in D.FEATURE_IDS})
            for i in range(40)]
    monkeypatch.setattr(D, "fit_predict", lambda *a, **k: pytest.fail("no fold has 100 rows"))
    wf = D.walk_forward(rows, D.FEATURE_IDS)
    assert wf["skipped"] == wf["months"] and len(wf["p"]) == 0


# ── grading ──────────────────────────────────────────────────────────────────

def test_auc_hand_computed_with_a_tie():
    assert D.auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)
    assert D.auc([0, 1], [0.5, 0.5]) == pytest.approx(0.5)
    assert math.isnan(D.auc([1, 1], [0.2, 0.3]))


@pytest.mark.parametrize("lo,v3,want", [
    (0.51, 0.55, D.PREDICTS),
    (0.51, 0.50, D.WEAK),          # v3 must be above 0.5, not at it
    (0.51, float("nan"), D.WEAK),
    (0.50, 0.90, D.NULL),          # the CI must clear 0.5
    (0.40, 0.90, D.NULL),
    (float("nan"), 0.9, D.NULL),
])
def test_verdict_grammar(lo, v3, want):
    assert D.verdict(lo, v3) == want


def test_forward_floors():
    assert D.forward_token(29, 500, 0.6) == "STILL-OPEN"
    assert D.forward_token(30, 99, 0.6) == "STILL-OPEN"
    assert D.forward_token(30, 100, 0.6) == "CONFIRMED"
    assert D.forward_token(30, 100, 0.5) == "NOT-CONFIRMED"


def test_subset_grid_is_sixteen_configs_over_the_four_groups():
    cfgs = D.subset_configs()
    assert len(cfgs) == 16 and cfgs[0] == ("intercept", ())
    full = [f for name, f in cfgs if name.count("+") == 3][0]
    assert set(full) == set(D.FEATURE_IDS)


def test_design_uses_training_statistics_only():
    tr = [dict(direction=1, date="2025-01-01", base={f: None for f in D.FEATURE_IDS} | {"F7": v})
          for v in (1.0, 2.0, 3.0)]
    te = [dict(direction=1, date="2025-02-01", base={f: None for f in D.FEATURE_IDS} | {"F7": 100.0})]
    Xtr, Xte = D.design(tr, te, ("F7",))
    assert Xtr[:, 0].mean() == pytest.approx(0.0)
    assert Xte[0, 0] == pytest.approx((100.0 - 2.0) / np.std([1.0, 2.0, 3.0]))
