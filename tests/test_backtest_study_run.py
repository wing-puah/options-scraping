"""Tests for scripts/backtest_study/run.py's post-run chart refresh.

Mirrors tests/test_study_review.py's approach: stub out anything that would
shell out or touch real study output (a real chart render, a real study
subprocess) and exercise the deterministic wiring around it. No real study
run, no real `scripts.study_charts` render, no writes to the tracked
`docs/` pages happen here — see the manual end-to-end check noted in the
session's task instead for that.
"""
from __future__ import annotations

import pytest

import scripts.study_map.build as map_build
import scripts.study_map.catalog as smc
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


def test_render_charts_points_at_the_compounding_positions_csv_for_that_arm(monkeypatch):
    """The compounding arm is a different SIZING basis over the same book, so
    its page must be drawn from its own export — never from the frozen one."""
    fake = _FakeChartModule(0)
    monkeypatch.setattr(study_runner.importlib, "import_module", lambda name: fake)

    study_runner._render_charts("account_sim", ["--compounding"],
                                ["fake.chart.module"])

    want = str(study_runner.OUT_DIR / "account_sim-positions-compounding-latest.csv")
    assert fake.calls == [["--positions", want]]


def test_render_charts_orders_compounding_before_structure_in_the_stem(monkeypatch):
    """Both axes at once. The order is the study's own (`sizing` then
    `universe`), so `-structure` stays the suffix that names the widened
    universe on either sizing basis."""
    fake = _FakeChartModule(0)
    monkeypatch.setattr(study_runner.importlib, "import_module", lambda name: fake)

    study_runner._render_charts(
        "account_sim", ["--compounding", "--structure-universe"],
        ["fake.chart.module"])

    want = str(study_runner.OUT_DIR
               / "account_sim-positions-compounding-structure-latest.csv")
    assert fake.calls == [["--positions", want]]


def test_render_charts_renders_only_the_modules_it_was_handed(monkeypatch, capsys):
    """An explicit module list overrides CHART_MODULES — that is how the
    compounding arm renders ITS page and does not redraw the frozen book's."""
    seen = []
    fake = _FakeChartModule(0)
    monkeypatch.setitem(study_runner.CHART_MODULES, "account_sim",
                        ["fake.frozen.page", "fake.frozen.regime"])
    monkeypatch.setattr(study_runner.importlib, "import_module",
                        lambda name: seen.append(name) or fake)

    study_runner._render_charts("account_sim", ["--compounding"],
                                ["fake.compounding.page"])

    assert seen == ["fake.compounding.page"]


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
    monkeypatch.setattr(study_runner, "_header",
                        lambda name, argv, module=None: "HEADER\n")
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
    monkeypatch.setattr(study_runner, "_header",
                        lambda name, argv, module=None: "HEADER\n")
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


# ─────────────────────────── designed refusals ───────────────────────────────
#
# A study can declare exit codes that mean "I deliberately declined to
# produce a result" (a pre-registered gate not met, a guard refusing to
# compare a book against itself) rather than "something broke". v4_bridge is
# the one study that declares this today.

def test_refusal_codes_reads_v4_bridges_real_declaration():
    assert study_runner._refusal_codes("v4_bridge") == frozenset({2, 3})


def test_refusal_codes_is_empty_for_a_study_with_no_declaration():
    """bear_deploy declares no DESIGNED_REFUSAL_EXIT_CODES — every non-zero
    exit of its is a real failure, unchanged."""
    assert study_runner._refusal_codes("bear_deploy") == frozenset()


def test_refusal_codes_is_empty_for_an_unknown_name():
    assert study_runner._refusal_codes("not_a_real_study_xyz") == frozenset()


