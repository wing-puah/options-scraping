"""Download the analysis workbook's tabs into `backtests/to_evaluate/` as CSV.

The study tier reads exported CSVs, never the live tabs — `lib/era.py` resolves
`backtests/to_evaluate/analysis - <Tab>.csv` and every study loads from there.
Until now those files arrived by hand ("File → Download → CSV" in the Sheets
UI), which is why `clean_generated.py` protects the directory and
`backup_research_caches.py` calls it irreplaceable. This makes the fetch a
command, using the SAME export endpoint the UI button hits, so the bytes match
what a hand export produced.

An existing file of the same name is OVERWRITTEN — that is the point: the bare
exports mean "whatever the live tabs hold now".

--- Why this is not just a loop of GETs -------------------------------------
`era.enforce()` refuses a HALF-FINISHED re-export: three files that disagree
about their prompt-version era are worse than either era alone, and on
2026-08-15 a silent era change under the bare filenames invalidated nineteen
study reports (see the `era.py` docstring). So this script:

  1. downloads every requested tab to a temp dir FIRST — a failure or a killed
     run leaves the existing exports untouched, never a mixed set;
  2. refuses an empty or header-only download, which would otherwise install a
     truncated export that `detect_era` cannot even classify;
  3. checks the era of the freshly downloaded set BEFORE installing it, and
     refuses (exit 3) if they disagree with each other — mid-rename tabs;
  4. installs them with `os.replace`, one file at a time but only after every
     download has already succeeded;
  5. REPORTS an era change against what was on disk, loudly. That is not an
     error — a version bump is legitimate — but every `-latest.txt` report and
     every research/study-results section written on the old era now describes
     a population that no longer exists behind that filename. Re-run the suite
     (`make study-all RECORD=1`) after an era change.

Run:
    python3 scripts/export_tabs.py                       # the three era exports
    python3 scripts/export_tabs.py --dry-run             # fetch + report, install nothing
    python3 scripts/export_tabs.py --tabs v3_AnalysisClaude,v3_BacktestResults
    python3 scripts/export_tabs.py --list                # tab names in the workbook
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from google.auth.transport.requests import AuthorizedSession  # noqa: E402

from lib import sheets_client  # noqa: E402
from lib.logger import setup_logging  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402

log = logging.getLogger(__name__)

# The tabs a bare study run reads. Taken from `era.EXPORTS` rather than restated,
# so adding a fourth export to the era contract adds it here too.
DEFAULT_TABS: list[str] = list(era.EXPORTS.values())

# The exported filename. The "analysis - " prefix is the SPREADSHEET TITLE a
# hand export prepends, but it is hardcoded here on purpose: it is the name
# `era.resolve_paths()` looks for, so renaming the workbook must NOT rename the
# files the studies read. `_dest_for` asserts the two agree.
FILENAME = "analysis - {tab}.csv"

# Columns that carry the signal date, by export. Only used for the "N dates"
# line in the summary — `era.require_dates` is what actually gates a study.
DATE_COLS = ("date", "signal_date")

EXIT_ERA_MISMATCH = era.EXIT_ERA_MISMATCH  # 3


def _export_key(tab: str) -> str | None:
    """The `era.EXPORTS` key `tab` is an export of, ignoring any era prefix.

    `BacktestResults` and `v3_BacktestResults` both answer "results";
    `BaselineDaily` answers None — it is not versioned, so it has no era.
    """
    for key, name in era.EXPORTS.items():
        if tab == name or tab.endswith(f"_{name}"):
            return key
    return None


def _prefix_of(tab: str) -> str:
    """`"v3_"` for `v3_BacktestResults`, `""` for the bare (current) export."""
    key = _export_key(tab)
    return "" if key is None else tab[: len(tab) - len(era.EXPORTS[key])]


def _dest_for(tab: str, dest_dir: Path) -> Path:
    """Destination path for `tab`, cross-checked against the era contract."""
    path = dest_dir / FILENAME.format(tab=tab)
    if dest_dir == era.EVAL_DIR:
        for key, name in era.EXPORTS.items():
            if name == tab:
                expected = era.resolve_paths(era.CURRENT)[key]
                assert path == expected, (
                    f"filename drift: this script would write {path.name}, but "
                    f"studies read {expected.name}"
                )
    return path


def _download(session: AuthorizedSession, sheet_id: str, gid: int, out: Path) -> None:
    """Fetch one tab as CSV — the same endpoint the Sheets UI download uses."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
           f"?format=csv&gid={gid}")
    resp = session.get(url, timeout=300)
    resp.raise_for_status()
    out.write_bytes(resp.content)


def _row_count(path: Path) -> int:
    """Data rows (header excluded), counting CSV records not physical lines."""
    import csv
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def _date_count(path: Path) -> int | None:
    """Distinct signal dates in `path`, or None if it carries no date column."""
    import csv
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        col = next((c for c in DATE_COLS if c in (reader.fieldnames or [])), None)
        if col is None:
            return None
        return len({(r.get(col) or "").strip() for r in reader} - {""})


def _era_of(path: Path) -> str:
    """`detect_era`, degraded to a label rather than raising on an empty file."""
    try:
        return era.detect_era(path)
    except (ValueError, OSError):
        return "?"


