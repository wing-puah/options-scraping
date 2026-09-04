# Archive 17 — 2026-08-22 → 2026-08-27: vocabulary, `concurrency_correlation`, the v4 refresh, `bear_deploy`

_Status: historical (covers 2026-08-22 → 2026-08-27). Superseded / qualified by: [current.md §2026-08-31 `hedge_exposure`](../current.md) — the `bear_deploy` D3 verdict graded here still stands, but it was read on a close-bucketed curve that UNDERSTATES this book's max drawdown by 40.2%, now recorded as a limitation of its measurement basis in [deployment-evidence.md](../deployment-evidence.md). Live record: [current.md](../current.md)._

Covers 2026-08-22 through 2026-08-27. "POWER STOP" was RETIRED in favour of
UNDERPOWERED and `ml_combination`'s v4 debut fixed. The operator's read that
"more deployed = works less" was reframed — the ladder's DEPTH is not the
problem, the book's SIZE is unmeasured — and `concurrency_correlation` was
pre-registered (module still unwritten at the close of this volume). The
2026-08-24 v4 refresh produced the first rollback-trigger census (`be_after`
REVERTED, LVOL cleared-but-held), the first calibration of the credit book,
and the `exit_mechanism_study` repair; the same-day two-analyst pass found
the ARM P "candidate" OFF-BASIS. `bear_deploy` was registered and graded
(pick line PULLED, sleeve relabelled operator policy, far-OTM prohibition
retained) and its D1 window check made fail-closed. Documentation work: ARM
labels declared STUDY-LOCAL with `arm-index.md` indexing every one;
pre-registrations consolidated onto one template; `ml-plan.md` split into
three per-study registrations and deleted. The volume closes with the
2026-08-27 full-suite re-run on the 140-date backfilled book, the one HARD
row that blocked the debit exit family, and the two fixes (defective reports
repaired; the HYG boundary-tie classifier widened) that unblocked it.

Sections are in log order.

---

## 2026-08-22 — "POWER STOP" RETIRED in favour of **UNDERPOWERED**, and `ml_combination`'s v4 debut FIXED: it died on two columns the v4 bump had already dropped

**Terminology.** The under-the-floor state is now printed as **UNDERPOWERED**
everywhere code prints it, and the mechanism that produces it is a **power
floor** — vocabulary five modules (`book.py`, `macro_event_study`,
`mech_regime_recut`, `bear_position_study`, `regime_gap_reread`) were already
using. `calendar_hedge.POWER_STOP_MIN_N` is now `MIN_N_TO_READ`, which says
what the constant does: below it, the cell is not read.

This finishes a migration `financed_spread` amendment 1 had started for F4
alone while F0–F3 kept the older token "their published reports already
quote". `underpowered_token(shape)` is gone with the split it encoded; the
module exports a single `UNDERPOWERED` constant, and `VERDICTS` no longer
carries the same state twice.

**What was deliberately NOT rewritten.** Every verbatim record — this log,
`research/study-results/`, `research/pre-registrations/`, `research/archive/`,
the dated index rows in `README.md` — still says POWER STOP / POWER-STOPPED,
because those quote reports that literally printed that word. Rewriting them
would have falsified the quote for a change in wording only. `glossary.md`
carries the mapping: same state, retired name, older documents quoted as they
printed. Living prose (`glossary.md`, `next-steps.md`, `study-map.md`,
`catalog.py`) moved to the new wording.

Seven studies re-run to confirm the change is only wording: `calendar_hedge`,
`selection_order`, `financed_spread`, `staged_exit`, `portfolio_delta`,
`emission_timing`, `macro_event_study` — all exit 0, no verdict changed, no
number changed. 2,120 tests pass.

**`ml_combination` on v4: the first genuine casualty of the v4 column drop.**
The study had NO `-latest.txt` at all after the 2026-08-22 18:08 suite run —
it crashed, and the runner correctly refuses to promote a failed report, so
its absence was silent. The crash:

```
ValueError: window shape cannot be larger than input array shape
  sklearn HistGradientBoostingRegressor._bin_data -> sliding_window_view(distinct_values, 2)
  ml_combination.py:424  phase2_models -> M1
```

`NUM_SCORES` names `score_flow` and `score_dealer`. Those were dropped at the
v4 bump — `lib/era.py::V3_ONLY_COLS` already treats their absence as the
DEFINITION of the era — and they arrive 100.0% blank on every v4 row. The
study's own Phase-0 census printed exactly that (`score_dealer 100.0%`,
`score_flow 100.0%`) and the median imputer said so too (`Skipping features
without any observed values: [57 58]`); the elastic net tolerated the all-NaN
columns, HistGBM's binner did not — zero distinct values, and a 2-wide window
over zero values raises.

Not a thin-era refusal: the era is fine (78 book dates, 517 rows, 4 test
blocks). An era-blind feature list, in the one study that hardcodes the two
columns the era is detected BY.

Fix: `design_matrix` drops columns with no observed value ONCE, on the whole
book — never per fold, so every fold and the permutation-importance pass keep
the same columns, and emptiness is a property of the export rather than of any
label. The Phase-0 census builds the undropped matrix so it can still NAME
what it dropped, and now prints `era-absent features (2, ...): score_dealer,
score_flow` above the missingness table. The fold-local case (a merely-sparse
column absent from ONE training fold) is REFUSED with a diagnosis rather than
patched: dropping per fold would leave the ablation and importance numbers
built on feature sets that are not the same set, which is what this study
compares.

`ml_combination` now exits 0 on era v4. Its first v4 numbers are NOT read here
— B0 $34,744 / meanR +0.257 over 168 positions is the benchmark, and the
model arms are for the write-up, not for this note.

**Carry-forward, not run today: the `analyze_bt_queue.sh` backfill has 20
dates stuck as permanently-skipped partials.** Five of them (2025-02-07,
2025-05-19, 2025-06-05, 2025-08-01, 2025-08-19) ALREADY have their analysis
rows in the tab — 11–13 each — so `RETRY_PARTIAL=1` on queue b would duplicate
them, which the tab has no dedup to catch. The other fifteen wrote nothing and
are safe to retry. Verified today: 87 dates in the export, one run timestamp
per date, no duplicates yet.

## 2026-08-22 (late) — operator read "more deployed = works less": the ladder's DEPTH is not the problem, the book's SIZE is unmeasured. v3 day-level cuts DIED on v4; `concurrency_correlation` pre-registered

Operator observation, unprompted: *"the more that is being deployed, the less
it seems to be working."* Three passes — an inventory of what actually gates a
deployment today, a sweep of the existing record, and fresh cuts on both eras.
Populations named per figure; nothing here is a shipped rule.

