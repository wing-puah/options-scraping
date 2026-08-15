"""Build the page and put it where it can be double-clicked.

`site/study-map.html` is generated output and `site/` is gitignored, so a fresh
checkout has no page until something builds one — `make study-map`, or any
study run (the runner refreshes it). Regenerating is cheap and side-effect free:
it only ever reads.
"""
from __future__ import annotations

from pathlib import Path

from . import catalog, render, summary, tuning

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "site" / "study-map.html"


def build_fragment(out_dir: Path = summary.OUT_DIR,
                   log_path: Path = tuning.CURRENT_MD) -> str:
    """The page as an HTML fragment (no doctype/head) — Artifact-publishable."""
    runs = summary.summarize_all(list(catalog.STUDIES), out_dir)
    return render.build(runs, tuning.read_log(log_path), tuning.log_mtime(log_path))


def write(dest: Path = DEST, out_dir: Path = summary.OUT_DIR,
          log_path: Path = tuning.CURRENT_MD, standalone: bool = True) -> Path:
    """Render and write the map. Returns the path written."""
    fragment = build_fragment(out_dir, log_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render.wrap_standalone(fragment) if standalone else fragment)
    return dest


def refresh_quietly(dest: Path = DEST) -> Path | None:
    """Best-effort rebuild for callers that must not fail because of this.

    The study runner calls this after a run. A study report is the valuable
    output; a broken map must never turn a good run into a failed command.
    """
    try:
        return write(dest)
    except Exception:  # noqa: BLE001 - deliberately swallowed, see docstring
        return None
