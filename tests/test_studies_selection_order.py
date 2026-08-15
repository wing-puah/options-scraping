"""Tests for the `selection_order` study's PURE machinery, plus its gate path.

No book load and no network. Everything up to the closing section builds its own
small `rec` dicts (and a hand-made `Trade` row, adapted from
`tests/test_studies_account_sim.py::_hand_trade`) so the properties pinned here
are the ones the pre-registration
(`research/pre-registrations/selection_order.md`) rests on --

  * `sized_contracts` never drops an unsizable row from the order -- it floors
    to one contract instead, because dropping it would change the candidate
    set, which this study may not do;
  * `sized_dn` is the SIZED delta-notional the net cap actually meters (not
    the per-contract figure), and is 0 when the row can't be signed;
  * `dollars_per_delta` is the one SIZE-INVARIANT ranking key in the module,
    and its two degenerate sentinels (`-inf` unsizable, `+inf` zero-delta) are
    a deliberate design choice, not an accident to be refactored away;
  * every within-tier arm (O1/O2/O3) preserves the tier partition -- only
    O1b, the tier-blind arm, may reorder A ahead of B or vice versa;
  * `perm_keys` is a deterministic, per-day PERMUTATION keyed on record
    identity, not content -- that is what lets G2 probe O4 for lookahead;
  * `contested_dates` is exactly ">=2 candidates AND >=1 exclusion in
    {day3_cap, net_delta, per_pos_delta}" -- `unsizable`/`cash` are
    deliberately excluded from that second half;
  * `paired_rows` drops (and counts, never imputes) a date where one book
    held nothing, and its gain is arm-mean-R minus baseline-mean-R per date;
  * `ex_both_windows` removes BOTH dominant windows in one cut, which
    `protocol.window_cuts` does not provide on its own;
  * `evaluate_arm`'s seven-part bar is a strict AND -- failing any single
    part fails the whole arm, proven here from an all-seven-PASS baseline by
    flipping exactly one part at a time.

The FINAL section is the exception to "pure": it constructs the shipped
`account_sim.Settings` and runs G1/G2 against it, because the one break this
file did not catch was a config field a gate read being deleted underneath it.
See that section's preamble.
"""
import sys
import types
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from scripts.backtest_study.f4_deployment import account_sim as A  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.f4_deployment import selection_order as S  # noqa: E402
from scripts.backtest_study.lib.harness import Trade  # noqa: E402

BUDGET = 500.0


# ── a hand-made Trade row (adapted from test_studies_account_sim.py) ────────

def _hand_trade(marks, contracts, entry=2.00, dte=30, signal=date(2025, 1, 6)):
    """A one-leg long call whose marks are exactly the weekday grid."""
    exp = signal + timedelta(days=dte)
    row = {
        "signal_date": signal.isoformat(), "ticker": "TEST",
        "structure": "long_call", "contracts": str(contracts),
        "dte_entry": str(dte), "entry_option_price": str(entry),
        "entry_underlying": "200",
        "legs": f"TEST:{exp.isoformat()}:100:C +1",
        "daily_price_csv": ",".join(str(m) for m in marks),
    }
    return row


def _grid_len(dte=30, signal=date(2025, 1, 6)):
    end = signal + timedelta(days=dte)
    d, n = signal + timedelta(days=1), 0
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def _rec(delta=0.5, entry_underlying=200.0, mlpc=200.0, tier="A",
         drop_delta=False, drop_entry_underlying=False):
    """A ranking-surface rec: a hand-made Trade row wrapped exactly the way
    `selection_order`'s arms read it -- `t`, `delta`, `max_loss_per_contract`,
    `tier` (+ `post13c` so `ladder_rank`'s tie-break has something to read).

    Only `entry_underlying` off the row and `delta`/`max_loss_per_contract`/
    `tier` off the rec are ever touched by the module under test here -- no
    exit replay happens, so the marks/legs are filler the harness needs to
    construct a valid `Trade`, nothing this file asserts on.
    """
    n = _grid_len()
    row = _hand_trade([2.40] * n, contracts=1)
    if drop_entry_underlying:
        row.pop("entry_underlying", None)
    else:
        row["entry_underlying"] = str(entry_underlying)
    rec = {"t": Trade(row), "max_loss_per_contract": mlpc, "tier": tier,
           "post13c": False}
    if not drop_delta:
        rec["delta"] = delta
    return rec