def test_run_one_promotes_latest_and_notes_a_refusal_on_a_declared_exit_code(
        monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(study_runner, "OUT_DIR", tmp_path)
    monkeypatch.setattr(study_runner, "_header",
                        lambda name, argv, module=None: "HEADER\n")
    monkeypatch.setattr(study_runner.subprocess, "Popen",
                        lambda *a, **k: _FakePopen(["GATE NOT MET\n"], 2))

    rc, out_path = study_runner.run_one("fake_study", [], dry_run=False,
                                        refusal_codes=frozenset({2, 3}))

    assert rc == 2
    latest = tmp_path / "fake_study-latest.txt"
    # Unlike a real failure, a declared refusal's report IS promoted — the
    # gate message is the study's current, correct, quotable status.
    assert latest.exists()
    assert latest.read_text() == out_path.read_text()
    err = capsys.readouterr().err
    assert "DESIGNED REFUSAL" in err
    assert "FAILED" not in err


def test_run_one_still_fails_on_an_exit_code_outside_the_declared_set(
        monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(study_runner, "OUT_DIR", tmp_path)
    monkeypatch.setattr(study_runner, "_header",
                        lambda name, argv, module=None: "HEADER\n")
    monkeypatch.setattr(study_runner.subprocess, "Popen",
                        lambda *a, **k: _FakePopen(["boom\n"], 1))
    latest = tmp_path / "fake_study-latest.txt"
    latest.write_text("SENTINEL: previous good run")

    rc, out_path = study_runner.run_one("fake_study", [], dry_run=False,
                                        refusal_codes=frozenset({2, 3}))

    assert rc == 1
    assert latest.read_text() == "SENTINEL: previous good run"
    err = capsys.readouterr().err
    assert "*** fake_study FAILED (exit 1)" in err


def test_main_designed_refusal_is_not_a_failure_and_does_not_fail_the_command(
        monkeypatch, capsys):
    """v4_bridge's real DESIGNED_REFUSAL_EXIT_CODES = {2, 3}; a stubbed exit 3
    must be reported as REFUSED, not FAILED, and must not make main() return
    non-zero — that is the whole point of declaring it."""
    monkeypatch.setattr(study_runner, "discover", lambda: {"v4_bridge": "doc"})
    _stub_run_one(monkeypatch, lambda stem: 3)
    _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "v4_bridge", "--no-handoff"])

    assert rc == 0
    captured = capsys.readouterr()
    assert "DESIGNED REFUSALS (not failures): v4_bridge (exit 3)" in captured.out
    assert "STUDY FAILURES" not in captured.err


def test_main_still_fails_v4_bridge_on_an_undeclared_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(study_runner, "discover", lambda: {"v4_bridge": "doc"})
    _stub_run_one(monkeypatch, lambda stem: 1)
    _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "v4_bridge", "--no-handoff"])

    assert rc == 1
    err = capsys.readouterr().err
    assert "*** STUDY FAILURES: v4_bridge (exit 1)" in err


def test_main_all_worst_real_failure_wins_even_alongside_a_refusal(monkeypatch, capsys):
    """A refusal must not mask an actual failure elsewhere in `--all`."""
    monkeypatch.setattr(study_runner, "discover",
                        lambda: {"v4_bridge": "doc", "bear_deploy": "doc"})
    _stub_run_one(monkeypatch, lambda stem: 3 if stem == "v4_bridge" else 1)
    _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "--all", "--no-handoff"])

    assert rc == 1
    err = capsys.readouterr().err
    assert "bear_deploy (exit 1)" in err
    assert "v4_bridge" not in err  # the refusal is not in the FAILURES line


# ─────────────────────────────── retirement ──────────────────────────────────
#
# A study whose inputs are gone for good is marked `retired=` in
# scripts.study_map.catalog. `run --all` excludes it from the bulk run but a
# `run <name>` still runs it directly, with a printed notice.

def test_main_all_skips_a_retired_study_but_runs_the_rest(monkeypatch, capsys):
    monkeypatch.setattr(study_runner, "discover",
                        lambda: {"study_a": "a", "study_b": "b"})
    monkeypatch.setattr(smc, "retired_studies",
                        lambda: {"study_a": "gone — inputs unrecoverable"})
    runs = _stub_run_one(monkeypatch, lambda stem: 0)
    _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "--all", "--no-handoff"])

    assert rc == 0
    assert runs == [("study_b", [], "study_b")]
    out = capsys.readouterr().out
    assert "SKIPPING study_a (retired): gone — inputs unrecoverable" in out


def test_main_runs_a_retired_study_directly_with_a_notice(monkeypatch, capsys):
    monkeypatch.setattr(study_runner, "discover", lambda: {"study_a": "a"})
    monkeypatch.setattr(smc, "retired_studies",
                        lambda: {"study_a": "gone — inputs unrecoverable"})
    runs = _stub_run_one(monkeypatch, lambda stem: 0)
    _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "study_a", "--no-handoff"])

    assert rc == 0
    assert runs == [("study_a", [], "study_a")]
    out = capsys.readouterr().out
    assert "NOTE: study_a is RETIRED" in out
    assert "gone — inputs unrecoverable" in out
    assert "Running anyway because it was named explicitly" in out


def test_catalogs_retired_studies_names_exactly_the_two_from_part_b():
    """Pins the actual retirement, not just the mechanism: combined_exit_study
    and underlying_exit_study are the two studies whose scratch inputs are
    gone for good (config/backtest-tuning/next-steps.md §0c(B))."""
    assert set(smc.retired_studies()) == {"combined_exit_study", "underlying_exit_study"}


