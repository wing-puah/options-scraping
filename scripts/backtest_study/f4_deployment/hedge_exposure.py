"""HEDGE-EXPOSURE arm — does concentration-triggered proxy hedging cut the book's drawdown?

Pre-registered 2026-08-29. Registration:
`research/pre-registrations/f4_deployment/hedge_exposure.md`, where
`scripts/study_review/` reads it. Read it before quoting anything printed here.

The operator's described practice is exposure-conditional: *"I hedge when I hold
a lot of correlated positions (semis -> SMH, tech -> QQQ), I see a specific
risk, AND the analysis says people are hedging."* This module asks whether that,
made mechanical, reduces the book's MARK-TO-MARKET drawdown versus carrying the
same concentrated book unhedged.

What this is NOT: not a timing study (`hedge_timing` returned 0 of 9 and no arm
here is keyed to a calendar or market state); not a selection study (`bear_deploy`
D1 stands); not a worst-decile tail study (every primary metric is path-shaped,
computed over every session the book is open); not a test of the §4 bear sleeve
(it appears only as instrument comparison ARM B and cannot be removed by any
outcome here); and NOT `concurrency_correlation` — that study asks whether
concentration degrades per-position R and its remedy is to deploy less; this one
asks whether concentration can be OVERLAID. Neither may be cited as evidence
for the other.

Arms:

  ARM M   MEASUREMENT. The SAME unhedged book on both curves — mark-to-market
          (from `daily_pnl_csv`) versus realized-on-close (`account_sim`'s
          `equity_curve` basis). Runs first, gates nothing.
  ARM C   Concentration-gated proxy put. Hedge while concentration >= tau,
          tau in {0.30, 0.35, 0.40}, sized at fraction f in {0.25, 0.50, 1.00}
          of a standard position's risk. Carries no prose.
  ARM CS  ARM C additionally requiring `hedge-pressure >= 50` in the analysis
          prose. PROSE-CONDITIONED.
  ARM P   ARM C on exactly ARM CS's session set, minus the prose condition —
          which is ARM CS's session set. INERT AS REGISTERED (ERRATUM 2), left
          literal rather than redefined, and the registration's binding prose
          rule is therefore unreachable by construction.
  ARM N   Random-admission null, 200 seeds, matched on episode COUNT, episode
          LENGTHS and PROXY mix. An arm must beat its 95th percentile; a
          CONTRARY must fall below its 5th.
  ARM B   Instrument comparison — the book's own bear row instead of the put.
  ARM R   Always-fillable reference — a delta-equivalent SHORT in the proxy
          underlying. Clause 7's control: a put that merely matches it is A
          RESTATEMENT OF DELTA REDUCTION. A floor on feasibility, NOT a
          recommendation.
  ARM RF  UNREGISTERED — ADDED AFTER COMMIT. ARM R's fill-independent floor,
          sized off the concentrated cluster's own net delta notional. Every
          row of it carries that label and no clause is read from it.

POPULATION: the registration's own population clause names two different books
(ERRATUM 1 in `research/hedge-exposure-errata.md`). Both are run, both are
printed with every count computed at run time, and NO study-level verdict is
emitted from either until the operator ratifies a reading.

Unit: the session. Primary metric: max drawdown in DOLLARS on the
mark-to-market curve. Co-primary, path-shaped: Ulcer index and time-under-water.
Secondary, never concluded from: total P&L, worst single session, realized-on-
close max drawdown. No annualised figure, Sharpe or time-to-recover is computed
or printed, by construction.

Gates: G-ERA (v4 or refuse) · G-FILL (band-rule fills on >=60% of triggered
sessions, else the put arms are NOT EVALUABLE) · G-POWER (>=25 date-clustered
trigger dates per cell; UNDERPOWERED is not a lean) · G-BLIND (the trigger must
be computable with outcome fields stripped) · G-MTM (the mark-to-market curve
reconciles to the booked realized P&L at every exit) · G-CENSUS (the power
census prints before any outcome column is read).

NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF. A MECHANISM-FOUND
verdict produces a DRAFTED §4 amendment held in `research/`, never an edit.

Run:
    source .venv/bin/activate
    python -m scripts.backtest_study run hedge_exposure
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest_study.f4_deployment import account_sim as A  # noqa: E402
from scripts.backtest_study.lib import concentration as C  # noqa: E402
from scripts.backtest_study.lib import hedge_instrument as HI  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as M  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import sectors as S  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# 2 and 3 belong to lib/era.py's thin-era and era-mismatch refusals; this study
# numbers from 4. A LITERAL set: run.py::_refusal_codes parses it with `ast` and
# never imports the module, so an alias or a frozenset() call is invisible to it.
EXIT_MTM_RECONCILE = 4
DESIGNED_REFUSAL_EXIT_CODES = {2, 3, 4}

# G-BLIND is NOT in that set on purpose. A trigger that moves when the outcome
# columns are stripped is a DEFECT in this module, not a pre-registered refusal,
# so it exits 1 and the runner deletes -latest.txt rather than promoting it.
EXIT_LOOKAHEAD = 1

# ── committed constants, imported never restated ────────────────────────────
TAU_GRID = C.TAU_GRID                 # (0.30, 0.35, 0.40)
F_GRID = C.F_GRID                     # (0.25, 0.50, 1.00)
MIN_TRIGGER_DATES = C.MIN_TRIGGER_DATES   # 25, date-clustered
HEDGE_PRESSURE_CUT = C.HEDGE_PRESSURE_CUT  # 50
FILL_GATE = HI.FILL_GATE              # 0.60, band rule
N_CELLS = len(TAU_GRID) * len(F_GRID)  # 9; Bonferroni denominator, fixed here
ALPHA = 0.05 / N_CELLS

# ── this module's own knobs (NOT pre-registered; stated in the report) ───────
N_SEEDS = 200                 # ARM N, as registered
BOOT_N = 2000                 # block-bootstrap resamples per cell
SEED = 20260829
MIN_YEARS_POSITIVE = 2        # bar clause 4
SETTLE_LOOKBACK_DAYS = 7      # bars to walk back for an expiry settlement spot
BOOT_BLOCK_MIN = 5            # floor on the moving block, in sessions

# The two bootstrap estimators. CHRONO is what clause 2 is read from; SHUFFLE
# is the withdrawn month-shuffle estimator, printed only so the report can say
# whether clause 2's outcome survived replacing it (errata F5).
BOOT_CHRONO = "chronological_moving_block"
BOOT_SHUFFLE = "month_shuffle_withdrawn"

VERDICTS = ("MECHANISM-FOUND", "NULL", "CONTRARY", "UNDERPOWERED",
            "NOT EVALUABLE", "MEASUREMENT-ONLY")

# The registration's population clause names two different books (ERRATUM 1).
# Both are run; neither is concluded from.
POP_REAL = "real"
POP_ALL = "all"
POP_BOTH = "both"
POP_LABELS = {
    POP_REAL: "the raw BacktestResults stratum (real pricing only)",
    POP_ALL: "the literal load_book(include_bs=False) call (real + tweak)",
}

# ARM R's caveat is COMMITTED prose, quoted verbatim from the registration and
# printed immediately above ARM R's own rows.
ARM_R_CAVEAT = ("ARM R is a floor on feasibility, not a recommendation: it has "
                "a different loss\n  shape from a put and is not an instrument "
                "the operator trades.")

# ARM RF is this module's own addition and prints the largest positive numbers
# in the report. Every one of its rows carries this label (errata F4).
ARM_RF_LABEL = "UNREGISTERED — ADDED AFTER COMMIT"

# Metric keys. `max_dd` is the PRIMARY; ulcer/tuw are the co-primaries clause 2
# is read on. Improvement is always signed so that POSITIVE means BETTER.
METRIC_MAXDD = "max_dd"
METRIC_ULCER = "ulcer"
METRIC_TUW = "tuw"
CO_PRIMARIES = (METRIC_ULCER, METRIC_TUW)


# ════════════════════════════════════════════════════════════════════════════
# printing helpers (shape copied from bear_deploy.py / hedge_timing.py)
# ════════════════════════════════════════════════════════════════════════════

def hdr(t: str) -> None:
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t: str) -> None:
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


def _ym(d: _date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _num(v) -> str:
    """A metric value, or `n/a` — never a bare `None` printed as text."""
    if v is None or v != v:
        return "n/a"
    return f"{v:+.4f}"


# ════════════════════════════════════════════════════════════════════════════
# Basis — the book, its positions, and the two curves
# ════════════════════════════════════════════════════════════════════════════

def book_positions(recs: list[dict]) -> list[A.Pos]:
    """Every book row as an `account_sim.Pos`, at its OWN contract count and on
    its OWN STORED outcome.

    This is the basis the pre-registration's own figures were measured on:
    `daily_pnl_csv` populated on every row, the session universe, the exposure
    table and the concentration quantiles are all the whole book, not an
    admitted subset.

    STORED, not replayed — the 2026-08-29 errata's F2. This function used to
    take `days_held` AND `dollars` from one `A.replay_sized(...)` call, and
    `mtm_curve.book_curves` then compared the MTM level indexed by that
    `days_held` against that same `dollars`: one replay on both sides of an
    equals sign, so G-MTM reported a perfect reconciliation it was incapable of
    failing. Taking the exit index and the booked dollars from the ROW makes
    the gate a check between two independent stored columns
    (`daily_pnl_csv` vs `realized_pnl_abs`), which can fail — and it aligns the
    curve's exit with the one `lib/concentration.py` already computes occupancy
    from, so the trigger and the drawdown path speak about the same sessions.

    The replay has not gone away: `replay_divergence()` runs it alongside and
    the report discloses how far it lands from the stored outcome.
    """
    out: list[A.Pos] = []
    for rec in recs:
        t = rec["t"]
        dh_stored = rec["days_held"]
        if dh_stored is None:
            raise ValueError(
                f"{rec['date']} {rec['ticker']}: no stored days_held — a row "
                f"with no exit index has no [entry, exit] window")
        dh = min(int(dh_stored), len(t.grid))
        out.append(A.Pos(
            rec=rec, contracts=t.contracts,
            reserved=(rec["max_loss_per_contract"] or 0.0) * t.contracts,
            dn=A.signed_dn(rec, t.contracts),
            entry_sess=t.grid[0], exit_sess=t.grid[dh - 1],
            days_held=int(dh_stored), R=rec["R"],
            dollars=M.stored_booked(rec), exit_reason=rec["exit_reason"]))
    return out


def replay_divergence(recs: list[dict], cache: dict) -> dict:
    """How far the SHIPPED-profile replay lands from each row's stored outcome.

    Disclosed, never gated on. The curve is built from the stored columns (see
    `book_positions`), so this is the figure that says what that choice cost —
    and, equally, what the previous replay-on-both-sides G-MTM was hiding. It
    is a property of the export, so every count here is computed at run time.
    """
    n_dh = n_reason = 0
    stored_total = replay_total = 0.0
    abs_gap = 0.0
    n_priced = 0
    for rec in recs:
        t = rec["t"]
        rp = A.replay_sized(rec, t.contracts, A.MAX_LOSS_ABS,
                            profile=A.profile_for(rec), cache=cache)
        if rec["days_held"] is not None and rp["days_held"] != rec["days_held"]:
            n_dh += 1
        if rec["exit_reason"] and rp["exit_reason"] != rec["exit_reason"]:
            n_reason += 1
        booked = M.stored_booked(rec)
        if booked is not None and rp["dollars"] is not None:
            stored_total += booked
            replay_total += rp["dollars"]
            abs_gap += abs(rp["dollars"] - booked)
            n_priced += 1
    return dict(n_rows=len(recs), n_priced=n_priced, n_days_held=n_dh,
                n_exit_reason=n_reason, stored_total=stored_total,
                replay_total=replay_total, abs_gap=abs_gap)


def curve_of(sessions: list[_date], daily: list[float],
             basis: str = M.MTM) -> M.Curve:
    """A `Curve` from per-session CHANGES; `levels` is their running sum."""
    levels: list[float] = []
    run = 0.0
    for d in daily:
        run += d
        levels.append(run)
    return M.Curve(basis, list(sessions), list(daily), levels)


def stats_on(axis: list[_date], daily: list[float], capital: float,
             keep=None) -> M.PathStats:
    """Path stats over `axis`, optionally restricted to the sessions `keep`.

    A cut re-runs the whole curve on the surviving sessions rather than slicing
    a precomputed level series: a drawdown is path-dependent, so a cut that kept
    the levels would carry the excluded window's peak into the remainder.
    """
    if keep is None:
        return M.path_stats(curve_of(axis, daily), capital)
    sess = [s for s in axis if s in keep]
    dd = [d for s, d in zip(axis, daily) if s in keep]
    return M.path_stats(curve_of(sess, dd), capital)


def improvement(base: M.PathStats, hedged: M.PathStats, metric: str) -> float:
    """Signed so POSITIVE is always BETTER, whichever metric is asked for."""
    if metric == METRIC_MAXDD:
        return hedged.max_dd - base.max_dd      # both <= 0; less negative wins
    if metric == METRIC_ULCER:
        return base.ulcer - hedged.ulcer
    if metric == METRIC_TUW:
        return base.tuw - hedged.tuw
    raise ValueError(f"unknown metric {metric!r}")


# ════════════════════════════════════════════════════════════════════════════
# The hedge, as a set of dated dollar CHANGES on the book's session axis
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Segment:
    """One instrument held over a contiguous run of sessions inside an episode.

    A long episode outlives a 25-75 DTE put, so the hedge ROLLS: each segment is
    one contract held from `days[0]` until it expires or the episode ends.
    `days[-1]` is the settlement session when `expired` is set.
    """
    pick: HI.PutPick
    contracts: int
    days: tuple[_date, ...]
    expired: bool


@dataclass
class Leg:
    """One episode's hedge — its segments and the dated dollar changes."""
    episode: tuple[_date, ...]
    proxy: str
    segments: list[Segment] = field(default_factory=list)
    daily: dict[_date, float] = field(default_factory=dict)
    cost: float = 0.0
    label: str = ""


