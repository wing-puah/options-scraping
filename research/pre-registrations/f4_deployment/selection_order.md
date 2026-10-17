## selection_order — does a different entry-side order of the same candidates spend the delta budget better?

<!-- outcome:start -->
> Latest outcome: on the registered v3 book, `POWER-STOPPED`: no arm powered, best 11 of 25 dates (2026-08-15). Later v4 runs, not the registered book, read `ORDERING-IS-NOISE` (2026-09-28) · [record](../../study-results/f4_deployment/selection_order.md).
<!-- outcome:end -->

_Registered 2026-08-14._

## The question

`account_sim` left one readable thread, and this study pulls it. Does a different, blind, entry-side ORDER of the same candidate set spend the binding delta budget better?

Three things `account_sim` established set it up:

- The binding constraint is delta exposure, not cash (`cash` binds ZERO times at both cap settings).
- The picks the net cap excludes outperform the picks it admits: meanR **+0.624 rejected vs +0.290 taken** at 0.25x/2.50x, **+0.431 vs +0.278** at 0.25x/1.50x.
- Loosening the cap roughly DOUBLED the gap (+0.153 → +0.333). So no cap value may be read off P&L: the grid is monotone 4/4 by construction.

What is readable is the **ordering**. The ladder-rank walk spends a scarce delta budget on earlier-ranked picks that underperform the ones it then excludes.

`account_sim`'s own follow-up (2) named this the pre-registerable item, and recorded the adverse-ordering read there as **post-hoc**. This registration makes a test of it admissible.

## What this study is not

It is not a selection study. Selection is closed: structure × regime × entry geometry, `score_total` decision-irrelevant, the ML search null across 15 cells, reopen on **new COLUMNS only**.

Tier MEMBERSHIP, the candidate universe, sizing, caps and exits are all frozen exactly as `account_sim` runs them. The only thing any arm changes is the sequence in which an already-eligible day's candidates are offered to the ledger.

## Population and basis, fixed here

- Book: `load_book(include_bs=False)`, proxy calibration gate ON. This is the frozen 795-row / 118-date basis. v4 rows are never pooled in. `--structure-universe` is NOT used.
- Config: `config/account-sim.yml` as committed, **compounding OFF** (the frozen, path-INDEPENDENT book). This study sweeps no cap, capital, risk-% or positions/day value. They are the account's friction model, not parameters.
- PRIMARY = the configured dense episodes. SECONDARY = full book, reported, carries nothing — same convention as `account_sim`.
- ARM H (the bear hedge sleeve) is OFF for every arm. It enters after the day's signal picks and cannot displace one. It is orthogonal to ordering and would only add variance.

## What it compares

The arms are frozen at six. None may be added after any result is seen.

Each arm is a `rank_fn` passed to `protocol.ordered_by_day`; higher sorts first. Every arm reads **entry-side fields only** (`delta`, `entry_underlying`, `max_loss_per_contract`, `tier`). Ties break on the existing `ladder_rank`, so the walk stays deterministic.

| Arm | Ordering | Role |
|---|---|---|
| **O0** | `ladder_rank` — tier, then `score_total` tie-break | baseline = today's production |
| **O1** | delta-notional ASCENDING, within tier | cheapest exposure first |
| **O2** | reserved-$ per unit delta-notional, DESCENDING, within tier | budget efficiency |
| **O3** | `\|delta\|` DESCENDING, within tier | transfer test of `hedge_sizing`'s D4 rule ("the losing trade is the cheap far-OTM one"), never yet run outside bear |
| **O1b** | delta-notional ASCENDING, TIER-BLIND across A∪B | admissible only because A vs B is statistically MERGED (+0.36 vs +0.37, p=.65, third validation); eligibility is unchanged, so this is an ordering change, not a tier change |
| **O4** | seeded random permutation within the day, 200 draws | the null band |

O4 decides the meaning of the others. **An arm must beat the random band, not merely beat O0.** If O0 itself sits inside the band, the adverse-ordering observation is an artifact of which picks the cap happened to exclude, and the thread closes.

## How it is judged

**Unit of observation = a contested date.** It is a session with ≥2 eligible candidates and ≥1 exclusion in `{day3_cap, net_delta, per_pos_delta}`. Uncontested dates are identical across arms by construction and are excluded from the paired test. Including them is the zero-inflation that failed `exit_switch_mech`'s LOO median gate; the corrected form is registered below.

