"""`f2_management/exit_drawdown.py` — the two claims the registration makes about
the MACHINERY rather than about exits, pinned as code properties.

The study's numbers are a data claim and belong in `research/`; what belongs
here is the pair of properties a report cannot demonstrate about itself:

  1. **The walk-forward stitching uses only TRAIN dates.** Every position's
     configuration must come from a block whose train set ends at least the
     embargo before that position's own signal date, and the burn-in dates —
     the ones that exist only to train the first fit — must be EXCLUDED from
     the evaluated population and counted, never silently folded in under the
     shipped profile. A synthetic date list makes that checkable without the
     book.

  2. **The verdict grammar has no hole.** The registration calls it TOTAL:
     "applied in the order below, first match wins, so every combination of
     gate outcomes maps to exactly one token". So enumerate every gate vector
     and assert exactly that — one token, from the registered vocabulary,
     with `REACTIVE-AGAIN` never emitted for the SIZING arm (a rule that moves
     no exit cannot re-find the reactive null) and `NULL` as the catch-all
     that makes the ladder total.

Everything else the module does (the overlays, the memo key, the composition)
is `lib/exit_overlays.py`'s and is pinned in `tests/test_exit_overlays.py`.
"""
from __future__ import annotations

import itertools
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f2_management import exit_drawdown as S  # noqa: E402


# ── a synthetic date list ────────────────────────────────────────────────────
#
# Weekly signal dates over three years: dense enough that the expanding train
# set clears `WF_MIN_TRAIN_DATES` and long enough that the 120-day embargo
# leaves real blocks. Deliberately NOT the book — the property under test is
# geometric, and reading it off whatever the exports happen to hold would make
# the test a data claim.

def _weekly_dates(n: int, start=date(2023, 1, 2)) -> list[str]:
    return [(start + timedelta(days=7 * i)).isoformat() for i in range(n)]


DATES = _weekly_dates(160)


# ════════════════════════════════════════════════════════════════════════════
# 1. The stitching uses only train dates
# ════════════════════════════════════════════════════════════════════════════

def test_the_split_geometry_is_non_degenerate():
    """The fixture must actually produce blocks, or every claim below is vacuous."""
    splits = S.build_splits(DATES)
    assert splits, "the synthetic date list produced no walk-forward block"
    assert all(s.train and s.test for s in splits)


def test_every_block_trains_at_least_the_embargo_before_it_tests():
    """The purge, restated on the study's own splitter.

    `walk_forward_splits` owns the rule; this asserts `exit_drawdown` reads it
    unchanged, because the whole no-lookahead claim rests on the gap being the
    PATH CAP and not something smaller.
    """
    splits = S.build_splits(DATES)
    for s in splits:
        gap = (date.fromisoformat(s.test[0]) - date.fromisoformat(s.train[-1])).days
        assert gap >= S.WF_EMBARGO_DAYS, (
            f"block {s.idx}: train ends {s.train[-1]}, test starts {s.test[0]}, "
            f"gap {gap}d < embargo {S.WF_EMBARGO_DAYS}d")
    assert S.embargo_ok(splits)


def test_every_position_takes_its_config_from_a_block_that_predates_it():
    """THE stitching property: a date is dispatched to the block whose TRAIN
    set predates it by at least the embargo — never to a block fitted on its
    own date, and never to one fitted on dates after it."""
    splits = S.build_splits(DATES)
    index = S.block_index(splits)
    by_idx = {s.idx: s for s in splits}
    block_of = S.map_block(index)

    for d in DATES:
        idx = block_of(date.fromisoformat(d))
        if idx is None:
            continue                      # burn-in — checked separately below
        s = by_idx[idx]
        assert d in s.test
        assert d not in s.train, f"{d} was fitted on its own date"
        assert max(s.train) < d, f"{d} took a config fitted on a LATER date"
        gap = (date.fromisoformat(d) - date.fromisoformat(s.train[-1])).days
        assert gap >= S.WF_EMBARGO_DAYS


def test_a_date_belongs_to_exactly_one_block():
    splits = S.build_splits(DATES)
    seen = [d for s in splits for d in s.test]
    assert len(seen) == len(set(seen))


def test_train_sets_expand_and_never_reach_forward():
    """Expanding, not rolling: each block's train set contains the previous
    block's, and no train date is on or after that block's first test date."""
    splits = S.build_splits(DATES)
    for prev, cur in zip(splits, splits[1:]):
        assert set(prev.train) <= set(cur.train)
    for s in splits:
        assert all(d < s.test[0] for d in s.train)