# ── sized_contracts: the unsizable row holds a place, never dropped ─────────

def test_sized_contracts_falls_back_to_one_when_max_loss_is_none_zero_or_negative():
    for mlpc in (None, 0.0, -50.0):
        rec = _rec(mlpc=mlpc)
        assert S.sized_contracts(rec, BUDGET) == 1


def test_sized_contracts_uses_risk_contracts_when_the_row_is_sizable():
    rec = _rec(mlpc=100.0)
    assert S.sized_contracts(rec, BUDGET) == A.risk_contracts(100.0, BUDGET) == 5


# ── sized_dn: SIZED delta-notional, the quantity the net cap actually meters ─

def test_sized_dn_is_the_per_contract_delta_notional_times_the_sized_count():
    rec = _rec(delta=0.5, entry_underlying=200.0, mlpc=100.0)   # -> 5 contracts
    n = S.sized_contracts(rec, BUDGET)
    assert n == 5
    assert S.sized_dn(rec, BUDGET) == pytest.approx(0.5 * 100 * n * 200.0)


def test_sized_dn_is_zero_when_delta_is_missing():
    rec = _rec(entry_underlying=200.0, mlpc=100.0, drop_delta=True)
    assert S.sized_dn(rec, BUDGET) == 0.0


def test_sized_dn_is_zero_when_entry_underlying_is_missing():
    rec = _rec(delta=0.5, mlpc=100.0, drop_entry_underlying=True)
    assert S.sized_dn(rec, BUDGET) == 0.0


# ── dollars_per_delta: size-invariant, with two deliberate sentinels ────────

def test_dollars_per_delta_is_invariant_to_the_contract_count():
    """The ratio is computed per contract, so it must equal `mlpc x n /
    dn(at n)` for EVERY n -- both scale linearly in contracts and cancel."""
    rec = _rec(delta=0.5, entry_underlying=200.0, mlpc=200.0)
    dpd = S.dollars_per_delta(rec)
    for n in (1, 2, 5, 10):
        dn_at_n = abs(A.signed_dn(rec, n))
        assert dpd == pytest.approx(rec["max_loss_per_contract"] * n / dn_at_n)


def test_dollars_per_delta_is_negative_infinity_for_an_unsizable_row():
    for mlpc in (None, 0.0, -10.0):
        rec = _rec(delta=0.5, entry_underlying=200.0, mlpc=mlpc)
        assert S.dollars_per_delta(rec) == float("-inf")


def test_dollars_per_delta_is_positive_infinity_for_zero_delta_notional():
    zero_delta = _rec(delta=0.0, entry_underlying=200.0, mlpc=200.0)
    assert S.dollars_per_delta(zero_delta) == float("inf")
    # ...and equally when delta is simply absent (signed_dn also reads 0 there).
    missing_delta = _rec(entry_underlying=200.0, mlpc=200.0, drop_delta=True)
    assert S.dollars_per_delta(missing_delta) == float("inf")


# ── make_rank: O0 identity, tier partition, within-tier direction ──────────

def test_make_rank_o0_is_ladder_rank_itself_not_a_copy():
    assert S.make_rank("O0", BUDGET) is P.ladder_rank


def test_make_rank_rejects_an_unknown_arm():
    with pytest.raises(ValueError, match="nope"):
        S.make_rank("nope", BUDGET)


@pytest.mark.parametrize("arm", ["O1", "O2", "O3"])
def test_within_tier_arms_never_reorder_across_tiers(arm):
    """Tier A is made deliberately the WORSE pick by every within-tier metric
    (expensive delta-notional, low $/delta, small |delta|) -- a tier-blind
    sort would put tier B first. O1/O2/O3 must not."""
    a1 = _rec(tier="A", delta=0.80, entry_underlying=200.0, mlpc=800.0)
    a2 = _rec(tier="A", delta=0.70, entry_underlying=200.0, mlpc=700.0)
    b1 = _rec(tier="B", delta=0.05, entry_underlying=200.0, mlpc=50.0)
    b2 = _rec(tier="B", delta=0.02, entry_underlying=200.0, mlpc=20.0)
    ranked = sorted([b1, a1, b2, a2], key=S.make_rank(arm, BUDGET), reverse=True)
    assert {id(r) for r in ranked[:2]} == {id(a1), id(a2)}
    assert {id(r) for r in ranked[2:]} == {id(b1), id(b2)}


