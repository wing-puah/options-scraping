"""
Google Drive client.

Folder structure:
  {GOOGLE_DRIVE_FOLDER_ID}/
    {YYYY-MM-DD}/               ← ET trading day
      {prefix}-{YYYYMMDD}-{HHMM}.csv

Use get_drive_client() to build from environment, or construct DriveClient
directly by injecting a googleapiclient service (useful for testing).
"""
import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_DEFAULT_TOKEN = str(Path(__file__).parent.parent / "credentials" / "drive_token.json")

FILE_PREFIXES = {
    "unusual-stocks": "Unusual Options Activity — Stocks",
    "unusual-etfs":   "Unusual Options Activity — ETFs",
    "stocks-flow":    "Options Flow — Stocks",
    "etfs-flow":      "Options Flow — ETFs",
}


# ── Protocol (for testing / dependency inversion) ─────────────────────────────

class StorageClient(Protocol):
    def get_or_create_date_folder(self, date_str: str) -> str: ...
    def file_exists(self, name: str, folder_id: str) -> str | None: ...
    def upload(self, local_path: Path, name: str, folder_id: str) -> str: ...
    def download(self, file_id: str) -> str: ...
    def list_files(self, prefix: str) -> list[dict]: ...
    def download_latest(self, prefix: str) -> tuple[str, str] | tuple[None, None]: ...
    def download_for_date(self, prefix: str, date_str: str) -> tuple[str, str] | tuple[None, None]: ...


# ── Pure helpers ──────────────────────────────────────────────────────────────

def trading_day() -> str:
    """Today's date in ET as YYYY-MM-DD."""
    return datetime.now(ET).strftime("%Y-%m-%d")


def file_name(prefix: str, dt: datetime | None = None) -> str:
    """Canonical filename: {prefix}-{YYYYMMDD}-{HHMM}.csv (ET time)."""
    dt = dt or datetime.now(ET)
    return f"{prefix}-{dt.strftime('%Y%m%d-%H%M')}.csv"


# ── DriveClient ───────────────────────────────────────────────────────────────

