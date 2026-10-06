"""narrow_to_fit — does narrowing an unaffordable spread beat refusing it?

Registration: `research/pre-registrations/f4_deployment/narrow_to_fit.md`
(2026-10-01). That file is the spec; this module implements it and adds
nothing to its bar. RESEARCH TIER: nothing ships from this study.

SEVEN CELLS, every one under `account_sim` ARM R, each one (floor rule,
sizing budget, dollar stop):

    (R, F3, $1,000)  narrow  $1,000  $1,000   HEADLINE (needs the scrape)
    (R, F1, $1,000)  take    $1,000  $1,000   the operator's stop-basis rule
    (R, F2, $1,000)  refuse  $1,000  $1,000   comparator at the headline budget
    (R, F3, $500)    narrow  $500    $500     secondary (needs the scrape)
    (R, F1, $500)    take    $500    $500     the registered account_sim headline
    (R, F2, $500)    refuse  $500    $500     the post-hoc result in question
    F4               take    $500    $1,000   the stop effect alone

The cells run IN PROCESS on `account_sim.simulate`, with `Settings` copied
by `dataclasses.replace` rather than a copied config file, so no account_sim
artifact is written or overwritten. The floor rule is `Cfg.floor`; F3 passes
a `narrower` (`Narrower` below) into `simulate()`.

F3, Definitions §Narrow-to-fit steps 1-7 (`Narrower.__call__`):

  1. keep ticker, expiry, right and the ANCHOR leg — the bought leg of a debit
     vertical, the sold leg of a credit vertical (operator ruling 2);
  2. walk the OTHER leg inward one strike at a time from the proposed strike;
  3. take the widest strike whose one-contract max loss, priced from the
     entry-day fill (`simulate.entry_day_fill` / `carried_entry_fill` under
     `open_print_allowed`, IMPORTED), is at or under the budget;
  4. size it with `account_sim.risk_contracts` (inside `simulate`);
  5. `narrow_no_fit` when no listed strike between the legs fits;
  6. `narrow_tier_break` when the narrowed legs change the pick's tier under
     `mapping.ladder_tier()` (IMPORTED);
  7. `narrow_unpriced` when the substitute has no usable price on the entry
     day, or its history stops before the original row's data end.

The narrowed path is built by PRODUCTION's own engine,
`scripts/backtest/simulate._simulate`, over the cached histories loaded the
way `fetch_option_histories` loads them. Junk quotes, the debit-to-credit
refusal and the entry window are therefore production's, imported rather
than mirrored; GN3 proves the builder reproduces stored rows.

A STRIKE WE CANNOT SEE. The strike grid is inferred (`strike_grid`): the
cached strikes plus every multiple of the finer of the cached spacing and the
standard listing step. A grid strike between the proposed strike and the
chosen one that is NOT cached, and that the skip-list holds no evidence
against, could be listed and could fit. The choice is then not proven
widest-that-fits and the pick is `narrow_unpriced` (reason `unproven`), never
silently skipped. The skip-list counts as evidence only for entries that
passed the evidence gate; `seeded_from_log` entries are ignored.

The same module owns the scrape census (`substitute_targets`), which
`scripts/collector/fetch_substitute_legs.py` imports. Its Black-Scholes
target estimate chooses WHAT TO FETCH and never prices anything.

Usage:
  python3 -m scripts.backtest_study run narrow_to_fit
  python3 -m scripts.backtest_study.f4_deployment.narrow_to_fit
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import math
import re
import statistics
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lib.barchart.options import (  # noqa: E402
    cache_path, parse_history_details, parse_history_series,
)
from lib.parsing import to_float  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _contract_key, _max_loss_per_unit  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest.proxy import _infer_strike_step, _strike_step  # noqa: E402
from scripts.backtest.shared import unlisted as UL  # noqa: E402
from scripts.backtest.simulate import (  # noqa: E402
    _is_junk_quote, _real_greek, _refuse_credit_priced_to_debit,
    _refuse_debit_priced_to_credit, _simulate, _snap_asof, carried_entry_fill,
    entry_day_fill, fresh_entry_date, last_good_mark, open_print_allowed,
)
from scripts.backtest_study.f3_structure.bear_rewrap import recorded_entry_date  # noqa: E402
from scripts.backtest_study.f4_deployment import account_sim as AS  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import path_bootstrap as PB  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import replay_basis as RB  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.lib.harness import MAX_LOSS_ABS, Trade  # noqa: E402
from scripts.backtest_study.lib.sleeve_synth import _strike_index  # noqa: E402
from scripts.journal.lib.mapping import ladder_tier as mapping_ladder_tier  # noqa: E402

# Era refusals from `load_book` (exit 2 thin era, exit 3 wrong era) are the
# study's correct status, not failures.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

hdr, sub = AS.hdr, AS.sub

# ── registered constants ─────────────────────────────────────────────────────

#: The operator's dollar stop, which is also the frozen harness's own
#: `MAX_LOSS_ABS`. The other budget is `account_sim`'s registered 2% of capital,
#: read from config/account-sim.yml at run time.
HIGH_BUDGET = 1000.0
#: The registered headline cap cell (per-position, net) and the tracked
#: robustness cell (registration, "Cap cells"). Constants, not the config's
#: `caps.net`: the config holds whichever cell account_sim's default run uses,
#: and a verdict here must hold on both registered cells whatever that is.
HEAD_NET_CAP = 1.50
ROBUST_NET_CAP = 2.50
PER_POS_CAP = 0.25
#: GN0 POWER — the narrowed subset needs this many dates AND positions.
GN0_MIN_DATES = 25
GN0_MIN_POSITIONS = 60
#: GN5 COVERAGE — the share of over-budget picks allowed to end `narrow_unpriced`.
GN5_MAX_UNPRICED = 0.10
#: N2 — block length and bar of the deflated drawdown.
N2_BLOCK = 10
N2_BAR = 0.25
#: N3 — the reference windows are `(R, F1, $500)` drawdowns at least this deep.
N3_WINDOW_DEPTH = 0.10
#: N5 — a calendar year is graded when it holds at least this many narrowed picks.
N5_MIN_YEAR_N = 10
#: The entry timing every v4 row was priced under (config/backtest.yml).
ENTRY_TIMING = "next_open"

BACKTEST_CONFIG = ROOT / "config" / "backtest.yml"
UNLISTED_PATH = HISTORY_CACHE / UL.FILENAME
SEEDED_PREFIX = "seeded_from_log"

#: `(key, label, budget-kind, dollar stop, floor rule, role)`. `budget-kind`
#: "low" is the config's 2% budget, "high" is `HIGH_BUDGET`.
CELLS = (
    ("F3_HI", "(R, F3, $1,000)", "high", None, "narrow", "HEADLINE"),
    ("F1_HI", "(R, F1, $1,000)", "high", None, "take", "cell"),
    ("F2_HI", "(R, F2, $1,000)", "high", None, "refuse", "control"),
    ("F3_LO", "(R, F3, $500)", "low", None, "narrow", "secondary"),
    ("F1_LO", "(R, F1, $500)", "low", None, "take", "control"),
    ("F2_LO", "(R, F2, $500)", "low", None, "refuse", "control"),
    ("F4", "F4 ($500 budget, $1,000 stop)", "low", HIGH_BUDGET, "take", "cell"),
)
CELL_LABEL = {k: lab for k, lab, *_ in CELLS}

log = logging.getLogger("narrow_to_fit")


# ════════════════════════════════════════════════════════════════════════════
# Legs, roles and the strike grid
# ════════════════════════════════════════════════════════════════════════════

def vertical_roles(legs: list[Leg], credit: bool) -> tuple[int, int] | None:
    """`(anchor_index, mover_index)` for a two-leg vertical, else None.

    The ANCHOR is the leg the tier rule keys on and never moves: the bought leg
    of a debit vertical, the sold leg of a credit vertical (operator ruling 2,
    2026-10-01). The MOVER is the other leg; narrowing walks it toward the
    anchor.
    """
    if not legs or len(legs) != 2:
        return None
    a, b = legs
    if (a.ticker, a.expiration, a.opt_type) != (b.ticker, b.expiration, b.opt_type):
        return None
    if a.qty * b.qty >= 0 or abs(a.qty) != abs(b.qty) or a.strike == b.strike:
        return None
    sold = 0 if a.qty < 0 else 1
    bought = 1 - sold
    return (sold, bought) if credit else (bought, sold)


def strike_grid(cached: list[float], spot: float | None, lo: float,
                hi: float) -> list[float]:
    """Every strike that MIGHT be listed strictly between `lo` and `hi`.

    The cached strikes, plus every multiple of the grid step: the finer of the
    cached strikes' spacing (`proxy._infer_strike_step`) and the standard
    listing step at this price (`proxy._strike_step`, keyed on the spot, else
    the mid strike). An estimate — some of these strikes are not listed — used
    to decide what to fetch and what the walk cannot yet see.
    """
    ref = spot if spot and spot > 0 else (lo + hi) / 2
    step = _strike_step(ref)
    inferred = _infer_strike_step(cached) if cached else None
    if inferred and inferred < step:
        step = inferred
    out = {round(k, 4) for k in cached if lo + 1e-9 < k < hi - 1e-9}
    n = math.floor(lo / step) + 1
    while n * step < hi - 1e-9:
        k = round(n * step, 4)
        if k > lo + 1e-9:
            out.add(k)
        n += 1
    return sorted(out)


def inward(anchor: Leg, mover: Leg, grid: list[float]) -> list[float]:
    """Grid strikes between the legs, ordered from the mover's side inward."""
    lo, hi = sorted((anchor.strike, mover.strike))
    between = [k for k in grid if lo < k < hi]
    return between if mover.strike < anchor.strike else between[::-1]


