"""
Tests for scripts/journal/recommend.py — the step-6 deploy-card ranker.

Offline throughout. `judge()`'s `invoke` is always stubbed (a plain callable
returning a JSON string), so nothing here spawns a `claude -p` subprocess.

`rank()`'s tier decision is MARKET-level (config/deployment-rules.md invariant:
the ladder reads the MARKET row's regime, never a play row's own `regime`), so
every play on one `_ac_df(...)` call shares one market regime — tests that need
two different tiers side by side (Tier A vs Tier B) get there with two
DIFFERENT STRUCTURES on the same date, not two regimes on the same date.
"""
from __future__ import annotations

import pandas as pd

from journal.recommend import Candidate, Rejected, judge, rank, render
from journal.risk import BookRisk

DATE = "2026-08-14"


def _row(ticker, play, score_total=None, trigger="", invalidation="", delta=None):
    row = {
        "date": DATE, "ticker": ticker, "play": play, "regime": "", "signal": "",
        "mech_cell": "", "horizon": "", "trigger": trigger, "invalidation": invalidation,
        "score_total": float("nan") if score_total is None else float(score_total),
    }
    if delta is not None:
        row["delta"] = delta
    return row


def _ac_df(market_regime, plays):
    rows = [{
        "date": DATE, "ticker": "MARKET", "play": "", "regime": market_regime,
        "signal": "", "mech_cell": "", "horizon": "", "trigger": "", "invalidation": "",
        "score_total": float("nan"),
    }]
    rows.extend(plays)
    return pd.DataFrame(rows)


def _empty_book() -> BookRisk:
    return BookRisk()


# --------------------------------------------------------------------------
# Part A — vetoes
# --------------------------------------------------------------------------
def test_bear_call_spread_vetoed_whatever_the_regime():
    for regime in ("RANGE + C-VOL", "BULL + L-VOL", "BEAR + E-VOL"):
        ac_df = _ac_df(regime, [_row("XOM", "Bear call spread 100/110, ~45 DTE")])
        candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
        assert candidates == []
        assert len(rejected) == 1
        assert rejected[0].tier == "VETO"
        assert "bear_call_spread" in rejected[0].reason


def test_bear_h_vol_day_vetoes_everything():
    plays = [
        _row("AAA", "Bull call spread 100/110, ~50 DTE"),
        _row("BBB", "Bull put spread 90/80, 45-59 DTE"),
        _row("CCC", "Bear put spread 100/90, ~50 DTE"),
        _row("DDD", "Long put 100, ~50 DTE"),
    ]
    ac_df = _ac_df("BEAR + H-VOL", plays)
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
    assert candidates == []  # no deploy AND no hedge candidates survive
    assert len(rejected) == 4
    assert all(r.tier == "VETO" for r in rejected)
    assert all("BEAR + H-VOL" in r.reason for r in rejected)


def test_credit_play_in_range_l_vol_vetoed():
    ac_df = _ac_df("RANGE + L-VOL", [_row("SPY", "Bull put spread 400/390, 45-59 DTE")])
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
    assert candidates == []
    assert len(rejected) == 1
    assert rejected[0].tier == "VETO"
    assert "credit" in rejected[0].reason


# --------------------------------------------------------------------------
# Part A — tiering / ordering
# --------------------------------------------------------------------------
def test_bull_call_spread_in_range_or_evol_ranks_tier_a_above_tier_b():
    plays = [
        _row("BBB", "Bull put spread 90/80, 45-59 DTE"),   # -> Tier B
        _row("AAA", "Bull call spread 100/110, ~50 DTE"),  # -> Tier A
    ]
    ac_df = _ac_df("RANGE + E-VOL", plays)
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
    deploy = [c for c in candidates if c.role == "deploy"]
    assert [c.ticker for c in deploy] == ["AAA", "BBB"]
    assert deploy[0].tier == "A"
    assert deploy[1].tier == "B"
    assert rejected == []


def test_score_total_never_moves_a_play_between_tiers():
    plays = [
        _row("AAA", "Bull call spread 100/110, ~50 DTE", score_total=1),    # Tier A, low score
        _row("BBB", "Bull put spread 90/80, 45-59 DTE", score_total=99),    # Tier B, high score
    ]
    ac_df = _ac_df("RANGE + E-VOL", plays)
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
    deploy = [c for c in candidates if c.role == "deploy"]
    # Tier A stays first despite the massively lower score_total.
    assert [c.ticker for c in deploy] == ["AAA", "BBB"]
    assert deploy[0].tier == "A" and deploy[0].score_total == 1
    assert deploy[1].tier == "B" and deploy[1].score_total == 99


