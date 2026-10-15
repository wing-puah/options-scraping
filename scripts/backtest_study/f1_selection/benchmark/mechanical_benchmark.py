"""mechanical_benchmark — do the picks beat a mechanical bull call spread on the same dates?

Registration: `research/pre-registrations/f1_selection/benchmark/mechanical_benchmark.md`
(accepted by default 2026-10-09). That file is the spec; this module implements
it and adds nothing to its bar. RESEARCH TIER: nothing ships from this study.

THE ARMS, every one paired on (date, ticker) with a deployed pick:

    ARM T    the deployed book (`top_k_per_day`, k=3, Tier A/B), replayed
    ARM M1   PRIMARY  — ATM / +5% call vertical, the pick's own expiry
    ARM M2   SECONDARY — long strike nearest the pick's net delta, +5% short
    ARM M2L  declared secondary of M2 — long strike nearest the pick's BOUGHT
             leg delta (Resolved at build: "the pick's delta" is contested)
    ARM U    PRIMARY for selection — the M1 wrap on a random ticker from the
             date's flow universe, at the monthly expiry nearest the pick's DTE
    ARM CEN  census — built, dropped and awaiting-fetch counts by tier, band

WHAT IS READ ON WHICH DAY (gate G2). Strikes and the delta target are chosen
from rows dated ON OR BEFORE THE SIGNAL DATE: the underlying is the median
`Price~` of the pick's own legs on the signal date, a strike is listed when its
cached history has a row on or before it, and a delta is the strike's
signal-date `Delta`. Entry is the pick's RECORDED entry day
(`bear_rewrap.recorded_entry_date`), so both sides of a pair fill on the same
session. G2 re-runs every choice on a cache cut at the signal date and fails
the run on any difference.

PRICING is production's: `scripts/backtest/simulate._simulate` over the cached
histories, loaded through `narrow_to_fit.Chain` exactly as
`fetch_option_histories` loads them. Entry fills, the junk-quote rule and the
debit-to-credit refusal are therefore production's, imported, never mirrored.
No model price is used anywhere. G5 checks the builder reproduces stored rows
at their own strikes before any counterpart is trusted.

EXITS. Both sides replay through the frozen harness (`lib/harness.replay`) on
the trade cut at its data end (`replay_basis.bounded`). Headline: `DEBIT_PROD`
on both sides (G3, as registered). Declared secondary: each side under its own
deployment-rules §5 row. Both books are GROSS of costs; `cost_sensitivity` has
not landed, so the registration's fallback applies and every table says so.

A STRIKE WE CANNOT SEE. The listed grid is the cached strikes plus every
multiple of the finer of the cached spacing and the standard listing step
(`narrow_to_fit.strike_grid`'s rule). A grid strike nearer the target that is
not cached, and that the skip-list holds no evidence against, could be listed:
the pair is then AWAITING FETCH, never silently built on the next-nearest
strike. While any pair awaits a fetch, no outcome prints: the cached subset is
selected by what the book traded, so it is not the registered population.

FLOORS BY ARM (Resolved at build 2026-10-13). Floors 1 and 2 gate every arm,
and a floor-2 FAIL kills the study. Floor 4a (no M1/M2 pair awaiting) gates
the same-ticker arms; M2L also needs its own pairs fetched. Floors 3 and 4b
gate only ARM U, the criteria graded on it (C3, C4, C5) and the study-level
verdict. Same-ticker arms read while ARM U is not built print
`SAME-TICKER READ — ARM U NOT BUILT` and per-arm C0-C2 + CONTRARY, never a
study-level token, since each of those also claims something about ARM U.

The fetch plan is `fetch_targets()`, imported by
`scripts/collector/fetch_mechanical_legs.py`. No code here fetches.

Usage:
  python3 -m scripts.backtest_study run mechanical_benchmark
  python3 -m scripts.backtest_study.f1_selection.benchmark.mechanical_benchmark
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import logging
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from lib.parsing import to_float  # noqa: E402
from lib.structure_names import canonical_spread_names  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest.proxy import _infer_strike_step, _strike_step  # noqa: E402
from scripts.backtest.simulate import _simulate  # noqa: E402
from scripts.backtest_study.f3_structure.bear_rewrap import recorded_entry_date  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import CREDIT_PROD, DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import Trade, replay  # noqa: E402
from scripts.backtest_study.lib.ladder_targets import third_fridays  # noqa: E402
from scripts.backtest_study.lib.replay_basis import bounded  # noqa: E402
from scripts.backtest_study.lib.underlying import _load_ohlc_cache  # noqa: E402

# Era refusals from `load_book` (exit 2 thin era, exit 3 wrong era).
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# ── registered constants (the registration's numbers; never re-chosen) ──────

#: DTE bands, `[lo, hi)`. A pick outside all four is out of scope.
BANDS = ((7, 21), (21, 45), (45, 90), (90, 180))
#: Fixed geometry: long nearest spot x1.00, short nearest spot x1.05 (M1);
#: short nearest long x1.05 (M2).
LONG_MULT = 1.00
SHORT_MULT = 1.05
#: The deployed set: top-3 per day in ladder order, Tier A/B only.
K_DEPLOY = 3
#: ARM U — draws, seed, redraw cap (floor 3 is `1 - cap`, by registration).
U_DRAWS = 1000
U_SEED = 20261009
U_REDRAW_CAP = 0.25
#: C0 power floor.
C0_MIN_DATES = 25
C0_MIN_PAIRS = 40
#: Census floors 1, 2, 5.
FLOOR1_MIN_DATES = 25
FLOOR1_PAIRS_LITERAL = 5      # declared secondary line; unreachable at k=3
FLOOR2_MAX_TIER_GAP = 0.10
FLOOR5_MIN_BAND_PAIRS = 10

#: §5 BEAR_HE trail row (config/backtest.yml regime_exit.cells.BEAR_HE).
BEAR_HE_PROD = dict(DEBIT_PROD, trig=0.50, trail=0.50)


UNIVERSE_DIRS = (ROOT / "audit", ROOT / "backtests" / "analysis_inputs_cache")
OUT_DIR = ROOT / "backtests" / "study_output"
PAIRS_CSV = OUT_DIR / "mechanical_benchmark-pairs.csv"
#: The wrap's label, from the one canonicalisation (`lib/structure_names.py`),
#: so it classifies exactly as a real call debit vertical does.
STRUCTURE = canonical_spread_names("call debit spread").replace(" ", "_")
#: The grid walk looks this many listing steps either side of a target.
GRID_REACH = 8
#: A ticker's underlying is the median `Price~` of this many cached calls
#: (`UniverseSpot`); the walk probes until it has them or runs out.
SPOT_CONTRACTS = 5

log = logging.getLogger("mechanical_benchmark")


def hdr(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ════════════════════════════════════════════════════════════════════════════
# Geometry rules — pure
# ════════════════════════════════════════════════════════════════════════════

def band_of(dte) -> tuple[int, int] | None:
    """The registered DTE band holding `dte`, or None (out of scope)."""
    try:
        d = int(dte)
    except (TypeError, ValueError):
        return None
    for lo, hi in BANDS:
        if lo <= d < hi:
            return (lo, hi)
    return None


def band_label(b: tuple[int, int] | None) -> str:
    return f"[{b[0]},{b[1]})" if b else "out"


def grid_step(spot: float, cached: list[float]) -> float:
    """The finer of the standard listing step and the cached strikes' spacing."""
    step = _strike_step(spot)
    inferred = _infer_strike_step(cached) if len(cached) > 1 else None
    return inferred if inferred and inferred < step else step


def grid_around(target: float, step: float, cached: list[float],
                reach: int = GRID_REACH) -> list[float]:
    """Candidate strikes near `target`, nearest first (ties: lower strike).

    The cached strikes within `reach` steps plus every grid multiple there.
    """
    lo, hi = target - reach * step, target + reach * step
    pts = {round(k, 4) for k in cached if lo <= k <= hi}
    n0 = math.floor(target / step)
    for i in range(-reach, reach + 2):
        k = round((n0 + i) * step, 4)
        if k > 0 and lo <= k <= hi:
            pts.add(k)
    return sorted(pts, key=lambda k: (abs(k - target), k))


def is_degenerate(k_long: float | None, k_short: float | None) -> bool:
    """Colliding strikes or a non-positive width: the pair is dropped."""
    return k_long is None or k_short is None or k_short <= k_long + 1e-9


