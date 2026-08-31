"""Tests for the mark-to-market book equity curve (`lib/mtm_curve.py`).

`hedge_exposure` reads every verdict off this curve, so what is pinned here is
the METHODOLOGY, not return shapes: that the curve actually marks open
positions (the whole reason the module exists), that the realized basis it
returns alongside is byte-identical to `account_sim.equity_curve`'s, that
G-MTM catches a booked/marked disagreement instead of averaging it away, and
that the tolerance is a parameter a caller has to name.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_study.lib import mtm_curve as M  # noqa: E402


# ── fakes ────────────────────────────────────────────────────────────────────

class _FakeTrade:
    """The three attributes `position_marks`/`stored_booked` read off a
    `harness.Trade`. `realized_pnl_abs` is G-MTM's STORED reconciliation
    target — omitted (`None`) only for the degraded-path fixture."""

    def __init__(self, grid, pnl_csv, realized_pnl_abs=None):
        self.grid = grid
        self.row = {"daily_pnl_csv": pnl_csv}
        if realized_pnl_abs is not None:
            self.row["realized_pnl_abs"] = realized_pnl_abs


class _FakePos:
    """Duck-typed on `account_sim.Pos` — the fields this module touches."""

    def __init__(self, grid, pnl_csv, contracts, days_held, dollars,
                 ticker="XYZ", d="2025-01-02", realized_pnl_abs=None):
        self.rec = {"t": _FakeTrade(grid, pnl_csv, realized_pnl_abs),
                    "ticker": ticker, "date": d, "structure": "long_call"}
        self.contracts = contracts
        self.days_held = days_held
        self.dollars = dollars


def _grid(start: str, n: int):
    """n consecutive weekdays from `start` — the shape `_weekday_grid` returns."""
    out, d = [], date.fromisoformat(start)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _pos(pnl, contracts=1, days_held=None, dollars=None, start="2025-01-06",
         ticker="XYZ", d="2025-01-03", extra_grid=0, stored=True):
    """A position whose per-contract cumulative MTM path is `pnl`.

    `extra_grid` lengthens the grid past the exit the way a real row does (the
    price path runs to expiry or the 120-day cap, well past `days_held`).

    `stored=True` (the default) gives the fake record its own
    `realized_pnl_abs` — the row's STORED column, equal to `dollars` — so
    G-MTM reconciles two independent values rather than falling back to
    `pos.dollars` for both sides. Pass `stored=False` to build the degraded
    fixture on purpose (a record with no stored outcome at all).
    """
    days_held = days_held if days_held is not None else len(pnl)
    tail = [0.0] * extra_grid
    toks = ",".join("" if v is None else f"{v:.2f}" for v in list(pnl) + tail)
    if dollars is None:
        dollars = pnl[days_held - 1] * contracts
    realized_pnl_abs = dollars if stored else None
    return _FakePos(_grid(start, len(pnl) + extra_grid), toks, contracts,
                    days_held, dollars, ticker=ticker, d=d,
                    realized_pnl_abs=realized_pnl_abs)


# ── the reason the module exists: open positions are marked ──────────────────

def test_mtm_marks_the_open_path_while_realized_books_only_at_exit():
    """A position that dives then recovers to flat leaves NO trace on the
    close-bucketed curve and a real trough on the mark-to-market one. This is
    the defect `account_sim.print_equity` documents and this module fixes."""
    p = _pos([-100.0, -400.0, -250.0, 0.0])
    bc = M.book_curves([p])

    assert bc.mtm.levels == [-100.0, -400.0, -250.0, 0.0]
    assert bc.realized.levels == [0.0, 0.0, 0.0, 0.0]
    assert M.path_stats(bc.mtm, 25_000).max_dd == pytest.approx(-400.0)
    assert M.path_stats(bc.realized, 25_000).max_dd == pytest.approx(0.0)


def test_both_bases_share_one_session_axis():
    """Ulcer and time-under-water carry a denominator, so the two curves must be
    counted over the same sessions or the comparison is meaningless."""
    bc = M.book_curves([_pos([10.0, 20.0, 30.0])])
    assert bc.mtm.sessions == bc.realized.sessions
    assert len(bc.mtm) == len(bc.realized) == 3


def test_the_two_bases_agree_on_the_final_total():
    """They differ in PATH, never in destination: once everything has exited,
    both curves hold the same booked dollars."""
    a = _pos([-50.0, 300.0], contracts=3, start="2025-01-06")
    b = _pos([200.0, -75.0, -75.0], contracts=2, start="2025-01-07")
    bc = M.book_curves([a, b])
    assert bc.mtm.levels[-1] == pytest.approx(bc.realized.levels[-1])
    assert bc.mtm.levels[-1] == pytest.approx(300.0 * 3 + (-75.0) * 2)


def test_a_closed_position_keeps_its_realized_dollars_on_the_mtm_curve():
    """After the exit the result stays in book equity — the curve must not drop
    the position back to zero, which would fabricate a drawdown."""
    early = _pos([500.0], start="2025-01-06")
    late = _pos([0.0, 0.0], start="2025-01-08")
    bc = M.book_curves([early, late])
    assert bc.mtm.levels[-1] == pytest.approx(500.0)


# ── daily_pnl_csv semantics ──────────────────────────────────────────────────

def test_marks_scale_by_contracts_because_the_column_is_per_single_contract():
    p = _pos([-20.0, 60.0], contracts=7)
    _, dollars, _ = M.position_marks(p)
    assert dollars == [-140.0, 420.0]


def test_the_grid_past_the_exit_is_not_carried_into_the_curve():
    """`Trade.grid` runs to expiry / the 120-day cap; only [entry, exit] is the
    position's open window."""
    p = _pos([10.0, 20.0, 30.0], days_held=2, dollars=20.0, extra_grid=40)
    sess, dollars, _ = M.position_marks(p)
    assert dollars == [10.0, 20.0]
    assert len(sess) == 2