def test_burn_in_is_exactly_the_untested_dates_and_is_counted():
    """Burn-in is EXCLUDED and REPORTED, never silently shipped-profile.

    The registration: "The OOS population is exactly the union of the blocks'
    TEST dates." So the burn-in census and the evaluated population must
    PARTITION the population — no date in both, none in neither.
    """
    splits = S.build_splits(DATES)
    index = S.block_index(splits)
    burn = S.burn_in_dates(DATES, splits)

    assert burn, "the fixture must exercise a non-empty burn-in"
    assert set(burn).isdisjoint(set(index))
    assert set(burn) | set(index) == set(DATES)
    assert burn == sorted(burn)
    # It is a PREFIX of the window: the dates that exist only to train the
    # first fit are the earliest ones.
    assert burn == sorted(DATES)[:len(burn)]


def test_the_burn_in_is_never_dispatched_to_a_configuration():
    """`make_blockwise_replayer` is given no default, so an unmapped date is a
    loud KeyError rather than a silent shipped-profile replay. The map itself
    must therefore return None for every burn-in date."""
    splits = S.build_splits(DATES)
    block_of = S.map_block(S.block_index(splits))
    for d in S.burn_in_dates(DATES, splits):
        assert block_of(date.fromisoformat(d)) is None


def test_one_block_dispatches_everything_to_the_same_fit():
    """The TRAIN fit and the in-sample disclosure both run a single
    configuration over a whole window; `one_block` is that map and must never
    return None (which would make the replayer raise)."""
    block_of = S.one_block(7)
    assert all(block_of(date.fromisoformat(d)) == 7 for d in DATES)


def test_a_thin_date_list_produces_no_test_block_at_all():
    """Fewer dates than the minimum train set can support is a legitimate
    outcome — the study reports zero OOS dates rather than inventing a block."""
    splits = S.build_splits(_weekly_dates(10))
    assert splits == []
    assert S.burn_in_dates(_weekly_dates(10), splits) == _weekly_dates(10)


# ════════════════════════════════════════════════════════════════════════════
# 2. The verdict grammar is total
# ════════════════════════════════════════════════════════════════════════════

_FLAGS = ("powered", "dates_ok", "dd_contrary", "r_contrary", "dd_ok", "r_ok",
          "stab_ok", "cont_ok")


def _vectors():
    for bits in itertools.product((False, True), repeat=len(_FLAGS)):
        yield dict(zip(_FLAGS, bits))


def test_every_gate_vector_maps_to_exactly_one_registered_token():
    """TOTALITY. Both arm kinds, all 256 gate vectors, no hole and no escape."""
    for sizing in (False, True):
        for vec in _vectors():
            token = S.verdict_token(sizing=sizing, **vec)
            assert token in S.TOKENS, f"{vec} sizing={sizing} -> {token!r}"


def test_a_sizing_arm_never_emits_reactive_again():
    """CONT is DROPPED from ARM D's conjunction: a sizing rule moves no exit,
    so `the arm's exits` has no referent and its continuation rate would be the
    baseline's by construction. V3 is skipped for it, and V5 stays the
    catch-all so the grammar is still total."""
    for vec in _vectors():
        assert S.verdict_token(sizing=True, **vec) != S.V_REACTIVE


def test_a_sizing_arms_verdict_ignores_cont_entirely():
    """The same gate vector with CONT flipped must give a sizing arm the same
    token — otherwise clause 7 is still binding on it through a side door."""
    for vec in _vectors():
        a = dict(vec, cont_ok=True)
        b = dict(vec, cont_ok=False)
        assert S.verdict_token(sizing=True, **a) == S.verdict_token(sizing=True, **b)


def test_power_wins_over_everything_else():
    """(V1) is first: an underpowered cell is UNDERPOWERED whatever else says.
    Both floors reach it — G0's own check and clause 6, its restatement."""
    for sizing in (False, True):
        for powered, dates_ok in ((False, False), (False, True), (True, False)):
            token = S.verdict_token(
                powered=powered, dates_ok=dates_ok, dd_contrary=True,
                r_contrary=True, dd_ok=True, r_ok=True, stab_ok=True,
                cont_ok=True, sizing=sizing)
            assert token == S.V_UNDERPOWERED


def test_contrary_precedes_reactive_and_candidate():
    """(V2) before (V3) and (V4): a harmful cell is a finding, not a candidate."""
    for dd_c, r_c in ((True, False), (False, True), (True, True)):
        assert S.verdict_token(
            powered=True, dates_ok=True, dd_contrary=dd_c, r_contrary=r_c,
            dd_ok=True, r_ok=True, stab_ok=True, cont_ok=True) == S.V_CONTRARY


def test_reactive_again_needs_r_to_have_cleared():
    """(V3) is reserved for a cell whose R clause CLEARED and whose CONT
    failed. A cell that fails CONT with R already failed is NULL — the
    registration says so explicitly, and the distinction is the whole point of
    registering CONT as a criterion rather than a footnote."""
    base = dict(powered=True, dates_ok=True, dd_contrary=False,
                r_contrary=False, dd_ok=True, stab_ok=True, cont_ok=False)
    assert S.verdict_token(r_ok=True, **base) == S.V_REACTIVE
    assert S.verdict_token(r_ok=False, **base) == S.V_NULL


