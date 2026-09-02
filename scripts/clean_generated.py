"""
Delete the repo's generated scratch — logs, rendered pages, chart PNGs, stamped
backtest exports, bytecode — so a working checkout can be reset without touching
anything that took a network round-trip or cannot be rebuilt.

Everything here is REGENERABLE by a documented command; each target records that
command in `regen` and the report prints it, because the only real question when
deleting generated output is "what do I run to get it back".

Two tiers:

  DEFAULT   local scratch. Rebuilt by re-running a script — no network, minutes
            at most. This is what `make clean` deletes.
  --caches  network-backed caches and Drive pulls (`audit/`, the OHLC cache, the
            sweep checkpoint, the regime table). Rebuilding them means refetching,
            so they are opt-in and a bare run never touches them.

`backtests/study_output/` is deliberately NOT a target here: it has its own
cleaner, `scripts/clean_study_output.py`, whose pin scan protects reports that
the tuning log cites or a study's gate greps for. `make clean` runs both.

FOUR GUARDS stand between a glob and an unlink. The first three are checked in
`safety_violations` for EVERY candidate on every run, dry or not, and a violation
is a HARD ERROR that deletes nothing — not a path quietly filtered out:

  1. inside the repo    — resolved path must be under ROOT (no `..`, no symlink
                          escape out of the tree)
  2. not git-tracked    — `git ls-files` is the authority. A tracked file is
                          source, whatever a glob thinks. This is what keeps
                          `backtests/__init__.py` and `portfolio/*.py` safe, and
                          it stays correct as the repo changes.
  3. not protected      — PROTECTED_PREFIXES are the irreplaceable trees: the
                          live trade record, broker exports, scraped caches,
                          credentials. They are gitignored, so guard 2 would MISS
                          them — which is exactly why this guard exists.

  4. not cited          — a soft guard, and the only one that is advisory: files
                          referenced by path in `research/`, `docs/`, `scripts/`
                          or `config/` are PINNED and reported rather than
                          deleted, because `backtests/` has no git history to
                          recover from and the tuning log's provenance lines are
                          the only thing marking an export as evidence. `--force`
                          turns this one off; nothing turns off 1-3.

Usage:
  python3 scripts/clean_generated.py --list          # targets + sizes, delete nothing
  python3 scripts/clean_generated.py --dry-run
  python3 scripts/clean_generated.py                 # prompts
  python3 scripts/clean_generated.py --yes
  python3 scripts/clean_generated.py --caches --yes  # + the refetchable caches
  python3 scripts/clean_generated.py --only logs,site
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Trees that must never lose a file to this script, as repo-relative paths. All
# are gitignored, so the git-tracked guard cannot see them — this list is their
# only protection. A path is protected if any of these is a SEGMENT-WISE prefix
# of it, so a multi-segment entry protects exactly that subtree.
#
#   journal/          the LIVE TRADE RECORD (raw broker pulls, fills, P&L).
#                     Not reproducible: it is the record of what happened.
#   portfolio/input/  broker exports dropped in by hand. A short Flex statement
#                     omits untouched positions, and CLAUDE.md says the fix is
#                     to add an export HERE — deleting them re-opens the gap.
#                     (portfolio/output/ IS derived, and is a target below.)
#   credentials/      OAuth tokens; deleting means re-running the Drive consent
#                     flow by hand.
#   cookies/          scraper session state; deleting means a fresh login.
#   config/           hand-written settings that drive every tier.
#   research/         the tuning log — conclusions, not output.
#   .venv/ .git/      obvious, and cheap to state.
#
#   backtests/option_history_cache/  ~337MB of scraped option history across ~20k
#                     files — the real short-leg prices the backtest depends on.
#                     Held out of the cleaner ENTIRELY, not merely behind
#                     --caches: there is no flag that deletes it.
#   backtests/to_evaluate/  NOT a cache. The Sheets CSV exports every study
#                     loader reads by filename. `make export-tabs` re-pulls the
#                     LIVE tabs, but a frozen era's tab may since have been
#                     deleted upstream, and the hand-written *.md date lists
#                     here have no source at all. An input that happens to live
#                     under a scratch directory.
#   backtests/live_loop/    point-in-time IBKR snapshots. The repo calls the tree
#                     disposable, but a snapshot for a past date cannot be
#                     refetched — which is why the test suite copied its fixture
#                     into tests/fixtures/ rather than rely on this surviving.
PROTECTED_PREFIXES = (
    ".git",
    ".venv",
    "backtests/live_loop",
    "backtests/option_history_cache",
    "backtests/to_evaluate",
    "config",
    "cookies",
    "credentials",
    "journal",
    "portfolio/input",
    "research",
)

# Names that anchor a gitignored directory or make it a package. A glob over a
# directory's contents will match these; they are not scratch.
KEEP_NAMES = frozenset({".gitkeep", "__init__.py", ".gitignore"})

# Directories never descended into when walking for bytecode.
_WALK_PRUNE = frozenset({".git", ".venv", "venv", "node_modules", ".next"})

# Where a reference to a generated file would be written: the tuning log and its
# archive, the hand-written docs, and any code that hardcodes a path.
CITATION_DIRS = ("research", "docs", "scripts", "config")
CITATION_SUFFIXES = (".md", ".py", ".yml", ".yaml")

# `backtests/foo/bar.csv` anywhere in prose or code. Deliberately anchored on
# `backtests/` — that is the only tree whose contents are both deletable here
# and cited as evidence elsewhere.
_CITE_RE = re.compile(r"backtests/([A-Za-z0-9_][A-Za-z0-9_./\-]*)")


@dataclass(frozen=True)
class Target:
    """One deletable class of generated output.

    `globs` are evaluated against ROOT and match the CONTENTS of a directory
    (`logs/*.log`), not the directory itself — the runtime dirs are gitignored
    and some scripts assume they exist, so they are emptied, never removed.
    `excludes` are subtracted from the match, for the case where one directory
    holds both regenerable and irreplaceable output.
    """
    name: str
    globs: tuple[str, ...]
    what: str                       # what it is, one line
    regen: str                      # the command that rebuilds it
    excludes: tuple[str, ...] = ()
    expensive: bool = False         # needs --caches
    walk_pycache: bool = False      # special-cased: recursive, prunes vendored trees


TARGETS: tuple[Target, ...] = (
    Target(
        name="logs",
        globs=("logs/*.log", "logs/*.log.*"),
        what="rotating run logs; write-only, nothing reads them back",
        regen="written afresh by the next script run",
    ),
    Target(
        name="site",
        globs=("site/*.html",),
        # `make study-docs` rebuilds the study map and the three chart pages. It
        # does NOT rebuild site/journal-*.html: those come from a real journal
        # run against live broker data, so a deleted page for a past date is gone
        # unless that date's pull is still in journal/raw/. Excluded, not risked.
        excludes=("site/journal-*.html",),
        what="generated study map + study-chart pages (journal pages excluded)",
        regen="make study-docs",
    ),
    Target(
        name="charts",
        globs=("backtests/charts/*",),
        what="backtest chart PNGs, recomputed locally from the results CSVs",
        regen="make chart-all",
    ),
    Target(
        name="backtest-runs",
        # Every backtest run archives the previous results.csv by renaming it to
        # results_<stamp>.csv (backtest/shared/results_io.py), so these stamped
        # files are the auto-generated history. The rolling results.csv and
        # proxy_results.csv are what `make chart-all` reads and are NOT matched.
        # The frozen evidence exports (v1_*/v2_*) do not match this shape either,
        # and the citation pin scan is the backstop if one ever does.
        globs=("backtests/results_*.csv", "backtests/proxy_results_*.csv"),
        what="STAMPED backtest exports (rolling results.csv/proxy_results.csv kept)",
        regen="make backtest-all",
    ),
    Target(
        name="ml-study-relic",
        # Orphaned: f1_selection/ml_combination.py writes to study_output/, not
        # here. This is leftover `tee` output from before the runner existed; the
        # study's verdict is recorded in research/study-map.md and does not
        # depend on these files.
        globs=("backtests/ml_combination_study/*",),
        what="orphaned tee output from a closed study (verdict lives in research/)",
        regen="nothing — the study's writer targets backtests/study_output/",
    ),
    Target(
        name="portfolio-output",
        globs=("portfolio/output/*",),
        what="derived portfolio CSVs, recomputed from portfolio/input/ in seconds",
        regen="python3 portfolio/01_cleanup.py && python3 portfolio/02_analysis.py",
    ),
    Target(
        name="pycache",
        globs=(),
        what="__pycache__ bytecode trees",
        regen="regenerated on the next import",
        walk_pycache=True,
    ),
    Target(
        name="pytest-cache",
        globs=(".pytest_cache/*",),
        what="pytest's incremental run cache",
        regen="regenerated on the next pytest run",
    ),
    Target(
        name="web-build",
        globs=("web/.next/*",),
        what="Next.js dashboard build output",
        regen="cd web && npm run dev  (or npm run build)",
    ),
    # ── --caches tier: everything below needs the network to come back ─────────
    Target(
        name="audit",
        globs=("audit/*.csv",),
        what="per-date analysis rollup CSVs; feed backtest scoring context",
        regen="python3 -m scripts.analysis_pipeline --skip-llm --date <date>  (per date, reads Drive)",
        expensive=True,
    ),
    Target(
        name="ohlc-cache",
        globs=("backtests/underlying_ohlc_cache/*",),
        what="cached underlying stock OHLC bars",
        regen="python3 scripts/collector/fetch_underlying_ohlc.py",
        expensive=True,
    ),
    Target(
        name="sweep-cache",
        globs=("backtests/sweep_cache/*",),
        what="sweep-leg manifest + the calendar_hedge RESUME CHECKPOINT",
        regen="python3 scripts/collector/fetch_sweep_legs.py  (an interrupted sweep restarts from zero)",
        expensive=True,
    ),
    Target(
        name="mech-regime",
        globs=("backtests/mech_regime/*.csv",),
        what="local copy of the SPY/VIX regime table (copy of record is on Drive)",
        regen="make mech-regime",
        expensive=True,
    ),
)


def _human(n: int) -> str:
    """Byte count as a short human string (976 -> '976B', 1200 -> '1.2K')."""
    for unit, size in (("G", 1024 ** 3), ("M", 1024 ** 2), ("K", 1024)):
        if n >= size:
            return f"{n / size:.1f}{unit}"
    return f"{n}B"


def tracked_files(root: Path) -> frozenset[Path]:
    """Absolute paths of every file git tracks, or empty outside a repo.

    An empty set only weakens guard 2; guards 1 and 3 still apply.
    """
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return frozenset()
    return frozenset(root / name for name in out.split("\0") if name)


def cited_paths(root: Path, dirs=CITATION_DIRS) -> dict[str, str]:
    """`{cited: "path/to/doc.md:LINE"}` for every `backtests/...` reference found.

    Each hit is recorded under its repo-relative path, and ALSO under its bare
    basename so a citation survives being written either way — but only when
    that basename carries a suffix. A bare directory name is far too generic to
    key on: `chart_backtest.py` names `backtests/charts` as its output dir, and
    a plain-basename index would let that pin every unrelated `charts/` in the
    repo. First mention wins — the report only needs to show one live pointer.
    """
    out: dict[str, str] = {}
    for name in dirs:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in CITATION_SUFFIXES or not path.is_file():
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            try:
                where = path.relative_to(root)
            except ValueError:
                where = path.name
            for lineno, line in enumerate(text.splitlines(), start=1):
                for hit in _CITE_RE.findall(line):
                    hit = hit.rstrip("./")
                    if not hit:
                        continue
                    out.setdefault(f"backtests/{hit}", f"{where}:{lineno}")
                    base = hit.rsplit("/", 1)[-1]
                    if "." in base:
                        out.setdefault(base, f"{where}:{lineno}")
    return out


def _walk_pycache(root: Path) -> list[Path]:
    """Every `__pycache__` dir under root, skipping vendored and protected trees.

    Protected trees are PRUNED rather than collected-then-refused: bytecode under
    `portfolio/` is genuinely disposable, but the guard is a blunt instrument by
    design, and skipping a few KB there is cheaper than carving an exception into
    a rule whose whole value is having none.
    """
    found: list[Path] = []
    for dirpath, dirnames, _ in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if d not in _WALK_PRUNE
            and _protecting_prefix(_safe_relative(here / d, root)) is None
        ]
        if "__pycache__" in dirnames:
            dirnames.remove("__pycache__")
            found.append(here / "__pycache__")
    return sorted(found)


def _safe_relative(path: Path, root: Path) -> Path:
    """`path` relative to `root`, or the path itself when it lies outside."""
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def resolve(target: Target, root: Path) -> list[Path]:
    """Existing paths this target matches, minus excludes and KEEP_NAMES anchors."""
    if target.walk_pycache:
        return _walk_pycache(root)
    excluded: set[Path] = set()
    for pattern in target.excludes:
        excluded.update(root.glob(pattern))
    hits: set[Path] = set()
    for pattern in target.globs:
        for path in root.glob(pattern):
            if path.name in KEEP_NAMES or path in excluded:
                continue
            hits.add(path)
    return sorted(hits)


def _size(path: Path) -> int:
    """Bytes on disk for a file or a whole directory tree."""
    if path.is_file() or path.is_symlink():
        try:
            return path.lstat().st_size
        except OSError:
            return 0
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for name in filenames:
            try:
                total += (Path(dirpath) / name).lstat().st_size
            except OSError:
                pass
    return total


def _count(path: Path) -> int:
    """Files represented by a path (1 for a file, the tree's file count for a dir)."""
    if path.is_file() or path.is_symlink():
        return 1
    return sum(len(filenames) for _, _, filenames in os.walk(path))


def _protecting_prefix(rel: Path) -> str | None:
    """The PROTECTED_PREFIXES entry covering `rel`, or None.

    Compares whole path SEGMENTS, so `backtests/option_history_cache` never
    matches a sibling like `backtests/option_history_cache_v2`, and the root
    `journal` never matches `scripts/journal` — the same trap the .gitignore's
    leading slash exists for.
    """
    parts = rel.parts
    for prefix in PROTECTED_PREFIXES:
        pparts = Path(prefix).parts
        if parts[:len(pparts)] == pparts:
            return prefix
    return None


def safety_violations(paths: list[Path], root: Path,
                      tracked: frozenset[Path]) -> list[tuple[Path, str]]:
    """`(path, reason)` for every candidate that must NOT be deleted.

    A non-empty result is a BUG in the target table, not a runtime condition to
    filter out — the caller aborts. Ordered as the module docstring lists them.
    """
    violations: list[tuple[Path, str]] = []
    for path in paths:
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            violations.append((path, "resolves outside the repository"))
            continue
        if path in tracked or resolved in tracked:
            violations.append((path, "tracked by git"))
            continue
        protected = _protecting_prefix(rel)
        if protected:
            violations.append((path, f"under protected {protected}/"))
    return violations


def pin(paths: list[Path], root: Path,
        citations: dict[str, str]) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Split candidates into (deletable, pinned) using the citation index."""
    deletable: list[Path] = []
    pinned: list[tuple[Path, str]] = []
    for path in paths:
        rel = _safe_relative(path, root).as_posix()
        where = citations.get(rel) or citations.get(path.name)
        if where:
            pinned.append((path, f"cited {where}"))
        else:
            deletable.append(path)
    return deletable, pinned


@dataclass
class Plan:
    """What one run intends to delete, per target, plus what the pin scan saved."""
    entries: list[tuple[Target, list[Path]]] = field(default_factory=list)
    pinned: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def paths(self) -> list[Path]:
        return [p for _, paths in self.entries for p in paths]

    @property
    def nbytes(self) -> int:
        return sum(_size(p) for p in self.paths)

    @property
    def nfiles(self) -> int:
        return sum(_count(p) for p in self.paths)


def build_plan(targets, root: Path, caches: bool, only: set[str] | None,
               citations: dict[str, str] | None = None) -> Plan:
    """Resolve every selected target. Targets left with nothing are dropped.

    The safety guards are NOT applied here — `main` runs them over the finished
    plan so that a violation aborts the whole run rather than silently shrinking
    one target.
    """
    citations = citations or {}
    plan = Plan()
    for target in targets:
        if only is not None and target.name not in only:
            continue
        if target.expensive and not caches:
            continue
        deletable, pinned = pin(resolve(target, root), root, citations)
        plan.pinned.extend(pinned)
        if deletable:
            plan.entries.append((target, deletable))
    return plan


def report(plan: Plan, root: Path, targets, caches: bool) -> None:
    """Print one line per target with its rebuild command, then the pins."""
    if plan.entries:
        width = max(len(t.name) for t, _ in plan.entries)
        for target, paths in plan.entries:
            nbytes = sum(_size(p) for p in paths)
            nfiles = sum(_count(p) for p in paths)
            tier = " [cache]" if target.expensive else ""
            print(f"  {target.name:<{width}}  {_human(nbytes):>7}  "
                  f"{nfiles:>6} files{tier}  {target.what}")
            print(f"  {'':<{width}}  {'':>7}  {'':>6} {'':>{len(tier)}}      "
                  f"rebuild: {target.regen}")
        print()
        print(f"  {'TOTAL':<{width}}  {_human(plan.nbytes):>7}  "
              f"{plan.nfiles:>6} files")
    else:
        print("  Nothing to delete.")

    if plan.pinned:
        print(f"\n  PINNED ({len(plan.pinned)}) — referenced elsewhere, kept:")
        width = max(len(p.name) for p, _ in plan.pinned)
        for path, why in plan.pinned:
            print(f"    {path.name:<{width}}  {why}")
        print("  Pass --force to delete pinned files too.")

    if not caches:
        held = [t.name for t in targets if t.expensive and resolve(t, root)]
        if held:
            print(f"\n  Network-backed caches kept ({', '.join(held)}) — "
                  f"pass --caches to delete those too.")


def delete(plan: Plan) -> int:
    """Remove every planned path. Returns the number of failures."""
    failed = 0
    for _, paths in plan.entries:
        for path in paths:
            try:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            except OSError as exc:
                print(f"  FAILED {path}: {exc}", file=sys.stderr)
                failed += 1
    return failed


def _list_targets(root: Path) -> int:
    """Print the whole table with current sizes, deleting nothing."""
    width = max(len(t.name) for t in TARGETS)
    for target in TARGETS:
        paths = resolve(target, root)
        nbytes = sum(_size(p) for p in paths)
        tier = "cache" if target.expensive else "     "
        print(f"  {target.name:<{width}}  {tier}  {_human(nbytes):>7}  "
              f"{target.what}")
        print(f"  {'':<{width}}         {'':>7}  rebuild: {target.regen}")
    print(f"\n  Never deleted by any flag: {', '.join(PROTECTED_PREFIXES)}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Delete the repo's regenerable scratch output.")
    parser.add_argument("--caches", action="store_true",
                        help="also delete the network-backed caches (refetch to restore)")
    parser.add_argument("--only", metavar="A,B",
                        help="clean only these targets (see --list)")
    parser.add_argument("--list", action="store_true", dest="list_targets",
                        help="show every target and what it holds, delete nothing")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be deleted, delete nothing")
    parser.add_argument("--force", action="store_true",
                        help="skip the citation pin scan — delete cited files too")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="do not prompt for confirmation")
    args = parser.parse_args(argv)

    if args.list_targets:
        return _list_targets(ROOT)

    only = None
    if args.only:
        only = {name.strip() for name in args.only.split(",") if name.strip()}
        unknown = only - {t.name for t in TARGETS}
        if unknown:
            print(f"Unknown target(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            print(f"Known: {', '.join(t.name for t in TARGETS)}", file=sys.stderr)
            return 2

    citations = {} if args.force else cited_paths(ROOT)
    plan = build_plan(TARGETS, ROOT, caches=args.caches, only=only,
                      citations=citations)

    violations = safety_violations(plan.paths, ROOT, tracked_files(ROOT))
    if violations:
        print("REFUSING TO DELETE — the target table matched protected paths:",
              file=sys.stderr)
        for path, why in violations:
            print(f"  {_safe_relative(path, ROOT)}: {why}", file=sys.stderr)
        return 2

    report(plan, ROOT, TARGETS, caches=args.caches)
    if not plan.entries:
        return 0

    print()
    if args.dry_run:
        print("(dry run — nothing deleted)")
        return 0

    if not args.yes:
        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 0

    freed, nfiles = _human(plan.nbytes), plan.nfiles
    failed = delete(plan)
    print(f"Deleted {nfiles - failed} files, freed {freed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
