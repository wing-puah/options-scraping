## hedge_timing — is the bear sleeve's DEPLOY DAY mechanical?

_Registered 2026-08-28._

## Question

The operator deploys the bear-debit hedge sleeve on discretionary triggers:
(a) the market looks choppy, (b) SPY gaps up, (c) SPY has closed lower 4–5
sessions in a row.

Do these mechanical triggers identify days on which the hedge earns more than
the same day's ladder-eligible long — or should streak days in particular be
spent opening a LONG instead?

The study asks about the TIMING of a sleeve whose pick and size are already
operator discretion. It does not ask whether the sleeve is worth holding at all.

## What this is NOT

- **Not a re-run of `bear_deploy` D5.** D5's regime gates for hedge timing were
  POST-HOC and failed year-stability — the surviving gate was carried by 2025
  alone. Its gate family is not re-tested here, and the one gate that came
  closest (`mech_direction = RANGE`) is explicitly excluded from every verdict
  below (see T-CHOP).
- **Not a re-opening of bear SELECTION.** `bear_arm` B1 (0 of 496 subsets) and
  `bear_deploy` D1 (0 survivors, re-confirmed on v4) stand. No arm here screens
  which bear to take.
- **Not a market-timing study.** H2 exists precisely to catch that confound: a
  trigger that marks days on which EVERYTHING pays (or nothing does) is a read
  on the tape, not a property of the hedge.

## Population and basis, fixed here

The book, the outcome column, the units, the era and the window cuts are all
fixed here, before any arm runs.

- **Book.** `lib/book.py::load_book(include_bs=False)` — real +
  `strike_expiry_tweak` rows, proxy calibration gate ON. No `bs_options_hist`.
- **Outcome.** `R` as the loader carries it, i.e. the SHIPPED PROD exit profiles
  (`DEBIT_PROD` / `CREDIT_PROD`). **No `be_after` variant anywhere.** `bear_arm`
  B2's `be_after: 0.50` was reverted by its own rollback trigger on 2026-08-24,
  so replaying bear rows under it would price the sleeve on an exit the operator
  is not running.
- **Units.** R only in H1–H3. Dollars ONLY in H4. **No `$` figure may be quoted
  for H1, H2 or H3**, in the report or in any write-up (G5).
- **Bear rows** = `bear_put_spread` and `long_put` DEBIT rows. `bear_call_spread`
  is a credit structure and is tier-VETO'd at intake, so it is not part of the
  sleeve this study is about.
- **Era.** The decisive read is `current` (v4). A pre-declared `--era v3`
  replication run is reported SEPARATELY, with identical thresholds, and is
  disclosed as **PARTIALLY CORRELATED**: the calendar windows overlap, so only
  v3's post-2025-11-04 tail is fresh evidence. That tail gets its own census and
  will most likely print UNDERPOWERED. **Pooling the two eras is forbidden**
  under every outcome.
- **The 2026 no-op, stated up front.** The v4 export carries ZERO 2026 signal
  dates. So `ex_2026_feb_apr` ≡ `ALL` on v4, and "the sign holds in every year"
  reduces to 2024 ∧ 2025. Every cut prints its own `n` beside `ALL`'s `n`, so a
  reader can see when a cut is a no-op rather than a passed test.
- **The ex-BOTH-windows cut.** A third column, computed BY HAND (not from
  `protocol.window_cuts`, which yields the two cuts separately): rows dated in
  NEITHER 2025-03/04 NOR 2026-02/03/04. On v4 it EQUALS `ex_2025_mar_apr`, and
  the report must say so rather than presenting it as an independent check.

## Plan-time observations, disclosed

Counts only. **No outcome column was read while designing this study** — the
census below is date and row counts against trigger definitions, nothing else.

Measured 2026-08-28 on the v4 book: 145 signal dates 2024-01-10 → 2025-11-04,
365 bear rows, 139 bear-carrying dates, and 121 dates carrying BOTH a bear row
and a ladder-A/B row.

