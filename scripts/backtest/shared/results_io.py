import csv
import logging
from datetime import datetime, timezone

from lib import sheets_client

from ..config import RESULTS_PATH

log = logging.getLogger("backtest")

# RESULTS_PATH = <repo root>/backtests, so its parent is the repo root — same
# value core.py's own ``ROOT`` resolves to, computed once here instead of via a
# second ``Path(__file__)`` walk (this module lives one directory deeper).
ROOT = RESULTS_PATH.parent


def write_results(results, *, key_order, local_csv=None, sheet_tab=None,
                  dry_run=False, summary_fn=None) -> None:
    """Write backtest results to a local CSV (archiving any previous file) and
    optionally append to a Google Sheets tab.

    Generalized over the output schema (``key_order``), destination path
    (``local_csv``, relative to the repo root — defaults to a timestamped
    ``backtests/results_<ts>.csv`` same as before), and destination tab
    (``sheet_tab``) so callers other than the CLI (e.g. a future proxy module)
    can reuse it with their own schema/output config. ``summary_fn``, if given,
    is called with ``results`` at the end (mirrors the old unconditional
    ``_print_summary`` call, but only reached when there ARE results — same as
    before).
    """
    if not results:
        log.warning("No results to write")
        return

    RESULTS_PATH.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    local_csv = local_csv or f"backtests/results_{ts}.csv"
    csv_path = ROOT / local_csv

    if not dry_run:
        if csv_path.exists():
            archive = csv_path.with_name(
                csv_path.stem + "_" + ts + csv_path.suffix)
            csv_path.rename(archive)
            log.info("Archived previous results to '%s'", archive.name)
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=key_order, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        log.info("Wrote %d results to '%s'", len(results), csv_path)

        if sheet_tab:
            sheets_client.append_rows(
                sheet_tab, [{k: r.get(k, "") for k in key_order} for r in results])
            log.info("Appended results to Google Sheets tab '%s'", sheet_tab)
    else:
        log.info("[dry-run] Would write %d results to '%s'", len(results), csv_path)

    if summary_fn is not None:
        summary_fn(results)
