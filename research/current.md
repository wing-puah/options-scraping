# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index. Pruned 2026-08-31: everything up to
2026-08-27 moved to [archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md)
(08-14/15 — era-scoping, suite repair, `selection_order`), [archive/16](archive/16-first-runs-on-v3.md)
(08-19 — first runs of the v3-era studies) and [archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md)
(08-22 → 08-27 — vocabulary, `concurrency_correlation`, the v4 refresh, `bear_deploy`).

**State of play (2026-08-31).** The live thread is the **hedge programme** on
era v4 (the 140-date backfilled book; exports of 2026-08-27). Where it stands:

- **`hedge_exposure` — run, graded, RATIFIED, and it ships nothing.** The
  registration's population clause was self-contradictory (ERRATUM 1); the
  operator ratified `all` — the literal `load_book(include_bs=False)` call,
  996 rows / 145 dates, real 485 + tweak 511 — because a `strike_expiry_tweak`
  row is a real Barchart price for a nearby strike and the operator does not
  follow a proposed leg exactly. Two verdicts over two objects: the mechanism
  question is **UNDERPOWERED** (all nine cells fail G-POWER; no direction is
  quoted from any), and ARM M is **MEASUREMENT-ONLY** — the close-bucketed
  curve **understates this book's max drawdown by 40.2%** (MTM −$32,571 vs
  close −$23,239). That understatement is now recorded in
  `deployment-evidence.md` against `bear_deploy` D3, `calendar_hedge` H3 and
  `hedge_timing` H4 as a limitation of their measurement basis — all three
  verdicts stand. ARM P is inert as registered (ERRATUM 2) and has NOT been
  redefined. The queued max-drawdown question stays **OPEN**. All of it is in
  the entries below. `hedge-exposure-errata.md` recorded ERRATUM 1/2 and the
  RATIFICATION; on 2026-09-02 that content was folded into the pre-
  registration's own §Population and basis (`research/pre-registrations/
  f4_deployment/hedge_exposure.md`) and the errata file was deleted —
  `study_review` and `hedge_exposure.py` now cite the registration directly,
  and `tests/test_studies_hedge_exposure.py` pins the two from drifting apart.
- **`hedge_timing` — GAP-UP came back CONTRARY** (the hedge did worse than the
  same day's ladder-eligible long, both money arms); the §4 prohibition was
  drafted and HELD, chop and the broad decline are NULL, the strict 4–5-day
  streak is UNTESTABLE on 2 book dates.
- **The bigger book DILUTES concentration** (median any-cluster concentration
  0.301 on `real` → 0.209 on `all`; τ=0.30 triggers 256 → 91 sessions). That,
  not a shortage of dates, is why every hedge cell is power-stopped — and it
  falsified the registration's power prediction in a direction it did not
  anticipate. A third reading (real + tweak prices, but an admission or
  concurrency model over which plays are held at once) would need its own
  registration; it is neither of the two the registration names.

**Open queue** (detail in [`next-steps.md`](next-steps.md)): `concurrency_correlation`
is pre-registered and its module is still unwritten; the max-drawdown hedge
question has its answer on the ADMITTED book — `hedge_concentration` (built
and run 2026-08-31 night) returned **PRECONDITION-NULL, powered**: how
concentrated the operator's book is says nothing about its next 20 sessions of
drawdown, so a concentration-gated hedge has no trigger to stand on; it awaits
`study_review` grading before §2.1 is closed in `deployment-evidence.md`; the
v4 composition bridge waits on data; rollback triggers are checked at gates,
never read from silence.

**Standing hazards carried forward** (each has its full entry in an archive):
the `exit_basis` export column is unlabelled and scrambled on **v3 and
earlier** and those exports are frozen (archive/15) — but it is CLEAN on v4
(re-measured 2026-09-02: 485/485 labelled and internally consistent), so the
rule is now era-scoped rather than absolute, and `BacktestProxy` carries it
only for rows written after the 2026-09-02 writer fix; studies are ERA-scoped and the bare export name is not a
population (archive/15, `lib/era.py`); ARM labels are study-local — cite
`emission_timing ARM P`, never a bare `ARM P` (archive/17, `arm-index.md`);
`study_review --dry-run` overwrites the review/digest artifacts (archive/17);
the `hedge_exposure` registration's plan-time observations describe the `real`
stratum, not the ratified book (`hedge-exposure-errata.md` §RATIFICATION).

---

## 2026-08-28 — hedge_timing (f4, NEW): the operator's hedge triggers tested; GAP-UP comes back CONTRARY, the 4–5-day streak is UNTESTABLE

Registered, built, run (v4 decisive + pre-declared v3 replication), two-analyst
graded and recorded same day (era v4 · sha 1fe4923; v3 run recorded beside it).
Question: the operator hedges (bear debit) on (a) chop, (b) SPY gap-ups,
(c) 4–5 straight SPY down days — do those triggers identify days the hedge
earns more than the same day's ladder-eligible long? Registration:
`research/pre-registrations/f4_deployment/hedge_timing.md` (one headline per
family, H3 within-date paired primary, total verdict grammar, floors ≥25
dates/≥60 rows, nothing ships from this correlated window under any outcome).

- **Census finding first (counts only, fixed at registration): the operator's
  actual streak trigger is NOT TESTABLE on this book.** A strict 4–5-session
  SPY down-run exists on 2 of the 145 v4 book dates (11 of the era's ~457
  trading days; the book samples 140). DECLINE-UNDERPOWERED was fixed in
  advance and no direction was quoted. Reaching a 25-date floor at current
  emission density needs ~3,000 more trading days — the 4–5-day habit stays
  discretionary because it cannot be evidenced here, not because it passed.
- **GAP (open ≥ prior close ×1.003): CONTRARY on BOTH verdicted money arms.**
  H3 (primary, within-date paired): on gap-up days bear-minus-long dR is
  −0.670 vs −0.262 on non-trigger days — headline difference **−0.408, CI95
  [−0.749, −0.057]**, every LOO fold negative, both years, all three window
  cuts (ex-BOTH ≡ ex_2025_mar_apr on v4, stated on the page). H4: gating the
  sleeve on gap-ups costs **−$5,893** (f=0.5, LOO min −$6,759, both years
  negative) while max DD and worst date are IDENTICAL to never hedging — the
  gap-up hedges never landed on a drawdown date. Caveat carried from H2: the
  ladder long is (n.s.) BETTER on gap-up days (+0.155), so part of the spread
  is "longs pay more on gap-ups" — for the hedge-or-long decision that is
  exactly the quantity that matters, but it is not a pure hedge-decay claim.
- **CHOP (eff_ratio bottom tercile): NULL** on H1/H3; H4 UNSTABLE (sign +$800
  but year signs split). The "I hedge when it's choppy" habit finds no support
  and no contradiction — chop days are indistinguishable.
- **DECLINE-BROAD (≥3 of last 5 down, the powered substitute): NULL on all
  three arms.** Per the pre-registered asymmetric reading rule this NULL IS
  informative about the strict rule: if even the broad construct cannot
  separate hedge value, the 4–5-day version is not worth waiting ~3,000
  trading days for. (A positive here could never have endorsed the strict
  rule; the null direction is the one allowed to speak.)
- **TIMING-CANDIDATE survivors: 0 of 9 headline tests** (~0.45 expected by
  chance). h2_mirrors fired only on H1-GAP (re-read NULL).
- **v3 replication (partially correlated, disclosed):** H3-GAP UNDERPOWERED
  by ONE date (24 paired vs floor 25 — no direction quoted); H4-GAP NULL by
  the grammar but directionally consistent (gating −$6,293, max DD worse,
  negative in all three years INCLUDING 2026 −$2,640 — the year v4 cannot
  see). Nothing contradicts the v4 CONTRARY; nothing independently confirms
  it either.
- **Registered outcome applied: the §4 prohibition is DRAFTED AND HELD** (the
  operator pre-chose draft-and-hold over auto-apply). Draft, verbatim, for
  the operator to accept or reject:
  > **Do not open the hedge on a gap-up day** (SPY open ≥ prior close
  > ×1.003). On those days the same-day A/B long out-earned the bear by
  > 0.67 R — an excess of +0.41 R (CI [+0.06, +0.75]) over ordinary days —
  > and gating the sleeve on them cost −$5.9k with zero drawdown benefit.
  > If the sleeve is to be fed that week, feed it on a non-gap day.
  NOT applied to docs/deployment-rules.md; recorded in
  `research/deployment-evidence.md` §Hedge-timing triggers with its forward
  trigger (re-run at ≥25 strict-streak book dates, or ≥25 post-2025-11-04
  dates).
- Review pass: first grading surfaced that H4's criterion vector was not
  printed (UNSTABLE vs CONTRARY unauditable from the page) — printer now
  emits the mapped vector under every H4 verdict (`criteria unharmed= sign=
  loo_all_same_sign= years_ok= cuts_ok=`), tokens unchanged, both eras re-run
  and re-recorded at the fixed sha; second grading clean (one analyst tally
  mis-transcription, resolved by recount, MET held).
- **QUEUED (operator, 2026-08-28): the hedge programme's next question is
  MAX DRAWDOWN, not timing.** H4 showed no tested sleeve policy reduces it:
  v4 baseline max DD −$10,968 is IDENTICAL under every gated policy (the
  hedges never land on the drawdown dates), and on the v3 book always-on
  hedging actively WORSENS it (−$7,609 → −$11,366 at f=0.5, −$18,278 at
  f=1.0). A future study should ask what mechanism (structure, sizing,
  trigger, or something outside this sleeve) actually cuts max drawdown —
  deliberately NOT designed now. Known wall to design around: the 2026-08-13
  finding that ~9 worst-decile dates cannot power a worst-decile criterion
  on this book (calendar_hedge died on exactly that), so the study needs
  either a drawdown measure that is not worst-decile-shaped or genuinely
  new dates.
- **Operator context on that queue (added 2026-08-28, same day):** the
  operator's actual hedge practice is EXPOSURE-conditional, not
  calendar-timed — "I hedge when I hold a lot of correlated positions
  (semis → SMH, tech → QQQ), I see a specific risk, AND the analysis says
  people are hedging. Not hedging for the sake of hedging." `hedge_timing`
  tested none of that: its triggers were pure market-state (chop / gap /
  streak) with no book-concentration or hedge-flow-signal conditioning, and
  its instrument was the book's own bear row, not a sector proxy. So the
  operator's practice is UNTESTED — neither validated nor contradicted —
  and the drafted GAP prohibition speaks only to the gap-as-reason, not to
  hedging concentrated exposure on a day that happens to gap. The queued
  mechanism study should therefore frame the trigger as book state (per-
  sector delta concentration from the s03 risk tables) × analysis
  hedge-flow signal, instrument as the sector proxy, counterfactual as the
  UNHEDGED concentrated book (not "open a long instead"), and outcome as
  drawdown. Data feasibility (does the study book carry a portfolio whose
  concentration can be replayed, and are hedge-flow signal tags recoverable
  per date?) is a design-time question, deliberately not answered now.
- Same day, production tier (not a study): §5's "75% of DTE" now prints as an
  absolute exit-by date — per open position in the journal §4 (⚠ OVERDUE past
  the book date) and as a projected range on the deploy card
  (exit_by_earliest/exit_by_latest, hash-excluded). deployment-rules §5 gained
  the date formulation; the fraction is read from config/backtest.yml at
  render time so card, report and table cannot drift.

---

## 2026-08-29 — feasibility pass for the queued max-drawdown hedge study (DESIGN NOTES, NOT a pre-registration)

**Nothing here is a commitment.** No arm, gate, bar or verdict below is binding;
the pre-registration that follows is where any of it becomes immutable. This
entry exists so the design-time facts are on the record before the design is
frozen, and so a later reader can see which questions were answered from disk
rather than assumed. It answers the feasibility question the 2026-08-28 scope
note deliberately left open: *does the study book carry a portfolio whose
concentration can be replayed, and are hedge-flow signal tags recoverable per
date?*

### What is on disk (v4 `current` era, exports of 2026-08-27 20:34)

| Question | Answer from disk |
|---|---|
| Is there a replayable PORTFOLIO, not just a row list? | **Yes.** `analysis - BacktestResults.csv` = 485 rows / 140 dates / 2024-01-10 → 2025-11-04. Reconstructing open intervals as `[signal_date, signal_date + days_held]` gives a median of **20 concurrently open positions**, p90 35, max 48. Concentration is a real quantity on this book, not a degenerate one. |
| Is signed book direction derivable? | **Yes, unambiguously, from `delta` alone** — it is already the net signed per-contract position delta (bull_call +0.212, bear_put −0.238, long_put −0.809 as group means). `structure` text does not need parsing. Exposure = `delta × contracts × 100 × entry_underlying`. |
| Is the book long-only? | **Yes, still** — consistent with `portfolio_delta`'s finding of 0 net-short sessions. The hedge is therefore the only downward dial, exactly as that study concluded. |
| Is the book dense enough for an equity PATH? | **Yes, and this has changed since 2026-08-19.** That day `account_sim` found ZERO dense episodes on a 34-date v4 book and its PRIMARY population was empty. The 140-date book now yields **5 dense episodes (49, 23, 18, 12, 11 dates) covering 113 of 140 dates**, median gap 3 sessions, p90 3, max 21. The book still samples only **30.4%** of the 457 trading sessions in its span. An `account_sim`-hosted study will run; it was not runnable ten days ago. |
| Is a sector-proxy hedge PRICEABLE, or would it be Black-Scholes? | **Real quotes exist.** `backtests/option_history_cache/` carries **SPY 1,504 / IWM 1,558 / QQQ 1,405 / SMH 868** contract files, plus XLE 650 and XLF 459. Underlying bars exist for SPY, QQQ, SMH, IWM, XLF, XLE. **No XLK, SOXX, XBI, OIH, DIA or VXX** in either cache. So the operator's own two proxies (semis → SMH, tech → QQQ) are both priceable from real history, which `calendar_hedge` was not able to say of its legs. Per-date, per-strike fill coverage is NOT established by file counts and remains a gate the study must measure, not assume. |
| Are hedge-flow signal tags recoverable per date? | **Only as prose, and the naive reading is useless.** There is no hedge column: `AnalysisClaude` is `date,ticker,regime,signal,play,horizon,trigger,invalidation,…`. A date-level "the analysis mentions hedging" match fires on **157 of 158 dates** — non-discriminating, and it would have been an easy trap to fall into. Two non-degenerate readings exist: (a) a **numeric** `hedge-pressure NN/100` embedded in the `regime` prose, which parses on **103 of 158 dates (65%)**, is **constant within a date** (0 dates carry two values), and spans 15–83 with median 35; (b) **row-level vocabulary density** — the share of a date's ticker rows whose `signal`/`play` carry hedge language (`hedge` 17.9%/27.7% of rows, `protect` 25.1%/25.2%, `insurance` 6.1%/16.6%, `collar` 3.3%/17.2%). Either needs its extraction rule fixed in the pre-registration before it is computed. |

### Two design-time findings that were not sought and matter more than the above

**1. The existing drawdown measure structurally cannot see a hedge.**
`account_sim.equity_curve()` buckets P&L by `exit_sess` — it books a position's
entire result on the day it closes, and its own `print_equity()` says so:
*"Open positions are not marked to market, so this understates intra-position
drawdown."* Every hedge verdict in the programme to date — `bear_deploy` D3,
`calendar_hedge` H3, `hedge_timing` H4, including the −$10,968 figure the
operator queued this study against — is measured on that realized-on-close
curve. A hedge's entire function is to cushion the mark-to-market path between
entry and exit, which is the one thing this curve does not contain. The
observation that "the hedges never land on the drawdown dates" may therefore be
partly a statement about the MEASURE rather than about the hedges: on a
close-bucketed curve, a drawdown "date" is an exit-clustering artefact.
**This is testable and the data is present** — `daily_pnl_csv` is populated on
**485 of 485** rows, so a genuine mark-to-market book equity curve can be built
for the entire book. Whether the primary outcome should move to that curve is
the first question put to the operator, not decided here.

**2. The v4 analysis prose carries irreducible model-recall lookahead risk.**
**All 1,893 `AnalysisClaude` rows have `created_datetime` in 2026-08** — every
row, including those for signal dates in January 2024. The v4 book being a
backfill is already on the record, but the consequence recorded so far has been
about DENSITY and power (the 2026-08-19 empty-PRIMARY entry). The consequence
for a study keyed to the model's WORDS is different in kind: the `hedge-pressure
35/100` written against 2024-03-20 was produced in 2026-08 by a model whose
training cutoff overlaps that date, so it may be recall rather than a read of
that day's tape. This is the same hazard `s06_recommend.judge()` and
`live_select.py` already document for their judge layers, arriving here through
the analysis prose instead. It cannot be engineered away by bounding inputs —
only segregated and reported. The practical consequence for design: any
prose-derived trigger needs a **mechanical, prose-free counterpart arm**
(book concentration alone, computed only from positions) so the study can state
how much of any effect survives without the model's words. Note this does not
bear on the flow inputs, which were point-in-time.

### Candidate hypotheses (UNCOMMITTED — wording is not final)

Framed per the 2026-08-28 scope note: trigger = book state × hedge-flow signal,
instrument = sector proxy, counterfactual = the unhedged concentrated book,
outcome = drawdown. Designed around the ~9-date worst-decile power wall by
using **path-shaped** drawdown statistics computed over every session of the
book (max DD, and a drawdown measure with a denominator — e.g. an Ulcer-style
index or time-under-water) rather than a worst-decile tail cell.

- **H-M (measurement, prerequisite).** Does the book's drawdown profile differ
  materially on a mark-to-market curve versus the realized-on-close curve every
  prior hedge verdict used? If it does not, the measurement concern is closed
  and the programme's null results stand as read.
- **H-C (concentration predicts).** Does high per-sector signed delta
  concentration in the OPEN book predict worse subsequent book drawdown? This
  is the precondition: if concentration carries no information, no
  concentration-gated hedge can work, and the study should stop here and say so.
- **H-S (the prose adds).** Does the analysis hedge-flow signal add
  discrimination over concentration alone — and does any effect survive the
  prose-free arm required by finding 2 above?
- **H-X (the mechanism).** Does a sector-proxy hedge, sized at fraction f and
  gated on H-C (and H-C × H-S), reduce book drawdown versus the SAME unhedged
  concentrated book — not versus a book that opened a long instead?
- **H-I (the instrument matters).** Is a sector proxy different from the book's
  own bear row, which `bear_deploy` D3 and `hedge_timing` H4 have both found
  cannot cut max drawdown?

Open design questions put to the operator before any of this is frozen:
the primary drawdown curve (mark-to-market vs realized-on-close), the
hedge-flow extraction rule, the hedge instrument's form, and the ship posture.
The sector map (which ticker belongs to SMH vs QQQ vs the residual) must also
be fixed in the pre-registration before it is computed, since no sector column
exists on any export.

---

## 2026-08-31 — hedge_exposure: built, run, and deliberately verdict-less

`scripts/backtest_study/f4_deployment/hedge_exposure.py` plus four new libs
(`lib/sectors.py`, `lib/mtm_curve.py`, `lib/hedge_instrument.py`,
`lib/concentration.py`) now implement the pre-registration committed in
`665956d`. It runs clean (exit 0, 30s) on era v4. **It emits no study-level
verdict, by design.** Two errata, recorded in `research/hedge-exposure-errata.md`
rather than by editing the immutable commitment, are why.

**ERRATUM 1 — the population clause contradicts itself.** The registration
commits BOTH `load_book(include_bs=False)` AND "485 rows / 140 signal dates".
The literal call returns **996 records / 145 dates** (real 485 + tweak 511). The
two readings do not merely differ in size, they decide the study: under `real`,
3 of 9 cells clear G-POWER; under the literal call, **0 of 9** do. Choosing one
after seeing that is a choice dressed as a finding, so the study runs BOTH,
prints both, and concludes from neither. The operator ratifies a reading or the
study stays open.

**ERRATUM 2 — ARM P is degenerate as worded.** "ARM C restricted to exactly the
sessions ARM CS would hedge on, minus the prose condition" is ARM CS's own
session set; the arms carry byte-identical hedges and differ only in what is
claimed to justify them (the report measures this and prints YES). ARM P is the
study's ONLY control on the irreducible prose lookahead — every AnalysisClaude
row was written in 2026-08, including rows for 2024 sessions — so that control
**does not exist**, and the registration's binding prose rule ("no verdict may
rest on ARM CS alone") is unreachable by construction. Declared INERT AS
REGISTERED and deliberately NOT redefined; a corrected control (ARM C on
concentration-matched sessions carrying NO hedge-pressure signal) needs its own
registration.

### The gate that would have lied

**G-MTM was tautological on first build** and passed 485/485 at $0.0000 — both
sides of the reconciliation came from one `replay_sized()` call, so it compared
the replay to itself. Rebuilt to take `days_held` from the row and dollars from
the STORED `realized_pnl_abs`. Against the stored outcome the replay differs on
**12 `days_held` and 13 `exit_reason`**, and $33,696 stored vs $34,644 replayed
(gap +$947 on a $33.7k book, sum of per-row |difference| $8,727). That
divergence is now printed. A gate that cannot fail is not a gate — worth
checking the others in this pattern.

### H-M answered, and it does not say what the design memo said

The unhedged book on both curves (551-session weekday grid):

| curve | total | maxDD | ulcer | TUW | worst session |
|---|---|---|---|---|---|
| mark-to-market | $33,696 | **−$21,890** | 16.61% | 92.9% | −$9,730 |
| realized-on-close | $33,696 | **−$22,592** | 16.14% | 90.9% | −$8,136 |

The curves differ materially — but **on max drawdown the close-bucketed curve
reports the LARGER number**, not the smaller one. The design-time argument that
"the close-bucketed measure is structurally blind to hedging" is not carried by
this evidence and should not be repeated. What the MTM curve actually adds is
path and tail: it is worse on Ulcer (+0.47pt), worse on time-under-water
(+2.0pt), and its worst single session is 20% deeper. So the prior hedge
verdicts (`bear_deploy` D3, `calendar_hedge` H3, `hedge_timing` H4) are not
invalidated by the measurement choice on the metric they were read on.

### What the book is, measured

504 open sessions, 2024-01-10 … 2026-01-16. Concentration by signed delta per
cluster: median 0.301, p75 0.398, p90 0.572 — so the τ grid {0.30, 0.35, 0.40}
straddles the median as intended. **Four of eleven clusters have no tradeable
hedge** (CRYPTO/IBIT, ENERGY/XLE, FINL/XLF, INTL/EEM — 10.2% of exposure);
per `concurrency_correlation`'s commitment they keep their identity, are carried
at f=0, and count against the fill gate rather than being folded into BROAD.
XLE is withheld by the repo's own `underlying.rescaled_tickers()` convention
(0.50 median relative difference over 267 overlaps), not by a new bug.

Two structural facts that limit what this book can ever answer:

- **The book barely does the practice being tested.** 62.7% of exposure is
  DIRECT (a put on an ETF the book already holds), not constituent-to-proxy.
  The constituent stratum is UNDERPOWERED at every τ — 8 / 3 / 0 sessions —
  exactly as the registration predicted at plan time. The asymmetric reading
  rule binds: a DIRECT result may never be cited for the constituent practice.
- **The f grid is largely unreachable on a $500 risk budget.** A proxy put's
  debit is typically several hundred dollars, so `risk_contracts()` returns 1
  and `int(0.25 × 1) = int(0.50 × 1) = 0`. Those cells carry no hedge at all
  (162 skips at τ 0.30 f 0.25) and are reported as such rather than floored
  to one contract.

`hedge-pressure NN/100` parses on 103/158 dates (65%), 0 multivalued dates,
span 15–83, median 35, ≥50 on only 20 — which is why every ARM CS cell is
power-stopped at 4–7 episodes.

### The result, such as it is

Population `real`: 3 powered cells, **all NULL**, 6 UNDERPOWERED. Population
`all`: 9 UNDERPOWERED. No cell clears a single clause of the 7-clause bar; the
largest ARM C improvement is +$1,012 of max drawdown at τ 0.30 f 1.00, bought
with $16,949 of debit and −$1,952 of total return, and it fails clause 2 (Ulcer
CI includes zero) and clause 3 (below ARM N's p95) outright. ARM B — the book's
own bear row instead of a put — is negative at every f=1.00 cell, consistent
with D3 and H4 on a curve those verdicts did not use.

Two bar corrections landed before any outcome was read: a CONTRARY previously
needed **zero** clauses while a positive needed seven (now a mirrored 6-clause
set, and a cell-level CONTRARY no longer escalates); and the bootstrap was a
month-SHUFFLE that concatenated resampled months in drawn order and then
computed PATH-DEPENDENT statistics on the reordered series, making month order
part of the statistic. Now a chronological moving-block bootstrap (22-session
blocks). The withdrawn estimator is still printed per cell: **clause 2's outcome
is unchanged in all 3 powered cells**, so the fix did not manufacture the null.

**Not independently audited.** Both verify agents in the fix workflow died on
the account's weekly rate limit, so the seven fixes are self-reported by the
agent that made them plus a hand spot-check. Full suite green (2513 passed),
flake8 clean. No A/B replication grading has been run.

Open: ratify a population reading, then `python3 -m scripts.study_review
hedge_exposure --skip-run`. Six further defects are recorded but NOT fixed in
`research/hedge-exposure-errata.md` — ARM CS's one-session lookahead, the
calendar-vs-trading reading of `days_held`, G-FILL's cache-conditioned
denominator, ARM B's stop mismatch, baseline non-comparability, and that ARM M
is weaker than the design memo argued.

### 2026-08-31, same day — independent audit, F8–F16, and a correction to H-M

The two verify lenses that died on a rate limit during the F1–F7 pass have now
run. Both confirm F1–F7 landed, the sector map is verbatim to the registration
ticker by ticker, lookahead discipline is clean (trigger, sizing, stratification
and fill read entry-dated fields only), no study-level verdict word is emitted,
and the four unhedgeable clusters are handled as both registrations commit.

They also found nine defects, all of one family: **operationalizations the
registration left undefined, which the report did not disclose, and which fed
the bar.** Fix plan F8–F16 is in `research/hedge-exposure-errata.md`; all are
now applied. Two mattered:

- **F8 — the hedge was fixed at the episode's FIRST session.** The registration
  says hedge on ANY session where concentration ≥ τ, on THAT cluster's proxy.
  At τ=0.30 the misread held a put on the wrong cluster for 37 session-days
  across 8 episodes, and dropped 2 episodes whole because only their first
  session was unhedgeable. Now re-picked per session, with an unhedgeable
  SESSION carried at f=0 in the denominator.
- **F9 — "results are always stratified" was printed, not computed.** Every
  clause ran on the pooled trigger; stratification existed only as a count
  table. The one powered cell is 199/256 DIRECT, and its NULL was a pooled
  number no reader could attach to a stratum. Now every metric, CI, ARM N band
  and clause runs per stratum, each power-gated on its own episode count.

**F8 moved every figure in the `real` population and changed nothing that
matters.** ARM C τ=0.30 f=1.00 dMaxDD +$1,012 → **+$318**; τ=0.40 f=1.00 −$447
→ −$17; ARM RF's headline +$3,202 → +$2,620. No cell word changed sign — still
NULL (3, pooled and DIRECT) or UNDERPOWERED under both populations, CONSTITUENT
underpowered in all 9 cells. Clause 6, now folding over trigger DATES rather
than placed legs, reports 0/256 where it used to report 2/29.

#### Correction: H-M's answer depends on which population you ratify

The 2026-08-31 entry above says the mark-to-market curve is *slightly better* on
max drawdown and that the design memo's "close-bucketing is blind to hedging"
claim is not carried. **That is true of the `real` population only.** Both
populations, same book, same code:

| population | MTM maxDD | close maxDD | gap |
|---|---|---|---|
| `real` (485 rows) | −$21,890 | −$22,592 | MTM **better** by $702 (3.1%) |
| `all` (996 rows) | −$32,571 | −$23,239 | MTM **worse** by $9,332 (40.2%) |

Under `all`, the close-bucketed curve understates max drawdown by 40% — which
is exactly the design memo's claim. Under `real` it overstates it slightly. So
the memo's argument is neither carried nor refuted: **the population clause
ERRATUM 1 flagged decides it**, alongside deciding what is powered. That is now
two independent things riding on a ratification the registration cannot supply,
and it is the strongest argument yet for settling the reading before anything
else is built on this study.

The earlier entry's sentence — "the prior hedge verdicts are not invalidated by
the measurement choice on the metric they were read on" — should be read as
holding under `real` and being **untested under `all`**.

Also fixed: G-MTM could still degrade to comparing a replay against itself when
a record carried no stored column, and the whole G-MTM test block was running on
that path; it now counts degraded rows and withholds the "two independent
columns" claim unless the count is zero (it is). G-CENSUS's header claimed to
print before any outcome column was read while three sections printed outcome
dollars above it. Every discretionary choice — 20 of them — is now in one
consolidated NOT PRE-REGISTERED block naming the clause it feeds.

Suite 2543 passed. Still no study-level verdict, still nothing shipped.

### 2026-08-31 — RATIFIED: population `all`, and the verdict that follows

**Operator ratification (recorded in `research/hedge-exposure-errata.md`):
the population is `all` — the literal `load_book(include_bs=False)` call,
996 rows / 145 signal dates (real 485 + tweak 511). `real` is retained as a
reported stratum, not a co-primary.**

The operator's argument, which is better than the one this log was leaning
toward: a `tweak` row is a `strike_expiry_tweak` substitution carrying a REAL
Barchart price for a nearby strike/expiry (model-priced `bs` rows stay
excluded). And the substitution is not merely harmless, it is REPRESENTATIVE —
the operator does not follow a proposed leg's strike and expiry precisely at
execution, so a book admitting that substitution is the closer model of their
real trading. Excluding 511 real-priced rows would need a positive reason and
there is none. The counter-argument (the registration's plan-time disclosures
reproduce on `real` alone) survives as a stated LIMITATION rather than a
decision rule: those disclosures describe the `real` stratum, not the ratified
book, and must not be read as disclosures about it.

**VERDICT — the mechanism question: UNDERPOWERED.** Every cell of the τ × f
grid fails G-POWER on the ratified population, under POOLED, DIRECT and
CONSTITUENT alike. No direction is quoted from any of them. The queued
max-drawdown question stays OPEN.

**VERDICT — ARM M: MEASUREMENT-ONLY, and it is the sharper result.** On the
ratified book the same unhedged book measures maxDD **−$32,571 mark-to-market
against −$23,239 close-bucketed** — the close-bucketed curve **understates max
drawdown by 40.2%**. The registration's own wording for MEASUREMENT-ONLY is
that it "would mean the programme's prior nulls were measured on a blind
instrument without a hedge mechanism yet being found." That is what ARM M now
shows. `bear_deploy` D3, `calendar_hedge` H3 and `hedge_timing` H4 all STAND,
but each was read on that curve, so their measurement basis is a known
limitation of theirs.

Both words are emitted because the registration defines them over different
objects and orders neither; ARM M is not power-gated, so it is powered exactly
when the cells are not.

#### The finding that most deserves a second look: the bigger book DILUTES

| | `real` (485) | `all` (996, ratified) |
|---|---|---|
| any-cluster concentration, median | 0.301 | **0.209** |
| p75 / p90 | 0.398 / 0.572 | 0.268 / 0.400 |
| τ=0.30 triggers | 256 sessions / 32 episodes | **91 / 18** |

Doubling the book HALVES the triggers. Adding 511 positions spreads exposure
across more clusters, so no single cluster reaches τ as often — that, not a
shortage of dates, is why every cell is power-stopped. It also falsifies the
registration's disclosed power prediction, which expected only the CONSTITUENT
stratum to be power-stopped "so a later underpowered result reads as predicted,
not as a disappointment." POOLED and DIRECT are power-stopped too.

**This does not reopen the ratification** — the pricing argument is sound and
untouched. But admitting `tweak` rows does two separable things: it makes the
PRICES representative of real execution, and it makes the BOOK bigger and more
diversified. Only the first was argued. The second is right only if every
proposed play would in fact have been held concurrently; if a subset is taken in
practice, the ratified book understates concentration and this study measures a
more diversified book than the operator runs. A third reading — tweak PRICES
with an admission/concurrency model over what is held at once — is neither
reading the registration names and would need its own registration.

Two further reading notes, both in the errata: MEASUREMENT-ONLY's plain reading
over-claims here, because "no hedge cell clears the bar" is true VACUOUSLY (no
cell was evaluated at all, rather than nine being judged and failing); and the
registration's Ship criteria has no branch for UNDERPOWERED + MEASUREMENT-ONLY,
so whether the ARM M finding is recorded in `research/deployment-evidence.md`
against D3/H3/H4 is an operator decision it does not make.

Suite 2550. Nothing ships; no rule moves; the §4 sleeve is untouched.

#### A/B replication grading (Mode 1) — clean, with one graded gate NOT MET

`python3 -m scripts.study_review hedge_exposure --skip-run`. Two isolated
analyst sessions plus a validator. **A and B reached identical verdicts on every
criterion both evaluated** — a high-agreement pair with one isolated slip.

| | graded |
|---|---|
| G-ERA · G-FILL · G-BLIND · G-MTM | **MET** |
| G-POWER | **NOT MET** (largest cell 18 episodes < 25) |
| **G-CENSUS** | **NOT MET** |
| bar clauses 1–7 | **NOT EVALUABLE** (0 powered cells on the ratified population) |
| asymmetric DIRECT/CONSTITUENT rule | **MET** — full per-stratum clause sets present |
| binding prose rule | NOT EVALUABLE (ARM P byte-identical to ARM CS; all ARM CS cells underpowered) |
| anti-tuning: 9-cell grid at α=0.05/9 · no second grid · no annualised/Sharpe/time-to-recover · cache state in header | **MET** |

**G-CENSUS grades NOT MET, and that is F13 working as intended.** The
registration words the gate as "the census prints before any outcome column is
read". F13 replaced that false claim in the report with the true one (the
census's INPUTS are entry-dated; G-MTM and ARM M print above it). Both analysts
then graded the gate NOT MET *against the registration's wording* — which is the
correct grade, and only reachable because the report stopped asserting something
untrue. A gate the study cannot honestly claim is better recorded as not met.

The one violation: analyst A's prose says the powered `real`-stratum cells fail
"(all clauses FAIL)". Clause 1 actually **PASSED** in 3 of those 6 cells (POOLED
τ0.30 f1.00 `dMaxDD +$318`; DIRECT τ0.30 f0.50 `+$16` and f1.00 `+$36`). The
cell-level NULLs A cites are right, the stated reason is not. B did not make the
error and its coverage was broader. Nothing verdict-bearing rests on it — the
`real` stratum carries no verdict.

Also confirmed by the validator: **ARM R shows `dMaxDD +0` in all nine ratified
cells** — the always-fillable delta-matched reference moves the drawdown not at
all on this book.

**Infrastructure gap worth fixing:** `study_review` inlines the pre-registration
but NOT `research/hedge-exposure-errata.md`, so neither analyst nor the
validator could check the ratification against its authority — all three
disclosed the gap themselves and graded the report's own quoted RATIFICATION
text instead. For a study whose population, two errata and verdict all rest on a
file the graders cannot see, that is a real hole in the protocol.

## 2026-08-31 (fix) — `study_review` now inlines a study's ERRATA file as authority

The gap logged at the end of the entry above is closed. `study_review` inlined
the pre-registration and the report; it did not inline
`research/hedge-exposure-errata.md`, so both analysts and the validator graded a
ratification against the report's own quoted account of it. For a study whose
population, both errata and final verdict all rest on that file, the graders
were working blind to the document that decides them.

**What changed.** `scripts/study_review/` discovers `research/<study>-errata.md`
by convention (`_` in the study name also tried as `-`, so `hedge_exposure` →
`hedge-exposure-errata.md`) and inlines it for the analysts AND the validator,
positioned directly after the pre-registration and before the report — the two
authority documents in hand before the artifact being graded. The block is
framed explicitly: the errata is authority, not commentary; any ratification,
population choice or closed erratum the report claims is graded against the
errata text rather than the report's account of it; and it never RELAXES a
commitment — every gate, bar, arm and verdict it does not explicitly resolve is
still graded against the registration as written. `--errata PATH` overrides
discovery, `--no-errata` reproduces a pre-errata grading run. A missing errata
is the normal case (stderr warning, run continues); an EMPTY errata file is
FATAL, because a run that appears to have graded against one and did not is
worse than one that plainly had none.

**The manual path had the same hole and is fixed too.**
`research/replication-protocol.md`'s rule 2 now names the errata as part of the
authority, and the worked-example prompts for analyst A, analyst B and the
validator all name `<errata path>`. The hand-spawned `research-analyst` agents
do have file access — the failure was that nothing told them the file existed.

Not re-graded: `hedge_exposure`'s existing review artifacts stand as they are.
The verdict they support (UNDERPOWERED + MEASUREMENT-ONLY on the ratified `all`
population) does not change, and a re-grade with the errata visible would cost
three model calls to confirm a conclusion the errata itself dictates. The next
`hedge_exposure` grading gets the file automatically.

## 2026-08-31 (recorded) — ARM M's 40.2% understatement written against D3 / H3 / H4

The operator decision the registration could not make (errata post-ratification
note 4) is made: **record it.** `research/deployment-evidence.md` gains
§"The curve D3 was read on understates drawdown (2026-08-31, `hedge_exposure`
ARM M)" directly after D3, plus a bullet in D3's "Remaining limits — quote these
with the rule" list and a measurement-basis note in the hedge-timing section.

**What is recorded.** The same unhedged book on both curves: on the ratified
`all` book, MTM maxDD −$32,571 against close-bucketed −$23,239 — the
close-bucketed curve understates by $9,332 (40.2%); on the `real` stratum the
gap runs the other way and is small (+$702, 3.1%). All three rules are judged on
a series of daily REALIZED dollars bucketed to each position's close — D3 in
`_sweep`'s `daily`, `calendar_hedge` H3 as "D3 verbatim", `hedge_timing` ARM H4
by D3's criterion verbatim — so all three inherit the basis ARM M found wanting.

**What is deliberately NOT recorded.** No verdict moves and no figure of theirs
is restated. ARM M measured `hedge_exposure`'s own 996-row concentrated book on
its own session axis, not D3's bear-sleeve book or H4's deployed-ladder dollars,
so **40.2% is not a correction factor to apply to them** — what transfers is the
basis, not the number. The write-up says so explicitly, because the tempting
misreading is to subtract 40% from D3's $571 improvement and call the rule dead.

Two label traps are called out in place, since this section is where a reader
meets all of them at once: `hedge_timing`'s ARM H3 (paired R, no dollars) is not
`calendar_hedge`'s H3 (sizing, D3 verbatim), and `calendar_hedge` H3 has never
been evaluated at all (v4: H0 FILL NOT MET, H2 NOT EVALUABLE) — the
qualification there is prospective.

`catalog.py`'s `attention` flag for `hedge_exposure` is updated rather than
cleared: this item is done, and what remains for the operator is errata note 3 —
admitting `tweak` rows made the prices representative AND the book more
diversified, and only the first was argued. Suite 2560.

## 2026-08-31 (late) — the dilution question answered from disk; `hedge_concentration` REGISTERED (module unwritten)

`next-steps.md` §2.1 asked for an operator answer to the dilution finding
(errata post-ratification note 3): does the operator hold every proposed play
concurrently, or a subset? The answer was on disk and did not need asking. The
deploy card admits at most 3 positions/day (`config/account-sim.yml`
`max_positions_per_day: 3`); on the 2026-08-27 exports `account_sim` takes
**221 of 458** ladder-eligible rows from the ratified population; and
`hedge_exposure.book_positions()` held **all 996** — its own report says the
figure "is not `account_sim`'s admitted-subset figure and the two are not
comparable". So the operator holds a subset, and `hedge_exposure` measured a
book about twice as diversified as the one being hedged. That closes the
operator question and makes the "third reading" — ratified PRICES on the
ADMITTED book — the right register.

**Verified first:** `account_sim`'s own loader is `load_book(include_bs=
args.include_bs)` with the flag defaulting False (`account_sim.py:2298-2301,
2384`) — byte-for-byte the call `hedge_exposure` ratified, identical at
runtime (996 rows both ways). The admitted book is the ratified population
thinned by admission and nothing else.

### Plan-time census of the admitted book (INPUT fields only)

Computed from positions, delta, contracts, entry underlying, signal date,
`days_held` for occupancy and the `regime` prose; no P&L, R, `daily_pnl_csv`,
drawdown or equity column was read. ARM H OFF, no `--live-select`.

| | admitted book (ratified pop.) | `hedge_exposure` `all` | `hedge_exposure` `real` |
|---|---|---|---|
| positions held | 221 / 110 dates | 996 / 145 | 485 / 140 |
| session universe | 498 | — | 504 |
| concurrently open, median / p90 / max | 15 / 21 / 25 | ~20 median | 20 / 35 / 48 |
| any-cluster concentration, median / p75 / p90 | **0.464 / 0.572 / 0.678** | 0.209 / 0.268 / 0.400 | 0.301 / 0.398 / 0.572 |
| top cluster = MEGATECH / SEMIS | 53.6% / 33.7% of sessions | — | — |
| top-cluster stratum CONSTITUENT | **93.4%** | — | 37.3% of exposure |
| gross / equity, median / p90 | 1.86× / 2.45× | — | — |

Trigger census, any-cluster (episodes = maximal consecutive runs,
`lib/concentration.py::episodes`): τ 0.30 → 477 sessions / 9 episodes;
0.35 → 438 / 12; 0.40 → 372 / **20**; 0.50 → 227 / 13. Episode lengths at
τ=0.30: 236, 123, 66, 21, 19, 8, 2, 1, 1.

**Three things this says, none of which was expected:**

1. **Thinning the book to what admission holds more than DOUBLES its typical
   concentration** (0.209 → 0.464). The dilution ran the other way from the
   every-row book, and further than the `real` stratum. The admitted book is
   the operator's described practice almost literally — MEGATECH or SEMIS on
   top 87% of sessions, 93% constituent — where `hedge_exposure`'s book was
   62.7% DIRECT.
2. **Concentration is a persistent STATE on this book, not an event.** At
   `hedge_exposure`'s τ levels the admitted book is "concentrated" 75–96% of
   the time, so a concentration-gated hedge there is nearly an always-on
   hedge. And because tightening τ splits long runs rather than creating new
   ones, the episode count peaks at 20 (τ=0.40) and FALLS beyond it — no τ
   reaches the ≥25-episode floor. **A τ×f hedge grid cannot be powered on the
   admitted book either**, for the opposite reason to the every-row book:
   there, too few triggers; here, one trigger that never ends.
3. **The prose is untestable here.** 71 of 110 admitted dates parse a
   `hedge-pressure`; 11 read ≥50; the prose-conditioned survivor set at
   τ=0.30 is 19 sessions / 17 episodes.

Also disclosed: Spearman(gross, concentration) = **+0.10** (n=498), so gross
and concentration are separable on this book and a gross-exposure control is
a real control; dense episodes of admitted signal dates = **3** (18, 12, 13
dates), the floor met exactly; and on the `real` stratum alone the admitted
book has **0** dense episodes — the ratified population is what makes any of
this powerable.

### What was registered, and why it is shaped this way

[`pre-registrations/f4_deployment/hedge_concentration.md`](pre-registrations/f4_deployment/hedge_concentration.md),
2026-08-31. Given (2), the hedge mechanism cannot be the load-bearing stage,
so the registration puts the PRECONDITION first — H-C from the 2026-08-29
feasibility pass, which `hedge_exposure` skipped: **does a session's
concentration PREDICT the admitted book's forward 20-session mark-to-market
drawdown?** (ARM K: tercile contrast + Spearman ρ, block-bootstrapped over
20-session blocks; ARM KN a circular-shift null preserving both series'
autocorrelation; ARM KG the gross-exposure control — clause 4 refuses a
"concentration" effect that vanishes within gross terciles.) It is powerable
on 498 sessions. Stage 2 — the τ×f proxy-put grid, τ ∈ {0.45, 0.55, 0.65}
set at the census's median/p75/p90 so the loosest trigger means "more
concentrated than usual", through `account_sim.admission()` in the ARM H
pattern — runs ONLY on PRECONDITION-FOUND and is disclosed at plan time as
expected UNDERPOWERED. No prose arm is registered (reason (3); the corrected
ARM P control is deferred in `next-steps.md` §2.1, not dropped).

The clause `hedge_exposure` lacked is written this time: **every outcome has
a Ship-criteria branch that moves §2.1** — PRECONDITION-NULL or
GROSS-NOT-CONCENTRATION close the queued question in
`deployment-evidence.md`; FOUND + Stage 2 UNDERPOWERED/NOT EVALUABLE
re-labels it BLOCKED ON NEW DATES with the shortfall printed; FOUND +
MECHANISM-FOUND drafts-and-holds a §4 amendment. Nothing ships without
sign-off under any branch. Module not yet written; README index says
`registered`; `arm-index.md` carries the new letters (`ARM K` collides with
`concurrency_correlation`'s ceiling — qualify every citation).

## 2026-08-31 (night) — `hedge_concentration` BUILT and RUN: PRECONDITION-NULL, and it is a POWERED null

The module registered earlier today is written, tested and run once on the
2026-08-27 exports. Report: `backtests/study_output/hedge_concentration-latest.txt`
(era v4, sha 9834563, exit 0, 23 s); per-era record:
[`study-results/f4_deployment/hedge_concentration.md`](study-results/f4_deployment/hedge_concentration.md).
Not yet graded — `study_review hedge_concentration` is the next step, and the
Ship-criteria branch is NOT acted on until it is.

### What was built

- `scripts/backtest_study/f4_deployment/hedge_concentration.py` (1,852 lines,
  62 tests in `tests/test_studies_hedge_concentration.py`). Stage 2 — the τ×f
  proxy-put grid through `account_sim.admission()`, ARM N, ARM R, the seven
  clauses, DIRECT/CONSTITUENT/POOLED — is fully implemented and was correctly
  NOT entered.
- `lib/forward_drawdown.py` (new): the forward-drawdown series, rank-tercile
  contrast, Spearman, non-overlapping block bootstrap and circular-shift null;
  H and every seed are parameters. `lib/concentration.py` gained
  `occupancy_from_positions` / `contracts_by_position` so the trigger layer
  reads the SIM's `[entry_sess, exit_sess]` and sized contracts — extended by
  parameter, `session_concentration` untouched.
- `lib/mtm_curve.book_curves(target=)`: **the admitted book cannot be
  reconciled against the stored row.** `account_sim` re-sizes and re-exits what
  it admits — on this run 101 of 221 positions at a different contract count,
  35 with a different exit day — so `realized_pnl_abs` describes a different
  position by construction (136 mismatches against it, correctly). G-MTM is
  read on `TARGET_POSITION`: `daily_pnl_csv` at the replay's exit index × the
  replay's contracts, versus the dollars the FROZEN harness booked — two
  separate computations, 221/221 within $0.01/contract, and the report says
  plainly it is not `hedge_exposure`'s two-stored-columns check. The default
  target is unchanged, so `hedge_exposure` is untouched.

### What the run printed

Gates: G-ERA v4; **G-ADMIT PASS** (this module's book reproduces
`account_sim.simulate()` — `signatures: 221 vs 221, differing 0`); **G-MTM
PASS** (position target, worst mismatch $0.0000); **G-BLIND PASS** (498
sessions, every x value and triggered set identical under `BlindRec`);
**G-POWER-K PASS** — `usable sessions per concentration tercile [162, 166,
152] floor 60 EACH` and `dense episodes 3 floor 3`, met exactly as the
registration's census said it would be.

The census reproduced the plan-time figures from the module's own run
(admitted 221 / 110 dates; skipped per_pos_delta 92 · net_delta 81 · day3_cap
64, partition EXACT; any-cluster median 0.4643; MEGATECH 53.6% / SEMIS 33.7%;
CONSTITUENT 93.4%; Spearman(gross, concentration) +0.10). Registered τ grid:
0.45 → 278 sessions / 14 episodes, 0.55 → 155 / 18, 0.65 → 60 / 11 — every
cell UNDERPOWERED, as disclosed.

ARM M on the admitted book (a measurement, never a verdict here): MTM maxDD
**−$11,348** vs realized-on-close −$8,920 — `THE GAP … maxDD $-2,428 (27.2% of
the realized-on-close drawdown) ulcer +2.49 pts TUW +15.2 pts`. Same direction
as `hedge_exposure`'s 40.2% on the every-row book, smaller; and this IS the
book `bear_deploy` D3 was read on, so its understatement is now measured
directly rather than inferred from a different book.

**Stage 1, ARM K (H = 20, 480 usable sessions, block 20):**

| read | point | block-bootstrap CI95 | ARM KN null p05 |
|---|---|---|---|
| tercile contrast (high − low) | **−$692** | [−$2,000, +$420] includes 0 | −$818 — not beaten |
| Spearman ρ | **−0.149** | [−0.383, +0.098] includes 0 | −0.217 — not beaten |

Mean forward drawdown by tercile: low −$1,552 · mid −$1,435 · high −$2,244.
ARM KG (gross-exposure control): contrast −$453 / −$1,940 / +$412 across gross
terciles — sign kept in 2 of 3, clause 4 PASS. Per dense episode: −$213,
−$451, **+$559** — clause 5 FAIL. Ex-window cuts: −$773 / −$692, clause 6
PASS. ARM K10 (sensitivity, no verdict): contrast −$413 CI [−$1,232, +$279],
ρ −0.148 CI [−0.326, +0.045] — the same picture at half the horizon.

Clauses: 1 FAIL · 2 FAIL · 3 FAIL · 4 PASS · 5 FAIL · 6 PASS →
`VERDICT — Stage 1 (ARM K, the precondition): PRECONDITION-NULL`;
`VERDICT — Stage 2 (ARM C, the mechanism): NOT RUN (Stage 1 PRECONDITION-NULL)`;
`SHIP-CRITERIA BRANCH: record in research/deployment-evidence.md as closing the
queued max-drawdown question for concentration-gated hedging; next-steps.md
§2.1 closed`.

### How to read it

- **It is the null the two-stage design was built to be able to return.**
  `hedge_exposure` could not power one hedge cell; Stage 1 does not depend on
  triggers and cleared its power gate. The point estimates lean the registered
  way (the concentrated tercile draws down ~$700 more over 20 sessions) and
  that lean sits INSIDE what rotating the concentration series against the
  curve produces by time structure alone. No direction is quoted from it.
- **The two clauses that pass are the controls.** KG keeping the sign in two
  gross terciles and the ex-window cuts keeping it say the (null) result is
  not a gross-exposure effect in disguise and not one window's artefact. That
  makes it a cleaner null, not a weaker one — GROSS-NOT-CONCENTRATION did not
  fire either.
- **Clause 5 is the substantive failure**: the 2025 dense episode has the
  OPPOSITE sign (+$559). Concentration predicted drawdown in the two 2024
  episodes and anti-predicted it in 2025 — exactly the instability a
  pre-committed every-episode clause exists to catch.
- **What it does not say.** Nothing about hedging in general, nothing about
  the §4 bear sleeve, nothing about `hedge_exposure`'s every-row book (its
  UNDERPOWERED stands over a different object), and nothing about
  `concurrency_correlation`'s per-position question. It says: on the book the
  operator runs, a concentration reading is not a drawdown forecast.
- **Twenty discretionary choices are disclosed in one block** (NOT
  PRE-REGISTERED in the report), each with the clause it feeds — the G-MTM
  target, the sim-window occupancy, forward windows computed on the full
  curve before any cut, episode membership by date span, `window_cuts` applied
  per session, the overlay-ledger semantics Stage 2 would have used. The
  grading pass should read that block against the registration first.

### Next

`python -m scripts.study_review hedge_concentration` (never `--dry-run`). On
a clean grade and the operator's sign-off, the branch is recorded in
`deployment-evidence.md` and §2.1 closes; a grading defect reopens the module,
not the registration.

## 2026-09-02 — `exit_basis` re-measured: the ban was right for v3 and WRONG for v4; the proxy half never wrote at all

**Prompted by** the standing rule "never key a study on `exit_basis`" and the
question of whether an unused column should just be deleted. It should not — but
the ban needed narrowing, and re-measuring turned up a separate live bug.

**What the column is.** `{PROD, CREDIT, BEAR_DEBIT, <regime cell>}` in
merge-precedence order — which of the four exit rule sets governed a result row.
Pooling rows across bases is exactly the ambiguity it exists to prevent, so it is
the natural stratifier for any future exit study.

**Three findings, measured on `backtests/to_evaluate/` (era v4, 2026-08-27 export).**

1. **v4 is clean.** Header matches `core._KEY_ORDER` **47/47**; **485/485 rows
   labelled** — `PROD` 260 / `CREDIT` 113 / `BEAR_DEBIT` 95 / `BEAR_HE` 17. Every
   2026-08-14 corruption symptom is gone: **0** `CREDIT` rows on a positive entry
   price (7 of 13 before), `BEAR_HE` does carry a `trailing_stop`, `BEAR_DEBIT`
   does carry `be_stop`. Cause of the repair: the 2026-08-11 version bump
   recreated the tabs empty, and `append_rows` writes a header on an empty tab.
   Nobody fixed it deliberately — the version bump did it as a side effect, which
   is why it went unnoticed for three weeks.
2. **v3 and earlier stay unreadable, permanently.** `v3_BacktestResults` has no
   `exit_basis` header at all — 47 columns ending in a nameless `''` field.
   `v2_BacktestResults` (46), `v3_BacktestProxy` and `v2_BacktestProxy` (45) do
   not carry the column. Frozen exports; this never gets repaired. The
   2026-08-14 measurement was correct **about the export it was taken on**.
3. **`BacktestProxy` has been blank in every era, and it was not corruption —
   it was a write bug.** `proxy.py::_evaluate` copied only `_RESULT_COLS` into
   the row, while `exit_basis` sits in `_BASIS_COLS`. All **1,111** rows blank,
   including the **461 `underlying_trend`** rows that `proxy.py:536` explicitly
   sets to `"NONE"`. A study stratifying the proxy book by exit profile would
   have read it as a single basis, silently.

**Zero readers, and that is the point.** Nothing in `scripts/`, `lib/`, `web/` or
any study consumes the column today. It was kept — over deletion — because the
four bases are four different exit rule sets and a future exit study needs to cut
on them; a write-only column that is *correct* is cheap, and it is the last
column in both key orders, so it costs nothing positionally either.

**Shipped (no simulated number changes — `_exit_basis` is a labeller, it does not
feed `_effective_sim_cfg`):**

- `proxy.py::_evaluate` copies `_RESULT_COLS + _BASIS_COLS`. Re-run the proxy
  before reading the column off that tab; existing rows stay blank.
- `align_tab_headers.py` resolves a target schema **per tab** (`SCHEMAS` /
  `schema_for`): analysis → `ROW_COLUMNS`, `BacktestResults` → `_KEY_ORDER`,
  `BacktestProxy` → `_PROXY_KEY_ORDER`, `vN_` renames mapping to the same
  schema. It targeted `ROW_COLUMNS` for **every** tab before — that gap is
  precisely how the column landed nameless on v3. Both tabs now sweep by default;
  the live v4 headers already agree (47/47, 46/46), so this is a guard against
  the next key-order change, not a repair. **`next-steps.md` §0c's open operator
  action is closed by this, and needed no Sheets write.**
- The ban narrowed from absolute to era-scoped in `simulate.py`,
  `replay_basis.py`, `docs/backtest-reference.md`, `glossary.md`,
  `deployment-evidence.md` and `next-steps.md` §0c/§3.

**What did NOT change.** `lib/replay_basis.py` still refuses to key on the
column, deliberately: it must work on v3, and "which profile was this written
under" is a different question from "does this row replay under the profile I am
testing" — the latter has to come from the replay, not a stored label.

**Tests: 2,723 passed.** 8 new — 3 pinning that a proxy row carries its basis
(priced tier `PROD`, direction-only `NONE`, `unevaluable` blank; the first two
fail without the fix, verified), 5 pinning the per-tab schema routing.

## 2026-09-02 — exit_basis is now AUDITED, not trusted: three one-directional checks, reporting only

Follow-on to the entry above. Keeping the column meant making it checkable, since
the point of keeping it was that a future study will STRATIFY on it — and would
otherwise do so on an unverified label.

`scripts/backtest_study/lib/basis_audit.py` runs on every `load_book()` call.
Population: the pooled v4 book, 996 rows (485 real + 511 proxy), era `v4`,
145 dates, 2024-01-10 → 2025-11-04.

    exit_basis coherence: 485 coherent, 511 unlabelled, 0 sign_conflict,
                          0 cell_conflict, 0 unreachable_reason, 0 unknown_basis of 996

The 511 unlabelled are the BacktestProxy rows, blank until the proxy is re-run
(the writer fix shipped the same day). All 485 real rows are coherent under all
three checks.

**It reports; it never gates.** `_exit_basis` is a pure labeller that feeds
nothing, so an incoherent label cannot move a simulated number — only mislead a
stratification. Refusing a book on it would block the exit-profile-combination
work the column exists to enable, and would block it hardest on v3, where the
label is known-bad and the rows are fine. That is the opposite of
`lib/replay_basis.py`, which DOES gate: a HARD row there means the harness and
the stored row disagree about a path both claim the same rules for, which does
make the variant numbers untrustworthy.

**The three checks, and why two of them are one-directional.**

| Check | Direction | Keyed on |
|---|---|---|
| `sign_conflict` | both | `CREDIT` ⇔ `entry_net < 0` — `_exit_basis`'s unconditional first branch, so provable from the row alone with no config |
| `cell_conflict` | one | a regime label vs `MechLabeler.cell()`, re-derived from the SPY/VIX table — a source that never went near the sheet |
| `unreachable_reason` | one | stored `exit_reason` ∈ `unreachable_reasons(claimed profile)` |

One-directionality is the substance, not a hedge: **a basis can be ARMED without
GOVERNING.** On this book 112 rows are labelled non-PROD but only 14 carry an
outcome `DEBIT_PROD` could not have produced; the other 98 exited on
`stop_loss` 34 / `profit_target` 31 / `dollar_stop` 23 / `time_exit` 8 /
`cap_open` 2 — reasons the base profile emits perfectly well. A bidirectional
check would call all 98 incoherent and silently shrink every stratified cut.
Likewise a row whose date IS `BEAR_HE` but which was simulated before the
2026-07-22 override correctly reports `PROD`.

**Retrospective: it would have caught the v3 corruption loudly.** Reading v3's
nameless 47th column positionally as `exit_basis` over its 406 rows gives
`43 coherent, 338 unlabelled, 22 sign_conflict, 3 unreachable_reason` — e.g.
`BEAR_HE` on a `dollar_stop` row with `entry = −5.40`, `CREDIT` on a
`trailing_stop` row with `entry = +0.82`. As WIRED it sees none of that, because
the column is unnamed there and every row audits as *unlabelled*: an unreadable
label is not a wrong one, and v3 studies are untouched.

**The profile table is HISTORICAL, deliberately.** `BASIS_KNOBS` is not a read of
`config/backtest.yml`: `simulation.structure_exit.enabled` is `false` as of today
while 95 v4 rows carry `BEAR_DEBIT` from when it shipped 2026-08-11, so a live
read would call all 95 incoherent. Only knob PRESENCE is consulted
(`unreachable_reasons` tests `is None`), so re-tuning a threshold does not date
the table — adding or removing a RULE does, and then the new basis needs an entry.

26 tests in `tests/test_basis_audit.py`; suite 2750 pass. A study that stratifies
by exit profile filters on the record's `basis_trusted`.

## 2026-09-02 — the text ↔ backtest loop BUILT and first-run: text is the last untested column family, and it NULLS; the model's own stop is CONTRARY on bull calls

Operator asked for a workflow that joins the analysis TEXT, the backtest results
and (bounded) raw data back into "the training loop" — a more robust prompt, or
entry/exit criteria with a higher profit factor. Scope decided: MINE + EVALUATE
(corpus, studies, and a prompt-evaluation harness); shipping a prompt stays a
manual v5 bump. Budget decided: ~40 backfill dates × 2 arms of production-model
calls. Plan file: `~/.claude/plans/giggly-dreaming-gizmo.md`.

**Infrastructure (all tracked, all tested; suite 2,947 pass after the catalog
entries).**
- `lib/text_corpus.py` — re-attaches the model's prose to every priced row through
  `book.py`'s OWN join (imported by identity, never re-implemented), inverts the
  play cell (pinned against `analysis_to_rows`), splits the tagged signal stream,
  emits the six regex features with NO numeric twin already tested null, and
  returns the UNPRICED analysis rows by reason. `citation_check` re-fetches a
  date's raw analysis inputs into `backtests/analysis_inputs_cache/` (never
  `audit/`). Census: v4 = 1,022 priced / 148 dates against 969 unpriced
  (`excluded_by_book` 611 · `not_backtested` 194 · `market_row` 164) — **about
  half of what the model proposes never prices**, which conditions every text
  claim. `invalidation_type` is 91% "mixed" in both eras (house style "a price
  level OR a flow reversal"); only a binary price_only-vs-mixed cut is honest.
- `lib/protocol.py` — `pf` / `pf_ci_by_date` / `pf_paired_by_date`, date-resampled
  like every other CI; a PF claim must also clear the mean-R criterion and PF is
  never printed alone (PF is gameable by fewer, larger wins).
- Pipeline: `python -m scripts.analysis_pipeline --date D --output-dir DIR
  [--framework-file F --method-file M]` writes the parsed analysis, the ASSEMBLED
  PROMPT, the RAW RESPONSE and a `ROW_COLUMNS` CSV locally and NEVER reaches
  `append_rows` — the re-run-doubles-rows trap cannot be hit from this path.
  Backtest + proxy accept `analysis.csv` and `sheet_tab: null` (derived config;
  commented examples in `config/backtest.yml`). Tab row count identical before
  and after the smoke call. `docs/architecture.md` §"Local-only prompt
  evaluation runs" states both invariants.
- Three registrations (`f1_selection/text_features.md`,
  `f2_management/exit_from_text.md`, `f1_selection/prompt_eval.md`), each with a
  dated build-time "wording corrections" tail, none of which moves a bar.

**`exit_from_text` (f2) — first run, era v4 PRIMARY, 995/1,022 admitted (27
HARD, classify-not-assert): NO CANDIDATE.** `tally: {'UNDERPOWERED': 276, 'NOT A
CRITERION (pooled)': 9, 'NULL': 19, 'CONTRARY': 5}`. All five CONTRARY cells are
E1 invalidation-as-stop on `bull_call_spread` / `LVOL` where the stated level is
NOT a strike — `STRUCT bull_call_spread buf1%/ne_strike: affected 360 rows / 134
dates … DeltaR -0.045 … CI95 [-0.083, -0.008] … real -0.064 tweak -0.027`, every
criterion true toward the NEGATIVE sign: **the model's own invalidation level,
used as an underlying-close stop, reliably cuts the engine structure's
winners.** This is the reactive-exit null of Attempts 1/2/10 arriving from the
text side — a price-level stop the model wrote at analysis time is still a
price-level stop. E2 (trigger-as-entry-filter) pooled N=3 reads CANDIDATE but is
`NOT A CRITERION (pooled)` and an INTAKE effect by registration; 11% of triggers
are conditional-but-unparseable (own bucket). E3 (horizon as time exit)
`SURVIVAL CONTROL: FAIL`. v3 SECONDARY (702 admitted): three CANDIDATE cells,
all `bear_put_spread` E1 at buf1%/buf2% in the registered `level != any strike`
cell (buf1%: 284 rows, 110 affected / 62 dates, dR +0.085 CI [+0.044, +0.126],
LOO min +0.079, all years/tiers/windows) — consistent with "bear is an EXIT
problem" (2026-08-11), but v4 cannot see it (no 2026 dates, bear cells
underpowered). **Re-read item, never a ship from a secondary era.**