def test_candidate_needs_the_whole_conjunction():
    """Failing any one clause is failing."""
    full = dict(powered=True, dates_ok=True, dd_contrary=False,
                r_contrary=False, dd_ok=True, r_ok=True, stab_ok=True,
                cont_ok=True)
    assert S.verdict_token(**full) == S.V_CANDIDATE
    for clause in ("dd_ok", "stab_ok"):
        assert S.verdict_token(**dict(full, **{clause: False})) == S.V_NULL
    # r_ok False with CONT passing is NULL, not CONTRARY (which needs a CI).
    assert S.verdict_token(**dict(full, r_ok=False)) == S.V_NULL
    # cont_ok False with r_ok True is REACTIVE-AGAIN, not NULL.
    assert S.verdict_token(**dict(full, cont_ok=False)) == S.V_REACTIVE


def test_a_sizing_arm_can_reach_candidate_on_clauses_one_to_six():
    """ARM D's conjunction is 1-6, and it takes V4 with the SECONDARY prefix
    applied by the caller. The bare ladder returns the unprefixed token."""
    full = dict(powered=True, dates_ok=True, dd_contrary=False,
                r_contrary=False, dd_ok=True, r_ok=True, stab_ok=True,
                cont_ok=False, sizing=True)
    assert S.verdict_token(**full) == S.V_CANDIDATE


def test_every_registered_token_is_reachable():
    """A ladder with an unreachable rung is a grammar with a dead branch."""
    seen = {S.verdict_token(sizing=s, **v) for s in (False, True) for v in _vectors()}
    assert seen == set(S.TOKENS)


def test_prod_robust_is_total_and_only_claimed_on_an_evaluated_null():
    """ARM W's arm-level token. PROD-ROBUST is the AFFIRMATIVE reading of a
    null; an UNDERPOWERED cell does not claim it."""
    assert S.prod_robust_token(S.V_NULL) == S.T_PROD_ROBUST
    assert S.prod_robust_token(S.V_CONTRARY) == S.T_PROD_ROBUST
    assert S.prod_robust_token(S.V_UNDERPOWERED) == S.V_UNDERPOWERED
    assert S.prod_robust_token(S.V_REACTIVE) == S.V_REACTIVE
    assert S.prod_robust_token(S.V_CANDIDATE) == S.V_CANDIDATE
    for token in S.TOKENS:
        assert S.prod_robust_token(token) in set(S.TOKENS) | {S.T_PROD_ROBUST}


# ════════════════════════════════════════════════════════════════════════════
# The frozen grids and the registered constants
# ════════════════════════════════════════════════════════════════════════════

def test_the_grids_are_the_registered_ones():
    """"The grids above are FINAL." A silent widening is the anti-tuning
    failure the registration names, so pin the shapes."""
    assert S.ARM_W_PT == (0.60, 0.75, 0.90, 1.10)
    assert S.ARM_W_SL == (0.50, 0.75, None)
    assert S.ARM_W_TEF == (0.60, 0.75, None)
    assert len(S.arm_w_grid()) == 36
    assert S.PROD_POINT in S.arm_w_grid()
    assert S.ARM_U_K == (1.5, 2.0, 3.0)
    assert S.ARM_O_X == (0.25, 0.40)
    assert S.ARM_D_D == (0.05, 0.10)


def test_the_gate_constants_are_the_registered_ones():
    assert (S.MIN_AFFECTED_DATES, S.MIN_AFFECTED_ROWS) == (25, 60)
    assert S.DD_IMPROVE_MIN == 0.15
    assert S.DR_NONINFERIORITY == -0.02
    assert S.CONT_MAJORITY == 0.50
    assert S.TRAIN_R_TOLERANCE == 0.02
    assert (S.WF_BLOCK, S.WF_EMBARGO_DAYS, S.WF_MIN_TRAIN_DATES) == (15, 120, 40)
    assert S.OI_BLANK_EXCLUSION == 0.20


def test_designed_refusal_codes_are_a_plain_set_literal():
    """`run.py` finds them by AST parse; a `frozenset(...)` call is invisible
    to `ast.literal_eval` and the era refusal would be misfiled as a failure."""
    import ast
    src = Path(S.__file__).read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "DESIGNED_REFUSAL_EXIT_CODES"
                for t in node.targets):
            assert ast.literal_eval(node.value) == {2, 3}
            break
    else:
        pytest.fail("no module-level DESIGNED_REFUSAL_EXIT_CODES assignment")


# ════════════════════════════════════════════════════════════════════════════
# Variants and ARM P's split
# ════════════════════════════════════════════════════════════════════════════

def test_arms_flag_selects_variants_and_nothing_else():
    assert [v.arm for v in S.variants_for("W")] == ["W", "W"]
    assert {v.arm for v in S.variants_for(S.ALL_ARMS)} == set("WUOPD")
    assert S.variants_for("") == []