def test_o1b_reorders_across_tiers_by_cheap_delta_notional():
    """The whole point of the tier-blind arm: a cheap-delta-notional B row can
    outrank an expensive-delta-notional A row."""
    a_expensive = _rec(tier="A", delta=0.90, entry_underlying=200.0, mlpc=900.0)
    b_cheap = _rec(tier="B", delta=0.01, entry_underlying=200.0, mlpc=10.0)
    ranked = sorted([a_expensive, b_cheap], key=S.make_rank("O1b", BUDGET),
                    reverse=True)
    assert ranked[0] is b_cheap


def test_o1_sorts_smaller_delta_notional_first_within_a_tier():
    cheap = _rec(tier="A", delta=0.05, entry_underlying=200.0, mlpc=50.0)
    expensive = _rec(tier="A", delta=0.80, entry_underlying=200.0, mlpc=800.0)
    ranked = sorted([expensive, cheap], key=S.make_rank("O1", BUDGET), reverse=True)
    assert ranked == [cheap, expensive]


def test_o3_sorts_larger_absolute_delta_first_within_a_tier():
    small = _rec(tier="A", delta=0.05, entry_underlying=200.0, mlpc=100.0)
    large = _rec(tier="A", delta=-0.80, entry_underlying=200.0, mlpc=100.0)
    ranked = sorted([small, large], key=S.make_rank("O3", BUDGET), reverse=True)
    assert ranked == [large, small]


def test_o2_sorts_higher_reserved_dollars_per_unit_delta_first_within_a_tier():
    efficient = _rec(tier="A", delta=0.05, entry_underlying=200.0, mlpc=500.0)
    inefficient = _rec(tier="A", delta=0.80, entry_underlying=200.0, mlpc=100.0)
    ranked = sorted([inefficient, efficient], key=S.make_rank("O2", BUDGET),
                    reverse=True)
    assert ranked == [efficient, inefficient]


def test_an_unsizable_row_still_holds_a_place_in_o1s_order():
    sizable = _rec(tier="A", delta=0.10, entry_underlying=200.0, mlpc=100.0)
    unsizable = _rec(tier="A", delta=0.50, entry_underlying=200.0, mlpc=None)
    ranked = sorted([sizable, unsizable], key=S.make_rank("O1", BUDGET), reverse=True)
    assert {id(r) for r in ranked} == {id(sizable), id(unsizable)}
    assert S.sized_contracts(unsizable, BUDGET) == 1


# ── perm_keys: deterministic, per-day permutation, keyed on identity ────────

def _small_day_lists():
    day1 = [object() for _ in range(4)]
    day2 = [object() for _ in range(3)]
    return [("2025-01-06", day1), ("2025-01-07", day2)]


def test_perm_keys_is_deterministic_for_the_same_seed():
    day_lists = _small_day_lists()
    assert S.perm_keys(day_lists, seed=42) == S.perm_keys(day_lists, seed=42)


def test_perm_keys_differs_for_a_different_seed():
    day_lists = _small_day_lists()
    k1 = S.perm_keys(day_lists, seed=1)
    k2 = S.perm_keys(day_lists, seed=2)
    assert k1 != k2


def test_perm_keys_assigns_exactly_one_key_per_record_forming_a_permutation():
    day_lists = _small_day_lists()
    keys = S.perm_keys(day_lists, seed=7)
    assert len(keys) == sum(len(ranked) for _, ranked in day_lists)
    for _, ranked in day_lists:
        vals = sorted(keys[id(r)] for r in ranked)
        assert vals == [float(i) for i in range(len(ranked))]


# ── contested_dates: >=2 candidates AND >=1 exclusion in CONTEST_BUCKETS ────

class _FakeSim:
    def __init__(self, signal_pos, skipped):
        self.signal_pos = signal_pos
        self.skipped = skipped


def _pos(d):
    return types.SimpleNamespace(rec={"date": d})


def test_contested_dates_excludes_a_date_with_only_one_total_candidate():
    sim = _FakeSim(signal_pos=[],
                   skipped=[({"date": "2025-01-06"}, "net_delta", None)])
    assert S.contested_dates(sim) == set()


