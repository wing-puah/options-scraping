"""
Tests for scripts/journal/s05b_bookwriter.py — the open book's persisted record.

Offline throughout: every write passes `skip_sheets=True` and an explicit
`csv_path` under tmp_path, so nothing here touches Sheets or the real
journal/open_book.csv.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from journal import s05b_bookwriter as bw
from journal.s03_risk import BookRisk, Caps
from journal.config import (BOOK_FLAG_SEVERITY, BOOK_IDENTITY_EXCLUDED,
                            DELTA_SOURCE_BARCHART, DELTA_SOURCE_UNAVAILABLE,
                            OPEN_BOOK_COLUMNS, OPEN_BOOK_CSV, BookContext, Leg,
                            PositionRisk)

AS_OF = "2026-08-14"
T1 = datetime(2026, 8, 14, 21, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 8, 14, 23, 0, tzinfo=timezone.utc)


def _leg(conid=1, symbol="NVDA", expiry="2026-10-16", strike=235.0, right="C", qty=1):
    return Leg(conid=conid, symbol=symbol, expiry=date.fromisoformat(expiry),
               strike=strike, right=right, qty=qty, fill_price=8.0,
               commission=0.65, exec_id=f"e{conid}",
               fill_time=datetime(2026, 7, 1, 14, 30), open_close="O")


def _pos(ticker="NVDA", *, priced=True, legs=None, **kw):
    legs = legs if legs is not None else [_leg(), _leg(conid=2, strike=270.0, qty=-1)]
    base = dict(
        conid_key="|".join(str(lg.conid) for lg in sorted(legs, key=lambda lg: lg.conid)),
        ticker=ticker, structure="bull_call_spread", contracts=1, legs=legs,
        position_delta=0.25, delta_notional=4_000.0, underlying_price=160.0,
        short_leg_delta=0.30, iv=0.42,
        delta_source=DELTA_SOURCE_BARCHART, dte=63.0,
        entry_date=date(2026, 7, 1), exit_by=date(2026, 9, 20),
    )
    if not priced:
        base.update(position_delta=None, delta_notional=None,
                    delta_source=DELTA_SOURCE_UNAVAILABLE)
    base.update(kw)
    return PositionRisk(**base)


def _caps(net_liq=25_000.0):
    return Caps(per_position=0.25, net=2.50, net_liq=net_liq)


_UNSET = object()


def _book(positions=None, unpriced=None, caps=_UNSET, **kw):
    positions = [] if positions is None else positions
    unpriced = [] if unpriced is None else unpriced
    caps = _caps() if caps is _UNSET else caps
    base = dict(
        positions=positions, unpriced=unpriced, caps=caps,
        net_delta_notional=sum(p.delta_notional for p in positions),
        gross_delta_notional=sum(abs(p.delta_notional) for p in positions),
        ticker_exposure={}, breaches=[])
    base["ticker_exposure"] = {
        t: sum(p.delta_notional for p in positions if p.ticker == t)
        for t in sorted({p.ticker for p in positions})}
    base.update(kw)
    return BookRisk(**base)


def _ctx(**kw):
    base = dict(as_of_date=AS_OF, net_liq=25_000.0, book_source="ibkr-2026-08-14.json",
                book_reconstructed=True, snapshot_at=T1)
    base.update(kw)
    return BookContext(**base)


def _write(book, ctx, path, **kw):
    return bw.write(book, ctx, skip_sheets=True, csv_path=path, **kw)


# --------------------------------------------------------------------------
# Row shape
# --------------------------------------------------------------------------
def test_to_rows_emits_exactly_the_contract_columns_in_order():
    rows = bw.to_rows(_book([_pos()]), _ctx())
    assert [list(r) for r in rows] == [OPEN_BOOK_COLUMNS]


def test_an_empty_book_writes_nothing(tmp_path):
    summary = _write(_book([]), _ctx(), tmp_path / "b.csv")
    assert summary["positions"] == 0
    assert summary["csv_written"] == 0
    assert not (tmp_path / "b.csv").exists()


def test_priced_and_unpriced_positions_are_written_together():
    book = _book([_pos("NVDA")], unpriced=[_pos("AMD", priced=False)])
    rows = bw.to_rows(book, _ctx())
    assert [r["ticker"] for r in rows] == ["AMD", "NVDA"]
    assert [r["priced"] for r in rows] == [False, True]


def test_an_unpriced_position_gets_blank_marks_never_zero():
    rows = bw.to_rows(_book([], unpriced=[_pos(priced=False)]), _ctx())
    row = rows[0]
    assert row["position_delta"] == ""
    assert row["delta_notional"] == ""
    assert row["pct_net_liq"] == ""
    assert row["priced"] is False


def test_a_real_zero_delta_survives():
    """0.0 delta is a market fact; blanking it would lose a real measurement."""
    rows = bw.to_rows(_book([_pos(position_delta=0.0, delta_notional=0.0)]), _ctx())
    assert rows[0]["position_delta"] == 0.0
    assert rows[0]["delta_notional"] == 0.0
    assert rows[0]["priced"] is True


def test_pct_net_liq_is_derived_when_the_record_carries_none():
    rows = bw.to_rows(_book([_pos(delta_notional=2_500.0)]), _ctx(net_liq=25_000.0))
    assert rows[0]["pct_net_liq"] == pytest.approx(0.10)


def test_expiry_is_blank_when_the_legs_disagree():
    legs = [_leg(conid=1, expiry="2026-10-16"), _leg(conid=2, expiry="2026-11-20")]
    rows = bw.to_rows(_book([_pos(legs=legs)]), _ctx())
    assert rows[0]["expiry"] == ""


def test_days_to_exit_by_is_signed_against_the_as_of_date():
    rows = bw.to_rows(_book([_pos(exit_by=date(2026, 8, 10))]), _ctx())
    assert rows[0]["days_to_exit_by"] == -4


# --------------------------------------------------------------------------
# Triage — status and flags
# --------------------------------------------------------------------------
def _flags(pos, book=None, **kw):
    if book is None:
        book = (_book([pos]) if pos.priced else _book([], unpriced=[pos]))
    kw.setdefault("as_of", date.fromisoformat(AS_OF))
    return bw.flags_for(pos, book, **kw)


def test_a_clean_position_is_ok_with_no_flags():
    rows = bw.to_rows(_book([_pos()]), _ctx())
    assert rows[0]["flags"] == ""
    assert rows[0]["status"] == "OK"


def test_an_overdue_exit_is_attention():
    flags = _flags(_pos(exit_by=date(2026, 8, 1)))
    assert "EXIT_OVERDUE" in flags
    assert bw.status_for(flags) == "ATTENTION"


def test_an_exit_due_soon_is_watch_not_attention():
    flags = _flags(_pos(exit_by=date(2026, 8, 17)))
    assert flags == ["EXIT_DUE_SOON"]
    assert bw.status_for(flags) == "WATCH"


def test_an_exit_due_today_is_due_soon_not_overdue():
    flags = _flags(_pos(exit_by=date.fromisoformat(AS_OF)))
    assert flags == ["EXIT_DUE_SOON"]


def test_an_unpriced_position_names_which_half_is_missing():
    assert "UNPRICED_NO_DELTA" in _flags(_pos(priced=False))
    no_spot = _pos(delta_notional=None, underlying_price=None,
                   delta_source=DELTA_SOURCE_UNAVAILABLE)
    assert "UNPRICED_NO_SPOT" in _flags(no_spot)


def test_expiry_flags_split_at_the_threshold():
    assert "EXPIRING_SOON" in _flags(_pos(dte=7.0))
    assert "EXPIRING_SOON" not in _flags(_pos(dte=8.0))
    assert "EXPIRED" in _flags(_pos(dte=-1.0))


def test_a_ticker_over_its_cap_is_flagged_as_a_breach():
    # per-position cap = 0.25 x 25,000 = $6,250
    flags = _flags(_pos(), ticker_total=7_000.0)
    assert "TICKER_CAP_BREACH" in flags
    assert bw.status_for(flags) == "ATTENTION"


def test_a_ticker_near_its_cap_is_only_a_watch():
    flags = _flags(_pos(), ticker_total=5_200.0)   # 0.83 of $6,250
    assert flags == ["TICKER_CAP_NEAR"]
    assert bw.status_for(flags) == "WATCH"


def test_the_net_cap_is_flagged_on_every_row():
    """A net breach is a fact about the BOOK, so every row must carry it —
    filtering the tab to ATTENTION should surface the whole book, not one row."""
    book = _book([_pos("NVDA", delta_notional=40_000.0),
                  _pos("AMD", conid_key="3|4", delta_notional=40_000.0)])
    rows = bw.to_rows(book, _ctx())
    assert all("NET_CAP_BREACH" in r["flags"] for r in rows)


def test_missing_caps_are_reported_as_not_evaluable_never_as_clear():
    book = _book([_pos()], caps=None)
    rows = bw.to_rows(book, _ctx(net_liq=None))
    assert "CAPS_NOT_EVALUABLE" in rows[0]["flags"]
    assert rows[0]["ticker_cap_utilisation"] == ""


def test_a_book_that_never_reached_assess_still_totals_its_positions():
    """_build_book skips assess() when NetLiquidation is missing, leaving the
    dataclass defaults at 0.0 — writing that would state a flat book."""
    book = BookRisk(positions=[_pos(delta_notional=4_000.0)], unpriced=[], caps=None)
    assert book.net_delta_notional == 0.0
    rows = bw.to_rows(book, _ctx(net_liq=None))
    assert rows[0]["ticker_delta_notional"] == 4_000.0
    # The net is not a column any more, but it still feeds the net-cap flags,
    # so the recompute must still see the real positions rather than the 0.0.
    assert bw._net_delta_notional(book) == 4_000.0


def test_mixed_entry_dates_and_an_unclassified_structure_are_watched():
    assert "MIXED_ENTRY_DATES" in _flags(_pos(entry_date_mixed=True))
    assert "UNCLASSIFIED_STRUCTURE" in _flags(_pos(structure="unclassified"))


def test_a_split_calendar_is_marked_on_both_rows_but_stays_ok():
    """SPLIT_EXPIRY is INFO: lib/book.py splits a calendar for presentation and
    says so — it changes neither a total nor a cap verdict."""
    near = _pos(conid_key="1|2", delta_notional=1_000.0,
                legs=[_leg(conid=1, expiry="2026-09-18"),
                      _leg(conid=2, expiry="2026-09-18", qty=-1)])
    far = _pos(conid_key="3|4", delta_notional=-1_000.0,
               legs=[_leg(conid=3, expiry="2026-12-18"),
                     _leg(conid=4, expiry="2026-12-18", qty=-1)])
    rows = bw.to_rows(_book([near, far]), _ctx())
    assert all("SPLIT_EXPIRY" in r["flags"] for r in rows)
    assert all(r["status"] == "OK" for r in rows)


def test_flags_are_ordered_worst_first():
    flags = _flags(_pos(exit_by=date(2026, 8, 1), entry_date_mixed=True,
                        structure="unclassified"),
                   ticker_total=7_000.0)
    severities = [BOOK_FLAG_SEVERITY[f] for f in flags]
    assert severities == sorted(severities, key=["ATTENTION", "WATCH", "INFO"].index)


def test_the_emitted_flags_are_exactly_the_declared_ones():
    """A token missing from BOOK_FLAG_SEVERITY would silently default to WATCH;
    one declared but never emitted is a stale entry in the vocabulary."""
    import re
    src = Path(bw.__file__).read_text(encoding="utf-8")
    literals = set(re.findall(r'"([A-Z][A-Z_]{3,})"', src))
    assert literals - set(bw._SEVERITY_RANK) == set(BOOK_FLAG_SEVERITY)


def test_an_unparseable_as_of_emits_no_date_flags():
    """Rather than measuring a replayed snapshot against today."""
    rows = bw.to_rows(_book([_pos(exit_by=date(2020, 1, 1))]), _ctx(as_of_date="not-a-date"))
    assert "EXIT_OVERDUE" not in rows[0]["flags"]
    assert rows[0]["days_to_exit_by"] == ""


# --------------------------------------------------------------------------
# Identity and generations
# --------------------------------------------------------------------------
def test_content_hash_ignores_identity_and_wall_clock():
    a = bw.to_rows(_book([_pos()]), _ctx(snapshot_at=T1))[0]
    b = bw.to_rows(_book([_pos()]), _ctx(snapshot_at=T2))[0]
    assert a["snapshot_utc"] != b["snapshot_utc"]
    assert bw.content_hash(a) == bw.content_hash(b)
    assert a["book_id"] == b["book_id"]


def test_identity_excluded_columns_are_actually_excluded():
    row = bw.to_rows(_book([_pos()]), _ctx())[0]
    base = bw.content_hash(row)
    for col in BOOK_IDENTITY_EXCLUDED:
        assert bw.content_hash({**row, col: "changed"}) == base


def test_a_changed_mark_changes_the_identity():
    a = bw.to_rows(_book([_pos(delta_notional=4_000.0)]), _ctx())[0]
    b = bw.to_rows(_book([_pos(delta_notional=4_500.0)]), _ctx())[0]
    assert a["book_id"] != b["book_id"]


def test_book_id_is_readable_at_the_front():
    row = bw.to_rows(_book([_pos()]), _ctx())[0]
    assert row["book_id"].startswith(f"{AS_OF}|NVDA|2026-10-16|bull_call_spread|")


def test_write_is_idempotent_across_reruns(tmp_path):
    p = tmp_path / "b.csv"
    first = _write(_book([_pos()]), _ctx(), p)
    second = _write(_book([_pos()]), _ctx(snapshot_at=T2), p)
    assert first["csv_written"] == 1
    assert second["csv_written"] == 0
    assert second["skipped_duplicate"] == 1
    assert len(bw.read_csv_rows(p)) == 1


def test_a_re_marked_book_appends_a_new_generation(tmp_path):
    p = tmp_path / "b.csv"
    _write(_book([_pos(delta_notional=4_000.0)]), _ctx(), p)
    _write(_book([_pos(delta_notional=5_000.0)]), _ctx(snapshot_at=T2), p)
    rows = bw.read_csv_rows(p)
    assert [r["generation"] for r in rows] == ["1", "2"]
    assert [r["delta_notional"] for r in rows] == ["4000.0", "5000.0"]


def test_a_later_session_starts_a_new_days_generation_not_a_bump(tmp_path):
    p = tmp_path / "b.csv"
    _write(_book([_pos()]), _ctx(), p)
    _write(_book([_pos()]), _ctx(as_of_date="2026-08-15"), p)
    assert [r["generation"] for r in bw.read_csv_rows(p)] == ["1", "1"]


def test_a_re_mark_appends_only_the_position_that_moved(tmp_path):
    """No row carries a book-level total any more, so an untouched position's
    content hash does not move when its neighbour is re-marked. Only the
    moved row appends; `latest_snapshot` reads the newest generation PER
    POSITION, so the current book is still whole."""
    p = tmp_path / "b.csv"
    nvda, amd = _pos("NVDA"), _pos("AMD", conid_key="3|4")
    _write(_book([nvda, amd]), _ctx(), p)
    _write(_book([_pos("NVDA", delta_notional=9.0), amd]), _ctx(snapshot_at=T2), p)
    rows = bw.read_csv_rows(p)
    assert [(r["ticker"], r["generation"]) for r in rows] == [
        ("AMD", "1"), ("NVDA", "1"), ("NVDA", "2")]
    snapshot = bw.latest_snapshot(rows)
    assert [(r["ticker"], r["generation"]) for r in snapshot] == [
        ("AMD", "1"), ("NVDA", "2")]


def test_a_flipped_net_cap_flag_still_re_marks_the_rows_it_lands_on(tmp_path):
    """The net cap left the columns but not the row: it reaches the tab as a
    flag, and a flag is content, so a breach appearing re-appends every row
    that now carries it."""
    p = tmp_path / "b.csv"
    nvda, amd = _pos("NVDA"), _pos("AMD", conid_key="3|4")
    _write(_book([nvda, amd]), _ctx(), p)
    _write(_book([_pos("NVDA", delta_notional=70_000.0), amd]),
           _ctx(snapshot_at=T2), p)
    rows = bw.read_csv_rows(p)
    assert [(r["ticker"], r["generation"]) for r in rows] == [
        ("AMD", "1"), ("NVDA", "1"), ("AMD", "2"), ("NVDA", "2")]
    assert all("NET_CAP_BREACH" in r["flags"] for r in rows if r["generation"] == "2")


# --------------------------------------------------------------------------
# Column order — the layout is a claim the operator made, so it is tested
# --------------------------------------------------------------------------
_BOOK_LEVEL = {"per_position_cap_usd", "net_delta_notional", "net_cap_usd",
               "net_utilisation", "net_headroom", "book_complete",
               "book_positions", "book_unpriced", "book_breaches", "net_liq",
               "book_reconstructed", "notes", "ticker_positions",
               "entry_date_mixed"}


def test_status_and_flags_lead_and_the_two_acted_on_numbers_are_in_the_first_eight():
    assert OPEN_BOOK_COLUMNS[:3] == ["as_of_date", "status", "flags"]
    assert OPEN_BOOK_COLUMNS.index("delta_notional") < 8
    assert OPEN_BOOK_COLUMNS.index("exit_by") < 8
    assert OPEN_BOOK_COLUMNS.index("delta_notional") < OPEN_BOOK_COLUMNS.index("legs")
    assert OPEN_BOOK_COLUMNS.index("exit_by") < OPEN_BOOK_COLUMNS.index("legs")


def test_nothing_book_level_is_written_and_identity_comes_last():
    assert not _BOOK_LEVEL & set(OPEN_BOOK_COLUMNS)
    assert OPEN_BOOK_COLUMNS[-5:] == ["book_id", "generation", "conid_key",
                                      "book_source", "snapshot_utc"]


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
def test_append_csv_widens_a_strict_prefix_header_and_blank_fills_old_rows(tmp_path):
    p = tmp_path / "b.csv"
    short = OPEN_BOOK_COLUMNS[:-3]
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=short)
        w.writeheader()
        w.writerow({c: "x" for c in short})
    bw.append_csv(bw.to_rows(_book([_pos()]), _ctx()), p)
    rows = bw.read_csv_rows(p)
    assert len(rows) == 2
    assert list(rows[0]) == OPEN_BOOK_COLUMNS
    assert rows[0][OPEN_BOOK_COLUMNS[-1]] == ""


def test_append_csv_refuses_a_header_matching_neither_the_schema_nor_a_prefix(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text("wat,who\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="refusing to append"):
        bw.append_csv(bw.to_rows(_book([_pos()]), _ctx()), p)


def _old_layout_file(p, rows):
    """A file written under the ORIGINAL 41-column layout: the same columns in
    a different order, plus book-level ones that no longer exist."""
    old_cols = (["as_of_date", "status", "flags", "book_id", "generation",
                 "conid_key", "ticker", "structure", "contracts", "legs",
                 "expiry", "dte", "entry_date", "entry_date_mixed", "exit_by",
                 "days_to_exit_by", "priced", "position_delta", "delta_notional",
                 "pct_net_liq", "underlying_price", "short_leg_delta", "iv",
                 "delta_source", "ticker_delta_notional", "ticker_positions",
                 "ticker_cap_utilisation", "per_position_cap_usd",
                 "net_delta_notional", "net_cap_usd", "net_utilisation",
                 "net_headroom", "book_complete", "book_positions",
                 "book_unpriced", "book_breaches", "net_liq", "book_source",
                 "book_reconstructed", "snapshot_utc", "notes"])
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=old_cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "book-level") for c in old_cols})
    return old_cols


def test_a_reordered_layout_is_rewritten_by_name_and_dropped_columns_go(tmp_path):
    p = tmp_path / "b.csv"
    today = bw.to_rows(_book([_pos()]), _ctx())[0]
    _old_layout_file(p, [dict(today, book_id="2026-08-14|NVDA|x|y|deadbeef0000",
                              generation="1")])
    bw.append_csv(bw.to_rows(_book([_pos("AMD", conid_key="3|4")]),
                             _ctx(snapshot_at=T2)), p)
    rows = bw.read_csv_rows(p)
    assert [list(r) for r in rows] == [OPEN_BOOK_COLUMNS, OPEN_BOOK_COLUMNS]
    assert rows[0]["ticker"] == "NVDA" and rows[0]["delta_notional"] == "4000.0"
    assert "notes" not in rows[0] and "net_headroom" not in rows[0]


def test_the_migration_recomputes_book_ids_so_a_rerun_still_deduplicates(tmp_path):
    """A layout change moves the content hash. Left as written, every old row
    would look new to the next run and the whole book would re-append."""
    p = tmp_path / "b.csv"
    today = bw.to_rows(_book([_pos()]), _ctx())[0]
    _old_layout_file(p, [dict(today, book_id="stale|id|under|old|layout",
                              generation="1")])
    summary = _write(_book([_pos()]), _ctx(snapshot_at=T2), p)
    assert summary["csv_written"] == 0
    assert summary["skipped_duplicate"] == 1
    rows = bw.read_csv_rows(p)
    assert len(rows) == 1
    assert rows[0]["book_id"] == today["book_id"]


def test_dry_run_writes_nothing(tmp_path):
    p = tmp_path / "b.csv"
    summary = _write(_book([_pos()]), _ctx(), p, dry_run=True)
    assert summary["would_write"] == 1
    assert summary["csv_written"] == 0
    assert not p.exists()


def test_an_explicit_csv_path_never_touches_the_real_record(tmp_path):
    p = tmp_path / "b.csv"
    _write(_book([_pos()]), _ctx(), p)
    assert p.exists()
    assert p != OPEN_BOOK_CSV


def test_read_csv_rows_tolerates_a_missing_file(tmp_path):
    assert bw.read_csv_rows(tmp_path / "nope.csv") == []


def test_write_refuses_rows_that_cannot_be_deduplicated(tmp_path, monkeypatch):
    monkeypatch.setattr(bw, "book_id", lambda row: "")
    with pytest.raises(ValueError, match="no book_id"):
        _write(_book([_pos()]), _ctx(), tmp_path / "b.csv")


def test_the_summary_counts_what_needs_attention(tmp_path):
    book = _book([_pos("NVDA", exit_by=date(2026, 8, 1)),
                  _pos("AMD", conid_key="3|4", exit_by=date(2026, 8, 17)),
                  _pos("MU", conid_key="5|6")])
    summary = _write(book, _ctx(), tmp_path / "b.csv")
    assert summary["positions"] == 3
    assert summary["attention"] == 1
    assert summary["watch"] == 1


# --------------------------------------------------------------------------
# Reading back
# --------------------------------------------------------------------------
def test_latest_snapshot_keeps_only_the_current_generation_of_the_newest_date(tmp_path):
    p = tmp_path / "b.csv"
    _write(_book([_pos()]), _ctx(), p)
    _write(_book([_pos(delta_notional=5_000.0)]), _ctx(as_of_date="2026-08-15"), p)
    _write(_book([_pos(delta_notional=6_000.0)]),
           _ctx(as_of_date="2026-08-15", snapshot_at=T2), p)
    latest = bw.latest_snapshot(bw.read_csv_rows(p))
    assert len(latest) == 1
    assert latest[0]["as_of_date"] == "2026-08-15"
    assert latest[0]["delta_notional"] == "6000.0"


def test_latest_snapshot_never_shows_a_book_after_the_date_asked_for(tmp_path):
    p = tmp_path / "b.csv"
    _write(_book([_pos()]), _ctx(), p)
    _write(_book([_pos()]), _ctx(as_of_date="2026-08-20"), p)
    latest = bw.latest_snapshot(bw.read_csv_rows(p), on_or_before=AS_OF)
    assert [r["as_of_date"] for r in latest] == [AS_OF]


def test_latest_snapshot_on_an_empty_record():
    assert bw.latest_snapshot([]) == []


# --------------------------------------------------------------------------
# Sheets: ordering, and the failure contract
# --------------------------------------------------------------------------
class _FakeSheets:
    """A tab that behaves like the real one: `replace_rows` REPLACES."""

    def __init__(self):
        self.calls = []
        self.tab = []       # what the tab holds now
        self.columns = []   # the header it holds it under

    def replace_rows(self, tab, rows, columns, raw=False, spreadsheet_id=None):
        self.calls.append(("replace_rows", tab, len(rows)))
        self.columns = list(columns)
        self.tab = [dict(r) for r in rows]
        return len(rows)

    def set_meta(self, tab, fingerprint="", last_row_time="", spreadsheet_id=None):
        self.calls.append(("set_meta", tab, None))

    def compute_batch_fingerprint(self, rows, key_cols):
        return "fp"


@pytest.fixture
def fake_sheets(monkeypatch):
    fake = _FakeSheets()
    monkeypatch.setattr(bw, "sheets_client", fake)
    monkeypatch.setenv("TRADE_JOURNAL_SPREADSHEET_ID", "sheet-id")
    return fake


def test_the_tab_holds_exactly_the_current_book_in_contract_order(tmp_path, fake_sheets):
    bw.write(_book([_pos("NVDA"), _pos("AMD", conid_key="3|4")]), _ctx(),
             csv_path=tmp_path / "b.csv")
    assert fake_sheets.columns == OPEN_BOOK_COLUMNS
    assert list(fake_sheets.tab[0]) == OPEN_BOOK_COLUMNS
    assert [r["ticker"] for r in fake_sheets.tab] == ["AMD", "NVDA"]


def test_a_position_that_left_the_book_leaves_the_tab_with_it(tmp_path, fake_sheets):
    """The reason the tab is a mirror. Appending would leave AMD's last
    ATTENTION row at the top of a status sort forever, indistinguishable from
    a position still held."""
    p = tmp_path / "b.csv"
    bw.write(_book([_pos("NVDA"), _pos("AMD", conid_key="3|4")]), _ctx(), csv_path=p)
    bw.write(_book([_pos("NVDA")]), _ctx(as_of_date="2026-08-15"), csv_path=p)
    assert [r["ticker"] for r in fake_sheets.tab] == ["NVDA"]
    # ...and the archive still remembers AMD was held.
    assert {r["ticker"] for r in bw.read_csv_rows(p)} == {"AMD", "NVDA"}


def test_a_flat_book_clears_the_tab_rather_than_leaving_yesterdays(tmp_path, fake_sheets):
    p = tmp_path / "b.csv"
    bw.write(_book([_pos()]), _ctx(), csv_path=p)
    summary = bw.write(_book([]), _ctx(as_of_date="2026-08-15"), csv_path=p)
    assert fake_sheets.tab == []
    assert summary["sheets_written"] == 0
    assert summary["positions"] == 0
    assert [c[0] for c in fake_sheets.calls].count("replace_rows") == 2


def test_an_unchanged_rerun_still_refreshes_the_tab_though_the_archive_gains_nothing(
        tmp_path, fake_sheets):
    """The archive dedupes on content; the tab does not, because a mirror that
    skips a run it thinks is unchanged is a mirror that can silently hold a
    book from a failed earlier write."""
    p = tmp_path / "b.csv"
    bw.write(_book([_pos()]), _ctx(), csv_path=p)
    summary = bw.write(_book([_pos()]), _ctx(snapshot_at=T2), csv_path=p)
    assert summary["csv_written"] == 0
    assert summary["skipped_duplicate"] == 1
    assert summary["sheets_written"] == 1
    assert [c[0] for c in fake_sheets.calls].count("replace_rows") == 2


def test_a_sheets_failure_is_reported_but_never_loses_the_local_row(tmp_path, monkeypatch):
    class Boom(_FakeSheets):
        def replace_rows(self, *a, **kw):
            raise RuntimeError("sheets is down")

    monkeypatch.setattr(bw, "sheets_client", Boom())
    monkeypatch.setenv("TRADE_JOURNAL_SPREADSHEET_ID", "sheet-id")
    p = tmp_path / "b.csv"
    summary = bw.write(_book([_pos()]), _ctx(), csv_path=p)
    assert "sheets is down" in summary["sheets_error"]
    assert summary["csv_written"] == 1
    assert len(bw.read_csv_rows(p)) == 1


def test_a_missing_spreadsheet_id_writes_locally_and_says_so(tmp_path, monkeypatch):
    monkeypatch.delenv("TRADE_JOURNAL_SPREADSHEET_ID", raising=False)
    p = tmp_path / "b.csv"
    summary = bw.write(_book([_pos()]), _ctx(), csv_path=p)
    assert summary["csv_written"] == 1
    assert "TRADE_JOURNAL_SPREADSHEET_ID" in summary["sheets_error"]


# --------------------------------------------------------------------------
# Documentation — the column dictionary must define every column, same check
# docs/recommendations-reference.md gets.
# --------------------------------------------------------------------------
_REFERENCE_DOC = (Path(__file__).resolve().parents[1] / "docs" / "open-book-reference.md")


def test_every_open_book_column_is_documented():
    doc = _REFERENCE_DOC.read_text(encoding="utf-8")
    missing = [c for c in OPEN_BOOK_COLUMNS if f"`{c}`" not in doc]
    assert not missing, "docs/open-book-reference.md does not define: " + ", ".join(missing)


def test_every_flag_is_documented():
    doc = _REFERENCE_DOC.read_text(encoding="utf-8")
    missing = [f for f in BOOK_FLAG_SEVERITY if f"`{f}`" not in doc]
    assert not missing, "docs/open-book-reference.md does not define: " + ", ".join(missing)
