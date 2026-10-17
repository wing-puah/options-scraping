## mechanical_benchmark — do the picks beat a mechanical bull call spread on the same dates?

<!-- outcome:start -->
> Latest outcome: `SAME-TICKER READ — ARM U NOT BUILT`. `mechanical_benchmark ARM M1` meets `CONTRARY`; `ARM M2` does not. C1 and C2 fail on both. `ARM U` is not built, so no study-level verdict prints. v3 is not graded: its pairs await a fetch — 2026-10-15 · [record](../../../study-results/f1_selection/benchmark/mechanical_benchmark.md).
<!-- outcome:end -->

_Registered 2026-10-09._

**STATUS: ACCEPTED BY DEFAULT 2026-10-09 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Every open decision of the draft is answered
beside the text it amends, tagged _Resolved at build (2026-10-09):_. Every default
was fixed before any outcome column was read.

## The question

Is the book selection, or is it a long call spread in a rising market?

Nothing in the repo has ever separated the two
([robustness review, short answer](../../../robustness-review.md#short-answer),
point 3). Every recorded edge is measured against the book's own variants:
another exit, another sizing rule, another ordering. No study has compared a
pick with what a mechanic with no model would have done on the same day.

Three sub-questions are answered separately, because they can disagree.

| Sub-question | What it isolates | Arm |
|---|---|---|
| Does the pick beat a fixed-geometry call vertical on the SAME ticker and date? | structure, strike and expiry choice | `ARM M1` |
| Does the pick beat a delta-and-DTE matched call vertical on the SAME ticker and date? | everything except geometry | `ARM M2` |
| Does the pick beat the same wrap on a RANDOM ticker from that day's flow universe? | ticker selection, the base-rate question | `ARM U` |

`ARM U` answers "long calls just worked". `ARM M1` and `ARM M2` answer "the
model wrapped the trade better than a rule would have".

`ml_combination`'s benchmark is the ladder itself, so it cannot answer this
([§7.2](../../../../docs/deployment-rules.md#s7-2)). The ladder's in-sample
circularity is called "mitigated, not eliminated" in
[`deployment-evidence.md`](../../../deployment-evidence.md#why-the-tiers). A
same-date mechanical benchmark is the missing external comparator.

## What this study is not

- **Not an exit study.** Both sides replay through the FROZEN harness
  (`scripts/backtest_study/lib/harness.py`) under the shipped debit-vertical
  exit profile ([§5](../../../../docs/deployment-rules.md#s5)) and the same
  [path cap](../../../glossary.md#path-cap). The comparison is exit-neutral by
  construction.

  _Resolved at build (2026-10-09):_ the headline replays BOTH sides under
  `DEBIT_PROD` (pt 0.90, sl 0.75, time exit 0.75), the debit row of §5, as G3
  asks. That puts the credit picks (`bull_put_spread`, Tier B) under a debit
  profile too.
  - A declared secondary replays each side under its own §5 row:
    `CREDIT_PROD` for a credit pick, the trail row on a mech `BEAR_HE` date,
    else `DEBIT_PROD`. It prints beside the headline and carries no verdict.
  - Both sides are cut at their data end (`replay_basis.bounded`).
  - The pick replays at its own contract count, as the book holds it. The
    counterpart replays at 1 lot, as the geometry table says. Only the
    harness's $1,000 dollar stop reads the count.
- **Not a proposal to trade the mechanical wrap.** No outcome ships a
  mechanical rule. A mechanical wrap that wins is a finding about the picks,
  not a new strategy.
- **Not a geometry search.** The geometry is frozen below. If ATM/+5% loses to
  ATM/+10%, that is not this study's business and may not be looked at.
- **Not a cost study.** It compares two books priced the same way. Costs are
  [`cost_sensitivity`](../../f2_management/cost_sensitivity.md)'s question. If
  that study lands first, this one inherits its cost model unchanged. If not,
  both books are gross and the report says so on every table.

  _Resolved at build (2026-10-09):_ `cost_sensitivity` is still a draft, so
  both books are gross. The harness replays the stored marks, which are pre-cost.
- **Not a claim about the operator's read.** What the operator actually traded
  is [next-steps §2.5](../../../next-steps.md#s2-5)'s `operator_read`, which needs
  the journal.

## Definitions

### Matched geometry

["Matched geometry"](../../../glossary.md#matched-geometry) decides this study,
so it is pinned here in full. A mechanical counterpart is a two-leg debit call
vertical:

- long the lower strike, short the higher strike;
- both legs on the SAME expiry, on the same underlying;
- entered on the same signal date;
- held under the same exit profile and path cap.

The two arms differ only in how the strikes and expiry are chosen.

| Element | `ARM M1` — fixed geometry (PRIMARY) | `ARM M2` — matched geometry (SECONDARY) |
|---|---|---|
| expiry | the listed expiry whose DTE at the signal date is nearest the pick's `dte_entry`, and inside the same DTE band | same rule |
| DTE bands | `[7,21) [21,45) [45,90) [90,180)` — a counterpart outside the pick's own band is NOT a match and the pair is dropped | same bands |
| long strike | the listed strike nearest `entry_underlying × 1.00` | the listed strike whose entry-dated delta is nearest the pick's `delta` |
| short strike | the listed strike nearest `entry_underlying × 1.05` | the listed strike 5% above the long strike, rounded to the nearest listed strike |
| contracts | 1 | 1 |

_Resolved at build (2026-10-09):_ the expiry rule counts both DTEs from the
same day, the pick's recorded entry day. `dte_entry` is counted from that day,
not the signal date. So the pick's own expiry is always the nearest (distance
0), and M1 and M2 use the pick's own expiry. Counting both from the signal date
would pick a daily expiry one or two days earlier on SPY and QQQ, which the
rule never meant.

_Resolved at build (2026-10-09):_ "the pick's `delta`" has two honest meanings,
so both print.

| Arm | Delta target | Role |
|---|---|---|
| `ARM M2` | the pick's net position delta (the `delta` column's quantity), absolute | SECONDARY, as registered |
| `ARM M2L` | the pick's bought leg's delta, absolute | declared secondary; no verdict |

Both targets and every candidate delta are read on the signal date. The
candidate is a call. Its delta is compared with the target's absolute value,
so a call of that size matches a put pick's target.

### Build rules for both arms

1. **Strikes and expiry are chosen from entry-dated information only:** the
   listed chain, the underlying close and the entry-dated delta. Nothing dated
   after the signal date may enter the choice (gate G2).

   _Resolved at build (2026-10-09):_ "entry-dated" and "nothing after the
   signal date" disagree, because the entry fills at the next session's open.
   The stricter one holds. Every input to the choice is dated on or before the
   signal date:

   - the underlying is the median `Price~` of the pick's own legs on the signal
     date, else of the ticker's other cached contracts that day;
   - a strike is listed when its cached history has a row on or before the
     signal date;
   - a delta is the strike's `Delta` on the signal date.

   The fill is on the pick's recorded entry day
   (`bear_rewrap.recorded_entry_date`), so both sides of a pair enter on the
   same session. G2 re-runs every choice on a cache cut at the signal date. Any
   difference fails the run.

   _Resolved at build (2026-10-15):_ a code bug in the second spot source is
   fixed; the rule is unchanged. `UniverseSpot` stopped after 20 probes from
   the pick's own expiry, so an expiry not yet listed dropped the pick as
   `no_spot_at_signal` (on SPY 2025-03-03, 654 cached contracts carried `Price~`
   583.77). The walk keeps its order and runs until five calls are priced or
   none are left. A spot the old walk read off five contracts is unchanged,
   and G2 still passes.
2. **No degenerate pair.** If the two chosen strikes collide, or the width is
   zero, the pair is dropped and counted, never silently widened.
3. **A dropped pair is dropped on BOTH sides.** Every comparison is paired. If
   a pick's counterpart cannot be built, the pick leaves the comparison
   entirely. Its exclusion is reported by tier and DTE band (`ARM CEN`).

_Resolved at build (2026-10-09):_ the full listed chain is not on disk. The
study treats as listed every cached strike, plus every multiple of the finer of
the cached spacing and the standard listing step.

- If a pair's nearest such strike is not cached, and the skip-list holds no
  evidence against it, the pair is AWAITING FETCH. It is neither built on the
  next strike nor dropped.
- While any pair awaits, no outcome prints. The cached strikes are the ones the
  book traded, so the cached subset is not the registered population.
- If a fetch returns 404, the strike goes on the skip-list and the walk steps
  past it.

_Resolved at build (2026-10-13):_ the `ARM M2` and `ARM M2L` walks now ask for
different strikes first. This changes the fetch order only. What makes a pair
built, dropped or awaiting, and which strike is chosen, is unchanged. It was
made mid-fetch, for cost, before any `ARM M1` or `ARM M2` outcome printed.

- An awaiting delta walk asks first for the strikes nearest an estimated
  target strike (interpolated between known deltas, else Black-Scholes from
  the nearest strike's delta and IV). Inside a bracket it asks for every open
  strike at once.
- An awaiting short leg asks for its next few open strikes in walk order, up to
  the first on the standard listing grid.
- Old and new code built identical pairs (status, reason, both strikes) on one
  cache, per era and arm, including `ARM U`.
  `test_fetch_order_cannot_change_a_build` pins this on a synthetic chain.
- The walk still steps at the finest cached spacing. A strike off the standard
  grid inside the final bracket must still be fetched or skip-listed before the
  pair builds.

`h ≥ 180` is out of scope. It is unpriceable with real data, and the BS proxy
tier is OFF ([next-steps §2.7](../../../next-steps.md#s2-7)).

### The universe

`ARM U` draws from the day's flow universe: every ticker appearing in that
signal date's compiled flow CSV, mirrored locally as
`backtests/analysis_inputs_cache/<date>-rollup.csv`. It is section-tagged, so
ETFs and stocks can be reported separately.

- Draws are per date, matched on count to that date's deployed pick count.
- There are at least 1,000 draws, date-clustered, seeded and recorded.
- A drawn ticker with no priceable counterpart is redrawn, and the redraw rate
  is reported. If the redraw rate on a date is above 25%, that date's draw is
  UNUSABLE, because the surviving draws are then a liquidity subset rather than
  the universe.
- **The redraw cap and census floor 3 are one number seen from two sides, and
  move together or not at all.** A date whose priceable share is `p` has an
  expected redraw rate of `1 − p`. So a 25% redraw cap requires a priceable
  share of at least 75%, which floor 3 demands. A floor below `1 − cap` would
  pass dates whose draws are UNUSABLE by construction. Changing either number
  without the other is a registration change, not an implementation detail.
- The ticker's own flow score plays no part in the draw. Using it would put
  selection back into the benchmark.

_Resolved at build (2026-10-09):_ how `ARM U` runs.

- **Source.** The universe is `audit/<date>-rollup.csv`, the copy the analysis
  fetch writes, with `backtests/analysis_inputs_cache/` as the fallback. The
  mirror named above stops at 2026-04-07, and v4 dates need the audit copy.
  `Section` (`etfs`, `stocks`) is the tag.
- **Expiry.** A random ticker gets the standard monthly expiry (third Friday,
  the Thursday before on a holiday) whose DTE from the entry day is nearest the
  pick's, inside the pick's band. Weeklies are not used, because which weeklies
  a name lists is not known from disk.
- **Underlying.** The median `Price~` of the ticker's cached contracts on the
  signal date. Stock bars are used only to plan a fetch, never to choose or
  price.
- **The draw.** Redrawing until priceable samples uniformly from the priceable
  universe. So the paired comparison uses each slot's mean over its priceable
  universe, and the 1,000 seeded draws give the band. The redraw rate is
  `1 − priceable share`, per date and expiry, against the 25% cap.

## Dependencies

The study is NOT built until a census has been run and read. The mechanical
legs are contracts the backtest never needed, so most of them are not in
`backtests/option_history_cache/`. Registering the plan before the data exists
is the point.

_Resolved at build (2026-10-09):_ the census is the study module's first
stage, not a separate script. It prints counts only. The module stops there
unless every floor passes and nothing awaits a fetch.

Plan-time state of the cache (2026-10-09): the census does not pass. The M1
legs are a few hundred contracts away. `ARM U` needs tens of thousands, plus
stock bars for most of the flow universe.

### What must exist in `option_history_cache`

For each matched pair, both mechanical legs need a per-contract CSV
(`<TICKER>_<YYYYMMDD>_<STRIKE><C|P>.csv`) with:

- a real quote on the signal date, so the entry is not carried forward into
  existence;
- rows covering the signal date through the path cap, or through the exit,
  whichever comes first;
- `Bid`, `Ask`, `Latest` and `Delta` populated on the entry row, since
  `ARM M2` selects on entry-dated delta.

### Census floors

**What the census must show, before any module is written.** All five,
printed and read by the operator.

| # | The census must report | Floor for building the study |
|---|---|---|
| 1 | Dates with at least 5 priceable matched pairs | ≥ 25 dates |
| 2 | Share of deployed picks whose counterpart is unbuildable, split by tier | no tier more than 10 points from another |
| 3 | Share of universe tickers per date that are priceable, for `ARM U` | median ≥ 75% of that date's universe (`floor = 1 − cap`) |
| 4 | Contracts that must be fetched to reach floors 1–3, as a count and as an estimated scrape volume | named, and approved by the operator before any fetch |
| 5 | Share of pairs falling in each DTE band | printed; no floor, but a band with fewer than 10 pairs is not read |

_Resolved at build (2026-10-09):_ four floors needed a ruling.

| Floor | Problem | Ruling |
|---|---|---|
| 1 | Top-3 per day caps a date at 3 pairs, so "≥ 5 pairs" can never pass | Headline: dates with at least 1 priced M1 pair. Two declared secondary lines print beside it |
| 2 | Picks out of scope (DTE ≥ 180 or < 7) are dropped for every tier alike | Floor 2 counts in-scope picks only, and ignores pairs still awaiting a fetch |
| 3 | A date can carry up to three expiries | A date's share is its lowest across its expiries |
| 4 | Under the default policy no one approves a fetch | The count prints and the run stops at `NOT BUILT — AWAITING SCRAPE` |

The two floor-1 secondary lines are dates whose every deployed pick is paired,
and dates with at least 5 pairs. The second is always 0.

Each floor prints two values: what the cache gives now, and the most a full
fetch could give. A floor that fails even at that upper value is a definitive
`NOT BUILT`.

_Resolved at build (2026-10-13):_ the floors are split by arm, so the
same-ticker arms can be read without `ARM U`. The operator chose this after
[`programme_gate`](../../f4_deployment/programme_gate.md) was registered and
before any `ARM M1` or `ARM M2` outcome was printed. It lets that gate's P1
read go ahead while `ARM U` is unbuilt.

| Floor | Gates |
|---|---|
| 1, 2 | every arm; a floor-2 FAIL still kills the whole study |
| 4a — no `ARM M1` or `ARM M2` pair awaits a fetch | the same-ticker arms `ARM M1`, `ARM M2`, `ARM M2L` |
| 3, and 4b — no contract left to fetch for any arm | `ARM U`, the criteria graded on it (C3, C4, C5) and the study-level verdict |
| 5 | nothing; printed only |

- Floor 4 is two lines. 4a counts only the `ARM M1` and `ARM M2` pairs still
  awaiting a fetch. 4b is the old floor 4.
- `ARM M2L` is graded only once none of its own pairs awaits a fetch. Until
  then it prints "not graded".
- C0–C2 and the `CONTRARY` condition are unchanged for the same-ticker arms.
  The C0 power floor is not lowered.
- An era is graded only on its own floors. If a v3 run's same-ticker pairs
  still await a fetch, it prints no v3 outcome.
- The census prints which arms each floor gates, on the floor's own line.
- If floors 1, 2 and 4a pass but 3 or 4b do not, the run prints the per-arm
  grades and the verdict `SAME-TICKER READ — ARM U NOT BUILT`. While floor 4a
  still awaits, the run prints `NOT BUILT — AWAITING SCRAPE`.

Floor 2 can kill the study rather than delay it. If the unbuildable share is
tier-dependent, the benchmark is liquidity-selected and the comparison is
confounded. In that case the census IS the result, it is recorded as such, and
it feeds the join-attrition question
([robustness review N6](../../../robustness-review.md#beyond)) instead.

### Fetching

**No study code fetches.** Any backfill runs through
`scripts/collector/fetch_counterpart_history.py` as a separate, operator-run
step, and the option cache is pushed to Drive afterwards.

_Resolved at build (2026-10-09):_ that collector fetches the other leg of a
book row, a different target set. The backfill runs through a new collector,
`scripts/collector/fetch_mechanical_legs.py`. It imports the study's own fetch
plan and fetches through the backtest's loop, as `fetch_substitute_legs.py`
does. It is still operator-run, and the cache is still pushed afterwards.

## Population and basis, fixed here

- **Population.** `lib/book.py::load_book()`, era-scoped by `lib/era.py`,
  `include_bs=False`. Real and `strike_expiry_tweak` rows only.
- **Era.** Current era (v4) PRIMARY; v3 run as the era-stability read.
- **The date count is NOT fixed here.** It is stated by rule: every
  era-resolved signal date carrying at least one deployed pick with a priceable
  counterpart. No count is written into this file or into the module.
- **Deployed set.** `protocol.top_k_per_day(book, ladder_rank, k=3,
  ladder_eligible)`. This study never re-selects and never re-tiers.
  `ladder_eligible` is `tier in ("A", "B")`, so Tier C and VETO rows are not in
  this study at all (see C4).
- **Sealed dates are excluded, by rule.** Every signal date inside the window
  sealed by [`holdout_seal`](../../f4_deployment/holdout_seal.md) is dropped
  from every arm, from both sides of every pair, and from every census count
  that feeds an outcome figure, for as long as that seal stands. The seal
  forbids paired meanR gains and PF on a sealed date. The exclusion tracks the
  seal rather than a date list. If the operator
  declines `holdout_seal`, this clause is inert and the population is the whole
  era.

  _Resolved at build (2026-10-09):_ `holdout_seal` was accepted on 2026-10-09
  with its first sealed date at 2026-09-23. This study is not a named reader,
  so every signal date from 2026-09-23 is withheld from every arm, and `ARM U`
  never reads a sealed date. The module loads the book through `load_book()`
  and applies `era.drop_sealed` again; it opens no export itself.
- **Pairing.** By date, using `protocol.boot_ci_paired_by_date`. Never pooled
  across dates unpaired.
- **Direction.** The mechanical wrap is a bull call vertical in every arm, on
  every pick, including bear picks. That is deliberate: the benchmark is "what
  a mechanic who only buys call spreads would have made". The bear subset is
  also reported on its own.

  _Resolved at build (2026-10-09):_ the ladder deploys no bear structure, so
  "bear picks" are the deployed rows whose model regime reads BEAR.

## What it compares

| Arm | What it is | Role |
|---|---|---|
| `ARM T` — THE PICKS | The deployed book as it stands, replayed unchanged | reference only; no verdict of its own |
| `ARM M1` — FIXED-GEOMETRY COUNTERPART | Same ticker, same date, ATM/+5% call vertical in the pick's DTE band | PRIMARY |
| `ARM M2` — MATCHED-GEOMETRY COUNTERPART | Same ticker, same date, delta-and-DTE matched call vertical | SECONDARY |
| `ARM M2L` | As `ARM M2`, targeting the pick's bought-leg delta (see Definitions) | declared secondary; no verdict |
| `ARM U` — UNIVERSE NULL | The `ARM M1` wrap on random flow-universe tickers, at least 1,000 date-clustered draws, reported as a [p5, p95] band | PRIMARY for selection |
| `ARM CEN` — CENSUS | Pair-build rates, redraw rates and band coverage by tier, structure and DTE band | DESCRIPTIVE ONLY; never a criterion |

If a pick set sits inside the `ARM U` band, it has not beaten the base rate,
whatever its own CI says.

## How it is judged

- **Unit.** A matched pair: one deployed pick and its counterpart, on the same
  date and ticker.
- **Metric.** [R](../../../glossary.md#r) under the shipped exit profile.
  [E](../../../glossary.md#e) is reported beside it and is never a criterion.
- **Headline per arm.** Paired within-date mean gain in R (`ARM T` minus the
  counterpart), with a 95% date-clustered CI, plus
  [PF](../../../glossary.md#pf) on both sides via `protocol.pf_paired_by_date`.
  PF is never quoted without meanR.

## Gates

Each gate exits non-zero on failure.

- **G1 ERA IDENTITY.** The header names the era and export fingerprint. A
  wrong or thin era refuses (`lib/era.py`).
- **G2 NO LOOK-AHEAD.** Every counterpart's strikes and expiry are recomputed
  from entry-dated information only, and verified against an independent
  recomputation. If a counterpart's selection reads a field dated after its
  signal date, the run FAILS.
- **G3 EXIT PARITY.** Both sides replay through the same frozen harness call
  under the same profile and path cap. If the two sides used different exit
  configs, the run FAILS.
- **G4 PAIRING INTEGRITY.** Every reported comparison is paired on (date,
  ticker). The pair counts on both sides are equal, and dropped pairs sum
  exactly to the census. A mismatch FAILS.
- **G5 PRICING-TIER HONESTY.** Real and tweak only; `bs_options_hist` is
  excluded on both sides. No dollar figure pools tiers.
- **G6 NO NEW STATISTIC.** No annualised figure, no Sharpe, no
  time-to-recover.
- **G7 NO HARDCODED CENSUS.** Every count, share and range printed in prose is
  computed from the run.

## Bar for a candidate

A selection claim needs all of C1–C5. C1–C3 are the registered pass rule from
[robustness review N2](../../../robustness-review.md#beyond).

0. **C0 POWER FLOOR.** An arm is read only if it has at least 25 dates and at
   least 40 matched pairs. Below either, it prints **UNDERPOWERED**: census
   only, no outcome number printed. The floor may not be lowered.
1. **C1 GAIN.** The paired within-date mean R gain over the counterpart has a
   95% date-clustered CI excluding zero.
2. **C2 LEAVE-ONE-DATE-OUT.** Every [LOO](../../../glossary.md#loo) fold is
   positive. Not "most". Every one.
3. **C3 BEATS THE BASE RATE.** The gain over `ARM U` exceeds `ARM U`'s p95
   band.

   _Resolved at build (2026-10-09):_ C3 passes when the picks' mean R, over the
   slots `ARM U` covers, is above the p95 of the random book's mean R across
   the 1,000 draws.
4. **C4 TIER COHERENCE.** Tier A's gain is not smaller than Tier B's. The
   comparison is A-versus-B, never A-versus-C. The deployed set is
   `ladder_eligible` (`protocol.ladder_eligible`), so no Tier C row is ever in
   this population and no Tier C gain may be computed for this criterion. If
   the top tier beats the mechanic by less than the second tier does, that is
   evidence against the ladder, and is reported as such rather than averaged
   away.

   _Resolved at build (2026-10-09):_ C4 is graded on `ARM U`, the arm that
   carries the selection claim. It prints for every arm.
5. **C5 ERA STABILITY.** C1 holds on both eras with the same sign.

   _Resolved at build (2026-10-09):_ C5 is graded on `ARM U`. The v3 era runs
   in the same process.

## Verdicts, worded now

`CONTRARY` takes precedence over the other powered verdicts, since it must
reach the operator first. The verdicts as registered:

| Token | When | What it means |
|---|---|---|
| `SELECTION-CONFIRMED` | `ARM U` clears C0–C3, and C4 and C5 both hold (the "all of C1–C5" bar) | The picks beat a mechanical wrap on a random universe ticker. The strongest outcome available; it still ships nothing on its own |
| `STRUCTURE-ONLY` | `ARM M1` or `ARM M2` clears C0–C2, but `ARM U` does not | The model wraps a trade better than a fixed rule, but its ticker choice is not distinguishable from the day's universe. Recorded plainly, including in [`deployment-evidence.md`](../../../deployment-evidence.md), because it narrows what every shipped rule can claim |
| `BASE-RATE` | `ARM U` clears, but `ARM M1` and `ARM M2` do not | The value is in which name is picked, not in how it is wrapped |
| `NULL` | Powered, and no arm clears C1 | The picks are not distinguishable from the mechanical wrap. Exit and sizing tuning stop being the priority; the selection question becomes the programme ([suggested order](../../../robustness-review.md#order), step 2) |
| `CONTRARY` | An arm's paired gain is negative with a CI excluding zero | The mechanical wrap beats the picks. Surfaced to the operator before any further study runs |
| `UNDERPOWERED` | No arm clears C0 | Census printed, nothing concluded |
| `NOT BUILT` | The pre-build census fails its floors | The census is the recorded result |

_Resolved at build (2026-10-09):_ two more labels.

- `NOT BUILT — AWAITING SCRAPE` is the census when a floor could still pass
  after the operator-run fetch.
- Some outcomes match no worded verdict, for example M1 clearing C1 but not
  C2. Those print `UNWORDED`, with the criteria met.

_Resolved at build (2026-10-13):_ one more label, for the same-ticker read
under the split floors (see [Dependencies](#dependencies)).

- `SAME-TICKER READ — ARM U NOT BUILT` prints when the same-ticker arms pass
  their floors and `ARM U` does not. Beside it, `ARM M1` and `ARM M2` each
  print C0, C1, C2, whether they clear C0–C2, and the `CONTRARY` condition.
- No other worded verdict prints with it. `SELECTION-CONFIRMED`,
  `STRUCTURE-ONLY`, `BASE-RATE`, `NULL`, `UNDERPOWERED`, `CONTRARY` and
  `UNWORDED` are all decided over `ARM U` too, so each would claim something
  about an arm that was not read.
- An arm meeting the `CONTRARY` condition is still named on its own line, for
  the operator, before any further study runs.
- The label is not a verdict of record for the study. The full verdict waits
  for `ARM U`.

## Anti-tuning

- The geometry is frozen in this file: ATM/+5%, the four DTE bands, one
  contract, same expiry on both legs. It may not be re-chosen, widened,
  shifted or re-banded after any number is seen. A losing geometry is a result
  about the picks, not a prompt to search.
- The universe is the flow CSV for that date. It may not be narrowed to liquid
  names, to the tickers the model happened to pick, or to a score band. Each
  of those puts selection back into the benchmark.
- `ARM M2` may not be promoted to PRIMARY after the fact.
- Neither arm's result may be quoted without `ARM CEN`'s exclusion table beside
  it.

## What could ship

None. This study ships no rule under any outcome. Its outcomes are a recorded
verdict, a recorded census, and, on STRUCTURE-ONLY, BASE-RATE, NULL or
CONTRARY, a written narrowing of what the shipped rules may claim.
