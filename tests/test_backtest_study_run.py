"""Tests for scripts/backtest_study/run.py's post-run chart refresh.

Mirrors tests/test_study_review.py's approach: stub out anything that would
shell out or touch real study output (a real chart render, a real study
subprocess) and exercise the deterministic wiring around it. No real study
run, no real `scripts.study_charts` render, no writes to the tracked
`docs/` pages happen here — see the manual end-to-end check noted in the
session's task instead for that.
"""
from __future__ import annotations

import scripts.study_map.build as map_build
from scripts.backtest_study import run as study_runner


class _FakeChartModule:
    """Stands in for a `scripts.study_charts.<name>` module's `main(argv)`."""

    def __init__(self, result):
        self.result = result  # int return code, or an Exception/SystemExit to raise
        self.calls: list[list[str]] = []

    def main(self, argv: list[str]) -> int:
        self.calls.append(argv)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class _FakePopen:
    """Stands in for `subprocess.Popen` inside `run_one` — no real study
    subprocess runs; `stdout` is a canned iterable of lines and `wait()`
    hands back whatever exit code the test wants."""

    def __init__(self, lines: list[str], rc: int):
        self.stdout = iter(lines)
        self._rc = rc

    def wait(self) -> int:
        return self._rc


# ────────────────────────────── _render_charts ───────────────────────────────

def test_render_charts_skips_studies_with_no_chart_module(monkeypatch):
    """Most studies have no chart page at all — that must not even try to import."""
    def _forbidden(name):
        raise AssertionError(f"import_module must not run for a chart-less study (got {name!r})")

    monkeypatch.setattr(study_runner.importlib, "import_module", _forbidden)
    study_runner._render_charts("bear_deploy", [])  # not in CHART_MODULES


def test_render_charts_points_at_the_plain_positions_csv_by_default(monkeypatch, capsys):
    fake = _FakeChartModule(0)
    monkeypatch.setitem(study_runner.CHART_MODULES, "account_sim", ["fake.chart.module"])
    monkeypatch.setattr(study_runner.importlib, "import_module", lambda name: fake)

    study_runner._render_charts("account_sim", [])

    want = str(study_runner.OUT_DIR / "account_sim-positions-latest.csv")
    assert fake.calls == [["--positions", want]]
    assert "chart refreshed: fake.chart.module" in capsys.readouterr().out


def test_render_charts_points_at_the_structure_positions_csv_for_that_arm(monkeypatch):
    """The whole point of arm pairing: a --structure-universe run must not
    render the frozen book's chart page from the widened arm's data."""
    fake = _FakeChartModule(0)
    monkeypatch.setitem(study_runner.CHART_MODULES, "account_sim", ["fake.chart.module"])
    monkeypatch.setattr(study_runner.importlib, "import_module", lambda name: fake)

    study_runner._render_charts("account_sim", ["--structure-universe"])

    want = str(study_runner.OUT_DIR / "account_sim-positions-structure-latest.csv")
    assert fake.calls == [["--positions", want]]


def test_render_charts_warns_loudly_on_a_nonzero_return_but_does_not_raise(monkeypatch, capsys):
    """cli.run returns 1 (not SystemExit) when reconciliation fails — the
    exact case this whole task exists to make visible."""
    fake = _FakeChartModule(1)
    monkeypatch.setitem(study_runner.CHART_MODULES, "account_sim", ["fake.chart.module"])
    monkeypatch.setattr(study_runner.importlib, "import_module", lambda name: fake)

    study_runner._render_charts("account_sim", [])  # must not raise

    err = capsys.readouterr().err
    assert "CHART RENDER FAILED" in err
    assert "account_sim" in err and "fake.chart.module" in err


def test_render_charts_surfaces_a_systemexit_message_verbatim(monkeypatch, capsys):
    """cli.py raises SystemExit(<message>) for setup problems (missing
    positions CSV, no matching report, wrong arm) — the message is the whole
    point and must not collapse into a bare 'exit 1'."""
    fake = _FakeChartModule(SystemExit("positions CSV not found: /nowhere.csv"))
    monkeypatch.setitem(study_runner.CHART_MODULES, "account_sim", ["fake.chart.module"])
    monkeypatch.setattr(study_runner.importlib, "import_module", lambda name: fake)

    study_runner._render_charts("account_sim", [])

    err = capsys.readouterr().err
    assert "positions CSV not found: /nowhere.csv" in err


