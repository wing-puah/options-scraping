"""Structure sweep: would another option structure have done better on the same 2026 plays?

Binding spec: research/pre-registrations/f3_structure/structure_sweep.md, registered
and accepted by default 2026-10-22, before this module existed. Its gates, arms,
metrics and verdict wording are not restated here as choices; where the build had
to rule on an ambiguity, the ruling is folded into the registration as a
`Resolved at build (2026-10-22)` paragraph and named in a comment below.

WHAT IT DOES
------------
Every `source == real` v4 row with a 2026 signal date keeps its ticker, signal
date, front expiry and RECORDED entry day (`bear_rewrap.recorded_entry_date`).
Only the wrapper changes:

    ARM P  the play's own legs, re-priced here (control)
    ARM F  every quantity negated
    ARM T  a vertical's other option type, same strikes and direction
    ARM C  short iron condor, shorts at |Delta| 0.16, wings at short +/- 0.03 x spot
    ARM B  short iron butterfly at the listed strike nearest spot, same wings
    ARM D  long straddle at the ARM B strike
    ARM G  long strangle at the ARM C short strikes
    ARM K  long ATM call calendar: short the play's expiry, long the nearest
           cached expiry >= 14 days later, closed at the front expiry
    ARM S  short strangle at the ARM C strikes, no wings (descriptive, never graded)

REUSED, NEVER COPIED
--------------------
Pricing is `bear_rewrap`'s mirror of production (`net_entry`, `net_marks`,
`basis_of`, and through them production's entry fill, junk-quote rule, zero-bid
mark, carry rule and defined-risk clamp). Strike pickers and the spot rule are
`index_vrp`'s (`select_atm`, `select_delta`, `select_wing`, `Chain.spot`).
Sizing is `financed_spread.size_contracts`. The exit profile is production's own
merge (`simulate._effective_sim_cfg`) and the cost knobs production's own
(`simulate._cost_knobs`), both read from `config/backtest.yml`. Exits replay on
the FROZEN harness. Statistics: `protocol.boot_ci_by_date` /
`boot_ci_paired_by_date`, `ticker_class.holm`, `pbo.cscv`.

THE TWO SAMPLES
---------------
A cache file's mtime is its fetch time. `CacheView` is the one filter: S1 sees
only files with mtime at or before the split instant (2026-10-22 23:00 +08:00,
epoched below), and every S1 chain, strike pick and price goes through it. S2 is
the whole cache as it stands when the study runs, and only for rows an arm could
not price in S1. Neither `bear_rewrap` nor `index_vrp` is edited: the view builds
`index_vrp.Chain`s from its own file listing and admits each leg before
`bear_rewrap.leg_details` reads it.

Read-only. Fetches nothing, writes no tab, never touches a cache file. Run:

    python -m scripts.backtest_study run structure_sweep
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _max_loss_per_unit  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest import simulate as SIM  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark.ticker_class import (  # noqa: E402
    ALPHA, holm,
)
from scripts.backtest_study.f3_structure import bear_rewrap as BR  # noqa: E402
from scripts.backtest_study.f3_structure import financed_spread as FS  # noqa: E402
from scripts.backtest_study.f3_structure import index_vrp as IV  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import CREDIT_PROD, DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import Trade, replay  # noqa: E402
from scripts.backtest_study.lib.replay_basis import bounded  # noqa: E402

REGISTRATION = "research/pre-registrations/f3_structure/structure_sweep.md"
ACCEPTED = "2026-10-22"

# Exit codes this study returns as a DESIGNED refusal: 2 = era too thin,
# 3 = era mismatch OR the registration's G-REPRO refusal. Literal on purpose:
# run.py reads it by AST parse.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
EXIT_REPRO = 3

# ── registered constants (frozen; a change is a new registration) ────────────
SEED = 20261022
BOOT_N = 10_000
SPLIT_LOCAL = datetime(2026, 10, 22, 23, 0, 0, tzinfo=timezone(timedelta(hours=8)))
SPLIT_EPOCH = 1792681200.0           # == SPLIT_LOCAL.timestamp(); asserted in main()
SIGNAL_YEAR = "2026"
SHORT_DELTA = 0.16
WING_FRAC = 0.03
CAL_MIN_GAP_DAYS = 14
# Pick tolerances — Resolved at build (2026-10-22), AFTER the first run exposed
# off-target picks on sparse single-name caches (a 0.93-delta call taken as the
# "0.16" short). They are the scoping census's own bands, fixed before the
# re-run and not tuned to it. A refused pick leaves the row unpriced for that arm.
DELTA_TOL = 0.05                     # |cached |Delta| - 0.16| <= 0.05
ATM_TOL = 0.03                       # |ATM strike - spot| <= 3% of spot
WING_BAND = (0.5, 2.0)               # wing distance / (0.03 x spot)
REPRO_TOL = 1.00                     # dollars
REPRO_MAX_FAIL = 0.10
THIN_ROWS, THIN_DATES = 30, 15
S2_MIN_ROWS = 30
PBO_S = 16
PBO_MAX = 0.5

ARMS = ("P", "F", "T", "C", "B", "D", "G", "K", "S")
GRADED = ("F", "T", "C", "B", "D", "G", "K")
ARM_NAME = {
    "P": "play, re-priced", "F": "flipped", "T": "type swap",
    "C": "short iron condor", "B": "short iron butterfly", "D": "long straddle",
    "G": "long strangle", "K": "long ATM call calendar", "S": "short strangle",
}
CANDIDATE, S1_ONLY, LOSES, NULL, THIN = (
    "CANDIDATE", "S1-ONLY", "LOSES-TO-PLAY", "NULL", "THIN")
STUDY_FOUND, STUDY_NULL = "CANDIDATE-FOUND", "WIDE-NET-NULL"

BACKTEST_YML = ROOT / "config" / "backtest.yml"
OUT_CSV = ROOT / "backtests" / "study_output" / "structure_sweep-latest.csv"


# ════════════════════════════════════════════════════════════════════════════
# The cache view — the ONE place the S1 mtime rule lives
# ════════════════════════════════════════════════════════════════════════════

def parse_cache_name(name: str):
    """`(TICKER, expiry, "C"|"P", strike)` for `T_YYYYMMDD_K{C|P}.csv`, else None."""
    if not name.endswith(".csv"):
        return None
    parts = name[:-4].rsplit("_", 2)
    if len(parts) != 3:
        return None
    tk, stamp, ks = parts
    try:
        exp = date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
        typ, strike = ks[-1], float(ks[:-1])
    except (ValueError, IndexError):
        return None
    if typ not in ("C", "P") or len(stamp) != 8:
        return None
    return tk, exp, typ, strike


def build_index(cache_dir: Path = HISTORY_CACHE) -> dict:
    """`{(TICKER, expiry): {(typ, strike): path}}` from ONE directory scan.

    The cache holds ~10^5 files; a `glob` per chain or per strike (what
    `bear_rewrap.cached_expiries` and `index_vrp.load_chain` do) rescans all of
    them each call. Listing only — no mtime is decided here; `CacheView.admits`
    stats each file live when it is used.
    """
    idx: dict = defaultdict(dict)
    with os.scandir(cache_dir) as it:
        for e in it:
            p = parse_cache_name(e.name)
            if p is None:
                continue
            tk, exp, typ, k = p
            idx[(tk, exp)][(typ, k)] = Path(e.path)
    return dict(idx)


def _typ(opt_type: str) -> str:
    return "C" if opt_type == "Call" else "P"


def _opt(typ: str) -> str:
    return "Call" if typ == "C" else "Put"


class CacheView:
    """The cache as one sample may see it. `cutoff=None` is the whole cache (S2).

    Every S1 read goes through `details()`: the file is admitted only when its
    mtime is at or before the cutoff, checked BEFORE and AFTER
    `bear_rewrap.leg_details` reads it, so a file another process rewrites
    mid-run cannot slip newer content into S1.
    """

    def __init__(self, cutoff: float | None, index: dict, label: str,
                 cache_dir: Path = HISTORY_CACHE):
        self.cutoff = cutoff
        self.index = index
        self.label = label
        self.cache_dir = cache_dir
        self._chains: dict = {}

    def admits_path(self, path: Path) -> bool:
        try:
            m = path.stat().st_mtime
        except OSError:
            return False
        return self.cutoff is None or m <= self.cutoff

    def path_of(self, leg: Leg) -> Path:
        return cache_path(self.cache_dir, leg.ticker, leg.expiration, leg.strike,
                          leg.opt_type)

    def details(self, leg: Leg) -> dict | None:
        """`leg_details(leg)` when the view admits the file, else None."""
        p = self.path_of(leg)
        if not self.admits_path(p):
            return None
        d = BR.leg_details(leg)
        if not self.admits_path(p):
            return None
        return d or None

    def admits(self, leg: Leg) -> bool:
        return self.details(leg) is not None

    def chain(self, ticker: str, expiry: date) -> IV.Chain:
        """`index_vrp.Chain` of the ADMITTED contracts of one (ticker, expiry)."""
        key = (ticker.upper(), expiry)
        if key not in self._chains:
            ch = IV.Chain(ticker, expiry)
            for (typ, k) in sorted(self.index.get(key, {})):
                d = self.details(Leg(1, ticker.upper(), expiry, k, _opt(typ)))
                if d:
                    ch.rows[(typ, k)] = d
            self._chains[key] = ch
        return self._chains[key]

    def expiries_with_row(self, ticker: str, strike: float, typ: str,
                          on: date) -> list[date]:
        """Admitted expiries of (ticker, strike, type) whose contract has a row on
        `on` — "cached by the entry day". Ascending."""
        out = []
        tk = ticker.upper()
        for (t2, exp), contracts in self.index.items():
            if t2 != tk or (typ, strike) not in contracts:
                continue
            d = self.details(Leg(1, tk, exp, strike, _opt(typ)))
            if d and on in d:
                out.append(exp)
        return sorted(out)


# ════════════════════════════════════════════════════════════════════════════
# Production config: exit profile, costs
# ════════════════════════════════════════════════════════════════════════════

def load_sim_cfg(path: Path = BACKTEST_YML) -> dict:
    import yaml
    return (yaml.safe_load(path.read_text()) or {}).get("simulation", {}) or {}


def exit_profile(sim_cfg: dict, entry_net: float, signal_date: date,
                 structure: str) -> tuple[dict, str]:
    """`(harness kwargs, "debit"|"credit")` from production's own merge.

    Resolved at build (2026-10-22): the registration's `DEBIT_PROD` is read as
    production's effective debit profile, which adds the BEAR_HE regime trail
    on BEAR_HE dates. `simulate._effective_sim_cfg` is called, never restated.
    """
    eff = SIM._effective_sim_cfg(sim_cfg, entry_net, signal_date.isoformat(), structure)
    prof = dict(pt=eff.get("profit_target"), sl=eff.get("stop_loss"),
                trig=eff.get("trailing_stop_trigger"), trail=eff.get("trailing_stop_pct"),
                tef=eff.get("time_exit_dte_fraction"), be_after=eff.get("be_after"))
    return prof, ("debit" if entry_net > 0 else "credit")


def commission_dollars(legs, contracts: int, sim_cfg: dict) -> float:
    """Production's round-trip commission (`simulate._apply_costs`): per contract
    per leg per side, two sides. Slippage is registered at 0 and asserted 0."""
    comm, slip = SIM._cost_knobs(sim_cfg)
    if slip:
        raise SystemExit(f"config slippage_frac_of_spread={slip}; the registration "
                         f"fixes slippage at 0 — refusing to price on another basis")
    return comm * sum(abs(lg.qty) for lg in legs) * contracts * 2


# ════════════════════════════════════════════════════════════════════════════
# Leg construction
# ════════════════════════════════════════════════════════════════════════════

def flip_legs(legs: list[Leg]) -> list[Leg]:
    """ARM F: every quantity negated."""
    return [lg._replace(qty=-lg.qty) for lg in legs]


def is_vertical(legs: list[Leg]) -> bool:
    """Two legs, one expiry, one type, opposite equal quantities, two strikes."""
    if len(legs) != 2:
        return False
    a, b = legs
    return (a.expiration == b.expiration and a.opt_type == b.opt_type
            and a.ticker == b.ticker and a.qty == -b.qty and a.qty != 0
            and a.strike != b.strike)


def type_swap_legs(legs: list[Leg]) -> list[Leg] | None:
    """ARM T: a vertical's other option type at the same strikes and quantities.
    A bull call K1/K2 (+K1C, -K2C) becomes a bull put K1/K2 (+K1P, -K2P): the
    direction survives because the long strike stays the low one. None for a
    non-vertical."""
    if not is_vertical(legs):
        return None
    return [lg._replace(opt_type="Put" if lg.opt_type == "Call" else "Call")
            for lg in legs]


@dataclass
class Picks:
    """Entry-day strike picks on one chain."""
    spot: float | None = None
    kb: float | None = None           # ARM B / D / K strike
    kc: float | None = None           # ARM C / G / S call strike
    kp: float | None = None           # ARM C / G / S put strike
    wc_c: float | None = None         # ARM C call wing
    wp_c: float | None = None         # ARM C put wing
    wc_b: float | None = None         # ARM B call wing
    wp_b: float | None = None         # ARM B put wing
    atm_why: str = "ok"               # why kb is refused (ARM B / D / K)
    short_why: str = "ok"             # why kc/kp are refused (ARM C / G / S)
    wing_c_why: str = "ok"            # why ARM C's wings are refused
    wing_b_why: str = "ok"            # why ARM B's wings are refused


def delta_on_target(row: dict) -> bool:
    """The picked short's cached |Delta| lies within `DELTA_TOL` of 0.16."""
    dl = IV._num(row.get("Delta"))
    return dl is not None and abs(abs(dl) - SHORT_DELTA) <= DELTA_TOL