class DriveClient:
    """
    Wraps a googleapiclient Drive v3 service with folder-aware file operations.
    The service is injected so tests can pass a mock without real credentials.
    """

    def __init__(self, service, root_folder_id: str) -> None:
        self._svc = service
        self._root = root_folder_id

    def get_or_create_date_folder(self, date_str: str) -> str:
        """Find or create a subfolder named date_str inside the root. Returns folder ID."""
        log.debug("Looking for date folder '%s' in Drive root", date_str)
        q = (
            f"name = '{date_str}' and '{self._root}' in parents "
            f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        files = self._svc.files().list(q=q, fields="files(id)").execute().get("files", [])
        if files:
            folder_id = files[0]["id"]
            log.info("Found existing date folder '%s'", date_str)
            return folder_id
        log.info("Date folder '%s' not found — creating", date_str)
        folder_id = self._svc.files().create(
            body={
                "name": date_str,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [self._root],
            },
            fields="id",
        ).execute()["id"]
        log.info("Created date folder '%s'", date_str)
        return folder_id

    def file_exists(self, name: str, folder_id: str) -> str | None:
        """Return file ID if name exists in folder_id, else None."""
        log.debug("Checking whether '%s' exists in Drive", name)
        q = f"name = '{name}' and '{folder_id}' in parents and trashed = false"
        files = self._svc.files().list(q=q, fields="files(id)").execute().get("files", [])
        if files:
            log.debug("'%s' exists in Drive", name)
            return files[0]["id"]
        log.debug("'%s' not found in Drive", name)
        return None

    def upload(self, local_path: Path, name: str, folder_id: str) -> str:
        """Upload local_path to folder_id. Replaces existing file with same name."""
        log.info("Uploading '%s' from local path '%s' to Drive", name, local_path)
        media = MediaFileUpload(str(local_path), mimetype="text/csv", resumable=True)
        q = f"name = '{name}' and '{folder_id}' in parents and trashed = false"
        existing = self._svc.files().list(q=q, fields="files(id)").execute().get("files", [])
        if existing:
            log.info("Replacing existing file '%s'", name)
            file_id = self._svc.files().update(
                fileId=existing[0]["id"], media_body=media, fields="id"
            ).execute()["id"]
        else:
            log.info("Creating new file '%s' in Drive", name)
            file_id = self._svc.files().create(
                body={"name": name, "parents": [folder_id]},
                media_body=media,
                fields="id",
            ).execute()["id"]
        log.info("Upload complete: '%s'", name)
        return file_id

    def download(self, file_id: str) -> str:
        """Download a Drive file by ID and return its text content."""
        log.info("Downloading Drive file")
        buf = io.BytesIO()
        req = self._svc.files().get_media(fileId=file_id)
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        content = buf.getvalue().decode("utf-8", errors="replace")
        log.info("Downloaded Drive file — %d bytes", len(content))
        return content

    def list_files(self, prefix: str) -> list[dict]:
        """
        List all Drive files matching {prefix}-*.csv across all folders, newest first.
        Intentionally has no parent constraint so files in date subfolders are included.
        """
        log.debug("Listing files with prefix '%s'", prefix)
        q = f"name contains '{prefix}-' and name contains '.csv' and trashed = false"
        files = self._svc.files().list(
            q=q, fields="files(id, name, createdTime)", orderBy="name desc"
        ).execute().get("files", [])
        log.info("Found %d file(s) for prefix '%s'", len(files), prefix)
        return files

    def download_latest(self, prefix: str) -> tuple[str, str] | tuple[None, None]:
        """Download the most recent file for prefix. Returns (name, content) or (None, None)."""
        log.info("Fetching latest file for prefix '%s'", prefix)
        files = self.list_files(prefix)
        if not files:
            log.warning("No files found for prefix '%s'", prefix)
            return None, None
        latest = files[0]
        log.info("Latest file for prefix '%s': '%s'", prefix, latest["name"])
        return latest["name"], self.download(latest["id"])

    def download_for_date(self, prefix: str, date_str: str) -> tuple[str, str] | tuple[None, None]:
        """Download the most recent file for prefix on date_str (YYYY-MM-DD)."""
        log.info("Fetching file for prefix '%s' on date '%s'", prefix, date_str)
        compact = date_str.replace("-", "")
        all_files = self.list_files(prefix)
        files = [f for f in all_files if f["name"].startswith(f"{prefix}-{compact}-")]
        if not files:
            log.warning("No files found for prefix '%s' on date '%s'", prefix, date_str)
            return None, None
        selected = files[0]
        log.info("Selected file '%s' for date '%s'", selected["name"], date_str)
        return selected["name"], self.download(selected["id"])


# ── Factory ───────────────────────────────────────────────────────────────────

def _build_service():
    import json

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_content = os.getenv("GOOGLE_OAUTH_TOKEN_JSON_CONTENT")
    log.debug("Loading Drive credentials")
    if token_content:
        log.debug("Loading Drive token from env content")
        creds = Credentials.from_authorized_user_info(json.loads(token_content), SCOPES)
        token_path = None
    else:
        token_path = Path(os.getenv("GOOGLE_OAUTH_TOKEN_JSON") or _DEFAULT_TOKEN)
        if not token_path.exists():
            log.error("Drive token not found — run scripts/auth_drive.py")
            raise RuntimeError(
                "Drive token not found. Run: python3 scripts/auth_drive.py"
            )
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        log.info("Drive token expired — refreshing")
        creds.refresh(Request())
        if token_path is not None:
            token_path.write_text(creds.to_json())
            log.info("Drive token refreshed and saved")
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    log.debug("Drive service built successfully")
    return svc


def get_drive_client() -> DriveClient:
    """Build a DriveClient from environment variables."""
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if not folder_id:
        log.error("GOOGLE_DRIVE_FOLDER_ID not set in .env")
        raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID not set in .env")
    log.info("Building DriveClient")
    return DriveClient(_build_service(), folder_id)