def test_contested_dates_excludes_a_date_whose_only_exclusion_is_outside_the_contest_buckets():
    """`unsizable` and `cash` are deliberately absent from CONTEST_BUCKETS --
    a date excluded only there is NOT contested even with 2 candidates."""
    cash_sim = _FakeSim(signal_pos=[_pos("2025-01-06")],
                        skipped=[({"date": "2025-01-06"}, "cash", None)])
    assert S.contested_dates(cash_sim) == set()
    unsizable_sim = _FakeSim(signal_pos=[_pos("2025-01-07")],
                             skipped=[({"date": "2025-01-07"}, "unsizable", None)])
    assert S.contested_dates(unsizable_sim) == set()


@pytest.mark.parametrize("bucket", list(S.CONTEST_BUCKETS))
def test_contested_dates_includes_a_two_candidate_date_excluded_in_any_contest_bucket(bucket):
    sim = _FakeSim(signal_pos=[_pos("2025-02-01")],
                   skipped=[({"date": "2025-02-01"}, bucket, None)])
    assert S.contested_dates(sim) == {"2025-02-01"}


# ── paired_rows: drop+count a one-sided date, gain = arm mean R - base mean R

def _sim_positions(pairs):
    """`[(date, R, dollars)]` -> a fake sim exposing `.signal_pos`."""
    positions = [types.SimpleNamespace(rec={"date": d}, R=r, dollars=dol)
                 for d, r, dol in pairs]
    return types.SimpleNamespace(signal_pos=positions)


def test_paired_rows_drops_and_counts_a_date_where_one_book_held_nothing():
    arm = _sim_positions([("d1", 0.5, 100.0), ("d2", 1.0, 200.0)])
    base = _sim_positions([("d1", 0.2, 50.0)])          # nothing taken on d2
    rows, dropped = S.paired_rows(arm, base, {"d1", "d2"})
    assert dropped == 1
    assert [r["date"] for r in rows] == ["d1"]


def test_paired_rows_gain_is_arm_mean_r_minus_baseline_mean_r_per_date():
    arm = _sim_positions([("d1", 0.6, 100.0), ("d1", 0.4, 50.0)])    # mean 0.5
    base = _sim_positions([("d1", 0.1, 10.0)])                        # mean 0.1
    rows, dropped = S.paired_rows(arm, base, {"d1"})
    assert dropped == 0
    row = rows[0]
    assert row["a"] == pytest.approx(0.5) and row["b"] == pytest.approx(0.1)
    assert row["gain"] == pytest.approx(0.4)
    assert row["a_dol"] == pytest.approx(150.0) and row["b_dol"] == pytest.approx(10.0)


# ── ex_both_windows: removes BOTH dominant windows in one cut ──────────────

def test_ex_both_windows_removes_both_dominant_windows_at_once():
    rows = [
        {"date": "2025-03-15"},   # inside ex_2025_mar_apr only
        {"date": "2026-03-10"},   # inside ex_2026_feb_apr only
        {"date": "2025-06-01"},   # inside neither
    ]
    cut = S.ex_both_windows(rows)
    assert [r["date"] for r in cut] == ["2025-06-01"]
    # protocol.window_cuts removes only ONE window at a time -- each single-cut
    # arm still keeps the row that falls in the OTHER window, unlike ours.
    cuts = dict(P.window_cuts(rows))
    assert any(r["date"] == "2026-03-10" for r in cuts["ex_2025_mar_apr"])
    assert any(r["date"] == "2025-03-15" for r in cuts["ex_2026_feb_apr"])


# ── evaluate_arm: the seven-part bar is a strict AND ────────────────────────
#
# `evaluate_arm` also calls `protocol.boot_ci_paired_by_date` (BOOT_N=10000
# date-clustered resamples). It is deterministic on the uniform fixture below
# regardless of seed (every row is identical), so replacing it with a stand-in
# keeps these tests well under a second without weakening what is asserted:
# the CI values below (0.9, 1.1) still bracket the true mean gain (1.0) away
# from zero, which is exactly the shape criterion (1) requires.

def _passing_rows(n=30):
    """n dates in June 2025 (outside both DOMINANT_WINDOWS), each a uniform
    +1.0 R win over the baseline -- built to clear every one of the seven
    criteria at once, so a single flipped input isolates exactly one part."""
    rows = []
    for i in range(1, n + 1):
        d = f"2025-06-{i:02d}"
        rows.append(dict(date=d, a=1.0, b=0.0, gain=1.0, a_dol=100.0, b_dol=0.0))
    return rows