**What gates a deployment today (inventory).** BINDING: the three §1 vetoes,
the §1.4 bear-debit redirect to the hedge sleeve, the A/B/C tier bucket (Tier C
is rejected), the §3 bull_put geometry (nominally binding, practically
unverified — `short_leg_delta` is not a `ROW_COLUMNS` column), and the
freshness/lookahead bound. ADVISORY ONLY: `DEPLOY_BUDGET = 3` (a LABEL — `rank()`
returns every survivor and `render()` printed all of them), the 0.25/2.50
exposure caps, duplicate-ticker exposure, and `judge()`. **No gate anywhere
counts concurrent open positions, and no gate raises the bar for the Nth play
of a day over the 1st.**

**Depth into the survivor list is FLAT, on both eras.** Deployed-order replay
of Tier A/B survivors, mean R by within-day rank:

| rank | v3 (795 rows / 118 dates) | v4 (517 rows / 78 dates) |
|---|---|---|
| 1 | +0.178 | +0.155 |
| 2 | +0.527 | +0.372 |
| 3 | +0.445 | +0.269 |
| 4-5 | +0.281 | +0.263 |
| 6+ | +0.323 | +0.257 |

Cumulative top-K on v3 plateaus at +0.364 (K=3) and is still +0.344 at K=8.
This does NOT contradict the recorded `top-1 +0.82 / top-3 +0.45 / all +0.14`
(607-row pooled book, 2026-07-19): that measures depth into the whole EMISSION
list, whose tail is Tier C and VETO, both negative every year (n=587 / n=145).
The tier gate does the work; the count cap inside the survivors does almost
none. **A tighter top-N is not the missing gate.**

**DEAD END, recorded so it is not re-found: two v3 day-level cuts that do not
survive the v4 bump.** Deployed top-3, mean R:

| cut | v3 | v4 |
|---|---|---|
| day had Tier A supply | +0.475 (n=137, 57 dates) | +0.247 (n=56, 27 dates) |
| Tier-B-only day | +0.182 (n=83, 33 dates) CI[-0.005,+0.369] | +0.257 (n=112, 45 dates) |
| model BULL + L-VOL | -0.050 (n=43, 15 dates) | +0.224 (n=102, 40 dates) |
| all other regimes | +0.465 (n=177, 75 dates) | +0.299 (n=66, 32 dates) |

On v3 the BULL+L-VOL cell held its sign in EVERY robustness cut (both halves,
2024 and 2025, real and tweak pricing, pre- and post-13c; date-clustered
p=0.0042), and all 15 such dates carried ZERO Tier A supply while emitting 4.87
Tier B per date against 1.24 elsewhere — i.e. the days with no A-tier flooded
the card with B-tier. It was a clean story and it is gone on v4: the gap is
+0.257 vs +0.247, and B-only days are now the MAJORITY (45 of 72 dates, vs 24%
on v3) because Tier A share collapsed across the bump (v3 131 A / 166 B; v4
58 A / 172 B). This is `v4_bridge`'s `LADDER UNVALIDATED ON v4 — ladder tier
mix shifted, chi2 p = 0.0000` claiming a victim. **No gate was built on it.**

**What the record already had, and what it never measured.** Established: tier
depth is monotone and C/VETO are negative every year; taking every emitted play
makes +$14.0k over three years against +$76k for the top-3 replay — the value
is in the triage, not the generation. Directional and independent:
`archive/08`'s discretionary book (468 closed trades) shows P&L per trade
falling monotonically with same-day trade count — 1/day +$119 · 2-3/day +$25 ·
4-6/day +$9 · 7+/day -$18 — with win rate FLAT at 51-59%, which is dilution
rather than worse reads on busy days. Already refuted: `portfolio_delta` ARM B
(128 -> 68 positions, paired gain -0.0164 R, FAIL) and ARM D (NON-MONOTONE /
FLAT, verdict NOISE) — both cut on DELTA CEILINGS. **Never studied at all:
concurrency vs outcome (census only — v3 median 8 concurrent, p90 29, max 48;
`account_sim` computes `n_open` and no report joins it to anything), and
correlation between concurrently held plays (every "correlation" in the repo is
sleeve-vs-book).**

**The live book, for context, not as evidence.** Open legs 3 -> 19 since May;
opening orders per week stepped rather than drifted, breaking the week of
2026-07-27 (19 in that week). Win rate rose over the ramp; average win / average
loss collapsed 1.53 -> 0.25. One TSM close is 48.8% of gross wins in the record
— strip it and the before/after profit factor is 0.76 vs 0.59, same direction,
much weaker. Both persisted deploy cards (08-14, 08-17) emitted 8 candidates,
100% Tier B, 100% `bull_call_spread`, in a BULL regime, with SNDK/MU/AMD on
both. The v4 book is long-only by construction (`positive 168 / NEGATIVE 0`,
`net-SHORT sessions 0`).

**Shipped today (production tier).** `render()` now treats the budget as a CUT
rather than a label: budgeted picks keep the full block, reserves collapse to
one line each under `### Reserve — N NOT for deployment` with prose saying a
reserve REPLACES an untradeable pick and is never a fourth position. `rank()`
is UNCHANGED — every survivor is still returned and still persisted, so the
record loses nothing; this is presentational, and it is presentational because
the card showed eight fully-specified plays under a 1-3/day rule. Also added:
an ADVISORY `**Book concentration:**` block (open positions, distinct tickers,
long/short/unpriced split, a warning when every priced position points the same
way, and a warning naming a budgeted pick whose ticker is already open). It
filters nothing and says so — no concurrency rule has been backtested.

**Registered, not run.** `research/pre-registrations/f4_deployment/concurrency_correlation.md`
— ARM N null band, ARM D0 descriptive, ARM C concurrency ceiling {5,8,12,20},
ARM K clustering ceiling {2,3,5} on direction / direction+sector / underlying,
ARM CK only if C and K clear independently. X4 (both eras, same sign, within
0.15 R) is expected to be the binding criterion, and X7 refuses any arm that is
a delta ceiling in disguise — ARM B and ARM D already failed that axis. The
module is NOT written; the plan exists before the code on purpose, and it
carries the dead-end table above so the study cannot re-find those cuts and
call them new.

**Three stale figures corrected.** (1) `deployment-evidence.md:39` quoted
`top-1/day 76% win / +0.35 mean`; the log says `+0.41` and by that file's own
precedence rule the log wins. (2) `selection_order.py` printed `changes only
7-14% of O0's taken positions` as a HARDCODED prose literal — the measured
census is 15%-24% (PRIMARY) / 11%-21% (SECONDARY); it now interpolates the
run's own `g0[n]["share"]` values, and the study-map verdict quoting the old
number was rewritten against the current report. Verdict, gates and every
numeric table are byte-identical to the pre-edit run. (3) The v3 claim that
`account_sim`'s rejected picks out-earn its taken ones REVERSES on v4 — the
sign flips in 7 of 8 frozen/compounding x PRIMARY/SECONDARY cells (PRIMARY:
taken +0.338 vs rejected +0.134 / +0.130); only one n=9 cell still favours
rejected. Corrected in the `account_sim` verdict, the `selection_order` verdict
and question, and `selection_order.py`'s docstring, which cited it as live
motivation.


