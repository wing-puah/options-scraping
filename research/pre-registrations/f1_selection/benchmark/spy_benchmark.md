## spy_benchmark — do the deployed picks beat a SPY call spread on the same dates?

<!-- brief:start -->
## In brief

> Plain-language brief for readers. The registration below is the binding text; where the two differ, the registration wins. `study_review` cuts this brief out before grading, so the blind graders never see it.
> Latest outcome: `DOES-NOT-BEAT` (headline basis, `SB-UNIT = pick`) — 2026-10-15 · [record](../../../study-results/f1_selection/benchmark/spy_benchmark.md).
> Nothing else in this brief is a result.

**The question**

Is the book's edge, if any, more than a SPY bull call spread bought on the same days?

The study is the cheap half of the ticker-choice question that `mechanical_benchmark ARM U` leaves unbuilt. It compares the picks with the index, not with a random name. It needs a few hundred SPY contracts, not about 39,000.

**Post hoc, and weaker for it**

The operator proposed this study after seeing three results: `cost_sensitivity` (2026-10-09), `direction_hit` (2026-10-12) and the first `mechanical_benchmark` read (2026-10-14). Those reads make a negative result more likely. Every record of the study says so. It was registered 2026-10-14 and accepted by default.

**What it compares**

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

**How it is judged**