**`prompt_eval` (f1) — the loop step, built and smoke-tested.** Sub-commands
`dates` (sets by RULE) · `variance` (PROD × 3 repeats — `claude -p` has no
temperature knob, so the noise floor is measured first) · `run` (PROD vs a
COMMITTED candidate dir on the backfill set, priced through derived local-only
configs, compared with `boot_ci_paired_by_date` + `pf_paired_by_date` under the
shipped top-3/day ladder, plus tier mix, emissions/date, unpriceable share,
hallucination rate, `bear_call_spread` leaks counted off the ANALYSIS rows
because the proxy blanks `structure` on vetoed rows) · `accumulate` (candidate
arm on each NEW live date — the PRIMARY evidence; backfill is SECONDARY because
both arms share the backfill's lookahead: the v4 book itself was backfilled in
2026-08 with a 2026 model) · `draft` (a headless model proposes a candidate DIR
from the robustness list; a record, never applied). Refusals: `--tab` anywhere,
non-null `sheet_tab`, a used run dir (the proxy writer archives its CSV, so a
second pass truncates the book — fresh `--run-dir` every run). Date sets
declared: `backtests/prompt_eval/variance-dates.txt` (5) and
`backfill-dates.txt` (40 of 143 eligible: BEAR×2024 1 / BULL×2024 17 /
BULL×2025 10 / RANGE×2024 6 / RANGE×2025 6; seed 20260902). **Variance run
started this evening** → `backtests/prompt_eval/variance-20260902/`; the 80-call
backfill scoring waits on a COMMITTED candidate — an operator decision, and
`text_features` (below) produced nothing for `draft` to work from.

