"""
Fetcher for the option legs `structure_sweep`'s second sample (S2) needs.

WHY THIS EXISTS
---------------
`structure_sweep` (research/pre-registrations/f3_structure/structure_sweep.md,
accepted by default 2026-10-22) re-wraps each 2026 real-priced play in eight
other structures: flipped, type-swapped, short and long condors, butterfly,
straddle, strangle and a call calendar. The option cache holds only the
strikes the book traded, so most rows cannot price most arms. S1 prices what
the cache already holds; S2 is whatever a later fetch makes priceable, and
this is that fetch. DRY-RUN BY DEFAULT: `--live` is the only flag that touches
the network.

THE ROWS
--------
`load_book()` at its defaults (era v4, seal applied), `source == real`, signal
date in 2026. Entry day = production's fill day, `bear_rewrap.recorded_entry_date`
(read off `dte_entry`, never re-derived). Expiry = the play's own front expiry.
Spot = the most common positive `Price~` across the entry day's cached rows for
that ticker and expiry (`index_vrp.Chain.spot`).

WHAT IS TARGETED (the registration's strike rules, on entry-day rows only)
--------------------------------------------------------------------------
  CGS_delta  ARM C / G / S  the call and the put whose entry-day |Delta| is
                            nearest 0.16
  C_wing     ARM C          wings at the listed strike nearest short +/- 0.03 x spot
                            (call wing above the short call, put wing below
                            the short put; never on or inside the short)
  BD_atm     ARM B / D      the listed strike nearest spot with BOTH a call and
                            a put quoted on the entry day (ties lower)
  B_wing     ARM B          wings at ATM +/- 0.03 x spot, as C_wing
  K_back     ARM K          the ATM call at the nearest later expiry at least
                            14 calendar days after the front
  T_swap     ARM T          the other option type at the play's own two strikes
                            (verticals only)
ARM G and S reuse C's shorts and take no wings; ARM D reuses B's pair and
takes none. So wings are fetched for C and B only.

HOW STRIKES ARE FOUND (the earnings_vol trap, research/current.md 2026-10-12)
------------------------------------------------------------------------------
Never from a guessed grid. A strike is chosen by a PROBE WALK over candidates,
nearest first, and only a contract with an entry-day row counts as listed:
  * cached with an entry-day row            -> listed (ok)
  * cached without one                      -> not quoted yet (dead)
  * on the skip-list ON EVIDENCE            -> unlisted (dead), no network
    (`narrow_to_fit.unlisted_evidence`: `seeded_from_log` and a first
    `no_rows` do not count, so those are probed again)
  * neither                                 -> OPEN: a probe the walk needs.
ATM and wing walks use a fine ladder (`lattice`: 0.5 under $75, 1 under $300,
2.5 above, plus the standard listing step of `proxy._strike_step`; cf.
`fetch_earnings_legs.strike_ladder`) so a nearer off-grid strike is probed
rather than skipped; one round names the open contracts of up to ATM_BATCH
(WING_BATCH) candidates, stopping at the first on the standard step, like
`mechanical_benchmark.listed_fetch`.
Delta walks are `mechanical_benchmark.nearest_delta` / `delta_fetch`,
generalised to puts: a nearest-|Delta| strike `k*` is proven when the walk from
`k*` toward the target reaches a known strike without meeting an open one;
when nothing is known, Black-Scholes at the legs' entry IV (TARGETING ONLY,
never a price) names the strikes to probe. The delta and wing walks step on
`mechanical_benchmark.grid_step` (the standard step, or the chain's finer
cached spacing), so an off-grid strike finer than both is not probed there;
the ATM walk is where finer listing shows up first.

A wing needs its short and the back leg needs the ATM strike, so the walks
are staged: a run plans, fetches, re-plans from the new cache and repeats
(at most MAX_ROUNDS) until nothing is open. `--dry-run` plans round 1 for real
and PROVISIONALLY plans the dependent stages against the likely parent strike,
which is what its "est. dependent" column counts.

HOW IT FETCHES
--------------
Through `scripts.backtest.shared.history.fetch_option_histories` with
`retry_unlisted=True` (the evidence filter above has already run), so the
`HISTORY_START_DATE` pin, the atomic write, the evidence-gated skip-list, the
pause and the network-outage abort (exit 6) all apply. RESUMABLE: the cache is
the state; a re-run recomputes the plan and fetches only what is still open.
`--limit N` caps the contracts one run requests.

Shares the Barchart session with the backtest and every other collector: never
run it beside another scrape. Needs BARCHART_EMAIL/BARCHART_PASSWORD.
Research-tier, run by hand after the operator approves the dry-run count. Run
`python3 scripts/backup_research_caches.py push` after it. A cache file's
mtime is its fetch time and `structure_sweep`'s S1 reads only files at or
before the split instant: a fetch after it can never move an S1 strike.

Usage:
  python3 scripts/collector/study_legs/fetch_structure_sweep_legs.py            # dry-run
  python3 scripts/collector/study_legs/fetch_structure_sweep_legs.py --list
  python3 scripts/collector/study_legs/fetch_structure_sweep_legs.py --live --limit 200
  python3 scripts/collector/study_legs/fetch_structure_sweep_legs.py --groups BD_atm,B_wing
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path  # noqa: E402
from lib.logger import setup_logging  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _contract_key  # noqa: E402
from scripts.backtest.proxy import _strike_step  # noqa: E402
from scripts.backtest.shared import unlisted as UL  # noqa: E402
from scripts.backtest.shared.history import (  # noqa: E402
    EXIT_NETWORK_OUTAGE, NetworkOutage, fetch_option_histories,
)
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f3_structure.bear_rewrap import recorded_entry_date  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

log = logging.getLogger("fetch_structure_sweep_legs")

# --- registered constants (structure_sweep.md) -------------------------------
SHORT_DELTA = 0.16            # ARM C / G / S shorts
WING_FRAC = 0.03              # wings at short +/- 0.03 x spot
BACK_GAP_DAYS = 14            # ARM K back expiry >= front + 14 calendar days

# --- fetch-order and bound knobs (never change what the study builds) --------
#: Finest strike increment a candidate walk probes, by spot: the half-dollar
#: strikes of cheap names, the dollar strikes of $75-300 names, then 2.5. The
#: standard listing step (`proxy._strike_step`) is always a candidate as well.
LATTICE_BY_SPOT = ((75.0, 0.5), (300.0, 1.0), (math.inf, 2.5))
ATM_BAND = 0.05               # ATM candidates within 5% of spot
WING_HALF = 0.01              # wing candidates within 1% of spot of the target (and >= 4 steps)
ATM_BATCH = 3                 # unresolved ATM candidates named per round, at most
WING_BATCH = 2                # unresolved wing candidates named per round, at most
NO_KNOWN_WIDTH = 3            # open strikes named when a delta walk knows nothing yet
BACK_BATCH = 3                # unresolved back expiries named per round
BACK_REACH_DAYS = 35          # back candidates up to front + 14 + 35
MAX_ROUNDS = 8
SECONDS_PER_CONTRACT = 2.1    # median gap in the repo's fetch manifests + the 0.4 s sleep
DEFAULT_IV = 40.0             # points; only if no leg, chain or row IV is readable

GROUPS = ("CGS_delta", "C_wing", "BD_atm", "B_wing", "K_back", "T_swap")
SERVES = {"CGS_delta": "C G S", "C_wing": "C", "BD_atm": "B D", "B_wing": "B",
          "K_back": "K", "T_swap": "T"}

OK, NOQUOTE, UNLISTED, FAILED, OPEN = "ok", "not_quoted", "unlisted", "failed", "open"
DEAD = frozenset({NOQUOTE, UNLISTED, FAILED})

BACKUP_REMINDER = ("Next: python3 scripts/backup_research_caches.py push  "
                   "(the scraped cache has no other copy)")

Contract = tuple  # (ticker, expiry: date, strike: float, "Call" | "Put")


def stem_of(c: Contract) -> str:
    return NTF.contract_stem(c[0], c[1], c[2], c[3])


# =============================================================================
# The cache, read the way the walks need it
# =============================================================================

class Cache:
    """Directory index + lazy per-file reads + the skip-list evidence.

    `state()` is the one classification every walk uses. `attempted` holds the
    stems this run already requested: one that is still neither a file nor
    evidence is FAILED for the rest of the run (a first `no_rows`, a network
    error), so a run never asks twice."""

    def __init__(self, cache_dir: Path = HISTORY_CACHE,
                 evidence: Iterable[str] | None = None,
                 attempted: set[str] | None = None):
        self.dir = Path(cache_dir)
        self._evidence = None if evidence is None else set(evidence)
        self.attempted = attempted if attempted is not None else set()
        self._files: dict[Path, dict] = {}
        self.refresh()

    @property
    def evidence(self) -> set[str]:
        if self._evidence is None:
            self._evidence = NTF.unlisted_evidence()
        return self._evidence

    def reload_evidence(self) -> None:
        self._evidence = None

    def refresh(self) -> None:
        """Re-list the directory (after a fetch). Forgets read files."""
        self._files.clear()
        idx: dict[tuple, dict[float, set]] = defaultdict(dict)
        by_ticker: dict[str, set] = defaultdict(set)
        if self.dir.exists():
            with os.scandir(self.dir) as it:
                for e in it:
                    n = e.name
                    if not n.endswith(".csv"):
                        continue
                    parts = n[:-4].split("_")
                    if len(parts) != 3 or parts[2][-1:] not in ("C", "P"):
                        continue
                    try:
                        x = date(int(parts[1][:4]), int(parts[1][4:6]), int(parts[1][6:8]))
                        k = float(parts[2][:-1])
                    except ValueError:
                        continue
                    idx[(parts[0], x)].setdefault(round(k, 4), set()).add(parts[2][-1])
                    by_ticker[parts[0]].add(x)
        self.idx, self.by_ticker = idx, by_ticker

    # -- existence --
    def has(self, t: str, x: date, k: float, typ: str) -> bool:
        return ("C" if typ == "Call" else "P") in self.idx.get((t, x), {}).get(round(k, 4), ())

    def strikes(self, t: str, x: date, typ: str | None = None) -> list[float]:
        cp = None if typ is None else ("C" if typ == "Call" else "P")
        return sorted(k for k, s in self.idx.get((t, x), {}).items() if cp is None or cp in s)

    def expiries(self, t: str) -> list[date]:
        return sorted(self.by_ticker.get(t, ()))

    # -- rows --
    def _file(self, t: str, x: date, k: float, typ: str) -> dict:
        p = cache_path(self.dir, t, x, k, typ)
        if p not in self._files:
            rows: dict[date, dict] = {}
            try:
                with open(p, newline="") as fh:
                    for r in csv.DictReader(fh):
                        try:
                            d = date.fromisoformat(str(r.get("Time", ""))[:10])
                        except ValueError:
                            continue
                        rows.setdefault(d, dict(
                            Delta=_num(r.get("Delta")), IV=_num(r.get("IV")),
                            Spot=_num(r.get("Price~"))))
            except OSError:
                pass
            self._files[p] = rows
        return self._files[p]

    def row(self, t: str, x: date, k: float, typ: str, day: date) -> dict | None:
        if not self.has(t, x, k, typ):
            return None
        return self._file(t, x, k, typ).get(day)

    def state(self, c: Contract, day: date) -> str:
        t, x, k, typ = c
        if self.has(t, x, k, typ):
            return OK if day in self._file(t, x, k, typ) else NOQUOTE
        stem = stem_of(c)
        if stem in self.evidence:
            return UNLISTED
        return FAILED if stem in self.attempted else OPEN

    def spot(self, t: str, x: date, day: date) -> float | None:
        """Most common positive `Price~` on `day` across the chain (ties to the
        lower), as `index_vrp.Chain.spot` resolves it."""
        cnt = Counter()
        for k, cps in self.idx.get((t, x), {}).items():
            for cp in cps:
                r = self.row(t, x, k, "Call" if cp == "C" else "Put", day)
                if r and r["Spot"] and r["Spot"] > 0:
                    cnt[r["Spot"]] += 1
        if not cnt:
            return None
        top = max(cnt.values())
        return min(v for v, n in cnt.items() if n == top)


def _num(v) -> float | None:
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# =============================================================================
# Targeting arithmetic (pure) — Black-Scholes names strikes, never prices
# =============================================================================

_ND = statistics.NormalDist()


def _clip(p: float) -> float:
    return min(max(p, 1e-4), 1 - 1e-4)


def bs_target_strike(spot: float, iv_pts: float, days: int, abs_delta: float,
                     typ: str) -> float:
    """The strike whose Black-Scholes |delta| is `abs_delta` (r = 0).

    d1 = N^-1(delta) for a call and -N^-1(|delta|) for a put;
    ln(K/S) = sigma^2 T / 2 - d1 sigma sqrt(T). TARGETING ONLY."""
    sig = max(iv_pts, 1.0) / 100.0
    t = max(days, 1) / 365.0
    z = _ND.inv_cdf(_clip(abs_delta))
    d1 = z if typ == "Call" else -z
    return spot * math.exp(sig * sig * t / 2.0 - d1 * sig * math.sqrt(t))


def bs_shift_strike(k0: float, d0: float, target: float, iv_pts: float, days: int,
                    typ: str) -> float:
    """Move from a strike with known |delta| `d0` to the strike with `target`
    (same IV): the secant-free estimate `mechanical_benchmark.delta_fetch` uses,
    for either type. |delta| falls with strike for a call and rises for a put."""
    sig_t = max(iv_pts, 1.0) / 100.0 * math.sqrt(max(days, 1) / 365.0)
    dz = _ND.inv_cdf(_clip(d0)) - _ND.inv_cdf(_clip(target))
    return k0 * math.exp((dz if typ == "Call" else -dz) * sig_t)


def lattice(spot: float) -> float:
    """The finest strike increment probed at this price."""
    for cap, inc in LATTICE_BY_SPOT:
        if spot < cap:
            return inc
    return LATTICE_BY_SPOT[-1][1]


def ladder(target: float, half_width: float, spot: float,
           extra: Iterable[float] = ()) -> list[float]:
    """Candidate strikes within `half_width` of `target`, nearest first (ties
    lower): every multiple of `lattice(spot)` and of the standard step, plus
    any cached strike in range."""
    lo, hi = target - half_width, target + half_width
    pts = {round(k, 4) for k in extra if lo - 1e-9 <= k <= hi + 1e-9}
    for inc in {lattice(spot), _strike_step(spot)}:
        n = math.ceil(lo / inc - 1e-9)
        while n * inc <= hi + 1e-9:
            if n * inc > 0:
                pts.add(round(n * inc, 4))
            n += 1
    return sorted(pts, key=lambda k: (round(abs(k - target), 6), k))


def on_std_grid(k: float, spot: float) -> bool:
    """On the standard listing step at this price (`proxy._strike_step`)."""
    step = _strike_step(spot)
    return abs(k / step - round(k / step)) < 1e-6


def wing_target(short: float, spot: float, typ: str) -> float:
    return short + WING_FRAC * spot if typ == "Call" else short - WING_FRAC * spot


# =============================================================================
# Walks
# =============================================================================

@dataclass
class Walk:
    """One strike choice. status: built | await | drop. `fetch` are the OPEN
    contracts this round names; `seen` is every contract the walk judged."""
    status: str
    strike: float | None = None
    reason: str = ""
    fetch: tuple = ()
    seen: dict = field(default_factory=dict)       # contract -> state
    est: float | None = None                       # likely parent strike if awaiting
    provisional: bool = False                      # planned against an assumed parent


def _first_listed(c: Cache, cands: list, contracts_for, day: date, spot: float,
                  batch: int, std_stop: bool) -> Walk:
    """The first candidate whose contracts are ALL quoted on `day`, walking
    nearest-first. Dead candidates are passed over. Open contracts are named up
    to `batch` unresolved candidates, ending at the first on the standard grid
    when `std_stop` (off-grid probes are mostly unlisted: batching them saves
    rounds)."""
    seen, fetch, n_unres, last = {}, [], 0, None
    for k in cands:
        cons = contracts_for(k)
        sts = [(con, c.state(con, day)) for con in cons]
        for con, s in sts:
            seen[con] = s
        if all(s == OK for _c, s in sts):
            if fetch:
                return Walk("await", None, "nearer_candidates_open", tuple(fetch), seen, est=last)
            return Walk("built", k, "", (), seen)
        if any(s in DEAD for _c, s in sts):
            continue
        fetch += [con for con, s in sts if s == OPEN]
        n_unres += 1
        last = k
        if (std_stop and on_std_grid(k, spot)) or n_unres >= batch:
            return Walk("await", None, "candidates_open", tuple(fetch), seen, est=last)
    if fetch:
        return Walk("await", None, "ladder_ended_open", tuple(fetch), seen, est=last)
    return Walk("drop", None, "no_listed_candidate", (), seen)


def atm_walk(c: Cache, t: str, x: date, day: date, spot: float,
             batch: int = ATM_BATCH) -> Walk:
    """ARM B/D: the strike nearest spot with a call AND a put quoted on `day`."""
    both = [k for k in c.strikes(t, x, "Call") if c.has(t, x, k, "Put")]
    cands = ladder(spot, ATM_BAND * spot, spot, extra=both)
    return _first_listed(c, cands, lambda k: [(t, x, k, "Call"), (t, x, k, "Put")],
                         day, spot, batch, std_stop=True)


def wing_walk(c: Cache, t: str, x: date, day: date, spot: float, short: float,
              typ: str, batch: int = WING_BATCH) -> Walk:
    """The listed strike nearest `short +/- 0.03 x spot`, strictly outside the
    short (a wing that lands on its short moves one listed strike out)."""
    target = wing_target(short, spot, typ)
    half = max(WING_HALF * spot, 4 * _strike_step(spot))
    outward = (lambda k: k > short + 1e-9) if typ == "Call" else (lambda k: k < short - 1e-9)
    cands = [k for k in ladder(target, half, spot, extra=c.strikes(t, x, typ)) if outward(k)]
    return _first_listed(c, cands, lambda k: [(t, x, k, typ)], day, spot, batch, std_stop=True)


def delta_walk(c: Cache, t: str, x: date, day: date, spot: float, typ: str, iv: float,
               target: float = SHORT_DELTA) -> Walk:
    """The `typ` strike whose entry-day |Delta| is nearest `target`.

    `mechanical_benchmark.nearest_delta` + `delta_fetch`, for either type.
    |Delta| falls with strike for a call and rises for a put, so the walk from
    the nearest known strike runs UP for a call that is too deep and DOWN for
    a put that is too deep. A strike with a row but no usable Delta is passed."""
    sign = 1 if typ == "Call" else -1
    cached = c.strikes(t, x, typ)
    step = MB.grid_step(spot, cached)
    days = (x - day).days
    known, seen = {}, {}
    for k in cached:
        con = (t, x, k, typ)
        st = c.state(con, day)
        seen[con] = st
        if st != OK:
            continue
        d = c.row(t, x, k, typ, day)["Delta"]
        if d is None or d == 0 or (d > 0) != (sign > 0) or not 0.0 < abs(d) <= 1.0:
            continue
        known[round(k, 4)] = abs(d)

    def open_(k: float) -> bool:
        return c.state((t, x, k, typ), day) == OPEN

    if not known:
        est = bs_target_strike(spot, iv, days, target, typ)
        want = [k for k in MB.grid_around(est, step, cached) if open_(k)]
        pool = [k for k in want if on_std_grid(k, spot)] or want
        fetch = tuple(sorted(pool, key=lambda k: (abs(k - est), k))[:NO_KNOWN_WIDTH])
        if not fetch:
            return Walk("drop", None, "no_open_strike_near_estimate", (), seen)
        return Walk("await", None, "no_delta_known",
                    tuple((t, x, k, typ) for k in fetch), seen, est=fetch[0])

    kstar = min(known, key=lambda k: (abs(known[k] - target), k))
    if abs(known[kstar] - target) < 1e-12:
        return Walk("built", kstar, "", (), seen)
    too_deep = known[kstar] > target
    toward = 1 if too_deep == (typ == "Call") else -1
    walk = sorted({round(kstar + toward * i * step, 4) for i in range(1, 4 * MB.GRID_REACH)}
                  | {k for k in known if (k - kstar) * toward > 0},
                  reverse=toward < 0)
    walk = [k for k in walk if k > 0]
    open_before, k2 = [], None
    for k in walk:
        if k in known:
            k2 = k
            break
        con = (t, x, k, typ)
        st = c.state(con, day)
        seen[con] = st
        if st == OPEN:
            open_before.append(k)
    if not open_before:
        return Walk("built", kstar, "", (), seen)
    d0 = known[kstar]
    straddle = k2 is not None and (d0 - target) * (known[k2] - target) < 0
    if straddle and len(open_before) <= MB.BRACKET_FILL:
        fetch = tuple(open_before)
        est = fetch[0]
    else:
        if straddle:
            est = kstar + (target - d0) / (known[k2] - d0) * (k2 - kstar)
        else:
            row = c.row(t, x, kstar, typ, day)
            kiv = (row or {}).get("IV") or iv
            est = bs_shift_strike(kstar, d0, target, kiv if kiv > 0 else iv, days, typ)
        pool = [k for k in open_before if on_std_grid(k, spot)] or open_before
        fetch = tuple(sorted(pool, key=lambda k: (abs(k - est), k))[:MB.DELTA_FETCH_WIDTH])
    return Walk("await", kstar, "delta_neighbour_not_cached",
                tuple((t, x, k, typ) for k in fetch), seen, est=fetch[0])


def back_expiry_candidates(c: Cache, t: str, front: date) -> list[date]:
    """Expiries at least BACK_GAP_DAYS after the front, nearest first: every
    cached expiry of the ticker, every Friday and every holiday-adjusted monthly
    in the reach window. Which of them are LISTED is what the walk probes."""
    lo = front + timedelta(days=BACK_GAP_DAYS)
    hi = lo + timedelta(days=BACK_REACH_DAYS)
    out = {x for x in c.expiries(t) if lo <= x <= hi}
    d = lo + timedelta(days=(4 - lo.weekday()) % 7)
    while d <= hi:
        out.add(d)
        d += timedelta(days=7)
    out |= set(MB.monthly_expiries(lo, hi))
    return sorted(out)


def back_walk(c: Cache, t: str, front: date, day: date, spot: float, strike: float,
              batch: int = BACK_BATCH) -> Walk:
    """ARM K: the ATM call at the nearest later expiry (>= front + 14) quoted on
    `day`. Expiries are walked nearest first; a weekly not yet listed on the
    entry day (file without an entry-day row) is passed over, as the study does.
    A built Walk's `strike` holds the chosen EXPIRY here."""
    return _first_listed(c, back_expiry_candidates(c, t, front),
                         lambda x: [(t, x, strike, "Call")], day, spot, batch,
                         std_stop=False)


