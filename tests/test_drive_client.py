from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from lib.drive_client import (
    DriveClient,
    classify_flow_name,
    file_name,
    snapshot_files,
    trading_day,
)

ET = ZoneInfo("America/New_York")


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_svc(list_result=None, create_result=None, update_result=None):
    """Build a mock googleapiclient service with pre-set return values."""
    svc = MagicMock()
    if list_result is not None:
        svc.files.return_value.list.return_value.execute.return_value = {"files": list_result}
    if create_result is not None:
        svc.files.return_value.create.return_value.execute.return_value = create_result
    if update_result is not None:
        svc.files.return_value.update.return_value.execute.return_value = update_result
    return svc


# ── file_name ─────────────────────────────────────────────────────────────────

def test_file_name_with_explicit_dt():
    dt = datetime(2026, 6, 2, 10, 30, tzinfo=ET)
    assert file_name("unusual-stocks", dt) == "unusual-stocks-20260602-1030.csv"


def test_file_name_prefix_variations():
    dt = datetime(2026, 1, 1, 9, 5, tzinfo=ET)
    assert file_name("stocks-flow", dt) == "stocks-flow-20260101-0905.csv"
    assert file_name("etfs-flow", dt)   == "etfs-flow-20260101-0905.csv"


# ── file_exists ───────────────────────────────────────────────────────────────

def test_file_exists_returns_id_when_found():
    svc = make_svc(list_result=[{"id": "abc123"}])
    client = DriveClient(svc, "root-id")
    assert client.file_exists("test.csv", "folder-id") == "abc123"


def test_file_exists_returns_none_when_not_found():
    svc = make_svc(list_result=[])
    client = DriveClient(svc, "root-id")
    assert client.file_exists("test.csv", "folder-id") is None


# ── get_or_create_date_folder ─────────────────────────────────────────────────

def test_get_or_create_date_folder_returns_existing():
    svc = make_svc(list_result=[{"id": "folder-123"}])
    client = DriveClient(svc, "root-id")
    result = client.get_or_create_date_folder("2026-06-02")
    assert result == "folder-123"
    svc.files.return_value.create.assert_not_called()


def test_get_or_create_date_folder_creates_when_missing():
    svc = make_svc(list_result=[], create_result={"id": "new-folder"})
    client = DriveClient(svc, "root-id")
    result = client.get_or_create_date_folder("2026-06-02")
    assert result == "new-folder"
    # Verify it was created with the right metadata
    call_kwargs = svc.files.return_value.create.call_args.kwargs
    assert call_kwargs["body"]["name"] == "2026-06-02"
    assert call_kwargs["body"]["mimeType"] == "application/vnd.google-apps.folder"
    assert call_kwargs["body"]["parents"] == ["root-id"]


def test_drive_identifiers_are_not_logged(caplog):
    svc = make_svc(list_result=[{"id": "secret-folder-id", "name": "2026-06-02",
                                 "parents": ["secret-root-id"]}])
    client = DriveClient(svc, "secret-root-id")

    with caplog.at_level("DEBUG", logger="lib.drive_client"):
        client.get_or_create_date_folder("2026-06-02")
        client.file_exists("test.csv", "secret-folder-id")
        client.flow_corpus(["etfs-flow"])

    assert "secret-root-id" not in caplog.text
    assert "secret-folder-id" not in caplog.text


# ── classify_flow_name ────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, expected", [
    ("etfs-flow-20260602-1600.csv",   ("2026-06-02", "snapshot")),
    ("etfs-flow-20260602-compiled.csv", ("2026-06-02", "compiled")),
    ("stocks-flow-20260602-1600.csv", None),      # different prefix
    ("etfs-flow-20260602-16000.csv",  None),      # 5-digit time
    ("etfs-flow-2026060-1600.csv",    None),      # 7-digit date
    ("etfs-flow-20260602-1600.txt",   None),      # not a csv
    ("etfs-flow-20260602-compiled-v2.csv", None),  # trailing junk
    ("etfs-flow-counterpart-20260602.csv", None),  # sidecar, not a flow file
])
def test_classify_flow_name(name, expected):
    assert classify_flow_name(name, "etfs-flow") == expected


