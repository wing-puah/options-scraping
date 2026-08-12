"""Regression tests for the live walk-forward fill mapper.

The bug these exist for (found 2026-08-11 by reading, not by a test): `SIDE`
maps `long_call` and `bull_call_spread` both to `debit`, so the family branch in
`map_entry()` labelled a naked fill against a spread play **STRUCTURE** — pooling
it into the eval as if the emitted play had been traded. A second defect in the
same branch matched on credit/debit only, so a `long_put` fill against a
`bull_call_spread` play (opposite directions, both debit) also passed.

Both are fixed by the `DIRECTION` gate and the `SUBSTITUTED` confidence level.
The tests below pin that behaviour, because the failure mode is silent: a
mislabelled fill does not raise, it just quietly corrupts the only source of new
evidence the system has.
"""

import numpy as np
import pandas as pd
import pytest

from live_loop.stage1_map_fills import (
    DIRECTION,
    SIDE,
    _CONF_RANK,
    _live_to_canonical,
    ladder_tier,
    map_entry,
    play_structure,
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _ac(*plays):
    """An AnalysisClaude frame for one ticker/date, one row per play text."""
    return pd.DataFrame(
        [{"date": "2026-07-22", "ticker": "META", "play": p, "horizon": 45}
         for p in plays]
    )


def _live(structure, strikes):
    """A reconstructed live entry.

    `structure` must be a label `classify_structure()` actually emits — naked
    legs come through as `"single long call"` (spaces), verticals as
    `"bull_call_spread"` (underscores). Passing the canonical form for a naked
    leg would silently make it `"unknown"` and the test would prove nothing;
    `test_classify_structure_labels_survive_canonicalisation` pins that seam.
    """
    return {
        "structure": structure,
        "entry": {"legs": [{"match": {"strike": s}} for s in strikes]},
    }


def _map(live_structure, live_strikes, *plays):
    return map_entry(_live(live_structure, live_strikes), "2026-07-22", "META",
                     _ac(*plays))


# --------------------------------------------------------------------------
# the maps themselves
# --------------------------------------------------------------------------
def test_side_alone_cannot_separate_naked_from_spread():
    """The precondition for the 08-11 bug — pinned so it stays visible.

    If this ever stops being true, the DIRECTION gate below is dead code and
    someone should find out why rather than delete the guard.
    """
    assert SIDE["long_call"] == SIDE["bull_call_spread"] == "debit"
    assert SIDE["long_put"] == SIDE["bull_call_spread"] == "debit"


def test_direction_separates_what_side_cannot():
    assert DIRECTION["long_call"] == DIRECTION["bull_call_spread"] == "bullish"
    assert DIRECTION["long_put"] != DIRECTION["bull_call_spread"]


def test_every_sided_structure_also_has_a_direction():
    """A structure in SIDE but not DIRECTION would fall through the gate."""
    assert set(SIDE) == set(DIRECTION)


# --------------------------------------------------------------------------
# map_entry — the four confidence levels
# --------------------------------------------------------------------------
def test_exact_requires_structure_and_both_strikes():
    out = _map("bull_call_spread", [185.0, 200.0], "bull call spread 185/200")
    assert out["confidence"] == "EXACT"
    assert out["ac_structure"] == "bull_call_spread"


def test_structure_when_strikes_differ():
    out = _map("bull_call_spread", [190.0, 205.0], "bull call spread 185/200")
    assert out["confidence"] == "STRUCTURE"


def test_naked_leg_against_a_spread_play_is_substituted_not_structure():
    """THE 08-11 BUG. Same side, same direction, different instrument."""
    out = _map("single long call", [185.0], "bull call spread 185/200")
    assert out["confidence"] == "SUBSTITUTED"


def test_short_put_against_a_bull_put_spread_is_substituted():
    """The META row the report's prose flagged while the tally counted it."""
    out = _map("single short put", [600.0], "bull put spread 600/580")
    assert out["confidence"] == "SUBSTITUTED"


def test_overlay_suffix_still_canonicalises_to_the_naked_leg():
    out = _map("single short call (overlay)", [200.0], "bear call spread 200/210")
    assert out["confidence"] == "SUBSTITUTED"


def test_opposite_direction_same_side_is_not_a_match_at_all():
    """THE SECOND 08-11 DEFECT: long_put vs bull_call_spread are both debit."""
    out = _map("single long put", [185.0], "bull call spread 185/200")
    assert out["confidence"] == "NONE"
    assert out["ac_structure"] is None


@pytest.mark.parametrize("emitted,canonical", [
    ("single long call", "long_call"),
    ("single long put", "long_put"),
    ("single short put", "short_put"),
    ("single short call", "short_call"),
    ("single short call (overlay)", "short_call"),
    ("bull_call_spread", "bull_call_spread"),
    ("bear_put_spread", "bear_put_spread"),
    ("bull_put_spread", "bull_put_spread"),
    ("bear_call_spread", "bear_call_spread"),
])
def test_classify_structure_labels_survive_canonicalisation(emitted, canonical):
    """The seam between classify_structure() and map_entry().

    A label classify_structure() emits that canonicalises to "unknown" cannot
    match ANY play, so the fill silently drops to NONE — indistinguishable from
    "no play that day". That is the exact failure the 07-27 entry described, so
    the label vocabulary is pinned rather than trusted.
    """
    assert _live_to_canonical(emitted) == canonical


def test_a_position_with_unpinnable_identity_stays_unknown():
    """Round-trip closes genuinely have no identity — they must NOT guess."""
    assert _live_to_canonical(
        "single long option (debit), strike/expiry UNKNOWN") == "unknown"


def test_no_play_for_that_ticker_date_is_none():
    out = map_entry(_live("bull_call_spread", [185.0, 200.0]),
                    "2026-07-22", "NVDA", _ac("bull call spread 185/200"))
    assert out["confidence"] == "NONE"


# --------------------------------------------------------------------------
# candidate ranking — a true match must outrank a substitution
# --------------------------------------------------------------------------
def test_rank_order_is_exact_then_structure_then_substituted():
    assert (_CONF_RANK["EXACT"] < _CONF_RANK["STRUCTURE"]
            < _CONF_RANK["SUBSTITUTED"])


@pytest.mark.parametrize("order", [
    ("long call 185", "bull call spread 185/200"),
    ("bull call spread 185/200", "long call 185"),
])
def test_exact_match_wins_over_a_substitution_regardless_of_row_order(order):
    """Selection is rank-based, not first-candidate-found."""
    out = _map("bull_call_spread", [185.0, 200.0], *order)
    assert out["confidence"] == "EXACT"
    assert out["ac_structure"] == "bull_call_spread"


def test_structure_match_wins_over_a_substitution_listed_first():
    out = _map("bull_call_spread", [190.0, 205.0],
               "long call 185", "bull call spread 185/200")
    assert out["confidence"] == "STRUCTURE"
    assert out["ac_structure"] == "bull_call_spread"


# --------------------------------------------------------------------------
# play_structure — the text parser feeding all of the above
# --------------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("bull call spread 185/200", "bull_call_spread"),
    ("bear put spread 500/480", "bear_put_spread"),
    ("bull put spread 600/580", "bull_put_spread"),
    ("protective put spread 500/480", "bear_put_spread"),
    ("long call 185", "long_call"),
    ("long put 500", "long_put"),
    ("something unparseable", "unknown"),
])
def test_play_structure_parses_emitted_play_text(text, expected):
    assert play_structure(text) == expected


