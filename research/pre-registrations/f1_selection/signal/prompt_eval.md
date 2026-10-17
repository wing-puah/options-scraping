## prompt_eval — a HARNESS for scoring a candidate analysis prompt against the shipped one

<!-- outcome:start -->
> Latest outcome: no candidate scored; variance floor 0.0419 from the `VARIANCE` set — 2026-09-04 · [record](../../../study-results/f1_selection/signal/prompt_eval.md).
<!-- outcome:end -->

_REGISTERED 2026-09-02; status: DRAFT — becomes immutable on first run._

## The question

Does a named CANDIDATE prompt produce a better book than the SHIPPED prompt,
measured under the shipped ladder's own top-3/day replay? Is any measured
difference larger than the harness's own noise?

This registers a HARNESS, not a hypothesis about the market. It fixes how a
candidate prompt is scored, so a v5 bump can rest on a number instead of a
hand-edit. Nothing here ships a prompt.

## What this study is not

- **Not a ship.** MET makes the candidate eligible for a v5 bump PROPOSAL. The
  bump is an operator decision and a tab rename, never a study output.
- **Not a selection study.** The ladder, tier map, structure universe, sizing
  and exits are the shipped ones in BOTH arms. Only the prompt text differs.
- **Not a model comparison.** Both arms run the same `JUDGMENT`-free analysis
  engine and the same `--model`. A model change is a different question.
- **Not a live-tab operation.** No arm writes Sheets (see Isolation).

It cannot tell you:

- anything about the ladder, sizing or exits: they are not swept;
- a distribution of prompt noise: the variance floor is a floor only;
- a clean forward read from the backfill: the shared lookahead defect applies.

## What it compares

Exactly two arms. No third arm, no per-date arm switching, no partial prompts.

| Arm | What it is |
|---|---|
| **PROD** | The current `config/prompts/analysis-framework.md` + `config/prompts/analysis-methods/claude.md` |
| **CANDIDATE** | A NAMED, COMMITTED snapshot directory holding the same two files |

- **PROD.** Its sha256 is recorded at run time in the run manifest. A report
  whose PROD sha differs from the committed files at read time is void.
- **CANDIDATE.** The diff between the two is part of the record and is stored
  with the run. A candidate that is not committed cannot be scored.

## Date sets, declared in this order

### (a) VARIANCE set — declared FIRST, run FIRST

**5 dates × 3 PROD repeats = 15 calls.** Same arm, same dates, three times.
`claude -p` exposes no temperature knob, so the within-arm spread is unknown
and unbounded until measured. This set establishes the **variance floor**: the
spread of paired ΔR between PROD repeats on the same dates.

**Binding consequence: no |ΔR| smaller than the variance floor may be called a
difference**, in this study or in any write-up that cites it. The floor is
computed once per (model, engine) pair and reported with every later run.

### (b) BACKFILL set — chosen BY RULE, not by hand

**~40 signal dates (an ESTIMATE; the rule decides the actual count), drawn from
the v4 book by this rule and no other:**

1. **Matured windows only** — signal date ≤ (run date − 90 calendar days), so
   every play in both arms has had its full path.
2. **Stratified across model regime × calendar year** among the eligible dates,
   proportional to the eligible population.
3. **No date from the VARIANCE set.**

The selected list is written into the run directory before any call is made.
It is part of the record.

### (c) LIVE set — PRIMARY evidence

**Every new production date after this registration** on which the CANDIDATE
arm is run locally the same day (`accumulate` mode). Production already
produced the PROD arm that day; its export IS the PROD arm. One extra model
call per day.

**Why LIVE is PRIMARY and BACKFILL is SECONDARY.** Both arms share the same
lookahead defect on backfilled dates: **the v4 book was itself backfilled in
2026-08 using a 2026 model on 2024–2025 dates**, so a "better" backfill score
may be recall rather than reasoning. The defect is symmetric across arms, so
the comparison is usable. It is not clean evidence about a prompt's forward
behaviour. Genuinely new live dates are.

## Isolation invariants (stated as invariants, enforced at run time)

- **`--output-dir` never writes Sheets.** The pipeline's Sheets append is
  skipped UNCONDITIONALLY under `--output-dir`, not merely under `--dry-run`.
- **Every derived backtest config carries `sheet_tab: null`** —
  `output.sheet_tab` and `proxy.sheet_tab` both — and reads its analysis from a
  local CSV.
- **The harness REFUSES TO START if any subprocess argv would carry `--tab`**,
  or if any derived config has a non-null `sheet_tab`. The refusal is a
  designed exit code, not an exception.
- The citation cache is `backtests/analysis_inputs_cache/`, **never** the
  production `audit/` directory.
- Option history scraping goes to the shared `backtests/option_history_cache/`
  exactly as production does. Candidate plays with new strikes cost scrape
  time; the report says so.

## How it is judged

Every measure is computed identically on both arms, over the same date set.
R is quoted, never dollars: the two arms emit different plays, so contract
counts are not comparable.

- **Paired ΔR by date** under the shipped ladder's **top-3/day replay**
  (`protocol.top_k_per_day(rank_fn=ladder_rank, k=3)`), via
  `protocol.boot_ci_paired_by_date`, `BOOT_N = 10000`, α = .05.
- **Paired profit factor** (`protocol.pf_paired_by_date`). **A PF claim must
  ALSO clear the mean-R criterion.**
- **Tier-mix census** — the A/B/C/VETO distribution per arm.
- **Emissions per date** per arm.
- **Unpriceable share** per arm, against the measured v4 baseline: 1,022 priced
  rows of 1,991 analysis rows, **~52% priceability** (census 2026-09-02, not a
  target). A prompt that emits unpriceable structures buys its score with rows
  the backtest cannot evaluate.
