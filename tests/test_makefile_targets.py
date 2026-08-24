"""The Makefile's target names are the interface every doc and script points
at when it tells an operator what to run next, so test that pointer.

The 2026-08 study-chart consolidation collapsed seven chart targets into one
parameterized `study-chart` (CHART=account_sim|regime|compounding) and removed
the old names outright — no aliases, per the recorded decision. A removal like
that is invisible to `make help` (which is hand-written prose, not derived
from the target list) and invisible to the target itself (nothing stops a doc
from citing a name that used to work). Three claims, each checked here:

  * every `` `make <target>` `` invocation cited in the docs a reader actually
    follows (README.md, CLAUDE.md, docs/*.md, research/README.md) names a
    target that still exists;
  * `make study-chart`'s CHART= validation set is exactly the three
    `scripts/study_charts/` render modules, no more, no fewer;
  * `scripts/clean_generated.py`'s `regen=` hints — "how do I get this file
    back" — that happen to be `make` invocations also name real targets.

research/archive/, research/current.md, and research/study-results/ are
dated historical records (see CLAUDE.md's `research/` row): a past write-up
may cite a target that has since been renamed, and rewriting history to keep
this test green would defeat the point of an append-only log. They are
excluded by simply not being in the scanned file list below, not by pattern.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def _phony_targets() -> set[str]:
    """Every name declared `.PHONY` — the Makefile's own claim of what a
    target is (as opposed to a real file it might otherwise be confused
    with), so this is the authoritative target list to check citations
    against."""
    names: set[str] = set()
    for line in re.findall(r"^\.PHONY:\s*(.+)$", MAKEFILE.read_text(), flags=re.MULTILINE):
        names.update(line.split())
    return names


PHONY = _phony_targets()


def test_phony_list_is_not_suspiciously_small():
    """Guard the guard: if `.PHONY:` parsing ever breaks (a reformat, a typo
    in the regex), every other test in this file would pass by checking
    nothing against an empty set."""
    assert len(PHONY) >= 30, sorted(PHONY)


# ── every `make <target>` cited in prose must be real ──────────────────────

DOC_FILES = [
    ROOT / "README.md",
    ROOT / "CLAUDE.md",
    ROOT / "research" / "README.md",
    *sorted((ROOT / "docs").glob("*.md")),
]

# Deliberately loose: this is the same shape a reader's eye follows when
# skimming for a command to copy-paste, whether it sits in a fenced code
# block or inline prose.
_MAKE_RE = re.compile(r"make ([a-z][a-z-]+)")


@pytest.mark.parametrize("path", DOC_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_cited_make_target_is_real(path):
    cited = set(_MAKE_RE.findall(path.read_text()))
    unknown = cited - PHONY
    assert not unknown, (
        f"{path.relative_to(ROOT)} cites make target(s) {sorted(unknown)} that "
        f"have no .PHONY entry in the Makefile — renamed or removed out from "
        f"under the doc.")


# ── study-chart's CHART= set is exactly the study_charts render modules ────

def test_chart_validation_set_matches_study_charts_modules():
    """`make study-chart CHART=<x>` runs `python -m scripts.study_charts.<x>`.
    The validation set (VALID_CHARTS in the Makefile) and the modules that can
    actually be invoked that way must be the same claim: a name in one but not
    the other is either a CHART value that 404s or a page nothing can reach."""
    text = MAKEFILE.read_text()
    m = re.search(r"^VALID_CHARTS\s*:=\s*(.+)$", text, flags=re.MULTILINE)
    assert m, "Makefile has no `VALID_CHARTS := ...` line for study-chart to validate against"
    valid = set(m.group(1).split())
    assert valid == {"account_sim", "regime", "compounding"}, valid


@pytest.mark.parametrize("chart", ["account_sim", "regime", "compounding"])
def test_each_valid_chart_has_a_runnable_module(chart):
    mod = ROOT / "scripts" / "study_charts" / f"{chart}.py"
    assert mod.exists(), f"CHART={chart} is valid but scripts/study_charts/{chart}.py does not exist"
    assert re.search(r"^def main\(", mod.read_text(), flags=re.MULTILINE), (
        f"scripts/study_charts/{chart}.py has no `def main(` — `make study-chart "
        f"CHART={chart}` invokes it as `python -m scripts.study_charts.{chart}`, "
        f"which needs one to run at all.")


# ── clean_generated's regen= hints must point at real targets ──────────────

def test_clean_generated_regen_make_targets_are_real():
    """`make clean-list` prints each target's `regen` line so an operator
    knows how to rebuild what `make clean` just deleted. A `regen=` string
    that names a make target which no longer exists would send them to a
    dead end at the exact moment they need the command to work."""
    import sys

    scripts_dir = str(ROOT / "scripts")
    added = scripts_dir not in sys.path
    if added:
        sys.path.insert(0, scripts_dir)
    try:
        from clean_generated import TARGETS
    finally:
        if added:
            sys.path.remove(scripts_dir)

    checked = 0
    for target in TARGETS:
        regen = target.regen
        if not regen.startswith("make "):
            continue
        name = regen.split()[1]
        checked += 1
        assert name in PHONY, (
            f"clean_generated.TARGETS[{target.name!r}].regen cites `make {name}`, "
            f"which has no .PHONY entry in the Makefile.")
    if checked == 0:
        pytest.skip("no regen= string in scripts/clean_generated.py is a `make ...` invocation")
