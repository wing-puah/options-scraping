"""The directory layout of `scripts/backtest_study/` is a CLAIM, so test it.

The package is organised the way `scripts/journal/` is, adapted to the fact that
studies are not a pipeline: journal names files `sNN_` because the listing is its
FLOW, while twenty studies argue past each other about four questions, so here
the FOLDERS carry the ordering. `f1_selection` … `f4_deployment` is the order a
play moves through the system — pick it, manage it, wrap it, fund it — and `lib/`
holds everything the studies lean on.

That split is only worth having if it cannot drift. The taxonomy already existed
as a hand-written `family` tag in `scripts/study_map/catalog.py`, and lived only
on the rendered study map; the failure mode this file exists to prevent is the
directory and that tag disagreeing, which would make `ls` a lie about what a
study argues. So:

  * a module in `fN_<family>/` MUST have a catalog entry, and its `family` must
    equal its folder;
  * a module in `lib/` must have NO catalog entry — `lib/` argues nothing, and
    "does this file have a verdict?" is answerable from its path alone;
  * the folder ORDER must match `catalog.FAMILIES`, since both claim to be the
    order a play moves through the system.

Plus one guard that is pure scar tissue: every module computes `ROOT` by index
(`parents[N]`) and then `sys.path.insert`s it. Moving a module one directory
deeper silently makes that index wrong — every study in the package broke
exactly this way during the 2026-08-15 reorganisation, and the failure surfaces
as a confusing "no such config file" pointing at `scripts/config/...`, not as an
import error.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts.backtest_study import run as study_runner
from scripts.study_map import catalog

PKG_DIR = Path(study_runner.STUDY_DIR)
ROOT = PKG_DIR.parents[1]


def _modules(folder: str) -> list[Path]:
    return sorted(p for p in (PKG_DIR / folder).glob("*.py")
                  if not p.stem.startswith("__"))


def _family_key(folder: str) -> str:
    """`f2_management` -> `management`, the key catalog tags a study with."""
    return folder.split("_", 1)[1]


# ── the folder IS the family ──────────────────────────────────────────────────

def test_family_dirs_are_the_catalog_families_in_the_catalog_order():
    """`FAMILY_DIRS` and `catalog.FAMILIES` both claim to be the order a play
    moves through the system. They must be the same claim."""
    assert [_family_key(d) for d in study_runner.FAMILY_DIRS] == list(catalog.FAMILIES)


def test_every_family_dir_exists_and_is_a_package():
    for folder in study_runner.FAMILY_DIRS:
        assert (PKG_DIR / folder).is_dir(), folder
        # Without __init__.py the module is unimportable as
        # scripts.backtest_study.<folder>.<name>, which is what `run` executes.
        assert (PKG_DIR / folder / "__init__.py").exists(), folder


@pytest.mark.parametrize("folder", study_runner.FAMILY_DIRS)
def test_every_module_in_a_family_dir_is_a_catalogued_study_of_that_family(folder):
    for path in _modules(folder):
        assert path.stem in catalog.STUDIES, (
            f"{path.relative_to(ROOT)} sits in a family folder but has no entry in "
            f"scripts/study_map/catalog.py. A file in fN_*/ is a STUDY and needs a "
            f"question and a verdict; a helper belongs in backtest_study/lib/.")
        assert catalog.STUDIES[path.stem].family == _family_key(folder), (
            f"{path.stem} is catalogued as family "
            f"{catalog.STUDIES[path.stem].family!r} but lives in {folder}/. "
            f"Move the file or fix the catalog — the map and the directory must "
            f"tell a reader the same thing.")


def test_every_catalogued_study_lives_in_its_familys_folder():
    """The other direction: no catalog entry without a file in the right place."""
    located = {p.stem: _family_key(folder)
               for folder in study_runner.FAMILY_DIRS for p in _modules(folder)}
    for name, study in catalog.STUDIES.items():
        assert name in located, f"{name} is catalogued but has no module in any fN_*/ folder"
        assert located[name] == study.family, name


def test_lib_modules_carry_no_verdict():
    """`lib/` is the shared substrate — it argues nothing, so nothing in it may
    have a catalog verdict. This is what makes the directory readable: a file's
    path answers "does this conclude something?" without opening it."""
    for path in _modules("lib"):
        assert path.stem not in catalog.STUDIES, (
            f"{path.relative_to(ROOT)} has a verdict in the catalog, so it is a "
            f"study, so it belongs in a family folder — not in lib/.")


def test_the_only_runnable_lib_module_is_the_book_loader():
    """`book --validate` is the standard pre-flight, so the runner lists it. If
    another lib module becomes runnable, say so here on purpose rather than
    letting the 'a study is a file in a family folder' rule quietly acquire an
    exception."""
    assert study_runner.RUNNABLE_LIB == {"book"}
    assert set(study_runner.study_paths()) - set(catalog.STUDIES) == {"book"}


def test_no_stray_modules_left_flat_in_the_package():
    """Only the runner and its entry point sit at the top level. Anything else
    is a module that was added without deciding whether it argues."""
    flat = {p.stem for p in PKG_DIR.glob("*.py") if not p.stem.startswith("__")}
    assert flat == {"run"}


# ── the moved-module scar ─────────────────────────────────────────────────────

def test_every_module_resolves_ROOT_to_the_repo_root():
    """`ROOT = Path(__file__).resolve().parents[N]` is index-based, so moving a
    module between directory depths silently points it at the wrong tree — it
    then reads config and CSVs from `scripts/` and fails far from the cause.

    Checked by `ast` rather than by importing, for the same reason `discover()`
    is: `mech_regime_recut` and `regime_gap_reread` do their work at module
    level, so importing them here would run two whole studies.
    """
    checked = 0
    for path in sorted(PKG_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "ROOT"
                            for t in node.targets)):
                continue
            # Path(__file__).resolve().parents[N] — pull out the N.
            src = ast.unparse(node.value)
            assert src.startswith("Path(__file__).resolve().parents["), (
                f"{path.relative_to(ROOT)} computes ROOT some other way ({src}); "
                f"teach this test about it rather than deleting the check.")
            depth = int(src.rsplit("[", 1)[1].rstrip("]"))
            assert path.resolve().parents[depth] == ROOT, (
                f"{path.relative_to(ROOT)} sets ROOT to parents[{depth}] = "
                f"{path.resolve().parents[depth]}, not the repo root {ROOT}. "
                f"The file moved directory depth without the index following it.")
            checked += 1
    # Guard the guard: if a refactor drops the ROOT idiom everywhere, this test
    # must fail loudly rather than pass by checking nothing.
    assert checked >= 25, f"only found {checked} ROOT definitions — did the idiom change?"


# ── names are identity, folders are navigation ───────────────────────────────

def test_study_names_are_bare_stems_not_dotted_paths():
    """A study's NAME is what `run <name>` takes, what the report is filed as,
    what the catalog keys on, and what `research/` cites in a hundred places.
    Moving a study between folders must never change it."""
    for name in study_runner.discover():
        assert "." not in name and "/" not in name, name


def test_module_of_returns_the_importable_dotted_path():
    import importlib.util

    for name in study_runner.discover():
        dotted = study_runner.module_of(name)
        assert dotted.startswith("scripts.backtest_study."), dotted
        assert dotted.rsplit(".", 1)[1] == name
        # find_spec resolves the module without executing it — the two
        # module-level studies must not run just because we checked the path.
        assert importlib.util.find_spec(dotted) is not None, dotted