def swap_contracts(legs) -> list[Contract]:
    """ARM T: the other type at each leg's own strike, for a plain vertical."""
    if NTF.vertical_roles(list(legs), False) is None:
        return []
    return [(l.ticker, l.expiration, float(l.strike),
             "Put" if l.opt_type == "Call" else "Call") for l in legs]


# =============================================================================
# Per-row plan
# =============================================================================

@dataclass
class RowCtx:
    label: str
    ticker: str
    front: date
    entry: date
    spot: float
    iv: float
    legs: tuple


@dataclass
class RowPlan:
    ctx: RowCtx
    walks: dict = field(default_factory=dict)       # group -> [Walk]


def _provisional(w: Walk) -> float | None:
    """The strike a dependent stage is planned against while its parent waits."""
    return w.strike if w.status == "built" else w.est


def plan_row(c: Cache, ctx: RowCtx, groups: tuple[str, ...] = GROUPS) -> RowPlan:
    t, x, e, spot = ctx.ticker, ctx.front, ctx.entry, ctx.spot
    plan = RowPlan(ctx)
    want = set(groups)

    def add(g: str, w: Walk, provisional: bool = False) -> Walk:
        w.provisional = provisional
        plan.walks.setdefault(g, []).append(w)
        return w

    if want & {"CGS_delta", "C_wing"}:
        for typ in ("Call", "Put"):
            w = delta_walk(c, t, x, e, spot, typ, ctx.iv)
            if "CGS_delta" in want:
                add("CGS_delta", w)
            if "C_wing" in want:
                k = _provisional(w)
                if k is not None and w.status != "drop":
                    add("C_wing", wing_walk(c, t, x, e, spot, k, typ), w.status != "built")

    if want & {"BD_atm", "B_wing", "K_back"}:
        w = atm_walk(c, t, x, e, spot)
        if "BD_atm" in want:
            add("BD_atm", w)
        k = _provisional(w)
        if k is not None and w.status != "drop":
            prov = w.status != "built"
            if "B_wing" in want:
                for typ in ("Call", "Put"):
                    add("B_wing", wing_walk(c, t, x, e, spot, k, typ), prov)
            if "K_back" in want:
                add("K_back", back_walk(c, t, x, e, spot, k), prov)

    if "T_swap" in want:
        cons = swap_contracts(ctx.legs)
        if cons:
            seen = {con: c.state(con, e) for con in cons}
            fetch = tuple(con for con, s in seen.items() if s == OPEN)
            add("T_swap", Walk("await" if fetch else "built", None, "", fetch, seen))
    return plan


