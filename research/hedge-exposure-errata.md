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
time, and emits no study-level verdict — and no VERDICT is written to
`catalog.py`, `study-map.md` or `research/study-results/` — until the operator
ratifies a reading. The earlier unilateral default to `--sources real` is
withdrawn.

**Amended 2026-08-31.** The clause above originally said nothing would be
*written* to `research/study-results/` at all. That folder is the append-only
archive of what each study last PRINTED, not a verdict store, and withholding
the run from it would have left no tracked record that this study ran at all.
The 2026-08-31 run IS recorded there; its excerpt quotes the
`NO STUDY-LEVEL VERDICT IS EMITTED` banner verbatim and its verdict field is
BLANK. `catalog.py` (`state="open"`) and `study-map.md` remain UNCONCLUDED,
which is what the clause was protecting.

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

---

# Independent audit, 2026-08-31 — fix plan F8–F16

Two independent audits ran after the F1–F7 pass (the two that were meant to run
during it died on a rate limit). Both confirm F1–F7 landed. Both confirm the
sector map is verbatim to the registration, that lookahead discipline is clean
(trigger, sizing, stratification and fill read entry-dated fields only), that no
study-level verdict word is emitted, and that the four unhedgeable clusters are
handled as both registrations commit.

The findings below are one family: **operationalizations the registration left
undefined, which the report does not disclose, and which feed the bar.** NONE of
them changed this run's outcome — every cell is NULL or UNDERPOWERED — but two
would decide a positive.

