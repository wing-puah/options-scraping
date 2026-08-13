# Archive 12 — 2026-08-12: bear_rewrap, vol_sleeve

Covers the 2026-08-12 wrapper/vol research: `bear_rewrap` (`long_put`
clears four of five gates, fails 2026-alone; the wrapper finding),
the `vol_sleeve` pre-registration pointer, and the `vol_sleeve` RUN
(the sleeve doubles down instead of diversifying; the calendar is the
only survivor, as a CANDIDATE).
See [../README.md](../README.md) for the full section index.

---

## 2026-08-12 — `bear_rewrap`: the WRAPPER is worth +0.085 and it does not hold in 2026; nothing ships

**Operator framing.** "The reference PDF study file does not have much impact.
Plan for testing more research/scenarios that make bear positions profitable —
and don't rely only on bullish movement; bearish or volatility plays should be
added to diversify." Scoping answers taken before the run: bear is judged on
**portfolio contribution**, not standalone E; counterpart-leg scraping is
authorised for the vol arm; new columns are **OHLC-derived only**.

**RECORDED DEVIATION.** The ship criteria were fixed in the approved plan
before the study was written or run, and are unchanged below — but this
`current.md` entry was written AFTER the run, not before it. Per the
pre-registration discipline that is a deviation and is recorded as one. No
criterion was added, dropped, or reworded post-hoc; the 2026 and tier cuts that
kill the headline are the ones the plan named.

**Provenance.** `backtests/study_output/bear_rewrap-latest.txt`, git 470b95f
(dirty), the 08-11 exports, `book.load_book(include_bs=False)` → 795 rows,
bear debit (`bear_put_spread` + `long_put`, non-credit) **n=332, real 168 /
tweak 164**. Read-only: no config, prompt, ladder or tab touched.

### 0. Why the PDFs underdelivered — it is not bad luck

Ten of the eleven reference papers are **cross-sectional** predictors validated
on decile sorts over thousands of names and decades. This book's effective
sample is the DATE count (~118). Of the three paper-derived column families
only `iv_spread` survived the 07-21 sweep; `price_vector` and `iv_pct` died as
composition. Paper 11 (forecasting volatility) is the only **time-series**
result in the set — the only kind a 118-date sample can test — and is the one
that was never implemented. It is now `vrp`, and that closes the reference set.
**Adding more columns of the first kind will keep producing nulls.** Recorded
so this is not re-litigated.

### 1. The composition problem, stated as a number

Classifying all 1,607 AnalysisClaude plays through `classify.py` on PRIMARY
text (Alt: sections stripped):

    bear_put_spread   596     straddle    12
    bull_call_spread  438     strangle     9
    bull_put_spread   328     calendar     0
    bear_call_spread   52     diagonal     0
    unsupported       152     butterfly / condor / iron_condor  0

**21 vol rows out of 1,607 (1.3%), of which 3 ever reached BacktestResults.**
The volatility sleeve is not underperforming — it has never been measured, and
no conclusion about diversification can be drawn from the current book. That is
what the counterpart-leg scrape is for.

### 2. The reconstruction gate — 332/332

Every substitution is a DIFFERENCE against a baseline replay, so the baseline
must be rebuildable from the cache by the same pricing code, or the difference
measures the re-pricer. Re-deriving each row's entry price and full daily mark
series from `option_history_cache` and comparing against the stored
`entry_option_price` / `daily_price_csv`: **332 of 332 reconstruct** (entry
within $0.005, ≥95% of days within $0.01). The baseline replays production
exactly — n=332, mean R −0.093, **−$37,951** — matching the 08-11 close-out
figure to the dollar.

Per-leg cache coverage is total: 165/165 bear_put, 128/128 bull_call, 85/85
bull_put real rows have BOTH legs cached. `long_put` needed no new data.

### 3. ARM W — the wrapper result

Same signal, same entry day, same shipped exit (base → structure_exit →
regime_exit, via `bear_giveback.prod_profile_for`). Only the structure differs.

    label        n     win   PF     meanR      $         MFE     MAE    gb    cap
    baseline    332    36%  0.76   -0.093   -37,951    +0.73   -0.82  1.13  -0.13
    long_put    326    33%  0.85   +0.002   -31,547    +0.87   -0.83  0.96  +0.00
    wider       200    38%  0.75   -0.056   -27,093    +0.88   -0.81  0.93  -0.06
    long_diag   153    34%  0.83   -0.050   -10,513    +0.70   -0.67  0.96  -0.07

**The mechanism reads exactly as predicted.** Dropping the short leg raises MFE
(+0.73 → +0.87) and drops give-back (1.13 → 0.96): the spread WAS selling away
the vol expansion that a down move brings. Mean R goes −0.093 → +0.002, paired
**dR +0.085**.

