"""
P2/P3 — robustness-review §Production loop, rows P2 and P3.

P2. A missing NetLiquidation used to build the open book by hand-constructing
a `BookRisk` directly (`__main__._build_book`'s old body), which left
`net_delta_notional`/`gross_delta_notional`/`ticker_exposure` at their 0.0
dataclass default while real priced positions sat in `book.positions` --
`assess()` never ran, so the caps AND the totals were both skipped. The only
place that caught it was `s04b_page.py`'s reconcile-or-write-nothing gate,
which recomputes the same totals independently and raised `ReconcileError`
*after* the report had already been built with the wrong (zero) figures and
*before* `s05_writer.py`/`s05b_bookwriter.py` ever ran.

THE FIX. `s03_risk.py::assess()` now accepts `caps: Caps | None` and always
computes the real totals; only the breach check is skipped when `caps` is
`None`. `__main__._build_book` routes the no-NetLiq path through `assess()`
instead of hand-building a `BookRisk`.

P3. `s05_writer.py`/`s07_recwriter.py` computed what to send to Sheets by
diffing against THIS RUN's `fresh` rows -- rows already local (written on an
earlier run whose Sheets call failed) were excluded from `fresh` and so were
never retried, forever. The fix diffs against every local row instead.

Fully offline -- every fixture is built inline, no broker/Sheets network.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from scripts.journal import __main__ as cli
from scripts.journal import s03_risk as risk
from scripts.journal import s04a_report as report
from scripts.journal import s04b_page as page
from scripts.journal import s05_writer as writer
from scripts.journal import s07_recwriter as recwriter
from scripts.journal.config import (DELTA_SOURCE_IBKR, DELTA_SOURCE_UNAVAILABLE,
                                    Leg, PositionEvent, PositionRisk, RecContext)
from scripts.journal.lib import book as book_lib
from scripts.journal.s03_risk import BookRisk, Caps
from scripts.journal.s06_recommend import Candidate

AS_OF = date(2026, 8, 14)


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------
def _risk(**kw):
    defaults = dict(conid_key="k1", ticker="NVDA", structure="bull_call_spread",
                    contracts=1, legs=[], position_delta=0.30, delta_notional=5000.0,
                    pct_net_liq=None, underlying_price=175.0, short_leg_delta=None,
                    iv=32.5, delta_source=DELTA_SOURCE_IBKR, dte=45.0)
    defaults.update(kw)
    return PositionRisk(**defaults)


def _unpriced(**kw):
    defaults = dict(conid_key="k2", ticker="AMD", structure="long_call", contracts=1,
                    legs=[], position_delta=None, delta_notional=None, pct_net_liq=None,
                    underlying_price=None, short_leg_delta=None, iv=None,
                    delta_source=DELTA_SOURCE_UNAVAILABLE, dte=None)
    defaults.update(kw)
    return PositionRisk(**defaults)


def _caps(net_liq=100000.0):
    return Caps(per_position=0.25, net=2.50, net_liq=net_liq)


def _meta(**kw):
    defaults = dict(date="2026-08-14", pull_source="ibkr-cpapi",
                    pull_file="journal/raw/ibkr-2026-08-14-2015.json",
                    analysis_source="sheets", net_liquidation=100000.0)
    defaults.update(kw)
    return defaults


def _leg(conid=1, qty=1, strike=170.0, right="C", symbol="NVDA", price=5.0):
    return Leg(conid=conid, symbol=symbol, expiry=date(2026, 10, 16), strike=strike,
               right=right, qty=qty, fill_price=price, commission=1.0,
               exec_id=f"e{conid}", fill_time=datetime(2026, 8, 14, 14, 30,
                                                       tzinfo=timezone.utc),
               open_close="O")


def _event(**kw):
    defaults = dict(date="2026-08-14", trade_datetime_utc="2026-08-14T14:30:00Z",
                    ticker="NVDA", structure="bull_call_spread", action="OPEN",
                    legs=[_leg(1, 1, 170.0), _leg(2, -1, 180.0)], contracts=1,
                    net_price=3.2, commission=2.0, net_cash=-322.0,
                    match_confidence="EXACT",
                    source_ref="ibkr-2026-08-14-1615.json:e1,e2")
    defaults.update(kw)
    return PositionEvent(**defaults)


# ==========================================================================
# P2 -- s03_risk.assess(positions, caps=None)
# ==========================================================================
def test_assess_with_no_caps_still_computes_real_totals():
    """The headline invariant: caps=None must not mean totals=0.0."""
    priced = _risk(delta_notional=5000.0, ticker="NVDA")
    unpriced = _unpriced()
    out = risk.assess([priced, unpriced], None)

    assert out.caps is None
    assert out.net_delta_notional == pytest.approx(5000.0)
    assert out.gross_delta_notional == pytest.approx(5000.0)
    assert out.ticker_exposure == {"NVDA": pytest.approx(5000.0)}
    assert out.positions == [priced]
    assert out.unpriced == [unpriced]
    assert out.complete is False  # the unpriced leg still excludes it from totals


def test_assess_with_no_caps_never_raises_a_breach():
    """No caps loaded means no breach CHECK, not "coincidentally under cap" --
    a position whose exposure would obviously breach any real cap must still
    come back with an empty breach list when caps is None."""
    huge = _risk(delta_notional=10_000_000.0, ticker="NVDA")
    out = risk.assess([huge], None)
    assert out.breaches == []

    # Contrast: the SAME position against real caps does breach -- proving
    # the empty list above is genuinely "not checked", not "always empty".
    out_with_caps = risk.assess([huge], _caps(net_liq=100_000.0))
    assert out_with_caps.breaches != []


def test_assess_none_and_real_caps_agree_on_the_totals():
    """caps=None must not silently change the totals a real run would see --
    only whether the breach check runs."""
    priced = _risk(delta_notional=3000.0, ticker="AMD")
    a = risk.assess([priced], None)
    b = risk.assess([priced], _caps())
    assert a.net_delta_notional == b.net_delta_notional
    assert a.gross_delta_notional == b.gross_delta_notional
    assert a.ticker_exposure == b.ticker_exposure


# ==========================================================================
# P2 -- __main__._build_book wiring: the no-NetLiq path must route through
# assess(), not hand-build a BookRisk.
# ==========================================================================
def _raw_book(net_liquidation):
    """A minimal Flex-shaped pull: one NVDA bull call spread, real deltas."""
    return {
        "schema_version": 1, "pulled_at_utc": "x", "trade_date": "2026-08-14",
        "source": "test", "trades": [],
        "positions": [{"conid": 1, "position": 1, "avg_cost": 700.0},
                      {"conid": 2, "position": -1, "avg_cost": 300.0}],
        "contracts": {"1": {"symbol": "NVDA", "sec_type": "OPT", "strike": 170.0,
                            "expiry": "2026-10-16", "right": "C"},
                      "2": {"symbol": "NVDA", "sec_type": "OPT", "strike": 180.0,
                            "expiry": "2026-10-16", "right": "C"}},
        "greeks": {"1": {"delta": 0.6, "source": DELTA_SOURCE_IBKR},
                  "2": {"delta": 0.35, "source": DELTA_SOURCE_IBKR}},
        "underlying_prices": {"NVDA": 175.0},
        "net_liquidation": net_liquidation,
    }


def test_build_book_with_missing_net_liq_reports_the_real_exposure():
    raw = _raw_book(None)
    out, positions, notes = cli._build_book(raw, AS_OF)

    assert out.caps is None
    # delta = 0.6 - 0.35 = 0.25; dn = 0.25 * 100 * 175 = 4375.0
    assert out.net_delta_notional == pytest.approx(4375.0)
    assert out.gross_delta_notional == pytest.approx(4375.0)
    assert out.breaches == []
    assert len(out.positions) == 1
    assert any("NetLiquidation" in n for n in notes)


def test_build_book_with_net_liq_present_is_unaffected():
    """Regression guard: the normal (NetLiquidation present) path must keep
    loading real caps and computing the same totals as before."""
    raw = _raw_book(100_000.0)
    out, positions, notes = cli._build_book(raw, AS_OF)

    assert out.caps is not None
    assert out.net_delta_notional == pytest.approx(4375.0)
    assert out.gross_delta_notional == pytest.approx(4375.0)


# ==========================================================================
# P2 -- end to end: the page reconciler must no longer crash on a missing
# NetLiquidation, and must have crashed on the OLD hand-built BookRisk shape.
# ==========================================================================
def test_the_old_hand_built_bookrisk_shape_reproduces_the_reconcile_crash(tmp_path):
    """Pins the bug: a BookRisk whose totals were left at their 0.0 default
    (exactly what `_build_book` used to construct for a missing NetLiquidation)
    makes `s04a_report.py` print a flat book while `s04b_page.py` recomputes
    the real one from `book.positions` -- the ReconcileError that used to
    abort the run before the fills or open book were written."""
    priced = _risk(delta_notional=5000.0)
    zeroed = BookRisk(positions=[priced], unpriced=[], caps=None)  # net/gross left at 0.0
    with pytest.raises(page.ReconcileError):
        page.build([_event()], zeroed, _meta(net_liquidation=None), tmp_path / "journal-x.html")


def test_assess_none_avoids_the_reconcile_crash(tmp_path):
    priced = _risk(delta_notional=5000.0)
    fixed = risk.assess([priced], None)  # the fix
    events = [_event()]
    out_path = tmp_path / "journal-2026-08-14.html"
    returned = page.build(events, fixed, _meta(net_liquidation=None), out_path)
    assert out_path.exists()
    assert returned == out_path
    # The report itself must also show the real figure, not a floor of zero.
    text = report.build(events, fixed, _meta(net_liquidation=None))
    assert "5,000" in text


# ==========================================================================
# P3 -- s05_writer.py: a row stuck locally after a Sheets outage must be
# retried on a LATER run, even though it is no longer "fresh".
# ==========================================================================


class _FakeSheets:
    """Records what reached it. `existing` seeds what get_all_rows returns,
    i.e. what is ALREADY on the tab (nothing, unless told otherwise)."""

    def __init__(self, existing_refs=(), fail=False):
        self.existing_refs = set(existing_refs)
        self.fail = fail
        self.sent = []

    def get_all_rows(self, tab, spreadsheet_id=None):
        return [{"source_ref": r} for r in self.existing_refs]

    def append_rows(self, tab, rows, raw=False, spreadsheet_id=None):
        if self.fail:
            raise RuntimeError("sheets is down")
        self.sent.extend(rows)
        self.existing_refs.update(r["source_ref"] for r in rows if r.get("source_ref"))

    def set_meta(self, tab, fingerprint="", last_row_time="", spreadsheet_id=None):
        pass

    def compute_batch_fingerprint(self, rows, key_cols):
        return "fp"


def test_a_row_stuck_after_a_sheets_outage_is_retried_on_the_next_run(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADE_JOURNAL_SPREADSHEET_ID", "sheet-id")
    csv_path = tmp_path / "trades.csv"
    ev = [_event()]

    # Run 1: CSV succeeds, Sheets fails. The row is now local-only.
    fake = _FakeSheets(fail=True)
    monkeypatch.setattr(writer, "sheets_client", fake)
    first = writer.write(ev, csv_path=csv_path)
    assert first["csv_written"] == 1
    assert first["sheets_error"]
    assert fake.sent == []

    # Run 2: same fills are still in the day's reconciled events (as they
    # would be if `cmd_run` re-derives them from the same raw pull), Sheets
    # is back up. The row is no longer "fresh" against the local CSV, but it
    # must still reach Sheets.
    fake2 = _FakeSheets(fail=False)
    monkeypatch.setattr(writer, "sheets_client", fake2)
    second = writer.write(ev, csv_path=csv_path)
    assert second["csv_written"] == 0          # already local -- correctly not re-appended
    assert second["skipped_duplicate"] == 1
    assert second["sheets_written"] == 1        # THE FIX: retried despite being non-fresh
    assert len(fake2.sent) == 1
    assert fake2.sent[0]["source_ref"] == ev[0].source_ref


def test_a_row_already_on_sheets_is_not_resent(tmp_path, monkeypatch):
    """The backlog diff must still exclude rows Sheets already has -- the fix
    must not turn every run into a full resend."""
    monkeypatch.setenv("TRADE_JOURNAL_SPREADSHEET_ID", "sheet-id")
    csv_path = tmp_path / "trades.csv"
    ev = [_event()]
    fake = _FakeSheets(existing_refs={ev[0].source_ref})
    monkeypatch.setattr(writer, "sheets_client", fake)
    summary = writer.write(ev, csv_path=csv_path)
    assert summary["sheets_written"] == 0
    assert fake.sent == []


# ==========================================================================
# P3 -- s07_recwriter.py: same shape, for the Recommendations record.
# ==========================================================================
def _cand(ticker="NVDA", role="deploy", **kw):
    base = dict(
        ticker=ticker, play="Bull call spread 235/270, 60-90 DTE",
        structure="bull_call_spread", market_regime="RANGE + E-VOL",
        tier="A", tier_partial=False, tier_reason="Sec2 debit vertical",
        score_total=41.0, horizon="60d", trigger="close above 235",
        invalidation="close below 218", alternative_interpretation="collar",
        role=role, deploy=True,
    )
    base.update(kw)
    return Candidate(**base)


def _ctx(**kw):
    base = dict(session_date="2026-08-14", as_of_date="2026-08-15", staleness_days=1,
                analysis_source="sheets", book_evaluable=True,
                generated_at=datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc))
    base.update(kw)
    return RecContext(**base)


class _FakeRecSheets(_FakeSheets):
    """Adds the tab-shaping no-ops `s07_recwriter.write` calls first."""

    def ensure_tab(self, tab, min_cols=0, spreadsheet_id=None):
        pass

    def ensure_header(self, tab, schema, spreadsheet_id=None):
        return "ok"

    def get_all_rows(self, tab, spreadsheet_id=None):
        return [{"rec_id": r} for r in self.existing_refs]


def test_a_recommendation_stuck_after_a_sheets_outage_is_retried(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADE_JOURNAL_SPREADSHEET_ID", "sheet-id")
    csv_path = tmp_path / "rec.csv"
    candidates = [_cand()]
    ctx = _ctx()

    fake = _FakeRecSheets(fail=True)
    monkeypatch.setattr(recwriter, "sheets_client", fake)
    first = recwriter.write(candidates, [], ctx, csv_path=csv_path)
    assert first["csv_written"] == 1
    assert first["sheets_error"]
    assert fake.sent == []

    # Same card, same content: rec_id is a content hash, so a re-run of an
    # UNCHANGED card also produces the same rec_id and is correctly a no-op
    # on the CSV side -- but it must still be retried against Sheets.
    fake2 = _FakeRecSheets(fail=False)
    monkeypatch.setattr(recwriter, "sheets_client", fake2)
    second = recwriter.write(candidates, [], ctx, csv_path=csv_path)
    assert second["csv_written"] == 0
    assert second["sheets_written"] == 1
    assert len(fake2.sent) == 1


def test_a_recommendation_already_on_sheets_is_not_resent(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADE_JOURNAL_SPREADSHEET_ID", "sheet-id")
    csv_path = tmp_path / "rec.csv"
    candidates = [_cand()]
    ctx = _ctx()
    # Discover the rec_id the card will actually carry, by writing it locally
    # first with Sheets skipped, then seed a fake Sheets that already has it.
    recwriter.write(candidates, [], ctx, csv_path=csv_path, skip_sheets=True)
    rec_id = recwriter.read_csv_rows(csv_path)[0]["rec_id"]

    fake = _FakeRecSheets(existing_refs={rec_id})
    monkeypatch.setattr(recwriter, "sheets_client", fake)
    summary = recwriter.write(candidates, [], ctx, csv_path=csv_path)
    assert summary["sheets_written"] == 0
    assert fake.sent == []
