"""`hedge_exposure` — the claims that live in CODE rather than in a report.

The study is pre-registered
(`research/pre-registrations/f4_deployment/hedge_exposure.md`). What belongs
here is everything that is a code-BEHAVIOUR claim rather than a data claim —
each one a way the module could be deterministically, reproducibly wrong while
printing a clean report:

  * `DESIGNED_REFUSAL_EXIT_CODES` is an AST-LITERAL set. `run.py` parses it
    without importing the module, so an alias or a `frozenset(...)` call is
    invisible to it and a designed refusal would be reported as a FAILURE.
  * G-BLIND is NOT in that set. A trigger that moves when the outcome columns
    are stripped is a defect in this module, not a pre-registered refusal.
  * the committed constants are IMPORTED from `lib/`, never restated. A second
    copy of the tau grid or the fill gate is how two files come to disagree
    about what was registered.
  * `improvement()` is signed so POSITIVE is BETTER for every metric, including
    max drawdown, which is negative. Get that wrong and every clause of the bar
    inverts silently.
  * a cut re-runs the curve rather than slicing precomputed levels. A drawdown
    is path-dependent, so a sliced cut carries the excluded window's peak.
  * sizing SKIPS a sub-one-contract hedge and never floors it to 1 — the defect
    the registration told this module to inherit-fix.
  * the holding window extends one session past the episode. Without it a
    one-session episode opens and closes on the same mark, contributes exactly
    zero, and every ARM CS cell prints an identical curve to f=0 for an
    arithmetic reason rather than an economic one.

The 2026-08-29 errata (`research/hedge-exposure-errata.md`) added six more,
each of which was a way the module printed a clean report while being wrong:

  * F1 — a CONTRARY must clear the SAME evidence as a positive, sign-inverted.
    It used to need no clause at all, so $26 of noise on a max drawdown could
    escalate to the study's verdict. Tested clause by clause.
  * F2 — G-MTM must reconcile the marked exit against the row's STORED booked
    dollars. It used to compare one replay against itself and could not fail;
    the test below forces a mismatch and asserts the refusal.
  * F3 — both readings of the population clause are reported and NO
    study-level verdict is emitted; no count is asserted in code.
  * F4 — ARM RF is labelled UNREGISTERED wherever it prints, and ARM R's
    committed caveat is quoted verbatim.
  * F5 — the bootstrap resamples CHRONOLOGICALLY. Path statistics are
    order-dependent, so a resample that reorders the tape is not that
    statistic's sampling distribution.
  * F7 — `max_drawdown` lives in `lib/`, and `bear_deploy` imports it from
    there. A `lib/` module must not execute an f4 study on import.
"""
from __future__ import annotations

import ast
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.backtest_study.f4_deployment import hedge_exposure as HE
from scripts.backtest_study.lib import concentration as C
from scripts.backtest_study.lib import hedge_instrument as HI
from scripts.backtest_study.lib import mtm_curve as M

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "backtest_study" / "f4_deployment" / "hedge_exposure.py"


# ── the runner's contract ────────────────────────────────────────────────────

def test_designed_refusal_codes_are_an_ast_literal_set() -> None:
    """`run.py::_refusal_codes` reads this with `ast` and never imports the
    module, so it must survive `ast.literal_eval` as a bare set."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    found = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(t, ast.Name) and t.id == "DESIGNED_REFUSAL_EXIT_CODES"
               for t in node.targets):
            found = node.value
    assert found is not None, "the runner cannot find the declaration at all"
    value = ast.literal_eval(found)
    assert isinstance(value, set)
    assert value == HE.DESIGNED_REFUSAL_EXIT_CODES


def test_refusal_codes_inherit_the_two_era_refusals_and_add_g_mtm() -> None:
    from scripts.backtest_study.lib import era as era_mod

    assert set(era_mod.DESIGNED_REFUSAL_EXIT_CODES) <= HE.DESIGNED_REFUSAL_EXIT_CODES
    assert HE.EXIT_MTM_RECONCILE in HE.DESIGNED_REFUSAL_EXIT_CODES


def test_lookahead_is_a_failure_not_a_designed_refusal() -> None:
    """G-BLIND firing means the trigger reads an outcome column. That is a bug
    in this module, so the runner must DELETE -latest.txt rather than promote
    the report as the study's current, correct status."""
    assert HE.EXIT_LOOKAHEAD not in HE.DESIGNED_REFUSAL_EXIT_CODES
    assert HE.EXIT_LOOKAHEAD == 1