# --------------------------------------------------------------------------
# ladder_tier — the encoded copy of config/deployment-rules.md
# --------------------------------------------------------------------------
def test_bear_call_spread_is_vetoed_whatever_the_regime():
    tier, _, reason = ladder_tier("bear_call_spread", "BULL + L-VOL")
    assert tier == "VETO"
    assert "bear_call" in reason


def test_bear_plus_hvol_vetoes_everything():
    tier, _, _ = ladder_tier("bull_call_spread", "BEAR + H-VOL")
    assert tier == "VETO"


def test_credit_in_range_lvol_is_vetoed():
    assert ladder_tier("bull_put_spread", "RANGE + L-VOL")[0] == "VETO"
    # ...but the same regime does not veto a debit
    assert ladder_tier("bull_call_spread", "RANGE + L-VOL")[0] != "VETO"


@pytest.mark.parametrize("regime", ["RANGE + C-VOL", "BULL + E-VOL"])
def test_bull_call_in_range_or_evol_is_tier_a(regime):
    assert ladder_tier("bull_call_spread", regime, dte_proxy=45)[0] == "A"


def test_bear_put_never_reaches_the_deployed_tiers():
    """Bear is a hedge, not a selection — it must never land in A or B."""
    for regime in ["BULL + L-VOL", "RANGE + C-VOL", "BEAR + L-VOL"]:
        tier, _, _ = ladder_tier("bear_put_spread", regime, dte_proxy=45)
        assert tier in {"C", "VETO"}, f"{regime} put bear_put in {tier}"


def test_unknown_structure_does_not_crash_the_ladder():
    tier, _, _ = ladder_tier("unknown", "RANGE + C-VOL", dte_proxy=np.nan)
    assert tier in {"A", "B", "C", "VETO"}
