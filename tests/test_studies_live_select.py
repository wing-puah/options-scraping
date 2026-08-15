"""Tests for the `account_sim --live-select` arm's machinery.

The arm's whole value is that the simulated decision IS the live decision, so
what is pinned here is every place the two could quietly come apart:

  * the two per-day budgets (`recommend.DEPLOY_BUDGET` and the config's
    `max_positions_per_day`) are asserted equal, and the drift is loud,
  * the synthetic book keeps the missing/zero invariant — a record with no delta
    lands in `unpriced`, never in the totals as a zero,
  * the §3 entry check joins a measured delta in one mode and invents nothing in
    the other,
  * the judgment cache replays a stored answer byte-for-byte and refuses to
    invent one when live calls are off (this is what makes two consecutive runs
    produce identical books),
  * a same-ticker collision is detected and BOTH verdicts are blanked rather
    than one annotating two plays, and
  * G6 fires on a fabricated ticker.

No CSV and no book: every fixture is built here.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from scripts.backtest_study.lib import live_select as LS  # noqa: E402
from scripts.backtest_study import run as study_runner  # noqa: E402
from scripts.backtest_study.f4_deployment.account_sim import positions_artifact  # noqa: E402
from scripts.journal import s06_recommend as recommend  # noqa: E402
from scripts.journal.config import DELTA_SOURCE_BARCHART  # noqa: E402


# ── fixtures ─────────────────────────────────────────────────────────────────

def make_rec(date="2026-01-05", ticker="NVDA", structure="bull_put_spread",
             delta=-0.15, dte=45.0, max_loss=250.0, underlying=500.0,
             market_regime="RANGE + L-VOL", source="real"):
    """A book record with only the keys the arm actually reads."""
    return dict(date=date, ticker=ticker, structure=structure, source=source,
                delta=delta, dte=dte, max_loss_per_contract=max_loss,
                market_regime=market_regime, credit=True,
                t=SimpleNamespace(row={"entry_underlying": str(underlying)}))


def make_pos(rec, contracts=2, dn=1500.0):
    return SimpleNamespace(rec=rec, contracts=contracts, dn=dn)


def make_ac_frame(rows):
    """A minimal AnalysisClaude-shaped frame (the columns `rank()` reads)."""
    df = pd.DataFrame(rows)
    for col in ("date", "ticker", "play", "regime", "horizon", "trigger",
                "invalidation", "score_total"):
        if col not in df.columns:
            df[col] = ""
    return df


def make_candidate(ticker="NVDA", structure="bull_put_spread", role="deploy"):
    return recommend.Candidate(
        ticker=ticker, play="bull put spread 45 DTE", structure=structure,
        market_regime="RANGE + L-VOL", tier="B", tier_partial=False,
        tier_reason="", score_total=30.0, horizon="45", trigger="", invalidation="",
        alternative_interpretation="", role=role)


# ── the two per-day budgets ──────────────────────────────────────────────────

def test_budgets_agree_today():
    """The live card and the simulation deploy the same number per session."""
    LS.assert_budgets_agree(recommend.DEPLOY_BUDGET)


def test_budget_drift_is_loud_not_silent(monkeypatch):
    monkeypatch.setattr(recommend, "DEPLOY_BUDGET", 5)
    with pytest.raises(LS.BudgetDrift) as exc:
        LS.assert_budgets_agree(3)
    assert "DEPLOY_BUDGET=5" in str(exc.value)
    assert "max_positions_per_day=3" in str(exc.value)


# ── the synthetic book ───────────────────────────────────────────────────────

def test_synthetic_book_totals_only_the_positions_with_a_delta():
    priced = make_pos(make_rec(ticker="NVDA", delta=-0.15), dn=1500.0)
    blind = make_pos(make_rec(ticker="AMD", delta=None), dn=0.0)
    book = LS.synthetic_book([priced, blind], equity=25_000,
                             per_pos_cap=0.25, net_cap=2.50)

    assert [p.ticker for p in book.positions] == ["NVDA"]
    assert [p.ticker for p in book.unpriced] == ["AMD"]
    assert book.net_delta_notional == 1500.0
    assert book.gross_delta_notional == 1500.0
    # The 0.0 the sim's own signed_dn() hands back for a delta-less record must
    # never be totalled as a real zero.
    assert not book.complete
    assert book.positions[0].delta_source == DELTA_SOURCE_BARCHART
    assert book.caps.per_position_dollars == pytest.approx(6250.0)
    assert book.caps.net_dollars == pytest.approx(62_500.0)


def test_synthetic_book_positions_are_visible_to_rank_as_open_tickers():
    """`rank()` reads `book.positions` + `book.unpriced` for duplicate exposure —
    a delta-less position must still count as open."""
    book = LS.synthetic_book([make_pos(make_rec(ticker="AMD", delta=None))],
                             equity=25_000, per_pos_cap=0.25, net_cap=2.50)
    frame = make_ac_frame([
        {"date": "2026-01-05", "ticker": "MARKET", "regime": "RANGE + E-VOL"},
        {"date": "2026-01-05", "ticker": "AMD", "play": "bull call spread 45 DTE"},
    ])
    candidates, _ = recommend.rank(frame, "2026-01-05", book, net_liq=25_000)
    assert [c.duplicate_exposure for c in candidates] == [True]


# ── the §3 entry check ───────────────────────────────────────────────────────

def _entry_check_frame():
    return make_ac_frame([
        {"date": "2026-01-05", "ticker": "MARKET", "regime": "BULL + E-VOL"},
        {"date": "2026-01-05", "ticker": "NVDA", "play": "bull put spread 45 DTE"},
        {"date": "2026-01-05", "ticker": "AMD", "play": "bull put spread 45 DTE"},
    ])


def test_entry_check_ibkr_verified_joins_the_measured_delta():
    by_key = {("2026-01-05", "NVDA", "bull_put_spread"): make_rec()}
    frame, stats = LS.join_entry_check(_entry_check_frame(), by_key,
                                       "ibkr_verified", budget=500.0)

    nvda = frame[frame["ticker"] == "NVDA"].iloc[0]
    amd = frame[frame["ticker"] == "AMD"].iloc[0]
    assert nvda["short_leg_delta"] == -0.15
    # 2 contracts at budget 500 / max_loss 250, x delta x 100 x underlying.
    assert nvda["delta_notional"] == pytest.approx(-0.15 * 100 * 2 * 500.0)
    # AMD has no record — nothing is invented for it. pandas stores the absence
    # as NaN in a float column, which `recommend._optional_float` reads back as
    # None; what matters is that no number appears where none was measured.
    assert pd.isna(amd["short_leg_delta"])
    assert recommend._optional_float(amd, "short_leg_delta") is None
    assert stats == {"mode": "ibkr_verified", "rows": 2, "joined": 1, "no_record": 1}


def test_entry_check_analysis_only_supplies_nothing_and_never_mutates_input():
    src = _entry_check_frame()
    by_key = {("2026-01-05", "NVDA", "bull_put_spread"): make_rec()}
    frame, stats = LS.join_entry_check(src, by_key, "analysis_only", budget=500.0)

    assert "short_leg_delta" not in frame.columns
    assert "short_leg_delta" not in src.columns
    assert stats["joined"] == 0 and stats["no_record"] == 2


def test_entry_check_changes_the_tier_the_shipped_ladder_assigns():
    """The point of the knob: a verified delta lifts a bull_put out of `partial`."""
    by_key = {("2026-01-05", "NVDA", "bull_put_spread"): make_rec()}
    verified, _ = LS.join_entry_check(_entry_check_frame(), by_key,
                                      "ibkr_verified", budget=500.0)
    blind, _ = LS.join_entry_check(_entry_check_frame(), by_key,
                                   "analysis_only", budget=500.0)

    def tier_of(frame):
        cands, _rej = recommend.rank(frame, "2026-01-05", LS.jrisk.BookRisk(),
                                     net_liq=25_000)
        return {c.ticker: (c.tier, c.tier_partial) for c in cands}

    assert tier_of(verified)["NVDA"] == ("B", False)
    assert tier_of(blind)["NVDA"] == ("B", True)


def test_entry_check_rejects_an_unknown_mode():
    with pytest.raises(ValueError):
        LS.join_entry_check(_entry_check_frame(), {}, "guess", budget=500.0)


# ── the judgment cache ───────────────────────────────────────────────────────

def test_cache_writes_a_row_then_replays_it_without_calling_again(tmp_path):
    calls = []

    def invoke(prompt):
        calls.append(prompt)
        return '{"candidates": [], "hedge": []}'

    path = tmp_path / "judgments.jsonl"
    cache = LS.JudgmentCache(path=path, model="test-model")
    cache.invoke_fn = invoke
    cache.for_date("2026-01-05")

    first = cache.invoke("PROMPT")
    second = cache.invoke("PROMPT")

    assert first == second
    assert len(calls) == 1
    assert (cache.hits, cache.misses) == (1, 1)

    row = json.loads(path.read_text().strip())
    assert row["prompt_sha256"] == LS.JudgmentCache.key("PROMPT")
    assert row["model"] == "test-model"
    assert row["session"] == "2026-01-05"
    assert row["response"] == first
    assert row["written_at"]


def test_a_second_process_replays_the_same_answer_off_disk(tmp_path):
    """This is what makes two consecutive `--live-select` runs identical."""
    path = tmp_path / "judgments.jsonl"
    first = LS.JudgmentCache(path=path, model="test-model")
    first.invoke_fn = lambda _p: "ANSWER"
    first.invoke("PROMPT")

    second = LS.JudgmentCache(path=path, model="test-model")
    second.invoke_fn = lambda _p: pytest.fail("re-ran the model instead of replaying")
    assert second.invoke("PROMPT") == "ANSWER"
    assert (second.hits, second.misses) == (1, 0)


def test_cache_ignores_rows_written_by_a_different_model(tmp_path):
    path = tmp_path / "judgments.jsonl"
    path.write_text(json.dumps({"prompt_sha256": LS.JudgmentCache.key("PROMPT"),
                                "model": "some-other-model",
                                "response": "STALE"}) + "\n")
    cache = LS.JudgmentCache(path=path, model="test-model", allow_calls=False)
    with pytest.raises(LS.CacheMiss):
        cache.invoke("PROMPT")


def test_cache_refuses_to_invent_an_answer_when_calls_are_off(tmp_path):
    cache = LS.JudgmentCache(path=tmp_path / "none.jsonl", model="m",
                             allow_calls=False)
    cache.for_date("2026-01-05")
    with pytest.raises(LS.CacheMiss) as exc:
        cache.invoke("PROMPT")
    assert "2026-01-05" in str(exc.value)


# ── §2e same-ticker collisions ───────────────────────────────────────────────

def test_collisions_are_detected_per_ticker():
    cands = [make_candidate("NVDA"), make_candidate("NVDA"), make_candidate("AMD")]
    assert LS.ticker_collisions(cands) == {"NVDA": 2}


def test_a_collided_verdict_annotates_neither_play():
    a, b, other = make_candidate("NVDA"), make_candidate("NVDA"), make_candidate("AMD")
    for c in (a, b, other):
        c.trigger_verdict = "no"
        c.demoted = True
        c.demote_reasons = ["trigger has not fired"]

    LS.strip_collided_verdicts([a, b, other], {"NVDA": 2})

    assert (a.trigger_verdict, a.demoted, a.demote_reasons) == (None, False, [])
    assert (b.trigger_verdict, b.demoted, b.demote_reasons) == (None, False, [])
    # The uncollided candidate keeps its verdict — this is a targeted blank, not
    # a blanket one.
    assert other.demoted is True


# ── G6 ───────────────────────────────────────────────────────────────────────

def test_g6_passes_when_every_deployed_ticker_was_a_survivor():
    assert LS.g6_violations({"NVDA", "AMD"}, ["NVDA"]) == []


def test_g6_fires_on_a_ticker_rank_never_cleared():
    """A promotion is the one thing the model layer is forbidden to do."""
    assert LS.g6_violations({"NVDA"}, ["NVDA", "TSLA"]) == ["TSLA"]


# ── ladder divergence ────────────────────────────────────────────────────────

def test_the_missing_credit_veto_is_attributed_to_1_3():
    rec = make_rec(structure="bull_put_spread", market_regime="RANGE + L-VOL",
                   delta=-0.15, dte=45.0)
    rows = LS.ladder_divergence([rec], entry_check="ibkr_verified")
    assert len(rows) == 1
    assert rows[0]["cause"] == LS.CAUSE_CREDIT_VETO
    assert (rows[0]["book_tier"], rows[0]["map_tier"]) == ("B", "VETO")


def test_an_agreeing_row_is_not_reported_as_a_divergence():
    rec = make_rec(structure="bull_call_spread", market_regime="RANGE + E-VOL",
                   delta=0.4, dte=45.0)
    assert LS.ladder_divergence([rec], entry_check="ibkr_verified") == []


def test_withholding_the_delta_moves_rows_into_the_3_bucket_not_the_1_3_one():
    rec = make_rec(structure="bull_put_spread", market_regime="BULL + E-VOL",
                   delta=0.55, dte=45.0)
    verified = LS.ladder_divergence([rec], entry_check="ibkr_verified")
    blind = LS.ladder_divergence([rec], entry_check="analysis_only")
    assert verified == []                       # both ladders say Tier C
    assert [r["cause"] for r in blind] == [LS.CAUSE_DELTA]


# ── artifacts and the runner ─────────────────────────────────────────────────

def test_the_arm_writes_its_own_positions_csv():
    stem, arm = positions_artifact(compounding=False, structure_universe=False,
                                   live_select=True)
    assert stem == "account_sim-positions-live-select-latest.csv"
    assert arm == "RF1-live-select"


def test_the_frozen_positions_csv_name_is_unchanged():
    assert positions_artifact(compounding=False, structure_universe=False) == (
        "account_sim-positions-latest.csv", "RF1")


def test_live_select_is_filed_under_its_own_report_stem_with_no_extra_arms():
    """Filing it as `account_sim` would overwrite the frozen book's report, and
    letting the compounding arm run would overwrite that arm's."""
    plan = study_runner.arm_plan("account_sim", ["--live-select"])
    assert [stem for stem, _args, _charts in plan] == ["account_sim-live-select"]
    assert plan[0][2] == ()


def test_a_plain_account_sim_run_still_gets_its_compounding_arm():
    plan = study_runner.arm_plan("account_sim", [])
    assert [stem for stem, _args, _charts in plan] == [
        "account_sim", "account_sim-compounding"]


def test_live_select_is_infrastructure_not_a_study():
    """A study module needs a catalog verdict; this one carries none because it
    asks no question of its own."""
    from scripts.study_map import catalog
    assert "live_select" in study_runner.INFRA
    assert "live_select" not in study_runner.discover()
    assert "live_select.py" in catalog.INFRA
