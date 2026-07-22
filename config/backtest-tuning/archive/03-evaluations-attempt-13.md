# Archive 03 — Framework evaluations and Attempt 13 (2026-07-08 → 07-17)

Part of the [backtest tuning log](../README.md). Covers the MFE/MAE signal-quality
study, the v1/v2/v3 three-run evaluation, Attempt 13 (bear_call veto + credit stop
removal), and the scoring-column keep/drop power check.

---

## 2026-07-08 — Framework evaluation: signal-quality study on MFE/MAE basis (not an exit experiment)

Audit of the analysis framework against `backtests/v1_20260625_results.csv`
(292 rows, signal_eod basis, pre-scoring-redesign labels) and
`backtests/results.csv` (116 rows, next_open basis). Because the exit rules are
still under tuning, the primary basis here is **exit-independent**: "worked" =
path MFE ≥ +30% of premium, "never moved" = MFE < +10%. These baselines don't
move when exit knobs do, so they're reusable for future exit studies.

**DTE gradient — replicates on both datasets, exit-independently.** Short-dated
plays are worse *signals*, not an exit artifact:

| DTE band | v1 n | v1 never<10% | v1 med MFE | v1 med MAE | cur n | cur never<10% | cur med MAE |
|---|---|---|---|---|---|---|---|
| 0–21 | 23 | 39% | +0.33 | −1.00 | 5 | 40% | −1.00 |
| 22–45 | 89 | 26% | +0.46 | −1.00 | 23 | 22% | −1.00 |
| 46–90 | 101 | 14% | +1.03 | −0.97 | 48 | 21% | −1.00 |
| 91–180 | 45 | 7% | +1.24 | −0.82 | 21 | 10% | −0.97 |
| 180+ | 34 | 6% | +0.75 | −0.49 | 19 | 5% | −0.58 |

Shipped as framework Step-4 "DTE discipline" (default ≥45 DTE; shorter only
with a named dated catalyst) + a prompt-contract discipline rule + a method-file
bullet in both engines.

**Retired high/medium/low labels did not discriminate** (v1, all rows predate
the numeric-score redesign): worked-rate high 68% / medium 72% / low 77%;
realized win 57% / 56% / 62%; mean realized $554 / $205 / $145 (the $ ordering
is exit-path-driven, not signal-driven). This is the baseline `score_total`
must beat. The `score_total`/`score_*` columns in results.csv are **entirely
empty** — no backtested row carries the new score yet — so score validation is
the standing follow-up (recipe in `config/analysis-roadmap.md`, alpha
attribution).

**Intent: HEDGE ≈ DIRECTIONAL on signal quality** (worked-rate ~75% vs ~73%;
v1 n=59 vs 200), but HEDGE's realized-dollar lead ($664 vs $181 mean) rode
median MAE ≈ −100% paths before recovering — entangled with the exit profile,
so documented in the framework as "first-class plays" with that caveat, not
promoted as a superior signal.

**Playbook distribution is degenerate:** TF = 73% of v1 plays; VC/DP ≈ zero on
both sets (expected — the per-name GEX gate that selects them isn't an input
yet; flagged UNEXERCISED in the framework). Current-window small-n reads:
GE weak (n=8, median MFE +0.07, 50% never moved), PU strong (n=11, median MFE
+1.85), MR strong on v1 (n=5, 100% worked). All small-n — log only.

**Path fact relevant to stops:** median MAE is ≈ −0.9 to −1.0 in nearly every
slice — a near-total drawdown is a *normal* excursion for these plays, which is
the zone `stop_loss=0.75` fires into. Consistent with Attempt 3's theta-decay
finding; worth remembering when tuning stop levels.

**Weak-signal correlations on the current 116-row set** (realized pnl_pct
basis, so exit-contaminated — retune flags, not conclusions): `oi_confirm_pct`
r ≈ −0.03 (vs +0.40 on the Mar-2025 n=20 that set the ±2/±1 bands — flagged in
`config/conviction-score.md`), `cpir` r ≈ −0.20, `iv_pct` r ≈ −0.16,
`iv_spread` r ≈ +0.09, `dte_entry` r ≈ +0.21.

---

## 2026-07-12 — Three-run evaluation of `backtests/to_evaluate/` (v1 / v2 / v3) — replaces the 2026-07-10 evaluation

