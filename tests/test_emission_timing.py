"""Unit tests for `scripts/backtest_study/f1_selection/emission_timing.py`.

Two things in that study are load-bearing and cannot be checked by reading its
report, so they are pinned here:

  1. **The emission ordinal.** ARM P's whole estimand is "repeat minus first",
     so if the ordinal is derived wrong the study measures nothing. The
     dangerous case is the same-day duplicate: the registration freezes
     `book.py`'s `created_datetime` keep-first join convention precisely because
     a session carrying two rows for one (ticker, structure) must NOT be able to
     manufacture a repeat. Ranking DISTINCT DATES is how the module implements
     that, and these tests hold it there.

  2. **The lag-L synthetic's construction.** `Trade` asserts
     `len(marks) == len(grid)`, and the interesting path is the 120-day
     cap-truncated row, where a later anchor recomputes a LONGER grid than the
     stored path and the marks must be right-padded with blanks. That path is a
     third of the v3 book, so a construction bug there would silently reshape
     the population ARM L compares — G1 fails the run on it, and these tests
     make sure the padding arithmetic it checks is actually exercised.

Nothing here reads the live exports: the fixtures are hand-built rows, so
growing the book cannot rot these tests (the lesson of the deleted
`expected_positions: 220` gates).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study.f1_selection import emission_timing as ET
from scripts.backtest_study.lib.harness import PATH_CAP_DAYS, Trade


# ── ARM P: the emission ordinal ──────────────────────────────────────────────

def _rec(ticker: str, structure: str, d: str, r: float = 0.0) -> dict:
    return dict(ticker=ticker, structure=structure, date=d, R=r, source="real")


def test_ordinal_ranks_distinct_dates_per_ticker_structure():
    recs = [_rec("AAA", "bull_call_spread", "2026-01-05"),
            _rec("AAA", "bull_call_spread", "2026-01-06"),
            _rec("AAA", "bull_call_spread", "2026-01-07"),
            _rec("BBB", "bull_call_spread", "2026-01-06")]
    ET.emission_index(recs)
    assert [r["emission_ordinal"] for r in recs] == [1, 2, 3, 1]
    assert recs[0]["first_emission_date"] == "2026-01-05"
    assert recs[2]["first_emission_date"] == "2026-01-05"
    # a different ticker is its own series, and its own first emission
    assert recs[3]["first_emission_date"] == "2026-01-06"
    assert recs[3]["prev_emission_date"] is None


def test_same_day_duplicates_collapse_and_cannot_fake_a_repeat():
    """The guard the registration froze: two rows on ONE session for one
    (ticker, structure) are both ordinal 1, and neither becomes a repeat."""
    recs = [_rec("AAA", "bull_call_spread", "2026-01-05"),
            _rec("AAA", "bull_call_spread", "2026-01-05"),
            _rec("AAA", "bull_call_spread", "2026-01-06")]
    em = ET.emission_index(recs)
    assert [r["emission_ordinal"] for r in recs] == [1, 1, 2]
    assert [r["emission_ordinal_capped"] for r in recs] == [1, 1, 2]
    assert em["dup_rows"] == 1 and em["dup_cells"] == 1
    # the repeat's predecessor is the SESSION, not the duplicate row
    assert recs[2]["prev_emission_date"] == "2026-01-05"


def test_a_structure_change_starts_a_new_series():
    """Ordinal is keyed on (ticker, structure): the same ticker re-emitted as a
    different structure is a FIRST emission, not a repeat."""
    recs = [_rec("AAA", "bull_call_spread", "2026-01-05"),
            _rec("AAA", "bear_put_spread", "2026-01-06")]
    ET.emission_index(recs)
    assert [r["emission_ordinal"] for r in recs] == [1, 1]


def test_single_emission_pairs_stay_at_ordinal_one():
    recs = [_rec("AAA", "bull_call_spread", "2026-01-05"),
            _rec("BBB", "bear_put_spread", "2026-01-06"),
            _rec("CCC", "bull_put_spread", "2026-01-07")]
    ET.emission_index(recs)
    assert {r["emission_ordinal_capped"] for r in recs} == {1}
    assert all(r["consecutive"] is None for r in recs)
    assert all(r["prev_emission_date"] is None for r in recs)


def test_consecutive_vs_gapped_repeats():
    """`consecutive` = the previous emission fell on the immediately preceding
    date present in the BOOK. A third-session repeat is GAPPED even though only
    one session separates them."""
    recs = [_rec("AAA", "bull_call_spread", "2026-01-05"),
            _rec("AAA", "bull_call_spread", "2026-01-06"),   # consecutive
            _rec("AAA", "bull_call_spread", "2026-01-08"),   # gapped (skips 01-07)
            _rec("ZZZ", "bull_put_spread", "2026-01-07")]    # only there to index 01-07
    em = ET.emission_index(recs)
    assert recs[1]["consecutive"] is True and recs[1]["gap_book_sessions"] == 1
    assert recs[2]["consecutive"] is False and recs[2]["gap_book_sessions"] == 2
    assert em["n_consecutive"] == 1
    # the calendar next-weekday diagnostic counts BOTH 01-05->01-06 and
    # 01-07->01-08 style adjacency; here only the first repeat qualifies
    assert em["n_next_weekday"] == 1


def test_ordinal_is_capped_at_four_plus():
    recs = [_rec("AAA", "bull_call_spread", f"2026-01-{d:02d}")
            for d in (5, 6, 7, 8, 9, 12)]
    ET.emission_index(recs)
    assert [r["emission_ordinal"] for r in recs] == [1, 2, 3, 4, 5, 6]
    assert [r["emission_ordinal_capped"] for r in recs] == [1, 2, 3, 4, 4, 4]


def test_within_date_pairing_only_keeps_dates_carrying_both_sides():
    recs = [_rec("AAA", "bull_call_spread", "2026-01-05", 0.10),   # first
            _rec("BBB", "bull_call_spread", "2026-01-05", 0.30),   # first
            _rec("AAA", "bull_call_spread", "2026-01-06", 0.50),   # repeat
            _rec("CCC", "bull_call_spread", "2026-01-06", -0.10),  # first
            _rec("BBB", "bull_call_spread", "2026-01-07", 0.90)]   # repeat, no first
    ET.emission_index(recs)
    paired = ET.paired_by_date(recs, lambda r: r["emission_ordinal_capped"] > 1)
    assert [p["date"] for p in paired] == ["2026-01-06"]
    assert paired[0]["a"] == pytest.approx(0.50)
    assert paired[0]["b"] == pytest.approx(-0.10)
    assert paired[0]["d"] == pytest.approx(0.60)


# ── ARM L: the lag-L synthetic ───────────────────────────────────────────────

def _fixture_rec(signal: date, expiry: date, mark_fn=None, marks=None) -> dict:
    """A book-shaped record whose `t` is a real `Trade` with a full mark path.

    Built the way the study's inputs are: the grid is whatever
    `harness.Trade` recomputes from `signal` and the legs, and the marks are
    generated to exactly that length.
    """
    nearest = (expiry - signal).days
    end = signal + timedelta(days=min(nearest, PATH_CAP_DAYS))
    grid = _weekday_grid(signal, end)
    if marks is None:
        mark_fn = mark_fn or (lambda i: round(1.50 + 0.01 * i, 4))
        marks = [mark_fn(i) for i in range(len(grid))]
    assert len(marks) == len(grid)
    row = {
        "signal_date": signal.isoformat(),
        "ticker": "AAA",
        "structure": "bull_call_spread",
        "entry_option_price": "1.40",   # the stored next-OPEN fill; deliberately != marks[0]
        "contracts": "8",
        "dte_entry": str(nearest),
        "legs": (f"AAA:{expiry.isoformat()}:100:C +1\n"
                 f"AAA:{expiry.isoformat()}:110:C -1"),
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
    }
    t = Trade(row)
    return dict(t=t, ticker="AAA", structure="bull_call_spread",
                date=signal.isoformat(), credit=False, mech_cell="PROD",
                source="real", R=0.0), grid, marks


def test_short_dated_row_needs_no_padding_and_stays_grid_aligned():
    rec, grid, marks = _fixture_rec(date(2026, 1, 5), date(2026, 2, 6))
    assert rec["t"].cap_reached_expiry, "fixture must NOT be cap-truncated"
    for lag in ET.LAGS:
        st, pad, status = ET.synth_trade(rec, lag)
        assert status == "ok" and st is not None
        assert pad == 0
        assert len(st.marks) == len(st.grid)
        assert st.marks == marks[lag:]
        assert st.grid == grid[lag:]
        assert st.entry_net == pytest.approx(marks[lag])


def test_cap_truncated_row_exercises_the_padding_path():
    """The 262/795 case: the stored grid stops at PATH_CAP_DAYS, so a later
    anchor recomputes a LONGER grid and the marks must be right-padded with
    blanks. Padding is behaviour-neutral (replay skips a None mark) and is what
    lets the truncated rows stay in the population instead of biasing it toward
    short-dated trades."""
    signal, expiry = date(2026, 1, 5), date(2026, 12, 18)
    rec, grid, marks = _fixture_rec(signal, expiry)
    assert not rec["t"].cap_reached_expiry, "fixture MUST be cap-truncated"

    padded_any = False
    for lag in ET.LAGS:
        st, pad, status = ET.synth_trade(rec, lag)
        assert status == "ok" and st is not None
        assert pad >= 0
        # G1's invariant, which is the whole point of the padding
        assert len(st.marks) == len(st.grid)
        # the real marks stay in place and aligned; only blanks are appended
        assert st.marks[:len(marks) - lag] == marks[lag:]
        assert all(m is None for m in st.marks[len(marks) - lag:])
        assert st.grid[:len(marks) - lag] == grid[lag:]
        assert st.entry_net == pytest.approx(marks[lag])
        padded_any = padded_any or pad > 0
    assert padded_any, "the cap-truncated fixture never hit the padding path"


def test_lag_zero_reproduces_the_stored_grid_and_dte():
    """L = 0 is the BASELINE: it must differ from the stored trade ONLY in the
    fill price (a day-0 CLOSE instead of the next open) and the sizing that
    follows from it — same anchor, same grid, same time-exit clock."""
    rec, grid, marks = _fixture_rec(date(2026, 1, 5), date(2026, 2, 6))
    st, pad, status = ET.synth_trade(rec, 0)
    assert status == "ok" and pad == 0
    assert st.signal_date == rec["t"].signal_date
    assert st.grid == rec["t"].grid
    assert st.dte_entry == rec["t"].dte_entry
    assert st.marks == rec["t"].marks
    assert st.entry_net == pytest.approx(marks[0])
    assert st.entry_net != rec["t"].entry_net


def test_dte_is_reduced_by_the_calendar_days_the_anchor_moved():
    rec, grid, _ = _fixture_rec(date(2026, 1, 5), date(2026, 2, 6))
    for lag in (1, 2, 3):
        st, _, status = ET.synth_trade(rec, lag)
        assert status == "ok"
        moved = (grid[lag - 1] - rec["t"].signal_date).days
        assert st.signal_date == grid[lag - 1]
        assert st.dte_entry == rec["t"].dte_entry - moved


def test_a_missing_mark_excludes_the_row_and_is_counted_not_dropped():
    signal, expiry = date(2026, 1, 5), date(2026, 2, 6)
    rec0, grid, marks = _fixture_rec(signal, expiry)
    holed = list(marks)
    holed[2] = None
    holed[3] = 0.0
    rec, _, _ = _fixture_rec(signal, expiry, marks=holed)
    assert ET.synth_trade(rec, 2)[2] == "no_mark_at_lag"
    assert ET.synth_trade(rec, 3)[2] == "degenerate_zero_entry"
    assert ET.synth_trade(rec, 1)[2] == "ok"


def test_contracts_are_resized_by_the_production_debit_formula():
    """`harness.replay`'s dollar_stop fires on `pl * |entry| * 100 * contracts`,
    so the contract count decides at what R it bites — re-sizing at the lagged
    entry is what keeps the ladder measuring lag rather than sizing."""
    dollar_risk = ET.PORTFOLIO_VALUE * ET.RISK_PER_TRADE_PCT
    for entry in (0.50, 1.50, 12.0):
        expect = int(dollar_risk // (entry * 100 * ET.DEBIT_STOP_LOSS))
        assert ET.size_contracts(entry, []) == max(1, expect)
    # a premium so large that one contract already exceeds the budget still
    # sizes to 1, as production does (the dollar stop caps the loss instead)
    assert ET.size_contracts(500.0, []) == 1


def test_synthetic_contracts_track_the_lagged_entry_price():
    rec, _, marks = _fixture_rec(date(2026, 1, 5), date(2026, 2, 6),
                                 mark_fn=lambda i: round(1.50 + 0.50 * i, 4))
    for lag in ET.LAGS:
        st, _, _ = ET.synth_trade(rec, lag)
        assert st.contracts == ET.size_contracts(marks[lag], rec["t"].legs)


# ── G3: the no-day-0-move assertion ──────────────────────────────────────────

def test_conditioning_allowlist_is_frozen_and_excludes_the_day_zero_move():
    assert ET.CONDITIONING_ALLOWLIST == frozenset({
        "emission_ordinal", "emission_gap", "pre_signal_move",
        "price_vector_tercile"})
    for name in ET.CONDITIONING_ALLOWLIST:
        assert ET.assert_conditioning(name) == name


def test_an_unregistered_conditioning_variable_fails_the_run():
    with pytest.raises(SystemExit) as exc:
        ET.assert_conditioning("next_day_move")
    assert exc.value.code == 1


def test_close_asof_refuses_to_read_past_the_signal_date():
    from scripts.backtest_study.lib.underlying import SRC_OHLC, Bar
    bars = {date(2026, 1, 5): Bar(c=10.0, source=SRC_OHLC),
            date(2026, 1, 6): Bar(c=11.0, source=SRC_OHLC)}
    signal = date(2026, 1, 5)
    assert ET.close_asof(bars, signal, signal)[0] == pytest.approx(10.0)
    with pytest.raises(SystemExit) as exc:
        ET.close_asof(bars, date(2026, 1, 6), signal)
    assert exc.value.code == 1


def test_designed_refusal_codes_are_a_plain_set_literal():
    """The runner AST-parses this; a `frozenset(...)` call is invisible to
    `ast.literal_eval` and would demote an era refusal to a FAILURE."""
    import ast
    from pathlib import Path
    src = Path(ET.__file__).read_text()
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "DESIGNED_REFUSAL_EXIT_CODES"
                        for t in node.targets)):
            assert isinstance(node.value, ast.Set)
            assert ast.literal_eval(node.value) == {2, 3}
            return
    pytest.fail("DESIGNED_REFUSAL_EXIT_CODES not found")
