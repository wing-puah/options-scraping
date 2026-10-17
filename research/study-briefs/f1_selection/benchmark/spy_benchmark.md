# spy_benchmark — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/benchmark/spy_benchmark.md); where the two differ, the registration wins.
> Latest outcome: `DOES-NOT-BEAT` (headline basis, `SB-UNIT = pick`) — 2026-10-15 · [record](../../../study-results/f1_selection/benchmark/spy_benchmark.md).
> Nothing else here is a result.

## The question

Is the book's edge, if any, more than a SPY bull call spread bought on the same days?

The study is the cheap half of the ticker-choice question that `mechanical_benchmark ARM U` leaves unbuilt. It compares the picks with the index, not with a random name. It needs a few hundred SPY contracts, not about 39,000.

## Post hoc, and weaker for it

The operator proposed this study after seeing three results: `cost_sensitivity` (2026-10-09), `direction_hit` (2026-10-12) and the first `mechanical_benchmark` read (2026-10-14). Those reads make a negative result more likely. Every record of the study says so. It was registered 2026-10-14 and accepted by default.

## What it compares

The rules are `mechanical_benchmark`'s, unchanged. Both sides replay through the frozen harness.

| Object | What it does | Kind |
|---|---|---|
| [spy_benchmark ARM SPY](../../../arm-index.md#spy_benchmark) | For each deployed pick, a SPY call vertical: long strike nearest SPY's signal-date price × 1.00, short strike nearest × 1.05, at the pick's own expiry, entered on the pick's recorded entry day | PRIMARY |
| spy_benchmark ARM T | The picks, replayed unchanged. The same object as `mechanical_benchmark ARM T` | reference |
| spy_benchmark ARM CEN | Built, dropped and awaiting counts by tier, structure and DTE band | descriptive |

SPY's price is the median `Price~` of SPY's cached contracts on the signal date. The spread is a bull spread on every pick, bear picks included. A pair with no SPY row on the signal date drops as `no_spot_at_signal`. A pair whose expiry SPY had not listed drops as `expiry_not_listed_at_signal`, under the rule in the build ruling.

Up to three picks deploy per date. The `SB-UNIT` setting decides how they pair, and both print.

| `SB-UNIT` | Unit | Role |
|---|---|---|
| `pick` | One row per pick, at that pick's expiry | default, the verdict |
| `date` | One row per date: the top-ranked paired pick's SPY wrap against the mean R of the date's paired picks | printed beside it, no verdict |

## How it is judged

**Measure.** Paired mean gain in [R](../../../glossary.md#r) per pair, picks minus SPY wrap. The CI is date-clustered. E prints beside it.

**Population.** `mechanical_benchmark`'s deployed set: top 3 per day, Tier A and B, real and `strike_expiry_tweak` rows. It is the post-P3 book. Signal dates from 2026-09-23 are withheld while the [`holdout_seal`](../../../pre-registrations/f4_deployment/holdout_seal.md) stands. v4 is the headline. v3 runs only with `--v3`. Gross of costs.

**Profiles.** The headline replays both sides under `DEBIT_PROD`. A declared secondary replays each side under its own [§5](../../../../docs/deployment-rules.md#s5) row and carries no verdict.

**Census floors.** Each floor prints what the cache gives now and the most a full fetch could give.

- Floor 1: at least 25 dates with a priced SPY pair.
- Floor 2: no tier more than 10 points from another in the dropped share of in-scope picks.
- Floor 3: the SPY contracts to fetch, named and operator-approved before any fetch.
- Floor 4: pairs by DTE band, printed; a band with fewer than 10 pairs is not read.

**Gates.** G1 to G7 are those of `mechanical_benchmark`: era, no look-ahead, exit parity, pairing, pricing tier, no new statistic, no hardcoded census.

**Bar.** `mechanical_benchmark`'s per-arm criteria. C3, C4 and C5 are not used.

1. C0: at least 25 dates and 40 matched pairs (rows, under `SB-UNIT = date`).
2. C1: the paired gain's CI excludes zero.
3. C2: every [leave-one-date-out](../../../glossary.md#loo) fold is positive.
4. The `CONTRARY` condition: the paired gain is negative with a CI excluding zero.

## Possible verdicts

Precedence runs from the bottom of the table up: census, then C0, then `CONTRARY`, then `BEATS-SPY`.

| Token | What it means |
|---|---|
| `BEATS-SPY` | C0, C1 and C2 hold, and `CONTRARY` does not |
| `CONTRARY` | C0 holds and the SPY spread beat the picks |
| `DOES-NOT-BEAT` | C0 holds, C1 or C2 fails, and `CONTRARY` is not met |
| `UNDERPOWERED` | C0 fails; counts print, no outcome number |
| `NOT BUILT` | A census floor fails even after a full fetch |
| `NOT BUILT — AWAITING SCRAPE` | A SPY pair awaits a fetch |

## What could ship

Nothing ships. The study is not an input to [`programme_gate`](../../../pre-registrations/f4_deployment/programme_gate.md). It is recorded beside the gate and never changes it.

## What this study cannot tell you

- Whether the picks beat a random name. SPY is one ticker; `ARM U` still owns that question.
- Whether to trade SPY call spreads. That needs its own registration.
- Anything about QQQ, IWM or any other index. SPY is fixed.
- Anything stronger than a post-hoc read. The study was proposed after three results were seen.
- Anything from the `date` setting alone. It may not become the verdict.
