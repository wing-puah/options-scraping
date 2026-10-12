# Deployment rules — the deploy-day card

Which analysis plays get real capital. Read this on a deploy morning, do what it
says. Every rule here is a confirmed backtest finding — the numbers, CIs and
rollback triggers behind them live in
[`research/deployment-evidence.md`](../research/deployment-evidence.md).

> **Derived on v3 rows; v4 transfer is not yet validated.** The pre-registered
> composition bridge has not fired. Until it does, deploy under these rules
> unchanged and expect them to be re-confirmed, not re-derived.

---

<a id="s0"></a>

## 0. Before you deploy

- `make analyze` — it already depends on the `mech-regime` target, so the
  SPY/VIX table behind `mech_cell` is refreshed for you.
- Read **`mech_cell`** off the analysis row. Do not hand-compute SPY vs its
  50-day SMA; the column is on every row and backfilled.
- Budget: the analysis emits ~10 plays/day. **Deploy 1–3.**
- Entry basis: the **next trading day's OPEN**. Same-day fills were never
  modeled and are not covered by any rule here.

<a id="s0-labels"></a>

### Labels on the analysis row

The card tells you to read two market labels. They are different things and they
govern different jobs.

| Label | Source | Governs |
|---|---|---|
| Model regime | The analysis model's own label on the row (BULL / BEAR / RANGE, plus a vol tag). Judgment, not a formula. | **Selection** — §1 vetoes and §2 tiers |
| `mech_cell` | A fixed formula on SPY and VIX closes (`lib/mech_regime.py`). | **Exits** — §5 |

Evidence that the two win on opposite jobs: `research/current.md`, section
2026-07-22, addendum 4. Never use one for the other's job.

**`mech_cell`** is causal: the label for date D uses only closes on or before D.
It has two parts.

| Part | Value | Rule |
|---|---|---|
| Direction | BULL | SPY > its 50-day SMA **and** 20-day return > 0 |
| | BEAR | SPY < its 50-day SMA **and** 20-day return < 0 |
| | RANGE | anything else |
| Vol | E-VOL | VIX ≥ 30 **or** 5-day VIX change ≥ +25% |
| | H-VOL | VIX ≥ 20 (and not E-VOL) |
| | L-VOL | otherwise |

The stored cell combines them, first match wins:

| `mech_cell` | When |
|---|---|
| `BEAR_HE` | BEAR and (H-VOL or E-VOL) |
| `LVOL` | any direction with L-VOL |
| `RB_EVOL` | RANGE or BULL, with E-VOL |
| `NONE` | labelled, but no override cell applies: in practice RANGE or BULL with H-VOL |
| `NO_DATA` | no label: the SPY/VIX table is missing, ends before D, or D is inside the first 50 days of history |

`PROD` in the §7.7 table is the backtest's stored fallback for a row with `NONE`
or no usable label. It means "run the base exit config" — no cell override.

`spy_below_sma` is a research-tier field (SPY strictly below its 50-day SMA,
read by the `dip_buy` study, still to be tested). It governs nothing on this card.

<a id="s1"></a>

## 1. VETO — never deploy, regardless of score

1. **`bear_call_spread`** — intake-vetoed. If one appears it is a pipeline bug,
   not a trade.
2. **Any play when the model regime is BEAR + H-VOL.**
3. **Any credit play when the model regime is RANGE + L-VOL.**
4. **`bear_put_spread` / `long_put` as a selection play** — never in the deployed
   top-3, however thin the day's A/B supply. Bear is a hedge, not a selection:
   all pre-registered DEMOTE criteria fired on the n=164 holdout, and 0 of 496
   conditioned subsets found a profitable bear slice.
   **Exception: the §4 hedge sleeve**, the one sanctioned way to hold a bear
   position. Bear plays therefore stay emitted and visible on the analysis rows
   for the sleeve to pick from — which is why this is a card veto, not an
   intake veto.

<a id="s2"></a>

## 2. Tier the survivors, deploy top-3/day in tier order

| Tier                                  | What qualifies                                                          |
| ------------------------------------- | ----------------------------------------------------------------------- |
| **A** — deploy first                  | `bull_call_spread` when the model regime is **RANGE or E-VOL**          |
| **B** — deploy if capital remains     | any other `bull_call_spread`; `bull_put_spread` meeting the §3 geometry |
| **C** — skip when capital-constrained | everything else                                                         |

Tier membership is **structure × model regime × entry geometry**. Nothing else.
Tie-break **within** a tier: higher `score_total`, a deterministic ordering that
carries no signal (see §6).

Survivors past the third are printed as a **Reserve** list, one line each. A
reserve REPLACES a budgeted pick that turns out to be untradeable at order
entry; it is never a fourth position. Taking one as an addition puts the day
over budget — which is how a 1–3/day rule coexisted with a book that grew from
3 open legs to 19 between May and August 2026.

<a id="s3"></a>

## 3. Check at order entry in IBKR — not on the analysis row

**`bull_put_spread` short leg: `0.08 ≤ |delta| ≤ 0.20` AND `DTE ≤ 59`.**

- Delta is a **band, not a floor** — too close to the money is as bad as too far.
- Prefer **45–59 DTE**; that sub-band carries the whole edge.
- Miss either condition and the play drops to Tier C.

`|delta|` and DTE are not columns on the analysis row — read them in IBKR.

<a id="s4"></a>

## 4. Bear positions — hedge sleeve only (optional)

Bear is a **hedge, not a selection**: §1.4 vetoes bear debit as a selection play
outright, and this section applies only to a position you take deliberately for
drawdown protection. (Until 2026-08-13 bear rows merely landed in Tier C, which
a thin day could still deploy.)

The sleeve is held as **operator policy** (stated 2026-08-24), not on v4
evidence. The hedge-contribution criterion (D2) is NOT MET on the v4 re-read and
is unstable within the era — it flipped MET → NOT MET between the 08-22 and
08-24 runs. The sleeve loses money on balance; that is the price of the
protection.

- **Pick:** operator discretion. No ranking preference is supported on v4 — the
  v3-adopted "closer-to-money first" (`|delta|` descending) rule read −0.004 vs
  the day average on the 2026-08-24 v4 re-read (CI [−0.166, +0.166], a null),
  and was pulled per `research/pre-registrations/f5_hedging/hedge_sizing.md`
  RE-1. The v3 evidence stays recorded in `research/deployment-evidence.md`.
- **Size: ≤ ½ a normal position.** Treat it as insurance, not a trade. Policy,
  not evidence — D3 sizing has never been MET at any size, v3 or v4.
- **Do not** rank the sleeve by `score_total` (§6).
- **Do not** buy the cheap far-OTM put. v3-era evidence, not contradicted on v4
  (`|delta| low first` gain +0.017, CI [−0.133, +0.168] spans zero; RE-2 retained).
- **Do not open the hedge because the day gapped up** (SPY open ≥ prior close
  ×1.003). The hedge does worse on exactly those days: `hedge_timing` H3-GAP
  reads a paired excess of −0.506 R against ordinary days (CI [−0.844, −0.157],
  every LOO fold, all cuts). Accepted by the operator 2026-09-06 from that
  study's drafted prohibition — a restriction taken on a correlated window, not
  a shipped rule. It bans the gap as the REASON to hedge; hedging concentrated
  exposure on a day that happens to gap is untested and not covered
  (`research/deployment-evidence.md` §"Hedge-timing triggers").

<a id="s5"></a>

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

- **The debit time exit has a date.** "75% of DTE elapsed" means **exit on or
  before `entry date + 0.75 × (expiry − entry date)`** — when 25% of the
  option's life remains, counted in calendar days and rounded down. You never
  need to compute it: the daily journal (§4 of its report) prints that date for
  every open debit position, and the deploy card projects it for every
  candidate (a range, since at card time only the play's DTE range is known).
  Card, report and this table all read the same
  `config/backtest.yml::time_exit_dte_fraction`, so they cannot drift apart.
  Credits carry no time exit and get no date (row 4).
- **Credits are never regime-switched.** A `bull_put_spread` keeps row 4 in every
  regime.
- **The bear-debit peak-triggered breakeven stop was REVERTED 2026-08-24.** A
  bear debit now runs the normal debit row everywhere except a mech BEAR +
  H/E-VOL date, where the trail row applies. Its rollback trigger fired at the
  first floor evaluation (2025 mean-R delta negative, total gain vs PROD +$58 on
  the v4 re-read). Evidence: `research/deployment-evidence.md` §"The
  bear-debit peak-triggered breakeven stop".

<a id="s6"></a>

## 6. What not to use

- **`score_total` is a within-tier tie-break only.** It is decision-irrelevant —
  never use it to promote a play into a tier, and never to pick the hedge sleeve.
- **Never rank a v3 row against a v4 row.** The scales differ (v3 0–100; v4 0–50,
  or 0–55 for VOLATILITY intent) and are deliberately incomparable.
- **Never use scores from rows emitted before 2026-07-13** — they anti-select.
  All live rows qualify.

---

<a id="s7"></a>

## 7. Reference stats — what each cell has actually done

**These are descriptive, not a selection rule** — in-sample summaries of the book.
Read them to know what a deploy *normally* looks like and how much room a position
needs, never to promote a play into a tier because its cell looks good here.
§1–4 is the selection rule.

**The tables below are the v4 book.** The rules in §1–§6 were derived on v3, so
several cells here read weaker than the rule's own evidence. That is a finding
about transfer, not a reason to change a rule on a read of one table. The v3
numbers stay in git history (this file before 2026-10-12) and in
[`research/deployment-evidence.md`](../research/deployment-evidence.md).
§7.1 keeps a compact v3 tier block for comparison.

<!-- Regenerate: `python -m scripts.backtest_study run bear_giveback -- --arms S`
     (study: scripts/backtest_study/f2_management/bear_giveback.py).
     Snapshot below: run 2026-10-12, era v4, 1,850 rows (1,020 real + 830
     strike_expiry_tweak, bs excluded), exports dated 2026-10-06, seal withheld 0 rows.
     Prior snapshot: 2026-08-12, v3 pooled book, 795 rows. -->

**Cost basis.** v4 rows are **net of commission** (`realized_pnl_abs` and `meanR`);
the path columns (`MFE`, `MAE`) are gross. The v3 snapshot was gross of costs.
Slippage is 0: spreads are filled at mid.

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

`win` and `PF` disagree constantly — read them together. On v4 `bull_put_spread`
wins 70% of the time and still has PF 0.92.

<a id="s7-1"></a>

### 7.1 The book, and the ladder

| Cell         |    n | win |   PF |  meanR |          $ |   MFE |   MAE |   gb |   cap |
| ------------ | ---: | --: | ---: | -----: | ---------: | ----: | ----: | ---: | ----: |
| **all rows** | 1850 | 50% | 0.99 | +0.013 |      −9.7k | +0.79 | −0.73 | 0.92 | +0.02 |
| debit        | 1362 | 42% | 0.98 | −0.003 |     −15.3k | +0.80 | −0.64 | 0.79 | −0.00 |
| credit       |  488 | 70% | 1.04 | +0.058 |      +5.6k | +0.75 | −0.99 | 1.31 | +0.08 |
| **Tier A**   |  213 | 51% | 1.28 | +0.119 |     +22.6k | +0.92 | −0.52 | 0.56 | +0.13 |
| **Tier B**   |  563 | 60% | 1.38 | +0.115 |     +71.7k | +0.83 | −0.71 | 0.86 | +0.14 |
| **Tier C**   | 1064 | 44% | 0.80 | −0.058 |     −99.3k | +0.75 | −0.78 | 1.05 | −0.08 |
| **VETO**     |   10 | 30% | 0.26 | −0.345 |      −4.8k | +0.24 | −0.70 | 2.93 | −1.45 |

**These tiers are not quite §1–§2.** The study book tiers rows with its own
port in `scripts/backtest_study/lib/book.py`, which lacks the §1.3 and §1.4
vetoes. Bear debits and RANGE + L-VOL credits therefore sit in Tier C here, not
VETO. That is why VETO holds only 10 rows.

The ladder separates A and B from C. It is **not** monotone: B beats A on win,
PF and `$`. A and B are about level on `meanR`. Tier C carries the loss
(−$99.3k), and the VETO cell is now only 10 rows. **The rules are still a
subtraction** — the edge is in not deploying C — but the A-over-B ordering is
not supported on v4.

v3 frozen tiers, for comparison (795 rows, gross of costs):

| Tier | n | win | PF | meanR | $ |
|---|--:|--:|--:|--:|--:|
| A | 131 | 63% | 2.29 | +0.400 | +50.0k |
| B | 166 | 67% | 1.78 | +0.303 | +32.1k |
| C | 408 | 43% | 0.79 | −0.098 | −41.5k |
| VETO | 90 | 32% | 0.34 | −0.394 | −28.3k |

<a id="s7-2"></a>

### 7.2 By structure

| Structure | n | win | PF | meanR | $ | MFE | MAE | gb | cap |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `bull_call_spread` | 612 | 54% | **1.40** | +0.140 | **+93.0k** | +0.87 | −0.54 | 0.62 | +0.16 |
| `bull_put_spread` | 476 | 70% | 0.92 | +0.068 | −10.8k | +0.76 | −0.98 | 1.29 | +0.09 |
| `bear_put_spread` | 677 | 33% | 0.76 | −0.135 | **−80.9k** | +0.76 | −0.74 | 0.98 | −0.18 |
| `long_call` | 13 | 15% | 0.03 | −0.227 | −11.8k | +0.47 | −0.57 | 1.22 | −0.48 |
| `long_put` | 9 | 22% | 0.36 | −0.160 | −5.4k | +0.51 | −0.54 | 1.06 | −0.32 |
| `straddle` | 36 | 28% | 0.89 | −0.058 | −2.2k | +0.42 | −0.43 | 1.02 | −0.14 |
| `strangle` | 13 | 31% | 0.26 | −0.005 | −19.2k | +0.67 | −0.57 | 0.86 | −0.01 |

Also in the book, all with n ≤ 6 (not readable): `short_put`, `butterfly`,
`iron_condor`, `calendar`. `bear_call_spread` has no v4 rows (intake-vetoed, §1.1).

`bull_call_spread` is +$93.0k against a whole-book −$9.7k. `bear_put_spread` is the
largest loss, −$80.9k. Naked longs (n=22 combined) have never worked.
Straddle/strangle `$` is dominated by a few large positions; do not read it.
v3 for reference: `bull_call_spread` PF 2.05 / +$79.4k, `bear_call_spread` `gb` 4.03.

<a id="s7-3"></a>

### 7.3 By model regime × structure

The **model** regime (the label on the analysis row) is the selection-relevant
one. Structures with n < 3 in a cell omitted.

| Model regime | Structure | n | win | PF | meanR | $ | MFE | MAE | gb | cap |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| BULL | `bull_call_spread` | 405 | 55% | 1.44 | +0.143 | +67.9k | +0.84 | −0.56 | 0.67 | +0.17 |
| BULL | `bull_put_spread` | 273 | 69% | 0.82 | +0.051 | −14.9k | +0.77 | −1.00 | 1.30 | +0.07 |
| BULL | `bear_put_spread` | 301 | 35% | 0.80 | −0.113 | −29.9k | +0.86 | −0.72 | 0.84 | −0.13 |
| BEAR | `bull_call_spread` | 10 | 70% | 2.75 | +0.407 | +4.6k | +0.94 | −0.37 | 0.39 | +0.43 |
| BEAR | `bull_put_spread` | 15 | 67% | 0.73 | +0.033 | −1.1k | +0.72 | −1.13 | 1.58 | +0.05 |
| BEAR | `bear_put_spread` | 40 | 28% | 0.54 | −0.244 | −10.9k | +0.53 | −0.92 | 1.72 | −0.46 |
| RANGE | `bull_call_spread` | 197 | 51% | 1.27 | +0.121 | +20.5k | +0.93 | −0.51 | 0.55 | +0.13 |
| RANGE | `bull_put_spread` | 188 | 72% | 1.11 | +0.096 | +5.1k | +0.74 | −0.93 | 1.24 | +0.13 |
| RANGE | `bear_put_spread` | 335 | 32% | 0.75 | −0.146 | −41.6k | +0.69 | −0.74 | 1.07 | −0.21 |

`bull_call_spread` has PF above 1 in **every** model regime, including BEAR
(too thin to read). `bear_put_spread` has PF below 1 in every regime. The v3
claim "PF > 1.7 in every regime" does not hold on v4. The structure ordering
holds; the size of the edge does not.

<a id="s7-4"></a>

### 7.4 By model regime × vol — where the §1 vetoes live

All structures pooled.

| Cell                         |   n |     win |       PF |  meanR |          $ |   MFE |   MAE |   gb |   cap |
| ---------------------------- | --: | ------: | -------: | -----: | ---------: | ----: | ----: | ---: | ----: |
| BULL + E-VOL                 |  50 |     46% |     0.63 | −0.052 |      −8.1k | +0.78 | −0.76 | 0.97 | −0.07 |
| BULL + L-VOL                 | 852 |     52% |     1.05 | +0.044 |     +18.6k | +0.82 | −0.71 | 0.87 | +0.05 |
| BULL + C-VOL                 | 123 |     52% |     0.98 | +0.071 |      −0.8k | +0.85 | −0.75 | 0.87 | +0.08 |
| BEAR + E-VOL                 |  62 |     44% |     0.84 | −0.030 |      −4.8k | +0.67 | −0.88 | 1.31 | −0.04 |
| **BEAR + H-VOL** ← §1.2 veto |  10 | **30%** | **0.26** | −0.345 |      −4.8k | +0.24 | −0.70 | 2.93 | −1.45 |
| RANGE + E-VOL                | 332 |     46% |     1.04 | −0.010 |      +6.4k | +0.78 | −0.77 | 0.98 | −0.01 |
| RANGE + H-VOL                |  39 |     44% |     0.47 | −0.186 |     −11.0k | +0.60 | −0.73 | 1.22 | −0.31 |
| RANGE + L-VOL                | 327 |     49% |     1.03 | +0.007 |      +3.2k | +0.77 | −0.69 | 0.89 | +0.01 |
| RANGE + C-VOL                |  54 |     43% |     0.60 | −0.130 |      −9.9k | +0.68 | −0.79 | 1.16 | −0.19 |

BEAR + H-VOL has the worst PF and `gb` on the board, but it is only 10 rows.
v3 had 64 rows and −$20.6k. The v4 window has almost no BEAR + H-VOL days, so
v4 neither confirms nor overturns §1.2. The largest `$` losses on v4 are
RANGE + H-VOL, RANGE + C-VOL and BULL + E-VOL. Those are not vetoed, and this
table is not a reason to veto them.

<a id="s7-5"></a>

### 7.5 The Tier-A cell — `bull_call_spread` by regime × vol

| Cell          |   n | win |   PF |  meanR |      $ |   MFE |   MAE |   gb |   cap |
| ------------- | --: | --: | ---: | -----: | -----: | ----: | ----: | ---: | ----: |
| RANGE + E-VOL |  74 | 46% | 1.10 | +0.071 |  +3.4k | +0.90 | −0.50 | 0.55 | +0.08 |
| RANGE + L-VOL |  98 | 51% | 1.21 | +0.111 |  +7.3k | +0.90 | −0.50 | 0.56 | +0.12 |
| RANGE + C-VOL |  18 | 56% | 1.64 | +0.110 |  +3.9k | +0.98 | −0.61 | 0.62 | +0.11 |
| BULL + E-VOL  |   8 | 25% | 0.34 | −0.274 |  −2.7k | +0.39 | −0.75 | 1.94 | −0.71 |
| BULL + L-VOL  | 345 | 54% | 1.35 | +0.122 | +47.4k | +0.81 | −0.56 | 0.69 | +0.15 |
| BULL + C-VOL  |  52 | 62% | 2.52 | +0.344 | +23.1k | +1.13 | −0.54 | 0.48 | +0.30 |
| BEAR + E-VOL  |   8 | 75% | 5.05 | +0.481 |  +4.8k | +1.06 | −0.35 | 0.33 | +0.46 |

Tier follows §2: RANGE and E-VOL cells are A, the rest B. Three things to notice:

- **BULL + C-VOL (PF 2.52, n=52) is the strongest large cell**, as in v3. It is B
  only because Tier A is defined as RANGE-or-E-VOL. Do not reorder on this: the
  tier ordering is judged on the tier as a whole (§7.1), not cell by cell.
- **The Tier-A cells are the weakest cells here.** RANGE + E-VOL fell from
  PF 2.99 on v3 to PF 1.10 on v4. This is the same fact as B beating A in §7.1.
- **The v3 BEAR + H-VOL `bull_call_spread` cell (n=9) has no v4 rows.** Cells
  with n=8 (BULL + E-VOL, BEAR + E-VOL) point opposite ways; read neither.

<a id="s7-6"></a>

### 7.6 The §3 geometry gate — `bull_put_spread`

| Cell | n | win | PF | meanR | $ | MFE | MAE | gb | cap |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **in band** (0.08 ≤ \|δ\| ≤ 0.20, DTE ≤ 59) | 166 | 73% | 1.03 | +0.029 | +1.2k | +0.79 | −1.09 | 1.38 | +0.04 |
| — of those, DTE 45–59 | 133 | 73% | 0.98 | −0.009 | −0.5k | +0.79 | −1.11 | 1.41 | −0.01 |
| out of band | 310 | 69% | 0.87 | +0.089 | −12.0k | +0.74 | −0.91 | 1.24 | +0.12 |

The gate is weaker on v4. PF and `$` still favour in band over out of band. But
`meanR` reverses, and the v3 win rate of 85% is now 73%. In band is roughly
break-even, not an edge. On v3 it was far better (see git history).
`gb` stays above 1 in band, which is why row 4 of §5 carries no stop.

<a id="s7-7"></a>

### 7.7 By mechanical cell — the exit-conditioning view

`mech_cell`, not the model regime. This is the label §5 keys exits off, so read it
to know what path a position is likely to walk, not to decide whether to deploy.
`PROD` is the stored sentinel for "no override cell" (see §0 labels).

| Mech cell | Structure | n | win | PF | meanR | $ | MFE | MAE | gb | cap |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| LVOL (n=1512) | `bull_call_spread` | 545 | 53% | 1.37 | +0.126 | +78.4k | +0.83 | −0.55 | 0.66 | +0.15 |
| | `bull_put_spread` | 378 | 70% | 0.87 | +0.064 | −14.9k | +0.75 | −0.98 | 1.31 | +0.09 |
| | `bear_put_spread` | 520 | 35% | 0.88 | −0.098 | −31.3k | +0.82 | −0.72 | 0.87 | −0.12 |
| BEAR_HE (n=189) | `bull_call_spread` | 30 | 70% | 2.36 | +0.405 | +10.6k | +1.49 | −0.47 | 0.31 | +0.27 |
| | `bull_put_spread` | 53 | 74% | 1.25 | +0.030 | +2.8k | +0.78 | −0.96 | 1.23 | +0.04 |
| | `bear_put_spread` | 97 | 28% | 0.40 | −0.297 | −35.3k | +0.50 | −0.86 | 1.71 | −0.59 |
| RB_EVOL (n=65) | `bull_call_spread` | 12 | 33% | 0.49 | −0.178 | −3.3k | +0.91 | −0.67 | 0.73 | −0.20 |
| | `bull_put_spread` | 19 | 63% | 0.98 | −0.089 | −0.1k | +0.74 | −1.13 | 1.52 | −0.12 |
| | `bear_put_spread` | 30 | 40% | 0.76 | −0.066 | −3.3k | +0.68 | −0.69 | 1.02 | −0.10 |
| PROD (n=84) | `bull_call_spread` | 25 | 60% | 2.14 | +0.275 | +7.3k | +1.00 | −0.41 | 0.41 | +0.28 |
| | `bull_put_spread` | 26 | 77% | 1.47 | +0.321 | +1.4k | +0.85 | −0.87 | 1.02 | +0.38 |
| | `bear_put_spread` | 30 | 20% | 0.36 | −0.329 | −10.9k | +0.50 | −0.76 | 1.53 | −0.66 |

`bear_put_spread` in BEAR_HE is the largest loss cell in the book, as in v3.
Its negative `cap` against a positive `MFE` says those positions show green and
then give it back, so §5 rows 2–3 still address an exit problem. LVOL is 1512 of 1850 rows: the v4 window is mostly calm, so the
override cells are thin. Cells with n < 30 are directional at best.

<a id="s7-8"></a>

### 7.8 Reading these numbers safely

- **In-sample.** Every cell here is the book the rules were measured on, and
  v4 is also the window the rules have been live in. Expect live results to be
  worse, not better.
- **Small n moves a lot.** Below ~30 rows, treat a cell as directional at best.
  n < 10 cells are printed for completeness only.
- **`$` and `meanR` can disagree** — `$` is position-size weighted. When they
  point opposite ways, one big position is doing the talking (§7.6 does this).
- **v4 rows, with v3 as the frozen base.** These tables are v4 (regenerated
  2026-10-12). The rules are v3-derived and not yet re-confirmed on v4. Where
  the two disagree, §7 says so in the prose under the table. v3 and v4 rows are
  never pooled. A v4 table reading weaker is not a rule change; changes go
  through [`research/deployment-evidence.md`](../research/deployment-evidence.md).
- **Costs differ by era.** v4 `$` and `meanR` are net of commission; v3 was gross.
  Part of every v3-to-v4 gap is this.
- **`bs_options_hist` proxy rows are excluded** (model-priced, attenuating).
  The book is real + `strike_expiry_tweak` only.

---

**Why these rules, what they were measured on, and what would revert them:**
[`research/deployment-evidence.md`](../research/deployment-evidence.md).
Config that implements the exits: `simulation.regime_exit` and
`simulation.structure_exit` in [`config/backtest.yml`](../config/backtest.yml).
