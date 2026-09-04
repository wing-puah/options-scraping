# Research overview

Written 2026-09-02, refreshed 2026-09-04. This is a SUMMARY of [`next-steps.md`](next-steps.md),
[`current.md`](current.md) and [`study-map.md`](study-map.md) — when any of
those disagrees with this page, they win and this page is stale.

## Where things stand

- **Era `v4` is current.** The book is the **166-date backfilled** one; every
  study below ran on the exports of **2026-09-04 20:31** — 535 real results /
  1,303 proxy / 2,212 analysis rows, pooled study book 1,143 rows, signal
  dates 2024-01-10 → 2026-04-16 ([`next-steps.md`](next-steps.md) §0). `v3`
  is the **frozen** era every shipped deployment rule was originally derived
  on; the two are **never pooled**.
- **The book has 2026 signal dates for the first time** — 13 of them
  (2026-01-06 → 2026-04-16, 79 pooled rows), so every "ex-2026" and "positive
  in every year" cut on this page is LIVE. Where it bit on its first run:
  the bear-debit `be_after` rollback census re-fired on the 2026 column,
  `next_day_move`'s bear-debit cut and `exit_from_text`'s pooled candidate
  lost their CIs, `portfolio_delta` kept only one ceiling, and `account_sim`'s
  full-book population fails two feasibility criteria while the dense-episode
  population that carries the verdict is still two-year
  ([`current.md`](current.md) 2026-09-04). These are still BACKFILL dates —
  the correlated window — not the genuinely new dates the rollback triggers
  and `v4_bridge` wait on.
- **Tests green, last recorded:** see [`current.md`](current.md) 2026-09-04.
- **The hedge programme is closed on triggers, open on the instrument.**
  `hedge_exposure` ships nothing; `hedge_concentration` is graded
  **PRECONDITION-NULL** (a *powered* null, unchanged on the 166-date book,
  ρ now +0.00) and §2.1 is CLOSED; the drafted GAP-UP prohibition is still
  HELD and now rests on `hedge_timing`'s paired-R arms only (H4 fell to NULL)
  ([`next-steps.md`](next-steps.md) §1, §2.1; [`deployment-evidence.md`](deployment-evidence.md)).
- **The v3→v4 transfer of the deployment rules is unvalidated.** `v4_bridge`
  prints `VERDICT: LADDER UNVALIDATED ON v4`
  ([`scripts/study_map/catalog.py`](../scripts/study_map/catalog.py)). Per
  its pre-registration: **keep deploying under the v3-derived rules**; do not
  re-derive the ladder on v4 rows yet ([`next-steps.md`](next-steps.md) §2.2).

## What is in production (SHIPPED)

These are the rules actually live in `config/` / [`docs/deployment-rules.md`](../docs/deployment-rules.md)
today. "CI" below means confidence interval — the range a measured number
could truly fall in; "PF" means profit factor.

| Rule | What it says | Era derived on | Evidence | Open rollback trigger |
|---|---|---|---|---|
| Debit exit profile | Profit target 90%, stop −75%, time exit at 75% of DTE elapsed, no trailing stop | v3 (Attempt 10) | [deployment-rules.md §5](../docs/deployment-rules.md) | none registered |
| `bear_call_spread` vetoed at intake; credit exit carries no stop | §1.1 veto; credit row rides toward expiry | v3 (Attempt 13) | [deployment-rules.md §1, §5](../docs/deployment-rules.md) | "credit sl-none": **0** fresh `bull_put` rows of 15 — UNDERPOWERED ([deployment-evidence.md](deployment-evidence.md) §"Open pre-registered rollback triggers") |
| Score-free tiers (structure × regime × entry geometry; `score_total` is a tie-break only) | Tier A/B deploy first, Tier C/VETO skipped | v3 (2026-07-21) | [deployment-rules.md §2, §6](../docs/deployment-rules.md) | none |
| `bull_put_spread` §3 geometry band (0.08 ≤ \|δ\| ≤ 0.20, DTE ≤ 59, prefer 45–59) | Miss the band → drops to Tier C | v3 | [deployment-rules.md §3](../docs/deployment-rules.md) | PROVISIONAL — re-read at the next independent window ([deployment-evidence.md](deployment-evidence.md)) |
| `mech_cell`-keyed BEAR_HE trail (arm at +50%, trail 50 pts from peak on a mech BEAR+H/E-VOL signal date) | Only debit exit that switches on the *mechanical* regime | v3 (2026-07-22, `mech_regime_recut` + `exit_switch_mech_study`) | [deployment-rules.md §5](../docs/deployment-rules.md) | "BEAR_HE trail": **1** affected date of 25 — UNDERPOWERED, census 2026-08-24 ([deployment-evidence.md](deployment-evidence.md)) |
| Bear debit selection veto (§1.4) + hedge-sleeve carve-out (§4) | Bear (`bear_put_spread`/`long_put`) never enters the deployed top-3; may only be held deliberately as a ≤½-size hedge | v3 mechanism, chosen 2026-08-13 | [deployment-rules.md §1.4, §4](../docs/deployment-rules.md) | D4 pick rule ("`\|delta\|` descending") was **PULLED** on the 2026-08-24 v4 re-read ([`scripts/study_map/catalog.py`](../scripts/study_map/catalog.py), `bear_deploy`) — the sleeve is now held as **operator policy**, not evidence |