def atm_on_spot(k: float, spot: float) -> bool:
    """The ATM strike lies within `ATM_TOL` of spot."""
    return abs(k - spot) <= ATM_TOL * spot


def wing_why(short: float, wing: float | None, spot: float) -> str:
    """`ok`, `no_wing`, or `wing_off_target` when the realised wing distance
    falls outside `WING_BAND` x (0.03 x spot)."""
    if wing is None:
        return "no_wing"
    lo, hi = WING_BAND
    target = WING_FRAC * spot
    return "ok" if lo * target <= abs(wing - short) <= hi * target else "wing_off_target"


def pick_strikes(ch: IV.Chain, ed: date) -> Picks:
    """Every strike rule of the registration, on the entry day's rows only."""
    calls, puts = ch.on(ed, "C"), ch.on(ed, "P")
    pk = Picks(spot=ch.spot(ed))
    if pk.spot is None:
        return pk
    pk.kb = IV.select_atm(calls, puts, pk.spot)
    if pk.kb is None:
        pk.atm_why = "no_atm"
    elif not atm_on_spot(pk.kb, pk.spot):
        pk.atm_why = "atm_off_spot"
    pk.kc = IV.select_delta(calls, +SHORT_DELTA)
    pk.kp = IV.select_delta(puts, -SHORT_DELTA)
    if pk.kc is None or pk.kp is None:
        pk.short_why = "no_short_delta"
    elif not (delta_on_target(calls[pk.kc]) and delta_on_target(puts[pk.kp])):
        pk.short_why = "delta_off_target"
    w = WING_FRAC * pk.spot
    if pk.short_why == "ok":
        pk.wc_c = IV.select_wing(calls, pk.kc, pk.kc + w, "C")
        pk.wp_c = IV.select_wing(puts, pk.kp, pk.kp - w, "P")
        pk.wing_c_why = next((y for y in (wing_why(pk.kc, pk.wc_c, pk.spot),
                                          wing_why(pk.kp, pk.wp_c, pk.spot))
                              if y != "ok"), "ok")
    if pk.atm_why == "ok":
        pk.wc_b = IV.select_wing(calls, pk.kb, pk.kb + w, "C")
        pk.wp_b = IV.select_wing(puts, pk.kb, pk.kb - w, "P")
        pk.wing_b_why = next((y for y in (wing_why(pk.kb, pk.wc_b, pk.spot),
                                          wing_why(pk.kb, pk.wp_b, pk.spot))
                              if y != "ok"), "ok")
    return pk


