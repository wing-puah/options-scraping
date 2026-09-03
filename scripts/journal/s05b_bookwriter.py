"""
Step 5b — persist the OPEN BOOK to the OpenBook Sheets tab and the local CSV.

PRODUCTION TIER. `s05_writer.py` records what you TRADED; this records what you
are HOLDING, once per marked session. The two are different questions and the
first cannot answer the second: a journal row describes a trade at the instant
it happened and is never revisited, so nothing in TradeJournal tells you that a
position opened five weeks ago is now past its §5 exit deadline, sitting on an
unpriced leg, or carrying the ticker that just breached its cap. Until now that
only existed in `journal/reports/<date>.md` and the generated HTML page — both
local, neither something you can open on a phone and sort.

WHAT MAKES IT SCANNABLE. Every row leads with `status` (ATTENTION / WATCH / OK)
and `flags`, derived from the numbers beside it by `flags_for`. The vocabulary
and its thresholds live in `config.BOOK_FLAG_SEVERITY` — greppable, and in the
same file as every other shape in this pipeline.

FLAGS ARE ATTENTION, NEVER VERDICTS. Nothing downstream reads one. The caps
still bind in `s03_risk.py`, the §5 deadline is still computed in
`lib/exit_rules.py`, and the ladder still ranks in `s06_recommend.py`. A flag
changes what gets NOTICED, not what is true — which is why its thresholds are
allowed to be round numbers with nothing fitted behind them.

DELIBERATELY NOT SHARED WITH s05_writer.py / s07_recwriter.py. Those two are
already independent of each other for a stated reason (see s07's docstring):
every helper is named and bodied for its own key, tab and column list, and
generalising them would mean editing the module whose failure loses the day's
TRADES in order to ship something that is not trades. This module mirrors their
structure and their discipline and stays independent for the same reason.

TWO DESTINATIONS, TWO JOBS. The TAB is a MIRROR: every run replaces it with
the book exactly as marked, so what is on it is what you hold, and a flat book
CLEARS it. The CSV is the ARCHIVE: append-only and generational, keeping every
mark ever taken. They differ because their readers differ, and the split is
what lets each be right.

WHY THE TAB IS NOT THE ARCHIVE. Its whole job is to be SORTED — sort on
`status`, see what is amiss. Appending defeats exactly that: a position closed
three weeks ago keeps its last ATTENTION row at the top of that sort forever,
indistinguishable from a live one, and the operator has to filter by
`as_of_date` and `generation` before the column means anything. A tab you must
filter before you can sort is not scannable, and scannable was the point.

WHY THE CSV IS. "Was this flagged before it went wrong?" is a real question and
only the record can answer it. Keeping it costs nothing: `journal/open_book.csv`
is already written first, already survives a Sheets outage, and is already the
copy the writer deduplicates against. `book_id` ends in a hash of the row's
CONTENT, marks included, so re-running the same session with the same greeks
appends nothing at all; a genuinely re-marked POSITION — new spot, new delta, a
cap flag that has since flipped — appends its own row at `generation = n+1` and
leaves the earlier mark, and every untouched position, alone. Read the current
book out of it as "largest as_of_date, then largest generation PER POSITION" —
`latest_snapshot()`, which is also what the tab already shows.

WHAT IS NOT ON THE TAB, ON PURPOSE. The original layout wrote the net-cap block,
the book counts, NetLiquidation, `book_reconstructed` and the pull's notes on
every row — fourteen columns identical down the whole snapshot, and the two
numbers the operator acts on (`delta_notional`, `exit_by`) buried behind them.
The operator asked for a tab that shows what they need to know about a
POSITION, nearest the left. Book-level facts now reach the tab only as the
flags they raise on the rows they concern; in full they are in the report and
the page.

THE MISSING/ZERO SEAM. An unpriced position is written with BLANK delta cells
and `priced` FALSE, never a zero, and carries an UNPRICED_* flag. Never total
the `delta_notional` column of this tab without filtering on `priced`.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path

from lib import sheets_client

from . import s03_risk as risk
from .config import (BOOK_DEDUP_KEY_COLS, BOOK_FLAG_SEVERITY,
                     BOOK_IDENTITY_EXCLUDED, CAP_NEAR_UTILISATION,
                     EXIT_DUE_SOON_DAYS, EXPIRING_SOON_DTE, OPEN_BOOK_COLUMNS,
                     OPEN_BOOK_CSV, OPEN_BOOK_TAB,
                     TRADE_JOURNAL_SPREADSHEET_ENV, BookContext, PositionRisk)
from .lib import exit_rules

log = logging.getLogger(__name__)

# The grouping a `generation` counts within: the same position, marked again on
# the same day. A mark on a LATER day is a new day's row, not a new generation.
_GEN_KEY = ("as_of_date", "conid_key")

# Worst first — the order `status` resolves in, and the order flags print in.
_SEVERITY_RANK = {"ATTENTION": 0, "WATCH": 1, "INFO": 2}


# --------------------------------------------------------------------------
# Triage
# --------------------------------------------------------------------------
def _days_between(later: date | None, earlier: date | None) -> int | None:
    if later is None or earlier is None:
        return None
    return (later - earlier).days


def flags_for(p: PositionRisk, book, *, as_of: date | None,
              ticker_total: float | None = None,
              net_total: float | None = None,
              split_expiry: bool = False) -> list[str]:
    """Every attention token this position earns, worst-severity first.

    `ticker_total` / `net_total` are passed in rather than re-derived per row:
    they are the same two numbers for every row of a snapshot, and the cap
    verdict must not depend on which row is being rendered.
    """
    flags: list[str] = []

    # --- can we even see it? ---------------------------------------------
    if not p.priced:
        flags.append("UNPRICED_NO_DELTA" if p.position_delta is None
                     else "UNPRICED_NO_SPOT")

    # --- time ------------------------------------------------------------
    if p.dte is not None:
        if p.dte < 0:
            flags.append("EXPIRED")
        elif p.dte <= EXPIRING_SOON_DTE:
            flags.append("EXPIRING_SOON")

    days_to_exit = _days_between(p.exit_by, as_of)
    if days_to_exit is not None:
        if days_to_exit < 0:
            flags.append("EXIT_OVERDUE")
        elif days_to_exit <= EXIT_DUE_SOON_DAYS:
            flags.append("EXIT_DUE_SOON")
    elif (p.exit_by is None and exit_rules.is_debit(p.structure) is True
            and exit_rules.time_exit_fraction() is not None):
        # A debit whose deadline could not be computed, while the rule itself is
        # enabled — the entry date is not provable from any export we hold. INFO,
        # not WATCH: it is a gap in the RECORD, not a fact about the position.
        flags.append("EXIT_DATE_UNKNOWN")

    # --- caps -------------------------------------------------------------
    caps = getattr(book, "caps", None)
    if caps is None:
        flags.append("CAPS_NOT_EVALUABLE")
    else:
        if ticker_total is not None and caps.per_position_dollars:
            util = abs(ticker_total) / caps.per_position_dollars
            if util > 1:
                flags.append("TICKER_CAP_BREACH")
            elif util >= CAP_NEAR_UTILISATION:
                flags.append("TICKER_CAP_NEAR")
        if net_total is not None and caps.net_dollars:
            util = abs(net_total) / caps.net_dollars
            if util > 1:
                flags.append("NET_CAP_BREACH")
            elif util >= CAP_NEAR_UTILISATION:
                flags.append("NET_CAP_NEAR")

    # --- how well do we understand the row? -------------------------------
    if p.entry_date_mixed:
        flags.append("MIXED_ENTRY_DATES")
    if str(p.structure or "").lower() == "unclassified":
        flags.append("UNCLASSIFIED_STRUCTURE")
    if split_expiry:
        flags.append("SPLIT_EXPIRY")

    return sorted(flags, key=lambda f: (_SEVERITY_RANK.get(
        BOOK_FLAG_SEVERITY.get(f, "WATCH"), 1), f))


def status_for(flags: list[str]) -> str:
    """ATTENTION / WATCH / OK — the worst severity present.

    INFO deliberately cannot move it: SPLIT_EXPIRY describes how a calendar is
    PRESENTED (see lib/book.py) and colouring it would train the reader to
    ignore the column.
    """
    severities = {BOOK_FLAG_SEVERITY.get(f, "WATCH") for f in flags}
    if "ATTENTION" in severities:
        return "ATTENTION"
    if "WATCH" in severities:
        return "WATCH"
    return "OK"


# --------------------------------------------------------------------------
# Row building
# --------------------------------------------------------------------------
def _blank(v):
    """None renders as an empty cell. A real 0 / 0.0 / False must survive.

    A third copy of a three-line rule, matching `writer._blank` and
    `recwriter._blank` byte for byte. The three modules are independent by
    design; sharing this would be the thin end of merging them.
    """
    return "" if v is None else v


def _net_delta_notional(book) -> float:
    """The book's net delta-notional, correct even when the caps never loaded.

    `__main__._build_book` constructs a `BookRisk` DIRECTLY — skipping
    `assess()` — when NetLiquidation is missing, which leaves the totals at
    their 0.0 dataclass default while real priced positions sit in
    `book.positions`. Writing that 0.0 into a permanent record would state a
    flat book on a day the book was not flat. So it is recomputed exactly when
    `assess` demonstrably did not run, and taken as given otherwise.
    """
    if getattr(book, "caps", None) is not None:
        return book.net_delta_notional
    return sum(p.delta_notional for p in book.positions if p.priced)


def _ticker_exposure(book) -> dict[str, float]:
    """Signed delta-notional per ticker — same caveat as `_net_delta_notional`."""
    if getattr(book, "caps", None) is not None and book.ticker_exposure:
        return dict(book.ticker_exposure)
    return risk.per_ticker_delta_notional(list(book.positions))


def _expiry_of(p: PositionRisk):
    """The position's expiry, or None.

    `lib/book.py` groups by (underlying, expiry) so every leg of a position
    shares one — but a hand-built PositionRisk need not, and a group with two
    would make the cell a lie. Report only an unambiguous one.
    """
    expiries = {lg.expiry for lg in (p.legs or [])}
    return expiries.pop() if len(expiries) == 1 else None


def _pct_net_liq(p: PositionRisk, net_liq: float | None) -> float | None:
    """Prefer a value already on the record; else derive it the way
    `s05_writer.to_row` and `s04a_report._pct_net_liq` both do."""
    if p.pct_net_liq is not None:
        return p.pct_net_liq
    if p.delta_notional is not None and net_liq:
        return p.delta_notional / net_liq
    return None


def to_rows(book, ctx: BookContext) -> list[dict]:
    """Flatten one marked open book into `OPEN_BOOK_COLUMNS`-shaped rows.

    Priced and unpriced positions are written TOGETHER, in one ordering, because
    the tab's job is "what am I holding" — a holding excluded from the exposure
    totals is still a holding, and hiding it below a fold is how it gets
    forgotten. `priced` and the UNPRICED_* flags are what separate them.
    """
    positions = sorted(list(book.positions) + list(book.unpriced),
                       key=lambda p: (p.ticker, str(_expiry_of(p) or ""), p.structure))
    if not positions:
        return []

    snapshot = (ctx.snapshot_at or datetime.now(timezone.utc)).isoformat()
    try:
        as_of = date.fromisoformat(ctx.as_of_date)
    except (TypeError, ValueError):
        # Without a parseable as-of there is no "overdue" and no "soon" — the
        # date-derived flags are simply not emitted, rather than measured
        # against today, which would date a replayed snapshot wrongly.
        as_of = None

    caps = getattr(book, "caps", None)
    by_ticker = _ticker_exposure(book)
    net = _net_delta_notional(book)

    # A ticker holding legs in more than one expiry is SPLIT across rows by
    # lib/book.py. Computed once over the whole book, so both halves of a
    # calendar carry the flag.
    expiries_per_ticker: dict[str, set] = {}
    for p in positions:
        e = _expiry_of(p)
        if e is not None:
            expiries_per_ticker.setdefault(p.ticker, set()).add(e)

    rows: list[dict] = []
    for p in positions:
        ticker_total = by_ticker.get(p.ticker)
        flags = flags_for(
            p, book, as_of=as_of, ticker_total=ticker_total, net_total=net,
            split_expiry=len(expiries_per_ticker.get(p.ticker, ())) > 1)
        expiry = _expiry_of(p)
        ticker_util = (abs(ticker_total) / caps.per_position_dollars
                       if caps is not None and ticker_total is not None
                       and caps.per_position_dollars else None)

        values = {
            "as_of_date": ctx.as_of_date,
            "status": status_for(flags),
            "flags": "; ".join(flags),
            "conid_key": p.conid_key,
            "ticker": p.ticker,
            "structure": p.structure,
            "contracts": p.contracts,
            "legs": " ".join(lg.leg_string() for lg in (p.legs or [])),
            "expiry": expiry.isoformat() if expiry else None,
            "dte": p.dte,
            "entry_date": p.entry_date.isoformat() if p.entry_date else None,
            "exit_by": p.exit_by.isoformat() if p.exit_by else None,
            "days_to_exit_by": _days_between(p.exit_by, as_of),
            "priced": p.priced,
            "position_delta": p.position_delta,
            "delta_notional": p.delta_notional,
            "pct_net_liq": _pct_net_liq(p, ctx.net_liq),
            "underlying_price": p.underlying_price,
            "short_leg_delta": p.short_leg_delta,
            "iv": p.iv,
            "delta_source": p.delta_source,
            "ticker_delta_notional": ticker_total,
            "ticker_cap_utilisation": ticker_util,
            "book_source": ctx.book_source,
            "snapshot_utc": snapshot,
        }
        # Deliberately NOT written: the net cap block, the book counts,
        # NetLiquidation, `book_reconstructed` and the pull's notes. They are
        # facts about the BOOK, identical on every row, and the operator asked
        # for a tab that shows only what they need to know about a POSITION.
        # They still shape the row through `flags` (NET_CAP_*,
        # CAPS_NOT_EVALUABLE, SPLIT_EXPIRY, MIXED_ENTRY_DATES) and live in full
        # in the report and the page.
        # Exactly the contract's columns, in the contract's order — a column
        # added to the contract with no value here shows up blank rather than
        # shifting every later column.
        row = {col: _blank(values.get(col)) for col in OPEN_BOOK_COLUMNS}
        row["book_id"] = book_id(row)
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
def content_hash(row: dict) -> str:
    """sha256 over the row's CONTENT — identity and wall clock excluded.

    Iterating OPEN_BOOK_COLUMNS (not the dict) makes this stable across
    processes and insensitive to key insertion order.
    """
    payload = "|".join(f"{c}={row.get(c, '')}" for c in OPEN_BOOK_COLUMNS
                       if c not in BOOK_IDENTITY_EXCLUDED)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def book_id(row: dict) -> str:
    """Readable at the front so the tab can be eyeballed, hashed at the back so
    an unchanged re-mark collides with itself and is dropped before the append."""
    return "|".join([
        str(row.get("as_of_date", "")),
        str(row.get("ticker", "")),
        str(row.get("expiry", "")),
        str(row.get("structure", "")),
        content_hash(row)[:12],
    ])


def _assign_generations(fresh: list[dict], existing: list[dict]) -> None:
    """Stamp `generation` on rows about to be written, counting what is already
    on disk for the same position on the same day. Runs AFTER the duplicate drop
    and is excluded from the hash, so it can never make a duplicate look new."""
    seen: dict[tuple, int] = {}
    for row in existing:
        key = tuple(str(row.get(k, "")) for k in _GEN_KEY)
        seen[key] = seen.get(key, 0) + 1
    for row in fresh:
        key = tuple(str(row.get(k, "")) for k in _GEN_KEY)
        seen[key] = seen.get(key, 0) + 1
        row["generation"] = seen[key]


# --------------------------------------------------------------------------
# Local CSV
# --------------------------------------------------------------------------
def _csv_path(path: Path | None = None) -> Path:
    """Resolve the CSV destination AT CALL TIME — see `writer._csv_path` for the
    full rationale. A default argument would bind the constant at import and
    make a test silently write to the real record."""
    return Path(path if path is not None else OPEN_BOOK_CSV)


def read_csv_rows(path: Path | None = None) -> list[dict]:
    """Every recorded snapshot row, or `[]`. Never raises — an absent file is
    the normal state before the first marked session."""
    p = _csv_path(path)
    if not p.exists():
        log.debug("No open-book record at %s yet", p)
        return []
    try:
        with open(p, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            header = list(reader.fieldnames or [])
    except Exception as exc:  # noqa: BLE001 - a readable record beats none
        log.warning("Could not read %s (%s) — treating as empty", p, exc)
        return []
    if header and header != OPEN_BOOK_COLUMNS and _is_ours(header):
        # A file still on an earlier layout is read AS the current one, ids
        # recomputed, so the duplicate check in `write` compares like with
        # like. The file itself is rewritten by `append_csv`, not here — a
        # read never mutates the record.
        return _reshape_rows(rows)
    return rows


def _is_ours(header: list[str]) -> bool:
    """An open-book file under ANY layout carries these two; anything else is
    not ours to reinterpret."""
    return "as_of_date" in header and "book_id" in header


def _reshape_rows(rows: list[dict]) -> list[dict]:
    """Rows from an earlier layout, re-keyed by NAME to `OPEN_BOOK_COLUMNS`:
    dropped columns discarded, new ones blank, `book_id` recomputed.

    The id ends in a hash over the schema's content columns, so a layout
    change moves it; left as written, the next run would fail to recognise its
    own rows and append the whole book again as a fresh generation.
    """
    out = []
    for r in rows:
        row = {c: r.get(c, "") for c in OPEN_BOOK_COLUMNS}
        row["book_id"] = book_id(row)
        out.append(row)
    return out


def _reconcile_csv_header(p: Path) -> None:
    """Bring an existing file up to the current schema, safely, by NAME.

    DictWriter writes its header only on FIRST use, so appending to a file
    written under another layout would put values under a header that does not
    name them. Two kinds of schema change are recognised, and both are handled
    by rewriting the file once, column by column, by name:

      * GROWTH — the old header is a strict prefix; new columns are blank.
      * RESHAPE — columns were reordered or dropped (2026-08-31: the tab was
        cut from 41 columns to 27 so the position's exposure and deadline sit
        at the left and nothing book-level repeats on every row). Dropped
        columns are discarded; the rest keep their values.

    In both cases every row's `book_id` is RECOMPUTED under the new schema. The
    id ends in a hash over the schema's content columns, so a layout change
    moves it; left as written, the next run would fail to recognise its own
    rows and append the whole book again as a fresh generation.

    A header that carries neither `as_of_date` nor `book_id` is not one of our
    files under any layout and is not ours to guess at — raise.
    """
    with open(p, newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh), None)
    if header is None or header == OPEN_BOOK_COLUMNS:
        return
    if not _is_ours(header):
        raise ValueError(
            f"{p} header matches neither OPEN_BOOK_COLUMNS nor an earlier layout "
            "of it — refusing to append into an unrecognised schema")
    with open(p, newline="", encoding="utf-8") as fh:
        old_rows = list(csv.DictReader(fh))
    tmp = p.with_name(p.name + ".reshape-tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OPEN_BOOK_COLUMNS)
        w.writeheader()
        for row in _reshape_rows(old_rows):
            w.writerow(row)
    tmp.replace(p)
    dropped = sorted(set(header) - set(OPEN_BOOK_COLUMNS))
    added = [c for c in OPEN_BOOK_COLUMNS if c not in header]
    log.info("Rewrote %s from %d to %d columns (dropped %s; added %s); book_ids "
             "recomputed", p, len(header), len(OPEN_BOOK_COLUMNS),
             dropped or "none", added or "none")


def append_csv(rows: list[dict], path: Path | None = None) -> int:
    """Append rows, writing the header on first use. Returns rows written."""
    if not rows:
        return 0
    p = _csv_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    exists = p.exists() and p.stat().st_size > 0
    if exists:
        _reconcile_csv_header(p)
    with open(p, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OPEN_BOOK_COLUMNS)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("Appended %d open-book row(s) to %s", len(rows), p)
    return len(rows)


# --------------------------------------------------------------------------
# Reading back
# --------------------------------------------------------------------------
def latest_snapshot(rows: list[dict], *, on_or_before: str | None = None) -> list[dict]:
    """The most recent snapshot's CURRENT generation of every position.

    `on_or_before` bounds it the way `recwriter.recent_rows` is bounded, and for
    the same reason: a page rebuilt for a past date must not show a book that
    did not exist yet.
    """
    rows = [r for r in rows if r.get("as_of_date")]
    if on_or_before:
        rows = [r for r in rows if str(r["as_of_date"]) <= str(on_or_before)]
    if not rows:
        return []
    newest = max(str(r["as_of_date"]) for r in rows)
    rows = [r for r in rows if str(r["as_of_date"]) == newest]

    current: dict[tuple, dict] = {}
    for r in rows:
        key = tuple(str(r.get(k, "")) for k in _GEN_KEY)
        prev = current.get(key)
        if prev is None or _as_int(r.get("generation")) >= _as_int(prev.get("generation")):
            current[key] = r
    return sorted(current.values(), key=lambda r: (r.get("ticker", ""),
                                                   r.get("expiry", "")))


def _as_int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------
# Sheets
# --------------------------------------------------------------------------
def write(book, ctx: BookContext, *, dry_run: bool = False,
          skip_sheets: bool = False, csv_path: Path | None = None) -> dict:
    """Record one marked open book: APPEND it to the CSV, MIRROR it onto the tab.

    Returns a summary dict. The CSV is written before Sheets and its failure is
    fatal; a Sheets failure is logged and reported but does NOT lose the mark,
    because the archive already holds it.
    """
    rows = to_rows(book, ctx)
    summary = {"positions": len(rows), "csv_written": 0, "sheets_written": 0,
               "skipped_duplicate": 0, "sheets_error": None,
               "attention": sum(1 for r in rows if r["status"] == "ATTENTION"),
               "watch": sum(1 for r in rows if r["status"] == "WATCH")}

    missing = [r for r in rows if not r.get("book_id")]
    if missing:
        # Without a book_id a row cannot be deduped, so a re-run would duplicate
        # it silently in the archive. Refuse rather than corrupt the record.
        raise ValueError(
            f"{len(missing)} open-book row(s) have no book_id — refusing to "
            "write rows that cannot be deduplicated on a later run")

    existing = read_csv_rows(csv_path)
    seen = {r.get("book_id", "") for r in existing if r.get("book_id")}
    fresh = [r for r in rows if r["book_id"] not in seen]
    summary["skipped_duplicate"] = len(rows) - len(fresh)
    _assign_generations(fresh, existing)

    if dry_run:
        log.info("DRY RUN — would archive %d new open-book row(s) (%d already "
                 "present) and mirror %d row(s) onto the tab",
                 len(fresh), summary["skipped_duplicate"], len(rows))
        summary["would_write"] = len(fresh)
        return summary

    if not rows:
        # A flat book adds nothing to the archive, but it is still a fact about
        # today and the tab must say it: the write below CLEARS the tab rather
        # than leaving yesterday's positions standing as if still held. A
        # spuriously flat book never reaches here — flexparse refuses a declared
        # book of nothing that the fills contradict.
        log.info("Open book is flat — nothing to archive; clearing the tab")

    summary["csv_written"] = append_csv(fresh, csv_path)

    if skip_sheets:
        return summary

    spreadsheet_id = os.getenv(TRADE_JOURNAL_SPREADSHEET_ENV)
    if not spreadsheet_id:
        summary["sheets_error"] = f"{TRADE_JOURNAL_SPREADSHEET_ENV} not set"
        log.warning("%s not set — open book written locally only",
                    TRADE_JOURNAL_SPREADSHEET_ENV)
        return summary

    try:
        # A MIRROR, not an append. `replace_rows` rewrites the header and every
        # data row from OPEN_BOOK_COLUMNS, which is why nothing here reads the
        # tab back first: there is no positional-append hazard to guard against
        # (the header is written with the rows it labels), no book_id to
        # dedupe against (a run that changed nothing writes the same content),
        # and a tab left on an older layout is simply rewritten rather than
        # refused — the archive, not the tab, is what a shape change must
        # migrate.
        summary["sheets_written"] = sheets_client.replace_rows(
            OPEN_BOOK_TAB, rows, OPEN_BOOK_COLUMNS, raw=True,
            spreadsheet_id=spreadsheet_id)
        if rows:
            sheets_client.set_meta(
                OPEN_BOOK_TAB,
                fingerprint=sheets_client.compute_batch_fingerprint(
                    rows, BOOK_DEDUP_KEY_COLS),
                last_row_time=datetime.now(timezone.utc).isoformat(),
                spreadsheet_id=spreadsheet_id)
    except Exception as exc:  # noqa: BLE001 - report, never lose the local row
        summary["sheets_error"] = str(exc)
        log.exception("Sheets write failed — rows are safe in %s", _csv_path(csv_path))

    return summary