One rule shipped and then came off: the bear-debit peak-triggered breakeven
stop (`be_after: 0.50`, shipped 2026-08-11) had its own pre-registered
rollback trigger **FIRE** on the 2026-08-24 census (2025 mean-R delta
negative) and was **REVERTED** —
`simulation.structure_exit.enabled` is back to `false`
([`next-steps.md`](next-steps.md) §1, §2.4).

## What was tried and did not survive

Grouped by the four study families (`f1_selection` → `f2_management` →
`f3_structure` → `f4_deployment`, "pick it, manage it, wrap it, fund it").
Verdict words are copied verbatim from [`scripts/study_map/catalog.py`](../scripts/study_map/catalog.py)
(the hand-written verdict file) unless noted. "n" = sample size; "LOO" =
leave-one-out (score a fold the rule was never tuned on).

### Selection — "which plays are worth taking?"

| Study | Verdict | Why (one clause) |
|---|---|---|
| `bear_position_study` | **DEMOTE TO VETO** | all three pre-registered demote criteria fire on n=368 (ex-window mean E −0.222, CI [−0.349, −0.087]); margins narrowed on the 166-date book but none crossed |
| `bear_arm` (B1 half) | **NO** | 0 of 496 pre-defined bear subsets clear the rule (B2 half shipped, then reverted — see above; on 2026-09-04 B2's exit-fix criteria were MET for the first time by `sl .50`, a correlated-window read that holds a rule and promotes nothing) |
| `ml_combination` | **NULL RESULT** | 0 of 15 model × strategy cells beat the score-free ladder out of sample; the "≥2 of 3 years" clause is a real three-year test for the first time (2026 −0.251) |
| `macro_event_study` | **UNDERPOWERED** / ARM X **DE-QUEUED** as `SURVIVAL-ARTIFACT` | every FOMC/minutes/CPI/PCE cell underpowered; the one raw trigger died under the survival control |
| `emission_timing` (ARM P) | **NULL** | v3-primary read spans zero; on the 166-date book two ARM P sub-cuts that had cleared fail on a 2026 sign flip — candidates 3 → 1 (ARM L only) |

`emission_timing`'s other half, ARM L (`LAG-TOLERANT`), is the one live
selection candidate — a 1–3 session fill delay does not decay the signal —
but it has not shipped anything.

### Management — "when do I get out?" (where both shipped exit rules came from)

| Study | Verdict | Why (one clause) |
|---|---|---|
| `combined_exit_study` | **RETIRED** | inputs were gitignored scratch, deleted and unrecoverable |
| `underlying_exit_study` | **RETIRED** | its second input is gone the same way; recorded verdict was "nothing shipped" |
| `bear_giveback` | **NULL** | the `be_after` grid does not ship; the give-back pattern lives in the **underlying**, not the option mark |
| `volume_signal` | **NULL** | no return separation on non-bear debit; the one frozen exit variant loses out-of-fold |
| `next_day_move` | **NULL** | ARM C never clears its confound, so no rule; ARM R's bear-debit day-0 cut lost its `**` on all three cuts on 2026-09-04 (CIs straddle zero, 2026 negative) |
| `staged_exit` | **NULL** | 51 of 96 cells powered on the 166-date v4 book; zero candidates, and the six cells whose CI excludes zero are all HARMFUL (day-5/day-20 loss cuts, early profit exits) |

### Structure — "am I expressing the signal in the wrong wrapper?"

| Study | Verdict | Why (one clause) |
|---|---|---|
| `bear_rewrap` | **NULL** (naive re-wraps) | the diagonal cut now fails the year clause on its first 2026 look (4/5; 2026 −0.106) while its portfolio checks are MET for the first time — a candidate, not a ship |
| `vol_sleeve` | **CLOSED** | the straddle clears its gate then dies out of sample, and correlates the WRONG SIGN with the deployed book (still +0.220 on 166 dates; only the calendar is right-signed) |
| `calendar_hedge` | **BLOCKED ON NEW DATES** | H0 fill 51.0% of deployed dates (gate 60%); H2 not evaluable (n=4); H3 has read NOT MET / DEPLOYABLE / NOT MET on three consecutive exports — an unstable measurement |
| `financed_spread` | **UNCONFIRMED** on v4 | same-expiry shapes NULL; F3 off1 prints RE-WRAP on 166 dates (6/7, fails only the anti-re-wrap correlation); the v3 candidate F4-d20 hold is still below the rows floor (36 of 60) |

### Deployment — "can I actually run this?"

| Study | Verdict | Why (one clause) |
|---|---|---|
| `account_sim` | `>>> FEASIBLE <<<` (caps) — but the WINDOW does not survive | delta-notional binds before cash does; feasibility only, nothing ships. FEASIBLE is a two-year, dense-episode claim: the full-book population fails A1 (2026 −0.062) and A3 (35.7% drawdown) on the 166-date book |
| `selection_order` | **ORDERING-IS-NOISE** | G0 powered since 08-27; no arm separates from the O4 null band on 166 dates; the primary population has no 2026 term and the secondary's 2026 cell is n=3 dates |
| `portfolio_delta` | **CANDIDATE-FOR-INDEPENDENT-WINDOW** (B ceiling 1.00 only) | B 1.00 clears the full conjunction on the dense-episode population; B 1.50 dropped out on 2026-09-04 (primary CI spans zero, secondary 2026 −0.088); nothing ships from a correlated window |
| `hedge_timing` | GAP-UP came back **CONTRARY** | the hedge underperformed the same day's ladder-eligible long (H3 −0.506 R on 166 dates, CI [−0.844, −0.157]; H1 now mirrors it, H4's dollars fell to NULL); survivors 0 of 9 |
| `hedge_exposure` | **UNDERPOWERED** (mechanism) + **MEASUREMENT-ONLY** (ARM M) | all nine hedge cells fail the power gate; the close-bucketed curve understates this book's max drawdown by 40.2% |
| `hedge_concentration` | **PRECONDITION-NULL** | a *powered* null — concentration does not predict the next 20 sessions of drawdown on the admitted book (ρ +0.00 on 166 dates, graded and closed 2026-09-04) |
| `bear_deploy` (v4 re-read) | D1–D4 **NOT MET** | the hedge-is-real and pick-rule estimands that held on v3 reverse on v4; sleeve now operator policy only; post-hoc D5 candidate gates 8 → 2 on the 166-date book |

