# Archive 09 — 2026-08-11: completed book, ML null result, DEPLOY arm, v3 close-out

Covers 2026-08-11, oldest first: the completed-book analysis (holdout
coverage FULL, all three bear_put DEMOTE criteria fire), the
`bs_options_hist` proxy tier measured and shipped OFF, the `mech_cell`
backfill, the ML combination search (NULL RESULT) with the bear
`be_after` finding, the DEPLOY arm (bear as a hedge, `|delta|`
descending), the v4 bridge pre-registration pointer, and the v3
CLOSE-OUT that shipped the ratchet, the hedge-sleeve rules and the
live-loop `SUBSTITUTED` fix.
See [../README.md](../README.md) for the full section index.

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

Pre-written plan at [`ml-plan.md`](../ml-plan.md): learn which structure ×
regime × entry-geometry × enrichment combination best predicts play outcome,
benchmark = the shipped score-free ladder's top-3/day replay, purged
walk-forward CV clustered by date, real+tweak training only, pre-registered
ship criteria. Nothing executed as of this entry.

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
   `docs/backtest-reference.md` fallback-chain section + `proxy_method` row,
   `docs/architecture.md` proxy map, proxy.py module docstring.
3. *Historical rows are NOT purged.* The 301 existing `bs_options_hist` rows
   stay in BacktestProxy — filter them out at read time by `proxy_method`
   (equivalently `pct_real_days == 0`); the flag only stops NEW ones.
4. What this does NOT fix: the long-dated blind spot itself. Removing bs makes
   the gap visible instead of papered over; the fix is still real long-dated
   price history.

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

## 2026-08-11 — ML combination search RUN: NULL RESULT; and the bear arm finds an EXIT fix, not a selection one

Both arms of [`ml-plan.md`](../ml-plan.md) executed against the same 08-11 exports.
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

## 2026-08-11 — DEPLOY arm: the hedge caveat was TESTABLE, and bear deployment has a rule

The 08-11 bear arm closed by calling the chop hedge "a *portfolio* decision the
book cannot price". **That was too strong** — 84 of the bear dates also carry a
deployed ladder sleeve, so the concurrent book exists and the portfolio question
is answerable on it. The operator's instruction (bear positions stay deployable)
made the gap worth closing. Pre-registered as
[`ml-plan.md` §addendum 2](../ml-plan.md) BEFORE running; code
`scripts/backtest_study/bear_deploy.py`, which at the time wrote a plain
`bear_deploy.txt` (pre-runner `tee` output; no report is retained).
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

## 2026-08-11 — v4 emission-composition bridge: PRE-REGISTRATION → [`pre-registrations/v4_bridge.md`](../pre-registrations/v4_bridge.md)

Moved out of this log: a pre-registration is an immutable artifact and this
file is pruned into `archive/`. The section is unchanged, just relocated.

---

## 2026-08-11 — v3 CLOSE-OUT: three findings SHIPPED, and the production delta is a third of the study's

v3 is closed. The trigger was not fatigue — it is that **no question left in the
queue is answerable from this book**. The ML combination search returned a null
result in all 15 model×strategy cells and its ablations put the binding
constraint in the *columns*, not the estimator; the Feb–Apr 2026 holdout is
complete; the ladder is monotone in every cut. What remained was shipping.

### 1. SHIPPED — `be_after: 0.50`, bear debit only (`simulation.structure_exit`)

Implemented in `scripts/backtest/simulate.py`: a `be_stop` branch in
`_summarize_path` between `dollar_stop` and `stop_loss` (ported from the frozen
harness ordering), plus `_structure_override()` keyed on
`bear_put_spread`/`long_put` with `entry_net >= 0`. Merge order for debits is
**base → structure → regime**.

**A3 — the pre-registered interaction check, and a recorded deviation from the
frozen grid.** One entry was added to `bear_arm.py`'s `DEBIT_GRID`:
`"BE @.50 + trail .50 trig .50"`. One named config, not a search.

    trail .50 trig .50            -0.098  +0.036  [+0.006,+0.063]  LOO +0.032
    BE ratchet @.50               -0.092  +0.041  [+0.016,+0.065]  LOO +0.038
    BE @.50 + trail .50 trig .50  -0.098  +0.036  [+0.006,+0.063]  LOO +0.032

