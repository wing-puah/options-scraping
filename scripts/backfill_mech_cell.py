"""Backfill the `mech_cell` column on every analysis tab.

`mech_cell` (lib/mech_regime.py) is the mechanical market-regime cell for a
signal date — BEAR_HE / LVOL / RB_EVOL / NONE — and it is what the operator
reads at deploy time to pick the exit profile (config/deployment-rules.md
§"Exit management"). The analysis pipeline stamps it on rows it writes, but:

  - every row written BEFORE the column shipped (2026-07-22) has a blank cell, and
  - any row written while the SPY/VIX table was missing or stale carries NO_DATA.

Both are backfillable, because the label is a pure, frozen function of the date
and the SPY/VIX table — not of anything that was only knowable at run time.

Behaviour: recomputes every row's cell, then
  - fills blanks and NO_DATA,
  - KEEPS an existing concrete label that disagrees with the recomputed one and
    logs it as DRIFT (a real label should never change; a disagreement means the
    table or the spec moved, which is a finding, not something to paper over),
  - `--force` overwrites the drifted cells too.

Only the `mech_cell` column is touched (sheets_client.add_or_update_column), so
user formulas and every other column are left alone, and the header gains the
column if the tab predates it.

The SPY/VIX table is NOT fetched here — refresh it first with `make mech-regime`
(or `python scripts/collector/fetch_mech_regime.py --download`), same contract as
`make backtest` / `make analyze`. A table that stops short of a row's date leaves
that row NO_DATA rather than labelling it off a stale close.

Run:
    python scripts/backfill_mech_cell.py                 # all analysis tabs
    python scripts/backfill_mech_cell.py --dry-run
    python scripts/backfill_mech_cell.py --tab AnalysisClaude
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib import sheets_client  # noqa: E402
from lib.logger import setup_logging  # noqa: E402
from lib.mech_regime import NO_DATA, cell_for_date  # noqa: E402
from scripts.analysis_pipeline import config  # noqa: E402

log = logging.getLogger("backfill_mech_cell")

COLUMN = "mech_cell"
DATE_COLUMN = "date"

# Every tab written by analysis_pipeline with the ROW_COLUMNS schema.
DEFAULT_TABS = [e.tab for e in config.ENGINES.values()] + [config.TICKER_SPECIFIC_TAB]

# Values that mean "no answer was recorded", and are therefore safe to overwrite
# without --force. A blank is a pre-column row; NO_DATA is a row written while the
# table could not answer.
REFILLABLE = ("", NO_DATA)

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_US = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def _norm_date(raw: str) -> str | None:
    """Sheet cell -> 'YYYY-MM-DD', or None if it is not a date.

    Rows are written RAW as ISO strings, but a tab someone has reformatted can
    read back as M/D/YYYY. Anything else is not guessed at — an unlabelled row is
    better than a row labelled off a misparsed date.
    """
    s = (raw or "").strip()
    for pattern, fmt in ((_ISO, "%Y-%m-%d"), (_US, "%m/%d/%Y")):
        if pattern.match(s):
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except ValueError:      # e.g. '21/04/2026' — D/M, not M/D. Never guessed.
                return None
    return None


def plan_tab(header: list[str], rows: list[list[str]], csv_path: Path,
             force: bool) -> tuple[list[str], dict]:
    """`(column values in sheet order, stats)` for one tab. Pure — no I/O."""
    stats = dict(rows=len(rows), filled=0, unchanged=0, drift=0, overwritten=0,
                 no_date=0, no_data=0)
    date_i = header.index(DATE_COLUMN)
    cell_i = header.index(COLUMN) if COLUMN in header else None

    # cell_for_date re-reads and re-labels the whole table per call; the book has
    # far more rows than trading dates, so answer each date once.
    memo: dict[str, str] = {}
    out: list[str] = []
    for row in rows:
        existing = (row[cell_i].strip() if cell_i is not None and cell_i < len(row) else "")
        raw_date = row[date_i] if date_i < len(row) else ""
        d = _norm_date(raw_date)
        if d is None:
            stats["no_date"] += 1
            out.append(existing or NO_DATA)
            continue

        if d not in memo:
            value, warning = cell_for_date(csv_path, d)
            if warning:
                log.warning("mech_cell unavailable for %s: %s", d, warning)
            memo[d] = value
        computed = memo[d]
        if computed == NO_DATA:
            stats["no_data"] += 1

        if existing == computed:
            stats["unchanged"] += 1
            out.append(existing)
        elif existing in REFILLABLE:
            stats["filled"] += 1
            out.append(computed)
        else:
            # A concrete label that no longer reproduces. Never silently replaced.
            stats["drift"] += 1
            log.warning("DRIFT %s: stored %s, recomputed %s%s",
                        d, existing, computed, " — overwriting (--force)" if force else "")
            if force:
                stats["overwritten"] += 1
                out.append(computed)
            else:
                out.append(existing)
    return out, stats


def backfill_tab(tab: str, csv_path: Path, force: bool, dry_run: bool) -> dict:
    header, rows = sheets_client.get_all_values(tab)
    if not header:
        log.info("%s: empty tab, nothing to backfill", tab)
        return dict(rows=0, filled=0, unchanged=0, drift=0, overwritten=0,
                    no_date=0, no_data=0, skipped=True)
    if DATE_COLUMN not in header:
        log.error("%s: no '%s' column in the header — skipped", tab, DATE_COLUMN)
        return dict(rows=len(rows), filled=0, unchanged=0, drift=0, overwritten=0,
                    no_date=0, no_data=0, skipped=True)

    values, stats = plan_tab(header, rows, csv_path, force)
    changed = stats["filled"] + stats["overwritten"]
    log.info("%s: %d row(s) — %d to fill, %d already correct, %d drift (%d overwritten), "
             "%d unlabelled dates, %d NO_DATA",
             tab, stats["rows"], stats["filled"], stats["unchanged"], stats["drift"],
             stats["overwritten"], stats["no_date"], stats["no_data"])
    if dry_run:
        log.info("%s: dry run — no write", tab)
    elif changed or COLUMN not in header:
        sheets_client.add_or_update_column(tab, COLUMN, values)
    else:
        log.info("%s: nothing to write", tab)
    stats["skipped"] = False
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tab", action="append", dest="tabs",
                    help="tab to backfill (repeatable); default = every analysis tab")
    ap.add_argument("--csv", default=None,
                    help=f"SPY/VIX table (default: {config.MECH_REGIME_CSV})")
    ap.add_argument("--force", action="store_true",
                    help="also overwrite stored labels that no longer reproduce")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()

    setup_logging()
    csv_path = Path(args.csv) if args.csv else ROOT / config.MECH_REGIME_CSV
    if not csv_path.exists():
        log.error("SPY/VIX table not found at %s — run `make mech-regime` first; "
                  "backfilling now would write NO_DATA over the whole book", csv_path)
        return 1

    tabs = args.tabs or DEFAULT_TABS
    total = dict(rows=0, filled=0, unchanged=0, drift=0, overwritten=0, no_date=0, no_data=0)
    for tab in tabs:
        stats = backfill_tab(tab, csv_path, force=args.force, dry_run=args.dry_run)
        for k in total:
            total[k] += stats.get(k, 0)
    log.info("Done: %d row(s) across %d tab(s) — %d filled, %d drift (%d overwritten)",
             total["rows"], len(tabs), total["filled"], total["drift"], total["overwritten"])
    # Drift left in place is a condition a human must look at, so it is visible in
    # the job's exit status rather than only in the log.
    return 2 if (total["drift"] and not args.force) else 0


if __name__ == "__main__":
    sys.exit(main())
