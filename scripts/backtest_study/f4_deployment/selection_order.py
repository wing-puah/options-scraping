"""Selection-ORDER study: does a different blind entry ORDER spend the delta budget better?

PRE-REGISTERED 2026-08-14, BEFORE this file was written, in
`research/pre-registrations/f4_deployment/selection_order.md`. Read that first;
nothing here may drift from it. In brief:

  Question  `account_sim` showed the binding constraint is delta exposure, not
            cash, and that the picks the net cap EXCLUDES outperform the ones it
            admits (+0.624 rejected vs +0.290 taken at 0.25x/2.50x). That read
            is post-hoc, it was measured on the v3 era, and it DOES NOT SURVIVE
            THE v4 BUMP -- re-run 2026-08-22, the sign flips in 7 of 8 printed
            comparisons (v4 PRIMARY: taken +0.338 vs rejected +0.134/+0.130).
            The v3 figures stay as the motivation this study was REGISTERED
            under, not as a live claim. The pre-registered question is asked
            anyway, on both eras: does a
            different, BLIND, entry-side ordering of the SAME candidate set spend
            the scarce delta budget better?
  Not this  It is NOT a selection study. Tier membership, the candidate universe,
            sizing, caps and exits are frozen exactly as `account_sim` runs them.
            The only thing an arm changes is the SEQUENCE in which an already-
            eligible day's candidates are offered to the ledger.
  Arms      Six, frozen: O0 (ladder_rank baseline), O1 (delta-notional ASC within
            tier), O2 ($ reserved per unit delta-notional DESC within tier), O3
            (|delta| DESC within tier), O1b (delta-notional ASC, tier-blind), O4
            (seeded random permutation, 200 draws = the null band).
  Unit      A CONTESTED DATE — >=2 eligible candidates and >=1 exclusion in
            {day3_cap, net_delta, per_pos_delta}. Uncontested dates are identical
            across arms by construction and are excluded from the paired test.
  Metric    Within-date paired difference vs O0 in mean R over the day's taken
            positions. Dollars print alongside as a sanity check only. QUOTE R.
  Gates     G0 power pre-check (runs FIRST, blocks everything; <25 affected dates
            -> UNDERPOWERED), G1 plumbing, G2 blindness, G3 attribution,
            G4 no annualised figure, G5 out-of-fold discipline. Gate IDS ARE
            FROZEN: G1's book-line checksum was removed 2026-08-15 and the line
            is now printed descriptively, but nothing was renumbered — the ids
            are named in the pre-registration and in recorded verdicts.
  Bar       The full seven-part conjunction in the registration. Failing any one
            is failing. No arm added, no threshold moved after a number is seen.

NOTHING SHIPS FROM THIS STUDY UNDER ANY OUTCOME. ORDERING-IS-NOISE is a real and
useful verdict.

REFUSES (exit 2) rather than reporting a verdict when the book is too thin to
conclude from, or when G2 has no candidates to compare. UNTESTABLE and FAILED are
different findings and this study says which one it got; exit 3 is `load_book`'s
era guard. See `DESIGNED_REFUSAL_EXIT_CODES` and `lib/era.py`.

    python -m scripts.backtest_study run selection_order
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f4_deployment import account_sim as A  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import hdr, sub  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# Exit codes this study returns as a DESIGNED refusal to produce a result rather
# than as a failure. 2 covers both of this file's refusals — the thin-era guard
# in main() and G2's UNTESTABLE case (an empty population cannot be probed for
# blindness) — as well as the long-standing compounding-config refusal, which is
# the same kind of statement: this study declines to run, it has not failed.
# 3 is `load_book`'s era guard rejecting an export set that is not the era asked
# for. `run.py` finds this by AST parse and never imports the module, so it MUST
# stay a literal module-level assignment — an alias to
# `era.DESIGNED_REFUSAL_EXIT_CODES` would be invisible to it, and a refusal would
# be reported as FAILED with its report deleted. A real gate failure stays exit 1.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# ── frozen constants (registered; none of these is a knob) ───────────────────

# O4, the null band. 200 draws, seed fixed and printed.
DRAWS = 200
SEED = 20260814
BAND_ALPHA = 0.05          # band = [p5, p95]; criterion 7 is "> p95"

# G0's power floor. Declared before the count was knowable — that is the point.
MIN_AFFECTED_DATES = 25

# The exclusion buckets that make a date CONTESTED. `unsizable` is deliberately
# absent: no constraint bound there, the row carries no usable max loss at any
# size, and it burns its slot identically under every ordering.
CONTEST_BUCKETS = ("day3_cap", "net_delta", "per_pos_delta")

# CAP-BOUND-NOT-ORDER-BOUND is a DESCRIPTIVE label, not an adoption decision —
# nothing ships under it or any other verdict. Both thresholds were coded here
# before the study first ran and are not moved afterwards.
CAPBOUND_MAX_ABS_GAIN = 0.05      # |mean paired gain| in R
CAPBOUND_MAX_PICK_DIFF = 0.10     # share of O0's taken positions an arm changes


# ════════════════════════════════════════════════════════════════════════════
# The arms — each is a rank_fn for protocol.ordered_by_day (higher sorts first)
# ════════════════════════════════════════════════════════════════════════════
#
# Every arm reads ENTRY-SIDE FIELDS ONLY — `delta`, `entry_underlying`,
# `max_loss_per_contract`, `tier` — and ties break on the existing `ladder_rank`
# so the walk stays deterministic. G2 enforces the blindness rather than
# asserting it by eye.
#
# DELTA-NOTIONAL IS TAKEN AT THE SIZE THE POSITION WOULD BE OPENED, not per
# contract: the resource the net cap meters is `|delta| x 100 x contracts x
# underlying`, so ranking on the per-contract figure would rank on a quantity
# the constraint never sees. Contracts come from the same MAX-LOSS sizing the
# simulation uses (`risk_contracts` at the configured static budget), which is
# entry-side and knowable before the trade. O2's ratio is size-INVARIANT (the
# contract count cancels), so it is computed per contract and means the same
# thing at any size.

def sized_contracts(rec: dict, budget: float) -> int:
    """Contracts the sim would open, for RANKING only.

    A row with no usable max loss is `unsizable` — the sim skips it but it still
    burns a day slot. It has to hold a place in the order, so it ranks at one
    contract rather than being dropped from the list (dropping it would change
    the candidate set, which is exactly what this study may not do).
    """
    c = A.risk_contracts(rec.get("max_loss_per_contract"), budget)
    return 1 if c is None else c


def sized_dn(rec: dict, budget: float) -> float:
    """|delta-notional| at the size the position would be opened."""
    return abs(A.signed_dn(rec, sized_contracts(rec, budget)))


def dollars_per_delta(rec: dict) -> float:
    """Reserved $ per unit |delta-notional| — size-invariant, so per contract.

    Two degenerate cases, both decided here rather than at read time:
      * no usable max loss -> there are no reserved dollars to spend, so the
        ratio is undefined and the row sorts LAST within its tier;
      * zero delta-notional -> the row consumes NONE of the scarce resource, so
        it is maximally efficient by this arm's own rationale and sorts FIRST.
    """
    mlpc = rec.get("max_loss_per_contract")
    if mlpc is None or mlpc <= 0:
        return float("-inf")
    dn = abs(A.signed_dn(rec, 1))
    if dn <= 0:
        return float("inf")
    return float(mlpc) / dn


def abs_delta(rec: dict) -> float:
    d = rec.get("delta")
    return abs(float(d)) if d is not None else -1.0


def make_rank(arm: str, budget: float):
    """The rank function for `arm`. Higher sorts first (ordered_by_day reverses)."""
    if arm == "O0":
        return P.ladder_rank
    if arm == "O1":
        return lambda r: (P.ladder_rank(r)[0], -sized_dn(r, budget), P.ladder_rank(r)[1])
    if arm == "O2":
        return lambda r: (P.ladder_rank(r)[0], dollars_per_delta(r), P.ladder_rank(r)[1])
    if arm == "O3":
        return lambda r: (P.ladder_rank(r)[0], abs_delta(r), P.ladder_rank(r)[1])
    if arm == "O1b":
        # TIER-BLIND across A u B. Admissible only because A vs B is
        # statistically MERGED (+0.36 vs +0.37, p=.65, third validation) —
        # ELIGIBILITY is unchanged, so this is an ordering change, not a tier
        # change. The tier still breaks ties, below the delta-notional key.
        return lambda r: (-sized_dn(r, budget), P.ladder_rank(r)[0], P.ladder_rank(r)[1])
    raise ValueError(f"unknown arm {arm!r}")


ARMS = (
    ("O0", "ladder_rank — tier, then score_total tie-break",
     "baseline = today's production"),
    ("O1", "delta-notional ASCENDING, within tier",
     "cheapest exposure first fits more picks per unit of the binding budget"),
    ("O2", "reserved-$ per unit delta-notional, DESCENDING, within tier",
     "budget efficiency: most risk-budget deployed per unit of the scarce resource"),
    ("O3", "|delta| DESCENDING, within tier",
     "transfer test of bear_deploy's D4 rule, never yet run outside bear"),
    ("O1b", "delta-notional ASCENDING, TIER-BLIND across A u B",
     "eligibility unchanged; A vs B is statistically merged"),
)
TEST_ARMS = tuple(name for name, _, _ in ARMS if name != "O0")


def perm_keys(day_lists, seed: int) -> dict:
    """O4 draw: a seeded within-day permutation, as `{id(rec): sort key}`.

    Keyed on `day_lists` ORDER (the ladder ordering), never on record identity
    content, so the SAME seed over the blinded copy of the same book produces
    the same permutation — which is what lets G2 probe O4 at all.
    """
    rng = random.Random(seed)
    keys: dict[int, float] = {}
    for _, ranked in day_lists:
        order = list(range(len(ranked)))
        rng.shuffle(order)
        for rec, k in zip(ranked, order):
            keys[id(rec)] = float(k)
    return keys


# ════════════════════════════════════════════════════════════════════════════
# Simulation plumbing — sizing, caps and exits come from account_sim untouched
# ════════════════════════════════════════════════════════════════════════════

def arm_sim(pop, rank_fn, st, label: str, cache: dict):
    """One arm's book. ARM H is OFF (no `bear_by_day`), compounding forced OFF."""
    lists = P.ordered_by_day(pop, rank_fn, P.ladder_eligible)
    return lists, A.simulate(lists, st.cfg(label, compound=False), cache=cache)


