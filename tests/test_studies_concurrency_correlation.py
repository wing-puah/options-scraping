"""`concurrency_correlation` — the book-state annotation, the arms, and the
estimator, all of which are pure functions no other study test covers.

Pre-registered
(`research/pre-registrations/f4_deployment/concurrency_correlation.md`). What
belongs here is the code-BEHAVIOUR claims a report cannot demonstrate for
itself:

  * `Pos.open_on` is the registration's HALF-OPEN occupancy rule
    (`entry_date <= s < exit_date`) — a position is NOT open on its own exit
    session. This deliberately differs from `account_sim.session_series`'s
    CLOSED convention (held THROUGH the exit session); pinned explicitly so a
    future edit cannot silently swap conventions.
  * `open_before` is the annotation rule (`entry_sess < s < exit_sess`) —
    same-session entries excluded, which is what makes the annotation
    look-ahead-free.
  * `state_for` counts six axes off a `BookState`, and a position (or a book
    peer) with `direction=None` (the missing-greek UNKNOWN) is EXCLUDED from
    every direction total rather than counted as a spurious zero-direction
    match.
  * `walk` runs the ceiling arms on a count that is RUNNING WITHIN the
    session (ladder order), never frozen at session open — a refused pick
    must never re-enter a later session's open book.
  * `arm_ck_rule` attributes C before K so a G4 refusal count never
    double-attributes a single refused pick.
  * `null_band` is a degenerate `(0.0, 0.0, [])` outside its domain
    (`n_refused` 0 or >= the base population) and otherwise deterministic on
    a fixed seed.
  * `x7_stratified` refuses to call a single readable band "discriminating" —
    a lone band is the whole sample relabelled, not a control.
  * `loo_by_ticker` reports the MIN fold, never the mean — the same
    leave-one-out discipline `protocol.loo_by_date` documents.
  * every frozen grid/floor pins the registration's own numbers, and
    `print_verdict` never invents a sixth verdict word.
"""
from __future__ import annotations

import ast
import math
import re
from datetime import date
from pathlib import Path

import pytest

from scripts.backtest_study.f4_deployment import concurrency_correlation as CC
from scripts.backtest_study.f4_deployment import portfolio_delta as PD

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "scripts" / "backtest_study" / "f4_deployment"
          / "concurrency_correlation.py")
SRC = MODULE.read_text(encoding="utf-8")
TREE = ast.parse(SRC)


# ── fixture builders ─────────────────────────────────────────────────────────

def _pos(ticker="AAA", sector="TECH", direction=1,
         entry=date(2025, 1, 6), exit_=date(2025, 1, 10),
         R=0.1, R_dol=None, dn=0.0, dt="2025-01-06"):
    return CC.Pos(rec={}, entry_sess=entry, exit_sess=exit_, date=dt,
                 ticker=ticker, direction=direction, sector=sector,
                 R=R, R_dol=R_dol, dn=dn)


def _state(**over):
    base = dict(n_open=0, n_same_dir=0, n_same_dir_sector=0,
               n_same_underlying=0, n_same_underlying_dir=0, net_dn=0.0)
    base.update(over)
    return CC.BookState(**base)


def _rows(n: int, gain: float, prefix: str = "r") -> list[dict]:
    return [dict(date=f"{prefix}{i}", a=gain, b=0.0, gain=gain)
            for i in range(n)]


# ── the runner's contract ────────────────────────────────────────────────────

def test_designed_refusal_codes_are_an_ast_literal_set() -> None:
    """`run.py` reads this with `ast` and never imports the module (see the
    module docstring's own note, verbatim from `portfolio_delta.py`)."""
    found = None
    for node in TREE.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(t, ast.Name) and t.id == "DESIGNED_REFUSAL_EXIT_CODES"
               for t in node.targets):
            found = node.value
    assert found is not None, "the runner cannot find the declaration at all"
    value = ast.literal_eval(found)
    assert isinstance(value, set)
    assert value == CC.DESIGNED_REFUSAL_EXIT_CODES == {2, 3}