def test_run_list_shows_the_retirement_notice_as_the_one_line_summary(capsys):
    """discover()'s summary is the module docstring's first line — retiring a
    study rewrites that line, so `list` surfaces the retired status without
    any extra machinery."""
    study_runner.main(["list"])
    out = capsys.readouterr().out
    assert "combined_exit_study" in out
    for line in out.splitlines():
        if line.strip().startswith("combined_exit_study"):
            assert "RETIRED" in line


# ──────────────────────────── extra arms (arm_plan) ─────────────────────────
#
# `account_sim` declares one: the post-hoc compounding sensitivity, run as a
# SECOND invocation of the same module inside one `run account_sim`, filed
# under its own report stem so it can never overwrite the frozen book's.

FROZEN_CHARTS = ("scripts.study_charts.account_sim", "scripts.study_charts.regime")
COMPOUNDING_CHARTS = ("scripts.study_charts.compounding",)


def test_arm_plan_runs_the_frozen_book_then_the_compounding_arm():
    plan = study_runner.arm_plan("account_sim", [])
    assert plan == [
        ("account_sim", [], FROZEN_CHARTS),
        ("account_sim-compounding", ["--compounding"], COMPOUNDING_CHARTS),
    ]


def test_arm_plan_carries_the_callers_own_flags_into_every_arm():
    plan = study_runner.arm_plan("account_sim", ["--structure-universe"])
    assert [stem for stem, _a, _c in plan] == ["account_sim", "account_sim-compounding"]
    assert [args for _s, args, _c in plan] == [
        ["--structure-universe"],
        ["--structure-universe", "--compounding"],
    ]


def test_arm_plan_runs_one_arm_when_the_caller_asked_for_that_arm_itself():
    """`run account_sim -- --compounding` means "that basis, alone" — running
    the arm again would just re-do it under a second stem."""
    plan = study_runner.arm_plan("account_sim", ["--compounding"])
    assert plan == [("account_sim", ["--compounding"], FROZEN_CHARTS)]


@pytest.mark.parametrize("flag", study_runner.SINGLE_ARM_FLAGS)
def test_arm_plan_runs_one_arm_for_a_gates_only_or_selftest_run(flag):
    """Every arm runs the SAME gates on the same frozen basis (G1-G4 are pinned
    there), so a second gates-only pass prints nothing new."""
    plan = study_runner.arm_plan("account_sim", [flag])
    assert plan == [("account_sim", [flag], FROZEN_CHARTS)]


def test_arm_plan_is_a_single_arm_for_a_study_with_none_declared():
    assert study_runner.arm_plan("bear_deploy", []) == [("bear_deploy", [], ())]


# ───────────────────────── wiring into main()'s run loop ────────────────────

def _stub_run_one(monkeypatch, rc_for):
    """Record every `run_one` invocation; `rc_for(stem)` gives its exit code."""
    runs = []

    def _run_one(name, extra, dry_run=False, stem=None, refusal_codes=frozenset()):
        stem = stem or name
        runs.append((name, list(extra), stem))
        return rc_for(stem), study_runner.OUT_DIR / f"{stem}-latest.txt"

    monkeypatch.setattr(study_runner, "run_one", _run_one)
    monkeypatch.setattr(map_build, "refresh_quietly", lambda *a, **k: None)
    return runs


def _stub_charts(monkeypatch):
    calls = []
    monkeypatch.setattr(study_runner, "_render_charts",
                        lambda name, argv, modules=None: calls.append((name, argv, modules)))
    return calls


def test_main_runs_both_arms_of_account_sim_in_one_command(monkeypatch):
    """The whole point: one `run account_sim` prints BOTH bases, each under its
    own report stem."""
    runs = _stub_run_one(monkeypatch, lambda stem: 0)
    _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "account_sim", "--no-handoff"])

    assert rc == 0
    assert runs == [
        ("account_sim", [], "account_sim"),
        ("account_sim", ["--compounding"], "account_sim-compounding"),
    ]


def test_main_renders_charts_after_a_successful_run(monkeypatch):
    _stub_run_one(monkeypatch, lambda stem: 0)
    calls = _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "account_sim", "--no-handoff"])

    assert rc == 0
    assert calls == [
        ("account_sim", [], FROZEN_CHARTS),
        ("account_sim", ["--compounding"], COMPOUNDING_CHARTS),
    ]


