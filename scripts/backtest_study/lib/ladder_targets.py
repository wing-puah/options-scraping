"""The ONE owner of "which contracts does a ladder campaign owe a core?"

WHY THIS EXISTS
---------------
`ladder_overlay` (`research/pre-registrations/f3_structure/ladder_overlay.md`)
tests a rolled short-call ladder (plus a naked-put alternative) wrapped around
a book `bull_call_spread` core. Both the PRE-SCRAPE collector
(`scripts/collector/fetch_ladder_legs.py`) and the POST-SCRAPE campaign engine
(`scripts/backtest_study/lib/overlay_campaign.py`) need to agree, contract for
contract, on which strikes/expiries a roll slot is owed — this module is that
single encoding, imported by both. A scrape target and a campaign target that
disagreed would let the collector fetch contracts the campaign never reads, or
let the campaign silently read a coverage gap as "nothing eligible" instead of
"not fetched yet".

The two callers differ only in their EXPIRY UNIVERSE: the collector passes
`cached ∪ third-Fridays` (it must be able to name an expiry that isn't cached
yet, or nothing would ever get fetched); the campaign passes cached-only (it
can price only what is on disk). Every function here is agnostic to which
universe it is handed — `expiries: list[date]` is always an explicit argument,
never re-derived internally — which is what keeps the two callers from
drifting apart on anything but that one input.

ONE-OWNER RULE: `third_fridays`, `eligible_expiries`, `roll_chain`,
`ticker_ladder`, `target_strikes`, `cached_strikes`, `CoreSpec` and `core_of`
are defined ONCE, here. Neither caller re-implements any of them — a second
copy is exactly how the collector and the campaign would end up disagreeing
about what "eligible" means.

Pure, no network, no writes. `DIAG_MIN_DAYS` / `DIAG_MAX_DTE_FRAC` are
imported from `financed_spread` (F4's frozen near-expiry window; see that
module for why 7 days / half-DTE are pinned) rather than redefined, so the
ladder's roll window and F4's diagonal window can never quietly diverge.
`cached_ticker_expiries` / `cached_calls` (financed_spread) and `cached_puts`
/ `entry_date_for` (bear_rewrap) are imported by reference for the same
reason — both modules are read-only, side-effect-free at import time (their
`main()` is guarded by `if __name__ == "__main__":`), so importing them here
costs nothing and buys one less strike-ladder implementation to keep in sync.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest_study.f3_structure import bear_rewrap as BR  # noqa: E402
from scripts.backtest_study.f3_structure.financed_spread import (  # noqa: E402
    DIAG_MAX_DTE_FRAC, DIAG_MIN_DAYS, cached_calls,
)
from scripts.backtest_study.lib.underlying import load_bars  # noqa: E402

N_STRIKES = 4        # nearest ladder strikes per roll slot, either side
N_EXPIRIES = 2        # roll slot 0 (t0) fetches the 2 nearest eligible expiries


# ─── Expiry calendar ────────────────────────────────────────────────────────

def third_fridays(start: date, end: date) -> list[date]:
    """Every third Friday of a calendar month whose date falls in `[start, end]`.

    No holiday table (a fixed US market holiday landing on a third Friday is
    rare and, per the contract, not worth the complexity here): if Barchart
    does not serve that contract the fetch simply comes back `failed` and is
    counted, never silently swapped for a nearby Friday.
    """
    out: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        first = date(year, month, 1)
        first_friday = first + timedelta(days=(4 - first.weekday()) % 7)
        third_friday = first_friday + timedelta(days=14)
        if start <= third_friday <= end:
            out.append(third_friday)
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return sorted(out)


def eligible_expiries(day: date, remaining_dte: int, expiries: list[date]) -> list[date]:
    """Sorted expiries in `financed_spread.near_expiry_for`'s own window:
    `day + DIAG_MIN_DAYS <= e <= day + int(remaining_dte * DIAG_MAX_DTE_FRAC)`.

    `eligible_expiries(...)[0]` (or `None` if empty) is that function's return
    value — the two must never disagree about which expiry is nearest, and
    `tests/test_ladder_targets.py` pins the equality directly against
    `financed_spread.near_expiry_for`.
    """
    lo = day + timedelta(days=DIAG_MIN_DAYS)
    hi = day + timedelta(days=int(remaining_dte * DIAG_MAX_DTE_FRAC))
    return sorted(e for e in expiries if lo <= e <= hi)


def roll_chain(grid: list[date], entry_day: date, core_expiry: date,
               expiries: list[date]) -> list[tuple[date, date]]:
    """`[(roll_day, near_expiry), ...]` — the sequence of roll slots a ladder
    campaign runs through the core's life.

    `roll_day_0 = entry_day`; at every roll day the NEAREST eligible expiry
    (`eligible_expiries(...)[0]`) is the tranche sold there; the next roll day
    is the first `grid` day STRICTLY AFTER that expiry. The chain stops the
    moment either a roll day falls outside `grid` or no expiry is eligible —
    never widened or extended to force another slot. Empty when nothing is
    eligible even at entry.
    """
    grid_sorted = sorted(grid)
    grid_set = set(grid_sorted)
    out: list[tuple[date, date]] = []
    roll_day = entry_day
    while roll_day in grid_set:
        remaining = (core_expiry - roll_day).days
        if remaining <= 0:
            break
        candidates = eligible_expiries(roll_day, remaining, expiries)
        if not candidates:
            break
        near = candidates[0]
        out.append((roll_day, near))
        later = [d for d in grid_sorted if d > near]
        if not later:
            break
        roll_day = later[0]
    return out


# ─── Strike ladder ──────────────────────────────────────────────────────────

def ticker_ladder(ticker: str) -> list[float]:
    """Union of every strike cached for `ticker`, across every expiry and both
    option types — the ticker's OWN observed strike ladder, never an invented
    increment.

    Same rule as `scripts/collector/fetch_financing_legs.py::ticker_ladder`,
    mirrored rather than imported: that one takes a pre-built `idx` covering
    EVERY ticker at once (built for a ~40k-row scan), while this one scans the
    cache for a single ticker on demand — different signature, same
    derivation. `tests/test_ladder_targets.py` pins the two against each
    other on a shared fixture.
    """
    tk = ticker.upper().strip()
    out: set[float] = set()
    for path in HISTORY_CACHE.glob(f"{tk}_*.csv"):
        parts = path.stem.split("_")
        if len(parts) != 3 or parts[0] != tk:
            continue
        try:
            out.add(float(parts[2][:-1]))
        except ValueError:
            continue
    return sorted(out)


def target_strikes(ladder: list[float], outer: float, opt_type: str,
                   n: int = N_STRIKES) -> list[float]:
    """The `n` nearest ladder strikes beyond `outer`, in the OTM direction.

    Call: `n` nearest STRICTLY ABOVE `outer`, ascending. Put: `n` nearest
    STRICTLY BELOW `outer`, descending (nearest first). Fewer than `n` on the
    ladder yields fewer targets — never a fabricated strike to round up.
    """
    if opt_type == "Call":
        return sorted(k for k in ladder if k > outer)[:n]
    return sorted((k for k in ladder if k < outer), reverse=True)[:n]


def cached_strikes(ticker: str, expiry: date, opt_type: str) -> list[float]:
    """What actually exists in the option cache at `(ticker, expiry, opt_type)`
    — `financed_spread.cached_calls` / `bear_rewrap.cached_puts`, dispatched
    on type so a caller doesn't need to pick the sibling helper itself."""
    if opt_type == "Call":
        return cached_calls(ticker, expiry)
    return BR.cached_puts(ticker, expiry)


