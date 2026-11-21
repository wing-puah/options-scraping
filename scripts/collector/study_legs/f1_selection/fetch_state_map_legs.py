"""
Fetcher for the SPY put strikes `state_map`'s Q4 section needs.

WHY THIS EXISTS
---------------
`state_map` Q4 (research/pre-registrations/f1_selection/regime/state_map.md)
prices a fixed 30-DTE SPY put spread on each Q3 signal from 2022-02-01. An
onset whose strikes are not in the option cache is AWAITING a fetch; while any
awaits, Q4 prints `AWAITING SCRAPE`. This collector fetches those puts.

TARGETS (`state_map.q4_fetch_list`, IMPORTED)
---------------------------------------------
The uncached contracts the awaiting onsets name, on the cache and skip-list as
they stand. A fetch can expose a nearer strike or prove one unlisted, so the
study and this collector alternate until the list is empty. Every run
recomputes the targets, so the loop is resumable.

HOW IT FETCHES
--------------
Exactly as `fetch_selloff_put_diagonal_legs.py`, whose writer check and
contract builder it imports: `fetch_option_histories`, one Barchart session,
the `HISTORY_START_DATE` floor, the atomic cache write, the evidence-gated
skip-list (a 404 is recorded unlisted; a network error, 403 or 5xx never is)
and the network-outage abort (exit 6). A real fetch REFUSES (exit 3) while
another option-cache writer runs. `--dry-run` reads the cache and the
skip-list from disk, prints the contracts, and touches no network.

Needs BARCHART_EMAIL/BARCHART_PASSWORD for a real fetch. Research tier, run by
hand. Run `python3 scripts/backup_research_caches.py push` ONCE after it.

Usage:
  python3 scripts/collector/study_legs/f1_selection/fetch_state_map_legs.py --dry-run
  python3 scripts/collector/study_legs/f1_selection/fetch_state_map_legs.py
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.logger import setup_logging  # noqa: E402
from scripts.backtest_study.f1_selection.regime import state_map as SM  # noqa: E402
from scripts.collector.study_legs.f1_selection.fetch_mechanical_baseline_legs import (  # noqa: E402
    EXIT_OTHER_WRITER, other_writers,
)
from scripts.collector.study_legs.f1_selection.fetch_mechanical_legs import (  # noqa: E402
    BACKUP_REMINDER, to_contracts,
)

log = logging.getLogger("fetch_state_map_legs")

MAX_ROUNDS = 10


def plan() -> list[dict]:
    """The Q4 fetch list on the cache as it stands. Selection only: nothing is
    priced and no network is touched. Rebuilds the calendar and flags exactly
    as `SM.analyse` does, from the cached series."""
    spy, vix, vix3m, hyg, ief, _rows = SM.load_inputs(False)
    full = SM.build_cal(spy, vix, vix3m, hyg, ief)
    cal = SM.cut_cal(full, SM.IN_SAMPLE_END)
    lab50 = SM.labels_from_labeler(SM.write_mech_csv(cal, SM.MECH_CSV), cal.dates)
    lab200 = SM.mech_labels(cal, SM.SMA_LONG)
    flags = SM.state_flags(lab50, lab200)
    flags["_vol"] = lab50.vol
    chain, evidence, _comm = SM.q4_env()
    return SM.q4_fetch_list(SM.q4_trades(chain, evidence, cal, flags))


async def fetch(targets: list[dict], headless: bool, timeout_ms: int) -> int:
    from scripts.backtest.shared.history import fetch_option_histories
    contracts = to_contracts(targets)
    series, _details = await fetch_option_histories(
        contracts, headless, timeout_ms, retry_unlisted=True)
    return sum(1 for c in contracts if series.get(c["key"]))


def main(argv=None) -> int:
    setup_logging()
    log.setLevel(logging.INFO)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the contracts; no network, no write.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Fetch at most N contracts this run (resumable).")
    ap.add_argument("--no-headless", action="store_true", help="Visible browser.")
    ap.add_argument("--timeout-ms", type=int, default=15000)
    args = ap.parse_args(argv)

    if not args.dry_run:
        busy = other_writers()
        if busy:
            pid, pat = busy[0]
            print(f"REFUSED: another option-cache writer is running (PID {pid}, "
                  f"matched {pat!r}). One writer at a time.", file=sys.stderr)
            return EXIT_OTHER_WRITER

    targets = plan()
    todo = targets if args.limit is None else targets[:args.limit]
    print(f"unique uncached contracts to fetch: {len(targets)}")
    if args.limit is not None:
        print(f"this run fetches at most {args.limit}")
    if args.dry_run:
        for t in todo:
            print(f"  {t['ticker']:<6} {t['expiration'].isoformat()} "
                  f"{t['strike']:>9.2f}{t['opt_type'][0]}  {t['category']}")
        print("[dry-run] nothing fetched")
        print(BACKUP_REMINDER)
        return 0
    if not todo:
        print("Nothing to fetch.")
        return 0
    from scripts.backtest.shared.history import EXIT_NETWORK_OUTAGE, NetworkOutage
    headless = not args.no_headless and os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
    try:
        got = asyncio.run(fetch(todo, headless, args.timeout_ms))
    except NetworkOutage as e:
        log.error("network outage: %d of %d fetches failed — stopped; what was "
                  "written is kept, re-run when online", e.n_failed, e.n_total)
        print(BACKUP_REMINDER)
        return EXIT_NETWORK_OUTAGE
    print(f"fetched {got} of {len(todo)} requested; "
          f"{len(targets) - len(todo)} left for a later run")
    print(BACKUP_REMINDER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
