"""
Scan Google Drive compiled flow files and record enrichment status per date/prefix.

Writes (or refreshes) the EnrichLog tab in Google Sheets with one row per
(date, prefix) pair showing how many contracts/tickers have been enriched by
each of the three enrichers: OI+greeks (enrich_oi.py), IV percentile
(fetch_iv_percentile.py), and the counterpart-IV sidecar (fetch_counterpart_iv.py,
per-date rather than per-prefix, so its columns are duplicated across both
prefix rows for that date).

Rows already marked 'complete' on ALL THREE (status/iv_status/cp_status) are
not re-downloaded; only non-complete and new rows are checked. Use --full to
force a re-check of everything.

Columns manually added to the EnrichLog sheet (last_analysis, backtest_ready,
last_backtest) are carried forward by name from the existing sheet on every
run — they are NOT computed here, just threaded through so a full-table
rewrite never blanks them. Carry-forward reads these columns with
get_all_rows_preserving_formulas so a manually anchored array formula (e.g.
a MAP() spilling down the column) round-trips as formula text instead of
being flattened into its evaluated value on every rewrite.

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
from lib.counterpart_iv import needed_counterparts
from lib import sheets_client
from lib.logger import setup_logging
from compile_flow import FLOW_PREFIXES
from enrich_oi import _source_file, _distinct_contracts, _done_keys, _ensure_columns
from fetch_iv_percentile import (
    _distinct_tickers,
    _done_tickers as _done_iv_tickers,
    _ensure_columns as _ensure_iv_columns,
)
from fetch_counterpart_iv import (
    _compiled_flow_rows,
    _done_keys as _done_cp_keys,
    _load_sidecar,
)

log = logging.getLogger("update_enrich_logs")

TAB = "EnrichLog"

# Columns this script computes, in write order. Anything in MANUAL_COLUMNS is
# NOT computed here — it's read back from the existing sheet and threaded
# through unchanged (see with_manual_cols in main()) so a human-added column
# never gets clobbered by the full-table rewrite in write_analysis().
COLUMNS = [
    "date", "prefix", "status",
    "total_contracts", "enriched_contracts", "enrichment_pct",
    "last_enriched_on",
    "iv_status", "iv_total_tickers", "iv_enriched_tickers", "iv_enrichment_pct",
    "iv_last_enriched_on",
    "cp_status", "cp_wanted", "cp_fetched", "cp_enrichment_pct", "cp_last_fetched_on",
    "last_updated",
]

# Manually maintained in the live sheet — preserved by name, never computed here.
MANUAL_COLUMNS = ["last_analysis", "backtest_ready ", "last_backtest"]

ALL_COLUMNS = COLUMNS + MANUAL_COLUMNS
STATUS_FIELDS = ("status", "iv_status", "cp_status")

# Function names that spill a single formula down a column (Google Sheets:
# only the anchor cell holds the formula, every cell below is an unowned
# computed spill). Used to detect a MANUAL_COLUMNS formula like this one.
_SPILL_FUNCS = ("MAP(", "ARRAYFORMULA(", "BYROW(", "BYCOL(", "SCAN(", "REDUCE(")


def _is_spill_formula(value) -> bool:
    v = str(value).strip().upper()
    return v.startswith("=") and any(f in v for f in _SPILL_FUNCS)


def _oi_fields(rows: list[dict]) -> dict:
    """OI+greeks enrichment status (enrich_oi.py) for an already-downloaded compiled file."""
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
        "status": status,
        "total_contracts": total,
        "enriched_contracts": enriched,
        "enrichment_pct": pct,
        "last_enriched_on": last_enriched_on,
    }


def _iv_fields(rows: list[dict]) -> dict:
    """IV-percentile enrichment status (fetch_iv_percentile.py) for the same rows."""
    _ensure_iv_columns(rows)
    tickers = _distinct_tickers(rows)
    done = _done_iv_tickers(rows)

    last_enriched_on = max(
        (r["iv_pct_enriched_on"] for r in rows if r.get("iv_pct_enriched_on", "").strip()),
        default="",
    )

    total = len(tickers)
    enriched = len(done)
    pct = f"{enriched / total * 100:.0f}%" if total else ""
    if total == 0:
        status = "no-tickers"
    elif enriched >= total:
        status = "complete"
    elif enriched:
        status = "partial"
    else:
        status = "none"

    return {
        "iv_status": status,
        "iv_total_tickers": total,
        "iv_enriched_tickers": enriched,
        "iv_enrichment_pct": pct,
        "iv_last_enriched_on": last_enriched_on,
    }


def _check(client, prefix: str, date_str: str) -> dict:
    """Download one compiled file once and return its OI + IV enrichment status.

    (cp_* fields are per-date, not per-prefix — the caller merges those in separately.)
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = {"date": date_str, "prefix": prefix, "last_updated": now}
    empty_oi = {"status": "no-compiled", "total_contracts": 0, "enriched_contracts": 0,
                "enrichment_pct": "", "last_enriched_on": ""}
    empty_iv = {"iv_status": "no-compiled", "iv_total_tickers": 0, "iv_enriched_tickers": 0,
                "iv_enrichment_pct": "", "iv_last_enriched_on": ""}

    file_id, file_name = _source_file(client, prefix, date_str)
    if not file_id:
        return {**base, **empty_oi, **empty_iv}

    rows = parse_csv(client.download(file_id, name=file_name))
    if not rows:
        return {**base, **{**empty_oi, "status": "empty"}, **{**empty_iv, "iv_status": "empty"}}

    return {**base, **_oi_fields(rows), **_iv_fields(rows)}


