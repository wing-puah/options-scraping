"""
Clear out `backtests/study_output/` — the study runner's scratch report directory.

Every `python -m scripts.backtest_study run <name>` writes a stamped
`<name>-<stamp>.txt` AND a full copy at `<name>-latest.txt`, so the directory
fills up with duplicate report text (nine `calendar_hedge` runs in one
afternoon, at the time this was written). The tree is gitignored scratch: there
is no history to recover from, so deletion here is final.

Two modes:
  --all          every file goes
  --keep-latest  only `<name>-latest.txt` survives; stamped runs, pre-runner
                 debris (`bear_arm.txt`, `run.txt`, `*_output.txt`) and
                 generated data (`dataset.csv`) all go

Some reports are still load-bearing, so both modes run a PIN SCAN first and
refuse to delete a file that a CODE PATH reads (see CODE_INPUTS), that the
tuning log cites, or that carries a study's gate marker (see GATE_MARKERS).
Pinned files are reported, not deleted; `--force` turns the scan off, which is
what makes `--all --force` a true wipe.

A PIN GUARANTEES THE FILENAME, NOT THE CONTENTS. Nothing stops the next
`run <name>` from overwriting a cited `-latest.txt` with a run against different
exports, and that is not hypothetical: on 2026-08-15 a `run --all` re-ran the
suite against the truncated v4 exports, so `bear_arm-latest.txt` — pinned by
`research/deployment-evidence.md` for a paired CI of [+0.015, +0.065] — came to
hold E = -0.193 on a 74-row book instead. The pin held the name while the
evidence left. So the scan also compares each cited report's provenance header
against the sha or date the citing line claims and prints STALE when they
disagree; see `_stale_reason`.

Usage:
  python3 scripts/clean_study_output.py --keep-latest --dry-run
  python3 scripts/clean_study_output.py --keep-latest
  python3 scripts/clean_study_output.py --all --force --yes
"""
import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

# The runner writes one provenance header and every study inherits it, so the
# chart layer's parser is the parser for it. Dependency-light (re/textwrap/
# pathlib) and already the system of record for reading that header.
from study_charts.report import Report, ReportParseError, parse_provenance

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "backtests" / "study_output"
TUNING_DIR = ROOT / "research"

# Suffixes for the stable "-latest" copy: the runner (scripts/backtest_study/
# run.py) writes .txt, while the study/review pipelines write .csv/.md
# latests (positions/digest/review artifacts). Matched literally via
# str.endswith, not by regex on the stem: these are exact strings.
LATEST_SUFFIXES = ("-latest.txt", "-latest.csv", "-latest.md")

# Verdict lines that some study greps its OWN past reports for. A study whose
# gate reads the report directory must register its marker here, or a cleanup
# can silently revoke that gate.
#
#   "H2 (primary)"  — scripts/backtest_study/f3_structure/calendar_hedge.py:1266 globs every
#                     calendar_hedge-*.txt for this line before it will run ARM
#                     S. Only stamped reports carry it; -latest.txt may not.
GATE_MARKERS = ("H2 (primary)",)

# Files a CODE PATH reads. Pinned regardless of what any write-up says: removing
# one breaks a build rather than losing evidence, so a write-up must never be
# the thing keeping them alive.
CODE_INPUTS = {
    "account_sim-latest.txt":
        "scripts/study_charts/cli.py raises without it and `make study-docs` "
        "builds the account_sim page unguarded",
    "account_sim-positions-latest.csv":
        "same chart build — cli.py's DEFAULT_POSITIONS",
}

# Citations look like `backtests/study_output/<file>` in the tuning write-ups.
_CITE_RE = re.compile(r"study_output/([A-Za-z0-9_][A-Za-z0-9_.\-]*)")

# Fenced blocks are skipped by the citation scan — see cited_files().
_FENCE_RE = re.compile(r"^\s*(`{3,})")

# A citing line's claim about WHICH run it means. Only these two forms are
# checked: a write-up that names neither cannot be contradicted, and guessing
# from prose would produce false STALE reports on correct citations.
_DOC_SHA = re.compile(r"\bgit\s+([0-9a-f]{7,40})\b")
_DOC_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_CLAIM_WINDOW = 3       # lines either side of the citation to read the claim from


