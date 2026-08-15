"""
Tests for scripts/journal/report.py and scripts/journal/page.py — step 4 of the
daily trade journal.

Offline throughout: every PositionEvent/PositionRisk/BookRisk here is built
inline, never pulled from a broker or Sheets. The recurring theme, same as
tests/test_journal_core.py, is the MISSING/ZERO invariant: a `None` greek/delta
renders as an em dash, a genuine `0.0` renders as `0.000`, and the two must never
look the same on the page a human reads before sizing the next position.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

import pytest

from scripts.journal import s04b_page as page, s07_recwriter as recwriter, s04a_report as report
from scripts.journal.config import (DELTA_SOURCE_IBKR, DELTA_SOURCE_UNAVAILABLE,
                                    Leg, PositionEvent, PositionRisk)
from scripts.journal.s03_risk import BookRisk, Caps

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


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
                    realized_pnl=None, signal_date="2026-08-13", entry_lag_days=1,
                    match_confidence="EXACT",
                    ac_play="[DIRECTIONAL] TF | bull call spread 170/180",
                    ac_structure="bull_call_spread", tier="B",
                    tier_reason="other bull_call_spread", tier_verified=True,
                    source_ref="ibkr-2026-08-14-1615.json:e1,e2")
    defaults.update(kw)
    return PositionEvent(**defaults)


def _caps(net_liq=100000.0):
    return Caps(per_position=0.25, net=2.50, net_liq=net_liq)


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


def _meta(**kw):
    defaults = dict(date="2026-08-14", pull_source="ibkr-cpapi",
                    pull_file="journal/raw/ibkr-2026-08-14-2015.json",
                    analysis_source="sheets", net_liquidation=100000.0)
    defaults.update(kw)
    return defaults


# --------------------------------------------------------------------------
# s04a_report.py — formatting invariants
# --------------------------------------------------------------------------


def test_none_renders_as_em_dash_across_every_formatter():
    assert report.delta3(None) == report.EM_DASH
    assert report.money(None) == report.EM_DASH
    assert report.pct(None) == report.EM_DASH
    assert report.iv_fmt(None) == report.EM_DASH
    assert report.num(None) == report.EM_DASH


def test_a_genuine_zero_delta_is_not_an_em_dash():
    """The whole missing/zero invariant in one assertion: 0.000 != em dash."""
    assert report.delta3(0.0) == "0.000"
    assert report.delta3(0.0) != report.EM_DASH


def test_open_book_row_distinguishes_zero_delta_from_missing_fields():
    p = _risk(position_delta=0.0, delta_notional=0.0, dte=None, iv=None,
              underlying_price=None)
    book = BookRisk(positions=[p], unpriced=[], caps=_caps(),
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build([], book, _meta())
    assert "0.000" in text                 # the real zero delta
    assert report.EM_DASH in text          # None dte/iv/underlying_price


# --------------------------------------------------------------------------
# s04a_report.py — sections
# --------------------------------------------------------------------------


def test_complete_book_states_totals_plainly_with_no_floor_caveat():
    p = _risk(delta_notional=5000.0)
    book = BookRisk(positions=[p], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    text = report.build([_event()], book, _meta())
    assert "Book is **complete**" in text
    assert "FLOOR" not in text
    assert "$5,000.00" in text


def test_unpriced_positions_trigger_the_floor_caveat_with_the_excluded_count():
    priced = _risk(delta_notional=5000.0)
    gone = [_unpriced(conid_key="k2", ticker="AMD"), _unpriced(conid_key="k3", ticker="TSM")]
    book = BookRisk(positions=[priced], unpriced=gone, caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    text = report.build([_event()], book, _meta())
    assert "FLOOR" in text
    assert "2 position(s) are excluded" in text
    assert "Positions excluded (no delta): 2" in text


def test_a_breach_appears_in_the_exposure_section():
    breach = "NVDA bull_call_spread: |delta-notional| $50,000 exceeds the per-position cap $25,000 (0.25x equity)"
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0,
                    breaches=[breach])
    text = report.build([_event()], book, _meta())
    exposure_idx = text.index("## 5. Exposure")
    assert breach in text[exposure_idx:]
    assert "**1 breach(es).**" in text


def test_the_per_ticker_exposure_table_shows_the_netting_behind_a_breach():
    """§5's table is what makes a breach checkable: the reader must be able to
    see the financing leg that a ticker's total already nets in."""
    from scripts.journal.s03_risk import assess
    core = _risk(conid_key="k1", ticker="GLD", structure="bull_call_spread",
                 delta_notional=8529.58)
    overlay = _risk(conid_key="k2", ticker="GLD", structure="single short call",
                    delta_notional=-2226.37)
    book = assess([core, overlay], _caps(net_liq=31000.0))
    text = report.build([], book, _meta())
    exposure = text[text.index("## 5. Exposure"):]
    assert "Per-ticker exposure" in exposure
    assert "**0 breach(es).**" in exposure          # $6,303 is under the $7,750 cap
    assert "BREACH" not in exposure


