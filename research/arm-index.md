# ARM index — every label that looks like an arm, and what it actually is

**One rule, and every confusion below follows from it: a label is study-local.**
`ARM P` is not an identifier — `emission_timing ARM P` is. Nothing defines
labels globally, and that is by design, not an oversight: an arm belongs to the
study that registered it. The cost is that the same letter means four different
things four studies over, and a bare `grep "ARM P"` returns ~200 hits, most of
them one study *citing* another's arm.

This file is the one place every such label is written down, organised BY
STUDY so everything a study owns sits together. **Citing an arm outside its
own study, always qualify it with the study** — `emission_timing ARM P`, never
a bare `ARM P`.

<a id="object-types"></a>
## Object types

Not every label below is an arm. The index uses twelve object types, and
"arm" stops being the catch-all noun for anything carrying a study-local
letter. The table gives each type's meaning and whether it earns its own
verdict.

| Object type | What it is | Graded? | Example |
|---|---|---|---|
| arm | one independently-verdicted question inside a study | own verdict | `exit_drawdown ARM U` |
| sub-arm | a named half or setting of one arm (other prose may call it a variant) | with its parent, never alone | `exit_drawdown ARM U/a` |
| cell | one parameter combination inside an arm | only as part of its arm's verdict | `financed_spread F4` |
| control | a comparator candidates are read against, not a candidate itself | no verdict of its own | `trigger_entry ARM L` |
| descriptive cut | a reported observation, disclosed but not graded | no | `next_day_move ARM D` |
| population scope | the same design run on a subset of the book | its arms are graded on that subset | `hedge_portfolio --admitted` |
| run | an alternative RUN of one study, usually a CLI flag, not a separate question | the run's arms are | `account_sim --compounding` |
| gate | a hard pass/fail precondition checked before any result prints | pass/fail, then stop | `account_sim G2` |
| criterion | a pre-registered numeric bar, MET / NOT MET once gates pass | MET / NOT MET | `hedge_sizing D2` |
| hypothesis | a pre-registered claim, here always also an arm under another letter | as its arm | `macro_event_study H1` |
| prose | printed report text or a code comment that only reads like a label | no | `ARM VERDICT` |
| axis | a dimension that composes cells, only in `ladder_overlay`, not itself graded | no | `ladder_overlay T0` |

Every label bullet below carries its object type in parentheses right after
the label and before the dash. A bare grep for a letter tells you nothing
until you read that tag.

See [`glossary.md`](glossary.md) §9 for the verdict grammar arms are graded
under.

## Collisions, up front

- **`P`** — **six** arms: `emission_timing`, `macro_event_study`,
  `bear_giveback`, `bear_rewrap`, `hedge_portfolio`, `exit_drawdown` — plus
  `P1`/`P2` sub-parts in `bear_rewrap` (the arm's own two halves) and
  `hedge_structure` (an unrelated `P1`, the hedge sleeve itself).
- **`D`** — **four** arms (`portfolio_delta`, `next_day_move`, `account_sim`,
  `trigger_entry`) — and `hedge_sizing`'s `D1`–`D5`, which are criteria, not
  `ARM D`.
- **`T`** — **three** arms: `staged_exit` (tighten / arm-trail, a fork of the
  replay engine), `trigger_entry` (trigger-gated ENTRY) and
  `mechanical_benchmark` (the deployed picks themselves, a reference arm).
  Opposite ends of the system and nothing alike.
- **`X`** — two arms: `macro_event_study` (the exit census, descriptive) and
  `mechanical_benchmark`'s sibling draft `cost_sensitivity` (the registered
  cost point, the one arm it grades on). One is a census, the other is the
  whole verdict.
- **`U`** — **three** arms: `bear_giveback` (the underlying's price path),
  `exit_drawdown` (the underlying ATR stop) and `mechanical_benchmark` (the
  random-universe base-rate null). Nothing alike beyond the letter.
- **`L`** — two arms: `emission_timing` (fill lag) and `trigger_entry` (the
  unconditional-lag control, deliberately matched to it).
- **`H`** — two arms (`account_sim`, `hedge_structure`). It also labels
  `H1`–`H4` hypotheses in `macro_event_study` and `H0`–`H5` criteria in
  `hedge_structure`, which *also* has its own `ARM H` — unrelated to its
  criteria of the same letter. It further labels `H0`–`H4` arms in
  `hedge_timing`, neither of those: there they are the census plus four
  hypotheses, each run once per trigger family and suffixed with it
  (`ARM H3-CHOP`).
- **`B1` / `B2`** — `bear_arm`'s two criteria (selection conditioning, exit
  fit) vs `ml_combination`'s two regression baselines. Same document
  registered both on 2026-08-11, and they mean nothing alike.
- **`F1` / `F2`** — `financed_spread`'s financing structures vs
  `account_sim`'s 1-contract-floor question. Unrelated.
- **`C`** — **six** arms (`text_features`, `next_day_move`, `hedge_portfolio`,
  `concurrency_correlation`, `hedge_concentration`, `trigger_entry`). **`N` `R`**
  — two arms each, different studies.
- **`S`** — `ARM S` in two studies (`hedge_structure`, `bear_giveback`) vs
  `hedge_structure`'s own `S1`–`S6` sub-arms vs the printed prose
  `ARM SELECTION`.
- **`E1` / `E2` / `E3`** — two studies: `exit_from_text` (arms —
  invalidation-as-stop, trigger-as-entry-filter, horizon-as-time-exit) vs
  `ladder_overlay` (gates — Δ(net delta), Δ(net vega), sleeve correlation).
  Nothing alike beyond the letter.
- **Gates: `G0` `G1` `G2` `G3` `G4` `G5` `G6`** — hard pass/fail
  preconditions checked before any result prints ([`glossary.md`](glossary.md)
  §9). Every study numbers its OWN from scratch, so `G2` in two studies is
  two unrelated checks — not indexed per-study below. Numbers are never
  reused after a gate is retired — `account_sim` runs G2–G5 because its G1
  went in 2026-08-15, and the survivors were deliberately NOT renumbered.