def contract_stem(ticker: str, expiry: date, strike: float, opt_type: str) -> str:
    return cache_path(Path("."), ticker, expiry, strike, opt_type).stem


def unlisted_evidence(path: Path = UNLISTED_PATH) -> set[str]:
    """Contract stems the skip-list records as unlisted ON EVIDENCE.

    `seeded_from_log` entries never passed the evidence gate (registration,
    "A listed strike ..."), so they are excluded: they are not evidence that a
    strike is unlisted, and a strike they name stays fetchable and unproven.
    """
    return {k for k, e in UL.load(path).items()
            if not str(e.get("reason", "")).startswith(SEEDED_PREFIX)}


# ════════════════════════════════════════════════════════════════════════════
# Cached histories, loaded the way production loads them
# ════════════════════════════════════════════════════════════════════════════

class Chain:
    """The option-history cache as `fetch_option_histories` loads it:
    `parse_history_series` for the marks and `parse_history_details` (rows with
    a mark) for the quotes — exactly the two maps `_simulate` is handed.

    `cutoff` (GN4) truncates the named contracts' histories after a date, so
    the strike choice can be re-run blind to everything after its entry day.
    """

    def __init__(self, idx: dict | None = None, cutoff: dict | None = None,
                 parent: "Chain | None" = None):
        self.idx = idx if idx is not None else (parent.idx if parent else _strike_index())
        self.cutoff = cutoff or {}
        self._memo = parent._memo if parent is not None else {}

    def cached(self, ticker: str, expiry: date, strike: float, opt_type: str) -> bool:
        cp = "C" if opt_type == "Call" else "P"
        return cp in self.idx.get((ticker, expiry), {}).get(round(strike, 4), set()) \
            or cp in self.idx.get((ticker, expiry), {}).get(float(strike), set())

    def strikes(self, ticker: str, expiry: date) -> list[float]:
        return sorted(self.idx.get((ticker, expiry), {}))

    def _load(self, leg: Leg) -> tuple[list, dict]:
        key = (leg.ticker, leg.expiration, round(leg.strike, 4), leg.opt_type)
        if key not in self._memo:
            p = cache_path(HISTORY_CACHE, leg.ticker, leg.expiration, leg.strike,
                           leg.opt_type)
            if not p.exists():
                self._memo[key] = ([], {})
            else:
                text = p.read_text(encoding="utf-8")
                self._memo[key] = (parse_history_series(text),
                                   parse_history_details(text))
        return self._memo[key]

    def history(self, leg: Leg) -> tuple[list, dict]:
        """`(series, details)` for one contract, cut at `cutoff` if named."""
        series, details = self._load(leg)
        cut = self.cutoff.get((leg.ticker, leg.expiration, round(leg.strike, 4),
                               leg.opt_type))
        if cut is None:
            return series, details
        return ([(d, m) for d, m in series if d <= cut],
                {d: r for d, r in details.items() if d <= cut})

    def maps(self, legs: list[Leg]) -> tuple[dict, dict]:
        """`(barchart_series, barchart_details)` keyed as production keys them."""
        s_map, d_map = {}, {}
        for leg in legs:
            k = _contract_key(leg.ticker, leg.opt_type, leg.strike,
                              leg.expiration.isoformat())
            s_map[k], d_map[k] = self.history(leg)
        return s_map, d_map


def entry_fill(chain: Chain, leg: Leg, entry_day: date,
               signal_date: date) -> tuple[float | None, str]:
    """One leg's ENTRY fill on the recorded entry day, production's choice.

    `(price, tag)`; price None means no usable fill (tag says why). The order
    is `_simulate._entry_price_leg` then `_price_leg(entry_qty=...)`: the entry
    day's own row through `entry_day_fill` when `open_print_allowed`, else the
    newest snap on or before the day through `carried_entry_fill`. Both are
    IMPORTED. A leg whose first real quote after the signal lands after the
    entry day, or whose quotes all precede the signal, is not filled on that
    day — production would move or refuse the entry (`fresh_entry_date`).
    """
    series, details = chain.history(leg)
    if not series and not details:
        return None, "no_history"
    quote_days = [d for d in set(d for d, _ in series) | set(details)
                  if d <= leg.expiration]
    day, stale = fresh_entry_date([quote_days], signal_date, entry_day)
    if stale is not None:
        return None, "stale_leg_at_entry"
    if day != entry_day:
        return None, "first_quote_after_entry"
    if open_print_allowed(entry_day, signal_date, ENTRY_TIMING):
        row = details.get(entry_day)
        if row is not None:
            fill = entry_day_fill(row, leg.qty, open_print=True)
            if fill is not None:
                return (fill[0], fill[1]) if fill[0] is not None else (None, fill[1])
    key = ("k",)
    p, snap = _snap_asof({key: series}, key, entry_day, leg.expiration)
    if p is None:
        return None, "no_price"
    row = details.get(snap)
    if snap != entry_day and entry_day <= leg.expiration:
        today = details.get(entry_day)
        if today is not None and _is_junk_quote(today):
            row = today
    fp, tag = carried_entry_fill(row, p, leg.qty)
    return (fp, tag) if fp is not None else (None, tag)


def max_loss_of(legs: list[Leg], net: float) -> float | None:
    """One contract's max loss in dollars, production's rounding."""
    mlpu = _max_loss_per_unit(legs, net)
    return round(mlpu * 100, 2) if mlpu is not None else None


def entry_greek_row(chain: Chain, leg: Leg, entry_day: date) -> dict | None:
    """The row a leg's entry greeks are read from: its own row on the entry
    day, else the row its carried entry mark came from (`_leg_greek_row`)."""
    series, details = chain.history(leg)
    if entry_day in details:
        return details[entry_day]
    key = ("k",)
    _, snap = _snap_asof({key: series}, key, entry_day, leg.expiration)
    return details.get(snap) if snap is not None else None


# ════════════════════════════════════════════════════════════════════════════
# The strike choice (steps 2, 3, 5) — reads the entry day and nothing later
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass(frozen=True)
class Choice:
    """The outcome of one walk. `reason`: fit | no_fit | unproven | unpriced."""
    reason: str
    strike: float | None = None
    net: float | None = None
    max_loss: float | None = None
    detail: str = ""
    steps: int = 0


