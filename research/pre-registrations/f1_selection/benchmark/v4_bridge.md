## v4_bridge — v4 emission-composition bridge

<!-- brief:start -->
## In brief

> Plain-language brief for readers. The registration below is the binding text; where the two differ, the registration wins. `study_review` cuts this brief out before grading, so the blind graders never see it.
> Latest outcome: `LADDER UNVALIDATED ON v4` — 2026-09-28. Four of five measures shifted (all but credit share), read on the full v3 and v4 books, not the ~20 dates registered · [record](../../../study-results/f1_selection/benchmark/v4_bridge.md).
> Nothing else in this brief is a result.

**The question**

Does trimming the analysis prompt change what kinds of plays the model emits, compared with v3?

The v4 prompt drops `score_flow` and `score_dealer` from the per-play score. `score_vol` stays. The dropped columns are already known to be decision-irrelevant. The risk is behavioural: the model may emit a different mix of plays. If it does, the rules in `docs/deployment-rules.md` were derived on a population v4 no longer draws from.

The only significant v2-to-v3 difference in the log was credit emission, 19% to 34%. Nobody predicted it.

**What it compares**

The study has one comparison, not arms. It runs the v4 prompt over about 20 dates already covered by v3. It writes to a scratch tab. The comparator is the v3 rows on the same dates, exported from the old sheet before the switch.

**How it is judged**

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

**Possible verdicts**

| Registered outcome | Printed token | What it means |
|---|---|---|
| Composition within noise | `LADDER CARRIES FORWARD TO v4` | The v3-derived ladder carries forward to v4 rows. Record it and deploy unchanged |
| Composition shifts on any of the five | `LADDER UNVALIDATED ON v4` | The ladder is unvalidated on v4 |

On a shift, keep deploying under the v3 rules and flag every v4 row as unvalidated. Let the live evaluation arbitrate. Do not assume the tiers transfer. Do not re-derive the ladder on v4 rows until enough exist.

**What could ship**

Nothing ships. The study records whether the v3 ladder carries forward. Within noise, the ladder applies to v4 rows. On a shift, deployment stays on the v3 rules and v4 rows are flagged.

**What this study cannot tell you**

- Whether the two populations are the same. A null means only that no large shift was detected.
- Whether the dropped score columns matter. That is already established as decision-irrelevant.
- Whether the ladder works on v4. A "within noise" result allows the ladder to carry forward, nothing more.
- Anything about the 2026-08-11 ML ablations or the 07-21 sweep. Both are settled elsewhere.

---
<!-- brief:end -->

_Registered 2026-08-11._

**Status: pre-registered, NOT run.** Everything below is fixed in advance. If the
numbers land differently from what the operator hopes, the decision rule stands
as written — that is the entire purpose of writing it first.

**What is changing.** v3 is being closed out (see the close-out entry above once
written) and the analysis prompt is being trimmed: `score_flow` and
`score_dealer` come out of the per-play `score` object, while `score_vol` stays.
v4 runs on a NEW spreadsheet, so the tabs are fresh and the schema drops both
columns rather than blanking them.

## Question

Does trimming the prompt change *what the model emits*?

The dropped columns themselves are established as decision-irrelevant, and that
is NOT the risk here:

- the 07-21 sweep found only `delta`/`dte` (bull_put) and `iv_spread` (bear_put)
  decision-relevant;
- the 08-11 ML ablations found nothing beyond structure × regime × geometry adds
  anything reproducible.

The risk is **behavioral**. Removing two of five Step-5 factors may change *what
plays the model emits*. The only statistically significant v2→v3 difference in
this entire log was exactly that — credit emission 19% → 34% — and it was not
predicted in advance either.

If the emission profile shifts, every rule in `docs/deployment-rules.md` was
derived on a population v4 no longer draws from, and the ladder's validation does
not transfer. That is worth ~20 headless runs to find out.

## What this is NOT

**Pre-committed caveat.** ~20 dates is thin for a five-way composition test; this
is powered to catch a shift the size of the v2→v3 credit jump, not a subtle one.
A null result here is "no large shift detected", never "the populations are the
same".

## Population and basis, fixed here

Run the v4 prompt over ~20 dates already covered by v3, writing to a scratch tab.
The comparator is the v3 rows on the same dates, exported from the old sheet
before the switch.

## Unit and metric

Date-paired, two-proportion tests on five measures:

1. structure mix (bull_call / bull_put / bear_put / other)
2. credit share of emitted plays
3. plays per day
4. bear share
5. ladder tier mix (A / B / C / VETO)

## Verdicts, worded now

Decision rule, fixed now — the two outcomes, both worded before the run:

- **Composition within noise** → the v3-derived ladder CARRIES FORWARD to v4
  rows. Record it and deploy unchanged.
- **Composition shifts on any of the five** → the ladder is UNVALIDATED on v4.
  Keep deploying under the v3 rules, flag every v4 row as such here, and let the
  live eval arbitrate. Do NOT quietly assume the tiers transfer, and do not
  re-derive the ladder on v4 rows until there are enough of them to mean
  anything.
