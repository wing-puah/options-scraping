"""
Push/pull dated snapshots of the irreplaceable local research caches under
`backtests/` to/from the operator's Google Drive.

WHY: CLAUDE.md's "backtests/ is NOT uniformly disposable" sharp edge lists
exactly what this backs up — `option_history_cache/` (~337MB / ~20k scraped
option-history files, the real short-leg prices every study depends on),
`to_evaluate/` (the Sheets CSV exports; `make export-tabs` re-pulls the tabs
that still exist, but not a deleted one nor the hand-written date lists), and
`live_loop/` (point-in-time broker snapshots that cannot be refetched for a
past date). None of it has git history, none of it lives anywhere but the
local checkout, and Barchart's lookback window means a lapsed local copy may
not even be re-scrapable later. This script is the backup: `push` archives
whichever of those trees exist locally into one dated `.tar.gz` and uploads
it to Drive; `pull` downloads the newest (or a named) snapshot and extracts
it ADDITIVELY — it never overwrites a file that already exists locally,
because a fresh checkout's cache may be older than the snapshot but a long-
running local checkout's cache may well be NEWER. Run `pull` on a fresh
checkout before any study run that needs real bars or priceable
counterparts; run `push` by hand after a scrape that grew the caches.

Research tier — hand-run, never scheduled, never imported by production or
by scripts/backtest_study/.

The "refuse push while a fetch is in-flight" rail from the spec is
deliberately NOT implemented: there is no lock/PID file convention anywhere
in this repo's fetch scripts to check trivially, and the spec says to skip
the guard rather than invent one.

Usage:
  python3 scripts/backup_research_caches.py push
  python3 scripts/backup_research_caches.py push --dry-run
  python3 scripts/backup_research_caches.py pull                 # newest snapshot, additive
  python3 scripts/backup_research_caches.py pull --stamp 20260819-1200
  python3 scripts/backup_research_caches.py pull --force          # overwrite existing files too
  python3 scripts/backup_research_caches.py list
"""
from __future__ import annotations

import argparse
import io
import logging
import re
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))  # lib.*, scripts.*
from googleapiclient.http import MediaIoBaseDownload  # noqa: E402

from lib.logger import setup_logging  # noqa: E402
from lib.drive_client import DriveClient, get_drive_client  # noqa: E402
from scripts.clean_generated import PROTECTED_PREFIXES  # noqa: E402

log = logging.getLogger("backup_research_caches")

ROOT = Path(__file__).resolve().parents[1]

BACKUP_FOLDER_NAME = "research-cache-backups"
ARCHIVE_PREFIX = "research-caches-"
_ARCHIVE_RE = re.compile(r"^research-caches-(\d{8}-\d{4})\.tar\.gz$")


def _human(n: int) -> str:
    """Byte count as a short human string (976 -> '976B', 1200 -> '1.2K')."""
    for unit, size in (("G", 1024 ** 3), ("M", 1024 ** 2), ("K", 1024)):
        if n >= size:
            return f"{n / size:.1f}{unit}"
    return f"{n}B"


# ── What to archive ─────────────────────────────────────────────────────────

def existing_prefixes(root: Path) -> list[str]:
    """PROTECTED_PREFIXES entries under `backtests/` that exist locally.

    PROTECTED_PREFIXES (scripts/clean_generated.py) also covers journal/,
    credentials/, research/, etc. — trees that are either already tracked
    elsewhere or out of scope for this backup, per CLAUDE.md: this script
    "never touch[es] anything outside backtests/".
    """
    return sorted(
        p for p in PROTECTED_PREFIXES
        if p.startswith("backtests/") and (root / p).exists()
    )


def build_archive(root: Path, dest: Path, prefixes: list[str]) -> dict[str, int]:
    """Tar+gzip `prefixes` (repo-relative) under `root` into `dest`.

    Members are stored with paths relative to `root`
    (e.g. "backtests/option_history_cache/AAPL.csv"), so extracting the
    archive from the repo root lands every file back in place. Returns the
    file count added per prefix, for the push report.
    """
    counts: dict[str, int] = {}
    with tarfile.open(dest, "w:gz") as tar:
        for prefix in prefixes:
            src = root / prefix
            n = 0
            if src.is_file():
                tar.add(src, arcname=prefix)
                n = 1
            elif src.is_dir():
                for path in sorted(src.rglob("*")):
                    if path.is_file():
                        arcname = str(Path(prefix) / path.relative_to(src))
                        tar.add(path, arcname=arcname)
                        n += 1
            counts[prefix] = n
    return counts


