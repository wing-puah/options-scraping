"""scripts/journal/lib/repair.py — the TradeJournal row repair (2026-09-22).

What is pinned: a duplicate fill keeps its first row; a pre-fix CLOSE row takes
the re-run's label, match and tier while its money columns must not move; the
repair is idempotent; a missing pull refuses; Drive's copy is replaced only
after it is saved beside itself; and the containment checks the apply relies on.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone

import pytest

from scripts.journal import s05_writer as writer
from scripts.journal.config import JOURNAL_COLUMNS, Leg, PositionEvent
from scripts.journal.lib import drive_sync, repair
from scripts.journal.s02_reconcile import CLOSE_ORIENTED_NOTE

from tests.test_journal_drive_sync import history_drive


def _leg(conid, qty, strike):
    return Leg(conid=conid, symbol="GLD", expiry=date(2026, 10, 16), strike=strike,
               right="C", qty=qty, fill_price=5.0, commission=1.0,
               exec_id=f"e{conid}",
               fill_time=datetime(2026, 8, 28, 14, 30, tzinfo=timezone.utc),
               open_close="C")


def _close_event(**kw):
    """A closed bull call spread, as the FIXED reconcile names it."""
    base = dict(date="2026-08-28", trade_datetime_utc="2026-08-28T14:30:00+00:00",
                ticker="GLD", structure="bull_call_spread", action="CLOSE",
                legs=[_leg(1, -1, 405.0), _leg(2, 1, 440.0)], contracts=1,
                net_price=-7.5, commission=2.0, net_cash=748.0, realized_pnl=120.0,
                dte_at_entry=49.0, match_confidence="STRUCTURE",
                ac_play="bull call spread 430/450", ac_structure="bull_call_spread",
                tier="B", tier_reason="other bull_call_spread", tier_verified=True,
                notes=f"{CLOSE_ORIENTED_NOTE} (bull_call_spread), read from ...",
                source_ref="ibkr-2026-08-28-1342.json:e1,e2")
    base.update(kw)
    return PositionEvent(**base)


def _as_csv_row(ev):
    """What the CSV holds: every value rendered as DictWriter renders it."""
    return {k: ("" if v == "" else str(v)) for k, v in writer.to_row(ev).items()}


def _prefix_row(**kw):
    """The same fills as journalled BEFORE the fix: mirror label, VETO, no note."""
    row = _as_csv_row(_close_event())
    row.update(structure="bear_call_spread", match_confidence="NONE", ac_play="",
               ac_structure="", tier="VETO", tier_reason="bear_call_spread intake veto",
               notes="")
    row.update(kw)
    return row


def _events(*evs):
    table = {}
    for ev in evs:
        table.setdefault(repair._pull_of(ev.source_ref), {})[
            writer.fill_identity(ev.source_ref)] = ev
    return lambda pull: table.get(pull)


def test_a_prefix_close_takes_the_rerun_label_match_and_tier():
    p = repair.plan([_prefix_row()], _events(_close_event()))
    changed = {c.column: (c.old, c.new) for c in p.changes}
    assert changed["structure"] == ("bear_call_spread", "bull_call_spread")
    assert changed["tier"] == ("VETO", "B")
    assert changed["match_confidence"] == ("NONE", "STRUCTURE")
    assert p.rows[0]["structure"] == "bull_call_spread"
    assert CLOSE_ORIENTED_NOTE in p.rows[0]["notes"]
    assert not p.unrepairable


def test_duplicate_fills_keep_the_first_row_only():
    first = _prefix_row()
    dup = _prefix_row(source_ref="ibkr-2026-08-28-1518.json:e2,e1")
    p = repair.plan([first, dup], _events(_close_event()))
    assert len(p.rows) == 1
    assert [(i, kept) for i, _row, kept in p.deleted] == [(2, 1)]
    assert p.rows[0]["source_ref"].startswith("ibkr-2026-08-28-1342.json")


def test_the_repair_is_idempotent():
    p = repair.plan([_prefix_row(), _prefix_row(source_ref="x.json:e1,e2")],
                    _events(_close_event()))
    again = repair.plan(p.rows, _events(_close_event()))
    assert again.empty
    assert again.rows == p.rows


def test_a_postfix_close_and_an_open_are_never_reconciled_again():
    def boom(pull):
        raise AssertionError("must not re-run reconcile")
    post = _as_csv_row(_close_event())
    opened = _as_csv_row(_close_event(action="OPEN", notes="",
                                      source_ref="p.json:e7"))
    assert repair.plan([post, opened], boom).empty


def test_a_missing_pull_is_refused_not_skipped():
    p = repair.plan([_prefix_row()], lambda pull: None)
    assert len(p.unrepairable) == 1
    assert "not available" in p.unrepairable[0][2]
    assert p.rows[0]["structure"] == "bear_call_spread"   # left as it was


def test_a_rerun_that_moves_the_money_is_refused():
    p = repair.plan([_prefix_row()], _events(_close_event(net_cash=1.0)))
    assert p.unrepairable and "net_cash" in p.unrepairable[0][2]
    assert not p.changes


def test_merge_appends_only_fills_local_lacks():
    local = [_prefix_row()]
    other = [_prefix_row(source_ref="d.json:e1,e2"),
             _prefix_row(source_ref="d.json:e9")]
    merged, added = repair.merge_rows(local, other)
    assert added == 1
    assert merged[-1]["source_ref"] == "d.json:e9"


def test_merge_refuses_a_regrouped_fill():
    with pytest.raises(repair.RepairRefused):
        repair.merge_rows([_prefix_row()], [_prefix_row(source_ref="d.json:e2,e3")])


def test_missing_from_names_fills_the_csv_lacks():
    rows = [_prefix_row()]
    assert repair.missing_from(rows, [{"source_ref": "tab.json:e1,e2"}]) == []
    assert repair.missing_from(rows, [{"source_ref": "tab.json:e5"}]) == ["tab.json:e5"]


def test_typed_row_restores_numbers_and_booleans():
    t = repair.typed_row(_as_csv_row(_close_event()))
    assert t["net_cash"] == 748.0 and t["contracts"] == 1
    assert t["tier_verified"] is True
    assert t["date"] == "2026-08-28"
    assert list(t) == JOURNAL_COLUMNS


def test_write_rows_round_trips(tmp_path):
    path = tmp_path / "trades.csv"
    rows = [_as_csv_row(_close_event())]
    repair.write_rows(rows, path)
    with open(path, newline="", encoding="utf-8") as fh:
        assert list(csv.DictReader(fh)) == rows


def test_replace_drive_keeps_the_previous_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(drive_sync, "DRIVE_STAGE_DIR", tmp_path / "drive")
    cli = history_drive({"trades.csv": "old,rows\n"})
    local = tmp_path / "trades.csv"
    local.write_text("new,rows\n", encoding="utf-8")
    repair.replace_drive(cli, local, "20260922T000000Z")
    assert cli.files["trades.csv"] == "new,rows\n"
    assert cli.files["trades-pre-repair-20260922T000000Z.csv"] == "old,rows\n"
    # the next run's pull sees nothing to reconcile
    assert drive_sync.relation(local.read_text(), cli.files["trades.csv"]) == "same"
