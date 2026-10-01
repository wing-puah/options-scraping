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

The UNUSUAL sections (`unusual-stocks`, `unusual-etfs`) have no compiled file —
nothing compiles them, so the verified-subset check above cannot apply. They get
their own, separate pass: a day's unusual snapshots are the same cumulative
strike-day table re-exported, so the RICHEST snapshot (most parsed rows) is kept
and the rest are trashed. Note this is a thinning pass, not a merge: unlike the
flow pass it does NOT prove the kept file is a superset of the ones it trashes.
It also changes what readers see — `download_for_date` picks the newest file by
name, so once the extras are gone the richest snapshot IS the newest, which is
the point (a short or truncated re-scrape stops shadowing a full one). Ties go to
the newest, so an already-correct day is read exactly as before.

Usage:
  python3 scripts/gc_flow.py                 # today (ET)
  python3 scripts/gc_flow.py --date 2026-06-09
  python3 scripts/gc_flow.py --all           # sweep every date that has a compiled file
  python3 scripts/gc_flow.py --last 3        # bounded sweep: the 3 most recent compiled dates
  python3 scripts/gc_flow.py --all --dry-run # report what would be trashed, trash nothing
  python3 scripts/gc_flow.py --all --skip-unusual   # flow pass only
"""
import argparse
import logging
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.logger import setup_logging
from lib.csv_utils import normalize_flow_rows, parse_csv
from lib.drive_client import SNAPSHOT, classify_flow_name, get_drive_client, trading_day
from compile_flow import DEDUP_KEY, FLOW_PREFIXES, compiled_name

log = logging.getLogger("gc_flow")

# The unusual-activity sections. Kept SEPARATE from compile_flow.FLOW_PREFIXES
# rather than appended to it: nothing compiles these, so they are collected by
# the keep-the-richest pass below, never by the verified-subset one.
UNUSUAL_PREFIXES = ["unusual-stocks", "unusual-etfs"]


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

    compiled_rows = parse_csv(client.download(compiled_id, name=compiled_name(prefix, date_str)))
    if not compiled_rows:
        log.warning("%s %s: compiled file is empty — keeping %d raw snapshot(s)", prefix, date_str, len(raws))
        return {"prefix": prefix, "date": date_str, "status": "empty-compiled", "raw": len(raws), "trashed": 0}

    raw_rows: list[dict] = []
    for f in raws:
        raw_rows.extend(parse_csv(client.download(f["id"], name=f["name"])))
    raw_rows = normalize_flow_rows(raw_rows, date.fromisoformat(date_str))

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


def gc_unusual_prefix(client, prefix: str, date_str: str, dry_run: bool = False) -> dict:
    """Keep the richest unusual snapshot for one type/date, trash the extras.

    An unusual-activity export is one row per strike-day with an elevated Vol/OI
    ratio — a cumulative table, not a trade log — so a day's snapshots are mostly
    re-exports of each other and the one with the most rows is the one worth
    keeping. There is no compiled file to verify against, so this pass cannot
    prove the kept snapshot covers the trashed ones; it is deliberately a thinning
    pass and nothing else.

    Returns a stats dict with a ``status`` describing the outcome:
      no-raw      — no snapshots for the date (nothing to collect)
      single      — one snapshot only, so nothing is extra
      unreadable  — every snapshot parsed to 0 rows; all kept
      deduped     — the richest kept, the rest trashed (0 trashed if dry-run)
    """
    snaps = client.list_files_for_date(prefix, date_str)
    if not snaps:
        log.info("%s %s: no snapshots — nothing to collect", prefix, date_str)
        return {"prefix": prefix, "date": date_str, "status": "no-raw", "raw": 0, "trashed": 0}
    if len(snaps) == 1:
        log.info("%s %s: one snapshot — nothing extra", prefix, date_str)
        return {"prefix": prefix, "date": date_str, "status": "single", "raw": 1, "trashed": 0}

    counts = {f["name"]: len(parse_csv(client.download(f["id"], name=f["name"]))) for f in snaps}
    # Richest first; ties to the newest name, which is the file download_for_date
    # already selects — so a day whose snapshots all agree keeps reading the same.
    ranked = sorted(snaps, key=lambda f: (counts[f["name"]], f["name"]), reverse=True)
    keep, extras = ranked[0], ranked[1:]

    if not counts[keep["name"]]:
        log.warning(
            "%s %s: all %d snapshot(s) parsed to 0 rows — keeping every one",
            prefix, date_str, len(snaps),
        )
        return {"prefix": prefix, "date": date_str, "status": "unreadable",
                "raw": len(snaps), "trashed": 0}

    log.info(
        "%s %s: keeping '%s' (%d rows) over %s",
        prefix, date_str, keep["name"], counts[keep["name"]],
        ", ".join(f"'{f['name']}' ({counts[f['name']]} rows)" for f in extras),
    )
    if dry_run:
        log.info("%s %s: would trash %d extra snapshot(s) (dry-run)", prefix, date_str, len(extras))
        return {"prefix": prefix, "date": date_str, "status": "deduped",
                "raw": len(snaps), "trashed": 0}

    for f in extras:
        client.trash(f["id"])
        log.info("%s %s: trashed extra snapshot '%s'", prefix, date_str, f["name"])
    return {"prefix": prefix, "date": date_str, "status": "deduped",
            "raw": len(snaps), "trashed": len(extras)}


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


def _dates_with_snapshots(client, prefix: str) -> set[str]:
    """Every trading date that has at least two raw snapshots for prefix in Drive.

    Dates with one snapshot are skipped: there is nothing extra to trash, so
    listing them would only cost the sweep a Drive round-trip per date.
    """
    seen: dict[str, int] = {}
    for f in client.list_files(prefix):
        parsed = classify_flow_name(f["name"], prefix)
        if parsed and parsed[1] == SNAPSHOT:
            seen[parsed[0]] = seen.get(parsed[0], 0) + 1
    return {d for d, n in seen.items() if n > 1}


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Trash raw flow snapshots verified-present in their compiled file, and "
                    "thin each day's unusual-activity snapshots down to the richest one.",
    )
    parser.add_argument("--date", help="Trading date to collect (YYYY-MM-DD). Default: today (ET).")
    parser.add_argument("--all", action="store_true",
                        help="Sweep every date that has a compiled file, not just one day.")
    parser.add_argument("--last", type=int, metavar="N",
                        help="Bounded sweep: only the N most recent dates that have a compiled "
                             "file. Older dates were collected on earlier runs, so re-checking "
                             "them costs Drive round-trips and trashes nothing.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be trashed without trashing anything.")
    parser.add_argument("--skip-unusual", action="store_true",
                        help="Run only the flow pass. The unusual pass has no compiled file to "
                             "verify against, so it keeps the richest snapshot rather than "
                             "proving coverage — skip it to collect flow alone.")
    args = parser.parse_args()

    if args.last is not None and args.last < 1:
        parser.error("--last must be at least 1")

    client = get_drive_client()

    # The two passes sweep DIFFERENT date sets: a flow date qualifies by having a
    # compiled file to verify against, an unusual date by having extras to thin.
    if args.all or args.last is not None:
        dates = sorted({d for prefix in FLOW_PREFIXES for d in _dates_with_compiled(client, prefix)})
        log.info("Sweep: %d date(s) with a compiled file", len(dates))
        unusual_dates = sorted(
            {d for prefix in UNUSUAL_PREFIXES for d in _dates_with_snapshots(client, prefix)}
        ) if not args.skip_unusual else []
        log.info("Sweep: %d date(s) with extra unusual snapshots", len(unusual_dates))
        if args.last is not None:
            dates = dates[-args.last:]
            unusual_dates = unusual_dates[-args.last:]
            log.info("Bounded to the %d most recent: %s", len(dates), ", ".join(dates))
    else:
        dates = [args.date or trading_day()]
        unusual_dates = [] if args.skip_unusual else list(dates)
    log.info("GC flow%s — %d date(s)", " (dry-run)" if args.dry_run else "", len(dates))

    results = [gc_prefix(client, prefix, d, dry_run=args.dry_run)
               for d in dates for prefix in FLOW_PREFIXES]
    results += [gc_unusual_prefix(client, prefix, d, dry_run=args.dry_run)
                for d in unusual_dates for prefix in UNUSUAL_PREFIXES]

    total_trashed = sum(r["trashed"] for r in results)
    kept = [r for r in results
            if r["status"] in ("no-compiled", "empty-compiled", "incomplete", "unreadable")]
    log.info(
        "Done — %d raw snapshot(s) trashed; %d type/date(s) kept for failing verification",
        total_trashed, len(kept),
    )
    for r in results:
        if r["raw"]:  # only report type/dates that had raw snapshots to consider
            print(f"{r['date']}  {r['prefix']:<12} {r['status']:<14} raw={r['raw']:>3}  trashed={r['trashed']:>3}")


if __name__ == "__main__":
    main()