Same backtest set as the 2026-07-10 study, which was written when v3 had only
53 evaluated trades in a single BULL+L-VOL month. v3 is now complete over the
shared window — **154 evaluated real trades (2024-06 → 2025-12)** plus a full
proxy sweep (235 rows / 211 evaluated) — so this section supersedes the old
one entirely. Two of its loudest reads are REVISED below (score_total
"inversion" → credit-composition confound; credit-pt-basis suspicion →
resolved, not a bug).

Runs: **v1** (`v1_BacktestResults_20260625`, 122 evaluated — signal_eod entry
basis, pre-credit-split analysis: 1 credit row in 122, and its months only
partially overlap (has 2025-02, lacks 2024-06/07) → reference only, NOT
decision-grade for the rollback question), **v2** (115 evaluated, next_open),
**v3** (`BacktestResults`, current pipeline, 154 evaluated, next_open).

### Headline (real backtest rows)

| run | n | win% | mean pnl% | median | total $ | mean MFE | capture* |
|---|---|---|---|---|---|---|---|
| v1 | 122 | 60.7% | +0.20 | +0.61 | +24,027 | +1.15 | 0.14 |
| v2 | 115 | 48.7% | +0.03 | −0.08 | +12,336 | +0.90 | 0.11 |
| v3 | 154 | 48.1% | −0.02 | −0.24 | +4,394 | +0.86 | 0.04 |

*capture = Σrealized$ / ΣMFE$ over MFE>0 rows.

### Rollback verdict: CANNOT BE DETERMINED — do not roll back on this evidence

No v2-vs-v3 P&L comparison clears significance, and the sign of the comparison
depends on which book you look at:

- **Pooled real book:** Mann-Whitney p = 0.365. **Debit-only p = 0.583**
  (mean +0.17 v2 vs +0.13 v3 — statistically identical). **Credit-only
  p = 0.249.** Version-unique picks p = 0.112.
- **Combined real + proxy `strike_expiry_tweak` book** (both real-priced) the
  sign FLIPS: v3 +$51,772 (n=282, mean +0.13) vs v2 +$14,654 (n=168, mean
  +0.05), p = 0.494. The v3 edge is concentrated in its 128 tweak rows
  (+$47,378, half in 2025-03) — coverage/selection evidence per the proxy
  caveat, not exit-grade P&L, but it blocks any "v3 is worse" conclusion.
- **The ONLY statistically significant v2→v3 difference is behavioral, not
  quality: credit-structure emission share 19% → 34%** (chi² p = 0.012;
  combined books 18% → 33%). Credit trades lose in BOTH runs under the
  still-unvalidated credit exit profile (v2 −0.52 mean / 36% win, n=22;
  v3 −0.30 / 46%, n=52). v3's aggregate drag vs v2 is structure MIX feeding a
  known-broken exit profile, not worse per-trade signal quality.

Practical read: rolling back to v2 would mostly be rolling back the credit
emission rate. The cheaper, better-targeted moves are the credit-side items in
the queue below — and v3's book finally provides the credit-heavy,
multi-cluster window (52 real credit rows across 2024-07/08 + 2025-03/04) that
Attempts 8/9/11 were blocked on.

### Factors that predict outcome (analysis-tab columns only)

1. **Structure (from the play text) is the dominant factor.**
   `bear_call_spread` is toxic in BOTH versions — v2: −0.95 mean, 11% win,
   −$4,363 (n=9); v3: −0.82, 17% win, −$8,632 (n=18). Dropping bear_call alone
   turns v3's book +$4,394 → +$13,026 and v2's +$12,336 → +$16,699.
   Version-independent → a structure gate, not a rollback, addresses it.
   Debit vs credit overall: v3 debit +0.13 / credit −0.30.
2. **score_total pooled ρ −0.27 (p=0.001, n=154) — but it is a
   credit-composition confound, NOT a per-trade inversion.** REVISES 07-10:
   the scorer rates credit plays higher (mean 66.8 vs 55.8 debit), and credit
   loses. Within-side ρ: debit **−0.01** (p=0.95), credit −0.13 (n.s.). The
   ≥70 band still fails overall (n=38, 34% win, −0.40 mean; its worst cell is
   score≥70 ∧ credit: n=22, 32% win, −$6,768). Bottom line: score_total has no
   positive predictive value anywhere yet (flat within side, anti-selects via
   structure channel). The fix target is the score→structure-choice channel,
   not the rubric weights per se.
3. **score_vol is the only component negative WITHIN side** (debit-only
   ρ −0.20, p=0.047; pooled −0.31). 07-10's `score_price ρ −0.41` driver
   softens to +0.02 within debit — it was regime/composition, as suspected.
