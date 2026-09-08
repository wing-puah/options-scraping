"""HEDGE-EXPOSURE arm — does concentration-triggered proxy hedging cut the book's drawdown?

Pre-registered 2026-08-29. Registration:
`research/pre-registrations/f5_hedging/hedge_portfolio.md`, where
`scripts/study_review/` reads it. Read it before quoting anything printed here.

The operator's described practice is exposure-conditional: *"I hedge when I hold
a lot of correlated positions (semis -> SMH, tech -> QQQ), I see a specific
risk, AND the analysis says people are hedging."* This module asks whether that,
made mechanical, reduces the book's MARK-TO-MARKET drawdown versus carrying the
same concentrated book unhedged.

What this is NOT: not a timing study (`hedge_timing` returned 0 of 9 and no arm
here is keyed to a calendar or market state); not a selection study (`hedge_sizing`
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
          of a standard position's risk. The concentrated cluster and its proxy
          are re-picked EACH SESSION; an unhedgeable session is carried at f=0
          and stays in the denominator. Carries no prose.
  ARM CS  ARM C additionally requiring `hedge-pressure >= 50` in the analysis
          prose. PROSE-CONDITIONED.
  ARM P   ARM C on exactly ARM CS's session set, minus the prose condition —
          which is ARM CS's session set. INERT AS REGISTERED (ERRATUM 2), left
          literal rather than redefined, and the registration's binding prose
          rule is therefore unreachable by construction.
  ARM N   Random-admission null, 200 seeds. Clause 3 is read from the RICH
          match — episode COUNT, episode LENGTHS and the per-session PROXY
          SEQUENCE — which is conservative but is NOT what the registration
          commits; the REGISTERED match (count and date-clustering only) is
          computed and printed beside it as the registered estimator. An arm
          must beat the 95th percentile; a CONTRARY must fall below the 5th.
  ARM B   Instrument comparison — the book's own bear row instead of the put.
  ARM R   Always-fillable reference — a delta-equivalent SHORT in the proxy
          underlying. Clause 7's control: a put that merely matches it is A
          RESTATEMENT OF DELTA REDUCTION. A floor on feasibility, NOT a
          recommendation.
  ARM RF  UNREGISTERED — ADDED AFTER COMMIT. ARM R's fill-independent floor,
          sized off the concentrated cluster's own net delta notional. Every
          row of it carries that label and no clause is read from it.

POPULATION: the registration's population clause originally named two
different books (ERRATUM 1). The OPERATOR ratified one on 2026-08-31 — the
literal `load_book(include_bs=False)` call — and the "Population and basis"
section of the pre-registration itself (consolidated 2026-09-02), not this
module, is the authority for it.
Both readings are still run and printed with every count computed at run time;
`real` is reported as a STRATUM, never a co-primary, and the study-level
verdict is read off the ratified population alone.

RESULT: UNDERPOWERED over the mechanism question (every cell fails G-POWER on
the ratified population) AND MEASUREMENT-ONLY over ARM M (which is not
power-gated, so it is readable when the cells are not). Two words over two
different objects; the registration defines both and orders neither.

STRATIFICATION IS COMPUTATION, not a count table: the registration's binding
asymmetric reading rule ("Results are always stratified DIRECT versus
CONSTITUENT") means every cell carries a full clause set — path metrics,
bootstrap CI, ARM N band, all seven clauses — under DIRECT, under CONSTITUENT
and POOLED, each power-gated on its own episode count and the pooled row
labelled POOLED. A DIRECT result may never be cited for the constituent
practice.

Every choice this module made that the registration does NOT commit is listed
in ONE place in the report, under NOT PRE-REGISTERED, with the clause each one
feeds.

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
    python -m scripts.backtest_study run hedge_portfolio
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest_study.f4_deployment import account_sim as A  # noqa: E402
from scripts.backtest_study.lib import concentration as C  # noqa: E402
from scripts.backtest_study.lib import forward_drawdown as F  # noqa: E402
from scripts.backtest_study.lib import hedge_instrument as HI  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as M  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import sectors as S  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# 2 and 3 belong to lib/era.py's thin-era and era-mismatch refusals; this study
# numbers from 4. A LITERAL set: run.py::_refusal_codes parses it with `ast` and
# never imports the module, so an alias or a frozenset() call is invisible to it.
#   4 = G-MTM, the curve reconciliation — BOTH arms, the same gate on the same
#       curve, which is why the admitted arm never restates it
#   5 = G-ADMIT, the ADMITTED arm's own: its book must BE account_sim's
# The set is the UNION of the two arms', because the runner reads ONE
# declaration per module. 5 is unreachable on the whole-book arm, which has no
# admission model to drift.
EXIT_MTM_RECONCILE = 4
DESIGNED_REFUSAL_EXIT_CODES = {2, 3, 4, 5}

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

# ── the ratified reading (OPERATOR, 2026-08-31) ─────────────────────────────
# ERRATUM 1's deadlock was resolved by the operator, NOT by this module, and
# both the decision and its reasoning are recorded in the pre-registration's
# own Population and basis section (consolidated there 2026-09-02; formerly a
# separate errata file, now deleted). This module cites that decision; it does
# not make it, and it may not re-decide it if a later run's shape changes.
RATIFIED_POPULATION = POP_ALL
RATIFICATION_SOURCE = ("research/pre-registrations/f5_hedging/"
                       "hedge_portfolio.md §Population and basis — "
                       "RATIFICATION, operator, 2026-08-31")

#: The two words emitted, each over a DIFFERENT object. UNDERPOWERED is defined
#: by G-POWER failing and is read over the hedge cells; MEASUREMENT-ONLY is
#: defined by ARM M's two curves differing materially while no cell clears the
#: bar, and ARM M is not power-gated — it is the whole book over its full
#: session axis and it gates nothing — so it is powered when the cells are not.
#: The registration defines both and orders neither; emitting one alone would
#: misreport, so both are emitted, each attached to what it is defined over.
RATIFIED_VERDICTS = ("UNDERPOWERED", "MEASUREMENT-ONLY")

#: Every study-level verdict line is stamped with this prefix so the report has
#: exactly one machine-checkable place a verdict word can be emitted from.
VERDICT_STAMP = "VERDICT"

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
#: The stratum labels every cell is evaluated under (errata F9). The
#: registration's asymmetric reading rule is BINDING — "Results are always
#: stratified DIRECT versus CONSTITUENT" — so a stratum is a unit of
#: COMPUTATION here, not a row in a count table. The pooled row is labelled.
STRATUM_POOLED = "POOLED"
STRATA = (STRATUM_POOLED, S.DIRECT, S.CONSTITUENT)

#: ARM N's two matchings. RICH is what clause 3 is read from (it reproduces the
#: per-session proxy sequence as well as the count and the date-clustering, so
#: the null is harder to beat — the conservative direction); REGISTERED is the
#: match the pre-registration actually commits to, "matched in COUNT and in
#: date-clustering", printed beside it as the registered estimator. Same
#: treatment F5 gave the withdrawn bootstrap.
MATCH_RICH = "count+clustering+proxy_sequence"
MATCH_REGISTERED = "count+clustering"

#: The trailing hold-window session carries whatever is already open one more
#: day and NEVER opens a hedge. A sentinel rather than None, because None
#: already means "this session's top cluster is UNHEDGEABLE".
CARRY = "__carry__"

#: Stamped on every stat row belonging to a cell the study has already
#: power-stopped (errata F11). "UNDERPOWERED — no direction is quoted, ever."
UNPOWERED_NOTE = "UNDERPOWERED CELL — no direction is quoted from this row"

METRIC_MAXDD = "max_dd"
METRIC_ULCER = "ulcer"
METRIC_TUW = "tuw"
CO_PRIMARIES = (METRIC_ULCER, METRIC_TUW)


# ════════════════════════════════════════════════════════════════════════════
# printing helpers (shape copied from hedge_sizing.py / hedge_timing.py)
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
    """One episode's hedge — its segments and the dated dollar changes.

    `proxies` is a TUPLE since errata F8: the concentrated cluster is re-picked
    each SESSION, so one episode may carry a put on SMH for four sessions and
    then on QQQ for three. It holds the distinct proxies the episode actually
    carried, in the order they were first opened.
    """
    episode: tuple[_date, ...]
    proxies: tuple[str, ...] = ()
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


def session_proxy(sc) -> str | None:
    """That session's own hedgeable top proxy, or None.

    None covers both "no cluster carries any priced exposure" and "the top
    cluster is one of the four the registration fixes as UNHEDGEABLE". Neither
    is a hedge, and the registration treats both the same way: the session is
    carried at f=0 and stays in the denominator.
    """
    if sc is None or sc.top_proxy is None or not sc.top_hedgeable:
        return None
    return sc.top_proxy


def episode_shape(episode, by_session) -> tuple[str | None, ...]:
    """The per-SESSION proxy sequence of one trigger episode.

    This is what ARM N's matching reproduces under `MATCH_RICH`, so the null
    carries the same rotation the arm does.
    """
    return tuple(session_proxy(by_session.get(s)) for s in episode)


def episode_plan(episode, by_session, universe
                 ) -> tuple[list[_date], list[str | None]]:
    """`(window, proxies)` — the hold window and the proxy to carry each session.

    ERRATA F8. The registration hedges "on ANY session where concentration >=
    tau ... a long put on the concentrated cluster's proxy" — PER SESSION. This
    module used to read `by_session[ep[0]]` once and carry THAT cluster's proxy
    for the whole episode, which was wrong in two directions at once: an
    episode whose top cluster rotated mid-run carried a put on a cluster that
    was no longer the concentrated one (measured at tau 0.30: 8 of 32 episodes,
    37 session-days), and an episode whose FIRST session was unhedgeable was
    DROPPED WHOLE (2 of 32 episodes, 15 triggered sessions) although its later
    sessions were hedgeable.

    Per session, therefore:

      * a session whose top cluster is UNHEDGEABLE, or carries no proxy at all,
        yields None. The hedge is carried at f=0 on that SESSION, the session
        stays in the denominator, and the episode is never dropped —
        `hedge_structure`'s standing principle, which this module already
        applies to an unfillable session.
      * the trailing hold-window session yields `CARRY`: it marks whatever is
        open one more day and opens nothing.
    """
    window = hold_window(episode, universe)
    proxies: list[str | None] = list(episode_shape(episode, by_session))
    proxies += [CARRY] * (len(window) - len(proxies))
    return window, proxies


def proxy_runs(window, proxies) -> list[tuple[str, list[_date], int]]:
    """`window` cut into maximal runs carrying the SAME proxy.

    Each run is `(proxy, days, n_active)`. `days[:n_active]` are the sessions on
    which that proxy IS the session's own top proxy — the only sessions a hedge
    may be OPENED on. One further session is appended when there is one: the
    session the run is closed on, so its last day's move is booked at that day's
    mark rather than silently dropped. That session belongs to the NEXT run as
    its opening day when the proxy rotated, which is the same overlap a roll
    already has (the settlement day is the new segment's entry day).
    """
    runs: list[tuple[str, list[_date], int]] = []
    i, n = 0, len(window)
    while i < n:
        p = proxies[i]
        if p is None or p == CARRY:
            i += 1
            continue
        j = i
        while j < n and proxies[j] == p:
            j += 1
        days = list(window[i:j])
        n_active = len(days)
        if j < n:
            days.append(window[j])
        runs.append((p, days, n_active))
        i = j
    return runs


def plan_episode(window, proxies, f: float, budget: float, rule: str,
                 diag: dict) -> Leg:
    """Select, ROTATE and roll the proxy put across one trigger episode's window.

    `proxies` is aligned with `window` (see `episode_plan`). A session with no
    fillable contract, whose size rounds below one contract, or whose top
    cluster is unhedgeable is carried at f=0 — the hedge simply is not on that
    day, and the next session tries again. Nothing is fabricated and nothing is
    dropped.
    """
    leg = Leg(episode=tuple(window))
    held: list[str] = []
    diag["sessions_unhedgeable"] += sum(1 for p in proxies if p is None)
    runs = proxy_runs(window, proxies)
    for r, (proxy, days, n_active) in enumerate(runs):
        if r:
            diag["rotations"] += 1
        cur_pick: HI.PutPick | None = None
        cur_c = 0
        cur_days: list[_date] = []
        for k, day in enumerate(days):
            if cur_pick is not None and day > cur_pick.expiry:
                leg.segments.append(Segment(cur_pick, cur_c,
                                            tuple(cur_days + [day]), True))
                diag["rolls"] += 1
                cur_pick, cur_c, cur_days = None, 0, []
            if cur_pick is None:
                if k >= n_active:
                    continue        # a close-only session never opens a hedge
                pick = HI.select_put(proxy, day, rule)
                if pick is None:
                    diag["sessions_no_fill"] += 1
                    continue
                c = _contracts_for(pick.entry_mark * HI.SHARES_PER_CONTRACT,
                                   f, budget)
                if c < 1:
                    diag["sessions_sub_one"] += 1
                    continue
                cur_pick, cur_c, cur_days = pick, c, [day]
                leg.cost += HI.entry_cost(pick, c)
                diag["opens"] += 1
                if proxy not in held:
                    held.append(proxy)
                continue
            cur_days.append(day)
        if cur_pick is not None:
            leg.segments.append(Segment(cur_pick, cur_c, tuple(cur_days), False))
    leg.proxies = tuple(held)
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


def price_cluster_short(episode, by_session, universe, f: float,
                        diag: dict) -> dict[_date, float]:
    """ARM RF — the fill-INDEPENDENT floor: short fraction f of the
    concentrated cluster's own signed delta notional in the proxy underlying.

    The registration's ARM R is delta-matched to ARM C's put, which makes it
    depend on the option cache it was introduced to be free of. Both readings
    are therefore run: ARM R is clause 7's control, ARM RF is the floor that
    keeps the study from terminating on fill coverage (`hedge_structure`'s end).
    The sign is the caller's: a POSITIVE cluster net (a long book) is stood
    against by carrying `-f x net`.

    Re-picked EACH SESSION since errata F8, on exactly the runs `plan_episode`
    hedges: one short per run of same-proxy sessions, sized off the cluster's
    own net at the session the run OPENS on. An episode whose first session is
    unhedgeable is no longer dropped; it carries nothing until a hedgeable
    session arrives.
    """
    window, proxies = episode_plan(episode, by_session, universe)
    out: dict[_date, float] = {}
    for proxy, days, _n_active in proxy_runs(window, proxies):
        sc = by_session.get(days[0])
        cl = (next((c for c in sc.clusters if c.name == sc.top_cluster), None)
              if sc is not None else None)
        if cl is None:
            diag["no_cluster"] += 1
            continue
        pos = HI.short_for_delta_notional(proxy, days[0], -f * cl.net)
        if pos is None:
            diag["no_bar"] += 1
            continue
        levels = HI.short_pnl_path(pos, days)
        prev = 0.0
        for day in days:
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
    stratum: str = STRATUM_POOLED
    triggered: list = field(default_factory=list)
    eps: list = field(default_factory=list)
    ep_hedges: list = field(default_factory=list)
    legs: list = field(default_factory=list)
    hedge: dict = field(default_factory=dict)
    diag: dict = field(default_factory=dict)
    stats: M.PathStats | None = None
    verdict: str = ""
    clauses: dict = field(default_factory=dict)


def new_diag() -> dict:
    """The planning diagnostic every arm shares.

    One shape, so a column of the cell-shape table never means two different
    things in two arms.
    """
    return dict(rolls=0, opens=0, rotations=0, sessions_no_fill=0,
                sessions_sub_one=0, sessions_unhedgeable=0,
                episodes_all_unhedgeable=0)


def episode_leg(episode, by_session, universe, f: float, budget: float,
                rule: str, diag: dict) -> Leg:
    """One trigger episode planned with its cluster re-picked EACH SESSION."""
    window, proxies = episode_plan(episode, by_session, universe)
    if not any(p is not None and p != CARRY for p in proxies):
        diag["episodes_all_unhedgeable"] += 1
    return plan_episode(window, proxies, f, budget, rule, diag)


def build_cell(arm: str, tau: float, f: float, rule: str, triggered,
               eps, by_session, budget: float, universe,
               stratum: str = STRATUM_POOLED) -> Cell:
    """One arm x tau x f x stratum cell, planned but not yet evaluated.

    NO EPISODE IS DROPPED (errata F8). Every triggered episode is planned; the
    sessions inside it that carry no hedgeable cluster are carried at f=0 and
    counted on the diagnostic. `ep_hedges` is kept PER EPISODE, aligned with
    `eps`, because clause 6's leave-one-DATE-out folds re-plan only the episode
    the removed date sits in.
    """
    diag = new_diag()
    cell = Cell(arm=arm, tau=tau, f=f, rule=rule, stratum=stratum,
                n_sessions=len(triggered), n_episodes=len(eps),
                n_book_dates=0, powered=len(eps) >= MIN_TRIGGER_DATES,
                diag=diag, triggered=list(triggered), eps=list(eps))
    for ep in eps:
        leg = episode_leg(ep, by_session, universe, f, budget, rule, diag)
        cell.ep_hedges.append(price_put(leg))
        if leg.segments:
            cell.legs.append(leg)
    cell.hedge = merge(cell.ep_hedges)
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


def leave_one_date_out(cell: Cell, by_session, universe, axis, base_daily,
                       capital: float, base: M.PathStats, metrics,
                       f: float, budget: float, rule: str) -> dict:
    """Clause 6, folded over TRIGGER DATES — errata F10.

    A FOLD IS ONE TRIGGER DATE. It used to be one placed LEG: at tau 0.30 that
    made 29 folds out of 32 episodes and 256 trigger dates, so an episode that
    placed nothing was not a fold at all and the clause was leave-one-LEG-out
    while the registration words it leave-one-date-out.

    Removing a date removes it from the TRIGGER, so the episode containing it
    is re-planned as the (up to two) contiguous sub-episodes that survive —
    which is what dropping one session out of a run actually leaves. Every
    other episode's priced hedge is reused unchanged, so a fold costs one
    episode's re-plan and not the cell's.

    Returns `{metric: [improvement per fold]}`, aligned with
    `cell.triggered`.
    """
    out = {m: [] for m in metrics}
    where = {}
    for i, ep in enumerate(cell.eps):
        for s in ep:
            where[s] = i
    diag = new_diag()
    for d in cell.triggered:
        i = where.get(d)
        parts = [h for j, h in enumerate(cell.ep_hedges) if j != i]
        if i is not None:
            ep = cell.eps[i]
            for piece in (tuple(s for s in ep if s < d),
                          tuple(s for s in ep if s > d)):
                if piece:
                    parts.append(price_put(episode_leg(
                        piece, by_session, universe, f, budget, rule, diag)))
        hd = hedged_daily(axis, base_daily, merge(parts))
        st = M.path_stats(curve_of(axis, hd), capital)
        for m in metrics:
            out[m].append(improvement(base, st, m))
    return out


def evaluate_bar(cell: Cell, axis, base_daily, capital, arm_n,
                 arm_r_improvement, boot_n: int, loo_all: dict,
                 arm_n_registered=None) -> dict:
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

    # 1 — hedge_sizing D3's criterion, verbatim, on dollars.
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
    per_year_all = {m: {y: improvement(b, h, m) for y, (b, h) in year_stats.items()}
                    for m in CO_PRIMARIES}
    cuts_all = {m: {k: improvement(b, h, m) for k, (b, h) in cut_stats.items()}
                for m in CO_PRIMARIES}

    # 3 — beats ARM N's 95th percentile on that same metric. Clause 3 is read
    # from the RICH match; the REGISTERED match is carried beside it as a
    # printed diagnostic, never as the clause (errata F14).
    p05, p95 = arm_n.get(metric, (None, None))
    out["arm_n_p95"] = p95
    out["arm_n_p05"] = p05
    out["c3"] = _finite(p95) and point > p95
    reg = (arm_n_registered or {}).get(metric, (None, None))
    out["arm_n_reg_p05"], out["arm_n_reg_p95"] = reg
    out["c3_registered"] = _finite(reg[1]) and point > reg[1]

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
               seed: int = SEED, match: str = MATCH_RICH) -> dict:
    """Matched random hedging. `portfolio_delta`'s ARM N applied to a path
    metric — an arm must beat this band's 95th percentile, not merely beat the
    unhedged book.

    TWO MATCHINGS, both run and both printed (errata F14):

      `MATCH_RICH`        same episode COUNT, same episode LENGTHS and the same
                          PER-SESSION PROXY SEQUENCE, at uniform random starts.
                          A richer match makes the null HARDER to beat, so it
                          is the conservative choice and it is what clause 3 is
                          read from. It is NOT what the registration commits,
                          which is why it is labelled wherever it prints.
      `MATCH_REGISTERED`  the registration's own words — "matched in COUNT and
                          in date-clustering" — and nothing more: the same
                          number of episodes at the same lengths and the same
                          contiguity, but each episode's proxy drawn UNIFORMLY
                          from the proxies the triggered set actually carried
                          rather than matched to it. Printed beside the rich
                          band as the registered estimator, the way F5 kept the
                          withdrawn bootstrap visible beside the chronological
                          one.

    The per-session rule of errata F8 applies to the null too: a matched
    episode carries the same rotation, and a session the arm carried at f=0
    because its cluster was unhedgeable is carried at f=0 in the null as well.
    Otherwise the null would stop being a null for the arm it is a null for.

    Returns `{metric: (p05, p95)}`. BOTH tails are needed: the 95th is clause
    3's bar for a positive and the 5th is the mirrored clause for a CONTRARY,
    so a negative is held against the same null as a positive (errata F1).
    """
    shapes = [episode_shape(ep, by_session) for ep in eps]
    shapes = [s for s in shapes if any(p is not None for p in s)]
    pool = sorted({p for s in shapes for p in s if p is not None})
    uni = list(universe)
    draws: dict[str, list[float]] = {m: [] for m in metrics}
    if not shapes or not pool or len(uni) < 2:
        return {m: (float("nan"), float("nan")) for m in metrics}
    rng = random.Random(seed)
    base = M.path_stats(curve_of(axis, base_daily), capital)
    for _ in range(n_seeds):
        legs = []
        diag = new_diag()
        for shape in shapes:
            length = len(shape)
            if length > len(uni):
                continue
            start = rng.randrange(0, len(uni) - length + 1)
            window = hold_window(uni[start:start + length], uni)
            seq = ([rng.choice(pool)] * length if match == MATCH_REGISTERED
                   else list(shape))
            proxies = seq + [CARRY] * (len(window) - length)
            legs.append(plan_episode(window, proxies, f, budget, rule, diag))
        hd = hedged_daily(axis, base_daily, merge(price_put(leg) for leg in legs))
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


def power_note(powered: bool) -> str:
    """`UNPOWERED_NOTE` when the cell this row belongs to is power-stopped.

    Errata F11. Signed dMaxDD / dUlcer / dTUW were tabulated for cells the
    study had ALREADY power-stopped — ARM C at tau 0.35/0.40, every ARM CS
    cell, the whole ARM R / ARM RF / ARM B tables and the nearest-fill
    sensitivity. No clause, verdict or prose read them, and each cell's own
    section restated the rule, but the registration's words are "UNDERPOWERED
    — no direction is quoted, ever", and a signed number in a table IS a
    direction in print. Every such row now carries the stamp.
    """
    return "" if powered else UNPOWERED_NOTE


def note(*parts: str) -> str:
    """Join the labels a stat row carries. Empty parts drop out."""
    return " · ".join(p for p in parts if p)


def print_clauses(res: dict, cell: Cell, args) -> tuple[int, int]:
    """One evaluated cell's full clause set. Returns (clause2 flip, clause3 flip).

    A "flip" is a clause whose PASS/FAIL differs between the estimator the
    clause is READ from and the one printed beside it as a diagnostic — the
    withdrawn month-shuffle bootstrap for clause 2 (errata F5), the
    registration's own ARM N match for clause 3 (errata F14).
    """
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
    flip2 = int(res["c2"] != res["c2_withdrawn"])
    print(f"    clause 2 under the withdrawn estimator: "
          f"{'PASS' if res['c2_withdrawn'] else 'FAIL'} — "
          f"{'SAME as the chronological one' if not flip2 else 'DIFFERENT'}")
    print(f"  3 beats ARM N p95                {'PASS' if res['c3'] else 'FAIL'}"
          f"   arm {pt:+.4f} vs null p95 {_num(res['arm_n_p95'])}"
          f"   [{args.seeds} seeds, RICH match: count + episode lengths + "
          f"per-session proxy sequence — NOT the registered match]")
    flip3 = int(res["c3"] != res["c3_registered"])
    print(f"    registered match (COUNT + date-clustering only): "
          f"null p95 {_num(res['arm_n_reg_p95'])} — clause 3 would "
          f"{'PASS' if res['c3_registered'] else 'FAIL'}, "
          f"{'SAME as the rich match' if not flip3 else 'DIFFERENT'} "
          f"(diagnostic; the clause is read from the rich match)")
    print(f"  4 years positive                 {'PASS' if res['c4'] else 'FAIL'}"
          f"   " + "  ".join(f"{y}:{v:+.4f}" for y, v in res["per_year"].items()))
    print(f"  5 ex-window cuts                 {'PASS' if res['c5'] else 'FAIL'}"
          f"   " + "  ".join(f"{k}:{v:+.4f}" for k, v in res["cuts"].items()))
    loo = res["loo"]
    print(f"  6 leave-one-date-out             {'PASS' if res['c6'] else 'FAIL'}"
          f"   {sum(1 for v in loo if v > 0)}/{len(loo)} folds keep the sign"
          + (f"   worst {min(loo):+.4f}" if loo else ""))
    print(f"      A FOLD IS ONE TRIGGER DATE (errata F10): {len(loo)} folds for "
          f"{cell.n_sessions} triggered\n      sessions in {cell.n_episodes} "
          f"episodes. The episode holding the removed date is re-planned as "
          f"the\n      (up to two) sub-episodes that survive. It used to be one "
          f"placed LEG, so an\n      episode that placed nothing was not a fold "
          f"at all.")
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
    return flip2, flip3


def print_not_preregistered(args, budget: float) -> None:
    """The ONE place every discretionary choice in this module is listed.

    Errata F14. These were disclosed before — but scattered, each beside the
    section it affected, so a reader had to reassemble them from six places and
    five of them were not disclosed at all. Every choice this module made that
    the registration does NOT commit is listed here, with what it is and which
    clause of the bar it feeds. A choice that feeds a clause and is not on this
    list is a defect.

    None of these may be read as findings, and none of them is tuned: they are
    fixed in code, stated here, and not revisited after an outcome.
    """
    hdr("NOT PRE-REGISTERED — every discretionary choice in this module, in "
        "one place")
    print(f"""  The pre-registration
  (research/pre-registrations/f5_hedging/hedge_portfolio.md) fixes the sector
  map, the tau grid, the f grid, the hedge-pressure cut, the two fill rules,
  the DTE windows, the >=60% fill gate, the >=25 trigger-date floor, the
  Bonferroni denominator of 9, the seven clauses of the bar and the verdict
  vocabulary. NONE of those appears below. What appears below is everything
  ELSE this module had to decide in order to run at all.

  THE POPULATION AND THE ORDER OF SECTIONS
  1  SESSION CALENDAR — the trading sessions are the dates in the SPY OHLC
     cache. It defines the {C.MIN_TRIGGER_DATES}-date floor's denominator, the session
     universe, and therefore every episode and every clause. Weekdays alone
     over-count by market holidays; the registration names a session universe
     but no calendar.   Feeds: G-POWER and, through the episodes, ALL SEVEN
     CLAUSES.
  2  G-POWER CLUSTERING = EPISODES — the registration asks for ">= {C.MIN_TRIGGER_DATES} trigger
     DATES (date-clustered, not sessions)" but every session already IS one
     date, so the clustering is undefined. All three readings are printed in
     the census; the floor is read against EPISODES, the strictest.
     Feeds: which cells are evaluated at all.
  3  BOTH READINGS OF THE POPULATION CLAUSE are run and neither concluded from
     — ERRATUM 1, resolved by the operator's ratification recorded in the
     pre-registration's Population and basis section, not a free choice.

  THE HEDGE ITSELF
  4  ROLLING — a 25-75 DTE put cannot span a long episode, so it is settled at
     expiry intrinsic and re-opened. The alternative is an unpriced hedge, not
     a longer one.   Feeds: ALL SEVEN CLAUSES.
  5  HOLDING WINDOW — the hedge is carried to the close of the session AFTER
     the episode ends. Without it a one-session episode opens and closes on the
     same mark and contributes exactly zero.   Feeds: ALL SEVEN CLAUSES.
  6  PER-SESSION RE-PICK, and how a rotation is executed (errata F8) — the
     registration says "a long put on the concentrated cluster's proxy" per
     triggered session, but not what to do when the top cluster CHANGES
     mid-episode. This module closes the run at that session's own mark and
     opens the new proxy on the same session; a session whose top cluster is
     UNHEDGEABLE closes the run and carries nothing, staying in the
     denominator.   Feeds: ALL SEVEN CLAUSES.
  7  SIZING — contracts = int(f x risk_contracts(put debit, ${budget:,.0f})); a hedge
     that rounds below one contract is SKIPPED, never floored to 1. The
     registration names the floor-to-1 DEFECT and says to inherit-fix it but
     does not say which fix.   Feeds: ALL SEVEN CLAUSES.
  8  SETTLE_LOOKBACK_DAYS = {SETTLE_LOOKBACK_DAYS} — an expiry settlement is marked against that
     expiry date's close, walked back up to {SETTLE_LOOKBACK_DAYS} calendar days for a holiday or
     half-session gap. The report elsewhere says only "against that day's
     close".   Feeds: ALL SEVEN CLAUSES.
  9  BAND-RULE TIE-BREAK — inside the committed band the contract is ranked by
     |DTE-45|, then |K-S|, then (expiry, strike) so the pick is deterministic
     on a grown cache. The registration fixes the band's WINDOWS and no
     tie-break.   Feeds: which contract fills, hence ALL SEVEN CLAUSES.
 10  NO ADMISSION LEDGER — the hedge is not routed through
     account_sim.admission(); the whole book at its own contract counts has no
     ledger to admit against. The cash and exposure footprint is REPORTED
     (peak debit per cell), not enforced.   Feeds: ALL SEVEN CLAUSES.

  THE MEASUREMENT AND THE INFERENCE
 11  DIRECT_MAJORITY = {C.DIRECT_MAJORITY:.2f} — a session is DIRECT when at least this share of
     its TOP cluster's gross exposure sits in the proxy instrument itself. The
     registration names the two strata and does not define the cut; the raw
     share is carried on every session so a reader can re-cut it.
     Feeds: the stratification, hence every per-stratum clause set.
 12  STRATIFICATION, as computed (errata F9) — a session's stratum is its TOP
     cluster's; POOLED is reported as a third row and labelled, not as a
     stratum; G-FILL is read on the POOLED triggered set and the strata inherit
     that decision.   Feeds: which stratum each clause set belongs to.
 13  THE READ METRIC — when neither co-primary's CI excludes zero the report
     falls back to ULCER so a number is printed rather than a blank, and
     CO_PRIMARIES order breaks a tie toward ulcer. The registration says "at
     least one co-primary" and names no tie-break.   Feeds: clauses 3, 4, 5, 6
     and 7, all of which are read on the chosen metric.
 14  BOOTSTRAP — {args.boot} paired resamples, a CHRONOLOGICAL moving block whose length
     is the median calendar-month cluster floored at {BOOT_BLOCK_MIN} sessions, at a fixed
     seed. The registration asks for "date-clustered resampling" and names no
     estimator. The withdrawn month-shuffle estimator (errata F5) is printed
     beside it and no clause is read from it.   Feeds: clause 2.
 15  ARM N'S MATCH (errata F14) — clause 3 is read from a RICH match: episode
     COUNT, episode LENGTHS and the PER-SESSION PROXY SEQUENCE, at uniform
     random starts. The registration commits only "matched in COUNT and in
     date-clustering". A richer match makes the null HARDER to beat, so it is
     conservative — but it is not what was committed, so the REGISTERED match
     (count and date-clustering, with each episode's proxy drawn uniformly from
     the proxies the triggered set carried) is computed and printed beside it
     as the registered estimator, and the report says whether clause 3's
     outcome differs between them.   Feeds: clause 3.
 16  A FOLD IS ONE TRIGGER DATE (errata F10) — the episode holding the removed
     date is re-planned as the up-to-two sub-episodes that survive. It used to
     be one placed LEG.   Feeds: clause 6.

  THINGS THAT FEED NO CLAUSE, LISTED SO THE LIST IS COMPLETE
 17  ARM RF — {ARM_RF_LABEL}. This module's own
     fill-independent floor. Every one of its rows carries that label and NO
     clause of the bar is read from it.
 18  ARM M'S "MATERIALLY DIFFERENT" THRESHOLDS — $1 / 0.1 ulcer point / 1 TUW
     point. ARM M gates nothing and no clause reads it; the GAP itself is
     printed beside the boolean because a boolean off a $1 cut is not a
     measurement.
 19  G-FILL'S DENOMINATOR IS CACHE-CONDITIONED — the instrument universe comes
     from the option history cache, i.e. contracts the BOOK traded, so the band
     rates measure cache coverage rather than market liquidity and would move
     on a re-scrape.   Feeds: G-FILL, and nothing else.
 20  ARM P IS LEFT LITERAL — ERRATUM 2. Not a choice this module made free of
     the registration: the registration's own definition is degenerate, and
     redefining it would be a post-hoc arm.""")


def cache_state() -> str:
    """`hedge_structure` R4's scar: the nearest-strike rule RE-PICKS legs on a
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
    print(f"  degraded (no stored outcome — fell back to pos.dollars): "
          f"{bc.n_degraded}")
    if bc.reconciles and not bc.n_degraded:
        print("  G-MTM PASS — daily_pnl_csv at the STORED exit index, times the "
              "row's contracts,\n  equals the row's STORED realized_pnl_abs. Two "
              "independent columns; neither\n  side is a replay of the other.")
        return 0
    if bc.reconciles:
        print(f"  G-MTM PASS — but NOT on two independent columns for every "
              f"position. {bc.n_degraded}\n  position(s) carried neither a "
              f"stored realized_pnl_abs nor a stored R_dol, so the\n  marked "
              f"exit was compared against this module's OWN pos.dollars — the "
              f"self-\n  comparison shape errata F2 removed, reopened per "
              f"position. Nothing may be\n  read from those rows as a "
              f"reconciliation.")
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
                     curve_gaps=None, curve_max_dd=None,
                     clause2_survives=None,
                     clause3_survives=None, n_powered=0, strata={})

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
    print("""  Every hedge verdict on record (hedge_sizing D3, hedge_structure H3,
  hedge_timing H4) rests on account_sim's close-bucketed curve, whose own
  print_equity says "Open positions are not marked to market, so this
  understates intra-position drawdown." A hedge's function is to cushion
  exactly the path that curve omits. ARM M measures the gap. It gates nothing.""")
    mtm_stats = M.path_stats(bc.mtm, capital)
    rea_stats = M.path_stats(bc.realized, capital)
    print()
    print_stats_row("mark-to-market (the basis)", mtm_stats)
    print_stats_row("realized-on-close (comparability)", rea_stats)
    gaps = dict(max_dd=mtm_stats.max_dd - rea_stats.max_dd,
                ulcer=mtm_stats.ulcer - rea_stats.ulcer,
                tuw=mtm_stats.tuw - rea_stats.tuw)
    curves_differ = (abs(gaps["max_dd"]) > 1.0 or abs(gaps["ulcer"]) > 0.1
                     or abs(gaps["tuw"]) > 0.01)
    out["curves_differ"] = curves_differ
    out["curve_gaps"] = gaps
    out["curve_max_dd"] = dict(mtm=mtm_stats.max_dd,
                               realized=rea_stats.max_dd)
    print(f"\n  sessions {mtm_stats.n_sessions} (the curve's own weekday-grid axis; "
          f"the census below\n  reports the calendar reading the registration "
          f"disclosed)")
    rel = (abs(gaps["max_dd"] / rea_stats.max_dd) * 100.0
           if rea_stats.max_dd else float("nan"))
    print(f"  THE GAP, printed rather than asserted: maxDD "
          f"${gaps['max_dd']:+,.0f} ({rel:.1f}% of the realized-on-close "
          f"drawdown)   ulcer {gaps['ulcer']:+.2f} pts   "
          f"TUW {gaps['tuw'] * 100:+.1f} pts")
    print(f"  curves differ materially: {'YES' if curves_differ else 'no'}  "
          f"(thresholds $1 / 0.1 ulcer pt / 1 TUW pt — this module's, NOT "
          f"pre-registered.\n  A boolean off a $1 cut on a "
          f"${abs(rea_stats.max_dd):,.0f} drawdown says far less than the gap "
          f"above, which is\n  the figure to read: the two curves differ by "
          f"about that much, and no more.)")
    role = ("the RATIFIED population" if name == RATIFIED_POPULATION
            else "a REPORTED STRATUM, not a co-primary")
    print(f"""  This is a MEASUREMENT. The registration words a MEASUREMENT-ONLY
  verdict for it. ARM M is NOT power-gated — it is the whole book over its full
  session axis and it gates nothing — so it is readable when every hedge cell
  is power-stopped. The word is emitted ONCE, in the closing section, and only
  off the ratified population; this population (`{name}`) is {role}.""")

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
    hdr("G-CENSUS — the power census; its INPUTS are entry-dated fields only")
    print("""  WHAT IS TRUE, stated as such (errata F13). Every number in this census is
  computed from ENTRY-DATED fields — ticker, delta, contracts,
  entry_underlying — plus `days_held` through the OCCUPANCY layer alone, which
  is the replay fixture of a book that already happened and is not a trigger
  input. That is the property the gate is for.

  WHAT IS NOT TRUE is the header this section used to carry. It claimed the
  census "prints before any outcome column is read", and the code contradicts
  it: G-MTM, the replay divergence and ARM M all print outcome-derived dollars
  ABOVE this line, and G-MTM must read the stored outcome by construction. The
  claim was about PRINT ORDER; the property worth having is about INPUTS.

  G-CENSUS HAS NO FAILING PATH. It is a DISCIPLINE, not a check: the census is
  computed and printed so the trigger's shape is visible before any arm is
  read. The gate that can refuse on lookahead is G-BLIND, above.""")
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
  hedge_structure's standing principle that a hedge unavailable exactly when
  needed is not a hedge. An UNHEDGEABLE cluster keeps its proxy identity and
  counts against the gate; it is never folded into BROAD/SPY.

  THE GATE AND THE ARMS NOW FILL THE SAME OBJECT (errata F15, closed by F8).
  These (session, proxy) pairs are built from each session's OWN top proxy. The
  arms used to fill the proxy picked at the EPISODE'S FIRST session and carry
  it for the whole episode, so the gate measured one population and the arms
  filled another — at tau 0.30, an 81.6% gate against 85.5% actual live-hedge
  session coverage at f=1.00. Since F8 re-picks per session, the two are one
  object and the gate is a gate on what the arms actually do.

  DISCLOSED: this denominator is CACHE-CONDITIONED. The instrument universe is
  built from the option history cache, i.e. contracts the BOOK traded, so these
  rates measure CACHE COVERAGE, not market liquidity, and would move on a
  re-scrape. The cache state is recorded in the header.""")
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
    print(f"""  THE CLUSTER AND ITS PROXY ARE RE-PICKED EACH SESSION (errata F8). A hedge is
  opened on a triggered session against THAT session's concentrated cluster,
  carried while that cluster stays on top, CLOSED and re-opened on the new
  proxy when the top cluster rotates, and ROLLED when the put expires inside
  the episode (settled at expiry intrinsic against that day's close). A session
  whose top cluster is one of the four UNHEDGEABLE ones is carried at f=0 and
  STAYS IN THE DENOMINATOR — never a dropped episode, per hedge_structure's
  standing principle. Until 2026-08-31 this module read the cluster ONCE, at
  the episode's first session, and dropped whole any episode whose first
  session was unhedgeable.

  Rolling is not pre-registered: episodes run to {longest} sessions and a 25-75 DTE
  put cannot span that, so the alternative would be an unpriced hedge, not a
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

  All three of those, and every other choice this module made that the
  registration does not commit, are listed together in the NOT PRE-REGISTERED
  section above, with the clause each one feeds.

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
            fdiag = dict(no_bar=0, no_cluster=0)
            rf = [price_cluster_short(ep, by_session, universe, f, fdiag)
                  for ep in eps]
            arm_rf[(tau, f)] = dict(hedge=merge(rf), diag=fdiag)

    sub("cell shape (no outcome read yet)")
    print("""  Since errata F8 the concentrated cluster and its proxy are re-picked EACH
  SESSION inside an episode. `rotate` counts the mid-episode proxy changes that
  produces; `unhedg-sess` counts the sessions carried at f=0 because that
  session's top cluster is one of the four the registration fixes as
  UNHEDGEABLE, and those sessions STAY in the denominator. `all-unhedg-ep`
  counts episodes with no hedgeable session at all — which is the only way an
  episode now contributes nothing. No episode is dropped for the state of its
  FIRST session.""")
    print("\n   tau     f   episodes  book_dates  legs  opens  rolls  rotate  "
          "no-fill  sub-1c  unhedg-sess  all-unhedg-ep    debit$   peak$  peak/cap")
    for (tau, f), cell in cells.items():
        d = cell.diag
        pk = peak_debit(cell.legs)
        print(f"  {tau:.2f}  {f:.2f}   {cell.n_episodes:8d}  "
              f"{cell.n_book_dates:10d}  {len(cell.legs):4d}  {d['opens']:5d}  "
              f"{d['rolls']:5d}  {d['rotations']:6d}  "
              f"{d['sessions_no_fill']:7d}  "
              f"{d['sessions_sub_one']:6d}  {d['sessions_unhedgeable']:11d}  "
              f"{d['episodes_all_unhedgeable']:13d}  "
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
        print_stats_row(f"ARM C tau {tau:.2f} f {f:.2f}", stt, mtm_stats,
                        note=power_note(cell.powered))

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
                            stt, mtm_stats,
                            note=power_note(cells[(tau, f)].powered))

    sub(f"ARM RF — {ARM_RF_LABEL}")
    print(f"""  {ARM_RF_LABEL}. ARM RF is NOT in
  research/pre-registrations/f5_hedging/hedge_portfolio.md. It is this
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
                            stt, mtm_stats,
                            note=note(ARM_RF_LABEL,
                                      power_note(cells[(tau, f)].powered)))

    # ── ARM B ───────────────────────────────────────────────────────────────
    hdr("ARM B — instrument comparison: the book's own bear row instead of the put")
    print("""  hedge_sizing D3 and hedge_timing H4 both found the sleeve cannot cut max
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
        print_stats_row(f"ARM B tau {tau:.2f} f {f:.2f}", stt, mtm_stats,
                        note=power_note(cells[(tau, f)].powered))

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
        print_stats_row(f"ARM CS tau {tau:.2f} f {f:.2f}", stt, mtm_stats,
                        note=power_note(cs.powered))

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
    clause3_flips = 0
    n_stratum_cells = 0

    def stratum_cell(strat: str, tau: float, f: float) -> Cell:
        """This (tau, f) cell restricted to one stratum — or the pooled cell."""
        if strat == STRATUM_POOLED:
            return cells[(tau, f)]
        trig = C.triggered_sessions(series, tau, stratum=strat)
        eps = C.episodes(trig, universe)
        c = build_cell("C", tau, f, args.rule, trig, eps, by_session, budget,
                       universe, stratum=strat)
        c.n_book_dates = C.trigger_date_counts(trig, series, recs)["book_dates"]
        return c

    print("""
  STRATIFIED — errata F9. The registration's asymmetric reading rule is BINDING
  ("Results are always stratified DIRECT versus CONSTITUENT"), and until now it
  was printed as a SESSION/EPISODE COUNT TABLE and nothing more: every clause,
  CI and ARM N band ran on the pooled trigger. So a MECHANISM-FOUND would have
  had no stratum to attach to, which is exactly what the asymmetric rule exists
  to prevent. Every cell below is therefore computed THREE times — POOLED,
  DIRECT and CONSTITUENT — each with its own path metrics, its own bootstrap
  CI, its own ARM N band and its own full clause set.

  POOLED IS NOT A STRATUM. A pooled result may not be read as a result about
  either practice; a DIRECT result — a put on an ETF the book already HOLDS —
  may NEVER be cited as evidence for the operator's constituent-to-sector-proxy
  practice, and a NULL in DIRECT is not evidence against it.

  G-POWER is applied PER STRATUM: a stratum below the floor prints UNDERPOWERED
  and no direction is quoted from it. G-FILL is a study-level gate on the arm's
  fill feasibility, read on the POOLED triggered set at each tau; the strata
  inherit that decision rather than re-deriving it.""")

    for (tau, f) in cells:
        sub(f"cell tau {tau:.2f}  f {f:.2f}")
        band_ok = fill[tau][args.rule].passes()
        for strat in STRATA:
            scell = stratum_cell(strat, tau, f)
            head = (f"[{strat:<11s}] triggered sessions {scell.n_sessions:4d}"
                    f"   episodes {scell.n_episodes:3d}"
                    f"   episodes that placed a hedge {len(scell.legs):3d}")
            print(f"\n  {head}")
            if not band_ok:
                scell.verdict = "NOT EVALUABLE"
                print(f"  G-FILL {fill[tau][args.rule].rate:.1%} < "
                      f"{FILL_GATE:.0%} — NOT EVALUABLE (not failed). Only "
                      f"ARM R is read.")
            elif not scell.powered:
                scell.verdict = "UNDERPOWERED"
                print(f"  {scell.n_episodes} trigger dates (episodes) < "
                      f"{MIN_TRIGGER_DATES} — UNDERPOWERED. No direction is "
                      f"quoted. UNDERPOWERED is not a lean.")
            elif not scell.legs:
                scell.verdict = "NO HEDGE PLACED"
                print(f"  no hedge was placed in this stratum — every episode "
                      f"was unhedgeable, unfilled, or sized below one contract "
                      f"(sub-1c {scell.diag['sessions_sub_one']}, unhedgeable "
                      f"sessions {scell.diag['sessions_unhedgeable']}). "
                      f"Nothing to evaluate; not evidence about hedging.")
            else:
                n_stratum_cells += 1
                band = arm_n_band(scell.eps, by_session, universe, axis,
                                  base_daily, capital, f, budget, args.rule,
                                  CO_PRIMARIES, n_seeds=args.seeds,
                                  match=MATCH_RICH)
                band_reg = arm_n_band(scell.eps, by_session, universe, axis,
                                      base_daily, capital, f, budget,
                                      args.rule, CO_PRIMARIES,
                                      n_seeds=args.seeds,
                                      match=MATCH_REGISTERED)
                rdiag = dict(no_entry_delta=0)
                rh = (arm_r[(tau, f)]["hedge"] if strat == STRATUM_POOLED
                      else merge(price_delta_short(leg, rdiag)
                                 for leg in scell.legs))
                rimp = {}
                if rh:
                    rst = M.path_stats(
                        curve_of(axis, hedged_daily(axis, base_daily, rh)),
                        capital)
                    rimp = {m: improvement(mtm_stats, rst, m)
                            for m in CO_PRIMARIES}
                folds = leave_one_date_out(
                    scell, by_session, universe, axis, base_daily, capital,
                    M.path_stats(curve_of(axis, base_daily), capital),
                    CO_PRIMARIES, f, budget, args.rule)
                res = evaluate_bar(scell, axis, base_daily, capital, band,
                                   rimp, args.boot, folds,
                                   arm_n_registered=band_reg)
                scell.clauses = res
                scell.verdict = cell_verdict(res)
                flips = print_clauses(res, scell, args)
                clause2_flips += flips[0]
                clause3_flips += flips[1]
            print(f"  => {strat}: {scell.verdict}")
            if strat == STRATUM_POOLED:
                cells[(tau, f)].verdict = scell.verdict
                if scell.clauses:
                    results[(tau, f)] = scell.clauses
                    out["n_powered"] += 1
                verdict_cells.append(scell)
            else:
                out["strata"].setdefault(strat, defaultdict(int))
                out["strata"][strat][scell.verdict] += 1

    if n_stratum_cells:
        out["clause2_survives"] = (clause2_flips == 0)
        out["clause3_survives"] = (clause3_flips == 0)
        print(f"""
  CLAUSE 2 UNDER THE ESTIMATOR CHANGE (errata F5): {n_stratum_cells} evaluated cell(s)
  across all strata; clause 2's PASS/FAIL differs between the chronological
  moving block and the withdrawn month-shuffle in {clause2_flips} of them. Clause 2's
  outcome therefore {'SURVIVES' if clause2_flips == 0 else 'DOES NOT SURVIVE'} the replacement.

  CLAUSE 3 UNDER THE ARM N MATCH (errata F14): clause 3 is read from the RICH
  match (count + episode lengths + per-session proxy sequence), which is NOT
  what the registration commits. Under the REGISTERED match — count and
  date-clustering only — clause 3's PASS/FAIL differs in {clause3_flips} of the {n_stratum_cells}
  evaluated cell(s). Clause 3's outcome therefore
  {'SURVIVES' if clause3_flips == 0 else 'DOES NOT SURVIVE'} the match this module chose over the committed one.""")

    # ── sensitivity: the nearest-available rule ─────────────────────────────
    other = HI.RULE_NEAREST if args.rule == HI.RULE_BAND else HI.RULE_BAND
    hdr(f"REGISTERED SENSITIVITY — the {other} fill rule, same taus and f grid")
    print(f"""  Both fill rules are pre-registered because coverage is not uniform in time
  (band-rule SMH and QQQ collapse in 2025Q3/Q4). The {other} rule RE-PICKS legs
  on a grown option cache — hedge_structure R4's scar — so the cache state is in
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
                            mtm_stats, note=power_note(c2.powered))

    # ── the asymmetric reading rule ─────────────────────────────────────────
    hdr("DIRECT vs CONSTITUENT — the binding asymmetric reading rule")
    print("""  Results are always stratified. A positive result in the DIRECT stratum — a
  put on an ETF the book already HOLDS — may NEVER be cited as evidence for the
  operator's constituent-to-sector-proxy practice: it is a different action. A
  NULL in DIRECT is likewise not evidence against the constituent practice.

  The book is not shaped like the practice being tested — most of its exposure
  is DIRECT — and the pre-registration disclosed at plan time that the
  constituent stratum would be power-stopped. The census above confirms it at
  every tau.

  THIS IS NO LONGER ONLY A COUNT TABLE (errata F9). Until 2026-08-31 the
  stratification existed here and NOWHERE else: every clause, CI and ARM N band
  ran on the pooled trigger, so the binding rule had a table to point at and no
  stratum to attach a result to. Every cell in the bar section above now
  carries a FULL CLAUSE SET per stratum — POOLED, DIRECT and CONSTITUENT —
  each with its own path metrics, bootstrap CI and null band, and each
  power-gated on its own episode count. The table below is the shape those
  clause sets were computed on.""")
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
    print(f"  {STRATUM_POOLED} (not a stratum — the pooled trigger):")
    for k in sorted(counts):
        print(f"    {k:<18s} {counts[k]} cell(s)")
    for strat in STRATA[1:]:
        tal = out["strata"].get(strat, {})
        print(f"  {strat}:")
        for k in sorted(tal):
            print(f"    {k:<18s} {tal[k]} cell(s)")
    out["counts"] = dict(counts)
    out["strata"] = {s: dict(v) for s, v in out["strata"].items()}
    out["gate_ok"] = dict(gate_ok)
    print("""
  Cell-level words only. The registration's study-level verdicts
  (MECHANISM-FOUND / NULL / CONTRARY / UNDERPOWERED / NOT EVALUABLE /
  MEASUREMENT-ONLY) are emitted ONCE, in the closing section, and only off the
  RATIFIED population — never from this tally and never per population.""")
    return out


# ════════════════════════════════════════════════════════════════════════════

def print_result(summaries: list[dict]) -> None:
    """The closing section: the RATIFIED study-level result.

    Emits the two words the operator's 2026-08-31 ratification fixes, each
    attached to the object the registration defines it over. Extracted from
    `main` so the wording is exercisable by a test instead of being reachable
    only through a full study run.

    This function CITES a recorded decision; it does not make one. If a later
    run's shape stops matching what was ratified, it says so and stops — it
    never re-decides the population or reaches for a different word.
    """
    by_name = {s["name"]: s for s in summaries}
    rat = by_name.get(RATIFIED_POPULATION)

    hdr("RESULT — UNDERPOWERED (the mechanism question) and MEASUREMENT-ONLY "
        "(ARM M)")
    print(f"""  RATIFIED POPULATION `{RATIFIED_POPULATION}` — {POP_LABELS[RATIFIED_POPULATION]}.
  AUTHORITY: {RATIFICATION_SOURCE}.

  ERRATUM 1's deadlock — the registration's population clause names two
  different books, and which one is read decides how many cells are powered at
  all — is RESOLVED. It was resolved by the OPERATOR, on the record, and this
  section cites that decision rather than making one: a `strike_expiry_tweak`
  row carries a REAL Barchart price for a nearby strike or expiry (model-priced
  `bs_options_hist` rows stay excluded), and a book that admits that
  substitution is the CLOSER model of an operator who does not follow a
  proposed leg's strike and expiry precisely at execution. The full reasoning
  is at the authority above and is not restated here as though this module had
  found it.

  `real` is retained as a REPORTED STRATUM. It is NOT a co-primary, and no
  verdict below is read from it.""")

    for s in summaries:
        role = ("RATIFIED — the verdict is read from this population"
                if s["name"] == RATIFIED_POPULATION
                else "REPORTED STRATUM — not a co-primary; no verdict is read "
                     "from it")
        tally = ("  ".join(f"{k} {v}" for k, v in sorted(s["counts"].items()))
                 or "none")
        print(f"\n  population {s['name']} — {POP_LABELS[s['name']]}")
        print(f"    {role}")
        print(f"    {s['n_rows']} rows / {s['n_dates']} signal dates")
        if s["refusal"]:
            print(f"    REFUSED at a gate, exit {s['refusal']} — no cells read")
            continue
        print(f"    powered POOLED cells {s['n_powered']}   "
              f"POOLED cell words: {tally}")
        for strat in STRATA[1:]:
            tal = ("  ".join(f"{k} {v}" for k, v in
                             sorted(s["strata"].get(strat, {}).items()))
                   or "none")
            print(f"    {strat} cell words: {tal}")
        g = s.get("curve_gaps") or {}
        print(f"    ARM M curve gap: maxDD ${g.get('max_dd', 0.0):+,.0f}   "
              f"ulcer {g.get('ulcer', 0.0):+.2f} pts   "
              f"TUW {g.get('tuw', 0.0) * 100:+.1f} pts   "
              f"(differ materially: {'YES' if s['curves_differ'] else 'no'})")
        if s["clause2_survives"] is not None:
            print(f"    clause 2's outcome survives the F5 estimator change: "
                  f"{'YES' if s['clause2_survives'] else 'NO'}")
        if s.get("clause3_survives") is not None:
            print(f"    clause 3's outcome survives the registered ARM N "
                  f"match: {'YES' if s['clause3_survives'] else 'NO'}")

    if rat is None or rat["refusal"]:
        print(f"""
  NO VERDICT IS EMITTED. The ratified population `{RATIFIED_POPULATION}` did
  not complete — it was not run, or it refused at a gate — so neither ratified
  word has an object to attach to. The `real` stratum above may NOT stand in
  for it.""")
        return

    # every cell word this population produced, pooled row and strata together
    words: dict[str, int] = dict(rat["counts"])
    for tal in rat["strata"].values():
        for k, v in tal.items():
            words[k] = words.get(k, 0) + v
    all_unpowered = set(words) == {"UNDERPOWERED"}
    no_candidate = not words.get("CANDIDATE")

    cm = rat.get("curve_max_dd") or {}
    mtm_dd = float(cm.get("mtm") or 0.0)
    rea_dd = float(cm.get("realized") or 0.0)
    gap = mtm_dd - rea_dd
    pct = abs(gap) / abs(rea_dd) * 100.0 if rea_dd else float("nan")
    verb = "UNDERSTATES" if mtm_dd < rea_dd else "OVERSTATES"

    def _ok(flag: bool) -> str:
        return "ok" if flag else "CHANGED — back to the operator"

    print(f"""
  THE CONDITIONS THE RATIFICATION FIXES, RECOMPUTED ON THIS RUN — each from
  this run's own export, none of them stored:
    every cell fails G-POWER, in every stratum ......... {_ok(all_unpowered)}
    ARM M's two curves differ materially .............. {_ok(bool(rat['curves_differ']))}
    no cell clears the bar (no CANDIDATE, any stratum) . {_ok(no_candidate)}
  A CHANGED line means this run is no longer the shape the operator ratified,
  and the words below would have to go back to the operator. They are not this
  module's to re-decide.

  {VERDICT_STAMP} — the mechanism question, over the hedge cells: {RATIFIED_VERDICTS[0]}
    Every cell of the registered tau x f grid fails G-POWER on the ratified
    population, under POOLED, DIRECT and CONSTITUENT alike. NO DIRECTION IS
    QUOTED FROM ANY OF THEM, EVER — the power stamp on each stat row above says
    the same thing row by row. UNDERPOWERED IS NOT A LEAN: it is not a NULL,
    and it is not evidence that the mechanism is absent.

  {VERDICT_STAMP} — ARM M, the measurement, which is not power-gated: {RATIFIED_VERDICTS[1]}
    On the ratified population the SAME unhedged book measures maxDD ${mtm_dd:,.0f}
    mark-to-market against ${rea_dd:,.0f} close-bucketed — a gap of ${gap:+,.0f},
    i.e. the close-bucketed curve {verb} this book's max drawdown by {pct:.1f}%.
    That is what the registration words MEASUREMENT-ONLY for: the two curves
    differ materially while no hedge cell clears the bar. ARM M is the whole
    book over its full session axis and it gates nothing, so it is powered
    exactly when the cells are not.

  BOTH WORDS ARE EMITTED, over DIFFERENT objects. UNDERPOWERED is defined by
  G-POWER failing and belongs to the hedge cells; MEASUREMENT-ONLY is defined
  by ARM M and belongs to the measurement. The registration defines both, and
  orders neither. Emitting only UNDERPOWERED would suppress a result the
  registration itself calls "a real, reportable outcome"; emitting only
  MEASUREMENT-ONLY would imply the cells had been read. There is no third word
  and no compound label.""")

    print(f"""
  WHAT THIS RESULT DOES NOT DO.
    It ships NOTHING.
    It does NOT close the queued max-drawdown question. UNDERPOWERED leaves it
      OPEN: the registration retires that question on a NULL or a CONTRARY, and
      neither was reached.
    It does NOT overturn hedge_sizing D3, hedge_structure H3 or hedge_timing H4.
      Those verdicts STAND. But MEASUREMENT-ONLY says they were read on the
      close-bucketed curve, which on THIS book {verb.lower()} max drawdown by
      {pct:.1f}%, so the basis they were read on is now a KNOWN LIMITATION of
      theirs and should be recorded against them.
    It does NOT remove or amend the §4 bear sleeve, which is operator policy
      and is not removed by any outcome here.

  LIMITATION CARRIED FROM THE RATIFICATION, binding on how this report is read.
  The registration's PLAN-TIME OBSERVATIONS — the exposure table, the
  concentration quantiles, the fill-coverage table and the session universe —
  describe the `real` STRATUM. They reproduce on that stratum and on no other
  reading, and they are NOT disclosures about the ratified population. A reader
  must not take them as such. The figures that describe the ratified population
  are the ones THIS RUN prints: its census, its quantiles, its session universe
  and its G-FILL coverage, every one computed at run time.""")

    print("""
  ARM P IS INERT AS REGISTERED and the registration's binding prose rule is
  UNREACHABLE BY CONSTRUCTION (ERRATUM 2). ARM P has not been redefined into
  something informative — that would be a post-hoc arm. ARM CS is power-stopped
  at every tau under both readings, so PROSE-CONDITIONED, LOOKAHEAD-UNRESOLVED
  does not arise either.

  ARM RF IS UNREGISTERED — ADDED AFTER COMMIT, and no clause of the bar is read
  from it.

  NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF. A MECHANISM-FOUND
  verdict would have produced a DRAFTED amendment to docs/deployment-rules.md
  §4 held in research/, never an edit; a NULL or CONTRARY verdict would have
  shipped nothing and closed the queued max-drawdown question in
  research/deployment-evidence.md. Neither was reached, so neither happens —
  the question stays open and no rule moves. The §4 sleeve is operator policy
  and is not removed by any outcome.""")


# ════════════════════════════════════════════════════════════════════════════

def main() -> int:
    # WHICH POPULATION, read off argv before any parser, because the two arms
    # take different flags (the admitted arm has ONE population and so no
    # `--sources`) and a different `--boot` default. `run.py` files the two
    # under different report stems; see ADMITTED_ARM_FLAG below.
    if ADMITTED_ARM_FLAG in sys.argv[1:]:
        return main_admitted()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--admitted", action="store_true",
                    help="run the ADMITTED-BOOK arm instead: the positions "
                         "account_sim actually takes. Handled above, before "
                         "this parser, and listed here so --help names it.")
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

    hdr("hedge_portfolio — does concentration-triggered proxy hedging cut the "
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

  POPULATION — RATIFIED: `{RATIFIED_POPULATION}`.
  The pre-registration's "Population and basis" clause originally named two
  different books at once (ERRATUM 1) — `load_book(include_bs=False)` AND a
  row/date count that only the raw BacktestResults stratum matches. The
  operator's ratification of `all`, and the reasoning behind it, is now
  consolidated into that same clause. On disk the two readings remain
  different books:

{shapes}

  The choice is LOAD-BEARING, not cosmetic — it decides how many cells are
  powered and therefore what could enter the evidence base at all — so it was
  never this module's to make. The OPERATOR made it: the ratified population is
  the LITERAL load_book(include_bs=False) call, and `real` is retained as a
  REPORTED STRATUM, not a co-primary. Both readings still print, with every
  count computed at run time; the study-level verdict is read off the ratified
  one alone. The authority, with the reasoning, is
  {RATIFICATION_SOURCE}.

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

    print_not_preregistered(args, budget)

    summaries = []
    for w in wanted:
        recs, pdiag = books[w]
        summaries.append(run_population(w, recs, pdiag, args, capital, budget,
                                        cache))

    # ── the closing section: the RATIFIED study-level result ─────────────────
    print_result(summaries)

    refusal = next((s["refusal"] for s in summaries if s["refusal"]), 0)
    return refusal


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  THE ADMITTED ARM  —  `--admitted`, filed as `hedge_portfolio-admitted`   ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# Everything below was `f5_hedging/hedge_concentration.py` until 2026-09-07,
# when that module was merged in here and DELETED. The two are the same question
# at two scopes — the whole book above, the ADMITTED book here — and the merged
# module runs whichever the arm flag selects. Nothing below prints a line the
# separate module did not print: the reports reconcile byte-identical.
#
# The move renamed only what COLLIDED. Six constants and six functions carry an
# `_ADMITTED` / `_admitted` suffix here because the whole-book arm above already
# owns the bare name with a DIFFERENT value (`TAU_GRID` 0.45/0.55/0.65 against
# 0.30/0.35/0.40, `BOOT_N` 10,000 against 2,000, `SEED` 20260831 against
# 20260829). Everything the two arms genuinely share — `hdr`, `merge`,
# `price_put`, `Cell`, `MIN_YEARS_POSITIVE`, `STRATA` — is now the single
# definition above rather than an alias, which is what the aliases said they
# were for. NO PRINTED LABEL is prefixed by the arm: the report STEM names the
# population, and prefixing would rename this registration's vocabulary.
#
# Both registrations stay immutable in substance and neither vocabulary is
# renamed. `hedge_concentration`'s Stage 1 / Stage 2 verdict grammars stay
# separate from the six study-level words above; a merged verdict would be a
# new claim.
#
# Run:
#     source .venv/bin/activate
#     python -m scripts.backtest_study run hedge_portfolio            # both arms
#     python -m scripts.backtest_study run hedge_portfolio -- --admitted

#: The flag `main()` dispatches on and `run.py`'s arm tables name.
ADMITTED_ARM_FLAG = "--admitted"

#: The admitted arm's own summary — what this module's docstring says for the
#: whole-book arm. `main_admitted()` gives argparse its first line, exactly as
#: the separate module gave argparse its `__doc__`'s.
#: Split only so no physical line runs past the linter's 120 columns; the
#: first line of the value is the separate module's first docstring line,
#: unchanged, because that is what argparse is handed.
ADMITTED_SUMMARY = ("HEDGE-CONCENTRATION — on the ADMITTED book, does "
                    "concentration predict drawdown, and only then can a "
                    "hedge cut it?")

ADMITTED_DOC = ADMITTED_SUMMARY + """

Pre-registered 2026-08-31 as `hedge_concentration`. Its registration and record
were deleted 2026-09-08 and are held in git at `44bbfb2`; the verdict row is
`research/study-map.md#hedging`. Read the registration there before quoting anything
printed here.

This is the "third reading" `hedge_portfolio`'s errata named and declined to run
under its own registration (post-ratification note 3): the SAME ratified
population and the SAME ratified prices, but an ADMISSION MODEL over which of
those plays are held at once. `hedge_portfolio` held every ratified row
concurrently; the operator's card admits at most `max_positions_per_day` new
positions a day and respects the cash and delta caps, so the book actually run
is `account_sim.simulate()`'s admitted subset — a smaller, more CONCENTRATED
book than the one `hedge_portfolio` measured.

TWO STAGES, IN A FIXED ORDER, and the second runs only if the first finds its
precondition:

  Stage 1 — ARM K, THE PRECONDITION. Does a session's cluster concentration
    predict the book's subsequent mark-to-market drawdown at all? If it does
    not, no concentration-gated hedge has a trigger to stand on, whatever its
    instrument or size, and the study stops and says so. Stage 1 does not
    depend on triggers, so it can be powered on the dates that exist.
  Stage 2 — ARM C, THE MECHANISM. The tau x f proxy-put grid, admitted through
    `account_sim.admission()`. RUN ONLY ON PRECONDITION-FOUND. The
    registration's own census predicts it is UNDERPOWERED at every tau.

Arms:

  ARM M    MEASUREMENT. The unhedged ADMITTED book on both curves —
           mark-to-market (from `daily_pnl_csv`) versus realized-on-close
           (`account_sim.equity_curve`'s basis). Runs first, gates nothing, and
           is NEVER a verdict word in this study.
  ARM K    Stage 1's precondition. x(s) = any-cluster concentration at s;
           y(s) = forward mark-to-market drawdown over the next H = 20
           sessions. Tercile contrast (primary) and Spearman rho (co-primary),
           both block-bootstrapped over non-overlapping blocks of H sessions.
  ARM KG   Gross-exposure control: ARM K re-read inside terciles of book
           gross / equity. Bar clause 4.
  ARM KN   Time-structure null: x circularly shifted against a fixed y by at
           least H sessions, 1,000 draws. ARM K must beat its 5th percentile.
  ARM K10  Registered sensitivity at H = 10. Carries no verdict and cannot
           rescue or overturn ARM K.
  ARM C    Stage 2 only. Concentration-gated proxy put, tau in {0.45, 0.55,
           0.65} x f in {0.25, 0.50, 1.00}, each leg admitted through
           `account_sim.admission()` against the ledger state at its session.
  ARM N    Stage 2 random-admission null, 200 seeds, matched on episode count,
           episode lengths and proxy mix.
  ARM R    Stage 2 always-fillable reference — a delta-equivalent SHORT in the
           proxy underlying. Clause 7's control, a feasibility floor, and never
           a recommendation.

There is NO prose-conditioned arm here, deliberately: the registration's own
plan-time census shows the hedge-flow prose survivor set on this book is
UNDERPOWERED by construction, so the prose is CENSUSED and read by nothing.

Gates: G-ERA (v4 or refuse; thin era exit 2, mismatch exit 3) · G-ADMIT (the
admitted book must reproduce `account_sim.simulate()` under `book_signature()`
equality, exit 5) · G-MTM (the mark-to-market curve reconciles at every
admitted position's exit, exit 4) · G-BLIND (every trigger and the ARM K
regressor must be computable with outcome fields stripped; a mismatch is a
DEFECT, exit 1) · G-POWER-K (Stage 1: >=60 usable sessions in each
concentration tercile over >=3 dense episodes) · G-FILL / G-POWER (Stage 2) ·
G-CENSUS (the census's INPUTS are entry-dated fields only; no failing path).

Every choice this module made that the registration does NOT commit is listed
in ONE place in the report, under NOT PRE-REGISTERED, with the clause it feeds.

Unit: the session. No annualised figure, Sharpe or time-to-recover is computed
or printed, by construction.

NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF.

Run (this is the ADMITTED arm of `hedge_portfolio`):
    source .venv/bin/activate
    python -m scripts.backtest_study run hedge_portfolio -- --admitted
"""

#: G-ADMIT's refusal, this arm's own. G-MTM (4) and G-BLIND (1) are the
#: module-level ones above, shared with the whole-book arm and never restated.
EXIT_ADMIT = 5

# ── committed constants ─────────────────────────────────────────────────────
#: Stage 1's horizon, fixed in the registration before any outcome was read.
H = 20
#: ARM K10's horizon — a DISCLOSED SENSITIVITY that carries no verdict.
H_SENS = 10

#: THIS STUDY'S OWN tau grid, fixed by its registration: the admitted book's
#: median / p75 / p90 concentration, rounded. It is deliberately NOT
#: `C.TAU_GRID` (0.30 / 0.35 / 0.40), which is `hedge_portfolio`'s grid on a
#: book more than twice as diversified. Sharing that constant would silently
#: run this study on a trigger the registration did not commit.
TAU_GRID_ADMITTED = (0.45, 0.55, 0.65)


N_CELLS_ADMITTED = len(TAU_GRID_ADMITTED) * len(F_GRID)   # 9; Bonferroni denominator, fixed here
ALPHA_ADMITTED = 0.05 / N_CELLS_ADMITTED

BOOT_N_ADMITTED = P.BOOT_N                        # 10,000 block-bootstrap resamples
KN_DRAWS = 1000                          # ARM KN, as registered
SEED_ADMITTED = 20260831

#: G-POWER-K, Stage 1's power gate, both parts registered.
MIN_TERCILE_SESSIONS = 60
MIN_DENSE_EPISODES = 3
#: Bar clause 5 — a dense episode with fewer usable sessions than this carries
#: no sign, so it neither confirms nor breaks the clause.
MIN_EPISODE_SESSIONS = 20
#: Bar clause 4 — ARM KG must keep the sign in at least this many of 3.
KG_MIN_SIGN = 2

#: The registration words exactly these four for Stage 1 and these five for
#: Stage 2. MEASUREMENT-ONLY is NOT a Stage 2 word here: ARM M is reported as a
#: measurement in every run and never as a verdict.
STAGE1_VERDICTS = ("PRECONDITION-FOUND", "PRECONDITION-NULL",
                   "GROSS-NOT-CONCENTRATION", "UNDERPOWERED")
STAGE2_VERDICTS = ("MECHANISM-FOUND", "NULL", "CONTRARY", "UNDERPOWERED",
                   "NOT EVALUABLE")

#: Stamped on any ARM K row belonging to a read the study has power-stopped —
#: `hedge_portfolio`'s errata F11 rule, applied to Stage 1. A signed number in a
#: table IS a direction in print.
UNPOWERED_NOTE_ADMITTED = "UNDERPOWERED — no direction is quoted from this row"

#: The taus `hedge_portfolio` ran, printed in this study's census FOR
#: CONTINUITY ONLY. They are not cells here and no arm reads them.
COMPARISON_TAUS = (0.30, 0.35, 0.40, 0.50)


def _num_admitted(v, spec: str = "+.4f") -> str:
    """A statistic, or `n/a` — never a bare `None`/NaN printed as text."""
    if v is None or v != v:
        return "n/a"
    return format(v, spec)


def _dollars(v) -> str:
    """A dollar statistic, or `n/a` — a NaN contrast is not a $0 contrast."""
    if v is None or v != v:
        return "n/a"
    return f"${v:,.2f}"


def _pass(flag: bool) -> str:
    return "PASS" if flag else "FAIL"


# ════════════════════════════════════════════════════════════════════════════
# The ADMITTED book
# ════════════════════════════════════════════════════════════════════════════

def load_population() -> tuple[list[dict], dict]:
    """The RATIFIED population — the literal call, and nothing around it.

    `hedge_portfolio`'s operator ratification (2026-08-31) fixes
    `load_book(include_bs=False)` as the population, and `account_sim`'s own
    default loader makes byte-for-byte the same call. There is no `--sources`
    switch here: this study's registration names ONE population and pooling or
    stratifying it would be a different study.
    """
    return load_book(include_bs=False)


def simulate_admitted(recs: list[dict], st, label: str) -> tuple[list, A.Sim]:
    """`account_sim.simulate()` on `recs`, in the shape `account_sim.main()` runs.

    ARM H OFF (`bear_by_day=None` AND `cfg.hedge=False`), no compounding, no
    `--live-select` ranker, a FRESH replay memo. Those are the arm selections
    the registration fixes; every sizing number comes from
    `config/account-sim.yml` through `Settings.cfg()`.
    """
    day_lists = P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)
    sim = A.simulate(day_lists, st.cfg(label, compound=False, hedge=False),
                     bear_by_day=None, cache=A.new_cache())
    return day_lists, sim


def admitted_positions(sim: A.Sim) -> list[A.Pos]:
    """The held book: `taken` + `taken_downsized`, never the ARM H sleeve.

    `sim.taken` carries hedge positions too when ARM H is on; it is off here,
    so the filter is a guard rather than a filter, and it is kept because a
    silent sleeve position would enter the concentration denominator.
    """
    return [p for p in sim.taken if not p.hedge]


def gate_admit(sim: A.Sim, recs: list[dict], st, label: str) -> int:
    """G-ADMIT: this module's admitted book IS `account_sim.simulate()`'s.

    `portfolio_delta`'s G-EQUIV, applied here. The reference is built the way
    `account_sim.main()` builds it — the same loader output, the same
    `ordered_by_day` ladder, `st.cfg(...)` with compounding and the sleeve off,
    a fresh `new_cache()` — and the two books must be identical under
    `book_signature()`: same positions, same order, same contract counts, same
    R, same dollars, same exit reasons.

    A drifted local admission is a finding ABOUT THE DRIFT. The run refuses
    (exit 5) rather than reporting a concentration series computed on a book
    `account_sim` never held.
    """
    hdr("G-ADMIT — the admitted book must reproduce account_sim.simulate()")
    print("""  This study's whole population is an ADMISSION MODEL: the ratified rows
  thinned by the operator's top-3-per-day rule and the cash / per-position /
  net delta caps. If this module's simulate() call has drifted from the one
  `account_sim` runs, every figure below describes a book nobody held. The
  reference is rebuilt the way account_sim.main() builds it and compared under
  book_signature() equality — positions, order, contracts, R, dollars, exit
  reasons.""")
    _day_lists, ref = simulate_admitted(recs, st, f"G-ADMIT {label}")
    got_sig, ref_sig = A.book_signature(sim), A.book_signature(ref)
    same = got_sig == ref_sig
    print(f"\n  account_sim.simulate (reference)  {len(ref.taken):>4} positions  "
          f"${sum(p.dollars for p in ref.taken):>10,.0f}")
    print(f"  this module's admitted book       {len(sim.taken):>4} positions  "
          f"${sum(p.dollars for p in sim.taken):>10,.0f}")
    n_diff = sum(1 for x, y in zip(ref_sig, got_sig) if x != y)
    print(f"  signatures: {len(ref_sig)} vs {len(got_sig)}, differing {n_diff}"
          f"  -> {'IDENTICAL' if same else 'DIVERGED'}")
    if same:
        print("  G-ADMIT PASS.")
        return 0
    for x, y in zip(ref_sig, got_sig):
        if x != y:
            print(f"    FIRST DIVERGENCE  account_sim {x}")
            print(f"                      this module {y}")
            break
    print(f"\nG-ADMIT FAILURE — the admitted book is not account_sim's. "
          f"Exit {EXIT_ADMIT}.")
    return EXIT_ADMIT


def admission_census(sim: A.Sim, day_lists, label: str) -> dict:
    """Candidates / admitted / skipped-by-reason, every count from this run.

    The registration requires the SKIPPED census printed NEXT TO the admitted
    one, so a reader sees what was NOT held, with the partition check
    (admitted + skipped == ladder-eligible candidates) stated rather than
    assumed.
    """
    rows = A.positions_rows(label, "ADMITTED", sim)
    adm = [r for r in rows if r["status"] in ("taken", "taken_downsized")]
    skipped = Counter(r["reject_reason"] for r in rows
                      if str(r["status"]).startswith("skipped:"))
    dates = sorted({r["date"] for r in adm})
    return dict(
        n_candidates=sum(len(r) for _d, r in day_lists),
        n_candidate_dates=len(day_lists),
        n_admitted=len(adm),
        n_taken=sum(1 for r in adm if r["status"] == "taken"),
        n_downsized=sum(1 for r in adm if r["status"] == "taken_downsized"),
        dates=dates,
        contracts=sum(int(r["contracts"]) for r in adm),
        skipped=dict(skipped),
        n_skipped=sum(skipped.values()),
    )


# ════════════════════════════════════════════════════════════════════════════
# The concentration layer over the admitted book
# ════════════════════════════════════════════════════════════════════════════

def concentration_layer(positions: list[A.Pos]) -> tuple[list[dict], dict, list]:
    """`(records, occupancy, series)` for an admitted position list.

    Occupancy is the SIM's `[entry_sess, exit_sess]` window over real trading
    sessions (`lib/concentration.occupancy_from_positions`), NOT
    `open_book_by_session`, which bounds the span from the ROW's stored
    `days_held` — the sim re-sizes and re-exits what it admits, so the row's
    span describes a different position. Contracts are the SIM's sized ones
    (`contracts_by_position`). Both are library helpers taking parameters; the
    measure itself (`session_concentration`) is untouched.
    """
    recs = [p.rec for p in positions]
    occ = C.occupancy_from_positions(positions)
    series = C.concentration_series(recs, occupancy=occ,
                                    contracts_fn=C.contracts_by_position(positions))
    return recs, occ, series


def blinded_positions(positions: list[A.Pos]) -> list[A.Pos]:
    """Each admitted position re-wrapped around a `BlindRec` of its record.

    G-BLIND blinds the RECORDS THE TRIGGER LAYER READS, not the simulator: the
    sim REPLAYS a book that already happened and reads outcomes by
    construction, so blinding it would test nothing about a trigger. What must
    survive blinding is the concentration series and every trigger derived from
    it. Each blind position keeps the sighted one's entry/exit window and
    contract count — those are the replay fixture — and carries a record whose
    outcome keys RAISE on read. `session_concentration` reads only ticker,
    delta, contracts and entry_underlying, so it is safe under `BlindRec`; a
    read of anything else raises `LookaheadError` rather than passing quietly.
    """
    blind = A.blind_records([p.rec for p in positions])
    out: list[A.Pos] = []
    for p, b in zip(positions, blind):
        out.append(A.Pos(rec=b, contracts=p.contracts, reserved=p.reserved,
                         dn=p.dn, entry_sess=p.entry_sess,
                         exit_sess=p.exit_sess, days_held=p.days_held,
                         R=p.R, dollars=p.dollars, exit_reason=p.exit_reason,
                         downsized=p.downsized, hedge=p.hedge))
    return out


def trigger_fingerprint(series, taus) -> dict:
    """Everything G-BLIND compares: the session set, the x values, the sets.

    Byte-comparable by construction — tuples of dates and floats, no objects.
    """
    return {
        "sessions": tuple(sc.session for sc in series),
        "x": tuple(sc.concentration for sc in series),
        "x_constituent": tuple(sc.constituent_concentration for sc in series),
        "strata": tuple(sc.stratum for sc in series),
        "triggered": {
            (tau, measure): tuple(C.triggered_sessions(series, tau, measure))
            for tau in taus for measure in C.MEASURES
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# Stage 1 — ARM K and its controls
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Aligned:
    """The two parallel series ARM K is read from, plus what alignment cost.

    `idx` maps each kept row back to its index on the CURVE's own session axis,
    so a cut or an episode can be expressed as a set of axis positions rather
    than re-derived from dates twice.
    """
    sessions: list[_date]
    idx: list[int]
    x: list[float]
    y: list[float | None]
    gross: list[float]
    n_axis: int
    n_axis_unmatched: int
    n_series_off_axis: int
    n_no_gross: int


def align(axis: list[_date], levels: list[float], series, sess_series: dict,
          capital: float, horizon: int) -> Aligned:
    """x, y and the gross control on ONE index, the curve's own session axis.

    The forward window is counted on the CURVE's axis — `forward_drawdown` runs
    over the whole `levels` series first — so y(s) always means "the next
    `horizon` sessions of the book's equity", whatever this alignment drops.
    Only then are rows without a concentration reading removed from ARM K's
    ROWS; they stay inside every forward window they fall in.
    """
    y_all = F.forward_drawdown(levels, horizon)
    conc = {sc.session: sc.concentration for sc in series}
    sessions, idx, xs, ys, gross = [], [], [], [], []
    n_no_gross = 0
    for i, s in enumerate(axis):
        if s not in conc:
            continue
        cell = sess_series.get(s)
        if cell is None:
            n_no_gross += 1
            continue
        sessions.append(s)
        idx.append(i)
        xs.append(conc[s])
        ys.append(y_all[i])
        gross.append(cell["gross"] / capital)
    on_axis = set(axis)
    return Aligned(sessions=sessions, idx=idx, x=xs, y=ys, gross=gross,
                   n_axis=len(axis),
                   n_axis_unmatched=sum(1 for s in axis if s not in conc),
                   n_series_off_axis=sum(1 for sc in series
                                         if sc.session not in on_axis),
                   n_no_gross=n_no_gross)


def tercile_means(x, y) -> list[float]:
    """Mean y inside each rank tercile of x — the numbers behind the contrast."""
    labels = F.rank_groups(x, 3)
    out = []
    for g in range(3):
        vals = [float(b) for lab, b in zip(labels, y) if b is not None and lab == g]
        out.append(statistics.fmean(vals) if vals else float("nan"))
    return out


def subset(al: Aligned, keep: set[int]) -> tuple[list[float], list[float | None]]:
    """`(x, y)` restricted to the kept ROW positions of `al`.

    Terciles are re-assigned inside the subset by `tercile_contrast`, which is
    what a cut means: "does the relationship hold among these sessions", not
    "do the whole series' terciles still separate here".
    """
    xs = [v for i, v in enumerate(al.x) if i in keep]
    ys = [v for i, v in enumerate(al.y) if i in keep]
    return xs, ys


def run_arm_k(al: Aligned, horizon: int, block: int, boot_n: int, seed: int
              ) -> dict:
    """ARM K's two reads and their block-bootstrap intervals.

    The block is the HORIZON, in sessions: neighbouring y's share up to
    `horizon - 1` of their forward window, so a row-level resample would treat
    `horizon` nearly-identical outcomes as independent draws and understate the
    variance. A block the length of the window keeps each outcome inside the
    block that generated it.
    """
    counts = F.group_counts(al.x, al.y, 3)
    contrast = F.tercile_contrast(al.x, al.y)
    rho = F.spearman(al.x, al.y)
    boot_c = F.block_bootstrap(al.x, al.y, F.tercile_contrast, block=block,
                               n_boot=boot_n, seed=seed)
    boot_r = F.block_bootstrap(al.x, al.y, F.spearman, block=block,
                               n_boot=boot_n, seed=seed)
    return dict(horizon=horizon, block=block, n_usable=sum(counts),
                counts=counts, means=tercile_means(al.x, al.y),
                contrast=contrast, rho=rho, boot_contrast=boot_c,
                boot_rho=boot_r)


def run_arm_kn(al: Aligned, min_shift: int, draws: int, seed: int) -> dict:
    """ARM KN — the time-structure null for both reads.

    A circular shift preserves the autocorrelation of BOTH series, which a row
    shuffle destroys; the 5th/95th percentiles of the rotated statistic are the
    band a real relationship must fall outside. `min_shift` is the horizon, so
    every rotation moves each x at least a full forward window away from its
    own y in both directions.
    """
    out: dict = {}
    for name, fn in (("contrast", F.tercile_contrast), ("rho", F.spearman)):
        try:
            out[name] = F.circular_shift_null(al.x, al.y, fn,
                                              min_shift=min_shift, draws=draws,
                                              seed=seed)
        except ValueError as exc:              # too few rows to rotate
            out[name] = None
            out[f"{name}_error"] = str(exc)
    return out


def run_arm_kg(al: Aligned) -> dict:
    """ARM KG — ARM K's contrast re-read inside terciles of gross / equity.

    A concentrated book is often just a bigger book. A concentration effect
    that vanishes once gross is held roughly constant is a gross-exposure
    effect wearing a different name — bar clause 4.
    """
    contrasts = F.within_group_stats(al.x, al.y, al.gross, F.tercile_contrast)
    return dict(contrasts=contrasts,
                gross_terciles=F.group_counts(al.gross, al.y, 3))


def episode_spans(dense_eps) -> list[tuple[_date, _date, int]]:
    """`(first, last, n_dates)` per dense episode of admitted SIGNAL dates."""
    return [(_date.fromisoformat(e[0]), _date.fromisoformat(e[-1]), len(e))
            for e in dense_eps]


def run_episode_signs(al: Aligned, spans, point: float) -> list[dict]:
    """Bar clause 5 — the contrast re-read inside each dense episode's SPAN.

    "Inside an episode" is by DATE SPAN: every session between the episode's
    first and last admitted signal date inclusive. The episode is a run of
    admitted signal DATES, so it names a stretch of calendar; the book it
    describes is open across that stretch, including the sessions between two
    consecutive signal dates. An episode with fewer than
    `MIN_EPISODE_SESSIONS` usable sessions carries NO sign and is reported
    rather than counted either way.
    """
    out = []
    for lo, hi, n_dates in spans:
        keep = {i for i, s in enumerate(al.sessions) if lo <= s <= hi}
        usable = sum(1 for i in keep if al.y[i] is not None)
        xs, ys = subset(al, keep)
        c = F.tercile_contrast(xs, ys) if usable else float("nan")
        out.append(dict(lo=lo, hi=hi, n_dates=n_dates, n_sessions=len(keep),
                        n_usable=usable, contrast=c,
                        counted=usable >= MIN_EPISODE_SESSIONS,
                        keeps_sign=bool(F.sign_kept([c], point))))
    return out


def run_window_cuts(al: Aligned, point: float) -> dict:
    """Bar clause 6 — the two mandatory ex-window cuts.

    `protocol.window_cuts` is row-shaped, so the session axis is handed to it
    as one row per session and the cut is applied by DROPPING that window's
    sessions from ARM K's rows. The forward windows were computed on the full
    curve before the cut, exactly as in the alignment above: a cut changes
    which sessions are READ, never what the book's next 20 sessions were.
    """
    rows = [{"date": s.isoformat(), "i": i} for i, s in enumerate(al.sessions)]
    out = {}
    for name, kept in P.window_cuts(rows).items():
        if name == "ALL":
            continue
        keep = {r["i"] for r in kept}
        xs, ys = subset(al, keep)
        c = F.tercile_contrast(xs, ys)
        out[name] = dict(n=len(keep),
                         n_usable=sum(1 for i in keep if al.y[i] is not None),
                         contrast=c, keeps_sign=bool(F.sign_kept([c], point)))
    return out


def stage1_verdict(res: dict) -> str:
    """The registration's Stage 1 word, mapped exactly as it words them.

    * G-POWER-K fails                        -> UNDERPOWERED (no direction).
    * every clause clears                    -> PRECONDITION-FOUND.
    * clauses 1-3 clear and clause 4 fails   -> GROSS-NOT-CONCENTRATION.
    * powered, and anything else fails       -> PRECONDITION-NULL.

    Pure, so the mapping is unit-testable without a book: `res` is
    `{"powered": bool, "c1".."c6": bool}` and nothing else is read.
    """
    if not res.get("powered"):
        return "UNDERPOWERED"
    c = [bool(res.get(f"c{i}")) for i in range(1, 7)]
    if all(c):
        return "PRECONDITION-FOUND"
    if c[0] and c[1] and c[2] and not c[3]:
        return "GROSS-NOT-CONCENTRATION"
    return "PRECONDITION-NULL"


# ════════════════════════════════════════════════════════════════════════════
# Stage 2 — the overlay ledger
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class OpenLeg:
    """One admitted hedge leg's footprint on the overlay ledger."""
    first: _date
    last: _date
    reserved: float
    dn: float


class Overlay:
    """The ledger a Stage 2 hedge leg is admitted against.

    The registration says the hedge is "admitted THROUGH
    `account_sim.admission()` after the day's picks in the ARM H pattern". The
    SIGNAL BOOK IS HELD FIXED — the counterfactual has to be the same book, or
    the arm would be measuring a different selection rather than an overlay —
    so the hedge never displaces a pick and never counts against
    `max_positions_per_day`. What it does consume is the ledger's headroom AT
    ITS OWN SESSION:

      cash     = capital - reserved(s) from `account_sim.session_series`
                 - reserved of hedge legs already open on s
      net_open = net(s) + signed delta notional of hedge legs open on s

    A refused leg is SKIPPED and counted by its binding constraint; a leg that
    sizes below one contract is SKIPPED and counted, never floored to one.
    Nothing is fabricated and no episode is dropped: the session is carried at
    f=0 and the next session tries again.
    """

    def __init__(self, capital: float, sess_series: dict, cfg) -> None:
        self.capital = float(capital)
        self.ss = sess_series
        self.cfg = cfg
        self.legs: list[OpenLeg] = []
        self.refused: Counter = Counter()
        self.admitted = 0

    def state(self, s: _date) -> tuple[float, float]:
        cell = self.ss.get(s) or {"reserved": 0.0, "net": 0.0}
        live = [g for g in self.legs if g.first <= s <= g.last]
        cash = self.capital - cell["reserved"] - sum(g.reserved for g in live)
        net_open = cell["net"] + sum(g.dn for g in live)
        return cash, net_open

    def admit(self, s: _date, last: _date, reserved: float,
              dn: float) -> tuple[bool, str | None]:
        cash, net_open = self.state(s)
        ok, why = A.admission(reserved, dn, cash, net_open, self.cfg)
        if ok:
            self.legs.append(OpenLeg(s, last, reserved, dn))
            self.admitted += 1
        else:
            self.refused[why or "unknown"] += 1
        return ok, why


def new_diag_admitted() -> dict:
    """`hedge_portfolio`'s planning diagnostic plus this study's admission ones."""
    d = new_diag()
    d.update(admission_refused=0, no_entry_delta=0)
    return d


def plan_episode_admitted(window, proxies, f: float, budget: float, rule: str,
                          diag: dict, overlay: Overlay) -> Leg:
    """`hedge_portfolio.plan_episode`, with every leg run past the overlay ledger.

    Identical in every other respect — the per-session re-pick, the rotation at
    a cluster change, the roll at expiry, the SKIP of a sub-one-contract size —
    so the only difference between this study's ARM C and `hedge_portfolio`'s is
    the admission the registration adds.

    A put with no cached entry greek cannot be admitted: its delta notional is
    UNKNOWN, and admitting it at a fabricated 0.0 would consume no net-delta
    headroom for a position that in fact carries some. It is counted and the
    session is carried at f=0.
    """
    leg = Leg(episode=tuple(window))
    held: list[str] = []
    diag["sessions_unhedgeable"] += sum(1 for p in proxies if p is None)
    runs = proxy_runs(window, proxies)
    for r, (proxy, days, n_active) in enumerate(runs):
        if r:
            diag["rotations"] += 1
        cur_pick: HI.PutPick | None = None
        cur_c = 0
        cur_days: list[_date] = []
        for k, day in enumerate(days):
            if cur_pick is not None and day > cur_pick.expiry:
                leg.segments.append(Segment(cur_pick, cur_c,
                                            tuple(cur_days + [day]), True))
                diag["rolls"] += 1
                cur_pick, cur_c, cur_days = None, 0, []
            if cur_pick is None:
                if k >= n_active:
                    continue        # a close-only session never opens a hedge
                pick = HI.select_put(proxy, day, rule)
                if pick is None:
                    diag["sessions_no_fill"] += 1
                    continue
                c = _contracts_for(pick.entry_mark * HI.SHARES_PER_CONTRACT,
                                   f, budget)
                if c < 1:
                    diag["sessions_sub_one"] += 1
                    continue
                share_delta = HI.entry_delta(pick, c)
                if share_delta is None:
                    diag["no_entry_delta"] += 1
                    continue
                cost = HI.entry_cost(pick, c)
                last = min(pick.expiry, days[-1])
                ok, _why = overlay.admit(day, last, cost,
                                         share_delta * pick.spot)
                if not ok:
                    diag["admission_refused"] += 1
                    continue
                cur_pick, cur_c, cur_days = pick, c, [day]
                leg.cost += cost
                diag["opens"] += 1
                if proxy not in held:
                    held.append(proxy)
                continue
            cur_days.append(day)
        if cur_pick is not None:
            leg.segments.append(Segment(cur_pick, cur_c, tuple(cur_days),
                                        False))
    leg.proxies = tuple(held)
    if leg.segments:
        leg.label = leg.segments[0].pick.label()
    return leg


def episode_leg_admitted(episode, by_session, universe, f, budget, rule, diag,
                         overlay) -> Leg:
    window, proxies = episode_plan(episode, by_session, universe)
    if not any(p is not None and p != CARRY for p in proxies):
        diag["episodes_all_unhedgeable"] += 1
    return plan_episode_admitted(window, proxies, f, budget, rule, diag, overlay)


def build_cell_admitted(tau: float, f: float, rule: str, triggered, eps, by_session,
                        budget: float, universe, overlay_factory,
                        stratum: str = STRATUM_POOLED, arm: str = "C") -> Cell:
    """One arm x tau x f x stratum cell, planned through a FRESH overlay ledger.

    Fresh per cell, because the ledger state a leg is admitted against must be
    the one THIS cell's own earlier legs produced — a shared ledger would let
    one cell's hedges refuse another's. No episode is dropped; a session inside
    one that carries no hedgeable cluster, no fill, no sizeable contract or no
    admission headroom is carried at f=0 and counted on the diagnostic.
    """
    diag = new_diag_admitted()
    overlay = overlay_factory()
    cell = Cell(arm=arm, tau=tau, f=f, rule=rule, stratum=stratum,
                n_sessions=len(triggered), n_episodes=len(eps),
                n_book_dates=0, powered=len(eps) >= MIN_TRIGGER_DATES,
                diag=diag, triggered=list(triggered), eps=list(eps))
    for ep in eps:
        leg = episode_leg_admitted(ep, by_session, universe, f, budget, rule,
                                   diag, overlay)
        cell.ep_hedges.append(price_put(leg))
        if leg.segments:
            cell.legs.append(leg)
    cell.hedge = merge(cell.ep_hedges)
    diag["admission_refused_by_reason"] = dict(overlay.refused)
    diag["admitted_legs"] = overlay.admitted
    return cell


def arm_n_band_admitted(eps, by_session, universe, axis, base_daily, capital, f, budget,
                        rule, metrics, overlay_factory, n_seeds=N_SEEDS, seed=SEED_ADMITTED
                        ) -> dict:
    """ARM N — matched random hedging, admitted through the SAME ledger.

    the whole-book arm's `arm_n_band`'s matching, re-planned through this study's
    overlay: episode COUNT, episode LENGTHS and the PER-SESSION PROXY SEQUENCE
    at uniform random starts. A null planned WITHOUT the admission the arm is
    subject to would stop being a null for that arm, so each seed gets its own
    fresh ledger exactly as each cell does.

    Returns `{metric: (p05, p95)}`. Both tails: the 95th is clause 3's bar for
    a positive and the 5th is the mirrored clause for a CONTRARY.
    """
    shapes = [episode_shape(ep, by_session) for ep in eps]
    shapes = [s for s in shapes if any(p is not None for p in s)]
    uni = list(universe)
    draws: dict[str, list[float]] = {m: [] for m in metrics}
    if not shapes or len(uni) < 2:
        return {m: (float("nan"), float("nan")) for m in metrics}
    rng = random.Random(seed)
    base = M.path_stats(curve_of(axis, base_daily), capital)
    for _ in range(n_seeds):
        legs = []
        diag = new_diag_admitted()
        overlay = overlay_factory()
        for shape in shapes:
            length = len(shape)
            if length > len(uni):
                continue
            start = rng.randrange(0, len(uni) - length + 1)
            window = hold_window(uni[start:start + length], uni)
            proxies = list(shape) + [CARRY] * (len(window) - length)
            legs.append(plan_episode_admitted(window, proxies, f, budget, rule,
                                              diag, overlay))
        hd = hedged_daily(axis, base_daily,
                          merge(price_put(leg) for leg in legs))
        hedged = M.path_stats(curve_of(axis, hd), capital)
        for m in metrics:
            draws[m].append(improvement(base, hedged, m))
    return {m: (pctile(v, 0.05), pctile(v, 0.95)) for m, v in draws.items()}


def leave_one_date_out_admitted(cell: Cell, by_session, universe, axis, base_daily,
                                capital, base, metrics, f, budget, rule,
                                overlay_factory) -> dict:
    """Clause 6, folded over TRIGGER DATES — `hedge_portfolio`'s errata F10 rule.

    A FOLD IS ONE TRIGGER DATE. Removing a date removes it from the trigger, so
    the episode containing it is re-planned as the (up to two) contiguous
    sub-episodes that survive. Re-planning goes through a fresh overlay, since
    a fold's ledger is not the full cell's.
    """
    out = {m: [] for m in metrics}
    where = {}
    for i, ep in enumerate(cell.eps):
        for s in ep:
            where[s] = i
    for d in cell.triggered:
        i = where.get(d)
        parts = [h for j, h in enumerate(cell.ep_hedges) if j != i]
        diag = new_diag_admitted()
        overlay = overlay_factory()
        if i is not None:
            ep = cell.eps[i]
            for piece in (tuple(s for s in ep if s < d),
                          tuple(s for s in ep if s > d)):
                if piece:
                    parts.append(price_put(episode_leg_admitted(
                        piece, by_session, universe, f, budget, rule, diag,
                        overlay)))
        hd = hedged_daily(axis, base_daily, merge(parts))
        st = M.path_stats(curve_of(axis, hd), capital)
        for m in metrics:
            out[m].append(improvement(base, st, m))
    return out


def stage2_dispatch(verdict: str, run_stage2, print_census) -> str | None:
    """Stage 2 runs ONLY on PRECONDITION-FOUND — the registration's anti-tuning
    clause, in one testable place.

    "A hedge tested on a trigger that carries no information is a hedge tested
    on noise", and a later reader may not run it by hand and quote it either.
    On any other word the trigger census is printed FOR THE RECORD and no cell
    is evaluated; the function returns None so no Stage 2 word exists to quote.
    """
    if verdict == STAGE1_VERDICTS[0]:          # PRECONDITION-FOUND
        return run_stage2()
    print_census()
    print(f"\n  STAGE 2 — NOT RUN (Stage 1 {verdict})")
    return None


# ════════════════════════════════════════════════════════════════════════════
# Report sections
# ════════════════════════════════════════════════════════════════════════════

def print_not_preregistered_admitted(args, capital: float, budget: float) -> None:
    """The ONE place every discretionary choice in this module is listed.

    `hedge_portfolio`'s errata F14 discipline: every choice this module made
    that the registration does NOT commit is listed here, with what it is and
    which clause it feeds. A choice that feeds a clause and is not on this list
    is a defect. None of these may be read as findings, and none is tuned —
    they are fixed in code, stated here, and not revisited after an outcome.
    """
    hdr("NOT PRE-REGISTERED — every discretionary choice in this module, in "
        "one place")
    print(f"""  The registration
  (hedge_concentration's, deleted 2026-09-08, held in git at 44bbfb2) fixes the
  population and the admission model, H = 20, the tercile rule, the tau grid
  {TAU_GRID_ADMITTED}, the f grid {F_GRID}, the fill rules and DTE windows, the
  >=60% fill gate, the >=25 trigger-date floor, G-POWER-K's 60/3, the
  Bonferroni denominator of {N_CELLS_ADMITTED}, both clause sets and both verdict
  vocabularies. NONE of those appears below. What appears below is everything
  ELSE this module had to decide in order to run at all.

  THE BOOK AND ITS AXIS
  1  G-MTM'S TARGET IS `TARGET_POSITION`, not the row's stored column. The
     registration words G-MTM as "the mark-to-market curve reconciles to the
     realized-on-close curve at every ADMITTED POSITION's exit". The sim
     RE-SIZES and RE-EXITS what it admits, so the row's stored
     realized_pnl_abs describes a different position by construction and the
     stored-target check cannot hold on this book. The gate is therefore read
     on the POSITION target — daily_pnl_csv at the replay's exit index times
     the replay's contracts, versus the dollars the FROZEN harness booked —
     which is a check between two separate computations but is NOT
     hedge_portfolio's two-STORED-columns check, and this report never calls it
     that. The stored-target reconciliation is printed BESIDE it as a
     disclosure, with the re-sized and re-exited counts computed at run time.
     Feeds: G-MTM, and through the curve every Stage 1 and Stage 2 read.
  2  OCCUPANCY IS THE SIM'S WINDOW. A position is open on the trading sessions
     in the SIM's [entry_sess, exit_sess], via the new
     lib/concentration.occupancy_from_positions(). lib/concentration's own
     open_book_by_session() bounds the span from the ROW's stored days_held,
     which is the wrong window for a re-exited position. Contracts are the
     sim's sized ones (contracts_by_position). Both are library helpers taking
     parameters; session_concentration itself is untouched.
     Feeds: x(s), every trigger, and G-BLIND.
  3  ALIGNMENT OF x TO THE CURVE AXIS. y is computed by forward_drawdown over
     the WHOLE curve axis first, so y(s) always means the book's next H
     sessions of equity. Only then are axis sessions with no concentration
     reading dropped from ARM K's ROWS — they remain inside every forward
     window they fall in. The counts of dropped and off-axis sessions are
     printed; a curve axis is `Trade.grid`, i.e. WEEKDAYS, while the
     concentration calendar is the SPY OHLC session list, so a market holiday
     inside a position's grid is exactly the kind of row this drops.
     Feeds: ARM K, KG, KN, K10 and clauses 1-6.
  4  ARM KG'S GROSS IS account_sim.session_series(sim)['gross'] / capital,
     joined to the curve axis by session. A kept session missing from
     session_series would have no gross to control on and is dropped and
     counted (it should be zero: session_series walks the same
     [entry_sess, exit_sess] windows on the same grids).   Feeds: clause 4.

  THE STAGE 1 STATISTICS
  5  BLOCK LENGTH = H. The block bootstrap resamples NON-OVERLAPPING blocks of
     exactly the horizon: the forward windows overlap by construction, so a
     row-level resample would treat H nearly-identical outcomes as H
     independent ones. The registration says "non-overlapping blocks of H
     sessions" for ARM K and says nothing for ARM K10, where the block is set
     to that arm's own horizon ({H_SENS}) by the same argument.
     Feeds: clauses 1 and 2, and ARM K10's disclosed interval.
  6  ARM KN'S OFFSET RANGE is [H, n - H] rows, drawn uniformly, so every
     rotation moves each x at least a full forward window away from its own y
     in BOTH directions. The registration fixes "at least H" and one end only.
     Feeds: clause 3.
  7  THE TERCILE TIE RULE is rank with ties broken by POSITION (a stable
     sort), so the three groups differ in size by at most one however many x
     values coincide. Terciles are assigned over EVERY x, including rows whose
     y is missing, so "the top tercile" means the top third of the whole
     series rather than of the usable part. The registration says "terciles by
     x over the universe" and names no tie-break.   Feeds: clauses 1, 4, 5, 6.
  8  "INSIDE A DENSE EPISODE" IS A DATE SPAN — every session between the
     episode's first and last admitted signal date inclusive. A dense episode
     is a run of signal DATES, so it names a stretch of calendar and the book
     it describes is open across all of it. "20 usable sessions" counts rows
     inside that span whose y exists (a full forward window). An episode below
     20 carries NO sign and is reported rather than counted either way.
     Feeds: clause 5 and G-POWER-K's episode floor.
  9  THE EX-WINDOW CUTS are applied by DROPPING that window's sessions from
     ARM K's rows, through protocol.window_cuts on one row per session. The
     forward windows were computed before the cut, as in 3: a cut changes
     which sessions are READ, never what the book's next H sessions were.
     Feeds: clause 6.
 10  ARM K10 IS A SENSITIVITY and carries no verdict. It is printed beside ARM
     K, at H = {H_SENS} and block {H_SENS}, and cannot rescue or overturn it. Its rows
     carry the same power stamp as ARM K's when G-POWER-K fails.
     Feeds: NOTHING.

  STAGE 2 — THE OVERLAY LEDGER (used only on PRECONDITION-FOUND)
 11  THE SIGNAL BOOK IS HELD FIXED. The counterfactual must be the same book,
     so a hedge never displaces a pick and never counts against
     max_positions_per_day. The registration says "admitted THROUGH
     account_sim.admission() after the day's picks in the ARM H pattern" and
     leaves the ledger arithmetic open.   Feeds: ALL SEVEN Stage 2 clauses.
 12  THE LEDGER STATE A LEG IS ADMITTED AGAINST, at its own session s:
       cash     = capital ${capital:,.0f} - reserved(s) from session_series
                  - reserved of hedge legs already open on s
       net_open = net(s) + signed delta notional of hedge legs open on s
     and then account_sim.admission(reserved=leg debit, dn_signed=leg delta
     notional, cash, net_open, cfg). A REFUSED leg is SKIPPED and counted by
     its binding constraint; the session is carried at f=0 and the next
     session tries again.   Feeds: ALL SEVEN Stage 2 clauses.
 13  A LEG'S LEDGER SPAN is [open session, min(expiry, last session of the
     same-proxy run)] — the sessions the leg is actually carried over. A roll
     inside an episode is a NEW admission at the roll session.
     Feeds: ALL SEVEN Stage 2 clauses.
 14  A PUT WITH NO CACHED ENTRY GREEK CANNOT BE ADMITTED. Its delta notional
     is unknown, and admitting it at a fabricated 0.0 would consume no
     net-delta headroom for a position that carries some — the standing "a
     missing greek is None, never 0.0" rule. Counted, session carried at f=0.
     Feeds: ALL SEVEN Stage 2 clauses.
 15  SUB-ONE-CONTRACT SIZING IS A SKIP, never a floor to 1: contracts =
     int(f x risk_contracts(put debit, ${budget:,.0f})). account_sim ARM H's convention,
     which the registration names explicitly.   Feeds: ALL SEVEN clauses.
 16  ARM N IS PLANNED THROUGH THE SAME OVERLAY, a fresh ledger per seed. A
     null free of the admission the arm is subject to would stop being a null
     for that arm.   Feeds: clause 3.
 17  EVERYTHING hedge_portfolio ALREADY DISCLOSED AND THIS MODULE INHERITS by
     importing its planner: rolling at expiry (settled at expiry intrinsic
     against that day's close, walked back up to {SETTLE_LOOKBACK_DAYS} calendar days), the
     holding window extended one session past the episode, the per-session
     re-pick and rotation rule, the band-rule tie-break (|DTE-45|, then |K-S|,
     then (expiry, strike)), DIRECT_MAJORITY = {C.DIRECT_MAJORITY:.2f}, the read-metric
     fall-back to ulcer, the chronological moving-block bootstrap for the
     Stage 2 CI, a fold being one trigger DATE, and G-FILL's denominator being
     CACHE-CONDITIONED (the instrument universe is the option history cache,
     so the rates measure cache coverage rather than market liquidity).
     Feeds: ALL SEVEN Stage 2 clauses.

  THINGS THAT FEED NO CLAUSE, LISTED SO THE LIST IS COMPLETE
 18  THE COMPARISON TAUS {COMPARISON_TAUS} are printed in the census for
     continuity with hedge_portfolio. They are NOT cells here, no arm reads
     them, and the registration's grid may not be moved after commit.
 19  THE HEDGE-FLOW PROSE is parsed and censused only. No arm in this study
     reads it — see the registration's "What this is NOT".
 20  SEEDS: block bootstrap and ARM KN and ARM N all take seed {SEED_ADMITTED}, printed
     wherever a band is. {args.boot} Stage 2 resamples per cell.""")


def print_census(series, universe, adm_dates, positions, sess_series,
                 capital: float, st, dense_eps, spans) -> None:
    """G-CENSUS — the trigger and tercile census, from entry-dated INPUTS.

    States the INPUT property, as `hedge_portfolio`'s errata F13 fixed it: every
    number here is computed from ticker / delta / contracts / entry_underlying,
    plus `days_held` through the OCCUPANCY layer alone — the replay fixture of
    a book that already happened, not a trigger input. G-CENSUS HAS NO FAILING
    PATH: it is a discipline, not a check. The gate that refuses on lookahead
    is G-BLIND, above.
    """
    hdr("G-CENSUS — the trigger and tercile census; its INPUTS are entry-dated "
        "fields only")
    print("""  WHAT IS TRUE, stated as such. Every number in this section is computed from
  ENTRY-DATED fields — ticker, delta, contracts, entry_underlying — plus
  `days_held` through the OCCUPANCY layer alone (here, the SIM's own
  [entry_sess, exit_sess]), which is the replay fixture of a book that already
  happened and is not a trigger input. That is the property this gate is for.

  WHAT IS NOT TRUE would be a claim about PRINT ORDER: G-MTM and ARM M print
  outcome-derived dollars above this line, and G-MTM must read an outcome by
  construction. G-CENSUS HAS NO FAILING PATH. The gate that can refuse on
  lookahead is G-BLIND, above.""")

    n = len(series)
    sub("per-session open book (ADMITTED positions, at the SIM's contracts)")
    print(f"  session universe                     {n}   "
          f"{universe[0]} .. {universe[-1]}")
    _q("concurrent open positions", [sc.n_open for sc in series])
    _q("priced positions per session", [sc.n_priced for sc in series])
    print(f"  sessions holding an unpriced position {sum(1 for sc in series if sc.n_unpriced)}"
          f"   (position-sessions {sum(sc.n_unpriced for sc in series)})")
    gross = [sc.book_gross for sc in series]
    _q("book gross ($)", gross, "12,.0f")
    _q("book gross / equity (x)", [g / capital for g in gross])
    print(f"  equity denominator = config/account-sim.yml account.capital "
          f"${capital:,.0f}")

    sub("concentration quantiles")
    anyv = [sc.concentration for sc in series]
    conv = [sc.constituent_concentration for sc in series]
    _q("any-cluster concentration", anyv)
    _q("constituent-only concentration", conv)

    sub("top-cluster identity, strata and the pooled gross split")
    tops = Counter(sc.top_cluster for sc in series if sc.top_cluster)
    for name, k in tops.most_common():
        print(f"  {name:<12s} top on {k:>4d} sessions ({k / n:6.1%})")
    strat = Counter(sc.stratum for sc in series)
    print(f"  top-cluster stratum (DIRECT_MAJORITY = {C.DIRECT_MAJORITY:.2f} of "
          f"the top cluster's gross):")
    for k, v in strat.most_common():
        print(f"    {str(k):<12s} {v:>4d} sessions ({v / n:6.1%})")
    g_direct = sum(sum(c.direct_gross for c in sc.clusters) for sc in series)
    g_all = sum(gross)
    if g_all:
        print(f"  pooled position-session gross: DIRECT {g_direct / g_all:6.2%}"
              f"   CONSTITUENT {1 - g_direct / g_all:6.2%}"
              f"   (of ${g_all:,.0f} summed session gross)")
    n_direct = sum(1 for p in positions
                   if S.stratum(p.rec["ticker"]) == S.DIRECT)
    print(f"  admitted POSITIONS that ARE their cluster's proxy (DIRECT): "
          f"{n_direct} / {len(positions)}")

    sub("trigger census — episodes are maximal runs of CONSECUTIVE triggered "
        "sessions")
    print(f"  G-POWER's floor is {MIN_TRIGGER_DATES} trigger DATES, read against EPISODES — the "
          f"strictest\n  of the readings, and the clustering hedge_portfolio "
          f"fixed. THE REGISTERED GRID:")
    print(f"  {'tau':>6s}  {'any:sessions':>13s} {'any:episodes':>13s}  "
          f"{'con:sessions':>13s} {'con:episodes':>13s}  power(any)")
    for tau in TAU_GRID_ADMITTED:
        _trigger_row(series, universe, tau)
    print("\n  FOR COMPARISON ONLY, NOT A CELL — hedge_portfolio's own taus on "
          "this book:")
    for tau in COMPARISON_TAUS:
        _trigger_row(series, universe, tau)
    for tau in TAU_GRID_ADMITTED:
        eps = C.episodes(C.triggered_sessions(series, tau), universe)
        if eps:
            print(f"    tau {tau:.2f} any-cluster episode lengths: "
                  f"{sorted((len(e) for e in eps), reverse=True)}")

    sub("gross versus concentration — is ARM KG a real control?")
    print(f"  Spearman( per-session gross , any-cluster concentration ) = "
          f"{_num_admitted(F.spearman(gross, anyv))}   n={n}")
    print(f"  Spearman( n_open           , any-cluster concentration ) = "
          f"{_num_admitted(F.spearman([float(sc.n_open) for sc in series], anyv))}")
    print("  The two variables separate on this book only if these are small; "
          "a large\n  value would mean ARM KG cannot control for anything.")

    sub("dense episodes of ADMITTED signal dates (account_sim.dense_episodes)")
    print(f"  parameters: episode_max_gap={st.episode_max_gap}  "
          f"episode_min_dates={st.episode_min_dates}  (config/account-sim.yml)")
    print(f"  dense episodes over admitted signal dates   {len(dense_eps)}"
          f"   (G-POWER-K floor {MIN_DENSE_EPISODES})")
    ep_dates = {d for e in dense_eps for d in e}
    for (lo, hi, k) in spans:
        inside = sum(1 for p in positions
                     if lo.isoformat() <= p.rec["date"] <= hi.isoformat())
        print(f"    {lo} .. {hi}   {k} dates   {inside} admitted positions")
    print(f"  admitted dates inside a dense episode      "
          f"{len(ep_dates)} / {len(adm_dates)}")
    print(f"  admitted positions inside a dense episode  "
          f"{sum(1 for p in positions if p.rec['date'] in ep_dates)} / "
          f"{len(positions)}")

    sub("hedge-flow prose — CENSUSED, READ BY NOTHING")
    print("""  The operator's practice has a third condition ("the analysis says people are
  hedging") and this study registers NO arm on it: the survivor set on this
  book is UNDERPOWERED by construction, and an arm that can never bite is not
  worth the lookahead it would carry. The parse is printed so a later reader
  can see exactly how far short it falls.""")
    try:
        hp, hp_diag = C.hedge_pressure_by_date()
    except FileNotFoundError as exc:
        print(f"  analysis export not available: {exc}")
        return
    print(f"  regex    {C.HEDGE_PRESSURE_RE.pattern}")
    print(f"  source   {hp_diag['source']}")
    print(f"  export dates {hp_diag['n_dates']}  parsed {hp_diag['n_dates_parsed']}"
          f"  coverage {hp_diag['coverage']:.1%}  multivalued "
          f"{hp_diag['n_dates_multivalued']}  cut {hp_diag['cut']}")
    par = [d for d in adm_dates if d in hp]
    cov = len(par) / len(adm_dates) if adm_dates else float("nan")
    print(f"  ADMITTED signal dates {len(adm_dates)}   parsed {len(par)}   "
          f"coverage {cov:.1%}   of those >= {C.HEDGE_PRESSURE_CUT}: "
          f"{sum(1 for d in par if hp[d] >= C.HEDGE_PRESSURE_CUT)}")
    tau_lo = TAU_GRID_ADMITTED[0]
    trig = C.triggered_sessions(series, tau_lo)
    cs = C.triggered_sessions(series, tau_lo, hedge_pressure=hp)
    print(f"  at the LOWEST registered tau {tau_lo:.2f}: {len(trig)} triggered "
          f"sessions; prose-conditioned survivors {len(cs)} sessions / "
          f"{len(C.episodes(cs, universe))} episodes\n  "
          f"(floor {MIN_TRIGGER_DATES} episodes — censused, used by nothing)")


def _trigger_row(series, universe, tau: float) -> None:
    ta = C.triggered_sessions(series, tau, C.MEASURE_ANY)
    tc = C.triggered_sessions(series, tau, C.MEASURE_CONSTITUENT)
    ea = C.episodes(ta, universe)
    ec = C.episodes(tc, universe)
    print(f"  {tau:>6.2f}  {len(ta):>13d} {len(ea):>13d}  {len(tc):>13d} "
          f"{len(ec):>13d}  "
          f"{'ok' if len(ea) >= MIN_TRIGGER_DATES else 'UNDERPOWERED'}")


def _q(label: str, vals, spec: str = "10.4f") -> None:
    if not vals:
        print(f"  {label:<36s} n=0")
        return
    print(f"  {label:<36s} n={len(vals):<5d} "
          f"median={format(C._pct(vals, 50), spec)}  "
          f"p75={format(C._pct(vals, 75), spec)}  "
          f"p90={format(C._pct(vals, 90), spec)}  "
          f"max={format(max(vals), spec)}")


def print_arm_k(name: str, res: dict, stamp: str) -> None:
    """One ARM K read — counts, means, contrast, rho and both CIs."""
    note = f"   [{stamp}]" if stamp else ""
    b_c, b_r = res["boot_contrast"], res["boot_rho"]
    print(f"\n  {name}   H = {res['horizon']}   usable sessions "
          f"{res['n_usable']}   block {res['block']} sessions "
          f"({b_c.n_blocks} blocks){note}")
    print(f"    tercile usable counts   low {res['counts'][0]}   "
          f"mid {res['counts'][1]}   high {res['counts'][2]}"
          f"   (floor {MIN_TERCILE_SESSIONS} each)")
    print(f"    mean forward drawdown   low ${res['means'][0]:,.0f}   "
          f"mid ${res['means'][1]:,.0f}   high ${res['means'][2]:,.0f}")
    print(f"    CONTRAST (high - low)   ${res['contrast']:,.2f}"
          f"   CI95 [${b_c.lo:,.2f}, ${b_c.hi:,.2f}]"
          f"   {'excludes 0' if b_c.excludes_zero else 'includes 0'}"
          f"   [{b_c.n_boot} resamples, seed {b_c.seed}]{note}")
    print(f"    SPEARMAN rho            {_num_admitted(res['rho'])}"
          f"   CI95 [{_num_admitted(b_r.lo)}, {_num_admitted(b_r.hi)}]"
          f"   {'excludes 0' if b_r.excludes_zero else 'includes 0'}"
          f"   [{b_r.n_boot} resamples, seed {b_r.seed}]{note}")


def print_shortfall(res: dict) -> str:
    """G-POWER-K's shortfall, in the words the Ship criteria branch needs."""
    c = res["counts"]
    return (f"terciles {c[0]}/{c[1]}/{c[2]} against {MIN_TERCILE_SESSIONS} each "
            f"(short by {max(0, MIN_TERCILE_SESSIONS - c[0])}/"
            f"{max(0, MIN_TERCILE_SESSIONS - c[1])}/"
            f"{max(0, MIN_TERCILE_SESSIONS - c[2])}); dense episodes "
            f"{res['n_dense']} against {MIN_DENSE_EPISODES} "
            f"(short by {max(0, MIN_DENSE_EPISODES - res['n_dense'])})")


SHIP_BRANCHES = {
    "PRECONDITION-NULL":
        "record in research/deployment-evidence.md as closing the queued "
        "max-drawdown question for concentration-gated hedging; "
        "next-steps.md §2.1 closed",
    "GROSS-NOT-CONCENTRATION":
        "record in research/deployment-evidence.md as closing the queued "
        "max-drawdown question for concentration-gated hedging; "
        "next-steps.md §2.1 closed. It points at portfolio_delta and "
        "concurrency_correlation, not at a hedge",
    "UNDERPOWERED":
        "next-steps.md §2.1 -> BLOCKED ON NEW DATES; shortfall against "
        "G-POWER-K",
}

SHIP_BRANCHES_STAGE2 = {
    "MECHANISM-FOUND":
        "a DRAFTED amendment to docs/deployment-rules.md §4, held in "
        "research/ (draft-and-hold); next-steps.md §2.1 becomes "
        "\"drafted, held\"",
    "NULL":
        "record in deployment-evidence.md as closing the question on this "
        "book; next-steps.md §2.1 closed",
    "CONTRARY":
        "record in deployment-evidence.md as closing the question on this "
        "book; next-steps.md §2.1 closed",
    "UNDERPOWERED":
        "next-steps.md §2.1 re-labelled BLOCKED ON NEW DATES / FILLS with the "
        "shortfall printed (trigger dates per cell against 25; fill share "
        "against 60%)",
    "NOT EVALUABLE":
        "next-steps.md §2.1 re-labelled BLOCKED ON NEW DATES / FILLS with the "
        "shortfall printed (trigger dates per cell against 25; fill share "
        "against 60%)",
}


# ════════════════════════════════════════════════════════════════════════════

def main_admitted() -> int:
    ap = argparse.ArgumentParser(description=ADMITTED_DOC.splitlines()[0])
    ap.add_argument("--admitted", action="store_true",
                    help="select this arm. `main()` has already dispatched on "
                         "it; it is declared here so the flag survives this "
                         "parser instead of being an unrecognized argument.")
    ap.add_argument("--rule", choices=HI.RULES, default=HI.RULE_BAND,
                    help="Stage 2 fill rule. `band` is the pre-registered "
                         "primary; `nearest` is the registered sensitivity.")
    ap.add_argument("--seeds", type=int, default=N_SEEDS,
                    help=f"ARM N seeds (registered: {N_SEEDS})")
    ap.add_argument("--boot", type=int, default=2000,
                    help="Stage 2 block-bootstrap resamples per cell "
                         "(Stage 1 always uses the registered "
                         f"{BOOT_N_ADMITTED})")
    args = ap.parse_args()

    st = A.load_settings()
    capital = st.capital
    budget = st.budget
    label = "hedge_concentration"

    # ── G-ERA (load_book refuses exit 3 / exit 2 on its own) ────────────────
    recs, diag = load_population()
    dates = sorted({r["date"] for r in recs})
    by_source: dict[str, int] = defaultdict(int)
    for r in recs:
        by_source[r["source"]] += 1

    hdr("hedge_concentration — on the ADMITTED book, does concentration "
        "PREDICT drawdown,\nand only then does a proxy hedge cut it?")
    print(f"""  era {diag['era']} (G-ERA: v4 only; a mismatch refuses exit 3, a thin era exit 2)
  config {st.source.name}: capital ${capital:,.0f}, risk {st.risk_pct:.0%} = ${budget:,.0f} per position
         on a MAX-LOSS basis, max_positions_per_day {st.max_per_day},
         caps per_position {st.per_pos_cap}x / net {st.net_cap}x equity (delta-notional)
  option cache: {cache_state()}
  Stage 2 primary fill rule: {args.rule}

  POPULATION — the RATIFIED one, by the literal call `load_book(include_bs=False)`
  (research/pre-registrations/f5_hedging/hedge_portfolio.md §Population and
  basis — RATIFICATION, operator 2026-08-31).
  `account_sim`'s own default loader makes byte-for-byte the same call, so the
  candidate set here IS the population hedge_portfolio ratified:
    rows {len(recs)}   signal dates {len(dates)}   {dates[0] if dates else 'n/a'} .. {dates[-1] if dates else 'n/a'}
    pricing sources: """ + "  ".join(f"{k} {v}" for k, v in sorted(by_source.items())) + f"""

  ARM H IS OFF (bear_by_day=None AND cfg.hedge=False), there is no --live-select
  ranker and no compounding. THE BOOK IS THE ADMITTED SUBSET: what
  account_sim.simulate() takes from that candidate set under the operator's
  top-{st.max_per_day}-per-day rule and the cash / per-position / net delta caps. Hedges
  (Stage 2 only) go through `account_sim.admission()` and never displace a pick.

  This is a DIFFERENT BOOK from hedge_portfolio's, which held every ratified row
  concurrently; no figure here restates one of that study's, and neither
  study's verdict overrides the other's.

  NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF. No annualised
  figure, Sharpe or time-to-recover appears anywhere in this report.""")

    # ── the sector map, quoted as the registration requires ─────────────────
    hdr("SECTOR MAP — fixed in hedge_portfolio's registration before any "
        "concentration was computed")
    for line in S.census_lines():
        print(line)
    print(f"\n  run-time confirmation: proxies on underlying.rescaled_tickers() "
          f"today = {sorted(S.rescale_withheld_proxies()) or 'none'}")
    print("  (diagnostic only — UNHEDGEABLE is a committed constant and is "
          "never recomputed from it)")

    print_not_preregistered_admitted(args, capital, budget)

    # ── the admitted book ───────────────────────────────────────────────────
    day_lists, sim = simulate_admitted(recs, st, label)
    positions = admitted_positions(sim)
    cen = admission_census(sim, day_lists, label)

    hdr("POPULATION + ADMISSION CENSUS — what was held, and what was NOT")
    print(f"  candidate rows (ratified population)        {len(recs):>6}   "
          f"/ {len(dates)} signal dates")
    print("  by pricing source:  " + "  ".join(
        f"{k} {v}" for k, v in sorted(by_source.items())))
    print(f"  ladder-eligible rows (tier A/B)             "
          f"{cen['n_candidates']:>6}   / {cen['n_candidate_dates']} dates")
    print(f"  ADMITTED (taken + taken_downsized)          "
          f"{cen['n_admitted']:>6}   / {len(cen['dates'])} dates   "
          f"{cen['dates'][0] if cen['dates'] else 'n/a'} .. "
          f"{cen['dates'][-1] if cen['dates'] else 'n/a'}")
    print(f"    of which taken                            {cen['n_taken']:>6}")
    print(f"    of which taken_downsized                  {cen['n_downsized']:>6}")
    print(f"  admitted contracts, total                   {cen['contracts']:>6}")
    print("\n  SKIPPED CANDIDATES, beside the admitted ones — what was NOT held:")
    for why, k in sorted(cen["skipped"].items(), key=lambda kv: -kv[1]):
        print(f"      {why or '(none)':<22s} {k:>6}")
    print(f"      {'TOTAL skipped':<22s} {cen['n_skipped']:>6}")
    ok_part = cen["n_admitted"] + cen["n_skipped"] == cen["n_candidates"]
    print(f"  partition check: admitted {cen['n_admitted']} + skipped "
          f"{cen['n_skipped']} = {cen['n_admitted'] + cen['n_skipped']}"
          f"  vs ladder-eligible candidates {cen['n_candidates']}"
          f"   -> {'EXACT' if ok_part else 'MISMATCH'}")
    print("  Every count above is computed from THIS run's export; none is "
          "stored.")

    # ── G-ADMIT ─────────────────────────────────────────────────────────────
    rc = gate_admit(sim, recs, st, label)
    if rc:
        return rc

    # ── G-MTM ───────────────────────────────────────────────────────────────
    hdr("G-MTM — the mark-to-market curve must reconcile at every admitted "
        "position's exit")
    bc = M.book_curves(positions, target=M.TARGET_POSITION)
    print("""  THE TARGET IS `TARGET_POSITION`, and this report does not call it
  hedge_portfolio's check. It compares TWO SEPARATE COMPUTATIONS — daily_pnl_csv
  at the REPLAY's exit index, times the REPLAY's contracts, against the dollars
  the FROZEN harness booked for that same replay — which is the only target the
  registration's own words ("reconciles ... at every ADMITTED POSITION's exit")
  can mean on a book the simulator re-sized and re-exited. It is NOT
  hedge_portfolio's two-STORED-columns check (daily_pnl_csv vs
  realized_pnl_abs), because the stored column describes a DIFFERENT position
  here by construction. That stored-target reconciliation is printed below as a
  DISCLOSURE, with the re-sizing and re-exiting counted at run time.""")
    print(f"\n  positions {bc.n_positions}   reconciled {bc.n_reconciled}   "
          f"tolerance ${bc.tolerance:.2f} per contract   "
          f"worst mismatch ${bc.worst_mismatch:.4f}")
    print(f"  stale marks carried forward inside an open window: "
          f"{bc.n_carried_forward}")
    if not bc.reconciles:
        print(f"\n  G-MTM FAILED — {len(bc.mismatches)} position(s) disagree:")
        for m in bc.mismatches[:20]:
            print(f"    {m.date} {m.ticker:<6s} {m.structure:<22s} "
                  f"x{m.contracts:<3d} mtm ${m.mtm_at_exit:,.2f} "
                  f"booked ${m.booked:,.2f} diff ${m.diff:,.2f}")
        print(f"\nG-MTM RECONCILIATION FAILURE. Exit {EXIT_MTM_RECONCILE}.")
        return EXIT_MTM_RECONCILE
    print("  G-MTM PASS.")

    sub("DISCLOSURE — the same book against the STORED-row target")
    bc_stored = M.book_curves(positions, target=M.TARGET_STORED)
    n_resized = sum(1 for p in positions
                    if int(p.contracts) != int(p.rec["t"].contracts))
    n_reexited = sum(1 for p in positions
                     if p.rec["days_held"] is not None
                     and int(p.days_held) != int(p.rec["days_held"]))
    print(f"  positions {bc_stored.n_positions}   reconciled "
          f"{bc_stored.n_reconciled}   mismatches {len(bc_stored.mismatches)}"
          f"   degraded {bc_stored.n_degraded}")
    print(f"  positions the sim RE-SIZED (contracts != the row's)   {n_resized}")
    print(f"  positions the sim RE-EXITED (days_held != the row's)  {n_reexited}")
    print("""  A mismatch here is EXPECTED and is not a gate: the stored column is the
  row's own realized_pnl_abs at the ROW's contract count and the ROW's exit
  day, and admission changed both. It is printed so a reader can see exactly
  how far the admitted book is from the book the row describes — which is the
  whole subject of this study — rather than discovering it later.""")

    axis = list(bc.mtm.sessions)
    base_daily = list(bc.mtm.daily)
    levels = list(bc.mtm.levels)

    # ── ARM M ───────────────────────────────────────────────────────────────
    hdr("ARM M — MEASUREMENT: the SAME unhedged ADMITTED book on both curves")
    print("""  Every hedge verdict on record (hedge_sizing D3, hedge_structure H3,
  hedge_timing H4) rests on account_sim's close-bucketed curve, whose own
  print_equity says "Open positions are not marked to market, so this
  understates intra-position drawdown." A hedge's function is to cushion
  exactly the path that curve omits. ARM M measures the gap ON THE BOOK
  account_sim ACTUALLY HOLDS, so unlike hedge_portfolio's ARM M it is a
  measurement of the very curve that study's baseline was queued against.

  ARM M GATES NOTHING and is NEVER a verdict word in this study: the
  registration is explicit that MEASUREMENT-ONLY is not a Stage 2 word here.
  `bc.realized` IS account_sim.equity_curve's realized-on-close basis,
  restated on the shared session axis — it is not rebuilt.""")
    mtm_stats = M.path_stats(bc.mtm, capital)
    rea_stats = M.path_stats(bc.realized, capital)
    print()
    print_stats_row("mark-to-market (the basis)", mtm_stats)
    print_stats_row("realized-on-close (comparability)", rea_stats)
    gaps = dict(max_dd=mtm_stats.max_dd - rea_stats.max_dd,
                ulcer=mtm_stats.ulcer - rea_stats.ulcer,
                tuw=mtm_stats.tuw - rea_stats.tuw)
    rel = (abs(gaps["max_dd"] / rea_stats.max_dd) * 100.0
           if rea_stats.max_dd else float("nan"))
    print(f"\n  sessions {mtm_stats.n_sessions} (the curve's own axis)")
    print(f"  THE GAP, printed rather than asserted: maxDD ${gaps['max_dd']:+,.0f} "
          f"({rel:.1f}% of the realized-on-close drawdown)   "
          f"ulcer {gaps['ulcer']:+.2f} pts   TUW {gaps['tuw'] * 100:+.1f} pts")
    print("  This is a MEASUREMENT and is reported as one. No verdict word is "
          "read from it.")

    # ── the concentration layer ─────────────────────────────────────────────
    recs_adm, occ, series = concentration_layer(positions)
    universe = [sc.session for sc in series]
    by_session = {sc.session: sc for sc in series}

    # ── G-BLIND ─────────────────────────────────────────────────────────────
    hdr("G-BLIND — every trigger and the ARM K regressor, with outcome fields "
        "stripped")
    print("""  WHAT IS BLINDED, and why it is the records rather than the simulator. The
  sim REPLAYS a book that already happened and reads outcomes by construction —
  blinding it would test nothing about a trigger. What must survive blinding is
  the layer that makes a DECISION: the concentration series and every trigger
  set derived from it. So each sighted admitted position is paired with a
  `BlindRec` of its record — same entry/exit window, same contracts, an
  identical occupancy — and the whole concentration layer is re-run over those.
  `session_concentration` reads only ticker / delta / contracts /
  entry_underlying, which is why it is safe under `BlindRec`; a read of any
  outcome key raises LookaheadError instead of passing quietly. `days_held`
  reaches the occupancy ONLY through the sim's [entry_sess, exit_sess], which
  is the replay fixture.""")
    bpos = blinded_positions(positions)
    _brecs, bocc, bseries = concentration_layer(bpos)
    taus_checked = tuple(sorted(set(TAU_GRID_ADMITTED) | set(COMPARISON_TAUS)))
    fp_sighted = trigger_fingerprint(series, taus_checked)
    fp_blind = trigger_fingerprint(bseries, taus_checked)
    same_occ = (sorted(occ) == sorted(bocc)
                and all(occ[s] == bocc[s] for s in occ))
    diffs = [k for k in fp_sighted if fp_sighted[k] != fp_blind[k]]
    print(f"\n  sessions sighted {len(series)}   blinded {len(bseries)}   "
          f"occupancy identical {'YES' if same_occ else 'NO'}")
    print(f"  taus compared {taus_checked}   measures {C.MEASURES}")
    print(f"  fingerprint parts compared: {sorted(fp_sighted)}   "
          f"differing: {diffs or 'none'}")
    if diffs or not same_occ:
        print("\n  LOOKAHEAD DETECTED — the session set, the ARM K regressor or "
              "a trigger set\n  moves when the outcome columns are blinded. "
              "That is a DEFECT in this module,\n  not a designed refusal, so "
              "it exits 1 and no report is promoted.")
        return EXIT_LOOKAHEAD
    print("  G-BLIND PASS — the session set, every x value and every triggered "
          "set are\n  byte-identical under blinded records.")

    # ── G-CENSUS ────────────────────────────────────────────────────────────
    adm_dates = cen["dates"]
    sess_series = A.session_series(sim)
    dense_eps = A.dense_episodes(adm_dates, max_gap=st.episode_max_gap,
                                 min_dates=st.episode_min_dates)
    spans = episode_spans(dense_eps)
    print_census(series, universe, adm_dates, positions, sess_series,
                 capital, st, dense_eps, spans)

    # ── STAGE 1 ─────────────────────────────────────────────────────────────
    hdr("STAGE 1 — ARM K, the precondition: does concentration PREDICT the "
        "book's drawdown?")
    print(f"""  x(s) = any-cluster concentration at the close of session s, over the
  ADMITTED positions open at s. y(s) = the book's forward MARK-TO-MARKET
  drawdown over the next H = {H} sessions: min(equity(t) - equity(s)) for
  s < t <= s+H, in dollars, <= 0. A session with fewer than H forward sessions
  has NO y and is dropped from ARM K alone, never from the universe — a partial
  window would make the last H sessions look systematically shallower.

  SIGN CONVENTION: the precondition predicts the TOP concentration tercile
  draws down MORE, i.e. contrast < 0 and rho < 0. Both reads are required.""")
    al = align(axis, levels, series, sess_series, capital, H)
    print(f"\n  curve axis sessions {al.n_axis}   concentration sessions "
          f"{len(series)}   ARM K rows {len(al.sessions)}")
    print(f"  axis sessions with NO concentration reading (dropped from ARM K's "
          f"rows): {al.n_axis_unmatched}")
    print(f"  concentration sessions NOT on the curve axis: "
          f"{al.n_series_off_axis}"
          + ("" if not al.n_series_off_axis else
             "   <- DISCLOSED: these carry no forward-drawdown reading"))
    print(f"  rows dropped for having no session_series gross (ARM KG's "
          f"control): {al.n_no_gross}")

    k = run_arm_k(al, H, H, BOOT_N_ADMITTED, SEED_ADMITTED)
    n_dense = len(dense_eps)
    powered = (min(k["counts"]) >= MIN_TERCILE_SESSIONS
               and n_dense >= MIN_DENSE_EPISODES)
    stamp = "" if powered else UNPOWERED_NOTE_ADMITTED

    print_arm_k("ARM K", k, stamp)
    k10 = run_arm_k(align(axis, levels, series, sess_series, capital, H_SENS),
                    H_SENS, H_SENS, BOOT_N_ADMITTED, SEED_ADMITTED)
    print_arm_k("ARM K10 (SENSITIVITY — carries no verdict, cannot rescue or "
                "overturn ARM K)", k10, stamp)

    sub("ARM KN — the time-structure null (circular shift, "
        f"{KN_DRAWS} draws, seed {SEED_ADMITTED})")
    kn = run_arm_kn(al, H, KN_DRAWS, SEED_ADMITTED)
    for name, lab in (("contrast", "contrast"), ("rho", "Spearman rho")):
        sn = kn.get(name)
        if sn is None:
            print(f"  {lab:<14s} not computable: {kn.get(name + '_error')}")
            continue
        beats = sn.beats_low()
        print(f"  {lab:<14s} point {_num_admitted(sn.point)}   null p05 {_num_admitted(sn.p05)}"
              f"   p95 {_num_admitted(sn.p95)}   min shift {sn.min_shift} rows"
              f"   beats p05 (more negative): {'yes' if beats else 'no'}"
              + (f"   [{stamp}]" if stamp else ""))

    sub("ARM KG — the gross-exposure control (ARM K inside gross/equity "
        "terciles)")
    kg = run_arm_kg(al)
    print(f"  gross terciles, usable rows: {kg['gross_terciles']}")
    for i, c in enumerate(kg["contrasts"]):
        print(f"    gross tercile {i + 1} (low->high)   contrast "
              f"{_dollars(c)}")
    n_kept = F.sign_kept(kg["contrasts"], k["contrast"])
    print(f"  contrast keeps ARM K's sign in {n_kept} of 3 gross terciles "
          f"(clause 4 needs >= {KG_MIN_SIGN})")

    sub("per dense episode — clause 5")
    ep_signs = run_episode_signs(al, spans, k["contrast"])
    for e in ep_signs:
        tag = ("COUNTED" if e["counted"]
               else f"< {MIN_EPISODE_SESSIONS} usable — no sign")
        print(f"  {e['lo']} .. {e['hi']}   {e['n_dates']:>3} signal dates   "
              f"{e['n_sessions']:>4} sessions   {e['n_usable']:>4} usable   "
              f"contrast {_dollars(e['contrast']):>14s}   {tag:<28s}"
              f"   {'sign kept' if e['keeps_sign'] else 'sign NOT kept'}")
    counted = [e for e in ep_signs if e["counted"]]
    c5 = bool(counted) and all(e["keeps_sign"] for e in counted)

    sub("ex-window cuts — clause 6 (protocol.DOMINANT_WINDOWS)")
    cuts = run_window_cuts(al, k["contrast"])
    for name, c in cuts.items():
        print(f"  {name:<18s} rows {c['n']:>4}  usable {c['n_usable']:>4}  "
              f"contrast {_dollars(c['contrast']):>14s}"
              f"   {'sign kept' if c['keeps_sign'] else 'sign NOT kept'}")
    c6 = bool(cuts) and all(c["keeps_sign"] for c in cuts.values())

    sub("G-POWER-K")
    print(f"  usable sessions per concentration tercile   "
          f"{k['counts']}   floor {MIN_TERCILE_SESSIONS} EACH   "
          f"{_pass(min(k['counts']) >= MIN_TERCILE_SESSIONS)}")
    print(f"  dense episodes of admitted signal dates     {n_dense}   "
          f"floor {MIN_DENSE_EPISODES}   {_pass(n_dense >= MIN_DENSE_EPISODES)}")
    print(f"  G-POWER-K: {_pass(powered)}"
          + ("" if powered else
             "   — ARM K is UNDERPOWERED and NO DIRECTION IS QUOTED from it. "
             "Every\n  ARM K / ARM K10 / ARM KN / ARM KG row above carries the "
             "stamp. UNDERPOWERED\n  IS NOT A LEAN: it is not a NULL, and it is "
             "not evidence that the precondition\n  is absent."))

    b_c, b_r = k["boot_contrast"], k["boot_rho"]
    kn_c = kn.get("contrast")
    res = dict(
        powered=powered,
        c1=(k["contrast"] < 0 and b_c.excludes_zero),
        c2=(k["rho"] == k["rho"] and k["rho"] < 0 and b_r.excludes_zero),
        c3=bool(kn_c is not None and kn_c.beats_low()),
        c4=(n_kept >= KG_MIN_SIGN),
        c5=c5,
        c6=c6,
        counts=k["counts"], n_dense=n_dense)

    sub("STAGE 1 BAR — all six clauses")
    print(f"  1 contrast negative, block-bootstrap CI excludes 0   "
          f"{_pass(res['c1'])}   contrast ${k['contrast']:,.2f}  "
          f"CI95 [${b_c.lo:,.2f}, ${b_c.hi:,.2f}]")
    print(f"  2 Spearman rho negative, CI excludes 0              "
          f"{_pass(res['c2'])}   rho {_num_admitted(k['rho'])}  "
          f"CI95 [{_num_admitted(b_r.lo)}, {_num_admitted(b_r.hi)}]")
    print(f"  3 contrast beyond ARM KN's 5th percentile           "
          f"{_pass(res['c3'])}   point {_num_admitted(kn_c.point) if kn_c else 'n/a'}  "
          f"p05 {_num_admitted(kn_c.p05) if kn_c else 'n/a'}")
    print(f"  4 not a gross effect: sign kept in >= {KG_MIN_SIGN} of 3          "
          f"{_pass(res['c4'])}   {n_kept} of 3")
    print(f"  5 sign kept in EVERY dense episode >= {MIN_EPISODE_SESSIONS} sessions   "
          f"{_pass(res['c5'])}   "
          f"{sum(1 for e in counted if e['keeps_sign'])} of {len(counted)} counted")
    print(f"  6 sign kept under BOTH ex-window cuts               "
          f"{_pass(res['c6'])}   "
          f"{sum(1 for c in cuts.values() if c['keeps_sign'])} of {len(cuts)}")

    v1 = stage1_verdict(res)
    print(f"\n  {VERDICT_STAMP} — Stage 1 (ARM K, the precondition): {v1}")

    # ── STAGE 2 ─────────────────────────────────────────────────────────────
    hdr("STAGE 2 — ARM C, the mechanism   (runs ONLY on PRECONDITION-FOUND)")
    print(f"""  ANTI-TUNING, binding: "Stage 2 does not run on a non-FOUND Stage 1, and a
  later reader may not run it by hand and quote it: a hedge tested on a trigger
  that carries no information is a hedge tested on noise." The trigger census
  is printed for the record either way; no cell is evaluated unless Stage 1
  found the precondition.

  Grid: tau {TAU_GRID_ADMITTED} x f {F_GRID} = {N_CELLS_ADMITTED} cells,
  Bonferroni alpha = 0.05/{N_CELLS_ADMITTED} = {ALPHA_ADMITTED:.5f}.""")

    def _census_only() -> None:
        sub("Stage 2 trigger census, FOR THE RECORD (no cell is evaluated)")
        print(f"  {'tau':>6s}  {'sessions':>9s} {'episodes':>9s}  power "
              f"(floor {MIN_TRIGGER_DATES} episodes)")
        for tau in TAU_GRID_ADMITTED:
            trig = C.triggered_sessions(series, tau)
            eps = C.episodes(trig, universe)
            print(f"  {tau:>6.2f}  {len(trig):>9d} {len(eps):>9d}  "
                  f"{'ok' if len(eps) >= MIN_TRIGGER_DATES else 'UNDERPOWERED'}")

    def _run_stage2() -> str:
        return run_stage2(series, universe, by_session, recs_adm, axis,
                          base_daily, mtm_stats, capital, budget, sess_series,
                          st, args)

    v2 = stage2_dispatch(v1, _run_stage2, _census_only)

    # ── CLOSE ───────────────────────────────────────────────────────────────
    hdr("RESULT")
    print(f"  {VERDICT_STAMP} — Stage 1 (ARM K, the precondition): {v1}")
    if v2 is None:
        print(f"  {VERDICT_STAMP} — Stage 2 (ARM C, the mechanism): NOT RUN "
              f"(Stage 1 {v1})")
    else:
        print(f"  {VERDICT_STAMP} — Stage 2 (ARM C, the mechanism): {v2}")

    if v1 == "UNDERPOWERED":
        branch = (f"{SHIP_BRANCHES['UNDERPOWERED']}: {print_shortfall(res)}")
    elif v1 in SHIP_BRANCHES:
        branch = SHIP_BRANCHES[v1]
    else:
        branch = SHIP_BRANCHES_STAGE2.get(v2 or "", "operator sign-off")
    print(f"\n  SHIP-CRITERIA BRANCH: {branch}")

    print("""
  WHAT THIS RESULT DOES NOT DO.
    It ships NOTHING. NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF.
    It does NOT remove or amend the §4 bear sleeve, which is operator policy
      and is not removed by any outcome here.
    It does NOT overturn hedge_portfolio. That study's UNDERPOWERED describes
      the every-row book; this one describes the ADMITTED book. Neither
      verdict overrides the other's.
    It is NOT evidence about concurrency_correlation's ceiling, in either
      direction: different unit, different outcome, different remedy.
    ARM M is a MEASUREMENT in every run of this study and never a verdict.

  ASYMMETRIC READING RULE, BINDING: DIRECT versus CONSTITUENT strata are always
  reported; a DIRECT result is never evidence for the constituent practice, nor
  a DIRECT null evidence against it.""")
    return 0


def run_stage2(series, universe, by_session, recs_adm, axis, base_daily,
               mtm_stats, capital, budget, sess_series, st, args) -> str:
    """The full Stage 2 grid. Reached ONLY on PRECONDITION-FOUND.

    Everything here is `hedge_portfolio`'s machinery over this study's objects —
    the seven clauses, the CONTRARY mirror, the ARM N band, the
    leave-one-date-out folds and the per-stratum computation — with one
    difference the registration adds: every hedge leg is admitted through
    `account_sim.admission()` against the overlay ledger.
    """
    cfg = st.cfg("hedge_concentration STAGE 2", compound=False, hedge=False)

    def overlay_factory() -> Overlay:
        return Overlay(capital, sess_series, cfg)

    # ── G-FILL ──────────────────────────────────────────────────────────────
    hdr("G-FILL — a hedge must be fillable on >=60% of triggered sessions "
        "(band rule)")
    print("""  An unfillable session is CARRIED AT f=0 and stays in the denominator, per
  hedge_structure's standing principle that a hedge unavailable exactly when
  needed is not a hedge. DISCLOSED: this denominator is CACHE-CONDITIONED — the
  instrument universe is the option history cache, i.e. contracts the BOOK
  traded, so these rates measure CACHE COVERAGE, not market liquidity.""")
    fill = {}
    for tau in TAU_GRID_ADMITTED:
        trig = C.triggered_sessions(series, tau)
        pairs = [(s, by_session[s].top_proxy) for s in trig
                 if by_session[s].top_proxy]
        table = HI.coverage_table(pairs)
        fill[tau] = table
        b, nr = table[HI.RULE_BAND], table[HI.RULE_NEAREST]
        print(f"\n  tau {tau:.2f}   triggered sessions {len(trig)}"
              f"   band {b.filled}/{b.n} = {b.rate:.1%}   "
              f"{_pass(b.passes())}   nearest {nr.rate:.1%}")

    # ── the cells ───────────────────────────────────────────────────────────
    hdr(f"ARM C — concentration-gated proxy put   ({len(TAU_GRID_ADMITTED)} tau x "
        f"{len(F_GRID)} f = {N_CELLS_ADMITTED} cells)")
    cells: dict[tuple, Cell] = {}
    arm_r: dict[tuple, dict] = {}
    for tau in TAU_GRID_ADMITTED:
        trig = C.triggered_sessions(series, tau)
        eps = C.episodes(trig, universe)
        counts = C.trigger_date_counts(trig, series, recs_adm)
        for f in F_GRID:
            cell = build_cell_admitted(tau, f, args.rule, trig, eps, by_session, budget,
                                       universe, overlay_factory)
            cell.n_book_dates = counts["book_dates"]
            cells[(tau, f)] = cell
            rdiag = dict(no_entry_delta=0)
            arm_r[(tau, f)] = dict(
                hedge=merge(price_delta_short(leg, rdiag)
                            for leg in cell.legs),
                diag=rdiag)

    sub("cell shape (no outcome read yet)")
    print("\n   tau     f   episodes  legs  opens  rolls  rotate  no-fill  "
          "sub-1c  no-greek  refused  unhedg-sess    debit$")
    for (tau, f), cell in cells.items():
        d = cell.diag
        print(f"  {tau:.2f}  {f:.2f}   {cell.n_episodes:8d}  {len(cell.legs):4d}"
              f"  {d['opens']:5d}  {d['rolls']:5d}  {d['rotations']:6d}"
              f"  {d['sessions_no_fill']:7d}  {d['sessions_sub_one']:6d}"
              f"  {d['no_entry_delta']:8d}  {d['admission_refused']:7d}"
              f"  {d['sessions_unhedgeable']:11d}"
              f"  {sum(leg.cost for leg in cell.legs):9,.0f}")
    print("\n  admission refusals by binding constraint, per cell:")
    for (tau, f), cell in cells.items():
        print(f"    tau {tau:.2f} f {f:.2f}   admitted legs "
              f"{cell.diag['admitted_legs']}   refused "
              f"{cell.diag['admission_refused_by_reason'] or 'none'}")

    sub("path metrics per cell — mark-to-market curve, unhedged baseline first")
    print_stats_row("f = 0 (unhedged)", mtm_stats)
    for (tau, f), cell in cells.items():
        if not cell.legs:
            cell.verdict = "NO HEDGE PLACED"
            continue
        stt = M.path_stats(curve_of(axis, hedged_daily(axis, base_daily,
                                                       cell.hedge)), capital)
        cell.stats = stt
        print_stats_row(f"ARM C tau {tau:.2f} f {f:.2f}", stt, mtm_stats,
                        note=power_note(cell.powered))

    sub("ARM R — always-fillable reference (delta-matched short in the proxy)")
    print(f"  {ARM_R_CAVEAT}\n")
    for (tau, f) in cells:
        h = arm_r[(tau, f)]["hedge"]
        if h:
            stt = M.path_stats(curve_of(axis, hedged_daily(axis, base_daily, h)),
                               capital)
            print_stats_row(f"ARM R tau {tau:.2f} f {f:.2f} (delta-matched)",
                            stt, mtm_stats,
                            note=power_note(cells[(tau, f)].powered))

    # ── the bar ─────────────────────────────────────────────────────────────
    hdr("BAR FOR A CANDIDATE — all seven clauses, per powered cell, per stratum")
    words: Counter = Counter()

    def stratum_cell(strat: str, tau: float, f: float) -> Cell:
        if strat == STRATUM_POOLED:
            return cells[(tau, f)]
        trig = C.triggered_sessions(series, tau, stratum=strat)
        eps = C.episodes(trig, universe)
        c = build_cell_admitted(tau, f, args.rule, trig, eps, by_session, budget,
                                universe, overlay_factory, stratum=strat)
        c.n_book_dates = C.trigger_date_counts(trig, series, recs_adm)["book_dates"]
        return c

    for (tau, f) in cells:
        sub(f"cell tau {tau:.2f}  f {f:.2f}")
        band_ok = fill[tau][args.rule].passes()
        for strat in STRATA:
            scell = stratum_cell(strat, tau, f)
            print(f"\n  [{strat:<11s}] triggered sessions {scell.n_sessions:4d}"
                  f"   episodes {scell.n_episodes:3d}"
                  f"   episodes that placed a hedge {len(scell.legs):3d}")
            if not band_ok:
                scell.verdict = "NOT EVALUABLE"
                print(f"  G-FILL {fill[tau][args.rule].rate:.1%} < "
                      f"{FILL_GATE:.0%} — NOT EVALUABLE (not failed).")
            elif not scell.powered:
                scell.verdict = "UNDERPOWERED"
                print(f"  {scell.n_episodes} trigger dates (episodes) < "
                      f"{MIN_TRIGGER_DATES} — UNDERPOWERED. No direction is "
                      f"quoted. UNDERPOWERED is not a lean.")
            elif not scell.legs:
                scell.verdict = "NO HEDGE PLACED"
                print("  no hedge was placed in this stratum; nothing to "
                      "evaluate, and not evidence about hedging.")
            else:
                band = arm_n_band_admitted(scell.eps, by_session, universe, axis,
                                           base_daily, capital, f, budget, args.rule,
                                           CO_PRIMARIES, overlay_factory,
                                           n_seeds=args.seeds, seed=SEED_ADMITTED)
                rdiag = dict(no_entry_delta=0)
                rh = (arm_r[(tau, f)]["hedge"] if strat == STRATUM_POOLED
                      else merge(price_delta_short(leg, rdiag)
                                 for leg in scell.legs))
                rimp = {}
                if rh:
                    rst = M.path_stats(
                        curve_of(axis, hedged_daily(axis, base_daily, rh)),
                        capital)
                    rimp = {m: improvement(mtm_stats, rst, m)
                            for m in CO_PRIMARIES}
                folds = leave_one_date_out_admitted(
                    scell, by_session, universe, axis, base_daily, capital,
                    mtm_stats, CO_PRIMARIES, f, budget, args.rule,
                    overlay_factory)
                # `arm_n_registered=band` is the SAME band on purpose. In
                # hedge_portfolio the rich match was NOT what its registration
                # committed, so the two had to be printed side by side; THIS
                # registration commits exactly this match — "episode COUNT,
                # episode LENGTHS and PROXY mix" — so there is no second
                # estimator to disagree with and the diagnostic row restates
                # the committed one.
                res = evaluate_bar(scell, axis, base_daily, capital, band,
                                   rimp, args.boot, folds,
                                   arm_n_registered=band)
                scell.clauses = res
                scell.verdict = cell_verdict(res)
                print_clauses(res, scell, args)
            print(f"  => {strat}: {scell.verdict}")
            words[scell.verdict] += 1

    hdr("CELL TALLY — no study-level verdict is read from it")
    for w, k in sorted(words.items()):
        print(f"    {w:<18s} {k} cell(s)")

    if words.get("CANDIDATE"):
        return "MECHANISM-FOUND"
    if words.get("CONTRARY"):
        return "CONTRARY"
    if set(words) <= {"NOT EVALUABLE", "NO HEDGE PLACED"}:
        return "NOT EVALUABLE"
    if not words.get("NULL"):
        return "UNDERPOWERED"
    return "NULL"

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  end of the admitted arm                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝


if __name__ == "__main__":
    sys.exit(main())
