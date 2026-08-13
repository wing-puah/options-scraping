"""Study runner — run a tuning study, capture its output, hand it off for write-up.

Every study in this package prints a long plain-text report to stdout and is
meant to be read once, argued about, and then condensed into an addendum in
`config/backtest-tuning/current.md`. Before this runner, that meant remembering
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
then prints the path to paste into Claude for the write-up.

Outputs live under `backtests/` because they are data, not source — the whole
tree is gitignored scratch. The code lives here, under `scripts/`.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = "scripts.backtest_study"
STUDY_DIR = Path(__file__).resolve().parent
OUT_DIR = ROOT / "backtests" / "study_output"

# Shared data layer, not runnable studies (`book` is listed anyway — its
# --validate diagnostics table is the standard pre-flight before any study).
INFRA = {"__init__", "__main__", "run", "harness", "protocol", "underlying",
         "underlying_features"}

# Flags a study needs but has no sensible argparse default for. Applied only
# when the caller did not pass that flag themselves.
DEFAULT_ARGS = {
    "exit_mechanism_study": ["--side", "debit"],
    "combined_exit_study": ["--side", "debit"],
    "book": ["--validate"],
}

# Inputs whose identity decides whether two runs are comparable. Reported in
# every header so a write-up can never silently attribute numbers to the wrong
# export (this has happened — see current.md on the 07-22 vs 08-08 books).
INPUT_CSVS = [
    "backtests/to_evaluate/analysis - BacktestResults.csv",
    "backtests/to_evaluate/analysis - BacktestProxy.csv",
    "backtests/to_evaluate/analysis - AnalysisClaude.csv",
    "backtests/mech_regime/spy_vix_daily_full.csv",
]


def discover() -> dict[str, str]:
    """`{study_name: one-line summary}`, summary read from the module docstring.

    Parsed with `ast`, never imported: two studies (`mech_regime_recut`,
    `regime_gap_reread`) do their work at module level, so importing them to
    read a docstring would run the whole study.
    """
    out = {}
    for path in sorted(STUDY_DIR.glob("*.py")):
        if path.stem in INFRA:
            continue
        doc = ast.get_docstring(ast.parse(path.read_text())) or ""
        lines = [ln.strip() for ln in doc.strip().splitlines() if ln.strip()]
        out[path.stem] = lines[0] if lines else "(no docstring)"
    return out


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


def _input_inventory() -> list[str]:
    rows = []
    for rel in INPUT_CSVS:
        p = ROOT / rel
        if not p.exists():
            rows.append(f"  MISSING  {rel}")
            continue
        with p.open() as fh:
            n = sum(1 for _ in fh) - 1  # minus header
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        rows.append(f"  {n:>6,} rows  {mtime}  {rel}")
    return rows


def _header(name: str, argv: list[str]) -> str:
    dirty = "dirty" if _git("status", "--porcelain") else "clean"
    lines = [
        "=" * 78,
        f"STUDY: {name}",
        "=" * 78,
        f"  run at    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  command   python -m {PKG}.{name} {' '.join(argv)}".rstrip(),
        f"  git       {_git('rev-parse', '--short', 'HEAD')} "
        f"({_git('rev-parse', '--abbrev-ref', 'HEAD')}, working tree {dirty})",
        f"  python    {sys.version.split()[0]}",
        "  inputs:",
        *_input_inventory(),
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


def run_one(name: str, extra: list[str], dry_run: bool = False) -> tuple[int, Path]:
    argv = _merge_args(name, extra)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = OUT_DIR / f"{name}-{stamp}.txt"
    latest = OUT_DIR / f"{name}-latest.txt"
    cmd = [sys.executable, "-u", "-m", f"{PKG}.{name}", *argv]

    if dry_run:
        print(f"[dry-run] {' '.join(cmd)}  ->  {out_path}")
        return 0, out_path

    header = _header(name, argv)
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
    latest.write_text(out_path.read_text())
    return rc, out_path


def main() -> int:
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
    args, extra = ap.parse_known_args()

    if args.cmd != "run":
        width = max(len(n) for n in studies)
        print(f"Studies ({len(studies)}) — `python -m {PKG} run <name>`:\n")
        for name, doc in studies.items():
            default = " ".join(DEFAULT_ARGS.get(name, []))
            tag = f"  [default: {default}]" if default else ""
            print(f"  {name:{width}s}  {doc[:88]}{tag}")
        print(f"\nOutput goes to {OUT_DIR.relative_to(ROOT)}/<name>-latest.txt")
        return 0

    names = list(studies) if args.all else ([args.name] if args.name else [])
    if not names:
        ap.error("give a study name or --all (see `list`)")
    unknown = [n for n in names if n not in studies]
    if unknown:
        ap.error(f"unknown study {unknown[0]!r}; known: {', '.join(studies)}")

    results = []
    for name in names:
        rc, path = run_one(name, extra, args.dry_run)
        results.append((name, rc, path))

    if args.dry_run:
        return 0

    print("\n" + "=" * 78)
    print("DONE — paste this into Claude to get the write-up:\n")
    for name, rc, path in results:
        status = "" if rc == 0 else f"  *** FAILED rc={rc} ***"
        rel = (OUT_DIR / f"{name}-latest.txt").relative_to(ROOT)
        print(f"  write up {rel}{status}")
    print("=" * 78)
    return max(rc for _, rc, _ in results)


if __name__ == "__main__":
    raise SystemExit(main())