## The index, by study

Grouped in `scripts/backtest_study/` family order (①–⑤), alphabetical within
a family, then the studies still queued with no module yet. A bullet that
DEFINES a label starts with the backticked label; cross-references to other
studies' labels appear mid-prose only.

### ① Selection — what to trade

#### `bear_arm`

_Registered in [`pre-registrations/f1_selection/bear_arm.md`](pre-registrations/f1_selection/bear_arm.md) · module `f1_selection/bear_arm.py`_

- `B1` `B2` (criterion) — Bear criteria, not arms and not
  `ml_combination`'s baselines of the same letters below. Selection
  conditioning is `B1`: is there a bear subset, definable at decision time,
  that is not negative. Exit fit is `B2`: is PROD mis-tuned for bear rows.
  This `B2` shipped `be_after: 0.50` in 2026-08-11, and its own rollback
  trigger reverted it on 2026-08-24.

#### `emission_timing`

_Registered in [`pre-registrations/f1_selection/emission_timing.md`](pre-registrations/f1_selection/emission_timing.md)_

- `ARM L` (arm) — Fill lag — does an entry filled 1, 2 or 3 sessions after
  the signal lose the edge?
- `ARM P` (arm) <a id="emission_timing-arm-p"></a> — Persistence — does a
  re-emitted play (2nd/3rd/4th+ of a ticker+structure) perform worse than
  the first emission? One of `ARM P`'s six owners repo-wide (see
  Collisions, above).

#### `text_features`

_Registered in [`pre-registrations/f1_selection/text_features.md`](pre-registrations/f1_selection/text_features.md) · module `f1_selection/text_features.py`_

- `ARM A` (arm) — Deterministic text features (invalidation `price_only` vs
  `mixed`, `invalidation_inside_strikes`, `trigger_conditional`,
  `numeric_specificity`, `thesis_len`, `alt_ratio`) plus the
  `hallucination_rate` from the citation check, read within structure × tier;
  `evidence_n` is a REDUNDANCY CONTROL, never a candidate.
- `ARM B` (arm) — Blind taxonomy labels (thesis type, evidence quality,
  confidence language, one-sided, invalidation concreteness) from a cheap
  headless model shown text only — never an outcome, never ticker or date.
- `ARM C` (arm) — Gate arms: a CANDIDATE from A/B applied as a VETO or a
  one-step tier demotion under the shipped top-3/day ladder, paired by date.
  Outputs are two named lists: PROMPT-ROBUSTNESS FINDINGS and ENTRY-GATE
  CANDIDATES.

#### `prompt_eval`

_Registered in [`pre-registrations/f1_selection/prompt_eval.md`](pre-registrations/f1_selection/prompt_eval.md) · module `f1_selection/prompt_eval.py`_

- `PROD` `CANDIDATE` (arm) — The two prompt arms: the committed
  framework + method files vs a named, committed snapshot; sha256 recorded.
- `VARIANCE` `BACKFILL` `LIVE` (population scope) — not an arm. Declared in
  that order: PROD repeats for the noise floor; ~40 matured signal dates
  chosen by rule (SECONDARY — both arms share the backfill lookahead); every
  new live date the candidate is run on (PRIMARY, supersedes BACKFILL at 25
  dates).
- `draft` (run) — not an arm: a headless model proposes a prompt diff from
  `text_features`' robustness list; a record, never auto-applied.

#### `macro_event_study`

_Registered in [`pre-registrations/f1_selection/macro_event_study.md`](pre-registrations/f1_selection/macro_event_study.md)_

- `H1` `H2` `H3` `H4` (hypothesis) — pre-registered claims, each mapped to
  an arm under a DIFFERENT letter: H1→`ARM I`, H2→`ARM P`, H3→`ARM V`,
  H4→`ARM X`. Reports cite both forms.
- `ARM I` (arm) — Entry IV behaviour (H1 PRIMARY) — `vrp` on sessions near
  a scheduled event vs control.
- `ARM P` (arm) <a id="macro_event_study-arm-p"></a> — Outcomes (H2) — mean
  R and E by entry-proximity bucket, within structure. One of `ARM P`'s six
  owners repo-wide.
- `ARM V` (arm) — Market context (H3) — VIX level and 1-day change by
  event-relative session.
- `ARM V-price` (arm) — Amendment 1 (2026-08-19) — the SPY-price companion
  to `ARM V`. CONTEXT ONLY, same standing as the VIX table.
- `ARM X` (arm) — Exit census (H4) — `exit_reason` mix and R. ENDOGENOUS by
  construction, DESCRIPTIVE, no verdict.

#### `ml_combination`

_Registered in [`pre-registrations/f1_selection/ml_combination.md`](pre-registrations/f1_selection/ml_combination.md) · module `f1_selection/ml_combination.py`_

- `B0` (control) — The benchmark: the shipped score-free ladder's top-3/day
  A-then-B replay, out-of-fold. Everything else is scored against it.
- `B1` `B2` (control) — COLLIDES with `bear_arm`'s criteria above: `B1` is
  logistic regression on E>0 with structure × market-direction × vol only
  (does the model rediscover the ladder?); `B2` is elastic-net on E with the
  full feature set (is there anything linear left).
- `M1` `M2` `M3` (arm) — Gradient boosting on E, the same on binary E>0, and
  a single depth-3 tree. Only `M3` may ship, "because only it reduces to a
  human checklist"; a black-box score may at most tie-break within a tier.

#### `trigger_entry`

_Registered in [`pre-registrations/f1_selection/trigger_entry.md`](pre-registrations/f1_selection/trigger_entry.md) · module `f1_selection/trigger_entry.py`_

- `ARM T` (arm) — Trigger-gated entry, the HEADLINE: enter only at the CLOSE of
  the first session k ∈ [1..N] whose underlying close crosses the model's own
  stated trigger level in the stated direction, re-priced and re-sized through
  the frozen harness; never crossing within N = NOT ENTERED. N ∈ {1, 3, 5}.
  Unrelated to `staged_exit`'s `ARM T` (tighten / arm-trail) — see Collisions.