def choose_strike(rec: dict, budget: float, chain: Chain, evidence: set[str],
                  roles: tuple[int, int], entry_day: date) -> Choice:
    """Walk the mover inward from the proposed strike; widest that fits wins.

    Every grid strike is visited in order, nothing is skipped on a guess:

      * on the skip-list ON EVIDENCE        -> not listed, step on;
      * not cached, no evidence             -> `unproven`: it could be listed
                                               and could fit, so the walk stops;
      * cached, no fill on the entry day    -> not listed on that day, step on;
      * cached, filled, refused by production's polarity rules
                                            -> `unpriced`: a listed strike with
                                               no usable price, the walk stops;
      * cached, filled, max loss <= budget  -> `fit`;
      * otherwise                           -> step on.

    Exhausting the grid is `no_fit`.
    """
    t: Trade = rec["t"]
    legs = list(t.legs)
    ai, mi = roles
    anchor, mover = legs[ai], legs[mi]
    a_px, a_tag = entry_fill(chain, anchor, entry_day, t.signal_date)
    if a_px is None:
        return Choice("unpriced", detail=f"anchor leg not filled ({a_tag})")
    spot = to_float(t.row.get("entry_underlying"))
    grid = strike_grid(chain.strikes(anchor.ticker, anchor.expiration), spot,
                       *sorted((anchor.strike, mover.strike)))
    steps = 0
    for k in inward(anchor, mover, grid):
        steps += 1
        sub = mover._replace(strike=k)
        stem = contract_stem(sub.ticker, sub.expiration, k, sub.opt_type)
        if stem in evidence:
            continue
        if not chain.cached(sub.ticker, sub.expiration, k, sub.opt_type):
            return Choice("unproven", detail=f"{stem} not cached", steps=steps)
        px, tag = entry_fill(chain, sub, entry_day, t.signal_date)
        if px is None:
            if tag in ("junk_entry_quote",):
                return Choice("unpriced", detail=f"{stem} {tag}", steps=steps)
            continue
        new = list(legs)
        new[mi] = sub
        net = a_px * anchor.qty + px * sub.qty
        if (abs(net) <= 1e-9
                or _refuse_debit_priced_to_credit(t.structure, net)
                or _refuse_credit_priced_to_debit(t.structure, net)):
            return Choice("unpriced", detail=f"{stem} entry net {net:+.4f} refused",
                          steps=steps)
        ml = max_loss_of(new, net)
        if ml is None or ml <= 0:
            return Choice("unpriced", detail=f"{stem} max loss unbounded", steps=steps)
        if ml <= budget + AS.EPS:
            return Choice("fit", strike=k, net=net, max_loss=ml, steps=steps)
    return Choice("no_fit", steps=steps)


# ════════════════════════════════════════════════════════════════════════════
# The builder — production's engine on the cached histories (GN3)
# ════════════════════════════════════════════════════════════════════════════

def _sim_cfg() -> dict:
    import yaml
    return yaml.safe_load(BACKTEST_CONFIG.read_text())["simulation"]


def build_position(rec: dict, legs: list[Leg], chain: Chain, sim_cfg: dict,
                   entry_day: date) -> tuple[dict | None, dict]:
    """`(result_row, refusal)` — `_simulate` on `legs` at the pick's RECORDED
    entry day and DTE, the call `plays.Play._simulate` makes. `result_row` is
    None when production refuses or cannot price; `refusal` then names why.
    """
    t: Trade = rec["t"]
    s_map, d_map = chain.maps(legs)
    anchor_row = d_map.get(_contract_key(legs[0].ticker, legs[0].opt_type,
                                         legs[0].strike,
                                         legs[0].expiration.isoformat()), {})
    iv_row = anchor_row.get(entry_day) or {}
    entry_row = {"DTE": t.dte_entry, "IV": iv_row.get("IV"), "_entry_date": entry_day}
    cand = {"ticker": t.ticker, "signal_date": t.signal_date,
            "play": t.row.get("play", "") or "", "regime": t.row.get("regime", "")}
    refusal: dict = {}
    res = _simulate(cand, legs, entry_row, {}, s_map, sim_cfg,
                    structure=t.structure, anchor_idx=0, barchart_details=d_map,
                    refusal=refusal)
    return (res or None), refusal


def reproduces(rec: dict, chain: Chain, sim_cfg: dict) -> tuple[bool, str]:
    """GN3 on one stored row: the builder at the row's OWN strikes must give
    its entry net and its daily marks, and the strike choice's own fill must
    give the same entry net."""
    t: Trade = rec["t"]
    day = recorded_entry_date(t)
    if day is None:
        return False, "no recorded entry day"
    res, refusal = build_position(rec, list(t.legs), chain, sim_cfg, day)
    if res is None:
        return False, f"builder refused ({refusal.get('reason', 'unpriced')})"
    want = round(float(t.row["entry_option_price"]), 4)
    if abs(float(res["entry_option_price"]) - want) > 1e-9:
        return False, f"entry net {res['entry_option_price']} vs stored {want}"
    if res["daily_price_csv"] != t.row["daily_price_csv"]:
        n = sum(1 for a, b in zip(res["daily_price_csv"].split(","),
                                  t.row["daily_price_csv"].split(",")) if a != b)
        return False, f"{n} daily marks differ"
    fill = 0.0
    for leg in t.legs:
        px, tag = entry_fill(chain, leg, day, t.signal_date)
        if px is None:
            return False, f"strike-choice fill refused a stored leg ({tag})"
        fill += leg.qty * px
    if abs(round(fill, 4) - want) > 1e-9:
        return False, f"strike-choice fill {fill:.4f} vs stored {want}"
    return True, "ok"


# ════════════════════════════════════════════════════════════════════════════
# The narrower (steps 1-7) — handed to account_sim.simulate
# ════════════════════════════════════════════════════════════════════════════

_LEG_DETAIL_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z.\-]*):(\d{4}-\d{2}-\d{2}):([\d.]+):([CP])\s+[+-]\d+.*?"
    r"delta=(-?[\d.]*)")


def stored_leg_delta(row: dict, leg: Leg) -> float | None:
    """A leg's entry delta as the stored row recorded it (`entry_leg_detail`)."""
    cp = "C" if leg.opt_type == "Call" else "P"
    for line in str(row.get("entry_leg_detail") or "").splitlines():
        m = _LEG_DETAIL_RE.match(line)
        if not m:
            continue
        if (m.group(1) == leg.ticker and m.group(2) == leg.expiration.isoformat()
                and abs(float(m.group(3)) - leg.strike) < 1e-6 and m.group(4) == cp):
            return to_float(m.group(5)) if m.group(5) else None
    return None


def _bs_delta(spot: float, strike: float, years: float, sigma: float,
              opt_type: str) -> float | None:
    """Black-Scholes delta, ONLY where the cache carries no real Delta for the
    substitute (build note "Delta-notional"). A finite difference of the
    research-tier pricer, so no second Black-Scholes body exists."""
    from scripts.backtest_study.lib.overlay_campaign import _bs_price
    if not (spot and sigma and years and spot > 0 and sigma > 0 and years > 0):
        return None
    h = spot * 1e-4
    up = _bs_price(spot + h, strike, years, 0.0, sigma, opt_type)
    dn = _bs_price(spot - h, strike, years, 0.0, sigma, opt_type)
    return (up - dn) / (2 * h)


def leg_ivs(row: dict) -> list[float]:
    """The legs' entry IVs (fractions) off `entry_leg_detail`."""
    out = []
    for line in str(row.get("entry_leg_detail") or "").splitlines():
        m = re.search(r"iv=([\d.]+)%", line)
        if m:
            out.append(float(m.group(1)) / 100)
    return out


