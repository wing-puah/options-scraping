# Research overview

Lost the thread? Start here. Terms are defined in [`glossary.md`](glossary.md),
study-local labels such as `ARM P` or `B2` in [`arm-index.md`](arm-index.md),
and the house style for writing any of this down in
[`writing-guide.md`](writing-guide.md).

Written 2026-09-02, refreshed 2026-09-04. This page is a summary of
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
- Nothing new ships from that book. Two studies produced a first-time
  candidate and both are held, because the dates are backfill and correlated.
- The hedge programme is closed on triggers and open on the instrument.
  `hedge_exposure` ships nothing, `hedge_concentration` is graded
  `PRECONDITION-NULL`, a *powered* null, and §2.1 is closed. The drafted
  gap-up prohibition is still held
  ([`next-steps.md`](next-steps.md) §1, §2.1;
  [`deployment-evidence.md`](deployment-evidence.md)).
- The v3 to v4 transfer of the deployment rules is unvalidated. `v4_bridge`
  prints `VERDICT: LADDER UNVALIDATED ON v4`
  ([`scripts/study_map/catalog.py`](../scripts/study_map/catalog.py)). Per its
  [pre-registration](pre-registrations/f1_selection/v4_bridge.md), keep
  deploying under the v3-derived rules and do not re-derive the ladder on v4
  rows yet ([`next-steps.md`](next-steps.md) §2.2).
- Repo state, tests, unpriceable dates and the known data gaps are in
  [`next-steps.md`](next-steps.md) §0.

## What is in production (SHIPPED)