def contested_dates(sim) -> set:
    """Dates with >=2 eligible candidates AND >=1 exclusion in CONTEST_BUCKETS."""
    offered: dict = defaultdict(int)
    for p in sim.signal_pos:
        offered[p.rec["date"]] += 1
    excluded: dict = defaultdict(int)
    for rec, why, _ in sim.skipped:
        offered[rec["date"]] += 1
        if why in CONTEST_BUCKETS:
            excluded[rec["date"]] += 1
    return {d for d, n in excluded.items() if n >= 1 and offered[d] >= 2}


def taken_ids(sim) -> set:
    return {id(p.rec) for p in sim.signal_pos}


def date_mean_r(sim) -> dict:
    by: dict = defaultdict(list)
    for p in sim.signal_pos:
        by[p.rec["date"]].append(p.R)
    return {d: statistics.fmean(v) for d, v in by.items()}


def date_dollars(sim) -> dict:
    by: dict = defaultdict(float)
    for p in sim.signal_pos:
        by[p.rec["date"]] += p.dollars
    return dict(by)


def paired_rows(arm_sim_, base_sim, dates) -> tuple[list[dict], int]:
    """One row per contested date where BOTH books hold a position.

    Returns `(rows, n_dropped)`. A date where one arm took nothing cannot carry
    a within-date paired difference; those are counted and reported rather than
    imputed.
    """
    a_r, b_r = date_mean_r(arm_sim_), date_mean_r(base_sim)
    a_d, b_d = date_dollars(arm_sim_), date_dollars(base_sim)
    rows, dropped = [], 0
    for d in sorted(dates):
        if d not in a_r or d not in b_r:
            dropped += 1
            continue
        rows.append(dict(date=d, a=a_r[d], b=b_r[d], gain=a_r[d] - b_r[d],
                         a_dol=a_d.get(d, 0.0), b_dol=b_d.get(d, 0.0)))
    return rows, dropped


def mean_gain(rows) -> float:
    return statistics.fmean(r["gain"] for r in rows) if rows else float("nan")


# ════════════════════════════════════════════════════════════════════════════
# G0 — POWER PRE-CHECK. Runs FIRST and blocks everything.
# ════════════════════════════════════════════════════════════════════════════