def _mock_ci(monkeypatch, lo=0.9, hi=1.1):
    monkeypatch.setattr(S.P, "boot_ci_paired_by_date", lambda rows, a, b: (lo, hi))


def test_evaluate_arm_passes_every_criterion_on_a_clean_uniform_win(monkeypatch, capsys):
    _mock_ci(monkeypatch)
    rows = _passing_rows()
    affected = {r["date"] for r in rows}
    band = dict(p95=0.5, draws=[0.1] * 190 + [0.6] * 10)
    res = S.evaluate_arm("O1", rows, affected, band, "test")
    capsys.readouterr()
    for k in ("c1", "c2", "c3", "c4", "c5", "c6", "c7"):
        assert res[k] is True, f"{k} unexpectedly failed on the clean baseline"
    assert res["pass"] is True


def test_evaluate_arm_fails_overall_when_only_the_band_criterion_fails(monkeypatch, capsys):
    """Criterion 7 alone: this arm's gain (1.0) does not clear a p95 of 5.0."""
    _mock_ci(monkeypatch)
    rows = _passing_rows()
    affected = {r["date"] for r in rows}
    band = dict(p95=5.0, draws=[0.1] * 200)
    res = S.evaluate_arm("O1", rows, affected, band, "test")
    capsys.readouterr()
    assert res["c7"] is False
    assert all(res[k] for k in ("c1", "c2", "c3", "c4", "c5", "c6"))
    assert res["pass"] is False


def test_evaluate_arm_fails_overall_when_only_the_affected_dates_criterion_fails(
        monkeypatch, capsys):
    """Criterion 2 alone: an affected set under MIN_AFFECTED_DATES (25)."""
    _mock_ci(monkeypatch)
    rows = _passing_rows()
    affected = set(sorted(r["date"] for r in rows)[:5])
    band = dict(p95=0.5, draws=[0.1] * 200)
    res = S.evaluate_arm("O1", rows, affected, band, "test")
    capsys.readouterr()
    assert res["c2"] is False
    assert all(res[k] for k in ("c1", "c3", "c4", "c5", "c6", "c7"))
    assert res["pass"] is False


def test_evaluate_arm_is_not_evaluable_with_no_paired_rows(capsys):
    res = S.evaluate_arm("O1", [], set(), dict(p95=0.5, draws=[]), "test")
    capsys.readouterr()
    assert res["pass"] is False
    assert res["n_rows"] == 0


# ── G1 / BOOK CALIBRATION: the gate path, exercised on the REAL Settings ────
#
# WHY THESE EXIST. On 2026-08-15 `account_sim` deleted `gates.book_calibration`
# from `config/account-sim.yml` and the four `g1_*` fields from its `Settings`,
# because those constants (220 positions / 90 dates / $63,553 / $1) fingerprinted
# ONE export and so failed on every legitimate data refresh. `gate_g1` here read
# the same four attributes off the same `Settings`, so the removal turned this
# study's first gate into an AttributeError at runtime -- and NO test caught it,
# because every test in this file works on the pure ranking machinery and none
# ever constructed a `Settings` or entered a gate.
#
# So these do exactly that: build the SHIPPED settings object and run the gate
# path against it. Any future field a gate reads and the config stops providing
# now fails here, on the commit that removes it, rather than in a study run.

def _sim_rec(signal: date, tier="A", mlpc=500.0, entry=50.0, mark=90.0, dte=5,
             underlying=50.0, delta=0.05, ticker="TEST"):
    """A rec `account_sim.simulate` can actually take a position on.

    Adapted from `test_studies_account_sim.py::_fat_rec`, plus the `tier` /
    `post13c` that `protocol.ladder_eligible` and `ladder_rank` read -- this
    file's own `_rec` builds a RANKING surface only and is never simulated.
    """
    end = signal + timedelta(days=dte)
    d, n = signal + timedelta(days=1), 0
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    row = _hand_trade([mark] * n, contracts=1, entry=entry, dte=dte,
                      signal=signal)
    row["entry_underlying"] = str(underlying)
    return {"t": Trade(row), "credit": False, "structure": "long_call",
            "mech_cell": "PROD", "max_loss_per_contract": mlpc, "delta": delta,
            "date": signal.isoformat(), "ticker": ticker, "tier": tier,
            "post13c": False}


