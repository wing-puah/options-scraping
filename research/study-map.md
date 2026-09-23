# Study map — what each file in `scripts/backtest_study/` is trying to prove

> **There is a rendered version of this page**: [`site/study-map.html`](../site/study-map.html).
> Open it in a browser. It carries everything below *plus* what each study's
> last run actually printed, quoted out of `backtests/study_output/`, and the
> newest sections of [`current.md`](current.md). It rebuilds itself after every
> `python -m scripts.backtest_study run …` and every `make study-review`; to
> rebuild by hand, `make study-map` (or `make study-map-open`).
>
> Its per-study verdicts come from `scripts/study_map/catalog.py`, which is the
> file to edit when a verdict changes. A study whose entry is missing there
> fails the test suite. This markdown is the prose companion; keep the two
> saying the same thing.

One page, read top to bottom. `scripts/backtest/` **prices** the book;
`scripts/backtest_study/` **argues** about it. Nothing here is imported by
production, nothing runs on a schedule, and no study writes config. Each
study ends in a plain-text report; that report becomes an addendum in
[`current.md`](current.md), and a human decides whether anything ships.

Each table row below gives, in order: the question the study asks, what it
graded, its standing verdict, and where the fuller record lives — the study
name links to its `study-results/` or `arm-index.md` entry.

The five sections below are the same order the studies sit in on disk:
`f1_selection/` → `f2_management/` → `f3_structure/` → `f4_deployment/` →
`f5_hedging/` ("pick it, manage it, wrap it, fund it, protect it"). The
Infrastructure table at the bottom covers `run.py`, `harness.py`, `book.py`,
`protocol.py`, the `underlying*` and `volume_features` families. It lives in
`lib/`: import-only, and it argues nothing, so it carries no verdict and no
family of its own.

---

## The shape of the whole thing

```
                    ANALYSIS ENGINE  (v3 frozen · v4 live)
                              │  emits plays
                              ▼
        ┌─────────────────────────────────────────────────┐
        │  THE BOOK          book.py                      │
        │  real rows (BacktestResults) + proxy rows        │
        │  (BacktestProxy, strike/expiry tweak only)      │
        │  calibration gate: a row that doesn't replay     │
        │  to its stored outcome does not get in           │
        │                                                  │
        │  n is the ~118 SIGNAL DATES, not the ~1,100 rows │
        └─────────────────────────┬───────────────────────┘
                                  │  every study replays through
                                  ▼
        ┌─────────────────────────────────────────────────┐
        │  harness.py    FROZEN exit-replay engine         │
        │                (DO NOT EDIT — every recorded     │
        │                 conclusion rests on it)          │
        │  protocol.py   purged walk-forward · date-       │
        │                clustered CIs · LOO · window cuts │
        │  underlying*.py stock bars + as-of-entry price   │
        │                 features (no look-ahead)         │
        └─────────────────────────┬───────────────────────┘
                                  │
  ┌─────────────┬───────────────┬────────┴──────┬──────────────┬─────────────┐
  ▼             ▼               ▼               ▼              ▼
① SELECTION  ② MANAGEMENT   ③ STRUCTURE   ④ DEPLOYMENT   ⑤ HEDGING
what to      when to get    what wrapper  can I run it   what protects
trade        out                                         the book
  │             │               │               │              │
mostly NULL  where the edge  two diagonal  $25k account   bear is a
0/496        actually lives  candidates,   NOT FEASIBLE   hedge, not a
subsets      (2 rules        neither       — drawdown,    selection —
0/15 ML      shipped)        confirmed     not cash       the rest is
cells                                                     blocked
  │             │               │               │              │
  └─────────────┴───────────────┴───────┬───────┴──────────────┘
                                        ▼
                    docs/deployment-rules.md
                    the operator card — top 3/day, tiers A/B
```

**The one-sentence result of the whole programme:** selection is not tunable
from the columns we have; the money is in the exit rules and in position
management. Every selection study returns a null; two exit studies shipped.

