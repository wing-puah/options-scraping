"""Study runner — run a tuning study, capture its output, hand it off for write-up.

Every study in this package prints a long plain-text report to stdout and is
meant to be read once, argued about, and then condensed into an addendum in
`research/current.md`. Before this runner, that meant remembering
each study's invocation, remembering to `tee` it somewhere, and remembering
which Sheets export the numbers rested on. All three were remembered wrong at
least once.

    python -m scripts.backtest_study list
    python -m scripts.backtest_study run bear_deploy
    python -m scripts.backtest_study run exit_mechanism_study --side credit
    python -m scripts.backtest_study run --all

The run writes `backtests/study_output/<name>-<stamp>.txt` plus a stable
`<name>-latest.txt`, both prefixed with a provenance header (git sha, dirty
flag, the exact argv, and the row counts / mtimes of the input exports). It
then prints the path to paste into Claude for the write-up. `<name>-latest.txt`
only ever holds a run that is CURRENT AND TRUE: a clean run, or a designed
refusal (which is the study's correct status right now — see below). A real
failure (bad flag, crash) keeps its stamped transcript for debugging and
DELETES `-latest.txt`, so the map, the chart pages and `study_review
--skip-run` quote nothing rather than quoting a run that no longer reproduces.

A study may also declare extra ARMS (`STUDY_ARMS`) — the same module run again
with one flag flipped, filed under its own report stem, positions CSV and chart
pages. `run account_sim` therefore prints both the frozen, path-independent book
and the post-hoc compounding sensitivity in one command, with neither arm able
to overwrite the other's artifacts. The exit code is the worst arm's, real
failures only — see "Designed refusals" below.

Retired studies. A study whose inputs are gone for good (gitignored scratch,
deleted, unrecoverable) may be marked `retired=` in `scripts.study_map.catalog`
rather than deleted: `run --all` then excludes it from the bulk run and prints
one notice line per skip, while `run <name>` still runs it directly, printing a
notice first, for anyone who wants to see it fail on the missing file with
their own eyes. Nothing is retired today. The two studies that were
(`combined_exit_study`, `underlying_exit_study`) were DELETED on 2026-09-05
once their verdicts were recorded in `research/study-map.md`; the mechanism is
kept for a future retirement where the module is still worth reading.

Designed refusals. Some studies exit non-zero ON PURPOSE — a pre-registered
calibration or power gate not cleared, or (like `v4_bridge.py`) a guard that
refuses to compare a book against itself. `README.md` calls this out: "a
non-zero exit is often the correct answer." Such a study declares which exit
codes mean this by setting a module-level `DESIGNED_REFUSAL_EXIT_CODES` (a
set of ints) — see `v4_bridge.py` for the convention. `run --all` reads it
(via `ast`, the same no-import approach as `discover()`, since two studies do
real work at import time) and reports a matching exit code as REFUSED, not
FAILED: distinct in the run-by-run status line, excluded from the `***
STUDY FAILURES ***` tally and from `main()`'s own non-zero return, and its
report IS promoted to `-latest.txt` same as a clean run — the refusal message
is itself the current, correct, quotable status, not something to discard in
favour of a stale prior report. A study with no `DESIGNED_REFUSAL_EXIT_CODES`
(the default) has every non-zero exit treated as a real failure, unchanged.

A real FAILURE deletes `-latest.txt` outright, leaving the study with no current
report. That is deliberate and it is a change of policy (2026-08-15): the report
used to be left at the previous good run, which meant a stale report and a
current one were indistinguishable on disk — see `run_one` for what that cost.
The two thin-era / era-mismatch refusals in `lib/era.py` are what make this
safe, by moving the common non-zero exit into the promoted branch above.

The `--era` flag picks which export set the whole run reads (`STUDY_ERA`), and
every header names the era it ran on. `lib/era.py` has the why.

It also re-renders `site/study-map.html`, so the readable one-page map of the
whole package always quotes the newest report. That step is best-effort: the
report is the valuable output, and a broken map must never turn a good run into
a failed command.

For studies that have one, it also re-renders the HTML chart pages under
`scripts/study_charts/` (today: `account_sim` only). Unlike the map, a chart
failure is never swallowed quietly — the chart pipeline's own contract is
reconcile-against-the-report-or-write-nothing, and a page that silently kept
showing a previous run's numbers is exactly the bug this closes (an operator
who changed a config, reran the study, and got a chart page that never moved).
See `_render_charts` below for the exact failure-visibility rule. A DESIGNED
REFUSAL renders no charts at all and says so as a SKIP: a refusal report has no
numbers in it to draw, so calling the chart layer would only produce a "chart
refreshed" line about a page that was not redrawn.

Outputs live under `backtests/` because they are data, not source — the whole
tree is gitignored scratch. The code lives here, under `scripts/`.
"""
from __future__ import annotations

