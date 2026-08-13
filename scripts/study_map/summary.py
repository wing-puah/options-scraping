"""Read what a study's last run actually printed — quote it, never paraphrase it.

Every report under `backtests/study_output/` carries the runner's provenance
header and footer, which are strict enough to parse:

    ==============================================================================
    STUDY: <name>
    ==============================================================================
      run at    2026-08-13 15:51:31
      command   python -m scripts.backtest_study.<name>
      git       309c564 (main, working tree dirty)
      python    3.11.2
      inputs:
       1,926 rows  2026-08-11 15:38  backtests/to_evaluate/...
    ==============================================================================
    <body>
    ==============================================================================
    exit code 3 after 1.5s
    ==============================================================================

The body is not strict at all — some studies close with a banner VERDICT block,
some end on a table, some abort on a missing export. So the excerpt this module
returns is always tagged with HOW it was found (`excerpt_kind`), in descending
order of how much the report is committing to it:

    verdict   a banner section titled VERDICT / CONCLUSION / DECISION / …
    failure   the abort or traceback line from a run that exited non-zero
    matched   lines that state a pre-registered criterion (MET / NOT MET / …)
    tail      no marker found — literally the last lines of the report

Nothing here summarises. A `tail` excerpt is labelled as the tail on the page
precisely so it cannot be read as a conclusion the study drew.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "backtests" / "study_output"

MAX_EXCERPT_LINES = 12
MAX_LINE_CHARS = 150

_RULE = re.compile(r"^={10,}$")
_FOOTER = re.compile(r"^exit code (-?\d+) after ([\d.]+)s\s*$")
_FIELD = re.compile(r"^ {2}(run at|command|git|python)\s+(.*)$")
_INPUT = re.compile(r"^\s*([\d,]+) rows\s+(\S+ \S+)\s+(.*)$")
_MISSING_INPUT = re.compile(r"^\s*MISSING\s+(.*)$")

# A banner title is a line sandwiched between two rules. These are the titles
# under which a study is stating its answer rather than showing its work.
_CONCLUSION_TITLE = re.compile(
    r"\b(VERDICT|CONCLUSION|DECISION|BOTTOM LINE|WHAT SHIPS|FINAL READ)\b", re.I)

# Lines that carry a pre-registered criterion's outcome. Deliberately narrow:
# a false positive here puts an arbitrary table row on the page under a heading
# that implies the study meant it.
_CRITERION = re.compile(
    r"(->\s*(MET|not met|NOT MET)\b"
    r"|\bNOT EVALUABLE\b"
    r"|\bNULL RESULT\b"
    r"|\bPOWER[- ]STOP"
    r"|^\s*VERDICT\b.*:"
    r"|^\s*(B\d|D\d|G\d|H\d|P\d|A\d|R\d)\b.*\b(MET|NOT|YES|NO|REJECTED|ADOPTED)\b)")

# Structural furniture that carries no information in an excerpt: the banner
# rules themselves, and the runner's own end marker. Titled separators like
# `--- calendar (n=169) ---` are NOT furniture — they say what a table is.
_FURNITURE = re.compile(r"^\s*([=-]{6,}|END OF REPORT)\s*$")

_FAILURE = re.compile(
    r"^\s*(\*\*\*.*\*\*\*"          # *** HARNESS VALIDATION FAILED — stopping. ***
    r"|ABORT\b.*"                    # ABORT: expected v3 then v4, got v3 then v3.
    r"|[A-Za-z_.]*(Error|Exception)\b.*)$")  # FileNotFoundError: [Errno 2] …


@dataclass
class RunSummary:
    """One study's last run, as the report itself reported it."""

    name: str
    report: Path | None = None
    ran: bool = False
    run_at: str = ""
    command: str = ""
    git: str = ""
    python: str = ""
    inputs: list[tuple[str, str, str]] = field(default_factory=list)  # rows, mtime, path
    missing_inputs: list[str] = field(default_factory=list)
    exit_code: int | None = None
    elapsed: str = ""
    excerpt: list[str] = field(default_factory=list)
    excerpt_kind: str = ""
    digest_title: str = ""
    digest_path: Path | None = None
    charts_path: Path | None = None
    regime_path: Path | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def status(self) -> str:
        if not self.ran:
            return "never run"
        if self.exit_code is None:
            return "incomplete"
        return "ok" if self.exit_code == 0 else f"exit {self.exit_code}"

    @property
    def git_sha(self) -> str:
        """Just the short sha, without the branch/dirty parenthetical."""
        return self.git.split()[0] if self.git else ""

    @property
    def dirty(self) -> bool:
        return "dirty" in self.git


def _clip(line: str) -> str:
    line = line.rstrip()
    return line if len(line) <= MAX_LINE_CHARS else line[:MAX_LINE_CHARS - 1] + "…"


