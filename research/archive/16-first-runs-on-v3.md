# Archive 16 — 2026-08-19: first runs of the v3-era studies

_Status: historical (covers 2026-08-19; every study read here is era v3). Superseded / qualified by: [archive/17 §2026-08-27](17-v4-refresh-bear-deploy-and-vocabulary.md) — the 140-date v4 re-run moved several of these first reads: `portfolio_delta`'s NOISE became CANDIDATE-FOR-INDEPENDENT-WINDOW, `financed_spread`'s F4-d20 candidate is UNDERPOWERED, and `calendar_hedge`'s fill fell under its own gate; [archive/17 §2026-08-24 addendum](17-v4-refresh-bear-deploy-and-vocabulary.md) — a later v4 `emission_timing` ARM P "candidate" was retracted as OFF-BASIS (the ARM P NULL here stands), and the v4 book carries no 2026 dates, so every ex-2026 robustness cut on it is a silent no-op; [archive/17 §2026-08-24](17-v4-refresh-bear-deploy-and-vocabulary.md) — `account_sim`'s v4 refusal was the thin backfill, not the study: it runs and prints FEASIBLE on the refreshed era. Live record: [current.md](../current.md)._

Covers 2026-08-19, the day the five studies registered that week
(`macro_event_study`, `staged_exit`, `emission_timing`, `financed_spread`,
`portfolio_delta`) ran for the first time on era v3, plus two gate lessons
(`account_sim` on v4: the date floor is not a density floor; `calendar_hedge`
R4: a gate keyed to a snapshot is not a gate). Headline reads, all on v3:
`macro_event_study` UNDERPOWERED in tight windows with NFP the only readable
cell and the ARM X trigger killed by the survival control; `staged_exit`
extends the reactive-exit null to scheduled switches (0 of 36 powered cells
clears the CI); `emission_timing` ARM L LAG-TOLERANT (the signal does not decay
within three sessions) and ARM P NULL; `financed_spread` all seven cells NULL
with the naked short significantly HARMFUL, then the post-scrape run's one
CANDIDATE (F4-d20 HOLD) hidden by the operator's own management rule;
`portfolio_delta` NOISE on the primary and the census finding that the
deployed ladder is LONG-ONLY BY CONSTRUCTION. The two-analyst disagreement
logs for all of these are folded in verbatim.

Sections are in log order. Later re-reads of these studies on v4 are in
archive 17 and `study-results/`.

---

## 2026-08-19 — `account_sim` on v4: the date floor is not a density floor

**No result. The study refuses on v4, and that refusal is the finding.**

The v4 export set crossed `MIN_ERA_DATES` (31 deployed signal dates, 34 in
`BacktestResults`) and `load_book` admitted it. `account_sim` then produced
**zero dense episodes** — not one run of ≥10 dates whose every internal gap is
≤5 trading sessions — because the v4 book is a BACKFILL: its signal dates are
scattered from 2024-01-10 to 2025-01-07, roughly a fortnight apart, plus a few
live sessions (2026-08-11 … 08-18) that have no backtest rows yet.

PRIMARY is the population this study concludes from, and on v4 it is empty.
SECONDARY (the full sparse book) is an availability upper bound and may not
carry a conclusion alone, so there is nothing to report and nothing to grade —
`make study-review` now stops on the refusal instead of spending three headless
model calls replicating it.

**What this says about the era floor.** `MIN_ERA_DATES` counts dates; it does
not ask whether any of them are CONSECUTIVE. Those are different questions, and
a backfilled era can satisfy the first while failing the second completely. Up
to 2026-08-18 the floor was masking this: v4 had 26 dates and refused as thin,
so the empty-PRIMARY path had never been reached. It was reached the day the
26th date became the 31st, and the study died in `statistics.median` on an
empty contract list rather than saying any of the above. That is now a designed
refusal (exit 2) stated at the population boundary — see `primary_refusal()`.

**Not a reason to loosen `episode_min_dates` / `episode_max_gap`.** They define
what this study is allowed to conclude from; the v3 evidence base was built
under them. The way to a v4 `account_sim` result is consecutive v4 sessions —
either accrued live, or backfilled DENSELY over a contiguous window rather than
sampled across a year.

---

## 2026-08-19 — `calendar_hedge` R4: a gate keyed to a snapshot is not a gate

**Method change, no new result.** R4 — the gate that decides whether the H arm
is allowed to run at all — was converted from a transcribed checksum to a
same-run comparison. Nothing about the hedge hypothesis changed.

**What R4 was.** It rebuilt `vol_sleeve`'s calendar cell and required it to
reproduce `R4_EXPECT = dict(n=183, mean_r=0.158, dollars=28059.0, exits={...})`,
transcribed by hand from `vol_sleeve-latest.txt` (2026-08-12, git 470b95f). The
stated purpose was to catch RE-IMPLEMENTATION drift: `calendar_hedge` builds its
own universe (`build_universe`) rather than importing `vol_sleeve.synthesize`'s
inline one, and two copies of an entry rule eventually disagree.

**Why it could not work.** The comparison had two free variables and one
equation. `vol_sleeve` picks K\* as "the cached strike nearest spot" and the far
leg as "the next cached expiry", so the option-history cache is an INPUT to leg
selection, not just storage — adding contracts re-picks legs and moves the cell
with no code change. A mismatch therefore could not be read as drift rather than
as cache growth, which is why the FAIL path carried an entire `_r4_attribute()`
bisect whose job was to guess which had happened.

The 2026-08-13 amendment tried to remove the second variable by SUBTRACTION:
withhold the contracts the ARM S sweep added (`legs_manifest.csv`) and rebuild
on the reconstructed pre-scrape grid. That inverse is valid only while every
LATER addition is manifested too. Measured 2026-08-19: 6,240 cache files
postdate the keyed run, the manifest covers 1,452. The remaining ~4,800 came
from routine `fetch_counterpart_history.py` runs that write no manifest, so the
"pre-scrape grid" had stopped being one. Worse, a rescrape that OVERWRITES an
existing contract changes leg PRICING with the same legs selected, and no index
filter can undo that — `snapshot_index()` explicitly filters selection only, on
the assumption that surviving files are byte-unchanged. Hence the study's own
FAIL text: "Once the cache grows, R4 can never pass again."

**Why re-baselining was not the fix either.** Re-keying the constants to a fresh
run would define "no drift" as "whatever this run printed" — circular, and
across an era boundary it is worse than circular: you would be baking v4's
characteristics into the definition of correct while v4 is the thing under test.
A constant that fails on legitimate data and cannot be corrected without
begging the question is not repairable. It has to go.