def test_the_module_does_no_work_at_import_time() -> None:
    """`run.py` parses study modules with `ast` and never imports them, but
    the test suite DOES import this one."""
    top = [n for n in TREE.body
           if not isinstance(n, (ast.Import, ast.ImportFrom, ast.Assign,
                                 ast.AnnAssign, ast.FunctionDef, ast.ClassDef,
                                 ast.Expr, ast.If))]
    assert not top, f"module-level statements that do work: {top}"


# ── frozen constants: every one the registration commits to ─────────────────

def test_frozen_grids_match_the_registration() -> None:
    assert CC.ARM_C_GRID == (5, 8, 12, 20)
    assert CC.ARM_K_GRID == (2, 3, 5)
    assert CC.K_RELATIONS == ("same-direction", "same-direction-and-sector",
                              "same-underlying")
    assert CC.CONC_BANDS == ((0, 3), (3, 6), (6, 10), (10, 20), (20, 10 ** 9))


def test_frozen_floors_and_draws_match_the_registration() -> None:
    assert CC.MIN_MOVED_DATES == 25
    assert CC.MIN_N_TO_READ == 10
    assert CC.MIN_CELL_N == 20
    assert CC.DRAWS == 1000
    assert CC.SEED == 20260822


def test_delta_bands_is_portfolio_deltas_own_bands_object() -> None:
    """The X7 control names "portfolio_delta's own bands" — importing the
    object, not restating its values, is what stops the control from ever
    disagreeing with the study it controls against."""
    assert CC.DELTA_BANDS is PD.BANDS


# ── Pos.open_on: the half-open occupancy rule ───────────────────────────────

def test_open_on_is_half_open_not_open_on_its_own_exit_session() -> None:
    """`entry_date <= s < exit_date`. This is NOT `account_sim.session_series`'s
    CLOSED convention, which holds a position THROUGH its exit session."""
    p = _pos(entry=date(2025, 1, 6), exit_=date(2025, 1, 9))
    assert p.open_on(date(2025, 1, 5)) is False       # before entry
    assert p.open_on(date(2025, 1, 6)) is True         # entry session: open
    assert p.open_on(date(2025, 1, 8)) is True         # held session: open
    assert p.open_on(date(2025, 1, 9)) is False        # its OWN exit session
    assert p.open_on(date(2025, 1, 10)) is False        # after exit


def test_open_on_a_single_session_position_is_never_open() -> None:
    """entry == exit collapses the half-open interval to empty."""
    p = _pos(entry=date(2025, 1, 6), exit_=date(2025, 1, 6))
    assert p.open_on(date(2025, 1, 6)) is False


# ── open_before: same-session entries and exits are both excluded ──────────

def test_open_before_returns_exactly_the_strictly_bracketing_positions() -> None:
    s = date(2025, 1, 8)
    entered_today = _pos(ticker="A", entry=s, exit_=date(2025, 1, 12))
    exits_today = _pos(ticker="B", entry=date(2025, 1, 5), exit_=s)
    held_through = _pos(ticker="C", entry=date(2025, 1, 5),
                        exit_=date(2025, 1, 12))
    long_since_closed = _pos(ticker="D", entry=date(2025, 1, 1),
                             exit_=date(2025, 1, 3))
    admitted = [entered_today, exits_today, held_through, long_since_closed]
    result = CC.open_before(admitted, s)
    assert result == [held_through]


# ── state_for: the six axes, and the missing-greek exclusion ───────────────

def test_state_for_counts_all_six_axes() -> None:
    p = _pos(ticker="NVDA", sector="TECH", direction=1)
    book = [
        _pos(ticker="NVDA", sector="TECH", direction=1, dn=100.0),   # dir+sector+ticker match
        _pos(ticker="AMD", sector="TECH", direction=1, dn=50.0),     # dir+sector match, diff ticker
        _pos(ticker="XOM", sector="ENERGY", direction=1, dn=25.0),   # dir match only
        _pos(ticker="NVDA", sector="TECH", direction=-1, dn=-10.0),  # ticker match, opposite dir
        _pos(ticker="TSLA", sector="AUTO", direction=-1, dn=-5.0),   # nothing matches
    ]
    st = CC.state_for(p, book)
    assert st.n_open == 5
    assert st.n_same_dir == 3
    assert st.n_same_dir_sector == 2
    assert st.n_same_underlying == 2
    assert st.n_same_underlying_dir == 1
    assert st.net_dn == pytest.approx(100.0 + 50.0 + 25.0 - 10.0 - 5.0)


