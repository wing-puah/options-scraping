"""`scripts/backtest_study/lib/pbo.py` — CSCV and PBO (Bailey, Borwein,
López de Prado, Zhu 2017). Synthetic matrices only: a null case, a signal
case, determinism, the metrics, and input validation."""
from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.backtest_study.lib import pbo


def _noise(T=320, N=40, seed=7):
    return np.random.default_rng(seed).normal(0.0, 1.0, size=(T, N))


def test_pure_noise_configurations_give_pbo_near_one_half():
    # Columns are iid noise: the IS winner is a random column OOS, so its
    # relative rank is uniform and PBO is about 0.5. Averaged over seeds to keep
    # the test about the estimator, not one draw.
    vals = [pbo.cscv(_noise(seed=s), S=10).pbo for s in range(8)]
    assert 0.35 < float(np.mean(vals)) < 0.65


def test_one_dominant_configuration_gives_pbo_near_zero():
    M = _noise(seed=3)
    M[:, 5] += 0.8          # a real edge in every period
    res = pbo.cscv(M, S=10)
    assert res.pbo < 0.02
    assert res.selection_share()[5] > 0.95
    assert res.prob_loss == 0.0


def test_combination_count_is_the_binomial_coefficient():
    res = pbo.cscv(_noise(T=160, N=6), S=16)
    assert res.n_combinations == math.comb(16, 8) == 12870
    assert res.logits.shape == (12870,)


def test_deterministic():
    M = _noise(T=120, N=8)
    a, b = pbo.cscv(M, S=8), pbo.cscv(M, S=8)
    assert a.pbo == b.pbo
    assert np.array_equal(a.logits, b.logits)
    assert np.array_equal(a.n_star, b.n_star)


def test_logit_is_the_log_odds_of_rank_over_n_plus_one():
    M = _noise(T=40, N=4)
    res = pbo.cscv(M, S=4, keep_ranks=True)
    for i in range(res.n_combinations):
        r = res.oos_rank[i, res.n_star[i]]
        w = r / (res.n_configs + 1)
        assert res.omega[i] == pytest.approx(w)
        assert res.logits[i] == pytest.approx(math.log(w / (1 - w)))
    assert res.pbo == pytest.approx(np.mean(res.logits <= 0))


def test_training_set_is_joined_in_original_order():
    # A drawdown depends on order. Column 0 rises then falls; joining blocks
    # in time order must see the fall after the rise.
    M = np.zeros((4, 2))
    M[:, 0] = [1.0, 1.0, -3.0, 0.0]
    assert pbo.max_drawdown(M)[0] == pytest.approx(3.0)
    assert pbo.max_drawdown(M[[0, 2]])[0] == pytest.approx(3.0)
    assert pbo.max_drawdown(M[[2, 0]])[0] == pytest.approx(3.0)  # peak seeded at 0
    assert pbo.max_drawdown(np.array([[2.0], [-1.0]]))[0] == pytest.approx(1.0)


def test_ratio_metric_and_ties():
    sub = np.zeros((2, 3, 2))
    sub[:, 0] = [[1.0, 1], [3.0, 1]]     # mean 2
    sub[:, 1] = [[4.0, 2], [0.0, 0]]     # mean 2
    # column 2 has no positions -> NaN, ranked worst
    out = pbo.ratio_metric(sub)
    assert out[0] == pytest.approx(2.0) and out[1] == pytest.approx(2.0)
    assert math.isnan(out[2])
    assert list(pbo.avg_rank(out)) == [2.5, 2.5, 1.0]


def test_report_metric_drives_loss_and_degradation():
    M = _noise(T=80, N=5)
    res = pbo.cscv(M, S=8, metric=pbo.neg_drawdown_metric,
                   report_metric=pbo.total_metric)
    assert res.prob_loss is not None and 0.0 <= res.prob_loss <= 1.0
    assert np.isfinite(res.slope)


def test_pad_head_adds_zero_rows_only_when_needed():
    M = np.ones((10, 3))
    out, k = pbo.pad_head(M, 4)
    assert k == 2 and out.shape == (12, 3) and out[:2].sum() == 0
    same, k0 = pbo.pad_head(np.ones((12, 3)), 4)
    assert k0 == 0 and same.shape == (12, 3)


@pytest.mark.parametrize("M,S,msg", [
    (np.zeros((16, 1)), 4, "at least 2"),
    (np.zeros((16, 3)), 3, "even"),
    (np.zeros((16, 3)), 0, "even"),
    (np.zeros((15, 3)), 4, "divisible"),
    (np.zeros((2, 3)), 4, "cannot form"),
    (np.zeros(16), 4, "shape"),
    (np.full((16, 3), np.nan), 4, "non-finite"),
])
def test_input_validation(M, S, msg):
    with pytest.raises(ValueError, match=msg):
        pbo.cscv(M, S=S)


def test_metric_shape_is_checked():
    with pytest.raises(ValueError, match="length"):
        pbo.cscv(np.zeros((8, 3)), S=4, metric=lambda sub: np.zeros(2))


# ── pbo_ledger: the configuration sets ───────────────────────────────────────

def test_ledger_sets_nest_and_f3_enters_only_the_last():
    from scripts.backtest_study.f4_deployment import pbo_ledger as PL
    trials = PL.ledger()
    sets = {name: {t.key for t in trials if t.in_set(name)} for name in PL.SETS}
    base, tc, f3 = (sets[n] for n in PL.SETS)
    assert base < tc < f3
    assert not any(k.startswith("TC_") for k in base)
    assert f3 - tc == {"F3LO_150", "F3LO_250", "F3HI_150", "F3HI_250"}
    for t in trials:
        if t.f3:
            assert t.over["floor"] == "narrow" and not t.ticker_cap
    assert not any("F3" in what for what, _why in PL.NOT_REPRODUCED)


def test_f3_trial_cfg_matches_narrow_to_fit_cells():
    # The F3 trial must be the cell narrow_to_fit graded: narrow floor, take
    # floor on, $500 = 2% and $1,000 = 4% of $25k, no separate dollar stop.
    from scripts.backtest_study.f4_deployment import pbo_ledger as PL
    by_key = {t.key: t for t in PL.ledger()}
    lo, hi = by_key["F3LO_150"], by_key["F3HI_250"]
    assert PL.BASE["capital"] * lo.over["risk_pct"] == 500.0
    assert PL.BASE["capital"] * hi.over["risk_pct"] == 1000.0
    assert (lo.over["net_cap"], hi.over["net_cap"]) == (1.50, 2.50)
    assert "take_floor" not in lo.over and "stop_abs" not in lo.over