def good_friday(year: int) -> date:
    """Easter Sunday minus two days (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    return date(year, month, day) - timedelta(days=2)


def monthly_expiries(start: date, end: date) -> list[date]:
    """Standard monthly expiries in `[start, end]`: third Fridays, moved to
    the Thursday when the Friday is an exchange holiday (Good Friday, or
    Juneteenth from 2022). The only two holidays a third Friday can fall on."""
    out = []
    for f in third_fridays(start - timedelta(days=1), end + timedelta(days=1)):
        hol = f == good_friday(f.year) or (f.month == 6 and f.day == 19 and f.year >= 2022)
        e = f - timedelta(days=1) if hol else f
        if start <= e <= end:
            out.append(e)
    return out


def monthly_for(entry_day: date, dte: int, band: tuple[int, int]) -> date | None:
    """ARM U's expiry: the monthly expiry whose DTE from the entry day is
    nearest `dte`, inside `band`. Ties go to the earlier expiry."""
    lo = entry_day + timedelta(days=band[0])
    hi = entry_day + timedelta(days=band[1] - 1)
    cands = monthly_expiries(lo, hi)
    if not cands:
        return None
    return min(cands, key=lambda e: (abs((e - entry_day).days - dte), e))


# ════════════════════════════════════════════════════════════════════════════
# The cache, read as of a date
# ════════════════════════════════════════════════════════════════════════════

class AsOfChain(NTF.Chain):
    """`narrow_to_fit.Chain` with EVERY contract cut at `asof` (gate G2)."""

    def __init__(self, parent: NTF.Chain, asof: date):
        super().__init__(parent=parent)
        self.asof = asof

    def history(self, leg: Leg):
        series, details = self._load(leg)
        return ([(d, m) for d, m in series if d <= self.asof],
                {d: r for d, r in details.items() if d <= self.asof})


def call_leg(ticker: str, expiry: date, strike: float, qty: int = 1) -> Leg:
    return Leg(qty, ticker, expiry, float(strike), "Call")


def cached_calls(chain: NTF.Chain, ticker: str, expiry: date) -> list[float]:
    return sorted(k for k in chain.strikes(ticker, expiry)
                  if chain.cached(ticker, expiry, k, "Call"))


def listed_by(chain: NTF.Chain, leg: Leg, asof: date) -> bool:
    """A cached contract is listed at `asof` when it has a row on or before it."""
    series, details = chain.history(leg)
    return any(d <= asof for d, _ in series) or any(d <= asof for d in details)


def row_on(chain: NTF.Chain, leg: Leg, day: date) -> dict | None:
    _series, details = chain.history(leg)
    return details.get(day)


def spot_on(chain: NTF.Chain, legs: list[Leg], day: date) -> float | None:
    """Median `Price~` on `day` across `legs` (production's entry rule, read on
    the signal date instead of the entry day)."""
    vals = []
    for leg in legs:
        row = row_on(chain, leg, day)
        v = to_float(row.get("Price~")) if row else None
        if v is not None and v > 0:
            vals.append(v)
    return statistics.median(vals) if vals else None


def delta_on(chain: NTF.Chain, leg: Leg, day: date) -> float | None:
    row = row_on(chain, leg, day)
    return to_float(row.get("Delta")) if row else None


# ════════════════════════════════════════════════════════════════════════════
# Strike selection — reads the signal date and nothing later
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass(frozen=True)
class Sel:
    """One strike choice. `status`: built | await | drop."""
    status: str
    strike: float | None = None
    reason: str = ""
    fetch: tuple = ()          # strikes to fetch (calls at the same expiry)


def nearest_listed(chain: NTF.Chain, evidence: set[str], ticker: str,
                   expiry: date, target: float, spot: float, asof: date) -> Sel:
    """The listed call strike nearest `target`, walked nearest-first.

    Skip-listed on evidence -> not listed, step on. Cached with a row on or
    before `asof` -> chosen. Cached without one -> not listed yet, step on.
    Not cached and not evidenced -> AWAIT: it could be the nearest listed one.
    """
    cached = cached_calls(chain, ticker, expiry)
    step = grid_step(spot, cached)
    for k in grid_around(target, step, cached):
        stem = NTF.contract_stem(ticker, expiry, k, "Call")
        if stem in evidence:
            continue
        if chain.cached(ticker, expiry, k, "Call"):
            if listed_by(chain, call_leg(ticker, expiry, k), asof):
                return Sel("built", k)
            continue
        return Sel("await", k, "strike_not_cached", (k,))
    return Sel("drop", reason="no_listed_strike")


def nearest_delta(chain: NTF.Chain, evidence: set[str], ticker: str,
                  expiry: date, target: float, spot: float, asof: date) -> Sel:
    """The listed call strike whose `asof` delta is nearest `target`.

    Call delta falls as the strike rises, so the nearest known strike `k*` is
    proven once the walk from `k*` toward the target reaches a known strike, or
    runs out of grid, without meeting an uncached, un-evidenced strike. A
    cached strike with no `asof` row has no delta to compare and is passed.
    """
    cached = cached_calls(chain, ticker, expiry)
    step = grid_step(spot, cached)
    known = {}
    for k in cached:
        if NTF.contract_stem(ticker, expiry, k, "Call") in evidence:
            continue
        d = delta_on(chain, call_leg(ticker, expiry, k), asof)
        if d is not None and 0.0 <= d <= 1.0:
            known[round(k, 4)] = d
    if not known:
        want = [k for k in grid_around(spot, step, cached, reach=2)
                if not chain.cached(ticker, expiry, k, "Call")
                and NTF.contract_stem(ticker, expiry, k, "Call") not in evidence]
        if want:
            return Sel("await", None, "no_delta_known", tuple(want[:2]))
        return Sel("drop", reason="no_delta_at_signal")
    kstar = min(known, key=lambda k: (abs(known[k] - target), k))
    if abs(known[kstar] - target) < 1e-12:
        return Sel("built", kstar)
    up = known[kstar] > target          # need a smaller delta: a higher strike
    sign = 1 if up else -1
    walk = sorted({round(kstar + sign * i * step, 4) for i in range(1, 4 * GRID_REACH)}
                  | {k for k in known if (k > kstar) == up and k != kstar},
                  reverse=not up)
    walk = [k for k in walk if (k > kstar) == up and k > 0]
    for k in walk:
        if k in known:
            return Sel("built", kstar)
        stem = NTF.contract_stem(ticker, expiry, k, "Call")
        if stem in evidence or chain.cached(ticker, expiry, k, "Call"):
            continue
        return Sel("await", kstar, "delta_neighbour_not_cached",
                   delta_fetch(chain, evidence, ticker, expiry, target, spot,
                               kstar, known, walk, asof))
    return Sel("built", kstar)


# ── fetch ORDER for the M2/M2L walks (Resolved at build 2026-10-13) ─────────
# These only choose which open strikes an awaiting pair names in `fetch`.
# None of them reads into built, await or drop, or into the chosen strike.

#: An awaiting delta walk names this many open strikes nearest its estimate.
DELTA_FETCH_WIDTH = 2
#: When known deltas straddle the target and at most this many open strikes
#: lie between them, all of them are named: the proof needs every one.
BRACKET_FILL = 10
#: An awaiting M2/M2L short leg names at most this many open strikes in walk
#: order, up to the first on the standard listing grid.
LISTED_BATCH = 8


def _open(chain: NTF.Chain, evidence: set[str], ticker: str, expiry: date,
          k: float) -> bool:
    """Uncached and not skip-listed on evidence: a probe the walk would make."""
    return (NTF.contract_stem(ticker, expiry, k, "Call") not in evidence
            and not chain.cached(ticker, expiry, k, "Call"))


def delta_fetch(chain: NTF.Chain, evidence: set[str], ticker: str, expiry: date,
                target: float, spot: float, kstar: float, known: dict,
                walk: list[float], asof: date) -> tuple:
    """FETCH ORDER ONLY: the strikes an awaiting `nearest_delta` walk names.

    The open strikes are the uncached, un-evidenced ones on the walk before
    its first known strike `k2`; every one is a probe the old walk, stepping
    from `k*`, would make. When the deltas of `k*` and `k2` straddle the
    target and few open strikes lie between them, all are named. Otherwise
    the `DELTA_FETCH_WIDTH` nearest the estimated target strike are named,
    standard-grid strikes first (they are the ones likely listed). The
    estimate is a secant on `k*` and `k2` when they straddle, else
    Black-Scholes from `k*`'s own delta and IV. With neither, the old choice:
    the open strike next to `k*`.
    """
    open_, k2 = [], None
    for k in walk:
        if k in known:
            k2 = k
            break
        if _open(chain, evidence, ticker, expiry, k):
            open_.append(k)
    d0 = known[kstar]
    straddle = k2 is not None and (d0 - target) * (known[k2] - target) < 0
    if straddle and len(open_) <= BRACKET_FILL:
        return tuple(open_)
    est = None
    if straddle:
        est = kstar + (target - d0) / (known[k2] - d0) * (k2 - kstar)
    else:
        row = row_on(chain, call_leg(ticker, expiry, kstar), asof)
        iv = to_float(row.get("IV")) if row else None
        days = (expiry - asof).days
        if iv and iv > 0 and days > 0:
            nd = statistics.NormalDist()
            sig_t = iv / 100.0 * math.sqrt(days / 365.0)

            def clip(d):
                return min(max(d, 1e-4), 1 - 1e-4)
            est = kstar * math.exp((nd.inv_cdf(clip(d0)) - nd.inv_cdf(clip(target))) * sig_t)
    if est is None:
        return (open_[0],)
    std = _strike_step(spot)
    pool = [k for k in open_ if _on_grid(k, std)] or open_
    return tuple(sorted(pool, key=lambda k: (abs(k - est), k))[:DELTA_FETCH_WIDTH])


def _on_grid(k: float, step: float) -> bool:
    return abs(k / step - round(k / step)) < 1e-6


def listed_fetch(chain: NTF.Chain, evidence: set[str], ticker: str, expiry: date,
                 target: float, spot: float, asof: date, sel: Sel) -> Sel:
    """FETCH ORDER ONLY: an awaiting `nearest_listed` Sel for an M2/M2L short
    leg names the open strikes in its own walk order, from the one it awaits
    up to the first on the standard grid (at most `LISTED_BATCH`). It stops
    early at a cached strike listed by `asof`, where the walk would stop.
    Off-grid probes are mostly unlisted, so batching them saves a round each.
    """
    if sel.status != "await":
        return sel
    cached = cached_calls(chain, ticker, expiry)
    std = _strike_step(spot)
    walk = grid_around(target, grid_step(spot, cached), cached)
    out = []
    for k in walk[walk.index(sel.fetch[0]):]:
        if NTF.contract_stem(ticker, expiry, k, "Call") in evidence:
            continue
        if chain.cached(ticker, expiry, k, "Call"):
            if listed_by(chain, call_leg(ticker, expiry, k), asof):
                break
            continue
        out.append(k)
        if _on_grid(k, std) or len(out) >= LISTED_BATCH:
            break
    return dataclasses.replace(sel, fetch=tuple(out))


# ════════════════════════════════════════════════════════════════════════════
# Slots (deployed picks) and counterparts
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass
class Slot:
    rec: dict
    date: str
    ticker: str
    tier: str
    structure: str
    band: tuple[int, int] | None
    expiry: date | None
    signal: date
    entry_day: date | None
    dte: int | None
    drop: str = ""               # a drop that applies to every arm


def slot_of(rec: dict) -> Slot:
    t: Trade = rec["t"]
    legs = list(t.legs)
    dte = None
    try:
        dte = int(float(t.row.get("dte_entry")))
    except (TypeError, ValueError):
        pass
    s = Slot(rec=rec, date=rec["date"], ticker=t.ticker, tier=rec.get("tier", ""),
             structure=rec["structure"], band=band_of(dte),
             expiry=legs[0].expiration if legs else None, signal=t.signal_date,
             entry_day=recorded_entry_date(t), dte=dte)
    if len(legs) != 2 or legs[0].expiration != legs[1].expiration:
        s.drop = "not_a_vertical"
    elif s.entry_day is None or dte is None:
        s.drop = "no_recorded_entry"
    elif s.band is None:
        s.drop = "dte_ge_180" if dte >= BANDS[-1][1] else "dte_lt_7"
    return s


@dataclasses.dataclass
class Wrap:
    """One counterpart. `status`: built | await | drop."""
    status: str
    reason: str = ""
    k_long: float | None = None
    k_short: float | None = None
    fetch: tuple = ()            # ((ticker, expiry, strike), ...)
    row: dict | None = None      # production's priced row


def _combine(ticker: str, expiry: date, *sels: Sel) -> Wrap | None:
    """Await if any leg awaits (all fetches collected), drop on the first drop."""
    fetch = tuple((ticker, expiry, k) for s in sels for k in s.fetch)
    for s in sels:
        if s.status == "drop":
            return Wrap("drop", s.reason)
    if any(s.status == "await" for s in sels):
        return Wrap("await", next(s.reason for s in sels if s.status == "await"),
                    fetch=fetch)
    return None


def select_m1(chain, evidence, ticker: str, expiry: date, spot: float | None,
              asof: date) -> Wrap:
    """M1 strikes: nearest spot x1.00 and spot x1.05. No pricing."""
    if spot is None:
        return Wrap("drop", "no_spot_at_signal")
    lo = nearest_listed(chain, evidence, ticker, expiry, spot * LONG_MULT, spot, asof)
    hi = nearest_listed(chain, evidence, ticker, expiry, spot * SHORT_MULT, spot, asof)
    w = _combine(ticker, expiry, lo, hi)
    if w is not None:
        return w
    if is_degenerate(lo.strike, hi.strike):
        return Wrap("drop", "degenerate", lo.strike, hi.strike)
    return Wrap("built", "", lo.strike, hi.strike)


def select_m2(chain, evidence, ticker: str, expiry: date, spot: float | None,
              target: float | None, asof: date) -> Wrap:
    """M2 strikes: long nearest `target` delta, short nearest long x1.05."""
    if spot is None:
        return Wrap("drop", "no_spot_at_signal")
    if target is None:
        return Wrap("drop", "no_target_delta")
    lo = nearest_delta(chain, evidence, ticker, expiry, target, spot, asof)
    if lo.status != "built":
        return _combine(ticker, expiry, lo)
    hi = nearest_listed(chain, evidence, ticker, expiry, lo.strike * SHORT_MULT,
                        spot, asof)
    hi = listed_fetch(chain, evidence, ticker, expiry, lo.strike * SHORT_MULT,
                      spot, asof, hi)
    w = _combine(ticker, expiry, hi)
    if w is not None:
        return w
    if is_degenerate(lo.strike, hi.strike):
        return Wrap("drop", "degenerate", lo.strike, hi.strike)
    return Wrap("built", "", lo.strike, hi.strike)


def net_delta_target(chain, legs: list[Leg], asof: date) -> float | None:
    """|sum of qty x delta| of the pick's legs on `asof` (the `delta` column's
    quantity, read on the signal date). None when any leg lacks a delta."""
    tot = 0.0
    for leg in legs:
        d = delta_on(chain, leg, asof)
        if d is None:
            return None
        tot += leg.qty * d
    return abs(tot)


def bought_delta_target(chain, legs: list[Leg], asof: date) -> float | None:
    """|delta| of the pick's bought leg on `asof` (M2L)."""
    bought = [leg for leg in legs if leg.qty > 0]
    if len(bought) != 1:
        return None
    d = delta_on(chain, bought[0], asof)
    return abs(d) if d is not None else None