def test_a_blank_mark_carries_forward_and_is_counted_never_read_as_zero():
    """A blank token means UNPRICEABLE, not "worth nothing". Zeroing it would
    invent a round trip in the path; the count is returned so the caller can
    report the staleness instead of discovering it."""
    p = _pos([-100.0, None, -300.0], dollars=-300.0)
    sess, dollars, carried = M.position_marks(p)
    assert dollars == [-100.0, -100.0, -300.0]
    assert carried == 1


def test_a_leading_blank_is_zero_not_the_next_days_mark():
    p = _pos([None, -300.0], dollars=-300.0)
    _, dollars, carried = M.position_marks(p)
    assert dollars == [0.0, -300.0]
    assert carried == 1


def test_a_position_open_over_a_session_its_own_grid_skipped_still_marks_there():
    """Two positions can contribute different weekday grids to the shared axis.
    A session another row supplied must inherit this row's last mark, not 0."""
    long_pos = _pos([100.0, 100.0, 100.0, 100.0], start="2025-01-06")
    long_pos.rec["t"].grid = [date(2025, 1, 6), date(2025, 1, 8),
                              date(2025, 1, 9), date(2025, 1, 10)]
    other = _pos([0.0, 0.0], start="2025-01-07")
    bc = M.book_curves([long_pos, other])
    i = bc.mtm.sessions.index(date(2025, 1, 7))
    assert bc.mtm.levels[i] == pytest.approx(100.0)


def test_a_grid_length_disagreement_refuses_rather_than_truncating():
    p = _FakePos(_grid("2025-01-06", 3), "10.00,20.00", 1, 2, 20.0)
    with pytest.raises(ValueError, match="daily_pnl_csv"):
        M.position_marks(p)


def test_a_caller_supplied_mark_series_is_used_verbatim():
    """A synthesised hedge instrument has no `daily_pnl_csv`; it may hand its
    own path in rather than fake one."""
    p = _pos([1.0])
    p.mtm_sessions = [date(2025, 3, 3), date(2025, 3, 4)]
    p.mtm_dollars = [-250.0, 175.0]
    assert M.position_marks(p) == ([date(2025, 3, 3), date(2025, 3, 4)],
                                   [-250.0, 175.0], 0)