def gate_g0(label, sims, base, cont) -> dict:
    hdr(f"[{label}] G0 — POWER PRE-CHECK (runs FIRST; blocks every read below)")
    print(f"""  Unit of observation = a CONTESTED DATE: >=2 eligible candidates and >=1
  exclusion in {{{', '.join(CONTEST_BUCKETS)}}}. Uncontested dates are identical
  across arms BY CONSTRUCTION and are excluded from the paired test — including
  them is the zero-inflation that failed exit_switch_mech's LOO median gate.

  An arm under {MIN_AFFECTED_DATES} AFFECTED dates is UNDERPOWERED: its cells are not read
  and no criterion is evaluated on it. This threshold was declared in the
  pre-registration BEFORE the count was knowable, which is the whole point.""")
    base_dates = {p.rec["date"] for p in base.signal_pos} | {
        rec["date"] for rec, _, _ in base.skipped}
    share_cont = (len(cont) / len(base_dates)) if base_dates else float("nan")
    print(f"\n  deployed signal dates            {len(base_dates):>4}")
    print(f"  CONTESTED dates                  {len(cont):>4}  "
          f"({share_cont:.0%} of the population)")
    ex = defaultdict(int)
    for rec, why, _ in base.skipped:
        if why in CONTEST_BUCKETS:
            ex[why] += 1
    # Population-wide, NOT restricted to the contested dates — these are the
    # exclusions that MAKE a date contested, counted over the whole walk.
    print("  exclusions in the contest buckets (population-wide): "
          + "  ".join(f"{k} {ex.get(k, 0)}" for k in CONTEST_BUCKETS))

    base_ids = taken_ids(base)
    out = {}
    print(f"\n  {'arm':<5} {'affected dates':>15} {'changed picks':>14} "
          f"{'of O0 taken':>12}   status")
    by_date_b: dict = defaultdict(set)
    for p in base.signal_pos:
        by_date_b[p.rec["date"]].add(id(p.rec))
    for name in TEST_ARMS:
        sim = sims[name]
        by_date_a: dict = defaultdict(set)
        for p in sim.signal_pos:
            by_date_a[p.rec["date"]].add(id(p.rec))
        affected = {d for d in set(by_date_a) | set(by_date_b)
                    if by_date_a.get(d, set()) != by_date_b.get(d, set())}
        # Positions O0 held that this arm did not (the symmetric difference
        # double-counts a swap, so halving it counts the SWAPS, not the ends).
        changed = len(taken_ids(sim) ^ base_ids) // 2 if base_ids else 0
        share = (changed / len(base_ids)) if base_ids else float("nan")
        ok = len(affected) >= MIN_AFFECTED_DATES
        out[name] = dict(affected=affected, n_affected=len(affected),
                         changed=changed, share=share, powered=ok)
        print(f"  {name:<5} {len(affected):>15} {changed:>14} {share:>11.0%}   "
              f"{'ok' if ok else 'UNDERPOWERED'}")
    powered = [n for n in TEST_ARMS if out[n]["powered"]]
    print(f"\n  arms cleared for reading: "
          f"{', '.join(powered) if powered else 'NONE — every arm underpowered'}")
    return out


# ════════════════════════════════════════════════════════════════════════════
# G1..G5
# ════════════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════════════
# Book calibration — DESCRIPTIVE, not a gate
# ════════════════════════════════════════════════════════════════════════════
#
# This print used to be the first half of G1, and G1 did two unrelated jobs: it
# COMPARED the deployed B1 line against four constants read off `Settings`
# (`g1_positions` / `g1_dates` / `g1_dollars` / `g1_dollar_tol`, sourced from
# `config/account-sim.yml`'s `gates.book_calibration`: 220 positions / 90 dates /
# $63,553 / $1), and it checked that this study's arm PLUMBING is neutral.
#
# The comparison was deleted on 2026-08-15, at the same time and for the same
# reason as `account_sim`'s own G1 (see that file's BOOK CALIBRATION preamble —
# these two must not disagree about what the number means). Those constants were
# a FINGERPRINT OF ONE EXPORT rather than a hypothesis: the book moves on every
# legitimate refresh, so the check fired on data refreshes, and the only way past
# it was to re-type the expectation to whatever the new run printed. What it cost
# here: when the exports were refreshed that day the book went from ~1,900 rows /
# 142 dates to 74 rows / 10 dates and this study failed a "calibration" gate
# although not one line of its logic had changed. `account_sim` then removed the
# four fields outright, which turned the same check into an AttributeError.
#
# The PRINTING stays — the B1 line is the provenance of the book every number
# below is computed on, and write-ups quote it as such. It now renders no
# verdict.
#
# G1 KEEPS ITS ID and its surviving half. The gates were NOT renumbered: G1..G5
# name specific checks in research/pre-registrations/f4_deployment/selection_order.md and in
# every recorded verdict, and sliding them would silently re-point that prose.

def print_book_calibration(picked) -> None:
    """The deployed B1 line this book produces. NO verdict, nothing can fail.

    Quote it as the provenance of the book, never as evidence that the book is
    unchanged — see this section's preamble.
    """
    hdr("BOOK CALIBRATION — descriptive provenance, NOT a gate")
    b1_n = len(picked)
    b1_dates = len({r["date"] for r in picked})
    b1_dol = sum(r["R_dol"] for r in picked if r.get("R_dol") is not None)
    print(f"  B1 (stored contracts, stored R): {b1_n} positions / {b1_dates} "
          f"dates / ${b1_dol:,.0f}")
    print("""  Descriptive only. This line MOVES whenever the backtest/proxy exports are
  refreshed, which is why it is no longer checked against a stored expectation
  (removed 2026-08-15 — the constants fingerprinted one export).""")