- `ARM L` (control) — Unconditional lag CONTROL: every in-scope row filled
  at a fixed session k ∈ {1, 3}, no gate, so a ΔR the control reproduces is
  a LAG finding and not a trigger finding. Named after and matched to
  `emission_timing`'s `ARM L` above, which is a different study's arm.
- `ARM C` (control) — Confound CONTROL: `ARM T`'s ΔR stratified by
  entry-session conformity band, reusing `next_day_move.DAY0_PNL_BANDS` and
  its `MIN_CELL_N` verbatim. Feeds criterion 8; carries no verdict of its
  own.
- `ARM D` (arm) — Deployment READ: the shipped top-3/day ladder with
  NOT-ENTERED rows made INELIGIBLE (the slot frees to the next-ranked play),
  trigger-priced against the shipped picks, R only.

### ② Management — when to get out

#### `bear_giveback`

_Module `f2_management/bear_giveback.py`_

- `ARM P` (arm) <a id="bear_giveback-arm-p"></a> — Production baseline —
  the `be_after` threshold measured against the SHIPPED production exit.
  One of `ARM P`'s six owners repo-wide.
- `ARM S` (arm) — Deployment reference stats — n / win rate / profit
  factor / mean R by cut. COLLIDES with `hedge_structure`'s own `ARM S`
  (its structure sweep) — unrelated.
- `ARM U` (arm) — Underlying path — does the underlying's price path
  explain the give-back? Buckets pre-declared before any output.

#### `next_day_move`

_Module `f2_management/next_day_move.py`_

- `ARM C` (control) — Confound control — `ARM U`'s method (see
  `bear_giveback`, above — a different study's unrelated arm despite the
  shared letter) moved to day 0; hold the day-0 mark fixed and repeat the
  conformity cut inside day-0 P&L bands.
- `ARM D` (descriptive cut) — Descriptive — conform vs non-conform, cut by
  regime, structure, side.
- `ARM R` (arm) — The rule — a pre-registered day-0 cut, graded against
  shipped production.

#### `staged_exit`

_Registered in [`pre-registrations/f2_management/staged_exit.md`](pre-registrations/f2_management/staged_exit.md)_

- `ARM E` (arm) <a id="staged_exit-arm-e"></a> — Terminal "exit now" — pure
  composition around the FROZEN `harness.replay`, no fork or copy.
- `ARM T` (arm) <a id="staged_exit-arm-t"></a> — Tighten / arm-trail —
  `harness.replay` is COPIED into the study for this arm (contrast `ARM E`,
  which composes around the frozen one).

#### `bear_fast_exit`

_Drafted in [`pre-registrations/f2_management/bear_fast_exit.md`](pre-registrations/f2_management/bear_fast_exit.md)_

**DRAFT — not registered.** The labels below are provisional until the
operator accepts the file. The study asks whether a bear debit held only a few
sessions, or closed at a small profit, is positive net of trading costs.

- `ARM TP` (arm) — Small profit target: the shipped bear-debit exit with pt
  0.10, 0.20 or 0.30.
- `ARM TS` (arm) — Time stop: exit at the close of session N if still open,
  for a short list of N fixed in the draft. Composes around the frozen
  `harness.replay`, like `staged_exit` `ARM E`.
- `ARM OP` (arm) — The operator's live habit as inferred from fills: pt 0.25
  or the close of session 5, whichever comes first.

#### `exit_from_text`

_Registered in [`pre-registrations/f2_management/exit_from_text.md`](pre-registrations/f2_management/exit_from_text.md) · module `f2_management/exit_from_text.py`_

- `E1` (arm) — Invalidation-as-stop: exit on the underlying close beyond the
  model's own stated invalidation level, buffer grid {0, 1%, 2%}, breakeven
  not strike for straddles; split "level == a strike" vs "level ≠ any strike".
- `E2` (arm) — Trigger-as-entry-filter: the play is entered only if its
  price-level trigger was met within N ∈ {1, 3} sessions — a SELECTION effect,
  quoted on R with the excluded share.
- `E3` (arm) — Horizon-as-time-exit: the emitted `horizon` DTE bucket as the
  time exit vs the shipped 0.75 fraction; survival control runs first.
  `E1`/`E2`/`E3` COLLIDE with `ladder_overlay`'s own `E1`/`E2`/`E3` (exposure
  gates) — unrelated; qualify every citation with its study.

#### `exit_drawdown`

_Registered in [`pre-registrations/f2_management/exit_drawdown.md`](pre-registrations/f2_management/exit_drawdown.md) · module `lib/exit_overlays.py`_

Five arms, every threshold chosen WALK-FORWARD on train dates only. The overlay
mechanics for W/U/O/P live in `lib/exit_overlays.py`; ARM D is a sizing hook in
`f4_deployment/account_sim.py` and changes no row's exit.

- `ARM W` (arm) <a id="exit_drawdown-arm-w"></a> — Walk-forward knob
  control: the pt × sl × tef grid (36 points, PROD is one of them) selected
  per block. The honesty baseline every other arm is read against. One of
  `ARM W`'s owners repo-wide.
  - `ARM W/wf` `ARM W/prod` (sub-arm) — the walk-forward pick and the PROD
    grid point, printed and graded together with `ARM W`, never alone.
- `ARM U` (arm) <a id="exit_drawdown-arm-u"></a> — Underlying ATR stop for
  DEBIT verticals: exit on the first close against the position by ≥
  k·ATR14, ATR FROZEN at entry, k ∈ {1.5, 2.0, 3.0}.
  - `ARM U/a` `ARM U/b` (sub-arm) — a adds the stop to sl .75; b replaces
    sl with it. Graded with `ARM U`, never alone.
