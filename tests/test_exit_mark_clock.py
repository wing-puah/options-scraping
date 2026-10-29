"""exit_mark_clock: the scoped ARM M swap, its mark rule, the verdict, the
forward-date filter, G-LOOK, and the no-network / no-write surface.

research/pre-registrations/f2_management/exit_mark_clock.md. All fixtures are
synthetic; nothing reads the real exports or the option cache.
"""
from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.backtest import simulate as SIM
from scripts.backtest_study.f2_management import exit_mark_clock as E

MOD = Path(E.__file__)
D0 = date(2026, 11, 2)


# (a) the context manager always restores production's functions ----------------

def test_arm_restores_originals_on_exit():
    orig_jdm, orig_snap = SIM.junk_day_mark, SIM._snap_asof
    for name in ("P", "M"):
        with E.arm(name):
            assert SIM.junk_day_mark is not orig_jdm
            assert SIM._snap_asof is not orig_snap
        assert SIM.junk_day_mark is orig_jdm
        assert SIM._snap_asof is orig_snap


def test_arm_restores_originals_on_exception():
    orig_jdm, orig_snap = SIM.junk_day_mark, SIM._snap_asof
    with pytest.raises(RuntimeError):
        with E.arm("M"):
            raise RuntimeError("boom")
    assert SIM.junk_day_mark is orig_jdm
    assert SIM._snap_asof is orig_snap


def test_unknown_arm_refused_without_patching():
    orig = SIM.junk_day_mark
    with pytest.raises(ValueError):
        with E.arm("Q"):
            pass
    assert SIM.junk_day_mark is orig


# (b) ARM M's mark rule ------------------------------------------------------------

def _orig(row, q_day, series, details, expiration=None):
    return ("ORIGINAL", "barchart_stale", q_day - timedelta(days=1))


def test_two_sided_junk_quote_marks_at_close_mid():
    row = {"Bid": "1.00", "Ask": "4.00", "Latest": "3.90", "Volume": "5"}
    assert SIM._is_junk_quote(row)
    assert E.mid_mark(_orig)(row, D0, [], {D0: row}) == (2.5, "barchart", D0)


def test_no_bid_junk_quote_falls_through_to_arm_p():
    row = {"Bid": "0", "Ask": "0.40", "Latest": "0.10", "Volume": "0"}
    assert SIM._is_junk_quote(row)
    assert E.mid_mark(_orig)(row, D0, [], {D0: row})[0] == "ORIGINAL"


def test_arm_m_matches_production_when_no_bid():
    row = {"Bid": "0", "Ask": "0.05"}
    series, details = [(D0, 0.025)], {D0: row}
    want = SIM.junk_day_mark(row, D0, series, details)
    with E.arm("M"):
        assert SIM.junk_day_mark(row, D0, series, details) == want


def test_arm_p_is_production_unchanged():
    row = {"Bid": "1.00", "Ask": "4.00", "Latest": "3.90", "Volume": "5"}
    want = SIM.junk_day_mark(row, D0, [], {D0: row})
    with E.arm("P"):
        assert SIM.junk_day_mark(row, D0, [], {D0: row}) == want


# G-LOOK ---------------------------------------------------------------------------

def test_g_look_passes_a_same_day_mid():
    row = {"Bid": "1.00", "Ask": "4.00"}
    with E.arm("M") as probe:
        SIM._snap_asof({"k": [(D0, 2.5)]}, "k", D0)
        SIM.junk_day_mark(row, D0, [(D0, 2.5)], {D0: row})
    assert probe.violations == [] and probe.mid_marks == 1


def test_g_look_flags_a_row_after_the_grid_day():
    later = D0 + timedelta(days=1)
    row = {"Bid": "1.00", "Ask": "4.00"}
    with E.arm("M") as probe:
        SIM._snap_asof({"k": [(D0, 2.5)]}, "k", D0)        # grid day D0
        SIM.junk_day_mark(row, later, [], {later: row})    # reads D0+1
    assert any("after grid day" in v for v in probe.violations)


def test_g_look_flags_a_mark_snapped_after_its_row(monkeypatch):
    def peeks(row, q_day, series, details, expiration=None):
        return 1.0, "barchart_stale", q_day + timedelta(days=3)
    monkeypatch.setattr(SIM, "junk_day_mark", peeks)
    with E.arm("P") as probe:
        SIM.junk_day_mark({"Bid": "0", "Ask": "1"}, D0, [], {})
    assert any("after its row" in v for v in probe.violations)


