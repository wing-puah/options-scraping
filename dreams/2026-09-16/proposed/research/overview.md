# Research overview

Lost the thread? Start here. Terms are defined in [`glossary.md`](glossary.md),
study-local labels such as `ARM P` or `B2` in [`arm-index.md`](arm-index.md),
and the house style for writing any of this down in
[`writing-guide.md`](writing-guide.md).

Written 2026-09-02, refreshed 2026-09-05, regenerated 2026-09-16 by the weekly
dream (`../DREAM.md`). This page is a derived summary of the
[State of play](current.md#state-of-play) block in [`current.md`](current.md),
of [`next-steps.md`](next-steps.md) and of [`study-map.md`](study-map.md).
It adds nothing to them. When any of those disagrees with this page, they win
and this page is stale.

## Where things stand

Figures, populations and the export provenance are in one place: the
[State of play](current.md#state-of-play) block at the top of
[`current.md`](current.md). These bullets only say which way to look.

- Era `v4` is current. `v3` is frozen, and is the era every shipped rule was
  derived on. The two are never pooled (see Standing rules below).
- The population was refreshed 2026-09-08: the 193-date backfilled book, 598
  real results over 193 dates, 1,665 proxy rows, a pooled study book of 1,374
  rows over 208 dates, signal dates 2024-01-10 to 2026-05-07
  ([the population](current.md#the-population)).
- **Every verdict on this page was read on the 166-date book of 2026-09-04.**
  The 42 dates of queues C, D and E landed 2026-09-08 and no study has run
  since, so the numbers below are the last recorded ones, not this book's.
  The suite is stale and is to be re-run once, deliberately
  ([`next-steps.md`](next-steps.md) [§0](next-steps.md#s0)).
- The book carries 2026 signal dates, so every "ex-2026" and "positive in every
  year" cut is live. Every study still prints the verdict word it printed on
  the 140-date book; what moved is underneath the verdict, and the 2026 column
  is negative in most cells
  ([where the 2026 column bit](current.md#where-the-2026-column-bit)).
- Nothing new ships. Two studies produced a first-time candidate and both are
  held, because the new dates are a correlated backfill window rather than a
  fresh one ([two firsts](current.md#two-firsts-that-hold-rather-than-ship)).
- The hedge programme is closed on triggers and open on the instrument. The
  gap-up prohibition in [§4](../docs/deployment-rules.md#s4) was accepted on
  2026-09-06; the sleeve stays, and WHEN to open a hedge is an open item with
  no candidate ([`next-steps.md`](next-steps.md) [§2.10](next-steps.md#s2-10)).
- The v3 to v4 transfer of the deployment rules is unvalidated. `v4_bridge`
  prints `VERDICT: LADDER UNVALIDATED ON v4`, and on the 166-date book all
  five pre-registered composition tests shift. Per its
  [pre-registration](pre-registrations/f1_selection/v4_bridge.md), keep
  deploying under the v3-derived rules and do not re-derive the ladder on v4
  rows yet ([`next-steps.md`](next-steps.md) [§2.2](next-steps.md#s2-2)).
- The daily journal is collecting the live walk-forward. On 2026-09-09 the
  sessions that predate the daily loop were replayed into it, so it covers
  every session since analysis coverage began; Stage 2, the live-vs-tier
  P&L reading, is not written ([§2.5](next-steps.md#s2-5)).
- Repo state, the stale suite, the option-history cache loss and restore, and
  the known data gaps are in [`next-steps.md`](next-steps.md)
  [§0](next-steps.md#s0).

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
`mech_regime_recut` and `exit_switch_mech_study` on 2026-07-22. The
`hedge_sizing` D4 pick rule ("`|delta|` descending") was **PULLED** on the
2026-08-24 v4 re-read, so the sleeve is held as operator policy rather than
as evidence. The §4 gap-up prohibition was accepted 2026-09-06 and rests on
`hedge_timing`'s paired-[R](glossary.md#r) arms alone
([the hedge programme](current.md#the-hedge-programme)).

One rule shipped and then came off. The bear-debit peak-triggered breakeven
stop (`be_after: 0.50`) shipped 2026-08-11. Its own pre-registered rollback
trigger **FIRED** on the 2026-08-24 census and it was **REVERTED**. The census
has since given three answers on three runs, the latest re-firing on the 2026
column alone; the stop is already off, so it asks for nothing, and a 60-row
floor on a backfilling book is not a decision procedure
([`next-steps.md`](next-steps.md) [§2.4](next-steps.md#s2-4),
[§2.6](next-steps.md#s2-6)).

Each rollback trigger is checked at its gate, with numbers. A trigger that
printed nothing has not been checked, and that is not the same as "not met".
Reading on the 166-date book ([rollback triggers](current.md#rollback-triggers)):

| Trigger | On this export | What it waits on |
|---|---|---|
| Bear-debit `be_after 0.50` | re-fired on 199 arming rows over 110 dates, 2026 −0.0431; already reverted | nothing |
| LVOL tef-null | `STAYS GATED` on 73 affected dates, median −0.033; the 2026-08-24 `CLEARED` did not survive two exports, so the operator's hold was right | new dates |
| BEAR_HE trail | `UNDERPOWERED` at 1 date of 25 | new dates |
| Credit sl-none | 0 of 15, unreachable by backfill because the window starts after 2026-07-13 | live dates after July 2026 |

## What was tried and did not survive

Grouped by the five study families: `f1_selection` → `f2_management` →
`f3_structure` → `f4_deployment` → `f5_hedging`, or "pick it, manage it, wrap
it, fund it, protect it".
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

Every figure below is on the 166-date `v4` book of 2026-09-04, the last run.
Terms used: [n vs dates](glossary.md#n-vs-dates), [LOO](glossary.md#loo),
[meanR](glossary.md#meanr), [CI](glossary.md#ci).

### Selection — "which plays are worth taking?"

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`bear_position_study`](study-results/f1_selection/bear_position_study.md) | **DEMOTE TO VETO** | all three pre-registered demote criteria fire on n=368 | — |
| [`bear_arm`](study-results/f1_selection/bear_arm.md) | **NO** | 0 of 496 pre-defined bear subsets clear the rule | [plan](pre-registrations/f1_selection/bear_arm.md) |
| [`ml_combination`](study-results/f1_selection/ml_combination.md) | **NULL RESULT** | 0 of 15 model × strategy cells beat the score-free ladder out of sample | [plan](pre-registrations/f1_selection/ml_combination.md) |
| [`macro_event_study`](study-results/f1_selection/macro_event_study.md) | **UNDERPOWERED**, and ARM X **DE-QUEUED** as `SURVIVAL-ARTIFACT` | every FOMC, minutes, CPI and PCE cell is underpowered, and the one raw trigger died under the survival control | [plan](pre-registrations/f1_selection/macro_event_study.md) |
| [`emission_timing`](study-results/f1_selection/emission_timing.md) [ARM P](arm-index.md#emission_timing "emission_timing ARM P: persistence — does a re-emitted play, the 2nd/3rd/4th of a ticker plus structure, do worse than the first emission?") | **NULL** | the v3-primary read spans zero; two sub-cuts flipped sign in 2026 | [plan](pre-registrations/f1_selection/emission_timing.md) |
| [`trigger_entry`](study-results/f1_selection/trigger_entry.md) | **LATE-ENTRY** on v4 and v3 | entering only when the stated trigger is crossed picks a better book, and the confirmation costs what it is worth | [plan](pre-registrations/f1_selection/trigger_entry.md) |
| [`text_features`](study-results/f1_selection/text_features.md) | every feature **NULL** or **UNDERPOWERED** | the model's own prose separates nothing within structure × tier; the text thread is closed as an edge search | [plan](pre-registrations/f1_selection/text_features.md) |

Detail behind those clauses.

| Study | Figure | What it means |
|---|---|---|
| `bear_position_study` | ex-window mean E −0.222, CI [−0.349, −0.087] | a selection verdict on E, the exit-free number; on R the same rows no longer separate | — |
| [`bear_arm` B1](arm-index.md#bear_arm "bear_arm criterion B1: selection conditioning — is there a bear subset, definable at decision time, that is not negative?") | 0 of 496 subsets | this is the "NO" in the table above | [plan](pre-registrations/f1_selection/bear_arm.md) |
| [`bear_arm` B2](arm-index.md#bear_arm "bear_arm criterion B2: exit fit — is the base exit profile mis-tuned for bear rows? B2 shipped be_after 0.50 on 2026-08-11 and its own rollback trigger reverted it on 2026-08-24") | exit-fix criteria MET for the first time by `sl .50 (tighter)`, Δ=+0.039, CI [+0.004, +0.071] | a read off a correlated window, so it holds a rule and promotes nothing | [plan](pre-registrations/f1_selection/bear_arm.md) |
| `ml_combination` | 2026 −0.251 | its "at least 2 of 3 years" clause is a real three-year test for the first time, passing on the two old years and failing on the new one | [plan](pre-registrations/f1_selection/ml_combination.md) |
| [`emission_timing` ARM P](arm-index.md#emission_timing "emission_timing ARM P: persistence — does a re-emitted play, the 2nd/3rd/4th of a ticker plus structure, do worse than the first emission?") | candidates 3 → 1 | two sub-cuts flipped sign in 2026 | [plan](pre-registrations/f1_selection/emission_timing.md) |
| `text_features` [ARM B](arm-index.md#text_features "text_features ARM B: blind-labelled thesis type and confidence") | label coverage 89.3% | the label cache does not cover the new rows, so no ARM B line is quotable until a live-label re-run | [plan](pre-registrations/f1_selection/text_features.md) |

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
| [`volume_signal`](study-results/f2_management/volume_signal.md) | **NULL** | `PATH-VOL-PROXY`: MFE and MAE move together with no R separation; the volume column is closed | [plan](pre-registrations/f2_management/volume_signal.md) |
| [`next_day_move`](study-results/f2_management/next_day_move.md) | **NULL** | [ARM C](arm-index.md#next_day_move "next_day_move ARM C: the confound control — hold the day-0 mark fixed and repeat the conformity cut inside bands of day-0 P&L, so the effect cannot just be day-0 P&L in disguise") never clears its confound control, so there is no rule | — |
| [`staged_exit`](study-results/f2_management/staged_exit.md) | **NULL** | zero candidates out of the 51 powered cells of 96, on the 166-date v4 book | [plan](pre-registrations/f2_management/staged_exit.md) |
| [`exit_from_text`](study-results/f2_management/exit_from_text.md) | **No CANDIDATE**; E1 **CONTRARY** on `bull_call_spread` / LVOL | the model's own invalidation level as a stop cuts that structure's winners; §2.8 is closed on it | [plan](pre-registrations/f2_management/exit_from_text.md) |
| [`exit_drawdown`](study-results/f2_management/exit_drawdown.md) | **UNDERPOWERED** on every PRIMARY cell | the purged walk-forward leaves too few out-of-sample dates behind the burn-in; the two powered `all` cells are NULL | [plan](pre-registrations/f2_management/exit_drawdown.md) |

Detail behind the NULL rows.

[`next_day_move` ARM R](arm-index.md#next_day_move "next_day_move ARM R: the rule — a pre-registered day-0 cut, graded against the shipped exit profile, run on three populations: whole book, all debit, bear debit") asks whether a bear debit play should be
closed on day 0 — the entry session — when the underlying moves against it.
Three versions of the rule were tried, and each earns a `**` only if its paired
CI excludes zero **and** every [LOO](glossary.md#loo) fold is positive. On the
bear-debit population all three had that marker before, and all three lost it
in the 2026-09-04 run: every CI now straddles zero, and the 2026 column is
negative on each.

| Version | paired CI | 2026 (n=21) |
|---|---|---|
| wrong sign | [−0.005, +0.148] | −0.153 |
| worse than −0.5σ | [−0.003, +0.090] | −0.143 |
| inside the flat band | [−0.011, +0.177] | −0.258 |

The study also has a `v3` run, and the two eras are never pooled, so nothing
here carries over to the frozen era
([record](study-results/f2_management/next_day_move.md)).

`staged_exit` asks a different question: having held a position to session 5,
10, 15 or 20, does acting on where it stands then beat leaving the shipped
exit rule ([§5](../docs/deployment-rules.md#s5)) alone? Of its 96 cells, 51
had enough data to read, and none produced a candidate. Six cells have a CI
excluding zero and **all six are HARMFUL** (for example ARM E, session 20,
R ≥ +0.25, ΔR −0.033, CI [−0.054, −0.011]), so they are evidence against
acting rather than for it: the reactive null of Attempts 1, 2 and 10 extends
to scheduled switches, now with a measured cost
([record](study-results/f2_management/staged_exit.md)).

`exit_drawdown` moves the same question to the account level: does any exit
rule chosen without look-ahead reduce the deployed book's mark-to-market
drawdown without giving back its edge? Every PRIMARY cell is UNDERPOWERED,
the outcome its registration named as most likely. On the disclosed `all`
cut, from which no verdict is read, the two powered cells are NULL. Its design
is parked on dates, not refuted ([§2.7](next-steps.md#s2-7)).

### Structure — "am I expressing the signal in the wrong wrapper?"

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`bear_rewrap`](study-results/f3_structure/bear_rewrap.md) | **NULL** for naive re-wraps | the diagonal re-wrap fails the every-year gate on its first look at 2026 | — |
| [`financed_spread`](study-results/f3_structure/financed_spread.md) | **RE-WRAP** for F3 off1, everything else NULL | the one real gain is the same exposure again; the v3 F4-d20 candidate is still under its rows floor | [plan](pre-registrations/f3_structure/financed_spread.md) |
| [`ladder_overlay`](study-results/f3_structure/ladder_overlay.md) | **NOT YET RUN** | registered 2026-09-10; waits on a scrape of 11,502 contracts | [plan](pre-registrations/f3_structure/ladder_overlay.md) |

`bear_rewrap` needs a table of its own; `financed_spread` is a line.

`bear_rewrap` re-prices each bear debit play as if it had been wrapped a
different way. The **diagonal** re-wrap rolls the long leg out to the next
cached expiry and leaves the short leg where it is, turning a vertical into a
diagonal. It is one of three re-wraps tried, not a cut of the population. This
study has no pre-registration file; its five ship gates are fixed in the module
(`bear_rewrap.py::report_criteria`). The diagonal passes four of them.

| `bear_rewrap` diagonal gate | Result |
|---|---|
| paired CI excludes zero | PASS (dR +0.205, CI [+0.059, +0.360]) |
| every [LOO](glossary.md#loo) fold positive | PASS (MIN +0.171 over 119 folds) |
| both window re-cuts positive | PASS |
| right-signed in both pricing tiers | PASS |
| same sign every year | **FAIL** — 2024 +0.195, 2025 +0.259, 2026 −0.106 |

In the same run its [ARM P](arm-index.md#bear_rewrap "bear_rewrap ARM P: portfolio contribution — P1 worst-decile mean R, P2 correlation with the deployed sleeve") portfolio checks came back MET for the
first time (P1 n=16, +0.499, CI [+0.202, +0.743]; P2 −0.326). One gate failing
and one arm newly passing is a candidate, not a ship.

| Study | Figure | Where it stands |
|---|---|---|
| [`financed_spread` F3](arm-index.md#financed_spread "financed_spread F3: same-direction financed vertical") off1 | 6 of 7 criteria, dR +0.217, CI [+0.056, +0.401] | prints RE-WRAP; the one failure is the anti-re-wrap correlation E3, and its fixed-contracts control spans zero | [plan](pre-registrations/f3_structure/financed_spread.md) |
| [`financed_spread` F4](arm-index.md#financed_spread "financed_spread F4: diagonal financing, added by amendment 1 on 2026-08-19")-d20 hold | 36 rows / 33 dates against a rows floor of 60 | UNDERPOWERED a third time | [plan](pre-registrations/f3_structure/financed_spread.md) |

### Deployment — "can I actually run this?"

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`account_sim`](study-results/f4_deployment/account_sim.md) | `>>> FEASIBLE <<<` on caps, but the window does not survive | delta-notional binds before cash does; feasibility only, nothing ships | [plan](pre-registrations/f4_deployment/account_sim.md) |
| [`selection_order`](study-results/f4_deployment/selection_order.md) | **ORDERING-IS-NOISE** | no arm separates from the O4 null band on 166 dates | [plan](pre-registrations/f4_deployment/selection_order.md) |
| [`concurrency_correlation`](study-results/f4_deployment/concurrency_correlation.md) | **NOISE** on both eras | neither the size of the open book nor its internal similarity degrades per-position outcome; closed 2026-09-04 | [plan](pre-registrations/f4_deployment/concurrency_correlation.md) |
| [`portfolio_delta`](study-results/f4_deployment/portfolio_delta.md) | **CANDIDATE-FOR-INDEPENDENT-WINDOW**, B ceiling 1.00 only | a 1.00× net-delta ceiling clears every one of its adoption criteria at once, on the dense-episode population | [plan](pre-registrations/f4_deployment/portfolio_delta.md) |

The figures behind those.

| Study | Figure | What it means |
|---|---|---|
| [`account_sim` A1 / A3](glossary.md#criteria-a1a6 "account_sim criterion A1: edge survival — mean R positive, CI excludes zero, every year positive. A3: no blowup — drawdown bound, no ledger violation") | 2026 −0.062 · 35.7% drawdown | FEASIBLE is a two-year, dense-episode claim only; the full book fails both | [plan](pre-registrations/f4_deployment/account_sim.md) |
| [`selection_order` G0](pre-registrations/f4_deployment/selection_order.md "selection_order gate G0 POWER PRE-CHECK: runs first and blocks every read below it; under 25 affected dates and nothing is read") | powered since 08-27 | but the primary population has no 2026 term at all, and the secondary's 2026 cell is 3 dates | [plan](pre-registrations/f4_deployment/selection_order.md) |
| `concurrency_correlation` [X4](pre-registrations/f4_deployment/concurrency_correlation.md "concurrency_correlation criterion X4 ERA STABILITY: X2 and X3 must hold on both eras, v3 and current") | 4 of the 8 arms powered in both eras flip sign | the verdict is era-stable, the per-arm gains are not | [plan](pre-registrations/f4_deployment/concurrency_correlation.md) |
| [`portfolio_delta` ARM B](arm-index.md#portfolio_delta "portfolio_delta ARM B: net-delta ceiling band, 1.0/1.5/2.0/2.5/infinity times equity") 1.50 | primary CI spans zero · secondary 2026 −0.0878 | dropped out 2026-09-04; only ceiling 1.00 clears, and nothing ships off a correlated window | [plan](pre-registrations/f4_deployment/portfolio_delta.md) |

### Hedging — "what protects the book when the ladder is wrong?"

Three modules were renamed 2026-09-08 after the question each answers:
`bear_deploy` → `hedge_sizing`, `calendar_hedge` → `hedge_structure`,
`hedge_exposure` → `hedge_portfolio`. Labels and figures are unchanged. The
spine is [`f5_hedging/README.md`](../scripts/backtest_study/f5_hedging/README.md).

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`hedge_sizing`](study-results/f5_hedging/hedge_sizing.md) | D1–D4 **NOT MET** | the hedge-is-real and pick-rule estimands that held on v3 reverse on v4 | [plan](pre-registrations/f5_hedging/hedge_sizing.md) |
| [`hedge_structure`](study-results/f5_hedging/hedge_structure.md) | **BLOCKED ON NEW DATES** | the sizing criterion answers differently on every export; R2 fails on five post-fold rows of the 2026-09-08 export | [plan](pre-registrations/f5_hedging/hedge_structure.md) |
| [`hedge_timing`](study-results/f5_hedging/hedge_timing.md) | GAP-UP came back **CONTRARY** | the hedge underperformed the same day's ladder-eligible long; survivors 0 of 9 | [plan](pre-registrations/f5_hedging/hedge_timing.md) |
| [`hedge_portfolio`](study-results/f5_hedging/hedge_portfolio.md) | **UNDERPOWERED** on the mechanism, **MEASUREMENT-ONLY** on ARM M | all nine hedge cells fail the power gate | [plan](pre-registrations/f5_hedging/hedge_portfolio.md) |
| [`hedge_concentration`](study-map.md#hedging) | **PRECONDITION-NULL** | the gate question failed, so the hedge itself was never tested — see below; merged into `hedge_portfolio --admitted` | plan and record deleted 2026-09-08 (git `44bbfb2`) |
| [`vol_sleeve`](study-map.md#hedging) | **CLOSED** | the straddle clears its gate then dies out of sample, and correlates the wrong sign with the deployed book; retired into `hedge_structure` gate R4 | plan and record deleted 2026-09-08 (git `44bbfb2`) |

The figures behind those.

| Study | Figure | What it means |
|---|---|---|
| [`hedge_sizing` D5](arm-index.md#hedge_sizing "hedge_sizing D5: carry the hedge only on some days — a POST-HOC gate search, labelled a candidate and not a finding") | 8 → 2 gates | the sleeve is **operator policy** now, not evidence | [plan](pre-registrations/f5_hedging/hedge_sizing.md) |
| [`hedge_structure` H0](arm-index.md#hedge_structure "hedge_structure criterion H0 FILL: the sleeve must produce a fillable hedge on at least 60% of deployed-book dates and at least 60% of the deployed book's worst-decile dates") | fills 51.0% of deployed dates | the gate is 60% | [plan](pre-registrations/f5_hedging/hedge_structure.md) |
| [`hedge_structure` H2](arm-index.md#hedge_structure "hedge_structure criterion H2 HEDGE CONTRIBUTION: negative daily correlation, positive mean sleeve R on the book's worst-decile dates, positive worst-quartile tail in two or more years") | n=4 | not evaluable | [plan](pre-registrations/f5_hedging/hedge_structure.md) |
| [`hedge_timing` ARM H3](arm-index.md#hedge_timing "hedge_timing ARM H3, the PRIMARY: within-date paired — date-mean bear R minus date-mean tier-A/B long R, compared on trigger versus non-trigger dates") | −0.506 R · CI [−0.844, −0.157] | the hedge lost to the same day's long; H1 now agrees and H4's dollar arm fell to NULL | [plan](pre-registrations/f5_hedging/hedge_timing.md) |
| [`hedge_portfolio` ARM M](arm-index.md#hedge_portfolio "hedge_portfolio ARM M: measurement only — the book on the mark-to-market curve versus the realized-on-close curve") | understates max drawdown by 40.2% | the close-bucketed curve is not the book's real worst case | [plan](pre-registrations/f5_hedging/hedge_portfolio.md) |
| `vol_sleeve` | +0.220 on 166 dates | only the calendar wrapper is right-signed against the book | plan and record deleted 2026-09-08 (git `44bbfb2`) |

**"Operator policy, not evidence"** means the rule is kept because the operator
chooses to keep it, not because a study supports it. The bear hedge sleeve was
adopted on `v3` evidence; that evidence reversed on `v4`, and the D4 pick rule
was PULLED. The sleeve stays on the card because holding a small bear position
is a risk preference, and a risk preference does not need a backtest to
justify it. What it does lose is protection: an evidence-backed rule has a
pre-registered rollback trigger that would take it off automatically, and a
policy rule has none. Nothing will fire to remove it, so it comes off only if
the operator decides to remove it.

`hedge_concentration`'s verdict is easy to misread, so it gets its own
paragraph. The question anyone would expect — when the book is concentrated
in a few correlated names, does buying a put help? — is stage 2, and
**stage 2 never ran**, because stage 1, the gate in front of it, failed.
Stage 1 asks something narrower:
[`hedge_concentration` ARM K](arm-index.md#hedge_concentration "hedge_concentration ARM K: does a session's any-cluster concentration predict the book's forward 20-session mark-to-market drawdown? Tercile contrast plus Spearman rho, block-bootstrapped")
measures whether how concentrated the book is on a given session predicts how
far it draws down over the next 20 sessions. It does not: Spearman ρ is +0.00
on 166 dates, a **powered** null — the sample was large enough that the flat
answer is the answer, not just thin data. With no link between concentration
and drawdown, a concentration-triggered hedge has nothing to trigger on, so
the τ×f grid was never priced. Graded and closed 2026-09-04. The instrument
itself — whether a put helps at all — is still unmeasured, and would need a
different trigger to be worth testing. Everything powered in the hedge
programme is about the TRIGGER; "not shown to work" is the absence of a
measurement, not a measurement of absence.

### Exit-rule attempts 1–13, the original tuning log

Indexed one line each, with the dated study sections that replaced the
numbering after attempt 13, in [`archive/README.md`](archive/README.md)
§Section index — whose last rows continue into [`current.md`](current.md).
The lessons those attempts learned, and re-learned in later volumes, are one
line each in [`lessons.md`](lessons.md).

## What is open

Priority order from [`next-steps.md`](next-steps.md)
[§2](next-steps.md#s2). The §-numbers are stable labels, not a ranking;
pick-up order is roughly §2.2, §2.5, §2.10, §2.9, then the parked items as
dates arrive. Most of the queue waits on genuinely new dates: the live
analysis dates from 2026-08-11 onward, which have no backtest rows until
their options expire. The 42 backfill dates of queues C, D and E do not
qualify, because they sit inside the same correlated window.

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
  measured — see the hedging table above. Do not register a fourth trigger
  study over these dates and columns.
- **Per-play `invalidation` exits** ([§2.8](next-steps.md#s2-8)) — **CLOSED
  2026-09-02, do not build**. `exit_from_text` answered it: the model's own
  invalidation level as a stop is CONTRARY on `bull_call_spread` / LVOL and
  NULL or UNDERPOWERED elsewhere. It was the one item the old 2026-06 backlog
  left open ([`archive/00`](archive/00-backtest-engine-backlog-2026-06.md)).

### Still open

1. **v4 composition bridge** ([§2.2](next-steps.md#s2-2)) — `v4_bridge` prints
   `LADDER UNVALIDATED ON v4` with all five tests shifting on 166 dates. It
   waits on genuinely new, non-backfill signal dates before anything is
   re-derived. Do not lower `MIN_V4_DATES`; its exit 3 is a designed refusal.
2. **Calendar-as-hedge** ([§2.3](next-steps.md#s2-3)) — **BLOCKED ON NEW
   DATES**. [`hedge_structure` H3](arm-index.md#hedge_structure "hedge_structure criterion H3 SIZING: the largest hedge size f whose max drawdown and worst single date are both no worse than carrying no hedge") is
   the sizing criterion: is there any hedge size that does not make the book's
   worst day or worst drawdown worse? It has answered NOT MET, then
   DEPLOYABLE, then NOT MET on three consecutive exports. A criterion that
   changes answer every export is a measurement problem, not a finding. The
   far leg is now fetchable (`fetch_far_legs.py`, 2026-09-08); the study's R2
   gate, not the cache, is what blocks the read.
3. **Bear sub-0.50 give-back** ([§2.4](next-steps.md#s2-4)) — the `be_after`
   route is closed, having been reverted, but the underlying give-back pattern
   is not refuted. The trigger that reverted it un-fired on the 140-date book
   and fired again on the 166-date one, on the 2026 column. Three censuses,
   three answers. Nothing un-reverts without a fresh registration. Held, not
   queued: `bear_arm` B2's exit-fix criteria are MET for the first time by
   `sl .50`, a correlated-window read that promotes nothing.
4. **Live walk-forward** ([§2.5](next-steps.md#s2-5)) — the daily journal
   (`make journal`) IS the Stage 1 fill mapping, and on 2026-09-09 the
   sessions that predate the daily loop were replayed into it. Stage 2, the
   live-vs-tier P&L reading, is NOT written. Census on 2026-09-09: 55 mapped
   rows over 20 signal dates against the `operator_read` floor of 25 dates;
   22 mapped closes, all tier B or C, against a Stage 2 gate of 30 to 50; no
   tier-A close yet, so the A > B > C question cannot be posed. The
   operator-read test (f4, `operator_read`) is to be pre-registered here
   before any code, with a census first.
5. **Rollback triggers** ([§2.6](next-steps.md#s2-6)) — three of the four wait
   on new dates; the readings are in the production section above. **Read a
   trigger only at its gate, and read the census, not the absence of an
   alarm.** A trigger that has printed nothing has usually not reached its
   gate, which is not the same as passing it.
6. **Parked or blocked long-term** ([§2.7](next-steps.md#s2-7)) — each blocked
   on something different, none scheduled.

   | Parked item | Blocked on |
   |---|---|
   | Credit exit knobs | a credit-heavy window; the fresh window starts after 2026-07-13, so no backfill can reach it |
   | Long-dated blind spot | real option price history for `h ≥ 180`; the BS proxy tier is OFF and never read as long-dated evidence. **Debit side only** (operator, 2026-09-05): the credit knobs do not wait on this |
   | Per-regime exit switch | `STAYS GATED` on the 166-date book; two of six criteria still fail |
   | [`portfolio_delta` ARM B](arm-index.md#portfolio_delta "portfolio_delta ARM B: net-delta ceiling band, 1.0/1.5/2.0/2.5/infinity times equity") ceiling 1.00 | an independent window; CANDIDATE-FOR-INDEPENDENT-WINDOW, nothing ships. Ceiling 1.50 dropped out 2026-09-04 |
   | `exit_drawdown`'s design | dates, not design; any CANDIDATE would need the independent window |
   | `hedge_portfolio` ARM C prose control | materially more parsed dates; deferred from §2.1, not dropped |
   | `analysis_pipeline/core.py` refactor and the hooks | nothing; deferred by choice |

7. **`prompt_eval`** ([§2.9](next-steps.md#s2-9)) — a STABILITY item, not an
   edge item, and it waits behind §2.2. The PROD × 3 variance run set the floor
   below which no difference may be claimed; the one candidate worth writing
   is a written BULL/RANGE/BEAR decision rule over rollup fields, tested for
   repeatability before P&L. Do not write the "adopt `mech_regime`" candidate.
8. **A hedge-open indicator** ([§2.10](next-steps.md#s2-10)) — OPEN with no
   candidate. Another timing rule cut from these dates and columns does not
   count; hedge flow in the analysis or a live exposure reading from the
   journal, measured on the mark-to-market curve on dates chosen without a
   rule, would. Census first: three of the four dead triggers died on power.
9. **Robustness follow-ups** ([§2.11](next-steps.md#s2-11)) — nothing waits on
   dates. Twelve items built; six committed and six merged to main on
   2026-09-08 (`3e5c2dc`), which added the cost model and the pre-entry grid
   fix the next suite run picks up. Open from that merge: the proxy rows carry
   none of the three new columns, `history.py` still unlinks a cache file
   before a refetch that can fail, and B5's zero-bid re-mark is not mirrored by
   `bear_rewrap`'s reconstruction, which blocks `hedge_structure` at R2 and is
   the operator's call. Three drafts (`cost_sensitivity`, `mechanical_benchmark`,
   `holdout_seal`) are not registered.
10. **Hedge programme follow-ups** ([§2.12](next-steps.md#s2-12)) — both picked
    up 2026-09-08. The far-call collector is built and run; the read waits on
    the R2 decision above. The two sleeve-sizing bodies are folded onto
    `lib/hedge_criteria.sleeve_pick`, identical print, closed.
11. **`ladder_overlay` first run** ([§2.13](next-steps.md#s2-13)) — registered
    2026-09-10, waits on a scrape of 11,502 contracts; then `push` the cache
    backup, run it, run the `--era v3` companion, review, write up.

### Standing rules — settled, do not re-open

One line each; the evidence is in [`next-steps.md` §3](next-steps.md#s3).

- `score_total` is decision-irrelevant, a tie-break only. Selection is
  structure × regime × entry geometry.
- The ML and selection search is closed. Re-open it only on new columns, never
  on new models.
- Trigger-gated entry is LATE-ENTRY; the day-X / ±Y% / ±$Z exit formula is
  `staged_exit` and it is null; walk-forward exit selection on account-level
  drawdown is `exit_drawdown` and it is UNDERPOWERED. Do not re-register any of
  them on these dates. No further text study.
- `bear_call_spread` is intake-vetoed; bear debit is selection-vetoed at
  [§1](../docs/deployment-rules.md#s1) and lives in the
  [§4](../docs/deployment-rules.md#s4) sleeve only.
- v3 and v4 rows are never pooled. v4's score scale, 0–50 and 0–55 for
  VOLATILITY, is not comparable to v3's 0–100. Real and tweak pricing tiers
  only; filter legacy `bs` rows by `proxy_method`.
- Studies are era-scoped. The bare export filename does not name a population;
  `lib/era.py` is the single encoding.
- [`exit_basis`](glossary.md#exit_basis) is readable on v4 and unreadable and scrambled on v3 and
  earlier. Never use it to answer a REPLAY question in any era.
- `hedge_portfolio`'s registration describes the `real` stratum, not the
  ratified `all` book.
- ARM labels are study-local. Always cite `study ARM X`, never a bare `ARM X`
  ([`arm-index.md`](arm-index.md)).
- A rollback trigger with no recorded census has not been checked. It is not
  "not met" until the numbers say so.
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
6. [`lessons.md`](lessons.md) — the core-lesson register, one line per lesson
   with the volume that learned it; cite the line instead of restating it.
7. [`archive/`](archive/) — via [`README.md`](README.md) §Section index only.
   Do not browse archive files directly without that map.
