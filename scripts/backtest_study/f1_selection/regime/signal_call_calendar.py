"""signal_call_calendar — after a mech BEAR or E-VOL signal, does a SPY call calendar pay?

REGISTRATION: research/pre-registrations/f1_selection/regime/signal_call_calendar.md
(accepted by default 2026-11-21, commit e534857). Every constant, floor, seed, window and
verdict word below is that file's. Read it before changing anything here.

WHAT IT ASKS
------------
K-BEAR, K-EVOL  One SPY call calendar on each `state_map` Q3 onset (S-BEAR, S-EVOL):
                short the standard monthly nearest 30 DTE (at least 21), long the same
                strike on the monthly after it nearest 60 DTE, strike nearest spot x 1.03,
                both legs at the D + 1 closing mid, out after 21 sessions or at the
                short's expiry. Graded on mean R, Holm m = 2.
CALM            The same calendar on `selloff_put_diagonal.calm_days`; the reference
                for every gain.
Parameter cells Strike x1.00 / x1.05, long 90 DTE, exit 5 / 10 sessions. Printed only,
                and the PBO grid.
FORWARD         The two arms on onsets from 2026-11-21, the current sell-off out.

REUSED, NEVER RE-DERIVED
------------------------
Signals: `state_map` (`build_cal`, `cut_cal`, `mech_labels`, `state_flags`, `onsets`,
`q4_trades` for gate GS, `build_episodes` / `zone_bounds` for the forward zone). Calm days
and the strike walk: `selloff_put_diagonal` (`rule_state`, `calm_days`, `gate_hash`,
`nearest_listed`, `leg_fill`, `leg_mark`). Expiries: `mechanical_benchmark.monthly_for` /
`monthly_expiries` / `listed_by`. Pricing: `simulate.entry_day_fill` (through `leg_fill`),
`junk_day_mark` (through `leg_mark`), `_monotonicity_violation`, and
`helpers._defined_risk_bounds`. Judging: `ticker_class.holm`, `lib/pbo.py`.

THE CUT. The in-sample run reads the SPY / VIX / VIX3M series cut at 2026-09-22 and the
option cache through `CutChain`, which drops every quote after 2026-09-22. Only the
forward section reads later closes and quotes.

EXIT CODES. 3 (GE input missing, wrong era) is a designed refusal. 4 (GS) and 5 (GH) are
real failures and read as FAILED in the runner by design.

THE AWAIT GATE. While any headline entry (K-BEAR, K-EVOL or CALM) awaits a fetch, the run
prints its census and `NOT BUILT — AWAITING SCRAPE` and stops. `Book.price` refuses until
`Book.open_outcomes` has seen no headline entry await. No code here fetches; the fetch
list is `fetch_list()`, imported by
`scripts/collector/study_legs/f1_selection/fetch_signal_call_calendar_legs.py`.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run signal_call_calendar
    python -m scripts.backtest_study.f1_selection.regime.signal_call_calendar --fetch-list
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest import simulate as SIM  # noqa: E402
from scripts.backtest.helpers import _defined_risk_bounds  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark.ticker_class import holm  # noqa: E402
from scripts.backtest_study.f1_selection.regime import selloff_put_diagonal as SPD  # noqa: E402
from scripts.backtest_study.f1_selection.regime import state_map as SM  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/signal_call_calendar.md"
REGISTERED = "2026-11-21"

# ── registered constants (the registration's numbers; never re-chosen) ──────
TICKER = "SPY"
IN_SAMPLE_START = "2022-02-01"
IN_SAMPLE_END = "2026-09-22"
GAP_START, GAP_END = "2026-09-23", "2026-11-20"
FORWARD_START = "2026-11-21"
FORWARD_ANCHOR = "2026-11-20"        # the last session before the forward window
SUNSET = "2028-11-21"
SIGNALS = ("S-BEAR", "S-EVOL")
ARM_OF = {"S-BEAR": "K-BEAR", "S-EVOL": "K-EVOL"}
ARMS = ("K-BEAR", "K-EVOL")
CALM = "CALM"
CALM_RULE = "E-DD5"
SHORT_DTE, SHORT_BAND = 30, (21, 122)
LONG_DTE, LONG_DTE_ALT = 60, 90
STRIKE_MULT = 1.03
HOLD = 21
COMMISSION = 0.65                    # per contract per leg-side, slippage 0
SIDES = 4
COST = SIDES * COMMISSION            # $2.60, entry and exit together
BOOT_N = 10_000
SEED = 20261121
ALPHA = 0.05
FLOOR = 10                           # month clusters, every population
PBO_S = 20
PBO_VETO, PBO_FRAGILE = 0.50, 0.25
LONG_WALK_DAYS = 400                 # bounds the long-expiry candidate list only

CP, PNS, CONTRARY, NULL = "CALENDAR-PAYS", "PAYS-NOT-SIGNAL", "CONTRARY", "NULL"
UNDERPOWERED, STILL_OPEN, THIN = "UNDERPOWERED", "STILL-OPEN", "THIN"
NOT_BUILT = "NOT BUILT — AWAITING SCRAPE"
NOTES = "second structure on one signal set; geometry set after Q4"
BANNER_ARM = ("call calendar after {sig}, 1.03 strike, 30/60 DTE, 21 sessions or short expiry, "
              f"{IN_SAMPLE_START} to {IN_SAMPLE_END}")
RULE = "=" * 78
FETCH_CMD = "python3 scripts/collector/study_legs/f1_selection/fetch_signal_call_calendar_legs.py"
CACHE_DIR = ROOT / "backtests" / "option_history_cache"
SERIES = ("SPY", "VIX", "VIX3M")

# Exit 3: an input is missing (GE) or the era is wrong, a designed refusal. Exits 4 (GS) and
# 5 (GH) are deliberately NOT declared: a code or definitions mismatch must read as FAILED.
EXIT_INPUT, EXIT_GS, EXIT_GH = 3, 4, 5
DESIGNED_REFUSAL_EXIT_CODES = {3}


class Refused(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class AwaitingScrape(RuntimeError):
    """An outcome was asked for while a headline entry awaits a fetch."""


# ════════════════════════════════════════════════════════════════════════════
# Cells
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Geom:
    mult: float = STRIKE_MULT
    long_dte: int = LONG_DTE
    h: int = HOLD


HEAD = Geom()
#: One choice moved from the headline per row, the rest held.
CELLS = (("headline", HEAD), ("strike x1.00", Geom(mult=1.00)), ("strike x1.05", Geom(mult=1.05)),
         ("long 90 DTE", Geom(long_dte=LONG_DTE_ALT)), ("exit 5", Geom(h=5)), ("exit 10", Geom(h=10)))
#: Calm days price at the headline strike only, with each long expiry and each exit.
CALM_CELLS = tuple(c for c in CELLS if c[1].mult == STRIKE_MULT)


# ════════════════════════════════════════════════════════════════════════════
# The cache, cut at a date
# ════════════════════════════════════════════════════════════════════════════

class CutChain:
    """A chain whose every contract history stops at `cut` (gate GC). Listing, cache
    membership and the strike index pass through unchanged."""

    def __init__(self, parent, cut: date):
        self.parent, self.cut = parent, cut

    @property
    def idx(self):
        return self.parent.idx

    def cached(self, ticker, expiry, strike, opt_type) -> bool:
        return self.parent.cached(ticker, expiry, strike, opt_type)

    def strikes(self, ticker, expiry) -> list:
        return self.parent.strikes(ticker, expiry)

    def history(self, leg):
        series, details = self.parent.history(leg)
        return ([(d, m) for d, m in series if d <= self.cut],
                {d: r for d, r in details.items() if d <= self.cut})


# ════════════════════════════════════════════════════════════════════════════
# Populations — closes only, no option price
# ════════════════════════════════════════════════════════════════════════════

def flags_of(cal: SM.Cal) -> dict:
    return SM.state_flags(SM.mech_labels(cal, SM.SMA_HEADLINE), SM.mech_labels(cal, SM.SMA_LONG))


def closes_of(cal: SM.Cal) -> dict:
    return {date.fromisoformat(d): float(c) for d, c in zip(cal.dates, cal.close)}


def truncate(ds: list[int], n: int, h: int = HOLD) -> tuple[list[int], int]:
    """`(kept, n_truncated)`: keep D when the D + 1 + h close is inside the calendar."""
    kept = [d for d in ds if d + 1 + h < n]
    return kept, len(ds) - len(kept)


def split_calm(calm: list[date], cal: SM.Cal, flags: dict) -> tuple[list[int], int]:
    """`(D indices, n_overlap)`: a calm day on which mech BEAR or E-VOL holds is dropped."""
    out, overlap = [], 0
    for d in calm:
        D = cal.pos.get(d.isoformat())
        if D is None:
            continue
        if any(bool(flags[s][0][D]) for s in SIGNALS):
            overlap += 1
            continue
        out.append(D)
    return out, overlap


@dataclass
class Pop:
    onsets: dict                 # signal -> every onset D in the window, before any drop (GS)
    signals: dict                # signal -> candidate D after truncation
    trunc: dict                  # signal -> n_truncated
    calm: list                   # candidate calm D after overlap and truncation
    calm_n: int = 0
    calm_overlap: int = 0
    calm_trunc: int = 0
    in_zone: dict = field(default_factory=dict)       # forward only: signal -> D in the zone
    excluded_runs: dict = field(default_factory=dict)  # forward only: onsets inside the re-arm


def in_sample_pop(cal: SM.Cal) -> Pop:
    """`cal` must already be cut at the in-sample end."""
    flags = flags_of(cal)
    ons, sig, tr = {}, {}, {}
    for s in SIGNALS:
        ons[s] = [d for d in SM.onsets(*flags[s]) if cal.dates[d] >= IN_SAMPLE_START]
        sig[s], tr[s] = truncate(ons[s], cal.n)
    rs = SPD.rule_state(closes_of(cal), CALM_RULE)
    cds = SPD.calm_days(rs, date.fromisoformat(IN_SAMPLE_START), date.fromisoformat(IN_SAMPLE_END))
    calm, overlap = split_calm(cds, cal, flags)
    calm_kept, calm_tr = truncate(calm, cal.n)
    return Pop(ons, sig, tr, calm_kept, len(cds), overlap, calm_tr)


def forward_split(ons: list[int], anchor: int, zone) -> tuple[list[int], list[int], int]:
    """`(graded, in_zone, excluded)`: an onset counts forward when it and its 10 re-arm
    sessions all fall after the anchor; one inside the current episode's zone is split out."""
    graded, inz, excluded = [], [], 0
    for d in ons:
        if d <= anchor:
            continue
        if d < anchor + SM.REARM + 1:
            excluded += 1
            continue
        (inz if zone is not None and zone[0] <= d <= zone[1] else graded).append(d)
    return graded, inz, excluded


