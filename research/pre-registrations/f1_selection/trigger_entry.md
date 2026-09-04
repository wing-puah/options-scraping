## trigger_entry — does entering only ON the stated trigger beat entering unconditionally?

_REGISTERED 2026-09-04; status: DRAFT — becomes immutable on first run._

An f1 SELECTION study. The exit profiles, the sizing formula, the structure
universe and the candidate set are frozen; the ONE thing that moves is WHETHER
and WHEN a play is opened.

## Admissibility

Selection reopens on **NEW COLUMNS ONLY**. This study introduces exactly one:
the model's own stated **entry TRIGGER** — a price LEVEL plus a DIRECTION,
printed on the card the operator reads, observable at entry, and **ignored by
production**. `config/backtest.yml` sets `entry_timing: next_open` and
`scripts/backtest/simulate.py` fills every non-vetoed play at the next
session's open regardless of what the trigger says.

`exit_from_text` ARM E2 (2026-09-02) censused the level but **kept the
next-open entry price**, so the favourable early move that satisfied the
trigger sits INSIDE the ENTERED number — the exact confound `next_day_move`
ARM C exposed. **Nobody has tested entering AT the trigger and PAYING for the
confirmation.** That re-pricing is what makes this a new question and not a
second look at a closed one.

## Question

Does entering a play only WHEN its stated trigger level is first crossed, **at
that session's CLOSE**, beat the unconditional next-open entry **once the entry
price pays for the confirmation**?

## What this is NOT

- **Not an exit study.** Every arm replays the SHIPPED per-row exit profile
  through the FROZEN `lib/harness.replay` — **import only, no fork, no copy, no
  edit**. No arm changes an exit rule. `staged_exit`'s replay fork is not
  needed and is not reproduced.
- **Not an intraday-touch rule. CLOSE ONLY.** `exit_from_text.trigger_met` is
  close-based, the `SRC_TILDE` fallback bar tier has no high or low at all, and
  the only fill this book can honour is a close-marked mark. A touch rule is
  not replayable on this data and is not registered.
- **Not a re-test of the day-0 underlying move.** `next_day_move` ARM C stands.
  The day-0 move enters this study ONLY as ARM C's confound CONTROL — a
  stratifier applied to a result, never a candidate of its own.
- **Not a re-run of E2.** E2's estimand is retained ONLY as a printed census in
  E2's own shape, at shipped pricing, marked **NOT A CRITERION**, so a reader
  can see the selection claim and the re-priced claim side by side.
- **Not `lib/triggers.py`.** That module holds ROLLBACK triggers for shipped
  rules and has nothing to do with the model's entry trigger text.

## Population and basis, fixed here

- **PRIMARY: era `current` (v4)** — the prompt whose text this is. **SECONDARY:
  `--era v3`**, identical thresholds, reported separately, **never pooled**.
- `lib/text_corpus.load_corpus(include_bs=False)` — the priced book with its
  prose re-attached; real + `strike_expiry_tweak` tiers only, `bs_options_hist`
  excluded (a NO-OP on v4, still binding on v3), proxy calibration gate ON.
- **The `exit_from_text` CALIBRATION GATE runs first, unchanged and by import.**
  Every row is replayed under the profile production would actually have run
  (`bear_giveback.prod_profile_for(rec, 0.50, True)` for debits, `CREDIT_PROD`
  for credits) and classified by `lib/replay_basis.classify`; only rows that
  REPRODUCE (exact / near / boundary_tie) are admitted. This is not a
  convenience: ARM T's estimand is a re-priced replay paired against the row's
  OWN shipped replay, so a row whose baseline does not reproduce would
  contribute a delta measured against a baseline production never ran. It is
  also what makes the E2 census reproducible on this study's population.
- **In scope** = the trigger parses to a numeric price LEVEL (`text_corpus`
  `trigger_level`) **AND** a DIRECTION (`exit_from_text.trigger_direction`)
  **AND** underlying bars exist (`underlying.load_bars`) **AND**
  `underlying.entry_day` resolves. E2's exclusion buckets are reprinted with
  their n and share; the `SRC_OHLC` / `SRC_TILDE` split PRINTS beside every
  bar-using number and is never pooled silently.