# ── Drive access gaps worked around here (not in lib/drive_client.py) ───────
#
# DriveClient has no generic "list a folder's children" method: list_files()
# hardcodes `.csv` in its query (built for the flow corpus) and our archives
# are `.tar.gz`, and list_date_folders() only returns folders. Worse,
# DriveClient.download() decodes the response as UTF-8 TEXT (`errors=
# "replace"`) — fine for CSV, silently corrupting for a gzip archive's raw
# bytes. Both are read-only, minimal reaches into the injected
# `googleapiclient` service DriveClient wraps (the same object
# `DriveClient(service, root_folder_id)` takes for testing) rather than
# edits to drive_client.py.

def _list_folder_files(client: DriveClient, folder_id: str) -> list[dict]:
    """Every file directly inside folder_id: id, name, size, createdTime."""
    q = f"'{folder_id}' in parents and trashed = false"
    out: list[dict] = []
    page_token = None
    while True:
        resp = client._svc.files().list(
            q=q, fields="nextPageToken, files(id, name, size, createdTime)",
            pageSize=1000, pageToken=page_token,
        ).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def _download_binary(client: DriveClient, file_id: str) -> bytes:
    """Download file_id's raw bytes (mirrors DriveClient.download()'s chunk
    loop without the lossy UTF-8 decode)."""
    buf = io.BytesIO()
    req = client._svc.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


# ── Snapshot selection ───────────────────────────────────────────────────────

def parse_stamp(name: str) -> str | None:
    """`research-caches-YYYYMMDD-HHMM.tar.gz` -> `YYYYMMDD-HHMM`, else None."""
    m = _ARCHIVE_RE.match(name)
    return m.group(1) if m else None


def select_snapshot(files: list[dict], stamp: str | None) -> dict | None:
    """Pick `stamp`'s file, or the newest by stamp when `stamp` is None."""
    dated = [(parse_stamp(f["name"]), f) for f in files]
    dated = [(s, f) for s, f in dated if s]
    if stamp is not None:
        for s, f in dated:
            if s == stamp:
                return f
        return None
    if not dated:
        return None
    return max(dated, key=lambda sf: sf[0])[1]


# ── Extraction (path-traversal guarded) ──────────────────────────────────────

