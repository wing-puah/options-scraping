"""
Resumable fetcher for the option-history legs the `financed_spread` structure
study needs and doesn't have yet.

WHY THIS EXISTS
---------------
`research/pre-registrations/f3_structure/financed_spread.md` tests whether wrapping a book
debit vertical in a FINANCING credit position (opposite-delta credit spread,
naked short leg, same-direction credit vertical — arms F1/F2/F3) improves the
outcome. Those financing legs are, almost always, contracts the book never
itself traded, so they aren't in `backtests/option_history_cache/` yet. This
collector derives exactly the missing contracts the study's frozen strike
rule implies and fetches them.

TARGET DERIVATION (`financing_target_records` / `financing_targets`)
----------------------------------------------------------------------
Pre-registered exactly (§Anti-tuning of `financed_spread.md` — not tunable
here). For every `(ticker, expiry)` pair the pooled book
(`scripts.backtest_study.lib.book.load_book`, `include_bs=False`, pinned to
`--era v3` — the study's PRIMARY basis) entered a leg into, the row-group is
every leg any book record entered at that `(ticker, expiry)`; `lo`/`hi` are
that row-group's lowest/highest leg strike (`leg_strike_groups`).

The candidate strikes come from the TICKER'S OWN observed cached strike
ladder — the union of every strike already cached for that ticker, across
ALL expiries and both option types (`ticker_ladder`) — never an invented
increment. From that ladder:

  fin_call_above   the 2 nearest ladder strikes STRICTLY ABOVE `hi`, Call
  fin_put_below    the 2 nearest ladder strikes STRICTLY BELOW `lo`, Put

both at the row-group's OWN expiry (every financing leg shares the debit's
expiry — plan-time measurement: 780/795 book rows are two-leg single-expiry).
A target already present in the cache is skipped (and counted, not silently
dropped — the dry-run census reports targets / cached / missing).

DIAGONAL TARGETS (`diag_target_records`) — AMENDMENT 1
------------------------------------------------------
ARM F4 (`financed_spread.md` §AMENDMENT 1) sells ONE short-dated leg at a
NEARER expiry than the debit, so its contracts are not merely un-traded, they
are at an expiry the book never touched at all. Derivation, per BOOK ROW (not
per (ticker, expiry) group — the window is anchored on the row's own entry
session and its own DTE):

  near expiry   the nearest expiry in the TICKER'S CACHED EXPIRY SET
                (`ticker_expiries` — union over all cached strikes/types) that
                is >= 7 calendar days after the row's entry session AND
                <= 1/2 the debit's DTE at entry. A row with nothing in that
                window is counted `no_near_expiry` and targeted with nothing.
  fin_diag_call  bull base: the 4 nearest ladder strikes strictly ABOVE the
                 debit's highest leg strike, Call, AT THE NEAR EXPIRY
  fin_diag_put   bear base: the 4 nearest ladder strikes strictly BELOW the
                 debit's lowest leg strike, Put, AT THE NEAR EXPIRY

The window rule itself is NOT re-implemented here: `near_expiry_for` is
imported from the study module that owns the frozen construction, so the
scrape and the study can never disagree about which expiry a row is owed. The
strike ladder is the same observed `ticker_ladder` the vertical targets use —
never an invented increment, at either expiry.

These rows go into the SAME manifest under new categories; a diagonal target
that collides with an already-derived vertical target is left alone rather
than relabelled, so existing manifest rows are untouched.

WHERE IT WRITES
----------------
`backtests/option_history_cache/` under the EXISTING
`{TICKER}_{YYYYMMDD}_{STRIKE}{C|P}.csv` convention (`lib.barchart.options.cache_path`)
— the same cache `fetch_sweep_legs.py`, `fetch_counterpart_history.py`,
`simulate.py`, `harness.py` and the study tier already read. Nothing
downstream needs a code change.

RESUMABILITY
------------
`backtests/sweep_cache/financing_manifest.csv` — a SEPARATE file from
`legs_manifest.csv` (`calendar_hedge --arm S` depends on that one; this
collector never reads or writes it). Same fields (ticker, expiration, strike,
opt_type, category, status, fetched_at, reason). Every fetch attempt writes
its CSV to the cache and flushes the manifest IMMEDIATELY, so a crash loses
at most the in-flight contract. `--dry-run` (re)computes targets and writes
the manifest without fetching; re-running it never clobbers a fetched/failed
row's status, only adds newly-derived pending rows and refreshes existing
pending ones. The DEFAULT run processes every pending target to completion
in one invocation: the manifest is flushed after every attempt, so an
interrupted run resumes exactly where it stopped and a done row is never
re-fetched. `--limit N` is an OPTIONAL cap on fetch ATTEMPTS per run (a cache
hit found via skip-existing doesn't count against the budget) for when a
deliberately small chunk is wanted. `--retry-failed` additionally attempts rows already marked
failed (skipped by default, so one bad contract doesn't get re-hit every
run). `--category fin_diag_call,fin_diag_put` restricts a run to one arm's
targets: the manifest is shared across arms and a closed arm's leftover
pending rows would otherwise eat the fetch budget of the live one. It is a
SELECTION filter only — it never rewrites, drops or re-derives a row.

Needs BARCHART_EMAIL/BARCHART_PASSWORD for an actual fetch. Research-tier,
run by hand — not scheduled, not imported by production.

Usage:
  python3 scripts/collector/fetch_financing_legs.py --dry-run
  python3 scripts/collector/fetch_financing_legs.py --category fin_diag_call,fin_diag_put
  python3 scripts/collector/fetch_financing_legs.py --category fin_diag_call,fin_diag_put --retry-failed
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import sys
from collections import Counter, defaultdict
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
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.f3_structure import bear_rewrap as BR  # noqa: E402
from scripts.backtest_study.f3_structure.financed_spread import (  # noqa: E402
    DIAG_N_CANDIDATES, near_expiry_for, population,
)
from scripts.backtest_study.f3_structure.vol_sleeve import _strike_index  # noqa: E402

log = logging.getLogger("fetch_financing_legs")

# Pinned to the study's PRIMARY basis (financed_spread.md §Population and
# basis) — never the caller's ambient STUDY_ERA. A financing target derived
# off a different era's book would anchor on a population this study never
# runs against.
ERA = "v3"

MANIFEST_PATH = ROOT / "backtests" / "sweep_cache" / "financing_manifest.csv"
MANIFEST_FIELDS = ("ticker", "expiration", "strike", "opt_type", "category",
                   "status", "fetched_at", "reason")

TYPE_NAME = {"C": "Call", "P": "Put"}

# A contract that never traded returns a valid CSV with a header and nothing
# else; writing that would satisfy "this exists" forever while pricing
# nothing (same guard as fetch_sweep_legs.py / fetch_counterpart_history.py).
MIN_USABLE_BARS = 2

_DEFAULT_COOKIES = str(ROOT / "cookies" / "barchart_session.json")


# ─── Target derivation ─────────────────────────────────────────────────────────

def leg_strike_groups(records: list[dict]) -> dict[tuple[str, date], tuple[float, float]]:
    """`{(ticker, expiry): (lowest_leg_strike, highest_leg_strike)}` over every
    leg every pooled-book record entered — the row-group each financing
    target is anchored on (financed_spread.md's "row-group's highest/lowest
    leg strike")."""
    groups: dict[tuple[str, date], list[float]] = defaultdict(list)
    for rec in records:
        t = rec.get("t") if isinstance(rec, dict) else None
        if t is None:
            continue
        for leg in t.legs:
            groups[(leg.ticker.upper(), leg.expiration)].append(leg.strike)
    return {key: (min(strikes), max(strikes)) for key, strikes in groups.items()}


def ticker_ladder(idx: dict) -> dict[str, list[float]]:
    """`{ticker: sorted strikes}` — the union of every strike already cached
    for that ticker across ALL expiries and both option types. This is the
    ticker's OWN observed strike ladder; a target strike always comes from
    here, never an invented increment."""
    out: dict[str, set] = defaultdict(set)
    for (ticker, _exp), strikes in idx.items():
        out[ticker].update(strikes)
    return {t: sorted(s) for t, s in out.items()}


def _candidates_for_group(ticker: str, expiry: date, lo: float, hi: float,
                          ladder: list[float]) -> list[dict]:
    """The (up to) 2 nearest ladder strikes strictly above `hi` (Call,
    fin_call_above) and strictly below `lo` (Put, fin_put_below) — before any
    cache-presence filtering, so this is the raw census unit."""
    out: list[dict] = []
    above = sorted(k for k in ladder if k > hi)[:2]
    for k in above:
        out.append(dict(ticker=ticker, expiration=expiry, strike=k, opt_type="C",
                        category="fin_call_above"))
    below = sorted((k for k in ladder if k < lo), reverse=True)[:2]
    for k in below:
        out.append(dict(ticker=ticker, expiration=expiry, strike=k, opt_type="P",
                        category="fin_put_below"))
    return out


def financing_target_records(records: list[dict] | None = None,
                             idx: dict | None = None) -> list[dict]:
    """Every candidate financing contract, deduplicated, with its category —
    BEFORE cache-presence filtering (`split_cached` does that). See the
    module docstring for the derivation rule.

    `records` defaults to `load_book(include_bs=False, era="v3")`'s records;
    `idx` defaults to a fresh scan of the option cache (`_strike_index`).
    Both are injectable so target derivation can be tested against a
    synthetic cache/book without touching the real ones.
    """
    if records is None:
        records, _diag = load_book(include_bs=False, era=ERA)
    if idx is None:
        idx = _strike_index()
    ladder = ticker_ladder(idx)

    seen: dict[tuple, dict] = {}
    for (ticker, expiry), (lo, hi) in leg_strike_groups(records).items():
        for r in _candidates_for_group(ticker, expiry, lo, hi, ladder.get(ticker, [])):
            key = (r["ticker"], r["expiration"], r["strike"], r["opt_type"])
            seen.setdefault(key, r)
    return sorted(seen.values(),
                 key=lambda r: (r["ticker"], r["expiration"], r["strike"], r["opt_type"]))


def financing_targets(records: list[dict] | None = None,
                      idx: dict | None = None) -> list[tuple[str, date, float, str]]:
    """`[(ticker, expiration, strike, opt_type)]`, sorted — the plain target
    list, BEFORE cache-presence filtering."""
    return [(r["ticker"], r["expiration"], r["strike"], r["opt_type"])
            for r in financing_target_records(records, idx)]


# ─── Diagonal target derivation (ARM F4, amendment 1) ─────────────────────────

def ticker_expiries(idx: dict) -> dict[str, list[date]]:
    """`{ticker: sorted expiries}` — every expiry the ticker has ANY cached
    contract at, across all strikes and both option types. This is "the
    ticker's cached expiry set" the F4 near-expiry window is drawn from: a near
    expiry is no more invented than a strike is."""
    out: dict[str, set] = defaultdict(set)
    for ticker, exp in idx:
        out[ticker].add(exp)
    return {t: sorted(e) for t, e in out.items()}


def _diag_candidates_for_row(ticker: str, near_exp: date, outer: float,
                             dirn: str, ladder: list[float]) -> list[dict]:
    """The DIAG_N_CANDIDATES nearest ladder strikes STRICTLY beyond `outer`, in
    the OTM direction, at `near_exp`. Calls above for a bull base
    (`fin_diag_call`), puts below for a bear base (`fin_diag_put`). Fewer than
    DIAG_N_CANDIDATES on the ladder yields fewer targets — never a fabricated
    strike to round the count up."""
    if dirn == "bull":
        ks = sorted(k for k in ladder if k > outer)[:DIAG_N_CANDIDATES]
        cp, cat = "C", "fin_diag_call"
    else:
        ks = sorted((k for k in ladder if k < outer),
                    reverse=True)[:DIAG_N_CANDIDATES]
        cp, cat = "P", "fin_diag_put"
    return [dict(ticker=ticker, expiration=near_exp, strike=k, opt_type=cp,
                 category=cat) for k in ks]


def diag_target_records(records: list[dict] | None = None,
                        idx: dict | None = None) -> tuple[list[dict], Counter]:
    """`(target records, census)` for the F4 diagonal legs, deduplicated and
    BEFORE cache-presence filtering.

    The unit is the BOOK ROW, not the (ticker, expiry) group: the near-expiry
    window is anchored on the row's own entry session and its own DTE, so two
    rows on the same (ticker, expiry) can legitimately be owed different near
    expiries. The population is `financed_spread.population` — two-leg
    single-expiry DEBIT verticals read off the leg GEOMETRY — so the scrape
    targets exactly the rows the study can build on.

    Census keys: `rows` (population rows), `no_entry_day`, `no_near_expiry`,
    `no_ladder_beyond`, `targeted` (rows that produced >= 1 target).
    """
    if records is None:
        records, _diag = load_book(include_bs=False, era=ERA)
    if idx is None:
        idx = _strike_index()
    ladder = ticker_ladder(idx)
    expiries = ticker_expiries(idx)

    census: Counter = Counter()
    seen: dict[tuple, dict] = {}
    pop, _why = population(records)
    for rec, dirn in pop:
        census["rows"] += 1
        legs = rec["t"].legs
        ticker, exp = legs[0].ticker.upper(), legs[0].expiration
        entry_day = BR.entry_date_for(legs, rec["t"].grid)
        if entry_day is None:
            census["no_entry_day"] += 1
            continue
        dte = (exp - entry_day).days
        near = (near_expiry_for(entry_day, dte, expiries.get(ticker, []))
                if dte > 0 else None)
        if near is None:
            census["no_near_expiry"] += 1
            continue
        outer = (max(lg.strike for lg in legs) if dirn == "bull"
                 else min(lg.strike for lg in legs))
        cands = _diag_candidates_for_row(ticker, near, outer, dirn,
                                         ladder.get(ticker, []))
        if not cands:
            census["no_ladder_beyond"] += 1
            continue
        census["targeted"] += 1
        for r in cands:
            key = (r["ticker"], r["expiration"], r["strike"], r["opt_type"])
            seen.setdefault(key, r)
    out = sorted(seen.values(), key=lambda r: (r["ticker"], r["expiration"],
                                               r["strike"], r["opt_type"]))
    return out, census


def split_cached(target_records: list[dict], idx: dict) -> tuple[list[dict], list[dict]]:
    """`(cached, missing)` — targets already present in the option cache
    (per `idx`) vs still needing a fetch. "Skip targets already present in
    the cache (count them)": `cached` is the count, `missing` is what gets
    added to the manifest."""
    cached, missing = [], []
    for r in target_records:
        near_idx = idx.get((r["ticker"], r["expiration"]), {})
        if r["opt_type"] in near_idx.get(r["strike"], set()):
            cached.append(r)
        else:
            missing.append(r)
    return cached, missing


# ─── Cache path (mirrors fetch_sweep_legs.py's contract_path) ─────────────────

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


def wanted_rows(rows: dict[tuple, dict], *, retry_failed: bool = False,
                categories: set[str] | None = None) -> list[tuple]:
    """The manifest keys one run would attempt, sorted. `categories` (None =
    every category) selects which arm's targets this run is for."""
    wanted = {"pending", ""} | ({"failed"} if retry_failed else set())
    return sorted(k for k, r in rows.items()
                  if r.get("status", "pending") in wanted
                  and (categories is None or r.get("category") in categories))


async def run_fetch(rows: dict[tuple, dict], manifest_path: Path, *, limit: int | None = None,
                    retry_failed: bool = False, headless: bool = True, timeout_ms: int = 30000,
                    sleep_s: float = 0.4, session=None,
                    categories: set[str] | None = None) -> dict:
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

    pending = wanted_rows(rows, retry_failed=retry_failed, categories=categories)
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


def print_census(target_records: list[dict], cached: list[dict], missing: list[dict],
                 n_records: int) -> None:
    n_tickers = len({r["ticker"] for r in target_records})
    n_groups = len({(r["ticker"], r["expiration"]) for r in target_records})
    log.info("financing target census (era=%s, %d book records): "
             "%d targets across %d tickers / %d (ticker, expiry) groups",
             ERA, n_records, len(target_records), n_tickers, n_groups)
    log.info("  cached %d  |  missing %d", len(cached), len(missing))
    by_cat = Counter(r["category"] for r in missing)
    log.info("  missing by category: %s", "  ".join(f"{k}={v}" for k, v in sorted(by_cat.items())))


def print_diag_census(target_records: list[dict], cached: list[dict],
                      missing: list[dict], census: Counter) -> None:
    n_tickers = len({r["ticker"] for r in target_records})
    n_exp = len({(r["ticker"], r["expiration"]) for r in target_records})
    log.info("fin_diag (ARM F4) target census: %d targets across %d tickers / "
             "%d (ticker, near-expiry) pairs", len(target_records), n_tickers,
             n_exp)
    log.info("  cached %d  |  missing %d", len(cached), len(missing))
    log.info("  population rows %d  ->  targeted %d   "
             "(no_near_expiry %d, no_entry_day %d, no_ladder_beyond %d)",
             census["rows"], census["targeted"], census["no_near_expiry"],
             census["no_entry_day"], census["no_ladder_beyond"])
    by_cat = Counter(r["category"] for r in missing)
    log.info("  missing by category: %s",
             "  ".join(f"{k}={v}" for k, v in sorted(by_cat.items())) or "none")


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
    parser.add_argument("--category", default=None,
                        help="Comma-separated manifest categories to fetch "
                             "(fin_call_above, fin_put_below, fin_diag_call, "
                             "fin_diag_put). Default: all. Targets are derived "
                             "and written for every category regardless — this "
                             "only selects what THIS run fetches.")
    parser.add_argument("--no-headless", action="store_true", help="Visible browser.")
    args = parser.parse_args()

    idx = _strike_index()
    records, _diag = load_book(include_bs=False, era=ERA)
    target_records = financing_target_records(records, idx)
    cached, missing = split_cached(target_records, idx)
    print_census(target_records, cached, missing, len(records))

    diag_records, diag_census = diag_target_records(records, idx)
    diag_cached, diag_missing = split_cached(diag_records, idx)
    print_diag_census(diag_records, diag_cached, diag_missing, diag_census)

    # A diagonal target that is ALREADY a vertical target keeps the vertical
    # row: same contract, same cache file, and rewriting a live row's category
    # for a cosmetic label is exactly the "existing rows untouched" promise
    # this manifest makes to a half-finished fetch.
    vertical_keys = {_key(r["ticker"], r["expiration"], r["strike"],
                          r["opt_type"]) for r in missing}
    diag_new = [r for r in diag_missing
                if _key(r["ticker"], r["expiration"], r["strike"],
                        r["opt_type"]) not in vertical_keys]

    existing = load_manifest(MANIFEST_PATH)
    rows = merge_manifest(existing, missing + diag_new)
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