- **Cells are the N grid, not a structure × regime cross.** The estimand here
  is a whole-book INTAKE question, so the registered cells are ARM T's three N
  values and ARM L's two lags. Structure and `mech_cell` marginals are NOT
  registered as criteria and are not evaluated; that cross underpowers on this
  book (`exit_from_text`, 276 of 309 cells) and adding it would be a second
  design, not a finer read of this one.
- **The 2026 disclosure.** The v4 results export carries **ZERO 2026 signal
  dates** (2024-01-10 → 2025-11-17), so `protocol.window_cuts`' `ex_2026_feb_apr`
  ≡ `ALL`, the ex-BOTH cut ≡ `ex_2025_mar_apr`, and "sign-stable per calendar
  year" reduces to 2024 ∧ 2025 on the PRIMARY era. **The report prints this
  explicitly whenever the export carries no 2026 dates**, so a reader sees a
  no-op rather than a passed test. The v3 export (2024-06-17 → 2026-04-07) does
  carry 2026 dates and the cuts bind there.

## Plan-time observations, disclosed

Measured while the study was being designed, BEFORE any arm ran. **These are
ESTIMATES from the exports on disk on 2026-09-04, not targets** — the run
prints its own and nothing is narrowed to make one come out right.

**v4 (PRIMARY).** 1,022 priced rows / 148 dates; the calibration gate admits
**995**; **in scope 853 rows / 147 dates**. Exclusion buckets: `no_direction`
109, `no_entry_session` 21, `no_trigger_text` 6, `no_level` 6. Bar tiers on the
in-scope rows: `ohlc` 804, `price_tilde` 49.

**The E2 census, at SHIPPED pricing, reproduces exactly** on that population:
N=1 ENTERED 517 rows / 140 dates mean R **+0.196** vs NOT ENTERED 336 / 131
**+0.025**; N=3 ENTERED 579 / 145 **+0.212** vs NOT ENTERED 274 / 121
**−0.048**; N=5 ENTERED 615 / 146 **+0.224** vs NOT ENTERED 238 / 115
**−0.118**. The N=3 line is `exit_from_text`'s published E2 figure to three
decimals, which is the point of reprinting it: **the selection claim this study
re-prices is the one already on the record.**

**v3 (SECONDARY).** 795 priced rows / 118 dates; gate admits 702; in scope 593
rows / 117 dates; N=3 ENTERED 412 / 112 **+0.216** vs NOT ENTERED 181 / 91
**+0.043**.

**Every ARM T cell clears the power floor on the whole book** at plan time; the
floor will bite on ARM C's conformity bands, not on the headline.

**The indexing reconciliation, disclosed because it is not exactly 1:1.**
`underlying.entry_day` equals `t.grid[0]` on 825 of 853 v4 in-scope rows and on
574 of 593 v3 rows; the remainder resolve one or two grid days later because
`grid` is WEEKDAY-based and the bar series skips market holidays. See §Frozen
grid for how the study handles the difference rather than assuming it away.

## Arms

Four arms, frozen; no fifth is added.

### ARM T — trigger-gated entry (HEADLINE)

- **Rule:** the first session **k ∈ [1..N]** whose underlying CLOSE crosses the
  stated level in the stated direction, INCLUSIVE (`>=` above, `<=` below, per
  `exit_from_text.trigger_met`, imported unchanged). Sessions are counted on
  the BAR SERIES from `underlying.entry_day` (`underlying.sessions_from`), so a
  market holiday inside the window does not consume one of the N.
- **Fill:** at that session's own CLOSE mark —
  `emission_timing.synth_trade(rec, lag)`: fill at `marks[lag]`, contracts
  **re-sized** by the production formula at the new entry price, `dte_entry`
  reduced by the calendar days the anchor moved, marks right-padded with EMPTY
  fields. The shipped per-row profile is then replayed through the **unmodified
  frozen harness**.
- **Never crossing within N → NOT ENTERED.** The row is dropped from the
  entered book, counted, and its slot is freed in ARM D.