**What R4 is now.** Both sides are built in ONE process from the SAME book and
the SAME strike index — side A through this study's `build_universe`/`evaluate`,
side B through `vol_sleeve.synthesize(..., structures=("calendar",))` — and
required equal row for row on (entry_net, contracts, exit_reason, days_held, R),
keyed (ticker, date, expiry). Rounding is the checkpoint store's own round-trip
precision (6dp / 10dp), not a tolerance. Cache growth now moves both sides
together, so a mismatch has exactly one possible cause, which is the one the
gate was always about. First run under the new form: **R4 PASS**, 20 rows,
meanR +0.628, $62, exit mix identical on both sides.

**A second snapshot was hiding underneath it.** The checkpoint store
(`backtests/sweep_cache/synth_results.csv`) is keyed
`(structure, ticker, date, expiry, profile_hash)` — no input generation. So
after a scrape, `evaluate` would skip a cached row while `vol_sleeve.synthesize`
recomputed a fresh one, and the converted R4 would fail on the next scrape for a
reason that is still not drift. The key now carries a per-TICKER cache signature
(`ticker_cache_sig()`: file count @ newest mtime), so a row built against one
cache generation is never reused as, or compared against, a row built against
another. Per-ticker rather than whole-cache: a scrape touches some names, and
invalidating the other ~1,100 would empty the store without making one number
more correct. Rows written before the column existed carry `""`, match no live
signature, and are recomputed rather than trusted.

**The rule both R3 and R4 arrived at the hard way.** A gate compares two things
computed THIS run from the SAME input, or it is a fingerprint of one snapshot
wearing a gate's clothes. R3 became a print on 2026-08-15 for the same reason;
four `account_sim` gates with stored `expected_positions` were deleted the same
day. R4 was the last transcribed expectation in `scripts/backtest_study/` and it
survived on the argument that a RE-IMPLEMENTATION checksum is different from a
POPULATION checksum. That argument holds only while the code's inputs are fixed,
and a 24k-file scraped cache is not fixed. Where a code-behaviour claim genuinely
needs a fixed expectation, it belongs in `tests/` against a COMMITTED fixture —
version-controlled beside the code, changed only in a deliberate commit — which
is what `tests/test_harness_replay.py` already does for the frozen harness.

**Study outcome on v4 (unchanged conclusion).** With the gates passing, the H arm
runs to completion for the first time since the cache grew: exit 0, **H0 FILL NOT
MET** (was MET on v3), **H2 NOT EVALUABLE**, H2-under-hold NOT EVALUABLE. That is
the thin v4 book, not a refutation — the hedge programme was already
power-stopped. Blocked on dates, as before.

## 2026-08-19 — `macro_event_study` first run (era v3): tight event windows are UNDERPOWERED on this book; NFP is the only readable cell (null on vrp/R); ARM X trigger FIRED

New layer, built study-first (no pipeline/prompt change — a macro input into the
analysis prompt would be a v5 bump, and nothing here authorises it).
Pre-registration: `research/pre-registrations/f1_selection/macro_event_study.md`, committed at
325964e BEFORE the study was built. Infrastructure: `config/macro-events.yml`
(188 events, FOMC decisions/minutes + CPI + NFP + PCE, 2023-06 → 2027-12,
hand-transcribed 2026-08-19 from the official Fed/BLS/BEA schedules — the 2025
shutdown gaps are REAL and pinned by test: no Oct-2025-reference CPI/NFP, Sep-2025
releases delayed, PCE Oct+Nov 2025 combined, three 10:00 ET PCE deviations) and
`scripts/backtest_study/lib/macro_calendar.py` (strictly-after `next_event`,
`verified_through` refusal, unscheduled events excluded from forward reads only;
distance keys off the ENTRY session, `pre_open` decides day 0).

**Population: pooled real+tweak, era v3 — 795 rows / 118 dates (2024-06-17..
2026-04-07), bs excluded.**

- **G0 (the headline): the book cannot power tight event windows.** Splitting
  sides (before/after — the hypotheses are directional) leaves ONE cell at the
  pre-registered 25-affected-dates floor: **NFP AFTER w<=5 (25 dates / 162
  rows)**. Every FOMC, minutes, CPI and PCE proximity cell power-stops (best:
  FOMC BEFORE w<=5 at 15 dates). The pre-registration predicted the FOMC stops
  from the scoping counts; the side-split cost — roughly halving each window's
  dates — is the part the scoping estimate missed. Census confirmed the other
  pre-declaration: 795/795 rows carry >=1 macro event inside the DTE window
  (`n_*_in_dte` is a constant, not a feature), 716/795 inside the realized hold.
- **ARM I (H1 PRIMARY): null where readable.** vrp NFP-AFTER vs control +0.022
  CI[-0.019,+0.060]. Secondary watches, NOT claims: ticker-demeaned iv_entry
  +0.031 CI[+0.013,+0.051] and iv_pct +0.154 CI[+0.084,+0.220] both star, but
  the pre-registered REGIME-PROXY re-cut is power-stopped at every mech_vol
  label (8/14/3 dates), so EVENT-PRICES-IV cannot be evaluated — and iv_pct has
  been killed twice as a composition proxy. Verdict inputs: POWER-STOPPED
  everywhere except one null cell.
- **ARM P (H2): null.** R NFP-AFTER -0.144 CI[-0.331,+0.056]; every
  within-structure cell power-stops (bear_put 23d is the closest). The year-2026
  cut alone stars (-0.339) — a cut, not a headline, logged as such.
- **ARM V (H3, CONTEXT ONLY — index vol, never a verdict):** NFP shows the
  textbook build-then-bleed: dVIX +0.493 CI[+0.005,+1.169] at t-1, mean VIX
  peaks 18.9 the session after the print, then -1.069 CI[-2.336,-0.303] at t+3.
  FOMC shows NO significant pattern anywhere in t-5..t+5 — consistent with
  2023-2026 decisions being mostly telegraphed. 7 of 55 cells star against
  ~2.75 expected by chance; only the NFP pair is a coherent shape.
- **ARM X (H4, census): TRIGGER FIRED.** Mean R by position of the first event
  inside the hold is monotone — EARLY +0.014 (541 rows) / MID +0.042 (121) /
  LATE +0.122 (54) — across 118 affected dates. Per the pre-registration this
  queues **`macro_event_exit` (f2_management) with its own pre-registration**,
  and nothing else: the pattern is endogenous on its face (an event landing
  LATE in a hold means the position already survived that long).

