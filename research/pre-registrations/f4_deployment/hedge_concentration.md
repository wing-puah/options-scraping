## hedge_concentration — on the ADMITTED book, does concentration predict drawdown, and only then does a proxy hedge cut it?

_Registered 2026-08-31._

## Question

Two questions, in a fixed order, on the book the operator actually runs rather
than the book the analysis emits.

**Stage 1 — the precondition (H-C).** On the ADMITTED book — the positions
`account_sim` takes from the ratified population under the operator's own
top-3-per-day rule and exposure caps — does a session's cluster concentration
PREDICT the book's subsequent mark-to-market drawdown? If concentration carries
no information about what comes next, no concentration-gated hedge can work,
whatever its instrument or size, and the study stops and says so.

**Stage 2 — the mechanism, run only if Stage 1 finds the precondition.** On
that same admitted book, does a long put on the concentrated cluster's proxy
reduce mark-to-market drawdown versus carrying the same concentrated book
unhedged?

This is the "third reading" `hedge_exposure`'s errata named and declined to
run under its own registration (post-ratification note 3): ratified PRICES
(real + `strike_expiry_tweak`), but an admission model over which plays are
held at once. `hedge_exposure` held every one of the 996 ratified rows
concurrently (`book_positions()` emits a position for every record; its own
report says *"It is not `account_sim`'s admitted-subset figure and the two are
not comparable"*). Doubling the book halved the triggers — median any-cluster
concentration 0.301 → 0.209, τ=0.30 triggers 256 → 91 sessions — and every
cell was power-stopped as a consequence. The operator's deployment card admits
at most 3 new positions per day (`config/account-sim.yml`
`max_positions_per_day: 3`), and on the 2026-08-27 exports `account_sim` took
221 of 458 ladder-eligible candidates. The admitted book is therefore the
closer model of the book being hedged, and `hedge_exposure` measured a more
diversified one.

**Why the precondition comes first.** `hedge_exposure` went straight to the
hedge cells and could not power them. Stage 1 does not depend on triggers at
all: it is a relationship read across EVERY session on which the admitted book
is open, so it can be powered on the dates that exist. It is also the question
every prior hedge verdict has assumed the answer to without asking.

## What this is NOT

- **Not a re-run of `hedge_exposure`, and not a re-litigation of its
  ratification.** The pricing argument for `all` is untouched and this study
  uses exactly that population as its candidate set. What changes is which of
  those candidates are HELD. Neither study's verdict overrides the other's:
  `hedge_exposure`'s UNDERPOWERED describes the every-row book, this study
  describes the admitted one.
- **Not a timing study, not a selection study, not a worst-decile study.**
  Every scope limit in `hedge_exposure`'s "What this is NOT" carries over
  verbatim: no arm is keyed to a calendar or market-state condition; selection
  (`top_k_per_day`, tiers A/B, the caps) is untouched in every arm; every
  primary metric is path-shaped over all open sessions, never a tail cell.
- **Not `concurrency_correlation`.** That study asks whether concentration
  degrades PER-POSITION outcome and its remedy is to deploy less; this one asks
  whether book-level concentration predicts BOOK drawdown and whether it can be
  overlaid. Different unit, different outcome, different remedy. Stage 1 finding
  concentration predictive is NOT evidence for a ceiling there, and a ceiling
  found there is not evidence for a hedge here.
- **Not a test of the §4 bear sleeve.** ARM H is OFF in the admitted book so
  that the counterfactual is the unhedged admitted book. The sleeve is operator
  policy; nothing here can remove it. The book's own bear row is NOT an
  instrument here — `bear_deploy` D3, `hedge_timing` H4 and `hedge_exposure`
  ARM B have each already asked that.
- **Not a test of the hedge-flow prose, and deliberately so.** The operator's
  practice has a third condition — "the analysis says people are hedging" —
  and `hedge_exposure` registered it (ARM CS) with a control (ARM P) that
  turned out inert (ERRATUM 2). The plan-time census below shows the
  prose-conditioned survivor set on the admitted book is **19 sessions / 17
  episodes** at the loosest τ, so any prose arm would be UNDERPOWERED by
  construction, and registering one with a corrected control would only add a
  second arm that can never bite. The corrected control's design — ARM C on
  concentration-matched sessions carrying NO hedge-pressure signal, matched on
  count — is recorded in `next-steps.md` §2.1 for a registration when the
  book carries materially more parsed dates. `hedge_exposure` ARM P stays
  inert and is not cited here.
- **Not an always-on hedge study.** The census shows this book is
  concentrated 75–96% of the time at `hedge_exposure`'s τ levels, so a
  concentration gate there would be nearly always-on. That is disclosed, and
  the τ grid is set above the book's median in response; whether an
  UNCONDITIONAL proxy put helps the admitted book on a mark-to-market curve
  is a different question, adjacent to `hedge_timing`'s always-on finding,
  and is not registered here.
- **Not a study of `hedge_exposure` ARM RF or any fill-independent floor.** One
  reference arm (ARM R) is registered; nothing is added after commit.
- **Not a claim about long-dated hedging.** Hedge expiries stay within
  20–120 DTE.

## Population and basis, fixed here

- **Era `v4` (`current`), and only v4.** Candidate set =
  `load_book(include_bs=False)` — real and `strike_expiry_tweak` pricing, no
  `bs_options_hist` rows: **the population `hedge_exposure` ratified, by the
  same literal call.** Era mismatch refuses (exit 3); a thin era refuses (exit
  2). v3 is not pooled and not replicated.
- **The held book = what `account_sim.simulate()` ADMITS from that candidate
  set** under `config/account-sim.yml` at its committed values — ladder tiers
  A/B via `protocol.ordered_by_day(rows, ladder_rank, ladder_eligible)`,
  `max_positions_per_day`, the cash / per-position-delta / net-delta caps in
  `admission()`, the ledger — with the ARM H bear sleeve OFF
  (`bear_by_day=None`) and no `--live-select` ranker. Positions of status
  `taken` and `taken_downsized` from `positions_rows()` are the book; skipped
  candidates are reported with their reason and are not held. **The admitted
  contracts are the sim's sized contracts, not the raw row's.**
- **Row and date counts are printed at run time, never stored.** The
  candidate-set and admitted counts below are disclosures about the 2026-08-27
  exports, not checksums; the study refuses nothing on them.
- **Session universe**: every trading session on which at least one admitted
  position is open, `[entry_sess, exit_sess]` from the sim.
- **Equity curve**: MARK-TO-MARKET from `daily_pnl_csv` via
  `lib/mtm_curve.book_curves`, on the admitted book. The realized-on-close
  curve (`account_sim.equity_curve`) is computed alongside for ARM M and for
  comparability with `account_sim`'s own drawdown figures, and is the basis of
  no verdict.
- **Equity denominator**: `config/account-sim.yml` `capital` (25,000) for every
  "× equity" quantity, exactly as `account_sim` and `portfolio_delta` use it.
- **Sector map**: `scripts/backtest_study/lib/sectors.py`, the single shared
  encoding — 11 clusters, residual BROAD → SPY, four clusters UNHEDGEABLE
  (CRYPTO, ENERGY, FINL, INTL) exactly as `hedge_exposure` fixed them. Not
  restated here and not editable here. A session whose top cluster is
  unhedgeable is carried at f=0 and counted against the fill gate.
- **Concentration** = `lib/concentration.session_concentration`: the largest
  cluster's |net signed delta notional| as a share of book gross, per session,
  over admitted positions only. Reported both any-cluster and constituent-only
  (`sectors.stratum`), as before.
- **Hedge-flow prose is censused, not used.** The registered regex
  `r"hedge[- ]pressure[^0-9]{0,15}(\d{1,3})\s*/\s*100"` on `regime` prose is
  parsed only to print coverage on the admitted dates; no arm reads it.

## Plan-time observations, disclosed

All of the following were measured from INPUT fields only — positions, delta,
contracts, entry underlying, signal date, `days_held` for occupancy, and the
`regime` prose — on the 2026-08-27 20:34 exports, before any outcome column
(P&L, R, `daily_pnl_csv`, drawdown, equity) was read. They are disclosures
about that snapshot, not checksums; the module reprints every one of them
from its own run. Working: `research/current.md` 2026-08-31 (late).

**The loader is the same.** A bare `run account_sim` loads
`load_book(include_bs=args.include_bs)` with `--include-bs` defaulting to
False (`account_sim.py:2298-2301, 2384`) — byte-for-byte the call
`hedge_exposure` ratified, verified identical at runtime (996 rows both
ways). The admitted book is therefore the ratified population, thinned by
admission and nothing else.

**Admission on the ratified population** (`config/account-sim.yml`: capital
$25,000, risk 2% = $500, max 3/day, caps 0.25× / 2.50×, ARM H OFF):

| | |
|---|---|
| candidate set | 996 rows / 145 signal dates (real 485, tweak 511) |
| ladder-eligible (tier A/B) | 458 rows / 127 dates |
| **ADMITTED** | **221** (taken 221, downsized 0) / **110 dates**, 2024-01-10 .. 2025-10-30 |
| skipped | per_pos_delta 92 · net_delta 81 · day3_cap 64 = 237 |
| session universe | **498** sessions, 2024-01-11 .. 2026-01-06 |
| concurrently open | median 15 · p75 19 · p90 21 · max 25 (0 unpriced) |
| gross / equity | median 1.86× · p75 2.32× · p90 2.45× · max 2.49× |

**The admitted book is concentrated almost always — that is the central
plan-time finding.** Any-cluster concentration: **median 0.464**, p75 0.572,
p90 0.678. Constituent-only: median 0.460 / 0.554 / 0.676. Compare
`hedge_exposure`'s every-row book: median 0.209 on `all`, 0.301 on `real`.
Thinning the book to what admission holds more than doubles its typical
concentration. The top cluster is MEGATECH on 53.6% of sessions and SEMIS on
33.7% — the two clusters the operator's scope note names — and the top
cluster is CONSTITUENT on **93.4%** of sessions (DIRECT 6.6%; pooled gross
CONSTITUENT 82.1%). Unlike `hedge_exposure`'s book, which was 62.7% DIRECT,
this book IS the described practice.

**Trigger census (episodes = maximal runs of consecutive triggered sessions,
`lib/concentration.py::episodes`, the rule `hedge_exposure` counted with):**

| τ | any-cluster sessions | episodes | constituent sessions | episodes |
|---|---|---|---|---|
| 0.30 | 477 (96%) | 9 | 425 | 8 |
| 0.35 | 438 (88%) | 12 | 390 | 10 |
| 0.40 | 372 (75%) | 20 | 339 | 16 |
| 0.50 | 227 (46%) | 13 | 189 | 13 |

Episode lengths at τ=0.30: 236, 123, 66, 21, 19, 8, 2, 1, 1. Concentration is
a PERSISTENT state on this book, not an event.

**Consequence, accepted now: Stage 2 is expected to be UNDERPOWERED at every
τ on these exports.** The episode count peaks at **20** (τ=0.40) against the
≥25 floor, and it falls, not rises, as τ tightens further, because tightening
splits long runs rather than creating new ones. This is the same disclosure
`hedge_exposure` made for its constituent stratum, made here for the whole
grid: a later UNDERPOWERED Stage 2 reads as predicted, and under the Ship
criteria below it still moves §2.1. **Stage 1 is the load-bearing stage of
this study**, by design and now by census.

**A concentration-GATED hedge on a book that is concentrated 75–96% of the
time is nearly an always-on hedge.** That is disclosed rather than designed
around: the τ grid below starts at the book's median, so that "concentrated"
means more than its normal state, and it goes no lower.

**Gross and concentration are only weakly related**: Spearman(gross,
any-cluster concentration) = **+0.10**, Spearman(open count, concentration)
= +0.01 over 498 sessions. ARM KG is therefore a real control — the two
variables are separable on this book.

**Dense episodes of admitted signal dates** (`account_sim.dense_episodes`,
max_gap 5, min_dates 10): **3** — 2024-01-10..03-19 (18 dates),
2024-04-29..06-14 (12), 2025-05-19..07-11 (13); 43 of 110 admitted dates and
89 of 221 admitted positions fall inside one. G-POWER-K's episode floor is met
exactly, not comfortably.

**The hedge-flow prose is untestable on this book.** Of 110 admitted signal
dates, 71 parse a `hedge-pressure` value (64.5%) and **11** read ≥50; at
τ=0.30 the prose-conditioned survivor set is **19 sessions / 17 episodes**.
No prose arm can clear a 25-episode floor here. See "What this is NOT".

**Contrast, `real` stratum only (not a population of this study):** 144
admitted / 83 dates, open median 9, any-cluster median 0.478, **0 dense
episodes**. It is disclosed so a reader can see that the ratified population
is what makes Stage 1 powerable at all.

## Arms

Stage 1 runs on the unhedged admitted book and gates Stage 2. Stage 2's grid is
fixed at 3 τ × 3 f = 9 cells per arm.

### Stage 1

- **ARM M — measurement.** The unhedged admitted book on both curves:
  max drawdown, Ulcer index and time-under-water, mark-to-market versus
  realized-on-close. Runs first, gates nothing. It is the direct measurement
  of the curve `bear_deploy` D3 was read on, because this IS `account_sim`'s
  book.
- **ARM K — concentration predicts (the precondition).** For every open
  session s, x(s) = any-cluster concentration at the close of s, computed from
  positions open at s; y(s) = the book's forward mark-to-market drawdown over
  the next **H = 20 sessions**: the minimum of (equity(t) − equity(s)) for
  s < t ≤ s+H, in dollars, ≤ 0. Sessions with fewer than H forward sessions
  before the book goes flat are dropped from ARM K only (never from the
  universe). Two reads, both required:
  - **tercile contrast** — mean y over the top concentration tercile minus
    mean y over the bottom tercile (terciles by x over the universe);
  - **rank association** — Spearman ρ between x and y.
  Sign convention: the precondition predicts the top tercile draws down MORE
  (contrast < 0, ρ < 0).
- **ARM KG — gross-exposure control for ARM K.** ARM K re-read within terciles
  of book gross / equity. A concentrated book is often just a bigger book; a
  concentration effect that vanishes within gross terciles is a gross-exposure
  effect wearing a different name. Reported as the share of gross terciles in
  which ARM K's contrast keeps its sign.
- **ARM KN — the time-structure null for ARM K, 1,000 draws.** The
  concentration series x is circularly shifted against the fixed drawdown
  series y by a random offset of at least H sessions; ARM K's contrast and ρ
  are recomputed per draw. This preserves the autocorrelation of both series,
  which a row shuffle would destroy. **ARM K must beat ARM KN's 5th percentile
  (more negative), not merely be negative.** Seed fixed and printed.
- **ARM K10 — registered sensitivity, never concluded from.** ARM K at H = 10.
  Reported beside ARM K; carries no verdict and cannot rescue one.

### Stage 2 — run only on PRECONDITION-FOUND

- **ARM C — concentration-gated proxy put.** Hedge on any session where
  any-cluster concentration ≥ τ, **τ ∈ {0.45, 0.55, 0.65}** — the census's
  median, p75 and p90, rounded, so that the loosest trigger means "more
  concentrated than this book usually is" — sized at fraction
  f ∈ {0.25, 0.50, 1.00} of a standard position's risk, admitted THROUGH
  `account_sim.admission()` after the day's picks in the ARM H pattern — not
  counted against `max_positions_per_day`, and a hedge that sizes below one
  contract is SKIPPED and counted, never floored up to one. Instrument = a long
  put on the concentrated cluster's proxy; band rule (25–75 DTE, strike within
  ±5% of close) primary, nearest-available (nearest strike at-or-below spot,
  expiry nearest 45 DTE within 20–120) the registered sensitivity. Carries no
  prose. **There is no prose-conditioned arm in this study** — see "What
  this is NOT".