| Trigger operationalisation | book dates | bear-carrying | bear rows | H3 paired | vs floors |
|---|---:|---:|---:|---:|---|
| CHOP `eff_ratio` ≤ 0.163 (bottom tercile) | 49 | 48 | 139 | 42 | MET |
| CHOP `eff_ratio` ≤ 0.30 (sensitivity) | 91 | 89 | 243 | 78 | MET |
| GAP ×1.002 (sensitivity) | 48 | 45 | 119 | 39 | MET |
| GAP ×1.003 (primary) | 37 | 34 | 88 | 30 | MET |
| GAP ×1.005 | 16 | 14 | 37 | 12 | UNDERPOWERED |
| DECLINE strict N=3 | 7 | 7 | 20 | 7 | DEAD |
| DECLINE strict N=4 | 2 | 2 | 7 | 2 | DEAD |
| DECLINE strict N=5 | 2 | 2 | 7 | 2 | DEAD |
| DECLINE ≥4 of 5 | 9 | 9 | 28 | 8 | UNDERPOWERED |
| DECLINE ≥3 of 4 | 22 | 22 | 71 | 15 | UNDERPOWERED |
| DECLINE ≥3 of 5 (BROAD, powered substitute) | 54 | 53 | 159 | 45 | MET |

**Provenance of the table, disclosed.** These counts came from a plan-time
script that APPROXIMATES `load_book`: it omits `Trade()` construction failures
and does not apply the proxy calibration gate. The study's own H0 census
re-derives every one of them THROUGH `load_book`; any discrepancy is printed and
explained in the report and is never silently accepted.

**THE OPERATOR'S OWN TRIGGER IS NOT TESTABLE ON THIS BOOK.** A strict 4-session
SPY down-run occurs on roughly 11 of the era's ~457 trading days; the book
samples 140 of them and lands on 2. Reaching the registered 25-date floor at the
current emission density needs on the order of 3,000 further trading days.

This registration therefore FIXES the verdict `DECLINE-UNDERPOWERED` for the
strict-run arms IN ADVANCE, and commits that **no direction will ever be quoted
from n=2**. That is a sampling limit of the book, not a fact about the market —
and it is itself the study's decision-relevant output for trigger (c).

## Arms

All triggers are evaluated on the SIGNAL DATE D. Entry is the next session's
open (`deployment-rules` §0), so every trigger below is known a full session
before money moves.

### Series, fixed here

- SPY CLOSES: `backtests/mech_regime/spy_vix_daily_full.csv` via
  `underlying_features.market_closes()` — holiday rows carrying only one leg are
  dropped (that loader already refuses a row with no positive `spy_close`).
- SPY OPENS: `underlying.load_bars("SPY")` (the OHLC cache). SPY is not in
  `rescaled_tickers()`, so no split rescaling applies.

### The triggers

**T-CHOP (primary: bottom tercile).** `eff_ratio` over the standing
`EFF_WINDOW = 20` sessions of the SPY close series, ≤ the bottom-tercile
boundary computed over the ERA'S BOOK DATES from the series alone. The boundary
is printed in the census BEFORE any R is touched. Sensitivity: `eff_ratio ≤ 0.30`.
The window length is the standing `underlying_features` constant and is NOT swept.

**T-CHOP is explicitly NOT `mech_direction = RANGE`.** RANGE was `bear_deploy`
D5's best POST-HOC gate on 2026-08-27 (+$9,622) and re-testing it here would be
a disguised D5 re-run. `mech_direction = RANGE` is computed and printed as a
flagged SECONDARY carrying NO verdict. Three further reasons it may not be the
primary: it is a RESIDUAL category (whatever is neither BULL nor BEAR), it was
fitted for EXITS rather than for entry timing, and it carried a provenance
defect on 2026-08-27.

**T-GAP (primary g = 0.003).** `open(D) ≥ close(D−1) × (1 + g)`. Sensitivity
`g = 0.002`. `g = 0.005` is declared UNDERPOWERED by the census above and
carries no verdict. SECONDARY, censused with no verdict: the ENTRY-session gap
`open(D+1)` vs `close(D)` — disclosed as requiring an at-the-open decision,
which the shipped card does not make.

**T-DECLINE-STRICT(N), N ∈ {3, 4, 5}.** N consecutive lower SPY closes ending at
D. **Verdict fixed in advance: `DECLINE-UNDERPOWERED`.** The census prints; no
direction is quoted, ever, under any outcome.

**T-DECLINE-BROAD.** SPY closed lower on ≥ 3 of the last 5 sessions ending at D.
**ASYMMETRIC READING RULE, pre-registered:** a NULL here IS informative about the
strict rule — if even the broad construct cannot separate, the narrow one is not
worth waiting for. A POSITIVE here is NOT evidence for the operator's 4–5-day
rule and may NEVER be cited as such; it is a different, weaker hypothesis and is
reported under its own name.

