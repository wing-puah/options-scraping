"""
Scan Google Drive compiled flow files and record enrichment status per date/prefix.

Writes (or refreshes) the EnrichLog tab in Google Sheets with one row per
(date, prefix) pair showing how many contracts have been enriched.

Rows already marked 'complete' are not re-downloaded; only non-complete and
new rows are checked. Use --full to force a re-check of everything.

Usage:
  python3 scripts/update_enrich_logs.py            # scan all, skip complete
  python3 scripts/update_enrich_logs.py --full     # re-check every date
  python3 scripts/update_enrich_logs.py --dry-run  # print table, no write
"""
import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client
from lib import sheets_client
from lib.logger import setup_logging
from compile_flow import FLOW_PREFIXES, compiled_name
from enrich_oi import _compiled_id, _distinct_contracts, _done_keys, _ensure_columns

log = logging.getLogger("update_enrich_logs")

TAB = "EnrichLog"
COLUMNS = [
    "date", "prefix", "status",
    "total_contracts", "enriched_contracts", "enrichment_pct",
    "last_enriched_on", "last_updated",
]


def _check(client, prefix: str, date_str: str) -> dict:
    """Download one compiled file and return its enrichment status row."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = {"date": date_str, "prefix": prefix, "last_updated": now}

    file_id = _compiled_id(client, prefix, date_str)
    if not file_id:
        return {**base, "status": "no-compiled", "total_contracts": 0,
                "enriched_contracts": 0, "enrichment_pct": "", "last_enriched_on": ""}

    rows = parse_csv(client.download(file_id, name=compiled_name(prefix, date_str)))
    if not rows:
        return {**base, "status": "empty", "total_contracts": 0,
                "enriched_contracts": 0, "enrichment_pct": "", "last_enriched_on": ""}

    _ensure_columns(rows)
    contracts, _ = _distinct_contracts(rows)
    done = _done_keys(rows)

    last_enriched_on = max(
        (r["oi_enriched_on"] for r in rows if r.get("oi_enriched_on", "").strip()),
        default="",
    )

    total = len(contracts)
    enriched = len(done)
    pct = f"{enriched / total * 100:.0f}%" if total else ""
    if total == 0:
        status = "no-contracts"
    elif enriched >= total:
        status = "complete"
    elif enriched:
        status = "partial"
    else:
        status = "none"

    return {
        **base,
        "status": status,
        "total_contracts": total,
        "enriched_contracts": enriched,
        "enrichment_pct": pct,
        "last_enriched_on": last_enriched_on,
    }


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", action="store_true",
                        help="Re-check all dates even if already marked complete.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the table but do not write to Sheets.")
    args = parser.parse_args()

    client = get_drive_client()
    all_dates = sorted(client.list_date_folders())

    existing: dict[tuple, dict] = {}
    if not args.full:
        try:
            for row in sheets_client.get_all_rows(TAB):
                key = (str(row.get("date", "")), str(row.get("prefix", "")))
                existing[key] = row
        except Exception as e:
            log.warning("Could not read existing EnrichLog tab: %s", e)

    rows_out: list[dict] = []
    skipped = 0
    for date_str in all_dates:
        for prefix in FLOW_PREFIXES:
            key = (date_str, prefix)
            ex = existing.get(key)
            if not args.full and ex and str(ex.get("status", "")) == "complete":
                rows_out.append({c: ex.get(c, "") for c in COLUMNS})
                skipped += 1
                continue
            log.info("%s  %s: checking...", date_str, prefix)
            rows_out.append(_check(client, prefix, date_str))

    rows_out.sort(key=lambda r: (r["date"], r["prefix"]))

    checked = len(rows_out) - skipped
    summary_line = (
        f"{len(rows_out)} row(s) total  "
        f"({checked} checked, {skipped} skipped as already-complete)"
    )

    if args.dry_run:
        w = [12, 14, 14, 17, 20, 15, 15]
        hdr = ["date", "prefix", "status", "total_contracts",
               "enriched_contracts", "enrichment_pct", "last_enriched_on"]
        print("\nEnrichLog (dry-run)")
        print("  " + "  ".join(h.ljust(w[i]) for i, h in enumerate(hdr)))
        print("  " + "  ".join("-" * ww for ww in w))
        for r in rows_out:
            vals = [str(r.get(h, "")) for h in hdr]
            print("  " + "  ".join(v.ljust(w[i]) for i, v in enumerate(vals)))
        print(f"\n  {summary_line}")
        return

    if rows_out:
        sheets_client.write_analysis(TAB, rows_out)
        print(f"\nEnrichLog updated — {summary_line}")
        print(f"  Tab: {TAB}")
    else:
        print("No dates found in Drive.")


if __name__ == "__main__":
    main()
