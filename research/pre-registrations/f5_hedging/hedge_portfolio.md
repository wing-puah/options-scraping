## hedge_portfolio — does exposure-triggered proxy hedging cut the book's drawdown?

<!-- outcome:start -->
> Latest outcome: mechanism `UNDERPOWERED`; `ARM M` `MEASUREMENT-ONLY` — 2026-09-28 · [record](../../study-results/f5_hedging/hedge_portfolio.md).
<!-- outcome:end -->

_Registered 2026-08-29._

## The question

When the open book is CONCENTRATED in one correlated cluster, does a long put on
that cluster's proxy reduce the book's
**[mark-to-market](../../glossary.md#mark-to-market-basis) drawdown**? The
comparison is the same concentrated book, carried unhedged.

The operator queued it on 2026-08-28 ("the hedge programme's next question is
MAX DRAWDOWN, not timing"). The same day's note limits it to their
exposure-conditional practice: *"I hedge when I hold a lot of
correlated positions (semis → SMH, tech → QQQ), I see a specific risk, AND the
analysis says people are hedging."*

Renamed from `hedge_exposure` on 2026-09-08, after its question in
`scripts/backtest_study/f5_hedging/README.md`; nothing else changed.

## What this study is not

- **Not a timing study.** `hedge_timing` tested market-state triggers (chop /
  gap / streak): 0 of 9 candidates. No arm here is keyed to a calendar or
  market-state condition. A trigger session that is a gap-up day is incidental;
  the drafted §4 GAP prohibition (the gap AS the reason to hedge) is not
  reopened.
- **Not a selection study.** Selection is untouched in every arm. `hedge_sizing`
  D1 settled that no rule identifies a profitable bear play ("Stop looking for
  one").
- **Not a worst-decile tail study.** The 2026-08-13 wall (~9 worst-decile dates
  cannot power a worst-decile criterion) is a constraint, not a gate to
  re-attempt. Every primary metric is **path-shaped**, over all 504 open
  sessions.
- **Not a test of the §4 bear sleeve.** The book's own bear row appears only as
  an instrument comparison (ARM B). The sleeve is operator policy, exempt from
  data-driven removal; this study cannot remove it.
- **Not `concurrency_correlation`** (registered 2026-08-22, before this one).
  That study asks whether concentration DEGRADES per-position outcome; its
  remedy is to DEPLOY LESS (ARM C/ARM K ceilings that refuse a pick). This one
  asks whether concentration can be OVERLAID with a hedge. The counterfactual,
  fixed by the operator's scope note, is the unhedged concentrated book,
  explicitly *not* "open a long instead". Unit (session vs position), outcome
  (book drawdown vs R) and remedy all differ. **Neither study's result may be
  cited as evidence for the other's**, in either direction.
- **Not about long-dated hedging.** The book is ≤60-DTE by accident of the
  ladder. Hedge expiries are bounded to 20–120 DTE.
- **The constituent stratum is reported, not concluded from** (expected
  POWER-STOPPED; see Plan-time observations).

## Population and basis, fixed here

- **Era `v4` (`current`), and only v4.** An era mismatch refuses (exit 3); a
  thin era refuses (exit 2). v3 is neither pooled nor replicated:
  `hedge_timing` disclosed its v3 window as PARTIALLY CORRELATED and forbade
  pooling.
- **Book, RATIFIED (operator, 2026-08-31; consolidated into this file
  2026-09-02).** The population is `all`: the literal
  `load_book(include_bs=False)` call (`real` and `strike_expiry_tweak` pricing,
  proxy calibration gate ON, no `bs_options_hist` rows). That is
  **996 rows / 145 signal dates / 2024-01-10 .. 2025-11-04** (real 485 +
  `strike_expiry_tweak` 511). A `tweak` row is a real Barchart price for a
  nearby strike/expiry, and the operator does not trade a proposed leg's strike
  and expiry exactly. `real` alone (485 rows / 140 signal dates) is a
  REPORTED STRATUM only, never the concluding population.
- **The plan-time disclosures describe the `real` stratum, not the ratified
  book.** The exposure table, the concentration quantiles and the 504-session
  universe below were computed on `real` alone. The figures that describe the
  ratified population are the ones the study's own run prints.
- **Session universe**: the 504 trading sessions on which at least one position
  is open, from `[signal_date, signal_date + days_held]` (~3.6× the
  signal-date count). The drawdown path is computed on it.
- **Equity curve**: MARK-TO-MARKET, built from `daily_pnl_csv` (populated
  485/485). The realized-on-close curve (`account_sim.equity_curve`, bucketed by
  `exit_sess`) is computed alongside for comparability; no verdict is read
  from it.
- **Sizing / capital**: `config/account-sim.yml` at its committed values,
  through `account_sim`'s ledger and `admission()`. The hedge is admitted after
  the day's signal picks, following the existing sleeve pattern.

### The sector map

The sector map is fixed HERE, before any concentration was computed. It has 11
clusters, each with one proxy instrument; the residual is BROAD → SPY. It may
not be edited after this file is committed.

- `SEMIS` → **SMH**: NVDA AMD MU TSM AVGO SMCI AMAT ARM MRVL INTC QCOM CRDO SMH
- `MEGATECH` → **QQQ**: AAPL MSFT META GOOGL GOOG AMZN NFLX TSLA ADBE CRM ORCL PLTR APP INTU CSCO IBM U SNOW NTNX AKAM DELL SHOP UBER DIS TMUS QQQ
- `CRYPTO` → **IBIT**: COIN MSTR MARA IBIT BITO ETHA HOOD IREN
- `RATES` → **TLT**: TLT
- `CREDIT` → **HYG**: HYG LQD
- `METALS` → **GLD**: GLD SLV GDX AGI
- `ENERGY` → **XLE**, but UNHEDGEABLE (see below): XOM CVX HES VLO USO OIH OKLO CCJ VST CEG DUK RUN BE FSLR GEV MP X
- `FINL` → **XLF**, but UNHEDGEABLE (see below): JPM GS WFC COF DFS AXP BX CMA KRE GPN SOFI NU UPST AFRM XLF
- `INTL` → **EEM**: EEM EFA FXI KWEB EWZ BABA PDD SE
- `SMALL` → **IWM**: IWM
- `BROAD` → **SPY**: every ticker not named above

**Four clusters are UNHEDGEABLE.** They keep their identity in the
concentration measure, but no hedge can be placed for them:

- `XLF` fails the fill gate (15.0% band / 40.7% nearest).
- `IBIT` (22.9%) and `EEM` (41.4% band) fail the fill gate.
- `XLE` is on `underlying.rescaled_tickers()` at a 0.5000 median relative
  difference over 267 overlaps, so the repo's own convention withholds it.

Together ENERGY, FINL, CRYPTO and INTL are 10.2% of book exposure. **They are
NOT folded into BROAD/SPY**: that would corrupt BROAD's trigger with exposure
SPY does not track. It would also break `concurrency_correlation`'s rule that
an unmapped ticker "is its own bucket — never folded into a named sector". If a
session's top cluster is unhedgeable, it is **carried at f=0 and counted
against the fill gate**.

**The sector map is shared, not study-local.** `concurrency_correlation`'s
ARM K uses the same static ticker→sector map, so two studies cannot disagree
about "same sector" (the failure `mapping.CONFIDENCES` and `ladder_tier()`
prevent). The single encoding is `scripts/backtest_study/lib/sectors.py`;
whichever study is built second imports it.

## Plan-time observations, disclosed

All of these were measured from INPUTS before any outcome column was touched.
The exposure table, the concentration quantiles and the 504-session universe
describe the `real` stratum. The full working is in
`research/archive/18-hedge-programme-exit-basis-and-text-loop.md` under
2026-08-29.

### The book is not shaped like the practice being tested

62.7% of book exposure is DIRECT: the position is in the proxy ETF itself.
Only 37.3% is CONSTITUENT: a single name inside a proxy, the operator's literal
practice. CREDIT and METALS are each 92% direct; SMALL and RATES are 100%.

| cluster | rows | share of exposure | direct% |
|---|---|---|---|
| CREDIT | 25 | 20.8% | 92.2 |
| MEGATECH | 115 | 20.6% | 20.5 |
| SMALL | 39 | 13.4% | 100.0 |
| BROAD | 41 | 11.9% | 69.9 |
| SEMIS | 106 | 9.4% | 20.5 |
| RATES | 28 | 8.4% | 100.0 |
| METALS | 29 | 5.2% | 92.2 |
| CRYPTO | 45 | 4.0% | 25.8 |
| INTL | 28 | 3.0% | 30.3 |
| FINL | 15 | 2.4% | 19.9 |
| ENERGY | 14 | 0.8% | 0.0 |

### Trigger census (no outcome column read)

Concentration is the largest absolute per-cluster signed delta notional as a
share of book gross, per session, over 504 sessions.

| concentration | median | p75 | p90 |
|---|---|---|---|
| any-cluster | 0.301 | 0.398 | 0.572 |
| constituent-only | 0.118 | 0.174 | 0.256 |

| threshold τ | any-cluster sessions | constituent-only sessions |
|---|---|---|
| 0.30 | 256 (51%) | 40 (8%) |
| 0.35 | 179 (36%) | 24 (5%) |
| 0.40 | 120 (24%) | 16 (3%) |

**Consequence, accepted now.** A constituent-only trigger has 16–24 qualifying
SESSIONS, far below the ≥25 DATE floor once date-clustered. The constituent
stratum is therefore expected to be POWER-STOPPED. It is a stratum to report,
not an arm to conclude from.

### Fill coverage, per proxy, over the 140 book dates

- **Band rule**: expiry 25–75 DTE, strike within ±5% of that date's close.
- **Nearest-available**: nearest strike at-or-below spot, expiry nearest 45 DTE
  within 20–120.

| proxy | band | nearest | gate (band ≥60%) |
|---|---|---|---|
| IWM | 86.4% | 99.3% | PASS |
| TLT | 78.6% | 95.7% | PASS |
| QQQ | 77.1% | 99.3% | PASS |
| HYG | 74.3% | 97.1% | PASS |
| SPY | 71.4% | 94.3% | PASS |
| GLD | 68.6% | 81.4% | PASS |
| SMH | 60.0% | 99.3% | PASS (at the gate) |
| EEM | 41.4% | 67.9% | FAIL band |
| IBIT | 22.9% | 38.6% | FAIL |

CRYPTO and INTL have no band-rule instrument (7.0% of exposure combined). Per
`hedge_structure`'s principle, *"A hedge unavailable exactly when needed is not
a hedge"*: such sessions are **carried at f=0 and counted against the fill
gate, never dropped from the population**.

**Coverage is not uniform in time.** Under the band rule, SMH and QQQ are strong
in 2024 and collapse in 2025Q3/Q4 (SMH .45/.00, QQQ .20/.00). GLD and EEM are
weak in 2024Q1 and strong later. The
nearest-available rule is ~flat. Hence both rules are registered, and the
ex-window cuts are mandatory.

### Lookahead: the analysis prose carries irreducible model-recall risk

All 1,893 `AnalysisClaude` rows carry `created_datetime` in 2026-08, including
January-2024 sessions: the v4 book is a backfill. For a study keyed to the
model's WORDS, that matters: `hedge-pressure 35/100`
written against 2024-03-20 may be model recall, not a read of that day's tape.
This is the defect `s06_recommend.judge()` and `live_select.py` document, and
it cannot be bounded away. ARM P (no prose) and the rule that **no verdict may
rest on a prose-conditioned arm alone** contain it.

### Hedge-flow signal extraction, fixed here

The signal is the numeric `hedge-pressure NN/100` embedded in `regime` prose,
parsed case-insensitively with
`r"hedge[- ]pressure[^0-9]{0,15}(\d{1,3})\s*/\s*100"`. It covers 103 of 158
analysis dates (65%). It is constant within a date (0 dates carry two values).
It spans 15–83, median 35. **A date with no parse is treated as NO SIGNAL
(do not hedge)**, the conservative direction. A naive date-level keyword match
was REJECTED at plan time: it fires on 157 of 158 dates and does not
discriminate.

### The measurement finding that motivated ARM M

`account_sim.equity_curve()` buckets P&L by `exit_sess`; its `print_equity()`
states *"Open positions are not marked to market, so this understates
intra-position drawdown."* Every hedge verdict on record rests on that curve:
`hedge_sizing` D3, `hedge_structure` H3, `hedge_timing` H4, and the −$10,968
baseline this study was queued against. A hedge cushions exactly the path that
curve omits.

## What it compares

The grid is 3 τ × 3 f = 9 cells per arm. It is fixed here and not expanded
later.

- τ, the concentration threshold: {0.30, 0.35, 0.40}.
- f, the hedge size as a fraction of a standard position's risk: {0.25, 0.50,
  1.00}.

| Arm | What it does | Kind |
|---|---|---|
| [hedge_portfolio ARM M](../../arm-index.md#hedge_portfolio) | Unhedged book, both curves | measurement |
| hedge_portfolio ARM C | Proxy put when concentration ≥ τ | hedge arm, no prose |
| hedge_portfolio ARM CS | ARM C plus `hedge-pressure ≥ 50` | hedge arm, prose |
| [hedge_portfolio ARM P](../../arm-index.md#hedge_portfolio-arm-p) | ARM C on ARM CS's sessions, no prose | INERT AS REGISTERED |
| hedge_portfolio ARM N | Random admission | null |
| hedge_portfolio ARM B | Bear row as instrument | instrument comparison |
| hedge_portfolio ARM R | Proxy underlying short | always-fillable reference |

### ARM M — measurement

The SAME unhedged book on both curves: max drawdown, Ulcer index and
time-under-water, mark-to-market versus realized-on-close. It runs first and
gates nothing else.

### ARM C — concentration-gated proxy put

On any session where concentration ≥ τ, ARM C buys a long put on the
concentrated cluster's proxy, sized at fraction f of a standard position's
risk. The band rule is primary; nearest-available is the registered
sensitivity. **Carries no prose.**

Resolved at build (2026-09-28): a usable price for the put is production's entry
fill and daily mark (see G-FILL), not the raw `_mark`.

### ARM CS — concentration × hedge-flow signal

ARM C, additionally requiring `hedge-pressure ≥ 50` (fixed here; the median is
35, so this is the upper ~third of parsed dates). Prose-conditioned.

### ARM P — prose-free counterpart

ARM C restricted to exactly the sessions ARM CS would hedge on, minus the prose
condition. Its intent is to isolate how much of any ARM CS effect is the prose
rather than the concentration underneath it. As registered it cannot: CS's
sessions without the prose condition are still CS's sessions, so both arms
hedge the same sessions. The arm is **INERT AS REGISTERED**. Redefining it
would be a post-hoc arm, so it stays as written.

### ARM N — random-admission null

ARM N hedges on a random set of sessions matched in COUNT and in
date-clustering to the triggered set, over 200 seeds. Following
`portfolio_delta`'s ARM N: **an arm must beat ARM N's 95th percentile, not
merely beat the unhedged book.**

### ARM B — instrument comparison

ARM C with the book's own bear row as the instrument instead of the proxy put.
`hedge_sizing` D3 and `hedge_timing` H4 found it cannot cut max drawdown on the
close-bucketed curve. ARM B asks only whether that survives on the
mark-to-market curve.

### ARM R — always-fillable reference

ARM C with a delta-equivalent SHORT in the proxy UNDERLYING instead of a put.
With no option cache and no fill gate, it keeps the study from ending on fill
coverage alone (as `hedge_structure` did). **ARM R is a floor on
feasibility, not a recommendation: it has a different loss shape from a put and
is not an instrument the operator trades.**

## How it is judged

- **Unit**: the session. Every confidence interval uses date-clustered
  resampling: never row-level, never session-level-independent.
- **Primary metric**: **max drawdown in dollars** on the mark-to-market book
  equity curve, hedged versus unhedged.
- **Co-primary, path-shaped**: **Ulcer index** (RMS of percentage drawdown
  across all open sessions) and **time-under-water** (share of open sessions
  spent below the running peak). Having a denominator, they do not inherit the
  ~9-date worst-decile wall.
- **Secondary, reported, never concluded from**: total P&L, worst single
  session, realized-on-close max drawdown.

**Asymmetric reading rule, binding.** Results are always stratified DIRECT
versus CONSTITUENT. A positive result in the DIRECT stratum (a put on an ETF the
book already holds) **may NEVER be cited as evidence for the operator's
constituent-to-sector-proxy practice.** It is a different action. A NULL in
DIRECT is likewise not evidence against the constituent practice. This mirrors
`hedge_timing`'s T-DECLINE-BROAD rule.

## Gates

- **G-ERA**: v4 or refuse (exit 3). A thin era refuses (exit 2).
- **G-FILL**: a hedge must be fillable on **≥60% of triggered sessions** under
  the band rule. Unfillable sessions are carried at f=0, never dropped. Below
  60%, the proxy-put arms are **NOT EVALUABLE** (not "failed") and only ARM R is
  read.

  Resolved at build (2026-09-28), operator ruling: "fillable" is production's
  entry rule, imported from `scripts/backtest/simulate.py` into
  `lib/hedge_instrument.py`. A put bought at the session close is a same-day
  entry, so `open_print_allowed` keeps the Open print out.

  `carried_entry_fill` prices the session's own row: the mark on a clean quote,
  the day's trade print on a junk quote that traded, and no fill on a junk quote
  that did not (`_is_junk_quote`). Until then any `_mark` on the session
  counted, junk quotes included. Daily marks follow `junk_day_mark`. The gate's
  name, its 60% bar and the f=0 carry are unchanged.
- **G-POWER**: **≥25 trigger DATES** (date-clustered, not sessions) per cell.
  Below that, the cell is UNDERPOWERED and carries no verdict.
  **UNDERPOWERED is not a lean.**
- **G-BLIND**: the trigger must be computable with outcome fields stripped. It
  reuses `account_sim`'s `blind_records` / `BlindRec`. If the triggered session
  set under blinded records is not byte-identical to the sighted run, the study
  prints `LOOKAHEAD DETECTED` and refuses.
- **G-MTM**: the mark-to-market curve must reconcile to the realized-on-close
  curve at every position's exit. Cumulative MTM P&L at exit equals the booked
  realized P&L, per position, to within rounding. A mismatch exits non-zero.
- **G-CENSUS**: the power census prints before any outcome column is read.

## Bar for a candidate

A cell is a CANDIDATE only if ALL of these hold:

1. **Max drawdown AND worst single session are both no worse than f=0**, judged
   on dollars. This criterion is carried verbatim from `hedge_sizing` D3.
2. The improvement in **at least one co-primary path metric** (Ulcer index or
   time-under-water) has a **date-clustered CI excluding zero** at
   Bonferroni-corrected α = 0.05/9.
3. It **beats ARM N's 95th percentile** on that same metric.
4. It is **positive in ≥2 of the book's years.**
5. **Both ex-window cuts** (`protocol.DOMINANT_WINDOWS`) retain the sign.
6. **Every leave-one-date-out fold** retains the sign.
7. **NOT A DELTA REDUCTION IN DISGUISE.** The cell's improvement must exceed
   ARM R's improvement at the same τ and f. ARM R shorts the proxy underlying to
   the same delta, so it carries the pure exposure-reduction effect and none of
   the convexity a put adds. A put arm that merely matches ARM R is reported as
   **A RESTATEMENT OF DELTA REDUCTION** and does not clear the bar. This is the
   control `concurrency_correlation`'s X7 applies to its ceilings, and the
   reason `portfolio_delta`'s already-failed delta arms are not re-litigated
   here.

## Verdicts, worded now

| Token | What it means |
|---|---|
| **MECHANISM-FOUND** | ≥1 cell clears every clause of the bar. States the cluster, τ, f, instrument, and which path metric moved |
| **NULL** | Gates pass, no cell clears the bar. Reads as: *concentration-triggered proxy hedging does not reduce this book's drawdown either.* |
| **CONTRARY** | A cell's drawdown is reliably WORSE than unhedged under the same bar clauses. Would corroborate `hedge_timing`'s v3 always-on finding on a different trigger and a better curve |
| **UNDERPOWERED** | G-POWER fails. No direction is quoted, ever |
| **NOT EVALUABLE** | G-FILL fails for the proxy-put arms. Only ARM R is read, and it may not be quoted as evidence about puts |
| **MEASUREMENT-ONLY** | ARM M shows the two curves differ materially, but no hedge cell clears the bar. A real, reportable outcome: it would mean the programme's prior nulls were measured on a blind instrument, and that no hedge mechanism has been found yet |

**Prose rule, binding.** No verdict may rest on ARM CS alone. If ARM CS clears
the bar and ARM P does not, the reported verdict is **PROSE-CONDITIONED,
LOOKAHEAD-UNRESOLVED**: a candidate for a forward window, never a ship.

## Anti-tuning

- The **sector map, the τ grid, the f grid, the hedge-pressure cut (≥50), the
  fill rules and the DTE window are all fixed in this file** before any outcome
  column is read. None may be edited after commit.
- **9 cells, Bonferroni α = 0.05/9.** One pre-registered grid fixes the
  multiplicity half of the `hedge_structure` wall. No second grid may be added
  to this study.
- **No post-hoc threshold search.** If no τ in the grid triggers ≥25 dates, the
  answer is UNDERPOWERED, not a new τ.
- **No stored expected figure.** No gate fingerprints a snapshot. Every count
  above is a plan-time observation, not a checksum.
- **No annualised figure, Sharpe, or time-to-recover** is computed or printed.
- If the study is re-run on a grown option cache, the cache state is recorded in
  the report header. (`hedge_structure` R4 had to be frozen to a pre-scrape
  snapshot because nearest-strike re-picks legs on a grown cache.)

## What could ship

**NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF.**

- **MECHANISM-FOUND** produces a DRAFTED amendment to
  [`docs/deployment-rules.md` §4](../../../docs/deployment-rules.md#s4), held in
  `research/`. This is draft-and-hold, as the operator chose for the GAP
  prohibition.
- **NULL** or **CONTRARY** ships nothing. It is recorded in
  `research/deployment-evidence.md` as closing the queued max-drawdown question.
- The §4 sleeve is operator policy and is not removed by any outcome here.
