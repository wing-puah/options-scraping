"""
Tests for scripts/journal/recwriter.py — the deploy card's persisted record.

Offline throughout: every write passes `skip_sheets=True` and an explicit
`csv_path` under tmp_path, so nothing here touches Sheets or the real
journal/recommendations.csv.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from journal import recwriter as rw
from journal.config import (RECOMMENDATION_COLUMNS, REC_IDENTITY_EXCLUDED,
                            RecContext)
from journal.recommend import Candidate, Rejected

SESSION = "2026-08-14"
AS_OF = "2026-08-15"
T1 = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc)


def _cand(ticker="NVDA", role="deploy", **kw):
    base = dict(
        ticker=ticker, play="Bull call spread 235/270, 60-90 DTE",
        structure="bull_call_spread", market_regime="RANGE + E-VOL",
        tier="A", tier_partial=False, tier_reason="§2 debit vertical",
        score_total=41.0, horizon="60d", trigger="close above 235",
        invalidation="close below 218", alternative_interpretation="collar",
        role=role, deploy=True,
    )
    base.update(kw)
    return Candidate(**base)


def _ctx(**kw):
    base = dict(session_date=SESSION, as_of_date=AS_OF, staleness_days=1,
                analysis_source="sheets", book_evaluable=True, generated_at=T1)
    base.update(kw)
    return RecContext(**base)


def _write(candidates, rejected, ctx, path, **kw):
    return rw.write(candidates, rejected, ctx, skip_sheets=True,
                    csv_path=path, **kw)


# --------------------------------------------------------------------------
# Row shape
# --------------------------------------------------------------------------
def test_to_rows_emits_exactly_the_contract_columns_in_order():
    rows = rw.to_rows([_cand()], [], _ctx())
    assert [list(r) for r in rows] == [RECOMMENDATION_COLUMNS]


def test_every_role_is_represented_and_rejected_rows_carry_no_rank():
    rows = rw.to_rows(
        [_cand("NVDA"), _cand("TLT", role="hedge", deploy=False)],
        [Rejected("XOM", "Bear call", "bear_call_spread", "RANGE", "VETO", "§1.2"),
         Rejected("MU", "Bull call", "bull_call_spread", "RANGE", "C", "capital")],
        _ctx())
    by_role = {r["role"]: r for r in rows}
    assert set(by_role) == {"deploy", "hedge", "veto", "tier_c"}
    assert by_role["deploy"]["rank"] == 1
    assert by_role["hedge"]["rank"] == 1      # ranked within its own role
    assert by_role["veto"]["rank"] == ""      # blank, not 0
    assert by_role["tier_c"]["rank"] == ""


def test_blanks_none_but_keeps_a_real_zero_and_false():
    rows = rw.to_rows([_cand(score_total=0.0, delta=0.0, deploy=False,
                             duplicate_exposure=False)], [], _ctx())
    row = rows[0]
    assert row["score_total"] == 0.0
    assert row["delta"] == 0.0
    assert row["deploy"] is False
    assert row["duplicate_exposure"] is False   # book WAS evaluable
    assert row["horizon"] == "60d"


def test_deploy_role_is_ranked_in_list_order():
    rows = rw.to_rows([_cand("AAA"), _cand("BBB"), _cand("CCC")], [], _ctx())
    assert [(r["ticker"], r["rank"]) for r in rows] == [
        ("AAA", 1), ("BBB", 2), ("CCC", 3)]


def test_a_demoted_candidate_keeps_its_deterministic_rank():
    """The model may annotate; it may never promote. `rank` is the ranker's own
    list position and a judge demotion must not move it."""
    demoted = _cand("BBB", demoted=True, trigger_verdict="no",
                    demote_reasons=["trigger has not fired"])
    rows = rw.to_rows([_cand("AAA"), demoted], [], _ctx(judge_status="ran"))
    ranks = {r["ticker"]: r["rank"] for r in rows}
    assert ranks == {"AAA": 1, "BBB": 2}
    assert [r for r in rows if r["ticker"] == "BBB"][0]["demoted"] is True


# --------------------------------------------------------------------------
# The blank-vs-false seam
# --------------------------------------------------------------------------
def test_book_derived_verdicts_are_blank_when_the_book_was_not_evaluable():
    """With no book, rank() stamps duplicate_exposure=False on everything —
    which would read as 'checked and clear'. It must persist as unknown."""
    rows = rw.to_rows([_cand(duplicate_exposure=False, headroom_ok=None)],
                      [], _ctx(book_evaluable=False))
    assert rows[0]["duplicate_exposure"] == ""
    assert rows[0]["headroom_ok"] == ""
    assert rows[0]["book_evaluable"] is False


def test_book_derived_verdicts_survive_when_the_book_was_evaluable():
    rows = rw.to_rows([_cand(duplicate_exposure=True, headroom_ok=False)],
                      [], _ctx(book_evaluable=True))
    assert rows[0]["duplicate_exposure"] is True
    assert rows[0]["headroom_ok"] is False


def test_judge_columns_are_blank_when_the_pass_did_not_run():
    row = rw.to_rows([_cand()], [], _ctx(judge_status="not_run"))[0]
    assert row["judge_ran"] is False
    assert row["judge_status"] == "not_run"
    assert row["judge_model"] == ""
    assert row["judge_lookahead_risk"] == ""


def test_a_judged_card_records_the_model_and_its_lookahead_caveat():
    row = rw.to_rows([_cand()], [], _ctx(judge_status="ran"))[0]
    assert row["judge_ran"] is True
    assert row["judge_model"]
    assert "cutoff" in row["judge_lookahead_risk"]


def test_a_failed_judge_pass_is_distinguishable_from_one_never_run():
    row = rw.to_rows([_cand()], [], _ctx(judge_status="failed"))[0]
    assert row["judge_ran"] is False
    assert row["judge_status"] == "failed"


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
def test_content_hash_ignores_identity_and_wall_clock():
    a = rw.to_rows([_cand()], [], _ctx(generated_at=T1))[0]
    b = rw.to_rows([_cand()], [], _ctx(generated_at=T2))[0]
    assert a["generated_at_utc"] != b["generated_at_utc"]
    assert rw.content_hash(a) == rw.content_hash(b)
    assert a["rec_id"] == b["rec_id"]


def test_identity_excluded_columns_are_actually_excluded():
    row = rw.to_rows([_cand()], [], _ctx())[0]
    base = rw.content_hash(row)
    for col in REC_IDENTITY_EXCLUDED:
        mutated = dict(row, **{col: "something-else"})
        assert rw.content_hash(mutated) == base, col


def test_a_changed_verdict_changes_the_identity():
    a = rw.to_rows([_cand()], [], _ctx())[0]
    b = rw.to_rows([_cand(headroom_ok=False)], [], _ctx())[0]
    assert a["rec_id"] != b["rec_id"]


def test_rec_id_is_readable_at_the_front():
    row = rw.to_rows([_cand()], [], _ctx())[0]
    assert row["rec_id"].startswith(f"{SESSION}|{AS_OF}|deploy|NVDA|bull_call_spread|")


# --------------------------------------------------------------------------
# Write / dedup / generations
# --------------------------------------------------------------------------
def test_write_is_idempotent_across_reruns(tmp_path):
    p = tmp_path / "rec.csv"
    first = _write([_cand()], [], _ctx(), p)
    second = _write([_cand()], [], _ctx(generated_at=T2), p)
    assert first["csv_written"] == 1
    assert second["csv_written"] == 0
    assert second["skipped_duplicate"] == 1
    assert len(rw.read_csv_rows(p)) == 1


def test_a_changed_judge_verdict_appends_a_new_generation(tmp_path):
    p = tmp_path / "rec.csv"
    _write([_cand()], [], _ctx(), p)
    _write([_cand(trigger_verdict="no", demoted=True)], [],
           _ctx(judge_status="ran", generated_at=T2), p)
    rows = rw.read_csv_rows(p)
    assert [r["generation"] for r in rows] == ["1", "2"]
    # the first row is left exactly as it was
    assert rows[0]["judge_status"] == "not_run"


def test_a_changed_book_appends_a_new_generation(tmp_path):
    p = tmp_path / "rec.csv"
    _write([_cand(headroom_ok=True)], [], _ctx(), p)
    _write([_cand(headroom_ok=False)], [], _ctx(generated_at=T2), p)
    assert [r["generation"] for r in rw.read_csv_rows(p)] == ["1", "2"]


def test_generations_are_counted_per_play_not_per_file(tmp_path):
    p = tmp_path / "rec.csv"
    _write([_cand("AAA"), _cand("BBB")], [], _ctx(), p)
    _write([_cand("AAA", headroom_ok=False), _cand("BBB", headroom_ok=False)],
           [], _ctx(generated_at=T2), p)
    gens = {(r["ticker"], r["generation"]) for r in rw.read_csv_rows(p)}
    assert gens == {("AAA", "1"), ("AAA", "2"), ("BBB", "1"), ("BBB", "2")}


def test_write_refuses_rows_that_cannot_be_deduplicated(tmp_path, monkeypatch):
    monkeypatch.setattr(rw, "rec_id", lambda row: "")
    with pytest.raises(ValueError, match="rec_id"):
        _write([_cand()], [], _ctx(), tmp_path / "rec.csv")


def test_dry_run_writes_nothing(tmp_path):
    p = tmp_path / "rec.csv"
    summary = _write([_cand()], [], _ctx(), p, dry_run=True)
    assert summary["would_write"] == 1
    assert summary["csv_written"] == 0
    assert not p.exists()


def test_no_candidates_writes_nothing(tmp_path):
    p = tmp_path / "rec.csv"
    assert _write([], [], _ctx(), p)["csv_written"] == 0
    assert not p.exists()


def test_an_explicit_csv_path_never_touches_the_real_record(tmp_path):
    from journal.config import RECOMMENDATIONS_CSV
    p = tmp_path / "rec.csv"
    _write([_cand()], [], _ctx(), p)
    assert p.exists()
    assert p != RECOMMENDATIONS_CSV


# --------------------------------------------------------------------------
# Sheets: ordering, and the failure contract
# --------------------------------------------------------------------------
class _FakeSheets:
    """Records the order of calls, so the tab-width ordering can be asserted."""

    def __init__(self):
        self.calls = []
        self.sent = []

    def ensure_tab(self, tab, min_cols=0, spreadsheet_id=None):
        self.calls.append(("ensure_tab", tab, min_cols))

    def get_all_rows(self, tab, spreadsheet_id=None):
        self.calls.append(("get_all_rows", tab, None))
        return []

    def append_rows(self, tab, rows, raw=False, spreadsheet_id=None):
        self.calls.append(("append_rows", tab, len(rows)))
        self.sent.extend(rows)

    def set_meta(self, tab, fingerprint="", last_row_time="", spreadsheet_id=None):
        self.calls.append(("set_meta", tab, None))

    def compute_batch_fingerprint(self, rows, key_cols):
        return "fp"


@pytest.fixture
def fake_sheets(monkeypatch):
    fake = _FakeSheets()
    monkeypatch.setattr(rw, "sheets_client", fake)
    monkeypatch.setenv("TRADE_JOURNAL_SPREADSHEET_ID", "sheet-id")
    return fake


def test_the_tab_is_sized_to_the_schema_before_anything_reads_it(tmp_path, fake_sheets):
    """get_all_rows creates a missing tab at the 30-column default, and
    append_rows' own min_cols only applies to a tab IT creates — so a read
    before the ensure would leave this schema's trailing columns truncated."""
    rw.write([_cand()], [], _ctx(), csv_path=tmp_path / "rec.csv")
    names = [c[0] for c in fake_sheets.calls]
    assert names.index("ensure_tab") < names.index("get_all_rows")
    ensure = [c for c in fake_sheets.calls if c[0] == "ensure_tab"][0]
    assert ensure[2] == len(RECOMMENDATION_COLUMNS)


