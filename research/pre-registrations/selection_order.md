## 2026-08-14 — `selection_order`: PRE-REGISTRATION (written BEFORE the study was built or run)

**Question.** `account_sim` established that the binding constraint is delta
exposure, not cash (`cash` binds ZERO times at both cap settings), and that the
picks the net cap excludes outperform the picks it admits: meanR **+0.624
rejected vs +0.290 taken** at 0.25x/2.50x, **+0.431 vs +0.278** at 0.25x/1.50x.
Loosening the cap roughly DOUBLED the gap (+0.153 → +0.333), which is why no cap
value may be read off P&L — the grid is monotone 4/4 by construction. What is
readable is the **ordering**: the ladder-rank walk spends a scarce delta budget
on earlier-ranked picks that underperform the ones it then excludes. This study
asks whether a different, blind, entry-side ORDER of the same candidate set
spends that budget better.

`account_sim`'s own follow-up (2) named this the pre-registerable item, and
recorded the adverse-ordering read there as **post-hoc**. This registration is
what makes a test of it admissible.

**What this is NOT.** It is not a selection study. Selection is closed —
structure × regime × entry geometry, `score_total` decision-irrelevant, the ML
search null across 15 cells, reopen on **new COLUMNS only**. Tier MEMBERSHIP,
the candidate universe, sizing, caps and exits are all frozen exactly as
`account_sim` runs them. The only thing any arm changes is the sequence in which
an already-eligible day's candidates are offered to the ledger.

---

### Population and basis, fixed here

- Book: `load_book(include_bs=False)`, proxy calibration gate ON — the frozen
  795-row / 118-date basis. v4 rows never pooled in. `--structure-universe` is
  NOT used.
- Config: `config/account-sim.yml` as committed, **compounding OFF** (the frozen,
  path-INDEPENDENT book). No cap, capital, risk-%, or positions/day value is
  swept by this study; they are the account's friction model, not parameters.
- PRIMARY = the configured dense episodes. SECONDARY = full book, reported,
  carries nothing — same convention as `account_sim`.
- ARM H (the bear hedge sleeve) is OFF for every arm. It enters after the day's
  signal picks and cannot displace one, so it is orthogonal to ordering and would
  only add variance.

### Arms — frozen at six, no additions after any result is seen

Each arm is a `rank_fn` passed to `protocol.ordered_by_day`; higher sorts first.
Every arm reads **entry-side fields only** (`delta`, `entry_underlying`,
`max_loss_per_contract`, `tier`) and ties break on the existing `ladder_rank`
so the walk stays deterministic.

| arm | ordering | rationale |
|---|---|---|
| **O0** | `ladder_rank` — tier, then `score_total` tie-break | baseline = today's production |
| **O1** | delta-notional ASCENDING, within tier | cheapest exposure first fits more picks per unit of the binding budget |
| **O2** | reserved-$ per unit delta-notional, DESCENDING, within tier | budget efficiency: most risk-budget deployed per unit of the scarce resource |
| **O3** | `\|delta\|` DESCENDING, within tier | transfer test of `bear_deploy`'s D4 rule ("the losing trade is the cheap far-OTM one"), never yet run outside bear |
| **O1b** | delta-notional ASCENDING, TIER-BLIND across A∪B | admissible only because A vs B is statistically MERGED (+0.36 vs +0.37, p=.65, third validation) — eligibility is unchanged, so this is an ordering change, not a tier change |
| **O4** | seeded random permutation within the day, 200 draws | the null band. If O0 sits inside it, ordering is noise |

O4 is the arm that decides the meaning of the others. The registered reading is
explicit: **an arm must beat the random band, not merely beat O0.** If O0 itself
sits inside the band, the adverse-ordering observation is an artifact of which
picks the cap happened to exclude, and the thread closes.

### Unit and metric

Unit of observation = **a contested date** — a session with ≥2 eligible
candidates and ≥1 exclusion in `{day3_cap, net_delta, per_pos_delta}`. Uncontested
dates are identical across arms by construction and are excluded from the paired
test (including them is the zero-inflation that failed `exit_switch_mech`'s LOO
median gate; the corrected form is registered below).

Metric = **within-date paired difference vs O0** in mean R over the day's taken
positions, the `bear_deploy` D4 method — it cancels the date's return level.
Dollars print alongside and are a sanity check only: an ordering change alters
which positions get sized, so $ is composition-dependent in the same way a
structure substitution is. **Quote R.**

### Gates (non-zero exit on failure)

- **G0 — POWER PRE-CHECK, runs FIRST and blocks everything.** Print the contested-date
  census and, per arm, the number of dates whose pick set differs from O0.
  **Under 25 affected dates for an arm → that arm is POWER-STOPPED**, its cells
  are not read, and no criterion is evaluated on it. This is the wall the entire
  hedge programme hit (all 30 ARM S cells, H2 at n=6); it is declared before the
  count is known, not after.