def test_state_for_excludes_a_position_with_unknown_direction_from_every_total() -> None:
    """`p` itself is UNKNOWN: its same-direction axes are always empty,
    regardless of what the book holds — never a spurious direction-0 match."""
    p = _pos(ticker="NVDA", direction=None)
    book = [
        _pos(ticker="NVDA", direction=1),
        _pos(ticker="NVDA", direction=None),
        _pos(ticker="AMD", direction=-1),
    ]
    st = CC.state_for(p, book)
    assert st.n_open == 3
    assert st.n_same_dir == 0
    assert st.n_same_dir_sector == 0
    assert st.n_same_underlying_dir == 0
    assert st.n_same_underlying == 2      # ticker match survives; direction axes do not


def test_state_for_excludes_a_book_peers_unknown_direction_from_same_dir() -> None:
    """A book peer with `direction=None` never counts toward `p`'s
    same-direction axes, even when it shares `p`'s ticker."""
    p = _pos(ticker="NVDA", direction=1)
    book = [_pos(ticker="NVDA", direction=None), _pos(ticker="AMD", direction=1)]
    st = CC.state_for(p, book)
    assert st.n_open == 2
    assert st.n_same_dir == 1                 # only AMD
    assert st.n_same_underlying == 1          # NVDA counts by ticker alone
    assert st.n_same_underlying_dir == 0      # NVDA's direction is unknown


# ── annotate_baseline: session-open book, never a later session ────────────

def test_annotate_baseline_excludes_same_session_peers_and_reads_only_the_past() -> None:
    d1, d2 = date(2025, 1, 6), date(2025, 1, 8)
    p1 = _pos(entry=d1, exit_=date(2025, 1, 20), dt="2025-01-06")
    p2 = _pos(entry=d2, exit_=date(2025, 1, 20), dt="2025-01-08")
    p3 = _pos(entry=d2, exit_=date(2025, 1, 20), dt="2025-01-08")
    states = CC.annotate_baseline([p1, p2, p3])
    assert states[id(p1)].n_open == 0     # nothing entered before d1
    assert states[id(p2)].n_open == 1     # only p1 open at d2's session-open
    assert states[id(p3)].n_open == 1     # p2, same-session peer, excluded


# ── walk: the running within-session count ──────────────────────────────────

def test_walk_uses_the_running_within_session_count_in_list_order() -> None:
    """A ceiling asks what the book already has when a pick is CONSIDERED, so
    the second pick of a session sees the first, and the third sees both —
    never the session-open count of zero for all three."""
    s = date(2025, 1, 6)
    a = _pos(ticker="AAA", entry=s, exit_=date(2025, 1, 10), dt="2025-01-06")
    b = _pos(ticker="BBB", entry=s, exit_=date(2025, 1, 10), dt="2025-01-06")
    c = _pos(ticker="CCC", entry=s, exit_=date(2025, 1, 10), dt="2025-01-06")
    kept, refused = CC.walk([a, b, c], CC.arm_c_rule(2))
    assert kept == [a, b]
    assert [p.ticker for p, _ in refused] == ["CCC"]
    assert refused[0][1] == "C>=2"


def test_walk_never_lets_a_refused_position_re_enter_a_later_sessions_book() -> None:
    s1, s2 = date(2025, 1, 6), date(2025, 1, 7)
    a = _pos(ticker="AAA", entry=s1, exit_=date(2025, 1, 20), dt="2025-01-06")
    b = _pos(ticker="BBB", entry=s1, exit_=date(2025, 1, 20), dt="2025-01-06")
    c = _pos(ticker="CCC", entry=s1, exit_=date(2025, 1, 20), dt="2025-01-06")
    d = _pos(ticker="DDD", entry=s2, exit_=date(2025, 1, 20), dt="2025-01-07")
    kept, refused = CC.walk([a, b, c, d], CC.arm_c_rule(2))
    refused_tickers = {p.ticker for p, _ in refused}
    assert "CCC" in refused_tickers
    assert all(q.ticker != "CCC" for q in kept)
    # session s2's book is built from `kept` only — c, refused on s1, is gone
    book_at_s2 = CC.open_before(kept, s2)
    assert all(q.ticker != "CCC" for q in book_at_s2)