def test_render_charts_treats_an_integer_systemexit_code_as_the_rc(monkeypatch, capsys):
    fake = _FakeChartModule(SystemExit(1))
    monkeypatch.setitem(study_runner.CHART_MODULES, "account_sim", ["fake.chart.module"])
    monkeypatch.setattr(study_runner.importlib, "import_module", lambda name: fake)

    study_runner._render_charts("account_sim", [])

    err = capsys.readouterr().err
    assert "CHART RENDER FAILED" in err and "exit 1" in err


def test_render_charts_keeps_going_after_one_module_fails(monkeypatch, capsys):
    """account_sim has two pages (readout + regime); one page's failure must
    not stop the other from being refreshed."""
    bad = _FakeChartModule(RuntimeError("boom"))
    good = _FakeChartModule(0)
    modules = {"fake.bad": bad, "fake.good": good}
    monkeypatch.setitem(study_runner.CHART_MODULES, "account_sim", list(modules))
    monkeypatch.setattr(study_runner.importlib, "import_module", lambda name: modules[name])

    study_runner._render_charts("account_sim", [])

    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert "chart refreshed: fake.good" in captured.out
    assert good.calls  # the second module still ran


# ───────────────────────────────── run_one ───────────────────────────────────

def test_run_one_promotes_the_stamped_report_to_latest_on_a_zero_exit(monkeypatch, tmp_path):
    monkeypatch.setattr(study_runner, "OUT_DIR", tmp_path)
    monkeypatch.setattr(study_runner, "_header", lambda name, argv: "HEADER\n")
    monkeypatch.setattr(study_runner.subprocess, "Popen",
                        lambda *a, **k: _FakePopen(["line one\n", "line two\n"], 0))

    rc, out_path = study_runner.run_one("fake_study", [], dry_run=False)

    assert rc == 0
    latest = tmp_path / "fake_study-latest.txt"
    assert latest.exists()
    assert latest.read_text() == out_path.read_text()
    body = out_path.read_text()
    assert body.startswith("HEADER\n")
    assert "line one\n" in body and "line two\n" in body
    assert "exit code 0" in body