Traps hit and fixed during the run (both now in code comments):
(1) `iv_spread`/`iv_pct` are pandas-sourced and carry **NaN, not None** — the
same trap `underlying_features.terciles()` fixed on 08-12; the study's
bootstrap now filters `v == v`. (2) `DESIGNED_REFUSAL_EXIT_CODES` must be a
PLAIN SET LITERAL — run.py finds it by `ast.literal_eval`, and a
`frozenset({4})` call is invisible, which silently demoted the tested exit-4
coverage refusal from DESIGNED REFUSAL to failure (deleting -latest.txt).
Negative test now verified: a truncated calendar (via `STUDY_MACRO_CALENDAR`,
test-only env) refuses exit 4 and the report is promoted, not deleted.

**Nothing ships. The macro layer's readable answer so far:** on THIS book,
entry proximity to scheduled macro events is mostly unmeasurable (the analysis
dates cluster away from event days), and where measurable (NFP) it moves
neither entry vrp nor outcomes. The live pipeline does not pay the v5 version
bump on this evidence. Re-run when new dates land; the calendar extends to
2027 so the layer is ready for the deploy card if evidence ever earns it.

### 2026-08-19 addendum — replication review graded; three report-completeness gaps closed

`study_review` (analyst A/B opus + validator sonnet) source-checked every quoted
number clean, and every hypothesis verdict stands as written above (H1 NOT MET
where powered, else NOT EVALUABLE; EXIT-TRIGGER MET both analysts). Validator
surfaced two real gaps, both closed the same day as REPORT-COMPLETENESS fixes
(no window, control, type, or floor changed): (1) ARM X now prints H4's
LITERAL census — exit position relative to the NEAREST event — which the first
report omitted in favour of the trigger's hold-position terciles: exits land
disproportionately just before/at events (−5..−1: 320 rows R +0.084; day 0:
+0.082) vs just after (+1..+5: −0.054); census only, feeds nothing. (2) The
starred ARM I secondaries now carry full G2 cuts (analyst B's stricter reading
of "headline"): `iv_entry_dm` survives ex-window/ex-BOTH and both pricing
tiers but its significance is 2024-carried (2025 and 2026 CIs span zero) —
confirming watch-not-claim. Also added a G0 day-0 audit table so the pre_open
assignment rule is checkable from the report (the 11 post-open PCE
entry-session rows are the 10:00 ET deviations, bucketing BEFORE as designed).
Grading-grammar note for future runs: the validator sided with bundling
UNBUNDLED — grade each anti-tuning clause separately rather than letting one
unevaluable clause downgrade a row.

### 2026-08-19 addendum 2 — ARM V-price (amendment 1): index PRICE around events

Operator follow-up ("how about the relationship with index price?") →
pre-registration AMENDMENT 1 (dated, after the first run; SPY numbers unseen
when written): the VIX context arm gains SPY close-to-close returns per
event-relative session plus two pre-declared cumulative windows (PRE t−3→t0,
POST t0→t+3). Same anchors, same event-clustered bootstrap, CONTEXT ONLY.

- **FOMC: the Lucca-Moench pre-announcement drift does NOT reproduce** at this
  n (26 events): PRE +0.371% CI[−0.202,+1.020]. Positive point estimate,
  unpowered; only t−2 stars (+0.442%).
- **CPI is the strongest price pattern in the table**: PRE +0.769%
  CI[+0.266,+1.236]* AND POST +0.642% CI[+0.213,+1.101]* — SPY rose into and
  out of CPI prints throughout this window. Read with the obvious caveat: the
  2023–2026 sample IS the disinflation regime; a market that rallies every
  time inflation prints soft produces exactly this table without any
  structural drift. Not separable at n=37.
- **NFP: price confirms the vol story.** POST +0.794% CI[+0.162,+1.546]* with
  the single-day star at t+3 (+0.621%*) landing the same session VIX bleeds
  (−1.069*). Build-then-relief in both moments — the one coherent
  cross-measure shape in the table.
- **PCE and minutes: noise-shaped** (scattered alternating-sign stars
  pre-event; nothing cumulative).
