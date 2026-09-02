# Research overview

Written 2026-09-02. This is a SUMMARY of [`next-steps.md`](next-steps.md),
[`current.md`](current.md) and [`study-map.md`](study-map.md) — when any of
those disagrees with this page, they win and this page is stale.

## Where things stand

- **Era `v4` is current.** The book is the **140-date backfilled** one; every
  study below ran on the exports of **2026-08-27 20:34** — 485 real results /
  1,111 proxy / 1,893 analysis rows, signal dates 2024-01-10 → 2025-11-04
  ([`next-steps.md`](next-steps.md) §0). `v3` is the **frozen** era every
  shipped deployment rule was originally derived on; the two are **never
  pooled**.
- **There are still zero 2026 signal dates** in the book, so any "ex-2026" or
  "positive in every year" cut anywhere in this page is a silent no-op
  ([`next-steps.md`](next-steps.md) §0).
- **Tests green, last recorded: 2,560 passed** (2026-08-31 —
  [`current.md`](current.md)).
- **The live thread is the hedge programme.** `hedge_exposure` is run, graded
  and ratified, and ships nothing. Its follow-up `hedge_concentration` ran
  2026-08-31 and came back **PRECONDITION-NULL**, a *powered* null — it still
  awaits `study_review` grading before the question closes
  ([`next-steps.md`](next-steps.md) §1, §2.1).
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
| `bear_position_study` | **DEMOTE TO VETO** | all three pre-registered demote criteria fire on n=177, ex-window mean E < 0 |
| `bear_arm` (B1 half) | **NO** | 0 of 496 pre-defined bear subsets clear the rule (B2 half shipped, then reverted — see above) |
| `ml_combination` | **NULL RESULT** | 0 of 15 model × strategy cells beat the score-free ladder out of sample |
| `macro_event_study` | **UNDERPOWERED** / ARM X **DE-QUEUED** as `SURVIVAL-ARTIFACT` | every FOMC/minutes/CPI/PCE cell underpowered; the one raw trigger died under the survival control |
| `emission_timing` (ARM P) | **NULL** | v3-primary read spans zero; the v4 "candidate" read is off-basis (wrong-era comparison) |

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
| `next_day_move` | **NULL** | ARM C never clears its confound, so no rule; the sensitivity is structural |
| `staged_exit` | **NULL** | 60 of 96 cells underpowered on v3, thinner still on v4; every powered cell fails its own CI |

### Structure — "am I expressing the signal in the wrong wrapper?"

| Study | Verdict | Why (one clause) |
|---|---|---|
| `bear_rewrap` | **NULL** (naive re-wraps) | the diagonal cut passes every gate, but the book has no 2026 dates — a candidate, not a ship |
| `vol_sleeve` | **CLOSED** | the straddle clears its gate then dies out of sample, and correlates the WRONG SIGN with the deployed book |
| `calendar_hedge` | **BLOCKED ON NEW DATES** | fill rate 37.7% on deployed dates; H2 underpowered at n=6 |
| `financed_spread` | **UNCONFIRMED** on v4 | same-expiry shapes all NULL, naked short harmful; the one v3 candidate (F4-d20 hold) drops below the power floor on v4 |

### Deployment — "can I actually run this?"

| Study | Verdict | Why (one clause) |
|---|---|---|
| `account_sim` | `>>> FEASIBLE <<<` (caps) — but the WINDOW does not survive | delta-notional binds before cash does; feasibility only, nothing ships |
| `selection_order` | **UNDERPOWERED** at G0 | best-powered re-ordering arm reaches 20 affected dates against a floor of 25 |
| `portfolio_delta` | **NOISE** | no arm exceeds the seeded null band; book is long-only by construction (0 short-delta picks) |
| `hedge_timing` | GAP-UP came back **CONTRARY** | the hedge underperformed the same day's ladder-eligible long by 0.408 R, CI excludes zero |
| `hedge_exposure` | **UNDERPOWERED** (mechanism) + **MEASUREMENT-ONLY** (ARM M) | all nine hedge cells fail the power gate; the close-bucketed curve understates this book's max drawdown by 40.2% |
| `hedge_concentration` | **PRECONDITION-NULL** | a *powered* null — concentration does not predict the next 20 sessions of drawdown on the admitted book |
| `bear_deploy` (v4 re-read) | D2/D3/D4 **NOT MET** | the hedge-is-real and pick-rule estimands that held on v3 reverse on v4; sleeve now operator policy only |

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

1. **`concurrency_correlation`** (§2.0) — pre-registered 2026-08-22, module
   still **not written**. The highest-value unbuilt thing in the repo: no
   report yet joins book size/similarity to outcome.
2. **`hedge_concentration` grading** (§2.1) — RUN, **PRECONDITION-NULL**
   (powered); needs `python -m scripts.study_review hedge_concentration`
   (never `--dry-run`) before the max-drawdown hedge question closes.
3. **v4 composition bridge** (§2.2) — `v4_bridge` runs now and prints
   `LADDER UNVALIDATED ON v4`; waiting on genuinely new (post-2025-11-04)
   signal dates before re-deriving anything.
4. **Calendar-as-hedge** (§2.3) — **BLOCKED ON NEW DATES**; 9 worst-decile
   dates cannot power a worst-decile criterion under a 1/day sleeve.
5. **Bear sub-0.50 give-back** (§2.4) — the `be_after` route is closed
   (reverted, above), but the underlying give-back pattern is not refuted.
   The trigger that reverted it **un-fires** on the grown 140-date book —
   nothing un-reverts without a fresh registration.
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
