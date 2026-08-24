## account_sim

_Registered 2026-08-13._

**Question.** Does the shipped ladder's paper edge survive a **$25,000** account
with real opening constraints? This is a FEASIBILITY study, not an edge search.
The selection rule is FROZEN (`protocol.top_k_per_day(book, ladder_rank, k=3,
ladder_eligible)` — the shipped operator card) and the exits are FROZEN (the
shipped profiles via `bear_giveback.prod_profile_for`). No column may be added
to selection and no exit knob may be moved. The only new machinery is an
account ledger. **Nothing ships from this study under any outcome.**

**Plan-time observations, disclosed.** These distributions were measured on the
pooled book (795 rows real+tweak, 08-11 exports) while DESIGNING this study; the
cap values below are informed by them and that is stated rather than hidden.
Ladder picks: 220 over 90 dates (218 with usable max_loss). At $25k / 2%
($500 budget): **170/218 picks floor at 1 contract; 133 breach the budget at one
contract** (worst single-position risk $3,321 = 13.3% of equity). Per-position
|delta-notional|/equity: p10 0.05, median 0.14, p75 0.22, p90 0.32, max 0.94.
Daily |net| delta-notional/equity: median 1.28×, p90 4.73×, max 8.38×; only
1/218 deployed picks is negative-delta, so net ≈ gross until a hedge sleeve is
added. Reserved-capital/equity: median 0.27, p90 0.83, max 1.80. Concurrent
open positions: median 8, p90 29, max 48. The 118 signal dates cluster hard
(2026-03: 124 rows; nine months have ≤4 dates) — not a trading calendar.

**Population and basis, fixed here.**
- `STARTING_CAPITAL = 25_000`, fixed base (matching production's fixed
  `portfolio_value`); a compounding-equity run is a labelled sensitivity only.
- `RISK_PER_TRADE_PCT = 0.02` → $500; `contracts = max(1, int(500 /
  max_loss_per_contract))` — a MAX-LOSS basis, deliberately more conservative
  than production's risk-to-stop basis (`budget / (premium × 0.75 × 100)`),
  because a real small account cannot assume the stop fills; the difference is
  disclosed here, not discovered later. Verified `max_loss_per_contract ==
  entry_net×100` on 593/593 debit rows; it is also the broker-margin basis for
  credits.
- `MAX_POSITIONS_PER_DAY = 3`; within-day order = `ladder_rank` descending (the
  shipped ordering, not a knob).
- Reserved capital = `max_loss_per_contract × contracts`, held from entry
  session `t.grid[0]` through exit session `t.grid[days_held-1]` inclusive,
  released with realized P&L booked at exit.
- Delta-notional per position = `|delta| × 100 × contracts × entry_underlying`,
  computed at entry, constant for the position's life. `delta` is the row's
  signed NET per-spread delta (`simulate.py:496-501`; one market anchor leg +
  BS for the rest — decision-time, never drifting). Portfolio net = |Σ signed|;
  gross = Σ|·|; both reported.
- **PER_POSITION_CAP = 0.25 × equity** ($6,250) — just above the observed p75,
  bites the tail without reshaping the book (a cap below the median would be a
  different strategy, not a friction).
- **NET_CAP = 1.50 × equity** ($37,500) — binds on roughly the upper half of
  occupied sessions, which is the point.
- The $500 dollar stop is applied through the exact scaling identity: replay at
  `contracts × 2` under the frozen harness ($1,000 stop) and divide dollars by
  2; integrality asserted; calibrated at scale=1 against stored rows (G2).

**Arms (all reported, none adopted).**
- R (REJECT): a position breaching any cap at risk-sized contracts is skipped,
  logged with counterfactual R / R_dol. D (DOWNSIZE): contracts reduced to the
  largest integer satisfying every cap, then **re-replayed at the reduced
  size** (never rescaled arithmetically); 0 → reject.
- F1 (TAKE the 1-contract floor even when its max loss exceeds $500 — what
  production does) vs F2 (REFUSE those picks). Known before registration: F1 vs
  F2 divides 133/218 of the book; this is the study's central object.
- ARM H: the SHIPPED bear hedge sleeve (1/day, `|delta|` descending, ≤½ size)
  added to the constrained run — the only way net-vs-gross becomes measurable.

**Anti-tuning.** Per-position ∈ {0.15, 0.25, 0.40, ∞} ×
net ∈ {1.00, 1.50, 2.50, ∞}. The HEADLINE is the single pre-registered
(0.25, 1.50) cell, quoted first and alone. **No cap value may be adopted,
recommended, or carried into a conclusion on the basis of its P&L in this
grid.** The only admissible reading is qualitative monotonicity; a non-monotone
surface is evidence of a ledger bug, not an opportunity.

**Population.** PRIMARY = dense episodes: maximal runs of signal dates with no
internal gap > 5 trading sessions and ≥ 10 dates; the episode list prints
before any result. SECONDARY = the full sparse book, labelled as an
availability upper bound / concurrency lower bound; it may not carry a
conclusion alone. No annualised return, Sharpe, or time-to-recover may be
quoted anywhere in the write-up.

**Baselines.** B1 = same ladder, unconstrained, STORED contract counts and
stored outcomes — must reproduce the deployed-book line the 08-12 `vol_sleeve`
report printed on the same exports (**220 positions / 90 dates / $63,553**).
B2 = same ladder, unconstrained, $25k max-loss sizing. B1→B2 isolates
granularity; B2→constrained isolates the caps.

**Bar for a candidate.**
- A1 EDGE SURVIVAL — constrained mean R over taken positions > 0, 95%
  date-clustered CI excluding zero, positive every year present.
- A2 ATTRITION — constrained total $ ≥ 60% of B2 on the same dates.
- A3 NO BLOWUP — ledger never over-reserves (violation FAILS the run) and
  constrained max drawdown ≤ 25% of starting capital.
- A4 ATTRIBUTION — every rejection/downsize attributes to exactly ONE binding
  constraint (cash / per-pos delta / net delta / min-1 refusal / day-3 cap)
  and the counts sum exactly (self-check; mismatch FAILS the run).
- A5 STABILITY — constrained/B2 dollar ratio moves ≤ 15 points across both
  mandatory window cuts.
- A6 CREDIT SENSITIVITY — A1 must also hold on the debit-only subset (credit
  rows are admitted ungated by `book.py`).

**Gates (non-zero exit on failure).** G1 book calibration quoted
(`debit_calib`, `n_credit_ungated`). G2 replay identity: every deployed pick
re-replayed at stored contracts, scale=1, must match stored
`(exit_reason, days_held, round(R,4))` for calibrated debit rows. G3 ledger
self-check: at every session `cash + Σreserved == 25,000 + Σrealized-to-date`.
G4 selection identity: the unconstrained pick set equals `top_k_per_day(...)`
by set equality (proves no silent re-selection).

**Verdicts, worded now.** FEASIBLE = A1∧A2∧A3∧A5∧A6. FEASIBLE-BUT-DEGRADED =
A1∧A3 with A2 failing. NOT FEASIBLE AT $25k = A1 fails. On NOT FEASIBLE, and
only after the primary verdict prints, the report prints the smallest capital
in {25k, 35k, 50k} at which A1∧A2 pass — an operator note under the same
anti-tuning rule.