### The verdicted arms

Each is run once per trigger FAMILY.

- **H0 — POWER CENSUS.** Runs FIRST and returns BEFORE any outcome column is
  touched: per trigger, the trigger dates, bear-carrying dates, bear rows,
  H3-paired dates, and the same four on non-trigger dates. An arm whose floor
  fails early-returns UNDERPOWERED without computing any statistic at all.
- **H1 — between-date.** `mean(date-mean bear R | trigger) − mean(date-mean bear
  R | non-trigger)`, date-clustered bootstrap CI. **Named weakness, registered:**
  no within-date pairing is possible (a date either fires the trigger or does
  not), and a positive H1 is confounded with "the market fell". H1 is therefore
  NOT the primary arm.
- **H2 — beta control.** The SAME between-date separation computed for the
  DEPLOYED LADDER (`protocol.top_k_per_day(rows, ladder_rank, k=3,
  eligible_fn=ladder_eligible)`), printed as a signed pair beside H1.
  `h2_mirrors` fires when long R falls on trigger days by an amount comparable
  to bear R's rise — **defined here as `|H2 delta| ≥ 0.5 × |H1 delta|` with the
  two deltas OPPOSITE-SIGNED.**
- **H3 — PRIMARY. The operator's counterfactual, within-date paired.** The
  method `bear_deploy` D4 proved: on each trigger date carrying ≥ 1 bear row AND
  ≥ 1 ladder-eligible (tier A|B) row, `dR = date-mean bear R − date-mean A/B
  long R`. Reported with `boot_ci_paired_by_date`, `loo_by_date`, per-year signs,
  and all three window cuts (`ex_2025_mar_apr`, `ex_2026_feb_apr`, ex-BOTH by
  hand). The SAME paired statistic on NON-trigger dates is the contrast, and the
  **headline claim is the DIFFERENCE of the two paired means** — not the trigger
  arm's level.
- **H4 — do-nothing baseline (portfolio, dollars).** Sleeve policies over the
  deployed ladder's daily dollars: `f = 0` (never hedge), always-on (hedge every
  day a bear row exists), and trigger-gated — at `f ∈ {0.5, 1.0}`, one hedge per
  day. **Criterion, verbatim from `bear_deploy` D3: max drawdown AND worst single
  date both no worse than `f = 0`.** Days with no bear row are CARRIED at `f = 0`,
  never dropped — the `calendar_hedge` lesson: a hedge that is unavailable exactly
  when it is needed is not a hedge, and dropping those days would hide that.
  **Disclosed:** H4 reuses D5's estimator on new gates, so a pass here ALONE can
  never ship — D5's own gate family failed year-stability.

## Unit and metric

The unit is the DATE. Every CI resamples dates
(`protocol.boot_ci_by_date` / `boot_ci_paired_by_date`), every stability check is
`protocol.loo_by_date`, and H3's floor binds on its PAIRED-date count, not on
its row count.

## Gates

Each gate exits non-zero on failure.

- **G1 — book calibration.** `load_book`'s debit calibration diagnostic via
  `lib/replay_basis.classify`, printed in the header. The 2026-08-27 HYG
  `boundary_tie` class (fixed in `dee8201`) is part of that vocabulary and is
  reported, not folded into `hard`.
- **G2 — SPY series cross-check.** The two SPY series must agree: daily log-return
  Pearson correlation ≥ 0.99 AND same-signed daily direction on ≥ 99% of
  overlapping dates. Disagreeing dates are listed. Failure ⇒ **NOT EVALUABLE**,
  non-zero exit. (The mech CSV is unadjusted and the OHLC cache is adjusted; this
  gate proves the difference cannot move a trigger.)
- **G3 — the floors.** Below, enforced before any outcome access.
- **G4 — no new statistic.** No annualised figure, no Sharpe, no
  time-to-recover, anywhere.
- **G5 — units.** Dollars appear ONLY in H4.

## Bar for a candidate

**Floors, pre-declared.**

- ≥ **25 trigger DATES** for every date-clustered arm (H3 binds on its
  paired-date count).
- ≥ **60 ROWS** additionally for any row-level structure/exit cell, which prints
  `n` only beneath it.
- ≥ **25 gated DAYS** for H4 — raised deliberately from D5's informal 10.