def test_page_and_risk_agree_on_the_breach_count_after_per_ticker_netting():
    """SYNC GUARD. `risk.assess` and `page._breach_count` are two deliberate
    implementations of the per-ticker cap rule — `page` recomputes rather than
    reading `book.breaches`, so a drift between them surfaces as a
    ReconcileError. This pins that they agree on a book where the netting
    actually matters."""
    from scripts.journal.s03_risk import assess
    positions = [
        _risk(conid_key="k1", ticker="GLD", structure="bull_call_spread",
              delta_notional=8529.58),
        _risk(conid_key="k2", ticker="GLD", structure="single short call",
              delta_notional=-2226.37),
        _risk(conid_key="k3", ticker="NVDA", structure="single long call",
              delta_notional=14204.42),
        _risk(conid_key="k4", ticker="NVDA", structure="single short call",
              delta_notional=-2305.30),
    ]
    book = assess(positions, _caps(net_liq=31000.0))
    assert len(book.breaches) == 1                  # NVDA only; GLD nets clear
    assert page.compute_figures([], book)["breach_n"] == len(book.breaches)


def test_stale_analysis_source_gets_the_loud_header_line():
    book = BookRisk(positions=[], unpriced=[], caps=_caps(),
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build([], book, _meta(analysis_source="backtests/to_evaluate/analysis - AnalysisClaude.csv"))
    assert "STALE ANALYSIS SOURCE" in text


def test_live_sheets_source_gets_no_stale_warning():
    book = BookRisk(positions=[], unpriced=[], caps=_caps(),
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build([], book, _meta(analysis_source="sheets"))
    assert "STALE ANALYSIS SOURCE" not in text


def test_today_activity_lists_every_event():
    events = [_event(ticker="NVDA"), _event(ticker="AMD", source_ref="x2")]
    book = BookRisk(positions=[], unpriced=[], caps=_caps(),
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build(events, book, _meta())
    assert "NVDA" in text and "AMD" in text
    assert "**2 position event(s) today.**" in text


def test_confidence_tally_counts_every_bucket():
    events = [_event(match_confidence="EXACT"), _event(match_confidence="NONE", source_ref="x2")]
    book = BookRisk(positions=[], unpriced=[], caps=_caps(),
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build(events, book, _meta())
    assert ("EXACT=1, STRUCTURE=0, CORE=0, SUBSTITUTED=0, OVERLAY=0, NONE=1"
            in text)


def test_a_financed_core_is_tallied_as_core_not_as_a_miss():
    events = [_event(match_confidence="CORE", structure="3-leg combo (debit)",
                     ac_structure="bull_call_spread")]
    book = BookRisk(positions=[], unpriced=[], caps=_caps(),
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build(events, book, _meta())
    assert "CORE=1" in text
    assert "**1/1 play attempt(s) matched an analysis play**" in text


def test_a_financing_overlay_leaves_both_sides_of_the_match_ratio():
    """An overlay was never an attempt to trade a play, so counting it as an
    unmatched trade would misdescribe the operator as trading off-plan."""
    events = [_event(match_confidence="EXACT"),
              _event(match_confidence="OVERLAY", source_ref="x2",
                     structure="single short call (overlay)")]
    book = BookRisk(positions=[], unpriced=[], caps=_caps(),
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build(events, book, _meta())
    assert "OVERLAY=1" in text
    # one attempt, one match — the overlay is in neither numerator nor denominator
    assert "**1/1 play attempt(s) matched an analysis play**" in text
    assert "1 financing/carry overlay(s)** excluded from the ratio" in text


def test_the_book_cross_check_counts_land_in_section_6():
    book = BookRisk(positions=[], unpriced=[], caps=_caps(),
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build([], book, _meta(book_diagnostics={
        "not_cross_checkable": ["a", "b"], "coverage_explained": ["c"],
        "unexplained": []}))
    head, section6 = text.split("## 6. Not covered")
    # demoted OUT of the §1 alarm...
    assert "declared OpenPositions book shows" not in head
    # ...and counted where the reader can still see the check ran
    assert "cannot see (no fill in its window) (2):" in section6
    assert "explained by a gap in export coverage (1):" in section6
    assert "NOT explained — a missing fill or a corporate action:** 0." in section6


def test_an_absent_cross_check_says_not_measured_rather_than_zero():
    """A pre-existing raw pull carries no book_diagnostics. Printing 0 there
    would claim a check ran that never did — the failure §6 exists to prevent."""
    book = BookRisk(positions=[], unpriced=[], caps=_caps(),
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build([], book, _meta())
    section6 = text.split("## 6. Not covered")[1]
    assert "Book cross-check" in section6
    assert section6.count("not recorded for this run") >= 3


def test_missing_caps_states_they_were_not_loaded():
    book = BookRisk(positions=[], unpriced=[], caps=None,
                    net_delta_notional=0.0, gross_delta_notional=0.0, breaches=[])
    text = report.build([], book, _meta(net_liquidation=None))
    assert "Caps: NOT LOADED" in text
    assert "NO NetLiquidation" in text


def test_write_creates_the_dated_report_file(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "REPORTS_DIR", tmp_path)
    path = report.write("hello", "2026-08-14")
    assert path == tmp_path / "2026-08-14.md"
    assert path.read_text() == "hello"


# --------------------------------------------------------------------------
# s04b_page.py — reconcile-or-write-nothing
# --------------------------------------------------------------------------


def test_reconcile_flags_a_genuine_mismatch():
    problems = page.reconcile({"net_dn": 100.0}, {"net_dn": 50.0})
    assert problems and "net_dn" in problems[0]


def test_reconcile_flags_a_figure_the_report_never_printed():
    problems = page.reconcile({"breach_n": 3}, {})
    assert problems and "breach_n" in problems[0]


def test_reconcile_is_silent_when_the_report_agrees():
    assert page.reconcile({"net_dn": 100.0, "breach_n": 0}, {"net_dn": 100.0, "breach_n": 0}) == []


def test_page_build_raises_and_writes_nothing_on_mismatch(tmp_path, monkeypatch):
    events = [_event()]
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])

    # Force report.build() (as s04b_page.py calls it) to return text describing a
    # different book than the one s04b_page.py itself will compute figures from.
    monkeypatch.setattr(page.report, "build",
                        lambda events, book, meta: "# fake report\n\nNet delta-notional: $1.00\n")

    out_path = tmp_path / "journal-2026-08-14.html"
    with pytest.raises(page.ReconcileError):
        page.build(events, book, _meta(), out_path)

    assert not out_path.exists()
    assert not (tmp_path / "journal-latest.html").exists()


def test_page_build_writes_dated_and_latest_files_when_consistent(tmp_path):
    events = [_event()]
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    out_path = tmp_path / "journal-2026-08-14.html"

    returned = page.build(events, book, _meta(), out_path)

    assert returned == out_path
    assert out_path.exists()
    assert (tmp_path / "journal-latest.html").exists()


def test_generated_html_makes_no_external_resource_reference(tmp_path):
    events = [_event()]
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    out_path = tmp_path / "journal-2026-08-14.html"
    page.build(events, book, _meta(), out_path)

    text = out_path.read_text()
    urls = re.findall(r'https?://[^\s"\'<>]+', text)
    # The only http(s)-looking string the inlined kit.js legitimately carries is
    # the SVG XML namespace identifier, which is never fetched over the network.
    external = [u for u in urls if "w3.org" not in u]
    assert external == []
    assert 'src="http' not in text
    assert 'href="http' not in text


# --------------------------------------------------------------------------
# Markdown table integrity
# --------------------------------------------------------------------------
def test_pipes_in_play_text_do_not_break_the_match_table():
    """Analysis play text is pipe-delimited BY CONSTRUCTION.

    Every play reads `PATTERN | structure | thesis`, so an unescaped cell splits
    one column into four and shifts tier/confidence under the wrong headers —
    silently, and on every single report. Regression guard for that.
    """
    text = report.build([_event(ac_play="[DIRECTIONAL] TF | bull call spread 220/240 "
                                        "~60 DTE | Cheap IV, strong uptrend")],
                        BookRisk(caps=_caps()), _meta())
    match_rows = [ln for ln in text.splitlines()
                  if ln.startswith("| NVDA |") and "EXACT" in ln]
    assert match_rows, "expected a match row"
    header = next(ln for ln in text.splitlines() if ln.startswith("| Ticker | Signal Date"))
    assert match_rows[0].count("|") - match_rows[0].count("\\|") == header.count("|")


def test_newlines_in_play_text_do_not_split_a_row():
    text = report.build([_event(ac_play="line one\nline two")],
                        BookRisk(caps=_caps()), _meta())
    assert "line one line two" in text or "line one line tw" in text


def test_a_pipe_in_a_structure_label_is_escaped_too():
    text = report.build([_event(structure="odd|label")], BookRisk(caps=_caps()), _meta())
    activity = [ln for ln in text.splitlines() if "odd" in ln][0]
    assert "odd\\|label" in activity


# --------------------------------------------------------------------------
# s04b_page.py — recommendations panel (deliberately outside the reconciled set)
# --------------------------------------------------------------------------
def _rec_row(**kw):
    defaults = dict(session_date="2026-08-14", role="deploy", rank=1, ticker="NVDA",
                    structure="bull_call_spread", tier="B", deploy="True",
                    trigger_verdict="PASS", headroom_ok="True",
                    play="[DIRECTIONAL] TF | bull call spread 170/180")
    defaults.update(kw)
    return defaults


def test_compute_figures_carries_no_recommendation_key():
    """The invariant that keeps the page buildable forever: a recommendation
    figure slipped into compute_figures() would make reconcile() demand it be
    parseable back out of report.build()'s markdown, which never prints one —
    so build() would raise ReconcileError on every single run."""
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    figs = page.compute_figures([_event()], book)
    assert not any(k.lower().startswith(("rec", "recommend")) for k in figs)


def test_build_computed_figures_are_identical_with_or_without_recommendation_data(
        tmp_path, monkeypatch):
    events = [_event()]
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    figs_without_recs = page.compute_figures(events, book)

    monkeypatch.setattr(recwriter, "read_csv_rows", lambda path=None: [_rec_row()])
    out_path = tmp_path / "journal-2026-08-14.html"
    page.build(events, book, _meta(), out_path)
    figs_with_recs = page.compute_figures(events, book)

    assert figs_with_recs == figs_without_recs
    assert out_path.exists()


def test_no_recommendations_available_renders_empty_state_and_still_writes_both_files(
        tmp_path, monkeypatch):
    monkeypatch.setattr(recwriter, "read_csv_rows", lambda path=None: [])
    events = [_event()]
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    out_path = tmp_path / "journal-2026-08-14.html"

    page.build(events, book, _meta(), out_path)

    text = out_path.read_text()
    assert "No recommendations recorded yet" in text
    assert out_path.exists()
    assert (tmp_path / "journal-latest.html").exists()


def test_recommendations_panel_degrades_to_empty_state_on_objects_with_no_get():
    """A list of plain objects (no .get method) must not blow up the page."""
    out = page._recommendations_panel([object(), object()])
    assert "No recommendations recorded yet" in out


def test_recommendations_panel_degrades_to_empty_state_when_get_raises():
    class _Boom:
        def get(self, key, default=None):
            raise RuntimeError("boom")

    out = page._recommendations_panel([_Boom()])
    assert "No recommendations recorded yet" in out


def test_recent_recommendations_returns_empty_and_does_not_raise_when_csv_read_fails(
        tmp_path, monkeypatch):
    def _boom(path=None):
        raise RuntimeError("no csv on disk")

    monkeypatch.setattr(recwriter, "read_csv_rows", _boom)
    assert page._recent_recommendations(_meta()) == ()

    events = [_event()]
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    out_path = tmp_path / "journal-2026-08-14.html"
    page.build(events, book, _meta(), out_path)
    assert out_path.exists()
    assert "No recommendations recorded yet" in out_path.read_text()


def test_recommendation_row_renders_html_escaped():
    row = _rec_row(play="<script>alert('x')</script> Tom & Jerry | pairs trade")
    out = page._recommendations_panel([row])
    assert "<script>alert" not in out
    assert "&lt;script&gt;" in out
    assert "Tom &amp; Jerry" in out


def test_recommendation_row_renders_html_escaped_end_to_end(tmp_path, monkeypatch):
    row = _rec_row(play="<script>alert('x')</script> Tom & Jerry | pairs trade")
    monkeypatch.setattr(recwriter, "read_csv_rows", lambda path=None: [row])
    events = [_event()]
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    out_path = tmp_path / "journal-2026-08-14.html"

    page.build(events, book, _meta(), out_path)

    text = out_path.read_text()
    assert "<script>alert" not in text
    assert "&lt;script&gt;" in text
    assert "Tom &amp; Jerry" in text


def test_chart_util_and_chart_conf_sit_in_grid_two_row_and_chart_dn_is_standalone(
        tmp_path):
    """Regression guard for the chart layout swap: chart-util/chart-conf now
    share the grid-2 row, and chart-dn is the standalone full-width figure
    below it. Fails loudly if the order is ever swapped back."""
    events = [_event()]
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    out_path = tmp_path / "journal-2026-08-14.html"
    page.build(events, book, _meta(), out_path)
    text = out_path.read_text()

    grid_start = text.index('<div class="grid-2">')
    standalone_start = text.index('<figure class="panel" style="margin-top:18px">')
    assert grid_start < standalone_start

    grid_block = text[grid_start:standalone_start]
    assert 'id="chart-util"' in grid_block
    assert 'id="chart-conf"' in grid_block
    assert 'id="chart-dn"' not in grid_block
    # util is drawn before conf within the grid row, matching the source order
    assert grid_block.index('id="chart-util"') < grid_block.index('id="chart-conf"')

    standalone_end = text.index('</section>', standalone_start)
    standalone_block = text[standalone_start:standalone_end]
    assert 'id="chart-dn"' in standalone_block

    # the inlined draw script was reordered to match: util, then conf, then dn
    script_util = text.index('getElementById("chart-util")')
    script_conf = text.index('getElementById("chart-conf")')
    script_dn = text.index('getElementById("chart-dn")')
    assert script_util < script_conf < script_dn


def test_generated_html_makes_no_external_resource_reference_with_recs_panel_present(
        tmp_path, monkeypatch):
    """The pre-existing no-external-resource guard must still hold with a
    populated recommendations panel in the page, not just the empty state."""
    monkeypatch.setattr(recwriter, "read_csv_rows", lambda path=None: [_rec_row()])
    events = [_event()]
    book = BookRisk(positions=[_risk()], unpriced=[], caps=_caps(),
                    net_delta_notional=5000.0, gross_delta_notional=5000.0, breaches=[])
    out_path = tmp_path / "journal-2026-08-14.html"
    page.build(events, book, _meta(), out_path)

    text = out_path.read_text()
    urls = re.findall(r'https?://[^\s"\'<>]+', text)
    external = [u for u in urls if "w3.org" not in u]
    assert external == []
    assert 'src="http' not in text
    assert 'href="http' not in text


def test_rec_cell_maps_true_false_strings_to_yes_no():
    assert page._rec_cell("True") == "yes"
    assert page._rec_cell("False") == "no"


def test_rec_cell_maps_none_and_blank_to_empty_string_never_no():
    """A blank means 'not evaluated', and must never render the same as a
    real False verdict."""
    assert page._rec_cell(None) == ""
    assert page._rec_cell("") == ""
    assert page._rec_cell(None) != "no"


def test_rec_cell_passes_through_other_values_unchanged():
    assert page._rec_cell("PASS") == "PASS"
    assert page._rec_cell(3) == "3"
