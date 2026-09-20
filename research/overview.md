# Research overview

Lost the thread? Start here. Terms are defined in [`glossary.md`](glossary.md),
study-local labels such as `ARM P` or `B2` in [`arm-index.md`](arm-index.md),
and the house style for writing any of this down in
[`writing-guide.md`](writing-guide.md).

Written 2026-09-02, refreshed 2026-09-05, regenerated 2026-09-17 by the weekly
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
- **Every verdict on this page was read on the 2026-09-19 re-priced book**,
  the first full suite run since 2026-09-04. Its records are in
  [`study-results/`](study-results/README.md) and its per-study verdicts in
  [`study-map.md`](study-map.md).
- **Four verdicts moved on that run.** `account_sim` now prints NOT FEASIBLE
  AT $25,000, `portfolio_delta`'s candidate became NOISE,
  `concurrency_correlation`'s NOISE banner became RESTATEMENT, and
  `exit_from_text` printed its first CANDIDATE. What each asks of the operator
  is in [study-map.md](study-map.md#operator-reading-2026-09-20).
- The book carries 2026 signal dates, so every "ex-2026" and "positive in every
  year" cut is live. The 2026 column was negative in most cells on the
  2026-09-04 book; on the re-priced one several of those cells came back
  positive, which is why per-year clauses flipped in both directions
  ([where the 2026 column bit](current.md#where-the-2026-column-bit)).
- Nothing new ships. The candidates that survive are held, because the added
  dates are a correlated backfill window rather than a fresh one
  ([two firsts](current.md#two-firsts-that-hold-rather-than-ship)).
- The hedge programme is closed on triggers and open on the instrument. The
  gap-up prohibition in [§4](../docs/deployment-rules.md#s4) was accepted on
  2026-09-06; the sleeve stays, and WHEN to open a hedge is an open item with
  no candidate ([`next-steps.md`](next-steps.md) [§2.10](next-steps.md#s2-10)).
  On the 2026-09-19 book that prohibition rests on `hedge_timing`'s primary
  paired arm alone.
- The v3 to v4 transfer of the deployment rules is unvalidated. `v4_bridge`
  prints `VERDICT: LADDER UNVALIDATED ON v4`, and four of its five
  pre-registered composition tests shift. Per its
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
`hedge_timing`'s primary paired-[R](glossary.md#r) arm
([the hedge programme](current.md#the-hedge-programme)).

One rule shipped and then came off. The bear-debit peak-triggered breakeven
stop (`be_after: 0.50`) shipped 2026-08-11. Its own pre-registered rollback
trigger **FIRED** on the 2026-08-24 census and it was **REVERTED**. The census
has since given four answers on four runs, the latest firing on all three of
its clauses; the stop is already off, so it asks for nothing, and a 60-row
floor on a backfilling book is not a decision procedure
([`next-steps.md`](next-steps.md) [§2.4](next-steps.md#s2-4),
[§2.6](next-steps.md#s2-6)).

Each rollback trigger is checked at its gate, with numbers. A trigger that
printed nothing has not been checked, and that is not the same as "not met".
Reading on the 2026-09-19 book ([rollback triggers](current.md#rollback-triggers)):

| Trigger | On this export | What it waits on |
|---|---|---|
| Bear-debit `be_after 0.50` | fired on all three clauses, 242 arming rows over 134 dates; already reverted | nothing |
| LVOL tef-null | `STAYS GATED` on 80 affected dates, median −0.011; it now fails one corrected criterion, not two | new dates |
| BEAR_HE trail | `UNDERPOWERED` at 8 dates of 25 | new dates |
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

Every figure below is on the `v4` book of the 2026-09-19 suite run.
Terms used: [n vs dates](glossary.md#n-vs-dates), [LOO](glossary.md#loo),
[meanR](glossary.md#meanr), [CI](glossary.md#ci).

### Selection — "which plays are worth taking?"

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`bear_position_study`](study-results/f1_selection/bear_position_study.md) | **DEMOTE TO VETO** | all three pre-registered demote criteria fire on n=438 | — |
| [`bear_arm`](study-results/f1_selection/bear_arm.md) | **NO** | 0 of 496 pre-defined bear subsets clear the rule | [plan](pre-registrations/f1_selection/bear_arm.md) |
| [`ml_combination`](study-results/f1_selection/ml_combination.md) | **NULL RESULT** | 0 of 15 model × strategy cells beat the score-free ladder out of sample | [plan](pre-registrations/f1_selection/ml_combination.md) |
| [`macro_event_study`](study-results/f1_selection/macro_event_study.md) | ARM X **DE-QUEUED** as `SURVIVAL-ARTIFACT` | the raw trigger no longer fires at all, and only the minutes cells are still uniformly underpowered | [plan](pre-registrations/f1_selection/macro_event_study.md) |
| [`emission_timing`](study-results/f1_selection/emission_timing.md) [ARM P](arm-index.md#emission_timing "emission_timing ARM P: persistence — does a re-emitted play, the 2nd/3rd/4th of a ticker plus structure, do worse than the first emission?") | **NULL** headline, one candidate cell beneath it | the v3-primary read spans zero, but the moved-against-the-play cut now clears all six criteria | [plan](pre-registrations/f1_selection/emission_timing.md) |
| [`trigger_entry`](study-results/f1_selection/trigger_entry.md) | **LATE-ENTRY** in every cell | entering only when the stated trigger is crossed picks a better book, and the confirmation costs more than it is worth | [plan](pre-registrations/f1_selection/trigger_entry.md) |
| [`text_features`](study-results/f1_selection/text_features.md) | every feature **NULL** or **UNDERPOWERED** | the model's own prose separates nothing within structure × tier; the text thread is closed as an edge search | [plan](pre-registrations/f1_selection/text_features.md) |

Detail behind those clauses.

| Study | Figure | What it means |
|---|---|---|
| `bear_position_study` | ex-window mean E −0.256, CI [−0.369, −0.135] | a selection verdict on E, the exit-free number; on R the same rows do not separate | — |
| [`bear_arm` B1](arm-index.md#bear_arm "bear_arm criterion B1: selection conditioning — is there a bear subset, definable at decision time, that is not negative?") | 0 of 496 subsets | this is the "NO" in the table above | [plan](pre-registrations/f1_selection/bear_arm.md) |
| [`bear_arm` B2](arm-index.md#bear_arm "bear_arm criterion B2: exit fit — is the base exit profile mis-tuned for bear rows? B2 shipped be_after 0.50 on 2026-08-11 and its own rollback trigger reverted it on 2026-08-24") | exit-fix criteria back to NOT met: `sl .50 (tighter)`, Δ=+0.030, CI [−0.003, +0.061] | the one clear it had on 2026-09-04 did not survive a re-price | [plan](pre-registrations/f1_selection/bear_arm.md) |
| `ml_combination` | 2026 −0.163 | its "at least 2 of 3 years" clause passes on the two old years and fails on the new one, while the headline interval still spans zero | [plan](pre-registrations/f1_selection/ml_combination.md) |
| [`emission_timing` ARM P](arm-index.md#emission_timing "emission_timing ARM P: persistence — does a re-emitted play, the 2nd/3rd/4th of a ticker plus structure, do worse than the first emission?") | candidates 1 → 2 | the moved-against-the-play cut regained the year criterion it failed on 2026-09-04 | [plan](pre-registrations/f1_selection/emission_timing.md) |
| `text_features` [ARM B](arm-index.md#text_features "text_features ARM B: blind-labelled thesis type and confidence") | label coverage 74.9% | the label cache covers less of the book on every re-price, so no ARM B line is quotable until a live-label re-run | [plan](pre-registrations/f1_selection/text_features.md) |

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
| [`bear_giveback`](study-results/f2_management/bear_giveback.md) | **NULL** | the `be_after` grid does not ship — every interval straddles zero — and the give-back pattern lives in the underlying | — |
| [`volume_signal`](study-results/f2_management/volume_signal.md) | **NULL** | `PATH-VOL-PROXY`: MFE and MAE move together with no R separation; the volume column is closed | [plan](pre-registrations/f2_management/volume_signal.md) |
| [`next_day_move`](study-results/f2_management/next_day_move.md) | **NULL** | [ARM C](arm-index.md#next_day_move "next_day_move ARM C: the confound control — hold the day-0 mark fixed and repeat the conformity cut inside bands of day-0 P&L, so the effect cannot just be day-0 P&L in disguise") never clears its confound control, so there is no rule | — |
| [`staged_exit`](study-results/f2_management/staged_exit.md) | **NULL** | zero candidates out of the 54 powered cells of 96 | [plan](pre-registrations/f2_management/staged_exit.md) |
| [`exit_from_text`](study-results/f2_management/exit_from_text.md) | its first **CANDIDATE**, in an intake cell; E1 **CONTRARY** in 11 cells | the model's own invalidation level as a stop cuts winners, and the one clear is an entry filter rather than an exit | [plan](pre-registrations/f2_management/exit_from_text.md) |
| [`exit_drawdown`](study-results/f2_management/exit_drawdown.md) | **UNDERPOWERED** on every PRIMARY cell | the purged walk-forward leaves too few out-of-sample dates behind the burn-in; the three powered `all` cells are NULL | [plan](pre-registrations/f2_management/exit_drawdown.md) |

Detail behind the NULL rows.

[`next_day_move` ARM R](arm-index.md#next_day_move "next_day_move ARM R: the rule — a pre-registered day-0 cut, graded against the shipped exit profile, run on three populations: whole book, all debit, bear debit") asks whether a bear debit play should be
closed on day 0 — the entry session — when the underlying moves against it.
Three versions of the rule were tried, and each earns a `**` only if its paired
CI excludes zero **and** every [LOO](glossary.md#loo) fold is positive. On the
bear-debit population all three had that marker on 2026-08-24, all three lost
it on 2026-09-04, and on the 2026-09-19 re-price one has it back.

| Version | paired CI | 2026 (n=64) |
|---|---|---|
| wrong sign | [−0.017, +0.114] | −0.035 |
| worse than −0.5σ | [+0.002, +0.082] | +0.010 |
| inside the flat band | [−0.019, +0.139] | −0.021 |

The middle row clears all six pre-registered criteria. It still makes no rule:
the gain is bear-only, the leak guard confirms nothing outside the key moves,
and cutting bear rows is `bear_position_study`'s veto arriving by another
route. ARM C is what would have to separate it from the day-0 mark, and it
does not.

The study also has a `v3` run, and the two eras are never pooled, so nothing
here carries over to the frozen era
([record](study-results/f2_management/next_day_move.md)).

`staged_exit` asks a different question: having held a position to a fixed
session, does acting on where it stands then beat leaving the shipped exit
rule ([§5](../docs/deployment-rules.md#s5)) alone? Of its 96 cells, 54 had
enough data to read, and none produced a candidate.

Eight of those cells have a confidence interval clear of zero, and **all eight
are harmful**. They are evidence against acting rather than for it: the
reactive null of Attempts 1, 2 and 10 extends to scheduled switches, with a
measured cost. Which cells qualify is not stable, though — one left the list
as two joined ([record](study-results/f2_management/staged_exit.md)).

| A harmful cell | ΔR | CI |
|---|---|---|
| ARM E, session 20, R ≥ +0.25 | −0.023 | [−0.042, −0.003] |

`exit_drawdown` moves the same question to the account level: does any exit
rule chosen without look-ahead reduce the deployed book's mark-to-market
drawdown without giving back its edge? Every PRIMARY cell is UNDERPOWERED,
the outcome its registration named as most likely. On the disclosed `all`
cut, from which no verdict is read, three cells now clear power and all are
NULL. Its design is parked on dates, not refuted
([§2.7](next-steps.md#s2-7)).

### Structure — "am I expressing the signal in the wrong wrapper?"

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`bear_rewrap`](study-results/f3_structure/bear_rewrap.md) | **NULL** for naive re-wraps | the diagonal re-wrap fails the every-year gate on its first look at 2026 | — |
| [`financed_spread`](study-results/f3_structure/financed_spread.md) | **RE-WRAP** for F4-d20 at $100, everything else NULL | the one real gain is the same exposure again, and the token has changed cell since 2026-09-04 | [plan](pre-registrations/f3_structure/financed_spread.md) |
| [`ladder_overlay`](study-results/f3_structure/ladder_overlay.md) | **NULL**, closed 2026-09-16 | no ladder or naked-put cell beats the plain spread on v4; the seven powered v3 cells are NULL too | [plan](pre-registrations/f3_structure/ladder_overlay.md) |

`bear_rewrap` needs a table of its own; `financed_spread` and `ladder_overlay`
are each a paragraph below.

`bear_rewrap` re-prices each bear debit play as if it had been wrapped a
different way. The **diagonal** re-wrap rolls the long leg out to the next
cached expiry and leaves the short leg where it is, turning a vertical into a
diagonal. It is one of three re-wraps tried, not a cut of the population. This
study has no pre-registration file; its five ship gates are fixed in the module
(`bear_rewrap.py::report_criteria`). The diagonal passes four of them.

| `bear_rewrap` diagonal gate | Result |
|---|---|
| paired CI excludes zero | PASS (dR +0.159, CI [+0.035, +0.288]) |
| every [LOO](glossary.md#loo) fold positive | PASS (MIN +0.134 over 156 folds) |
| both window re-cuts positive | PASS |
| right-signed in both pricing tiers | PASS |
| same sign every year | **FAIL** — 2024 +0.220, 2025 +0.153, 2026 −0.069 |

Its [ARM P](arm-index.md#bear_rewrap "bear_rewrap ARM P: portfolio contribution — P1 worst-decile mean R, P2 correlation with the deployed sleeve") portfolio checks have since REVERSED. They read MET for the
first time on 2026-09-04 and now read `P1 worst-decile: n= 21  meanR +0.196  CI [-0.212, +0.547]  $+4,897   -> not met`.
So the candidate has failed its year criterion on two consecutive exports and
lost the portfolio support it briefly had — neither a ship nor a refutation.

| Study | Figure | Where it stands |
|---|---|---|
| [`financed_spread` F4](arm-index.md#financed_spread "financed_spread F4: diagonal financing, added by amendment 1 on 2026-08-19")-d20 at $100 | 6 of 7 criteria, dR +0.369, CI [+0.019, +0.985] | prints RE-WRAP; the one failure is the anti-re-wrap correlation E3, and it is built from only 114 of 920 candidates | [plan](pre-registrations/f3_structure/financed_spread.md) |
| [`financed_spread` F3](arm-index.md#financed_spread "financed_spread F3: same-direction financed vertical") off1 | now NULL | it held the RE-WRAP token on 2026-09-04 and lost it on the re-price | [plan](pre-registrations/f3_structure/financed_spread.md) |

`ladder_overlay` asks whether wrapping a bull call spread in a rolled
short-call ladder, or swapping in a naked put for the core, beats running the
spread to the shipped [§5](../docs/deployment-rules.md#s5) exits. All ten
graded cells are NULL on v4; on v3 seven are NULL and three are
UNDERPOWERED. The one confidence interval clear of zero is on the wrong
side: selling the call on the entry day and rolling it costs about a quarter
of an R against the plain spread.

Waiting for a gap-up or a run before selling is the only pattern positive on
v4, and it still fails three criteria. Its interval includes zero, 2026 is a
negative year, and it correlates positively with the deployed book — the
re-wrap pattern `financed_spread` prints above. Closed 2026-09-16; nothing
ships, and the thread reopens only on genuinely new dates
([`next-steps.md`](next-steps.md) [§2.13](next-steps.md#s2-13)).

### Deployment — "can I actually run this?"

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`account_sim`](study-results/f4_deployment/account_sim.md) | **NOT FEASIBLE AT $25,000 — BLOWUP RISK** | the edge survives the caps and the drawdown does not; feasibility only, nothing ships | [plan](pre-registrations/f4_deployment/account_sim.md) |
| [`selection_order`](study-results/f4_deployment/selection_order.md) | **ORDERING-IS-NOISE** | no arm separates from the O4 null band, on more dates than before | [plan](pre-registrations/f4_deployment/selection_order.md) |
| [`concurrency_correlation`](study-results/f4_deployment/concurrency_correlation.md) | **RESTATEMENT**, where 2026-09-04 read NOISE | one arm now clears the gain and noise criteria, then loses under the delta control, so it restates `portfolio_delta` | [plan](pre-registrations/f4_deployment/concurrency_correlation.md) |
| [`portfolio_delta`](study-results/f4_deployment/portfolio_delta.md) | **NOISE**; the candidate is gone | the 1.00× ceiling lost criterion 1 alone when its gain halved on a larger dense-episode population | [plan](pre-registrations/f4_deployment/portfolio_delta.md) |

The figures behind those.

| Study | Figure | What it means |
|---|---|---|
| [`account_sim` A1 / A3](glossary.md#criteria-a1a6 "account_sim criterion A1: edge survival — mean R positive, CI excludes zero, every year positive. A3: no blowup — drawdown bound, no ledger violation") | A1 MET · A3 35.0% against a 25% bar | the drawdown is a Jan–Apr 2025 cluster, not the March 2026 sessions the re-price added | [plan](pre-registrations/f4_deployment/account_sim.md) |
| [`selection_order` G0](pre-registrations/f4_deployment/selection_order.md "selection_order gate G0 POWER PRE-CHECK: runs first and blocks every read below it; under 25 affected dates and nothing is read") | powered since 08-27 | but the primary population has no 2026 term at all, and the secondary's 2026 cell is 3 dates | [plan](pre-registrations/f4_deployment/selection_order.md) |
| `concurrency_correlation` [X4](pre-registrations/f4_deployment/concurrency_correlation.md "concurrency_correlation criterion X4 ERA STABILITY: X2 and X3 must hold on both eras, v3 and current") | the 2026-09-04 settlement is WITHDRAWN | it rested on no arm clearing the gain and noise criteria in either era, which is no longer true of v4 | [plan](pre-registrations/f4_deployment/concurrency_correlation.md) |
| [`portfolio_delta` ARM B](arm-index.md#portfolio_delta "portfolio_delta ARM B: net-delta ceiling band, 1.0/1.5/2.0/2.5/infinity times equity") 1.00 | +0.0519 R, CI [−0.0333, +0.1407] | six of seven criteria still pass; the gain halved and its interval now spans zero | [plan](pre-registrations/f4_deployment/portfolio_delta.md) |

### Hedging — "what protects the book when the ladder is wrong?"

Three modules were renamed 2026-09-08 after the question each answers:
`bear_deploy` → `hedge_sizing`, `calendar_hedge` → `hedge_structure`,
`hedge_exposure` → `hedge_portfolio`. Labels and figures are unchanged. The
spine is [`f5_hedging/README.md`](../scripts/backtest_study/f5_hedging/README.md).

| Study | Verdict | Why | Plan |
|---|---|---|---|
| [`hedge_sizing`](study-results/f5_hedging/hedge_sizing.md) | D2–D4 **NOT MET**; D1 found four subsets | the hedge-is-real and pick-rule estimands that held on v3 stay reversed, and D1's four survivors are fewer than chance predicts | [plan](pre-registrations/f5_hedging/hedge_sizing.md) |
| [`hedge_structure`](study-results/f5_hedging/hedge_structure.md) | **BLOCKED ON NEW DATES** | the sizing criterion answers differently on every export; R2 passes again since the 2025-04-09 re-price | [plan](pre-registrations/f5_hedging/hedge_structure.md) |
| [`hedge_timing`](study-results/f5_hedging/hedge_timing.md) | GAP-UP still **CONTRARY** on the primary arm alone | the hedge underperformed the same day's ladder-eligible long; survivors 0 of 9, and the between-date mirror went back to NULL | [plan](pre-registrations/f5_hedging/hedge_timing.md) |
| [`hedge_portfolio`](study-results/f5_hedging/hedge_portfolio.md) | **UNDERPOWERED** on the mechanism, **MEASUREMENT-ONLY** on ARM M | all nine hedge cells fail the power gate | [plan](pre-registrations/f5_hedging/hedge_portfolio.md) |
| [`hedge_concentration`](study-map.md#hedging) | **PRECONDITION-NULL** | the gate question failed, so the hedge itself was never tested — see below; merged into `hedge_portfolio --admitted` | plan and record deleted 2026-09-08 (git `44bbfb2`) |
| [`vol_sleeve`](study-map.md#hedging) | **CLOSED** | the straddle clears its gate then dies out of sample, and correlates the wrong sign with the deployed book; retired into `hedge_structure` gate R4 | plan and record deleted 2026-09-08 (git `44bbfb2`) |

The figures behind those.

| Study | Figure | What it means |
|---|---|---|
| [`hedge_sizing` D5](arm-index.md#hedge_sizing "hedge_sizing D5: carry the hedge only on some days — a POST-HOC gate search, labelled a candidate and not a finding") | still 2 gates, now costing dollars | the sleeve is **operator policy**, not evidence, and the two gates reversed sign on the re-price | [plan](pre-registrations/f5_hedging/hedge_sizing.md) |
| [`hedge_structure` H0](arm-index.md#hedge_structure "hedge_structure criterion H0 FILL: the sleeve must produce a fillable hedge on at least 60% of deployed-book dates and at least 60% of the deployed book's worst-decile dates") | fills 33.3% of deployed dates | the gate is 60%, and the rate fell as the book grew | [plan](pre-registrations/f5_hedging/hedge_structure.md) |
| [`hedge_structure` H2](arm-index.md#hedge_structure "hedge_structure criterion H2 HEDGE CONTRIBUTION: negative daily correlation, positive mean sleeve R on the book's worst-decile dates, positive worst-quartile tail in two or more years") | n=2 | not evaluable | [plan](pre-registrations/f5_hedging/hedge_structure.md) |
| [`hedge_timing` ARM H3](arm-index.md#hedge_timing "hedge_timing ARM H3, the PRIMARY: within-date paired — date-mean bear R minus date-mean tier-A/B long R, compared on trigger versus non-trigger dates") | −0.510 R · CI [−0.820, −0.190] | the hedge lost to the same day's long; H1 no longer mirrors it, because the beta control absorbed that arm | [plan](pre-registrations/f5_hedging/hedge_timing.md) |
| [`hedge_portfolio` ARM M](arm-index.md#hedge_portfolio "hedge_portfolio ARM M: measurement only — the book on the mark-to-market curve versus the realized-on-close curve") | understates max drawdown by 27.0%, from 40.2% | the close-bucketed curve is not the book's real worst case, and the gap is not a constant | [plan](pre-registrations/f5_hedging/hedge_portfolio.md) |
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

### Re-opened by the 2026-09-19 run

- **`concurrency_correlation`** ([§2.0](next-steps.md#s2-0)) — **RE-OPENED**,
  having been closed 2026-09-04. The banner is RESTATEMENT rather than NOISE.
  One arm,
  [K 5 / same-direction-and-sector](arm-index.md#concurrency_correlation "concurrency_correlation ARM K: a ceiling on how many open positions share a direction, or a direction and a sector"),
  now clears
  [X2](pre-registrations/f4_deployment/concurrency_correlation.md "concurrency_correlation criterion X2 GAIN: paired within-date mean gain in R against the unmodified deployed book")
  (does capping concurrency gain anything?) and
  [X3](pre-registrations/f4_deployment/concurrency_correlation.md "concurrency_correlation criterion X3 NOT NOISE: the arm's gain must exceed ARM N's 95th percentile — ARM N being random book-state labels matched on affected count")
  (is that gain bigger than randomly shuffled book states?), then loses the
  gain under the delta control.
- That is why the report calls it a restatement of `portfolio_delta` rather
  than a finding, and nothing is adoption-eligible either way. The
  [X4](pre-registrations/f4_deployment/concurrency_correlation.md "concurrency_correlation criterion X4 ERA STABILITY: X2 and X3 must hold on both eras, v3 and current")
  era settlement made by hand on 2026-09-04 is **withdrawn**: it rested on no
  arm clearing X2 and X3 in either era. Settling it again needs a fresh
  `--era v3` companion run.

### Closed, listed here only because their numbers are still cited
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
- **`ladder_overlay`** ([§2.13](next-steps.md#s2-13)) — **CLOSED 2026-09-16**.
  Registered 2026-09-10, run on both eras. All ten graded cells are NULL on
  v4; on v3 seven are NULL and three are UNDERPOWERED. Nothing ships; the
  thread reopens only on genuinely new dates.

### Still open

1. **v4 composition bridge** ([§2.2](next-steps.md#s2-2)) — `v4_bridge` prints
   `LADDER UNVALIDATED ON v4`, with four of five tests shifting. It
   waits on genuinely new, non-backfill signal dates before anything is
   re-derived. Do not lower `MIN_V4_DATES`; its exit 3 is a designed refusal.
2. **Calendar-as-hedge** ([§2.3](next-steps.md#s2-3)) — **BLOCKED ON NEW
   DATES**. [`hedge_structure` H3](arm-index.md#hedge_structure "hedge_structure criterion H3 SIZING: the largest hedge size f whose max drawdown and worst single date are both no worse than carrying no hedge") is
   the sizing criterion: is there any hedge size that does not make the book's
   worst day or worst drawdown worse? It has now answered differently on four
   consecutive exports, most recently DEPLOYABLE. A criterion that
   changes answer every export is a measurement problem, not a finding. The
   far leg is now fetchable (`fetch_far_legs.py`, 2026-09-08); the study's R2
   gate, not the cache, is what blocks the read.
3. **Bear sub-0.50 give-back** ([§2.4](next-steps.md#s2-4)) — the `be_after`
   route is closed, having been reverted, but the underlying give-back pattern
   is not refuted. The trigger has now given four answers on four runs, the
   latest firing on all three of its clauses. Nothing un-reverts without a
   fresh registration, and nothing needs to, because the stop is already off.
   `bear_arm` B2's exit-fix criteria, MET for the first time on 2026-09-04,
   are back to NOT met on the re-price.
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
   | Per-regime exit switch | `STAYS GATED` on the 2026-09-19 book; two of six criteria still fail |
   | [`portfolio_delta` ARM B](arm-index.md#portfolio_delta "portfolio_delta ARM B: net-delta ceiling band, 1.0/1.5/2.0/2.5/infinity times equity") ceiling 1.00 | nothing — the item comes OFF the queue. It read NOISE on 2026-09-19 and there is no candidate left to confirm |
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