**Metric = within-date paired difference vs O0** in mean R over the day's taken positions, the `hedge_sizing` D4 method. It cancels the date's return level.

Dollars print alongside and are a sanity check only. An ordering change alters which positions get sized, so $ is composition-dependent in the same way a structure substitution is. **Quote R.**

## Gates

Each gate exits non-zero on failure.

- **G0 — POWER PRE-CHECK, runs FIRST and blocks everything.** Print the contested-date census and, per arm, the number of dates whose pick set differs from O0. **Under 25 affected dates for an arm → that arm is POWER-STOPPED.** Its cells are not read and no criterion is evaluated on it. The entire hedge programme hit this wall (all 30 ARM S cells, H2 at n=6). It is declared before the count is known, not after.
- **G1 — calibration.** O0 must reproduce the current default `account_sim` run exactly: positions, dates, dollars, and G1's `220 / 90 / $63,553` book line. An ordering study whose baseline does not reproduce production is measuring its own bug.
- **G2 — blindness.** Every arm passes the `BlindRec` / `blind_records` probe: outcome keys raise, `LOOKAHEAD_ROW_COLUMNS` deleted from the row, resulting book identical to the sighted one. A rank function that peeks is worthless, because the study's point is a rule an agent could run live.
- **G3 — attribution.** Candidates partition exactly into taken + census buckets, per arm (the A4 identity). A mismatch FAILS the run.
- **G4 — no annualised figure, Sharpe, or time-to-recover anywhere.**
- **G5 — out-of-fold discipline.** In-sample tables are labelled as such. The only adoption-eligible numbers are LOO folds and `protocol.walk_forward_splits` TEST rows.

## Bar for a candidate

The unit judged here is an arm. It must clear the whole conjunction below, every item, not most of them. It is registered as the corrected gate from 2026-07-22, plus the `hedge_sizing` D4 standard that is the only precedent here that ever passed.

1. Paired mean gain vs O0 > 0 with **date-clustered bootstrap CI excluding zero** (`BOOT_N = 10000`).
2. **Median gain positive among AFFECTED dates** (not all dates) and **≥25 affected dates**.
3. **Every LOO fold positive.**
4. **Positive in every calendar year present in the arm's population.**
5. Holds on the SHIPPED exit config, not only a variant.
6. Survives `protocol.window_cuts` AND the **ex-BOTH-windows cut added by hand**. `window_cuts()` drops only one window at a time, and the vol_sleeve straddle died precisely in the gap that leaves.
7. **Exceeds the O4 random band** (above the 95th percentile of the 200 draws).

Failing any one is failing. No post-hoc relaxation, no arm added, no threshold moved after a number is seen.

## Verdicts, worded now

- **ORDERING-MATTERS** (candidate, NOT a ship): an arm clears all seven. It queues an independent-window confirmation. The ordering may then be proposed for `deployment-rules.md` as a tie-break within the deployed set.
- **ORDERING-IS-NOISE**: no arm separates from the O4 band. The adverse-ordering read was an artifact; record it and close the thread.
- **CAP-BOUND-NOT-ORDER-BOUND**: arms clear G0 but produce near-identical books. The cap excludes the same picks whatever the order. Ordering is not the lever; the constraint is the account.
- **POWER-STOPPED**: G0 fails. Census only, nothing read, no re-run on these dates.

## Anti-tuning

- Arms are frozen at six.
- Caps, capital, risk %, positions/day, `take_floor`, `downsize` and the exit profile are NOT swept. They come from config and are held at their committed values for every arm.
- No new columns.
- The random-control seed is fixed and printed.
- Every arm's result is reported regardless of outcome, including the ones that lose.

## What could ship

Nothing ships from this study, and the report must carry the reason.

**Standing caveat that must appear in the report.** The ladder is itself in-sample (fitted on this book), so an ordering evaluated on the same book is second-order in-sample. The only mitigations are that these are **mechanical entry-side rules with no fitted thresholds**, and that adoption requires out-of-fold survival. That caveat does not disappear if the numbers look good. It is why nothing ships from this study under any outcome.
