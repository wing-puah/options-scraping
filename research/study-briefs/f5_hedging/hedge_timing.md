# hedge_timing — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f5_hedging/hedge_timing.md); where the two differ, the registration wins.
> Latest outcome: `hedge_timing ARM H3-GAP` `CONTRARY`. `ARM H4-CHOP`, `ARM H4-GAP` and `ARM H4-DECLINE` `UNSTABLE`. The other six headline arms `NULL`: H1 and H3 for each of CHOP and DECLINE, and H1-GAP. Control `ARM H2-GAP` `TIMING-CANDIDATE`; the other two H2 controls `NULL`. 0 `TIMING-CANDIDATE` survivors — 2026-09-28 · [record](../../study-results/f5_hedging/hedge_timing.md).
> Nothing else here is a result.

## The question

The operator deploys the bear-debit hedge sleeve on three discretionary triggers: the market looks choppy, SPY gaps up, or SPY has closed lower 4 to 5 sessions in a row. Do those triggers, made mechanical, mark days when the hedge earns more than the same day's ladder-eligible long? Should streak days be spent opening a long instead?

The study asks about timing only. The sleeve's pick and size stay operator discretion.

## What it compares

Each trigger is evaluated on the signal date D. Entry is the next session's open, so every trigger is known a session before money moves. The trigger set is closed at registration.

| Object | What it does | Kind |
|---|---|---|
| T-CHOP | `eff_ratio` over 20 SPY sessions at or below the bottom-tercile boundary. Sensitivity: ≤ 0.30 | trigger family |
| T-GAP | `open(D) ≥ close(D−1) × (1 + g)`. Primary g = 0.003. Sensitivity g = 0.002 | trigger family |
| T-DECLINE-STRICT(N) | N consecutive lower SPY closes ending at D, N ∈ {3, 4, 5}. Verdict fixed in advance: `DECLINE-UNDERPOWERED` | trigger family |
| T-DECLINE-BROAD | SPY closed lower on at least 3 of the last 5 sessions | trigger family |

T-CHOP is not `mech_direction = RANGE`, a post-hoc gate from `hedge_sizing` D5. RANGE prints as a flagged secondary with no verdict.

The verdicted arms run once per trigger family.

| Object | What it does | Kind |
|---|---|---|
| [hedge_timing ARM H0](../../arm-index.md#hedge_timing-arm-h0) | Power census. Runs first and reads no outcome column | census |
| [hedge_timing ARM H1](../../arm-index.md#hedge_timing-arm-h1) | Between-date: mean bear R on trigger dates minus non-trigger dates. Confounded with "the market fell", so not primary | arm |
| [hedge_timing ARM H2](../../arm-index.md#hedge_timing-arm-h2) | Beta control: the same separation for the deployed ladder | control |
| [hedge_timing ARM H3](../../arm-index.md#hedge_timing-arm-h3) | PRIMARY. Within-date paired: bear R minus ladder-eligible long R | arm |
| [hedge_timing ARM H4](../../arm-index.md#hedge_timing-arm-h4) | Do-nothing baseline in dollars: never hedge, always hedge, and trigger-gated | arm |

H4 runs at f ∈ {0.5, 1.0}, one hedge per day. Days with no bear row are carried at f = 0, never dropped.

## How it is judged

**Population.** The decisive read is `current` (v4), through `load_book(include_bs=False)`. Outcome is R under the shipped PROD exits, with no `be_after` variant. Bear rows are `bear_put_spread` and `long_put` debit rows. A `--era v3` replication prints separately with identical thresholds and is partially correlated. The two eras are never pooled.

**Units.** R only in H1 to H3. Dollars only in H4. The unit is the date, and every interval resamples dates.

**H3.** On each trigger date with at least one bear row and one tier A or B row, dR is the date-mean bear R minus the date-mean long R. The headline is the difference between the paired means on trigger and non-trigger dates.

**H2 mirror.** `h2_mirrors` fires when `|H2 delta| ≥ 0.5 × |H1 delta|` and the two deltas have opposite signs.

**Gates.** Each gate exits non-zero on failure.

- `G1`: book calibration is printed in the header. A build ruling changes the basis; see [Gates](../../pre-registrations/f5_hedging/hedge_timing.md#gates).
- `G2`: the two SPY series agree. Daily log-return correlation is at least 0.99, and daily direction matches on at least 99% of overlapping dates. Failure gives `NOT EVALUABLE`.
- `G3`: the floors below hold before any outcome access.
- `G4`: no annualised figure, Sharpe or time-to-recover. `G5`: dollars appear only in H4.

**Floors.** An arm below a floor prints its n and no direction.

- At least 25 trigger dates for every date-clustered arm. H3 binds on paired dates.
- At least 60 rows for any row-level cell.
- At least 25 gated days for H4.

**Multiplicity.** Each family has one headline: CHOP tercile, GAP 0.003, DECLINE-BROAD. Three families times H1, H3 and H4 give 9 headline tests. The report prints "~0.45 expected by chance at 5%". Every other operationalisation is a sensitivity and never promotes.

**Bar.** A candidate meets all of these.

1. The CI excludes zero.
2. Every leave-one-date-out fold has the same sign.
3. Both year signs hold. On v4 this means 2024 and 2025.
4. All three window cuts hold. On v4, two of them are no-ops and the report says so.
5. For `TIMING-CANDIDATE`, `h2_mirrors` is false.

A positive T-DECLINE-BROAD result is a weaker hypothesis. It may never count as evidence for the 4-to-5-day rule. A null there does inform the strict rule.

## Possible verdicts

| Token | What it means |
|---|---|
| `NOT EVALUABLE` | An upstream gate failed: `G1` calibration or `G2` series cross-check |
| `UNDERPOWERED` | A floor is not met. Census only, no direction |
| `TIMING-CANDIDATE` | Full bar, positive, and not `h2_mirrors` |
| `MARKET-TIMING-PROXY` | Full bar, positive, but `h2_mirrors`: the day is good for everything |
| `CONTRARY` | Full bar with a negative sign: the hedge is worse than the same day's long |
| `UNSTABLE` | The CI excludes zero, but a LOO fold, year sign or window cut fails |
| `NULL` | Powered, and the CI spans zero |
| `INDETERMINATE` | Catch-all. The criterion vector prints verbatim |

## What could ship

Nothing ships from this study under any outcome. Each result is applied by hand, and the outcomes are fixed in advance.

- `TIMING-CANDIDATE` on H3, with H4 unharmed and the v3 read not contradicting: queued for an independent window. No [§4](../../../docs/deployment-rules.md#s4) edit.
- `CONTRARY`: a §4 prohibition is drafted and held for the operator.
- `MARKET-TIMING-PROXY`: recorded as a not-a-hedge finding.
- All `NULL` or `UNDERPOWERED`: §4 gains one subtraction sentence, plus the finding that the 4-to-5-day streak rule is not testable at this book's emission density.

A forward trigger re-runs the study when 25 book dates carry a live strict down-run of N ≥ 4. It also re-runs once 25 signal dates exist after 2025-11-04.

## What this study cannot tell you

- Whether the operator's strict 4-session rule works. The registration fixes `DECLINE-UNDERPOWERED` for it and quotes no direction from n = 2.
- Whether the sleeve is worth holding. It tests timing only.
- Which bear to pick. Selection is closed.
- Anything pooled across eras.
- Anything from a H4 pass alone. H4 reuses `hedge_sizing` D5's estimator, which failed year-stability.
