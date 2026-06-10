"""
Garbage-collect raw flow snapshots once they are safely captured in a compiled file.

compile_flow.py dedups a day's hourly `{prefix}-YYYYMMDD-HHMM.csv` snapshots into
one `{prefix}-YYYYMMDD-compiled.csv`. This script is the separate cleanup pass: it
trashes those raw snapshots — but only after independently VERIFYING the compile,
not merely that a compiled file exists.

The check, per type per date:
  1. A compiled file exists for the date.
  2. It parses to a non-empty set of rows.
  3. Every raw snapshot trade (by trade-identity key) is present in the compiled
     file — i.e. the raws are a subset of the compiled output, so nothing is lost.

Only when all three hold are the raw snapshots moved to Drive trash (recoverable
~30 days). Because the verification re-reads both sides from Drive, this is
independent of whatever compile_flow.py did and is safe to re-run: a date whose
raws are already trashed simply has nothing left to collect.

Usage:
  python3 scripts/gc_flow.py                 # today (ET)
  python3 scripts/gc_flow.py --date 2026-06-09
  python3 scripts/gc_flow.py --all           # sweep every date that has a compiled file
  python3 scripts/gc_flow.py --all --dry-run # report what would be trashed, trash nothing
"""
import argparse
import logging
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.logger import setup_logging
from lib.csv_utils import parse_csv
from lib.drive_client import get_drive_client, trading_day
from compile_flow import DEDUP_KEY, FLOW_PREFIXES, compiled_name

log = logging.getLogger("gc_flow")


def _identity_keys(rows: list[dict]) -> set[tuple]:
    """Trade-identity key set for a batch of flow rows (same key compile_flow dedups on)."""
    return {tuple(r.get(c, "") for c in DEDUP_KEY) for r in rows}


def _compiled_id(client, prefix: str, date_str: str) -> str | None:
    """Drive file ID of the compiled file for prefix/date, or None if absent."""
    name = compiled_name(prefix, date_str)
    for f in client.list_files(prefix):
        if f["name"] == name:
            return f["id"]
    return None


def gc_prefix(client, prefix: str, date_str: str, dry_run: bool = False) -> dict:
    """Verify the compile for one type/date, then trash its raw snapshots.

    Returns a stats dict with a ``status`` describing the outcome:
      no-raw          — nothing left to collect (already clean)
      no-compiled     — compiled file missing; raws kept
      empty-compiled  — compiled file present but parsed to 0 rows; raws kept
      incomplete      — compiled file is missing some raw trades; raws kept
      trashed         — verified, raws moved to trash (0 if dry-run)
    """
    raws = client.list_files_for_date(prefix, date_str)
    if not raws:
        log.info("%s %s: no raw snapshots — already clean", prefix, date_str)
        return {"prefix": prefix, "date": date_str, "status": "no-raw", "raw": 0, "trashed": 0}

    compiled_id = _compiled_id(client, prefix, date_str)
    if not compiled_id:
        log.warning("%s %s: no compiled file — keeping %d raw snapshot(s)", prefix, date_str, len(raws))
        return {"prefix": prefix, "date": date_str, "status": "no-compiled", "raw": len(raws), "trashed": 0}

    compiled_rows = parse_csv(client.download(compiled_id))
    if not compiled_rows:
        log.warning("%s %s: compiled file is empty — keeping %d raw snapshot(s)", prefix, date_str, len(raws))
        return {"prefix": prefix, "date": date_str, "status": "empty-compiled", "raw": len(raws), "trashed": 0}

    raw_rows: list[dict] = []
    for f in raws:
        raw_rows.extend(parse_csv(client.download(f["id"])))

    missing = _identity_keys(raw_rows) - _identity_keys(compiled_rows)
    if missing:
        log.warning(
            "%s %s: compiled file is missing %d raw trade(s) — keeping %d raw snapshot(s)",
            prefix, date_str, len(missing), len(raws),
        )
        return {"prefix": prefix, "date": date_str, "status": "incomplete", "raw": len(raws), "trashed": 0}

    if dry_run:
        log.info("%s %s: verified — would trash %d raw snapshot(s) (dry-run)", prefix, date_str, len(raws))
        return {"prefix": prefix, "date": date_str, "status": "trashed", "raw": len(raws), "trashed": 0}

    for f in raws:
        client.trash(f["id"])
        log.info("%s %s: trashed raw snapshot '%s'", prefix, date_str, f["name"])
    log.info("%s %s: verified — trashed %d raw snapshot(s)", prefix, date_str, len(raws))
    return {"prefix": prefix, "date": date_str, "status": "trashed", "raw": len(raws), "trashed": len(raws)}


def _dates_with_compiled(client, prefix: str) -> set[str]:
    """Every trading date (YYYY-MM-DD) that has a compiled file for prefix in Drive."""
    pat = re.compile(rf"^{re.escape(prefix)}-(\d{{8}})-compiled\.csv$")
    out: set[str] = set()
    for f in client.list_files(prefix):
        m = pat.match(f["name"])
        if m:
            c = m.group(1)
            out.add(f"{c[:4]}-{c[4:6]}-{c[6:8]}")
    return out


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Trash raw flow snapshots that are verified-present in their compiled file.",
    )
    parser.add_argument("--date", help="Trading date to collect (YYYY-MM-DD). Default: today (ET).")
    parser.add_argument("--all", action="store_true",
                        help="Sweep every date that has a compiled file, not just one day.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be trashed without trashing anything.")
    args = parser.parse_args()

    client = get_drive_client()

    if args.all:
        dates = sorted({d for prefix in FLOW_PREFIXES for d in _dates_with_compiled(client, prefix)})
        log.info("Sweep: %d date(s) with a compiled file", len(dates))
    else:
        dates = [args.date or trading_day()]
    log.info("GC flow%s — %d date(s)", " (dry-run)" if args.dry_run else "", len(dates))

    results = [gc_prefix(client, prefix, d, dry_run=args.dry_run)
               for d in dates for prefix in FLOW_PREFIXES]

    total_trashed = sum(r["trashed"] for r in results)
    kept = [r for r in results if r["status"] in ("no-compiled", "empty-compiled", "incomplete")]
    log.info(
        "Done — %d raw snapshot(s) trashed; %d type/date(s) kept for failing verification",
        total_trashed, len(kept),
    )
    for r in results:
        if r["raw"]:  # only report type/dates that had raw snapshots to consider
            print(f"{r['date']}  {r['prefix']:<12} {r['status']:<14} raw={r['raw']:>3}  trashed={r['trashed']:>3}")


if __name__ == "__main__":
    main()