def _fail(code: int, msg: str) -> None:
    print(f"\nexport-tabs: {msg}", file=sys.stderr)
    sys.exit(code)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tabs", help="comma-separated tab names "
                                   f"(default: {','.join(DEFAULT_TABS)})")
    ap.add_argument("--dest", type=Path, default=era.EVAL_DIR,
                    help="destination directory (default: backtests/to_evaluate)")
    ap.add_argument("--list", action="store_true",
                    help="list the workbook's tabs and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="download and report, but install nothing")
    ap.add_argument("--allow-empty", action="store_true",
                    help="install a header-only export (default: refuse)")
    ap.add_argument("--force", action="store_true",
                    help="install even if the downloaded exports disagree about "
                         "their era (a half-finished re-export — almost never right)")
    args = ap.parse_args()

    setup_logging(logging.INFO)

    ss = sheets_client._get_spreadsheet()
    gids = {ws.title: ws.id for ws in ss.worksheets()}

    if args.list:
        print(f"{ss.title}:")
        for title in sorted(gids):
            print(f"  {title}")
        return 0

    tabs = [t.strip() for t in args.tabs.split(",")] if args.tabs else list(DEFAULT_TABS)
    tabs = [t for t in tabs if t]
    missing = [t for t in tabs if t not in gids]
    if missing:
        _fail(2, f"no such tab in {ss.title!r}: {', '.join(missing)}\n"
                 f"  available: {', '.join(sorted(gids))}")

    dest_dir: Path = args.dest
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Everything lands in a temp dir first; nothing existing is touched until
    # every download has succeeded and the set has passed its era check.
    session = AuthorizedSession(sheets_client.load_credentials())
    staging = Path(tempfile.mkdtemp(prefix=".export-tabs-", dir=dest_dir))
    try:
        staged: dict[str, Path] = {}
        for tab in tabs:
            tmp = staging / FILENAME.format(tab=tab)
            log.info("Downloading tab '%s' (gid %s)", tab, gids[tab])
            _download(session, ss.id, gids[tab], tmp)
            staged[tab] = tmp

        empty = [t for t, p in staged.items() if _row_count(p) == 0]
        if empty and not args.allow_empty:
            _fail(2, "these tabs exported with no data rows — installing them "
                     "would replace a real export with a truncated one:\n"
                     + "\n".join(f"    {t}" for t in empty)
                     + "\n  Re-export once the tab has rows, or pass --allow-empty.")

        # Era check on the DOWNLOADED set, before it can become the set on disk.
        # Grouped BY PREFIX, so `--tabs v3_BacktestResults,v3_BacktestProxy` is
        # checked the same way the bare three are. Deliberately NOT a check that
        # the detected era matches the prefix: `detect_era` discriminates v3 from
        # NOT-v3 (its docstring says so), so a v1_/v2_ tab correctly reads "v3"
        # and a prefix-equality test would refuse a perfectly good pull.
        eras = {t: _era_of(p) for t, p in staged.items() if _export_key(t)}
        groups: dict[str, dict[str, str]] = {}
        for tab, detected in eras.items():
            groups.setdefault(_prefix_of(tab), {})[tab] = detected
        for prefix, group in groups.items():
            distinct = {e for e in group.values() if e != "?"}
            if len(distinct) > 1 and not args.force:
                lines = "\n".join(f"    {group[t]:<3} {t}" for t in sorted(group))
                label = "the bare exports" if prefix == "" else f"the {prefix[:-1]} exports"
                _fail(EXIT_ERA_MISMATCH,
                      f"{label} disagree about their era — the tabs are "
                      f"mid-rename, or a bump is half-done:\n{lines}\n"
                      "  Nothing was installed. Re-run once every tab in the "
                      "set holds the same prompt version.")

        # What each file was BEFORE, so the summary can name an era change.
        before = {t: (_dest_for(t, dest_dir)) for t in tabs}
        prior = {t: (_era_of(p) if p.exists() and _export_key(t) else None)
                 for t, p in before.items()}
        prior_rows = {t: (_row_count(p) if p.exists() else None)
                      for t, p in before.items()}

        print()
        print(f"{'tab':<24} {'rows':>7} {'dates':>6} {'era':>4}   was")
        for tab in tabs:
            p = staged[tab]
            dates = _date_count(p)
            was = "—" if prior_rows[tab] is None else f"{prior_rows[tab]:,} rows"
            if prior[tab]:
                was += f", {prior[tab]}"
            print(f"{tab:<24} {_row_count(p):>7,} "
                  f"{('' if dates is None else dates):>6} "
                  f"{eras.get(tab, '—'):>4}   {was}")

        changed = [t for t in tabs
                   if prior[t] and eras.get(t) not in (None, "?") and prior[t] != eras[t]]
        if changed:
            print()
            print("  !! ERA CHANGE — these filenames now name a DIFFERENT population:")
            for t in changed:
                print(f"       {FILENAME.format(tab=t)}: {prior[t]} -> {eras[t]}")
            print("     Every study report and research/study-results section written")
            print("     against the old era describes a book that no longer sits behind")
            print("     that name. Re-run the suite:  make study-all RECORD=1")

        if args.dry_run:
            print("\ndry run — nothing installed")
            return 0

        for tab in tabs:
            os.replace(staged[tab], before[tab])
        print(f"\nwrote {len(tabs)} file(s) to {dest_dir}")
        return 0
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