# ── pricing: production's engine ────────────────────────────────────────────

def price_wrap(chain: NTF.Chain, sim_cfg: dict, ticker: str, signal: date,
               entry_day: date, expiry: date, k_long: float,
               k_short: float) -> tuple[dict | None, str]:
    """`_simulate` on a 1-lot call vertical entered on `entry_day`.

    Returns `(row, "")` or `(None, reason)`. The call `plays.Play._simulate`
    makes, with the histories `narrow_to_fit.Chain` loads.
    """
    legs = [call_leg(ticker, expiry, k_long, 1), call_leg(ticker, expiry, k_short, -1)]
    s_map, d_map = chain.maps(legs)
    from scripts.backtest.helpers import _contract_key
    anchor = d_map.get(_contract_key(ticker, "Call", k_long, expiry.isoformat()), {})
    iv_row = anchor.get(entry_day) or {}
    entry_row = {"DTE": (expiry - entry_day).days, "IV": iv_row.get("IV"),
                 "_entry_date": entry_day}
    cand = {"ticker": ticker, "signal_date": signal, "play": "mechanical_benchmark",
            "regime": ""}
    refusal: dict = {}
    try:
        res = _simulate(cand, legs, entry_row, {}, s_map, sim_cfg, structure=STRUCTURE,
                        anchor_idx=0, barchart_details=d_map, refusal=refusal)
    except Exception as exc:  # production raised on this input: unpriced, named
        return None, f"simulate_error:{type(exc).__name__}"
    if not res:
        return None, f"unpriced:{refusal.get('reason', 'no_result')}"
    if "bs" in str(res.get("entry_source", "")).lower().split("+"):
        return None, "model_priced"
    return res, ""


