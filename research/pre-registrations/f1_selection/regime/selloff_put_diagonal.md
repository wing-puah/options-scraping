## selloff_put_diagonal — on a SPY sell-off, does a near put plus a long-dated call diagonal pay?

<!-- outcome:start -->
> Latest outcome: `NOT BUILT — AWAITING SCRAPE` on the first run, 2026-11-01. 153 primary trades await a fetch (177 contracts), so no arm is graded.
<!-- outcome:end -->

_Drafted 2026-11-01, before any module exists or any outcome of this rule is printed._

**STATUS: ACCEPTED BY DEFAULT 2026-11-01 on the drafter's recommended defaults, under the
2026-10-09 policy. One choice, OD1 (which way the diagonal points), was the operator's idea to
define. A change before the first outcome prints is an edit; after that, it is a NEW
registration.**

_Resolved at build (2026-11-01):_ the operator confirmed the call diagonal as the primary.
`ARM PD` stays a printed secondary.

## The question

The operator's idea: when the market sells off, buy a near-dated put to catch the rest of a fast
drop, and at the same time open a longer-dated diagonal at the lower price. This study turns that
into one mechanical SPY rule and asks three things, graded separately because they can disagree.

| Object | Question | Comparator |
|---|---|---|
| `ARM K` vs zero | Does the package make money after a sell-off trigger, net of commission? | none |
| `ARM K` vs `ARM C` | Is a sell-off a better time to open it than a calm week? | the same package on calm weeks |
| put contribution | Does the put leg add to the diagonal, or only cost? | `ARM K` minus its diagonal alone, same trigger |

**Why now.** The operator is moving to mechanical rules (2026-10-23), and the pieces of this idea
have each been tried on the analysis book, never together and never on a fixed trigger:

| Prior study | What it found |
|---|---|
| [`index_bear_hedge`](../../f5_hedging/index_bear_hedge.md) | Index bear spreads cut drawdown in all 5 v4 sell-offs, but lost $43.9k net between them. Forward read still open. |
| [`bear_rewrap`](../../../arm-index.md#bear_rewrap) `long_put` | A plain long put instead of the bear spread: dead, 0 of 5 criteria. |
| `bear_rewrap` `long_diag` | The diagonal wrap: 2 of 5 criteria after the late-fill fix; CI crosses zero. |
| [`hedge_timing`](../../f5_hedging/hedge_timing.md) | No mechanical down-run trigger picks a better day for the hedge: 0 survivors. |
| [`dip_buy`](dip_buy.md) | Tier A/B picks on dip dates: forward read still open. |

The difference here: the put is never held between sell-offs, so the carry that sank
`index_bear_hedge` does not exist. The put only has to earn its keep on the days after a trigger.

## What this study is not

- **Not a hedge of the book.** No analysis row is read. The package is a standalone trade.
- **Not a trigger search.** The trigger is `index_bear_hedge`'s E-DD5 threshold, fixed and hashed
  on 2026-10-07. No other threshold is graded.
- **Not a geometry search.** One geometry is graded. The others in
  [Parameters printed both ways](#parameters-printed-both-ways) print and never promote.
- **Not a ship decision.** See [What could ship](#what-could-ship).

## The rule, fixed here

| Element | PRIMARY value |
|---|---|
| Underlying | SPY only |
| Trigger | a session whose SPY close is at least 5% below its 63-session high, while the rule is not armed |
| Re-arm | the rule disarms on the first close back above −2% from the 63-session high |
| Decision and fill | decide on trigger day D's close; every leg fills on D+1 at the closing mid |
| Put leg | 1 long put, listed strike nearest spot × 1.00, standard monthly expiry nearest 30 DTE |
| Diagonal, long leg | 1 long call, listed strike nearest spot × 0.90, standard monthly expiry nearest 365 DTE among those listed by D's close, at least 270 DTE, no upper cap |
| Diagonal, short leg | 1 short call, listed strike nearest spot × 1.05, the same expiry as the put |
| Put exit | first of: the rule disarms (close above −2%), 75% of the put's DTE elapsed, or its expiry |
| Diagonal horizon | three short-call cycles. At each short expiry, buy it back at that close and sell the next one by the same rule |
| Diagonal exit | close both legs at the third short expiry's close |
| Size | 1 contract per leg; the graded unit is [R](../../../glossary.md#r) of the package |

_Resolved at build (2026-11-01):_ spot is the SPY close in the session tables on the decision
day. That is D for the entry legs and the roll day for each new short. Each strike is the
nearest listed one by that day's close, walked as `mechanical_baseline` walks it, for calls
and puts alike.

_Resolved at build (2026-11-01):_ "nearest 30 DTE" and "nearest 365 DTE" count from the
planned entry day, ties to the earlier expiry, as in `mechanical_baseline`. The next short at
a roll is the monthly nearest 30 DTE from the roll day, at that day's close × 1.05.

_Resolved at build (2026-11-01):_ the put's exit is read from the session after its entry
day. "The rule disarms" is a disarm since D. A trigger trade whose rule disarms on the entry
day exits its put the next session. An `ARM C` put exits on a disarm only if the rule arms and
disarms during its life.

_Resolved at build (2026-11-01):_ "75% of the put's DTE elapsed" is the first session at least
`int(0.75 × DTE)` calendar days after the entry day, the harness's time-exit count.

### OD1 — which way the diagonal points

This is the one choice that changes what the idea is.

- **PRIMARY: call diagonal (bullish, a poor man's covered call).** The put pays for the drop, and
  the diagonal buys the recovery at a lower price. This reads "buying longer-out diagonals" as
  adding long exposure in the dip, which is how the operator's own book is built.
- **Secondary, printed and never graded: put diagonal (bearish).** Long put at spot × 1.00 on the
  365-DTE monthly, short put at spot × 0.95 on the near monthly. With the near put on top, the
  whole package is a bet on further falls.

_Resolved at build (2026-11-01):_ the operator confirmed the call diagonal; `ARM PD` stays a
printed secondary. The arms do not swap.

### Why these values

- **The trigger** reuses `index_bear_hedge.EPISODE_DEFS["E-DD5"]` thresholds (−5% trigger, −2%
  recovery, 63-session high), imported and checked against `EPISODE_DEFS_SHA256`. The armed and
  disarmed states make it knowable on the day: no peak or trough is used.
- **The put** is ATM and near-dated because the payoff sought is the next few weeks of the drop.
  A 30-DTE monthly is the shortest expiry the cache reliably holds; weeklies are not used, as in
  `mechanical_baseline`.
- **The diagonal** has its long leg deep enough in the money (spot × 0.90) to hold most of the
  delta, and far enough out (365 DTE) that three short cycles leave over 270 days on it. The short
  leg sits at spot × 1.05, the width `mechanical_benchmark` already prices.
- **Three cycles** is about 63 sessions, the median trigger-to-recovery span in the episodes
  below. It is fixed now; 1 and 6 cycles print as parameters.
- **D+1 closing mid on every leg** is the [one-clock rule](../../../current.md#2026-10-23--every-leg-of-an-entry-now-fills-at-the-same-close).

### Pricing and costs

- Production's shared pricing functions are imported, never copied: the entry fill, the
  junk-quote rule, the zero-bid mark and the defined-risk clamp, as `mechanical_baseline` imports
  them. No model price anywhere.
- A short-call roll prices both sides at the expiry day's closing mid; an expiring short is marked
  at its intrinsic value when its quote fails the junk-quote rule.
- Commission is $0.65 per contract per leg per side, slippage 0, because the operator fills at mid.
  R is net of commission; gross prints beside it.
- R is the package's net P&L over its entry debit (put debit plus diagonal net debit).

_Resolved at build (2026-11-01):_ the three entry legs fill on ONE day. It is production's
entry day: the first day from the planned entry, inside production's five-session window, on
which every leg has a closing quote (`common_entry_day`). A package with no such day drops.
A new short at a roll sells on the roll day's close, or on the first day in that window after
it with a closing quote.

_Resolved at build (2026-11-01):_ the expiry-day rule covers every expiring leg (the near put
too), and a missing row on expiry day is marked at intrinsic value like a junk one. Any other
exit, the put before expiry and the long call, uses production's daily mark. That is the
series mark, with `junk_day_mark` on a junk quote.

_Resolved at build (2026-11-01):_ the defined-risk clamp is called on each leg set and binds
on none. A diagonal spans two expiries and the put is one leg, so
`_defined_risk_bounds` returns None for all of them; the run prints that count.

_Resolved at build (2026-11-01):_ production's entry refusals apply to the package: a junk
bought leg with no bid, and legs priced against strike order. A put priced at zero and a
diagonal priced to a credit also drop. A drop at any leg drops the whole package. `ARM K`,
`ARM K-diag` and `ARM K-put` are therefore always the same trades.

_Resolved at build (2026-11-01):_ commission is counted per leg-side traded: the put in and
out, the long in and out, and each short sold and bought back. A short bought back at zero is
still charged. With 2 puts per diagonal, the put leg counts twice.

### Degenerate and missing trades

- A nearest listable strike or expiry that is not cached and not skip-listed makes the trade
  `AWAITING FETCH`. It is never built on the next cached contract. While any primary trade awaits,
  no primary outcome prints.
- If the long call's nearest-365 expiry is not listed on D+1, the trade uses the listed monthly
  with at least 270 DTE whose DTE is nearest 365, and the substitution is counted. Below 270 DTE
  the trade drops.
- Every drop and substitution is printed by year.

_Resolved at build (2026-11-01):_ the operator approved longer-dated calls. The long leg is the
monthly listed by D's close, with at least 270 DTE, whose DTE is nearest 365, with no upper cap.
A January LEAP 400 to 700 days out is allowed when it is the nearest listed to 365. A tie goes
to the nearer expiry. The count printed is "long expiry ≠ nearest-365 monthly".

_Resolved at build (2026-11-01):_ "listed on D+1" is read as listed by D's close, when the
rule decides. An expiry is listed when a cached contract of it has a row on or before D. It
is not listed when contracts of it are cached and none has such a row. With nothing cached,
it is not listed only when the skip-list holds evidence against the standard-grid strike
nearest the target; otherwise that strike is fetched.

_Resolved at build (2026-11-01):_ a trade whose diagonal closes after the calendar's last
session is `OPEN`. It is counted by year, not graded and not fetched. The in-sample `ARM C`
set therefore grows until the last in-sample calm week's diagonal closes, in December 2026.

_Resolved at build (2026-11-01), operator:_ the in-sample set is frozen so it cannot grow.

- An in-sample trade is graded only if its diagonal closes on or before 2026-10-22, the data
  end at registration (`CLOSE_BY`). A later one is `OPEN`, reason `closes_after_freeze`.
- The cut is by calendar date, set before any option price was read, so it cannot favour
  either arm. No trigger trade is affected.
- The primary `ARM C` is 147 of the 154 calm weeks; the 6-cycle cell loses 20.
- Once the 7 left-out weeks close and are fetched (collector `--scope all`), a CHECK line
  prints `ARM K` minus all 154 calm weeks beside the graded figure. It flags a change of sign.
  It is never graded.

## Arms

| Arm | Entry dates | Legs | Role |
|---|---|---|---|
| `ARM K` | every trigger day | put + call diagonal | **graded** |
| `ARM K-diag` | every trigger day | call diagonal alone | component; feeds the put-contribution comparison |
| `ARM K-put` | every trigger day | put alone | component; printed |
| `ARM C` | first session of each ISO week, rule disarmed, SPY within 2% of its 63-session high | put + call diagonal | **graded comparator** |
| `ARM H` | every trigger day | SPY shares, same dollars as `ARM K`'s debit, same horizon | graded as a secondary: does the option wrap beat owning the dip? |
| `ARM PD` | every trigger day | put + put diagonal | OD1 secondary; graded as a secondary |

_Resolved at build (2026-11-01):_ `ARM C` enters on the first session of each ISO week that is
disarmed and within 2% of the 63-session high. Read literally (the week's first session
only), the rule gives 135 weeks. This reading reproduces the 154 the drafter counted, so it
is the one the count was made under.

_Resolved at build (2026-11-01):_ `ARM H` buys SPY at the planned entry day's close and sells
at the diagonal's exit close. It pays no commission. Under the −8% trigger cell, `ARM C`'s
"disarmed" is that cell's own rule.

## Population and windows

| Window | Signal dates | Role |
|---|---|---|
| in-sample | 2022-03-01 → 2026-09-22 | PROVISIONAL grade. Starts with the SPY option cache; ends before the holdout seal |
| forward | 2026-11-01 → | Confirmation, see [The forward read](#the-forward-read) |

- **The seal.** [`holdout_seal`](../../f4_deployment/holdout_seal.md) withholds signal dates from
  2026-09-23. This study reads no analysis row, so prompt eras do not apply; it still stops the
  in-sample window before the seal, as `mechanical_baseline` does.
- **Inputs.** The SPY option cache, plus `backtests/mech_regime/spy_base_rate_daily.csv` extended
  by `spy_vix_daily_full.csv` for the trigger.

## Plan-time observations, disclosed

The drafter read the SPY closes, not any option price. Every figure here is market data, but the
"trigger → trough" column is most of the put leg's outcome, so the in-sample read is
contaminated by hindsight in both the operator's idea and this geometry.

| # | Trigger day | Episode peak | Episode trough | Peak → trough | Trigger → trough |
|---|---|---|---|---|---|
| 1 | 2022-08-26 | 2022-08-16 | 2022-10-12 | −17.0% | −12.0% |
| 2 | 2022-12-16 | 2022-11-30 | 2022-12-28 | −7.6% | −1.7% |
| 3 | 2023-03-01 | 2023-02-02 | 2023-03-13 | −7.5% | −2.4% |
| 4 | 2023-09-21 | 2023-07-31 | 2023-10-27 | −10.3% | −4.8% |
| 5 | 2024-04-19 | 2024-03-27 | 2024-04-19 | −5.4% | 0.0% |
| 6 | 2024-08-02 | 2024-07-16 | 2024-08-05 | −8.4% | −2.9% |
| 7 | 2025-03-04 | 2025-02-19 | 2025-04-08 | −19.0% | −13.9% |
| 8 | 2025-11-20 | 2025-10-29 | 2025-11-20 | −5.1% | 0.0% |
| 9 | 2026-03-19 | 2026-01-27 | 2026-03-30 | −9.1% | −4.2% |

- `ARM C` has 154 calm weeks in the in-sample window.
- The 2022-01 episode triggered on 2022-01-19, before the option cache starts, so it is out.
- **Power.** Nine trigger trades is thin. Two of them (#1 and #7) carry most of the fall, and two
  triggered on the trough itself. The likeliest outcome, written down now, is `NULL` on `ARM K`
  vs zero, with the sign set by #1 and #7.
- On 2026-10-22 SPY closed 1.9% below its 63-session high, so the rule is disarmed and no forward
  trigger is live.

## Criteria

All CIs are bootstrap CI95s, 10,000 draws, seeded, resampling trigger days (for `ARM C`, weeks).

1. **C0 POWER.** `ARM K` needs at least 8 built trigger trades in-sample; `ARM C` at least 60
   weeks. Below a floor the object prints `UNDERPOWERED`. No floor may be lowered.
2. **C1 SIGN.** The mean (net R; or the difference for a comparison) has a CI95 excluding zero.
   For `ARM K` vs `ARM C` the CI comes from resampling each arm independently.
3. **C2 LOO.** Every leave-one-trigger-out fold keeps the full-sample sign.
4. **C3 BIG-EPISODE CUT.** The sign holds with triggers #1 and #7 both removed. This is the
   `lessons.md` rule that one window can carry a whole effect.

   _Resolved at build (2026-11-01):_ for `ARM K` vs `ARM C`, C2 and C3 drop trigger days only;
   the calm arm stays whole. The put contribution is paired on the same trigger days.
5. **C4 OVERFITTING.** PBO by CSCV (`lib/pbo.py`) across the trade-level cells in
   [Parameters printed both ways](#parameters-printed-both-ways), blocked by calendar quarter. It
   prints every run and never grades the primary, which was fixed before any cell was seen. A PBO
   of 0.5 or more forbids promoting any non-primary cell in a later registration.

   _Resolved at build (2026-11-01):_ the cells are the ten rows below, the primary included.
   Each period is one calendar quarter of signal dates, so there are 19. One zero quarter is
   padded at the head to make the count even, and each block is one quarter. The statistic is
   `ARM K`'s summed net R per quarter (`total_metric`), because most quarters hold no trigger.

## Parameters printed both ways

Each prints `ARM K`, `ARM C` and the put contribution. It is graded only as a secondary object, under [Secondary grades](#secondary-grades), and never yields a primary verdict.

| Parameter | PRIMARY | Printed |
|---|---|---|
| Diagonal direction (OD1) | call | put (`ARM PD`) |
| Diagonal horizon | 3 cycles | 1, 6 |
| Put strike | spot × 1.00 | spot × 0.95 |
| Puts per diagonal | 1 | 0 (`ARM K-diag`), 2 |
| Trigger | −5% | −8% (`E-DD8` threshold) |
| Fill | D+1 close | D close |
| Put leg | naked put | bear put spread, short leg at spot × 0.95 |

_Resolved at build (2026-11-01):_ the operator's put leg is usually a put spread or a naked put.
The naked ATM put stays primary. The `Put leg` cell buys the put at the listed strike nearest
spot × 1.00 and sells one at the listed strike nearest spot × 0.95, on the same near monthly
(nearest 30 DTE). It exits like the naked put: disarm, 75% of DTE, or expiry. It uses the same
pricing functions. The defined-risk clamp applies to this vertical and is allowed to bind; the
run prints how many values it moved. R uses the spread's net debit and four leg-sides per put.

## Verdicts, worded now

| Object | Token | When |
|---|---|---|
| `ARM K` vs zero | `PAYS` | C0–C3 hold, mean positive |
| | `LOSES` | C1 holds with the mean negative |
| | `NULL` | powered, C1 fails |
| `ARM K` vs `ARM C` | `SELLOFF-ENTRY-HELPS` | C0–C3 hold, difference positive |
| | `SELLOFF-ENTRY-HURTS` | C1 holds, difference negative |
| | `NULL` | powered, C1 fails |
| put contribution | `PUT-ADDS` | C0–C3 hold, `ARM K` minus `ARM K-diag` positive |
| | `PUT-COSTS` | C1 holds, the difference negative |
| | `NULL` | powered, C1 fails |

Any object may also print `UNDERPOWERED`, `NOT BUILT — AWAITING SCRAPE`, or `UNWORDED` (criteria
met listed) when C1 holds but a later criterion fails.

| Study-level token | When |
|---|---|
| `CANDIDATE (PROVISIONAL)` | `ARM K` `PAYS`, and `SELLOFF-ENTRY-HELPS`, and the put is not `PUT-COSTS` |
| `DIAGONAL-ONLY (PROVISIONAL)` | `ARM K-diag` would meet `PAYS` and `SELLOFF-ENTRY-HELPS` on its own, and the put is `PUT-COSTS` |

_Resolved at build (2026-11-01):_ "on its own" grades `ARM K-diag` against zero and against the
calm weeks' diagonal alone, on the same criteria.
| `NO-EDGE` | anything else |

Every in-sample token carries `(PROVISIONAL)`, because of the hindsight disclosed above.

## Secondary grades

_Resolved at build (2026-11-01):_ the operator asked, before any outcome, that every printed arm
and cell be graded, not only printed. The primary objects and their tokens above are unchanged.
The primary keeps its uncorrected C1, which was fixed beforehand.

Each secondary object gets the same C0 to C3 and the same tokens as its primary counterpart. The
floors do not move. The objects:

| Question | Secondary objects |
|---|---|
| vs zero | the eight non-primary cells' `ARM K` (put diagonal `ARM PD`, 1 cycle, 6 cycles, put strike × 0.95, `ARM K-diag`, 2 puts, −8% trigger, D-close fill, put spread; the `ARM K-diag` cell is one of them), and `ARM K-put` |
| vs its own `ARM C` | the same cells, each against its own calm weeks |
| put contribution | the cells that hold a put, each `ARM K` minus its diagonal alone |
| option wrap vs shares | `ARM K` minus `ARM H` per trigger |

The tokens for the last row are `WRAP-BEATS-SHARES`, `SHARES-BEAT-WRAP` and `NULL`, with the same
C0 to C3 and a paired bootstrap on trigger days.

**Multiplicity.** C1 for a secondary object is a Holm–Bonferroni step-down across the powered
secondary objects of its question, at family alpha 0.05. The bootstrap p is two-sided, from the
same draws as the interval. The report prints raw and adjusted p. An object below its C0 floor
prints `UNDERPOWERED` and is not in its family. The −8% trigger cell has 5 triggers, under the
floor of 8, so it prints `UNDERPOWERED`; the floor is not lowered. Every secondary token is
suffixed `(SECONDARY)`. The `ARM K-diag` cell also feeds the primary `DIAGONAL-ONLY` test
uncorrected, as registered above; the corrected token is the secondary one.

**Standing.** A secondary cell reaches `CANDIDATE (SECONDARY)` only when its corrected tokens
read `PAYS`, `SELLOFF-ENTRY-HELPS` and not `PUT-COSTS`, and the PBO across the full cell set is
below 0.5. It is never promoted without forward confirmation and a new registration.

## The forward read

- Every trigger day after 2026-11-01 is traded by the rule and graded once its diagonal closes
  (about 63 sessions), on the same criteria.
- **Confirmation.** A PROVISIONAL `CANDIDATE` becomes `CONFIRMED` after at least 3 forward
  triggers whose mean R is positive and whose `ARM K` minus same-quarter `ARM C` is positive.
- **Disconfirmation.** A forward mean R at or below zero after 3 triggers sends it back to
  `NO-EDGE`.
- **Sunset.** 2029-11-01. Nine triggers in 4.5 years is about two a year, so three forward
  triggers take one to two years.

## Gates

A failed gate refuses the run (non-zero exit).

- **G-HASH.** The imported E-DD5 thresholds match `EPISODE_DEFS_SHA256`.
- **G-CENSUS.** The trigger list, calm-week count and fetch census print before any option price
  is read. The trigger list must reproduce the nine dates above.

  _Resolved at build (2026-11-01):_ the calm-week count must also reproduce the 154 above. The
  await gate covers both graded arms of the primary, `ARM K` and `ARM C`, in-sample. A
  parameter cell with a trade still awaiting prints `NOT BUILT` for that cell only.
- **G-SEAL.** No in-sample signal date on or after 2026-09-23.

## What could ship

Nothing ships from this study. A secondary cell with `CANDIDATE (SECONDARY)` standing is
a lead for a new registration. It needs PBO below 0.5, forward confirmation and a new
registration before it is anything more.

- `CANDIDATE (CONFIRMED)` files an entry in `research/deployment-evidence.md` under "to be
  tested": the sell-off package as a mechanical rule, sized by the operator's §2 practice.
- `DIAGONAL-ONLY` files the dip-entry diagonal alone, and the put as a cost.
- `NO-EDGE` closes the idea on this geometry. A different geometry is a new registration.

## Anti-tuning

- The trigger was fixed on 2026-10-07 by another study, before this idea was written.
- The geometry was fixed on 2026-11-01 before any option price for these dates was read.
- Exactly one arm and one comparator are graded.
- A revisit after a result is a NEW registration, never an edit.