# ── G-MTM ────────────────────────────────────────────────────────────────────

def test_g_mtm_passes_when_the_marked_exit_equals_the_booked_dollars():
    bc = M.book_curves([_pos([-10.0, 250.0], contracts=4)])
    assert bc.reconciles
    assert (bc.n_reconciled, bc.n_positions) == (1, 1)
    assert bc.worst_mismatch == 0.0
    # The default fixture carries its own `realized_pnl_abs` (errata F12's
    # fix), so the gate compared it against a genuinely independent stored
    # column — not the degraded self-comparison fallback.
    assert bc.n_degraded == 0


def test_g_mtm_degrades_to_self_comparison_when_no_stored_outcome_exists():
    """A record with neither `realized_pnl_abs` nor `R_dol` has nothing
    independent to reconcile against, so the gate falls back to the caller's
    own `pos.dollars` for THAT position — the shape errata F2 removed,
    reopened per-position (errata F12). It must be counted, not silent."""
    degraded = _pos([10.0, 20.0], ticker="AAA", stored=False)
    normal = _pos([5.0, 40.0], ticker="BBB")
    bc = M.book_curves([degraded, normal])
    assert bc.n_degraded == 1
    # The degraded position still "reconciles" — it is being checked against
    # itself — which is exactly why the count, not just `.reconciles`, is
    # what a caller must inspect before claiming two independent columns.
    assert bc.reconciles
    assert bc.n_reconciled == 2


def test_g_mtm_degraded_count_is_zero_when_every_position_has_a_stored_column():
    bc = M.book_curves([_pos([1.0, 2.0], ticker="AAA"),
                        _pos([3.0, -4.0], ticker="BBB")])
    assert bc.n_degraded == 0


def test_g_mtm_returns_the_offending_position_not_just_a_flag():
    """The study exits non-zero on mismatch, so it has to be able to PRINT
    which positions disagreed and by how much."""
    good = _pos([5.0, 40.0], ticker="AAA")
    bad = _pos([5.0, 40.0], ticker="BBB", dollars=25.0)
    bc = M.book_curves([good, bad])
    assert not bc.reconciles
    assert [m.ticker for m in bc.mismatches] == ["BBB"]
    assert bc.mismatches[0].mtm_at_exit == pytest.approx(40.0)
    assert bc.mismatches[0].booked == pytest.approx(25.0)
    assert bc.mismatches[0].diff == pytest.approx(15.0)
    assert bc.worst_mismatch == pytest.approx(15.0)
    assert bc.n_reconciled == 1


def test_the_g_mtm_tolerance_is_an_argument_with_a_stated_default():
    """Not a magic number inside a comparison — a caller that loosens it has to
    say so, in its own report."""
    p = _pos([0.0, 100.0], dollars=100.5)
    assert M.TOL_DOLLARS == 0.01
    assert not M.book_curves([p]).reconciles
    assert M.book_curves([p], tolerance=1.0).reconciles


# ── path statistics ──────────────────────────────────────────────────────────

def test_max_drawdown_is_bear_deploys_function_not_a_second_implementation():
    from scripts.backtest_study.f4_deployment.bear_deploy import max_drawdown
    assert M.max_drawdown is max_drawdown


def test_time_under_water_counts_sessions_below_the_running_peak():
    # peak seeded at 0: session 0 is a fresh high, 1 and 2 are under it, 3 is a
    # new high.
    assert M.time_under_water([100.0, 40.0, 90.0, 150.0]) == pytest.approx(0.5)
    assert M.time_under_water([1.0, 2.0, 3.0]) == 0.0
    assert M.time_under_water([-1.0, -2.0]) == pytest.approx(1.0)


def test_ulcer_index_is_rms_percentage_drawdown_on_account_equity():
    # capital 1000; levels +0, -100 -> equity 1000 (peak), 900 -> -10% one
    # session, 0% the other -> RMS = sqrt((0 + 100)/2).
    assert M.ulcer_index([0.0, -100.0], 1000.0) == pytest.approx((100 / 2) ** 0.5)
    assert M.ulcer_index([0.0, 0.0, 50.0], 1000.0) == 0.0