def finish(w: Wrap, chain, sim_cfg, ticker, signal, entry_day, expiry) -> Wrap:
    """Price a built wrap; an unpriceable one becomes a drop."""
    if w.status != "built":
        return w
    row, why = price_wrap(chain, sim_cfg, ticker, signal, entry_day, expiry,
                          w.k_long, w.k_short)
    if row is None:
        return Wrap("drop", why, w.k_long, w.k_short)
    return dataclasses.replace(w, row=row)


# ════════════════════════════════════════════════════════════════════════════
# ARM U — the day's flow universe
# ════════════════════════════════════════════════════════════════════════════

def universe(day: str, dirs=UNIVERSE_DIRS) -> list[tuple[str, str]] | None:
    """`[(ticker, section)]` from `<day>-rollup.csv`, or None when no copy exists."""
    for d in dirs:
        p = Path(d) / f"{day}-rollup.csv"
        if p.exists():
            with p.open(newline="") as fh:
                out = []
                for r in csv.DictReader(fh):
                    sym = (r.get("Symbol") or "").strip().upper()
                    if sym and sym.replace(".", "").replace("-", "").isalnum():
                        out.append((sym, (r.get("Section") or "").strip()))
                return sorted(set(out))
    return None


class UniverseSpot:
    """A ticker's underlying on a day, read off its cached calls.

    The median `Price~` of the first `SPOT_CONTRACTS` cached calls with a
    positive `Price~` on `day`, in a fixed probe order: the pick expiry's
    strikes middle-out, then every other cached expiry on or after `day`,
    nearest first, strikes ascending. Only `day`'s own row is read (gate G2).
    None only when no cached call for the ticker carries one on that day.

    Until 2026-10-15 the walk stopped after `SPOT_CONTRACTS * 4` probes. When
    the pick's expiry was not yet listed on the signal date, every probe went
    to its unlisted strikes and the call returned None, although other
    expiries were priced that day (SPY 2025-03-03: 654 contracts at 583.77).
    The probe order is unchanged, so a spot the old walk read off five
    contracts is the same; one it read off fewer now reads up to five.
    A ticker and day with nothing priced is remembered, so the full walk runs
    once per (ticker, day), not once per expiry asked.
    """

    def __init__(self, chain: NTF.Chain):
        self.chain = chain
        self.by_ticker: dict[str, list[tuple[date, float]]] = defaultdict(list)
        for (tk, exp), strikes in chain.idx.items():
            for k, cps in strikes.items():
                if "C" in cps:
                    self.by_ticker[tk].append((exp, k))
        for pool in self.by_ticker.values():
            pool.sort()
        self._empty: set[tuple[str, date]] = set()
        self._memo: dict[tuple[str, date, date], float | None] = {}

    def _order(self, ticker: str, day: date, expiry: date):
        """`(expiry, strike)` in probe order (see the class doc)."""
        pool = [p for p in self.by_ticker.get(ticker, ()) if p[0] >= day]
        at = [p for p in pool if p[0] == expiry]           # strike-ascending
        mid = len(at) // 2
        for i in sorted(range(len(at)), key=lambda i: (abs(i - mid), i)):
            yield at[i]
        for p in pool:
            if p[0] != expiry:
                yield p

    def __call__(self, ticker: str, day: date, expiry: date) -> float | None:
        key = (ticker, day, expiry)
        if key in self._memo:
            return self._memo[key]
        if (ticker, day) in self._empty:
            return None
        got = []
        for e, k in self._order(ticker, day, expiry):
            row = row_on(self.chain, call_leg(ticker, e, k), day)
            v = to_float(row.get("Price~")) if row else None
            if v is not None and v > 0:
                got.append(v)
                if len(got) >= SPOT_CONTRACTS:
                    break
        if not got:
            self._empty.add((ticker, day))
        out = statistics.median(got) if got else None
        self._memo[key] = out
        return out


def ohlc_close(ticker: str, day: date) -> float | None:
    """Fetch PLANNING only: the cached stock close on or before `day`.

    Split-adjusted (underlying.py), so on a split ticker the estimate is off by
    the split ratio and the first fetch misses; the next run re-targets off the
    fetched contracts' own `Price~`. Never used to choose or price a wrap.
    """
    bars = _load_ohlc_cache(ticker)
    days = [d for d in bars if d <= day and (day - d).days <= 7]
    return bars[max(days)].c if days else None


# ════════════════════════════════════════════════════════════════════════════
# The build — every arm, every era
# ════════════════════════════════════════════════════════════════════════════

ARMS_M = ("M1", "M2", "M2L")


@dataclasses.dataclass
class EraBuild:
    era: str
    slots: list
    m: dict                      # arm -> [Wrap per slot]
    u_slot: list                 # per slot: (date, expiry | None, reason)
    u: dict                      # (date, ticker, expiry) -> Wrap
    universe: dict               # date -> [(ticker, section)] | None
    seal: str


def apply_seal(records: list[dict]) -> tuple[list[dict], str]:
    """The holdout seal on the returned book (`era.drop_sealed`, keyed on
    `date`). Idempotent beside `load_book`'s own withholding."""
    kept, info = era.drop_sealed(records, "date")
    return kept, era.seal_line(info)


def pick_spot(chain, spot_u, s: Slot) -> float | None:
    """The pick's signal-date underlying: its own legs' `Price~`, else the
    ticker's other cached contracts on that day (`UniverseSpot`)."""
    v = spot_on(chain, list(s.rec["t"].legs), s.signal)
    return v if v is not None else spot_u(s.ticker, s.signal, s.expiry)


def deployed(records: list[dict]) -> list[dict]:
    return P.top_k_per_day(records, P.ladder_rank, k=K_DEPLOY,
                           eligible_fn=P.ladder_eligible)


def build_era(era_name: str | None, chain: NTF.Chain, evidence: set[str],
              sim_cfg: dict, price: bool = True, records=None) -> EraBuild:
    if records is None:
        records, _diag = load_book(era=era_name, include_bs=False)
    records, seal = apply_seal(records)
    slots = [slot_of(r) for r in deployed(records)]
    spot_u = UniverseSpot(chain)
    m = {a: [] for a in ARMS_M}
    for s in slots:
        if s.drop:
            for a in ARMS_M:
                m[a].append(Wrap("drop", s.drop))
            continue
        legs = list(s.rec["t"].legs)
        spot = pick_spot(chain, spot_u, s)
        targets = {"M2": net_delta_target(chain, legs, s.signal),
                   "M2L": bought_delta_target(chain, legs, s.signal)}
        for a in ARMS_M:
            if a == "M1":
                w = select_m1(chain, evidence, s.ticker, s.expiry, spot, s.signal)
            else:
                w = select_m2(chain, evidence, s.ticker, s.expiry, spot,
                              targets[a], s.signal)
            if price:
                w = finish(w, chain, sim_cfg, s.ticker, s.signal, s.entry_day, s.expiry)
            m[a].append(w)

    uni = {d: universe(d) for d in sorted({s.date for s in slots})}
    u_slot, u = [], {}
    for s in slots:
        if s.drop:
            u_slot.append((s.date, None, s.drop))
            continue
        exp = monthly_for(s.entry_day, s.dte, s.band)
        if exp is None:
            u_slot.append((s.date, None, "no_monthly_in_band"))
            continue
        if uni[s.date] is None:
            u_slot.append((s.date, exp, "no_universe_file"))
            continue
        u_slot.append((s.date, exp, ""))
        for tk, _sec in uni[s.date]:
            key = (s.date, tk, exp)
            if key in u:
                continue
            u[key] = u_wrap(chain, evidence, sim_cfg, spot_u, tk, s, exp, price)
    return EraBuild(era_name or era.CURRENT, slots, m, u_slot, u, uni, seal)


def plan_m1_fetch(chain, evidence: set[str], ticker: str, exp: date,
                  est: float) -> tuple:
    """FETCH PLANNING ONLY, for a wrap whose underlying is not cached on the
    signal date: per M1 leg, the grid strike nearest `est` x mult that the
    skip-list holds no evidence against, when it is not cached. Never chooses
    or prices a wrap; the wrap awaits whatever this returns.

    The evidence skip is the one `nearest_listed` applies. Without it an
    evidenced strike was re-named on every run and re-requested forever
    (SPY 2025-04-25 613C, 2026-10-14)."""
    cached = cached_calls(chain, ticker, exp)
    step = grid_step(est, cached)
    fetch = []
    for tgt in (est * LONG_MULT, est * SHORT_MULT):
        k = next((c for c in grid_around(tgt, step, cached)
                  if NTF.contract_stem(ticker, exp, c, "Call") not in evidence), None)
        if k is not None and not chain.cached(ticker, exp, k, "Call"):
            fetch.append((ticker, exp, k))
    return tuple(fetch)


