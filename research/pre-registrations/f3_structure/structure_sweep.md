## structure_sweep — would another structure on the same 2026 plays have done better?

<!-- outcome:start -->
> Latest outcome: not yet run.
<!-- outcome:end -->

_Registered 2026-10-22, before the study was built or run._

**STATUS: ACCEPTED BY DEFAULT 2026-10-22 on the drafter's recommended
defaults; the operator asked for a wide net and deferred the details. A
revisit after a result is a NEW registration, never an edit.**

## The question

The 2026 book lost money, and the plays that followed the ticker's trend lost
most. Holding the analysis's ticker, signal date and expiry fixed, would a
different option structure have made money on the same plays?

This is a wide net. Eight structures are tried against the play as proposed.
The design pays for the width twice: a Holm correction across the arms, and a
second sample that only a later fetch can price.

| Paper | Use here |
|---|---|
| Holm (1979) | Step-down correction across the graded arms |
| Bailey, Borwein, López de Prado & Zhu (2017) | PBO by CSCV across the arm matrix |
| Goyal & Saretto (2009) | Prior that rich single-name IV favours sellers |
| Coval & Shumway (2001) | Prior that short premium is paid for crash risk |

## What this study is not

- **Not an index test.** `index_vrp` already sold SPY volatility and found no
  premium at expiry. This study sells and buys single-name structures on the
  analysis's own tickers and dates.
- **Not a selection test.** Every arm trades the same rows. Only the wrapper
  changes.
- **Not an exit study.** Each arm uses production's exit profile for its sign.
- **Not a ship decision.** See *What could ship*.

## Population and basis, fixed here

- **Loader.** `load_book()` at its defaults, era v4, holdout seal applied.
  This study is not a named seal reader. Rows dated 2026-09-23 or later stay
  withheld.
- **Rows.** `source == real` rows with a signal date in 2026. `tweak` rows
  print as a secondary line. `pending` rows are excluded, as the loader does.
- **Ticker, expiry, entry day.** The play's ticker and signal date. The
  expiry is the play's own front expiry. The entry day is the production fill
  day, read from the row's `dte_entry` (`bear_rewrap.recorded_entry_date`),
  never re-derived from a cache that has since grown.
- **Spot.** The most common positive `Price~` across the entry day's cached
  rows for that ticker and expiry, as `index_vrp` resolved it.
- **Pricing.** Production's shared functions, imported, never copied: entry
  fill, junk-quote rule, zero-bid mark, carry rule and defined-risk clamp, as
  `bear_rewrap` imports them. No model price anywhere.
- **Costs.** Commission $0.65 per contract per leg per side, slippage 0. This
  is production's `commission_only` basis, because the operator fills at mid.
- **Exits.** The frozen harness `replay()`. A net debit uses `DEBIT_PROD`. A
  net credit uses `CREDIT_PROD`. The harness's $1,000 dollar stop applies to
  both.
- **Sizing.** `financed_spread.size_contracts`, production's port. A structure
  with no defined max loss trades 1 contract.

_Resolved at build (2026-10-22):_ `DEBIT_PROD` means production's effective
debit profile, read through `simulate._effective_sim_cfg`. On BEAR_HE dates
that adds the regime trail, without which `ARM P` cannot reproduce those rows.
Every arm's path stops at the play row's `path_data_end`, as `ARM P`'s must.
Grid days before the entry day are unpriced, as production leaves them.

### Two samples, split by fetch time

A cache file's mtime is its fetch time. The split instant is fixed below.

| Split instant | Value |
|---|---|
| local | 2026-10-22 23:00 +08:00 |

| Sample | Cache it may read | Rows |
|---|---|---|
| S1, primary | files with mtime at or before the split | every row an arm can price from that cache |
| S2, replication | the whole cache after the study's fetch | rows that arm could not price in S1 |

S1 and S2 never share a row within an arm. Strike selection for S1 runs on the
S1 cache only, so a later fetch cannot move an S1 strike.

## Plan-time observations, disclosed

Written before the module exists. None of it read this study's output.

- **The drafter read the 2026 export on 2026-10-22.** That pass read the bare
  export, sealed dates included. It found net −$18.7k on 366 closed rows. It
  found plays aligned with `price_vector` lost and plays against it won. Labels
  that agreed with the play lost too. SPY was flat from May.
