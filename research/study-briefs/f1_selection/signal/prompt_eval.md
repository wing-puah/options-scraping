# prompt_eval — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/signal/prompt_eval.md); where the two differ, the registration wins.
> Latest outcome: no candidate scored; variance floor 0.0419 from the `VARIANCE` set — 2026-09-04 · [record](../../../study-results/f1_selection/signal/prompt_eval.md).
> Nothing else here is a result.

## The question

Does a named candidate analysis prompt produce a better book than the shipped prompt, under the shipped ladder's own top-3/day replay? Is any measured difference larger than the harness's own noise? The registration covers a harness, not a market hypothesis. It fixes how a candidate prompt is scored, so a v5 bump can rest on a number instead of a hand edit.

## What it compares

Exactly two arms. Only the prompt text differs. The ladder, tier map, structure universe, sizing and exits are the shipped ones in both arms. Both arms use the same engine and the same `--model`.

| Object | What it does | Kind |
|---|---|---|
| `prompt_eval PROD` | The committed `config/prompts/analysis-framework.md` and `config/prompts/analysis-methods/claude.md`. Their sha256 is recorded at run time | arm |
| `prompt_eval CANDIDATE` | A named, committed snapshot directory holding the same two files. The diff between the two is stored with the run | arm |

A report whose PROD sha differs from the committed files at read time is void. A candidate that is not committed cannot be scored.

Three date sets are declared in this order:

- **`VARIANCE`:** 5 dates × 3 PROD repeats, 15 calls. It measures the spread of paired ΔR between PROD repeats. That spread is the variance floor.
- **`BACKFILL`:** about 40 signal dates drawn from the v4 book by rule. The signal date must be at least 90 calendar days before the run date. Dates are stratified across model regime × calendar year in proportion to the eligible population. No `VARIANCE` date is used. The list is written to the run directory before any call.
- **`LIVE`:** every new production date after the registration on which the candidate runs locally the same day. Production's export is the PROD arm.

`LIVE` is primary and `BACKFILL` is secondary. Both arms share a lookahead defect on backfilled dates, because the v4 book was backfilled in 2026-08 with a 2026 model. `prompt_eval draft` is a run, not an arm. A headless model proposes a candidate directory and diff from the `text_features` findings. Nothing applies it.

## How it is judged

**Measure.** Paired ΔR by date under the shipped top-3/day replay (`ladder_rank`, k = 3), date-clustered, `BOOT_N = 10000`, α = .05. R is quoted, never dollars. Printed beside it:

- Paired [PF](../../../glossary.md#pf). A PF claim must also clear the mean-R criterion.
- Tier-mix census and emissions per date.
- Unpriceable share per arm. The measured v4 baseline is about 52% priceability, a census and not a target.
- `citation_check` hallucination rate, with coverage.
- The `bear_call_spread` leak count.
- The variance floor, reprinted on every report.

**Isolation.** No arm writes Sheets. Every derived config carries `sheet_tab: null`. The harness refuses to start if any subprocess argv carries `--tab`. The citation cache is `backtests/analysis_inputs_cache/`, never `audit/`. The comparison book uses `load_book(..., check_era=False, min_dates=0)` and supports no era-scoped conclusion.

**Binding consequence of the floor.** No |ΔR| smaller than the variance floor may be called a difference. The floor is computed once per model and engine pair.

**Bar.** `MET` needs all seven, on the date set being judged.

1. The paired ΔR CI excludes zero.
2. |ΔR| exceeds the variance floor.
3. PF(candidate) ≥ PF(prod) by CI.
4. The hallucination rate is not worse than PROD on the same dates.
5. Zero `bear_call_spread` leaks.
6. Every leave-one-date-out fold is positive (`min_gain`).
7. At least 25 dates on the set being judged.

**Precedence.** The `LIVE` verdict supersedes the `BACKFILL` verdict once `LIVE` reaches 25 dates. A candidate is scored once on backfill. A second backfill run on the same dates is not permitted.

## Possible verdicts

| Token | What it means |
|---|---|
| `MET` | All seven criteria clear. The candidate is eligible for a v5 bump proposal. The operator decides |
| `NOT MET` | Powered (criterion 7 clears) and the conjunction does not clear. Not re-scored on these dates |
| `UNDERPOWERED` | Criterion 7 fails, or the variance floor is not yet established. Nothing is read |
| `CONTRARY` | Powered, CI excludes zero, and the candidate is reliably worse. The diff is kept with the record |
| `NO PRE-REGISTERED VERDICT MATCHES` | The catch-all. Printed with its numbers and resolved by hand in `research/current.md` |

## What could ship

Nothing ships from this study. `MET` makes the candidate eligible for a v5 bump proposal. The bump is an operator decision and a tab rename, never a study output.

## What this study cannot tell you

- Whether a different model helps. Both arms use the same model and engine.
- Anything about the ladder, sizing or exits. They are not swept.
- A distribution of prompt noise. The floor comes from 5 dates and is a floor only.
- A clean forward read from the backfill. The shared lookahead defect applies.
