# ticker_class — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/benchmark/ticker_class.md); where the two differ, the registration wins.
> Latest outcome: `P1` `NULL`; `S1` `NULL vs G5`; `S2` `NULL vs G6`; `S3` `NULL vs G7`; `S4` `UNDERPOWERED vs G2`; PBO 0.367 (graded N=5), so verdicts print "selection fragile". `S3` has a raw CI below zero that fails Holm. The v3 replication is also `NULL`, by the PBO veto. The forward read of `P1` is `STILL-OPEN` — 2026-10-07 · [record](../../../study-results/f1_selection/benchmark/ticker_class.md).
> Nothing else here is a result.

## The question

Is a play on a broad US index ETF (SPY, QQQ, IWM, DIA) more reliable than a play on a single stock, once direction is held fixed?

"Reliable" means four things together: expectancy in R with a date-clustered CI, hit rate, share of the book's drawdown, and stability across the two dominant windows, calendar years and half-years. Total P&L alone never answers it. The study registered 2026-10-07. The operator took every recommendation the same day.

## What it compares

The unit is a fixed ticker group, hashed (sha256 `6ce7373e…`) before any outcome column was read. The first matching rule wins, in the order G1, G2, G3, G4, G6, G5, G7. Semis therefore beat big tech, and NVDA lands in G6. [Full group table](../../../pre-registrations/f1_selection/benchmark/ticker_class.md#group-table-fixed-here).

| Group | Holds |
|---|---|
| G1 index | SPY, QQQ, IWM, DIA |
| G2 country | single-country or regional equity ETFs |
| G3 sector | US sector or thematic equity ETFs (context only) |
| G4 non-equity | commodity, rates, credit or crypto ETPs (context only) |
| G5 big tech | the Magnificent 7 minus NVDA |
| G6 semis | GICS 4530 single names |
| G7 rest | every other single name |

S is G5 ∪ G6 ∪ G7. A new ticker goes to G7 unless it is an ETF, which goes to the group its mandate names.

Direction comes from the canonical structure: bull, bear or neutral. Neutral rows print and are never graded.

| Object | What it does | Kind |
|---|---|---|
| [ticker_class P1](../../../arm-index.md#ticker_class) | G1 against S, direction-standardised by G1's own bear/bull mix; in-sample, bear and bull | PRIMARY, graded |
| ticker_class S1, S2, S3 | G1 against G5, G6, G7 respectively, bear plays only | secondary, graded |
| ticker_class S4 | G1 against G2, bull plays only | secondary, graded |
| ticker_class T1 | G1 against S, tier C only, direction-standardised | diagnostic, printed |
| ticker_class T2 | G1 against S, tier B only | diagnostic, printed |
| ticker_class C0 | all seven groups pooled, unadjusted | context, printed |
| ticker_class R1 | `P1` repeated on real rows only | sensitivity, printed |

## How it is judged

**Population.** v4 only, signal dates before 2026-08-11, rows with `fill_trusted` true. The headline is net of cost; gross prints beside it. v3 is a separately labelled replication of `P1` and `S1`–`S3`, run with `--era v3`. It cannot confirm or refute a v4 verdict.

**Gates.** Each exits non-zero on failure, except `GT0`.

- `GT0`: each graded side needs ≥ 30 dates and ≥ 60 positions. Failure prints `UNDERPOWERED`.
  - Exception: `S4`'s G2 side needs 30 dates and 30 positions.
- `GT1`: the era resolves to `current` and the header names it.
- `GT2`: every in-sample ticker resolves to exactly one group.
- `GT3`: the group-table hash matches the registration.
- `GT4`: summed R over all groups equals the book's summed R, within 1e-9.

**Bar.** A contrast is `INDEX-MORE-RELIABLE` only when all six criteria hold.

1. The CI95 of the meanR difference (G1 minus comparison) excludes 0 on the positive side. For `S1`–`S4` the CI is Holm-adjusted across the secondary contrasts run (four on v4).
2. G1's hit rate is not lower, with the date-clustered CI of the difference reaching above 0.
3. G1's share of the book's [maxDD](../../../glossary.md#maxdd) episode is no larger than its share of positions in it.
4. The difference keeps its sign without Mar–Apr 2025, without Feb–Apr 2026, and in every calendar year where each side has ≥ 10 positions.
5. The difference keeps its sign in ≥ two-thirds of the half-years where each side has ≥ 10 positions.
6. The difference keeps its sign with the largest ticker of each side removed.

**PBO veto.** A CSCV over monthly group meanR checks the "pick the best group" selection. It is a veto only, never evidence for G1.

| PBO | Reading |
|---|---|
| ≤ 0.25 | Supports a verdict |
| 0.25 – 0.50 | The verdict prints with "selection fragile" |
| > 0.50 | No group-level verdict ships; every graded contrast reads `NULL` |

**Forward read.** `P1` alone re-runs on signal dates after 2026-10-07 under criteria 1–3. It reads `STILL-OPEN` until each side has ≥ 30 forward dates. Dates from 2026-08-11 to 2026-10-07 sit in neither window.

## Possible verdicts

`S1`–`S4` take the same words, qualified by their comparison group. A contrast that meets the first three criteria but fails the fourth, fifth or sixth reads `NULL`. The failed criterion prints beside it.

| Token | What it means |
|---|---|
| `INDEX-MORE-RELIABLE` | `P1` meets all six criteria and PBO is ≤ 0.25 |
| `INDEX-LESS-RELIABLE (CONTRARY)` | The mirror of the bar: the CI excludes 0 on the negative side, and criteria 4–6 hold with the sign reversed |
| `MIX-ONLY` | `C0`'s pooled CI is clear of 0 but `P1`'s is not. The gap was direction or tier mix |
| `NULL` | Neither direction meets the bar, or PBO is > 0.50 |
| `UNDERPOWERED` | `GT0` fails for `P1`. Census prints, nothing is concluded |
| `FORWARD-CONFIRMED` / `FORWARD-REFUTED` | The forward read, once both sides have 30 forward dates |

## What could ship

Nothing ships. `INDEX-MORE-RELIABLE` or `CONTRARY` files a "to be tested" entry in `research/deployment-evidence.md`. A `deployment-rules.md` change waits for `FORWARD-CONFIRMED` and a separate operator ruling.

## What this study cannot tell you

- Whether any single ticker is reliable. There is no per-ticker verdict.
- Anything about sectors or non-equity ETPs. `G3` and `G4` are context only.
- Whether a different grouping would differ. A new table is a new registration.
- Anything about tier A on index ETFs. G1 has too few tier A positions.
- Anything the v4 backfill hides. The v4 prompt ran after the fact, so model recall of those dates is a standing risk.