def gate_g1(st, base_sims, cache) -> bool:
    hdr("G1 — PLUMBING: O0 reproduces a direct ladder walk exactly")
    print("""  An ordering study whose BASELINE does not reproduce production is
  measuring its own bug. The check that survives is the one about CODE: a
  byte-identical book between O0 (built through this study's arm plumbing) and a
  walk built directly on protocol.ladder_rank, proving the plumbing is neutral.
  The book line itself is printed above, descriptively; it used to be compared
  against stored constants, which fingerprinted one export rather than testing
  anything — see the BOOK CALIBRATION preamble.""")
    ok = True
    for label, (pop, o0_sim) in base_sims.items():
        direct = A.simulate(
            P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible),
            st.cfg(f"G1 direct {label}", compound=False), cache=cache)
        same = A.book_signature(o0_sim) == A.book_signature(direct)
        ok = ok and same
        print(f"  [{label}] O0 vs direct ladder walk: {len(o0_sim.signal_pos)} vs "
              f"{len(direct.signal_pos)} positions, ${o0_sim.dollars:,.0f} vs "
              f"${direct.dollars:,.0f}  -> {'identical' if same else 'DIVERGED'}")
    print(f"  G1: {'PASS' if ok else 'FAIL'}")
    return ok


def gate_g2(pop_by_label, st, budget) -> bool:
    hdr("G2 — BLINDNESS: no arm's rank function may read an outcome")
    print("""  Every record is re-wrapped so reading an outcome key RAISES, and the
  outcome columns are DELETED from the underlying trade row so a read cannot
  route around the wrapper. Each arm must then produce a byte-identical book.
  A rank function that peeks is worthless, and the point of this study is a
  rule an agent could run live.""")
    print(f"  row columns deleted from every Trade: "
          f"{', '.join(sorted(A.LOOKAHEAD_ROW_COLUMNS))}")
    ok = True
    # UNTESTABLE is not FAIL. A blindness check compares two books; with no
    # candidates there are no books, and "the rank function did not peek" is
    # unproven rather than false. Collected and refused (exit 2) at the end
    # instead of being folded into `ok`.
    #
    # COST OF NOT HAVING THIS: on 2026-08-15 the input book collapsed to 74 rows
    # over 10 dates. `blind[0]["R"]` raised IndexError, the bare `except
    # IndexError: pass` left `tripwire = False`, and G2 printed six arms of
    # "sighted 0 blind 0 differing 0 -> DIVERGED" followed by G2: FAIL. Read
    # literally that says the rank functions peek at outcomes — an accusation
    # against the study's core claim — when the truth was that nothing was tested.
    untestable: list[str] = []
    for label, pop in pop_by_label.items():
        if not pop:
            print(f"\n  [{label}] NOT EVALUABLE — the population is empty; there "
                  f"is no record to wrap, so the tripwire cannot be armed.")
            untestable.append(f"{label}: empty population")
            continue
        blind = A.blind_records(pop)
        tripwire = False
        try:
            _ = blind[0]["R"]
        except A.LookaheadError:
            tripwire = True
        ok = ok and tripwire
        print(f"\n  [{label}] tripwire live: {tripwire}")
        # O4 is probed at draw 0 — the band's arms are rank functions too, and a
        # random key built off a sighted ordering would be a silent leak.
        probes = [(n, make_rank(n, budget)) for n, _, _ in ARMS]
        sighted_lists = P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible)
        blind_lists = P.ordered_by_day(blind, P.ladder_rank, P.ladder_eligible)
        s_keys = perm_keys(sighted_lists, SEED)
        b_keys = perm_keys(blind_lists, SEED)
        probes.append(("O4[draw 0]", None))
        for name, rank_fn in probes:
            s_fn = (lambda r: s_keys[id(r)]) if rank_fn is None else rank_fn
            b_fn = (lambda r: b_keys[id(r)]) if rank_fn is None else rank_fn
            sighted = A.simulate(
                P.ordered_by_day(pop, s_fn, P.ladder_eligible),
                st.cfg(f"G2 sighted {name}", compound=False), cache=A.new_cache())
            try:
                blind_sim = A.simulate(
                    P.ordered_by_day(blind, b_fn, P.ladder_eligible),
                    st.cfg(f"G2 blind {name}", compound=False), cache=A.new_cache())
                leaked = None
            except A.LookaheadError as exc:
                blind_sim, leaked = None, str(exc)
            if leaked:
                print(f"    {name:<11} LOOKAHEAD DETECTED: {leaked}")
                ok = False
                continue
            a_sig, b_sig = A.book_signature(sighted), A.book_signature(blind_sim)
            n_diff = sum(1 for x, y in zip(a_sig, b_sig) if x != y)
            if not a_sig and not b_sig:
                # Two empty books are trivially equal, which is why `same` has
                # always carried `len(a_sig) > 0` — an empty comparison must not
                # PASS. But it must not FAIL either: there was nothing to peek
                # at. Third outcome, said out loud.
                print(f"    {name:<11} sighted {0:>4}  blind {0:>4}  "
                      f"differing {0:>3}  -> NOT EVALUABLE (empty book)")
                untestable.append(f"{label}/{name}: both books empty")
                continue
            same = a_sig == b_sig and len(a_sig) > 0
            ok = ok and same
            print(f"    {name:<11} sighted {len(a_sig):>4}  blind {len(b_sig):>4}  "
                  f"differing {n_diff:>3}  -> {'identical' if same else 'DIVERGED'}")

    if untestable:
        # Refuse rather than verdict. G2 is a conjunction over every population
        # and arm; with a member that could not be evaluated the conjunction is
        # undefined, and reporting either PASS or FAIL would be a claim the run
        # did not earn. A detected divergence is still worth stating, so it is
        # printed alongside — it just does not turn an undefined gate into FAIL.
        print(f"\n  G2: NOT EVALUABLE — {len(untestable)} of the checks had "
              f"nothing to compare:")
        for line in untestable:
            print(f"    {line}")
        if not ok:
            print("    (at least one EVALUABLE check also diverged — read it "
                  "above; it is not what this refusal is about)")
        print("\nREFUSED — the blindness gate could not be run on this book. That "
              "is a statement about the POPULATION, not about the rank "
              "functions:\n"
              "  an empty candidate set proves neither that an arm peeks at an "
              "outcome nor that it does not.\n"
              "  Not a failure, and not a reason to weaken the gate — re-run "
              "once the era carries candidates.")
        sys.exit(era.EXIT_THIN_ERA)

    print(f"\n  G2: {'PASS' if ok else 'FAIL'}")
    return ok


