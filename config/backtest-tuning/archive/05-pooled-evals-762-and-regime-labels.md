# Archive 05 — pooled evaluations at 762 rows, regime-label validation, regime-gap backfill

Covers 2026-07-21 (the >=800-gate evaluation and its addenda, edge-status
assessment, mechanical regime-label validation) and the 2026-07-22 regime-gap
backfill audit that the 25-date gate later closed.
See [../README.md](../README.md) for the full section index.

---

## 2026-07-21 — ≥800-GATE EVALUATION at 762 pooled priced rows (the run everything was queued for)

Snapshot exported 07-21 21:13: 304 real BacktestResults + 458 priced proxy
(264 strike_expiry_tweak, 194 bs_options_hist) = **762 pooled priced** (824
total backtest rows incl. 62 unevaluable — the ">800 runs"), 80 signal dates
2024-06-17 → 2026-03-02, real-priced tier 568 (75%). **312 rows are
post-13c-emitted** (2× the 07-19 sample), 68 of them credit. Methodology
identical to 07-17/18/19 (within-side + within-structure Spearman, tier
split, MFE/MAE asymmetry rule, joined-coverage features, BH-FDR 10% over 204
tests → 55 raw survivors, most mechanical path-vol). Join note: play-text
exact match now joins ~0 rows (play wording drifts between tab and backtest);
60-char-prefix join recovers 752/762.

### Headline 1 — the deployment ladder is VALIDATED; score_total is not a signal

- **Ladder ordering A > B > C > VETO is monotone in every cut**: pooled
  (+0.55/+0.19/+0.03/−0.39), real-priced, PRE-13c, POST-13c, and both time
  halves. A vs C MWU p=.0003, B vs C p=.0035 on post-13c rows alone. The
  07-19 "post-13c A < B" watch item RESOLVED: A +0.46 vs B +0.22 (A vs B
  p=.38 — ordered, not separated). Post-13c capped replay: top-1/day 76%
  win / +0.41 mean, top-3/day $19.1k of the $23.8k post-13c book from 97 of
  296 deployable rows. **deploy_tier is unblocked** (queue item 8): the
  ladder survived its out-of-derivation-sample test.
- **score_total remains decision-irrelevant everywhere it's been tested.**
  Post-13c within-side: debit −0.03 (n=244), credit −0.04 (n=68), all n.s.
  The 07-19 "first monotone band table" (n=157) did NOT survive doubling the
  sample: post-13c debit bands now run <40 → +0.24, 40–69 → +0.04, 70+ →
  +0.07, and within BOTH bull_call and bear_put the band slope is flat-to-
  negative. The 07-19 monotonicity was small-n noise. Selection power lives
  in structure × regime (the ladder), not in the model's self-score. The
  within-tier score tie-break survives only as "harmless".

### Headline 2 — 13c validation CLOSED (the fix did what it claimed)

- bear_call: 0 post-13c emissions (51 pre) in analysis AND backtest — veto
  permanent. Credit emission share (structure-segment classified) 30.6% →
  24.9% (χ² p=.066) — drifting down, still above v2's 19%.
- credit score_vol: pre-13c −0.218 p=.012 (5th confirmation of the old
  channel) vs post-13c **+0.209 p=.086** (n=68). The self-fulfilling
  vol-alignment channel is confirmed gone; if anything the rewritten rubric
  is weakly right-signed.
- Post-13c debit signal quality unchanged vs pre (win 46→52% band-mix
  dependent, MFE basis similar) — the rubric rewrite didn't degrade picks.

### Headline 3 — bull_put entry constraint DERIVED and SHIPPED (docs)

Real-priced bull_puts n=118: delta vs MFE +0.261 p=.004, DTE vs MFE −0.311
p=.0006, delta vs MAE −0.15 n.s. — the asymmetric read survives its 4th
snapshot. Credit-wide delta vs realized +0.213 p=.008 (FDR-survivor).
Bin structure says it's a **delta BAND, not a floor**, and the DTE edge is
concentrated:

- |delta| bins: ≤0.05 → −1.21 (n=3); 0.05–0.08 → −0.28 (n=18);
  **0.08–0.12 → +0.31, 78% win (n=40); 0.12–0.20 → +0.23, 77% (n=47)**;
  >0.20 → −0.39 (n=10).
- DTE bins: ≤22 → −0.76 (n=5); 22–45 → −0.15 (n=16); **45–59 → +0.47,
  87% win (n=46)**; 59–75 → −0.44 (n=16); >75 → +0.06 (n=35).

Shipped to config/deployment-rules.md (operator doc only — NOT an intake
veto; violating cells are dead money, mean −0.08, not poison):
**Tier-B bull_put = 0.08 ≤ |short-leg delta| ≤ 0.20 AND DTE ≤ 59, prefer
45–59 DTE.** Replaces the provisional 0.12/59 median split: 0.08 dominates
0.12 (n=60 vs 34, same 80% win, and stays positive post-13c: +0.15 vs
−0.19 for the strict cell, whose post-13c losers are all DTE ≤ 22 rows —
ORCL/SMH dollar_stops). The ≤0.20 cap and 45-DTE preference are thin-n
(10/21 rows) — marked PROVISIONAL in the doc. Caveat honestly: exact
thresholds are in-sample; the 4×-confirmed part is the direction.

### Attempt-13 rollback trigger — TESTED, NOT MET (credit sl-none stands)

The trigger ("sl-none loses to sl-1× on the next ≥15-row fresh bull_put
window") finally had its window: 51 post-13c-emitted real-priced bull_puts.
Path-approx replay (row exits at −1.0× credit if MAE ≤ −1.0, else actual):
actual mean +0.09 / −$6.3k vs sl-1× **−0.36 / −$8.4k** — 20 whipsawed
winners vs 8 capped losers. Full 118-row book agrees (+0.09/−$3.1k vs
−0.18/−$10.4k). No-stop is confirmed the right credit config; the fresh
window's dollar-negative total is tail concentration (ORCL −$1.6k, SMH
−$1.1k), not the exit rule.

### Queue-item verdicts (the rest)

1. **score_dealer drop candidate WEAKENED.** Full-book debit MAE −0.152
   p=.002 (4th confirmation) but post-13c-only −0.06 n.s. (n=172) — the
   drawdown channel is attenuating in the current rubric's emissions. Keep
   the column; drop case now needs a post-13c-only confirmation, don't act.
2. **bear_put × iv_spread MAE −0.197 p=.003 (n=222)** — 4th confirmation,
   asymmetric (MFE +0.08 n.s.), no bull_call mirror (−0.09 n.s.). Already
   encoded as the Tier-C rule; nothing further to ship.
3. **debit iv_pct FDR reads are composition** — within bull_call and within
   bear_put all iv_pct reads n.s. (mirrors the cpir lesson; rule 7 works).
   cpir kill re-confirmed within-structure (+0.09/+0.03 n.s.).
4. **BULL+L-VOL debit flat cell: first positive read** — pooled still −0.02
   (n=101) but post-13c +0.16 (n=39, 44% win). Sizing-down candidate
   weakens; keep watching, don't act.
5. **Book shape unchanged**: bull_call is the engine (n=273, 62% win, +0.44,
   +$128.1k pooled; +$115.1k real-priced; H1 +0.57 / H2 +0.47 — stable).
   bear_put: n=276, 40% win, −$10.6k — half the debit book earning nothing
   (the ladder's Tier-C handles it at deploy time; a framework-level
   emission demotion is the obvious NEXT candidate, not shipped). bull_put
   +0.03 mean / **−$5.7k dollars** despite 65% win — fat left tail, stays
   Tier-B-with-constraints, never A. bear_call −0.52/−$11.9k (veto right).