### Exit-rule Attempts 1–13 (the original tuning log)

One line each, ✓/❌ copied verbatim from [`README.md`](README.md) §Section index.

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
| 10 | ✓ BETTER | debit trailing stop removed — this is today's shipped debit profile |
| 11 | ❌ | credit re-check on 18 rows |
| 12 | — (milestone) | next-open re-baseline + grouped exit study |
| 13 | ✓ | `bear_call` vetoed + credit stop removed — this is today's shipped credit/veto rule |

## What is open

Priority order from [`next-steps.md`](next-steps.md) §2. The section numbers
are stable labels, not a ranking.

1. **`concurrency_correlation`** (§2.0) — **CLOSED 2026-09-04**: built, run
   on both eras, **NOISE** on each; X4 settled by hand (verdict era-stable,
   per-arm gains not; no arm clears X2/X3 in either era, so none is
   ADOPT-eligible).
2. **`hedge_concentration` grading** (§2.1) — **CLOSED 2026-09-04**: graded
   under the two-analyst protocol, **PRECONDITION-NULL** stands (and again
   on the 166-date book, ρ +0.00). The hedge trigger is dead; the hedge
   INSTRUMENT is unmeasured.
3. **v4 composition bridge** (§2.2) — `v4_bridge` prints `LADDER
   UNVALIDATED ON v4` with all five tests shifting on 166 dates; waiting on
   genuinely new (non-backfill) signal dates before re-deriving anything —
   the 2026 backfill dates do not qualify.
