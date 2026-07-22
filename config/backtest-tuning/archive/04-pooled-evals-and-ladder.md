# Archive 04 — Pooled evaluations and the deployment ladder (2026-07-18 → 07-20)

Part of the [backtest tuning log](../README.md). Covers the 607-row and 523-row
pooled reads ahead of the ≥800 gate, the deployment ladder
(`config/deployment-rules.md`), and the regime-gap-driven next-25-dates selection.

---

## 2026-07-19 — Final evaluation at 607 pooled rows (early, ahead of the ≥800 gate; first post-13c read)

Snapshot exported 07-19 22:21: 249 real BacktestResults + 358 priced proxy
(215 strike_expiry_tweak, 143 bs_options_hist) = **607 pooled** (76% of the
gate; detectable |ρ| ≈ 0.11 pooled, ≈ 0.22 credit-side), 63 signal dates
2024-06-17 → 2026-02-25. Real-priced tier (real+tweak) = 464 rows (76%).
Methodology identical to 07-17/07-18/07-19 (within-side + within-structure
Spearman, tier split, MFE/MAE asymmetry rule, BH-FDR 10%). New this run:
**157 backtested rows are first-emitted after 2026-07-13** (joined to
AnalysisClaude by date+ticker+play, minimum `created_datetime` = first
emission; 10 rows unjoinable) — the first sample under the 13c rubric,
covering 17 signal dates incl. genuinely new windows (2024-08 chop,
2025-05, 2026-02 tail).

### 13c validation — early reads all point the right way (n small, keep gate)

- **bear_call veto: fully effective.** 0 post-13c emissions with bear_call as
  the chosen structure (51 pre-13c), 0 backtested. (5 post-13c plays *mention*
  "bear call" in rationale text only — "expressed as debit because bear call
  is suspended" — a text-classifier trap for future share measurements: always
  classify on the structure segment, not the whole cell.)
- **score_vol sign flip, exactly as the 13c diagnosis predicted.** Post-13c:
  debit +0.13 (p=.16), credit +0.04 (n=34, n.s.) vs the pre-13c −0.20 credit
  read confirmed on four consecutive snapshots. The self-fulfilling
  vol-alignment channel is gone from the post-fix emissions.
- **score_total positive within-side for the first time**: post-13c debit
  ρ +0.138 (p=.127, n=123; detectable ρ at this n ≈ 0.25 — underpowered, not
  significant). Post-13c band table is **monotone for the first time ever**:
  70+ → 70% win / +0.30 mean (n=27); 40–69 → 57% / +0.14; <40 → 54% / +0.04.
  Every prior snapshot had 70+ as the WORST band (composition). Do not
  celebrate until ≥800; do record that nothing is inverted anymore.
- **Credit-emission share did NOT fall back to v2's ~19%**: structure-segment
  classified share 30.9% pre → 27.8% post (χ² p=.45). The mix shifted within
  credits (bear_call → 0, bull_put remains). Watch: if bull_put entry
  constraints ship (below), share should drop further.
- **Post-13c credit book looks great (79% win, +0.20 mean, n=34) but is
  confounded** with the Attempt-13 exit change (all post-13c rows were
  backtested under sl-none; exit mix: 23 profit_target / 6 cap_open / 3
  dollar_stop / 2 expired, zero stop_loss by construction). The
  exit-independent MFE-basis read shows post-13c credit signal quality is
  *similar*, not better (worked-rate 74% vs 80% pre). The dollar improvement
  is the exit config + structure mix doing what Attempt 13 designed, not a
  smarter signal. Debit signal quality unchanged (worked 69% both, χ² p=1.0)
  — the rubric rewrite did not degrade debit picks.

### Queue-item verdicts at 607 rows (real-priced tier, joined coverage)

1. **bull_put delta/DTE — CONFIRMED third time, now realized-significant
   credit-wide.** Within real-priced bull_puts (n=95): delta vs MFE +0.315
   p=.002, DTE vs MFE −0.385 p=.0001, delta vs MAE flat (−0.10 n.s.) —
   asymmetric, not path-vol. Credit-wide delta vs *realized* now +0.23
   p=.009 (survives FDR). This is the ripest unshipped item:
   **min-delta + max-DTE entry constraint on bull_puts** — propose deriving
   thresholds at ≥800 (or ship conservatively now: the effect has survived
   every cut since 07-18).
