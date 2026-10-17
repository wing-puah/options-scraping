# Pre-registrations

Each study has one pre-registration file: the question, frozen inputs,
criteria, and gates committed to **before** the study was built or run.
Each file is written to be read top to bottom by a person, and opens with
the study's latest outcome.

**The rule.** A pre-registration's commitments are immutable — no gate, bar,
arm definition, or verdict changes meaning after it is written.

**Current practice.** The file itself is not frozen prose: it is consolidated
so it reads as one final design rather than a change-log. A later
refinement — a ruling made, say, while the module was being built — is
folded into the section it amends, and what changed and when is not tracked
inline; that history lives in git instead. Pre-registrations deliberately do
NOT live in [`../current.md`](../current.md) (a rolling log pruned into
`../archive/`), because pruning one would destroy its evidentiary value.

**Tooling.** Files are grouped by study family, mirroring
`scripts/backtest_study/` and [`../study-results/`](../study-results/): a
study's registration lives in the same `fN_*` folder as its module.
`python -m scripts.study_review <study>` globs `<family>/<study>.md` and
hands the file, with its outcome block cut out, to the two independent analyst
agents plus validator,
who grade the study's run against what was committed here — see
[`../replication-protocol.md`](../replication-protocol.md).

## How this index works

This README is the **living index** over the immutable files: only the tables
below are kept current, as studies move through their lifecycle. **Status**
values:

- `draft` — not registered; every number, arm, gate and verdict may still be
  edited (the file's own first body line and `STATUS` line say so); becomes
  immutable in substance the moment the operator accepts it and stamps the
  registration date, at which point its status becomes `registered`
- `registered` — plan committed; module not yet written or not yet run
- `run` — the study has produced a report (see `../study-results/`)
- `graded` — a `study_review` A/B replication grading + digest exists
- `retracted` — a registered claim withdrawn before/without adoption (say why)

`accepted by default` after a status means the operator deferred and the
drafter's recommended defaults were accepted unreviewed.

**Latest outcome** is the verdict the study last printed, quoted verbatim, with
its date and a link to the record. The record is the study's file in
[`../study-results/`](../study-results/); a commitment's is
[`../current.md`](../current.md). The same line opens the file, inside its
outcome block. Nowhere else in a file may an outcome appear, because blind
graders read everything outside that block. When a study re-runs, update both
copies.
`graded` means a grading exists; it may predate the latest run.

## How a registration is structured

Every file follows one template:

- **Line 1** is a `## ` heading: the study slug, plus a short descriptive
  fragment only when there is a real one. `scripts/study_review/` extracts
  this line as the document's label, so never demote it or put anything
  above it.
- **The outcome block** comes next: the Latest outcome line, between
  `<!-- outcome:start -->` and `<!-- outcome:end -->`. `strip_outcome` in
  `scripts/study_review/core.py` cuts it before grading, and an unbalanced
  marker refuses the grading. `tests/test_study_review.py` checks every file:
  one block each, and no outcome in the graded text.
- **First line after the outcome block** reads `_Registered YYYY-MM-DD._` — the original
  commitment date, and the only date the file carries. A `draft` file's
  first body line reads `_Registered ____-__-__ (DRAFT — not registered;
  becomes immutable in substance when the operator accepts it)._` instead,
  with the file's own `**STATUS: DRAFT.**` sentence sitting directly below
  it. Acceptance fills in the date and drops the parenthetical, and the line
  then reads like every other registration's.
- **Sections**, each a `## ` heading at the same level as line 1, come in
  this order. A section is omitted, never left as an empty stub, when a study
  has nothing for it:
  1. The question
  2. What this study is not
  3. Definitions
  4. Dependencies
  5. Population and basis, fixed here
  6. Plan-time observations, disclosed
  7. What it compares (the arms: a table first, then one `###` per arm)
  8. How it is judged
  9. Gates
  10. Bar for a candidate
  11. Verdicts, worded now
  12. Anti-tuning
  13. What could ship

  A COMMITMENT rather than a study (`holdout_seal`, `programme_gate`,
  `rollback_triggers`, `v4_bridge`) keeps its own section list in plain
  words, still ending Verdicts → Anti-tuning → What could ship. Keep freezing
  words in headings ("fixed here", "worded now", "in order"): they tell the
  graders what is frozen.
- **No Build notes.** Implementation lives in the study module and in git. A
  build ruling that changes what a gate refuses, what an arm does or how a
  clause is read sits beside the text it amends, tagged
  `Resolved at build (date)`.

The unifying property: the same kind of content always has the same name and
relative position, not that every file has every section.

## Writing a registration

Adopted 2026-10-18, when all 41 files were rewritten to read top to bottom
and the separate plain-language briefs were retired. The reference file is
[`f2_management/exit_drawdown.md`](f2_management/exit_drawdown.md).

- **Plain words, exact commitments.** Follow
  [`../writing-guide.md`](../writing-guide.md), with ASD-STE100 Issue 9 as
  inspiration: sentences of 25 words or fewer where possible, active voice,
  condition first, one term per thing, tables for arms and verdicts, vertical
  lists for gates and bar clauses. `scripts/check_prose.py` skips this
  folder, so check by hand.
- **Every number, label, gate id, verdict token and quotation is exact.**
- **Dates stay on rules.** Each `Resolved at build (date)` tag, plan-time
  observation, pre-run expectation and dated wording correction stays beside
  the rule it belongs to.
- **Nothing added.** No unit, scope or summary statement the commitments do
  not make, and no "same as X's" cross-reference that is not registered.
- **A second reader fact-checks** any rewrite of a registered file, clause by
  clause against the committed text, before it is committed.

## Terminology legend

Every registration is a scientific pre-registration. Its recurring sections
map to standard experiment terms:

| Section in a registration | Experiment term |
|---|---|
| "Question" | Hypothesis |
| "Arms" (the study-local ARM labels) | Independent variables / treatment conditions |
| Null / random arm (e.g. a shuffle band) | Control group |
| "Population and basis, fixed here" | Sample, frozen up front against selection bias |
| "Unit and metric" | Outcome measure (dependent variable) |
| "Gates" (G0, G2, …) | Validity checks — exclusion and stopping criteria |
| "Bar for a candidate" | Pre-committed decision rule (significance criteria) |
| "Verdicts, worded now" | Pre-committed interpretations (anti-HARKing) |
| "Anti-tuning" | Anti-p-hacking: parameters frozen, no sweeping |
| "What this is NOT" | Scope limitations |
| "Ship criteria" (older files: "Ship ceiling") | Maximum admissible outcome — what, if anything, the study may cause to ship |
| Object-type tag after a label, e.g. `(control)` | Object type — [see arm-index.md](../arm-index.md#object-types) |

Verdict vocabulary, repo-wide (originally recorded in `financed_spread`'s
build-time notes, moved here): "POWER-STOPPED" is read as **UNDERPOWERED —
too few dates to judge; census printed, nothing concluded**. Existing printed
reports and registrations keep the original token for traceability; new code
prints UNDERPOWERED.

## Arm labels

An **ARM** is one independently-verdicted question inside a study; a study may
earn one verdict per arm. Arm labels are **study-local** — nothing defines them
globally, and single letters are deliberately kept: renaming one would break
the audit chain `scripts/study_review/` grades against. **Qualify every
citation with its study** — `emission_timing ARM P`, never a bare `ARM P` —
and look any label up in [`../arm-index.md`](../arm-index.md).

Not every label is an arm: the parenthesised tag in the index says which
object type it is, and a registration's "Arms" section may register
controls, cells and descriptive cuts under the same letters.

## ① Selection — `f1_selection/`

| File | Question | Status | Latest outcome |
|---|---|---|---|
| [`bear/bear_arm.md`](f1_selection/bear/bear_arm.md) | Does any subset of bear positions keep an edge (B1), and is the shipped exit mis-tuned for bears (B2)? | run | B1 `NOT met` (v3, v4); B2 `MET` on v3, shipped, reverted 2026-08-24; v4 B2 has flipped between runs — 2026-09-28 · [record](../study-results/f1_selection/bear/bear_arm.md) |
| [`benchmark/v4_bridge.md`](f1_selection/benchmark/v4_bridge.md) | Does trimming the analysis prompt change what kinds of plays the model emits, compared with v3? | run | `LADDER UNVALIDATED ON v4` — 2026-09-28 · [record](../study-results/f1_selection/benchmark/v4_bridge.md) |
| [`benchmark/mechanical_benchmark.md`](f1_selection/benchmark/mechanical_benchmark.md) | Does the book's selection, or a same-date mechanical bull call spread, carry the edge? | run · accepted by default | `ARM U NOT BUILT`; `ARM M1` meets `CONTRARY`, `ARM M2` does not; v3 awaits a fetch — 2026-10-15 · [record](../study-results/f1_selection/benchmark/mechanical_benchmark.md) |
| [`benchmark/spy_benchmark.md`](f1_selection/benchmark/spy_benchmark.md) | Do the deployed picks beat a SPY call spread on the same dates? Proposed post hoc. | run · accepted by default | `DOES-NOT-BEAT` — 2026-10-15 · [record](../study-results/f1_selection/benchmark/spy_benchmark.md) |
| [`benchmark/ticker_class.md`](f1_selection/benchmark/ticker_class.md) | Do index ETFs carry a more reliable edge than single stocks, with direction held fixed? | run | `P1 NULL`, secondaries `NULL`/`UNDERPOWERED`; PBO 0.367 (fragile); forward `STILL-OPEN` — 2026-10-07 · [record](../study-results/f1_selection/benchmark/ticker_class.md) |
| [`benchmark/ticker_class_regime.md`](f1_selection/benchmark/ticker_class_regime.md) | Does the index-versus-single-stock gap depend on the trend or volatility regime? Forward dates only. | draft | not run |
| [`regime/macro_event_study.md`](f1_selection/regime/macro_event_study.md) | Do macro events show up in entry IV, in P&L, or in exit timing? | graded | v4, not PRIMARY: `DE-QUEUED`; `X-C1 SURVIVAL-ARTIFACT` — 2026-09-28 · [study map](../study-map.md) |
| [`regime/dip_buy.md`](f1_selection/regime/dip_buy.md) | Do Tier A/B positions do better when SPY closed below its 50-day SMA? Picked post hoc, so graded forward only. | run · accepted by default | forward `STILL-OPEN` — 2026-10-12 · [record](../study-results/f1_selection/regime/dip_buy.md) |
| [`regime/adaptive_ladder.md`](f1_selection/regime/adaptive_ladder.md) | Does re-choosing among six fixed selection rules from trailing results beat the shipped ladder? | run · accepted by default | forward `STILL-OPEN` (in-sample `ADAPTS`) — 2026-10-12 · [record](../study-results/f1_selection/regime/adaptive_ladder.md) |
| [`regime/regime_map.md`](f1_selection/regime/regime_map.md) | In which market conditions does each ladder tier make or lose money? Descriptive. | run · accepted by default | v4: 2 `POSITIVE`, 1 `NEGATIVE`, 45 `NULL`; 2 Tier A cells `REPLICATED` on v3; forward `STILL-OPEN` — 2026-10-12 · [record](../study-results/f1_selection/regime/regime_map.md) |
| [`signal/ml_combination.md`](f1_selection/signal/ml_combination.md) | Does any learned combination of structure, regime, geometry and enrichment columns beat the shipped score-free ladder? | run | PRIMARY v3 `NULL RESULT` (2026-08-15); v4 `NULL RESULT` — 2026-09-28 · [record](../study-results/f1_selection/signal/ml_combination.md) |
| [`signal/emission_timing.md`](f1_selection/signal/emission_timing.md) | Does entering later than the signal date, or on a repeat signal, change the result? | graded | v4, not PRIMARY: `ARM P NULL`; `ARM L LAG-TOLERANT` — 2026-09-28 · [record](../study-results/f1_selection/signal/emission_timing.md) |
| [`signal/direction_hit.md`](f1_selection/signal/direction_hit.md) | Does anything known at entry predict the underlying moving the play's way? | run · accepted by default | `NULL`; forward `STILL-OPEN` — 2026-10-12 · [record](../study-results/f1_selection/signal/direction_hit.md) |
| [`signal/prompt_eval.md`](f1_selection/signal/prompt_eval.md) | Does a candidate analysis prompt beat the production prompt on the same dates? | run (variance floor only) | no candidate scored; variance floor 0.0419 R — 2026-09-04 · [record](../study-results/f1_selection/signal/prompt_eval.md) |
| [`signal/text_features.md`](f1_selection/signal/text_features.md) | Do features of the play text (trigger, invalidation) predict outcome? | run | 2 `CANDIDATE` (prompt-robustness, bear put spreads), 17 `NULL`, 9 `UNDERPOWERED`; no entry-gate candidate — 2026-09-28 · [record](../study-results/f1_selection/signal/text_features.md) |
| [`signal/trigger_entry.md`](f1_selection/signal/trigger_entry.md) | Does entering only after the play's trigger fires, at that session's close, help? | run | `LATE-ENTRY` at N=1, 3, 5 — 2026-09-28 · [record](../study-results/f1_selection/signal/trigger_entry.md) |

## ② Management — `f2_management/`

| File | Question | Status | Latest outcome |
|---|---|---|---|
| [`volume_signal.md`](f2_management/volume_signal.md) | Does underlying share volume condition exits, paths or selection within a structure? | run | PRIMARY v3 `NULL` (2026-08-15); v4 `NULL` — 2026-09-28 · [record](../study-results/f2_management/volume_signal.md) |
| [`staged_exit.md`](f2_management/staged_exit.md) | Does a day-X ±Y% staged exit beat the shipped exit? | graded | v4, not PRIMARY: `ARM E` X=5 `REACTIVE-AGAIN`; 39 `ARM T` cells `UNDERPOWERED`; no candidate — 2026-09-28 · [record](../study-results/f2_management/staged_exit.md) |
| [`rollback_triggers.md`](f2_management/rollback_triggers.md) | Have the shipped rules' rollback triggers fired? Census inside host studies. | run (via host studies) | `LVOL STAYS GATED`; `BEAR_HE UNDERPOWERED`; `be_after` `REVERT CONDITION FIRED` (already reverted); credit `sl-none` `NOT FIRED` — 2026-10-06 · [log](../current.md) |
| [`exit_from_text.md`](f2_management/exit_from_text.md) | Do the levels in the play text make better exits than the shipped rule? | run | 301 `UNDERPOWERED`, 18 `CONTRARY`, 17 `NULL`; no candidate — 2026-09-28 · [record](../study-results/f2_management/exit_from_text.md) |
| [`exit_drawdown.md`](f2_management/exit_drawdown.md) | Do walk-forward exit rules cut the account's mark-to-market drawdown? | graded | `ARM U` `REACTIVE-AGAIN` (both variants); `ARM O/vol NULL`; `ARM D SECONDARY-NULL`; others `UNDERPOWERED` — 2026-09-28 · [record](../study-results/f2_management/exit_drawdown.md) |
| [`cost_sensitivity.md`](f2_management/cost_sensitivity.md) | At what cost per leg does the Tier A/B edge vanish? | run · accepted by default | Tier A `VANISHES`; Tier B `VANISHES` — 2026-10-09 · [record](../study-results/f2_management/cost_sensitivity.md) |
| [`bear_fast_exit.md`](f2_management/bear_fast_exit.md) | Is a bear debit closed within a few sessions, or at a small profit, positive after costs? | run · accepted by default | `BLEED-CUT (C7 PENDING)` — 2026-10-10 · [record](../study-results/f2_management/bear_fast_exit.md) |

## ③ Structure — `f3_structure/`

| File | Question | Status | Latest outcome |
|---|---|---|---|
| [`financed_spread.md`](f3_structure/financed_spread.md) | Does financing a debit spread with a sold leg improve it? | graded | PRIMARY v3: `F4-d20 hold` `CANDIDATE`, other 12 `NULL` (2026-08-19); v4: all 13 `NULL` — 2026-09-28 · [record](../study-results/f3_structure/financed_spread.md) |
| [`ladder_overlay.md`](f3_structure/ladder_overlay.md) | Does selling and rolling shorter-dated calls against a bull call spread beat the shipped exits, and would a naked put beat both? | graded | all cells `NULL`; selling at entry loses (CI clear of zero) — 2026-09-28 · [record](../study-results/f3_structure/ladder_overlay.md) |
| [`index_vrp.md`](f3_structure/index_vrp.md) | Does a monthly short SPY iron condor lose in the same windows as the ladder book? | run · accepted by default | `NO-TAIL-LINK` — 2026-10-12 · [record](../study-results/f3_structure/index_vrp.md) |
| [`earnings_vol.md`](f3_structure/earnings_vol.md) | Does a long straddle or a calendar across earnings pay? | run · accepted by default | `ARM S NULL`; `ARM K NULL` (natural-fill secondary `CONTRARY`); forward `STILL-OPEN` — 2026-10-13 · [record](../study-results/f3_structure/earnings_vol.md) |

## ④ Deployment — `f4_deployment/`

| File | Question | Status | Latest outcome |
|---|---|---|---|
| [`account_sim.md`](f4_deployment/account_sim.md) | Is the ladder feasible on a $25,000 account under the exposure caps? | graded | `NOT FEASIBLE` (no capital rung passes A1 and A2) — 2026-09-28 · [record](../study-results/f4_deployment/account_sim.md) |
| [`selection_order.md`](f4_deployment/selection_order.md) | Does the order picks are taken within a day matter? | run | v3 book: `POWER-STOPPED` (2026-08-15); v4: `ORDERING-IS-NOISE` — 2026-09-28 · [record](../study-results/f4_deployment/selection_order.md) |
| [`portfolio_delta.md`](f4_deployment/portfolio_delta.md) | Do new positions do worse when the book already carries high net delta, and can ceilings or targets steer it? | graded | PRIMARY v3 `NOISE` (2026-08-19); SECONDARY v4 `DELTA-DOSE-RESPONSE` — 2026-09-28 · [record](../study-results/f4_deployment/portfolio_delta.md) |
| [`concurrency_correlation.md`](f4_deployment/concurrency_correlation.md) | Does the number of open positions, or their similarity, degrade a new position's outcome? | run | v4 `NOISE`, `X4` era check pending — 2026-09-28 · [record](../study-results/f4_deployment/concurrency_correlation.md) |
| [`narrow_to_fit.md`](f4_deployment/narrow_to_fit.md) | When one contract is over budget, does narrowing the spread beat refusing it? | run | $1,000 headline `NULL`; $500 secondary `NARROW-FEASIBLE`; stop-basis F1, F4 `NOT FEASIBLE` — 2026-10-10 · [record](../study-results/f4_deployment/narrow_to_fit.md) |
| [`refuse_floor_forward.md`](f4_deployment/refuse_floor_forward.md) | Standing forward grade of F2 and `(R, F3, $500)` from 2026-10-08, by confidence sequence. | run | both cells `STILL-OPEN` — 2026-10-10 · [record](../study-results/f4_deployment/refuse_floor_forward.md) |
| [`ruin_bound.md`](f4_deployment/ruin_bound.md) | Which cap cell earns most while ruin risk and drawdown stay under fixed bounds? | run · accepted by default | $500: `SAFEST ELIGIBLE CELL: N250-F2 G-none`; $1,000: `NO CELL MEETS THE BOUNDS` — 2026-10-10 · [record](../study-results/f4_deployment/ruin_bound.md) |
| [`holdout_seal.md`](f4_deployment/holdout_seal.md) | Commitment: seal signal dates from 2026-09-23 until 40 have priced, then one Tier A/B read. | registered · accepted by default | sealed; 0 of 40 priced on the exports (dated 2026-10-06) — census 2026-10-17 · [log](../current.md) |
| [`programme_gate.md`](f4_deployment/programme_gate.md) | Commitment: keep or retire the flow-selection layer on `mechanical_benchmark` and `dip_buy`. Backstop 2027-10-13. | registered · accepted by default | `WAIT` (`PG-M` `CONTRARY`, `PG-D` `STILL-OPEN`) — 2026-10-15 · [log](../current.md) |

## ⑤ Hedging — `f5_hedging/`

| File | Question | Status | Latest outcome |
|---|---|---|---|
| [`hedge_sizing.md`](f5_hedging/hedge_sizing.md) | Is a bear hedge sleeve deployable (D1–D4), and do the §4 card lines still stand on v4? | graded | D1–D4 all `NOT MET` — 2026-09-28 · [record](../study-results/f5_hedging/hedge_sizing.md) |
| [`hedge_structure.md`](f5_hedging/hedge_structure.md) | Does the calendar hedge survive a fixed pick rule, a fixed universe and a strict fill definition? | run | `H0 FILL NOT MET` (24.5% of dates fillable); `H2 NOT EVALUABLE` (n = 4) — 2026-09-28 · [record](../study-results/f5_hedging/hedge_structure.md) |
| [`hedge_timing.md`](f5_hedging/hedge_timing.md) | Does a mechanical trigger (chop, SPY gap-up, down-run) pick a day the hedge beats the long? | graded | `H3-GAP CONTRARY`; `H4-CHOP`, `H4-GAP`, `H4-DECLINE` `UNSTABLE`; 0 `TIMING-CANDIDATE` survivors — 2026-09-28 · [record](../study-results/f5_hedging/hedge_timing.md) |
| [`hedge_portfolio.md`](f5_hedging/hedge_portfolio.md) | When the book is concentrated in one cluster, does a put on its proxy cut drawdown? | graded | mechanism `UNDERPOWERED`; `ARM M MEASUREMENT-ONLY` — 2026-09-28 · [record](../study-results/f5_hedging/hedge_portfolio.md) |
| [`index_bear_hedge.md`](f5_hedging/index_bear_hedge.md) | Do SPY, QQQ and IWM bear spreads work as crash insurance on later sell-offs? | run · accepted by default | forward `STILL-OPEN`, 0 episodes graded — 2026-10-09 · [record](../study-results/f5_hedging/index_bear_hedge.md) |

`vol_sleeve` and `hedge_concentration` were deleted as modules on 2026-09-07 and their registrations and records on 2026-09-08 (held in git at `44bbfb2`); the DELETED rows in [`../study-map.md`](../study-map.md#hedging) are the record. `bear_deploy`, `calendar_hedge` and `hedge_exposure` were renamed `hedge_sizing`, `hedge_structure` and `hedge_portfolio` on 2026-09-08; each file's second line says so.