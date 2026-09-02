"""The exit_basis coherence audit — scripts/backtest_study/lib/basis_audit.py.

The property under test is as much what this module REFUSES to flag as what it
flags. A basis can be ARMED without GOVERNING, so agreement between the label
and the stored exit reason is one-directional; a bidirectional check would
reject ~98 of the 112 non-PROD rows on the v4 book and silently shrink every
stratified cut. And nothing here may raise or drop: gating the book on a LABEL
would block the exit-profile studies the column exists to serve.
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import basis_audit as ba  # noqa: E402
from scripts.backtest_study.lib.replay_basis import unreachable_reasons  # noqa: E402


# ── the profile table ────────────────────────────────────────────────────────

def test_vocabulary_matches_the_writers():
    """Every label `_exit_basis` can emit needs an entry, or a real row audits
    as `unknown_basis`. BEAR_HE stands for the regime cells: a NEW cell with an
    override shipped in config needs adding here too."""
    assert set(ba.BASIS_KNOBS) == {"PROD", "CREDIT", "BEAR_DEBIT", "BEAR_HE"}


def test_each_basis_has_the_unreachable_set_its_knobs_imply():
    for label, knobs in ba.BASIS_KNOBS.items():
        assert ba._UNREACHABLE[label] == unreachable_reasons(knobs)


def test_bear_he_suppresses_the_breakeven_stop():
    """The regime merge lands LAST and nulls `be_after`, so a BEAR_HE row can
    carry trailing_stop but never be_stop — the inverse of BEAR_DEBIT."""
    assert "be_stop" in ba._UNREACHABLE["BEAR_HE"]
    assert "trailing_stop" not in ba._UNREACHABLE["BEAR_HE"]
    assert "be_stop" not in ba._UNREACHABLE["BEAR_DEBIT"]
    assert "trailing_stop" in ba._UNREACHABLE["BEAR_DEBIT"]


def test_profiles_are_historical_not_a_live_config_read():
    """`simulation.structure_exit.enabled` is false as of 2026-09-02 while 95
    v4 rows carry BEAR_DEBIT from when it shipped. Reading the live YAML would
    call all 95 incoherent, so the table must not consult it."""
    src = (ROOT / "scripts/backtest_study/lib/basis_audit.py").read_text()
    assert "backtest.yml" not in src.split('"""')[2]  # not in code, only prose
    assert "yaml" not in src.lower().split('"""')[2]


# ── sign_conflict: the only bidirectional check ──────────────────────────────

def test_credit_label_on_a_debit_row_is_a_conflict():
    assert ba.audit_row("CREDIT", "profit_target", 1.20) == "sign_conflict"


def test_debit_label_on_a_credit_row_is_a_conflict():
    assert ba.audit_row("PROD", "profit_target", -1.20) == "sign_conflict"


def test_credit_label_on_a_credit_row_is_fine():
    assert ba.audit_row("CREDIT", "profit_target", -1.20) == "ok"


def test_sign_check_is_skipped_when_the_entry_is_unknown():
    assert ba.audit_row("CREDIT", "profit_target", None) == "ok"


# ── cell_conflict: cross-checked against the SPY/VIX re-derivation ───────────

def test_regime_label_must_match_the_independently_derived_cell():
    assert ba.audit_row("BEAR_HE", "trailing_stop", 2.50, "BULL_LO") == "cell_conflict"


def test_regime_label_agreeing_with_the_cell_is_fine():
    assert ba.audit_row("BEAR_HE", "trailing_stop", 2.50, "BEAR_HE") == "ok"


def test_cell_check_is_skipped_when_the_table_cannot_label_the_date():
    """None means "unlabelled", not "disagrees" — the mech table starts in 2024
    and a date outside it must not manufacture a conflict."""
    assert ba.audit_row("BEAR_HE", "trailing_stop", 2.50, None) == "ok"


def test_a_prod_row_on_a_cell_date_is_not_a_conflict():
    """One-directional. A row whose date IS BEAR_HE but which was simulated
    before the 2026-07-22 override shipped correctly reports PROD."""
    assert ba.audit_row("PROD", "profit_target", 2.50, "BEAR_HE") == "ok"


# ── unreachable_reason: armed is not governed ────────────────────────────────

def test_stored_reason_the_claimed_profile_cannot_emit():
    assert ba.audit_row("PROD", "be_stop", 2.50) == "unreachable_reason"