def current_zone(full: SM.Cal, anchor: int):
    """`state_map.run_forward`'s zone: `zone_bounds` of the last headline E-DD8 episode
    whose peak is on or before the anchor."""
    eps = SM.build_episodes(full, SM.HEADLINE_DEF)
    cur = [e for e in eps if e.p <= anchor]
    return SM.zone_bounds(cur[-1], full.n) if cur else None


def forward_pop(full: SM.Cal) -> Pop:
    flags = flags_of(full)
    anchor = SM.idx_on_or_before(full, FORWARD_ANCHOR)
    zone = current_zone(full, anchor)
    ons, sig, tr, inz, exc = {}, {}, {}, {}, {}
    for s in SIGNALS:
        every = SM.onsets(*flags[s])
        g, z, x = forward_split(every, anchor, zone)
        ons[s] = g
        sig[s], tr[s] = truncate(g, full.n)
        inz[s], exc[s] = truncate(z, full.n)[0], x
    rs = SPD.rule_state(closes_of(full), CALM_RULE)
    cds = SPD.calm_days(rs, date.fromisoformat(FORWARD_START))
    calm, overlap = split_calm(cds, full, flags)
    calm_kept, calm_tr = truncate(calm, full.n)
    return Pop(ons, sig, tr, calm_kept, len(cds), overlap, calm_tr, inz, exc)


# ════════════════════════════════════════════════════════════════════════════
# Selection — reads the entry session and nothing later (GX)
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Sel:
    status: str                  # built | await | drop
    reason: str = ""
    strike: float | None = None
    short_exp: date | None = None
    long_exp: date | None = None
    fetch: tuple = ()            # ((opt, expiry, strike), ...)


def short_expiry(entry: date) -> date | None:
    return MB.monthly_for(entry, SHORT_DTE, SHORT_BAND)


def long_expiry(entry: date, short_exp: date, long_dte: int) -> date | None:
    """Among standard monthlies strictly after the short's expiry, the one nearest
    `long_dte` DTE from the entry; ties go to the earlier."""
    cands = MB.monthly_expiries(short_exp + timedelta(days=1), short_exp + timedelta(days=LONG_WALK_DAYS))
    if not cands:
        return None
    return min(cands, key=lambda e: (abs((e - entry).days - long_dte), e))


def _call(expiry: date, strike: float, qty: int) -> Leg:
    return Leg(qty, TICKER, expiry, float(strike), "Call")


def _stem(expiry: date, strike: float) -> str:
    return SPD.NTF.contract_stem(TICKER, expiry, strike, "Call")