def u_wrap(chain, evidence, sim_cfg, spot_u, ticker: str, s: Slot, exp: date,
           price: bool) -> Wrap:
    spot = spot_u(ticker, s.signal, exp)
    if spot is None:
        est = ohlc_close(ticker, s.signal)
        if est is None:
            return Wrap("await", "no_underlying_known")
        return Wrap("await", "no_spot_cached",
                    fetch=plan_m1_fetch(chain, evidence, ticker, exp, est))
    w = select_m1(chain, evidence, ticker, exp, spot, s.signal)
    if price:
        w = finish(w, chain, sim_cfg, ticker, s.signal, s.entry_day, exp)
    return w


# ════════════════════════════════════════════════════════════════════════════
# Census (ARM CEN) and the five floors — counts only
# ════════════════════════════════════════════════════════════════════════════

def u_share(b: EraBuild) -> dict:
    """`{(date, expiry): (priced, total, awaiting)}` over the date's universe."""
    out = {}
    for d, exp, why in b.u_slot:
        if why or (d, exp) in out:
            continue
        ws = [b.u[(d, tk, exp)] for tk, _ in b.universe[d]]
        out[(d, exp)] = (sum(w.status == "built" for w in ws), len(ws),
                         sum(w.status == "await" for w in ws))
    return out


def census(b: EraBuild) -> dict:
    """Every count the floors and ARM CEN print. Reads no outcome."""
    c: dict = {"n_slots": len(b.slots), "arms": {}}
    for a in ARMS_M:
        st = Counter(w.status for w in b.m[a])
        reasons = Counter(w.reason for w in b.m[a] if w.status == "drop")
        by = defaultdict(Counter)
        for s, w in zip(b.slots, b.m[a]):
            for cut in (f"tier {s.tier}", f"{s.structure}", f"band {band_label(s.band)}"):
                by[cut][w.status] += 1
        built_dates = Counter(s.date for s, w in zip(b.slots, b.m[a]) if w.status == "built")
        open_dates = Counter(s.date for s, w in zip(b.slots, b.m[a])
                             if w.status in ("built", "await"))
        n_dep = Counter(s.date for s in b.slots)
        c["arms"][a] = dict(
            status=st, reasons=reasons, by=by,
            f1_now=sum(1 for n in built_dates.values() if n >= 1),
            f1_bound=sum(1 for n in open_dates.values() if n >= 1),
            f1_full_now=sum(1 for d, n in built_dates.items()
                            if n >= min(FLOOR1_PAIRS_LITERAL, n_dep[d])),
            f1_literal=sum(1 for n in open_dates.values() if n >= FLOOR1_PAIRS_LITERAL),
            f2=tier_unbuildable(b.slots, b.m[a]),
            bands=Counter(band_label(s.band) for s, w in zip(b.slots, b.m[a])
                          if w.status == "built"),
            pairs_now=st["built"], pairs_bound=st["built"] + st["await"],
        )
    shares = u_share(b)
    per_date = defaultdict(list)
    for (d, _e), (pr, tot, _aw) in shares.items():
        per_date[d].append(pr / tot if tot else 0.0)
    bound = defaultdict(list)
    for (d, _e), (pr, tot, aw) in shares.items():
        bound[d].append((pr + aw) / tot if tot else 0.0)
    c["u"] = dict(
        slot_reasons=Counter(w for _d, _e, w in b.u_slot),
        dates_no_universe=sorted({d for d, v in b.universe.items() if v is None}),
        wraps=Counter(w.status for w in b.u.values()),
        wrap_reasons=Counter(w.reason for w in b.u.values() if w.status != "built"),
        median_share=statistics.median([min(v) for v in per_date.values()])
        if per_date else None,
        median_share_bound=statistics.median([min(v) for v in bound.values()])
        if bound else None,
        universe_size=statistics.median([len(v) for v in b.universe.values() if v])
        if any(b.universe.values()) else None,
    )
    return c


#: Drops by the registered scope (h >= 180, h < 7) apply to every tier alike
#: and are not a liquidity selection, so floor 2 does not count them.
SCOPE_DROPS = ("dte_ge_180", "dte_lt_7")


def tier_unbuildable(slots, wraps) -> dict:
    """Floor 2: share of a tier's in-scope picks DROPPED (structurally
    unbuildable), over in-scope picks that are built or dropped. Awaiting
    picks are not counted either way. `{tier: (dropped, decided)}`."""
    out: dict = {}
    for s, w in zip(slots, wraps):
        if w.status == "await" or s.drop in SCOPE_DROPS:
            continue
        dr, n = out.get(s.tier, (0, 0))
        out[s.tier] = (dr + (w.status == "drop"), n + 1)
    return out


def tier_gap(f2: dict) -> float | None:
    shares = [dr / n for dr, n in f2.values() if n]
    return (max(shares) - min(shares)) if len(shares) > 1 else None


def fetch_targets(builds: list[EraBuild], arms=("M1", "M2", "M2L", "U")) -> list[dict]:
    """Unique uncached call contracts the awaiting pairs name, with the arm
    that first named each. `scripts/collector/fetch_mechanical_legs.py`
    fetches these; a re-run after a fetch re-targets from the new cache."""
    seen: dict = {}
    for b in builds:
        for a in arms:
            ws = b.u.values() if a == "U" else b.m[a]
            for w in ws:
                if w.status != "await":
                    continue
                for tk, exp, k in w.fetch:
                    key = (tk, exp, round(float(k), 4))
                    seen.setdefault(key, f"{a}:{b.era}")
    return [dict(ticker=tk, expiration=exp, strike=k, opt_type="Call", category=cat)
            for (tk, exp, k), cat in sorted(seen.items())]


def tickers_without_underlying(builds: list[EraBuild]) -> list[str]:
    return sorted({tk for b in builds for (_d, tk, _e), w in b.u.items()
                   if w.status == "await" and w.reason == "no_underlying_known"})


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def g2_blind(b: EraBuild, chain, evidence) -> list[str]:
    """Every M choice re-run on a cache cut at the signal date must agree."""
    bad = []
    for s, w1, w2, w3 in zip(b.slots, b.m["M1"], b.m["M2"], b.m["M2L"]):
        if s.drop:
            continue
        cut = AsOfChain(chain, s.signal)
        legs = list(s.rec["t"].legs)
        spot = pick_spot(cut, UniverseSpot(cut), s)
        again = {
            "M1": select_m1(cut, evidence, s.ticker, s.expiry, spot, s.signal),
            "M2": select_m2(cut, evidence, s.ticker, s.expiry, spot,
                            net_delta_target(cut, legs, s.signal), s.signal),
            "M2L": select_m2(cut, evidence, s.ticker, s.expiry, spot,
                             bought_delta_target(cut, legs, s.signal), s.signal),
        }
        for a, w in (("M1", w1), ("M2", w2), ("M2L", w3)):
            if w.status == "await":
                continue
            r = again[a]
            same = (r.k_long, r.k_short) == (w.k_long, w.k_short) or \
                (w.status == "drop" and r.status == "drop")
            if not same:
                bad.append(f"{a} {s.date} {s.ticker}: full {w.k_long}/{w.k_short} "
                           f"vs cut {r.k_long}/{r.k_short}")
    return bad


def g4_pairing(b: EraBuild) -> list[str]:
    """Every arm accounts for every slot: built + dropped + awaiting = deployed."""
    bad = []
    for a in ARMS_M:
        if len(b.m[a]) != len(b.slots):
            bad.append(f"{a}: {len(b.m[a])} wraps for {len(b.slots)} slots")
    return bad


def g5_mirror(records_t: list[dict], chain, sim_cfg) -> tuple[int, list[str]]:
    """The builder at a stored row's OWN strikes reproduces it
    (`narrow_to_fit.reproduces`), on the commission-only rows."""
    tried = [r for r in records_t
             if (r["t"].row.get("cost_basis") or "") == "commission_only"]
    fails = []
    for r in tried:
        ok, why = NTF.reproduces(r, chain, sim_cfg)
        if not ok:
            fails.append(f"{r['date']} {r['ticker']}: {why}")
    return len(tried), fails


# ════════════════════════════════════════════════════════════════════════════
# Outcomes — only after the census passes (per arm, see FLOORS BY ARM)
# ════════════════════════════════════════════════════════════════════════════

def profile_for(rec_like: dict, basis: str) -> dict:
    """Exit profile: `headline` = DEBIT_PROD for every row (G3, registered);
    `own` = the row's §5 row (credit -> CREDIT_PROD, mech BEAR_HE debit ->
    the trail row, else DEBIT_PROD)."""
    if basis == "headline":
        return DEBIT_PROD
    if rec_like.get("credit"):
        return CREDIT_PROD
    if rec_like.get("mech_cell") == "BEAR_HE":
        return BEAR_HE_PROD
    return DEBIT_PROD


