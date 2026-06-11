"""
Build daily market-baseline rows and append them to the BaselineDaily sheet tab.

One row per trading date (see lib/baseline.py for the schema and rationale).
Idempotent: existing dates in the tab are never recomputed or rewritten, so
re-running is a no-op and --backfill self-heals any missed days — the same
pattern as gc_flow --all.

Usage:
  python3 scripts/build_baseline.py                       # latest Drive date
  python3 scripts/build_baseline.py --date 2026-06-10
  python3 scripts/build_baseline.py --start 2026-06-01 --end 2026-06-10
  python3 scripts/build_baseline.py --backfill            # every Drive date
  python3 scripts/build_baseline.py --backfill --dry-run  # report, no write
"""
import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.baseline import BASELINE_TAB, compute_daily_baseline, normalize_sheet_date
from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client
from lib.logger import setup_logging
from lib.sheets_client import append_rows, get_all_rows

log = logging.getLogger("build_baseline")

# The two premium-flow sections the baseline is computed from. The unusual-
# activity sections do not contribute (see lib/baseline.py).
_FLOW_PREFIXES = ("stocks-flow", "etfs-flow")


def _drive_dates(client) -> list[str]:
    """Every trading date with stocks-flow data in Drive, oldest → newest."""
    dates = set()
    for f in client.list_files("stocks-flow"):
        rest = f["name"][len("stocks-flow") + 1:]
        compact = rest.split("-", 1)[0]
        if len(compact) == 8 and compact.isdigit():
            dates.add(f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}")
    return sorted(dates)


def _weekday_range(start_iso: str, end_iso: str) -> list[str]:
    d, end = date.fromisoformat(start_iso), date.fromisoformat(end_iso)
    out = []
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _load_flow(client, prefix: str, date_str: str) -> list[dict]:
    try:
        name, content = client.download_for_date(prefix, date_str)
        if not content:
            return []
        log.info("Fetched '%s' for %s", name, date_str)
        return parse_csv(content)
    except Exception:
        log.exception("Could not fetch '%s' for %s", prefix, date_str)
        return []


def _existing_dates() -> set[str]:
    rows = get_all_rows(BASELINE_TAB)
    return {iso for r in rows if (iso := normalize_sheet_date(r.get("date")))}


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Single trading date (YYYY-MM-DD).")
    parser.add_argument("--start", help="Range start (YYYY-MM-DD), weekdays only.")
    parser.add_argument("--end", help="Range end (YYYY-MM-DD), weekdays only.")
    parser.add_argument("--backfill", action="store_true",
                        help="Target every date with flow data in Drive.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute and report; do not write to the sheet.")
    args = parser.parse_args()

    if args.date and (args.start or args.end or args.backfill):
        parser.error("--date is exclusive with --start/--end/--backfill")
    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be given together")

    client = get_drive_client()

    if args.backfill:
        targets = _drive_dates(client)
    elif args.date:
        targets = [args.date]
    elif args.start:
        targets = _weekday_range(args.start, args.end)
    else:
        all_dates = _drive_dates(client)
        targets = all_dates[-1:]  # latest available

    existing = _existing_dates()
    missing = [d for d in targets if d not in existing]
    log.info("Targets: %d date(s), %d already in %s, %d to compute",
             len(targets), len(targets) - len(missing), BASELINE_TAB, len(missing))

    new_rows, skipped = [], []
    for d in missing:
        stocks = _load_flow(client, "stocks-flow", d)
        etfs = _load_flow(client, "etfs-flow", d)
        if not stocks and not etfs:
            skipped.append(d)
            continue
        new_rows.append(compute_daily_baseline(d, stocks, etfs))

    if new_rows and not args.dry_run:
        append_rows(BASELINE_TAB, new_rows, raw=True)

    print(f"\nBaseline {'dry-run' if args.dry_run else 'run'} summary")
    print(f"  targeted:        {len(targets)}")
    print(f"  already present: {len(targets) - len(missing)}")
    print(f"  computed:        {len(new_rows)}")
    print(f"  no flow data:    {len(skipped)}{' — ' + ', '.join(skipped) if skipped else ''}")
    if new_rows:
        first, last = new_rows[0], new_rows[-1]
        print(f"  date span:       {first['date']} → {last['date']}")
        print(f"  written:         {'no (dry-run)' if args.dry_run else f'yes → {BASELINE_TAB}'}")


if __name__ == "__main__":
    main()