def test_the_profile_that_can_emit_it_is_fine():
    assert ba.audit_row("BEAR_DEBIT", "be_stop", 2.50) == "ok"


def test_an_armed_basis_that_did_not_govern_is_not_a_conflict():
    """THE central non-regression. BEAR_HE arms a trail; if the trail never
    triggered the row exits on profit_target and that is correct. Flagging it
    would eject the 98 v4 rows measured 2026-09-02 whose override was armed but
    did not produce the exit."""
    for reason in ("profit_target", "stop_loss", "dollar_stop", "time_exit", "cap_open"):
        assert ba.audit_row("BEAR_HE", reason, 2.50, "BEAR_HE") == "ok"
        assert ba.audit_row("BEAR_DEBIT", reason, 2.50) == "ok"


def test_credit_carries_the_widest_unreachable_set():
    """Attempt 13 left credits with a profit target and nothing else."""
    assert ba.audit_row("CREDIT", "stop_loss", -1.20) == "unreachable_reason"
    assert ba.audit_row("CREDIT", "time_exit", -1.20) == "unreachable_reason"
    assert ba.audit_row("CREDIT", "profit_target", -1.20) == "ok"


# ── unlabelled / unknown ─────────────────────────────────────────────────────

def test_blank_is_absent_not_a_conflict():
    for blank in ("", None, "   "):
        assert ba.audit_row(blank, "profit_target", 2.50) == "absent"


def test_a_label_outside_the_vocabulary_is_reported_not_guessed():
    assert ba.audit_row("BEAR_LO", "profit_target", 2.50) == "unknown_basis"


# ── column_present: the era gate ─────────────────────────────────────────────

def test_column_present_on_a_v4_header():
    assert ba.column_present(["ticker", "exit_reason", "exit_basis"])


def test_column_absent_on_a_v3_header():
    """v3 exports it into a NAMELESS trailing field, so the name is missing and
    every row must audit as `absent`. An unreadable label is not a wrong one."""
    assert not ba.column_present(["ticker", "exit_reason", "Unnamed: 46"])


# ── audit(): reports, never gates ────────────────────────────────────────────

_ROWS = [
    dict(exit_basis="PROD", exit_reason="profit_target", entry_net=2.5, mech_cell=None),
    dict(exit_basis="CREDIT", exit_reason="profit_target", entry_net=1.5, mech_cell=None),
    dict(exit_basis="", exit_reason="stop_loss", entry_net=2.5, mech_cell=None),
    dict(exit_basis="PROD", exit_reason="be_stop", entry_net=2.5, mech_cell=None),
]


def test_audit_tallies_every_row_and_returns_only_the_conflicts():
    tally, conflicts = ba.audit(_ROWS)
    assert tally == Counter({"ok": 1, "sign_conflict": 1, "absent": 1,
                             "unreachable_reason": 1})
    assert sum(tally.values()) == len(_ROWS)
    assert [c["basis_verdict"] for c in conflicts] == ["sign_conflict",
                                                       "unreachable_reason"]


def test_unlabelled_rows_are_never_reported_as_conflicts():
    _tally, conflicts = ba.audit([_ROWS[2]])
    assert conflicts == []


def test_audit_short_circuits_an_export_without_the_column():
    tally, conflicts = ba.audit(_ROWS, columns=["ticker", "exit_reason"])
    assert tally == Counter({"absent": len(_ROWS)})
    assert conflicts == []


def test_a_nan_cell_is_absent_not_a_crash():
    """pandas types an all-blank exit_basis column as float64, so every cell
    arrives as NaN — truthy, and fatal to a plain falsiness check. This is the
    shape BacktestProxy has until the proxy is re-run."""
    assert ba.audit_row(float("nan"), "profit_target", 2.50) == "absent"


def test_audit_raises_on_nothing():
    """The contract that makes it safe in load_book: garbage in, verdict out."""
    tally, _c = ba.audit([dict(exit_basis=object(), exit_reason=None,
                               entry_net=None, mech_cell=None)])
    assert sum(tally.values()) == 1


def test_format_tally_names_the_zero_buckets():
    """A check that prints nothing on success is a check nobody notices has
    stopped running."""
    line = ba.format_tally(Counter({"ok": 485, "absent": 511}), 996)
    for bucket in ("sign_conflict", "cell_conflict", "unreachable_reason",
                   "unknown_basis"):
        assert f"0 {bucket}" in line
    assert "485 coherent" in line and "511 unlabelled" in line and "of 996" in line
