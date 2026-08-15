"""CLI: `python -m scripts.study_map [--open] [--fragment] [-o PATH]`."""
from __future__ import annotations

import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path

from . import build, catalog, summary


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="python -m scripts.study_map",
        description="Render site/study-map.html — what every backtest study asks, "
                    "and what its last run printed.")
    ap.add_argument("-o", "--out", type=Path, default=build.DEST,
                    help=f"output path (default: {build.DEST.relative_to(build.ROOT)})")
    ap.add_argument("--fragment", action="store_true",
                    help="emit the bare fragment (no doctype/head) for publishing")
    ap.add_argument("--open", action="store_true", help="open it in a browser after writing")
    ap.add_argument("--check", action="store_true",
                    help="print each study's last-run status instead of rendering")
    args = ap.parse_args()

    if args.check:
        runs = summary.summarize_all(list(catalog.STUDIES))
        width = max(len(n) for n in runs)
        for name, run in runs.items():
            when = run.run_at.split()[0] if run.run_at else "-"
            kind = f"  [{run.excerpt_kind}]" if run.excerpt_kind else ""
            print(f"  {name:{width}s}  {catalog.state_of(name):9s}  "
                  f"{when:10s}  {run.status}{kind}")
        return 0

    path = build.write(args.out, standalone=not args.fragment)
    rel = path.relative_to(build.ROOT) if path.is_relative_to(build.ROOT) else path
    print(f"wrote {rel}")
    if args.open:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            webbrowser.open(path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