# =============================================================================
# The rows
# =============================================================================

def row_ctx(c: Cache, rec: dict) -> tuple[RowCtx | None, str]:
    """`(ctx, "")` or `(None, drop_reason)`."""
    t = rec["t"]
    legs = tuple(t.legs)
    if not legs:
        return None, "no_legs"
    entry = recorded_entry_date(t)
    if entry is None:
        return None, "no_recorded_entry_day"
    front = min(l.expiration for l in legs)
    if (front - entry).days <= 0:
        return None, "entry_not_before_expiry"
    spot = c.spot(t.ticker, front, entry)
    if spot is None:
        return None, "no_spot_on_entry_day"
    ivs = []
    for l in legs:
        r = c.row(l.ticker, l.expiration, l.strike, l.opt_type, entry)
        if r and r["IV"] and r["IV"] > 0:
            ivs.append(r["IV"])
    iv = statistics.fmean(ivs) if ivs else None
    if iv is None:
        near = [r["IV"] for k in c.strikes(t.ticker, front)
                for typ in ("Call", "Put")
                if abs(k - spot) <= 0.05 * spot
                and (r := c.row(t.ticker, front, k, typ, entry)) and r["IV"] and r["IV"] > 0]
        iv = statistics.median(near) if near else (rec.get("iv_entry") or DEFAULT_IV)
    label = f"{rec['date']} {t.ticker} {t.structure}"
    return RowCtx(label, t.ticker, front, entry, spot, float(iv), legs), ""


