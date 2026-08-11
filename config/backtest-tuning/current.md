# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index.

**State of play (2026-08-11, latest).** The DEPLOY arm has run and settles the bear question the operator actually asked: bear positions ARE deployable — as a *hedge*, not as a selection. Selection stays unfixable (D1: 0 of 496 subsets, even under the new exit), but the sleeve pays on the deployed book's worst dates (D2 MET) and there is now one reproducing pick rule — take the **closer-to-money** bear, `|delta|` descending (D4, all three years, holds on the shipped exit). Nothing shipped; both are recommendations. Prior state below.

**State of play (2026-08-11, late).** The ML combination search has RUN and is a
NULL RESULT (no model beats the ladder in any of 15 model×strategy cells); the
bear arm run alongside it found that bear structures are an EXIT problem after
all — `be_after: 0.50` keyed to bear debit spreads clears every pre-registered
criterion including the 2026 window on its own, which is the "second sustained
bear drawdown" addendum 12 said would settle it. Recommended, not shipped —
awaiting the operator. Bear SELECTION remains unfixable from these columns
(0 of 496 conditioned subsets survive). Details in the entry below.

**Earlier that day.** The Feb–Apr 2026 holdout backfill is COMPLETE
(33 window dates priced, incl. the 7 late dates and 02-17/02-19) and the
completed-book analysis (below) has all three pre-registered bear_put DEMOTE
criteria firing at n=164 with the real-tier discordance resolved downward —
the demotion is decision-eligible; implementation choice (intake veto vs
ladder VETO vs Tier-C-never-deploy) is the user's. Shipped config is the
source of truth — `config/backtest.yml` (exits, `regime_exit.cells: BEAR_HE`
only) and `config/deployment-rules.md` (VETO / A / B / C ladder, top-3 per
day, bull_put band `0.08 ≤ |delta| ≤ 0.20` + `DTE ≤ 59`). Open questions:
(1) **bear_put implementation** — verdict reached, mechanism not chosen;
(2) **the long-dated blind spot** — h≥180 still unpriceable with real data,
and the bs tier — measured as attenuating (tail-compressed marks shrink every
effect toward zero) AND selection-contaminating (64 rows inside the top-3/day
replay) — is now OFF (`proxy.bs_fallback: false`); evaluate real+tweak only,
and filter the 301 legacy bs rows out by `proxy_method` at read time;
(3) **live substitution** — the
operator sometimes trades naked where the engine emitted a spread, which
breaks the live walk-forward's attribution. Next study queued: the ML
combination search — plan pre-written in [`ml-plan.md`](ml-plan.md), NOT run.

---

## 2026-08-11 — DEPLOY arm: the hedge caveat was TESTABLE, and bear deployment has a rule

The 08-11 bear arm closed by calling the chop hedge "a *portfolio* decision the
book cannot price". **That was too strong** — 84 of the bear dates also carry a
deployed ladder sleeve, so the concurrent book exists and the portfolio question
is answerable on it. The operator's instruction (bear positions stay deployable)
made the gap worth closing. Pre-registered as
[`ml-plan.md` §addendum 2](ml-plan.md) BEFORE running; code
`scripts/backtest_study/bear_deploy.py`, output `backtests/study_output/bear_deploy.txt`.
Same 795-row book, same protocol, no new columns.

**What B1/B2 had actually left open.** Three distinct estimands, not a second
bite at the same one: B1 asked an *absolute level* question and B2 an *exit*
question, and neither asked (a) the two jointly, (b) what bear does to a
concurrent long book, or (c) *which* bear to take on a day one is taken anyway.

### 1. D1 — joint selection × exit: NOT MET (B1's verdict survives)

B1 screened E under the PROD exit; B2 then changed the exit; the pair had never
been run together. Re-screening the identical 496-subset vocabulary on R under
`be_after: 0.50`: **0 survivors, ~10 expected by chance.** Pooled bear
E −0.601 / R(PROD) −0.168 / R(bear exit) −0.203. The best subset is
`mech LVOL AND dte 31-59` at R +0.287, CI [−0.034, +0.593] — still includes
zero at n=49. **Bear selection remains unfixable; the new exit does not rescue
it.** Worth noting the exit lowers pooled R slightly (−0.168 → −0.203) across
ALL bear rows including credit — B2's +0.041 gain was measured on bear *debit*
rows only, and that scoping is load-bearing.

### 2. D2 — the hedge is REAL (all three pre-registered criteria fire)

Deployed sleeve = shipped ladder (top-3/day, tiers A/B, 220 rows / 90 dates).
Bear sleeve = that date's bear candidates. 84 overlapping dates.

    deployed-book bucket   dates   deployed R    bear R     bear $   bear win%
    worst decile               8       -0.795    +0.252     +6,669      75.0%
    worst quartile            21       -0.457    +0.184    +16,824      66.7%
    negative dates            25       -0.390    +0.109    +16,985      60.0%
    positive dates            59       +0.706    -0.281    -41,895      32.2%
    ALL                       84       +0.380    -0.165    -24,910      40.5%

Sleeve correlation −0.132; tail positive in 2 of 3 evaluable years
(2024 +0.129 / 2025 −0.048 / 2026 +0.405). **HEDGE IS REAL: MET.** The shape is
textbook insurance: it pays where the book bleeds and bleeds where the book
pays. Honest limits — the worst-decile row-level CI is [−0.113, +0.639] (n=28,
includes zero), 2025's tail is mildly negative, and D2 approximates a hedge as
equal-weighted concurrent dollars, which is a *proxy* for, not a measurement of,
a held hedge.

This is the first evidence in the log that supports carrying bear risk at all,
and it exists only because the question was asked at the book level. Every prior
bear verdict measured the standalone play and was correct to be negative.

### 3. D4 — the operator's real question, and the one actionable rule

Not "is bear good" but **"given I take a bear position today, which one?"** —
a *within-date paired* test on 93 dates with ≥2 bear candidates (3.8/day). The
day is its own control, so the −0.5 level that sinks every B1/D1 subset cancels.
This test had never been run, on any structure.

    ranker                    dates    pick R   day avg      gain   CI95              LOO min
    |delta| HIGH first           93    +0.051    -0.181    +0.232  [+0.091,+0.370]     +0.204  **
    iv_spread low first          92    -0.094    -0.180    +0.086  [-0.056,+0.236]     +0.065
    dte short first              93    -0.176    -0.181    +0.004  [-0.203,+0.185]     -0.015
    |delta| low first            93    -0.393    -0.181    -0.212  [-0.370,-0.062]     -0.233
    score_total high first       93    -0.436    -0.181    -0.255  [-0.417,-0.098]     -0.276
    widest max_loss first        93    -0.526    -0.181    -0.345  [-0.580,-0.147]     -0.368

**`|delta| high first` is ADOPTED** — 1 survivor of 10 tested (~0.5 expected),
CI excludes zero, every LOO fold positive, positive in all three years
(+0.285 / +0.312 / +0.083). It is **not exit-dependent**: on R under the
SHIPPED PROD exit it still holds (+0.159, CI [+0.028, +0.280], LOO +0.144, all
three years positive). On E alone it fails (+0.059, CI includes zero) — so this
is a *realized-return* effect, partly exit-mediated, and must be quoted that way.

Read: **the losing bear trade is the cheap far-OTM one.** Buying the
closer-to-money bear spread turns a −0.181 average day into +0.051. Two
corroborations from elsewhere in the log: D1's best subsets pair `LVOL` with
`|delta|>0.20`, and `score_total high first` anti-selecting (−0.255) is the
07-21 "score is decision-irrelevant / pre-13c scores anti-select" finding
reappearing inside a structure.

### 4. D3 — always-on sizing: NOT MET, but by $86

**Deviation, recorded:** the pre-registration fixed the sizing rule but not
which bear is taken daily. The first cut used the day's widest `max_loss` —
which D4 then measured as the single *worst* available pick. Both are reported.

    sleeve = 1/day by |delta| high (D4-adopted)
        f      total $    max DD $   worst date $
     0.00       63,553      -7,609         -3,212
     0.25       64,268      -7,255         -3,255
     0.50       64,982      -7,037         -3,298
     1.00       66,412      -7,780         -3,501

    sleeve = 1/day by widest max_loss (lower bound on a bad pick)
     0.50       42,167     -11,291         -3,877
     1.00       20,780     -18,127         -4,542

At f = 0.50 with the right pick, **max drawdown IMPROVES** (−7,609 → −7,037) and
total rises +$1,430. The pre-registered rule still returns NOT MET because
worst-date slips $86 on a $63.5k book — the rule's worst-date clause is doing
all the work at a magnitude that is noise. Reported as NOT MET per the letter of
the pre-registration; read as *the sleeve is roughly free at half size, and
expensive at full size or with a bad pick.* The picker matters more than the
size: same sleeve, same days, −$42.8k swing between the two.

### 5. D5 — timing the hedge: POST-HOC, and it does NOT reproduce

D2+D3 jointly imply a gate (pays in the tail, bleeds in the body). Seven
deploy-time gates tested; `mech H-VOL` and `mech BEAR_HE` leave drawdown and
worst-date unharmed while adding $2–3k. **But the year check kills it:** the
leading gate is 2024 −$2,655 / 2025 +$5,179 / 2026 +$813 — one year carries it,
which is the Mar–Apr-2025 failure mode for the third time in this log.
**Candidate only, not a finding, chosen after seeing D2.**

### 6. What this changes

- **Bear positions are deployable — as a hedge, not as a selection.** D1
  reconfirms there is no bear edge standalone. D2 shows the sleeve pays in the
  deployed book's tail. These are consistent, not contradictory, and the
  distinction is the whole answer.
- **Recommended (NOT shipped — operator decision):** add to
  `deployment-rules.md` — *when you take a bear position, take the
  closer-to-money one; rank the day's bear candidates by |delta| descending.
  Size the sleeve at ≤ ½ a normal position and treat it as insurance, not as a
  play.* This is the first bear rule in the log that reproduces in all three
  years on the SHIPPED exit.
- **The `bear_arm.py` caveat is amended:** "the book cannot price a hedge" is
  retired and replaced with the measured version — it *can* price a
  concurrent-dollar proxy for one, and did.
- **Still unanswered, and honestly so:** 88% of bear rows are `bear_put_spread`
  and only 6 are naked `long_put`, so none of this speaks to the naked-put
  hedge the operator sometimes substitutes (see the SUBSTITUTED item in the
  live walk-forward). Margin, assignment and real position sizing remain
  outside the book. D5's gate needs an independent window.
- Unchanged: no production config, prompt or ladder was modified by this run.

---

## 2026-08-11 — ML combination search RUN: NULL RESULT; and the bear arm finds an EXIT fix, not a selection one