## 2026-08-24 — v4 refresh evaluated: first rollback-trigger census (be_after REVERTED, LVOL cleared-but-held), the credit book calibrates for the first time, `exit_mechanism_study` repaired

Bare exports refreshed 2026-08-24 17:09; full suite re-run (25 reports, era v4,
git `c841a01`, exit 0, all recorded via `study-record`). Pooled book **567 rows
(real+tweak) / 87 dates** — up from 517/78 on 08-22. The provenance headers'
apparent shrink (results "1,212 rows" → "280 rows") is NOT a population change:
every header before today was a LINE count over `daily_price_csv`'s embedded
newlines — the exact `wc -l` hazard the 08-14 method note warned about, sitting
in the runner itself. `run.py` now counts CSV rows; every report recorded in
`research/study-results/` before 2026-08-24 overstates its input counts ~4×.

**Rollback-trigger census — the four shipped-rule forward triggers evaluated
for the FIRST time** (they were prose only; nothing computed "affected dates").
Pre-registered before the runs in `research/pre-registrations/f2_management/rollback_triggers.md`;
one definition of affected/arming in `scripts/backtest_study/lib/triggers.py`;
all census blocks additive. v4 is a CORRELATED-WINDOW re-read (new plays from a
new prompt version on the same historical signal dates) — registered as such,
with the operator's act-only-if-decisive reading committed before any number
was read.

| Trigger | Census | Outcome |
|---|---|---|
| bear-debit `be_after 0.50` | 92 arming rows / 53 dates ≥ floor 60 | condition three **FIRED** → **REVERTED** |
| LVOL tef-null (corrected gate) | 31 affected dates ≥ floor 25 | all four criteria PASS — **CLEARED, operator HELD the ship** |
| BEAR_HE trail | 1 affected date of 25 | decisively UNDERPOWERED — census is the result |
| credit sl-none | 0 fresh bull_put rows of 15 | UNDERPOWERED — comparator now printed by every credit run |

- **be_after REVERTED** (`structure_exit.enabled: false`, commit `1e36dba`).
  The trigger's three conditions on the arming rows: (a) total gain vs PROD
  **+$58** — pass, but ~zero against the −$54.4k → −$38.0k the rule shipped on;
  (b) mean-R on affected rows +0.0071 — pass; (c) per-year mean-R delta
  2024 +0.022 / **2025 −0.034 → FIRE**. Operator decision per the registration:
  revert. Block and evidence kept verbatim in config; re-entry only through a
  fresh registration. `docs/deployment-rules.md` loses the ratchet row.
