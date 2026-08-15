"""
Step 5 — persist journal rows to the TradeJournal Sheets tab and the local CSV.

PRODUCTION TIER. Two destinations, deliberately:

  * `journal/trades.csv` — the local record. Written FIRST and independently, so
    a Sheets outage, a revoked credential or a missing env var can never cost you
    the day's trades. Gitignored.
  * TradeJournal tab in TRADE_JOURNAL_SPREADSHEET_ID — the copy you can look at
    from a phone and the one the dashboard could read. A separate workbook from
    the analysis book so it can be shared on its own terms.

IDEMPOTENCY is per ROW, not per batch. `lib/sheets_client.compute_batch_fingerprint`
answers "was the last batch identical", which is the wrong question here: a
re-run later in the day legitimately carries the morning's fills PLUS new ones,
and that batch hashes differently while most of its rows are already written.
So the real key is `source_ref` — the broker's own execution ids — and rows
whose source_ref is already present are dropped before the append. Running the
same date five times appends the first time and nothing after; running it again
after new fills appends exactly the new fills.

The fingerprint is still recorded in `_meta` as a cheap "when did this last
change" marker, not as the dedup mechanism.
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from lib import sheets_client

from .config import (DEDUP_KEY_COLS, JOURNAL_COLUMNS, TRADE_JOURNAL_SPREADSHEET_ENV,
                     TRADE_JOURNAL_TAB, TRADES_CSV, PositionEvent, PositionRisk)

log = logging.getLogger(__name__)


def to_row(event: PositionEvent,
           risk_by_key: dict[str, PositionRisk] | None = None,
           net_liq: float | None = None) -> dict:
    """Flatten one PositionEvent (+ its risk mark, if any) into a journal row.

    The row is built key-by-key from JOURNAL_COLUMNS so a column added to the
    contract without a value here shows up as blank rather than shifting every
    later column — the failure mode that makes a spreadsheet quietly wrong.
    """
    risk = (risk_by_key or {}).get(event.conid_key())

    pct_net_liq = None
    if risk is not None and risk.delta_notional is not None and net_liq:
        pct_net_liq = risk.delta_notional / net_liq

    values = {
        "date": event.date,
        "trade_datetime_utc": event.trade_datetime_utc,
        "ticker": event.ticker,
        "structure": event.structure,
        "action": event.action,
        "legs": event.legs_string(),
        "contracts": event.contracts,
        "net_price": event.net_price,
        "commission": event.commission,
        "net_cash": event.net_cash,
        "realized_pnl": event.realized_pnl,
        "dte_at_entry": event.dte_at_entry,
        "signal_date": event.signal_date,
        "entry_lag_days": event.entry_lag_days,
        "match_confidence": event.match_confidence,
        "ac_play": event.ac_play,
        "ac_structure": event.ac_structure,
        "tier": event.tier,
        "tier_reason": event.tier_reason,
        "tier_verified": event.tier_verified,
        "entry_slippage": event.entry_slippage,
        "position_delta": risk.position_delta if risk else None,
        "delta_notional": risk.delta_notional if risk else None,
        "pct_net_liq": pct_net_liq,
        "underlying_price": risk.underlying_price if risk else None,
        "short_leg_delta": risk.short_leg_delta if risk else None,
        "iv": risk.iv if risk else None,
        "delta_source": risk.delta_source if risk else None,
        "mech_cell": event.mech_cell,
        "market_regime": event.market_regime,
        "notes": event.notes,
        "source_ref": event.source_ref,
    }
    # Exactly the contract's columns, in the contract's order.
    return {col: _blank(values.get(col)) for col in JOURNAL_COLUMNS}


def _blank(v):
    """None renders as an empty cell. A real 0 / 0.0 / False must survive."""
    return "" if v is None else v


# --------------------------------------------------------------------------
# Local CSV
# --------------------------------------------------------------------------
def _csv_path(path: Path | None = None) -> Path:
    """Resolve the CSV destination AT CALL TIME.

    Deliberately not a default argument: `def f(path=TRADES_CSV)` binds the
    constant at import, which makes the destination impossible to redirect
    afterwards. That is not merely awkward to test — it means a test, or any
    caller wanting a different target, silently writes to the real trade journal
    instead. Resolving here keeps the module patchable and the real journal safe.
    """
    return Path(path if path is not None else TRADES_CSV)


def read_csv_source_refs(path: Path | None = None) -> set[str]:
    path = _csv_path(path)
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as fh:
        return {r.get("source_ref", "") for r in csv.DictReader(fh)
                if r.get("source_ref")}


def append_csv(rows: list[dict], path: Path | None = None) -> int:
    """Append rows, writing the header on first use. Returns rows written."""
    if not rows:
        return 0
    path = _csv_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=JOURNAL_COLUMNS)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("Appended %d row(s) to %s", len(rows), path)
    return len(rows)


# --------------------------------------------------------------------------
# Sheets
# --------------------------------------------------------------------------
def read_sheet_source_refs(spreadsheet_id: str) -> set[str]:
    rows = sheets_client.get_all_rows(TRADE_JOURNAL_TAB, spreadsheet_id=spreadsheet_id)
    return {str(r.get("source_ref", "")) for r in rows if r.get("source_ref")}


def write(events: list[PositionEvent],
          risk_by_key: dict[str, PositionRisk] | None = None,
          net_liq: float | None = None,
          *, dry_run: bool = False, skip_sheets: bool = False,
          csv_path: Path | None = None) -> dict:
    """Write the day's events to CSV and Sheets, skipping anything already there.

    Returns a summary dict. The CSV is written before Sheets and its failure is
    fatal; a Sheets failure is logged and reported but does NOT lose the row,
    because the local copy already holds it.
    """
    rows = [to_row(e, risk_by_key, net_liq) for e in events]
    summary = {"candidates": len(rows), "csv_written": 0, "sheets_written": 0,
               "skipped_duplicate": 0, "sheets_error": None}
    if not rows:
        log.info("No journal rows to write")
        return summary

    seen = read_csv_source_refs(csv_path)
    fresh = [r for r in rows if r["source_ref"] and r["source_ref"] not in seen]
    summary["skipped_duplicate"] = len(rows) - len(fresh)

    missing_ref = [r for r in rows if not r["source_ref"]]
    if missing_ref:
        # Without a source_ref a row cannot be deduped, so a re-run would
        # duplicate it silently. Refuse rather than corrupt the record.
        raise ValueError(
            f"{len(missing_ref)} journal row(s) have no source_ref — refusing to "
            "write rows that cannot be deduplicated on a later run")

    if dry_run:
        log.info("DRY RUN — would write %d new row(s) (%d already present)",
                 len(fresh), summary["skipped_duplicate"])
        summary["would_write"] = len(fresh)
        return summary

    summary["csv_written"] = append_csv(fresh, csv_path)

    if skip_sheets or not fresh:
        return summary

    spreadsheet_id = os.getenv(TRADE_JOURNAL_SPREADSHEET_ENV)
    if not spreadsheet_id:
        summary["sheets_error"] = f"{TRADE_JOURNAL_SPREADSHEET_ENV} not set"
        log.warning("%s not set — journal written locally only", TRADE_JOURNAL_SPREADSHEET_ENV)
        return summary

    try:
        already = read_sheet_source_refs(spreadsheet_id)
        to_send = [r for r in fresh if r["source_ref"] not in already]
        if to_send:
            # raw=True: the date column is part of the identity and must not be
            # locale-parsed into a sheet date.
            sheets_client.append_rows(TRADE_JOURNAL_TAB, to_send, raw=True,
                                      spreadsheet_id=spreadsheet_id)
            sheets_client.set_meta(
                TRADE_JOURNAL_TAB,
                fingerprint=sheets_client.compute_batch_fingerprint(to_send, DEDUP_KEY_COLS),
                last_row_time=datetime.now(timezone.utc).isoformat(),
                spreadsheet_id=spreadsheet_id)
        summary["sheets_written"] = len(to_send)
    except Exception as exc:  # noqa: BLE001 - report, never lose the local row
        summary["sheets_error"] = str(exc)
        log.exception("Sheets write failed — rows are safe in %s", TRADES_CSV)

    return summary
