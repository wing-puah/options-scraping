## text_features — does the model's own TEXT separate outcome within structure × tier?

<!-- outcome:start -->
> Latest outcome: `ARM A` `invalidation_level` and `trigger_level` `CANDIDATE`, each in `bear_put_spread`/C (T3 vs T1) and listed under PROMPT-ROBUSTNESS FINDINGS; ENTRY-GATE CANDIDATES none; the other 26 verdict lines 17 `NULL` and 9 `UNDERPOWERED` — 2026-09-28 · [record](../../../study-results/f1_selection/signal/text_features.md).
<!-- outcome:end -->

_Registered 2026-09-02._

## The question

The prompt emits about 10 plays a day. Most of their content is TEXT (`regime`, `signal`, `play`/thesis, `trigger`, `invalidation`). None of it was ever measured. This study asks two questions.

1. **Separation.** Does any deterministic text feature, or any blind taxonomy label, separate mean R WITHIN structure × tier?
2. **Gate value.** Used as a VETO or a tier demotion, does any such feature raise mean R and profit factor under a `top_k_per_day(k=3)` replay against the shipped `ladder_rank`?

Every feature is observable at entry. The text fields are a NEW COLUMN FAMILY: they sit in the analysis export, are never joined to the priced book, and have no numeric counterpart in the closed sweep. Two sub-families qualify: **deterministic text features** (regex only) and **blind taxonomy labels** (a cheap headless model shown ONLY the text fields, never an outcome).

The 2026-08-11 clause fixes HOW a new column is tested: **within structure from the first look**. Three columns once looked predictive pooled and vanished within structure. Every arm here is within structure and within tier.

## What this study is not

- **It is not a new scorer.** It does not re-open the ML/selection search. No arm builds a composite, weights features or fits anything. Each feature is read alone. That search closed 2026-08-11 `NULL` across 15 cells. It re-opens on **new COLUMNS only, never new models.**
- **It does not re-test any numeric column.** `score_total`, `score_flow`, `score_catalyst`, `cpir`, `oi_confirm`, `iv_pct` and `days_to_earnings` are closed. Features that restate one of them are EXCLUDED by name below.
- **It is not an exit study.** Shipped profiles are used throughout, replayed by the FROZEN `harness.replay`. Exit questions from the same text belong to `exit_from_text` (f2).
- **It cannot tell you** whether text works as a composite score, because no arm combines features. It says nothing about exits. It reads nothing pooled across structure: `thesis_len` and `alt_ratio` are never read pooled. It cannot show that a label is free of recall. Nothing from v3 stands on its own.
- Nothing here reaches `docs/deployment-rules.md` without an operator decision.

## Population and basis, fixed here

| Fixed | Value |
|---|---|
| PRIMARY era | `current` (v4). The v4 text IS current-prompt behaviour and is what `prompt_eval` will modify |
| SECONDARY era | `--era v3`, identical thresholds, reported separately, **never pooled**, carries nothing |
| Book | `load_book(include_bs=False)`: **real + strike_expiry_tweak only**. bs rows are excluded (the 2026-08-11 defect). On v4 the exclusion is a NO-OP, because the v4 proxy export carries ZERO `bs_options_hist` rows (measured 2026-09-02). It still binds on v3 and stays in force |
| Priceability | **Every text-feature claim on priced rows is conditioned on ~52% priceability.** The report says so on every table |
| Unpriced share | The unpriced share BY FEATURE is reported. It asks whether vaguer text co-occurs with unpriceable plays. It is a PROMPT-ROBUSTNESS read in its own right. It is the only place an unpriced row carries a number. No criterion is evaluated on unpriced rows |
| Missing values | A row missing a feature, or with no cached markdown for its date, is NOT EVALUABLE on it. It is never imputed. Coverage prints |

**The v4 2026 no-op, stated up front.** The v4 results export carries ZERO 2026 signal dates (it ends 2025-11-17). On the PRIMARY era this has three effects:

- `ex_2026_feb_apr` ≡ `ALL`.
- ex-BOTH ≡ `ex_2025_mar_apr`.
- "Positive in every calendar year" reduces to 2024 ∧ 2025.

Every cut prints its `n` beside `ALL`'s, so a reader sees a no-op rather than a passed test. Any v4 conjunction pass that cites year stability inherits this until 2026 dates land.

## Plan-time observations, disclosed

Measured 2026-09-02, before any arm ran. Each is a census, not a target. A later run prints its own. No number here is a result.