- **So the prior favours `ARM F`, `ARM C` and `ARM B`.** The flipped play and
  the neutral sellers are the arms the descriptive pass points at. That is why
  S2 must replicate before anything is a candidate.
- **Coverage census, cache as of 2026-10-22.** Counted from file names and
  entry-day deltas only, on 356 real rows:

  | Structure | Rows priceable |
  |---|---|
  | two puts below and two calls above spot | about 187 |
  | 0.16 condor | about 64 |
  | iron butterfly | about 105 |
  | straddle | about 116 |
  | calendar | about 71 |
- **The fetch is not sized to the verdict.** It targets every row an arm cannot
  price, about 1,700 contracts before probes.

## What it compares

Labels are `structure_sweep ARM P` to `ARM K`
([index](../../arm-index.md#structure_sweep)). Every arm is built on the
entry day's cached rows only.

| Object | What it does | Kind |
|---|---|---|
| `ARM P` | The play's own legs, re-priced by this study | control |
| `ARM F` | The same legs with every quantity negated | arm |
| `ARM T` | Same direction and strikes, the other option type | arm |
| `ARM C` | Short iron condor | arm |
| `ARM B` | Short iron butterfly | arm |
| `ARM D` | Long ATM straddle | arm |
| `ARM G` | Long strangle | arm |
| `ARM K` | Long ATM call calendar | arm |
| `ARM S` | Short strangle, no defined max loss | descriptive cut |

### ARM P — the play, re-priced (control)

The stored legs go through this study's own pricing path. A row whose stored
`realized_pnl_abs` this path does not reproduce within $1 plus costs is
printed and dropped from every arm. Paired differences use `ARM P`, never the
stored figure.

_Resolved at build (2026-10-22):_ "within $1 plus costs" means this path's P&L,
net of its own commission, lies within $1 of the stored `realized_pnl_abs`,
which is net of costs too.

### ARM F — flipped

Every leg's quantity is negated. A bull call debit becomes a bear call credit
on the same strikes. The exit profile follows the new sign.

### ARM T — type swap

A vertical keeps its direction and strikes but swaps calls for puts, or puts
for calls. A bull call spread at K1/K2 becomes a bull put spread at K1/K2.
Non-vertical plays have no `ARM T`.

### ARM C and ARM B — short neutral, defined risk

- **`ARM C` shorts.** The call and put whose cached entry-day `Delta` is
  nearest ±0.16, as in `index_vrp`.
- **`ARM B` shorts.** The call and put at the listed strike nearest spot with
  both types cached. Ties go to the lower strike.
- **Wings, both arms.** The listed strike nearest `short ± 0.03 × spot`. A wing
  that lands on its short moves one listed strike out. A side with no wing
  leaves the row unpriced for that arm.

_Resolved at build (2026-10-22):_ the pickers now refuse an off-target strike.
These tolerances were added after the first run, which on sparse single-name
caches took strikes far from target. They are the scoping census's own bands,
fixed before the re-run and not tuned to its result. A refused pick leaves the
row unpriced for that arm. The first run is kept at
`backtests/study_output/structure_sweep-run1-untoleranced-20261022.txt`.

| Pick | Accepted when |
|---|---|
| `ARM C`, `ARM G`, `ARM S` shorts | cached \|Delta\| within 0.05 of 0.16 |
| ATM strike (`ARM B`, `ARM D`, `ARM K`) | within 3% of spot |
| Wing (`ARM C`, `ARM B`) | 0.5 to 2 times 0.03 × spot from its short |

### ARM D, ARM G and ARM S — straddles and strangles

- **`ARM D`** buys the `ARM B` call and put.
- **`ARM G`** buys the `ARM C` short strikes.
- **`ARM S`** sells the `ARM C` short strikes with no wings. It has no max
  loss, so it is printed and never graded.

### ARM K — long ATM call calendar

- **Front leg.** Sell the play's expiry call at the `ARM B` strike.
- **Back leg.** Buy the same strike at the nearest later cached expiry at
  least 14 calendar days after the front.
- **Path.** The harness grid ends at the front expiry, so the calendar closes
  there at both legs' marks.

_Resolved at build (2026-10-22):_ `ARM P` is exempt from the entry-day rule. It
mirrors production's fill, which may carry a prior mark. `ARM F` and `ARM T`
need an entry-day row on every leg.

## How it is judged

### Metric

- **Primary.** R, net P&L over capital at risk. Capital at risk is the debit
  paid, or a credit structure's structural max loss.
- **Beside it.** Net dollars per position at production sizing.

_Resolved at build (2026-10-22):_ a structure with no defined max loss has no
capital at risk, so it has no R. That covers `ARM F` on a long single option,
straddle or strangle. It also covers an entry whose credit meets or exceeds its
widest wing. Such rows are counted in coverage and left out of that arm's grade.

### Per arm, in S1

- **Absolute.** Mean R with a date-clustered CI95
  (`protocol.boot_ci_by_date`), 10,000 draws, seed 20261022.
- **Paired.** Mean of `R(arm) − R(ARM P)` on rows both priced, date-clustered
  CI95 (`protocol.boot_ci_paired_by_date`).
- **p-value.** Two-sided, from the same paired bootstrap: twice the smaller
  share of draws on either side of zero.
- **Holm.** Across the seven graded arms (`ARM F` to `ARM K`), family α 0.05.

### Across arms

- **PBO.** `lib/pbo.py::cscv` on the date × arm matrix of mean R, `ARM P`
  included, S = 16, on S1.

_Resolved at build (2026-10-22):_ a date an arm did not price is a missing cell.
Each cell carries its mean R and a presence flag, read through
`pbo.ratio_metric`, so a block's statistic is the mean of the date means it
holds. Head padding to a multiple of 16 adds empty rows.

### Descriptive cuts, never graded

- Aligned `price_vector` bucket (joined from AnalysisClaude on the identity
  key), H1 against H2, and the mechanical direction label.
- `tweak` rows, and v3 where the cache can price it.

_Resolved at build (2026-10-22):_ a play is aligned when its direction has the
sign of `price_vector`, against when opposite, and neutral otherwise. H1 is
January to June. The v3 cut reads v3 real rows dated 2026.

## Gates

- **G-REPRO.** If more than 10% of rows fail `ARM P`'s reproduction check, the
  study refuses with exit 3. The pricing path is then not production's.
- **G-THIN.** An arm with fewer than 30 rows or 15 signal dates in S1 prints
  `THIN` and leaves the Holm family. The family shrinks; α does not.

## No-lookahead rules, tested

- Strikes, deltas, IV and spot come from entry-day rows only.
- S1 reads no cache file with an mtime after the split.
- The calendar's back expiry is chosen from expiries cached by the entry day.
- `price_vector` is the stored value from the analysis row, known at signal.

## Verdicts, worded now

| Token | When |
|---|---|
| `CANDIDATE` | S1 paired difference > 0 and Holm-significant, **and** the S2 paired CI95 lower bound > 0, **and** PBO < 0.5 |
| `S1-ONLY` | S1 positive and Holm-significant, but S2 or PBO fails |
| `LOSES-TO-PLAY` | S1 paired difference < 0 and Holm-significant |
| `NULL` | none of the above |
| `THIN` | G-THIN fired |

- An S2 with fewer than 30 rows for an arm cannot replicate it. That arm
  stays `S1-ONLY` at best, and the report says S2 was too thin.
- **Study token.** `CANDIDATE-FOUND` if any arm prints `CANDIDATE`, else
  `WIDE-NET-NULL`. The report prints it as `>>> structure_sweep TOKEN <<<`.

## Anti-tuning

- Eight arms and fixed strike rules. Nothing is picked from a grid before the
  run.
- PBO is computed and printed whatever the Holm result.
- A revisit of a strike delta, wing width or calendar gap is a new
  registration.

## What could ship

Nothing ships whatever it prints. A `CANDIDATE` earns a forward registration
graded on dates after the seal, with sizing fixed in advance. A
`LOSES-TO-PLAY` is a fact to record, not a rule.

## Output

`backtests/study_output/structure_sweep-latest.txt`, a per-row CSV
`structure_sweep-latest.csv`, and the study-results record. The report header
names the era, the registration, the seed, the split instant and the seal line.
