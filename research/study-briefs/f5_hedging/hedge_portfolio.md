# hedge_portfolio — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f5_hedging/hedge_portfolio.md); where the two differ, the registration wins.
> Latest outcome: mechanism `UNDERPOWERED`; `ARM M` `MEASUREMENT-ONLY` — 2026-09-28 · [record](../../study-results/f5_hedging/hedge_portfolio.md).
> Nothing else here is a result.

## The question

When the open book is concentrated in one correlated cluster, does a long put on that cluster's proxy cut the book's [mark-to-market](../../glossary.md#mark-to-market-basis) drawdown? The comparison is the same concentrated book, unhedged.

The operator queued this on 2026-08-28: the programme's next question is max drawdown, not timing. It matches their practice of hedging when they hold many correlated positions, such as semis against SMH.

## What it compares

The grid is 3 τ × 3 f, so 9 cells per arm. It is fixed and never expanded. Concentration is the largest cluster's share of book gross delta notional.

- τ, the concentration threshold: {0.30, 0.35, 0.40}
- f, the hedge size as a fraction of a standard position's risk: {0.25, 0.50, 1.00}

| Object | What it does | Kind |
|---|---|---|
| [hedge_portfolio ARM M](../../arm-index.md#hedge_portfolio) | Measurement. The same unhedged book on the mark-to-market curve and the realized-on-close curve. Runs first, gates nothing | measurement |
| hedge_portfolio ARM C | Hedges when concentration ≥ τ with a long put on the cluster's proxy. Band rule primary, nearest-available as sensitivity. No prose | hedge arm |
| hedge_portfolio ARM CS | `ARM C` plus the analysis prose's `hedge-pressure ≥ 50`. A date with no parse is no signal | hedge arm, prose-conditioned |
| [hedge_portfolio ARM P](../../arm-index.md#hedge_portfolio-arm-p) | `ARM C` on exactly `ARM CS`'s sessions, minus the prose condition. Inert as registered, because both arms hedge the same sessions | hedge arm |
| hedge_portfolio ARM N | Random admission matched in count and date-clustering, 200 seeds. An arm must beat its 95th percentile | null band |
| hedge_portfolio ARM B | `ARM C` with the book's own bear row as the instrument | instrument comparison |
| hedge_portfolio ARM R | `ARM C` with a delta-equivalent short in the proxy underlying. A floor on feasibility, not a recommendation | reference |

The sector map is fixed in the registration: 11 clusters, each with one proxy, and the residual is BROAD with proxy SPY. It cannot be edited. Four clusters are unhedgeable: ENERGY, FINL, CRYPTO and INTL. They keep their identity in the concentration measure and are never folded into BROAD. A session whose top cluster is unhedgeable is carried at f = 0 and counted against the fill gate. See [Population and basis](../../pre-registrations/f5_hedging/hedge_portfolio.md#population-and-basis-fixed-here).

## How it is judged

**Population.** Era v4 only, through `load_book(include_bs=False)`. The ratified population is `all`: 996 rows over 145 signal dates. The `real` stratum alone is a reported stratum, never the concluding population. The universe is the sessions with at least one open position: 504 on the `real` stratum at plan time; the run prints the ratified count.

**Metrics.** The unit is the session, with date-clustered intervals.

- Primary: max drawdown in dollars on the mark-to-market curve, hedged versus unhedged.
- Co-primary: Ulcer index, and time-under-water.
- Secondary, never concluded from: total P&L, worst single session, realized-on-close max drawdown.

**Gates.**

- `G-ERA`: v4 or refuse. A thin era also refuses.
- `G-FILL`: a hedge must be fillable on at least 60% of triggered sessions under the band rule. Unfillable sessions are carried at f = 0. Below 60%, the proxy-put arms are `NOT EVALUABLE` and only `ARM R` is read. A build ruling defines "fillable"; see [Gates](../../pre-registrations/f5_hedging/hedge_portfolio.md#gates).
- `G-POWER`: at least 25 trigger dates per cell. Below that, the cell is `UNDERPOWERED`.
- `G-BLIND`: the triggered session set must be identical with outcome fields stripped, or the study prints `LOOKAHEAD DETECTED` and refuses.
- `G-MTM`: cumulative mark-to-market P&L at each position's exit equals its booked realized P&L, within rounding.
- `G-CENSUS`: the power census prints before any outcome column is read.

**Bar.** A cell is a candidate only if it meets all seven clauses.

1. Max drawdown and worst single session are both no worse than f = 0, in dollars.
2. Ulcer index or time-under-water improves, with a date-clustered CI excluding zero at Bonferroni α = 0.05/9.
3. The cell beats ARM N's 95th percentile on that metric.
4. The cell is positive in at least 2 of the book's years.
5. Both ex-window cuts keep the sign.
6. Every leave-one-date-out fold keeps the sign.
7. The improvement exceeds `ARM R`'s at the same τ and f. A put that only matches it is reported as a restatement of delta reduction.

**Stratification.** Results split DIRECT versus CONSTITUENT. A DIRECT result may never support the operator's constituent-to-proxy practice. A DIRECT null is not evidence against it either.

## Possible verdicts

| Token | What it means |
|---|---|
| `MECHANISM-FOUND` | At least one cell clears every clause. It names the cluster, τ, f, instrument and path metric |
| `NULL` | Gates pass and no cell clears the bar |
| `CONTRARY` | A cell's drawdown is reliably worse than unhedged under the same clauses |
| `UNDERPOWERED` | `G-POWER` fails. No direction is quoted, ever |
| `NOT EVALUABLE` | `G-FILL` fails for the proxy-put arms. `ARM R` is not evidence about puts |
| `MEASUREMENT-ONLY` | `ARM M` shows the two curves differ materially, but no hedge cell clears the bar |

No verdict may rest on `ARM CS` alone. If `ARM CS` clears the bar and `ARM P` does not, the verdict is `PROSE-CONDITIONED, LOOKAHEAD-UNRESOLVED`. That is a forward-window candidate, never a ship.

## What could ship

Nothing ships without operator sign-off. `MECHANISM-FOUND` produces a drafted amendment to [§4](../../../docs/deployment-rules.md#s4) of the deployment rules, held in `research/`. `NULL` or `CONTRARY` ships nothing and closes the queued max-drawdown question. No outcome removes the §4 sleeve.

## What this study cannot tell you

- Whether the operator's constituent practice works. The constituent stratum is expected to be power-stopped.
- Whether any result holds on the analysis prose. The prose carries model-recall risk, because the v4 analysis is a 2026-08 backfill.
- Anything about long-dated hedging. Hedge expiries are bounded to 20–120 DTE.
- Whether `ARM R` is tradable. The operator does not trade it.
- Anything about worst-decile tails. Every primary metric is path-shaped.