- **v4 corpus:** 1,022 priced rows over 148 dates (2024-01-10 to 2025-11-17). 1,016 of them join to AnalysisClaude. 969 analysis rows are unpriced: `excluded_by_book` 611 (mostly underlying_trend / unevaluable proxy rows), `not_backtested` 194, `market_row` 164.
- **v4 proxy export tiers:** tweak 564, underlying_trend 473, unevaluable 107.
- **v3 corpus:** 795 priced rows over 118 dates. 820 are unpriced: `bs_only` 295, `not_backtested` 280, market 140, excluded 105.
- **`invalidation_type` census (v4):** price+flow 1515, price-only 143, price+flow+macro 131, flow-only 4, none 3. The 5-level split is 91% `mixed` in BOTH eras, because the prompt's house style is "a price level OR a flow reversal".
- **Coverage on priced rows:** 95–100% for all six features (`invalidation_level` 98.8%, `invalidation_inside_strikes` 95.0%).
- **Pre-run expectation:** a 7-feature × structure × tier grid on 148 v4 dates will UNDERPOWER most cells. That is a legitimate outcome, not a failure.

## Features, frozen here

The feature list is closed. No seventh deterministic feature is added after a number is seen.

**ARM A — deterministic features (six, regex only), plus one measured quantity.**