- **LVOL tef-null cleared its corrected gate** (median among affected dates
  +0.023 > 0, total +5.70 > 0, halves +3.99/+1.71, no perturbation flip) — the
  first time the 07-22 corrected gate has been computable at all. Operator HELD:
  no urgency asymmetry (unlike BEAR_HE's bear-leg protection) justifies an
  in-window ship. Re-gate when the affected-date count includes genuinely new
  dates. The original six-criterion gate still reads 5/6 (`LOO median > 0`
  fails by construction) — `STAYS GATED` on that axis, unchanged.

**`exit_mechanism_study` repaired — its v4 "CALIBRATION FAILED" was false, and
its credit baseline was a retired rule** (commit `038cdc6`). The 08-22 banner's
14 mismatches were exactly the shipped overrides' own output (13 `be_stop` +
1 `trailing_stop`) — the failure mode diagnosed 08-14 and repaired in the three
gate-sharing studies, which this study never received. `calibrate()` now
classifies via the shared `lib/replay_basis.py` (extracted verbatim from
`exit_switch_mech_study`): debit **191 exact / 0 near / 16 superseded-basis /
0 HARD of 207**, banner reserved for HARD, `main()` stops on it. The worse
find: its local `CREDIT_PROD` still carried the pre-Attempt-13 `sl=1.00` —
every credit Δ since 07-13 was measured against a stop production had removed,
and the variant named "sl none" WAS production. Profiles now import from
`lib/book.py`, test-pinned against `config/backtest.yml`. The study's duplicated
replay engine (byte-identical to frozen `lib/harness.py`) is deleted in favour
of the import, so the whole f2 import chain sits under the pinned fixture. A
new `-credit` ARM joins `run --all`: **73/73 exact** — the v4 credit book is
single-basis and calibrates against shipped PROD for the first time
(`book.py`'s standing "no single credit PROD" caveat is not true of this era).

**Debit variant grid = the reactive null, re-confirmed on 207 rows.** Best
trail variant `trail .25 trig .75` Δ=+$1,679 but **Δ-LOO −$501** (one trade);
every other trail negative on both. Two non-reactive in-sample positives worth
recording as observations, NOT candidates (selected on the file they score):
`pt .75 no trail` Δ=+$4,354 / Δ-LOO +$1,734 — the second era in which a lower
profit target has looked good on debit — and `BE ratchet @.75` Δ-LOO +$806.
Credit side: `sl 1x (pre-Attempt-13)` Δ=−$3,468 / Δ-LOO −$3,853 vs PROD —
Attempt 13 re-confirmed hard, though on the correlated window, not the fresh
one the trigger names.

**Suite movers** (catalog verdicts refreshed for 20 studies, quoted verbatim):
- **`bear_deploy` REVERSED on v4**: D2 (hedge is real), D3, D4 all NOT MET —
  the shipped "take the closer-to-money bear" pick reads −0.004 vs the day
  average (CI [−0.166,+0.166]). That line sits in `docs/deployment-rules.md`
  on v3 evidence and now has no v4 support. No prereg file exists, so it
  cannot go through `study_review` as-is. **QUEUED (operator): register a
  re-read before re-affirming or pulling the card line.** Not acted on today.
- **`bear_rewrap` promoted `long_diag`**: all five criteria pass on v4
  (dR +0.353 CI [+0.121,+0.613], LOO min +0.275 over 61 folds, worst-decile
  meanR +0.902 CI [+0.275,+1.498] → P1 MET, P2 MET; bear sleeve −0.168 →
  −0.003). First full-conjunction pass for a bear wrapper — on a population
  `bear_position_study` still DEMOTEs on E (−0.288 at n=177, re-confirmed
  today). Candidate for independent-window confirmation, NOT shipped.
- **`emission_timing` ARM P sign-flipped**: v3 +0.054 (CI spans 0, null) →
  v4 **−0.205 CI [−0.379,−0.031] EXCLUDES 0**, reported as
  `STALE-ENTRY-PENALTY (CANDIDATE, NOT A SHIP)`. Two-analyst review run today
  (Disagreement log below).
- **`financed_spread` F4-d20**: the graded v3 candidate is UNDERPOWERED on v4
  (20 rows / 19 dates, under the G0 floor — no criterion evaluated). Review
  run today to decide carry/re-scope/shelve (Disagreement log below).
- `ml_combination` NULL again, gap wider (M3 out-of-fold −0.103 vs B0).
  `account_sim` FEASIBLE, and the v3 "rejected out-earn taken" reversal is now
  complete in all 8 cells. `staged_exit` null again, thinner (24/96 powered).
  `v4_bridge` unchanged (`LADDER UNVALIDATED ON v4`) — its catalog entry was
  two runs stale and factually wrong (claimed the study still aborts); fixed.
- `exit_switch_structure_study` STAYS GATED (1/6); new Q2 retention detail:
  the shipped BEAR_HE clause retains 0% of its gain outside its cell, the
  rejected bear_put trail 187% — the composition guard is doing its job.

**Infra shipped today** (all committed): the calibration repair + shared
classifier (`038cdc6`), `lib/triggers.py` + census blocks (`e54b4cd`), the
credit ARM + `make study-record` footer (`c841a01`), the be_after revert
(`1e36dba`), the Makefile study-surface consolidation (`d9f2853` — ONE
parameterized `study-chart CHART=account_sim|regime|compounding [ARM=structure]
[OPEN=1]` replacing seven targets, `study-check`, `RECORD=1` chaining,
`tests/test_makefile_targets.py` pinning every documented target), and
`lib/gex_snapshot.py` retired (`f3a7b2e`, zero importers, operator-confirmed).

### Same-day addendum — two-analyst review pass: the ARM P "candidate" is OFF-BASIS, and a new standing hazard

`study_review` ran on the two verdict-movers (`emission_timing`,
`financed_spread`; analyst A + B in parallel, validator, digest — artifacts in
`backtests/study_output/*-review-*-latest.md`). The pass earned its cost twice
over:

**CORRECTION — `emission_timing` ARM P is retracted from mover status.** Both
analysts, independently: the registration pins PRIMARY to `--era v3` (795 rows
/ 118 dates) and declares the v4 basis SECONDARY ("carries nothing… never
pooled"), and the report ran bare-era (v4) with no `--era v3` anywhere in its
command line. The 08-19 log had additionally marked ARM P a post-hoc watch for
NEW DATES ONLY. So the "STALE-ENTRY-PENALTY (CANDIDATE)" printed above is an
off-basis observation on overlapping dates — if anything, a sign flip between
eras on the same dates argues era-composition, not timing. The v3 NULL stands;
the catalog verdict is corrected. Analyst A also caught an internal
contradiction the study should fix: the ARM L headline says LAG-TOLERANT while
the report's own two tercile L=3 cells print `** CANDIDATE`.

**NEW STANDING HAZARD — the v4 book contains NO 2026 dates (BacktestResults
signal_dates end 2025-08-19), so every 2026-keyed robustness cut is a silent
no-op on it.** Analyst B proved it mechanically: all 17 `ex_2026_feb_apr`
values in `financed_spread` (and every one in `emission_timing`) are
numerically identical to their `ALL` column. Consequences: "positive every
calendar year" on v4 means 2024+2025 only; window-cut conjunctions collapse
from three cuts to two; and **`bear_rewrap`'s long_diag "passes all five" is
partly vacuous — 2026-alone is exactly the cut that killed `long_put` in the
original run, and this book cannot ask it.** Catalog caveated. Any v4
conjunction pass that cites year-stability inherits this until 2026 dates
land in the results export.

**Both underlying reports also violated their registrations in smaller ways**,
now on record: `financed_spread` prints `$` on substitution cell lines
("Dollars are never quoted on a substitution" — its own registration; queue a
report-format fix), and `emission_timing`'s G0/G3 headers both claim to run
first. Validator scope call left to this session: analyst A graded the
harness gates (G1/G2/G3) MET as code properties, B graded everything NOT
EVALUABLE on the wrong basis — resolved here as A's reading for CODE claims
(the gates are tested in `tests/`), B's for POPULATION claims (no criterion
verdict from an off-basis run is quotable).

**Disagreement log** (protocol requirement): `emission_timing` — G1/G2/G3
MET (A) vs NOT EVALUABLE (B), resolved as scoped above; A-only catches: the
ARM L internal contradiction, the G0/G3 header contradiction; B-only catch:
the `ex_2026` no-op. `financed_spread` — E2 MET (A) vs NOT EVALUABLE (B),
resolved for B (E2 is descriptive, "nothing is gated on it" — A answered a
non-evaluable item); B-only catches: the `$`-on-substitution violation, the
`ex_2026` no-op; A missed both, neither analyst wrong on any number
(validator source-checked every quoted figure; all matched).

**QUEUE updates from the pass:** (a) graded v3-registered studies re-run on
era v4 print criteria against the wrong PRIMARY — for a GRADED read, run
`--era v3`, or amend the registration with a dated v4-basis section first;
(b) `financed_spread` F4-d20 carry-question resolved as CARRY, UNCHANGED:
UNDERPOWERED on v4 (20 rows / 19 dates) is a census, not a refutation — the
graded v3 candidate still waits on its independent-window confirmation;
(c) fix the `financed_spread` $-print and `emission_timing` header/headline
contradictions (report-format, no numbers move).


## 2026-08-24 (late) — `bear_deploy` registered and graded: pick line PULLED, sleeve relabelled operator policy, far-OTM prohibition retained

The 08-24 suite refresh left `bear_deploy` REVERSED (D1–D4 all NOT MET) with
no way to grade it — its original registration is `ml-plan.md` §addendum 2
(2026-08-11), which predates `research/pre-registrations/`, so `study_review`
had no file to hand the analysts. Written today, before grading and before any
card edit: `research/pre-registrations/f4_deployment/bear_deploy.md` — the original D-rules
quoted verbatim, plus a v4 re-read section pinning the decisive read, the
binding basis (R under the SHIPPED PROD exit, since `be_after 0.50` was
reverted this morning), RE-1…RE-4 card-edit decision rules, and the operator
pre-commitment (stated 2026-08-24: *"i still want bear positions as hedge"*)
that the §4 sleeve is policy and EXEMPT from data-driven removal. The file's
honesty note names the three already-seen runs — this registration pins
decision rules, not blindness; only its forward trigger (≥20 multi-candidate
bear dates on post-2026-08-11 signals) is blind.

**Graded** (`study_review bear_deploy`, analysts opus ×2, validator sonnet;
fresh run 19:15 reproduced the 18:23 verdicts exactly — same inputs `46cc19b`):

- **D1–D4 all NOT MET — unanimous, every quoted number source-checked.** D4:
  0 of 10 rankers adopted (~0.5 expected by chance).
- **RE-1 FAIL → the §4 pick line is PULLED.** `|delta| high first` (the
  shipped "closer-to-money" rule) gain −0.004, CI [−0.166, +0.166], LOO min
  −0.045. §4 now reads "pick is operator discretion"; a null does not flip
  the preference, and no new ranker may be adopted from this correlated
  window (`iv_spread high first` +0.148 and `iv_pct high first` +0.110 are
  the eye-catchers the window rule exists for — CIs span zero anyway).
- **RE-2 MET → far-OTM prohibition RETAINED** with a v3-era citation:
  `|delta| low first` gain +0.017, CI [−0.133, +0.168] spans zero — v4 does
  not contradict the prohibition.
- **RE-3: size line unchanged** (policy-held; D3 has never been MET at any
  size — the one analyst disagreement, MET vs NOT EVALUABLE on how to grade a
  policy-fixed line, is vocabulary, not numbers; both confirmed the same D3
  figures).
- **RE-4 → sleeve relabelled OPERATOR POLICY** in §4: D2 NOT MET (tail R on
  worst-decile dates negative, correlation −0.087, tail positive in 0/2
  years) and within-era UNSTABLE (D2/D3 flipped MET → NOT MET between 08-22
  and 08-24 on +50 rows / +9 dates).

**Report defects the review surfaced** (analyst A catches, validator-confirmed;
queued, no numbers move): (a) D3's DEVIATION prose hardcodes "−0.345 vs day
average" for the widest-max_loss picker — a v3-era figure sitting in the
STUDY'S OWN PROSE while the same report's D4 table prints −0.083; the
never-hardcode rule, in prose form; (b) D2's pass rule evaluates worst-DECILE
dates but its ≥2-years reproduction check evaluates worst-QUARTILE dates —
two different cuts feeding one criterion, silently; (c) the D4 table doesn't
name its basis (Rb) in its header, which is what let the binding-basis gate
go NOT EVALUABLE. All three are report-format/prose fixes in
`bear_deploy.py`, none touch a computed number.

Card edits applied to `docs/deployment-rules.md` §4 exactly per the
registration. Artifacts: `backtests/study_output/bear_deploy-review-{analyst-a,
analyst-b,validator}-latest.md` + `bear_deploy-digest-latest.md`. The
study-results record for era v4 · inputs 46cc19b (18:23 run) stands — the
19:15 grading run reproduced it bit-for-bit, no new append.

---

## 2026-08-24 (docs) — ARM labels are STUDY-LOCAL and STAY single letters; `research/arm-index.md` indexes every one, BY STUDY

**The problem, stated precisely.** It is not that arms are letters — it is that
looking one up costs a repo-wide grep. `ARM P` has FOUR owners: `emission_timing`
(persistence — repeat vs first emission), `macro_event_study` (H2 outcomes by
event proximity), `bear_giveback` (the `be_after` production baseline) and
`bear_rewrap` (portfolio contribution, P1/P2). `grep "ARM P"` returns ~200 hits
across `scripts/`, `research/` and `backtests/study_output/`, and the majority
are not definitions at all — they are one study CITING another's arm without
naming it: `emission_timing`'s `ARM C` mentions all mean `next_day_move`'s;
`financed_spread` and `selection_order` cite `calendar_hedge`'s `ARM S`;
`concurrency_correlation` cites `portfolio_delta`'s `ARM B`/`ARM D` while its
own arms are C/K/CK/D0/N. Resolving a cited letter against the file you are
reading gives the WRONG arm.

**Renaming was considered and rejected.** Letters stay. A pre-registration is
immutable; `scripts/study_review/`'s analysts grade against the label strings
the reports printed; `current.md`, `archive/`, `study-results/` and the
committed `*-review-*.md` gradings all quote them. The audit chain is worth more
than label prettiness, and the actual need was lookup speed, not new names.

**What shipped:**

1. **`research/arm-index.md`** (new) — every arm label with its owning study,
   grouped BY STUDY in the four family folders' order (①–④, then studies still
   queued with no module yet) with an up-front collisions note, so everything
   a study owns reads in one place. Covers the `ARM <letter>` arms, the
   non-`ARM`-form arms (`selection_order` O0–O4/O1b, `financed_spread` F0–F4
   and its F1/F2 collision with `account_sim`'s unrelated 1-contract-floor
   F1/F2), and the labels that only look like arms (G* gates, `calendar_hedge`'s
   H0–H5 criteria vs `macro_event_study`'s H1–H4 hypotheses, `bear_deploy`'s
   D1–D5).
