## v4_bridge — v4 emission-composition bridge

_Registered 2026-08-11._

**Status: pre-registered, NOT run.** Everything below is fixed in advance. If
the numbers land differently from what the operator hopes, the decision rule
stands as written — that is the entire purpose of writing it first.

**What is changing.** v3 is being closed out (see the close-out entry above once
written) and the analysis prompt is being trimmed: `score_flow` and
`score_dealer` come out of the per-play `score` object; `score_vol` stays. v4
runs on a NEW spreadsheet, so the tabs are fresh and the schema drops both
columns rather than blanking them.

**Why a bridge test is needed at all.** The columns themselves are established
as decision-irrelevant — the 07-21 sweep found only `delta`/`dte` (bull_put) and
`iv_spread` (bear_put) decision-relevant, and the 08-11 ML ablations found
nothing beyond structure × regime × geometry adds anything reproducible. That is
NOT the risk here. The risk is **behavioral**: removing two of five Step-5
factors may change *what plays the model emits*. The only statistically
significant v2→v3 difference in this entire log was exactly that — credit
emission 19% → 34% — and it was not predicted in advance either.

If the emission profile shifts, every rule in `docs/deployment-rules.md` was
derived on a population v4 no longer draws from, and the ladder's validation
does not transfer. That is worth ~20 headless runs to find out.

**Test.** Run the v4 prompt over ~20 dates already covered by v3, writing to a
scratch tab. Compare against the v3 rows on the same dates (exported from the
old sheet before the switch). Date-paired, two-proportion tests on:

1. structure mix (bull_call / bull_put / bear_put / other)
2. credit share of emitted plays
3. plays per day
4. bear share
5. ladder tier mix (A / B / C / VETO)

**Decision rule, fixed now:**

- **Composition within noise** → the v3-derived ladder CARRIES FORWARD to v4
  rows. Record it and deploy unchanged.
- **Composition shifts on any of the five** → the ladder is UNVALIDATED on v4.
  Keep deploying under the v3 rules, flag every v4 row as such here, and let the
  live eval arbitrate. Do NOT quietly assume the tiers transfer, and do not
  re-derive the ladder on v4 rows until there are enough of them to mean
  anything.

**Pre-committed caveat.** ~20 dates is thin for a five-way composition test;
this is powered to catch a shift the size of the v2→v3 credit jump, not a subtle
one. A null result here is "no large shift detected", never "the populations are
the same".