def _contracts_for(unit_cost: float, f: float, budget: float) -> int:
    """`int(f x risk_contracts(...))` — account_sim ARM H's SKIP convention.

    The pre-registration flags `max(1, int(f x contracts))` as a defect to
    inherit-fix: it silently promotes every hedge to full size whenever the risk
    size is one contract. ARM H fixed it by SKIPPING the sub-one-contract hedge,
    and that is what a 0 here means — the session is carried at f=0 and counted,
    never rounded up.
    """
    base = A.risk_contracts(unit_cost, budget)
    return 0 if base is None else int(f * base)


def _settled_level(pick: HI.PutPick, contracts: int) -> float | None:
    """Open P&L dollars if the put is settled at expiry intrinsic.

    `hedge_instrument.mark_on` never carries a mark past expiry, so without this
    a put that expires inside an episode would freeze at its last quoted mark
    and never book the drop to zero. The spot is that expiry's close, walked
    back at most a week for a holiday/half-session gap.
    """
    spot = None
    for back in range(SETTLE_LOOKBACK_DAYS + 1):
        spot = HI.spot_on(pick.ticker, pick.expiry - timedelta(days=back))
        if spot is not None:
            break
    if spot is None:
        return None
    intrinsic = max(pick.strike - spot, 0.0)
    return (intrinsic - pick.entry_mark) * HI.SHARES_PER_CONTRACT * contracts


def hold_window(episode, universe) -> list[_date]:
    """The episode PLUS the next session in the universe — the hedge's window.

    NOT pre-registered and stated in the report. An instrument opened and closed
    on the same mark contributes exactly zero, so an episode of one session
    would be structurally invisible: at the tau grid's ARM CS sets EVERY episode
    is one session long, and the arm would print an identical curve to f=0 for a
    reason that is arithmetic, not economic. The decision to unhedge is made at
    the close of the last triggered session and fills at the next one, which is
    the entry-at-next-close convention the rest of the package already uses.
    Episodes are separated by at least one untriggered session, so the extension
    can never overlap the next episode.
    """
    ep = list(episode)
    order = {s: i for i, s in enumerate(universe)}
    last = order.get(ep[-1])
    if last is not None and last + 1 < len(universe):
        ep.append(universe[last + 1])
    return ep


def plan_episode(proxy: str, episode, f: float, budget: float,
                 rule: str, diag: dict, universe=None) -> Leg:
    """Select (and roll) the proxy put across one trigger episode.

    A session with no fillable contract, or whose size rounds below one
    contract, is carried at f=0 — the hedge simply is not on that day, and the
    next session tries again. Nothing is fabricated and nothing is dropped.
    """
    window = episode if universe is None else hold_window(episode, universe)
    leg = Leg(episode=tuple(window), proxy=proxy)
    cur_pick: HI.PutPick | None = None
    cur_c = 0
    cur_days: list[_date] = []
    for day in window:
        if cur_pick is not None and day > cur_pick.expiry:
            leg.segments.append(Segment(cur_pick, cur_c,
                                        tuple(cur_days + [day]), True))
            diag["rolls"] += 1
            cur_pick, cur_c, cur_days = None, 0, []
        if cur_pick is None:
            pick = HI.select_put(proxy, day, rule)
            if pick is None:
                diag["sessions_no_fill"] += 1
                continue
            c = _contracts_for(pick.entry_mark * HI.SHARES_PER_CONTRACT, f, budget)
            if c < 1:
                diag["sessions_sub_one"] += 1
                continue
            cur_pick, cur_c, cur_days = pick, c, [day]
            leg.cost += HI.entry_cost(pick, c)
            diag["opens"] += 1
            continue
        cur_days.append(day)
    if cur_pick is not None:
        leg.segments.append(Segment(cur_pick, cur_c, tuple(cur_days), False))
    if leg.segments:
        leg.label = leg.segments[0].pick.label()
    return leg


def price_put(leg: Leg) -> dict[_date, float]:
    """Per-session dollar CHANGES of the long put(s) in `leg`."""
    out: dict[_date, float] = {}
    for seg in leg.segments:
        prev = 0.0
        out.setdefault(seg.days[0], 0.0)
        for day in seg.days[1:]:
            if day > seg.pick.expiry:
                lvl = _settled_level(seg.pick, seg.contracts)
            else:
                lvl = HI.pnl_path(seg.pick, [day], seg.contracts)[day]
            if lvl is None:
                continue            # an unpriced hedge is not a flat hedge
            out[day] = out.get(day, 0.0) + (lvl - prev)
            prev = lvl
    return out


def price_delta_short(leg: Leg, diag: dict) -> dict[_date, float]:
    """ARM R — the same segments, carried as a delta-equivalent SHORT.

    Sized through `hedge_instrument.delta_equivalent_short`, which returns None
    rather than 0.0 when the put's entry delta is missing: a fabricated zero
    would size the control at nothing and make the put look better by exactly
    the missing exposure.
    """
    out: dict[_date, float] = {}
    for seg in leg.segments:
        pos = HI.delta_equivalent_short(seg.pick, seg.contracts)
        if pos is None:
            diag["no_entry_delta"] += 1
            continue
        levels = HI.short_pnl_path(pos, seg.days)
        prev = 0.0
        for day in seg.days:
            lvl = levels.get(day)
            if lvl is None:
                continue
            out[day] = out.get(day, 0.0) + (lvl - prev)
            prev = lvl
    return out


def price_cluster_short(proxy: str, episode, cluster_net: float, f: float,
                        diag: dict, universe=None) -> dict[_date, float]:
    """ARM RF — the fill-INDEPENDENT floor: short fraction f of the
    concentrated cluster's own signed delta notional in the proxy underlying.

    The registration's ARM R is delta-matched to ARM C's put, which makes it
    depend on the option cache it was introduced to be free of. Both readings
    are therefore run: ARM R is clause 7's control, ARM RF is the floor that
    keeps the study from terminating on fill coverage (`calendar_hedge`'s end).
    The sign is the caller's: a POSITIVE cluster net (a long book) is stood
    against by carrying `-f x net`.
    """
    window = list(episode) if universe is None else hold_window(episode, universe)
    pos = HI.short_for_delta_notional(proxy, window[0], -f * cluster_net)
    if pos is None:
        diag["no_bar"] += 1
        return {}
    levels = HI.short_pnl_path(pos, window)
    out: dict[_date, float] = {}
    prev = 0.0
    for day in window:
        lvl = levels.get(day)
        if lvl is None:
            continue
        out[day] = out.get(day, 0.0) + (lvl - prev)
        prev = lvl
    return out


