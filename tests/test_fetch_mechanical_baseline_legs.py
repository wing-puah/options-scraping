"""fetch_mechanical_baseline_legs: the dry run is offline and a real fetch
refuses to run beside another option-cache writer. No network, no cache."""
from __future__ import annotations

from datetime import date

import pytest

from scripts.backtest.shared import history
from scripts.collector.study_legs.f1_selection import fetch_mechanical_baseline_legs as F

PLAN = [dict(ticker="SPY", expiration=date(2026, 3, 20), strike=600.0,
             opt_type="Call", category="SPY:weekly:65:A")]


@pytest.fixture
def no_network(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("network fetch attempted")
    monkeypatch.setattr(history, "fetch_option_histories", boom)
    monkeypatch.setattr(F.MBL, "plan", lambda scope: list(PLAN))


def test_dry_run_is_offline_and_not_refused(no_network, monkeypatch, capsys):
    def busy(*a, **k):
        raise AssertionError("the dry run must not consult the writer guard")
    monkeypatch.setattr(F, "other_writers", busy)
    assert F.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "to fetch (primary): 1" in out and "[dry-run] nothing fetched" in out


def test_real_fetch_refuses_beside_another_writer(no_network, monkeypatch, capsys):
    monkeypatch.setattr(F, "other_writers", lambda: [("69881", "fetch")])

    def no_plan(scope):
        raise AssertionError("planned while another writer runs")
    monkeypatch.setattr(F.MBL, "plan", no_plan)
    assert F.main(["--limit", "1"]) == F.EXIT_OTHER_WRITER
    assert "REFUSED" in capsys.readouterr().err


SCRIPT = "scripts/collector/study_legs/f1_selection/fetch_state_map_legs.py"
SELF = "500"


def _writers(rows, own=SELF):
    ancestors = F.ancestry(int(own), table=rows)
    return F.other_writers(own=ancestors, table=rows)


def test_launching_shell_and_wrappers_are_not_counted():
    rows = [("1", "0", "/sbin/launchd"),
            ("200", "1", f"/bin/zsh -c caffeinate -i python3 {SCRIPT} --limit 5"),
            ("300", "200", f"caffeinate -i python3 {SCRIPT} --limit 5"),
            ("400", "300", f"rtk python3 {SCRIPT}"),
            ("450", "400", f"make fetch ARGS={SCRIPT}"),
            (SELF, "450", f"/usr/bin/python3 {SCRIPT} --limit 5"),
            ("501", SELF, "ps -axo pid=,ppid=,command=")]
    assert _writers(rows) == []


def test_scan_own_children_and_text_mentions_are_not_counted():
    rows = [(SELF, "1", f"python3 {SCRIPT}"),
            ("501", SELF, f"pgrep -f {SCRIPT}"),
            ("600", "1", f"tail -f logs/{SCRIPT}.log"),
            ("601", "1", "grep fetch_state_map_legs.py logs/x"),
            ("602", "1", f"vim {SCRIPT}"),
            ("603", "1", f"/bin/zsh -c python3 {SCRIPT}"),
            ("604", "1", "python3 -c print('fetch_x_legs.py')")]
    assert _writers(rows) == []


def test_second_real_python_writer_is_counted():
    rows = [(SELF, "1", f"python3 {SCRIPT}"),
            ("700", "10", f"/opt/homebrew/bin/python3.12 {SCRIPT} --limit 9"),
            ("701", "11", "python3 -m scripts.backtest --config config/backtest.yml --redo"),
            ("702", "12", "Python -m scripts.journal recommend"),
            ("703", "13", "python3 -m scripts.backtest_study run x")]
    got = _writers(rows)
    assert [p for p, _ in got] == ["700", "701", "702"]


def test_writer_target_reads_interpreter_args():
    assert F.writer_target("python3 -u -m scripts.backtest.proxy --x") == "scripts.backtest.proxy"
    assert F.writer_target("python3 -W ignore a/fetch_a_legs.py") == "a/fetch_a_legs.py"
    assert F.writer_target("caffeinate python3 a/fetch_a_legs.py") is None