def test_module_has_a_one_line_summary_first() -> None:
    """`run.py list` shows the docstring's FIRST line."""
    first = HE.__doc__.splitlines()[0]
    assert first.startswith("HEDGE-EXPOSURE")
    assert first.endswith("?")


# ── committed constants are imported, never restated ─────────────────────────

def test_committed_constants_are_the_library_objects() -> None:
    assert HE.TAU_GRID is C.TAU_GRID == (0.30, 0.35, 0.40)
    assert HE.F_GRID is C.F_GRID == (0.25, 0.50, 1.00)
    assert HE.MIN_TRIGGER_DATES is C.MIN_TRIGGER_DATES == 25
    assert HE.HEDGE_PRESSURE_CUT is C.HEDGE_PRESSURE_CUT == 50
    assert HE.FILL_GATE is HI.FILL_GATE == 0.60


def test_bonferroni_denominator_is_the_registered_nine_cells() -> None:
    assert HE.N_CELLS == 9
    assert HE.ALPHA == pytest.approx(0.05 / 9)


# ── metric algebra ───────────────────────────────────────────────────────────

def _stats(max_dd=0.0, ulcer=0.0, tuw=0.0):
    return M.PathStats(basis=M.MTM, n_sessions=1, total=0.0, max_dd=max_dd,
                       ulcer=ulcer, tuw=tuw, worst_session=0.0)


def test_improvement_is_positive_is_better_for_every_metric() -> None:
    """max drawdown is NEGATIVE dollars, so a shallower one is a LARGER number;
    Ulcer and time-under-water are costs, so a smaller one is better. All three
    must come back positive-is-better or the bar inverts."""
    base = _stats(max_dd=-1000.0, ulcer=10.0, tuw=0.9)
    better = _stats(max_dd=-600.0, ulcer=8.0, tuw=0.8)
    worse = _stats(max_dd=-1400.0, ulcer=12.0, tuw=0.95)
    for metric in (HE.METRIC_MAXDD, HE.METRIC_ULCER, HE.METRIC_TUW):
        assert HE.improvement(base, better, metric) > 0, metric
        assert HE.improvement(base, worse, metric) < 0, metric
        assert HE.improvement(base, base, metric) == 0, metric


def test_improvement_refuses_an_unknown_metric() -> None:
    with pytest.raises(ValueError):
        HE.improvement(_stats(), _stats(), "sharpe")


def test_curve_of_levels_are_the_running_sum_of_the_changes() -> None:
    sess = [date(2025, 1, d) for d in (6, 7, 8)]
    c = HE.curve_of(sess, [10.0, -4.0, 2.0])
    assert c.levels == [10.0, 6.0, 8.0]
    assert c.daily == [10.0, -4.0, 2.0]


def test_a_cut_reruns_the_curve_rather_than_slicing_the_levels() -> None:
    """A drawdown is path-dependent. If a cut kept the precomputed levels, the
    excluded window's peak would travel into the remainder and the surviving
    sessions would show a drawdown they never had."""
    sess = [date(2025, 1, d) for d in (6, 7, 8, 9)]
    daily = [100.0, -100.0, 5.0, -5.0]      # a big spike, then a quiet tail
    keep = {sess[2], sess[3]}
    st = HE.stats_on(sess, daily, 25_000, keep)
    assert st.n_sessions == 2
    # +5 then -5: the peak is 5, the drawdown is -5. NOT the -100 of the spike.
    assert st.max_dd == pytest.approx(-5.0)


