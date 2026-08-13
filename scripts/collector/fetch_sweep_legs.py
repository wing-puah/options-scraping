"""
Resumable fetcher for the option-history legs the `calendar_hedge --arm S`
structure sweep needs and doesn't have yet.

WHY THIS EXISTS
---------------
`vol_sleeve` (2026-08-12) showed the option cache only carries the legs the
book actually traded — directional verticals, almost entirely. A calendar
or diagonal sweep needs the FAR-expiry leg and, for a diagonal, an
off-strike far leg; an iron-condor sweep needs both wing strikes at the
near expiry. None of that exists in the cache unless it happens to overlap
a leg the book itself entered. This collector derives exactly the missing
contracts a put-calendar / put-diagonal / iron-condor sweep anchored on the
book's own (ticker, expiry, spot) entries would need, and fetches them.

TARGET DERIVATION (`sweep_targets` / `sweep_target_records`)
--------------------------------------------------------------
Every (ticker, expiry) the pooled book (`scripts.backtest_study.book.load_book`,
`include_bs=False`) entered a leg into is one "near" anchor, with K* = the
cached strike nearest that entry's spot (preferring a strike with BOTH a
call and a put cached, since that is the flow-truth strike the book traded
around; falling back to the nearest strike of any type if no cached pair
exists). From that anchor:

  put_calendar   the put at K*, near expiry AND next-later expiry (the
                 first later expiry with a CALL already cached at K* — that
                 call is the evidence the strike is listed there at all)
  put_diagonal   the put at the nearest cached strike BELOW K*, at that
                 same far expiry (only if a call is cached there, put isn't)
  condor_wing    at the near expiry, whichever of {call, put} is missing at
                 the nearest cached strike above K* and the nearest cached
                 strike below K*

A strike/expiry combo is only ever a target if SOME option is already
cached there (never invent a strike that may not be listed on the chain),
and a contract already cached is never a target. This mirrors
`fetch_counterpart_history.py`'s discipline of anchoring every fetch to
real, already-observed chain structure.

WHERE IT WRITES
----------------
`backtests/option_history_cache/` under the EXISTING
`{TICKER}_{YYYYMMDD}_{STRIKE}{C|P}.csv` convention (`lib.barchart.options.cache_path`)
— the same cache `fetch_counterpart_history.py`, `simulate.py`, `harness.py`
and the study tier already read. Nothing downstream needs a code change.

RESUMABILITY
------------
`backtests/sweep_cache/legs_manifest.csv` tracks one row per target contract
(`status`: pending / fetched / failed). Every fetch attempt writes its CSV
to the cache and flushes the manifest IMMEDIATELY, so a crash loses at most
the in-flight contract. `--dry-run` (re)computes targets and writes the
manifest without fetching; re-running it never clobbers a fetched/failed
row's status, only adds newly-derived pending rows and refreshes existing
pending ones. `--limit N` caps fetch ATTEMPTS per run (a cache hit found via
skip-existing doesn't count against the budget) for interruption-safe
chunking. `--retry-failed` additionally attempts rows already marked
failed (skipped by default, so one bad contract doesn't get re-hit every
run).

Needs BARCHART_EMAIL/BARCHART_PASSWORD for an actual fetch. Research-tier,
run by hand — not scheduled, not imported by production.

Usage:
  python3 scripts/collector/fetch_sweep_legs.py --dry-run
  python3 scripts/collector/fetch_sweep_legs.py --limit 200
  python3 scripts/collector/fetch_sweep_legs.py --limit 200 --retry-failed
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.barchart import BarchartSession  # noqa: E402
from lib.barchart.options import (  # noqa: E402
    cache_path, option_history_url, parse_history_details,
)
from lib.logger import safe_err, setup_logging  # noqa: E402
from lib.parsing import to_float  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest_study.book import load_book  # noqa: E402
from scripts.backtest_study.vol_sleeve import _strike_index, paired_strikes  # noqa: E402

log = logging.getLogger("fetch_sweep_legs")

MANIFEST_PATH = ROOT / "backtests" / "sweep_cache" / "legs_manifest.csv"
MANIFEST_FIELDS = ("ticker", "expiration", "strike", "opt_type", "category",
                   "status", "fetched_at", "reason")

TYPE_NAME = {"C": "Call", "P": "Put"}

# A contract that never traded returns a valid CSV with a header and nothing
# else; writing that would satisfy "this exists" forever while pricing
# nothing (same guard as fetch_counterpart_history.py).
MIN_USABLE_BARS = 2

_DEFAULT_COOKIES = str(ROOT / "cookies" / "barchart_session.json")


# ─── Target derivation ─────────────────────────────────────────────────────────

def entered_groups(records: list[dict]) -> dict[tuple[str, date], float]:
    """`{(ticker, expiry): spot}` over every leg every pooled-book record entered.

    `spot` is the MEDIAN of the entering record(s)' `entry_underlying` when more
    than one record touches the same (ticker, expiry) — deterministic, and not
    swayed by whichever record happened to be iterated last. Records with a
    missing or non-positive spot are skipped entirely (their legs contribute no
    group), per the task's "skip missing spot" rule.
    """
    spots: dict[tuple[str, date], list[float]] = {}
    for rec in records:
        t = rec.get("t") if isinstance(rec, dict) else None
        if t is None:
            continue
        spot = to_float(t.row.get("entry_underlying"))
        if spot is None or spot <= 0:
            continue
        for leg in t.legs:
            key = (leg.ticker.upper(), leg.expiration)
            spots.setdefault(key, []).append(spot)
    out = {}
    for key, vals in spots.items():
        vals = sorted(vals)
        n = len(vals)
        mid = n // 2
        out[key] = vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2
    return out


def _k_star(idx: dict, ticker: str, expiry: date, spot: float) -> float | None:
    """Nearest paired (call+put cached) strike to spot, else nearest cached
    strike of any type; None if nothing at all is cached for this expiry."""
    near_idx = idx.get((ticker, expiry), {})
    if not near_idx:
        return None
    paired = paired_strikes(idx, ticker, expiry)
    pool = paired if paired else list(near_idx)
    return min(pool, key=lambda k: abs(k - spot))


def _later_call_expiry(idx: dict, ticker: str, near_expiry: date, k_star: float) -> date | None:
    """First expiry after `near_expiry`, among every expiry cached for this
    ticker, with a CALL already cached at `k_star` — the evidence that the
    strike is listed there at all. None if no such expiry exists (never
    invent one)."""
    ticker_expiries = sorted({exp for (tk, exp) in idx if tk == ticker})
    for exp in ticker_expiries:
        if exp > near_expiry and "C" in idx.get((ticker, exp), {}).get(k_star, set()):
            return exp
    return None


def _targets_for_group(ticker: str, near_expiry: date, spot: float, idx: dict) -> list[dict]:
    """The put_calendar / put_diagonal / condor_wing targets anchored on one
    (ticker, near_expiry, spot) entry — see module docstring for the rules."""
    out: list[dict] = []
    near_idx = idx.get((ticker, near_expiry), {})
    if not near_idx:
        return out  # nothing cached for this expiry at all; no anchor

    k_star = _k_star(idx, ticker, near_expiry, spot)
    if k_star is None:
        return out

    far_expiry = _later_call_expiry(idx, ticker, near_expiry, k_star)

    if far_expiry is not None:
        # -- put_calendar: put at K* on the near AND far leg of the calendar --
        if "P" not in near_idx.get(k_star, set()):
            out.append(dict(ticker=ticker, expiration=near_expiry, strike=k_star,
                            opt_type="P", category="put_calendar"))
        far_idx = idx.get((ticker, far_expiry), {})
        if "P" not in far_idx.get(k_star, set()):
            out.append(dict(ticker=ticker, expiration=far_expiry, strike=k_star,
                            opt_type="P", category="put_calendar"))

        # -- put_diagonal: far leg at the nearest cached strike BELOW K* --
        below = [k for k in far_idx if k < k_star]
        if below:
            k_below = max(below)
            cps = far_idx[k_below]
            if "C" in cps and "P" not in cps:
                out.append(dict(ticker=ticker, expiration=far_expiry, strike=k_below,
                                opt_type="P", category="put_diagonal"))

    # -- condor_wing: nearest cached strikes above/below K* at the near expiry --
    above = [k for k in near_idx if k > k_star]
    below_near = [k for k in near_idx if k < k_star]
    wings = []
    if above:
        wings.append(min(above))
    if below_near:
        wings.append(max(below_near))
    for k in wings:
        cps = near_idx[k]
        if "C" not in cps:
            out.append(dict(ticker=ticker, expiration=near_expiry, strike=k,
                            opt_type="C", category="condor_wing"))
        if "P" not in cps:
            out.append(dict(ticker=ticker, expiration=near_expiry, strike=k,
                            opt_type="P", category="condor_wing"))

    return out


def sweep_target_records(records: list[dict] | None = None,
                         idx: dict | None = None) -> list[dict]:
    """Every missing contract the sweep needs, deduplicated, with its category.

    `records` defaults to `load_book(include_bs=False)`'s records; `idx`
    defaults to a fresh scan of the option cache (`_strike_index`). Both are
    injectable so target derivation can be tested against a synthetic cache/
    book without touching the real ones.
    """
    if records is None:
        records, _diag = load_book(include_bs=False)
    if idx is None:
        idx = _strike_index()

    seen: dict[tuple, dict] = {}
    for (ticker, near_expiry), spot in entered_groups(records).items():
        for r in _targets_for_group(ticker, near_expiry, spot, idx):
            key = (r["ticker"], r["expiration"], r["strike"], r["opt_type"])
            seen.setdefault(key, r)
    return sorted(seen.values(),
                 key=lambda r: (r["ticker"], r["expiration"], r["strike"], r["opt_type"]))


def sweep_targets(records: list[dict] | None = None,
                  idx: dict | None = None) -> list[tuple[str, date, float, str]]:
    """`[(ticker, expiration, strike, opt_type)]`, sorted — the plain target list."""
    return [(r["ticker"], r["expiration"], r["strike"], r["opt_type"])
            for r in sweep_target_records(records, idx)]


# ─── Cache path (mirrors fetch_counterpart_history.py's contract_path) ────────

def contract_path(target: tuple) -> Path:
    ticker, expiration, strike, opt_type = target
    return cache_path(HISTORY_CACHE, ticker, expiration, strike, TYPE_NAME[opt_type])


# ─── Manifest I/O ───────────────────────────────────────────────────────────────

def _key(ticker: str, expiration, strike, opt_type: str) -> tuple:
    exp = expiration if isinstance(expiration, str) else expiration.isoformat()
    return (ticker.upper(), exp, f"{float(strike):.2f}", opt_type)


def _row_from_target(r: dict) -> dict:
    return dict(ticker=r["ticker"], expiration=r["expiration"].isoformat(),
               strike=f"{r['strike']:.2f}", opt_type=r["opt_type"],
               category=r["category"], status="pending", fetched_at="", reason="")


def target_of_row(row: dict) -> tuple:
    return (row["ticker"], date.fromisoformat(row["expiration"]), float(row["strike"]),
           row["opt_type"])


def load_manifest(path: Path) -> dict[tuple, dict]:
    if not path.exists():
        return {}
    out = {}
    with open(path) as fh:
        for row in csv.DictReader(fh):
            k = _key(row["ticker"], row["expiration"], row["strike"], row["opt_type"])
            out[k] = {f: row.get(f, "") or "" for f in MANIFEST_FIELDS}
    return out


def write_manifest(path: Path, rows: dict[tuple, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({f: rows[k].get(f, "") for f in MANIFEST_FIELDS})
    tmp.replace(path)  # atomic on the same filesystem: never a half-written manifest on disk


def merge_manifest(existing: dict[tuple, dict], target_records: list[dict]) -> dict[tuple, dict]:
    """Add newly-derived targets as pending rows; refresh existing PENDING rows
    (category may have changed); NEVER touch a fetched/failed row's status —
    that is the whole resumability contract."""
    merged = dict(existing)
    for r in target_records:
        k = _key(r["ticker"], r["expiration"], r["strike"], r["opt_type"])
        if k not in merged or merged[k].get("status") not in ("fetched", "failed"):
            merged[k] = _row_from_target(r)
    return merged


def sync_cache_status(rows: dict[tuple, dict]) -> int:
    """Any non-fetched row whose cache file already exists (any source — a
    manual fetch, a run of `fetch_counterpart_history.py`, whatever) is marked
    fetched WITHOUT a request. Returns how many rows were upgraded."""
    n = 0
    for row in rows.values():
        if row.get("status") == "fetched":
            continue
        if contract_path(target_of_row(row)).exists():
            row["status"] = "fetched"
            row["reason"] = ""
            if not row.get("fetched_at"):
                row["fetched_at"] = "pre-existing"
            n += 1
    return n


# ─── Scrape ──────────────────────────────────────────────────────────────────────

async def _fetch_one(session, target: tuple, timeout_ms: int) -> str | None:
    ticker, expiration, strike, opt_type = target
    try:
        return await session.fetch_history_fast(
            option_history_url(ticker, expiration, strike, TYPE_NAME[opt_type]), timeout_ms)
    except Exception as e:
        log.error("history scrape failed for %s: %s", contract_path(target).stem, safe_err(e))
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def run_fetch(rows: dict[tuple, dict], manifest_path: Path, *, limit: int | None = None,
                    retry_failed: bool = False, headless: bool = True, timeout_ms: int = 30000,
                    sleep_s: float = 0.4, session=None) -> dict:
    """Fetch every pending (and, if `retry_failed`, failed) row, writing each
    contract's CSV to the cache and flushing the manifest IMMEDIATELY after —
    so a crash mid-run loses at most the in-flight contract, and a re-run with
    the same manifest resumes exactly where this one stopped.

    `limit` caps fetch ATTEMPTS (an actual network call); a row resolved via
    skip-existing costs nothing against it.
    """
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    sync_cache_status(rows)
    write_manifest(manifest_path, rows)

    wanted = {"pending", ""} | ({"failed"} if retry_failed else set())
    pending = sorted(k for k, r in rows.items() if r.get("status", "pending") in wanted)
    stats = Counter()

    async def run(sess) -> None:
        attempts = 0
        for i, k in enumerate(pending, 1):
            if limit is not None and attempts >= limit:
                log.info("--limit %d reached — %d targets left for a later run",
                         limit, len(pending) - i + 1)
                break
            row = rows[k]
            target = target_of_row(row)
            name = contract_path(target).stem
            path = contract_path(target)
            if path.exists():
                row["status"], row["fetched_at"], row["reason"] = "fetched", _now_iso(), ""
                stats["skip_existing"] += 1
                write_manifest(manifest_path, rows)
                continue

            attempts += 1
            csv_text = await _fetch_one(sess, target, timeout_ms)
            if not csv_text:
                row["status"], row["reason"] = "failed", "no data"
                stats["failed"] += 1
                log.warning("[%d] %s: no data", attempts, name)
                write_manifest(manifest_path, rows)
                continue
            try:
                details = parse_history_details(csv_text, require_mark=False)
            except Exception as e:
                row["status"], row["reason"] = "failed", f"unparseable ({safe_err(e)})"
                stats["failed"] += 1
                log.warning("[%d] %s: unparseable (%s)", attempts, name, safe_err(e))
                write_manifest(manifest_path, rows)
                continue
            if len(details) < MIN_USABLE_BARS:
                row["status"], row["reason"] = "failed", "no bars (never traded)"
                stats["no_bars"] += 1
                log.info("[%d] %s: no bars — not written", attempts, name)
                write_manifest(manifest_path, rows)
                continue

            path.write_text(csv_text)
            row["status"], row["fetched_at"], row["reason"] = "fetched", _now_iso(), ""
            stats["fetched"] += 1
            days = sorted(details)
            log.info("[%d] %s: %d bars %s..%s", attempts, name, len(details), days[0], days[-1])
            write_manifest(manifest_path, rows)
            if sleep_s:
                await asyncio.sleep(sleep_s)

    if session is not None:
        await run(session)
    else:
        email = os.getenv("BARCHART_EMAIL", "")
        password = os.getenv("BARCHART_PASSWORD", "")
        if not (email and password):
            log.error("BARCHART_EMAIL/PASSWORD not set — cannot scrape")
            return dict(stats)
        cookies_path = Path(os.getenv("COOKIES_PATH", _DEFAULT_COOKIES))
        async with BarchartSession(email, password, cookies_path, headless) as sess:
            await run(sess)
    return dict(stats)


# ─── Reporting ───────────────────────────────────────────────────────────────────

def print_summary(rows: dict[tuple, dict]) -> None:
    pending = [r for r in rows.values() if r.get("status", "pending") in ("pending", "")]
    fetched = sum(1 for r in rows.values() if r.get("status") == "fetched")
    failed = sum(1 for r in rows.values() if r.get("status") == "failed")
    by_cat = Counter(r["category"] for r in pending)
    by_ticker = Counter(r["ticker"] for r in pending)
    log.info("manifest: %d rows total  |  pending %d  fetched %d  failed %d",
             len(rows), len(pending), fetched, failed)
    log.info("pending by category: %s", "  ".join(f"{k}={v}" for k, v in sorted(by_cat.items())))
    log.info("pending by ticker (top 15): %s",
             "  ".join(f"{t}={n}" for t, n in by_ticker.most_common(15)))


# ─── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()
    # `lib.logger._OWN_LOGGERS` is a fixed allowlist in lib/ (read-only for this
    # script) that this module's name isn't on, so its INFO logs would
    # otherwise be silently dropped at the root's WARNING level.
    log.setLevel(logging.INFO)
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
    target_records = sweep_target_records(records, idx)
    log.info("derived %d distinct missing contracts from %d book records",
             len(target_records), len(records))

    existing = load_manifest(MANIFEST_PATH)
    rows = merge_manifest(existing, target_records)
    n_upgraded = sync_cache_status(rows)
    if n_upgraded:
        log.info("%d rows already covered by an existing cache file — marked fetched", n_upgraded)
    write_manifest(MANIFEST_PATH, rows)
    print_summary(rows)
    log.info("manifest: %s", MANIFEST_PATH)

    if args.dry_run:
        log.info("[dry-run] nothing fetched")
        return

    pending_n = sum(1 for r in rows.values() if r.get("status", "pending") in ("pending", ""))
    failed_n = sum(1 for r in rows.values() if r.get("status") == "failed")
    if pending_n == 0 and not (args.retry_failed and failed_n):
        log.info("Nothing to fetch.")
        return

    stats = asyncio.run(run_fetch(rows, MANIFEST_PATH, limit=args.limit,
                                  retry_failed=args.retry_failed,
                                  headless=not args.no_headless))
    log.info("done: %s", "  ".join(f"{k}={v}" for k, v in sorted(stats.items())))


if __name__ == "__main__":
    main()