### 4. The gates — four pass, one fails, and the failure is broad

    long_put
      [PASS] CI excludes zero        dR +0.085  CI [+0.030, +0.139]
      [PASS] every LOO fold positive MIN +0.077 over 107 folds (share+ 100%)
      [PASS] both ex-window cuts     ex-2025-Mar-Apr +0.059  ex-2026-Feb-Apr +0.150
      [FAIL] sign-stable every year  2024 +0.135  2025 +0.158  2026 -0.026
      [PASS] right-signed both tiers real n=164 +0.073   tweak n=162 +0.098

`wider` and `long_diag` fail on four of five each and are dead.

**The 2026 failure is NOT one window**, which is what would normally rescue a
candidate here. Monthly: 2026-02 −0.061, 2026-03 −0.026, 2026-04 +0.088, and
dropping any single month leaves it negative (ex-Feb −0.010, ex-Mar −0.026,
ex-Apr −0.039). This is a broad regime change in the most recent year, not a
carrying date. Under the standing screen standard an effect that loses its sign
in a year present is a window artifact until proven otherwise — and here the
losing year is the CURRENT one, which is the worst possible year to lose.

**Dollars must not be quoted on this.** The tiers agree on R and disagree on
dollars (real +$14,837, tweak −$13,317). A substitution changes premium, hence
contracts under the production sizing formula, so $ carries a sizing effect
that R does not. Quote R.

### 5. ARM P — the chosen criterion, and it is NOT MET

P1 (worst-decile deployed dates) and P2 (correlation), the D2 tests:

    label       P1 n   meanR    CI              $         P2 corr   by year
    baseline     21   +0.108  [-0.335,+0.479]  +2,092     -0.109   -0.340/+0.019/-0.145
    long_put     21   +0.262  [-0.273,+0.730]  +9,450     -0.089   -0.228/+0.070/-0.505
    wider        13   +0.160  [-0.306,+0.527]  +2,505     -0.127
    long_diag    11   -0.121  [-0.689,+0.352]  -1,828     -0.084

**P1 is NOT MET for any wrapper, including the baseline.** The deployed ladder
has 90 dates, so the worst decile is **9 dates / 21 rows** — the CI is wide
because the sample is tiny, not because the point estimate is small. `long_put`
more than doubles the baseline's worst-date rescue (+0.108 → +0.262, $2,092 →
$9,450) and cannot demonstrate it. P2 passes pooled for every variant but is
not sign-stable by year (2025 positive for both baseline and `long_put`).

### 6. What this changes

- **Nothing ships.** `config/backtest.yml` and `deployment-rules.md` unchanged.
- **The wrapper hypothesis is CONFIRMED as a mechanism and REFUSED as a rule.**
  The vega story is real and visible in MFE and give-back; it stopped paying in
  2026. Those are both findings and the second one blocks the first.
- **B1's null is untouched** — this study never changed which signals were
  taken, only how they were expressed, so bear SELECTION remains closed.
- The 2026 breakdown is the open question, and it is a genuinely new one: what
  changed in 2026 such that buying the naked put stopped beating the spread?
  The `underlying_features` layer exists to ask that (a vol-regime shift would
  show in `rv20` / `vrp`), and it is the natural next arm.
- **`bear_rewrap` is re-runnable** as more 2026 dates land. If 2026 turns
  positive on a fresh window the candidate is back with all five gates clear;
  if it stays negative the wrapper question is closed for good.

### 7. New infrastructure landed with this

`scripts/backtest_study/underlying_features.py` (+ 25 tests) — pure functions
over `underlying.py` bars: `rv20`, `rv_parkinson`, `semivar_dn`, `atr14_pct`,
`eff_ratio`, `vrp`, `beta_spy60` / `corr_spy60`. Strictly as-of-entry.
**100% coverage on all 406 real book rows, all OHLC source.** Sanity: median
`rv20` 0.329, `vrp` **+0.011** — a small positive vol premium is the textbook
value and is the check that the decimal-fraction units were handled (a
points/fraction mixup reads ~+32 there).

`rv_parkinson` and `atr14_pct` are OHLC-only and carry a different denominator
from the rest; `coverage()` prints the split and every study using them must
quote it.

---

## 2026-08-12 — `vol_sleeve`: PRE-REGISTRATION → [`pre-registrations/vol_sleeve.md`](../pre-registrations/vol_sleeve.md)

Moved out of this log: a pre-registration is an immutable artifact and this
file is pruned into `archive/`. The section is unchanged, just relocated.

---

## 2026-08-12 — `vol_sleeve` RUN: the sleeve does not diversify, it DOUBLES DOWN; the calendar is the only survivor