- **N ∈ {1, 3, 5}**, frozen.

### ARM L — unconditional lag (CONTROL)

- **Rule:** every in-scope row filled at a FIXED session k, **no trigger gate at
  all**, k ∈ {1, 3}, frozen. Same synthetic construction, same frozen replay.
- **Purpose:** ARM T changes two things at once — WHEN the fill happens and
  WHICH rows are filled. ARM L holds the selection constant and moves only the
  delay, so a ΔR that ARM L reproduces is a LAG finding, not a trigger finding.
  `emission_timing` ARM L already found the book LAG-TOLERANT within three
  sessions on v3; this is that control re-run on this population and this
  basis.

### ARM C — conformity control (CONFOUND)

- **Rule:** ARM T's ΔR stratified by **entry-session conformity band**, reusing
  `next_day_move.DAY0_PNL_BANDS` and `MIN_CELL_N = 20` **verbatim**, with the
  band read off `next_day_move.day0_mark_pnl` at the SHIPPED entry session — the
  same measure that study cut on.
- **Purpose:** the trigger is satisfied by a favourable move, and a favourable
  move is already visible in the day-0 mark. Inside a band the position is
  roughly equally green either way, so any REMAINING ΔR is the trigger telling
  us something the mark had not already said. **A band thinner than
  `MIN_CELL_N` prints its n and is NOT READ.**

### ARM D — deployment read

- **Rule:** `protocol.top_k_per_day(..., protocol.ladder_rank, k=3,
  eligible_fn=…)` — the shipped top-3/day ladder — run twice on the SAME book:
  once with the shipped picks at shipped pricing, once with **NOT-ENTERED rows
  INELIGIBLE (the slot is freed to the next-ranked play)** and every entered
  in-scope row priced at its trigger fill. Rows the trigger cannot be read on
  (out of scope) stay eligible at shipped pricing in BOTH books — the gate can
  only bind where the text supports it.
- **R only. No dollar figure.**

## Frozen grid

| knob | values | may not move |
|---|---|---|
| ARM T window `N` | 1, 3, 5 | frozen |
| ARM L fixed session `k` | 1, 3 | frozen |
| ARM C bands | `next_day_move.DAY0_PNL_BANDS`, `MIN_CELL_N = 20` | imported verbatim |
| ARM D ladder depth | `k = 3` | the shipped card |
| power floor | ≥ 25 dates AND ≥ 60 rows per cell | declared before any count |
| bootstrap | `BOOT_N = 10000`, α = .05 | `protocol` defaults |

**Session numbering, and the lag it maps to.** Session **k = 1** is
`underlying.entry_day`, which is `t.grid[0]` — `_weekday_grid` is "weekdays
AFTER the signal date", so `marks[0]` is already the fill session and there is
no pre-entry mark to skip. A crossing at session k therefore fills at
`synth_trade(rec, k − 1)`. Because the grid is WEEKDAY-based while sessions are
counted on the BAR SERIES, the two can differ by a market holiday, so the module
resolves the lag as **the crossing session's own index in the trade's grid** —
which IS `k − 1` whenever `entry_day == grid[0]` and no holiday falls inside the
window, and is the crossing session's true mark otherwise. **G2 prints how many
rows differ.** A crossing session that lies beyond the end of the trade's grid
is a construction exclusion, counted, never silently re-anchored.

## Unit and metric

- **Unit = the signal DATE.** Every CI is `protocol.boot_ci_paired_by_date`,
  date-clustered, `BOOT_N = 10000`, α = .05.
- **Metric = R** (credit rows: R on the credit — `harness` denominates on
  `abs(entry_net)`).
- **NO DOLLAR FIGURE IS QUOTED ACROSS ARMS, ANYWHERE.** Contracts are RE-SIZED
  when the entry price moves (that is what holds the harness `dollar_stop`
  biting at the same effective R on every rung), so a dollar total compares two
  different position sizes and means nothing. G4 prints the sizing census
  precisely so that this is checkable rather than asserted.
- **No annualised figure, no Sharpe, no time-to-recover.** Worst-decile reads
  are FORBIDDEN as criteria (the 2026-08-13 nine-date decile wall) and are not
  computed.

