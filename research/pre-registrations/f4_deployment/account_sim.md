## account_sim — does the shipped ladder survive a small real account?

<!-- outcome:start -->
> Latest outcome: `NOT FEASIBLE` (no capital rung passes A1 and A2) — 2026-09-28 · [record](../../study-results/f4_deployment/account_sim.md).
<!-- outcome:end -->

_Registered 2026-08-13._

## The question

Does the shipped ladder's paper edge survive a **$25,000** account with real
opening constraints?

## What this study is not

This is a FEASIBILITY study, not an edge search. Nothing in the trading rule
moves:

- The selection rule is FROZEN: `protocol.top_k_per_day(book, ladder_rank,
  k=3, ladder_eligible)`, the shipped operator card. No column may be added to
  selection.
- The exits are FROZEN: the shipped profiles via
  `bear_giveback.prod_profile_for`. No exit knob may be moved.
- The only new machinery is an account ledger.

## Population and basis, fixed here

### The dates measured

- **PRIMARY** = dense episodes: maximal runs of signal dates with no internal
  gap > 5 trading sessions and ≥ 10 dates. The episode list prints before any
  result.
- **SECONDARY** = the full sparse book. It is labelled an availability upper
  bound and a concurrency lower bound. It may not carry a conclusion alone.
- No annualised return, Sharpe, or time-to-recover may be quoted anywhere in
  the write-up.

### The account and the ledger

- `STARTING_CAPITAL = 25_000`, a fixed base, matching production's fixed
  `portfolio_value`. A compounding-equity run is a labelled sensitivity only.
- `RISK_PER_TRADE_PCT = 0.02`, so $500. `contracts = max(1, int(500 /
  max_loss_per_contract))`. This is a MAX-LOSS basis.
- The max-loss basis is deliberately more conservative than production's
  risk-to-stop basis (`budget / (premium × 0.75 × 100)`). A real small account
  cannot assume the stop fills. The difference is disclosed here, not
  discovered later.
- `max_loss_per_contract == entry_net×100` was verified on 593/593 debit rows.
  It is also the broker-margin basis for credits.
- `MAX_POSITIONS_PER_DAY = 3`. Within a day the order is `ladder_rank`
  descending, the shipped ordering, not a knob.
- Reserved capital = `max_loss_per_contract × contracts`. It is held from entry
  session `t.grid[0]` through exit session `t.grid[days_held-1]` inclusive. It
  is released with realized P&L booked at exit.
- Delta-notional per position = `|delta| × 100 × contracts × entry_underlying`.
  It is computed at entry and is constant for the position's life.
- `delta` is the row's signed NET per-spread delta (`simulate.py:496-501`): one
  market anchor leg plus BS for the rest. It is decision-time and never drifts.
- Portfolio net = |Σ signed|. Gross = Σ|·|. Both are reported.
- **PER_POSITION_CAP = 0.25 × equity** ($6,250). It sits just above the
  observed p75 and bites the tail without reshaping the book. A cap below the
  median would be a different strategy, not a friction.
- **NET_CAP = 1.50 × equity** ($37,500). It binds on roughly the upper half of
  occupied sessions, which is the point.
- The $500 dollar stop is applied through an exact scaling identity. The replay
  runs at `contracts × 2` under the frozen harness ($1,000 stop), and dollars
  are divided by 2. Integrality is asserted. The identity is calibrated at
  scale=1 against stored rows (G2).

## Plan-time observations, disclosed

These distributions were measured on the pooled book (795 rows real+tweak,
08-11 exports) while DESIGNING this study. The cap values above are informed by
them, and that is stated rather than hidden.

- **Ladder picks:** 220 over 90 dates (218 with usable max_loss).
- **At $25k / 2% ($500 budget):** **170/218 picks floor at 1 contract; 133
  breach the budget at one contract** (worst single-position risk $3,321 =
  13.3% of equity).
- **Per-position |delta-notional|/equity:** p10 0.05, median 0.14, p75 0.22,
  p90 0.32, max 0.94.
- **Daily |net| delta-notional/equity:** median 1.28×, p90 4.73×, max 8.38×.
  Only 1/218 deployed picks is negative-delta, so net ≈ gross until a hedge
  sleeve is added.
- **Reserved-capital/equity:** median 0.27, p90 0.83, max 1.80.
- **Concurrent open positions:** median 8, p90 29, max 48.
- **Date spacing:** the 118 signal dates cluster hard (2026-03: 124 rows; nine
  months have ≤4 dates). They are not a trading calendar.

## What it compares

All arms are reported; none is adopted. The constrained run is read against two
unconstrained baselines, both on the same ladder.

