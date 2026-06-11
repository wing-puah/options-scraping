import hashlib
import json
import logging
import os
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv(Path(__file__).parent.parent / ".env")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

log = logging.getLogger(__name__)


def _get_client() -> gspread.Client:
    json_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT")
    json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    if json_content:
        log.debug("Authorising Sheets via service account JSON content")
        info = json.loads(json_content)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    elif json_path:
        log.debug("Authorising Sheets via service account file")
        creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
    else:
        log.error("No Sheets credentials found in environment")
        raise RuntimeError("Set GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT or GOOGLE_SERVICE_ACCOUNT_JSON")

    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    if not spreadsheet_id:
        log.error("GOOGLE_SPREADSHEET_ID not set")
        raise RuntimeError("Set GOOGLE_SPREADSHEET_ID")
    log.debug("Opening configured spreadsheet")
    return _get_client().open_by_key(spreadsheet_id)


def _ensure_tab(spreadsheet: gspread.Spreadsheet, tab_name: str) -> gspread.Worksheet:
    try:
        ws = spreadsheet.worksheet(tab_name)
        log.debug("Found existing tab '%s'", tab_name)
        return ws
    except gspread.WorksheetNotFound:
        log.info("Tab '%s' not found — creating it", tab_name)
        return spreadsheet.add_worksheet(title=tab_name, rows=5000, cols=30)


def get_all_rows(tab: str) -> list[dict]:
    log.info("Reading all rows from tab '%s'", tab)
    ss = _get_spreadsheet()
    ws = _ensure_tab(ss, tab)
    rows = ws.get_all_records()
    log.info("Read %d row(s) from tab '%s'", len(rows), tab)
    return rows


def get_recent_rows(tab: str, n: int = 100) -> list[dict]:
    all_rows = get_all_rows(tab)
    return all_rows[-n:] if len(all_rows) > n else all_rows


def append_rows(tab: str, rows: list[dict], raw: bool = False) -> None:
    """Append dict rows (header written on first use). raw=True stores values
    as-is (RAW input option) so string dates like '2026-06-10' are not
    locale-parsed into sheet dates — required when the date is a dedup key."""
    if not rows:
        return
    log.info("Appending %d row(s) to tab '%s'", len(rows), tab)
    ss = _get_spreadsheet()
    ws = _ensure_tab(ss, tab)
    # NB: get_all_values() returns [[]] (truthy!) for a fresh tab — test the
    # first row's cells, not the outer list, or the header is silently skipped.
    if not ws.row_values(1):
        ws.append_row(list(rows[0].keys()))
    option = "RAW" if raw else "USER_ENTERED"
    ws.append_rows([list(r.values()) for r in rows], value_input_option=option)
    log.info("Appended %d row(s) to tab '%s'", len(rows), tab)


def write_analysis(tab_name: str, rows: list[dict]) -> None:
    if not rows:
        return
    log.info("Writing %d row(s) to tab '%s' (clearing first)", len(rows), tab_name)
    ss = _get_spreadsheet()
    ws = _ensure_tab(ss, tab_name)
    ws.clear()
    ws.append_row(list(rows[0].keys()))
    ws.append_rows([list(r.values()) for r in rows], value_input_option="USER_ENTERED")
    log.info("Write complete for tab '%s'", tab_name)


def get_meta(tab: str) -> dict:
    ss = _get_spreadsheet()
    ws = _ensure_tab(ss, "_meta")
    records = ws.get_all_records()
    for row in records:
        if row.get("tab_name") == tab:
            return row
    return {}


def set_meta(tab: str, fingerprint: str = "", last_row_time: str = "") -> None:
    ss = _get_spreadsheet()
    ws = _ensure_tab(ss, "_meta")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    existing = ws.get_all_values()
    if not existing:
        ws.append_row(["tab_name", "last_fingerprint", "last_row_time", "last_written_at"])
        ws.append_row([tab, fingerprint, last_row_time, now])
        return

    records = ws.get_all_records()
    for i, row in enumerate(records):
        if row.get("tab_name") == tab:
            row_num = i + 2  # 1-indexed + header
            ws.update(f"A{row_num}:D{row_num}", [[tab, fingerprint, last_row_time, now]])
            return

    ws.append_row([tab, fingerprint, last_row_time, now])


def compute_batch_fingerprint(rows: list[dict], key_cols: list[str]) -> str:
    sorted_rows = sorted(rows, key=lambda r: tuple(str(r.get(c, "")) for c in key_cols))
    content = "|".join(
        ",".join(str(r.get(c, "")) for c in key_cols)
        for r in sorted_rows
    )
    return hashlib.sha256(content.encode()).hexdigest()