def replay_R(t: Trade, prof: dict) -> tuple[float, float]:
    """`(R, E)` on the trade cut at its data end. E = the last priced mark."""
    bt = bounded(t)
    r = replay(bt, **prof)["pnl_pct"]
    marks = [m for m in bt.marks if m is not None]
    return r, bt.pnl_of(marks[-1])


def trade_of(row: dict) -> Trade:
    """The harness Trade of a counterpart row, at the registered 1 lot."""
    return Trade(dict(row, contracts=1))


def pair_rows(b: EraBuild, arm: str, basis: str) -> list[dict]:
    out = []
    for s, w in zip(b.slots, b.m[arm]):
        if w.status != "built":
            continue
        rt, et = replay_R(s.rec["t"], profile_for(s.rec, basis))
        rc, ec = replay_R(trade_of(w.row), profile_for(
            {"credit": False, "mech_cell": s.rec.get("mech_cell")}, basis))
        out.append(dict(date=s.date, ticker=s.ticker, tier=s.tier,
                        structure=s.structure, band=band_label(s.band),
                        model_dir=s.rec.get("model_dir"), R_T=rt, R_C=rc,
                        E_T=et, E_C=ec, k_long=w.k_long, k_short=w.k_short))
    return out


def u_rows(b: EraBuild, basis: str) -> tuple[list[dict], dict, set]:
    """ARM U per slot: R_T and the EXPECTED random wrap (mean over the
    priceable universe, which is what redraw-until-priceable samples from).
    Returns `(rows, pools, unusable_dates)`; `pools[i]` lists the slot's
    priceable universe R values for the draws."""
    shares = u_share(b)
    unusable = {d for (d, _e), (pr, tot, _aw) in shares.items()
                if not tot or 1 - pr / tot > U_REDRAW_CAP}
    rows, pools, memo = [], {}, {}
    for s, (d, exp, why) in zip(b.slots, b.u_slot):
        if why or d in unusable:
            continue
        pool = []
        for tk, sec in b.universe[d]:
            w = b.u[(d, tk, exp)]
            if w.status != "built":
                continue
            key = (d, tk, exp, s.rec.get("mech_cell"), basis)
            if key not in memo:
                memo[key] = replay_R(trade_of(w.row), profile_for(
                    {"credit": False, "mech_cell": s.rec.get("mech_cell")}, basis))[0]
            pool.append((memo[key], sec))
        if not pool:
            continue
        rt, _et = replay_R(s.rec["t"], profile_for(s.rec, basis))
        pools[len(rows)] = [v for v, _ in pool]
        rows.append(dict(date=d, ticker=s.ticker, tier=s.tier, structure=s.structure,
                         band=band_label(s.band), model_dir=s.rec.get("model_dir"),
                         R_T=rt, R_C=statistics.fmean(v for v, _ in pool),
                         R_C_etf=_mean([v for v, sec in pool if sec == "etfs"]),
                         R_C_stock=_mean([v for v, sec in pool if sec == "stocks"])))
    return rows, pools, unusable


def _mean(v):
    return statistics.fmean(v) if v else None


def u_band(rows: list[dict], pools: dict, draws: int = U_DRAWS,
           seed: int = U_SEED) -> tuple[float, float, list[float]]:
    """`(p5, p95, means)` of the random book's mean R over `draws` seeded
    replications, one ticker drawn per slot from its priceable universe."""
    rng = random.Random(seed)
    means = []
    for _ in range(draws):
        vals = [rng.choice(pools[i]) for i in range(len(rows))]
        means.append(statistics.fmean(vals))
    srt = sorted(means)
    return srt[int(0.05 * draws)], srt[min(draws - 1, int(0.95 * draws))], means


def grade(rows: list[dict]) -> dict:
    """C0-C2 and the headline line for one arm's paired rows."""
    dates = {r["date"] for r in rows}
    g = dict(n=len(rows), dates=len(dates),
             c0=len(dates) >= C0_MIN_DATES and len(rows) >= C0_MIN_PAIRS)
    if not g["c0"]:
        return g
    g["mean_T"] = statistics.fmean(r["R_T"] for r in rows)
    g["mean_C"] = statistics.fmean(r["R_C"] for r in rows)
    g["gain"] = g["mean_T"] - g["mean_C"]
    g["ci"] = P.boot_ci_paired_by_date(rows, "R_T", "R_C")
    g["c1"] = g["ci"][0] > 0
    g["contrary"] = g["ci"][1] < 0
    loo = P.loo_by_date(rows, lambda r: r["R_T"], lambda r: r["R_C"])
    g["loo"] = loo
    g["c2"] = loo[1] == 1.0
    a = [dict(date=r["date"], R=r["R_T"]) for r in rows]
    c = [dict(date=r["date"], R=r["R_C"]) for r in rows]
    g["pf_T"], g["pf_C"] = P.pf(a), P.pf(c)
    g["pf_diff"] = P.pf_paired_by_date(a, c)
    g["tier_gain"] = {t: statistics.fmean(r["R_T"] - r["R_C"] for r in rows
                                          if r["tier"] == t)
                      for t in ("A", "B") if any(r["tier"] == t for r in rows)}
    tg = g["tier_gain"]
    g["c4"] = ("A" in tg and "B" in tg) and tg["A"] >= tg["B"]
    return g


def verdict(gm1: dict, gm2: dict, gu: dict, c5: bool) -> str:
    """The registration's worded verdicts, in its own precedence."""
    def clears(g, upto):
        return g.get("c0") and all(g.get(f"c{i}") for i in range(1, upto + 1))
    if not any(g.get("c0") for g in (gm1, gm2, gu)):
        return "UNDERPOWERED"
    if any(g.get("contrary") for g in (gm1, gm2, gu)):
        return "CONTRARY"
    u_ok = clears(gu, 3)
    m_ok = clears(gm1, 2) or clears(gm2, 2)
    if u_ok and gu.get("c4") and c5:
        return "SELECTION-CONFIRMED"
    if m_ok and not u_ok:
        return "STRUCTURE-ONLY"
    if u_ok and not m_ok:
        return "BASE-RATE"
    if not any(g.get("c1") for g in (gm1, gm2, gu) if g.get("c0")):
        return "NULL"
    return "UNWORDED"


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def print_census(b: EraBuild, c: dict) -> None:
    hdr(f"ARM CEN — census, era {b.era} (counts only)")
    print(f"  {b.seal}")
    print(f"  deployed picks (top-{K_DEPLOY}/day, Tier A/B): {c['n_slots']} on "
          f"{len({s.date for s in b.slots})} dates")
    for a in ARMS_M:
        x = c["arms"][a]
        st = x["status"]
        print(f"\n  {a}: built {st['built']}  awaiting fetch {st['await']}  "
              f"dropped {st['drop']}")
        for why, n in x["reasons"].most_common():
            print(f"      dropped {why:<34} {n:>5}")
        print("      cut                          built  await  drop")
        for cut in sorted(x["by"]):
            s = x["by"][cut]
            print(f"      {cut:<28} {s['built']:>6} {s['await']:>6} {s['drop']:>5}")
    u = c["u"]
    slots = "  ".join(f"{k or 'usable'}={v}" for k, v in u["slot_reasons"].most_common())
    print(f"\n  U: slots {slots}")
    print("     universe wraps: " + "  ".join(f"{k}={v}" for k, v in u["wraps"].items()))
    for why, n in u["wrap_reasons"].most_common():
        print(f"      not built: {why:<34} {n:>6}")
    if u["dates_no_universe"]:
        print(f"     dates with no universe file: {len(u['dates_no_universe'])} "
              f"({u['dates_no_universe'][0]} .. {u['dates_no_universe'][-1]})")
    print(f"     median universe size {u['universe_size']}")


#: Resolved at build (2026-10-13): the same-ticker arms are read without
#: ARM U. Floors 1, 2 and 4a gate them; floors 3 and 4b gate only ARM U
#: and every criterion graded on it (C3, C4, C5) and the study-level verdict.
SAME_TICKER_ARMS = ARMS_M
SAME_TICKER_READ = "SAME-TICKER READ — ARM U NOT BUILT"
GATES_ALL = "[gates every arm]"
GATES_SAME = "[gates M1 M2 M2L]"
GATES_U = "[gates ARM U and the study verdict]"


def _worse(a: str, b: str) -> str:
    order = ("PASS", "AWAITING", "FAIL")
    return max(a, b, key=order.index)


