"""The journal's Drive mirror: monthly grouping, and the append-only round trip.

What is actually at stake here is not "did the upload happen" but the two ways
this mirror could destroy history: rewriting a monthly file it did not fully
understand, and overwriting a Drive copy that holds rows this machine never saw.
Both are asserted below.
"""

from __future__ import annotations

import json

import pytest

from scripts.journal.lib import drive_sync


class FakeDrive:
    """Enough of DriveClient for the sync: {name: text}, plus each file's parent.

    Names are unique across the fake, so `files` stays keyed on name alone and
    `parent` records where each one was put — which is what the month-folder
    assertions read.
    """

    def __init__(self, files=None, parents=None):
        self.files = dict(files or {})
        self.parent = dict(parents or {})
        self.root = "FOLDER"
        self.folders = {}
        self.uploads = []

    def get_or_create_date_folder(self, name):
        return self.folders.setdefault(name, f"folder:{name}")

    def find_date_folder(self, name):
        return self.folders.get(name)

    def _where(self, name):
        return self.parent.get(name, self.root)

    def file_exists(self, name, folder_id):
        if name in self.files and self._where(name) == folder_id:
            return f"id:{name}"
        return None

    def download(self, file_id, name=None):
        return self.files[file_id.removeprefix("id:")]

    def upload(self, local_path, name, folder_id, mimetype="text/csv"):
        self.files[name] = local_path.read_text(encoding="utf-8")
        self.parent[name] = folder_id
        self.uploads.append((name, mimetype))
        return f"id:{name}"


def history_drive(files=None):
    """A fake whose `files` already sit in `_history/`, where the archives live."""
    cli = FakeDrive()
    fid = cli.get_or_create_date_folder(drive_sync.HISTORY_FOLDER)
    for name, text in (files or {}).items():
        cli.files[name] = text
        cli.parent[name] = fid
    return cli


@pytest.fixture
def staged(tmp_path, monkeypatch):
    monkeypatch.setattr(drive_sync, "DRIVE_STAGE_DIR", tmp_path / "drive")
    return tmp_path


# --------------------------------------------------------------------------
# relation()
# --------------------------------------------------------------------------
@pytest.mark.parametrize("local,remote,expected", [
    ("a\nb\n", "a\nb\n", "same"),
    ("a\nb\nc\n", "a\nb\n", "local_ahead"),
    ("a\nb\n", "a\nb\nc\n", "remote_ahead"),
    ("a\nb\nx\n", "a\nb\ny\n", "diverged"),
    # A missing final newline is a formatting difference, not a fork.
    ("a\nb", "a\nb\n", "same"),
])
def test_relation(local, remote, expected):
    assert drive_sync.relation(local, remote) == expected


# --------------------------------------------------------------------------
# Monthly grouping
# --------------------------------------------------------------------------
def test_sections_round_trip():
    text = drive_sync.render_sections(
        "report", "2026-09", {"2026-09-02": "second", "2026-09-01": "first"})
    # Date order, not insertion order.
    assert text.index("first") < text.index("second")
    assert drive_sync.parse_sections(text) == {
        "2026-09-01": "first", "2026-09-02": "second"}


def test_parse_refuses_a_file_it_did_not_write():
    text = drive_sync.render_sections("report", "2026-09", {"2026-09-01": "first"})
    with pytest.raises(drive_sync.DriveSyncError):
        drive_sync.parse_sections(text + "\nhand-written note\n")


def test_push_grouped_adds_then_replaces(staged):
    cli = FakeDrive()
    assert drive_sync.push_grouped(cli, "report", "2026-09-01", "one") == "added"
    assert drive_sync.push_grouped(cli, "report", "2026-09-02", "two") == "added"
    # A re-run of a date REPLACES that day's section rather than duplicating it.
    assert drive_sync.push_grouped(cli, "report", "2026-09-01", "one-corrected") == "replaced"
    sections = drive_sync.parse_sections(cli.files["reports-2026-09.md"])
    assert sections == {"2026-09-01": "one-corrected", "2026-09-02": "two"}
    assert ("reports-2026-09.md", "text/markdown") in cli.uploads
    # Into that month's folder, so the folder root does not grow three files a
    # month for as long as the journal runs.
    assert cli.parent["reports-2026-09.md"] == "folder:2026-09"


