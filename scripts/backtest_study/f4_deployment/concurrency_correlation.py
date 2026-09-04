"""Concurrency / correlation study: does the SIZE and INTERNAL SIMILARITY of the
open book degrade per-position outcome, independently of what was selected?

PRE-REGISTERED 2026-08-22, BEFORE this file was written, in
`research/pre-registrations/f4_deployment/concurrency_correlation.md`. Read that
first; nothing here may drift from it. In brief:

  Question  `DEPLOY_BUDGET`/`max_positions_per_day = 3` caps the FLOW of new
            positions per day. Nothing caps the STOCK of open ones, and no
            report has ever joined `account_sim`'s `n_open` to an outcome. Two
            effects, deliberately separated: CONCURRENCY (does a position
            opened while N others are open do worse as N rises?) and
            CORRELATION (does a position opened alongside others pointing the
            same way do worse than one opened into an unlike book?).
  Not this  NOT a selection study and NOT an exit study. The ladder is FROZEN
            (`top_k_per_day(book, ladder_rank, k=3, ladder_eligible)`) and the
            exits are FROZEN (each position keeps the stored `days_held` its
            shipped-profile replay produced). No column is added to selection,
            no exit knob moves, no tier rule is touched. The only new machinery
            is a book-state annotation computed at each position's ENTRY
            session.
  Arms      ARM N null control (count-matched random refusals, >= 1,000 draws).
            ARM D0 descriptive dose-response by concurrency band, by
            same-direction count and by same-sector count — DESCRIPTIVE ONLY,
            never a criterion. ARM C concurrency ceiling C in {5, 8, 12, 20}.
            ARM K clustering ceiling K in {2, 3, 5} over three similarity
            relations. ARM CK the conjunction, run ONLY if ARM C and ARM K each
            clear their criteria alone.
  Unit      The POSITION, paired within its signal DATE against the unmodified
            deployed book. Positions are counted at the POSITION level, never
            the leg level, so the figure is comparable to `account_sim`'s
            `n_open` and NOT to live leg counts.
  Bar       X1 power floor -> X2 gain -> X3 not noise -> X4 era stability ->
            X5 population stability -> X6 leave-one-out -> X7 NOT a delta
            ceiling in disguise -> X8 dollar honesty. All eight, or it is not a
            candidate. A failure is a failure, not a footnote.
  Gates     G1 era identity, G2 no look-ahead, G3 selection identity, G4
            refusal attribution, G5 no new statistic, G6 no hardcoded census.

NOTHING SHIPS FROM THIS STUDY ON THE BASIS OF A DOLLAR TOTAL. The grid is a
SHAPE, not a menu.

REFUSES (exit 2) rather than reporting a verdict when the era is too thin to
conclude from; exit 3 is `load_book`'s era guard. A real gate failure is exit 1.

    python -m scripts.backtest_study run concurrency_correlation
    python -m scripts.backtest_study run concurrency_correlation --era v3
    python -m scripts.backtest_study run concurrency_correlation -- --gates-only
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f2_management.bear_giveback import hdr, sub  # noqa: E402
from scripts.backtest_study.f4_deployment import account_sim as A  # noqa: E402
from scripts.backtest_study.f4_deployment import portfolio_delta as PD  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import sectors  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# Exit codes this study returns as a DESIGNED refusal rather than a failure: 2
# is the thin-era guard, 3 is `load_book`'s era mismatch. `run.py` finds this by
# AST parse and never imports the module, so it MUST stay a literal module-level
# set assignment — see the identical note in `portfolio_delta.py`.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}


# ════════════════════════════════════════════════════════════════════════════
# Frozen constants — every one written from the registration, before first run
# ════════════════════════════════════════════════════════════════════════════

# ARM D0's concurrency bands, on open positions at entry. Five, frozen.
CONC_BANDS = ((0, 3), (3, 6), (6, 10), (10, 20), (20, 10 ** 9))

# ARM C's ceilings and ARM K's ceilings. Four and three, frozen.
ARM_C_GRID = (5, 8, 12, 20)
ARM_K_GRID = (2, 3, 5)

# ARM K's three similarity relations, run SEPARATELY. The labels are the
# registration's own words.
K_SAME_DIR = "same-direction"
K_SAME_DIR_SECTOR = "same-direction-and-sector"
K_SAME_UNDERLYING = "same-underlying"
K_RELATIONS = (K_SAME_DIR, K_SAME_DIR_SECTOR, K_SAME_UNDERLYING)

# ARM N — the null band. The registration says ">= 1,000 draws"; 1,000 it is,
# with the seed PRINTED whether or not the draws are taken so the claim and the
# number can never come apart.
DRAWS = 1000
SEED = 20260822
BAND_ALPHA = 0.05          # band = [p5, p95]; X3 reads "> p95"

# X1's two power floors. `MIN_MOVED_DATES` is the registration's own ">= 25
# dates". `MIN_N_TO_READ` is the repo's existing constant of that name
# (`f3_structure/calendar_hedge.py`, = 10), which is what the registration
# cites; it is NOT re-derived here and may not be lowered to make an arm
# readable.
MIN_MOVED_DATES = 25
MIN_N_TO_READ = 10

# A descriptive ARM D0 cell under this many positions prints its n and is NOT
# read. Same value and same reason as `portfolio_delta.MIN_CELL_N`.
MIN_CELL_N = 20

# X7's control bands. Imported rather than restated: the criterion names
# "portfolio_delta's own bands", and two copies would let the control disagree
# with the study it controls against.
DELTA_BANDS = PD.BANDS

# X4 needs BOTH eras and a study runs on ONE era by repo rule (`lib/era.py`).
# The companion run is a separate invocation and its report is the other half of
# this criterion; see `X4_NOTE` and the NOT PRE-REGISTERED block.
X4_NOTE = """  X4 (ERA STABILITY) cannot be evaluated inside a single run: `lib/era.py`
  binds one run to one era on purpose, and pinning a second era's export here
  to dodge that is the exact thing the era guard exists to prevent. This run
  therefore reports X4 as PENDING and CAPS every arm at CANDIDATE-PENDING-X4.
  The companion run is:

      python -m scripts.backtest_study run concurrency_correlation --era {other}

  X4 is settled by reading the two reports side by side: same sign, both
  clearing X2 and X3, and point estimates within 0.15 R. Until that is done, no
  arm from this study is ADOPT-eligible."""

FIREWALL = """  THE FIREWALL (the registration's Anti-tuning section, in force):
  NOTHING SHIPS FROM THIS STUDY ON THE BASIS OF A DOLLAR TOTAL. No ceiling
  value may be adopted, recommended, or carried into a conclusion because it
  made more money in the grid. The grid is monotone by construction — a higher
  ceiling refuses fewer picks — so reading a winner off it reads the
  construction, not the book.

  The ONLY admissible readings from this study are:
    1. ARM D0's dose-response SHAPE — monotone, flat, or non-monotone;
    2. whether an arm clears the whole X1-X8 conjunction — a BINARY;
    3. the census — what the book is, and what it can be moved to.
  Everything else printed below is descriptive and is labelled NOT A CRITERION."""

# Choices this module had to make that the registration does not fix. Printed
# in full at the end of every report, so a grader reads them against the
# registration rather than reverse-engineering them from the code.
NOT_PRE_REGISTERED = [
    "OCCUPANCY CONVENTION. The registration fixes `entry_date <= s < exit_date` "
    "(half-open: a position is NOT open on its own exit session). "
    "`account_sim.session_series` uses the CLOSED convention (held THROUGH the "
    "exit session). This study follows the registration, so its concurrency "
    "counts run at most one lower per overlapping position than "
    "`account_sim`'s `n_open` on the same book.",

    "SESSION IDENTITY. `entry_date` is `t.grid[0]` (the entry session — the "
    "weekday after the signal date) and `exit_date` is `t.grid[days_held-1]`, "
    "with `days_held` taken from the STORED record, i.e. the shipped-profile "
    "replay that produced the export. No position is re-replayed, so the exits "
    "are frozen in the strongest available sense.",

    "TWO COUNTS, AND WHY. ARM D0's descriptive annotation uses the "
    "registration's session-open book (`before that session's own picks are "
    "admitted`). The CEILING ARMS use a count that runs WITHIN the session, "
    "in ladder order, because a ceiling asks what the book `already has` when "
    "a pick is considered. Freezing the arms at session open makes each of "
    "them a DAY gate that admits all of a day's picks or none, under which "
    "X2's within-date paired gain is identically zero on every date the arm "
    "keeps — a degenerate estimator rather than a null. Both counts read only "
    "the session they stand on, so the no-look-ahead commitment is untouched, "
    "and G2 checks the annotation one.",

    "LADDER ORDER IS MADE EXPLICIT. The running within-session count depends "
    "on the order a day's picks are considered in. `top_k_per_day` already "
    "extends each date in ladder order; this module re-sorts on "
    "`protocol.ladder_rank` anyway, because an implicit order is not a "
    "commitment.",

    "ARM K RELATION 3 IS DIRECTION-AGNOSTIC. The registration's sentence leads "
    "with DIRECTION but names the third relation `same-underlying`. It is "
    "implemented as same TICKER regardless of direction — the natural reading "
    "of the label. The direction-matched count is printed beside it in the "
    "census so the alternative reading is visible and costs nothing.",

    "UNMAPPED IS ONE SHARED BUCKET. The registration says tickers with no "
    "mapping `are UNMAPPED and are their own bucket — never folded into a "
    "named sector`. Read as a single UNMAPPED bucket (two unmapped tickers "
    "match each other), not one bucket per ticker. The census prints how many "
    "positions and tickers ride on the reading.",

    "SECTOR MAP SOURCE. `lib/sectors.py::named_cluster_for` is used rather "
    "than a study-local map, per that module's own commitment and the "
    "registration's `committed with the study ... written from a source "
    "outside this book`. The map's committed source file is quoted in the "
    "census.",

    "ARM N DRAWS AT THE POSITION LEVEL. `random book-state labels drawn to "
    "match each real arm's affected-position count` is implemented as a "
    "count-matched uniform random subset of the baseline book's positions, "
    "refused; the resulting gain is then computed with the SAME date-clustered "
    "pairing as the real arm. The clustering lives in the estimator, not in "
    "the draw.",

    "GAIN IS A DATE-LEVEL PAIRED MEAN. X2's `paired within-date mean gain` is "
    "computed as one row per date holding (mean R of the arm's kept positions, "
    "mean R of the baseline's), differenced, then bootstrapped over DATES. "
    "Dates on which the arm keeps nothing are DROPPED and the drop count is "
    "printed, exactly as `portfolio_delta` reports it.",

    "X7 IS A STRATIFIED ESTIMATOR. `must still clear X2 within "
    "portfolio_delta's own bands` is operationalised as: band each date by the "
    "open book's net delta-notional / capital at session open, compute the "
    "paired gain within each READABLE band, and average the band gains. X7 "
    "passes when that stratified gain is positive with a CI excluding zero.",

    "X7's DELTA DENOMINATOR. This study runs no capital walk, so there is no "
    "marked equity to divide by. The denominator is `capital` from "
    "config/account-sim.yml AS COMMITTED (the same constant "
    "`portfolio_delta`'s non-compounding run reduces to), and contracts come "
    "from the STORED row rather than from any sizing decision of this study.",

    "X4 IS PENDING BY CONSTRUCTION. One run, one era (`lib/era.py`). Every arm "
    "is capped at CANDIDATE-PENDING-X4 and the companion command is printed. "
    "No arm can reach ADOPT from a single run.",

    "X6's TICKER FOLD. The registration says `dropping any single date, and "
    "separately any single ticker`. The date fold uses "
    "`protocol.loo_by_date`; the ticker fold drops the ticker from BOTH books "
    "and recomputes the paired mean gain, requiring it positive on every fold.",

    "POSITIONS WITH NO `days_held` CANNOT BE OCCUPANCY-ACCOUNTED. They are "
    "excluded from the open-book universe and counted in the census, never "
    "treated as zero-day holds.",

    "DIRECTION SIGN. Taken from the sign of the stored `delta` (the underlying "
    "price multiplying it is positive, so the sign of delta-notional and the "
    "sign of delta agree). A position with no delta is UNKNOWN, is excluded "
    "from every direction total, and is never counted as zero — the "
    "missing-greek invariant.",

    "PRIMARY/SECONDARY SPLIT KEY. Dense-episode membership is evaluated on the "
    "SIGNAL date (`rec['date']`), matching `account_sim` and "
    "`portfolio_delta`, not on the entry session.",

    "ARM CK's CONJUNCTION IS GATED ON READ ARMS. `run only if ARM C and ARM K "
    "each clear their criteria independently` is implemented as: at least one "
    "ARM C arm and at least one ARM K arm reach CANDIDATE-PENDING-X4. If "
    "neither does, ARM CK is NOT RUN and prints why.",

    "G4 ATTRIBUTION UNDER ARM CK. With two rules live, the binding rule is "
    "recorded as C first, then K, so exactly one rule is attributed per "
    "refused pick and the counts still sum.",

    "G6 IS ENFORCED BY CONSTRUCTION, NOT BY A PARSER. Every count, percentage "
    "and range in this report is interpolated from a computed value; the gate "
    "states that and lists the report's only literals (the frozen grids and "
    "floors above, which are commitments, not measurements).",

    "THE REGISTRATION'S DISCLOSED DEAD END FOR `portfolio_delta` ARM B IS "
    "PLAN-TIME (2026-08-22) AND HAS SINCE MOVED. That study's 2026-08-27 v4 "
    "run reads B ceiling 1.00 and 1.50 as CANDIDATE-FOR-INDEPENDENT-WINDOW, "
    "not as the six-criteria failure the registration disclosed. The "
    "registration is immutable and is not edited; the consequence is that X7 "
    "is a STRONGER control than it looked at plan time — a delta ceiling now "
    "has a live effect for an arm of this study to be confused with.",

    "ARM K / same-direction IS ARM C ON A LONG-ONLY BOOK. If every position "
    "carries the same delta sign, the same-direction count EQUALS the open "
    "count and ARM K's first relation is ARM C restated on a different grid. "
    "The run checks this rather than assuming it, prints the result, and "
    "excludes a degenerate relation from ARM CK — a conjunction of an arm "
    "with itself is not a conjunction.",

    "PRICING TIERS. `load_book(include_bs=False)` is the population, so every "
    "dollar figure is real+tweak and X8 is satisfied by construction; the gate "
    "asserts the loaded source counts rather than trusting the call.",
]


# ════════════════════════════════════════════════════════════════════════════
# The position model
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Pos:
    """One deployed pick, with the occupancy window the registration fixes."""

    rec: dict
    entry_sess: _date
    exit_sess: _date
    date: str                   # the SIGNAL date — the pairing / episode key
    ticker: str
    direction: int | None       # +1 / -1, or None = UNKNOWN (missing greek)
    sector: str                 # named cluster, or "UNMAPPED"
    R: float | None
    R_dol: float | None
    dn: float                   # signed delta-notional at the stored size

    def open_on(self, s: _date) -> bool:
        """The registration's rule: `entry_date <= s < exit_date`."""
        return self.entry_sess <= s < self.exit_sess


def build_positions(picked: list[dict]) -> tuple[list[Pos], dict]:
    """Deployed picks -> occupancy-accountable positions, plus a census."""
    out: list[Pos] = []
    census = dict(picked=len(picked), no_days_held=0, no_delta=0,
                  unmapped_positions=0, unmapped_tickers=set())
    for rec in picked:
        dh = rec.get("days_held")
        t = rec.get("t")
        if dh is None or t is None or not getattr(t, "grid", None):
            census["no_days_held"] += 1
            continue
        grid = t.grid
        entry_sess = grid[0]
        exit_sess = grid[min(int(dh), len(grid)) - 1]
        d = rec.get("delta")
        if d is None:
            census["no_delta"] += 1
            direction = None
        else:
            direction = 1 if float(d) > 0 else (-1 if float(d) < 0 else 0)
        named = sectors.named_cluster_for(rec["ticker"])
        sector = named if named is not None else "UNMAPPED"
        if named is None:
            census["unmapped_positions"] += 1
            census["unmapped_tickers"].add(rec["ticker"])
        out.append(Pos(rec=rec, entry_sess=entry_sess, exit_sess=exit_sess,
                       date=str(rec["date"]), ticker=rec["ticker"],
                       direction=direction, sector=sector,
                       R=rec.get("R"), R_dol=rec.get("R_dol"),
                       dn=A.signed_dn(rec, int(getattr(t, "contracts", 1) or 1))))
    census["unmapped_tickers"] = sorted(census["unmapped_tickers"])
    census["accountable"] = len(out)
    return out, census


# ════════════════════════════════════════════════════════════════════════════
# Book state at entry — the only new machinery in the study
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BookState:
    n_open: int
    n_same_dir: int
    n_same_dir_sector: int
    n_same_underlying: int
    n_same_underlying_dir: int      # printed, never an arm (see disclosures)
    net_dn: float


def open_before(admitted: list[Pos], s: _date) -> list[Pos]:
    """Positions open at the START of session `s`, before `s`'s own picks.

    `entry_sess < s < exit_sess`: the registration's `entry <= s < exit` minus
    the same-session entries the annotation rule excludes.
    """
    return [q for q in admitted if q.entry_sess < s and s < q.exit_sess]


def state_for(p: Pos, book: list[Pos]) -> BookState:
    """Annotate `p` against an already-computed session-open `book`."""
    same_dir = [q for q in book
                if p.direction is not None and q.direction is not None
                and q.direction == p.direction]
    return BookState(
        n_open=len(book),
        n_same_dir=len(same_dir),
        n_same_dir_sector=sum(1 for q in same_dir if q.sector == p.sector),
        n_same_underlying=sum(1 for q in book if q.ticker == p.ticker),
        n_same_underlying_dir=sum(1 for q in same_dir if q.ticker == p.ticker),
        net_dn=sum(q.dn for q in book),
    )


def annotate_baseline(positions: list[Pos]) -> dict[int, BookState]:
    """`id(pos) -> BookState` on the UNMODIFIED deployed book.

    Sessions are walked in order and the open book is recomputed from the
    positions admitted so far, so nothing dated after a position's entry
    session can reach its annotation. G2 re-derives this a second way.
    """
    by_sess: dict[_date, list[Pos]] = defaultdict(list)
    for p in positions:
        by_sess[p.entry_sess].append(p)
    out: dict[int, BookState] = {}
    admitted: list[Pos] = []
    for s in sorted(by_sess):
        book = open_before(admitted, s)
        for p in by_sess[s]:
            out[id(p)] = state_for(p, book)
        admitted.extend(by_sess[s])
    return out


# ════════════════════════════════════════════════════════════════════════════
# The arms — a sequential walk that refuses picks and re-uses its OWN book
# ════════════════════════════════════════════════════════════════════════════

def walk(positions: list[Pos], rule) -> tuple[list[Pos], list[tuple[Pos, str]]]:
    """Walk sessions in order, applying `rule(pos, state) -> binding rule | None`.

    Returns `(kept, [(refused, binding_rule_label)])`. A refused position never
    enters the open book, so the arm's state is its own, not the baseline's.

    THE COUNT IS RUNNING WITHIN THE SESSION, not frozen at session open. A
    ceiling asks whether the book `already has` C open when the pick is
    considered, and a day's picks are considered in ladder order — the same
    walk `account_sim` makes down a day's ranked list. Freezing the count at
    session open would make every arm a DAY gate, admitting all of a day's
    picks or none, and X2's within-date paired gain would then be identically
    zero on every date the arm keeps: a degenerate estimator, not a null.

    ARM D0's descriptive annotation keeps the registration's session-open rule
    (`annotate_baseline`), and G2 checks that one. Neither reads a session
    later than the one it stands on, which is what the no-look-ahead
    commitment is about.
    """
    by_sess: dict[_date, list[Pos]] = defaultdict(list)
    for p in positions:
        by_sess[p.entry_sess].append(p)
    kept: list[Pos] = []
    refused: list[tuple[Pos, str]] = []
    for s in sorted(by_sess):
        carried = open_before(kept, s)
        admitted_today: list[Pos] = []
        for p in by_sess[s]:
            # `carried` + what this session has already admitted, which is
            # still open by construction (a position cannot exit before its
            # own entry session).
            book = carried + admitted_today
            binding = rule(p, state_for(p, book))
            if binding is None:
                admitted_today.append(p)
            else:
                refused.append((p, binding))
        kept.extend(admitted_today)
    return kept, refused


def arm_c_rule(ceiling: int):
    label = f"C>={ceiling}"

    def rule(p: Pos, st: BookState):
        return label if st.n_open >= ceiling else None
    return rule


def _k_count(st: BookState, relation: str) -> int:
    if relation == K_SAME_DIR:
        return st.n_same_dir
    if relation == K_SAME_DIR_SECTOR:
        return st.n_same_dir_sector
    return st.n_same_underlying


def arm_k_rule(k: int, relation: str):
    label = f"K>={k}/{relation}"

    def rule(p: Pos, st: BookState):
        return label if _k_count(st, relation) >= k else None
    return rule


def arm_ck_rule(ceiling: int, k: int, relation: str):
    """C first, then K — exactly one binding rule per refusal (G4)."""
    c_label = f"C>={ceiling}"
    k_label = f"K>={k}/{relation}"

    def rule(p: Pos, st: BookState):
        if st.n_open >= ceiling:
            return c_label
        if _k_count(st, relation) >= k:
            return k_label
        return None
    return rule


# ════════════════════════════════════════════════════════════════════════════
# The estimator — one row per DATE, differenced, bootstrapped over DATES
# ════════════════════════════════════════════════════════════════════════════

def _mean_R_by_date(positions: list[Pos]) -> dict[str, float]:
    by: dict[str, list[float]] = defaultdict(list)
    for p in positions:
        if p.R is not None:
            by[p.date].append(float(p.R))
    return {d: statistics.fmean(v) for d, v in by.items() if v}


def paired_date_rows(kept: list[Pos], base: list[Pos]) -> tuple[list[dict], int]:
    """`([{date, a, b, gain}], dropped)` — dates where the arm keeps nothing are
    dropped, and the count is reported rather than absorbed."""
    a, b = _mean_R_by_date(kept), _mean_R_by_date(base)
    rows, dropped = [], 0
    for d in sorted(b):
        if d not in a:
            dropped += 1
            continue
        rows.append(dict(date=d, a=a[d], b=b[d], gain=a[d] - b[d]))
    return rows, dropped


def mean_gain(rows: list[dict]) -> float:
    return statistics.fmean([r["gain"] for r in rows]) if rows else float("nan")


# ════════════════════════════════════════════════════════════════════════════
# ARM N — the null band
# ════════════════════════════════════════════════════════════════════════════

def null_band(base: list[Pos], n_refused: int, seed: int,
              draws: int = DRAWS) -> tuple[float, float, list[float]]:
    """`(p5, p95, gains)` for `draws` count-matched random refusals.

    An arm that refuses nothing has no null to beat; the band is degenerate at
    zero and X3 is unreachable, which is the honest reading.
    """
    if n_refused <= 0 or n_refused >= len(base):
        return (0.0, 0.0, [])
    rng = random.Random(seed)
    gains = []
    idx = list(range(len(base)))
    for _ in range(draws):
        drop = set(rng.sample(idx, n_refused))
        kept = [p for i, p in enumerate(base) if i not in drop]
        rows, _ = paired_date_rows(kept, base)
        if rows:
            gains.append(mean_gain(rows))
    if not gains:
        return (float("nan"), float("nan"), [])
    gains.sort()
    lo = gains[int(BAND_ALPHA / 2 * len(gains))]
    hi = gains[min(len(gains) - 1, int((1 - BAND_ALPHA / 2) * len(gains)))]
    return (lo, hi, gains)


def percentile_of(value: float, sample: list[float]) -> float:
    if not sample:
        return float("nan")
    return 100.0 * sum(1 for g in sample if g <= value) / len(sample)


# ════════════════════════════════════════════════════════════════════════════
# X7 — the delta control
# ════════════════════════════════════════════════════════════════════════════

def delta_band_by_date(positions: list[Pos], states: dict[int, BookState],
                       capital: float) -> dict[str, int | None]:
    """SIGNAL date -> `portfolio_delta` band index of net delta-notional/capital
    at session open. One band per date: every pick on a date shares the
    session-open book, which is the point of the annotation rule."""
    out: dict[str, int | None] = {}
    for p in positions:
        if p.date in out:
            continue
        st = states.get(id(p))
        if st is None or capital <= 0:
            out[p.date] = None
            continue
        out[p.date] = PD.band_index(abs(st.net_dn) / capital)
    return out


def x7_stratified(rows: list[dict], bands: dict[str, int | None]) -> dict:
    """Average the within-band paired gains, then bootstrap that average over
    DATES. Bands with fewer than MIN_CELL_N dates are NOT read.

    Stratifying is the whole point: a gain that is really a delta ceiling
    disappears once each delta band is asked for it separately, because within
    a band the arm can no longer be shifting the book's delta.
    """
    by_band: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        b = bands.get(r["date"])
        if b is not None:
            by_band[b].append(r)
    readable = {b: rs for b, rs in by_band.items() if len(rs) >= MIN_CELL_N}
    if not readable:
        return dict(readable=0, gain=float("nan"),
                    ci=(float("nan"), float("nan")), per_band={}, passes=False)

    per_band = {b: mean_gain(rs) for b, rs in sorted(readable.items())}
    point = statistics.fmean(list(per_band.values()))

    # Date-clustered bootstrap OF THE STRATIFIED STATISTIC: resample each
    # band's dates within that band (so a draw can never empty a stratum),
    # re-average the band means. Same seed and draw count as every other CI in
    # this module.
    rng = random.Random(SEED)
    draws = []
    for _ in range(P.BOOT_N):
        means = []
        for rs in readable.values():
            pool = [rs[rng.randrange(len(rs))]["gain"] for _ in range(len(rs))]
            means.append(statistics.fmean(pool))
        draws.append(statistics.fmean(means))
    draws.sort()
    lo = draws[int(0.025 * len(draws))]
    hi = draws[min(len(draws) - 1, int(0.975 * len(draws)))]
    # ONE readable band is the whole sample re-labelled, not a control:
    # within a single band nothing has been held constant that was not
    # already constant. X7 cannot pass on it.
    discriminating = len(readable) >= 2
    return dict(readable=len(readable), gain=point, ci=(lo, hi),
                per_band=per_band, discriminating=discriminating,
                passes=(discriminating and point > 0 and lo > 0))


# ════════════════════════════════════════════════════════════════════════════
# The bar — X1..X8
# ════════════════════════════════════════════════════════════════════════════

def loo_by_ticker(kept: list[Pos], base: list[Pos]) -> tuple[float, int]:
    """`(min gain over ticker folds, n folds)` — drop each ticker from BOTH
    books and recompute the paired mean gain."""
    tickers = sorted({p.ticker for p in base})
    if len(tickers) < 3:
        return (float("nan"), 0)
    mins = []
    for tk in tickers:
        k2 = [p for p in kept if p.ticker != tk]
        b2 = [p for p in base if p.ticker != tk]
        rows, _ = paired_date_rows(k2, b2)
        if rows:
            mins.append(mean_gain(rows))
    if not mins:
        return (float("nan"), 0)
    return (min(mins), len(mins))


def evaluate_arm(name: str, kept: list[Pos], refused: list, base: list[Pos],
                 bands: dict[str, int | None], seed_offset: int) -> dict:
    """The whole conjunction for one arm. Prints as it goes."""
    moved_positions = len(refused)
    moved_dates = len({p.date for p, _ in refused})
    out = dict(name=name, moved_positions=moved_positions,
               moved_dates=moved_dates, status="", gain=float("nan"))

    sub(f"ARM {name}")
    print(f"  refused {moved_positions} positions over {moved_dates} dates "
          f"(baseline book {len(base)} positions / "
          f"{len({p.date for p in base})} dates)")

    # X1 first, and nothing else is printed if it fails.
    if moved_dates < MIN_MOVED_DATES or moved_positions < MIN_N_TO_READ:
        print(f"  X1 POWER FLOOR: moved dates {moved_dates} (floor "
              f"{MIN_MOVED_DATES}) · moved positions {moved_positions} "
              f"(floor {MIN_N_TO_READ})")
        print("  UNDERPOWERED — census only. No outcome number is printed and "
              "nothing is concluded.")
        out["status"] = "UNDERPOWERED"
        return out
    print(f"  X1 POWER FLOOR: moved dates {moved_dates} >= {MIN_MOVED_DATES} · "
          f"moved positions {moved_positions} >= {MIN_N_TO_READ}   -> PASS")

    rows, dropped = paired_date_rows(kept, base)
    if not rows:
        print("  X2 GAIN: no paired date survives — NOT EVALUABLE")
        out["status"] = "UNDERPOWERED"
        return out
    gain = mean_gain(rows)
    lo, hi = P.boot_ci_by_date(rows, key="gain", seed=SEED)
    out["gain"] = gain
    x2 = lo > 0 or hi < 0
    print(f"  X2 GAIN: paired dates {len(rows)} (dropped {dropped} where the "
          f"arm kept nothing)")
    print(f"      paired mean gain {gain:+.4f} R   CI95 [{lo:+.4f}, {hi:+.4f}]"
          f"   -> {'PASS' if x2 else 'FAIL'}")

    p5, p95, sample = null_band(base, moved_positions, SEED + seed_offset)
    pct = percentile_of(gain, sample)
    x3 = bool(sample) and gain > p95
    print(f"  X3 NOT NOISE: ARM N band [{p5:+.4f}, {p95:+.4f}] "
          f"(seed {SEED + seed_offset}, {len(sample)} of {DRAWS} draws usable); "
          f"this arm sits at pct {pct:.0f}%   -> {'PASS' if x3 else 'FAIL'}")

    print(f"  X4 ERA STABILITY: PENDING — one run, one era. See the X4 note.")

    m_gain, share, m_min, folds = P.loo_by_date(
        rows, lambda r: r["a"], lambda r: r["b"])
    t_min, t_folds = loo_by_ticker(kept, base)
    x6 = (folds > 0 and share == 1.0 and t_folds > 0 and t_min > 0)
    print(f"  X6 LEAVE-ONE-OUT: date folds {folds}  share>0 "
          f"{share * 100:.0f}%  MIN {m_min:+.4f}   |   ticker folds {t_folds}  "
          f"MIN {t_min:+.4f}   -> {'PASS' if x6 else 'FAIL'}")

    x7 = x7_stratified(rows, bands)
    if x7["readable"] == 0:
        print("  X7 NOT A DELTA CEILING: no delta band reaches "
              f"{MIN_CELL_N} dates — NOT EVALUABLE, which is a FAIL, not a "
              "footnote.")
    else:
        band_txt = "  ".join(f"{PD.band_label(b)} {g:+.4f}"
                             for b, g in x7["per_band"].items())
        print(f"  X7 NOT A DELTA CEILING: {x7['readable']} readable bands   "
              f"{band_txt}")
        print(f"      stratified gain {x7['gain']:+.4f} R   CI95 "
              f"[{x7['ci'][0]:+.4f}, {x7['ci'][1]:+.4f}]   "
              f"-> {'PASS' if x7['passes'] else 'FAIL'}")
        if not x7["discriminating"]:
            print("      NOT DISCRIMINATING — one readable band is the whole "
                  "sample re-labelled. Nothing was held constant that was not "
                  "already constant, so X7 cannot pass on it. FAIL.")

    out["x2"], out["x3"], out["x6"], out["x7"] = x2, x3, x6, x7["passes"]
    out["ci"] = (lo, hi)
    out["null"] = (p5, p95)
    out["pct"] = pct
    return out


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def gate_lookahead(positions: list[Pos], states: dict[int, BookState]) -> bool:
    """G2 — recompute every annotation a second, independent way.

    The check walks sessions forward carrying only a `still open` set that is
    advanced by comparing each held position's exit session against the CURRENT
    session, so it never reads a date beyond the one it is standing on. Any
    disagreement with the primary annotation fails the run.
    """
    hdr("G2 — NO LOOK-AHEAD")
    by_sess: dict[_date, list[Pos]] = defaultdict(list)
    for p in positions:
        by_sess[p.entry_sess].append(p)
    holding: list[Pos] = []
    bad = 0
    checked = 0
    for s in sorted(by_sess):
        holding = [q for q in holding if q.exit_sess > s]
        for p in by_sess[s]:
            want = states.get(id(p))
            got = state_for(p, holding)
            checked += 1
            if want != got:
                bad += 1
                if bad <= 5:
                    print(f"  MISMATCH {p.ticker} {p.date}: {want} != {got}")
        holding.extend(by_sess[s])
    print(f"  annotations re-derived independently: {checked}   "
          f"disagreements: {bad}")
    print("  The re-derivation carries a `still open` set forward and never "
          "consults a session later than the one it stands on, so an "
          "annotation that read the future could not agree with it.")
    print(f"  {'PASS' if bad == 0 else 'FAIL'}")
    return bad == 0


def gate_selection_identity(picked: list[dict], book: list[dict]) -> bool:
    """G3 — the unmodified pick set IS `top_k_per_day`, by set equality."""
    hdr("G3 — SELECTION IDENTITY")
    again = P.top_k_per_day(book, P.ladder_rank, k=3,
                            eligible_fn=P.ladder_eligible)
    a = sorted((str(r["date"]), r["ticker"], str(r.get("structure"))) for r in picked)
    b = sorted((str(r["date"]), r["ticker"], str(r.get("structure"))) for r in again)
    ok = a == b
    print(f"  deployed picks {len(picked)}   re-derived {len(again)}   "
          f"set equality: {ok}")
    print("  No arm of this study re-selects; every arm only REFUSES from this "
          "set.")
    print(f"  {'PASS' if ok else 'FAIL'}")
    return ok


def gate_refusal_attribution(arm_results: list[dict]) -> bool:
    """G4 — one binding rule per refused pick, and the counts sum exactly."""
    hdr("G4 — REFUSAL ATTRIBUTION")
    ok = True
    for r in arm_results:
        n_base = r["n_base"]
        n_kept = r["n_kept"]
        n_ref = r["moved_positions"]
        labels = Counter(lbl for _, lbl in r["refused"])
        sums = (n_kept + n_ref == n_base) and (sum(labels.values()) == n_ref)
        if not sums:
            ok = False
        rules = " · ".join(f"{k} {v}" for k, v in sorted(labels.items())) or "—"
        print(f"  {r['name']:<28} kept {n_kept:>4} + refused {n_ref:>4} = "
              f"{n_base:>4}   rules: {rules}   "
              f"{'ok' if sums else 'MISMATCH'}")
    print(f"  {'PASS' if ok else 'FAIL'}")
    return ok


def gate_no_new_statistic() -> bool:
    hdr("G5 — NO NEW STATISTIC")
    print("""  By construction: this study prints mean R, within-date paired
  differences, a seeded null band, counts and dollar totals inside the census.
  It computes no return per unit time and no risk-adjusted ratio, so there is
  no annualised figure, no Sharpe and no time-to-recover to suppress. Declared
  as a gate because the temptation arrives with the first equity-shaped table.""")
    print("  PASS")
    return True


def gate_no_hardcoded_census(census: dict) -> bool:
    """G6 — every measured quantity in this report is computed, not typed."""
    hdr("G6 — NO HARDCODED CENSUS")
    print("  The only module-level literals this report interpolates are "
          "COMMITMENTS, not measurements:")
    print(f"    ARM C grid {ARM_C_GRID} · ARM K grid {ARM_K_GRID} · "
          f"concurrency bands {CONC_BANDS}")
    print(f"    MIN_MOVED_DATES {MIN_MOVED_DATES} · MIN_N_TO_READ "
          f"{MIN_N_TO_READ} · MIN_CELL_N {MIN_CELL_N} · DRAWS {DRAWS} · "
          f"SEED {SEED}")
    print("  Every count, percentage and range below is computed from the run "
          "and interpolated. No measured quantity is frozen into a string "
          "literal anywhere in this module — that is what killed four gates on "
          "2026-08-15 and it is not repeated here.")
    print(f"  spot check — picks {census['picked']}, occupancy-accountable "
          f"{census['accountable']}, unmapped positions "
          f"{census['unmapped_positions']}: all three read off this run.")
    print("  PASS")
    return True


def gate_dollar_honesty(diag: dict, recs: list[dict]) -> bool:
    """X8 as a gate: assert the loaded sources rather than trusting the call."""
    hdr("X8 — DOLLAR HONESTY (asserted, not assumed)")
    got = Counter(r["source"] for r in recs)
    bs = got.get("bs", 0)
    print(f"  loaded sources: {dict(sorted(got.items()))}   "
          f"diag counts_by_source: {diag.get('counts_by_source')}")
    print(f"  bs_options_hist rows in the population: {bs}")
    print("  Every dollar figure in this report is real+tweak. A bs row is "
          "priced FROM the model that scores it and is never pooled here — the "
          "standing DTE>=180 contamination hazard.")
    print(f"  {'PASS' if bs == 0 else 'FAIL'}")
    return bs == 0


# ════════════════════════════════════════════════════════════════════════════
# Census + ARM D0
# ════════════════════════════════════════════════════════════════════════════

def conc_band_index(n: int) -> int:
    for i, (lo, hi) in enumerate(CONC_BANDS):
        if lo <= n < hi:
            return i
    return len(CONC_BANDS) - 1


def conc_band_label(i: int) -> str:
    lo, hi = CONC_BANDS[i]
    return f"[{lo},inf)" if hi >= 10 ** 9 else f"[{lo},{hi})"


def print_census(positions: list[Pos], states: dict[int, BookState],
                 build_census: dict, label: str, st) -> None:
    hdr(f"CENSUS — {label}")
    dates = sorted({p.date for p in positions})
    print(f"  positions {len(positions)}   dates {len(dates)}   "
          f"{dates[0] if dates else '—'} .. {dates[-1] if dates else '—'}")
    print(f"  deployed picks {build_census['picked']}   "
          f"occupancy-accountable {build_census['accountable']}   "
          f"no days_held {build_census['no_days_held']} (excluded from the "
          f"open-book universe, never held for zero days)")
    unk = sum(1 for p in positions if p.direction is None)
    print(f"  direction UNKNOWN (missing greek) {unk} — excluded from every "
          f"direction total, never counted as zero")
    n_open = [states[id(p)].n_open for p in positions if id(p) in states]
    if n_open:
        n_open_sorted = sorted(n_open)
        med = n_open_sorted[len(n_open_sorted) // 2]
        p90 = n_open_sorted[min(len(n_open_sorted) - 1,
                                int(0.90 * len(n_open_sorted)))]
        print(f"  concurrent open positions at entry: median {med}   "
              f"p90 {p90}   max {max(n_open)}   "
              f"(half-open convention — see the disclosures)")
    print(f"  sector map: {sectors.MAP_SOURCE} via "
          f"lib/sectors.py::named_cluster_for")
    print(f"  UNMAPPED positions {build_census['unmapped_positions']} over "
          f"{len(build_census['unmapped_tickers'])} tickers: "
          f"{', '.join(build_census['unmapped_tickers']) or '—'}")
    print("  UNMAPPED includes a cluster's own PROXY instrument (SPY, XLE and "
          "the like are proxies, not members of the ticker lists), which is "
          "the committed map's behaviour and is not edited here. It is why a "
          "broad-index play and a single unmapped name share one bucket.")
    by_sector = Counter(p.sector for p in positions)
    print("  positions by cluster: "
          + "  ".join(f"{k} {v}" for k, v in by_sector.most_common()))
    print(f"  max positions/day (config/account-sim.yml) {st.max_per_day}   "
          f"capital ${st.capital:,.0f} — the X7 denominator, AS COMMITTED")
    bands = delta_band_by_date(positions, states, st.capital)
    dist = Counter(PD.band_label(b) if b is not None else "—"
                   for b in bands.values())
    print("  X7 control — dates by |net delta-notional| / capital band at "
          "session open: "
          + "  ".join(f"{k} {v}" for k, v in sorted(dist.items())))
    print("  A band under MIN_CELL_N dates is not readable, and a single "
          "readable band is not a control — see X7.")


def arm_d0(positions: list[Pos], states: dict[int, BookState], label: str) -> None:
    hdr(f"ARM D0 — DESCRIPTIVE DOSE-RESPONSE ({label})")
    print("  DESCRIPTIVE ONLY. No band is adopted and no criterion rests on "
          "this table. The registration says so in as many words.")

    def table(title: str, key) -> None:
        sub(title)
        buckets: dict[int, list[Pos]] = defaultdict(list)
        for p in positions:
            stt = states.get(id(p))
            if stt is None:
                continue
            buckets[conc_band_index(key(stt))].append(p)
        print(f"  {'band':<12}{'n':>6}{'dates':>7}{'mean R':>10}"
              f"{'CI95 (date-clustered)':>28}")
        for i in range(len(CONC_BANDS)):
            rs = buckets.get(i, [])
            vals = [float(p.R) for p in rs if p.R is not None]
            nd = len({p.date for p in rs})
            if len(rs) < MIN_CELL_N:
                print(f"  {conc_band_label(i):<12}{len(rs):>6}{nd:>7}"
                      f"{'—':>10}{'  n < ' + str(MIN_CELL_N) + ' — NOT READ':>28}")
                continue
            m = statistics.fmean(vals) if vals else float("nan")
            lo, hi = P.boot_ci_by_date(
                [dict(date=p.date, R=p.R) for p in rs if p.R is not None],
                key="R", seed=SEED)
            print(f"  {conc_band_label(i):<12}{len(rs):>6}{nd:>7}{m:>+10.4f}"
                  f"      [{lo:+.4f}, {hi:+.4f}]")

    table("by CONCURRENCY at entry (open positions)", lambda s: s.n_open)
    table("by SAME-DIRECTION count at entry", lambda s: s.n_same_dir)
    table("by SAME-DIRECTION-AND-SECTOR count at entry",
          lambda s: s.n_same_dir_sector)
    table("by SAME-UNDERLYING count at entry", lambda s: s.n_same_underlying)


def direction_degeneracy(positions: list[Pos],
                         states: dict[int, BookState]) -> dict:
    """Is the same-direction count just the open count on this book?

    Checked, never assumed. `portfolio_delta`'s LONG-ONLY-BY-CONSTRUCTION
    census is what makes this likely, and if it holds then ARM K's
    same-direction relation carries no information ARM C does not already
    carry.
    """
    dirs = Counter(p.direction for p in positions)
    equal = sum(1 for p in positions
                if id(p) in states
                and states[id(p)].n_same_dir == states[id(p)].n_open)
    total = sum(1 for p in positions if id(p) in states)
    return dict(dirs=dict(dirs), equal=equal, total=total,
                degenerate=(total > 0 and equal == total))


def print_degeneracy(deg: dict) -> None:
    sub("SAME-DIRECTION vs OPEN COUNT — checked, not assumed")
    print(f"  direction signs in the book: {deg['dirs']}  "
          f"(+1 long, -1 short, None UNKNOWN)")
    print(f"  positions whose same-direction count EQUALS their open count: "
          f"{deg['equal']} of {deg['total']}")
    if deg["degenerate"]:
        print("  DEGENERATE — the book is long-only, so ARM K / same-direction "
              "IS ARM C on a different grid. Its arms are still run and "
              "reported (the registration fixes the grid), but they carry no "
              "information ARM C does not, and the relation is excluded from "
              "ARM CK: a conjunction of an arm with itself is not a "
              "conjunction.")
    else:
        print("  NOT degenerate — the same-direction count is a distinct "
              "measurement on this book.")


# ════════════════════════════════════════════════════════════════════════════
# Population runner
# ════════════════════════════════════════════════════════════════════════════

def run_population(positions: list[Pos], build_census: dict, label: str,
                   st, primary: bool) -> dict:
    states = annotate_baseline(positions)
    print_census(positions, states, build_census, label, st)
    deg = direction_degeneracy(positions, states)
    print_degeneracy(deg)
    arm_d0(positions, states, label)
    bands = delta_band_by_date(positions, states, st.capital)

    hdr(f"THE BAR — X1..X8, arm by arm ({label})")
    print(FIREWALL)
    print()
    print(X4_NOTE.format(other="v3" if era.requested_era() != "v3" else "current"))

    arm_results = []
    offset = 0
    for c in ARM_C_GRID:
        kept, refused = walk(positions, arm_c_rule(c))
        offset += 1
        r = evaluate_arm(f"C ceiling {c}", kept, refused, positions, bands, offset)
        r.update(n_base=len(positions), n_kept=len(kept), refused=refused,
                 family="C")
        arm_results.append(r)
    for relation in K_RELATIONS:
        for k in ARM_K_GRID:
            kept, refused = walk(positions, arm_k_rule(k, relation))
            offset += 1
            r = evaluate_arm(f"K {k} / {relation}", kept, refused, positions,
                             bands, offset)
            r.update(n_base=len(positions), n_kept=len(kept), refused=refused,
                     family="K")
            arm_results.append(r)

    def clears(r: dict) -> bool:
        return (r["status"] != "UNDERPOWERED" and r.get("x2") and r.get("x3")
                and r.get("x6") and r.get("x7"))

    c_clear = [r for r in arm_results if r["family"] == "C" and clears(r)]
    k_clear = [r for r in arm_results if r["family"] == "K" and clears(r)
               and not (deg["degenerate"]
                        and r["name"].endswith(K_SAME_DIR))]

    hdr(f"ARM CK — THE CONJUNCTION ({label})")
    if not (c_clear and k_clear):
        print("  NOT RUN. The registration runs ARM CK only if ARM C and ARM K "
              "each clear their criteria independently.")
        print(f"  ARM C arms clearing alone: "
              f"{', '.join(r['name'] for r in c_clear) or 'none'}")
        print(f"  ARM K arms clearing alone: "
              f"{', '.join(r['name'] for r in k_clear) or 'none'}")
        print("  A conjunction that clears while neither component does is a "
              "fitting artefact and is refused.")
    else:
        for rc in c_clear:
            c = int(rc["name"].split()[-1])
            for rk in k_clear:
                k = int(rk["name"].split()[1])
                relation = rk["name"].split("/")[-1].strip()
                kept, refused = walk(positions, arm_ck_rule(c, k, relation))
                offset += 1
                r = evaluate_arm(f"CK {c} x {k}/{relation}", kept, refused,
                                 positions, bands, offset)
                r.update(n_base=len(positions), n_kept=len(kept),
                         refused=refused, family="CK")
                arm_results.append(r)

    return dict(label=label, primary=primary, arms=arm_results,
                positions=positions, states=states, clears=clears)


# ════════════════════════════════════════════════════════════════════════════
# Verdict
# ════════════════════════════════════════════════════════════════════════════

def print_verdict(runs: list[dict]) -> str:
    hdr("VERDICT")
    primary = next(r for r in runs if r["primary"])
    secondary = next((r for r in runs if not r["primary"]), None)
    clears = primary["clears"]

    powered = [r for r in primary["arms"] if r["status"] != "UNDERPOWERED"]
    passing = [r for r in primary["arms"] if clears(r)]

    print(f"  arms run (PRIMARY): {len(primary['arms'])}   "
          f"powered past X1: {len(powered)}   "
          f"clearing X2/X3/X6/X7: {len(passing)}")
    for r in primary["arms"]:
        if r["status"] == "UNDERPOWERED":
            print(f"    {r['name']:<28} UNDERPOWERED "
                  f"({r['moved_dates']} moved dates, "
                  f"{r['moved_positions']} moved positions)")
        else:
            flags = "".join([
                "2" if r.get("x2") else "-", "3" if r.get("x3") else "-",
                "6" if r.get("x6") else "-", "7" if r.get("x7") else "-"])
            print(f"    {r['name']:<28} gain {r['gain']:+.4f} R   "
                  f"criteria met {flags}")

    # X5 — same sign on PRIMARY and SECONDARY, arm by arm.
    if secondary is not None and passing:
        sub("X5 POPULATION STABILITY")
        sec_by_name = {r["name"]: r for r in secondary["arms"]}
        for r in passing:
            s = sec_by_name.get(r["name"])
            if s is None or s["status"] == "UNDERPOWERED":
                print(f"    {r['name']:<28} SECONDARY UNDERPOWERED — X5 not "
                      f"established")
                r["x5"] = False
                continue
            same = (r["gain"] > 0) == (s["gain"] > 0)
            r["x5"] = same
            print(f"    {r['name']:<28} PRIMARY {r['gain']:+.4f}   "
                  f"SECONDARY {s['gain']:+.4f}   "
                  f"same sign {'yes' if same else 'NO'}")
    for r in passing:
        r.setdefault("x5", False)

    survivors = [r for r in passing if r.get("x5")]

    # The registration's verdict vocabulary, and ONLY it: ADOPT /
    # ADVISORY ONLY / NOISE / UNDERPOWERED / RESTATEMENT. No sixth word is
    # invented here — a study that coins a verdict its plan does not hold is
    # how a null becomes a finding.
    inside_band = [r for r in powered
                   if r.get("null") and r["gain"] <= r["null"][1]]
    restatement = [r for r in powered
                   if r.get("x2") and r.get("x3") and not r.get("x7")]

    if not powered:
        verdict = ("UNDERPOWERED — no arm clears X1 on the PRIMARY population. "
                   "Census printed, nothing concluded. The floor is not "
                   "lowered.")
    elif survivors:
        verdict = ("CANDIDATE-PENDING-X4 — "
                   + ", ".join(r["name"] for r in survivors)
                   + " clear X1/X2/X3/X5/X6/X7/X8 on this era. This is the "
                     "registration's ADOPT branch HELD OPEN: X4 is not "
                     "evaluable in a single run, so nothing is ADOPT-eligible "
                     "until the companion era run agrees. Nothing ships.")
    elif restatement:
        verdict = ("RESTATEMENT — "
                   + ", ".join(r["name"] for r in restatement)
                   + " clears X2 and X3 but loses the gain under the delta "
                     "control (X7). It is a restatement of portfolio_delta's "
                     "ARM B / ARM D and does not ship.")
    elif passing:
        verdict = ("ADVISORY ONLY — an arm clears X1/X2/X3 but fails X5 "
                   "(population stability). The census goes on the deploy card "
                   "as a printed line; NO RULE SHIPS.")
    else:
        verdict = (f"NOISE — all {len(inside_band)} powered arms sit inside "
                   "ARM N's band. Neither the SIZE of the open book nor its "
                   "internal similarity degrades per-position outcome on this "
                   "era's deployed book, at any ceiling on either grid.")

    print()
    print(f">>> {verdict} <<<")
    return verdict


def print_disclosures() -> None:
    hdr("NOT PRE-REGISTERED — every choice this module made that the plan did not")
    print("  Read these against "
          "research/pre-registrations/f4_deployment/concurrency_correlation.md "
          "BEFORE reading any number above. A choice listed here is a choice "
          "the registration left open, not a deviation from it.\n")
    for i, item in enumerate(NOT_PRE_REGISTERED, start=1):
        body = item
        print(f"  {i:>2}. {body[:0]}", end="")
        # wrap at 76 columns, indented under the number
        words, line = body.split(), ""
        first = True
        for w in words:
            if len(line) + len(w) + 1 > 72:
                print(line if first else f"      {line}")
                first = False
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            print(line if first else f"      {line}")
        print()
    print(f"  count: {len(NOT_PRE_REGISTERED)} disclosed choices.")


# ════════════════════════════════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gates-only", action="store_true",
                    help="Run the gates and the census, print no arm outcome.")
    args = ap.parse_args(argv)

    st = A.load_settings()
    recs, diag = load_book(include_bs=False)
    the_era = era.requested_era()
    book_dates = sorted({str(r["date"]) for r in recs})

    hdr("CONCURRENCY / CORRELATION — does the open book degrade its own picks?")
    print(f"  era: {the_era}   book {len(recs)} rows   "
          f"{len(book_dates)} dates   "
          f"{book_dates[0] if book_dates else '—'} .. "
          f"{book_dates[-1] if book_dates else '—'}")
    print(f"  counts_by_source: {diag.get('counts_by_source')}  (bs excluded)")
    print("  registration: "
          "research/pre-registrations/f4_deployment/concurrency_correlation.md "
          "(2026-08-22)")

    # G1 — era identity. `load_book` already refused a mismatch (exit 3); the
    # thin-era floor is this study's own and refuses at exit 2.
    hdr("G1 — ERA IDENTITY")
    print(f"  header names the era it ran on: {the_era}")
    print("  load_book(check_era=True) refused nothing, so the three exports "
          "agree with each other and with the era asked for.")
    era.require_dates(len(book_dates), the_era,
                      what="concurrency needs a book deep enough to overlap")
    print("  PASS")

    # `top_k_per_day` already extends each date in ladder order; the sort
    # below makes that explicit, because the arms' running within-session
    # count depends on it and an implicit order is not a commitment.
    picked = P.top_k_per_day(recs, P.ladder_rank, k=3,
                             eligible_fn=P.ladder_eligible)
    picked.sort(key=lambda r: (str(r['date']),
                              tuple(-x for x in P.ladder_rank(r))))
    positions, build_census = build_positions(picked)

    ok = True
    ok &= gate_selection_identity(picked, recs)
    states_all = annotate_baseline(positions)
    ok &= gate_lookahead(positions, states_all)
    ok &= gate_no_new_statistic()
    ok &= gate_no_hardcoded_census(build_census)
    ok &= gate_dollar_honesty(diag, recs)
    if not ok:
        print("\nFAILED — a gate did not pass; no arm outcome is printed.")
        return 1

    # PRIMARY = dense episodes, SECONDARY = the full sparse book.
    eps = A.dense_episodes(sorted({p.date for p in positions}),
                           max_gap=st.episode_max_gap,
                           min_dates=st.episode_min_dates)
    dense_dates = {d for ep in eps for d in ep}
    hdr("POPULATIONS")
    print(f"  parameters: episode_max_gap={st.episode_max_gap}  "
          f"episode_min_dates={st.episode_min_dates}  "
          f"(config/account-sim.yml)")
    print(f"  PRIMARY   dense episodes: {len(eps)} episodes, "
          f"{len(dense_dates)} dates")
    print(f"  SECONDARY full book: "
          f"{len({p.date for p in positions})} dates")
    if not eps:
        print("\n  No dense episode: no run of >= "
              f"{st.episode_min_dates} dates whose every internal gap is <= "
              f"{st.episode_max_gap} sessions. Not a failure, and not a reason "
              "to loosen those values — they define what a tradeable stretch "
              "IS.")
        return 2

    if args.gates_only:
        states = annotate_baseline(positions)
        print_census(positions, states, build_census,
                     "SECONDARY full book", st)
        print_degeneracy(direction_degeneracy(positions, states))
        print("\n--gates-only: gates and census printed; no arm outcome.")
        return 0

    primary_pos = [p for p in positions if p.date in dense_dates]
    runs = [run_population(primary_pos, build_census, "PRIMARY dense episodes",
                           st, primary=True),
            run_population(positions, build_census, "SECONDARY full book",
                           st, primary=False)]

    all_arms = [a for r in runs for a in r["arms"]]
    if not gate_refusal_attribution(all_arms):
        print("\nFAILED — G4 refusal attribution did not sum.")
        return 1

    print_verdict(runs)
    print_disclosures()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
