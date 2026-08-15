"""The qualifier-infixed structure name ('bear put debit spread') must reach the
same structure as its canonical form, everywhere a play's text is parsed.

Regression: the model periodically writes the debit/credit qualifier inside the
structure name because the framework's own prose describes structures that way.
Neither `bear put spread` nor `put spread` is a substring of `bear put debit
spread`, so the phrase used to fall through every spread branch — the backtest
classifier priced a two-leg vertical as ONE long option, and the live-loop play
parser returned "unknown" and could not match the fill at all. Both are silent:
a row is still written, with a `structure`/`legs` contradicting its own `play`.
"""

import pytest

from lib.structure_names import canonical_spread_names
from backtest.classify import classify_play
from live_loop.mapping import play_structure


# (play text, expected structure, expected is_credit)
QUALIFIED = [
    ("[HEDGE] TF | bear put debit spread 580/540 | index protection",
     "bear_put_spread", False),
    ("[SYNTHETIC STOCK] PU | bear put debit spread 185/165, ~136 DTE",
     "bear_put_spread", False),
    ("[DIRECTIONAL] TF | bull call debit spread 180/200 | cheap IV",
     "bull_call_spread", False),
    ("[DIRECTIONAL] TF-S | bull put credit spread 62/57 | rich IV",
     "bull_put_spread", True),
    ("[DIRECTIONAL] TF | call debit spread 87/92 ~180 DTE | call-lean",
     "bull_call_spread", False),
    ("[HEDGE] MR | put debit spread 81/78, 60-120 DTE | cheap credit puts",
     "bear_put_spread", False),
    ("[SYNTHETIC STOCK] PU | buy Mar 15 (56 DTE) 80/72.5 put debit spread",
     "bear_put_spread", False),
    # Reversed qualifier order, and a hyphen before 'spread'.
    ("[DIRECTIONAL] TF | debit put spread 350/320 | down-vector",
     "bear_put_spread", False),
    ("[DIRECTIONAL] TF | bear put debit-spread 350/320 | down-vector",
     "bear_put_spread", False),
]


@pytest.mark.parametrize("text,structure,is_credit", QUALIFIED)
def test_classify_play_reads_qualified_spread_names(text, structure, is_credit):
    got = classify_play(text)
    assert got["structure"] == structure
    assert got["is_credit"] is is_credit
    # Two strikes parsed means it is priced as a vertical, not a single leg.
    assert len(got["strikes"]) == 2


@pytest.mark.parametrize("text,structure,_is_credit", QUALIFIED)
def test_play_structure_reads_qualified_spread_names(text, structure, _is_credit):
    assert play_structure(text) == structure


def test_canonical_names_leave_clean_text_alone():
    for text in ["bear put spread 350/320", "long put 350", "iron condor 5/6/7/8",
                 "a defined-risk debit across the 390 level", "calendar 500"]:
        assert canonical_spread_names(text) == text


def test_type_and_qualifier_beat_a_contradictory_direction_word():
    # 'bull put debit spread' is incoherent; (put, debit) is the reliable pair.
    assert classify_play("bull put debit spread 350/320")["structure"] == "bear_put_spread"


def test_covered_gate_needs_the_structure_not_the_bare_word():
    """'covered' in prose must not reject a priceable spread (it did: a
    `bear put spread 470/440` whose rationale said 'deserves to be covered')."""
    prose = ("[HEDGE] TF | bear put spread 470/440, 90-120 DTE | Protection on a "
             "long Nasdaq book: the downside deserves to be covered while the tape "
             "holds.")
    assert classify_play(prose)["structure"] == "bear_put_spread"
    # A real covered call is still refused.
    assert classify_play("covered call 200 against the long")["structure"] == "unsupported"
    assert classify_play("covered-call sale at 200")["structure"] == "unsupported"