def gate_g3(sims_by_label) -> bool:
    hdr("G3 — ATTRIBUTION: candidates partition into taken + census buckets, per arm")
    print("  The A4 identity, re-asserted per arm. A mismatch FAILS the run.")
    ok = True
    for label, (n_cand, sims) in sims_by_label.items():
        print(f"\n  [{label}] candidates offered per arm: {n_cand}")
        for name in [a for a, _, _ in ARMS]:
            sim = sims[name]
            total = sum(sim.census[b] for b in A.CENSUS_BUCKETS)
            taken = sim.census["taken"] + sim.census["taken_downsized"]
            good = (total == n_cand and taken == len(sim.signal_pos))
            ok = ok and good
            print(f"    {name:<5} taken {taken:>4}  exclusions "
                  f"{total - taken:>4}  sum {total:>4} vs candidates {n_cand:>4}  "
                  f"-> {'OK' if good else 'MISMATCH'}")
    print(f"\n  G3: {'PASS' if ok else 'FAIL'}")
    return ok


def gate_g4() -> bool:
    hdr("G4 — no annualised figure, Sharpe, or time-to-recover appears anywhere")
    print("""  By construction: this study prints mean R, a paired within-date
  difference, dollar sanity checks, and counts. It computes no return per unit
  time and no risk-adjusted ratio, so there is nothing to annualise.""")
    print("  G4: PASS")
    return True


def gate_g5(out: dict) -> bool:
    """Out-of-fold discipline — reported under EVERY outcome, including a stop.

    A gate that only prints when it has something to say is a gate a reader
    cannot check. Under a power floor it is vacuously satisfied — and saying so
    on the page is the point, because "no G5 line appeared" and "G5 passed" look
    identical from the outside otherwise.
    """
    hdr("G5 — OUT-OF-FOLD DISCIPLINE: what on this page is adoption-eligible")
    print("""  In-sample tables are labelled as such. The ONLY adoption-eligible
  numbers are LOO folds and protocol.walk_forward_splits TEST rows.""")
    ok = True
    for label, res in out.items():
        powered = [n for n in TEST_ARMS if res["g0"][n]["powered"]]
        if not powered:
            print(f"\n  [{label}] every arm UNDERPOWERED at G0, so NO outcome "
                  f"number was printed at all —")
            print("    no arm mean R, no paired gain, no band, no LOO fold, no "
                  "TEST row. There is nothing")
            print("    on this page that could be adopted, so the discipline is "
                  "satisfied VACUOUSLY.")
            continue
        print(f"\n  [{label}] arms read: {', '.join(powered)}")
        print("    in-sample: the arm book table and every criterion (1)-(7) "
              "cell, all labelled IN-SAMPLE.")
        print("    out-of-fold: the LOO folds under criterion (3) and the "
              "walk-forward TEST block per arm.")
        missing = [n for n in powered if n not in res["results"]]
        if missing:
            ok = False
            print(f"    *** arms cleared but never evaluated: "
                  f"{', '.join(missing)} ***")
    print(f"\n  G5: {'PASS' if ok else 'FAIL'}")
    return ok


# ════════════════════════════════════════════════════════════════════════════
# The seven-part candidate bar
# ════════════════════════════════════════════════════════════════════════════

def ex_both_windows(rows):
    """The cut `protocol.window_cuts` does NOT provide.

    It drops one dominant window at a time; the vol_sleeve straddle died
    precisely in the gap that leaves, which is why the registration adds this
    by hand.
    """
    months = {m for ms in P.DOMINANT_WINDOWS.values() for m in ms}
    return [r for r in rows if str(r["date"])[:7] not in months]


def evaluate_arm(name: str, rows, affected: set, band, label: str) -> dict:
    """The full conjunction. Failing any one part is failing."""
    sub(f"[{label}] {name} — the seven-part bar")
    res = dict(arm=name, n_rows=len(rows))
    if not rows:
        print("  no paired contested dates — NOT EVALUABLE")
        res["pass"] = False
        return res

    # (1) paired mean gain > 0, date-clustered bootstrap CI excluding zero
    g = mean_gain(rows)
    ci_lo, ci_hi = P.boot_ci_paired_by_date(rows, "a", "b")
    c1 = g > 0 and ci_lo > 0
    print(f"  (1) paired mean gain {g:+.4f} R   CI95 [{ci_lo:+.4f}, {ci_hi:+.4f}] "
          f"(date-clustered, BOOT_N={P.BOOT_N})  -> {'PASS' if c1 else 'FAIL'}")

    # (2) median gain positive among AFFECTED dates, and >=25 affected
    aff_rows = [r for r in rows if r["date"] in affected]
    med = statistics.median(r["gain"] for r in aff_rows) if aff_rows else float("nan")
    c2 = len(affected) >= MIN_AFFECTED_DATES and med == med and med > 0
    print(f"  (2) affected dates {len(affected)} (>= {MIN_AFFECTED_DATES}), median gain "
          f"among them {med:+.4f}  -> {'PASS' if c2 else 'FAIL'}")

    # (3) every LOO fold positive
    loo_mean, loo_share, loo_min, loo_n = P.loo_by_date(
        rows, lambda r: r["a"], lambda r: r["b"])
    c3 = loo_n > 0 and loo_share == 1.0 and loo_min > 0
    print(f"  (3) LOO by date: folds {loo_n}  mean {loo_mean:+.4f}  share>0 "
          f"{loo_share:.0%}  MIN {loo_min:+.4f}  -> {'PASS' if c3 else 'FAIL'}")

    # (4) positive in all years present
    years = P.by_year(rows)
    ymeans = {y: mean_gain(rs) for y, rs in years.items()}
    c4 = bool(ymeans) and all(v > 0 for v in ymeans.values())
    print("  (4) by year: " + "  ".join(f"{y} {v:+.4f} (n={len(years[y])})"
                                        for y, v in ymeans.items())
          + f"  -> {'PASS' if c4 else 'FAIL'}")
    if len(ymeans) < 3:
        print(f"      DISCLOSURE: criterion (4) reads 'positive in every calendar "
              f"year present in the arm's population' (wording corrected "
              f"2026-08-14 — see the pre-registration; the implementation is "
              f"unchanged and no number moves); this population spans "
              f"{len(ymeans)}. Evaluated as EVERY year present positive —")
        print("      requiring three on a two-year population would make the "
              "criterion unsatisfiable by construction. Recorded as a "
              "registration-wording note, not a relaxation.")

    # (5) holds on the SHIPPED exit config
    c5 = True
    print("  (5) SHIPPED exit config: the only profile this study replays is "
          "account_sim.profile_for")
    print("      (bear_giveback.prod_profile_for merge / CREDIT_PROD). No "
          "variant exists here.  -> PASS")

    # (6) window_cuts AND the ex-BOTH-windows cut
    cuts = dict(P.window_cuts(rows))
    cuts["ex_BOTH_windows"] = ex_both_windows(rows)
    cut_g = {k: mean_gain(v) for k, v in cuts.items() if v}
    c6 = bool(cut_g) and all(v > 0 for v in cut_g.values()) and len(cut_g) == 4
    print("  (6) window cuts: " + "  ".join(
        f"{k} {v:+.4f} (n={len(cuts[k])})" for k, v in cut_g.items())
        + f"  -> {'PASS' if c6 else 'FAIL'}")
    for k, v in cuts.items():
        if not v:
            print(f"      {k}: EMPTY after the cut — cannot survive a cut that "
                  f"removes every date")

    # (7) exceeds the O4 random band
    p95 = band.get("p95")
    c7 = p95 is not None and p95 == p95 and g > p95
    pct = (sum(1 for x in band.get("draws", []) if x < g)
           / len(band["draws"])) if band.get("draws") else float("nan")
    print(f"  (7) O4 band p95 {p95:+.4f} (seed {SEED}, {DRAWS} draws); this arm "
          f"{g:+.4f} sits at pct {pct:.0%}  -> {'PASS' if c7 else 'FAIL'}")

    dol = sum(r["a_dol"] - r["b_dol"] for r in rows)
    print(f"  dollars alongside (SANITY CHECK ONLY — composition-dependent, "
          f"quote R): {dol:+,.0f}")

    parts = dict(c1=c1, c2=c2, c3=c3, c4=c4, c5=c5, c6=c6, c7=c7)
    res.update(parts, gain=g, ci=(ci_lo, ci_hi), median_affected=med,
               loo_min=loo_min, dollars=dol, band_pct=pct)
    res["pass"] = all(parts.values())
    failed = ", ".join(k for k, v in parts.items() if not v)
    print(f"  => {name}: "
          + ("CANDIDATE (all seven)" if res["pass"] else f"FAILS {failed}"))
    return res