- **G1 — calibration.** O0 must reproduce the current default `account_sim` run
  exactly (positions, dates, dollars, and G1's `220 / 90 / $63,553` book line).
  An ordering study whose baseline does not reproduce production is measuring its
  own bug.
- **G2 — blindness.** Every arm passes the `BlindRec` / `blind_records` probe:
  outcome keys raise, `LOOKAHEAD_ROW_COLUMNS` deleted from the row, resulting
  book identical to the sighted one. A rank function that peeks is worthless, and
  the whole point of this study is a rule an agent could run live.
- **G3 — attribution.** Candidates partition exactly into taken + census buckets,
  per arm (the A4 identity; a mismatch FAILS the run).
- **G4 — no annualised figure, Sharpe, or time-to-recover anywhere.**
- **G5 — out-of-fold discipline.** In-sample tables are labelled as such. The only
  adoption-eligible numbers are LOO folds and `protocol.walk_forward_splits`
  TEST rows.

### Bar to call an arm a CANDIDATE — the full conjunction, all of it

Registered as the corrected gate from 2026-07-22, plus the `bear_deploy` D4
standard that is the only precedent here that ever passed:

1. paired mean gain vs O0 > 0 with **date-clustered bootstrap CI excluding zero**
   (`BOOT_N = 10000`);
2. **median gain positive among AFFECTED dates** (not all dates) and **≥25
   affected dates**;
3. **every LOO fold positive**;
4. **positive in every calendar year present in the arm's population**
   [wording corrected 2026-08-14 — see "Wording correction" below];
5. holds on the SHIPPED exit config, not only a variant;
6. survives `protocol.window_cuts` AND the **ex-BOTH-windows cut added by hand** —
   `window_cuts()` drops only one window at a time, and the vol_sleeve straddle
   died precisely in the gap that leaves;
7. **exceeds the O4 random band** (above the 95th percentile of the 200 draws).

Failing any one is failing. No post-hoc relaxation, no arm added, no threshold
moved after a number is seen.

### Verdicts, worded now

- **ORDERING-MATTERS** (candidate, NOT a ship): an arm clears all seven. Queues an
  independent-window confirmation; the ordering may then be proposed for
  `deployment-rules.md` as a tie-break within the deployed set.
- **ORDERING-IS-NOISE**: no arm separates from the O4 band → the adverse-ordering
  read was an artifact; record it and close the thread.
- **CAP-BOUND-NOT-ORDER-BOUND**: arms clear G0 but produce near-identical books —
  the cap excludes the same picks whatever the order. Ordering is not the lever;
  the constraint is the account.
- **POWER-STOPPED**: G0 fails → census only, nothing read, no re-run on these
  dates.

### Anti-tuning

Arms frozen at six. Caps, capital, risk %, positions/day, `take_floor`,
`downsize` and the exit profile are NOT swept — they come from config and are
held at their committed values for every arm. No new columns. Random-control
seed fixed and printed. Every arm's result is reported regardless of outcome,
including the ones that lose.

### Standing caveat that must appear in the report

The ladder is itself in-sample (fitted on this book), so an ordering evaluated on
the same book is second-order in-sample. The only mitigations are that these are
**mechanical entry-side rules with no fitted thresholds**, and that adoption
requires out-of-fold survival. That caveat does not disappear if the numbers look
good, and it is why nothing ships from this study under any outcome.

### Wording correction (2026-08-14, post-run — labelled, not a re-registration)

Criterion (4) originally read "positive in all three years." The PRIMARY
population spans only **two** calendar years (2025, 2026), which makes that
literal wording unsatisfiable by construction — a registration bug the build
exposed, not a finding about the arms. The implementation was already correct
— `selection_order.py` evaluates "every year present positive" and prints an
inline DISCLOSURE saying so whenever the population spans fewer than three
years — so this corrects the WORDING above to match the implementation:
**"positive in every calendar year present in the arm's population."** No
threshold, no measured number, and no arm's PASS/FAIL under criterion (4)
moves. `selection_order` is POWER-STOPPED and closed on this book; this
correction does not reopen it or license a re-run on these dates.

### Build notes (not part of the registration)

- Module `scripts/backtest_study/f4_deployment/selection_order.py`; run via
  `python -m scripts.backtest_study run selection_order`; report to
  `backtests/study_output/selection_order-latest.txt`.
- A `scripts/study_map/catalog.py` entry with a hand-written VERDICT is REQUIRED —
  a study with no entry fails the test suite.
- `harness.py` is not touched. `protocol.top_k_per_day` is not touched (every
  recorded conclusion rests on it; `ordered_by_day` is the stateful door and the
  two are pinned equal by test).
- Noted while reading `simulate()`: the `day3_cap`, `unsizable` and `ruined`
  census buckets append a `None` counterfactual, so the existing "rejected picks
  returned +X" description is computed only over the `net_delta` /
  `per_pos_delta` / `min1_refusal` exclusions. This study does not need those
  counterfactuals — each arm simulates its own book — but the gap should be
  recorded rather than rediscovered.