- Star accounting kept honest: 110 daily cells × 5% ≈ 5.5 expected, 9
  observed, plus 3/10 drift windows — only NFP (and CPI's paired drift) form
  coherent shapes.

Infra fix found by the run: `spy_vix_daily_full.csv` carries HOLIDAY rows with
one leg populated (2026-05-25: VIX close, empty SPY) — ARM V now requires BOTH
closes to parse before a date counts as a session; a one-legged session
poisons the return chain. Still CONTEXT: none of this touches a gate, floor,
readable cell, or the book itself. Nothing ships.

### 2026-08-19 addendum 3 — survival control kills the ARM X trigger; `macro_event_exit` DE-QUEUED; study goes passive

Amendment 2 (pre-declared before computing: X-C1 = same position table within
holds >= 20 sessions, X-C2 = position x hold-length terciles, consequence
grammar fixed in the pre-registration) came back unambiguous:

- **X-C1: the LATE bucket is EMPTY in long holds** (369 EARLY / 20 MID / 0
  LATE of 389 rows, 111 affected dates). With an event every ~2 weeks, a
  20+-session hold's first event lands early almost surely — the coupling is
  mechanical, exactly as suspected. Non-monotone by construction →
  **SURVIVAL-ARTIFACT** per the pre-declared grammar.
- **X-C2 shows what the raw trigger was actually reading**: within SHORT
  holds EARLY is the BEST bucket (+0.154 vs LATE +0.127, non-monotone);
  within MID holds EARLY wins (+0.147); LONG holds are negative everywhere
  (-0.184/-0.412). The raw EARLY +0.014 / MID +0.042 / LATE +0.122 monotone
  was composition: 50 of 54 LATE-position rows are SHORT holds (winners
  taking profit near an event they were about to span), while EARLY absorbs
  every long grinding loser. Exit-rule composition, not an event effect.
- **Consequence taken: `macro_event_exit` (f2) is DE-QUEUED.** It re-arms
  only if a future run fires the CONTROLLED trigger (X-C1), never the raw
  one. No new exit study will be built on this book's macro layer.

**Study disposition (operator: "do what you have to do"):** macro_event_study
goes PASSIVE — re-run at the next evaluation gate / when the enrich-queue
expansion lands (one command, `--era` as appropriate; G0 says whether any cell
crossed the floor), calendar gets an annual top-up (2028 dates), and no
active session is spent on this layer absent a powered cell. The v5 prompt
bump stays unpaid. Reusable lesson, again: a monotone table whose bucketing
variable is mechanically coupled to hold length is a composition read until
proven otherwise — condition on the coupling variable BEFORE queueing
follow-ups.

---

## 2026-08-19 — `staged_exit` first run (era v3): the reactive-exit null EXTENDS to scheduled switches — 60 of 96 cells UNDERPOWERED, and **0 of 36** powered cells clears the CI

**Nothing ships, nothing is queued. No CANDIDATE and no REACTIVE-AGAIN was
reached, because no cell got past criterion 1.**
Pre-registration: `research/pre-registrations/f2_management/staged_exit.md`, written before
the module existed. Report: `backtests/study_output/staged_exit-latest.txt`
(run 2026-08-19 17:10:09, git bfcd512, exit 0 after 43.3s).

**Population: pooled real+tweak, era v3 — 795 rows / 118 dates (2024-06-17 ..
2026-04-07), bs excluded** (`counts_by_source` real 406 / tweak 389 / bs 272).
`debit_calib` n=301 exact=289 near=0 hard=12; `n_credit_ungated` 277 — every
credit-side exit number below is unvalidated until the book is split per
credit-stop era (Attempt 13 removed the credit stop mid-book), and that caveat
bites hardest on ARM T, whose "tighten stop to −0.40" action INTRODUCES a stop
on rows whose shipped profile carries `sl=None`.

- **G0 — the grid does not power itself.** The frozen grid is 96 cells
  (2 arms × X ∈ {5,10,15,20} × 8 conditions × the arm's actions). At the
  pre-declared floor of 25 affected dates / 60 affected rows, **36 cells clear
  and 60 are UNDERPOWERED** (the report prints the older token
  `POWER-STOPPED`; the tally line reads `{'POWER-STOPPED': 60, '-': 36}`).
  The kill is structural, not incidental: **all 32 `arm trail 0.50/0.50` cells
  are UNDERPOWERED** — the largest is 27 rows / 22 dates — so ARM T's transfer
  test is carried entirely by the tighten-stop action, exactly as the build-time
  wording correction predicted.
- **Both integrity gates PASS and they are the reason to believe the nulls.**
  G1 (leak guard) checked 96 cells × 795 rows and found **0 rows changed
  outside the population**, with the keying evaluated INSIDE the rule so the
  check cannot be vacuous. G-FORK — the local `replay_staged` fork reproducing
  the FROZEN harness on (exit_reason, days_held, round(pnl, 10)) — ran
  **3,180 comparisons, 0 disagreements**.
- **The result: 0/36 on criterion 1.** Not one powered cell's date-clustered
  CI95 excludes zero. Best ΔR in the whole grid is **+0.011** (ARM E X=5
  R ≤ −0.25, CI [−0.036, +0.065], and ARM T X=10 $ ≤ −500, +0.011); worst is
  **−0.113** (ARM E X=15 R ≤ −0.25). Criterion 4 (sign-stable every year)
  passes **0/36** cells; criterion 7 passes 1/36; criterion 6 passes 36/36 by
  construction. The whole verdict column is `-` or UNDERPOWERED.
- **Criterion 7 is the same wall the trail attempts hit.** Across the 36
  powered cells the G2 continuation share — early exits followed by a post-exit
  max > realized + 0.30 — runs **49–79%** (ARM E 55–79%, ARM T 49–68%). The
  worst offenders are the profit-taking cells the operator instinct wants most:
  ARM E X=5 R ≥ +0.25 sells **112/141 (79%)** continuations, X=10 R ≥ +0.25
  sells **99/130 (76%)**. Cutting a winner at a scheduled checkpoint is the same
  trade as cutting it reactively.

**What this closes.** The Attempts 1/2/10 finding — a reactive exit switch on
this book sells continuation — was about triggers that fire whenever a
threshold is touched. `staged_exit` asked whether making the switch SCHEDULED
(evaluated once, at session X, then never again) buys immunity from that. It
does not: the same continuation share appears at every X, and no scheduled
switch separates from the shipped merge on any horizon between session 5 and
session 20. **The null now covers both reactive and time-staged exit switching
on these dates.**

**Build-time wording correction, recorded (part of the scientific record).**
The registration disclosed plan-time survivor counts (513 rows/114 dates past
session 5; 415/110; 333/109; 265/102). Those reproduce EXACTLY on the **debit
slice** (593 of 795 rows) — measured there, mislabelled as the whole book. The
registered POPULATION WORDING is unrestricted, and the wording governs: the
build runs credits in every population under CREDIT_PROD, and G0 now prints
debit and credit columns side by side with a reconciliation paragraph
(whole-book survivors **702/118, 583/117, 473/116, 385/111**). No population,
threshold or criterion moved — only a label on a disclosed number. Two
consequences were stated in place rather than quietly absorbed: the ARM T
tighten action introduces a stop on credit rows, and the trail action is
near-inert on this book.

**What re-arms it.** New dates only — 60 UNDERPOWERED cells need affected-date
counts to grow, and the powered 36 are recorded as read on these dates and are
not re-run on them. A v4 book large enough to power the grid would also be the
first honest test of whether the continuation share is a v3 selection artifact.

---

## 2026-08-19 — `emission_timing` first run (era v3): **the signal does not decay within three sessions** (ARM L LAG-TOLERANT — a publishable operational finding); repeat emissions are NULL (ARM P)

**The headline is ARM L, and it is a finding rather than a null: a missed
same-day fill is not a lost trade.**
Pre-registration: `research/pre-registrations/f1_selection/emission_timing.md`, written
before the module existed. Report:
`backtests/study_output/emission_timing-latest.txt` (run 2026-08-19 17:10:53,
git bfcd512, exit 0 after 15.0s).

**Population: pooled real+tweak, era v3 — 795 rows / 118 dates (2024-06-17 ..
2026-04-07), bs excluded.** `debit_calib` n=301 exact=289 hard=12;
`n_credit_ungated` 277 with the standing credit caveat. The ladder runs on ONE
population — **783/795 rows constructible at ALL of L ∈ {0,1,2,3}** (12
excluded and counted: 5 `degenerate_zero_entry`, the rest `no_mark_at_lag`) —
so no rung is compared against a different book.

### ARM L — LAG-TOLERANT

L=0 is a day-0 CLOSE fill built IDENTICALLY to L=1..3, so the close-vs-open
basis change cancels and the estimand is LAG-ONLY. The stored book prints as a
REFERENCE line (+0.0416) and is not the comparator.

- **The ladder is flat:** L=0 **+0.0051**, L=1 **+0.0180**, L=2 **+0.0158**,
  L=3 **+0.0168** mean R, all n=783 / 118 dates. If anything the lagged rungs
  are marginally *better*, which is itself evidence against decay.
- **Paired against L=0, every rung's CI includes zero:** L=1 **+0.0129
  CI[−0.0335, +0.0568]**, L=2 **+0.0107 CI[−0.0480, +0.0689]**, L=3 **+0.0117
  CI[−0.0574, +0.0772]**. All three clear criterion 2 (LOO every fold signed,
  share_positive 1.000) and criterion 6, and fail 3/4/5 — i.e. there is no
  stable effect in EITHER direction.
- **Verdict, in the registration's vocabulary: LAG-TOLERANT (PUBLISHABLE
  OPERATIONAL FINDING).** Worth stating precisely, because it is easy to
  over-read: the study did not find that waiting helps. It found that no lag in
  {1,2,3} separates from L=0 under the full conjunction, on a population where
  a real decay of the size the sizing rules care about would have shown. The
  operational consequence — the one the deploy card actually needs — is that
  the same-day fill is not load-bearing, so a missed morning is a deferred
  trade rather than a dead one.
- **The terciles argue with each other, and neither wins.** Cut on the
  pre-signal `price_vector` (frozen on the FULL book before any lag result was
  read): **T1_low** (the signal already moved against the play) improves with
  lag — L=3 **+0.0947 CI[−0.0187, +0.2040]**, clearing criteria 2–6 and
  failing only the CI, the single closest near-miss in the study — while
  **T3_high** decays with lag, L=3 **−0.0495 CI[−0.2031, +0.0851]**. T2_mid is
  inert. Opposite-signed sub-cuts that both fail the CI are exactly what a flat
  pooled result looks like when it is genuinely flat, and neither may be
  promoted. `MISSING` (73 rows / 16 dates) is its own cell by registration,
  UNDERPOWERED (the report prints the older token `POWER-STOPPED`), never
  imputed.
- **INTRADAY FILLS REMAIN UNTESTABLE.** Daily marks cannot represent a fill
  inside the session; nothing here is evidence about intraday timing.

### ARM P — NULL

Within-date paired Δ(mean R), repeats (ordinal ≥ 2) minus firsts, aggregated
over dates. 82 of 118 dates carry BOTH and are POWERED.

- **Headline: +0.0537 CI[−0.1149, +0.2243]**, n=82 pairs / 82 dates —
  criterion 1 FAIL. Criterion 4 (sign stable by year) also FAILs: **2024
  +0.1303, 2025 −0.0323, 2026 +0.1336**.
- Both frozen sub-cuts land in the same place: **consecutive repeats +0.0695
  CI[−0.1511, +0.2894]** (LOO clean, year sign FAIL), **gapped repeats +0.0390
  CI[−0.1548, +0.2354]** (LOO FAIL at share_positive 0.988). The
  already-moved-with-the-play cut is +0.0848, the moved-against cut +0.0211 —
  neither separates.
- **Verdict: NULL (no persistence effect).** A repeat emission is neither a
  stale signal nor a confirmation on these dates.
- **Recorded as a WATCH, explicitly post-hoc:** every ARM P cell's point
  estimate is positive, and the headline's LOO folds are 82/82 positive with
  min gain +0.0148. That is a LEAN toward "confirmation, not staleness", and it
  is written down only so a future run on new dates can be checked against a
  direction stated in advance. It is not a result, it did not clear the
  conjunction, and 2025 is wrong-signed inside it. Nothing may be built on it.

**G3 held throughout.** Every conditioning key routes through
`assert_conditioning()` against the frozen allowlist and every bar-derived
value through `close_asof()`, which FAILS the run if it resolves a session
after the signal date — so the day-0 underlying move is unreachable, not merely
unused, and `next_day_move` ARM C stands untouched.

**Build-time wording corrections, recorded (four, all before the run).**
(1) **ARM L anchoring was off by one** — the harness grid is weekdays AFTER
signal_date, so grid[0] is already the fill session; the synthetic anchors at
grid[L−1], which makes L=0 reproduce the stored trade except for the fill
price, as "L=0 is the baseline" requires. (2) **price_vector coverage** — the
disclosed 785/795 measured JOIN failure only; 63 further rows join with a blank
cell, so the true conditioned population is 722/795 and all 73 form the MISSING
cell. (3) **Consecutive repeats** — disclosed as 150; the frozen definition
(previous emission on the immediately preceding date present in the era book)
counts **151**, with the stricter calendar-next-weekday diagnostic (106)
printed alongside. (4) **Degenerate entries** — lag priceability now excludes
`marks[L] == 0.0` as well as None (5 rows, counted, never silently dropped).
Also recorded for the grader: contracts are re-sized by the production formula
at EVERY lag including L=0, because the harness `dollar_stop` fires on a
contract-dependent threshold and holding the stored count would turn the ladder
into a sizing artifact.

**What re-arms it.** New dates. ARM P's watch-lean and T1_low's near-miss are
both one powered re-run away from being checkable against a direction stated
here first; nothing about either is actionable until then. ARM L's finding is
already usable as an operational fact and needs no re-run to be relied on for
what it says.

---

## 2026-08-19 — `financed_spread` first run (era v3): **all seven cells NULL**, the naked short is significantly HARMFUL, and E3 says every shape re-wraps the sleeve it was supposed to diversify

**Financing a book debit vertical at a strike offset does not improve it, and
one shape actively destroys it.** Pre-registration:
`research/pre-registrations/f3_structure/financed_spread.md`. Report:
`backtests/study_output/financed_spread-latest.txt` (run 2026-08-19 17:11:08,
git bfcd512, exit 0 after 144.8s).

**Population: era v3 — 795 rows / 118 dates (2024-06-17 .. 2026-04-07),
real 406 / tweak 389.** The financed population is read off **LEG GEOMETRY, not
the `structure` label** (the label is a classifier output; the strike ladder is
not): **570 two-leg single-expiry debit verticals kept** (bull 240 / bear 330)
of 795 — excluded credit_signed 201, not_a_debit_vertical 9, not_two_leg 15,
plus 48 non-exact proxy debit rows. All seven cells clear the G0 floor
(≥25 dates / ≥60 rows). Baseline: n=570, win 46%, PF 1.16, **meanR +0.062**.

**Gates all PASS, so the nulls are about the structures and not the pricing.**
G1 reconstruction rebuilt **570/570 (100.0%)** rows within the pre-registered
tolerances (entry ±$0.005, per-day mark ±$0.01, ≥95% of priced days agreeing).
G2 clamp attribution PASS. E1 (the geometry gate) PASS at 96–100% row-sign
agreement on every gated shape.

### The cells

| cell | n / dates | ΔR (prod-sized) | CI95 |
|---|---|---|---|
| F0 own | 470 / 109 | −0.192 | [−0.422, +0.027] |
| F1 off1 | 173 / 85 | **+0.105** | [−0.019, +0.246] |
| F1 off2 | 107 / 66 | +0.002 | [−0.086, +0.079] |
| F2 off1 | 278 / 104 | **−0.290** | **[−0.559, −0.045]** |
| F2 off2 | 187 / 87 | **−0.456** | **[−0.819, −0.126]** |
| F3 off1 | 205 / 95 | −0.155 | [−0.429, +0.089] |
| F3 off2 | 160 / 87 | +0.016 | [−0.232, +0.250] |

- **F2 — the naked short leg beyond the outer strike — is the only cell whose
  CI excludes zero, and it excludes it on the WRONG SIDE.** off1 **ΔR −0.290
  CI[−0.559, −0.045]**, off2 **ΔR −0.456 CI[−0.819, −0.126]**; LOO share+ 0%
  at both offsets; every year negative at off2 (2024 −0.550, 2025 −0.488, 2026
  −0.314). The financed cell's own path tells the story: gb (|mean MAE| / mean
  MFE) blows out to **1.45 / 1.62** against the baseline's 0.75, and the
  fixed-contracts control at off2 is worse still (−0.650 CI[−1.149, −0.240]),
  so this is not a sizing artifact. Selling an unbounded short to finance a
  defined-risk debit is **significantly harmful on this book** — the strongest
  signed result the study produced, and it points the opposite way to the
  operator instinct that motivated the arm.
