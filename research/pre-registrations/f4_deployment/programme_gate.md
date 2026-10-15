## programme_gate — keep or retire the flow-selection layer

_Registered 2026-10-13._

**STATUS: ACCEPTED BY DEFAULT 2026-10-13 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** The rule's substance is the operator's, from
[next-steps P0](../../next-steps.md#plan-20261013). Every contested choice
below is a parameter, and the gate's record prints its outcome both ways.

**What this file says, in one paragraph.** Two reads decide whether the
flow-selection layer stays. If the picks do not beat the mechanical spread in
`mechanical_benchmark`'s same-ticker arms, and `dip_buy` grades `NULL` or
`CONTRARY`, the gate reads `RETIRE`. If either read is positive, it reads
`KEEP`. While `dip_buy` is `STILL-OPEN`, the gate reads `WAIT`, and the P1
read alone cannot retire anything. The gate changes no deployment rule.
Acting on it is a separate operator decision.

**Registered before any input exists.** On 2026-10-13 no
`mechanical_benchmark` outcome has been printed: its only run reads
`NOT BUILT — AWAITING SCRAPE`, and the same-ticker legs are not fetched.
`dip_buy` reads `STILL-OPEN` behind the holdout seal.

## What this is

A COMMITMENT, not a study. It has no module, no report and no arms of its
own. It fixes, before either input is read, which verdicts of two registered
studies decide whether the flow-selection layer keeps running.

The flow-selection layer is the analysis pipeline plus the deploy card's
ladder: the picks the model emits, tiered by `ladder_tier()` and deployed
top-3/day ([§2](../../../docs/deployment-rules.md#s2)).

It follows the [`holdout_seal`](holdout_seal.md) shape: its own section list,
with Verdicts, Anti-tuning, Ship criteria and Build notes in the usual order.

## What this is NOT

- **Not a deployment rule.** `RETIRE` changes nothing in
  [`docs/deployment-rules.md`](../../../docs/deployment-rules.md), the deploy
  card or the journal. The operator decides whether to act, and any new rule
  needs its own registration.
- **Not a new grade of either input.** Both studies grade themselves under
  their own registrations. This file only says which of their verdicts count
  here. It adds no criterion, cut or statistic to either.
- **Not a ticker-choice test.** P2 (`mechanical_benchmark` `ARM U`, or a
  SPY-only benchmark) is not an input. See [Inputs](#inputs).
- **Not the dip sizing rollback.** The
  [sizing policy](../../../docs/deployment-rules.md#s2-sizing) already reverts
  to uniform $500 when `dip_buy` reads `NULL` or `CONTRARY`. That rollback
  stands on its own and is unaffected by this gate.

## Inputs

Two inputs, both fixed by the operator's rule.

| Input | Source | Era | What counts |
|---|---|---|---|
| `PG-M`, the P1 read | [`mechanical_benchmark`](../f1_selection/benchmark/mechanical_benchmark.md), arms [`ARM M1` and `ARM M2`](../../arm-index.md#mechanical_benchmark) | v4 | The per-arm criteria C0, C1, C2 and the `CONTRARY` condition, on the headline basis |
| `PG-D`, the dip read | [`dip_buy`](../f1_selection/regime/dip_buy.md), arm [`DB1`](../../arm-index.md#dip_buy) | v4 forward dates | Its verdict of record |

### PG-M — do the picks beat the mechanical spread?

The read uses `mechanical_benchmark`'s per-arm criteria verbatim:

- **C0** — at least 25 dates and 40 matched pairs;
- **C1** — paired within-date mean R gain with a 95% date-clustered CI
  excluding zero;
- **C2** — every leave-one-date-out fold positive;
- **the `CONTRARY` condition** — an arm's paired gain negative with a CI
  excluding zero.

Every one is read on the headline basis (`DEBIT_PROD` on both sides, gross
of costs). The declared secondaries, `ARM M2L` and the own-profile replay,
carry no verdict there and none here.

| `PG-M` reads | When |
|---|---|
| `BEATS` | An admitted arm clears C0, C1 and C2, and no arm meets the `CONTRARY` condition |
| `CONTRARY` | `ARM M1` or `ARM M2` meets the `CONTRARY` condition |
| `DOES NOT BEAT` | At least one arm clears C0, no admitted arm clears C0–C2, and neither is `CONTRARY` |
| `UNDERPOWERED` | Neither arm clears C0 |
| `NOT BUILT` | The census fails a floor even at its upper value |
| `NOT READ` | No run has printed per-arm grades yet, for example `NOT BUILT — AWAITING SCRAPE` |

`CONTRARY` wins over `BEATS`, as `mechanical_benchmark` ranks it first.
"Clears C0–C2" is the same per-arm bar that study's `STRUCTURE-ONLY` uses
for "the model wraps a trade better than a fixed rule".

**Parameter `PG-ARMS`: which arms are admitted to `BEATS`.**

| Setting | Meaning | Default? |
|---|---|---|
| `M1 or M2` | Either arm clearing C0–C2 counts | **Yes** |
| `M1 only` | Only the primary arm counts | Printed beside it |

Why the default: `mechanical_benchmark` itself reads "`ARM M1` or `ARM M2`
clears C0–C2" as a beat in `STRUCTURE-ONLY`. Admitting only M1 would read its
labels more strictly than it does. This promotes nothing: `ARM M2` stays
SECONDARY there. The cost is two chances to clear, which tilts the gate
toward `KEEP`, the status quo.

**Parameter `PG-UNPOWERED`: what an `UNDERPOWERED` or `NOT BUILT` P1 read
means.**

| Setting | Meaning | Default? |
|---|---|---|
| `burden on the picks` | Counts as `DOES NOT BEAT` | **Yes** |
| `hold` | Leaves `PG-M` without a read, as `NOT READ` | Printed beside it |

Why the default: the operator's words are "do not beat", not "lose to". The
layer has to show it earns its keep, so a read that cannot show a beat is not
one. A `NOT BUILT` from a liquidity-confounded census is the weakest case,
and the record says which of the two it was.

### PG-D — does the dip rule hold forward?

`dip_buy`'s own verdict words, verbatim:

| `dip_buy` verdict of record | Counts here as |
|---|---|
| `SUPPORTED` | positive |
| `NULL` | negative |
| `CONTRARY` | negative |
| `STILL-OPEN` | no read yet |

The verdict of record is the first `dip_buy` run that prints anything but
`STILL-OPEN`. Later runs are descriptive, as its registration says.

### What is not an input

- **P2**, the ticker-choice read: `mechanical_benchmark` `ARM U`, or a
  SPY-only benchmark registered later. The operator's rule names only the
  same-ticker arms, so P2 stays out by default. A P2 result is recorded beside
  the gate and never changes its outcome. Making it an input would need a new
  registration written before P2 prints.
- **`mechanical_benchmark`'s study-level verdict token.** With `ARM U` unread,
  `STRUCTURE-ONLY` would also claim that `ARM U` does not clear. The gate
  reads the per-arm criteria instead.
- **v3.** `mechanical_benchmark`'s C5 and `dip_buy`'s in-sample tables are
  context, not inputs.
- **The [`holdout_seal`](holdout_seal.md) read.** It grades the ladder's
  tiers on the sealed window, not the layer against a mechanic.

## The gate

Read top to bottom; the first matching row is the outcome.

| # | `PG-M` | `PG-D` | Gate reads |
|---|---|---|---|
| 1 | `BEATS` | any | `KEEP` |
| 2 | any | `SUPPORTED` | `KEEP` |
| 3 | `CONTRARY` or `DOES NOT BEAT` | `NULL` or `CONTRARY` | `RETIRE` |
| 4 | `CONTRARY` or `DOES NOT BEAT` | `STILL-OPEN` | `WAIT`, recorded as "P1 negative, `dip_buy` open" |
| 5 | `NOT READ` | `NULL`, `CONTRARY` or `STILL-OPEN` | `WAIT` |

`UNDERPOWERED` and `NOT BUILT` enter this table as set by `PG-UNPOWERED`.

### Timing

- **The P1 read alone cannot retire.** Row 4 waits for `dip_buy`. That read
  needs about 142 forward signal dates, roughly seven months, and the seal must
  lift first.
- **`KEEP` can arrive first.** Row 1 needs only P1, and row 2 only `dip_buy`.
- **The gate is read whenever an input gets its verdict of record**, and once
  more at the backstop. Each read is recorded, `WAIT` included.

**Parameter `PG-BACKSTOP`: what happens if `dip_buy` never grades.** In a
steady rally the dip arm may never fill, so row 4 could wait forever.

| Setting | At the backstop date | Default? |
|---|---|---|
| `2027-10-13, not positive` | An input with no read counts as not positive. Row 4 becomes `RETIRE`; row 5 becomes `RETIRE` too | **Yes** |
| `2027-10-13, operator` | The gate reads `BACKSTOP` and the operator decides | Printed beside it |

Why the default: the keep clause needs a positive read, and a year with none
is not one. 2027-10-13 is one year after registration. That gives `dip_buy`
about five months of slack past its expected wait, and leaves room for the
seal to lift. A prompt-version bump that freezes `dip_buy` at `STILL-OPEN`
brings the backstop forward to the bump date, since no later v4 date can
grade it.

## What each outcome means

- **`KEEP`.** The pipeline keeps running and the daily loop is unchanged. Both
  reads keep running: `dip_buy`'s forward grade, and `mechanical_benchmark` as
  dates unseal. Neither re-opens this gate.
- **`RETIRE`.** The flow-selection layer has not earned its keep. The rule
  names two ways out, and the operator picks one:

  | Option | What it is, by reference |
  |---|---|
  | A mechanical dip rule at $500 | Trade on [dip dates](../../glossary.md#dip-date) only, at $500 max risk per position, as the [sizing policy](../../../docs/deployment-rules.md#s2-sizing) defines both. Instrument and geometry are not fixed here |
  | Stop | No new positions from the pipeline |

  Either one is a deployment change and needs its own registration and
  rollback trigger first. Nothing changes on the gate's word alone.
- **`WAIT`.** Nothing changes. The record says which input is missing.
- **`BACKSTOP`** (only under the non-default `PG-BACKSTOP`). The operator
  decides; the record states both inputs as they stand.

## Verdicts, worded now

| Token | Meaning |
|---|---|
| `KEEP` | Row 1 or 2 |
| `RETIRE` | Row 3, or rows 4–5 at the backstop under the default |
| `WAIT` | Row 4 or 5 before the backstop |
| `BACKSTOP` | Rows 4–5 at the backstop under `PG-BACKSTOP = operator` |

**The verdict of record is the first read that is not `WAIT`.** The gate is
read once to a final outcome. A later look, under either setting, is a new
registration.

Every read prints under both settings of each parameter. Only the defaults
are the verdict; the other settings are printed beside it.

## Anti-tuning

- The inputs, their labels and the gate table are fixed now, before either
  input has an outcome. None may change after one prints.
- No third input is added because the first two look bad or good. P2 stays
  out unless a new registration says otherwise before P2 prints.
- The backstop date may not move once either input has a read.
- `mechanical_benchmark`'s geometry, arms and floors are its own. This gate
  never asks for a different geometry, basis or arm.

## Ship criteria

None. No rule ships from this commitment. `RETIRE` lets the operator consider
a mechanical dip rule at $500 or stopping. Either needs its own registration
before money moves.

## Build notes

Not part of the commitment. Implementation only.

- No module, no report and no `scripts/study_map/catalog.py` entry, as with
  `holdout_seal`. The test suite requires the catalog to match the study
  runner's list exactly, so an entry without a module would fail it.
- The gate is read by hand from the two studies' recorded runs. Each read goes
  into `research/current.md` and the P0 row of
  [next-steps](../../next-steps.md#plan-20261013).
- **P1 needs a build change before `PG-M` can be read.** As built on
  2026-10-09, `mechanical_benchmark` prints per-arm grades only when every
  census floor passes. That includes floor 3 and the fetch count for `ARM U`.
  A same-ticker-only fetch therefore still prints `NOT BUILT — AWAITING
  SCRAPE`. The P1 step must add a same-ticker path first. It would be a
  `Resolved at build` ruling in that study's file, written before the run.
  Until then `PG-M` is `NOT READ`.
- Done 2026-10-13: that study now prints `SAME-TICKER READ — ARM U NOT BUILT` with the per-arm criteria ([ruling](../f1_selection/benchmark/mechanical_benchmark.md#dependencies)).