def test_only_arm_w_has_a_prod_tie_point():
    """Tie order step (i) is live for ARM W and INERT for every other arm —
    only ARM W's grid contains a PROD point to tie back to."""
    for v in S.variants_for(S.ALL_ARMS):
        fires = [c for c in v.grid if v.is_prod(c)]
        assert (v.arm == "W") or not fires


def test_partial_split_is_ceil_then_floor_and_refuses_a_single_contract():
    """The registration fixes the odd-count rule; it is not a build choice."""
    assert S.partial_split(4) == (2, 2)
    assert S.partial_split(5) == (3, 2)
    assert S.partial_split(7) == (4, 3)
    top, bottom = S.partial_split(1)
    assert bottom == 0          # not a position — the caller EXCLUDES the row
    assert top == 1


def test_arm_p_and_the_volume_variant_have_nothing_to_select():
    for v in S.variants_for("PO"):
        if v.key in ("half", "vol"):
            assert len(v.grid) == 1


def test_largest_param_tolerates_a_parameterless_config():
    """Tie order step (iv) must not raise on ARM P / the volume variant, whose
    configurations carry no parameter at all."""
    for v in S.variants_for(S.ALL_ARMS):
        for c in v.grid:
            assert isinstance(v.largest_param(c), float)
            assert isinstance(v.n_active_rules(c), int)
            assert isinstance(v.config_label(c), str)


# ════════════════════════════════════════════════════════════════════════════
# The G1 shift, and the improvement sign
# ════════════════════════════════════════════════════════════════════════════

class _Grid:
    """The only thing `shift_on_grid` reads off a trade."""

    def __init__(self, grid):
        self.grid = list(grid)


GRID = [date(2026, 1, d) for d in (5, 6, 7, 8, 9)]


def test_shift_on_grid_moves_a_series_one_grid_session_later():
    t = _Grid(GRID)
    series = {k: float(i) for i, k in enumerate(GRID)}
    got = S.shift_on_grid(t, series)
    assert GRID[0] not in got            # session 1 has no predecessor
    assert [got[k] for k in GRID[1:]] == [0.0, 1.0, 2.0, 3.0]


def test_shift_on_grid_keeps_missing_missing_and_never_zero():
    """A grid session whose predecessor had no value has no value — the whole
    "missing is missing" contract, restated on the gate's own shift."""
    t = _Grid(GRID)
    series = {GRID[0]: 10.0, GRID[2]: 20.0}      # GRID[1] absent from the file
    got = S.shift_on_grid(t, series)
    assert got[GRID[1]] == 10.0
    assert GRID[2] not in got                     # its predecessor had nothing
    assert got[GRID[3]] == 20.0
    assert all(v is not None for v in got.values())


def test_shift_on_grid_ignores_dates_the_grid_never_reads():
    """THE reason the shift is on the grid and not on the file's key order: an
    option-history file carries dates the position never reads, and pulling one
    of those onto a grid session is not "one session later"."""
    t = _Grid(GRID)
    off = date(2026, 1, 4)                        # before the grid starts
    series = {off: 999.0, GRID[0]: 1.0, GRID[1]: 2.0}
    got = S.shift_on_grid(t, series)
    assert got[off] == 999.0                      # carried verbatim, unread
    assert GRID[0] not in got                     # NOT fed from the off-grid day
    assert got[GRID[1]] == 1.0
    assert got[GRID[2]] == 2.0


def test_shift_on_grid_holds_the_pre_entry_window_fixed():
    """ARM U's ATR14 is a SCALAR frozen at entry off bars <= entry. Shifting
    that window would move the THRESHOLD instead of the information set, and
    the gate would measure an ATR re-estimate rather than a leak. Holding it
    also keeps entry_day()'s anchor, so the two runs stay comparable."""
    t = _Grid(GRID)
    series = {k: float(i) for i, k in enumerate(GRID)}
    got = S.shift_on_grid(t, series, after=GRID[1])
    assert got[GRID[0]] == 0.0 and got[GRID[1]] == 1.0       # untouched
    assert got[GRID[2]] == 1.0 and got[GRID[3]] == 2.0       # shifted
    # The held region still FEEDS the shifted one at the boundary.
    assert got[GRID[4]] == 3.0


def test_the_volume_probe_is_the_spike_leg_and_only_the_spike_leg():
    """`vol_spike_session` is a GATE probe, never an exit. It must fire on the
    expanding-median spike alone, ignoring the mark leg the rule also needs."""
    t = _Grid(GRID)
    vol = {GRID[0]: 100.0, GRID[1]: 100.0, GRID[2]: 1000.0, GRID[3]: 100.0,
           GRID[4]: 100.0}
    assert S.vol_spike_session(t, vol) == 3
    assert S.vol_spike_session(t, {k: 100.0 for k in GRID}) is None