**Provenance.** `backtests/study_output/vol_sleeve-latest.txt`, git 470b95f
(dirty), the 08-11 exports, `book.load_book(include_bs=False)` → 795 rows.
**1,293 synthetic positions** (758 straddle / 352 strangle / 183 calendar) over
**118 dates, 101 tickers**, every leg REAL-priced from
`backtests/option_history_cache/`. Read-only: no config, prompt, ladder or tab
touched. Pre-registration is the entry immediately below this one and was
written before the study was run; the two additions to it are labelled.

### 0. The gates that ran BEFORE any result was read

- **Reconstruction: 786 / 786 (100%).** A ticker-date is used only if this
  study's pricing code, re-pricing the ORIGINAL book row from the same cache,
  reproduces its stored entry and marks. The synthetics are priced by code
  verified against the real book on the same dates.
- **Freshness.** Long premium is the one structure a carried-forward mark
  flatters — a dying option stops trading and gets frozen at its last print. Cut
  to rows whose final mark is ≤3 days stale: straddle **+0.106 → +0.105**
  (n 758 → 740), strangle +0.095 → +0.107, calendar +0.054 → +0.042. **The
  marks are real.** This was the most likely way for the study to be wrong and
  it isn't the way it's wrong.
- Coverage is not a caveat here: median path coverage 1.00, p10 1.00, median
  |K−S|/S **0.019** — these are genuinely ATM structures, not a strike grid
  scraped from whatever was lying around.

### 1. Q1 — the straddle clears the pre-registered gate and fails the standard screen

    structure   n     meanE    CI95 (E)            meanR   win     $R      years(E)
    straddle   758   +0.106   [+0.039, +0.172]    +0.075   36%   158,565   +0.01/+0.12/+0.18
    strangle   352   +0.095   [-0.029, +0.226]    +0.096   39%    62,597   +0.01/+0.19/+0.01
    calendar   183   +0.054   [-0.094, +0.214]    +0.158   55%    28,059   +0.04/-0.06/+0.24

On the pre-registered terms the straddle **passes**: n ≥ 30, date-clustered CI
excluding zero, same sign in all three years. Then the concentration screen —
**an ADDITION to the pre-registration, and it is the log's standard screen**, so
it is recorded as an addition rather than smuggled in:

    straddle   ALL               n=758   E +0.106   CI [+0.039, +0.172]
               ex_2025_mar_apr   n=559   E +0.081   CI [+0.004, +0.156]
               ex_2026_feb_apr   n=563   E +0.081   CI [+0.014, +0.147]
               ex_BOTH windows   n=364   E +0.029   CI [-0.044, +0.101]   <- dead

**Dropping either dominant window leaves it alive; dropping both kills it.** The
single-window cuts, which is all `window_cuts()` does by default, were never
going to catch this — the carrying dates *span* both windows (top-5 dates =
2026-04-02, 2026-03-18, 2025-03-28, 2025-04-03, 2026-03-24, **61% of $R**). A
long-vol book that only pays in the two volatility events in the sample is the
textbook window artifact, and the fact that it survives a single-window cut is
precisely what makes it look like a finding.

**Strangle is worse and clearer:** ex-2025-Mar/Apr takes it to −0.004, and
**97% of its $62.6k is 5 dates**. Not a sleeve, a lottery ticket on two months.

**Long-dated caveat on the `>90` cell** (straddle +0.130, and $133.8k of the
$158.6k): with `path_cap_days: 120` a >90-DTE straddle is closed at a
**mark-to-market at the cap** with substantial time value left, not at a
realized exit — `tef 0.75` on a 200-DTE position lands past the cap and never
fires. That cell is a valuation, not an outcome. Same blind spot recorded on
2026-07-27, now with real marks instead of BS ones.

### 2. Q2 — NULL, and the sign is the finding

    cell        corr(daily mean R)   CI95                worst-decile sleeve R
    POOLED           +0.268          [+0.081, +0.440]    +0.061  CI [-0.115, +0.248]
    straddle         +0.225          [+0.004, +0.446]    +0.093  CI [-0.122, +0.308]
    strangle         +0.258          [+0.060, +0.461]    -0.090  CI [-0.341, +0.192]
    calendar         +0.088          [-0.153, +0.248]    +0.336  CI [+0.124, +0.486]

The pre-registered gate wanted correlation **< 0**. It came back **positive with
a CI excluding zero** — the sleeve moves WITH the deployed ladder. Mechanically
this should have been predictable and is worth stating plainly so it is not
re-tested: **the sleeve is synthesized at the engine's own signal dates**, and
the engine signals on unusual flow, which is the same event that moves the
underlying. Buying a straddle there is not a different exposure from buying the
vertical the engine emitted — it is a **less efficient wrapper on the same
exposure**, which is exactly the 08-12 `bear_rewrap` result read from the other
side. On the deployed book's worst decile the pooled sleeve returns +0.061 with
a CI spanning zero: it is not there when the book needs it.