def chain_legs(arm: str, tk: str, exp: date, pk: Picks) -> tuple[list[Leg] | None, str]:
    """ARM C / B / D / G / S legs from the picks, or `(None, reason)`."""
    def L(q, k, typ):
        return Leg(q, tk, exp, k, _opt(typ))
    if pk.spot is None:
        return None, "no_spot"
    if arm in ("B", "D") and pk.atm_why != "ok":
        return None, pk.atm_why
    if arm in ("C", "G", "S") and pk.short_why != "ok":
        return None, pk.short_why
    if arm == "C":
        if pk.wing_c_why != "ok":
            return None, pk.wing_c_why
        return [L(-1, pk.kc, "C"), L(+1, pk.wc_c, "C"),
                L(-1, pk.kp, "P"), L(+1, pk.wp_c, "P")], "ok"
    if arm == "B":
        if pk.wing_b_why != "ok":
            return None, pk.wing_b_why
        return [L(-1, pk.kb, "C"), L(+1, pk.wc_b, "C"),
                L(-1, pk.kb, "P"), L(+1, pk.wp_b, "P")], "ok"
    if arm == "D":
        return [L(+1, pk.kb, "C"), L(+1, pk.kb, "P")], "ok"
    if arm == "G":
        return [L(+1, pk.kc, "C"), L(+1, pk.kp, "P")], "ok"
    if arm == "S":
        return [L(-1, pk.kc, "C"), L(-1, pk.kp, "P")], "ok"
    raise ValueError(arm)


def calendar_back_expiry(front: date, candidates: list[date]) -> date | None:
    """ARM K: the nearest candidate at least `CAL_MIN_GAP_DAYS` after the front."""
    later = [e for e in candidates if (e - front).days >= CAL_MIN_GAP_DAYS]
    return min(later) if later else None


# ════════════════════════════════════════════════════════════════════════════
# One priced position
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Priced:
    arm: str
    sample: str
    legs: list
    entry_net: float
    sign: str
    contracts: int
    unbounded: bool
    capital: float | None             # per unit, option points
    exit_reason: str
    days_held: int
    gross: float
    cost: float
    net: float
    R: float | None
    mfe: float | None
    mae: float | None
    spot: float | None = None


def leg_str(legs: list[Leg]) -> str:
    """The harness's leg grammar, as `bear_rewrap.synth_trade` writes it."""
    return "\n".join(f"{lg.ticker}:{lg.expiration.isoformat()}:{lg.strike:g}:"
                     f"{_typ(lg.opt_type)} {lg.qty:+d}" for lg in legs)


def price_position(rec: dict, legs: list[Leg], arm: str, ed: date, full_grid: list[date],
                   sim_cfg: dict, sample: str) -> tuple[Priced | None, str]:
    """Price, size, replay and cost one structure on the row's own entry day.

    The path is cut at the play row's `path_data_end` (`replay_basis.bounded`)
    — Resolved at build (2026-10-22): every arm stops where ARM P must stop to
    reproduce the stored row. Grid days before the entry day are unpriced, as
    production's `pre_entry` days are.
    """
    base: Trade = rec["t"]
    row0 = base.row
    sig = base.signal_date
    with BR.basis_of(row0):
        net = BR.net_entry(legs, ed, signal_date=sig)
        if net is None:
            return None, "entry_unpriced"
        if abs(net) <= 1e-9:
            return None, "zero_net"
        marks = BR.net_marks(legs, full_grid)
    marks = [None if day < ed else m for day, m in zip(full_grid, marks)]
    if all(m is None for m in marks):
        return None, "no_marks"
    contracts, unbounded = FS.size_contracts(net, legs)
    row = {
        "signal_date": sig.isoformat(), "ticker": base.ticker,
        "structure": f"sweep_{arm}", "entry_option_price": f"{net:.4f}",
        "contracts": str(contracts), "dte_entry": str(row0.get("dte_entry")),
        "legs": leg_str(legs),
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
        "path_data_end": row0.get("path_data_end") or "",
    }
    try:
        t = bounded(Trade(row))
    except (AssertionError, ValueError, KeyError):
        return None, "trade_build_failed"
    if not any(m is not None for m in t.marks):
        return None, "no_marks"
    prof, sign = exit_profile(sim_cfg, t.entry_net,
                              sig, rec["structure"] if arm == "P" else f"sweep_{arm}")
    out = replay(t, **prof)
    pl = out["pnl_pct"]
    gross = t.dollars(pl)
    cost = commission_dollars(legs, contracts, sim_cfg)
    net_dol = gross - cost
    capital = _max_loss_per_unit(legs, t.entry_net)
    if capital is not None and capital <= 0:
        capital = None
    R = None
    held = [m for m in t.marks[:out["days_held"]] if m is not None]
    mfe = mae = None
    if capital is not None:
        R = net_dol / (capital * 100 * contracts)
        if held:
            scale = t.denom / capital
            pls = [t.pnl_of(m) * scale for m in held]
            mfe, mae = max(pls), min(pls)
    return Priced(arm=arm, sample=sample, legs=legs, entry_net=t.entry_net, sign=sign,
                  contracts=contracts, unbounded=unbounded, capital=capital,
                  exit_reason=out["exit_reason"], days_held=out["days_held"],
                  gross=gross, cost=cost, net=net_dol, R=R, mfe=mfe, mae=mae), "ok"


