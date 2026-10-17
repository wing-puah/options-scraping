## holdout_seal — seal the live dates before they are spent

<!-- outcome:start -->
> Latest outcome: sealed; 0 of 40 priced on the exported tabs (census 2026-10-17); the exports date from 2026-10-06, and a re-export is needed before a newer count is recorded · [log](../../current.md).
<!-- outcome:end -->

_Registered 2026-10-09._

**STATUS: ACCEPTED BY DEFAULT 2026-10-09 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Every open decision of the draft is answered
beside the text it amends, tagged _Resolved at build (2026-10-09)_.

## The question

This is a COMMITMENT, not a study. It has no arms, no module and no report.

It commits that the live signal dates stay unread by research code until enough of them have priced. It then fixes the single read that grades the deploy ladder on those dates.

The seal starts on **2026-09-23**, the first signal date no research run has read an outcome on. Research code reads no outcome on a sealed date until 40 sealed dates have priced and the one registered read below has run. Three forward grades accepted before this file keep reading their own dates from 2026-10-08, and nothing else does. `lib/era.py` enforces it.

This file is a pre-registration because that is the only artefact in this repo that is immutable in substance. A holdout is worth exactly as much as the promise not to peek at it.

_Resolved at build (2026-10-09):_ "no module" still holds for the read. The guard that keeps the promise is code, in `scripts/backtest_study/lib/era.py`.