def book_rows(c: Cache, records: list[dict]) -> tuple[list[RowCtx], Counter]:
    rows, drops = [], Counter()
    for rec in records:
        if rec.get("source") != "real" or not str(rec["date"]).startswith("2026"):
            continue
        ctx, why = row_ctx(c, rec)
        if ctx is None:
            drops[why] += 1
        else:
            rows.append(ctx)
    return rows, drops


# =============================================================================
# Census, dry-run report
# =============================================================================

@dataclass
class GroupStats:
    rows: int = 0
    rows_need: int = 0
    rows_need_prov: int = 0
    now: set = field(default_factory=set)           # open contracts to fetch this round
    dependent: set = field(default_factory=set)     # open contracts of provisional stages
    ok: set = field(default_factory=set)
    unlisted: set = field(default_factory=set)
    drops: Counter = field(default_factory=Counter)


def census(plans: list[RowPlan]) -> dict[str, GroupStats]:
    out = {g: GroupStats() for g in GROUPS}
    for p in plans:
        for g, walks in p.walks.items():
            s = out[g]
            s.rows += 1
            need = need_prov = False
            for w in walks:
                for con, st in w.seen.items():
                    if st == OK:
                        s.ok.add(con)
                    elif st == UNLISTED:
                        s.unlisted.add(con)
                if w.status == "drop":
                    s.drops[w.reason] += 1
                if w.fetch:
                    if w.provisional:
                        s.dependent.update(w.fetch)
                        need_prov = True
                    else:
                        s.now.update(w.fetch)
                        need = True
            s.rows_need += need
            s.rows_need_prov += need_prov and not need
    return out