- **ARM N — random-admission null, 200 seeds.** Hedges on a random session set
  matched to the triggered set in episode COUNT, episode LENGTHS and PROXY mix.
  An arm must beat ARM N's 95th percentile on the metric it is judged on.
- **ARM R — always-fillable reference.** ARM C with a delta-equivalent SHORT in
  the proxy underlying instead of a put. A feasibility floor and the control
  for clause 7 — not an instrument the operator trades and never a
  recommendation.

## Unit and metric

- **Unit**: the session. Every Stage 1 interval is a block bootstrap over
  non-overlapping blocks of H sessions (BOOT_N = 10,000, seed printed) — the
  forward windows overlap, so a session-level or date-level resample would
  understate the variance. Every Stage 2 interval is date-clustered, as in
  `hedge_exposure`.
- **Stage 1 primary**: the ARM K tercile contrast in dollars.
  **Co-primary**: Spearman ρ.
- **Stage 2 primary**: max drawdown in dollars on the mark-to-market admitted
  book, hedged versus unhedged. **Co-primary, path-shaped**: Ulcer index and
  time-under-water.
- **Secondary, reported never concluded from**: total P&L, worst single
  session, realized-on-close max drawdown, ARM K10.

## Gates

- **G-ERA** — v4 or refuse (exit 3); thin era refuses (exit 2).
- **G-ADMIT** — the admitted book must reproduce `account_sim.simulate()`'s
  default-arm book EXACTLY under `book_signature()` equality when run on the
  same candidate set with the same config. A drifted local admission is a
  finding about the drift, and the run refuses (exit 5). This is
  `portfolio_delta`'s G-EQUIV, applied here.
