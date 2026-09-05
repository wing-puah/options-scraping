"""Cross-link checker for the repo's hand-written docs.

Scans README.md, CLAUDE.md, GEMINI.md, docs/**/*.md and research/**/*.md for
markdown links -- inline `[text](target)` and reference-style `[text]: target`
-- and verifies each relative target resolves to a real file/directory, and
that any `#anchor` on it matches something inside the target file.

A "slug" is GitHub's own anchor id for a heading: lowercase the heading text,
strip markdown emphasis/code/link syntax, drop anything that is not a
letter, digit, space, hyphen or underscore, then turn spaces into hyphens
(see `slugify()`). We recompute it here because there is no API for it and
it is a plain enough algorithm to keep in sync by hand.

`site/` is GENERATED HTML and gitignored (see CLAUDE.md's "Where things
live" table): a fresh checkout has no pages until a study/doc build runs, so
a broken link INTO `site/` is only a WARNING here, not an error -- unless
`--strict` is passed, in which case it is treated like any other link.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_TOP = ["README.md", "CLAUDE.md", "GEMINI.md"]
_DEFAULT_GLOBS = ["docs/**/*.md", "research/**/*.md"]

_FENCE_RE = re.compile(r"^\s*```")
_INLINE_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_REF_LINK_RE = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*(\S+)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_ID_ATTR_RE = re.compile(r'<[a-zA-Z][^>]*\b(?:id|name)="([^"]+)"')
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_MD_EMPHASIS_RE = re.compile(r"\*{1,3}")
_MD_LINK_TEXT_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


@dataclass
class Problem:
    path: Path
    line: int
    target: str
    reason: str
    warning: bool = False

    def format(self, root: Path, as_warning: bool | None = None) -> str:
        rel = self.path.relative_to(root)
        is_warning = self.warning if as_warning is None else as_warning
        kind = "WARNING" if is_warning else "broken link"
        return f"{rel}:{self.line}: {kind} -> {self.target} ({self.reason})"


def slugify(heading: str) -> str:
    """GitHub-style anchor slug for a heading's text (see module docstring)."""
    text = heading.replace("`", "")
    text = _MD_LINK_TEXT_RE.sub(r"\1", text)
    text = _MD_EMPHASIS_RE.sub("", text)
    text = text.lower()
    text = "".join(ch for ch in text if ch.isalnum() or ch in (" ", "-", "_"))
    return text.replace(" ", "-")


def _iter_non_fenced_lines(text: str):
    """Yield (lineno, line) pairs, skipping lines inside fenced code blocks."""
    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            yield i, line


def _slugs_for_file(text: str) -> set[str]:
    slugs: set[str] = set()
    seen: dict[str, int] = {}
    for _, line in _iter_non_fenced_lines(text):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        base = slugify(m.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        slugs.add(base if count == 0 else f"{base}-{count}")
    slugs.update(_ID_ATTR_RE.findall(text))
    return slugs


def _extract_links(text: str) -> list[tuple[int, str]]:
    """Return (lineno, target) pairs for every link, ignoring code spans/fences."""
    out: list[tuple[int, str]] = []
    for lineno, raw_line in _iter_non_fenced_lines(text):
        line = _INLINE_CODE_RE.sub("", raw_line)
        out.extend((lineno, m.group(2)) for m in _INLINE_LINK_RE.finditer(line))
        ref = _REF_LINK_RE.match(line)
        if ref:
            out.append((lineno, ref.group(2)))
    return out


def _under_site(resolved: Path, root: Path) -> bool:
    try:
        resolved.relative_to(root / "site")
        return True
    except ValueError:
        return False


def _check_link(path: Path, lineno: int, target: str, root: Path, own_slugs: set[str]) -> Problem | None:
    if target.startswith(("http://", "https://", "mailto:")):
        return None

    raw_target, _, anchor = target.partition("#")
    raw_target = raw_target.strip()

    if not raw_target:  # in-page anchor only, e.g. [x](#some-heading)
        if anchor and anchor not in own_slugs:
            return Problem(path, lineno, target, f"no heading/id '#{anchor}' in {path.name}")
        return None

    decoded = unquote(raw_target)
    resolved = (path.parent / decoded).resolve()

    if not resolved.exists():
        return Problem(path, lineno, target, f"{decoded} does not exist", warning=_under_site(resolved, root))

    if anchor and resolved.is_file() and resolved.suffix == ".md":
        target_slugs = _slugs_for_file(resolved.read_text(encoding="utf-8", errors="replace"))
        if anchor not in target_slugs:
            return Problem(path, lineno, target, f"no heading/id '#{anchor}' in {decoded}",
                            warning=_under_site(resolved, root))
    return None


def _default_files(root: Path) -> list[Path]:
    files = [root / name for name in _DEFAULT_TOP if (root / name).exists()]
    for pattern in _DEFAULT_GLOBS:
        files.extend(sorted(root.glob(pattern)))
    return files


def check(paths: list[Path] | None = None, root: Path = ROOT) -> list[Problem]:
    problems: list[Problem] = []
    for path in paths if paths else _default_files(root):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        own_slugs = _slugs_for_file(text)
        for lineno, target in _extract_links(text):
            problem = _check_link(path, lineno, target, root, own_slugs)
            if problem is not None:
                problems.append(problem)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="specific markdown files to scan instead of the default set")
    parser.add_argument("--strict", action="store_true", help="treat site/ links as errors too")
    parser.add_argument("--quiet", action="store_true", help="print only the summary line")
    args = parser.parse_args(argv)

    paths = [Path(p).resolve() for p in args.paths] if args.paths else None
    problems = check(paths)

    if args.strict:
        errors, warnings = problems, []
    else:
        errors = [p for p in problems if not p.warning]
        warnings = [p for p in problems if p.warning]

    if not args.quiet:
        for problem in sorted(warnings, key=lambda p: (str(p.path), p.line)):
            print(problem.format(ROOT))
        for problem in sorted(errors, key=lambda p: (str(p.path), p.line)):
            print(problem.format(ROOT, as_warning=False))

    print(f"checked links: {len(errors)} broken, {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
