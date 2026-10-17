# earnings_vol — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f3_structure/earnings_vol.md); where the two differ, the registration wins.
> Latest outcome: `ARM S` `NULL` and `ARM K` `NULL`. Secondary reads: all four `ARM S` lines `NULL`; `ARM K` natural fill `CONTRARY`, and its other three secondary lines `NULL`; forward (2 sealed events) `STILL-OPEN`; nothing ships (v4 era) — 2026-10-13 · [record](../../study-results/f3_structure/earnings_vol.md).
> Nothing else here is a result.

## The question

Across 11 earnings seasons on a fixed list of 25 names, does a long ATM straddle or a long ATM calendar earn a positive mean return whose daily P&L does not move with the deployed book?

Both structures enter 5 sessions before the report and close the session after. The ladder is a direction bet, and earnings are the one scheduled event with a known date and a large single-name move. The trades run on an earnings calendar that never reads the engine's signal dates.

The motivating hint came from `vol_sleeve`. It was found post hoc, on the engine's own dates, and did not replicate. It motivates the study and is not evidence for it. The study reads none of those rows.

## What it compares

Labels are `earnings_vol ARM S` and `ARM K` ([index](../../arm-index.md#earnings_vol)). One unit per event. Return is net P&L over the entry debit.

| Object | What it does | Kind |
|---|---|---|
| `earnings_vol ARM S` | Buys the ATM call and put on the front expiry | PRIMARY |
| `earnings_vol ARM K` | Buys a [double calendar](../../glossary.md#double-calendar): sells the front ATM call and put, buys the back ATM call and put | PRIMARY |

**Universe.** 25 US single stocks, fixed before any result.

| Group | Names |
|---|---|
| agent-trading list (19) | AAPL AMD AMZN ASML AVGO COST GOOGL INTC JPM LLY META MSFT MU NFLX NVDA QCOM TSLA TSM UNH |
| Added (6) | BA BAC COIN DIS PLTR UBER |

**Events.** The calendar is agent-trading's `data/earnings/<SYM>.csv`. A season is a calendar quarter of report dates, 2024-Q1 through 2026-Q3, so 11 seasons.

- Event session E is the first session whose open reflects the report. For `bmo` it is the report date. For `amc` and `dmh` it is the next session.
- An `unknown` session is dropped and counted. A secondary line treats it as `amc`.
- Entry is the close of session E − 5. Exit is the close of E.
- The run-up exit, the close of E − 1, prints and is not graded.
- An event with E on or after `era.SEAL_START` is forward. It prints `STILL-OPEN` and never enters the verdict.

**Structures.**

- The ATM strike is the listed strike nearest the close at entry, ties to the lower strike.
- The front expiry is the first listed expiry after session E.
- The back expiry is the first listed expiry at least 28 calendar days after the front.
- An event with any leg missing on the entry or exit day is dropped and counted, per arm.
- A debit ≤ 0 at a fill's own basis refuses that trade. A calendar priced to a credit is refused and counted.

**Fills.** The default is mid, plus $0.65 per contract per side. The natural fill prints beside it: bought legs at the ask, sold legs at the bid. A sold leg with no bid fills at 0. A junk quote falls back to `Latest` and is counted.

## How it is judged

**Measure.** Per arm: mean return, median, win rate, profit factor, and MFE and MAE as a share of the debit. The CI is a cluster bootstrap over the 11 seasons: whole seasons resampled, 10,000 draws, seed 20261012. The report prints the cluster count beside it.

Also printed: means per half (2024-Q1 → 2025-Q2 and 2025-Q3 → 2026-Q3), the leave-one-season-out minimum, and mean and n per name. Per-name figures carry no verdict.

**Population.** In-sample events only, at mid fill, on the v4 era with the holdout seal applied.

**The gate, `G1`.** The sleeve's daily mark-to-market P&L is set against the deployed book's daily change. The book is `account_sim`'s registered cell, the same as in `index_vrp`. The sleeve sums all open events, one unit each.

- `G1` passes when the correlation's point estimate is ≤ 0. This is the anti-re-wrap bar `financed_spread` E3 uses.
- A pass at ≤ 0.10 prints beside it.
- The correlation CI is a stationary block bootstrap over sessions: mean block 10, 10,000 paths.
- The sleeve's mean daily P&L on the book's worst 5% of sessions also prints.
- A `G1` with fewer than 3 common sessions is `NOT EVALUABLE`, and the token is `NULL`.

**Overfitting.** Nothing is picked from a grid. The printed variants form a grid of 2 arms, 2 fills and 2 exits. Their PBO prints as context from `lib/pbo.py::cscv`.

## Possible verdicts

Per arm, at mid fill, on in-sample events.

| Token | When |
|---|---|
| `EDGE` | Season-clustered CI95 lower bound > 0, both halves' means > 0, and `G1` passes |
| `RE-WRAP` | The CI and halves clauses hold, and `G1` fails |
| `CONTRARY` | CI95 upper bound < 0 |
| `NULL` | Anything else |

The natural fill, the unknown-as-`amc` events, the run-up exit and the 0.10 gate each print their own token, labelled secondary.

## What could ship

Nothing ships. An `EDGE` token earns a sizing registration and a forward read, not a deployment.

## What this study cannot tell you

- Whether the effect exists in small, illiquid names. The list is mega-caps, and a `NULL` there does not contradict the literature.
- Whether a report that moves after entry matters. The calendar cannot show it.
- Anything about a run-up trade. That exit prints and is not graded.
- Anything about the book's picks. No signal date, play or analysis row chooses a trade.
- Anything about the sealed events. They stay `STILL-OPEN`.