def round_targets(plans: list[RowPlan]) -> list[Contract]:
    """Unique contracts to request this round (never a provisional stage's),
    in plan order."""
    seen, out = set(), []
    for p in plans:
        for g in GROUPS:
            for w in p.walks.get(g, ()):
                if w.provisional:
                    continue
                for con in w.fetch:
                    if con not in seen:
                        seen.add(con)
                        out.append(con)
    return out


def print_report(plans: list[RowPlan], n_rows: int, drops: Counter, listing: bool,
                 limit: int | None) -> dict:
    cs = census(plans)
    print(f"rows: {n_rows} planned" + "".join(f", {v} dropped ({k})" for k, v in drops.items()))
    head = (f"{'group':<10} {'arms':<6} {'rows':>5} {'need':>5} {'+dep':>5} "
            f"{'fetch r1':>9} {'est.dep':>8} {'cached':>7} {'skiplist':>8}")
    print(head)
    print("-" * len(head))
    now_all, dep_all = set(), set()
    for g in GROUPS:
        s = cs[g]
        now_all |= s.now
        dep_all |= s.dependent
        print(f"{g:<10} {SERVES[g]:<6} {s.rows:>5} {s.rows_need:>5} {s.rows_need_prov:>5} "
              f"{len(s.now):>9} {len(s.dependent - s.now):>8} {len(s.ok):>7} {len(s.unlisted):>8}")
        if s.drops:
            print(f"{'':<17}walk drops: " + ", ".join(f"{k}={v}" for k, v in s.drops.items()))
    dep_only = dep_all - now_all
    est_total = len(now_all) + len(dep_only)
    print("-" * len(head))
    print(f"unique contracts, round 1:           {len(now_all)}")
    print(f"unique contracts, est. dependent:    {len(dep_only)}  (wings / back legs planned "
          f"against the likely parent strike)")
    print(f"estimated probes (round 1 + dependent): {est_total}  "
          f"~{est_total * SECONDS_PER_CONTRACT / 60:.0f} min at "
          f"{SECONDS_PER_CONTRACT}s/contract, before any re-probe of a first `no_rows`")
    if limit is not None:
        print(f"this run would request at most {limit}")
    if listing:
        for con in sorted(now_all, key=lambda c_: (c_[0], c_[1], c_[2], c_[3])):
            print(f"  {con[0]:<6} {con[1].isoformat()} {con[2]:>9.2f}{con[3][0]}")
    return dict(round1=len(now_all), dependent=len(dep_only), total=est_total)