def test_the_volume_probe_skips_missing_sessions_like_the_rule_does():
    t = _Grid(GRID)
    # GRID[2] is absent from the file — skipped, never read as zero volume.
    vol = {GRID[0]: 100.0, GRID[1]: 100.0, GRID[3]: 1000.0}
    assert S.vol_spike_session(t, vol) == 4
    assert S.vol_spike_session(t, {}) is None


def test_dd_improvement_is_positive_when_the_drawdown_shrinks():
    """Signed through `hedge_exposure.improvement`, so the two studies cannot
    drift on what "improved" means: max_dd is <= 0 and less negative wins."""
    import scripts.backtest_study.lib.mtm_curve as M

    def stats(dd):
        return M.PathStats(basis=M.MTM, n_sessions=10, total=0.0, max_dd=dd,
                           ulcer=0.0, tuw=0.0, worst_session=dd)

    gain, ratio = S.dd_improvement(stats(-1000.0), stats(-750.0))
    assert gain == pytest.approx(250.0)
    assert ratio == pytest.approx(0.25)
    gain, ratio = S.dd_improvement(stats(-1000.0), stats(-1200.0))
    assert gain == pytest.approx(-200.0)
    assert ratio == pytest.approx(-0.20)


def test_dd_improvement_ratio_is_nan_against_a_flat_baseline():
    """No percentage of zero. A zero-baseline cell fails clause 1 on the CI,
    never on a fabricated ratio."""
    import scripts.backtest_study.lib.mtm_curve as M
    flat = M.PathStats(basis=M.MTM, n_sessions=3, total=0.0, max_dd=0.0,
                       ulcer=0.0, tuw=0.0, worst_session=0.0)
    _gain, ratio = S.dd_improvement(flat, flat)
    assert ratio != ratio


def test_a_nan_ratio_can_never_clear_or_contradict_clause_one():
    """The comparison operators must be written so `NaN` fails BOTH the
    improvement and the CONTRARY mirror — a silent `NaN >= 0.15` would be
    False, but `NaN <= -0.15` must be False too."""
    nan = float("nan")
    assert not (nan >= S.DD_IMPROVE_MIN)
    assert not (nan <= -S.DD_IMPROVE_MIN)


# ════════════════════════════════════════════════════════════════════════════
# Continuation — criterion 7 is the staged_exit diagnostic, not a second copy
# ════════════════════════════════════════════════════════════════════════════

def test_the_continuation_margin_is_staged_exits_own_constant():
    from scripts.backtest_study.f2_management import staged_exit as SE
    assert S.CONTINUATION_MARGIN is SE.CONTINUATION_MARGIN
    assert S.post_exit_max is SE.post_exit_max


# ════════════════════════════════════════════════════════════════════════════
# G0's "affected" — the arm CHANGED that row's exit, and nothing else
# ════════════════════════════════════════════════════════════════════════════

class _Pos:
    """The four fields `affected_set` reads off a position."""

    def __init__(self, rec, exit_reason="expired", days_held=10, R=0.0):
        self.rec = rec
        self.exit_reason = exit_reason
        self.days_held = days_held
        self.R = R


def _rec(d: str) -> dict:
    return {"date": d, "ticker": "T"}


def test_only_changed_rows_count_towards_the_power_floor():
    """The registration's "affected" is "the arm changed that row's exit". A row
    only one of the two books took is a RESERVE-RELEASE KNOCK-ON — the arm's
    earlier exit freed a reserve — and counting it towards the floor would
    inflate power in the permissive direction."""
    same, moved, arm_only, base_only = _rec("2026-01-05"), _rec("2026-01-06"), \
        _rec("2026-01-07"), _rec("2026-01-08")
    base = [_Pos(same), _Pos(moved), _Pos(base_only)]
    arm = [_Pos(same), _Pos(moved, exit_reason="atr_stop", days_held=3),
           _Pos(arm_only)]

    aff = S.affected_set(arm, base)
    assert [p.rec for p in aff["changed"]] == [moved]
    assert [p.rec for p in aff["arm_only"]] == [arm_only]
    assert [p.rec for p in aff["base_only"]] == [base_only]
    # The GATED counts are the changed ones alone...
    assert aff["n_rows"] == 1
    assert aff["dates"] == ["2026-01-06"]
    # ...and the knock-ons survive as the disclosed breakdown.
    assert len(aff["knockon_rows"]) == 2
    assert aff["knockon_dates"] == ["2026-01-07", "2026-01-08"]


def test_a_split_row_is_affected_even_when_one_half_did_not_move():
    """ARM P puts two positions on one record and the `pt` half often exits
    where the shipped position did; the comparison is over the whole triple
    SET, so a row whose OTHER half moved still counts as changed."""
    rec = _rec("2026-01-05")
    base = [_Pos(rec)]
    arm = [_Pos(rec), _Pos(rec, days_held=4)]
    assert S.affected_set(arm, base)["n_rows"] == 1