import argparse
import ast
import csv
import importlib
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era as era_mod  # noqa: E402

PKG = "scripts.backtest_study"
STUDY_DIR = Path(__file__).resolve().parent
OUT_DIR = ROOT / "backtests" / "study_output"

# Studies with an HTML chart-rendering pipeline under scripts/study_charts/.
# A study with no entry here gets no chart render attempt — most studies have
# no chart page, and that is not an error. Each module is a page that shares
# scripts/study_charts/cli.py's arm-pairing and reconcile-or-write-nothing
# rules; account_sim currently has two (the feasibility readout + the by-regime
# cut), both drawn from the same run's report + positions CSV.
CHART_MODULES = {
    "account_sim": ["scripts.study_charts.account_sim", "scripts.study_charts.regime"],
}


# ── extra arms ───────────────────────────────────────────────────────────────
#
# Some studies have a SECOND basis worth printing every time, not a different
# study: same module, same config, one flag flipped. `account_sim`'s
# compounding sensitivity is the case this exists for — it used to be a copied
# config file the operator had to remember to run, and running it silently
# overwrote the frozen book's positions CSV and chart pages, so the tracked
# artifacts could end up describing a post-hoc arm nobody meant to publish.
#
# So an arm is a first-class part of one `run <name>`: its own stamped report
# and `-latest` promotion under its own STEM, its own positions CSV (the study
# names that itself, keyed off the same flag), and its own chart modules. A
# failing arm therefore cannot clobber the other arm's `-latest`, and the run's
# exit code is the worst arm's.
#
# An arm is NOT run when it would be wrong or redundant: when the caller already
# passed its own flag (they asked for that arm alone), or when the run is a
# gates-only / gate-selftest run, where the arm would re-run the same gates on
# the same frozen basis and print nothing else.

SINGLE_ARM_FLAGS = ("--gates-only", "--selftest-gates")


@dataclass(frozen=True)
class Arm:
    """One extra invocation of a study module within a single `run <name>`."""

    suffix: str                     # report stem becomes `<name>-<suffix>`
    args: tuple[str, ...]           # appended to the caller's own extra args
    charts: tuple[str, ...] = ()    # chart modules for THIS arm only


STUDY_ARMS = {
    "account_sim": (
        Arm(suffix="compounding",
            args=("--compounding",),
            charts=("scripts.study_charts.compounding",)),
    ),
    # The credit side was invisible to `run --all` until 2026-08-24 — the study
    # requires --side, the runner passed none, and only the debit default ever
    # ran. Filed under its own stem so it can never clobber the debit report.
    "exit_mechanism_study": (
        Arm(suffix="credit", args=("--side", "credit")),
    ),
}

# Arms the CALLER asks for by flag, which rename the report stem instead of
# adding a second invocation. `--live-select` is one: it changes who SELECTS, so
# its book is not a sensitivity of the frozen one and must not be filed as it.
# Two things follow, and both matter. It gets its own `-latest.txt` — filing it
# under `account_sim-latest.txt` would overwrite the report every recorded
# conclusion in research/current.md rests on. And it suppresses
# the extra arms — a `--live-select --compounding` pass nobody asked for would
# land on `account_sim-compounding-latest.txt` and quietly replace the
# compounding sensitivity with a differently-selected book.
CALLER_ARMS = {
    "account_sim": (("--live-select", "live-select"),),
}