def tier_of(rec: dict, delta: float | None) -> str:
    """`mapping.ladder_tier()` with the pick's own inputs and `delta`.

    `delta` is the POSITION's net entry delta — the quantity the book's own
    ladder port keys §3 on (`book.ladder_tier` reads the row's `delta`) — so
    at the pick's original legs this is the tier the pick was admitted under.
    """
    dte = rec.get("dte")
    tier, _partial, _why = mapping_ladder_tier(
        rec["structure"], rec.get("market_regime") or "",
        dte_proxy=float(dte) if dte is not None else float("nan"),
        short_leg_delta=delta)
    return tier


@dataclasses.dataclass
class Narrowing:
    """One pick's narrowing at one budget — the audit row behind every bucket."""
    rec: dict
    budget: float
    bucket: str | None            # None = narrowed and returned
    reason: str
    choice: Choice | None = None
    narrowed: dict | None = None
    delta_source: str = ""


class Narrower:
    """`narrower(rec, budget) -> (narrowed_rec | None, bucket | None)`.

    Memoised per (pick, budget): the narrowed record must stay alive for as
    long as `simulate`'s replay memo, which is keyed by `id()`, and the same
    pick is offered in every cell, cap cell and population at one budget.
    """

    def __init__(self, chain: Chain, evidence: set[str], sim_cfg: dict,
                 force_refuse: bool = False):
        self.chain, self.evidence, self.sim_cfg = chain, evidence, sim_cfg
        self.force_refuse = force_refuse
        self.log: dict[tuple, Narrowing] = {}

    def __call__(self, rec: dict, budget: float):
        if self.force_refuse:                       # GN1 REFUSE IDENTITY
            return None, "narrow_no_fit"
        key = (id(rec), round(budget, 6))
        if key not in self.log:
            self.log[key] = self.narrow(rec, budget)
        n = self.log[key]
        return (n.narrowed, None) if n.bucket is None else (None, n.bucket)

    def narrow(self, rec: dict, budget: float) -> Narrowing:
        t: Trade = rec["t"]
        legs = list(t.legs)
        roles = vertical_roles(legs, rec["credit"])
        if roles is None:
            return Narrowing(rec, budget, "narrow_unpriced", "not_two_leg_vertical")
        entry_day = recorded_entry_date(t)
        if entry_day is None:
            return Narrowing(rec, budget, "narrow_unpriced", "no_recorded_entry_day")
        ch = choose_strike(rec, budget, self.chain, self.evidence, roles, entry_day)
        if ch.reason == "no_fit":
            return Narrowing(rec, budget, "narrow_no_fit", "no_fit", ch)
        if ch.reason != "fit":
            return Narrowing(rec, budget, "narrow_unpriced", ch.reason, ch)

        ai, mi = roles
        new = list(legs)
        new[mi] = legs[mi]._replace(strike=ch.strike)
        # Step 6 — the tier at the narrowed legs against the tier at the
        # original legs, both through mapping.ladder_tier().
        a_delta = stored_leg_delta(t.row, legs[ai])
        g_row = entry_greek_row(self.chain, new[mi], entry_day)
        s_delta, source = _real_greek(g_row, "Delta"), "cache"
        if s_delta is None:
            ivs = leg_ivs(t.row)
            sigma = _real_greek(g_row, "IV")
            sigma = sigma / 100 if sigma else (statistics.fmean(ivs) if ivs else None)
            s_delta = _bs_delta(to_float(t.row.get("entry_underlying")), ch.strike,
                                t.dte_entry / 365.0, sigma, new[mi].opt_type)
            source = "black_scholes" if s_delta is not None else "none"
        net_delta = (None if a_delta is None or s_delta is None
                     else legs[ai].qty * a_delta + new[mi].qty * s_delta)
        if tier_of(rec, net_delta) != tier_of(rec, rec.get("delta")):
            return Narrowing(rec, budget, "narrow_tier_break", "tier_changed", ch,
                             delta_source=source)

        # Step 7 — production prices the narrowed spread over the held window.
        res, refusal = build_position(rec, new, self.chain, self.sim_cfg, entry_day)
        if res is None:
            return Narrowing(rec, budget, "narrow_unpriced",
                             f"builder_{refusal.get('reason', 'unpriced')}", ch,
                             delta_source=source)
        if int(res["dte_entry"]) != t.dte_entry:
            return Narrowing(rec, budget, "narrow_unpriced", "entry_day_moved", ch,
                             delta_source=source)
        if abs(float(res["entry_option_price"]) - round(ch.net, 4)) > 1e-9:
            # The strike choice and the builder disagree about the fill: a
            # mirror failure, never a price. Counted and refused; GN3 reports it.
            return Narrowing(rec, budget, "narrow_unpriced", "fill_mismatch", ch,
                             delta_source=source)
        need = data_end(t)
        series, details = self.chain.history(new[mi])
        last = last_good_mark(series, details, new[mi].expiration + timedelta(days=1),
                              new[mi].expiration)
        if need is not None and (last is None or last[1] < need):
            return Narrowing(rec, budget, "narrow_unpriced", "short_history", ch,
                             delta_source=source)

        row = {k: ("" if v is None else str(v)) for k, v in res.items()}
        row["contracts"] = str(res["contracts"])
        nt = RB.bounded(Trade(row))
        narrowed = {k: v for k, v in rec.items() if k not in AS.LOOKAHEAD_REC_KEYS}
        narrowed.update(
            t=nt, max_loss_per_contract=float(res["max_loss_per_contract"]),
            delta=net_delta, narrowed=True, orig=rec,
            orig_strike=legs[mi].strike, sub_strike=ch.strike,
            delta_source=source)
        return Narrowing(rec, budget, None, "narrowed", ch, narrowed,
                         delta_source=source)


def data_end(t: Trade) -> date | None:
    """The original row's data end: `path_data_end`, else its last priced day."""
    s = str(t.row.get("path_data_end") or "").strip()
    if s:
        return date.fromisoformat(s[:10])
    priced = [d for d, m in zip(t.grid, t.marks) if m is not None]
    return priced[-1] if priced else None


# ════════════════════════════════════════════════════════════════════════════
# The scrape census — imported by scripts/collector/fetch_substitute_legs.py
# ════════════════════════════════════════════════════════════════════════════

def estimated_target(rec: dict, budget: float, grid: list[float],
                     roles: tuple[int, int]) -> tuple[float | None, float | None, str]:
    """`(target, next_wider, why)` — the census's Black-Scholes ESTIMATE.

    Each grid strike is priced at the legs' mean entry IV, the entry spot and
    the recorded DTE, r = 0. The target is the widest that fits; the next-wider
    strike is its neighbour toward the proposed strike (which may be the
    proposed strike itself). FOR CHOOSING WHAT TO FETCH ONLY: the study prices
    nothing with it.
    """
    from scripts.backtest_study.lib.overlay_campaign import _bs_price
    t: Trade = rec["t"]
    legs = list(t.legs)
    ai, mi = roles
    anchor, mover = legs[ai], legs[mi]
    ivs = leg_ivs(t.row)
    sigma = statistics.fmean(ivs) if ivs else to_float(t.row.get("iv_entry_pct"))
    spot = to_float(t.row.get("entry_underlying"))
    if not sigma or not spot or sigma <= 0 or spot <= 0:
        return None, None, "no_iv_or_spot"
    years = max(t.dte_entry, 1) / 365.0
    a_px = _bs_price(spot, anchor.strike, years, 0.0, sigma, anchor.opt_type)
    order = inward(anchor, mover, grid)
    walk = [mover.strike] + order
    for i, k in enumerate(order, start=1):
        px = _bs_price(spot, k, years, 0.0, sigma, mover.opt_type)
        new = list(legs)
        new[mi] = mover._replace(strike=k)
        net = a_px * anchor.qty + px * mover.qty
        if abs(net) <= 1e-9:
            continue
        ml = max_loss_of(new, net)
        if ml is not None and 0 < ml <= budget:
            return k, walk[i - 1], "fit"
    if not order:
        return None, None, "no_strike_between"
    return order[-1], walk[-2], "no_estimated_fit"


