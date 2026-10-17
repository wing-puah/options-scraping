## hedge_structure — re-deriving the calendar candidate under a fixed pick rule

<!-- outcome:start -->
> Latest outcome: `H0 FILL NOT MET` (P1 fillable on 24.5% of deployed dates, 16.7% of worst-decile dates); `H2 NOT EVALUABLE` (parts a and c MET, part b n = 4) — 2026-09-28 · [record](../../study-results/f5_hedging/hedge_structure.md).
<!-- outcome:end -->

_Registered 2026-08-13._
_Renamed from `calendar_hedge` on 2026-09-08, after the question it answers in `scripts/backtest_study/f5_hedging/README.md`. No gate, arm, bar or verdict changed._

## The question

Does the calendar survive a pre-registered pick rule, a fixed universe, and a
strict fill definition?

This is a structure study. It takes the one leftover candidate from
`vol_sleeve`, the calendar, and asks again under rules written before the
number is re-read. The 2026-08-12 `vol_sleeve` run left that candidate. This
study re-derives its number on a smaller n. The number will come out
different, and that is the point. A bounded sweep of untried wrappers runs
SEPARATELY behind it (ARM S below).

| `vol_sleeve` figure (2026-08-12) | Value | CI | Population |
|---|---|---|---|
| Correlation with the deployed book | +0.088 | spans zero | — |
| Worst-decile return | +0.336 | [+0.124, +0.486] | n=13 rows / 7 dates — a per-structure subgroup of a POOLED gate |

## What this study is not

- It does not ship anything from ARM S. See What could ship.
- OUT OF SCOPE, so it is not re-litigated: ratio spreads and
  straddle/strangle structures. Ratio spreads are out on a harness constraint: frozen harness
  `_defined_risk_bounds` is None for unbounded net quantities, a harness
  constraint. Straddle/strangle is CLOSED 2026-08-12.
- It adds no calendar-specific exit. That would stack a second free parameter
  on the pick rule.

## Population and basis, fixed here

Everything the study stands on is fixed here, before any number is read: the
book, the code, the eligible dates, the sizing, the exit and the comparison
baselines.

**Book and code.**

- Book: `book.load_book(include_bs=False)`.
- Deployed book: `top_k_per_day(ladder_rank, k=3, A|B)`.
- Synthesis and pricing: `vol_sleeve.build_legs` + `_strike_index` and
  `bear_rewrap.{entry_date_for, net_entry, net_marks, leg_details,
  size_contracts, reconstructs}`, UNCHANGED.
- Exits: frozen `harness.replay` under `DEBIT_PROD`.
- Nothing in `harness.py`, `vol_sleeve.py`, `bear_rewrap.py`,
  `config/backtest.yml` or `docs/deployment-rules.md` is edited.

_Resolved at build (2026-09-24)._ `bear_rewrap.py` has been edited since this
was written, only to follow production's pricer. The edits are the B5
zero-bid mark, the side-aware and `open_side` entry fills, and the junk-quote
rule, each applied per row on its write-time basis. It also imports
production's shared entry and junk-mark functions from
`scripts/backtest/simulate.py` (`open_print_allowed`, `entry_day_fill`,
`carried_entry_fill`, `last_good_mark`, `junk_day_mark`) in place of restated
copies. No gate, bar, arm or published cell mean changed meaning. The only
output change is reconstruction on same-day entries, from 5 mismatches to 0
(1,154/1,159 → 1,159/1,159).

**Eligible dates and candidates.** Only dates where the ladder actually
deployed count. A candidate must be **fillable on the ladder's own entry
session**: both legs cached on `grid[0]`. The loose ≤5-day entry-lag rule that
`vol_sleeve` used does NOT apply, because you cannot decide to hedge Monday
and be filled Friday. The lag distribution under the loose rule prints as a
sensitivity. Two kinds of candidate are excluded and counted: `entry_net ≤ 0`
(crossed or stale market; vol_sleeve saw 2/183) and `far_exp ≤ near_exp`.

### Sizing

The study opens one hedge per day, at most ½ position:
`bear_rewrap.size_contracts` × 0.5 on the shipped $50k basis. This makes it
directly comparable with the shipped bear sleeve. The portfolio effect runs at
sleeve fractions f ∈ {0, 0.25, 0.50, 1.0}, exactly as `hedge_sizing` D3.

### Exit

The exit is `DEBIT_PROD` (pt .90 / sl .75 / tef .75), the profile the
candidate was measured under.

The frozen harness already handles calendars. The grid ends at the SHORT leg's
expiry, `_price_asof` never carries a leg past its own expiration, and
multi-expiry net marks are deliberately unclamped.

As a LABELLED SENSITIVITY only, the study prints the same table under
hold-to-near-expiry (pt/sl/tef all None). The sensitivity may not change the
verdict. It exists so the write-up can say whether the verdict is
exit-shape-dependent.

### Baselines

The study uses two baselines. `vol_sleeve` compared against no hedge only.

- the deployed ladder alone at $50k;
- the ladder PLUS the SHIPPED bear hedge sleeve (`|delta|` descending, ½ size,
  1/day).

The calendar must beat the hedge the operator already has, not just the empty
seat.

## What it compares

The pick rules are decision-time only, and the list is CLOSED here.

| Arm | Rule |
|---|---|
| **P1** | Nearest-ATM: min \|K*−S\|/S among the day's fillable calendars |
| **P2** | Longest near-leg DTE |
| **P3** | Shortest near-leg DTE |
| **P4** | Widest expiry gap |
| **P5** | Same ticker as the day's top-ranked deployed position (P1 tie-break) |
| **P6** | ETF underlyings only, then P1 |