2. **score_dealer drawdown-without-upside — third confirmation** (debit MAE
   −0.149 p=.006, MFE +0.05 n.s., realized +0.02 n.s.). The drop-candidate
   case is now as solid as it will get pre-800; it costs model output tokens
   and buys deeper drawdowns.
3. **bear_put × iv_spread — CONFIRMED, survives FDR** (MAE −0.330 p=.0001
   n=135; MFE n.s.; no bull_call mirror −0.07). Sizing-haircut/entry-flag
   candidate for bear_put when iv_spread strongly positive.
4. **BULL+L-VOL debit still dead flat** (n=83 real-priced, mean −0.03,
   −$5.8k). The modal cell earns nothing; sizing-down candidate stands.
5. **cpir stays dead** — pooled MAE +0.32 is pure bull_call-vs-bear_put
   composition again (median cpir 0.97 vs 0.10; within-structure +0.09/+0.05
   both n.s.). The 07-19 kill is re-confirmed at joined coverage n=312.
6. **credit score_catalyst vs MFE (−0.30)** decomposes as before: bear_call
   −0.47 (vetoed, moot), bull_put −0.16 n.s. — ignore.

### Book shape (pooled / real-priced) — repeats 07-18 exactly, sharper

- **bull_call remains the entire P&L engine**: n=223 pooled, 60% win, mean
  +0.41, +$105.9k (real-priced +$96.8k). bear_put flat on huge n (203/154,
  mean +0.05/+0.03, median −0.19/−0.54, 45%/42% win). bear_call −0.52 mean,
  −$11.9k (veto validated again). bull_put mean ≈ 0 with 64–69% win + fat
  left tail — exactly the shape items 1 above targets.