def price_bear_row(rec: dict, contracts: int, stop: float,
                   cache: dict) -> dict[_date, float]:
    """ARM B — the book's own bear row, marked to market like any position."""
    rp = A.replay_sized(rec, contracts, stop, cache=cache)
    pos = A.Pos(rec=rec, contracts=contracts,
                reserved=(rec["max_loss_per_contract"] or 0.0) * contracts,
                dn=A.signed_dn(rec, contracts),
                entry_sess=rec["t"].grid[0],
                exit_sess=rec["t"].grid[min(rp["days_held"],
                                            len(rec["t"].grid)) - 1],
                days_held=rp["days_held"], R=rp["R"], dollars=rp["dollars"],
                exit_reason=rp["exit_reason"])
    sess, dol, _ = M.position_marks(pos)
    out: dict[_date, float] = {}
    prev = 0.0
    for s, lvl in zip(sess, dol):
        out[s] = out.get(s, 0.0) + (lvl - prev)
        prev = lvl
    return out


def peak_debit(legs) -> float:
    """Largest hedge debit outstanding on any one session, in dollars.

    The hedge is NOT routed through `account_sim.admission()` on this basis —
    the whole book at its own contract counts has no ledger to admit against —
    so the footprint is reported instead of enforced, and a reader can see
    whether a cell would have fitted inside the account at all.
    """
    per: dict[_date, float] = defaultdict(float)
    for leg in legs:
        for seg in leg.segments:
            cost = HI.entry_cost(seg.pick, seg.contracts)
            for day in seg.days:
                per[day] += cost
    return max(per.values(), default=0.0)


def merge(dicts) -> dict[_date, float]:
    out: dict[_date, float] = defaultdict(float)
    for d in dicts:
        for k, v in d.items():
            out[k] += v
    return dict(out)


def hedged_daily(axis: list[_date], base_daily: list[float],
                 hedge: dict[_date, float]) -> list[float]:
    return [b + hedge.get(s, 0.0) for s, b in zip(axis, base_daily)]


# ════════════════════════════════════════════════════════════════════════════
# Date-clustered inference
# ════════════════════════════════════════════════════════════════════════════

def month_blocks(axis: list[_date]) -> list[list[int]]:
    """The session axis cut into calendar-month blocks — the resampling unit.

    The unit of this study is the SESSION and adjacent sessions share almost the
    whole open book, so a session-level bootstrap would treat one occasion as
    dozens of independent draws. Months are the date-cluster the whole package
    resamples on (`protocol.boot_ci_by_date`'s clustering, applied to a path).
    """
    blocks: dict[str, list[int]] = defaultdict(list)
    for i, s in enumerate(axis):
        blocks[_ym(s)].append(i)
    return [blocks[k] for k in sorted(blocks)]


