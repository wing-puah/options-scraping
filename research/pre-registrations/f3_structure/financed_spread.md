## financed_spread — does financing a debit vertical with a credit leg improve it?

<!-- outcome:start -->
> Latest outcome: PRIMARY v3 — `F4-d20 hold` `CANDIDATE`, the other 12 cells `NULL`, awaiting an independent window (2026-08-19). On v4: all 13 cells `NULL` (2026-09-28) · [record](../../study-results/f3_structure/financed_spread.md).
<!-- outcome:end -->

_Registered 2026-08-19._

## The question

Holding the signal, the entry day and the exit rules fixed, does wrapping a book debit vertical in a FINANCING credit position improve the outcome?

The operator's hypothesis is the classic one: sell premium against the debit to cheapen the entry. The premium can be sold on the opposite side of spot (opposite-delta credit), as a naked short leg, or as a same-direction credit vertical.

This is a STRUCTURE question (f3), the `bear_rewrap` shape: same signal, same dates, same exits, different wrapper.

## What this study is not

- **Not a selection study.** No arm changes WHICH signals are taken.
- **Not an exit study.** Every synthetic replays under the shipped profiles.
- **Not a sizing study.** Sizing is pinned to the production formula per variant.
- **Not a diversification claim taken on faith.** The `vol_sleeve` lesson is registered up front: synthesizing on the engine's own signal dates can re-wrap the SAME exposure. A wrapper that clears every R gate but correlates positively with the deployed sleeve is a RE-WRAP, not a diversifier. It is recorded as RE-WRAP regardless of its ΔR (E3).
- **Not evidence about a rolling financing campaign.** F4 sells once and does not roll. A rolling campaign is a separate future registration.
- **Not evidence about dollars across shapes.** Contract counts differ by construction.
- **Not evidence about multi-expiry or three-leg rows.** The study uses two-leg single-expiry debit verticals only.

## Population and basis, fixed here

- **Era.** PRIMARY is `--era v3`: `load_book(include_bs=False)`, proxy calibration gate ON, the 795-row / 118-date basis. SECONDARY is `current`. It is reported and carries nothing (34 backfill dates; most cells will power-stop). Eras are never pooled.
- **Rows.** Two-leg single-expiry debit verticals only.
- **Entry day.** The baseline row's own entry day (`entry_date_for`): the first grid day on which ALL legs, financing legs included, are cached. Baseline and financed variant fill on the SAME day, or the row is excluded and counted.
  - _Resolved at build (2026-10-20)._ `bear_rewrap.entry_date_for` now obeys production's entry window (`simulate.fresh_entry_date`, operator ruling 2026-10-01): a stale leg is no fill, a late leg inside the window moves the fill, a common day past the window is no fill. Every cell builds the same rows: a variant that filled late already failed `entry_day_mismatch`, and is now counted under `no_common_entry_day` instead.

### Plan-time observations, disclosed

Measured before any arm ran. No number here is a result.

- Plan-time measurement: 780 of 795 rows are two-leg. 0 rows are multi-expiry. So every financing leg shares the debit's expiry, and `_defined_risk_bounds` stays applicable to bounded shapes.
- Plan-time head start: 346 of 795 rows already have at least 2 cached calls above their highest strike. 398 of 795 have at least 2 cached puts below their lowest. So F1 and F3 may clear G0 even before the scrape. F0 clears on the whole population.

### Pricing, sizing, exits — pinned

- **Pricing.** The `bear_rewrap` path, verbatim by import: `leg_details`, `leg_series`, `entry_price_of`, `net_entry`, `net_marks` with the `_defined_risk_bounds` clamp, `synth_trade`, `reconstructs`. `bear_rewrap` is imported as a module and never refactored, because `hedge_structure` pins its published cell means. New financing legs are fetched into the SAME cache under the SAME filename convention.
  - `Resolved at build (2026-09-24)`: `bear_rewrap.py` has been edited only to follow production's pricer. The edits are the B5 zero-bid mark, the side-aware and `open_side` entry fills, and the junk-quote rule, each applied per row on its write-time basis. Production's shared entry and junk-mark functions in `scripts/backtest/simulate.py` are imported in place of restated copies: `open_print_allowed`, `entry_day_fill`, `carried_entry_fill`, `last_good_mark`, `junk_day_mark`. No gate, bar, arm or published cell mean changed meaning. The only output change is reconstruction on same-day entries, from 5 mismatches to 0 (1,154/1,159 → 1,159/1,159).