| Object | What it does | Kind |
|---|---|---|
| [account_sim B1](../../arm-index.md#account_sim) | STORED contract counts and stored outcomes | baseline |
| account_sim B2 | $25k max-loss sizing | baseline |
| [account_sim ARM R](../../arm-index.md#account_sim) (REJECT) | A position breaching any cap at risk-sized contracts is skipped, logged with counterfactual R / R_dol | admission arm |
| account_sim ARM D (DOWNSIZE) | Contracts are reduced to the largest integer satisfying every cap, then **re-replayed at the reduced size** (never rescaled arithmetically); 0 → reject | admission arm |
| account_sim F1 | TAKE the 1-contract floor even when its max loss exceeds $500, as production does | floor cell |
| account_sim F2 | REFUSE those picks | floor cell |
| account_sim ARM H | The SHIPPED bear hedge sleeve (1/day, `|delta|` descending, ≤½ size) added to the constrained run | hedge arm |

- **B1** must reproduce the deployed-book line the 08-12 `vol_sleeve` report
  printed on the same exports: **220 positions / 90 dates / $63,553**.
- B1→B2 isolates granularity. B2→constrained isolates the caps.
- **F1 vs F2:** known before registration, F1 vs F2 divides 133/218 of the book.
  This is the study's central object.
- `ARM H` is the only way net-vs-gross becomes measurable.

## Gates

Four gates. A failure exits non-zero.

- **G1 — book calibration** quoted (`debit_calib`, `n_credit_ungated`).
- **G2 — replay identity.** Every deployed pick re-replayed at stored
  contracts, scale=1, must match stored `(exit_reason, days_held, round(R,4))`
  for calibrated debit rows.
  - `Resolved at build (2026-09-28)`, operator ruling: since the 2026-09-24
    re-price, a stored row is net of `cost_total` and stops at `path_data_end`.
  - The comparison adds the row's cost back. It replays the path cut at
    `path_data_end` (`lib/replay_basis.py`). An `open_at_data_end` row
    therefore matches as the `cap_open` outcome it is.
  - A row with blank `cost_basis` is compared as before.
  - A deferred exit fill (`exit_fill` = `deferred_<n>`) is its own
    `deferred_fill` class. It is kept as an outcome and never compared.
  - The gate's bar is unchanged.
  - Resolved at build (2026-10-21), operator ruling: a pending row is no
    longer in the book. It is an `open_at_data_end` row still inside its path
    window at the export's data end (`lib/book.py::is_pending`). A row whose
    window has closed still matches as `cap_open`. The gate's bar is unchanged.
- **G3 — ledger self-check.** At every session,
  `cash + Σreserved == 25,000 + Σrealized-to-date`.
- **G4 — selection identity.** The unconstrained pick set equals
  `top_k_per_day(...)` by set equality. This proves no silent re-selection.

## Bar for a candidate

- **A1 EDGE SURVIVAL** — constrained mean R over taken positions > 0, 95%
  date-clustered CI excluding zero, positive every year present.
- **A2 ATTRITION** — constrained total $ ≥ 60% of B2 on the same dates.
- **A3 NO BLOWUP** — the ledger never over-reserves (a violation FAILS the
  run) and constrained max drawdown ≤ 25% of starting capital.
- **A4 ATTRIBUTION** — every rejection or downsize attributes to exactly ONE
  binding constraint (cash / per-pos delta / net delta / min-1 refusal / day-3
  cap). The counts sum exactly (self-check; a mismatch FAILS the run).
- **A5 STABILITY** — the constrained/B2 dollar ratio moves ≤ 15 points across
  both mandatory window cuts.
- **A6 CREDIT SENSITIVITY** — A1 must also hold on the debit-only subset.
  Credit rows are admitted ungated by `book.py`.

## Verdicts, worded now

Worded now, before any result.

| Token | When |
|---|---|
| `FEASIBLE` | A1∧A2∧A3∧A5∧A6 |
| `FEASIBLE-BUT-DEGRADED` | A1∧A3 with A2 failing |
| `NOT FEASIBLE AT $25k` | A1 fails |

On NOT FEASIBLE, and only after the primary verdict prints, the report prints
the smallest capital in {25k, 35k, 50k} at which A1∧A2 pass. This is an
operator note under the same anti-tuning rule.

## Anti-tuning

The cap grid is per-position ∈ {0.15, 0.25, 0.40, ∞} × net ∈ {1.00, 1.50,
2.50, ∞}. The HEADLINE is the single pre-registered (0.25, 1.50) cell, quoted
first and alone.

**No cap value may be adopted, recommended, or carried into a conclusion on the
basis of its P&L in this grid.** The only admissible reading is qualitative
monotonicity. A non-monotone surface is evidence of a ledger bug, not an
opportunity.

## What could ship

**Nothing ships from this study under any outcome.**