**Why now.** Everything in the queue "waits on new dates", and the last holdout was spent that way. The February to April 2026 window was absorbed into the book ([robustness review M2](../../robustness-review.md#method)). Without a seal, five waiting questions would read the first live dates that price at once, and no clean window would be left. Candidates held on a correlated window are [`bear_arm` B2](../../arm-index.md#bear_arm), [`financed_spread` F3](../../arm-index.md#financed_spread) and [`portfolio_delta` ARM B](../../arm-index.md#portfolio_delta), plus two provisional rules.

## What this commitment cannot tell you

- It does not show that any held candidate works. Each needs its own registration and its own window.
- It says nothing about a tier other than A and B, or about a sub-window or regime.
- The seal does not bind the journal. The operator sees its live P&L daily, which is the seal's one soft edge.
- It does not show the tier split on the deployed set before the read. None of the named readers prints a per-tier figure on the deployed set.

## The seal

**[Sealed](../../glossary.md#sealed-window):** every signal date on or after **2026-09-23**.

_Resolved at build (2026-10-09):_ the draft sealed every date from 2026-08-11. That window was spent before this file was accepted, so the start moves to the first date no run has read an outcome on. This is the move [`refuse_floor_forward`](refuse_floor_forward.md) asked for in its answer 8: "its start moves past the dates already read".

**Unsealed:** every signal date before 2026-09-23. That is the whole book every current result rests on, plus the spent live dates 2026-08-11 → 2026-09-22. One of those, 2026-09-04, has no priced row yet. It stays unsealed, because the seal is a date boundary and not a row list.

### Plan-time observations, disclosed

Measured before this file was accepted. Counts only; none is a result.

Census of the 2026-10-06 exports:

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

The run list comes from `refuse_floor_forward`'s census and the report headers in `backtests/study_output/`. No priced row on 2026-09-23 or later has existed in any export, so no run can have read one.

### What "sealed" forbids

No study, chart, review, digest or write-up may compute or print an OUTCOME statistic on a sealed date. An outcome statistic is any figure derived from a position's realised or marked P&L: [R](../../glossary.md#r), [E](../../glossary.md#e), [meanR](../../glossary.md#meanr), [PF](../../glossary.md#pf), [win%](../../glossary.md#win-rate), [maxDD](../../glossary.md#maxdd), [MFE/MAE](../../glossary.md#mfe), a dollar total, or any CI, band or fold computed from one.

_Resolved at build (2026-10-09):_ an underlying's move after the signal date, scored against the play's direction, is an outcome too. A study that grades emitted plays on price bars instead of backtest rows is bound the same way.

The ban holds if the sealed dates are read alone, pooled into a larger window, or dropped from a comparison in a way that reveals what they held.

### What "sealed" permits

Four things, and nothing else.

| Permitted | Why it is not a peek |
|---|---|
| Census counts: row counts, date counts, priceability, structure and tier mix | No outcome figure. This is how the unseal condition is checked |
| The production loop: `scripts/journal/`, the deploy card | It is production, not research, and it reads the live book by design |
| Pipeline health: `check_pipeline.py`, header alignment, the era refusals | Mechanical, and blind to outcome |
| Data collection and enrichment on sealed dates | Collecting is not reading |

The journal exception is deliberate. The seal binds the RESEARCH tier, which produces the numbers rules ship on.

### Named readers

_Resolved at build (2026-10-09):_ three forward grades were accepted before this file, each with fixed cells and its own forward window. They are named readers, each from its own first date.

| Named reader | Reads sealed dates from |
|---|---|
| [`refuse_floor_forward`](refuse_floor_forward.md) | 2026-10-08 |
| [`ticker_class`](../f1_selection/benchmark/ticker_class.md), forward P1 only | 2026-10-08 |
| [`narrow_to_fit`](narrow_to_fit.md), forward sign read only | 2026-10-08 |

Three limits bind each named reader:

- It may read only its registered cells, on its own forward dates.
- It may never print the read this file reserves: Tier A or Tier B meanR or PF on the deployed set.
- Its routine, in-sample run stays sealed like any other study.

**The list is closed.** A forward read accepted on or after 2026-10-09 waits for the unseal. Adding a name later is a broken seal, not an amendment.

**What this costs the seal.** Only 2026-09-23 → 2026-10-07 is unread by everyone until the unseal read. From 2026-10-08 the three named readers print pooled outcomes on every look. None of them prints a per-tier figure on the deployed set, so the tier split stays unread. The read below still means what it says, because its timing and figures are fixed now.

### What waits for the unseal

_Resolved at build (2026-10-09):_ each waiting item reads only what the later start allows.

| Item | What it may read now |
|---|---|
| [next-steps §2.2](../../next-steps.md#s2-2) `v4_bridge` composition bridge | Its five composition tests on every date, sealed ones included (the exemption below). It waited for "the live 2026-08/09 dates price"; those dates 2026-08-11 → 2026-09-22 are unsealed. Plan-time observation: 29 of their 30 dates have priced, so it can run now |
| [next-steps §2.6](../../next-steps.md#s2-6) rollback triggers | Unsealed dates only. Every trigger reads gain versus PROD (BEAR_HE trail, LVOL tef-null, credit `sl-none`), so each stays sealed. The credit `sl-none` window starts after 2026-07-13 and has 2026-07-14 → 2026-09-22 open; the rest waits for the unseal |
| [`cost_sensitivity`](../f2_management/cost_sensitivity.md), [`mechanical_benchmark`](../f1_selection/benchmark/mechanical_benchmark.md) | Unsealed dates only. `load_book` withholds the sealed ones for them |

A rollback trigger pools new dates into a whole-book census, so it cannot be a named reader. A trigger rewritten as a forward-only grade would need its own registration, and it would still wait for the unseal.

The two exclusions, for `cost_sensitivity` and `mechanical_benchmark`, are written into those two files, so neither can pass the seal by never having read this one. Both clauses are inert if the operator declines this commitment.

### The `v4_bridge` exemption

_Resolved at build (2026-10-09):_ the weak leak is accepted. A composition test reads what the model emitted on the sealed window and prints no outcome number.

_Resolved at build (2026-10-09):_ the exemption is accepted (the draft's Option 2). This file's own census row already permits structure and tier mix on sealed dates. Forbidding it in `v4_bridge` would forbid what that row allows everywhere else. The weak steering leak cannot move the read, because the read's figures, window and timing are fixed below. The cost is that a later claim that the emission profile was unexamined before the unseal is no longer available.

_Resolved at build (2026-10-09):_ on sealed dates `v4_bridge` may compute exactly these five tests, on emitted plays from the analysis export, and nothing else:

1. structure mix;
2. credit share;
3. plays per day;
4. bear share;
5. ladder tier mix.

It reads no backtest export and prints no outcome figure. Its report states the first sealed date.

_Resolved at build (2026-10-09):_ the duty to "say which dates were sealed" binds when `v4_bridge`'s code is next touched. Today it reads the analysis export directly and never opens a results row, so it prints no outcome on any date.

Every rollback trigger stays sealed, because each reads outcomes. An exemption added after acceptance is a broken seal, not an amendment.

## The unseal condition

The seal lifts on the first day the sealed window holds at least **40 priced signal dates**. A priced date is a sealed signal date with at least one real-or-`strike_expiry_tweak` backtest row.

_Resolved at build (2026-10-09):_ 40 is kept. The reasons the draft gave still hold, and the later start does not change them. `MIN_ERA_DATES` is 30 and the v4 tier mix shifted, so a bare era floor would give a window too thin to separate Tier A from Tier B.

- **Priced, not emitted.** An analysis date with no backtest row does not count. Live dates price only when their options expire or their paths cap.
- **Backfill does not count.** A date before 2026-09-23 never enters the sealed window, however late it is priced ([next-steps §0](../../next-steps.md#pick-up), [§2.2](../../next-steps.md#s2-2)). _Resolved at build (2026-10-09):_ the draft's boundary here was 2026-08-11; it moves with the seal.
- **The count is checked by census only**, which the seal permits.

_Resolved at build (2026-10-09):_ two clauses settle when the seal lifts.

- **Meeting the count does not lift the seal by itself.** The census then says the condition is met. The registered read runs first, before any other code reads the window. The commit that records that read also lifts the guard.
- **A prompt version bump before the count is met.** The window is v4 only, and v5 rows never join it. At the bump the read runs once on the v4 dates that have priced. The `UNDERPOWERED` rule below then decides what each tier prints, and the seal lifts.

## The read, fixed now

On unseal, ONE run, producing exactly these figures on the deployed set (`protocol.top_k_per_day(book, ladder_rank, k=3, ladder_eligible)`, era-scoped, `include_bs=False`, real and tweak only):

| Figure | Tier A | Tier B |
|---|---|---|
| meanR | one number | one number |
| 95% date-clustered [CI](../../glossary.md#ci) on meanR | one interval | one interval |
| PF | one number | one number |
| 95% date-clustered CI on PF | one interval | one interval |

_Resolved at build (2026-10-09):_ the book is every sealed signal date from 2026-09-23, loaded with `load_book(sealed_read="holdout_seal")` and cut to that window before `top_k_per_day`. It includes the dates the named readers have read. Cutting them out would leave a window too short to reach 40 in any useful time.

Nothing else prints. Specifically NOT: any other tier, any sub-window, any regime cut, any structure cut, any DTE band, any exit variant, any sizing arm, any per-year split, any leave-one-out, any second run.

**No re-cut.** The window is read once. If the read is inconvenient, that is the result. A second look at the same window is not a robustness check. It is the thing this file exists to prevent.

The run's output is recorded verbatim in [`study-results/`](../../study-results/) and quoted, not paraphrased, in [`current.md`](../../current.md).

## Verdicts, worded now

Graded on the sealed window alone, never pooled with the unsealed book.

| Token | When | What it triggers |
|---|---|---|
| `CONFIRMED` | Tier A and Tier B each show meanR > 0 with a CI excluding zero, and Tier A's meanR is not below Tier B's | The ladder ([§2](../../../docs/deployment-rules.md#s2)) holds out of sample for the first time. Recorded; nothing new ships on the strength of it |
| `PARTIAL` | One tier clears, the other does not | Recorded as such. The tier that fails loses its out-of-sample support, and every rule resting on it is flagged in [`deployment-evidence.md`](../../deployment-evidence.md) |
| `CONTRARY` | Either tier's meanR is negative with a CI excluding zero | The ladder does not hold out of sample. Surfaced to the operator immediately; the deployment decision is theirs, not this file's |
| `NULL` | Powered, and both CIs straddle zero | The window cannot distinguish the tiers from zero. A real outcome, recorded as one |
| `UNDERPOWERED` | The window reached 40 dates, but a tier has fewer than 40 deployed positions | That tier prints `UNDERPOWERED`, census only. The seal does NOT re-close, and the window is not extended to make it readable. Extending a holdout after seeing it is the failure mode this file names |

## Anti-tuning

- The unseal condition is a count of dates, fixed before any of them price. It may not be raised because the early dates look bad, nor lowered because the wait is long.
- The read is fixed above. No figure may be added to it after the run, and no cut may be taken "just to understand" the result.
- The seal does not re-close after a read. There is one unseal.
- A candidate held on the correlated window ([`bear_arm` B2](../../arm-index.md#bear_arm), [`financed_spread` F3](../../arm-index.md#financed_spread), [`portfolio_delta` ARM B](../../arm-index.md#portfolio_delta)) is not promoted by this read. This read grades the ladder, nothing else. Promoting a held candidate needs its own registration and its own window.
- _Resolved at build (2026-10-09):_ the named-reader list and each reader's first date are fixed. Neither moves to let a study see more.

## How the guard behaves

_Resolved at build (2026-10-09):_ the guard is built, and it withholds rather than refuses. Analysis rows reach the exports the day they are emitted, so a refusal would stop the whole suite at the next export re-pull. `load_book(sealed_read=None)` drops every sealed record before the date floor counts and prints one census line. The unseal read passes `holdout_seal`.

## What could ship

Nothing ships from this commitment under any outcome. Its outcomes are a recorded verdict on the ladder's out-of-sample behaviour, and a written narrowing of what the shipped rules may claim if that verdict is `PARTIAL`, `CONTRARY` or `NULL`.
