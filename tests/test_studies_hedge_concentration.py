"""`hedge_concentration` — the claims that live in CODE rather than in a report.

The study is pre-registered
(`research/pre-registrations/f4_deployment/hedge_concentration.md`). What
belongs here is everything that is a code-BEHAVIOUR claim rather than a data
claim — each one a way the module could be deterministically, reproducibly
wrong while printing a clean report:

  * `DESIGNED_REFUSAL_EXIT_CODES` is an AST-LITERAL set. `run.py` parses it
    without importing the module, so an alias or a `frozenset(...)` call is
    invisible to it and a designed refusal would be reported as a FAILURE.
    G-ADMIT (5) is this study's own; G-MTM (4) is imported from
    `hedge_exposure`; 2 and 3 come from `lib/era.py`.
  * G-BLIND is NOT in that set. A trigger that moves when the outcome columns
    are stripped is a DEFECT in this module, not a pre-registered refusal, so
    it exits 1 and the runner deletes `-latest.txt`.
  * the committed constants that belong to `lib/` are IMPORTED from it, and the
    tau grid that does NOT — this study's registration fixes its own
    {0.45, 0.55, 0.65} against `hedge_exposure`'s {0.30, 0.35, 0.40} — is
    stated here and is deliberately not `C.TAU_GRID`. Sharing that constant
    would silently run the study on a trigger nobody registered.
  * `stage1_verdict` maps the registration's four words EXACTLY. A module that
    reaches PRECONDITION-FOUND on five of six clauses, or that calls a clause-4
    failure a NULL, has silently rewritten the registration.
  * Stage 2 is NOT ENTERED on a non-FOUND Stage 1. "A hedge tested on a trigger
    that carries no information is a hedge tested on noise" is an anti-tuning
    clause, so the dispatch has to be a testable object rather than an `if`
    buried in a 900-line `main`.
  * the overlay ledger SKIPS a sub-one-contract hedge and never floors it, and
    a refused admission is counted by its binding constraint. Both are the
    difference between "the account could not carry this hedge" and "the hedge
    was carried for free".
  * G-MTM is read on `TARGET_POSITION`. The sim re-sizes and re-exits what it
    admits, so the stored-column target describes a different position by
    construction and the gate would refuse a correct book.
  * no population count is stored, no banned statistic is named, and every
    registered verdict word is declared.
"""
from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.backtest_study.f4_deployment import account_sim as A
from scripts.backtest_study.f4_deployment import hedge_concentration as HC
from scripts.backtest_study.f4_deployment import hedge_exposure as HE
from scripts.backtest_study.lib import concentration as C
from scripts.backtest_study.lib import forward_drawdown as F
from scripts.backtest_study.lib import hedge_instrument as HI
from scripts.backtest_study.lib import mtm_curve as M
from scripts.backtest_study.lib import protocol as P

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "scripts" / "backtest_study" / "f4_deployment"
          / "hedge_concentration.py")
SRC = MODULE.read_text(encoding="utf-8")
TREE = ast.parse(SRC)


# ── the runner's contract ────────────────────────────────────────────────────

def test_designed_refusal_codes_are_an_ast_literal_set() -> None:
    """`run.py::_refusal_codes` reads this with `ast` and never imports the
    module, so it must survive `ast.literal_eval` as a bare set."""
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
    assert value == HC.DESIGNED_REFUSAL_EXIT_CODES == {2, 3, 4, 5}


def test_refusal_codes_are_era_plus_g_mtm_plus_g_admit() -> None:
    from scripts.backtest_study.lib import era as era_mod

    assert set(era_mod.DESIGNED_REFUSAL_EXIT_CODES) <= HC.DESIGNED_REFUSAL_EXIT_CODES
    assert HC.EXIT_MTM_RECONCILE in HC.DESIGNED_REFUSAL_EXIT_CODES
    assert HC.EXIT_ADMIT in HC.DESIGNED_REFUSAL_EXIT_CODES
    assert HC.EXIT_ADMIT == 5