def test_hedged_daily_adds_the_hedge_only_on_its_own_sessions() -> None:
    sess = [date(2025, 1, d) for d in (6, 7, 8)]
    out = HE.hedged_daily(sess, [1.0, 1.0, 1.0], {sess[1]: 50.0})
    assert out == [1.0, 51.0, 1.0]


# ── sizing: the inherited fix ────────────────────────────────────────────────

def test_a_sub_one_contract_hedge_is_skipped_never_floored_to_one() -> None:
    """`max(1, int(f x contracts))` silently promotes every hedge to full size
    whenever the risk size is one contract — the defect the registration names.
    account_sim ARM H's fix is to SKIP, and 0 here is that skip."""
    budget = 500.0
    debit = 400.0                       # risk_contracts -> 1
    assert HE._contracts_for(debit, 1.00, budget) == 1
    assert HE._contracts_for(debit, 0.50, budget) == 0
    assert HE._contracts_for(debit, 0.25, budget) == 0


def test_sizing_scales_when_the_instrument_is_cheap_enough_to_fit() -> None:
    assert HE._contracts_for(50.0, 1.00, 500.0) == 10
    assert HE._contracts_for(50.0, 0.50, 500.0) == 5
    assert HE._contracts_for(50.0, 0.25, 500.0) == 2


def test_an_unsizable_instrument_is_zero_not_one() -> None:
    assert HE._contracts_for(0.0, 1.00, 500.0) == 0
    assert HE._contracts_for(None, 1.00, 500.0) == 0


# ── the holding window ───────────────────────────────────────────────────────

def _universe(n: int) -> list[date]:
    return [date(2025, 1, 6) + __import__("datetime").timedelta(days=i)
            for i in range(n)]


def test_hold_window_extends_one_session_past_the_episode() -> None:
    uni = _universe(5)
    assert HE.hold_window([uni[1]], uni) == [uni[1], uni[2]]
    assert HE.hold_window(uni[1:3], uni) == uni[1:4]


def test_hold_window_does_not_run_off_the_end_of_the_universe() -> None:
    uni = _universe(3)
    assert HE.hold_window([uni[-1]], uni) == [uni[-1]]


# ── ARM N's matching ─────────────────────────────────────────────────────────

def test_peak_debit_is_zero_for_a_cell_that_placed_nothing() -> None:
    assert HE.peak_debit([]) == 0.0
    assert HE.peak_debit([HE.Leg(episode=(), proxy="SPY")]) == 0.0


def test_merge_sums_overlapping_sessions() -> None:
    d = date(2025, 1, 6)
    assert HE.merge([{d: 1.0}, {d: 2.5}, {}]) == {d: 3.5}


def test_month_blocks_are_the_date_cluster_not_the_session() -> None:
    """Adjacent sessions share almost the whole open book, so the resampling
    unit is the calendar month, never the session."""
    axis = [date(2025, 1, 6), date(2025, 1, 20), date(2025, 2, 3)]
    blocks = HE.month_blocks(axis)
    assert blocks == [[0, 1], [2]]


def test_pctile_interpolates_and_survives_an_empty_band() -> None:
    assert HE.pctile([0.0, 1.0, 2.0, 3.0], 0.95) == pytest.approx(2.85)
    assert math.isnan(HE.pctile([], 0.95))


# ── the verdict vocabulary ───────────────────────────────────────────────────

def test_every_registered_verdict_word_is_declared() -> None:
    """The registration words six verdicts. A module that can only print five
    has silently dropped one of them."""
    assert set(HE.VERDICTS) == {
        "MECHANISM-FOUND", "NULL", "CONTRARY", "UNDERPOWERED",
        "NOT EVALUABLE", "MEASUREMENT-ONLY"}