def test_main_renders_only_the_compounding_page_for_the_compounding_arm(monkeypatch):
    """The arm must not redraw the frozen book's two tracked pages from
    compounded numbers — that is the failure this whole change removes."""
    _stub_run_one(monkeypatch, lambda stem: 0)
    calls = _stub_charts(monkeypatch)

    study_runner.main(["run", "account_sim", "--no-handoff"])

    by_arm = {("compounding" if "--compounding" in argv else "frozen"): modules
              for _n, argv, modules in calls}
    assert by_arm["frozen"] == FROZEN_CHARTS
    assert by_arm["compounding"] == COMPOUNDING_CHARTS


def test_main_skips_the_chart_render_when_the_study_run_failed(monkeypatch):
    """A gate-failed run leaves whatever chart page already existed alone —
    there is no new, valid report to draw it from."""
    _stub_run_one(monkeypatch, lambda stem: 1)
    calls = _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "account_sim", "--no-handoff"])

    assert rc == 1
    assert calls == []


def test_main_keeps_the_good_arm_when_the_other_arm_fails(monkeypatch, capsys):
    """A failing arm must not take the other arm's report or page down with it,
    and the command still exits with the worst arm's code."""
    _stub_run_one(monkeypatch, lambda stem: 1 if stem.endswith("-compounding") else 0)
    calls = _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "account_sim", "--no-handoff"])

    assert rc == 1
    assert calls == [("account_sim", [], FROZEN_CHARTS)]
    err = capsys.readouterr().err
    assert "account_sim-compounding (exit 1)" in err


def test_main_passes_the_structure_universe_flag_through_to_the_chart_render(monkeypatch):
    """The flag lives in `extra`, merged the same way the study subprocess
    itself receives it — the chart render must see the same merged argv, on
    BOTH arms."""
    _stub_run_one(monkeypatch, lambda stem: 0)
    calls = _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "account_sim", "--no-handoff", "--structure-universe"])

    assert rc == 0
    assert calls == [
        ("account_sim", ["--structure-universe"], FROZEN_CHARTS),
        ("account_sim", ["--structure-universe", "--compounding"], COMPOUNDING_CHARTS),
    ]


def test_main_runs_a_single_arm_when_the_compounding_flag_was_passed_explicitly(monkeypatch):
    runs = _stub_run_one(monkeypatch, lambda stem: 0)
    _stub_charts(monkeypatch)

    study_runner.main(["run", "account_sim", "--no-handoff", "--compounding"])

    assert runs == [("account_sim", ["--compounding"], "account_sim")]


@pytest.mark.parametrize("flag", study_runner.SINGLE_ARM_FLAGS)
def test_main_runs_a_single_arm_for_gates_only_and_selftest_runs(monkeypatch, flag):
    runs = _stub_run_one(monkeypatch, lambda stem: 0)
    _stub_charts(monkeypatch)

    study_runner.main(["run", "account_sim", "--no-handoff", flag])

    assert runs == [("account_sim", [flag], "account_sim")]


def test_main_dry_run_prints_the_planned_command_for_every_arm(monkeypatch, capsys):
    monkeypatch.setattr(map_build, "refresh_quietly", lambda *a, **k: None)

    rc = study_runner.main(["run", "account_sim", "--no-handoff", "--dry-run"])

    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("[dry-run]") == 2
    assert "account_sim-compounding-" in out       # the arm's own stamped report
    assert "--compounding" in out


def test_main_does_not_render_charts_for_a_study_with_no_chart_module(monkeypatch):
    """`_render_charts` is still called (it is a no-op for these studies) —
    this pins that the no-op path, not a skip in main(), is what's doing the
    work, matching bear_deploy's absence from CHART_MODULES."""
    _stub_run_one(monkeypatch, lambda stem: 0)
    calls = _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "bear_deploy", "--no-handoff"])

    assert rc == 0
    assert calls == [("bear_deploy", [], ())]


# ─────────────────────── main()'s stderr failure summary ────────────────────

def test_main_prints_a_stderr_failure_summary_when_a_study_fails(monkeypatch, capsys):
    _stub_run_one(monkeypatch, lambda stem: 2)
    _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "bear_deploy", "--no-handoff"])

    assert rc == 2
    err = capsys.readouterr().err
    assert "*** STUDY FAILURES:" in err
    assert "bear_deploy (exit 2)" in err


def test_main_prints_no_failure_summary_when_every_study_succeeds(monkeypatch, capsys):
    _stub_run_one(monkeypatch, lambda stem: 0)
    _stub_charts(monkeypatch)

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
    _stub_run_one(monkeypatch, lambda stem: rcs[stem])
    _stub_charts(monkeypatch)

    rc = study_runner.main(["run", "--all", "--no-handoff"])

    assert rc == 1
    err = capsys.readouterr().err
    assert "*** STUDY FAILURES: study_a (exit 1)" in err
    assert "study_b" not in err
