"""
Compile a trading day's hourly flow snapshots into one deduped CSV per type.

The scraper (scrape_flow.py, run ~hourly by GitHub Actions) drops a separate
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
  python3 scripts/compile_flow.py --start 2026-06-09 --end 2026-06-13   # weekdays in range
  python3 scripts/compile_flow.py --date 2026-06-09 --dry-run     # report, no upload
"""
import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.logger import setup_logging
from lib.csv_utils import normalize_flow_rows, parse_csv
from lib.drive_client import get_drive_client, trading_day

log = logging.getLogger("compile_flow")

# Flow types to compile (Drive filename prefix).
FLOW_PREFIXES = ["etfs-flow", "stocks-flow"]

# Columns that identify a unique trade execution. Everything else (Price~, DTE,
# Volume, Open Int, IV, Delta, quote columns) can drift between snapshots and is
# deliberately excluded from the dedup key.
DEDUP_KEY = ["Symbol", "Type", "Strike", "Expires", "Trade", "Size", "Side", "Premium", "Time"]

COMPILED_SUFFIX = "compiled"


def trading_days(start: date, end: date) -> list[date]:
    """Return all weekdays (Mon–Fri) between start and end, inclusive."""
    days, current = [], start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


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


def compile_prefix(client, prefix: str, date_str: str, dry_run: bool = False,
                   skip_existing: bool = False) -> dict | None:
    """Gather, dedup, and (unless dry_run) upload one flow type's snapshots.

    Returns a stats dict, or None when no snapshots exist for the date (or the
    compiled file already exists under skip_existing — recompiling would drop
    enrichment columns). The raw snapshots are left in place — reclaiming them
    is gc_flow.py's job.
    """
    if skip_existing:
        folder_id = client.find_date_folder(date_str)
        if folder_id and client.file_exists(compiled_name(prefix, date_str), folder_id):
            log.info("%s: %s already compiled — skipped (--skip-existing)", prefix, date_str)
            return None

    files = client.list_files_for_date(prefix, date_str)  # oldest→newest
    if not files:
        log.warning("%s: no snapshots for %s — nothing to compile", prefix, date_str)
        return None

    rows: list[dict] = []
    for f in files:
        rows.extend(parse_csv(client.download(f["id"], name=f["name"])))

    rows = normalize_flow_rows(rows, date.fromisoformat(date_str))
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


def compile_date(client, date_str: str, dry_run: bool = False,
                 skip_existing: bool = False) -> None:
    """Compile every flow type for one trading date and print the summary."""
    log.info("Compiling flow for %s%s", date_str, " (dry-run)" if dry_run else "")
    results = [compile_prefix(client, prefix, date_str, dry_run=dry_run,
                              skip_existing=skip_existing)
               for prefix in FLOW_PREFIXES]

    compiled = [r for r in results if r]
    if not compiled:
        if not skip_existing:
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
            + ("" if dry_run else f"  → {r['name']}")
        )


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Compile a day's hourly flow snapshots into one deduped CSV per type.",
    )
    parser.add_argument("--date", help="Trading date to compile (YYYY-MM-DD). Default: today (ET).")
    parser.add_argument("--start", help="Compile a date range: start date (YYYY-MM-DD). Weekends skipped.")
    parser.add_argument("--end", help="Range end date (YYYY-MM-DD), inclusive. Default: today.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report dedup counts without uploading the compiled files.")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip dates whose compiled file already exists on Drive "
                             "(recompiling drops enrichment columns).")
    args = parser.parse_args()

    if args.date and (args.start or args.end):
        parser.error("--date cannot be combined with --start/--end")
    if args.end and not args.start:
        parser.error("--end requires --start")

    if args.start:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end) if args.end else date.today()
        dates = [d.isoformat() for d in trading_days(start, end)]
        if not dates:
            log.warning("No weekdays between %s and %s — nothing to compile", args.start, args.end)
            return
    else:
        dates = [args.date or trading_day()]

    client = get_drive_client()
    for date_str in dates:
        compile_date(client, date_str, dry_run=args.dry_run,
                     skip_existing=args.skip_existing)


if __name__ == "__main__":
    main()