**Measure.** Paired mean gain in [R](../../../glossary.md#r) per pair, picks minus SPY wrap. The CI is date-clustered. E prints beside it.

**Population.** `mechanical_benchmark`'s deployed set: top 3 per day, Tier A and B, real and `strike_expiry_tweak` rows. It is the post-P3 book. Signal dates from 2026-09-23 are withheld while the [`holdout_seal`](../../f4_deployment/holdout_seal.md) stands. v4 is the headline. v3 runs only with `--v3`. Gross of costs.

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

**Possible verdicts**

Precedence runs from the bottom of the table up: census, then C0, then `CONTRARY`, then `BEATS-SPY`.

| Token | What it means |
|---|---|
| `BEATS-SPY` | C0, C1 and C2 hold, and `CONTRARY` does not |
| `CONTRARY` | C0 holds and the SPY spread beat the picks |
| `DOES-NOT-BEAT` | C0 holds, C1 or C2 fails, and `CONTRARY` is not met |
| `UNDERPOWERED` | C0 fails; counts print, no outcome number |
| `NOT BUILT` | A census floor fails even after a full fetch |
| `NOT BUILT — AWAITING SCRAPE` | A SPY pair awaits a fetch |

**What could ship**

Nothing ships. The study is not an input to [`programme_gate`](../../f4_deployment/programme_gate.md). It is recorded beside the gate and never changes it.

**What this study cannot tell you**

- Whether the picks beat a random name. SPY is one ticker; `ARM U` still owns that question.
- Whether to trade SPY call spreads. That needs its own registration.
- Anything about QQQ, IWM or any other index. SPY is fixed.
- Anything stronger than a post-hoc read. The study was proposed after three results were seen.
- Anything from the `date` setting alone. It may not become the verdict.

---
<!-- brief:end -->

_Registered 2026-10-14._

**STATUS: ACCEPTED BY DEFAULT 2026-10-14 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** The operator chose this study as P2 of the
[2026-10-13 plan](../../../next-steps.md#plan-20261013). Every contested
choice below is a parameter, and the run prints its outcome both ways. Only
the default is the verdict.

**What this file says, in one paragraph.** On each deployed pick's signal
date, a mechanic buys an ATM / +5% SPY call spread at the pick's own expiry,
enters on the pick's recorded entry day, and holds it under the same exit
profile. The study asks whether the picks made more R than that SPY spread.
It is the cheap half of the ticker-choice question that
`mechanical_benchmark`'s `ARM U` leaves unbuilt: it compares the picks with
the index, not with a random name. It ships nothing, and it is not an input to
[`programme_gate`](../../f4_deployment/programme_gate.md).

## Post hoc, and weaker for it

**This study was proposed after three results were seen.** It is weaker
evidence than a test planned in advance, and every record of it says so.

| Seen before this file | What it showed |
|---|---|
| [`cost_sensitivity`](../../f2_management/cost_sensitivity.md), 2026-10-09 | Neither tier has a measured edge on v4, gross or net |
| [`direction_hit`](../signal/direction_hit.md), 2026-10-12 | Nothing known at entry predicts the underlying's direction; v4 is a bull tape |
| [`mechanical_benchmark`](mechanical_benchmark.md) P1, 2026-10-14 | `ARM M1`, the ATM/+5% spread on the pick's own ticker, meets `CONTRARY`, gross |

Those reads make a negative result here more likely than it was before they
were seen. A SPY call spread in a rising tape is a hard benchmark to beat.
The drafter knew that when choosing the arm.

**No SPY-arm outcome exists at registration.** The study module did not
exist when this file was written. One overlap is stated plainly: picks on SPY
itself are already in `mechanical_benchmark`'s `ARM M1`, where the counterpart
is the same SPY spread. Those rows sat inside P1's aggregate and were never
read on their own.

## Question

Is the book's edge, if any, more than a SPY bull call spread bought on the
same days?

`mechanical_benchmark` tests ticker choice through `ARM U`, a random ticker
from the day's flow universe. That arm needs about 39,000 contracts and stock
bars for about 1,978 tickers. This study needs a few hundred SPY contracts.
It answers a narrower question: does picking names beat holding the index,
wrapped the same way, on the same days?

## What this is NOT

- **Not `ARM U`.** SPY is one ticker, not a draw from the universe. A pick set
  that beats SPY may still not beat a random name, and the reverse.
- **Not a `programme_gate` input.** The gate's registration names only
  `mechanical_benchmark`'s same-ticker arms and says P2 "is recorded beside
  the gate and never changes its outcome". This study keeps to that.
- **Not a proposal to trade SPY call spreads.** A SPY spread that wins is a
  finding about the picks. Trading it would need its own registration.
- **Not an exit, geometry or cost study.** The rules below are
  `mechanical_benchmark`'s, unchanged.

## The arm, defined

`ARM SPY` — **the SPY wrap. PRIMARY.** For every deployed pick, one two-leg
debit call vertical on SPY:

| Element | Rule | Source |
|---|---|---|
| expiry | the pick's own expiry date | `ARM M1`'s rule, which uses the pick's own expiry |
| long strike | the listed SPY call strike nearest SPY's signal-date price × 1.00 | `ARM M1` |
| short strike | the listed SPY call strike nearest SPY's signal-date price × 1.05 | `ARM M1` |
| contracts | 1 | `ARM M1` |
| entry | the pick's recorded entry day (`bear_rewrap.recorded_entry_date`) | `ARM M1` |
| SPY's price | the median `Price~` of SPY's cached contracts on the signal date | `ARM U`'s rule for a ticker other than the pick's |
| direction | a bull call spread on every pick, bear picks included | `mechanical_benchmark` §Direction |

The expiry needs no DTE-band check: the same expiry and the same entry day
give the same DTE, so the SPY wrap is always in the pick's band.

_Resolved at build (2026-10-15):_ the arm inherits `ARM M1`'s no-spot drop.
When no cached SPY contract carries a row on the signal date, the pair drops
as `no_spot_at_signal` instead of awaiting forever. This was decided before
any SPY outcome printed. It reads nothing after the signal date. Three pairs
drop this way, all on Sunday 2024-07-28.

**Reused, not re-encoded.** The module imports `mechanical_benchmark`'s
functions: `select_m1` (strike choice, the skip-list walk and the AWAITING
rule), `finish` (production's `_simulate` pricing), `UniverseSpot`,
`slot_of`, `deployed`, `profile_for`, `replay_R`, `grade` and the seal. Each
rule below therefore means exactly what it means there:

- strikes and price are read on or before the signal date (gate G2);
- a degenerate pair is dropped, never widened;
- a strike that could be listed but is not cached makes the pair AWAITING
  FETCH, and no outcome prints while any pair awaits;
- entry fills, junk quotes and the debit-to-credit refusal are production's;
  no model price is used.

`ARM T` — **the picks**, replayed unchanged. Reference only.

`ARM CEN` — **the census**: built, dropped and awaiting counts by tier,
structure and DTE band. Never a criterion.

### A date with several picks

Up to three picks deploy on a date, often with different expiries. Two
honest ways to pair them exist, so both print.

| `SB-UNIT` | Unit | SPY side | Default? |
|---|---|---|---|
| `pick` | one row per pick | the SPY wrap at that pick's expiry; a SPY wrap repeats when two picks share an expiry | **Yes** |
| `date` | one row per date | the SPY wrap at the expiry of the date's top-ranked paired pick, against the mean R of the date's paired picks | Printed beside it |

Why the default: it mirrors `mechanical_benchmark`'s unit, one pick and its
counterpart, and keeps each pick's own expiry. The CI is date-clustered
(`protocol.boot_ci_paired_by_date`), so repeated SPY wraps on one date are
not counted as independent. The `date` setting needs no extra contracts: its
SPY wrap is the one already built for the top-ranked pick. Each setting is
graded on its own rows, against the same C0 floor.

## Population and basis

- **Deployed set.** Whatever `mechanical_benchmark`'s deployed set is:
  `lib/book.py::load_book()`, era-scoped, `include_bs=False`, then
  `protocol.top_k_per_day(book, ladder_rank, k=3, ladder_eligible)`. The
  module calls that study's `deployed()`; it never re-selects or re-tiers.
- **It is the post-P3 book.** P3 (2026-10-13) made `book_tier` call
  `mapping.ladder_tier()`, which moved 34 v4 Tier B rows to VETO
  ([next-steps item 8](../../../next-steps.md#s0)). Those rows leave the
  deployed set and others fill their slots. `mechanical_benchmark`'s P1 run
  of record used the pre-P3 tiers, so the two populations differ.
- **Scope.** Picks with DTE under 7 or at least 180, and picks that are not a
  two-leg same-expiry vertical, drop as `slot_of` drops them.
- **Sealed dates are excluded**, as in `mechanical_benchmark`: every signal
  date from the [`holdout_seal`](../../f4_deployment/holdout_seal.md) start
  (2026-09-23) is withheld from both sides, for as long as the seal stands.
- **Era.** v4 is the headline. v3 is optional: it runs only with `--v3`, and
  prints an outcome only once none of its SPY pairs awaits a fetch. Default:
  v4 only. No era-stability criterion exists here.
- **Basis.** Gross of costs, as `mechanical_benchmark`'s headline. The stored
  marks are pre-cost, and both sides are priced the same way.
- **Metric.** [R](../../../glossary.md#r) per pair; E printed beside it.

### Exit profiles

| Basis | Picks | SPY wrap | Role |
|---|---|---|---|
| headline | `DEBIT_PROD` | `DEBIT_PROD` | the verdict |
| own profile | the pick's own §5 row (credit → `CREDIT_PROD`, mech `BEAR_HE` → the trail row, else `DEBIT_PROD`) | `DEBIT_PROD`, or the trail row on a mech `BEAR_HE` date | declared secondary, no verdict |

These are `mechanical_benchmark`'s two bases, through its `profile_for`. Both
sides replay through the frozen harness, cut at their data end.

## Census floors

The census runs first and decides whether anything else prints. Each floor
prints what the cache gives now and the most a full fetch could give.

| # | The census reports | Floor |
|---|---|---|
| 1 | Dates with at least 1 priced SPY pair | ≥ 25 dates |
| 2 | Share of in-scope picks whose SPY wrap is dropped, by tier | no tier more than 10 points from another; scope drops and awaiting pairs not counted |
| 3 | SPY contracts to fetch, as a count | named, and approved by the operator before any fetch |
| 4 | Pairs by DTE band | printed; a band with fewer than 10 pairs is not read |

- A floor that fails even at its upper value prints `NOT BUILT`.
- While any SPY pair awaits a fetch, the study prints
  `NOT BUILT — AWAITING SCRAPE` and the fetch count. No outcome prints.
- Floor 2 matters less here than in `mechanical_benchmark`: SPY is liquid,
  so a drop is mostly an expiry SPY does not list. It is kept so a
  tier-dependent drop cannot pass unseen.
- There is no universe floor: no ticker is drawn.

_Resolved at build (2026-10-15):_ ruling B. A SPY wrap whose expiry SPY had
not listed on the signal date drops as `expiry_not_listed_at_signal`. It no
longer awaits a fetch that cannot build it.

- **The rule.** The wrap drops when both hold:
  - (a) every cached SPY contract at that expiry, call or put, has rows,
    and its first row is strictly after the signal date;
  - (b) at least 5 contracts are cached at that expiry
    (`EXPIRY_NOT_LISTED_MIN_CONTRACTS`).
- **Why (b).** An expiry lists all its strikes at once. Many strikes that
  all first trade after the signal date show the expiry did not exist then,
  whatever strikes they are. Fewer than 5 is too thin, so the pair still
  awaits a fetch.
- **Amended the same day, before any SPY outcome printed.** The first
  version of (b) asked that the cached call strikes span both targets. That
  left 5 Feb-2027 slots blocked. Their ATM target sits below the lowest
  cached strike, and that strike returns an empty live feed, which never
  caches. So the span could never be met.
- **Why it fits this file.** Floor 2 above already expects that "a drop is
  mostly an expiry SPY does not list". The ruling names that drop.
- **No look-ahead.** The rule reads each cached file's first row, which can
  be dated after the signal. That only decides that the expiry was not
  listed. It never chooses a strike, and a cache cut at the signal date gets
  the same answer (gate G2).
- **Scope.** `ARM SPY` only. `mechanical_benchmark`'s arms are unchanged.
- **Floor 2.** These drops count toward floor 2, and the census table lists
  the reason.

## Gates

Each gate exits non-zero on failure.

- **G1 ERA IDENTITY.** Through `load_book` and `lib/era.py`.
- **G2 NO LOOK-AHEAD.** Every SPY choice is re-run on a cache cut at the
  signal date (`mechanical_benchmark.AsOfChain`). Any difference fails the
  run.
- **G3 EXIT PARITY.** Both sides through one harness call under the same
  profile on the headline basis.
- **G4 PAIRING INTEGRITY.** Built + dropped + awaiting equals the deployed
  count, and both sides of every reported comparison carry the same rows.
- **G5 PRICING-TIER HONESTY.** Real and tweak rows only on the picks' side;
  no model price on the SPY side.
- **G6 NO NEW STATISTIC.** No annualised figure, Sharpe or time-to-recover.
- **G7 NO HARDCODED CENSUS.** Every count is computed by the run.

## Criteria

`mechanical_benchmark`'s per-arm criteria, verbatim by reference
([Bar for a candidate](mechanical_benchmark.md#bar-for-a-candidate)):

- **C0 POWER FLOOR** — at least 25 dates and 40 matched pairs (rows, under
  `SB-UNIT = date`). The floor may not be lowered.
- **C1 GAIN** — paired within-date mean R gain over the SPY wrap, with a 95%
  date-clustered CI excluding zero.
- **C2 LEAVE-ONE-DATE-OUT** — every LOO fold positive.
- **The `CONTRARY` condition** — the paired gain is negative with a CI
  excluding zero.

C3, C4 and C5 are not used: there is no universe band, and Tier A against
Tier B and v3 print as context only.

## Verdicts, worded now

| Token | When |
|---|---|
| `BEATS-SPY` | C0, C1 and C2 hold, and the `CONTRARY` condition does not |
| `CONTRARY` | C0 holds and the `CONTRARY` condition is met: the SPY spread beat the picks |
| `DOES-NOT-BEAT` | C0 holds, C1 or C2 fails, and the `CONTRARY` condition is not met |
| `UNDERPOWERED` | C0 fails; counts print, no outcome number |
| `NOT BUILT` | a census floor fails even after a full fetch |
| `NOT BUILT — AWAITING SCRAPE` | a SPY pair awaits a fetch |

Precedence runs from the bottom of the table up: the census first, then C0,
then `CONTRARY`, then `BEATS-SPY`. The verdict of record is the headline
basis under `SB-UNIT = pick`. The `date` setting and the own-profile basis
print their own tokens beside it, and carry no verdict.

**What each outcome means.**

- `BEATS-SPY`: the picks made more R than the index spread on the same days.
  It does not show they beat a random name; `ARM U` still owns that.
- `DOES-NOT-BEAT` or `CONTRARY`: on these dates, the selection layer did not
  earn more than holding SPY the same way. Recorded beside the
  `programme_gate` read; the gate does not change.

## Anti-tuning

- The geometry, expiry rule, entry day and profiles are
  `mechanical_benchmark`'s, frozen there. None is re-chosen here.
- SPY is fixed. No other index (QQQ, IWM) is added after a number prints.
- `SB-UNIT = date` may not become the verdict after the fact.

## Ship criteria

None. No outcome ships a rule.

## Build notes

Not part of the registration. Implementation only.

- Module `scripts/backtest_study/f1_selection/benchmark/spy_benchmark.py`; it
  imports `mechanical_benchmark` and adds only the SPY slot, the two units,
  the floors and the verdict.
- Fetch: `python3 scripts/collector/fetch_mechanical_legs.py --arms SPY
  --no-v3 --dry-run` prints the count; drop `--dry-run` and add `--limit N`
  to fetch once the operator approves it. The collector's loop, skip-list and
  fetch order are unchanged.
- Tests in `tests/test_spy_benchmark.py`: pairing under both units, the
  cut-cache check, and the AWAITING stop.
- Catalog entry: state open, verdict "registered; awaiting fetch".
- Fetch planning off `backtests/mech_regime/spy_vix_daily_full.csv`, for a
  signal date with no SPY row cached, was removed on 2026-10-15. Such a pair
  now drops as `no_spot_at_signal`, so nothing is planned for it.
