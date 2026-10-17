## index_vrp — does short index vol lose in the same weeks as the long-delta ladder?

<!-- outcome:start -->
> Latest outcome: `NO-TAIL-LINK` (SPY condor d0.16, mid fill, v4 deployed book); all eight secondary lines also `NO-TAIL-LINK`; M1 premium `NO-PREMIUM` on SPY and GLD, as context only; nothing ships — 2026-10-12 · [record](../../study-results/f3_structure/index_vrp.md).
<!-- outcome:end -->

_Registered 2026-10-12, before the study's first run._

**STATUS: ACCEPTED BY DEFAULT 2026-10-12 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Contested choices are parameters printed both
ways; only the defaults below carry a verdict.

## The question

On the deployed ladder book's worst days and in its four stress windows, does a
monthly short SPY iron condor lose money alongside the book?

The ladder is a bet on the underlying's direction, and nothing at entry predicts
that direction (`direction_hit` NULL, 2026-10-12). A non-directional sleeve is
the next question. Selling index volatility is the textbook one. agent-trading
has already rejected it as a standalone trade on real SPY and GLD quotes (study
0047: test Sharpe −0.50 SPY, −1.10 GLD).

This study does not re-ask whether short index volatility pays. It prints the
[variance risk premium](../../glossary.md#vrp) on SPY and GLD as context. It
grades one thing: whether a defined-risk short condor loses in the same windows
and on the same days as the deployed ladder book. If it does, short vol adds to
the book's tail instead of diversifying it, and the question is closed for this
book.

Literature (verified 2026-10-12) says the premium is compensation for crash
exposure, and the book is long delta. The prior is that the two lose together.
This study checks that prior on real quotes.

| Paper | Use here |
|---|---|
| Coval & Shumway (2001) | The premium is expected to be positive for the seller |
| Bakshi & Kapadia (2003) | Same |
| Carr & Wu (2009) | Why index ETFs, not single names, for the short side |
| Bollerslev, Tauchen & Zhou (2009) | The VRP definition: implied minus realized variance |
| Driessen, Maenhout & Vilkov (2009) | Expect the premium; do not expect it to survive costs |

## What this study is not

- **Not a profitability test.** Standalone short index vol is rejected in
  agent-trading 0001, 0002, 0019, 0023, 0047 and 0055. The premium is printed,
  not graded.
- **Not a VRP gate.** 0023 found a VIX-minus-RV20 gate "improves every symbol
  and rescues none". The VIX tercile cut here is descriptive.
- **Not `vol_sleeve` again.** That study synthesised straddles on the engine's
  own signal dates and re-wrapped the book (correlation +0.268; lesson in
  `research/lessons.md`). This sleeve runs on a fixed monthly calendar and never
  reads a signal date.
- **Not a management study.** Both arms hold to expiry. Exit rules (50% take
  profit, 21-DTE close) were 0047's subject and its biggest leak.
- **Not a read on W1.** No book covers W1. Its beta proxy carries no verdict.
- **Not a read on the straddle.** It has no max loss and no part in the verdict.

## Population and basis, fixed here

### The sleeve

- **Underlyings.** SPY is graded. GLD is printed beside it, secondary. It is the
  one real-quote chain that is not equity beta.
- **Cycles.** Every standard monthly expiry (third Friday, or the holiday
  Thursday) from the 2022-03 cycle through the last cycle whose expiry is on or
  before the last cached quote date. Cycles do not overlap: the next cycle's
  entry is after the previous expiry.
- **Entry day.** The trading day whose calendar DTE is nearest 30, ties to the
  earlier day. Entry uses only that day's rows.
- **Data.** `backtests/option_history_cache/` real end-of-day quotes, read
  directly. There is no fetch and no model price anywhere.
- **Dropped legs and cycles.** A leg with no row on the entry day is dropped and
  counted. A cycle where any leg has no row on more than 2 of its held sessions
  is dropped and counted. A single missing session is carried at the previous
  mark and counted.
- **Spot.** The option file's `Price~` on that date.

_Resolved at build (2026-10-12):_ spot is the most common positive `Price~`
across that day's chain rows. A day more than 25% from the last accepted spot is
a bad print and has no spot. One such day was dropped per underlying (SPY 177.54
on 2025-11-28, GLD 47.11 the same day). A listed strike is one with a cached row
of that type on the entry day. Delta candidates exclude a blank or zero `Delta`.

### Fills and costs

- **Default: mid** for every leg, at entry and at each daily mark, plus
  commission $0.65 per contract per side. The operator fills spreads at mid
  (memory note `operator_fills_spreads_at_mid`, 2026-09-24).
- **Printed beside it: natural.** Sold legs at the bid, bought legs at the ask,
  at entry. A sold leg with no bid fills at 0, as production does.
- **Junk quote.** A leg whose bid/ask width exceeds twice the Cboe maximum width
  for its price falls back to `Latest` and is counted. The study uses
  `scripts/backtest`'s shared junk-quote function.

_Resolved at build (2026-10-12):_ the shared function is
`simulate._is_junk_quote`, used whole, so a no-bid leg and a spread wider than
mid also count as junk. Commission is charged on every leg at entry and again at
expiry, worthless legs included.

### Size

One condor (or one straddle) per underlying per cycle. Correlations are
scale-free. Drawdown and O2 figures print at 1 contract and at the contract
count whose max loss is nearest $1,000 (the operator's stop,
`operator_sizes_on_1000_stop`), minimum 1.

### The book

- **Loader.** `load_book()` at its defaults, era v4, holdout seal applied. This
  study is not a named seal reader; forward rows stay withheld.
- **The deployed book.** `account_sim` at `config/account-sim.yml`'s registered
  cell, then `simulate()`, then `mtm_curve.book_curves(...,
  target=TARGET_POSITION)`. This is the daily marked P&L of the book as
  deployed, gross of costs. Its sessions are the comparison axis.
- **Printed beside it:** the stored book (`hedge_portfolio.book_positions`,
  `TARGET_STORED`, net), as `index_bear_hedge` does.
- **v3** prints as replication when `load_book(era="v3")` loads. A refusal is
  printed and is not an error.

_Resolved at build (2026-10-12):_ the yml carries net cap 2.50, so the
registered cell is the 2026-08-13 one: $25,000, 2% risk, 0.25 per position, net
1.50, ARM R, F1, no compounding. The 2.50 book prints as an unregistered
secondary line. The stored book is the top-3-per-day ladder-eligible rows with
`days_held`, index bears kept.

### Stress windows, fixed now

| Window | Dates | Book coverage on v4 |
|---|---|---|
| W1 2022 bear | 2022-01-01 → 2022-12-31 | none |
| W2 Aug 2024 | 2024-08-01 → 2024-08-31 | yes |
| W3 Mar–Apr 2025 | 2025-03-01 → 2025-04-30 | yes |
| W4 Feb–Apr 2026 | 2026-02-01 → 2026-04-30 | yes |

W1 has no book. For W1 only, a **beta proxy** prints: the v4 book's daily P&L
regressed on SPY's daily return over its own sessions, applied to 2022 SPY
returns. It is descriptive and carries no verdict.

## Plan-time observations, disclosed

Written before the first run, from the 2026-10-12 scoping pass and agent-trading
notes. None read this study's output.

- The cache holds 50 of 53 SPY and 52 of 53 GLD third-Friday cycles with an ATM
  call and put quoted every session. The SPY gaps are one-session holes.
- agent-trading 0047's real-quote condor lost. The worst 5% of trades were the
  entire loss on both symbols. The prior for T1 is negative.
- The v4 book's MTM sessions start in 2024-01, so W1 is uncovered and the graded
  windows are three.

## What it compares

Labels are `index_vrp ARM S` and `ARM C` ([index](../../arm-index.md#index_vrp)).
Both arms hold to expiry and settle at intrinsic.

| Object | What it does | Kind |
|---|---|---|
| `index_vrp ARM S` | Sells the call and put at the listed strike nearest spot. Undefined risk, so no verdict | descriptive cut |
| `index_vrp ARM C` | Short [iron condor](../../glossary.md#iron-condor): shorts at the cached `Delta` nearest ±0.16, wings nearest 0.03 × spot beyond. Graded on SPY at mid | PRIMARY |

### ARM S — short ATM straddle (descriptive)

- Sell one call and one put at the listed strike nearest spot on the entry day
  (ties to the lower strike).
- Hold to expiry. Settle at intrinsic on the expiry-day `Price~`.
- It has no O2 figure and takes no part in the verdict.

### ARM C — short iron condor (graded)

- **Shorts.** The call and the put whose cached `Delta` on the entry day is
  nearest ±0.16 (0047's choice).
- **Wings.** Long call at the listed strike nearest `short call + 0.03 × spot`.
  Long put nearest `short put − 0.03 × spot`. A wing that would land on the
  short strike moves one listed strike out.
- **Max loss** = the wider wing's width − net credit, per share × 100.
- Hold to expiry. Settle at intrinsic.

## How it is judged

### M1 — the variance risk premium (context)

Per cycle and underlying:

- **Premium, price form.** `(straddle credit at mid − |S_T − K|) / S_entry`.
- **Premium, variance form.** `IV_entry² − RV²`, where `IV_entry` is the mean of
  the two ATM legs' cached IV and `RV` is the annualised close-to-close realized
  volatility of `Price~` from entry to expiry (252-day convention). It prints in
  vol points as `IV_entry − RV`.
- Mean, median, share positive, and a CI95 from an iid bootstrap over cycles
  (they do not overlap), 10,000 draws, seed 20261012.
- **Cut by VIX tercile at entry.** The tercile is VIX's percentile at entry
  within the trailing 756 sessions of
  `backtests/mech_regime/spy_base_rate_daily.csv`, split at 1/3 and 2/3. Only
  past values enter the percentile.

The premium prints `PREMIUM` when its price-form CI95 lower bound is above 0,
else `NO-PREMIUM`, per underlying. Context only.

### M2 — arm P&L, with MFE and MAE (context)

Per cycle: P&L at expiry, the worst daily mark (MAE) and the best daily mark
(MFE) over the hold. All print in dollars and as a share of max loss (condor) or
credit (straddle). The table is by underlying, arm, fill and VIX tercile. The
worst 5 cycles are listed by date.

### M3 — tail overlap with the book (graded)

The sleeve is the SPY condor, arm C, mid fill. Its daily mark-to-market change
is aligned to the book's sessions.

| Id | Statistic | Population |
|---|---|---|
| T1 | Mean daily sleeve P&L on the book's worst 5% of sessions, CI95 | v4 book sessions with a sleeve position open |
| T2 | Per window W2–W4: book P&L and sleeve P&L, summed over the window | v4 |
| T3 | Daily correlation, sleeve vs book, all common sessions and the book's worst-decile sessions, CI95 | v4 |
| T4 | Max drawdown of book alone vs book + sleeve, and a block-bootstrap band | v4 |
| T5 | O2 total-loss overlay, book alone vs book + sleeve | v4 |

- **CIs on T1 and T3.** A stationary block bootstrap over sessions
  (`lib/ruin_walk.py::stationary_indices`), mean block 10 sessions, 10,000
  paths, seed 20261012. Blocks 5 and 20 print beside it.
- **T4 bands.** `lib/path_bootstrap.py::bootstrap_drawdown_blocks`, blocks
  (5, 10, 20), capital $25,000.
- **T5, O2.** At the session where the combined book reserves the most capital
  (book reserved plus the open condor's max loss), every open position is marked
  at minus its max loss. The loss prints as a share of the equity just before
  that session, for the book alone and for book + sleeve. `ruin_walk._shock` is
  reused where the book's `Table` can carry the sleeve's positions. Otherwise
  the same rule is computed directly and the report says which. A block
  bootstrap cannot invent a crash, which is why T5 prints.

_Resolved at build (2026-10-12):_ T5 is computed directly, because the book's
`ruin_walk.Table` holds only ladder candidates. The loss per open position is
its previous-session mark plus its max loss. Equity is capital plus the
previous-session level. T1 and T3 take the sleeve's level at the last trading
day on or before each book session, then difference it. Each bootstrap path
re-finds its own worst sessions. T4 bands use 10,000 resamples, seed 20261012.

## No-lookahead rules, tested

- Strikes, deltas, IV and spot for a cycle come from the entry day's rows only.
- The VIX tercile uses only VIX closes on or before the entry day.
- The beta proxy for W1 is fitted on v4 sessions and applied to 2022. It is
  descriptive because the fit uses later data. It never enters a verdict.
- A cycle's settlement uses the expiry-day `Price~`, which is known only at
  expiry. Daily marks before it use that day's rows only.

## Verdicts, worded now

Graded on the SPY condor, mid fill, v4 deployed book.

| Token | When |
|---|---|
| `LOSES-TOGETHER` | The sleeve loses in at least 2 of the 3 covered windows (W2–W4) in which the book loses, **and** T1's CI95 upper bound is below 0 |
| `DIVERSIFIES` | T1's CI95 lower bound is above 0, **and** T4's realized max drawdown of book + sleeve is below the book's alone |
| `NO-TAIL-LINK` | Neither |

- If the book loses in fewer than 2 covered windows, the window clause cannot be
  met. The verdict is then decided by `DIVERSIFIES` or `NO-TAIL-LINK` alone, and
  the report says so.
- The GLD condor, the natural fill, the stored book and v3 each print their own
  token, labelled secondary. They carry no verdict.

### Contested choices, printed both ways

| Choice | Default | Printed beside it |
|---|---|---|
| Fill | mid | natural |
| Condor short delta | 0.16 | 0.30 |
| Book | deployed (`TARGET_POSITION`, gross) | stored (`TARGET_STORED`, net) |
| T1/T3 block length | 10 | 5, 20 |

## Anti-tuning

No configuration is picked from the grid above, so no PBO read applies. If a
later registration picks one of these variants, it owes a `lib/pbo.py` read.

## What could ship

Nothing ships whatever it prints. A `DIVERSIFIES` token would earn a new
registration with a sizing and an exit rule, not a deployment.

## Output

`backtests/study_output/index_vrp-latest.txt`, a per-cycle CSV
`index_vrp-latest.csv`, and the study-results record. The report header names
the era, the registration, the seed and the seal line.
