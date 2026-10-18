"""Decide whether the Flow Pacemaker should scrape today.

Prints `open=true|false` and `reason=...` (appended to $GITHUB_OUTPUT when set).
"Today" is the date in ET, never the runner's clock date: at 09:00 UTC on a
Monday it is still Monday in New York, but at 01:00 UTC it is still Sunday.

The holiday calendar is backfill_chain's `_nyse_holidays` — the repo's one
encoding of it — imported rather than copied so the two can never disagree.

    python .github/scripts/pacemaker_gate.py                 # today (ET)
    python .github/scripts/pacemaker_gate.py --date 2026-11-26
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.collector.history.backfill_chain import _nyse_holidays  # noqa: E402

ET = ZoneInfo("America/New_York")


def session_status(d: date) -> tuple[bool, str]:
    """(is a trading session, human-readable reason)."""
    if d.weekday() >= 5:
        return False, f"{d} is a {d.strftime('%A')} — market closed"
    if d in _nyse_holidays(d, d):
        return False, f"{d} is an NYSE holiday — market closed"
    return True, f"{d} is a trading session"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=date.fromisoformat,
                    help="override today's ET date (YYYY-MM-DD)")
    args = ap.parse_args()

    d = args.date or datetime.now(ET).date()
    is_open, reason = session_status(d)
    lines = [f"open={'true' if is_open else 'false'}", f"reason={reason}"]
    print("\n".join(lines))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