- **`citation_check` hallucination rate** per arm, with coverage printed.
- **`bear_call_spread` leak count — MUST BE 0.** It is tier-VETO'd at intake.
  A candidate that emits one has broken the intake contract.
- **The variance floor** from set (a), reprinted on every report.


## Bar for a candidate

MET means **the candidate is eligible for a v5 bump PROPOSAL. It is NEVER a
ship.** All of the following must hold, on the date set being judged:

1. **paired ΔR CI excludes zero** (date-clustered, `BOOT_N = 10000`, α = .05);
2. **|ΔR| > the variance floor** from set (a);
3. **PF(candidate) ≥ PF(prod) by CI** (`pf_paired_by_date`);
4. **hallucination rate not worse** than PROD on the same dates;
5. **zero `bear_call_spread` leaks**;
6. **every LOO fold positive** (`protocol.loo_by_date`, read `min_gain`);
7. **≥ 25 dates on the set being judged.**

Failing any one is failing.

### Precedence between date sets

**Precedence, fixed here: the LIVE-set verdict SUPERSEDES the BACKFILL verdict
whenever the LIVE set reaches the 25-date floor.** A backfill MET plus a live
NOT MET is NOT MET. A backfill NOT MET does not block a candidate from
accumulating live dates. A candidate is scored ONCE on backfill. A second
backfill run on the same dates is criterion-shopping and is not permitted.

## Possible verdicts

| Token | When |
|---|---|
| `MET` | All seven clear. Candidate for a v5 bump proposal; operator decides |
| `NOT MET` | Powered (criterion 7 clears) and the conjunction does not. Recorded; the candidate is not re-scored on these dates |
| `UNDERPOWERED` | Criterion 7 fails, or the variance floor is not yet established. Census published, nothing read, nothing refuted |
| `CONTRARY` | Powered, CI excludes zero, and the candidate is reliably WORSE. A real finding about the proposed edit; recorded, and the diff is kept with it |
| `NO PRE-REGISTERED VERDICT MATCHES` | The catch-all, printed with its numbers and resolved by hand in `research/current.md` |

## Known confounds and defects

- **Shared backfill lookahead**, as stated in (c) — the reason LIVE supersedes.
- **The variance floor is itself estimated from 5 dates.** It is a floor, not a
  distributional claim. It is re-estimated whenever the model or engine
  changes.
- **Candidate strikes may be un-cached**, so the candidate arm can carry a
  higher unpriceable share for a mechanical reason. The unpriceable-share
  census is the guard and prints beside every ΔR.
- **The `draft` diff is model-written** and inherits every bias of the
  `text_features` list that seeded it.
- **The comparison book uses a documented escape hatch** — `load_book(...,
  check_era=False, min_dates=0)` on the run's own CSVs. It is an ARM-COMPARISON
  book, never a population claim, and no era-scoped conclusion may be drawn
  from it. The report states this inline.

## Cost and operating disclosure

All figures are ESTIMATES, disclosed so the operator can refuse the run:

- ~**80 backfill calls** (≈40 dates × 2 arms) + **15 variance calls** ≈
  **$190**, ≈ **5 hours** unattended, plus option-history scrape time for
  candidate strikes not already cached.
- After that first scoring, a candidate only **accumulates**: one extra call
  per live date, ~$2/day, no re-scoring.
- The run is delegated to a subagent. The report records wall time, call count
  and the model used.

## `draft` mode

A headless model receives the **PROMPT-ROBUSTNESS FINDINGS** list from
`text_features` plus the current framework/method text. It writes a unified
diff to `backtests/prompt_drafts/<stamp>.diff`.

**Wording correction (2026-09-02):** the BUILD could not match the wording above, so `draft` writes a candidate DIRECTORY, not a
bare `.diff`. The harness writes `<out>/analysis-framework.md`,
`<out>/claude.md`, `<out>/CANDIDATE.md` and `<out>/draft.diff` (plus the prompt
and the raw response), conventionally under `backtests/prompt_drafts/<stamp>/`.
Two mechanical reasons:

1. A candidate is a directory holding the two prompt files, and `run` refuses
   one with no `CANDIDATE.md`. A bare `.diff` could not be copied into one
   without the operator rebuilding both files by hand.
2. The diff is computed LOCALLY with `difflib` from the files the model
   returned, not trusted from a model-written diff hunk. So `draft.diff`
   describes the files that would actually be scored.

This correction changes no gate, bar, arm definition, criterion or verdict.

**The diff is a RECORD, never an application.** Nothing applies it. The
operator reviews it and, if they want it scored, copies it into a committed
candidate directory, which is what makes it an arm. Nothing writes
`config/prompts/`: the harness refuses an `--out` inside `config/`. A draft
that is never committed is never scored, and that is the intended default.

## Anti-tuning

- Two arms; three date sets, each defined by a rule fixed before any call.
- Criteria are fixed at seven; k is fixed at 3.
- The variance floor is computed before any candidate is scored and is not
  recomputed to fit a result.
- The ladder, tier map, sizing, exits, structure universe and entry side are
  NOT swept.
- A candidate is scored once on backfill.
- **Every measure is reported regardless of outcome.**
- No annualised figure, Sharpe, or time-to-recover anywhere.

## What could ship

Nothing ships from this study. MET makes the candidate eligible for a v5 bump
PROPOSAL. The bump is an operator decision and a tab rename, never a study
output.
