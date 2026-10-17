# text_features — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/signal/text_features.md); where the two differ, the registration wins.
> Latest outcome: `ARM A` `invalidation_level` and `trigger_level` `CANDIDATE`, each in `bear_put_spread`/C (T3 vs T1) and listed under PROMPT-ROBUSTNESS FINDINGS; ENTRY-GATE CANDIDATES none; the other 26 verdict lines 17 `NULL` and 9 `UNDERPOWERED` — 2026-09-28 · [record](../../../study-results/f1_selection/signal/text_features.md).
> Nothing else here is a result.

## The question

Does the model's own text separate outcome within structure × tier? The prompt emits about 10 plays a day. Most of the content is text, and none of it was ever measured. Two questions:

1. **Separation:** does any deterministic text feature, or any blind taxonomy label, separate mean R within structure × tier?
2. **Gate value:** used as a veto or a one-step tier demotion, does any such feature raise mean R and profit factor under a top-3/day replay against the shipped `ladder_rank`?

## What it compares

Each feature is read alone. No arm builds a composite or fits anything. Numeric columns already closed (`score_total`, cpir, `oi_confirm`, `iv_pct`, `days_to_earnings` and similar) are not re-tested.

| Object | What it does | Kind |
|---|---|---|
| [text_features ARM A](../../../arm-index.md#text_features) | Six deterministic features plus `hallucination_rate`, read within structure × tier | arm |
| `text_features ARM B` | Five blind taxonomy labels, read the same way | arm |
| `text_features ARM C` | Each `CANDIDATE` from A or B applied as a veto or a one-step demotion, replayed top-3/day, paired by date | arm |

**ARM A features.** The list is closed.

- `invalidation_type`: the graded cut is binary, `price_only` against `mixed`. The 5-level split prints descriptively, with no criterion.
- `invalidation_level`, with `invalidation_inside_strikes`.
- `trigger_conditional`, with `trigger_level`.
- `numeric_specificity`, `thesis_len` (with `alt_len` beside it) and `alt_ratio`.
- `hallucination_rate`: the share of `[FLOW]` figures cited in the text that are absent from that date's raw flow markdown.

Continuous features are cut at terciles on the full era book, frozen before any outcome is read. `hallucination_rate` falls back to `> 0` against `== 0` when its tercile edges coincide.

`evidence_n` is a redundancy control and never a candidate. Evidence and tag counts, earnings mentions and hedge language are excluded as redundant with closed columns.

**ARM B labels.** A cheap headless model sees only the text fields, with date and ticker stripped. The levels are frozen.

| Label | Levels |
|---|---|
| `thesis_type` | flow-follow, mean-reversion, catalyst, hedge, vol |
| `evidence_quality` | 1, 2, 3 |
| `confidence_language` | hedged, neutral, assertive |
| `one_sided` | token, substantive |
| `invalidation_concreteness` | 1, 2, 3 |

Contrast shapes: `thesis_type` is tested one-vs-rest per level. The two ordinal labels are tested 3 against 1. `confidence_language` is `assertive` against `hedged`, and `one_sided` is `substantive` against `token`. Every test joins the arm's BH family.

**ARM C.** The "bad level" is the contrast group with the lower pooled mean R on the era book. It fixes only the gate's direction. A row whose level is unmeasured is left alone.

## How it is judged

**Population.** The primary era is v4 (`current`). v3 is secondary, same thresholds, never pooled, and carries nothing. Only real and `strike_expiry_tweak` rows enter, because bs rows are excluded. Every claim is conditioned on about 52% priceability, and the report says so.

**Measure.** Mean R, date-clustered, `BOOT_N = 10000`, α = .05. A/B contrasts use a joint-date resample over the union of the two groups' dates. ARM C uses the paired-by-date CI. PF must also clear the mean-R criterion. R is quoted, never dollars, in ARM C.

**Gates.** Floors run first and block everything.

- **ARM A/B:** at least 25 affected dates and at least 60 rows on each level of a contrast, not on the pair.
- **ARM C:** at least 25 dates on which the gate changes the picked set.
- A cell under a floor is `UNDERPOWERED`, printed with its n.

**Bar.** A feature is a `CANDIDATE` only on all of these.

1. The date-clustered CI excludes zero.
2. Every leave-one-date-out fold has the effect's sign (`min_gain`).
3. It survives `protocol.window_cuts` and an ex-BOTH cut added by hand.
4. The effect has the same sign in every calendar year present.
5. It is right-signed on both pricing tiers, real and tweak.
6. At least 25 affected dates and 60 rows on the evaluated set.

Clauses 2 to 4 are read in the direction the effect points. Both stated hypotheses are negative-signed, so a negative point estimate needs negative folds and years. A point estimate of exactly zero fails all four.

Benjamini–Hochberg at q = 0.10 also controls clause 1, per arm and never pooled. A feature clearing its raw CI but failing BH is `NULL`. When an export carries no 2026 dates, the 2026 cuts are a no-op. Each cut prints its n beside `ALL`.

## Possible verdicts

| Token | What it means |
|---|---|
| `UNDERPOWERED` | A floor was not met. Nothing is read |
| `NULL` | Powered, and the conjunction or BH did not clear |
| `CANDIDATE` | The whole conjunction clears. Not a ship |
| `NO PRE-REGISTERED VERDICT MATCHES` | The catch-all, including a result contrary to the hypothesis. Resolved by hand in `research/current.md` |

Each `CANDIDATE` goes into one of two lists. PROMPT-ROBUSTNESS FINDINGS hold text that predicts failure independent of the numeric columns, and feed `prompt_eval`'s `draft` mode. ENTRY-GATE CANDIDATES hold an ARM C gate that raises mean R and PF under the k = 3 replay.

## What could ship

Nothing ships from a research-tier study. An ENTRY-GATE CANDIDATE becomes a written `docs/deployment-rules.md` proposal, queued for independent-window confirmation. A PROMPT-ROBUSTNESS FINDING becomes input to `prompt_eval`.

## What this study cannot tell you

- Whether text works as a composite score. No arm combines features.
- Anything about exits. The shipped profiles replay through the frozen harness.
- Anything pooled across structure. `thesis_len` and `alt_ratio` are never read pooled.
- Whether a label is free of recall. The labeller may recognise a ticker or period despite stripping.
- Anything from v3 on its own.