**Runner traps met today (not fixed, logged):** `run.py` forwards a `--`
sentinel verbatim (only `prompt_eval` strips it — pass study flags bare:
`run text_features --era v3 --labels run`); an argparse usage error exits 2,
which equals `era.EXIT_THIN_ERA` and is therefore read as a DESIGNED REFUSAL and
promoted to `-latest.txt` (one such transcript was produced and deleted by
hand); `-latest.txt` is not era-scoped, so run v3 first and current last.

**`text_features` (f1) — first run, era v4 PRIMARY: NULL everywhere.** 1,022
priced / 148 dates; ARM B blind labels 1,022/1,022 after the batch-10 top-up
(batch 25 silently truncated 620/1,804 payloads — coverage, never correctness);
citation check 148/148 dates, **1.62% of cited flow figures unmatched** (v3
2.86%) — the prompt is not hallucinating prints. Verdict block: every feature
`NULL` or `UNDERPOWERED` in ARM A (`invalidation_level NULL cells=15 powered=2`,
`alt_ratio NULL cells=15 powered=2`, `hallucination_rate UNDERPOWERED cells=15
powered=0`), ARM B (`thesis_type NULL cells=75 powered=4`) and ARM C
(`thesis_type NULL arms=10 powered=8`); `PROMPT-ROBUSTNESS FINDINGS … none`,
`ENTRY-GATE CANDIDATES … none`. v3 SECONDARY: the same, plus one ARM C
`alt_ratio` VETO that clears the six-point conjunction and BH but LOWERS mean R
(dR −0.0762, PF up) — routed to `NO PRE-REGISTERED VERDICT MATCHES` by the
catch-all and resolved here as NOT A CANDIDATE (the registered ENTRY-GATE list
requires mean R AND PF to rise; a gate that trades mean R for PF is the exact
gaming the PF rule exists to refuse). **Text was the last untested column
family, and it nulls like the numeric ones.** The 2026-08-11 "re-open only on
NEW COLUMNS" clause is now spent: the model's numbers, its prose, and its
citation faithfulness all fail to separate outcome within structure × tier.
Selection stays structure × model regime × entry geometry. Nothing for
`prompt_eval draft` to work from — a candidate prompt, if one is written, will
be an operator's hypothesis, not a data-derived one.

**Variance run (prompt_eval, PROD × 3 repeats) — interrupted by the account
session limit** at 23:36 (`claude exited 1` three times on 2024-02-01, repeat
2) after repeat 1 completed and priced. Resumed 2026-09-03 09:50 into a fresh
run dir seeded with the finished analyses (`variance-20260903/`); the harness
skips a date whose rows CSV exists, so no model call is repeated. Noise floor
to be appended when it lands.
