# `hedge_exposure` — errata and fix plan

_Opened 2026-08-29, after the first build and its three-lens audit._

The pre-registration
(`research/pre-registrations/f4_deployment/hedge_exposure.md`, committed
`665956d`) is IMMUTABLE. Two defects in it were found only after commit. Per
the repo's rule that a commitment never changes meaning after it is written,
they are recorded here as ERRATA rather than edited into that file. Neither
erratum changes a gate, bar, arm definition or verdict — each records that a
committed clause is defective and states how the build resolved it, so a later
reader is not misled by the registration's own words.

**No result from this study may be recorded until every item below is closed.**
The first run produced a verdict, a `catalog.py` entry and a `study-map.md`
line; none of them has a `research/study-results/` record behind it and none is
ratified.

---

## ERRATUM 1 — the population clause is self-contradictory

The registration's "Population and basis, fixed here" says BOTH:

- *"`load_book(include_bs=False)` — real and `strike_expiry_tweak` pricing"*, and
- *"**Book**: 485 rows / 140 signal dates / 2024-01-10 .. 2025-11-04"*

These are different populations. Verified on this checkout: the literal call
returns **996 records / 145 dates**, split `real` 485 / `tweak` 511. The 485/140
figure is the RAW `analysis - BacktestResults.csv` export, which is what every
plan-time observation in the registration was computed on — the exposure table,
the concentration quantiles (median 0.301 / p75 0.398 / p90 0.572) and the
504-session universe all reproduce on the `real` stratum alone and on no other
reading.

**This is load-bearing, not cosmetic.** Under `real`: 3 of 9 cells powered,
verdict MEASUREMENT-ONLY. Under the literal call: **all 9 cells UNDERPOWERED**,
the study concludes nothing. The population choice, not the data, decides what
enters the evidence base.

**Resolution (operator, 2026-08-29): report BOTH, conclude from NEITHER until
one is ratified.** The study prints gates, cell shape and verdicts under both
populations in one report, labels each with its row/date counts computed at run
time, and emits no study-level verdict — and nothing is written to
`catalog.py`, `study-map.md` or `research/study-results/` — until the operator
ratifies a reading. The earlier unilateral default to `--sources real` is
withdrawn.

## ERRATUM 2 — ARM P is degenerate as worded

The registration defines ARM P as *"ARM C restricted to exactly the sessions
ARM CS would hedge on, minus the prose condition"*. Restricting to CS's session
set and then removing the prose condition yields CS's session set. The build
implemented it literally (`p_trig = list(cs_trig)`), so ARM P and ARM CS carry
byte-identical hedges and differ only in what is claimed to justify them.

**Consequence:** the study's ONLY control on the irreducible model-recall
lookahead disclosed in the registration does not exist, and the binding prose
rule (*"no verdict may rest on ARM CS alone"* → `PROSE-CONDITIONED,
LOOKAHEAD-UNRESOLVED`) is unreachable by construction. It does not bite this run
— ARM CS is power-stopped at 7/6/4 sessions — but it would on a powered window.

**Resolution: ARM P is declared INERT AS REGISTERED.** The report must say so
wherever ARM P appears. It may NOT be silently redefined into something
informative — that would be a post-hoc arm. A corrected control (e.g. ARM C on
concentration-matched sessions that carry NO hedge-pressure signal) requires its
own registration and is out of scope here.

---

## Fix plan

Ordered. Each item states its acceptance criterion. `harness.py` stays frozen
throughout; no committed constant (sector map, tau grid, f grid, hedge-pressure
cut, fill rules, >=60% fill gate, >=25 date floor, Bonferroni 0.05/9) may move.

**F1 — CONTRARY must carry the same clause set as a positive.** *(critical)*
`hedge_exposure.py:1159` emits CONTRARY from
`hedged.max_dd < base.max_dd and point < 0` — no CI, no ARM N band, no year
sign, no ex-window cut, no leave-one-out fold. A positive needs all 7 clauses;
a negative currently needs none, and a cell-level CONTRARY escalates to the
study-level verdict (`:1222`). At tau 0.30 / f 0.25 the cell sits at dMaxDD
+$26, i.e. $26 of noise from printing CONTRARY.
*Accept:* CONTRARY requires clause 2 with the sign inverted (co-primary CI
entirely below zero at alpha = 0.05/9), worse than ARM N's 5th percentile, and
sign-stability on clauses 4-6; otherwise fall through to NULL. Table-driven test
per clause.

