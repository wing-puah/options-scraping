## ladder_overlay — does a rolled short-call ladder beat selling the spread, and would a naked put beat both?

_Registered 2026-09-10._

## Question

Holding the signal, the entry day and the core position fixed, does selling a
SHORTER-DATED short call against a long-dated bull call spread — and rolling
that short call as each one expires — beat simply running the spread to the
shipped [§5](../../../docs/deployment-rules.md#s5) exits?

The operator's real trades are mostly this shape: a long-dated debit vertical
(the CORE) plus a short call sold against it, usually after a gap-up or a
sustained rise, replaced when it expires. Four questions, in the order they
matter:

1. Is the ladder profitable versus closing the core at the shipped §5 exits?
2. When should the short call be sold — at entry, on a gap-up, on a sustained
   rise, or never — and does holding the core longer while rolling short calls
   beat the profit target, or does the short strike get breached too often?
3. How does the answer behave under a fixed-volatility scenario and across
   market-regime cuts?
4. Would a naked short put in place of the core have yielded more?

This is a STRUCTURE question (f3): same signal, same dates, a different wrapper
around the same core. The short call is part of the position — it finances the
core — rather than protection held alongside it, which is why this is f3 and
not f5.

### This is the roll registration `financed_spread` deferred

[`financed_spread`](financed_spread.md) ARM F4 sells ONE delta-targeted short
leg at a nearer expiry, at entry only. Its registration says, twice:

> **Single tranche:** sold once at entry; after the near expiry the position
> is the plain debit. No roll. A rolling campaign is a separate future
> registration.

This is that separate future registration. It does not reopen F0–F3, and it
does not re-run F4 on F4's own terms.

**ARM L-F4 is the replication anchor.** One cell here — L-F4 — reproduces
[`financed_spread` ARM F4](../../arm-index.md#financed_spread)-d20 hold exactly:
one tranche, sold at entry, never rolled, held to its near expiry. Gate G1b
requires this study's MARK SERIES to equal `financed_spread`'s F4-d20-hold
series to $0.01 per day on the shared rows. A mismatch is a build bug and fails
the run. That is what makes the rolling engine a demonstrated SUPERSET of the
single-tranche one rather than a second, differently-wrong implementation.

## What this is NOT

- **Not a selection study.** No arm changes WHICH signals are taken. Every cell
  runs on the same core rows.
- **Not an exit search.** The core exit is a registered two-value axis (X-SHIP,
  X-TEF) plus one sensitivity (X-EXP), frozen here before any outcome is read.
  Nothing sweeps profit targets, stops or time-exit fractions; that is
  `exit_drawdown`'s territory and it came back UNDERPOWERED there.
- **Not a sizing study.** Contracts are pinned to the baseline core's
  production count in every cell, so no cell can win on size.
- **Not a hedging study.** A short call above the core sells premium; it does
  not protect the book. `hedge_portfolio` and `hedge_structure` own protection.
- **Not a re-run of `financed_spread` F0–F3.** Those seven same-expiry cells
  returned NULL on v3 and are closed on those dates. L-F4 is the only cell that
  touches F4's ground, and it is there as a machinery check, not as a third
  attempt at F4-d20's unconfirmed v3 candidate.
- **Not a diversification claim taken on faith.** `financed_spread` F3 printed
  the **RE-WRAP** token on the v4 re-run: a same-direction financed vertical
  that cleared six of seven criteria and failed only E3. A ladder that clears
  every R gate but correlates positively with the deployed sleeve is the same
  exposure again, and is recorded as RE-WRAP regardless of its
  [ΔR](../../glossary.md#r).

## Definitions

### Tranche

One short option sold against the core: its leg, the grid day it opened, the
per-contract credit received, the grid day it closed, the per-contract closing
cost, the closing reason, and whether it was breached. A campaign is an ordered
list of tranches over one core's grid. At most one tranche is live at a time —
the overlay ratio is 1:1 with the core, which is the operator's practice.

### Breach

The underlying's CLOSE reaches the live tranche's short strike: `close ≥ K` for
a call tranche, `close ≤ K` for a put tranche, on the core ticker's own OHLC
bars, on any day the tranche is live. Breach is a state, not an exit — under
the PRIMARY breach rule (BHOLD) nothing is done about it, and the census in G4
is how its cost is read.

### Roll window

The window `financed_spread.near_expiry_for` already defines, anchored on the
ROLL DAY rather than on entry: an eligible expiry `e` satisfies
`roll_day + 7 calendar days ≤ e ≤ roll_day + ½ × remaining core DTE`, where
remaining core DTE is `(core expiry − roll_day).days`. For the first tranche
the roll day IS the entry day, so slot 0's window is F4's window unchanged;
later slots re-measure both ends from their own roll day, because a window with
one end fixed at entry would widen without limit as the core ages.

### Campaign structure

A tranche slot opens on the first core grid day on or after its trigger day
where the picked contract has a REAL cached row — never a carried mark. Under
R1 the next slot's trigger day is the first grid day after the previous
tranche's expiry. The campaign stops when no expiry fits the roll window or the
core's grid ends.

### MODEL tier

Every leg repriced by `scripts/backtest/helpers.py::_bs_price` instead of from
the cache, at the leg's ENTRY-DAY cache IV/100 held constant for the whole
path, with the underlying taken from the OHLC close. Printed under a `[MODEL]`
header. It is a sensitivity, never evidence: MODEL rows are never pooled with
cache-priced rows, and a MODEL row reaching a criterion is a BUILD ERROR that
fails the run.

## Dependencies

Three things must land before a full run is possible, and the study prints
`AWAITING SCRAPE` until they have:

- `scripts/backtest_study/lib/ladder_targets.py` — the one owner of "which
  contracts does a campaign owe a core", imported by both the collector and the
  campaign engine so the scrape targets and the simulation can never disagree.
- `scripts/collector/fetch_ladder_legs.py` — resumable collector, manifest
  `backtests/sweep_cache/ladder_manifest.csv`, categories `ladder_call_t0`,
  `ladder_call_roll`, `ladder_put_short`, `ladder_put_core`. Its `--dry-run`
  census is pasted into Anti-tuning below BEFORE the first fetch.
- `scripts/backtest_study/lib/overlay_campaign.py` — the roll-capable campaign
  composed AROUND the frozen harness. `lib/harness.py` is not edited.

`python3 scripts/backup_research_caches.py push` runs before and after every
scrape session, because `scripts/backtest/shared/history.py` unlinks a shallow
cache file before refetching and once lost 178 files that way.

## Population and basis, fixed here

- **Era.** PRIMARY is era **v4**: `load_book(include_bs=False)` on the current
  exports, real and tweak pricing tiers carried separately, `bs_options_hist`
  rows excluded by policy. A `--era v3` companion run is reported for
  replication and carries nothing on its own. **The two eras are never
  pooled** — v4's `score_total` scale is not v3's, and the ladder question is
  read on v4.
- **Cores.** `bull_call_spread` two-leg single-expiry rows only. A three-leg
  row, a multi-expiry row, or a bear structure is not a core here and is
  excluded and counted. The short overlay is a CALL above the core's high
  strike in every ladder cell, so restricting to bull cores keeps the geometry
  one thing.
- **Entry day.** `bear_rewrap.entry_date_for(rec["t"].legs, rec["t"].grid)` —
  the baseline row's own fill day. Every cell for a given core fills on the
  SAME day; a core with no common entry day is excluded and counted.
- **Grid and horizon.** The harness `Trade.grid`: weekday days from the signal
  date to `min(core expiry, 120-day` [path cap](../../glossary.md#path-cap)`)`.
  A core longer than 120 days is TRUNCATED at the cap, not extended.

### Pricing, sizing, exits — pinned

Nothing in this subsection may change after a number is seen.

- **Pricing path.** The `bear_rewrap` path verbatim by import: `leg_details`,
  `leg_series`, `entry_price_of`, `net_entry`, `reconstructs`. Near-expiry and
  candidate machinery by import from `financed_spread`: `near_expiry_for`,
  `cached_ticker_expiries`, `cached_calls`, the `DIAG_*` constants. Shared
  helpers by import: `scripts/backtest/helpers.py::_price_asof`,
  `_defined_risk_bounds`, `_bs_price`, `_max_loss_per_unit`;
  `lib/greeks.py::leg_greek`; `lib/underlying.py::load_bars`.
- **Strike pick.** `financed_spread.build_f4`'s rule, unchanged: candidates are
  the 4 nearest CACHED strikes strictly beyond the core's outer leg at the
  chosen expiry — never an invented strike — and the pick is the candidate
  whose scraped entry-day |Δ| is closest to target, excluded and counted when
  the closest is off-target by more than the F4 tolerance. The zero-filled
  greek sentinel is detected on **IV**, not on Delta: a row quoting no IV has
  no measured delta and is skipped, because a missing greek is None and never
  0.0.
- **Denominator.** Every ladder cell's [R](../../glossary.md#r) denominator is
  the **CORE debit** (`entry_net` = the core spread's own net). Tranche credits
  enter the MARK series as live or realized value; they are never folded into
  the entry net. This is a deliberate departure from F4, which folds the
  entry-day credit into `entry_net`, and it is what makes ΔR like-for-like
  across trigger arms — a T-GAP tranche sold on day 12 cannot be in the entry
  net of a position filled on day 0. Because R's denominator differs from F4's,
  **G1b pins the MARK series, not R.**
- **Naked-put denominator.** The N cells replace the core, so their R
  denominator is the core's MAX-LOSS DOLLARS (`_max_loss_per_unit` on the core
  leg set), which keeps ΔR against the same baseline comparable.
- **Contracts.** Every cell, including the naked-put cells, runs at the
  BASELINE CORE's production contract count — the `--fixed-contracts` control
  of `financed_spread` made the default here. Overlay ratio 1:1. No cell can
  beat another on size. The production 1-contract convention for an unbounded
  naked short prints as a CENSUS LINE in G3, not as a cell.
- **Settlement.** A tranche still open at its own expiry settles at its LAST
  REAL MARK (`financed_spread` amendment 2's precedent), never dropped to zero.
  The single exception: a BREACHED tranche with no cached mark within 3
  sessions of its expiry settles at INTRINSIC, and every such row is counted
  and printed (`settle_intrinsic`) beside the `settle_mark` count. A breached
  short that stops printing is exactly the row whose stale mark would forgive
  assignment.
- **Breach costing.** The core does NOT cap the net. A short call above the
  core's high strike is uncovered above its own strike, so `_defined_risk_bounds`
  is applied to the CORE ONLY, and only on days with no live tranche. While a
  tranche is live the mark series is UNCLAMPED. The share of exits taken by the
  harness [`dollar_stop`](../../glossary.md#dollar_stop) prints per cell,
  because that stop truncates exactly the tail this study is measuring.
- **Cost model.** `config/backtest.yml::commission_per_contract` and
  `slippage_frac_of_spread` are charged on EVERY tranche open and close, in
  addition to the core's own entry and exit. Both GROSS and NET figures print
  for every cell. Both knobs default to 0 in the shipped config; the run states
  the values it used, and a criterion is read on the NET series.
- **Core exits.** Three values, two of them PRIMARY:
  `X-SHIP` — the shipped §5 debit profile applied to the campaign net;
  `X-TEF` — no profit target, hold to the §5 time exit;
  `X-EXP` — hold to the 120-day path cap (SENSITIVITY only).

## Plan-time observations, disclosed

Measured read-only on 2026-09-10, before any cell was built or any outcome
column was read. These are plan-time MEASUREMENTS of the population, not
expected figures, and no gate compares against them.

| Export | bull_call rows | median core DTE | rows ≥ 60 DTE |
|---|---|---|---|
| `BacktestResults` (real + tweak) | 203 | 81 | 132 |
| `BacktestProxy` (real + tweak, bs excluded) | 562 | 150 | not measured at plan time |

The long-dated question is therefore answerable on this book, bounded by the
120-day path cap. Nothing else was read.

## Arms

Three groups: the PRIMARY ladder cells, the naked-put cells, and SENSITIVITY.
Only PRIMARY and the naked-put cells may earn a verdict. Every label below is
indexed in [`arm-index.md`](../../arm-index.md#ladder_overlay).

Axis vocabulary, used in every table below:

| Axis | Values |
|---|---|
| trigger | `T0` at entry · `TGAP` gap-up · `TRUN` sustained rise · `TNEVER` no tranche |
| roll | `R0` one tranche only · `R1` roll each slot |
| breach | `BHOLD` do nothing · `BBUY` buy back at that close's mark · `BUP` buy back and sell the next expiry's target-delta strike on the next grid day |
| delta | the tranche's per-contract absolute delta target |
| core exit | `X-SHIP` · `X-TEF` · `X-EXP` |

### Triggers, frozen

- **T0** — sell at the core's entry day.
- **T-GAP** — the session whose OPEN ≥ **1.015 × the prior close**, on the core
  ticker's own OHLC bars.
- **T-RUN** — the session whose CLOSE ≥ **1.04 × the entry-day close** AND
  which is the third of **3 consecutive higher closes**.
- **T-NEVER** — no tranche is ever sold.

Both T-GAP and T-RUN fire **at most once per empty tranche slot**, and the
tranche is sold on the **NEXT grid day** after the trigger day — never on the
trigger session itself, whose close is the same quote the trigger read. If the
picked contract has no real cached row that day, the slot opens on the first
later grid day where it does; the slot never opens on a carried mark.

### Expiry candidates

At each roll day the candidate expiries are those inside the roll window. The
COLLECTOR derives them from the ticker's cached expiry set UNION the standard
third-Friday monthlies, and fetches the 2 nearest eligible ones per slot, so a
monthly the cache has never seen can still become available. The STUDY reads
only what the cache holds AFTER the scrape — it never invents an expiry, and a
contract Barchart would not serve is a failed fetch, counted, not a gap filled
by a neighbour.

### PRIMARY — 8 ladder cells

All at |Δ| 0.20, BHOLD, call tranches, real and tweak tiers reported
separately.

| cell | trigger | roll | breach | delta | core exit |
|---|---|---|---|---|---|
| `L-BASE` | TNEVER | — | — | — | X-SHIP |
| `L-F4` | T0 | R0 | BHOLD | 0.20 | X-SHIP |
| `L-T0` | T0 | R1 | BHOLD | 0.20 | X-SHIP |
| `L-GAP` | TGAP | R1 | BHOLD | 0.20 | X-SHIP |
| `L-RUN` | TRUN | R1 | BHOLD | 0.20 | X-SHIP |
| `L-T0-TEF` | T0 | R1 | BHOLD | 0.20 | X-TEF |
| `L-GAP-TEF` | TGAP | R1 | BHOLD | 0.20 | X-TEF |
| `L-RUN-TEF` | TRUN | R1 | BHOLD | 0.20 | X-TEF |

`L-BASE` is the baseline every ΔR is paired against: the core alone, run to the
shipped §5 exits. `L-F4` is the G1b replication anchor and is not a candidate
in its own right. The TEF cells answer question 2's second half — does holding
the core longer while rolling short calls beat taking the profit target.

### Naked-put cells — 2

Both REPLACE the core rather than wrap it, and both are paired against the same
`L-BASE`.

| cell | trigger | roll | breach | delta | core exit |
|---|---|---|---|---|---|
| `N-CORE` | T0 | R0 | BHOLD | struck at the core's LONG strike, core expiry | n/a — the put is the position |
| `N-ROLL` | T0 | R1 | BHOLD | 0.30 | n/a — the put is the position |

`N-CORE` is a short put at the core's own long strike and expiry, which
`fetch_counterpart_history` has mostly cached already. `N-ROLL` is a
short-dated put rolled on the same slot schedule as the ladder cells, struck by
the |Δ| 0.30 target from the cached ladder below spot. Breach for a put is
`close ≤ K`. Both are UNBOUNDED below the strike and are the reason G3 carries
a margin census.

### SENSITIVITY

Printed with n, never a criterion, never pooled with PRIMARY.

| cell | trigger | roll | breach | delta | core exit |
|---|---|---|---|---|---|
| `S-D30` | T0 | R1 | BHOLD | 0.30 | X-SHIP |
| `S-BBUY` | T0 | R1 | BBUY | 0.20 | X-SHIP |
| `S-BUP` | T0 | R1 | BUP | 0.20 | X-SHIP |
| `S-XEXP` | T0 | R1 | BHOLD | 0.20 | X-EXP |
| `S-GAP103` | TGAP at 1.03 | R1 | BHOLD | 0.20 | X-SHIP |
| `S-DTE60` | T0 | R1 | BHOLD | 0.20 | X-SHIP, cores ≥ 60 DTE only |
| `S-MODEL` ×{1.00, 0.75, 1.25} | T0 | R1 | BHOLD | 0.20 | X-SHIP, `[MODEL]` tier |

### The fixed-volatility question, answered two ways

Question 3 splits into one sensitivity and one piece of evidence, and they are
kept apart on purpose.

- **`[MODEL]` tier — sensitivity.** `S-MODEL` reprices every leg with
  `_bs_price` at the leg's entry-day cache IV/100 held CONSTANT, scaled by
  ×1.00, ×0.75 and ×1.25, with the underlying from the OHLC close. It answers
  "what would this campaign have paid if volatility had not moved". It is
  printed under a `[MODEL]` header, is never pooled with cache-priced rows, and
  a MODEL row that reaches a criterion fails the run as a build error.
- **Regime cut — evidence.** The PRIMARY cells are additionally cut on
  `mech_cell` and on the book's `L-VOL` / `H-VOL` regime columns. This IS
  evidence: it is the same cache-priced series, split by a column the book
  already carries. **G0 is re-applied inside every cut**, so an underpowered
  cut prints its n and no statistic.

## Unit and metric

Unit = the signal **DATE**; everything is date-clustered. Metric = **within-row
paired ΔR** — the cell minus `L-BASE` on rows BOTH price — aggregated by date
through `protocol.boot_ci_paired_by_date`
([paired CI](../../glossary.md#paired-ci), BOOT_N = 10000).

Supporting reads, all from `lib/protocol.py`: `loo_by_date`
([LOO](../../glossary.md#loo--leave-one-date-out)), `window_cuts` plus the
ex-BOTH-windows cut added by hand, and `by_year`.

**Dollars are never quoted on a substitution.** Contract counts and structures
differ across cells by construction; `$` appears only inside the sizing and
margin censuses. Every cell quotes R.

### Exposure reads

Three reads print alongside ΔR for every PRIMARY and naked-put cell.

- **E1 — Δ(net delta)** at the common entry day, from cached per-leg `Delta`.
  Geometry check: a short call above the core must make net delta MORE
  NEGATIVE. A cell whose delta moves the other way is a BUILD BUG, not a
  finding, and fails the run.
- **E2 — Δ(net vega)** from cached per-leg `Vega`. Every ladder cell sells an
  extra option and is structurally SHORT vega; quantify it rather than assume
  it.

_Resolved at build (2026-09-10; recorded 2026-09-16)._ A trigger cell (`TGAP`, `TRUN`) holds no
tranche on the common entry day, so its entry-day Δ is 0 by construction. The
E1 geometry gate is applied to such a cell at its FIRST SALE DAY, printed in
the column beside the entry-day read; T0 cells are gated at entry as written.
The naked-put cells replace the core rather than wrap it (a short put is long
delta), so E1 and E2 print their direction for them and are not gated.
- **E3 — correlation with the deployed sleeve.** Date-level correlation of the
  cell's mean R against the deployed
  [`top_k_per_day`](../../glossary.md#top-kday)`(`[`ladder_rank`](../../glossary.md#ladder_rank)`, k=3)`
  sleeve's mean R, per year, **≥ 8 shared dates required**. Registered reading:
  **positive correlation = RE-WRAP, regardless of ΔR.**

## Gates

Evaluated in this order. A gate failure exits non-zero.

- **G0 — POWER, runs FIRST.** Per cell, and again inside every regime cut:
  constructible rows and dates. **< 25 dates OR < 60 rows → the cell is
  UNDERPOWERED**, printed with its n, no criterion evaluated. No cell may be
  rescued by lowering this floor.
- **G1 — reconstruction.** `reconstructs()` on every candidate CORE (entry
  ±$0.005, per-day mark ±$0.01, ≥95% of priced days agree). Failures are
  excluded from every cell, counted by reason, and the pass rate is quoted.
- **G1b — F4 identity.** `L-F4`'s per-day MARK series must equal
  `financed_spread` F4-d20-hold's series to **$0.01 per day on the shared
  rows**. This proves the rolling engine is a superset of the single-tranche
  one. A mismatch FAILS THE RUN — it is never reported as a difference of
  method. R is deliberately NOT compared, because this study's denominator is
  the core debit and F4's is the financed net.

  _Resolved at build (2026-09-10; recorded 2026-09-16)._ "The shared rows" are grid days on or
  after the common entry day, on cores where F4 priced a leg and the campaign
  sold its tranche on that same day. Rows F4 never had a leg for (`no_f4_leg`),
  rows F4 excluded and the campaign sold (`campaign_sold_f4_excluded`), rows
  the campaign opened after entry (`opened_after_entry`), and pre-fill grid
  days are each listed separately with their count and never averaged in.
  None of them is a pass; the tolerance applies to the matched rows only.
- **G2 — clamp attribution.** Every ladder cell must be **100% UNCLAMPED on
  days with a live tranche** (`_defined_risk_bounds` returns None on a
  two-expiry leg set by design) and clamped on core-only days. The segment
  boundaries print. A clamped live-tranche day means the leg set is wrong and
  fails the run.
- **G3 — sizing and margin census.** Contract-count distribution per cell;
  count of rows that would sit at the production 1-contract unbounded fallback.
  For the naked-put cells a reg-T MARGIN PROXY prints per row at entry:

  `margin ≈ [ max(0.20 × S − max(0, S − K), 0.10 × K) + credit ] × 100` per contract

  with `S` the entry-day underlying close and `K` the short strike. **Caveat,
  registered:** this is a proxy. Real margin is broker-set, is often higher,
  and EXPANDS while the position is losing — exactly when the account can least
  fund it. No criterion reads this number; it exists so a positive naked-put
  ΔR cannot be read as free.
- **G4 — breach census.** Per cell: tranches sold, share breached, the
  `settle_mark` vs `settle_intrinsic` split, mean and worst breach cost in R,
  and the share of exits taken by `dollar_stop`. This census is what criterion
  8 is read against.

### Exposure gates

- **E1** — net delta must become more negative (geometry, above).
- **E2** — net vega short, quantified.
- **E3** — correlation against the deployed top-3 sleeve, **≥ 8 shared dates**
  required; fewer shared dates means E3 is NOT EVALUABLE and the cell cannot be
  a CANDIDATE.

## Bar for a candidate

A candidate must clear the full conjunction — all eight. Criteria 1–7 are
`financed_spread`'s seven, verbatim.

1. paired ΔR > 0, date-clustered bootstrap CI (BOOT_N=10000) excluding zero;
2. **every** LOO fold positive (read `min_gain`);
3. survives `protocol.window_cuts` AND the ex-BOTH-windows cut added by hand;
4. positive in every calendar year present in the shape's population;
5. right-signed on BOTH pricing tiers (real and tweak);
6. ≥25 affected dates (G0's floor, re-checked on the priced set);
7. **E3 ≤ 0** — the shape must not re-wrap the deployed exposure;
8. **right-signed under breach-stress** — the cell stays positive when INTRINSIC
   is paid on every breached tranche instead of its settlement mark.

Failing any one is failing. Criterion 8 is computed from G4's census on the
same rows: it is a re-costing of the recorded campaign, not a different
campaign.

Worst-decile cells print DESCRIPTIVELY with their n and are marked NOT A
CRITERION. No criterion here requires one.

## Verdicts, worded now

- **CANDIDATE** — a cell clears all eight. **This is not a ship.** It queues an
  independent-window confirmation. Nothing ships from a research-tier study.
- **RE-WRAP** — clears 1–6 and 8, fails 7. The ladder makes money by holding
  more of the same exposure. Recorded; the thread closes for these dates. This
  is what `financed_spread` F3 printed on v4.
- **NULL** — clears the CI but fails LOO, the ex-BOTH cut, or sign stability. A
  window artifact; recorded.

  _Resolved at build (2026-09-10; recorded 2026-09-16)._ `verdict_of()` makes NULL the total
  default, so it also covers: a CI that includes zero or lies wholly below it;
  a failure of criterion 5 or 6; an E3 that is NOT EVALUABLE; and the corner
  where 1–6 pass and both 7 and 8 fail. There is no CONTRARY token. A cell that
  loses with a CI clear of zero prints NULL and the write-up states the sign
  in words.
- **UNDERPOWERED** — G0 fails for the cell (or for a regime cut). Census
  published, no re-run on these dates, nothing concluded.
- **BREACH-DOMINATED** — criteria 1–7 pass and **8 flips the sign**. The
  campaign's edge is the tail it did not pay for. Recorded as its own outcome,
  never softened into CANDIDATE.
- **AWAITING SCRAPE** — the contracts a cell needs are not yet cached. The run
  exits 0, prints the census, and evaluates no criterion.

## Anti-tuning

Everything below is frozen by this file and may not be changed after any
outcome is seen.

- **Trigger thresholds:** T-GAP 1.015 × prior close; T-RUN 1.04 × entry close
  with 3 consecutive higher closes. The single alternative, T-GAP at 1.03, is
  registered as a SENSITIVITY cell and cannot become the headline.
- **Delta targets:** 0.20 PRIMARY for calls, 0.30 for `N-ROLL`, 0.30 as the one
  registered call sensitivity. No third.
- **Strike and expiry counts:** 4 nearest cached strikes beyond the outer leg,
  2 nearest eligible expiries per slot. The roll window is
  `near_expiry_for`'s, unchanged.
- **Exit profiles:** X-SHIP is the shipped §5 debit profile as written;
  X-TEF drops only the profit target; X-EXP is a sensitivity. No knob inside a
  profile is swept.
- **Cost knobs:** whatever `config/backtest.yml` carries at run time, charged
  identically in every cell, with the values printed in the report header.
- **Reporting:** every PRIMARY and naked-put cell is reported with its n and a
  verdict token regardless of outcome. No cell is dropped for being
  uninteresting.
- The scrape target derivation is fixed before any fetch, and no target is
  added or removed after any outcome is seen.

_Collector dry-run census, pasted 2026-09-10 before the first fetch
(`python3 scripts/collector/fetch_ladder_legs.py --dry-run`, era v4, 447
bull_call_spread cores, 44 with no eligible expiry at any slot):_

| category | targets | cached | missing |
|---|---|---|---|
| `ladder_call_t0` | 2,390 | 243 | 2,147 |
| `ladder_call_roll` | 3,833 | 419 | 3,414 |
| `ladder_put_core` | 377 | 132 | 245 |
| `ladder_put_short` | 6,547 | 851 | 5,696 |
| **all** | **13,147** | **1,645** | **11,502** |

The plan-time estimate was ~5,000 fetches; the live number is 11,502 and is
recorded as printed, not adjusted. Fetch order: the two call categories and
`ladder_put_core` first, `ladder_put_short` last, so the ladder cells can be
read before the naked-put arm fills.

## What this cannot answer

Six limits, stated before any number exists.

- **The power of T-GAP and T-RUN.** Both triggers subset the book hard, and
  `hedge_timing` already found a streak rule untestable on this population —
  its strict 4–5-day down-run trigger had **2 book dates** and the
  [`hedge_timing` ARM H0](../../arm-index.md#hedge_timing) power census stopped
  every arm on it. Expect `L-RUN` UNDERPOWERED, and possibly `L-GAP` too. An
  UNDERPOWERED trigger cell says nothing about the trigger.
- **Long cores beyond 120 days.** The harness path cap truncates them. The
  proxy book's median bull_call DTE is 150, so a large part of the long-dated
  population is being read on its first 120 days only. No cell may be described
  as "the full life of a long-dated core".
- **Whether RE-WRAP is avoidable.** RE-WRAP is the MODAL EXPECTED outcome:
  `financed_spread` F3 already printed it for a same-direction financed
  vertical on this book, and a short call over a long call is the same
  direction again. A RE-WRAP verdict here is a confirmation of that pattern,
  not a new finding about ladders.
- **Early assignment.** A short call assigned over an ex-dividend date is
  unmodelled. The direction is known: costs are UNDERSTATED, so every ladder
  cell's ΔR is optimistic by an unmeasured amount. Criterion 8's breach-stress
  is a partial, not a complete, answer to this.
- **Cache-fill survivorship.** A core survives into a cell only when its
  tranche contracts were served and cached. That biases the surviving
  population toward liquid names, and the bias runs the same way in every cell,
  so ΔR is protected but the LEVEL of any cell is not a claim about the whole
  book.
- **Naked-put capital.** The margin figure is a reg-T proxy on a proxy
  denominator. This study cannot say whether the operator's account could have
  carried `N-CORE` or `N-ROLL` at the registered contract count, and it does
  not try.

## Ship criteria

Nothing ships from this study. The maximum admissible outcome is a CANDIDATE
cell that queues an independent-window confirmation. No §5 exit, no deployment
rule and no card behaviour changes on this file's evidence, and a RE-WRAP or
BREACH-DOMINATED cell closes its own thread for these dates.

## Build notes

*Not part of the registration — implementation and operational record.*

- Module `scripts/backtest_study/f3_structure/ladder_overlay.py`; run via
  `python3 -m scripts.backtest_study run ladder_overlay`, `--era v3` for the
  companion.
- Engine `scripts/backtest_study/lib/overlay_campaign.py`: `Tranche`,
  `CampaignSpec`, the `PriceSource` protocol with `CachePrices` and
  `ModelPrices`, `trigger_days`, `sell_tranche`, `run_campaign`,
  `campaign_net_marks`, `campaign_trade`. The synthetic `Trade`'s leg string
  carries the CORE legs only, as in `f4_synth_trade`, so the harness does not
  truncate the core's path window to a tranche's expiry.
- Targets `scripts/backtest_study/lib/ladder_targets.py`, shared with the
  collector, so the scrape and the simulation cannot disagree about what a core
  is owed.
- `lib/harness.py` is untouched. `financed_spread.py` and `bear_rewrap.py` are
  imported, never refactored — their published cell means are pinned by other
  studies.
- Tests: `tests/test_overlay_campaign.py` and `tests/test_ladder_legs.py`, on
  hand fixtures, following `tests/test_financed_spread_f4.py`'s cache-fixture
  pattern. A test pins `eligible_expiries(...)[0] == near_expiry_for(...)`.
- Catalog entry in `scripts/study_map/catalog.py` is required or
  `tests/test_study_map.py` fails; `research/arm-index.md`,
  `research/study-map.md` and `research/glossary.md` gain their lines in the
  same change, and the write-up goes to `research/current.md` after the run.
- The pre-scrape run must print `AWAITING SCRAPE` and exit 0.
