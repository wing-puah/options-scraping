# Archive — the tuning log by period

Everything older than [`../current.md`](../current.md) is split by period into
the volumes below. When `current.md` grows past about 400 lines, its oldest
sections move into a new volume here and gain a row in the section index at the
foot of this page.

**Every volume carries a status line** directly under its title. It reads
`_Status: historical (covers …). Conclusions stand as of <date>._`, or names
what superseded it after a `Superseded / qualified by:` label, as a link to the
document and section that changed plus a few words on what changed. Read the top
of any volume for the shape. The line exists because an agent sometimes reaches
a volume by grep rather than by link, and a confident conclusion with no marker
reads as current. Add the line when a volume is created. When later work
qualifies or refutes something in an older volume, update THAT volume's line.
The status stamp is the only thing in `archive/` that is meant to change.

Paths in these volumes predate 2026-08-11 and still say `backtests/study/`. The
code they name is now under `scripts/backtest_study/`.

## The volumes

| Volume | Covers | Topic |
|---|---|---|
| [`00-backtest-engine-backlog-2026-06.md`](00-backtest-engine-backlog-2026-06.md) | 2026-06-24/25, triaged 2026-08-15 | Backtest-engine backlog, triaged; not the live queue |
| [`01-exit-rules-attempts-1-7.md`](01-exit-rules-attempts-1-7.md) | 2026-06 | Baseline through Attempt 7: the first exit-rule grid |
| [`02-credit-debit-split-attempts-8-12.md`](02-credit-debit-split-attempts-8-12.md) | 2026-07-04 to 07-07 | Credit/debit split, Attempts 8 to 12, next-open entry basis |
| [`03-evaluations-attempt-13.md`](03-evaluations-attempt-13.md) | 2026-07-08 to 07-17 | MFE/MAE framework evaluations, Attempt 13, scoring keep/drop |
| [`04-pooled-evals-and-ladder.md`](04-pooled-evals-and-ladder.md) | 2026-07-18 to 07-20 | Pooled evaluations and the first deployment ladder |
| [`05-pooled-evals-762-and-regime-labels.md`](05-pooled-evals-762-and-regime-labels.md) | 2026-07-21 to 07-22 | The 762-row gate, regime-label validation, regime-gap backfill |
| [`06-mech-regime-and-shipped-exits.md`](06-mech-regime-and-shipped-exits.md) | 2026-07-22 | 25-date gate closed, mechanical-regime overlay, shipped exits |
| [`07-bear-put-demotion-thread-and-holdout.md`](07-bear-put-demotion-thread-and-holdout.md) | 2026-07-22 to 2026-08-04 | The bear_put demotion thread and the Feb to Apr 2026 holdout |
| [`08-pre-engine-book-and-year-split.md`](08-pre-engine-book-and-year-split.md) | 2026-07-27 to 2026-08-08 | Pre-engine discretionary book, year split, long-dated blind spot |
| [`09-v3-closeout.md`](09-v3-closeout.md) | 2026-08-11 | Completed book, the ML null, the DEPLOY arm, v3 close-out |
| [`10-post-closeout-ops-and-live-evals.md`](10-post-closeout-ops-and-live-evals.md) | 2026-08-12 | Rules split, v4 bridge deviation, live loop, live-vs-analysis evals |
| [`11-exit-conditioning.md`](11-exit-conditioning.md) | 2026-08-12 | Edge status, bear MFE give-back, the `be_after` grid, day-0 conditioning |
| [`12-wrappers-and-vol-sleeve.md`](12-wrappers-and-vol-sleeve.md) | 2026-08-12 | The `bear_rewrap` wrapper and the `vol_sleeve` study |
| [`13-account-sim-and-calendar-hedge.md`](13-account-sim-and-calendar-hedge.md) | 2026-08-13 | `account_sim` and `calendar_hedge`: registrations, runs, caps |
| [`14-volume-signal-demotion-and-audit.md`](14-volume-signal-demotion-and-audit.md) | 2026-08-13 | `volume_signal`, the demotion mechanism, method audit, compounding arm |
| [`15-era-scoping-suite-repair-and-selection-order.md`](15-era-scoping-suite-repair-and-selection-order.md) | 2026-08-14 to 08-15 | Era scoping, study-suite repair, `selection_order`, `--live-select` |
| [`16-first-runs-on-v3.md`](16-first-runs-on-v3.md) | 2026-08-19 | First runs of the v3-era studies, plus their replication reviews |
| [`17-v4-refresh-bear-deploy-and-vocabulary.md`](17-v4-refresh-bear-deploy-and-vocabulary.md) | 2026-08-22 to 08-27 | Verdict vocabulary, the v4 refresh, `bear_deploy`, `concurrency_correlation` |
| [`18-hedge-programme-exit-basis-and-text-loop.md`](18-hedge-programme-exit-basis-and-text-loop.md) | 2026-08-28 to 09-02 | The hedge programme, `exit_basis` re-measured, the text loop closed |

