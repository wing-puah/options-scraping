## bear_arm — bear selection conditioning (B1) and exit fit (B2) (2026-08-11, quoted from research/ml-plan.md §Kickoff addendum)

<!-- outcome:start -->
> Latest outcome: `bear_arm B1` `NOT met` on v3 and v4. `bear_arm B2` `MET` on PRIMARY v3 (2026-08-11, break-even ratchet at .50, shipped as `be_after 0.50` and reverted 2026-08-24). On v4, `B2` printed `MET` for `sl .50` (2026-09-28), but that verdict has flipped between runs and the 2026 cell's CI spans zero · [record](../../../study-results/f1_selection/bear/bear_arm.md).
<!-- outcome:end -->

_Registered 2026-08-11._

Module: `scripts/backtest_study/f1_selection/bear/bear_arm.py`. This study's pre-registration was written on 2026-08-11 in `research/ml-plan.md` §Kickoff addendum. It was written before this folder existed, before the module was written, and before any code ran. It therefore had no file here and could not go through `study_review`. This file carries the commitments over so a run can be graded. Every criterion below is **quoted**, not restated. `research/ml-plan.md` was removed on 2026-08-24; its original text is in git (`git show 42b5e46:research/ml-plan.md`).

The same document registered the ML combination search ([`ml_combination.md`](../signal/ml_combination.md)). Later the same day it registered the DEPLOY arm ([`../f5_hedging/hedge_sizing.md`](../../f5_hedging/hedge_sizing.md)). The DEPLOY arm asks the deployment questions B1/B2 skipped. It is a **different estimand**, not a second bite.

## The question

Operator instruction, quoted in the addendum: *"I don't want to fully remove the bear positions as those are still necessary especially when the market are choppy. Assume that the exit plan might not be fully tuned for the bear positions as well."*

> This reframes the pending bear_put decision from **demote/keep** to **when**.

Does any group of bear positions have E ≥ 0 and reproduce, and is the shipped exit mis-tuned for bear positions? The question is not whether to demote bears. It is when a bear position is allowed, and whether its exit needs a fix.

- **B1 — selection conditioning.** "Within bear structures, is there a subset defined by *decision-time* variables (mech cell, model regime, |delta|, DTE, iv_spread, credit/debit) whose E is ≥ 0 and which reproduces? Ship form is a 'bear allowed when …' clause, not a blanket veto."
- **B2 — exit fit.** "Is PROD mis-tuned for bear rows specifically? Bear rows are the population with |MAE|/MFE 1.25 (vs bull_call 0.51) — mirrored path-vol, which is exactly where exit shape can matter."

## What this study is not

- **Not a re-litigation of the blanket demotion.** "The 08-11 completed-book cut satisfied all three addendum-13 DEMOTE criteria (E −0.358, CI [−0.460, −0.256], both halves negative), so the blanket case is settled and is NOT re-litigated here."
- **Not a new exit-mechanism search.** "Exit configs are drawn ONLY from the frozen grid already validated in `exit_mechanism_study.py`."
- **Not a statement about hedging.** The caveat must appear in any bear conclusion, quoted in full:

  > This book measures each play standalone. It cannot measure the hedging value of holding a bear position against a long book — a play with negative expected standalone P&L can still be correct as insurance. So "no positive bear subset" is a statement about bear plays as *independent* selections, and never an argument against a deliberately-held hedge.

  The DEPLOY arm later judged this caveat "too strong" *for the portfolio question specifically*, because 107 of 111 bear dates carry concurrent non-bear rows (see `../f5_hedging/hedge_sizing.md`). The standalone-vs-hedge distinction itself stands.
- **Not a study of naked long puts.** Too few rows exist: "conclusions are about bear *spreads*; the naked-put hedge the operator sometimes substitutes remains untested for lack of rows."

## Population and basis, fixed here