# ── the arm rules, as pure functions of a BookState ─────────────────────────

def test_arm_c_rule_refuses_at_or_above_ceiling_only() -> None:
    rule = CC.arm_c_rule(5)
    p = _pos()
    assert rule(p, _state(n_open=4)) is None
    assert rule(p, _state(n_open=5)) == "C>=5"
    assert rule(p, _state(n_open=6)) == "C>=5"


@pytest.mark.parametrize("relation, field", [
    (CC.K_SAME_DIR, "n_same_dir"),
    (CC.K_SAME_DIR_SECTOR, "n_same_dir_sector"),
    (CC.K_SAME_UNDERLYING, "n_same_underlying"),
])
def test_arm_k_rule_reads_the_relations_own_book_state_field(
        relation: str, field: str) -> None:
    rule = CC.arm_k_rule(3, relation)
    p = _pos()
    assert rule(p, _state(**{field: 2})) is None
    assert rule(p, _state(**{field: 3})) == f"K>=3/{relation}"


def test_arm_k_rule_ignores_the_other_two_axes() -> None:
    """K on `n_same_dir` must not fire off `n_open` or `n_same_underlying`."""
    rule = CC.arm_k_rule(2, CC.K_SAME_DIR)
    p = _pos()
    st = _state(n_open=99, n_same_underlying=99, n_same_dir=1)
    assert rule(p, st) is None


def test_arm_ck_rule_attributes_c_before_k_when_both_bind() -> None:
    """Exactly one binding rule per refusal (G4) — C wins the tie."""
    rule = CC.arm_ck_rule(5, 2, CC.K_SAME_DIR)
    st = _state(n_open=5, n_same_dir=2)
    assert rule(_pos(), st) == "C>=5"


def test_arm_ck_rule_falls_through_to_k_when_c_does_not_bind() -> None:
    rule = CC.arm_ck_rule(5, 2, CC.K_SAME_DIR)
    st = _state(n_open=4, n_same_dir=2)
    assert rule(_pos(), st) == "K>=2/same-direction"


def test_arm_ck_rule_admits_when_neither_binds() -> None:
    rule = CC.arm_ck_rule(5, 2, CC.K_SAME_DIR)
    st = _state(n_open=4, n_same_dir=1)
    assert rule(_pos(), st) is None


# ── the concurrency bands ────────────────────────────────────────────────────

@pytest.mark.parametrize("n, idx", [
    (0, 0), (2, 0), (3, 1), (5, 1), (6, 2), (9, 2),
    (10, 3), (19, 3), (20, 4), (10 ** 6, 4),
])
def test_conc_band_index_over_the_frozen_bands(n: int, idx: int) -> None:
    assert CC.conc_band_index(n) == idx


def test_conc_band_label_the_open_ended_top_band() -> None:
    assert CC.conc_band_label(4) == "[20,inf)"
    assert CC.conc_band_label(0) == "[0,3)"
    assert CC.conc_band_label(2) == "[6,10)"


# ── paired_date_rows / mean_gain ────────────────────────────────────────────

def test_paired_date_rows_computes_gain_as_kept_mean_minus_base_mean() -> None:
    base = [_pos(dt="d1", R=1.0, ticker="A")]
    kept = [_pos(dt="d1", R=1.5, ticker="A")]
    rows, dropped = CC.paired_date_rows(kept, base)
    assert dropped == 0
    assert rows == [dict(date="d1", a=1.5, b=1.0, gain=0.5)]
    assert CC.mean_gain(rows) == pytest.approx(0.5)


def test_paired_date_rows_drops_dates_the_arm_keeps_nothing_on_and_reports_it() -> None:
    base = [_pos(dt="d1", R=1.0, ticker="A"),
           _pos(dt="d2", R=2.0, ticker="B"),
           _pos(dt="d3", R=3.0, ticker="C")]
    kept = [base[0], base[1]]     # the arm refused every d3 position
    rows, dropped = CC.paired_date_rows(kept, base)
    assert dropped == 1
    assert {r["date"] for r in rows} == {"d1", "d2"}