## Section index

| Section | File |
|---------|------|
| Baseline | [archive/01](01-exit-rules-attempts-1-7.md) |
| Attempt 1 — WORSE ❌ | [archive/01](01-exit-rules-attempts-1-7.md) |
| Attempt 2 — WORSE ❌ | [archive/01](01-exit-rules-attempts-1-7.md) |
| Attempt 3 — BETTER, exit config now stable ✓ | [archive/01](01-exit-rules-attempts-1-7.md) |
| Attempt 4 — WORSE ❌ (trailing-on-profit-target) | [archive/01](01-exit-rules-attempts-1-7.md) |
| Attempt 5 — IDENTICAL ❌ | [archive/01](01-exit-rules-attempts-1-7.md) |
| Attempt 6 — BETTER ✓ (profit_target 0.60) | [archive/01](01-exit-rules-attempts-1-7.md) |
| Rules of thumb learned so far | [archive/01](01-exit-rules-attempts-1-7.md) |
| What actually drives losses — confidence, not regime | [archive/01](01-exit-rules-attempts-1-7.md) |
| The real next step: confidence-based position sizing | [archive/01](01-exit-rules-attempts-1-7.md) |
| Financing & IVSpread gates (2026-06-19) | [archive/01](01-exit-rules-attempts-1-7.md) |
| Attempt 7 — BETTER ✓ (profit_target=0.90 + trailing stop) | [archive/01](01-exit-rules-attempts-1-7.md) |
| Attempt 8 — Credit/debit split (2026-07-04) | [archive/02](02-credit-debit-split-attempts-8-12.md) |
| Attempt 9 — underlying-price exit study for credits ❌ | [archive/02](02-credit-debit-split-attempts-8-12.md) |
| Attempt 10 — BETTER ✓ (debit trailing stop removed) | [archive/02](02-credit-debit-split-attempts-8-12.md) |
| Attempt 11 — credit re-check on 18 rows ❌ | [archive/02](02-credit-debit-split-attempts-8-12.md) |
| Proxy backtest for untested plays (2026-07-06) | [archive/02](02-credit-debit-split-attempts-8-12.md) |
| Entry basis changed: EOD → next-day OPEN (2026-07-06) | [archive/02](02-credit-debit-split-attempts-8-12.md) |
| Attempt 12 — next_open re-baseline + grouped exit study | [archive/02](02-credit-debit-split-attempts-8-12.md) |
| 2026-07-08 — Framework evaluation on MFE/MAE basis | [archive/03](03-evaluations-attempt-13.md) |
| 2026-07-12 — Three-run evaluation (v1 / v2 / v3) | [archive/03](03-evaluations-attempt-13.md) |
| Attempt 13 — bear_call vetoed + credit stop removed ✓ | [archive/03](03-evaluations-attempt-13.md) |
| 2026-07-17 — Power check; scoring-column keep/drop | [archive/03](03-evaluations-attempt-13.md) |
| 2026-07-19 — Final evaluation at 607 pooled rows | [archive/04](04-pooled-evals-and-ladder.md) |
| 2026-07-18 — Early pooled power check at 523 rows | [archive/04](04-pooled-evals-and-ladder.md) |
| 2026-07-19 — Deployment ladder (`docs/deployment-rules.md`) | [archive/04](04-pooled-evals-and-ladder.md) |
| 2026-07-20 — Next-25 backtest dates: regime-gap selection | [archive/04](04-pooled-evals-and-ladder.md) |
| 2026-07-21 — ≥800-GATE EVALUATION at 762 pooled priced rows | [archive/05](05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-21 — Edge status: honest assessment + priority queue | [archive/05](05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-21 — Regime-label validation: 86 MARKET rows | [archive/05](05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-22 — Regime-gap backfill: the 13 remaining dates | [archive/05](05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-22 — 25-date gate CLOSED at 913 pooled priced | [archive/06](06-mech-regime-and-shipped-exits.md) |
| 2026-07-22 addenda 1–10 — mech_regime overlay, shipped BEAR_HE trail, `exit_basis`, `mech_cell`, SPY/VIX in Drive | [archive/06](06-mech-regime-and-shipped-exits.md) |
| 2026-07-22 addenda 11–14 — bear_put: cancellation, structure-keyed trail, pre-registration, DEMOTE verdict | [archive/07](07-bear-put-demotion-thread-and-holdout.md) |
| 2026-07-22 — Feb–Apr 2026 bear holdout: coverage + backfill status | [archive/07](07-bear-put-demotion-thread-and-holdout.md) |
| 2026-07-27 — the pre-engine discretionary book, and the long-dated blind spot | [archive/08](08-pre-engine-book-and-year-split.md) |
| 2026-08-08 — year-split evaluation on refreshed exports: 2025 IS the outlier | [archive/08](08-pre-engine-book-and-year-split.md) |
| 2026-08-11 — completed-book analysis: holdout coverage FULL, DEMOTE fires at n=164 | [archive/09](09-v3-closeout.md) |
| 2026-08-11 addendum — `bs_options_hist` DROPPED: attenuating + replay-contaminating | [archive/09](09-v3-closeout.md) |
| 2026-08-11 addendum — `mech_cell` BACKFILLED across the analysis tabs | [archive/09](09-v3-closeout.md) |
| 2026-08-11 — ML combination search RUN: NULL RESULT; bear `be_after` finding | [archive/09](09-v3-closeout.md) |
| 2026-08-11 — DEPLOY arm: hedge is real, `|delta| high` pick adopted | [archive/09](09-v3-closeout.md) |
| 2026-08-11 — v4 emission-composition bridge: PRE-REGISTRATION | [pre-registrations/f1_selection/v4_bridge.md](../pre-registrations/f1_selection/v4_bridge.md) |
| 2026-08-11 — v3 CLOSE-OUT: three findings SHIPPED, production delta measured | [archive/09](09-v3-closeout.md) |
| 2026-08-12 — deployment rules split: operator card vs evidence | [archive/10](10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — v4 bridge: RECORDED DEVIATION from the pre-registration | [archive/10](10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — live loop promoted to tracked code + fill mapper | [archive/10](10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — v1 → v2 → v3 prompt-version comparison + June live-vs-analysis audit | [archive/10](10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — Stage 1 live-vs-tier eval on July | [archive/10](10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — deployment reference stats added to the operator card | [archive/10](10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — edge status after close-out: real, narrow, NOT selection-tunable | [archive/11](11-exit-conditioning.md) |
| 2026-08-12 — bear MFE give-back below the breakeven-stop threshold (candidate, not run) | [archive/11](11-exit-conditioning.md) |
| 2026-08-12 — `be_after` grid RUN: does NOT ship; give-back pattern is in the underlying | [archive/11](11-exit-conditioning.md) |
| 2026-08-12 — day-0 underlying move: ARM C does not clear, no rule; sensitivity is structural | [archive/11](11-exit-conditioning.md) |
| 2026-08-12 — `bear_rewrap`: the WRAPPER is worth +0.085 but does not hold up | [archive/12](12-wrappers-and-vol-sleeve.md) |
| 2026-08-12 — `vol_sleeve`: PRE-REGISTRATION | [pre-registrations/f3_structure/vol_sleeve.md](../pre-registrations/f3_structure/vol_sleeve.md) |
| 2026-08-12 — `vol_sleeve` RUN: the sleeve DOUBLES DOWN; the calendar is the only survivor | [archive/12](12-wrappers-and-vol-sleeve.md) |
| 2026-08-13 — `account_sim`: PRE-REGISTRATION ($25k feasibility, caps, nothing ships) | [pre-registrations/f4_deployment/account_sim.md](../pre-registrations/f4_deployment/account_sim.md) |
| 2026-08-13 — `account_sim` RUN: caps survive, window doesn't; delta binds, not cash; grammar gap | [archive/13](13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `calendar_hedge` RUN: R4 exact; H2 power-stopped at n=6, corr wrong-signed; needs new dates | [archive/13](13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `calendar_hedge --arm S` RUN: 30/30 cells power-stopped; condor NOT EVALUABLE (39.9%); hedge programme blocked on new dates | [archive/13](13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `calendar_hedge`: PRE-REGISTRATION (calendar candidate + gated ARM S sweep) | [pre-registrations/f3_structure/calendar_hedge.md](../pre-registrations/f3_structure/calendar_hedge.md) |
| 2026-08-13 — `account_sim` SIZING ARM ($1,000/position, per-pos 0.40x, net 3.00x) | [archive/13](13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `account_sim` made CONFIG-DRIVEN (`config/account-sim.yml`) | [archive/13](13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `account_sim` caps reconfigured to 0.25x / 2.50x | [archive/13](13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — method-config audit: −25 veto RETIRED, OIConfirm dropped, codex engine retired | [archive/14](14-volume-signal-demotion-and-audit.md) |
| 2026-08-13 — bear_put demotion mechanism CHOSEN: card veto §1.4, hedge sleeve carved out | [archive/14](14-volume-signal-demotion-and-audit.md) |
| 2026-08-13 — `volume_signal`: PRE-REGISTRATION | [pre-registrations/f2_management/volume_signal.md](../pre-registrations/f2_management/volume_signal.md) |
| 2026-08-13 — `volume_signal` RUN: NULL — the volume column is closed | [archive/14](14-volume-signal-demotion-and-audit.md) |
| 2026-08-13 — `account_sim` COMPOUNDING arm: costs money on this book; A2/A5 do not transfer | [archive/14](14-volume-signal-demotion-and-audit.md) |
| 2026-08-14 — `selection_order`: PRE-REGISTRATION (six ordering arms, O4 random control, G0 power pre-check) | [pre-registrations/f4_deployment/selection_order.md](../pre-registrations/f4_deployment/selection_order.md) |
| 2026-08-14 — `selection_order` RUN: POWER-STOPPED at G0 — 7–14% of the book moves, nothing read, nothing refuted | [archive/15](15-era-scoping-suite-repair-and-selection-order.md) |
| 2026-08-14 — study-suite triage: DEBIT_PROD exact-replay gate unsatisfiable; `bear_position_study` R partly contaminated | [archive/15](15-era-scoping-suite-repair-and-selection-order.md) |
| 2026-08-15 — structure-name defect FIXED: `bear put debit spread` backtested as a single long option; v4 re-run, v3 frozen | [archive/15](15-era-scoping-suite-repair-and-selection-order.md) |
| 2026-08-14 — three carried follow-ups closed: verdict grammar TOTAL, ARM H sizing floor skips, criterion (4) reworded | [archive/15](15-era-scoping-suite-repair-and-selection-order.md) |
| 2026-08-14 — `run --all` GREEN: two dead studies RETIRED, designed refusal now a runner status | [archive/15](15-era-scoping-suite-repair-and-selection-order.md) |
| 2026-08-14 — study-suite triage FIXED: gate classifies instead of asserting; `exit_basis` column UNUSABLE | [archive/15](15-era-scoping-suite-repair-and-selection-order.md) |
| 2026-08-15 — `account_sim --live-select` ARM ADDED: shipped selector run under history; 150 unpriceable candidates, 37 below-top-3 slots, §1.3 veto gap | [archive/15](15-era-scoping-suite-repair-and-selection-order.md) |
| 2026-08-15 — `enrich_queue_pilot` COMPLETE: kill switch NOT fired (deployed yield 9/10); queues a/b GO | [archive/15](15-era-scoping-suite-repair-and-selection-order.md) |
| 2026-08-19 — `account_sim` on v4: the date floor is not a density floor | [archive/16](16-first-runs-on-v3.md) |
| 2026-08-19 — `calendar_hedge` R4: a gate keyed to a snapshot is not a gate | [archive/16](16-first-runs-on-v3.md) |
| 2026-08-19 — `macro_event_study` first run (v3): tight windows UNDERPOWERED; NFP only readable cell; ARM X trigger fired, then killed by the survival control | [archive/16](16-first-runs-on-v3.md) |
| 2026-08-19 — `staged_exit` first run (v3): reactive-exit null EXTENDS to scheduled switches; 0 of 36 powered cells clears the CI | [archive/16](16-first-runs-on-v3.md) |
| 2026-08-19 — `emission_timing` first run (v3): ARM L LAG-TOLERANT (no decay within three sessions); ARM P NULL | [archive/16](16-first-runs-on-v3.md) |
| 2026-08-19 — `financed_spread` first run (v3): all seven cells NULL; naked short HARMFUL; post-scrape run’s one CANDIDATE (F4-d20 HOLD) | [archive/16](16-first-runs-on-v3.md) |
| 2026-08-19 — `portfolio_delta` first run (v3): NOISE on the primary; ladder is LONG-ONLY BY CONSTRUCTION | [archive/16](16-first-runs-on-v3.md) |
| 2026-08-19 — Disagreement logs, four-study + `financed_spread` replication reviews | [archive/16](16-first-runs-on-v3.md) |
| 2026-08-22 — "POWER STOP" RETIRED for UNDERPOWERED; `ml_combination` v4 debut FIXED | [archive/17](17-v4-refresh-bear-deploy-and-vocabulary.md) |
| 2026-08-22 — `concurrency_correlation`: PRE-REGISTRATION (ladder DEPTH is not the problem, book SIZE is unmeasured) | [pre-registrations/f4_deployment/concurrency_correlation.md](../pre-registrations/f4_deployment/concurrency_correlation.md) · [archive/17](17-v4-refresh-bear-deploy-and-vocabulary.md) |
| 2026-08-24 — v4 refresh evaluated: first rollback-trigger census (`be_after` REVERTED), credit book calibrates, `exit_mechanism_study` repaired; ARM P "candidate" OFF-BASIS | [archive/17](17-v4-refresh-bear-deploy-and-vocabulary.md) |
| 2026-08-24 — `bear_deploy` registered and graded: pick line PULLED, sleeve = operator policy, far-OTM prohibition retained; D1 window check made fail-closed | [archive/17](17-v4-refresh-bear-deploy-and-vocabulary.md) |
| 2026-08-24 — docs: ARM labels STUDY-LOCAL (`arm-index.md`); pre-registrations consolidated to one template; `ml-plan.md` split and deleted | [archive/17](17-v4-refresh-bear-deploy-and-vocabulary.md) |
| 2026-08-27 — full-suite re-run on the 140-date book; one HARD row blocks the debit exit family; two fixes (reports repaired, HYG boundary-tie widened) unblock it | [archive/17](17-v4-refresh-bear-deploy-and-vocabulary.md) |
| 2026-08-28 — `hedge_timing` (f4, NEW): GAP-UP CONTRARY, §4 prohibition drafted and HELD; chop / broad decline NULL; strict streak UNTESTABLE | [archive/18](18-hedge-programme-exit-basis-and-text-loop.md) |
| 2026-08-29 — feasibility pass for the queued max-drawdown hedge study (design notes, not a registration) | [archive/18](18-hedge-programme-exit-basis-and-text-loop.md) |
| 2026-08-31 — `hedge_exposure`: built, run, verdict-less by design; two errata; independent audit F8–F16; RATIFIED population `all` → UNDERPOWERED + MEASUREMENT-ONLY (curve understates max DD by 40.2%) | [archive/18](18-hedge-programme-exit-basis-and-text-loop.md) |
| 2026-08-31 — `study_review` inlines a study’s errata as authority; ARM M’s understatement recorded against D3 / H3 / H4 | [archive/18](18-hedge-programme-exit-basis-and-text-loop.md) |
| 2026-08-31 — `hedge_concentration` REGISTERED off a plan-time census, then BUILT and RUN the same night: PRECONDITION-NULL, and a POWERED one | [archive/18](18-hedge-programme-exit-basis-and-text-loop.md) |
| 2026-09-02 — `exit_basis` re-measured: the ban was right for v3 and WRONG for v4 (485/485 labelled); the proxy half never wrote at all | [archive/18](18-hedge-programme-exit-basis-and-text-loop.md) |
| 2026-09-02 — `exit_basis` now AUDITED, not trusted: three one-directional checks, reporting only | [archive/18](18-hedge-programme-exit-basis-and-text-loop.md) |
| 2026-09-02 — the text ↔ backtest loop BUILT and first-run: text NULLS (`exit_from_text` CONTRARY on bull calls, `prompt_eval` at the variance floor); thread closed | [archive/18](18-hedge-programme-exit-basis-and-text-loop.md) |
| 2026-09-04 — first export with 2026 signal dates (166 dates, 13 in 2026); full-suite re-run: no headline verdict moves, the per-year clause bites for the first time (bear-debit `be_after` census re-FIRES on 2026, `next_day_move` ARM R and `exit_from_text` E2 lose their candidates, `portfolio_delta` keeps only B 1.00); campaign b closed | [current.md](../current.md) |
