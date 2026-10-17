# bear_arm — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/bear/bear_arm.md); where the two differ, the registration wins.
> Latest outcome: `bear_arm B1` `NOT met` on v3 and v4. `bear_arm B2` `MET` on PRIMARY v3 (2026-08-11, break-even ratchet at .50, shipped as `be_after 0.50` and reverted 2026-08-24). On v4, `B2` printed `MET` for `sl .50` (2026-09-28), but that verdict has flipped between runs and the 2026 cell's CI spans zero · [record](../../../study-results/f1_selection/bear/bear_arm.md).
> Nothing else here is a result.

## The question

Does any group of bear positions keep an edge? And is the shipped exit mis-tuned for bear positions?

The operator wants bear positions kept, "especially when the market are choppy". So the question is not whether to demote bears. The blanket demotion is settled and is not re-litigated here. The question is when a bear position is allowed, and whether its exit needs a fix.

## What it compares

`B1` and `B2` are criteria, not arms. See [bear_arm B1 and B2](../../../arm-index.md#bear_arm).

| Object | What it asks | Kind |
|---|---|---|
| [bear_arm B1](../../../arm-index.md#bear_arm) | Is there a subset of bear structures, defined by decision-time variables, whose [E](../../../glossary.md#e) is at least 0 and which reproduces? | selection criterion |
| bear_arm B2 | Is the shipped exit mis-tuned for bear rows specifically? | exit criterion |

Both use the same pooled book and protocol as `ml_combination`.

- `B1` clauses come from a fixed list: mech cell, model regime, `|delta|`, DTE, `iv_spread`, credit versus debit.
- `B2` draws exit configs only from the frozen grid already validated in `exit_mechanism_study.py`. It searches no new exit mechanism.
- Bear rows are 88% `bear_put_spread`. Only 6 are naked `long_put`. Conclusions are about bear spreads.

## How it is judged

**Measure.** `B1` screens on E (`pnl_at_cap_pct`), under the shipped exit. `B2` compares configs on [mean R](../../../glossary.md#meanr) with replayed exits.

**Population.** Bear structures in the deduped pooled book. Four ground rules of `ml_combination` bind here:

- CIs are date-clustered (its rule 2).
- Real and `strike_expiry_tweak` pricing tiers only (rule 3); `bs_options_hist` is excluded from headlines.
- Every headline is cut (rule 4) ALL, ex-Mar–Apr-2025 and ex-Feb–Apr-2026.
- The book is in practice 60 DTE or less (rule 7).

**Bar.** `B1` ships only if one subset meets every item.

1. Mean E ≥ 0, with a date-clustered 95% CI whose lower bound is > −0.05.
2. Positive in ≥ 2 of the 3 years present.
3. Survives both window cuts.
4. n ≥ 40.
5. Expressible in ≤ 2 clauses a person can check at deploy time.

`B2` ships only if a frozen-grid config meets all three items.

1. It beats the shipped exit on bear rows by mean R, with a date-clustered CI excluding zero.
2. It survives [leave-one-date-out](../../../glossary.md#loo).
3. It does not degrade the non-bear book. The rule would be keyed to bear rows only.

The registered expectation, written so no after-the-fact story can be told: no stable positive bear subset. The likeliest exception is the BEAR or E-VOL mech cells. Anything found elsewhere is a candidate, not a finding. Survivor counts are read against a 5%-of-tested false-positive expectation.

## Possible verdicts

| Token | What it means |
|---|---|
| `KEEP-CONDITIONED` | `B1` ships: a "bear allowed when …" clause, not a blanket veto |
| `EXIT FIX` | `B2` ships: a frozen-grid config, keyed to bear rows |
| `NEITHER` | The standing recommendation stays: bear structures are Tier C and not deployed on their own. The operator's chop hedge is a portfolio decision the book cannot price |

## What could ship

`B1` could ship a conditioned "bear allowed when …" clause. `B2` could ship one config already in the frozen grid, keyed to bear rows. Nothing else ships.

## What this study cannot tell you

- Whether to hold a bear position as a hedge. The book scores each play standalone, so it cannot price insurance value.
- Anything about naked long puts. Too few rows exist.
- Anything about a new exit mechanism. Only the frozen grid is searched.
- Whether the blanket bear demotion was right. That case is settled elsewhere.
- Anything about the v4 era alone. The registration was run first on v3 and re-read on v4; a grading run names its era.