def test_ulcer_index_refuses_a_missing_or_non_positive_capital_base():
    """A P&L curve starts at zero and has no percentage of its own; the base is
    required rather than defaulted to something invented here."""
    for bad in (None, 0, -1):
        with pytest.raises(ValueError):
            M.ulcer_index([0.0, -10.0], bad)


def test_path_stats_reports_both_co_primaries_and_the_worst_session():
    bc = M.book_curves([_pos([-100.0, -400.0, -250.0, 0.0])])
    s = M.path_stats(bc.mtm, 25_000)
    assert s.basis == M.MTM
    assert s.n_sessions == 4
    assert s.total == pytest.approx(0.0)
    assert s.max_dd == pytest.approx(-400.0)
    assert s.worst_session == pytest.approx(-300.0)   # -100 -> -400
    assert 0.0 < s.ulcer < 100.0
    assert s.tuw == pytest.approx(0.75)


def test_an_empty_book_returns_empty_curves_rather_than_raising():
    bc = M.book_curves([])
    assert len(bc.mtm) == len(bc.realized) == 0
    assert bc.reconciles and bc.n_positions == 0
    assert bc.n_degraded == 0
    assert M.path_stats(bc.mtm, 25_000).n_sessions == 0


# ── against the real v4 export ───────────────────────────────────────────────

def test_realized_basis_is_byte_identical_to_account_sim_equity_curve():
    """The realized curve is kept only for comparability with prior hedge
    verdicts, so it must be the SAME series `account_sim` produced them from —
    restated on the open-session axis, not recomputed differently.

    Positions are built from each row's STORED outcome, which is what
    `hedge_exposure.book_positions` does since the 2026-08-29 errata (F2). It
    used to build them from a `replay_sized(..., 1000.0)` REPLAY and then
    assert G-MTM passed — an assertion that could only hold while the gate
    compared that replay against itself. Now that the gate reconciles the
    marked exit against the row's stored `realized_pnl_abs`, a replay at a stop
    the row was never written under legitimately disagrees with it, and the
    gate says so.
    """
    from scripts.backtest_study.lib.book import load_book
    from scripts.backtest_study.f4_deployment.account_sim import Pos, equity_curve

    recs, diag = load_book(include_bs=False)
    if diag["era"] != "v4":
        pytest.skip(f"exports on disk are era {diag['era']}, not v4")

    positions = []
    for r in recs:
        t = r["t"]
        dh = min(int(r["days_held"]), len(t.grid))
        positions.append(Pos(
            rec=r, contracts=t.contracts,
            reserved=(r["max_loss_per_contract"] or 0.0) * t.contracts, dn=0.0,
            entry_sess=t.grid[0], exit_sess=t.grid[dh - 1],
            days_held=int(r["days_held"]), R=r["R"],
            dollars=M.stored_booked(r), exit_reason=r["exit_reason"]))

    bc = M.book_curves(positions)

    # G-MTM on the real book.
    assert bc.reconciles, bc.mismatches[:5]
    assert bc.n_reconciled == bc.n_positions == len(recs)

    booked = dict(zip(*equity_curve(positions)))
    on_axis = dict(zip(bc.realized.sessions, bc.realized.daily))
    for sess, dollars in booked.items():
        assert on_axis[sess] == pytest.approx(dollars, abs=1e-6), sess
    assert sum(booked.values()) == pytest.approx(bc.realized.levels[-1], abs=1e-6)

    # The whole point: the mark-to-market curve moves on sessions where the
    # close-bucketed one is flat. (Which curve carries the DEEPER drawdown is
    # an outcome, not an invariant — it is what the study measures, so nothing
    # is asserted about its direction here.)
    mtm = M.path_stats(bc.mtm, 25_000)
    rea = M.path_stats(bc.realized, 25_000)
    assert mtm.n_sessions == rea.n_sessions
    assert mtm.total == pytest.approx(rea.total, abs=1e-6)
    assert any(abs(a - b) > 1.0
               for a, b in zip(bc.mtm.levels, bc.realized.levels))