BANNED = ("sharpe", "annualis", "annualiz", "timetorecover", "time_to_recover")


def test_no_banned_statistic_is_computed_anywhere() -> None:
    """Standing research-tier ban: no annualised figure, no Sharpe, no
    time-to-recover.

    Checked on IDENTIFIERS rather than on the raw text, because the report says
    the ban out loud in prose and must be allowed to: a computed statistic needs
    a name, an attribute or a call, and none of those may carry one of these
    words. `path_stats` is the only place a path statistic is produced at all,
    and `mtm_curve` owns which ones exist."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    offenders = sorted(n for n in names
                       if any(b in n.lower() for b in BANNED))
    assert not offenders, f"banned statistic named in code: {offenders}"


def test_the_only_path_statistics_are_the_ones_mtm_curve_defines() -> None:
    """Nothing here may add a statistic the study refuses to print."""
    assert set(M.PathStats.__dataclass_fields__) == {
        "basis", "n_sessions", "total", "max_dd", "ulcer", "tuw",
        "worst_session"}


# ═══════════════════════════════════════════════════════════════════════════
# F1 — a CONTRARY carries the same clause set as a positive, sign-inverted
# ═══════════════════════════════════════════════════════════════════════════

def _contrary_case(**over):
    """Evidence that clears every clause of the NEGATIVE bar, before `over`.

    Deliberately built as plain metric-keyed maps: `evaluate_contrary` is pure,
    so each clause can be broken on its own and the rest left standing.
    """
    case = dict(
        base=_stats(max_dd=-1000.0, ulcer=10.0, tuw=0.9),
        hedged=_stats(max_dd=-1400.0, ulcer=12.0, tuw=0.95),   # 1' worse
        cis={HE.METRIC_ULCER: (-0.50, -0.90, -0.10),           # 2' below zero
             HE.METRIC_TUW: (0.0, -0.10, 0.10)},
        arm_n_p05={HE.METRIC_ULCER: -0.20, HE.METRIC_TUW: 0.0},  # 3'
        per_year={HE.METRIC_ULCER: {2024: -0.40, 2025: -0.30, 2026: 0.10},
                  HE.METRIC_TUW: {2024: 0.0}},                 # 4'
        cuts={HE.METRIC_ULCER: {"ex_a": -0.20, "ex_b": -0.30},
              HE.METRIC_TUW: {}},                              # 5'
        loo={HE.METRIC_ULCER: [-0.10, -0.20, -0.30],
             HE.METRIC_TUW: []},                               # 6'
    )
    case.update(over)
    return case


def test_the_negative_bar_is_met_when_every_clause_holds() -> None:
    res = HE.evaluate_contrary(**_contrary_case())
    assert res["contrary"] is True
    assert res["metric"] == HE.METRIC_ULCER
    assert all(res[f"n{i}"] for i in range(1, 7))


# One entry per clause: what to break, and which clause number must go False.
_CONTRARY_BREAKS = [
    # 1' — the drawdown is no worse than unhedged.
    ("n1", dict(hedged=_stats(max_dd=-900.0, ulcer=12.0, tuw=0.95))),
    # 2' — the CI straddles zero, so no co-primary is reliably negative.
    ("n2", dict(cis={HE.METRIC_ULCER: (-0.50, -0.90, 0.10),
                     HE.METRIC_TUW: (0.0, -0.10, 0.10)})),
    # 3' — the point estimate sits INSIDE the random null's lower tail.
    ("n3", dict(arm_n_p05={HE.METRIC_ULCER: -0.90, HE.METRIC_TUW: 0.0})),
    # 4' — only one of the book's years is negative.
    ("n4", dict(per_year={HE.METRIC_ULCER: {2024: -0.40, 2025: 0.30, 2026: 0.10},
                          HE.METRIC_TUW: {2024: 0.0}})),
    # 5' — an ex-window cut flips the sign.
    ("n5", dict(cuts={HE.METRIC_ULCER: {"ex_a": -0.20, "ex_b": 0.30},
                      HE.METRIC_TUW: {}})),
    # 6' — one leave-one-date-out fold flips the sign.
    ("n6", dict(loo={HE.METRIC_ULCER: [-0.10, 0.20, -0.30],
                     HE.METRIC_TUW: []})),
]


@pytest.mark.parametrize("clause,broken", _CONTRARY_BREAKS,
                         ids=[c for c, _ in _CONTRARY_BREAKS])
def test_breaking_any_single_clause_drops_the_contrary_to_null(clause, broken) -> None:
    """Each clause is load-bearing on its own. Before the errata a CONTRARY
    needed NONE of them — `hedged.max_dd < base.max_dd and point < 0` was the
    whole test, which is $26 of noise away from a printed finding."""
    res = HE.evaluate_contrary(**_contrary_case(**broken))
    assert res[clause] is False, f"{clause} should have been broken"
    assert res["contrary"] is False
    assert HE.cell_verdict({"candidate": False, "contrary": res}) == "NULL"


def test_a_contrary_needs_a_ci_below_zero_not_merely_a_negative_point() -> None:
    """The clause the old code skipped entirely: a point estimate on the wrong
    side of zero is not evidence, and an interval that straddles zero says so."""
    res = HE.evaluate_contrary(**_contrary_case(
        cis={HE.METRIC_ULCER: (-0.50, -0.90, 0.60),
             HE.METRIC_TUW: (0.0, -0.10, 0.10)}))
    assert res["n1"] is True                    # drawdown IS worse
    assert res["n2"] is False                   # but nothing is reliable
    assert res["metric"] is None
    assert res["point"] is None
    assert res["contrary"] is False


def test_a_metricless_negative_reports_no_direction_at_all() -> None:
    """With no co-primary below zero there is no metric to read clauses 3'-6'
    on, and the module must not fall back to one and quote a direction."""
    res = HE.evaluate_contrary(**_contrary_case(
        cis={HE.METRIC_ULCER: (0.5, 0.1, 0.9), HE.METRIC_TUW: (0.0, -0.1, 0.1)}))
    assert res["metric"] is None
    assert (res["n3"], res["n4"], res["n5"], res["n6"]) == (False,) * 4


def test_cell_verdict_prefers_candidate_and_falls_through_to_null() -> None:
    assert HE.cell_verdict({"candidate": True,
                            "contrary": {"contrary": True}}) == "CANDIDATE"
    assert HE.cell_verdict({"candidate": False,
                            "contrary": {"contrary": True}}) == "CONTRARY"
    assert HE.cell_verdict({"candidate": False,
                            "contrary": {"contrary": False}}) == "NULL"
    assert HE.cell_verdict({}) == "NULL"


def test_arm_n_band_returns_both_tails_so_a_negative_has_a_null_too() -> None:
    """Clause 3 reads the 95th percentile; clause 3' reads the 5th. A band that
    only carried one tail is how a negative came to have no null at all."""
    band = HE.arm_n_band([], {}, [], [], [], 25_000.0, 1.0, 500.0,
                         HI.RULE_BAND, HE.CO_PRIMARIES)
    for m in HE.CO_PRIMARIES:
        p05, p95 = band[m]
        assert math.isnan(p05) and math.isnan(p95)


# ═══════════════════════════════════════════════════════════════════════════
# F2 — G-MTM reconciles against the STORED outcome and CAN fail
# ═══════════════════════════════════════════════════════════════════════════

class _FakeTrade:
    def __init__(self, grid, pnl_csv, booked):
        self.grid = grid
        self.row = {"daily_pnl_csv": pnl_csv, "realized_pnl_abs": booked}


class _FakePos:
    """Duck-typed on `account_sim.Pos`, carrying BOTH a stored booked column
    and a caller-supplied `dollars`, so the two can be made to disagree."""

    def __init__(self, marks, booked_stored, dollars, contracts=1,
                 ticker="XYZ"):
        grid = [date(2025, 1, 6) + timedelta(days=i) for i in range(len(marks))]
        toks = ",".join(f"{v:.2f}" for v in marks)
        self.rec = {"t": _FakeTrade(grid, toks, booked_stored), "ticker": ticker,
                    "date": "2025-01-03", "structure": "long_call",
                    "R_dol": booked_stored}
        self.contracts = contracts
        self.days_held = len(marks)
        self.dollars = dollars


def test_g_mtm_reconciles_against_the_stored_column_not_the_callers_dollars() -> None:
    """THE errata F2 test. The caller's own `dollars` agrees with the marked
    exit perfectly — which is exactly the shape the old gate checked and always
    passed — while the row's STORED booked figure does not. The gate must
    refuse anyway, or it is comparing a replay with itself."""
    p = _FakePos(marks=[10.0, 40.0], booked_stored=25.0, dollars=40.0)
    bc = M.book_curves([p])
    assert not bc.reconciles
    assert bc.mismatches[0].booked == pytest.approx(25.0)
    assert bc.mismatches[0].mtm_at_exit == pytest.approx(40.0)
    assert bc.mismatches[0].diff == pytest.approx(15.0)


def test_the_g_mtm_gate_refuses_with_the_registered_exit_code(capsys) -> None:
    """A gate that cannot fail is not a gate. Forced to fail, the study must
    return its pre-registered refusal code — not print and carry on."""
    bad = _FakePos(marks=[10.0, 40.0], booked_stored=25.0, dollars=40.0,
                   ticker="BAD")
    rc = HE.check_mtm(M.book_curves([bad]))
    assert rc == HE.EXIT_MTM_RECONCILE
    assert HE.EXIT_MTM_RECONCILE in HE.DESIGNED_REFUSAL_EXIT_CODES
    out = capsys.readouterr().out
    assert "G-MTM FAILED" in out and "BAD" in out


def test_g_mtm_passes_when_the_two_stored_columns_agree(capsys) -> None:
    good = _FakePos(marks=[10.0, 40.0], booked_stored=40.0, dollars=40.0)
    assert HE.check_mtm(M.book_curves([good])) == 0
    assert "G-MTM PASS" in capsys.readouterr().out


def test_the_tolerance_scales_per_contract_because_the_column_does() -> None:
    """`daily_pnl_csv` is written at 2 decimals PER SINGLE CONTRACT, so the
    finest distinction it can express at N contracts is a cent times N."""
    assert M.tolerance_for(1) == pytest.approx(M.TOL_DOLLARS)
    assert M.tolerance_for(50) == pytest.approx(50 * M.TOL_DOLLARS)
    assert M.tolerance_for(0) == pytest.approx(M.TOL_DOLLARS)


def test_book_positions_take_their_exit_and_dollars_from_the_stored_row() -> None:
    """The replay is no longer on both sides of G-MTM's equals sign. It runs
    alongside, and `replay_divergence` discloses the gap."""
    src = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "book_positions")
    calls = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert not any("replay" in c for c in calls), (
        "book_positions must not replay the row it reconciles")
    assert "M.stored_booked" in {ast.unparse(n.func) for n in ast.walk(fn)
                                 if isinstance(n, ast.Call)}
    assert any(isinstance(n, ast.FunctionDef) and n.name == "replay_divergence"
               for n in tree.body)


# ═══════════════════════════════════════════════════════════════════════════
# F3 — both populations, no study-level verdict, no asserted count
# ═══════════════════════════════════════════════════════════════════════════

def test_both_readings_of_the_population_clause_are_declared() -> None:
    assert set(HE.POP_LABELS) == {HE.POP_REAL, HE.POP_ALL}
    assert HE.POP_BOTH not in HE.POP_LABELS


def test_the_default_run_reports_both_populations() -> None:
    """`run.py` invokes the module bare, so the DEFAULT is what the errata
    binds: report both, conclude from neither."""
    src = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    defaults = {}
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call)
                and ast.unparse(node.func).endswith("add_argument")):
            arg = node.args[0].value if node.args else ""
            for kw in node.keywords:
                if kw.arg == "default":
                    defaults[arg] = ast.unparse(kw.value)
    assert defaults.get("--sources") == "POP_BOTH"


def test_no_study_level_verdict_variable_exists_anywhere() -> None:
    """The old module assigned a study-level `verdict` and printed it. The
    errata REMOVES that: cells still carry a word (`cell.verdict`, an
    attribute), the study does not."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    assigned = {t.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
                for t in node.targets if isinstance(t, ast.Name)}
    assert "verdict" not in assigned