- **Regime cells repeat**: RANGE+E debit +0.45/+$69.0k (the book's profit);
   worst BEAR+H debit −0.31/26% win, RANGE+L credit −0.49, BEAR+H credit
   −0.38 — all three already VETO tiers. Stop-recovery re-validated (debit
   stops firm: 14% recover post-exit; credits 42% recover — sl-none right).
   Exit capture unchanged (median 0.36 debit / 0.70 credit, p25 negative
   both sides) — still waits on the per-regime exit switch study.

### Decisions

Shipped: deployment-rules.md bull_put constraint finalized (delta band
0.08–0.20, DTE ≤ 59, prefer 45–59) + ladder marked validated-at-762.
Not shipped: score_dealer drop (attenuating), deploy_tier pipeline column
(unblocked but cross-cutting schema change — needs its own pass), bear_put
emission demotion (new mechanism, propose first). Rollback not triggered.
The next data milestone: the 25 regime-gap dates (§2026-07-20) → re-read
the thin-n items (delta ≤0.20 cap, 45-DTE preference, post-13c A-vs-B
separation, BULL+L debit recovery) once they land.

### 2026-07-21 addendum — score_total REMOVED from ladder membership

Follow-up to the user's (correct) challenge: if score_total is
decision-irrelevant, its two membership clauses in deployment-rules.md were
untested legacy from the 07-19 derivation. Marginal-value test on the 762-row
book: (1) bull_calls promoted to A by score≥70 alone (n=27, non-RANGE/E)
perform like Tier B (+0.11 vs +0.24, MWU p=.47; post-13c +0.31 vs +0.39) —
clause removed, those rows demote to B. (2) "other debit score≥70" → B
(n=25, 23 of them bear_puts) is indistinguishable from the score<70 Tier-C
debits (−0.06 vs −0.00, p=.84; post-13c both negative) — the clause was a
bear_put leak into B; removed, those rows fall to C. (3) Tie-break replay:
score DESC +0.41 vs 500-draw random +0.37 (5–95% +0.19..+0.58) vs score ASC
+0.31 — no signal; kept only as a deterministic ordering, relabeled as such.
The score-free ladder is strictly better: pooled +0.64/+0.28/−0.02/−0.39,
monotone every cut; post-13c B-vs-C p<.0001; post-13c top-3/day $19.1k →
$30.3k (win 61% → 69%). score_total now appears nowhere in tier membership —
selection is structure × regime × entry-geometry only. (Post-13c A-vs-B
separation stays open: +0.50 vs +0.40, p=.98.)

### 2026-07-21 addendum 2 — within-structure sweep of the remaining columns

Completing the composition cut for every FDR survivor not yet checked
(real-priced, within-structure):

- **oi_confirm_pct: KILLED** — null within bull_call AND bear_put (all
  |ρ|≤.14 n.s.); the pooled debit-MFE read was structure composition.
- **iv_pct: KILLED both sides** — already null within debit structures;
  now also null within bull_put (realized −0.14 p=.15) → the credit-side
  pooled read was composition too. iv_pct has no measured effect anywhere
  (its Step-4 structure-choice role in the framework is untouched — that
  was never a P&L claim on this basis).
- **score_catalyst: path-vol proxy CONFIRMED, concentrated in bear_put**
  (MAE +0.33 p=.0003 with MFE −0.16 — inverse-mirrored; realized null in
  every structure). No P&L information.
- **score_flow: path-vol picker** (bear_put MFE +0.16 / MAE −0.21
  mirrored; realized null everywhere; bull_put MFE +0.18 p=.045 marginal).
- **price_vector: NEW watch item** — within bull_call realized −0.15
  p=.046 / MFE −0.18 p=.018 / MAE flat (asymmetric NEGATIVE: stronger
  price momentum → worse bull_call outcomes). Single marginal read,
  multiplicity-exposed — watch only, re-read after the 25 dates.
- **debit delta vs realized: NEW watch item** — post-13c debit realized
  +0.26 p=.001 (MFE +0.31 / MAE +0.40, shallower drawdowns AND more
  upside). Bigger-delta (more-ITM) debits doing better post-13c; prior
  snapshots called delta-MAE mechanical, but the realized read is new.
  Composition with regime not yet excluded — watch, don't act.
- bull_put iv_skew realized +0.30 p=.024 (n=55) — 3rd small-n
  appearance, still below FDR-proof; keep on the watch list.

Net per-column verdict after all cuts: the only columns with confirmed
decision-relevant effects are **delta + dte_entry (bull_put entry
constraint, shipped)** and **iv_spread (bear_put Tier-C rule)**;
score_dealer keeps a fading debit-MAE effect (post-13c n.s.); everything
else (score_total/flow/price/vol/catalyst as P&L predictors, oi_confirm,
cpir, iv_pct, iv_skew, days_to_earnings) is null, mechanical path-vol, or
composition artifact on realized AND MFE/MAE bases.

### 2026-07-21 addendum 3 — QUEUED: prompt-score drop rule + lean-versioned test track

**Queue item A — prompt-contract drop rule (decided, execution gated).**
After the 25 regime-gap dates (§2026-07-20) are analyzed AND backtested:
re-run the within-side/within-structure reads on the post-13c pooled book.
If `score_flow` and `score_dealer` are still null (realized + asymmetric
MFE/MAE basis), REMOVE both from the model emission contract — the usual
four touch points (ANALYSIS_PROMPT_CONTRACT in
scripts/analysis_pipeline/config.py, analysis_to_rows expansion, claude.md,
codex.md). `score_vol` is exempt from this rule: it's the component the 13c
rewrite targeted and its post-13c read is right-signed (+0.21 credit) —
it gets its own verdict at the next gate.

**Queue item B — lean enrichment profile + analysis versioning (user
decision 2026-07-21: compute less → scrape less → test faster; new sheet
tabs per version so books never mix).** The eval's column verdicts map onto
the enrichment chain as follows:

- **REVISED 2026-07-21 (same day, twice): NO scraper is droppable — the
  lean profile is SHELVED and `enrich_oi` stays in.** The chain of
  corrections: (1) the initial "lean = live input set" claim was WRONG —
  live runs happen on D+1 (measured: every live-run tab row has
  created−signal lag = 1 day), after enrich_oi for D has landed, so
  **91% of live rows carry a populated `oi_confirm_pct`** (n=100 lag-1
  rows, stable ~0.91 across every live date Jul 08–20); (2) enrich_oi's
  output is consumed beyond the killed `oi_confirm_pct` column —
  `eod_iv` is the traded-leg settlement IV inside IVspr/IVskew
  (`lib/flow_summary/core.py:_settlement_iv`; the counterpart legs are
  always EOD sidecar values, so without eod_iv the pair mixes intraday
  vs EOD IV and the like-with-like comparison breaks), and `iv_spread`
  is one of only TWO decision-relevant columns (bear_put Tier-C rule).
  `eod_delta` also feeds the OI-factor delta weighting. User decision:
  if other columns require the scrape, don't leave it out — enrich_oi
  KEPT for now. Backfill speed-ups must come from elsewhere (or from a
  future cheaper eod_iv-only fetch), not from dropping inputs that
  decision-relevant columns consume.
- **KEEP everything else**:
  - `fetch_iv_percentile` → USED in the analysis (Step-4 rich/cheap
    structure choice + IVpct rollup column) and needs no D+1, so live
    runs have it — keeping it keeps live and backfill inputs identical
    (user decision 2026-07-21, reversing the initial skip proposal).
  - `fetch_counterpart_iv` → `iv_spread` is a LIVE deployment rule
    (bear_put Tier-C) — dropping it blinds the ladder on new rows.
  - `fetch_price_catalyst` → `price_vector` is an open watch item
    (bull_call negative read), and `key_level` grounding +
    `score_price`/`score_catalyst` come from here at per-ticker cost.
  - `scrape_flow`/`compile_flow` — the analysis itself.

**Versioning rule (structural, from the pre/post-13c join trap):** any
input change = a NEW analysis version writing to NEW tabs (engine registry
tab names in scripts/analysis_pipeline/config.py); never append
changed-input rows to an existing tab. Evals read within-version; the
flow/dealer null re-test (item A) is valid on a lean-version book because
the null has been version-robust across v1/v2/v3 and pre/post-13c — but
say so explicitly when reading it.

## 2026-07-21 — Edge status: honest assessment + priority queue (post-≥800-gate)

Question (user): is the edge proven? Verdict: **confirmed in backtest,
concentrated, not yet proven live.**

**Solid:**
- Ladder ordering A > B > C > VETO monotone in every cut (pooled,
  real-priced, both time halves, post-13c holdout) and survived doubling
  the sample.
- Methodology held up: FDR over 204 tests, within-structure composition
  cuts (killed score_total/oi_confirm/iv_pct/cpir), MFE/MAE asymmetry
  rule. The book got stronger under scrutiny, not weaker.

**Why "proven" is still too strong:**
- The edge is essentially ONE cell: bull_call in RANGE/E-VOL (+$69k of
  the book's profit; top-3/day = 83% of P&L). Tier A partly encodes that
  cell — validation is partly circular (acknowledged in
  deployment-rules.md caveats). Honest claim: "the analysis picks good
  bull_calls in elevated-vol range markets," not broad edge.
- Credit side unproven: bull_put −$5.7k dollars despite 65% win (fat left
  tail); constraint-band thresholds in-sample, ≤0.20 cap thin-n.
- Rows within a date share one market path → not independent → MWU
  p-values somewhat optimistic (not previously logged). Time-half +
  post-13c splits partially compensate; cell-level n's smaller than they
  look (e.g. the 87%-win DTE 45–59 bin).
- Backtest ≠ fills: next-day-open entry on settlement-derived pricing,
  25% proxy-priced; live slippage/partial fills unmeasured.

**Priority queue (in order):**
1. **Close the live loop** — user is already deploying live per the
   ladder, but nothing records deploy_tier per live position or compares
   actual fills/exits to backtest assumptions. Ship deploy_tier, tag live
   entries, after ~30–50 live positions run the first live-vs-backtest
   eval (realized P&L by tier + fill vs assumed entry). Only this turns
   "confirmed in backtest" into "proven."
2. Finish the 13 remaining regime-gap dates — explicitly: **2024-11-01,
   2024-11-04, 2024-11-06, 2024-11-07, 2024-12-18, 2025-04-03,
   2025-05-05, 2025-08-12, 2025-11-20, 2026-03-06, 2026-03-12,
   2026-03-20, 2026-03-27** (election week + Mar-2026 = the untouched
   clusters where the edge claim is weakest). Per-date readiness and the
   exact remaining commands: §2026-07-22 below.
3. Per-regime exit switch study (exit capture median 0.36 debit, p25
   negative — biggest non-selection P&L lever).
4. bear_put emission demotion proposal (half the debit book dead money).
5. Credit tail management — bull_put dollar problem is concentrated
   losers (ORCL/SMH), not the exit rule; look at sizing / max-loss-per-
   underlying, since sl-none is confirmed right.

**Discipline note:** deployment-rules.md is now pre-registered — the live
walk-forward is only valid if rules stay frozen mid-window; changes queue
for the next gate.

## 2026-07-21 — Regime-label validation: 86 MARKET rows vs mechanical SPY/VIX truth

**Question (user)**: is the analysis market regime detecting correctly?

**Method**: parsed the directional + vol tokens from all 86 AnalysisClaude
MARKET-row regime labels and compared against a mechanical classification of
the same dates (yfinance SPY/^VIX; trend = close vs 50-SMA + 20d return, vol =
VIX level L/H at 20 with E/C from 5d VIX change — same family of rule as the
§2026-07-20 gap selection). 85 comparable dates.

**Headline**: raw agreement 55% directional / 55% vol — but the structure is
what matters, and it is much better than the headline:

- **Zero dangerous inversions.** L-VOL↔H-VOL confusions: 0/85 (when the
  analysis says L-VOL, VIX is never ≥20; 22/26 exact). BULL↔BEAR inversions:
  1/85, and it's 2025-04-25 "BULL + C-VOL" at the V-recovery start where the
  50-SMA rule still said BEAR — the analysis was early and *right*, the
  mechanical label lagged. All 13 analysis BEAR calls land on mechanical BEAR
  days (100% precision).
- **The dominant miss is systematic: RANGE-when-mechanical-BEAR, 22/85.**
  Mar-2025 slide, Apr-2025 aftermath, Jan-2025 grind all labeled RANGE. Root
  cause is the framework's own strict BEAR bar ("sustained decline ≥20% from
  highs") — SPY never got there, so −3%…−9% drawdowns become RANGE. Consistent
  with the framework text, but it means the book's "RANGE" bucket spans calm
  chop AND −8% slides.
- **E-VOL is over-used / sometimes wrong-signed.** 26 E-VOL calls, only 10
  mechanically expanding; 4 had VIX *falling* double-digits (2025-03-17/18,
  04-28/29) and 2026-07-09 was E-VOL at VIX 15.8 falling. The engine reads
  "expanding risk" from hedging flow/VVIX (forward-looking) rather than
  realized VIX change — defensible per the framework wording, but E↔C
  sign-flips are the one genuine vol error mode.
- **Contract violation, one-off**: 2025-02-24 MARKET row has no volatility
  label at all ("RANGE + RISK-OFF + HP") — framework requires it.

**Implication for the backtest evals**: every per-regime finding (07-12/07-13
per-regime exit switch: "BEAR/H-VOL want trail, L-VOL wants tef null"; the
regime×structure selection result) is grouped on ANALYSIS labels, and the
RANGE group is polluted with ~22 mechanical-BEAR drawdown days. Before
shipping any per-regime exit switch, re-cut the groups on mechanical labels
as a robustness check — if the trail benefit follows the mechanical BEAR days
rather than the labeled BEAR days, the switch should key off a mechanical
trigger (price vs SMA / VIX), not the model's label.

**Not queued as a fix**: relabeling would be an input change → new version →
new tabs. The label convention is internally consistent; the action item is
the robustness re-cut above, plus optionally tightening the framework's E-VOL
definition (require realized expansion, or split "hedging-implied" from
"realized") in the next version bump. Artifact:
scratchpad regime_validation.csv (per-date table, this session).

## 2026-07-22 — Regime-gap backfill: the 13 remaining dates, made explicit

Audit of `backtests/next_25_dates.md` (§2026-07-20 selection) against the
AnalysisClaude tab (89 distinct dates) + the Drive folder for each date.
**12 of 25 are analyzed; 13 remain.** Priority-queue item #2 now names them.

### Status table

| # | Date | Bucket (mechanical) | Compiled | Enrichment gap | Next step |
|---|------|---------------------|----------|----------------|-----------|
| 4  | 2024-11-01 | RANGE+H-VOL | etfs+stocks | — (full) | analyze | ✅ - analyze-bt
| 5  | 2024-11-04 | RANGE+H-VOL | etfs+stocks | — (full) | analyze | ✅ - analyze-bt
| 6  | 2024-11-06 | BULL+C-VOL  | etfs+stocks | no `oi_change`/`eod_iv` | `enrich-oi`, then analyze | ✅ - enrich-oi + analyze-bt
| 7  | 2024-11-07 | BULL+C-VOL  | etfs+stocks | no `oi_change`/`eod_iv` | `enrich-oi`, then analyze | ✅ - enrich-oi + analyze-bt 
| 8  | 2024-12-18 | RANGE+E-VOL | etfs+stocks | — (full) | analyze | ✅ - analyze-bt
| 12 | 2025-04-03 | BEAR+E-VOL  | etfs+stocks | — (full) | analyze | ✅ - analyze-bt
| 15 | 2025-05-05 | BULL+H-VOL  | etfs+stocks | — (full) | analyze | ✅ - analyze-bt
| 18 | 2025-08-12 | BULL+C-VOL  | **etfs only — stocks compiled MISSING** | all | re-scrape/compile stocks, full chain, analyze | ✅ - scrape + compile + enrich-all + analyze-bt
| 22 | 2026-03-06 | RANGE+E-VOL | etfs+stocks | — (full) | analyze | ✅ - analyze-bt
| 20 | 2025-11-20 | BEAR+E-VOL  | etfs+stocks | no `iv_pct` / price-catalyst | `iv-percentile`, `price-catalyst`, analyze | ✅ - iv-percentile + price-catalyst + analyze-bt
| 22 | 2026-03-06 | RANGE+E-VOL | etfs+stocks | — (full) | analyze | ✅ - analyze-bt
| 23 | 2026-03-12 | BEAR+H-VOL  | etfs+stocks | — (full) | analyze | ✅ - analyze-bt 
| 24 | 2026-03-20 | BEAR+H-VOL  | etfs+stocks | no `iv_pct` / price-catalyst | `iv-percentile`, `price-catalyst`, analyze | ✅ - iv-percentile + price-catalyst + analyze-bt
| 25 | 2026-03-27 | BEAR+E-VOL  | etfs+stocks | **none of oi/eod_iv/iv_pct/price-catalyst** | full chain, then analyze | ✅ - enrich-all + analyze-bt

Readiness column derived from the header of `stocks-flow-<YYYYMMDD>-compiled.csv`
in each Drive date folder (`oi_change`, `eod_iv`, `iv_pct`, `price_*`, `catalyst`).
Row counts are 492–500 on all 12 existing stocks files — no thin days.

**8 analysis-ready right now** (#4, 5, 8, 12, 15, 22, 23 + #6/#7 once
`enrich-oi` lands): `python3 -m scripts.analysis_pipeline --date <D>` each.
**5 need collector work first**: #18 (worst — stocks compiled absent), #20,
#24 (two stages each), #25 (full chain), #6/#7 (`enrich-oi` only).

### Queue-file drift (fix before re-running the shell driver)

`backtests/enrich_queue_{a,b}.txt.done` is NOT a reliable record of analysis
state — it tracks *enrichment* stages, and the "(done analysis)" annotations
were hand-appended and are wrong in one place: the queue-A line
`2025-04-03 price-catalyst (done analysis 2025-03-28, 2025-03-31, 2025-04-09)`
records analysis for neighbouring dates, and **2025-04-03 itself has no
AnalysisClaude rows** despite being fully enriched. Also, dates #1–7 and #8–9
were never in either queue file (marked "run manually"), so 2024-11-01→11-07
and 2024-12-18 have no `.done` entries at all even though 11-01/11-04/12-18
are fully enriched. Treat the AnalysisClaude tab as the only source of truth
for "analyzed"; the `.done` files only for "enriched".

### Why these two clusters matter most

Both untouched clusters are exactly where the §2026-07-21 honest-assessment
weakness sits. Election week (#4–7) is the only RANGE+H-VOL → BULL+C-VOL
vol-crush transition in the selection, and the book's edge is concentrated in
bull_call/RANGE/E-VOL — a C-VOL crush regime is the natural falsification
test for it. Mar-2026 (#22–25) is 4 of the 13 and the only *recent*
BEAR+H-VOL/E-VOL stretch, i.e. the out-of-sample end of the walk-forward, and
it also feeds the §2026-07-21 regime-label finding (RANGE-when-mechanical-BEAR
pollution) with dates the model has not yet labeled.

Gating: queue item A (drop `score_flow`/`score_dealer` from the prompt) and
the PROVISIONAL bull_put band re-read both wait on all 25 being analyzed AND
backtested — 13 dates ≈ 13 × ~10 plays, enough to move the post-13c book.

