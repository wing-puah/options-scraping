# holdout_seal — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f4_deployment/holdout_seal.md); where the two differ, the registration wins.
> Latest outcome: sealed; 0 of 40 priced on the exported tabs (census 2026-10-17); the exports date from 2026-10-06, and a re-export is needed before a newer count is recorded · [log](../../current.md).
> Nothing else here is a result.

## The question

This is a commitment, not a study. It has no arms, no module and no report.

It asks whether the live signal dates can stay unread by research code until enough of them have priced. The read taken then grades the deploy ladder once, on dates no earlier run has seen.

## What it commits to

The seal covers every signal date on or after **2026-09-23**. That is the first date on which no research run has read an outcome.

**What the seal forbids.** No study, chart, review, digest or write-up may compute or print an outcome statistic on a sealed date. An outcome statistic is any figure derived from a position's realised or marked P&L, such as [R](../../glossary.md#r), [meanR](../../glossary.md#meanr), [PF](../../glossary.md#pf) or a dollar total. A CI, band or fold built from one counts too. An underlying's move after the signal date, scored against the play's direction, is also an outcome.

**What the seal permits.** Four things only:

- census counts: rows, dates, priceability, structure and tier mix;
- the production loop (`scripts/journal/` and the deploy card);
- pipeline health checks;
- data collection and enrichment on sealed dates.

**Named readers.** Three forward grades were accepted before this file. Each reads sealed dates from 2026-10-08 and nothing else does.

- [`refuse_floor_forward`](../../pre-registrations/f4_deployment/refuse_floor_forward.md)
- [`ticker_class`](../../pre-registrations/f1_selection/benchmark/ticker_class.md), forward P1 only
- [`narrow_to_fit`](../../pre-registrations/f4_deployment/narrow_to_fit.md), forward sign read only

Each may read only its registered cells on its own forward dates. None may print Tier A or Tier B meanR or PF on the deployed set. The list is closed.

**One exemption.** `v4_bridge` may run five composition tests on sealed dates: structure mix, credit share, plays per day, bear share and ladder tier mix. It reads emitted plays only and prints no outcome figure.

## When the seal lifts

The seal lifts when the sealed window holds **40 priced signal dates**. A priced date has at least one real or `strike_expiry_tweak` backtest row.

- An emitted but unpriced date does not count.
- A backfilled date before 2026-09-23 never enters the window.
- Meeting the count does not lift the seal by itself. The registered read runs first, and the commit that records it lifts the guard.
- A prompt version bump before the count is met runs the read once on the v4 dates that have priced. The seal then lifts.

## The read

One run, on the deployed set: `top_k_per_day(book, ladder_rank, k=3, ladder_eligible)`, v4 era, `include_bs=False`, real and tweak pricing only. The book is every sealed signal date from 2026-09-23.

| Figure | Tier A | Tier B |
|---|---|---|
| meanR | one number | one number |
| 95% date-clustered CI on meanR | one interval | one interval |
| PF | one number | one number |
| 95% date-clustered CI on PF | one interval | one interval |

Nothing else prints: no other tier, sub-window, regime cut, structure cut, exit variant, sizing arm or second run. The seal does not re-close after the read.

## What each outcome triggers

The read is graded on the sealed window alone, never pooled with the unsealed book.

| Token | What it means | What it triggers |
|---|---|---|
| `CONFIRMED` | Tier A and Tier B each have meanR > 0 with a CI excluding zero, and Tier A's meanR is not below Tier B's | The ladder holds out of sample. Recorded; nothing new ships |
| `PARTIAL` | One tier clears, the other does not | The failing tier loses its out-of-sample support. Every rule resting on it is flagged in `deployment-evidence.md` |
| `CONTRARY` | Either tier's meanR is negative with a CI excluding zero | Surfaced to the operator at once. The deployment decision is theirs |
| `NULL` | Powered, and both CIs straddle zero | Recorded as a real outcome |
| `UNDERPOWERED` | The window reached 40 dates, but a tier has fewer than 40 deployed positions | That tier prints census only. The seal does not re-close and the window is not extended |

## What could ship

Nothing ships under any outcome. A `PARTIAL`, `CONTRARY` or `NULL` read narrows in writing what the shipped rules may claim.

## What this commitment cannot tell you

- Whether any held candidate works. [`bear_arm`](../../arm-index.md#bear_arm) B2, [`financed_spread`](../../arm-index.md#financed_spread) F3 and [`portfolio_delta`](../../arm-index.md#portfolio_delta) ARM B each need their own registration and window.
- Anything about a tier other than A and B, or about a sub-window or regime.
- Whether the journal's live P&L is unbiased. The operator sees it daily, which is the seal's one soft edge.
- The tier split on the deployed set before the read. Named readers print pooled cells only.