def block_length(axis: list[_date]) -> int:
    """The moving block's length in SESSIONS: the MEDIAN calendar-month block.

    The date-cluster stays the month — that is the package's unit and this
    module's `month_blocks` still defines it. What changes (errata F5) is that
    the block is a contiguous RUN of sessions of that typical length, taken
    anywhere on the axis, rather than a named calendar month.
    """
    sizes = sorted(len(b) for b in month_blocks(axis))
    if not sizes:
        return 1
    return max(BOOT_BLOCK_MIN, sizes[len(sizes) // 2])


def _chronological_index(n: int, length: int, rng: random.Random) -> list[int]:
    """Moving-block resample indices, RE-SORTED into calendar order.

    Blocks are drawn with replacement from every contiguous run of `length`
    sessions — the block is what carries the serial dependence adjacent
    sessions have — and the resulting index list is then SORTED, so the
    resampled series runs FORWARDS in time. Overlapping and repeated blocks
    make that a real step: without the sort the series jumps backwards at every
    block boundary.

    That is the fix. Max drawdown, Ulcer and time-under-water are
    PATH-DEPENDENT: a resample that reorders the tape makes the ordering part
    of the statistic, and the spread of such draws is not that statistic's
    sampling distribution. The withdrawn month-shuffle estimator did exactly
    that, which is why its ulcer interval ran [-8.70, +8.93] around a point of
    +0.11.
    """
    last = max(0, n - length)
    k = max(1, -(-n // length))          # ceil
    idx: list[int] = []
    for _ in range(k):
        s = rng.randint(0, last)
        idx.extend(range(s, min(s + length, n)))
    idx.sort()
    return idx[:n]


def _month_shuffle_index(n: int, blocks: list[list[int]],
                         rng: random.Random) -> list[int]:
    """The WITHDRAWN estimator, kept only as a printed diagnostic.

    Calendar months drawn with replacement and concatenated IN DRAWN ORDER.
    Reported so the report can say whether clause 2's failure survives the
    change to `_chronological_index`; no clause is read from it.
    """
    nb = len(blocks)
    idx: list[int] = []
    for _ in range(nb):
        idx.extend(blocks[rng.randrange(nb)])
    return idx


def boot_ci(axis: list[_date], base_daily: list[float], hedge_daily: list[float],
            capital: float, metric: str, n: int = BOOT_N,
            seed: int = SEED, alpha: float = ALPHA,
            estimator: str = BOOT_CHRONO) -> tuple[float, float, float]:
    """(point, lo, hi) for the hedged-minus-unhedged improvement in `metric`.

    PAIRED: each resample draws one index sequence and applies it to BOTH
    curves, so the difference isolates the hedge rather than the resampled
    tape. `alpha` is Bonferroni-corrected for the 9 cells fixed at
    registration.

    `estimator` is `BOOT_CHRONO` (the chronological moving-block bootstrap that
    clause 2 is read from) or `BOOT_SHUFFLE` (the withdrawn month-shuffle
    estimator, printed as a diagnostic only).
    """
    point = improvement(M.path_stats(curve_of(axis, base_daily), capital),
                        M.path_stats(curve_of(axis, hedge_daily), capital),
                        metric)
    blocks = month_blocks(axis)
    if len(blocks) < 2 or len(axis) < 2:
        return point, float("nan"), float("nan")
    rng = random.Random(seed)
    length = block_length(axis)
    n_ax = len(axis)
    draws: list[float] = []
    for _ in range(n):
        if estimator == BOOT_SHUFFLE:
            idx = _month_shuffle_index(n_ax, blocks, rng)
        else:
            idx = _chronological_index(n_ax, length, rng)
        b = [base_daily[i] for i in idx]
        h = [hedge_daily[i] for i in idx]
        sess = [axis[i] for i in idx]
        draws.append(improvement(M.path_stats(curve_of(sess, b), capital),
                                 M.path_stats(curve_of(sess, h), capital),
                                 metric))
    draws.sort()
    lo = draws[max(0, int(round((alpha / 2) * (n - 1))))]
    hi = draws[min(n - 1, int(round((1 - alpha / 2) * (n - 1))))]
    return point, lo, hi


def pctile(vals: list[float], q: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# ════════════════════════════════════════════════════════════════════════════
# Cells
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Cell:
    arm: str
    tau: float
    f: float
    rule: str
    n_sessions: int
    n_episodes: int
    n_book_dates: int
    powered: bool
    legs: list = field(default_factory=list)
    hedge: dict = field(default_factory=dict)
    diag: dict = field(default_factory=dict)
    stats: M.PathStats | None = None
    verdict: str = ""
    clauses: dict = field(default_factory=dict)


def build_cell(arm: str, tau: float, f: float, rule: str, triggered,
               eps, by_session, budget: float, universe) -> Cell:
    diag = dict(rolls=0, opens=0, sessions_no_fill=0, sessions_sub_one=0,
                unhedgeable_episodes=0, unhedgeable_sessions=0)
    counts = dict(sessions=len(triggered), episodes=len(eps))
    cell = Cell(arm=arm, tau=tau, f=f, rule=rule,
                n_sessions=counts["sessions"], n_episodes=counts["episodes"],
                n_book_dates=0, powered=counts["episodes"] >= MIN_TRIGGER_DATES,
                diag=diag)
    for ep in eps:
        sc = by_session[ep[0]]
        if sc.top_proxy is None or not sc.top_hedgeable:
            diag["unhedgeable_episodes"] += 1
            diag["unhedgeable_sessions"] += len(ep)
            continue
        cell.legs.append(plan_episode(sc.top_proxy, ep, f, budget, rule, diag,
                                      universe))
    cell.hedge = merge(price_put(leg) for leg in cell.legs)
    return cell


# ════════════════════════════════════════════════════════════════════════════
# The 7-clause bar
# ════════════════════════════════════════════════════════════════════════════

def _finite(v) -> bool:
    return v is not None and v == v


def evaluate_contrary(base, hedged, cis: dict, arm_n_p05: dict,
                      per_year: dict, cuts: dict, loo: dict,
                      min_years: int = MIN_YEARS_POSITIVE) -> dict:
    """The NEGATIVE bar — the clause set a CONTRARY verdict must clear.

    Errata F1. Until 2026-08-29 this module emitted CONTRARY from
    `hedged.max_dd < base.max_dd and point < 0`: no confidence interval, no ARM
    N band, no year sign, no ex-window cut, no leave-one-date-out fold. A
    POSITIVE needed all seven clauses; a NEGATIVE needed none — and a
    cell-level CONTRARY escalated to the study's verdict. At tau 0.30 / f 0.25
    the cell sat at dMaxDD +$26, i.e. $26 of noise away from printing CONTRARY
    as a finding.

    A negative is now held to the same evidence as a positive, with the sign
    inverted:

      1'  max drawdown strictly WORSE than f=0 (the primary metric, dollars)
      2'  a co-primary whose date-clustered CI lies ENTIRELY BELOW zero at the
          same Bonferroni alpha = 0.05/9
      3'  WORSE than ARM N's 5th percentile on that metric (the mirror of
          clause 3's 95th)
      4'  negative in >= `min_years` of the book's years
      5'  both ex-window cuts keep the negative sign
      6'  every leave-one-date-out fold keeps the negative sign

    Anything short of all six falls through to NULL. Clause 7 has no mirror:
    it asks whether a put merely restates ARM R's delta reduction, which is a
    question about an EFFECT, and a cell with no effect to explain does not
    need it explained.

    Pure by design — `cis`, `arm_n_p05`, `per_year`, `cuts` and `loo` are all
    metric-keyed plain maps — so every clause can be broken one at a time in a
    table-driven test.
    """
    out: dict = {}
    out["n1"] = hedged.max_dd < base.max_dd
    losers = [m for m, (pt, lo, hi) in cis.items()
              if _finite(lo) and _finite(hi) and pt < 0 and hi < 0]
    out["n2"] = bool(losers)
    metric = losers[0] if losers else None
    out["metric"] = metric
    if metric is None:
        out.update({"point": None, "arm_n_p05": None,
                    "n3": False, "n4": False, "n5": False, "n6": False,
                    "contrary": False})
        return out
    point = cis[metric][0]
    p05 = arm_n_p05.get(metric)
    years = per_year.get(metric, {})
    cut = cuts.get(metric, {})
    folds = loo.get(metric, [])
    out["point"] = point
    out["arm_n_p05"] = p05
    out["n3"] = _finite(p05) and point < p05
    out["n4"] = sum(1 for v in years.values() if v < 0) >= min_years
    out["n5"] = bool(cut) and all(v < 0 for v in cut.values())
    out["n6"] = bool(folds) and all(v < 0 for v in folds)
    out["contrary"] = all(out[f"n{i}"] for i in range(1, 7))
    return out


def cell_verdict(res: dict) -> str:
    """CANDIDATE / CONTRARY / NULL for one evaluated cell.

    NULL is the fall-through in BOTH directions: a cell that clears neither the
    positive bar nor the negative one has not shown anything.
    """
    if res.get("candidate"):
        return "CANDIDATE"
    if res.get("contrary", {}).get("contrary"):
        return "CONTRARY"
    return "NULL"


def evaluate_bar(cell: Cell, axis, base_daily, capital, arm_n,
                 arm_r_improvement, boot_n: int) -> dict:
    """Every clause of the registration's bar, computed and reported in full,
    plus the mirrored negative bar `evaluate_contrary` reads.

    A cell is a CANDIDATE only if ALL seven hold. Clause 2 needs only ONE
    co-primary to move, so both are tested and the better one named.

    `arm_n` is `{metric: (p05, p95)}` — the 95th percentile clause 3 must beat
    and the 5th percentile clause 3' must fall below.

    The year, ex-window and leave-one-out stability re-runs produce PathStats,
    not a single number, and the improvement for BOTH co-primaries is read off
    the same PathStats. So the positive and the negative bar cost one pass
    between them and can never be computed on different re-runs.
    """
    hd = hedged_daily(axis, base_daily, cell.hedge)
    base = M.path_stats(curve_of(axis, base_daily), capital)
    hedged = M.path_stats(curve_of(axis, hd), capital)
    cell.stats = hedged
    out: dict = {"base": base, "hedged": hedged}

    # 1 — bear_deploy D3's criterion, verbatim, on dollars.
    out["c1"] = (hedged.max_dd >= base.max_dd
                 and hedged.worst_session >= base.worst_session)

    # 2 — a co-primary whose date-clustered CI excludes zero at alpha/9.
    cis, cis_withdrawn = {}, {}
    for metric in CO_PRIMARIES:
        cis[metric] = boot_ci(axis, base_daily, hd, capital, metric, n=boot_n,
                              estimator=BOOT_CHRONO)
        cis_withdrawn[metric] = boot_ci(axis, base_daily, hd, capital, metric,
                                        n=boot_n, estimator=BOOT_SHUFFLE)
    out["ci"] = cis
    out["ci_withdrawn"] = cis_withdrawn
    winners = [m for m, (pt, lo, hi) in cis.items()
               if _finite(lo) and _finite(hi) and pt > 0 and lo > 0]
    out["c2"] = bool(winners)
    out["c2_withdrawn"] = bool([
        m for m, (pt, lo, hi) in cis_withdrawn.items()
        if _finite(lo) and _finite(hi) and pt > 0 and lo > 0])
    losers = [m for m, (pt, lo, hi) in cis.items()
              if _finite(lo) and _finite(hi) and pt < 0 and hi < 0]
    # The metric everything downstream is READ on: the co-primary that moved,
    # in whichever direction. Ulcer when neither did, so the report still
    # prints a number rather than a blank.
    metric = winners[0] if winners else (losers[0] if losers else METRIC_ULCER)
    out["metric"] = metric
    point = cis[metric][0]

    # --- stability re-runs, once, as PathStats -----------------------------
    years = sorted({s.year for s in axis})
    year_stats = {}
    for y in years:
        keep = {s for s in axis if s.year == y}
        year_stats[y] = (stats_on(axis, base_daily, capital, keep),
                         stats_on(axis, hd, capital, keep))
    cut_stats = {}
    for name, months in P.DOMINANT_WINDOWS.items():
        keep = {s for s in axis if _ym(s) not in months}
        cut_stats[name] = (stats_on(axis, base_daily, capital, keep),
                           stats_on(axis, hd, capital, keep))
    fold_stats = []
    for i in range(len(cell.legs)):
        h = merge(price_put(leg) for j, leg in enumerate(cell.legs) if j != i)
        fold_stats.append(M.path_stats(
            curve_of(axis, hedged_daily(axis, base_daily, h)), capital))

    per_year_all = {m: {y: improvement(b, h, m) for y, (b, h) in year_stats.items()}
                    for m in CO_PRIMARIES}
    cuts_all = {m: {k: improvement(b, h, m) for k, (b, h) in cut_stats.items()}
                for m in CO_PRIMARIES}
    loo_all = {m: [improvement(base, h, m) for h in fold_stats]
               for m in CO_PRIMARIES}

    # 3 — beats ARM N's 95th percentile on that same metric.
    p05, p95 = arm_n.get(metric, (None, None))
    out["arm_n_p95"] = p95
    out["arm_n_p05"] = p05
    out["c3"] = _finite(p95) and point > p95

    # 4 — positive in >= 2 of the book's years.
    per_year = per_year_all[metric]
    out["per_year"] = per_year
    out["c4"] = sum(1 for v in per_year.values() if v > 0) >= MIN_YEARS_POSITIVE

    # 5 — both ex-window cuts retain the sign.
    cuts = cuts_all[metric]
    out["cuts"] = cuts
    out["c5"] = bool(cuts) and all(v > 0 for v in cuts.values())

    # 6 — every leave-one-date-out fold retains the sign.
    folds = loo_all[metric]
    out["loo"] = folds
    out["c6"] = bool(folds) and all(v > 0 for v in folds)

    # 7 — NOT A DELTA REDUCTION IN DISGUISE.
    r_imp = arm_r_improvement.get(metric)
    out["arm_r"] = r_imp
    out["c7"] = _finite(r_imp) and point > r_imp

    out["candidate"] = all(out[f"c{i}"] for i in range(1, 8))
    out["point"] = point

    # --- the mirrored negative bar -----------------------------------------
    out["contrary"] = evaluate_contrary(
        base, hedged, cis,
        {m: arm_n.get(m, (None, None))[0] for m in CO_PRIMARIES},
        per_year_all, cuts_all, loo_all)
    return out


# ════════════════════════════════════════════════════════════════════════════
# ARM N — the random-admission null
# ════════════════════════════════════════════════════════════════════════════

def arm_n_band(eps, by_session, universe, axis, base_daily, capital, f: float,
               budget: float, rule: str, metrics, n_seeds: int = N_SEEDS,
               seed: int = SEED) -> dict:
    """Matched random hedging: same episode COUNT, same episode LENGTHS, same
    PROXY mix, random start sessions. `portfolio_delta`'s ARM N, applied to a
    path metric — an arm must beat this band's 95th percentile, not merely beat
    the unhedged book.

    Returns `{metric: (p05, p95)}`. BOTH tails are needed: the 95th is clause
    3's bar for a positive, and the 5th is clause 3''s bar for a CONTRARY, so
    a negative is held against the same null as a positive (errata F1)."""
    shape = []
    for ep in eps:
        sc = by_session[ep[0]]
        if sc.top_proxy is None or not sc.top_hedgeable:
            continue
        shape.append((len(ep), sc.top_proxy))
    uni = list(universe)
    draws: dict[str, list[float]] = {m: [] for m in metrics}
    if not shape or len(uni) < 2:
        return {m: (float("nan"), float("nan")) for m in metrics}
    rng = random.Random(seed)
    for _ in range(n_seeds):
        legs = []
        diag = dict(rolls=0, opens=0, sessions_no_fill=0, sessions_sub_one=0)
        for length, proxy in shape:
            if length > len(uni):
                continue
            start = rng.randrange(0, len(uni) - length + 1)
            legs.append(plan_episode(proxy, uni[start:start + length], f,
                                     budget, rule, diag, uni))
        hd = hedged_daily(axis, base_daily, merge(price_put(leg) for leg in legs))
        base = M.path_stats(curve_of(axis, base_daily), capital)
        hedged = M.path_stats(curve_of(axis, hd), capital)
        for m in metrics:
            draws[m].append(improvement(base, hedged, m))
    return {m: (pctile(v, 0.05), pctile(v, 0.95)) for m, v in draws.items()}


# ════════════════════════════════════════════════════════════════════════════
# Report sections
# ════════════════════════════════════════════════════════════════════════════

def print_stats_row(label: str, st: M.PathStats, base: M.PathStats | None = None,
                    note: str = "") -> None:
    d = ""
    if base is not None:
        d = (f"   dMaxDD {st.max_dd - base.max_dd:+9,.0f}"
             f"  dUlcer {base.ulcer - st.ulcer:+6.2f}"
             f"  dTUW {base.tuw - st.tuw:+6.3f}")
    tail = f"   [{note}]" if note else ""
    print(f"  {label:<34s} total ${st.total:>10,.0f}  maxDD ${st.max_dd:>10,.0f}"
          f"  ulcer {st.ulcer:6.2f}%  TUW {st.tuw:5.1%}"
          f"  worst ${st.worst_session:>9,.0f}{d}{tail}")


def cache_state() -> str:
    """`calendar_hedge` R4's scar: the nearest-strike rule RE-PICKS legs on a
    grown option cache, so the report must record the cache it ran against."""
    if not HISTORY_CACHE.exists():
        return f"{HISTORY_CACHE} MISSING"
    files = list(HISTORY_CACHE.glob("*.csv"))
    newest = max((p.stat().st_mtime for p in files), default=0.0)
    import datetime as _dt
    stamp = (_dt.datetime.fromtimestamp(newest).isoformat(timespec="seconds")
             if newest else "n/a")
    total = sum(p.stat().st_size for p in files)
    return (f"{len(files)} contract files, {total / 1e6:.0f} MB, "
            f"newest {stamp}  ({HISTORY_CACHE})")


# ════════════════════════════════════════════════════════════════════════════


def _population_recs(which: str) -> tuple[list[dict], dict]:
    """One of the two readings of the registration's population clause.

    `real` is the raw `BacktestResults` stratum every plan-time observation in
    the registration was computed on; `all` is the LITERAL
    `load_book(include_bs=False)` call the same clause names. Which rows each
    returns is a property of the exports on disk and is counted at run time —
    nothing here asserts a row or date total.
    """
    sources = {"real"} if which == POP_REAL else None
    return load_book(include_bs=False, sources=sources)


def check_mtm(bc: M.BookCurves) -> int:
    """G-MTM: print the reconciliation and return 0, or EXIT_MTM_RECONCILE.

    Extracted from `main` so the refusal can be exercised directly: the gate's
    whole defect (errata F2) was that it could not fail, so "it refuses on a
    mismatch" has to be a testable claim rather than a claim about a code path
    nothing reaches.
    """
    print(f"  positions {bc.n_positions}   reconciled {bc.n_reconciled}   "
          f"tolerance ${bc.tolerance:.2f} per contract   "
          f"worst mismatch ${bc.worst_mismatch:.4f}")
    print(f"  stale marks carried forward inside an open window: "
          f"{bc.n_carried_forward}")
    if bc.reconciles:
        print("  G-MTM PASS — daily_pnl_csv at the STORED exit index, times the "
              "row's contracts,\n  equals the row's STORED realized_pnl_abs. Two "
              "independent columns; neither\n  side is a replay of the other.")
        return 0
    print(f"\n  G-MTM FAILED — {len(bc.mismatches)} position(s) disagree:")
    for m in bc.mismatches[:20]:
        print(f"    {m.date} {m.ticker:<6s} {m.structure:<22s} x{m.contracts:<3d} "
              f"mtm ${m.mtm_at_exit:,.2f} booked ${m.booked:,.2f} "
              f"diff ${m.diff:,.2f}")
    print(f"\nG-MTM RECONCILIATION FAILURE. Exit {EXIT_MTM_RECONCILE}.")
    return EXIT_MTM_RECONCILE


def print_divergence(div: dict) -> None:
    """The replay-vs-stored disclosure that replaces the old self-comparison."""
    gap = div["replay_total"] - div["stored_total"]
    print(f"""
  DISCLOSED, gated on by nothing — how far the SHIPPED-profile replay lands
  from the stored outcome this curve is built on. The old G-MTM took BOTH the
  exit index and the booked dollars from this replay and then compared them to
  each other; the divergence it was hiding is:
    rows                                      {div['n_rows']}
    replayed days_held  != stored days_held   {div['n_days_held']}
    replayed exit_reason != stored exit_reason {div['n_exit_reason']}
    total dollars   stored ${div['stored_total']:,.0f}   replayed ${div['replay_total']:,.0f}   \
gap ${gap:+,.0f}
    sum of |per-row difference|               ${div['abs_gap']:,.0f}
  Every figure computed at run time from the export in the header.""")


def run_population(name: str, recs: list[dict], diag: dict, args, capital: float,
                   budget: float, cache: dict) -> dict:
    """Gates, cell shape and per-cell verdicts under ONE reading of the
    population clause. Returns a summary; prints everything.

    Emits NO study-level verdict — see `main`. Per ERRATUM 1 the population
    choice, not the data, decides what enters the evidence base here, so both
    readings are run and neither is concluded from until the operator ratifies
    one.
    """
    out: dict = dict(name=name, n_rows=len(recs),
                     n_dates=len({r["date"] for r in recs}),
                     refusal=0, counts={}, curves_differ=None,
                     clause2_survives=None, n_powered=0)

    hdr(f"POPULATION {name} — {POP_LABELS[name]}")
    dates = sorted({r["date"] for r in recs})
    by_source: dict[str, int] = defaultdict(int)
    for r in recs:
        by_source[r["source"]] += 1
    print(f"  rows {len(recs)}   signal dates {len(dates)}   "
          f"{dates[0] if dates else 'n/a'} .. {dates[-1] if dates else 'n/a'}")
    print("  pricing sources: " + "  ".join(
        f"{k} {v}" for k, v in sorted(by_source.items())))

    # ── G-MTM ───────────────────────────────────────────────────────────────
    positions = book_positions(recs)
    bc = M.book_curves(positions)
    hdr("G-MTM — the mark-to-market curve must reconcile to the STORED booked "
        "realized P&L")
    rc = check_mtm(bc)
    print_divergence(replay_divergence(recs, cache))
    if rc:
        out["refusal"] = rc
        return out

    axis = list(bc.mtm.sessions)
    base_daily = list(bc.mtm.daily)

    # ── ARM M ───────────────────────────────────────────────────────────────
    hdr("ARM M — MEASUREMENT: the SAME unhedged book on both curves")
    print("""  Every hedge verdict on record (bear_deploy D3, calendar_hedge H3,
  hedge_timing H4) rests on account_sim's close-bucketed curve, whose own
  print_equity says "Open positions are not marked to market, so this
  understates intra-position drawdown." A hedge's function is to cushion
  exactly the path that curve omits. ARM M measures the gap. It gates nothing.""")
    mtm_stats = M.path_stats(bc.mtm, capital)
    rea_stats = M.path_stats(bc.realized, capital)
    print()
    print_stats_row("mark-to-market (the basis)", mtm_stats)
    print_stats_row("realized-on-close (comparability)", rea_stats)
    curves_differ = (abs(mtm_stats.max_dd - rea_stats.max_dd) > 1.0
                     or abs(mtm_stats.ulcer - rea_stats.ulcer) > 0.1
                     or abs(mtm_stats.tuw - rea_stats.tuw) > 0.01)
    out["curves_differ"] = curves_differ
    print(f"\n  sessions {mtm_stats.n_sessions} (the curve's own weekday-grid axis; "
          f"the census below\n  reports the calendar reading the registration "
          f"disclosed)")
    print(f"  curves differ materially: {'YES' if curves_differ else 'no'}  "
          f"(thresholds $1 / 0.1 ulcer pt / 1 TUW pt — this module's, not "
          f"pre-registered)")
    print("""  This is a MEASUREMENT. The registration words a MEASUREMENT-ONLY
  verdict for it, and this run does not reach for that word: no study-level
  verdict is emitted under either population until one is ratified.""")

    # ── G-BLIND ─────────────────────────────────────────────────────────────
    hdr("G-BLIND — the trigger must be computable with outcome fields stripped")
    blind = C.blind_trigger_check(recs)
    print(f"  sessions {blind['n_sessions']}   triggered-set mismatches "
          f"{len(blind['trigger_set_mismatches'])}   stratum mismatches "
          f"{blind['stratum_mismatches']}   values match {blind['values_match']}")
    if not blind["identical"]:
        print("\n  LOOKAHEAD DETECTED — the concentration trigger moves when the "
              "outcome\n  columns are blinded. That is a defect in this module, "
              "not a designed\n  refusal, so it exits 1 and no report is promoted.")
        out["refusal"] = EXIT_LOOKAHEAD
        return out
    print("  G-BLIND PASS — occupancy is the replay fixture; every trigger input "
          "is entry-dated.")

    # ── G-CENSUS (before any outcome column is read) ─────────────────────────
    hdr("G-CENSUS — the power census, printed before any outcome column is read")
    census = C.census(recs)
    for line in C.census_lines(census):
        print(line)
    series = census["series"]
    by_session = {sc.session: sc for sc in series}
    universe = [sc.session for sc in series]
    hp, _hp_diag = C.hedge_pressure_by_date()

    print(f"""
  G-POWER CLUSTERING, fixed here before any outcome is read. The registration
  asks for ">= {MIN_TRIGGER_DATES} trigger DATES (date-clustered, not sessions)" but every
  session already IS one date, so the clustering is undefined. All three
  readings are printed above; this run is read against EPISODES — maximal runs
  of consecutive triggered sessions — which is the strictest of the three and
  treats one concentrated stretch as one occasion rather than N. It is fixed
  now and not revisited after any outcome.""")

    # ── G-FILL ──────────────────────────────────────────────────────────────
    hdr("G-FILL — a hedge must be fillable on >=60% of triggered sessions "
        "(band rule)")
    print("""  An unfillable session is CARRIED AT f=0 and stays in the denominator, per
  calendar_hedge's standing principle that a hedge unavailable exactly when
  needed is not a hedge. An UNHEDGEABLE cluster keeps its proxy identity and
  counts against the gate; it is never folded into BROAD/SPY.""")
    fill: dict[float, dict] = {}
    for tau in TAU_GRID:
        trig = C.triggered_sessions(series, tau)
        pairs = [(s, by_session[s].top_proxy) for s in trig
                 if by_session[s].top_proxy]
        table = HI.coverage_table(pairs)
        fill[tau] = table
        b, n = table[HI.RULE_BAND], table[HI.RULE_NEAREST]
        print(f"\n  tau {tau:.2f}   triggered sessions {len(trig)}"
              f"   band {b.filled}/{b.n} = {b.rate:.1%}"
              f"   {'PASS' if b.passes() else 'FAIL'}"
              f"   nearest {n.rate:.1%}")
        print("    per proxy (band):  " + "  ".join(
            f"{k} {v[0]}/{v[1]}" for k, v in b.by_proxy.items()))
        print("    unfilled because:  " + "  ".join(
            f"{k}={v}" for k, v in b.by_reason.items() if k != HI.FILLED))
    gate_ok = {tau: fill[tau][args.rule].passes() for tau in TAU_GRID}
    if not any(gate_ok.values()):
        print("\n  G-FILL FAILS AT EVERY TAU — the proxy-put arms are NOT "
              "EVALUABLE (not failed).\n  Only ARM R is read below and it may "
              "not be quoted as evidence about puts.")

    # ── the cells ───────────────────────────────────────────────────────────
    hdr("ARM C — concentration-gated proxy put   (3 tau x 3 f = 9 cells, "
        "Bonferroni alpha = 0.05/9)")
    longest = max(len(e) for e in C.episodes(
        C.triggered_sessions(series, TAU_GRID[0]), universe))
    print(f"""  A hedge is opened on the first session of a trigger EPISODE, held while
  concentration stays >= tau, and ROLLED when the put expires inside the
  episode (settled at expiry intrinsic against that day's close). Rolling is
  not pre-registered: episodes run to {longest} sessions and a 25-75 DTE put
  cannot span that, so the alternative would be an unpriced hedge, not a
  longer one.

  HOLDING WINDOW, not pre-registered: the hedge is carried to the close of the
  session AFTER the episode ends. An instrument opened and closed on the same
  mark contributes exactly zero, and every ARM CS episode here is one session
  long, so without it those arms would print an identical curve to f=0 for an
  arithmetic reason rather than an economic one.

  SIZING, the inherited fix stated explicitly: contracts = int(f x
  risk_contracts(put debit, ${budget:,.0f})). A hedge that rounds below one contract is
  SKIPPED (account_sim ARM H's convention, which dropped 61 of 132 candidates
  there) and its session is carried at f=0. It is NOT floored to 1 — that
  defect is what the registration told this module to inherit-fix.

  alpha = {ALPHA:.5f} two-sided; CI percentiles {100 * ALPHA / 2:.2f} / {100 * (1 - ALPHA / 2):.2f}.""")

    cells: dict[tuple, Cell] = {}
    arm_r: dict[tuple, dict] = {}
    arm_rf: dict[tuple, dict] = {}
    for tau in TAU_GRID:
        trig = C.triggered_sessions(series, tau)
        eps = C.episodes(trig, universe)
        counts = C.trigger_date_counts(trig, series, recs)
        for f in F_GRID:
            cell = build_cell("C", tau, f, args.rule, trig, eps, by_session,
                              budget, universe)
            cell.n_book_dates = counts["book_dates"]
            cells[(tau, f)] = cell
            rdiag = dict(no_entry_delta=0)
            arm_r[(tau, f)] = dict(
                hedge=merge(price_delta_short(leg, rdiag) for leg in cell.legs),
                diag=rdiag)
            fdiag = dict(no_bar=0)
            rf = []
            for ep in eps:
                sc = by_session[ep[0]]
                if sc.top_proxy is None or not sc.top_hedgeable:
                    continue
                cl = next((c for c in sc.clusters if c.name == sc.top_cluster),
                          None)
                if cl is None:
                    continue
                rf.append(price_cluster_short(sc.top_proxy, ep, cl.net, f,
                                              fdiag, universe))
            arm_rf[(tau, f)] = dict(hedge=merge(rf), diag=fdiag)

    sub("cell shape (no outcome read yet)")
    print("   tau     f   episodes  book_dates  legs  opens  rolls  no-fill  "
          "sub-1c  unhedgeable-ep    debit$   peak$  peak/cap")
    for (tau, f), cell in cells.items():
        d = cell.diag
        pk = peak_debit(cell.legs)
        print(f"  {tau:.2f}  {f:.2f}   {cell.n_episodes:8d}  "
              f"{cell.n_book_dates:10d}  {len(cell.legs):4d}  {d['opens']:5d}  "
              f"{d['rolls']:5d}  {d['sessions_no_fill']:7d}  "
              f"{d['sessions_sub_one']:6d}  {d['unhedgeable_episodes']:14d}  "
              f"{sum(leg.cost for leg in cell.legs):9,.0f}  {pk:6,.0f}  "
              f"{pk / capital:7.1%}")
    print(f"""
  The f grid is largely UNREACHABLE on a ${budget:,.0f} risk budget: a proxy put's debit
  is typically several hundred dollars, so risk_contracts() returns 1 and
  int(0.25 x 1) = int(0.50 x 1) = 0. Those cells are carried at f=0 by the SKIP
  convention above and are reported, not hidden — a cell with no hedge in it
  cannot clear the bar and is not evidence about hedging.""")

    # ── outcome per cell ────────────────────────────────────────────────────
    sub("path metrics per cell — mark-to-market curve, unhedged baseline first")
    print_stats_row("f = 0 (unhedged)", mtm_stats)
    results: dict[tuple, dict] = {}
    for (tau, f), cell in cells.items():
        if not cell.legs:
            cell.verdict = "NO HEDGE PLACED"
            continue
        hd = hedged_daily(axis, base_daily, cell.hedge)
        stt = M.path_stats(curve_of(axis, hd), capital)
        cell.stats = stt
        print_stats_row(f"ARM C tau {tau:.2f} f {f:.2f}", stt, mtm_stats)

    sub("ARM R — always-fillable reference (delta-matched short in the proxy)")
    print(f"""  {ARM_R_CAVEAT}

  Printed here, immediately above its own rows, because study_review and every
  paste-the-report path read THIS file rather than research/arm-index.md.""")
    print()
    for (tau, f) in cells:
        h = arm_r[(tau, f)]["hedge"]
        if h:
            stt = M.path_stats(curve_of(axis, hedged_daily(axis, base_daily, h)),
                               capital)
            print_stats_row(f"ARM R tau {tau:.2f} f {f:.2f} (delta-matched)",
                            stt, mtm_stats)

    sub(f"ARM RF — {ARM_RF_LABEL}")
    print(f"""  {ARM_RF_LABEL}. ARM RF is NOT in
  research/pre-registrations/f4_deployment/hedge_exposure.md. It is this
  module's own fill-INDEPENDENT floor — short fraction f of the concentrated
  cluster's own signed delta notional in the proxy underlying — added because
  the registration's ARM R is delta-matched to ARM C's put and therefore
  depends on the option cache ARM R exists to be free of.

  It prints the largest positive numbers in this report and NO clause of the
  bar is read from it. Every row below carries the label.""")
    print()
    for (tau, f) in cells:
        h = arm_rf[(tau, f)]["hedge"]
        if h:
            stt = M.path_stats(curve_of(axis, hedged_daily(axis, base_daily, h)),
                               capital)
            print_stats_row(f"ARM RF tau {tau:.2f} f {f:.2f} (cluster short)",
                            stt, mtm_stats, note=ARM_RF_LABEL)

    # ── ARM B ───────────────────────────────────────────────────────────────
    hdr("ARM B — instrument comparison: the book's own bear row instead of the put")
    print("""  bear_deploy D3 and hedge_timing H4 both found the sleeve cannot cut max
  drawdown on the close-bucketed curve. This arm asks ONLY whether that survives
  the move to a mark-to-market curve. It cannot remove the §4 sleeve, which is
  operator policy.""")
    bear_by_date: dict[str, list] = defaultdict(list)
    for r in recs:
        if r["structure"] in A.BEAR_DEBIT and not r["credit"]:
            bear_by_date[r["date"]].append(r)
    arm_b: dict[tuple, dict] = {}
    for tau in TAU_GRID:
        trig = C.triggered_sessions(series, tau)
        eps = C.episodes(trig, universe)
        for f in F_GRID:
            parts, placed, none_avail, sub_one = [], 0, 0, 0
            for ep in eps:
                rec = None
                for day in ep:
                    cands = bear_by_date.get(day.isoformat())
                    if cands:
                        rec = max(cands, key=lambda r: abs(r["delta"])
                                  if r.get("delta") is not None else -1.0)
                        break
                if rec is None:
                    none_avail += 1
                    continue
                c = _contracts_for(rec["max_loss_per_contract"], f, budget)
                if c < 1:
                    sub_one += 1
                    continue
                parts.append(price_bear_row(rec, c, budget, cache))
                placed += 1
            arm_b[(tau, f)] = dict(hedge=merge(parts), placed=placed,
                                   none_avail=none_avail, sub_one=sub_one,
                                   episodes=len(eps))
    print("\n   tau     f  episodes  placed  no-bear-row  sub-1c")
    for (tau, f), d in arm_b.items():
        print(f"  {tau:.2f}  {f:.2f}  {d['episodes']:8d}  {d['placed']:6d}  "
              f"{d['none_avail']:11d}  {d['sub_one']:6d}")
    print()
    for (tau, f), d in arm_b.items():
        if not d["hedge"]:
            continue
        stt = M.path_stats(curve_of(axis, hedged_daily(axis, base_daily,
                                                       d["hedge"])), capital)
        print_stats_row(f"ARM B tau {tau:.2f} f {f:.2f}", stt, mtm_stats)

    # ── ARM CS / ARM P ──────────────────────────────────────────────────────
    hdr("ARM CS — concentration x hedge-flow signal   ·   ARM P — INERT AS "
        "REGISTERED")
    print(f"""  ARM CS additionally requires `hedge-pressure >= {HEDGE_PRESSURE_CUT}` parsed from the
  analysis `regime` prose. A date with NO parse is NO SIGNAL (do not hedge) —
  the conservative direction, fixed at registration.

  LOOKAHEAD, irreducible: every AnalysisClaude row was written in 2026-08,
  including rows for 2024 sessions, by a model whose training cutoff overlaps
  them. A hedge-pressure score may be recall rather than a read of that day's
  tape.

  ARM P IS INERT AS REGISTERED (errata, ERRATUM 2). The registration defines it
  as "ARM C restricted to exactly the sessions ARM CS would hedge on, minus the
  prose condition". Restricting to ARM CS's session set and then removing the
  prose condition yields ARM CS's session set: the two arms carry BYTE-IDENTICAL
  hedges and differ only in what is claimed to have justified them. This module
  implements that literally (`p_trig = list(cs_trig)`) and does NOT redefine it
  — a redefinition would be a post-hoc arm.

  The consequence is stated rather than worked around: the study's ONLY control
  on the model-recall lookahead above DOES NOT EXIST, and the registration's
  binding prose rule — "no verdict may rest on ARM CS alone", whose remedy is
  the verdict PROSE-CONDITIONED, LOOKAHEAD-UNRESOLVED — IS UNREACHABLE BY
  CONSTRUCTION. It does not bite this run, because ARM CS is power-stopped at
  every tau below, but it would on a powered window. A corrected control (ARM C
  on concentration-matched sessions carrying NO hedge-pressure signal) needs its
  own registration and is out of scope here.""")
    arm_cs: dict[tuple, Cell] = {}
    arm_p: dict[tuple, Cell] = {}
    print("\n   tau     f  CS sessions  CS episodes  power   P sessions  P episodes")
    for tau in TAU_GRID:
        cs_trig = C.triggered_sessions(series, tau, hedge_pressure=hp)
        cs_eps = C.episodes(cs_trig, universe)
        # ARM P: the SAME sessions, reached without the prose — by construction
        # the identical set. Left literal on purpose; see the note above.
        p_trig = list(cs_trig)
        p_eps = C.episodes(p_trig, universe)
        for f in F_GRID:
            cs = build_cell("CS", tau, f, args.rule, cs_trig, cs_eps,
                            by_session, budget, universe)
            pp = build_cell("P", tau, f, args.rule, p_trig, p_eps,
                            by_session, budget, universe)
            arm_cs[(tau, f)] = cs
            arm_p[(tau, f)] = pp
        print(f"  {tau:.2f}   all  {len(cs_trig):11d}  {len(cs_eps):11d}  "
              f"{'ok' if len(cs_eps) >= MIN_TRIGGER_DATES else 'UNDERPOWERED':<12s} "
              f"{len(p_trig):10d}  {len(p_eps):10d}")
    identical = all(arm_p[k].hedge == arm_cs[k].hedge for k in arm_cs)
    print(f"\n  ARM P's hedges are byte-identical to ARM CS's in every cell: "
          f"{'YES' if identical else 'no'} — the inertness above, measured.")
    for (tau, f), cs in arm_cs.items():
        if not cs.legs:
            continue
        stt = M.path_stats(curve_of(axis, hedged_daily(axis, base_daily,
                                                       cs.hedge)), capital)
        print_stats_row(f"ARM CS tau {tau:.2f} f {f:.2f}", stt, mtm_stats)

    # ── the bar ─────────────────────────────────────────────────────────────
    hdr("BAR FOR A CANDIDATE — all seven clauses, per powered cell")
    print(f"""  1  max drawdown AND worst single session both no worse than f=0 (dollars)
  2  a co-primary (Ulcer or time-under-water) with a date-clustered CI
     excluding zero at Bonferroni alpha = 0.05/9 = {ALPHA:.5f}
  3  beats ARM N's 95th percentile on that same metric ({args.seeds} seeds)
  4  positive in >= {MIN_YEARS_POSITIVE} of the book's years
  5  both ex-window cuts (protocol.DOMINANT_WINDOWS) retain the sign
  6  every leave-one-date-out fold retains the sign
  7  exceeds ARM R's improvement at the same tau and f — a cell that merely
     matches it is A RESTATEMENT OF DELTA REDUCTION and does not clear the bar

  AND THE MIRROR (errata F1): a CONTRARY needs clauses 1'-6' — drawdown
  strictly worse, a co-primary CI entirely BELOW zero at the same alpha, worse
  than ARM N's 5th percentile, negative in >= {MIN_YEARS_POSITIVE} years, both ex-window cuts
  negative and every leave-one-out fold negative. Short of that a cell is NULL.
  A negative used to need no clause at all.

  Bootstrap: {args.boot} resamples, CHRONOLOGICAL moving block of {block_length(axis)} sessions
  (the median calendar-month cluster), paired. Errata F5 withdrew the
  month-shuffle estimator: it concatenated resampled months IN DRAWN ORDER and
  then computed PATH-DEPENDENT statistics on the reordered series, so month
  order was part of the statistic and the interval was not its sampling
  distribution. The withdrawn estimator is still printed per cell, so this
  report can say whether clause 2's outcome survived the change.""")

    verdict_cells = []
    clause2_flips = 0
    for (tau, f), cell in cells.items():
        band_ok = fill[tau][args.rule].passes()
        sub(f"cell tau {tau:.2f}  f {f:.2f}")
        if not band_ok:
            cell.verdict = "NOT EVALUABLE"
            print(f"  G-FILL {fill[tau][args.rule].rate:.1%} < {FILL_GATE:.0%} "
                  f"— NOT EVALUABLE (not failed). Only ARM R is read.")
            verdict_cells.append(cell)
            continue
        if not cell.powered:
            cell.verdict = "UNDERPOWERED"
            print(f"  {cell.n_episodes} trigger dates (episodes) < "
                  f"{MIN_TRIGGER_DATES} — UNDERPOWERED. No direction is quoted. "
                  f"UNDERPOWERED is not a lean.")
            verdict_cells.append(cell)
            continue
        if not cell.legs:
            cell.verdict = "NO HEDGE PLACED"
            print(f"  no hedge was placed in this cell — every episode was "
                  f"unhedgeable, unfilled, or sized below one contract "
                  f"(sub-1c {cell.diag['sessions_sub_one']}). "
                  f"Nothing to evaluate; not evidence about hedging.")
            verdict_cells.append(cell)
            continue
        eps = C.episodes(C.triggered_sessions(series, tau), universe)
        band = arm_n_band(eps, by_session, universe, axis, base_daily, capital,
                          f, budget, args.rule, CO_PRIMARIES,
                          n_seeds=args.seeds)
        rimp = {}
        rh = arm_r[(tau, f)]["hedge"]
        if rh:
            rst = M.path_stats(curve_of(axis, hedged_daily(axis, base_daily, rh)),
                               capital)
            rimp = {m: improvement(mtm_stats, rst, m) for m in CO_PRIMARIES}
        res = evaluate_bar(cell, axis, base_daily, capital, band, rimp,
                           args.boot)
        results[(tau, f)] = res
        cell.clauses = res
        out["n_powered"] += 1
        m = res["metric"]
        pt = res["ci"][m][0]
        print(f"  metric read: {m}")
        print(f"  1 maxDD/worst-session no worse   {'PASS' if res['c1'] else 'FAIL'}"
              f"   dMaxDD ${res['hedged'].max_dd - res['base'].max_dd:+,.0f}"
              f"   dWorst ${res['hedged'].worst_session - res['base'].worst_session:+,.0f}")
        for mm in CO_PRIMARIES:
            p2, l2, h2 = res["ci"][mm]
            print(f"  2 {mm:<6s} improvement {p2:+.4f}   CI[{l2:+.4f}, {h2:+.4f}]"
                  f"   {'excludes 0' if (_finite(l2) and (l2 > 0 or h2 < 0)) else 'includes 0'}")
        print(f"  2 verdict                        {'PASS' if res['c2'] else 'FAIL'}")
        for mm in CO_PRIMARIES:
            p2, l2, h2 = res["ci_withdrawn"][mm]
            print(f"    withdrawn month-shuffle {mm:<6s} {p2:+.4f}   "
                  f"CI[{l2:+.4f}, {h2:+.4f}]  (diagnostic; no clause read from it)")
        if res["c2"] != res["c2_withdrawn"]:
            clause2_flips += 1
        print(f"    clause 2 under the withdrawn estimator: "
              f"{'PASS' if res['c2_withdrawn'] else 'FAIL'} — "
              f"{'SAME as the chronological one' if res['c2'] == res['c2_withdrawn'] else 'DIFFERENT'}")
        print(f"  3 beats ARM N p95                {'PASS' if res['c3'] else 'FAIL'}"
              f"   arm {pt:+.4f} vs null p95 {_num(res['arm_n_p95'])}")
        print(f"  4 years positive                 {'PASS' if res['c4'] else 'FAIL'}"
              f"   " + "  ".join(f"{y}:{v:+.4f}" for y, v in res["per_year"].items()))
        print(f"  5 ex-window cuts                 {'PASS' if res['c5'] else 'FAIL'}"
              f"   " + "  ".join(f"{k}:{v:+.4f}" for k, v in res["cuts"].items()))
        loo = res["loo"]
        print(f"  6 leave-one-date-out             {'PASS' if res['c6'] else 'FAIL'}"
              f"   {sum(1 for v in loo if v > 0)}/{len(loo)} folds keep the sign"
              + (f"   worst {min(loo):+.4f}" if loo else ""))
        print(f"  7 exceeds ARM R (not delta in disguise)  "
              f"{'PASS' if res['c7'] else 'FAIL'}   ARM R {_num(res['arm_r'])}")
        neg = res["contrary"]
        print(f"  CONTRARY mirror                  "
              f"{'MET' if neg['contrary'] else 'not met'}   "
              f"1' maxDD worse {'Y' if neg['n1'] else 'n'}"
              f"  2' CI below 0 {'Y' if neg['n2'] else 'n'}"
              f"  3' under ARM N p05 {'Y' if neg['n3'] else 'n'}"
              f"  4' years {'Y' if neg['n4'] else 'n'}"
              f"  5' cuts {'Y' if neg['n5'] else 'n'}"
              f"  6' folds {'Y' if neg['n6'] else 'n'}"
              + (f"   (metric {neg['metric']}, ARM N p05 {_num(neg['arm_n_p05'])})"
                 if neg["metric"] else "   (no co-primary CI lies below zero)"))
        cell.verdict = cell_verdict(res)
        print(f"  => {cell.verdict}")
        verdict_cells.append(cell)

    if out["n_powered"]:
        out["clause2_survives"] = (clause2_flips == 0)
        print(f"""
  CLAUSE 2 UNDER THE ESTIMATOR CHANGE (errata F5): {out['n_powered']} powered cell(s);
  clause 2's PASS/FAIL differs between the chronological moving block and the
  withdrawn month-shuffle in {clause2_flips} of them. Clause 2's outcome therefore
  {'SURVIVES' if clause2_flips == 0 else 'DOES NOT SURVIVE'} the replacement.""")

    # ── sensitivity: the nearest-available rule ─────────────────────────────
    other = HI.RULE_NEAREST if args.rule == HI.RULE_BAND else HI.RULE_BAND
    hdr(f"REGISTERED SENSITIVITY — the {other} fill rule, same taus and f grid")
    print(f"""  Both fill rules are pre-registered because coverage is not uniform in time
  (band-rule SMH and QQQ collapse in 2025Q3/Q4). The {other} rule RE-PICKS legs
  on a grown option cache — calendar_hedge R4's scar — so the cache state is in
  the header above. Reported for shape only; no verdict is read from it.""")
    print()
    print_stats_row("f = 0 (unhedged)", mtm_stats)
    for tau in TAU_GRID:
        trig = C.triggered_sessions(series, tau)
        eps = C.episodes(trig, universe)
        for f in F_GRID:
            c2 = build_cell("C", tau, f, other, trig, eps, by_session, budget,
                            universe)
            if not c2.legs or not c2.hedge:
                continue
            stt = M.path_stats(curve_of(axis, hedged_daily(axis, base_daily,
                                                           c2.hedge)), capital)
            print_stats_row(f"ARM C[{other}] tau {tau:.2f} f {f:.2f}", stt,
                            mtm_stats)

    # ── the asymmetric reading rule ─────────────────────────────────────────
    hdr("DIRECT vs CONSTITUENT — the binding asymmetric reading rule")
    print("""  Results are always stratified. A positive result in the DIRECT stratum — a
  put on an ETF the book already HOLDS — may NEVER be cited as evidence for the
  operator's constituent-to-sector-proxy practice: it is a different action. A
  NULL in DIRECT is likewise not evidence against the constituent practice.

  The book is not shaped like the practice being tested — most of its exposure
  is DIRECT — and the pre-registration disclosed at plan time that the
  constituent stratum would be power-stopped. The census above confirms it at
  every tau.""")
    print("\n   tau  stratum        sessions  episodes  power")
    for tau in TAU_GRID:
        for strat in (S.DIRECT, S.CONSTITUENT):
            t = C.triggered_sessions(series, tau, stratum=strat)
            e = C.episodes(t, universe)
            print(f"  {tau:.2f}  {strat:<12s} {len(t):9d}  {len(e):8d}  "
                  f"{'ok' if len(e) >= MIN_TRIGGER_DATES else 'UNDERPOWERED'}")
    for tau in TAU_GRID:
        t = C.triggered_sessions(series, tau, measure=C.MEASURE_CONSTITUENT)
        e = C.episodes(t, universe)
        print(f"  {tau:.2f}  constituent-measure, all strata: {len(t)} sessions / "
              f"{len(e)} episodes — "
              f"{'ok' if len(e) >= MIN_TRIGGER_DATES else 'UNDERPOWERED (as predicted at plan time)'}")

    # ── this population's cell tally — NOT a verdict ────────────────────────
    hdr(f"CELL TALLY — population {name}   (no verdict is read from it)")
    counts: dict[str, int] = defaultdict(int)
    for cell in verdict_cells:
        counts[cell.verdict] += 1
    for k in sorted(counts):
        print(f"  {k:<18s} {counts[k]} cell(s)")
    out["counts"] = dict(counts)
    out["gate_ok"] = dict(gate_ok)
    print("""
  Cell-level words only. The registration's study-level verdicts
  (MECHANISM-FOUND / NULL / CONTRARY / UNDERPOWERED / NOT EVALUABLE /
  MEASUREMENT-ONLY) are NOT emitted by this run under either population — see
  the closing section.""")
    return out


# ════════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rule", choices=HI.RULES, default=HI.RULE_BAND,
                    help="fill rule for the proxy put. `band` is the "
                         "pre-registered primary; `nearest` is the registered "
                         "sensitivity and is also printed by default.")
    ap.add_argument("--sources", choices=(POP_BOTH, POP_REAL, POP_ALL),
                    default=POP_BOTH,
                    help="which reading of the registration's population "
                         "clause to run. `both` (the default, and what the "
                         "errata requires) runs the raw BacktestResults "
                         "stratum AND the literal load_book(include_bs=False) "
                         "call, and concludes from neither.")
    ap.add_argument("--seeds", type=int, default=N_SEEDS,
                    help=f"ARM N seeds (registered: {N_SEEDS})")
    ap.add_argument("--boot", type=int, default=BOOT_N,
                    help=f"block-bootstrap resamples per cell (default {BOOT_N})")
    args = ap.parse_args()

    st = A.load_settings()
    capital = st.capital
    budget = st.budget

    # ── G-ERA ───────────────────────────────────────────────────────────────
    wanted = ([POP_REAL, POP_ALL] if args.sources == POP_BOTH
              else [args.sources])
    books = {w: _population_recs(w) for w in wanted}
    era = next(iter(books.values()))[1]["era"]

    hdr("hedge_exposure — does concentration-triggered proxy hedging cut the "
        "book's drawdown?")
    shapes = "\n".join(
        f"    {w:<5s} {POP_LABELS[w]:<58s} {len(recs):4d} rows / "
        f"{len({r['date'] for r in recs})} signal dates"
        for w, (recs, _d) in books.items())
    print(f"""  era {era} (G-ERA: v4 only; a mismatch refuses exit 3, a thin era exit 2)
  config {st.source.name}: capital ${capital:,.0f}, risk {st.risk_pct:.0%} = ${budget:,.0f}
         per position on a MAX-LOSS basis — the "standard position's risk" the
         f grid is a fraction OF.
  option cache: {cache_state()}
  primary fill rule: {args.rule}   (nearest-available printed as the registered sensitivity)

  POPULATION — REPORTED BOTH WAYS, CONCLUDED FROM NEITHER.
  The pre-registration's "Population and basis" clause is self-contradictory
  (recorded as ERRATUM 1 in research/hedge-exposure-errata.md, because a
  committed file never changes meaning after it is written). It names
  `load_book(include_bs=False)` AND states a row/date count that only the raw
  BacktestResults stratum matches. On disk those are different books:

{shapes}

  The choice is LOAD-BEARING, not cosmetic — it decides how many cells are
  powered and therefore what could enter the evidence base at all. So this run
  prints the gates, the cell shape and the cell-level words under BOTH
  readings, with every count computed at run time, and emits NO study-level
  verdict. Nothing is written to study_map/catalog.py, research/study-map.md or
  research/study-results/ until the operator ratifies a reading. The earlier
  unilateral default to the real stratum is WITHDRAWN.

  BASIS — the whole book at its OWN contract counts, on its OWN STORED
  outcome (days_held and realized_pnl_abs off the row, not off a replay; see
  book_positions and G-MTM below). `account-sim.yml` supplies the SIZING basis
  the hedge is a fraction of, which is the role the registration's sizing
  bullet gives it. The hedge is NOT routed through `account_sim.admission()`:
  there is no ledger on this basis. Its cash and exposure footprint is reported
  instead — see ARM C.

  BASELINE CAVEAT — the max drawdown printed here is the WHOLE book at its own
  contract counts. It is not `account_sim`'s admitted-subset figure and the two
  are not comparable; no number here restates the -$10,968 this study was
  queued against.

  NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF. No annualised
  figure, Sharpe or time-to-recover appears anywhere in this report.""")

    cache = A.new_cache()

    # ── the sector map, quoted as the registration requires ─────────────────
    hdr("SECTOR MAP — fixed in the pre-registration before any concentration "
        "was computed")
    for line in S.census_lines():
        print(line)
    withheld = S.rescale_withheld_proxies()
    print(f"\n  run-time confirmation: proxies on underlying.rescaled_tickers() "
          f"today = {sorted(withheld) or 'none'}")
    print("  (diagnostic only — UNHEDGEABLE is a committed constant and is "
          "never recomputed from it)")

    summaries = []
    for w in wanted:
        recs, pdiag = books[w]
        summaries.append(run_population(w, recs, pdiag, args, capital, budget,
                                        cache))

    # ── the closing section: no study-level verdict ─────────────────────────
    hdr("RESULT — NO STUDY-LEVEL VERDICT IS EMITTED")
    for s in summaries:
        tally = ("  ".join(f"{k} {v}" for k, v in sorted(s["counts"].items()))
                 or "none")
        print(f"\n  population {s['name']} — {POP_LABELS[s['name']]}")
        print(f"    {s['n_rows']} rows / {s['n_dates']} signal dates")
        if s["refusal"]:
            print(f"    REFUSED at a gate, exit {s['refusal']} — no cells read")
            continue
        print(f"    powered cells {s['n_powered']}   cell words: {tally}")
        print(f"    ARM M curves differ materially: "
              f"{'YES' if s['curves_differ'] else 'no'}")
        if s["clause2_survives"] is not None:
            print(f"    clause 2's outcome survives the F5 estimator change: "
                  f"{'YES' if s['clause2_survives'] else 'NO'}")
    print("""
  Both populations are reported. NEITHER is concluded from. Per ERRATUM 1 the
  population clause of the pre-registration is self-contradictory and the
  choice between its two readings decides what is powered, so a study-level
  verdict here would be a choice dressed as a finding. No word from the
  registration's verdict vocabulary is emitted, the research/study-results/
  record for this run carries a BLANK verdict field, and the catalog entry
  stays unconcluded until the operator ratifies one reading.

  ARM P IS INERT AS REGISTERED and the registration's binding prose rule is
  UNREACHABLE BY CONSTRUCTION (ERRATUM 2). ARM P has not been redefined into
  something informative — that would be a post-hoc arm.

  ARM RF IS UNREGISTERED — ADDED AFTER COMMIT, and no clause of the bar is read
  from it.

  NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF. A MECHANISM-FOUND
  verdict would produce a DRAFTED amendment to docs/deployment-rules.md §4 held
  in research/, never an edit; a NULL or CONTRARY verdict would ship nothing and
  be recorded in research/deployment-evidence.md as closing the queued
  max-drawdown question. Neither is claimed here. The §4 sleeve is operator
  policy and is not removed by any outcome.""")

    refusal = next((s["refusal"] for s in summaries if s["refusal"]), 0)
    return refusal


if __name__ == "__main__":
    sys.exit(main())