**Estimands, in order of authority:**
1. **HEADLINE — ARM T:** paired-by-date ΔR on the ENTERED rows, trigger-priced
   versus **the SAME rows' shipped replay** (stored trade, same profile). This
   is the price of confirmation.
2. **CENSUS — E2 shape:** ENTERED vs the full in-scope population at SHIPPED
   pricing, excluded share (rows and dates) beside every number. **NOT A
   CRITERION**, printed for reconciliation only.
3. **ARM D deployed ΔR** under the shipped ladder.

## Gates, in order

Each blocks everything below it.

- **G0 — POWER.** ≥ 25 affected DATES **and** ≥ 60 affected ROWS per cell, else
  **UNDERPOWERED**: the census prints, no criterion is evaluated, nothing is
  refuted, and the cell is not re-run on these dates.
- **G1 — PARSE CENSUS.** Every exclusion bucket with its n and share of the
  admitted book, plus the conditional-trigger count and the SRC split. A
  prompt-robustness finding in its own right, published whatever else happens.
- **G2 — CONSTRUCTION (G-SYNTH).** `synth_trade(rec, 0)` must reproduce the
  stored trade in `signal_date`, `dte_entry`, grid and mark path, differing
  ONLY in fill price and contract count. **Any `Trade` construction failure
  FAILS THE RUN** (a silently dropped row would make the ladder a comparison
  between different populations). Padded-row count and the grid/session
  reconciliation count print.
- **G3 — LEAK GUARD.** Every row OUTSIDE the in-scope population must come back
  byte-identical to its shipped replay on `(exit_reason, days_held,
  round(pnl, 10))`. The keying is evaluated INSIDE the outcome function and the
  whole admitted book is handed to it — a pre-filtered list could not leak and
  would make the gate vacuous. One changed row fails the run.
- **G4 — SIZING CENSUS.** Contract distribution per k against the stored count,
  with the "no dollar figure across arms" statement printed beside it.
- **G5 — DEADLINE DIAGNOSTIC.** The synthetic's time exit recomputes from the
  NEW entry anchor, which is production semantics
  (`scripts/journal/lib/exit_rules.py`). The absolute-from-signal alternative
  is a **printed diagnostic, not a second grid**: the report counts how many
  ARM T `time_exit` rows would exit on a different session under it.

## Bar for CANDIDATE

The full conjunction, all eight — failing any one is failing:

1. paired date-clustered CI **excludes zero** (`BOOT_N = 10000`, α = .05);
2. **every** LOO-by-date fold on the point estimate's side
   (`protocol.loo_by_date`, read `min_gain`);
3. survives `protocol.window_cuts` **AND the ex-BOTH cut added BY HAND**;
4. **sign-stable per calendar year** (`protocol.sign_stable`) — **DISCLOSED:
   with no 2026 dates on v4 this spans 2024/2025 only, and the report says so**;
5. right-signed on **BOTH pricing tiers** (real and tweak);
6. floor re-checked on the EVALUATED set (≥ 25 dates, ≥ 60 rows);
7. **no sign flip across N ∈ {1, 3, 5}** — a knob artifact fails whatever its
   CI says;
8. **ARM C: the ΔR survives inside the conformity bands** — right-signed in
   every `DAY0_PNL_BANDS` band holding ≥ `MIN_CELL_N` entered rows. If NO band
   clears `MIN_CELL_N`, criterion 8 FAILS: nothing survived to check.

**L-SEP, the separation test** (used by the verdict grammar, not a ninth
criterion): ARM T at N **separates** from ARM L at the matched k when ARM T's
ΔR exceeds ARM L's ΔR at that k **and** ARM L's own ΔR does not itself clear
criterion 1 in the same direction. The **matched k** for N is
`min(N, 3)` — N=1 → k=1, N=3 → k=3, N=5 → k=3, the deepest registered lag.
Both numbers print beside every ARM T cell.

## Verdicts, worded now

Per ARM T cell, **exactly one**, evaluated in this ORDER, first match wins.
The grammar is EXHAUSTIVE — no cell may be given a word that is not on this
list, and the **criteria vector prints under every verdict**.