def candidates(records: list[dict]) -> list[dict]:
    """Every ladder-eligible pick the account_sim walk can reach, full book."""
    return [r for _d, ranked in P.ordered_by_day(records, P.ladder_rank,
                                                 P.ladder_eligible)
            for r in ranked]


def substitute_targets(records: list[dict], budgets: tuple[float, ...],
                       idx: dict | None = None, evidence: set[str] | None = None,
                       scope: str = "target_wider") -> tuple[list[dict], Counter]:
    """`(targets, census)` — the contracts the F3 cells need fetched.

    Scope `target_wider` (the registration's middle row): the estimated target
    strike and the next-wider strike per over-budget pick per budget. Scope
    `between`: every grid strike between the legs. A contract already cached,
    or on the skip-list on evidence, is never a target. Each target dict is
    `{ticker, expiration, strike, opt_type ("Call"/"Put"), category}`.
    """
    chain = Chain(idx)
    evidence = unlisted_evidence() if evidence is None else evidence
    census: Counter = Counter()
    seen: dict[tuple, dict] = {}
    cands = candidates(records)
    census["candidates"] = len(cands)
    census["candidate_dates"] = len({r["date"] for r in cands})
    for b in budgets:
        tag = f"${b:,.0f}"
        for rec in cands:
            ml = rec.get("max_loss_per_contract")
            if ml is None or ml <= b:
                continue
            census[f"over {tag}"] += 1
            census[f"over {tag} {rec['structure']}"] += 1
            t: Trade = rec["t"]
            roles = vertical_roles(list(t.legs), rec["credit"])
            if roles is None:
                census[f"over {tag} not a two-leg vertical"] += 1
                continue
            anchor, mover = t.legs[roles[0]], t.legs[roles[1]]
            grid = strike_grid(chain.strikes(anchor.ticker, anchor.expiration),
                               to_float(t.row.get("entry_underlying")),
                               *sorted((anchor.strike, mover.strike)))
            if scope == "between":
                want = [(k, "between") for k in inward(anchor, mover, grid)]
            else:
                target, wider, why = estimated_target(rec, b, grid, roles)
                census[f"over {tag} estimate {why}"] += 1
                want = [(k, cat) for k, cat in ((target, "target"),
                                                (wider, "next_wider"))
                        if k is not None]
                # Strikes the target_wider scope leaves unseen between the
                # proposed strike and the next-wider one: the walk cannot prove
                # widest-that-fits past an uncached one.
                if wider is not None:
                    lo, hi = sorted((mover.strike, wider))
                    gap = [k for k in grid if lo < k < hi
                           and not chain.cached(anchor.ticker, anchor.expiration,
                                                k, mover.opt_type)
                           and contract_stem(anchor.ticker, anchor.expiration, k,
                                             mover.opt_type) not in evidence]
                    if gap:
                        census[f"over {tag} unseen strike beyond next-wider"] += 1
            for k, cat in want:
                stem = contract_stem(anchor.ticker, anchor.expiration, k,
                                     mover.opt_type)
                if chain.cached(anchor.ticker, anchor.expiration, k, mover.opt_type):
                    census[f"over {tag} {cat} cached"] += 1
                    continue
                if stem in evidence:
                    census[f"over {tag} {cat} unlisted on evidence"] += 1
                    continue
                census[f"over {tag} {cat} not cached"] += 1
                seen.setdefault(stem, dict(
                    ticker=anchor.ticker, expiration=anchor.expiration,
                    strike=float(k), opt_type=mover.opt_type,
                    category=cat))
    targets = sorted(seen.values(), key=lambda r: (r["ticker"], r["expiration"],
                                                   r["opt_type"], r["strike"]))
    census["unique uncached contracts"] = len(targets)
    return targets, census


# ════════════════════════════════════════════════════════════════════════════
# Grading helpers
# ════════════════════════════════════════════════════════════════════════════

def settings_for(st: AS.Settings, kind: str, stop: float | None) -> AS.Settings:
    budget = st.budget if kind == "low" else HIGH_BUDGET
    return dataclasses.replace(st, risk_pct=budget / st.capital, dollar_stop=stop)


def cfg_for(st_cell: AS.Settings, label: str, floor: str, net_cap: float) -> AS.Cfg:
    return st_cell.cfg(label, net_cap=net_cap, floor=floor,
                       take_floor=(floor != "refuse"), compound=False)


def stats_line(sim: AS.Sim) -> tuple:
    rs = [p.R for p in sim.signal_pos]
    _, vals = AS.equity_curve(sim.signal_pos)
    win = sum(1 for v in rs if v > 0) / len(rs) if rs else float("nan")
    return len(rs), len(sim.dates), sim.dollars, AS.fmean(rs), win, AS.max_drawdown(vals)


def feasible(s: dict) -> bool:
    """account_sim's FEASIBLE: A1, A2, A3, A5 and A6 all MET."""
    return all(s[k] for k in ("A1", "A2", "A3", "A5", "A6"))


def verdict_label(s: dict, capital: float) -> str:
    """account_sim's own outcome-to-label mapping, through `print_verdict`'s
    grammar, without printing it."""
    if not s["A1"]:
        return f"{AS.NOT_FEASIBLE_PREFIX}{capital:,.0f}"
    if feasible(s):
        return "FEASIBLE"
    if s["A3"] and not s["A2"]:
        return "FEASIBLE-BUT-DEGRADED"
    if not s["A3"]:
        return f"{AS.NOT_FEASIBLE_PREFIX}{capital:,.0f} — BLOWUP RISK (A1 holds, A3 fails)"
    return "FEASIBILITY NOT CONFIRMED"


def n2_median(sim: AS.Sim) -> float | None:
    """N2: median max drawdown (fraction of capital) over block-10 paths."""
    _, vals = AS.equity_curve(sim.signal_pos)
    if not vals:
        return None
    band = PB.bootstrap_drawdown(vals, sim.cfg.capital, N2_BLOCK, AS.BOOTSTRAP_N,
                                 AS.BOOTSTRAP_SEED)
    return band.p50


def depth_inside(sim: AS.Sim, dd: AS.Drawdown) -> float:
    """The cell's own deepest drawdown inside `(dd.peak_sess, dd.trough_sess]`,
    measured from the cell's realized equity at the window's start."""
    sessions, vals = AS.equity_curve(sim.signal_pos)
    cum = sum(v for s, v in zip(sessions, vals)
              if dd.peak_sess is not None and s <= dd.peak_sess)
    peak, worst = cum, 0.0
    for s, v in zip(sessions, vals):
        if (dd.peak_sess is not None and s <= dd.peak_sess) or s > dd.trough_sess:
            continue
        cum += v
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def n3_windows(ref: AS.Sim, capital: float) -> list[AS.Drawdown]:
    return [d for d in AS.drawdowns(ref) if abs(d.depth) >= N3_WINDOW_DEPTH * capital]


def n3_pass(sim: AS.Sim, ref: AS.Sim, capital: float) -> tuple[bool, list[str]]:
    lines, ok = [], True
    for d in n3_windows(ref, capital):
        mine = depth_inside(sim, d)
        better = abs(mine) < abs(d.depth)
        ok = ok and better
        lines.append(f"{d.peak_label}..{d.trough_sess}  ref {d.depth:,.0f}  "
                     f"cell {mine:,.0f}  {'shallower' if better else 'NOT shallower'}")
    return ok, lines


def narrowed_positions(sim: AS.Sim) -> list:
    return [p for p in sim.signal_pos if p.rec.get("narrowed")]


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

COLS = (f"  {'cell':<32}{'n':>5}{'dates':>7}{'total $':>12}{'meanR':>9}"
        f"{'win':>7}{'maxDD $':>11}")