def _check_cp(client, date_str: str) -> dict:
    """Counterpart-IV sidecar status (fetch_counterpart_iv.py) — one per date, all prefixes."""
    flow_rows = _compiled_flow_rows(client, date_str)
    if not flow_rows:
        return {"cp_status": "no-compiled", "cp_wanted": 0, "cp_fetched": 0,
                "cp_enrichment_pct": "", "cp_last_fetched_on": ""}

    wanted = needed_counterparts(flow_rows)
    sidecar = _load_sidecar(client, date_str)
    done = _done_cp_keys(sidecar)

    last_fetched_on = max(
        (r.get("fetched_on", "") for r in sidecar if str(r.get("fetched_on", "")).strip()),
        default="",
    )

    total = len(wanted)
    fetched = sum(1 for c in wanted if c["key"] in done)
    pct = f"{fetched / total * 100:.0f}%" if total else ""
    if total == 0:
        status = "no-counterparts"
    elif fetched >= total:
        status = "complete"
    elif fetched:
        status = "partial"
    else:
        status = "none"

    return {
        "cp_status": status,
        "cp_wanted": total,
        "cp_fetched": fetched,
        "cp_enrichment_pct": pct,
        "cp_last_fetched_on": last_fetched_on,
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

    # Always read the existing sheet — not just when not --full — so manually
    # added columns (MANUAL_COLUMNS) can be carried forward even on a --full run.
    existing: dict[tuple, dict] = {}
    # Formula-preserving read of the same tab, used ONLY for MANUAL_COLUMNS: a
    # manually anchored array formula (e.g. MAP() in backtest_ready) must be
    # carried forward as formula text, not its evaluated value, or the
    # full-table rewrite below flattens it into a static string and the
    # formula is gone for good.
    existing_raw: dict[tuple, dict] = {}
    try:
        for row in sheets_client.get_all_rows(TAB):
            key = (str(row.get("date", "")), str(row.get("prefix", "")))
            existing[key] = row
        for row in sheets_client.get_all_rows_preserving_formulas(TAB):
            key = (str(row.get("date", "")), str(row.get("prefix", "")))
            existing_raw[key] = row
    except Exception as e:
        log.warning("Could not read existing EnrichLog tab: %s", e)

    # A MANUAL_COLUMNS formula anchored on the sheet's first data row (e.g.
    # backtest_ready's MAP()) only owns that one cell — every row below it is
    # an unowned spill. Carrying forward each row's *evaluated* spill value
    # (as with_manual_cols does below) writes real content into those cells,
    # so the next time the formula recalculates Sheets refuses to spill
    # ("Array result was not expanded because it would overwrite data") and
    # the column goes dead until someone manually deletes the stray content.
    # Fix: for a detected spill column, keep the formula text ONLY on the
    # physical first output row and force every other row blank.
    anchor_row = next(iter(existing_raw.values()), {})
    spill_cols = {c for c in MANUAL_COLUMNS if _is_spill_formula(anchor_row.get(c, ""))}

    def with_manual_cols(row: dict, key: tuple) -> dict:
        ex = existing_raw.get(key) or existing.get(key)
        return {**row, **{c: (ex.get(c, "") if ex else "") for c in MANUAL_COLUMNS}}

    rows_out: list[dict] = []
    skipped = 0
    for date_str in all_dates:
        keys = [(date_str, prefix) for prefix in FLOW_PREFIXES]
        exs = {k: existing.get(k) for k in keys}
        all_complete = all(
            not args.full and ex and all(str(ex.get(f, "")) == "complete" for f in STATUS_FIELDS)
            for ex in exs.values()
        )

        if all_complete:
            for key in keys:
                rows_out.append(with_manual_cols(
                    {c: exs[key].get(c, "") for c in COLUMNS}, key))
                skipped += 1
            continue

        cp_result = _check_cp(client, date_str)
        for prefix in FLOW_PREFIXES:
            key = (date_str, prefix)
            log.info("%s  %s: checking...", date_str, prefix)
            row = {**_check(client, prefix, date_str), **cp_result}
            rows_out.append(with_manual_cols(row, key))

    # Normalize every row to ALL_COLUMNS order — write_analysis derives the sheet's
    # column order from rows_out[0].keys(), and dict insertion order otherwise
    # differs between the skip-branch and compute-branch rows built above.
    rows_out = [{c: r.get(c, "") for c in ALL_COLUMNS} for r in rows_out]
    rows_out.sort(key=lambda r: (r["date"], r["prefix"]))

    # Re-anchor spill formulas: only the physical first row keeps the formula
    # text, every other row is forced blank so the formula can spill freely.
    for c in spill_cols:
        for i, r in enumerate(rows_out):
            r[c] = anchor_row.get(c, "") if i == 0 else ""

    checked = len(rows_out) - skipped
    summary_line = (
        f"{len(rows_out)} row(s) total  "
        f"({checked} checked, {skipped} skipped as already-complete)"
    )

    if args.dry_run:
        w = [12, 14, 10, 8, 10, 8, 8]
        hdr = ["date", "prefix", "status", "iv_status", "cp_status",
               "enrichment_pct", "iv_enrichment_pct"]
        print("\nEnrichLog (dry-run)")
        print("  " + "  ".join(h.ljust(w[i]) for i, h in enumerate(hdr)))
        print("  " + "  ".join("-" * ww for ww in w))
        for r in rows_out:
            vals = [str(r.get(h, "")) for h in hdr]
            print("  " + "  ".join(v.ljust(w[i]) for i, v in enumerate(vals)))
        print(f"\n  {summary_line}")
        return

    if rows_out:
        sheets_client.write_analysis(TAB, rows_out, preserve_extra_cols=True)
        print(f"\nEnrichLog updated — {summary_line}")
        print(f"  Tab: {TAB}")
    else:
        print("No dates found in Drive.")


if __name__ == "__main__":
    main()
