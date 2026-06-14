"""
Compile a trading day's hourly flow snapshots into one deduped CSV per type.

The scraper (barchart_scrape.py, run ~hourly by GitHub Actions) drops a separate
`{prefix}-YYYYMMDD-HHMM.csv` into the date folder on every run. Each export is
capped at 500 rows and consecutive snapshots overlap heavily, so the same trade
appears many times across the day. This script gathers all snapshots for a date,
concatenates them, removes duplicate trades, and uploads one compiled file per
flow type:

    etfs-flow-YYYYMMDD-*.csv   →  etfs-flow-YYYYMMDD-compiled.csv
    stocks-flow-YYYYMMDD-*.csv →  stocks-flow-YYYYMMDD-compiled.csv

A duplicate is decided by TRADE IDENTITY — the columns that pin a single trade
execution (Symbol, Type, Strike, Expires, Trade, Size, Side, Premium, Time) —
not by an exact full-row match, so scrape-time columns that drift between
snapshots (Volume, Open Int, Price~, IV, Delta, quote sizes) don't keep an
otherwise-identical trade as two rows. The newest snapshot's copy of each trade
is kept, so the most-settled Volume/OI values win.

Compiling only produces the compiled artifact; it never removes the raw
snapshots. Reclaiming the raw files is a separate, independently-verified step —
see scripts/gc_flow.py.

Usage:
  python3 scripts/compile_flow.py                 # today's trading day (ET)
  python3 scripts/compile_flow.py --date 2026-06-09
  python3 scripts/compile_flow.py --date 2026-06-09 --dry-run     # report, no upload
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.logger import setup_logging
from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client, trading_day

log = logging.getLogger("compile_flow")

# Flow types to compile (Drive filename prefix).
FLOW_PREFIXES = ["etfs-flow", "stocks-flow"]

# Columns that identify a unique trade execution. Everything else (Price~, DTE,
# Volume, Open Int, IV, Delta, quote columns) can drift between snapshots and is
# deliberately excluded from the dedup key.
DEDUP_KEY = ["Symbol", "Type", "Strike", "Expires", "Trade", "Size", "Side", "Premium", "Time"]

COMPILED_SUFFIX = "compiled"


def compiled_name(prefix: str, date_str: str) -> str:
    """Output filename for a compiled day, e.g. 'etfs-flow-20260609-compiled.csv'."""
    return f"{prefix}-{date_str.replace('-', '')}-{COMPILED_SUFFIX}.csv"


def dedup_rows(rows: list[dict]) -> tuple[pd.DataFrame, int]:
    """Deduplicate flow rows on trade identity.

    Returns (deduped DataFrame, number of duplicate rows removed). The last copy
    of each trade is kept, so callers should pass rows oldest→newest for the
    newest snapshot's values to survive. Key columns absent from the data are
    dropped from the key; if none remain it falls back to a full-row match.
    """
    if not rows:
        return pd.DataFrame(), 0
    df = pd.DataFrame(rows)
    key = [c for c in DEDUP_KEY if c in df.columns]
    before = len(df)
    deduped = df.drop_duplicates(subset=key or None, keep="last").reset_index(drop=True)
    return deduped, before - len(deduped)


def compile_prefix(client, prefix: str, date_str: str, dry_run: bool = False) -> dict | None:
    """Gather, dedup, and (unless dry_run) upload one flow type's snapshots.

    Returns a stats dict, or None when no snapshots exist for the date. The raw
    snapshots are left in place — reclaiming them is gc_flow.py's job.
    """
    files = client.list_files_for_date(prefix, date_str)  # oldest→newest
    if not files:
        log.warning("%s: no snapshots for %s — nothing to compile", prefix, date_str)
        return None

    rows: list[dict] = []
    for f in files:
        rows.extend(parse_csv(client.download(f["id"], name=f["name"])))

    deduped, n_dups = dedup_rows(rows)
    name = compiled_name(prefix, date_str)

    if not dry_run:
        folder_id = client.get_or_create_date_folder(date_str)
        tmp = Path(f"/tmp/{name}")
        deduped.to_csv(tmp, index=False)
        client.upload(tmp, name, folder_id)
        tmp.unlink(missing_ok=True)

    stats = {
        "prefix": prefix,
        "snapshots": len(files),
        "rows_in": len(rows),
        "rows_out": len(deduped),
        "duplicates": n_dups,
        "name": name,
    }
    log.info(
        "%s: %d snapshot(s), %d rows → %d unique (%d duplicate row(s) removed)%s",
        prefix, stats["snapshots"], stats["rows_in"], stats["rows_out"],
        stats["duplicates"], "" if dry_run else f" → {name}",
    )
    return stats


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Compile a day's hourly flow snapshots into one deduped CSV per type.",
    )
    parser.add_argument("--date", help="Trading date to compile (YYYY-MM-DD). Default: today (ET).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report dedup counts without uploading the compiled files.")
    args = parser.parse_args()

    date_str = args.date or trading_day()
    log.info("Compiling flow for %s%s", date_str, " (dry-run)" if args.dry_run else "")

    client = get_drive_client()
    results = [compile_prefix(client, prefix, date_str, dry_run=args.dry_run)
               for prefix in FLOW_PREFIXES]

    compiled = [r for r in results if r]
    if not compiled:
        log.warning("No flow snapshots found for %s — nothing compiled", date_str)
        return

    total_dups = sum(r["duplicates"] for r in compiled)
    log.info(
        "Done — %d type(s) compiled, %d total duplicate row(s) removed",
        len(compiled), total_dups,
    )
    for r in compiled:
        print(
            f"{r['prefix']:<12} {r['snapshots']:>3} snapshot(s)  "
            f"{r['rows_in']:>5} → {r['rows_out']:>5} rows  "
            f"{r['duplicates']:>5} duplicate(s) removed"
            + ("" if args.dry_run else f"  → {r['name']}")
        )


if __name__ == "__main__":
    main()