# ════════════════════════════════════════════════════════════════════════════
# Per-row driver
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class RowResult:
    rec: dict
    entry_day: date | None
    arms: dict = field(default_factory=dict)      # arm -> Priced
    why: dict = field(default_factory=dict)       # arm -> last unpriced reason
    spot: dict = field(default_factory=dict)      # sample -> spot
    repro_ok: bool = False
    repro_why: str = ""
    stored_net: float | None = None


def arm_legs(arm: str, rec: dict, ed: date, view: CacheView,
             picks_cache: dict) -> tuple[list[Leg] | None, str]:
    """The legs `arm` trades on `view`, or `(None, reason)`."""
    base: Trade = rec["t"]
    legs = list(base.legs)
    if arm == "P":
        return legs, "ok"
    if arm == "F":
        return flip_legs(legs), "ok"
    if arm == "T":
        sw = type_swap_legs(legs)
        return (sw, "ok") if sw else (None, "not_vertical")
    front = min(lg.expiration for lg in legs)
    tk = base.ticker.upper()
    if view.label not in picks_cache:
        picks_cache[view.label] = pick_strikes(view.chain(tk, front), ed)
    pk = picks_cache[view.label]
    if arm == "K":
        if pk.spot is None:
            return None, "no_spot"
        if pk.atm_why != "ok":
            return None, pk.atm_why
        back = calendar_back_expiry(front, view.expiries_with_row(tk, pk.kb, "C", ed))
        if back is None:
            return None, "no_back_expiry"
        return [Leg(-1, tk, front, pk.kb, "Call"), Leg(+1, tk, back, pk.kb, "Call")], "ok"
    return chain_legs(arm, tk, front, pk)


def run_row(rec: dict, views: list[CacheView], sim_cfg: dict) -> RowResult:
    base: Trade = rec["t"]
    ed = BR.recorded_entry_date(base)
    res = RowResult(rec=rec, entry_day=ed)
    try:
        res.stored_net = float(base.row.get("realized_pnl_abs"))
    except (TypeError, ValueError):
        res.stored_net = None
    if ed is None:
        res.why = {a: "no_entry_day" for a in ARMS}
        res.repro_why = "no_entry_day"
        return res
    full_grid = Trade(base.row).grid
    picks: dict = {}
    for arm in ARMS:
        why = "unpriced"
        for view in views:
            legs, why = arm_legs(arm, rec, ed, view, picks)
            if legs is None:
                continue
            dets = [view.details(lg) for lg in legs]
            if any(d is None for d in dets):
                why = "leg_not_in_view"
                continue
            # Every arm but the control is built on the entry day's rows only.
            if arm != "P" and any(ed not in d for d in dets):
                why = "leg_no_entry_day_row"
                continue
            pr, why = price_position(rec, legs, arm, ed, full_grid, sim_cfg, view.label)
            if pr is None:
                continue
            if view.label in picks:
                pr.spot = picks[view.label].spot
            res.arms[arm] = pr
            break
        if arm not in res.arms:
            res.why[arm] = why
    for view in views:
        if view.label in picks:
            res.spot[view.label] = picks[view.label].spot
    p = res.arms.get("P")
    if p is None:
        res.repro_why = f"P_unpriced:{res.why.get('P')}"
    elif res.stored_net is None:
        res.repro_why = "no_stored_pnl"
    elif abs(p.net - res.stored_net) <= REPRO_TOL:
        res.repro_ok, res.repro_why = True, "ok"
    else:
        res.repro_why = "pnl_mismatch"
    return res


# ════════════════════════════════════════════════════════════════════════════
# Statistics
# ════════════════════════════════════════════════════════════════════════════

def paired_draws(rows, key_a: str, key_b: str, n: int = BOOT_N, seed: int = SEED):
    """The draws of `protocol.boot_ci_paired_by_date`, which returns only the
    interval. The registration's p-value needs the draws themselves, so this
    replays the SAME loop on the SAME seed; `paired_test` reconciles the
    interval read off these draws with protocol's own and refuses on a mismatch.
    """
    by: dict[str, list[tuple[float, float]]] = {}
    for r in rows:
        if r.get(key_a) is None or r.get(key_b) is None:
            continue
        by.setdefault(str(r["date"]), []).append((float(r[key_a]), float(r[key_b])))
    if not by:
        return []
    dates = list(by)
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        a_pool, b_pool = [], []
        for _ in range(len(dates)):
            for a, b in by[rng.choice(dates)]:
                a_pool.append(a)
                b_pool.append(b)
        diffs.append(statistics.fmean(a_pool) - statistics.fmean(b_pool))
    return diffs


def two_sided_p(draws) -> float:
    """Twice the smaller share of draws on either side of zero, capped at 1."""
    if not draws:
        return float("nan")
    n = len(draws)
    below = sum(1 for d in draws if d <= 0) / n
    above = sum(1 for d in draws if d >= 0) / n
    return min(1.0, 2 * min(below, above))


def paired_test(rows, n: int = BOOT_N, seed: int = SEED, alpha: float = 0.05) -> dict:
    """Mean diff, protocol's CI and the two-sided p, reconciled."""
    if not rows:
        return dict(n=0, dates=0, mean=float("nan"), lo=float("nan"),
                    hi=float("nan"), p=float("nan"))
    lo, hi = P.boot_ci_paired_by_date(rows, "a", "b", n=n, seed=seed, alpha=alpha)
    draws = sorted(paired_draws(rows, "a", "b", n=n, seed=seed))
    if (draws[int(alpha / 2 * n)], draws[int((1 - alpha / 2) * n)]) != (lo, hi):
        raise RuntimeError("paired_draws drifted from protocol.boot_ci_paired_by_date")
    return dict(n=len(rows), dates=len({r["date"] for r in rows}),
                mean=statistics.fmean(r["a"] - r["b"] for r in rows),
                median=statistics.median(r["a"] - r["b"] for r in rows),
                lo=lo, hi=hi, p=two_sided_p(draws))


def arm_token(thin: bool, s1: dict, holm_p: float | None, s2: dict, pbo: float | None) -> str:
    """The registration's verdict table, in its order."""
    if thin:
        return THIN
    sig = holm_p is not None and not math.isnan(holm_p) and holm_p <= ALPHA
    if sig and s1["mean"] > 0:
        s2_ok = s2["n"] >= S2_MIN_ROWS and s2["lo"] > 0
        pbo_ok = pbo is not None and pbo < PBO_MAX
        return CANDIDATE if (s2_ok and pbo_ok) else S1_ONLY
    if sig and s1["mean"] < 0:
        return LOSES
    return NULL


def study_token(tokens: dict) -> str:
    return STUDY_FOUND if any(v == CANDIDATE for v in tokens.values()) else STUDY_NULL


def pbo_matrix(rows_by_arm: dict[str, list[dict]], arms: tuple[str, ...]):
    """`(M, dates)`: T dates x N arms x 2 channels (date-mean R, present).

    Resolved at build (2026-10-22): a date an arm did not price is a MISSING
    cell, carried as (0, 0) and read through `pbo.ratio_metric`, so a subset's
    statistic is the mean of the date means it holds. Head padding to a
    multiple of S adds (0, 0) rows, which that metric ignores.
    """
    dates = sorted({r["date"] for a in arms for r in rows_by_arm.get(a, [])})
    di = {d: i for i, d in enumerate(dates)}
    M = np.zeros((len(dates), len(arms), 2))
    for j, a in enumerate(arms):
        by = defaultdict(list)
        for r in rows_by_arm.get(a, []):
            by[r["date"]].append(r["R"])
        for d, vs in by.items():
            M[di[d], j, 0] = statistics.fmean(vs)
            M[di[d], j, 1] = 1.0
    return M, dates