def test_g_blind_exits_one_and_is_not_a_designed_refusal() -> None:
    """A trigger that moves under blinded records is a DEFECT. Declaring it as
    a designed refusal would promote a broken report to `-latest.txt`."""
    assert HC.EXIT_LOOKAHEAD == 1
    assert HC.EXIT_LOOKAHEAD not in HC.DESIGNED_REFUSAL_EXIT_CODES


def test_g_mtm_exit_code_is_hedge_exposures_not_a_second_copy() -> None:
    assert HC.EXIT_MTM_RECONCILE is HE.EXIT_MTM_RECONCILE == 4


def test_the_docstring_first_line_is_a_one_line_summary() -> None:
    """`run.py list` shows the docstring's FIRST line."""
    first = HC.__doc__.splitlines()[0]
    assert first.startswith("HEDGE-CONCENTRATION")
    assert first.endswith("?")
    assert len(first) <= 120


# ── committed constants: imported where they are lib's, stated where they are
#    this registration's ─────────────────────────────────────────────────────

def test_library_constants_are_the_library_objects() -> None:
    assert HC.F_GRID is C.F_GRID == (0.25, 0.50, 1.00)
    assert HC.MIN_TRIGGER_DATES is C.MIN_TRIGGER_DATES == 25
    assert HC.FILL_GATE is HI.FILL_GATE == 0.60
    assert HC.BOOT_N is P.BOOT_N == 10000


def test_the_tau_grid_is_this_studys_own_registered_triple() -> None:
    """The registration fixes {0.45, 0.55, 0.65} — the ADMITTED book's median,
    p75 and p90 — against `hedge_exposure`'s {0.30, 0.35, 0.40} on a book more
    than twice as diversified. Sharing `C.TAU_GRID` would silently run this
    study on a trigger it did not register."""
    assert HC.TAU_GRID == (0.45, 0.55, 0.65)
    assert HC.TAU_GRID is not C.TAU_GRID
    assert HC.TAU_GRID != C.TAU_GRID


def test_the_registered_stage_one_knobs() -> None:
    assert HC.H == 20 and HC.H_SENS == 10
    assert HC.MIN_TERCILE_SESSIONS == 60
    assert HC.MIN_DENSE_EPISODES == 3
    assert HC.MIN_EPISODE_SESSIONS == 20
    assert HC.KG_MIN_SIGN == 2
    assert HC.KN_DRAWS == 1000
    assert HC.N_SEEDS == 200


def test_bonferroni_denominator_is_the_registered_nine_cells() -> None:
    assert HC.N_CELLS == len(HC.TAU_GRID) * len(HC.F_GRID) == 9
    assert HC.ALPHA == pytest.approx(0.05 / 9)


def test_the_comparison_taus_are_not_cells() -> None:
    """`hedge_exposure`'s taus are printed for continuity. Registering them as
    cells here would be the post-hoc threshold search the registration bans."""
    assert set(HC.COMPARISON_TAUS).isdisjoint(HC.TAU_GRID)


# ── the verdict vocabularies ─────────────────────────────────────────────────

def test_every_registered_verdict_word_is_declared() -> None:
    """The registration words four Stage 1 verdicts and five for Stage 2. A
    module that can only print three has silently dropped one."""
    assert set(HC.STAGE1_VERDICTS) == {
        "PRECONDITION-FOUND", "PRECONDITION-NULL", "GROSS-NOT-CONCENTRATION",
        "UNDERPOWERED"}
    assert set(HC.STAGE2_VERDICTS) == {
        "MECHANISM-FOUND", "NULL", "CONTRARY", "UNDERPOWERED",
        "NOT EVALUABLE"}


