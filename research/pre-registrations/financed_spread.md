## 2026-08-19 — `financed_spread`: PRE-REGISTRATION (written BEFORE the study was built or run)

**Question.** Holding the signal, the entry day and the exit rules fixed, does
wrapping a book debit vertical in a FINANCING credit position improve the
outcome? The operator's hypothesis is the classic one: sell premium against the
debit to cheapen the entry — either on the opposite side of spot (opposite-delta
credit), as a naked short leg, or as a same-direction credit vertical. This is a
STRUCTURE question (f3), the `bear_rewrap` shape: same signal, same dates, same
exits, different wrapper.

**What this is NOT.** It is not a selection study — no arm changes WHICH signals
are taken. It is not an exit study — every synthetic replays under the shipped
profiles. And it is not a sizing study, which is why sizing is pinned to the
production formula per variant with a fixed-contracts control printed alongside
(§Sizing). The `vol_sleeve` lesson is registered up front: synthesizing on the
engine's own signal dates can re-wrap the SAME exposure; a wrapper that clears
every R gate but correlates positively with the deployed sleeve is a RE-WRAP,
not a diversifier, and is recorded as such regardless of its ΔR (E3).

---

### Population and basis, fixed here

- Era: PRIMARY `--era v3` — `load_book(include_bs=False)`, proxy calibration
  gate ON, the 795-row / 118-date basis. SECONDARY = `current`, reported,
  carries nothing (34 backfill dates; most cells will power-stop). Never pooled.
- Population: two-leg single-expiry debit verticals only. Plan-time measurement
  (disclosed): 780/795 rows are two-leg; 0 rows are multi-expiry, so every
  financing leg shares the debit's expiry and `_defined_risk_bounds` stays
  applicable to bounded shapes.
- Entry day: the baseline row's own entry day (`entry_date_for` — first grid day
  ALL legs, financing legs included, are cached). Baseline and financed variant
  fill on the SAME day or the row is excluded and counted.

### Arms — four shapes × two strike offsets, frozen, no additions

For a bull_call debit (mirror for bear_put): "beyond the outer strike, OTM
direction" = calls ABOVE the highest leg strike; "the other side of spot" =
puts BELOW the lowest leg strike. Candidate strikes come from the ticker's
OBSERVED cached strike ladder — never an invented increment.

| shape | legs added | risk |
|---|---|---|
| **F0** strike-aligned control | the counterpart-mirror same-direction credit at the debit's OWN two strikes (zero scrape — mirrors are 100% cached) | defined |
| **F1** opposite-delta credit spread | short + long at the next two cached strikes beyond the outer strike, OTM direction | defined |
| **F2** naked short leg | short only, first cached strike beyond the outer strike | UNBOUNDED |
| **F3** same-direction financed vertical | credit spread on the other side of spot (bull_call + bull_put credit; bear_put + bear_call credit) | defined |

Strike-offset sensitivity frozen at TWO settings: offset 1 (nearest cached
strike beyond) and offset 2 (one further out). No third.

F0 is registered as the machinery pilot: it is buildable on essentially the
whole population before any scrape, it collapses algebraically to a
doubled-delta synthetic forward capped at ±(K2−K1), and it is a legitimate
answer to "same-direction financing." F0 runs FIRST; its report is published
whether or not the scrape ever completes.

### Pricing, sizing, exits — pinned

- Pricing: the `bear_rewrap` path verbatim by import (`leg_details`,
  `leg_series`, `entry_price_of`, `net_entry`, `net_marks` with the
  `_defined_risk_bounds` clamp, `synth_trade`, `reconstructs`). New financing
  legs are fetched into the SAME cache under the SAME filename convention.