# ════════════════════════════════════════════════════════════════════════════
# Descriptive labels
# ════════════════════════════════════════════════════════════════════════════

def play_direction(structure: str) -> int:
    s = (structure or "").lower()
    if s.startswith("bull") or s == "long_call":
        return +1
    if s.startswith("bear") or s == "long_put":
        return -1
    return 0


def pv_bucket(structure: str, pv: float | None) -> str:
    """`aligned` when the play's direction has the sign of `price_vector`,
    `against` when opposite, `neutral` otherwise (no direction, zero or blank)."""
    d = play_direction(structure)
    if pv is None or d == 0 or pv == 0:
        return "neutral"
    return "aligned" if d * pv > 0 else "against"


def half_of(d: str) -> str:
    return "H1" if d[5:7] <= "06" else "H2"


def analysis_price_vectors(analysis_csv: Path) -> dict:
    """`{identity_key: price_vector}` from the AnalysisClaude export, first-written
    row per key (as `book._build_analysis_lookup` keeps), via production's
    `identity.identity_key`."""
    from scripts.backtest.shared.identity import identity_key
    out: dict = {}
    if not analysis_csv.exists():
        return out
    with open(analysis_csv, newline="") as fh:
        rows = list(csv.DictReader(fh))
    # The seal binds every export reader, a join table included.
    rows, _info = era_mod.drop_sealed(rows, "date")
    rows.sort(key=lambda r: str(r.get("created_datetime") or ""))
    for r in rows:
        try:
            k = identity_key(r.get("date"), r.get("ticker"), r.get("play"))
        except Exception:
            continue
        if k in out:
            continue
        try:
            out[k] = float(r.get("price_vector"))
        except (TypeError, ValueError):
            out[k] = None
    return out


# ════════════════════════════════════════════════════════════════════════════
# Reporting
# ════════════════════════════════════════════════════════════════════════════

