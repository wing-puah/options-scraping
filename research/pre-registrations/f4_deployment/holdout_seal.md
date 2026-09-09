## holdout_seal — seal the live dates before they are spent

_Registered ____-__-__ (DRAFT — not registered; becomes immutable in substance when the operator accepts it)._

**STATUS: DRAFT.** Until acceptance every date, count, rule and option
below may be edited. After acceptance none of them may. The registration
date is filled in on acceptance and is the only date this file then
carries.

## What this is

A COMMITMENT, not a study. It has no arms, no module and no report. It says
that a named set of dates may not be looked at, names the condition that lifts
that, and fixes in advance the single read taken when it does.

It is filed as a pre-registration because that is the only artefact in this
repo that is immutable in substance, and a holdout is worth exactly as much as
the promise not to peek at it.

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
**2026-08-11**.

The [robustness review](../../robustness-review.md#beyond) says "after
2026-08-11". That wording leaves 2026-08-11 itself outside the seal, and that
date is live and unpriced like the rest, so this file seals it too. The
operator should confirm that reading before accepting; it is the only place
this file differs from the review's own words.

**Unsealed:** every signal date before 2026-08-11, which is the whole book
every current result rests on.

### What "sealed" forbids

No study, chart, review, digest or write-up may compute or print an OUTCOME
statistic on a sealed date. An outcome statistic is any figure derived from a
position's realised or marked P&L: [R](../../glossary.md#r),
[E](../../glossary.md#e), [meanR](../../glossary.md#meanr),
[PF](../../glossary.md#pf), [win%](../../glossary.md#win-rate),
[maxDD](../../glossary.md#maxdd), [MFE/MAE](../../glossary.md#mfe), a dollar
total, or any CI, band or fold computed from one.

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

## The unseal condition

The seal lifts on the first day the sealed window holds at least

**40 priced signal dates** — a sealed signal date with at least one
real-or-`strike_expiry_tweak` backtest row.

Three clauses fix what that sentence means.

- **Priced, not emitted.** An analysis date with no backtest row does not
  count. Live dates price only when their options expire or their paths cap.
- **Backfill does not count.** A date before 2026-08-11 never enters the
  sealed window, however late it is priced ([next-steps
  §0](../../next-steps.md#s0), [§2.2](../../next-steps.md#s2-2)).
- **The count is checked by census only**, which the seal permits.

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

## The two options

Both are written out so the operator picks one. **This file does not choose.**

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