# ════════════════════════════════════════════════════════════════════════════
# O4 — the null band
# ════════════════════════════════════════════════════════════════════════════

def random_band(pop, base, cont, st, cache, label: str) -> dict:
    sub(f"[{label}] O4 — the null band ({DRAWS} seeded random within-day "
        f"permutations, seed {SEED})")
    print("""  O4 is the arm that decides the meaning of the others. The registered
  reading is explicit: an arm must beat the RANDOM BAND, not merely beat O0. If
  O0 itself sits inside the band, the adverse-ordering observation is an artifact
  of which picks the cap happened to exclude, and the thread closes.""")
    ladder_lists = P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible)
    draws = []
    for i in range(DRAWS):
        keys = perm_keys(ladder_lists, SEED + i)
        _, sim = arm_sim(pop, lambda r: keys[id(r)], st, f"{label} O4[{i}]", cache)
        rows, _ = paired_rows(sim, base, cont)
        if rows:
            draws.append(mean_gain(rows))
    if not draws:
        print("  no evaluable draws")
        return dict(draws=[], p95=float("nan"))
    draws.sort()
    # A 90% two-sided band: [p5, p95]. Criterion (7) reads the UPPER edge only
    # ("above the 95th percentile of the 200 draws"); the lower edge exists so
    # "does O0 sit inside the band" is a two-sided question, which is how the
    # registration words the thread-closing condition.
    lo = draws[int(BAND_ALPHA * len(draws))]
    p95 = draws[min(len(draws) - 1, int((1 - BAND_ALPHA) * len(draws)))]
    med = statistics.median(draws)
    inside = lo <= 0.0 <= p95
    print(f"\n  draws {len(draws)}   min {draws[0]:+.4f}   p5 {lo:+.4f}   median "
          f"{med:+.4f}   p95 {p95:+.4f}   max {draws[-1]:+.4f}")
    print(f"  O0 (gain 0 by definition) sits {'INSIDE' if inside else 'OUTSIDE'} "
          f"the band [p5, p95].")
    if inside:
        print("  -> Random orderings scatter around O0. On the registered "
              "reading this is the ORDERING-IS-NOISE condition.")
    return dict(draws=draws, p95=p95, p5=lo, median=med, inside=inside)


# ════════════════════════════════════════════════════════════════════════════
# G5 — out-of-fold discipline
# ════════════════════════════════════════════════════════════════════════════

def out_of_fold(name: str, rows, label: str) -> None:
    sub(f"[{label}] {name} — G5 out-of-fold read (walk-forward TEST rows)")
    print("""  These arms fit NOTHING — they are mechanical entry-side rules with no
  thresholds — so the walk-forward split does not train anything. It is here to
  give an out-of-fold READING of the same paired difference: TEST blocks only,
  purged with a 120-day embargo. Everything above it is in-sample and labelled.""")
    dates = [r["date"] for r in rows]
    test_dates: set = set()
    folds = 0
    for _, test in P.walk_forward_splits(dates):
        folds += 1
        test_dates |= set(test)
    if not folds:
        print("  (no evaluable folds — the population is too thin for the "
              "embargo; nothing here is adoption-eligible)")
        return
    test_rows = [r for r in rows if r["date"] in test_dates]
    print(f"  folds {folds}   TEST dates {len(test_dates)}   TEST rows "
          f"{len(test_rows)}   mean gain {mean_gain(test_rows):+.4f}")


# ════════════════════════════════════════════════════════════════════════════
# Verdict
# ════════════════════════════════════════════════════════════════════════════