def select(chain, evidence: set, entry: date, spot: float, mult: float, long_dte: int) -> Sel:
    """The calendar's strike and expiries on the entry session's close. No pricing.

    When the short strike awaits a fetch, the long contract at that same strike is listed
    with it, so one fetch round covers the pair the entry will most likely need."""
    se = short_expiry(entry)
    if se is None:
        return Sel("drop", "no_monthly")
    le = long_expiry(entry, se, long_dte)
    if le is None:
        return Sel("drop", "no_monthly", short_exp=se)
    s = SPD.nearest_listed(chain, evidence, se, spot * mult, spot, entry, "Call")
    if s.status == "drop":
        return Sel("drop", s.reason, short_exp=se, long_exp=le)
    k = float(s.strike)
    long_open = _stem(le, k) not in evidence and not chain.cached(TICKER, le, k, "Call")
    if s.status == "await":
        fetch = tuple(s.fetch) + ((("Call", le, k),) if long_open else ())
        return Sel("await", "strike_not_cached", k, se, le, fetch)
    if _stem(le, k) in evidence:
        return Sel("drop", "long_strike_unlisted", k, se, le)
    if chain.cached(TICKER, le, k, "Call"):
        if MB.listed_by(chain, _call(le, k, 1), entry):
            return Sel("built", "", k, se, le)
        return Sel("drop", "long_strike_unlisted", k, se, le)
    return Sel("await", "long_strike_not_cached", k, se, le, (("Call", le, k),))


@dataclass
class Entry:
    arm: str
    D: int
    d: str                       # the signal (or calm) date D
    entry: date                  # D + 1
    spot: float
    geom: Geom
    sel: Sel

    @property
    def status(self) -> str:
        return self.sel.status


@dataclass
class Priced:
    e: Entry
    h: int
    debit: float
    value: float                 # exit value, floored at 0
    R: float
    gross: float
    exit_day: date
    exit_reason: str             # h<N> | short_expiry
    floored: bool
    stale: int
    clamp: int
    mono: int
    mfe: float
    mae: float
    hold: float                  # ln(A[exit] / A[entry]); NaN when the exit is not a session
    vix_state: str               # above | below | missing


def r_of(value: float, debit: float) -> float:
    """R: P&L over the cash at risk, both with every commission. `value` is floored first."""
    v = max(0.0, value)
    return ((v - debit) * 100.0 - COST) / (debit * 100.0 + COST)


class Book:
    """Selections memoised by (D, strike multiple, long DTE); prices by (that, h).

    `price()` refuses until `open_outcomes()` has seen no headline entry await. That is
    the await gate, by construction."""

    def __init__(self, cal: SM.Cal, chain, evidence: set):
        self.cal, self.chain, self.evidence = cal, chain, evidence
        self.close_of = closes_of(cal)
        self._sel: dict = {}
        self._px: dict = {}
        self._open = False
        self.mono_checked = 0
        self.clamp_checked = 0

    def sel(self, D: int, geom: Geom) -> Sel:
        key = (D, geom.mult, geom.long_dte)
        if key not in self._sel:
            entry = date.fromisoformat(self.cal.dates[D + 1])
            self._sel[key] = select(self.chain, self.evidence, entry, float(self.cal.close[D + 1]),
                                    geom.mult, geom.long_dte)
        return self._sel[key]

    def entries(self, arm: str, Ds: list[int], geom: Geom) -> list[Entry]:
        return [Entry(arm, D, self.cal.dates[D], date.fromisoformat(self.cal.dates[D + 1]),
                      float(self.cal.close[D + 1]), geom, self.sel(D, geom)) for D in Ds]

    def open_outcomes(self, headline: list[Entry]) -> None:
        aw = [e for e in headline if e.status == "await"]
        if aw:
            raise AwaitingScrape(f"{len(aw)} headline entries await a fetch")
        self._open = True

    def price(self, e: Entry) -> Priced | str:
        """`Priced` or a refusal / drop reason. Raises while the await gate is shut."""
        if not self._open:
            raise AwaitingScrape("outcomes are closed until no headline entry awaits")
        key = (e.D, e.geom)
        if key not in self._px:
            self._px[key] = self._price(e)
        return self._px[key]

    def _mark(self, legs: list[Leg], day: date):
        marks = [SPD.leg_mark(self.chain, lg, day, self.close_of.get(day)) for lg in legs]
        return None if any(m is None for m in marks) else marks

    def _price(self, e: Entry) -> Priced | str:
        s, cal = e.sel, self.cal
        lng, sht = _call(s.long_exp, s.strike, 1), _call(s.short_exp, s.strike, -1)
        legs = [lng, sht]
        fills = [SPD.leg_fill(self.chain, lg, e.entry) for lg in legs]
        if any(f is None for f in fills):
            return "no_entry_quote"
        if any(f[0] is None for f in fills):
            return SIM.JUNK_ENTRY_REFUSAL
        prices, tags = [f[0] for f in fills], [f[1] for f in fills]
        self.mono_checked += 1
        mono = SIM._monotonicity_violation(legs, prices, tags)
        if mono:
            return SIM.NON_MONOTONIC_REFUSAL
        debit = prices[0] - prices[1]
        if debit <= 0:
            return "debit_priced_to_credit"
        self.clamp_checked += 1
        clamp = int(_defined_risk_bounds(legs) is not None)
        i_in = e.D + 1
        i_out = i_in + e.geom.h
        if i_out >= cal.n:
            return "exit_after_data_end"
        exit_day, reason = date.fromisoformat(cal.dates[i_out]), f"h{e.geom.h}"
        if s.short_exp <= exit_day:
            exit_day, reason = s.short_exp, "short_expiry"
        out = self._mark(legs, exit_day)
        if out is None:
            return "exit_unmarked"
        raw = out[0][0] - out[1][0]
        value = max(0.0, raw)
        R = r_of(value, debit)
        path = []
        for i in range(i_in + 1, cal.n):
            day = date.fromisoformat(cal.dates[i])
            if day >= exit_day:
                break
            m = self._mark(legs, day)
            if m is not None:
                path.append(r_of(m[0][0] - m[1][0], debit))
        path.append(R)
        j = cal.pos.get(exit_day.isoformat())
        hold = math.log(cal.adj[j] / cal.adj[i_in]) if j is not None else float("nan")
        v, v3 = cal.vix[i_in], cal.vix3m[i_in]
        vs = "missing" if not (np.isfinite(v) and np.isfinite(v3)) else "above" if v > v3 else "below"
        return Priced(e, e.geom.h, debit, value, R, (value - debit) / debit, exit_day, reason,
                      raw < 0, sum(1 for m in out if m[1] == "barchart_stale"), clamp, 0,
                      max(path), min(path), hold, vs)


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def load_inputs() -> tuple[SM.Cal, dict]:
    """GE: the cached SPY, ^VIX and ^VIX3M series (no fetch) and the option cache."""
    rows = {}
    for name in SERIES:
        p = SM._cache_path(name)
        if not p.exists():
            raise Refused(EXIT_INPUT, f"GE: {p.relative_to(ROOT)} is missing. Exit 3.")
        rows[name] = SM.read_series(p)
        if not rows[name] or rows[name][-1][0] < IN_SAMPLE_END:
            raise Refused(EXIT_INPUT, f"GE: {name} does not reach {IN_SAMPLE_END}. Exit 3.")
    if not CACHE_DIR.is_dir():
        raise Refused(EXIT_INPUT, f"GE: the option cache {CACHE_DIR.relative_to(ROOT)} is missing. Exit 3.")
    vix = {d: c for d, c, _ in rows["VIX"]}
    vix3m = {d: c for d, c, _ in rows["VIX3M"]}
    full = SM.build_cal(rows["SPY"], vix, vix3m, {}, {})
    try:
        SM.check_cuts(full)
    except SM.Refused as exc:
        raise Refused(EXIT_INPUT, exc.message)
    return full, rows


