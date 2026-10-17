## hedge_sizing — the bear sleeve's deployment criteria (D1–D4), and the v4 re-read of the card lines they backed

<!-- brief:start -->
## In brief

> Plain-language brief for readers. The registration below is the binding text; where the two differ, the registration wins. `study_review` cuts this brief out before grading, so the blind graders never see it.
> Latest outcome: D1–D4 all `NOT MET` — 2026-09-28 · [record](../../study-results/f5_hedging/hedge_sizing.md).
> Nothing else in this brief is a result.

**The question**

The file holds two registrations. The original (2026-08-11) asks whether a bear hedge sleeve is deployable, and on what terms. Four criteria, D1 to D4, carry it. The v4 re-read (2026-08-24) asks what happens to the `docs/deployment-rules.md` [§4](../../../docs/deployment-rules.md#s4) hedge-sleeve lines now that the v4 verdicts reversed.

The study measures a proxy, not a held hedge. It cannot see margin, assignment or the operator's real sizing. It speaks about bear spreads, not naked puts. The operator pre-committed that bear positions stay as a hedge, so no outcome deletes §4.

**What it compares**

The study has criteria, not arms. [hedge_sizing D1 to D4](../../arm-index.md#hedge_sizing) are not `ARM D`. Each original criterion has a pass rule, quoted below. Four decision rules, RE-1 to RE-4, govern the §4 lines.

| Object | What it tests | Kind |
|---|---|---|
| hedge_sizing D1 | Joint selection × exit: the pre-declared clause vocabulary re-screened on R replayed under `be_after: 0.50` | criterion |
| hedge_sizing D2 | Hedge contribution: does a bear sleeve pay on the deployed book's worst-decile dates | criterion |
| hedge_sizing D3 | Sizing: a bear sleeve added at fraction f ∈ {0, ¼, ½, 1} of standard size | criterion |
| hedge_sizing D4 | Conditional pick: does `|delta| high first` beat the day's bear average on dates with at least 2 bear candidates | criterion |
| hedge_sizing RE-1 | The pick line: "rank by `|delta|` DESCENDING, take the closer-to-money one" | decision rule |
| hedge_sizing RE-2 | The far-OTM prohibition: "do not buy the cheap far-OTM put" | decision rule |
| hedge_sizing RE-3 | The size line: "≤ ½ a normal position" | decision rule |
| hedge_sizing RE-4 | The sleeve's evidence label in §4 | decision rule |

**How it is judged**

**Basis for the v4 re-read.**

- The decisive read is the `study_review` run on the era-v4 exports refreshed 2026-08-24 17:09 (inputs `46cc19b`).
- The 2026-08-22 run is instability evidence, not a basis. D2 and D3 flipped from MET to NOT MET on +50 rows and +9 dates. A criterion whose verdict flipped within an era counts as UNSTABLE.
- The pick line binds on R under the shipped PROD exit. The bear `be_after: 0.50` exit was reverted on 2026-08-24.
- This is a correlated-window re-read. Pulling an unsupported card line is allowed. Adopting a new rule from it is not.

**Original criteria, as quoted in the registration.**

1. D1 SHIPS iff all of these hold:
   - n ≥ 40 and mean R ≥ 0
   - date-clustered CI lower bound > 0
   - positive in ≥ 2 years
   - both ex-window cuts ≥ 0
   - ≤ 2 clauses
2. D2 is REAL iff bear-sleeve mean R on the book's worst-decile dates is > 0 and the date-level sleeve correlation is < 0. Both must reproduce in ≥ 2 years.
3. D3 is DEPLOYABLE AT f iff the combined book's max drawdown and worst-date loss are both no worse than f = 0, judged on dollars.
4. D4 is ADOPTED iff the mean within-date rank gain has a date-clustered CI excluding zero and every leave-one-date-out fold is positive.

**Decision rules for the §4 lines.**

- RE-1: `|delta| high first` must pass the D4 rule on the R (PROD) basis. Pass means RE-AFFIRMED. Otherwise the line is PULLED and the pick is operator discretion. A null does not flip the preference.
- RE-2: the prohibition is RETAINED if `|delta| low first` has a point gain ≤ 0 on R, or a CI that spans zero. It is PULLED only if the gain is > 0 with the CI excluding zero.
- RE-3: the size line is POLICY-HELD and unchanged by any outcome. D3 is recorded as evidence status only.
- RE-4: if D2 is NOT MET, §4 gains a sentence. The sleeve is held as operator policy, and the v4 hedge-contribution read is unsupported and unstable within the era. If D2 is MET, the evidence-backed wording stays with the same caveat.

The registration quotes its expectation up front. D1 is most likely NULL, D2 is most likely to return something, and D4 is a coin-flip.

**Possible verdicts**

| Token | What it means |
|---|---|
| `MET` | The criterion's pass rule holds in the decisive read |
| `NOT MET` | The pass rule fails |
| RE-1 `RE-AFFIRMED` or `PULLED` | The pick line stays, or the bullet is replaced |
| RE-2 `RETAINED` or `PULLED` | The prohibition stays with a v3-era citation, or is removed |
| RE-3 `POLICY-HELD` | The size line never changes |

**What could ship**

Nothing ships and no config changes. The outcomes are the RE-1 to RE-4 edits to §4, applied after grading. A forward trigger re-runs the study when the v4 book holds at least 20 multi-candidate bear dates after 2026-08-11. A pick rule may be adopted again only on that read.

**What this study cannot tell you**

- Whether a held hedge pays. Equal-weighted concurrent dollars stand in for it.
- Whether naked puts work. Bear rows are mostly spreads.
- Whether to delete the §4 sleeve. It is operator policy and exempt from removal.
- Anything adoptable from this window. It is a correlated-window re-read.
- Whether the v4 D2 and D3 results are stable. They flipped within the era.

---
<!-- brief:end -->

_Registered 2026-08-11._
_Renamed from `bear_deploy` on 2026-09-08, after the question it answers in `scripts/backtest_study/f5_hedging/README.md`. No gate, arm, bar or verdict changed._

Module: `scripts/backtest_study/f5_hedging/hedge_sizing.py`.

This file carries two registrations, kept separate so a run can be graded
against either.

1. **The original D-rules** (2026-08-11), first written as `research/ml-plan.md`
   §addendum 2, before the study was built or run. That file predates this
   folder, so the study had no file here and could not go through
   `study_review`. It was removed on 2026-08-24 once its three studies had
   files of their own — its text is in git at
   `git show 42b5e46:research/ml-plan.md` — and its other two arms live in
   [`../f1_selection/signal/ml_combination.md`](../f1_selection/signal/ml_combination.md) and
   [`../f1_selection/bear/bear_arm.md`](../f1_selection/bear/bear_arm.md). The D-rules
   are quoted here verbatim.
2. **The v4 re-read**, registered 2026-08-24. Everything belonging to it sits
   under the "v4 re-read" sub-heading below, or is dated inline.

## Question

Two questions, registered on two dates.

- **The original (2026-08-11)** asks whether a bear sleeve is deployable, and
  on what terms. Four criteria carry it: D1 joint selection × exit, D2 hedge
  contribution, D3 sizing, D4 conditional pick — each quoted in full under
  "Bar for a candidate".
- **The v4 re-read (2026-08-24)** asks what happens to the
  `docs/deployment-rules.md` §4 hedge-sleeve lines now that the v4 verdicts
  reversed.

## What this is NOT

Three limits bound what this study may say. Two are inherited from the original
addendum; the third the operator fixed.

**Not a measurement of a held hedge.** Inherited caveat, quoted:

> Standalone pricing still cannot see margin, assignment, or the operator's
> real position sizing; D2 approximates a hedge as equal-weighted concurrent
> dollars, which is a *proxy* for, not a measurement of, a held hedge.

The other two limits:

- **Not a statement about naked puts.** The caveat's second half — bear rows
  are 88% `bear_put_spread` and only 6 are naked `long_put`, so conclusions are
  about bear *spreads* — is carried in
  [`../f1_selection/bear/bear_arm.md`](../f1_selection/bear/bear_arm.md) and binds here
  too.
- **Not a case for deleting the §4 sleeve.** Operator pre-commitment
  (2026-08-24, before grading): *"i still want bear positions as hedge."* The
  §4 hedge sleeve itself is OPERATOR POLICY — consistent with the original
  addendum's "bear positions are to remain deployable" — and is EXEMPT from
  data-driven removal. No outcome may delete §4; outcomes may only change which
  of its lines are evidence-backed vs policy-held.

## Population and basis, fixed here

The v4 re-read pins its basis before the grading is read: which run decides,
which return basis binds, and what this window may support.

- **Decisive read.** The `study_review`-produced run on the era-v4 current
  exports (refreshed 2026-08-24 17:09, inputs `46cc19b`). The 2026-08-22 run is
  instability evidence, not a basis: D2 and D3 flipped MET → NOT MET on +50
  rows / +9 dates. Any criterion whose verdict flipped within-era counts as
  UNSTABLE, not settled either way.
- **Binding basis for the pick line: R under the shipped PROD exit.** The
  bear-keyed `be_after: 0.50` exit (the study's Rb basis) was REVERTED
  2026-08-24 (commit `1e36dba`, rollback trigger fired), so Rb no longer
  describes what a deployed bear position returns. The study's D4
  exit-dependence block prints both bases; the R line binds.
- **Window status: a CORRELATED-WINDOW re-read.** The v4 book is new plays from
  a new prompt version on the same historical signal dates (2024-01 → 2025-08)
  as the v3 evidence. Pulling an unsupported card line is allowed on this
  window (it removes a claim); ADOPTING any new rule from it is not.

## Plan-time observations, disclosed

**The v4 re-read is not a blind registration.** Three runs were already read
before this file was written.

| Era | Date | D1 | D2 | D3 |
|---|---|---|---|---|
| v3 | 2026-08-15 | — | MET | — |
| v4 | 2026-08-22 | — | MET | MET |
| v4 | 2026-08-24 | NOT MET | NOT MET | NOT MET |

D4 (adoption of `|delta| high first`): v3, 2026-08-15 — adopted, the basis of
the §4 card lines. v4, 2026-08-22 — NOT MET. v4, 2026-08-24 — NOT MET, gain
−0.004, CI [−0.166, +0.166].

What is pinned here BEFORE the `study_review` grading and before any edit to
`docs/deployment-rules.md`: the decision rules, the binding basis, which run is
decisive, and the forward trigger. The forward trigger alone is blind — its
data does not exist yet.

## Bar for a candidate

The original addendum fixes four criteria, each quoted below as written.

- **D1 — joint selection × exit.** "B1 screened on E under the PROD exit; B2
  then changed the exit. The pair was never evaluated together. Re-screen the
  identical pre-declared clause vocabulary on **R replayed under
  `be_after: 0.50`** — what a deployed bear position actually returns.
  *SHIPS iff:* n ≥ 40, mean R ≥ 0, date-clustered CI lower bound > 0, positive
  in ≥ 2 years, both ex-window cuts ≥ 0, ≤ 2 clauses. Survivor count is read
  against the ~5%-of-tested false-positive expectation, as in B1."
- **D2 — hedge contribution.** *A hedge is REAL iff:* bear-sleeve mean R on
  the deployed book's worst-decile dates is > 0 AND the date-level sleeve
  correlation is < 0, both reproducing in ≥ 2 years.
- **D3 — sizing.** "Sweep an added bear sleeve at fraction f ∈ {0, ¼, ½, 1} of
  standard size. *DEPLOYABLE AT f iff:* the combined book's max drawdown and
  worst-date loss are both no worse than f = 0, judged on dollars."
- **D4 — conditional pick.** Within-date paired, dates with ≥ 2 bear
  candidates. *ADOPTED iff:* mean within-date rank gain over the day's bear
  average has a date-clustered CI excluding zero AND every leave-one-date-out
  fold positive.

### v4 re-read (2026-08-24)

Four decision rules, committed before the grading is read. Each fixes in
advance what happens to one `docs/deployment-rules.md` §4 line.

- **RE-1 — the pick line** ("rank by `|delta|` DESCENDING, take the
  closer-to-money one"): RE-AFFIRMED iff `|delta| high first` passes the
  original D4 rule (paired date-clustered CI > 0 AND every LOO fold > 0) on
  the R (PROD) basis in the decisive read. Otherwise PULLED: the bullet is
  replaced with "no ranking preference is supported on v4; pick is operator
  discretion (v3 evidence recorded in `research/deployment-evidence.md`)".
  A null result does NOT flip the preference to the opposite pick.
- **RE-2 — the far-OTM prohibition** ("do not buy the cheap far-OTM put"):
  RETAINED (with a v3-era citation) iff `|delta| low first`'s point gain is
  ≤ 0 on the R basis, or its CI spans zero. PULLED only if v4 actively
  contradicts it: `|delta| low first` gain > 0 with CI excluding zero on the
  R basis. The `score_total` half of that bullet is governed by §6
  independently and is out of scope here.
- **RE-3 — the size line** ("≤ ½ a normal position"): POLICY-HELD and
  unchanged by any outcome. It was never D3-backed (v3 D3: NOT MET at any
  size). The decisive read's D3 result is recorded as evidence status only.
- **RE-4 — the sleeve's evidence label**: if D2 is NOT MET in the decisive
  read, §4 gains an explicit sentence that the sleeve is held as operator
  policy and the v4 hedge-contribution read is unsupported and within-era
  unstable; if MET, the evidence-backed wording stays, carrying the same
  instability caveat.

## Anti-tuning

**Pre-registered expectation** — the original's anti-HARKing paragraph, quoted
so a post-hoc story cannot be told afterwards:

> D1 modal outcome NULL (the exit shifts the mean ~+0.04; the level problem is
> ~0.5 deep). D2 is the arm most likely to return something, and is also the
> only one that would justify deploying a negative-expectancy structure. D4 is
> a genuine coin-flip.

## Ship criteria

None. This registration ships no rule and touches no config. Its outcomes are
the RE-1…RE-4 edits to `docs/deployment-rules.md` §4 exactly as committed
above, applied after the grading and logged in `research/current.md`.

Quoted from the original addendum: "Nothing in this arm may change production
config; a MET criterion produces a recommendation only." And: "The operator's
instruction stands — bear positions are to remain deployable."

### Forward trigger (blind)

Re-run and re-grade through `study_review` when the v4 book holds ≥ 20
multi-candidate bear dates (the study's own D4 floor) among signal dates
AFTER 2026-08-11 — genuinely new data, outside the correlated window. D2 is
re-read then too if ≥ 20 deployed/bear overlapping new dates exist (its
internal floor). On that read — and only then — adoption of a pick rule is
permitted again.

## Build notes

*Not part of the registration — implementation, not commitment.*

- **D1's window check was fixed 2026-08-24 to match what is registered here.**
  "Both ex-window cuts ≥ 0" was implemented as
  `all(v >= 0 for v in cuts.values() if v == v)`; an ex-window cut with no rows
  computes as nan, the nan was filtered out of the `all()`, and the check
  passed VACUOUSLY — on precisely the subsets that lie entirely inside a
  dominant window, which is the population ground rule 4 exists to reject.
  `bear_arm`'s B1, the criterion D1 mirrors, already failed closed. Now
  `cuts_pass()`, pinned by `tests/test_studies_hedge_sizing.py`. **No recorded
  verdict changes**: D1 has returned 0 survivors on every run, so nothing was
  ever admitted through the vacuous branch.