def _split(lines: list[str]) -> tuple[list[str], list[str], int | None, str]:
    """`(header_lines, body_lines, exit_code, elapsed)`.

    Falls back to treating the whole file as the body: a report written by
    something other than the runner is still worth quoting the tail of.
    """
    rules = [i for i, ln in enumerate(lines) if _RULE.match(ln.strip())]

    exit_code: int | None = None
    elapsed = ""
    end = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        m = _FOOTER.match(lines[i].strip())
        if m:
            exit_code, elapsed = int(m.group(1)), m.group(2) + "s"
            end = i - 1 if i and _RULE.match(lines[i - 1].strip()) else i
            break

    start = 0
    header: list[str] = []
    if len(rules) >= 3 and rules[0] == 0 and lines[1].startswith("STUDY:"):
        header = lines[3:rules[2]]
        start = rules[2] + 1

    return header, lines[start:end], exit_code, elapsed


def _parse_header(header: list[str], out: RunSummary) -> None:
    for line in header:
        m = _FIELD.match(line)
        if m:
            setattr(out, m.group(1).replace(" ", "_"), m.group(2).strip())
            continue
        m = _INPUT.match(line)
        if m:
            out.inputs.append((m.group(1), m.group(2), m.group(3).strip()))
            continue
        m = _MISSING_INPUT.match(line)
        if m:
            out.missing_inputs.append(m.group(1).strip())


def _banner_sections(body: list[str]) -> list[tuple[str, int]]:
    """`[(title, first_body_line_index)]` for every `===`-sandwiched heading."""
    out = []
    for i in range(1, len(body) - 1):
        if (_RULE.match(body[i - 1].strip()) and _RULE.match(body[i + 1].strip())
                and body[i].strip() and not _RULE.match(body[i].strip())):
            out.append((body[i].strip(), i + 2))
    return out


def _section_body(body: list[str], start: int) -> list[str]:
    """Lines from `start` up to the next rule (which opens the next section)."""
    out = []
    for line in body[start:]:
        if _RULE.match(line.strip()):
            break
        out.append(line)
    return out


def _nonempty_tail(lines: list[str], n: int) -> list[str]:
    kept = [ln for ln in lines if ln.strip() and not _FURNITURE.match(ln)]
    return kept[-n:]


def extract(body: list[str], exit_code: int | None) -> tuple[list[str], str]:
    """`(excerpt_lines, kind)` — see the module docstring for the four kinds."""
    sections = _banner_sections(body)
    for title, start in reversed(sections):
        if _CONCLUSION_TITLE.search(title):
            chunk = [title] + _section_body(body, start)
            chunk = [ln for ln in chunk if ln.strip()][:MAX_EXCERPT_LINES]
            if len(chunk) > 1:
                return [_clip(ln) for ln in chunk], "verdict"

    if exit_code not in (0, None):
        for i in range(len(body) - 1, -1, -1):
            if _FAILURE.match(body[i]):
                chunk = [body[i]]
                # An ABORT is usually a paragraph; a traceback line is not.
                for follow in body[i + 1:i + 5]:
                    if not follow.strip():
                        break
                    chunk.append(follow)
                return [_clip(ln) for ln in chunk], "failure"

    matched = [ln for ln in body if _CRITERION.search(ln)]
    if matched:
        return [_clip(ln) for ln in matched[-6:]], "matched"

    tail = _nonempty_tail(body, 8)
    return [_clip(ln) for ln in tail], "tail"


def _digest_title(path: Path) -> str:
    """The digest's own H1, or "" — never a line we composed."""
    for line in path.read_text(errors="replace").splitlines()[:20]:
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def summarize(name: str, out_dir: Path = OUT_DIR) -> RunSummary:
    """Parse `<name>-latest.txt`, plus any digest / charts pages beside it."""
    out = RunSummary(name=name)

    digest = out_dir / f"{name}-digest-latest.md"
    if digest.exists():
        out.digest_path, out.digest_title = digest, _digest_title(digest)
    charts = out_dir / f"{name}-charts-latest.html"
    if charts.exists():
        out.charts_path = charts
    regime = out_dir / f"{name}-regime-latest.html"
    if regime.exists():
        out.regime_path = regime

    report = out_dir / f"{name}-latest.txt"
    if not report.exists():
        return out

    lines = report.read_text(errors="replace").splitlines()
    header, body, out.exit_code, out.elapsed = _split(lines)
    out.report, out.ran = report, True
    _parse_header(header, out)
    if not out.run_at:
        out.run_at = datetime.fromtimestamp(
            report.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    out.excerpt, out.excerpt_kind = extract(body, out.exit_code)
    return out


def summarize_all(names: list[str], out_dir: Path = OUT_DIR) -> dict[str, RunSummary]:
    return {name: summarize(name, out_dir) for name in names}
