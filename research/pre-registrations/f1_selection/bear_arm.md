## bear_arm — bear selection conditioning (B1) and exit fit (B2) (2026-08-11, quoted from research/ml-plan.md §Kickoff addendum)

_Registered 2026-08-11._

Module: `scripts/backtest_study/f1_selection/bear_arm.py`. This study's
pre-registration was written on 2026-08-11 in `research/ml-plan.md` §Kickoff
addendum — before this folder existed, before the module was written, and
before any code ran. It therefore had no file here and could not go through
`study_review`. This file carries the commitments over so a run can be graded;
every criterion below is **quoted**, not restated. `research/ml-plan.md` itself
was removed on 2026-08-24 once its three studies had files of their own — its
original text is in git (`git show 42b5e46:research/ml-plan.md`).

The same document registered the ML combination search
([`ml_combination.md`](ml_combination.md)) and, later the same day, the DEPLOY
arm ([`../f4_deployment/bear_deploy.md`](../f4_deployment/bear_deploy.md)) —
which asks the deployment questions B1/B2 skipped and is a **different
estimand**, not a second bite: "B1 asked an *absolute level* question — is
there a bear subset with mean E ≥ 0 — and the answer is no in 496 subsets."

## Question

Operator instruction, quoted in the addendum: *"I don't want to fully remove
the bear positions as those are still necessary especially when the market are
choppy. Assume that the exit plan might not be fully tuned for the bear
positions as well."*

> This reframes the pending bear_put decision from **demote/keep** to **when**.

- **B1 — selection conditioning.** "Within bear structures, is there a subset
  defined by *decision-time* variables (mech cell, model regime, |delta|, DTE,
  iv_spread, credit/debit) whose E is ≥ 0 and which reproduces? Ship form is a
  'bear allowed when …' clause, not a blanket veto."
- **B2 — exit fit.** "Is PROD mis-tuned for bear rows specifically? Bear rows
  are the population with |MAE|/MFE 1.25 (vs bull_call 0.51) — mirrored
  path-vol, which is exactly where exit shape can matter."

## What this is NOT

- **Not a re-litigation of the blanket demotion.** "The 08-11 completed-book
  cut satisfied all three addendum-13 DEMOTE criteria (E −0.358, CI [−0.460,
  −0.256], both halves negative), so the blanket case is settled and is NOT
  re-litigated here."
- **Not a new exit-mechanism search.** "Exit configs are drawn ONLY from the
  frozen grid already validated in `exit_mechanism_study.py`."
- **Not a statement about hedging.** The caveat that must appear in any bear
  conclusion, quoted in full:

  > This book measures each play standalone. It cannot measure the hedging
  > value of holding a bear position against a long book — a play with
  > negative expected standalone P&L can still be correct as insurance. So "no
  > positive bear subset" is a statement about bear plays as *independent*
  > selections, and never an argument against a deliberately-held hedge.

  (The DEPLOY arm later judged this caveat "too strong" *for the portfolio
  question specifically*, because 107 of 111 bear dates carry concurrent
  non-bear rows — see `../f4_deployment/bear_deploy.md`. The standalone-vs-
  hedge distinction itself stands.)

## Population and basis, fixed here

Bear structures within the same deduped pooled book and the same protocol
(`scripts/backtest_study/lib/protocol.py`) as
[`ml_combination.md`](ml_combination.md), whose ground rules bind here too —
in particular rule 2 (all CIs date-clustered; ~118 dates, not ~1,100 rows),
rule 3 (real + `strike_expiry_tweak` tiers only; `bs_options_hist` excluded
from headlines), rule 4 (every headline cut ALL / ex-Mar–Apr-2025 /
ex-Feb–Apr-2026) and rule 7 (the book is in practice ≤60-DTE).

Bear rows are 88% `bear_put_spread` and only 6 are naked `long_put`, so
"conclusions are about bear *spreads*; the naked-put hedge the operator
sometimes substitutes remains untested for lack of rows."

## Unit and metric

- **B1** screens on **E** (`pnl_at_cap_pct`, exit-free — the selection
  measure), under the PROD exit.
- **B2** compares configs on **mean R** (replayed exits) on bear rows.
- Clause vocabulary is pre-declared and decision-time only: mech cell, model
  regime, `|delta|`, DTE, `iv_spread`, credit/debit.

## Bar for a candidate

"Decision rule, fixed now":

> - **KEEP-CONDITIONED (B1 ships)** iff a subset has mean E ≥ 0 with a
>   date-clustered 95% CI whose lower bound > −0.05, is positive in ≥ 2 of the
>   3 years present, survives both window cuts (ex-Mar–Apr-2025,
>   ex-Feb–Apr-2026), holds n ≥ 40, and is expressible in ≤ 2 clauses a person
>   can check at deploy time.
> - **EXIT FIX (B2 ships)** iff a frozen-grid config beats PROD on bear rows
>   by mean R with a date-clustered CI excluding zero AND survives
>   leave-one-date-out (the test that killed the per-regime switch twice) AND
>   does not degrade the non-bear book (it would be keyed to bear rows only).

## Verdicts, worded now

> - **NEITHER** → the standing recommendation stays "bear structures are
>   Tier C / not deployed on their own", and the operator's chop hedge is
>   documented as a *portfolio* decision the book cannot price (see caveat).

## Anti-tuning

**Pre-registered expectation**, written "so a post-hoc story can't be told":

> given E < 0 in every year and the mirrored MFE/MAE, the modal outcome is NO
> stable positive bear subset. The most likely exception, if there is one, is
> BEAR or E-VOL mech cells — the "choppy market" case the operator names.
> Anything found outside that must be treated as a candidate, not a finding.

Survivor counts are read against the ~5%-of-tested false-positive expectation
(the reading the DEPLOY arm's D1 inherits from B1).

## Ship criteria

B1 may ship only "a 'bear allowed when …' clause, not a blanket veto", and
only if the full rule above passes. B2 may ship only a config **already in the
frozen `exit_mechanism_study` grid**, keyed to bear rows.

## Build notes

*Not part of the registration — implementation and operational record.*

- **Outcome of the 2026-08-11 run:** B1 NOT MET (496 combinations evaluated,
  132 with n ≥ 40, 0 survivors of the full rule); B2 MET — `be_after: 0.50`
  keyed to bear debit spreads shipped.
- **B2's shipped config was later REVERTED.** `bear_arm` hosts the additive
  rollback-trigger census block registered in
  [`../f2_management/rollback_triggers.md`](../f2_management/rollback_triggers.md);
  on 2026-08-24 that trigger reached its floor and FIRED, and
  `structure_exit.enabled` went back to false (commit `1e36dba`). Any later
  reading of B2 is a reading of a reverted rule.
- **Era.** Registered and first run on the **v3** book (2026-08-11); re-read
  on era **v4** (B1 unchanged at 0 survivors). The criteria name CIs, cuts and
  sign stability rather than figures, so they are era-agnostic; a grading run
  must say which era it graded, and reproducing the original verdict needs
  `--era v3`.