def test_rows_reach_sheets_in_contract_order(tmp_path, fake_sheets):
    rw.write([_cand()], [], _ctx(), csv_path=tmp_path / "rec.csv")
    assert list(fake_sheets.sent[0]) == RECOMMENDATION_COLUMNS


def test_a_sheets_failure_is_reported_but_never_loses_the_local_row(tmp_path, monkeypatch):
    class Boom(_FakeSheets):
        def append_rows(self, *a, **kw):
            raise RuntimeError("sheets is down")

    monkeypatch.setattr(rw, "sheets_client", Boom())
    monkeypatch.setenv("TRADE_JOURNAL_SPREADSHEET_ID", "sheet-id")
    p = tmp_path / "rec.csv"
    summary = rw.write([_cand()], [], _ctx(), csv_path=p)
    assert "sheets is down" in summary["sheets_error"]
    assert summary["csv_written"] == 1
    assert len(rw.read_csv_rows(p)) == 1


def test_a_missing_spreadsheet_id_writes_locally_and_says_so(tmp_path, monkeypatch):
    monkeypatch.delenv("TRADE_JOURNAL_SPREADSHEET_ID", raising=False)
    p = tmp_path / "rec.csv"
    summary = rw.write([_cand()], [], _ctx(), csv_path=p)
    assert summary["csv_written"] == 1
    assert "TRADE_JOURNAL_SPREADSHEET_ID" in summary["sheets_error"]


