"""Walk-forward exit hypotheses judged on ACCOUNT-LEVEL mark-to-market drawdown.

PRE-REGISTERED 2026-09-05 in `research/pre-registrations/f2_management/exit_drawdown.md`,
BEFORE this file was written. That document is BINDING; nothing here may drift
from it. Read it first. In brief:

  THE QUESTION. Does any exit rule — chosen WITHOUT look-ahead — reduce the
  account-level MTM drawdown of the deployed book without giving back its edge?
  The operator's queued question is "MAX DRAWDOWN, not timing". `account_sim`
  deploys the ladder through a $25,000 ledger; `lib/mtm_curve.py` marks that
  same book to market. No study has judged an exit rule on that curve, and no
  exit knob in this repo has ever been chosen out of sample.

  WHY THIS IS ADMISSIBLE after a page of standing exit nulls: every one of them
  was reached on a PER-ROW R estimand under IN-SAMPLE parameter choice. The
  headline here is a path-dependent, account-level, MARKED dollar drawdown, and
  every threshold is fitted on TRAIN dates and applied to TEST dates. Neither
  difference exempts any arm from the continuation diagnostic — a rule that cuts
  drawdown by SELLING CONTINUATIONS has re-found the reactive null in new
  clothes, and CONT is registered as a PASS CRITERION (`REACTIVE-AGAIN`), not a
  footnote.

  FIVE ARMS, frozen.
    ARM W  walk-forward knob control — the pt x sl x tef grid (36 points, PROD
           is one of them) selected per block. The honesty baseline.
    ARM U  underlying ATR stop for DEBIT verticals, ATR14 FROZEN at entry,
           k in {1.5, 2.0, 3.0}, added to sl .75 (a) or replacing it (b).
    ARM O  flow-unwind off the entry LONG leg's own `Open Int` path, read
           LAGGED one session, X in {0.25, 0.40}; plus ONE volume variant.
    ARM P  partial scale-out — half the contracts at the shipped pt, half at
           pt=None, as TWO synthetic positions. Exact, nothing to select.
    ARM D  SECONDARY drawdown THROTTLE (sizing, not exit). Can never ship.

  NO LOOKAHEAD, mechanically. Thresholds come from
  `protocol.walk_forward_splits(dates, block=15, embargo_days=120,
  min_train_dates=40)` on TRAIN dates only, two-stage (cheap per-row mean-R
  prefilter within 0.02 of best, then the smallest TRAIN MTM max drawdown among
  the survivors). A `date -> block` map dispatches each position's configuration
  inside ONE stitched OOS `simulate()`. BURN-IN dates — the dates that exist
  only to train the first fit — are EXCLUDED from the OOS headline and reported
  as their own census; they are never silently replayed under the shipped
  profile and folded in.

  COMPOSITION, NOT A FORK. Every overlay goes through
  `lib/exit_overlays.py`, which takes the EARLIER of `harness.replay`'s own exit
  and the rule's first-firing session. `lib/harness.py` is FROZEN and is not
  edited or copied here. G-FORK is the mechanical statement of that.

Gates, all printed: G-COV (coverage, BEFORE any conditional number) · G-FORK ·
G-CAL (the host simulation is unchanged) · G-MTM · G1 (leak guard) · G0 (power,
blocks every criterion). A machinery failure stops the run non-zero and NO
verdict is read for any arm.

Verdict grammar, TOTAL and applied in order, first match wins: UNDERPOWERED ->
CONTRARY -> REACTIVE-AGAIN -> CANDIDATE-FOR-INDEPENDENT-WINDOW -> NULL. ARM W
carries an extra arm-level token (`PROD-ROBUST`); ARM D takes four tokens, each
`SECONDARY-` prefixed, with REACTIVE-AGAIN never emitted (a sizing rule moves no
exit). Nothing ships from this run under any outcome.

    python -m scripts.backtest_study run exit_drawdown
    python -m scripts.backtest_study run exit_drawdown -- --era v3
    python -m scripts.backtest_study run exit_drawdown -- --arms W --population primary
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as M  # noqa: E402
from scripts.backtest_study.lib import exit_overlays as X  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import hdr, sub  # noqa: E402
# CONTINUATION_MARGIN and post_exit_max are IMPORTED, not restated: criterion 7
# is "the `staged_exit` G2 continuation diagnostic, reused here as a PASS
# CRITERION", and two copies of one diagnostic is how two studies come to
# disagree about what a continuation is.
from scripts.backtest_study.f2_management.staged_exit import (  # noqa: E402
    CONTINUATION_MARGIN, post_exit_max,
)
from scripts.backtest_study.f4_deployment import account_sim as A  # noqa: E402
from scripts.backtest_study.f4_deployment import hedge_exposure as HE  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# The runner promotes `-latest.txt` on these codes instead of deleting it. It
# finds them by AST parse, so this MUST stay a PLAIN SET LITERAL — a
# `frozenset(...)` call is invisible to `ast.literal_eval` and the refusal would
# be misfiled as a failure. {2, 3} are `era.EXIT_THIN_ERA` / `EXIT_ERA_MISMATCH`,
# raised by `load_book` when the exports on disk are not the era asked for.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

EXIT_GATE_FAILURE = 1        # a real failure, NOT a designed refusal


# ═══════════════════════════════════════════════════════════════════════════
# FROZEN grids and gate constants — every one of them fixed by the
# registration BEFORE any number was seen. Nothing here is swept.
# ═══════════════════════════════════════════════════════════════════════════

ARM_W_PT = (0.60, 0.75, 0.90, 1.10)
ARM_W_SL = (0.50, 0.75, None)
ARM_W_TEF = (0.60, 0.75, None)
#: The PROD grid point — `book.DEBIT_PROD`'s pt/sl/tef, and the ONLY point the
#: tie order's step (i) can tie back to. Live for ARM W, inert everywhere else.
PROD_POINT = (0.90, 0.75, 0.75)

ARM_U_K = (1.5, 2.0, 3.0)
ARM_O_X = (0.25, 0.40)
ARM_D_D = (0.05, 0.10)
#: ARM D's hysteresis: throttle at `d` below peak, restore within `d * this`.
#: The registration's "restore within d/2".
ARM_D_RESTORE_FRACTION = 0.5

#: ARM O excludes a row blank on this share or more of its hold sessions.
#: DECLARED ONCE, in `lib/exit_overlays.py`, and re-exported here: the threshold
#: has to bind where the series is READ (`exit_overlays.default_oi_for` returns
#: an empty series for an excluded row, which is what makes the exclusion real)
#: and a second literal here would let the census and the run disagree.
OI_BLANK_EXCLUSION = X.OI_BLANK_EXCLUSION

# Walk-forward selection (SELECTION — never interchanged with the stability
# cuts below, which are a different cut over the same dates).
WF_BLOCK = 15
WF_EMBARGO_DAYS = P.PATH_CAP_DAYS          # 120 — equal to the path cap
WF_MIN_TRAIN_DATES = 40
#: Stage-1 prefilter: keep configurations within this much of the TRAIN best
#: mean R, then choose among them on TRAIN MTM max drawdown.
TRAIN_R_TOLERANCE = 0.02

# G0 power floors, and criterion 6.
MIN_AFFECTED_DATES = 25
MIN_AFFECTED_ROWS = 60

# The conjunction's own constants.
DD_IMPROVE_MIN = 0.15        # clause 1 / (V2)'s mirror
DR_NONINFERIORITY = -0.02    # clause 2
CONT_MAJORITY = 0.50         # clause 7 — fails STRICTLY at or above this share

#: Block-bootstrap resamples for the drawdown-improvement CI, and its alpha.
#: The estimator is `hedge_exposure`'s chronological moving block — the
#: `improvement()` pattern the registration names. `alpha` is passed
#: EXPLICITLY at .05: `hedge_exposure`'s module constant is Bonferroni-
#: corrected for ITS nine registered cells and does not transfer.
BOOT_N = HE.BOOT_N
BOOT_ALPHA = 0.05
BOOT_SEED = HE.SEED

#: Arms, in report order. `--arms` takes a subset of these letters.
ALL_ARMS = "WUOPD"

POP_PRIMARY = "primary"
POP_ALL = "all"

# Verdict vocabulary — the whole of it.
V_UNDERPOWERED = "UNDERPOWERED"
V_CONTRARY = "CONTRARY"
V_REACTIVE = "REACTIVE-AGAIN"
V_CANDIDATE = "CANDIDATE-FOR-INDEPENDENT-WINDOW"
V_NULL = "NULL"
TOKENS = (V_UNDERPOWERED, V_CONTRARY, V_REACTIVE, V_CANDIDATE, V_NULL)
SECONDARY_PREFIX = "SECONDARY-"
#: ARM W's extra ARM-LEVEL token (it also emits a cell verdict under the ladder).
T_PROD_ROBUST = "PROD-ROBUST"

#: ARM P's exit reason on the ledger-facing blend. New, never a reuse of one of
#: `harness.replay`'s nine, so a reader can segregate it on the reason alone.
REASON_PARTIAL = "partial_scaleout"


# ═══════════════════════════════════════════════════════════════════════════
# Variants — one stitched OOS `simulate()` per (arm, variant)
# ═══════════════════════════════════════════════════════════════════════════
#
# A VARIANT is a family inside an arm within which the walk-forward fit
# selects. Its `grid` is the arm's OWN configurations and contains NO "off" /
# no-overlay point — deliberately, and registered as such: whether doing
# nothing would have been better is answered by the arm-versus-SHIPPED
# comparison every criterion is written against, not by letting the fit pick
# "no overlay". A one-element grid selects trivially and is still run through
# the same machinery, so the control (ARM W's PROD point) and the arms take
# exactly one code path.

KIND_OVERLAY = "overlay"     # an `exit_overlays.Overlay` per configuration
KIND_PARTIAL = "partial"     # ARM P — two synthetic positions, no threshold
KIND_SIZING = "sizing"       # ARM D — a `Cfg.dd_throttle`, changes no exit


class Variant:
    """One (arm, variant) cell: its grid, and how a configuration becomes a run."""

    def __init__(self, arm: str, key: str, label: str, kind: str, grid,
                 note: str = ""):
        self.arm = arm
        self.key = key
        self.label = label
        self.kind = kind
        self.grid = tuple(grid)
        self.note = note

    @property
    def name(self) -> str:
        return f"ARM {self.arm}/{self.key}"

    def spec(self, config) -> X.Overlay:
        """The `Overlay` a configuration replays under. Overlay variants only."""
        if self.arm == "W":
            pt, sl, tef = config
            return X.Overlay(profile=X.knob_profile(pt, sl, tef),
                             label=f"W pt={pt} sl={sl} tef={tef}")
        if self.arm == "U":
            return X.Overlay(atr_k=config, atr_replaces_sl=(self.key == "b"),
                             label=f"U k={config} {self.key}")
        if self.arm == "O":
            if self.key == "oi":
                return X.Overlay(oi_x=config, label=f"O X={config}")
            return X.Overlay(vol_climax=True, label="O vol-climax")
        raise ValueError(f"{self.name} has no overlay spec")

    def config_label(self, config) -> str:
        if self.arm == "W":
            pt, sl, tef = config
            return (f"pt {pt:.2f} / sl {'off' if sl is None else f'{sl:.2f}'}"
                    f" / tef {'off' if tef is None else f'{tef:.2f}'}")
        if self.arm == "U":
            return f"k {config:.1f}"
        if self.arm == "O":
            return "vol-climax 3x" if self.key == "vol" else f"X {config:.2f}"
        if self.arm == "D":
            return f"d {config:.2f}"
        return "half/half"

    def n_active_rules(self, config) -> int:
        """Tie order step (ii) — "fewer active rules"."""
        if self.arm == "W":
            return sum(1 for v in config if v is not None)
        return 1

    def largest_param(self, config) -> float:
        """Tie order step (iv) — "the LARGEST parameter value".

        `0.0` for a configuration with no parameter at all (ARM P, ARM O's
        volume variant): a one-point grid can never reach step (iv) anyway, and
        inventing a value there would be an unregistered knob.
        """
        if config is None:
            return 0.0
        if self.arm == "W":
            return max(v for v in config if v is not None)
        if isinstance(config, tuple):
            return max(float(v) for v in config if v is not None)
        return float(config)

    def is_prod(self, config) -> bool:
        """Tie order step (i). Live for ARM W ONLY, inert for every other arm —
        only ARM W's grid contains a PROD point to tie back to."""
        return self.arm == "W" and tuple(config) == PROD_POINT


def arm_w_grid() -> tuple:
    """The 36 pt x sl x tef points, PROD among them. FINAL; nothing is added."""
    return tuple((pt, sl, tef)
                 for pt in ARM_W_PT for sl in ARM_W_SL for tef in ARM_W_TEF)


def variants_for(arms: str) -> list[Variant]:
    out: list[Variant] = []
    if "W" in arms:
        out.append(Variant(
            "W", "wf", "walk-forward knob selection over the 36-point grid",
            KIND_OVERLAY, arm_w_grid(),
            note="the honesty baseline: how much of any arm's movement is "
                 "walk-forward SELECTION rather than the rule under test."))
        out.append(Variant(
            "W", "prod", "the PROD grid point itself (pt .90 / sl .75 / tef .75)",
            KIND_OVERLAY, (PROD_POINT,),
            note="a one-point grid, so the fit selects it every block. Reported "
                 "beside the WF cell exactly as the registration asks."))
    if "U" in arms:
        out.append(Variant("U", "a", "ATR stop ADDED to the shipped sl",
                           KIND_OVERLAY, ARM_U_K))
        out.append(Variant("U", "b", "ATR stop REPLACES sl",
                           KIND_OVERLAY, ARM_U_K))
    if "O" in arms:
        out.append(Variant("O", "oi", "flow-unwind on the lagged Open Int path",
                           KIND_OVERLAY, ARM_O_X))
        out.append(Variant("O", "vol", "the ONE volume-climax variant",
                           KIND_OVERLAY, (None,),
                           note="no threshold to select — 3x the EXPANDING "
                                "post-entry median and an adverse mark, both "
                                "fixed by the registration."))
    if "P" in arms:
        out.append(Variant("P", "half", "partial scale-out, two synthetic positions",
                           KIND_PARTIAL, (None,),
                           note="exact; there is nothing to select and no "
                                "threshold to fit."))
    if "D" in arms:
        out.append(Variant("D", "throttle", "SECONDARY drawdown throttle (SIZING)",
                           KIND_SIZING, ARM_D_D,
                           note="changes no row's exit. Its own SIZING "
                                "definition of 'affected' and no CONT clause."))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Walk-forward geometry