1. `invalidation_type`. The PRIMARY cut is BINARY: `price_only` (~8%) vs `mixed` (all else). The 5-level split prints DESCRIPTIVELY, with **no criterion on it**.
2. `invalidation_level`: the parsed numeric level. It comes with `invalidation_inside_strikes` (the level sits between the structure's strikes).
3. `trigger_conditional`: the trigger withholds entry ("no entry before", "only if", "holds X on a closing basis"). It comes with `trigger_level`.
4. `numeric_specificity`: the count of committed `$`/strike/DTE tokens.
5. `thesis_len`: thesis length in words. `alt_len` prints beside it.
6. `alt_ratio`: `alt_len` ÷ `thesis_len`, scale-free.
7. `hallucination_rate`, from `text_corpus.citation_check`: the share of `[FLOW]` figures (strike / DTE / premium) cited in the text that are ABSENT from that date's raw flow markdown. Its coverage follows which dates have a cached markdown, so it is reported, never assumed.

**Redundancy control, not a candidate.** `evidence_n` counts `[TAG]` items only. The 95 UNTAGGED continuation lines in the v4 signal cells attach to the item above and are not counted as evidence. It is reported for ONE purpose: to show it adds nothing over `score_total`. It is never promotable to a candidate.

**EXCLUDED as redundant with closed numeric columns**, named so the exclusion is auditable:

- Evidence-item and tag COUNTS (≈ `score_flow`/`score_total`, null).
- Earnings mentions (≈ `days_to_earnings`/`score_catalyst`, null).
- Hedge language (≈ the structured `flow_intent` bracket).

**ARM B — blind taxonomy labels (five), with level sets frozen.**

| Label | Levels |
|---|---|
| `thesis_type` | flow-follow · mean-reversion · catalyst · hedge · vol |
| `evidence_quality` | 1 · 2 · 3 |
| `confidence_language` | hedged · neutral · assertive |
| `one_sided` | token · substantive (is the alt reading real?) |
| `invalidation_concreteness` | 1 · 2 · 3 |

- **Labeller.** A cheap headless model (`claude -p` with `--model claude-haiku-4-5-20251001`) sees **ONLY the text fields**: no outcome, no price, no structure result, no date, no ticker.
- **Cache.** `backtests/text_labels_cache/<sha256(text fields)>.json`, keyed on those fields ALONE. A cache hit therefore cannot carry an outcome.
- **Leakage guard, test-enforced.** `tests/test_text_features.py::test_label_input_carries_no_outcome_key` asserts that the input holds no outcome or pricing key and that the cache key is a function of the text fields only. The run fails if it fails.
- **Labeller batch size is 10, not 25** (a build note appended 2026-09-02 after the first labelling pass and BEFORE any ARM B number was read). A batch of 25 silently lost 620 of 1,804 payloads, because the labeller truncates a 25-object JSON array. A dropped item is an UNLABELLED row (NOT EVALUABLE in ARM B), never a wrong label. Batch size changes nothing a label MEANS: same prompt, same frozen level sets, same `sha256(text payload)` cache key. Every report prints the batch size it used together with its ARM B label coverage.
- **Defaults.** Wording correction (2026-09-02, before any result): `--labels` and `--citations` default to `cached`, not `run`, so that `backtest_study run --all` can never spend model credits or touch Drive by accident. The registered runs pass `--labels run --citations run` explicitly.

## What it compares

| Arm | What it does | Kind |
|---|---|---|
| [text_features ARM A](../../../arm-index.md#text_features) | The six deterministic features plus `hallucination_rate`, read WITHIN structure × tier | arm |
| `text_features ARM B` | The five blind labels, read the same way | arm |
| `text_features ARM C` | Each `CANDIDATE` from A or B applied as (i) a VETO or (ii) a one-step TIER DEMOTION, replayed top-3/day, paired by date | arm |

### ARM A and ARM B — within structure × tier

- **Terciles.** Continuous features are cut at terciles computed on the FULL era book and FROZEN before any outcome is read.
- **NaN filter.** It is `v == v` on the raw value, applied before the cut. The excluded count prints.
- **Wording correction (2026-09-02, before any result): `hallucination_rate` falls back to a declared binary cut when its terciles are degenerate.** Its distribution is a spike at zero, so the tercile edges can coincide. Then "top vs bottom tercile" is undefined and the cut is `> 0` vs `== 0`, printed as `DEGENERATE tercile edges` on the frozen-edges table. Every other continuous feature is cut at terciles as registered.
- **ARM B contrast shapes.** The registration froze the level SETS only. Wording correction (2026-09-02, before any label was read): `thesis_type` is tested ONE-VS-REST for each of its five levels. The two ordinal labels (`evidence_quality`, `invalidation_concreteness`) are tested 3 vs 1. The remaining labels are tested on their two levels (`assertive` vs `hedged`, `substantive` vs `token`). Every such test enters the same per-arm BH family.

### ARM C — gate arms

Each feature that reaches `CANDIDATE` in A or B is applied as (i) a VETO or (ii) a one-step TIER DEMOTION. It is replayed through `protocol.top_k_per_day(rank_fn=ladder_rank, k=3)` against the unmodified shipped ladder, **paired by date**.

- No other selection knob moves. Tier membership, structure universe, entry side, sizing and exits stay shipped.
- There is no gate arm without a `CANDIDATE` in A or B.
- **Bad level.** Wording correction (2026-09-02, before any result): the "bad level" is whichever of the contrast's two groups has the lower POOLED mean R on the era book. The report prints both group means beside the gate. This choice fixes only the gate's direction. It never decides whether the gate clears anything. Under the same correction, a row whose level is `None` is NOT EVALUABLE and is left alone. A gate cannot fire on a value that was never measured.

## How it is judged

**Mean R**, date-clustered: `BOOT_N = 10000`, α = .05. **PF**: `protocol.pf` with `pf_ci_by_date` / `pf_paired_by_date`.

- **ARM A/B CI.** Wording correction (2026-09-02, before any result): the separation CI is a joint-date resample over the union of the two groups' dates (`text_features.boot_ci_diff_by_date`), not `boot_ci_by_date`. That function is a one-sample CI of a mean, and criterion 1 needs a CI of a two-group difference. Within-date pairing is rejected: inside one structure × tier cell the two groups share 0–45 dates against 28–126 in the union. Each drawn date contributes its rows to whichever pool they belong to. This is the same joint-resampling shape as `protocol.pf_paired_by_date`. `protocol.boot_ci_by_date` still prints each group's own mean CI beside the difference.
- **ARM C CI.** It uses `protocol.boot_ci_paired_by_date`, as registered. `boot_ci_paired_by_date` needs both statistics on the SAME row, which A/B contrasts cannot supply.
- **PF rule, binding.** A PF claim must ALSO clear the mean-R criterion, because PF alone is gameable by fewer, larger wins.
- **MFE / MAE.** Give-back prints DESCRIPTIVELY. It is NOT A CRITERION.
- **Units.** R is quoted, never dollars, in ARM C.

## Gates

Floors run FIRST and block everything. A cell under a floor is `UNDERPOWERED`, printed with its n. No criterion is evaluated on it.

- **ARM A / B cells (feature level × structure × tier):** Wording correction (2026-09-02, before any result): at least **25 affected DATES** and at least **60 rows**. The floor binds on EACH LEVEL, not on the pair. The code requires at least 60 rows AND at least 25 dates on EACH SIDE of a contrast, and prints both as `level_a/level_b`. A looser reading (60 rows and 25 dates across the two groups combined) let a 181-vs-1 comparison "clear" the floor, so it is rejected. `tests/test_text_features.py::test_floor_binds_on_each_LEVEL_not_on_the_pair` pins the stricter reading.
- **ARM C:** at least **25 dates on which the gate CHANGES the picked set**. A date where the veto or demotion is inert is not affected.

## Bar for a candidate

A feature is a `CANDIDATE` only on the full conjunction. Failing any one clause is failing.

1. **Separation (A/B) or paired ΔR (C):** the date-clustered bootstrap CI excludes zero (`BOOT_N = 10000`, α = .05).
2. **Every LOO fold has the effect's sign.** `protocol.loo_by_date`; "read `min_gain`". For a two-group A/B contrast, Wording correction (2026-09-02, before any result): `text_features.loo_diff_by_date` is the same-shaped local helper and returns the identical `(mean_gain, share_positive, min_gain, n_folds)` tuple. `protocol.loo_by_date(rows, value_fn, baseline_fn)` takes both statistics from the SAME rows, which two disjoint row sets cannot supply. ARM C uses `protocol.loo_by_date` unchanged.
3. **It survives `protocol.window_cuts` AND the ex-BOTH cut added BY HAND.** `window_cuts()` drops one window at a time. On v4 both collapse to the 2026 no-op above, and the report says so.
4. **The effect has the same sign in every calendar year present** in the cell's population (`protocol.sign_stable`).
5. **It is right-signed on BOTH pricing tiers** (real and tweak).
6. **At least 25 affected dates and at least 60 rows**, re-checked on the evaluated set.

**Direction.** Wording correction (2026-09-02, before any result): the registration words clause 2 as "every LOO fold positive" and clause 4 as "positive in every calendar year". Clauses 2, 3 and 4 are read in the direction the effect points. Both stated hypotheses are NEGATIVE-signed (vaguer invalidation → worse, hallucinated citations → worse). A negative point estimate therefore needs every fold NEGATIVE, every year NEGATIVE, every window cut and both pricing tiers keeping that sign. A point estimate of exactly zero fails all four. This is the stability test the registration describes, not a weaker one.

**Multiple comparisons.** The feature list is closed above. Within an arm, clause 1 is also controlled by **Benjamini–Hochberg at q = 0.10**. A feature that clears its raw CI but fails BH is `NULL`, not `CANDIDATE`. BH is applied per arm, never pooled across A, B, C.

## Possible verdicts

Each feature gets exactly one token.

| Token | When |
|---|---|
| `UNDERPOWERED` | A floor was not met. The census is published and nothing is read |
| `NULL` | Powered, and the conjunction (or BH) did not clear. Recorded |
| `CANDIDATE` | The whole conjunction clears. NOT a ship |
| `NO PRE-REGISTERED VERDICT MATCHES` | The catch-all: any outcome that is none of the three above, including a result CONTRARY to the stated hypothesis and any cell the code cannot classify. It prints with its numbers and is resolved by hand in `research/current.md` |

Each `CANDIDATE` is filed into exactly one of two named output lists.

- **PROMPT-ROBUSTNESS FINDINGS.** Text predicts failure independent of the numeric columns (vaguer invalidation → worse; hallucinated citations → worse). It feeds `prompt_eval`'s `draft` mode, nothing more.
- **ENTRY-GATE CANDIDATES.** An ARM C gate raises mean R **and** PF under the k=3 replay. It feeds a `docs/deployment-rules.md` PROPOSAL.

## Known confounds, declared now

- **Text length ∝ structure complexity.** Hence every ARM A/B test is WITHIN structure, and `thesis_len` / `alt_ratio` are never read pooled.
- **Regime words ≈ the regime label already in the ladder.** The thesis restates what the ladder conditions on. So every within-structure test ALSO conditions on tier, and a "finding" cannot be the ladder read back.
- **The labeller's own lookahead.** Labels describe TEXT, never outcomes. But the model may recognise a ticker or period and label from recall. **Mitigation, binding: date and ticker are STRIPPED from the labeller input**, and the cache key is that stripped text. This reduces the risk and does not eliminate it. Every label-derived `CANDIDATE` carries the caveat.
- **`hallucination_rate` coverage is not random.** It follows which dates have a cached markdown, so it is reported, never assumed.

## Anti-tuning

- The registered set is final: six deterministic features, one measured rate, one control, five labels with frozen level sets.
- `invalidation_type` is cut binary. Terciles are cut on the full book before any outcome is read. k = 3. BH q = 0.10. Floors are 25 dates / 60 rows.
- Exit profiles, sizing, structure universe, tier membership and entry side are NOT swept.
- No threshold moves and no feature is added after any number is seen.
- **Every cell is reported regardless of outcome.**
- No annualised figure, Sharpe or time-to-recover appears anywhere.

## What could ship

**Nothing automatically. Nothing ships from a research-tier study.** An ENTRY-GATE CANDIDATE becomes a written `docs/deployment-rules.md` proposal, queued for an independent-window confirmation. The operator decides. A PROMPT-ROBUSTNESS FINDING becomes input to `prompt_eval`. A prompt reaches a v5 bump only through that harness plus an operator decision.