Both arms of [`ml-plan.md`](ml-plan.md) executed against the same 08-11 exports.
Code is now TRACKED under `scripts/backtest_study/` (`book.py` loader, `harness.py`
replay port, `protocol.py` validation, `ml_combination.py`, `bear_arm.py`);
outputs in `backtests/study_output/`. Book: **795 priced rows,
118 dates, real 406 / tweak 389** (bs excluded per the 08-11 decision; the
loader's exact-replay gate drops 48 non-reproducing proxy debit rows and 3 real
dups, which is why 795 and not the 08-11 scratch cut's 817).

Deviations from the plan, both recorded before the run: GBM is sklearn
HistGradientBoosting rather than LightGBM (same family, no libomp), and a
third replay variant (**abstain** — the model may sit out a day) was added so
the ladder's right to trade nothing is not an unfair advantage.

### 1. ML arm — nothing beats the ladder, in any form

Purged expanding walk-forward, 10-date blocks, 120-day embargo → 58 of 118
dates ever tested (the embargo is expensive at this sample size). Every model
ranked against the ladder on the SAME dates, paired at date level.

    model            forced        abstain       tie-break in A/B
    B1 logistic      -0.173        -0.073        -0.074
    B2 elastic net   -0.180 *      -0.095        -0.062
    M1 GBM (E)       -0.096        -0.057        -0.006
    M2 GBM (E>0)     -0.113        -0.097        +0.022  CI[-0.017,+0.071]
    M3 depth-3 tree  -0.155 *      -0.102        -0.027
    (* CI excludes zero — i.e. significantly WORSE than the ladder)

**Not one positive gain with a CI excluding zero, in 15 model×strategy cells.**
The best cell in the whole study is M2 as a within-tier tie-break at +0.022,
CI [−0.017, +0.071] — includes zero, so ADOPT-AS-TIE-BREAK is also not met.
M3 additionally fails the year-sign criterion (2025 +0.361 / 2026 −0.121).

**Phase-5 verdict: NULL RESULT — the ladder is at or near the information
ceiling of these columns.** This was the plan's stated modal outcome.

Supporting reads, all consistent with the 07-21 column sweep:
- The full-sample M3 tree's root split is `structure = bull_call` — the model
  rediscovers "structure is the signal" unprompted.
- Ablations (top-3/day $ out-of-fold): ladder-only +$6.1k → +regime +$1.9k →
  +geometry +$11.9k → +enrichment +$2.5k → +scores +$4.0k → +calendar +$10.3k.
  Non-monotone and inside the noise: **nothing beyond structure × regime ×
  geometry adds anything reproducible.**
- Composition-proxy test (rule 6) catches `cpir` red-handed: pooled Spearman
  vs E **+0.27**, but within structure +0.04 / −0.03 / −0.10. Same trap as
  oi_confirm/iv_pct. `iv_pct` repeats its own failure (pooled −0.17, within
  structure −0.12 / +0.05 / +0.12, sign-flipping).

### 2. Bear arm B1 — selection: NOT MET, decisively

370 bear rows (bear_put 327 / bear_call 37 / long_put 6), 111 dates. Pooled
E −0.601, CI [−0.726, −0.477], negative every year (−0.815 / −0.660 / −0.386).

496 pre-declared 1- and 2-clause subsets evaluated, 203 with n ≥ 40.
**0 survivors** of the pre-registered rule, against ~10 expected by chance at a
nominal 5% rate. The best subset in the entire search is E −0.231
(`mech BEAR AND iv_pct<0.5`, n=43) — still negative. There is no conditioning
of bear entries, on any decision-time variable in the book, that is not a
losing selection.

**The operator's chop hypothesis, tested directly.** The closest thing to
support is the RANGE + calm/choppy slice, and it is an EXIT story:

    slice                    n    dates   E        R        $        |MAE|/MFE
    model RANGE + C/L-VOL    55   16     -0.370   +0.182   +$10,119   0.76
    model C-VOL              53   20     -0.596   +0.128    +$7,095   0.92
    mech L-VOL               97   38     -0.581   +0.002    +$3,586   0.99
    model H-VOL              78   17     -1.157   -0.682   -$50,482   4.01

RANGE+C/L-VOL is the only bear slice that makes money (R positive in 2 of 3
years: −0.247 / +0.320 / +0.284), and its |MAE|/MFE of 0.76 is the only
non-mirrored bear number in the book. But **E is −0.370 with CI [−0.697,
−0.045] and the R CI [−0.117, +0.463] includes zero**: the plays are still
wrong, the exit is what collects. Directionally consistent with the operator's
instinct; not a selection edge, and n=55 over 16 dates.

The mirror image is decisive and already shipped: bear in H-VOL is −$50.5k at
a 9% win rate and |MAE|/MFE 4.01 — the ladder's BEAR+H-VOL VETO earns its keep.

### 3. Bear arm B2 — exit: **CRITERIA MET**, and it is the knob addendum 12 pre-nominated

Frozen grid only (18 debit configs, no new mechanism). Bear debit n=332:
mean E −0.534 vs mean R(PROD) −0.133 — the exit is ALREADY rescuing ~0.40 of a
bad selection, and six configs rescue more. Ranked by robustness, not by size:

    config              Δ pooled   CI95            ex-25MarApr   2026 alone      LOO min
    BE ratchet @.50     +0.041   [+0.015,+0.065]   +0.020        +0.028 [+0.009,+0.053]  +0.038
    trail .40/.50       +0.042   [+0.007,+0.073]   +0.023        +0.037 [-0.002,+0.077]  +0.038
    trail .25/.50       +0.043   [+0.003,+0.081]   +0.020        +0.025 [-0.032,+0.078]  +0.038
    trail .50/.50       +0.036   [+0.005,+0.064]   +0.014        +0.031 [-0.002,+0.066]  +0.032

**Why this is not addendum 12 again.** Addendum 12 killed the structure-keyed
bear trail because 94% of its gain sat in Mar–Apr 2025 (ex-window +$744 over
241 rows ≈ 0). It closed with two statements that this run tests exactly:
"trail .25/.50 dominates .50/.50 … recorded so the next bear-heavy window tests
the right knob first", and "what would settle it: a second sustained bear
drawdown in the book." Feb–Apr 2026 is that drawdown, and the backfill is now
complete. On the completed book:

- ex-Mar–Apr-2025 Δ is **+0.020** (was ≈ +0.003 in July) — the effect no longer
  lives in one window;
- **2026 alone is +0.028 with CI [+0.009, +0.053]**, i.e. the new, independent
  bear window confirms it on its own;
- positive in all three years (+0.036 / +0.055 / +0.028) and in both pricing
  tiers (real +0.054 / tweak +0.027);
- LOO-by-date: every fold positive (min +0.038) — the test that killed the
  per-regime switch twice.

BE ratchet @.50 is preferred over the trails on robustness, not on pooled size:
it is the only config whose 2026-alone CI excludes zero and its pooled CI is
the tightest. Mechanically it converts 44 rows into `be_stop` and cuts
stop_loss 110 → 92 — it stops giving back excursions, which is precisely the
|MAE|/MFE ≈ 1.1–1.4 mirrored-path signature of bear rows.

**It must be bear-KEYED.** The same config on the non-bear debit book is
+0.234 → +0.209 (−0.026); this is why Attempt 10 was right to remove the global
debit trail and why the correct scope is the structure, not the whole side.

**Honest size.** −0.133 → −0.092 mean R: it cuts the bleed by ~31%, it does not
create an edge, and −$54.4k → −$38.0k over 332 rows. Every bear row in the book
is ladder tier C (299) or VETO (71) — **none are deployed by the shipped
ladder**, so this rule only bites on positions the operator takes deliberately.
That is exactly the stated use case (the chop hedge), which is what makes it
worth shipping despite the modest size.

Credit side (bear_call, n=38): `pt .50` clears CI+LOO (+0.344) but the best
config `sl 1x` does not (CI [−0.012, +1.252]), the population is one year deep,
and bear_call is already structure-vetoed at intake with 0 emissions since. **No
credit-side change** — nothing to apply it to.

### 4. What this changes

- **The bear_put implementation question (open since 07-22) now has a
  non-demotion answer**: keep bear structures selectable, keep them out of the
  deployed top-3 (they are already C/VETO), and give them their own exit
  profile. Selection stays unfixed because it is unfixable from these columns.
- **Recommended (NOT shipped — operator decision):** a structure-keyed exit
  clause for bear debit spreads, `be_after: 0.50`, alongside the existing
  `regime_exit` block in `config/backtest.yml`, plus the matching line in
  `deployment-rules.md` §"Exit management": *if you are holding a bear debit
  spread, move the stop to breakeven once it has made 0.5× the debit.*
- **The ML question is closed** for this feature set. Re-open only on new
  columns, not on new models — the ablations say the columns, not the
  estimator, are the binding constraint.
- Unchanged: no production config, prompt or ladder was modified by this run.

---

## 2026-08-11 addendum — `mech_cell` BACKFILLED across the analysis tabs + nightly job

Plumbing, no tuning conclusion. `mech_cell` shipped 2026-07-22 (archive/06
addendum 9) but only stamps rows written after it, so the deploy-time surface
was blank for the whole history and `NO_DATA` wherever the SPY/VIX table had
been stale. Both are recoverable: the label is a pure function of the signal
date and the frozen table.

- `scripts/backfill_mech_cell.py` — recomputes every row, fills blanks and
  `NO_DATA`, and KEEPS a stored label that no longer reproduces (logged as
  DRIFT, exit 2) rather than overwriting it; `--force` overwrites, `--dry-run`
  reports. Writes only that one column, so formulas and every other column are
  untouched. `make backfill-mech-cell` (depends on `mech-regime`).
- `.github/workflows/backfill-mech-cell.yml` — chained on Compile Flow
  (`workflow_run`), which refreshes the SPY/VIX table at 22:30 UTC, so the job
  can never label off a stale close. Idempotent; nothing to fill = no write.
- Run 2026-08-11: **1,284 cells filled across 1,620 rows / 3 tabs, 0 DRIFT** —
  every one of the 336 previously-stored labels reproduced exactly, which is the
  first end-to-end check that the stored column and `lib/mech_regime.py` agree.
  AnalysisClaude now reads 142 dates, 2024-06-17 → 2026-08-10: BEAR_HE 758 /
  LVOL 728 / RB_EVOL 43 / NONE 78, no blanks, no NO_DATA.

**Header drift found while doing it (fix written, NOT yet applied).**
AnalysisGPT and AnalysisTickerSpecific headers had stopped at 24 columns
against a 27-column `ROW_COLUMNS` — GPT missing `iv_pct`/`price_vector`/
`days_to_earnings` plus pre-rename `ConvictionScore`/`ConvictionScoreLabel`,
TickerSpecific missing `iv_skew`/`iv_pct`/`score_catalyst`. Because
`append_rows` writes POSITIONALLY, every column past the gap is mislabelled on
those tabs, and a column-keyed write lands in the wrong place. Data loss: none —
all 13 rows on those two tabs are empty past `created_datetime` (both tabs are
near-unused). `scripts/align_tab_headers.py` repairs it (relocating a
schema column that is merely misplaced, aborting the tab if a drifted column
holds data that is not in the schema); dry run is clean, the write is pending
operator approval. AnalysisClaude — the tab everything reads — was already
correct.

---

## 2026-08-11 addendum — `bs_options_hist` DROPPED: measured as effect-diluting and replay-contaminating; tier now off behind `proxy.bs_fallback`

Scratch cut on the same 08-11 exports (`bs_tier_decision.py`, read-only, no
config changed). Question from the operator: keep BS, or evaluate on
real+tweak only.

**Calibration is impossible and the tier knows it.** 0 same-key overlap rows
(no play is priced both real and bs — the chain is strictly ordered, so BS is
never checked against a real mark), and `pct_real_days = 0.00` on **all 301**
bs rows. There is no bs row anywhere in the book with a single real price day.

**What is actually lost by dropping it:** 301 rows (27% of the pooled book)
but **0 dates** — every bs date also carries real/tweak rows. The tier is
overwhelmingly the long-dated filler: 69% of the DTE≥180 band is bs (208 of
302 rows), vs 5% of ≤30 DTE and 5% of 31–59. Dropping bs therefore removes
almost nothing from the ≤60-DTE band the ladder actually deploys in.

**The dilution finding (this is the real reason, not the $).** BS marks are
tail-compressed: E sd 0.86 vs real 1.38 / tweak 1.24, `|E|>2` at **2.3% vs
12.1% real**. Flat-ish donor vol, no spread, no gaps — so every bs row sits
nearer zero than a real one, and pooling shrinks **every** effect toward zero
in the same direction:

    bucket            r+t E     pooled E   (bs pulls toward 0)
    bull_call        +0.672  →  +0.540
    tier A           +0.688  →  +0.590
    tier B           +0.601  →  +0.495
    bear_put         −0.528  →  −0.394
    bear_call        −1.240  →  −1.054
    tier VETO        −0.548  →  −0.432

That is attenuation bias against exactly the separations the ladder is built
on. No sign flips and no shipped conclusion reverses (year signs, structure
ranking, ladder monotonicity, bear_put DEMOTE all hold either way — holdout
r+t is E −0.406 CI [−0.517, −0.295] vs pooled −0.358), so bs has **never been
load-bearing for a decision**; it has only ever made true effects look weaker.
Where bs *can* be compared like-for-like (DTE≤59, n=20) it does not track
real: E −0.220 vs real +0.026, sd 1.83.

**It is not merely a headline-$ problem — it enters the replay.** bs supplies
**64 of the top-3/day A-then-B picks**, worth +$8.5k of model-priced P&L, and
inflates the 2026 replay from **+$3.3k (r+t) to +$8.8k (pooled)**. The 08-11
"quote real+tweak only" rule was framed as reporting hygiene; it is actually
a selection problem. Total bs $ is +$51.6k of the +$65.7k pooled, +$48.9k of
that in DTE≥180 (single SNDK 04-06 long_call DTE 182 = +$27.5k).

**Decision — SHIPPED same day (operator approved).**

1. *Evidence layer:* real+tweak is the ONLY population for E, R, $, MFE/MAE,
   ladder tiers, holdouts, and the replay. bs is coverage bookkeeping, never
   evidence. Same standing as the 07-27 §3 long-dated rule.
2. *Chain layer:* `_method2` is now opt-in behind **`proxy.bs_fallback`
   (default `false`)** in `config/backtest.yml`, gated in `_evaluate`
   (`scripts/backtest/proxy.py`). Directional plays fall to `underlying_trend`,
   which answers the same question honestly (direction verdict, blank P&L,
   `exit_basis=NONE`) instead of minting a P&L number that reads as data. Only
   2 rows in the whole book (1 straddle, 1 strangle) would go from bs to
   `unevaluable`; existing bs rows stay frozen unless `--redo`. Cost: no
   path/MFE estimate for long-dated — but a tail-compressed BS path was never
   a usable one. Kept as a flag rather than deleted so the tier can be revived
   for a deliberate study; two tests pin both branches of the chain
   (`test_evaluate_skips_bs_tier_by_default_and_falls_to_underlying_trend`,
   `test_evaluate_uses_bs_tier_when_bs_fallback_enabled`). Docs synced:
   `config/backtest-reference.md` fallback-chain section + `proxy_method` row,
   `docs/architecture.md` proxy map, proxy.py module docstring.
3. *Historical rows are NOT purged.* The 301 existing `bs_options_hist` rows
   stay in BacktestProxy — filter them out at read time by `proxy_method`
   (equivalently `pct_real_days == 0`); the flag only stops NEW ones.
4. What this does NOT fix: the long-dated blind spot itself. Removing bs makes
   the gap visible instead of papered over; the fix is still real long-dated
   price history.

---

## 2026-08-11 — completed-book analysis: holdout coverage FULL, DEMOTE fires at n=164; bs long-dated rows contaminate pooled $ totals

Source: fresh exports `backtests/to_evaluate/analysis - BacktestResults.csv`
(406 rows) / `- BacktestProxy.csv` (796), stamped 08-11 15:38. Pooled priced
book after dedup: **1,118 rows** (real 406 / tweak 411 / bs 301), 118 dates,
2024-06-17 → 2026-04-07. Scratch cut (read-only), no config changed. Operator
instruction: treat the run as complete even though some analyses are flagged
for rerun. Housekeeping: 0 within-real dups (03-06 fix held); all 7
previously-missing holdout dates present; 02-17/02-19 present in both tabs.

### 1. Year breakdown — 2025H1-only profit confirmed; 2026 is the only year with CI fully below zero

    year   n     mean E   CI95 (date-clust)     R        $ (real+tweak)
    2024   295   −0.018   [−0.195, +0.152]      −0.059   −$14,355
    2025   499   +0.091   [−0.037, +0.213]      +0.145   +$47,893
    2026   324   −0.196   [−0.287, −0.101]      −0.055   −$19,503

    halves: 2024H1 −0.198 · 2024H2 +0.009 · 2025H1 +0.136 (+$78.0k pooled) ·
            2025H2 −0.181 · 2026H1 −0.196
    MFE/MAE by year: |MAE|/MFE 1.13 / 0.79 / 1.18, R-capture −0.08 / +0.16 /
    −0.09 — only 2025 has upside asymmetry; 2024/2026 mirrored = path-vol.

**⚠ Pooled-$ contamination (new standing hazard).** Pooled realized $ reads
+$65.7k, but **+$48.9k of it is DTE≥180 `bs_options_hist` rows with
`pct_real_days = 0.0`** — pure flat-vol BS marks on exactly the contracts the
2026-07-27 §3 rule says carry no evidence. One row (04-06 SNDK long_call,
DTE 182) is +$27.5k by itself; the 04-06 NVDA/MRVL long_calls (DTE 722/725)
add +$9.6k. The honest book is **real+tweak: +$14.0k total** (−$14.4k / +$47.9k
/ −$19.5k by year). Any headline $ from these exports must be quoted
real+tweak; the pooled figure is not a portfolio number.

### 2. Structure breakdown (pooled / real+tweak E)

    structure          n(pooled)  E pooled  E r+t    R       $ r+t
    bear_put_spread    468        −0.394    −0.528   −0.081  −$44,000
    bull_call_spread   338        +0.540    +0.672   +0.295  +$80,237
    bull_put_spread    237        +0.101    +0.183   −0.005   −$1,946
    bear_call_spread    43        −1.054    −1.240   −0.518  −$11,221

    year × structure (E): bear_put −0.41/−0.43/−0.35 (negative every year);
    bull_call +0.44/+0.66/+0.29 (positive every year — still the only
    reproducing positive); bull_put +0.24/+0.25/−0.17 (2026 out-of-band
    DTE-driven as before); bear_call −1.97/−0.70/— (0 emissions 2026 —
    intake veto holding).

### 3. Ladder reproduces on the completed book

    tier    2024            2025            2026
    A       +0.708 (n=37)   +0.670 (n=105)  +0.305 (n=45)
    B       +0.338 (n=88)   +0.644 (n=98)   +0.431 (n=13)
    C       −0.294 (n=131)  −0.299 (n=207)  −0.278 (n=249)
    VETO    −0.586 (n=39)   −0.294 (n=89)   −0.803 (n=17)

A/B positive, C/VETO negative every year. Top-3/day A-then-B replay:
2024 +$22.7k (64% win) · 2025 +$44.8k (67%) · 2026 **+$8.8k** (66%, mean R
+0.364). 2026 Tier A improved +0.210 → +0.305 with the late dates added —
the 08-08 "genuinely weaker Tier A" worry softened. bull_put band in-window:
in-band E +0.431 / R +0.337 (n=13) vs out-of-band −0.139 / −0.211 (n=59) —
second independent window, band holds.

### 4. bear_put holdout at FULL coverage — all three pre-registered criteria fire

    n=164 priced (was 82 at the 08-04 mid-stop)
    mean E −0.358   date-clustered bootstrap CI95 [−0.460, −0.256]
    halves: early −0.207 (n=87) / late −0.529 (n=77)  ← late worse, as predicted
    ex-flawed-dates (02-23/03-02/03-20): −0.380 (n=154)
    → mean E < 0 PASS · CI upper < 0 PASS · both halves < 0 PASS → DEMOTE

The 08-04 real-tier discordance is **resolved downward**: real E −0.169
(n=51; was +0.201 at 08-04, −0.178 at 08-08) vs tweak −0.569 / bs −0.204.
Real R +0.047 — the "negative unmanaged, ~breakeven only under active risk
control" framing survives verbatim. Measure-dependence caveat stands: R-based
read is −0.086 CI [−0.215, +0.042] (includes zero), halves +0.042 / −0.232
deteriorating into the bottom. Comparator bull_call in-window: E +0.293 /
R +0.315 (n=43), |MAE|/MFE 0.51 vs bear_put 1.25 — same discriminator as
addenda 14/07-29.

**Status.** The addendum-13 criteria are now satisfied on the completed
second drawdown via this scratch cut. The formal decision run remains
`bear_position_study.py` unmodified on the window (its `AC_PATH`/`BR_PATH`/
`BP_PATH` need repointing to these exports first — the 08-04 flag #2 is
still true). Given the operator's "treat as fully run", the demotion is
decision-eligible NOW; what remains is the implementation choice (intake
`structure_veto` like bear_call vs ladder VETO tier vs leave-at-C-never-
deploy) — a user decision, deliberately not taken here.

### 5. Next study: ML combination search — plan written, NOT run

Pre-written plan at [`ml-plan.md`](ml-plan.md): learn which structure ×
regime × entry-geometry × enrichment combination best predicts play outcome,
benchmark = the shipped score-free ladder's top-3/day replay, purged
walk-forward CV clustered by date, real+tweak training only, pre-registered
ship criteria. Nothing executed as of this entry.

---

## 2026-08-08 — year-split evaluation on refreshed exports: 2025 IS the outlier for the raw book; the ladder separation is what reproduces per year

Source: fresh unversioned exports in `backtests/to_evaluate/` (`analysis -
BacktestResults.csv` 384 rows / `- BacktestProxy.csv` 738). Pooled priced book
after dedup (date|ticker|structure|play): **1,043 rows** (real 384 / tweak 381 /
bs 278), 2024-06-17 → 2026-04-02. Read-only scratch cut; no config changed.
Housekeeping vs the 08-04 mid-stop flags: **#1 the 2026-03-06 wholesale
duplication is GONE from this export** (0 within-real dups found), **#2 the
stale-export problem is resolved by this drop**, **#4 02-17 and 02-19 are now
present in both tabs**. Still missing from the holdout window: 03-18,
03-23→03-26, 04-06/04-07 (7 of 32 dates, the block nearest the episode bottom).

### 1. The unfiltered book has no standalone edge — 2025H1 is the only positive half-year of five

    year   n    mean E   E CI95 (date-clust)   R       $ realized
    2024   295  −0.018   [−0.193, +0.149]      −0.059   −$11,391
    2025   499  +0.091   [−0.036, +0.214]      +0.145   +$63,669
    2026   249  −0.243   [−0.344, −0.140]      −0.051   −$11,505

    half-years: 2024H1 −0.198 · 2024H2 +0.009 · 2025H1 +0.136 (+$78.0k) ·
                2025H2 −0.181 (−$14.4k) · 2026H1 −0.243 (−$11.5k)

Net book +$40.8k, all of it 2025. **Answer to "is 2025 an outlier": for the
take-everything book, yes** — and it is NOT the Mar–Apr window doing it (2025
ex-window E +0.184 beats in-window +0.001; the window has fat realized dollars
+$42.6k but flat expectancy on huge n=254). MFE/MAE agrees: 2024 and 2026 are
mirrored (|MAE|/MFE 1.13 / 1.26, R-capture −0.08 / −0.09 — path-vol by the
asymmetry rule); only 2025 shows upside asymmetry (0.79, capture +0.16).

### 2. What DOES reproduce in all three years: the ladder separation

Tier means on E (deployment-rules.md ladder recomputed from row fields):

    tier    2024            2025            2026
    A       +0.708 (n=37)   +0.670 (n=105)  +0.210 (n=34)
    B       +0.338 (n=88)   +0.660 (n=103)  +0.431 (n=13)
    C       −0.275 (n=135)  −0.291 (n=215)  −0.322 (n=185)
    VETO    −0.691 (n=35)   −0.402 (n=76)   −0.803 (n=17)

A/B positive and C/VETO negative in **every** year (A<B inversion in 2026 is
within thin-n noise; both positive). Top-3/day A-then-B replay is positive every
year: 2024 +$22.7k (64% win) · 2025 +$44.9k (67%) · 2026 +$5.9k (65%, mean R
+0.374). The bull_put band separates every year (in-band vs out E: 2024 +0.51 /
+0.10 · 2025 +0.83 / −0.08 · 2026 +0.34 / −0.44 — 2026 out-of-band is again
DTE>59-driven, −0.456 over 40 rows). bear_put E is negative with CI upper < 0
in each year separately (−0.41 / −0.43 / −0.32); bear_call is disastrous in
both years it appears (−1.97 / −0.70).

**So "is there proven edge": not in the analysis-as-emitted — the edge that
survives a year split is entirely SELECTION.** The system's claim is "the
ladder finds the deployable 20%", not "the plays make money" — 2024 proves it
(book −$11.4k take-everything, +$22.7k top-3 replay, and the −$36.6k of 2024
bear-structure losses are exactly what the ladder screens). Standing caveat
unchanged: the ladder was derived on this same pooled book, so per-year
consistency is robustness, not out-of-sample proof — the live walk-forward
remains the only true test.

### 3. The 2026 read: mostly composition, partly a genuinely weaker Tier A

2026 = the Feb–Apr bear episode, nothing else (29 dates, 02-02 → 04-02). It is
**57% bear_put by row count** (141/249) — the model answered a bear tape by
emitting its known-worst structure in size. Ex-bear_put 2026 is −0.138 (n=108,
median +0.002) — weak, not disastrous; the deployable A/B slice is +$6.6k. The
genuine warning is **Tier A at +0.21 vs +0.71/+0.67 in prior years** (n=34,
median +0.18): the flagship bull_call cell is much thinner in a bear episode,
as it should be directionally, but it has not yet been negative.

### 4. bear_put holdout: all three pre-registered criteria fire again at near-full coverage

Feb–Apr 2026 window, n=141 priced over 27 dates (08-04: 82/16):

    mean E −0.324   CI95 [−0.448, −0.202]   halves −0.154 / −0.496   → DEMOTE
    R −0.033 (exit rules still rescuing ~0.29 of E)

Late half twice as negative as early — deterioration into the episode bottom,
the wrong direction for a bear structure in a bear market. The 08-04 real-tier
discordance has **softened**: real is now E −0.178 (n=40) vs tweak −0.474 —
no longer positive, though real R is +0.135 (+$9.3k), keeping the addendum-14
framing "negative unmanaged, breakeven only under active risk control" alive.
Formal decision still waits on `bear_position_study.py` unmodified over the
completed window (7 dates outstanding), but this is the third consecutive read
where every criterion fires, now at 141 rows.

### 2026-08-08 addendum — year × regime × structure screens: the only reproducing POSITIVE cell family is bull_call; everything else that reproduces is a negative

Same pooled 1,043-row book, grouped by year × market_regime (direction / vol /
cell), year × stock (per-play) regime (leading BULL/BEAR/RANGE token of the free
text), and year × structure crosses. Screens required n≥8–10 per year present
and same-sign mean E every year; 24 cells tested across the three screens (few
enough that the consistent ones are not a multiplicity artifact — and they
cohere into one factor rather than scattering).

**Positive, every year present (the entire list):**

    bull_call × market-RANGE   +0.71 / +0.60 / +0.15   CI[+0.31,+0.81]  (= Tier A)
    bull_call × stock-BULL     +0.24 / +0.74 / +0.05
    bull_call × BULL (mkt)     +0.30 / +0.60 / — (no 2026 BULL dates)
    bull_put  × BULL (mkt)     +0.19 / +0.59 / — (thin, no 2026 test)
    bull_call × BEAR+E-VOL     — / +1.04(n=17) / +0.38(n=9)  (new, thin, contrarian)

Every one is long-delta. The 2026 magnitudes shrink toward zero (+0.15/+0.05):
the cell survives sign-wise through the bear episode but the edge is thin there.

**Negative, every year present:** bear_put × {BEAR, BULL, RANGE} market,
bear_put × {stock-BEAR, stock-RANGE}, bear_put × four market cells,
bear_call × stock-BEAR, bull_put × {BEAR+E-VOL, RANGE+E-VOL},
market H-VOL pooled (−0.69/−0.33/−0.10), market BEAR pooled
(−0.73/−0.23/−0.29), stock-BEAR pooled (−0.51/−0.55/−0.26).

**Reads.** (1) The "proven edge" grouped this way is ONE positive factor —
long-delta debit structures in non-bear-labelled conditions — surrounded by
reproducing negative knowledge; the ladder is close to the best available
partition of this book. (2) bear_put is negative in every year × every market
direction × every stock regime — the demotion needs no regime qualifier.
(3) H-VOL is negative all three years *unconditionally*, suggesting the shipped
BEAR+H-VOL veto may be the narrow version of a vol-only veto (H-VOL 2026 is
only −0.10, so not actionable without the missing dates). (4) bull_put ×
RANGE+E-VOL is negative all three years (−0.20/−0.04/−0.03) — the current
Tier-B band admits these; a regime qualifier is a candidate, not a rule.
(5) Alignment cut (structure direction vs stock regime) adds nothing: "with"
flips sign by year; "against" is positive every year on comedy n (10/20/6).
(6) stock-RANGE rows are E-negative but R-positive all three years — exits
extracting from chop; composition unexamined, not evidence. No 2026 data
exists for market-BULL or C-VOL, so the strongest 2024/2025 cells are simply
untested in 2026. Standing circularity caveat applies — these crosses are
re-derivations on the derivation book, now with per-year sign checks.

### 2026-08-08 addendum — bear_put MFE re-check on the refreshed book: addendum-14's "volatility, not direction" read reproduces; exit is already rescuing ~0.32

User asked whether the ten-cell demotion read means bear_put *never* went into
profit, or whether the exit is the fixable part. Recomputed on the refreshed
1,034-row deduped pool (bear_put n=424: 146 real / 160 tweak / 118 bs):

    MFE  mean +0.692  median +0.392  reach+0.30 57%  reach+0.90 29%  never>0 16%
    E    mean −0.392  median −0.897        R  mean −0.069
    give-back MFE→E +1.084   exit rescue R−E +0.323
    mfe_day 20 vs mae_day 40, MFE-first 71%
    of 241 rows reaching MFE +0.30: 61% end E<0 (held to cap), 38% end R<0

Same shape in each year separately (2026 holdout n=132: MFE +0.585, E −0.325,
rescue +0.29) and worst in the REAL tier (E −0.517, give-back 1.36) — the bs
tier is the only benign one (E −0.02), so real pricing makes it worse, not
better. bull_call comparator: give-back only 0.541, E +0.538. Answer stands as
addendum 14 ruled: the excursion is round-trip volatility, not harvestable
edge — the shipped exits already extract ~0.32 of E, the structure-keyed trail
was tested (addendum 12) and was one-window. No new cut type, no config change;
per addendum 13 the next move on bear_put is the completed holdout, not
another exit variant.

Follow-up cut, same session — "was bear_put a good choice IN the Feb–Apr 2026
bear episode": no, even there. In-window bear_put (n=132) E −0.325 / R −0.035 /
−$1.9k vs in-window bull_call (n=36) E +0.193 / R +0.312 / +$4.7k — the
long-delta structure beat the bear structure inside the bear episode itself
(rhymes with addendum 14's "bull_call beats bear_put inside mechanical BEAR
cells"). Timing decomposition: Feb entries R +0.125 (60% win, +$6.7k), Mar flat,
Apr catastrophic (R −0.700, 9% win, −$8.2k); early/late halves split at 03-06:
+$10.0k / −$11.9k. Even the February winners are exit-manufactured — Feb E is
still −0.205, the rescue is the early-run harvest before the rebound. Real tier
in-window R +0.131 (+$8.9k) keeps the addendum-14/08-04 framing "negative
unmanaged, breakeven-to-positive only under active risk control". Caveat the
right way: the 7 missing holdout dates are the block NEAREST the bottom
(03-18, 03-23→26, 04-06/07) — i.e. more late-window rows, the worst slice, so
completion should make the window read worse, not better.

Full path re-read of the same window (user flagged the cut above used only
E/R — asymmetry rule applied): bear_put in-window |MAE|/MFE **1.13** (mirrored
= path-vol by the standing rule), capture R/MFE −0.06, 59% of MFE≥+0.30 rows
round-trip to E<0 (exits recover about half: 32% still end R<0). bull_call
in-window is genuinely asymmetric — |MAE|/MFE **0.56**, capture +0.36, only
17% round-trip — so the bear-window inversion is not two flavors of noise; one
structure has real upside asymmetry there and the other doesn't. Month
asymmetry marches 0.89 (Feb) → 1.11 (Mar) → **4.34** (Apr: MFE +0.215,
mfe_day 8.5, MAE −0.934 late = bought the bottom, small pop, rebound ran them
to −100%). Even Feb's positive R (+0.125) sits on 64% round-trip — exits
harvesting path-vol, not direction. bull_put's in-window failure is the
opposite shape: |MAE|/MFE 2.21, capture −0.53, LOW round-trip (23%) — genuine
adverse direction (E-VOL short-put), not path-vol; different problem, different
cell (the RANGE/BEAR+E-VOL screen). Real-tier bear_put is the most favorable
path read (0.82, MFE med +0.70, mfe_day 13) and still E −0.134 with 48%
round-trip.

Qualifier sweep, same session (user hypothesis: "bear_put feels safer in bear
markets — maybe it's the qualification step"). Both bear windows cut
(Feb–Apr 2026 n=132 / Mar–Apr 2025 n=105); only the two pre-registered
qualifiers are decision-relevant, the rest is post-hoc:

- **"Safer" is TRUE as a tail claim** — in-window managed bear_put loses
  $14.6/row with 1% of rows at R≤−0.90 (min −$1.6k) vs bull_put −$141.8/row
  with **23%** at R≤−0.90 (min −$5.0k). Defined-risk debit + early MFE +
  shipped exits = small bounded losses. Safety yes; expectancy no — no
  qualifier cell is E-positive in both windows.
- **iv_spread ≤ 0 (shipped Tier-C rule): 6th right-signed confirmation** —
  2026 keeps R +0.089/+$3.9k (n=27) vs skips R −0.219 (n=6); 2025 same sign.
  But **99/132 window rows have iv_spread MISSING** (unenriched holdout
  dates) — the shipped qualifier is blind on 75% of the window; the action
  item is the existing 7-date backfill, nothing new.
- **|delta| 0.30–0.45 recorded cut: DEAD** — right-signed 2026 (E +0.142,
  n=17), sign-flips 2025 (E −0.972, R −0.161 vs outside +0.067). The
  addendum-14 "mean carried by tails" suspicion confirmed on the other window.
- **New post-hoc candidate, motivating only: LOW entry IV** — iv_entry_pct
  below-median is R-positive in BOTH windows (+0.051/+$6.0k · +0.347/+$20.5k,
  asym 0.57) and above-median negative in both (−0.120 · −0.298, asym
  1.39/1.89). Textbook mechanism (don't pay elevated vol for a debit spread
  late in a selloff) but confounded with episode age (IV rises into the
  bottom, and the timing split is the same shape), and E is negative in both
  low-IV halves (−0.481/−0.686) — it selects which bear_puts the exits can
  rescue, not an edge population. Park next to the early/late finding as
  probably one factor.
- score_total ≥ 70 anti-selects in both windows again (R −0.096/−0.301).

Net: qualification can move managed bear_put from ~breakeven to modestly
positive (early-episode ∧ low-IV ∧ iv_spread≤0 slices) but uncovers no
positive-E sub-population; the demotion question is expectancy, and stands.
Per addendum 13 none of this is decision-eligible — finish the backfill,
run the pre-registered study.

---

## 2026-07-27 — the pre-engine discretionary book, and the long-dated blind spot

Source: `portfolio/` (IBKR flex exports, 468 closed trades, 2025-02-03 →
2026-07-24, +$10,634). **This is pre-engine and mostly pre-June-2026** — it is
a portrait of how the operator trades by hand, NOT a test of the engine and not
a holdout. Treat every comparison below as directional, not evidential: n per
structure is 7–26, unconditioned by regime, and discretionary in sizing/timing.

### 1. What the discretionary book independently confirms

- **Cadence.** P&L per trade by same-day trade count is monotone decreasing:
  1/day +$119 (n=67) · 2–3/day +$25 (n=160) · 4–6/day +$9 (n=109) · 7+/day
  **−$18** (n=132). Win rate is flat (51–59%) across all four, so this is
  dilution, not worse reads on busy days. The ladder's 1–3 positions/day cap
  came from capital constraints, not this data, and it lands on the knee.
- **Concentration.** Top-3 trades = the entire book: ex-top-3 the book is
  **−$5,004** over 465 trades; ex-top-10 it is −$20,478. Compare the ladder's
  derivation finding (top-3/day = 28% of positions, 83% of book P&L).
- **DTE.** 0DTE −$541 · 1–14d −$1,857 · 15–45d +$5,940 · 45d+ +$7,093.
- **The bull_put DTE band reproduces out-of-sample.** His 26 bull put spreads,
  never seen by the engine: DTE ≤22 → n=14, **−$1,805**; 45–59 → n=4, **+$443**.
  That is the PROVISIONAL 45–59 preference in `deployment-rules.md` landing on
  independent, real-fill, human-executed data. Weak n, right sign.

### 2. What it contradicts (noted, NOT actioned)

The four engine verticals total **−$1,952** over 58 trades in his book; all
+$10,072 of profit came from naked/single-leg and calendars, which the engine
does not emit. Tier ordering also inverts: bull_call (Tier A) 36% win /
−$1,652 (n=14, one TSM trade = −$2,101 of it); bear_call (hard VETO) 86% win /
+$479 (n=7). **Not evidence against the ladder** — no regime conditioning, no
delta/DTE gating, tiny n, and discretionary entry timing. Recorded so it is not
rediscovered as novel later.

### 3. The long-dated blind spot (the real finding)

`deployment-rules.md` is **in practice a ≤60-DTE ladder, and not by design.**

Pooled across all `backtests/results*.csv` + `proxy_results*.csv` (203 unique
plays), 36% of what the engine emits is horizon ≥180:

| horizon | 14 | 60 | 180 | 720 |
|---|---|---|---|---|
| real-priced | 4 | 42 | 8 | 1 |
| proxy (skipped by real backtest) | 2 | 73 | 54 | 19 |

53 of 54 h=180 rows and **19 of 19** h=720 rows were skipped with
`skip_reason = no_history`. Barchart's options history does not carry those
contracts, so they never got real prices and never entered the ladder's
evidence base. Nothing in `ANALYSIS_PROMPT_CONTRACT` blocks long-dated —
`structure` already lists "long call", `horizon` already has 180/720 buckets,
and the DTE-discipline rule already says default ≥45 DTE. The pipeline has been
dropping the rows, not the prompt.

**The BS proxy cannot substitute here** (user challenge, correct — my first
suggestion, "fix `path_cap_days` and 73 rows become readable", was wrong):

- All 45 long-dated `bs_options_hist` rows have **`pct_real_days = 0.0`**. Not
  partially modeled — zero days of those paths came from a real quote.
- `_method2` (`scripts/backtest/proxy.py:450-478`) prices the target leg off a
  **donor contract at a different expiry**. For a 500-DTE leg the donor is
  necessarily far shorter-dated — that is why the real leg had no history. Term
  structure is unmodeled at the horizon where vega dominates. Worst possible
  place for flat-vol BS.

So the real evidence base is 21 rows, not 73:

| | n | mean | win | MFE | MAE |
|---|---|---|---|---|---|
| `strike_expiry_tweak` (real-priced), h≥180 | 21 | −0.46 | 24% | +0.41 | −0.96 |
| of which h=180 / h=720 | 20 / **1** | | | | |

**At h=720 there is no evidence either way (n=1).** The 21-row negative also
does not settle it: those are spreads (MAE −0.96 = defined-risk structures
going to near-total loss), and all are still scored under `path_cap_days: 120`
and `time_exit_dte_fraction: 0.75` — 23/49 h=180 and 14/17 h=720 rows exit
`cap_open`, i.e. marked at an arbitrary date rather than a real exit.

**Shape note.** The operator's three book-carrying trades were long-dated
*instruments* on **short holds**, not hold-to-expiry: TSM 276 DTE held 69d
(25% of DTE), GLD 246 DTE held 82d (33%), GOOG 205 DTE held 121d (59%). Buying
convexity with theta off, then leaving on the move. The current exit config
would hold that TSM call 207 days. Any future long-dated test must model this
shape, not hold-to-expiry.

**Status: BLOCKED, not queued.** The blocker is real long-dated option price
history, and no re-read of existing rows fixes it. Only lead is IBKR
(`get_price_history` / `get_option_data` over the connected MCP) — unprobed,
user deferred 2026-07-27. If IBKR has no depth on 180+ DTE contracts, the only
route is paper-forwarding long-dated plays live. Do NOT ship a long-dated tier
off BS rows.

### 4. Live substitution — the operator sometimes trades naked where the engine said spread

Reported by the user 2026-07-27. When the analysis emits e.g. a bull call
spread, he sometimes buys the naked long call instead.

**Why it matters:** it silently breaks the live walk-forward's attribution. A
naked long call and its debit spread share direction and entry but not payoff,
max loss, vega, or exit behaviour — the spread caps upside where the naked leg
carries the convexity that produced 100% of this book's profit. Any live-vs-tier
comparison that assumes the deployed position matches the emitted `structure`
will mis-attribute both wins and losses, in the direction of making the ladder
look wrong when the substitution was the variable.

**Action:** the live walk-forward eval must record the **structure actually
traded** alongside the emitted one and split on divergence, before any live
result is read against tier means.

`backtests/live_loop/stage1_map_fills.py` already derives both sides —
`classify_structure()` from the IBKR fill and `play_structure()` from the play
text — but its match confidence is only `EXACT` / `STRUCTURE` / `NONE`, with no
substitution category. A naked long call filled against a `bull_call_spread`
play therefore falls to **`NONE`, indistinguishable from "no play that day"**:
substitutions are silently dropped from the eval rather than labelled. Adding a
`SUBSTITUTED` confidence (same ticker, same direction, different structure) is a
precondition for the eval, not a nice-to-have — otherwise the deployed book
being read is exactly the subset where he followed instructions, which biases
the live-vs-tier comparison in an unknown direction.
This is also the one channel through which the long-dated question could get
answered by accident: if he substitutes naked long-dated calls for h≥180
spreads, those fills are real prices on exactly the contracts the backtest
cannot reach.

---

## 2026-07-22 — bear_put demotion: the open thread

### 2026-07-22 addendum 11 — bear_put demotion CANCELLED: it is an exit-shape problem, not a selection problem (user challenge, correct)

**User challenge:** "we changed our exit and bear_put becomes profitable, why do
we demote it?" Prompted a structure × (MFE, MAE, realized) re-read of the 913-row
pooled export. The challenge was right and queue #4 is withdrawn.

**My error, retracted.** I argued bear_put had shallow upside and that "an exit
rule can only harvest MFE that already exists." The premise was false. The
asymmetry reads that seeded the demotion (bear_put × iv_spread MAE −0.197,
score_dealer MAE −0.320) are *correlations with* MFE/MAE, and I read them as
statements about bear_put's MFE *level*. They are not. Level, pooled: mean MFE
+0.713 (real-priced +0.788), median +0.398; 58% of rows reach +0.30, 29% reach
the +0.90 PT.

**Path shape is the finding** (real-priced):

| structure | MFE-first | mfe_day | mae_day | PT exit | stop exit |
|---|---|---|---|---|---|
| bear_put  | **77.3%** | 17.0 | 41.0 | 23.9% | **29.3%** |
| bull_call | 38.2%     | 37.9 | 25.1 | 42.0% | 13.5%     |

bear_put runs early then bleeds; bull_call dips then runs. Opposite exit
treatment. **Attempt 10 removed the debit trailing stop POOLED**, and the debit
pool is dominated by bull_call (n=312, the dollar weight) — the "21 trail exits
sold continuations" evidence is bull_call's signature. bear_put was never tested
on its own path shape.

**Give-back (conditions on MFE ≥ X — LOOKAHEAD, motivating only, does NOT price
the rule):** of 206 bear_puts reaching +0.30, 43.2% finished red; at +0.50,
32.5% of 157. bull_call at the same cuts: 23.2% / 16.9%.

**Ceiling test — settles the dead-money claim:**

```
bear_put   realized  −$38.6k   perfect-foresight exit +$296.9k   headroom $335.5k
bull_call  realized +$133.6k   perfect-foresight exit +$467.5k   headroom $333.9k
```

Same extractable headroom as the engine structure. "Half the debit book earning
nothing" (§addendum, line ~104) is wrong as a *selection* verdict — the emissions
are fine, the exit is mismatched.

**Queue change:** #4 bear_put emission demotion → **CANCELLED**. Replaced by
**structure-conditional trailing stop for bear_put**, to run through the existing
replay harness (`scripts/backtest_study/exit_mechanism_study.py`, `combined_exit_study.py`)
under the addendum-4 corrected LOO gate. Not run yet.

**New concern to test in the same pass — possible composition proxy.** The
SHIPPED BEAR+H/E trail .50/.50 (addendum 7, +$4.4k per-cell) may be this same
effect found through the wrong key: if BEAR+H/E dates emit disproportionately
more bear_puts, a regime-keyed override is a composition proxy for a
structure-keyed one — the trap that killed `oi_confirm` and `iv_pct` (rule 7).
Test structure-keying and regime-keying head to head, and check the bear_put
share of BEAR+H/E rows. If structure-keying dominates it is both simpler and
drops the runtime dependency on the SPY/VIX table (addenda 9/10).

No code changed. No re-run performed.

### 2026-07-22 addendum 12 — structure-keyed bear_put trail RUN: does NOT ship, and it exposes the shipped BEAR_HE clause as a bear_put proxy that is NEGATIVE outside one window

Ran the addendum-11 follow-up: `scripts/backtest_study/exit_switch_structure_study.py`
(output `backtests/exit_switch_structure_study_output.txt`). Data, calibration,
dedup, post-13c join and gate thresholds are IMPORTED from
`exit_switch_mech_study.py` — same 663-row pooled debit book (real 250 / tweak
247 / bs 166), same harness validation (250/250 real debit rows reproduce
DEBIT_PROD, replay total $27,648.70 = stored to the cent). Only the KEY differs,
so a difference in answer cannot come from a difference in setup. Treatment is
the SAME frozen variant the mech switch uses for BEAR_HE (trail .50 / trig .50).

**Q1 — structure-keyed bear_put trail: right-signed, but it is ONE WINDOW.**

    bear_put (n=343)  PROD mean −0.1242, win 35.6%
    + V_TRAIL         mean −0.0925, win 38.8%   Δ +10.87 pnl_pct / +$11,781

Concentration check (the Attempt-13 July-2024 discipline):

    ALL                n=343   Δ +10.866   +$11,781   win 35.6%→38.8%
    Mar+Apr 2025       n=102   Δ +10.183   +$11,037   win 40.2%→48.0%
    EX Mar+Apr 2025    n=241   Δ  +0.683      +$744   win 33.6%→34.9%

**94% of the gain is Mar–Apr 2025** (the tariff drawdown — precisely the regime
where a bear_put runs then bleeds). Dates are diffuse (top-5 dates = 11.7% of
total, 10/17 months positive), so this is not a single-trade artefact; it is a
single *market window*, which is worse for a rule meant to generalise. Ex-window
the effect is +$744 over 241 rows ≈ nothing. **Structure-keyed trail: NO SHIP.**

Gate for the record: 5/6 PASS, failing only "LOO median > 0" — which fails **by
construction** for every sparse-cell switch (most dates have no rows in the cell,
so the fold gain is exactly 0 and the median is 0). The mech switch failed the
identical criterion in addendum 4. The criterion is uninformative here and should
be replaced by "median over AFFECTED dates" in any future exit-switch gate.

**Q2 — the shipped BEAR_HE clause is a composition proxy, and a lossy one.**

Composition: bear_put is 51.7% of the debit book but **63.9% of BEAR_HE rows**
(+12.1pp lift); 53% of all bear_puts sit inside BEAR_HE. Decomposition, each key
run on the other's complement (pooled; BEAR_HE clause alone, LVOL/RB_EVOL
excluded so this matches what is actually in `config/backtest.yml`):

    slice                              n_changed    Δpnl_pct        Δ$
    BEAR_HE clause, all rows                 285      +3.657     +4,416
    BEAR_HE clause, NON-bear_put only        103      −4.676     −4,929
    bear_put trail, all rows                 343     +10.866    +11,781
    bear_put trail, OUTSIDE BEAR_HE          161      +2.534     +2,436
    overlap only (bear_put AND BEAR_HE)      182      +8.333     +9,345

The shipped clause retains **−128%** of its gain on its own complement; the
structure key retains +23% of its. The overlap alone (+$9,345) is larger than the
whole BEAR_HE cell (+$4,416) — the non-bear_put two-fifths of the cell actively
**lose** $4,929. So BEAR_HE is not merely a proxy for bear_put: it is bear_put
plus a money-losing tail the regime key drags in.

**And the shipped clause has the same window dependence:**

    BEAR_HE clause  ALL           n=285   Δ +3.657   +$4,416
                    Mar+Apr 2025  n=121   Δ +5.624   +$6,426
                    EX Mar+Apr    n=164   Δ −1.967   −$2,010

**The one rule currently in production off this line of work is negative outside
Mar–Apr 2025.** That is not the pre-registered rollback trigger (which asks for
≥25 affected BEAR+H/E dates of NEW data and is untouched by a re-cut of old
rows), so this is NOT an automatic revert — but it is a live warning, and it is
the same window that carries the structure result, so the two findings are one
finding: **trail .50/.50 helps debit trades during a sustained bear drawdown, and
the key — regime or structure — is mostly picking out how much of that window a
slice contains.**

**Decisions.**
1. Structure-keyed bear_put trail: **NOT SHIPPED.** Stays a candidate.
2. BEAR_HE clause: **left in production, rollback trigger UNCHANGED** — the
   trigger is pre-registered on new data and re-cutting old rows must not be
   allowed to relitigate it (that is exactly the discipline addendum 7 bought).
   But its evidence is now known to be window-bound; **if the trigger evaluation
   is ambiguous, revert** rather than extend.
3. Exit-gate criterion "LOO median > 0" is retired for sparse-cell switches —
   replace with median over affected dates when this is next run.
4. The exploratory grid says trail **.25/.50** dominates .50/.50 on bear_put
   (+13.50 / +$16,196 vs +10.87 / +$11,781) and BE@.50 is close (+12.05 /
   +$13,438). NOT ship-eligible off this run (chosen post-hoc from the grid, and
   subject to the same Mar–Apr concentration). Recorded so the next credit- or
   bear-heavy window tests the right knob first.

**What would settle it:** a second sustained bear drawdown in the book. Until
then, both the shipped clause and the structure candidate rest on one window.

No production config changed. New file: `scripts/backtest_study/exit_switch_structure_study.py`
(read-only study, imports the mech harness).

### 2026-07-22 addendum 13 — PRE-REGISTRATION: bear-position study (written BEFORE the run)

Reason this is pre-registered rather than another cut: addenda 11–12 produced
three different verdicts on bear_put in one session (demote → don't demote →
maybe demote) because each was a post-hoc slice of the SAME 663-row book,
reported as a verdict. On a book this dominated by one window, post-hoc slicing
will keep generating verdicts. Everything below is fixed before running.

**Population.** All bear-direction plays in the pooled priced debit book
(real + proxy tweak + proxy bs, same loader/calibration as addenda 4/12).
Primary: `bear_put_spread`. Comparator: `bull_call_spread`. Any
`bear_call_spread`/`long_put` rows counted and reported, not analysed.

**Two outcome measures, both reported on every cut.**
- **E = `pnl_at_cap_pct`** — P&L at the last priced path day, computed
  independently of any exit rule (`simulate.py:267`). This is the SELECTION
  measure: no exit rule can rescue a structure whose E is negative.
- **R = `realized_pnl_pct`** under PROD — SELECTION + EXIT.
Discriminator: E<0 ⇒ selection problem. E>0 with R<0 ⇒ exit problem. This
replaces MFE, which addendum 11 leaned on and which only bounds the upside a
perfect exit could have reached.

**Window control.** W = Mar+Apr 2025 (declared now, from addendum 12: it
carries 94% of the structure-trail gain and flips the shipped BEAR_HE clause).
Every headline is reported ALL / IN-W / EX-W. Pricing tier (real / tweak /
bs-model) reported alongside per the standing split rule.

**Cuts — fixed, complete, no additions after the run.**
- C1 levels by structure × window, on E and R
- C2 date-clustered bootstrap (10k, cluster = signal_date) 95% CI on mean E and
  mean R for ex-window bear_put
- C3 time halves + per-month sign count, on E
- C4 mech cell × structure, on E
- C5 entry geometry — |delta| bands, DTE bands, `iv_entry_pct`, `iv_spread`
  sign — on E, ex-window decision-eligible, in-window reported only
- C6 deployment ladder (config/deployment-rules.md): do the existing vetoes /
  tiers already screen the bear_put losers?
- C7 path shape: mfe_day vs mae_day, and the MFE→E give-back

**Decision rule — fixed now.**
- **DEMOTE to veto** iff ex-window mean E < 0 AND the C2 bootstrap 95% CI upper
  bound < 0 AND both C3 halves negative.
- **CONSTRAIN** (Tier-C→B style entry-geometry rule) iff some C5 cut is positive
  ex-window in BOTH halves with n ≥ 30.
- **NO ACTION** otherwise. Explicitly: no decision may rest on in-window
  numbers, and no cut invented after seeing the output is decision-eligible.

**This is the last cut of this book on the bear_put question.** Any further
change to bear_put's treatment requires new data, not a new slice.

### 2026-07-22 addendum 14 — bear-position study RUN: DEMOTE fires on all three pre-registered criteria; bear_put is a SELECTION problem, not an exit problem

`scripts/backtest_study/bear_position_study.py` → `backtests/bear_position_study_output.txt`.
Cuts, window control and decision rule were fixed in addendum 13 before the run;
nothing was added after seeing output. Same 663-row pooled debit book, same
harness validation (250/250 real rows reproduce DEBIT_PROD to the cent).

**The number that settles it — E, hold-to-cap, EXIT-FREE (`pnl_at_cap_pct`):**

    bear_put   ALL   n=343  mean −0.414  median −0.928  win 27.7%   −$160,256
               IN-W  n=102  mean −0.674  median −0.988  win 15.7%    −$76,329
               EX-W  n=241  mean −0.304  median −0.670  win 32.8%    −$83,927
    bull_call  EX-W  n=228  mean +0.423  median +0.265  win 57.0%   +$101,380

With no exit rule at all, the median bear_put is a −93% loss. R (realized under
PROD) is −0.124 — i.e. **the current exit rule is already rescuing ~0.29 of
mean P&L**, and the thing underneath it is far worse than realized P&L showed.
That is the reverse of addendum 11's conclusion and it is the direct test
addendum 11 lacked: MFE bounds what a perfect exit *could* reach; E measures
what the position is worth without one.

**Decision-rule evaluation (pre-registered):**

    [PASS]  ex-window mean E < 0                  (−0.304)
    [PASS]  date-clustered bootstrap 95% CI < 0   ([−0.433, −0.175], 10k, cluster=date)
    [PASS]  both time halves negative             (early −0.289, late −0.322)
    VERDICT: DEMOTE TO VETO

**It is not the window, and not the pricing tier.** Negative in 14/17 months;
negative in every mech cell (BEAR_HE −0.281, LVOL −0.301, RB_EVOL −0.497,
PROD −0.254 — all EX-W); negative in every pricing tier (real −0.431, tweak
−0.383, bs −0.045). Every prior explanation I offered for bear_put — exit shape,
regime key, Mar–Apr window — was a local slice of a structure that loses
everywhere on this book.

**Path shape, reinterpreted.** bear_put MFE +0.691 with give-back to E of
**1.105** and MFE-first 72.0%; bull_call MFE +1.281, give-back 0.566, MFE-first
40.2%. bear_put reliably runs and then round-trips *past zero*. Addendum 11 read
the excursion as harvestable edge; with E on the table it reads as volatility,
not direction. A trailing stop harvests some of it (addendum 12: +$11.8k, 94%
in-window) but cannot make a −0.414 expectancy positive.

**Ladder interaction (C6): the operational change is smaller than it sounds.**
Every bear_put already lands in VETO (n=36, mean E −0.894) or Tier C (n=307,
mean E −0.358); none ever reach Tier A or B. Under the shipped top-3/day
ladder, bear_puts are already largely not deployed. Whole-book tier means on E
stay monotone (A +0.907, B +0.482, C −0.355, VETO −0.510), and hold EX-W
(A +0.414, B +0.445, C −0.285, VETO −0.785) — A/B invert slightly EX-W, worth
noting but not a ladder failure.

**CONSTRAIN candidate, reported and NOT taken.** `|delta| 0.30–0.45` was the one
cut passing the pre-registered n≥30 / both-halves-positive filter (n=36 EX-W,
mean +0.097, halves +0.065 / +0.129). Its median is **−0.767** and its total is
+$2,465 — a mean carried by a couple of tails on 36 rows. The pre-registered
rule puts DEMOTE first and it fired; recording the cut so it is not re-discovered
as a novelty later.

**The honest caveat, which is a portfolio question and not a statistical one.**
The book spans 2024-06 → 2026-03, a period with exactly one sustained drawdown.
bull_call beat bear_put even *inside* mechanical BEAR cells (EX-W +0.326 vs
−0.281). So this may be measuring "the sample was a bull market" as much as
"the model is bad at bearish calls" — the two are not separable on this data.
A structure veto on bear_put removes essentially all downside exposure from the
system. That is a deliberate choice to make, not a mechanical consequence of a
p-value.

**Status: verdict reached, NOT yet implemented.** Implementation options (intake
structure_veto like bear_call vs ladder VETO tier vs leave at Tier C and simply
never deploy) are a user decision. Per addendum 13 this is the last cut of this
book on the bear_put question — any revision needs new data.

---

## 2026-07-22 — Feb–Apr 2026 bear holdout: coverage + backfill status

The addendum-13 pre-registration ends "this is the last cut of this book" —
so the DEMOTE verdict needs **new** data, not another slice. The only genuine
holdout available is the second sustained drawdown: **2026-02-05 → 2026-04-07**,
32 trading days, all of them mechanical `BEAR_HE` (BEAR + H/E-VOL), VIX peak
31.0, SPY −7.9%. The current book samples it with **6 dates**.

Why not the Iran window instead: checked against the frozen `lib/mech_regime.py`
labels, 2025-06-02 → 2025-07-15 is **BULL on every single day** (26 L-VOL /
3 H-VOL / 1 E-VOL), SPY 592.71 → 622.14, VIX peak 21.6. A vol blip inside an
uptrend — it would add the cell the book already has most of, not a bear cell.

### Status table

Drive coverage + enrichment fill read 07-22. "Analyzed" = has rows in the
AnalysisClaude tab (the only source of truth for analysis state — see the
queue-file drift note in archive/05). Enrichment columns are the **fill rate of
each collector's marker column** on `stocks-flow-*-compiled.csv`
(`oi_enriched_on`, `iv_pct_enriched_on`, `price_catalyst_enriched_on`) and the
row count of the `counterpart-iv-*.csv` sidecar — measured, not inferred from
the `.done` queue files. Every date is either 0% or 100%: enrichment is
all-or-nothing per date, so there is no partial-fill case to handle.

Row counts are 498–501 on all 26 compiled stocks files; etfs compiled is
present everywhere except 2026-03-18. Nothing here is a dropped stage — the
lean-enrichment profile was SHELVED on 2026-07-21 (archive/05, "NO scraper is
droppable"), so these are gaps to fill, not decisions to honour.

| # | Date | In Drive | Analyzed | oi/eod_iv | iv_pct | p/cat | cpart | Next step |
|---|------|----------|----------|-----------|--------|-------|-------|-----------|
| 1  | 2026-02-05 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ iv-pct + ✅ p/cat + ✅ counterpart → ✅ analyze |
| 2  | 2026-02-12 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 3  | 2026-02-13 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 4  | 2026-02-17 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 5  | 2026-02-19 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 6  | 2026-02-23 | yes | ✅ | **0%** | 100% | 100% | 260 | ⚠ in book WITHOUT eod_iv — see flaw note |
| 7  | 2026-03-02 | yes | ✅ | **0%** | **0%** | **0%** | **0** | ⚠ in book with NO enrichment at all |
| 8  | 2026-03-03 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 9  | 2026-03-04 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 10 | 2026-03-05 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 11 | 2026-03-06 | yes | ✅ | 100% | 100% | 100% | 278 | in book, complete |
| 12 | 2026-03-09 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 13 | 2026-03-10 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 14 | 2026-03-11 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 15 | 2026-03-12 | yes | ✅ | 100% | 100% | 100% | 84 | in book, complete |
| 16 | 2026-03-13 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 17 | 2026-03-16 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 18 | 2026-03-17 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 19 | 2026-03-18 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze (etfs compiled absent) |
| 20 | 2026-03-19 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 21 | 2026-03-20 | yes | ✅ | 100% | 100% | 100% | **0** | ⚠ in book with BLANK iv_spread |
| 22 | 2026-03-23 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 23 | 2026-03-24 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 24 | 2026-03-25 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 25 | 2026-03-26 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 26 | 2026-03-27 | yes | ✅ | 100% | 100% | 100% | 253 | in book, complete |
| 27 | 2026-03-30 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 28 | 2026-03-31 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 29 | 2026-04-01 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 30 | 2026-04-02 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 31 | 2026-04-06 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 32 | 2026-04-07 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |

**26/32 in Drive · 6/32 analyzed · 3 of those 6 input-incomplete · 6 need
scraping.** (2026-04-03 is Good Friday, so 03-30 → 04-07 is 6 trading days.)
Wider Drive audit: 26 weekdays are missing in 2026-02-01 → 2026-07-22, and
**all 22 weekdays of 2026-04 are absent** — the 6 above are the subset inside
the bear episode; the rest of April is a separate gap.

Stage totals to fill across the 26 in-Drive dates: `enrich_oi` 21 ·
`fetch_iv_percentile` 21 · `fetch_price_catalyst` 21 · `fetch_counterpart_iv` 22.

**Scrape 2026-04-08 as well.** `enrich_oi` reads D+1 open interest, so the last
episode date (04-07) cannot be enriched without it, and 04-08 is inside the
missing-April block. It is not itself a holdout date — it is an input.

### The three flawed in-book dates (decision needed)

The existing 6-date sample of this episode is **not** input-consistent, and the
inconsistency lands on `iv_spread` — the bear_put Tier-C column, i.e. the exact
variable the holdout is meant to test:

- **2026-03-02** — analyzed with zero enrichment. No `oi_confirm_pct`, no
  `iv_pct`, no `iv_spread`.
- **2026-02-23** — counterpart sidecar present (260 legs) but traded-leg
  `eod_iv` absent. This is the failure mode the shelving note names: counterpart
  legs are *always* EOD, so without `eod_iv` the matched pair compares intraday
  against EOD IV. `iv_spread` here is **silently wrong**, not missing — worse
  than a blank, because nothing downstream flags it.
- **2026-03-20** — traded-leg enrichment complete but no counterpart sidecar, so
  `iv_spread` is blank. Honest gap, at least.

Re-running `analysis_pipeline` on these **appends** rows rather than replacing
them, so fixing them is a duplicate-row decision, not just a re-run. Open
options: (a) leave them and note the holdout's 6 pre-existing dates are mixed
quality; (b) enrich, re-analyze, and delete the original rows. Unresolved —
does not block enriching the other 20.

### Sequence

1. **Scrape the 6 + 04-08** (user is running this):
   `python3 scripts/collector/scrape_flow.py --start 2026-03-30 --end 2026-04-08 --skip-existing`
2. `compile_flow.py` on the newly scraped dates.
3. Enrichment chain, batched by stage over the gap lists above —
   `enrich_oi`, `fetch_iv_percentile`, `fetch_counterpart_iv`,
   `fetch_price_catalyst`. All four stay in (archive/05); none is optional.
4. `python3 -m scripts.analysis_pipeline --date <D>` for the 26 unanalyzed
   dates — **config unchanged**, or the holdout stops being a holdout.
5. `python3 -m scripts.backtest` + `python3 -m scripts.backtest.proxy`.
6. Re-run `scripts/backtest_study/bear_position_study.py` **unmodified** against the
   Feb–Apr 2026 rows only. The pre-registered decision rule from addendum 13
   applies as written: DEMOTE iff mean E < 0 AND bootstrap CI upper < 0 AND
   both halves negative.

If the holdout agrees, the demotion ships and the "sample was a bull market"
caveat in addendum 14 is answered by a second independent drawdown. If it
disagrees, bear_put stays at Tier C and the 2024-06 → 2026-03 result is
recorded as window-bound. Either way the decision is made once, on the
holdout, and not by re-cutting the 663-row book again.

### 2026-07-29 — PRELIMINARY holdout read (backfill incomplete — NOT the decision run)

Backfill in progress; read taken from the Sheets tab exports
(`backtests/analysis - BacktestResults.csv` / `- BacktestProxy.csv`, pulled
07-29), holdout window rows only. Coverage: **12 dates priced** (02-05 → 03-27;
02-24/02-25 now analyzed beyond the status table above), 115 priced rows, 5
unpriced (3 no_history / 2 unsupported). Scratch script only — the decision run
stays `bear_position_study.py` unmodified once the window is fully backfilled.

**bear_put_spread, n=67 priced — all three pre-registered criteria fire on the
partial sample:**

    mean E −0.242   date-clustered bootstrap 95% CI [−0.370, −0.077]  (12 dates)
    halves: early −0.205 (n=28) · late −0.268 (n=39)
    ex-flawed-dates (02-23/03-02/03-20 excluded): mean E −0.214 (n=51), still negative

R (PROD) −0.073 — the exit rule is again rescuing ~0.17 of mean E, same
signature as addendum 14. Path shape repeats too: MFE +0.609 / MAE −0.621,
run-then-round-trip. And this window IS a bear drawdown — the most favourable
conditions bear_put will ever see — so the addendum-14 "maybe the sample was a
bull market" caveat is, preliminarily, not holding up. Comparator bull_call:
mean E +0.150 (n=18, but ex-flawed only n=6 at −0.138 — too thin to read).

**One discordant cut to watch: the pure-real tier is POSITIVE** — real n=16
mean E +0.177 (win 62.5%) vs strike_expiry_tweak n=34 mean −0.471 and bs n=17
mean −0.177. Real+tweak pooled is still −0.26, and tweak rows are real-priced
(only bs is model-priced), but if the final run still shows real-tier-positive /
tweak-tier-negative, the tweak fallback itself (strike/expiry substitution on
bear_puts in a fast tape) needs a look before the verdict is read as clean.

**MFE/MAE cut (standing rule — realized alone is not a read):**

    structure   n   MFE     MAE     |MAE|/MFE  MFE-first  give-back  R-capture
    bear_put    67  +0.609  −0.621    1.02       59.7%      0.851      −0.12
    bull_call   18  +1.108  −0.574    0.52       55.6%      0.958      +0.40
    bull_put    27  +0.559  −1.347    2.41       44.4%      0.738      −0.41

- bear_put's excursions are **perfectly mirrored** (ratio 1.02) — by the
  asymmetry rule that is path-vol, not harvestable edge; 58% of rows reaching
  +0.30 still end E<0 (old book: 43%). bull_call keeps upside asymmetry (0.52)
  *inside the drawdown*, and its exit capture is +0.40 of MFE vs bear_put's
  −0.12 — same discriminator as addendum 14: exit harvesting works on
  bull_call, nothing on bear_put rescues a negative-E selection.
- The addendum-14 bear_put signature (MFE-first 72%, give-back 1.105) lives in
  the **tweak tier** here (70.6% / 1.095, MAE med −0.926); the real tier looks
  different in kind: MFE +0.885 / MAE −0.546 (ratio 0.62), mfe_day 12.4, 44%
  reach the +0.90 PT, E +0.177. Reinforces the real-vs-tweak discordance above —
  on the final run, check whether tweak's strike/expiry substitution is
  manufacturing the round-trip shape before reading the pooled number.
- bull_put side note (thin): ratio 2.41 with 59% reaching +0.30 and only 6% of
  those ending E<0 — deep-MAE-then-recover, the Attempt-13 whipsaw shape; its
  real-tier R (−0.304) undershoots E (+0.009) via dollar_stop exits. Watch, not
  actionable.

Loose ends for the backfill: **2026-02-17 is analyzed but absent from BOTH
backtest tabs** (0 rows in Results and Proxy — backtest apparently never run on
it); late dates are the most negative (03-20 −0.53, 03-27 −0.52), and the
still-missing late-March/April dates sit closest to the episode bottom, so
completing coverage is more likely to strengthen than soften this read.
No config changed. No decision taken — waits on the full window.

### 2026-08-04 — MID-STOP check (backfill still incomplete — NOT the decision run)

Read off the refreshed `backtests/results.csv` (364 rows) + `proxy_results.csv`
(675), window rows only, deduped on date|ticker|play|structure. Scratch script,
read-only, no config changed. Purpose is to catch problems before the decision
run, not to decide.

**Coverage: 16 dates / 137 priced rows** (07-29: 12 / 115). 14 of the status
table's 32 dates, plus 02-24 and 02-25 which are not on it. Still missing 18,
including the whole late-March block (03-11 → 03-26 except 03-20) and all of
03-30 → 04-07 — i.e. everything nearest the episode bottom. 6 unpriced
(5 no_history / 1 unsupported).

**bear_put: DEMOTE fires again, and harder.** n=82 (was 67).

    mean E −0.254   bootstrap 95% CI [−0.392, −0.091]  (16 dates, cluster=date)
    halves: early −0.100 (n=29) · late −0.338 (n=53)
    ex-flawed-dates n=66, mean E −0.235
    R (PROD) −0.040 → exit rule still rescuing ~0.21 of mean E

All three pre-registered criteria pass on the partial sample, second time
running, with the late half more negative than the early — the added dates
moved the read away from zero. Comparator bull_call n=20: E +0.187, R +0.463,
|MAE|/MFE 0.51, R-capture +0.43 vs bear_put's −0.06. Same discriminator as
addendum 14; bear_put excursions still mirrored (0.97).

**Four things to fix before the decision run — all mechanical, none of them
change the verdict, but two would corrupt it:**

1. **`2026-03-06` is duplicated wholesale in BOTH tabs** — in BacktestResults,
   10 plays each appearing twice with identical legs/play/P&L (it is the only
   20-row date in the window; every other is ≤11), and separately in
   BacktestProxy (GLD/MU/USO bull_puts, same doubling). The study loader
   (`exit_switch_mech_study.load_debit_trades`) dedups proxy-against-real via
   `real_keys` but has **no within-real dedup**, so an unmodified re-run
   double-weights that date. My numbers above dedup it; the decision run will
   not unless the loader is patched.
2. **The study scripts read the wrong files.** `AC_PATH`/`BR_PATH`/`BP_PATH`
   point at `backtests/to_evaluate/analysis - *.csv`, exports dated **07-22**
   holding only 8 window dates. `bear_position_study.py` re-run "unmodified"
   would read stale data. Refresh those exports (or repoint the paths) as step 0
   of the decision run.
3. **The real-vs-tweak discordance flagged on 07-29 has grown, not resolved:**
   real n=22 mean E **+0.201** (win 63.6%) · tweak n=39 **−0.514** · bs n=21
   −0.246. Real+tweak pooled −0.256. The whole demotion currently rests on the
   proxy tiers being trustworthy on bear_puts in a fast tape. Caveat in the
   other direction: 6 of those 22 real rows are the duplicated 03-06 IWM/TSLA
   pairs, so the real tier is effectively n=18. This needs settling before the
   verdict is called clean — it is now the largest open risk on the demotion.
4. **02-17 and 02-19 are still absent from both backtest tabs** (07-29 flagged
   02-17 only). The status table marks both analyzed with the full chain. Either
   the backtest was never run on them or the analysis rows are not actually
   there — worth a direct Sheets check, not another export.

**New, unrelated to bear_put: the shipped bull_put band gets its first
out-of-sample look, and it holds.** Pooled window bull_put is bad (n=33,
E −0.450, R −0.451, |MAE|/MFE 2.75, late half −0.733) — but split on the rule
actually in `deployment-rules.md`:

    0.08 ≤ |delta| ≤ 0.20 AND DTE ≤ 59    n= 9   E +0.180   R +0.152
    out of band                           n=24   E −0.686   R −0.677

Out-of-band is DTE-driven, not delta-driven: DTE>59 n=18 E −0.898, |delta|<0.08
n=11 E −0.632, |delta|>0.20 n=2 E −0.048 (rows can fail both legs). 6 of the 9
in-band rows finish positive (median E +1.00); the mean is dragged by one
SMH −2.66. Thin and one-window, so not a promotion — but it is the first
independent window where the constraint separates the book, and it separates it
by 0.87 of mean E. Do NOT read the pooled bull_put number as evidence against
the structure; it is an out-of-band number.

**Lead worth chasing on the long-dated blind spot (2026-07-27 §3).** Five rows
in this window are real-priced at DTE ≥ 180 with `pct_real_days = 1.0` —
TLT 707/689/687 (two bull_call spreads + a long_call) and HYG 197/191. So
Barchart history at 180–700 DTE is not universally absent; it appears to be
ticker-dependent (bond/credit ETFs have it). n=5 does not unblock anything, but
"h≥180 cannot be priced" is too strong as stated — the cheap next step is a
coverage probe by ticker before assuming IBKR is the only route.

#### Same-day addendum — does E survive "we never hold to expiry"?

Operator objection (2026-08-04): positions are closed early in practice, and
credits especially are closed before terminal gamma. E is a hold-to-cap mark, so
does it measure a counterfactual we would never trade? Checked both reads:

**bull_put band: survives.** 30% of window bull_put rows sit at E = +1.00
(structural max = expired worthless), and 5 of the 9 in-band rows are among them
— so the E-based band number IS partly a hold-through-gamma artifact. But R
already prices the early close (credit PROD = `profit_target 0.65`, no stop, no
time exit; only 2 of 33 rows exit `expired`), and the split holds under R alone:
in-band R +0.152 (median +0.666) vs out-of-band R −0.677. Conclusion unchanged.

**bear_put DEMOTE: the verdict is measure-dependent. Recorded, not resolved.**

    criterion          mean      CI 95%             halves           verdict
    E (hold-to-cap)   −0.254   [−0.392, −0.091]   −0.100 / −0.338   DEMOTE
    R (PROD exits)    −0.040   [−0.218, +0.177]   +0.221 / −0.183   NO ACTION

Pre-registration picked E deliberately, and three things still argue for it
here: (a) R's rescue is exit-driven — 32 of 82 bear_put rows (39%) exit on a
risk control (`stop_loss` 14, `dollar_stop` 10, `trailing_stop` 8), i.e. the
structure reaches breakeven only by being cut fast; (b) **no transaction cost is
modelled anywhere** — `spread_width_pct` is the synthetic short-strike width,
not bid/ask, and fills are the Barchart Open, so realistic two-leg fills in a
fast tape push R below zero; (c) R's halves run +0.221 → −0.183, deteriorating
as the bear episode deepens, which is the wrong direction for a bear structure.
Still: the demotion should be stated as "negative unmanaged, breakeven only
under active risk control", not "loses money". Re-check on the full window.

**Real gap this exposes (new candidate).** `simulation.credit.time_exit_dte_fraction`
is explicitly `null` ("ride toward expiry within path_cap") while debits carry
0.75 — the credit profile does exactly the thing we would never do live, and
11 of 33 bull_put rows exit `cap_open`, i.e. ran to the 120-day path cap. A
gamma-motivated DTE-floor exit for credits (close at ~21 DTE) is untested and
cheap to sweep. Do it on the credit book AFTER the window completes; it is not
part of the pre-registered bear decision run.