1. **UNDERPOWERED** — a floor was not met. Census published, nothing read, no
   re-run on these dates.
2. **LATE-ENTRY** — ΔR ≤ 0 **and** the E2-shape selection census reproduces at
   shipped pricing on this N (ENTERED mean R above the in-scope mean R). The
   signal works — the trigger does sort winners from losers — but the confirmed
   entry comes AFTER the move it selects on, so the confirmation costs at least
   as much as it is worth. This is the registered null-with-a-mechanism, and it closes E2
   as a shippable intake rule.
3. **CONTRARY** — criterion 1 holds with ΔR < 0 and the census does NOT
   reproduce: the trigger is actively misleading. Fed to the
   PROMPT-ROBUSTNESS list.
4. **CONFOUND-EXPLAINED** — ΔR > 0, criteria 1–7 hold, criterion 8 fails: the
   gain lives outside the conformity bands, i.e. it is the day-0 move
   `next_day_move` ARM C already owns.
5. **LAG-EXPLAINED** — ΔR > 0, all eight criteria hold, but **L-SEP fails**:
   ARM L reproduces the effect without any gate, so this is about WHEN, not
   WHICH.
6. **CANDIDATE** — all eight criteria hold **and** L-SEP holds. **An INTAKE
   proposal, never an exit rule and never a ship**: it becomes a written
   proposal with its own rollback trigger and an independent-window
   confirmation before it may reach `docs/deployment-rules.md`.
7. **NULL** — powered, nothing above matched. Recorded.

ARM L, ARM C and ARM D carry **no verdict word of their own**: ARM L and ARM C
feed criteria 8 and L-SEP, and ARM D is a deployment READ printed with its ΔR
and CI. The E2-shape census carries no verdict at all.

## Anti-tuning

The grid above is frozen and **every cell is reported regardless of outcome**.
Nothing is added, moved, or dropped after a number is seen. Exit profiles, the
sizing formula, the structure universe, the entry side, the ladder depth and
the candidate population are NOT swept. The study is **read-only and touches no
config**. Structure × `mech_cell` cells are deliberately NOT registered and are
not computed — adding them after reading the headline would be exactly the
tuning this section forbids.

## Build notes

*Not part of the registration — implementation record.*

- Module `scripts/backtest_study/f1_selection/trigger_entry.py`; run
  `python -m scripts.backtest_study run trigger_entry` (`--era v3` secondary);
  report `backtests/study_output/trigger_entry-latest.txt`. `lib/harness.py` is
  **NOT touched and NOT copied**.
- Reuse is by IMPORT, nothing re-implemented:
  `emission_timing.synth_trade` / `size_contracts` / `profile_for`;
  `exit_from_text.trigger_direction` / `trigger_met` / `source_split` /
  `calibration_gate` / `changed`; `underlying.load_bars` / `entry_day` /
  `sessions_from`; `next_day_move.DAY0_PNL_BANDS` / `MIN_CELL_N` /
  `day0_mark_pnl`; `protocol.boot_ci_paired_by_date` / `window_cuts` /
  `loo_by_date` / `sign_stable` / `top_k_per_day` / `ladder_rank` /
  `ladder_eligible`; `bear_giveback.hdr` / `sub`.
- `DESIGNED_REFUSAL_EXIT_CODES = {2, 3}` as a PLAIN SET LITERAL — the runner
  AST-parses it and a `frozenset(...)` call would misfile `lib/era.py`'s
  refusals as failures.
- `tests/test_trigger_entry.py` must exist and must pin: the k-indexing
  (a crossing at session k fills at `marks[k−1]`), `first_cross` returning None
  when nothing crosses within N, G-SYNTH at lag 0 over the
  `tests/test_harness_replay.py` fixture (imported, never copied), the leak
  guard on a no-direction row, `trigger_met` inclusivity in both directions, a
  holiday not consuming an N, a credit row's synthetic having a positive denom
  and a sane contract count, and a close-only (`SRC_TILDE`, o/h/l None) bar
  never raising.
