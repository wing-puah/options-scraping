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
refuse to delete a file that is either cited by the tuning log or carries a
study's gate marker (see GATE_MARKERS). Pinned files are reported, not deleted;
`--force` turns the scan off, which is what makes `--all --force` a true wipe.

Usage:
  python3 scripts/clean_study_output.py --keep-latest --dry-run
  python3 scripts/clean_study_output.py --keep-latest
  python3 scripts/clean_study_output.py --all --force --yes
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "backtests" / "study_output"
TUNING_DIR = ROOT / "config" / "backtest-tuning"

# Suffixes for the stable "-latest" copy: the runner (scripts/backtest_study/
# run.py) writes .txt, while the study/review pipelines write .csv/.md
# latests (positions/digest/review artifacts). Matched literally via
# str.endswith, not by regex on the stem: these are exact strings.
LATEST_SUFFIXES = ("-latest.txt", "-latest.csv", "-latest.md")

# Verdict lines that some study greps its OWN past reports for. A study whose
# gate reads the report directory must register its marker here, or a cleanup
# can silently revoke that gate.
#
#   "H2 (primary)"  — scripts/backtest_study/calendar_hedge.py:1266 globs every
#                     calendar_hedge-*.txt for this line before it will run ARM
#                     S. Only stamped reports carry it; -latest.txt may not.
GATE_MARKERS = ("H2 (primary)",)

# Citations look like `backtests/study_output/<file>` in the tuning write-ups.
_CITE_RE = re.compile(r"study_output/([A-Za-z0-9_][A-Za-z0-9_.\-]*)")


def _human(n: int) -> str:
    """Byte count as a short human string (976 -> '976B', 1200 -> '1.2K')."""
    for unit, size in (("M", 1024 ** 2), ("K", 1024)):
        if n >= size:
            return f"{n / size:.1f}{unit}"
    return f"{n}B"


def cited_files(tuning_dir: Path) -> dict[str, str]:
    """`{basename: "path/to/doc.md:LINE"}` for every study_output file cited.

    First citation of a given file wins — the report only needs to show one
    place that still points at it.
    """
    out: dict[str, str] = {}
    for md in sorted(tuning_dir.glob("*.md")):
        try:
            text = md.read_text()
        except OSError:
            continue
        try:
            where = md.relative_to(ROOT)
        except ValueError:      # a tuning dir outside the repo (tests)
            where = md.name
        for lineno, line in enumerate(text.splitlines(), start=1):
            for name in _CITE_RE.findall(line):
                out.setdefault(name, f"{where}:{lineno}")
    return out


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
             citations: dict[str, str]) -> tuple[list[Path], list[tuple[Path, str]],
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
            where = citations.get(path.name)
            if where:
                pinned.append((path, f"cited {where}"))
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
