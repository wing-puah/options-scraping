## bear_deploy — original D-rules (2026-08-11) + v4 re-read registration (2026-08-24)

Module: `scripts/backtest_study/f4_deployment/bear_deploy.py`. The study's
original pre-registration is `research/ml-plan.md` §addendum 2 (2026-08-11,
written before the study was built or run). It predates this folder, so the
study had no file here and could not go through `study_review`. This file
(1) carries the original D-rules verbatim so a run can be graded, and
(2) registers the 2026-08-24 v4 re-read: what happens to the
`docs/deployment-rules.md` §4 hedge-sleeve lines now that the v4 verdicts
reversed.

## Original pre-registered rules (quoted from ml-plan.md §addendum 2)

- **D1 — joint selection × exit.** Re-screen the identical pre-declared clause
  vocabulary on R replayed under `be_after: 0.50`. *SHIPS iff:* n ≥ 40, mean
  R ≥ 0, date-clustered CI lower bound > 0, positive in ≥ 2 years, both
  ex-window cuts ≥ 0, ≤ 2 clauses; survivor count read against the ~5%
  false-positive expectation.
- **D2 — hedge contribution.** *A hedge is REAL iff:* bear-sleeve mean R on
  the deployed book's worst-decile dates is > 0 AND the date-level sleeve
  correlation is < 0, both reproducing in ≥ 2 years.
- **D3 — sizing.** Sweep f ∈ {0, ¼, ½, 1}. *DEPLOYABLE AT f iff:* combined
  max drawdown and worst-date loss both no worse than f = 0, judged on dollars.
- **D4 — conditional pick.** Within-date paired, dates with ≥ 2 bear
  candidates. *ADOPTED iff:* mean within-date rank gain over the day's bear
  average has a date-clustered CI excluding zero AND every leave-one-date-out
  fold positive.
- "Nothing in this arm may change production config; a MET criterion produces
  a recommendation only." And: "The operator's instruction stands — bear
  positions are to remain deployable."

## 2026-08-24 v4 re-read — registered before grading and before any card edit

**Honesty note (this is a re-read, not a blind registration).** Three runs
were already read before this file was written: era v3 2026-08-15 (D2 MET,
D4 adopted `|delta| high first` — the basis of the §4 card lines), era v4
2026-08-22 (D2 MET, D3 MET, D4 NOT MET), era v4 2026-08-24 (D1–D4 all NOT
MET; D4 `|delta| high first` gain −0.004, CI [−0.166, +0.166]). What is
pinned here BEFORE the `study_review` grading and before any edit to
`docs/deployment-rules.md`: the decision rules, the binding basis, which run
is decisive, and the forward trigger. The forward trigger alone is blind —
its data does not exist yet.

### Pinned specifications

- **Decisive read**: the `study_review`-produced run on the era-v4 current
  exports (refreshed 2026-08-24 17:09, inputs `46cc19b`). The 2026-08-22 run
  is instability evidence, not a basis: D2 and D3 flipped MET → NOT MET on
  +50 rows / +9 dates. Graders should treat any criterion whose verdict
  flipped within-era as UNSTABLE rather than settled either way.
- **Binding basis for the pick line**: **R under the shipped PROD exit.** The
  bear-keyed `be_after: 0.50` exit (the study's Rb basis) was REVERTED
  2026-08-24 (commit `1e36dba`, rollback trigger fired), so Rb no longer
  describes what a deployed bear position returns. The study's D4
  exit-dependence block prints both bases; the R line binds.
- **Window status**: the v4 book is a CORRELATED-WINDOW re-read — new plays
  from a new prompt version on the same historical signal dates
  (2024-01 → 2025-08) as the v3 evidence. Pulling an unsupported card line is
  allowed on this window (it removes a claim); ADOPTING any new rule from it
  is not.
- **Operator pre-commitment (2026-08-24, before grading)**: *"i still want
  bear positions as hedge."* The §4 hedge sleeve itself is OPERATOR POLICY —
  consistent with the original addendum's "bear positions are to remain
  deployable" — and is EXEMPT from data-driven removal. No outcome below may
  delete §4; outcomes may only change which of its lines are evidence-backed
  vs policy-held.

### Decision rules (committed before the grading is read)

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

### Forward trigger (blind)

Re-run and re-grade through `study_review` when the v4 book holds ≥ 20
multi-candidate bear dates (the study's own D4 floor) among signal dates
AFTER 2026-08-11 — genuinely new data, outside the correlated window. D2 is
re-read then too if ≥ 20 deployed/bear overlapping new dates exist (its
internal floor). On that read — and only then — adoption of a pick rule is
permitted again.

### Ship criteria

None. This registration ships no rule and touches no config. Its outcomes
are the RE-1…RE-4 edits to `docs/deployment-rules.md` §4 exactly as
committed above, applied after the grading and logged in
`research/current.md`.
