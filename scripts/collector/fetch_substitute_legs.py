"""
Fetcher for the substitute legs `narrow_to_fit`'s F3 cells need.

WHY THIS EXISTS
---------------
`narrow_to_fit` (research/pre-registrations/f4_deployment/narrow_to_fit.md,
registered 2026-10-01) narrows a spread whose one-contract max loss is over
budget: the anchor leg stays and the other leg moves inward to the widest
listed strike that fits. The option cache holds only the strikes the book
traded, so the F3 cells print AWAITING SCRAPE until the substitute strikes are
fetched. This collector fetches them.

TARGETS (`narrow_to_fit.substitute_targets`, IMPORTED)
------------------------------------------------------
Every ladder-eligible pick the `account_sim` walk can reach on the full book,
at both budgets ($500 and $1,000), whose one-contract max loss exceeds the
budget. On a debit vertical the SOLD leg moves inward; on a credit vertical
the LONG (protective) leg moves inward and the sold leg stays (operator
ruling 2).

  --scope target_wider   (default, the registration's middle census row)
                         the estimated target strike plus the next-wider one.
                         The target is a Black-Scholes ESTIMATE at the legs'
                         mean entry IV over an inferred strike grid. It decides
                         what to fetch and never prices anything.
  --scope between        every inferred grid strike between the two legs.

A contract already cached is never fetched. A contract the skip-list
(`_unlisted.jsonl`) records as unlisted is skipped only when its entry passed
the evidence gate; `seeded_from_log` entries are ignored and the contract is
fetched. The fetch itself never marks a network error, a 403 or a 5xx as
unlisted: that logic is `scripts/backtest/shared/history.py`'s and runs
unchanged.

HOW IT FETCHES
--------------
Through `scripts.backtest.shared.history.fetch_option_histories`, the same
loop the backtest uses: one Barchart session (reopened on a dead browser),
the `HISTORY_START_DATE` floor on the feed request, the sibling `Price~`
guard, an atomic stage-then-replace write into
`backtests/option_history_cache/`, the evidence-gated skip-list update and
the network-outage abort (exit 6). The skip-list filter above runs here,
before the call, and the call is made with `retry_unlisted=True` so the
loop does not re-apply its own TTL skip to the seeded entries.

RESUMABLE. The cache is the state: a re-run recomputes the targets, finds
the contracts already written and fetches only the rest. `--limit N` caps
how many contracts one run requests.

Shares the Barchart session with the backtest: never run it beside another
scrape. Needs BARCHART_EMAIL/BARCHART_PASSWORD. Research-tier, run by hand.
Run `python3 scripts/backup_research_caches.py push` after it.

Usage:
  python3 scripts/collector/fetch_substitute_legs.py --dry-run
  python3 scripts/collector/fetch_substitute_legs.py --limit 200
  python3 scripts/collector/fetch_substitute_legs.py --scope between --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
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
from scripts.backtest_study.f4_deployment import account_sim as AS  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

log = logging.getLogger("fetch_substitute_legs")

SCOPES = ("target_wider", "between")
BACKUP_REMINDER = ("Next: python3 scripts/backup_research_caches.py push  "
                   "(the scraped cache has no other copy)")


def budgets() -> tuple[float, float]:
    """The two registered budgets: account_sim's 2% and the $1,000 stop."""
    st = AS.load_settings(AS.DEFAULT_CONFIG)
    return st.budget, NTF.HIGH_BUDGET


def to_contracts(targets: list[dict]) -> list[dict]:
    """`fetch_option_histories`'s contract dicts."""
    return [dict(key=_contract_key(t["ticker"], t["opt_type"], t["strike"],
                                   t["expiration"].isoformat()),
                 symbol=t["ticker"], opt_type=t["opt_type"], strike=t["strike"],
                 expiration=t["expiration"])
            for t in targets]


def print_plan(targets: list[dict], census, scope: str, limit: int | None) -> None:
    print(f"scope {scope}: {census['candidates']} candidates on "
          f"{census['candidate_dates']} dates")
    for k in sorted(k for k in census if k.startswith("over ")):
        print(f"  {k:<58} {census[k]:>5}")
    print(f"unique uncached contracts to fetch: {len(targets)}")
    if limit is not None:
        print(f"this run fetches at most {limit}")
    for t in targets:
        cp = "C" if t["opt_type"] == "Call" else "P"
        print(f"  {t['ticker']:<6} {t['expiration'].isoformat()} {t['strike']:>9.2f}{cp}"
              f"  {t['category']}")


async def fetch(targets: list[dict], headless: bool, timeout_ms: int) -> int:
    """Fetch through the backtest's own loop; returns how many got history."""
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
                    help="Print the contract list and count; no network.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Fetch at most N contracts this run (resumable).")
    ap.add_argument("--scope", choices=SCOPES, default="target_wider",
                    help="target_wider (default): estimated target + next-wider "
                         "strike. between: every grid strike between the legs.")
    ap.add_argument("--no-headless", action="store_true", help="Visible browser.")
    ap.add_argument("--timeout-ms", type=int, default=15000)
    args = ap.parse_args(argv)

    records, _diag = load_book(include_bs=False)
    targets, census = NTF.substitute_targets(records, budgets(), scope=args.scope)
    todo = targets if args.limit is None else targets[:args.limit]
    print_plan(todo if args.dry_run else targets, census, args.scope, args.limit)
    if args.dry_run:
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
