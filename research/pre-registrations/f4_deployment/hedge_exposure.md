## hedge_exposure — does exposure-triggered proxy hedging cut the book's drawdown?

_Registered 2026-08-29._

## Question

When the open book is CONCENTRATED in one correlated cluster, does adding a
long put on that cluster's proxy reduce the book's **mark-to-market drawdown**,
versus carrying the same concentrated book unhedged?

The operator queued this mechanism study on 2026-08-28 ("the hedge
programme's next question is MAX DRAWDOWN, not timing"). The same day's note
scopes it to their actual practice, which is exposure-conditional:
*"I hedge when I hold a lot of correlated positions (semis → SMH, tech → QQQ),
I see a specific risk, AND the analysis says people are hedging."*

## What this is NOT

Scope limits, fixed here.

- **Not a timing study.** `hedge_timing` tested market-state triggers (chop /
  gap / streak) and returned 0 of 9 candidates. No arm here is keyed to a
  calendar or market-state condition. Where a trigger session happens to be a
  gap-up day, that is incidental; the drafted §4 GAP prohibition speaks to the
  gap AS the reason to hedge and is not litigated here.
- **Not a selection study.** Selection is untouched in every arm. `bear_deploy`
  D1 settled that no rule identifies a profitable bear play ("Stop looking for
  one"); nothing here reopens it.
- **Not a worst-decile tail study.** The 2026-08-13 wall — ~9 worst-decile
  dates cannot power a worst-decile criterion on this book — is the constraint
  this design is built around, not a gate to re-attempt. Every primary metric
  here is **path-shaped**, computed over all 504 sessions on which the book is
  open, not over a tail cell.
- **Not a test of the §4 bear sleeve.** The book's own bear row appears only as
  a pre-registered instrument comparison (ARM B). The sleeve is operator policy
  and exempt from data-driven removal; this study cannot remove it.
- **Not `concurrency_correlation`.** That study (registered 2026-08-22) asks
  whether concentration DEGRADES per-position outcome, and its remedy is to
  DEPLOY LESS (ARM C/ARM K ceilings that refuse a pick). This study asks
  whether concentration can be OVERLAID, and its remedy is to add a hedge; the
  counterfactual is fixed by the operator's scope note as the unhedged
  concentrated book, explicitly *not* "open a long instead". Different unit
  (session vs position), different outcome (book drawdown vs R), different
  remedy. **Neither study's result may be cited as evidence for the other's.**
  If both run, a concentration effect found here does not license a ceiling
  there, nor the reverse.
- **Not a claim about long-dated hedging.** The book is ≤60-DTE by accident of
  the ladder; hedge expiries are bounded to 20–120 DTE and nothing here speaks
  beyond that.

## Population and basis, fixed here

The frozen inputs: the era, the book, the session universe, the equity curve
the drawdown is measured on, the sizing, and the sector map.

- **Era `v4` (`current`), and only v4.** `load_book(include_bs=False)` — real
  and `strike_expiry_tweak` pricing, proxy calibration gate ON, no
  `bs_options_hist` rows. Era mismatch refuses (exit 3); a thin era refuses
  (exit 2). v3 is NOT pooled and NOT replicated here: `hedge_timing` disclosed
  its v3 window as PARTIALLY CORRELATED and forbade pooling, and that holds.
- **Book**: 485 rows / 140 signal dates / 2024-01-10 .. 2025-11-04.
- **Session universe**: the 504 trading sessions on which at least one position
  is open, derived from `[signal_date, signal_date + days_held]`. This is the
  unit the drawdown path is computed on and is ~3.6× the signal-date count.
- **Equity curve**: MARK-TO-MARKET, built from `daily_pnl_csv` (populated
  485/485). The realized-on-close curve (`account_sim.equity_curve`, bucketed
  by `exit_sess`) is computed alongside for comparability with every prior
  hedge verdict, but it is NOT the basis any verdict here is read from.
- **Sizing / capital**: `config/account-sim.yml` at its committed values,
  through `account_sim`'s ledger and `admission()`. The hedge is admitted after
  the day's signal picks, following the existing sleeve pattern.
- **The sector map is fixed HERE, before any concentration was computed** — 11
  clusters, each with one proxy instrument. Residual is BROAD → SPY. It may not
  be edited after this file is committed:
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
- **Four clusters are UNHEDGEABLE.** They keep their identity in the
  concentration measure, but no hedge can be placed for them:
  - `XLF` fails the fill gate (15.0% band / 40.7% nearest).
  - `IBIT` (22.9%) and `EEM` (41.4% band) fail the fill gate.
  - `XLE` is on `underlying.rescaled_tickers()` at a 0.5000 median relative
    difference over 267 overlaps, so the repo's own convention withholds it.

  Together ENERGY, FINL, CRYPTO and INTL are 10.2% of book exposure.
  **They are NOT folded into BROAD/SPY.** Folding would inflate BROAD's
  measured concentration with exposure that SPY does not actually track,
  corrupting the trigger itself. It would also contradict
  `concurrency_correlation`'s standing commitment that an unmapped ticker "is
  its own bucket — never folded into a named sector". A session whose top
  cluster is unhedgeable is **carried at f=0 and counted against the fill
  gate**, per `calendar_hedge`'s rule that a hedge unavailable exactly when
  needed is not a hedge.
- **The sector map is shared, not study-local.** `concurrency_correlation`
  (registered 2026-08-22, module not yet written) commits to a static
  ticker→sector map for its ARM K. Two maps would let two studies disagree
  about what "same sector" means, which is the failure mode
  `mapping.CONFIDENCES` and `ladder_tier()` exist to prevent. The map above is
  written to `scripts/backtest_study/lib/sectors.py` as the single encoding.
  Whichever study is built second imports it rather than restating it.

## Plan-time observations, disclosed

All of the following were measured from INPUTS before any outcome column was
touched, and are disclosed here rather than discovered later. The full working
is in `research/current.md` under 2026-08-29.

**The book is not shaped like the practice being tested.** 62.7% of book
exposure is DIRECT — the position is in the proxy ETF itself (CREDIT 92%
direct, SMALL 100%, RATES 100%, METALS 92%). Only 37.3% is CONSTITUENT — a
single name inside a proxy, which is the operator's literal described practice.

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

**Trigger census (no outcome column read).** Concentration = the largest
absolute per-cluster signed delta notional as a share of book gross, per
session, over 504 sessions. Any-cluster: median 0.301, p75 0.398, p90 0.572.
Constituent-only: median 0.118, p75 0.174, p90 0.256.

| threshold τ | any-cluster sessions | constituent-only sessions |
|---|---|---|
| 0.30 | 256 (51%) | 40 (8%) |
| 0.35 | 179 (36%) | 24 (5%) |
| 0.40 | 120 (24%) | 16 (3%) |

**Consequence, accepted now:** a trigger on the operator's literal practice
(constituent-only) has 16–24 qualifying SESSIONS, which date-clustered is far
below the ≥25 DATE floor. The constituent stratum is therefore expected to be
POWER-STOPPED and is registered as a stratum to report, not an arm to conclude
from. This is disclosed at plan time so a later underpowered result reads as
predicted, not as a disappointment.

**Fill coverage, per proxy, over the 140 book dates.** Band rule = expiry
25–75 DTE and strike within ±5% of that date's close; nearest-available =
nearest strike at-or-below spot, expiry nearest 45 DTE within 20–120.

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

CRYPTO and INTL therefore have no band-rule instrument (7.0% of exposure
combined). Per `calendar_hedge`'s standing principle — *"A hedge unavailable
exactly when needed is not a hedge"* — those sessions are **carried at f=0 and
counted against the fill gate, never dropped from the population**.

**Coverage is not uniform in time.** Under the band rule SMH and QQQ are strong
in 2024 and collapse in 2025Q3/Q4 (SMH .45/.00, QQQ .20/.00); GLD and EEM are
weak in 2024Q1 and strong later. The nearest-available rule is ~flat. This is
why both rules are registered, and why the ex-window cuts below are mandatory.

**Lookahead: the analysis prose carries irreducible model-recall risk.** All
1,893 `AnalysisClaude` rows carry `created_datetime` in 2026-08, including rows
for January-2024 sessions — the v4 book is a backfill. For a study keyed to the
model's WORDS, the consequence differs in kind from the density consequence
already on record: `hedge-pressure 35/100` written against 2024-03-20 was
produced in 2026-08 by a model whose training cutoff overlaps that date, so it
may be recall rather than a read of that day's tape. This is the hazard
`s06_recommend.judge()` and `live_select.py` already document, arriving through
the analysis prose. It cannot be bounded away. It is handled by ARM P below,
which carries no prose at all, and by the reading rule that **no verdict may
rest on a prose-conditioned arm alone**.

**Hedge-flow signal extraction, fixed here.** The numeric `hedge-pressure
NN/100` embedded in `regime` prose, parsed with
`r"hedge[- ]pressure[^0-9]{0,15}(\d{1,3})\s*/\s*100"`, case-insensitive. It
covers 103 of 158 analysis dates (65%), is constant within a date (0 dates
carry two values), and spans 15–83 with median 35. **A date with no parse is
treated as NO SIGNAL (do not hedge)** — the conservative direction. A naive
date-level keyword match was considered and REJECTED at plan time: it fires on
157 of 158 dates and is non-discriminating.

**The measurement finding that motivated ARM M.** `account_sim.equity_curve()`
buckets P&L by `exit_sess` and its own `print_equity()` states *"Open positions
are not marked to market, so this understates intra-position drawdown."* Every
hedge verdict on record — `bear_deploy` D3, `calendar_hedge` H3, `hedge_timing`
H4, including the −$10,968 baseline this study was queued against — rests on
that curve. A hedge's function is to cushion the intra-position path, which is
precisely what the curve omits.

## Arms

- **ARM M — measurement (runs first, gates nothing else).** The SAME unhedged
  book on both curves. Reports max drawdown, Ulcer index and time-under-water
  on the mark-to-market curve versus the realized-on-close curve.
- **ARM C — concentration-gated proxy put.** Hedge on any session where
  concentration ≥ τ, τ ∈ {0.30, 0.35, 0.40}, sized at fraction f ∈ {0.25,
  0.50, 1.00} of a standard position's risk. Instrument = a long put on the
  concentrated cluster's proxy, band rule primary, nearest-available as the
  registered sensitivity. **Carries no prose.**
- **ARM CS — concentration × hedge-flow signal.** ARM C, additionally requiring
  `hedge-pressure ≥ 50` (fixed here; the median is 35, so this is the upper
  ~third of parsed dates). Prose-conditioned.
- **ARM P — prose-free counterpart.** ARM C restricted to exactly the sessions
  ARM CS would hedge on, minus the prose condition — isolating how much of any
  ARM CS effect is the prose rather than the concentration underneath it.
- **ARM N — random-admission null, 200 seeds.** Hedges on a random set of
  sessions matched in COUNT and in date-clustering to the triggered set.
  Following `portfolio_delta`'s ARM N: **an arm must beat ARM N's 95th
  percentile, not merely beat the unhedged book.**
- **ARM B — instrument comparison.** ARM C with the book's own bear row as the
  instrument instead of the proxy put. `bear_deploy` D3 and `hedge_timing` H4
  both found this cannot cut max drawdown on the close-bucketed curve; this arm
  asks only whether that survives the move to a mark-to-market curve.
- **ARM R — always-fillable reference.** ARM C with a delta-equivalent SHORT in
  the proxy UNDERLYING instead of a put. No option cache dependency and no fill
  gate, so the study cannot terminate on fill coverage alone — which is how
  `calendar_hedge` ended. **ARM R is a floor on feasibility, not a
  recommendation: it has a different loss shape from a put and is not an
  instrument the operator trades.**

Grid: 3 τ × 3 f = 9 cells per arm. Fixed here; not expanded later.

## Unit and metric

- **Unit**: the session. Date-clustered resampling for every confidence
  interval — never row-level, never session-level-independent.
- **Primary metric**: **max drawdown in dollars** on the mark-to-market book
  equity curve, hedged versus unhedged.
- **Co-primary, path-shaped**: **Ulcer index** (RMS of percentage drawdown
  across all open sessions) and **time-under-water** (share of open sessions
  spent below the running peak). These carry a denominator, so they are not
  worst-decile-shaped and do not inherit the ~9-date wall.
- **Secondary, reported never concluded from**: total P&L, worst single
  session, realized-on-close max drawdown.

## Gates

- **G-ERA** — v4 or refuse (exit 3); thin era refuses (exit 2).
- **G-FILL** — a hedge must be fillable on **≥60% of triggered sessions** under
  the band rule. Unfillable sessions are carried at f=0, never dropped. Below
  60%, the proxy-put arms are **NOT EVALUABLE** (not "failed") and only ARM R
  is read.
- **G-POWER** — **≥25 trigger DATES** (date-clustered, not sessions) per cell.
  Below that the cell is UNDERPOWERED and carries no verdict.
  **UNDERPOWERED is not a lean.**
- **G-BLIND** — the trigger must be computable with outcome fields stripped.
  Reuse `account_sim`'s `blind_records` / `BlindRec`; the triggered session set
  under blinded records must be byte-identical to the sighted run, or the
  study prints `LOOKAHEAD DETECTED` and refuses.
- **G-MTM** — the mark-to-market curve must reconcile to the realized-on-close
  curve at every position's exit: cumulative MTM P&L at exit equals the booked
  realized P&L, per position, to within rounding. Mismatch exits non-zero.
- **G-CENSUS** — the power census prints before any outcome column is read.

## Bar for a candidate

A cell is a CANDIDATE only if ALL of:

1. **Max drawdown AND worst single session are both no worse than f=0** — the
   criterion carried verbatim from `bear_deploy` D3, judged on dollars.
2. The improvement in **at least one co-primary path metric** (Ulcer index or
   time-under-water) has a **date-clustered CI excluding zero** at
   Bonferroni-corrected α = 0.05/9.
3. It **beats ARM N's 95th percentile** on that same metric.
4. **Positive in ≥2 of the book's years.**
5. **Both ex-window cuts** (`protocol.DOMINANT_WINDOWS`) retain the sign.
6. **Every leave-one-date-out fold** retains the sign.
7. **NOT A DELTA REDUCTION IN DISGUISE.** The cell's improvement must exceed
   ARM R's improvement at the same τ and f. ARM R shorts the proxy underlying
   to the same delta, so it carries the pure exposure-reduction effect and none
   of the convexity a put adds. A put arm that merely matches ARM R is
   reported as **A RESTATEMENT OF DELTA REDUCTION** and does not clear the bar
   — the same control `concurrency_correlation`'s X7 applies to its ceilings.
   It is also why `portfolio_delta`'s already-failed delta arms are not
   re-litigated here.

## Verdicts, worded now

- **MECHANISM-FOUND** — ≥1 cell clears every clause of the bar. States the
  cluster, τ, f, instrument, and which path metric moved.
- **NULL** — gates pass, no cell clears the bar. Reads as: *concentration-
  triggered proxy hedging does not reduce this book's drawdown either.*
- **CONTRARY** — a cell's drawdown is reliably WORSE than unhedged under the
  same bar clauses. Would corroborate `hedge_timing`'s v3 always-on finding on
  a different trigger and a better curve.
- **UNDERPOWERED** — G-POWER fails. No direction is quoted, ever.
- **NOT EVALUABLE** — G-FILL fails for the proxy-put arms; only ARM R is read
  and it may not be quoted as evidence about puts.
- **MEASUREMENT-ONLY** — ARM M shows the two curves differ materially, but no
  hedge cell clears the bar. This is a real, reportable outcome: it would mean
  the programme's prior nulls were measured on a blind instrument without a
  hedge mechanism yet being found.

**Asymmetric reading rule, binding.** Results are always stratified DIRECT
versus CONSTITUENT. A positive result in the DIRECT stratum — a put on an ETF
the book already holds — **may NEVER be cited as evidence for the operator's
constituent-to-sector-proxy practice.** It is a different action. A NULL in
DIRECT is likewise not evidence against the constituent practice. This mirrors
`hedge_timing`'s T-DECLINE-BROAD rule.

**Prose rule, binding.** No verdict may rest on ARM CS alone. If ARM CS clears
the bar and ARM P does not, the reported verdict is **PROSE-CONDITIONED,
LOOKAHEAD-UNRESOLVED** — a candidate for a forward window, never a ship.

## Anti-tuning

- The **sector map, the τ grid, the f grid, the hedge-pressure cut (≥50), the
  fill rules and the DTE window are all fixed in this file** before any outcome
  column is read. None may be edited after commit.
- **9 cells, Bonferroni α = 0.05/9.** Half of the `calendar_hedge` wall was
  multiplicity and is free to fix by pre-registering one grid; that is done
  here. No second grid may be added to this study.
- **No post-hoc threshold search.** If no τ in the grid triggers ≥25 dates,
  the answer is UNDERPOWERED, not a new τ.
- **No stored expected figure.** No gate here fingerprints a snapshot; every
  count above is disclosed as a plan-time observation, not a checksum.
- **No annualised figure, Sharpe, or time-to-recover** is computed or printed.
- If the study is re-run on a grown option cache, the cache state is recorded
  in the report header — `calendar_hedge` R4 had to be frozen to a pre-scrape
  snapshot because nearest-strike re-picks legs on a grown cache.

## Ship criteria

**NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF.** A MECHANISM-FOUND
verdict produces a DRAFTED amendment to `docs/deployment-rules.md` §4, held in
`research/` — draft-and-hold, the posture the operator chose for the GAP
prohibition. A NULL or CONTRARY verdict ships nothing and is recorded in
`research/deployment-evidence.md` as closing the queued max-drawdown question.
The §4 sleeve is operator policy and is not removed by any outcome here.

## Build notes

_Not part of the registration._

- Module: `scripts/backtest_study/f4_deployment/hedge_exposure.py`. Auto-
  discovered by `run.py::study_paths()`; needs a `catalog.STUDIES` entry and a
  mention in `research/study-map.md` or `tests/test_study_map.py` fails.
- Declare `DESIGNED_REFUSAL_EXIT_CODES` as an AST-literal `set` at module
  level — `run.py::_refusal_codes` parses it without importing. Add a code for
  G-MTM reconciliation failure.
- Reuse, do not reimplement: `lib/era.py::load_book`, `account_sim.simulate`'s
  hedge-admission pattern (hedge added after the day's picks, through the same
  `admission()`), `account_sim.session_series` for open-book exposure,
  `bear_deploy.max_drawdown`, `protocol.walk_forward_splits` /
  `DOMINANT_WINDOWS`, `underlying.rescaled_tickers` as an instrument filter,
  `vol_sleeve._strike_index` for the option-cache filename convention, and
  `lib/barchart/options.py::_mark` for what counts as a usable price.
- `harness.py` is FROZEN and prices ONE position — use it as the per-position
  primitive inside the book loop, exactly as `account_sim` does. Do not edit it.
- Known defect to inherit-fix: hedge sizing that floors at
  `max(1, int(f × contracts))` silently becomes full size whenever risk size is
  1 contract. `account_sim` ARM H fixed this by SKIPPING sub-one-contract
  hedges, which dropped 61 of 132 candidates. Whichever is chosen must be
  stated in the report, not left implicit.
