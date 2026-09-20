"""Readability check for the repo's hand-written research prose.

`research/writing-guide.md` says what a readable entry looks like. This script
measures the parts of it a machine can measure, so prose that has drifted into
300-word table cells is caught when it is written rather than six weeks later.

It cannot rewrite anything. It names the block, the measurement and the limit,
and the writer fixes it. Three ways to run it:

    python3 scripts/check_prose.py research/current.md    # whole files
    python3 scripts/check_prose.py --since HEAD            # only blocks touched since a git ref
    python3 scripts/check_prose.py --hook                  # Claude Code PostToolUse hook (JSON on stdin)

`--since` and `--hook` report a problem only when its block overlaps the lines
that changed. The existing files predate the check and fail it wholesale, so
the rule is "leave every block you touch readable", not "fix the file first".

Scope is `research/**/*.md` and `docs/**/*.md`, minus the three trees the
writing guide says not to restyle: `research/archive/` (history),
`research/study-results/` (machine-written) and `research/pre-registrations/`
(held verbatim).

Runs on the system python (3.9, stdlib only) because the hook calls it outside
the venv.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCOPE_GLOBS = ["research/**/*.md", "docs/**/*.md"]
_EXCLUDED_PREFIXES = ("research/archive/", "research/study-results/", "research/pre-registrations/")

# Limits. Each one is a rule in research/writing-guide.md made countable.
MAX_CELL_WORDS = 40  # "Numbers live in tables" -- a cell is a value, not a paragraph
MAX_SENTENCE_WORDS = 45  # "One main claim per sentence"
MAX_PARAGRAPH_WORDS = 110  # "make the rigour visible through structure rather than dense prose"
MAX_SENTENCE_FIGURES = 3  # "A sentence carrying more than two figures becomes a table row" (+1 slack)
MAX_HEADING_CHARS = 100  # "Keep the heading to one line"
MAX_SHOUTED_WORDS = 1  # "One emphasis per point ... Capitals only to quote a token"
MAX_REPORTED = 12

# Ordinary words written in capitals for emphasis. Tickers, acronyms and the
# verdict tokens a study prints are deliberately NOT here: the guide allows those.
_SHOUTED = {
    "NOT", "NEVER", "ONLY", "ALL", "ALWAYS", "MUST", "BEFORE", "AFTER", "EVERY", "WHOLE", "SAME",
    "ONE", "NO", "IS", "ARE", "WAS", "BOTH", "ANY", "NOTHING", "STILL", "ALREADY", "AND", "OR",
}  # fmt: skip
# "use them only when ordinary language cannot draw the distinction" -- advisory, never blocks.
_VAGUE = ("pre-empts", "retro-fitted", "disposition", "posture")

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
_TABLE_RULE_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_HTML_LINE_RE = re.compile(r"^\s*<[^>]+>\s*$")
_CODE_SPAN_RE = re.compile(r"`[^`]*`")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b|\b\d{2}-\d{2}\b")
_SECTION_REF_RE = re.compile(r"§\s?\d+(?:\.\d+)*")
_FIGURE_RE = re.compile(r"(?<![\w.#/-])[+−-]?\$?\d[\d,]*(?:\.\d+)?%?(?![\w-])")
_ABBREV_RE = re.compile(r"\b(e\.g|i\.e|vs|cf|etc|approx)\.", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])[\"')\]*_]*\s+(?=[\"'(\[*_`]*[A-Z0-9])")
_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
_WORD_RE = re.compile(r"[A-Za-z0-9À-ɏ][\w'’./%+−-]*")


@dataclass
class Block:
    kind: str  # "paragraph" | "cell" | "heading"
    start: int  # 1-indexed, inclusive
    end: int
    text: str


@dataclass
class Problem:
    path: Path
    line: int
    end: int
    rule: str
    detail: str
    warning: bool = False

    def format(self, root: Path) -> str:
        try:
            rel = self.path.relative_to(root)
        except ValueError:
            rel = self.path
        kind = "advisory" if self.warning else self.rule
        return f"{rel}:{self.line}: {kind} -- {self.detail}"


def _plain(text: str) -> str:
    """Markdown stripped to what a reader reads: link text kept, targets and code spans collapsed."""
    text = _LINK_RE.sub(lambda m: m.group(1) or "link", text)
    text = _CODE_SPAN_RE.sub("code", text)
    return re.sub(r"[*_~]{1,3}|<[^>]+>", "", text)


def _words(text: str) -> int:
    return len(_WORD_RE.findall(_plain(text)))


def _sentences(text: str) -> list[str]:
    plain = _ABBREV_RE.sub(lambda m: m.group(1).replace(".", "") + ",", _plain(text))
    return [s for s in _SENTENCE_SPLIT_RE.split(plain) if s.strip()]


def _figures(sentence: str) -> int:
    sentence = _SECTION_REF_RE.sub("", _DATE_RE.sub("", sentence))
    return len(_FIGURE_RE.findall(sentence))


def blocks(text: str) -> list[Block]:
    """Split markdown into the units a reader takes in at once. Fenced code is skipped."""
    out: list[Block] = []
    para: list[str] = []
    para_start = 0
    in_fence = False

    def flush(end: int) -> None:
        nonlocal para
        if para:
            out.append(Block("paragraph", para_start, end, " ".join(s.strip() for s in para)))
            para = []

    for n, line in enumerate(text.splitlines(), 1):
        if _FENCE_RE.match(line):
            flush(n - 1)
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = line.strip()
        heading = _HEADING_RE.match(line)
        if not stripped or _HTML_LINE_RE.match(line):
            flush(n - 1)
        elif heading:
            flush(n - 1)
            out.append(Block("heading", n, n, heading.group(1)))
        elif stripped.startswith("|"):
            flush(n - 1)
            if not _TABLE_RULE_RE.match(line):
                for cell in _CELL_SPLIT_RE.split(stripped.strip("|")):
                    out.append(Block("cell", n, n, cell.strip()))
        else:
            if _LIST_ITEM_RE.match(line):
                flush(n - 1)
                line = _LIST_ITEM_RE.sub("", line, count=1)
            if not para:
                para_start = n
            para.append(line.lstrip("> "))
    flush(len(text.splitlines()))
    return out


def check_text(text: str, path: Path) -> list[Problem]:
    problems: list[Problem] = []

    def add(block: Block, rule: str, detail: str, warning: bool = False) -> None:
        problems.append(Problem(path, block.start, block.end, rule, detail, warning))

    for block in blocks(text):
        if block.kind == "heading":
            if len(block.text) > MAX_HEADING_CHARS:
                add(block, "heading-too-long", f"{len(block.text)} chars (limit {MAX_HEADING_CHARS}): "
                    "date, subject, verdict in a few words; qualifiers go in the first line under it")  # fmt: skip
            continue
        n_words = _words(block.text)
        if block.kind == "cell" and n_words > MAX_CELL_WORDS:
            add(block, "cell-too-long", f"table cell of {n_words} words (limit {MAX_CELL_WORDS}): "
                "keep the verdict and the number in the cell; the story goes in a paragraph or linked entry")
        if block.kind == "paragraph" and n_words > MAX_PARAGRAPH_WORDS:
            add(block, "paragraph-too-long", f"{n_words} words (limit {MAX_PARAGRAPH_WORDS}): "
                "split by rule / current behaviour / implementation, or cut what the archive already says")  # fmt: skip
        for sentence in _sentences(block.text):
            s_words = len(_WORD_RE.findall(sentence))
            opening = " ".join(sentence.split()[:6])
            if s_words > MAX_SENTENCE_WORDS:
                add(block, "sentence-too-long", f'{s_words} words (limit {MAX_SENTENCE_WORDS}), starts "{opening}...": '
                    "one main claim per sentence")  # fmt: skip
            if block.kind == "paragraph" and _figures(sentence) > MAX_SENTENCE_FIGURES:
                add(block, "too-many-figures", f'{_figures(sentence)} figures in one sentence, starts "{opening}...": '
                    "numbers live in tables; the sentence says what they mean")  # fmt: skip
        shouted = [w for w in re.findall(r"\b[A-Z]{2,}\b", _plain(block.text)) if w in _SHOUTED]
        if len(shouted) > MAX_SHOUTED_WORDS:
            add(block, "shouting", f"{len(shouted)} ordinary words in capitals ({', '.join(sorted(set(shouted)))}): "
                "one emphasis per point; capitals only quote a token a study printed")  # fmt: skip
        vague = [w for w in _VAGUE if re.search(rf"\b{re.escape(w)}\b", block.text, re.IGNORECASE)]
        if vague:
            add(block, "vague-word", f"{', '.join(vague)}: use only if plain words cannot draw the distinction", True)
    return problems


def in_scope(path: Path, root: Path = ROOT) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    if path.suffix != ".md" or rel.startswith(_EXCLUDED_PREFIXES):
        return False
    return rel.startswith(("research/", "docs/"))


def _overlaps(problem: Problem, ranges: list[tuple[int, int]]) -> bool:
    return any(problem.line <= hi and problem.end >= lo for lo, hi in ranges)


def check_file(path: Path, ranges: list[tuple[int, int]] | None = None) -> list[Problem]:
    problems = check_text(path.read_text(encoding="utf-8"), path)
    return problems if ranges is None else [p for p in problems if _overlaps(p, ranges)]


def _changed_ranges(ref: str, root: Path) -> dict[Path, list[tuple[int, int]]]:
    """Line ranges added or modified since `ref`, per file, from a zero-context diff."""
    diff = subprocess.run(
        ["git", "diff", "-U0", "--no-color", ref, "--", "research", "docs"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "research", "docs"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.split("\n")  # fmt: skip
    out: dict[Path, list[tuple[int, int]]] = {root / f: [(1, 10**9)] for f in untracked if f}
    current: Path | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = None if line.endswith("/dev/null") else root / line[6:]
        elif line.startswith("@@") and current is not None:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            start, count = int(m.group(1)), int(m.group(2) or 1)
            if count:
                out.setdefault(current, []).append((start, start + count - 1))
    return out


def _hook_ranges(path: Path, tool_input: dict) -> list[tuple[int, int]] | None:
    """Where the just-written text sits in the file. None means the whole file (a Write)."""
    new = tool_input.get("new_string")
    if not new:
        return None
    text = path.read_text(encoding="utf-8")
    ranges = []
    at = text.find(new)
    while at != -1:
        start = text.count("\n", 0, at) + 1
        ranges.append((start, start + new.count("\n")))
        at = text.find(new, at + len(new)) if tool_input.get("replace_all") else -1
    return ranges or None


def _report(problems: list[Problem], root: Path, stream) -> None:
    for p in problems[:MAX_REPORTED]:
        print(p.format(root), file=stream)
    if len(problems) > MAX_REPORTED:
        print(f"... and {len(problems) - MAX_REPORTED} more", file=stream)


def run_hook(stdin_text: str, root: Path = ROOT) -> int:
    """PostToolUse entry point. Exit 2 puts stderr in front of the model; anything else is silent."""
    try:
        tool_input = json.loads(stdin_text).get("tool_input", {})
        path = Path(tool_input.get("file_path", ""))
        if not path.is_file() or not in_scope(path, root):
            return 0
        problems = [p for p in check_file(path, _hook_ranges(path, tool_input)) if not p.warning]
    except Exception:  # a broken lint must never fail an edit
        return 0
    if not problems:
        return 0
    print(f"check_prose: the text just written breaks research/writing-guide.md in {len(problems)} place(s). "
          "Rewrite those blocks now -- shorter sentences, numbers into a table, the story out of the table "
          "cell -- keeping every fact, date and figure. Do not answer by deleting content.", file=sys.stderr)
    _report(problems, root, sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="markdown files to check instead of the default scope")
    parser.add_argument("--since", metavar="REF", help="report only blocks touched since this git ref (e.g. HEAD)")
    parser.add_argument("--hook", action="store_true", help="run as a Claude Code PostToolUse hook, JSON on stdin")
    parser.add_argument("--quiet", action="store_true", help="print only the summary line")
    args = parser.parse_args(argv)
    if args.hook:
        return run_hook(sys.stdin.read())

    problems: list[Problem] = []
    if args.since:
        for path, ranges in sorted(_changed_ranges(args.since, ROOT).items()):
            if path.is_file() and in_scope(path):
                problems += check_file(path, ranges)
    else:
        files = [Path(p).resolve() for p in args.paths] or sorted(
            f for g in _SCOPE_GLOBS for f in ROOT.glob(g) if in_scope(f)
        )
        for path in files:
            problems += check_file(path)
    errors = [p for p in problems if not p.warning]
    if not args.quiet:
        _report(errors, ROOT, sys.stdout)
        _report([p for p in problems if p.warning], ROOT, sys.stdout)
    print(f"check_prose: {len(errors)} problem(s), {len(problems) - len(errors)} advisory")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