# ─── Core + targets ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CoreSpec:
    ticker: str
    expiry: date
    lo: float           # the core's long (lower) strike
    hi: float           # the core's short (higher) strike
    entry_day: date
    grid: tuple[date, ...]
    spot_entry: float | None


def core_of(rec: dict) -> CoreSpec | None:
    """`CoreSpec` for a `bull_call_spread` book row, else `None`.

    `rec` is a `load_book` record (`rec["t"]` the harness `Trade`). Only a
    two-leg, single-expiry `bull_call_spread` (long the lower Call strike,
    short the higher one — the geometry, not just the label, is checked)
    qualifies; every other structure, and a row whose legs cannot even be
    priced on a common entry day (`bear_rewrap.entry_date_for` returns
    `None`), is excluded rather than guessed at. `spot_entry` is the
    underlying's OHLC close on the entry day (`lib.underlying.load_bars`),
    `None` if that ticker/day has no bar — callers that need it (the put-short
    tranche) skip rather than substitute a stand-in spot.
    """
    t = rec.get("t") if isinstance(rec, dict) else None
    if t is None or getattr(t, "structure", None) != "bull_call_spread":
        return None
    legs = list(t.legs)
    if len(legs) != 2 or len({lg.expiration for lg in legs}) != 1:
        return None
    longs = [lg for lg in legs if lg.qty > 0]
    shorts = [lg for lg in legs if lg.qty < 0]
    if len(longs) != 1 or len(shorts) != 1:
        return None
    lo_leg, hi_leg = longs[0], shorts[0]
    if lo_leg.opt_type != "Call" or hi_leg.opt_type != "Call" or lo_leg.strike >= hi_leg.strike:
        return None
    entry_day = BR.entry_date_for(legs, list(t.grid))
    if entry_day is None:
        return None
    bar = load_bars(lo_leg.ticker).get(entry_day)
    return CoreSpec(ticker=lo_leg.ticker, expiry=lo_leg.expiration, lo=lo_leg.strike,
                    hi=hi_leg.strike, entry_day=entry_day, grid=tuple(t.grid),
                    spot_entry=bar.c if bar is not None else None)