def print_row(label: str, sim: AS.Sim) -> None:
    n, d, tot, mr, win, mdd = stats_line(sim)
    print(f"  {label:<32}{n:>5}{d:>7}{tot:>12,.0f}{mr:>9.3f}{win:>7.0%}{mdd:>11,.0f}")


def print_census(sim: AS.Sim, label: str, n_candidates: int) -> dict:
    c = sim.census
    offered = c["narrow_offered"]
    buckets = AS.CENSUS_BUCKETS + AS.NARROW_EXCLUSIONS
    total = sum(c[k] for k in buckets)
    unpriced = c["narrow_unpriced"]
    share = unpriced / offered if offered else 0.0
    print(f"  {label}: over-budget picks offered to the narrower {offered}  "
          f"narrowed {c['narrowed']}  no_fit {c['narrow_no_fit']}  "
          f"tier_break {c['narrow_tier_break']}  unpriced {unpriced} ({share:.0%})")
    print(f"    partition: {total} bucketed of {n_candidates} candidates walked -> "
          f"{'OK' if total == n_candidates else 'MISMATCH'}")
    return dict(offered=offered, unpriced=unpriced, share=share,
                partition_ok=total == n_candidates)


def print_reasons(narrower: Narrower, budget: float, recs_ids: set[int]) -> None:
    rows = [n for (rid, b), n in narrower.log.items()
            if b == round(budget, 6) and rid in recs_ids]
    by = Counter((n.bucket or "narrowed", n.reason) for n in rows)
    for (bucket, reason), k in sorted(by.items()):
        print(f"    {bucket:<20} {reason:<34} {k:>5}")
    srcs = Counter(n.delta_source for n in rows if n.bucket is None)
    if srcs:
        joined = "  ".join(f"{k}={v}" for k, v in sorted(srcs.items()))
        print(f"    narrowed delta source: {joined}")


def q2_grade(pos: list, label: str) -> dict:
    """N4 and N5 on a narrowed subset. Prints, returns flags."""
    rows = [dict(date=p.rec["date"], R=p.R) for p in pos]
    mean_r = AS.fmean([r["R"] for r in rows])
    lo, hi = P.boot_ci_by_date(rows, key="R", n=P.BOOT_N)
    n4 = mean_r > 0 and lo > 0
    print(f"  N4  meanR {mean_r:+.3f}  CI95 [{lo:+.3f},{hi:+.3f}]  (date-clustered, "
          f"BOOT_N {P.BOOT_N})  -> {'MET' if n4 else 'NOT MET'}")
    signs = []
    for name, months in P.DOMINANT_WINDOWS.items():
        kept = [r["R"] for r in rows if r["date"][:7] not in months]
        m = AS.fmean(kept)
        signs.append(m > 0)
        print(f"  N5  {name.replace('ex_', 'ex-')}: meanR {m:+.3f} (n={len(kept)})")
    for y, yr in P.by_year(rows).items():
        if len(yr) >= N5_MIN_YEAR_N:
            m = AS.fmean([r["R"] for r in yr])
            signs.append(m > 0)
            print(f"  N5  year {y}: meanR {m:+.3f} (n={len(yr)})")
        else:
            print(f"  N5  year {y}: n={len(yr)} < {N5_MIN_YEAR_N}, not graded")
    n5 = n4 and all(signs)
    print(f"  N5  -> {'MET' if n5 else 'NOT MET'}")
    return dict(N4=n4, N5=n5, lo=lo, hi=hi, mean=mean_r)


def q2_verdict(gn5: bool, gn0: bool, q1: bool, q2: dict | None) -> str:
    if gn5:
        return "AWAITING SCRAPE"
    if not gn0:
        return "UNDERPOWERED"
    if q2["hi"] <= 0:
        return "SELECTION"
    if q2["lo"] < 0 < q2["hi"] or q2["lo"] == 0:
        return "NULL"
    if q2["N4"] and q2["N5"]:
        return "NARROW-FEASIBLE" if q1 else "AFFORDABILITY"
    return "NO VERDICT MATCHES (N4 met, N5 not met)"


