"""Render each study's plain-language digest to a standalone page under `site/`.

`scripts/study_review` writes a graded write-up to
`backtests/study_output/<study>-digest-latest.md` — readable prose, but plain
Markdown text on disk, so nobody actually opens it. This module renders that
file to `site/<study>-digest.html` (see `render.site_name`) so the study map
can link straight to it.

No markdown library is used. `markdown-it-py` sits in `.venv` only as an
undeclared transitive dependency of `rich`, which this repo doesn't otherwise
use — importing it here would quietly turn "installed in this venv" into "a
declared dependency of a clean install." The digest grammar the study-review
prompt actually produces is small (headings, paragraphs, a few tables and
lists, the odd code span), so `_md_to_html` hand-rolls just that subset, in
the same spirit as `render.py`'s `_rich()` and `summary.py`'s
`_banner_sections`/`_section_body` — escape first, recognise a handful of
patterns, never attempt to be a general parser.

One data quirk to work around: 5 of the 7 real digest files are wrapped
WHOLE-FILE in a stray ```markdown fence — the first line is a bare
"```markdown" (or "```"), the last is a bare "```", and the entire write-up
sits inside it. That's an LLM authoring quirk from `scripts/study_review`,
not a deliberate code block. `_unwrap_stray_fence` strips it before
conversion; left in place, every one of those pages would render as a single
inert `<pre><code>` block instead of formatted prose.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from . import catalog, render, summary

_FENCE_LINE = re.compile(r"^```(?:markdown)?\s*$")


def _unwrap_stray_fence(text: str) -> str:
    """Strip a whole-file ```markdown ... ``` wrapper, if the file is one big fence.

    Only fires when the FIRST non-blank line and the LAST non-blank line are
    both bare fence markers — a digest that legitimately opens with a fenced
    code example (fence not on line 1) is left alone.
    """
    stripped = text.strip("\n")
    lines = stripped.split("\n")
    if len(lines) < 2:
        return text
    if _FENCE_LINE.match(lines[0].strip()) and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return text


# ── inline formatting ────────────────────────────────────────────────────────
_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+?)\*\*")
_ITALIC = re.compile(r"\*([^*]+?)\*")


def _inline(text: str) -> str:
    """Escape, then honour `code`, **bold**, *italic* — in that order."""
    out = html.escape(text, quote=False)
    out = _INLINE_CODE.sub(r"<code>\1</code>", out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _ITALIC.sub(r"<em>\1</em>", out)
    return out


# ── block conversion ─────────────────────────────────────────────────────────
_ATX = re.compile(r"^(#{1,4})\s+(.*)$")
_HR = re.compile(r"^-{3,}$")
_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*\|?\s*$")
_UL = re.compile(r"^([-*])\s+(.*)$")
_OL = re.compile(r"^(\d+)[.)]\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")


def _split_row(line: str) -> list[str]:
    cells = line.strip()
    if cells.startswith("|"):
        cells = cells[1:]
    if cells.endswith("|"):
        cells = cells[:-1]
    return [c.strip() for c in cells.split("|")]


def _md_to_html(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    para: list[str] = []

    def flush_para() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        # fenced code block
        if stripped.startswith("```"):
            flush_para()
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
            continue

        m = _ATX.match(stripped)
        if m:
            flush_para()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2).strip())}</h{level}>")
            i += 1
            continue

        if _HR.match(stripped):
            flush_para()
            out.append("<hr>")
            i += 1
            continue

        # pipe table: a "| ... |" row followed by a "|---|---|" separator
        if (_TABLE_ROW.match(line) and i + 1 < n and _TABLE_SEP.match(lines[i + 1])):
            flush_para()
            header = _split_row(line)
            i += 2  # header + separator
            body_rows = []
            while i < n and _TABLE_ROW.match(lines[i]):
                body_rows.append(_split_row(lines[i]))
                i += 1
            thead = "".join(f"<th>{_inline(c)}</th>" for c in header)
            tbody = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>"
                for row in body_rows)
            out.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>")
            continue

        if _QUOTE.match(stripped):
            flush_para()
            quote_lines = []
            while i < n and _QUOTE.match(lines[i].strip()):
                quote_lines.append(_QUOTE.match(lines[i].strip()).group(1))
                i += 1
            out.append(f"<blockquote><p>{_inline(' '.join(quote_lines))}</p></blockquote>")
            continue

        if _UL.match(stripped):
            flush_para()
            items = []
            while i < n and _UL.match(lines[i].strip()):
                items.append(_UL.match(lines[i].strip()).group(2))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(it)}</li>" for it in items) + "</ul>")
            continue

        if _OL.match(stripped):
            flush_para()
            items = []
            while i < n and _OL.match(lines[i].strip()):
                items.append(_OL.match(lines[i].strip()).group(2))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_inline(it)}</li>" for it in items) + "</ol>")
            continue

        para.append(stripped)
        i += 1

    flush_para()
    return "\n".join(out)


# ── page ──────────────────────────────────────────────────────────────────────
def page(study: str, md_path: Path) -> str:
    """The digest, rendered as a standalone-publishable HTML fragment."""
    raw = _unwrap_stray_fence(md_path.read_text(errors="replace"))
    body_html = _md_to_html(raw)
    title = summary._digest_title(md_path) or study
    css = (render.ASSETS / "page.css").read_text()
    return f"""<title>{html.escape(title, quote=False)} — digest</title>
<style>
{css}
</style>

<div class="wrap digest-page">
  <p class="digest-back"><a href="study-map.html">← study map</a></p>
  <p class="digest-src">Rendered from <code>{html.escape(md_path.name, quote=False)}</code> — \
regenerate with <code>python -m scripts.study_review {html.escape(study, quote=False)}</code>.</p>
{body_html}
</div>
"""


def write_all(out_dir: Path = summary.OUT_DIR, site_dir: Path | None = None) -> list[Path]:
    """Render every study's digest (if it has one) to `site_dir`. Returns paths written.

    Iterates `catalog.STUDIES` — never a glob — because `{study}-digest-latest.md`
    is the load-bearing name contract shared with `scripts/study_review` and
    `summary.py`. A fresh checkout has no digests on disk, so this returns []
    without creating anything under `site/` beyond the directory itself.
    """
    site_dir = site_dir if site_dir is not None else render.ROOT / "site"
    written: list[Path] = []
    for name in catalog.STUDIES:
        md_path = out_dir / f"{name}-digest-latest.md"
        if not md_path.is_file():
            continue
        site_dir.mkdir(parents=True, exist_ok=True)
        dest = site_dir / render.site_name(name)
        dest.write_text(render.wrap_standalone(page(name, md_path)))
        written.append(dest)
    return written


if __name__ == "__main__":
    for path in write_all():
        print(f"wrote {path}")
