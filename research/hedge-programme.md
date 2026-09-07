# The hedge programme

The hedge is two claims and only one of them has been tested. Every mechanical
rule for when to open a hedge has been tested and none survives. Whether the
thing you put on pays for itself has never been powered. Nothing ships from any
of it, and [§4](../docs/deployment-rules.md#s4) keeps its one bear sleeve as
operator policy.

_Written 2026-09-07. Every verdict below is the last recorded run of that study:
era `v4`, git sha `e59356f`, recorded 2026-09-04. The population on every one of
them is 535 real results, 1,303 proxy rows, 2,212 analysis rows and 819
`spy_vix_daily_full` rows, from inputs dated 2026-09-04 11:10 to 20:31. Two
power-gate figures in [Q4](#q4) are carried forward from an earlier run and are
labelled there. Metrics are defined in [`glossary.md`](glossary.md) and
study-local labels in [`arm-index.md`](arm-index.md)._

This page groups studies that have already run. It adds no result. The record's
own split is two claims rather than four, the trigger and the instrument
([closing note](deployment-evidence.md#the-hedge-trigger-is-dead-the-hedge-instrument-is-unmeasured-closing-note-2026-09-04)).
The four questions below are a finer cut of that same split. Where the note this
page was drafted from disagreed with a file, the file won, and the sharpest case
is [§4](../docs/deployment-rules.md#s4) itself: the sleeve and its half-size line
are held despite `D2` and `D3` never being met, not shipped on them.

<a id="q1"></a>
## Q1. WHEN to open a hedge

**No mechanical trigger survives.** Four candidate triggers have been tested and
all four are dead. The one that came closest, book concentration, was refuted at
its precondition on a powered sample.

`hedge_timing` asks whether chop, a gap-up or a SPY down-run picks a day on
which the bear sleeve earns more than the same day's ladder-eligible long
([pre-registration](pre-registrations/f4_deployment/hedge_timing.md),
[record](study-results/f4_deployment/hedge_timing.md)). Its labels are in
[`arm-index.md`](arm-index.md#hedge_timing).

| Arm | Verdict, as printed |
|---|---|
| paired within-date, chop | `ARM H3-CHOP        : NULL` |
| paired within-date, gap-up | `ARM H3-GAP         : CONTRARY` |
| paired within-date, down-run | `ARM H3-DECLINE     : NULL` |
| between-date, gap-up | `ARM H1-GAP         : CONTRARY` |
| dollars, gap-up | `ARM H4-GAP         : NULL` |

The gap-up row is the one finding the programme produced. It is a prohibition
rather than a rule. [§4](../docs/deployment-rules.md#s4) now bans the gap as the
reason to hedge, on the paired excess in the table below.

| Reading | Figure | Accepted by the operator |
|---|---|---|
| `ARM H3-GAP` paired excess | −0.506 [R](glossary.md#r), [CI](glossary.md#ci) [−0.844, −0.157] | 2026-09-06 |

`hedge_concentration` asks the prior question, whether a session's cluster
concentration predicts the book's later drawdown at all
([pre-registration](pre-registrations/f4_deployment/hedge_concentration.md),
[record](study-results/f4_deployment/hedge_concentration.md),
[labels](arm-index.md#hedge_concentration)).

| Stage | Verdict, as printed |
|---|---|
| the precondition | `VERDICT — Stage 1 (ARM K, the precondition): PRECONDITION-NULL` |
| the mechanism | `VERDICT — Stage 2 (ARM C, the mechanism): NOT RUN (Stage 1 PRECONDITION-NULL)` |

**Why it stopped.** `hedge_timing` ran to completion and produced zero
candidates out of nine headline cells. Its own ship criteria say nothing ships
from it under any outcome. The operator's literal four-day and five-day streak
rule was fixed in advance as `DECLINE-UNDERPOWERED`, because the book samples
too few occurrences to reach the 25-date floor. `hedge_concentration` was a
powered refusal rather than a power stop, so Stage 2 never opened.

**What would unblock it.** [`next-steps.md`](next-steps.md) §2.10, open with
nothing in it. Another timing rule cut from these dates and these columns does
not count. What counts is a signal the book does not carry yet, either hedge
flow in the analysis or a live exposure reading from the journal, read on the
mark-to-market curve, on dates chosen without a rule. A census of how many book
dates carry the proposed signal comes before any registration. §2.1 is closed
and stays closed.

<a id="q2"></a>
## Q2. WHAT to hedge with

**No instrument has a powered read.** Three instruments have been examined and
each stopped for a different reason. Nothing here refutes an instrument. It
leaves them unmeasured.

The bear put debit is the shipped one. `bear_deploy` asks whether it pays as a
hedge and which one to pick
([pre-registration](pre-registrations/f4_deployment/bear_deploy.md),
[record](study-results/f4_deployment/bear_deploy.md),
[labels](arm-index.md#bear_deploy)).

| Criterion | Verdict, as printed |
|---|---|
| hedge contribution | `D2 hedge is real          : NOT MET` |
| conditional pick | `D4 conditional pick       : NOT MET` |
| joint selection and exit | `D1 joint selection x exit : NOT MET` |

The straddle, the strangle and the calendar were built and priced by
`vol_sleeve` on the dates the engine already signalled
([pre-registration](pre-registrations/f3_structure/vol_sleeve.md),
[record](study-results/f3_structure/vol_sleeve.md)). Its diversification
question, whether the sleeve is anti-correlated with the deployed book or
positive on that book's worst dates, came back null. Only the calendar carried a
negative correlation. The straddle and the strangle re-wrap the exposure the
book already has.

The calendar was then re-derived on its own, under a pre-registered pick rule
and a strict fill rule, by `calendar_hedge`
([pre-registration](pre-registrations/f3_structure/calendar_hedge.md),
[record](study-results/f3_structure/calendar_hedge.md),
[labels](arm-index.md#calendar_hedge)).

| Gate | Verdict, as printed |
|---|---|
| fill | `H0 FILL           NOT MET` |
| hedge contribution | `H2 (primary)      NOT EVALUABLE` |
| hedge contribution, sensitivity | `H2 under hold     NOT EVALUABLE   (sensitivity — may not change the verdict)` |

**Why it stopped.** On every `v4` export the first gate to fail is the fill
gate, not the primary. The sleeve is available on about half the deployed dates
and about a third of the worst tenth. The primary then cannot be read at all,
because its worst-decile cell never reaches the pre-registered floor of 10
positions. On `v3` the fill gate passed and the primary was still not evaluable.
`vol_sleeve` stopped for a different reason. Its correlation question was
answered and the answer was no, and nothing in that study can ship on its own.
`bear_deploy` stopped for a third reason. It ran clean and shipped no rule
because it was registered to ship none.

| Line | 2026-09-04 export, recorded | live tabs 2026-09-07, projection |
|---|---|---|
| Deployed dates | 147 | 163 |
| Worst-decile dates | 14 | 16 |
| Fill, deployed dates | 75 / 147 = 51.0% | 83 / 163 = 50.9% |
| Fill, worst-decile dates | 4 / 14 = 28.6% | 5 / 16 = 31.2% |
| Worst-decile cell | n=4, [meanR](glossary.md#meanr) +0.810 | n=5, meanR +0.557 |

The projection column is not a recorded run. It was taken on staged tabs and
appended to no record
([sizing](current.md#2026-09-07-fourth--calendar_hedge--the-new-dates-do-not-unblock-it-two-cached-legs-have-gone-missing)).

**What would unblock it.** [`next-steps.md`](next-steps.md) §2.3 for the
calendar, blocked on new dates and sized at roughly 320 deployed dates. For the
bear put debit it is `bear_deploy`'s own forward trigger, a re-grade once the
book holds at least 20 multi-candidate bear dates after 2026-08-11. `vol_sleeve`
carries no queue item at all.

<a id="q3"></a>
## Q3. HOW MUCH to hedge

**No size has ever been supported by evidence, and the half-position line is
policy.** The sizing criterion is one rule, written once in `bear_deploy` and
then reused verbatim by two other studies. It reads the largest fraction whose
[maxDD](glossary.md#maxdd) and worst single date are both no worse than carrying
no sleeve.

| Study | Criterion | Verdict, as printed |
|---|---|---|
| `bear_deploy` | `D3` | `D3 always-on sizing       : NOT MET at any size` |
| `hedge_timing` | `ARM H4` | `ARM H4-CHOP        : NULL` |
| `hedge_timing` | `ARM H4` | `ARM H4-DECLINE     : NULL` |
| `calendar_hedge` | `H3` | not reached, the study stops at `H0 FILL           NOT MET` |

`hedge_exposure` sweeps a size fraction against a concentration threshold, nine
cells in all
([pre-registration](pre-registrations/f4_deployment/hedge_exposure.md),
[record](study-results/f4_deployment/hedge_exposure.md),
[labels](arm-index.md#hedge_exposure)). Every cell of the ratified population is
power-stopped.

| Stratum | Verdict, as printed |
|---|---|
| pooled trigger | `UNDERPOWERED       9 cell(s)` |
| direct | `UNDERPOWERED       9 cell(s)` |
| constituent | `UNDERPOWERED       9 cell(s)` |

**Why it stopped.** `D3` has never been met at any size, on any era. The
[§4](../docs/deployment-rules.md#s4) size line of at most half a normal position
was registered as policy held whatever the outcome, and the card says so. Two of
the three sizing reads are also measured on a curve that books profit and loss
on the session a position exits, and never marks an open one. On a book measured
the same way that curve missed 40% of the drawdown.

| population | mark-to-market maxDD | close-bucketed maxDD | gap |
|---|---|---|---|
| `real` stratum, 485 rows | −$21,890 | −$22,592 | mark-to-market better by $702 |
| `all`, ratified, 996 rows | −$32,571 | −$23,239 | close understates by $9,332, 40.2% |

That gap is a fact about the basis and not a correction factor for any of the
three figures
([basis](deployment-evidence.md#the-curve-d3-was-read-on-understates-drawdown-2026-08-31-hedge_exposure-arm-m)).
`calendar_hedge` `H3` compounds it. It read `NOT MET`, then deployable at full
size, then `NOT MET` on three consecutive exports, so it is recorded as an
unstable measurement rather than a verdict.

**What would unblock it.** [`next-steps.md`](next-steps.md) §2.3 for
`calendar_hedge` `H3`, which also carries the basis caveat. `hedge_exposure`
carries no numbered item. Its registration forbids searching for a threshold
that would power a cell, so the only path is the book accruing more trigger
dates. Any future read that wants to conclude about drawdown computes the
mark-to-market curve instead.

<a id="q4"></a>
## Q4. HOW the portfolio make-up changes the answers

**It does not, because the link it would work through is absent.** On the
admitted book, how concentrated a session is says nothing about how far the book
draws down next. A concentration gate therefore has no trigger to stand on.

`hedge_concentration` measured that link on the positions `account_sim` actually
takes under the top-three-per-day rule and the exposure caps. The precondition
was powered and it was refused.

| Reading | Figure | Population |
|---|---|---|
| tercile contrast | −$173.65, CI [−$1,205.66, +$893.81] | 626 usable sessions, terciles 216 / 215 / 195 |
| Spearman rho | +0.0000, CI [−0.2198, +0.2231] | the same 626 sessions |

Those two figures are quoted from
[the log](current.md#2026-09-04-late--first-book-with-2026-dates-export-refreshed-suite-re-run-nothing-ships-the-year-clause-bites-campaign-b-closed),
because the frozen record for the `e59356f` run carries the verdict lines and no
numbers.

The power gate and the clause tally were not re-measured on that run. They are
carried forward from the earlier `64689d0` run of the same study, on a smaller
admitted book of 225 rows over 112 dates.

| Reading, `64689d0` | Figure |
|---|---|
| usable sessions per tercile | 172 / 172 / 152, floor 60 each — passed |
| dense episodes | 3, floor 3 — passed at the floor |
| bar clauses | four of six failed |
| tercile contrast on that book | −$767.93, CI [−$2,186.47, +$349.09] |

The two clauses that passed are the controls, so this is not a gross-exposure
effect wearing a concentration label. It is no effect. That run is written up in
[deployment-evidence](deployment-evidence.md#the-queued-max-drawdown-question-is-closed-for-concentration-gated-hedging-2026-09-04-hedge_concentration-stage-1).

`hedge_exposure` is the same question one layer out, on the whole book rather
than the admitted one. Its cells are all power-stopped, so it says nothing about
composition either. Its measurement arm is the one part of the hedge programme
that produced a usable number, and it is a fact about the measuring instrument
rather than about hedging.

**Why it stopped.** The operator's literal practice is to hedge only the
constituents of a cluster. That cut falls short of the power floor.

| Cut | Qualifying sessions | Floor |
|---|---|---|
| constituents only | 16 to 24 | 25 |

The shortfall was disclosed at plan time. The cut was registered as a stratum to
report rather than an arm to conclude from.

**What would unblock it.** Nothing, on this question.
[`next-steps.md`](next-steps.md) §2.1 is closed and a fourth trigger study over
these dates and these columns is ruled out. The successor question is §2.10. The
one deferred piece is `hedge_exposure`'s corrected prose control, to be
registered only when the book holds materially more parsed dates.

<a id="dependency"></a>
## Dependency

**The four questions were answered in the inverted order, and Q1 is now the link
that blocks the rest.** The bear sleeve was an existing operator practice before
any study touched it. So the instrument and its size were the first things
written down, in `bear_deploy`, and both came back unmet. The trigger studies
came second, once there was a sleeve whose timing could be asked about.

That order left the programme with a sleeve it keeps, a size it holds as policy,
and no rule for when to put it on. Q1 blocks the rest because a hedge tested on
a trigger that carries no information is a hedge tested on noise. Q2 and Q3
cannot be read on trigger-selected dates until a trigger exists. The always-on
`D2` read does not stand in for Q2, because carrying the sleeve every day is
itself a reading at one trigger, the trigger "always".
[`next-steps.md`](next-steps.md) §2.10 names what would count as a candidate: a
signal the book does not carry yet, meaning hedge flow in the analysis or a live
exposure reading from the journal, censused before it is registered.

`bear_rewrap` is a structure study and not part of this programme, and
`calendar_hedge` imports its reconstruction and pricing machinery rather than
its verdict ([labels](arm-index.md#bear_rewrap),
[record](study-results/f3_structure/bear_rewrap.md)).

<a id="known-walls"></a>
## Known walls

| Wall | Size | What it binds |
|---|---|---|
| worst-decile deployed dates | 14 recorded, about 16 on the staged tabs | every worst-decile reading, `bear_deploy` `D2`, `calendar_hedge` `H2`, `vol_sleeve` Q2 |
| `calendar_hedge` fill, not date count | 31% of worst-decile dates fill, so a cell of 10 needs about 320 deployed dates, twice the book | `calendar_hedge` `H0` and `H2` |
| two missing option-history files | IWM 2026-05-29 245P and MSTR 2025-06-27 420C | `calendar_hedge` exits 1 at `R2` until they are refetched |
