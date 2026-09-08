"""
Resumable fetcher for the FAR CALL leg `hedge_structure`'s hedge arm reads
and the option cache does not hold.

WHY THIS EXISTS
---------------
`hedge_structure` (`f5_hedging/`, Q2 of the hedge programme) builds its
calendar as `lib/sleeve_synth.build_legs("calendar")`: short the call at K* on
the near expiry the book entered, long the call at the SAME K* on the first
later expiry that already has a call at K* in the cache. K* is the paired
(call AND put cached) strike nearest the entry's spot. The cache only carries
what the book traded and what earlier collectors added, so on every `v4`
export the calendar is available on about half the deployed dates and a
third of the worst decile, and the fill gate H0 fails before the primary can
be read. Part of that gap is the far call itself: the near-expiry grid names
K*, the ticker has a later expiry cached, and no call at K* is cached there.
This collector fetches exactly that contract.

WHAT IT DOES NOT DO
-------------------
It changes no rule and invents nothing. K* comes from the near-expiry paired
grid the study already reads, and the far expiry is the ticker's FIRST cached
expiry after the near one, evidenced by any contract already in the cache at
that expiry. An anchor with no paired grid gets no target (the study could
not name K* there either — its near PUT at K* is `fetch_sweep_legs.py`'s
`put_calendar` target, not this script's). A ticker with no later expiry
cached at all gets no target. Whether the chain listed K* at that far expiry
is Barchart's to answer: a contract that never traded comes back with no
bars and is recorded `failed`, never written.

Note the moving part this creates: on an anchor where a call at K* is cached
at a LATER expiry than the ticker's first later one, the study currently
pairs with that later expiry, and after this fetch it pairs with the first —
which is what the rule asks for, but it means an already-built calendar can
change value. The post-fetch `hedge_structure` print is a new population,
not a delta on the old one (the study stamps every checkpoint row with a
per-ticker cache signature for exactly this reason).

ANCHORS (`anchors`)
-------------------
`hedge_structure.build_universe`'s loop, without its reconstruction gate:
per (date, ticker), the FIRST book record supplies the spot for each of its
leg expiries (`setdefault`, iteration order kept), so K* here is the K* the
study picks. The whole pooled book is walked, not only deployed dates: the
H arm restricts by date AFTER building the universe, so a whole-book target
set is a superset that costs fetches, not correctness.

WHERE IT WRITES / RESUMABILITY
------------------------------
Same cache, same filename convention, same manifest contract and same scrape
loop as `fetch_sweep_legs.py` — those are IMPORTED, not copied. The manifest
is its own file, `backtests/sweep_cache/far_legs_manifest.csv`, so the
`--arm S` sweep's `legs_manifest.csv` is never touched.

Needs BARCHART_EMAIL/BARCHART_PASSWORD for an actual fetch. Research-tier,
run by hand — not scheduled, not imported by production.

Usage:
  python3 scripts/collector/fetch_far_legs.py --dry-run
  python3 scripts/collector/fetch_far_legs.py --limit 200
  python3 scripts/collector/fetch_far_legs.py --limit 200 --retry-failed
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.logger import setup_logging  # noqa: E402
from lib.parsing import to_float  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.lib.sleeve_synth import (  # noqa: E402
    _strike_index, call_expiries, paired_strikes,
)
from scripts.collector.fetch_sweep_legs import (  # noqa: E402
    load_manifest, merge_manifest, print_summary, run_fetch, sync_cache_status,
    write_manifest,
)

log = logging.getLogger("fetch_far_legs")

MANIFEST_PATH = ROOT / "backtests" / "sweep_cache" / "far_legs_manifest.csv"
CATEGORY = "far_call"


# ─── Anchors: the study's universe, minus its reconstruction gate ───────────────

def anchors(records: list[dict]) -> dict[tuple[str, str, date], float]:
    """`{(date, ticker, expiry): spot}` — the first book record on a
    (date, ticker, expiry) supplies the spot, as `build_universe` does.

    A record with a missing or non-positive spot contributes nothing; the
    study drops it the same way (`no_spot`).
    """
    out: dict[tuple[str, str, date], float] = {}
    for rec in records:
        t = rec.get("t") if isinstance(rec, dict) else None
        if t is None:
            continue
        spot = to_float(t.row.get("entry_underlying"))
        if spot is None or spot <= 0:
            continue
        d, tk = str(rec.get("date", "")), str(rec.get("ticker", "")).upper()
        for leg in t.legs:
            out.setdefault((d, tk, leg.expiration), spot)
    return out


# ─── Target derivation ─────────────────────────────────────────────────────────

def first_later_expiry(idx: dict, ticker: str, near_expiry: date) -> date | None:
    """The ticker's first cached expiry after `near_expiry`, at ANY strike or
    type — the evidence the chain lists something there. None: never invent."""
    later = [exp for (tk, exp) in idx if tk == ticker and exp > near_expiry]
    return min(later) if later else None


def far_call_target(idx: dict, ticker: str, near_expiry: date,
                    spot: float) -> tuple[str, dict | None]:
    """`(why, target)` for one anchor.

    `why` is one of `no_grid` (no paired strike at the near expiry, so no K*),
    `no_later_expiry` (nothing cached for the ticker after the near one),
    `cached` (the call at K* at the first later expiry is already there) or
    `target`. Only `target` carries a record.
    """
    grid = paired_strikes(idx, ticker, near_expiry)
    if not grid:
        return "no_grid", None
    k_atm = min(grid, key=lambda k: abs(k - spot))
    far = first_later_expiry(idx, ticker, near_expiry)
    if far is None:
        return "no_later_expiry", None
    if far in call_expiries(idx, ticker, k_atm):
        return "cached", None
    return "target", dict(ticker=ticker, expiration=far, strike=k_atm,
                          opt_type="C", category=CATEGORY)


def far_call_census(records: list[dict] | None = None,
                    idx: dict | None = None) -> tuple[list[dict], Counter]:
    """Every missing far call, deduplicated and sorted, plus the per-anchor
    census the pre-run note quotes. Both inputs are injectable for tests."""
    if records is None:
        records, _diag = load_book(include_bs=False)
    if idx is None:
        idx = _strike_index()
    census: Counter = Counter()
    seen: dict[tuple, dict] = {}
    for (_d, ticker, near), spot in anchors(records).items():
        why, r = far_call_target(idx, ticker, near, spot)
        census[why] += 1
        if r is not None:
            seen.setdefault((r["ticker"], r["expiration"], r["strike"], r["opt_type"]), r)
    census["anchors"] = sum(v for k, v in census.items())
    targets = sorted(seen.values(),
                     key=lambda r: (r["ticker"], r["expiration"], r["strike"], r["opt_type"]))
    return targets, census


def far_call_target_records(records: list[dict] | None = None,
                            idx: dict | None = None) -> list[dict]:
    return far_call_census(records, idx)[0]


# ─── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()
    log.setLevel(logging.INFO)   # not on lib.logger's allowlist, same as fetch_sweep_legs
    logging.getLogger("fetch_sweep_legs").setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Recompute targets, write the manifest, fetch nothing.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Fetch at most N contracts this run (resumable).")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Also attempt rows already marked failed.")
    parser.add_argument("--no-headless", action="store_true", help="Visible browser.")
    args = parser.parse_args()

    idx = _strike_index()
    records, _diag = load_book(include_bs=False)
    target_records, census = far_call_census(records, idx)
    log.info("anchors %d: no_grid %d  no_later_expiry %d  cached %d  target %d",
             census["anchors"], census["no_grid"], census["no_later_expiry"],
             census["cached"], census["target"])
    log.info("derived %d distinct missing far calls from %d book records",
             len(target_records), len(records))

    existing = load_manifest(MANIFEST_PATH)
    rows = merge_manifest(existing, target_records)
    n_upgraded = sync_cache_status(rows)
    if n_upgraded:
        log.info("%d rows already covered by an existing cache file — marked fetched", n_upgraded)
    write_manifest(MANIFEST_PATH, rows)
    print_summary(rows)

    if args.dry_run:
        log.info("dry run — manifest written to %s, nothing fetched", MANIFEST_PATH)
        return

    stats = asyncio.run(run_fetch(rows, MANIFEST_PATH, limit=args.limit,
                                  retry_failed=args.retry_failed,
                                  headless=not args.no_headless))
    log.info("fetch stats: %s", "  ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    print_summary(rows)


if __name__ == "__main__":
    main()
