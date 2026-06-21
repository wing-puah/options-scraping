import hashlib
import json
import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

load_dotenv(Path(__file__).parent.parent / ".env")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

_DEFAULT_TOKEN = Path(__file__).parent.parent / "credentials" / "drive_token.json"

log = logging.getLogger(__name__)


def _get_client() -> gspread.Client:
    token_content = os.getenv("GOOGLE_OAUTH_TOKEN_JSON_CONTENT")
    if token_content:
        log.debug("Authorising Sheets via OAuth2 token (env content)")
        creds = Credentials.from_authorized_user_info(json.loads(token_content), SCOPES)
        token_path = None
    else:
        token_path = Path(os.getenv("GOOGLE_OAUTH_TOKEN_JSON") or _DEFAULT_TOKEN)
        if not token_path.exists():
            log.error("OAuth token not found — run scripts/auth_drive.py")
            raise RuntimeError("OAuth token not found. Run: python3 scripts/auth_drive.py")
        log.debug("Authorising Sheets via OAuth2 token file")
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds.expired and creds.refresh_token:
        log.info("Sheets OAuth token expired — refreshing")
        creds.refresh(Request())
        if token_path is not None:
            token_path.write_text(creds.to_json(), encoding="utf-8")
            log.info("OAuth token refreshed and saved")

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


def _sanitize(v):
    """Replace non-JSON-compliant floats (nan/inf) with empty string."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return ""
    return v


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
    ws.append_rows([[_sanitize(v) for v in r.values()] for r in rows], value_input_option=option)
    log.info("Appended %d row(s) to tab '%s'", len(rows), tab)


def _col_letter(n: int) -> str:
    """Convert 1-based column number to A1-notation letter (e.g. 8 → 'H')."""
    result = ""
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def write_analysis(tab_name: str, rows: list[dict], preserve_extra_cols: bool = False) -> None:
    """Write rows to a sheet tab, clearing it first.

    preserve_extra_cols=True clears only the managed columns (A:<last key>),
    leaving any columns to the right (e.g. user-added formulas) untouched.
    """
    if not rows:
        return
    log.info("Writing %d row(s) to tab '%s' (clearing first)", len(rows), tab_name)
    ss = _get_spreadsheet()
    ws = _ensure_tab(ss, tab_name)
    keys = list(rows[0].keys())
    data = [keys] + [[r.get(k, "") for k in keys] for r in rows]
    if preserve_extra_cols:
        end_col = _col_letter(len(keys))
        ws.batch_clear([f"A:{end_col}"])
    else:
        ws.clear()
    ws.update("A1", data, value_input_option="USER_ENTERED")
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
