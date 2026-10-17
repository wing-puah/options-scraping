# account_sim — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f4_deployment/account_sim.md); where the two differ, the registration wins.
> Latest outcome: `NOT FEASIBLE` (no capital rung passes A1 and A2) — 2026-09-28 · [record](../../study-results/f4_deployment/account_sim.md).
> Nothing else here is a result.

## The question

Does the shipped ladder's paper edge survive a $25,000 account with real opening constraints? This is a feasibility study, not an edge search. Selection and exits stay frozen. The only new machinery is an account ledger.

## What it compares

Every arm runs on the same frozen ladder picks, `top_k_per_day` with k=3 and `ladder_eligible`. Exits are the shipped profiles. Two baselines bracket the constrained run.

| Object | What it does | Kind |
|---|---|---|
| [account_sim B1](../../arm-index.md#account_sim) | Stored contract counts and stored outcomes. It must reproduce the deployed-book line of the 08-12 `vol_sleeve` report: 220 positions, 90 dates, $63,553 | baseline |
| account_sim B2 | The same ladder sized at $25k on a max-loss basis | baseline |
| [account_sim ARM R](../../arm-index.md#account_sim) | Skips a position that breaches any cap at risk-sized contracts. It logs the counterfactual R and R_dol | admission arm |
| account_sim ARM D | Cuts contracts to the largest integer that satisfies every cap, then re-replays at that size. Zero contracts means reject | admission arm |
| account_sim F1 | Takes the 1-contract floor even when its max loss exceeds $500. This is what production does | floor cell |
| account_sim F2 | Refuses those picks | floor cell |
| account_sim ARM H | Adds the shipped bear hedge sleeve (1 per day, `|delta|` descending, at most half size) to the constrained run | hedge arm |

B1 to B2 isolates granularity. B2 to the constrained run isolates the caps. F1 versus F2 divides 133 of 218 picks, so the registration calls it the central object.

## How it is judged

**Ledger.**

- Starting capital is $25,000, a fixed base. A compounding run is a labelled sensitivity only.
- Risk per trade is 2%, so $500. Contracts are `max(1, int(500 / max_loss_per_contract))`, a max-loss basis.
- At most 3 positions open per day, in descending `ladder_rank`.
- Reserved capital equals max loss times contracts. It is held from the entry session through the exit session.
- The per-position cap is 0.25 × equity. The net cap is 1.50 × equity. Both use [delta-notional](../../glossary.md#delta-notional).

**Population.** PRIMARY is the dense episodes: maximal runs of signal dates with no internal gap over 5 trading sessions and at least 10 dates. SECONDARY is the full sparse book. It cannot carry a conclusion alone.

**Headline cell.** The cap grid crosses two sets. The headline is the single (0.25, 1.50) cell, quoted first and alone.

- Per-position cap: {0.15, 0.25, 0.40, ∞}
- Net cap: {1.00, 1.50, 2.50, ∞}

**Gates.** A failed gate exits non-zero.

- `G1`: book calibration is quoted (`debit_calib`, `n_credit_ungated`).
- `G2`: every deployed pick, replayed at stored contracts, matches its stored exit reason, days held and R. A build ruling changes the basis; see [Gates](../../pre-registrations/f4_deployment/account_sim.md#gates).
- `G3`: at every session, cash plus reserved equals $25,000 plus realized P&L to date.
- `G4`: the unconstrained pick set equals `top_k_per_day` by set equality.

**Bar.** Six criteria, A1 to A6.

1. A1 EDGE SURVIVAL: constrained [mean R](../../glossary.md#meanr) is above 0, the 95% date-clustered CI excludes zero, and every year present is positive.
2. A2 ATTRITION: constrained total dollars are at least 60% of B2 on the same dates.
3. A3 NO BLOWUP: the ledger never over-reserves, and constrained max drawdown is at most 25% of starting capital.
4. A4 ATTRIBUTION: every rejection or downsize names exactly one binding constraint, and the counts sum exactly. A mismatch fails the run.
5. A5 STABILITY: the constrained-to-B2 dollar ratio moves at most 15 points across both mandatory window cuts.
6. A6 CREDIT SENSITIVITY: A1 also holds on the debit-only subset, because `book.py` admits credit rows ungated.

## Possible verdicts

| Token | What it means |
|---|---|
| `FEASIBLE` | A1, A2, A3, A5 and A6 all hold |
| `FEASIBLE-BUT-DEGRADED` | A1 and A3 hold, and A2 fails |
| `NOT FEASIBLE AT $25k` | A1 fails |

After a `NOT FEASIBLE` verdict prints, the report adds an operator note. It names the smallest capital in {25k, 35k, 50k} where A1 and A2 pass. The same anti-tuning rule covers it.

No cap value may be adopted, recommended or carried into a conclusion on its P&L in the grid. Only qualitative monotonicity is readable. A non-monotone surface signals a ledger bug.

## What could ship

Nothing ships from this study under any outcome.

## What this study cannot tell you

- Whether any cap value is good. The grid exists for a monotonicity check only.
- Whether the selection rule or the exits should change. Both are frozen.
- Anything from the SECONDARY full book alone.
- A return rate. No annualised figure, Sharpe or time-to-recover may be quoted.
- Whether the plan-time cap values are free of influence. The registration discloses that its own observations informed them.
