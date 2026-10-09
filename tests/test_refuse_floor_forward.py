"""Unit tests for `refuse_floor_forward`'s pure pieces: the complete prefix,
the minimum counts, the verdict order and FW4. The confidence sequence itself
is pinned in tests/test_confidence_sequence.py."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.backtest_study.f4_deployment import refuse_floor_forward as M


def pos(day: str, r: float, exit_reason: str = "profit_target",
        path_status: str = "complete", credit: bool = False):
    t = SimpleNamespace(row={"path_status": path_status})
    return SimpleNamespace(rec={"date": day, "t": t, "credit": credit}, R=r,
                           exit_reason=exit_reason, dollars=r * 100)


def test_registered_constants():
    assert M.FIRST_FORWARD_DATE == "2026-10-08"
    assert (M.ALPHA, M.T_STAR, M.MIN_DATES, M.MIN_POSITIONS) == (0.0125, 150, 30, 60)
    assert M.REFUTE_BAR == 0.10 and M.DD_BAR == 0.25
    assert M.GRADED == ("F2", "F3")
    assert M.CAPS == (1.50, 2.50)
    assert M.EXIT_NO_FORWARD in M.DESIGNED_REFUSAL_EXIT_CODES
    # Four graded sequences share the 0.05 family error rate.
    assert M.ALPHA * len(M.GRADED) * len(M.CAPS) == pytest.approx(0.05)


def test_the_floored_f3_line_is_a_declared_secondary_outside_the_family():
    # Resolved at build 2026-10-09: sequenced and printed, never graded into
    # the four-sequence alpha family, and narrowed under narrow_to_fit's floor.
    assert M.SECONDARY == ("F3_FL",)
    assert not set(M.SECONDARY) & set(M.GRADED)
    assert M.SEQUENCED == M.GRADED + M.SECONDARY
    row = {k: (kind, floor, graded) for k, _l, kind, floor, graded in M.CELLS}
    assert row["F3_FL"] == ("low", "narrow", False) == row["F3"][:2] + (False,)
    assert M.NF.NET_FLOOR_SHARE == 0.20


def test_open_means_cap_open_at_the_data_end_only():
    assert M.is_open(pos("2026-10-08", 0.1, "cap_open", "open_at_data_end"))
    assert not M.is_open(pos("2026-10-08", 0.1, "cap_open", "complete"))    # path cap
    assert not M.is_open(pos("2026-10-08", 0.1, "expired", "open_at_data_end"))
    assert not M.is_open(pos("2026-10-08", 0.1, "stop_loss", "open_at_data_end"))


def test_observations_are_date_means_and_stop_before_the_first_open_date():
    ps = [pos("2026-10-09", 0.4), pos("2026-10-08", 0.2), pos("2026-10-08", -0.4),
          pos("2026-10-12", 1.0, "cap_open", "open_at_data_end"), pos("2026-10-12", 0.5),
          pos("2026-10-13", 0.3)]
    obs, stop, n_open = M.date_observations(ps)
    assert obs == [("2026-10-08", pytest.approx(-0.1), 2), ("2026-10-09", 0.4, 1)]
    assert stop == "2026-10-12" and n_open == 1


def test_start_needs_both_minimum_counts():
    one_a_day = [(f"d{i:03d}", 0.1, 1) for i in range(80)]
    assert M.start_index(one_a_day) == 60            # positions bind
    three_a_day = [(f"d{i:03d}", 0.1, 3) for i in range(40)]
    assert M.start_index(three_a_day) == 30          # dates bind
    assert M.start_index(three_a_day[:29]) is None


def _seq(run_lo, run_hi, start=30, empty=False):
    return dict(start=start, run_lo=run_lo, run_hi=run_hi, empty=empty)


@pytest.mark.parametrize("seq,dd,awaiting,want", [
    (_seq(0.05, 0.5), False, True, M.AWAITING),
    (_seq(0.05, 0.5), True, False, M.REFUTED_DD),
    (_seq(None, None, start=None), True, False, M.REFUTED_DD),   # fires at any count
    (_seq(-0.3, 0.09), False, False, M.REFUTED_EDGE),
    (_seq(0.01, 0.5), False, False, M.CONFIRMED),
    (_seq(-0.1, 0.5), False, False, M.OPEN),
    (_seq(None, None, start=None), False, False, M.OPEN),
    (_seq(0.3, 0.2, empty=True), False, False, M.OPEN),          # CS EMPTY
])
def test_verdict_takes_the_first_row_that_holds(seq, dd, awaiting, want):
    assert M.verdict(seq, dd, awaiting) == want


def test_headline_is_the_worse_of_two_cap_cells():
    assert M.worse(M.CONFIRMED, M.OPEN) == M.OPEN
    assert M.worse(M.OPEN, M.REFUTED_EDGE) == M.REFUTED_EDGE
    assert M.worse(M.AWAITING, M.OPEN) == M.AWAITING
    assert M.worse(M.CONFIRMED, M.CONFIRMED) == M.CONFIRMED


def _obs(n, x=0.2, k=2):
    return [(f"2026-11-{i:02d}" if i < 31 else f"2026-12-{i - 30:02d}",
             x + (0.3 if i % 2 else -0.3), k) for i in range(1, n + 1)]


def test_fw4_reproduces_an_unchanged_sequence_and_explains_a_changed_one():
    obs = _obs(40)
    seq = M.run_sequence(obs)
    look = {"sequences": {"F2|1.50|PRIMARY": seq}}
    ok, lines = M.fw4_check("F2|1.50|PRIMARY", M.run_sequence(obs + _obs(45)[40:]), [look])
    assert ok and "reproduced" in lines[0]

    moved = list(obs)
    moved[3] = (moved[3][0], moved[3][1] + 1.0, moved[3][2])
    ok, lines = M.fw4_check("F2|1.50|PRIMARY", M.run_sequence(moved), [look])
    assert ok and obs[3][0] in lines[0]


def test_fw4_fails_when_the_interval_moves_with_no_changed_value():
    obs = _obs(40)
    seq = M.run_sequence(obs)
    tampered = dict(seq, run_lo=seq["run_lo"] + 0.01)
    ok, lines = M.fw4_check("F2|1.50|PRIMARY", seq, [{"sequences": {"F2|1.50|PRIMARY":
                                                                    tampered}}])
    assert not ok and "FAILS" in lines[0]


def test_fw4_with_no_earlier_look_passes():
    ok, _ = M.fw4_check("F3|2.50|PRIMARY", M.run_sequence(_obs(5)), [])
    assert ok


def test_the_look_log_is_append_only(tmp_path):
    path = tmp_path / "looks.jsonl"
    M.append_look({"a": 1}, path)
    M.append_look({"a": 2}, path)
    assert [lk["a"] for lk in M.read_looks(path)] == [1, 2]