def test_push_grouped_preserves_a_file_it_cannot_parse(staged):
    cli = FakeDrive({"reports-2026-09.md": "something else entirely\n"},
                    {"reports-2026-09.md": "folder:2026-09"})
    drive_sync.push_grouped(cli, "report", "2026-09-01", "one")
    preserved = [n for n in cli.files if "unreadable" in n]
    assert preserved, "the unparseable month must be kept, not overwritten"
    assert cli.files[preserved[0]] == "something else entirely\n"
    assert drive_sync.parse_sections(cli.files["reports-2026-09.md"]) == {
        "2026-09-01": "one"}


# --------------------------------------------------------------------------
# Append-only push
# --------------------------------------------------------------------------
def _csv(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_push_append_only_creates_and_extends(staged, tmp_path):
    cli = FakeDrive()
    path = _csv(tmp_path, "trades.csv", "h\na\n")
    assert drive_sync.push_append_only(cli, path) == "created"
    assert drive_sync.push_append_only(cli, path) == "same"
    path.write_text("h\na\nb\n", encoding="utf-8")
    assert drive_sync.push_append_only(cli, path) == "local_ahead"
    assert cli.files["trades.csv"] == "h\na\nb\n"
    # NOT month-partitioned: one continuous series, so it lives in _history/
    # where the next run — of any month — looks for it.
    assert cli.parent["trades.csv"] == "folder:_history"


def test_push_never_overwrites_a_drive_copy_that_is_ahead(staged, tmp_path):
    cli = history_drive({"trades.csv": "h\na\nb\n"})
    path = _csv(tmp_path, "trades.csv", "h\na\n")
    assert drive_sync.push_append_only(cli, path) == "remote_ahead"
    assert cli.files["trades.csv"] == "h\na\nb\n"


def test_a_fork_is_saved_beside_the_original(staged, tmp_path):
    cli = history_drive({"trades.csv": "h\na\nfrom-cloud\n"})
    path = _csv(tmp_path, "trades.csv", "h\na\nfrom-laptop\n")
    assert drive_sync.push_append_only(cli, path) == "diverged"
    assert cli.files["trades.csv"] == "h\na\nfrom-cloud\n", "Drive's copy is untouched"
    conflict = [n for n in cli.files if "conflict" in n]
    assert conflict and cli.files[conflict[0]] == "h\na\nfrom-laptop\n"


# --------------------------------------------------------------------------
# The pull half
# --------------------------------------------------------------------------
def test_pull_restores_a_missing_archive(staged, tmp_path, monkeypatch):
    path = tmp_path / "trades.csv"
    monkeypatch.setattr(drive_sync, "ARCHIVES", (path,))
    monkeypatch.setenv("JOURNAL_DRIVE_FOLDER_ID", "FOLDER")
    cli = history_drive({"trades.csv": "h\na\n"})
    assert drive_sync.pull_archives(cli) == {"trades.csv": "restored"}
    assert path.read_text() == "h\na\n"


def test_pull_updates_a_behind_archive_and_keeps_the_old_copy(staged, tmp_path, monkeypatch):
    path = _csv(tmp_path, "trades.csv", "h\na\n")
    monkeypatch.setattr(drive_sync, "ARCHIVES", (path,))
    monkeypatch.setenv("JOURNAL_DRIVE_FOLDER_ID", "FOLDER")
    cli = history_drive({"trades.csv": "h\na\nb\n"})
    assert drive_sync.pull_archives(cli) == {"trades.csv": "updated"}
    assert path.read_text() == "h\na\nb\n"
    backups = list((staged / "drive").glob("trades-local-*.csv"))
    assert backups and backups[0].read_text() == "h\na\n"


def test_pull_leaves_a_local_copy_that_is_ahead_or_forked(staged, tmp_path, monkeypatch):
    path = _csv(tmp_path, "trades.csv", "h\na\nlocal\n")
    monkeypatch.setattr(drive_sync, "ARCHIVES", (path,))
    monkeypatch.setenv("JOURNAL_DRIVE_FOLDER_ID", "FOLDER")
    cli = history_drive({"trades.csv": "h\na\ncloud\n"})
    assert drive_sync.pull_archives(cli) == {"trades.csv": "diverged"}
    assert path.read_text() == "h\na\nlocal\n"


def test_pull_is_a_no_op_without_a_folder(monkeypatch):
    monkeypatch.delenv("JOURNAL_DRIVE_FOLDER_ID", raising=False)
    assert drive_sync.enabled() is False
    assert drive_sync.pull_archives() == {}
    assert drive_sync.push("2026-09-10", report_text="x") == {}


# --------------------------------------------------------------------------
# Broker pulls
# --------------------------------------------------------------------------
def test_push_raw_appends_once_per_pull(staged, tmp_path):
    cli = FakeDrive()
    raw = tmp_path / "ibkr-2026-09-10-2215.json"
    raw.write_text(json.dumps({"trade_date": "2026-09-10"}), encoding="utf-8")
    assert drive_sync.push_raw(cli, raw) == "added"
    # Immutable evidence: the same pull is never written twice.
    assert drive_sync.push_raw(cli, raw) == "present"
    assert cli.parent["raw-2026-09.jsonl"] == "folder:2026-09"
    lines = cli.files["raw-2026-09.jsonl"].splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["_file"] == raw.name

    other = tmp_path / "ibkr-2026-09-11-2215.json"
    other.write_text(json.dumps({"trade_date": "2026-09-11"}), encoding="utf-8")
    drive_sync.push_raw(cli, other)
    assert len(cli.files["raw-2026-09.jsonl"].splitlines()) == 2


def test_pull_page(tmp_path):
    cli = FakeDrive({drive_sync.PAGE_NAME: "<html></html>"})
    dest = drive_sync.pull_page(tmp_path / "site" / "journal-latest.html", cli)
    assert dest.read_text() == "<html></html>"
    with pytest.raises(drive_sync.DriveSyncError):
        drive_sync.pull_page(tmp_path / "x.html", FakeDrive())


# --------------------------------------------------------------------------
# The CLI's half of the contract
# --------------------------------------------------------------------------
class _Args:
    """Just the flags `_drive_push` / `_drive_pull` read."""

    def __init__(self, **kw):
        self.dry_run = kw.get("dry_run", False)
        self.no_drive = kw.get("no_drive", False)
        self.quiet = kw.get("quiet", False)


def test_quiet_without_a_folder_refuses_before_any_work(monkeypatch):
    from scripts.journal import __main__ as journal_main

    monkeypatch.delenv("JOURNAL_DRIVE_FOLDER_ID", raising=False)
    # No broker call, no Sheets read: the refusal happens on the flags alone.
    assert journal_main.main(["--quiet"]) == journal_main.EXIT_USAGE


def test_a_failed_push_is_fatal_only_when_quiet(monkeypatch):
    from scripts.journal import __main__ as journal_main

    monkeypatch.setenv("JOURNAL_DRIVE_FOLDER_ID", "FOLDER")

    def boom(*a, **kw):
        raise RuntimeError("drive is down")

    monkeypatch.setattr(journal_main.drive_sync, "push", boom)
    # An ordinary run still has the report on screen and in journal/.
    assert journal_main._drive_push(_Args(), "2026-09-10", report_text="x") == 0
    # A quiet one does not: Drive was the only copy.
    assert journal_main._drive_push(
        _Args(quiet=True), "2026-09-10", report_text="x") == journal_main.EXIT_DRIVE


def test_the_mirror_is_skipped_on_a_dry_run_and_on_no_drive(monkeypatch):
    from scripts.journal import __main__ as journal_main

    monkeypatch.setenv("JOURNAL_DRIVE_FOLDER_ID", "FOLDER")
    called = []
    monkeypatch.setattr(journal_main.drive_sync, "push",
                        lambda *a, **kw: called.append(1) or {})
    assert journal_main._drive_push(_Args(dry_run=True), "2026-09-10") == 0
    assert journal_main._drive_push(_Args(no_drive=True), "2026-09-10") == 0
    assert not called


def test_pull_does_not_create_the_history_folder_just_to_look(tmp_path, monkeypatch):
    """A read against a folder nothing has been pushed to leaves no trace."""
    path = tmp_path / "trades.csv"
    monkeypatch.setattr(drive_sync, "ARCHIVES", (path,))
    monkeypatch.setenv("JOURNAL_DRIVE_FOLDER_ID", "FOLDER")
    cli = FakeDrive()
    assert drive_sync.pull_archives(cli) == {"trades.csv": "absent"}
    assert cli.folders == {}
    assert not cli.uploads