- `ARM O` (arm) <a id="exit_drawdown-arm-o"></a> — Flow-unwind exit off the
  entry long leg's own `Open Int` path, read LAGGED one session, X ∈ {0.25,
  0.40}.
  - `ARM O/oi` `ARM O/vol` (sub-arm) — oi is the Open Int unwind; vol is
    the volume-climax variant (3× the EXPANDING post-entry median and an
    adverse mark). Graded with `ARM O`, never alone.
- `ARM P` (arm) <a id="exit_drawdown-arm-p"></a> — Partial scale-out: half
  the contracts at the shipped pt, half with pt=None, as two synthetic
  positions. Exact, nothing to select. Quoted in R, not dollars. One of
  `ARM P`'s owners repo-wide.
  - `ARM P/half` (sub-arm) — the printed cell for this arm, graded with
    `ARM P`, never alone.
- `ARM D` (arm) <a id="exit_drawdown-arm-d"></a> — SECONDARY drawdown
  THROTTLE (sizing, not exit): half budget while marked equity is ≥ d
  below its running peak, d ∈ {0.05, 0.10}. Can never ship from this
  study; has its own "affected" definition for G0.
  - `ARM D/throttle` (sub-arm) — the printed cell for this arm, graded
    with `ARM D`, never alone.

### ③ Structure — which wrapper

#### `bear_rewrap`

_Module `f3_structure/bear_rewrap.py`_

- `ARM P` (arm) <a id="bear_rewrap-arm-p"></a> — Portfolio contribution —
  P1 worst-decile, P2 correlation. The merge this arm validated is what
  `financed_spread` and `account_sim` cite. One of `ARM P`'s six owners
  repo-wide.
  - `P1` `P2` (sub-arm) — `ARM P`'s own two halves (worst-decile,
    correlation), graded together with their parent, never alone. Not to be
    confused with `hedge_structure`'s own `P1` below, which is unrelated.
- `ARM W` (arm) — The wrapper, replayed on the shipped production exit.

#### `financed_spread`

_Registered in [`pre-registrations/f3_structure/financed_spread.md`](pre-registrations/f3_structure/financed_spread.md)_

- `F0` `F1` `F2` `F3` `F4` (cell) — Financing structures. `F0` strike-aligned
  control (machinery pilot, runs first); `F1` opposite-delta credit spread;
  `F2` naked short leg; `F3` same-direction financed vertical; `F4`
  diagonal financing (amendment 1, 2026-08-19). `F1`/`F2` COLLIDE with
  `account_sim`'s unrelated 1-contract-floor `F1`/`F2` below.

#### `ladder_overlay`

_Registered in [`pre-registrations/f3_structure/ladder_overlay.md`](pre-registrations/f3_structure/ladder_overlay.md) · module `f3_structure/ladder_overlay.py` · engine `lib/overlay_campaign.py` · targets `lib/ladder_targets.py`_

