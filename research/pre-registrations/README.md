# Pre-registrations

One file per study, containing that study's pre-registration: the question,
frozen inputs, criteria, and gates committed to **before** the study was built
or run. The **commitments** are immutable — no gate, bar, arm definition, or
verdict changes meaning after it is written. The **file** is not frozen prose,
though: it is consolidated so it reads as one final design rather than a
change-log — a later refinement is folded into the section it amends, and what
changed and when is not tracked inline; that history lives in git. They
deliberately do NOT live in [`../current.md`](../current.md) (a rolling log
pruned into `../archive/`) — pruning a pre-registration would destroy its
evidentiary value.

Files are grouped by study family, mirroring `scripts/backtest_study/` and
[`../study-results/`](../study-results/): a study's registration lives in the
same `fN_*` folder as its module. `python -m scripts.study_review <study>`
globs `<family>/<study>.md` and hands the whole file to the two independent
analyst agents plus validator, who grade the study's run against what was
committed here — see [`../replication-protocol.md`](../replication-protocol.md).

## How this index works

This README is the **living index** over the immutable files: the tables below
(and only they) are kept current as studies move through their lifecycle.
**Status** values:

- `registered` — plan committed; module not yet written or not yet run
- `run` — the study has produced a report (see `../study-results/`)
- `graded` — a `study_review` A/B replication grading + digest exists
- `retracted` — a registered claim withdrawn before/without adoption (say why)

## How a registration is structured

Every file follows one template:

- **Line 1** is a `## ` heading: the study slug, plus a short descriptive
  fragment only when there is a real one (`scripts/study_review/` extracts this
  line as the document's label — never demote it or put anything above it).
- **First body line**: `_Registered YYYY-MM-DD._` — the original commitment
  date, and the only date the file carries.
- **Sections**, each a `## ` heading (the same level as line 1 — see
  [`f1_selection/bear_arm.md`](f1_selection/bear_arm.md) for the reference
  shape), in canonical order, each omitted when a study has nothing for it
  (never an empty stub): Question · What this is NOT · Population and basis,
  fixed here · Plan-time observations, disclosed · Arms · Unit and metric ·
  Gates · Bar for a candidate · Verdicts, worded now · Anti-tuning · Ship
  criteria · Build notes (the one section that is NOT part of the
  registration — implementation, not commitment). `### ` sub-headings are
  free inside a section (one per ARM, per gate group, …). Qualifiers that used
  to live in headings ("in order", "frozen at two") sit in the section's first
  sentence instead.
- **Wording** is plain English. The files were re-edited for readability on
  2026-08-31 with every number, ARM label, gate id, verdict token and
  quotation held verbatim (a mechanical diff enforced it); what a registration
  COMMITS did not change, only how it reads.

The unifying property is that the same kind of content always has the same
name and relative position — not that every file has every section.

## Terminology legend

Every registration is a scientific pre-registration; its recurring sections map
to standard experiment terminology:

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

Verdict vocabulary, repo-wide (registered in `financed_spread`'s build-time
notes, re-homed here): "POWER-STOPPED" is read as **UNDERPOWERED — too few
dates to judge; census printed, nothing concluded**. Existing printed reports
and registrations keep the original token for traceability; new code prints
UNDERPOWERED.

## Arm labels

An **ARM** is one independently-verdicted question inside a study; a study may
earn one verdict per arm. Arm labels are **study-local** — nothing defines them
globally, and single letters are deliberately kept: renaming one would break
the audit chain `scripts/study_review/` grades against. **Qualify every
citation with its study** — `emission_timing ARM P`, never a bare `ARM P` —
and look any label up in [`../arm-index.md`](../arm-index.md).

## ① Selection — `f1_selection/`

| File | Study | Status |
|---|---|---|
| [`f1_selection/bear_arm.md`](f1_selection/bear_arm.md) | `bear_arm` — B1/B2 carried over from `ml-plan.md` §Kickoff addendum (2026-08-11); B2's shipped exit was later reverted by its rollback trigger | run |
| [`f1_selection/macro_event_study.md`](f1_selection/macro_event_study.md) | `macro_event_study` | graded |
| [`f1_selection/ml_combination.md`](f1_selection/ml_combination.md) | `ml_combination` — ground rules + Phases 0–5 carried over from `ml-plan.md` (2026-08-11) | run |
| [`f1_selection/v4_bridge.md`](f1_selection/v4_bridge.md) | `v4_bridge` | run |
| [`f1_selection/emission_timing.md`](f1_selection/emission_timing.md) | `emission_timing` | graded |

## ② Management — `f2_management/`

| File | Study | Status |
|---|---|---|
| [`f2_management/volume_signal.md`](f2_management/volume_signal.md) | `volume_signal` | run |
| [`f2_management/staged_exit.md`](f2_management/staged_exit.md) | `staged_exit` | graded |
| [`f2_management/rollback_triggers.md`](f2_management/rollback_triggers.md) | rollback-trigger census — additive blocks in `exit_switch_mech_study` / `bear_arm` / `exit_mechanism_study --side credit` | run (via host studies) |
| [`f2_management/exit_drawdown.md`](f2_management/exit_drawdown.md) | `exit_drawdown` — **built 2026-09-05, not yet run to a recorded verdict** (registered 2026-09-05; the plan is committed before the code on purpose — see the file's own "What this is NOT" table for the eleven exit families it must not re-find). Walk-forward exit hypotheses judged on the ACCOUNT-level mark-to-market drawdown curve (`lib/mtm_curve.py`) rather than on per-row R. Five arms, labelled W (out-of-sample selection of the shipped pt/sl/tef knobs, with its own `PROD-ROBUST` token), U (underlying ATR stop on debit verticals), O (flow-unwind off the traded contract's OI path), P (partial scale-out), and D (a drawdown sizing throttle, labelled SECONDARY and unshippable from this family). Every threshold is fitted on TRAIN dates and applied to TEST dates; burn-in dates are excluded from the headline. Nothing ships — a candidate queues an independent window. | registered |

## ③ Structure — `f3_structure/`

| File | Study | Status |
|---|---|---|
| [`f3_structure/calendar_hedge.md`](f3_structure/calendar_hedge.md) | `calendar_hedge` | run |
| [`f3_structure/vol_sleeve.md`](f3_structure/vol_sleeve.md) | `vol_sleeve` | run |
| [`f3_structure/financed_spread.md`](f3_structure/financed_spread.md) | `financed_spread` | graded |

## ④ Deployment — `f4_deployment/`

| File | Study | Status |
|---|---|---|
| [`f4_deployment/account_sim.md`](f4_deployment/account_sim.md) | `account_sim` | graded |
| [`f4_deployment/selection_order.md`](f4_deployment/selection_order.md) | `selection_order` | run |
| [`f4_deployment/portfolio_delta.md`](f4_deployment/portfolio_delta.md) | `portfolio_delta` | graded |
| [`f4_deployment/bear_deploy.md`](f4_deployment/bear_deploy.md) | `bear_deploy` — original D-rules carried over from `ml-plan.md` §addendum 2 + the 2026-08-24 v4 re-read (card-line decision rules; sleeve itself operator-policy, exempt) | graded |
| [`f4_deployment/concurrency_correlation.md`](f4_deployment/concurrency_correlation.md) | `concurrency_correlation` — **module NOT yet written** (registered 2026-08-22; the plan exists before the code on purpose — see the file's own "dead ends" table for the v3 cuts it must not re-find) | registered |
| [`f4_deployment/hedge_timing.md`](f4_deployment/hedge_timing.md) | `hedge_timing` — registered 2026-08-28, run and graded same day (era v4 + v3 replication). Does a mechanical trigger — chop, SPY gap-up, a 4–5-day down-run — pick a day the bear hedge beats the same day's ladder-eligible long? GAP-UP came back CONTRARY (hedge worse than the long, both money arms) — §4 prohibition drafted and HELD; chop and the broad decline NULL; the strict streak UNDERPOWERED as fixed in advance (2 book dates). | graded |
| [`f4_deployment/hedge_exposure.md`](f4_deployment/hedge_exposure.md) | `hedge_exposure` — registered 2026-08-29, built, run and graded 2026-08-31 (era v4). The operator's queued max-drawdown question, scoped to their practice: when the open book is concentrated in one correlated cluster, does a long put on that cluster's proxy cut the book's MARK-TO-MARKET drawdown versus the same book unhedged? The registration's population clause was originally self-contradictory; the operator ratified `all` (996 rows / 145 dates), consolidated into this file's own §Population and basis on 2026-09-02. Result: the mechanism question is UNDERPOWERED (all nine cells), ARM M is MEASUREMENT-ONLY (the close-bucketed curve understates this book's max drawdown by 40.2%). Nothing ships; the question stays open. | graded |
| [`f4_deployment/hedge_concentration.md`](f4_deployment/hedge_concentration.md) | `hedge_concentration` (registered 2026-08-31, first run 2026-08-31). The "third reading" `hedge_exposure`'s errata named: the ratified population thinned to what `account_sim` ADMITS (top-3/day, caps, ARM H off), 221 of 458 ladder-eligible rows on the 2026-08-27 exports. Stage 1 asks the precondition every hedge verdict has assumed — does open-book concentration PREDICT forward mark-to-market drawdown? (ARM K, against a circular-shift null and a gross-exposure control); Stage 2, the τ×f proxy-put grid, runs only on PRECONDITION-FOUND and is disclosed at plan time as expected UNDERPOWERED (episodes peak at 20 < 25). Every outcome has a Ship-criteria branch that moves `next-steps.md` §2.1 out of "open". **Ran 2026-08-31 (era v4): Stage 1 PRECONDITION-NULL on a POWERED read (G-POWER-K PASS, terciles [162, 166, 152] over 3 dense episodes) — concentration carries no information about the admitted book's forward drawdown, so Stage 2 did NOT run and no cell was evaluated.** | run |