# ═══════════════════════════════════════════════════════════════════════════

class Split:
    """One walk-forward block: its TRAIN dates and its TEST dates."""

    def __init__(self, idx: int, train: list[str], test: list[str]):
        self.idx = idx
        self.train = list(train)
        self.test = list(test)


def build_splits(dates) -> list[Split]:
    """`protocol.walk_forward_splits` as an indexed list.

    Purged, expanding, `WF_EMBARGO_DAYS` between the last train date and the
    first test date — the embargo IS the path cap, so no training label can
    still be open when the block's test dates start. Blocks whose purged train
    set is thinner than `WF_MIN_TRAIN_DATES` are dropped by the splitter and
    their dates therefore belong to no TEST block: that is the BURN-IN, and it
    is excluded and counted, never silently replayed under the shipped profile.
    """
    return [Split(i, train, test) for i, (train, test) in enumerate(
        P.walk_forward_splits(dates, block=WF_BLOCK,
                              embargo_days=WF_EMBARGO_DAYS,
                              min_train_dates=WF_MIN_TRAIN_DATES))]


def block_index(splits: list[Split]) -> dict[str, int]:
    """`{test date -> block idx}`. A date in no test block is absent (burn-in)."""
    out: dict[str, int] = {}
    for s in splits:
        for d in s.test:
            out[str(d)] = s.idx
    return out


def burn_in_dates(dates, splits: list[Split]) -> list[str]:
    """Population dates belonging to NO test block, sorted."""
    tested = set(block_index(splits))
    return sorted(d for d in {str(x) for x in dates} if d not in tested)


def embargo_ok(splits: list[Split]) -> bool:
    """Every block's last TRAIN date precedes its first TEST date by >= the
    embargo. A property of `walk_forward_splits`, re-asserted here because the
    whole no-lookahead claim rests on it."""
    for s in splits:
        if not s.train or not s.test:
            continue
        gap = (_date.fromisoformat(str(s.test[0])[:10])
               - _date.fromisoformat(str(s.train[-1])[:10])).days
        if gap < WF_EMBARGO_DAYS:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Books — one stitched `simulate()` per (arm, variant)
# ═══════════════════════════════════════════════════════════════════════════

def day_lists_for(recs: list[dict], dates: set) -> list:
    """`protocol.ordered_by_day` restricted to `dates` — `account_sim`'s own
    construction, so the baseline this study pairs against IS its book."""
    pop = [r for r in recs if str(r["date"]) in dates]
    return P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible)


def partial_replayer(stop_hint: float):
    """ARM P's drop-in for `replay_sized` — the LEDGER-facing blend.

    The two halves are each a plain `replay_sized` call at their own contract
    count, so the FROZEN harness prices both and nothing here re-implements the
    scaling block. `ceil(n/2)` keeps the shipped profit target, `floor(n/2)`
    replays the same profile with `pt=None`; the registration fixes that split
    and it is not a build choice.

    What this function returns is the blend the LEDGER sees: `days_held` is the
    LATER of the two halves, so the reserve is held until the whole position is
    out. That is deliberately CONSERVATIVE against the registration's "the
    ledger releases half the reserve at the first exit" — `simulate()` takes one
    exit session per position and cannot release half a reserve — and it can
    only ever admit FEWER later positions than the registered release, never
    more. The CURVE does see two positions: `split_positions()` below re-splits
    every ARM P position before `book_curves` is called, which is where the
    "two synthetic Pos, each with its own exit session" requirement actually
    bites. This deviation is printed in ARM P's census, not buried here.

    A row that cannot be split — a CREDIT row (credit rows keep `CREDIT_PROD` in
    every arm) or one sized to n = 1 (one half would be zero contracts, which is
    not a position) — falls through to `replay_sized` unchanged and is EXCLUDED
    and counted in ARM P's census.
    """
    def replayer(rec: dict, contracts: int, stop: float,
                 profile: dict | None = None, cache: dict | None = None) -> dict:
        if rec.get("credit") or int(contracts) < 2:
            return A.replay_sized(rec, contracts, stop, profile=profile, cache=cache)
        prof = dict(profile) if profile else dict(A.profile_for(rec))
        top, bottom = partial_split(int(contracts))
        a = A.replay_sized(rec, top, stop, profile=prof, cache=cache)
        b = A.replay_sized(rec, bottom, stop, profile={**prof, "pt": None},
                           cache=cache)
        return dict(exit_reason=REASON_PARTIAL,
                    days_held=max(a["days_held"], b["days_held"]),
                    # Paired R = the MEAN of the two halves, per registration.
                    R=(a["R"] + b["R"]) / 2.0,
                    dollars=a["dollars"] + b["dollars"],
                    stop_exact=a["stop_exact"] and b["stop_exact"])
    replayer.stop_hint = stop_hint          # type: ignore[attr-defined]
    return replayer


def partial_split(n: int) -> tuple[int, int]:
    """`(ceil(n/2), floor(n/2))` — the registration's odd-count rule."""
    top = -(-int(n) // 2)
    return top, int(n) - top


def split_positions(sim: A.Sim, stop: float, cache: dict) -> list:
    """ARM P's book as TWO synthetic `Pos` per split position.

    `book_curves` needs valid per-position windows, and the whole point of a
    scale-out is that the two halves have DIFFERENT exit sessions. Every other
    position (credit, n = 1, and every other arm's) passes through untouched.
    """
    out = []
    for p in sim.taken:
        if p.exit_reason != REASON_PARTIAL:
            out.append(p)
            continue
        prof = A.profile_for(p.rec)
        top, bottom = partial_split(int(p.contracts))
        grid = p.rec["t"].grid
        for res, c in ((A.replay_sized(p.rec, top, stop, profile=prof, cache=cache), top),
                       (A.replay_sized(p.rec, bottom, stop,
                                       profile={**prof, "pt": None}, cache=cache), bottom)):
            share = c / float(p.contracts)
            out.append(A.Pos(
                rec=p.rec, contracts=c,
                reserved=p.reserved * share, dn=p.dn * share,
                entry_sess=p.entry_sess,
                exit_sess=grid[min(res["days_held"], len(grid)) - 1],
                days_held=res["days_held"], R=res["R"], dollars=res["dollars"],
                exit_reason=res["exit_reason"], downsized=p.downsized,
                hedge=p.hedge))
    return out


def collapse_choice(chosen: dict):
    """ARM D's ONE `d` for a whole simulation — the EARLIEST block's choice.

    `Cfg.dd_throttle` is a single value for a whole `simulate()`: a ledger
    cannot carry a different `d` per block, so a sizing arm's per-block
    selection has to collapse to one value before the stitched book can run.
    WHICH value it collapses to is a NO-LOOKAHEAD question, not a cosmetic one.

    The MODAL choice would be lookahead. The registration's binding rule is
    "thresholds are chosen per walk-forward block on TRAIN dates only ... then
    applied to that block's TEST dates"; a modal collapse replays block 0's
    TEST dates under a `d` selected using blocks 1..n's fits, whose train sets
    contain dates at or after those very test dates. The stitched book would
    then not be out of sample at all, and on the v4 primary population the
    choice is not academic — one grid value throttles sessions and moves the
    book while the other never fires, so the collapse decides the whole cell.

    The EARLIEST block's choice uses no information after its own train window,
    which is the same guarantee every exit arm's per-block dispatch gives, so
    the stitched book stays out of sample. There is no tie to break: block
    indices are unique and `min` is total over them. Every grid value's OWN
    stitched book is printed beside the headline as the disclosure of what the
    collapse cost.

    THE COLLAPSE LIVES HERE, in the one function that builds the book, and not
    in the caller: a caller that pre-filtered `chosen` to some other rule would
    silently get this one anyway, and the report's prose would describe a
    collapse the code did not perform.
    """
    return chosen[min(chosen)]


def run_book(variant: Variant, chosen: dict, day_lists, st: A.Settings,
             cache: dict, label: str, block_of) -> tuple[A.Sim, list]:
    """One stitched book for a variant, and its positions AS THE CURVE SEES THEM.

    `chosen` is `{block idx -> configuration}` from the walk-forward fit; a
    position's configuration is looked up by its SIGNAL DATE's block, so every
    position is replayed under knobs chosen without seeing its own date. There
    is deliberately NO default: `make_blockwise_replayer` raises on an unmapped
    date, which is how "burn-in is never silently shipped-profile" stays true
    rather than being a comment.

    A SIZING arm cannot dispatch per block — one `dd_throttle` per simulation —
    so its `chosen` is collapsed by `collapse_choice()`, which owns both the
    rule (the EARLIEST block's pick) and the reason it is that one and not the
    modal pick. `block_of` is unused on that path.
    """
    if variant.kind == KIND_SIZING:
        d = collapse_choice(chosen) if chosen else ARM_D_D[0]
        cfg = st.cfg(label, dd_throttle=(float(d), ARM_D_RESTORE_FRACTION))
        sim = A.simulate(day_lists, cfg, cache=cache)
        return sim, list(sim.taken)
    cfg = st.cfg(label)
    if variant.kind == KIND_PARTIAL:
        sim = A.simulate(day_lists, cfg, cache=cache,
                         replayer=partial_replayer(cfg.stop))
        return sim, split_positions(sim, cfg.stop, cache)
    spec_by_block = {b: variant.spec(c) for b, c in chosen.items()}
    sim = A.simulate(day_lists, cfg, cache=cache,
                     replayer=X.make_blockwise_replayer(block_of, spec_by_block))
    return sim, list(sim.taken)


def one_block(idx: int):
    """`block_of` for a run in which every date belongs to the same block."""
    def block_of(_d) -> object:
        return idx
    return block_of


def map_block(index: dict):
    """`block_of` for the stitched OOS book: the real date -> block map."""
    def block_of(d) -> object:
        return index.get(str(d))
    return block_of


# ═══════════════════════════════════════════════════════════════════════════
# Curves — the co-primary
# ═══════════════════════════════════════════════════════════════════════════

def curves_for(positions, capital: float) -> tuple[M.BookCurves, M.PathStats]:
    """`book_curves(target=TARGET_POSITION)` + `path_stats` for one book.

    `TARGET_POSITION` because this book was RE-SIZED and RE-EXITED by a replay:
    the row's stored `realized_pnl_abs` describes a different contract count and
    a different exit day by construction. The check is still between two
    separate computations — `daily_pnl_csv` at the replay's exit index times the
    replay's contracts, against the dollars the FROZEN harness booked — but it
    is NOT the two-stored-columns check and this report never calls it that.
    """
    bc = M.book_curves(positions, target=M.TARGET_POSITION)
    return bc, M.path_stats(bc.mtm, capital)


def aligned_daily(bc: M.BookCurves, axis: list) -> list[float]:
    """`bc`'s MTM LEVEL curve resampled onto `axis`, as per-session changes.

    Two books admitted on the same dates can still occupy different SESSIONS
    (a different exit moves the last open day), so every paired figure below is
    computed on the union axis with each book's level carried forward across
    sessions its own curve did not name. Carrying the level — not zeroing it —
    is the same convention `mtm_curve._carry_gaps` uses inside one book.
    """
    lv = dict(zip(bc.mtm.sessions, bc.mtm.levels))
    out, last, prev = [], 0.0, 0.0
    for s in axis:
        if s in lv:
            last = lv[s]
        out.append(last - prev)
        prev = last
    return out


def union_axis(a: M.BookCurves, b: M.BookCurves) -> list:
    return sorted(set(a.mtm.sessions) | set(b.mtm.sessions))


def dd_improvement(base: M.PathStats, arm: M.PathStats) -> tuple[float, float]:
    """`(dollars better, share of the base drawdown)` — positive is BETTER.

    Signed through `hedge_exposure.improvement`, the same function
    `hedge_exposure`'s own clause reads, so the two studies cannot drift on what
    "improved" means. The share is `NaN` when the baseline never drew down —
    there is no percentage of zero, and a zero-baseline cell fails clause 1 on
    the CI rather than on a fabricated ratio.
    """
    gain = HE.improvement(base, arm, HE.METRIC_MAXDD)
    denom = abs(base.max_dd)
    return gain, (gain / denom if denom > 1e-12 else float("nan"))


# ═══════════════════════════════════════════════════════════════════════════
# Clause 5 — the SECONDARY-era corroboration, read ACROSS the two runs
# ═══════════════════════════════════════════════════════════════════════════
#
# Clause 5 asks whether the SECONDARY era's cell is opposite-signed. The two
# eras are two SEPARATE PROCESSES — `run exit_drawdown` and `... --era v3` — so
# inside one of them the other cell's sign is not in memory. Hardcoding the
# clause to True made it unfailable: a genuinely powered, opposite-signed v3
# cell could not veto a PRIMARY candidate, and the conjunction was six clauses
# pretending to be seven.
#
# So each run RECORDS its own cells (name -> verdict, improvement ratio, power)
# in a small per-era sidecar and READS the sibling era's, if one is on disk.
# The sidecar is written by the run that produced it and is keyed by the
# DETECTED era, so a v3 file can never be read as v4's: the two never pool, here
# or anywhere else.
#
# When no sibling file exists the clause is VACUOUS — the registration's own
# treatment of a v3 cell with no sign ("a population that says nothing
# contradicts nothing"), printed as such, and any CANDIDATE resting on it
# carries that annotation into the write-up.

CELLS_DIR = ROOT / "backtests" / "study_output"

#: `{era -> the era whose cell clause 5 reads}`. v3 is the SECONDARY era and
#: carries no verdict of its own, so a v3 run has no referent at all.
SECONDARY_ERA = "v3"


def cells_artifact_path(era: str) -> Path:
    """Where a run records its own cells for the sibling era to read."""
    return CELLS_DIR / f"exit_drawdown-cells-{era}.json"


def write_cells_artifact(era: str, cells: dict) -> Path | None:
    """Record this run's cells. A failure here is REPORTED, never fatal — the
    artifact only feeds the OTHER era's clause 5, and losing it degrades that
    clause to VACUOUS (which is disclosed) rather than losing this report."""
    path = cells_artifact_path(era)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"era": era, "written": _date.today().isoformat(), "cells": cells},
            indent=2, sort_keys=True))
    except OSError as exc:
        print(f"\n  (could not record this run's cells for the sibling era's "
              f"clause 5: {exc})")
        return None
    return path


