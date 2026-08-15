"""
Persist the deploy card to the Recommendations Sheets tab and the local CSV.

PRODUCTION TIER. The card that `recommend.py` builds used to be printed and
thrown away; this module is what makes it a RECORD — the thing you can look at a
month later and ask "did I do what the card said, and was the card right".

Two destinations, deliberately, exactly as `writer.py` does it:

  * `journal/recommendations.csv` — written FIRST and independently, so a Sheets
    outage or a revoked credential can never cost you the card. Gitignored.
  * Recommendations tab in TRADE_JOURNAL_SPREADSHEET_ID — the same workbook as
    TradeJournal, because the two halves describe one loop (what was
    recommended, what was actually traded) and splitting the workbooks would
    mean sharing one without the other.

DELIBERATELY NOT SHARED WITH writer.py. Every helper there is `source_ref`- and
TradeJournal-shaped by name and by body — the key it dedupes on, the tab it
reads, the `fieldnames=JOURNAL_COLUMNS` it writes. Generalising them over
(key, tab, columns) would mean editing the one module whose failure loses the
day's TRADES in order to ship a feature that is not trades. So this module
mirrors its structure and its discipline instead, and the two stay independent.

APPEND-ONLY AND GENERATIONAL. `rec_id` ends in a hash of the row's CONTENT, so
re-running an unchanged card appends nothing at all — not even on a later day.
But a card whose judge verdict, or whose cap headroom, has changed IS a
different recommendation: it gets a new row at `generation = n+1`, and the
earlier one is left exactly as it was. Nothing is ever overwritten. If the 07:00
card said DEPLOY and the 15:00 re-run says RESERVE, both are true statements
about their own moment, and destroying the first would destroy the only record
of what you actually acted on.

THE BLANK-VS-FALSE SEAM. `rank()` computes `duplicate_exposure` from the open
book; handed an empty one it stamps False on every candidate, meaning "not a
duplicate" when the truth is "not checked". The dataclass field cannot carry
that distinction and widening it would ripple into
scripts/backtest_study/live_select.py, so it is resolved HERE: with
`ctx.book_evaluable` False, both book-derived verdicts serialise as a blank
cell, never as FALSE. Same missing/zero discipline the greeks get.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from lib import sheets_client

from .config import (JUDGE_LOOKAHEAD_NOTE, JUDGMENT_MODEL,
                     PAGE_RECENT_REC_SESSIONS, REC_DEDUP_KEY_COLS,
                     REC_IDENTITY_EXCLUDED, RECOMMENDATION_COLUMNS,
                     RECOMMENDATIONS_CSV, RECOMMENDATIONS_TAB,
                     TRADE_JOURNAL_SPREADSHEET_ENV, RecContext)

log = logging.getLogger(__name__)

# The grouping a `generation` counts within: the same play, recommended again.
_GEN_KEY = ("session_date", "role", "ticker", "structure")


# --------------------------------------------------------------------------
# Row building
# --------------------------------------------------------------------------
def _blank(v):
    """None renders as an empty cell. A real 0 / 0.0 / False must survive.

    Byte-identical to `writer._blank`, and deliberately a second copy: the two
    modules are independent by design (see the module docstring), and this rule
    is three lines. Sharing it would be the thin end of merging them.
    """
    return "" if v is None else v


def _book_derived(value, evaluable: bool):
    """A verdict that is only meaningful if the open book was readable.

    Returns "" (unknown) rather than the value when it was not. See the
    blank-vs-false note in the module docstring — this is the single place that
    distinction is applied.
    """
    return _blank(value) if evaluable else ""


def _candidate_row(c, i: int, ctx: RecContext, judged: bool) -> dict:
    return {
        "role": c.role,
        # The DETERMINISTIC list position. `rank()` produced this ordering
        # before judge() was ever called, and nothing downstream re-sorts on a
        # model verdict -- that is the "may annotate, may never promote"
        # invariant, written into the record rather than merely trusted.
        "rank": i,
        "deploy": c.deploy,
        "ticker": c.ticker,
        "structure": c.structure,
        "market_regime": _regime_label(c.market_regime),
        "tier": c.tier,
        "tier_partial": c.tier_partial,
        "tier_reason": c.tier_reason,
        "score_total": c.score_total,
        "horizon": c.horizon,
        "play": _play_headline(c.play),
        "trigger": c.trigger,
        "invalidation": c.invalidation,
        "alternative_interpretation": c.alternative_interpretation,
        "delta": c.delta,
        "duplicate_exposure": _book_derived(c.duplicate_exposure, ctx.book_evaluable),
        "headroom_ok": _book_derived(c.headroom_ok, ctx.book_evaluable),
        "headroom_note": c.headroom_note,
        "reasons": "; ".join(c.reasons or []),
        "trigger_verdict": c.trigger_verdict,
        "trigger_note": c.trigger_note,
        "alt_verdict": c.alt_verdict,
        "alt_note": c.alt_note,
        "demoted": c.demoted,
        "demote_reasons": "; ".join(c.demote_reasons or []),
        "hedge_pick": c.hedge_pick,
        "judge_lookahead_risk": JUDGE_LOOKAHEAD_NOTE if judged else "",
    }


def _rejected_row(r, ctx: RecContext) -> dict:
    return {
        "role": "veto" if r.tier == "VETO" else "tier_c",
        # Blank, not 0: the rejected sets carry no ordering to record.
        "rank": None,
        "deploy": False,
        "ticker": r.ticker,
        "structure": r.structure,
        "market_regime": _regime_label(r.market_regime),
        "tier": r.tier,
        "tier_reason": r.reason,
        "score_total": r.score_total,
        "play": _play_headline(r.play),
        "judge_lookahead_risk": "",
    }


def _regime_label(regime) -> str:
    from .recommend import _regime_label as label
    return label(regime)


def _play_headline(play) -> str:
    from .recommend import _play_headline as headline
    return headline(play)


def to_rows(candidates, rejected, ctx: RecContext) -> list[dict]:
    """Flatten one deploy card into `RECOMMENDATION_COLUMNS`-shaped rows.

    Deploy and hedge roles are ranked independently (both are 1-based within
    their own role), matching how `render()` numbers them on the card.
    """
    judged = ctx.judge_status == "ran"
    generated = (ctx.generated_at or datetime.now(timezone.utc)).isoformat()

    common = {
        "session_date": ctx.session_date,
        "as_of_date": ctx.as_of_date,
        "generated_at_utc": generated,
        "staleness_days": ctx.staleness_days,
        "judge_ran": judged,
        "judge_status": ctx.judge_status,
        "judge_model": JUDGMENT_MODEL if judged else "",
        "analysis_source": ctx.analysis_source,
        "book_source": ctx.book_source,
        "book_as_of": ctx.book_as_of,
        "book_evaluable": ctx.book_evaluable,
        "net_liq": ctx.net_liq,
        "stale_override": ctx.stale_override,
        "notes": ctx.notes,
    }

    partial: list[dict] = []
    for role in ("deploy", "hedge"):
        for i, c in enumerate([c for c in candidates if c.role == role], 1):
            partial.append(_candidate_row(c, i, ctx, judged))
    partial.extend(_rejected_row(r, ctx) for r in rejected)

    rows = []
    for values in partial:
        merged = {**common, **values}
        # Exactly the contract's columns, in the contract's order -- a column
        # added to the contract with no value here shows up blank rather than
        # shifting every later column.
        row = {col: _blank(merged.get(col)) for col in RECOMMENDATION_COLUMNS}
        row["rec_id"] = rec_id(row)
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
def content_hash(row: dict) -> str:
    """sha256 over the row's CONTENT — identity and wall clock excluded.

    Iterating RECOMMENDATION_COLUMNS (not the dict) makes this stable across
    processes and insensitive to key insertion order.
    """
    payload = "|".join(f"{c}={row.get(c, '')}" for c in RECOMMENDATION_COLUMNS
                       if c not in REC_IDENTITY_EXCLUDED)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def rec_id(row: dict) -> str:
    """Readable at the front so the tab can be eyeballed, hashed at the back so
    an unchanged re-run collides with itself and is dropped before the append."""
    return "|".join([
        str(row.get("session_date", "")),
        str(row.get("as_of_date", "")),
        str(row.get("role", "")),
        str(row.get("ticker", "")),
        str(row.get("structure", "")),
        content_hash(row)[:12],
    ])


def _assign_generations(fresh: list[dict], existing: list[dict]) -> None:
    """Stamp `generation` on rows about to be written, counting what is already
    on disk for the same play. Runs AFTER the duplicate drop and is excluded
    from the hash, so it can never make a duplicate look new."""
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
    return Path(path if path is not None else RECOMMENDATIONS_CSV)


def read_csv_rows(path: Path | None = None) -> list[dict]:
    """Every recorded recommendation, or `[]`.

    Never raises. The dashboard reads through this, and an absent file is the
    NORMAL state (the page is built by `cmd_run`, the card by `cmd_recommend`),
    so absence logs at DEBUG rather than as a fault. A corrupt file degrades the
    same way: a panel that cannot be drawn must never stop the journal page from
    being written.
    """
    p = _csv_path(path)
    if not p.exists():
        log.debug("No recommendations record at %s yet", p)
        return []
    try:
        with open(p, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except Exception as exc:  # noqa: BLE001 - a readable page beats a correct one here
        log.warning("Could not read %s (%s) — treating as empty", p, exc)
        return []


def read_csv_rec_ids(path: Path | None = None) -> set[str]:
    return {r.get("rec_id", "") for r in read_csv_rows(path) if r.get("rec_id")}


def append_csv(rows: list[dict], path: Path | None = None) -> int:
    """Append rows, writing the header on first use. Returns rows written."""
    if not rows:
        return 0
    p = _csv_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    exists = p.exists() and p.stat().st_size > 0
    with open(p, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RECOMMENDATION_COLUMNS)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("Appended %d recommendation row(s) to %s", len(rows), p)
    return len(rows)


# --------------------------------------------------------------------------
# Reading back — the dashboard's view
# --------------------------------------------------------------------------
def recent_rows(rows: list[dict], *, on_or_before: str | None = None,
                sessions: int = PAGE_RECENT_REC_SESSIONS) -> list[dict]:
    """The newest `sessions` analysis sessions' current recommendations.

    THE `on_or_before` FILTER IS NOT OPTIONAL IN SPIRIT. The dashboard rebuilds
    historical pages (`journal-<date>.html`) from today's files; without the
    bound, re-rendering last month's page would show it recommendations that did
    not exist yet — the same lookahead the card itself refuses, leaking in
    through the page.

    Within a session only the CURRENT generation of each play survives, so a
    session re-run does not show the same play three times.
    """
    rows = [r for r in rows if r.get("session_date")]
    if on_or_before:
        rows = [r for r in rows if str(r["session_date"]) <= str(on_or_before)]
    if not rows:
        return []

    keep = sorted({r["session_date"] for r in rows})[-sessions:]
    rows = [r for r in rows if r["session_date"] in keep]

    current: dict[tuple, dict] = {}
    for r in rows:
        key = tuple(str(r.get(k, "")) for k in _GEN_KEY)
        prev = current.get(key)
        if prev is None or _as_int(r.get("generation")) >= _as_int(prev.get("generation")):
            current[key] = r

    return sorted(current.values(),
                  key=lambda r: (r["session_date"], r.get("role", ""),
                                 _as_int(r.get("rank"))),
                  reverse=False)


def _as_int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------
# Sheets
# --------------------------------------------------------------------------
def read_sheet_rec_ids(spreadsheet_id: str) -> set[str]:
    rows = sheets_client.get_all_rows(RECOMMENDATIONS_TAB,
                                      spreadsheet_id=spreadsheet_id)
    return {str(r.get("rec_id", "")) for r in rows if r.get("rec_id")}


def write(candidates, rejected, ctx: RecContext, *,
          dry_run: bool = False, skip_sheets: bool = False,
          csv_path: Path | None = None) -> dict:
    """Write one deploy card to CSV and Sheets, skipping anything already there.

    Returns a summary dict. The CSV is written before Sheets and its failure is
    fatal; a Sheets failure is logged and reported but does NOT lose the row,
    because the local copy already holds it.
    """
    rows = to_rows(candidates, rejected, ctx)
    summary = {"candidates": len(rows), "csv_written": 0, "sheets_written": 0,
               "skipped_duplicate": 0, "sheets_error": None}
    if not rows:
        log.info("No recommendation rows to write")
        return summary

    missing = [r for r in rows if not r.get("rec_id")]
    if missing:
        # Without a rec_id a row cannot be deduped, so a re-run would duplicate
        # it silently. Refuse rather than corrupt the record.
        raise ValueError(
            f"{len(missing)} recommendation row(s) have no rec_id — refusing to "
            "write rows that cannot be deduplicated on a later run")

    existing = read_csv_rows(csv_path)
    seen = {r.get("rec_id", "") for r in existing if r.get("rec_id")}
    fresh = [r for r in rows if r["rec_id"] not in seen]
    summary["skipped_duplicate"] = len(rows) - len(fresh)
    _assign_generations(fresh, existing)

    if dry_run:
        log.info("DRY RUN — would write %d new recommendation row(s) (%d already present)",
                 len(fresh), summary["skipped_duplicate"])
        summary["would_write"] = len(fresh)
        return summary

    summary["csv_written"] = append_csv(fresh, csv_path)

    if skip_sheets or not fresh:
        return summary

    spreadsheet_id = os.getenv(TRADE_JOURNAL_SPREADSHEET_ENV)
    if not spreadsheet_id:
        summary["sheets_error"] = f"{TRADE_JOURNAL_SPREADSHEET_ENV} not set"
        log.warning("%s not set — recommendations written locally only",
                    TRADE_JOURNAL_SPREADSHEET_ENV)
        return summary

    try:
        # Size the tab to the full schema BEFORE anything reads it. get_all_rows
        # would otherwise create it at the 30-column default, and append_rows'
        # own min_cols only applies to a tab IT creates -- leaving this schema's
        # trailing columns silently truncated on every write.
        sheets_client.ensure_tab(RECOMMENDATIONS_TAB,
                                 min_cols=len(RECOMMENDATION_COLUMNS),
                                 spreadsheet_id=spreadsheet_id)
        already = read_sheet_rec_ids(spreadsheet_id)
        to_send = [r for r in fresh if r["rec_id"] not in already]
        if to_send:
            # raw=True: the date columns are part of the identity and must not
            # be locale-parsed into sheet dates.
            sheets_client.append_rows(RECOMMENDATIONS_TAB, to_send, raw=True,
                                      spreadsheet_id=spreadsheet_id)
            sheets_client.set_meta(
                RECOMMENDATIONS_TAB,
                fingerprint=sheets_client.compute_batch_fingerprint(
                    to_send, REC_DEDUP_KEY_COLS),
                last_row_time=datetime.now(timezone.utc).isoformat(),
                spreadsheet_id=spreadsheet_id)
        summary["sheets_written"] = len(to_send)
    except Exception as exc:  # noqa: BLE001 - report, never lose the local row
        summary["sheets_error"] = str(exc)
        log.exception("Sheets write failed — rows are safe in %s", _csv_path(csv_path))

    return summary