The stacked cell is **bit-identical to the trail alone, with zero `be_stop`
exits**, and below BE alone. The cause is structural, not sampling: the trail
arms at peak ≥ 0.50 and its floor (peak − 0.50) is then ≥ 0 — at or above the
ratchet's threshold — and the trail is checked first. The ratchet is strictly
dominated inside BEAR_HE. Decision rule fires **SUPPRESS**, implemented as
`be_after: null` on the `BEAR_HE` cell (which is why regime merges last).
Confirmed in production: suppress vs stack over the 224 BEAR_HE bear-debit rows
differ on **0 rows**.

**The production delta is NOT the study delta — record this, it will recur.**
The study measured against `DEBIT_PROD` (pt .90 / sl .75 / tef .75, **no
trail**). Production has shipped the BEAR_HE trail since 07-22, so the study's
baseline is not production's:

    bear debit (n=332)          mean R              total $            rows changed
    study framing            -0.133 → -0.092                              —
    production, measured     -0.109 → -0.093    -43,806 → -37,951         16
      on BEAR_HE (suppressed) -0.152 → -0.152    unchanged                 0
      elsewhere (n=108)       -0.019 → +0.028     -4,916 → +939           16

So the shipped rule is worth **+0.015 mean R / +$5.9k**, not +0.041 / +$16.4k,
and `be_stop` fires on **16 rows, not ~44**. The two rules were largely buying
the same rows and the trail got there first on 224 of 332. The generalisable
lesson: **a study delta measured against `DEBIT_PROD` overstates production
impact wherever a regime cell already ships a rule that converts the same
rows.** Every future exit study should quote both baselines.

`stop_loss` 92 reproduces exactly; the *baseline* is 100, not the study's 110,
for the same reason.

**Leak guard — PASSED.** Non-bear debits (n=261): 0 rows changed, mean R and
dollars identical. Credits (n=202): 0 rows changed. The narrowness is the
finding (+0.234 → +0.209 on non-bear debits), and it is now enforced by tests.

### 2. SHIPPED — bear hedge sleeve (`deployment-rules.md`)

D2/D4/D3 written up as an operator section: bear is a **hedge, not a
selection**; rank the day's candidates by `|delta|` DESCENDING; size at ≤ ½.
Limits travel with the rule (D3 formally NOT MET by $86, worst-decile CI
includes zero, naked puts unrepresented, D5 does not reproduce). The bear_put
**DEMOTION thread (open since 07-22) is CLOSED without a demotion mechanism** —
bear rows are already C/VETO and never enter the deployed top-3, so the answer
was an exit profile, not an intake veto.

### 3. SHIPPED — live-loop `SUBSTITUTED`, and a CORRECTION to the 07-27 entry

The 07-27 §4 entry states that a naked leg filled against a spread play "falls
to **NONE**, indistinguishable from 'no play that day'", i.e. silently dropped.
**That is wrong, and the truth is worse.** `SIDE` maps `long_call` and
`bull_call_spread` both to `debit`, so the family branch labelled such fills
**STRUCTURE** — pooled into the eval as if the emitted play had been traded.
A second defect: that branch matched on credit/debit only, so a `long_put` fill
against a `bull_call_spread` play (opposite directions, both debit) was also
labelled STRUCTURE.

Fixed in `stage1_map_fills.py`: a `DIRECTION` map now gates the family branch,
substitutions get their own `SUBSTITUTED` confidence, and candidate selection is
rank-based (EXACT ≺ STRUCTURE ≺ SUBSTITUTED) so a true match always outranks a
substitution. Tally on the checked-in snapshot moves **0/3/15 → EXACT 0 /
STRUCTURE 2 / SUBSTITUTED 1 / NONE 15**; the reclassified row is the META
short-put-vs-`bull_put_spread` entry the report's own prose had already flagged
as weak while the tally counted it as a match.

### 4. SHIPPED — the v4 prompt trim (`score_flow` / `score_dealer` dropped)

`score_vol` stays (exempt); `score_price`/`score_catalyst` were always
pipeline-computed. `ROW_COLUMNS` goes 27 → 25 and the columns are dropped from
the schema outright rather than blanked, because v4 writes fresh tabs.
`RESULT_COLUMNS` KEEPS them so the results schema stays stable across eras and
the four study loaders that name them keep working on pooled exports. Reader
audit found no `KeyError` risk — every analysis-row consumer uses
`.get(col, "")`.

**The queued trigger did NOT fire.** The 07-21 queue said "drop if still null
after the 25-date backfill". They are not null — 366 of the last 400 rows carry
both. The justification is instead the 08-11 ML ablations (nothing beyond
structure × regime × geometry is reproducible) and the framework's own admission
that `score_dealer` was judged off a vol-snapshot proxy, never real dealer data.
Recording this because the trim now rests on a *different* argument than the one
that queued it.

