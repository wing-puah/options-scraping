"""Regression tests for the `ladder_tier()` verified-delta path.

`ladder_tier(structure, market_regime, dte_proxy, short_leg_delta)` gained a
4th, optional parameter so `scripts/journal/` (a real-delta daily pipeline)
can evaluate the bull_put_spread Tier-B clause in
`config/deployment-rules.md` §3 for real — ``0.08 <= |delta| <= 0.20`` AND
``DTE <= 59`` — instead of the DTE-only PARTIAL proxy `stage1_map_fills.py`
is stuck with (no delta on the analysis row).

These tests pin the new path; `tests/test_live_loop.py` (untouched) pins that
omitting `short_leg_delta` stays byte-identical to the original PARTIAL
behaviour.
"""

import numpy as np

# mapping.py has no import-time side effects (unlike stage1_map_fills.py,
# which resolves an IBKR snapshot path at import time) -- a plain import is
# safe here.
from live_loop.mapping import ladder_tier


def test_delta_too_low_is_tier_c():
    tier, partial, reason = ladder_tier(
        "bull_put_spread", "BULL + C-VOL", dte_proxy=50, short_leg_delta=0.07)
    assert tier == "C"
    assert partial is False
    assert "0.07" in reason


def test_delta_and_dte_both_pass_is_tier_b_not_partial():
    tier, partial, reason = ladder_tier(
        "bull_put_spread", "BULL + C-VOL", dte_proxy=50, short_leg_delta=0.14)
    assert tier == "B"
    assert partial is False
    assert "0.14" in reason


def test_delta_too_high_is_tier_c():
    tier, partial, reason = ladder_tier(
        "bull_put_spread", "BULL + C-VOL", dte_proxy=50, short_leg_delta=0.21)
    assert tier == "C"
    assert partial is False
    assert "0.21" in reason


def test_dte_too_long_fails_even_with_good_delta():
    tier, partial, reason = ladder_tier(
        "bull_put_spread", "BULL + C-VOL", dte_proxy=90, short_leg_delta=0.14)
    assert tier == "C"
    assert partial is False
    assert "90" in reason
    assert "0.14" in reason


def test_nan_dte_with_known_delta_is_tier_c_and_partial():
    """DTE unknown must never be silently treated as passing."""
    tier, partial, reason = ladder_tier(
        "bull_put_spread", "BULL + C-VOL", dte_proxy=np.nan, short_leg_delta=0.14)
    assert tier == "C"
    assert partial is True
    assert "0.14" in reason


def test_omitting_delta_reproduces_old_partial_behaviour():
    tier, partial, reason = ladder_tier(
        "bull_put_spread", "BULL + C-VOL", dte_proxy=50)
    assert tier == "B"
    assert partial is True
    assert "UNVERIFIED" in reason

    tier, partial, reason = ladder_tier(
        "bull_put_spread", "BULL + C-VOL", dte_proxy=90)
    assert tier == "C"
    assert partial is True
    assert "UNVERIFIED" in reason
