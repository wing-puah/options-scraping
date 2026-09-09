"""Regression tests for the journal's fill mapper (`scripts/journal/lib/mapping.py`).

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

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from scripts.journal.config import Leg
from scripts.journal.lib.mapping import (
    CONFIDENCES,
    DIRECTION,
    SIDE,
    _CONF_RANK,
    _core_strikes,
    _live_to_canonical,
    _vertical_label,
    classify_structure,
    core_structure,
    decompose_core,
    ladder_tier,
    map_entry,
    play_structure,
    position_legs,
)


# --------------------------------------------------------------------------
# helpers
#
# mapping.py takes the journal's OWN `Leg` objects — the same type
# `lib/rawpull.py` builds from a fill and from an open position — so the
# fixtures below build Legs directly. There is no adapter to mirror.
# --------------------------------------------------------------------------
_EXPIRY = date(2026, 12, 18)


def _leg(strike, *, right="C", qty=1, price=1.0, expiry=_EXPIRY, symbol="META",
         conid=None):
    return Leg(conid=conid if conid is not None else int(strike * 10),
               symbol=symbol, expiry=expiry, strike=float(strike), right=right,
               qty=qty, fill_price=price, commission=0.0,
               exec_id=f"e{strike}{right}{qty}", fill_time=datetime(2026, 7, 22, 14, 0),
               open_close="O")


def _ac(*plays):
    """An AnalysisClaude frame for one ticker/date, one row per play text."""
    return pd.DataFrame(
        [{"date": "2026-07-22", "ticker": "META", "play": p, "horizon": 45}
         for p in plays]
    )


def _live(structure, strikes):
    """The legs of a reconstructed live position, at `strikes`.

    `structure` must be a label `classify_structure()` actually emits — naked
    legs come through as `"single long call"` (spaces), verticals as
    `"bull_call_spread"` (underscores). Passing the canonical form for a naked
    leg would silently make it `"unknown"` and the test would prove nothing;
    `test_classify_structure_labels_survive_canonicalisation` pins that seam.
    """
    return structure, [_leg(s) for s in strikes]


def _map(live_structure, live_strikes, *plays):
    structure, legs = _live(live_structure, live_strikes)
    return map_entry(structure, legs, "2026-07-22", "META", _ac(*plays))


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
    out = map_entry(*_live("bull_call_spread", [185.0, 200.0]),
                    "2026-07-22", "NVDA", _ac("bull call spread 185/200"))
    assert out["confidence"] == "NONE"


# --------------------------------------------------------------------------
# candidate ranking — a true match must outrank a substitution
# --------------------------------------------------------------------------
def test_rank_order_is_exact_then_structure_then_core_then_substituted():
    assert (_CONF_RANK["EXACT"] < _CONF_RANK["STRUCTURE"]
            < _CONF_RANK["CORE"] < _CONF_RANK["SUBSTITUTED"])


def test_the_confidence_vocabulary_is_defined_once():
    """`scripts/journal/config.py::MATCH_CONFIDENCES` DERIVES from this tuple.
    A category present in one and not the other vanishes silently from a count."""
    from journal.config import MATCH_CONFIDENCES
    # `==`, not `is`: conftest puts BOTH the repo root and scripts/ on sys.path,
    # so mapping.py is importable as two distinct module objects and the tuples
    # are equal without being identical. The claim under test is that the
    # vocabulary is not hand-copied, and equality is what carries that.
    assert MATCH_CONFIDENCES == CONFIDENCES
    # every rankable confidence must be in the vocabulary, or a match could be
    # produced that no tally has a bucket for
    assert set(_CONF_RANK) <= set(CONFIDENCES)


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
# ladder_tier — the encoded copy of docs/deployment-rules.md
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


# --------------------------------------------------------------------------
# decompose_core — a financed vertical is the play plus a leg sold against it
#
# The operator's actual strategy: buy a debit vertical, sell a further (always
# short, usually shorter-dated) leg to reduce the debit. The broker reports one
# N-leg combo, `classify_structure` can only call it "3-leg combo (debit)", and
# that canonicalises to "unknown" — which has no SIDE/DIRECTION entry, so
# `map_entry` used to reject it outright and the trade scored NONE against the
# very play it was built from. These pin the decomposition that fixes it, and —
# more importantly — pin that an AMBIGUOUS group is never guessed at.
# --------------------------------------------------------------------------
def _mleg(strike, right, expiry, qty, price):
    """One leg of a financed multi-leg group."""
    return _leg(strike, right=right, qty=qty, price=price, symbol="CRWV",
                expiry=date.fromisoformat(expiry),
                conid=int(strike * 10) + (0 if expiry == "2027-01-15" else 1))


def _crwv():
    """The real 2026-08-14 fill: a 110/135 Jan-27 call spread, financed by a
    short Sep-26 150 call."""
    return [
        _mleg(110.0, "C", "2027-01-15", 1, 22.00),
        _mleg(135.0, "C", "2027-01-15", -1, 13.00),
        _mleg(150.0, "C", "2026-09-18", -1, 2.65),
    ]


def test_a_financed_vertical_decomposes_into_its_core_and_the_financing_leg():
    core, overlays = decompose_core(_crwv())
    assert core is not None
    assert {c.strike for c in core} == {110.0, 135.0}
    assert [o.strike for o in overlays] == [150.0]
    assert core_structure(_crwv()) == "bull_call_spread"
    assert _core_strikes(_crwv()) == {110.0, 135.0}


def test_the_core_matches_the_emitted_play_as_core_not_none():
    """THE BUG. Before decomposition this scored NONE against its own play."""
    ac = pd.DataFrame([{"date": "2026-08-13", "ticker": "CRWV",
                        "play": "bull call spread 110/135", "horizon": 45}])
    out = map_entry("3-leg combo (debit)", _crwv(), "2026-08-13", "CRWV", ac)
    assert out["confidence"] == "CORE"
    assert out["ac_structure"] == "bull_call_spread"
    assert out["core_structure"] == "bull_call_spread"


def test_a_core_match_is_not_promoted_to_exact_even_when_strikes_agree():
    """EXACT means the emitted play was traded. This is the emitted play PLUS a
    leg the analysis never proposed — a materially different position."""
    ac = pd.DataFrame([{"date": "2026-08-13", "ticker": "CRWV",
                        "play": "bull call spread 110/135", "horizon": 45}])
    out = map_entry("3-leg combo (debit)", _crwv(), "2026-08-13", "CRWV", ac)
    assert out["confidence"] != "EXACT"


def test_the_core_still_matches_when_the_plays_strikes_differ():
    ac = pd.DataFrame([{"date": "2026-08-13", "ticker": "CRWV",
                        "play": "bull call spread 120/140", "horizon": 45}])
    out = map_entry("3-leg combo (debit)", _crwv(), "2026-08-13", "CRWV", ac)
    assert out["confidence"] == "CORE"


def test_the_direction_gate_still_binds_on_a_decomposed_core():
    """Decomposition widens WHAT can match, never WHETHER direction matters."""
    ac = pd.DataFrame([{"date": "2026-08-13", "ticker": "CRWV",
                        "play": "bear put spread 100/90", "horizon": 45}])
    out = map_entry("3-leg combo (debit)", _crwv(), "2026-08-13", "CRWV", ac)
    assert out["confidence"] == "NONE"


def test_a_whole_group_match_outranks_a_core_reading():
    """A 2-leg entry that matches outright is stronger evidence than any
    decomposition, so ranking must prefer it."""
    out = _map("bull_call_spread", [185.0, 200.0], "bull call spread 185/200")
    assert out["confidence"] == "EXACT"


# -- undecidable groups fall back; they are never guessed at ----------------
def test_a_long_leftover_leg_makes_the_group_undecidable():
    """A financing overlay is SHORT by definition. A long leftover means this is
    some other structure whose shape we do not know."""
    e = _crwv()
    e[2] = _mleg(150.0, "C", "2026-09-18", 1, 2.65)   # long, not short
    assert decompose_core(e) == (None, [])


def test_a_credit_core_makes_the_group_undecidable():
    """'A debit vertical, part-financed' is the strategy modelled. A credit core
    is a different animal and gets no invented interpretation."""
    e = _crwv()
    e[0] = _mleg(110.0, "C", "2027-01-15", 1, 5.00)   # core now a credit
    assert decompose_core(e) == (None, [])


def test_a_group_with_no_vertical_pair_is_undecidable():
    e = [_mleg(110.0, "C", "2027-01-15", -1, 22.00),
         _mleg(135.0, "C", "2027-01-15", -1, 13.00),
         _mleg(150.0, "C", "2026-09-18", -1, 2.65)]
    assert decompose_core(e) == (None, [])


def test_a_leg_missing_its_identity_makes_the_group_undecidable():
    """A `Leg` rebuilt from a partial record (relabel.py does this) can carry a
    None field. That must make the group undecidable, never raise."""
    from dataclasses import replace
    e = _crwv()
    e[1] = replace(e[1], strike=None)
    assert decompose_core(e) == (None, [])


def test_a_tie_between_two_equal_cores_is_undecidable_rather_than_arbitrary():
    """Two candidate cores with identical net debit: picking either would be a
    coin flip presented as a fact."""
    e = [_mleg(110.0, "C", "2027-01-15", 1, 20.00),
         _mleg(135.0, "C", "2027-01-15", -1, 10.00),
         _mleg(110.0, "P", "2027-01-15", 1, 20.00),
         _mleg(135.0, "P", "2027-01-15", -1, 10.00),
         _mleg(150.0, "C", "2026-09-18", -1, 2.65)]
    assert decompose_core(e) == (None, [])


def test_decompose_core_never_raises_on_a_degenerate_group():
    """An empty or under-identified group is undecidable, never an exception."""
    from dataclasses import replace
    e = [replace(lg, expiry=None, right=None) for lg in _crwv()]
    assert decompose_core(e) == (None, [])
    assert core_structure(e) is None
    assert _core_strikes(e) == set()
    assert decompose_core([]) == (None, [])
    assert decompose_core(None) == (None, [])


# -- _vertical_label is one encoding, shared by the two-leg branch and the core
@pytest.mark.parametrize("lo_qty,hi_qty,right,expected", [
    (1, -1, "C", "bull_call_spread"),
    (-1, 1, "C", "bear_call_spread"),
    (1, -1, "P", "bull_put_spread"),
    (-1, 1, "P", "bear_put_spread"),
])
def test_vertical_label_names_every_plain_vertical(lo_qty, hi_qty, right, expected):
    a = _leg(100.0, right=right, qty=lo_qty)
    b = _leg(110.0, right=right, qty=hi_qty)
    assert _vertical_label(a, b, "debit") == expected
    assert _vertical_label(b, a, "debit") == expected   # order-independent


# --------------------------------------------------------------------------
# position_legs — the CLOSE orientation (the P1 fix), and the money it must
# never touch. `tests/test_p1_closed_spread_robustness.py` pins the pipeline
# end of this; these pin the function itself.
# --------------------------------------------------------------------------
def test_position_legs_leaves_an_opening_group_alone():
    legs = [_leg(170.0, qty=1, price=8.0), _leg(180.0, qty=-1, price=3.0)]
    assert position_legs(legs, closing=False) == legs
    assert classify_structure(legs)[0] == "bull_call_spread"


def test_position_legs_names_the_position_a_close_unwinds():
    """Selling the 170 and buying back the 180 IS a bull call spread being
    closed — read from the fill signs it is the mirror image, which
    `ladder_tier()` then vetoes."""
    closing = [_leg(170.0, qty=-1, price=11.0), _leg(180.0, qty=1, price=5.0)]
    assert classify_structure(closing)[0] == "bear_call_spread"
    assert classify_structure(position_legs(closing, closing=True))[0] == \
        "bull_call_spread"


def test_orientation_never_touches_the_money():
    """`net_price()` is read off the UNORIENTED legs on purpose: the label names
    the position, the cash names the transaction."""
    from scripts.journal.lib.mapping import net_price
    closing = [_leg(170.0, qty=-1, price=11.0), _leg(180.0, qty=1, price=5.0)]
    assert net_price(closing) == pytest.approx(-6.0)          # a $6 credit
    assert net_price(position_legs(closing, closing=True)) == pytest.approx(6.0)


# --------------------------------------------------------------------------
# classify_structure — the labels the rest of the journal reads
# --------------------------------------------------------------------------
def test_classify_structure_names_a_single_leg_by_side_and_right():
    assert classify_structure([_leg(185.0, qty=1)])[0] == "single long call"
    assert classify_structure([_leg(185.0, qty=-1, right="P")])[0] == "single short put"


def test_a_short_leg_over_another_expiry_is_an_overlay():
    """The overlay test reads the OPEN BOOK — `rawpull.open_legs()`'s Legs."""
    leg = _leg(200.0, qty=-1, expiry=date(2026, 9, 18))
    book = [_leg(185.0, qty=1, expiry=date(2027, 1, 15)),
            _leg(200.0, qty=-1, expiry=date(2027, 1, 15))]
    label, _note, is_overlay = classify_structure([leg], book)
    assert (label, is_overlay) == ("single short call (overlay)", True)
    # a LONG leg is never an overlay, and neither is one with an empty book
    assert classify_structure([_leg(200.0, qty=1, expiry=date(2026, 9, 18))],
                              book)[2] is False
    assert classify_structure([leg])[2] is False


def test_two_expiries_are_reported_as_a_calendar_rather_than_a_vertical():
    legs = [_leg(200.0, qty=1, expiry=date(2027, 1, 15), price=9.0),
            _leg(200.0, qty=-1, expiry=date(2026, 9, 18), price=3.0)]
    label, note, _overlay = classify_structure(legs)
    assert label == "diagonal/calendar (mixed expiry)"
    assert "two expiries" in note


def test_three_distinct_contracts_are_a_combo_named_by_their_net():
    assert classify_structure(_crwv())[0] == "3-leg combo (debit)"
