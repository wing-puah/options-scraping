# concurrency_correlation — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f4_deployment/concurrency_correlation.md); where the two differ, the registration wins.
> Latest outcome: v4 `NOISE`, all 13 arms inside `ARM N`'s band (2026-09-28). The `X4` era-stability check is still pending. Newest v3 run: 8 of 13 arms powered, none clear (2026-09-04) · [record](../../study-results/f4_deployment/concurrency_correlation.md).
> Nothing else here is a result.

## The question

Does the size of the open book, or its internal similarity, degrade a new position's outcome, apart from which plays were selected? The study separates two effects.

- **Concurrency.** Does a position opened while N others are open do worse as N rises?
- **Correlation.** Does a position opened beside others pointing the same way (same direction, sector or underlying) do worse than one opened into an unlike book?

## What it compares

This is an exposure study, not a selection study. The ladder is frozen: `protocol.top_k_per_day(book, ladder_rank, k=3, ladder_eligible)`. The exits are frozen. The only new machinery is a book-state annotation at each position's entry session. Each arm refuses picks, and a refused pick keeps its stored outcome as a counterfactual.

| Object | What it does | Kind |
|---|---|---|
| [concurrency_correlation ARM N](../../arm-index.md#concurrency_correlation) | Random book-state labels drawn to match each real arm's affected-position count, at least 1,000 draws, date-clustered. Every arm's gain is reported against its [p5, p95] band | null control |
| concurrency_correlation ARM D0 | Mean R by concurrency band at entry, plus the same table by same-direction count and by same-sector count. Never a criterion | descriptive |
| concurrency_correlation ARM C | Refuses a pick whose entry session already has at least C open positions | ceiling arm |
| concurrency_correlation ARM K | Refuses a pick when the open book already holds at least K positions sharing its relation | ceiling arm |
| concurrency_correlation ARM CK | The conjunction of `ARM C` and `ARM K`. Runs only if `ARM C` and `ARM K` each clear their criteria independently. A conjunction that clears while neither component does is refused | conjunction |

The grids are fixed.

- `ARM D0` bands: `[0,3) [3,6) [6,10) [10,20) [20,inf)`.
- `ARM C`: `C ∈ {5, 8, 12, 20}`.
- `ARM K`: `K ∈ {2, 3, 5}`, run separately for same-direction, same-direction-and-sector, and same-underlying.

## How it is judged

**Measure.** The paired within-date mean gain in [R](../../glossary.md#r) against the unmodified deployed book.

**Book state.** Computed at entry from entry-dated information only. A position is open on session *s* if `entry_date <= s < exit_date`. Counts are at position level, not leg level. A position with no delta has direction UNKNOWN and is excluded from every direction total, never counted as zero. Sector comes from a static ticker-to-sector map written from a source outside this book. Unmapped tickers form their own bucket.

**Population.** The pooled book from `load_book()`, era-scoped, `include_bs=False`. PRIMARY is dense episodes (`episode_max_gap = 5`, `episode_min_dates = 10`). SECONDARY is the full sparse book. Both eras must run and be reported.

**Gates.** Each exits non-zero on failure.

- `G1`: the report names the era and export fingerprint. A mismatch or thin era refuses, with no study-local snapshot pin.
- `G2`: every annotation is re-verified by independent recomputation. Any field dated after entry fails the run.
- `G3`: the unmodified pick set equals `top_k_per_day(...)` by set equality.
- `G4`: every refused pick attributes to exactly one binding arm rule, and the counts sum exactly.
- `G5`: no annualised figure, Sharpe or time-to-recover.
- `G6`: every printed count is computed from the run, never hardcoded.

**Bar.** All of X1 to X8 must hold. A failure is not a footnote.

1. **X1 power floor.** The arm changes at least 25 dates and at least `MIN_N_TO_READ` positions. Below either, it prints `UNDERPOWERED` with census only.
2. **X2 gain.** Paired within-date mean gain in R has a 95% date-clustered CI excluding zero.
3. **X3 not noise.** The gain exceeds `ARM N`'s p95.
4. **X4 era stability.** X2 and X3 hold on both eras (v3 and current) with the same sign, and the point estimates lie within 0.15 R of each other.
5. **X5 population stability.** Same sign on PRIMARY and SECONDARY.
6. **X6 leave-one-out.** Dropping any single date, and separately any single ticker, leaves the gain positive.
7. **X7 not a delta ceiling in disguise.** The gain must still clear X2 within `portfolio_delta`'s own bands, after controlling for net delta-notional at entry.
8. **X8 dollar honesty.** Dollars are quoted real plus tweak, never pooled with `bs_options_hist` rows.

## Possible verdicts

| Token | What it means |
|---|---|
| `ADOPT` | One arm clears X1 to X8 on both eras. The report proposes the ceiling as a card rule. The operator decides |
| `ADVISORY ONLY` | An arm clears X1, X2 and X3 but fails X4 or X5. The census stays a printed line on the deploy card. No rule ships |
| `NOISE` | Any arm is powered but inside `ARM N`'s band |
| `UNDERPOWERED` | No arm clears X1. Census only, nothing concluded |
| `RESTATEMENT` | An arm clears X2 and X3 but fails X7. It restates `portfolio_delta`'s ARM B or ARM D, which already failed |

## What could ship

Nothing ships on a dollar total. No ceiling value is adopted because it made more money in the grid. The only admissible reading of the grid is qualitative monotonicity: the grid is a shape, not a menu. `ADOPT` is the only verdict that proposes a card rule.

## What this study cannot tell you

- Whether the account can afford a position. The 3-per-day cap's displaced picks carry no counterfactual in `account_sim`, and this study never compares to its dollar totals.
- Whether concurrency differs from calendar clustering. Dense-episode sessions are often high-concurrency sessions. `ARM D0` prints the cross-tab and no criterion rests on it.
- Anything about top-N depth. Rank depth inside the survivor set is flat on both eras.
- Anything about selection, exits or tier rules. No column, knob or tier rule may change.
