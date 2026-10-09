## holdout_seal — seal the live dates before they are spent

_Registered 2026-10-09._

**STATUS: ACCEPTED BY DEFAULT 2026-10-09 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Every open decision of the draft is answered
beside the text it amends, tagged _Resolved at build (2026-10-09)_.

**What this file now says, in one paragraph.** The seal starts on
**2026-09-23**, the first signal date no research run has read an outcome on.
Research code reads no outcome on a sealed date until 40 sealed dates have
priced and the one registered read below has run. Three forward grades that
were accepted before this file keep reading their own dates from 2026-10-08,
and nothing else does. `lib/era.py` enforces it.

## What this is

A COMMITMENT, not a study. It has no arms, no module and no report. It says
that a named set of dates may not be looked at, names the condition that lifts
that, and fixes in advance the single read taken when it does.

It is filed as a pre-registration because that is the only artefact in this
repo that is immutable in substance, and a holdout is worth exactly as much as
the promise not to peek at it.

_Resolved at build (2026-10-09):_ "no module" still holds for the read. The
guard that keeps the promise is code, in `scripts/backtest_study/lib/era.py`
(see [Build notes](#build-notes)).

## Why

Everything in the queue "waits on new dates", and the last holdout was spent
that way. The February to April 2026 window was absorbed into the book
([robustness review M2](../../robustness-review.md#method)). There is no
programme-level control for multiple testing, no stopping rule, and the
candidates now held on a correlated window are
[`bear_arm` B2](../../arm-index.md#bear_arm),
[`financed_spread` F3](../../arm-index.md#financed_spread),
[`portfolio_delta` ARM B](../../arm-index.md#portfolio_delta), plus two
provisional rules.

Without a seal, the first live dates that price will be read by five waiting
questions at once, and after that there is no clean window left to answer any
of them.

## The seal

**[Sealed](../../glossary.md#sealed-window):** every signal date on or after
**2026-09-23**.

_Resolved at build (2026-10-09):_ the draft sealed every date from
2026-08-11. That window was spent before this file was accepted, so the start
moves to the first date no run has read an outcome on. This is the move
[`refuse_floor_forward`](refuse_floor_forward.md) asked for in its answer 8:
"its start moves past the dates already read".

Census of the 2026-10-06 exports, counts only:

| Export | Last signal date with a priced row | Rows on or after 2026-09-23 |
|---|---|---|
| `BacktestResults` | 2026-09-22 | 0 |
| `BacktestProxy` | 2026-09-18 | 10, all unpriced, on one date |
| `AnalysisClaude` | — | 105 on 9 dates, no outcome column |

Runs that printed outcomes on 2026-08-11 → 2026-09-22:

| Run | What it printed |
|---|---|
| `account_sim`, 2026-09-28 and 2026-09-29 | Episode E9, 2026-08-11 → 2026-09-22, in every F1 and F2 row |
| The 2026 column, 2026-09-29 | Tier A+B meanR for 2026, naming rows dated 2026-09-15 and 2026-09-18 |
| `narrow_to_fit`, 2026-10-01 and 2026-10-07 | Every cell, through 2026-09-22 |
| `pbo_ledger` and `exit_mechanism_study`, 2026-10-06 and 2026-10-07 | The whole book, through 2026-09-22 |

The run list comes from `refuse_floor_forward`'s census and the report headers
in `backtests/study_output/`. No priced row on 2026-09-23 or later has existed
in any export, so no run can have read one.

**Unsealed:** every signal date before 2026-09-23. That is the whole book every
current result rests on, plus the spent live dates 2026-08-11 → 2026-09-22.
One of those, 2026-09-04, has no priced row yet; it stays unsealed, because the
seal is a date boundary and not a row list.

### What "sealed" forbids

No study, chart, review, digest or write-up may compute or print an OUTCOME
statistic on a sealed date. An outcome statistic is any figure derived from a
position's realised or marked P&L: [R](../../glossary.md#r),
[E](../../glossary.md#e), [meanR](../../glossary.md#meanr),
[PF](../../glossary.md#pf), [win%](../../glossary.md#win-rate),
[maxDD](../../glossary.md#maxdd), [MFE/MAE](../../glossary.md#mfe), a dollar
total, or any CI, band or fold computed from one.

_Resolved at build (2026-10-09):_ an underlying's move after the signal date,
scored against the play's direction, is an outcome too. A study that grades
emitted plays on price bars instead of backtest rows is bound the same way.

That holds whether the sealed dates are read alone, pooled into a larger
window, or dropped from a comparison in a way that reveals what they held.

### What "sealed" permits

Four things, and nothing else.

| Permitted | Why it is not a peek |
|---|---|
| Census counts — row counts, date counts, priceability, structure and tier mix | No outcome figure. This is how the unseal condition is checked at all. |
| The production loop: `scripts/journal/`, the deploy card | It is production, not research. It must keep running, and it reads the live book by design. |
| Pipeline health: `check_pipeline.py`, header alignment, the era refusals | Mechanical, and blind to outcome. |
| Data collection and enrichment on sealed dates | Collecting is not reading. |

The journal exception is deliberate and is the one soft edge in this
commitment. The operator sees live P&L daily because they are trading it. The
seal binds the RESEARCH tier, which is what produces the numbers rules ship on.

_Resolved at build (2026-10-09):_ three forward grades were accepted before
this file, each with fixed cells and its own forward window. They are named
readers, each from its own first date.

| Named reader | Reads sealed dates from | Why it is admitted |
|---|---|---|
| [`refuse_floor_forward`](refuse_floor_forward.md) | 2026-10-08 | Accepted 2026-10-07; its answer 8 asked to be named here |
| [`ticker_class`](../f1_selection/ticker_class.md), forward P1 only | 2026-10-08 | Accepted 2026-10-07; its forward dates are after 2026-10-07 |
| [`narrow_to_fit`](narrow_to_fit.md), forward sign read only | 2026-10-08 | Accepted 2026-10-01; its forward read waits on this decision. Not yet built |

Three limits bind each named reader:

- It may read only its registered cells, on its own forward dates.
- It may never print the read this file reserves: Tier A or Tier B meanR or
  PF on the deployed set.
- Its routine, in-sample run stays sealed like any other study.

**The list is closed.** A forward read accepted on or after 2026-10-09 waits
for the unseal. Adding a name later is a broken seal, not an amendment.

**What this costs the seal, stated plainly.** Only 2026-09-23 → 2026-10-07 is
unread by everyone until the unseal read. From 2026-10-08 the three named
readers print pooled outcomes on every look. None of them prints a per-tier
figure on the deployed set, so the tier split stays unread. The read below
still means what it says, because its timing and its figures are fixed now
and no earlier look can change either.

## The unseal condition

The seal lifts on the first day the sealed window holds at least

**40 priced signal dates** — a sealed signal date with at least one
real-or-`strike_expiry_tweak` backtest row.

_Resolved at build (2026-10-09):_ 40 is kept. The reasons the draft gave
still hold, and the later start does not change them.

Three clauses fix what that sentence means.

- **Priced, not emitted.** An analysis date with no backtest row does not
  count. Live dates price only when their options expire or their paths cap.
- **Backfill does not count.** A date before 2026-09-23 never enters the
  sealed window, however late it is priced ([next-steps
  §0](../../next-steps.md#pick-up), [§2.2](../../next-steps.md#s2-2)).
  _Resolved at build (2026-10-09):_ the draft's boundary here was 2026-08-11;
  it moves with the seal.
- **The count is checked by census only**, which the seal permits.

_Resolved at build (2026-10-09):_ two clauses settle when the seal lifts.

- **Meeting the count does not lift the seal by itself.** The census then
  says the condition is met. The registered read runs first, before any other
  code reads the window. The commit that records that read also lifts the
  guard.
- **A prompt version bump before the count is met.** The window is v4 only,
  and v5 rows never join it. At the bump the read runs once on the v4 dates
  that have priced. The underpowered rule below then decides what each tier
  prints, and the seal lifts.

**40 is the number the operator should set deliberately before accepting
this.** It is proposed because `MIN_ERA_DATES` is 30 and the v4 tier mix
shifted, so a bare era floor would give a window too thin to separate Tier A
from Tier B. Raising it costs waiting; lowering it costs the whole point.

## The read, fixed now

On unseal, ONE run, producing exactly these figures on the deployed set
(`protocol.top_k_per_day(book, ladder_rank, k=3, ladder_eligible)`, era-scoped,
`include_bs=False`, real and tweak only):

| Figure | Tier A | Tier B |
|---|---|---|
| meanR | one number | one number |
| 95% date-clustered [CI](../../glossary.md#ci) on meanR | one interval | one interval |
| PF | one number | one number |
| 95% date-clustered CI on PF | one interval | one interval |

_Resolved at build (2026-10-09):_ the book is every sealed signal date from
2026-09-23, loaded with `load_book(sealed_read="holdout_seal")` and cut to
that window before `top_k_per_day`. It includes the dates the named readers
have read. Cutting them out would leave a window too short to reach 40 in any
useful time.

Nothing else. Specifically NOT: any other tier, any sub-window, any regime cut,
any structure cut, any DTE band, any exit variant, any sizing arm, any
per-year split, any leave-one-out, any second run.

**No re-cut.** The window is read once. If the read is inconvenient, that is
the result. A second look at the same window is not a robustness check, it is
the thing this file exists to prevent.

The run's output is recorded verbatim in
[`study-results/`](../../study-results/) and quoted, not paraphrased, in
[`current.md`](../../current.md).

## Verdicts, worded now

Graded on the sealed window alone, never pooled with the unsealed book.

- **CONFIRMED** — Tier A and Tier B each show meanR > 0 with a CI excluding
  zero, and Tier A's meanR is not below Tier B's. The ladder
  ([§2](../../../docs/deployment-rules.md#s2)) holds out of sample for the
  first time. Recorded; nothing new ships on the strength of it.
- **PARTIAL** — one tier clears, the other does not. Recorded as such. The
  tier that fails loses its out-of-sample support and every rule resting on it
  is flagged in [`deployment-evidence.md`](../../deployment-evidence.md).
- **CONTRARY** — either tier's meanR is negative with a CI excluding zero. The
  ladder does not hold out of sample. Surfaced to the operator immediately; the
  deployment decision is theirs, not this file's.
- **NULL** — powered, both CIs straddle zero. The window cannot distinguish the
  tiers from zero. This is a real outcome and is recorded as one.
- **UNDERPOWERED** — the window reached 40 dates but a tier has fewer than 40
  deployed positions. That tier prints UNDERPOWERED, census only. The seal does
  NOT re-close, and the window is not extended to make it readable. Extending
  a holdout after seeing it is the failure mode this file names.

## The conflict, stated plainly

Sealing these dates blocks the only thing that unblocks the queue. Four things
collide with the seal: two queue items wait on exactly the sealed window, and
two sibling drafts would otherwise sweep it the moment a live date priced.

| Waiting item | What it waits on | Does it read outcomes? |
|---|---|---|
| [next-steps §2.2](../../next-steps.md#s2-2) — `v4_bridge` composition bridge | "the live 2026-08/09 dates price"; backfill does not count | Its five tests are composition tests on EMITTED plays — structure mix, credit share, plays per day, bear share, ladder tier mix. None is a P&L figure. But §2.2 gates it on the dates PRICING, which implies it also wants priced rows. |
| [next-steps §2.6](../../next-steps.md#s2-6) — rollback triggers | new dates; the credit `sl-none` window starts after 2026-07-13 and is unreachable by backfill | Yes. Every trigger reads gain versus PROD. All of them stay sealed under either option below. |
| [`cost_sensitivity`](../f2_management/cost_sensitivity.md) — sibling DRAFT | the cost knobs, the pre-fill grid fix and one suite re-run; NOT new dates | Yes — per-tier net meanR and net PF. Its population is stated by rule over the era, so it would sweep sealed dates automatically. RESOLVED: its §Population now excludes sealed dates by rule while this seal stands. |
| [`mechanical_benchmark`](../f1_selection/mechanical_benchmark.md) — sibling DRAFT | a pre-build census and a counterpart backfill; NOT new dates | Yes — paired meanR gain and PF. Same rule-stated population, same automatic sweep. RESOLVED: its §Population now excludes sealed dates by rule while this seal stands. |

_Resolved at build (2026-10-09):_ what each item gets under the later start.

| Item | What it may read now |
|---|---|
| §2.2 `v4_bridge` | Its composition tests on every date, sealed ones included (Option 2 below). Its awaited live dates 2026-08-11 → 2026-09-22 are unsealed, and 29 of their 30 dates have priced, so it can run now |
| §2.6 rollback triggers | Unsealed dates only. The credit `sl-none` window has 2026-07-14 → 2026-09-22 open; the rest waits for the unseal |
| `cost_sensitivity`, `mechanical_benchmark` | Unsealed dates only. `load_book` now withholds the sealed ones for them |

A rollback trigger pools new dates into a whole-book census, so it cannot be a
named reader. A trigger rewritten as a forward-only grade would need its own
registration, and it would still wait for the unseal.

Both sibling exclusions are written into those two files rather than only here,
so neither can pass the seal by never having read this one. Both clauses are
inert if the operator declines this commitment. Neither study waits on the
sealed window for power: both are blocked on other work, so excluding the seal
costs them nothing today.

The `v4_bridge` case is the live question, because its tests read composition
rather than P&L. Reading composition on the sealed window is a weak leak, not a
strong one: it tells the operator what the model emitted there, which can steer
what they look for on unseal, but it prints no outcome number. Whether a weak
leak is acceptable is a judgement, and this file does not make it.

_Resolved at build (2026-10-09):_ the weak leak is accepted; see Option 2.

## The two options

Both are written out so the operator picks one. **This file does not choose.**

_Resolved at build (2026-10-09):_ **Option 2.** This file's own census row
already permits structure and tier mix on sealed dates. Option 1 would forbid
in `v4_bridge` what that row allows everywhere else. The steering leak cannot
move the read either, because the read's figures, window and timing are fixed
above.

### Option 1 — seal everything

Nothing in the research tier touches a sealed date until the 40-date condition
is met.

| Cost | Detail |
|---|---|
| `v4_bridge` waits longer | The ladder stays UNVALIDATED on v4 for the whole seal. Deployment continues under the v3-derived rules, which is already the standing instruction in §2.2. |
| Rollback triggers wait longer | BEAR_HE trail, LVOL tef-null and credit `sl-none` stay unevaluated. Credit `sl-none` cannot be evaluated at all before unseal, since its fresh window lies entirely inside the seal. |
| Benefit | One clean holdout. Every read on it is the registered read, and no earlier look has shaped it. |

### Option 2 — exempt `v4_bridge`'s five composition tests, seal everything else

`v4_bridge` may run its five composition tests on sealed dates. It may print no
outcome figure on them, and its report must say which dates were sealed.

| Cost | Detail |
|---|---|
| The holdout is no longer clean for composition | A later claim that the emission profile was unexamined before unseal is no longer available. |
| A weak steering leak | Knowing the tier mix on the sealed window can shape which tier the operator expects to clear. |
| Benefit | The queue's oldest blocker moves. The ladder's transfer to v4 can be judged without spending the outcome window. |
| Unchanged | Every rollback trigger stays sealed. They read outcomes, so no exemption is on offer for them. |

If Option 2 is chosen, the exemption is written into this file as a named
clause before acceptance, listing the five tests exactly. An exemption added
after acceptance is a broken seal, not an amendment.

**The `v4_bridge` exemption** (_Resolved at build (2026-10-09)_). On sealed
dates `v4_bridge` may compute exactly these five tests, on emitted plays from
the analysis export, and nothing else:

1. structure mix;
2. credit share;
3. plays per day;
4. bear share;
5. ladder tier mix.

It reads no backtest export and prints no outcome figure. Its report states
the first sealed date.

_Resolved at build (2026-10-09):_ the "say which dates were sealed" duty
binds when `v4_bridge`'s code is next touched. Today it reads the analysis
export directly and never opens a results row, so it prints no outcome on
any date.

## Anti-tuning

- The unseal condition is a count of dates, fixed before any of them price. It
  may not be raised because the early dates look bad, nor lowered because the
  wait is long.
- The read is fixed above. No figure may be added to it after the run, and no
  cut may be taken "just to understand" the result.
- The seal does not re-close after a read. There is one unseal.
- A candidate held on the correlated window
  ([`bear_arm` B2](../../arm-index.md#bear_arm),
  [`financed_spread` F3](../../arm-index.md#financed_spread),
  [`portfolio_delta` ARM B](../../arm-index.md#portfolio_delta)) is not promoted
  by this read. This read grades the ladder, nothing else. Promoting a held
  candidate needs its own registration and its own window.
- _Resolved at build (2026-10-09):_ the named-reader list and each reader's
  first date are fixed. Neither moves to let a study see more.

## Ship criteria

None. No rule ships from this commitment under any outcome. Its outcomes are a
recorded verdict on the ladder's out-of-sample behaviour, and a written
narrowing of what the shipped rules may claim if that verdict is PARTIAL,
CONTRARY or NULL.

## Build notes

Not part of the commitment. Implementation only.

- No study module, no `scripts/study_map/catalog.py` entry, no report of its
  own until unseal.
- The seal is worth enforcing mechanically rather than by memory. The natural
  place is beside `lib/era.py`'s existing refusals: a study run that loads a
  row whose signal date is on or after the sealed boundary refuses, unless it
  declares itself census-only. That code is a separate change and is not
  registered here.
- The census that checks the unseal condition is a counting script. It prints
  the priced-date count in the sealed window and nothing else.

_Resolved at build (2026-10-09):_ the guard is built, and it withholds rather
than refuses. Analysis rows reach the exports the day they are emitted, so a
refusal would stop the whole suite at the next export re-pull.

| Piece | Where | What it does |
|---|---|---|
| `SEAL_START`, `UNSEAL_PRICED_DATES`, `SEALED_READERS`, `SEAL_LIFTED` | `lib/era.py` | The dates, the count, the closed reader list, and the lift date (`None` while sealed) |
| `load_book(sealed_read=None)` | `lib/book.py` | Drops every sealed record before the date floor counts, and prints one census line |
| `drop_sealed`, `drop_sealed_frame` | `lib/era.py` | The same filter for the four studies that open the exports themselves |
| `make seal-census` | `lib/era.py` | Rows and priced dates in the window, against 40. Counts only |
| `tests/test_holdout_seal.py` | `tests/` | Pins the dates and readers, and fails on any study module that resolves an export path without the filter |

`refuse_floor_forward` and `ticker_class` pass their reader names to
`load_book`. `narrow_to_fit` passes it only when its forward read is built.
The unseal read passes `holdout_seal`.
