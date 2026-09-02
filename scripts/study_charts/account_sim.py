"""Render the account_sim study's results as a single self-contained HTML page.

    python -m scripts.study_charts.account_sim
    python -m scripts.study_charts.account_sim --standalone --open
    python -m scripts.study_charts.account_sim --positions .../account_sim-positions-structure-latest.csv

The study writes two artifacts per run — a fixed-width report and a positions
CSV — and `<name>-latest.txt` is whichever ARM ran last, which is not
necessarily the arm that wrote `account_sim-positions-latest.csv`. So the
report is chosen to match the positions file's arm rather than assumed, and
every recomputed number is reconciled against the report before the page is
written. A mismatch is a hard error: a chart that quietly disagrees with the
report it claims to draw is worse than no chart.

Two files come out of one run, for two different readers: the scratch fragment
under `backtests/study_output/` (what the Artifact publisher wants) and a
standalone `site/account-sim-charts.html`, the double-clickable copy. `site/` is
generated output and gitignored — `make study-docs` rebuilds the lot. `--no-site`
writes only the scratch one, and the structure-universe arm always writes only
the scratch one (see `cli.site_dest`).

The pipeline itself lives in `cli.py`, shared with the regime page.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.study_charts import cli, render  # noqa: E402
from scripts.study_charts.cli import (  # noqa: E402,F401  (kept importable: callers and tests use these)
    SITE_DIR, is_structure_arm, pick_report,
)

SITE_NAME = "account-sim-charts.html"


def site_dest(positions: Path, site_dir: Path = SITE_DIR) -> Path | None:
    """Where this page's site copy lives, or None for the structure arm."""
    return cli.site_dest(positions, SITE_NAME, site_dir)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_arguments(ap, SITE_NAME)
    args = ap.parse_args(argv)
    return cli.run(args, build=render.build, out_stem="account_sim-charts",
                   site_name=SITE_NAME, module="readout")


if __name__ == "__main__":
    raise SystemExit(main())