class Citation(NamedTuple):
    """Where a write-up points at a report, and the file that line lives in."""
    where: str          # "research/archive/13-….md:344", for the printed report
    doc: Path
    lineno: int


def _human(n: int) -> str:
    """Byte count as a short human string (976 -> '976B', 1200 -> '1.2K')."""
    for unit, size in (("M", 1024 ** 2), ("K", 1024)):
        if n >= size:
            return f"{n / size:.1f}{unit}"
    return f"{n}B"


def cited_files(tuning_dir: Path) -> dict[str, Citation]:
    """`{basename: Citation}` for every study_output file cited under `tuning_dir`.

    RECURSIVE, and that is the whole point: `research/archive/` and
    `research/pre-registrations/` hold most of the `**Provenance.**` lines in
    the repo, and the non-recursive glob this used to do read NONE of them — so
    every archive citation pinned nothing while appearing to.

    First citation of a given file wins — the report only needs to show one
    place that still points at it.
    """
    out: dict[str, Citation] = {}
    for md in sorted(tuning_dir.rglob("*.md")):
        try:
            text = md.read_text()
        except OSError:
            continue
        try:
            where = md.relative_to(ROOT)
        except ValueError:      # a tuning dir outside the repo (tests)
            # Relative to the scanned root, not just the basename: the scan is
            # recursive now, so `archive/13-….md` and a same-named file one
            # level up must not print identically.
            where = md.relative_to(tuning_dir)
        fence = ""      # the backtick run that opened the current code block
        for lineno, line in enumerate(text.splitlines(), start=1):
            if m := _FENCE_RE.match(line):
                # Closing needs a bare run at least as long as the opener's, so
                # a ```` block quoting ``` inside it stays open.
                if not fence:
                    fence = m.group(1)
                elif len(m.group(1)) >= len(fence) and not line.strip(" `"):
                    fence = ""
                continue
            if fence:
                # A path inside a fence is QUOTED REPORT OUTPUT, not a citation.
                # Study reports print their own export paths ("positions CSV:
                # 447 rows -> backtests/study_output/…"), so a folded excerpt
                # would otherwise pin the very files it was folded in to replace.
                continue
            for name in _CITE_RE.findall(line):
                out.setdefault(name, Citation(f"{where}:{lineno}", md, lineno))
    return out


def _report_stamp(path: Path) -> tuple[str, str] | None:
    """`(git sha, run date)` from the runner's provenance header, or None.

    None is the normal answer for anything that is not a runner report — a
    positions CSV, a review markdown, or pre-runner `tee` debris with no header
    at all. That is not an error; it means there is nothing to check a citation
    against.
    """
    if path.suffix != ".txt":
        return None
    try:
        prov = parse_provenance(Report(path.read_text(errors="ignore"), path))
    except (OSError, ReportParseError):
        return None
    return prov["git"].split()[0], prov["run_at"][:10]


def _stale_reason(path: Path, cit: Citation) -> str | None:
    """The report no longer is the run its citation names, or None.

    Deliberately conservative: it fires only when the citing line NAMES a git
    sha or a date. A write-up that claims neither is not making a checkable
    claim, and inventing one from prose would flag correct citations. The sha
    wins when both are present — docs routinely quote the export date next to a
    different run date, and the sha is the unambiguous one.
    """
    stamp = _report_stamp(path)
    if stamp is None:
        return None
    sha, run_date = stamp
    try:
        lines = cit.doc.read_text().splitlines()
    except OSError:
        return None

    lo = max(0, cit.lineno - 1 - _CLAIM_WINDOW)
    ctx = " ".join(lines[lo:cit.lineno + _CLAIM_WINDOW])

    if shas := _DOC_SHA.findall(ctx):
        # Either may be the abbreviation — compare on the shorter prefix.
        if not any(sha.startswith(s) or s.startswith(sha) for s in shas):
            return (f"STALE: report is git {sha} run {run_date}; "
                    f"citation says git {'/'.join(sorted(set(shas)))}")
    elif (dates := _DOC_DATE.findall(ctx)) and run_date not in dates:
        return (f"STALE: report ran {run_date}; "
                f"citation says {'/'.join(sorted(set(dates)))}")
    return None


