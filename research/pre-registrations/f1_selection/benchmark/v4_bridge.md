## v4_bridge — v4 emission-composition bridge

<!-- outcome:start -->
> Latest outcome: `LADDER UNVALIDATED ON v4` — 2026-09-28. Four of five measures shifted (all but credit share), read on the full v3 and v4 books, not the ~20 dates registered · [record](../../../study-results/f1_selection/benchmark/v4_bridge.md).
<!-- outcome:end -->

_Registered 2026-08-11._

**Status: pre-registered, NOT run.** Everything below is fixed in advance. If the numbers land differently from what the operator hopes, the decision rule stands as written — that is the entire purpose of writing it first.

## The question

Does trimming the prompt change *what the model emits*?

**What is changing.** v3 is being closed out (see the close-out entry above once written). The analysis prompt is being trimmed: `score_flow` and `score_dealer` come out of the per-play `score` object, while `score_vol` stays. v4 runs on a NEW spreadsheet, so the tabs are fresh and the schema drops both columns rather than blanking them.

The dropped columns themselves are established as decision-irrelevant. That is NOT the risk here:

- the 07-21 sweep found only `delta`/`dte` (bull_put) and `iv_spread` (bear_put) decision-relevant;
- the 08-11 ML ablations found nothing beyond structure × regime × geometry adds anything reproducible.

The risk is **behavioral**. Removing two of five Step-5 factors may change *what plays the model emits*. The only statistically significant v2→v3 difference in this entire log was exactly that — credit emission 19% → 34% — and it was not predicted in advance either.

If the emission profile shifts, every rule in `docs/deployment-rules.md` was derived on a population v4 no longer draws from. The ladder's validation then does not transfer. That is worth ~20 headless runs to find out.

## What this study is not

**Pre-committed caveat.** ~20 dates is thin for a five-way composition test. The study is powered to catch a shift the size of the v2→v3 credit jump, not a subtle one. A null result here is "no large shift detected", never "the populations are the same".

It does not test whether the dropped score columns matter, and it does not re-open the 08-11 ML ablations or the 07-21 sweep.

## Population and basis, fixed here

Run the v4 prompt over ~20 dates already covered by v3, writing to a scratch tab. The comparator is the v3 rows on the same dates, exported from the old sheet before the switch.

## How it is judged

Date-paired, two-proportion tests on five measures:

1. structure mix (bull_call / bull_put / bear_put / other)
2. credit share of emitted plays
3. plays per day
4. bear share
5. ladder tier mix (A / B / C / VETO)

## Verdicts, worded now

Decision rule, fixed now — the two outcomes, both worded before the run:

| Outcome | Consequence |
|---|---|
| **Composition within noise** | The v3-derived ladder CARRIES FORWARD to v4 rows. Record it and deploy unchanged |
| **Composition shifts on any of the five** | The ladder is UNVALIDATED on v4. Keep deploying under the v3 rules, flag every v4 row as such here, and let the live eval arbitrate |

On a shift, do NOT quietly assume the tiers transfer. Do not re-derive the ladder on v4 rows until there are enough of them to mean anything.

## What could ship

Nothing ships. The study records whether the v3 ladder carries forward. Within noise, the ladder applies to v4 rows unchanged. On a shift, deployment stays on the v3 rules and v4 rows are flagged.