def _safe_member_target(name: str, root: Path) -> Path | None:
    """The extraction target for a tar member's path, or None if unsafe.

    Rejects an absolute path outright (readable diagnostic even though the
    `root / name` join below would already drop `root` for one — pathlib
    absolute-component joins discard the left side) and anything that
    resolves outside `root` (`../..` traversal) or outside `backtests/`
    (defence in depth: a well-formed archive from build_archive() never
    produces a member outside it).
    """
    if not name or name.startswith("/") or name.startswith("\\"):
        return None
    if not name.startswith("backtests/"):
        return None
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def extract_additive(archive_bytes: bytes, root: Path, force: bool) -> dict[str, list[str]]:
    """Extract `archive_bytes` under `root`.

    Default (force=False): only files that do NOT already exist locally are
    written — a local cache may hold newer scrapes than the snapshot, so a
    silent overwrite could regress it. force=True restores everything.

    Every member's path is validated BEFORE anything is written; one unsafe
    member aborts the whole extraction rather than partially applying it.
    """
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tar:
        members = [m for m in tar.getmembers() if m.isfile()]
        unsafe = [m.name for m in members if _safe_member_target(m.name, root) is None]
        if unsafe:
            raise ValueError(
                f"refusing to extract — unsafe path(s) in archive: {unsafe}")

        added: list[str] = []
        skipped: list[str] = []
        overwritten: list[str] = []
        for member in members:
            target = _safe_member_target(member.name, root)
            exists = target.exists()
            if exists and not force:
                skipped.append(member.name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            target.write_bytes(extracted.read())
            (overwritten if exists else added).append(member.name)
    return {"added": added, "skipped": skipped, "overwritten": overwritten}


# ── Commands ──────────────────────────────────────────────────────────────

def cmd_push(args, root: Path = ROOT, client: DriveClient | None = None) -> int:
    prefixes = existing_prefixes(root)
    if not prefixes:
        print("No protected backtests/ trees found locally — nothing to back up.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = f"{ARCHIVE_PREFIX}{stamp}.tar.gz"
    tmp_path = Path(tempfile.gettempdir()) / name
    try:
        counts = build_archive(root, tmp_path, prefixes)
        size = tmp_path.stat().st_size
        print(f"Archive: {name}  ({_human(size)})")
        for prefix in prefixes:
            print(f"  {prefix}: {counts.get(prefix, 0)} files")

        if args.dry_run:
            print("(dry run — nothing uploaded)")
            return 0

        client = client or get_drive_client()
        folder_id = client.get_or_create_date_folder(BACKUP_FOLDER_NAME)
        file_id = client.upload(tmp_path, name, folder_id)
        print(f"Uploaded '{name}' to Drive (file id {file_id})")
        return 0
    finally:
        tmp_path.unlink(missing_ok=True)


def cmd_pull(args, root: Path = ROOT, client: DriveClient | None = None) -> int:
    client = client or get_drive_client()
    folder_id = client.find_date_folder(BACKUP_FOLDER_NAME)
    if folder_id is None:
        print(f"No '{BACKUP_FOLDER_NAME}' folder on Drive yet — nothing to pull.")
        return 1

    files = _list_folder_files(client, folder_id)
    stamp = getattr(args, "stamp", None)
    snap = select_snapshot(files, stamp)
    if snap is None:
        print(f"No snapshot stamped {stamp} found." if stamp else "No snapshots found.")
        return 1

    print(f"Snapshot: {snap['name']}")
    data = _download_binary(client, snap["id"])
    result = extract_additive(data, root, force=args.force)
    print(f"Files added: {len(result['added'])}")
    print(f"Files skipped (already exist): {len(result['skipped'])}")
    if args.force:
        print(f"Files overwritten: {len(result['overwritten'])}")
    return 0


def cmd_list(args, client: DriveClient | None = None) -> int:
    client = client or get_drive_client()
    folder_id = client.find_date_folder(BACKUP_FOLDER_NAME)
    if folder_id is None:
        print(f"No '{BACKUP_FOLDER_NAME}' folder on Drive yet.")
        return 0

    files = _list_folder_files(client, folder_id)
    dated = sorted(
        ((parse_stamp(f["name"]), f) for f in files if parse_stamp(f["name"])),
        key=lambda sf: sf[0], reverse=True,
    )
    if not dated:
        print("No snapshots found.")
        return 0
    for stamp, f in dated:
        size = int(f.get("size") or 0)
        print(f"  {stamp}  {_human(size):>7}  {f['name']}")
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    desc = "Push/pull dated snapshots of backtests/ research caches to/from Google Drive."
    parser = argparse.ArgumentParser(description=desc)
    sub = parser.add_subparsers(dest="command", required=True)

    p_push = sub.add_parser("push", help="archive local backtests/ caches and upload to Drive")
    p_push.add_argument("--dry-run", action="store_true",
                        help="build the archive locally, print everything, upload nothing")

    p_pull = sub.add_parser("pull", help="download and extract a snapshot (additive by default)")
    p_pull.add_argument("--stamp", metavar="YYYYMMDD-HHMM",
                        help="pull this specific snapshot instead of the newest")
    p_pull.add_argument("--force", action="store_true",
                        help="overwrite existing local files too (full restore)")

    sub.add_parser("list", help="print available snapshots with sizes and stamps")

    args = parser.parse_args(argv)
    setup_logging()

    if args.command == "push":
        return cmd_push(args)
    if args.command == "pull":
        return cmd_pull(args)
    if args.command == "list":
        return cmd_list(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