# ── where the studies live ───────────────────────────────────────────────────
#
# A study IS a module in a family folder. That is the whole rule, and it is a
# POSITIVE one: before 2026-08-15 this was a hand-maintained `INFRA` blocklist
# of names to skip, so adding a helper module to the package silently made it a
# "study" — discovered, listed, and then failing the catalog test with no hint
# as to why. Now a helper goes in `lib/` and is never a candidate.
#
# The folders are ORDERED, and the order is real: it is the order a play moves
# through the system — pick it, manage it, wrap it, fund it. It is the same
# order `scripts/study_map/catalog.py::FAMILIES` renders on the map, and the
# `fN_` prefix is what makes `ls` agree with both (`f` only because a package
# name may not begin with a digit — the same reason journal steps are `sNN_`).
FAMILY_DIRS = ("f1_selection", "f2_management", "f3_structure", "f4_deployment")

# `lib/` modules the runner will still RUN. Only `book`, whose `--validate`
# diagnostics table is the standard pre-flight before any study; the rest are
# import-only. Listing it here rather than in a family folder keeps the rule
# above true: it has no verdict in the catalog, so it is not a study.
RUNNABLE_LIB = {"book"}

# Kept for `scripts/study_map/catalog.py`, which cross-checks its own INFRA
# prose against this: every module that is NOT a study. Derived from the
# directory now, so the two can no longer drift by hand.
INFRA = {"run"} | {p.stem for p in (Path(__file__).resolve().parent / "lib").glob("*.py")
                   if not p.stem.startswith("__")}

# Flags a study needs but has no sensible argparse default for. Applied only
# when the caller did not pass that flag themselves.
DEFAULT_ARGS = {
    "exit_mechanism_study": ["--side", "debit"],
    "book": ["--validate"],
}

# Inputs whose identity decides whether two runs are comparable. Reported in
# every header so a write-up can never silently attribute numbers to the wrong
# export (this has happened — see current.md on the 07-22 vs 08-08 books, and
# again on 08-15 when a re-export turned the bare filenames from v3 into v4).
#
# Row counts and mtimes were not enough that second time: both moved, and both
# look like an ordinary refresh. The header now names the detected ERA of each
# export, which is the thing that actually changed. Paths are resolved per-era,
# so a `--era v3` run reports the files it really read.
MECH_TABLE_REL = "backtests/mech_regime/spy_vix_daily_full.csv"


def _input_csvs(era: str) -> list[str]:
    """Repo-relative input paths for `era`, in report order."""
    paths = era_mod.resolve_paths(era)
    return [str(paths[k].relative_to(ROOT)) for k in ("results", "proxy", "analysis")] + \
        [MECH_TABLE_REL]


def study_paths() -> dict[str, Path]:
    """`{study_name: module file}` — every runnable name, in family order.

    A study is a module in a family folder (plus `lib/book.py`, see
    `RUNNABLE_LIB`). The name is the bare STEM, never the dotted path: it is
    what `run <name>` takes, what the report is filed as
    (`backtests/study_output/<name>-latest.txt`), what `study_map.catalog` keys
    on, and what a hundred lines of `research/current.md` cite. Moving a study
    between families must therefore never rename it — the folder is navigation,
    the stem is identity.
    """
    out: dict[str, Path] = {}
    for family in FAMILY_DIRS:
        for path in sorted((STUDY_DIR / family).glob("*.py")):
            if not path.stem.startswith("__"):
                out[path.stem] = path
    for stem in sorted(RUNNABLE_LIB):
        out[stem] = STUDY_DIR / "lib" / f"{stem}.py"
    return out


def module_of(name: str) -> str:
    """The dotted module path `run <name>` executes, e.g.
    `scripts.backtest_study.f4_deployment.account_sim`.

    An unknown name falls back to the package root rather than raising.
    Nothing reaches here with one in practice — `main()` rejects unknown names
    against `discover()` before any run starts — so the fallback exists for
    callers that drive `run_one` directly with a stub name and a faked
    subprocess (the report-promotion tests). If one ever did reach the
    subprocess, it fails as a plain ModuleNotFoundError, exactly as it did when
    every study sat flat in this directory.
    """
    path = study_paths().get(name)
    return f"{PKG}.{path.parent.name}.{name}" if path else f"{PKG}.{name}"


def discover() -> dict[str, str]:
    """`{study_name: one-line summary}`, summary read from the module docstring.

    Parsed with `ast`, never imported: two studies (`mech_regime_recut`,
    `regime_gap_reread`) do their work at module level, so importing them to
    read a docstring would run the whole study.
    """
    out = {}
    for name, path in study_paths().items():
        doc = ast.get_docstring(ast.parse(path.read_text())) or ""
        lines = [ln.strip() for ln in doc.strip().splitlines() if ln.strip()]
        out[name] = lines[0] if lines else "(no docstring)"
    return out


