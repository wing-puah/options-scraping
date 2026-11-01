"""
Fetcher for the legs `selloff_put_diagonal`'s packages need.

WHY THIS EXISTS
---------------
`selloff_put_diagonal` (research/pre-registrations/f1_selection/regime/
selloff_put_diagonal.md, accepted by default 2026-11-01) buys a near SPY put
and a long-dated call diagonal on each sell-off trigger day, and the same
package on calm weeks. The diagonal's long leg sits on a monthly about a year
out, and its short leg rolls three times, so most of those contracts are not in
the option cache. A package whose nearest listable strike, or whose long
expiry's listing, is unknown is AWAITING FETCH; while any PRIMARY package
awaits, the study prints NOT BUILT — AWAITING SCRAPE. This collector fetches
them. It names calls AND puts.

TARGETS (`selloff_put_diagonal.plan`, IMPORTED)
-----------------------------------------------
The strikes an awaiting package names: each leg's nearest-first walk, read on
its decision day, plus the standard-grid strike that settles whether a long
expiry was listed. A fetch can expose a nearer strike or prove one unlisted,
so the study and this collector alternate until nothing awaits. Every run
recomputes the targets from the cache as it stands, so the loop is resumable.

  --scope primary  (default) the primary cell, ARM K and ARM C, in-sample
  --scope all      every parameter cell, both arms

HOW IT FETCHES
--------------
Exactly as `fetch_mechanical_baseline_legs.py`, whose writer check and
contract builder it imports: `fetch_option_histories`, one Barchart session,
the `HISTORY_START_DATE` floor, the atomic cache write, the evidence-gated
skip-list and the network-outage abort (exit 6). A real fetch REFUSES (exit
3) while another option-cache writer runs. `--dry-run` reads the cache index
and the skip-list from disk, prints the count, and touches no network.

Needs BARCHART_EMAIL/BARCHART_PASSWORD for a real fetch. Research tier, run by
hand. Run `python3 scripts/backup_research_caches.py push` after it.

Usage:
  python3 scripts/collector/study_legs/fetch_selloff_put_diagonal_legs.py --dry-run
  python3 scripts/collector/study_legs/fetch_selloff_put_diagonal_legs.py --limit 50
  python3 scripts/collector/study_legs/fetch_selloff_put_diagonal_legs.py --scope all --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.logger import setup_logging  # noqa: E402
from scripts.backtest_study.f1_selection.regime import selloff_put_diagonal as SPD  # noqa: E402
from scripts.collector.study_legs.fetch_mechanical_baseline_legs import (  # noqa: E402
    EXIT_OTHER_WRITER, other_writers,
)
from scripts.collector.study_legs.fetch_mechanical_legs import (  # noqa: E402
    BACKUP_REMINDER, to_contracts,
)

log = logging.getLogger("fetch_selloff_put_diagonal_legs")

SCOPES = ("primary", "all")


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
                    help="Print the contract count; no network, no write.")
    ap.add_argument("--list", action="store_true",
                    help="With --dry-run, also print every contract.")
    ap.add_argument("--scope", default="primary", choices=SCOPES,
                    help="primary (default): the primary cell; all: every parameter cell.")
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

    targets = SPD.plan(args.scope)
    todo = targets if args.limit is None else targets[:args.limit]
    by = Counter(t["category"] for t in targets)
    cats = "  ".join(f"{k}={v}" for k, v in sorted(by.items()))
    kinds = Counter(t["opt_type"] for t in targets)
    print(f"unique uncached contracts to fetch ({args.scope}): {len(targets)}  "
          f"calls={kinds['Call']} puts={kinds['Put']}  {cats}")
    if args.limit is not None:
        print(f"this run fetches at most {args.limit}")
    if args.dry_run:
        if args.list:
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
