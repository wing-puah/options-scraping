"""HEDGE-CONCENTRATION — on the ADMITTED book, does concentration predict drawdown, and only then can a hedge cut it?

Pre-registered 2026-08-31. Registration:
`research/pre-registrations/f4_deployment/hedge_concentration.md`, where
`scripts/study_review/` reads it. Read it before quoting anything printed here.

This is the "third reading" `hedge_exposure`'s errata named and declined to run
under its own registration (post-ratification note 3): the SAME ratified
population and the SAME ratified prices, but an ADMISSION MODEL over which of
those plays are held at once. `hedge_exposure` held every ratified row
concurrently; the operator's card admits at most `max_positions_per_day` new
positions a day and respects the cash and delta caps, so the book actually run
is `account_sim.simulate()`'s admitted subset — a smaller, more CONCENTRATED
book than the one `hedge_exposure` measured.

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

Run:
    source .venv/bin/activate
    python -m scripts.backtest_study run hedge_concentration
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
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f4_deployment import account_sim as A  # noqa: E402
from scripts.backtest_study.f4_deployment import hedge_exposure as HE  # noqa: E402
from scripts.backtest_study.lib import concentration as C  # noqa: E402
from scripts.backtest_study.lib import forward_drawdown as F  # noqa: E402
from scripts.backtest_study.lib import hedge_instrument as HI  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as M  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import sectors as S  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# 2 and 3 belong to lib/era.py's thin-era and era-mismatch refusals. A LITERAL
# set: run.py::_refusal_codes parses it with `ast` and never imports the module,
# so an alias or a frozenset() call is invisible to it.
#   4 = G-MTM (imported from hedge_exposure, the same gate on the same curve)
#   5 = G-ADMIT (this study's own: the admitted book must BE account_sim's)
DESIGNED_REFUSAL_EXIT_CODES = {2, 3, 4, 5}

EXIT_MTM_RECONCILE = HE.EXIT_MTM_RECONCILE      # 4 — imported, never restated
EXIT_ADMIT = 5

# G-BLIND is NOT in that set, on purpose and exactly as in `hedge_exposure`. A
# trigger that moves when the outcome columns are stripped is a DEFECT in this
# module, not a pre-registered refusal, so it exits 1 and the runner deletes
# -latest.txt rather than promoting it.
EXIT_LOOKAHEAD = 1

# ── committed constants ─────────────────────────────────────────────────────
#: Stage 1's horizon, fixed in the registration before any outcome was read.
H = 20
#: ARM K10's horizon — a DISCLOSED SENSITIVITY that carries no verdict.
H_SENS = 10

#: THIS STUDY'S OWN tau grid, fixed by its registration: the admitted book's
#: median / p75 / p90 concentration, rounded. It is deliberately NOT
#: `C.TAU_GRID` (0.30 / 0.35 / 0.40), which is `hedge_exposure`'s grid on a
#: book more than twice as diversified. Sharing that constant would silently
#: run this study on a trigger the registration did not commit.
TAU_GRID = (0.45, 0.55, 0.65)

#: The risk fractions are the same committed grid, so they ARE the library's.
F_GRID = C.F_GRID                       # (0.25, 0.50, 1.00)

N_CELLS = len(TAU_GRID) * len(F_GRID)   # 9; Bonferroni denominator, fixed here
ALPHA = 0.05 / N_CELLS

MIN_TRIGGER_DATES = C.MIN_TRIGGER_DATES  # 25, date-clustered — G-POWER
FILL_GATE = HI.FILL_GATE                 # 0.60, band rule — G-FILL
BOOT_N = P.BOOT_N                        # 10,000 block-bootstrap resamples
KN_DRAWS = 1000                          # ARM KN, as registered
N_SEEDS = 200                            # ARM N, as registered
SEED = 20260831

#: G-POWER-K, Stage 1's power gate, both parts registered.
MIN_TERCILE_SESSIONS = 60
MIN_DENSE_EPISODES = 3
#: Bar clause 5 — a dense episode with fewer usable sessions than this carries
#: no sign, so it neither confirms nor breaks the clause.
MIN_EPISODE_SESSIONS = 20
#: Bar clause 4 — ARM KG must keep the sign in at least this many of 3.
KG_MIN_SIGN = 2

#: Stage 2's stability clause, carried verbatim from `hedge_exposure`.
MIN_YEARS_POSITIVE = HE.MIN_YEARS_POSITIVE

#: The registration words exactly these four for Stage 1 and these five for
#: Stage 2. MEASUREMENT-ONLY is NOT a Stage 2 word here: ARM M is reported as a
#: measurement in every run and never as a verdict.
STAGE1_VERDICTS = ("PRECONDITION-FOUND", "PRECONDITION-NULL",
                   "GROSS-NOT-CONCENTRATION", "UNDERPOWERED")
STAGE2_VERDICTS = ("MECHANISM-FOUND", "NULL", "CONTRARY", "UNDERPOWERED",
                   "NOT EVALUABLE")

#: Every study-level verdict line carries this prefix, so the report has one
#: machine-checkable place a verdict word can be emitted from.
VERDICT_STAMP = "VERDICT"

#: Stamped on any ARM K row belonging to a read the study has power-stopped —
#: `hedge_exposure`'s errata F11 rule, applied to Stage 1. A signed number in a
#: table IS a direction in print.
UNPOWERED_NOTE = "UNDERPOWERED — no direction is quoted from this row"

#: Metric keys, borrowed so Stage 2 speaks `hedge_exposure`'s vocabulary.
CO_PRIMARIES = HE.CO_PRIMARIES
STRATUM_POOLED = HE.STRATUM_POOLED
STRATA = HE.STRATA

#: The taus `hedge_exposure` ran, printed in this study's census FOR
#: CONTINUITY ONLY. They are not cells here and no arm reads them.
COMPARISON_TAUS = (0.30, 0.35, 0.40, 0.50)


# ════════════════════════════════════════════════════════════════════════════
# printing helpers — hedge_exposure's, imported so two reports cannot drift
# ════════════════════════════════════════════════════════════════════════════

hdr = HE.hdr
sub = HE.sub
print_stats_row = HE.print_stats_row
curve_of = HE.curve_of
improvement = HE.improvement
hedged_daily = HE.hedged_daily
merge = HE.merge
cache_state = HE.cache_state


def _num(v, spec: str = "+.4f") -> str:
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

    `hedge_exposure`'s operator ratification (2026-08-31) fixes
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


def new_diag() -> dict:
    """`hedge_exposure`'s planning diagnostic plus this study's admission ones."""
    d = HE.new_diag()
    d.update(admission_refused=0, no_entry_delta=0)
    return d


def plan_episode_admitted(window, proxies, f: float, budget: float, rule: str,
                          diag: dict, overlay: Overlay) -> HE.Leg:
    """`hedge_exposure.plan_episode`, with every leg run past the overlay ledger.

    Identical in every other respect — the per-session re-pick, the rotation at
    a cluster change, the roll at expiry, the SKIP of a sub-one-contract size —
    so the only difference between this study's ARM C and `hedge_exposure`'s is
    the admission the registration adds.

    A put with no cached entry greek cannot be admitted: its delta notional is
    UNKNOWN, and admitting it at a fabricated 0.0 would consume no net-delta
    headroom for a position that in fact carries some. It is counted and the
    session is carried at f=0.
    """
    leg = HE.Leg(episode=tuple(window))
    held: list[str] = []
    diag["sessions_unhedgeable"] += sum(1 for p in proxies if p is None)
    runs = HE.proxy_runs(window, proxies)
    for r, (proxy, days, n_active) in enumerate(runs):
        if r:
            diag["rotations"] += 1
        cur_pick: HI.PutPick | None = None
        cur_c = 0
        cur_days: list[_date] = []
        for k, day in enumerate(days):
            if cur_pick is not None and day > cur_pick.expiry:
                leg.segments.append(HE.Segment(cur_pick, cur_c,
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
                c = HE._contracts_for(pick.entry_mark * HI.SHARES_PER_CONTRACT,
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
            leg.segments.append(HE.Segment(cur_pick, cur_c, tuple(cur_days),
                                           False))
    leg.proxies = tuple(held)
    if leg.segments:
        leg.label = leg.segments[0].pick.label()
    return leg


def episode_leg_admitted(episode, by_session, universe, f, budget, rule, diag,
                         overlay) -> HE.Leg:
    window, proxies = HE.episode_plan(episode, by_session, universe)
    if not any(p is not None and p != HE.CARRY for p in proxies):
        diag["episodes_all_unhedgeable"] += 1
    return plan_episode_admitted(window, proxies, f, budget, rule, diag, overlay)


def build_cell(tau: float, f: float, rule: str, triggered, eps, by_session,
               budget: float, universe, overlay_factory,
               stratum: str = STRATUM_POOLED, arm: str = "C") -> HE.Cell:
    """One arm x tau x f x stratum cell, planned through a FRESH overlay ledger.

    Fresh per cell, because the ledger state a leg is admitted against must be
    the one THIS cell's own earlier legs produced — a shared ledger would let
    one cell's hedges refuse another's. No episode is dropped; a session inside
    one that carries no hedgeable cluster, no fill, no sizeable contract or no
    admission headroom is carried at f=0 and counted on the diagnostic.
    """
    diag = new_diag()
    overlay = overlay_factory()
    cell = HE.Cell(arm=arm, tau=tau, f=f, rule=rule, stratum=stratum,
                   n_sessions=len(triggered), n_episodes=len(eps),
                   n_book_dates=0, powered=len(eps) >= MIN_TRIGGER_DATES,
                   diag=diag, triggered=list(triggered), eps=list(eps))
    for ep in eps:
        leg = episode_leg_admitted(ep, by_session, universe, f, budget, rule,
                                   diag, overlay)
        cell.ep_hedges.append(HE.price_put(leg))
        if leg.segments:
            cell.legs.append(leg)
    cell.hedge = merge(cell.ep_hedges)
    diag["admission_refused_by_reason"] = dict(overlay.refused)
    diag["admitted_legs"] = overlay.admitted
    return cell


def arm_n_band(eps, by_session, universe, axis, base_daily, capital, f, budget,
               rule, metrics, overlay_factory, n_seeds=N_SEEDS, seed=SEED
               ) -> dict:
    """ARM N — matched random hedging, admitted through the SAME ledger.

    `hedge_exposure.arm_n_band`'s matching, re-planned through this study's
    overlay: episode COUNT, episode LENGTHS and the PER-SESSION PROXY SEQUENCE
    at uniform random starts. A null planned WITHOUT the admission the arm is
    subject to would stop being a null for that arm, so each seed gets its own
    fresh ledger exactly as each cell does.

    Returns `{metric: (p05, p95)}`. Both tails: the 95th is clause 3's bar for
    a positive and the 5th is the mirrored clause for a CONTRARY.
    """
    shapes = [HE.episode_shape(ep, by_session) for ep in eps]
    shapes = [s for s in shapes if any(p is not None for p in s)]
    uni = list(universe)
    draws: dict[str, list[float]] = {m: [] for m in metrics}
    if not shapes or len(uni) < 2:
        return {m: (float("nan"), float("nan")) for m in metrics}
    rng = random.Random(seed)
    base = M.path_stats(curve_of(axis, base_daily), capital)
    for _ in range(n_seeds):
        legs = []
        diag = new_diag()
        overlay = overlay_factory()
        for shape in shapes:
            length = len(shape)
            if length > len(uni):
                continue
            start = rng.randrange(0, len(uni) - length + 1)
            window = HE.hold_window(uni[start:start + length], uni)
            proxies = list(shape) + [HE.CARRY] * (len(window) - length)
            legs.append(plan_episode_admitted(window, proxies, f, budget, rule,
                                              diag, overlay))
        hd = hedged_daily(axis, base_daily,
                          merge(HE.price_put(leg) for leg in legs))
        hedged = M.path_stats(curve_of(axis, hd), capital)
        for m in metrics:
            draws[m].append(improvement(base, hedged, m))
    return {m: (HE.pctile(v, 0.05), HE.pctile(v, 0.95)) for m, v in draws.items()}


def leave_one_date_out(cell: HE.Cell, by_session, universe, axis, base_daily,
                       capital, base, metrics, f, budget, rule,
                       overlay_factory) -> dict:
    """Clause 6, folded over TRIGGER DATES — `hedge_exposure`'s errata F10 rule.

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
        diag = new_diag()
        overlay = overlay_factory()
        if i is not None:
            ep = cell.eps[i]
            for piece in (tuple(s for s in ep if s < d),
                          tuple(s for s in ep if s > d)):
                if piece:
                    parts.append(HE.price_put(episode_leg_admitted(
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

def print_not_preregistered(args, capital: float, budget: float) -> None:
    """The ONE place every discretionary choice in this module is listed.

    `hedge_exposure`'s errata F14 discipline: every choice this module made
    that the registration does NOT commit is listed here, with what it is and
    which clause it feeds. A choice that feeds a clause and is not on this list
    is a defect. None of these may be read as findings, and none is tuned —
    they are fixed in code, stated here, and not revisited after an outcome.
    """
    hdr("NOT PRE-REGISTERED — every discretionary choice in this module, in "
        "one place")
    print(f"""  The registration
  (research/pre-registrations/f4_deployment/hedge_concentration.md) fixes the
  population and the admission model, H = 20, the tercile rule, the tau grid
  {TAU_GRID}, the f grid {F_GRID}, the fill rules and DTE windows, the
  >=60% fill gate, the >=25 trigger-date floor, G-POWER-K's 60/3, the
  Bonferroni denominator of {N_CELLS}, both clause sets and both verdict
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
     hedge_exposure's two-STORED-columns check, and this report never calls it
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
 17  EVERYTHING hedge_exposure ALREADY DISCLOSED AND THIS MODULE INHERITS by
     importing its planner: rolling at expiry (settled at expiry intrinsic
     against that day's close, walked back up to {HE.SETTLE_LOOKBACK_DAYS} calendar days), the
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
     continuity with hedge_exposure. They are NOT cells here, no arm reads
     them, and the registration's grid may not be moved after commit.
 19  THE HEDGE-FLOW PROSE is parsed and censused only. No arm in this study
     reads it — see the registration's "What this is NOT".
 20  SEEDS: block bootstrap and ARM KN and ARM N all take seed {SEED}, printed
     wherever a band is. {args.boot} Stage 2 resamples per cell.""")


def print_census(series, universe, adm_dates, positions, sess_series,
                 capital: float, st, dense_eps, spans) -> None:
    """G-CENSUS — the trigger and tercile census, from entry-dated INPUTS.

    States the INPUT property, as `hedge_exposure`'s errata F13 fixed it: every
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
          f"strictest\n  of the readings, and the clustering hedge_exposure "
          f"fixed. THE REGISTERED GRID:")
    print(f"  {'tau':>6s}  {'any:sessions':>13s} {'any:episodes':>13s}  "
          f"{'con:sessions':>13s} {'con:episodes':>13s}  power(any)")
    for tau in TAU_GRID:
        _trigger_row(series, universe, tau)
    print("\n  FOR COMPARISON ONLY, NOT A CELL — hedge_exposure's own taus on "
          "this book:")
    for tau in COMPARISON_TAUS:
        _trigger_row(series, universe, tau)
    for tau in TAU_GRID:
        eps = C.episodes(C.triggered_sessions(series, tau), universe)
        if eps:
            print(f"    tau {tau:.2f} any-cluster episode lengths: "
                  f"{sorted((len(e) for e in eps), reverse=True)}")

    sub("gross versus concentration — is ARM KG a real control?")
    print(f"  Spearman( per-session gross , any-cluster concentration ) = "
          f"{_num(F.spearman(gross, anyv))}   n={n}")
    print(f"  Spearman( n_open           , any-cluster concentration ) = "
          f"{_num(F.spearman([float(sc.n_open) for sc in series], anyv))}")
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
    tau_lo = TAU_GRID[0]
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
    print(f"    SPEARMAN rho            {_num(res['rho'])}"
          f"   CI95 [{_num(b_r.lo)}, {_num(b_r.hi)}]"
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

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rule", choices=HI.RULES, default=HI.RULE_BAND,
                    help="Stage 2 fill rule. `band` is the pre-registered "
                         "primary; `nearest` is the registered sensitivity.")
    ap.add_argument("--seeds", type=int, default=N_SEEDS,
                    help=f"ARM N seeds (registered: {N_SEEDS})")
    ap.add_argument("--boot", type=int, default=2000,
                    help="Stage 2 block-bootstrap resamples per cell "
                         "(Stage 1 always uses the registered "
                         f"{BOOT_N})")
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
  (research/pre-registrations/f4_deployment/hedge_exposure.md §Population and
  basis — RATIFICATION, operator 2026-08-31).
  `account_sim`'s own default loader makes byte-for-byte the same call, so the
  candidate set here IS the population hedge_exposure ratified:
    rows {len(recs)}   signal dates {len(dates)}   {dates[0] if dates else 'n/a'} .. {dates[-1] if dates else 'n/a'}
    pricing sources: """ + "  ".join(f"{k} {v}" for k, v in sorted(by_source.items())) + f"""

  ARM H IS OFF (bear_by_day=None AND cfg.hedge=False), there is no --live-select
  ranker and no compounding. THE BOOK IS THE ADMITTED SUBSET: what
  account_sim.simulate() takes from that candidate set under the operator's
  top-{st.max_per_day}-per-day rule and the cash / per-position / net delta caps. Hedges
  (Stage 2 only) go through `account_sim.admission()` and never displace a pick.

  This is a DIFFERENT BOOK from hedge_exposure's, which held every ratified row
  concurrently; no figure here restates one of that study's, and neither
  study's verdict overrides the other's.

  NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF. No annualised
  figure, Sharpe or time-to-recover appears anywhere in this report.""")

    # ── the sector map, quoted as the registration requires ─────────────────
    hdr("SECTOR MAP — fixed in hedge_exposure's registration before any "
        "concentration was computed")
    for line in S.census_lines():
        print(line)
    print(f"\n  run-time confirmation: proxies on underlying.rescaled_tickers() "
          f"today = {sorted(S.rescale_withheld_proxies()) or 'none'}")
    print("  (diagnostic only — UNHEDGEABLE is a committed constant and is "
          "never recomputed from it)")

    print_not_preregistered(args, capital, budget)

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
  hedge_exposure's check. It compares TWO SEPARATE COMPUTATIONS — daily_pnl_csv
  at the REPLAY's exit index, times the REPLAY's contracts, against the dollars
  the FROZEN harness booked for that same replay — which is the only target the
  registration's own words ("reconciles ... at every ADMITTED POSITION's exit")
  can mean on a book the simulator re-sized and re-exited. It is NOT
  hedge_exposure's two-STORED-columns check (daily_pnl_csv vs
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
    print("""  Every hedge verdict on record (bear_deploy D3, calendar_hedge H3,
  hedge_timing H4) rests on account_sim's close-bucketed curve, whose own
  print_equity says "Open positions are not marked to market, so this
  understates intra-position drawdown." A hedge's function is to cushion
  exactly the path that curve omits. ARM M measures the gap ON THE BOOK
  account_sim ACTUALLY HOLDS, so unlike hedge_exposure's ARM M it is a
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
    taus_checked = tuple(sorted(set(TAU_GRID) | set(COMPARISON_TAUS)))
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

    k = run_arm_k(al, H, H, BOOT_N, SEED)
    n_dense = len(dense_eps)
    powered = (min(k["counts"]) >= MIN_TERCILE_SESSIONS
               and n_dense >= MIN_DENSE_EPISODES)
    stamp = "" if powered else UNPOWERED_NOTE

    print_arm_k("ARM K", k, stamp)
    k10 = run_arm_k(align(axis, levels, series, sess_series, capital, H_SENS),
                    H_SENS, H_SENS, BOOT_N, SEED)
    print_arm_k("ARM K10 (SENSITIVITY — carries no verdict, cannot rescue or "
                "overturn ARM K)", k10, stamp)

    sub("ARM KN — the time-structure null (circular shift, "
        f"{KN_DRAWS} draws, seed {SEED})")
    kn = run_arm_kn(al, H, KN_DRAWS, SEED)
    for name, lab in (("contrast", "contrast"), ("rho", "Spearman rho")):
        sn = kn.get(name)
        if sn is None:
            print(f"  {lab:<14s} not computable: {kn.get(name + '_error')}")
            continue
        beats = sn.beats_low()
        print(f"  {lab:<14s} point {_num(sn.point)}   null p05 {_num(sn.p05)}"
              f"   p95 {_num(sn.p95)}   min shift {sn.min_shift} rows"
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
          f"{_pass(res['c2'])}   rho {_num(k['rho'])}  "
          f"CI95 [{_num(b_r.lo)}, {_num(b_r.hi)}]")
    print(f"  3 contrast beyond ARM KN's 5th percentile           "
          f"{_pass(res['c3'])}   point {_num(kn_c.point) if kn_c else 'n/a'}  "
          f"p05 {_num(kn_c.p05) if kn_c else 'n/a'}")
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

  Grid: tau {TAU_GRID} x f {F_GRID} = {N_CELLS} cells,
  Bonferroni alpha = 0.05/{N_CELLS} = {ALPHA:.5f}.""")

    def _census_only() -> None:
        sub("Stage 2 trigger census, FOR THE RECORD (no cell is evaluated)")
        print(f"  {'tau':>6s}  {'sessions':>9s} {'episodes':>9s}  power "
              f"(floor {MIN_TRIGGER_DATES} episodes)")
        for tau in TAU_GRID:
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
    It does NOT overturn hedge_exposure. That study's UNDERPOWERED describes
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

    Everything here is `hedge_exposure`'s machinery over this study's objects —
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
  calendar_hedge's standing principle that a hedge unavailable exactly when
  needed is not a hedge. DISCLOSED: this denominator is CACHE-CONDITIONED — the
  instrument universe is the option history cache, i.e. contracts the BOOK
  traded, so these rates measure CACHE COVERAGE, not market liquidity.""")
    fill = {}
    for tau in TAU_GRID:
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
    hdr(f"ARM C — concentration-gated proxy put   ({len(TAU_GRID)} tau x "
        f"{len(F_GRID)} f = {N_CELLS} cells)")
    cells: dict[tuple, HE.Cell] = {}
    arm_r: dict[tuple, dict] = {}
    for tau in TAU_GRID:
        trig = C.triggered_sessions(series, tau)
        eps = C.episodes(trig, universe)
        counts = C.trigger_date_counts(trig, series, recs_adm)
        for f in F_GRID:
            cell = build_cell(tau, f, args.rule, trig, eps, by_session, budget,
                              universe, overlay_factory)
            cell.n_book_dates = counts["book_dates"]
            cells[(tau, f)] = cell
            rdiag = dict(no_entry_delta=0)
            arm_r[(tau, f)] = dict(
                hedge=merge(HE.price_delta_short(leg, rdiag)
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
                        note=HE.power_note(cell.powered))

    sub("ARM R — always-fillable reference (delta-matched short in the proxy)")
    print(f"  {HE.ARM_R_CAVEAT}\n")
    for (tau, f) in cells:
        h = arm_r[(tau, f)]["hedge"]
        if h:
            stt = M.path_stats(curve_of(axis, hedged_daily(axis, base_daily, h)),
                               capital)
            print_stats_row(f"ARM R tau {tau:.2f} f {f:.2f} (delta-matched)",
                            stt, mtm_stats,
                            note=HE.power_note(cells[(tau, f)].powered))

    # ── the bar ─────────────────────────────────────────────────────────────
    hdr("BAR FOR A CANDIDATE — all seven clauses, per powered cell, per stratum")
    words: Counter = Counter()

    def stratum_cell(strat: str, tau: float, f: float) -> HE.Cell:
        if strat == STRATUM_POOLED:
            return cells[(tau, f)]
        trig = C.triggered_sessions(series, tau, stratum=strat)
        eps = C.episodes(trig, universe)
        c = build_cell(tau, f, args.rule, trig, eps, by_session, budget,
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
                band = arm_n_band(scell.eps, by_session, universe, axis,
                                  base_daily, capital, f, budget, args.rule,
                                  CO_PRIMARIES, overlay_factory,
                                  n_seeds=args.seeds, seed=SEED)
                rdiag = dict(no_entry_delta=0)
                rh = (arm_r[(tau, f)]["hedge"] if strat == STRATUM_POOLED
                      else merge(HE.price_delta_short(leg, rdiag)
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
                    mtm_stats, CO_PRIMARIES, f, budget, args.rule,
                    overlay_factory)
                # `arm_n_registered=band` is the SAME band on purpose. In
                # hedge_exposure the rich match was NOT what its registration
                # committed, so the two had to be printed side by side; THIS
                # registration commits exactly this match — "episode COUNT,
                # episode LENGTHS and PROXY mix" — so there is no second
                # estimator to disagree with and the diagnostic row restates
                # the committed one.
                res = HE.evaluate_bar(scell, axis, base_daily, capital, band,
                                      rimp, args.boot, folds,
                                      arm_n_registered=band)
                scell.clauses = res
                scell.verdict = HE.cell_verdict(res)
                HE.print_clauses(res, scell, args)
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


if __name__ == "__main__":
    sys.exit(main())