def _refusal_codes(name: str) -> frozenset[int]:
    """Exit codes `name` declares as a DESIGNED refusal — see the "Designed
    refusals" note in this module's docstring and `v4_bridge.py`'s
    `DESIGNED_REFUSAL_EXIT_CODES` for the worked example.

    Parsed with `ast`, never imported, for the same reason as `discover()`:
    two studies do real work at import time, so importing every study just to
    read one constant would run them.

    The era refusals (`lib/era.py`: thin era, era mismatch) are added to EVERY
    study's set, declared or not. They are not a study's private convention —
    they are emitted by shared infrastructure that every study inherits the
    moment it calls `load_book`, so requiring twenty modules to restate the
    same two integers would just be a rule waiting to be forgotten by the
    twenty-first. A study still declares codes of its OWN meaning here.
    """
    path = study_paths().get(name)
    if path is None or not path.exists():
        return era_mod.DESIGNED_REFUSAL_EXIT_CODES
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "DESIGNED_REFUSAL_EXIT_CODES"
                   for t in node.targets):
            continue
        try:
            return frozenset(ast.literal_eval(node.value)) | era_mod.DESIGNED_REFUSAL_EXIT_CODES
        except (ValueError, TypeError):
            return era_mod.DESIGNED_REFUSAL_EXIT_CODES
    # No declaration of its own — still inherits the era refusals.
    return era_mod.DESIGNED_REFUSAL_EXIT_CODES


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


def _input_inventory(era: str) -> list[str]:
    rows = []
    for rel in _input_csvs(era):
        p = ROOT / rel
        if not p.exists():
            rows.append(f"  MISSING  {rel}")
            continue
        with p.open(newline="") as fh:
            # CSV ROWS minus header — never a line count: daily_price_csv
            # carries embedded newlines that inflate line counts ~4x (the
            # `wc -l` hazard, current.md §2026-08-14 method note).
            n = max(0, sum(1 for _ in csv.reader(fh)) - 1)
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        # Format is load-bearing: `study_charts.report.parse_provenance` matches
        # `\s+([\d,]+) rows\s+(\S+ \S+)\s+(.+)` against these lines, and
        # `clean_study_output` now leans on that parse to decide whether a cited
        # report is stale. The era goes on its own header line above rather than
        # a per-file column, which would put a non-digit ahead of the row count
        # and silently empty out `inputs`. Per-file detection is not needed here
        # anyway — `era.enforce` already refuses a half-finished re-export at
        # load time, before a report exists to record it.
        rows.append(f"  {n:>6,} rows  {mtime}  {rel}")
    return rows


def _era_line(era: str) -> str:
    """What the header records as the era: the DETECTED one, always.

    `current` is a SELECTOR, not an era — it means "the bare exports, whatever
    they hold now". Recording it verbatim would reintroduce the exact ambiguity
    this whole layer exists to remove: a v4 run and a later v5 run would both
    file themselves under "current", and `research/study-results/` keys its
    append-only sections on this string. So the alias is resolved here and
    shown alongside how it was selected.
    """
    paths = era_mod.resolve_paths(era)
    try:
        detected = era_mod.detect_era(paths["results"])
    except (OSError, ValueError):
        # An unreadable or empty export is `era.enforce`'s problem, and it will
        # refuse in a moment with a better message than a header could give.
        # Say what was ASKED for and mark it unresolved rather than guess.
        return f"{era} (UNRESOLVED — see the refusal below)"
    how = "bare exports" if era == era_mod.CURRENT else "prefixed exports"
    origin = f"{era} — {how}" if era != detected else how
    return f"{detected} ({origin})"