- **F1 off1 is the only near-miss, and it still fails twice.** It clears
  criteria **2–6** (LOO min +0.071 over 85 folds, share+ 100%; ex_BOTH +0.140;
  every year positive; both pricing tiers right-signed real +0.205 / tweak
  +0.031; 85 dates) and fails **1** (CI [−0.019, +0.246] includes zero) and
  **7** (E3 **+0.067** over 69 shared dates). Under the registered grammar a
  cell clearing 1–6 and failing 7 would be RE-WRAP; this one never cleared 1,
  so it is **NULL**.
- **E3 is positive on every single shape** — F0 +0.135, F1 +0.067/+0.278,
  F2 +0.061/+0.017, F3 +0.265/+0.115 — and the registered reading was fixed
  before the run: **POSITIVE correlation = RE-WRAP, REGARDLESS of ΔR.** That is
  the deepest finding here and it is not about any one shape: these synthetics
  are built on the ENGINE'S OWN signal dates, so financing does not add a new
  exposure, it **re-wraps the exposure already deployed**. This is the
  `vol_sleeve` lesson arriving again in a different costume.
- **The exit rule moves underneath F0 and F2 and is printed before any ΔR.**
  Exits are assigned by the SIGN of the synthetic net entry, so F0 flips
  **83.0%** of its rows to CREDIT_PROD and F2 flips 32.0% / 28.9% — those cells
  changed the exit rule as well as the wrapper, and their ΔR is not a pure
  structure read. F1 flips 1.2% / 0.0%, which is why F1 is the cleanest arm in
  the table.