def test_no_population_count_is_hardcoded_in_the_module() -> None:
    """"No stored expected figure" is a standing rule and the errata restates
    it: the asserted "485 / 140" string had to go. Every count in the report is
    computed at run time from the export named in the header."""
    src = MODULE.read_text(encoding="utf-8")
    for token in ("485", "996", "140 signal dates", "145 dates"):
        assert token not in src, f"hardcoded population figure {token!r}"


def test_the_cell_words_are_the_only_thing_a_cell_can_be_called() -> None:
    for res in ({"candidate": True, "contrary": {"contrary": False}},
                {"candidate": False, "contrary": {"contrary": True}},
                {"candidate": False, "contrary": {"contrary": False}}):
        assert HE.cell_verdict(res) in ("CANDIDATE", "CONTRARY", "NULL")


# ═══════════════════════════════════════════════════════════════════════════
# F4 — ARM RF is labelled, ARM R's committed caveat is quoted
# ═══════════════════════════════════════════════════════════════════════════

def test_arm_rf_carries_its_unregistered_label_on_every_row() -> None:
    """`study_review` and every paste-the-report path read the REPORT, not
    `research/arm-index.md`, and ARM RF prints the largest positive numbers in
    it while not appearing in the registration at all."""
    assert HE.ARM_RF_LABEL == "UNREGISTERED — ADDED AFTER COMMIT"
    src = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    notes = [ast.unparse(kw.value) for node in ast.walk(tree)
             if isinstance(node, ast.Call)
             and ast.unparse(node.func) == "print_stats_row"
             for kw in node.keywords if kw.arg == "note"]
    assert notes == ["ARM_RF_LABEL"], (
        "every ARM RF row, and only ARM RF rows, carry the label")