**Correction to the plan: the new scale is 0–50 for DIRECTIONAL/HEDGE/SYNTHETIC
but 0–55 for VOLATILITY.** VOLATILITY's dropped `flow` max was 20, not 25, so
its survivors are 10 + 25 + 20 = 55. Documented as such everywhere rather than
rounding the claim down; flattening it to 50 would be a rubric change, not a doc
change. Either way v4's `score_total` is NOT comparable to v3's 0–100 and must
never be ranked across the two eras — it survives only as a deterministic
tie-break within a tier.

**A live prompt bug found and fixed in passing.** The contract told the model
"NEVER emit a bear call spread" and then, ~45 lines later, instructed it to use
one for the bearish high-IVpct TF-S case; `claude.md` and `codex.md` carried the
same contradiction. Only the framework's Step-4 table was correct. This could
emit the single most toxic structure in the book (−0.82 mean, 17% win,
intake-vetoed since Attempt 13) — the backtest would have refused it at intake,
so the cost was wasted plays rather than bad fills, but it was live. All three
now route bearish TF-S to a bear put debit spread or a pass. Folded into this
version bump because it is a prompt change and needed one.

Also fixed: the guardrails told the model to "zero the price and catalyst
components" to hold a total down — impossible since both became
pipeline-computed. It now withholds `vol`, the only lever it still has.

### 5. The cut-over mechanics — in-place `vN_` renaming, NOT a new spreadsheet

Worth recording because the close-out plan assumed a new spreadsheet and a
`GOOGLE_SPREADSHEET_ID` change, and that is **not** what this repo does. The
sheet already carries `v1_AnalysisClaude_20260625`, `v2_AnalysisClaude`,
`v3_AnalysisClaude` — the established convention is to rename the live tabs with
a `vN_` prefix in place and let the pipeline recreate fresh ones. The v3 rename
is done (`v3_AnalysisClaude` 1,608 rows / 27 cols, `v3_BacktestResults`,
`v3_BacktestProxy`), and an empty `AnalysisClaude` is waiting with 0 columns, so
the first v4 append writes a clean 25-column header.

Two consequences, both good, that the plan got wrong in the cautious direction:

- **`BaselineDaily` is untouched** (214 rows, continuous). The plan's warning
  that v4 would start with no regime-baseline history — the one real risk it
  flagged — is moot under in-place renaming. No `build_baseline --backfill`
  needed.
- **No env change, and no code change.** `config/backtest.yml`'s
  `analysis.tab: AnalysisClaude` and `output.sheet_tab: BacktestResults` already
  point at the v4 tabs by virtue of the rename.

The live cost is that `python -m scripts.backtest` now reads 0 rows until v4
accumulates; v3 work must pass `--tab v3_AnalysisClaude`. Study code is
unaffected — it reads CSV exports by filename, not tabs.

### 6. Tests

`tests/test_mech_regime.py` gains the structure-override suite (bear debit gets
the ratchet, non-bear debit and credits never do, BEAR_HE suppression, merge
order, disabled/default no-ops). `tests/test_backtest.py` gains five ladder
tests pinning `be_stop` between `dollar_stop` and `stop_loss` — the position is
load-bearing and was previously unguarded.

### 7. `exit_basis` widened — `BEAR_DEBIT` (fixed in the same change)

Shipping the ratchet initially broke the column's guarantee: a bear debit that
ran `be_after` reported `PROD`, so `exit_basis == "PROD"` stopped meaning "base
config only" — the exact ambiguity the column was added to prevent. The
vocabulary is now `{PROD, CREDIT, BEAR_DEBIT, <regime cell>}`, reported in
merge-precedence order: a regime cell outranks `BEAR_DEBIT` because regime
merges last and, on BEAR_HE, genuinely governs (it nulls `be_after`). Pinned by
tests that assert the label never claims a profile the merge did not apply.

### 8. Known gaps left open, deliberately

- **`scripts/chart_backtest.py:55-76`** re-derives exit config for chart
  reference lines and knows about neither `regime_exit` nor `structure_exit`;
  bear-debit charts draw a −75% stop line for positions that exited at
  breakeven. Pre-existing, now one rule wider.
- **`backtests/live_loop/` is UNTRACKED.** `.gitignore` excludes `backtests/*`
  and its own comment calls that directory disposable scratch that "gets deleted
  periodically" — yet `stage1_map_fills.py` is 30KB of real code and is now the
  only source of new evidence. This is the same mistake the 08-11 refactor fixed
  for study code by moving it to `scripts/backtest_study/`; the live loop was
  missed.

---