def floors(c: dict, n_fetch: int) -> tuple[str, str, list[str]]:
    """`(same, u, lines)`, each state PASS | AWAITING | FAIL (FAIL is
    definitive: even if every awaiting pair priced, a floor could not be met).
    `same` gates the same-ticker arms (floors 1, 2, 4a). `u` gates ARM U and
    the study-level verdict: it is `same` worsened by floors 3 and 4b."""
    lines = []
    m1 = c["arms"]["M1"]
    m_await = m1["status"]["await"] + c["arms"]["M2"]["status"]["await"]
    same = u_only = "PASS"

    def mark(now_ok, bound_ok):
        if not bound_ok:
            return "FAIL", "FAIL"
        return ("AWAITING", "PENDING") if not now_ok else ("PASS", "pass")

    st1, f1 = mark(m1["f1_now"] >= FLOOR1_MIN_DATES, m1["f1_bound"] >= FLOOR1_MIN_DATES)
    same = _worse(same, st1)
    lines.append(f"  1  dates with >= 1 priced M1 pair (headline)     now {m1['f1_now']:>4}  "
                 f"if fetched <= {m1['f1_bound']:>4}  need {FLOOR1_MIN_DATES}  {f1}  "
                 f"{GATES_ALL}")
    lines.append(f"     declared secondary: dates whose every deployed pick is paired "
                 f"{m1['f1_full_now']}; dates with >= {FLOOR1_PAIRS_LITERAL} pairs "
                 f"(literal, k={K_DEPLOY}) <= {m1['f1_literal']}")
    gap = tier_gap(m1["f2"])
    f2s = "  ".join(f"{t} {dr}/{n}" for t, (dr, n) in sorted(m1["f2"].items()))
    if gap is None:
        f2 = "PENDING"
        same = _worse(same, "AWAITING")
    elif m1["status"]["await"]:
        f2 = "PENDING (provisional gap; awaiting pairs undecided)"
        same = _worse(same, "AWAITING")
    else:
        f2 = "pass" if gap <= FLOOR2_MAX_TIER_GAP else "FAIL"
        if f2 == "FAIL":
            same = "FAIL"
    lines.append(f"  2  M1 in-scope dropped share by tier  {f2s}  gap "
                 f"{'n/a' if gap is None else f'{gap:.3f}'}  max {FLOOR2_MAX_TIER_GAP}  {f2}  "
                 f"{GATES_ALL}")
    u = c["u"]
    need = 1 - U_REDRAW_CAP
    now, bound = u["median_share"], u["median_share_bound"]
    st3, f3 = mark(now is not None and now >= need, bound is not None and bound >= need)
    u_only = _worse(u_only, st3)
    lines.append(f"  3  median priceable share of the day's universe  now "
                 f"{'n/a' if now is None else f'{now:.3f}'}  if fetched <= "
                 f"{'n/a' if bound is None else f'{bound:.3f}'}  need {need:.2f}  {f3}  "
                 f"{GATES_U}")
    if m_await:
        same = _worse(same, "AWAITING")
    lines.append(f"  4a M1/M2 pairs awaiting a fetch {m_await}  "
                 f"{'pass' if not m_await else 'NEEDS OPERATOR-RUN FETCH'}  {GATES_SAME}")
    if n_fetch:
        u_only = _worse(u_only, "AWAITING")
    lines.append(f"  4b contracts still to fetch, every arm {n_fetch} (one feed request "
                 f"each); U wraps awaiting {u['wraps'].get('await', 0)}  "
                 f"{'pass' if n_fetch == 0 else 'NEEDS OPERATOR-RUN FETCH'}  {GATES_U}")
    bands = m1["bands"]
    lines.append("  5  M1 pairs by band  " + "  ".join(
        f"{band_label(bd)} {bands.get(band_label(bd), 0)}"
        f"{'' if bands.get(band_label(bd), 0) >= FLOOR5_MIN_BAND_PAIRS else ' (not read)'}"
        for bd in BANDS) + "  (no floor)")
    return same, _worse(same, u_only), lines


def study_word(same: str, u: str) -> str | None:
    """The census verdict word, or None when every floor passes and the full
    outcome path runs. Floors 1 and 2 kill the whole study; floors 3 and 4b
    hold back only ARM U, so the same-ticker arms are read without it."""
    if same == "FAIL":
        return "NOT BUILT"
    if same == "AWAITING":
        return "NOT BUILT — AWAITING SCRAPE"
    if u != "PASS":
        return SAME_TICKER_READ
    return None


def print_grade(name: str, g: dict, gross_note: str) -> None:
    if not g.get("c0"):
        print(f"  {name:<5} UNDERPOWERED — {g['n']} pairs on {g['dates']} dates "
              f"(needs {C0_MIN_PAIRS} and {C0_MIN_DATES}); no outcome printed")
        return
    lo, hi = g["ci"]
    pfd = g["pf_diff"]
    pf_t = "n/a" if g["pf_T"] is None else f"{g['pf_T']:.2f}"
    pf_c = "n/a" if g["pf_C"] is None else f"{g['pf_C']:.2f}"
    print(f"  {name:<5} pairs {g['n']:>4} dates {g['dates']:>4}  meanR T {g['mean_T']:+.3f} "
          f"C {g['mean_C']:+.3f}  gain {g['gain']:+.3f} [{lo:+.3f}, {hi:+.3f}]  "
          f"PF T {pf_t} C {pf_c}  {gross_note}")
    print(f"        LOO share positive {g['loo'][1]:.2f} min {g['loo'][2]:+.3f}  "
          f"C1 {'Y' if g['c1'] else 'n'} C2 {'Y' if g['c2'] else 'n'}  "
          f"tier gain " + "  ".join(f"{t} {v:+.3f}" for t, v in g["tier_gain"].items())
          + f"  C4 {'Y' if g['c4'] else 'n'}"
          + (f"  PF diff {pfd[0]:+.2f} [{pfd[1]:+.2f}, {pfd[2]:+.2f}]"
             if pfd[0] is not None else ""))


def awaits(b: EraBuild, arm: str) -> bool:
    """True while any of the arm's pairs awaits a fetch: its built pairs are
    then the cached subset, not the registered population."""
    return any(w.status == "await" for w in b.m[arm])


def arm_criteria(g: dict) -> str:
    """One arm's C0-C2 and CONTRARY condition, the per-arm read
    `programme_gate`'s PG-M consumes."""
    yn = lambda v: "Y" if v else "n"     # noqa: E731
    return (f"C0 {yn(g.get('c0'))}  C1 {yn(g.get('c1'))}  C2 {yn(g.get('c2'))}  "
            f"clears C0-C2 {yn(g.get('c0') and g.get('c1') and g.get('c2'))}  "
            f"CONTRARY {yn(g.get('contrary'))}")


def print_same_ticker_verdict(g: dict) -> None:
    """The verdict block while ARM U is not built: per-arm criteria only.
    No study-level token prints, because each of them reads ARM U too."""
    hdr(f"VERDICT (headline basis): {SAME_TICKER_READ}")
    for a in ("M1", "M2"):
        print(f"  ARM {a:<3} {arm_criteria(g[a])}")
    print("  ARM U is not built, so no study-level verdict prints: every one of them")
    print("  also says something about ARM U. C3, C4 and C5 are graded on ARM U and")
    print("  are not read.")
    hit = [a for a in ("M1", "M2") if g[a].get("contrary")]
    if hit:
        print(f"  CONTRARY condition met on ARM {', ARM '.join(hit)}: surface to the "
              f"operator before any further study runs.")
    print("  M2L is a declared secondary and carries no verdict.")


