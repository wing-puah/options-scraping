# ML combination-search plan (written 2026-08-11 — **RUN 2026-08-11**)

> **Status: executed, plus a DEPLOY arm (addendum 2) run the same day.**
> Deploy-arm verdicts: **D1 NOT MET** (bear selection still unfixable under
> the new exit), **D2 MET** (the hedge is real — bear pays on the deployed
> book's worst dates), **D3 NOT MET** by $86 of worst-date, **D4 ADOPTED**
> (`|delta| high first` picks the better bear within a day, all three years,
> shipped exit too), **D5 post-hoc, does not reproduce**.
>
> Results and verdicts live in
> [`current.md`](current.md) §"2026-08-11 — ML combination search RUN".
> Phase 5 verdict: **NULL RESULT** (no model beats the ladder). Bear arm:
> **B1 NOT MET** (no conditioned bear subset survives), **B2 MET**
> (`be_after: 0.50` keyed to bear debit spreads). Deviations at run time, both
> declared before running: sklearn HistGradientBoosting in place of
> LightGBM/XGBoost, and an added "abstain" replay variant so the ladder's right
> to trade nothing is not an unfair advantage. Code: `scripts/backtest_study/`.


Goal: determine, with models instead of hand-cut screens, **which combination
of structure × regime × entry geometry × enrichment columns best predicts
play outcome** — and whether any learned rule beats the shipped score-free
ladder. This document is the pre-registration scaffold; nothing here has been
executed. Any deviation at run time must be recorded as a deviation.

## Why a plan first

The tuning history (current.md + archive/) already burned every failure mode
this study is exposed to: post-hoc slicing generating three verdicts in one
session (addenda 11–14), composition proxies masquerading as signal
(BEAR_HE ≈ bear_put; oi_confirm/iv_pct killed by composition), one market
window carrying 94% of an effect (Mar–Apr 2025), and score_total looking
monotone on noise (07-19 vs 07-21). ML amplifies all four if the protocol is
loose. Hence: benchmark fixed in advance, validation fixed in advance, ship
criteria fixed in advance.

## Ground rules (non-negotiable, inherited from the tuning log)

1. **Benchmark = the shipped ladder.** The number to beat is the score-free
   deployment-rules.md ladder's **top-3/day A-then-B replay, out-of-fold**
   (completed book: +$22.7k / +$44.8k / +$8.8k by year; monotone tiers every
   year). A model that cannot beat a 4-rule checklist out-of-sample does not
   ship, whatever its AUC.
2. **Everything date-clustered.** Rows within a signal_date share the tape;
   the effective sample is ~118 dates, not ~1,100 rows. All CV splits group
   by date; all CIs are date-clustered bootstrap.
3. **Pricing-tier discipline.** Train on real + strike_expiry_tweak only
   (n≈817). bs_options_hist rows are excluded from training AND from any
   headline metric (the 08-11 entry shows why: +$49k of model-priced $).
   Report bs-tier performance separately as a curiosity only.
4. **Window-dominance checks are mandatory.** Every headline reported
   ALL / ex-Mar–Apr-2025 / ex-Feb–Apr-2026. A learned rule whose gain
   concentrates >70% in one window is recorded, not shipped.
5. **No deep learning.** At ~800 usable rows / ~118 dates, the model class
   is regularized linear, shallow trees, and gradient boosting with heavy
   regularization. Anything bigger fits the windows, not the market.
6. **Composition-proxy test (rule 7).** Any feature the model ranks highly
   must be re-tested *within* structure before being named as signal — the
   oi_confirm/iv_pct trap.
7. **Known inherited bias.** The book is in practice ≤60-DTE (h≥180
   unpriceable with real data — 07-27 §3). Whatever the model learns, it
   learns about short-dated spreads; say so in any output.

## Phase 0 — dataset assembly + leakage audit

One row per priced play from the deduped pooled book (dedup key
date|ticker|structure|play, within-tab then proxy-minus-real).

**Features (frozen at decision time — D+1 morning, post-enrichment):**

- Structure (one-hot), horizon bucket, direction (long/short delta), credit
  vs debit.
- Market regime tokens from `market_regime` (direction / vol / RISK-OFF /
  HP flags), mech regime from `lib/mech_regime.py` (SPY/VIX — refresh the
  table first), stock-regime leading token from `regime`.
- Entry geometry: |delta|, dte_entry, iv_entry_pct, entry_premium_total /
  max_loss_per_contract (defined-risk width).
- Enrichment: iv_spread, iv_skew, iv_pct, oi_confirm_pct, cpir.
- Score components: score_flow, score_dealer, score_price, score_vol,
  score_catalyst, score_total — **post-13c rows only** for any score
  feature (pre-13c scores anti-select; encode a `post13c` indicator and
  interact, or drop pre-13c rows in score ablations).
- Calendar: day-of-week, month (regularized hard; these are confound
  detectors, not features to ship).

**Leakage audit (gate to Phase 1):** for each feature, verify it is
available at deployment time. oi_confirm_pct is D+1-enriched and live
analysis runs after enrich_oi lands, so it is legitimate; anything computed
from the price path after entry (MFE/MAE, exit_reason, days_held) is a
label, never a feature. iv_spread is blind on unenriched dates — impute
with a missing-indicator column, never silently drop rows (missingness is
correlated with the 2026 window = with the label).

**Labels:** primary **E** (`pnl_at_cap_pct`, exit-free — the selection
measure per addendum 13); secondary **R** (PROD exits) and binary E>0.
Optional auxiliary: MFE-asymmetry class, for interpretation only.

## Phase 1 — baselines (must run before any model)

- **B0:** ladder replay out-of-fold (the benchmark).
- **B1:** logistic regression on E>0 with structure × market-direction ×
  vol only — does the model rediscover the ladder? If B1 ≈ ladder, the
  ladder is near the information ceiling of those columns.
- **B2:** elastic-net linear regression on E with the full feature set —
  the "is there anything linear left" check.

## Phase 2 — models

- **M1:** LightGBM (or XGBoost) on E, depth ≤ 3, min_child_samples ≥ 30,
  strong L1/L2, early stopping on the walk-forward validation block.
  Monotone constraints where theory is unambiguous (none forced initially).
- **M2:** same on binary E>0 (classification often stabler at this n).
- **M3:** a single depth-3 decision tree on the survivors' features — the
  "ladder v2" candidate. This is the only model whose output can ship,
  because only it reduces to a human checklist (see Ship form below).

## Phase 3 — validation protocol

- **Primary: purged walk-forward.** Expanding window by date; test blocks
  of ~15 trading dates; **embargo = 120 calendar days** between train end
  and test start (path_cap_days — outcome windows overlap, so unpurged CV
  leaks the label; López de Prado purged-CV rationale).
- Secondary: GroupKFold(signal_date) for variance estimates only.
- **Metrics, in order of authority:** (1) out-of-fold top-3/day replay $
  and mean R vs B0; (2) mean E of selected rows, date-clustered CI;
  (3) per-year sign stability (the 08-08 screen standard: same sign every
  year present); (4) rank metrics (Spearman of prediction vs E) last.
- Every metric also cut: ex-window (rule 4), real-tier-only, post-13c-only.

## Phase 4 — attribution + robustness

- SHAP / permutation importance on M1/M2 to *name* the combinations.
- Within-structure re-test of every top-5 feature (rule 6).
- Ablations: full model vs ladder-features-only vs enrichment-only vs
  scores-only — how much does anything beyond structure × regime add?
  (The 07-21 column sweep predicts: little — only delta+dte on bull_put
  and iv_spread on bear_put were decision-relevant.)
- Stability: refit per year, compare feature rankings; a combination that
  reorders every refit is window fit.

## Phase 5 — pre-registered ship decision

Written now, evaluated once, no re-cuts:

- **SHIP (as ladder v2)** iff the M3 tree's top-3/day out-of-fold replay
  beats B0's by a margin whose date-clustered 95% CI excludes zero, AND
  the gain is positive in ≥2 of 3 years, AND survives both ex-window cuts,
  AND the tree's rules pass the within-structure composition test.
- **ADOPT AS TIE-BREAK** iff M1/M2 rank-order adds value within tiers
  (out-of-fold, same CI standard) but no tree beats the ladder outright —
  the model score replaces score_total as the within-tier ordering only.
- **NULL RESULT** otherwise — recorded as "the ladder is near the ceiling
  of this data", which is a finding, not a failure. Given the 07-21 sweep
  and the one-factor structure of this book, this is the modal outcome.

**Ship form:** only human-readable rules ship (deployment-rules.md is an
operator checklist). A black-box score never gates deployment; at most it
tie-breaks within a tier, clearly labelled with its validation window.

## Artifacts + hygiene

- Code under `scripts/backtest_study/` — TRACKED, not `backtests/` (which is
  gitignored in full, the 07-22 addendum-10 finding: the producer of a
  production input lived on one laptop). The loader (`scripts/backtest_study/book.py`)
  is a port of the same dedup/calibration as `exit_switch_mech_study.py` so
  setup differences can't explain answer differences.
- Outputs to `backtests/study_output/` (data artifacts stay
  untracked); a RESULTS.md per run; this file gains an addendum per phase,
  verdicts only at Phase 5.
- No production config, prompt, or ladder change from any phase before the
  Phase-5 evaluation.

---

## Kickoff addendum (2026-08-11) — settled choices + the BEAR arm

Written BEFORE any code ran. The three open choices are settled, and an
operator-directed second arm is added and pre-registered here.

### Open choices, settled

1. **2026 rows train.** They enter the expanding walk-forward (so they are
   only ever *tested* out-of-fold), rather than being held out wholesale —
   ~600 training rows is too thin, and 2026 is the regime the ladder now
   deploys into. A single extra "train ≤ 2025 → test 2026" epoch is reported
   alongside as the strictest cut, not as the headline.
2. **E-only models in v1.** R entangles the exit config; E is the selection
   measure. R is used for evaluation (replay $, tier means) and is the label
   of the separate exit arm below, which uses the replay harness, not a model.
3. **No ticker/sector features in v1**, per the plan default. Revisited only
   in the Phase-4 ablation.

### The BEAR arm (new — operator instruction, 2026-08-11)

Operator: *"I don't want to fully remove the bear positions as those are
still necessary especially when the market are choppy. Assume that the exit
plan might not be fully tuned for the bear positions as well."*

This reframes the pending bear_put decision from **demote/keep** to **when**.
The 08-11 completed-book cut satisfied all three addendum-13 DEMOTE criteria
(E −0.358, CI [−0.460, −0.256], both halves negative), so the blanket case is
settled and is NOT re-litigated here. What is open, and what this arm asks:

- **B1 — selection conditioning.** Within bear structures, is there a subset
  defined by *decision-time* variables (mech cell, model regime, |delta|,
  DTE, iv_spread, credit/debit) whose E is ≥ 0 and which reproduces? Ship
  form is a "bear allowed when …" clause, not a blanket veto.
- **B2 — exit fit.** Is PROD mis-tuned for bear rows specifically? Bear rows
  are the population with |MAE|/MFE 1.25 (vs bull_call 0.51) — mirrored
  path-vol, which is exactly where exit shape can matter. Exit configs are
  drawn ONLY from the frozen grid already validated in
  `exit_mechanism_study.py`; this is not a new mechanism search.

**Decision rule, fixed now:**

- **KEEP-CONDITIONED (B1 ships)** iff a subset has mean E ≥ 0 with a
  date-clustered 95% CI whose lower bound > −0.05, is positive in ≥ 2 of the
  3 years present, survives both window cuts (ex-Mar–Apr-2025,
  ex-Feb–Apr-2026), holds n ≥ 40, and is expressible in ≤ 2 clauses a person
  can check at deploy time.
- **EXIT FIX (B2 ships)** iff a frozen-grid config beats PROD on bear rows by
  mean R with a date-clustered CI excluding zero AND survives leave-one-date-
  out (the test that killed the per-regime switch twice) AND does not degrade
  the non-bear book (it would be keyed to bear rows only).
- **NEITHER** → the standing recommendation stays "bear structures are
  Tier C / not deployed on their own", and the operator's chop hedge is
  documented as a *portfolio* decision the book cannot price (see caveat).

**Pre-registered expectation** (so a post-hoc story can't be told): given
E < 0 in every year and the mirrored MFE/MAE, the modal outcome is NO stable
positive bear subset. The most likely exception, if there is one, is BEAR or
E-VOL mech cells — the "choppy market" case the operator names. Anything
found outside that must be treated as a candidate, not a finding.

**Caveat that must appear in any bear conclusion.** This book measures each
play standalone. It cannot measure the hedging value of holding a bear
position against a long book — a play with negative expected standalone P&L
can still be correct as insurance. So "no positive bear subset" is a
statement about bear plays as *independent* selections, and never an argument
against a deliberately-held hedge.

## Open choices to settle at kickoff (deliberately not pre-decided)

1. Whether 2026 rows enter training or are held out entirely as the final
   test epoch (cleaner, but leaves ~600 training rows).
2. Whether R-labeled models are run at all in v1, or E-only (R entangles
   the exit config; E is the selection measure).
3. Ticker/sector features: informative but high-cardinality at this n —
   default is to exclude in v1, revisit in ablation.

---

## 2026-08-11 addendum 2 — DEPLOY arm (`D`), pre-registered BEFORE running

The 08-11 bear arm answered two questions (B1 selection, B2 exit) and closed
with the caveat that the chop hedge is "a *portfolio* decision the book cannot
price". That caveat is **too strong**: 107 of the 111 bear dates also carry
non-bear rows, so the concurrent book exists and the portfolio question is
testable on it. The operator's instruction stands — bear positions are to
remain deployable — so this arm asks the deployment questions B1/B2 skipped.

Same book, same protocol (`scripts/backtest_study/protocol.py`), same frozen exit
grid. No new columns, no new mechanism. Code: `scripts/backtest_study/bear_deploy.py`.

**What B1 could not answer, and why a new arm is not a second bite.** B1 asked
an *absolute level* question — is there a bear subset with mean E ≥ 0 — and the
answer is no in 496 subsets. Every question below is a *different estimand*,
each with its own pre-registered rule:

- **D1 — joint selection × exit.** B1 screened on E under the PROD exit; B2
  then changed the exit. The pair was never evaluated together. Re-screen the
  identical pre-declared clause vocabulary on **R replayed under
  `be_after: 0.50`** — what a deployed bear position actually returns.
  *SHIPS iff:* n ≥ 40, mean R ≥ 0, date-clustered CI lower bound > 0, positive
  in ≥ 2 years, both ex-window cuts ≥ 0, ≤ 2 clauses. Survivor count is read
  against the ~5%-of-tested false-positive expectation, as in B1.
- **D2 — hedge contribution (the caveat, tested).** Per-date, compare the
  deployed ladder book (top-3/day of tiers A/B) with and without a bear sleeve.
  Report the date-level correlation of the two sleeves and, decisively, what
  the bear sleeve does **on the deployed book's losing dates**.
  *A hedge is REAL iff:* bear-sleeve mean R on the deployed book's worst-decile
  dates is > 0 AND the date-level sleeve correlation is < 0, both reproducing
  in ≥ 2 years. A negative-carry hedge that pays in the tail is still a hedge;
  one that loses in the tail too is just a second losing book.
- **D3 — sizing.** Sweep an added bear sleeve at fraction f ∈ {0, ¼, ½, 1} of
  standard size. *DEPLOYABLE AT f iff:* the combined book's max drawdown and
  worst-date loss are both no worse than f = 0, judged on dollars.
- **D4 — conditional pick (the operator's actual question).** Given the
  operator WILL take a bear position on a given day, does any decision-time
  variable pick a *better-than-average* one? This is a **within-date paired**
  test on dates with ≥ 2 bear candidates — immune to the level problem that
  sinks every B1 subset, because the day is its own control.
  *ADOPTED iff:* mean within-date rank gain over the day's bear average has a
  date-clustered CI excluding zero AND every leave-one-date-out fold positive.

**Pre-registered expectation.** D1 modal outcome NULL (the exit shifts the mean
~+0.04; the level problem is ~0.5 deep). D2 is the arm most likely to return
something, and is also the only one that would justify deploying a
negative-expectancy structure. D4 is a genuine coin-flip. Nothing in this arm
may change production config; a MET criterion produces a recommendation only.

**Inherited caveats.** Standalone pricing still cannot see margin, assignment,
or the operator's real position sizing; D2 approximates a hedge as
equal-weighted concurrent dollars, which is a *proxy* for, not a measurement
of, a held hedge. Bear rows are 88% `bear_put_spread` and only 6 are naked
`long_put` — conclusions are about bear *spreads*; the naked-put hedge the
operator sometimes substitutes remains untested for lack of rows.
