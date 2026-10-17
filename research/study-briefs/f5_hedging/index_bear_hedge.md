# index_bear_hedge — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f5_hedging/index_bear_hedge.md); where the two differ, the registration wins.
> Latest outcome: forward `STILL-OPEN`, 0 episodes graded — 2026-10-09. In-sample description only, no verdict: the sleeve cut drawdown in 5 of 5 v4 episodes, net −$43,947 · [record](../../study-results/f5_hedging/index_bear_hedge.md).
> Nothing else here is a result.

## The question

Do the book's SPY, QQQ and IWM bear spreads work as crash insurance? An index bear spread pays only in a sell-off, so the study grades it as insurance rather than as a standalone trade.

Three parts:

1. **Protection.** In sell-off episodes, do the spreads reduce the deployed book's drawdown?
2. **Carry.** Between episodes, what do they cost?
3. **Net.** Over the whole span, does protection outweigh carry, and at what episode frequency would it break even?

Only sell-offs that start after 2026-10-09 are graded. The in-sample v4 and v3 episodes print as a description with no verdict word.

## What it compares

Exactly one arm is graded, so no configuration is chosen from many and no PBO runs. There is no sizing grid.

| Arm | Book | Sleeve | Kind |
|---|---|---|---|
| [`index_bear_hedge B`](../../arm-index.md#index_bear_hedge) | deployed book | none | base |
| `H` | deployed book | index bears, one risk unit per signal date | graded |
| `H-raw` | deployed book | index bears at recorded size | printed, never graded; read as `RB3` |
| `H-stock` | deployed book | single-stock bears (groups G5, G6, G7), one unit per date | printed, never graded; read as `RB5` |

The deployed book is `top_k_per_day(ladder_rank, k=3, A|B)` with any index bear dropped and no fourth row promoted. An index bear is a bear position in group G1 (SPY, QQQ, IWM, DIA).

## How it is judged

**Episodes.** The primary sell-off, `E-DD5`, is built from SPY closes alone.

- A trigger day has SPY at least 5% below its trailing 63-day high.
- The window runs from that high (the peak) to the lowest close (the trough). The trough search ends when `dd` recovers above −0.02, or 42 sessions after the last trigger day, whichever is first. An episode the data has not closed is listed and never read.
- Episodes less than 10 trading days apart merge.
- Sessions in no window and not within 10 trading days after a trough count as outside. The 10-day buffer counts on neither side.

`E-DD8`, `E-VIX25` and `E-20D5` are sensitivity definitions. They never carry a verdict.

**Measures.** Curves are mark-to-market dollars, net of costs, under the shipped exits.

- `M1`, protection: `ΔDD_e`, the sleeve's change in worst in-window drawdown. Positive means it helped.
- `M2`, carry: the sleeve's dollars over outside sessions.
- `M3`, net: the sleeve's total dollars over the span, and the break-even frequency `f*`.

**Gates.** A failed gate refuses the run.

- `G-ERA`: one era per run.
- `G-MTM`: the curve reconciliation passes at the shipped tolerance.
- `G-HASH`: the episode-definition and group-table hashes match.
- `G-CENSUS`: the census prints before any outcome column is read.
- `G-OPEN`: at most 25% of the sleeve's in-window positions are still open at `path_data_end`, per episode. A failing episode is NOT EVALUABLE.

**Power floor.** An episode is evaluable with ≥ 3 sleeve positions open into the window, a pass on `G-OPEN` and ≥ 5 sessions. The verdict needs ≥ 5 evaluable forward `E-DD5` episodes, counted per era and never pooled.

**Robustness battery.** A check can block a protective verdict and none can create one.

- `RB1`: `E-DD8` and `E-20D5` keep the sign of `ΣΔDD_e`.
- `RB2`: leave-one-episode-out keeps the sign of `ΣΔDD_e` and of NET.
- `RB3`: `H-raw` keeps the sign.
- `RB4`: real-priced rows only keep the sign, when ≥ 3 episodes stay evaluable.
- `RB5`: `H-stock` does not protect at least as well. If it does, `EARNS ITS KEEP` and `PROTECTS, COSTS MORE THAN IT SAVES` gain the suffix "— bear protection, not index-specific".

A calendar-shift permutation read gives `p`. See [Overfitting](../../pre-registrations/f5_hedging/index_bear_hedge.md#overfitting).

## Possible verdicts

The first match wins. n counts evaluable forward `E-DD5` episodes.

| Token | What it means |
|---|---|
| `STILL-OPEN` | n < 5 before the sunset of 2029-10-09 |
| `UNDERPOWERED` | n < 5 after the sunset |
| `EARNS ITS KEEP` | `ΔDD_e > 0` in all n episodes; `p ≤ 0.05`; NET > 0; `H` is `unharmed` against `B` on full-span MTM; `RB1`–`RB4` hold |
| `PROTECTS, COSTS MORE THAN IT SAVES` | `ΔDD_e > 0` in ≥ n − 1 episodes and NET ≤ 0; prints `f*` against the observed rate |
| `DOES NOT PROTECT` | `ΔDD_e ≤ 0` in ≥ 2 episodes, or median `ΔDD_e ≤ 0` |
| `INDETERMINATE` | Anything else; prints the criterion vector |

Two declared lines print beside it. `FORWARD VERDICT` is the headline, with a floor of 5 forward episodes. `FORWARD EARLY READ` has a floor of 2, is never a verdict, and prints `PROTECTING`, `NOT PROTECTING` or `STILL-OPEN`.

The v3 replication runs the same rule, labelled "same-episode replication". It can block `EARNS ITS KEEP` and never upgrade v4.

The holdout seal applies: this registration is not a named reader, so both lines print `STILL-OPEN` with zero episodes graded until the seal lifts.

## What could ship

Nothing ships. `EARNS ITS KEEP` files an entry in `research/deployment-evidence.md` under "to be tested". `PROTECTS, COSTS MORE THAN IT SAVES` files `f*` as the price of the insurance. No verdict removes the [§4 sleeve](../../../docs/deployment-rules.md#s4).

## What this study cannot tell you

- Whether any one index bear is worth taking. The sleeve is every index bear emitted, with no selection or pick rule.
- When to hedge. Episode windows are drawn after the fact and can never become an entry trigger.
- Anything from the in-sample episodes. They print a description and no verdict word, in either era.
- Whether v3 is an independent check. It covers the same market episodes as v4.
- Whether the §4 sleeve should stay or go. A verdict files evidence only.