def test_measurement_only_is_not_a_verdict_word_here() -> None:
    """The registration is explicit: ARM M is reported as a MEASUREMENT in
    every run and never as a verdict."""
    assert "MEASUREMENT-ONLY" not in HC.STAGE1_VERDICTS
    assert "MEASUREMENT-ONLY" not in HC.STAGE2_VERDICTS
    # It may still appear in PROSE — the report says out loud that it is not a
    # word here — but only ever inside a sentence that denies it.
    for line in SRC.splitlines():
        if "MEASUREMENT-ONLY" in line:
            assert " not " in line or " NOT " in line, line


def test_every_ship_criteria_branch_has_a_verdict_to_attach_to() -> None:
    """The reason this registration exists: every outcome moves §2.1."""
    assert set(HC.SHIP_BRANCHES) | {"PRECONDITION-FOUND"} == set(HC.STAGE1_VERDICTS)
    assert set(HC.SHIP_BRANCHES_STAGE2) == set(HC.STAGE2_VERDICTS)


# ── stage1_verdict: the registration's mapping, exactly ─────────────────────

def _clauses(**over) -> dict:
    res = {"powered": True, **{f"c{i}": True for i in range(1, 7)}}
    res.update(over)
    return res


def test_all_six_clauses_clear_is_precondition_found() -> None:
    assert HC.stage1_verdict(_clauses()) == "PRECONDITION-FOUND"


@pytest.mark.parametrize("clause", [1, 2, 3, 5, 6])
def test_any_single_clause_failure_other_than_four_is_null(clause: int) -> None:
    assert HC.stage1_verdict(_clauses(**{f"c{clause}": False})) \
        == "PRECONDITION-NULL"


def test_clause_four_alone_is_gross_not_concentration() -> None:
    """"bigger books draw down more; the cluster structure adds nothing" is a
    real finding with its own Ship-criteria branch, not a NULL."""
    assert HC.stage1_verdict(_clauses(c4=False)) == "GROSS-NOT-CONCENTRATION"


def test_clause_four_needs_clauses_one_to_three_to_have_cleared() -> None:
    """The registration words it "clauses 1-3 clear but clause 4 fails"."""
    assert HC.stage1_verdict(_clauses(c1=False, c4=False)) == "PRECONDITION-NULL"
    assert HC.stage1_verdict(_clauses(c2=False, c4=False)) == "PRECONDITION-NULL"
    assert HC.stage1_verdict(_clauses(c3=False, c4=False)) == "PRECONDITION-NULL"


@pytest.mark.parametrize("over", [
    {}, {"c1": False}, {"c4": False},
    {f"c{i}": False for i in range(1, 7)},
])
def test_unpowered_beats_every_clause_pattern(over: dict) -> None:
    """G-POWER-K failing means NO DIRECTION IS QUOTED, whatever the clauses
    happen to say. UNDERPOWERED is not a lean and it is not a NULL."""
    assert HC.stage1_verdict(_clauses(powered=False, **over)) == "UNDERPOWERED"


def test_stage1_verdict_reads_nothing_but_powered_and_the_six_clauses() -> None:
    """Pure, so the mapping is unit-testable without a book."""
    assert HC.stage1_verdict({"powered": True, **{f"c{i}": True
                                                  for i in range(1, 7)}}) \
        == "PRECONDITION-FOUND"
    assert HC.stage1_verdict({}) == "UNDERPOWERED"


def test_every_word_stage1_can_emit_is_a_registered_word() -> None:
    seen = set()
    for powered in (True, False):
        for mask in range(64):
            res = {"powered": powered,
                   **{f"c{i}": bool(mask >> (i - 1) & 1) for i in range(1, 7)}}
            seen.add(HC.stage1_verdict(res))
    assert seen <= set(HC.STAGE1_VERDICTS)


# ── Stage 2 is not entered on a non-FOUND word ───────────────────────────────

class _Spy:
    def __init__(self) -> None:
        self.ran = 0
        self.censused = 0

    def run(self) -> str:
        self.ran += 1
        return "MECHANISM-FOUND"

    def census(self) -> None:
        self.censused += 1


