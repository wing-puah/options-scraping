## 2026-08-13 — `volume_signal`: PRE-REGISTRATION (written BEFORE the study was built or run)

**Question.** Underlying share volume is the one column already on disk that no
study has read (`scripts/backtest_study/lib/underlying.py` drops it at parse time).
Does it condition anything the book cares about? This satisfies the ML-search
reopen condition — **new COLUMNS only** — and inherits every closed-thread
rule: selection is structure×regime, `score_total` is a tie-break, and any
selection read must be **within structure from the first look**
(`cpir`/`oi_confirm_pct`/`iv_pct` all looked predictive pooled and vanished
within structure). **The primary hypothesis is exit/path conditioning, not
selection** — bear was diagnosed as an exit problem, and the −$77.2k sub-arming
give-back census (§2.4 of `next-steps.md`) is a path phenomenon. **Nothing
ships from this study under any outcome**; a surviving result queues an
independent-window confirmation, and only THAT could ever justify feeding
volume to the live pipeline (input change → version bump → new tabs — not paid
for an untested column).

**Data, fixed here.**
- Share volume = `Volume` column of `backtests/underlying_ohlc_cache/<T>.csv`.
  `Bar` gains a `v` field; the close-only `Price~` tilde fallback path carries
  **no volume** (`v=None` always) — coverage is OHLC-cache tickers only, the
  same smaller denominator `rv20`/`beta_spy60` already carry, and
  `coverage()` prints before any conditional number (G2).
- Option volume = `Contracts` column of `audit/<date>-rollup.csv`, joined on
  (signal_date, ticker). DISCLOSED: this is the **flow-scrape contract count**
  (Barchart's filtered unusual-flow feed), not total listed option volume — the
  feature is an "unusual-O/S", plausibly closer to the informed subset Johnson
  & So were proxying, but it is not the literature's exact numerator and no
  read may pretend otherwise. Join hit-rate prints in G2.
- No lookahead: every feature is as-of the signal date; entry basis is
  next-day OPEN (2026-07-06 re-baseline), so signal-session volume is
  decision-time information.

**Features (three, no additions after first run).**
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
- Min-obs mirrors `underlying_features`: ≥15 usable positive-volume sessions
  else `None`; volume observations paired with a dropped split-artifact return
  (`_MAX_ABS_LOG_RETURN`) are dropped with it.
- Rescaled tickers (`rescaled_tickers.txt`): `os_ratio` KEPT (same-day
  numerator and denominator, internally consistent); `rvolz20` and `amihud20`
  WITHHELD (`None`) — a split steps the share count and fabricates exactly the
  volume spike the z-score is looking for. Withheld counts print in G2.

**Population.** Pooled real+tweak book via `load_book` (defaults: bs excluded,
proxy calibration gate ON). The exit arm runs on **calibrated debit rows only**
(same basis as every exit study; credits are ungated by `book.py` and carry no
validated replay). Descriptive tables may use the full pooled book with credit
rows flagged. v3-era exports in `backtests/to_evaluate/` by filename; v4 rows
are never pooled in.

**Hypotheses.**
- **H1 (PRIMARY — path/exit).** High unusual-O/S rows give back more: within
  structure, the HIGH `os_ratio` tercile shows (a) lower exit capture (R
  against MFE) and (b) a larger share of rows that peak below the `be_after`
  arming threshold and finish ≤ 0, versus the LOW tercile. Mechanism test —
  **frozen variant set of exactly ONE**: `be_after: 0.50` applied to NON-bear
  debit rows in the HIGH tercile only, versus PROD, leave-one-date-out
  (out-of-fold, `exit_switch` house pattern). Bear debit rows are EXCLUDED
  from the variant arm (they already carry the shipped ratchet; re-testing it
  here would double-count the 08-11 result) but their sub-arming give-back
  census BY TERCILE prints for the blocked §2.4 thread. Standing asymmetry
  rule applies: an MFE/MAE-mirrored read is a path-vol artifact, not a
  finding.
- **H2 (`rvolz20`, exploratory).** Descriptive tercile cut within structure,
  MIN_CELL_N enforced, date-clustered. No adoption path this run.
- **H3 (`amihud20` control).** Any H1 separation is re-cut within `amihud20`
  terciles; if it collapses (HIGH-os_ratio separation exists only in the
  illiquid tercile), the verdict is LIQUIDITY-PROXY, not flow information.
- **Selection (SECONDARY).** Mean R / total $ by feature tercile WITHIN
  structure only; a pooled cross-structure table may be printed but may not
  carry a conclusion. Anything that separates within structure must survive
  `protocol.walk_forward_splits` with tercile boundaries fitted on TRAIN dates
  only before it may even be called a CANDIDATE.

**Gates (non-zero exit on failure).**
- G1 calibration: `replay(DEBIT_PROD)` reproduces stored
  `(exit_reason, days_held, round(R,4))` on every calibrated debit row;
  `debit_calib` / `n_credit_ungated` quoted.
- G2 coverage BEFORE any conditional number: volume-feature hit-rates,
  `by_source` split, O/S join hit-rate, rescaled-withheld counts.
- G3 `MIN_CELL_N = 20`; thinner cells print n and are not read.
- G4 no annualised return, Sharpe, or time-to-recover anywhere.
- G5 out-of-fold discipline: descriptive tercile tables are in-sample and
  labelled as such; the only adoption-eligible numbers are LOO fold summaries
  and walk-forward TEST rows.
- Anti-tuning: the exit-variant set is `{be_after: 0.50}` and may not grow
  after any result is seen; tercile boundaries are not knobs; window lengths
  (20 sessions) are the standing `underlying_features` constants, not swept.

**Verdicts, worded now.**
- **VOLUME-CONDITIONS-EXITS** (candidate, NOT a ship): H1's LOO median AND
  total positive, sign holds on the log's standard both-window cut, H3 does
  not collapse it → queue an independent-window confirmation.
- **LIQUIDITY-PROXY**: separation absorbed by `amihud20` (H3 fires).
- **PATH-VOL-PROXY**: MFE and MAE move together with no R separation.
- **NULL**: none of the above survives its gate → the volume column is CLOSED
  and the live pipeline never pays the version bump.

---

## 2026-08-13 — labelled amendment (after first run): mirrored-path operationalization

The verdict grammar above words PATH-VOL-PROXY as "MFE and MAE move together
with no R separation". The study code's first-run operationalization compared
SIGNED tercile separations, so a HIGH cell with higher peaks and SHALLOWER
drawdowns (what the data actually showed) counted as "mirrored" and the first
run printed PATH-VOL-PROXY. The registered wording means path WIDTH moving
together — MFE up with MAE DEEPER — so the check was corrected to
`mfe_sep × (−mae_sep) > 0` and the study rerun the same day. No number
changed (seeded bootstrap; the diff between the stamped reports is the
timestamp and verdict lines only). Final verdict under the registered
grammar: **NULL**. Details in `current.md`'s RUN entry.