def gate_gs(chain, evidence, cal: SM.Cal, pop: Pop) -> dict:
    """GS: `{signal: (study set, q4 set)}` of onset dates D >= the window start. The study
    side takes the filter `q4_trades` applies (D + 1 inside the calendar), so an onset on
    the last session cannot raise a false GS failure; truncation drops it anyway."""
    flags = flags_of(cal)
    q4 = SM.q4_trades(chain, evidence, cal, flags, start=IN_SAMPLE_START)
    return {s: ({cal.dates[d] for d in pop.onsets[s] if d + 1 < cal.n}, {cal.dates[t.D] for t in q4 if t.signal == s})
            for s in SIGNALS}


def env():
    """`(chain, evidence)`: the option-history cache and the skip-list evidence."""
    return SPD.NTF.Chain(), SPD.NTF.unlisted_evidence()


# ════════════════════════════════════════════════════════════════════════════
# Fetch list — selection only
# ════════════════════════════════════════════════════════════════════════════

def all_entries(book: Book, pop: Pop) -> dict:
    """`{(cell name, arm): [Entry]}` for every signal cell and every calm cell."""
    out = {}
    for name, g in CELLS:
        for s in SIGNALS:
            out[(name, ARM_OF[s])] = book.entries(ARM_OF[s], pop.signals[s], g)
    for name, g in CALM_CELLS:
        out[(name, CALM)] = book.entries(CALM, pop.calm, g)
    return out


def contract_census(chain, entries: dict, label: str = "") -> tuple[set, list[dict]]:
    """`(named, fetch rows)`: every contract the entries name (built legs and await
    targets) and the unique uncached ones, deduplicated, first naming cell wins."""
    named, seen = set(), {}
    for (cell, arm), es in entries.items():
        for e in es:
            s = e.sel
            keys = list(s.fetch)
            if s.status == "built":
                keys += [("Call", s.short_exp, s.strike), ("Call", s.long_exp, s.strike)]
            for o, x, k in keys:
                key = (o, x, round(float(k), 4))
                named.add(key)
                if s.status == "await" and (o, x, k) in s.fetch:
                    seen.setdefault(key, f"signal_call_calendar:{label}{arm}:{cell.replace(' ', '_')}")
    rows = [dict(ticker=TICKER, expiration=x, strike=k, opt_type=o, category=c)
            for (o, x, k), c in sorted(seen.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2]))]
    return named, rows


def fetch_plan(full: SM.Cal, chain, evidence) -> dict:
    """In-sample (on the cut series and cut chain) and forward fetch rows, merged."""
    cal = SM.cut_cal(full, IN_SAMPLE_END)
    cut = CutChain(chain, date.fromisoformat(IN_SAMPLE_END))
    ins = all_entries(Book(cal, cut, evidence), in_sample_pop(cal))
    fwd = forward_entries(Book(full, chain, evidence), forward_pop(full))
    n_in, rows_in = contract_census(chain, ins)
    n_fw, rows_fw = contract_census(chain, fwd, "forward:")
    merged = {(r["opt_type"], r["expiration"], r["strike"]): r for r in rows_fw}
    merged.update({(r["opt_type"], r["expiration"], r["strike"]): r for r in rows_in})
    rows = sorted(merged.values(), key=lambda r: (r["expiration"], r["opt_type"], r["strike"]))
    named = n_in | n_fw
    return dict(rows=rows, named=named, n_in=n_in, n_fw=n_fw, rows_in=rows_in, rows_fw=rows_fw,
                cached=sum(1 for o, x, k in named if chain.cached(TICKER, x, k, o)))


def fetch_list() -> list[dict]:
    """The collector's entry point: the unique uncached contracts, on the cache as it
    stands. Selection only: nothing is priced and no network is touched."""
    full, _ = load_inputs()
    chain, evidence = env()
    return fetch_plan(full, chain, evidence)["rows"]


# ════════════════════════════════════════════════════════════════════════════
# Grading — pure functions
# ════════════════════════════════════════════════════════════════════════════

def month(d: str) -> str:
    return d[:7]


def quarter(d: str) -> tuple[int, int]:
    return int(d[:4]), (int(d[5:7]) - 1) // 3 + 1


def n_clusters(rows: list[tuple[str, float]]) -> int:
    return len({month(d) for d, _ in rows})


def _cluster_arrays(rows):
    by = defaultdict(lambda: [0.0, 0])
    for d, r in rows:
        by[month(d)][0] += r
        by[month(d)][1] += 1
    keys = sorted(by)
    return np.array([by[k][0] for k in keys]), np.array([by[k][1] for k in keys], dtype=float)


def boot_p(draws: np.ndarray) -> float:
    """Two-sided: twice the smaller share at or below 0 and at or above 0, capped at 1."""
    return float(min(1.0, 2 * min(np.mean(draws <= 0), np.mean(draws >= 0))))


@dataclass
class Stat:
    n: int
    k: int
    mean: float
    lo: float = float("nan")
    hi: float = float("nan")
    p: float = float("nan")
    gain: float = float("nan")
    glo: float = float("nan")
    ghi: float = float("nan")
    gp: float = float("nan")

    @property
    def half(self) -> float:
        return (self.hi - self.lo) / 2

    @property
    def ghalf(self) -> float:
        return (self.ghi - self.glo) / 2


def boot(arm: list[tuple[str, float]], calm: list[tuple[str, float]] | None,
         n: int = BOOT_N, seed: int = SEED) -> Stat:
    """Calendar-month cluster bootstrap. Each draw resamples the arm's clusters with
    replacement; the draw statistic is the entry-weighted mean R. In the same draw CALM's
    clusters are resampled on their own, and the gain is the difference of the means."""
    nan = float("nan")
    if not arm:
        return Stat(0, 0, nan)
    s, c = _cluster_arrays(arm)
    st = Stat(len(arm), len(s), float(s.sum() / c.sum()))
    rng = np.random.default_rng(seed)
    ix = rng.integers(0, len(s), (n, len(s)))
    d_arm = s[ix].sum(axis=1) / c[ix].sum(axis=1)
    st.lo, st.hi = (float(x) for x in np.percentile(d_arm, [2.5, 97.5]))
    st.p = boot_p(d_arm)
    if calm:
        cs, cc = _cluster_arrays(calm)
        jx = rng.integers(0, len(cs), (n, len(cs)))
        d_calm = cs[jx].sum(axis=1) / cc[jx].sum(axis=1)
        g = d_arm - d_calm
        st.gain = st.mean - float(cs.sum() / cc.sum())
        st.glo, st.ghi = (float(x) for x in np.percentile(g, [2.5, 97.5]))
        st.gp = boot_p(g)
    return st