- Worst-decile behaviour is printed and **refused as evidence** (9 dates), as
  the 2026-08-13 hedge-programme wall requires. F2 off1 shows +0.824 there on
  16 rows. It licenses nothing.

**Verdict: NULL on all seven cells.** No CANDIDATE, no RE-WRAP verdict issued
(RE-WRAP requires clearing 1–6 first), nothing queued from F0–F3.

**Build-time wording corrections, recorded.** Two registration statements the
geometry made unsatisfiable as written, corrected before the run with no
threshold or criterion changed: (1) **G2 on F2** — "100% UNclamped" is true
only of a naked short CALL; a naked short PUT (F2 on a bear base) is
structurally bounded at S=0 and `_defined_risk_bounds` clamps it CORRECTLY, so
the gate is evaluated on the naked-CALL subset (0 clamped of 102 / 59) with the
put-side count printed beside it. (2) **F0's offset axis is degenerate** — F0
sits at the debit's own strikes, so "four shapes × two offsets" yields **seven
cells, not eight**.

**Collector census discrepancy, recorded because it is part of the trail.**
The implemented target derivation reads **1,775 targets / 607 cached / 1,168
missing** (93 tickers, 462 groups) against the plan-time estimate of
**2,522 / 925 / 1,597**. The plan-time figure exceeded the rule's own
4-per-group cap and came from a looser derivation; the RULE that was registered
(2 nearest cached-ladder strikes strictly beyond each side) is what the
collector implements. No target was added or removed after any outcome was
seen. The gap shows up in the build census as `no_cached_ladder` (229–411 rows
per cell), which is why F1/F3 run on 107–205 rows rather than the full 570.

**A post-scrape re-run of F1–F3 is judged LOW VALUE, and this is the decision.**
Filling the 1,168 missing ladder strikes would raise n on cells whose verdicts
do not hinge on n: F2 is significantly HARMFUL (more rows make it more
harmful, not less), and **E3 is positive on every shape**, so criterion 7 fails
for a structural reason a bigger cache cannot fix. Only F1 off1 would benefit,
and it needs the CI to move a full 0.019 in the right direction while criterion
7 stays broken. **The live thread is F4.**

**AMENDMENT 1 (registered the same day, after this run and before F4 is built —
being built now).** The operator's intended financing is a structure these arms
never priced: a **short-dated, delta-targeted naked short leg** sold "not to be
reached", expiring while the debit thesis is still developing. Frozen in the
amendment: one short leg strictly beyond the debit's furthest OTM leg; expiry =
the nearest cached expiry ≥7 calendar days after entry AND ≤½ the debit's DTE
(else `no_near_expiry`); two cells at |Δ| ∈ {0.10, 0.20} picked from the 4
nearest cached-ladder strikes (never an invented strike; off-target by >0.10
⇒ `target_unreachable`); single tranche, no roll; the single-expiry clamp is
inapplicable so G2's F4 clause is "unclamped while the short leg lives" with
the segment boundary printed; **same gates, same floor, same 7-part
conjunction including E3 ≤ 0**. Nothing in the amendment reopens F0–F3 on
these dates. Note that F2's result is the relevant prior for F4 and it is a
bad one — the amendment's differences (short-dated, delta-targeted, expiring
inside the hold) are precisely what has to overcome it.