def test_run_one_leaves_latest_untouched_and_warns_on_a_nonzero_exit(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(study_runner, "OUT_DIR", tmp_path)
    monkeypatch.setattr(study_runner, "_header", lambda name, argv: "HEADER\n")
    monkeypatch.setattr(study_runner.subprocess, "Popen",
                        lambda *a, **k: _FakePopen(["gate crashed\n"], 3))
    latest = tmp_path / "fake_study-latest.txt"
    latest.write_text("SENTINEL: previous good run")

    rc, out_path = study_runner.run_one("fake_study", [], dry_run=False)

    assert rc == 3
    # The stamped transcript for this attempt is written for debugging...
    assert out_path.exists()
    assert "gate crashed" in out_path.read_text()
    # ...but the canonical -latest.txt that the map/charts/study_review quote
    # is left exactly as it was before this failed attempt.
    assert latest.read_text() == "SENTINEL: previous good run"
    err = capsys.readouterr().err
    assert "*** fake_study FAILED (exit 3)" in err


# ───────────────────────── wiring into main()'s run loop ────────────────────

def test_main_renders_charts_after_a_successful_run(monkeypatch):
    calls = []
    monkeypatch.setattr(study_runner, "run_one",
                        lambda name, extra, dry_run=False: (0, study_runner.OUT_DIR / f"{name}-latest.txt"))
    monkeypatch.setattr(study_runner, "_render_charts", lambda name, argv: calls.append((name, argv)))
    monkeypatch.setattr(map_build, "refresh_quietly", lambda *a, **k: None)

    rc = study_runner.main(["run", "account_sim", "--no-handoff"])

    assert rc == 0
    assert calls == [("account_sim", [])]


def test_main_skips_the_chart_render_when_the_study_run_failed(monkeypatch):
    """A gate-failed run leaves whatever chart page already existed alone —
    there is no new, valid report to draw it from."""
    calls = []
    monkeypatch.setattr(study_runner, "run_one",
                        lambda name, extra, dry_run=False: (1, study_runner.OUT_DIR / f"{name}-latest.txt"))
    monkeypatch.setattr(study_runner, "_render_charts", lambda name, argv: calls.append((name, argv)))
    monkeypatch.setattr(map_build, "refresh_quietly", lambda *a, **k: None)

    rc = study_runner.main(["run", "account_sim", "--no-handoff"])

    assert rc == 1
    assert calls == []


def test_main_passes_the_structure_universe_flag_through_to_the_chart_render(monkeypatch):
    """The flag lives in `extra`, merged the same way the study subprocess
    itself receives it — the chart render must see the same merged argv."""
    calls = []
    monkeypatch.setattr(study_runner, "run_one",
                        lambda name, extra, dry_run=False: (0, study_runner.OUT_DIR / f"{name}-latest.txt"))
    monkeypatch.setattr(study_runner, "_render_charts", lambda name, argv: calls.append((name, argv)))
    monkeypatch.setattr(map_build, "refresh_quietly", lambda *a, **k: None)

    rc = study_runner.main(["run", "account_sim", "--no-handoff", "--structure-universe"])

    assert rc == 0
    assert calls == [("account_sim", ["--structure-universe"])]


def test_main_does_not_render_charts_for_a_study_with_no_chart_module(monkeypatch):
    """`_render_charts` is still called (it is a no-op for these studies) —
    this pins that the no-op path, not a skip in main(), is what's doing the
    work, matching bear_deploy's absence from CHART_MODULES."""
    calls = []
    monkeypatch.setattr(study_runner, "run_one",
                        lambda name, extra, dry_run=False: (0, study_runner.OUT_DIR / f"{name}-latest.txt"))
    monkeypatch.setattr(study_runner, "_render_charts", lambda name, argv: calls.append((name, argv)))
    monkeypatch.setattr(map_build, "refresh_quietly", lambda *a, **k: None)

    rc = study_runner.main(["run", "bear_deploy", "--no-handoff"])

    assert rc == 0
    assert calls == [("bear_deploy", [])]


# ─────────────────────── main()'s stderr failure summary ────────────────────

def test_main_prints_a_stderr_failure_summary_when_a_study_fails(monkeypatch, capsys):
    monkeypatch.setattr(study_runner, "run_one",
                        lambda name, extra, dry_run=False: (2, study_runner.OUT_DIR / f"{name}-latest.txt"))
    monkeypatch.setattr(study_runner, "_render_charts", lambda name, argv: None)
    monkeypatch.setattr(map_build, "refresh_quietly", lambda *a, **k: None)

    rc = study_runner.main(["run", "bear_deploy", "--no-handoff"])

    assert rc == 2
    err = capsys.readouterr().err
    assert "*** STUDY FAILURES:" in err
    assert "bear_deploy (exit 2)" in err


def test_main_prints_no_failure_summary_when_every_study_succeeds(monkeypatch, capsys):
    monkeypatch.setattr(study_runner, "run_one",
                        lambda name, extra, dry_run=False: (0, study_runner.OUT_DIR / f"{name}-latest.txt"))
    monkeypatch.setattr(study_runner, "_render_charts", lambda name, argv: None)
    monkeypatch.setattr(map_build, "refresh_quietly", lambda *a, **k: None)

    rc = study_runner.main(["run", "bear_deploy", "--no-handoff"])

    assert rc == 0
    err = capsys.readouterr().err
    assert "STUDY FAILURES" not in err


def test_main_lists_every_failed_study_with_its_own_exit_code_and_still_returns_the_max_rc(monkeypatch, capsys):
    """With --all, one bad study among several must not get lost — each
    failure is named individually, and the return code is the max across
    all of them (matching the existing "returns max rc" contract)."""
    monkeypatch.setattr(study_runner, "discover", lambda: {"study_a": "a", "study_b": "b"})
    rcs = {"study_a": 1, "study_b": 0}
    monkeypatch.setattr(study_runner, "run_one",
                        lambda name, extra, dry_run=False: (rcs[name], study_runner.OUT_DIR / f"{name}-latest.txt"))
    monkeypatch.setattr(study_runner, "_render_charts", lambda name, argv: None)
    monkeypatch.setattr(map_build, "refresh_quietly", lambda *a, **k: None)

    rc = study_runner.main(["run", "--all", "--no-handoff"])

    assert rc == 1
    err = capsys.readouterr().err
    assert "*** STUDY FAILURES: study_a (exit 1)" in err
    assert "study_b" not in err
