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


_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_SLUG_DROP = re.compile(r"[^\w\- ]")


def _slug(text: str) -> str:
    """GitHub-style heading anchor, so `[x](#the-q2-statistic)` lands."""
    return _SLUG_DROP.sub("", text.lower().replace("`", "")).strip().replace(" ", "-")


def _inline(text: str, resolve=None) -> str:
    """Escape, then honour `code`, **bold**, *italic* — in that order.

    With `resolve` (href -> URL or None), `[text](href)` becomes a link, or the
    text in <code> when resolve returns None. Without it links stay literal,
    which is what the digest pages have always done.
    """
    out = html.escape(text, quote=False)
    if resolve is not None:
        stash: list[str] = []

        def keep(m):
            stash.append(m.group(0))
            return f"\x00{len(stash) - 1}\x00"

        out = _INLINE_CODE.sub(keep, out)

        def link(m):
            url = resolve(html.unescape(m.group(2)))
            label = m.group(1)
            return (f'<a href="{html.escape(url)}">{label}</a>' if url
                    else f"<code>{label}</code>")

        out = _LINK.sub(link, out)
        out = re.sub("\x00(\\d+)\x00", lambda m: stash[int(m.group(1))], out)
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


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _list(lines: list[str], i: int, resolve) -> tuple[str, int]:
    """One (possibly nested) list starting at lines[i]; returns (html, next index).

    Items may continue on following indented lines and hold a deeper list.
    """
    n = len(lines)
    base = _indent(lines[i])
    first = lines[i].strip()
    tag = "ol" if _OL.match(first) else "ul"
    items: list[str] = []
    while i < n:
        line = lines[i]
        m = _UL.match(line.strip()) or _OL.match(line.strip())
        if not line.strip() or _indent(line) != base or not m:
            break
        parts = [m.group(2)]
        i += 1
        nested = ""
        while i < n and lines[i].strip():
            nxt = lines[i]
            marker = _UL.match(nxt.strip()) or _OL.match(nxt.strip())
            if marker and _indent(nxt) > base:
                nested, i = _list(lines, i, resolve)
            elif marker or _indent(nxt) <= base or nested:
                break
            else:
                parts.append(nxt.strip())
                i += 1
        items.append(f"<li>{_inline(' '.join(parts), resolve)}{nested}</li>")
        j = i
        while j < n and not lines[j].strip():
            j += 1   # a blank line between items keeps one list
        if j < n and j > i and _indent(lines[j]) == base and (
                _UL.match(lines[j].strip()) or _OL.match(lines[j].strip())):
            i = j
    return f"<{tag}>" + "".join(items) + f"</{tag}>", i


def _md_to_html(text: str, resolve=None) -> str:
    lines = text.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    para: list[str] = []

    def flush_para() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para), resolve)}</p>")
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
            head = m.group(2).strip()
            anchor = f' id="{_slug(head)}"' if resolve is not None else ""
            out.append(f"<h{level}{anchor}>{_inline(head, resolve)}</h{level}>")
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
            thead = "".join(f"<th>{_inline(c, resolve)}</th>" for c in header)
            tbody = "".join(
                "<tr>" + "".join(f"<td>{_inline(c, resolve)}</td>" for c in row) + "</tr>"
                for row in body_rows)
            out.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>")
            continue

        if _QUOTE.match(stripped):
            flush_para()
            quote_lines = []
            while i < n and _QUOTE.match(lines[i].strip()):
                quote_lines.append(_QUOTE.match(lines[i].strip()).group(1))
                i += 1
            out.append(f"<blockquote><p>{_inline(' '.join(quote_lines), resolve)}</p></blockquote>")
            continue

        if _UL.match(stripped) or _OL.match(stripped):
            flush_para()
            block, i = _list(lines, i, resolve)
            out.append(block)
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
  <p class="digest-back"><a href="dashboard.html#studies">← studies on the dashboard</a></p>
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


def prereg_page(src: Path, root: Path, pages: dict[Path, str]) -> str:
    """One registration as a standalone page: title, source path, way back, rendered body.

    A relative link to another registration that has a page points at that page;
    any other repo link shows as code (the file is not part of the site).
    """
    def resolve(href: str) -> str | None:
        if href.startswith(("http://", "https://")) or href.startswith("#"):
            return href
        target, _, frag = href.partition("#")
        if target.endswith(".md"):
            dest = pages.get((src.parent / target).resolve())
            if dest:
                return dest + (f"#{frag}" if frag else "")
        return None

    raw = _unwrap_stray_fence(src.read_text(errors="replace"))
    first = next((ln[2:].strip() for ln in raw.split("\n") if ln.startswith("# ")), src.stem)
    try:
        shown = src.relative_to(render.ROOT).as_posix()
    except ValueError:
        shown = src.as_posix()
    css = (render.ASSETS / "page.css").read_text()
    e = html.escape
    return f"""<title>{e(first, quote=False)} — registration</title>
<style>
{css}
.digest-page table{{display:block;overflow-x:auto}}
</style>

<div class="wrap digest-page">
  <p class="digest-back"><a href="dashboard.html#studies">← studies on the dashboard</a></p>
  <p class="digest-src">Pre-registration, rendered from <code>{e(shown, quote=False)}</code>.</p>
{_md_to_html(raw, resolve)}
</div>
"""


def write_prereg(site_dir: Path, root: Path = render.PREREG_DIR) -> list[Path]:
    """Render every registration under root to site_dir. Returns the paths written."""
    names = render.prereg_pages(root)
    resolved = {f.resolve(): n for f, n in names.items()}
    written: list[Path] = []
    for src, name in names.items():
        site_dir.mkdir(parents=True, exist_ok=True)
        dest = site_dir / name
        dest.write_text(render.wrap_standalone(prereg_page(src, root, resolved)))
        written.append(dest)
    return written


if __name__ == "__main__":
    for path in write_all():
        print(f"wrote {path}")