2. **`tests/test_arm_index.py`** — every `ARM <label>` token in a live study
   module or pre-registration must be in the index (a newly registered arm
   cannot skip it), and the four `ARM P` owners are pinned; descriptions are
   NOT tested — operator's own words.
3. **Digest pages** — `scripts.study_map.build` now renders each
   `backtests/study_output/<study>-digest-latest.md` to
   `site/<study>-digest.html` (hyphenated) and the study's card on
   `site/study-map.html` links it — the plain-language write-up was
   previously stranded in a gitignored directory no reader visits.
4. **Doc touch-ups** — `glossary.md` §9 ARM entry + §11 see-alsos,
   `pre-registrations/README.md`'s "Arm labels" section (the one forward
   rule: qualify every citation with its study), `research/README.md`'s
   pointer, and the `CLAUDE.md` `research/` row — none mention any lookup
   tooling; the index is for reading, and the reader's surfaces are
   `site/study-map.html` and `research/`.

## 2026-08-24 — Pre-registrations consolidated to one template; study_review dry-run clobbered two reviews' artifacts

All 14 files under `research/pre-registrations/` reformatted to a single
template (editorial only — no gate, bar, arm, or verdict changed meaning):
`## <slug>` heading + `_Registered <date>._` line, canonical section names,
and every dated AMENDMENT / wording-correction section folded into the section
it amends (superseded rules removed as live text; git history carries what
changed and when). README gained the template spec + two legend rows
(Ship criteria; POWER-STOPPED→UNDERPOWERED, re-homed from financed_spread);
CLAUDE.md's immutability sentence now reads commitments-immutable /
file-consolidatable. `load_pre_registration` verified on the amended studies;
the macro_event_study and rollback_triggers filename-fallback extractions are
incidentally fixed.

INCIDENT: the verification step `study_review <s> --skip-run --dry-run`
OVERWRITES the `-review-*/-digest-latest.md` artifacts with 51-byte
placeholders (--dry-run does not guard those writes). Recovered byte-exact
from session transcripts: `financed_spread-digest-latest.md`,
`macro_event_study-review-validator-latest.md`. LOST (now carrying dated
loss notes in place): financed_spread analysts A/B + validator,
macro_event_study analysts A/B + digest. Verdicts survive in this log's
2026-08-19 disagreement-log entry (all ACCEPTED as written); reports intact.
Follow-up candidates: make --dry-run write to a scratch stem, and regrade via
`study_review <s> --skip-run` only if the full artifacts are wanted again.

