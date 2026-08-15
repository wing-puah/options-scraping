"""The recent end of the tuning log, read straight out of `current.md`.

Sections in that file are `## YYYY-MM-DD — <what happened>`, and the headings
are already written as findings rather than labels ("`be_after` grid RUN: does
NOT ship; give-back pattern is in the underlying"). So the map quotes the
heading and the first line of prose under it, and adds nothing — the log is the
source of truth, and a second, softer restatement of it is exactly the drift
this repo has been bitten by before.

Sections are returned newest first by their leading date. Entries whose heading
carries no date keep file order at the end; they are older material that was
merged in rather than appended.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT_MD = ROOT / "research" / "current.md"

_H2 = re.compile(r"^## +(.*?)\s*$")
_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
# Markdown noise that would otherwise land in a one-line gist verbatim.
# Underscores are NOT stripped: these headings are full of identifiers like
# `be_after` and `oi_confirm_pct`, and mangling one is worse than leaving a
# stray emphasis marker in.
_INLINE = re.compile(r"[*`]")


@dataclass
class LogEntry:
    date: str
    heading: str
    gist: str

    @property
    def title(self) -> str:
        """The heading with its leading date stripped, since the date is shown."""
        rest = self.heading[len(self.date):].lstrip(" —-") if self.date else self.heading
        return rest or self.heading


def _gist(lines: list[str], start: int, limit: int = 240) -> str:
    """First prose line under a heading — skipping blanks, sub-headings, tables."""
    buf: list[str] = []
    for line in lines[start:start + 25]:
        if line.startswith("#"):
            break
        text = line.strip()
        if not text:
            if buf:
                break
            continue
        if text.startswith(("|", "```", "---", "===", "- ", "* ", "> ")) or text[:1].isdigit():
            if buf:
                break
            continue
        buf.append(_INLINE.sub("", text))
        if len(" ".join(buf)) > limit:
            break
    gist = " ".join(buf).strip()
    return gist if len(gist) <= limit else gist[:limit - 1].rsplit(" ", 1)[0] + "…"


def read_log(path: Path = CURRENT_MD, limit: int = 6) -> list[LogEntry]:
    """The `limit` newest `## ` sections of the tuning log, newest first."""
    if not path.exists():
        return []
    lines = path.read_text(errors="replace").splitlines()
    entries: list[LogEntry] = []
    for i, line in enumerate(lines):
        m = _H2.match(line)
        if not m:
            continue
        heading = _INLINE.sub("", m.group(1))
        date_m = _DATE.match(heading)
        entries.append(LogEntry(
            date=date_m.group(1) if date_m else "",
            heading=heading,
            gist=_gist(lines, i + 1),
        ))
    entries.sort(key=lambda e: e.date or "0000-00-00", reverse=True)
    return entries[:limit]


def log_mtime(path: Path = CURRENT_MD) -> str:
    if not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