# =============================================================================
# Fetch
# =============================================================================

def to_contracts(targets: list[Contract]) -> list[dict]:
    """`fetch_option_histories`'s contract dicts."""
    return [dict(key=_contract_key(t, typ, k, x.isoformat()),
                 symbol=t, opt_type=typ, strike=k, expiration=x)
            for t, x, k, typ in targets]


async def fetch(targets: list[Contract], headless: bool, timeout_ms: int) -> None:
    await fetch_option_histories(to_contracts(targets), headless, timeout_ms,
                                 retry_unlisted=True)


def classify_outcomes(c: Cache, targets: list[Contract]) -> Counter:
    """After a fetch: a file is fetched; an entry on the skip-list (any reason)
    is unlisted; the rest failed."""
    listed = set(UL.load(NTF.UNLISTED_PATH))
    tally = Counter()
    for con in targets:
        if c.has(*con):
            tally["fetched"] += 1
        elif stem_of(con) in listed:
            tally["unlisted"] += 1
        else:
            tally["failed"] += 1
    return tally


def run_live(rows: list[RowCtx], c: Cache, groups,
             limit: int | None, headless: bool, timeout_ms: int) -> int:
    tally, net_errors, remaining = Counter(), 0, limit
    for rnd in range(1, MAX_ROUNDS + 1):
        plans = [plan_row(c, r, groups) for r in rows]
        targets = round_targets(plans)
        if remaining is not None:
            targets = targets[:max(remaining, 0)]
        if not targets:
            print(f"round {rnd}: nothing open" + (" within --limit" if remaining == 0 else ""))
            break
        print(f"round {rnd}: requesting {len(targets)} contracts")
        try:
            asyncio.run(fetch(targets, headless, timeout_ms))
        except NetworkOutage as e:
            net_errors += e.n_failed
            log.error("network outage: %d of %d fetches failed — stopped; what was "
                      "written is kept, re-run when online", e.n_failed, e.n_total)
            c.attempted.update(stem_of(t_) for t_ in targets)
            c.refresh()
            c.reload_evidence()
            tally += classify_outcomes(c, targets)
            print_tally(tally, net_errors)
            return EXIT_NETWORK_OUTAGE
        UL.flush_at_exit()      # pending clean 404s -> the skip-list now, not at exit
        c.attempted.update(stem_of(t_) for t_ in targets)
        c.refresh()
        c.reload_evidence()
        tally += classify_outcomes(c, targets)
        if remaining is not None:
            remaining -= len(targets)
    else:
        print(f"stopped at MAX_ROUNDS={MAX_ROUNDS}; re-run to continue")
    print_tally(tally, net_errors)
    return 0