def holm2(pvals: dict) -> dict:
    """`{arm: Holm-adjusted p}` over K-BEAR and K-EVOL, m = 2 always: an arm with no p
    enters at 1.0, so it can never loosen the other's adjustment."""
    full = {a: (p if p is not None and math.isfinite(p) else 1.0) for a, p in pvals.items()}
    for a in ARMS:
        full.setdefault(a, 1.0)
    return {a: v[0] for a, v in holm(full).items()}


@dataclass
class Grade:
    st: Stat
    mean_padj: float
    gain_padj: float


def conds(g: Grade) -> dict:
    st = g.st
    return dict(c1=st.lo > 0, c2=g.mean_padj < ALPHA, c3=st.glo > 0, c4=g.gain_padj < ALPHA,
                neg=st.hi < 0)


def _cp(c: dict) -> bool:
    return c["c1"] and c["c2"] and c["c3"] and c["c4"]


def _pns(c: dict) -> bool:
    return c["c1"] and c["c2"] and not (c["c3"] and c["c4"])


def word_without_pbo(g: Grade) -> str:
    c = conds(g)
    if _cp(c):
        return CP
    if _pns(c):
        return PNS
    if c["neg"] and c["c2"]:
        return CONTRARY
    return NULL


def verdict(g: Grade, k_arm: int, k_calm: int, pbo: float | None, sens: Grade | None,
            forward: bool = False) -> tuple[str, list[str]]:
    """`(word, notes)`, first match. In-sample: UNDERPOWERED below the floor in the arm or
    CALM; PBO not computed or above 0.50 turns every word into NULL; a CALENDAR-PAYS or
    PAYS-NOT-SIGNAL whose own conditions fail with every exit_unmarked entry at R = -1 is
    NULL. Forward: STILL-OPEN below the floor in the arm or CALM, and no PBO clause."""
    notes: list[str] = []
    if forward:
        if k_arm < FLOOR or k_calm < FLOOR:
            return STILL_OPEN, notes
    elif k_arm < FLOOR or k_calm < FLOOR:
        return UNDERPOWERED, notes
    w = word_without_pbo(g)
    if not forward:
        if pbo is None:
            return NULL, ["PBO not computed"]
        if pbo > PBO_VETO:
            return NULL, ["PBO veto"]
    if w in (CP, PNS) and sens is not None:
        c = conds(sens)
        if not (_cp(c) if w == CP else _pns(c)):
            return NULL, ["exit-drop sensitive"]
    if not forward and PBO_FRAGILE < pbo <= PBO_VETO:
        notes.append("selection fragile")
    return w, notes


def pbo_grid(rows_by_cfg: dict, lo: str = IN_SAMPLE_START, hi: str = IN_SAMPLE_END) -> np.ndarray:
    """`T x 12 x 2`: per calendar quarter of D, [sum of R, entry count]; one zero quarter
    padded at the head so S = 20 divides T."""
    qs, cur = [], quarter(lo)
    while cur <= quarter(hi):
        qs.append(cur)
        cur = (cur[0] + 1, 1) if cur[1] == 4 else (cur[0], cur[1] + 1)
    pos = {q: i for i, q in enumerate(qs)}
    M = np.zeros((len(qs), len(rows_by_cfg), 2))
    for j, rows in enumerate(rows_by_cfg.values()):
        for d, r in rows:
            i = pos.get(quarter(d))
            if i is not None:
                M[i, j, 0] += r
                M[i, j, 1] += 1
    return PBO.pad_head(M, PBO_S)[0]


def pbo_of(M: np.ndarray) -> float | None:
    try:
        return float(PBO.cscv(M, S=PBO_S, metric=PBO.ratio_metric).pbo)
    except ValueError:
        return None


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
# ════════════════════════════════════════════════════════════════════════════

