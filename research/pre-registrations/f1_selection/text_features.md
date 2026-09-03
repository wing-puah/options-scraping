## text_features — does the model's own TEXT separate outcome within structure × tier?

_REGISTERED 2026-09-02; status: DRAFT — becomes immutable on first run._

## Question

The prompt emits ~10 plays/day, most of whose content is TEXT (`regime`,
`signal`, `play`/thesis, `trigger`, `invalidation`), none of it ever measured.
Two questions, one study: (1) **separation** — does any deterministic text
feature, or any blind taxonomy label, separate mean R WITHIN structure × tier?
(2) **gate value** — used as a VETO or a tier demotion, does any such feature
raise mean R and profit factor under a `top_k_per_day(k=3)` replay against the
shipped `ladder_rank`?

## What this is NOT

- **Not a new scorer**, and **not a re-opening of the ML/selection search.** No
  arm builds a composite, weights features or fits anything — each feature is
  read alone. That search closed 2026-08-11 NULL across 15 cells and re-opens on
  **new COLUMNS only, never new models.**
- **Not a re-test of any numeric column.** `score_total`, `score_flow`,
  `score_catalyst`, `cpir`, `oi_confirm`, `iv_pct`, `days_to_earnings` are
  closed; features restating one of them are EXCLUDED by name below.
- **Not an exit study** — shipped profiles throughout, replayed by the FROZEN
  `harness.replay`; exit questions from the same text are `exit_from_text` (f2).
  Nothing here reaches `docs/deployment-rules.md` without an operator decision.

## Admissibility

The text fields are a **NEW COLUMN FAMILY**: in the analysis export, never
joined to the priced book, no numeric counterpart in the closed sweep. Two
sub-families qualify — **deterministic text features** (regex-only) and **blind
taxonomy labels** (a cheap headless model shown ONLY the text fields, never an
outcome). Every feature is **observable at entry**. The 2026-08-11 clause also
fixes HOW a new column is tested — **within structure from the first look**,
because three columns were caught looking predictive pooled and vanishing within
structure. Every arm here is within structure and within tier.

## Population and basis, fixed here

One era carries the study; the other is reported and carries nothing.
- **PRIMARY: era `current` (v4)** — chosen over v3 because the v4 text IS
  current-prompt behaviour and is what `prompt_eval` will modify; a finding
  about v3 text is a finding about a dead prompt.
- **SECONDARY: `--era v3`**, identical thresholds, reported separately, **never
  pooled**. `load_book(include_bs=False)`: **real + strike_expiry_tweak only**;
  bs rows excluded (the 2026-08-11 hazard). **On v4 that exclusion is a NO-OP** —
  the v4 proxy export carries ZERO `bs_options_hist` rows (tweak 564 /
  underlying_trend 473 / unevaluable 107, measured 2026-09-02). It still binds
  on v3 (295 bs rows) and is left in force.
- **Priceability, measured 2026-09-02 (a census, not a target; a later run
  prints its own).** v4 corpus = **1,022 priced rows / 148 dates** (2024-01-10 →
  2025-11-17), 1,016 joined to AnalysisClaude; **969 analysis rows unpriced**
  (`excluded_by_book` 611 — mostly underlying_trend / unevaluable proxy rows —
  `not_backtested` 194, `market_row` 164). v3 = 795 priced / 118 dates, 820
  unpriced (`bs_only` 295, `not_backtested` 280, market 140, excluded 105).
  **Every text-feature claim on priced rows is conditioned on ~52%
  priceability**, and the report says so on every table.
- **The unpriced share BY FEATURE is itself reported** — does vaguer text
  co-occur with unpriceable plays? A PROMPT-ROBUSTNESS read in its own right,
  and the only place an unpriced row carries a number; no criterion is
  evaluated on unpriced rows.
- **The v4 2026 no-op, stated up front.** The v4 results export carries ZERO
  2026 signal dates (it ends 2025-11-17), so on the PRIMARY era
  `ex_2026_feb_apr` ≡ `ALL`, ex-BOTH ≡ `ex_2025_mar_apr`, and "positive in every
  calendar year" reduces to 2024 ∧ 2025. Every cut prints its `n` beside `ALL`'s
  so a reader sees a no-op rather than a passed test; any v4 conjunction pass
  citing year stability inherits this until 2026 dates land.