def print_tally(tally: Counter, net_errors: int) -> None:
    print(f"tally: fetched {tally['fetched']}  unlisted {tally['unlisted']}  "
          f"failed {tally['failed']}  network errors {net_errors}")
    print(BACKUP_REMINDER)


def main(argv=None) -> int:
    setup_logging()
    log.setLevel(logging.INFO)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true",
                    help="Fetch from Barchart. Without it the run is a dry-run: "
                         "the plan and its counts are printed and nothing is fetched.")
    ap.add_argument("--list", action="store_true",
                    help="In a dry-run, also print every round-1 contract.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Request at most N contracts this run (resumable).")
    ap.add_argument("--groups", default=",".join(GROUPS),
                    help=f"Comma list of {','.join(GROUPS)} (default all).")
    ap.add_argument("--no-headless", action="store_true", help="Visible browser.")
    ap.add_argument("--timeout-ms", type=int, default=15000)
    args = ap.parse_args(argv)

    groups = tuple(g.strip() for g in args.groups.split(",") if g.strip())
    bad = [g for g in groups if g not in GROUPS]
    if bad:
        ap.error(f"unknown group(s) {bad}; choose from {GROUPS}")

    records, _diag = load_book()
    c = Cache()
    rows, drops = book_rows(c, records)
    if not args.live:
        plans = [plan_row(c, r, groups) for r in rows]
        print_report(plans, len(rows), drops, args.list, args.limit)
        print("[dry-run] nothing fetched; --live fetches")
        print(BACKUP_REMINDER)
        return 0
    headless = not args.no_headless and os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
    return run_live(rows, c, groups, args.limit, headless, args.timeout_ms)


if __name__ == "__main__":
    raise SystemExit(main())