def test_a_split_that_duplicates_one_unchanged_outcome_is_not_affected():
    """The NEGATIVE counterpart, and a G0 power question. When the shipped exit
    was not a profit target, ARM P's `pt` half and its `pt=None` half BOTH exit
    exactly where the shipped position did — the arm changed nothing. A sorted-
    LIST comparison would read `[X, X] != [X]` and count the row towards the
    floor, inflating power in the PERMISSIVE direction that `affected_set`'s own
    docstring forbids; the SET comparison does not."""
    rec = _rec("2026-01-05")
    base = [_Pos(rec)]
    arm = [_Pos(rec), _Pos(rec)]                 # two IDENTICAL halves
    aff = S.affected_set(arm, base)
    assert aff["n_rows"] == 0 and aff["dates"] == []
    assert aff["arm_only"] == [] and aff["base_only"] == []


# ════════════════════════════════════════════════════════════════════════════
# ARM D — the throttle state is re-derived AND reconciled
# ════════════════════════════════════════════════════════════════════════════

class _Sim:
    def __init__(self, taken, throttle_dates):
        self.taken = taken
        self.throttle_dates = list(throttle_dates)


class _Cfg:
    dd_throttle = (0.10, S.ARM_D_RESTORE_FRACTION)
    capital = 25_000.0


class _TPos:
    def __init__(self, d, exit_sess, dollars):
        self.rec = {"date": d, "ticker": "T"}
        self.exit_sess = exit_sess
        self.dollars = dollars


def _throttle_fixture():
    d1, d2 = date(2026, 1, 5), date(2026, 2, 2)
    day_lists = [(d1.isoformat(), [{"t": _Grid([d1])}]),
                 (d2.isoformat(), [{"t": _Grid([d2])}])]
    # One position taken on d1, closed BEFORE d2 at a loss deep enough to put
    # realized equity 10% below the peak — so the throttle is on for d2 alone.
    taken = [_TPos(d1.isoformat(), date(2026, 1, 20), -3_000.0),
             _TPos(d2.isoformat(), date(2026, 2, 20), 100.0)]
    return day_lists, taken, [d2.isoformat()]


def test_the_arm_d_collapse_is_causal_not_modal():
    """`Cfg.dd_throttle` is ONE value for a whole `simulate()`, so ARM D's
    per-block selection must collapse before the stitched book can run. WHICH
    value it collapses to is a NO-LOOKAHEAD question: the MODAL choice replays
    block 0's TEST dates under a `d` fitted on train sets that contain those
    very dates, and the cell would not be out of sample. The EARLIEST block's
    choice reads nothing after its own train window."""
    # Blocks 1 and 2 outvote block 0 — a modal collapse would take 0.10.
    chosen = {0: 0.05, 1: 0.10, 2: 0.10}
    assert S.collapse_choice(chosen) == 0.05
    assert S.collapse_choice({2: 0.10, 0: 0.05, 1: 0.10}) == 0.05   # order-free
    assert S.collapse_choice({7: 0.10}) == 0.10


def test_the_clause_three_row_disclosure_counts_affected_rows(monkeypatch):
    """The registration commits the report to PRINTING "each half's affected-
    date and AFFECTED-ROW counts ... so a reader can see when a cleared sign
    rests on a thin half". Counting every position in the half prints the
    BOOK's size there, which is thin in no half of interest and cannot show the
    thing the disclosure exists for."""
    monkeypatch.setattr(S, "union_axis", lambda a, b: ["2026-01-05", "2026-02-05"])
    monkeypatch.setattr(S, "aligned_daily", lambda bc, axis: {})
    monkeypatch.setattr(S.HE, "stats_on", lambda *a, **k: None)
    monkeypatch.setattr(S.HE, "improvement", lambda *a, **k: 1.0)

    book = [_Pos(_rec(d)) for d in ("2026-01-05", "2026-01-06", "2026-02-05")]
    affected_rows = [_Pos(_rec("2026-01-05"))]
    st_ = S.stability(None, None, 25_000.0, ["2026-01-05"],
                      ["2026-01-05", "2026-02-05"], book, book, affected_rows)
    # ONE affected row in the first half — not the two book rows dated there.
    assert st_["halves"]["first half"]["n_rows"] == 1
    assert st_["halves"]["first half"]["n_dates"] == 1
    assert st_["halves"]["second half"]["n_rows"] == 0


def test_the_throttle_state_matches_the_ledgers_own_record():
    day_lists, taken, active = _throttle_fixture()
    out = S.throttled_entries(_Sim(taken, active), _Cfg(), day_lists)
    assert out["dates"] == active
    assert out["n_rows"] == 1                      # the position entered on d2


def test_a_throttle_disagreement_is_a_hard_failure_not_a_silent_count():
    """Two hand-written implementations of one state machine (the ledger's own
    loop and this re-derivation) is the `s03_risk`/`s04b_page` pattern — which
    only works because something COMPARES them. ARM D's power counts come from
    the re-derivation, so a mismatch has to stop the run."""
    day_lists, taken, _active = _throttle_fixture()
    with pytest.raises(S.ThrottleReconcileError):
        S.throttled_entries(_Sim(taken, []), _Cfg(), day_lists)
    with pytest.raises(S.ThrottleReconcileError):
        S.throttled_entries(_Sim(taken, ["2026-01-05", "2026-02-02"]),
                            _Cfg(), day_lists)