def test_deploy_budget_marks_top_three():
    plays = [_row(f"T{i}", "Bull call spread 100/110, ~50 DTE") for i in range(5)]
    ac_df = _ac_df("RANGE + E-VOL", plays)
    candidates, _ = rank(ac_df, DATE, _empty_book(), None)
    deploy = [c for c in candidates if c.role == "deploy"]
    assert len(deploy) == 5
    assert [c.deploy for c in deploy] == [True, True, True, False, False]


def test_duplicate_exposure_flagged():
    ac_df = _ac_df("RANGE + E-VOL", [_row("AAA", "Bull call spread 100/110, ~50 DTE")])
    book = BookRisk()
    from journal.config import PositionRisk
    book.positions.append(PositionRisk(conid_key="1", ticker="AAA", structure="open",
                                       contracts=1, position_delta=0.3, delta_notional=1000.0,
                                       delta_source="ibkr"))
    candidates, _ = rank(ac_df, DATE, book, None)
    deploy = [c for c in candidates if c.role == "deploy"]
    assert deploy[0].duplicate_exposure is True


# --------------------------------------------------------------------------
# Part A — hedge sleeve
# --------------------------------------------------------------------------
def test_hedge_sleeve_ranks_by_abs_delta_desc_not_score_total():
    plays = [
        _row("H1", "Bear put spread 100/90, ~50 DTE", score_total=90, delta=-0.10),
        _row("H2", "Long put 100, ~50 DTE", score_total=1, delta=-0.30),
    ]
    ac_df = _ac_df("RANGE + E-VOL", plays)  # not BEAR+H-VOL -> not blanket-vetoed
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
    hedge = [c for c in candidates if c.role == "hedge"]
    # H2 has the LARGER |delta| (0.30 > 0.10) despite the much lower score_total.
    assert [c.ticker for c in hedge] == ["H2", "H1"]
    assert rejected == []  # bear structures cleared §1, so they're hedge-eligible


def test_hedge_candidates_never_appear_in_deploy_set():
    plays = [_row("H1", "Bear put spread 100/90, ~50 DTE", delta=-0.10)]
    ac_df = _ac_df("RANGE + E-VOL", plays)
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
    assert [c.role for c in candidates] == ["hedge"]
    assert not any(c.deploy for c in candidates)
    assert rejected == []


# --------------------------------------------------------------------------
# Part B — the judgment call, structural guards
# --------------------------------------------------------------------------
def test_fabricated_ticker_in_response_is_dropped_with_warning():
    ac_df = _ac_df("RANGE + E-VOL", [_row("AAA", "Bull call spread 100/110, ~50 DTE",
                                          trigger="SPY closes above 450")])
    candidates, _ = rank(ac_df, DATE, _empty_book(), None)

    import json

    def stub_invoke(_prompt):
        return json.dumps({
            "candidates": [
                {"ticker": "AAA", "trigger_fired": "yes", "trigger_note": "ok",
                 "alt_more_likely": "no", "alt_note": ""},
                {"ticker": "ZZZZ", "trigger_fired": "yes", "trigger_note": "fabricated",
                 "alt_more_likely": "no", "alt_note": ""},
            ],
            "hedge": [], "hedge_pick": None, "hedge_pick_note": "",
        })

    result = judge(candidates, "context text", invoke=stub_invoke)
    assert result["ran"] is True
    assert "ZZZZ" in result["dropped_tickers"]
    assert any("ZZZZ" in w for w in result["warnings"])
    # The real candidate's verdict WAS applied.
    aaa = next(c for c in candidates if c.ticker == "AAA")
    assert aaa.trigger_verdict == "yes"