## 2026-08-24 (docs) — `ml-plan.md` split into three per-study pre-registrations and DELETED

The last pre-registration living outside `research/pre-registrations/`. It was
written 2026-08-11 as one document covering THREE studies, before that folder
existed, so `study_review` — which globs `<family>/<study>.md` — could not find
it: `bear_deploy` got a carried-over file on 08-24, while `ml_combination` and
`bear_arm` remained ungradable except by hand-passing `--pre-reg`.

Split (editorial only — every gate, bar, arm and verdict carried across as a
VERBATIM quote, nothing reworded): `pre-registrations/f1_selection/ml_combination.md`
(ground rules 1–7, Phases 0–5, the ship decision, the kickoff's three settled
choices) and `pre-registrations/f1_selection/bear_arm.md` (§Kickoff addendum,
B1 selection + B2 exit, the standalone-vs-hedge caveat). `f4_deployment/bear_deploy.md`
already held §addendum 2's D-rules. `ml-plan.md` itself is DELETED rather than
left as a pointer — two copies of one commitment is how they drift; its text is
in git at `42b5e46`. Links in `archive/09` retargeted to the successor files
(historical prose keeps the old NAME, as history); `research/README.md` row
dropped, root README row repointed; the three module docstrings, comments and
`hdr()` citation lines now name the registration path they are graded against.

`arm-index.md` gained both studies, and with them a real collision: `bear_arm`'s
`B1`/`B2` are CRITERIA (selection conditioning, exit fit) while
`ml_combination`'s `B1`/`B2` are regression BASELINES — same document registered
both on the same day, meaning nothing alike. `B0`/`M1`/`M2`/`M3` indexed too.

Both new files are status `run`, not `graded`: no `-review-*` artifacts exist
for either. They are now gradable, but a bare `study_review` would re-run
against the CURRENT era while the recorded verdicts are v3 — reproducing them
needs `--era v3`, and the criteria are era-agnostic by construction (CIs, cuts
and sign stability, never a stored figure). Both files say so in Build notes.

SEPARATE FINDING, not fixed here: `tests/test_arm_index.py:54` uses
`PREREGS.glob("*.md")`, not `rglob`. Since the family-folder reorg every
registration sits in `fN_*/`, so the arm-index coverage test has been checking
ZERO pre-registrations — it silently only sees study modules. The index entries
above were added by hand; the one-word test fix is its own change.

## 2026-08-24 (fix) — `bear_deploy` D1's window check was FAIL-OPEN on an empty ex-window cut

Found while answering "what causes a wrong compute if everything is
deterministic". The answer is: a deterministic bug returns the same wrong
number every run and produces an internally consistent report, which is exactly
what a report-reading grader passes.

The same pre-registered criterion, two encodings that disagreed:

    bear_arm.py    B1: all(c is not None and c["mean"] >= 0 ...)   empty cut -> FAILS
    bear_deploy.py D1: all(v >= 0 for v in cuts.values() if v == v) empty cut -> WAIVED

`fmean([])` returns nan, and the `if v == v` filter dropped it OUT of the
`all()`, so "both ex-window cuts ≥ 0" was satisfied by a cut that contained no
rows. A cut empties exactly when the subset lies WHOLLY inside Mar–Apr 2025 or
Feb–Apr 2026 — the window-dominance case ground rule 4 exists to reject. The
guard failed open on the population it was written to kill. D1 registers itself
as re-screening "the identical pre-declared clause vocabulary" as B1, so the
two were supposed to be comparable; they were not.

Fixed: `cuts_pass()` in `bear_deploy.py`, `all(v == v and v >= 0 ...)`, pinned
by `tests/test_studies_bear_deploy.py` (6 cases, including the end-to-end shape
— rows dated 2025-03/2025-04 producing the empty cut — and a test asserting B1
and D1 agree, so neither drifts again). NO recorded verdict changes: D1 has
returned 0 survivors on every run, so nothing was ever admitted through the
vacuous branch. Had one been, the report would have printed `mar_apr_2025:nan`
beside a PASS — visible, but only to a reader who knows nan means "waived".

Audited the three other `v == v` uses in `backtest_study/`: `emission_timing`
(NaN excluded BEFORE the tercile cut, excluded rows printed as their own cell),
`ml_combination:557` (display filter on a within-structure correlation) and
`portfolio_delta:843` / `account_sim:933` (a display sort with an explicit
empty branch, and a mean helper). All legitimate; the gate was the only
fail-open one.

STANDING LIMIT this exposes, for the record: `research/replication-protocol.md`
grades the printed REPORT, never the raw data — `.claude/agents/research-analyst.md`
forbids re-deriving a number that is not printed, and only `account_sim` is
handed a positions CSV (which neither analyst has ever used; both A/B tables
are headed "read from report"). So the protocol catches mislabelling, silent
non-evaluation, internal contradiction, era/basis mismatch and stale prose — it
demonstrably has, four times — but CANNOT catch a wrong-but-stable computation
that is correctly labelled from correct inputs. That class needs a test, which
is what this entry adds. Call it an audit, not a replication.

## 2026-08-27 — full-suite re-run on refreshed exports (140-date backfilled book); one HARD row blocks the debit exit family