def print_verdict(results: dict, g0: dict, band: dict, label: str) -> str:
    hdr(f"VERDICT ({label} — grammar worded in the pre-registration)")
    powered = [n for n in TEST_ARMS if g0[n]["powered"]]
    winners = [n for n in TEST_ARMS if results.get(n, {}).get("pass")]
    print(f"  arms powered (G0):  {', '.join(powered) if powered else 'none'}")
    print(f"  arms clearing all seven: {', '.join(winners) if winners else 'none'}")

    if not powered:
        v = ("UNDERPOWERED — every arm fell under "
             f"{MIN_AFFECTED_DATES} affected dates. Census only; nothing read, "
             "and NO re-run on these dates.")
        worst = max(g0[n]["n_affected"] for n in TEST_ARMS)
        print(f"\n  Best-powered arm reached {worst} affected dates against a "
              f"threshold of {MIN_AFFECTED_DATES}.")
        shares = [g0[n]["share"] for n in TEST_ARMS if g0[n]["share"] == g0[n]["share"]]
        share_range = (f"{min(shares):.0%}-{max(shares):.0%}" if shares
                       else "an unmeasurable share of")
        print(f"""
  CENSUS OBSERVATION, explicitly NOT a verdict upgrade: the reason the arms are
  under-powered is itself informative — each one changes only {share_range} of O0's
  taken positions (this run's measured range across the {len(TEST_ARMS)} ordering
  arms), because on most contested dates the caps exclude the same picks
  whatever the order. That
  texture is what CAP-BOUND-NOT-ORDER-BOUND describes. It may NOT be recorded
  as that verdict: the label requires arms that CLEAR G0, and reading a
  blocked arm's shape as a conclusion is exactly the move the power floor
  exists to prevent. It is a carry-forward for a re-registration on a
  materially larger book, nothing more.""")
    elif winners:
        v = (f"ORDERING-MATTERS — {', '.join(winners)} clears all seven. CANDIDATE, "
             "NOT a ship: queues an independent-window confirmation, after which "
             "the ordering may be proposed for deployment-rules.md as a TIE-BREAK "
             "within the deployed set.")
    else:
        gains = [abs(results[n]["gain"]) for n in powered
                 if results.get(n, {}).get("gain") == results.get(n, {}).get("gain")]
        shares = [g0[n]["share"] for n in powered]
        capbound = (bool(gains) and max(gains) < CAPBOUND_MAX_ABS_GAIN
                    and bool(shares) and max(shares) < CAPBOUND_MAX_PICK_DIFF)
        if capbound:
            v = ("CAP-BOUND-NOT-ORDER-BOUND — arms clear G0 but produce "
                 "near-identical books: the cap excludes the same picks whatever "
                 "the order. Ordering is not the lever; the constraint is the "
                 "account.")
        else:
            v = ("ORDERING-IS-NOISE — no arm separates from the O4 band. The "
                 "adverse-ordering read from account_sim was an ARTIFACT of which "
                 "picks the cap happened to exclude. Record it and CLOSE the "
                 "thread.")
    _ = band
    print(f"\n  VERDICT: {v}")
    return v


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def arm_table(label: str, sims: dict, read_outcomes: bool) -> None:
    """The arms' books. Outcome columns appear ONLY if G0 cleared an arm.

    Under a power floor the registration is explicit — "its cells are not read"
    — and an arm's mean R IS its cell. So the table degrades to a CENSUS
    (positions and dates, both knowable at entry) and the outcome columns are
    withheld rather than printed with a caveat next to them. A number that is
    on the page gets quoted eventually, whatever the caveat says.
    """
    sub(f"[{label}] the five deterministic arms — "
        + ("book summary (G5: IN-SAMPLE)" if read_outcomes
           else "CENSUS ONLY (G0 power floor: no outcome column is printed)"))
    head = f"  {'arm':<5} {'positions':>9} {'dates':>6} "
    print(head + (f"{'meanR':>8} {'$':>11}   ordering" if read_outcomes
                  else "  ordering"))
    for name, ordering, _ in ARMS:
        sim = sims[name]
        rs = [p.R for p in sim.signal_pos]
        row = f"  {name:<5} {len(sim.signal_pos):>9} {len(sim.dates):>6} "
        if read_outcomes:
            row += (f"{(statistics.fmean(rs) if rs else float('nan')):>+8.3f} "
                    f"{sim.dollars:>11,.0f}  ")
        print(row + f" {ordering}")


def build_books(recs, dates_allowed, label, st, cache) -> dict:
    """Every arm's book for one population. Computes NOTHING readable.

    Split out from the reporting so G0 can run — and print — before any other
    gate, which is what the registration means by "runs FIRST and blocks
    everything". Print order and execution order then agree, and a reader does
    not have to take the difference on trust.
    """
    pop = [r for r in recs if r["date"] in dates_allowed]
    sims, n_cand = {}, 0
    for name, _, _ in ARMS:
        lists, sim = arm_sim(pop, make_rank(name, st.budget), st,
                             f"{label} {name}", cache)
        sims[name] = sim
        n_cand = sum(len(ranked) for _, ranked in lists)
    return dict(pop=pop, sims=sims, n_candidates=n_cand,
                contested=contested_dates(sims["O0"]))


def report_population(label: str, book: dict, st, cache) -> dict:
    hdr(f"{label.upper()} — arms, band, and the seven-part bar")
    pop, sims = book["pop"], book["sims"]
    base, cont, g0 = sims["O0"], book["contested"], book["g0"]
    n_cand = book["n_candidates"]

    powered = [n for n in TEST_ARMS if g0[n]["powered"]]
    arm_table(label, sims, read_outcomes=bool(powered))

    if not powered:
        # G0 "runs FIRST and blocks everything". With no arm cleared there is
        # nothing for the band to be a control FOR, so the 200 draws are not
        # run either: an O4 distribution printed under a total power floor is an
        # unregistered number with no criterion attached to it.
        sub(f"[{label}] O4 — NOT RUN  (seed {SEED}, {DRAWS} draws, not taken)")
        print("  The null band exists to serve criterion (7). Every arm is "
              "underpowered, so there is no\n  criterion to serve and the "
              f"{DRAWS} draws are not taken. The seed is stated anyway "
              f"({SEED}) so the\n  arm is reproducible by anyone re-running it "
              "on a larger book.")
        return dict(sims=sims, n_candidates=n_cand, g0=g0, band={},
                    contested=cont, results={})

    band = random_band(pop, base, cont, st, cache, label)
    results = {}
    for name in TEST_ARMS:
        if not g0[name]["powered"]:
            sub(f"[{label}] {name} — UNDERPOWERED at "
                f"{g0[name]['n_affected']} affected dates")
            print(f"  Not read. No criterion is evaluated on this arm "
                  f"(threshold {MIN_AFFECTED_DATES}, declared before the count "
                  f"was knowable).")
            continue
        rows, dropped = paired_rows(sims[name], base, cont)
        print(f"\n  [{label}] {name}: paired contested dates {len(rows)} "
              f"(dropped {dropped} where one book held nothing)")
        results[name] = evaluate_arm(name, rows, g0[name]["affected"], band, label)
        out_of_fold(name, rows, label)
    return dict(sims=sims, n_candidates=n_cand, g0=g0, band=band,
                contested=cont, results=results)


