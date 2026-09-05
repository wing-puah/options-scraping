# Research overview

Lost the thread? Start here. Terms are defined in [`glossary.md`](glossary.md),
study-local labels such as `ARM P` or `B2` in [`arm-index.md`](arm-index.md),
and the house style for writing any of this down in
[`writing-guide.md`](writing-guide.md).

Written 2026-09-02, refreshed 2026-09-05. This page is a summary of
[`next-steps.md`](next-steps.md), [`current.md`](current.md) and
[`study-map.md`](study-map.md). When any of those disagrees with this page,
they win and this page is stale.

## Where things stand

Figures, populations and the export provenance are in one place: the
[State of play](current.md#state-of-play) block at the top of
[`current.md`](current.md). These bullets only say which way to look.

- Era `v4` is current. `v3` is frozen, and is the era every shipped rule was
  derived on. The two are never pooled.
- The book carries 2026 signal dates for the first time, so every "ex-2026" and
  "positive in every year" cut is live. See
  [where the 2026 column bit](current.md#state-of-play).
- Nothing new ships from the 166-date `v4` book. Two studies produced a
  first-time candidate and both are held, because the new dates are a
  backfill window and its dates move together.
- The hedge programme is closed on triggers and open on the instrument.
  `hedge_exposure` ships nothing, `hedge_concentration` is graded
  `PRECONDITION-NULL`, a *powered* null, and the queue item is closed. The
  drafted gap-up prohibition is still held
  ([`next-steps.md`](next-steps.md) [§1](next-steps.md#s1),
  [§2.1](next-steps.md#s2-1);
  [`deployment-evidence.md`](deployment-evidence.md)).
- The v3 to v4 transfer of the deployment rules is unvalidated. `v4_bridge`
  prints `VERDICT: LADDER UNVALIDATED ON v4`
  ([`scripts/study_map/catalog.py`](../scripts/study_map/catalog.py)). Per its
  [pre-registration](pre-registrations/f1_selection/v4_bridge.md), keep
  deploying under the v3-derived rules and do not re-derive the ladder on v4
  rows yet ([`next-steps.md`](next-steps.md) [§2.2](next-steps.md#s2-2)).
- Repo state, tests, unpriceable dates and the known data gaps are in
  [`next-steps.md`](next-steps.md) [§0](next-steps.md#s0).

## What is in production (SHIPPED)

These are the rules live in `config/` and
[`docs/deployment-rules.md`](../docs/deployment-rules.md) today.
Terms used in the table: [CI](glossary.md#ci), [PF](glossary.md#pf).

| Rule | What it says | Era derived on | Card | Open rollback trigger |
|---|---|---|---|---|
| Debit exit profile | profit target 90%, stop −75%, time exit at 75% of DTE elapsed, no trailing stop | v3, attempt 10 | [§5](../docs/deployment-rules.md#s5) | none registered |
| `bear_call_spread` vetoed at intake; credit exit carries no stop | the §1.1 veto; the credit row rides toward expiry | v3, attempt 13 | [§1.1](../docs/deployment-rules.md#s1), [§5](../docs/deployment-rules.md#s5) | "credit sl-none", `UNDERPOWERED` |
| Score-free tiers | tier A and B deploy first, tier C and VETO are skipped | v3, 2026-07-21 | [§2](../docs/deployment-rules.md#s2), [§6](../docs/deployment-rules.md#s6) | none |
| `bull_put_spread` geometry band | 0.08 ≤ \|δ\| ≤ 0.20, DTE ≤ 59, prefer 45–59; a miss drops to tier C | v3 | [§3](../docs/deployment-rules.md#s3) | provisional, re-read at the next independent window |
| [`mech_cell`](glossary.md#mech_cell)-keyed [BEAR_HE](glossary.md#bear_he) trail | arm at +50%, then trail 50 points from peak on a signal date the mechanical regime labels BEAR with high or extreme vol | v3, 2026-07-22 | [§5](../docs/deployment-rules.md#s5) | "BEAR_HE trail", `UNDERPOWERED` |
| Bear debit selection veto plus hedge-sleeve carve-out | bear (`bear_put_spread`, `long_put`) never enters the deployed top-3, and may only be held deliberately as a ≤½-size hedge | v3 mechanism, chosen 2026-08-13 | [§1.4](../docs/deployment-rules.md#s1), [§4](../docs/deployment-rules.md#s4) | D4 pick rule PULLED |

Tiers are structure × regime × entry geometry, and `score_total` is a
tie-break only. The [BEAR_HE](glossary.md#bear_he) trail is the one
debit exit that switches on the *mechanical* regime; it came from
`mech_regime_recut` and `exit_switch_mech_study` on 2026-07-22. The two open
`UNDERPOWERED` triggers are "credit sl-none" at **0** fresh `bull_put` rows of
15, and "BEAR_HE trail" at **1** affected date of 25 on the 2026-08-24 census;
both are in [`deployment-evidence.md`](deployment-evidence.md) §"Open
pre-registered rollback triggers". The `bear_deploy` D4 pick rule
("`|delta|` descending") was **PULLED** on the 2026-08-24 v4 re-read
([`scripts/study_map/catalog.py`](../scripts/study_map/catalog.py)), so the
sleeve is now held as operator policy rather than as evidence.

One rule shipped and then came off. The bear-debit peak-triggered breakeven
stop (`be_after: 0.50`) shipped 2026-08-11. Its own pre-registered rollback
trigger **FIRED** on the 2026-08-24 census, because the 2025 mean-R delta was
negative, and it was **REVERTED**. `simulation.structure_exit.enabled` is back
to `false` ([`next-steps.md`](next-steps.md) [§1](next-steps.md#s1),
[§2.4](next-steps.md#s2-4)).

## What was tried and did not survive

Grouped by the four study families: `f1_selection` → `f2_management` →
`f3_structure` → `f4_deployment`, or "pick it, manage it, wrap it, fund it".
Verdict words are copied verbatim from
[`scripts/study_map/catalog.py`](../scripts/study_map/catalog.py), unless
noted. That file is where a verdict is written down as prose rather than
computed from a report, which is why it is the one place to edit when a
verdict changes. It is not an independent human judgement: an agent drafts
the entry and the operator accepts it, so read it as a stored summary of the
report, not as a second opinion on it.

Each row links three ways: the study name to what it last printed, **Plan** to
its pre-registration — the commitments it was graded against, written before it
ran — and every arm or criterion to wherever that label is actually defined.
Most land in [`arm-index.md`](arm-index.md), which is organised BY STUDY, so
the link opens the study's block rather than the individual arm; the arm's own
definition is in the link's hover text. A few labels are not arms and live
elsewhere: `account_sim`'s A1–A6 in [`glossary.md`](glossary.md), and gates
like `selection_order` G0 or `concurrency_correlation` X2 only in their
pre-registration. Those link there instead. A dash in **Plan** means the study
predates the pre-registration system and has none.

Terms used below: [n vs dates](glossary.md#n-vs-dates),
[LOO](glossary.md#loo), [meanR](glossary.md#meanr), [CI](glossary.md#ci).

### Selection — "which plays are worth taking?"

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`bear_position_study`](study-results/f1_selection/bear_position_study.md) | **DEMOTE TO VETO** | all three pre-registered demote criteria fire on n=368 | — |
| [`bear_arm`](study-results/f1_selection/bear_arm.md) | **NO** | 0 of 496 pre-defined bear subsets clear the rule | [plan](pre-registrations/f1_selection/bear_arm.md) |
| [`ml_combination`](study-results/f1_selection/ml_combination.md) | **NULL RESULT** | 0 of 15 model × strategy cells beat the score-free ladder out of sample | [plan](pre-registrations/f1_selection/ml_combination.md) |
| [`macro_event_study`](study-results/f1_selection/macro_event_study.md) | **UNDERPOWERED**, and ARM X **DE-QUEUED** as `SURVIVAL-ARTIFACT` | every FOMC, minutes, CPI and PCE cell is underpowered, and the one raw trigger died under the survival control | [plan](pre-registrations/f1_selection/macro_event_study.md) |
| [`emission_timing`](study-results/f1_selection/emission_timing.md) [ARM P](arm-index.md#emission_timing "emission_timing ARM P: persistence — does a re-emitted play, the 2nd/3rd/4th of a ticker plus structure, do worse than the first emission?") | **NULL** | the v3-primary read spans zero | [plan](pre-registrations/f1_selection/emission_timing.md) |

Detail behind those clauses.

| Study | Figure | What it means |
|---|---|---|
| `bear_position_study` | ex-window mean E −0.222, CI [−0.349, −0.087] | margins narrowed on the 166-date book, but none crossed | — |
| [`bear_arm` B1](arm-index.md#bear_arm "bear_arm criterion B1: selection conditioning — is there a bear subset, definable at decision time, that is not negative?") | 0 of 496 subsets | this is the "NO" in the table above | [plan](pre-registrations/f1_selection/bear_arm.md) |
| [`bear_arm` B2](arm-index.md#bear_arm "bear_arm criterion B2: exit fit — is the base exit profile mis-tuned for bear rows? B2 shipped be_after 0.50 on 2026-08-11 and its own rollback trigger reverted it on 2026-08-24") | criteria MET for the first time by `sl .50` | a read off a correlated window, so it holds a rule and promotes nothing | [plan](pre-registrations/f1_selection/bear_arm.md) |
| `ml_combination` | 2026 −0.251 | its "at least 2 of 3 years" clause is a real three-year test for the first time | [plan](pre-registrations/f1_selection/ml_combination.md) |
| [`emission_timing` ARM P](arm-index.md#emission_timing "emission_timing ARM P: persistence — does a re-emitted play, the 2nd/3rd/4th of a ticker plus structure, do worse than the first emission?") | candidates 3 → 1 | two sub-cuts flipped sign in 2026 | [plan](pre-registrations/f1_selection/emission_timing.md) |

One candidate survives this family: `emission_timing`'s other half,
[ARM L](arm-index.md#emission_timing "emission_timing ARM L: fill lag — does an entry filled 1, 2 or 3 sessions after the signal lose the edge?")
(`LAG-TOLERANT`). Filling an entry one to three sessions late does not decay
the signal. It is the one live selection candidate and it has shipped
nothing.

### Management — "when do I get out?"

Both shipped exit rules ([§5](../docs/deployment-rules.md#s5)) came from this
family.

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`bear_giveback`](study-results/f2_management/bear_giveback.md) | **NULL** | the `be_after` grid does not ship; the give-back pattern lives in the underlying, not the option mark | — |
| [`volume_signal`](study-results/f2_management/volume_signal.md) | **NULL** | no return separation on non-bear debit, and the one frozen exit variant loses on a [LOO](glossary.md#loo) fold | [plan](pre-registrations/f2_management/volume_signal.md) |
| [`next_day_move`](study-results/f2_management/next_day_move.md) | **NULL** | [ARM C](arm-index.md#next_day_move "next_day_move ARM C: the confound control — hold the day-0 mark fixed and repeat the conformity cut inside bands of day-0 P&L, so the effect cannot just be day-0 P&L in disguise") never clears its confound control, so there is no rule | — |
| [`staged_exit`](study-results/f2_management/staged_exit.md) | **NULL** | zero candidates out of the 51 powered cells of 96, on the 166-date v4 book | [plan](pre-registrations/f2_management/staged_exit.md) |

Detail behind the two NULL rows at the bottom.

[`next_day_move` ARM R](arm-index.md#next_day_move "next_day_move ARM R: the rule — a pre-registered day-0 cut, graded against the shipped exit profile, run on three populations: whole book, all debit, bear debit") asks whether a bear debit play should be
closed on day 0 — the entry session — when the underlying moves against it.
Three versions of the rule were tried:

- cut when the move was the wrong sign;
- cut when the move was worse than −0.5σ;
- cut when the move stayed inside a flat ±0.5σ band.

In the report each version earns a `**` only if its paired CI excludes zero
**and** every [LOO](glossary.md#loo) fold is positive.

On the bear-debit population all three had that marker before, and all three
lost it in the 2026-09-04 run — era `v4`, the 166-date book, 361 bear-debit
rows.

| Version | paired CI | 2024 | 2025 | 2026 (n=21) |
|---|---|---|---|---|
| wrong sign | [−0.005, +0.148] | +0.091 | +0.083 | −0.153 |
| worse than −0.5σ | [−0.003, +0.090] | +0.073 | +0.031 | −0.143 |
| inside the flat band | [−0.011, +0.177] | +0.094 | +0.127 | −0.258 |

The marker was lost on the CI half: all three now straddle zero. The LOO half
still passes. The negative 2026 column is a second and separate failure. Every
figure above is `v4`. The study also has a `v3` run, recorded 2026-08-15, and
the two eras are never pooled, so nothing here carries over to the frozen era
([record](study-results/f2_management/next_day_move.md)).

`staged_exit` asks a different question: having held a position to session 5,
10, 15 or 20, does acting on where it stands then beat leaving the shipped
exit rule ([§5](../docs/deployment-rules.md#s5)) alone? Acting means exiting, tightening the stop, or arming a trail.
Of its 96 cells, 51 had enough data to read, and none produced a candidate.
Six cells have a CI excluding zero, and **all six point the wrong way**, so
they are evidence against acting rather than for it:

| Session | Trigger | Action | Δ meanR CI |
|---|---|---|---|
| 5 | down past −0.25 | exit | [−0.061, −0.006] |
| 5 | down past −0.25 | tighten the stop | [−0.057, −0.004] |
| 15 | up past +0.25 | exit | [−0.046, −0.001] |
| 20 | up past +0.25 | exit | [−0.054, −0.011] |
| 20 | up past +0.25 | arm a trail | [−0.053, −0.013] |
| 20 | up past +0.50 | exit | [−0.030, −0.005] |

So: cutting a loser at session 5, and taking profit early at sessions 15 and
20, both measurably cost money against leaving the shipped exit rule
([§5](../docs/deployment-rules.md#s5)) alone.

### Structure — "am I expressing the signal in the wrong wrapper?"

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`bear_rewrap`](study-results/f3_structure/bear_rewrap.md) | **NULL** for naive re-wraps | the diagonal re-wrap fails the every-year gate on its first look at 2026 | — |
| [`vol_sleeve`](study-results/f3_structure/vol_sleeve.md) | **CLOSED** | the straddle clears its gate then dies out of sample, and correlates the wrong sign with the deployed book | [plan](pre-registrations/f3_structure/vol_sleeve.md) |
| [`calendar_hedge`](study-results/f3_structure/calendar_hedge.md) | **BLOCKED ON NEW DATES** | the sizing criterion answers differently on every export | [plan](pre-registrations/f3_structure/calendar_hedge.md) |
| [`financed_spread`](study-results/f3_structure/financed_spread.md) | **UNCONFIRMED** on v4 | same-expiry shapes are NULL | [plan](pre-registrations/f3_structure/financed_spread.md) |

`bear_rewrap` needs a table of its own; the other three are a line each.

`bear_rewrap` re-prices each bear debit play as if it had been wrapped a
different way. The **diagonal** re-wrap rolls the long leg out to the next
cached expiry and leaves the short leg where it is, turning a vertical into a
diagonal. It is one of three re-wraps tried, not a cut of the population. This
study has no pre-registration file; its five ship gates are fixed in the module
(`bear_rewrap.py::report_criteria`). The diagonal passes four of them.

| `bear_rewrap` diagonal gate | Result |
|---|---|
| paired CI excludes zero | PASS |
| every [LOO](glossary.md#loo) fold positive | PASS |
| both window re-cuts positive | PASS |
| right-signed in both pricing tiers | PASS |
| same sign every year | **FAIL** — 2024 +0.195, 2025 +0.259, 2026 −0.106 |

In the same run its [ARM P](arm-index.md#bear_rewrap "bear_rewrap ARM P: portfolio contribution — P1 worst-decile mean R, P2 correlation with the deployed sleeve") portfolio checks came back MET for the
first time (P1 n=16, +0.499, CI [+0.202, +0.743]; P2 −0.326). One gate failing
and one arm newly passing is a candidate, not a ship.

| Study | Figure | Where it stands |
|---|---|---|
| `vol_sleeve` | +0.220 on 166 dates | only the calendar wrapper is right-signed against the book | [plan](pre-registrations/f3_structure/vol_sleeve.md) |
| [`calendar_hedge` H0](arm-index.md#calendar_hedge "calendar_hedge criterion H0 FILL: the sleeve must produce a fillable hedge on at least 60% of deployed-book dates and at least 60% of the deployed book's worst-decile dates") | fills 51.0% of deployed dates | the gate is 60% | [plan](pre-registrations/f3_structure/calendar_hedge.md) |
| [`calendar_hedge` H2](arm-index.md#calendar_hedge "calendar_hedge criterion H2 HEDGE CONTRIBUTION: negative daily correlation, positive mean sleeve R on the book's worst-decile dates, positive worst-quartile tail in two or more years") | n=4 | not evaluable | [plan](pre-registrations/f3_structure/calendar_hedge.md) |
| [`financed_spread` F3](arm-index.md#financed_spread "financed_spread F3: same-direction financed vertical") off1 | 6 of 7 criteria on 166 dates | prints RE-WRAP; the one failure is the anti-re-wrap correlation | [plan](pre-registrations/f3_structure/financed_spread.md) |
| [`financed_spread` F4](arm-index.md#financed_spread "financed_spread F4: diagonal financing, added by amendment 1 on 2026-08-19")-d20 hold | 36 rows against a floor of 60 | the v3 candidate is still under its rows floor | [plan](pre-registrations/f3_structure/financed_spread.md) |

### Deployment — "can I actually run this?"

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`account_sim`](study-results/f4_deployment/account_sim.md) | `>>> FEASIBLE <<<` on caps, but the window does not survive | delta-notional binds before cash does; feasibility only, nothing ships | [plan](pre-registrations/f4_deployment/account_sim.md) |
| [`selection_order`](study-results/f4_deployment/selection_order.md) | **ORDERING-IS-NOISE** | no arm separates from the O4 null band on 166 dates | [plan](pre-registrations/f4_deployment/selection_order.md) |
| [`portfolio_delta`](study-results/f4_deployment/portfolio_delta.md) | **CANDIDATE-FOR-INDEPENDENT-WINDOW**, B ceiling 1.00 only | a 1.00× net-delta ceiling clears every one of its adoption criteria at once, on the dense-episode population | [plan](pre-registrations/f4_deployment/portfolio_delta.md) |
| [`hedge_timing`](study-results/f4_deployment/hedge_timing.md) | GAP-UP came back **CONTRARY** | the hedge underperformed the same day's ladder-eligible long; survivors 0 of 9 | [plan](pre-registrations/f4_deployment/hedge_timing.md) |
| [`hedge_exposure`](study-results/f4_deployment/hedge_exposure.md) | **UNDERPOWERED** on the mechanism, **MEASUREMENT-ONLY** on ARM M | all nine hedge cells fail the power gate | [plan](pre-registrations/f4_deployment/hedge_exposure.md) |
| [`hedge_concentration`](study-results/f4_deployment/hedge_concentration.md) | **PRECONDITION-NULL** | the gate question failed, so the hedge itself was never tested — see below | [plan](pre-registrations/f4_deployment/hedge_concentration.md) |
| [`bear_deploy`](study-results/f4_deployment/bear_deploy.md) | D1–D4 **NOT MET** | the hedge-is-real and pick-rule estimands that held on v3 reverse on v4 | [plan](pre-registrations/f4_deployment/bear_deploy.md) |

The figures behind those. Every number is on the 166-date `v4` book.

| Study | Figure | What it means |
|---|---|---|
| [`account_sim` A1 / A3](glossary.md#criteria-a1a6 "account_sim criterion A1: edge survival — mean R positive, CI excludes zero, every year positive. A3: no blowup — drawdown bound, no ledger violation") | 2026 −0.062 · 35.7% drawdown | FEASIBLE is a two-year, dense-episode claim only; the full book fails both | [plan](pre-registrations/f4_deployment/account_sim.md) |
| [`selection_order` G0](pre-registrations/f4_deployment/selection_order.md "selection_order gate G0 POWER PRE-CHECK: runs first and blocks every read below it; under 25 affected dates and nothing is read") | powered since 08-27 | but the primary population has no 2026 term at all, and the secondary's 2026 cell is 3 dates | [plan](pre-registrations/f4_deployment/selection_order.md) |
| [`portfolio_delta` ARM B](arm-index.md#portfolio_delta "portfolio_delta ARM B: net-delta ceiling band, 1.0/1.5/2.0/2.5/infinity times equity") 1.50 | primary CI spans zero · secondary 2026 −0.088 | dropped out 2026-09-04; nothing ships off a correlated window | [plan](pre-registrations/f4_deployment/portfolio_delta.md) |
| [`hedge_timing` ARM H3](arm-index.md#hedge_timing "hedge_timing ARM H3, the PRIMARY: within-date paired — date-mean bear R minus date-mean tier-A/B long R, compared on trigger versus non-trigger dates") | −0.506 R · CI [−0.844, −0.157] | the hedge lost to the same day's long; H1 now agrees and H4's dollar arm fell to NULL | [plan](pre-registrations/f4_deployment/hedge_timing.md) |
| [`hedge_exposure` ARM M](arm-index.md#hedge_exposure "hedge_exposure ARM M: measurement only — the book on the mark-to-market curve versus the realized-on-close curve") | understates max drawdown by 40.2% | the close-bucketed curve is not the book's real worst case | [plan](pre-registrations/f4_deployment/hedge_exposure.md) |
| [`bear_deploy` D5](arm-index.md#bear_deploy "bear_deploy D5: carry the hedge only on some days — a POST-HOC gate search, labelled a candidate and not a finding") | 8 → 2 gates | the sleeve is **operator policy** now, not evidence | [plan](pre-registrations/f4_deployment/bear_deploy.md) |

**"Operator policy, not evidence"** means the rule is kept because the operator
chooses to keep it, not because a study supports it. The bear hedge sleeve was
adopted on `v3` evidence; that evidence reversed on `v4`, and the D4 pick rule
was PULLED. The sleeve stays on the card because holding a small bear position
is a risk preference, and a risk preference does not need a backtest to
justify it. What it does lose is protection: an evidence-backed rule has a
pre-registered rollback trigger that would take it off automatically, and a
policy rule has none. Nothing will fire to remove it, so it comes off only if
the operator decides to remove it.

`hedge_concentration` deserves its own paragraph, because its verdict is easy
to misread. The intended question was the one you would expect: when the book
is concentrated in a few correlated names, does buying a put help? That is
stage 2, and **stage 2 never ran.** Stage 1 is a gate in front of it, and it
asks something narrower:
[`hedge_concentration` ARM K](arm-index.md#hedge_concentration "hedge_concentration ARM K: does a session's any-cluster concentration predict the book's forward 20-session mark-to-market drawdown? Tercile contrast plus Spearman rho, block-bootstrapped")
measures whether how concentrated the book is on a given session predicts how
far it draws down over the next 20 sessions. It does not. Spearman ρ is +0.00
on 166 dates. That is a **powered** null, meaning the sample was large enough
that the flat answer is the answer and not just thin data. With no link
between concentration and drawdown, a concentration-triggered hedge has
nothing to trigger on, so the τ×f grid was never priced. Graded and closed
2026-09-04. The instrument — whether a put helps at all — is still
unmeasured, and would need a different trigger to be worth testing.

### Exit-rule attempts 1–13, the original tuning log

Indexed one line each, with the dated study sections that replaced the
numbering after attempt 13, in [`archive/README.md`](archive/README.md)
§Section index — whose last rows continue into [`current.md`](current.md).

## What is open

Priority order from [`next-steps.md`](next-steps.md)
[§2](next-steps.md#s2). The §-numbers are stable labels, not a ranking.
Two of them are now closed. They keep their numbers so older entries that
cite them still resolve, but nothing is waiting on either.

### Closed, listed here only because their numbers are still cited

- **`concurrency_correlation`** ([§2.0](next-steps.md#s2-0)) — **CLOSED
  2026-09-04**. Built, run on both eras, **NOISE** on each. No arm clears
  [X2](pre-registrations/f4_deployment/concurrency_correlation.md "concurrency_correlation criterion X2 GAIN: paired within-date mean gain in R against the unmodified deployed book")
  (does capping concurrency actually gain anything?) or
  [X3](pre-registrations/f4_deployment/concurrency_correlation.md "concurrency_correlation criterion X3 NOT NOISE: the arm's gain must exceed ARM N's 95th percentile — ARM N being random book-state labels matched on affected count")
  (is that gain bigger than randomly shuffled book states?) in either era, so
  none is eligible to adopt.
  [X4](pre-registrations/f4_deployment/concurrency_correlation.md "concurrency_correlation criterion X4 ERA STABILITY: X2 and X3 must hold on both eras, v3 and current")
  asks for era stability and was settled by hand: the *verdict* is the same in
  both eras, the per-arm gains are not.
- **`hedge_concentration` grading** ([§2.1](next-steps.md#s2-1)) — **CLOSED
  2026-09-04**. Graded under the two-analyst protocol, and
  **PRECONDITION-NULL** stands on the 166-date book. The trigger that was
  supposed to switch a hedge on is dead. The hedge instrument itself was never
  measured — see the deployment table above.

### Still open

1. **v4 composition bridge** ([§2.2](next-steps.md#s2-2)) — `v4_bridge` prints
   `LADDER UNVALIDATED ON v4` with all five tests shifting on 166 dates. It
   waits on genuinely new, non-backfill signal dates before anything is
   re-derived. The 2026 backfill dates do not qualify.
2. **Calendar-as-hedge** ([§2.3](next-steps.md#s2-3)) — **BLOCKED ON NEW
   DATES**. [`calendar_hedge` H3](arm-index.md#calendar_hedge "calendar_hedge criterion H3 SIZING: the largest hedge size f whose max drawdown and worst single date are both no worse than carrying no hedge") is
   the sizing criterion: is there any hedge size that does not make the book's
   worst day or worst drawdown worse? It has answered NOT MET, then
   DEPLOYABLE, then NOT MET on three consecutive exports. A criterion that
   changes answer every export is a measurement problem, not a finding.
3. **Bear sub-0.50 give-back** ([§2.4](next-steps.md#s2-4)) — the `be_after`
   route is closed, having been reverted, but the underlying give-back pattern
   is not refuted. The trigger that reverted it un-fired on the 140-date book
   and fired again on the 166-date one, on the 2026 column. Three censuses,
   three answers. Nothing un-reverts without a fresh registration.
4. **Live walk-forward** ([§2.5](next-steps.md#s2-5)) — still the intended
   evidence source, with no recorded progress since 2026-08-13. A missing log
   entry means nobody wrote one, not that nothing happened, so check the
   live-loop artifacts before re-planning.
5. **Rollback triggers** ([§2.6](next-steps.md#s2-6)) — a rollback trigger is a
   pre-registered condition that would take a shipped rule back off. Each one
   names its own gate: a minimum number of rows or dates before it may be read
   at all. **Read a trigger only at its gate, and read the census, not the
   absence of an alarm.** A trigger that has printed nothing has usually not
   reached its gate, which is not the same as passing it.

   | Trigger | Census (2026-08-24) | Outcome |
   |---|---|---|
   | Bear-debit `be_after 0.50` | 92 rows / 53 dates ≥ floor 60 | **FIRED → REVERTED** |
   | LVOL tef-null | 31 dates ≥ floor 25 | all four criteria pass — **CLEARED**, operator **HELD** the ship |
   | BEAR_HE trail | 1 date of floor 25 | **UNDERPOWERED** |
   | Credit sl-none | 0 fresh `bull_put` rows of 15 | **UNDERPOWERED** |

   The LVOL row moved after that census: it reads `STAYS GATED` on the
   2026-09-04 export ([`current.md`](current.md#state-of-play)).

6. **Parked or blocked long-term** ([§2.7](next-steps.md#s2-7)) — five things,
   each blocked on something different.

   | Parked item | Blocked on |
   |---|---|
   | Credit exit knobs | a credit-heavy window; every historical winner is the one March TSLA cluster |
   | Long-dated blind spot | real option price history for plays with a `horizon` of 180 or 720 days. **Debit side only** — the operator does not hold credit that long, so no credit-exit work waits on this. Never substitute BS proxy rows |
   | Per-regime exit switch | `STAYS GATED` on this book |
   | [`portfolio_delta` ARM B](arm-index.md#portfolio_delta "portfolio_delta ARM B: net-delta ceiling band, 1.0/1.5/2.0/2.5/infinity times equity") ceiling 1.50 | an independent window; queued as CANDIDATE-FOR-INDEPENDENT-WINDOW |
   | `analysis_pipeline/core.py` refactor, 20 stuck backfill partials | nothing; deferred by choice |

7. **`invalidation_exit`** ([§2.8](next-steps.md#s2-8)) — the exit engine still
   ignores each analysis row's free-text `invalidation` condition. It is the one
   item the old 2026-06 backlog left open; everything else there was refuted,
   fixed or superseded
   ([`archive/00`](archive/00-backtest-engine-backlog-2026-06.md)).

### Standing rules — settled, do not re-open

- `score_total` is decision-irrelevant, a tie-break only. Selection is
  structure × regime × entry geometry.
- The ML and selection search is closed. Re-open it only on new columns, never
  on new models.
- v3 and v4 rows are never pooled. v4's score scale, 0–50 and 0–55 for
  VOLATILITY, is not comparable to v3's 0–100.
- Studies are era-scoped. The bare export filename does not name a population;
  `lib/era.py` is the single encoding.
- [`exit_basis`](glossary.md#exit_basis) is readable on v4 and unreadable and scrambled on v3 and
  earlier. Never use it to answer a REPLAY question in any era.
- ARM labels are study-local. Always cite `study ARM X`, never a bare `ARM X`
  ([`arm-index.md`](arm-index.md)).
- `study_review … --dry-run` **overwrites** review and digest artifacts. Never
  use it as a read-only check.
- Never hardcode a figure off one export, in code or in prose.

## Reading order for more depth

1. [`next-steps.md`](next-steps.md) — the live queue and repo state, read first.
2. [`current.md`](current.md) — the [State of play](current.md#state-of-play)
   block at the top, then dated entries newest-first for the full evidence
   trail.
3. [`study-map.md`](study-map.md) — one page per study family, what each study
   asked and concluded.
4. [`docs/deployment-rules.md`](../docs/deployment-rules.md) — the operator
   card: what to actually do on a deploy morning.
5. [`deployment-evidence.md`](deployment-evidence.md) — why each card rule
   ships, its numbers, and its rollback triggers.
6. [`archive/`](archive/) — via [`README.md`](README.md) §Section index only.
   Do not browse archive files directly without that map.
