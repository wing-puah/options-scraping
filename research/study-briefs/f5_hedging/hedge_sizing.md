# hedge_sizing — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f5_hedging/hedge_sizing.md); where the two differ, the registration wins.
> Latest outcome: D1–D4 all `NOT MET` — 2026-09-28 · [record](../../study-results/f5_hedging/hedge_sizing.md).
> Nothing else here is a result.

## The question

The file holds two registrations. The original (2026-08-11) asks whether a bear hedge sleeve is deployable, and on what terms. Four criteria, D1 to D4, carry it. The v4 re-read (2026-08-24) asks what happens to the `docs/deployment-rules.md` [§4](../../../docs/deployment-rules.md#s4) hedge-sleeve lines now that the v4 verdicts reversed.

The study measures a proxy, not a held hedge. It cannot see margin, assignment or the operator's real sizing. It speaks about bear spreads, not naked puts. The operator pre-committed that bear positions stay as a hedge, so no outcome deletes §4.

## What it compares

The study has criteria, not arms. [hedge_sizing D1 to D4](../../arm-index.md#hedge_sizing) are not `ARM D`. Each original criterion has a pass rule, quoted below. Four decision rules, RE-1 to RE-4, govern the §4 lines.

| Object | What it tests | Kind |
|---|---|---|
| hedge_sizing D1 | Joint selection × exit: the pre-declared clause vocabulary re-screened on R replayed under `be_after: 0.50` | criterion |
| hedge_sizing D2 | Hedge contribution: does a bear sleeve pay on the deployed book's worst-decile dates | criterion |
| hedge_sizing D3 | Sizing: a bear sleeve added at fraction f ∈ {0, ¼, ½, 1} of standard size | criterion |
| hedge_sizing D4 | Conditional pick: does `|delta| high first` beat the day's bear average on dates with at least 2 bear candidates | criterion |
| hedge_sizing RE-1 | The pick line: "rank by `|delta|` DESCENDING, take the closer-to-money one" | decision rule |
| hedge_sizing RE-2 | The far-OTM prohibition: "do not buy the cheap far-OTM put" | decision rule |
| hedge_sizing RE-3 | The size line: "≤ ½ a normal position" | decision rule |
| hedge_sizing RE-4 | The sleeve's evidence label in §4 | decision rule |

## How it is judged

**Basis for the v4 re-read.**

- The decisive read is the `study_review` run on the era-v4 exports refreshed 2026-08-24 17:09 (inputs `46cc19b`).
- The 2026-08-22 run is instability evidence, not a basis. D2 and D3 flipped from MET to NOT MET on +50 rows and +9 dates. A criterion whose verdict flipped within an era counts as UNSTABLE.
- The pick line binds on R under the shipped PROD exit. The bear `be_after: 0.50` exit was reverted on 2026-08-24.
- This is a correlated-window re-read. Pulling an unsupported card line is allowed. Adopting a new rule from it is not.

**Original criteria, as quoted in the registration.**

1. D1 SHIPS iff all of these hold:
   - n ≥ 40 and mean R ≥ 0
   - date-clustered CI lower bound > 0
   - positive in ≥ 2 years
   - both ex-window cuts ≥ 0
   - ≤ 2 clauses
2. D2 is REAL iff bear-sleeve mean R on the book's worst-decile dates is > 0 and the date-level sleeve correlation is < 0. Both must reproduce in ≥ 2 years.
3. D3 is DEPLOYABLE AT f iff the combined book's max drawdown and worst-date loss are both no worse than f = 0, judged on dollars.
4. D4 is ADOPTED iff the mean within-date rank gain has a date-clustered CI excluding zero and every leave-one-date-out fold is positive.

**Decision rules for the §4 lines.**

- RE-1: `|delta| high first` must pass the D4 rule on the R (PROD) basis. Pass means RE-AFFIRMED. Otherwise the line is PULLED and the pick is operator discretion. A null does not flip the preference.
- RE-2: the prohibition is RETAINED if `|delta| low first` has a point gain ≤ 0 on R, or a CI that spans zero. It is PULLED only if the gain is > 0 with the CI excluding zero.
- RE-3: the size line is POLICY-HELD and unchanged by any outcome. D3 is recorded as evidence status only.
- RE-4: if D2 is NOT MET, §4 gains a sentence. The sleeve is held as operator policy, and the v4 hedge-contribution read is unsupported and unstable within the era. If D2 is MET, the evidence-backed wording stays with the same caveat.

The registration quotes its expectation up front. D1 is most likely NULL, D2 is most likely to return something, and D4 is a coin-flip.

## Possible verdicts

| Token | What it means |
|---|---|
| `MET` | The criterion's pass rule holds in the decisive read |
| `NOT MET` | The pass rule fails |
| RE-1 `RE-AFFIRMED` or `PULLED` | The pick line stays, or the bullet is replaced |
| RE-2 `RETAINED` or `PULLED` | The prohibition stays with a v3-era citation, or is removed |
| RE-3 `POLICY-HELD` | The size line never changes |

## What could ship

Nothing ships and no config changes. The outcomes are the RE-1 to RE-4 edits to §4, applied after grading. A forward trigger re-runs the study when the v4 book holds at least 20 multi-candidate bear dates after 2026-08-11. A pick rule may be adopted again only on that read.

## What this study cannot tell you

- Whether a held hedge pays. Equal-weighted concurrent dollars stand in for it.
- Whether naked puts work. Bear rows are mostly spreads.
- Whether to delete the §4 sleeve. It is operator policy and exempt from removal.
- Anything adoptable from this window. It is a correlated-window re-read.
- Whether the v4 D2 and D3 results are stable. They flipped within the era.
