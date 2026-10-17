# exit_from_text — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f2_management/exit_from_text.md); where the two differ, the registration wins.
> Latest outcome: no `CANDIDATE` cell; 301 cells `UNDERPOWERED`, 17 `NULL` and 18 `CONTRARY`; the pooled `ALL` rows are not a criterion (v4 era) — 2026-09-28 · [record](../../study-results/f2_management/exit_from_text.md).
> Nothing else here is a result.

## The question

Every emitted play states an entry trigger, an invalidation and a horizon. The backtest ignores all three. Does honouring them beat the shipped profiles?

The study is an f2 management study. Signal, entry day, structure, sizing and candidate set are frozen. Each arm changes one thing about an open position, or (E2) whether it opens. Nothing ships.

The text columns are a new column family. Each parsed level is observable at entry, because it is printed on the card the operator reads.

## What it compares

Three arms, frozen. No fourth arm is added. Labels are `exit_from_text E1`, `E2` and `E3` ([index](../../arm-index.md#exit_from_text)).

| Object | What it does | Kind |
|---|---|---|
| `exit_from_text E1` | Exits at the first close of the underlying beyond the parsed invalidation level, in the direction the structure implies. Buffer grid {0%, 1%, 2%} | exit arm |
| `exit_from_text E2` | Enters the play only if its price-level trigger was met within N ∈ {1, 3} sessions of the signal date. Rows not met are not entered | selection effect |
| `exit_from_text E3` | Replaces PROD's `time_exit_dte_fraction 0.75` with the emitted `horizon`, a DTE bucket of 14, 60, 180 or 720 | exit arm |

**E1 details.**

- A 0% buffer is the null arm. A buffer of 1% or more is the expected shape.
- Direction comes from the structure side. Long-delta structures exit on a close below the level. Short-delta structures exit on a close above it.
- Credit straddles and strangles use breakeven levels, never a strike.
- The rule fires ahead of the PROD stops, as the earlier of the two. A tie leaves the outcome unchanged.
- Long-vol debit straddles and strangles go to the bucket `long_vol_no_stop_side`.
- `iron_condor`, `butterfly` and `calendar` go to the bucket `no_structure_side`.
- Rows with no parseable level are their own bucket, counted and never imputed.

**E2 details.** Only price-level triggers are testable. Conditional triggers that do not parse are their own bucket. E2 is quoted on R for the entered subset, with the excluded share beside every number. It can never be called an exit improvement.

**E3 details.** The horizon maps to a calendar-day count, once. A survival control runs before any monotone claim, because horizon is coupled to hold length. It recomputes the horizon table within `days_held` terciles and prints the horizon by hold-length census.

## How it is judged

**Measure.** Paired [ΔR](../../glossary.md#r) against the shipped book, by date, with a date-clustered bootstrap (`BOOT_N = 10000`, α = .05). Paired [PF](../../glossary.md#pf) prints, but a PF claim must also clear the mean-R criterion. R is quoted, never dollars.

**Population.** The v4 era is PRIMARY. The v3 era is SECONDARY, run with `--era v3`, and the two are never pooled. The loader uses `include_bs=False`. Cells are per structure, per `mech_cell` and their cross. A pooled `ALL` row prints for orientation and is NOT A CRITERION.

**Power floor.** A cell needs at least 60 affected rows and 25 affected dates. "Affected" means base and variant differ on the `(exit_reason, days_held, round(pnl, 10))` triple under the frozen replay. A cell below either floor prints `UNDERPOWERED` with its census and no criterion.

**Calibration.** Rows that do not reproduce their stored exit are excluded and counted, not failed. `superseded`, `hard` and `deferred_fill` rows leave the variant arms.

**Bar for a candidate.** A cell must clear all seven clauses.

1. Paired ΔR against the shipped book, with the date-clustered CI excluding zero.
2. Every leave-one-date-out ([LOO](../../glossary.md#loo)) fold positive, and the LOO median fold gain above zero among affected dates.
3. The cell survives `protocol.window_cuts` and the ex-BOTH cut added by hand.
4. Positive in every calendar year present.
5. Right-signed on both pricing tiers, `real` and tweak.
6. At least 60 affected rows and 25 affected dates, re-checked on the evaluated set.
7. No perturbation flip across the buffer grid. E3's analogue is the survival control. E2's analogue is the N grid: a cell positive at one N and flipped at the other fails.

**The strike split.** Level equals a strike is split from level differs from every strike. A candidate must be carried by the second cell. A gain that lives only in the first is an Attempt 9 restatement.

Worst-decile cells print descriptively and are NOT A CRITERION.

## Possible verdicts

One token per cell.

| Token | What it means |
|---|---|
| `UNDERPOWERED` | A floor was not met. Census only, nothing read |
| `NULL` | Powered, but the conjunction did not clear |
| `CANDIDATE` | The whole conjunction clears. It is not a ship |
| `CONTRARY` | Powered, CI excludes zero, and the sign is opposite to the arm's hypothesis |
| `SURVIVAL-ARTIFACT` | E3 only. The raw table is monotone but dies under the survival control |
| `NO PRE-REGISTERED VERDICT MATCHES` | The catch-all, resolved by hand in `research/current.md` |

The unparseable buckets for invalidation and trigger print their shares as prompt-robustness findings, whatever else happens.

## What could ship

Nothing ships automatically. A `CANDIDATE` becomes a written proposal.

- A `structure_exit` or `regime_exit` cell in `config/backtest.yml`, keyed on the structure and `mech_cell` where it was found.
- A matching line in [§5](../../../docs/deployment-rules.md#s5).
- Its own rollback trigger, plus an independent-window confirmation first.

The operator decides. E2 can never ship as an exit rule. If it clears, it is an intake proposal and is labelled one.

## What this study cannot tell you

- Whether a trailing stop helps. Drawdown-from-peak trailing failed three times and is not retested.
- Whether text-derived rules help rows that did not price. Every arm is conditioned on priceability.
- Anything about E2 as an exit. It changes which rows enter.