These are the rules live in `config/` and
[`docs/deployment-rules.md`](../docs/deployment-rules.md) today.
[CI](glossary.md#ci) means confidence interval, the
range a measured number could truly fall in. PF means profit factor.

| Rule | What it says | Era derived on | Card | Open rollback trigger |
|---|---|---|---|---|
| Debit exit profile | profit target 90%, stop −75%, time exit at 75% of DTE elapsed, no trailing stop | v3, attempt 10 | [§5](../docs/deployment-rules.md#s5) | none registered |
| `bear_call_spread` vetoed at intake; credit exit carries no stop | the §1.1 veto; the credit row rides toward expiry | v3, attempt 13 | [§1.1](../docs/deployment-rules.md#s1), [§5](../docs/deployment-rules.md#s5) | "credit sl-none", `UNDERPOWERED` |
| Score-free tiers | tier A and B deploy first, tier C and VETO are skipped | v3, 2026-07-21 | [§2](../docs/deployment-rules.md#s2), [§6](../docs/deployment-rules.md#s6) | none |
| `bull_put_spread` geometry band | 0.08 ≤ \|δ\| ≤ 0.20, DTE ≤ 59, prefer 45–59; a miss drops to tier C | v3 | [§3](../docs/deployment-rules.md#s3) | provisional, re-read at the next independent window |
| `mech_cell`-keyed BEAR_HE trail | arm at +50%, then trail 50 points from peak on a mech BEAR+H/E-VOL signal date | v3, 2026-07-22 | [§5](../docs/deployment-rules.md#s5) | "BEAR_HE trail", `UNDERPOWERED` |
| Bear debit selection veto plus hedge-sleeve carve-out | bear (`bear_put_spread`, `long_put`) never enters the deployed top-3, and may only be held deliberately as a ≤½-size hedge | v3 mechanism, chosen 2026-08-13 | [§1.4](../docs/deployment-rules.md#s1), [§4](../docs/deployment-rules.md#s4) | D4 pick rule PULLED |

A few of those cells need a sentence. Tiers are structure × regime × entry
geometry, and `score_total` is a tie-break only. The BEAR_HE trail is the one
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
to `false` ([`next-steps.md`](next-steps.md) §1, §2.4).

## What was tried and did not survive

Grouped by the four study families: `f1_selection` → `f2_management` →
`f3_structure` → `f4_deployment`, or "pick it, manage it, wrap it, fund it".
Verdict words are copied verbatim from
[`scripts/study_map/catalog.py`](../scripts/study_map/catalog.py), the
hand-written verdict file, unless noted. "n" is sample size and
[LOO](glossary.md#loo) is leave-one-out, scoring a fold the
rule was never tuned on.

### Selection — "which plays are worth taking?"

| Study | Verdict | Why |
|---|---|---|
| [`bear_position_study`](study-results/f1_selection/bear_position_study.md) | **DEMOTE TO VETO** | all three pre-registered demote criteria fire on n=368 |
| [`bear_arm`](study-results/f1_selection/bear_arm.md) | **NO** | 0 of 496 pre-defined bear subsets clear the rule |
| [`ml_combination`](study-results/f1_selection/ml_combination.md) | **NULL RESULT** | 0 of 15 model × strategy cells beat the score-free ladder out of sample |
| [`macro_event_study`](study-results/f1_selection/macro_event_study.md) | **UNDERPOWERED**, and ARM X **DE-QUEUED** as `SURVIVAL-ARTIFACT` | every FOMC, minutes, CPI and PCE cell is underpowered, and the one raw trigger died under the survival control |
| [`emission_timing`](study-results/f1_selection/emission_timing.md) [ARM P](arm-index.md#emission_timing) | **NULL** | the v3-primary read spans zero |

Detail behind those clauses. `bear_position_study`'s ex-window mean E is
−0.222 with CI [−0.349, −0.087]; margins narrowed on the 166-date book but none
crossed. [`bear_arm`](arm-index.md#bear_arm)'s B1 half is the "NO"; its B2 half shipped and was then
reverted, as above, and on 2026-09-04 B2's exit-fix criteria were MET for the
first time by `sl .50`, which is a correlated-window read that holds a rule and
promotes nothing. `ml_combination`'s "≥2 of 3 years" clause is a real
three-year test for the first time, at 2026 −0.251. `emission_timing` ARM P
lost two sub-cuts to a 2026 sign flip on the 166-date book, so its candidates
went 3 → 1.

That one survivor is `emission_timing`'s other half, ARM L
(`LAG-TOLERANT`): a 1–3 session fill delay does not decay the signal. It is
the one live selection candidate and it has shipped nothing.

### Management — "when do I get out?"

Both shipped exit rules came from this family.

| Study | Verdict | Why |
|---|---|---|
| `combined_exit_study` | **RETIRED** | inputs were gitignored scratch, deleted and unrecoverable |
| `underlying_exit_study` | **RETIRED** | its second input is gone the same way; the recorded verdict was "nothing shipped" |
| [`bear_giveback`](study-results/f2_management/bear_giveback.md) | **NULL** | the `be_after` grid does not ship; the give-back pattern lives in the underlying, not the option mark |
| [`volume_signal`](study-results/f2_management/volume_signal.md) | **NULL** | no return separation on non-bear debit, and the one frozen exit variant loses out of fold |
| [`next_day_move`](study-results/f2_management/next_day_move.md) | **NULL** | ARM C never clears its confound, so there is no rule |
| [`staged_exit`](study-results/f2_management/staged_exit.md) | **NULL** | zero candidates out of 51 of 96 cells powered on the 166-date v4 book |

`next_day_move` ARM R's bear-debit day-0 cut lost its `**` on all three cuts on
2026-09-04; the CIs straddle zero and 2026 is negative. In `staged_exit`, the
six cells whose CI excludes zero are all harmful: day-5 and day-20 loss cuts,
and early profit exits.

### Structure — "am I expressing the signal in the wrong wrapper?"

| Study | Verdict | Why |
|---|---|---|
| [`bear_rewrap`](study-results/f3_structure/bear_rewrap.md) | **NULL** for naive re-wraps | the diagonal cut fails the year clause on its first 2026 look |
| [`vol_sleeve`](study-results/f3_structure/vol_sleeve.md) | **CLOSED** | the straddle clears its gate then dies out of sample, and correlates the wrong sign with the deployed book |
| [`calendar_hedge`](study-results/f3_structure/calendar_hedge.md) | **BLOCKED ON NEW DATES** | H3 has read NOT MET / DEPLOYABLE / NOT MET on three consecutive exports, an unstable measurement |
| [`financed_spread`](study-results/f3_structure/financed_spread.md) | **UNCONFIRMED** on v4 | same-expiry shapes are NULL |

The figures. `bear_rewrap`'s diagonal is 4/5 with 2026 −0.106, while its
portfolio checks were MET for the first time in the same run, so it is a
candidate and not a ship. `vol_sleeve` is still +0.220 on 166 dates, and only
the calendar is right-signed. `calendar_hedge` H0 fills 51.0% of deployed dates
against a 60% gate, and H2 is not evaluable at n=4. `financed_spread` F3 off1
prints RE-WRAP on 166 dates at 6/7, failing only the anti-re-wrap correlation,
and the v3 candidate F4-d20 hold is still below the rows floor at 36 of 60.

### Deployment — "can I actually run this?"

| Study | Verdict | Why |
|---|---|---|
| [`account_sim`](study-results/f4_deployment/account_sim.md) | `>>> FEASIBLE <<<` on caps, but the window does not survive | delta-notional binds before cash does; feasibility only, nothing ships |
| [`selection_order`](study-results/f4_deployment/selection_order.md) | **ORDERING-IS-NOISE** | no arm separates from the O4 null band on 166 dates |
| [`portfolio_delta`](study-results/f4_deployment/portfolio_delta.md) | **CANDIDATE-FOR-INDEPENDENT-WINDOW**, B ceiling 1.00 only | B 1.00 clears the full conjunction on the dense-episode population |
| [`hedge_timing`](study-results/f4_deployment/hedge_timing.md) | GAP-UP came back **CONTRARY** | the hedge underperformed the same day's ladder-eligible long; survivors 0 of 9 |
| [`hedge_exposure`](study-results/f4_deployment/hedge_exposure.md) | **UNDERPOWERED** on the mechanism, **MEASUREMENT-ONLY** on ARM M | all nine hedge cells fail the power gate |
| [`hedge_concentration`](study-results/f4_deployment/hedge_concentration.md) | **PRECONDITION-NULL** | a *powered* null: concentration does not predict the next 20 sessions of drawdown |
| [`bear_deploy`](study-results/f4_deployment/bear_deploy.md) | D1–D4 **NOT MET** | the hedge-is-real and pick-rule estimands that held on v3 reverse on v4 |

The figures behind those. `account_sim`'s FEASIBLE is a two-year,
dense-episode claim: the full-book population fails A1 at 2026 −0.062 and A3
at 35.7% drawdown on the 166-date book. `selection_order`'s G0 has been
powered since 08-27; its primary population has no 2026 term and the
secondary's 2026 cell is n=3 dates. `portfolio_delta` B 1.50 dropped out on
2026-09-04, because the primary CI spans zero and the secondary 2026 is
−0.088, and nothing ships from a correlated window. `hedge_timing` H3 is
−0.506 R on 166 dates with CI [−0.844, −0.157], H1 now mirrors it, and H4's
dollars fell to NULL. `hedge_exposure`'s close-bucketed curve understates this
book's max drawdown by 40.2%. `hedge_concentration`'s ρ is +0.00 on 166 dates,
graded and closed 2026-09-04. `bear_deploy`'s sleeve is now operator policy
only, and its post-hoc D5 candidate gates went 8 → 2 on the 166-date book.

### Exit-rule attempts 1–13, the original tuning log

One line each. The ✓ and ❌ are copied verbatim from [`README.md`](README.md)
§Section index.

| Attempt | Result | One clause |
|---|---|---|
| 1 | ❌ WORSE | first grid pass |
| 2 | ❌ WORSE | — |
| 3 | ✓ BETTER | exit config now stable |
| 4 | ❌ WORSE | trailing-on-profit-target |
| 5 | ❌ IDENTICAL | — |
| 6 | ✓ BETTER | `profit_target 0.60` |
| 7 | ✓ BETTER | `profit_target=0.90` + trailing stop |
| 8 | — (milestone) | credit/debit split |
| 9 | ❌ | underlying-price exit study for credits |
| 10 | ✓ BETTER | debit trailing stop removed, which is today's shipped debit profile |
| 11 | ❌ | credit re-check on 18 rows |
| 12 | — (milestone) | next-open re-baseline + grouped exit study |
| 13 | ✓ | `bear_call` vetoed and credit stop removed, which is today's shipped credit and veto rule |

## What is open

Priority order from [`next-steps.md`](next-steps.md) §2. The section numbers
are stable labels, not a ranking.

1. **`concurrency_correlation`** (§2.0) — **CLOSED 2026-09-04**: built, run on
   both eras, **NOISE** on each. X4 was settled by hand: the verdict is
   era-stable, the per-arm gains are not, and no arm clears X2 or X3 in either
   era, so none is ADOPT-eligible.
2. **`hedge_concentration` grading** (§2.1) — **CLOSED 2026-09-04**: graded
   under the two-analyst protocol, and **PRECONDITION-NULL** stands on the
   166-date book. The hedge trigger is dead; the hedge instrument is unmeasured.
3. **v4 composition bridge** (§2.2) — `v4_bridge` prints `LADDER UNVALIDATED
   ON v4` with all five tests shifting on 166 dates. It waits on genuinely new,
   non-backfill signal dates before anything is re-derived. The 2026 backfill
   dates do not qualify.
4. **Calendar-as-hedge** (§2.3) — **BLOCKED ON NEW DATES**. H3 has read NOT MET
   / DEPLOYABLE / NOT MET on three consecutive exports and is recorded as an
   unstable measurement.
5. **Bear sub-0.50 give-back** (§2.4) — the `be_after` route is closed, having
   been reverted, but the underlying give-back pattern is not refuted. The
   trigger that reverted it un-fired on the 140-date book and fired again on
   the 166-date one, on the 2026 column. Three censuses, three answers. Nothing
   un-reverts without a fresh registration.
6. **Live walk-forward** (§2.5) — still the intended evidence source, with no
   recorded progress since 2026-08-13. Silence here is not evidence of no
   progress, so check the live-loop artifacts before re-planning.
7. **Rollback triggers** (§2.6) — checked at their gates, never read from
   silence.

   | Trigger | Census (2026-08-24) | Outcome |
   |---|---|---|
   | Bear-debit `be_after 0.50` | 92 rows / 53 dates ≥ floor 60 | **FIRED → REVERTED** |
   | LVOL tef-null | 31 dates ≥ floor 25 | all four criteria pass — **CLEARED**, operator **HELD** the ship |
   | BEAR_HE trail | 1 date of floor 25 | **UNDERPOWERED** |
   | Credit sl-none | 0 fresh `bull_put` rows of 15 | **UNDERPOWERED** |

   The LVOL row moved after that census: it reads `STAYS GATED` on the
   2026-09-04 export ([`current.md`](current.md#state-of-play)).

8. **Parked or blocked long-term** (§2.7) — credit exit knobs, which need a
   credit-heavy window; the long-dated (≥180 DTE) blind spot, which is
   unpriceable with the BS proxy tier off; the per-regime exit switch, which
   STAYS GATED on this book; `portfolio_delta` ARM B ceiling 1.50, queued as
   CANDIDATE-FOR-INDEPENDENT-WINDOW; 20 stuck backfill partials; and the
   deferred `analysis_pipeline/core.py` refactor.
9. **`invalidation_exit`** (§2.8) — the exit engine still ignores each analysis
   row's free-text `invalidation` condition. It is the one item the old 2026-06
   backlog left open; everything else there was refuted, fixed or superseded
   ([`archive/00`](archive/00-backtest-engine-backlog-2026-06.md)).

### Standing rules — do not re-litigate these

- `score_total` is decision-irrelevant, a tie-break only. Selection is
  structure × regime × entry geometry.
- The ML and selection search is closed. Re-open it only on new columns, never
  on new models.
- v3 and v4 rows are never pooled. v4's score scale, 0–50 and 0–55 for
  VOLATILITY, is not comparable to v3's 0–100.
- Studies are era-scoped. The bare export filename does not name a population;
  `lib/era.py` is the single encoding.
- `exit_basis` is readable on v4 and unreadable and scrambled on v3 and
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