def ladder_targets(core: CoreSpec, expiries: list[date],
                   ladder: list[float]) -> list[dict]:
    """`{ticker, expiration, strike, opt_type("Call"/"Put"), category}` rows
    this core owes, deduplicated (the manifest layer dedupes again against
    the cache — this is a within-list dedupe only):

      ladder_call_t0    roll slot 0 — for EACH of the `N_EXPIRIES` nearest
                        eligible expiries at `entry_day`, `target_strikes`
                        above `core.hi`, Call
      ladder_call_roll  roll slots 1..k from `roll_chain` (one expiry per
                        slot — the chain follows the NEAREST expiry only) —
                        same strike rule
      ladder_put_short  same slots/expiries as the two call categories,
                        `target_strikes` around `core.spot_entry`, Put —
                        skipped entirely when `spot_entry` is `None`
      ladder_put_core   ONE row, unconditional: Put at `(core.expiry, core.lo)`
                        — the naked-put-in-place-of-the-core alternative
    """
    seen: dict[tuple, dict] = {}

    def add(expiry: date, strike: float, opt_type: str, category: str) -> None:
        key = (core.ticker, expiry, strike, opt_type)
        seen.setdefault(key, dict(ticker=core.ticker, expiration=expiry, strike=strike,
                                  opt_type=opt_type, category=category))

    remaining = (core.expiry - core.entry_day).days
    t0_expiries = eligible_expiries(core.entry_day, remaining, expiries)[:N_EXPIRIES] \
        if remaining > 0 else []
    for exp in t0_expiries:
        for k in target_strikes(ladder, core.hi, "Call"):
            add(exp, k, "Call", "ladder_call_t0")
        if core.spot_entry is not None:
            for k in target_strikes(ladder, core.spot_entry, "Put"):
                add(exp, k, "Put", "ladder_put_short")

    chain = roll_chain(list(core.grid), core.entry_day, core.expiry, expiries)
    for _roll_day, near in chain[1:]:
        for k in target_strikes(ladder, core.hi, "Call"):
            add(near, k, "Call", "ladder_call_roll")
        if core.spot_entry is not None:
            for k in target_strikes(ladder, core.spot_entry, "Put"):
                add(near, k, "Put", "ladder_put_short")

    add(core.expiry, core.lo, "Put", "ladder_put_core")

    return sorted(seen.values(), key=lambda r: (r["ticker"], r["expiration"], r["strike"],
                                                r["opt_type"], r["category"]))