# --------------------------------------------------------------------------
# Reading back
# --------------------------------------------------------------------------
def test_read_csv_rows_tolerates_a_missing_file(tmp_path):
    assert rw.read_csv_rows(tmp_path / "nope.csv") == []


def test_read_csv_rows_tolerates_a_corrupt_file(tmp_path):
    p = tmp_path / "rec.csv"
    p.write_bytes(b"\xff\xfe not a csv at all \x00")
    assert isinstance(rw.read_csv_rows(p), list)


def _row(session, ticker, generation, role="deploy", rank="1"):
    return {"session_date": session, "role": role, "ticker": ticker,
            "structure": "s", "generation": generation, "rank": rank}


def test_recent_rows_drops_sessions_after_the_page_being_built():
    """A historical page rebuilt today must not show recommendations that did
    not exist on its session — the card's own no-lookahead rule, on the page."""
    rows = [_row("2026-08-12", "OLD", "1"), _row("2026-08-20", "FUTURE", "1")]
    out = rw.recent_rows(rows, on_or_before="2026-08-14")
    assert [r["ticker"] for r in out] == ["OLD"]


def test_recent_rows_keeps_only_the_current_generation():
    rows = [_row("2026-08-12", "AAA", "1"), _row("2026-08-12", "AAA", "2")]
    out = rw.recent_rows(rows, on_or_before="2026-08-14")
    assert [r["generation"] for r in out] == ["2"]


def test_recent_rows_limits_to_the_requested_session_count():
    rows = [_row(d, "AAA", "1") for d in
            ("2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13")]
    out = rw.recent_rows(rows, on_or_before="2026-08-14", sessions=2)
    assert sorted({r["session_date"] for r in out}) == ["2026-08-12", "2026-08-13"]


def test_recent_rows_on_an_empty_record():
    assert rw.recent_rows([], on_or_before="2026-08-14") == []


def test_recent_rows_survives_rows_with_no_session_date():
    assert rw.recent_rows([{"ticker": "AAA"}], on_or_before="2026-08-14") == []


def test_write_then_read_back_round_trips(tmp_path):
    p = tmp_path / "rec.csv"
    _write([_cand("AAA"), _cand("TLT", role="hedge", deploy=False)], [], _ctx(), p)
    out = rw.recent_rows(rw.read_csv_rows(p), on_or_before=AS_OF)
    assert {r["ticker"] for r in out} == {"AAA", "TLT"}
