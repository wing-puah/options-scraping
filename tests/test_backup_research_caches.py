"""
Tests for `scripts/backup_research_caches.py`.

No real Drive credentials or network calls: Drive interaction is either a
`DriveClient` wrapping a `MagicMock` service (mirrors tests/test_drive_client.py)
or, for pull/list, a bare stub whose `find_date_folder` is enough — the
listing/download helpers (`_list_folder_files`, `_download_binary`) are
monkeypatched directly since they reach past DriveClient's public surface (see
the module docstring for why).
"""
import argparse
import io
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import backup_research_caches as brc
from lib.drive_client import DriveClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _touch(path: Path, body: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def _tar_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class _StubClient:
    """Just enough of DriveClient's surface for pull/list tests."""

    def __init__(self, folder_id: str | None):
        self._folder_id = folder_id

    def find_date_folder(self, name: str) -> str | None:
        return self._folder_id


# ── existing_prefixes ────────────────────────────────────────────────────────

def test_existing_prefixes_filters_to_backtests_and_existing(monkeypatch, tmp_path):
    monkeypatch.setattr(brc, "PROTECTED_PREFIXES", (
        "backtests/option_history_cache", "backtests/to_evaluate", "journal", "config",
    ))
    _touch(tmp_path / "backtests/option_history_cache/AAPL.csv")
    _touch(tmp_path / "journal/foo.csv")  # not under backtests/ — must be excluded
    # backtests/to_evaluate does NOT exist locally — must be excluded too

    assert brc.existing_prefixes(tmp_path) == ["backtests/option_history_cache"]


# ── build_archive ─────────────────────────────────────────────────────────────

def test_build_archive_contains_relative_paths_and_counts(tmp_path):
    _touch(tmp_path / "backtests/option_history_cache/AAPL.csv", "aapl")
    _touch(tmp_path / "backtests/option_history_cache/MSFT.csv", "msft")
    _touch(tmp_path / "backtests/to_evaluate/analysis.csv", "eval")

    dest = tmp_path / "out.tar.gz"
    counts = brc.build_archive(
        tmp_path, dest, ["backtests/option_history_cache", "backtests/to_evaluate"])

    assert counts == {"backtests/option_history_cache": 2, "backtests/to_evaluate": 1}

    with tarfile.open(dest, "r:gz") as tar:
        names = set(tar.getnames())
    assert names == {
        "backtests/option_history_cache/AAPL.csv",
        "backtests/option_history_cache/MSFT.csv",
        "backtests/to_evaluate/analysis.csv",
    }
    assert all(not n.startswith("/") for n in names)


# ── push ──────────────────────────────────────────────────────────────────────

def test_push_dry_run_uploads_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(brc, "PROTECTED_PREFIXES", ("backtests/option_history_cache",))
    _touch(tmp_path / "backtests/option_history_cache/AAPL.csv")

    def _boom():
        raise AssertionError("get_drive_client() must not be called in --dry-run")
    monkeypatch.setattr(brc, "get_drive_client", _boom)

    rc = brc.cmd_push(argparse.Namespace(dry_run=True), root=tmp_path)
    assert rc == 0

    out = capsys.readouterr().out
    assert "dry run" in out
    assert "AAPL" not in out  # per-file names never printed, only counts/sizes

    # The temp archive built to compute size/counts is deleted afterward.
    import re
    m = re.search(r"Archive: (research-caches-\S+\.tar\.gz)", out)
    assert m
    import tempfile
    assert not (Path(tempfile.gettempdir()) / m.group(1)).exists()


@patch("lib.drive_client.MediaFileUpload")
def test_push_uploads_archive_via_drive_client(mock_media, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(brc, "PROTECTED_PREFIXES", ("backtests/option_history_cache",))
    _touch(tmp_path / "backtests/option_history_cache/AAPL.csv")

    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {"files": []}
    svc.files.return_value.create.return_value.execute.side_effect = [
        {"id": "folder-id"},  # get_or_create_date_folder(BACKUP_FOLDER_NAME)
        {"id": "file-id"},    # upload()
    ]
    client = DriveClient(svc, "root-id")

    rc = brc.cmd_push(argparse.Namespace(dry_run=False), root=tmp_path, client=client)
    assert rc == 0

    out = capsys.readouterr().out
    assert "Uploaded" in out
    assert "file-id" in out
    assert svc.files.return_value.create.call_count == 2


def test_push_with_no_local_caches_is_a_noop(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(brc, "PROTECTED_PREFIXES", ("backtests/option_history_cache",))
    rc = brc.cmd_push(argparse.Namespace(dry_run=False), root=tmp_path)
    assert rc == 0
    assert "nothing to back up" in capsys.readouterr().out


# ── pull ──────────────────────────────────────────────────────────────────────

def test_pull_additive_extracts_only_missing_files(monkeypatch, tmp_path, capsys):
    _touch(tmp_path / "backtests/option_history_cache/AAPL.csv", "old-A")  # exists locally

    archive = _tar_bytes({
        "backtests/option_history_cache/AAPL.csv": b"new-A",
        "backtests/option_history_cache/MSFT.csv": b"new-M",
    })
    monkeypatch.setattr(brc, "_list_folder_files", lambda client, folder_id: [
        {"id": "file-id", "name": "research-caches-20260101-0000.tar.gz", "size": "10"},
    ])
    monkeypatch.setattr(brc, "_download_binary", lambda client, file_id: archive)

    client = _StubClient(folder_id="folder-id")
    rc = brc.cmd_pull(argparse.Namespace(stamp=None, force=False), root=tmp_path, client=client)
    assert rc == 0

    assert (tmp_path / "backtests/option_history_cache/AAPL.csv").read_text() == "old-A"
    assert (tmp_path / "backtests/option_history_cache/MSFT.csv").read_text() == "new-M"

    out = capsys.readouterr().out
    assert "Files added: 1" in out
    assert "Files skipped (already exist): 1" in out


def test_pull_force_overwrites_existing_files(monkeypatch, tmp_path, capsys):
    _touch(tmp_path / "backtests/option_history_cache/AAPL.csv", "old-A")

    archive = _tar_bytes({"backtests/option_history_cache/AAPL.csv": b"new-A"})
    monkeypatch.setattr(brc, "_list_folder_files", lambda client, folder_id: [
        {"id": "file-id", "name": "research-caches-20260101-0000.tar.gz", "size": "5"},
    ])
    monkeypatch.setattr(brc, "_download_binary", lambda client, file_id: archive)

    client = _StubClient(folder_id="folder-id")
    rc = brc.cmd_pull(argparse.Namespace(stamp=None, force=True), root=tmp_path, client=client)
    assert rc == 0

    assert (tmp_path / "backtests/option_history_cache/AAPL.csv").read_text() == "new-A"
    out = capsys.readouterr().out
    assert "Files overwritten: 1" in out


def test_pull_selects_requested_stamp(monkeypatch, tmp_path):
    calls = []
    archive_old = _tar_bytes({"backtests/option_history_cache/OLD.csv": b"old"})
    archive_new = _tar_bytes({"backtests/option_history_cache/NEW.csv": b"new"})

    monkeypatch.setattr(brc, "_list_folder_files", lambda client, folder_id: [
        {"id": "id-old", "name": "research-caches-20260101-0000.tar.gz", "size": "1"},
        {"id": "id-new", "name": "research-caches-20260215-1200.tar.gz", "size": "1"},
    ])

    def _dl(client, file_id):
        calls.append(file_id)
        return archive_old if file_id == "id-old" else archive_new

    monkeypatch.setattr(brc, "_download_binary", _dl)

    client = _StubClient(folder_id="folder-id")
    rc = brc.cmd_pull(
        argparse.Namespace(stamp="20260101-0000", force=False), root=tmp_path, client=client)
    assert rc == 0
    assert calls == ["id-old"]
    assert (tmp_path / "backtests/option_history_cache/OLD.csv").exists()
    assert not (tmp_path / "backtests/option_history_cache/NEW.csv").exists()


def test_pull_unknown_stamp_reports_and_does_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(brc, "_list_folder_files", lambda client, folder_id: [
        {"id": "id-old", "name": "research-caches-20260101-0000.tar.gz", "size": "1"},
    ])
    client = _StubClient(folder_id="folder-id")
    rc = brc.cmd_pull(
        argparse.Namespace(stamp="99999999-9999", force=False), root=tmp_path, client=client)
    assert rc == 1
    assert "No snapshot stamped 99999999-9999" in capsys.readouterr().out


def test_pull_no_backup_folder_yet(tmp_path, capsys):
    client = _StubClient(folder_id=None)
    rc = brc.cmd_pull(argparse.Namespace(stamp=None, force=False), root=tmp_path, client=client)
    assert rc == 1
    assert "nothing to pull" in capsys.readouterr().out


# ── select_snapshot / parse_stamp ────────────────────────────────────────────

def test_select_snapshot_picks_newest_by_stamp():
    files = [
        {"name": "research-caches-20260101-0000.tar.gz"},
        {"name": "research-caches-20260215-1200.tar.gz"},
        {"name": "research-caches-20260110-0930.tar.gz"},
        {"name": "not-a-snapshot.tar.gz"},
    ]
    assert brc.select_snapshot(files, None)["name"] == "research-caches-20260215-1200.tar.gz"


def test_select_snapshot_with_explicit_stamp():
    files = [
        {"name": "research-caches-20260101-0000.tar.gz"},
        {"name": "research-caches-20260215-1200.tar.gz"},
    ]
    assert brc.select_snapshot(files, "20260101-0000")["name"] == \
        "research-caches-20260101-0000.tar.gz"
    assert brc.select_snapshot(files, "99999999-9999") is None


# ── extraction safety ─────────────────────────────────────────────────────────

def test_extract_rejects_relative_traversal_member(tmp_path):
    archive = _tar_bytes({"backtests/../../evil.csv": b"pwned"})
    with pytest.raises(ValueError, match="unsafe path"):
        brc.extract_additive(archive, tmp_path, force=False)
    assert not (tmp_path.parent.parent / "evil.csv").exists()
    # Nothing partially written under root either.
    assert list(tmp_path.iterdir()) == []


def test_extract_rejects_absolute_path_member(tmp_path):
    archive = _tar_bytes({"/etc/passwd": b"pwned"})
    with pytest.raises(ValueError, match="unsafe path"):
        brc.extract_additive(archive, tmp_path, force=False)
    assert not Path("/etc/passwd_pwned_by_test").exists()


def test_extract_rejects_member_outside_backtests(tmp_path):
    archive = _tar_bytes({"config/evil.yml": b"pwned"})
    with pytest.raises(ValueError, match="unsafe path"):
        brc.extract_additive(archive, tmp_path, force=False)
    assert not (tmp_path / "config").exists()


def test_extract_aborts_wholesale_when_one_member_is_unsafe(tmp_path):
    # A mix of a legitimate member and a malicious one must write NEITHER —
    # a partial extraction is not a safe outcome.
    archive = _tar_bytes({
        "backtests/option_history_cache/AAPL.csv": b"aapl",
        "../escape.csv": b"pwned",
    })
    with pytest.raises(ValueError):
        brc.extract_additive(archive, tmp_path, force=False)
    assert not (tmp_path / "backtests/option_history_cache/AAPL.csv").exists()


# ── list ──────────────────────────────────────────────────────────────────────

def test_cmd_list_prints_snapshots_newest_first(monkeypatch, capsys):
    monkeypatch.setattr(brc, "_list_folder_files", lambda client, folder_id: [
        {"name": "research-caches-20260101-0000.tar.gz", "size": str(1024 * 1024)},
        {"name": "research-caches-20260215-1200.tar.gz", "size": str(2048)},
    ])
    client = _StubClient(folder_id="folder-id")
    rc = brc.cmd_list(argparse.Namespace(), client=client)
    assert rc == 0

    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if "research-caches-" in line]
    assert lines[0].strip().startswith("20260215-1200")
    assert lines[1].strip().startswith("20260101-0000")


def test_cmd_list_no_backup_folder_yet(capsys):
    client = _StubClient(folder_id=None)
    rc = brc.cmd_list(argparse.Namespace(), client=client)
    assert rc == 0
    assert "No 'research-cache-backups' folder" in capsys.readouterr().out