**UNDERPOWERED is not a lean**: such an arm prints its `n` and its census line
and NO direction.

**Multiplicity.** Exactly ONE headline per trigger family — CHOP tercile,
GAP 0.003, DECLINE-BROAD — fixed here. Every other operationalisation is a
SENSITIVITY that may confirm but may never promote. 3 families × 3 verdicted
arms (H1 / H3 / H4) = **9 headline tests**, and the report prints
"~0.45 expected by chance at 5%" beside the survivor count.

**The candidate bar is the conjunction:** CI excludes zero ∧ every LOO fold
same-signed ∧ both year signs ∧ all three window cuts ∧ (for TIMING-CANDIDATE)
¬`h2_mirrors`.

## Verdicts, worded now

One function, `verdict_for(c) -> str`, TOTAL by construction over the criterion
vector `{evaluable, powered, ci_excludes_zero, positive, loo_all_same_sign,
years_ok, cuts_ok, h2_mirrors}`:

- **NOT EVALUABLE** — an upstream gate failed (G1 calibration or G2 series
  cross-check).
- **UNDERPOWERED** — a registered floor is not met. Census printed, no direction.
- **TIMING-CANDIDATE** — the full bar, positive, and ¬`h2_mirrors`.
- **MARKET-TIMING-PROXY** — the full bar, positive, but `h2_mirrors`: the day is
  good for everything, so this is not a fact about the hedge.
- **CONTRARY** — the full bar with a NEGATIVE sign: the trigger marks days on
  which the hedge is WORSE than the same day's long.
- **UNSTABLE** — the CI excludes zero, but LOO, a year sign, or a window cut
  fails.
- **NULL** — powered, CI spans zero.
- **INDETERMINATE — `<criterion vector printed verbatim>`** — the catch-all, so
  nothing can fall through unlabelled.

**Outcomes, worded now. Nothing ships from this correlated window.**

- **TIMING-CANDIDATE on H3** (with H4 unharmed and the v3 read not contradicting)
  ⇒ queued for independent-window confirmation, an attention flag on the study
  map, recorded in `research/deployment-evidence.md`. **No `docs/deployment-rules.md`
  §4 edit.**
- **CONTRARY** ⇒ a proposed §4 PROHIBITION line is DRAFTED AND HELD for the
  operator. It is their standing decision and is never auto-applied.
- **MARKET-TIMING-PROXY** ⇒ recorded as a not-a-hedge finding: the trigger reads
  the tape, and the sleeve is incidental.
- **All-NULL / UNDERPOWERED — the MODAL EXPECTATION, stated here for
  anti-HARKing** (bear standalone E is negative; D2 reversed on v4;
  `bear_position_study` fired `DEMOTE TO VETO`; D5's gates failed year-stability)
  ⇒ §4 gains ONE subtraction sentence: *"no mechanical trigger tested — chop,
  gap-up, decline — identifies a day on which the hedge is worth more than the
  same day's ladder-eligible long; the sleeve's timing is operator discretion, as
  its pick and size already are"* — plus the standing census finding that the
  4–5-day streak rule is not testable at this book's emission density.

## Anti-tuning

The trigger set is CLOSED at registration. Window lengths are the standing
constants (`EFF_WINDOW = 20`), not knobs. The tercile boundary and `g` are fixed
by the COUNT-ONLY census above. Ship criteria are never re-read after numbers
are seen.

**Forward trigger (blind).** Re-run when EITHER ≥ 25 book dates carry a live
strict N ≥ 4 SPY down-run, OR ≥ 25 signal dates exist after 2025-11-04.

## Ship criteria

Nothing ships from this study under any outcome. The maximum admissible result
is one of three things, each of which the operator applies by hand:

- a queued candidate (TIMING-CANDIDATE),
- a held draft prohibition (CONTRARY), or
- one subtraction sentence in `docs/deployment-rules.md` §4 (all-NULL).

## Build notes

_Not part of the registration — implementation, not commitment._

`scripts/backtest_study/f4_deployment/hedge_timing.py`. Rows already carry `R`
and `R_dol` under the PROD profiles from `load_book`, so the FROZEN harness is
not imported. `max_drawdown` and the daily-dollar series shape are COPIED from
`bear_deploy.py` with attribution comments rather than imported — studies do not
import each other's internals. Census lines use
`lib/triggers.py::census_line`, the house `FLOOR MET` / `UNDERPOWERED` token.
