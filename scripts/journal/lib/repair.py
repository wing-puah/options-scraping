"""
Repair already-journalled TradeJournal rows: collapse duplicate fills, and
re-derive every CLOSE row written before the 2026-09-07 orientation fix.

WHY IT EXISTS. Two bugs wrote rows that stay wrong after their code was fixed,
because `journal/trades.csv` and the TradeJournal tab are append-only:

  * CLOSE rows written before 2026-09-07 name the mirror image of the position
    they closed (robustness-review P1). Their `structure` is inverted, and so is
    everything read off it: the analysis match, `ac_play`, the tier.
  * Until 2026-09-22 the dedup key included the pull filename, so a fill seen
    by two pulls was written twice (`s05_writer.fill_identity`).

`relabel.py` only PRINTS the label half of that, from the CSV alone. This module
does the whole repair, and it does it by RE-RUNNING RECONCILE on the original
broker pull — so the label, the match and the tier all come from the one live
code path, not from a second copy of any rule.

WHAT IT CHANGES, AND WHAT IT NEVER DOES.
  * A duplicate fill keeps its FIRST row (file order = earliest pull); the rest
    are deleted.
  * A pre-fix CLOSE row (action CLOSE, and no `CLOSE_ORIENTED_NOTE` in `notes`)
    gets `REDERIVED_COLUMNS` from the re-run. The money and identity columns
    (`FIXED_COLUMNS`) must come back EQUAL, or the row is refused — a re-run
    that moves the money is not the same fill any more. The risk columns are
    the mark taken on the day and are never touched.
  * A pre-fix row whose pull is not on disk is UNREPAIRABLE, and `--apply`
    refuses the whole repair rather than half-doing it.

IT IS IDEMPOTENT. A repaired CLOSE row carries `CLOSE_ORIENTED_NOTE` and no fill
appears twice, so a second run plans nothing and writes nothing.

THE THREE COPIES MOVE TOGETHER, OR NOT AT ALL. `--apply` reads the tab and the
Drive archive first and refuses unless every fill on each is already in the CSV
being repaired — so replacing them from that CSV can lose nothing. An edited
archive is not an append, so `drive_sync` would read the repaired local file as
a FORK of Drive's. `--apply` therefore REPLACES Drive's copy deliberately, after
saving it beside itself as `trades-pre-repair-<stamp>.csv`, leaving local and
Drive identical for the next run. `--merge-drive` first appends Drive rows whose
fills the CSV lacks, which is how two machines' disjoint halves become one file.

    python3 -m scripts.journal repair                    # dry run -> --out DIR
    python3 -m scripts.journal repair --merge-drive      # plan over local + Drive
    python3 -m scripts.journal repair --merge-drive --apply
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..config import (JOURNAL_COLUMNS, JOURNAL_DIR, TRADE_JOURNAL_SPREADSHEET_ENV,
                      TRADE_JOURNAL_TAB, TRADES_CSV)

log = logging.getLogger("journal.repair")

RAW_DIR = JOURNAL_DIR / "raw"

# What reconcile decides about a fill group. Taken from the re-run.
REDERIVED_COLUMNS = ("structure", "signal_date", "entry_lag_days",
                     "match_confidence", "ac_play", "ac_structure", "tier",
                     "tier_reason", "tier_verified", "entry_slippage",
                     "mech_cell", "market_regime", "notes")

# What the fills themselves say. The re-run must reproduce these exactly.
FIXED_COLUMNS = ("date", "trade_datetime_utc", "ticker", "action", "legs",
                 "contracts", "net_price", "commission", "net_cash",
                 "realized_pnl", "dte_at_entry")

# Numeric columns, typed back to numbers before the tab write so a repaired tab
# holds numbers where the writer's own appends did.
_NUMERIC = {"contracts", "net_price", "commission", "net_cash", "realized_pnl",
            "dte_at_entry", "entry_lag_days", "entry_slippage", "position_delta",
            "delta_notional", "pct_net_liq", "underlying_price",
            "short_leg_delta", "iv"}


class RepairRefused(RuntimeError):
    """A precondition failed. Nothing has been written."""


@dataclass(frozen=True)
class Change:
    row: int            # 1-based data-row number in the input
    date: str
    ticker: str
    source_ref: str
    column: str
    old: str
    new: str


@dataclass
class Plan:
    rows: list[dict] = field(default_factory=list)      # repaired, in order
    deleted: list[tuple[int, dict, int]] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    unrepairable: list[tuple[int, str, str]] = field(default_factory=list)
    input_rows: int = 0
    merged_from_drive: int = 0

    @property
    def empty(self) -> bool:
        return not (self.deleted or self.changes or self.merged_from_drive)

    def rows_changed(self) -> int:
        return len({c.row for c in self.changes})


def _pull_of(source_ref: str) -> str:
    return str(source_ref or "").rsplit(":", 1)[0]


def needs_rederive(row: dict) -> bool:
    """A CLOSE row the fixed pipeline did not write."""
    from ..s02_reconcile import CLOSE_ORIENTED_NOTE
    return ((row.get("action") or "").strip().upper() == "CLOSE"
            and CLOSE_ORIENTED_NOTE not in (row.get("notes") or ""))


def _cell(v) -> str:
    """How `csv.DictWriter` renders a `to_row` value."""
    return "" if v is None else str(v)


def _same(old: str, new: str) -> bool:
    if old == new:
        return True
    try:
        a, b = float(old), float(new)
    except (TypeError, ValueError):
        return False
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def plan(rows: list[dict],
         events_for_pull: Callable[[str], dict | None]) -> Plan:
    """Collapse duplicate fills and re-derive pre-fix CLOSE rows. PURE.

    `events_for_pull(pull_filename)` returns `{fill_identity: PositionEvent}`
    for that pull, or None when the pull is not available.
    """
    from ..s05_writer import fill_identity, to_row

    out = Plan(input_rows=len(rows))
    first_at: dict[frozenset, int] = {}
    for i, row in enumerate(rows, start=1):
        ident = fill_identity(row.get("source_ref"))
        if ident and ident in first_at:
            out.deleted.append((i, row, first_at[ident]))
            continue
        if ident:
            first_at[ident] = i
        row = dict(row)
        if needs_rederive(row):
            pull = _pull_of(row.get("source_ref"))
            events = events_for_pull(pull)
            if events is None:
                out.unrepairable.append((i, row.get("source_ref", ""),
                                         f"pull {pull} not available"))
            elif ident not in events:
                out.unrepairable.append((i, row.get("source_ref", ""),
                                         f"no fill group with these ids in {pull}"))
            else:
                new = to_row(events[ident])
                moved = [c for c in FIXED_COLUMNS
                         if not _same(row.get(c, ""), _cell(new[c]))]
                if moved:
                    out.unrepairable.append(
                        (i, row.get("source_ref", ""),
                         f"re-run moves fixed column(s) {moved}"))
                else:
                    for col in REDERIVED_COLUMNS:
                        v = _cell(new[col])
                        if row.get(col, "") != v:
                            out.changes.append(Change(
                                i, row.get("date", ""), row.get("ticker", ""),
                                row.get("source_ref", ""), col, row.get(col, ""), v))
                            row[col] = v
        out.rows.append(row)
    return out


def raw_events_loader(raw_dir: Path = RAW_DIR, ac_df=None):
    """`events_for_pull` over `journal/raw/`, reconciling each pull once.

    The analysis book is loaded once, lazily, and only if a row needs it.
    """
    from .. import s02_reconcile
    from ..s05_writer import fill_identity
    from . import analysis, rawpull

    cache: dict[str, dict | None] = {}
    book = {"df": ac_df}

    def events_for_pull(pull: str):
        if pull in cache:
            return cache[pull]
        path = Path(raw_dir) / pull
        if not pull or not path.exists():
            cache[pull] = None
            return None
        if book["df"] is None:
            book["df"], source = analysis.load()
            log.info("analysis book for the re-run: %s", source)
        events = s02_reconcile.reconcile(rawpull.load(path), book["df"])
        cache[pull] = {fill_identity(e.source_ref): e for e in events}
        return cache[pull]

    return events_for_pull


def merge_rows(local: list[dict], other: list[dict]) -> tuple[list[dict], int]:
    """`local` plus every `other` row whose fills `local` lacks, in order.

    Refuses a row sharing SOME fills with a local row: two groupings of the same
    fills are a question for a person.
    """
    from ..s05_writer import fill_identity

    known = {fill_identity(r.get("source_ref")) for r in local}
    ids = {i for k in known for i in k}
    merged, added = list(local), 0
    for r in other:
        ident = fill_identity(r.get("source_ref"))
        if not ident or ident in known:
            continue
        if ident & ids:
            raise RepairRefused(f"{r.get('source_ref')} shares fills with a local "
                                "row under a different grouping")
        merged.append(r)
        known.add(ident)
        ids |= ident
        added += 1
    return merged, added


def missing_from(rows: list[dict], other: list[dict]) -> list[str]:
    """source_refs on `other` whose fills are not among `rows`."""
    from ..s05_writer import fill_identity

    have = {fill_identity(r.get("source_ref")) for r in rows}
    return [str(r.get("source_ref")) for r in other
            if r.get("source_ref") and fill_identity(r.get("source_ref")) not in have]


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_rows(rows: list[dict], path: Path) -> None:
    """Write `rows` under JOURNAL_COLUMNS, atomically."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=JOURNAL_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in JOURNAL_COLUMNS})
    os.replace(tmp, path)


