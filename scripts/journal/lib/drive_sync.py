"""Google Drive as the journal's durable, private home.

WHY THIS EXISTS. Every artefact the journal produces is gitignored — raw pulls
carry account identifiers, the CSVs carry position sizes and P&L — so on a
machine that is thrown away after each run (a CI runner, a cloud session) the
journal writes its record onto a disk that ceases to exist, and prints the rest
into a build log that other people can read. This module gives that output one
private destination instead: a Drive folder named by JOURNAL_DRIVE_FOLDER_ID,
separate from GOOGLE_DRIVE_FOLDER_ID (the Barchart flow scrapes) for the same
reason TRADE_JOURNAL_SPREADSHEET_ID is a separate workbook — so the trade record
can be shared, or kept unshared, on its own.

Set no JOURNAL_DRIVE_FOLDER_ID and every function here is a no-op: a local run
behaves exactly as it did before this module existed.

WHAT LANDS THERE, and how it is grouped. One file per day per artefact would
reach four figures inside two years, so everything datewise is grouped BY MONTH —
into a folder as well as into a file, so the folder root holds a fixed handful of
things however many years accumulate behind it:

    YYYY-MM/
      reports-YYYY-MM.md  every daily report for that month, in date order
      cards-YYYY-MM.md    every deploy card for that month, likewise
      raw-YYYY-MM.jsonl   one broker pull per line, keyed on its filename
    _history/
      trades.csv          the three append-only archives, whole — one series
      open_book.csv       each, so they are NOT month-partitioned
      recommendations.csv
    journal-latest.html   the current page, overwritten each run

`_history/` is where the WRITERS' OWN RECORD lives, not a second copy of the
Sheets tabs: each writer reads its file to find what it has already recorded and
what `generation` a re-marked row gets. The OpenBook tab is REPLACED every run,
so open_book.csv is the only place that book's past marks exist at all.

The month folder is created on first write and never listed or scanned: every
read here asks for one exact name inside one known folder.

THE ROUND TRIP. The three CSVs are append-only AND generational: each writer
reads the file's own history to assign `generation` and to drop rows it has
already recorded. A fresh checkout has none of that history, so a cloud run left
to itself restarts every generation at 1 and re-appends rows it already wrote.
`pull_archives()` therefore runs BEFORE the writers and restores them; `push()`
runs after. The pair is what makes a cloud run behave like a local one.

DIVERGENCE IS REPORTED, NEVER RESOLVED BY GUESSING. Every file here is
append-only, which makes "has this copy fallen behind?" answerable exactly: one
copy's lines are a prefix of the other's. So a pull that finds the local file
BEHIND Drive replaces it (keeping a timestamped backup), a push that finds Drive
behind the local file overwrites it, and a genuine fork — neither a prefix of
the other, which means two machines appended different rows to the same base —
is never merged on a guess. The local file is left alone and pushed under a
`-conflict-<stamp>` name, so both copies survive for a person to reconcile.

FAILURE POLICY. A Drive failure is a warning, not a lost journal: the local
files and the Sheets tabs are already written by the time `push()` runs. The one
exception is `--quiet`, where Drive is the ONLY place the report goes — there
the caller treats a push failure as fatal, because a silent run whose upload
failed produced nothing at all.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from ..config import (DRIVE_FOLDER_ENV, DRIVE_STAGE_DIR, OPEN_BOOK_CSV,
                      RECOMMENDATIONS_CSV, TRADES_CSV)

log = logging.getLogger("journal.drive")


class DriveSyncError(RuntimeError):
    """Drive could not be reached, or its copy could not be reconciled."""


# The archives that round-trip. Name on Drive == name on disk: these files are
# the whole series, not a month of it, so there is nothing to group.
ARCHIVES = (TRADES_CSV, OPEN_BOOK_CSV, RECOMMENDATIONS_CSV)

PAGE_NAME = "journal-latest.html"

# The archives' own subfolder. Underscore-led so it sorts away from the month
# folders and reads as machinery rather than as something to open.
HISTORY_FOLDER = "_history"

_MIME = {
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".html": "text/html",
    ".jsonl": "application/x-ndjson",
    ".json": "application/json",
}


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------
def folder_id() -> str:
    return os.getenv(DRIVE_FOLDER_ENV, "").strip()


def enabled() -> bool:
    """True when a destination folder is configured. Everything here no-ops
    otherwise, so the module is safe to call unconditionally."""
    return bool(folder_id())


def client():
    """A DriveClient rooted at the JOURNAL folder — never the flow folder.

    Built here rather than via `get_drive_client()`, which reads
    GOOGLE_DRIVE_FOLDER_ID: pointing the journal at that folder would put
    account ids and live P&L in with the Barchart scrapes.
    """
    from lib.drive_client import get_drive_client

    fid = folder_id()
    if not fid:
        raise DriveSyncError(f"{DRIVE_FOLDER_ENV} not set")
    return get_drive_client(fid)


def month_of(date_str: str) -> str:
    """`2026-09-10` -> `2026-09`. The grouping key for every dated artefact."""
    return date_str[:7]


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _stage(name: str, text: str) -> Path:
    """Write what is about to be uploaded to `journal/drive/`, so the thing that
    went to Drive can be read back on disk afterwards. Drive uploads take a
    path, and a staged copy is worth more than a temp file."""
    DRIVE_STAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = DRIVE_STAGE_DIR / name
    path.write_text(text, encoding="utf-8")
    return path


def history_folder(cli, *, create: bool) -> str | None:
    """The `_history/` subfolder. `create=False` on the read path so a pull
    against a folder that has never been written to does not leave an empty
    directory behind as its only effect."""
    if create:
        return cli.get_or_create_date_folder(HISTORY_FOLDER)
    return cli.find_date_folder(HISTORY_FOLDER)


def month_folder(cli, key: str) -> str:
    """The `YYYY-MM` subfolder for `key`, created if it is not there yet.

    `get_or_create_date_folder` is named for the flow corpus's YYYY-MM-DD
    folders, but it is just "find or make a subfolder of the root by name" and
    a month is the same shape one level up.
    """
    return cli.get_or_create_date_folder(key)


def _download(cli, name: str, folder: str | None = None) -> str | None:
    folder = folder or cli.root
    fid = cli.file_exists(name, folder)
    if fid is None:
        return None
    return cli.download(fid, name)


def _upload(cli, path: Path, name: str, folder: str | None = None) -> str:
    return cli.upload(path, name, folder or cli.root,
                      mimetype=_MIME.get(path.suffix, "application/octet-stream"))


# --------------------------------------------------------------------------
# Append-only reconciliation
# --------------------------------------------------------------------------
def relation(local: str, remote: str) -> str:
    """How two versions of an append-only file stand to each other.

    `same` | `local_ahead` | `remote_ahead` | `diverged`. Compared line-wise
    rather than byte-wise so a missing final newline is not read as a fork.
    """
    a, b = local.splitlines(), remote.splitlines()
    if a == b:
        return "same"
    if a[:len(b)] == b:
        return "local_ahead"
    if b[:len(a)] == a:
        return "remote_ahead"
    return "diverged"


def push_append_only(cli, path: Path, name: str | None = None) -> str:
    """Upload an append-only file, refusing to overwrite work it does not
    contain. Returns the relation that was acted on."""
    name = name or path.name
    if not path.exists() or path.stat().st_size == 0:
        return "empty"
    folder = history_folder(cli, create=True)
    remote = _download(cli, name, folder)
    if remote is None:
        _upload(cli, path, name, folder)
        return "created"
    rel = relation(path.read_text(encoding="utf-8"), remote)
    if rel == "same":
        return "same"
    if rel == "local_ahead":
        _upload(cli, path, name, folder)
        return "local_ahead"
    if rel == "remote_ahead":
        # Nothing to send: Drive already holds everything this file does, plus
        # rows this machine never saw. `pull_archives()` is what fixes the
        # local copy, and it runs at the start of the next run.
        log.warning("%s on Drive is ahead of the local copy — not overwriting it", name)
        return "remote_ahead"
    conflict = f"{path.stem}-conflict-{_stamp()}{path.suffix}"
    _upload(cli, path, conflict, folder)
    log.error("%s has forked: Drive and this machine appended different rows to the "
              "same base. Drive's copy is untouched; this one is at %s. Reconcile "
              "them by hand.", name, conflict)
    return "diverged"


def pull_archives(cli=None) -> dict[str, str]:
    """Restore the append-only archives from Drive before the writers read them.

    Returns `{filename: action}` where action is one of `absent` (Drive has no
    copy), `restored` (there was no local file), `updated` (the local file was
    behind), `kept` (local is current or ahead) or `diverged`.
    """
    if not enabled():
        return {}
    cli = cli or client()
    folder = history_folder(cli, create=False)
    if folder is None:
        # Nothing has ever been pushed. Not an error — the first run's push
        # creates the folder — and NOT a reason to create it here.
        return {path.name: "absent" for path in ARCHIVES}
    out: dict[str, str] = {}
    for path in ARCHIVES:
        remote = _download(cli, path.name, folder)
        if remote is None:
            out[path.name] = "absent"
            continue
        if not path.exists() or path.stat().st_size == 0:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(remote, encoding="utf-8")
            out[path.name] = "restored"
            continue
        rel = relation(path.read_text(encoding="utf-8"), remote)
        if rel == "remote_ahead":
            # Keep the copy we are about to replace. It is append-only history
            # and a wrong call here would destroy rows nothing else holds.
            backup = _stage(f"{path.stem}-local-{_stamp()}{path.suffix}",
                            path.read_text(encoding="utf-8"))
            path.write_text(remote, encoding="utf-8")
            log.info("%s was behind Drive — restored (previous copy at %s)",
                     path.name, backup)
            out[path.name] = "updated"
        elif rel == "diverged":
            log.error("%s has forked from Drive's copy — leaving the local file "
                      "alone; the push will save it under a -conflict- name",
                      path.name)
            out[path.name] = "diverged"
        else:
            out[path.name] = "kept"
    return out


# --------------------------------------------------------------------------
# Monthly grouping — reports and deploy cards
# --------------------------------------------------------------------------
_OPEN = "<!-- journal:{kind} {key} -->"
_CLOSE = "<!-- /journal:{kind} {key} -->"
_BLOCK = re.compile(
    r"<!-- journal:(?P<kind>[a-z]+) (?P<key>[0-9]{4}-[0-9]{2}-[0-9]{2}) -->\n"
    r"(?P<body>.*?)\n?"
    r"<!-- /journal:(?P=kind) (?P=key) -->",
    re.DOTALL)


def parse_sections(text: str) -> dict[str, str]:
    """Split a grouped monthly file back into `{date: body}`.

    Raises if the file holds text OUTSIDE the marked blocks and its own title:
    that means something wrote to it that this module did not, and rewriting it
    would silently drop that content.
    """
    if not text.strip():
        return {}
    sections = {m["key"]: m["body"] for m in _BLOCK.finditer(text)}
    leftover = _BLOCK.sub("", text)
    leftover = re.sub(r"^# .*\n", "", leftover, count=1)
    if leftover.strip():
        raise DriveSyncError(
            "the grouped file holds text outside its marked sections — refusing "
            "to rewrite it")
    return sections


def render_sections(kind: str, key: str, sections: dict[str, str]) -> str:
    """`{date: body}` back to one file, in date order, with a title."""
    title = {"report": "Journal reports", "card": "Deploy cards"}.get(kind, kind)
    parts = [f"# {title} — {key}\n"]
    for date_str in sorted(sections):
        parts.append(_OPEN.format(kind=kind, key=date_str))
        parts.append(sections[date_str])
        parts.append(_CLOSE.format(kind=kind, key=date_str) + "\n")
    return "\n".join(parts)


def push_grouped(cli, kind: str, date_str: str, body: str) -> str:
    """Add (or replace) one day's section in that month's file.

    Replacing rather than appending is deliberate: re-running a date is normal —
    a corrected pull, a later Flex statement — and the second run's report is
    the true one, not a duplicate to read past.
    """
    key = month_of(date_str)
    folder = month_folder(cli, key)
    name = f"{kind}s-{key}.md"
    remote = _download(cli, name, folder) or ""
    try:
        sections = parse_sections(remote)
    except DriveSyncError:
        stray = f"{kind}s-{key}-unreadable-{_stamp()}.md"
        _upload(cli, _stage(stray, remote), stray, folder)
        log.error("%s could not be parsed — its content is preserved as %s and the "
                  "month is being rebuilt from this run", name, stray)
        sections = {}
    action = "replaced" if date_str in sections else "added"
    sections[date_str] = body.rstrip("\n")
    _upload(cli, _stage(name, render_sections(kind, key, sections)), name, folder)
    return action


# --------------------------------------------------------------------------
# Monthly grouping — broker pulls
# --------------------------------------------------------------------------
def push_raw(cli, raw_path: Path) -> str:
    """Append one broker pull to that month's JSONL, keyed on its filename.

    Pulls are immutable, so a filename already present is the same pull and is
    skipped — the line is never rewritten. `_file` is what a later reader
    extracts on:

        jq -r 'select(._file=="ibkr-2026-09-10-2215.json")' raw-2026-09.jsonl
    """
    if not raw_path or not Path(raw_path).exists():
        return "absent"
    raw_path = Path(raw_path)
    date_str = raw_path.stem.split("-")[1:4]
    if len(date_str) != 3:
        raise DriveSyncError(f"cannot read a date out of {raw_path.name}")
    key = '-'.join(date_str[:2])
    folder = month_folder(cli, key)
    name = f"raw-{key}.jsonl"
    remote = _download(cli, name, folder) or ""
    for line in remote.splitlines():
        if f'"_file": "{raw_path.name}"' in line or f'"_file":"{raw_path.name}"' in line:
            return "present"
    obj = json.loads(raw_path.read_text(encoding="utf-8"))
    obj["_file"] = raw_path.name
    text = remote if remote.endswith("\n") or not remote else remote + "\n"
    text += json.dumps(obj, sort_keys=True, default=str) + "\n"
    _upload(cli, _stage(name, text), name, folder)
    return "added"


# --------------------------------------------------------------------------
# The two entry points the pipeline calls
# --------------------------------------------------------------------------
def push(session: str, *, report_text: str | None = None,
         card_text: str | None = None, raw_path=None, page: Path | None = None,
         archives: bool = True, cli=None) -> dict[str, str]:
    """Send this run's output to Drive. Returns `{artefact: action}`."""
    if not enabled():
        return {}
    cli = cli or client()
    out: dict[str, str] = {}
    key = month_of(session)
    if report_text:
        out[f"{key}/reports-{key}.md"] = push_grouped(
            cli, "report", session, report_text)
    if card_text:
        out[f"{key}/cards-{key}.md"] = push_grouped(
            cli, "card", session, card_text)
    if raw_path:
        out["raw"] = push_raw(cli, Path(raw_path))
    if page and Path(page).exists():
        _upload(cli, Path(page), PAGE_NAME)
        out[PAGE_NAME] = "written"
    if archives:
        for path in ARCHIVES:
            out[f"{HISTORY_FOLDER}/{path.name}"] = push_append_only(cli, path)
    return out


def pull_page(dest: Path, cli=None) -> Path:
    """Download the latest journal page to `dest`. Raises if Drive has none."""
    cli = cli or client()
    text = _download(cli, PAGE_NAME)
    if text is None:
        raise DriveSyncError(
            f"no {PAGE_NAME} in the journal Drive folder — run the journal first")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest
