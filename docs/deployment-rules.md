# Deployment rules — the deploy-day card

Which analysis plays get real capital. Read this on a deploy morning, do what it
says. Every rule here is a confirmed backtest finding — the numbers, CIs and
rollback triggers behind them live in
[`research/deployment-evidence.md`](../research/deployment-evidence.md).

> **Derived on v3 rows; v4 transfer is not yet validated.** The pre-registered
> composition bridge has not fired. Until it does, deploy under these rules
> unchanged and expect them to be re-confirmed, not re-derived.

---

## 0. Before you deploy

- `make analyze` — it already depends on the `mech-regime` target, so the
  SPY/VIX table behind `mech_cell` is refreshed for you.
- Read **`mech_cell`** off the analysis row. Do not hand-compute SPY vs its
  50-day SMA; the column is on every row and backfilled.
- Budget: the analysis emits ~10 plays/day. **Deploy 1–3.**
- Entry basis: the **next trading day's OPEN**. Same-day fills were never
  modeled and are not covered by any rule here.

## 1. VETO — never deploy, regardless of score

1. **`bear_call_spread`** — intake-vetoed. If one appears it is a pipeline bug,
   not a trade.
2. **Any play when the model regime is BEAR + H-VOL.**
3. **Any credit play when the model regime is RANGE + L-VOL.**
4. **`bear_put_spread` / `long_put` as a selection play** — never in the deployed
   top-3, however thin the day's A/B supply. Bear is a hedge, not a selection:
   all pre-registered DEMOTE criteria fired on the n=164 holdout, and 0 of 496
   conditioned subsets found a profitable bear slice. **This veto does not apply
   to the §4 hedge sleeve** — that is the one sanctioned way to hold a bear
   position. Bear plays stay emitted and visible on the analysis rows; the
   sleeve picks from them (which is why this is a card veto, not an intake veto).

## 2. Tier the survivors, deploy top-3/day in tier order

| Tier                                  | What qualifies                                                          |
| ------------------------------------- | ----------------------------------------------------------------------- |
| **A** — deploy first                  | `bull_call_spread` when the model regime is **RANGE or E-VOL**          |
| **B** — deploy if capital remains     | any other `bull_call_spread`; `bull_put_spread` meeting the §3 geometry |
| **C** — skip when capital-constrained | everything else                                                         |

Tie-break **within** a tier: higher `score_total`. That is a deterministic
ordering only — it carries no signal (see §6).

Survivors past the third are printed as a **Reserve** list, one line each. A
reserve REPLACES a budgeted pick that turns out to be untradeable at order
entry; it is never a fourth position. Taking one as an addition puts the day
over budget — which is how a 1–3/day rule coexisted with a book that grew from
3 open legs to 19 between May and August 2026.

Tier membership is **structure × model regime × entry geometry**. Nothing else.

## 3. Check at order entry in IBKR — not on the analysis row

**`bull_put_spread` short leg: `0.08 ≤ |delta| ≤ 0.20` AND `DTE ≤ 59`.**

- Delta is a **band, not a floor** — too close to the money is as bad as too far.
- Prefer **45–59 DTE**; that sub-band carries the whole edge.
- Miss either condition and the play drops to Tier C.

`|delta|` and DTE are not columns on the analysis row — read them in IBKR.

## 4. Bear positions — hedge sleeve only (optional)

Bear is a **hedge, not a selection** — §1.4 vetoes bear debit as a selection
play outright (until 2026-08-13 bear rows merely landed in Tier C, which a thin
day could still deploy). This section only applies to a position you take
deliberately for drawdown protection.

- **Pick:** no ranking preference is supported on v4 — the pick is operator
  discretion. The v3-adopted "closer-to-money first" (`|delta|` descending)
  rule read −0.004 vs the day average on the 2026-08-24 v4 re-read (CI
  [−0.166, +0.166], a null — pulled per `research/pre-registrations/f4_deployment/bear_deploy.md`
  RE-1; the v3 evidence stays recorded in `research/deployment-evidence.md`).
- **Size:** **≤ ½ a normal position.** Treat it as insurance, not a trade.
  (Policy, not evidence — D3 sizing has never been MET at any size, v3 or v4.)
- **Do not** rank the sleeve by `score_total` (§6), and **do not** buy the
  cheap far-OTM put — v3-era evidence, not contradicted on v4
  (`|delta| low first` gain +0.017, CI [−0.133, +0.168] spans zero; RE-2 retained).
- The sleeve is held as **operator policy** (stated 2026-08-24), not on v4
  evidence: the hedge-contribution criterion (D2) is NOT MET on the v4 re-read
  and within-era unstable (it flipped MET → NOT MET between the 08-22 and
  08-24 runs). The sleeve loses money on balance. That is the price of the
  protection.

## 5. Exit management

Set these at order entry. `mech_cell` on the signal-date row picks the row of the
table; the **mechanical** regime governs exits, while the **model** regime
governs selection in §1–2.

| Position                                                        | Profit target          | Stop                                       | Trailing stop                               | Time exit                 |
| --------------------------------------------------------------- | ---------------------- | ------------------------------------------ | ------------------------------------------- | ------------------------- |
| Debit — normal                                                  | 90% of premium paid    | −75%                                       | none                                        | 75% of DTE elapsed        |
| Debit — signal date is mech **BEAR + H-VOL or E-VOL**           | 90%                    | −75%                                       | **arm at +50%, then trail 50pts from peak** | 75% of DTE                |
| Credit (`bull_put_spread`)                                      | 65% of credit captured | **none** — risk is defined by wing width   | none                                        | none (ride toward expiry) |

Three clauses that keep the table consistent:

- **The debit time exit has a date.** "75% of DTE elapsed" means: **exit on or
  before `entry date + 0.75 × (expiry − entry date)`** — i.e. when 25% of the
  option's life remains, counted in calendar days and rounded down. You never
  need to compute it: the daily journal (§4 of its report) prints that date for
  every open debit position, and the deploy card projects it for every
  candidate (a range, since at card time only the play's DTE range is known).
  Card, report and this table all read the same
  `config/backtest.yml::time_exit_dte_fraction`, so they cannot drift apart.
  Credits carry no time exit and get no date (row 4).
- **Credits are never regime-switched.** A `bull_put_spread` keeps row 4 in every
  regime.
- **The bear-debit breakeven ratchet was REVERTED 2026-08-24.** Its rollback
  trigger fired at the first floor evaluation (2025 mean-R delta negative,
  total gain vs PROD +$58 on the v4 re-read) — a bear debit now runs the
  normal debit row everywhere except a mech BEAR + H/E-VOL date, where the
  trail row applies. Evidence: `research/deployment-evidence.md` §"The
  bear-debit breakeven ratchet".

## 6. What not to use

- **`score_total` is a within-tier tie-break only.** It is decision-irrelevant —
  never use it to promote a play into a tier, and never to pick the hedge sleeve.
- **Never rank a v3 row against a v4 row.** The scales differ (v3 0–100; v4 0–50,
  or 0–55 for VOLATILITY intent) and are deliberately incomparable.
- **Never use scores from rows emitted before 2026-07-13** — they anti-select.
  All live rows qualify.

---

## 7. Reference stats — what each cell has actually done

**These are descriptive, not a selection rule.** They are in-sample summaries of
the book the rules above were derived on. Read them to know what a deploy
*normally* looks like and how much room a position needs; do **not** promote a
play into a tier because its cell looks good here. §1–4 is the selection rule.

<!-- Regenerate: `python -m scripts.backtest_study run bear_giveback --arms S`
     Snapshot below: 2026-08-12, pooled real+tweak book, 795 rows, bs excluded. -->

**Column key**

| Col     | Meaning                                                                                                    |
| ------- | ---------------------------------------------------------------------------------------------------------- |
| `n`     | rows in the cell                                                                                           |
| `win`   | share with realized R > 0                                                                                  |
| `PF`    | profit factor — gross winning $ / \|gross losing $\|                                                       |
| `meanR` | mean realized return as a fraction of premium at risk                                                      |
| `$`     | summed realized dollars (size-weighted; `meanR` is not)                                                    |
| `MFE`   | mean best unrealized point on the path                                                                     |
| `MAE`   | mean worst unrealized point on the path                                                                    |
| `gb`    | give-back = \|MAE\| / MFE. **>1 = the average row went deeper under water than it ever showed green.**     |
| `cap`   | capture = meanR / MFE. **Low `cap` with high `MFE` is an exit problem; low `MFE` is a selection problem.** |

`win` and `PF` disagree constantly — read them together. `bull_put_spread` wins
68% of the time and still has PF 0.94.

### 7.1 The book, and the ladder

| Cell         |   n | win |       PF |  meanR |          $ |   MFE |   MAE |   gb |   cap |
| ------------ | --: | --: | -------: | -----: | ---------: | ----: | ----: | ---: | ----: |
| **all rows** | 795 | 50% |     1.04 | +0.034 |     +12.3k | +0.89 | −0.87 | 0.98 | +0.04 |
| debit        | 593 | 45% |     1.06 | +0.034 |     +15.7k | +0.91 | −0.70 | 0.77 | +0.04 |
| credit       | 202 | 63% |     0.92 | +0.033 |      −3.4k | +0.82 | −1.37 | 1.68 | +0.04 |
| **Tier A**   | 131 | 63% | **2.29** | +0.400 | **+50.0k** | +1.30 | −0.49 | 0.38 | +0.31 |
| **Tier B**   | 166 | 67% | **1.78** | +0.303 | **+32.1k** | +1.06 | −0.82 | 0.77 | +0.29 |
| **Tier C**   | 408 | 43% |     0.79 | −0.098 |     −41.5k | +0.74 | −0.90 | 1.22 | −0.13 |
| **VETO**     |  90 | 32% |     0.34 | −0.394 |     −28.3k | +0.61 | −1.38 | 2.28 | −0.65 |

The ladder is monotone on every column. A and B carry the whole book; C and VETO
together are −$69.8k. **The rules are a subtraction, not an addition** — the edge
comes from not deploying C and VETO.

### 7.2 By structure

| Structure | n | win | PF | meanR | $ | MFE | MAE | gb | cap |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `bull_call_spread` | 242 | 60% | **2.05** | +0.329 | **+79.4k** | +1.24 | −0.51 | 0.41 | +0.27 |
| `bull_put_spread` | 166 | 68% | 0.94 | +0.063 | −2.2k | +0.78 | −1.24 | 1.60 | +0.08 |
| `bear_put_spread` | 327 | 37% | 0.74 | −0.114 | **−44.8k** | +0.73 | −0.82 | 1.11 | −0.15 |
| `bear_call_spread` | 37 | 32% | **0.19** | −0.578 | −11.2k | +0.55 | −2.20 | **4.03** | −1.06 |
| `long_call` | 8 | 0% | 0.00 | −0.522 | −8.2k | +0.74 | −0.72 | 0.98 | −0.71 |
| `long_put` | 6 | 17% | 0.01 | −0.613 | −4.9k | +0.27 | −0.88 | 3.26 | −2.28 |
| `straddle` | 5 | 60% | 3.97 | +0.402 | +3.5k | +0.76 | −0.37 | 0.48 | +0.53 |
| `strangle` | 3 | 67% | 2.46 | +0.487 | +1.9k | +1.28 | −0.65 | 0.51 | +0.38 |

`bull_call_spread` alone is +$79.4k against a whole-book +$12.3k. `bear_call_spread`
gives back 4× what it ever shows — that ratio is why it is intake-vetoed, and it is
the worst `gb` on the board. Naked longs (n=14 combined) are a rounding error but
have never worked. Straddle/strangle n is too small to read.

### 7.3 By model regime × structure

The **model** regime (the free-text label on the analysis row) is the
selection-relevant one. Structures with n < 3 in a cell omitted.

| Model regime | Structure | n | win | PF | meanR | $ | MFE | MAE | gb | cap |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| BULL | `bull_call_spread` | 100 | 56% | 1.78 | +0.237 | +26.4k | +1.14 | −0.55 | 0.48 | +0.21 |
| BULL | `bull_put_spread` | 41 | 73% | 0.85 | +0.237 | −1.1k | +0.87 | −1.29 | 1.49 | +0.27 |
| BULL | `bear_put_spread` | 42 | 29% | 0.56 | −0.239 | −11.9k | +0.58 | −0.92 | 1.58 | −0.41 |
| BEAR | `bull_call_spread` | 31 | 65% | 2.14 | +0.400 | +9.7k | +1.48 | −0.42 | 0.28 | +0.27 |
| BEAR | `bull_put_spread` | 28 | 57% | 0.63 | −0.200 | −2.9k | +0.70 | −0.88 | 1.25 | −0.29 |
| BEAR | `bear_put_spread` | 115 | 40% | 0.79 | −0.105 | −11.7k | +0.72 | −0.80 | 1.10 | −0.14 |
| BEAR | `bear_call_spread` | 18 | 33% | 0.24 | −0.483 | −5.3k | +0.57 | −2.03 | 3.53 | −0.84 |
| RANGE | `bull_call_spread` | 111 | 62% | **2.28** | +0.392 | **+43.3k** | +1.26 | −0.51 | 0.41 | +0.31 |
| RANGE | `bull_put_spread` | 97 | 69% | 1.07 | +0.066 | +1.8k | +0.76 | −1.32 | 1.74 | +0.09 |
| RANGE | `bear_put_spread` | 170 | 36% | 0.77 | −0.089 | −21.2k | +0.78 | −0.80 | 1.03 | −0.11 |
| RANGE | `bear_call_spread` | 16 | 31% | 0.15 | −0.592 | −4.8k | +0.47 | −2.43 | 5.20 | −1.27 |

`bull_call_spread` is the only structure that is PF > 1.7 in **every** model
regime, including BEAR. That is the whole reason Tier A and B are both
`bull_call_spread` cells.

### 7.4 By model regime × vol — where the §1 vetoes live

All structures pooled.

| Cell                         |   n |     win |       PF |  meanR |          $ |   MFE |   MAE |   gb |   cap |
| ---------------------------- | --: | ------: | -------: | -----: | ---------: | ----: | ----: | ---: | ----: |
| BULL + L-VOL                 | 117 |     44% |     0.81 | −0.062 |      −9.9k | +0.85 | −0.94 | 1.10 | −0.07 |
| BULL + C-VOL                 |  74 |     65% |     1.80 | +0.351 |     +17.4k | +1.06 | −0.61 | 0.57 | +0.33 |
| BEAR + E-VOL                 | 122 |     52% |     1.07 | +0.025 |      +3.0k | +0.91 | −0.75 | 0.82 | +0.03 |
| **BEAR + H-VOL** ← §1.2 veto |  64 | **30%** | **0.39** | −0.350 | **−20.6k** | +0.61 | −1.07 | 1.75 | −0.57 |
| BEAR + C-VOL                 |   9 |     67% |     2.22 | +0.440 |      +4.4k | +1.09 | −0.86 | 0.79 | +0.40 |
| RANGE + E-VOL                | 212 |     52% |     1.14 | +0.087 |     +11.1k | +0.88 | −0.91 | 1.03 | +0.10 |
| RANGE + H-VOL                |  60 |     37% |     0.63 | −0.196 |     −11.6k | +0.62 | −0.85 | 1.39 | −0.32 |
| RANGE + L-VOL                |  54 |     46% |     1.08 | −0.114 |      +1.9k | +1.01 | −1.04 | 1.03 | −0.11 |
| RANGE + C-VOL                |  73 |     59% |     1.50 | +0.250 |     +13.6k | +1.06 | −0.87 | 0.82 | +0.24 |

BEAR + H-VOL is the worst pooled cell on the board — 30% win, PF 0.39, −$20.6k.
That is §1.2, and it holds pooled across every structure.

### 7.5 The Tier-A cell — `bull_call_spread` by regime × vol

| Cell          | Tier |   n | win |   PF |  meanR |      $ |   MFE |   MAE |   gb |   cap |
| ------------- | ---- | --: | --: | ---: | -----: | -----: | ----: | ----: | ---: | ----: |
| RANGE + E-VOL | A    |  50 | 66% | 2.99 | +0.543 | +25.4k | +1.47 | −0.47 | 0.32 | +0.37 |
| RANGE + H-VOL | A    |  13 | 77% | 9.80 | +0.644 | +10.4k | +1.08 | −0.25 | 0.23 | +0.60 |
| RANGE + L-VOL | A    |  15 | 53% | 1.81 | +0.197 |  +3.7k | +1.26 | −0.68 | 0.54 | +0.16 |
| RANGE + C-VOL | A    |  32 | 56% | 1.35 | +0.179 |  +4.9k | +1.02 | −0.60 | 0.59 | +0.18 |
| BULL + C-VOL  | B    |  40 | 75% | 5.01 | +0.544 | +24.5k | +1.37 | −0.31 | 0.22 | +0.40 |
| BULL + L-VOL  | B    |  60 | 43% | 1.07 | +0.033 |  +1.9k | +0.99 | −0.71 | 0.71 | +0.03 |
| BEAR + E-VOL  | A    |  20 | 65% | 2.37 | +0.446 |  +6.8k | +1.56 | −0.38 | 0.25 | +0.29 |
| BEAR + H-VOL  | VETO |   9 | 67% | 2.27 | +0.389 |  +2.9k | +1.50 | −0.43 | 0.29 | +0.26 |

Two things to notice, both already reflected in the rules:

- **BULL + C-VOL (PF 5.01, n=40) is the strongest Tier-B cell** and beats most of
  Tier A. It is B only because Tier A is defined as RANGE-or-E-VOL. Do not
  reorder on this — n=40 in-sample, and the A-vs-B ordering was validated on the
  tier as a whole (§7.1), not cell by cell.
- **BEAR + H-VOL `bull_call_spread` (n=9) looks positive but is still vetoed.**
  §1.2 vetoes the whole regime cell, which is −$20.6k pooled (§7.4). Nine rows do
  not overturn that. This is the cell most likely to tempt an override — don't.

### 7.6 The §3 geometry gate — `bull_put_spread`

| Cell | n | win | PF | meanR | $ | MFE | MAE | gb | cap |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **in band** (0.08 ≤ \|δ\| ≤ 0.20, DTE ≤ 59) | 65 | **85%** | 1.95 | +0.418 | +5.9k | +0.94 | −1.23 | 1.31 | +0.45 |
| — of those, DTE 45–59 | 52 | 87% | 1.70 | +0.439 | +3.6k | +0.93 | −1.08 | 1.16 | +0.47 |
| out of band | 101 | 57% | 0.76 | −0.166 | −8.0k | +0.67 | −1.25 | 1.86 | −0.25 |

The gate is the entire `bull_put_spread` edge: in-band is PF 1.95 / +$5.9k,
out-of-band is PF 0.76 / −$8.0k. The structure's flat headline in §7.2 is those
two pooled. Note `gb` stays above 1 even in band — credits routinely go further
against you than for you, which is exactly why row 4 of §5 carries no stop.

### 7.7 By mechanical cell — the exit-conditioning view

`mech_cell`, not the model regime. This is the label §5 keys exits off, so read it
to know what path a position is likely to walk, not to decide whether to deploy.

| Mech cell | Structure | n | win | PF | meanR | $ | MFE | MAE | gb | cap |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| LVOL (n=291) | `bull_call_spread` | 125 | 54% | 1.58 | +0.192 | +26.9k | +1.07 | −0.62 | 0.58 | +0.18 |
| | `bull_put_spread` | 61 | 67% | 0.63 | +0.027 | −5.7k | +0.79 | −1.61 | 2.03 | +0.03 |
| | `bear_put_spread` | 91 | 46% | 1.18 | +0.088 | +7.3k | +0.95 | −0.82 | 0.85 | +0.09 |
| | `bear_call_spread` | 6 | 17% | 0.00 | −1.290 | −3.8k | +0.51 | −2.39 | 4.73 | −2.55 |
| BEAR_HE (n=449) | `bull_call_spread` | 95 | 64% | 2.58 | +0.463 | +38.8k | +1.35 | −0.43 | 0.32 | +0.34 |
| | `bull_put_spread` | 90 | 67% | 1.25 | +0.063 | +5.1k | +0.77 | −0.95 | 1.23 | +0.08 |
| | `bear_put_spread` | 218 | 35% | 0.66 | −0.164 | −40.3k | +0.67 | −0.81 | 1.21 | −0.25 |
| | `bear_call_spread` | 31 | 35% | 0.27 | −0.440 | −7.5k | +0.55 | −2.16 | 3.91 | −0.80 |
| RB_EVOL (n=17) | all | 17 | — | — | — | −7.3k | — | — | — | — |
| PROD (n=38) | `bull_call_spread` | 18 | 78% | 5.90 | +0.655 | +14.0k | +1.76 | −0.26 | 0.15 | +0.37 |
| | `bull_put_spread` | 10 | 90% | 1.26 | +0.626 | +0.3k | +0.91 | −1.50 | 1.66 | +0.69 |
| | `bear_put_spread` | 10 | 10% | 0.23 | −0.566 | −6.7k | +0.47 | −0.95 | 2.01 | −1.19 |

`bear_put_spread` in BEAR_HE is the single largest loss cell in the book
(n=218, −$40.3k) — and `cap −0.25` against `MFE +0.67` says those positions
**do** show green and then give it all back. That is the finding §5 rows 2–3
exist to manage: it is an exit problem, not a selection one. RB_EVOL (n=17) is
too thin to break out per structure.

### 7.8 Reading these numbers safely

- **In-sample.** Every cell here is the book the rules were fitted on. Expect
  live results to be worse, not better.
- **Small n moves a lot.** Below ~30 rows, treat a cell as directional at best.
  n < 10 cells are printed for completeness only.
- **`$` and `meanR` can disagree** — `$` is position-size weighted. When they
  point opposite ways, one big position is doing the talking.
- **v3 rows.** Same caveat as the rules themselves: derived on v3, not yet
  re-confirmed on v4.
- **`bs_options_hist` proxy rows are excluded** (model-priced, attenuating).
  The book is real + `strike_expiry_tweak` only.

---

**Why these rules, what they were measured on, and what would revert them:**
[`research/deployment-evidence.md`](../research/deployment-evidence.md).
Config that implements the exits: `simulation.regime_exit` and
`simulation.structure_exit` in [`config/backtest.yml`](../config/backtest.yml).