**Sizing note.** The mixing lines normalise the sleeve to ONE AVERAGE POSITION
per date (the date's mean $, not its sum). The synthesizer emits ~6× as many
rows per day as the ladder deploys, and summing them would compare a 14-position
sleeve to a 3-position book and call the size difference a hedge. Averaging is
choice-free; picking *which* structure to hold each day is a selection rule and
none is pre-registered. Per-structure "book alone" totals differ because each
structure covers a different subset of dates.

### 3. The calendar — the only thing that survives, and what it is not

Uncorrelated (+0.088, CI spans zero; on $ it is −0.020), positive on the
deployed book's worst decile (**+0.336, CI [+0.124, +0.486]**, n=13) and worst
quartile (**+0.287, CI [+0.102, +0.457]**, n=30), and it is the only cell in the
study that **reduces drawdown while adding return**:

    calendar dates (72 overlapping)     total        maxDD
    book alone                        $ 50,889     $ -7,878
    + 0.5 avg calendar position       $ 63,482     $ -6,860
    + 1   avg calendar position       $ 76,076     $ -5,979

**This is a CANDIDATE, not a finding, and the reasons are not decoration.**
(a) It is a **per-structure subgroup of a POOLED pre-registered gate** — the
exact post-hoc move this log has been burned by. (b) n=13 rows across 7 dates
carries the worst-decile number. (c) Its unconditional E is null (+0.054, CI
spans zero), so the claim would be "a structure with no measurable edge is worth
holding for its correlation" — plausible for a hedge, and precisely what the
2026-08-11 bear DEPLOY arm concluded about bear verticals, but it needs the same
treatment: a **pre-registered pick rule** (which calendar, which day, what size)
before any number is believed. (d) The calendar is also the structure the
synthesizer fails most often — 338 unpriceable, 191 of them because the far leg
has no bar on the shared entry day. A rule that can only be filled on the liquid
half of its candidates has a selection problem before it has an edge.

### 4. Q3 — the gate opened, and all three pre-registered conditions fail

Gate opened on Q1's pre-registered pass (correctly — the concentration screen
that kills Q1 is an addition, and letting it retro-close the gate would be
exactly the post-hoc reasoning the gate exists to prevent). Differences are
tested with a **date-clustered bootstrap of mean(selected) − mean(rest)**, added
because reading two overlapping one-sided CIs and calling the gap a difference
is not a test:

    POOLED (n=1293)                  n    meanE   vs rest   diff CI95
    vrp < 0 (implied cheap)         593   +0.134   +0.062   [-0.048, +0.191]
    earnings inside DTE             429   +0.161   +0.063   [-0.020, +0.212]
    iv_pct bottom tercile (<0.56)   380   +0.073   +0.105   [-0.148, +0.087]   wrong sign

**None of the three clears.** `vrp < 0` is right-signed in every structure but
calendar and never separates; `iv_pct` low is **backwards** — the pre-registered
direction is contradicted, which retires the "buy vol when it's cheap in its own
range" idea for this book rather than leaving it open. The one difference that
excludes zero is **calendar × earnings-inside-DTE: +0.356 vs −0.035, diff CI
[+0.111, +0.664], n=42** — same subgroup as §3, same status, and now the second
independent hint that the calendar deserves its own pre-registered study.

### 5. Infrastructure defect found and fixed (affects other studies)

`underlying_features.terciles()` filtered `None` but not `NaN`, and the book's
numeric columns come off pandas — **71 `iv_pct` cells arrive as `float('nan')`**.
Sorting them corrupted both cut points: the "bottom tercile" cut printed as
**0.92** and swept **69% of the population** into the "bottom third". Fixed to
filter non-finite values (cut is now 0.56, n=380 of 1,293). Any earlier read of
a tercile table on a NaN-bearing column is suspect; `vrp`/`rv20` and the other
OHLC-derived features are computed in-module and never NaN, so the exposure is
`iv_pct`-shaped.

### 6. What this closes and what it leaves open

- **CLOSED: the vol sleeve as a source of EDGE.** Straddle and strangle are
  two-window artifacts; the direction of the Q2 correlation says synthesizing
  vol on engine signal dates is a re-wrapping of the existing exposure, not a
  new one. Do not re-run this with more structures or more columns — the
  2026-08-11 ML null and this share a cause (the ceiling is in what the signal
  dates ARE, not in what is traded on them).
- **CLOSED: the "no evidence at all" state.** The counterpart scrape did its
  job — 481/481 groups, 100% reconstruction, real marks. The question was
  answerable and got answered.
- **OPEN, and the only thing worth running next: the calendar as a HEDGE**,
  pre-registered like the bear DEPLOY arm — a pick rule, a size, the D1–D5
  criteria, and the fill-rate problem in §3(d) treated as part of the test
  rather than a footnote.
- Unchanged: `config/backtest.yml`, `config/deployment-rules.md`, the prompt,
  every tab.

---