def _o0_sim(st, pop):
    return A.simulate(P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible),
                      st.cfg("O0 test", compound=False), cache=A.new_cache())


def test_gate_g1_runs_against_the_shipped_settings_object(capsys):
    """The regression guard: every attribute `gate_g1` reads must still exist.

    Uses `load_settings(DEFAULT_CONFIG)` -- the real, committed config -- so a
    field dropped from the YAML or from `Settings` raises here.
    """
    st = A.load_settings(A.DEFAULT_CONFIG)
    pop = [_sim_rec(date(2025, 1, 6))]
    ok = S.gate_g1(st, {"PRIMARY test": (pop, _o0_sim(st, pop))}, A.new_cache())
    out = capsys.readouterr().out
    assert ok is True
    assert "identical" in out and "G1: PASS" in out


def test_gate_g1_fails_when_the_arm_plumbing_is_not_neutral(capsys):
    """G1's surviving job: O0 and a direct ladder walk must agree.

    The baseline handed in was simulated on ONE of the population's two dates,
    so the direct walk books more positions and the signatures diverge.
    """
    st = A.load_settings(A.DEFAULT_CONFIG)
    pop = [_sim_rec(date(2025, 1, 6)), _sim_rec(date(2025, 2, 3))]
    ok = S.gate_g1(st, {"PRIMARY test": (pop, _o0_sim(st, pop[:1]))},
                   A.new_cache())
    out = capsys.readouterr().out
    assert ok is False
    assert "DIVERGED" in out and "G1: FAIL" in out


def test_gate_g1_no_longer_compares_the_book_line_to_a_stored_expectation(capsys):
    """The removed half must not come back: no `expected (...)` line, and no
    reference to the config group that no longer exists."""
    st = A.load_settings(A.DEFAULT_CONFIG)
    pop = [_sim_rec(date(2025, 1, 6))]
    S.gate_g1(st, {"PRIMARY test": (pop, _o0_sim(st, pop))}, A.new_cache())
    out = capsys.readouterr().out
    assert "expected (" not in out
    assert "book_calibration" not in out


def test_print_book_calibration_prints_the_line_and_renders_no_verdict(capsys):
    """The half that SURVIVED is descriptive: numbers, never a PASS/FAIL.

    A verdict next to this line is what made it a snapshot checksum; the line
    itself is the provenance of the book and stays.
    """
    picked = [{"date": "2026-03-10", "R_dol": 100.0},
              {"date": "2026-03-10", "R_dol": 50.0},
              {"date": "2026-03-11", "R_dol": None}]
    S.print_book_calibration(picked)
    out = capsys.readouterr().out
    assert "NOT a gate" in out
    assert "3 positions / 2 dates / $150" in out
    assert "PASS" not in out and "FAIL" not in out


def test_gate_g2_refuses_rather_than_failing_on_an_empty_population(capsys):
    """UNTESTABLE is not FAIL.

    On 2026-08-15 an empty population left G2's tripwire unarmed and printed six
    arms of `sighted 0 blind 0 differing 0 -> DIVERGED`, which reads as "the rank
    functions peek at outcomes". The truth was that there was nothing to test, so
    G2 now refuses with `era.EXIT_THIN_ERA` instead of rendering a verdict.
    """
    st = A.load_settings(A.DEFAULT_CONFIG)
    with pytest.raises(SystemExit) as exc:
        S.gate_g2({"PRIMARY test": []}, st, st.budget)
    out = capsys.readouterr().out
    assert exc.value.code == era.EXIT_THIN_ERA
    assert "NOT EVALUABLE" in out
    assert "REFUSED" in out
    assert "G2: PASS" not in out and "G2: FAIL" not in out
    assert "DIVERGED" not in out


def test_selection_order_declares_its_designed_refusal_exit_codes():
    """`run.py` finds this by AST parse and never imports the module, so it has
    to stay a literal module-level `set` of ints -- an alias to
    `era.DESIGNED_REFUSAL_EXIT_CODES` would be invisible to it and a correct
    refusal would be reported as FAILED with its report deleted."""
    assert S.DESIGNED_REFUSAL_EXIT_CODES == {era.EXIT_THIN_ERA,
                                             era.EXIT_ERA_MISMATCH}