def test_snapshot_files_excludes_compiled_and_other_dates():
    files = [
        {"name": "etfs-flow-20260602-1600.csv"},
        {"name": "etfs-flow-20260602-0930.csv"},
        {"name": "etfs-flow-20260602-compiled.csv"},   # never fed back in as input
        {"name": "etfs-flow-20260603-1600.csv"},       # different date
        {"name": "stocks-flow-20260602-1600.csv"},     # different prefix
    ]
    got = [f["name"] for f in snapshot_files(files, "etfs-flow", "2026-06-02")]
    assert got == ["etfs-flow-20260602-0930.csv", "etfs-flow-20260602-1600.csv"]


# ── pagination / flow_corpus ──────────────────────────────────────────────────

def _page(files, token=None):
    return {"files": files, **({"nextPageToken": token} if token else {})}


def test_paginated_queries_follow_next_page_token():
    """A query that reads ALL results must paginate — Drive truncates at one page,
    which is how a corpus scan silently sees only part of the corpus."""
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.side_effect = [
        _page([{"id": "f1", "name": "2026-06-01"}], token="t1"),
        _page([{"id": "f2", "name": "2026-06-02"}]),
    ]
    client = DriveClient(svc, "root-id")
    assert client.list_date_folders() == {"2026-06-01": "f1", "2026-06-02": "f2"}


def test_flow_corpus_indexes_compiled_and_snapshots_across_prefixes():
    folders = [{"id": "folder-A", "name": "2026-06-02"}]

    def _list(**kw):
        resp = MagicMock()
        if "google-apps.folder" in kw["q"]:
            resp.execute.return_value = _page(folders)
        elif "etfs-flow" in kw["q"]:
            resp.execute.return_value = _page([
                {"id": "1", "name": "etfs-flow-20260602-compiled.csv", "parents": ["folder-A"]},
                {"id": "2", "name": "etfs-flow-20260602-0930.csv", "parents": ["folder-A"]},
            ])
        else:
            resp.execute.return_value = _page([
                {"id": "3", "name": "stocks-flow-20260602-0930.csv", "parents": ["folder-A"]},
                {"id": "4", "name": "stocks-flow-20260602-1600.csv", "parents": ["folder-A"]},
            ])
        return resp

    svc = MagicMock()
    svc.files.return_value.list.side_effect = _list
    corpus = DriveClient(svc, "root-id").flow_corpus(["etfs-flow", "stocks-flow"])

    assert corpus.has_compiled("2026-06-02", "etfs-flow") is True
    assert corpus.has_compiled("2026-06-02", "stocks-flow") is False
    assert corpus.snapshot_count("2026-06-02", "etfs-flow") == 1     # compiled not counted
    assert corpus.snapshot_count("2026-06-02", "stocks-flow") == 2
    assert corpus.has_compiled("2026-06-03", "etfs-flow") is False   # absent date
    assert corpus.snapshot_count("2026-06-03", "etfs-flow") == 0


