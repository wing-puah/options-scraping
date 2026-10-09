"""
Fetcher for the call legs `mechanical_benchmark`'s counterparts need.

WHY THIS EXISTS
---------------
`mechanical_benchmark` (research/pre-registrations/f1_selection/
mechanical_benchmark.md, accepted by default 2026-10-09) pairs every deployed
pick with a mechanical bull call spread: ATM / +5% on the same ticker and
expiry (M1), a delta-matched one (M2, M2L), and the M1 wrap on a random ticker
from the day's flow universe (U). The option cache holds only the strikes the
book traded, so most of those legs are not on disk, and the study prints
NOT BUILT — AWAITING SCRAPE until they are. This collector fetches them.

TARGETS (`mechanical_benchmark.fetch_targets`, IMPORTED)
--------------------------------------------------------
The strikes a pair is WAITING on: a grid strike nearer the target than any
cached listed strike, that the skip-list holds no evidence against. A fetch
can expose a nearer strike (or prove one unlisted), so the study and this
collector alternate until nothing awaits. Every run recomputes the targets
from the cache as it stands, so the loop is resumable.

ARM U also needs each universe ticker's underlying before it can name a
strike. `--list-underlying` prints the tickers with no cached contract and no
stock bars; fetch their bars first with
`scripts/collector/fetch_underlying_ohlc.py --tickers <list>`.

HOW IT FETCHES
--------------
Through `scripts.backtest.shared.history.fetch_option_histories`, the same
loop the backtest uses (the `fetch_substitute_legs.py` pattern): one Barchart
session, the `HISTORY_START_DATE` floor, the atomic cache write, the
evidence-gated skip-list and the network-outage abort (exit 6). A 404 is
recorded as unlisted there, which is what lets the study's walk step past a
strike that is not listed.

Shares the Barchart session with the backtest: never run it beside another
scrape. Needs BARCHART_EMAIL/BARCHART_PASSWORD. Research-tier, run by hand,
after the operator approves the count `--dry-run` prints (census floor 4).
Run `python3 scripts/backup_research_caches.py push` after it.

Usage:
  python3 scripts/collector/fetch_mechanical_legs.py --dry-run
  python3 scripts/collector/fetch_mechanical_legs.py --arms M1,M2 --limit 200
  python3 scripts/collector/fetch_mechanical_legs.py --list-underlying
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

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.logger import setup_logging  # noqa: E402
from scripts.backtest.helpers import _contract_key  # noqa: E402
from scripts.backtest.shared.history import (  # noqa: E402
    EXIT_NETWORK_OUTAGE, NetworkOutage, fetch_option_histories,
)
from scripts.backtest_study.f1_selection import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402

log = logging.getLogger("fetch_mechanical_legs")

ARMS = ("M1", "M2", "M2L", "U")
BACKUP_REMINDER = ("Next: python3 scripts/backup_research_caches.py push  "
                   "(the scraped cache has no other copy)")


def plan(arms: tuple[str, ...], eras: tuple[str | None, ...]):
    """`(targets, builds)` on the cache as it stands; selection only, no pricing."""
    chain = NTF.Chain()
    evidence = NTF.unlisted_evidence()
    builds = [MB.build_era(e, chain, evidence, {}, price=False) for e in eras]
    return MB.fetch_targets(builds, arms), builds


def to_contracts(targets: list[dict]) -> list[dict]:
    """`fetch_option_histories`'s contract dicts."""
    return [dict(key=_contract_key(t["ticker"], t["opt_type"], t["strike"],
                                   t["expiration"].isoformat()),
                 symbol=t["ticker"], opt_type=t["opt_type"], strike=t["strike"],
                 expiration=t["expiration"])
            for t in targets]


async def fetch(targets: list[dict], headless: bool, timeout_ms: int) -> int:
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
                    help="Print the contract count by arm; no network.")
    ap.add_argument("--list", action="store_true",
                    help="With --dry-run, also print every contract.")
    ap.add_argument("--list-underlying", action="store_true",
                    help="Print the ARM U tickers with no underlying known, "
                         "comma-separated, and exit.")
    ap.add_argument("--arms", default=",".join(ARMS),
                    help="Comma list of M1,M2,M2L,U (default all).")
    ap.add_argument("--no-v3", action="store_true", help="Primary era only.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Fetch at most N contracts this run (resumable).")
    ap.add_argument("--no-headless", action="store_true", help="Visible browser.")
    ap.add_argument("--timeout-ms", type=int, default=15000)
    args = ap.parse_args(argv)

    arms = tuple(a.strip().upper() for a in args.arms.split(",") if a.strip())
    bad = [a for a in arms if a not in ARMS]
    if bad:
        ap.error(f"unknown arm(s) {bad}; choose from {ARMS}")
    eras = (None,) if args.no_v3 else (None, "v3")
    targets, builds = plan(arms, eras)

    if args.list_underlying:
        print(",".join(MB.tickers_without_underlying(builds)))
        return 0

    todo = targets if args.limit is None else targets[:args.limit]
    by = Counter(t["category"] for t in targets)
    cats = "  ".join(f"{k}={v}" for k, v in sorted(by.items()))
    print(f"unique uncached call contracts to fetch: {len(targets)}  {cats}")
    if args.limit is not None:
        print(f"this run fetches at most {args.limit}")
    if args.dry_run:
        if args.list:
            for t in todo:
                print(f"  {t['ticker']:<6} {t['expiration'].isoformat()} "
                      f"{t['strike']:>9.2f}C  {t['category']}")
        print("[dry-run] nothing fetched")
        print(BACKUP_REMINDER)
        return 0
    if not todo:
        print("Nothing to fetch.")
        return 0
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