def test_print_stats_row_appends_the_note_it_is_given(capsys) -> None:
    st = M.PathStats(basis=M.MTM, n_sessions=1, total=1.0, max_dd=-1.0,
                     ulcer=1.0, tuw=0.5, worst_session=-1.0)
    HE.print_stats_row("ARM RF x", st, note=HE.ARM_RF_LABEL)
    assert HE.ARM_RF_LABEL in capsys.readouterr().out


def test_arm_r_caveat_is_the_registrations_own_words() -> None:
    for phrase in ("floor on feasibility", "not a recommendation",
                   "not an instrument the operator trades"):
        assert phrase in HE.ARM_R_CAVEAT.replace("\n  ", " ")


# ═══════════════════════════════════════════════════════════════════════════
# F5 — the bootstrap resamples chronologically
# ═══════════════════════════════════════════════════════════════════════════

def _axis(n: int) -> list:
    import datetime as _dt
    out, d = [], date(2025, 1, 1)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += _dt.timedelta(days=1)
    return out


def test_the_resample_runs_forwards_in_time() -> None:
    """Max drawdown, Ulcer and time-under-water are PATH-DEPENDENT. A resample
    that concatenates blocks in drawn order makes the ordering part of the
    statistic, so its spread is not that statistic's sampling distribution."""
    import random as _random
    rng = _random.Random(7)
    for _ in range(50):
        idx = HE._chronological_index(120, 21, rng)
        assert idx == sorted(idx)
        assert len(idx) == 120
        assert max(idx) < 120


