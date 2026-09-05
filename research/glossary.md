# Backtest tuning glossary

Every metric and term the study reports in `backtests/study_output/` print,
defined against the code that computes them — not textbook-generic.

## 1. How to read this

Audience: the project owner reading a study report who doesn't recall what
`CI-lo` or `exit_basis=BEAR_HE` means. Each entry is a bold term, one plain
sentence, then (where it isn't obvious) one sentence on *why* it's measured
that way, naming the defining file (`protocol.py`, `harness.py`, `book.py`,
`account_sim.py`, or a named study module) — no line numbers, they rot.

This file is also inlined into the automated "digest" LLM call as its source
of truth for definitions — extend it rather than let the digest invent one.
Scope: terms, not conclusions. What a study found lives in `current.md`;
what's shipped lives in `deployment-rules.md`.

## 2. Core P&L metrics

### R
realized P&L %: what actually happened under whatever exit rule
governed the trade (`realized_pnl_pct` on the stored row, or the `pnl_pct`
a `harness.replay()` call returns when a study re-simulates under a
different rule). The FROZEN-EXIT-RULE outcome.

### E
P&L % at the path cap (`pnl_at_cap_pct`): what the position would
show held to the end of its priced path with no exit rule at all. The
HELD-TO-CAP baseline. **R vs E is the crucial distinction** in every
report: R asks "did the exit rule make money," E asks "was there money in
the move regardless of when we got out." A report that only shows E can't
speak to exit quality; one that only shows R can't tell you whether a bad
exit is throwing away a good signal. Both assembled per row in
`book.py`'s `_build_record`.

### meanR
arithmetic mean of R across a set of rows; the number most
tables lead with.

### R_dol / E_dol
R or E in dollars at the position's actual size
(`R × abs(entry_option_price) × 100 × contracts`, `Trade.dollars()` in
`harness.py`). Summed across a book, this is what the strategy actually
made or lost.

<a id="pf"></a>
### PF (profit factor)
Gross dollars won divided by gross dollars lost across a set of rows. Above 1.0 the set made money; 2.0 means winners paid for losers twice over. Quoted in `docs/deployment-rules.md` §7 reference tables beside meanR, because a high meanR carried by one large winner shows up as a PF close to 1.0.

<a id="win-rate"></a>
### win%
share of rows with R > 0. Blunt alone (90% win rate can still
lose money to a few large losers) — read next to meanR, not instead of it.

### n vs dates
`n` = row count (one per play); `dates` = distinct
`signal_date`s those rows span. They diverge whenever several plays fire
the same day, which is usual — and is why almost nothing here resamples
on `n`. See §3.

## 3. Uncertainty & robustness

<a id="ci"></a>
### CI95 (date-clustered bootstrap)
95% CI for a mean (usually meanR or
meanE), from `protocol.boot_ci_by_date`: resample *dates* with
replacement (a date's rows always travel together), recompute the mean,
repeat 10,000×, take the 2.5th/97.5th percentiles. **Why dates, not
rows:** rows inside one `signal_date` share the same day's tape — not
independent draws — so bootstrapping rows individually overstates
sample size and narrows the CI artificially. `CI-lo`/`CI-hi` are its
ends; "CI excludes zero" is the usual bar for calling an effect real.

### Paired CI
`protocol.boot_ci_paired_by_date`: the same date-clustered
resample on the *difference* of two means on the SAME rows (e.g. a model
vs the deployed ladder). Paired because comparing two book means
independently would mostly measure which days each traded, not which is
better.

<a id="loo"></a>
### LOO / leave-one-date-out
`protocol.loo_by_date`: drop one
`signal_date` at a time, recompute a candidate rule's gain over a
baseline on what's left, report `(mean_gain, share_of_folds_positive,
min_gain, n_folds)`. A rule SURVIVES only when every fold stays positive
(`share == 1.0`).

**"Fold" here is the KEPT set, not the held-out one.** The word is the
usual cross-validation one, but the usual meaning is inverted. In
ordinary leave-one-out you train on the rest and SCORE the one you held
out. Here the dropped date is never scored. One fold is the whole book
minus one signal date, and the gain is measured on that remainder. There
are as many folds as there are dates. So the question is not "does the
rule predict the date I hid," it is "does the rule still win if any one
date had never happened." That is a robustness check, not a
generalisation check — the split discipline in §4 is where
generalisation is tested.

**Why min_gain matters more than the mean:** a
one-date-driven rule can still show a high mean gain and a share "just
under 1" — only `min_gain` catches the single fold that flips when its
carrying date drops. This check killed the per-regime exit switch
candidate twice (`current.md`).

<a id="mwu"></a>
### MWU (Mann–Whitney U / Wilcoxon rank-sum)
nonparametric two-sample
test of whether one group's values systematically OUTRANK another's —
effectively `P(random row from A > random row from C) ≠ 0.5`. It uses ranks
only and never touches either mean. **Why rank-based here:** R is floored
by the stop, zero-inflated and long-tailed, so a t-test's p would be driven
by a handful of outsized winners. **Read it with the CI95 caveat above:**
MWU assumes independent observations and rows sharing a `signal_date` are
not, so it overstates significance on this book — it is the OLDER evidence
style here, superseded by the date-clustered bootstrap and LOO. Treat a
surviving MWU p as supporting evidence, not the standard. A HIGH p is still
informative: the ladder's `A vs B p = .98` (`deployment-evidence.md`) says
those two tiers are ordered but NOT separated — a watch item, still open.

### sign-stability
`protocol.sign_stable`: mean of a key per year;
checks every year has the same sign. A sign that flips across years is
treated as a window artifact until proven otherwise (the 2026-08-08
screen standard).

### terciles
`underlying_features.terciles`: the two cut points
splitting a population into equal thirds on a feature, computed from the
study's OWN population rather than a fixed level — most features (e.g.
realized vol) have no fixed scale across tickers. Returns `None` below 9
usable rows; NaNs are filtered explicitly (a 2026-08-12 bug let NaN
`iv_pct` rows corrupt both cut points and swept 69% of a population into
the "bottom" tercile).

## 4. Split discipline

### Purged walk-forward + embargo
`protocol.walk_forward_splits`:
expanding-window walk-forward over 15-date test blocks; train is
restricted to dates ≥`embargo_days` (120, `PATH_CAP_DAYS`) before the
test block starts, and a block with a purged train set under 40 dates is
skipped. **Why the embargo:** a trade's outcome can take up to
`path_cap_days` calendar days to resolve, so without the gap a training
row's label may not exist yet in reality at test time — leaking the
future label backward flatters whatever's evaluated (Lopez de Prado's
purged CV).

### Year-epoch split
`protocol.year_epoch_split`: the strict version —
train on every (embargoed) date before a target year, test only that
year. Used to ask "does this generalize to a whole future year" rather
than "block by block."

### Window-dominance re-cuts
`protocol.window_cuts` /
`DOMINANT_WINDOWS`: every headline number is re-computed excluding two
calendar windows, March–April 2025 and February–April 2026, because each
has single-handedly carried a result before. Surviving `ALL` but
collapsing under `ex_2025_mar_apr` or `ex_2026_feb_apr` marks a window
effect, not a general one.

## 5. Risk & path

### maxDD
largest peak-to-trough decline in a cumulative realized-dollar
equity curve (`bear_deploy.max_drawdown`, reused by `account_sim.py`),
booked on the session a position exits. Open positions aren't marked to
market on this curve, so maxDD *understates* true intra-position drawdown.

<a id="mfe"></a>
### MFE / MAE (Max Favorable / Adverse Excursion)
the best (MFE) or
worst (MAE) P&L % a trade reaches anywhere on its full daily path,
independent of the exit rule (`mfe_pct`/`mae_pct`,
`docs/backtest-reference.md`). MFE tunes the profit target, MAE tunes
the stop. **Asymmetry reads:** near-mirrored MFE/MAE across two groups
usually reflects shared path volatility, not a real difference — read
them alongside R, not as a standalone verdict.

### Path cap
`path_cap_days` (120, `config/backtest.yml` /
`harness.PATH_CAP_DAYS`): the simulated path never runs past this many
calendar days from entry, bounding far-dated/LEAP trades. Still open at
the cap → exits `cap_open` (below).

## 6. Exit reasons

`harness.replay()`'s exact vocabulary, checked in this priority order every
simulated day: `profit_target` → `trailing_stop` → `underlying_stop` →
`dollar_stop` → `stop_loss`/`be_stop` → `time_exit` (`dollar_stop` and the
terminal states always run regardless of exit config).

### profit_target
today's P&L hit the profit-target threshold (`pt`).

### trailing_stop
after peak P&L crossed the trail-activation trigger
(`trig`), P&L fell `trail` below that peak.

### underlying_stop
credit-side: underlying's close breached a
strike-based threshold (short strike ± buffer for verticals; breakeven
basis for straddle-like structures, since a strike-basis breach fires day
one when the short strike is already near the money).

### dollar_stop
dollar loss hit `MAX_LOSS_ABS` ($1,000, a $50k book's
2% risk budget) — checked on every trade regardless of exit profile.

### be_stop
peak-P&L-triggered breakeven stop: once the position's
RUNNING peak P&L reached `be_after`, the stop tightens from `-sl` to `0`,
so a former winner can't slide through breakeven into a loss. "Peak" is the
max-so-far of `(mark − entry) / |entry|` on the daily mark grid — causal,
not the completed path's MFE — so the rule is implementable live.

### stop_loss
P&L fell to `-sl`.

### time_exit
held `dte_entry × tef` days with nothing else triggering.

### expired
held to the nearest leg's expiration, nothing triggered.

### cap_open
still open at the `path_cap_days` boundary; recorded P&L
is the mark on the last priced day, not a closed trade's outcome.

### Exit basis & mechanical regime cells

A different axis from the vocabulary above: not *why* a position closed, but
WHICH exit profile was in force when it did.

**Mechanical regime cells** (`lib/mech_regime.py` — FROZEN spec; changing a
threshold invalidates every gate decision resting on it):

#### mech_cell
the stored per-row label naming that signal date's regime
cell, computed from SPY/^VIX closes ON OR BEFORE the signal date only, so
it is causal and safe to key a trade decision on. Two axes: direction is
**BEAR** (SPY < 50-day SMA AND 20-day return < 0), **BULL** (SPY > SMA AND
return > 0), else **RANGE**; vol is **E-VOL** (VIX ≥ 30 OR 5-day VIX change
≥ +25%), **H-VOL** (VIX ≥ 20), else **L-VOL**. **Exit conditioning ONLY** —
the model's own regime label from the analysis remains the basis for
SELECTION gates. The two label sources win on opposite jobs (`current.md`
§2026-07-22 addendum 4), so neither substitutes for the other.

#### BEAR_HE
BEAR direction AND vol in {H-VOL, E-VOL}; "HE" = H-VOL *or*
E-VOL. The only cell that ships an exit override (trail 0.50 / trigger
0.50, shipped 2026-07-22).

#### LVOL
vol == L-VOL, ANY direction.

#### RB_EVOL
direction in {RANGE, BULL} AND vol == E-VOL; "RB" =
RANGE-or-BULL. A vol spike without a downtrend.

#### NONE / NO_DATA
the two sentinels: `NONE` = labelled fine, but the
regime maps to no override cell; `NO_DATA` = could not label at all (table
missing, or it ends before the date). Explicit names rather than a blank,
because blank is indistinguishable from "row written before this column
existed" — both failure modes get named.

`MechLabeler.cell()` tests those three IN THE ORDER LISTED, so **BEAR +
L-VOL lands in `BEAR_HE`, never `LVOL`** — and only 3 of the 9 direction × vol
combinations are named cells at all; everything else is `NONE`.

**Which profile governed the row** (`docs/backtest-reference.md`; written by
`simulate.py::_exit_basis`):

#### exit_basis
the exit profile that actually governed a result row:
`{CREDIT, <regime cell>, BEAR_DEBIT, PROD}`, plus `NONE` for proxy rows
where no exit rules run. Config merges base → structure → regime, and the
column is reported in **merge-precedence order** (`CREDIT` → regime cell →
`BEAR_DEBIT` → `PROD`), so the label always names the profile that won.

#### PROD
the base `simulation:` block governed the row and nothing
overrode it: `profit_target` 0.90 / `stop_loss` 0.75 /
`time_exit_dte_fraction` 0.75, no trail. That precedence order is what
keeps `PROD` meaning **base config only**, never "base plus whatever merged
on top".

#### DEBIT_PROD
the same profile named as a study BASELINE. A delta
measured against it **overstates production impact** wherever a regime cell
already converts the same rows: the 08-11 bear-debit breakeven stop scored
+0.041 meanR / +$16.4k against `DEBIT_PROD` but +0.015 / +$5.9k against live
production, which had shipped the BEAR_HE trail since 07-22
(`deployment-evidence.md`). An exit study should quote BOTH baselines.

- ⚠️ **`exit_basis` is trustworthy PER ERA — v4 yes, v3 no.** On v3 and
  earlier the tab header never gained the name, so the values landed in an
  unlabelled trailing column, scrambled relative to their rows (measured
  2026-08-14); those exports are frozen, so it stays unreadable there. On v4
  the tab was recreated at the version bump and the column is clean — 485/485
  rows labelled, internally consistent (re-measured 2026-09-02). Stratifying a
  v4 book by exit profile is what the column is FOR. But to ask whether a row
  *replays* under a profile, still classify mechanically from unreachable exit
  reasons (`lib/replay_basis.py`) — that is a different question and works on
  every era. Full diagnosis in `docs/backtest-reference.md`.

## 7. Sizing & exposure (`account_sim.py`)

A $25,000-account feasibility ledger wrapped around the SAME frozen
selection and exits described elsewhere in this file — nothing about
signal or exit logic changes here, only "can a small account hold these
positions."

### Delta-notional
`signed_dn()`: `delta × 100 × contracts ×
entry_underlying`, a position's dollar-equivalent exposure to the
underlying moving $1. Signed, so long and short exposure offset.

### Per-position cap / net cap
`caps.per_position` (0.25× equity) and
`caps.net` (1.50× equity) in `config/account-sim.yml`: the max absolute
delta-notional one position, or the whole open book's net delta-notional,
may reach. `grids.per_position` / `grids.net` sweep other values for a
monotonicity check ONLY — no grid cell's P&L may be adopted as a
recommendation.

### Reserved capital
dollars set aside for an open position's
structural max loss, tracked by `Ledger` alongside `cash`/`realized`; the
identity `cash + reserved == capital + realized` is checked after every
open/close.

### MAX-LOSS budget sizing
`risk_contracts()`: `max(1, budget /
max_loss_per_contract)` — sizes so a position's worst-case structural
loss consumes the risk budget, never the premium alone.

### Utilisation / occupancy
`session_series()` reports reserved
capital, gross and net delta-notional as a fraction of equity per
session. **Occupancy** = which sessions a position counts "held," entry
session through exit session inclusive; capital frees up the FIRST
session *after* exit, never the same one.

### ARM R vs D
how an admission failure is handled: **R** (reject)
drops a candidate a cap would breach; **D** (downsize) instead takes the
largest contract count that still fits.

### F1 vs F2
the 1-contract-floor question: **F1** takes a position at
1 contract even if its max loss exceeds budget (production behavior, the
HEADLINE cell); **F2** refuses it outright.

### Gates G1–G4
hard pass/fail preconditions checked before any results
print (§9): G1 reproduces the known deployed-book totals; G2 checks the
dollar-stop scaling identity reproduces stored outcomes exactly at
scale=1; G3 checks the ledger's accounting identity never breaks; G4
checks the unconstrained walk reproduces `top_k_per_day`'s selection
exactly.

### Criteria A1–A6
the feasibility questions once gates pass: A1 edge
survival (mean R positive, CI excludes zero, every year positive), A2
attrition (constrained $ vs the unconstrained B2 baseline, same dates),
A3 no blowup (drawdown bound, no ledger violation), A4 attribution (every
candidate accounted for across taken/rejected buckets), A5 stability
(A2's ratio holds under the §4 window re-cuts), A6 credit sensitivity (A1
re-checked on debit-only rows).

## 8. Selection & population

### Tier ladder A/B/C/VETO
`book.ladder_tier()`, per
`docs/deployment-rules.md`: **VETO** = never emitted
(`bear_call_spread` always; BEAR + H-VOL regime always); **A** =
highest-conviction (`bull_call_spread` in RANGE regime or E-VOL); **B** =
`bull_call_spread` otherwise, or `bull_put_spread` meeting the delta/DTE
constraint (0.08 ≤ |delta| ≤ 0.20, DTE ≤ 59); **C** = everything else,
never deployed.

### ladder_rank
deployed ordering: tier first (A > B > C > VETO),
`score_total` as a tie-break WITHIN a tier only, and only on rows written
after the Attempt-13c prompt change (`post13c`) — `score_total` is
decision-irrelevant for which tier a play lands in.

### ladder_eligible
filters to tiers A and B only; C and VETO never
taken regardless of rank.

### top-k/day
`protocol.top_k_per_day`: the top `k` (=3 in production)
eligible rows each date, mirroring the "1–3 positions/day, tier order"
operator rule in `deployment-rules.md`.

### PRIMARY dense episodes vs SECONDARY full book
`dense_episodes()`:
PRIMARY = maximal runs of signal dates with no internal gap over 5
trading sessions and ≥10 dates — a continuously-tradeable stretch.
SECONDARY = every date in the pooled book, gaps included; only an
availability upper bound / concurrency lower bound and, per the
`account_sim` pre-registration, "may not carry a conclusion alone."

## 9. Verdict grammar

### ARM
one independently-verdicted question inside a study. A study
may earn one verdict PER ARM (`macro_event_study` earns ARM I and ARM P
separately), which is why one report can read NULL on one arm and
LAG-TOLERANT on another. **Arm labels are STUDY-LOCAL and are NOT
defined here** — each is defined in its own study's file under
[`pre-registrations/`](pre-registrations/) or module, and the same
letter means four different things: `ARM P` is *persistence* in
`emission_timing`, *P&L outcomes* in `macro_event_study`, the `be_after`
*production baseline* in `bear_giveback`, and *portfolio contribution*
in `bear_rewrap`. **Look one up in
[`arm-index.md`](arm-index.md)** — organised by study, so everything a
study owns sits under its own heading; a repo grep mostly returns one
study citing another's arm. Always resolve an arm against the study that printed it,
and name that study when quoting one (`emission_timing ARM P`, never a
bare `ARM P`).
Not to be confused with the config-variant "arms" of `account_sim`
(**ARM R vs D**, **F1 vs F2** in §7) or its `--compounding` /
`--structure-universe` / `--live-select` CLI arms, which are alternative
RUNS of one study rather than separate questions.

### Gates (hard fail)
checked first; if even one fails the run stops
and prints nothing further (`account_sim.run_gates`). A non-zero exit
here means the gate did its job, not that something needs fixing.

### Criteria (MET / NOT MET)
pre-registered numeric thresholds checked
once gates pass; each gets a plain verdict against its stated bar — no
rounding the bar to fit the result.

### NOT EVALUABLE
**UNDERPOWERED**, not a failure: a cell's sample size
fell below a pre-registered power floor (e.g. `calendar_hedge.
MIN_N_TO_READ = 10`), so its CI literally can't be read. Its own state
so a thin-n subset never silently gets counted as a negative finding.
Reports, registrations and log entries dated before 2026-08-22 call this
same state a **POWER STOP** / **POWER-STOPPED**; the wording was retired
that day, the meaning is unchanged, and the older documents are quoted as
they printed rather than rewritten.

### FEASIBLE variants
(`account_sim.print_verdict`) — **FEASIBLE** (every
criterion holds), **FEASIBLE-BUT-DEGRADED** (edge + no-blowup hold but
attrition doesn't), **NOT FEASIBLE AT $25k** (edge itself fails), or a
printed **"NO PRE-REGISTERED VERDICT MATCHES"** when the outcome falls
outside those three named buckets — reported as-is rather than force-fit.

### Why "nothing ships from this study"
several studies (`account_sim`,
`calendar_hedge`) are pre-registered as read-only feasibility/robustness
checks: passing every gate and criterion still doesn't change
`deployment-rules.md` by itself. A finding ships only after grading by
the replication protocol (§10) and write-up into `current.md` /
`deployment-evidence.md` — a report is evidence toward that, not the
decision.

## 10. Provenance & the replication protocol

### Provenance header
top of every report: run timestamp, exact
command, git SHA plus working-tree clean/dirty state, Python version,
and row count + mtime of every input CSV. Lets a reader confirm which
exact code and data produced the numbers, and flags when two
"comparable" studies ran against different exports.

### Pre-registration
a `##` section in `current.md` written BEFORE a
study runs, naming its gates, criteria, thresholds, anti-tuning rules in
advance. The run can't add or loosen a criterion after seeing results.

### Analyst A / B
two independent `research-analyst` subagents spawned
with an IDENTICAL prompt (same pre-registration section, same report
path), each producing a fixed MET/NOT MET/NOT EVALUABLE table. Neither
sees the other's output (`replication-protocol.md`).

### Validator
a `research-validator` subagent run after both analysts
return; checks their numbers against the source report, flags
disagreements and methodology violations, stops there — no new claims,
no ship/no-ship call.

### Adjudication
the validator's output: a table of A vs B vs resolved
answer, written into the `current.md` entry as a "Disagreement log" even
when it found none (absence must never read as "we didn't check").

## 11. See also

- [`docs/backtest-reference.md`](../docs/backtest-reference.md) — raw column
  definitions for `BacktestResults`/`BacktestProxy` (`realized_pnl_pct`,
  `mfe_pct`, `exit_basis`, etc. on the underlying row).
- [`lib/mech_regime.py`](../lib/mech_regime.py) — the FROZEN spec behind the
  mechanical regime cells (§6): thresholds, cell precedence, and the
  `NONE`/`NO_DATA` sentinels.
- [`docs/rollup-reference.md`](../docs/rollup-reference.md) — per-ticker
  flow-rollup columns (`oi_confirm_pct`, `cpir`, `iv_spread`, `iv_skew`,
  `iv_pct`) that ride along on analysis/backtest rows.
- [`replication-protocol.md`](replication-protocol.md) — the full
  MET/NOT MET/NOT EVALUABLE grading protocol referenced in §9–10.
- [`arm-index.md`](arm-index.md) — every ARM label in the repo (§9), its
  owning study and what it varies, organised by study.
- [`pre-registrations/`](pre-registrations/) — one file per study; the full,
  immutable definition of that study's arms, hypotheses and criteria.
- [`README.md`](README.md) — how to run a study and where its write-up
  lands.
- [`docs/deployment-rules.md`](../docs/deployment-rules.md) — the operator
  card the tier ladder (§8) and exit profiles (§6) implement.
