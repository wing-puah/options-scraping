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
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
# Full Drive scope (not drive.file): drive.file only exposes files THIS OAuth client
# created, so folders/files added via the web UI or copy-paste are invisible to it.
# Full scope lets the pipeline read + re-upload such folders (e.g. hand-copied date
# folders). Requires re-running scripts/auth_drive.py to re-consent.
SCOPES = ["https://www.googleapis.com/auth/drive",
          "https://www.googleapis.com/auth/spreadsheets",]
_DEFAULT_TOKEN = str(
    Path(__file__).parent.parent / "credentials" / "drive_token.json"
)

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
    def find_date_folder(self, date_str: str) -> str | None: ...
    def list_date_folders(self) -> dict[str, str]: ...

    def download_latest(self, prefix: str) -> tuple[str,
                                                    str] | tuple[None, None]: ...
    def download_for_date(
        self, prefix: str, date_str: str) -> tuple[str, str] | tuple[None, None]: ...


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
        media = MediaFileUpload(
            str(local_path), mimetype="text/csv", resumable=True)
        q = f"name = '{name}' and '{folder_id}' in parents and trashed = false"
        existing = self._svc.files().list(
            q=q, fields="files(id)").execute().get("files", [])
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

    def download(self, file_id: str, name: str | None = None) -> str:
        """Download a Drive file by ID and return its text content."""
        label = f"'{name}'" if name else file_id
        log.info("Downloading Drive file %s", label)
        buf = io.BytesIO()
        req = self._svc.files().get_media(fileId=file_id)
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        content = buf.getvalue().decode("utf-8", errors="replace")
        log.info("Downloaded Drive file %s — %d bytes", label, len(content))
        return content

    def trash(self, file_id: str) -> None:
        """Move a Drive file to trash. Recoverable for ~30 days, then auto-purged.

        Preferred over a hard delete for cleanup steps so a bad run is reversible;
        trashed files no longer match list queries (which filter trashed = false).
        """
        log.debug("Trashing Drive file")
        self._svc.files().update(fileId=file_id, body={
            "trashed": True}).execute()

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
        return latest["name"], self.download(latest["id"], name=latest["name"])

    def find_date_folder(self, date_str: str) -> str | None:
        """Return the folder ID for date_str, or None if it doesn't exist (read-only)."""
        q = (
            f"name = '{date_str}' and '{self._root}' in parents "
            f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        files = self._svc.files().list(q=q, fields="files(id)").execute().get("files", [])
        return files[0]["id"] if files else None

    # Backwards-compatible private alias for existing internal callers.
    _find_date_folder = find_date_folder

    _DATE_FOLDER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def list_date_folders(self) -> dict[str, str]:
        """{YYYY-MM-DD: folder_id} for every trading-day folder directly under the root.

        One paginated query against the root's direct children — cheaper and more
        reliable than a global `name contains` file search, which has no parent
        constraint and silently truncates at the first results page. Callers then look
        inside a specific date folder for the exact file they want.
        """
        q = (f"'{self._root}' in parents "
             f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
        folders: dict[str, str] = {}
        page_token = None
        while True:
            resp = self._svc.files().list(
                q=q, fields="nextPageToken, files(id, name)", pageSize=1000,
                pageToken=page_token,
            ).execute()
            for f in resp.get("files", []):
                if self._DATE_FOLDER_RE.match(f["name"]):
                    folders[f["name"]] = f["id"]
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        log.info("Found %d date folder(s) under Drive root", len(folders))
        return folders

    def list_files_for_date(self, prefix: str, date_str: str) -> list[dict]:
        """All timestamped snapshot files for prefix on date_str (YYYY-MM-DD), oldest→newest.

        Matches only `{prefix}-YYYYMMDD-HHMM.csv` snapshots; derived files such as
        `{prefix}-YYYYMMDD-compiled.csv` are excluded so a compiled output is never
        fed back in as input. Sorted chronologically by name.
        """
        log.debug("Listing files with prefix '%s' for date '%s'", prefix, date_str)
        folder_id = self._find_date_folder(date_str)
        if folder_id is None:
            log.info("No date folder found for '%s' — 0 snapshots", date_str)
            return []
        compact = date_str.replace("-", "")
        pattern = re.compile(rf"^{re.escape(prefix)}-{compact}-\d{{4}}\.csv$")
        q = f"'{folder_id}' in parents and name contains '{prefix}-' and trashed = false"
        files = self._svc.files().list(
            q=q, fields="files(id, name, createdTime)", orderBy="name"
        ).execute().get("files", [])
        files = sorted(
            [f for f in files if pattern.match(f["name"])],
            key=lambda f: f["name"],
        )
        log.info("Found %d snapshot(s) for prefix '%s' on %s", len(files), prefix, date_str)
        return files

    def list_day_files(self, prefix: str, date_str: str) -> list[dict]:
        """Files to process for date_str: compiled file if present, all snapshots otherwise."""
        folder_id = self._find_date_folder(date_str)
        if folder_id is None:
            return []
        compact = date_str.replace("-", "")
        q = (f"'{folder_id}' in parents and name contains '{prefix}-{compact}-' "
             f"and trashed = false")
        files = self._svc.files().list(
            q=q, fields="files(id, name, createdTime)", orderBy="name"
        ).execute().get("files", [])
        compiled = [f for f in files if f["name"].endswith("-compiled.csv")]
        return compiled if compiled else files

    def download_for_date(self, prefix: str, date_str: str) -> tuple[str, str] | tuple[None, None]:
        """Download the most recent file for prefix on date_str (YYYY-MM-DD)."""
        log.info("Fetching file for prefix '%s' on date '%s'", prefix, date_str)
        folder_id = self._find_date_folder(date_str)
        if folder_id is None:
            log.warning("No date folder found for '%s'", date_str)
            return None, None
        compact = date_str.replace("-", "")
        q = (
            f"'{folder_id}' in parents and name contains '{prefix}-{compact}-' "
            f"and trashed = false"
        )
        files = self._svc.files().list(
            q=q, fields="files(id, name, createdTime)", orderBy="name desc"
        ).execute().get("files", [])
        if not files:
            log.warning("No files found for prefix '%s' on date '%s'", prefix, date_str)
            return None, None
        selected = files[0]
        log.info("Selected file '%s' for date '%s'", selected["name"], date_str)
        return selected["name"], self.download(selected["id"], name=selected["name"])


# ── Factory ───────────────────────────────────────────────────────────────────

def _build_service():
    token_content = os.getenv("GOOGLE_OAUTH_TOKEN_JSON_CONTENT")
    log.debug("Loading Drive credentials")
    if token_content:
        log.debug("Loading Drive token from env content")
        creds = Credentials.from_authorized_user_info(
            json.loads(token_content), SCOPES)
        token_path = None
    else:
        token_path = Path(
            os.getenv("GOOGLE_OAUTH_TOKEN_JSON") or _DEFAULT_TOKEN)
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
            token_path.write_text(creds.to_json(), encoding="utf-8")
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