def _header(name: str, argv: list[str], module: str | None = None,
            era: str | None = None) -> str:
    """The provenance header. `name` is what the report is CALLED (the arm's
    stem, e.g. `account_sim-compounding`); `module` is what actually ran and
    defaults to `name` — they differ only for an extra arm, where the command
    line has to stay copy-pasteable and the arm's flag is what identifies the
    arm downstream (the chart layer reads it off this line)."""
    era = era or era_mod.requested_era()
    dirty = "dirty" if _git("status", "--porcelain") else "clean"
    lines = [
        "=" * 78,
        f"STUDY: {name}",
        "=" * 78,
        f"  run at    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  command   python -m {module_of(module or name)} {' '.join(argv)}".rstrip(),
        f"  git       {_git('rev-parse', '--short', 'HEAD')} "
        f"({_git('rev-parse', '--abbrev-ref', 'HEAD')}, working tree {dirty})",
        f"  python    {sys.version.split()[0]}",
        f"  era       {_era_line(era)}",
        "  inputs:",
        *_input_inventory(era),
        "=" * 78,
        "",
    ]
    return "\n".join(lines)


def _merge_args(name: str, extra: list[str]) -> list[str]:
    """Study defaults, minus any flag the caller supplied explicitly."""
    defaults = DEFAULT_ARGS.get(name, [])
    merged = []
    i = 0
    while i < len(defaults):
        flag = defaults[i]
        takes_value = i + 1 < len(defaults) and not defaults[i + 1].startswith("-")
        if flag not in extra:
            merged.extend(defaults[i:i + 2] if takes_value else [flag])
        i += 2 if takes_value else 1
    return merged + extra


def _render_charts(name: str, argv: list[str],
                   modules: list[str] | tuple[str, ...] | None = None) -> None:
    """Re-render `name`'s chart pages (no-op if it has none), against whichever
    arm this run's own argv shows it took.

    `modules` overrides `CHART_MODULES[name]` and is how an extra arm renders
    ITS page and only its page: the compounding arm must not redraw the frozen
    book's two pages from compounded numbers.

    Imported here, not at module scope, for the same reason as the map import
    below: nothing about running a study should depend on study_charts being
    importable.

    Failure handling is deliberately NOT the map's best-effort swallow. The
    map is a convenience index that degrades gracefully; a stale chart page
    reads as a *current* one — there is no visual difference between "this
    quotes the new run" and "this still quotes the old run" until someone
    reads the numbers wrong. So a chart failure prints a loud, impossible-to-
    miss warning naming the study, the page, and the reason, and leaves the
    process exit code alone: `study_charts.cli.run` already refuses to write
    a stale-looking page on reconcile failure (exit 1, nothing written), so
    the previous page — old but honestly old — survives untouched. The study
    report itself is valid and already on disk either way, so a chart problem
    must never be reported as a study-run failure.

    A DESIGNED REFUSAL never reaches this function — the caller prints a SKIP
    for each of the study's chart modules instead, because a refusal report has
    nothing to draw and "chart refreshed:" below would be a false statement
    about a page that was not redrawn.
    """
    modules = modules if modules is not None else CHART_MODULES.get(name)
    if not modules:
        return
    # account_sim writes one positions CSV per arm (the chart layer keys the arm
    # off the filename); point the chart pipeline at whichever one this run's
    # own argv says it just wrote, so the render pairs with the report that
    # was just written rather than the default (frozen-arm) positions file.
    # Suffix ORDER matches the study's own: compounding (sizing basis) before
    # structure (candidate universe).
    stem = "account_sim-positions"
    if "--compounding" in argv:
        stem += "-compounding"
    if "--structure-universe" in argv:
        stem += "-structure"
    positions = OUT_DIR / f"{stem}-latest.csv"
    for mod_name in modules:
        try:
            module = importlib.import_module(mod_name)
            rc = module.main(["--positions", str(positions)])
        except SystemExit as exc:
            # cli.py raises SystemExit(<message>) for setup problems (no
            # positions CSV, no matching report, wrong arm) rather than
            # returning a code — surface that message rather than collapsing
            # it to a bare "exit 1".
            if isinstance(exc.code, int):
                rc = exc.code
            else:
                print(f"\n*** CHART RENDER FAILED for {name} ({mod_name}): {exc.code} ***", file=sys.stderr)
                continue
        except Exception as exc:  # noqa: BLE001 - report it, never crash the run over a chart
            print(f"\n*** CHART RENDER FAILED for {name} ({mod_name}): {exc} ***", file=sys.stderr)
            continue
        if rc:
            print(f"\n*** CHART RENDER FAILED for {name} ({mod_name}): exit {rc} — "
                  f"its page was NOT updated and may be quoting a stale run; "
                  f"see the reconciliation output above ***", file=sys.stderr)
        else:
            print(f"  chart refreshed: {mod_name} ({positions.name})")