def read_sibling_cells(era: str) -> tuple[dict | None, str]:
    """`(cells, provenance)` for the SECONDARY era, or `(None, why not)`.

    Refuses anything whose recorded era is not the one asked for — the sidecar
    names its own era and a file that says otherwise is not read, so the two
    eras cannot be crossed by a stale filename.
    """
    if era == SECONDARY_ERA:
        return None, "this IS the secondary era"
    path = cells_artifact_path(SECONDARY_ERA)
    if not path.exists():
        return None, f"no {path.name} on disk (the v3 run has not been recorded)"
    try:
        blob = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return None, f"{path.name} unreadable ({exc})"
    if blob.get("era") != SECONDARY_ERA:
        return None, (f"{path.name} records era {blob.get('era')!r}, not "
                      f"{SECONDARY_ERA!r} — not read")
    return blob.get("cells") or {}, f"{path.name} written {blob.get('written')}"


def clause_five(cell: str, ratio: float, sibling: dict | None,
                why_not: str, is_v3: bool) -> tuple[bool, str]:
    """`(passed, the line the report prints)` for clause 5.

    The registration fixes the signless case: a v3 cell that is UNDERPOWERED on
    its own dates, or has no affected dates, has NO SIGN, is therefore not
    opposite-signed, and the clause PASSES VACUOUSLY — DISCLOSED, never silent.
    It FAILS only on a v3 cell that is powered, evaluated, and signed AGAINST
    the primary's improvement.
    """
    if is_v3:
        return True, ("this IS the v3 run — the clause has no referent here and "
                      "this report\n      carries no verdict of its own.")
    if sibling is None:
        return True, (f"VACUOUS ({why_not}). A CANDIDATE resting on it carries "
                      f"the annotation:\n      v3 did NOT corroborate, it was "
                      f"not asked.")
    rec = sibling.get(cell)
    if rec is None:
        return True, (f"VACUOUS (the v3 run recorded no {cell} cell; source "
                      f"{why_not}).")
    v3_ratio = rec.get("ratio")
    if not rec.get("powered") or v3_ratio is None or v3_ratio != v3_ratio:
        return True, (f"VACUOUS (v3 cell {rec.get('verdict', '?')} — no sign to "
                      f"contradict with; source {why_not}).")
    if _sign(v3_ratio) == 0 or _sign(ratio) == 0 or _sign(v3_ratio) == _sign(ratio):
        return True, (f"v3 cell {rec.get('verdict', '?')} improvement "
                      f"{v3_ratio:+.1%} — NOT opposite-signed (primary "
                      f"{ratio:+.1%});\n      source {why_not}.")
    return False, (f"v3 cell {rec.get('verdict', '?')} improvement "
                   f"{v3_ratio:+.1%} is OPPOSITE-SIGNED to the primary's "
                   f"{ratio:+.1%}\n      — the SECONDARY era CONTRADICTS this "
                   f"cell; source {why_not}.")


# ═══════════════════════════════════════════════════════════════════════════
# The verdict ladder — TOTAL, first match wins
# ═══════════════════════════════════════════════════════════════════════════

def verdict_token(*, powered: bool, dates_ok: bool, dd_contrary: bool,
                  r_contrary: bool, dd_ok: bool, r_ok: bool, stab_ok: bool,
                  cont_ok: bool, sizing: bool = False) -> str:
    """The registration's ladder, verbatim, as one total function.

    (V1) UNDERPOWERED — G0 fails for the cell on the evaluated set, equivalently
         clause 6, which RESTATES G0's date floor on that same population.
    (V2) CONTRARY      — powered, and signed against itself beyond noise.
    (V3) REACTIVE-AGAIN— powered, not contrary, CLEARS R and FAILS CONT.
         SKIPPED for a SIZING arm: it moves no exit, so "the arm's exits" has no
         referent and its continuation rate would be the baseline's by
         construction.
    (V4) CANDIDATE     — powered, not contrary, clears DD, R, STAB, DATES and
         (for an exit arm) CONT. Not a ship — a queue.
    (V5) NULL          — every remaining evaluated cell. The catch-all that
         makes the grammar total.

    Returned bare; `ARM D`'s `SECONDARY-` prefix is applied by the caller so the
    ladder itself has one shape.
    """
    if not powered or not dates_ok:
        return V_UNDERPOWERED
    if dd_contrary or r_contrary:
        return V_CONTRARY
    if not sizing and r_ok and not cont_ok:
        return V_REACTIVE
    if dd_ok and r_ok and stab_ok and dates_ok and (sizing or cont_ok):
        return V_CANDIDATE
    return V_NULL


def prod_robust_token(wf_cell_verdict: str) -> str:
    """ARM W's extra ARM-LEVEL token, also total.

    `PROD-ROBUST` is the AFFIRMATIVE reading of a null here: the WF cell was
    powered, it was evaluated, and no walk-forward-selected configuration beat
    PROD out of sample. An UNDERPOWERED cell does NOT claim it — too few dates
    to say whether PROD survived.
    """
    if wf_cell_verdict in (V_NULL, V_CONTRARY):
        return T_PROD_ROBUST
    return wf_cell_verdict


# ═══════════════════════════════════════════════════════════════════════════
# Coverage (G-COV) — printed BEFORE any conditional number
# ═══════════════════════════════════════════════════════════════════════════

def arm_u_census(recs: list[dict]) -> dict:
    """Bar coverage for ARM U, per the registration's three exclusions."""
    out = dict(n=0, no_bars=0, no_entry_anchor=0, close_only=0, no_atr=0,
               no_direction=0, usable=0, tickers=set(), tickers_no_bars=set())
    for rec in recs:
        if rec["credit"]:
            continue
        out["n"] += 1
        t = rec["t"]
        out["tickers"].add(t.ticker)
        bars = X.load_bars(t.ticker)
        cov = X.bar_coverage(t, bars)
        if not cov["has_bars"]:
            out["no_bars"] += 1
            out["tickers_no_bars"].add(t.ticker)
            continue
        if cov["entry_day"] is None:
            out["no_entry_anchor"] += 1
            continue
        if not cov["has_ohlc"]:
            out["close_only"] += 1
            continue
        if cov["atr14_pct"] is None:
            out["no_atr"] += 1
            continue
        if X.position_direction(t.structure) is None:
            out["no_direction"] += 1
            continue
        out["usable"] += 1
    return out


def arm_o_census(recs: list[dict]) -> dict:
    """OI coverage for ARM O, including the >= 20%-blank exclusion.

    THE DENOMINATOR IS THE SHIPPED HOLD WINDOW, not the whole weekday grid, and
    it is the same `exit_overlays.shipped_hold_sessions(rec)` the READ boundary
    uses — so what this census counts as excluded is exactly what the arm
    refuses to read. Measured on the whole grid instead (out to expiry or the
    120-day path cap), a row held six sessions and blank on all six reads as
    5% blank and is admitted; the registration's exclusion is written on HOLD
    sessions and the permissive reading is the one it exists to close.
    """
    out = dict(n=0, no_long_leg=0, no_series=0, too_blank=0, usable=0,
               blank_shares=[], hold_sessions=[])
    for rec in recs:
        if rec["credit"]:
            continue
        out["n"] += 1
        t = rec["t"]
        leg = X.entry_long_leg(t)
        if leg is None:
            out["no_long_leg"] += 1
            continue
        oi = X.load_oi(leg)
        if not oi:
            out["no_series"] += 1
            continue
        hold = X.shipped_hold_sessions(rec)
        share = X.oi_blank_share(t, oi, hold)
        if share is None:
            out["no_series"] += 1
            continue
        out["blank_shares"].append(share)
        out["hold_sessions"].append(hold)
        if share >= OI_BLANK_EXCLUSION:
            out["too_blank"] += 1
            continue
        out["usable"] += 1
    return out


def arm_p_census(sims: dict) -> dict:
    """ARM P's n = 1 and credit exclusions, counted off the book it ran on."""
    out = dict(n=0, credit=0, single_contract=0, split=0)
    for p in sims:
        out["n"] += 1
        if p.rec.get("credit"):
            out["credit"] += 1
        elif int(p.contracts) < 2:
            out["single_contract"] += 1
        else:
            out["split"] += 1
    return out


# ═══════════════════════════════════════════════════════════════════════════
# The walk-forward fit — two stages, TRAIN dates only
# ═══════════════════════════════════════════════════════════════════════════

def train_rows(recs: list[dict], train_dates: set, st: A.Settings) -> list[dict]:
    """The rows the ladder would actually DEPLOY on the train dates.

    `top_k_per_day` with the shipped rank and eligibility — the same selection
    `account_sim` replays. Fitting on the whole book instead would tune the
    knobs on rows the deployment never takes.
    """
    pop = [r for r in recs if str(r["date"]) in train_dates]
    return P.top_k_per_day(pop, P.ladder_rank, k=st.max_per_day,
                           eligible_fn=P.ladder_eligible)


def row_R(rec: dict, spec: X.Overlay, stop: float, cache: dict) -> float:
    """One row's R under `spec`, at one contract and the study's dollar stop.

    Memoised through the run's shared cache; the key carries the whole
    `Overlay`, so two configurations can never serve each other an answer (the
    2026-08-13 G5 bug class).
    """
    return X.replay_overlaid(rec, 1, stop, spec, cache=cache)["R"]


def shipped_triple(rec: dict, stop: float, cache: dict) -> tuple:
    """The SHIPPED per-row outcome triple at one contract — the pairing basis."""
    r = A.replay_sized(rec, 1, stop, cache=cache)
    return (r["exit_reason"], r["days_held"], round(r["R"], 10))


def fire_count(variant: Variant, config, rows: list[dict], stop: float,
               cache: dict) -> int:
    """Tie order step (iii): how many TRAIN rows the configuration MOVES.

    "The most conservative survivor, the one closest to leaving the shipped
    profile alone." Uniform across arms: a row fires if its outcome triple under
    the configuration differs from the shipped one.
    """
    if variant.kind != KIND_OVERLAY:
        return 0
    spec = variant.spec(config)
    n = 0
    for rec in rows:
        if rec["credit"]:
            continue          # credit rows are never overlaid, in any arm
        got = X.replay_overlaid(rec, 1, stop, spec, cache=cache)
        if (got["exit_reason"], got["days_held"], round(got["R"], 10)) != \
                shipped_triple(rec, stop, cache):
            n += 1
    return n


def fit_block(variant: Variant, split: Split, recs: list[dict], st: A.Settings,
              cache: dict) -> dict:
    """The two-stage fit for ONE block, on TRAIN dates only.

    Stage 1 — the cheap per-row prefilter: every configuration's TRAIN mean R
    via the memoised replay; keep those within `TRAIN_R_TOLERANCE` of the best.
    A SIZING arm changes no row's exit, so its per-row mean R is identical
    across configurations and stage 1 is INERT for it — every configuration
    survives to stage 2, which is stated rather than silently skipped.

    Stage 2 — among the survivors, run `simulate()` on the TRAIN `day_lists`
    only and pick the SMALLEST TRAIN MTM max drawdown.

    Ties break, in the registration's order: (i) to PROD (live for ARM W only),
    (ii) fewer active rules, (iii) fires on the fewest TRAIN rows, (iv) the
    LARGEST parameter value. Step (iii) is a FULL EXTRA PASS over the train
    rows, so it is computed LAZILY — only for the configurations still tied
    after (i) and (ii), which on most blocks is one configuration and no pass
    at all. The pick is identical either way; only the work is skipped.

    STAGE 1's MEAN IS OVER ALL TRAIN ROWS, CREDIT INCLUDED, and that is
    deliberate: the registration fixes the prefilter as "every grid config's
    TRAIN mean R", and computing it on debits alone would be a different
    statistic than the one registered. Credit rows are forced to `DISABLED` by
    `replay_overlaid`, so they contribute an IDENTICAL constant to every
    configuration's mean and cannot change the ORDER — but they do dilute the
    registered 0.02 tolerance relative to the debit-only signal the grid can
    move, by an amount that depends on the credit share of the train rows. So
    the credit share is RETURNED and printed beside the survivor count, which
    makes the effective tolerance visible rather than leaving it inferred.
    """
    tset = {str(d) for d in split.train}
    rows = train_rows(recs, tset, st)
    dls = day_lists_for(recs, tset)
    stop = st.budget

    means: dict = {}
    if variant.kind == KIND_OVERLAY:
        for config in variant.grid:
            spec = variant.spec(config)
            vals = [row_R(r, spec, stop, cache) for r in rows]
            means[config] = statistics.fmean(vals) if vals else float("nan")
        best = max((v for v in means.values() if v == v), default=None)
        survivors = [c for c in variant.grid
                     if means[c] == means[c] and best is not None
                     and means[c] >= best - TRAIN_R_TOLERANCE]
        if not survivors:
            survivors = list(variant.grid)
    else:
        survivors = list(variant.grid)

    scored = []
    for config in survivors:
        chosen = {split.idx: config}
        _sim, positions = run_book(variant, chosen, dls, st, cache,
                                   f"{variant.name} train b{split.idx}",
                                   one_block(split.idx))
        _bc, stats = curves_for(positions, st.capital)
        scored.append((config, stats.max_dd,
                       0 if variant.is_prod(config) else 1,
                       variant.n_active_rules(config),
                       -variant.largest_param(config)))
    # `-max_dd` first: max_dd is <= 0, so the smallest drawdown is the largest
    # value and `min()` over `-max_dd` picks it. Exact float comparison — a
    # rounded key would be an unregistered knob on the tie order.
    scored.sort(key=lambda s: (-s[1], s[2], s[3]))
    head = scored[0][1:4]
    tied = [row for row in scored if row[1:4] == head]
    if len(tied) > 1:
        # Step (iii) only where it can decide something. `fire_count` is a full
        # pass over the TRAIN rows per configuration; running it for every
        # survivor on every block bought nothing on the blocks that were never
        # tied, and it was the run's dominant cost.
        tied.sort(key=lambda row: (fire_count(variant, row[0], rows, stop, cache),
                                   row[4]))
    pick = tied[0][0]
    return dict(pick=pick, means=means, survivors=survivors, scored=scored,
                n_tied=len(tied), n_credit_train_rows=sum(1 for r in rows if r["credit"]),
                n_train_rows=len(rows), n_train_dates=len(tset))