def write_pairs(rows_by_arm: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["arm", "date", "ticker", "tier", "structure", "band", "model_dir",
            "R_T", "R_C", "E_T", "E_C", "k_long", "k_short"]
    with PAIRS_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for arm, rows in rows_by_arm.items():
            for r in rows:
                w.writerow(dict(r, arm=arm))


FETCH_CMD = "python3 scripts/collector/fetch_mechanical_legs.py"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-v3", action="store_true",
                    help="skip the v3 era-stability read (C5 then reads as unmet)")
    args = ap.parse_args(argv)
    logging.getLogger("backtest").setLevel(logging.ERROR)
    logging.getLogger("scripts.backtest").setLevel(logging.ERROR)

    hdr("mechanical_benchmark — do the picks beat a mechanical bull call spread?")
    print("""  Registration research/pre-registrations/f1_selection/benchmark/mechanical_benchmark.md
  (accepted by default 2026-10-09). NOTHING SHIPS FROM THIS STUDY.
  Both books GROSS of costs (cost_sensitivity has not landed). No annualised
  figure, Sharpe or time-to-recover is printed (G6); every count is computed
  by this run (G7). Same-ticker outcomes (M1, M2, M2L) print once floors 1,
  2 and 4a pass; ARM U and the study verdict also need floors 3 and 4b.""")

    chain = NTF.Chain()
    evidence = NTF.unlisted_evidence()
    sim_cfg = NTF._sim_cfg()

    records, diag = load_book(include_bs=False)
    print(f"\n  G1 era {diag.get('era')}  book {len(records)} rows  "
          f"{diag.get('n_dates')} dates  {diag.get('date_range')}")
    eras = [("primary", None, records)]
    if not args.no_v3:
        try:
            v3, d3 = load_book(era="v3", include_bs=False)
            print(f"  G1 era {d3.get('era')} (C5 stability read)  book {len(v3)} rows  "
                  f"{d3.get('n_dates')} dates")
            eras.append(("v3", "v3", v3))
        except SystemExit as exc:
            print(f"  v3 era refused (exit {exc.code}); C5 reads as unmet")

    builds = []
    for label, name, recs in eras:
        builds.append(build_era(name, chain, evidence, sim_cfg, records=recs))

    cens = [census(b) for b in builds]
    for b, c in zip(builds, cens):
        print_census(b, c)

    targets = fetch_targets(builds)
    no_und = tickers_without_underlying(builds)
    no_uni = sorted({d for c in cens for d in c["u"]["dates_no_universe"]})

    hdr("CENSUS FLOORS (registration §Dependencies)")
    states = {}
    for b, c in zip(builds, cens):
        n_era = len([t for t in targets if t["category"].endswith(f":{b.era}")])
        same, full, lines = floors(c, n_era)
        states[b.era] = (same, full)
        print(f"  era {b.era}: same-ticker arms (M1 M2 M2L) {same}  ·  ARM U {full}")
        for ln in lines:
            print(ln)
    by_cat = Counter(t["category"] for t in targets)
    cats = "  ".join(f"{k}={v}" for k, v in sorted(by_cat.items()))
    print(f"\n  fetch plan: {len(targets)} unique uncached call contracts  {cats}")
    print(f"  universe tickers with no underlying known (need stock bars first): "
          f"{len(no_und)}")
    print(f"  signal dates with no universe file: {len(no_uni)}")

    word = study_word(*states[builds[0].era])
    if word and word != SAME_TICKER_READ:
        hdr(f"VERDICT: {word}")
        print("  The census is the recorded result. No outcome column was read.")
        print("  Operator-run steps, in order (each resumable; none runs from here):")
        if no_uni:
            print(f"    0. universe files for {len(no_uni)} dates: "
                  f"python3 -m scripts.analysis_pipeline --skip-llm --date <D> "
                  f"(no LLM, no Sheets write)")
        if no_und:
            print(f"    1. stock bars for {len(no_und)} universe tickers: "
                  f"python3 scripts/collector/fetch_underlying_ohlc.py --tickers "
                  f"<list from {FETCH_CMD} --list-underlying>")
        print(f"    2. option legs: {FETCH_CMD} --dry-run   (then --limit N)")
        print("    3. python3 scripts/backup_research_caches.py push")
        print("    4. re-run this study; a fetch can expose nearer strikes, so "
              "steps 2-4 repeat until nothing awaits")
        return 0

    # ── gates before any outcome ─────────────────────────────────────────────
    hdr("GATES")
    ok = True
    for b in builds:
        bad = g2_blind(b, chain, evidence)
        print(f"  G2 NO LOOK-AHEAD ({b.era}): {'PASS' if not bad else 'FAIL'}"
              f"  {len(bad)} choices differ on a cache cut at the signal date")
        for x in bad[:10]:
            print(f"     {x}")
        ok &= not bad
        bad4 = g4_pairing(b)
        print(f"  G4 PAIRING ({b.era}): {'PASS' if not bad4 else 'FAIL'}")
        ok &= not bad4
    print(f"  G3 EXIT PARITY: one harness call per side, headline profile "
          f"{DEBIT_PROD} on both sides, path cap from the harness")
    n5, f5 = g5_mirror([s.rec for s in builds[0].slots if not s.drop], chain, sim_cfg)
    print(f"  G5 PRICING MIRROR: {n5} commission-only picks re-built at their own "
          f"strikes, {len(f5)} differ  {'PASS' if not f5 else 'FAIL'}")
    for x in f5[:10]:
        print(f"     {x}")
    ok &= not f5
    srcs = Counter(s.rec["source"] for b in builds for s in b.slots)
    print(f"  G5 TIERS: sources {dict(srcs)}  {'PASS' if 'bs' not in srcs else 'FAIL'}")
    ok &= "bs" not in srcs
    if not ok:
        print("\nGATE FAILURE — no outcome printed. Exit 1.")
        return 1

    # ── outcomes ──────────────────────────────────────────────────────────────
    results = {}
    for basis in ("headline", "own"):
        title = ("HEADLINE — DEBIT_PROD on both sides (registered)" if basis == "headline"
                 else "DECLARED SECONDARY — each side under its own §5 row")
        hdr(f"OUTCOMES, {title}. GROSS of costs.")
        for b in builds:
            same, full = states[b.era]
            read_m = same == "PASS"
            read_u = full == "PASS" and word is None
            arms = [a for a in ARMS_M if read_m and not awaits(b, a)]
            rows = {a: pair_rows(b, a, basis) for a in arms}
            g = {a: grade(rows[a]) for a in arms}
            print(f"\n  era {b.era}  (ARM CEN table above)")
            if not read_m:
                print(f"  same-ticker floors {same}: no outcome printed for this era")
            for a in ARMS_M:
                if a in arms:
                    print_grade(a, g[a], "GROSS")
                elif read_m:
                    print(f"  {a:<5} not graded: pairs await a fetch")
            urows = []
            if read_u:
                urows, pools, unusable = u_rows(b, basis)
                g["U"] = grade(urows)
                print_grade("U", g["U"], "GROSS")
            else:
                print(f"  U     not graded: ARM U floors {full} (floors 3 and 4b)")
            if g.get("U", {}).get("c0"):
                p5, p95, _ = u_band(urows, pools)
                mt = g["U"]["mean_T"]
                g["U"]["c3"] = mt > p95
                for sec in ("etf", "stock"):
                    vals = [r["R_T"] - r[f"R_C_{sec}"] for r in urows
                            if r[f"R_C_{sec}"] is not None]
                    if vals:
                        print(f"  U {sec} universe only: {len(vals)} slots, mean paired "
                              f"gain {statistics.fmean(vals):+.3f} (descriptive)")
                print(f"  U band [p5, p95] of the random book's meanR over {U_DRAWS} "
                      f"draws (seed {U_SEED}): [{p5:+.3f}, {p95:+.3f}]  picks "
                      f"{mt:+.3f}  C3 {'Y' if g['U']['c3'] else 'n'}  unusable dates "
                      f"{len(unusable)}")
            for a in [x for x in ("M1", "U") if x in g]:
                cuts = P.window_cuts(rows[a] if a != "U" else urows)
                for name, rs in cuts.items():
                    if name == "ALL":
                        continue
                    gg = grade(rs)
                    print_grade(f"{a} {name}"[:5], gg, f"GROSS {name}")
                bear = [r for r in (rows[a] if a != "U" else urows)
                        if r.get("model_dir") == "BEAR"]
                print(f"  {a} bear-regime subset: {len(bear)} pairs")
                if len(bear) >= C0_MIN_PAIRS:
                    print_grade(f"{a}bear"[:5], grade(bear), "GROSS")
            results[(basis, b.era)] = g
            if basis == "headline" and b is builds[0]:
                write_pairs({**rows, **({"U": urows} if read_u else {})})

    g0 = results[("headline", builds[0].era)]
    if word == SAME_TICKER_READ:
        print_same_ticker_verdict(g0)
        print(f"  pairs written to {PAIRS_CSV.relative_to(ROOT)} (no ARM U rows)")
        return 0
    c5 = False
    if len(builds) > 1:
        gv = results[("headline", builds[1].era)]
        c5 = all(g0[a].get("c1") and gv.get(a, {}).get("c1")
                 and (g0[a]["gain"] > 0) == (gv[a]["gain"] > 0) for a in ("U",))
    word = verdict(g0["M1"], g0["M2"], g0["U"], c5)
    hdr(f"VERDICT (headline basis): {word}")
    print(f"  C5 era stability on ARM U: {'Y' if c5 else 'n'}. M2L is a declared "
          f"secondary and carries no verdict.")
    print(f"  pairs written to {PAIRS_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