def run_one(name: str, extra: list[str], dry_run: bool = False,
            stem: str | None = None,
            refusal_codes: frozenset[int] = frozenset()) -> tuple[int, Path]:
    """Run study `name` and capture its report under `stem` (default `name`).

    `stem` is what an extra arm is filed as (`account_sim-compounding`): the
    module that runs is still `name`, so the two arms of one study cannot write
    over each other's stamped transcript or `-latest` report.

    `refusal_codes` are exit codes `name` declared (via
    `DESIGNED_REFUSAL_EXIT_CODES`, see this module's docstring) as a DESIGNED
    refusal rather than a failure — a non-zero exit in that set is treated
    like a clean run: `-latest.txt` IS promoted, just with a note instead of a
    FAILED warning.
    """
    stem = stem or name
    argv = _merge_args(name, extra)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = OUT_DIR / f"{stem}-{stamp}.txt"
    latest = OUT_DIR / f"{stem}-latest.txt"
    cmd = [sys.executable, "-u", "-m", module_of(name), *argv]

    if dry_run:
        print(f"[dry-run] {' '.join(cmd)}  ->  {out_path}")
        return 0, out_path

    header = _header(stem, argv, module=name)
    print(header, end="")
    t0 = time.time()
    with out_path.open("w") as fh:
        fh.write(header)
        # Tee: the operator watches it live, the file keeps it for the write-up.
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            sys.stdout.write(line)
            fh.write(line)
        rc = proc.wait()
        footer = (f"\n{'=' * 78}\nexit code {rc} after {time.time() - t0:.1f}s\n"
                  f"{'=' * 78}\n")
        fh.write(footer)
    print(footer, end="")
    if rc == 0 or rc in refusal_codes:
        # A designed refusal is a legitimate, current, quotable report — the
        # gate/guard message IS the study's correct status right now, not
        # something to hide behind a stale prior -latest.txt.
        latest.write_text(out_path.read_text())
        if rc != 0:
            # "declared or inherited", not "declared in its own": most studies
            # never name these codes — they inherit the era pair from
            # `lib/era.py` via `_refusal_codes`. Saying otherwise would send a
            # reader looking for a constant that is not in the file.
            print(f"\n*** {stem} exited {rc} — a DESIGNED REFUSAL (declared or inherited "
                  f"via DESIGNED_REFUSAL_EXIT_CODES), not a failure; {latest.name} "
                  f"promoted as usual. ***", file=sys.stderr)
    else:
        # A genuine failure DELETES the canonical report rather than leaving a
        # prior good run in place. Keeping it was the older policy, and on
        # 2026-08-15 it is what let five stale reports sit next to fourteen
        # freshly-contaminated ones with nothing on either to tell them apart:
        # the map, charts and study_review all quote `-latest.txt`, and a report
        # that no longer reproduces is worse than no report at all.
        #
        # Safe here in a way it was not before, because the COMMON non-zero exit
        # is now a designed refusal (thin era, era mismatch), which is promoted
        # by the branch above. What reaches this branch is a real bug.
        existed = latest.exists()
        latest.unlink(missing_ok=True)
        gone = f"{latest.name} DELETED" if existed else f"{latest.name} absent"
        print(f"\n*** {stem} FAILED (exit {rc}) — {gone}; the study now has NO "
              f"current report. This attempt's output is in {out_path.name} ***",
              file=sys.stderr)
    return rc, out_path