# ═══════════════════════════════════════════════════════════════════════════
# Cell evaluation
# ═══════════════════════════════════════════════════════════════════════════

def by_rec(positions) -> dict:
    """`{id(rec): Pos}` — the SAME record objects appear in both books, so
    identity is the pairing key. A (date, ticker) key would silently merge a
    date's duplicate rows. The FIRST position per record; use `grouped_by_rec`
    where a record can carry more than one (ARM P's two halves)."""
    out = {}
    for p in positions:
        out.setdefault(id(p.rec), p)
    return out


def grouped_by_rec(positions) -> dict:
    """`{id(rec): [Pos, ...]}` — ARM P puts TWO positions on one record."""
    out: dict = {}
    for p in positions:
        out.setdefault(id(p.rec), []).append(p)
    return out


def _triples(group) -> list[tuple]:
    return sorted((p.exit_reason, p.days_held, round(p.R, 10)) for p in group)


def _outcome_set(group) -> set[tuple]:
    """The record's outcome triples AS A SET — the changed-test's comparison.

    A SET, not the sorted list, and the difference is a G0 power question.
    ARM P puts TWO `Pos` on one record; when the shipped exit was not a
    profit-target, the `pt` half and the `pt=None` half BOTH exit exactly where
    the shipped position did, so the arm changed nothing — yet `[X, X]` is not
    `[X]` and the row would be counted as `changed`. That inflates power in the
    PERMISSIVE direction, which is the direction `affected_set`'s own docstring
    forbids: on a wide enough population a pure duplication of an unchanged
    outcome could carry a cell over the 25-date / 60-row floor and hand a
    verdict to a cell the registration would have power-stopped.

    A GENUINE scale-out still differs under the set comparison, because its two
    halves exit on different sessions and therefore carry different triples;
    the case this collapses is exactly the one where they do not.
    """
    return set(_triples(group))


def affected_set(arm_positions, base_positions) -> dict:
    """Which records the arm CHANGED, and how — G0's "affected" for an exit arm.

    Three ways a row can be affected, all counted separately because they mean
    different things: the arm exited it differently, the arm took a row the
    shipped book did not, or the shipped book took one the arm did not (a
    knock-on of a different reserve-release schedule, not a rule firing).

    The comparison is over a record's WHOLE SET of outcome triples, not over
    one position. ARM P splits a record into two halves and the `pt` half often
    exits exactly where the shipped position did; keying on the first position
    would then read a scaled-out row as UNAFFECTED because half of it did not
    move, which is precisely the row the arm changed. It is a SET and not a
    sorted list for the mirror-image reason — see `_outcome_set`: a split that
    duplicates ONE unchanged outcome changed nothing and must not count.

    ONLY `changed` COUNTS TOWARDS POWER. G0's floors and clause 6 read `rows`
    and `dates`, and those are the CHANGED rows alone. `arm_only`/`base_only`
    are reserve-release KNOCK-ONS — a row one book took and the other did not
    because an earlier exit freed (or held) a reserve — and the registration's
    "affected" is "the arm CHANGED THAT ROW'S EXIT", not "a row the two books
    disagree about holding". Counting them towards the floor inflates power in
    the PERMISSIVE direction: a cell could clear 25 dates / 60 rows on rows the
    rule under test never fired on. They stay in the returned dict and are
    printed as the G0 table's own breakdown columns, disclosed and non-gating.
    """
    a, b = grouped_by_rec(arm_positions), grouped_by_rec(base_positions)
    changed, arm_only, base_only = [], [], []
    for k, ga in a.items():
        gb = b.get(k)
        if gb is None:
            arm_only.append(ga[0])
        elif _outcome_set(ga) != _outcome_set(gb):
            changed.append(ga[0])
    for k, gb in b.items():
        if k not in a:
            base_only.append(gb[0])
    knockon = arm_only + base_only
    return dict(changed=changed, arm_only=arm_only, base_only=base_only,
                rows=list(changed), n_rows=len(changed),
                dates=sorted({str(p.rec["date"]) for p in changed}),
                knockon_rows=knockon,
                knockon_dates=sorted({str(p.rec["date"]) for p in knockon}))


class ThrottleReconcileError(RuntimeError):
    """ARM D's re-derived throttle state disagrees with the ledger's record.

    A hard failure, never a warning: every ARM D count downstream is derived
    from that state, so a mismatch means the numbers below it describe two
    different simulations.
    """


def throttled_entries(sim: A.Sim, cfg: A.Cfg, day_lists) -> dict:
    """ARM D's SIZING definition of "affected", re-derived from its own book.

    An affected ROW is a position ENTERED while the throttle was ACTIVE; an
    affected DATE is a signal date on which at least one such row was entered.
    G0's general definition ("the arm changed that row's exit") is EMPTY for a
    sizing rule and would make every ARM D cell VACUOUSLY UNDERPOWERED, which is
    a defect of the general definition and not a finding about sizing — so the
    registration fixes this one, for ARM D and ARM D alone.

    The state is re-derived here rather than read off the book: the mark is
    `capital + realized` taken AFTER the session's `release_before`, which is
    exactly `sum(dollars of positions whose exit_sess < entry_sess)` over the
    book the arm actually produced. Same basis, same hysteresis, same order.

    AND IT IS RECONCILED AGAINST THE LEDGER'S OWN RECORD. `simulate()` appends
    the sessions on which the halved budget was in force to `Sim.throttle_dates`
    (added for exactly this), and the two sets must be equal. Two hand-written
    implementations of one state machine is the `s03_risk.py`/`s04b_page.py`
    pattern — DELIBERATE, because a second derivation is what makes drift
    visible — but that pattern only works if something COMPARES them. Without
    this check a divergence would silently move ARM D's affected-row and
    affected-date counts, and with them its UNDERPOWERED-vs-evaluated status.
    """
    dd, restore = cfg.dd_throttle
    peak = float(cfg.capital)
    on = False
    active_dates: set[str] = set()
    taken_by_day: dict[str, list] = {}
    for p in sim.taken:
        taken_by_day.setdefault(str(p.rec["date"]), []).append(p)
    for d, ranked in day_lists:
        entry_sess = ranked[0]["t"].grid[0]
        realized = sum(q.dollars for q in sim.taken if q.exit_sess < entry_sess)
        equity = cfg.capital + realized
        peak = max(peak, equity)
        if not on and equity <= peak * (1.0 - dd):
            on = True
        elif on and equity >= peak * (1.0 - dd * restore):
            on = False
        if on:
            active_dates.add(str(d))
    recorded = set(getattr(sim, "throttle_dates", ()) or ())
    if recorded != active_dates:
        missing = sorted(recorded - active_dates)
        extra = sorted(active_dates - recorded)
        raise ThrottleReconcileError(
            f"ARM D throttle state disagrees with the ledger's own record: "
            f"{len(recorded)} session(s) recorded by simulate(), "
            f"{len(active_dates)} re-derived here; "
            f"only in simulate(): {missing[:5]}; only re-derived: {extra[:5]}")
    rows = [p for d, ps in taken_by_day.items() if d in active_dates for p in ps]
    return dict(rows=rows, n_rows=len(rows), dates=sorted(active_dates))


def continuation(positions, base_by_rec: dict) -> dict:
    """Criterion 7 — the `staged_exit` G2 diagnostic, reused as a PASS criterion.

    Over the rows the arm exits EARLIER than shipped, the share whose post-exit
    path max exceeds the realized exit P&L by more than `CONTINUATION_MARGIN`. A
    cell that cuts drawdown by selling continuations has re-found the reactive
    null in new clothes and does not pass, whatever its DeltaR says.

    The STRICT share (any recovery past the exit at all, margin 0) is computed
    and printed beside it as a DISCLOSED figure. The gate is the margin-0.30
    one, because that is the diagnostic being reused.
    """
    early = []
    for p in positions:
        pb = base_by_rec.get(id(p.rec))
        if pb is not None and p.days_held < pb.days_held:
            early.append(p)
    n_cont = n_strict = 0
    for p in early:
        pm = post_exit_max(p.rec["t"], p.days_held)
        if pm is None:
            continue
        if pm > p.R + CONTINUATION_MARGIN:
            n_cont += 1
        if pm > p.R:
            n_strict += 1
    n = len(early)
    share = (n_cont / n) if n else None
    return dict(n_early=n, n_continuation=n_cont, n_strict=n_strict,
                share=share, strict_share=(n_strict / n) if n else None,
                # No early exits cannot be a continuation sale, and is not a
                # pass by merit either — such a cell is UNDERPOWERED long
                # before this is read.
                passed=(True if share is None else share < CONT_MAJORITY))


def paired_rows(arm_positions, base_positions) -> list[dict]:
    """Paired per-row R on the records BOTH books took — clause 2's input.

    A record's R is the MEAN over its positions, which is a no-op everywhere
    except ARM P, where the registration fixes exactly that: "Paired R = the
    mean of the two halves". R, not dollars — the contract counts differ from
    the shipped row's.

    Records only ONE book took are dropped from the pairing (there is nothing
    to pair them with) and counted separately in `affected_set`, so the
    selection difference is reported rather than absorbed into a mean.
    """
    a, b = grouped_by_rec(arm_positions), grouped_by_rec(base_positions)
    out = []
    for k, ga in a.items():
        gb = b.get(k)
        if gb is None:
            continue
        rec = ga[0].rec
        out.append(dict(date=str(rec["date"]),
                        a=statistics.fmean(p.R for p in ga),
                        b=statistics.fmean(p.R for p in gb),
                        source=rec.get("source")))
    return out


def _sign(x: float) -> int:
    if x != x:
        return 0
    return 1 if x > 0 else (-1 if x < 0 else 0)