def test_flow_corpus_rejects_files_outside_their_own_date_folder():
    """The corpus query has no parent constraint (Drive can't express "in any of
    these folders"), so a same-named file elsewhere in the Drive — or one misfiled
    under a date folder that disagrees with its own name — must be dropped."""
    folders = [{"id": "folder-A", "name": "2026-06-02"},
               {"id": "folder-B", "name": "2026-06-03"}]

    def _list(**kw):
        resp = MagicMock()
        if "google-apps.folder" in kw["q"]:
            resp.execute.return_value = _page(folders)
        else:
            resp.execute.return_value = _page([
                {"id": "1", "name": "etfs-flow-20260602-compiled.csv", "parents": ["folder-A"]},
                # right name, WRONG folder — claims the 3rd, sits in the 2nd
                {"id": "2", "name": "etfs-flow-20260603-compiled.csv", "parents": ["folder-A"]},
                # somewhere else in the Drive entirely
                {"id": "3", "name": "etfs-flow-20260603-1600.csv", "parents": ["unrelated"]},
            ])
        return resp

    svc = MagicMock()
    svc.files.return_value.list.side_effect = _list
    corpus = DriveClient(svc, "root-id").flow_corpus(["etfs-flow"])

    assert corpus.has_compiled("2026-06-02", "etfs-flow") is True
    assert corpus.has_compiled("2026-06-03", "etfs-flow") is False
    assert corpus.snapshot_count("2026-06-03", "etfs-flow") == 0


# ── upload ────────────────────────────────────────────────────────────────────

@patch("lib.drive_client.MediaFileUpload")
def test_upload_creates_new_file(mock_media, tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Symbol,Volume\nAAPL,1000\n")

    svc = make_svc(list_result=[], create_result={"id": "new-file-id"})
    client = DriveClient(svc, "root-id")
    result = client.upload(csv_file, "test.csv", "folder-id")

    assert result == "new-file-id"
    svc.files.return_value.update.assert_not_called()


@patch("lib.drive_client.MediaFileUpload")
def test_upload_updates_existing_file(mock_media, tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Symbol,Volume\nAAPL,1000\n")

    svc = make_svc(list_result=[{"id": "existing-id"}], update_result={"id": "existing-id"})
    client = DriveClient(svc, "root-id")
    result = client.upload(csv_file, "test.csv", "folder-id")

    assert result == "existing-id"
    svc.files.return_value.create.assert_not_called()


# ── list_files ────────────────────────────────────────────────────────────────

def test_list_files_returns_sorted_results():
    files = [
        {"id": "1", "name": "unusual-stocks-20260602-1600.csv", "createdTime": "2026-06-02T16:00:00Z"},
        {"id": "2", "name": "unusual-stocks-20260601-1600.csv", "createdTime": "2026-06-01T16:00:00Z"},
    ]
    svc = make_svc(list_result=files)
    client = DriveClient(svc, "root-id")
    result = client.list_files("unusual-stocks")
    assert result[0]["name"] == "unusual-stocks-20260602-1600.csv"


def test_list_files_queries_without_parent_constraint():
    """list_files must not filter by parent so it spans all date subfolders."""
    svc = make_svc(list_result=[])
    client = DriveClient(svc, "root-id")
    client.list_files("unusual-stocks")
    query = svc.files.return_value.list.call_args.kwargs["q"]
    assert "in parents" not in query


# ── download_for_date ─────────────────────────────────────────────────────────

def test_download_for_date_finds_matching_file():
    files = [
        {"id": "1", "name": "unusual-stocks-20260602-1600.csv", "createdTime": "2026-06-02T16:00:00Z"},
        {"id": "2", "name": "unusual-stocks-20260601-1600.csv", "createdTime": "2026-06-01T16:00:00Z"},
    ]
    svc = make_svc(list_result=files)
    # Mock download to return CSV content
    svc.files.return_value.get_media.return_value = MagicMock()
    client = DriveClient(svc, "root-id")

    with patch.object(client, "download", return_value="Symbol,Volume\nAAPL,100\n") as mock_dl:
        name, content = client.download_for_date("unusual-stocks", "2026-06-02")

    assert name == "unusual-stocks-20260602-1600.csv"
    mock_dl.assert_called_once_with("1", name="unusual-stocks-20260602-1600.csv")


def test_download_for_date_returns_none_when_not_found():
    svc = make_svc(list_result=[])
    client = DriveClient(svc, "root-id")
    name, content = client.download_for_date("unusual-stocks", "2026-06-02")
    assert name is None
    assert content is None