- Degenerate-premium guard: a synthetic with |entry_net| < 0.10 is EXCLUDED and
  counted (Trade.denom = |entry_net|; a near-zero financed net makes R explode,
  and shrinking the debit is this structure's whole purpose).
- Sizing: the production `_size_contracts` logic ported verbatim — debit-signed
  nets on the premium×0.75 formula, credit-signed nets on structural max loss,
  UNBOUNDED (F2) at 1 contract per the production convention. A
  `--fixed-contracts` control (contracts held at the baseline's count) prints
  alongside so the sizing sensitivity is visible, not assumed away.
- Exits: assigned by the SIGN of the synthetic net entry — debit-signed → the
  shipped debit profile (incl. the bear-keyed `be_after 0.50` where the
  baseline row carries it), credit-signed → `CREDIT_PROD`. The debit/credit
  flip share is reported PER SHAPE: a shape that flips half its rows to the
  credit profile is changing the exit rule as well as the wrapper, and that
  must be visible before any ΔR is read.

### Unit and metric

Unit = the signal DATE (date-clustered everything). Metric = **within-row
paired ΔR** (financed minus baseline) on rows BOTH variants price, aggregated
by date, `boot_ci_paired_by_date`. **Dollars are never quoted on a
substitution** — contract counts differ by construction (the `bear_rewrap`
NOTE); $ prints only inside the sizing census.

### Exposure reads (pre-registered alongside ΔR, per shape)

- **E1 — Δ(net delta)** at the common entry day from cached per-leg `Delta`.
  Geometry check: F1 must reduce |net delta|, F0/F3 must increase it. A shape
  whose delta does not move as its geometry dictates is a BUILD BUG, not a
  finding, and fails the run.
- **E2 — Δ(net vega)** from cached per-leg `Vega`. Every financing shape sells
  an extra option and is structurally short vega; quantify it.
- **E3 — correlation with the deployed sleeve**: date-level correlation of the
  shape's mean R vs the deployed `top_k_per_day(ladder_rank, k=3)` sleeve's
  mean R, per year, ≥8 shared dates required. Registered reading: **positive
  correlation = RE-WRAP verdict regardless of ΔR.**

### Gates (non-zero exit on failure, in order)

- **G0 — POWER, runs FIRST.** Per shape × offset: constructible rows and dates.
  **< 25 dates OR < 60 rows → that cell is POWER-STOPPED**, printed with n,
  no criterion evaluated. Declared now; plan-time head start (disclosed):
  346/795 rows already have ≥2 cached calls above their highest strike,
  398/795 have ≥2 cached puts below their lowest, so F1/F3 may clear G0 even
  before the scrape; F0 clears on the whole population.
- **G1 — reconstruction.** `reconstructs()` on every candidate row (entry
  ±$0.005, per-day mark ±$0.01, ≥95% of priced days agree). Failures excluded
  from every cell and counted by reason; pass rate quoted.
- **G2 — clamp attribution.** F2 must be 100% UNclamped (`_defined_risk_bounds`
  → None on a naked short); F0/F1/F3 must be ~100% clamped. A mismatch means
  the leg set is wrong and fails the run.
- **G3 — sizing census.** Contract-count distribution per shape; count of rows
  at the 1-contract unbounded fallback.

### Bar to call a shape a CANDIDATE — the full conjunction

1. paired ΔR > 0, date-clustered bootstrap CI (BOOT_N=10000) excluding zero;
2. **every** LOO fold positive (read `min_gain`);
3. survives `protocol.window_cuts` AND the ex-BOTH-windows cut added by hand;
4. positive in every calendar year present in the shape's population;
5. right-signed on BOTH pricing tiers (real and tweak);
6. ≥25 affected dates (G0's floor, re-checked on the priced set);
7. **E3 ≤ 0** — the shape must not re-wrap the deployed exposure.

Failing any one is failing. Worst-decile cells print DESCRIPTIVELY with their n
and are marked NOT A CRITERION — 118 dates cannot power a worst-decile read
(the 2026-08-13 hedge-programme wall), and no criterion here requires one.

### Verdicts, worded now

- **CANDIDATE** (not a ship): a shape clears all seven → queues an
  independent-window confirmation. Nothing ships from a research-tier study.
- **RE-WRAP**: clears 1–6, fails 7 → "the financing does not diversify";
  recorded, thread closed for these dates (the `vol_sleeve` outcome).
- **NULL**: clears the CI but fails LOO / ex-BOTH / sign stability → window
  artifact, recorded (the `bear_rewrap` +0.085 outcome).
- **POWER-STOPPED**: G0 fails after the scrape → census published, no re-run
  on these dates.

### Anti-tuning

Shapes frozen at four, offsets at two. Exit profiles, sizing formula, caps and
the candidate population are NOT swept. Every shape × offset cell is reported
regardless of outcome. The scrape target derivation (2 strikes beyond each
side, observed ladder only) is fixed before any fetch; plan-time census
(disclosed): 2,522 target contracts, 925 already cached, 1,597 to fetch.

### Build notes (not part of the registration)

- Module `scripts/backtest_study/f3_structure/financed_spread.py`; run via
  `python -m scripts.backtest_study run financed_spread --era v3`.
- Scrape: `scripts/collector/fetch_financing_legs.py`, manifest
  `backtests/sweep_cache/financing_manifest.csv` — a SEPARATE file from
  `legs_manifest.csv` (calendar_hedge ARM S depends on that one).
- `bear_rewrap` is imported as a module (the `calendar_hedge` precedent), never
  refactored — its published cell means are pinned by `calendar_hedge`.
- New shared helper `scripts/backtest_study/lib/greeks.py` (per-leg greeks from
  the cache; missing leg → None, never 0) serves E1/E2 here and G-DELTA in
  `portfolio_delta`.
- `harness.py` untouched. Catalog + study-map entries required.

### Wording corrections (2026-08-19, at build time — labelled, not a re-registration)

Two registration bugs the build exposed, in the `selection_order` §Wording-
correction tradition: each is a statement the geometry makes unsatisfiable as
written, corrected here BEFORE the study has run, with no threshold, criterion,
or arm changed.

1. **G2 on F2.** "F2 must be 100% UNclamped" is true only of a naked short
   CALL (bull_call base). A naked short PUT (F2 on a bear_put base) is
   structurally bounded at S=0, so `_defined_risk_bounds` correctly clamps it —
   geometry, not a wrong leg set. G2's F2 clause is evaluated on the
   naked-short-CALL subset; the put-side clamp count prints beside it with this
   reason stated. Build smoke check: 0 clamped calls on the sampled rows (PASS
   as corrected).
2. **F0's offset axis is degenerate.** F0 sits at the debit's OWN strikes, so
   "four shapes × two strike offsets" yields seven cells, not eight — F0 is one
   cell. The G0 table prints it as `F0 own`.

Also recorded here for the census trail: the collector's implemented
target-derivation census reads **1,775 targets / 607 cached / 1,168 missing**
(93 tickers, 462 groups) against the plan-time estimate of 2,522/925/1,597.
The plan-time figure exceeded the rule's own 4-per-group cap and was an
estimate by a looser derivation; the RULE (2 nearest cached-ladder strikes
strictly beyond each side) is what was registered and is what the collector
implements. No target was added or removed after any outcome was seen.

## 2026-08-19 — AMENDMENT 1: ARM F4, diagonal financing (dated pre-registration,
## written AFTER the F0–F3 run and BEFORE F4 is built or run)

The 2026-08-19 run returned NULL on all seven same-expiry strike-offset cells
and closed them. The operator's intended financing is a DIFFERENT structure the
original arms never priced, registered here as a new commitment (the
macro_event_study amendment precedent): a SHORT-DATED, DELTA-TARGETED naked
short leg — premium sold "not to be reached", expiring while the debit thesis
is still developing. Nothing in this amendment reopens F0–F3 on these dates.

**F4 construction, frozen:**
- One short leg, the debit's own option type, ALWAYS strictly beyond the
  debit's furthest OTM leg (calls above the highest strike for a bull_call;
  puts below the lowest for a bear_put).
- **Expiry:** the nearest expiry in the ticker's cached expiry set that is
  ≥ 7 calendar days after entry AND ≤ ½ of the debit's DTE at entry. No expiry
  in that window → row excluded and counted (`no_near_expiry`).
- **Delta target, two cells:** |Δ| ∈ {0.10, 0.20} (F4-d10, F4-d20), measured
  from the scraped entry-day Delta. Candidate strikes = the 4 nearest
  cached-ladder strikes strictly beyond the outer leg (never an invented
  strike), scraped at the chosen near expiry; the pick is the candidate whose
  entry-day |Δ| is closest to target. Closest candidate off-target by > 0.10
  in |Δ| → row excluded and counted (`target_unreachable`).
- **Single tranche:** sold once at entry; after the near expiry the position
  is the plain debit (the short leg's mark contribution ends at its own
  expiry). No roll. A rolling campaign is a separate future registration.
- **Sizing/exits:** as the original registration — production sizing (naked
  short ⇒ the 1-contract unbounded convention), exits by sign of the synthetic
  net, `--fixed-contracts` control printed. The single-expiry
  `_defined_risk_bounds` clamp is INAPPLICABLE to a two-expiry synthetic; F4
  marks are clamped only on the post-near-expiry segment (where the position
  is the plain debit again) — G2's F4 clause is "unclamped while the short
  leg lives", with the segment boundary printed.
- **Gates and criteria:** identical to the original registration — G0 floor
  ≥25 dates / ≥60 rows per cell, G1 reconstruction on the baseline, G3 sizing
  census, E1/E2/E3 exposure reads (E1 geometry check for F4: |net delta| must
  DECREASE), and the same 7-part conjunction including E3 ≤ 0.
- **Scrape:** a new category in fetch_financing_legs.py's manifest
  (`fin_diag_<type>`), same resumable semantics; the target census prints in
  --dry-run before any fetch.

**Terminology note (applies to all future write-ups and new code):**
"POWER-STOPPED" is hereby read as **UNDERPOWERED — too few dates to judge;
census printed, nothing concluded**. Existing printed reports and the
registrations above keep the original token for traceability; new code prints
UNDERPOWERED.

## 2026-08-19 — AMENDMENT 2: F4 management cells (dated pre-registration, written
## BEFORE the F4 scrape and BEFORE any F4 cell has run)

Operator's actual practice, registered verbatim before any F4 number exists:
the financing leg is NOT held to expiry — it is bought back once it has earned
50% of the credit, "or at least $100", and stopped at 2× credit against.

**F4 management (applies to the new mgmt cells):**
- **Profit take, two parallel trigger bases** (the staged_exit twin-cut
  precedent; neither has precedence, both report side by side):
  `mgmt-pt50` — buy back at the first session whose mark ≤ 0.5 × entry credit;
  `mgmt-$100` — buy back at the first session where (credit − mark) × 100 ×
  contracts ≥ $100 for the tranche (at the simulated contract count; under the
  1-contract naked convention this is per-contract).
- **Loss stop, both mgmt bases:** buy back at the first session whose mark ≥
  2 × entry credit.
- **Residual:** a leg still open at its near expiry is bought back at its
  LAST REAL MARK — never dropped to zero. This costing change applies to ALL
  F4 cells INCLUDING the hold-to-expiry comparison cells, superseding
  amendment 1's drop-to-zero (which forgave assignment; the smoke sample
  carried 5/18 rows > $0.05 into the near expiry). The forgiven-value count
  still prints for comparability with the amendment-1 wording.
- All triggers evaluate on the leg's own cached daily marks; a missing mark on
  a trigger day defers to the next priced session (the harness carry
  convention). After any buyback the position is the plain debit.

**Cells:** {d10, d20} × {mgmt-pt50, mgmt-$100, hold} = six cells, same
underlying rows (no power cost per cell). Gates, E-reads, and the 7-part
conjunction are unchanged from the original registration and amendment 1; the
hold cells serve to attribute any effect to the management rule vs the
structure. No trigger value may be tuned after a number is seen; 0.50, $100,
and 2× are the operator's stated practice and are frozen here.

### Build notes to amendment 2 (2026-08-19 — labelled, not part of the registration)

- **Zero-greek sentinel guard.** Barchart writes sessions whose IV and every
  greek are literally 0 while the mark is real; read literally, a deep-ITM put
  quoted "0.00 delta" and sat inside the d10 tolerance. The candidate picker
  skips rows quoting no IV (`skip_greeks_absent`, counted on the page), and
  `lib/greeks.py` now returns None on such rows (regression-tested) — the
  None-never-0 invariant applied to the greek block. Amendment-1 smoke counts
  predate this guard.
- **Trigger scan starts the session AFTER the fill** — a trigger on the fill
  session would read an Open-vs-mark spread rather than decay. Build decision,
  stated on the page and pinned by a test.
- Known residual caveats, printed per cell: a stale last real mark on an
  illiquid leg is the buyback price the amendment's wording implies (not a
  price the market printed at expiry); a near expiry beyond the debit's
  120-day path cap leaves the leg open for the whole path
  (`open_at_grid_end`, 0 rows on the smoke sample); mean vs MEDIAN buyback
  cost both print because the naked short's tail dominates the mean.
