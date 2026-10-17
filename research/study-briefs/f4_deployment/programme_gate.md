# programme_gate — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f4_deployment/programme_gate.md); where the two differ, the registration wins.
> Latest outcome: `WAIT` (row 4: `PG-M` `CONTRARY`, `PG-D` `STILL-OPEN`) — 2026-10-15 · [log](../../current.md).
> Nothing else here is a result.

## The question

This is a commitment, not a study. It has no module, report or arms.

It asks which verdicts of two registered studies decide whether the flow-selection layer stays. That layer is the analysis pipeline plus the deploy card's ladder: the picks the model emits, tiered by `ladder_tier()` and deployed top-3 per day. The gate fixes the rule before either input is read.

## What it commits to

The gate reads two inputs. Neither study changes its own grading for this gate.

| Input | Source | What counts |
|---|---|---|
| `PG-M` | [`mechanical_benchmark`](../../pre-registrations/f1_selection/benchmark/mechanical_benchmark.md), [`ARM M1` and `ARM M2`](../../arm-index.md#mechanical_benchmark), v4 | Per-arm criteria C0, C1, C2 and the `CONTRARY` condition, on the headline basis (`DEBIT_PROD` on both sides, gross of costs) |
| `PG-D` | [`dip_buy`](../../pre-registrations/f1_selection/regime/dip_buy.md), [`DB1`](../../arm-index.md#dip_buy), v4 forward dates | Its verdict of record: the first run that prints anything but `STILL-OPEN` |

The criteria, used verbatim:

- C0: at least 25 dates and 40 matched pairs.
- C1: paired within-date mean R gain, with a 95% date-clustered CI excluding zero.
- C2: every leave-one-date-out fold positive.
- `CONTRARY` condition: an arm's paired gain is negative with a CI excluding zero.

`PG-M` reads one of six tokens. `CONTRARY` wins over `BEATS`.

| `PG-M` reads | When |
|---|---|
| `BEATS` | An admitted arm clears C0, C1 and C2, and no arm meets the `CONTRARY` condition |
| `CONTRARY` | `ARM M1` or `ARM M2` meets the `CONTRARY` condition |
| `DOES NOT BEAT` | At least one arm clears C0, no admitted arm clears C0–C2, and neither is `CONTRARY` |
| `UNDERPOWERED` | Neither arm clears C0 |
| `NOT BUILT` | The census fails a floor even at its upper value |
| `NOT READ` | No run has printed per-arm grades yet |

`PG-D` counts `SUPPORTED` as positive, `NULL` and `CONTRARY` as negative, and `STILL-OPEN` as no read yet.

Three parameters are contested. Each prints under both settings, and only the default is the verdict.

| Parameter | Default | Printed beside it |
|---|---|---|
| `PG-ARMS` | `M1 or M2`: either arm clearing C0–C2 counts | `M1 only` |
| `PG-UNPOWERED` | `burden on the picks`: `UNDERPOWERED` or `NOT BUILT` counts as `DOES NOT BEAT` | `hold`: leaves `PG-M` as `NOT READ` |
| `PG-BACKSTOP` | `2027-10-13, not positive`: an input with no read counts as not positive | `2027-10-13, operator`: the gate reads `BACKSTOP` |

**Not inputs.** `mechanical_benchmark` `ARM U` and any SPY-only benchmark (P2), that study's own verdict token, v3 results, and the [`holdout_seal`](holdout_seal.md) read. A P2 result is recorded beside the gate and never changes it.

## What each outcome triggers

The gate reads the table top to bottom. The first matching row is the outcome.

| # | `PG-M` | `PG-D` | Gate reads |
|---|---|---|---|
| 1 | `BEATS` | any | `KEEP` |
| 2 | any | `SUPPORTED` | `KEEP` |
| 3 | `CONTRARY` or `DOES NOT BEAT` | `NULL` or `CONTRARY` | `RETIRE` |
| 4 | `CONTRARY` or `DOES NOT BEAT` | `STILL-OPEN` | `WAIT`, recorded as "P1 negative, `dip_buy` open" |
| 5 | `NOT READ` | `NULL`, `CONTRARY` or `STILL-OPEN` | `WAIT` |

At the backstop under the default, rows 4 and 5 become `RETIRE`. A prompt-version bump that freezes `dip_buy` at `STILL-OPEN` brings the backstop forward to the bump date.

| Token | What it triggers |
|---|---|
| `KEEP` | The pipeline and daily loop run unchanged. Both reads keep running; neither re-opens the gate |
| `RETIRE` | The operator picks one way out: a mechanical dip rule at $500, or no new positions from the pipeline. Either needs its own registration and rollback trigger first |
| `WAIT` | Nothing changes. The record says which input is missing |
| `BACKSTOP` | Only under `PG-BACKSTOP = operator`. The operator decides, with both inputs stated |

**Timing.** The P1 read alone cannot retire. Row 4 waits for `dip_buy`, which needs about 142 forward signal dates once the seal lifts. `KEEP` can arrive first. The verdict of record is the first read that is not `WAIT`.

## What could ship

Nothing ships. `RETIRE` lets the operator consider a mechanical dip rule at $500 or stopping, and money does not move without a new registration.

## What this commitment cannot tell you

- Whether the model's ticker choice adds value. P2 is not an input.
- Whether any deployment rule should change. It changes none.
- Anything about the dip sizing rollback. The [sizing policy](../../../docs/deployment-rules.md#s2-sizing) reverts on its own when `dip_buy` reads `NULL` or `CONTRARY`.
- Anything while an input is unread. As of 2026-10-15 the gate reads `WAIT`: `PG-M` is `CONTRARY` and `PG-D` is open.