Wraps a book `bull_call_spread` core in a rolled short-call ladder, on the
same core rows and dates as `financed_spread`; two cells replace the core
with a naked put instead. Run on both eras and **closed 2026-09-16**: every
graded cell `NULL` on v4, six `NULL` and four `UNDERPOWERED` on v3
([record](study-results/f3_structure/ladder_overlay.md),
[`next-steps.md` §2.13](next-steps.md#s2-13)).

- `L-BASE` `L-F4` `L-T0` `L-GAP` `L-RUN` `L-T0-TEF` `L-GAP-TEF` `L-RUN-TEF` (cell) —
  the 8 PRIMARY ladder cells, all |Δ| 0.20 calls, `BHOLD` breach.
  The core alone (`TNEVER`) is `L-BASE`, the baseline every other cell's ΔR
  pairs against — never a candidate itself. Three cells vary the trigger,
  rolling (`R1`): `L-T0`, `L-GAP`, `L-RUN`. The `-TEF` cells repeat those
  three with the profit target dropped (`X-TEF` core exit). One cell is the
  `G1b` replication anchor and not a candidate: `L-F4` reproduces
  `financed_spread` [`ARM F4`](#financed_spread)-d20-hold's mark series
  exactly, a machinery check and not a new arm on F4's ground.
- `N-CORE` `N-ROLL` (cell) — the 2 naked-put cells; both REPLACE the core
  rather than wrap it. `N-CORE` sells a put at the core's own long strike
  and expiry (`T0`/`R0`). `N-ROLL` rolls a |Δ| 0.30 put on the same slot
  schedule as the ladder cells (`T0`/`R1`). Both UNBOUNDED below the
  strike; `G3` carries a margin census, never a criterion.
- `S-D30` `S-BBUY` `S-BUP` `S-XEXP` `S-GAP103` `S-DTE60` `S-MODEL` (cell) —
  7 SENSITIVITY cells, printed with n, never a criterion. Delta widens at
  `S-D30`: |Δ| 0.30 against a PRIMARY of 0.20. Breach policy varies at
  `S-BBUY`/`S-BUP`: buy back, or buy back and re-sell. Hold period changes
  at `S-XEXP`: the 120-day path cap instead of §5. Trigger tightens at
  `S-GAP103`: the `TGAP` level moves to 1.03× from 1.015×. DTE floor
  applies at `S-DTE60`: the `T0` cell restricts to cores ≥60 DTE. Score
  weight sweeps at `S-MODEL`: the `[MODEL]` tier (below) runs at ×{1.00,
  0.75, 1.25}.
- `T0` `TGAP` `TRUN` `TNEVER` (axis) — the trigger a tranche is sold on: at
  entry, on a gap-up (open ≥1.015× prior close), on a sustained rise (3
  consecutive higher closes, close ≥1.04× entry close), or never.
- `R0` `R1` (axis) — roll policy: one tranche only, or roll each slot as it
  expires.
- `BHOLD` `BBUY` `BUP` (axis) — breach policy while a tranche is live: do
  nothing, buy back at that close's mark, or buy back and sell the next
  expiry's target-delta strike.
- `X-SHIP` `X-TEF` `X-EXP` (axis) — core exit profile: the shipped §5 debit
  profile, §5 with no profit target, or hold to the 120-day path cap
  (sensitivity only).
- `G0` (gate) — power floor: <25 dates OR <60 rows → UNDERPOWERED, no
  criterion evaluated.
- `G1` (gate) — `reconstructs()` on every candidate core; failures excluded
  and counted by reason.
- `G1b` (gate) — the F4 identity check: `L-F4`'s per-day mark series must
  equal `financed_spread` [`ARM F4`](#financed_spread)-d20-hold's to $0.01
  per day on shared rows (`overlay_campaign.f4_identity`). Proves the
  campaign engine is a SUPERSET of F4's single-tranche simulator, not a
  second one; a mismatch fails the run.
- `G2` (gate) — clamp attribution: every ladder cell must be 100%
  unclamped on days with a live tranche, clamped on core-only days.
- `G3` (gate) — sizing and margin census; the naked-put cells' reg-T margin
  proxy prints here, never as a criterion.
- `G4` (gate) — breach census: tranches sold, share breached, the
  `settle_mark`/`settle_intrinsic` split, breach cost in R, share of exits
  taken by `dollar_stop`. Criterion 8 is read against this census.
- `E1` `E2` `E3` (gate) — exposure reads printed alongside ΔR for every
  PRIMARY and naked-put cell, re-checked as gates in the bar for a
  candidate. Entry geometry is `E1`: Δ(net delta) at entry must go more
  negative. Vega structure is `E2`: Δ(net vega), since every ladder cell is
  structurally short vega. Sleeve correlation is `E3`: the cell's mean R
  against the deployed top-3 sleeve's mean R (≥8 shared dates required);
  positive = **RE-WRAP** regardless of ΔR. COLLIDES with
  `exit_from_text`'s own [`E1`/`E2`/`E3` above](#exit_from_text)
  (invalidation-stop / entry-filter / time-exit arms) — unrelated; qualify
  every citation with its study.
- **BREACH-DOMINATED** / **AWAITING SCRAPE** (verdict) — two tokens this
  study adds to the verdict grammar ([glossary.md](glossary.md) §9).
  BREACH-DOMINATED: criteria 1–7 pass and criterion 8 flips sign — the
  campaign's edge is a tail it never paid for. AWAITING SCRAPE: the
  contracts a cell needs are not yet cached; the run exits 0, prints the
  census, and evaluates no criterion.

### ④ Deployment — can I run it

#### `account_sim`

_Registered in [`pre-registrations/f4_deployment/account_sim.md`](pre-registrations/f4_deployment/account_sim.md) · module `f4_deployment/account_sim.py`_

- `ARM D` (arm) — Downsize on admission failure (vs `ARM R` reject) — take
  the largest contract count that still fits.
- `ARM H` (arm) — The shipped bear hedge sleeve — 1/day, `|delta|`
  descending, ≤ ½ size.
- `ARM R` (arm) — Reject on admission failure (vs `ARM D` downsize) — drop
  a candidate a cap would breach.
- `F1` `F2` (cell) — COLLIDES with `financed_spread`'s F1/F2 above and means
  something unrelated: the 1-contract-floor question. `F1` takes a
  position at 1 contract even when its max loss exceeds budget (production
  behaviour, the headline cell). `F2` refuses it.
- `--compounding` `--live-select` `--structure-universe` (run) — CLI
  arms — alternative RUNS of one study, not separate questions. Each
  writes its own report/CSV stem ([`glossary.md`](glossary.md) §7).

#### `portfolio_delta`

_Registered in [`pre-registrations/f4_deployment/portfolio_delta.md`](pre-registrations/f4_deployment/portfolio_delta.md)_

- `ARM B` (arm) — Net-delta ceiling band, tested at 1.0×, 1.5× and 2.0×
  equity. Also tested at 2.5× equity and unlimited (∞).
- `ARM D` (arm) — Dose-response (DESCRIPTIVE PRIMARY) — mean R by the open
  book's delta at entry.
- `ARM H*` (arm) — Delta-TARGETED hedge-sleeve resizing — adjacent to
  `account_sim`'s hedge sleeve above, NOT the same arm.
- `ARM N` (arm) — The random null band — 200 seeded random admissions.
  COLLIDES with `concurrency_correlation`'s own `ARM N` below — same role,
  different study.

#### `selection_order`

_Registered in [`pre-registrations/f4_deployment/selection_order.md`](pre-registrations/f4_deployment/selection_order.md)_

- `O0` `O1` `O1b` `O2` `O3` `O4` (arm) — Ordering arms. `O0` = production
  `ladder_rank` baseline; `O1` delta-notional ascending; `O2` reserved-$
  per unit delta-notional descending; `O3` `|delta|` descending; `O1b`
  tier-blind across A∪B; `O4` = the seeded random null band that decides
  the meaning of the others.

### ⑤ Hedging — what protects the book

<a id="bear_deploy"></a>
#### `hedge_sizing`

_Was `bear_deploy` until 2026-09-08; renamed after the question it answers, labels unchanged._

_Registered in [`pre-registrations/f5_hedging/hedge_sizing.md`](pre-registrations/f5_hedging/hedge_sizing.md) · module `f5_hedging/hedge_sizing.py`_

- `D1` `D2` `D3` `D4` `D5` (criterion) — Deployment criteria, NOT `ARM D` —
  `D1` is joint selection × exit, and the four that follow it. Mirrored by
  `hedge_structure`'s `H1`–`H5` above.

<a id="calendar_hedge"></a>
#### `hedge_structure`

_Was `calendar_hedge` until 2026-09-08; renamed after the question it answers, labels unchanged._

_Registered in [`pre-registrations/f5_hedging/hedge_structure.md`](pre-registrations/f5_hedging/hedge_structure.md) · module `f5_hedging/hedge_structure.py`_

- `ARM H` (arm) <a id="hedge_structure-arm-h"></a> — The hedge programme
  (`hedge_structure`'s own `P1` sleeve, below) — runs first; `ARM S` runs
  only behind it. This study also uses `H0`–`H5` as criteria (below); the
  two are unrelated despite the shared letter.
- `ARM S` (arm) <a id="hedge_structure-arm-s"></a> — Structure sweep of
  untried wrappers. Runs only AFTER `ARM H` prints; nothing in it can ship
  on its own. COLLIDES with `bear_giveback`'s own `ARM S` above — unrelated.
  - `S1` `S2` `S3` `S6` (sub-arm) — `S1` put mirror, `S2` short-near-put,
    `S3` short-pulled-up bear vertical, `S6` bull-put + bear-call wings.
    Graded together with `ARM S`, never alone.
- `H0` `H0b` `H1` `H2` `H3` `H4` `H5` (criterion) — criteria, not
  hypotheses and not `ARM H`: `H0` FILL, `H0b` FRESHNESS, `H1`–`H5`
  mirroring `hedge_sizing`'s `D1`–`D5` (below). COLLIDES in letter only with
  `macro_event_study`'s `H1`–`H4` hypotheses above — unrelated forms.
- `P1` (sub-arm) — this study's own hedge sleeve itself, NOT `bear_rewrap`'s
  `P1`/`P2` above (which are that study's `ARM P` halves) — same letter,
  unrelated meaning.

<a id="hedge_exposure"></a>
#### `hedge_portfolio`

_Was `hedge_exposure` until 2026-09-08; renamed after the question it answers, labels unchanged._

_Registered in [`pre-registrations/f5_hedging/hedge_portfolio.md`](pre-registrations/f5_hedging/hedge_portfolio.md) · module `f5_hedging/hedge_portfolio.py`_

**The module carries a second arm since 2026-09-07.** `--admitted` runs the same
question on the ADMITTED book, and its labels are indexed separately under
[`hedge_concentration`](#hedge_concentration), which is the study it was merged
from. The labels below are the WHOLE-BOOK arm's. Six tokens are spelled the same
in both and mean the same role over a different population, so always say which
arm. This `--admitted` run is a population scope: the same design read on the
ADMITTED book, not a second question ([Object types](#object-types)).

Grid: 3 τ × 3 f = 9 cells per arm, fixed at registration and never expanded.
`ARM C` here is NOT `concurrency_correlation`'s `ARM C` (a concurrency
ceiling) and `ARM N` is the third `ARM N` in this family — same random-null
role, different study.

- `ARM M` (arm) — MEASUREMENT. The same unhedged book on both equity curves,
  mark-to-market (from `daily_pnl_csv`) versus realized-on-close
  (`account_sim.equity_curve`). Runs first and gates nothing. It is not
  power-gated, so it is readable when the hedge cells are not: on the
  population the operator ratified 2026-08-31 it carries the study's
  **MEASUREMENT-ONLY** verdict — the two curves differ materially while no
  hedge cell clears the bar. Every hedge CELL is UNDERPOWERED there, so the
  mechanism question is **UNDERPOWERED** and no direction is quoted from any
  of them. See `research/pre-registrations/f5_hedging/hedge_portfolio.md`
  §Population and basis (RATIFICATION consolidated there 2026-09-02).
- `ARM C` (arm) — Concentration-gated proxy put: hedge while the largest
  cluster's share of book gross delta notional is ≥ τ, tested at 0.30, 0.35
  and 0.40. Sizing is f, tested at 0.25, 0.50 and 1.00 of a standard
  position's risk. Carries no prose.
- `ARM CS` (arm) — `ARM C` plus the analysis prose's `hedge-pressure ≥ 50`.
  PROSE-CONDITIONED; a date with no parse is NO SIGNAL.
- `ARM P` (arm) <a id="hedge_portfolio-arm-p"></a> — The prose-free
  counterpart on exactly `ARM CS`'s session set. Written `**ARM P**` in
  `lib/hedge_instrument.py`, so the emphasis markers travel with the
  token: `P**` is this same arm. One of `ARM P`'s six owners repo-wide.
- `ARM N` (arm) — Random-admission null, 200 seeds, matched on episode COUNT,
  episode LENGTHS and PROXY mix. An arm must beat its 95th percentile, not
  merely beat the unhedged book. COLLIDES with `portfolio_delta`'s and
  `concurrency_correlation`'s own `ARM N` — same role, different study.
- `ARM B` (arm) — Instrument comparison: the book's own bear row instead of the
  put. It cannot remove the §4 sleeve, which is operator policy.
- `ARM R` (arm) — Always-fillable reference: a delta-equivalent SHORT in the
  proxy underlying. Clause 7's control — a put arm that merely matches it is
  A RESTATEMENT OF DELTA REDUCTION. NOT `account_sim`'s `ARM R` (reject on
  admission failure). Written `**ARM R**` in `lib/hedge_instrument.py`, so
  `R**` is this same arm.
- `ARM RF` (arm) — Not pre-registered: `ARM R`'s fill-INDEPENDENT floor, sized
  off fraction f of the concentrated cluster's own signed delta notional rather
  than off `ARM C`'s put. It exists because the registration's `ARM R` is
  delta-matched to a put and so depends on the option cache it was introduced
  to be free of. Reference only; no verdict is read from it.

#### `hedge_timing`

_Registered in [`pre-registrations/f5_hedging/hedge_timing.md`](pre-registrations/f5_hedging/hedge_timing.md) · module `f5_hedging/hedge_timing.py`_

Each arm is run once per TRIGGER FAMILY and printed suffixed with it —
`ARM H1-CHOP`, `ARM H1-GAP`, `ARM H1-DECLINE`, and likewise for `H2`/`H3`/`H4`.
The bare `H0`–`H4` below are the arms themselves; the suffix names which
trigger the arm was run on, not a different question. Not `hedge_structure`'s
`H0`–`H5` (criteria), and not `macro_event_study`'s `H1`–`H4` (hypotheses).

- `ARM H0` (arm) <a id="hedge_timing-arm-h0"></a> — POWER CENSUS. Runs
  first and returns BEFORE any outcome column is read: trigger dates,
  bear-carrying dates, bear rows, H3-paired dates, and the same four on
  non-trigger dates. Every arm below early-returns UNDERPOWERED off it
  without computing a statistic.
- `ARM H1` (arm) <a id="hedge_timing-arm-h1"></a> — Between-date separation
  of bear R, trigger vs non-trigger, date-clustered. NOT the primary: a
  date either fires or does not, so no within-date pairing exists and a
  positive is confounded with "the market fell".
  - `ARM H1-CHOP` `ARM H1-GAP` `ARM H1-DECLINE` (sub-arm) — printed once
    per trigger family, graded with `ARM H1`, never alone.
- `ARM H2` (arm) <a id="hedge_timing-arm-h2"></a> — Beta control: the SAME
  separation on the DEPLOYED LADDER. `h2_mirrors` (|H2 delta| ≥ 0.5 × |H1
  delta|, opposite-signed) turns a positive into MARKET-TIMING-PROXY.
  - `ARM H2-CHOP` `ARM H2-GAP` `ARM H2-DECLINE` (sub-arm) — printed once
    per trigger family, graded with `ARM H2`, never alone.
- `ARM H3` (arm) <a id="hedge_timing-arm-h3"></a> — **PRIMARY.** Within-date
  paired (`hedge_sizing` D4's method): date-mean bear R minus date-mean
  tier-A/B long R, headline = the DIFFERENCE of that paired mean on trigger
  vs non-trigger dates.
  - `ARM H3-CHOP` `ARM H3-GAP` `ARM H3-DECLINE` (sub-arm) — printed once
    per trigger family, graded with `ARM H3`, never alone.
- `ARM H4` (arm) <a id="hedge_timing-arm-h4"></a> — Do-nothing baseline in
  DOLLARS (the only arm that may quote `$`): sleeve policies over the
  deployed ladder's daily dollars, judged by `hedge_sizing` D3's criterion.
  - `ARM H4-CHOP` `ARM H4-GAP` `ARM H4-DECLINE` (sub-arm) — printed once
    per trigger family, graded with `ARM H4`, never alone.

### Queued — pre-registered, no module yet

#### `concurrency_correlation`

_Registered in [`pre-registrations/f4_deployment/concurrency_correlation.md`](pre-registrations/f4_deployment/concurrency_correlation.md)_

Registered 2026-08-22; **built and first run 2026-09-04**
(`scripts/backtest_study/f4_deployment/concurrency_correlation.py`, era v4,
verdict NOISE). Every arm below is now a run arm, not a plan arm. The three
`ARM K` relations print as `K <k> / <relation>`, and on a long-only book the
`same-direction` relation is `ARM C` on a different grid — the run checks this
and excludes it from `ARM CK` rather than assuming it.

- `ARM C` (arm) — Concurrency ceiling — refuse a pick whose entry session
  already holds ≥ C open positions. Grid C is tested at 5 and 8. Also
  tested at 12 and 20.
- `ARM CK` (arm) — The conjunction of `ARM C` and `ARM K`, run only if each
  clears independently.
- `ARM D0` (descriptive cut) — Descriptive only — mean R by concurrency band
  at entry; the shape is reported, no band is adopted.
- `ARM K` (arm) — Clustering ceiling — refuse a pick when the open book
  already holds ≥ K sharing its direction (also run same-direction-and-
  sector, same-underlying); grid K ∈ {2, 3, 5}. COLLIDES with
  `hedge_concentration`'s `ARM K` (a concentration→drawdown PRECONDITION, an
  entirely different object) — qualify every citation with its study.
- `ARM N` (arm) — Null control (required) — random book-state labels
  matched on affected count; an arm inside its [p5, p95] band is NOISE
  regardless of its own CI. COLLIDES with `portfolio_delta`'s own `ARM N`
  above — same role, different study.
- `X1–X8` (criterion) — Eight ship criteria, all required for `ADOPT`.
  - The power floor, `X1`: ≥25 changed dates.
  - Paired gain, `X2`: within-date gain with a date-clustered CI clear of
    zero.
  - Beats the null, `X3`: gain above `ARM N`'s p95.
  - Era stability, `X4`: `X2` and `X3` hold on BOTH v3 and the current
    era, same sign, within 0.15 R. Settled by a `--era v3` companion run,
    since `lib/era.py` binds one run to one era.
  - Same sign, `X5`: PRIMARY and SECONDARY agree.
  - Leave-one-out, `X6`: stable by date and by ticker.
  - Survives the control, `X7`: beats the delta-notional check, else
    RESTATEMENT of `portfolio_delta`.
  - Real dollars, `X8`: quoted real+tweak only.

  Settled 2026-09-04: NOISE on both eras, no arm clears `X2`/`X3`.

#### `hedge_concentration`

_Registered 2026-08-31. The registration and the record were deleted 2026-09-08 with the module's other leftovers and are held in git at `44bbfb2`; the verdict is the DELETED row in [`study-map.md`](study-map.md#hedging)._

**These labels now print from `hedge_portfolio`'s `--admitted` arm.** The module was merged into [`hedge_portfolio`](#hedge_portfolio) and deleted on 2026-09-07; the section stays because the registration and the labels do.

Registered 2026-08-31 and first run the same day. The book is the ADMITTED
subset `account_sim` takes from `hedge_portfolio`'s ratified population. Stage 1
gates Stage 2, and on the first run it did not open it: Stage 1 is
PRECONDITION-NULL on a POWERED read, so `ARM C` / `ARM N` / `ARM R` were NOT
evaluated and no cell of the τ×f grid carries a number.

- `ARM M` (arm) — Measurement: the unhedged admitted book on both curves,
  mark-to-market versus realized-on-close. Reported every run, never a
  verdict. Same role as `hedge_portfolio`'s `ARM M`, on the admitted book.
- `ARM K` (arm) — The precondition: does a session's any-cluster
  concentration PREDICT the book's forward 20-session mark-to-market
  drawdown? Tercile contrast + Spearman ρ, block-bootstrapped. COLLIDES with
  `concurrency_correlation`'s `ARM K` (a clustering CEILING) — qualify every
  citation.
- `ARM KG` (arm) — `ARM K` re-read within terciles of gross/equity; the
  "not a gross-exposure effect in disguise" control (bar clause 4).
- `ARM KN` (arm) — `ARM K`'s time-structure null: the concentration series
  circularly shifted against the fixed drawdown series, 1,000 draws; `ARM K`
  must beat its 5th percentile.
- `ARM K10` (arm) — `ARM K` at H = 10; a disclosed sensitivity, never
  concluded from.
- `ARM C` (arm) — Stage 2 only: concentration-gated proxy put. The τ grid
  is tested at 0.45, 0.55 and 0.65. The f grid is tested at 0.25, 0.50 and
  1.00, admitted through `account_sim.admission()` in the ARM H pattern.
  Not `concurrency_correlation`'s `ARM C`. No prose arm exists in this
  study.
- `ARM N` (arm) — Stage 2 random-admission null, 200 seeds, matched on
  episode count, lengths and proxy mix. The fourth `ARM N` in this family.
- `ARM R` (arm) — Stage 2 always-fillable reference: delta-equivalent SHORT
  in the proxy underlying; clause 7's control. NOT `account_sim`'s `ARM R`.

#### `cost_sensitivity`

_Drafted in [`pre-registrations/f2_management/cost_sensitivity.md`](pre-registrations/f2_management/cost_sensitivity.md)_

**DRAFT — not registered.** The file carries a STATUS line saying so, and the
labels below are provisional until the operator accepts it. The study asks at
what cost per leg the Tier A/B edge vanishes; it cannot be built before the
cost knobs and the pre-fill grid fix land and the suite is re-run once.

- `ARM Z` (arm) — Zero-cost control: the book exactly as it prints today.
  Reference only, never a result of this study.
- `ARM X` (arm) — The registered cost point: $0.65 per contract plus 25% of
  the quoted spread, per leg, per side. The only arm any criterion is graded
  on. COLLIDES with `macro_event_study`'s `ARM X` (its exit census), which is
  unrelated — qualify every citation with its study.
- `ARM SW` (arm) — The cost sweep, commission × slippage fraction. Sensitivity
  only; it locates the breakeven contour and may never carry a verdict.
- `ARM Q` (arm) — Quote availability: the census of missing or degenerate
  quotes and the fixed three-step fallback ladder. A position with no usable
  quote is UNCOSTABLE and excluded, never charged zero.
- `ARM GAP` (arm) — Adverse-fill sensitivity on close-marked exits; folds
  [`robustness-review.md`](robustness-review.md) B4 in as a sensitivity.

#### `mechanical_benchmark`

_Drafted in [`pre-registrations/f1_selection/mechanical_benchmark.md`](pre-registrations/f1_selection/mechanical_benchmark.md)_

**DRAFT — not registered**, and NOT BUILDABLE until a pre-build census clears
its floors: most mechanical counterpart legs are not in
`backtests/option_history_cache/` today. The study asks whether the picks beat
a mechanical bull call spread on the same dates and tickers.

- `ARM T` (arm) — The deployed picks, replayed unchanged. Reference only.
  COLLIDES with `staged_exit`'s and `trigger_entry`'s `ARM T`, which are
  unrelated — qualify every citation with its study.
- `ARM M1` (arm) — Fixed-geometry counterpart: ATM/+5% call vertical on the
  same ticker and date, inside the pick's DTE band. PRIMARY.
- `ARM M2` (arm) — Matched-geometry counterpart: the vertical whose
  entry-dated delta and DTE are nearest the pick's. SECONDARY.
- `ARM U` (control) — Universe null: the `ARM M1` wrap on random
  flow-universe tickers for that date, ≥1,000 date-clustered draws. The
  base-rate arm, and the one that answers "long calls just worked". COLLIDES
  with `bear_giveback`'s `ARM U` (the underlying's price path) and
  `exit_drawdown`'s `ARM U` (the underlying ATR stop), both unrelated —
  qualify every citation with its study. Not the printed prose `ARM UNIVERSE`
  below either.
- `ARM CEN` (arm) — Census: pair-build rates, redraw rates and band coverage
  by tier, structure and DTE band. Descriptive only, never a criterion.

Registered alongside these two, with no arms of its own:
[`pre-registrations/f4_deployment/holdout_seal.md`](pre-registrations/f4_deployment/holdout_seal.md)
— a DRAFT commitment to seal the live dates, not a study. It has no module, no
report and no labels to index.

## Not labels

`ARM SELECTION` `ARM UNIVERSE` `ARM VERDICT` — printed report text or code
comments that read like labels but are not: `"ARM VERDICT INPUT:
UNDERPOWERED"` is a printed report line; `ARM SELECTION` marks
`account_sim`'s `--compounding` switch in a code comment; `H ARM UNIVERSE`
is a `hedge_structure` table header.

## Keeping this file honest

`tests/test_arm_index.py` fails if any `ARM <label>` token appears in a study
module or a pre-registration without a mention here — so a newly registered
arm cannot be added without landing in this index — and pins the six `ARM P`
owners. It also refuses any label bullet whose object-type tag is missing or
falls outside the closed list under [Object types](#object-types).

What it does NOT check: the descriptions, which are the operator's own words,
same as [`study-map.md`](study-map.md)'s verdicts. It also cannot enforce
coverage of the non-`ARM` labels — gates, criteria and hypotheses have no
identifying token shape, so those bullets are hand-maintained and can go
stale; where this file disagrees with the code, the code is right.

## See also

- [`glossary.md`](glossary.md) §9 — what an ARM is, and the verdict grammar
  arms are graded under. §7 — CLI arms.
- [Object types](#object-types) — what each parenthesised tag means.
- [`pre-registrations/`](pre-registrations/) — the arms' actual definitions,
  in full, immutable.
- [`study-map.md`](study-map.md) — what each study asked and concluded.