**Terminology, registered in the same amendment and adopted from here on:**
"POWER-STOPPED" is read as **UNDERPOWERED — too few dates to judge; census
printed, nothing concluded.** Existing reports and registrations keep the
original token for traceability; new code prints UNDERPOWERED.

---

## 2026-08-19 — `portfolio_delta` first run (era v3): **NOISE** on the primary — and the census is the real finding: the deployed ladder is **LONG-ONLY BY CONSTRUCTION** (219/220 positive delta, 0 net-short sessions)

**No band, ceiling or delta target is adoption-eligible, and the operating
constraint the study set out to test turns out to be a constraint on the study
itself.** Pre-registration: `research/pre-registrations/f4_deployment/portfolio_delta.md`.
Report: `backtests/study_output/portfolio_delta-latest.txt` (run 2026-08-19
17:13, git bfcd512, exit 0 after 15.5s). THE FIREWALL is printed at the top of
the report and holds: nothing ships from this study under any outcome.

**Population: era v3 book 795 rows; deployed picks 220 over 90 dates
(2024-06-17 .. 2026-04-07). PRIMARY = 3 dense episodes / 46 dates; SECONDARY =
the full 118-date book**, which by the same convention `account_sim` and
`selection_order` run under is an availability upper bound and carries nothing
alone. B1 provenance (descriptive, never a gate since the 2026-08-15 constant
purge): 220 positions / 90 dates / $63,553.

- **G-DELTA PASS, and it matters more here than any other gate** — every band
  in this study is a statement about signed delta-notional. Stored signed
  `delta` present on **795/795 (100.0%)**; per-leg greeks available at the entry
  day **795/795**; of those **732 (92.1%)** agree within 0.05 (threshold 90%);
  |leg-sum − stored| median 0.0140, p90 0.0457, max 0.1695. **0 rows excluded
  for a None leg greek** — and the repo invariant held: a missing leg greek is
  None, never 0.0, and such a row would have been excluded and COUNTED rather
  than silently zeroed.
- **G-INVENTORY — the census, and the finding most likely to BE the study.**
  Of 220 deployed picks: **179 bull_call_spread + 41 bull_put_spread**;
  **219 positive delta, 1 NEGATIVE, 0 zero, 0 missing** — and the report names
  the entire short side, a single row (2024-11-06, X, bull_put_spread, delta
  −0.097). Per-date net delta-notional / equity at session open: PRIMARY median
  **+1.703**, range [+0.000, +2.494]; SECONDARY median +1.316, range [+0.000,
  +2.498]. **net-SHORT sessions: 0 in both populations. OUT-OF-BANDS: 0.** The
  registration's central claim is therefore confirmed as measured, not assumed:
  **a band with a LOWER bound is unreachable from below on this book**, and net
  delta can only be moved DOWN by not trading or by re-sizing the hedge sleeve.
- **ARM D (dose-response, descriptive primary) does not separate.** On PRIMARY
  only one band reaches MIN_CELL_N=20 — [1.0,2.0) n=29, meanR +0.325
  CI[+0.090, +0.546] — so **SHAPE: NOT READABLE** (≥3 n-sufficient bands are
  needed before "monotone" means anything), recorded as such and explicitly not
  as a null. On SECONDARY all four bands are readable and the shape is
  **NON-MONOTONE / FLAT**: +0.069 / +0.079 / +0.234 / +0.201. Adding exposure
  onto an already-long book does not visibly pay worse — descriptive only, and
  no band value may be adopted on it.
- **Power, stated precisely because it differs by population.** On **PRIMARY**,
  **only `B ceiling 1.00` clears the ≥25-moved-dates floor** (32 of 46);
  everything else is **UNDERPOWERED** (the report prints the older token
  `POWER-STOPPED`) — B 1.50 at 22, B 2.00 at 19, B 2.50 and B inf at 0, and
  **all three H\* delta-target arms** at 16 / 19 / 20. On **SECONDARY** five
  arms clear (B 1.00 at 58, B 1.50 at 36, B 2.00 at 30, H\* 1.50 at 29, H\*
  2.00 at 31) and are read — but SECONDARY carries nothing on its own, so
  **the delta-target hedge programme is UNDERPOWERED where it counts.**
- **ARM N decides the meaning of everything else**, per the registration: an
  arm must beat the null band's 95th percentile, not merely beat the shipped
  book. PRIMARY draws 200, seed 20260819, p95 **−0.0104**; SECONDARY p95
  **+0.0245**; SECONDARY sleeve-basis p95 +0.1085.
- **The single powered PRIMARY arm fails the bar.** `B ceiling 1.00`: paired
  mean gain **+0.0374 R CI95 [−0.0766, +0.1680] → FAIL c1**; LOO share>0 95%
  with MIN −0.0087 → FAIL c2; by year 2025 +0.0984 / 2026 −0.0298 → FAIL c4;
  it PASSES c3, c5, c6 and — notably — **c7 at pct 100%**, sitting above ARM
  N's p95. On SECONDARY the read arms fail too: B 1.00 fails c1 and c5
  (tweak −0.0062); B 1.50 fails six of seven; B 2.00 fails six of seven;
  **H\* 1.50 is the only arm anywhere whose CI excludes zero (+0.0841
  CI[+0.0102, +0.1683])** and it fails c4 (2024 −0.0199) and c7 (pct 76%,
  inside the sleeve-basis null band) — i.e. it does not beat random admission,
  which is the whole point of ARM N.
- **Verdict, in the registration's vocabulary: NOISE** — no arm exceeds ARM N's
  95th percentile and ARM D's bands do not separate within their cells.
  Recorded; thread closed for these dates.

**Verdict-grammar note, recorded (build-time, labelled, not a
re-registration).** The registered labels left one combination unnamed: an arm
clearing criterion (7) while failing the rest matches none of NOISE /
DELTA-DOSE-RESPONSE / LONG-ONLY-BY-CONSTRUCTION / UNDERPOWERED. Per the
`account_sim` 2026-08-14 lesson — fix the grammar BEFORE a run, never after a
number — the build assigned that case to **NOISE with a printed QUALIFICATION
block naming the arm**, rather than inventing a fifth label after the fact.
That block duly fired for `B ceiling 1.00`, and the report says so in plain
words: NOISE is carrying it as the catch-all, the per-arm checklist is the
whole result, and nothing on it is adoption-eligible. Also recorded in the same
note: the registration's disclosed per-date net-delta figures (median 0.33, max
1.17) were measured on THAT DAY'S PICKS at 1 contract, while G-INVENTORY
measures the OPEN BOOK at session open under production sizing (median +1.70,
max +2.49). Different quantities by definition, both now printed with their
definitions — and the long-only fact (0 net-short sessions) holds under both.

