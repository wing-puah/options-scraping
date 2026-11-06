"""
Fetcher for the legs `daily_vol_structure`'s trades need.

WHY THIS EXISTS
---------------
`daily_vol_structure` (research/pre-registrations/f3_structure/
daily_vol_structure.md, accepted by default 2026-11-06) opens a straddle and two
1x2 ratios on QQQ and SMH every session, on a monthly near 30 DTE and a weekly
near 7 DTE. Most of those contracts are not in the option cache. While any
trade awaits a contract, the study prints NOT BUILT — AWAITING SCRAPE. This
collector fetches them. It names calls AND puts.

TARGETS (`daily_vol_structure.fetch_targets`, IMPORTED)
-------------------------------------------------------
The strikes an awaiting trade names: each leg's nearest-first walk, read on its
signal day. Strikes are probed, never inferred from a sparse cache. A fetch can
expose a nearer strike or prove one unlisted, so the study and this collector
alternate until nothing awaits. Every run recomputes the targets from the cache
as it stands, so the loop is resumable.

  --scope window   (default) the graded dates, 2024-03-15 to 2026-09-22
  --scope forward  signal dates from 2026-09-23, once a CANDIDATE has printed

Refresh the QQQ and SMH OHLC first: a date past the OHLC's end names no strike,
so an old file makes the count low. The dry run says how many trades that holds
back, and prints `Price~` against the closes for the trades already built.

HOW IT FETCHES
--------------
Exactly as `fetch_selloff_put_diagonal_legs.py`: `fetch_option_histories`, one
Barchart session, the `HISTORY_START_DATE` floor, the atomic cache write, the
evidence-gated skip-list and the network-outage abort (exit 6). A real fetch
REFUSES (exit 3) while another option-cache writer runs. `--dry-run` reads the
cache index and the skip-list from disk, prints the counts, and touches no
network.

Needs BARCHART_EMAIL/BARCHART_PASSWORD for a real fetch. Research tier, run by
hand. Run `python3 scripts/backup_research_caches.py push` after it.

Usage:
  python3 scripts/collector/study_legs/fetch_daily_vol_structure_legs.py --dry-run
  python3 scripts/collector/study_legs/fetch_daily_vol_structure_legs.py --limit 50
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
from scripts.backtest_study.f3_structure import daily_vol_structure as DVS  # noqa: E402
from scripts.collector.study_legs.fetch_mechanical_baseline_legs import (  # noqa: E402
    EXIT_OTHER_WRITER, other_writers,
)
from scripts.collector.study_legs.fetch_mechanical_legs import (  # noqa: E402
    BACKUP_REMINDER, to_contracts,
)

log = logging.getLogger("fetch_daily_vol_structure_legs")

SCOPES = ("window", "forward")


async def fetch(targets: list[dict], headless: bool, timeout_ms: int) -> int:
    from scripts.backtest.shared.history import fetch_option_histories
    contracts = to_contracts(targets)
    series, _details = await fetch_option_histories(
        contracts, headless, timeout_ms, retry_unlisted=True)
    return sum(1 for c in contracts if series.get(c["key"]))


def print_census(book: DVS.Book) -> None:
    """Counts, and `Price~` against the closes. No option price."""
    DVS.print_coverage(book)
    held = sum(1 for tk in DVS.TICKERS for t in DVS.TENORS for tr in book.trades(tk, t)
               if tr.reason == "no_ohlc_bar")
    if held:
        print(f"  {held} trades name no strike yet, because the OHLC ends before their date; "
              "refresh it and re-run for the full count")
    for tk, (glitches, runs) in book.split_census().items():
        print(f"  {tk} Price~ against the closes, on built trades: {glitches} bad-print days, "
              f"{len(runs)} split-basis runs")


def main(argv=None) -> int:
    setup_logging()
    log.setLevel(logging.INFO)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the contract count; no network, no write.")
    ap.add_argument("--list", action="store_true",
                    help="With --dry-run, also print every contract.")
    ap.add_argument("--scope", default="window", choices=SCOPES,
                    help="window (default): the graded dates; forward: from 2026-09-23.")
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

    book = DVS.build_book()
    if args.dry_run:
        print_census(book)
    targets = DVS.fetch_targets(book, args.scope)
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
