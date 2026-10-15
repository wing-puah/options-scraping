"""
Fetcher for the call legs `mechanical_benchmark`'s counterparts need.

WHY THIS EXISTS
---------------
`mechanical_benchmark` (research/pre-registrations/f1_selection/
benchmark/mechanical_benchmark.md, accepted by default 2026-10-09) pairs every deployed
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

Which strikes an awaiting pair names is fetch ORDER only; it never changes
what the study builds (registration, resolved at build 2026-10-13):
  - M1 and ARM U: the nearest open strike to the target, one per leg.
  - M2/M2L long leg (`delta_fetch`): when known deltas straddle the target
    with at most `BRACKET_FILL` open strikes between them, all of those;
    otherwise the `DELTA_FETCH_WIDTH` open strikes nearest the estimated
    target strike (secant on the straddling deltas, else Black-Scholes from
    k*'s own delta and IV), standard-grid strikes first.
  - M2/M2L short leg (`listed_fetch`): the open strikes in walk order up to
    the first on the standard grid, at most `LISTED_BATCH`.
So a round names more than one strike per pair; the delta walks converge in
a few rounds instead of one grid step per round.

ARM SPY (`--arms SPY`) is a separate study, `spy_benchmark`
(research/pre-registrations/f1_selection/benchmark/spy_benchmark.md,
accepted by default 2026-10-14, post hoc): the M1 wrap on SPY at each deployed
pick's own expiry. Its targets come from `spy_benchmark.fetch_targets`, which
names strikes exactly as M1 does. It is not in the default `--arms` list, so
a bare run fetches what it fetched before; name it to fetch it.

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
  python3 scripts/collector/fetch_mechanical_legs.py --arms SPY --no-v3 --dry-run
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
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import spy_benchmark as SB  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402

log = logging.getLogger("fetch_mechanical_legs")

#: mechanical_benchmark's arms: the default `--arms`.
MB_ARMS = ("M1", "M2", "M2L", "U")
#: Every arm this collector can fetch; SPY is spy_benchmark's, named explicitly.
ARMS = MB_ARMS + ("SPY",)
BACKUP_REMINDER = ("Next: python3 scripts/backup_research_caches.py push  "
                   "(the scraped cache has no other copy)")


def plan(arms: tuple[str, ...], eras: tuple[str | None, ...]):
    """`(targets, builds)` on the cache as it stands; selection only, no pricing.

    `builds` are mechanical_benchmark's (empty when only SPY is asked for, so
    a SPY-only plan never walks ARM U's universe). A contract two arms name is
    listed once, under the first arm that named it."""
    chain = NTF.Chain()
    evidence = NTF.unlisted_evidence()
    mb_arms = tuple(a for a in arms if a in MB_ARMS)
    builds, targets = [], []
    if mb_arms:
        builds = [MB.build_era(e, chain, evidence, {}, price=False) for e in eras]
        targets += MB.fetch_targets(builds, mb_arms)
    if "SPY" in arms:
        spy = [SB.build_era(e, chain, evidence, {}, price=False) for e in eras]
        targets += SB.fetch_targets(spy)
    seen, out = set(), []
    for t in targets:
        key = (t["ticker"], t["expiration"], t["strike"])
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out, builds


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
    ap.add_argument("--arms", default=",".join(MB_ARMS),
                    help="Comma list of M1,M2,M2L,U,SPY (default M1,M2,M2L,U: "
                         "mechanical_benchmark's; SPY is spy_benchmark's).")
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