def test_mean_gain_of_no_rows_is_nan() -> None:
    assert math.isnan(CC.mean_gain([]))


# ── null_band: degenerate outside its domain, deterministic inside it ──────

def _multi_date_base() -> list[CC.Pos]:
    return [
        _pos(ticker="A", dt="d1", R=1.0), _pos(ticker="B", dt="d1", R=2.0),
        _pos(ticker="C", dt="d1", R=3.0), _pos(ticker="D", dt="d2", R=10.0),
        _pos(ticker="E", dt="d2", R=20.0), _pos(ticker="F", dt="d2", R=30.0),
    ]


def test_null_band_is_degenerate_when_nothing_is_refused() -> None:
    base = [_pos(dt=f"d{i}", R=float(i)) for i in range(5)]
    assert CC.null_band(base, 0, seed=1) == (0.0, 0.0, [])


def test_null_band_is_degenerate_when_the_whole_base_is_refused() -> None:
    base = [_pos(dt=f"d{i}", R=float(i)) for i in range(5)]
    assert CC.null_band(base, len(base), seed=1) == (0.0, 0.0, [])
    assert CC.null_band(base, len(base) + 1, seed=1) == (0.0, 0.0, [])


def test_null_band_is_deterministic_for_a_fixed_seed() -> None:
    base = _multi_date_base()
    r1 = CC.null_band(base, 2, seed=42, draws=50)
    r2 = CC.null_band(base, 2, seed=42, draws=50)
    assert r1 == r2


def test_null_band_differs_across_seeds() -> None:
    """A determinism pin is only meaningful next to a change detector."""
    base = _multi_date_base()
    r1 = CC.null_band(base, 2, seed=1, draws=50)
    r2 = CC.null_band(base, 2, seed=2, draws=50)
    assert r1 != r2


def test_null_band_brackets_its_own_draws() -> None:
    base = _multi_date_base()
    lo, hi, gains = CC.null_band(base, 2, seed=7, draws=300)
    assert gains
    assert lo <= hi
    assert min(gains) - 1e-9 <= lo
    assert hi <= max(gains) + 1e-9


# ── x7_stratified: a lone band is not a control ─────────────────────────────

def test_x7_a_single_readable_band_is_not_discriminating_and_cannot_pass() -> None:
    rows = _rows(CC.MIN_CELL_N, 0.5, prefix="b0")
    bands = {r["date"]: 0 for r in rows}
    res = CC.x7_stratified(rows, bands)
    assert res["readable"] == 1
    assert res["discriminating"] is False
    assert res["passes"] is False


def test_x7_respects_min_cell_n_a_band_under_the_floor_is_not_readable() -> None:
    rows = _rows(CC.MIN_CELL_N - 1, 0.5, prefix="b0")
    bands = {r["date"]: 0 for r in rows}
    res = CC.x7_stratified(rows, bands)
    assert res["readable"] == 0
    assert math.isnan(res["gain"])
    assert res["passes"] is False


def test_x7_can_pass_with_two_readable_bands_both_positive() -> None:
    rows = _rows(CC.MIN_CELL_N, 0.5, prefix="b0") + _rows(CC.MIN_CELL_N, 0.6, prefix="b1")
    bands = {}
    bands.update({r["date"]: 0 for r in rows[:CC.MIN_CELL_N]})
    bands.update({r["date"]: 1 for r in rows[CC.MIN_CELL_N:]})
    res = CC.x7_stratified(rows, bands)
    assert res["readable"] == 2
    assert res["discriminating"] is True
    assert res["passes"] is True


def test_x7_dates_with_no_band_assignment_are_dropped() -> None:
    rows = _rows(CC.MIN_CELL_N, 0.5, prefix="unbanded")
    res = CC.x7_stratified(rows, bands={})
    assert res["readable"] == 0


# ── direction_degeneracy: checked, not assumed ──────────────────────────────

