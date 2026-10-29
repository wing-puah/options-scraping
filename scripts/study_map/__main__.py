"""CLI: `python -m scripts.study_map [--open] [--check]`."""
from __future__ import annotations

import argparse
import subprocess
import sys
import webbrowser

from . import build, catalog, summary


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="python -m scripts.study_map",
        description="Rebuild site/dashboard.html, whose studies section says what every "
                    "backtest study asks and what its last run printed.")
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

    path = build.rebuild_dashboard(quiet=False)
    if args.open:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            webbrowser.open(path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
