"""Realign an analysis tab's header row with `config.ROW_COLUMNS`.

`sheets_client.append_rows` writes values POSITIONALLY, so a tab whose header
stopped short of the schema mislabels every column after the gap — and any
column-keyed write (e.g. `add_or_update_column`) lands in the wrong place. This
is the failure CLAUDE.md warns about when a column is appended to ROW_COLUMNS:
the tab header must gain it too. AnalysisGPT and AnalysisTickerSpecific had both
drifted (missing `iv_pct`, `price_vector`, `days_to_earnings`, `iv_skew`,
`score_catalyst`; old CamelCase conviction names), which is what this repairs.

SAFETY: values are never moved between columns. A tab is repaired only when every
data cell to the right of the last agreeing header column is EMPTY, apart from
columns whose header name also exists in the target schema (those are relocated
to their schema position). Anything else aborts that tab untouched — realigning a
tab whose rows already carry data under drifted headers needs a per-column
mapping decision a script must not guess at.

Run:
    python scripts/align_tab_headers.py --dry-run
    python scripts/align_tab_headers.py --tab AnalysisGPT
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib import sheets_client  # noqa: E402
from lib.logger import setup_logging  # noqa: E402
from scripts.analysis_pipeline import config  # noqa: E402

log = logging.getLogger("align_tab_headers")

DEFAULT_TABS = [e.tab for e in config.ENGINES.values()] + [config.TICKER_SPECIFIC_TAB]


def plan(header: list[str], rows: list[list[str]],
         target: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """`(relocations, blockers)` for one tab. Pure — no I/O.

    `relocations` maps a target column name to its data values (in sheet order)
    for every column that must move. `blockers` is non-empty when the tab cannot
    be repaired safely, and names why.
    """
    if header == target:
        return {}, []

    agree = 0
    while agree < min(len(header), len(target)) and header[agree] == target[agree]:
        agree += 1

    relocations: dict[str, list[str]] = {}
    blockers: list[str] = []
    for j in range(agree, len(header)):
        col = [(r[j] if j < len(r) else "") for r in rows]
        if not any(c.strip() for c in col):
            continue                       # empty column — nothing to preserve
        if header[j] in target:
            relocations[header[j]] = col   # same column, wrong position
        else:
            blockers.append(f"column {j + 1} ('{header[j]}') holds data but is not "
                            f"in the schema")
    return relocations, blockers


def align_tab(tab: str, dry_run: bool) -> bool:
    """True when the tab ends up matching the schema (or already did)."""
    header, rows = sheets_client.get_all_values(tab)
    target = list(config.ROW_COLUMNS)
    if not header:
        log.info("%s: empty tab — nothing to align", tab)
        return True
    if header == target:
        log.info("%s: header already matches the schema (%d cols)", tab, len(target))
        return True

    relocations, blockers = plan(header, rows, target)
    log.info("%s: header %d cols vs schema %d — %s",
             tab, len(header), len(target),
             ", ".join(f"+{c}" for c in target if c not in header) or "reorder only")
    if blockers:
        for b in blockers:
            log.error("%s: ABORT — %s", tab, b)
        return False
    if dry_run:
        log.info("%s: dry run — would rewrite the header and move %d column(s): %s",
                 tab, len(relocations), ", ".join(relocations) or "none")
        return True

    ss = sheets_client._get_spreadsheet()
    ws = ss.worksheet(tab)
    if len(target) > ws.col_count:
        ws.add_cols(len(target) - ws.col_count)
    # Clear the drifted columns BEFORE rewriting the header, so a relocated column
    # is never briefly present twice.
    stale = [sheets_client._col_letter(j + 1) for j in range(len(header))
             if j >= len(target) or header[j] != target[j]]
    if rows and stale:
        ws.batch_clear([f"{c}2:{c}{len(rows) + 1}" for c in stale])
    ws.update("A1", [target], value_input_option="USER_ENTERED")
    for name, values in relocations.items():
        sheets_client.add_or_update_column(tab, name, values)
    log.info("%s: header realigned to %d cols; moved %s",
             tab, len(target), ", ".join(relocations) or "no data columns")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tab", action="append", dest="tabs",
                    help="tab to align (repeatable); default = every analysis tab")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()

    setup_logging()
    ok = all([align_tab(tab, args.dry_run) for tab in (args.tabs or DEFAULT_TABS)])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
