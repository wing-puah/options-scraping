# v4_bridge — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/benchmark/v4_bridge.md); where the two differ, the registration wins.
> Latest outcome: `LADDER UNVALIDATED ON v4` — 2026-09-28. Four of five measures shifted (all but credit share), read on the full v3 and v4 books, not the ~20 dates registered · [record](../../../study-results/f1_selection/benchmark/v4_bridge.md).
> Nothing else here is a result.

## The question

Does trimming the analysis prompt change what kinds of plays the model emits, compared with v3?

The v4 prompt drops `score_flow` and `score_dealer` from the per-play score. `score_vol` stays. The dropped columns are already known to be decision-irrelevant. The risk is behavioural: the model may emit a different mix of plays. If it does, the rules in `docs/deployment-rules.md` were derived on a population v4 no longer draws from.

The only significant v2-to-v3 difference in the log was credit emission, 19% to 34%. Nobody predicted it.

## What it compares

The study has one comparison, not arms. It runs the v4 prompt over about 20 dates already covered by v3. It writes to a scratch tab. The comparator is the v3 rows on the same dates, exported from the old sheet before the switch.

## How it is judged

**Measure.** Date-paired, two-proportion tests on five measures.

1. Structure mix: bull_call, bull_put, bear_put, other.
2. Credit share of emitted plays.
3. Plays per day.
4. Bear share.
5. Ladder tier mix: A, B, C, VETO.

**Power.** About 20 dates is thin for a five-way composition test. The study can catch a shift the size of the v2-to-v3 credit jump, not a subtle one. A null result means "no large shift detected". It never means the populations are the same.

**Bar.** The decision rule has two outcomes, both worded before the run.

- Composition within noise on all five measures.
- Composition shifts on any one of the five.

## Possible verdicts

| Registered outcome | Printed token | What it means |
|---|---|---|
| Composition within noise | `LADDER CARRIES FORWARD TO v4` | The v3-derived ladder carries forward to v4 rows. Record it and deploy unchanged |
| Composition shifts on any of the five | `LADDER UNVALIDATED ON v4` | The ladder is unvalidated on v4 |

On a shift, keep deploying under the v3 rules and flag every v4 row as unvalidated. Let the live evaluation arbitrate. Do not assume the tiers transfer. Do not re-derive the ladder on v4 rows until enough exist.

## What could ship

Nothing ships. The study records whether the v3 ladder carries forward. Within noise, the ladder applies to v4 rows. On a shift, deployment stays on the v3 rules and v4 rows are flagged.

## What this study cannot tell you

- Whether the two populations are the same. A null means only that no large shift was detected.
- Whether the dropped score columns matter. That is already established as decision-irrelevant.
- Whether the ladder works on v4. A "within noise" result allows the ladder to carry forward, nothing more.
- Anything about the 2026-08-11 ML ablations or the 07-21 sweep. Both are settled elsewhere.