# ════════════════════════════════════════════════════════════════════════════
# Clause 5 — the SECONDARY era, read across the two runs
# ════════════════════════════════════════════════════════════════════════════

def _sibling(ratio, powered=True, verdict="NULL"):
    return {"ARM U/a": dict(verdict=verdict, ratio=ratio, powered=powered)}


def test_clause_five_has_no_referent_inside_the_v3_run():
    ok, text = S.clause_five("ARM U/a", 0.30, None, "n/a", is_v3=True)
    assert ok and "v3 run" in text


def test_clause_five_is_vacuous_when_the_sibling_run_is_not_on_disk():
    """The registration's own treatment of a v3 cell with no sign: "a population
    that says nothing contradicts nothing" — but DISCLOSED, never silent."""
    ok, text = S.clause_five("ARM U/a", 0.30, None, "no file", is_v3=False)
    assert ok and text.startswith("VACUOUS")


def test_clause_five_is_vacuous_on_an_underpowered_sibling_cell():
    ok, text = S.clause_five("ARM U/a", 0.30,
                             _sibling(-0.40, powered=False, verdict="UNDERPOWERED"),
                             "src", is_v3=False)
    assert ok and "VACUOUS" in text


def test_clause_five_passes_a_same_signed_sibling():
    ok, text = S.clause_five("ARM U/a", 0.30, _sibling(0.05), "src", is_v3=False)
    assert ok and "NOT opposite-signed" in text


def test_clause_five_FAILS_a_powered_opposite_signed_sibling():
    """The whole point of the fix: a genuinely powered, opposite-signed v3 cell
    must be able to veto a PRIMARY candidate. Hardcoded True, it never could."""
    ok, text = S.clause_five("ARM U/a", 0.30, _sibling(-0.22), "src", is_v3=False)
    assert not ok and "OPPOSITE-SIGNED" in text


def test_a_failed_clause_five_cannot_reach_candidate():
    """Clause 5 enters the ladder through `stab_ok`, so a failed one leaves an
    otherwise-perfect cell at NULL rather than CANDIDATE."""
    kw = dict(powered=True, dates_ok=True, dd_contrary=False, r_contrary=False,
              dd_ok=True, r_ok=True, cont_ok=True)
    assert S.verdict_token(stab_ok=True, **kw) == S.V_CANDIDATE
    assert S.verdict_token(stab_ok=False, **kw) == S.V_NULL


def test_the_cells_sidecar_round_trips_and_refuses_the_wrong_era(
        tmp_path, monkeypatch):
    """A run records its own cells for the OTHER era's clause 5. The file names
    its own era and one that says otherwise is not read — the two eras never
    pool, here or anywhere else."""
    monkeypatch.setattr(S, "CELLS_DIR", tmp_path)
    cells = {"ARM U/a": dict(verdict="NULL", ratio=-0.05, powered=True)}
    assert S.write_cells_artifact(S.SECONDARY_ERA, cells) is not None
    got, why = S.read_sibling_cells("v4")
    assert got == cells and S.SECONDARY_ERA in why

    # A v3 run has no referent at all.
    assert S.read_sibling_cells(S.SECONDARY_ERA)[0] is None
    # A file recording the wrong era is refused rather than crossed over.
    S.cells_artifact_path(S.SECONDARY_ERA).write_text(
        '{"era": "v4", "cells": {"ARM U/a": {}}}')
    got, why = S.read_sibling_cells("v4")
    assert got is None and "not read" in why


# ════════════════════════════════════════════════════════════════════════════
# The cell report — what it may and may not quote
# ════════════════════════════════════════════════════════════════════════════

def _ev(**over):
    ev = dict(
        gain=1_250.0, ratio=0.25, ci=(400.0, 2_100.0), point=1_250.0,
        d_mean=0.01, d_ci=(-0.01, 0.03), n_paired=80,
        stab=dict(overall=1_250.0,
                  halves={"first": dict(imp=600.0, n_dates=13, n_rows=31),
                          "second": dict(imp=650.0, n_dates=14, n_rows=33)},
                  years={"2026": dict(imp=1_250.0, n_dates=43, n_aff_dates=27)},
                  tiers={"real": dict(imp=900.0, n=60),
                         "tweak": dict(imp=350.0, n=20)},
                  halves_ok=True, years_ok=True, tiers_ok=True,
                  y_present=1, y_agree=1, y_required=1, median_date="2026-04-01"),
        cont=dict(n_early=40, n_continuation=8, share=0.20, strict_share=0.35,
                  passed=True),
        powered=True, c5_text="VACUOUS (no v3 run recorded).",
        n_aff_rows=64, n_aff_dates=27,
        criteria=dict(c1_dd=True, c2_dr=True, c3_stability=True, c4_tiers=True,
                      c5_v3=True, c6_dates=True, c7_cont=True),
        dd_contrary=False, r_contrary=False, verdict=S.V_CANDIDATE, is_v3=False)
    ev.update(over)
    return ev