def test_direction_degeneracy_true_on_a_long_only_book() -> None:
    d1, d2 = date(2025, 1, 6), date(2025, 1, 8)
    p1 = _pos(ticker="AAA", direction=1, entry=d1, exit_=date(2025, 2, 1),
              dt="2025-01-06")
    p2 = _pos(ticker="BBB", direction=1, entry=d2, exit_=date(2025, 2, 1),
              dt="2025-01-08")
    p3 = _pos(ticker="CCC", direction=1, entry=d2, exit_=date(2025, 2, 1),
              dt="2025-01-08")
    positions = [p1, p2, p3]
    states = CC.annotate_baseline(positions)
    deg = CC.direction_degeneracy(positions, states)
    assert deg["degenerate"] is True
    assert deg["total"] == 3 and deg["equal"] == 3


def test_direction_degeneracy_false_when_a_short_position_is_present() -> None:
    d1, d2 = date(2025, 1, 6), date(2025, 1, 8)
    p1 = _pos(ticker="AAA", direction=1, entry=d1, exit_=date(2025, 2, 1),
              dt="2025-01-06")
    q1 = _pos(ticker="ZZZ", direction=-1, entry=d1, exit_=date(2025, 2, 1),
              dt="2025-01-06")
    p2 = _pos(ticker="BBB", direction=1, entry=d2, exit_=date(2025, 2, 1),
              dt="2025-01-08")
    positions = [p1, q1, p2]
    states = CC.annotate_baseline(positions)
    deg = CC.direction_degeneracy(positions, states)
    assert deg["degenerate"] is False


# ── loo_by_ticker: the MIN over folds, never the mean ───────────────────────

def test_loo_by_ticker_is_not_evaluable_under_three_tickers() -> None:
    base = [_pos(ticker="A", dt="d1", R=1.0), _pos(ticker="B", dt="d2", R=2.0)]
    gain, folds = CC.loo_by_ticker(base, base)
    assert math.isnan(gain) and folds == 0


def test_loo_by_ticker_returns_the_min_fold_not_the_mean() -> None:
    base = [
        _pos(ticker="A", dt="d1", R=1.0),
        _pos(ticker="B", dt="d2", R=2.0),
        _pos(ticker="C", dt="d3", R=5.0),
    ]
    kept = [
        _pos(ticker="A", dt="d1", R=1.5),
        _pos(ticker="B", dt="d2", R=2.0),
    ]
    # by hand: drop A -> fold gain 0.0 ; drop B -> fold gain 0.5 ;
    # drop C -> fold gain 0.25. Mean of the three is 0.25 -- MIN is 0.0.
    gain, folds = CC.loo_by_ticker(kept, base)
    assert folds == 3
    assert gain == pytest.approx(0.0)


# ── verdict vocabulary: only the registration's words ────────────────────────

def _print_verdict_source() -> str:
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == "print_verdict":
            return ast.get_source_segment(SRC, node)
    raise AssertionError("print_verdict not found in the module")


def test_print_verdict_emits_only_the_registrations_five_words() -> None:
    """The registration's own vocabulary is ADOPT / ADVISORY ONLY / NOISE /
    UNDERPOWERED / RESTATEMENT. This module can never reach ADOPT from a
    single run — X4 needs BOTH eras and `lib/era.py` binds one run to one —
    so its ADOPT branch is HELD OPEN as `CANDIDATE-PENDING-X4`, disclosed in
    `NOT_PRE_REGISTERED` ("X4 IS PENDING BY CONSTRUCTION ... No arm can reach
    ADOPT from a single run"). No sixth word may appear."""
    src = _print_verdict_source()
    prefixes = re.findall(r'verdict = \(\s*f?"([A-Z][A-Z0-9\- ]*?)\s+—', src)
    assert set(prefixes) == {
        "UNDERPOWERED", "CANDIDATE-PENDING-X4", "RESTATEMENT",
        "ADVISORY ONLY", "NOISE"}
    # a bare, unqualified ADOPT verdict is never emitted by this study
    assert 'verdict = ("ADOPT' not in src
    assert 'verdict = (f"ADOPT' not in src


def test_the_verdict_assignment_appears_exactly_once_per_branch() -> None:
    """Five `verdict = (` sites, matching the five words above one-to-one —
    guards against a branch that silently falls through to another's string."""
    src = _print_verdict_source()
    assert src.count("verdict = (") == 5