Every label below carries a type — arm, sub-arm, cell, control, descriptive
cut, population scope, run, gate, criterion, hypothesis, or prose. The full
list is [object types](arm-index.md#object-types). Each study's row links to
its `arm-index.md` section, where every label carries its type in
parentheses after the label.

---

<a id="selection"></a>
## ① SELECTION — "which plays are worth taking?"

| File | The question | Graded | Verdict |
|---|---|---|---|
| [`regime_gap_reread.py`](study-results/f1_selection/regime_gap_reread.md) | Numbers only, no interpretation: build the pooled book and print the report. | see index | Baseline snapshot, no verdict line by design. The 2026-09-19 carry-forward is [§5d](../docs/deployment-rules.md#s5)'s Tier-C continuity check, `iv_spread vs mae_pct \| bear_put_spread, pooled          n=  446  rho=-0.0774  p= 0.1027`, against v3's −0.215 on n=380 — non-replication at larger n. |
| [`mech_regime_recut.py`](study-results/f1_selection/mech_regime_recut.md) | Does a *deterministic* regime label beat the model's free-text regime? | see index | Overlay adopted: [`mech_cell`](glossary.md#mech_cell) is a column and keys the shipped BEAR_HE exit. The OR-veto extension stays rejected on 2026-09-19 — `VERDICT RULE: OR-VETO REJECTED (newly-vetoed subset net-positive)` — the newly-cut rows being net positive at `n=  127  mean=  0.0170`. |
| [`bear_position_study.py`](study-results/f1_selection/bear_position_study.md) | Pre-registered cuts on `bear_put`: a **selection** problem ([E](glossary.md#e)<0) or an **exit** problem (E>0, [R](glossary.md#r)<0)? | see index | DEMOTE criteria all fire at n=438 on 2026-09-19: `[PASS]  ex-window mean E < 0            (-0.256)`, [CI](glossary.md#ci) `[-0.369, -0.135]`, halves `early -0.285, late -0.220`. They are on **E**, the exit-free number; on **R** the same rows do not separate. |
| [`bear_arm.py`](arm-index.md#bear_arm) | B1 — is there *any* bear subset defined at decision time that isn't negative? B2 — is the exit just mis-tuned? | 2 criteria | **B1 NO**: 0 survivors of 496 subsets. B2's one clear is withdrawn — `pre-registered EXIT FIX criteria (CI excludes zero AND every LOO fold positive): NOT met` on 2026-09-19. The `be_after 0.50` rollback census fires on all three clauses now; the stop was reverted 2026-08-24. |
| [`ml_combination.py`](arm-index.md#ml_combination) | Does any learned combination (structure × regime × geometry × enrichment) beat the score-free ladder out of sample? | 3 arms, 3 controls | **NULL** — `VERDICT: NULL RESULT — the ladder is at/near the ceiling of this data`. On 2026-09-19 the headline construct reads `M3 out-of-fold paired R gain vs B0: -0.063 CI95 [-0.168, +0.042]` and every learned construct is negative. Re-open on new **columns**, never new models. |
| [`v4_bridge.py`](study-results/f1_selection/v4_bridge.md) | v4 dropped two prompt factors. Does the v3-derived ladder still apply to what v4 *emits*? | see index | **LADDER UNVALIDATED ON v4**, unchanged. On 2026-09-19 four of five pre-registered tests shift — `Shifted: 1. structure mix, 3. plays per day, 4. bear share, 5. ladder tier mix`. Credit share came back inside noise at `two-proportion z = -1.78, p = 0.0743`. Keep deploying under the v3 rules. |
| [`text_features.py`](arm-index.md#text_features) | Does the model's own prose — invalidation, trigger, specificity, thesis shape, blind-labelled type and confidence, citation faithfulness — separate outcome within structure × tier, or gate the shipped ladder? | 3 arms | **Every feature NULL or UNDERPOWERED in all three arms**, on every run since 2026-09-02: `PROMPT-ROBUSTNESS FINDINGS ... none`, `ENTRY-GATE CANDIDATES ... none`. On 2026-09-19 label coverage fell again, to `ARM B label coverage: 992/1325 priced rows (74.9%)`, so no ARM B line is quotable here. |
| [`prompt_eval.py`](arm-index.md#prompt_eval) | The loop step: does a CANDIDATE prompt beat the shipped one on the same dates under the shipped ladder (paired ΔR, PF, hallucination rate, zero bear_call leaks), with accumulated live dates as the primary evidence? | 2 arms | **No candidate has been scored yet** — scoring needs a committed candidate directory, so there is nothing to verdict. The harness was built 2026-09-02; date sets are declared by rule; the PROD noise floor is the first scored step. MET, when it happens, is a v5-bump proposal, never a ship. It is a tool driven by subcommands, so `run --all` skips it (`BULK_RUN = False`, 2026-09-17); any `-latest.txt` on disk is an older bare invocation's argparse refusal, not a result. The scored run of record is the PROD variance floor. |
| [`macro_event_study.py`](arm-index.md#macro_event_study) | Do scheduled macro events — FOMC, minutes, CPI, NFP, PCE — show up in the book: in entry IV, in outcomes, or in exits? | 5 arms, 4 hypotheses | `macro_event_exit` stays **DE-QUEUED**. On 2026-09-19 the ARM X raw trigger no longer fires, and the survival control still reads `X-C1 verdict (203 affected dates vs floor 25): SURVIVAL-ARTIFACT`. It is no longer a one-powered-cell study; three reads are newly starred and none is a criterion. |
| [`trigger_entry.py`](arm-index.md#trigger_entry) | Production enters every non-vetoed play at the next open and ignores the stated trigger. Does entering only when that trigger is first crossed beat it, once the entry price pays for the confirmation? | 2 arms, 2 controls | **`tally: {'LATE-ENTRY': 3}`** on 2026-09-19 — the N=1 cell that read NULL is LATE-ENTRY too, and the grid no longer flips sign. The trigger picks a better book and the confirmation costs more than it is worth; `ARM T  N=5` excludes zero at `[-0.0800, -0.0033]`. |
| [`emission_timing.py`](arm-index.md#emission_timing) | Same signal, later entry: do repeat emissions of a persisting (ticker, structure) underperform first emissions, and does a fill delayed 1–3 sessions decay the edge? | 2 arms | **ARM P NULL / ARM L LAG-TOLERANT**, both unchanged on 2026-09-19 — but the report prints **two** `** CANDIDATE` cells where 09-04 printed one. The new one is ARM P's `ohlc: repeats that moved AGAINST the play`, which passes the year criterion it used to fail. |

<a id="management"></a>
## ② MANAGEMENT — "when do I get out?" ← where the edge is

| File | The question | Graded | Verdict |
|---|---|---|---|
| [`exit_mechanism_study.py`](study-results/f2_management/exit_mechanism_study.md) | The original grid: replay stored daily marks under alternative exit rules, real rows only. | see index | **SHIPPED** the production debit profile — pt 0.90 / sl 0.75 / tef 0.75, no trail (Attempt 10). The 2026-09-19 run is its cleanest result yet: **every** grid cell loses to it, in sample and out. `PROD pt.90 sl.75 no-trail tef.75             total=$   +41934`. |
| `combined_exit_study.py` — **DELETED** | Same grid, bigger tuning set (real + proxy-priced rows pooled). | deleted | **RETIRED 2026-08-14, module DELETED 2026-09-05.** Its inputs (`backtests/results_proxy.csv`, an author transposition that never matched `config/backtest.yml`'s actual `proxy_results.csv` name) were gitignored scratch, deleted and unrecoverable, so it could not be re-run. **This row is now the record.** Verdict, reached while its inputs existed and unchanged by the deletion: **NOTHING SHIPPED** — a `reference` study, it confirmed the exit profile ALREADY in production was the best *global* config, so there was nothing to change. Its one consequence was a follow-up question: the same run showed exits are regime-conditional, which is what motivated the two switch studies below (the BEAR_HE trail shipped from those, not from this). Full trail: [archive/02](archive/02-credit-debit-split-attempts-8-12.md) (Attempts 8, 9, 12). Nothing re-opens this. |
| `underlying_exit_study.py` — **DELETED** | Credit spreads: stop on the **underlying** breaching a level instead of on the mark? | deleted | **RETIRED 2026-08-14, module DELETED 2026-09-05.** Its second input (`backtests/v2_BacktestResults_nocreditdiff.csv`) was gitignored scratch, deleted and unrecoverable; the genuine rename `v2_results_nocreditdiff.csv` survives but holds 0 credit rows, so re-pointing would only emit an empty report. **This row is now the record.** Verdict, unchanged by the deletion: **NOTHING SHIPPED** — a `null`. Stopping on the underlying did not beat stopping on the mark (❌ Attempt 9). Full trail: [archive/02](archive/02-credit-debit-split-attempts-8-12.md). Nothing re-opens this. |
| [`exit_switch_mech_study.py`](study-results/f2_management/exit_switch_mech_study.md) | Per-regime exit switch keyed on the mechanical regime — stable where the model-keyed version failed [LOO](glossary.md#loo)? | see index | **BEAR_HE cell SHIPPED** (trail 0.50 / trigger 0.50). On 2026-09-19 both verdicts STAY GATED. BEAR_HE's census is still unread at `n_rows=8  n_dates=8  floor=25 dates`; LVOL now fails one corrected criterion rather than two, the median. Three exports, three answers on LVOL. |
| [`exit_switch_structure_study.py`](study-results/f2_management/exit_switch_structure_study.md) | Q1: does a bear_put-keyed trail pass the same ship gate? Q2: is BEAR_HE secretly a *composition proxy* for that structure effect? | see index | Q1 `STAYS GATED` on 2026-09-19, now failing four of six. Q2 inverted again, and this time it reports on the shipped key: `shipped BEAR_HE clause  Δ=-4.5205   on its complement (non-bear_put) Δ=-2.1440   retained 47%`. An observation, not a rollback trigger — see [Operator reading](#operator-reading-2026-09-20). |
| [`bear_giveback.py`](arm-index.md#bear_giveback) | 82% of bear rows go green then give it back. Can a peak-triggered breakeven stop capture it, and does the underlying path explain it? | 3 arms | The `be_after` grid does **not** ship, and what stops it changed: on 2026-09-19 every interval straddles zero. The per-year cut no longer kills the leaders — every stacked variant is positive in all three years. |
| [`next_day_move.py`](arm-index.md#next_day_move) | Move the give-back question to day 0 (knowable at the close): cut positions the stock didn't confirm? | 1 arm, 1 control, 1 descriptive cut | One bear-keyed cut has its marker back and it still makes no rule. `cut when worse than -0.5 sigma          -0.039   +0.041        [+0.002, +0.082]   +0.033      -17,276   108  **` clears all six criteria on 2026-09-19, but the gain is bear-only — [`bear_position_study`](study-results/f1_selection/bear_position_study.md)'s veto through a second door. |
| [`volume_signal.py`](study-results/f2_management/volume_signal.md) | Share volume — the one column on disk no study had read. Does unusual-O/S condition exits, or anything? | see index | **NULL** — `VERDICT: PATH-VOL-PROXY — MFE and MAE move together with no R separation.`, unchanged on 2026-09-19 at `r_sep=+0.0025`. Two older readings are gone: the 2026 row is no longer a structural zero, and bear's os_ratio terciles are no longer monotone. Column closed. |
| [`exit_from_text.py`](arm-index.md#exit_from_text) | Do the model's own invalidation level (E1, underlying-close stop), trigger condition (E2, an intake filter) and emitted horizon (E3, time exit) beat the shipped mechanical exits? | 3 arms | **A CANDIDATE for the first time**: `E2  MECH   LVOL                                  N=3               CANDIDATE`, all seven criteria true, on 2026-09-19. E2 is intake, so its ceiling is a proposal behind an independent window. E1 is CONTRARY in 11 cells; E3 fails its survival control. |
| [`staged_exit.py`](arm-index.md#staged_exit) | Evaluate ONCE at a fixed session X on P&L vs the ORIGINAL entry — exit, tighten the stop, or arm a trail. | 2 arms | **NULL in substance on both arms.** On 2026-09-19, `54 of 96 cells clear the floor; 42 are UNDERPOWERED.` and not one powered cell reaches CANDIDATE. Eight cells now have an interval excluding zero and all eight are harmful, so the scheduled switch has a measured cost. |
| [`exit_drawdown.py`](arm-index.md#exit_drawdown) | Does any exit rule — chosen WITHOUT look-ahead, on TRAIN dates only — reduce the account-level mark-to-market drawdown of the deployed [`account_sim`](arm-index.md#account_sim) book without giving back its edge? Five arms: W, U, O, P and a SECONDARY sizing throttle D. | 5 arms | **Every PRIMARY cell UNDERPOWERED**, unchanged: `tally: {'UNDERPOWERED': 7, 'SECONDARY-UNDERPOWERED': 1}`, `PROD-ROBUST` not claimed. The purged walk-forward leaves too few out-of-sample dates behind the burn-in. On the disclosed `all` cut a third cell clears power and is NULL. |

<a id="structure"></a>
## ③ STRUCTURE — "am I expressing the signal in the wrong wrapper?"

| File | The question | Graded | Verdict |
|---|---|---|---|
| [`bear_rewrap.py`](arm-index.md#bear_rewrap) | A bear *spread* sells the lower put, giving away the vol expansion that makes a bear position pay. Drop the short leg? | 2 arms | The naive re-wraps stay 0 of 5. The **diagonal** is 4 of 5 and keeps losing the year: `[FAIL] sign-stable every year    2024 +0.220  2025 +0.153  2026 -0.069` against `dR +0.159 CI [+0.035, +0.288]`. Its portfolio checks have since reversed, so neither a ship nor a refutation. |
| [`financed_spread.py`](arm-index.md#financed_spread) | Does wrapping a book debit vertical in a financing credit improve outcomes without re-wrapping the same exposure? | 5 cells | The **RE-WRAP** token has moved cell: `F4-d20 $100      RE-WRAP` on 2026-09-19, where `F3 off1` held it on 09-04 and now reads NULL. It clears six of seven, failing `[FAIL] 7 E3 <= 0 (does not re-wrap the sleeve)  corr +0.180 over 83 shared dates` — a real gain that is the same exposure again. |
| [`ladder_overlay.py`](arm-index.md#ladder_overlay) | Does selling a shorter-dated short call against a long-dated bull call spread — rolling it as each expires — beat running the spread to the shipped [§5](../docs/deployment-rules.md#s5) exits, and would a naked put beat both? | 17 cells, 9 gates | **NULL** on both eras, closed 2026-09-16 and unchanged by the 2026-09-19 re-run. Selling the call at entry loses with the interval clear of zero; the trigger cells are positive inside their intervals and re-wrap the deployed exposure. |

<a id="deployment"></a>
## ④ DEPLOYMENT — "can I actually run this?"

| File | The question | Graded | Verdict |
|---|---|---|---|
| [`account_sim.py`](arm-index.md#account_sim) | The ladder assumes infinite capital. Does a real **$25,000** account — paying for positions, holding reserve, respecting a delta cap — still produce a book? | 3 arms, 2 cells | **The verdict MOVED on 2026-09-19**: `>>> NOT FEASIBLE AT $25,000 — BLOWUP RISK (A1 holds, A3 fails) <<<`, where 09-04 printed FEASIBLE. The edge survives the caps and the drawdown does not — `A3 NO BLOWUP      maxDD $-8,755 = 35.0% of capital;  ledger violations 0` against a 25% bar. |
| [`selection_order.py`](arm-index.md#selection_order) | Does a different **blind entry-side order** of the same candidate set spend the scarce delta budget better — or was `account_sim`'s adverse-ordering read an artifact? | 6 arms | **ORDERING-IS-NOISE**, unchanged on 2026-09-19 — thread CLOSED. All four arms clear G0 more comfortably (48 / 41 / 46 / 49 affected dates against a floor of 25) and none clears the bar: every arm sits inside the O4 random-order band. |
| [`concurrency_correlation.py`](arm-index.md#concurrency_correlation) | `max_positions_per_day` caps the FLOW of new positions; nothing caps the **STOCK** of open ones. Does the size and internal similarity of the open book degrade per-position outcome? | 4 arms, 8 criteria, 1 descriptive cut | **The NOISE banner is gone**: 2026-09-19 prints `>>> RESTATEMENT — K 5 / same-direction-and-sector clears X2 and X3 but loses the gain under the delta control (X7). It is a restatement of portfolio_delta's ARM B / ARM D and does not ship. <<<`. The X4 era settlement is withdrawn with it. |
| [`portfolio_delta.py`](arm-index.md#portfolio_delta) | Is the book's net delta LEVEL a lever? Dose-response by exposure band, a ceiling-band admission, and a delta-targeted hedge sleeve, against a seeded random-admission null band. | 4 arms | **The candidate is gone.** On 2026-09-19 the label moved to `>>> NOISE — no arm exceeds ARM N's 95th percentile and ARM D's bands do not separate within their cells. Recorded; thread closed for these dates. <<<`. `B ceiling 1.00` lost criterion 1 alone, halving to `+0.0519 R   CI95 [-0.0333, +0.1407]`. |

<a id="hedging"></a>
## ⑤ HEDGING — "what protects the book when the ladder is wrong?"

Three modules were renamed 2026-09-08 after the question each answers: `bear_deploy` → `hedge_sizing`, `calendar_hedge` → `hedge_structure`, `hedge_exposure` → `hedge_portfolio` (table in [`f5_hedging/README.md`](../scripts/backtest_study/f5_hedging/README.md)). Labels and figures are unchanged.

| File | The question | Graded | Verdict |
|---|---|---|---|
| [`hedge_sizing.py`](arm-index.md#hedge_sizing) | Bear selection is unfixable — but is bear worth holding as a **hedge**? Four estimands: D1 joint selection×exit, D2 hedge contribution, D3 sizing, D4 conditional pick. | 5 criteria | The hedge case stays NOT MET and **D1 moved**, to `D1 joint selection x exit : candidate(s) found — 4` against `~11.8 expected by chance`. D2 now fails on the worst-decile clause instead of the year one. The [§4](../docs/deployment-rules.md#s4) pick line stays **PULLED**. |
| `hedge_structure.py` | Re-derive that one survivor under a pre-registered pick rule and a strict fill rule. | 2 arms, 7 criteria | Gates pass, the primary stays unreadable, the **fill rate** binds: `P1 fillable on deployed dates          58 / 174  =  33.3%   FAIL` on 2026-09-19, against a 60% gate. `H0 FILL           NOT MET` and `H2 (primary)      NOT EVALUABLE`. H3 has answered differently on four consecutive exports, so carry none of the four. |
| [`hedge_timing.py`](arm-index.md#hedge_timing) | The bear hedge sleeve is deployed on discretionary triggers — chop, a SPY gap-up, a 4–5-day SPY down-run. Does any of them, made mechanical, pick a day the hedge beats the **same day's** ladder-eligible long? | 5 arms | `TIMING-CANDIDATE survivors: 0`, unchanged. The [§4](../docs/deployment-rules.md#s4) gap-up prohibition now rests on **H3-GAP alone** at `HEADLINE difference -0.510  CI95 [-0.820, -0.190]`: H1-GAP went back to NULL because the beta control H2-GAP absorbed it. |
| [`hedge_portfolio.py`](arm-index.md#hedge_portfolio) | When the open book is **concentrated** in one correlated cluster, does a long put on that cluster's proxy cut the book's **mark-to-market** drawdown, versus carrying the same book unhedged? | 8 arms | **UNDERPOWERED** on the mechanism and **MEASUREMENT-ONLY** on ARM M, both unchanged on 2026-09-19 at `1325 rows / 207 signal dates`. ARM M's gap shrank: `the close-bucketed curve UNDERSTATES this book's max drawdown by 27.0%.`, against 40.2% on 09-04. |
| `hedge_concentration.py` — **DELETED** | On the **admitted** book — the positions `account_sim` actually takes under the operator's top-3-per-day rule and exposure caps — does a session's cluster **concentration predict** the book's subsequent mark-to-market drawdown, and only then does a proxy put on that cluster cut it? | 8 arms | **MERGED 2026-09-07, module DELETED 2026-09-07.** It was the same question as [`hedge_portfolio`](arm-index.md#hedge_portfolio) at a second scope — the ADMITTED book rather than the whole one — and it already imported 32 symbols from that module, including its whole pricing and evaluation stack. It is now that module's `--admitted` ARM: run it with `python -m scripts.backtest_study run hedge_portfolio -- --admitted`, or let a bare `run hedge_portfolio` run both arms, and it files its report as `hedge_portfolio-admitted`. Merged means deleted here: the module is gone rather than kept as a second copy. Nothing it prints changed — the merged arm's report body reconciles BYTE-IDENTICAL to this module's last run, and its registration (pre-registration (deleted 2026-09-08, held in git at `44bbfb2`)) is immutable and untouched, so every gate, arm and verdict word still prints under its registered label. **This row is now the record**, beside the frozen per-era print in study-results/f5_hedging/hedge_concentration.md (deleted 2026-09-08, held in git at `44bbfb2`) and the arm labels at [arm-index.md#hedge_concentration](arm-index.md#hedge_concentration). Verdict, unchanged by the merge: RUN 2026-09-04 (era v4, sha e59356f), re-run of the 08-31 first pass on the refreshed export and unchanged in verdict: `VERDICT — Stage 1 (ARM K, the precondition): PRECONDITION-NULL` and `VERDICT — Stage 2 (ARM C, the mechanism): NOT RUN (Stage 1 PRECONDITION-NULL)`. This is a POWERED null, not an underpowered one — `usable sessions per concentration tercile   [216, 215, 195]   floor 60 EACH   PASS` / `dense episodes of admitted signal dates     3   floor 3   PASS` / `G-POWER-K: PASS` — which is what the two-stage design was for: `hedge_portfolio` could not power a single hedge cell, and Stage 1 does not depend on triggers at all. The precondition every prior hedge verdict assumed is ABSENT on the book the operator runs, and on this export the point estimate is not merely inside the band but AT zero: `1 contrast negative, block-bootstrap CI excludes 0   FAIL   contrast $-173.65  CI95 [$-1,205.66, $893.81]` and `2 Spearman rho negative, CI excludes 0              FAIL   rho +0.0000  CI95 [-0.2198, +0.2231]`, with the contrast well inside the circular-shift null (`contrast       point -173.6548   null p05 -635.5211   p95 +648.0933   min shift 20 rows   beats p05 (more negative): no`). Four of six clauses fail (1, 2, 3, 5); the two that PASS are the CONTROLS — `4 not a gross effect: sign kept in >= 2 of 3          PASS   2 of 3` and `6 sign kept under BOTH ex-window cuts               PASS   2 of 2` — so it is not a gross-exposure effect in disguise either, it is no effect. The second of those controls is real for the first time: `ex_2026_feb_apr    rows  584  usable  564  contrast       $-164.28   sign kept` is now a genuine cut rather than the no-op it was on a book that ended in 2025. Population and admission, every count from this run: `candidate rows (ratified population)          1143   / 166 signal dates` -> `ladder-eligible rows (tier A/B)                513   / 147 dates` -> `ADMITTED (taken + taken_downsized)             260   / 129 dates   2024-01-10 .. 2026-04-16`, skipped per_pos_delta 101 · net_delta 84 · day3_cap 68, `partition check: admitted 260 + skipped 253 = 513  vs ladder-eligible candidates 513   -> EXACT`. G-ADMIT PASS, G-MTM PASS on TARGET_POSITION (`positions 260   reconciled 260   tolerance $0.01 per contract   worst mismatch $0.0000`) with the stored-target reconciliation printed beside it as a disclosure, G-BLIND PASS. ARM M is a measurement and never a verdict here, and it grew with the book: `THE GAP, printed rather than asserted: maxDD $-5,318 (59.6% of the realized-on-close drawdown)   ulcer +3.71 pts   TUW +11.4 pts` on the admitted book — the same direction hedge_portfolio found on the every-row book. Stage 2 was NOT run and no cell was evaluated; its census is on the record (episodes peak at 18 against a floor of 25), as the registration predicted. SHIP-CRITERIA BRANCH, quoted: `record in research/deployment-evidence.md as closing the queued max-drawdown question for concentration-gated hedging; next-steps.md §2.1 closed`. Nothing ships. This does not overturn hedge_portfolio — that study's UNDERPOWERED describes the every-row book — and it is not evidence about concurrency_correlation's clustering ceiling in either direction. |
| `vol_sleeve.py` — **DELETED** | Synthesize straddle / strangle / calendar on the dates the engine already signalled. Is there a vol sleeve in here? | deleted | **RETIRED 2026-09-07, module DELETED 2026-09-07.** It was retired into [`hedge_structure`](arm-index.md#hedge_structure), which already rebuilds its calendar cell in-process under gate `R4` and compares the two row for row, so the study had nothing left to print that `hedge_structure` does not build itself. Retired means deleted here: the module is gone rather than kept unrunnable. Its synthesis layer survives as `scripts/backtest_study/lib/sleeve_synth.py`, byte-identical, because `R4` runs it as the second side of that comparison. **This row is now the record**, beside the frozen per-era print in study-results/f5_hedging/vol_sleeve.md (deleted 2026-09-08, held in git at `44bbfb2`) and the immutable pre-registration (deleted 2026-09-08, held in git at `44bbfb2`). Verdict, unchanged by the deletion: CLOSED — that word is this catalog's label for the argument, not a token the study prints. What the run prints is `Q1 non-null: True   Q2 non-null: False` and `Q2 IS NULL — the sleeve is neither reliably anti-correlated with the deployed book nor reliably positive on its worst dates.`, unchanged on the 2026-09-04 re-run (sha e59356f, run 21:45; the book's new year is `2026  n=   61  dates=  11`). The sign check is still the whole argument, same signs and all three weaker: straddle `corr(daily mean R)   +0.220   CI95 [+0.063, +0.384]` and strangle `+0.187   CI95 [+0.036, +0.354]` against calendar `-0.211   CI95 [-0.384, -0.026]` — the straddle and strangle re-wrap the same exposure, the calendar does not. WHICH cells clear Q1 moved with the new rows: `Q1 NON-NULL cells: straddle/>90, strangle/>90, calendar/ALL, calendar/>90` where 08-24 read straddle/ALL, straddle/>90, calendar/ALL — the ALL-tenor straddle dropped out and the >90 strangle joined, which is composition rather than a finding, and Q2 fails either way. The calendar remains the one survivor and reads stronger than before on the numbers the study prints POST-HOC rather than as a gate: `calendar                       n= 133  win   57%  PF  1.39  meanR +0.303  $    17,583` and `calendar   ex_BOTH_windows    n= 123  E +0.337  CI [+0.111, +0.637]`. The two structures split hard on the new year (straddle `2026:-0.31`, calendar `2026:+0.67`, on 61 rows over 11 dates — too thin to lean on). Those worst-decile numbers go on to hedge_structure, which is where the fill rule bites. Nothing re-opens this; the calendar's remaining question is `hedge_structure`'s. |

---

<a id="operator-reading-2026-09-20"></a>
## Operator reading (2026-09-20)

Three things the 2026-09-19 suite run put in front of the operator. None of
them changes a rule by itself; each is a decision.

| What moved | Where it sits | What it asks for |
|---|---|---|
| `account_sim` prints NOT FEASIBLE AT $25,000 | the drawdown bar, not the edge | a capital or sizing decision |
| The shipped BEAR_HE clause reads negative in `exit_switch_structure_study` Q2 | an observation, not a registered trigger | whether to re-read [§5](../docs/deployment-rules.md#s5) |
| `exit_from_text` printed its first CANDIDATE | an intake proposal, never an exit rule | an independent window before anything |

The registered rollback trigger for the shipped trail is
[`exit_switch_mech_study`](study-results/f2_management/exit_switch_mech_study.md)'s
BEAR_HE census, and it is still UNDERPOWERED at 8 affected dates against 25. So
nothing fired. The Q2 line above is the guard study reporting on the shipped key
rather than on the candidate it was built to block, which is new and is worth a
look before the next deploy.

<a id="infrastructure"></a>
## Infrastructure (not studies — `run.py` lists these in `INFRA`)

| File | Role |
|---|---|
| `run.py` | The runner. Writes `backtests/study_output/<name>-latest.txt` with a provenance header (git sha, dirty flag, exact argv, input row counts + mtimes) so no write-up can attribute numbers to the wrong export. |
| `harness.py` | **FROZEN** `Trade`/`replay`. Prices nothing — it replays a stored mark series. Every recorded conclusion depends on its exact clamps and rounding. Changing the exit mechanism means *copying* this file, never editing it. |
| `book.py` | Pooled real + proxy loader. `bs_options_hist` rows are excluded by default — they're priced *from* the model that scores them. |
| `protocol.py` | The four things every conclusion rests on: date clustering, purging + embargo, same-dates comparison, window dominance re-cuts. Plus the profit-factor helpers (`pf`, `pf_ci_by_date`, `pf_paired_by_date`) — never printed without mean R beside them. |
| `text_corpus.py` | The model's own prose (thesis, Alt, signal items, trigger, invalidation) joined to every priced row through `book.py`'s join, parsed back into the writer's fields, and reduced to the regex features with no numeric twin already tested null. Also returns the *unpriced* analysis rows by reason and a citation check against the raw flow feed. Built for `text_features`, `exit_from_text`, `prompt_eval`. |
| `underlying.py` | Daily stock bars — real OHLC, falling back to close-only `Price~`. The widening `harness.py` is frozen out of. |
| `underlying_features.py` | As-of-entry price-*state* columns (rv20, Parkinson, semivar, ATR%, efficiency ratio, VRP, beta). This family is the ML re-open — none of it existed when B1 searched 496 subsets. |
| `volume_features.py` | As-of-entry *volume* columns (unusual-O/S, relative-volume z, Amihud), split-guarded, rescaled tickers withheld from the window features. Built for `volume_signal` (NULL), kept for future pre-registered use. |
| `macro_calendar.py` | Scheduled macro events (FOMC, minutes, CPI, NFP, PCE) as as-of features, read from the hand-authored `config/macro-events.yml`. `next_event` is strictly-after and refuses past each type's `verified_through`; unscheduled events excluded from forward reads only. Built for `macro_event_study`. |
| `greeks.py` | Per-leg greeks from the option-history cache at a given day, signed and qty-scaled; net sums are all-or-nothing per greek (a missing leg makes the greek `None`, never 0). Built for `financed_spread`'s exposure reads and `portfolio_delta`'s G-DELTA cross-check. |

---

## How to read any one report

1. **Check the header.** Row counts and mtimes of the input exports. Two runs on different exports are not comparable. That has caused a wrong attribution before.
2. **Check the calibration gate.** Most studies open by proving production rules reproduce the stored `exit_reason` / `days_held` / `realized_pnl_pct`. A non-zero exit here is the gate *working*. Do not route around it.
3. **Check the pre-registration.** Nearly every study names a `current.md` section written *before* it ran. If a number isn't covered by a pre-registered criterion, it's an observation, not a result.
4. **Metric definitions** live in [`glossary.md`](glossary.md). `E` = P&L at path cap (selection only). `R` = realized under the exit rules (selection + exit). `E<0` means no exit rule can rescue it.

## Recurring traps this log has actually fallen into

- **Composition, not signal.** A cut looks predictive because it changed the *mix* of structures, not because the variable matters. Killed `oi_confirm_pct`, `iv_pct`, and the `score_total` bands.
- **Grading against a baseline production doesn't run.** Changed a decision twice. Always compare against the *shipped merge*, not against a clean default.
- **One window carrying an effect.** Every headline is re-cut ex-Mar–Apr-2025 and ex-Feb–Apr-2026.
- **Row count ≠ sample size.** Rows inside a signal date share the tape. `n` is ~118.