- **Regime cells**: RANGE+E-VOL debit +1.19 (n=42, **+$66.2k — most of the
  book's profit sits in this one cell**); worst remain RANGE+L-VOL credit
  (−0.77), BEAR+H-VOL debit (−0.30, medMFE +0.29 — still the "never goes
  green" veto candidate) and credit (−0.40), RANGE+H-VOL both sides negative.
  Per-regime handling stays the most-supported gated follow-up.
- **Stop-recovery re-validated at 4× the original sample**: 14% of 134
  stopped real-priced debits later exceeded +25% MFE (stops firm); 43% of 44
  stopped credits recovered, median to full profit — the Attempt-13 credit
  stop removal keeps checking out.
- **Exit capture**: median 0.41 debit / 0.70 credit; 25th percentile negative
  both sides (39%/35% of MFE>10% trades still realized a loss) — unchanged;
  waits on the per-regime exit switch study.
- BH-FDR (102 tests): 18 survivors; after the mechanical path-vol discount
  (delta/dte/horizon/iv_entry/price_vector vs MAE debit; dte/horizon vs MFE
  credit) the non-mechanical set is: bull_put/credit delta (MFE + realized),
  score_dealer MAE, bear_put×iv_spread MAE, credit score_catalyst MFE
  (bear_call artifact), debit score_flow vs MFE (+0.14 p=.012 — first
  appearance, watch only), debit iv_pct vs MAE (−0.18, near-mirrored, likely
  path-vol).

### Decisions

**Nothing ships tonight** — the gate discipline holds (607/800, post-13c
n=157/34-credit, and the loudest new reads are confirmations of already-queued
items, not new mechanisms). The queue for the ≥800 run is unchanged except:
(1) bull_put min-delta/max-DTE is promoted to "derive thresholds and ship at
≥800 unless it reverses"; (2) the 13c validation now has a positive early
read — finish it at ≥800 with the same joined-emission method; (3) always
classify emission share on the structure segment (bear-call-mention trap).

## 2026-07-18 — Early re-run of the pooled power check at 523 rows (user-requested, ahead of the ≥800 gate)

Snapshot exported 07-18 21:18: 220 real BacktestResults + 303 priced proxy
(182 strike_expiry_tweak, 121 bs_options_hist) = **523 pooled** (65% of the
gate; detectable |ρ| ≈ 0.12 pooled, ≈ 0.19 credit-side). Signal dates
2024-06-17 → 2026-02-04, 53 dates — **zero backtested rows post-13c** (43
post-13c AnalysisClaude rows over 4 dates exist but are unbacktested), so
this is still entirely a pre-fix book; the 13c validation remains open.
Methodology identical to 07-17 (within-side Spearman vs realized_pnl_pct;
composition confound removed). ~40 correlations scanned — expect ~2 false
positives at p<.05 from multiplicity alone.

### DEBIT (n=369): still nothing

Every score component and every feature null (all |ρ|≤.06, p≥.24), incl.
the pipeline-computed price_vector/days_to_earnings. Real-only (n=151)
same; cpir +0.155 p=.06 real-only is absent pooled (+0.00) → noise.

### CREDIT (n=154): three reads worth flagging, checked within-structure

- **bull_put `delta` ρ +0.303 p=.001 (n=111) — DOWNGRADED to watch-only
  after a pricing-tier cut.** The pool has three pricing tiers: real
  BacktestResults, proxy strike_expiry_tweak (neighbor contract but REAL
  Barchart history; pct_real_days ≈ 0.99), and proxy bs_options_hist
  (model-priced). On the real-priced 83 bull_puts (real+tweak) the read is
  only ρ +0.184 p=.095; in the BS tier alone it's absent (−0.08 n.s.,
  n=28). The pooled p=.001 is largely cross-tier composition: BS-tier
  bull_puts have both lower mean delta (−0.16 vs +0.13/+0.11) and worse
  mean P&L (−0.21 vs +0.06). Can't currently distinguish "far-OTM
  bull_puts lose" from "BS-priced rows measure worse" — plausibly causal
  either way, since far-OTM illiquid contracts are exactly the ones with
  no Barchart history. Re-read at ≥800 within the real-priced tier only.
- **bull_put `dte_entry` ρ −0.243 p=.010** — same tier caveat: −0.167
  p=.13 on real-priced only. Watch, don't act.
- **score_vol ρ −0.196 p=.015 credit-side** (bull_put-only −0.176 p=.06,
  bear_call-only −0.220 n.s.; robust on the real-priced subset: −0.195
  p=.03, n=120) — third consecutive confirmation of the pre-13c
  self-fulfilling vol-alignment channel; all rows predate the fix.
  Not a new defect. score_catalyst −0.151 p=.06 credit-side is marginal
  and concentrated in vetoed bear_call (−0.255) → ignore.
- iv_skew +0.316 p=.010 credit-side collapses to n=25 p=.12 within
  bull_put — small-n, watch only. bear_call iv_entry_pct −0.334 p=.03 is
  moot (structure vetoed at intake 07-13).

### Structures / groups (pooled; real-only agrees directionally)

- **bull_call is the entire book's P&L engine**: n=181, 58% win, mean
  +0.43, +$90.6k (real-only +0.32, +$30.8k). bear_put is flat despite
  n=176 (mean +0.07, median −0.19, 45% win). bear_call −0.52 mean /
  −$11.9k — veto validated. bull_put mean ≈ 0 with 62% win + fat left
  tail (10th pctile −1.34): the credit stop_loss removal (Attempt 13)
  targets exactly this shape but is unvalidated on this book.
- Regime × side extremes repeat Attempt 12's read: **BEAR+H-VOL debit
  −0.52 (n=21)** and **RANGE+L-VOL credit −0.65 (n=21)** are the two
  worst cells; **RANGE+E-VOL debit +1.19 (n=45)** the best. BULL+L-VOL
  debit — the single biggest cell, n=93 — is dead flat (−0.01). Per-regime
  handling stays the most-supported gated follow-up.
- Horizon: debit 720 mean +0.85 (n=47); credits negative at every horizon.

### Real-priced robustness (correcting the "58% model-priced" framing)

Only the 121 bs_options_hist rows are model-priced; real + tweak = 402
rows (77%) settle on real Barchart history. On that real-priced subset the
structure and regime conclusions hold and mostly sharpen: bull_call mean
+0.51 (+$84.6k of the book), bear_put flat (+0.05, median −0.54),
bear_call −0.58, RANGE+L-VOL credit −0.97 / BEAR+H-VOL debit −0.59 worst
cells, RANGE+E-VOL debit +1.65 best, BULL+L-VOL debit still flat (−0.03,
n=76). The only findings that materially weaken on real-priced rows are
the bull_put delta/DTE reads (above).

### MFE/MAE validation (exit-rule-independent outcomes)

Rationale: realized P&L bakes in the exit rules (still in flux), so the
reads were re-run against mfe_pct (signal quality: did the trade ever go
green) and mae_pct (drawdown depth). Interpretation rule applied
throughout: MFE/MAE scale mechanically with path volatility — DTE,
horizon, delta, iv_entry all shift the % excursion range — so **mirrored
reads (bigger MFE and deeper MAE) are path-vol artifacts; only
asymmetric reads count.** By that rule, discounted as mechanical/vol:
debit dte/horizon/iv_entry vs MAE, credit dte/horizon vs MFE (short-DTE
credits mechanically reach a high % of max profit), score_flow (mirrored
+0.10 MFE / −0.12 MAE = picks volatile paths), score_catalyst (inverse
mirrored — high catalyst score = low-vol path, not a directional edge).

Asymmetric survivors:

- **bull_put delta/DTE UPGRADED back to serious candidate**: real-priced
  bull_puts, delta vs MFE ρ +0.330 p=.002 and dte vs MFE ρ −0.425
  p=.0001, while delta vs MAE is FLAT (−0.07 n.s.) — higher-delta,
  shorter-dated bull_puts get materially more favorable excursion at no
  extra drawdown. Asymmetric ⇒ not path-vol. The weak realized read
  (+0.18 p=.095) now looks like exit-rule noise on top of a real entry
  signal. Still gated on ≥800 (Mar-2025 cluster), but this is the
  leading entry-constraint candidate: min-delta + max-DTE on bull_puts.
- **cpir is the only debit-side feature with an asymmetric favorable
  read**: vs MAE ρ +0.357 p<.0001 (shallower drawdowns) AND vs MFE
  +0.153 p=.06 (more upside), consistent with the earlier real-only
  realized read (+0.155 p=.06). n=148 and effectively real-rows-only
  (cpir coverage) — watch closely at ≥800.
- **score_dealer: deeper drawdowns with NO extra upside** (real-priced
  debit vs MAE ρ −0.218 p=.0002, vs MFE ~0) — strengthens the existing
  drop-candidate case from 07-17.

Exit-capture diagnosis (realized/MFE where MFE>10%, real-priced):
median capture 0.41 debit / 0.68 credit; the 25th percentile is NEGATIVE
both sides — ≥25% of trades that were up >10% at some point still
realized a loss. Cell-level split of "bad signal" vs "bad exit":

- **Genuinely bad signals** (MFE never material): BEAR+H-VOL debit
  median MFE −0.02 — never even goes green; veto/sizing candidate, no
  exit rule can save it.
- **Bad exits on OK signals**: RANGE+H-VOL debit (median MFE +0.42 →
  realized −0.76) and RANGE+L-VOL credit (median MFE +0.87 → realized
  −1.24) — decent favorable excursions fully given back; these two cells
  are where a per-regime exit switch would bite, matching Attempt 12's
  group-level read.
- **bear_put is half-and-half**: its median MFE (+0.68) is genuinely
  below bull_call's (+1.05), AND its MFE peaks at day ~13 while median
  hold is 12 days with capture 0.34 — the excursion dies right around
  exit. If bear_put is kept, faster profit-taking is the lever.

### 07-19 follow-ups: cpir coverage fix, stop-recovery check, FDR pass

- **cpir KILLED as a feature.** The 07-18 asymmetric read was a coverage
  artifact (native-column subset, n=148); at full joined coverage (n=276)
  MFE and realized are null, and the surviving MAE read (+0.284) is pure
  bull_call-vs-bear_put composition — median cpir 0.97 on bull_call vs
  0.11 on bear_put, and within either structure cpir vs MAE is n.s.
  (+0.09/+0.05). Lesson folded into standard practice: rollup features
  must be tested at joined coverage AND within-structure.
- **Replacement read the composition check exposed: bear_put × iv_spread.**
  Within bear_puts (n=117), higher (more bullish) iv_spread → deeper
  drawdowns: MAE ρ −0.308 p=.0007 (survives BH), MFE +0.09 n.s., realized
  n.s. — asymmetric, so not path-vol. Directionally sensible: bearish
  debits entered against call-demand IV spreads ride deeper troughs.
  Candidate use: sizing haircut or entry flag for bear_put when iv_spread
  is strongly positive. Gate on ≥800. (bull_call shows no mirror-image
  effect vs negative spreads.)
- **Stop-recovery check (MFE/MAE span the full path per
  backtest-reference, so post-exit recovery is measurable): debit stops
  are FIRM, credit-stop removal re-validated.** Only 16% (18/114) of
  stopped real-priced debits later exceeded +25% MFE — debit stops are
  not systematically selling bottoms. Credits: 43% (19/44) recovered,
  median to full max-profit (+1.00, day ~40 vs exit day ~8) — the
  Attempt-13 10/10 whipsaw finding confirmed on 4× the sample.
- **BH-FDR pass (96 tests, real-priced within-side, FDR 10%)**: 18
  survivors, but after discounting mechanical path-vol reads
  (delta/horizon/dte/iv_entry vs MAE on debits; dte/horizon vs MFE on
  credits) and composition (credit delta vs realized), the non-mechanical
  survivors are exactly: bull_put delta+DTE vs MFE, score_dealer
  drawdown-without-upside, score_catalyst as a path-vol proxy, bear_put ×
  iv_spread vs MAE, and credit iv_skew vs realized (n=53, collapses
  within bull_put — small-n watch only).

**Decisions**: nothing shipped (early, underpowered, pre-13c book).
**Queue additions for the ≥800 run**: (1) bull_put delta/DTE read —
re-test within the real-priced tier only (MFE-validated 07-18); if it
survives, propose a min-delta (or max-OTM) + max-DTE entry constraint
on bull_puts; (2) unchanged 13c validation + credit-emission share; (3)
BULL+L-VOL debit flatness — the modal trade earns nothing; check whether
score/feature cuts can rescue it or it's a sizing-down candidate; (4)
run all correlation reads with a tier split (real+tweak vs bs_model) as
standard practice — the delta read shows pooling tiers can manufacture
significance; (5) MFE/MAE columns join the standard read (asymmetry
rule above) — score_dealer drawdown-without-upside and bear_put ×
iv_spread MAE are the items to confirm (cpir killed 07-19: coverage +
composition artifact); (6) re-check the RANGE+H debit / RANGE+L credit
capture failures once the per-regime exit switch study unfreezes; (7)
rollup-feature reads must always use full joined coverage AND a
within-structure cut before being believed.

## 2026-07-19 — Deployment ladder: capital-constrained live selection rule (config/deployment-rules.md)

**Question (user)**: the analysis emits ~10 plays/day (median 10, p75 11,
max 13 — stable pre/post-13c); live capital supports 1–3 positions. What
conditions decide which plays get real capital?

**Method**: assembled ONLY ≥2-snapshot-confirmed findings into a
VETO/A/B/C priority ladder, then validated on the 607-row pooled book:
tier tables (pooled + real-priced), time-split stability (halves at
2025-03-17), post-13c subset, and a capped-k-per-day selection replay
with an anti-selection control. Script: scratchpad `deploy_filter.py`
(imports `final_eval.py`).

**The ladder** (full operator doc: `config/deployment-rules.md`):

- **VETO**: bear_call (intake veto, Attempt 13); anything in BEAR+H-VOL
  (n=47, 30% win, −0.34); credit in RANGE+L-VOL (n=20, −0.49).
- **A**: bull_call in RANGE or E-VOL, or score_total ≥ 70.
- **B**: other bull_call; bull_put with |delta| ≥ 0.12 AND DTE ≤ 59
  (PROVISIONAL median splits — the 3×-confirmed delta/DTE read turned
  into cuts; joint cell 88% win +0.41 n=26 vs NEITHER 59% win −0.15
  n=22); other debit with score ≥ 70.
- **C** (skip when constrained): bear_put with iv_spread > 0
  (3×-confirmed MAE penalty), low-delta/long-DTE bull_put, the rest.
- Tie-break within tier: score_total (post-13c rows only — bands
  monotone 70/57/54% win).

**Validation**:

- Tier means monotone everywhere: pooled A +0.51 / B +0.27 / C +0.09 /
  VETO −0.39; real-priced +0.60/+0.30/+0.11/−0.46; ordering holds in
  both time halves (H1 A +0.74 … VETO −0.34; H2 +0.33/+0.38/+0.09/−0.53
  — A≈B in H2, never inverted vs C/VETO).
- Capped replay (score-free tie-break, so pre-13c score contamination
  can't leak in): top-1/day mean +0.82, top-2 +0.51, top-3 +0.45 vs
  take-everything +0.14. **Top-3/day = 172/607 positions (28%) captures
  +$88k of the +$106k book (83%).** Post-13c dates only, score
  tie-break: top-1/day 82% win (n=17).
- **Methodology trap logged**: the first replay tie-broke within tier by
  score_total across the whole book and top-1/2 collapsed to ≈baseline
  (top-1 mean +0.17) — pre-13c scores are inverted, so a score tie-break
  on pre-13c rows anti-selects. Any historical replay that ranks by
  score must restrict the score to post-13c rows (or drop it); the tier
  itself does the work (alpha tie-break already gives +0.82).
- Anti-selection control: bottom-k medians ≈0 vs top-k +0.28…+0.60; the
  bottom-1 MEAN is inflated by HYG/IBIT bear_put tail winners the ladder
  correctly ranked C (path-vol lottery tickets, not a ladder failure).

**Caveats**: Tier A partly re-encodes the RANGE/E-VOL profit cell
(circularity mitigated by the time-split, not eliminated); bull_put
0.12/59 cuts are in-sample median splits pending the ≥800 derivation;
post-13c A (n=23, +0.16) < B (n=58, +0.32) — small-n watch, re-order at
≥800 if it persists.

**Decisions**: `config/deployment-rules.md` written as the operator
checklist (deploy-time triage, no pipeline/schema change — delta/DTE
checked at order entry in IBKR since they aren't on the analysis row).
Nothing else ships. **Queue addition for the ≥800 run**: (8) re-validate
the deployment ladder (tier ordering, bull_put cuts, A-vs-B order) and
only then consider wiring a computed `deploy_tier` column into the
analysis tabs (schema touch points: tab headers + ROW_COLUMNS + backtest
reader).

## 2026-07-20 — Next-25 backtest dates: regime-gap-driven selection (toward the ≥800 gate)

**Question (user)**: need ~200 more backtests; pick 25 new analysis dates
that either differ from, or are least-represented in, the market
conditions of the 70 dates already in AnalysisClaude.

**Method**: pulled the 70 distinct AnalysisClaude dates + their MARKET-row
regime labels, then classified every SPY trading day 2024-06→2026-07-17
(yfinance SPY/^VIX/^VIX3M) into trend (vs 50-SMA + 20d ret) × vol
(L/H + 5d-VIX-change for E/C) buckets and diffed tested vs untested.

**Coverage gaps found**: tested book is heavy BULL+L-VOL (16) and
BEAR spike-aftermath (Aug-24, Mar/Apr-25 post-crash weeks). Thin/absent:
BULL+E-VOL (2), RANGE+E-VOL (2), RANGE+H-VOL (1), BULL+C-VOL (3),
BULL+H-VOL (3), BEAR+L-VOL (3). Zero coverage of: the Apr-2025 crash
CORE (VIX 45–52, VIX/VIX3M 1.23–1.27 deep backwardation — aftermath
tested, panic itself never), the entire Sep–Dec-2024 stretch (Sept
selloff, election, Dec-18 hawkish-FOMC shock ts 1.14), the entire
Jun-2025→Nov-2025 stretch (summer melt-up ts ~0.80, Oct spike, Nov
correction), and the Mar-2026 selloff (VIX to ~31, dd −7% — largest
untested new event).

**The 25 dates** (9× 2024, 12× 2025, 4× 2026, grouped in mini-clusters
so --days 5 persistence context stays cheap to scrape):
Sep-2024 selloff: 09-03, 09-04, 09-06 · Election week: 11-01, 11-04,
11-06, 11-07 · Dec FOMC shock: 12-18, 12-19 · Jan-2025 rate-scare grind
(BEAR+L-VOL): 01-08, 01-10 · Tariff-crash core: 04-03, 04-07, 04-09 ·
V-recovery (BULL+H-VOL): 05-05, 05-06, 05-12 · Summer melt-up: 08-12 ·
Oct spike: 10-16 · Nov-2025 correction: 11-20, 11-24 · Mar-2026
selloff: 03-06, 03-12, 03-20, 03-27.

**Caveats**: bucket labels are mechanical (SMA/VIX thresholds), not the
framework's own regime call — expect some drift when the analysis
labels them; the Apr-2025/Mar-2026 panic days will stress the
arbitrage-clamp + proxy pricing paths (thin quotes, huge IV) — watch
the pricing-tier split when evaluating.

**Progress check 2026-07-21**: 12/25 already analyzed + backtested (and
included in the 07-21 ≥800-gate snapshot — its 80 signal dates vs the 70
this selection diffed against): 09-03/04/06, 12-19, 01-08/10, 04-07/09,
05-06/12, 10-16, 11-24. **13 remain**: election week 11-01/04/06/07,
12-18, 04-03, 05-05, 08-12, 11-20, and the whole Mar-2026 cluster
03-06/12/20/27 — election week and Mar-2026 are the two untouched
clusters, and the queued re-reads stay gated until they land.