**THE RULE IS P1.** It uses geometry, not score. It is the closest analogue of
the shipped bear-hedge convention, and implicitly what produced the vol_sleeve
number. P2–P6 print as a robustness fan. A P2–P6 pass with P1 failing is a
candidate for a future window, never a ship.

### ARM S — the structure sweep

ARM S runs only AFTER the H arm has printed, only under `--arm S`, in a
separate invocation and report file.

| Arm | Structure | Legs | Plan-time cache feasibility |
|---|---|---|---|
| S1 | `put_calendar` | short near put + long next-cached-expiry put at K* | 577/786 groups |
| S2 | `put_diagonal` | short near put at K*, long next-expiry put at nearest cached strike BELOW | 561/786 |
| S3 | `narrower` | bear vertical, short pulled UP to the highest cached strike below the long; the mirror of `sub_wider` | — |
| S4 | `wider` | rerun UNCHANGED from `bear_rewrap` as an internal plumbing control; known answer −0.056 | — |
| S5 | `long_put` | rerun UNCHANGED from `bear_rewrap` as an internal plumbing control; known answer +0.002, failing 2026 | — |
| S6 | `iron_condor` | bull-put + bear-call wings at nearest cached-or-scraped strikes around K*, same expiry | 214/786, far short |

S6 is included ONLY if the leg scrape reaches ≥60% four-leg group coverage.
Otherwise S6 is NOT EVALUABLE, with the coverage number printed.

Missing legs are scraped FIRST by `scripts/collector/fetch_sweep_legs.py`
(resumable: one cache file per contract, `--limit` chunks, skip-existing,
manifest CSV) into the same cache under the same naming. Synthesis results are
checkpointed to `backtests/sweep_cache/synth_results.csv` so an interrupted
run resumes instead of restarting.

**MULTIPLICITY:** A sweep cell is a CANDIDATE only if all three hold:

- its worst-decile CI excludes zero at Bonferroni α = 0.05 / (n_structures ×
  n_pick_rules);
- it is right-signed every year present;
- it clears H0.

**Nothing in ARM S can ship from this run.** The maximum verdict is
carry-to-next-window.

## Gates

These must pass before any hedge number is read.

- **H0 FILL:** P1 produces a fillable hedge on ≥60% of deployed-book dates AND
  ≥60% of the deployed book's worst-decile dates. Both print side by side.
  The gate fails on either. Unfillable days are carried as f=0 in every
  portfolio line, never dropped from the denominator. A hedge unavailable
  exactly when needed is not a hedge.
- **H0b FRESHNESS:** the headline must survive `stale_at_cap ≤ 3` and
  `pct_real ≥ 0.5` (`vol_sleeve.mark_quality`).
- **R1 RECONSTRUCTION:** book calibration quoted.
- **R2 RECONSTRUCTION:** `bear_rewrap.reconstructs` on every source row
  feeding the universe.
- **R3 RECONSTRUCTION:** the deployed-book replay reproduces the deployed line
  the 08-12 `vol_sleeve` report printed on the same exports.
- **R4 RECONSTRUCTION (the critical one):** with the pick rule disabled and
  the LOOSE fill rule, this study must reproduce vol_sleeve's calendar cell
  EXACTLY. Otherwise the gap between +0.336 and whatever H2 prints cannot be
  attributed (pick rule vs re-implementation drift). Non-zero exit on
  failure.

The four R checks verify that the plumbing is the plumbing it claims.

| Check | Must reproduce |
|---|---|
| R3 | 220 positions / 90 dates / $63,553 |
| R4 | 183 rows, meanR +0.158, $28,059, exit mix time_exit 124 / pt 28 / dollar_stop 22 / cap_open 5 / sl 4 |

## Bar for a candidate

H1–H5 mirror hedge_sizing D1–D5, renamed to avoid confusion.

1. **H1 STANDALONE** (context, NOT a gate): mean E and R of the P1 sleeve,
   date-clustered CI, per-year signs. Negative standalone does not fail a
   hedge.
2. **H2 HEDGE CONTRIBUTION (the primary gate, D2's rule verbatim):** on
   deployed-book dates, all three of:
   - (a) date-level correlation of the two daily series < 0;
   - (b) mean sleeve R on the deployed book's worst-decile dates > 0 with
     date-clustered CI excluding zero;
   - (c) worst-quartile tail positive in ≥2 evaluable years.
3. **H3 SIZING** (D3 verbatim): the largest f whose max drawdown AND worst
   single date are both no worse than f=0.
4. **H4 CONDITIONAL PICK:** within-date paired comparison of P1 vs the day's
   average fillable calendar and vs each of P2–P6.
5. **H5 TIMING** (POST-HOC, labelled): gates on `mech_cell == BEAR_HE`, H-VOL,
   RANGE+C/L-VOL, and earnings-inside-DTE. The last is vol_sleeve's one
   CI-clearing conditional. H5 is candidate-only.

   | Conditional | non-conditional | CI | n |
   |---|---|---|---|
   | earnings-inside-DTE +0.356 | −0.035 | [+0.111, +0.664] | 42 |

**POWER STOP.** If the P1 worst-decile cell has fewer than 10 positions,
H2(b)'s CI is NOT read. H2 is then recorded **NOT EVALUABLE**, not "failed".
Pre-run expectation: the cell will be ≈7–9 under a 1/day rule. NOT EVALUABLE
is a likely and correct outcome, and the honest conclusion is "needs new
dates".

## What could ship

Nothing changes `config/backtest.yml`. The maximum outcome is an optional
second hedge sleeve added to `docs/deployment-rules.md` §4. It requires H0
MET ∧ H0b not flipping the verdict ∧ H2 MET ∧ H3 deployable at f ≥ 0.25.
Anything less is a candidate.