def arm_plan(name: str, extra: list[str]) -> list[tuple[str, list[str], tuple[str, ...]]]:
    """`[(report_stem, arm_extra_args, chart_modules)]` for one `run <name>`.

    Always at least the study itself. Extra arms are appended unless the caller
    asked for a single arm — either by passing that arm's own flag (they want
    that basis alone, and running it twice would just overwrite it) or by
    passing a gates-only / gate-selftest flag (every arm runs the same gates on
    the same frozen basis, so the extra arm would add nothing).

    A CALLER_ARMS flag is the third case: one invocation, filed under its own
    stem, with no extra arms and no chart pages (its numbers are not the ones
    those pages draw, and a page redrawn from them would look current while
    describing a different selector).
    """
    base_charts = tuple(CHART_MODULES.get(name, ()))
    for flag, suffix in CALLER_ARMS.get(name, ()):
        if flag in extra:
            return [(f"{name}-{suffix}", list(extra), ())]
    plan = [(name, list(extra), base_charts)]
    if any(f in extra for f in SINGLE_ARM_FLAGS):
        return plan
    for arm in STUDY_ARMS.get(name, ()):
        if any(f in extra for f in arm.args):
            continue
        plan.append((f"{name}-{arm.suffix}", [*extra, *arm.args], arm.charts))
    return plan