def test_stage2_runs_only_on_precondition_found(capsys) -> None:
    spy = _Spy()
    assert HC.stage2_dispatch("PRECONDITION-FOUND", spy.run, spy.census) \
        == "MECHANISM-FOUND"
    assert (spy.ran, spy.censused) == (1, 0)


@pytest.mark.parametrize("word", ["PRECONDITION-NULL",
                                  "GROSS-NOT-CONCENTRATION", "UNDERPOWERED"])
def test_stage2_is_not_entered_on_any_other_word(word: str, capsys) -> None:
    """The trigger census is still printed FOR THE RECORD, and the return is
    None so there is no Stage 2 word for a later reader to quote."""
    spy = _Spy()
    assert HC.stage2_dispatch(word, spy.run, spy.census) is None
    assert (spy.ran, spy.censused) == (0, 1)
    out = capsys.readouterr().out
    assert "STAGE 2 — NOT RUN" in out and word in out


# ── the overlay ledger ───────────────────────────────────────────────────────

def _cfg(**over):
    base = dict(label="t", capital=25_000.0, per_pos_cap=0.25, net_cap=2.50,
                risk_pct=0.02, max_per_day=3)
    base.update(over)
    return A.Cfg(**base)


def _overlay(reserved=0.0, net=0.0, session=date(2025, 1, 7), **cfg_over):
    return HC.Overlay(25_000.0,
                      {session: {"reserved": reserved, "net": net,
                                 "gross": abs(net), "n": 1}},
                      _cfg(**cfg_over))


def test_overlay_cash_is_capital_less_the_signal_books_reserve() -> None:
    ov = _overlay(reserved=4_000.0, net=10_000.0)
    cash, net_open = ov.state(date(2025, 1, 7))
    assert cash == pytest.approx(21_000.0)
    assert net_open == pytest.approx(10_000.0)


def test_an_open_hedge_leg_consumes_cash_and_net_delta() -> None:
    ov = _overlay(reserved=4_000.0, net=10_000.0)
    ok, why = ov.admit(date(2025, 1, 7), date(2025, 1, 9), 500.0, -3_000.0)
    assert ok and why is None
    cash, net_open = ov.state(date(2025, 1, 8))
    assert cash == pytest.approx(25_000.0 - 500.0)   # no signal book on the 8th
    assert net_open == pytest.approx(-3_000.0)


def test_a_leg_is_off_the_ledger_after_its_last_session() -> None:
    ov = _overlay()
    ov.admit(date(2025, 1, 7), date(2025, 1, 8), 500.0, -3_000.0)
    assert ov.state(date(2025, 1, 9)) == (25_000.0, 0.0)


def test_a_refused_admission_is_counted_by_its_binding_constraint() -> None:
    """A hedge the account could not carry must be SKIPPED and counted, never
    carried for free."""
    ov = _overlay(reserved=0.0, net=0.0)
    ok, why = ov.admit(date(2025, 1, 7), date(2025, 1, 7), 100.0, -9_000.0)
    assert not ok and why == "per_pos_delta"
    assert ov.refused == {"per_pos_delta": 1} and ov.admitted == 0
    assert ov.legs == []


def test_a_refused_leg_never_reaches_the_ledger() -> None:
    ov = _overlay()
    ov.admit(date(2025, 1, 7), date(2025, 1, 7), 30_000.0, 0.0)
    assert ov.refused == {"cash": 1}
    assert ov.state(date(2025, 1, 7)) == (25_000.0, 0.0)


def test_the_net_cap_binds_against_the_signal_books_own_net() -> None:
    """The signal book is HELD FIXED, so a hedge is admitted against the net
    delta that book already carries — not against an empty account."""
    ov = _overlay(net=62_000.0)          # 2.48x equity, just inside the cap
    ok, why = ov.admit(date(2025, 1, 7), date(2025, 1, 7), 100.0, 3_000.0)
    assert not ok and why == "net_delta"


