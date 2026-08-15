"""The entry-point body both study_charts pages share.

Resolving the positions export, pairing it to a report from the same arm,
parsing, recomputing, reconciling, and writing the fragment plus the `site/`
copy is the same job whichever page is being drawn — and the rules that matter
most (write nothing when reconciliation fails; the structure arm never lands a
site page; no arm is ever written onto another arm's page) are rules that must
hold for every page, so they live here once rather than in each entry point.

Two arm axes, matched independently everywhere: `--structure-universe` and
`--compounding`. `site/` is generated output, rebuilt by `make study-docs`.

One thing happens before any of that (added 2026-08-16): if the report is a
DESIGNED REFUSAL — a study whose era is too thin to conclude from, see
`scripts/backtest_study/lib/era.py` — `run` prints it and exits 0 without
touching a byte on disk. See `skip_refused` for why each of those three
properties is there.

The `--docs`/`--no-docs` flags keep their old names as aliases of
`--site`/`--no-site`: they appear in study invocations recorded verbatim in
`research/`, and renaming them would invalidate those replication instructions.
"""
from __future__ import annotations

import argparse
import re
import sys
import webbrowser
from pathlib import Path
from typing import Callable

from scripts.study_charts import render, report, series

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "backtests" / "study_output"
SITE_DIR = ROOT / "site"
DEFAULT_POSITIONS = OUT_DIR / "account_sim-positions-latest.csv"

# A rendered page's own era, out of the JSON payload `render.build` embeds
# (`"report": {"provenance": {…, "era": "v3"}}`). Matched textually, on the
# FIRST occurrence, because the only caller is telling a human that the page
# they are about to read came from a different population than the one the
# study reads now — see `page_era`.
_PAGE_ERA_RE = re.compile(r'"era":\s*"([^"]*)"')


def is_structure_arm(positions: Path) -> bool:
    """The structure arm writes `account_sim-positions-structure-latest.csv`."""
    return "-structure" in positions.name


def is_compounding_arm(positions: Path) -> bool:
    """The compounding arm writes `account_sim-positions-compounding-latest.csv`.

    A second, INDEPENDENT axis from the structure one: a run can be either,
    both (`-positions-compounding-structure-latest.csv`) or neither, so every
    pairing check below matches on both rather than on whichever it thought of
    first.
    """
    return "-compounding" in positions.name


def arm_label(structure: bool, compounding: bool) -> str:
    """How to name an arm in an error message."""
    flags = [f for f, on in (("--compounding", compounding),
                             ("--structure-universe", structure)) if on]
    return " ".join(flags) if flags else "plain (frozen-book)"


def arm_of(positions: Path) -> str:
    return arm_label(is_structure_arm(positions), is_compounding_arm(positions))


def pick_report(positions: Path, out_dir: Path) -> Path:
    """Newest account_sim report whose command line matches the positions arm.

    Matched on BOTH arm axes. The glob is deliberately wide — every arm's
    report is `account_sim-*.txt` — so matching on one axis would let the
    frozen book's page pair with the compounding arm's report, which is exactly
    the silent mis-pairing this module exists to prevent.
    """
    want = (is_structure_arm(positions), is_compounding_arm(positions))
    candidates: list[tuple[float, Path]] = []
    for path in out_dir.glob("account_sim-*.txt"):
        if "-review-" in path.name or "-digest-" in path.name:
            continue
        try:
            prov = report.parse_provenance(report.Report(path.read_text(), path))
        except report.ReportParseError:
            continue
        if (prov["structure_arm"], prov["compound_arm"]) == want:
            candidates.append((path.stat().st_mtime, path))
    if not candidates:
        raise SystemExit(
            f"no account_sim report in {out_dir} was produced by a {arm_label(*want)} run.\n"
            f"Run the study first, or pass --report explicitly."
        )
    return max(candidates)[1]


def add_arguments(ap: argparse.ArgumentParser, site_name: str) -> None:
    ap.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS,
                    help="positions CSV exported by the study (default: the plain run's)")
    ap.add_argument("--report", type=Path,
                    help="report .txt to read the non-CSV sections from "
                         "(default: newest report matching the positions file's arm)")
    ap.add_argument("--out", type=Path, help="output path (default: alongside the study output)")
    ap.add_argument("--standalone", action="store_true",
                    help="wrap in a full HTML document for opening off disk "
                         "(the default fragment is what the Artifact publisher wants)")
    ap.add_argument("--site", "--docs", dest="site", type=Path,
                    help=f"also write a standalone copy here (default: site/{site_name}; "
                         "the structure arm writes no site copy at all, and no arm "
                         "may be written to another arm's page)")
    ap.add_argument("--no-site", "--no-docs", dest="write_site", action="store_false",
                    help="skip the site/ copy; write only --out")
    ap.add_argument("--open", dest="open_after", action="store_true", help="open the page when done")
    ap.add_argument("--capital", type=float, default=None,
                    help="account capital the study simulated (default: read out of the "
                         "report's own EQUITY CURVE section)")