4. **Calendar-as-hedge** (§2.3) — **BLOCKED ON NEW DATES**; H3 has read NOT
   MET / DEPLOYABLE / NOT MET on three consecutive exports and is recorded
   as an unstable measurement.
5. **Bear sub-0.50 give-back** (§2.4) — the `be_after` route is closed
   (reverted, above), but the underlying give-back pattern is not refuted.
   The trigger that reverted it un-fired on the 140-date book and fired
   again on the 166-date one (on the 2026 column) — three censuses, three
   answers; nothing un-reverts without a fresh registration.
6. **Live walk-forward** (§2.5) — still the intended evidence source; no
   recorded progress since 2026-08-13. Silence here is not evidence of no
   progress — check the live-loop artifacts before re-planning.
7. **Rollback triggers** (§2.6) — checked at their gates, never read from
   silence:

   | Trigger | Census (2026-08-24) | Outcome |
   |---|---|---|
   | Bear-debit `be_after 0.50` | 92 rows / 53 dates ≥ floor 60 | **FIRED → REVERTED** |
   | LVOL tef-null | 31 dates ≥ floor 25 | all four criteria pass — **CLEARED**, operator **HELD** the ship |
   | BEAR_HE trail | 1 date of floor 25 | **UNDERPOWERED** |
   | Credit sl-none | 0 fresh `bull_put` rows of 15 | **UNDERPOWERED** |

8. **Parked / blocked long-term** (§2.7) — credit exit knobs (needs a
   credit-heavy window), the long-dated (≥180 DTE) blind spot (unpriceable,
   BS proxy tier off), the per-regime exit switch (STAYS GATED on this
   book), `portfolio_delta` ARM B ceiling 1.50 (queued,
   CANDIDATE-FOR-INDEPENDENT-WINDOW), 20 stuck backfill partials, and the
   deferred `analysis_pipeline/core.py` refactor.
9. **`invalidation_exit`** (§2.8) — the exit engine still ignores each
   analysis row's free-text `invalidation` condition; this is the one item
   the old 2026-06 backlog left open (everything else there was refuted,
   fixed, or superseded — [`archive/00`](archive/00-backtest-engine-backlog-2026-06.md)).

### Standing rules — do not re-litigate these

- `score_total` is decision-irrelevant (tie-break only); selection is
  structure × regime × entry geometry.
- The ML/selection search is closed; re-open only on new columns, never new
  models.
- v3 and v4 rows are never pooled; v4's score scale (0–50, 0–55 VOLATILITY)
  is not comparable to v3's 0–100.
- Studies are era-scoped; the bare export filename does not name a
  population — `lib/era.py` is the single encoding.
- `exit_basis` is readable on v4, unreadable and scrambled on v3 and
  earlier; never use it to answer a REPLAY question in any era.
- ARM labels are study-local — always cite `study ARM X`, never a bare
  `ARM X` ([`arm-index.md`](arm-index.md)).
- `study_review … --dry-run` **overwrites** review/digest artifacts; never
  use it as a read-only check.
- Never hardcode a figure off one export, in code or in prose.

Full glossary of terms (PF, CI, LOO, etc.) used across this page:
[`glossary.md`](glossary.md).

## Reading order for more depth

1. [`next-steps.md`](next-steps.md) — the live queue and repo state, read first.
2. [`current.md`](current.md) — "State of play" block at the top, then dated
   entries newest-first for the full evidence trail.
3. [`study-map.md`](study-map.md) — one page per study family, what each
   study asked and concluded.
4. [`docs/deployment-rules.md`](../docs/deployment-rules.md) — the operator
   card: what to actually do on a deploy morning.
5. [`deployment-evidence.md`](deployment-evidence.md) — why each card rule
   ships, its numbers, and its rollback triggers.
6. [`archive/`](archive/) — via [`README.md`](README.md) §Section index only;
   do not browse archive files directly without that map.