def test_a_hedge_that_reduces_net_delta_is_admitted_where_one_that_adds_is_not():
    ov = _overlay(net=62_000.0)
    assert ov.admit(date(2025, 1, 7), date(2025, 1, 7), 100.0, -3_000.0)[0]


# ── sizing: SKIP, never floor ───────────────────────────────────────────────

def test_a_sub_one_contract_hedge_is_skipped_not_floored_to_one() -> None:
    """`account_sim` ARM H's convention, which the registration names. The
    planner is `hedge_exposure`'s, imported rather than copied, so the two
    studies cannot come to size a hedge differently."""
    assert HC.plan_episode_admitted.__module__ == HC.__name__
    assert HE._contracts_for(500.0, 0.25, 500.0) == 0     # int(0.25 x 1)
    assert HE._contracts_for(500.0, 1.00, 500.0) == 1


def test_the_planner_skips_a_sub_one_contract_session_without_admitting_it(
        monkeypatch) -> None:
    """A skip must happen BEFORE the ledger is touched: a hedge that was never
    placed must not consume headroom a later session could have used."""
    session = date(2025, 1, 7)
    pick = HI.PutPick(ticker="QQQ", session=session, expiry=date(2025, 2, 21),
                      strike=500.0, rule=HI.RULE_BAND, entry_mark=5.0,
                      spot=500.0)
    monkeypatch.setattr(HI, "select_put", lambda t, d, r: pick)
    monkeypatch.setattr(HI, "entry_delta", lambda p, c: -10.0 * c)
    ov = _overlay(session=session)
    diag = HC.new_diag()
    leg = HC.plan_episode_admitted([session, date(2025, 1, 8)],
                                   ["QQQ", HE.CARRY], 0.25, 500.0,
                                   HI.RULE_BAND, diag, ov)
    assert diag["sessions_sub_one"] == 1
    assert leg.segments == [] and leg.cost == 0.0
    assert ov.admitted == 0 and ov.refused == {}


def test_the_planner_counts_a_refused_admission_and_places_nothing(
        monkeypatch) -> None:
    session = date(2025, 1, 7)
    pick = HI.PutPick(ticker="QQQ", session=session, expiry=date(2025, 2, 21),
                      strike=500.0, rule=HI.RULE_BAND, entry_mark=5.0,
                      spot=500.0)
    monkeypatch.setattr(HI, "select_put", lambda t, d, r: pick)
    monkeypatch.setattr(HI, "entry_delta", lambda p, c: -10.0 * c)
    ov = _overlay(session=session, per_pos_cap=0.0001)
    diag = HC.new_diag()
    leg = HC.plan_episode_admitted([session, date(2025, 1, 8)],
                                   ["QQQ", HE.CARRY], 1.00, 500.0,
                                   HI.RULE_BAND, diag, ov)
    assert diag["admission_refused"] == 1
    assert ov.refused == {"per_pos_delta": 1}
    assert leg.segments == []


def test_a_put_with_no_cached_entry_greek_is_never_admitted_at_zero_delta(
        monkeypatch) -> None:
    """A missing greek is None, never 0.0. Admitting at a fabricated 0.0 would
    consume no net-delta headroom for a position that carries some."""
    session = date(2025, 1, 7)
    pick = HI.PutPick(ticker="QQQ", session=session, expiry=date(2025, 2, 21),
                      strike=500.0, rule=HI.RULE_BAND, entry_mark=5.0,
                      spot=500.0)
    monkeypatch.setattr(HI, "select_put", lambda t, d, r: pick)
    monkeypatch.setattr(HI, "entry_delta", lambda p, c: None)
    ov = _overlay(session=session)
    diag = HC.new_diag()
    leg = HC.plan_episode_admitted([session, date(2025, 1, 8)],
                                   ["QQQ", HE.CARRY], 1.00, 500.0,
                                   HI.RULE_BAND, diag, ov)
    assert diag["no_entry_delta"] == 1
    assert leg.segments == [] and ov.admitted == 0