**F2 — G-MTM must reconcile against the STORED outcome, not itself.** *(critical)*
`book_positions` (`hedge_exposure.py:163`) takes `days_held` AND `dollars` from
one `A.replay_sized(...)`; `mtm_curve.book_curves` (`mtm_curve.py:284`) then
compares the MTM level indexed by that `days_held` against that same `dollars`.
Both sides are one replay, which is why it passes 485/485 at $0.0000. The
registration asks for reconciliation against the booked realized P&L.
*Accept:* reconcile `mtm_at_exit` against the row's stored `R_dol`; report as a
separate disclosed figure the count of rows whose replayed exit differs from the
stored one (measured: 12/485 on `days_held`, 13 on `exit_reason`, $947 on
$33,697). The gate must be able to fail; prove it with a test that makes it fail.

**F3 — report both populations, emit no verdict.** *(critical, per ERRATUM 1)*
*Accept:* one report, both populations, every count computed at run time (no
asserted "485 / 140" string), no study-level verdict, and the `catalog.py` /
`study-map.md` entries reverted to an unconcluded state.

**F4 — label ARM RF, and print ARM R's registered caveat.** *(critical)*
ARM RF (`hedge_exposure.py:378`) is not in the registration and prints the
largest positive numbers in the report (dMaxDD up to +$3,202, total $43,165 vs
$34,644 unhedged) with no prose. `study_review` and any paste-the-report path
read the report, not `arm-index.md`.
*Accept:* every ARM RF row carries `UNREGISTERED — ADDED AFTER COMMIT`, and
ARM R's committed caveat (*"a floor on feasibility, not a recommendation ... not
an instrument the operator trades"*) is printed immediately above its rows.

**F5 — replace the month-shuffle bootstrap.** *(major)*
`boot_ci` (`hedge_exposure.py:476`) resamples calendar months with replacement
and concatenates them in drawn order, then computes PATH-DEPENDENT statistics
(max drawdown, Ulcer, TUW) on the reordered series — month order is part of the
statistic, so the interval is not that statistic's sampling distribution
(observed: ulcer improvement +0.1092, CI [-8.6955, +8.9270]). Clause 2 is the
only clause failing in every powered cell.
*Accept:* a chronological moving-block bootstrap, or `protocol`'s existing
date-clustered helpers where they apply; and either way a report line stating
whether clause 2's failure survives the change.

**F6 — ARM P declared inert in-report.** *(major, per ERRATUM 2)*
*Accept:* the report states ARM P is inert as registered and that the prose rule
is unreachable, in those words. No redefinition.

**F7 — fix the layering inversion.** *(major)*
`lib/mtm_curve.py:77` imports `max_drawdown` from
`f4_deployment/bear_deploy` at module level — a `lib/` module executing an f4
study on import. `greeks.py:8`, `sectors.py:35` and `hedge_instrument.py:44`
each state and honour the opposite rule.
*Accept:* `max_drawdown` moves into `lib/` (mtm_curve.py already owns the path
statistics) and `bear_deploy` imports it from there. One implementation, correct
direction. `bear_deploy`'s own results must be unchanged — verify by re-running it.

### Also recorded, not fixed here

- **ARM CS reads the analysis dated D to hedge at D's close**, one session
  earlier than the repo's next-day entry convention; `blind_trigger_check()`
  never exercises the hedge-pressure path, so G-BLIND cannot see it. Low impact
  now (ARM CS carries no verdict at any tau), real on a forward window.
- **The `days_held` calendar-vs-trading reading moves the trigger.** Calendar
  (committed) gives 504 sessions / 3 powered cells; the field's trading-day
  semantics give 529 and ALL NINE cells UNDERPOWERED. The committed reading is
  the one under which anything is powered. `holding_disagreement()` prints only
  the two session counts — it should print per-tau triggered and episode counts
  under both.
- **G-FILL's denominator is cache-conditioned.** `_put_index` builds the
  instrument universe from `option_history_cache/`, i.e. contracts the BOOK
  traded. The 81.6% / 83.8% / 88.3% band rates measure cache coverage, not
  market liquidity, and would move on a re-scrape. Needs a disclosure line.
- **ARM B runs a $500 stop against a book replayed at `MAX_LOSS_ABS` ($1,000)**
  — not the like-for-like comparison the registration describes.
- **The baseline is not the object the study was queued against.** maxDD
  -$22,473 here is the whole book at its own contract counts; the operator's
  queued -$10,968 is `account_sim`'s admitted subset. The two are not comparable
  and the report must not imply they are.
- **ARM M is weaker than the design memo argued.** MTM vs close-bucketed:
  maxDD -$22,473 vs -$22,781, ulcer 17.19% vs 16.75%, TUW 93.3% vs 91.1%. The
  curves differ, but by ~1.4% and with the MTM curve slightly BETTER on max
  drawdown. The 2026-08-29 design-notes claim that the close-bucketed measure is
  structurally blind to hedging is NOT carried by this evidence and should not
  be repeated without it.