**F8 — the hedge instrument is fixed at the episode's FIRST session.**
`build_cell` reads `by_session[ep[0]]` and carries that cluster's proxy for the
whole episode; an episode whose FIRST session is unhedgeable is dropped whole.
The registration says "hedge on ANY session where concentration >= τ … a long
put on the concentrated cluster's proxy" — per session. Measured at τ=0.30:
**8 of 32 episodes rotate their top cluster mid-episode** (37 session-days
carried a put on a cluster that was not that session's top), and **2 of 32
episodes — 15 triggered sessions — are dropped although only their first session
was unhedgeable.** Same rule in ARM RF and in ARM N's shape.
*Fix:* re-pick the cluster and proxy each session within an episode; an
unhedgeable SESSION is carried at f=0 and stays in the denominator (the standing
`calendar_hedge` principle), never a dropped episode. Feeds all 7 clauses.

**F9 — the binding DIRECT/CONSTITUENT rule is printed, not enforced.**
All 9 cells and all 7 clauses run on the pooled all-strata trigger. Stratification
exists ONLY as a session/episode count table — no path metric, CI, ARM N band or
clause is ever computed per stratum. The registration: "Results are always
stratified DIRECT versus CONSTITUENT." The one powered τ=0.30 cell is 199/256
DIRECT; its NULL is a pooled number the report never labels as pooled.
*Fix:* compute and print every cell's path metrics and clause set per stratum as
well as pooled, and label the pooled row POOLED. A MECHANISM-FOUND under the
current build would have had no stratum to attach to — which is exactly what the
asymmetric reading rule exists to prevent.

**F10 — clause 6 is leave-one-LEG-out, not leave-one-DATE-out.** Folds are placed
legs (29 at τ=0.30, not 32 episodes and not 256 dates), so an episode that placed
nothing is not a fold. The registration words it as leave-one-date-out.
*Fix:* fold over trigger DATES. The report must also say what a fold is where it
prints "0/29 folds".

**F11 — directions are printed from UNDERPOWERED cells.** Signed `dMaxDD` /
`dUlcer` / `dTUW` are tabulated for cells the study has already power-stopped
(ARM C τ0.35/0.40 f1.00, every ARM CS cell, the ARM R/RF/B tables, the nearest-fill
sensitivity). The registration: "UNDERPOWERED — no direction is quoted, ever."
Mitigating: no clause, verdict or prose reads them, and each cell's own section
restates the rule. It is still a lean in print.
*Fix:* stamp every stat row belonging to an underpowered cell.

**F12 — G-MTM's degraded path is reachable and untested-around.**
`mtm_curve.book_curves` falls back to the caller's own `pos.dollars` when a record
carries neither `realized_pnl_abs` nor `R_dol` — the exact shape F2 removed. It is
safe today only because `book_positions` also fills `dollars` from `stored_booked`,
so both go None and the row fails closed; nothing enforces that. Worse, the G-MTM
block in `tests/test_mtm_curve.py` runs entirely on this fallback (its fake
position has no stored column), so the suite's most visible G-MTM tests exercise
the degraded comparison.
*Fix:* count degraded rows on `BookCurves` and print the count in `check_mtm`; the
report may not claim "two independent columns" while that count is non-zero.

**F13 — G-CENSUS's stated property is false as printed.** Its header claims the
census prints "before any outcome column is read", but G-MTM, `print_divergence`
and ARM M all print outcome-derived dollars above it. The census is COMPUTED from
entry-dated fields only — that part is true — and G-MTM must read stored outcomes
by construction.
*Fix:* say what is true (the census's INPUTS are entry-dated; the reconciliation
and the measurement print above it), rather than a claim about print order that
the code contradicts. G-CENSUS also has no failing path — it is a discipline, not
a check, and should say so.

**F14 — further unregistered choices feeding a clause, all undisclosed.** Add
each to the report's consolidated "not pre-registered" block:
- the session calendar is the SPY OHLC cache's dates — it defines the 504-session
  universe and therefore every episode and G-POWER;
- ARM N matches on count **plus episode lengths plus proxy mix** with uniform
  random starts; the registration commits only "COUNT and date-clustering". A
  richer match makes the null harder to beat, so it is conservative — but it is
  not what was committed. Keep it, label it, and print the committed-match null
  beside it as the registered estimator;
- the read metric silently defaults to ULCER when neither co-primary's CI excludes
  zero, and `CO_PRIMARIES` order breaks ties toward ulcer;
- `SETTLE_LOOKBACK_DAYS = 7` walk-back for the settlement spot, reported only as
  "against that day's close";
- `DIRECT_MAJORITY = 0.50`, which the code itself flags as not pre-registered and
  which the report never mentions.

**F15 — G-FILL's denominator is a different object from what the arms fill.** The
gate pairs are built from the per-session top proxy; the arms fill the
episode-first proxy (F8). At τ=0.30: gate 81.6% vs actual live-hedge session
coverage 85.5% at f=1.00. F8 makes the two the same object; if F8 is not taken,
this needs a disclosure line. (Distinct from the cache-conditioned denominator
already recorded above.)

**F16 — stale prose.** `research/arm-index.md` still says ARM M "is the only arm
that returned a finding" — no arm returned a finding in this run; that sentence
outlived the withdrawn first run. `mtm_curve.path_stats`'s docstring and
`study_map/catalog.py`'s INFRA note still say max drawdown comes from
`bear_deploy`, which F7 inverted. ARM M asserts "curves differ materially: YES"
off a **$1** threshold on a $21,890 drawdown — print the gap, not a boolean.
`tests/test_studies_hedge_exposure.py`'s ARM RF label test keys on there being
exactly one `note=` kwarg module-wide, so a second unlabelled ARM RF row would
leave it green; key it on the row label instead.

**Recorded, NOT fixed:** G-BLIND could not have caught a leak through
`realized_pnl_abs`/`daily_pnl_csv` (`account_sim`'s blinder does not strip them);
traced by hand — `session_concentration` reads only ticker/delta/contracts/
entry_underlying, so there is no leak, but the gate is weaker than it reads.
Tickers named in NO cluster (XLE itself, EWJ, ASHR, JD, XLU…) resolve to BROAD/SPY
as positions: faithful to the committed map's literal residual, but the "never
folded into BROAD" guarantee covers NAMED tickers only. 2024-01-10 is in the
504-session trigger universe but not on the 551-session MTM axis, so the two axes
are not nested (immaterial — it is an episode's opening session, which contributes
zero by construction).

---

# RATIFICATION — operator, 2026-08-31

**ERRATUM 1 is resolved. The ratified population is `all`: the literal
`load_book(include_bs=False)` call, 996 rows / 145 signal dates
(real 485 + tweak 511).**

**The operator's reasoning, recorded because it is the substantive argument and
it is not the one this file made.** A `tweak` row is a `strike_expiry_tweak`
substitution from `BacktestProxy` — a nearby strike/expiry standing in for a
contract the real backtest could not price. Those are REAL prices scraped from
Barchart, not model prices (`bs_options_hist` rows remain excluded by
`include_bs=False`, per the 2026-08-11 decision that they are replay-
contaminating). And the substitution is not only harmless here, it is
REPRESENTATIVE: the operator does not follow the proposed leg's strike and
expiry precisely at execution. A book that admits a nearby-strike substitution
is therefore a CLOSER model of the operator's real trading than one that
requires an exact contract match. Excluding those 511 rows would need a positive
reason, and there is none on the table.

This supersedes the argument this file previously leaned toward — that the
registration's plan-time disclosures (the exposure table, the concentration
quantiles, the 504-session universe) reproduce on `real` alone and so `real`
must be the disclosed population. That remains TRUE and is now a stated
limitation rather than a decision rule: **the registration's plan-time
observations describe the `real` stratum, not the ratified population.** A
reader must not take them as disclosures about the 996-row book. The
concentration quantiles, exposure shares and session universe under `all` are
printed by the run itself and are the figures that describe it.

**`real` is retained as a reported stratum, not a co-primary.** Both readings
print, as they have since F3; the verdict is read off `all`.

**Consequences, fixed by this decision and not chosen after seeing them.**

1. **The mechanism question is UNDERPOWERED.** All nine cells fail G-POWER
   under `all`. No direction is quoted from any of them, ever.
2. **ARM M returns MEASUREMENT-ONLY, and it is the sharper result.** Under
   `all` the two curves differ by far more than under `real`:

   | population | MTM maxDD | close maxDD | gap |
   |---|---|---|---|
   | `real` (stratum) | −$21,890 | −$22,592 | MTM better by $702 (3.1%) |
   | **`all` (ratified)** | **−$32,571** | **−$23,239** | **MTM worse by $9,332 (40.2%)** |

   The registration's own wording for MEASUREMENT-ONLY says it "would mean the
   programme's prior nulls were measured on a blind instrument without a hedge
   mechanism yet being found." On the ratified population that is exactly what
   ARM M shows: the close-bucketed curve understates this book's max drawdown
   by 40%.

**Both words are emitted, because they answer different questions and the
registration defines them over different objects.** UNDERPOWERED is defined by
G-POWER failing (the hedge cells); MEASUREMENT-ONLY is defined by ARM M
differing materially while no cell clears the bar (the measurement). ARM M is
not power-gated — it is the whole book over its full session axis and it gates
nothing — so it is powered when the cells are not. Emitting only UNDERPOWERED
would suppress a result the registration explicitly calls "a real, reportable
outcome"; emitting only MEASUREMENT-ONLY would imply the cells were read. The
registration does not order the two, and neither is weakened by the other.

**What this does NOT do.** It ships nothing. It does not close the queued
max-drawdown question — UNDERPOWERED leaves it open. It does not remove or
amend the §4 sleeve, which is operator policy. It does not overturn
`bear_deploy` D3, `calendar_hedge` H3 or `hedge_timing` H4: those verdicts
stand, but the MEASUREMENT-ONLY result means their curve understates drawdown
on this book, so the basis on which they were read is now a known limitation of
theirs and should be recorded against them.

The prose rule is unreachable (ERRATUM 2, ARM P inert), and ARM CS is
power-stopped at every τ under both readings, so PROSE-CONDITIONED,
LOOKAHEAD-UNRESOLVED does not arise.
