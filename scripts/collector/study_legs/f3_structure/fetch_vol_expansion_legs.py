"""
Fetcher for the legs `vol_expansion_long_vol`'s trades need.

WHY THIS EXISTS
---------------
`vol_expansion_long_vol` (research/pre-registrations/f3_structure/
vol_expansion_long_vol.md, accepted on the defaults 2026-11-27) opens a SPY
straddle and two 1x2 backspreads at the close after each `E-VOL` onset and on
each calm ISO week, on strikes walked on a fixed $1 step. SPY's cache is mostly
a $5 grid, so most of those contracts are not cached. While any headline entry
awaits a contract, the study prints NOT BUILT — AWAITING SCRAPE. This collector
fetches them. It names calls AND puts.

TARGETS (`vol_expansion_long_vol.fetch_targets`, IMPORTED)
----------------------------------------------------------
The strikes an awaiting entry names: each leg's nearest-first walk on the $1
step, read on its fill day. A fetch can prove a strike unlisted, so the study and
this collector alternate until nothing awaits. A cached file from before the
range fix that has no row by the fill day is re-fetched through `needed_dates`.
Every run recomputes the targets from the cache as it stands, so it resumes.

  --scope primary  (default) the headline cells' onsets and ARM C (monthly ~30 DTE)
  --scope all      also the 60-DTE onset cells (the PBO grid)

HOW IT FETCHES
--------------
Exactly as `fetch_daily_vol_structure_legs.py`: `fetch_option_histories`, one
Barchart session, the `HISTORY_START_DATE` floor, the atomic cache write, the
evidence-gated skip-list and the network-outage abort (exit 6). A real fetch
REFUSES (exit 3) while another option-cache writer runs. `--dry-run` reads the
cache index and the skip-list from disk, prints the counts, and touches no
network and no file.

Needs BARCHART_EMAIL/BARCHART_PASSWORD for a real fetch. Research tier, run by
hand. Run `python3 scripts/backup_research_caches.py push` after it.

Usage:
  python3 scripts/collector/study_legs/f3_structure/fetch_vol_expansion_legs.py --dry-run --list
  python3 scripts/collector/study_legs/f3_structure/fetch_vol_expansion_legs.py --limit 100
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

ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.logger import setup_logging  # noqa: E402
from scripts.backtest_study.f3_structure import vol_expansion_long_vol as VEL  # noqa: E402
from scripts.collector.study_legs.f1_selection.fetch_mechanical_baseline_legs import (  # noqa: E402
    EXIT_OTHER_WRITER, other_writers,
)
from scripts.collector.study_legs.f1_selection.fetch_mechanical_legs import (  # noqa: E402
    BACKUP_REMINDER, to_contracts,
)

log = logging.getLogger("fetch_vol_expansion_legs")

SCOPES = ("primary", "all")


async def fetch(targets: list[dict], headless: bool, timeout_ms: int) -> int:
    from scripts.backtest.shared.history import fetch_option_histories
    contracts = to_contracts(targets)
    needed = {c["key"]: t["needed"] for c, t in zip(contracts, targets) if t.get("needed")}
    series, _details = await fetch_option_histories(
        contracts, headless, timeout_ms, needed_dates=needed, retry_unlisted=True)
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
                    help="primary (default): headline onsets and ARM C; all: also 60 DTE.")
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

    targets = VEL.plan(args.scope)
    todo = targets if args.limit is None else targets[:args.limit]
    by = Counter(t["category"] for t in targets)
    cats = "  ".join(f"{k}={v}" for k, v in sorted(by.items()))
    kinds = Counter(t["opt_type"] for t in targets)
    print(f"unique contracts to fetch ({args.scope}): {len(targets)}  "
          f"calls={kinds['Call']} puts={kinds['Put']}  "
          f"re-fetches={sum(1 for t in targets if t.get('needed'))}  {cats}")
    exps = Counter(t["expiration"] for t in targets)
    print(f"expiries named: {len(exps)}  "
          f"({min(exps).isoformat() if exps else '-'} -> {max(exps).isoformat() if exps else '-'})")
    if args.limit is not None:
        print(f"this run fetches at most {args.limit}")
    if args.dry_run:
        if args.list:
            for t in todo:
                print(f"  {t['ticker']:<6} {t['expiration'].isoformat()} "
                      f"{t['strike']:>9.2f}{t['opt_type'][0]}  {t['category']}"
                      + (f"  re-fetch from {t['needed']}" if t.get("needed") else ""))
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
