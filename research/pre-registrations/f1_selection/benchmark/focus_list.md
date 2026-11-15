## focus_list — does trading only a fixed watchlist beat the card?

<!-- outcome:start -->
> Latest outcome (v4, exports dated 2026-10-26, in-sample):
> `>>> focus_list P1 (ARM F minus ARM C, paired by date, in-sample v4): FOCUS-BEATS-CARD <<<`
> on `P1  gain +0.140  CI95 [+0.061, +0.220]  dates 185  ARM F positions 289`.
> The v3 replication reads `NULL` on `P1  gain -0.064  CI95 [-0.241, +0.096]  dates 64`.
> `>>> focus_list FORWARD (one read from 2026-11-16): STILL-OPEN <<<` — 2026-11-15 · [record](../../../study-results/f1_selection/benchmark/focus_list.md).
<!-- outcome:end -->

_Registered 2026-11-15. First forward date 2026-11-16._

The operator accepted this file on 2026-11-15. It was written that day from two operator statements:

- "the trick is to not take all the trades. i want to focus on a few stock in a sector and just focus on that."
- "I want semis, AI, GLD, QQQ, and two more of traditional."

The operator named the groups. The drafter filled two of them by counts, and the operator accepted both fills. The four decisions settled at acceptance:

| # | Decision | Ruling |
|---|---|---|
| 1 | Which names are "AI" | CRWV, GOOG, GOOGL, PLTR, META |
| 2 | Which two names are "traditional" | XLE and XLF |
| 3 | What the list is compared with | The card's own top-3 picks on the same dates |
| 4 | When the forward window starts | 2026-11-16, the day after acceptance |

The list is frozen.

## The question

Each day the card ranks every eligible play and takes the top three. Would the operator do better by looking only at a fixed watchlist and taking up to three of those?

"Better" needs all of these together:

- a higher mean [R](../../../glossary.md#r) than the card on the same dates;
- a higher mean R than random picks on the same dates;
- a positive mean R of its own;
- the same sign without either dominant window, and without the list's largest name;
- no worse a return for the drawdown it carries.

A total P&L figure alone never answers it.

## What this study is not

- **Not a test of how many trades to take.** Both arms take at most three picks a day from Tier A and B. Only the names they may pick from differ. Dates on which only the card trades are not graded.
- **Not the card's $500 skip rule.** Neither arm sizes a position or skips an expensive one. The comparison is the tier ladder's top three, before sizing.
- **Not a ticker ranking.** One fixed list is graded. No name and no group gets its own verdict.
- **Not a list search.** No name or group is added or dropped after a run.
- **Not a sizing or cap study.** The journal's per-ticker and net caps are unchanged and are not graded here.
- **Not a read of the operator's own fills.** The graded figures come from backtest rows. Live fills are printed as context only.
- **Not a ship.** See [What could ship](#what-could-ship).

## Definitions

### The watchlist, fixed here

The list is `LW`: 14 tickers in five groups. GOOG and GOOGL are one company and both are listed.

| Group | Object type | Members | How it was filled |
|---|---|---|---|
| semis | population scope | MU, TSM, SMH, NVDA, AMD | Every name of the `SEMIS` cluster the operator opened live |
| AI | population scope | CRWV, GOOG, GOOGL, PLTR, META | Single names, not ETFs, outside `SEMIS` with three or more live opening trades; plus GOOGL, GOOG's other share class |
| GLD | population scope | GLD | Named by the operator |
| QQQ | population scope | QQQ | Named by the operator |
| traditional | population scope | XLE, XLF | The ticker with the most eligible rows in each of `ENERGY` and `FINL`, counting each cluster's members and its proxy |

- **`SEMIS`** is the cluster of that name in `scripts/backtest_study/lib/sectors.py`, frozen by [`hedge_portfolio`](../../f5_hedging/hedge_portfolio.md).
- **Live opening trades** are journal rows with action `OPEN`, 2026-07-01 to 2026-11-12.
- **"AI" has no table in the repo.** The rule above picks four companies by count. The operator accepted them as the AI group.
- **"Traditional" is read as old-economy sectors.** The operator accepted XLE and XLF, having opened neither live.

Every fill rule used counts only. No outcome column was loaded.

**The list's hash.** GF2 checks the sha256 of this exact string:

```
semis:MU,TSM,SMH,NVDA,AMD|AI:CRWV,GOOG,GOOGL,PLTR,META|GLD:GLD|QQQ:QQQ|traditional:XLE,XLF
9a44a41796f10479cee7187b86b1feb9b90ca533cd735e34e6324cfe93413395
```

### Eligible, and the card

- **Eligible** is `protocol.ladder_eligible`: a row in Tier A or Tier B. The tier comes from `mapping.ladder_tier`, which `load_book()` applies to every row.
- **The card's picks** are `protocol.top_k_per_day(book, ladder_rank, k=3, ladder_eligible)`, on rows sorted by ticker first. [`account_sim`](../../../arm-index.md#account_sim) makes the same call on rows in export order.
- **Ties.** `top_k_per_day` keeps the input order of tied rows. With the rows sorted by ticker, a tie goes to the ticker earlier in the alphabet, on every arm. So export row order never decides a pick.
- **R** is the row's realized R on the study basis `load_book()` returns, net of commission.
- **Exit date.** A row carries no exit date. It is the grid day at `days_held`, as `lib/mtm_curve.py` derives it.

## Dependencies

### `holdout_seal`

[`holdout_seal`](../../f4_deployment/holdout_seal.md) seals signal dates from 2026-09-23. Its list of named readers is closed, and a forward read accepted after 2026-10-09 waits for the unseal. So this study's forward read prints census counts only until the seal lifts.

### The selection ledger

[`ticker_class`](ticker_class.md) put its trials on a separate selection ledger. This study adds one graded contrast, `P1`, to that ledger. The report prints the line it added.

## Population and basis, fixed here

- **Era.** v4 only, from the bare exports in `backtests/to_evaluate/`, with `STUDY_ERA=current`. `load_book()` runs at its defaults: real rows plus `strike_expiry_tweak` proxy rows, `bs` excluded, pending open rows dropped. _Resolved at build (2026-11-15):_ the run refuses any other era with exit 3.
- **Pending rows.** _Resolved at build (2026-11-15):_ the loader drops a pending row before the arms rank a date, as it does for every study. Both arms then hold the next row down on that date. The report prints how many picks and dates that touches. The in-sample read can move as those rows close.
- **In-sample window.** Signal dates before 2026-09-23. The study cuts at that date itself, so the window stays the same after the seal lifts. The list was filled from live trades made from 2026-07-01, so the last months of this window were known when it was filled.
- **Forward window.** Signal dates from 2026-11-16. See [Forward read](#forward-read).
- **Neither window.** Signal dates from 2026-09-23 through 2026-11-15. The operator traded these names live on those dates before naming the list.
- **Unit.** A signal date. Rows inside a date share the tape, so every interval resamples dates.
- **v3.** A separately labelled replication. See [v3 replication](#v3-replication).

## Plan-time observations, disclosed

### Counts, from a census with no outcome column loaded

Census of 2026-11-15, on the exports then on disk, in-sample window.

| Population | Rows | Signal dates | Tickers |
|---|---|---|---|
| Whole book | 1,806 | 279 | 182 |
| Eligible, Tier A/B | 699 | 232 | 117 |
| Eligible, on `LW` | 294 | 185 | 14 |

| Group | Eligible rows | Eligible dates | Live opening trades |
|---|---|---|---|
| semis | 158 | 125 | 69 |
| AI | 54 | 48 | 19 |
| GLD | 51 | 51 | 3 |
| QQQ | 12 | 12 | 11 |
| traditional | 19 | 19 | 0 |
| `LW` | 294 | 185 | 102 of 117 |

| What the arms would take, in-sample | Count |
|---|---|
| ARM F dates | 185 |
| ARM F positions | 289 |
| ARM F positions the card also takes | 244, or 84% |
| ARM F dates on which both arms hold exactly the same picks | 48 |
| ARM F dates on which every ARM F pick is also a card pick | 146 |
| ARM F dates with more than three eligible `LW` rows | 5 |
| ARM F dates with no eligible row off the list | 45 |
| ARM F dates with a spare eligible row of a tier ARM F took | 135 |
| ARM C positions, on 232 dates | 543 |

Four things follow from the counts.

- **The watchlist is most of what the operator already trades.** It holds 102 of 117 live opening trades.
- **The watchlist is most of what the card already takes.** 84% of ARM F's positions are card picks too. On 48 dates the two arms are identical and the difference is zero.
- **On most other dates the list's picks are among the card's.** There the difference is the list's rows against the card's extra, off-list rows. So `P1` mostly measures what those extra names add or cost.
- **ARM F almost never chooses.** Only 5 dates offer more than three eligible list rows.

NVDA holds 84 of the list's 294 eligible rows and 9 of its 102 live opening trades.

### Outcomes seen before this file was written

The list was not filled from outcomes, but outcomes on these names were known.

| Source | What was seen |
|---|---|
| `ticker_class`, 2026-10-07 | `P1 NULL`. `S2`, index ETFs against semiconductor names on bear plays, `NULL`. PBO 0.367 |
| `ticker_pattern`, 2026-10-23 | `TICKER-EFFECT`, p = 0.0383, "selection fragile", `FLAGGED GLD`. Its per-name table was printed |
| `ticker_pattern`, re-run 2026-10-26 | `P1 NULL`; the GLD flag was gone |
| Profit-factor review, 2026-10-29 | A one-per-ticker cap did worse than dropping positions at random. "The live problem is single-name concentration" |
| `concurrency_correlation`, 2026-09-19 | A cap on same-direction-and-sector positions printed `RESTATEMENT` |
| Journal, read 2026-11-15 | 122 closing fills, 2026-07-07 to 2026-11-12, a net loss. Trades matched to a card play were near flat. Unmatched trades carried nearly all of the loss |
| Journal, read 2026-11-15 | The three largest losing closes were on SMH and TSM, and another large one on AMD |
| Journal report, 2026-11-12 | Four tickers over the per-ticker cap: GOOG, QQQ, MU, TSM. All four are on `LW` |

Dollar figures stay out of this file, because they reveal position sizes.

### What these observations shaped

- **The forward read is the test.** The operator knows the live result on each of these names, and GLD was once flagged by a study. No in-sample figure can confirm a list chosen with that knowledge.
- **The random band exists** for the same reason. See [`ARM N`](#arm-n--random-picks-on-the-same-dates).
- **The concentration clause exists** because one name carries over a quarter of the list's rows.
- **`D1` exists** because 84% of ARM F's positions are card picks. It compares the list with the card's best other names.
- **No in-sample result separates the list from its sectors' moves.** Every eligible row is a bull play, and R on this book mostly follows the direction of the underlying. An in-sample pass may only record how these names moved in 2024–26.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `focus_list` ARM F | arm | Up to three `LW` picks per date | HEADLINE |
| `focus_list` ARM C | control | The card's top three per date | The comparison |
| `focus_list` ARM N | control | Random eligible picks, same dates, tiers and counts | The null band |
| `focus_list` P1 | arm | ARM F minus ARM C, paired by date | PRIMARY, graded |
| `focus_list` D1 | descriptive cut | ARM F minus the card rebuilt without `LW` names | Printed |
| `focus_list` D2 | descriptive cut | `P1` with the semis group alone as the list | Printed |
| `focus_list` D3 | descriptive cut | ARM F's positions and mean R by group | Printed |
| `focus_list` L-LIVE | descriptive cut | Journal closes from 2026-11-16, on-list and off-list | Printed to `journal/` only |

### ARM F — the watchlist

On each in-sample signal date, keep the eligible rows whose ticker is on `LW`. Rank them with `ladder_rank` and take up to three. A date with no eligible `LW` row is not an ARM F date.

### ARM C — the card

`top_k_per_day` on the whole in-sample book. The report prints the share of ARM F positions that ARM C also took.

### L-LIVE — the journal, kept out of the report

_Resolved at build (2026-11-15):_ `L-LIVE` writes one file under `journal/`. Until the seal lifts that file holds counts only, because a win rate on live closes is an outcome on sealed dates. The study report names the file and prints nothing from it.

### D1 — the list against the card's other names

Rebuild the card from eligible rows that are not on `LW`. Pair it with ARM F by date, as `P1` does, on the ARM F dates where that rebuilt card has a pick. The report prints how many dates that leaves. On the census, 45 of 185 ARM F dates have no eligible row off the list.

### ARM N — random picks on the same dates

For each ARM F date, draw as many Tier A rows and as many Tier B rows as ARM F took, without replacement, from that date's eligible rows of the same tier. Repeat for 2,000 draws with a printed seed. Each draw is scored against ARM C exactly as ARM F is. The band is the 95th percentile of the 2,000 gains.

Matching the tier keeps the band from crediting the list with the ladder's own Tier A preference. On a date where a tier holds no more rows than ARM F took, the draw copies ARM F. Those dates add no spread, which makes criterion 2 harder to pass, not easier.

## How it is judged

### The statistic

For each ARM F date `i`:

```
X_i  = mean R of ARM F's picks on date i  −  mean R of ARM C's picks on date i
gain = mean of X_i over ARM F dates
```

The 95% interval resamples ARM F dates with replacement, `BOOT_N` = 10,000 draws, percentile bounds. Every date counts once, however many picks it holds. No existing helper computes this, so the module adds it. The report prints [PF](../../../glossary.md#pf) for both arms beside it, from `protocol.pf_paired_by_date`, never without the mean R.

Criterion 3 uses `protocol.boot_ci_by_date`, which weights every position equally. The two weightings differ, and the report prints ARM F's mean R both ways.

### Why there is no PBO read

A PBO read grades a pick made from many configurations by outcome. Here one list is graded, and it was filled by counts. `ARM N` and the forward read do that job.

### Expected outcome, written before the run

`NULL`. Every ticker and sector study so far has read `NULL` or a restatement. The two arms share 84% of ARM F's positions, so the gain comes mostly from the card's extra off-list rows. If the gain is positive, criterion 5 is where it is most likely to fail.

## Gates

- **GF0 power.** ARM F has at least 30 dates and 60 positions in the window being read. On failure the read prints `UNDERPOWERED`.
- **GF1 era.** `load_book()` resolves era `current` and the header names it. On failure: exit 3, as the loader does.
- **GF2 list.** The report prints `LW` by group and a hash of it. The hash matches the one recorded under [The watchlist](#the-watchlist-fixed-here). On failure: exit 1.
- **GF3 window.** No in-sample row is dated 2026-09-23 or later. No forward row is dated before 2026-11-16. On failure: exit 1.
- **GF4 subset.** Every ARM F pick is an eligible row of the book ARM C was built from. On failure: exit 1.
- **GF5 band.** On at least 30 ARM F dates, some tier ARM F picked from holds more eligible rows than ARM F took from it. On failure criterion 2 reads `NOT EVALUABLE`.

## Bar for a candidate

`P1` reads **FOCUS-BEATS-CARD** only when all six hold:

1. **Gain.** The 95% interval of the gain lies above 0.
2. **Not random.** The gain exceeds `ARM N`'s 95th percentile.
3. **Own edge.** ARM F's mean R has a date-clustered 95% interval above 0 (`protocol.boot_ci_by_date`, key `R`).
4. **Windows and years.** The gain keeps its sign without March–April 2025 and without February–April 2026 (`protocol.window_cuts`). It is positive in every calendar year where ARM F has 10 or more positions. "Sign" here and in criterion 5 means the point estimate.
5. **Concentration.** The gain keeps its sign with the list's largest name removed and ARM F rebuilt. The largest name is the one with the most ARM F positions. ARM C is unchanged.
6. **Drawdown.** Total R divided by the depth of the worst drawdown is at least as high for ARM F as for ARM C. Each curve is cumulative R by exit date. Both curves use ARM F's dates only, so the larger book gains nothing from its size.

**Edge cases of criterion 6.** If ARM F's total R is 0 or below, the criterion fails. A curve with no drawdown counts as the better of the two. If neither has one, the criterion holds.

**Limit of criterion 6.** A curve booked at the close of each trade understates a drawdown that open positions share. The report prints the mark-to-market drawdown of both arms beside the criterion, from `mtm_curve.book_curves`. That figure is in dollars at each row's own contract count, printed with the number of positions whose marked exit reconciles to the stored result. It is context and does not set the verdict.

## Verdicts, worded now

`P1` takes the first row, from the top, whose condition holds.

| Verdict | When | In plain words |
|---|---|---|
| `UNDERPOWERED` | GF0 fails | Too few list trades to say anything |
| `FOCUS-BEATS-CARD` | All six criteria hold | The list did better than the card and better than chance |
| `FOCUS-TRAILS-CARD` | The gain's interval lies below 0. The gain is also negative without each dominant window, and with the largest name removed | The list did worse than the card |
| `NOT-THE-LIST` | Criterion 1 holds and criterion 2 was evaluated and fails | Random picks beat the card as well; the names are not why |
| `NULL` | Anything else, including criterion 2 `NOT EVALUABLE` | No difference shown. The failed criteria are printed |

## Forward read

The forward read runs once. It runs on the first suite run, after the seal lifts, at which ARM F holds 30 forward dates and 60 positions whose trades have all closed. Before that it prints census counts and `STILL-OPEN`.

_Resolved at build (2026-11-15):_ three points.

- While the seal holds, the loader withholds every forward row. The census is then the loader's count of withheld rows.
- "All closed" is a complete prefix: the forward dates before the first one that still holds a pending Tier A/B row.
- The read is stored in `backtests/study_output/focus_list-forward-read.json`, and later runs print that file. The output cleaner pins it, so a clean cannot cause a second read.

| Verdict | When |
|---|---|
| `STILL-OPEN` | The counts are not met, or the seal has not lifted |
| `FORWARD-CONFIRMED` | Criteria 1 and 3 both hold on the forward dates |
| `FORWARD-REFUTED` | The gain's interval lies below 0, or ARM F's mean R interval lies below 0 |
| `FORWARD-NULL` | Anything else |

Criterion 2 and the mark-to-market drawdown are printed beside it. On the in-sample census, `LW` has an eligible row on 185 of 279 signal dates, about 66%. ARM F takes about 1.56 positions per date, so the 60-position floor binds: it needs about 39 ARM F dates. That is roughly 59 signal dates, plus the time for the last trades to close.

## v3 replication

`--era v3` runs `P1` alone and prints it as "v3 replication (same path)". It covers the same market path, so it can note agreement and cannot confirm or refute. Its report goes to `focus_list-v3-<date>.txt`. The v4 `-latest.txt` is copied aside first and restored afterwards.

## Anti-tuning

- **The list is fixed:** its groups, its names and its size. A different list is a new registration and a new ledger line.
- **The comparison is fixed:** the card's top three, ranked by `ladder_rank`. No other `k`, tier set or rank.
- **The bar is fixed:** six criteria, the 95th percentile, 2,000 draws, the power floors.
- **No cut is graded.** `D1` to `D3`, the per-year table and `L-LIVE` are printed for reading.
- **No per-name or per-group verdict**, and no name is dropped from the list after a run.
- **The forward read is not repeated.** One read, at the counts fixed above.

## What could ship

**Nothing ships from this file directly.**

| Result | What the operator would do with it |
|---|---|
| `FOCUS-BEATS-CARD`, in-sample | File "to be tested" in [`deployment-evidence.md`](../../../deployment-evidence.md). Change nothing |
| `FORWARD-CONFIRMED` | Consider a watchlist line in [§2](../../../../docs/deployment-rules.md#s2): "consider only survivors on the list". It needs an operator ruling and a rollback trigger written then |
| `FOCUS-TRAILS-CARD` or `FORWARD-REFUTED` | The list is closed as a candidate. Narrowing the card to these names is not supported |
| `NOT-THE-LIST` | The card's ranking, not the list, is what the result is about. A new question, not a ship |
| `NULL`, `FORWARD-NULL`, `UNDERPOWERED` | No evidence either way. The card stands as written |