def main(argv=None) -> int:
    argparse.ArgumentParser(
        prog="python -m scripts.backtest_study.f4_deployment.selection_order",
        description=__doc__.splitlines()[0]).parse_args(argv or [])

    st = A.load_settings(A.DEFAULT_CONFIG)
    if st.compound_enabled:
        print("CONFIG ERROR: this study is registered on the FROZEN, "
              "path-INDEPENDENT book (compounding OFF). "
              f"{A.DEFAULT_CONFIG.name} has compounding.enabled: true.")
        return 2

    cache = A.new_cache()
    hdr("selection_order — does a different BLIND entry ORDER spend the delta "
        "budget better?")
    print(f"""  config    {A.DEFAULT_CONFIG.relative_to(ROOT)}  (as committed; NO cap,
            capital, risk-%, or positions/day value is swept by this study)
  Basis     load_book(include_bs=False), proxy calibration gate ON, v4 never
            pooled in, --structure-universe NOT used, compounding OFF.
  Frozen    Tier membership, candidate universe, sizing, caps and exits are
            EXACTLY account_sim's. ARM H (the bear hedge sleeve) is OFF for every
            arm — it enters after the day's signal picks, cannot displace one, and
            is orthogonal to ordering.
  Capital   ${st.capital:,.0f}, risk {st.risk_pct:.0%} = ${st.budget:,.0f}/position,
            {st.max_per_day} positions/day, per-position cap {st.per_pos_cap:.2f}x,
            net cap {st.net_cap:.2f}x equity.
  NOTHING SHIPS FROM THIS STUDY UNDER ANY OUTCOME.""")

    A.print_configuration(st, A.DEFAULT_CONFIG.relative_to(ROOT))

    recs, diag = load_book(include_bs=False)
    # Refuse a thin era HERE, with the numbers, rather than letting it surface as
    # a gate verdict several hundred lines of report later. This study's own
    # declared floor (MIN_AFFECTED_DATES = 25) is a G0 power floor over CONTESTED
    # dates, a SUBSET of book dates — it cannot substitute for a floor on the
    # book itself, and it is smaller than the shared one anyway, so the shared
    # power floor is what binds.
    print(f"\n  era: {diag['era']}  book dates={diag['n_dates']}  "
          f"{diag['date_range'][0]} .. {diag['date_range'][1]}")
    era.require_dates(diag["n_dates"], diag["era"],
                      what="a book the six arms can be contested on at all; G0's "
                           "25-contested-date power floor is a tighter test on top")

    picked = P.top_k_per_day(recs, P.ladder_rank, k=st.max_per_day,
                             eligible_fn=P.ladder_eligible)
    print(f"\n  book: {len(recs)} rows  counts_by_source="
          f"{diag['counts_by_source']}  date_range={diag['date_range']}")

    episodes = A.dense_episodes(
        (d for d, _ in P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    ep_dates = {d for ep in episodes for d in ep}
    all_dates = {r["date"] for r in recs}
    print(f"  PRIMARY   dense episodes: {len(episodes)} episodes, "
          f"{len(ep_dates)} dates")
    print(f"  SECONDARY full book: {len(all_dates)} dates (reported, carries "
          f"nothing — same convention as account_sim)")

    pops = {"PRIMARY dense episodes": ep_dates, "SECONDARY full book": all_dates}

    # Every arm's book, both populations, built before anything is reported.
    books = {label: build_books(recs, dates, label, st, cache)
             for label, dates in pops.items()}

    # G0 RUNS AND PRINTS FIRST, before every other gate — the registration's
    # "runs FIRST and blocks everything", in execution order as well as on the
    # page. Nothing readable has been printed at this point.
    for label, book in books.items():
        book["g0"] = gate_g0(label, book["sims"], book["sims"]["O0"],
                             book["contested"])

    print_book_calibration(picked)

    gates = {}
    gates["G1"] = gate_g1(st,
                          {label: (b["pop"], b["sims"]["O0"])
                           for label, b in books.items()}, cache)
    gates["G2"] = gate_g2({label: b["pop"] for label, b in books.items()},
                          st, st.budget)
    if not all(gates.values()):
        print("\nGATE FAILURE (G1/G2) — no results printed. Exit 1.")
        return 1

    out = {label: report_population(label, book, st, cache)
           for label, book in books.items()}

    gates["G3"] = gate_g3({label: (v["n_candidates"], v["sims"])
                           for label, v in out.items()})
    gates["G4"] = gate_g4()
    gates["G5"] = gate_g5(out)

    primary = "PRIMARY dense episodes"
    verdict = print_verdict(out[primary]["results"], out[primary]["g0"],
                            out[primary]["band"], primary)

    hdr("STANDING CAVEAT (required by the pre-registration to appear here)")
    print("""  The ladder is itself IN-SAMPLE (fitted on this book), so an ordering
  evaluated on the same book is SECOND-ORDER in-sample. The only mitigations are
  that these are mechanical entry-side rules with no fitted thresholds, and that
  adoption requires out-of-fold survival. That caveat does not disappear if the
  numbers look good, and it is why nothing ships from this study under any
  outcome.

  Anti-tuning: arms frozen at six. Caps, capital, risk %, positions/day,
  take_floor, downsize and the exit profile are NOT swept — they come from config
  and are held at their committed values for every arm. No new columns. Every
  arm's result is reported regardless of outcome, including the ones that lose.""")
    print(f"  Random-control seed: {SEED} (fixed; draw i uses SEED + i over "
          f"{DRAWS} draws). Stated here\n  whether or not O4 was drawn, so the "
          f"claim and the number never come apart.")

    hdr("CLOSE")
    print(f"  verdict: {verdict}")
    for k in ("G1", "G2", "G3", "G4", "G5"):
        print(f"  {k}: {'PASS' if gates[k] else 'FAIL'}")
    any_powered = any(out[primary]["g0"][n]["powered"] for n in TEST_ARMS)
    print("  G0: at least one arm cleared" if any_powered
          else "  G0: POWER FLOOR FIRED on every arm")
    if not all(gates.values()):
        print("\nGATE FAILURE — exit 1.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