def print_ledger(n_cells: int) -> None:
    hdr("TRIAL LEDGER")
    print("""  The feasibility plan caps NEW arms on this era at three. This run enters
  exactly three new objects, and scores every cell below as SEEN:

    1. the narrow floor rule F3
    2. the $1,000 budget level
    3. the decoupled stop F4

  F1 and F2 at $500 were seen before registration (plan-time observations).""")
    print(f"  cells scored by this run: {n_cells} (7 registered cells x 2 cap cells x "
          f"2 populations, F3 only where GN5 lets it grade)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip-gates", action="store_true",
                    help="skip account_sim's G2-G5 (debugging only; the report "
                         "says so)")
    args = ap.parse_args(argv)
    logging.getLogger("backtest").setLevel(logging.ERROR)

    st = AS.load_settings(AS.DEFAULT_CONFIG)
    capital, low = st.capital, st.budget
    head_cap, caps = HEAD_NET_CAP, (HEAD_NET_CAP, ROBUST_NET_CAP)
    if abs(st.per_pos_cap - PER_POS_CAP) > 1e-9:
        print(f"REFUSED — config per-position cap {st.per_pos_cap} is not the "
              f"registered {PER_POS_CAP}")
        return 2
    assert abs(HIGH_BUDGET - MAX_LOSS_ABS) < 1e-9, "HIGH_BUDGET must be MAX_LOSS_ABS"

    hdr("narrow_to_fit — does narrowing an unaffordable spread beat refusing it?")
    print(f"""  Registration research/pre-registrations/f4_deployment/narrow_to_fit.md
  Capital ${capital:,.0f}. Budgets ${low:,.0f} (config) and ${HIGH_BUDGET:,.0f}.
  Cap cells: per-position {st.per_pos_cap:.2f}x, net {head_cap:.2f}x (headline) and
  {ROBUST_NET_CAP:.2f}x (robustness). Every cell runs under account_sim ARM R.
  NOTHING SHIPS FROM THIS STUDY. No annualised figure, Sharpe or
  time-to-recover is printed (GN6); every count below is computed by this run.""")

    recs, diag = load_book(include_bs=False)
    picked = P.top_k_per_day(recs, P.ladder_rank, k=st.max_per_day,
                             eligible_fn=P.ladder_eligible)
    print(f"  era {diag.get('era')}  book {len(recs)} rows  "
          f"{diag.get('n_dates')} dates  {diag.get('date_range')}")

    cell_st = {k: settings_for(st, kind, stop) for k, _l, kind, stop, _f, _r in CELLS}

    # ── G2-G5, account_sim's, on each settings basis the cached cells use ──
    gates_ok = True
    if args.skip_gates:
        hdr("GATES G2-G5 — SKIPPED (--skip-gates); this run is not a result")
    else:
        for name, s in (("$500", cell_st["F1_LO"]), ("$1,000", cell_st["F1_HI"]),
                        ("F4", cell_st["F4"])):
            print(f"\n######## account_sim gates on the {name} basis ########")
            res = AS.run_gates(recs, picked, s, AS.new_cache())
            gates_ok = gates_ok and res["ok"]
        if not gates_ok:
            print("\nGATE FAILURE (G2-G5) — no results printed. Exit 1.")
            return 1

    episodes = AS.dense_episodes(
        (d for d, _ in P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    ep_dates = {d for ep in episodes for d in ep}
    all_dates = {r["date"] for r in recs}
    refusal = AS.primary_refusal(all_dates, ep_dates, st)
    if refusal:
        print(f"\nREFUSED — {refusal}")
        return era.EXIT_THIN_ERA
    pops = (("PRIMARY", ep_dates), ("SECONDARY", all_dates))

    chain = Chain()
    evidence = unlisted_evidence()
    sim_cfg = _sim_cfg()
    narrower = Narrower(chain, evidence, sim_cfg)
    cache = AS.new_cache()
    exit_code = 0

    # ── GN3 PRICING MIRROR ────────────────────────────────────────────────
    hdr("GN3 PRICING MIRROR — the builder at a stored row's own strikes")
    cands = candidates(recs)
    tried = [r for r in cands if (r.get("max_loss_per_contract") or 0) > low
             and (r["t"].row.get("cost_basis") or "") == "commission_only"]
    fails = []
    for r in tried:
        ok, why = reproduces(r, chain, sim_cfg)
        if not ok:
            fails.append((r, why))
    print(f"  over-budget (${low:,.0f}) commission_only candidates tried: {len(tried)}  "
          f"reproduced {len(tried) - len(fails)}  failed {len(fails)}")
    for r, why in fails[:20]:
        print(f"    FAIL {r['date']} {r['ticker']} {r['structure']}: {why}")
    if len(fails) > 20:
        print(f"    ... {len(fails) - 20} more")
    gn3 = not fails
    print(f"  GN3: {'PASS' if gn3 else 'FAIL'}")

    # ── GN4 STRIKE BLINDNESS ──────────────────────────────────────────────
    hdr("GN4 STRIKE BLINDNESS — substitute histories cut after the entry day")
    n_cmp = n_diff = 0
    for b in (low, HIGH_BUDGET):
        for r in cands:
            if (r.get("max_loss_per_contract") or 0) <= b:
                continue
            roles = vertical_roles(list(r["t"].legs), r["credit"])
            day = recorded_entry_date(r["t"])
            if roles is None or day is None:
                continue
            full = choose_strike(r, b, chain, evidence, roles, day)
            anchor, mover = r["t"].legs[roles[0]], r["t"].legs[roles[1]]
            cut = {}
            for k in chain.strikes(anchor.ticker, anchor.expiration):
                if abs(k - mover.strike) < 1e-9 or abs(k - anchor.strike) < 1e-9:
                    continue
                cut[(mover.ticker, mover.expiration, round(k, 4), mover.opt_type)] = day
            blind = choose_strike(r, b, Chain(cutoff=cut, parent=chain), evidence,
                                  roles, day)
            n_cmp += 1
            if (full.reason, full.strike) != (blind.reason, blind.strike):
                n_diff += 1
                print(f"    DIFF {r['date']} {r['ticker']} ${b:,.0f}: "
                      f"{full.reason}/{full.strike} vs blind {blind.reason}/{blind.strike}")
    gn4 = n_diff == 0
    print(f"  choices compared {n_cmp}  identical {n_cmp - n_diff}")
    print(f"  GN4: {'PASS' if gn4 else 'FAIL'}")

    # ── run every cell ───────────────────────────────────────────────────
    sims: dict[tuple, AS.Sim] = {}
    b2s: dict[tuple, AS.Sim] = {}
    walked: dict[str, int] = {}
    for pop, dates in pops:
        pop_recs = [r for r in recs if r["date"] in dates]
        day_lists = P.ordered_by_day(pop_recs, P.ladder_rank, P.ladder_eligible)
        walked[pop] = sum(len(rk) for _d, rk in day_lists)
        for cap in caps:
            for key, label, _kind, _stop, floor, _role in CELLS:
                s = cell_st[key]
                sims[(pop, cap, key)] = AS.simulate(
                    day_lists, cfg_for(s, label, floor, cap), cache=cache,
                    narrower=narrower if floor == "narrow" else None)
            for key in ("F1_LO", "F1_HI", "F4"):
                s = cell_st[key]
                b2s[(pop, cap, key)] = AS.simulate(
                    day_lists, s.cfg(f"B2 {key}", compound=False, **AS.UNCONSTRAINED),
                    cache=cache)

        # GN1 / GN2 on this population at the headline cap cell
        if pop == "PRIMARY":
            hdr("GN1 REFUSE IDENTITY / GN2 STOP IDENTITY")
            gn1 = True
            refuser = Narrower(chain, evidence, sim_cfg, force_refuse=True)
            for b_key, f2_key in (("F3_LO", "F2_LO"), ("F3_HI", "F2_HI")):
                s = cell_st[b_key]
                forced = AS.simulate(day_lists, cfg_for(s, "GN1", "narrow", head_cap),
                                     cache=cache, narrower=refuser)
                same = (AS.book_signature(forced)
                        == AS.book_signature(sims[(pop, head_cap, f2_key)]))
                gn1 = gn1 and same
                print(f"  GN1 {CELL_LABEL[b_key]} forced-refuse vs {CELL_LABEL[f2_key]}: "
                      f"{len(forced.signal_pos)} vs "
                      f"{len(sims[(pop, head_cap, f2_key)].signal_pos)} positions -> "
                      f"{'identical' if same else 'DIFFERENT'}")
            s4 = dataclasses.replace(cell_st["F4"], dollar_stop=low)
            back = AS.simulate(day_lists, cfg_for(s4, "GN2", "take", head_cap), cache=cache)
            gn2 = AS.book_signature(back) == AS.book_signature(sims[(pop, head_cap, "F1_LO")])
            print(f"  GN2 F4 with its stop set back to ${low:,.0f} vs {CELL_LABEL['F1_LO']}: "
                  f"{'identical' if gn2 else 'DIFFERENT'}")
            print(f"  GN1: {'PASS' if gn1 else 'FAIL'}   GN2: {'PASS' if gn2 else 'FAIL'}")

    f3_gates_ok = gn1 and gn2 and gn3 and gn4
    if not f3_gates_ok:
        exit_code = 1

    # ── cached cells: the arms table ─────────────────────────────────────
    scores: dict[tuple, dict] = {}
    for pop, _dates in pops:
        for cap in caps:
            hdr(f"[{pop}] cap cell per-position {st.per_pos_cap:.2f}x, net {cap:.2f}x"
                f"{' (HEADLINE)' if cap == head_cap else ' (robustness)'}")
            print(COLS)
            for key, label, kind, _stop, floor, _role in CELLS:
                if floor == "narrow":
                    continue
                print_row(label, sims[(pop, cap, key)])
            print(f"\n  {'cell':<32}{'A1':>5}{'A2':>5}{'A3':>5}{'A4':>5}{'A5':>5}"
                  f"{'A6':>5}  verdict (account_sim grammar)")
            for key, label, kind, _stop, floor, _role in CELLS:
                if floor == "narrow":
                    continue
                b2_key = "F4" if key == "F4" else ("F1_LO" if kind == "low" else "F1_HI")
                s = AS.criteria_scores(sims[(pop, cap, key)], b2s[(pop, cap, b2_key)],
                                       cell_st[key])
                scores[(pop, cap, key)] = s
                flags = "".join(f"{'MET' if s[a] else 'no':>5}"
                                for a in ("A1", "A2", "A3", "A4", "A5", "A6"))
                print(f"  {label:<32}{flags}  {verdict_label(s, capital)}")

    # ── F3 cells: census, GN5, GN0 ───────────────────────────────────────
    hdr("F3 CELLS — census and coverage (GN5) / power (GN0)")
    f3 = {}
    for key in ("F3_HI", "F3_LO"):
        b = HIGH_BUDGET if key == "F3_HI" else low
        sub(f"{CELL_LABEL[key]}")
        for pop, _dates in pops:
            for cap in caps:
                c = print_census(sims[(pop, cap, key)],
                                 f"{pop} net {cap:.2f}x", walked[pop])
                f3[(pop, cap, key)] = c
        prim_ids = {id(r) for r in recs if r["date"] in ep_dates}
        print("  PRIMARY narrowing reasons (each over-budget pick once):")
        print_reasons(narrower, b, prim_ids)
        head = f3[("PRIMARY", head_cap, key)]
        gn5 = head["share"] > GN5_MAX_UNPRICED
        print(f"  GN5 COVERAGE: {head['unpriced']} of {head['offered']} over-budget "
              f"PRIMARY picks unpriced ({head['share']:.0%}; bar "
              f"{GN5_MAX_UNPRICED:.0%}) -> {'FIRES' if gn5 else 'clear'}")
        npos = narrowed_positions(sims[("PRIMARY", head_cap, key)])
        nd = len({p.rec["date"] for p in npos})
        gn0 = len(npos) >= GN0_MIN_POSITIONS and nd >= GN0_MIN_DATES
        print(f"  GN0 POWER: narrowed subset {len(npos)} positions on {nd} dates "
              f"(needs {GN0_MIN_POSITIONS} and {GN0_MIN_DATES}) -> "
              f"{'clear' if gn0 else 'UNDERPOWERED'}")
        f3[key] = dict(gn5=gn5, gn0=gn0)
    unproven = sum(1 for n in narrower.log.values() if n.reason == "unproven")
    print(f"""
  UNPROVEN means a grid strike between the proposed strike and the one the
  walk would reach is not cached and the skip-list holds no evidence against
  it. It could be listed and could fit, so the choice cannot be proven
  widest-that-fits and the pick is narrow_unpriced, never skipped. Picks
  stopped this way (each pick counted once per budget): {unproven}.""")

    # ── Q1 / Q2 and verdict lines ────────────────────────────────────────
    def q1(key: str) -> tuple[bool, list[str]]:
        lines, ok = [], True
        for cap in caps:
            s = scores.get(("PRIMARY", cap, key))
            if s is None:
                s = AS.criteria_scores(sims[("PRIMARY", cap, key)],
                                       b2s[("PRIMARY", cap, "F1_HI" if key.endswith("HI")
                                            else "F1_LO")], cell_st[key])
            n1 = feasible(s)
            med = n2_median(sims[("PRIMARY", cap, key)])
            n2 = med is not None and med <= N2_BAR
            n3 = True
            n3_lines = []
            for pop, _d in pops:
                ok3, ls = n3_pass(sims[(pop, cap, key)], sims[(pop, cap, "F1_LO")],
                                  capital)
                n3 = n3 and ok3
                n3_lines += [f"      {pop}: {x}" for x in ls] or [f"      {pop}: no window"]
            ok = ok and n1 and n2 and n3
            lines.append(f"  net {cap:.2f}x  N1 {'MET' if n1 else 'no'}  "
                         f"N2 median maxDD {('n/a' if med is None else f'{med:.1%}')} "
                         f"{'MET' if n2 else 'no'}  N3 {'MET' if n3 else 'no'}")
            lines += n3_lines
        return ok, lines

    hdr("STOP-BASIS LINES — (R, F1, $1,000) and F4 on N1-N3")
    ref_mdd = stats_line(sims[("PRIMARY", head_cap, "F1_LO")])[5]
    for key in ("F1_HI", "F4"):
        ok, lines = q1(key)
        print(f"  {CELL_LABEL[key]}")
        print("\n".join(lines))
        mdd = stats_line(sims[("PRIMARY", head_cap, key)])[5]
        line = ("STOP-FEASIBLE" if ok else
                "STOP-HURTS" if mdd < ref_mdd else "NOT FEASIBLE")
        print(f"  >>> {CELL_LABEL[key]}: {line} <<<  (PRIMARY maxDD ${mdd:,.0f} vs "
              f"{CELL_LABEL['F1_LO']} ${ref_mdd:,.0f})\n")

    verdicts = {}
    for key in ("F3_HI", "F3_LO"):
        hdr(f"{CELL_LABEL[key]} — Q1 and Q2"
            f"{' (HEADLINE)' if key == 'F3_HI' else ' (secondary)'}")
        gn5, gn0 = f3[key]["gn5"], f3[key]["gn0"]
        if not f3_gates_ok:
            failed = [g for g, ok in (("GN1", gn1), ("GN2", gn2), ("GN3", gn3),
                                      ("GN4", gn4)) if not ok]
            print(f"  {', '.join(failed)} FAILED: this cell is not graded whatever "
                  f"GN5 says, and the run exits non-zero.")
        if gn5:
            verdicts[key] = "AWAITING SCRAPE"
            print("  GN5 fires: census only, nothing graded. The fix is the scrape "
                  "(scripts/collector/fetch_substitute_legs.py), never a lower gate.")
        elif not f3_gates_ok:
            verdicts[key] = "NOT GRADED — " + ", ".join(
                g for g, ok in (("GN1", gn1), ("GN2", gn2), ("GN3", gn3),
                                ("GN4", gn4)) if not ok) + " FAILED"
        else:
            print(COLS)
            for cap in caps:
                print_row(f"PRIMARY net {cap:.2f}x", sims[("PRIMARY", cap, key)])
            ok1, lines = q1(key)
            print("  Q1")
            print("\n".join(lines))
            q2 = None
            if gn0:
                print("  Q2 — the narrowed subset, PRIMARY, headline cap cell")
                npos = narrowed_positions(sims[("PRIMARY", head_cap, key)])
                q2 = q2_grade(npos, CELL_LABEL[key])
                f1_key = "F1_HI" if key == "F3_HI" else "F1_LO"
                print_disclosures(npos, sims[("PRIMARY", head_cap, f1_key)])
            verdicts[key] = q2_verdict(False, gn0, ok1, q2)
        print(f"\n  >>> {CELL_LABEL[key]}: {verdicts[key]} <<<")

    print_ledger(len(sims))
    hdr("CLOSE")
    print(f"  headline {CELL_LABEL['F3_HI']}: {verdicts['F3_HI']}")
    print(f"  secondary {CELL_LABEL['F3_LO']}: {verdicts['F3_LO']}")
    print(f"  gates: G2-G5 {'SKIPPED' if args.skip_gates else 'PASS'}"
          f"  GN1 {'PASS' if gn1 else 'FAIL'}  GN2 {'PASS' if gn2 else 'FAIL'}"
          f"  GN3 {'PASS' if gn3 else 'FAIL'}  GN4 {'PASS' if gn4 else 'FAIL'}")
    print("  Nothing in this report is a shippable rule.")
    return exit_code


def print_disclosures(npos: list, f1: AS.Sim) -> None:
    """Build-note disclosures on the narrowed subset. Grade nothing."""
    unreachable = 0
    shifts = []
    for p in npos:
        t, o = p.rec["t"], p.rec["orig"]["t"]
        prof = AS.profile_for(p.rec)
        if not p.rec["credit"]:
            width = abs(t.legs[0].strike - t.legs[1].strike)
            if prof.get("pt") is not None and width - t.entry_net < prof["pt"] * t.entry_net:
                unreachable += 1
        roles = vertical_roles(list(t.legs), p.rec["credit"])
        k_anchor = t.legs[roles[0]].strike
        # A call spread breaks even at the anchor strike plus the net premium,
        # a put spread at the anchor strike minus it, debit or credit alike.
        sign = 1 if t.legs[0].opt_type == "Call" else -1
        be_new = k_anchor + sign * abs(t.entry_net)
        be_old = k_anchor + sign * abs(o.entry_net)
        shifts.append(be_new - be_old)
    print(f"  disclosure: narrowed debit spreads whose max gain is under the profit "
          f"target x debit (can never reach it): {unreachable}")
    if shifts:
        print(f"  disclosure: median breakeven shift {statistics.median(shifts):+.2f} "
              f"(narrowed minus proposed, in underlying points)")
    f1_by = {id(p.rec): p for p in f1.signal_pos}
    rows = [dict(date=p.rec["date"], a=p.dollars, b=f1_by[id(p.rec["orig"])].dollars)
            for p in npos if id(p.rec["orig"]) in f1_by]
    if rows:
        lo, hi = P.boot_ci_paired_by_date(rows, "a", "b")
        print(f"  paired contrast (prints, grades nothing): {len(rows)} narrowed picks "
              f"also taken by F1; mean R_dol narrowed minus F1 "
              f"{AS.fmean([r['a'] - r['b'] for r in rows]):+,.0f}  CI95 "
              f"[{lo:+,.0f},{hi:+,.0f}]")


if __name__ == "__main__":
    raise SystemExit(main())
