## mechanical_benchmark — do the picks beat a mechanical bull call spread on the same dates?

_Registered 2026-10-09._

**STATUS: ACCEPTED BY DEFAULT 2026-10-09 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Every open decision of the draft is answered
beside the text it amends, tagged _Resolved at build (2026-10-09):_. Every default
was fixed before any outcome column was read.

**What this file now says, in one paragraph.** The census runs first, inside
the study module, and decides whether anything else prints. On the cache as it
stood on 2026-10-09 it does not pass: the M1 legs are a few hundred contracts
away, and `ARM U` needs tens of thousands, plus stock bars for most of the
flow universe. So the recorded result is `NOT BUILT — AWAITING SCRAPE`, with
the fetch plan printed. No outcome has been read.

## Question

Is the book selection, or is it a long call spread in a rising market?

Nothing in the repo has ever separated the two
([robustness review, short answer](../../robustness-review.md#short-answer),
point 3). Every recorded edge is measured against the book's own variants:
another exit, another sizing rule, another ordering. No study has ever
compared a pick to what a mechanic with no model would have done on the same
day.

Three sub-questions, answered separately because they can disagree:

| Sub-question | What it isolates | Arm |
|---|---|---|
| Does the pick beat a fixed-geometry call vertical on the SAME ticker and date? | structure, strike and expiry choice | `ARM M1` |
| Does the pick beat a delta-and-DTE matched call vertical on the SAME ticker and date? | everything except geometry | `ARM M2` |
| Does the pick beat the same wrap on a RANDOM ticker from that day's flow universe? | ticker selection, the base-rate question | `ARM U` |

`ARM U` is the one that answers "long calls just worked". `ARM M1` and
`ARM M2` answer "the model wrapped the trade better than a rule would have".

### Why this study exists

`ml_combination`'s benchmark is the ladder itself, so it cannot speak to this
([§7.2](../../../docs/deployment-rules.md#s7-2) shows one structure in one cell
carrying the book). The ladder's in-sample circularity is described in
[`deployment-evidence.md`](../../deployment-evidence.md#why-the-tiers) as
"mitigated, not eliminated". A same-date mechanical benchmark is the missing
external comparator.

## What this is NOT

- **Not an exit study.** Both sides replay through the FROZEN harness
  (`scripts/backtest_study/lib/harness.py`) under the shipped debit-vertical
  exit profile ([§5](../../../docs/deployment-rules.md#s5)) and the same
  [path cap](../../glossary.md#path-cap). The comparison is exit-neutral by
  construction.

  _Resolved at build (2026-10-09):_ the headline replays BOTH sides under
  `DEBIT_PROD` (pt 0.90, sl 0.75, time exit 0.75), the debit row of §5, as G3
  asks. That puts the credit picks (`bull_put_spread`, Tier B) under a debit
  profile too. A declared secondary replays each side under its own §5 row:
  `CREDIT_PROD` for a credit pick, the trail row on a mech `BEAR_HE` date,
  else `DEBIT_PROD`. The secondary prints beside the headline and carries no
  verdict. Both sides are cut at their data end (`replay_basis.bounded`).
  The pick replays at its own contract count, as the book holds it. The
  counterpart replays at 1 lot, as the geometry table says. Only the
  harness's $1,000 dollar stop reads the count.
- **Not a proposal to trade the mechanical wrap.** No outcome of this study
  ships a mechanical rule. A mechanical wrap that wins is a finding about the
  picks, not a new strategy.
- **Not a geometry search.** The geometry is frozen below. If ATM/+5% loses to
  ATM/+10%, that is not this study's business and may not be looked at.
- **Not a cost study.** It compares two books priced the same way. Costs are
  [`cost_sensitivity`](../f2_management/cost_sensitivity.md)'s question. If
  that study lands first, this one inherits its cost model unchanged; if not,
  both books are gross and the report says so on every table.

  _Resolved at build (2026-10-09):_ `cost_sensitivity` is still a draft, so
  both books are gross. The harness replays the stored marks, which are pre-cost.
- **Not a claim about the operator's read.** What the operator actually traded
  is [next-steps §2.5](../../next-steps.md#s2-5)'s `operator_read`, which needs
  the journal.

## Definitions

### Matched geometry, defined

["Matched geometry"](../../glossary.md#matched-geometry) is the phrase that
decides this study, so it is pinned here in full. A mechanical counterpart is a two-leg debit call vertical: long the
lower strike, short the higher strike, both legs on the SAME expiry, on the
same underlying, entered on the same signal date, held under the same exit
profile and path cap.

The two arms differ only in how the strikes and expiry are chosen.

| Element | `ARM M1` — fixed geometry (PRIMARY) | `ARM M2` — matched geometry (SECONDARY) |
|---|---|---|
| expiry | the listed expiry whose DTE at the signal date is nearest the pick's `dte_entry`, and inside the same DTE band | same rule |
| DTE bands | `[7,21) [21,45) [45,90) [90,180)` — a counterpart outside the pick's own band is NOT a match and the pair is dropped | same bands |
| long strike | the listed strike nearest `entry_underlying × 1.00` | the listed strike whose entry-dated delta is nearest the pick's `delta` |
| short strike | the listed strike nearest `entry_underlying × 1.05` | the listed strike 5% above the long strike, rounded to the nearest listed strike |
| contracts | 1 | 1 |

_Resolved at build (2026-10-09):_ the expiry rule compares the pick's
`dte_entry` with a DTE taken on a different day. `dte_entry` is counted from
the pick's recorded entry day, not the signal date. Both are now counted from
the same day, so the pick's own expiry is always the nearest (distance 0). M1
and M2 therefore use the pick's own expiry. Counting both from the signal date
would instead pick a daily expiry one or two days earlier on SPY and QQQ,
which the rule never meant.

_Resolved at build (2026-10-09):_ "the pick's `delta`" has two honest meanings,
so both print.

| Arm | Delta target | Role |
|---|---|---|
| `ARM M2` | the pick's net position delta (the `delta` column's quantity), absolute | SECONDARY, as registered |
| `ARM M2L` | the pick's bought leg's delta, absolute | declared secondary; no verdict |

Both targets and every candidate delta are read on the signal date (see the
next tag). The candidate is a call; its delta is compared with the target's
absolute value, so a put pick's target is matched by a call of that size.

Three rules bind both arms:

- **Strikes and expiry are chosen from entry-dated information only.** The
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
  same session. G2 re-runs every choice on a cache cut at the signal date.
  Any difference fails the run.
- **No degenerate pair.** If the two chosen strikes collide, or the resulting
  width is zero, the pair is dropped and counted, never silently widened.
- **A dropped pair is dropped on BOTH sides.** Every comparison is paired. A
  pick whose counterpart cannot be built leaves the comparison entirely, and
  its exclusion is reported by tier and DTE band (`ARM CEN`).

_Resolved at build (2026-10-09):_ the full listed chain is not on disk. The
study treats as listed every cached strike, plus every multiple of the finer
of the cached spacing and the standard listing step. A pair whose nearest such
strike is not cached, and that the skip-list holds no evidence against, is
AWAITING FETCH. It is neither built on the next strike nor dropped. While any
pair awaits, no outcome prints: the cached strikes are the ones the book
traded, so the cached subset is not the registered population. A fetch that
returns 404 puts the strike on the skip-list, and the walk then steps past it.

`h ≥ 180` is out of scope. It is unpriceable with real data and the BS proxy
tier is OFF ([next-steps §2.7](../../next-steps.md#s2-7)).

### The universe, defined

`ARM U` draws from the day's flow universe, which is pinned as: every ticker
appearing in that signal date's compiled flow CSV, mirrored locally as
`backtests/analysis_inputs_cache/<date>-rollup.csv`, section-tagged so ETFs and
stocks can be reported separately.

- Draws are per date, matched on count to that date's deployed pick count.
- At least 1,000 draws, date-clustered, seeded and recorded.
- A drawn ticker with no priceable counterpart is redrawn, and the redraw rate
  is reported. A redraw rate above 25% on a date makes that date's draw
  UNUSABLE, because the surviving draws are then a liquidity subset rather than
  the universe.
- **The redraw cap and census floor 3 are one number seen from two sides, and
  move together or not at all.** A date whose priceable share of the universe
  is `p` has an expected redraw rate of `1 − p`. So a redraw cap of 25%
  requires a priceable share of at least 75%, which is what census floor 3
  demands. Setting the floor at anything below `1 − cap` would pass dates whose
  draws are then UNUSABLE by construction, and the census would certify a study
  that yields no draws. Changing either number without the other is a
  registration change, not an implementation detail.
- The ticker's own flow score plays no part in the draw. Using it would put
  selection back into the benchmark.

_Resolved at build (2026-10-09):_ how `ARM U` runs.

- **Source.** The universe is `audit/<date>-rollup.csv`, the copy the analysis
  fetch writes, with `backtests/analysis_inputs_cache/` as the fallback. The
  mirror named above stops at 2026-04-07, and v4 dates need the audit copy.
  `Section` (`etfs`, `stocks`) is the tag.
- **Expiry.** A random ticker has no expiry of its own. It gets the standard
  monthly expiry (third Friday, the Thursday before on a holiday) whose DTE
  from the entry day is nearest the pick's, inside the pick's band. Weeklies are
  not used, because which weeklies a name lists is not known from disk.
- **Underlying.** The median `Price~` of the ticker's cached contracts on the
  signal date. Stock bars are used only to plan a fetch, never to choose or
  price.
- **The draw.** Redrawing until priceable samples uniformly from the
  priceable universe. So the paired comparison uses each slot's mean over its
  priceable universe, and the 1,000 seeded draws give the band. The redraw rate
  is `1 − priceable share`, per date and expiry. A date where it exceeds 25% is
  unusable.

## Dependencies

_Resolved at build (2026-10-09):_ the census is the study module's first
stage, not a separate script. It prints counts only, and the module stops
there unless every floor passes and nothing awaits a fetch.

The study is NOT built until a census has been run and read. The mechanical
legs are contracts the backtest never needed, so most of them are not in
`backtests/option_history_cache/` today. Registering the plan before the data
exists is the point.

**What must exist in `option_history_cache`.** For each matched pair, both
mechanical legs need a per-contract CSV
(`<TICKER>_<YYYYMMDD>_<STRIKE><C|P>.csv`) with:

- a real quote on the signal date, so the entry is not carried forward into
  existence;
- rows covering the signal date through the path cap, or through the exit,
  whichever comes first;
- `Bid`, `Ask`, `Latest` and `Delta` populated on the entry row, since
  `ARM M2` selects on entry-dated delta.

**What the census must show, before any module is written.** All five, printed
and read by the operator:

| # | The census must report | Floor for building the study |
|---|---|---|
| 1 | Dates with at least 5 priceable matched pairs | ≥ 25 dates |
| 2 | Share of deployed picks whose counterpart is unbuildable, split by tier | no tier more than 10 points from another |
| 3 | Share of universe tickers per date that are priceable, for `ARM U` | median ≥ 75% of that date's universe — the 25% redraw cap above, read from the other side (`floor = 1 − cap`) |
| 4 | Contracts that must be fetched to reach floors 1–3, as a count and as an estimated scrape volume | named, and approved by the operator before any fetch |
| 5 | Share of pairs falling in each DTE band | printed; no floor, but a band with fewer than 10 pairs is not read |

_Resolved at build (2026-10-09):_ four floors needed a ruling.

| Floor | Problem | Ruling |
|---|---|---|
| 1 | Top-3 per day caps a date at 3 pairs, so "≥ 5 pairs" can never pass | Headline: dates with at least 1 priced M1 pair. Two declared secondary lines print beside it. |
| 2 | Picks out of scope (DTE ≥ 180 or < 7) are dropped for every tier alike | Floor 2 counts in-scope picks only, and ignores pairs still awaiting a fetch |
| 3 | A date can carry up to three expiries | A date's share is its lowest across its expiries |
| 4 | Under the default policy no one approves a fetch | The count prints and the run stops at `NOT BUILT — AWAITING SCRAPE` |

The two floor-1 secondary lines are dates whose every deployed pick is paired,
and dates with at least 5 pairs. The second is always 0.

Each floor prints two values: what the cache gives now, and the most a full
fetch could give. A floor that fails even at that upper value is a definitive
`NOT BUILT`.

Floor 2 is the one that can kill the study rather than delay it. If the
unbuildable share is tier-dependent, the benchmark is liquidity-selected and
the comparison is confounded. In that case the census IS the result, it is
recorded as such, and it feeds the join-attrition question
([robustness review N6](../../robustness-review.md#beyond)) instead.

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
- **The date count is NOT fixed here.** Stated by rule: every era-resolved
  signal date carrying at least one deployed pick with a priceable
  counterpart. No count is written into this file or into the module.
- **Deployed set.** `protocol.top_k_per_day(book, ladder_rank, k=3,
  ladder_eligible)`. This study never re-selects and never re-tiers.
  `ladder_eligible` is `tier in ("A", "B")`, so Tier C and VETO rows are not in
  this study at all — see C4.
- **Sealed dates are excluded, by rule.** Every signal date inside the window
  sealed by [`holdout_seal`](../f4_deployment/holdout_seal.md) is dropped from
  every arm, from both sides of every pair, and from every census count that
  feeds an outcome figure, for as long as that seal stands. This study prints
  paired meanR gains and PF, which is exactly what the seal forbids on a sealed
  date, and its population is stated by rule — so without this clause it would
  sweep the seal the moment a live date priced. The exclusion tracks the seal
  rather than a date list. If the operator declines `holdout_seal`, this clause
  is inert and the population is the whole era.

  _Resolved at build (2026-10-09):_ `holdout_seal` was accepted on 2026-10-09
  with its first sealed date at 2026-09-23. This study is not a named reader,
  so every signal date from 2026-09-23 is withheld from every arm, and
  `ARM U` never reads a sealed date. The module loads the book through
  `load_book()` and applies `era.drop_sealed` again; it opens no export itself.
- **Pairing.** By date, using `protocol.boot_ci_paired_by_date`. Never pooled
  across dates unpaired.
- **Direction.** The mechanical wrap is a bull call vertical in every arm, on
  every pick, including bear picks. That is deliberate: the benchmark is "what
  a mechanic who only buys call spreads would have made", and a bear pick that
  loses to it is exactly the comparison being asked for. The bear subset is
  also reported on its own.

  _Resolved at build (2026-10-09):_ the ladder deploys no bear structure, so
  "bear picks" are the deployed rows whose model regime reads BEAR.

## Arms

- **`ARM T` — THE PICKS.** The deployed book as it stands, replayed unchanged.
  Reference only. It carries no verdict of its own.
- **`ARM M1` — FIXED-GEOMETRY COUNTERPART. PRIMARY.** Same ticker, same date,
  ATM/+5% call vertical in the pick's DTE band.
- **`ARM M2` — MATCHED-GEOMETRY COUNTERPART. SECONDARY.** Same ticker, same
  date, delta-and-DTE matched call vertical.
- **`ARM U` — UNIVERSE NULL. PRIMARY for selection.** The `ARM M1` wrap on
  random flow-universe tickers, at least 1,000 date-clustered draws. Reported
  as a [p5, p95] band. A pick set inside the band has not beaten the base
  rate, whatever its own CI says.
- **`ARM CEN` — CENSUS. DESCRIPTIVE ONLY.** Pair-build rates, redraw rates and
  band coverage by tier, structure and DTE band. Never a criterion.

## Unit and metric

- **Unit** is a matched pair: one deployed pick and its counterpart, on the
  same date and ticker.
- **Metric** is [R](../../glossary.md#r) under the shipped exit profile.
  [E](../../glossary.md#e) is reported beside it and is never a criterion.
- **Headline** per arm: paired within-date mean gain in R
  (`ARM T` minus the counterpart), with a 95% date-clustered CI, plus
  [PF](../../glossary.md#pf) on both sides via `protocol.pf_paired_by_date`,
  never quoted without meanR.

## Gates

Each gate exits non-zero on failure.

- **G1 ERA IDENTITY.** Header names the era and export fingerprint; a wrong or
  thin era refuses (`lib/era.py`).
- **G2 NO LOOK-AHEAD.** Every counterpart's strikes and expiry are recomputed
  from entry-dated information only, verified against an independent
  recomputation. A counterpart whose selection reads a field dated after its
  signal date FAILS the run.
- **G3 EXIT PARITY.** Both sides replay through the same frozen harness call
  under the same profile and path cap. A run whose two sides used different
  exit configs FAILS.
- **G4 PAIRING INTEGRITY.** Every reported comparison is paired on (date,
  ticker), the pair counts on both sides are equal, and dropped pairs sum
  exactly to the census. A mismatch FAILS.
- **G5 PRICING-TIER HONESTY.** Real and tweak only; `bs_options_hist` excluded
  on both sides. No dollar figure pools tiers.
- **G6 NO NEW STATISTIC.** No annualised figure, no Sharpe, no
  time-to-recover.
- **G7 NO HARDCODED CENSUS.** Every count, share and range printed in prose is
  computed from the run.

## Bar for a candidate

All of C1–C5 for a selection claim. C1–C3 are the registered pass rule from
[robustness review N2](../../robustness-review.md#beyond).

- **C0 POWER FLOOR.** An arm is read only if it has at least 25 dates and at
  least 40 matched pairs. Below either, it prints **UNDERPOWERED**: census
  only, no outcome number printed. The floor may not be lowered.
- **C1 GAIN.** Paired within-date mean R gain over the counterpart, with a 95%
  date-clustered CI excluding zero.
- **C2 LEAVE-ONE-DATE-OUT.** Every [LOO](../../glossary.md#loo) fold positive.
  Not "most". Every one.
- **C3 BEATS THE BASE RATE.** The gain over `ARM U` exceeds `ARM U`'s p95
  band.

  _Resolved at build (2026-10-09):_ C3 passes when the picks' mean R, over
  the slots `ARM U` covers, is above the p95 of the random book's mean R
  across the 1,000 draws.
- **C4 TIER COHERENCE.** Tier A's gain is not smaller than Tier B's. The
  comparison is A-versus-B and never A-versus-C: the deployed set fixed in
  §Population is `ladder_eligible`, which is `tier in ("A", "B")`
  (`protocol.ladder_eligible`), so no Tier C row is ever in this study's
  population and no Tier C gain may be computed for this criterion. A ladder
  whose top tier beats the mechanic by less than its second tier does is
  evidence against the ladder, and is reported as such rather than averaged
  away.

  _Resolved at build (2026-10-09):_ C4 is graded on `ARM U`, the arm that
  carries the selection claim. It prints for every arm.
- **C5 ERA STABILITY.** C1 holds on both eras with the same sign.

  _Resolved at build (2026-10-09):_ C5 is graded on `ARM U`. The v3 era runs
  in the same process.

## Verdicts, worded now

- **SELECTION-CONFIRMED** — `ARM U` clears C0–C3 and C4 and C5 both hold, which
  is the "all of C1–C5" bar above. The picks beat a mechanical
  wrap on a random universe ticker. This is the strongest outcome available and
  it still ships nothing on its own.
- **STRUCTURE-ONLY** — `ARM M1` or `ARM M2` clears C0–C2 but `ARM U` does not.
  The model wraps a trade better than a fixed rule, but its ticker choice is
  not distinguishable from the day's universe. Recorded plainly, including in
  [`deployment-evidence.md`](../../deployment-evidence.md), because it narrows
  what every shipped rule can claim.
- **BASE-RATE** — `ARM U` clears but `ARM M1` and `ARM M2` do not. The value is
  in which name is picked, not in how it is wrapped.
- **NULL** — powered, and no arm clears C1. The picks are not distinguishable
  from the mechanical wrap. Exit and sizing tuning stop being the priority; the
  selection question becomes the programme
  ([suggested order](../../robustness-review.md#order), step 2).
- **CONTRARY** — an arm's paired gain is negative with a CI excluding zero. The
  mechanical wrap beats the picks. Surfaced to the operator before any further
  study runs.
- **UNDERPOWERED** — no arm clears C0. Census printed, nothing concluded.
- **NOT BUILT** — the pre-build census fails its floors. The census is the
  recorded result.

_Resolved at build (2026-10-09):_ two more labels.

- `NOT BUILT — AWAITING SCRAPE` is the census when a floor could still pass
  after the operator-run fetch.
- Some outcomes match no worded verdict, for example M1 clearing C1 but not
  C2. Those print `UNWORDED`, with the criteria met.

`CONTRARY` takes precedence over the other powered verdicts, since it must
reach the operator first.

## Anti-tuning

The geometry is frozen in this file: ATM/+5%, the four DTE bands, one contract,
same expiry on both legs. It may not be re-chosen, widened, shifted or
re-banded after any number is seen. A losing geometry is a result about the
picks, not a prompt to search.

The universe is the flow CSV for that date. It may not be narrowed to liquid
names, to the tickers the model happened to pick, or to a score band, because
each of those puts selection back into the benchmark.

`ARM M2` may not be promoted to PRIMARY after the fact, and neither arm's
result may be quoted without `ARM CEN`'s exclusion table beside it.

## Ship criteria

None. This study ships no rule under any outcome. Its outcomes are a recorded
verdict, a recorded census, and — on STRUCTURE-ONLY, BASE-RATE, NULL or
CONTRARY — a written narrowing of what the shipped rules may claim.

## Build notes

Not part of the registration. Implementation only.

- Family `f1_selection/`. No `scripts/study_map/catalog.py` entry until the
  module exists.
- Step 1 is the census, and it is its own script run. The study module is not
  written until the census has been read.
- Counterpart construction should reuse `lib/structure_names.py` for the
  structure label so the mechanical wrap classifies identically to a real one.
- `tests/` gets the geometry rules: band matching, degenerate-pair rejection,
  entry-dated-only selection, and the paired-drop symmetry.
- Built 2026-10-09: `scripts/backtest_study/f1_selection/mechanical_benchmark.py`,
  `scripts/collector/fetch_mechanical_legs.py`,
  `tests/test_mechanical_benchmark.py`. Pricing is production's
  `simulate._simulate` over the cache, loaded as `narrow_to_fit.Chain` loads
  it. Entry fills, junk quotes and the debit-to-credit refusal are therefore
  production's. No model price is used. G5 rebuilds the commission-only picks
  at their own strikes and must match them.