- **G-MTM** — the mark-to-market curve reconciles to the realized-on-close
  curve at every admitted position's exit, to within $0.01 per contract
  (`hedge_exposure`'s check, exit 4).
- **G-BLIND** — every trigger and every ARM K regressor is computable with
  outcome fields stripped (`blind_records` / `BlindRec`); the session set
  under blinded records must be byte-identical to the sighted run, or the
  study prints `LOOKAHEAD DETECTED` and refuses. Occupancy needs `days_held`,
  which is an outcome field; it is used for occupancy ONLY, and the blind
  check strips every other outcome key.
- **G-POWER-K** (Stage 1) — ≥ **60 sessions in each concentration tercile**
  after the forward-window drop, spread over ≥ **3 dense episodes**. Below
  that, ARM K is UNDERPOWERED and carries no verdict.
- **G-FILL** (Stage 2) — a hedge fillable on ≥60% of triggered sessions under
  the band rule; unfillable sessions carried at f=0. Below 60% the proxy-put
  arms are NOT EVALUABLE and only ARM R is read.
- **G-POWER** (Stage 2) — ≥ **25 trigger DATES** (date-clustered) per cell;
  below that the cell is UNDERPOWERED and carries no verdict. **UNDERPOWERED
  is not a lean.**
- **G-CENSUS** — the trigger and tercile census is computed and printed from
  input fields before any outcome column is read; the report states which
  lines are input-only.

## Bar for a candidate

**Stage 1 — PRECONDITION-FOUND requires ALL of:**

1. ARM K's tercile contrast is **negative** with a block-bootstrap 95% CI
   excluding zero.
2. Spearman ρ is **negative** with a block-bootstrap 95% CI excluding zero.
3. The contrast is **beyond ARM KN's 5th percentile**.
4. **Not a gross-exposure effect in disguise**: ARM KG keeps the contrast's
   sign in **at least 2 of 3** gross terciles.
5. Sign retained in **every dense episode** with ≥ 20 usable sessions.
6. Sign retained under **both ex-window cuts** (`protocol.DOMINANT_WINDOWS`).

**Stage 2 — a cell is a CANDIDATE only if ALL of** (carried verbatim from
`hedge_exposure`, α = 0.05/9):

1. Max drawdown AND worst single session both no worse than f=0.
2. At least one co-primary path metric improves with a date-clustered CI
   excluding zero at α = 0.05/9.
3. Beats ARM N's 95th percentile on that same metric.
4. Positive in ≥ 2 of the book's years.
5. Both ex-window cuts retain the sign.
6. Every leave-one-date-out fold retains the sign.
7. **Not a delta reduction in disguise**: the improvement exceeds ARM R's at
   the same τ and f, or it is reported as A RESTATEMENT OF DELTA REDUCTION.

## Verdicts, worded now

Stage 1 emits exactly one of:

- **PRECONDITION-FOUND** — every Stage 1 clause clears. Stage 2 runs.
- **PRECONDITION-NULL** — G-POWER-K passes and a clause fails, with the
  contrast inside ARM KN's band or the wrong sign. Reads as: *on the book the
  operator runs, how concentrated it is says nothing about how far it draws
  down next; a concentration-gated hedge has no trigger to stand on.* Stage 2
  is NOT run; its trigger census is printed for the record and no cell is
  evaluated.
- **GROSS-NOT-CONCENTRATION** — clauses 1–3 clear but clause 4 fails. Reads
  as: *bigger books draw down more; the cluster structure adds nothing.* Stage
  2 is NOT run. This is a real finding and it points at `portfolio_delta` and
  `concurrency_correlation`, not at a hedge.
- **UNDERPOWERED** — G-POWER-K fails. No direction quoted.

Stage 2, when it runs, emits one of `hedge_exposure`'s words over the same
objects: **MECHANISM-FOUND**, **NULL**, **CONTRARY**, **UNDERPOWERED**,
**NOT EVALUABLE**. MEASUREMENT-ONLY is not a Stage 2 word here: ARM M is
reported as a measurement in every run and never as a verdict.

**Asymmetric reading rule, binding.** DIRECT versus CONSTITUENT strata are
always reported; a DIRECT result is never evidence for the constituent
practice, nor a DIRECT null evidence against it.

**No prose, no prose rule.** Every arm here is computed from positions alone,
so the model-recall lookahead `hedge_exposure` disclosed for its prose does
not reach any verdict in this study. The flow inputs behind the positions were
point-in-time.

## Anti-tuning

- **H = 20, the tercile rule, the τ grid, the f grid, the fill rules and the
  DTE window are fixed here** before any outcome column is read. The τ grid
  was chosen from the input-only census disclosed above and may not be moved
  after commit; if no τ triggers ≥25 dates, the answer is UNDERPOWERED, not a
  new τ — and the census already says that is the expected outcome.
- **One Stage 1 horizon carries a verdict.** ARM K10 is a disclosed
  sensitivity; it cannot rescue or overturn ARM K.
- **9 Stage 2 cells, Bonferroni α = 0.05/9.** No second grid.
- **No stored expected figure.** Counts are printed from the run.
- **No annualised figure, Sharpe, or time-to-recover.**
- **Cache state in the report header**, as `hedge_exposure` prints it.
- **Stage 2 does not run on a non-FOUND Stage 1**, and a later reader may not
  run it by hand and quote it: a hedge tested on a trigger that carries no
  information is a hedge tested on noise.

## Ship criteria

**NOTHING SHIPS FROM THIS STUDY WITHOUT OPERATOR SIGN-OFF**, and — the reason
this registration exists — **every outcome has a branch that moves
`next-steps.md` §2.1 out of its current state.** The clause `hedge_exposure`
lacked is written here:

- **PRECONDITION-NULL or GROSS-NOT-CONCENTRATION** — recorded in
  `research/deployment-evidence.md` as **closing the queued max-drawdown
  question for concentration-gated hedging**. §2.1 is closed. This says
  nothing about hedging in general and does not touch the §4 sleeve.
- **PRECONDITION-FOUND + Stage 2 MECHANISM-FOUND** — a DRAFTED amendment to
  `docs/deployment-rules.md` §4, held in `research/` (draft-and-hold, the
  operator's chosen posture). §2.1 becomes "drafted, held".
- **PRECONDITION-FOUND + Stage 2 NULL or CONTRARY** — recorded in
  `deployment-evidence.md` as closing the question on this book. §2.1 closed.
- **PRECONDITION-FOUND + Stage 2 UNDERPOWERED or NOT EVALUABLE** — §2.1 is
  re-labelled **BLOCKED ON NEW DATES / FILLS** with the shortfall printed
  (trigger dates per cell against 25; fill share against 60%), the same status
  §2.3 already carries. It is no longer a live task.
- **Stage 1 UNDERPOWERED** — §2.1 re-labelled BLOCKED ON NEW DATES with the
  shortfall against G-POWER-K printed.

## Build notes

_Not part of the registration._

- Module: `scripts/backtest_study/f4_deployment/hedge_concentration.py`;
  needs a `catalog.STUDIES` entry, a `research/study-map.md` line and an
  `arm-index.md` block (ARM K / KG / KN / K10 are new letters; `ARM K`
  collides with `concurrency_correlation`'s clustering ceiling — qualify
  every citation). The plan-time census script that produced the disclosed
  figures was a scratch script; the module reprints every figure from its own
  run and is the reproducible record.
- `DESIGNED_REFUSAL_EXIT_CODES = {2, 3, 4, 5}` as an AST literal; 5 = G-ADMIT.
  G-BLIND exits 1 by design, as in `hedge_exposure`.
- Reuse, do not reimplement: `lib/era.load_book`, `account_sim.simulate` /
  `positions_rows` / `book_signature` / `session_series` / `blind_records`,
  `lib/concentration` (`open_book_by_session`, `session_concentration`,
  `concentration_series` — they must accept the admitted position list with
  the sim's contracts; extend by parameter, not by copy), `lib/mtm_curve.
  book_curves`, `lib/sectors`, `lib/hedge_instrument` for the put/short
  pricing and the fill rules, `protocol.DOMINANT_WINDOWS`, and
  `account_sim`'s dense-episode helper for G-POWER-K's episode count.
- New helpers belong in `lib/`: a block bootstrap over fixed-length session
  blocks, a circular-shift null, and the forward-drawdown series. Keep them
  free of study-specific constants; H is a parameter.
- `harness.py` is FROZEN; it prices one position and is used only as
  `account_sim` uses it.
- The report must state, in the header, that ARM H was OFF and that the book
  is the admitted subset, and must print the skipped-candidate census next to
  the admitted one so a reader sees what was NOT held.