4. **iv_pct: third consecutive negative read (ρ −0.24, p=0.005; v2 −0.20,
   p=0.054) — but the hard >0.6 veto FAILS on dollars** and is rejected as a
   gate: the dropped set totals +$5.8–5.9k in BOTH runs (mean ≈ 0, 49% win —
   big winners live in the high-iv bucket too). Keep iv_pct as a sizing/flag
   input, not a filter.
5. **horizon** weakly positive (v2 ρ +0.20 p=0.034; v3 +0.10 n.s.) —
   consistent with the standing ≥45-DTE discipline, nothing new to ship.
6. **oi_confirm_pct, cpir, iv_spread, iv_skew: still ~flat** on realized basis
   (|ρ| ≤ 0.15, all n.s., both runs) — third dataset where the rollup signals
   don't discriminate realized P&L.
7. **Regime (market_regime label): BULL+L-VOL again the worst big bucket**
   (v3 n=40, −0.21) vs RANGE+E-VOL +0.49 (n=27) and BEAR+E-VOL +0.48 (n=9).
   New wrinkles vs the pooled 07-10 table: BEAR+H-VOL flips negative on v3
   (−0.53, n=15) and RANGE+L-VOL is bad (−0.34, n=17) — the "every BEAR bucket
   positive" pooled read does not survive on v3 alone.
8. **(Observation, not an analysis-tab column:) consensus names lose.** Picks
   appearing in BOTH v2 and v3 (same signal_date+ticker, 48 rows each, 79%
   same structure): ~34% win, −0.30/−0.34 mean in both runs. Version-unique
   picks: 55–58% win, +0.13/+0.27. The obvious/crowded flow names are the bad
   trades regardless of which pipeline version reads them.

### 07-10 queue item resolved: credit profit-target basis is NOT broken

All 10 v3 credit rows with path MFE ≥ +0.90 that exited `stop_loss` have
**mfe_day > days_held (10 of 10)** — the peak came AFTER the exit; MFE/MAE are
full-path-to-cap metrics, so no pt-basis bug. The real pattern: the 1×credit
stop fired (mean realized −1.32), then every one of these positions recovered
to ~full credit by expiry (9 of 10 are July-2024 bull_puts — the same whipsaw
cluster Attempt 9 flagged). This is now the single biggest quantified credit
pain point (10 trades × ~2.3 swing), but "no stop" was still worse in
aggregate in Attempt 11 — it goes to the credit exit study, not straight to a
config change.

### Actionable queue (in value order)

1. ~~**Re-run the credit exit study on v3's credit book**~~ — **DONE
   2026-07-13, see §Attempt 13.** Structure split resolved it: credit
   `stop_loss` removed (1× → null; pt 0.65 kept), the 10 whipsaws priced at
   +$3,646 on the bull_put book.
2. ~~**bear_call gate**~~ — **DONE 2026-07-13, see §Attempt 13.** Shipped as
   `entry.structure_veto: [bear_call_spread]` in config/backtest.yml (intake
   veto, honored by backtest + proxy); the credit study confirmed no exit rule
   redeems it (best variant still −$4.9k on n=37 combined).
3. ~~**Score→structure channel**~~ — **DONE 2026-07-13, see §Attempt 13c.**
   Root cause was the reverse arrow (structure→score via the self-fulfilling
   Vol-alignment rubric row); rubric + prompt contract rewritten, Step-4
   decoupling rule added. Within-side ρ re-test pends post-change emissions.
