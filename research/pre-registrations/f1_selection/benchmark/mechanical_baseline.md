## mechanical_baseline — does a fixed SPY call spread, bought every week, make money on its own?

<!-- outcome:start -->
> Latest outcome: `NOT BUILT — AWAITING SCRAPE` on the first run, 2026-10-26. 31 primary trades await a fetch (42 contracts), so no arm is graded.
<!-- outcome:end -->

_Registered 2026-10-26, before any module exists or any outcome of this rule is printed._

**STATUS: ACCEPTED 2026-10-26 by the operator, as drafted. A revisit after a result is a NEW
registration, never an edit.**

## The question

Can a rule with no model and no flow data replace the analysis picks?

The rule is `ARM X`: buy one SPY ATM/+5% call spread on the first session of each week, at the
monthly expiry nearest 65 days out, and manage it under the shipped debit exits. Four questions
are graded separately, because they can disagree.

| Object | Question | Comparator |
|---|---|---|
| `ARM X` vs zero | Does the rule make money, net of commission? | none |
| `ARM X` vs `ARM H` | Does the rule earn anything beyond SPY's own drift? | SPY held as shares |
| `ARM X` vs `ARM RND` | Is SPY a better underlying than a random name from the day's flow universe? | [`mechanical_benchmark` ARM U](../../../arm-index.md#mechanical_benchmark), reused legs |
| `ARM X` vs `ARM BK` | Does the rule beat the book it would replace? | the v4 deployed picks |

**Why now.** On 2026-10-23 the operator set the direction: go fully mechanical. The planned
order is: re-price (done), `structure_sweep` (done, `WIDE-NET-NULL`), a mechanical baseline
against random and SPY (this file), then retire the analysis. Two results point here:

- [`mechanical_benchmark` ARM M1](../../../current.md#2026-10-15--mechanical_benchmark-p1-corrected-the-contrary-survives-the-spot-fix-and-the-tier-port)
  printed `CONTRARY`: on the picks' own tickers and expiries, a mechanical ATM/+5% call spread
  beat the picks.
- [`spy_benchmark`](../../../current.md#2026-10-15--spy_benchmark-the-picks-do-not-beat-a-spy-call-spread-gross)
  printed `DOES-NOT-BEAT`: the same spread on SPY did at least as well as the picks.

Both of those are relative and gross, and both start from the picks' dates. Neither shows that the
mechanical spread makes money on its own schedule, net of cost. This study does.

## What this study is not

- **Not a `programme_gate` input.** The [gate](../../f4_deployment/programme_gate.md) still
  decides KEEP/RETIRE from `mechanical_benchmark` and `dip_buy`, and it reads `WAIT`. Retiring the
  analysis before the gate fires is an operator decision. This study supplies the replacement
  candidate; it does not amend the gate.
- **Not a geometry search.** ATM/+5% is `mechanical_benchmark`'s frozen geometry, reused so the
  two studies measure the same object. No other width or moneyness is tried.
- **Not an exit study.** Exit tuning stopped when
  [`cost_sensitivity`](../../../current.md#2026-10-09--cost-sensitivity-n1-both-tiers-vanish-and-there-was-no-gross-edge-to-lose)
  printed `VANISHES`. The shipped [§5](../../../../docs/deployment-rules.md#s5) debit exits apply.
- **Not a hedge study.** The rule is long only. The [§4](../../../../docs/deployment-rules.md#s4)
  bear sleeve and [`index_bear_hedge`](../../f5_hedging/index_bear_hedge.md) are untouched.
- **Not a ship decision.** See [What could ship](#what-could-ship).

## The rule, fixed here

Each element names the evidence it rests on. Where evidence is split, the element is a parameter
(see [Parameters printed both ways](#parameters-printed-both-ways)) and the PRIMARY value is
marked.

| Element | PRIMARY value | Evidence |
|---|---|---|
| Universe | SPY only | See [Universe](#universe) |
| Signal dates | first NYSE session of each ISO week | See [Cadence](#cadence) |
| Direction | long only (bullish) | See [Direction](#direction) |
| Structure | debit call vertical, both legs on one expiry | See [Structure](#structure) |
| Strikes | long: listed call nearest spot × 1.00; short: listed call nearest spot × 1.05 | `mechanical_benchmark` ARM M1, frozen |
| Expiry | standard monthly whose DTE from the entry day is nearest 65 | See [Expiry](#expiry) |
| Contracts | 1 per trade at the R level; sizing variants at the account level only | See [Sizing](#sizing) |
| Exits | production's effective debit profile through the frozen harness, plus its $1,000 dollar stop | See [Exits](#exits) |
| Entry | decide on signal date D's close; fill on D+1 at the closing mid | See [Pricing and costs](#pricing-and-costs) |

### Universe

SPY is the primary because it is the one underlying with direct evidence and a dense cache.

- [`spy_benchmark`](../../../study-results/f1_selection/benchmark/spy_benchmark.md): on the
  picks' dates the SPY ATM/+5% spread made more per trade than the picks, gross.
- [`ticker_class`](../../../current.md#2026-10-07--ticker_class-index-etfs-are-not-more-reliable)
  is `NULL`: no evidence that any class of underlying is more reliable. Nothing argues for
  widening the list on evidence.
- [`ticker_pattern`](../../../current.md#2026-10-23--the-market-regime-label-does-not-forecast-spy-the-ten-names-show-one-fragile-flag):
  the one flagged name (GLD) is fragile and gone on real rows. A list of the book's favourite names
  would import the picks' selection into the baseline.
- The option cache holds SPY monthly expiries from 2022-03 on, with strikes 85–125% of spot. QQQ
  is thin, and single names hold only the strikes past picks touched.

Contested: a single-ticker book concentrates the per-position cap on one name
([glossary](../../../glossary.md#per-position-cap--net-cap)). SPY, QQQ and IWM together is
printed as a parameter.

### Cadence

Weekly is the primary. No study tests cadence for a mechanical rule, so the choice rests on
construction.

- At a 65-day expiry and a 75% time exit, a daily rule holds about 30 overlapping SPY spreads.
  They are one bet counted 30 times, and the per-position cap binds on the first few.
- A weekly rule holds about six, and gives one independent-ish observation per week.
- [`emission_timing` ARM L](../../../study-results/f1_selection/signal/emission_timing.md) is
  `LAG-TOLERANT`. The entry day within a week carries no measured decay.

Contested, and printed both ways:

- **Daily.** Every session. Used also to pair against `ARM RND` and `ARM BK`, whose dates are
  not weekly.
- **Dip-gated weekly.** The weekly entry only on a [dip date](../../../glossary.md#dip-date)
  (SPY closed strictly below its 50-day SMA on D). This mirrors the
  [sizing policy of 2026-10-12](../../../../docs/deployment-rules.md#s2-sizing). Its in-sample
  support is Tier A picks on falling-market dates (+0.332, CI [+0.133, +0.522], v4,
  [regime_map](../../../current.md#2026-10-12--regime_map-tier-a-on-falling-market-dates-is-the-one-cell-both-eras-agree-on)),
  which is a pick result, not a SPY result. `dip_buy`'s forward grade is still open.

_Resolved at build (2026-10-26):_ the session calendar is the SPY close table
`backtests/mech_regime/spy_base_rate_daily.csv`, extended past its end by
`spy_vix_daily_full.csv`. A week's first session is its first date there.

_Resolved at build (2026-10-26):_ the dip flag is `dip_buy.dip_label` read on the same two
tables, `spy_base_rate_daily.csv` first. The shipped table starts on 2023-06-01,
so on its own it would leave most of `window B` unlabelled. A weekly date with no
label is not traded, and it is counted.

### Direction

Long only. No regime label decides direction.

- v4's ladder edge is the underlying's move: bull plays hit 58.7% and bear plays 42.5%
  ([2026-10-12 read](../../../current.md#2026-10-12--exploratory-read-v4-is-a-bull-tape-and-the-vetoes-are-its-only-ladder-edge)).
- Bear debits have no standalone selection edge ([§1](../../../../docs/deployment-rules.md#s1),
  [lessons](../../../lessons.md)).
- No mechanical label forecasts SPY: `market_read` and `baseline_read` print `NO-FORECAST`,
  `regime_confirm` prints `RETRO-NULL`, and `direction_hit` finds nothing at entry that predicts
  direction ([2026-10-12](../../../current.md#2026-10-12--direction_hit-nothing-known-at-entry-predicts-the-underlyings-direction)).

The cost of this choice is stated plainly: a long-only rule is a bet on drift. The 2022 window
(`window B`, below) is where it is expected to lose.

### Structure

A debit call vertical, because it is the one structure with a positive record and a mechanical
replication.

- [§7.2](../../../../docs/deployment-rules.md#s7-2): `bull_call_spread` PF 1.40 on v4;
  `bull_put_spread` PF 0.92; naked long calls have never worked.
- `mechanical_benchmark` ARM M1 is this exact geometry.
- [`structure_sweep`](../../../study-results/f3_structure/structure_sweep.md) is `WIDE-NET-NULL`:
  no other wrapper beat the proposed one on the 2026 plays.

### Expiry

The monthly nearest 65 DTE is the primary because 65 is the v4 book's median `dte_entry`. It is
the horizon at which `ARM M1` and `spy_benchmark` measured the spread, and the one at which
`ARM RND` can reuse the most legs.

- Weeklies are not used: which weeklies were listed on a past date is not known from disk
  (`mechanical_benchmark`'s own ruling for `ARM U`).
- Monthlies are the third Friday, or the Thursday before on a holiday
  (`mechanical_benchmark.monthly_expiries`).
- Contested: 45 DTE is printed as a parameter. The book's real evidence sits mostly at or below 60
  DTE ([long-dated caveat](../../../deployment-evidence.md#caveats-on-the-ladder-as-a-whole)).

_Resolved at build (2026-10-26):_ "nearest" has no DTE band, as the census assumed. The
expiry must fall after the entry day. The entry day is the session after D, so the
choice is known on D.

### Sizing

The graded unit is [R](../../../glossary.md#r) of one contract. R is size-free, so the verdicts
do not depend on the sizing rule.

Sizing matters only for the account layer, which prints with no verdict. Four variants print
side by side.

| Variant | Contracts per trade | Evidence |
|---|---|---|
| `S-1` (reference) | 1 | `mechanical_benchmark` convention |
| `S-STOP` | as many as keep the $1,000 dollar stop's loss within $1,000 | the operator's practice |
| `S-500-F2` | as many as fit $500 max loss; skip if one does not fit | [§ Sizing](../../../../docs/deployment-rules.md#s2-sizing), [`ruin_bound`](../../../current.md#2026-10-09--ruin_bound--refusing-the-unaffordable-pick-keeps-ruin-away-nothing-passes-at-1000) |
| `S-500-F3` | narrow the short strike until one contract fits $500 | [`narrow_to_fit`](../../../current.md#2026-10-07--narrow_to_fit-graded-headline-null-500-narrow-feasible), `NARROW-FEASIBLE` secondary |

The account layer runs `account_sim`'s config (reference capital, the registered 1.50 net cap
cell and 0.25 per-position cap) and prints, per variant: trades refused by the caps or the budget,
realized P&L, mark-to-market max drawdown, and the [§ Sizing](../../../../docs/deployment-rules.md#s2-sizing)
dip classes.

Disclosed now: at SPY's 2026 price, one ATM/+5% spread can cost more than $500, so `S-500-F2`
may refuse most trades. `S-500-F3` narrows the spread, which production sizing forbids ("do not
narrow the spread to fit"). It prints as research only.

_Resolved at build (2026-10-26):_ `S-STOP` is production's own contract count,
`simulate._size_contracts`: $1,000 over one contract's loss at the 75% stop,
at least one. The $1,000 dollar stop then caps the loss.

_Resolved at build (2026-10-26):_ the account layer runs `account_sim.simulate` with the
rule's own exit profile. `S-500-F3` uses `narrow_to_fit`'s narrower unchanged,
including its tier-break refusal. Every rule trade enters the walk as Tier A,
because the rule has no tier. `account_sim` books gross, so each position's
commission is subtracted after the walk.

### Exits

Production's effective debit profile, through the FROZEN harness `replay()`. This is `DEBIT_PROD`
(target 90%, stop −75%, time exit at 75% of DTE), read through `simulate._effective_sim_cfg`, so
a mech `BEAR_HE` signal date adds the regime trail as §5 says. The harness's $1,000 dollar stop
reads the trade's contract count. The path stops at `min(DTE, path_cap_days)` (120) and at the
data end (`replay_basis.bounded`).

Evidence: on 2026-09-19 every exit grid cell lost to `DEBIT_PROD`
([study map](../../../study-map.md)); `staged_exit` is `NULL`; reactive exits sell continuation
([lessons](../../../lessons.md)).

### Pricing and costs

- **Decision on D, fill on D+1.** The spot, the listed strikes, the dip flag and the mech cell
  are all read on or before signal date D. Spot is `mechanical_benchmark.UniverseSpot` (the median
  `Price~` of cached SPY calls on D). The fill is D+1's closing mid on every leg, the
  [one-clock rule](../../../current.md#2026-10-23--every-leg-of-an-entry-now-fills-at-the-same-close).
  If D+1 has no quote, the entry waits within production's five-session window.
- **Production's shared pricing functions, imported, never copied:** the entry fill, the
  junk-quote rule, the zero-bid mark and the defined-risk clamp, as `structure_sweep` imports
  them. No model price anywhere.
- **Costs.** Commission $0.65 per contract per leg per side, slippage 0, because the operator
  fills at mid ([2026-09-24](../../../current.md#2026-09-24-latest--backtest-costs--commission-only-the-operator-fills-spreads-at-the-mid)).
  R is net of commission for the primary; gross prints beside it.

Disclosed now: [§0](../../../../docs/deployment-rules.md#s0) still says entries fill at the next
session's open. The 2026-10-23 one-clock ruling is newer, and this study follows it.

### Degenerate and missing trades

- If the two strikes collide, the trade is dropped and counted.
- If a nearest listable strike is not cached and not skip-listed, the trade is `AWAITING FETCH`.
  It is never built on the next cached strike. While any primary trade awaits, no primary outcome
  prints.
- If D has no SPY spot, the week is dropped and counted.
- Every drop is printed by year.

_Resolved at build (2026-10-26):_ a QQQ or IWM date with no spot is dropped too, as for
SPY. No strike is estimated from stock bars.

_Resolved at build (2026-10-26):_ the await gate counts both windows of the primary cell,
because C4 grades it on `window B`. Nothing is priced before the gate passes, so
no outcome exists to print. While it holds, the run prints the census and stops.

_Resolved at build (2026-10-26):_ a built trade with no D+1 quote is not awaiting. It
enters within production's window, or production refuses it and it is dropped.

## Comparators

### `ARM H` — SPY held as shares

The question is whether the option wrap earns anything beyond the market's drift. The operator's
own read is that it does not.

- **Primary.** Monthly [Jensen alpha](#references). Regress `ARM X`'s monthly account return
  (`S-1`, reference capital, mark-to-market) on SPY's monthly total return. The intercept is the
  alpha. Its CI comes from a month-block bootstrap. Scaling the size scales the alpha, so its sign
  does not depend on sizing.
- **Secondary.** The trade-level version of the 2026-10-12 read: regress each trade's R on SPY's
  move over the same hold. The intercept is R at zero move. It prints with no verdict, because a
  call spread's value at zero move is mostly decay.

_Resolved at build (2026-10-26):_ the account is every built `window A` trade at one
contract, with no cap. A cap refusal would change which trades are graded. The
account layer's `S-1` keeps the caps.

_Resolved at build (2026-10-26):_ the month blocks are runs of three consecutive months.
A primary trade is open for up to about 49 days, which can touch three calendar
months. One-month blocks would treat overlapping trades as independent.

_Resolved at build (2026-10-26):_ the regression uses raw returns, as the text says, with
no risk-free rate. No dividend series is on disk, so SPY's return is the price
return of the unadjusted close. That leaves out about 0.1% a month. The alpha
moves by beta times that, and beta is small for a one-lot account.

_Resolved at build (2026-10-26):_ the account return is mark-to-market on
`mtm_curve.book_curves`, net of each position's commission at its exit. The
months run from January 2024 to the last full month with a SPY close.

### `ARM RND` — a random flow-universe ticker, same wrap

The question is whether SPY is a better underlying than a ticker drawn from the day's flow
universe. It reuses [`mechanical_benchmark` ARM U](../../f1_selection/benchmark/mechanical_benchmark.md)'s
legs and draws unchanged.

- A pair exists only where an `ARM U` slot and an `ARM X` daily-cadence trade share the signal
  date, the entry day, and the monthly expiry. No other pairing is made, and no `ARM U` leg is
  re-chosen.
- The comparison runs on `ARM U`'s basis, so its legs are reused as priced: gross, `DEBIT_PROD`
  on both sides, 1 contract. `ARM X` is re-run on that basis for these pairs.
- The paired figure is `ARM X`'s R minus the slot's expected R over its priceable universe
  (`ARM U`'s `R_C`). The p95 of the 1,000 seeded draws prints beside it.
- `ARM RND` is graded only once `mechanical_benchmark`'s floors 3 and 4b pass. Until then it
  prints `NOT BUILT — AWAITING SCRAPE`.

_Resolved at build (2026-10-26):_ the entry day is matched on `ARM X`'s recorded fill
day. The census, which prices nothing, matches on the planned day, the session
after D. A pair's `ARM X` figure is the mean of its universe's matching trades.

_Resolved at build (2026-10-26):_ a parameter cell's `ARM RND` and `ARM BK` pair on the
daily trades of that cell's universe and target DTE. Cells that differ only in
cadence therefore print the same two pairings.

### `ARM BK` — the v4 book

The question is whether the rule beats the book it would replace.

- **Population.** `load_book()` at its defaults, era v4, seal applied: the deployed top-3 Tier A
  and B picks (`protocol.ladder_eligible`), real and tweak rows, net R as stored.
- **Pairing.** On every book signal date, the book's mean R is paired with `ARM X`'s
  daily-cadence trade on that date. A date where `ARM X` cannot be built leaves the comparison,
  and the drop is counted.
- **Era v3** prints as the replication, on the frozen `v3_` exports, the same way.

The book is net and recent; `ARM X` uses the same cost model, so the pair is like for like.

_Resolved at build (2026-10-26):_ a book date whose `ARM X` trade awaits a fetch is not a
drop. While any does, `ARM BK` prints `NOT BUILT — AWAITING SCRAPE`. The v3
replication pairs on its own book dates, with no window cut.

## Population and windows

| Window | Signal dates | Role |
|---|---|---|
| `window A` | 2024-01-10 → 2026-09-22 | PRIMARY. The v4 book's span, cut before the seal |
| `window B` | 2022-03-01 → 2024-01-09 | Replication. It holds the 2022 bear market |
| forward | 2026-10-27 → | Forward grade, see [The forward read](#the-forward-read) |

- **The seal.** [`holdout_seal`](../../f4_deployment/holdout_seal.md) withholds every signal date
  from 2026-09-23. This study is not a named reader. `window A` stops before the seal, and
  `ARM BK` reads book rows only through the loader's seal.
- **Window B is not an era.** The rule reads no analysis row, so prompt eras do not apply to
  `ARM X`. They apply only to `ARM BK`.
- The SPY cache is the only input `ARM X` needs, plus `backtests/mech_regime/` for the dip flag
  and mech cell.

## Criteria

All CIs are [date-clustered bootstrap CI95s](../../../glossary.md#ci95-date-clustered-bootstrap),
10,000 draws, seeded. For `ARM X` alone, a "date" is one weekly signal date.

1. **C0 POWER.** `ARM X` needs at least 40 built trades in `window A`. A paired comparison needs
   at least 25 dates and 40 pairs. `ARM H` needs at least 24 months. Below a floor the object
   prints `UNDERPOWERED`, census only. No floor may be lowered.
2. **C1 SIGN.** The mean (net R for `ARM X`; the paired gain for a comparator; alpha for `ARM H`)
   has a CI95 excluding zero.
3. **C2 [LOO](../../../glossary.md#loo--leave-one-date-out).** Every leave-one-date-out fold has
   the same sign as the full-sample mean. For `ARM H` the fold is a month.
4. **C3 STRESS WINDOWS.** The mean keeps its sign with the Mar–Apr 2025 and the Feb–Apr 2026
   sell-offs each removed ([window-dominance re-cuts](../../../glossary.md#window-dominance-re-cuts)).

   _Resolved at build (2026-10-26):_ for a negative mean, C2 needs every fold
   negative.
5. **C4 WINDOW B.** For `ARM X` vs zero only: `window B`'s mean net R is not negative with a CI95
   excluding zero.

   _Resolved at build (2026-10-26):_ C4 fails only when `window B`'s CI95 lies wholly
   below zero.
6. **C5 OVERFITTING.** [PBO by CSCV](#references) (`lib/pbo.py`, S = 16) across the twelve
   trade-level cells in [Parameters printed both ways](#parameters-printed-both-ways). It prints
   for every run. The primary was chosen before any cell was seen, so PBO does not grade it. A PBO
   of 0.5 or more forbids promoting any non-primary cell in a later registration.

   _Resolved at build (2026-10-26):_ the rows are the ISO weeks of `window A`. Each
   cell's metric is its mean net R per trade, and a week it did not trade is
   empty. The head is padded with empty weeks so 16 blocks divide it.

## Verdicts, worded now

One token per comparison, then one study-level token.

| Object | Token | When |
|---|---|---|
| `ARM X` vs zero | `PROFITABLE` | C0–C4 hold, mean positive |
| | `LOSES` | C1 holds with the mean negative |
| | `NULL` | powered, C1 fails |
| `ARM H` | `ALPHA` | C0–C3 hold, alpha positive |
| | `DRIFT-ONLY` | powered, C1 fails |
| | `NEGATIVE-ALPHA` | C1 holds with alpha negative |
| `ARM RND` | `SPY-BEATS-RANDOM` | C0–C3 hold, gain positive |
| | `NULL` | powered, C1 fails |
| | `RANDOM-BEATS-SPY` | C1 holds with the gain negative |
| `ARM BK` | `BEATS-BOOK` | C0–C3 hold, gain positive |
| | `NULL` | powered, C1 fails |
| | `TRAILS-BOOK` | C1 holds with the gain negative |

Any object may also print `UNDERPOWERED`, `NOT BUILT — AWAITING SCRAPE`, or `UNWORDED` (criteria
met listed) when C1 holds but a later criterion fails.

| Study-level token | When | What it means |
|---|---|---|
| `REPLACEMENT-CANDIDATE` | `ARM X` is `PROFITABLE` and `ARM BK` is not `TRAILS-BOOK` | The rule earns its keep and is no worse than the book. It earns a forward read |
| `DRIFT-REPLACEMENT` | as above, and `ARM H` is `DRIFT-ONLY` | The same, with the plain caveat that it is a defined-risk way to own SPY's drift |
| `NO-REPLACEMENT` | `ARM X` is `NULL` or `LOSES` | The rule does not make money. Retiring the analysis then rests on the book's own record, not on a replacement |
| `BOOK-BETTER` | `ARM BK` is `TRAILS-BOOK` | The book beats the rule. Surfaced to the operator before the analysis is retired |

`BOOK-BETTER` takes precedence, because it argues against the planned retirement. `ARM RND` does
not enter the study-level token; it is graded later and answers a narrower question about SPY.

_Resolved at build (2026-10-26):_ the study-level token is withheld while `ARM BK` is
`NOT BUILT — AWAITING SCRAPE`. `BOOK-BETTER` and "not `TRAILS-BOOK`" both need
it read. When `ARM X` is `UNDERPOWERED` or `UNWORDED`, no study-level token
prints.

## Parameters printed both ways

Every cell prints the four comparisons, with no verdict except the primary. Twelve trade-level
cells feed C5.

| Parameter | PRIMARY | Alternatives |
|---|---|---|
| Universe | SPY | SPY, QQQ and IWM, one spread each per signal date |
| Cadence | weekly | daily; dip-gated weekly |
| Target DTE | 65 | 45 |
| Basis | net of commission | gross |
| C4 rule | not significantly negative | same sign as `window A` |
| Account sizing | `S-1` | `S-STOP`, `S-500-F2`, `S-500-F3` |

Universe × cadence × target DTE gives the twelve cells. Basis, the C4 rule and sizing change how a
cell is reported, not which trades it holds, so they are not counted.

## The forward read

The forward read is the grade of record for anything that would trade.

- **Dates.** Weekly signal dates from 2026-10-27, the first NYSE session after acceptance.
- **Statistic.** `ARM X`'s mean net R, graded continuously with a
  [confidence sequence](../../../glossary.md#confidence-sequence), as `F2`'s draft does.
- **Floor.** 30 forward dates with a closed trade (about seven months).
- **Tokens.** `STILL-OPEN` below the floor or while the sequence spans zero; `FORWARD-HOLDS` when
  it clears zero above; `FORWARD-FAILS` when it clears zero below.
- Forward trades are priced from the cache like any other. Paper or live is an operator decision.

_Resolved at build (2026-10-26):_ the forward dates fall inside the
[holdout seal](../../f4_deployment/holdout_seal.md), and this study is not a
named reader. No forward date is read until the seal is lifted. Until then the
read prints `STILL-OPEN`.

_Resolved at build (2026-10-26):_ the sequence uses `refuse_floor_forward`'s constants,
imported: alpha 0.0125 and t* 150. It enters the running intersection at the
30th date. A closed trade is one that exited before the data end.

## Dependencies and the fetch

**No study code fetches.** A missing leg is fetched by an operator-run collector,
`scripts/collector/study_legs/fetch_mechanical_baseline_legs.py`, built like
`fetch_mechanical_legs.py`: it imports this study's fetch plan and goes through the backtest's
loop. The option cache is pushed to Drive after it.

It does not run while `mechanical_benchmark`'s `ARM U` loop runs. That loop writes into the same
cache, and two writers is how duplicates were made before.

_Resolved at build (2026-10-26):_ a real fetch refuses to start while another cache
writer runs: a backtest, the journal, or any `fetch_*_legs.py` collector. The
check is the `pgrep` pattern `scripts/daily_loop.sh` uses. `--dry-run` writes
nothing and is not refused.

### Plan-time census, disclosed

Counted 2026-10-26 from the cache index, offline, while the `ARM U` loop was running. Counts
only; no outcome was read.

**The primary cell is nearly buildable now.** SPY, weekly, 65 DTE:

| Window | Signal dates | Built | Awaiting a fetch | No spot | Contracts to fetch |
|---|---|---|---|---|---|
| `window A` | 141 | 116 | 24 | 1 | 33 |
| `window B` | 97 | 90 | 7 | 0 | 9 |

**The parameter cells need more.** Distinct contracts to fetch, summed over both windows and both
target DTEs. Daily dates contain the weekly ones, so the daily figure bounds both cadences.

| Ticker | Daily-cadence fetch | Note |
|---|---|---|
| SPY | 302 | |
| QQQ | 1,442 | a floor: 99 QQQ dates in `window B` have no cached spot, so their strikes are unknown |
| IWM | 1,041 | |
| `S-500-F3` narrowing strikes (weekly, 45 DTE, `window A`) | SPY 3, IWM 199 | |

- In total about 3,000 contracts, a few hours at the `ARM U` loop's rate of about 430 an hour.
  The primary alone is 42.
- Four built trades have no D+1 bid or ask in their cached file. They need two existing files
  re-fetched each.

**`ARM RND` overlap** with `mechanical_benchmark`'s v4 `ARM U` slots (430 usable slots on 208
dates, seal applied):

| `ARM X` cadence, target DTE | Slot dates sharing the rule's date and expiry | Universe wraps on those dates | Already built |
|---|---|---|---|
| daily, 65 | 147 | 23,624 | 3,433 |
| daily, 45 | 92 | 14,715 | 2,345 |
| weekly, 65 | 38 | 6,178 | 939 |

`ARM RND` therefore pairs on the daily cadence: the weekly overlap of 38 dates falls short of the
C0 floor's spirit once drops are counted. About 15% of the shared wraps are built today. The rest
are in the running `ARM U` loop's plan, so `ARM RND` needs no fetch of its own.

The script is the session scratchpad's `count_rule.py`, not in the repo. Its assumptions: expiry
nearest the target with no DTE band limit; "built" means both legs cached with a bid and ask on
D+1.

## Anti-tuning

- The rule in [The rule, fixed here](#the-rule-fixed-here) may not change after any number is
  seen. A losing rule is the result.
- No alternative cell may be promoted to primary in this file. A cell that looks better earns
  its own registration, gated by C5.
- The universe may not be narrowed to tickers that priced well, and `ARM RND` may not re-draw.
- `window B` may not be dropped or shortened because 2022 was a bear market. That is why it is
  there.
- `ARM X` may not be quoted without its drop census beside it.

## What could ship

Nothing ships from the retrospective.

- `REPLACEMENT-CANDIDATE` or `DRIFT-REPLACEMENT` earns the forward read. A `FORWARD-HOLDS` grade
  is the evidence a live-money change would rest on. The change itself still needs the operator's
  explicit decision, and a new section of `docs/deployment-rules.md`.
- `NO-REPLACEMENT` and `BOOK-BETTER` are written into
  [`deployment-evidence.md`](../../../deployment-evidence.md) and go to the operator before the
  analysis is retired.

## References

| Paper | Use here |
|---|---|
| Jensen (1968), "The performance of mutual funds in the period 1945–1964", _Journal of Finance_ 23(2) | `ARM H`: alpha as the intercept of returns regressed on the market |
| Bailey, Borwein, López de Prado & Zhu (2017), "The probability of backtest overfitting", _Journal of Computational Finance_ 20(4) | C5: PBO by CSCV across the twelve cells |
| Künsch (1989), "The jackknife and the bootstrap for general stationary observations", _Annals of Statistics_ 17(3) | `ARM H`: the block bootstrap over months |
