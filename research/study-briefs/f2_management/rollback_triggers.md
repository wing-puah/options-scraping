# rollback_triggers — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f2_management/rollback_triggers.md); where the two differ, the registration wins.
> Latest outcome, read on the 2026-09-19 book except where dated: `LVOL tef-null` `STAYS GATED`; `BEAR_HE trail` `UNDERPOWERED`; bear-debit `be_after` all three revert clauses fire (`REVERT CONDITION FIRED`; the stop was already reverted 2026-08-24); credit `sl-none` `NOT FIRED`, not settled (read 2026-10-06) · [log](../../current.md#rollback-triggers) · [evidence](../../deployment-evidence.md#open-pre-registered-rollback-triggers).
> Nothing else here is a result.

## The question

Four shipped or gated rules carry a pre-registered rollback trigger. Until 2026-08-24 the triggers existed only as prose. Nothing in the repo computed "affected dates", so no trigger had ever been evaluated.

This registration adds a census for each trigger. It also fixes how the first evaluation is read. Silence is not "not met": a trigger with no recorded census has not been checked.

## What it commits to

This is a commitment, not a comparison of arms. It adds additive census blocks to three host studies, all built on `scripts/backtest_study/lib/triggers.py`.

- `exit_switch_mech_study`, STEP 3(f)
- `bear_arm`, the `be_after` census
- `exit_mechanism_study --side credit`, the Attempt-13 comparator census

The four trigger texts are quoted in the registration and are the immutable commitment. The registration only pins the terms they left loose.

| Term | Pinned meaning |
|---|---|
| Population | Era-resolved current exports, `real` and `strike_expiry_tweak` rows, `include_bs=False` everywhere |
| Affected row | Base and variant configs give different `(exit_reason, days_held, round(pnl_pct, 4))` under the frozen harness replay |
| Affected date | A signal date with at least one affected row |
| Arming (trigger 3) | The stored mark path peaks at `round(pnl_of(mark), 10) ≥ +0.50` |
| Fresh window (trigger 4) | `bull_put` rows signal-dated after 2026-07-13, the Attempt-13 ship date. Floor 15 rows |

**Census first.** Every run prints the census: affected rows, affected dates, the floor, and `MET` or `UNDERPOWERED`. A trigger below its floor gets no reading. The census is its recorded result.

## How each trigger is read

Each trigger has its own floor and revert rule.

| Trigger | Floor | Revert condition |
|---|---|---|
| `BEAR_HE` trail (shipped 2026-07-22) | ≥ 25 affected BEAR + H/E dates of new data | Total gain vs PROD ≤ 0, or affected-date median gain < 0 |
| `LVOL` tef-null (not shipped, still gated) | ≥ 25 affected dates | Not a revert. It ships only if the median among affected dates > 0, total > 0, both halves positive and no perturbation flip |
| Bear-debit `be_after: 0.50` (shipped 2026-08-11) | ≥ 60 new bear-debit rows that arm the breakeven stop | Total gain vs PROD ≤ 0, or mean R delta on affected rows < 0, or any single year of the pooled book flips negative |
| Credit `sl-none` (Attempt 13) | ≥ 15 fresh `bull_put` rows | `sl-none` loses to `sl-1×` on the window |

Where a floor is met, the estimators are:

- Triggers 1 and 2: the per-affected-date summed `pnl_pct` delta (variant minus PROD), as median and total.
- Trigger 3: total dollar gain vs PROD on arming rows, mean-R delta on affected rows, and per-year mean-R delta sign on the pooled bear-debit book.
- Trigger 4: dollars and mean R, `sl-none` against `sl-1×`, on the fresh window.

## What each outcome triggers

Two triggers have special status, decided before any number was read.

**Trigger 3 is a correlated-window re-read.** The v4 arming rows are new plays, but they sit on the same historical signal dates (2024-01 to 2025-08) as the v3 book that fitted the rule. The evaluation runs now because the floor is met. It counts as a within-window replication, not out-of-sample confirmation.

- A revert condition that fires counts, and the operator acts on it after it is surfaced.
- A pass promotes nothing. It is logged as "held on correlated re-read". Promotion to cleared waits for genuinely new dates.

**Trigger 4 is census and comparator only.** The v4 credit book has 73 rows, 70 of them `bull_put`. Of those, 58 of 70 are 2024-dated, so the book is not the fresh window. The `sl 1x (pre-Attempt-13)` grid line and the census print. No tuning read is taken, and the credit-knob thread stays parked.

For triggers 1 and 2, a floor that is not met means no reading. They wait for new data.

## What could ship

Nothing ships. The registration changes no rule. Its outputs are a recorded census per trigger and, for trigger 3 only, a revert or hold decision. That decision goes to the operator before any config change.

## What this study cannot tell you

- Whether a rule is out-of-sample safe. Trigger 3's reading is a within-window replication.
- Whether `sl-none` beats `sl-1×` on credit spreads in general. Trigger 4 has no tuning read.
- Anything for a trigger whose floor is unmet. Only the census counts.
