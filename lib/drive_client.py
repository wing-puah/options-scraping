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
from typing import NamedTuple, Protocol
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


# The naming convention, in ONE place. Both the per-folder path
# (list_files_for_date) and the corpus-wide path (flow_corpus) decide "which date
# is this, and is it a snapshot or a compiled file?" through classify_flow_name,
# so the two can never disagree about a filename. The (\d{4}|compiled) alternation
# is what keeps an HHMM stamp from ever reading as a compiled file, or vice versa.
_FLOW_NAME_RE = re.compile(r"^(\d{8})-(\d{4}|compiled)\.csv$")

SNAPSHOT, COMPILED = "snapshot", "compiled"


def classify_flow_name(name: str, prefix: str) -> tuple[str, str] | None:
    """Parse a flow filename into (YYYY-MM-DD, SNAPSHOT | COMPILED).

    Returns None when `name` does not follow prefix's convention — a different
    prefix, a malformed date or time, or any other file that happens to live in
    the same folder. Callers treat None as "not part of the flow corpus".
    """
    if not name.startswith(f"{prefix}-"):
        return None
    m = _FLOW_NAME_RE.match(name[len(prefix) + 1:])
    if not m:
        return None
    compact, kind = m.groups()
    date_str = f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
    return date_str, (COMPILED if kind == COMPILED else SNAPSHOT)


def snapshot_files(files: list[dict], prefix: str, date_str: str) -> list[dict]:
    """Filter a folder listing down to prefix's snapshots for date_str, oldest→newest.

    The in-memory equivalent of DriveClient.list_files_for_date, for a caller that
    already holds the folder's listing. Compiled files are excluded, so a compiled
    output is never fed back in as input.
    """
    return sorted(
        (f for f in files
         if classify_flow_name(f["name"], prefix) == (date_str, SNAPSHOT)),
        key=lambda f: f["name"],
    )


class FlowCorpus(NamedTuple):
    """What flow files exist across the WHOLE corpus, built in a bounded number of
    Drive calls (see DriveClient.flow_corpus).

    `folders` is {YYYY-MM-DD: folder_id}, exactly list_date_folders()'s shape.
    `files` is {date: {prefix: {"compiled": bool, "snapshots": int}}}; a date or
    prefix absent from it simply has nothing, so read it through the accessors
    below rather than indexing directly.
    """

    folders: dict[str, str]
    files: dict[str, dict[str, dict]]

    def has_compiled(self, date_str: str, prefix: str) -> bool:
        """Does prefix have a compiled file on date_str?"""
        return bool(self.files.get(date_str, {}).get(prefix, {}).get("compiled"))

    def snapshot_count(self, date_str: str, prefix: str) -> int:
        """How many raw snapshots prefix has on date_str (compiled files excluded)."""
        return self.files.get(date_str, {}).get(prefix, {}).get("snapshots", 0)


# ── DriveClient ───────────────────────────────────────────────────────────────

class DriveClient:
    """
    Wraps a googleapiclient Drive v3 service with folder-aware file operations.
    The service is injected so tests can pass a mock without real credentials.
    """

    def __init__(self, service, root_folder_id: str) -> None:
        self._svc = service
        self._root = root_folder_id

    @property
    def root(self) -> str:
        """Root folder ID — for the few files that are NOT date-partitioned
        (e.g. the SPY/VIX mech-regime table, which is one continuous series)."""
        return self._root

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

    def _paginate(self, q: str, fields: str, order_by: str | None = None) -> list[dict]:
        """Every file matching q, following nextPageToken to the last page.

        Drive returns a limited page by default; a query that reads all results
        MUST paginate or it silently sees a truncated corpus.
        """
        params = {"q": q, "fields": f"nextPageToken, files({fields})", "pageSize": 1000}
        if order_by:
            params["orderBy"] = order_by
        out: list[dict] = []
        page_token = None
        while True:
            resp = self._svc.files().list(**params, pageToken=page_token).execute()
            out.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    def list_date_folders(self) -> dict[str, str]:
        """{YYYY-MM-DD: folder_id} for every trading-day folder directly under the root.

        One paginated query against the root's direct children — cheaper and more
        reliable than a global `name contains` file search, which has no parent
        constraint and silently truncates at the first results page. Callers then look
        inside a specific date folder for the exact file they want.
        """
        q = (f"'{self._root}' in parents "
             f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
        folders = {f["name"]: f["id"] for f in self._paginate(q, "id, name")
                   if self._DATE_FOLDER_RE.match(f["name"])}
        log.info("Found %d date folder(s) under Drive root", len(folders))
        return folders

    def flow_corpus(self, prefixes: list[str]) -> FlowCorpus:
        """Index what flow files exist for every date, in a BOUNDED number of calls.

        One paginated query per prefix plus one for the date folders — roughly ten
        round trips for the whole corpus, regardless of how many dates it holds.
        The per-date alternative (a file_exists per prefix per date) costs two to
        six calls PER DATE and grows without limit as the corpus does; that is what
        this replaces.

        A file is indexed only if its name follows the convention AND it sits
        directly in the date folder its own name claims. The query has no parent
        constraint (Drive cannot express "in any of these folders"), so this check
        is what keeps a same-named file from elsewhere in the Drive — or one
        misfiled under the wrong date — out of the index.
        """
        folders = self.list_date_folders()
        files: dict[str, dict[str, dict]] = {}
        skipped = 0
        for prefix in prefixes:
            q = (f"name contains '{prefix}-' and name contains '.csv' "
                 f"and trashed = false")
            for f in self._paginate(q, "id, name, parents"):
                parsed = classify_flow_name(f["name"], prefix)
                if parsed is None:
                    continue
                date_str, kind = parsed
                # The file must live in the date folder its NAME claims — not merely
                # in some known date folder.
                if folders.get(date_str) not in (f.get("parents") or []):
                    skipped += 1
                    continue
                entry = files.setdefault(date_str, {}).setdefault(
                    prefix, {"compiled": False, "snapshots": 0})
                if kind == COMPILED:
                    entry["compiled"] = True
                else:
                    entry["snapshots"] += 1
        log.info("Built flow corpus: %d date(s) with flow files across %d prefix(es)"
                 "%s", len(files), len(prefixes),
                 f" — {skipped} misfiled file(s) ignored" if skipped else "")
        return FlowCorpus(folders=folders, files=files)

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
        q = f"'{folder_id}' in parents and name contains '{prefix}-' and trashed = false"
        files = self._svc.files().list(
            q=q, fields="files(id, name, createdTime)", orderBy="name"
        ).execute().get("files", [])
        files = snapshot_files(files, prefix, date_str)
        log.info("Found %d snapshot(s) for prefix '%s' on %s", len(files), prefix, date_str)
        return files

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