def test_an_admitted_leg_reaches_the_ledger_and_the_segment(monkeypatch) -> None:
    session = date(2025, 1, 7)
    pick = HI.PutPick(ticker="QQQ", session=session, expiry=date(2025, 2, 21),
                      strike=500.0, rule=HI.RULE_BAND, entry_mark=5.0,
                      spot=500.0)
    monkeypatch.setattr(HI, "select_put", lambda t, d, r: pick)
    monkeypatch.setattr(HI, "entry_delta", lambda p, c: -10.0 * c)
    ov = _overlay(session=session)
    diag = HC.new_diag()
    leg = HC.plan_episode_admitted([session, date(2025, 1, 8)],
                                   ["QQQ", HE.CARRY], 1.00, 500.0,
                                   HI.RULE_BAND, diag, ov)
    assert diag["opens"] == 1 and ov.admitted == 1
    assert len(leg.segments) == 1
    assert leg.cost == pytest.approx(HI.entry_cost(pick, 1))
    assert ov.legs[0].dn == pytest.approx(-10.0 * 1 * 500.0)


def test_a_legs_ledger_span_stops_at_the_expiry(monkeypatch) -> None:
    session = date(2025, 1, 7)
    pick = HI.PutPick(ticker="QQQ", session=session, expiry=date(2025, 1, 8),
                      strike=500.0, rule=HI.RULE_BAND, entry_mark=5.0,
                      spot=500.0)
    monkeypatch.setattr(HI, "select_put", lambda t, d, r: pick)
    monkeypatch.setattr(HI, "entry_delta", lambda p, c: -10.0 * c)
    ov = _overlay(session=session)
    HC.plan_episode_admitted([session, date(2025, 1, 8), date(2025, 1, 9)],
                             ["QQQ", "QQQ", HE.CARRY], 1.00, 500.0,
                             HI.RULE_BAND, HC.new_diag(), ov)
    assert ov.legs[0].last == date(2025, 1, 8)


# ── G-ADMIT ──────────────────────────────────────────────────────────────────

class _FakePos:
    def __init__(self, sig) -> None:
        self.rec = {"date": sig[0], "ticker": sig[1], "structure": sig[2]}
        self.contracts = sig[3]
        self.R = sig[4]
        self.dollars = sig[5]
        self.exit_reason = sig[6]
        self.hedge = False


class _FakeSim:
    def __init__(self, sigs) -> None:
        self.taken = [_FakePos(s) for s in sigs]


_SIG_A = ("2025-01-06", "NVDA", "bull_call", 2, 1.0, 500.0, "target")
_SIG_B = ("2025-01-06", "NVDA", "bull_call", 3, 1.0, 750.0, "target")


def test_gate_admit_passes_when_the_two_signatures_agree(monkeypatch) -> None:
    sim = _FakeSim([_SIG_A])
    monkeypatch.setattr(HC, "simulate_admitted",
                        lambda recs, st, label: ([], _FakeSim([_SIG_A])))
    assert HC.gate_admit(sim, [], object(), "t") == 0


def test_gate_admit_refuses_with_exit_five_on_a_signature_mismatch(
        monkeypatch, capsys) -> None:
    """A drifted local admission is a finding ABOUT THE DRIFT: the run refuses
    rather than reporting a concentration series on a book nobody held."""
    sim = _FakeSim([_SIG_B])
    monkeypatch.setattr(HC, "simulate_admitted",
                        lambda recs, st, label: ([], _FakeSim([_SIG_A])))
    assert HC.gate_admit(sim, [], object(), "t") == HC.EXIT_ADMIT
    out = capsys.readouterr().out
    assert "DIVERGED" in out and "FIRST DIVERGENCE" in out


def test_gate_admit_refuses_on_a_different_book_size(monkeypatch) -> None:
    monkeypatch.setattr(HC, "simulate_admitted",
                        lambda recs, st, label: ([], _FakeSim([_SIG_A, _SIG_B])))
    assert HC.gate_admit(_FakeSim([_SIG_A]), [], object(), "t") == HC.EXIT_ADMIT


