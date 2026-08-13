"""The entry-point body both study_charts pages share.

Resolving the positions export, pairing it to a report from the same arm,
parsing, recomputing, reconciling, and writing the fragment plus the tracked
docs copy is the same job whichever page is being drawn — and the rules that
matter most (write nothing when reconciliation fails; the structure arm never
lands a tracked page) are rules that must hold for every page, so they live
here once rather than in each entry point.
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path
from typing import Callable

from scripts.study_charts import render, report, series

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "backtests" / "study_output"
DOCS_DIR = ROOT / "docs"
DEFAULT_POSITIONS = OUT_DIR / "account_sim-positions-latest.csv"


def is_structure_arm(positions: Path) -> bool:
    """The structure arm writes `account_sim-positions-structure-latest.csv`."""
    return "-structure" in positions.name


def pick_report(positions: Path, out_dir: Path) -> Path:
    """Newest account_sim report whose command line matches the positions arm."""
    want_structure = is_structure_arm(positions)
    candidates: list[tuple[float, Path]] = []
    for path in out_dir.glob("account_sim-*.txt"):
        if "-review-" in path.name or "-digest-" in path.name:
            continue
        try:
            prov = report.parse_provenance(report.Report(path.read_text(), path))
        except report.ReportParseError:
            continue
        if prov["structure_arm"] == want_structure:
            candidates.append((path.stat().st_mtime, path))
    if not candidates:
        arm = "--structure-universe" if want_structure else "the plain (frozen-book)"
        raise SystemExit(
            f"no account_sim report in {out_dir} was produced by {arm} run.\n"
            f"Run the study first, or pass --report explicitly."
        )
    return max(candidates)[1]


def add_arguments(ap: argparse.ArgumentParser, docs_name: str) -> None:
    ap.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS,
                    help="positions CSV exported by the study (default: the plain run's)")
    ap.add_argument("--report", type=Path,
                    help="report .txt to read the non-CSV sections from "
                         "(default: newest report matching the positions file's arm)")
    ap.add_argument("--out", type=Path, help="output path (default: alongside the study output)")
    ap.add_argument("--standalone", action="store_true",
                    help="wrap in a full HTML document for opening off disk "
                         "(the default fragment is what the Artifact publisher wants)")
    ap.add_argument("--docs", type=Path,
                    help=f"also write a standalone copy here (default: docs/{docs_name}; "
                         "the structure arm writes no tracked copy at all)")
    ap.add_argument("--no-docs", dest="write_docs", action="store_false",
                    help="skip the tracked docs/ copy; write only --out")
    ap.add_argument("--open", dest="open_after", action="store_true", help="open the page when done")
    ap.add_argument("--capital", type=float, default=None,
                    help="account capital the study simulated (default: read out of the "
                         "report's own EQUITY CURVE section)")


def docs_dest(positions: Path, docs_name: str, docs_dir: Path = DOCS_DIR) -> Path | None:
    """Where the tracked, double-clickable copy of this page lives, or None.

    Only the frozen book gets a tracked page. The structure-universe arm is an
    exploratory widening of the candidate set that moves the book by a handful
    of picks, so its page reads the same as the frozen one chart for chart —
    two near-identical tracked pages cost a reader a diff to learn there was
    nothing to learn. It still writes its scratch fragment under
    `backtests/study_output/`, which is what looking at the widened arm needs.
    """
    if is_structure_arm(positions):
        return None
    return docs_dir / docs_name


def run(args: argparse.Namespace, *, build: Callable[..., str],
        out_stem: str, docs_name: str, module: str) -> int:
    """Draw one page. Returns the process exit code."""
    positions = args.positions.resolve()
    if not positions.exists():
        raise SystemExit(f"positions CSV not found: {positions}")
    # An explicit --docs is refused rather than honoured on the widened arm:
    # a hand-typed path is exactly how the frozen book's tracked page gets
    # clobbered, and the scratch fragment already covers looking at this arm.
    if args.docs and is_structure_arm(positions):
        raise SystemExit(
            "the --structure-universe arm writes no tracked docs page "
            f"(--docs {args.docs} refused). Its scratch fragment under "
            "backtests/study_output/ is the way to view it; add --standalone to open it."
        )
    report_path = (args.report or pick_report(positions, positions.parent)).resolve()
    if not report_path.exists():
        raise SystemExit(f"report not found: {report_path}")

    parsed = report.parse(report_path)
    rows = series.load(positions)

    if parsed["provenance"]["structure_arm"] != is_structure_arm(positions):
        raise SystemExit(
            f"arm mismatch: {report_path.name} ran `{parsed['provenance']['command']}` but "
            f"{positions.name} is the {'structure' if is_structure_arm(positions) else 'plain'} arm's export."
        )

    # No --capital given: take the study's own figure out of the report rather
    # than assume one, so a config-driven capital never needs a second, silently
    # stale copy here. This is what keeps series.reconcile()'s capital check
    # self-consistent — it compares the CSV-derived capital against this same
    # report field.
    capital = args.capital
    if capital is None:
        capital = parsed["populations"]["primary"]["equity"]["capital"]

    populations, problems = {}, []
    for pop in report.POPULATIONS:
        derived = series.build(rows, pop, capital)
        problems += series.reconcile(derived, parsed, pop)
        populations[pop] = derived

    if problems:
        print(f"reconciliation FAILED — {report_path.name} and {positions.name} do not describe the same run:",
              file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    source = {"report": report_path.name, "positions": positions.name}
    fragment = build(parsed, populations, capital, source)
    page = render.wrap_standalone(fragment) if args.standalone else fragment

    suffix = "-structure" if is_structure_arm(positions) else ""
    out = args.out or (positions.parent / f"{out_stem}{suffix}-latest.html")
    out.write_text(page)

    print(f"report      {report_path}")
    print(f"positions   {positions}")
    for pop in report.POPULATIONS:
        s = populations[pop]["summary"]
        print(f"  {pop:<10} {s['n']:>4} positions  {s['dates']:>3} dates  "
              f"${s['dollars']:>9,.0f}  meanR {s['meanR']:+.3f}  reconciled OK")
    print(f"wrote       {out}  ({len(page):,} bytes, "
          f"{'standalone' if args.standalone else 'artifact fragment'})  [{module}]")

    # The docs copy is always standalone whatever --standalone did to `out`:
    # its whole job is to be opened straight from a checkout.
    docs = None
    if args.write_docs:
        dest = args.docs or docs_dest(positions, docs_name)
        if dest is None:
            print("docs copy   skipped — the structure arm gets no tracked page")
        else:
            docs = dest.resolve()
            docs.parent.mkdir(parents=True, exist_ok=True)
            docs.write_text(render.wrap_standalone(fragment))
            print(f"wrote       {docs}  (standalone, tracked)")

    if args.open_after:
        # A fragment opened off disk has no doctype or charset, so prefer a
        # standalone file whenever this run wrote one.
        webbrowser.open((out if args.standalone else docs or out).as_uri())
    return 0