def test_g_look_flags_a_snap_after_its_day(monkeypatch):
    monkeypatch.setattr(SIM, "_snap_asof", lambda s, k, d, e=None: (1.0, d + timedelta(days=1)))
    with E.arm("P") as probe:
        SIM._snap_asof({}, "k", D0)
    assert probe.violations


# (c) verdict logic ----------------------------------------------------------------

def _dates(vals):
    return {D0 + timedelta(days=i): v for i, v in enumerate(vals)}


def test_verdict_underpowered_below_floor():
    assert E.verdict(_dates([100.0] * 24))[0] == "UNDERPOWERED"
    assert E.verdict({})[0] == "UNDERPOWERED"


def test_verdict_candidate():
    tok, e = E.verdict(_dates([10.0] * 25))
    assert tok == "CANDIDATE" and e["total"] == 250 and e["median"] == 10


def test_verdict_contrary():
    assert E.verdict(_dates([-10.0] * 25))[0] == "CONTRARY"


def test_verdict_null_when_one_half_loses():
    # total > 0, median > 0, but the first chronological half is negative.
    vals = [-100.0] * 4 + [5.0] * 8 + [50.0] * 13
    tok, e = E.verdict(_dates(vals))
    assert e["total"] > 0 and e["median"] > 0 and e["h1"] < 0
    assert tok == "NULL"


def test_verdict_null_when_median_flat():
    vals = [-1.0] * 13 + [1000.0] * 12      # total > 0, median < 0
    assert E.verdict(_dates(vals))[0] == "NULL"


def test_halves_put_the_odd_date_second():
    h1, h2 = E.halves([3, 1, 2])
    assert h1 == [1] and h2 == [2, 3]


def _r(exit_reason="profit_target", dh=3, pnl=10.0, status="complete"):
    return {"exit_reason": exit_reason, "days_held": dh, "realized_pnl_abs": pnl,
            "path_status": status}


def test_per_date_deltas_counts_only_affected_dates_and_skips_open_rows():
    d1, d2, d3 = D0, D0 + timedelta(days=1), D0 + timedelta(days=2)
    pairs = [
        (d1, _r(pnl=10), _r(pnl=10)),                    # unchanged: not affected
        (d2, _r(pnl=10), _r("dollar_stop", 5, -40)),     # affected: -50
        (d2, _r(pnl=0), _r(pnl=0)),                      # same date, no change
        (d3, _r(pnl=10, status=E.OPEN), _r(pnl=99)),     # open in ARM P: excluded
    ]
    assert E.per_date_deltas(pairs) == {d2: -50.0}


def test_outcome_triple_rounds_pnl():
    assert E.outcome({"exit_reason": "time_exit", "days_held": "7.0",
                      "realized_pnl_abs": "12.3449"}) == ("time_exit", 7, 12.34)
    assert E.outcome({"exit_reason": "x", "days_held": "", "realized_pnl_abs": "1"}) is None


# (d) the forward-date filter ------------------------------------------------------

def test_registered_constants():
    assert E.REGISTERED_ON == date(2026, 10, 29)
    assert E.G_REPRO_MIN == 0.98 and E.G_THIN_MIN_DATES == 25


@pytest.mark.parametrize("sig,graded", [
    ("2026-10-28", False),
    ("2026-10-29", False),            # the registration date itself is excluded
    ("2026-10-30", True),
    ("2026-10-30 09:30:00", True),
    ("", False),
])
def test_forward_filter(sig, graded):
    assert E.is_forward({"signal_date": sig}) is graded


def test_forward_rows_filters_a_list():
    rows = [{"signal_date": d} for d in ("2026-10-29", "2026-10-30", "2026-09-01")]
    assert [r["signal_date"] for r in E.forward_rows(rows)] == ["2026-10-30"]


# safety surface: no network, no tab write -----------------------------------------

def test_module_imports_no_writer_or_fetcher():
    tree = ast.parse(MOD.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    for banned in ("lib.sheets_client", "lib.drive_client", "lib.drive_sync",
                   "fetch_option_histories", "sheets_client", "drive_client"):
        assert banned not in names, banned


def test_replay_is_cache_only_and_never_probes():
    src = MOD.read_text()
    assert "cache_only=True" in src
    assert '"exit_mark_clock", False)' in src      # proxy._evaluate(..., allow_probe=False)
    assert "append_rows" not in src
