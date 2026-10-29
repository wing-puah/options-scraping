"""Build the studies section, and rebuild the dashboard that carries it.

The study map has no page of its own since 2026-10-29: it is the "What have the
studies found?" section of `site/dashboard.html`, built by `scripts/dashboard.py`.
`site/` is gitignored, so a fresh checkout has no dashboard until something
builds one — `make dashboard`, or any study run (the runner refreshes it).
Building the section is cheap: it only ever reads `backtests/study_output/` and
`research/current.md`. The digest pages (see `digest.py`) are written beside the
dashboard, one per study that has a plain-language write-up on disk.
"""
from __future__ import annotations

from pathlib import Path

from . import catalog, digest, render, summary, tuning

ROOT = Path(__file__).resolve().parents[2]


def build_fragment(out_dir: Path = summary.OUT_DIR,
                   log_path: Path = tuning.CURRENT_MD) -> str:
    """The studies section body, as an HTML fragment styled by the dashboard."""
    runs = summary.summarize_all(list(catalog.STUDIES), out_dir)
    return render.build(runs, tuning.read_log(log_path), tuning.log_mtime(log_path))


def write_digests(site_dir: Path, out_dir: Path = summary.OUT_DIR) -> list[Path]:
    """Render each study's digest page into site_dir, beside the dashboard that links it."""
    return digest.write_all(out_dir, site_dir)


def rebuild_dashboard(dest: Path | None = None, quiet: bool = True) -> Path:
    """Rebuild site/dashboard.html (or dest). Raises if the build fails."""
    from scripts import dashboard  # lazy: the dashboard imports this module
    out = Path(dest) if dest is not None else dashboard.OUT
    rc = dashboard.main(["--out", str(out)] + (["--quiet"] if quiet else []))
    if rc != 0:
        raise RuntimeError(f"scripts/dashboard.py exited {rc}")
    return out


def refresh_quietly(dest: Path | None = None) -> Path | None:
    """Best-effort rebuild for callers that must not fail because of this.

    The study runner calls this after a run. A study report is the valuable
    output; a broken dashboard must never turn a good run into a failed command.
    """
    try:
        return rebuild_dashboard(dest)
    except Exception:  # noqa: BLE001 - deliberately swallowed, see docstring
        return None