4. ~~**Per-regime exit switch** (standing, gated)~~ — **RE-CHECKED 2026-07-13,
   see §Attempt 13b: stays gated.** BEAR/H-VOL trail survives only weakly (no
   longer either group's winner), L-VOL tef-null fails LOO; new lead candidate
   for the eventual switch is `pt 1.10+` in E-VOL/RANGE (2025-03-concentrated,
   needs out-of-window validation).
5. ~~**iv_pct veto: rejected as a hard gate**~~ — **DONE 2026-07-13.**
   Downgrade recorded where operators read the column:
   config/conviction-score.md §IV percentile now states the veto was
   dollar-tested and rejected (dropped set +$5.8–5.9k both runs) and that high
   `iv_pct` is a sizing haircut / monitoring flag only. No veto was ever
   implemented in config/code, so nothing to remove. (Distinct from the stale
   IVspread ≈ −25 BEAR veto note in backtest-reference.md — that one still
   awaits re-derivation on the matched-pair definition.)

Roll-back re-check trigger: revisit only if the credit-side fixes (1–3) fail
to close the gap on a fresh window, or if a debit-only regression vs v2 ever
reaches significance (today p = 0.583, wrong direction to worry).

## Attempt 13 — credit exit study on v3's credit book: bear_call vetoed + credit stop removed (2026-07-13) ✓

**Motivation:** queue items 1+2 from the 2026-07-12 evaluation. v3's 52 real
credit rows (2024-06→2025-12, 6 months incl. the 2024-07/08 and 2025-03/04
clusters) finally break the March-TSLA single-cluster trap that froze Attempts
8/9/11. Inputs rebuilt from the v3 sheet exports (`backtests/to_evaluate/` →
`backtests/results.csv` + `results_proxy.csv`); study scripts' imports updated
for the `lib.barchart` refactor. **Calibration gates: real 52/52, tweak 42/42;
4 bs rows excluded as the documented ±0.0001 precision ties.**

**The decisive cut Attempts 8–12 never made: split the credit book by
STRUCTURE before tuning.** The global variant table is two opposite books
averaged together:

| Variant | bull_put real (n=34) | bull_put real+tweak (n=56) | bear_call real (n=18) | bear_call real+tweak (n=37) |
|---|---|---|---|---|
| PROD pt.65 sl 1× | +$1,836 (21/34) | +$2,814 (37/56) | −$8,632 (3/18) | −$11,221 (12/37) |
| **sl none (dollar stop only)** | **+$5,482 (31/34)** | **+$6,573 (48/56)** | −$14,574 | −$17,656 |
| pt .50 | +$132 (Δ −$1,704) | +$2,108 (Δ −$706) | −$4,608 (best) | −$4,912 (best) |
| sl 1.5× | +$3,356 (Δ-LOO2 −$286) | +$3,978 (LOO2 −$641) | −$11,193 | −$14,903 |
| trail .50/.50 | +$1,224 (Δ −$612) | +$2,863 (Δ +$50) | −$6,209 | −$7,990 |

**Shipped 1 — `entry.structure_veto: [bear_call_spread]` (config/backtest.yml,
new intake veto honored by both backtest.py and proxy.py; skip category
`vetoed`, proxy records vetoed plays as unevaluable instead of pricing them).**
bear_call is unredeemable by exit rules: PROD −$8.6k real / −$11.2k combined at
12–17% win, and the BEST variant on the combined set still loses $4.9k. Add
v2's −$4.4k (11% win, n=9) → version-independent, month-spread. The 2026-07-12
"pt .50 Δ-LOO +$452" tease was 100% bear_call rows (the same March-2025 TSLA
pair again, +$1,684/+$1,868); within bull_puts pt .50 is *negative*. Every
global credit-variant verdict in Attempts 8–12 was distorted by this mix.

**Shipped 2 — `simulation.credit.stop_loss: 1.00 → null`** (premium-based stop
removed; dollar_stop from risk sizing + defined-risk structural max loss remain
the backstop). This directly prices the 07-12 finding that 10/10 credit
stop_loss exits with path-MFE ≥ +0.90 recovered to ~full credit after the stop
fired. On the post-veto book (bull_puts): real +$1,836 → +$5,482 (win 21/34 →
31/34, Δ +$3,646, Δ-LOO +$2,652, Δ-LOO2 +$1,840); combined real+tweak n=56
agrees (+$2,814 → +$6,573, LOO2 +$1,954). Worst movers are bounded: TSLA rides
to dollar_stop −$1,166, KWEB expires −$892. `sl 1.5×` (halfway house) does NOT
survive LOO2 — the recovery is to ~full credit, so only full removal captures
it. pt stays 0.65 (`pt .50 sl none` is worse than `sl none` alone within
bull_puts, LOO2 −$26).

**Honesty caveat (selection discipline):** ~80% of the sl-none dollar gain
(+$2,995 of +$3,646 real) is the correlated July-2024 whipsaw week (9 same-week
bull_puts stopped in the drawdown, all recovered by expiry). Per-trade LOO
can't see that correlation. What keeps it shippable: the behavioral read is
10/10 (not a P&L accident), the non-July months are still net +$651 real /
+$764 combined with only −$46 against, the combined set agrees in sign and
magnitude, and the downside of being wrong is bounded by dollar_stop +
defined-risk sizing. **Rollback trigger:** if the next credit-heavy window
(≥15 fresh bull_put rows) shows sl-none losing to sl-1× there, restore the 1×
stop and log it here.

Not shipped: pt .50 (bear_call artifact, hurts bull_puts), underlying-breach
stops (still negative on bull_puts: und ±1% Δ −$2,032 combined — Attempt 9/11's
conclusion stands), trail variants (flat-to-negative within bull_puts).

### Attempt 13b — per-regime exit switch re-check on v3 (queue item 4): stays GATED ❌

`combined_exit_study.py --side debit` re-run on the v3 book (real 102 —
calibration 102/102 after fixing a 1-ulp float tie in the replay boundary
check (XLF 2024-06-21 sat exactly on sl=0.75; replay now rounds pnl to 10
decimals) — plus 86 tweak). The Attempt-12 group hypotheses, re-checked:

- **BEAR trail .50/.50** — still positive (Δ +$1,359, Δ-LOO +$493, n=34) but
  no longer the group winner: `pt 1.25 no trail` dominates BEAR (Δ-LOO
  +$2,282). Weakened.
- **H-VOL trail .50/.50** — still positive (Δ +$2,296, Δ-LOO +$1,135, n=45);
  group winner shifted to `BE ratchet @.50 + trail .50/.75` (Δ-LOO +$2,356).
  Direction (some giveback protection in H-VOL) persists; the specific variant
  doesn't.
- **L-VOL tef null** — Δ +$1,249 collapses to Δ-LOO +$42: "no robust winner".
  NOT confirmed on v3.
- **DIRECTIONAL tef null** — not checkable: v3 play cells don't parse into the
  `[…|intent|…]` bracket the study's intent tag expects (all rows land in
  `[?]`); fix the intent regex before the next re-check.

