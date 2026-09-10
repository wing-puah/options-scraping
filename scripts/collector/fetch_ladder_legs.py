"""
Resumable fetcher for the rolled call/put ladder-overlay contracts
`ladder_overlay`'s tranche campaign needs and doesn't have yet.

WHY THIS EXISTS
---------------
`research/pre-registrations/f3_structure/ladder_overlay.md` tests whether
rolling a short-call ladder against a book `bull_call_spread` core (plus a
naked-put alternative) beats closing the spread at the shipped §5 exits. The
ladder rolls through expiries and strikes the book never itself traded, so
almost none of it is in `backtests/option_history_cache/` yet. This collector
derives exactly the contracts the pre-registered rule implies and fetches
them, the way `fetch_financing_legs.py` does for `financed_spread`'s F1-F4.

TARGET DERIVATION
------------------
Population: every `bull_call_spread` row in the pooled book
(`scripts.backtest_study.lib.book.load_book`, `include_bs=False`, era from
`--era`, default `current` — NOT pinned to `v3` the way `financed_spread`'s
collector is, because this study runs on v4). `ladder_targets.core_of` turns
each row into a `CoreSpec` (or `None`, counted as `skip_no_core` — wrong
structure, multi-leg/multi-expiry, or no common entry day).

For each core, the CANDIDATE EXPIRY UNIVERSE is
`ladder_targets.core_expiries()`: `financed_spread.cached_ticker_expiries`
(the ticker's own cached expiry set) UNION `ladder_targets.third_fridays`
over `[entry_day, entry_day + 120d]` (the harness path cap) — a collector
must be able to name an expiry that isn't cached yet, or nothing would ever
get scraped. The POST-scrape campaign engine
(`scripts.backtest_study.lib.overlay_campaign`) passes CACHED-ONLY expiries
to the same `ladder_targets` functions, by design (§E of the approved plan) —
so a contract this collector fails to fetch reads as "not eligible" there,
never as a silent gap.

From that universe, `ladder_targets.ladder_targets()` derives, per core:

  ladder_call_t0    roll slot 0 — the 2 nearest eligible expiries at entry,
                    the 4 nearest ticker-ladder strikes strictly above the
                    core's short strike, Call
  ladder_call_roll  roll slots 1..k (`ladder_targets.roll_chain`) — same
                    strike rule, one expiry per slot
  ladder_put_short  same slots/expiries, 4 nearest strikes strictly below the
                    entry-day spot, Put (skipped when the ticker has no bar
                    on the entry day)
  ladder_put_core   one row per core: Put at the core's own (expiry, long
                    strike) — the naked-put-in-place-of-the-core alternative

Every strike comes from the ticker's OWN observed cached-ladder
(`ladder_targets.ticker_ladder`) — never an invented increment, exactly the
`fetch_financing_legs.py` convention. A target already present in the cache
is skipped (and counted, not silently dropped — `--dry-run` reports
targets / cached / missing per category).

WHERE IT WRITES
----------------
`backtests/option_history_cache/` under the EXISTING
`{TICKER}_{YYYYMMDD}_{STRIKE}{C|P}.csv` convention — the same cache every
other collector and the study tier read. Nothing downstream needs a code
change.

RESUMABILITY
------------
`backtests/sweep_cache/ladder_manifest.csv` — a SEPARATE file from
`financing_manifest.csv` / `legs_manifest.csv` / `far_legs_manifest.csv`.
Same fields (`fetch_financing_legs.MANIFEST_FIELDS`). The manifest I/O,
cache-presence split, resumable fetch loop and reporting are IMPORTED from
`fetch_financing_legs.py`, never copied — one fetch loop, four collectors.
`--dry-run` (re)computes targets and writes the manifest without fetching;
`--limit N` caps fetch ATTEMPTS per run (a cache hit costs nothing against
it); `--retry-failed` additionally attempts rows already marked failed;
`--category ladder_call_t0,ladder_put_core` restricts a run to one category
— a SELECTION filter only, it never rewrites or drops a row. `--era` picks
the book era the targets are derived from (default `current`; the study
itself may also be run with `--era v3` as a companion, per the plan).

Needs BARCHART_EMAIL/BARCHART_PASSWORD for an actual fetch. Research-tier,
run by hand — not scheduled, not imported by production.

Usage:
  python3 scripts/collector/fetch_ladder_legs.py --dry-run
  python3 scripts/collector/fetch_ladder_legs.py --category ladder_call_t0,ladder_call_roll
  python3 scripts/collector/fetch_ladder_legs.py --limit 200 --retry-failed
  python3 scripts/collector/fetch_ladder_legs.py --era v3 --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.logger import setup_logging  # noqa: E402
from scripts.backtest_study.f3_structure.financed_spread import (  # noqa: E402
    cached_ticker_expiries,
)
from scripts.backtest_study.lib import ladder_targets as LT  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.lib.sleeve_synth import _strike_index  # noqa: E402
from scripts.collector.fetch_financing_legs import (  # noqa: E402
    load_manifest, merge_manifest, print_summary, run_fetch, split_cached,
    sync_cache_status, wanted_rows, write_manifest,
)

log = logging.getLogger("fetch_ladder_legs")

MANIFEST_PATH = ROOT / "backtests" / "sweep_cache" / "ladder_manifest.csv"
ROLL_WINDOW_DAYS = 120     # the harness path cap (`Trade.grid`'s own window)
CATEGORIES = ("ladder_call_t0", "ladder_call_roll", "ladder_put_short", "ladder_put_core")

# `ladder_targets` speaks Leg's "Call"/"Put" convention; the manifest / cache
# filename convention (shared with fetch_financing_legs.py, fetch_sweep_legs.py,
# ...) is the single-letter "C"/"P". This is the one conversion boundary.
_OPT_CODE = {"Call": "C", "Put": "P"}


# ─── Target derivation ─────────────────────────────────────────────────────────

def core_expiries(ticker: str, entry_day: date) -> list[date]:
    """The pre-scrape candidate expiry universe for one core: every expiry the
    ticker already has ANY cached contract at, union the standard third-Friday
    monthlies out to the 120-day path cap. Never invents a strike; an invented
    EXPIRY is unavoidable here only because a collector's whole job is to name
    a contract that isn't cached yet — the post-scrape campaign engine passes
    cached-only expiries to the same `ladder_targets` functions instead."""
    cached = set(cached_ticker_expiries(ticker))
    monthly = set(LT.third_fridays(entry_day, entry_day + timedelta(days=ROLL_WINDOW_DAYS)))
    return sorted(cached | monthly)


def ladder_target_records(records: list[dict] | None = None,
                          era: str = "current") -> tuple[list[dict], Counter]:
    """Every ladder-overlay target contract, deduplicated and manifest-shaped
    (`opt_type` already "C"/"P"), plus the per-core derivation census.

    Census keys: `population` (bull_call_spread rows), `skip_no_core`
    (`ladder_targets.core_of` returned `None`), `no_eligible_expiry` (a core
    with nothing in `ladder_targets.eligible_expiries` at entry — it still
    contributes its unconditional `ladder_put_core` row), `targeted` (every
    core that reached target derivation).

    `records` is injectable for tests; `era` is read only when `records` is
    `None` (the CLI's own `load_book` call already applies it otherwise).
    """
    if records is None:
        records, _diag = load_book(include_bs=False, era=era)
    census: Counter = Counter()
    seen: dict[tuple, dict] = {}
    ladder_cache: dict[str, list[float]] = {}

    for rec in records:
        if rec.get("structure") != "bull_call_spread":
            continue
        census["population"] += 1
        core = LT.core_of(rec)
        if core is None:
            census["skip_no_core"] += 1
            continue

        remaining = (core.expiry - core.entry_day).days
        expiries = core_expiries(core.ticker, core.entry_day)
        if remaining <= 0 or not LT.eligible_expiries(core.entry_day, remaining, expiries):
            census["no_eligible_expiry"] += 1

        if core.ticker not in ladder_cache:
            ladder_cache[core.ticker] = LT.ticker_ladder(core.ticker)
        census["targeted"] += 1

        for r in LT.ladder_targets(core, expiries, ladder_cache[core.ticker]):
            row = dict(ticker=r["ticker"], expiration=r["expiration"], strike=r["strike"],
                       opt_type=_OPT_CODE[r["opt_type"]], category=r["category"])
            key = (row["ticker"], row["expiration"], row["strike"], row["opt_type"])
            seen.setdefault(key, row)

    out = sorted(seen.values(), key=lambda r: (r["ticker"], r["expiration"], r["strike"], r["opt_type"]))
    return out, census


# ─── Reporting ───────────────────────────────────────────────────────────────

def print_ladder_census(target_records: list[dict], cached: list[dict],
                        missing: list[dict], census: Counter, era: str) -> None:
    n_tickers = len({r["ticker"] for r in target_records})
    log.info("ladder target census (era=%s): population %d bull_call_spread cores -> "
             "skip_no_core %d, no_eligible_expiry %d, targeted %d",
             era, census["population"], census["skip_no_core"],
             census["no_eligible_expiry"], census["targeted"])
    log.info("  %d distinct targets across %d tickers", len(target_records), n_tickers)
    log.info("  cached %d  |  missing %d", len(cached), len(missing))
    by_cat_targets = Counter(r["category"] for r in target_records)
    by_cat_cached = Counter(r["category"] for r in cached)
    by_cat_missing = Counter(r["category"] for r in missing)
    log.info("  targets by category: %s",
             "  ".join(f"{k}={v}" for k, v in sorted(by_cat_targets.items())) or "none")
    log.info("  cached by category:  %s",
             "  ".join(f"{k}={v}" for k, v in sorted(by_cat_cached.items())) or "none")
    log.info("  missing by category: %s",
             "  ".join(f"{k}={v}" for k, v in sorted(by_cat_missing.items())) or "none")


# ─── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()
    log.setLevel(logging.INFO)   # not on lib.logger's allowlist, same as fetch_financing_legs
    logging.getLogger("fetch_financing_legs").setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Recompute targets, write the manifest, fetch nothing.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Fetch at most N contracts this run (resumable).")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Also attempt rows already marked failed.")
    parser.add_argument("--category", default=None,
                        help="Comma-separated manifest categories to fetch "
                             f"({', '.join(CATEGORIES)}). Default: all. Targets "
                             "are derived and written for every category "
                             "regardless — this only selects what THIS run fetches.")
    parser.add_argument("--era", default="current",
                        help="Book era to derive ladder targets from (default: current).")
    parser.add_argument("--no-headless", action="store_true", help="Visible browser.")
    args = parser.parse_args()

    idx = _strike_index()
    target_records, census = ladder_target_records(era=args.era)
    cached, missing = split_cached(target_records, idx)
    print_ladder_census(target_records, cached, missing, census, args.era)

    existing = load_manifest(MANIFEST_PATH)
    rows = merge_manifest(existing, missing)
    n_upgraded = sync_cache_status(rows)
    if n_upgraded:
        log.info("%d rows already covered by an existing cache file — marked fetched", n_upgraded)
    write_manifest(MANIFEST_PATH, rows)
    print_summary(rows)
    log.info("manifest: %s", MANIFEST_PATH)

    if args.dry_run:
        log.info("[dry-run] nothing fetched")
        return

    cats = ({c.strip() for c in args.category.split(",") if c.strip()}
            if args.category else None)
    if cats:
        log.info("category filter: %s", "  ".join(sorted(cats)))
    todo = wanted_rows(rows, retry_failed=args.retry_failed, categories=cats)
    if not todo:
        log.info("Nothing to fetch.")
        return

    stats = asyncio.run(run_fetch(rows, MANIFEST_PATH, limit=args.limit,
                                  retry_failed=args.retry_failed,
                                  headless=not args.no_headless,
                                  categories=cats))
    log.info("done: %s", "  ".join(f"{k}={v}" for k, v in sorted(stats.items())))


if __name__ == "__main__":
    main()