def section(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def f3(x, fmt: str = "+.3f") -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def ci_txt(st: Stat) -> str:
    if not math.isfinite(st.lo):
        return f"mean R {f3(st.mean)}"
    return f"mean R {f3(st.mean)} [{f3(st.lo)}, {f3(st.hi)}] ±{st.half:.3f}"


def gain_txt(st: Stat) -> str:
    if not math.isfinite(st.glo):
        return "gain n/a"
    return f"gain {f3(st.gain)} [{f3(st.glo)}, {f3(st.ghi)}] ±{st.ghalf:.3f}"


def pbo_txt(pbo: float | None) -> str:
    if pbo is None:
        return "not computed"
    note = "  -> PBO veto" if pbo > PBO_VETO else "  -> selection fragile" if pbo > PBO_FRAGILE else ""
    return f"{pbo:.3f}{note}"


def _mean(xs) -> float:
    xs = list(xs)
    return float(np.mean(xs)) if xs else float("nan")


def print_header(full: SM.Cal, cal: SM.Cal, rows: dict) -> None:
    print("signal_call_calendar — after a mech BEAR or E-VOL signal, does a SPY call calendar pay?")
    print(f"registration: {REGISTRATION} (accepted by default; stamp {REGISTERED})")
    print("era: current (inputs are unversioned market closes and option quotes)")
    print(f"windows: in-sample signal dates {IN_SAMPLE_START} -> {IN_SAMPLE_END}; gap {GAP_START} -> "
          f"{GAP_END} (in no population); forward from {FORWARD_START}; sunset {SUNSET}")
    print(f"seal: this study reads no play row, so the holdout seal does not bind; the in-sample "
          f"window ends the day before era.SEAL_START ({era_mod.SEAL_START})")
    dirty = "dirty" if SM._git("status", "--porcelain") else "clean"
    print(f"git: {SM._git('rev-parse', '--short', 'HEAD')} (working tree {dirty})")
    print("inputs read:")
    for name in SERIES:
        print(SM._inventory(SM._cache_path(name)))
    print(f"  option cache {CACHE_DIR.relative_to(ROOT)} and its skip-list")
    print("series read (in-sample, after the cut):")
    for name, arr in (("SPY", cal.close), ("VIX", cal.vix), ("VIX3M", cal.vix3m)):
        ok = [d for d, v in zip(cal.dates, arr) if np.isfinite(v)]
        print(f"  {name:<6} {ok[0] if ok else '—'} -> {ok[-1] if ok else '—'}")
    print(f"series read (forward): SPY {full.dates[0]} -> {full.dates[-1]}")
    print(f"bootstrap: {BOOT_N} draws, seed {SEED}, calendar-month clusters of D; commission "
          f"${COMMISSION:.2f} per contract per leg-side, slippage 0")


def census_line(label: str, arm: str, es: list[Entry]) -> str:
    c = Counter(e.status for e in es)
    drops = Counter(e.sel.reason for e in es if e.status == "drop")
    return (f"  {label:<14} {arm:<7} n {len(es):>4}  built {c['built']:>4}  await {c['await']:>4}  "
            f"drop {c['drop']:>3} {dict(drops) if drops else ''}")


# ════════════════════════════════════════════════════════════════════════════
# The in-sample run
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class CellRes:
    ps: list                     # Priced
    why: Counter                 # unpriced: selection drops, refusals, pricing drops
    n_await: int
    unmarked: list               # Entry dropped as exit_unmarked
    by_year: Counter             # (year, reason) for every unpriced entry


def priced_cell(book: Book, es: list[Entry]) -> CellRes:
    res = CellRes([], Counter(), 0, [], Counter())
    for e in es:
        if e.status == "await":
            res.n_await += 1
            continue
        why = e.sel.reason if e.status == "drop" else None
        if why is None:
            p = book.price(e)
            if isinstance(p, str):
                why = p
                if p == "exit_unmarked":
                    res.unmarked.append(e)
            else:
                res.ps.append(p)
        if why is not None:
            res.why[why] += 1
            res.by_year[(e.d[:4], why)] += 1
    return res


def rows_of(ps: list[Priced]) -> list[tuple[str, float]]:
    return [(p.e.d, p.R) for p in ps]


def census(book: Book, pop: Pop, entries: dict, chain, label: str) -> None:
    print(f"  {label} onsets (before any drop): "
          + "  ".join(f"{s} {len(pop.onsets[s])}" for s in SIGNALS))
    print("  n_truncated (D + 1 + 21 past the window's last close): "
          + "  ".join(f"{s} {pop.trunc[s]}" for s in SIGNALS) + f"  CALM {pop.calm_trunc}")
    print(f"  calm days {pop.calm_n}; dropped where mech BEAR or E-VOL holds on D: {pop.calm_overlap}; "
          f"candidate calm entries {len(pop.calm)}")
    print("  candidate entries: " + "  ".join(f"{ARM_OF[s]} {len(pop.signals[s])}" for s in SIGNALS)
          + f"  CALM {len(pop.calm)}")
    print("  selection per cell (counts only; no price read):")
    for (cell, arm), es in entries.items():
        print(census_line(cell, arm, es))
    named, rows = contract_census(chain, entries)
    cached = sum(1 for o, x, k in named if chain.cached(TICKER, x, k, o))
    print(f"  contracts named {len(named)}; cached {cached}; fetch list {len(rows)} unique uncached")
    for t in rows:
        print(f"    {t['expiration'].isoformat()} {t['strike']:>9.2f}{t['opt_type'][0]}  {t['category']}")


def in_sample(full: SM.Cal, chain, evidence, boot_n: int = BOOT_N, pbo_fn=pbo_of) -> dict:
    """Everything in-sample, from the cut series and the cut chain. Returns the state the
    verdict needs, or `{"await": n}` when the await gate stays shut."""
    cal = SM.cut_cal(full, IN_SAMPLE_END)
    cut = CutChain(chain, date.fromisoformat(IN_SAMPLE_END))
    pop = in_sample_pop(cal)
    book = Book(cal, cut, evidence)

    section("GATE GS — the onsets equal state_map.q4_trades on the same run")
    gs = gate_gs(cut, evidence, cal, pop)
    bad = [s for s, (a, b) in gs.items() if a != b]
    for s, (a, b) in gs.items():
        print(f"  {s}: study {len(a)} onset dates from {IN_SAMPLE_START}, q4_trades {len(b)} — "
              f"{'pass' if a == b else 'FAIL'}")
    if bad:
        raise Refused(EXIT_GS, f"GS: the onset set differs from state_map.q4_trades for {bad}. Exit 4.")

    section("CENSUS — in-sample entries, the fetch list and every selection drop (no price read)")
    entries = all_entries(book, pop)
    census(book, pop, entries, cut, "in-sample")
    head = [e for (cell, _arm), es in entries.items() if cell == "headline" for e in es]
    try:
        book.open_outcomes(head)
    except AwaitingScrape as exc:
        return {"await": str(exc)}

    section("OUTCOMES — per cell (R net of commission; the graded unit is one calendar)")
    print(f"  R = ((exit value - debit) x 100 - ${COST:.2f}) / (debit x 100 + ${COST:.2f}); exit value "
          "floored at 0")
    cells = {key: priced_cell(book, es) for key, es in entries.items()}
    calm_rows = {cell: rows_of(cells[(cell, CALM)].ps) for cell, _ in CALM_CELLS
                 if not cells[(cell, CALM)].n_await}
    stats: dict = {}
    for cell, _g in CALM_CELLS:
        c = cells[(cell, CALM)]
        if c.n_await:
            stats[(cell, CALM)] = Stat(0, 0, float("nan"))
            print(f"  CALM    {cell:<14} NOT BUILT ({c.n_await} await)")
            continue
        st = boot(calm_rows[cell], None, boot_n)
        stats[(cell, CALM)] = st
        flag = "" if st.k >= FLOOR else f"  {THIN}"
        print(f"  CALM    {cell:<14} priced {st.n:>4} clusters {st.k:>3}  {ci_txt(st)}  "
              f"unpriced {dict(c.why)}{flag}")
    for s in SIGNALS:
        arm = ARM_OF[s]
        for cell, _g in CELLS:
            c = cells[(cell, arm)]
            if c.n_await:
                stats[(cell, arm)] = Stat(0, 0, float("nan"))
                print(f"  {arm:<7} {cell:<14} NOT BUILT ({c.n_await} await)")
                continue
            st = boot(rows_of(c.ps), calm_rows.get(cell), boot_n)
            stats[(cell, arm)] = st
            flag = "" if st.k >= FLOOR else f"  {THIN}"
            if cell == "headline":
                print(f"  {arm:<7} {cell:<14} priced {st.n:>4} clusters {st.k:>3}  {ci_txt(st)}  "
                      f"p {f3(st.p, '.4f')}  {gain_txt(st)}  p {f3(st.gp, '.4f')}  unpriced {dict(c.why)}")
            else:
                gtxt = f"  gain {f3(st.gain)}" if cell in calm_rows else ""
                print(f"  {arm:<7} {cell:<14} priced {st.n:>4} clusters {st.k:>3}  {ci_txt(st)}{gtxt}  "
                      f"unpriced {dict(c.why)}{flag}")
    print(f"  monotonicity check: called on {book.mono_checked} entries, fired "
          f"{sum(c.why[SIM.NON_MONOTONIC_REFUSAL] for c in cells.values())}")
    print(f"  defined-risk clamp: called on {book.clamp_checked} entries, bounded "
          f"{sum(p.clamp for c in cells.values() for p in c.ps)} (expected 0)")

    section("MULTIPLE COMPARISONS — Holm at 0.05, m = 2 per family, headline cell")
    padj_m = holm2({a: stats[("headline", a)].p for a in ARMS})
    padj_g = holm2({a: stats[("headline", a)].gp for a in ARMS})
    for a in ARMS:
        st = stats[("headline", a)]
        print(f"  {a}: mean R p {f3(st.p, '.4f')} -> Holm {padj_m[a]:.4f};  gain p {f3(st.gp, '.4f')} "
              f"-> Holm {padj_g[a]:.4f}")

    section("PBO / CSCV — 12 signal cells, calendar quarters of D, S = 20")
    awaiting_cells = [k for k, c in cells.items() if k[1] != CALM and c.n_await]
    if awaiting_cells:
        pbo = None
        print(f"  {len(awaiting_cells)} signal cells still await a fetch")
    else:
        grid = {(cell, ARM_OF[s]): rows_of(cells[(cell, ARM_OF[s])].ps) for s in SIGNALS for cell, _ in CELLS}
        pbo = pbo_fn(pbo_grid(grid))
    print(f"  PBO: {pbo_txt(pbo)}")

    section("EXIT-DROP SENSITIVITY — exit_unmarked as R = -1 in a signal arm, left out of CALM")
    sens_rows = {}
    for a in ARMS:
        c = cells[("headline", a)]
        sens_rows[a] = rows_of(c.ps) + [(e.d, -1.0) for e in c.unmarked]
        print(f"  {a}: exit_unmarked {len(c.unmarked)}; mean R with them at -1 "
              f"{f3(_mean(r for _, r in sens_rows[a]))}")
    print(f"  CALM: exit_unmarked {len(cells[('headline', CALM)].unmarked)}; mean R with them left out "
          f"{f3(stats[('headline', CALM)].mean)}")
    sens_st = {a: boot(sens_rows[a], calm_rows["headline"], boot_n) for a in ARMS}
    s_m = holm2({a: sens_st[a].p for a in ARMS})
    s_g = holm2({a: sens_st[a].gp for a in ARMS})

    printed_only(cells)

    section("IN-SAMPLE WORDS — per graded arm, first matching row")
    k_calm = stats[("headline", CALM)].k
    words = {}
    for a in ARMS:
        g = Grade(stats[("headline", a)], padj_m[a], padj_g[a])
        sg = Grade(sens_st[a], s_m[a], s_g[a])
        w, notes = verdict(g, g.st.k, k_calm, pbo, sg)
        words[a] = (w, notes)
        tail = f" ({', '.join(notes)})" if notes else ""
        half = f"; half-width {g.st.half:.3f}" if w == NULL and math.isfinite(g.st.lo) else ""
        print(f"  {a}: clusters {g.st.k} (CALM {k_calm}, floor {FLOOR}) -> {w}{tail}{half}")
    return {"words": words, "pbo": pbo}


def printed_only(cells: dict) -> None:
    section("PRINTED ONLY — no verdict reads anything below")
    groups = [(a, cells[("headline", a)]) for a in ARMS + (CALM,)]
    print("  MFE, MAE and capture on the daily mark path (headline cell)")
    for a, c in groups:
        smfe = sum(p.mfe for p in c.ps)
        cap = sum(p.R for p in c.ps) / smfe if smfe > 0 else float("nan")
        print(f"    {a:<7} n {len(c.ps):>4}  mean MFE {f3(_mean(p.mfe for p in c.ps))}  mean MAE "
              f"{f3(_mean(p.mae for p in c.ps))}  capture {f3(cap)}")
    print("  R by the sign of SPY's hold return (not blind: Q4 printed SPY's path after every onset)")
    for a, c in groups:
        up = [p.R for p in c.ps if p.hold > 0]
        dn = [p.R for p in c.ps if p.hold <= 0]
        na = [p.R for p in c.ps if not math.isfinite(p.hold)]
        print(f"    {a:<7} SPY up n {len(up):>4} mean R {f3(_mean(up))}   SPY flat or down n {len(dn):>4} "
              f"mean R {f3(_mean(dn))}   missing n {len(na):>4} mean R {f3(_mean(na))}")
    print("  R by VIX above or below VIX3M at the entry session's close")
    for a, c in groups:
        parts = []
        for v in ("above", "below", "missing"):
            xs = [p.R for p in c.ps if p.vix_state == v]
            parts.append(f"{v} n {len(xs):>4} mean R {f3(_mean(xs))}")
        print(f"    {a:<7} " + "   ".join(parts))
    print("  Short-expiry exits (headline cell)")
    for a, c in groups:
        k = sum(1 for p in c.ps if p.exit_reason == "short_expiry")
        share = f3(k / len(c.ps), ".1%") if c.ps else "n/a"
        print(f"    {a:<7} {k} of {len(c.ps)} exits ({share})")
    print("  Counts (headline cell): drops and refusals by reason, floored exits, stale marks, clamp hits")
    for a, c in groups:
        print(f"    {a:<7} all years: {dict(c.why)}  floored {sum(p.floored for p in c.ps)}  stale "
              f"{sum(p.stale for p in c.ps)}  clamp {sum(p.clamp for p in c.ps)}")
        by = Counter(c.by_year)
        for p in c.ps:
            y = p.e.d[:4]
            by[(y, "floored_exit")] += int(p.floored)
            by[(y, "stale_mark")] += p.stale
            by[(y, "clamp_hit")] += p.clamp
        for (y, kind), n in sorted(by.items()):
            if n:
                print(f"      {y}  {kind:<24} {n}")
    print("  Per entry (headline cell, signal arms)")
    for a in ARMS:
        for p in sorted(cells[("headline", a)].ps, key=lambda p: p.e.d):
            s = p.e.sel
            print(f"    {p.e.d}  {a:<7} K {s.strike:>7.2f}  short {s.short_exp}  long {s.long_exp}  "
                  f"debit {p.debit:>6.2f}  R {p.R:+.3f}  gross R {p.gross:+.3f}  exit {p.exit_reason}")


# ════════════════════════════════════════════════════════════════════════════
# The forward read
# ════════════════════════════════════════════════════════════════════════════

def forward_entries(book: Book, pop: Pop) -> dict:
    """The forward read grades the headline cell only; the zone split prints beside it."""
    out = {("headline", ARM_OF[s]): book.entries(ARM_OF[s], pop.signals[s], HEAD) for s in SIGNALS}
    out[("headline", CALM)] = book.entries(CALM, pop.calm, HEAD)
    for s in SIGNALS:
        out[("zone", ARM_OF[s])] = book.entries(ARM_OF[s], pop.in_zone[s], HEAD)
    return out


def forward(full: SM.Cal, chain, evidence, boot_n: int = BOOT_N) -> dict:
    section(f"FORWARD — onsets from {FORWARD_START}, the current sell-off out (one shot; no PBO veto)")
    pop = forward_pop(full)
    book = Book(full, chain, evidence)
    entries = forward_entries(book, pop)
    head = [e for (cell, _a), es in entries.items() if cell == "headline" for e in es]
    print("  forward onsets counted (re-arm sessions after the anchor, outside the zone): "
          + "  ".join(f"{s} {len(pop.onsets[s])}" for s in SIGNALS))
    print("  onsets inside the re-arm of the runs in force on the anchor (never count): "
          + "  ".join(f"{s} {pop.excluded_runs[s]}" for s in SIGNALS))
    print("  n_truncated: " + "  ".join(f"{s} {pop.trunc[s]}" for s in SIGNALS)
          + f"  CALM {pop.calm_trunc}; calm days {pop.calm_n}, overlap drops {pop.calm_overlap}")
    try:
        book.open_outcomes(head)
    except AwaitingScrape as exc:
        print(f"  {NOT_BUILT}: {exc}; every forward arm stays {STILL_OPEN}")
        return {a: STILL_OPEN for a in ARMS}
    res = {k: priced_cell(book, es) for k, es in entries.items()}
    calm_rows = rows_of(res[("headline", CALM)].ps)
    st, sens = {}, {}
    for a in ARMS:
        c = res[("headline", a)]
        st[a] = boot(rows_of(c.ps), calm_rows, boot_n)
        sens[a] = boot(rows_of(c.ps) + [(e.d, -1.0) for e in c.unmarked], calm_rows, boot_n)
    pm, pg = holm2({a: st[a].p for a in ARMS}), holm2({a: st[a].gp for a in ARMS})
    sm, sg = holm2({a: sens[a].p for a in ARMS}), holm2({a: sens[a].gp for a in ARMS})
    k_calm = n_clusters(calm_rows)
    print(f"  CALM    priced {len(calm_rows):>3} clusters {k_calm:>3}  mean R {f3(_mean(r for _, r in calm_rows))}  "
          f"unpriced {dict(res[('headline', CALM)].why)}")
    words = {}
    for a in ARMS:
        w, notes = verdict(Grade(st[a], pm[a], pg[a]), st[a].k, k_calm, None,
                           Grade(sens[a], sm[a], sg[a]), forward=True)
        words[a] = w
        tail = f" ({', '.join(notes)})" if notes else ""
        print(f"  {a:<7} priced {st[a].n:>3} clusters {st[a].k:>3} (floor {FLOOR})  {ci_txt(st[a])}  "
              f"{gain_txt(st[a])}  Holm {pm[a]:.4f} / {pg[a]:.4f}  unpriced {dict(res[('headline', a)].why)}"
              f"  -> {w}{tail}")
    for a in ARMS:
        z = res[("zone", a)]
        print(f"  split, inside the current episode's zone ({a}): onsets {len(entries[('zone', a)])}, "
              f"priced {len(z.ps)}, mean R {f3(_mean(p.R for p in z.ps))}")
    print("  The first forward run in which an arm prints a word other than STILL-OPEN is its verdict of record.")
    print(f"  Sunset {SUNSET}: an arm still STILL-OPEN then keeps STILL-OPEN.")
    return words


# ════════════════════════════════════════════════════════════════════════════
# The run
# ════════════════════════════════════════════════════════════════════════════

def operator_steps() -> None:
    print("  Operator-run steps, in order (none runs from here):")
    print(f"    1. {FETCH_CMD} --dry-run   (then --limit N)")
    print("    2. python3 scripts/backup_research_caches.py push")
    print("    3. re-run this study; a fetch can expose a nearer strike or prove one unlisted,")
    print("       so steps 1-3 repeat until no headline entry awaits")
    print("  It does not run beside another option-cache writer: one writer.")


def banner(words: dict, pbo: float | None, fwd: dict) -> None:
    section("VERDICT")
    for s in SIGNALS:
        a = ARM_OF[s]
        w, notes = words[a]
        extra = "; ".join(notes + [NOTES])
        print(f"  >>> signal_call_calendar {a} ({BANNER_ARM.format(sig=s)}): {w} <<<  [{extra}]")
    print(f"  >>> signal_call_calendar PBO: {'not computed' if pbo is None else f'{pbo:.3f}'} <<<  [{NOTES}]")
    print(f"  >>> signal_call_calendar FORWARD (onsets from {FORWARD_START}, current sell-off out): "
          f"K-BEAR {fwd['K-BEAR']} K-EVOL {fwd['K-EVOL']} <<<  [{NOTES}]")
    print()
    print("  CALENDAR-PAYS files 'to be tested' in deployment-evidence.md, pending the forward read.")
    print("  Nothing ships from this study (signal_call_calendar.md).")


def run(boot_n: int = BOOT_N) -> int:
    era = era_mod.requested_era()
    if era != era_mod.CURRENT:
        print(f"REFUSED — era {era}: this study reads unversioned market closes and option quotes "
              "only; run it on the current era. Exit 3.")
        return EXIT_INPUT
    full, rows = load_inputs()
    cal = SM.cut_cal(full, IN_SAMPLE_END)
    print_header(full, cal, rows)
    section("GATES")
    print(f"  GE: SPY, ^VIX and ^VIX3M cached and reaching {IN_SAMPLE_END}; option cache present — pass")
    bad_hash = SPD.gate_hash()
    print(f"  GH: selloff_put_diagonal.gate_hash (E-DD5 vs EPISODE_DEFS_SHA256) — "
          f"{'pass' if not bad_hash else 'FAIL'}")
    if bad_hash:
        raise Refused(EXIT_GH, f"GH: {bad_hash[0]}. Exit 5.")
    print("  GX: strike, expiry and listing choices read nothing after the entry session "
          "(tests/test_signal_call_calendar.py)")
    print(f"  GC: every series and every quote is cut at {IN_SAMPLE_END} before the in-sample run "
          "(tests/test_signal_call_calendar.py)")
    print(f"  floors: {FLOOR} month clusters per graded arm, CALM, parameter cell (else {THIN}) and forward arm")
    chain, evidence = env()
    out = in_sample(full, chain, evidence, boot_n)
    if "await" in out:
        section(f"VERDICT: {NOT_BUILT}")
        print(f"  HEADLINE: {NOT_BUILT} — {out['await']}.")
        print("  No outcome was computed for any arm: no R, no P&L, no CI.")
        operator_steps()
        return 0
    fwd = forward(full, chain, evidence, boot_n)
    banner(out["words"], out["pbo"], fwd)
    return 0


def print_fetch_list() -> int:
    """`--fetch-list`: the census of contracts and the fetch rows. Selection only."""
    full, _ = load_inputs()
    chain, evidence = env()
    plan = fetch_plan(full, chain, evidence)
    print(f"contracts named: in-sample {len(plan['n_in'])}, forward {len(plan['n_fw'])}, "
          f"together {len(plan['named'])}; already cached {plan['cached']}")
    print(f"unique uncached contracts to fetch: {len(plan['rows'])} "
          f"(in-sample {len(plan['rows_in'])}, forward {len(plan['rows_fw'])})")
    for t in plan["rows"]:
        print(f"  {t['ticker']:<6} {t['expiration'].isoformat()} {t['strike']:>9.2f}{t['opt_type'][0]}  "
              f"{t['category']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fetch-list", action="store_true",
                    help="print the contracts the rules name and the uncached fetch list; price nothing")
    args = ap.parse_args(argv)
    try:
        return print_fetch_list() if args.fetch_list else run()
    except Refused as exc:
        print(f"REFUSED — {exc.message}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