def stability(base_bc: M.BookCurves, arm_bc: M.BookCurves, capital: float,
              affected_dates: list[str], eval_dates: list[str],
              base_positions, arm_positions, affected_rows) -> dict:
    """Clauses 3, 4 and 5's inputs, on the EVALUATED population.

    Halves are split CHRONOLOGICALLY at the median evaluated date; a half in
    which the improvement has NO SIGN — no affected dates fall in it, so there
    is nothing to compute — cannot be same-signed and the clause CANNOT be
    cleared. A signless half is never read as agreeing by default and is never
    dropped to let the surviving half decide.

    Each half's and each year's affected-date and affected-row counts are
    returned so the report can PRINT them as a DISCLOSED, NON-GATING
    observation. No thinness floor is applied — this registration commits none,
    and one chosen at run time could flip a cell straight to NULL.

    `affected_rows` IS THE `changed` SET, not the arm's whole book, and that is
    what makes the printed row count the registered disclosure. The clause
    exists so "a reader can see when a cleared sign rests on a THIN HALF";
    counting every position whose signal date falls in the half would print the
    book's size there, which is thin in no half of interest and cannot show the
    thing the disclosure is for.
    """
    axis = union_axis(base_bc, arm_bc)
    b_daily = aligned_daily(base_bc, axis)
    a_daily = aligned_daily(arm_bc, axis)

    def imp(keep) -> float:
        if keep is not None and not keep:
            return float("nan")
        base = HE.stats_on(axis, b_daily, capital, keep=keep)
        arm = HE.stats_on(axis, a_daily, capital, keep=keep)
        return HE.improvement(base, arm, HE.METRIC_MAXDD)

    overall = imp(None)
    aff = sorted(affected_dates)
    ev = sorted(eval_dates)
    median = ev[(len(ev) - 1) // 2] if ev else None

    halves = {}
    if median is not None:
        for name, pick in (("first half", lambda d: str(d)[:10] <= median),
                           ("second half", lambda d: str(d)[:10] > median)):
            keep = {s for s in axis if pick(s)}
            n_aff = sum(1 for d in aff if pick(d))
            halves[name] = dict(imp=imp(keep) if n_aff else float("nan"),
                                n_dates=n_aff,
                                n_rows=sum(1 for p in affected_rows
                                           if pick(str(p.rec["date"]))))

    years = {}
    for y in sorted({str(d)[:4] for d in ev}):
        keep = {s for s in axis if str(s)[:4] == y}
        n_aff = sum(1 for d in aff if str(d)[:4] == y)
        years[y] = dict(imp=imp(keep) if n_aff else float("nan"),
                        n_dates=sum(1 for d in ev if str(d)[:4] == y),
                        n_aff_dates=n_aff)

    tiers = {}
    for tier in ("real", "tweak"):
        bp = [p for p in base_positions if p.rec.get("source") == tier]
        ap = [p for p in arm_positions if p.rec.get("source") == tier]
        if not bp or not ap:
            tiers[tier] = dict(imp=float("nan"), n=len(ap))
            continue
        bbc, _ = curves_for(bp, capital)
        abc, _ = curves_for(ap, capital)
        ax = union_axis(bbc, abc)
        tiers[tier] = dict(
            imp=HE.improvement(
                M.path_stats(HE.curve_of(ax, aligned_daily(bbc, ax)), capital),
                M.path_stats(HE.curve_of(ax, aligned_daily(abc, ax)), capital),
                HE.METRIC_MAXDD),
            n=len(ap))

    want = _sign(overall)
    halves_ok = bool(halves) and all(
        _sign(h["imp"]) == want and want != 0 for h in halves.values())
    y_present = len(years)
    y_agree = sum(1 for v in years.values() if _sign(v["imp"]) == want and want != 0)
    y_required = y_present if y_present < 3 else 2
    years_ok = y_present > 0 and y_agree >= y_required
    tiers_ok = all(_sign(v["imp"]) == want and want != 0 for v in tiers.values())

    return dict(overall=overall, halves=halves, years=years, tiers=tiers,
                halves_ok=halves_ok, years_ok=years_ok, tiers_ok=tiers_ok,
                y_present=y_present, y_agree=y_agree, y_required=y_required,
                median_date=median)


def evaluate_cell(variant: Variant, arm_positions, base_positions,
                  arm_bc: M.BookCurves, base_bc: M.BookCurves,
                  arm_stats: M.PathStats, base_stats: M.PathStats,
                  affected: dict, eval_dates: list[str],
                  st: A.Settings, is_v3: bool,
                  sibling: dict | None = None,
                  sibling_why: str = "not read") -> dict:
    """The whole conjunction for one cell. Returns every component."""
    sizing = variant.kind == KIND_SIZING
    capital = st.capital

    gain, ratio = dd_improvement(base_stats, arm_stats)
    axis = union_axis(base_bc, arm_bc)
    point, lo, hi = HE.boot_ci(axis, aligned_daily(base_bc, axis),
                               aligned_daily(arm_bc, axis), capital,
                               HE.METRIC_MAXDD, n=BOOT_N, seed=BOOT_SEED,
                               alpha=BOOT_ALPHA)

    paired = paired_rows(arm_positions, base_positions)
    if paired:
        d_lo, d_hi = P.boot_ci_paired_by_date(paired, "a", "b", n=P.BOOT_N)
        d_mean = (statistics.fmean(p["a"] for p in paired)
                  - statistics.fmean(p["b"] for p in paired))
    else:
        d_lo = d_hi = d_mean = float("nan")

    stab = stability(base_bc, arm_bc, capital, affected["dates"], eval_dates,
                     base_positions, arm_positions, affected["rows"])
    cont = continuation(arm_positions, by_rec(base_positions)) if not sizing else None

    n_dates = len(affected["dates"])
    n_rows = affected["n_rows"]
    powered = n_dates >= MIN_AFFECTED_DATES and n_rows >= MIN_AFFECTED_ROWS

    c1 = (ratio == ratio and ratio >= DD_IMPROVE_MIN and lo == lo and lo > 0)
    c2 = d_lo == d_lo and d_lo > DR_NONINFERIORITY
    c3 = stab["halves_ok"] and stab["years_ok"]
    c4 = stab["tiers_ok"]
    # Clause 5 is a CORROBORATION clause and its referent — the v3 cell — is
    # produced by a SEPARATE process. It is read here from that run's recorded
    # sidecar when one exists (`read_sibling_cells`), and is VACUOUS-but-
    # DISCLOSED when it does not, exactly as the registration fixes for a v3
    # cell with no sign. It is NOT hardcoded True: a powered, opposite-signed
    # v3 cell fails it and blocks the candidate.
    c5, c5_text = clause_five(variant.name, ratio, sibling, sibling_why, is_v3)
    c6 = n_dates >= MIN_AFFECTED_DATES
    c7 = True if sizing else cont["passed"]

    dd_contrary = (ratio == ratio and ratio <= -DD_IMPROVE_MIN
                   and hi == hi and hi < 0)
    r_contrary = d_hi == d_hi and d_hi <= DR_NONINFERIORITY

    token = verdict_token(powered=powered, dates_ok=c6, dd_contrary=dd_contrary,
                          r_contrary=r_contrary, dd_ok=c1, r_ok=c2,
                          stab_ok=(c3 and c4 and c5), cont_ok=c7, sizing=sizing)
    if sizing:
        token = SECONDARY_PREFIX + token

    return dict(gain=gain, ratio=ratio, ci=(lo, hi), point=point,
                d_mean=d_mean, d_ci=(d_lo, d_hi), n_paired=len(paired),
                stab=stab, cont=cont, powered=powered, c5_text=c5_text,
                n_aff_rows=n_rows, n_aff_dates=n_dates,
                criteria=dict(c1_dd=c1, c2_dr=c2, c3_stability=c3,
                              c4_tiers=c4, c5_v3=c5, c6_dates=c6, c7_cont=c7),
                dd_contrary=dd_contrary, r_contrary=r_contrary,
                verdict=token, is_v3=is_v3)


# ═══════════════════════════════════════════════════════════════════════════
# G1 — the leak guard
# ═══════════════════════════════════════════════════════════════════════════

def shift_on_grid(t, series: dict, after=None) -> dict:
    """`series` re-keyed so GRID session `i` carries what session `i-1` carried.

    The shift is on the TRADE'S OWN GRID — the axis the rules actually read —
    not on the cached file's date keys. That distinction is load-bearing: an
    option-history file carries dates the position's grid never reads (before
    the signal, after the exit, and any session the weekday grid skips), so
    shifting on the file's key order pulls a value the rule never saw onto a
    grid session, which is not "one session later" and is not what the gate
    means. Shifting on the reading axis makes session `i` see exactly what
    session `i-1` saw — strictly older information — which is the property
    under test.

    Keys OFF the grid are carried verbatim; a grid session whose predecessor
    had no value simply has no value (MISSING stays MISSING, never zero).

    `after` holds grid sessions at or before it FIXED. ARM U needs it: its
    ATR14 is a SCALAR frozen at entry off bars `<= entry`, and shifting that
    window too would move the THRESHOLD rather than the information set — the
    gate would then be measuring an ATR re-estimate, not a leak. Holding the
    entry window also keeps `entry_day()`'s anchor unchanged, so the two runs
    are comparable at all.
    """
    grid = list(t.grid)
    gset = set(grid)
    out = {k: v for k, v in series.items() if k not in gset}
    for i, day in enumerate(grid):
        if after is not None and day <= after:
            if day in series:
                out[day] = series[day]
            continue
        if i >= 1 and grid[i - 1] in series:
            out[day] = series[grid[i - 1]]
    return out


def vol_spike_session(t, vol, mult: float = X.VOL_CLIMAX_MULT) -> int | None:
    """GATE-ONLY probe: the VOLUME leg of ARM O's climax variant, alone.

    NOT the rule and never an exit. `vol_climax_session` is a CONJUNCTION — a
    volume spike AND a mark that closed against the position — and only the
    volume half is governed by the series G1 shifts. Delaying the volume while
    the mark stays put therefore re-pairs the two legs, and a firing session
    can legitimately move EARLIER for that reason alone: a spike that missed an
    adverse mark on its own session can land on one a session later, ahead of
    the original firing. That is an artifact of shifting one leg of a
    conjunction, not a rule reading the future.

    So G1's DIRECTION half is evaluated on this probe for the volume variant —
    the leg the shifted series actually governs — while the conjunction's own
    earlier-firings are printed as a DISCLOSED, non-gating count. See the
    2026-09-05 wording correction appended to the registration.

    `_vol_climax_is_at_or_after_the_spike` pins this probe to the rule it is
    standing in for, so the two cannot drift apart silently.
    """
    observed: list[float] = []
    for i, day in enumerate(t.grid, start=1):
        v = vol.get(day)
        if v is None:
            continue
        observed.append(float(v))
        median = statistics.median(observed)
        if median <= 0:
            continue
        if v >= float(mult) * median:
            return i
    return None


def _vol_climax_is_at_or_after_the_spike(t, vol) -> bool:
    """The conjunction can only fire at or after its own volume leg."""
    spike = vol_spike_session(t, vol)
    fire = X.vol_climax_session(t, vol)
    if fire is None:
        return True
    return spike is not None and fire >= spike


def g1_leak(recs: list[dict], variants: list[Variant]) -> tuple[int, dict]:
    """Shift every auxiliary series one session forward; assert the direction.

    Two halves, both required: at least ONE firing session must CHANGE (which
    proves the series is actually being read), and NO firing session may move
    EARLIER (which proves the rule is not reading the future).

    THE FIRST HALF IS TALLIED PER VARIANT. Its stated purpose is per-series —
    "the first half proves the series is actually being read" — and one counter
    aggregated over every variant lets a series that is in fact never read hide
    behind one that changes. Each EXERCISED variant must change at least one
    firing session on its own, and the per-variant table is printed.

    A variant that reads no auxiliary series — ARM W reads only marks, ARM P has
    no trigger, ARM D moves no exit — cannot leak through one and is reported as
    NOT EXERCISED rather than passed.

    The DIRECTION half is evaluated on ARM O's volume variant through
    `vol_spike_session`, the leg the shifted series governs; see that function
    and the 2026-09-05 wording correction on the registration for why, and for
    what is printed instead.
    """
    hdr("G1 — LEAK GUARD (every auxiliary series shifted ONE SESSION FORWARD)")
    print("""  The shift is on the TRADE'S OWN GRID, the axis the rules read: session
  d carries what session d-1 carried, so a rule reading the shifted series sees
  strictly OLDER information. A correct rule's exits then move LATER or stay;
  one that moves EARLIER is reading ahead. Both halves are required: at least
  one firing session must CHANGE (the series is genuinely read) and none may
  move EARLIER. MISSING stays MISSING under the shift — never zero.

  ARM U's shift holds bars at or before the ENTRY session fixed. ATR14 is a
  SCALAR frozen at entry off bars <= entry; shifting that window too would move
  the THRESHOLD, and the gate would be measuring an ATR re-estimate rather than
  the information set. Every session after entry is shifted in full.

  ARM O's VOLUME variant is a CONJUNCTION — a volume spike AND a mark that
  closed against the position — and only the volume half is governed by the
  series shifted here. Delaying the volume while the mark stays put re-pairs
  the two legs, so a firing session can move earlier for that reason alone.
  The direction half is therefore read on the VOLUME LEG, and the
  conjunction's own earlier-firings are printed below as a DISCLOSED,
  NON-GATING count. Registered as a dated wording correction, not a silent
  change.""")

    checks = {"changed": 0, "earlier": 0, "compared": 0, "exercised": [],
              "vol_conjunction_earlier": 0, "probe_incoherent": 0,
              "per_variant": {}}
    for v in variants:
        if v.arm not in ("U", "O"):
            continue
        checks["exercised"].append(v.name)
        # PER VARIANT, not one aggregate. The "at least one exit CHANGED" half
        # exists to prove that THIS variant's series is genuinely read; a single
        # counter summed over every variant lets a series that is never read
        # (a wiring bug returning an empty map) hide behind one that is.
        per = checks["per_variant"].setdefault(
            v.name, {"changed": 0, "earlier": 0, "compared": 0})
        for config in v.grid:
            for rec in recs:
                if rec["credit"]:
                    continue
                t = rec["t"]
                # The series are taken from the SAME loaders the arms are wired
                # to (`exit_overlays.default_*_for`), exclusions included, so
                # this gate probes what the run reads rather than a parallel
                # read of the same files.
                if v.arm == "U":
                    bars = X.default_bars_for(rec)
                    if not bars:
                        continue
                    ed = X.entry_day(t, sessions=set(bars))
                    base = X.atr_stop_session(t, bars, config)
                    got = X.atr_stop_session(
                        t, shift_on_grid(t, bars, after=ed), config)
                elif v.key == "oi":
                    oi = X.default_oi_for(rec)
                    if not oi:
                        continue
                    base = X.oi_unwind_session(t, oi, config)
                    got = X.oi_unwind_session(t, shift_on_grid(t, oi), config)
                else:
                    vol = X.default_vol_for(rec)
                    if not vol:
                        continue
                    shifted = shift_on_grid(t, vol)
                    if not _vol_climax_is_at_or_after_the_spike(t, vol):
                        checks["probe_incoherent"] += 1
                    fb, fg = X.vol_climax_session(t, vol), X.vol_climax_session(t, shifted)
                    if fb is not None and fg is not None and fg < fb:
                        checks["vol_conjunction_earlier"] += 1
                    if fb != fg:
                        checks["changed"] += 1
                        per["changed"] += 1
                    checks["compared"] += 1
                    per["compared"] += 1
                    base = vol_spike_session(t, vol)
                    got = vol_spike_session(t, shifted)
                    if base is not None and got is not None and got < base:
                        checks["earlier"] += 1
                        per["earlier"] += 1
                    continue
                checks["compared"] += 1
                per["compared"] += 1
                if base != got:
                    checks["changed"] += 1
                    per["changed"] += 1
                if base is not None and got is not None and got < base:
                    checks["earlier"] += 1
                    per["earlier"] += 1

    if not checks["exercised"]:
        print("\n  G1: NOT EXERCISED — no arm in this run reads an auxiliary "
              "series (ARM W\n  reads only marks; ARM P has no trigger; ARM D "
              "moves no exit). The gate is\n  neither passed nor failed here.")
        return 0, checks

    print(f"\n  variants exercised: {', '.join(checks['exercised'])}")
    print(f"  (row, config) comparisons {checks['compared']}   "
          f"firing session CHANGED {checks['changed']}   "
          f"moved EARLIER {checks['earlier']}")
    print(f"\n  {'variant':<16} {'compared':>9} {'changed':>8} {'earlier':>8}")
    for name, per in checks["per_variant"].items():
        print(f"  {name:<16} {per['compared']:>9} {per['changed']:>8} "
              f"{per['earlier']:>8}"
              f"   {'reads its series' if per['changed'] else 'READS NOTHING'}")
    print(f"  DISCLOSED, NON-GATING: ARM O's volume CONJUNCTION fired earlier on "
          f"{checks['vol_conjunction_earlier']} (row, config)\n  pair(s) under "
          f"the delayed series — the re-paired-legs artifact described above, "
          f"not a leak.\n  Probe-vs-rule coherence failures (the conjunction "
          f"firing BEFORE its own volume leg):\n  "
          f"{checks['probe_incoherent']} — any non-zero here means the probe "
          f"has drifted from the rule.")
    if checks["probe_incoherent"]:
        print("\n  *** G1 FAILED: the volume probe no longer stands in for the "
              "rule. ***")
        return EXIT_GATE_FAILURE, checks
    if checks["earlier"]:
        print(f"\n  *** G1 FAILED: {checks['earlier']} exit(s) moved EARLIER "
              f"under a DELAYED series. ***")
        return EXIT_GATE_FAILURE, checks
    silent = [n for n, per in checks["per_variant"].items() if not per["changed"]]
    if silent:
        print(f"\n  *** G1 FAILED: shifting the series changed NOTHING for "
              f"{', '.join(silent)} — that\n      variant's series is not being "
              f"read, so no conditional number below means\n      what it says. "
              f"The half is per-VARIANT: another variant's series changing "
              f"cannot\n      stand in for this one's. ***")
        return EXIT_GATE_FAILURE, checks
    print("  G1: PASS — the series is read, and no exit moves earlier under a "
          "delayed one.")
    return 0, checks


# ═══════════════════════════════════════════════════════════════════════════
# G-FORK / G-CAL
# ═══════════════════════════════════════════════════════════════════════════

def g_fork(recs: list[dict], st: A.Settings) -> int:
    """The DISABLED overlay must reproduce `account_sim.replay_sized` exactly.

    Every overlay, with its own rule disabled, must reproduce the frozen replay
    on ALL rows. `tests/test_exit_overlays.py` carries the fixture half of this
    (all nine exit reasons, both entry signs, the knob grid); this is the
    RUNTIME half, on the book the study actually loaded.
    """
    hdr("G-FORK — the overlay is a COMPOSITION, not a fork")
    print("""  With its own rule DISABLED, every overlay must reproduce
  account_sim.replay_sized field for field — exit_reason, days_held, R,
  dollars, stop_exact — on every row of the loaded book. lib/harness.py is
  FROZEN and is neither edited nor copied here; one disagreement fails the run
  and nothing below may be read.""")
    disabled = X.make_replayer(X.DISABLED)
    bad = []
    n = 0
    for rec in recs:
        for contracts in (1, 3):
            want = A.replay_sized(rec, contracts, st.budget)
            got = disabled(rec, contracts, st.budget)
            n += 1
            # EXACT `!=`, no tolerance. The registration says the disabled
            # overlay reproduces `harness.replay` EXACTLY and
            # `tests/test_exit_overlays.py` asserts exact equality; the two
            # paths are the SAME arithmetic on the SAME inputs, so a tolerance
            # buys nothing and would weaken the "N/N exact" line printed below
            # into a claim the comparison did not make.
            if any(got[k] != want[k] for k in want):
                bad.append((rec["date"], rec["ticker"], contracts, want, got))
    print(f"\n  comparisons {n} ({len(recs)} rows x 2 contract counts, "
          f"stop ${st.budget:,.0f})")
    if bad:
        print(f"\n  *** G-FORK FAILED: {len(bad)} disagreement(s). ***")
        for d, tick, c, want, got in bad[:20]:
            print(f"    {d} {tick} x{c}: replay_sized {want} vs overlay {got}")
        return EXIT_GATE_FAILURE
    print(f"  G-FORK: PASS — {n}/{n} exact.")
    return 0


def g_cal(baseline: A.Sim, day_lists, st: A.Settings) -> int:
    """The HOST simulation is unchanged: the shipped baseline IS `account_sim`.

    The baseline book is built with `replayer=None` — the default path — and is
    compared, by `book_signature`, against a DIRECT `account_sim.simulate()` on
    the same population with its OWN fresh cache. A mismatch means this study's
    plumbing moved the host's book, and no arm-versus-shipped number would mean
    anything; the run stops.

    The other half of G-CAL — `account_sim`'s own G2-G5 under the default
    replayer — is `python -m scripts.backtest_study.f4_deployment.account_sim
    --selftest-gates`, run outside this process because it is a property of that
    module, not of this population.
    """
    hdr("G-CAL — the host simulation is unchanged")
    print("""  The SHIPPED baseline every arm is paired against is
  account_sim.simulate() on the default replayer path. It is re-run here
  directly, with its own fresh memo, and the two books' order-sensitive
  book_signature must match exactly. account_sim's own G2-G5 are checked by
  its --selftest-gates run, outside this process.""")
    direct = A.simulate(day_lists, st.cfg("G-CAL direct"), cache=A.new_cache())
    want = A.book_signature(direct)
    got = A.book_signature(baseline)
    print(f"\n  positions   direct {len(want)}   study baseline {len(got)}")
    if want != got:
        print("\n  *** G-CAL FAILED: the study's baseline book is not "
              "account_sim's. ***")
        for i, (w, g) in enumerate(zip(want, got)):
            if w != g:
                print(f"    first disagreement at index {i}:\n      direct {w}"
                      f"\n      study  {g}")
                break
        return EXIT_GATE_FAILURE
    print("  G-CAL: PASS — book_signature identical on every position.")
    return 0


# ═══════════════════════════════════════════════════════════════════════════
# Printing
# ═══════════════════════════════════════════════════════════════════════════

def _fmt(x: float, spec: str = "+.3f") -> str:
    return "n/a" if x != x else format(x, spec)


def print_cell(variant: Variant, ev: dict, arm_stats: M.PathStats,
               base_stats: M.PathStats, capital: float, arm_p_dollars: bool) -> None:
    sub(f"{variant.name} — {variant.label}")
    if variant.note:
        print(f"  ({variant.note})")
    if variant.arm == "D":
        print("  SECONDARY — a SIZING rule. It can never ship from this study; "
              "the most it can\n  ever do is queue an f4 registration. No token "
              "below is an exit finding.")
    if variant.arm == "W" and variant.key == "prod":
        print("""  READ THE `affected` COUNT ON THIS CELL WITH CARE. The grid point is
  pt/sl/tef ONLY: `knob_profile` REPLACES the whole exit profile, so this cell
  drops the shipped `be_after 0.50` and the BEAR_HE merge that
  `account_sim.profile_for` applies on bear-debit rows. Any difference from the
  shipped baseline HERE is therefore that merge, not walk-forward selection —
  which is the opposite of what this control exists to show. Registered
  behaviour (the grid is pt x sl x tef and PROD is a point in it), stated here
  so the count is not read as selection movement.""")

    withhold = (variant.arm == "P" and not arm_p_dollars)
    if withhold:
        print("""  ARM P's account-level drawdown — its LEVELS, its improvement and that
  improvement's CI bounds — is quoted as a SHARE OF STARTING CAPITAL, not in
  dollars. The registration carries an OPEN operator ACK on whether the planning
  rule "quote R, not dollars, for ARM P" reaches the whole-book MTM co-primary;
  no ack is recorded, so this run uses the registration's own ALTERNATIVE
  reading, which is recorded as wording correction (c) of 2026-09-05 (build,
  second). The verdict is identical either way: clause 1 is evaluated on the
  IMPROVEMENT RATIO, which is scale-free. Re-run with --arm-p-dollars for the
  dollar levels.""")
        print(f"  max DD   shipped {base_stats.max_dd / capital:>8.2%} of capital"
              f"   arm {arm_stats.max_dd / capital:>8.2%}")
    else:
        print(f"  max DD   shipped ${base_stats.max_dd:>10,.0f}"
              f"   arm ${arm_stats.max_dd:>10,.0f}"
              f"   ({base_stats.max_dd / capital:.1%} / "
              f"{arm_stats.max_dd / capital:.1%} of capital)")
    print(f"  Ulcer    shipped {base_stats.ulcer:>7.3f}%   arm {arm_stats.ulcer:>7.3f}%"
          f"     time-under-water shipped {base_stats.tuw:.1%}   arm {arm_stats.tuw:.1%}")
    print(f"  affected {ev['n_aff_rows']} rows / {ev['n_aff_dates']} dates"
          f"   paired rows {ev['n_paired']}")

    lo, hi = ev["ci"]
    # Under `withhold` the CI bounds are converted TOO. They are the same
    # dollar-improvement estimator as the point figure three characters to
    # their left, so printing them raw would quote in dollars the very number
    # the banner above just said is not quoted in dollars.
    if withhold:
        gain_txt = f"{ev['gain'] / capital:+.2%} of capital"
        ci_txt = (f"[{_fmt(lo / capital, '+.2%')}, {_fmt(hi / capital, '+.2%')}] "
                  f"of capital")
    else:
        gain_txt = f"${ev['gain']:+,.0f}"
        ci_txt = f"[{_fmt(lo, '+,.0f')}, {_fmt(hi, '+,.0f')}]"
    print(f"  1 max DD improvement {gain_txt} = {_fmt(ev['ratio'], '+.1%')} of the "
          f"shipped drawdown\n      block-bootstrap CI95 {ci_txt} "
          f"(n={BOOT_N}, chronological moving block)"
          f"   {'PASS' if ev['criteria']['c1_dd'] else 'FAIL'}")
    d_lo, d_hi = ev["d_ci"]
    print(f"  2 paired DeltaR by date {_fmt(ev['d_mean'])}   CI95 "
          f"[{_fmt(d_lo)}, {_fmt(d_hi)}]   lower bound > {DR_NONINFERIORITY}"
          f"   {'PASS' if ev['criteria']['c2_dr'] else 'FAIL'}")

    st_ = ev["stab"]

    def acct_imp(v: float) -> str:
        """EVERY account-level max-DD improvement figure in this cell, in the
        cell's own unit and LABELLED.

        The halves, the years and the tier lines carry the SAME account-level
        dollar improvement estimator as clause 1's point figure, so under
        `withhold` they are converted exactly as it is — printing them raw
        would quote in dollars the very number the banner above says is not
        quoted in dollars. And the unit is named either way: a bare `+600`
        beside a `% of capital` banner tells a reader nothing about which it is.
        """
        if v != v:
            return "n/a"
        if withhold:
            return f"{v / capital:+.2%} of cap"
        return f"${v:+,.0f}"

    halves = "  ".join(f"{k} {acct_imp(v['imp'])} "
                       f"(aff dates {v['n_dates']}, aff rows {v['n_rows']})"
                       for k, v in st_["halves"].items())
    years = "  ".join(f"{y} {acct_imp(v['imp'])} "
                      f"(eval dates {v['n_dates']}, aff {v['n_aff_dates']})"
                      for y, v in st_["years"].items())
    print(f"  3 halves (split at the median evaluated date {st_['median_date']}): "
          f"{halves or '(none)'}\n      years: {years or '(none)'}   "
          f"{st_['y_agree']}/{st_['y_present']} agree, {st_['y_required']} "
          f"required   {'PASS' if ev['criteria']['c3_stability'] else 'FAIL'}")
    print("      DISCLOSED, NON-GATING: the per-half counts above are printed so a "
          "cleared sign\n      resting on a thin half is visible. No thinness "
          "floor is applied — this\n      registration commits none.")
    print("      The YEAR requirement is the registration's \">= 2 of the 3 years "
          "present\": all of\n      them when fewer than 3 are present, and TWO "
          "whenever 3 OR MORE are. Clause 3\n      is written against a 3-year "
          "book and is NOT scaled up past it — disclosed here\n      rather "
          "than tightened at run time, which would be an unregistered floor.")
    tiers = "  ".join(f"{t} {acct_imp(v['imp'])} (n={v['n']})"
                      for t, v in st_["tiers"].items())
    print(f"  4 pricing tiers: {tiers or '(none)'}"
          f"   {'PASS' if ev['criteria']['c4_tiers'] else 'FAIL'}")
    print("      READING, stated rather than left to `nan` propagation: a tier "
          "with NO SIGN —\n      no positions in one of the two books, so there "
          "is no improvement to compute —\n      cannot be same-signed and the "
          "clause is NOT cleared. The registration spells the\n      signless "
          "case out for clause 3 (fails) and clause 5 (vacuous pass) and is "
          "silent\n      for clause 4; this run takes clause 3's STRICT reading, "
          "because clause 4 is a\n      stability clause asking the PRIMARY "
          "population to agree with itself. Recorded as\n      wording "
          "correction (g) of 2026-09-05 (build, third).")
    print(f"  5 SECONDARY v3: {ev['c5_text']}"
          f"   {'PASS' if ev['criteria']['c5_v3'] else 'FAIL'}")
    print(f"  6 affected dates {ev['n_aff_dates']} >= {MIN_AFFECTED_DATES}"
          f"   (G0's date floor, restated)"
          f"   {'PASS' if ev['criteria']['c6_dates'] else 'FAIL'}")
    if ev["cont"] is None:
        print("  7 CONT: DROPPED from ARM D's conjunction — a sizing rule moves "
              "no exit, so its\n      continuation rate is the baseline's by "
              "construction. ARM D's conjunction is 1-6.")
    else:
        c = ev["cont"]
        share = "n/a" if c["share"] is None else f"{c['share']:.0%}"
        strict = "n/a" if c["strict_share"] is None else f"{c['strict_share']:.0%}"
        print(f"  7 CONT: {c['n_continuation']}/{c['n_early']} early exits "
              f"({share}) followed by a post-exit max\n      > realized"
              f"+{CONTINUATION_MARGIN:.2f} R   (strict any-recovery share "
              f"{strict}, DISCLOSED, not the gate)"
              f"   {'PASS' if c['passed'] else 'FAIL'}")
    print(f"  VERDICT: {ev['verdict']}")


# ═══════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--era", default=None,
                    help="era to run (default: STUDY_ERA, else `current`). The "
                         "runner sets STUDY_ERA for the whole suite; this flag "
                         "is the per-study equivalent and is named in the header.")
    ap.add_argument("--population", default=POP_PRIMARY,
                    choices=(POP_PRIMARY, POP_ALL),
                    help="PRIMARY is account_sim's dense_episodes population; "
                         "`all` is the DISCLOSED SECONDARY CUT and carries no "
                         "verdict of its own.")
    ap.add_argument("--arms", default=ALL_ARMS,
                    help=f"subset of {ALL_ARMS} to run. The registration freezes "
                         f"the arms at five and adds none.")
    ap.add_argument("--arm-p-dollars", action="store_true",
                    help="print ARM P's account-level drawdown in DOLLARS. Off "
                         "until the registration's OPEN operator ACK on the "
                         "scope of the ARM P dollars ban is recorded; the "
                         "verdict is unaffected either way (clause 1 is a "
                         "scale-free ratio).")
    ap.add_argument("--config", type=Path, default=A.DEFAULT_CONFIG,
                    help="the account simulation this study deploys through "
                         "(default: config/account-sim.yml).")
    a = ap.parse_args(argv)

    arms = "".join(ch for ch in ALL_ARMS if ch in a.arms.upper())
    if not arms:
        print(f"no arms selected from {a.arms!r} — expected a subset of {ALL_ARMS}.")
        return 2

    try:
        st = A.load_settings(a.config)
    except A.ConfigError as exc:
        print(f"CONFIG ERROR: {exc}")
        return 2

    recs, diag = load_book(include_bs=False, era=a.era)
    era = diag["era"]
    cache = A.new_cache()          # ONE shared memo for the whole era-run

    hdr(f"exit_drawdown — ERA {era}   (pre-registration "
        f"research/pre-registrations/f2_management/exit_drawdown.md)")
    print(f"book: {len(recs)} rows  era={era}  "
          f"counts_by_source={diag['counts_by_source']}  "
          f"date_range={diag['date_range']}  (bs excluded, calibration gate ON)")
    print(f"debit_calib: {diag['debit_calib']}")
    print(f"arms: {arms}   population: {a.population}   "
          f"capital ${st.capital:,.0f}  risk {st.risk_pct:.0%} = "
          f"${st.budget:,.0f}/position  {st.max_per_day}/day")
    print("""
  NOTHING SHIPS FROM THIS RUN UNDER ANY OUTCOME. A CANDIDATE queues an
  independent-window confirmation; ARM D can only ever queue an f4
  registration. No annualised figure, no Sharpe and no time-to-recover appears
  anywhere in this report, by construction.""")
    if era == "v3":
        print("""
  THIS IS THE SECONDARY ERA. v3 is RUN and REPORTED and CARRIES NO VERDICT OF
  ITS OWN; v3 and v4 rows are NEVER pooled. Its cells print tokens so the
  PRIMARY run's clause 5 can be graded ACROSS the two reports, which is the
  only place that comparison can honestly be made.""")

    variants = variants_for(arms)

    # ── the population ──────────────────────────────────────────────────────
    all_dates = {str(r["date"]) for r in recs}
    episodes = A.dense_episodes(
        (d for d, _ in P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    ep_dates = {str(d) for ep in episodes for d in ep}
    pop_dates = ep_dates if a.population == POP_PRIMARY else all_dates

    hdr("POPULATION AND BASIS")
    print(f"""  Deployment population: {a.population.upper()}.
  dense episodes {len(episodes)}  covering {len(ep_dates)} dates;
  full book {len(all_dates)} dates. account_sim's FEASIBLE verdict is a
  dense-episode claim, which is why PRIMARY is that population and `all` is a
  disclosed secondary cut carrying no verdict.
  Baseline: the SHIPPED profile as account_sim.profile_for resolves it per row
  (base -> bear-debit be_after .50 -> BEAR_HE), NEVER a clean DEBIT_PROD.
  CREDIT rows keep CREDIT_PROD in every arm — they are in the book so the
  ledger and the curve are the real book, not so a credit exit is tested.""")

    # The walk-forward geometry is computed HERE, before G-COV, purely so the
    # coverage censuses can be reported on the population the conditional
    # numbers are actually computed on (the OOS-stitched evaluated set). It is
    # PRINTED below, in its own section, in the order the report reads.
    splits = build_splits(pop_dates)
    block_map = block_index(splits)
    burn = burn_in_dates(pop_dates, splits)
    oos_dates = set(block_map)

    # ── G-COV, before any conditional number ────────────────────────────────
    hdr("G-COV — COVERAGE. Printed BEFORE any conditional number.")
    print("""  A conditional figure printed above its coverage line is a reporting
  defect. Every count below comes from len(records) after filters at run time —
  never from a stored expected figure.""")
    pop_recs = [r for r in recs if str(r["date"]) in pop_dates]
    oos_recs = [r for r in recs if str(r["date"]) in oos_dates]
    print(f"\n  population rows {len(pop_recs)}   dates {len(pop_dates)}   "
          f"debit {sum(1 for r in pop_recs if not r['credit'])}   "
          f"credit {sum(1 for r in pop_recs if r['credit'])}")
    print(f"  OOS-EVALUATED rows {len(oos_recs)}   dates {len(oos_dates)}   "
          f"(the population every conditional number below is computed on; the "
          f"line\n  above is the whole POPULATION, burn-in included, and is "
          f"the wider denominator)")
    print("""  BOTH DENOMINATORS ARE PRINTED FOR EVERY CENSUS BELOW. The census on the
  population says what the caches hold; the census on the OOS-evaluated rows
  says what the arms could actually read on the dates the verdicts are read
  from. Quoting only the first would describe a different population from the
  one the numbers below it come from.""")

    def _two_denominators(label: str, fn, render) -> None:
        sub(label)
        for scope, rows in (("POPULATION (burn-in included)", pop_recs),
                            ("OOS-EVALUATED (the verdict population)", oos_recs)):
            print(f"  -- {scope}: {len(rows)} rows")
            render(fn(rows))

    if "U" in arms:
        def _render_u(cu: dict) -> None:
            print(f"     debit rows {cu['n']}   tickers {len(cu['tickers'])}   "
                  f"tickers with NO cached series {len(cu['tickers_no_bars'])}")
            print(f"     EXCLUDED and counted: no bars {cu['no_bars']}   no entry "
                  f"anchor {cu['no_entry_anchor']}   close-only `Price~` "
                  f"{cu['close_only']}\n                           atr14_pct None "
                  f"{cu['no_atr']}   no bull_/bear_ direction {cu['no_direction']}")
            print(f"     USABLE by ARM U: {cu['usable']}   "
                  f"NOT GOVERNED by the ATR rule: {cu['n'] - cu['usable']}")
        _two_denominators("ARM U — underlying bar coverage", arm_u_census, _render_u)
        print("""  WHAT THE EXCLUSION MEANS FOR VARIANT (b). ARM U/b REPLACES the shipped
  `sl` with the ATR stop. It may only do that on a row the ATR rule can GOVERN:
  every row counted as EXCLUDED above replays the SHIPPED profile UNCHANGED,
  `sl` included. Stripping the stop from a row the rule cannot fire on would
  run it with NEITHER stop — an arm nobody registered — and its book would be
  read as ARM U's. `exit_overlays.atr_governs()` is the single test, and
  `tests/test_exit_overlays.py` pins the identity: an armed (b) overlay on a
  bars-less row equals `replay_sized` field for field.""")
    if "O" in arms:
        def _render_o(co: dict) -> None:
            print(f"     debit rows {co['n']}   EXCLUDED: no single long leg "
                  f"{co['no_long_leg']}   no OI series {co['no_series']}   "
                  f">= {OI_BLANK_EXCLUSION:.0%} blank {co['too_blank']}")
            if co["blank_shares"]:
                print(f"     blank share on the measured rows: median "
                      f"{statistics.median(co['blank_shares']):.1%}   "
                      f"max {max(co['blank_shares']):.1%}")
                print(f"     DENOMINATOR: the SHIPPED HOLD WINDOW (days_held "
                      f"under account_sim.profile_for), median "
                      f"{statistics.median(co['hold_sessions']):.0f} sessions   "
                      f"max {max(co['hold_sessions'])}   — NOT the weekday grid "
                      f"out to expiry / the {P.PATH_CAP_DAYS}-day path cap.")
            print(f"     USABLE by ARM O: {co['usable']}")
        _two_denominators("ARM O — Open Int path coverage", arm_o_census, _render_o)
        print("""  THE DENOMINATOR IS THE ROW'S HOLD SESSIONS, as registered — the shipped
  replay's `days_held`, which is the only hold window ARM O's own exit does not
  depend on. Measuring the blank share over the whole weekday grid instead
  would admit rows the registration excludes (a row held six sessions and blank
  on all six reads as 5% blank against a 120-session grid), which is the
  PERMISSIVE direction. `exit_overlays.shipped_hold_sessions()` is the single
  encoding and both this census and the read boundary call it.
  THE >= 20%-BLANK EXCLUSION BINDS AT THE READ BOUNDARY, not only in this
  census: `exit_overlays.default_oi_for()` returns an EMPTY series for an
  excluded row, and an empty series makes `oi_unwind_session` return None — so
  an excluded row replays the shipped profile and the arm cannot exit it. A
  threshold that only the census knew about would leave the headline book
  carrying exits the registration forbids.
  Blank OI is MISSING; OI literally 0 is a VALID full unwind —
  lib/exit_overlays.load_oi keeps the two distinct, and a missing value on a
  grid day is skipped exactly as an unpriced mark is, never read as a 100%
  drop.""")

    # ── walk-forward geometry ───────────────────────────────────────────────
    hdr("WALK-FORWARD DESIGN — thresholds chosen on TRAIN dates only")
    print(f"""  walk_forward_splits(dates, block={WF_BLOCK}, embargo_days={WF_EMBARGO_DAYS}, \
min_train_dates={WF_MIN_TRAIN_DATES})
  — purged, expanding, the embargo EQUAL to the path cap, so no training label
  can still be open when a block's test dates start.

  BURN-IN IS EXCLUDED AND REPORTED. Dates before the first TEST block exist
  only to train the first fit. They are NOT silently replayed under the shipped
  profile and folded into the headline; the OOS population is EXACTLY the union
  of the blocks' TEST dates.""")
    print(f"\n  blocks {len(splits)}   OOS (test) dates {len(oos_dates)}   "
          f"burn-in dates {len(burn)}")
    if burn:
        print(f"  burn-in span {burn[0]} .. {burn[-1]}   rows "
              f"{sum(1 for r in pop_recs if str(r['date']) in set(burn))}")
    embargo_held = embargo_ok(splits)
    print(f"  embargo respected in every block: {embargo_held}")
    for s in splits:
        print(f"    block {s.idx:>2}  train {len(s.train):>3} dates "
              f"(.. {s.train[-1] if s.train else '-'})   "
              f"test {len(s.test):>3} dates ({s.test[0]} .. {s.test[-1]})")

    if not embargo_held:
        print("""
  *** MACHINERY GATE FAILED: THE EMBARGO. At least one block's last TRAIN date
  is closer to its first TEST date than the registered embargo, so a training
  label could still have been open when that block's test dates began. The
  whole no-lookahead claim rests on the purge, and nothing below it would mean
  what it says — so the run STOPS here rather than printing verdicts with a
  `False` on this line. This is a real failure of the machinery, not a designed
  refusal: `walk_forward_splits` is expected to guarantee it. ***""")
        return EXIT_GATE_FAILURE

    if not oos_dates:
        print("""
  NO TEST BLOCK SURVIVED THE PURGE. Every candidate block's train set is
  thinner than the registered minimum once the 120-day embargo is applied, so
  there is no out-of-sample population to read and no cell can be evaluated.
  That is the honest output of this design on this population — not a failure,
  and not a reason to lower the floor. Every arm is UNDERPOWERED by
  construction; nothing below is computed.""")
        hdr("VERDICT SUMMARY")
        for v in variants:
            token = V_UNDERPOWERED
            if v.arm == "D":
                token = SECONDARY_PREFIX + token
            print(f"  {v.name:<16} {token}   (no OOS dates)")
        return 0

    day_lists = day_lists_for(recs, oos_dates)
    if not day_lists:
        print("\n  no deployable rows on the OOS dates — nothing to simulate.")
        return 0

    # ── machinery gates ─────────────────────────────────────────────────────
    rc = g_fork(recs, st)
    if rc:
        return rc

    baseline = A.simulate(day_lists, st.cfg("SHIPPED baseline"), cache=cache)
    rc = g_cal(baseline, day_lists, st)
    if rc:
        return rc
    base_positions = list(baseline.taken)
    base_bc, base_stats = curves_for(base_positions, st.capital)

    rc = g1_leak(pop_recs, variants)[0]
    if rc:
        return rc

    # ── the fits, the books, the cells ──────────────────────────────────────
    hdr("WALK-FORWARD FITS — per block, on TRAIN dates only")
    print(f"""  Two stages, both registered before any number was seen:
    (1) every configuration's TRAIN mean R via the memoised replay; keep those
        within {TRAIN_R_TOLERANCE} of the best.
    (2) among the survivors, simulate() on the TRAIN day_lists only and pick the
        SMALLEST TRAIN MTM max drawdown.
  Ties break: PROD (ARM W only) -> fewer active rules -> fires on the fewest
  TRAIN rows -> the LARGEST parameter value. Stage 1 is INERT for a SIZING arm
  (it changes no row's exit, so every configuration has the same per-row mean R)
  and every configuration goes straight to stage 2.
  DISCLOSED: stage 1's mean is over ALL train rows, as registered — CREDIT rows
  included. A credit row is forced to the shipped profile in every arm, so it
  adds the SAME constant to every configuration's mean and cannot change the
  order; it does dilute the {TRAIN_R_TOLERANCE} tolerance relative to the debit-only
  signal the grid can move, so each block's credit count is printed beside its
  survivor count and the effective tolerance is visible rather than inferred.
  'tied after (i)-(ii)' is how many configurations reached the fires-on-fewest-
  TRAIN-rows tiebreak; that pass is computed only when it can decide something.""")

    # One FULL-WINDOW book per (arm, configuration), computed once. Two
    # disclosures want the same objects — ARM D's "every grid value's own
    # stitched book" and the in-sample best — and on ARM W that is 36
    # `simulate()` + `book_curves` passes, the run's dominant cost after the
    # per-block stage 2.
    full_books: dict[tuple[str, str], tuple] = {}

    def full_window_book(v: Variant, config):
        key = (v.name, str(config))
        if key not in full_books:
            sim2, pos2 = run_book(v, {0: config}, day_lists, st, cache,
                                  f"{v.name} @ {v.config_label(config)}",
                                  one_block(0))
            bc2, s2 = curves_for(pos2, st.capital)
            full_books[key] = (sim2, pos2, bc2, s2)
        return full_books[key]

    results = []
    mtm_failed = []
    for v in variants:
        chosen: dict[int, object] = {}
        sub(f"{v.name} — per-block selection")
        for s in splits:
            fit = fit_block(v, s, recs, st, cache)
            chosen[s.idx] = fit["pick"]
            print(f"    block {s.idx:>2}  train {fit['n_train_dates']:>3} dates "
                  f"/ {fit['n_train_rows']:>4} rows "
                  f"({fit['n_credit_train_rows']} credit)   survivors "
                  f"{len(fit['survivors']):>2}/{len(v.grid):<2}"
                  f"  tied after (i)-(ii) {fit['n_tied']:>2}  -> "
                  f"{v.config_label(fit['pick'])}")
        picks = Counter(v.config_label(c) for c in chosen.values())
        print(f"    selection tally: {dict(picks)}")

        if v.kind == KIND_SIZING and chosen:
            print(f"""    DISCLOSED, and recorded as wording corrections (b) of
    2026-09-05 (build, second) and (f) of 2026-09-05 (build, third) on the
    registration: `Cfg.dd_throttle` is ONE value for a whole simulation — a
    ledger cannot carry a different `d` per block — so ARM D's walk-forward
    selection has to COLLAPSE to one value before the stitched book can run.
    It collapses to the EARLIEST block's choice, which uses no information
    after its own TRAIN window, so the stitched book REMAINS OUT OF SAMPLE.
    Correction (b)'s MODAL collapse would not: it would replay block 0's TEST
    dates under a `d` fitted on train sets containing those very dates, and
    the cell could not be called out of sample anywhere it was printed. The
    per-block table above shows what each block picked; every grid value's own
    stitched OOS book is printed below, so the reader can see what the collapse
    cost. Collapsed choice (block {min(chosen)}): {v.config_label(collapse_choice(chosen))}.""")
            for g in v.grid:
                _s2, pos2, _bc2, st2 = full_window_book(v, g)
                print(f"      stitched OOS book at {v.config_label(g):<10} "
                      f"positions {len(pos2):>4}   max DD ${st2.max_dd:>10,.0f} "
                      f"({st2.max_dd / st.capital:>6.1%} of capital)   "
                      f"Ulcer {st2.ulcer:.3f}%")

        sim, positions = run_book(v, chosen, day_lists, st, cache, v.name,
                                  map_block(block_map))
        bc, stats = curves_for(positions, st.capital)
        if not bc.reconciles:
            mtm_failed.append((v.name, bc))
        if v.kind == KIND_SIZING:
            # ARM D's OWN registered definition of "affected" (a position
            # ENTERED at the halved budget) IS its `changed` set: G0 and clause
            # 6 read `rows`/`dates`, and for a sizing arm those are the throttled
            # entries. `arm_only`/`base_only` have no meaning here — a sizing
            # rule's book is not compared row-for-row against the shipped one —
            # and the G0 table prints '-' for them.
            aff = throttled_entries(sim, sim.cfg, day_lists)
            aff = dict(changed=aff["rows"], arm_only=[], base_only=[],
                       rows=aff["rows"], n_rows=aff["n_rows"],
                       dates=aff["dates"], knockon_rows=[], knockon_dates=[])
        else:
            aff = affected_set(positions, base_positions)
        results.append((v, sim, positions, bc, stats, aff))

    # G-MTM, printed with the books it was computed on — it has nothing to
    # reconcile until every arm's book exists.
    hdr("G-MTM — the curve and the ledger agree")
    print("""  Every position's cumulative mark-to-market at its exit index, times its
  contracts, must equal the dollars the FROZEN harness booked for it, within
  TOL_DOLLARS per contract. Target = TARGET_POSITION: this book was RE-SIZED
  and RE-EXITED by a replay, so the row's stored realized_pnl_abs describes a
  different position by construction. Two separate computations, but NOT the
  two-stored-columns check, and this report does not call it that.""")
    n_pos = sum(len(r[2]) for r in results) + len(base_positions)
    # The BASELINE is in the gate, not merely in its pass line. Every
    # arm-versus-shipped number in this report is computed against this book;
    # a baseline that failed to reconcile would make all of them meaningless,
    # and the pass line below claims it reconciled.
    if not base_bc.reconciles:
        mtm_failed.insert(0, ("SHIPPED baseline", base_bc))
    if mtm_failed:
        print(f"\n  *** G-MTM FAILED on {len(mtm_failed)} book(s). ***")
        for name, bc in mtm_failed:
            print(f"    {name}: {len(bc.mismatches)} position(s) disagree, "
                  f"worst ${bc.worst_mismatch:,.4f}")
            for m in bc.mismatches[:5]:
                print(f"      {m.date} {m.ticker} x{m.contracts} mtm "
                      f"${m.mtm_at_exit:,.2f} vs booked ${m.booked:,.2f}")
        return EXIT_GATE_FAILURE
    print(f"\n  G-MTM: PASS — {n_pos} positions across the baseline and every "
          f"arm's book\n  reconcile at TOL_DOLLARS ${M.TOL_DOLLARS:.2f} per "
          f"contract; baseline stale marks carried\n  forward inside an open "
          f"window: {base_bc.n_carried_forward}.")

    # ── G0 and the cells ────────────────────────────────────────────────────
    hdr("G0 — POWER. Runs first and blocks every criterion.")
    print(f"""  Floor, registered before any count was known: a cell with
  < {MIN_AFFECTED_DATES} affected DATES or < {MIN_AFFECTED_ROWS} affected ROWS is UNDERPOWERED — its census is
  printed, no criterion is evaluated on it, and it is not re-run on these dates.

  "Affected" means the arm CHANGED THAT ROW'S EXIT, measured on the
  OOS-STITCHED EVALUATED POPULATION (the union of the blocks' TEST dates, after
  the burn-in exclusion and after the arm's own data exclusions) — the same
  population every clause below reads. ARM D is the ONE exception and it is
  DEFINED, not left to the build: a sizing rule changes no exit, so its
  affected rows are the positions ENTERED AT THE HALVED BUDGET and its affected
  dates are the dates on which one was.

  THE FLOOR COUNTS THE `changed` COLUMN ONLY. A row one book took and the other
  did not ('arm-only' / 'base-only') is a RESERVE-RELEASE KNOCK-ON, not a rule
  firing on it: an earlier exit freed a reserve and admitted a later position.
  Counting those towards the floor would inflate power in the PERMISSIVE
  direction — a cell clearing 25 dates / 60 rows on rows the rule never touched
  — so they are printed as a DISCLOSED, NON-GATING breakdown beside it.""")
    print(f"\n  baseline book: {len(base_positions)} positions / "
          f"{len({str(p.rec['date']) for p in base_positions})} dates   "
          f"max DD ${base_stats.max_dd:,.0f} "
          f"({base_stats.max_dd / st.capital:.1%} of capital)   "
          f"Ulcer {base_stats.ulcer:.3f}%   TUW {base_stats.tuw:.1%}")
    print(f"\n  {'cell':<16} {'curve pos':>9} {'aff rows':>9} {'aff dates':>10}"
          f"  {'changed':>8} {'arm-only':>9} {'base-only':>10}  status")
    print("  ('curve pos' is the positions the CURVE sees — ARM P's two halves "
          "count twice; ARM D\n   changes no exit, so its breakdown columns are "
          "'-' and its counts are the SIZING ones.\n   'aff rows'/'aff dates' "
          "ARE the 'changed' column; 'arm-only'/'base-only' are the knock-on\n   "
          "counts and are DISCLOSED, NON-GATING.)")
    for v, _sim, positions, _bc, _stats, aff in results:
        ok = (len(aff["dates"]) >= MIN_AFFECTED_DATES
              and aff["n_rows"] >= MIN_AFFECTED_ROWS)
        sizing = v.kind == KIND_SIZING
        cols = ("-", "-", "-") if sizing else (
            str(len(aff["changed"])), str(len(aff["arm_only"])),
            str(len(aff["base_only"])))
        print(f"  {v.name:<16} {len(positions):>9} {aff['n_rows']:>9} "
              f"{len(aff['dates']):>10}  {cols[0]:>8} {cols[1]:>9} "
              f"{cols[2]:>10}  {'powered' if ok else 'UNDERPOWERED'}")

    if "P" in arms:
        for v, sim, _positions, _bc, _stats, _aff in results:
            if v.arm != "P":
                continue
            cp = arm_p_census(sim.taken)
            sub("ARM P — split census (G-COV)")
            print(f"  LEDGER positions {cp['n']}   SPLIT into two halves "
                  f"{cp['split']}   EXCLUDED: "
                  f"credit {cp['credit']}   n = 1 (cannot be halved) "
                  f"{cp['single_contract']}")
            print("""  The ledger holds the WHOLE reserve until the LATER half exits —
  simulate() carries one exit session per position and cannot release half a
  reserve. That is CONSERVATIVE against the registration's "releases half the
  reserve at the first exit" (it can only admit FEWER later positions, never
  more) and is disclosed here rather than buried. The CURVE does see two
  positions: every ARM P position is re-split into its two halves, each with
  its own exit session and contract count, before book_curves is called.
  Each half carries the per-position dollar stop on its own loss; at this
  sizing a position's max loss is <= the risk budget by construction, so that
  stop cannot bind before the structure's own max loss and the choice is
  immaterial here.""")

    hdr("CELL RESULTS — every cell, regardless of outcome")
    print("""  A cell is a CANDIDATE-FOR-INDEPENDENT-WINDOW only on the FULL
  conjunction. Failing any one clause is failing. A cell that clears DeltaR and
  fails CONT is REACTIVE-AGAIN: it cut the curve by SELLING CONTINUATIONS,
  exactly as the three rejected trails did, and the thread closes for these
  dates. CANDIDATE is NOT a ship — it queues an independent window.""")
    verdicts: dict[str, str] = {}
    cells: dict[str, dict] = {}
    sibling, sibling_why = read_sibling_cells(era)
    print(f"\n  clause 5 referent: "
          f"{'this IS the secondary era' if era == SECONDARY_ERA else sibling_why}")
    for v, _sim, positions, bc, stats, aff in results:
        powered = (len(aff["dates"]) >= MIN_AFFECTED_DATES
                   and aff["n_rows"] >= MIN_AFFECTED_ROWS)
        if not powered:
            sub(f"{v.name} — {v.label}")
            print(f"  affected {aff['n_rows']} rows / {len(aff['dates'])} dates"
                  f"   floor {MIN_AFFECTED_DATES} dates / {MIN_AFFECTED_ROWS} rows")
            token = V_UNDERPOWERED
            if v.arm == "D":
                token = SECONDARY_PREFIX + token
            print(f"  VERDICT: {token}  (census printed, nothing concluded, "
                  f"no re-run on these dates)")
            verdicts[v.name] = token
            cells[v.name] = dict(verdict=token, ratio=None, powered=False,
                                 n_aff_dates=len(aff["dates"]),
                                 n_aff_rows=aff["n_rows"])
            continue
        ev = evaluate_cell(v, positions, base_positions, bc, base_bc, stats,
                           base_stats, aff, sorted(oos_dates), st, era == "v3",
                           sibling=sibling, sibling_why=sibling_why)
        print_cell(v, ev, stats, base_stats, st.capital, a.arm_p_dollars)
        verdicts[v.name] = ev["verdict"]
        cells[v.name] = dict(verdict=ev["verdict"], ratio=ev["ratio"],
                             powered=True, n_aff_dates=ev["n_aff_dates"],
                             n_aff_rows=ev["n_aff_rows"])

    # ── in-sample disclosure ────────────────────────────────────────────────
    hdr("DISCLOSURE, in-sample — NO VERDICT IS READ FROM ANYTHING BELOW")
    print("""  The best configuration by FULL-WINDOW (in-sample) MTM max drawdown on
  the same OOS population, printed only so a reader can see the size of the
  in-sample / out-of-sample gap. No criterion above may be evaluated on it and
  none is.""")
    for v in variants:
        if len(v.grid) < 2:
            print(f"  {v.name:<16} single-configuration grid — nothing to "
                  f"disclose.")
            continue
        rows = []
        for config in v.grid:
            _s, _pos, _bc2, s2 = full_window_book(v, config)
            rows.append((config, s2.max_dd))
        rows.sort(key=lambda r: -r[1])
        best, dd = rows[0]
        print(f"  {v.name:<16} in-sample best {v.config_label(best):<34} "
              f"max DD ${dd:,.0f}   vs shipped ${base_stats.max_dd:,.0f}")

    # ── summary ─────────────────────────────────────────────────────────────
    hdr("VERDICT SUMMARY")
    for v in variants:
        print(f"  {v.name:<16} {verdicts.get(v.name, '-')}")
    if "W" in arms and "ARM W/wf" in verdicts:
        token = prod_robust_token(verdicts["ARM W/wf"])
        print(f"\n  ARM W arm-level token: {token}")
        if token == T_PROD_ROBUST:
            print("  No walk-forward-selected configuration beat PROD out of "
                  "sample on these dates.\n  That is the affirmative reading of "
                  "a null here, and it is what the rest of the\n  study is "
                  "measured against. It ships nothing: it RETAINS the shipped "
                  "profile.")
        elif token == V_UNDERPOWERED:
            print("  PROD-ROBUST is NOT claimed — too few dates to say whether "
                  "PROD survived.")
    print(f"\n  tally: {dict(Counter(verdicts.values()))}")
    written = write_cells_artifact(era, cells)
    if written:
        print(f"  cells recorded for the other era's clause 5: "
              f"{written.relative_to(ROOT)}")
    print(f"""
  Nothing ships from this research-tier study. A CANDIDATE queues an
  independent-window confirmation (the live 2026-08/09 dates, once priced);
  REACTIVE-AGAIN closes the thread for these dates; NULL is recorded as such;
  UNDERPOWERED publishes its census and is not re-run on these dates. Every
  ARM D token is prefixed SECONDARY- and none of them is an exit finding.
  Clause 5 is read ACROSS the two eras: each run records its own cells and reads
  the SECONDARY era's if that run has been recorded (the referent is named above
  the cells). Where it printed VACUOUS, the {'v4' if era == 'v3' else 'v3'} cell did not corroborate —
  it was not asked — and any CANDIDATE carries that annotation into the write-up.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
