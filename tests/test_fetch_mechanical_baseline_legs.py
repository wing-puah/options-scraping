"""fetch_mechanical_baseline_legs: the dry run is offline and a real fetch
refuses to run beside another option-cache writer. No network, no cache."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from scripts.backtest.shared import history
from scripts.collector.study_legs import fetch_mechanical_baseline_legs as F

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


def _fake_run(table):
    def run(cmd, **k):
        if cmd[0] == "pgrep":
            return SimpleNamespace(stdout=table["pgrep"].get(cmd[-1], ""))
        return SimpleNamespace(stdout=table["ppid"].get(cmd[-1], "0"))
    return run


def test_other_writers_excludes_self_and_parents():
    pat = F.WRITER_PATTERNS[-1]
    run = _fake_run({"pgrep": {pat: "100\n200\n300\n"},
                     "ppid": {"100": "200", "200": "1", "1": "0"}})
    own = F.ancestry(100, run=run)
    assert own == {"100", "200", "1"}
    assert F.other_writers((pat,), own=own, run=run) == [("300", pat)]


def test_writer_patterns_match_the_running_loops():
    import re
    pats = [re.compile(p.replace("[s]", "s").replace("[f]", "f")) for p in F.WRITER_PATTERNS]
    for cmd in ("python3 scripts/collector/study_legs/fetch_mechanical_legs.py --limit 400",
                "python3 -m scripts.backtest --config config/backtest.yml",
                "python3 -m scripts.backtest.proxy --config config/backtest.yml",
                "python3 -m scripts.journal"):
        assert any(p.search(cmd) for p in pats), cmd
    assert not any(p.search("python3 -m scripts.backtest_study run x") for p in pats)