## Features, frozen here

**Deterministic (six, regex-only).** No seventh is added after a number is seen.
1. `invalidation_type` — **PRIMARY cut is BINARY: `price_only` (~8%) vs `mixed`
   (all else).** The 5-level split is near-degenerate — 91% `mixed` in BOTH
   eras, the prompt's house style being "a price level OR a flow reversal" (v4
   census 2026-09-02: price+flow 1515, price-only 143, price+flow+macro 131,
   flow-only 4, none 3) — so it prints DESCRIPTIVELY, **no criterion on it**.
2. `invalidation_level` — the parsed numeric level, plus
   `invalidation_inside_strikes` (level sits between the structure's strikes).
3. `trigger_conditional` — the trigger withholds entry ("no entry before",
   "only if", "holds X on a closing basis"), plus `trigger_level`.
4. `numeric_specificity` — count of committed `$`/strike/DTE tokens.
5. `thesis_len` — thesis length in words (`alt_len` prints beside it).
6. `alt_ratio` — `alt_len` ÷ `thesis_len`, scale-free.

**Plus one measured quantity**: `hallucination_rate` from
`text_corpus.citation_check` — the share of `[FLOW]` figures (strike / DTE /
premium) cited in the text that are ABSENT from that date's raw flow markdown.
**Coverage on priced rows, measured 2026-09-02: 95-100% for all six features**
(`invalidation_level` 98.8%, `invalidation_inside_strikes` 95.0%); a row missing
a feature, or with no cached markdown for its date, is NOT EVALUABLE on it,
never imputed, and coverage prints.

**Redundancy control, not a candidate.** `evidence_n` counts `[TAG]` items only
— the 95 UNTAGGED continuation lines in the v4 signal cells attach to the item
above, not counted as evidence. Reported for ONE purpose, to show it adds
nothing over `score_total`; never promotable to a candidate.

**EXCLUDED as redundant with closed numeric columns**, named so the exclusion is
auditable: evidence-item / tag COUNTS (≈ `score_flow`/`score_total`, null);
earnings mentions (≈ `days_to_earnings`/`score_catalyst`, null); hedge language
(≈ the structured `flow_intent` bracket).

**Blind taxonomy labels (five), with their level sets frozen:**

| label | levels |
|---|---|
| `thesis_type` | flow-follow · mean-reversion · catalyst · hedge · vol |
| `evidence_quality` | 1 · 2 · 3 |
| `confidence_language` | hedged · neutral · assertive |
| `one_sided` | token · substantive (is the alt reading real?) |
| `invalidation_concreteness` | 1 · 2 · 3 |

- **Labeller**: a cheap headless model (`claude -p --model
  claude-haiku-4-5-20251001`) shown **ONLY the text fields** — no outcome, no
  price, no structure result, no date, no ticker. **Cache**:
  `backtests/text_labels_cache/<sha256(text fields)>.json`, keyed on those
  fields ALONE, so a cache hit cannot carry an outcome.
- **Leakage guard, test-enforced**:
  `tests/test_text_features.py::test_label_input_carries_no_outcome_key` asserts
  the input holds no outcome/pricing key and the cache key is a function of the
  text fields only; the run fails if it fails.

## Arms

- **ARM A — deterministic features.** The six features plus
  `hallucination_rate`, read WITHIN structure × tier. Continuous features are
  cut at terciles computed on the FULL era book and FROZEN before any outcome is
  read; the NaN filter is `v == v` on the raw value, applied before the cut,
  excluded count printed. **ARM B — blind labels**: the five labels, same
  within-structure × tier treatment, level sets as tabled above.
- **ARM C — gate arms.** Each feature reaching CANDIDATE in A or B, applied as
  (i) a VETO or (ii) a one-step TIER DEMOTION, replayed through
  `protocol.top_k_per_day(rank_fn=ladder_rank, k=3)` against the unmodified
  shipped ladder, **paired by date**. No other selection knob moves — tier
  membership, structure universe, entry side, sizing, exits stay shipped; no
  gate arm without a CANDIDATE in A or B.

## Metrics

- **Mean R**, date-clustered: `protocol.boot_ci_by_date` (A/B),
  `boot_ci_paired_by_date` (C), `BOOT_N = 10000`, α = .05. **PF**: `protocol.pf`
  with `pf_ci_by_date` / `pf_paired_by_date`.
- **Rule, binding**: **a PF claim must ALSO clear the mean-R criterion** (PF
  alone is gameable by fewer, larger wins). MFE / MAE give-back prints
  DESCRIPTIVELY, **NOT A CRITERION**. **R is quoted, never dollars** in ARM C.


## Power floors, declared per arm

- **ARM A / B cells (feature level × structure × tier):** ≥ **25 affected DATES**
  and ≥ **60 rows**; a cell under either floor is **UNDERPOWERED**, printed with
  its n, no criterion evaluated on it. **ARM C:** ≥ **25 dates on which the gate
  CHANGES the picked set** — a date where the veto/demotion is inert is not
  affected.
- Floors run FIRST and block everything. Stated before any count: a 7-feature ×
  structure × tier grid on 148 v4 dates will UNDERPOWER most cells — a
  legitimate outcome, not a failure.

## Bar for CANDIDATE

A feature is a CANDIDATE only on the full conjunction — failing any one is
failing:

1. mean-R separation (A/B) or paired ΔR (C) with **date-clustered bootstrap CI
   excluding zero** (`BOOT_N = 10000`, α = .05);
2. **every** LOO fold positive (`protocol.loo_by_date`, read `min_gain`);
3. survives `protocol.window_cuts` **AND the ex-BOTH cut added BY HAND** —
   `window_cuts()` drops one window at a time; on v4 both collapse to the 2026
   no-op above and the report says so;
4. **positive in every calendar year present** in the cell's population
   (`protocol.sign_stable`);
5. right-signed on **BOTH pricing tiers** (real and tweak);
6. ≥ 25 affected dates and ≥ 60 rows, re-checked on the evaluated set.

**Multiple comparisons.** The feature list is closed above. Within an arm,
criterion 1 is additionally controlled by **Benjamini–Hochberg at q = 0.10**; a
feature clearing its raw CI but failing BH is NULL, not CANDIDATE. BH is applied
per arm, never pooled across A, B, C.

## Verdict grammar

Per feature, exactly one of:
- **UNDERPOWERED** — a floor was not met; census published, nothing read.
- **NULL** — powered, conjunction (or BH) not cleared; recorded.
- **CANDIDATE** — the whole conjunction clears; NOT a ship.

Each CANDIDATE is filed into exactly one of two named output lists:
- **PROMPT-ROBUSTNESS FINDINGS** — text predicts failure independent of the
  numeric columns (vaguer invalidation → worse; hallucinated citations → worse);
  feeds `prompt_eval`'s `draft` mode, nothing more.
- **ENTRY-GATE CANDIDATES** — an ARM C gate raising mean R **and** PF under the
  k=3 replay; feeds a `docs/deployment-rules.md` PROPOSAL.

**Catch-all, so no result falls outside the grammar**: any outcome neither
UNDERPOWERED nor NULL nor CANDIDATE — including a result CONTRARY to the stated
hypothesis, and any cell the code cannot classify — prints as **NO
PRE-REGISTERED VERDICT MATCHES** with its numbers, resolved by hand in
`research/current.md`.

## What ships if MET

**Nothing automatically. Nothing ships from a research-tier study.** An
ENTRY-GATE CANDIDATE becomes a written `docs/deployment-rules.md` proposal,
queued for an independent-window confirmation; the operator decides. A
PROMPT-ROBUSTNESS FINDING becomes input to `prompt_eval`; a prompt only reaches
a v5 bump through that harness plus an operator decision.

## Known confounds, declared now

- **Text length ∝ structure complexity** — hence every ARM A/B test is WITHIN
  structure; `thesis_len` / `alt_ratio` are never read pooled.
- **Regime words ≈ the regime label already in the ladder** — the thesis
  restates what the ladder conditions on, so every within-structure test ALSO
  conditions on tier and a "finding" cannot be the ladder read back.
- **The labeller's own lookahead.** Labels describe TEXT, never outcomes — but
  the model may recognise a ticker or period and label from recall.
  **Mitigation, binding: date and ticker are STRIPPED from the labeller input**,
  the cache key being that stripped text. It reduces the risk, not eliminates
  it; every label-derived CANDIDATE carries the caveat.
- **`hallucination_rate` coverage is not random** — it follows which dates have
  a cached markdown, so it is reported, never assumed.

## Anti-tuning

Six deterministic features, one measured rate, one control, five labels with
frozen level sets; `invalidation_type` cut binary; terciles cut on the full book
before any outcome is read; k = 3; BH q = 0.10; floors 25 dates / 60 rows. Exit
profiles, sizing, structure universe, tier membership and entry side are NOT
swept. No threshold moves and no feature is added after any number is seen.
**Every cell is reported regardless of outcome.** No annualised figure, Sharpe
or time-to-recover anywhere.

## Build notes

*Not part of the registration — implementation record.*

- Module `scripts/backtest_study/f1_selection/text_features.py`; run
  `python -m scripts.backtest_study run text_features` (`--era v3` secondary);
  report `backtests/study_output/text_features-latest.txt`. Corpus + features
  from `lib/text_corpus.py`; `book` helpers IMPORTED, never forked;
  `lib/harness.py` untouched. `tests/test_text_features.py` covers the features,
  the leakage guard above and the conjunction-bar logic.
- A `scripts/study_map/catalog.py` entry with a hand-written VERDICT is REQUIRED
  — no entry fails the test suite — plus a `research/study-map.md` prose mention
  (test-enforced).
- Every report prints `debit_calib`, `n_credit_ungated`, the credit-ungated
  caveat, the era header, priceability and `citation_check` coverage; PF never
  prints without mean R. Labelling cost is an ESTIMATE: ~1,000 priced rows ×
  ~$0.01 ≈ **$10-20**, once, cached.

---

## Wording corrections (appended 2026-09-02, at build time, before any result was read)

*The commitments above do not change. Each note below records a place where the
registration's wording named a `protocol` helper that cannot express the thing
the arm asks for, or left a mechanical choice unspecified that the code had to
make. Nothing here loosens a gate, moves a floor, adds a feature, or changes a
verdict word. Written while `text_features.py` was being built and BEFORE the
first run printed a number.*

1. **The ARM A/B separation CI is a joint-date resample over the union of the
   two groups' dates, not `boot_ci_by_date`.** §Metrics names
   `protocol.boot_ci_by_date` for A/B, but that function is a ONE-SAMPLE CI of a
   mean and criterion 1 needs a CI of a TWO-GROUP DIFFERENCE; `protocol` exposes
   no unpaired two-group mean-difference CI, and `boot_ci_paired_by_date`
   requires both statistics to live on the SAME row. Within-date pairing was
   measured and rejected on the data, not on preference: inside one structure ×
   tier cell the two contrast groups share 0–45 dates against 28–126 in the
   union, so pairing would discard most of the evidence and fail the power floor
   for a reason unrelated to any effect. `text_features.boot_ci_diff_by_date`
   therefore resamples DATES over the union, each drawn date contributing its
   rows to whichever pool they belong to — the identical joint-resampling shape
   `protocol.pf_paired_by_date` already uses to compare two books, and
   date-clustered in the same unit. `protocol.boot_ci_by_date` still prints each
   group's own mean CI beside the difference. ARM C is unaffected and uses
   `protocol.boot_ci_paired_by_date` exactly as registered.

2. **Criterion 2's LOO for a two-group contrast uses the same-shaped local
   helper.** `protocol.loo_by_date(rows, value_fn, baseline_fn)` computes both
   statistics from the SAME rows, which an ARM A/B contrast (two disjoint row
   sets) cannot supply. `text_features.loo_diff_by_date` is the two-group
   analogue and returns the identical
   `(mean_gain, share_positive, min_gain, n_folds)` tuple, so the registration's
   "read `min_gain`" instruction reads unchanged. ARM C uses
   `protocol.loo_by_date` itself, unchanged.

3. **Criteria 2, 3 and 4 are read in the DIRECTION the effect points.** The
   registration words criterion 2 as "every LOO fold positive" and criterion 4
   as "positive in every calendar year". Both of this study's stated hypotheses
   are NEGATIVE-signed (vaguer invalidation → worse, hallucinated citations →
   worse), so the code applies the mirror of each test to a negative point
   estimate: every fold NEGATIVE, every year NEGATIVE, every window cut and both
   pricing tiers keeping that sign. A cell whose point estimate is exactly zero
   fails all four. This is the stability test the registration describes, not a
   weaker one; the literal wording would have excluded the direction the study
   was written to look for.

4. **`hallucination_rate` falls back to a declared binary cut when its terciles
   are degenerate.** Its distribution is a spike at zero, so the tercile edges
   can coincide and "top vs bottom tercile" becomes undefined. Where that
   happens the cut is `> 0` vs `== 0`, printed as `DEGENERATE tercile edges` on
   the frozen-edges table so a reader sees which cut was used. Every other
   continuous feature is cut at terciles on the full era book as registered.

5. **ARM C's "bad level" is fixed as the lower-mean-R contrast group, on the era
   book, and printed.** §Arms says the gate is applied as "a VETO (eligible_fn
   excludes the bad level)" without naming which level is bad. The code takes
   whichever of the contrast's two groups has the lower POOLED mean R on the era
   book, prints both group means beside the gate, and never lets that choice
   decide whether the gate clears anything — it fixes only the gate's direction.
   A row whose level is `None` is NOT EVALUABLE and is left alone: a gate cannot
   fire on a value that was never measured.