def test_the_withdrawn_estimator_is_kept_only_as_a_diagnostic() -> None:
    """It is still computed so the report can state whether clause 2's outcome
    survived the change — and it is reachable ONLY by asking for it."""
    import inspect
    assert HE.BOOT_CHRONO != HE.BOOT_SHUFFLE
    sig = inspect.signature(HE.boot_ci)
    assert sig.parameters["estimator"].default == HE.BOOT_CHRONO


def test_the_block_is_the_median_month_floored_at_a_minimum() -> None:
    axis = _axis(250)
    assert HE.block_length(axis) >= HE.BOOT_BLOCK_MIN
    sizes = sorted(len(b) for b in HE.month_blocks(axis))
    assert HE.block_length(axis) == max(HE.BOOT_BLOCK_MIN,
                                        sizes[len(sizes) // 2])
    assert HE.block_length([]) == 1


def test_a_flat_hedge_gives_a_zero_point_estimate_under_both_estimators() -> None:
    axis = _axis(60)
    base = [1.0, -2.0] * 30
    for est in (HE.BOOT_CHRONO, HE.BOOT_SHUFFLE):
        pt, lo, hi = HE.boot_ci(axis, base, list(base), 25_000.0,
                                HE.METRIC_ULCER, n=20, estimator=est)
        assert pt == pytest.approx(0.0)
        assert lo == pytest.approx(0.0) and hi == pytest.approx(0.0)


# ═══════════════════════════════════════════════════════════════════════════
# F6 — ARM P is declared inert, and is not redefined
# ═══════════════════════════════════════════════════════════════════════════

def test_arm_p_is_declared_inert_in_the_report_in_those_words() -> None:
    src = MODULE.read_text(encoding="utf-8")
    assert "ARM P IS INERT AS REGISTERED" in src
    assert "UNREACHABLE BY CONSTRUCTION" in src


def test_arm_p_is_still_literally_arm_cs_session_set() -> None:
    """Redefining ARM P into something informative would be a POST-HOC ARM.
    The registration's wording is degenerate; the module says so and leaves it
    alone."""
    src = MODULE.read_text(encoding="utf-8")
    assert "p_trig = list(cs_trig)" in src


# ═══════════════════════════════════════════════════════════════════════════
# F7 — the layering direction
# ═══════════════════════════════════════════════════════════════════════════

def test_max_drawdown_lives_in_lib_and_bear_deploy_imports_it() -> None:
    """A `lib/` module importing an f4 study executes that study at import
    time. `lib/greeks.py`, `lib/sectors.py` and `lib/hedge_instrument.py` each
    state and honour the opposite rule."""
    from scripts.backtest_study.f4_deployment import bear_deploy

    assert M.max_drawdown.__module__.endswith("lib.mtm_curve")
    assert bear_deploy.max_drawdown is M.max_drawdown


def test_mtm_curve_imports_nothing_from_a_study_family() -> None:
    text = (ROOT / "scripts" / "backtest_study" / "lib" / "mtm_curve.py"
            ).read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "f1_selection" not in node.module
            assert "f2_management" not in node.module
            assert "f3_structure" not in node.module
            assert "f4_deployment" not in node.module


def test_the_drawdown_is_still_the_same_arithmetic_it_always_was() -> None:
    """Moved, not rewritten: the peak seeds at 0.0, so a book that never gets
    above flat still reports its whole fall."""
    assert M.max_drawdown([]) == 0.0
    assert M.max_drawdown([-10.0, -5.0]) == pytest.approx(-15.0)
    assert M.max_drawdown([100.0, -40.0, 10.0]) == pytest.approx(-40.0)
    assert M.max_drawdown([10.0, 20.0]) == 0.0
