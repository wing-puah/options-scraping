## ticker_class — do index ETFs carry more reliable edge than single-stock groups?

_Registered 2026-10-07._

The operator accepted this file and took every recommendation on the same day. The answers
are folded into the text and listed under [Rulings at acceptance](#rulings-at-acceptance).
No outcome column was read before acceptance.

## Question

Is a play on a broad US index ETF (SPY, QQQ, IWM, DIA) more reliable than a play on a
single stock, once direction is held fixed? "Reliable" means four things together:
expectancy in R with a date-clustered CI, hit rate, share of the book's drawdown, and
stability across the two dominant windows, calendar years and half-years. Total P&L alone
never answers it.

## What this is NOT

- Not a ticker filter. Nothing here changes `ladder_tier()` or the deploy card. A positive
  verdict files "to be tested" in `research/deployment-evidence.md` and waits for the forward read.
- Not a per-ticker ranking. The unit is the group; single tickers appear only in the
  concentration check.
- Not a sector or country study. G3 (sector ETFs) and G4 (non-equity ETPs) are printed as
  context and are never graded.
- Not a regrouping exercise. The group table is fixed below. A different table is a new
  registration with its own ledger entry.

## The trial ledger

This study adds trials to the account-sim feasibility ledger
(`research/account-sim-feasibility-plan.md`, "A trial ledger"). The group map is one
configuration. The graded contrasts are the trials: one primary and four secondary, five
in all. Whether they count against the "three new arms on this era" cap is
[ruling 1](#rulings-at-acceptance): they go on a separate selection ledger, outside that cap, and
are also printed in the feasibility ledger. The report prints the ledger line it added.

## Definitions

### Group table, fixed here

The table was written 2026-10-07 18:35 +08, before any outcome column was read. It was hashed
(sha256 `6ce7373e…`) and then frozen. Membership comes from outside sources only:

- the ETF's prospectus mandate;
- GICS industry 4530 (semiconductors and equipment);
- the "Magnificent 7" list.

The first matching rule wins, in the order G1, G2, G3, G4, G6, G5, G7. So semis take
precedence over big tech, and NVDA lands in G6.

| Group | Object type | Members |
|---|---|---|
| G1 index | US broad index ETF | SPY, QQQ, IWM, DIA |
| G2 country | Single-country or regional equity ETF | FXI, EWZ, EWY, EWJ, EEM, EFA, KWEB, ASHR, INDA, EWW, EWT, MCHI |
| G3 sector | US sector or thematic equity ETF (context only) | SMH, SOXX, XLE, XLF, XLI, XLU, XLV, XLY, XRT, KRE, XBI, IGV, ITB, OIH, GDX, ARKK, DRAM |
| G4 non-equity | Commodity, rates, credit or crypto ETP (context only) | GLD, SLV, TLT, HYG, LQD, USO, IBIT, ETHA, BITO |
| G6 semis | GICS 4530 single name | NVDA, AMD, MU, TSM, INTC, AVGO, MRVL, ARM, LRCX, AMAT, KLAC, QCOM, TXN, CRDO, SKHY |
| G5 big tech | Magnificent 7 minus NVDA | AAPL, MSFT, AMZN, GOOGL, GOOG, META, TSLA |
| G7 rest | Every other single name | everything not listed above |

The pooled single-stock set S is G5 ∪ G6 ∪ G7. It excludes every ETF.

A ticker that first appears after acceptance goes to G7 unless it is an ETF. An ETF goes
to the group its mandate names. The report lists every ticker assigned that way.

### Direction

Direction comes from the canonical `structure`:

| Direction | Structures |
|---|---|
| Bull | `bull_*`, `long_call`, `short_put` |
| Bear | `bear_*`, `long_put` |
| Neutral | straddle, strangle, iron condor, butterfly, calendar |

Neutral rows are printed and never graded. Their count is at most 19 in every group.

### Metrics

All four metrics are graded per position, on the study basis `load_book()` returns.

- **Expectancy.** [meanR](../../glossary.md#meanr) with a
  [date-clustered CI95](../../glossary.md#ci95-date-clustered-bootstrap), from
  `protocol.boot_ci_by_date` with `BOOT_N` = 10,000.
- **Hit rate.** The share of positions with R > 0. _Resolved at build (2026-10-07):_ on P1 and T1 it is
  direction-standardised with the same weights as meanR.
- **Drawdown share.** Take the book's [maxDD](../../glossary.md#maxdd) episode on the R series
  summed by exit date. A group's share is its summed R inside that episode, divided by the
  episode's depth. It is printed beside the group's share of positions in the episode.
  _Resolved at build (2026-10-07):_ the episode is taken on the whole in-sample book, and a
  position's exit date is the grid day at `days_held`.
- **Path.** Median MFE, median MAE, and exit capture (R / MFE where MFE > 0), per group.
  These are reported, never graded, so a gap in R is never read without its path.

## Population and basis, fixed here

- **Era.** v4 only, from the bare exports in `backtests/to_evaluate/`. `load_book()` runs at
  its defaults: real rows plus `strike_expiry_tweak` proxy rows, `bs` excluded, and the
  proxy calibration gate on. Use `STUDY_ERA=current`.
- **In-sample window.** Signal dates before 2026-08-11. Dates from 2026-08-11 onward are the
  forward window, and no outcome is read there before the forward grade (see
  [Forward read](#forward-read)).
- **Trusted rows.** Rows with `fill_trusted` false are dropped. The report prints the count.
- **Cost basis.** The study splits rows by `cost_total`, never by the blank `cost_basis`
  column (lessons.md). The headline is net of cost. The gross figure is printed beside it.
  _Resolved at build (2026-10-07):_ gross R is stored R plus `cost_total` scaled by position size.
- **v3.** v3 is a SEPARATELY LABELLED replication, run with `--era v3`. It covers the same
  market path, so it is not out of sample. It grades the primary contrast only (see
  [v3 replication](#v3-replication)).

## Plan-time observations, disclosed

These counts come from a blind census of descriptor columns on the full v4 book
(1,871 positions over 280 dates, 2024-01-10 to 2026-09-22). No outcome column was loaded.
The in-sample window is smaller, and the build reprints these counts for it.

**Group sizes**

| Group | Positions | Dates | Tickers | Largest ticker |
|---|---|---|---|---|
| G1 index | 254 | 222 | 3 | IWM 53% |
| G2 country | 63 | 62 | 8 | FXI 35% |
| G3 sector | 175 | 143 | 17 | SMH 53% |
| G4 non-equity | 300 | 200 | 9 | GLD 35% |
| G5 big tech | 311 | 196 | 7 | TSLA 27% |
| G6 semis | 362 | 215 | 15 | NVDA 39% |
| G7 rest | 406 | 215 | 120 | COIN 11% |

DIA has no v4 positions. G1 is in effect IWM, SPY and QQQ.

**Confounds.** Group is confounded with direction and tier. Cramér's V for group × direction
is 0.28, and for group × tier it is 0.17. Structure family (0.13), horizon (0.14) and
mech_cell (0.08) are weaker.

| Group | Bear share | Debit-vertical share | Tier C share | Tier A positions |
|---|---|---|---|---|
| G1 index | 80% | 91% | 82% | 3 |
| G2 country | 19% | 60% | 40% | 5 |
| G5 big tech | 29% | 68% | 44% | 48 |
| G6 semis | 22% | 61% | 43% | 50 |
| G7 rest | 32% | 69% | 48% | 51 |

So a pooled comparison of G1 against S mostly compares bear, tier-C debit puts against bull
plays. The [Tier ladder](../../glossary.md#tier-ladder-abcveto) on v3 already separates C from
A/B, and lessons.md warns that a feature can re-sort structures. That is why the primary
contrast holds direction fixed and the tier cut is secondary.

**Cell power.** Positions (dates) on the full v4 book. Cells below 30 dates are marked ✗.

| Group | Bear | Bull | Tier B | Tier C |
|---|---|---|---|---|
| G1 index | 202 (201) | 50 (49) | 36 (36) | 208 (204) |
| G2 country | 12 (12) ✗ | 51 (51) | 27 (27) ✗ | 25 (25) ✗ |
| G5 big tech | 91 (81) | 211 (152) | 104 (80) | 137 (108) |
| G6 semis | 79 (70) | 274 (180) | 131 (97) | 157 (119) |
| G7 rest | 130 (101) | 257 (162) | 146 (92) | 194 (130) |

- **G2** can be graded only on bull plays.
- **G1 tier A** has 3 positions, so no tier-A contrast is possible.
- **G1 and G2** share only 54 dates.
- **v3 cells** are thinner. Only G1-bear clears 30 dates on the index side.

**Other disclosures.**

- **The v4 book is a backfill.** The v4 prompt was run after the fact on past dates; every
  AnalysisClaude row was created on or after 2026-08-12. Model recall of those dates is a
  standing risk this study does not remove.
- **NVDA and GE are on the rescaled-ticker list.** R and E are ratios and stay valid; no
  dollar figure is compared across tickers.

## Arms

| Object | Object type | Population | Role |
|---|---|---|---|
| P1 | G1 vs S, direction-standardised | in-sample, bear + bull | PRIMARY, graded |
| S1 | G1 vs G5, bear only | in-sample | secondary, graded |
| S2 | G1 vs G6, bear only | in-sample | secondary, graded |
| S3 | G1 vs G7, bear only | in-sample | secondary, graded |
| S4 | G1 vs G2, bull only | in-sample | secondary, graded |
| T1 | G1 vs S, tier C only, direction-standardised | in-sample | diagnostic, printed |
| T2 | G1 vs S, tier B only | in-sample | diagnostic, printed |
| C0 | all seven groups, pooled, unadjusted | in-sample | context, printed |
| R1 | real rows only, P1 repeated | in-sample | sensitivity, printed |

**Direction standardisation (P1, T1).** Each group's meanR is computed separately for bear
and bull positions. The two are then weighted by G1's own bear/bull mix, which is about
80/20 and is reprinted at build. The contrast is G1's meanR minus S's standardised meanR.
The CI comes from a date-clustered bootstrap that resamples dates jointly for both sides.
A stratum below 30 dates on either side is dropped, and its weight is renormalised. The
report prints the weights it used.

_Resolved at build (2026-10-07):_ tier is computed by `scripts/journal/lib/mapping.py::ladder_tier`, the
single encoding, not read from the loader's `tier` field. The loader's own copy lacks the
credit RANGE+L-VOL veto; the two agree on 1,763 of 1,850 rows.

## Gates

| Gate | Rule | On failure |
|---|---|---|
| GT0 power | Every graded side has 30 or more dates and 60 or more positions in the in-sample window. S4's G2 side needs 30 dates and 30 positions. | That contrast prints `UNDERPOWERED` |
| GT1 era | `load_book()` resolves era `current`, and the header names it | exit 3, as the loader does |
| GT2 map | Every in-sample ticker resolves to exactly one group. The newly assigned list is printed. | exit 1 |
| GT3 blind order | The group-table hash in the report matches the one in this file | exit 1 |
| GT4 reconcile | Summed R over all groups equals the book's summed R, within 1e-9 | exit 1 |

## Bar for a candidate

A contrast is **INDEX-MORE-RELIABLE** only when all six criteria hold:

1. **Expectancy.** The CI95 of the meanR difference (G1 minus comparison) excludes 0 on the
   positive side. For S1–S4 the CI is Holm-adjusted across the four. _Resolved at build (2026-10-07):_ each
   contrast gets a two-sided bootstrap p, then Holm step-down; the printed CI is at that
   contrast's Holm level. The family size is the number of secondary contrasts run (4 on
   v4, 3 on v3).
2. **Hit rate.** G1's hit rate is not lower than the comparison's, with the date-clustered CI
   of the difference reaching above 0.
3. **Drawdown.** G1's share of the book's maxDD episode is no larger than its share of
   positions in that episode.
4. **Window and year stability.** The difference keeps its sign without Mar–Apr 2025, without
   Feb–Apr 2026 (`protocol.window_cuts`), and in every calendar year where each side has 10 or
   more positions.
5. **Half-year stability.** This test is new here and is not A5. The difference keeps its
   sign in at least two-thirds of the half-years where each side has 10 or more positions.
6. **Concentration.** The difference keeps its sign with the largest ticker of each side
   removed, for example IWM from G1 and NVDA from G6.

The report also quotes [DEBIT_PROD](../../glossary.md#debit_prod) and the shipped-rule
baseline beside each contrast, as lessons.md requires. _Resolved at build (2026-10-07):_ the shipped-rule
baseline is the contrast restricted to tiers A/B, plus the shipped top-3/day ladder book.

## PBO / CSCV read

The selection being tested is "pick the best group". The CSCV in `lib/pbo.py` runs on a
T × N matrix:

- **N.** The five graded groups: G1, G2, G5, G6, G7.
- **T.** In-sample calendar months, each cell holding that month's group meanR on the
  direction-standardised basis. A month where a group has no position is left blank, never
  zero-filled.
- **S.** 16. When T is not a multiple of 16, the earliest months are trimmed until it is.
  This is decided by date only. With the in-sample window ending 2026-08-10 the expected T is
  32, which trims nothing.

_Resolved at build (2026-10-07):_ T runs from the first in-sample signal month through 2026-08, so a month
with no position is a blank row, not a dropped one. `cscv` refuses NaN, so cells are passed
as [value, present] with `pbo.ratio_metric`; a block's statistic is the mean over non-blank
months. PBO counts λ ≤ 0, so ties at the median count against the selection. The v3
replication runs the same CSCV and applies the same PBO reading.

The report prints three things:

- PBO;
- the in-sample argmax group;
- the probability that the argmax lands below the median out of sample.

A second CSCV over the bear stratum alone, with N = G1, G5, G6 and G7, is printed as a
diagnostic.

**Reading the PBO.** No threshold is registered elsewhere in the programme, so this file sets
one ([ruling 4](#rulings-at-acceptance)).

| PBO | Reading |
|---|---|
| ≤ 0.25 | Supports a verdict |
| 0.25 – 0.50 | The verdict is printed with "selection fragile" |
| > 0.50 | No group-level verdict ships. Every graded contrast reads `NULL`. |

PBO enters only as a veto, never as evidence for G1.

## Verdicts, worded now

| Verdict | When |
|---|---|
| INDEX-MORE-RELIABLE | P1 meets all six bar criteria and PBO is 0.25 or below |
| INDEX-LESS-RELIABLE (CONTRARY) | The mirror of the bar holds: the CI excludes 0 on the negative side, and criteria 4–6 hold with the sign reversed |
| MIX-ONLY | C0 shows a CI clear of 0 but P1 does not. The gap was direction or tier mix, not the ticker class. _Resolved at build (2026-10-07):_ C0's basis is the pooled, unadjusted G1-vs-comparison CI. |
| NULL | Neither direction meets the bar, or PBO is above 0.50 |
| UNDERPOWERED | GT0 fails for P1. The census is printed and nothing is concluded. |

S1–S4 take the same words, each qualified by its comparison group. A contrast meeting
criteria 1–3 but failing 4, 5 or 6 reads NULL, with the failed criterion printed beside it.
_Resolved at build (2026-10-07):_ criterion 5 with no qualifying half-year reads NOT MET.
An outcome not named here goes to the nearest label above with a printed qualification.

## Forward read

Dates from 2026-08-11 onward are not read in-sample. The forward grade re-runs P1 alone on
signal dates after 2026-10-07, under the same bar criteria 1–3. It reads `STILL-OPEN` until each
side has 30 or more forward dates. Then it reads `FORWARD-CONFIRMED` or `FORWARD-REFUTED`.
Dates from 2026-08-11 to 2026-10-07 are in neither window ([ruling 5](#rulings-at-acceptance)),
consistent with the `holdout_seal` draft. Forward dates are signal dates after 2026-10-07.

## v3 replication

`--era v3` runs P1 and S1–S3 only. G1-bull has 16 v3 positions, so P1 on v3 is in effect the
bear stratum and is labelled that way. The report goes to
`ticker_class-v3-<date>.txt`, and the v4 `-latest.txt` is copied aside first and restored
afterwards. The v3 verdict is printed as "v3 replication (same path)". It cannot confirm or
refute a v4 verdict; it can only note agreement.

## Anti-tuning

- The group table, the direction rule, the standardisation weights rule, the bar and the PBO
  threshold are fixed here.
- No regrouping, no new comparison group and no new stratum after a run. Each of those is a
  new registration and a new ledger line.
- No mech_cell, horizon, DTE, month or structure cut is graded. C0, T1, T2 and R1 are printed
  for reading, never for a verdict.
- No per-ticker verdict.

## Ship criteria

Nothing ships from this study. INDEX-MORE-RELIABLE or CONTRARY files a "to be tested" entry
in `research/deployment-evidence.md`. A `deployment-rules.md` change waits for
FORWARD-CONFIRMED and a separate operator ruling.

## Rulings at acceptance

The operator took every recommendation on 2026-10-07.

| # | Decision | Ruling |
|---|---|---|
| 1 | Trial cap | A separate selection ledger, outside the "three new arms" cap. The five trials are also printed in the feasibility ledger. |
| 2 | Unresolved tickers | SPCX, SNDK and SMCI stay in G7; SKHY stays in G6; DRAM stays in G3. The table is now frozen. |
| 3 | NVDA placement | G6, by the GICS rule. Criterion 6 tests its weight. |
| 4 | PBO threshold | 0.25 and 0.50, as written. |
| 5 | The 2026-08-11 → 2026-10-07 gap | Excluded from both windows. |
| 6 | QQQ | Stays in G1. |
| 7 | Proxy rows | Pooled, with R1 real-only printed. |

## Build notes

- New study `scripts/backtest_study/f1_selection/ticker_class.py`. Group table lives in that
  module verbatim, with its hash asserted by GT3.
- It reads only through `load_book()` and `protocol`. No outcome is recomputed from CSVs.
- It needs a `catalog.py` entry and an `arm-index.md` section before the suite is green.