6. **ARM B's contrast shapes.** The five level SETS are frozen above; the
   registration does not say how a 5-level nominal label becomes a two-group
   contrast. Fixed here, before any label was read: `thesis_type` is tested
   ONE-VS-REST for each of its five levels; the two ordinal labels
   (`evidence_quality`, `invalidation_concreteness`) are tested 3 vs 1; and the
   two remaining labels are tested on their two levels
   (`assertive` vs `hedged`, `substantive` vs `token`). Every such test enters
   the same per-arm BH family.

7. **`--labels` and `--citations` default to `cached`, not `run`.** So that
   `backtest_study run --all` can never spend model credits or touch Drive by
   accident. The registered runs pass `--labels run --citations run`
   explicitly, and both steps are resumable and cached, so a later bare
   `run text_features` reproduces the same report from cache.

8. **The labeller's batch size is 10, not 25** (a build note, appended
   2026-09-02 after the first labelling pass and BEFORE any ARM B number was
   read). 25 rows per `claude -p` call was tried first and silently LOST 620 of
   1,804 payloads — v3 220/795, v4 400/1009 — because the labeller truncates a
   25-object JSON array on a ~39k-character prompt. A dropped item is an
   UNLABELLED row (NOT EVALUABLE in ARM B), never a wrong label, so this cost
   coverage rather than correctness; at batch 10 the identical prompt returns
   complete batches. Batch size changes nothing a label MEANS — same prompt,
   same frozen level sets, same `sha256(text payload)` cache key — and every
   report prints the batch size it used together with its ARM B label coverage.

9. **The ARM A/B floor binds on EACH LEVEL, not on the pair.** §Power floors
   declares the floor on "ARM A / B cells (**feature level** × structure ×
   tier): ≥ 25 affected DATES and ≥ 60 rows", so the unit is one LEVEL of one
   feature inside one structure × tier — the code requires ≥ 60 rows AND ≥ 25
   dates on EACH SIDE of a contrast, and prints both as `level_a/level_b`. The
   looser reading (60 rows and 25 dates across the two groups combined) was
   written first and produced a 181-vs-1 comparison that "cleared" the floor;
   it is a bug against the registration's own wording, not a judgement call,
   and `tests/test_text_features.py::test_floor_binds_on_each_LEVEL_not_on_the_pair`
   pins the stricter reading. Nothing was read from the looser pass.