Exports refreshed 20:34 (485 real / 1,111 proxy / 1,893 analysis; 140 signal
dates 2024-01-10 → 2025-11-04). The growth 87 → 140 dates since 08-24 is
BACKFILL: 49 dates / 172 real rows sit BEFORE the v3 window start
(2024-06-17); there are still ZERO 2026 signal dates, so every
`ex_2026_feb_apr` cut and "positive every year" clause remains a silent no-op
(confirmed cell-by-cell: ex-window n == ALL n across f2/f3 grids). Suite run
`make study-all` + four-family analyst pass (per-study detail below is the
analysts' read of the printed reports; no study code changed this session).

**BLOCKER — one row stops four studies.** `exit_mechanism_study --side debit`,
`exit_switch_mech_study`, `exit_switch_structure_study`, `bear_position_study`
all exit 1 on the same pre-registered harness gate:
`HARD 2024-08-15 HYG bear_put want=('dollar_stop',18,-0.775) got=('stop_loss',17,-0.75)`.
Diagnosed to the ULP: production computes `entry_net = 0.29 − 0.09 =
0.19999999999999998` → day-17 pl `−0.7499999999999999` → sl does NOT fire,
dollar_stop fires day 18 (−$1,023, stored). The harness rebuilds
`entry_net = float(export "0.2")` → day-17 pl `−0.7500000000000001` → sl
fires a day early. Both engines agree on every daily dollar figure; the
disagreement is worth $0 and one booking day. The row is old (identical in
v1 export), absent from v2/v3, re-admitted by the 2026-08-25 23:37 re-backtest.
Fix is a BASIS question (reconstruct entry_net from `entry_leg_detail`, or
widen `replay_basis.classify`'s near-tie to adjacent-day boundary ties), NOT a
harness edit — harness.py stays frozen. Until decided, the debit exit family
has no current report. Credit arm is clean for the second time: 113/113 exact.

**Two report defects found (both need a fix before recording/re-run):**
- `mech_regime_recut.py:52` reads `spy_vix_daily.csv` (starts 2024-06-03)
  while everything else — and its own provenance header — uses
  `spy_vix_daily_full.csv` (starts 2023-06-01). Result: 440/1031 rows
  (60 dates, 2024-01-10→08-02 = exactly the backfill) carry
  `mech_direction=NaN`; every mech agreement/veto number this run excludes
  H1-2024. One-line path fix, then re-run.
- `portfolio_delta` prints verdict `NOISE` while its own checklist line reads
  "arms clearing the whole bar: B ceiling 1.00, B ceiling 1.50" — the same
  verdict-grammar hole account_sim closed on 08-14, now on the study that
  produced its FIRST full-bar candidate: B ceiling 1.50 clears all seven on
  BOTH populations (paired +0.0894 R CI[+0.0255,+0.1656] primary / +0.0872
  CI[+0.0283,+0.1526] secondary, LOO 100%, ARM-N pct 100%). Costs dollars
  (−$3.5k, composition) and criterion-3 windows are vacuous on PRIMARY, so it
  cleared six live criteria + one free. Fix the grammar, then treat as
  candidate-for-independent-window, per registration.

**Trigger census reversals (correlated-window caveat applies to all):**
- `be_after 0.50` rollback trigger UN-FIRES on the grown book: 165 arming
  rows / 96 dates, total +$3,521, affected mean-R +0.0987, per-year 2024
  +0.0148 / 2025 +0.0046 → HOLD. The 08-24 revert fired on 2025 −0.034 at 92
  rows. Nothing un-reverts without a fresh registration — but a 60-row floor
  on a still-backfilling book produced a trigger decision that did not
  survive the next export. Also: `bear_arm.py:442` header still says
  "shipped 2026-08-11" and prints HOLD with no knowledge that
  `structure_exit.enabled: false` — misleading to a report-only reader.
- `bear_deploy` reversal HOLDS (2nd run): D2/D3/D4 all NOT MET; the shipped
  closer-to-money pick measures −0.014 [−0.146,+0.119] vs day average, its
  mirror +0.030. account_sim ARM H still cites "bear_deploy D4-adopted" —
  stale, remove before it propagates. New: D5 now shows 8 post-hoc gates,
  led by model-RANGE (+$9,622, both years positive) — independent window only.
- Attempt-13 credit rollback: 0 fresh bull_put rows (no 2026 dates) —
  UNDERPOWERED, parked; correlated comparator still favours sl-none
  (Δ −$2,294 vs sl-1×).

**Verdict movers elsewhere:** `account_sim --compounding` flips FEASIBLE →
NOT FEASIBLE AT $25k (A3 maxDD 25.7% vs 25% limit; A1 holds +0.359
[+0.245,+0.464]) — first run where the amended grammar names the combination;
under compounding the binding constraint moves off delta onto the 3/day cap
(56/126 primary). Base arm unchanged FEASIBLE (+0.342 [+0.221,+0.456], delta
binds, cash never does; its SECONDARY A3 fails at 35.7% with no verdict line —
grammar gap of its own). `selection_order` CLOSES its thread: all four arms
powered for the first time (29–45 affected dates), none clear, O0 sits inside
the O4 null band both populations → ORDERING-IS-NOISE recorded; the
"rejected-picks-outperform" premise also inverts in account_sim's own census
(per_pos_delta rejects +0.039 vs taken +0.342). `volume_signal` verdict moves
NULL → PATH-VOL-PROXY (r_sep sign-flipped to −0.0106, MFE/MAE now mirrored);
its one frozen exit variant is dead (−0.0036, 0% of 144 LOO folds). Best
readable bear cell yet: bear debit HIGH rvolz20 −0.421 [−0.561,−0.259] n=93,
reproduced in walk-forward TEST (−0.404 n=51). `staged_exit`: 40 powered
cells, 0 clear criterion 1, continuation failure 45–79% everywhere — the
reactive-exit null now extends to scheduled switches at 2× the sample.
`next_day_move` ARM R bear-debit carries ** on all three cuts for the first
time (flat band +0.110 [+0.006,+0.208] LOOmin +0.099) and stays unpromotable
by its own registration: criterion 4 unevaluable (no 2026), criterion 5
tweak-carried (real +0.002 vs tweak +0.193), ARM C control flattens → NO RULE.
`bear_rewrap` long_diag holds 5/5 on R (+0.216 [+0.051,+0.388], LOO min
+0.177) but its P1 worst-decile pass REVERSED (08-24 n=10 +0.902 → n=12
+0.186 CI spans 0) — re-label wrapper-fix, not hedge; long_put falls to 0/5,
closed. `financed_spread` F4-d20 still UNDERPOWERED (32 rows/29 dates vs
60/25) — dates cleared, rows didn't; blocker is CACHE coverage (621/2,040
candidate contracts, target_unreachable 152) → unblock is a
fetch_financing_legs d20 scrape, not more dates; and the v3 candidate's edge
was 4× concentrated in 2026, which this era cannot test. New near-miss:
F1 off2 6/7 (fails CI only, +0.053 [−0.027,+0.144]); F2 naked short
significantly harmful both offsets — close. `calendar_hedge` went backwards:
strict-fill worst-decile n 9 → 3 (12-date decile recomputed on the grown
book), overall fill 51.2% vs 60% gate — now a FILL-REALISM question, and the
survivor is fragile (89% of calendar $R in 5 dates, 38% in 2025-01-27;
>90-DTE carries 84%; hedge property vanishes under hold-to-expiry). ml_combination
NULL again (M3 −0.028 [−0.139,+0.081]); top features are calendar (dte/dow/
month_num) and M3's real-tier-only read is +0.036 vs B0 +0.320 — pooled gain
is tweak-tier. M2-as-tie-break is one bootstrap draw from arming Phase 5
(+0.042 [−0.005,+0.094]) — watch, off-basis. `v4_bridge`: all five tests
shift; v4 emission now LARGER than v3 (1,733 plays/157 dates) with tier mix
chi2 212 (B 13.7→27.6%, VETO 10.2→1.2%, A 15.4→9.9%) — the deploy card's
candidate pool is structurally different from the evidence population. And
regime_gap_reread §5d: the bear_put×iv_spread→MAE relation behind the Tier-C
rule is GONE at comparable n on v4 (v3 ρ −0.215 p<.0001 n=380 → v4 ρ −0.055
p=.33 n=322) — the strongest single non-replication this run; §1/§4b of that
report are dead weight on v4 (n=0 by construction; hardcoded date list
matches 0 rows).

NOT DONE, deliberately: `make study-record` — two reports above are
known-defective (mech SPY file, portfolio_delta grammar) and the record is
append-only verbatim; record after the fixes, or record now and re-record the
fixed runs under their new sha (operator call). emission_timing's v4 candidate
churn (4→3 candidates, membership swapped, ARM P headline flipped CANDIDATE→
FAIL between two v4 runs three days apart) re-confirms the 08-24 OFF-BASIS
retraction — v3 NULL stands, do not act on v4 ARM P cells.

Infra (same session, outside the suite): `make chart-evaluate` charts the
to_evaluate tab exports (full book, not the per-run scratch) into
backtests/charts/to_evaluate/; chart_backtest.py distribution panels
(MFE/MAE strip-box, $ histograms, spaghetti y-axes, paths MFE/MAE scatters)
now display-trim at the pooled 0.5–99.5 pct with clipped points drawn at the
axis edge and a per-panel count note — stats stay full-sample.

## 2026-08-27 (fix) — the two defective reports repaired and re-run; era recorded

1. `mech_regime_recut.py` now reads `spy_vix_daily_full.csv` (was the trimmed
   `spy_vix_daily.csv`, which starts 2024-06-03 and left 440/1031 rows —
   the whole H1-2024 backfill — with `mech_direction=NaN`). Corrected run:
   labels on 1021/1031 rows (the residual 10 predate the 50-SMA lookback).
   Verdict UNCHANGED — OR-VETO REJECTED — but the evidence is now much
   thinner than the truncated run implied: the newly-vetoed-by-OR subset is
   n=34 mean +0.0057 / total +0.19 R (truncated file said n=27 +0.1335), and
   the EARLY-half cut of that subset is negative (n=7, −0.4874). "The model's
   disagreements with the mech read are systematically right" now rests on a
   subset that is net-flat, not net-positive; worth a re-read at the next
   genuinely-new window. Row/date agreement rates now computed on the full
   book: direction 0.7346 / vol 0.7062 (row), 0.7379 / 0.6966 (date).
2. `portfolio_delta` verdict grammar completed per a dated registration
   amendment (research/pre-registrations/f4_deployment/portfolio_delta.md
   §Amendment 2026-08-27): the full-§Bar-pass combination — worded in §Bar
   since registration but never mapped to a label — is now
   **CANDIDATE-FOR-INDEPENDENT-WINDOW**, precedence below LONG-ONLY/
   UNDERPOWERED (unreachable there) and above DELTA-DOSE-RESPONSE/NOISE. No
   criterion, threshold, or arm definition moved; the c7-only case still
   resolves NOISE + QUALIFICATION. Re-run prints: "CANDIDATE-FOR-INDEPENDENT-
   WINDOW — B ceiling 1.00, B ceiling 1.50 clear the full adoption-eligibility
   conjunction" (B 1.00 is PRIMARY-only per the checklist; B 1.50 clears on
   both populations). Nothing ships; queued for an independent window.