def test_admitted_positions_never_include_an_arm_h_sleeve_position() -> None:
    class _P:
        def __init__(self, hedge):
            self.hedge = hedge

    sim = _FakeSim([])
    sim.taken = [_P(False), _P(True), _P(False)]
    assert len(HC.admitted_positions(sim)) == 2


# ── G-MTM's target ───────────────────────────────────────────────────────────

def _book_curves_targets() -> list[str]:
    """Every `target=` keyword `M.book_curves` is called with in the module."""
    out = []
    for node in ast.walk(TREE):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "book_curves"):
            continue
        for kw in node.keywords:
            if kw.arg == "target" and isinstance(kw.value, ast.Attribute):
                out.append(kw.value.attr)
    return out


def test_the_gate_calls_book_curves_with_the_position_target() -> None:
    """The sim RE-SIZES and RE-EXITS what it admits, so the row's stored
    column describes a different position: the stored target would refuse a
    correct book. Both targets are computed — the gate on TARGET_POSITION, the
    stored one beside it as a disclosure — and `target=` is always explicit."""
    targets = _book_curves_targets()
    assert "TARGET_POSITION" in targets
    assert "TARGET_STORED" in targets
    assert len(targets) == 2, "every book_curves call must name its target"


def test_the_two_targets_are_the_library_ones() -> None:
    assert M.TARGET_POSITION in M.TARGETS and M.TARGET_STORED in M.TARGETS
    assert M.TARGET_POSITION != M.TARGET_STORED


# ── the Stage 1 statistics come from lib/, not from a second copy ───────────

def test_stage_one_statistics_are_the_library_functions() -> None:
    """`lib/forward_drawdown.py` was written and tested for this study; a
    reimplementation here is how two answers to one question appear."""
    for name in ("forward_drawdown", "rank_groups", "group_counts",
                 "tercile_contrast", "spearman", "within_group_stats",
                 "sign_kept", "block_bootstrap", "circular_shift_null"):
        assert hasattr(F, name)
        assert f"def {name}(" not in SRC, f"{name} is reimplemented locally"


def test_the_block_is_the_horizon() -> None:
    """Neighbouring y's share up to H-1 of their forward window, so a
    row-level resample would understate the variance."""
    al = _aligned(n=120)
    res = HC.run_arm_k(al, HC.H, HC.H, n_boot := 5, seed=1)
    assert res["block"] == HC.H == 20
    assert res["boot_contrast"].block == 20
    assert res["boot_contrast"].n_boot == n_boot


def test_arm_kn_shifts_by_at_least_the_horizon() -> None:
    al = _aligned(n=120)
    kn = HC.run_arm_kn(al, HC.H, draws=25, seed=1)
    assert kn["contrast"].min_shift == HC.H
    assert kn["rho"].min_shift == HC.H


def test_arm_kn_reports_rather_than_crashes_on_too_few_rows() -> None:
    al = _aligned(n=10)
    kn = HC.run_arm_kn(al, HC.H, draws=25, seed=1)
    assert kn["contrast"] is None and "contrast_error" in kn


def _aligned(n: int = 120) -> HC.Aligned:
    sessions = [date(2024, 1, 1) + timedelta(days=i) for i in range(n)]
    x = [(i % 7) / 7.0 for i in range(n)]
    y = [None if i >= n - HC.H else -float(i % 5) for i in range(n)]
    return HC.Aligned(sessions=sessions, idx=list(range(n)), x=x, y=y,
                      gross=[1.0 + (i % 3) for i in range(n)], n_axis=n,
                      n_axis_unmatched=0, n_series_off_axis=0, n_no_gross=0)