- **Degenerate-premium guard.** A synthetic with |entry_net| < 0.10 is EXCLUDED and counted. Trade.denom = |entry_net|, and a near-zero financed net makes R explode. Shrinking the debit is this structure's whole purpose.
- **Sizing.** The production `_size_contracts` logic, ported verbatim.
  - Debit-signed nets use the premium×0.75 formula.
  - Credit-signed nets use structural max loss.
  - UNBOUNDED (F2) takes 1 contract, the production convention.
  - A `--fixed-contracts` control (contracts held at the baseline's count) prints alongside, so the sizing sensitivity is visible.
- **Exits.** The SIGN of the synthetic net entry assigns them. Debit-signed rows get the shipped debit profile, including the bear-keyed `be_after 0.50` where the baseline row carries it. Credit-signed rows get `CREDIT_PROD`.
- **Flip share.** The debit/credit flip share is reported PER SHAPE. A shape that flips half its rows to the credit profile changes the exit rule as well as the wrapper. That must be visible before any ΔR is read.

## What it compares

Shapes F0–F3 were registered first and are frozen with no additions. F4 was registered later, after the F0–F3 run, as a DIFFERENT structure the original arms never priced.

For a bull_call debit (mirror for bear_put):

- "beyond the outer strike, OTM direction" means calls ABOVE the highest leg strike.
- "the other side of spot" means puts BELOW the lowest leg strike.
- Candidate strikes come from the ticker's OBSERVED cached strike ladder, never an invented increment.

| Shape | Legs added | Risk |
|---|---|---|
| **F0** strike-aligned control | The counterpart-mirror same-direction credit at the debit's OWN two strikes | defined |
| **F1** opposite-delta credit spread | Short + long at the next two cached strikes beyond the outer strike, OTM direction | defined |
| **F2** naked short leg | Short only, first cached strike beyond the outer strike | UNBOUNDED |
| **F3** same-direction financed vertical | Credit spread on the other side of spot (bull_call + bull_put credit; bear_put + bear_call credit) | defined |
| **F4** diagonal financing | One SHORT-DATED, DELTA-TARGETED naked short leg, sold once at entry | UNBOUNDED |

Strike-offset sensitivity for F1–F3 is frozen at TWO settings: offset 1 (nearest cached strike beyond) and offset 2 (one further out). No third.

### F0 — machinery pilot

F0 zero-scrapes (mirrors are 100% cached) and is buildable on essentially the whole population before any scrape. It collapses algebraically to a doubled-delta synthetic forward capped at ±(K2−K1). It answers "same-direction financing."
F0 runs FIRST. Its report is published whether or not the scrape ever completes.

F0 sits at the debit's OWN strikes, so its offset axis is degenerate. Four shapes × two strike offsets yields SEVEN cells, not eight. F0 is one cell, printed as `F0 own` in the G0 table.

### F4 — diagonal financing

Registered 2026-08-19, after the F0–F3 run and before F4 was built or run. It is a new commitment (the macro_event_study precedent): premium sold "not to be reached", expiring while the debit thesis is still developing. Nothing in this arm reopens F0–F3 on these dates.

Construction, frozen:

- **Leg.** One short leg, the debit's own option type, ALWAYS strictly beyond the debit's furthest OTM leg. For a bull_call, calls above the highest strike. For a bear_put, puts below the lowest.
- **Expiry.** The nearest expiry in the ticker's cached expiry set that is ≥ 7 calendar days after entry AND ≤ ½ of the debit's DTE at entry. If no expiry is in that window, the row is excluded and counted (`no_near_expiry`).
- **Delta target, two cells.** |Δ| ∈ {0.10, 0.20} (F4-d10, F4-d20), measured from the scraped entry-day Delta.
  - Candidate strikes are the 4 nearest cached-ladder strikes strictly beyond the outer leg, never an invented strike. They are scraped at the chosen near expiry.
  - The pick is the candidate whose entry-day |Δ| is closest to target.
  - If the closest candidate is off target by > 0.10 in |Δ|, the row is excluded and counted (`target_unreachable`).
  - The candidate picker skips rows quoting no IV (`skip_greeks_absent`, counted on the page). Barchart writes sessions whose IV and every greek are literally 0 while the mark is real. A literal zero would put a deep-ITM put inside the d10 tolerance.
- **Single tranche.** The leg is sold once at entry. After the near expiry the position is the plain debit. No roll.
- **Sizing and exits.** As the original registration: production sizing (naked short takes the 1-contract unbounded convention), exits by sign of the synthetic net, `--fixed-contracts` control printed.
- **Clamp.** The single-expiry `_defined_risk_bounds` clamp is INAPPLICABLE to a two-expiry synthetic. F4 marks are clamped only on the post-near-expiry segment, where the position is the plain debit again. The segment boundary is printed.
- **Gates and criteria.** Identical to the original registration: the G0 floor (≥25 dates / ≥60 rows per cell), G1 reconstruction on the baseline, the G3 sizing census, the E1/E2/E3 exposure reads and the 7-part conjunction with E3 ≤ 0. The E1 geometry check for F4 is that |net delta| must DECREASE.
- **Scrape.** A new category in fetch_financing_legs.py's manifest (`fin_diag_<type>`), with the same resumable semantics. The target census prints in --dry-run before any fetch.

### F4 management

The operator's actual practice, registered verbatim before any F4 number exists: the financing leg is NOT held to expiry. It is bought back once it has earned 50% of the credit, "or at least $100", and stopped at 2× credit against.

- **Profit take, two parallel trigger bases.** Neither has precedence. Both report side by side (the staged_exit twin-cut precedent).
  - `mgmt-pt50`: buy back at the first session whose mark ≤ 0.5 × entry credit.
  - `mgmt-$100`: buy back at the first session where (credit − mark) × 100 × contracts ≥ $100 for the tranche. This uses the simulated contract count. Under the 1-contract naked convention it is per-contract.
- **Loss stop, both mgmt bases.** Buy back at the first session whose mark ≥ 2 × entry credit.
- **Residual.** A leg still open at its near expiry is bought back at its LAST REAL MARK, never dropped to zero. This is the operative residual costing for ALL F4 cells, INCLUDING the hold-to-expiry comparison cells. The smoke sample carried 5/18 rows > $0.05 into the near expiry. A forgiven-value count prints as a COMPARISON figure only (what those residuals would cost if dropped to zero). It is not a costing rule.
- **Trigger days.** All triggers evaluate on the leg's own cached daily marks. The scan starts the session AFTER the fill, so a trigger never reads an Open-vs-mark spread on the fill session. A missing mark on a trigger day defers to the next priced session (the harness carry convention). After any buyback the position is the plain debit.
- **Frozen values.** No trigger value may be tuned after a number is seen. 0.50, $100 and 2× are the operator's stated practice.

### F4 cells

{d10, d20} × {mgmt-pt50, mgmt-$100, hold} gives six cells on the same underlying rows (no power cost per cell). Gates, E-reads and the 7-part conjunction are unchanged. The hold cells attribute any effect to the management rule versus the structure.

## How it is judged

**Unit.** The signal DATE. Everything is date-clustered.

**Metric.** Within-row paired ΔR (financed minus baseline) on rows BOTH variants price, aggregated by date with `boot_ci_paired_by_date`.

**Dollars.** Dollars are never quoted on a substitution, because contract counts differ by construction (the `bear_rewrap` NOTE). Dollars print only inside the sizing census.

### Exposure reads

Three exposure reads are pre-registered alongside ΔR, per shape.

- **E1 — Δ(net delta)** at the common entry day, from cached per-leg `Delta`.
  - F1 must reduce |net delta|. F0/F3 must increase it.
  - A shape whose delta does not move as its geometry dictates is a BUILD BUG, not a finding, and fails the run.
- **E2 — Δ(net vega)**, from cached per-leg `Vega`. Every financing shape sells an extra option and is structurally short vega. E2 quantifies it.
- **E3 — correlation with the deployed sleeve.** The date-level correlation of the shape's mean R with the deployed `top_k_per_day(ladder_rank, k=3)` sleeve's mean R, per year, with ≥ 8 shared dates required. Registered reading: **positive correlation = RE-WRAP verdict regardless of ΔR.**

## Gates

Four gates, evaluated in this order. Failure exits non-zero.

- **G0 — POWER, runs FIRST.** Per shape × offset: constructible rows and dates. **< 25 dates OR < 60 rows → that cell is POWER-STOPPED**, printed with n, no criterion evaluated.
- **G1 — reconstruction.** `reconstructs()` on every candidate row: entry ±$0.005, per-day mark ±$0.01, ≥ 95% of priced days agree. Failures are excluded from every cell and counted by reason. The pass rate is quoted.
- **G2 — clamp attribution.**
  - F2 must meet "100% UNclamped" (`_defined_risk_bounds` → None on a naked short). This is evaluated on the naked-short-CALL subset. A naked short PUT (F2 on a bear_put base) is structurally bounded at S=0, so the clamp there is correct geometry, not a wrong leg set. The put-side clamp count prints beside it with this reason stated.
  - F0/F1/F3 must be ~100% clamped.
  - F4 is unclamped while the short leg lives.
  - A mismatch means the leg set is wrong and fails the run.
  - Build smoke check: 0 clamped calls on the sampled rows (PASS as corrected).
- **G3 — sizing census.** The contract-count distribution per shape, and the count of rows at the 1-contract unbounded fallback.

## Bar for a candidate

A candidate must clear the full conjunction, all seven clauses:

1. Paired ΔR > 0, with the date-clustered bootstrap CI (BOOT_N=10000) excluding zero.
2. **Every** LOO fold positive (read `min_gain`).
3. Survives `protocol.window_cuts` AND the ex-BOTH-windows cut added by hand.
4. Positive in every calendar year present in the shape's population.
5. Right-signed on BOTH pricing tiers (real and tweak).
6. ≥ 25 affected dates (G0's floor, re-checked on the priced set).
7. **E3 ≤ 0**: the shape must not re-wrap the deployed exposure.

Failing any one clause is failing.

Worst-decile cells print DESCRIPTIVELY with their n and are marked NOT A CRITERION. 118 dates cannot power a worst-decile read (the 2026-08-13 hedge-programme wall), and no criterion here requires one.

## Verdicts, worded now

| Token | When | Consequence |
|---|---|---|
| `CANDIDATE` | A shape clears all seven clauses | Not a ship. Queues an independent-window confirmation |
| `RE-WRAP` | Clears clauses 1–6, fails clause 7 | "the financing does not diversify". Recorded. Thread closed for these dates (the `vol_sleeve` outcome) |
| `NULL` | Clears the CI but fails LOO, ex-BOTH or sign stability | Window artifact, recorded (the `bear_rewrap` +0.085 outcome) |
| `POWER-STOPPED` | G0 fails after the scrape | Census published, no re-run on these dates |

## Anti-tuning

- Shapes are frozen at four (F4 registered later, as above), and offsets at two.
- Exit profiles, the sizing formula, caps and the candidate population are NOT swept.
- Every shape × offset cell is reported regardless of outcome.
- The scrape target derivation (2 strikes beyond each side, observed ladder only) is fixed before any fetch.
- The plan-time census (disclosed) estimated 2,522 target contracts, 925 already cached, 1,597 to fetch. That figure exceeded the rule's own 4-per-group cap and came from a looser derivation.
- The RULE is what was registered: the 2 nearest cached-ladder strikes strictly beyond each side. The collector implements it, and its target-derivation census reads **1,775 targets / 607 cached / 1,168 missing** (93 tickers, 462 groups).
- No target was added or removed after any outcome was seen.

## What could ship

Nothing ships from a research-tier study. A `CANDIDATE` queues an independent-window confirmation first.