def hdr(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def sub(title: str) -> None:
    print(f"\n--- {title} ---")


def _f(x, fmt="+.3f") -> str:
    return "   n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else format(x, fmt)


def arm_rows(results: list[RowResult], arm: str, sample: str | None) -> list[dict]:
    """Flat rows for one arm (graded R only), with the control's R beside them."""
    out = []
    for res in results:
        if not res.repro_ok:
            continue
        pr = res.arms.get(arm)
        if pr is None or pr.R is None or (sample and pr.sample != sample):
            continue
        p = res.arms["P"]
        rec = res.rec
        out.append(dict(date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
                        R=pr.R, net=pr.net, mfe=pr.mfe, mae=pr.mae,
                        exit_reason=pr.exit_reason, sample=pr.sample,
                        R_P=p.R, P_sample=p.sample,
                        pv=rec.get("_pv"), mech=rec.get("mech_direction") or "none",
                        legs=pr.legs, entry_net=pr.entry_net, contracts=pr.contracts,
                        capital=pr.capital, spot=res.spot.get(pr.sample)))
    return out


def widest_wing(legs: list[Leg]) -> float | None:
    """The widest short-to-long distance on either side of a condor or fly."""
    widths = []
    for typ in ("Call", "Put"):
        sh = [lg.strike for lg in legs if lg.opt_type == typ and lg.qty < 0]
        lo = [lg.strike for lg in legs if lg.opt_type == typ and lg.qty > 0]
        if sh and lo:
            widths.append(abs(lo[0] - sh[0]))
    return max(widths) if widths else None


def credit_ratio(legs: list[Leg], entry_net: float) -> float | None:
    """Credit received over the widest wing; None for a debit or no wing."""
    w = widest_wing(legs)
    if not w or entry_net >= 0:
        return None
    return -entry_net / w


def ratio_bucket(x: float) -> str:
    return "<=0.6" if x <= 0.6 else ("0.6-0.8" if x <= 0.8 else ">0.8")


def credit_wing_cut(results: list[RowResult]) -> None:
    hdr("CREDIT / WIDEST WING — ARM B and ARM C, S1, never graded")
    print("  A credit near the wing width leaves almost no capital at risk, so R "
          "explodes on it.\n  n = graded rows; `no R` = priced rows whose credit "
          "met the width.")
    for arm in ("B", "C"):
        sub(f"ARM {arm} — {ARM_NAME[arm]}")
        rows = arm_rows(results, arm, "S1")
        no_r = sum(1 for res in results if res.repro_ok and arm in res.arms
                   and res.arms[arm].sample == "S1" and res.arms[arm].R is None)
        for b in ("<=0.6", "0.6-0.8", ">0.8"):
            rs = [r for r in rows if (x := credit_ratio(r["legs"], r["entry_net"]))
                  is not None and ratio_bucket(x) == b]
            if not rs:
                print(f"  {b:>8}  n=   0")
                continue
            dr = [r["R"] - r["R_P"] for r in rs if r["R_P"] is not None]
            print(f"  {b:>8}  n={len(rs):>4}  mean R {statistics.fmean(r['R'] for r in rs):+.3f}  "
                  f"median R {statistics.median(r['R'] for r in rs):+.3f}  "
                  f"mean dR {_f(statistics.fmean(dr) if dr else None)}")
        print(f"     no R  n={no_r:>4}")


def _row_line(r: dict) -> str:
    return (f"{r['date']} {r['ticker']:<5} spot {_f(r['spot'], '8.2f')}  "
            f"{leg_str(r['legs']).replace(chr(10), ' | ')}  net entry "
            f"{r['entry_net']:+.2f} x{r['contracts']}")


def top_abs_r(results: list[RowResult], k: int = 5) -> None:
    hdr(f"LARGEST |R| — top {k} S1 rows per arm, for a strike sanity read")
    for arm in ("P",) + GRADED:
        rows = sorted(arm_rows(results, arm, "S1"), key=lambda r: -abs(r["R"]))[:k]
        sub(f"ARM {arm}")
        for r in rows:
            print(f"  R {r['R']:+8.3f}  net ${r['net']:+10,.0f}  {_row_line(r)}")


def paired_of(rows: list[dict], p_sample: str | None = None) -> list[dict]:
    return [dict(date=r["date"], a=r["R"], b=r["R_P"], **{k: r[k] for k in
                 ("structure", "pv", "mech")})
            for r in rows if r["R_P"] is not None
            and (p_sample is None or r["P_sample"] == p_sample)]


def print_coverage(results: list[RowResult], title: str) -> None:
    sub(title)
    print(f"  {'arm':<5} {'name':<23} {'S1':>5} {'S2':>5} {'none':>5}  unpriced reasons")
    for arm in ARMS:
        c = Counter(res.arms[arm].sample if arm in res.arms else "none" for res in results)
        whys = Counter(res.why[arm] for res in results if arm in res.why)
        unb = sum(1 for res in results if arm in res.arms and res.arms[arm].R is None)
        extra = f"  (+{unb} priced, no max loss -> no R)" if unb else ""
        print(f"  {arm:<5} {ARM_NAME[arm]:<23} {c['S1']:>5} {c['S2']:>5} {c['none']:>5}  "
              + "  ".join(f"{k}={v}" for k, v in whys.most_common(4)) + extra)


def mfe_line(rows: list[dict]) -> str:
    mf = [r["mfe"] for r in rows if r["mfe"] is not None]
    ma = [r["mae"] for r in rows if r["mae"] is not None]
    if not mf:
        return "MFE/MAE n/a"
    m_mfe, m_mae = statistics.fmean(mf), statistics.fmean(ma)
    mean_r = statistics.fmean(r["R"] for r in rows)
    cap = mean_r / m_mfe if m_mfe > 0 else float("nan")
    gb = abs(m_mae) / m_mfe if m_mfe > 0 else float("nan")
    return f"MFE {m_mfe:+.3f}  MAE {m_mae:+.3f}  capture {_f(cap, '+.2f')}  gb {_f(gb, '.2f')}"


def descriptive_cuts(results: list[RowResult], label: str) -> None:
    hdr(f"DESCRIPTIVE CUTS — {label}, S1, never graded")
    print("  mean R(arm) / mean R(ARM P) / mean dR on rows both priced in S1. "
          "`aligned` = the play's\n  direction has the sign of the analysis "
          "row's price_vector; H1 = Jan-Jun, H2 = Jul-Dec.")
    cuts = (("price_vector", lambda r: pv_bucket(r["structure"], r["pv"]),
             ("aligned", "against", "neutral")),
            ("half", lambda r: half_of(r["date"]), ("H1", "H2")),
            ("mech direction", lambda r: r["mech"], ("BULL", "BEAR", "RANGE", "none")))
    for cname, fn, levels in cuts:
        sub(cname)
        print(f"  {'arm':<4}" + "".join(f"  {lv:>26}" for lv in levels))
        for arm in ("P",) + GRADED:
            rows = paired_of(arm_rows(results, arm, "S1"), "S1")
            cells = []
            for lv in levels:
                rs = [r for r in rows if fn(r) == lv]
                if not rs:
                    cells.append(f"  {'-':>26}")
                    continue
                a = statistics.fmean(r["a"] for r in rs)
                b = statistics.fmean(r["b"] for r in rs)
                cells.append(f"  n={len(rs):>3} {a:+.3f}/{b:+.3f}/{a - b:+.3f}")
            print(f"  {arm:<4}" + "".join(cells))


def secondary_population(label: str, results: list[RowResult]) -> None:
    sub(label)
    n = len(results)
    ok = sum(1 for r in results if r.repro_ok)
    print(f"  rows {n}   ARM P reproduced {ok} ({ok / n:.0%})" if n else "  rows 0")
    if not ok:
        return
    for arm in ARMS:
        rows = arm_rows(results, arm, None)
        if arm == "S":
            nets = [res.arms["S"].net for res in results if res.repro_ok and "S" in res.arms]
            if nets:
                print(f"  ARM S  n={len(nets):>4}  net$/pos {statistics.fmean(nets):+9,.0f}  "
                      f"(no max loss: dollars only)")
            continue
        if not rows:
            print(f"  ARM {arm}  n=   0")
            continue
        pr = paired_of(rows)
        d = statistics.fmean(r["a"] - r["b"] for r in pr) if pr else float("nan")
        print(f"  ARM {arm}  n={len(rows):>4} dates={len({r['date'] for r in rows}):>3}  "
              f"meanR {statistics.fmean(r['R'] for r in rows):+.3f}  "
              f"dR vs P {_f(d)}  net$/pos {statistics.fmean(r['net'] for r in rows):+9,.0f}")


def write_csv(path: Path, populations: list[tuple[str, list[RowResult]]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["population", "date", "ticker", "structure", "source", "arm", "sample",
            "status", "entry_day", "spot", "legs", "entry_net", "sign", "capital",
            "contracts", "exit_reason", "days_held", "gross", "cost", "net", "R",
            "R_P", "dR", "mfe", "mae", "price_vector", "pv_bucket", "half",
            "mech_direction", "repro_ok", "repro_why", "stored_net"]
    n = 0
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for pop, results in populations:
            for res in results:
                rec = res.rec
                pP = res.arms.get("P")
                for arm in ARMS:
                    pr = res.arms.get(arm)
                    row = dict(
                        population=pop, date=rec["date"], ticker=rec["ticker"],
                        structure=rec["structure"], source=rec["source"], arm=arm,
                        sample=pr.sample if pr else "",
                        status="priced" if pr else res.why.get(arm, ""),
                        entry_day=res.entry_day.isoformat() if res.entry_day else "",
                        price_vector=_r(rec.get("_pv")),
                        pv_bucket=pv_bucket(rec["structure"], rec.get("_pv")),
                        half=half_of(rec["date"]),
                        mech_direction=rec.get("mech_direction") or "",
                        repro_ok=res.repro_ok, repro_why=res.repro_why,
                        stored_net=_r(res.stored_net, 2))
                    if pr:
                        row.update(
                            spot=_r(pr.spot), legs=leg_str(pr.legs).replace("\n", " | "),
                            entry_net=_r(pr.entry_net), sign=pr.sign,
                            capital=_r(pr.capital), contracts=pr.contracts,
                            exit_reason=pr.exit_reason, days_held=pr.days_held,
                            gross=_r(pr.gross, 2), cost=_r(pr.cost, 2), net=_r(pr.net, 2),
                            R=_r(pr.R), R_P=_r(pP.R if pP else None),
                            dR=_r(pr.R - pP.R if (pP and pr.R is not None and pP.R is not None)
                                  else None),
                            mfe=_r(pr.mfe), mae=_r(pr.mae))
                    w.writerow(row)
                    n += 1
    return n


def _r(x, nd=4):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return round(x, nd)


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def population(recs: list[dict], source: str) -> list[dict]:
    return [r for r in recs if r["source"] == source and r["date"][:4] == SIGNAL_YEAR]


def attach_pv(recs: list[dict], pv_by_key: dict) -> Counter:
    """Join `price_vector` on production's identity key; census vs the loader's join."""
    from scripts.backtest.shared.identity import identity_key
    c = Counter()
    for r in recs:
        k = identity_key(r["date"], r["ticker"], r["t"].row.get("play", ""))
        pv = pv_by_key.get(k)
        r["_pv"] = pv
        c["joined" if pv is not None else "unjoined"] += 1
        if pv is not None and r.get("price_vector") is not None \
                and abs(pv - r["price_vector"]) > 1e-9:
            c["disagrees_with_loader"] += 1
    return c


def run_population(recs: list[dict], views: list[CacheView], sim_cfg: dict) -> list[RowResult]:
    return [run_row(rec, views, sim_cfg) for rec in recs]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-secondary", action="store_true",
                    help="skip the tweak and v3 descriptive populations (debugging only)")
    a = ap.parse_args(argv)
    assert SPLIT_LOCAL.timestamp() == SPLIT_EPOCH, "split epoch drifted from its local instant"

    recs, diag = load_book()
    era = diag["era"]
    print("structure_sweep — would another structure on the same 2026 plays have done better?")
    print(f"  era           {era}")
    print(f"  registration  {REGISTRATION} (accepted by default {ACCEPTED})")
    print(f"  seed          {SEED}   bootstrap draws {BOOT_N:,}")
    print(f"  split instant {SPLIT_LOCAL.isoformat()}  (epoch {SPLIT_EPOCH:.0f}); "
          f"S1 reads files with mtime <= it")
    print(f"  {era_mod.seal_line(diag['seal'])}")
    print(f"  {BR.__name__.split('.')[-1]} pricing, index_vrp strike rules, "
          f"financed_spread sizing, frozen harness exits")

    sim_cfg = load_sim_cfg()
    comm, slip = SIM._cost_knobs(sim_cfg)
    print(f"  costs         commission ${comm:.2f}/contract/leg/side, slippage {slip:g} "
          f"(config/backtest.yml)")
    # Reconcile production's merge with the registration's named profiles on a
    # date no regime cell touches: a drift here means the config moved.
    probe = date(2026, 1, 2)
    dprof, _ = exit_profile(sim_cfg, 1.0, probe, "bull_call_spread")
    cprof, _ = exit_profile(sim_cfg, -1.0, probe, "bull_put_spread")
    d_ok = all(dprof.get(k) == v for k, v in DEBIT_PROD.items())
    c_ok = all(cprof.get(k) == v for k, v in CREDIT_PROD.items())
    print(f"  exit profiles production merge == DEBIT_PROD: {d_ok}   == CREDIT_PROD: {c_ok}"
          f"   (BEAR_HE dates add the regime trail)")

    index = build_index()
    n_files = sum(len(v) for v in index.values())
    s1 = CacheView(SPLIT_EPOCH, index, "S1")
    s2 = CacheView(None, index, "S2")
    newer = sum(1 for v in index.values() for p in v.values() if not s1.admits_path(p))
    print(f"  cache         {n_files:,} contract files indexed at "
          f"{datetime.now().astimezone().isoformat(timespec='seconds')}; "
          f"{newer:,} newer than the split (S2 only)")

    era_paths = era_mod.resolve_paths(era_mod.requested_era())
    pv_by_key = analysis_price_vectors(era_paths["analysis"])

    real = population(recs, "real")
    tweak = population(recs, "tweak")
    pvc = attach_pv(real + tweak, pv_by_key)
    print(f"  population    {len(real)} real rows on {len({r['date'] for r in real})} "
          f"signal dates in {SIGNAL_YEAR} (tweak {len(tweak)} secondary)")
    print(f"  price_vector  identity_key join: {dict(pvc)}")
    sys.stdout.flush()

    results = run_population(real, [s1, s2], sim_cfg)

    # ── G-REPRO ─────────────────────────────────────────────────────────────
    hdr("G-REPRO — does this pricing path reproduce the stored rows?")
    print(f"  ARM P re-prices the stored legs; |net - realized_pnl_abs| <= ${REPRO_TOL:.2f} "
          f"after this path's\n  own commission. A failing row is dropped from every arm.")
    fails = [r for r in results if not r.repro_ok]
    rate = len(fails) / len(results) if results else 1.0
    pc = Counter(r.arms["P"].sample for r in results if "P" in r.arms)
    print(f"\n  rows {len(results)}   ARM P priced S1 {pc['S1']} / S2 {pc['S2']}   "
          f"reproduced {len(results) - len(fails)}   failed {len(fails)} ({rate:.1%})")
    print("  failures by reason: " + "  ".join(
        f"{k}={v}" for k, v in Counter(r.repro_why for r in fails).most_common()))
    for r in sorted(fails, key=lambda x: (x.rec["date"], x.rec["ticker"])):
        p = r.arms.get("P")
        ef = r.rec["t"].row.get("exit_fill") or ""
        print(f"    {r.rec['date']} {r.rec['ticker']:<5} {r.rec['structure']:<17} "
              f"stored {_f(r.stored_net, '+10,.2f')}  got "
              f"{_f(p.net if p else None, '+10,.2f')}  "
              f"stored exit {r.rec['exit_reason']}/{r.rec['days_held']} got "
              f"{(p.exit_reason + '/' + str(p.days_held)) if p else '-'}  "
              f"{r.repro_why}{'  exit_fill=' + ef if ef and ef != 'same_day' else ''}")
    if rate > REPRO_MAX_FAIL:
        n_csv = write_csv(OUT_CSV, [("primary", results)])
        print(f"\n  wrote {n_csv} rows to {OUT_CSV.relative_to(ROOT)}")
        print(f"\nG-REPRO REFUSED: {rate:.1%} of rows fail ARM P's reproduction "
              f"(> {REPRO_MAX_FAIL:.0%}). The pricing path is not production's.")
        return EXIT_REPRO
    print(f"  -> G-REPRO passes ({rate:.1%} <= {REPRO_MAX_FAIL:.0%})")

    hdr("COVERAGE — per arm, per sample (reproduced rows only)")
    kept = [r for r in results if r.repro_ok]
    print_coverage(kept, f"primary: {len(kept)} reproduced real rows")

    # ── S1 per arm ──────────────────────────────────────────────────────────
    hdr("S1 — per arm, absolute and paired against ARM P (primary)")
    print("  R = net P&L / capital at risk (debit paid, or a credit's structural max loss), "
          "net of\n  commission. CIs are date-clustered, 10,000 draws, seed 20261022. "
          "p is two-sided from\n  the paired draws. MFE/MAE on the same capital basis, "
          "gross, over the held days.")
    s1_rows = {arm: arm_rows(results, arm, "S1") for arm in ARMS}
    stats: dict[str, dict] = {}
    for arm in ("P",) + GRADED:
        rows = s1_rows[arm]
        st: dict = dict(n=len(rows), dates=len({r["date"] for r in rows}))
        if rows:
            st["mean"] = statistics.fmean(r["R"] for r in rows)
            st["lo"], st["hi"] = P.boot_ci_by_date(rows, "R", n=BOOT_N, seed=SEED)
            st["net_mean"] = statistics.fmean(r["net"] for r in rows)
            st["net_total"] = sum(r["net"] for r in rows)
            st["mfe"] = mfe_line(rows)
            st["exits"] = Counter(r["exit_reason"] for r in rows)
            st["wild"] = sum(1 for r in rows if abs(r["R"]) > 2)
            st["median"] = statistics.median(r["R"] for r in rows)
        st["thin"] = arm != "P" and (st["n"] < THIN_ROWS or st["dates"] < THIN_DATES)
        st["paired"] = paired_test(paired_of(rows, "S1")) if arm != "P" else None
        stats[arm] = st

    holm_in = {a: stats[a]["paired"]["p"] for a in GRADED
               if not stats[a]["thin"] and stats[a]["paired"]["n"]}
    adj = holm(holm_in) if holm_in else {}
    for arm in ("P",) + GRADED:
        st = stats[arm]
        sub(f"ARM {arm} — {ARM_NAME[arm]}" + ("  [THIN]" if st["thin"] else ""))
        if not st["n"]:
            print("  no S1 rows")
            continue
        print(f"  S1 n={st['n']:>4} dates={st['dates']:>3}  mean R {st['mean']:+.3f}  "
              f"CI95 [{st['lo']:+.3f}, {st['hi']:+.3f}]  net$/pos {st['net_mean']:+,.0f}  "
              f"total {st['net_total']:+,.0f}")
        print(f"  median R {st['median']:+.3f}   {st['mfe']}   |R|>2: {st['wild']}")
        print("  exits: " + "  ".join(f"{k}={v}" for k, v in st["exits"].most_common()))
        if arm != "P":
            pt = st["paired"]
            hp = adj.get(arm, (None,))[0]
            print(f"  paired vs ARM P  n={pt['n']:>4} dates={pt['dates']:>3}  "
                  f"dR {_f(pt['mean'])}  CI95 [{_f(pt['lo'])}, {_f(pt['hi'])}]  "
                  f"p {_f(pt['p'], '.4f')}  Holm p "
                  f"{_f(hp, '.4f') if hp is not None else 'not in family'}  "
                  f"median dR {_f(pt.get('median'))}")

    # ── S2 ──────────────────────────────────────────────────────────────────
    hdr("S2 — replication on rows each arm could not price in S1")
    print(f"  Priced on the whole cache as it stands now. Fewer than {S2_MIN_ROWS} rows "
          f"cannot replicate:\n  that arm stays S1-ONLY at best.")
    s2_stats: dict[str, dict] = {}
    for arm in GRADED:
        rows = arm_rows(results, arm, "S2")
        pt = paired_test(paired_of(rows))
        s2_stats[arm] = pt
        thin_note = "  (S2 too thin to replicate)" if pt["n"] < S2_MIN_ROWS else ""
        mean_r = statistics.fmean(r["R"] for r in rows) if rows else None
        print(f"  ARM {arm}  n={pt['n']:>4} dates={pt['dates']:>3}  meanR {_f(mean_r)}  "
              f"dR {_f(pt['mean'])}  CI95 [{_f(pt['lo'])}, {_f(pt['hi'])}]{thin_note}")

    # ── PBO ─────────────────────────────────────────────────────────────────
    hdr("PBO — CSCV on the S1 date x arm matrix of mean R, ARM P included")
    pbo_arms = ("P",) + GRADED
    M, dates = pbo_matrix(s1_rows, pbo_arms)
    pbo_val = None
    if len(dates) >= PBO_S:
        Mp, padded = PBO.pad_head(M, PBO_S)
        res_pbo = PBO.cscv(Mp, S=PBO_S, metric=PBO.ratio_metric)
        pbo_val = res_pbo.pbo
        share = res_pbo.selection_share()
        print(f"  T={len(dates)} dates (+{padded} empty head rows), N={len(pbo_arms)} arms, "
              f"S={PBO_S}, {res_pbo.n_combinations:,} combinations")
        print(f"  PBO {pbo_val:.3f}   (lambda = 0 in {res_pbo.n_at_zero})   degradation "
              f"slope {_f(res_pbo.slope)}   P(OOS < 0) {_f(res_pbo.prob_loss, '.3f')}")
        print("  IS-best share: " + "  ".join(
            f"{a} {s:.2f}" for a, s in zip(pbo_arms, share)))
    else:
        print(f"  only {len(dates)} S1 dates: CSCV needs at least {PBO_S}; PBO not computed")

    # ── descriptive ─────────────────────────────────────────────────────────
    descriptive_cuts(results, "primary")
    credit_wing_cut(results)
    top_abs_r(results)
    hdr("ARM S — short strangle, no defined max loss: dollars only, never graded")
    srows = [res.arms["S"] for res in kept if "S" in res.arms]
    if srows:
        nets = [p.net for p in srows]
        pnet = [res.arms["P"].net for res in kept if "S" in res.arms]
        print(f"  n={len(srows)}  net$/pos {statistics.fmean(nets):+,.0f}  total "
              f"{sum(nets):+,.0f}  (ARM P on the same rows {sum(pnet):+,.0f})  worst "
              f"{min(nets):+,.0f}  samples {dict(Counter(p.sample for p in srows))}")
        print("  exits: " + "  ".join(
            f"{k}={v}" for k, v in Counter(p.exit_reason for p in srows).most_common()))
        ranked = sorted((res for res in kept if "S" in res.arms),
                        key=lambda res: res.arms["S"].net)
        for label, picks in (("worst", ranked[:3]), ("best", ranked[::-1][:3])):
            for res in picks:
                p = res.arms["S"]
                line = dict(date=res.rec["date"], ticker=res.rec["ticker"],
                            spot=res.spot.get(p.sample), legs=p.legs,
                            entry_net=p.entry_net, contracts=p.contracts)
                print(f"  {label:<5} net ${p.net:+10,.0f}  {p.exit_reason:<13} {_row_line(line)}")
    else:
        print("  no ARM S rows priced")

    hdr("SECONDARY POPULATIONS — never graded")
    secondary: list[tuple[str, list[RowResult]]] = []
    if a.no_secondary:
        print("  skipped (--no-secondary)")
    else:
        tw = run_population(tweak, [s1, s2], sim_cfg)
        secondary.append(("tweak", tw))
        secondary_population(f"tweak rows, {SIGNAL_YEAR} ({len(tw)})", tw)
        try:
            v3_recs, v3_diag = load_book(era="v3")
            v3 = population(v3_recs, "real")
            attach_pv(v3, analysis_price_vectors(era_mod.resolve_paths("v3")["analysis"]))
            v3r = run_population(v3, [s1, s2], sim_cfg)
            secondary.append(("v3", v3r))
            secondary_population(f"v3 real rows, {SIGNAL_YEAR} ({len(v3r)}; "
                                 f"era {v3_diag['era']})", v3r)
        except SystemExit as e:
            print(f"\n  v3: load_book refused (exit {e.code}); no v3 cut on this run")
        except Exception as e:  # a descriptive cut never fails the study
            print(f"\n  v3: could not be built ({type(e).__name__}: {e})")

    n_csv = write_csv(OUT_CSV, [("primary", results)] + secondary)
    print(f"\n  wrote {n_csv} rows (row x arm) to {OUT_CSV.relative_to(ROOT)}")

    # ── verdict ─────────────────────────────────────────────────────────────
    tokens = {}
    for arm in GRADED:
        hp = adj.get(arm, (None,))[0]
        tokens[arm] = arm_token(stats[arm]["thin"], stats[arm]["paired"], hp,
                                s2_stats[arm], pbo_val)
    token = study_token(tokens)
    hdr("VERDICT")
    for arm in GRADED:
        st, pt, s2t = stats[arm], stats[arm]["paired"], s2_stats[arm]
        hp = adj.get(arm, (None,))[0]
        print(f"  ARM {arm} {ARM_NAME[arm]:<22} S1 n={pt['n']:>3}/{pt['dates']:>2}d  "
              f"dR {_f(pt['mean'])} [{_f(pt['lo'])}, {_f(pt['hi'])}]  Holm p "
              f"{_f(hp, '.3f') if hp is not None else '  -  '}  S2 n={s2t['n']:>3}  "
              f"-> {tokens[arm]}")
    print(f"  PBO {_f(pbo_val, '.3f')} (threshold < {PBO_MAX})   Holm family "
          f"{len(holm_in)} arm(s), alpha {ALPHA}")
    print(f">>> structure_sweep {token} <<<")
    print("  Nothing ships whatever this prints; a CANDIDATE earns a forward registration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
