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
- **Sections**, in canonical order, each omitted when a study has nothing for
  it (never an empty stub): Question · What this is NOT · Population and
  basis, fixed here · Plan-time observations, disclosed · Arms · Unit and
  metric · Gates · Bar for a candidate · Verdicts, worded now · Anti-tuning ·
  Ship criteria · Build notes (the one section that is NOT part of the
  registration — implementation, not commitment).

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
| [`f4_deployment/hedge_timing.md`](f4_deployment/hedge_timing.md) | `hedge_timing` — registered 2026-08-28, module written, **not yet run** (registration committed before the first run on purpose). Does a mechanical trigger — chop, SPY gap-up, a 4–5-day down-run — pick a day the bear hedge beats the same day's ladder-eligible long? The strict streak arm is fixed UNDERPOWERED in advance: the book samples 2 such days. | registered |