New wrinkle worth watching, NOT shipped: **raising the debit profit target
(pt 1.10–1.25, no other change) is the loudest global signal on v3**
(combined Δ-LOO +$5,650/+$6,791; real-only Δ +$7,585/+$5,570) — but on the
real book ~88% of it is 2025-03 (panic month, V-shaped recoveries blowing
through +90%), and it's actively bad in L-VOL (Δ-LOO −$1,772/−$4,343) and BULL.
Same story as every exit read since Attempt 12: the knob is regime-conditional
(E-VOL/RANGE/BEAR want to let winners run; L-VOL/BULL don't), which is exactly
the per-regime switch — and a switch fitted on the same window that motivated
it still needs out-of-window validation before it ships. Gate unchanged;
`pt 1.10 in E-VOL` is now the lead candidate cell when that validation window
exists.

### Attempt 13c — score→structure channel decoupled (queue item 3) ✓ (validation pending)

The 07-12 framing had the arrow backwards. It is not that high scores select
into credit structures — it is that **choosing a credit structure mechanically
raised the score**, via Step 5's Vol-alignment row, whose rubric was "IV/term
structure/skew fit the chosen structure (cheap-or-rising for debit,
rich-or-falling for credit)". Step 4's ladder already forces the structure to
match IV, so every ladder-consistent play banked those points automatically:
the component was consistency-with-your-own-rules dressed as evidence.
Measured on v3: score_vol mean 11.3 credit vs 9.6 debit; iv_pct mean 0.89
credit vs 0.61 debit; within credits score_vol tracks iv_pct (ρ +0.36) — i.e.
the vol row paid MORE for RICHER IV credits, exactly the losing bucket (iv_pct
ρ −0.24 on P&L). And score_vol is now negative within BOTH sides on v3
(ρ −0.20 debit p≈0.05, −0.21 credit), confirming 07-12 factor #3.

Shipped (all four analysis touch points kept in sync):
- **`config/analysis-framework.md` Step 5** — Vol-alignment rubric rewritten:
  score whether vol conditions support the *thesis* (realized-vs-implied gap,
  term structure, skew/IVspr/IVskew, expected IV path), never whether the
  structure matches the IV level (that consistency is Step 4's job; a mismatch
  invalidates the play instead of scoring low). Rationale note added beside
  the rubric so the old wording doesn't creep back.
- **`config/analysis-framework.md` Step 4** — explicit decoupling rule:
  conviction level never picks the structure in either direction (no
  de-risking high conviction into credits, no leverage-reaching on weak
  ideas); structure comes only from playbook + IV ladder. Plus the Attempt-13
  bear_call suspension callout (TF-S bearish now expresses as bear put debit
  or passes; table + bullets updated).
- **`scripts/analysis_pipeline/config.py`** (`ANALYSIS_PROMPT_CONTRACT`) —
  `score.vol` and `structure` field descriptions synced to the above (bear
  call spread: NEVER emit).

**Validation (open):** re-test within-side ρ (score_total and score_vol vs
realized) on rows emitted AFTER 2026-07-13 once a decent post-change sample
exists; also check the credit-emission share drops back toward v2's ~19% now
that bear_call is suspended and the vol row no longer subsidizes rich-IV
credits. Rubric *weights* deliberately untouched — per the 07-12 read, fix
the channel first, then re-measure.

## 2026-07-17 — Power check on `backtests/to_evaluate/` refresh: version comparison still underpowered; scoring-column keep/drop decision

Refreshed snapshot (unversioned = newest, exported 07-17): 170 real
BacktestResults rows + 263 priced proxy rows (433 pooled), vs v2's 115 real
and v1's 122 priced. All scored columns 100% filled on the pooled 433.

### Is the backtest volume sufficient to compare versions? NO

- **Minimum detectable effect** at these ns (α=.05, 80% power, pooled
  sd≈0.97): **~33 P&L pct-pts of mean difference**. Observed debit-only means
  are v1 +0.205 / v2 +0.166 / v3 +0.147 — a ~6-pt spread; p=0.64–0.89.
  Bootstrap 95% CIs on the debit means are ~35 pts wide and nearly identical
  (v2 [−0.01,+0.34], v3 [−0.02,+0.33]). Verdict unchanged from 07-12: the
  books are statistically indistinguishable.
- **Composition confound repeats**: headline means (v1 +0.205 → v3 +0.001)
  are driven by credit-emission share (0% → 19% → 33%) — credits average
  −0.30 to −0.52 while debits are flat-positive across all three versions.
  Never compare versions on the headline mean; compare within-side.
- **Coverage confound**: only 19–21 signal dates are shared between version
  pairs (v1 spans 59 backtested dates, v3 only 42). Shared-date comparison
  also null (p=0.29–0.44).
- **What sufficiency would look like**: ~500 priced rows per side to detect a
  17-pt mean difference, or ~780 pooled rows to confirm a factor rho of 0.10.
  Current pace (~430 pooled per snapshot) → keep collecting; re-run this at
  ≥800 pooled priced rows.

### Scoring-column signal on the refreshed pool (within-structure, credit confound removed)

- DEBIT (n=307): every component null — score_total ρ −0.00, flow +0.03,
  dealer −0.04, price −0.07, vol −0.02, catalyst +0.04 (all p>0.24). The
  raw pooled score_total ρ −0.17 is entirely the credit-composition artifact.
- CREDIT (n=126): score_vol ρ −0.20 p=0.02 — same self-fulfilling
  vol-alignment channel Attempt 13c decoupled on 07-13; every backtested row
  predates the fix, so this is confirmation of the diagnosis, not a failure
  of the fix.
- New pipeline-computed columns: price_vector ρ +0.04 (p=0.48),
  |price_vector| ρ −0.07, days_to_earnings ρ +0.08 (p=0.25) — no signal yet.
- Band table symptom (pooled): 70+ scores win 39% / mean −0.26 vs 40–69's
  56% / +0.25 — again composition (credits are over-represented in 70+),
  not an inverted signal within a side.

### Keep/drop decision on the additional scoring columns

- **Dropping the pipeline-computed columns does not lean the model at all**:
  score_price, score_catalyst, price_vector, days_to_earnings are joined at
  row-expansion time from fetched data — zero LLM tokens. Keep them; they are
  free option value for the ≥800-row re-test.
- **Only score_flow / score_dealer / score_vol cost model output.** None
  shows within-side signal, but n=307 debit can only detect |ρ|≥0.16 —
  "no impact" is not yet demonstrated, and every scored+backtested row was
  emitted under the pre-13c rubric. Decision: **keep emitting, do not drop
  yet** — the 13c validation explicitly needs post-2026-07-13 scored rows,
  and dropping now would abandon the components right before the first clean
  read on them.
- If one component must go for leanness, score_dealer is the candidate
  (ρ ≈ −0.04/−0.11, never significant in any cut, and the most speculative
  for the model to assess) — but gate that on the ≥800-row re-test too.

**Queue**: re-run this power check when pooled priced rows ≥800 or ~8 more
backtested signal dates accumulate post-13c, whichever first; that run is
also the 13c validation (within-side score_vol ρ + credit-emission share).
