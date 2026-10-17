## volume_signal — does underlying share volume condition anything the book cares about?

<!-- brief:start -->
## In brief

> Plain-language brief for readers. The registration below is the binding text; where the two differ, the registration wins. `study_review` cuts this brief out before grading, so the blind graders never see it.
> Latest outcome: PRIMARY v3 `NULL` (2026-08-15). On v4, `NULL` (2026-09-28), after earlier v4 runs had printed `PATH-VOL-PROXY` · [record](../../study-results/f2_management/volume_signal.md).
> Nothing else in this brief is a result.

**The question**

Underlying share volume is the one column on disk that no study had read. Does it condition anything the book cares about?

The primary hypothesis is about exits and paths, not selection. Bear debits were diagnosed as an exit problem, and the sub-arming give-back census is a path effect. Reading the column also meets the ML-search reopen condition, which allows new columns only.

Every closed-thread rule applies. Any selection read must be within structure from the first look.

**What it compares**

The study builds three features from data already on disk. It reads them on the pooled `real` and `strike_expiry_tweak` book. Labels below are `volume_signal H1`, `H2` and `H3`.

| Object | What it does | Kind |
|---|---|---|
| `volume_signal H1` | Tests whether high unusual-O/S rows give back more, within structure. Compares the HIGH `os_ratio` tercile with the LOW tercile on exit capture and on the share of rows that peak below the `be_after` arming threshold and finish ≤ 0 | PRIMARY, path and exit |
| `volume_signal H1` mechanism test | One variant only: `be_after: 0.50` on non-bear debit rows in the HIGH tercile, against [PROD](../../glossary.md#prod), leave-one-date-out | PRIMARY, path and exit |
| `volume_signal H2` | Descriptive tercile cut of `rvolz20` within structure. No direction is committed and no adoption path exists | exploratory |
| `volume_signal H3` | Re-cuts any H1 separation within `amihud20` terciles | control |
| Selection | Mean R and total dollars by feature tercile, within structure only | SECONDARY |

The three features:

- `os_ratio` = `Contracts × 100 / Volume(signal date)`. Only the tercile order is read.
- `rvolz20` = z-score of `ln(Volume)` on the signal date against the trailing 20 sessions ending the prior session.
- `amihud20` = mean over 20 sessions of `|session log return| / (close × Volume)`.

Bear debit rows are excluded from the H1 variant arm. They already carry the shipped breakeven stop. Their give-back census by tercile still prints.

Rescaled tickers keep `os_ratio`. Their `rvolz20` and `amihud20` are withheld, because a split fabricates a volume spike. A window feature needs at least 15 usable positive-volume sessions.

Option volume is the flow-scrape contract count, not total listed volume. No read may treat it as the literature's exact numerator.

**How it is judged**

**Measure.** [MFE/MAE](../../glossary.md#mfe) separation, [R](../../glossary.md#r) separation and leave-one-date-out ([LOO](../../glossary.md#loo)) fold summaries.

**Population.** The pooled `real` and `strike_expiry_tweak` book through `load_book`. The exit variant runs on calibrated debit rows only. Descriptive tables may use the full book with credit rows flagged. The v3 and v4 eras are never pooled.

**Gates.** A failed gate gives a non-zero exit.

- `G1` calibration: `replay(DEBIT_PROD)` reproduces the stored exit reason, days held and rounded R on every calibrated debit row. The build ruling adds the row's cost back and cuts the path at `path_data_end`; the bar is unchanged.
- `G2` coverage: volume-feature hit rates, source split, O/S join hit rate and withheld counts print before any conditional number.
- `G3`: `MIN_CELL_N = 20`. Thinner cells print n and are not read.
- `G4`: no annualised return, Sharpe or time-to-recover.
- `G5` out-of-fold discipline: descriptive tercile tables are in-sample and labelled so. Only LOO fold summaries and walk-forward test rows can support adoption.

**Selection read.** A within-structure separation must survive `protocol.walk_forward_splits`, with tercile boundaries fitted on train dates only, before it may be called a candidate.

**Bar for the candidate verdict.** All three must hold.

1. H1's LOO median and total are both positive.
2. The sign holds on the log's standard both-window cut.
3. H3 does not collapse the separation.

**Possible verdicts**

| Token | What it means |
|---|---|
| `VOLUME-CONDITIONS-EXITS` | A candidate, not a ship. It queues an independent-window confirmation |
| `LIQUIDITY-PROXY` | `amihud20` absorbs the separation, so H3 fires |
| `PATH-VOL-PROXY` | Path width moves together with no R separation: `mfe_sep × (−mae_sep) > 0`. Higher peaks with shallower drawdowns do not count |
| `NULL` | None of the above survives its gate. The volume column is closed and the live pipeline never pays the version bump |

**What could ship**

Nothing ships under any outcome. A surviving result queues an independent-window confirmation. Only that could justify feeding volume to the live pipeline. That change is an input change, so it needs a version bump and new tabs.

**What this study cannot tell you**

- Whether volume helps selection on its own. Selection is a secondary read within structure.
- Anything about `rvolz20`. It has no committed direction and no adoption path.
- Anything about total listed option volume. The numerator is the flow-scrape count.
- Anything about bear debits as a group. They are excluded from the variant arm.
- The exit-variant set can never grow. It is exactly `{be_after: 0.50}`.

---
<!-- brief:end -->

_Registered 2026-08-13._

## Question

Underlying share volume is the one column already on disk that no study has
read (`scripts/backtest_study/lib/underlying.py` drops it at parse time). Does
it condition anything the book cares about?

- **The primary hypothesis is exit/path conditioning, not selection** — bear
  was diagnosed as an exit problem, and the −$77.2k sub-arming give-back
  census (§2.4 of `next-steps.md`) is a path phenomenon.
- Reading it satisfies the ML-search reopen condition — **new COLUMNS only**.
- It inherits every closed-thread rule: selection is structure×regime,
  `score_total` is a tie-break, and any selection read must be **within
  structure from the first look** (`cpir`/`oi_confirm_pct`/`iv_pct` all looked
  predictive pooled and vanished within structure).

## Population and basis, fixed here

Three features, built from data already on disk, read on the pooled real+tweak
book.

### Data

- **Share volume** = `Volume` column of
  `backtests/underlying_ohlc_cache/<T>.csv`. `Bar` gains a `v` field. The
  close-only `Price~` tilde fallback path carries **no volume** (`v=None`
  always), so coverage is OHLC-cache tickers only — the same smaller
  denominator `rv20`/`beta_spy60` already carry — and `coverage()` prints
  before any conditional number (G2).
- **Option volume** = `Contracts` column of `audit/<date>-rollup.csv`, joined
  on (signal_date, ticker). DISCLOSED: this is the **flow-scrape contract
  count** (Barchart's filtered unusual-flow feed), not total listed option
  volume — the feature is an "unusual-O/S", plausibly closer to the informed
  subset Johnson & So were proxying, but it is not the literature's exact
  numerator and no read may pretend otherwise. Join hit-rate prints in G2.
- **No lookahead**: every feature is as-of the signal date; entry basis is
  next-day OPEN (2026-07-06 re-baseline), so signal-session volume is
  decision-time information.

### Features (three, no additions after first run)

1. `os_ratio` = `Contracts × 100 / Volume(signal date)` — Johnson & So (2012,
   JFE), option-to-stock volume as an informed-trading signal. Only the tercile
   ORDER is ever read, so scale constants are irrelevant.
2. `rvolz20` = z-score of `ln(Volume)` at the signal date against the trailing
   20 sessions ending the PRIOR session (the baseline excludes the day being
   scored) — Gervais/Kaniel/Mingelgrin (2001) high-volume premium; Lee &
   Swaminathan (2000). Labelled EXPLORATORY: the literature sign is for
   unconditional stocks, this book is flow-selected, so no direction is
   pre-committed and no adoption path exists for it this run.
3. `amihud20` = mean over the 20 sessions ending at the signal date of
   `|session log return| / (close × Volume)` — Amihud (2002). A CONTROL, not a
   headline: its job is H3 below.

Two housekeeping rules, on the window features:

- Min-obs mirrors `underlying_features`: ≥15 usable positive-volume sessions
  else `None`; volume observations paired with a dropped split-artifact return
  (`_MAX_ABS_LOG_RETURN`) are dropped with it.
- Rescaled tickers (`rescaled_tickers.txt`): `os_ratio` KEPT (same-day
  numerator and denominator, internally consistent); `rvolz20` and `amihud20`
  WITHHELD (`None`) — a split steps the share count and fabricates exactly the
  volume spike the z-score is looking for. Withheld counts print in G2.

### Book

Pooled real+tweak book via `load_book` (defaults: bs excluded, proxy
calibration gate ON). The exit arm runs on **calibrated debit rows only**
(same basis as every exit study; credits are ungated by `book.py` and carry no
validated replay). Descriptive tables may use the full pooled book
with credit rows flagged. v3-era exports in `backtests/to_evaluate/` by
filename; v4 rows are never pooled in.

## Arms

One primary path/exit hypothesis, one exploratory feature, one control, and a
secondary selection read.

### H1 (PRIMARY — path/exit)

High unusual-O/S rows give back more: within structure, the HIGH `os_ratio`
tercile shows (a) lower exit capture (R against MFE) and (b) a larger share of
rows that peak below the `be_after` arming threshold and finish ≤ 0, versus the
LOW tercile.

Mechanism test — **frozen variant set of exactly ONE**: `be_after: 0.50`
applied to NON-bear debit rows in the HIGH tercile only, versus PROD,
leave-one-date-out (out-of-fold, `exit_switch` house pattern). Bear debit rows
are EXCLUDED from the variant arm, because they already carry the shipped
breakeven stop and re-testing it here would double-count the 08-11 result; their
sub-arming give-back census BY TERCILE still prints, for the blocked §2.4
thread. Standing asymmetry rule applies: an MFE/MAE-mirrored read is a
path-vol artifact, not a finding.

### H2 (`rvolz20`, exploratory)

Descriptive tercile cut within structure, MIN_CELL_N enforced, date-clustered.
No adoption path this run.

### H3 (`amihud20` control)

Any H1 separation is re-cut within `amihud20` terciles. If it collapses
(HIGH-os_ratio separation exists only in the illiquid tercile), the verdict is
LIQUIDITY-PROXY, not flow information.

### Selection (SECONDARY)

Mean R / total $ by feature tercile WITHIN structure only. A pooled
cross-structure table may be printed but may not carry a conclusion. Anything
that separates within structure must survive `protocol.walk_forward_splits`
with tercile boundaries fitted on TRAIN dates only before it may even be
called a CANDIDATE.

## Gates

Five gates; failing any of them is a non-zero exit.

- G1 calibration: `replay(DEBIT_PROD)` reproduces stored
  `(exit_reason, days_held, round(R,4))` on every calibrated debit row;
  `debit_calib` / `n_credit_ungated` quoted.
  Resolved at build (2026-09-28), operator ruling: since the 2026-09-24
  re-price a stored row is net of `cost_total` and stops at `path_data_end`.
  The comparison adds the row's cost back and replays the path cut at
  `path_data_end` (`lib/replay_basis.py`), so an `open_at_data_end` row
  matches as the `cap_open` outcome it is; a row with blank `cost_basis` is
  compared as before. A deferred exit fill (`exit_fill` = `deferred_<n>`)
  is its own `deferred_fill` class, kept as an outcome and never compared.
  The gate's bar is unchanged.
- G2 coverage BEFORE any conditional number: volume-feature hit-rates,
  `by_source` split, O/S join hit-rate, rescaled-withheld counts.
- G3 `MIN_CELL_N = 20`; thinner cells print n and are not read.
- G4 no annualised return, Sharpe, or time-to-recover anywhere.
- G5 out-of-fold discipline: descriptive tercile tables are in-sample and
  labelled as such; the only adoption-eligible numbers are LOO fold summaries
  and walk-forward TEST rows.

## Verdicts, worded now

- **VOLUME-CONDITIONS-EXITS** (candidate, NOT a ship): H1's LOO median AND
  total positive, sign holds on the log's standard both-window cut, H3 does
  not collapse it → queue an independent-window confirmation.
- **LIQUIDITY-PROXY**: separation absorbed by `amihud20` (H3 fires).
- **PATH-VOL-PROXY**: path WIDTH moves together with no R separation —
  operationalized as `mfe_sep × (−mae_sep) > 0` (MFE moving up together with
  MAE going DEEPER), not merely same-signed tercile separations; a HIGH cell
  with higher peaks and SHALLOWER drawdowns does not count as "mirrored"
  under this reading.
- **NULL**: none of the above survives its gate → the volume column is CLOSED
  and the live pipeline never pays the version bump.

## Anti-tuning

The exit-variant set is `{be_after: 0.50}` and may not grow after any result
is seen; tercile boundaries are not knobs; window lengths (20 sessions) are
the standing `underlying_features` constants, not swept.

## Ship criteria

**Nothing ships from this study under any outcome.** A surviving result queues
an independent-window confirmation, and only THAT could ever justify feeding
volume to the live pipeline (input change → version bump → new tabs — not paid
for an untested column).