**The standing caveat is not discharged by a null.** The ladder is itself
in-sample, so any exposure rule evaluated on the same book is SECOND-ORDER
in-sample. That does not disappear if the numbers look good, and it is why
adoption would have required out-of-fold survival even had an arm cleared.

**What re-arms it.** New dates, and specifically DENSE ones: PRIMARY is 46
dates across 3 episodes, which is what starves the ceiling and delta-target
arms of moved dates. Note the same trap `account_sim` hit on v4 the same day —
a date floor is not a density floor — so a backfilled v4 era will not re-arm
this study however many dates it accumulates; consecutive sessions will.
Until then the usable output is the census, not a rule: **the book is
structurally long, and any delta-management proposal has to start from that
rather than from a band.**

## 2026-08-19 — Disagreement logs, four-study replication reviews (protocol step 4)

All four studies graded via `scripts.study_review` (analyst A/B + validator; digests
in `backtests/study_output/<name>-digest-latest.md`). Main-session decision: **all
four recorded verdicts ACCEPTED as written.** Per-study log:

- **staged_exit** — one disagreement, RESOLVED mechanically by the validator:
  analyst A graded G2 "NOT MET" while applying the opposite aggregation rule two
  rows later on the same facts; resolves to B's reading (1 of 36 cells passes the
  continuation diagnostic). Verdict unaffected — that cell fails criterion 1
  regardless. Zero number mismatches.
- **emission_timing** — disagreement UNRESOLVED but verdict-neutral: A and B split
  on how to collapse 17 per-cell criterion results into one table row
  (all-must-pass vs any-passes); the registration states a per-cell conjunction and
  never defines a collapsed row, so both readings are defensible and the per-cell
  grading in the report stands. One confirmed transcription slip in B (window-cut
  pass count 10 → 9; changes nothing under B's own rule). A alone flagged a REAL
  coverage gap, logged below.
- **financed_spread** — zero verdict disagreements, zero number mismatches across
  54 shared rows.
- **portfolio_delta** — agreement; B additionally caught that the registration
  gives two readings of "SECONDARY" (v4-era vs sparse-book) and the report
  implements the sparse-book one. Accepted as the operative reading; noted for the
  next amendment if the study re-arms.

**Build-wide gap (logged, deferred):** every registration names era `current`/v4 as
a reported-only SECONDARY; none of the four first-run reports prints such a
section (single-era invocation). Deliberately NOT patched by re-running on
`--era current` now — that would overwrite each `-latest.txt` the reviews just
graded, and the v4 era (34 backfill dates) would underpower nearly every cell
exactly as the registrations predict. The secondary section lands at the next
scheduled re-run of each study (F4 post-scrape for financed_spread; new-dates
gates for the rest).

## 2026-08-19 — `financed_spread` post-scrape run: F4-d20 HOLD is the study's one CANDIDATE — and the operator's own management rule is what was hiding it

Second run, era v3, after the fin_diag scrape (897 fetched + 10 on retry; 171
residual failures are unlisted/expired contracts; F4 coverage ~86% of the
1,256-target census). F0–F3 verdicts unchanged (all NULL). The six F4 cells
(amendment 2): **F4-d20 hold clears the full 7-part conjunction** — paired dR
+0.176 CI [+0.015, +0.354], LOO min +0.143 over 74 folds (100% positive),
windows ex_2025_mar_apr +0.259 / ex_2026_feb_apr +0.073 / ex_BOTH +0.148,
years 2024 +0.019 / 2025 +0.098 / 2026 +0.374, tiers real +0.060 / tweak
+0.259, 74 dates, **E3 −0.134** — the only negative sleeve correlation in all
13 cells. This survives amendment 2's honest residual costing (108/1284
cell-rows that amendment 1 would have forgiven are PAID at their last real
mark; d20-hold residual cost mean 1.240 vs median 0.010 — the tail is in the
number).

The two reads that matter:
1. **The management rule kills the edge on the same rows**: F4-d20 pt50
   +0.052 (NULL), $100 +0.022 (NULL), hold +0.176 (CANDIDATE). The 50%/$100
   buyback fires at mean 3.9/2.8 grid days and returns the remaining decay;
   hold keeps the leg live 17.8 days. The operator's stated close-early
   practice is, for THIS financing leg, the expensive half of the idea.
2. **d10 far-OTM is the losing version**: all three d10 cells NULL-to-negative
   AND re-wrapping (E3 +0.21 to +0.29) — the bear_deploy "cheap far-OTM is the
   losing trade" shape, now on the financing side.

Caveats stated with the candidate: built 117/570 rows / 74 dates
(target_unreachable 237 — the cached ladder often has no strike within 0.10 of
the 0.20 target at the near expiry; no_near_expiry 149), so the cell is a
candidate ON THE BUILDABLE SUBSET; the naked-short tail is real (residual mean
vs median above); assignment mechanics beyond mark-costing (pin risk, early
exercise) remain unmodelled. **CANDIDATE is not a ship**: per the registration
it queues an independent-window confirmation before it may even be proposed
for docs/deployment-rules.md. Re-arms on new dates; the d20 scrape gap
(target_unreachable) could be narrowed by a wider near-expiry strike scrape if
the confirmation window ever needs it.

## 2026-08-19 — Disagreement log, `financed_spread` post-scrape review (protocol step 4)

Second review, on the post-scrape report with the F4 cells priced (the first
review graded the pre-scrape report, where F4 was ungradable). Validator
re-checked all G0–G3, E1–E3 and all 91 C1–C7 cells: **zero numeric
mismatches**, and both analysts independently confirm the VERDICTS block —
NULL ×12, **CANDIDATE for F4-d20 hold**. Two disagreements, both resolved as
cosmetic: (1) analyst A graded the descriptive E2 vega read as a MET row where
B excluded it — the registration gates nothing on E2, so B's omission is the
literal reading and A's label was harmless; (2) A graded the E3 ≥8-shared-dates
precondition as its own row where B folded it into each cell's criterion 7 —
same fact, two presentations. Main-session decision: **CANDIDATE grading
ACCEPTED.** Status unchanged: not a ship; queued for the independent-window
confirmation the registration requires.