def is_compounding_page(site_name: str) -> bool:
    """Whether a page's site filename is the compounding arm's own page."""
    return "-compounding" in site_name


def site_dest(positions: Path, site_name: str, site_dir: Path = SITE_DIR) -> Path | None:
    """Where the generated, double-clickable copy of this page lives, or None.

    Two rules, and both exist to stop one arm's numbers landing on another
    arm's page (`site/` is generated output, rebuilt by `make study-docs` — a
    page that quietly changed arm reads exactly like a page that did not).

    1. The structure-universe arm gets NO page. It is an exploratory widening
       of the candidate set that moves the book by a handful of picks, so its
       page reads the same as the frozen one chart for chart — two near
       identical pages cost a reader a diff to learn there was nothing to
       learn. Its scratch fragment under `backtests/study_output/` is what
       looking at that arm needs.
    2. The compounding arm HAS a page, its own (`account-sim-compounding.html`
       and friends), and may only be written there — never onto the frozen
       book's. The check runs both ways: the frozen book cannot be written onto
       the compounding page either.
    """
    if is_structure_arm(positions):
        return None
    if is_compounding_arm(positions) != is_compounding_page(site_name):
        return None
    return site_dir / site_name


def out_suffix(positions: Path, out_stem: str) -> str:
    """Arm marks the default fragment filename carries.

    Each arm's fragment needs its own name or the arms overwrite each other's
    scratch output. A mark the stem already states (the compounding page's stem
    is `account_sim-compounding-charts`) is not repeated.
    """
    marks = ((is_compounding_arm(positions), "-compounding"),
             (is_structure_arm(positions), "-structure"))
    return "".join(mark for on, mark in marks if on and mark not in out_stem)


def default_out(positions: Path, out_stem: str) -> Path:
    """The scratch fragment this arm writes when `--out` is not given."""
    return positions.parent / f"{out_stem}{out_suffix(positions, out_stem)}-latest.html"


def page_era(path: Path) -> str:
    """The era the rendered page at `path` was built from, or `?`.

    Every page embeds its whole parsed report as JSON, so the era the run
    recorded is already on disk — no sidecar needed. Read with a regex rather
    than by loading the payload: this is called on a page that may predate the
    era line entirely (or be absent, or be some older hand-made file), and the
    honest answer in all of those cases is "unknown", never an exception.

    `?` is `report.UNKNOWN_ERA` on purpose — the same marker a report with no
    era line parses to, so "we do not know" reads identically wherever it is
    printed rather than looking like two different states.
    """
    try:
        text = path.read_text()
    except OSError:
        return report.UNKNOWN_ERA
    m = _PAGE_ERA_RE.search(text)
    return m.group(1) if m else report.UNKNOWN_ERA


def skip_refused(refused: report.Refusal, report_path: Path, positions: Path,
                 *, out: Path, site: Path | None, module: str) -> int:
    """Report a study's designed refusal and write NOTHING. Always exit 0.

    Three properties, all of which cost something to get wrong:

    1. Exit 0. A refusal is the study's correct current status, not a build
       failure, and `make study-docs` must finish so the pages that CAN be
       rebuilt are.
    2. Nothing on disk is touched — not overwritten, not deleted. The pages
       already there were rendered from a real run of some earlier era, and a
       blank or half-drawn page would destroy the last good visualisation to
       report news that fits in four lines of text.
    3. The pages that survive are named as STALE, with the era they were built
       from set against the era that just refused. Point 2 leaves a page on
       disk that looks exactly as current as it did yesterday; a stale page
       that silently reads as current is the failure the whole era change set
       exists to remove, and re-introducing it here — at the last step, in the
       artifact a human actually looks at — would undo the lot.
    """
    print(f"SKIPPED — the study REFUSED on era {refused.era}; there is nothing new to draw.")
    print(f"  report      {report_path}")
    for line in refused.message.splitlines():
        print(f"  study says  {line.strip()}" if line.strip() else "  study says")
    print(f"  positions   {positions}" + ("" if positions.exists() else "  (not written)"))
    kept = [p for p in (out, site) if p is not None and p.exists()]
    for page in kept:
        built = page_era(page)
        # Three cases, and the unknown one is NOT collapsed into the mismatch
        # one: a page that records no era cannot be SHOWN to disagree with the
        # current one, and asserting that it does would be inventing the very
        # fact the era line was added to stop people inventing.
        if built == report.UNKNOWN_ERA:
            era_note = (f"records no era of its own, so it cannot be shown to match the "
                        f"current era {refused.era} — read it as stale until it is redrawn")
        elif built != refused.era:
            era_note = (f"built from era {built}, and the current era is {refused.era} — "
                        f"it is NOT a picture of what the study reads today")
        else:
            era_note = f"built from era {built}, the same era that just refused"
        print(f"  KEPT STALE  {page}  ({era_note})")
    if not kept:
        print("  no page      nothing had been rendered here yet — none was written now")
    print(f"  wrote       nothing  [{module}]")
    return 0