def _has_gate_marker(path: Path) -> str | None:
    """The gate marker this report carries, or None."""
    if path.suffix != ".txt":
        return None
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return None
    return next((m for m in GATE_MARKERS if m in text), None)


def classify(out_dir: Path, keep_latest: bool, force: bool,
             citations: dict[str, Citation]) -> tuple[list[Path], list[tuple[Path, str]],
                                                      list[Path], list[Path]]:
    """Split the directory into (keep, pinned, delete, skipped_dirs).

    `keep` survives on the mode alone; `pinned` are delete candidates rescued by
    the pin scan, each with the reason to print. `force` empties `pinned`.
    """
    keep: list[Path] = []
    pinned: list[tuple[Path, str]] = []
    delete: list[Path] = []
    skipped: list[Path] = []

    for path in sorted(out_dir.iterdir()):
        if path.is_dir():
            skipped.append(path)
            continue
        if not path.is_file():
            continue
        if keep_latest and path.name.endswith(LATEST_SUFFIXES):
            keep.append(path)
            continue
        if not force:
            if reason := CODE_INPUTS.get(path.name):
                pinned.append((path, f"code input — {reason}"))
                continue
            cit = citations.get(path.name)
            if cit:
                why = f"cited {cit.where}"
                if stale := _stale_reason(path, cit):
                    why += f"  ** {stale} **"
                pinned.append((path, why))
                continue
            marker = _has_gate_marker(path)
            if marker:
                pinned.append((path, f'gate marker "{marker}"'))
                continue
        delete.append(path)

    return keep, pinned, delete, skipped


def _total(paths) -> int:
    return sum(p.stat().st_size for p in paths)


def report(keep: list[Path], pinned: list[tuple[Path, str]], delete: list[Path],
           skipped: list[Path]) -> None:
    """Print the KEEP / PINNED / DELETE summary."""
    def section(label: str, paths: list[Path]) -> None:
        print(f"{label:<8} ({len(paths):>3})  {_human(_total(paths)):>6}")

    section("KEEP", keep)

    print(f"{'PINNED':<8} ({len(pinned):>3})  "
          f"{_human(_total([p for p, _ in pinned])):>6}")
    width = max((len(p.name) for p, _ in pinned), default=0)
    for path, why in pinned:
        print(f"{'':>21}{path.name:<{width}}  {why}")

    section("DELETE", delete)
    for path in skipped:
        print(f"{'SKIP':<8}         subdirectory {path.name}/ (left alone)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clear backtests/study_output/ (all, or all but -latest.txt).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all", action="store_true",
                      help="delete every file in the directory")
    mode.add_argument("--keep-latest", action="store_true",
                      help="delete everything except <name>-latest.txt")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be deleted, delete nothing")
    parser.add_argument("--force", action="store_true",
                        help="skip the pin scan — delete cited and gate-marker files too")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="do not prompt for confirmation")
    args = parser.parse_args()

    if not OUT_DIR.is_dir():
        print(f"No such directory: {OUT_DIR.relative_to(ROOT)}", file=sys.stderr)
        return 1

    citations = {} if args.force else cited_files(TUNING_DIR)
    keep, pinned, delete, skipped = classify(
        OUT_DIR, keep_latest=args.keep_latest, force=args.force, citations=citations)

    report(keep, pinned, delete, skipped)
    print()

    if not delete:
        print(f"Nothing to delete in {OUT_DIR.relative_to(ROOT)}/.")
        return 0

    freed = _human(_total(delete))
    print(f"Delete {len(delete)} files, free {freed} "
          f"from {OUT_DIR.relative_to(ROOT)}/.")
    if pinned:
        print("Pinned files are kept — pass --force to delete those too.")

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

    failed = 0
    for path in delete:
        try:
            path.unlink()
        except OSError as exc:
            print(f"  FAILED {path.name}: {exc}", file=sys.stderr)
            failed += 1
    print(f"Deleted {len(delete) - failed} files, freed {freed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