Full pytest green (2,226). `make study-record` run after the fixes: 21
studies appended under era v4 · sha 25f3e27 · inputs 44c76b5 (the 6 absent =
4 HYG-blocked + 2 retired). The HYG basis decision (current.md §2026-08-27
BLOCKER) remains open — the debit exit family still has no current report.

## 2026-08-27 (fix 2) — HYG boundary-tie: classifier widened, debit exit family unblocked

The §2026-08-27 BLOCKER is resolved. Root cause restated precisely: harness
`replay()` rounds pnl to 10dp so that a threshold tie production FIRED
(Attempt 13's XLF class) fires in replay too — but rounding collapses BOTH
sides of the boundary onto it, so when production's unrounded pnl landed one
ulp on the SURVIVING side (HYG 2024-08-15: raw −0.7499999999999999 vs
sl 0.75), the replay fires a day early under EVERY entry basis — the entry-
leg reconstruction idea does NOT fix it (leg-basis pl −0.74999…99 also
rounds onto −0.75). So the fix is in the CLASSIFIER, not the basis and not
the frozen harness: `lib/replay_basis.py` gains a fifth class,
`boundary_tie` — a hard-looking row earns it iff the stored outcome
reproduces IN FULL (reason, day, pnl) once pt/sl is nudged TIE_EPS = 1e-9 in
the non-firing direction. 1e-9 sits 20x above the ~5e-11 rounding-tie scale
and 1000x below the smallest genuine mark-tick pnl gap (~1e-6), so the nudge
can only un-fire an exact tie; a stop 4 ticks past the boundary stays hard
(test-pinned). harness.py untouched. Consumers updated: exit_mechanism_study
tally/print, exit_switch_mech_study gate (boundary-tie rows EXCLUDED from
the calibrated-row cent check, like superseded — their flat replay books a
different day), book.py debit_calib seed/print; proxy admission unchanged
(exact-only). Tests: 5 new in test_exit_replay_gate.py (34 pass), full suite
2,230 green.

Re-runs, all four calibrate 356 exact / 1 near / 14 superseded /
1 boundary-tie / 0 HARD of 372 (credit arm 113/113):
- `exit_mechanism_study` (debit): reactive null AGAIN on the 140-date book —
  PROD +$32,765; best trail (.40/.75) +$34,697 ≈ noise-level Δ, most trails
  below PROD. Credit arm unchanged (pt .50 tease still single-trade-carried).
- `exit_switch_mech_study`: mech-keyed switch STAYS GATED; LVOL tef-null
  STAYS GATED (criteria pass again on the correlated window; ship still held
  for genuinely new dates per 08-24).
- `exit_switch_structure_study`: structure-keyed bear_put trail STAYS GATED.
- `bear_position_study`: **DEMOTE TO VETO — all three pre-registered
  criteria fire** (ex-window mean E −0.284; bootstrap CI [−0.413, −0.140]
  upper < 0; both halves negative −0.446/−0.087; CONSTRAIN candidates NONE).
  Same caveat as every graded read this week: registered on v3, bare-v4 run,
  correlated window — and the bear_put demotion IMPLEMENTATION (intake veto
  vs ladder VETO vs C-never-deploy) remains the queued OPERATOR decision
  from 2026-08-11; this run strengthens the case, it does not take the
  decision.
All four recorded (era v4 · sha 25f3e27 — total 25 studies on record for
this era; only the 2 retired lack reports).