def run(args: argparse.Namespace, *, build: Callable[..., str],
        out_stem: str, site_name: str, module: str) -> int:
    """Draw one page. Returns the process exit code."""
    positions = args.positions.resolve()
    # An explicit --site is refused rather than honoured whenever this arm has
    # no page of its own: a hand-typed path is exactly how one arm's numbers
    # land on another arm's page, and the scratch fragment already covers
    # looking at any arm.
    if args.site and site_dest(positions, site_name) is None:
        if is_structure_arm(positions):
            raise SystemExit(
                "the --structure-universe arm writes no site page "
                f"(--site {args.site} refused). Its scratch fragment under "
                "backtests/study_output/ is the way to view it; add --standalone to open it."
            )
        raise SystemExit(
            f"wrong page for this arm: site/{site_name} is "
            f"{'the compounding arm' if is_compounding_page(site_name) else 'the frozen book'}'s "
            f"page, but {positions.name} is the {arm_of(positions)} arm's export "
            f"(--site {args.site} refused). Each arm writes only its own page."
        )
    report_path = (args.report or pick_report(positions, positions.parent)).resolve()
    if not report_path.exists():
        raise SystemExit(f"report not found: {report_path}")

    # BEFORE parsing, and before the positions CSV is required: a study that
    # REFUSED (era too thin to conclude from) wrote a report with a provenance
    # header, its refusal, and nothing else, and may not have written a
    # positions CSV at all. Parsing it produced a ReportParseError naming
    # whichever section happened to be missing first — a true statement about
    # the wrong problem. The order here is load-bearing: check what the report
    # IS before demanding the inputs a real report would need.
    if refused := report.read_refusal(report_path):
        return skip_refused(refused, report_path, positions,
                            out=args.out or default_out(positions, out_stem),
                            site=(args.site or site_dest(positions, site_name)
                                  if args.write_site else None),
                            module=module)

    if not positions.exists():
        raise SystemExit(f"positions CSV not found: {positions}")

    parsed = report.parse(report_path)
    rows = series.load(positions)

    prov = parsed["provenance"]
    if (prov["structure_arm"], prov["compound_arm"]) != (is_structure_arm(positions),
                                                         is_compounding_arm(positions)):
        raise SystemExit(
            f"arm mismatch: {report_path.name} ran `{prov['command']}` but "
            f"{positions.name} is the {arm_of(positions)} arm's export."
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

    out = args.out or default_out(positions, out_stem)
    out.write_text(page)

    print(f"report      {report_path}")
    print(f"positions   {positions}")
    for pop in report.POPULATIONS:
        s = populations[pop]["summary"]
        print(f"  {pop:<10} {s['n']:>4} positions  {s['dates']:>3} dates  "
              f"${s['dollars']:>9,.0f}  meanR {s['meanR']:+.3f}  reconciled OK")
    print(f"wrote       {out}  ({len(page):,} bytes, "
          f"{'standalone' if args.standalone else 'artifact fragment'})  [{module}]")

    # The site copy is always standalone whatever --standalone did to `out`:
    # its whole job is to be opened straight from a checkout.
    site = None
    if args.write_site:
        dest = args.site or site_dest(positions, site_name)
        if dest is None:
            why = ("the structure arm gets no site page" if is_structure_arm(positions)
                   else f"site/{site_name} is not the {arm_of(positions)} arm's page")
            print(f"site copy   skipped — {why}")
        else:
            site = dest.resolve()
            site.parent.mkdir(parents=True, exist_ok=True)
            site.write_text(render.wrap_standalone(fragment))
            print(f"wrote       {site}  (standalone, generated)")

    if args.open_after:
        # A fragment opened off disk has no doctype or charset, so prefer a
        # standalone file whenever this run wrote one.
        webbrowser.open((out if args.standalone else site or out).as_uri())
    return 0