def _stats(dd):
    import scripts.backtest_study.lib.mtm_curve as M
    return M.PathStats(basis=M.MTM, n_sessions=43, total=1_000.0, max_dd=dd,
                       ulcer=1.5, tuw=0.3, worst_session=-500.0)


def _print_cell(variant, arm_p_dollars, capsys, ev=None):
    S.print_cell(variant, ev or _ev(), _stats(-3_750.0), _stats(-5_000.0),
                 25_000.0, arm_p_dollars)
    return capsys.readouterr().out


def _variant(arm, key):
    return next(v for v in S.variants_for(S.ALL_ARMS)
                if v.arm == arm and v.key == key)


def test_arm_p_withholds_the_ci_bounds_in_dollars_too(capsys):
    """Under the dollars ban the CI bounds are the SAME dollar-improvement
    estimator as the point figure beside them — quoting them raw would print in
    dollars the very number the banner three lines above withholds.

    Asserted over the WHOLE cell, not one slice: the clause-3 halves, the
    clause-3 years and the clause-4 tier lines carry that same account-level
    estimator, and a slice ending at `2 paired` cannot see any of them."""
    out = _print_cell(_variant("P", "half"), False, capsys)
    assert "SHARE OF STARTING CAPITAL" in out
    assert "+5.00% of capital" in out                 # the point estimate
    assert "[+1.60%, +8.40%] of capital" in out       # and its CI bounds
    # halves (+600 / +650), years (+1,250) and tiers (+900 / +350) too.
    assert "+2.40% of cap" in out and "+2.60% of cap" in out
    assert "+5.00% of cap" in out
    assert "+3.60% of cap" in out and "+1.40% of cap" in out
    # NO dollar figure anywhere in an ARM P cell under the ban.
    assert "$" not in out


def test_arm_p_dollars_prints_dollars_everywhere_when_the_flag_is_given(capsys):
    out = _print_cell(_variant("P", "half"), True, capsys)
    assert "[+400, +2,100]" in out
    assert "SHARE OF STARTING CAPITAL" not in out
    # ...and the account-level figures are LABELLED as dollars rather than
    # printed as a bare `+600` a reader cannot assign a unit to.
    assert "$+600" in out and "$+650" in out          # clause 3, halves
    assert "$+900" in out and "$+350" in out          # clause 4, tiers


def test_the_clause_four_signless_reading_is_printed_not_inferred(capsys):
    """A tier with no positions in one book yields `nan`, `_sign(nan) == 0` and
    a FAILED clause 4. The registration spells the signless case out for
    clauses 3 and 5 and is silent for clause 4, so which reading binds must be
    stated on the line rather than left to `nan` propagation."""
    out = _print_cell(_variant("U", "a"), False, capsys)
    assert "4 pricing tiers" in out
    assert "NO SIGN" in out and "is NOT cleared" in out
    assert "wording correction (g)" in out


def test_the_prod_control_says_what_its_affected_count_is_made_of(capsys):
    """ARM W/prod's grid point is pt/sl/tef ONLY: it replaces the whole shipped
    profile and so drops `be_after`/BEAR_HE. Its difference from the shipped
    baseline on bear-debit rows is that merge, not walk-forward selection —
    the opposite of what the control exists to show."""
    out = _print_cell(_variant("W", "prod"), False, capsys)
    assert "be_after" in out and "BEAR_HE" in out
    assert "not walk-forward selection" in out
    assert "be_after" not in _print_cell(_variant("W", "wf"), False, capsys)


def test_the_clause_five_line_comes_from_the_evaluation(capsys):
    """Not a fixed string: the line must say what was actually read, and carry
    its own PASS/FAIL."""
    out = _print_cell(_variant("U", "a"), False, capsys,
                      ev=_ev(c5_text="v3 cell NULL improvement -20.0% is "
                                     "OPPOSITE-SIGNED",
                             criteria=dict(c1_dd=True, c2_dr=True,
                                           c3_stability=True, c4_tiers=True,
                                           c5_v3=False, c6_dates=True,
                                           c7_cont=True)))
    assert "OPPOSITE-SIGNED" in out
    assert "5 SECONDARY v3" in out and "FAIL" in out


def test_the_year_requirement_is_disclosed_beside_the_year_table(capsys):
    """Clause 3 is written against a 3-year book and is NOT scaled up past it;
    the reading is stated rather than tightened at run time."""
    out = _print_cell(_variant("U", "a"), False, capsys)
    assert "TWO" in out and "3 OR MORE" in out