def test_alignment_computes_y_on_the_whole_axis_before_dropping_rows() -> None:
    """A row with no concentration reading is dropped from ARM K's ROWS but
    stays inside every forward window it falls in — otherwise a market holiday
    inside a position's grid would shorten the horizon."""
    axis = [date(2024, 1, 1) + timedelta(days=i) for i in range(60)]
    levels = [float(i) for i in range(60)]
    levels[30] = -100.0                       # the trough, on a dropped row

    class _SC:
        def __init__(self, s, c):
            self.session, self.concentration = s, c

    series = [_SC(s, 0.5) for i, s in enumerate(axis) if i != 30]
    ss = {s: {"gross": 1000.0} for s in axis}
    al = HC.align(axis, levels, series, ss, 25_000.0, 5)
    assert al.n_axis_unmatched == 1 and al.n_series_off_axis == 0
    assert len(al.x) == 59
    # the session 5 rows before the trough still SEES the trough in its window
    i = al.sessions.index(axis[26])
    assert al.y[i] == pytest.approx(-100.0 - 26.0)


def test_alignment_counts_series_sessions_that_are_not_on_the_axis() -> None:
    axis = [date(2024, 1, 1) + timedelta(days=i) for i in range(10)]

    class _SC:
        def __init__(self, s, c):
            self.session, self.concentration = s, c

    series = [_SC(s, 0.5) for s in axis] + [_SC(date(2030, 1, 1), 0.5)]
    ss = {s: {"gross": 1.0} for s in axis}
    al = HC.align(axis, levels := [0.0] * 10, series, ss, 25_000.0, 2)
    assert al.n_series_off_axis == 1
    assert len(levels) == 10


def test_the_ex_window_cuts_are_the_protocols_two() -> None:
    al = _aligned(n=120)
    assert set(HC.run_window_cuts(al, -1.0)) == set(P.DOMINANT_WINDOWS)


def test_a_dense_episode_below_the_session_floor_carries_no_sign() -> None:
    al = _aligned(n=120)
    spans = [(al.sessions[0], al.sessions[5], 3),        # 6 sessions
             (al.sessions[0], al.sessions[60], 20)]      # 61 sessions
    signs = HC.run_episode_signs(al, spans, -1.0)
    assert signs[0]["counted"] is False
    assert signs[1]["counted"] is True


# ── the standing research-tier bans ─────────────────────────────────────────

BANNED = ("sharpe", "annualis", "annualiz", "timetorecover", "time_to_recover")


def test_no_banned_statistic_is_computed_anywhere() -> None:
    """Standing research-tier ban: no annualised figure, no Sharpe, no
    time-to-recover. Checked on IDENTIFIERS rather than raw text, because the
    report says the ban out loud in prose and must be allowed to."""
    names: set[str] = set()
    for node in ast.walk(TREE):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    offenders = sorted(n for n in names
                       if any(b in n.lower() for b in BANNED))
    assert not offenders, f"banned statistic named in code: {offenders}"


def test_the_only_path_statistics_are_the_ones_mtm_curve_defines() -> None:
    assert set(M.PathStats.__dataclass_fields__) == {
        "basis", "n_sessions", "total", "max_dd", "ulcer", "tuw",
        "worst_session"}


def test_no_population_count_is_hardcoded_in_the_module() -> None:
    """"No stored expected figure" is a standing rule: a stored 221 or 498
    fingerprints one export, and the book grows on every legitimate refresh.
    Every count in the report is computed at run time."""
    for token in ("996", "145", "458", "221", "498", "110", "308"):
        assert token not in SRC, f"hardcoded population figure {token!r}"


def test_the_module_does_no_work_at_import_time() -> None:
    """`run.py::discover` and `_refusal_codes` parse study modules with `ast`
    and never import them, but the test suite DOES import this one."""
    top = [n for n in TREE.body
           if not isinstance(n, (ast.Import, ast.ImportFrom, ast.Assign,
                                 ast.AnnAssign, ast.FunctionDef, ast.ClassDef,
                                 ast.Expr, ast.If))]
    assert not top, f"module-level statements that do work: {top}"