def test_stubbed_response_promoting_a_vetoed_play_does_not_change_ordering():
    plays = [
        _row("VETO1", "Bear call spread 100/110, ~45 DTE"),   # -> VETO, never a survivor
        _row("AAA", "Bull call spread 100/110, ~50 DTE"),     # -> Tier A, survivor
        _row("BBB", "Bull put spread 90/80, 45-59 DTE"),      # -> Tier B, survivor
    ]
    ac_df = _ac_df("RANGE + E-VOL", plays)
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
    before_order = [c.ticker for c in candidates]
    assert "VETO1" not in before_order
    assert any(r.ticker == "VETO1" and r.tier == "VETO" for r in rejected)

    import json

    def stub_invoke(_prompt):
        # Model tries to resurrect the vetoed ticker and give it a verdict.
        return json.dumps({
            "candidates": [
                {"ticker": "VETO1", "trigger_fired": "yes", "trigger_note": "promote me",
                 "alt_more_likely": "no", "alt_note": ""},
                {"ticker": "BBB", "trigger_fired": "yes", "trigger_note": "fine",
                 "alt_more_likely": "no", "alt_note": ""},
            ],
            "hedge": [], "hedge_pick": None, "hedge_pick_note": "",
        })

    result = judge(candidates, "context text", invoke=stub_invoke)
    assert "VETO1" in result["dropped_tickers"]
    # Ordering (and membership) of the Part-A candidate list is byte-identical.
    assert [c.ticker for c in candidates] == before_order
    assert all(c.ticker != "VETO1" for c in candidates)
    # The real survivor's tier/deploy flags are untouched by the annotation pass.
    bbb = next(c for c in candidates if c.ticker == "BBB")
    assert bbb.tier == "B"
    assert bbb.trigger_verdict == "yes"  # annotation applied, ordering/tier not


def test_no_survivors_short_circuits_without_invoking():
    called = {"n": 0}

    def stub_invoke(_prompt):
        called["n"] += 1
        return "{}"

    result = judge([], "context", invoke=stub_invoke)
    assert result["ran"] is False
    assert called["n"] == 0


# --------------------------------------------------------------------------
# Part C — render()
# --------------------------------------------------------------------------
def test_no_llm_path_renders_a_complete_card():
    plays = [
        _row("AAA", "Bull call spread 100/110, ~50 DTE"),
        _row("BBB", "Bear call spread 90/80, ~45 DTE"),
    ]
    ac_df = _ac_df("RANGE + E-VOL", plays)
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
    card = render(candidates, rejected, None, date=DATE, source="sheets", net_liq=None)
    assert card.startswith(f"# Deploy card — {DATE}")
    assert "## Deploy set" in card
    assert "## Hedge sleeve" in card
    assert "## Rejected" in card
    assert "## Judgment call" in card
    assert "**Not run**" in card
    assert "AAA" in card
    assert "BBB" in card  # vetoed, still visible


def test_rendered_card_contains_v3_v4_caveat():
    ac_df = _ac_df("RANGE + E-VOL", [_row("AAA", "Bull call spread 100/110, ~50 DTE")])
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)
    card = render(candidates, rejected, None, date=DATE)
    assert "v4 transfer is not yet validated" in card
    assert "not comparable" in card


def test_render_shows_judgment_ran_and_dropped_tickers():
    ac_df = _ac_df("RANGE + E-VOL", [_row("AAA", "Bull call spread 100/110, ~50 DTE")])
    candidates, rejected = rank(ac_df, DATE, _empty_book(), None)

    import json

    def stub_invoke(_prompt):
        return json.dumps({
            "candidates": [{"ticker": "AAA", "trigger_fired": "unknown", "trigger_note": "",
                            "alt_more_likely": "no", "alt_note": ""}],
            "hedge": [], "hedge_pick": None, "hedge_pick_note": "",
        })

    judgment = judge(candidates, "ctx", invoke=stub_invoke)
    card = render(candidates, rejected, judgment, date=DATE)
    assert "Ran." in card


def test_dataclasses_importable_and_shaped():
    # Cheap smoke test that the two record types carry the fields render()/judge()
    # depend on -- guards against an accidental field rename in one place only.
    c = Candidate(ticker="X", play="p", structure="bull_call_spread", market_regime="RANGE",
                  tier="A", tier_partial=False, tier_reason="r", score_total=None,
                  horizon="", trigger="", invalidation="", alternative_interpretation="",
                  role="deploy")
    assert c.deploy is False and c.demoted is False
    r = Rejected(ticker="Y", play="p", structure="bear_call_spread", market_regime="RANGE",
                 tier="VETO", reason="r")
    assert r.score_total is None
