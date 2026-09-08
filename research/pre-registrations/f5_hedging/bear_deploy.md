## bear_deploy — the bear sleeve's deployment criteria (D1–D4), and the v4 re-read of the card lines they backed

_Registered 2026-08-11._

Module: `scripts/backtest_study/f4_deployment/bear_deploy.py`. The study's
original pre-registration is `research/ml-plan.md` §addendum 2 (2026-08-11,
written before the study was built or run). It predates this folder, so the
study had no file here and could not go through `study_review`. That document
was removed on 2026-08-24 once its three studies had files of their own — its
text is in git, `git show 42b5e46:research/ml-plan.md` — and its other two arms
live in
[`../f1_selection/ml_combination.md`](../f1_selection/ml_combination.md) and
[`../f1_selection/bear_arm.md`](../f1_selection/bear_arm.md).

This file therefore carries two registrations. The first is the original
D-rules, quoted here verbatim so a run can be graded. The second, registered
2026-08-24, is the v4 re-read; everything belonging to it either sits under a
"v4 re-read" sub-heading or is dated inline.

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
  [`../f1_selection/bear_arm.md`](../f1_selection/bear_arm.md) and binds here
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
  rows / +9 dates. Graders should treat any criterion whose verdict flipped
  within-era as UNSTABLE rather than settled either way.
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

**Honesty note: the v4 re-read is a re-read, not a blind registration.** Three
runs were already read before this file was written.

- **era v3, 2026-08-15** — D2 MET, D4 adopted `|delta| high first`, the basis
  of the §4 card lines.
- **era v4, 2026-08-22** — D2 MET, D3 MET, D4 NOT MET.
- **era v4, 2026-08-24** — D1–D4 all NOT MET; D4 `|delta| high first` gain
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
  `cuts_pass()`, pinned by `tests/test_studies_bear_deploy.py`. **No recorded
  verdict changes**: D1 has returned 0 survivors on every run, so nothing was
  ever admitted through the vacuous branch.
