"""Render the account_sim study's deployed book as a breakdown by market regime.

    python -m scripts.study_charts.regime
    python -m scripts.study_charts.regime --standalone --open
    python -m scripts.study_charts.regime --positions .../account_sim-positions-structure-latest.csv

Same inputs, same arm pairing and same reconcile-or-fail contract as the
feasibility readout (`account_sim.py`) — both run through `cli.py`. What
differs is only what gets drawn: where the book deployed under each of the two
regime readings it carries, what those positions cost the account, what the
caps refused there, and how far the two readings disagree.

The study prints this cut itself, in its own `DEPLOYED BOOK BY REGIME` section,
and it prints it flagged as post-hoc. That is deliberate: a page like this is
exactly where a descriptive table starts getting quoted as a regime edge, so
the numbers had to exist in the study — and be reconciled against it — before
they were allowed to become charts.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.study_charts import cli, render_regime  # noqa: E402

SITE_NAME = "account-sim-regime.html"


def site_dest(positions: Path, site_dir: Path = cli.SITE_DIR) -> Path | None:
    """Where this page's site copy lives, or None for the structure arm."""
    return cli.site_dest(positions, SITE_NAME, site_dir)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_arguments(ap, SITE_NAME)
    args = ap.parse_args(argv)
    return cli.run(args, build=render_regime.build, out_stem="account_sim-regime",
                   site_name=SITE_NAME, module="regime")


if __name__ == "__main__":
    raise SystemExit(main())