def main(argv: list[str] | None = None) -> int:
    studies = discover()
    ap = argparse.ArgumentParser(
        prog="python -m scripts.backtest_study",
        description="Run a backtest tuning study and capture its report.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="list available studies")
    p_run = sub.add_parser("run", help="run a study (extra args pass through)")
    p_run.add_argument("name", nargs="?", help="study name (see `list`)")
    p_run.add_argument("--all", action="store_true",
                       help="run every study with its default args")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--no-handoff", action="store_true",
                       help="suppress the 'paste this into Claude' footer — for callers "
                            "like scripts.study_review that do the write-up themselves")
    p_run.add_argument("--era", default=None,
                       help="which export era to run on: 'current' (default — the bare "
                            "exports, i.e. whatever the live tabs hold now) or a version "
                            "prefix like 'v3'. Sets STUDY_ERA for every study in the run "
                            "and is stamped in each report's provenance header.")
    # argv=None (the default) falls through to argparse's own sys.argv[1:]
    # read, same as before this parameter existed; passing a list is what
    # lets tests drive main() without touching sys.argv or shelling out.
    args, extra = ap.parse_known_args(argv)

    # Set for the whole run, before any header is built or subprocess spawned,
    # so the runner's own provenance and every study's loader agree on the era
    # without threading a flag through fourteen argparse blocks.
    if getattr(args, "era", None):
        os.environ["STUDY_ERA"] = args.era

    if args.cmd != "run":
        # Grouped by family, in family order, so `list` reads the same way the
        # directory and the study map do — pick it, manage it, wrap it, fund it.
        paths = study_paths()
        width = max(len(n) for n in studies)
        print(f"Studies ({len(studies)}) — `python -m {PKG} run <name>`:\n")
        for folder in (*FAMILY_DIRS, "lib"):
            names = [n for n in studies if paths[n].parent.name == folder]
            if not names:
                continue
            print(f"  {folder}/")
            for name in names:
                default = " ".join(DEFAULT_ARGS.get(name, []))
                tag = f"  [default: {default}]" if default else ""
                arms = ", ".join(a.suffix for a in STUDY_ARMS.get(name, ()))
                tag += f"  [+arms: {arms}]" if arms else ""
                print(f"    {name:{width}s}  {studies[name][:84]}{tag}")
            print()
        print(f"Output goes to {OUT_DIR.relative_to(ROOT)}/<name>-latest.txt")
        return 0

    names = list(studies) if args.all else ([args.name] if args.name else [])
    if not names:
        ap.error("give a study name or --all (see `list`)")
    unknown = [n for n in names if n not in studies]
    if unknown:
        ap.error(f"unknown study {unknown[0]!r}; known: {', '.join(studies)}")

    # Retired studies (scripts.study_map.catalog) are excluded from --all's
    # bulk run but stay runnable by explicit name — see this module's
    # docstring "Retired studies" note. Imported here, not at module scope,
    # for the same reason as the map import below.
    from scripts.study_map.catalog import retired_studies
    retired = retired_studies()
    skipped: list[str] = []
    if args.all:
        skipped = [n for n in names if n in retired]
        names = [n for n in names if n not in retired]
        for n in skipped:
            print(f"SKIPPING {n} (retired): {retired[n]}\n")
    else:
        for n in names:
            if n in retired:
                print(f"NOTE: {n} is RETIRED — {retired[n]}\n"
                      f"  Running anyway because it was named explicitly.\n")

    # (report stem, module name, that arm's argv, its chart modules, rc, refused)
    results = []
    for name in names:
        codes = _refusal_codes(name)
        for stem, arm_extra, charts in arm_plan(name, extra):
            rc, _path = run_one(name, arm_extra, args.dry_run, stem=stem,
                                refusal_codes=codes)
            results.append((stem, name, arm_extra, charts, rc, rc != 0 and rc in codes))

    if args.dry_run:
        return 0

    print("\n" + "=" * 78)
    print("DONE — reports:" if args.no_handoff else "DONE — reports written:\n")
    for stem, _name, _arm_extra, _charts, rc, refused in results:
        if rc == 0:
            status = ""
        elif refused:
            status = f"  (DESIGNED REFUSAL, exit {rc} — see report)"
        else:
            status = f"  *** FAILED rc={rc} ***"
        rel = (OUT_DIR / f"{stem}-latest.txt").relative_to(ROOT)
        print(f"  {rel}{status}")
    for n in skipped:
        print(f"  {n}  — SKIPPED (retired): {retired[n].split(' — ', 1)[-1][:80]}…")

    # Only a SUCCESSFUL run wrote a new report + (for account_sim) positions
    # CSV worth charting. A real failure leaves whatever chart page already
    # existed alone (its own "*** FAILED ***" line above is the visible signal
    # for that case). Each arm renders its OWN pages from its OWN positions CSV.
    #
    # A DESIGNED REFUSAL is a third case, and it is a SKIP, never a chart
    # error: the study did write a promoted report, but that report is its
    # refusal — there are no numbers in it to draw, and it may have exited
    # before writing a positions CSV at all. `study_charts.cli.run` detects
    # this itself and skips cleanly (exit 0, nothing written), so the only
    # thing wrong with calling it here would be the "chart refreshed:" line
    # underneath — which would report a page as redrawn when it was not, the
    # exact stale-reads-as-current failure `_render_charts` exists to prevent.
    for _stem, name, arm_extra, charts, rc, refused in results:
        if refused:
            for mod_name in (charts if charts is not None else CHART_MODULES.get(name)) or ():
                print(f"  chart SKIPPED: {mod_name} — {name} refused (exit {rc}); its page "
                      f"was left as it was and is now a page of an older era")
        elif rc == 0:
            _render_charts(name, _merge_args(name, arm_extra), charts)

    # Imported here, not at module scope: the map reads every report in the
    # output dir, and nothing about running a study should depend on it.
    from scripts.study_map.build import refresh_quietly
    mapped = refresh_quietly()
    if mapped:
        print(f"\n  map refreshed: {mapped.relative_to(ROOT)}  (open it in a browser)")
    # Standalone runs still need a write-up; study_review passes --no-handoff
    # because it runs the graded write-up itself (analyst A/B + validator + digest).
    if not args.no_handoff:
        print("\nFor the write-up, either:")
        print(f"  python3 -m scripts.study_review {names[0]} --skip-run"
              "   (graded: analyst A/B + validator + digest)")
        print("  or paste the report above into Claude and ask for a write-up.")
        print("  next: make study-record  (append this run's report to research/study-results/)")
    print("=" * 78)
    failed = [(stem, rc) for stem, _n, _a, _c, rc, refused in results if rc and not refused]
    refusals = [(stem, rc) for stem, _n, _a, _c, rc, refused in results if refused]
    if refusals:
        # Informational only — not a failure, so this stays off stderr and out
        # of the non-zero-exit calculation below.
        print("\n  DESIGNED REFUSALS (not failures): "
              + ", ".join(f"{n} (exit {rc})" for n, rc in refusals))
    if failed:
        # To stderr, after everything else: with --all a single study's failure
        # is easy to lose in thousands of report lines, and the non-zero exit
        # below is what makes `make study-all` stop with an Error.
        print("\n*** STUDY FAILURES: "
              + ", ".join(f"{n} (exit {rc})" for n, rc in failed)
              + " — their -latest.txt was NOT updated; "
              "scroll up for each one's output ***", file=sys.stderr)
    # The worst arm's / study's code among REAL failures only: a designed
    # refusal must not make `run --all` (or `make study-all`) look broken —
    # that is the whole point of declaring it. 0 when nothing real failed,
    # even if every study that ran was a refusal.
    return max((rc for *_rest, rc, refused in results if not refused), default=0)


if __name__ == "__main__":
    raise SystemExit(main())
