"""Tests for the pure, outcome-blind capital-adequacy module
(`scripts/backtest_study/lib/capital_adequacy.py`), step 0c of
`research/account-sim-feasibility-plan.md`.

Every input here is synthetic — no figure is taken from any export. What is
pinned:

  * `None`/non-positive costs are excluded from every statistic AND counted,
    never treated as zero;
  * the fit test's EPS boundary (`cost == budget` fits) matches
    `account_sim.py`'s own convention;
  * the adequacy curve is monotonically non-decreasing in capital;
  * the target-share lookups (ladder-smallest and exact) behave correctly,
    including on an empty population;
  * `format_block()` renders without error and carries the required
    disclosure language.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from scripts.backtest_study.lib.capital_adequacy import (  # noqa: E402
    EPS, adequacy_curve, cost_census, format_block,
)


# ── cost_census ──────────────────────────────────────────────────────────────

def test_cost_census_empty():
    c = cost_census([])
    assert c.n_total == 0
    assert c.n_excluded == 0
    assert c.overall is None


def test_cost_census_excludes_none_and_nonpositive_and_counts_them():
    costs = [100.0, None, 0.0, -5.0, 300.0]
    c = cost_census(costs)
    assert c.n_total == 5
    assert c.n_excluded == 3          # None, 0.0, -5.0
    assert c.overall.n == 2
    assert c.overall.min == 100.0
    assert c.overall.max == 300.0


def test_cost_census_none_never_treated_as_zero():
    # A population of [None, None] must NOT read as two zero-cost plays: the
    # overall census must be None (no usable cost), not a stats block full of
    # zeros.
    c = cost_census([None, None])
    assert c.overall is None
    assert c.n_excluded == 2


def test_cost_census_quartiles_median_p90_on_known_values():
    # 1..9: median 5, Q1 3, Q3 7 under linear interpolation.
    # p90: idx = 0.9 * 8 = 7.2 -> between sorted[7]=8 and sorted[8]=9 -> 8.2.
    costs = [float(v) for v in range(1, 10)]
    c = cost_census(costs)
    s = c.overall
    assert s.n == 9
    assert s.min == 1.0
    assert s.max == 9.0
    assert s.median == 5.0
    assert s.q1 == 3.0
    assert s.q3 == 7.0
    assert abs(s.p90 - 8.2) < 1e-9


def test_cost_census_single_value():
    c = cost_census([42.0])
    s = c.overall
    assert (s.min, s.q1, s.median, s.q3, s.p90, s.max) == (42.0, 42.0, 42.0, 42.0, 42.0, 42.0)


def test_cost_census_by_group_splits_and_counts_excluded_per_group():
    costs = [100.0, 200.0, None, 50.0, -1.0]
    groups = ["A", "A", "A", "B", "B"]
    c = cost_census(costs, groups=groups)
    assert c.n_total == 5
    assert c.n_excluded == 2
    assert c.by_group["A"].n == 2
    assert c.by_group["A"].min == 100.0
    assert c.excluded_by_group["A"] == 1
    assert c.by_group["B"].n == 1
    assert c.by_group["B"].min == 50.0
    assert c.excluded_by_group["B"] == 1


def test_cost_census_group_with_no_usable_cost_still_reported():
    costs = [None, -5.0]
    groups = ["C", "C"]
    c = cost_census(costs, groups=groups)
    assert c.by_group["C"] is None
    assert c.excluded_by_group["C"] == 2


def test_cost_census_groups_length_mismatch_raises():
    import pytest
    with pytest.raises(ValueError):
        cost_census([1.0, 2.0], groups=["A"])


# ── adequacy_curve: fit-test boundary ───────────────────────────────────────

def test_fit_boundary_cost_equal_budget_fits():
    # cost == capital * risk_pct exactly -> must fit (<=, not <), mirroring
    # account_sim.py's admission()/risk_contracts() convention.
    curve = adequacy_curve([500.0], capitals=[25_000.0], risk_pct=0.02, target_shares=())
    rung = curve.ladder[0]
    assert rung.budget == 500.0
    assert rung.n_fit == 1
    assert rung.share == 1.0


def test_fit_boundary_cost_just_over_budget_excluded_beyond_eps():
    # A cost that exceeds the budget by more than EPS must NOT fit.
    curve = adequacy_curve([500.0 + 1e-6], capitals=[25_000.0], risk_pct=0.02,
                           target_shares=())
    assert curve.ladder[0].n_fit == 0
    assert curve.ladder[0].share == 0.0


def test_fit_boundary_within_eps_still_fits():
    curve = adequacy_curve([500.0 + EPS / 2], capitals=[25_000.0], risk_pct=0.02,
                           target_shares=())
    assert curve.ladder[0].n_fit == 1


# ── adequacy_curve: general behaviour ───────────────────────────────────────

def test_adequacy_curve_empty_plays_returns_none_everywhere():
    curve = adequacy_curve([], capitals=[25_000.0, 50_000.0], risk_pct=0.02,
                           target_shares=(0.5, 0.9))
    assert curve.n_total == 0
    assert curve.n_usable == 0
    for rung in curve.ladder:
        assert rung.share is None
        assert rung.n_fit == 0
    assert curve.smallest_capital_for_target[0.5] is None
    assert curve.smallest_capital_for_target[0.9] is None
    assert curve.exact_capital_for_target[0.5] is None
    assert curve.exact_capital_for_target[0.9] is None


def test_adequacy_curve_all_unusable_returns_none_shares():
    curve = adequacy_curve([None, -1.0, 0.0], capitals=[25_000.0], risk_pct=0.02,
                           target_shares=(0.5,))
    assert curve.n_usable == 0
    assert curve.n_excluded == 3
    assert curve.ladder[0].share is None
    assert curve.smallest_capital_for_target[0.5] is None
    assert curve.exact_capital_for_target[0.5] is None


def test_adequacy_curve_share_is_decimal_fraction_not_percent():
    costs = [100.0, 100.0, 100.0, 100.0]
    curve = adequacy_curve(costs, capitals=[10_000.0], risk_pct=0.02, target_shares=())
    # budget = 200, all four fit
    assert curve.ladder[0].share == 1.0
    assert 0.0 <= curve.ladder[0].share <= 1.0


def test_adequacy_curve_excludes_unusable_from_denominator():
    # 2 usable at 100, 2 excluded. At a budget of 200 both usable plays fit,
    # so the share is over the 2 usable plays (1.0), not over all 4 (0.5).
    costs = [100.0, 100.0, None, -5.0]
    curve = adequacy_curve(costs, capitals=[10_000.0], risk_pct=0.02, target_shares=())
    assert curve.n_usable == 2
    assert curve.n_excluded == 2
    assert curve.ladder[0].share == 1.0


def test_adequacy_curve_monotonic_in_capital():
    costs = [50.0, 150.0, 400.0, 900.0, 2500.0]
    capitals = [5_000.0, 10_000.0, 25_000.0, 50_000.0, 100_000.0, 250_000.0]
    curve = adequacy_curve(costs, capitals=capitals, risk_pct=0.02, target_shares=())
    shares = [r.share for r in curve.ladder]
    assert all(a <= b + 1e-12 for a, b in zip(shares, shares[1:]))
    # Highest capital in the ladder affords everything here.
    assert shares[-1] == 1.0


def test_adequacy_curve_preserves_caller_supplied_ladder_order():
    costs = [100.0]
    capitals = [50_000.0, 25_000.0, 100_000.0]
    curve = adequacy_curve(costs, capitals=capitals, risk_pct=0.02, target_shares=())
    assert [r.capital for r in curve.ladder] == capitals


def test_adequacy_curve_smallest_capital_for_target():
    # costs: one at 100 (fits at budget>=100 i.e. capital>=5000 @2%),
    #        one at 1000 (fits at capital>=50000 @2%).
    costs = [100.0, 1000.0]
    capitals = [5_000.0, 25_000.0, 50_000.0, 100_000.0]
    curve = adequacy_curve(costs, capitals=capitals, risk_pct=0.02,
                           target_shares=(0.5, 1.0))
    assert curve.smallest_capital_for_target[0.5] == 5_000.0
    assert curve.smallest_capital_for_target[1.0] == 50_000.0


def test_adequacy_curve_smallest_capital_for_target_never_reached():
    costs = [10_000.0]
    capitals = [1_000.0, 2_000.0]
    curve = adequacy_curve(costs, capitals=capitals, risk_pct=0.02, target_shares=(1.0,))
    assert curve.smallest_capital_for_target[1.0] is None


def test_adequacy_curve_exact_capital_actually_reaches_the_target_share():
    """The claim the line makes is the property under test — not the formula.

    The previous version asserted `exact_capital` == the interpolated quantile
    over risk_pct, which is the implementation compared with itself; it passed
    while the capital it named bought 89.9% of a 90% target (444 plays). This
    asserts what a reader takes off the line: at that capital the share is AT
    OR ABOVE the target, and no cheaper usable play's capital gets there.
    """
    risk_pct = 0.02
    for n in range(2, 61):
        # A spread of costs with deliberate TIES — ties are what make the
        # achieved share jump past the target rather than land on it.
        costs = [float(50 * (1 + (i // 2))) for i in range(n)]
        curve = adequacy_curve(costs, capitals=[], risk_pct=risk_pct,
                               target_shares=(0.5, 0.75, 0.9))
        usable = sorted(costs)
        for t in (0.5, 0.75, 0.9):
            cap = curve.exact_capital_for_target[t]
            assert cap is not None
            budget = cap * risk_pct
            n_fit = sum(1 for c in usable if c <= budget + EPS)
            assert n_fit / n >= t - 1e-12, (
                f"n={n} t={t}: capital ${cap:,.0f} reaches only {n_fit}/{n}")
            # And the module says so: the printed share is the achieved one.
            assert curve.exact_share_for_target[t] == pytest.approx(n_fit / n)
            # Minimality: the largest cost STRICTLY below this budget is the
            # best any cheaper capital could do, and it must fall short.
            lower = [c for c in usable if c < budget - EPS]
            if lower:
                b = max(lower)
                got = sum(1 for x in usable if x <= b + EPS)
                assert got / n < t - 1e-12, (
                    f"n={n} t={t}: ${b / risk_pct:,.0f} already reaches "
                    f"{got}/{n}, so ${cap:,.0f} is not the smallest")


def test_adequacy_curve_exact_capital_is_an_order_statistic_not_an_interpolation():
    """1..10 at 2%: the 5th smallest cost ($5) is the smallest budget that
    covers 5 of 10. The interpolated median ($5.50) also covers 5 of 10 — it
    is simply not the smallest capital that does, which is what the line
    claims."""
    costs = [float(v) for v in range(1, 11)]
    curve = adequacy_curve(costs, capitals=[], risk_pct=0.02,
                           target_shares=(0.5,))
    assert curve.exact_capital_for_target[0.5] == pytest.approx(5.0 / 0.02)
    assert curve.exact_share_for_target[0.5] == pytest.approx(0.5)


def test_adequacy_curve_exact_capital_is_independent_of_ladder():
    costs = [50.0, 150.0, 400.0]
    curve_a = adequacy_curve(costs, capitals=[1_000.0], risk_pct=0.02, target_shares=(0.5,))
    curve_b = adequacy_curve(costs, capitals=[999_999.0], risk_pct=0.02, target_shares=(0.5,))
    assert curve_a.exact_capital_for_target[0.5] == curve_b.exact_capital_for_target[0.5]


def test_adequacy_curve_rejects_nonpositive_risk_pct():
    import pytest
    with pytest.raises(ValueError):
        adequacy_curve([100.0], capitals=[1_000.0], risk_pct=0.0, target_shares=())


# ── format_block ─────────────────────────────────────────────────────────────

def test_format_block_states_outcome_blind_and_disclosure():
    census = cost_census([100.0, 200.0, None])
    curve = adequacy_curve([100.0, 200.0, None], capitals=[25_000.0, 50_000.0],
                           risk_pct=0.02, target_shares=(0.5, 0.9))
    lines = format_block(census, curve, label="PRIMARY")
    text = "\n".join(lines)
    assert "outcome-blind" in text.lower()
    assert "disclosure" in text.lower() or "DISCLOSURE" in text
    assert "not a criterion" in text.lower()
    assert "[PRIMARY]" in text


def test_format_block_handles_empty_population_without_error():
    census = cost_census([])
    curve = adequacy_curve([], capitals=[25_000.0], risk_pct=0.02, target_shares=(0.5,))
    lines = format_block(census, curve)
    assert isinstance(lines, list)
    assert any("no cost census to report" in line for line in lines)


def test_format_block_lists_group_rows():
    costs = [100.0, 200.0, None]
    groups = ["bull_call_spread", "bull_call_spread", "bull_put_spread"]
    census = cost_census(costs, groups=groups)
    curve = adequacy_curve(costs, capitals=[25_000.0], risk_pct=0.02, target_shares=())
    lines = format_block(census, curve)
    text = "\n".join(lines)
    assert "bull_call_spread" in text
    assert "bull_put_spread" in text