- A `scripts/study_map/catalog.py` entry with a hand-written VERDICT is
  REQUIRED — no entry fails the test suite — plus a `research/study-map.md`
  prose mention (test-enforced) and an `research/arm-index.md` section (also
  test-enforced).
- Every report prints: the era header, `date_range`, the no-2026-dates note
  when it applies, the calibration census, G1's full parse census, the SRC
  split, G0, G2, G3, G4, G5, ARM T per N, the E2-shape census marked NOT A
  CRITERION, ARM L at the matched k, ARM C's band table, ARM D, and the verdict
  summary table with its `Counter` tally.

---

## Wording corrections — appended 2026-09-04 at build time

*Not amendments. Nothing below moves a threshold, adds a cell, changes an arm's
definition or touches a verdict rule. Each entry records a place where the
registration's WORDING could not be implemented literally against the frozen
harness, the frozen corpus or `exit_from_text`'s published figures, and states
exactly what the module does instead. Appended at the end, dated, as the record
of what the run actually ran.*

1. **The E2-shape census keys on "the trigger was MET", not on "ARM T could
   build a synthetic for it".** §Unit and metric calls estimand 2 "ENTERED vs
   the full in-scope population at SHIPPED pricing". A handful of rows meet the
   level at a session whose mark is unusable (`degenerate_zero_entry`: 13 of 853
   on v4 at lag 0, 6 at the crossing session). Counting those on the NOT-ENTERED
   side would make the census disagree with `exit_from_text`'s published E2
   figures for a reason that has nothing to do with selection. They are a
   CONSTRUCTION exclusion, reported in G2, and ARM T's evaluated n prints beside
   each census row so the two numbers reconcile on the page. With this the N=3
   census reproduces E2 exactly: **ENTERED 579 rows / 145 dates +0.212 vs NOT
   ENTERED 274 / 121 −0.048 on 853 in-scope rows / 147 dates.**

2. **A row with no usable day-0 mark is a COUNTED G2 exclusion, not a G-SYNTH
   failure.** §Gates says "any `Trade` construction failure FAILS THE RUN". That
   binds on a row `synth_trade` tried to BUILD and could not — which aborts
   through the imported helper. A row whose day-0 mark is absent or a degenerate
   `0.00` has nothing to reproduce in the first place; it is excluded, counted
   with its reason, and never counted as a pass. G-SYNTH's assertion is
   evaluated on the rows that do build, and on v4 all 840 of them reproduce.

3. **The G2 abort prints `emission_timing`'s own gate label.** Construction
   failures raise inside the IMPORTED `emission_timing.synth_trade`, whose
   message says "G1" because that is ITS gate number. The label belongs to that
   module; the abort belongs to this study's G2. Noted in the report where it
   would otherwise confuse a reader.

4. **Criterion 5 is evaluated on the pricing tiers PRESENT in a cell.** The
   registration says "right-signed on BOTH pricing tiers". A cell containing
   rows from only one tier is graded on that tier — the same rule
   `exit_from_text.evaluate_cell` applies. On the v4 PRIMARY run every ARM T
   cell carries both tiers, so this makes no difference to any number recorded
   here; it is stated so a thinner future cut cannot be read as having cleared a
   test it never ran.

5. **`first_cross` is asserted equal to `trigger_met` at run time.** §Arms says
   the crossing is "inclusive, per `trigger_met`". Rather than trust that,
   G2 evaluates BOTH on every in-scope row × every N and FAILS THE RUN on a
   single disagreement, so there is one definition of "met" and it is
   `exit_from_text`'s. 0 disagreements on both eras.

6. **2026-09-04 (after the first run) — verdict label renamed `PRICED-AWAY` →
   `LATE-ENTRY`; definition unchanged.** The operator read "priced-away" as
   ambiguous between "the edge was arbitraged out" and "the entry is late".
   The registered condition (ΔR ≤ 0 with the census reproducing) is the second
   reading, so the label now says it: the signal works, the confirmed entry is
   late. No gate, bar, arm, or verdict CONDITION changed; the study-results
   record keeps the first run's sections verbatim under the old word, and the
   re-run appends new sections under the new one.