Bear structures in the same deduped pooled book and the same protocol (`scripts/backtest_study/lib/protocol.py`) as [`ml_combination.md`](../signal/ml_combination.md). Its ground rules bind here too:

- Rule 2: all CIs are date-clustered (~118 dates, not ~1,100 rows).
- Rule 3: real + `strike_expiry_tweak` tiers only; `bs_options_hist` is excluded from headlines.
- Rule 4: every headline is cut ALL / ex-Mar–Apr-2025 / ex-Feb–Apr-2026.
- Rule 7: the book is in practice ≤60-DTE.

Bear rows are 88% `bear_put_spread`. Only 6 are naked `long_put`.

**Era** (build note, not part of the registration). The study was registered and first run on the **v3** book (2026-08-11), and re-read on era **v4**. The criteria name CIs, cuts and sign stability rather than figures, so they are era-agnostic. A grading run must say which era it graded. Reproducing the original verdict needs `--era v3`.

## How it is judged

- **B1** screens on **E** (`pnl_at_cap_pct`, exit-free — the selection measure), under the PROD exit.
- **B2** compares configs on **mean R** (replayed exits) on bear rows.
- The clause vocabulary is pre-declared and decision-time only: mech cell, model regime, `|delta|`, DTE, `iv_spread`, credit/debit.

## Bar for a candidate

"Decision rule, fixed now":

> - **KEEP-CONDITIONED (B1 ships)** iff a subset has mean E ≥ 0 with a date-clustered 95% CI whose lower bound > −0.05, is positive in ≥ 2 of the 3 years present, survives both window cuts (ex-Mar–Apr-2025, ex-Feb–Apr-2026), holds n ≥ 40, and is expressible in ≤ 2 clauses a person can check at deploy time.
> - **EXIT FIX (B2 ships)** iff a frozen-grid config beats PROD on bear rows by mean R with a date-clustered CI excluding zero AND survives leave-one-date-out (the test that killed the per-regime switch twice) AND does not degrade the non-bear book (it would be keyed to bear rows only).

In list form, `B1` ships only if one subset meets every item:

1. Mean E ≥ 0, with a date-clustered 95% CI whose lower bound is > −0.05.
2. Positive in ≥ 2 of the 3 years present.
3. Survives both window cuts (ex-Mar–Apr-2025, ex-Feb–Apr-2026).
4. Holds n ≥ 40.
5. Is expressible in ≤ 2 clauses a person can check at deploy time.

`B2` ships only if a frozen-grid config meets all three items:

1. It beats PROD on bear rows by mean R, with a date-clustered CI excluding zero.
2. It survives leave-one-date-out.
3. It does not degrade the non-bear book. The rule would be keyed to bear rows only.

## Verdicts, worded now

The registered wording names `NEITHER`; the other two rows restate the Bar
and Ship criteria above.

| Token | Meaning |
|---|---|
| `KEEP-CONDITIONED` | `B1` ships: a "bear allowed when …" clause, not a blanket veto |
| `EXIT FIX` | `B2` ships: a config already in the frozen grid, keyed to bear rows |
| `NEITHER` | "the standing recommendation stays "bear structures are Tier C / not deployed on their own", and the operator's chop hedge is documented as a *portfolio* decision the book cannot price (see caveat)." |

## Anti-tuning

**Pre-registered expectation**, written "so a post-hoc story can't be told":

> given E < 0 in every year and the mirrored MFE/MAE, the modal outcome is NO stable positive bear subset. The most likely exception, if there is one, is BEAR or E-VOL mech cells — the "choppy market" case the operator names. Anything found outside that must be treated as a candidate, not a finding.

Survivor counts are read against the ~5%-of-tested false-positive expectation (the reading the DEPLOY arm's D1 inherits from B1).

## What could ship

B1 may ship only "a 'bear allowed when …' clause, not a blanket veto", and only if the full rule above passes. B2 may ship only a config **already in the frozen `exit_mechanism_study` grid**, keyed to bear rows. Nothing else ships.