def write_diff(p: Plan, path: Path) -> None:
    """One line per changed cell, deleted row and refused row."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "row", "date", "ticker", "source_ref", "column",
                    "old", "new"])
        for c in p.changes:
            w.writerow(["changed", c.row, c.date, c.ticker, c.source_ref,
                        c.column, c.old, c.new])
        for i, row, kept in p.deleted:
            w.writerow(["deleted", i, row.get("date", ""), row.get("ticker", ""),
                        row.get("source_ref", ""), "", "",
                        f"duplicate of row {kept}"])
        for i, ref, why in p.unrepairable:
            w.writerow(["refused", i, "", "", ref, "", "", why])


def typed_row(row: dict) -> dict:
    """A CSV row with numbers and booleans typed back, for the tab write."""
    out = {}
    for c in JOURNAL_COLUMNS:
        v = row.get(c, "")
        if v in ("True", "False"):
            out[c] = v == "True"
        elif c in _NUMERIC and v != "":
            try:
                f = float(v)
                out[c] = int(f) if f.is_integer() and "." not in str(v) else f
            except ValueError:
                out[c] = v
        else:
            out[c] = v
    return out


# --------------------------------------------------------------------------
# The three destinations
# --------------------------------------------------------------------------
def _sheet_rows(spreadsheet_id: str) -> list[dict]:
    from lib import sheets_client
    return sheets_client.get_all_rows(TRADE_JOURNAL_TAB, spreadsheet_id=spreadsheet_id)


def _drive_rows(cli) -> tuple[str | None, list[dict]]:
    import io

    from . import drive_sync
    folder = drive_sync.history_folder(cli, create=False)
    text = drive_sync._download(cli, TRADES_CSV.name, folder) if folder else None
    if text is None:
        return None, []
    return text, list(csv.DictReader(io.StringIO(text)))


def replace_drive(cli, csv_path: Path, stamp: str) -> str:
    """Replace Drive's `_history/trades.csv` with `csv_path`, deliberately.

    Drive's current copy is saved beside it first as
    `trades-pre-repair-<stamp>.csv`, so nothing it held is lost.
    """
    from . import drive_sync
    folder = drive_sync.history_folder(cli, create=True)
    remote = drive_sync._download(cli, TRADES_CSV.name, folder)
    if remote is not None:
        backup = f"{TRADES_CSV.stem}-pre-repair-{stamp}{TRADES_CSV.suffix}"
        drive_sync._upload(cli, drive_sync._stage(backup, remote), backup, folder)
    drive_sync._upload(cli, Path(csv_path), TRADES_CSV.name, folder)
    return "replaced"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Repair TradeJournal rows: collapse duplicate fills, re-derive "
                    "pre-2026-09-07 CLOSE rows from their pulls. Dry run by default.")
    ap.add_argument("--csv", default=None, help=f"trades CSV (default: {TRADES_CSV})")
    ap.add_argument("--out", default=None,
                    help="directory for the diff, the repaired CSV and the backup "
                         "(default: journal/repair-<UTC stamp>/)")
    ap.add_argument("--merge-drive", action="store_true",
                    help="first append Drive's rows whose fills the CSV lacks")
    ap.add_argument("--apply", action="store_true",
                    help="write the CSV, the TradeJournal tab and the Drive archive")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = Path(args.csv) if args.csv else TRADES_CSV
    out_dir = Path(args.out) if args.out else JOURNAL_DIR / f"repair-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    local = read_rows(csv_path)
    rows, merged = local, 0
    cli = drive_text = None
    drive_rows: list[dict] = []
    from . import drive_sync
    if args.merge_drive or args.apply:
        if drive_sync.enabled():
            cli = drive_sync.client()
            drive_text, drive_rows = _drive_rows(cli)
    if args.merge_drive:
        rows, merged = merge_rows(local, drive_rows)

    p = plan(rows, raw_events_loader())
    p.merged_from_drive = merged
    write_diff(p, out_dir / "repair-diff.csv")
    write_rows(p.rows, out_dir / "trades-repaired.csv")

    print(f"{p.input_rows} row(s) in ({len(local)} local + {merged} merged from Drive); "
          f"{len(p.deleted)} duplicate(s) to delete; {p.rows_changed()} row(s) "
          f"re-derived ({len(p.changes)} cell(s)); {len(p.unrepairable)} refused; "
          f"{len(p.rows)} row(s) out")
    for c in p.changes:
        if c.column != "notes":
            print(f"  row {c.row:>3}  {c.date} {c.ticker:<5} {c.column:<17} "
                  f"{c.old[:40]!r} -> {c.new[:40]!r}")
    for i, ref, why in p.unrepairable:
        print(f"  REFUSED row {i}: {ref} — {why}")
    print(f"diff: {out_dir / 'repair-diff.csv'}")

    if not args.apply:
        print("DRY RUN — nothing written outside the output directory.")
        return 0
    if p.empty:
        print("Nothing to repair.")
        return 0
    if p.unrepairable:
        raise RepairRefused(f"{len(p.unrepairable)} row(s) cannot be re-derived")

    sid = os.getenv(TRADE_JOURNAL_SPREADSHEET_ENV, "")
    if not sid:
        raise RepairRefused(f"{TRADE_JOURNAL_SPREADSHEET_ENV} not set")
    if cli is None:
        raise RepairRefused("JOURNAL_DRIVE_FOLDER_ID not set — Drive would be left "
                            "holding the unrepaired archive")
    tab = _sheet_rows(sid)
    for label, other in (("TradeJournal tab", tab), ("Drive archive", drive_rows)):
        lost = missing_from(rows, other)
        if lost:
            raise RepairRefused(f"{label} holds {len(lost)} fill(s) the CSV lacks "
                                f"(e.g. {lost[0]}) — replacing it would lose them")

    shutil.copy2(csv_path, out_dir / f"{csv_path.stem}-pre-repair-{stamp}.csv")
    if drive_text is not None:
        (out_dir / f"drive-{TRADES_CSV.stem}-pre-repair-{stamp}.csv").write_text(
            drive_text, encoding="utf-8")
    write_rows(p.rows, csv_path)
    print(f"wrote {csv_path} ({len(p.rows)} rows)")

    from lib import sheets_client
    n = sheets_client.replace_rows(TRADE_JOURNAL_TAB, [typed_row(r) for r in p.rows],
                                   JOURNAL_COLUMNS, raw=True, spreadsheet_id=sid)
    print(f"replaced the {TRADE_JOURNAL_TAB} tab ({n} rows)")
    replace_drive(cli, csv_path, stamp)
    print(f"replaced Drive {drive_sync.HISTORY_FOLDER}/{TRADES_CSV.name} "
          f"(previous copy kept as {TRADES_CSV.stem}-pre-repair-{stamp}.csv)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
