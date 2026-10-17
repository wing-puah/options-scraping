## trigger_entry — does entering only ON the stated trigger beat entering unconditionally?

<!-- outcome:start -->
> Latest outcome: `ARM T` `LATE-ENTRY` at N=1, N=3 and N=5 — 2026-09-28 · [record](../../../study-results/f1_selection/signal/trigger_entry.md).
<!-- outcome:end -->

_Registered 2026-09-04._

## The question

Does entering a play only WHEN its stated trigger level is first crossed, **at
that session's CLOSE**, beat the unconditional next-open entry **once the entry
price pays for the confirmation**?

An f1 SELECTION study. The exit profiles, the sizing formula, the structure
universe and the candidate set are frozen. The ONE thing that moves is WHETHER
and WHEN a play is opened.

**Why admissible.** Selection reopens on **NEW COLUMNS ONLY**. This study adds
exactly one: the model's stated **entry TRIGGER**, a price LEVEL plus a
DIRECTION, on the operator's card, observable at entry, and **ignored by
production** (`config/backtest.yml` sets `entry_timing: next_open`;
`scripts/backtest/simulate.py` fills every non-vetoed play at the next open).
`exit_from_text` ARM E2 (2026-09-02) censused the level but **kept the next-open
entry price**. The favourable move that met the trigger thus sits INSIDE the
ENTERED number, the confound `next_day_move` ARM C exposed. **Nobody has tested
entering AT the trigger and PAYING for the confirmation.**

## What this study is not

- **Not an exit study.** Every arm replays the SHIPPED per-row exit profile
  through the FROZEN `lib/harness.replay`: **import only, no fork, no copy, no
  edit**. No arm changes an exit rule. `staged_exit`'s replay fork is not needed and is not reproduced.
- **Not an intraday-touch rule. CLOSE ONLY.** `exit_from_text.trigger_met` is
  close-based, the `SRC_TILDE` fallback bar tier has no high or low, and the
  only fill this book can honour is a close-marked mark. A touch rule is not
  replayable here and is not registered.
- **Not a re-test of the day-0 underlying move.** `next_day_move` ARM C stands.
  The day-0 move enters ONLY as ARM C's confound CONTROL, never as a candidate.
- **Not a re-run of E2.** E2's estimand survives ONLY as a printed census in
  E2's own shape, at shipped pricing, marked **NOT A CRITERION**.
- **Not `lib/triggers.py`.** That module holds ROLLBACK triggers for shipped
  rules, unrelated to the model's entry trigger text.

## Population and basis, fixed here

- **PRIMARY: era `current` (v4)**, the prompt whose text this is. **SECONDARY:
  `--era v3`**, identical thresholds, reported separately, **never pooled**.
- **Corpus:** `lib/text_corpus.load_corpus(include_bs=False)`, the priced book
  with its prose re-attached. Real + `strike_expiry_tweak` tiers only;
  `bs_options_hist` excluded (a NO-OP on v4, still binding on v3); proxy
  calibration gate ON.
- **The `exit_from_text` CALIBRATION GATE runs first, unchanged and by import.**
  Each row is replayed under the profile production would have run
  (`bear_giveback.prod_profile_for(rec, 0.50, True)` for debits, `CREDIT_PROD`
  for credits) and classified by `lib/replay_basis.classify`. Only rows that
  REPRODUCE (exact / near / boundary_tie) are admitted, because ARM T's delta is
  measured against the row's OWN shipped replay.
- **In scope** = the trigger parses to a numeric price LEVEL (`text_corpus`
  `trigger_level`) **AND** a DIRECTION (`exit_from_text.trigger_direction`)
  **AND** underlying bars exist (`underlying.load_bars`) **AND**
  `underlying.entry_day` resolves. E2's exclusion buckets reprint with n and
  share. The `SRC_OHLC` / `SRC_TILDE` split PRINTS beside every bar-using number
  and is never pooled silently.
- **Cells are the N grid, not a structure × regime cross:** ARM T's three N
  values and ARM L's two lags. Structure and `mech_cell` marginals are NOT
  registered as criteria and are not evaluated; that cross underpowers on this
  book (`exit_from_text`, 276 of 309 cells).
- **The 2026 disclosure.** The v4 results export carries **ZERO 2026 signal
  dates** (2024-01-10 → 2025-11-17). On the PRIMARY era, `protocol.window_cuts`'
  `ex_2026_feb_apr` ≡ `ALL`, the ex-BOTH cut ≡ `ex_2025_mar_apr`, and
  "sign-stable per calendar year" reduces to 2024 ∧ 2025. **The report prints
  this explicitly whenever the export carries no 2026 dates**, so a no-op is not
  read as a passed test. The v3 export (2024-06-17 → 2026-04-07) carries 2026
  dates, and the cuts bind there.

## Plan-time observations, disclosed

Measured BEFORE any arm ran. **These are ESTIMATES from the exports on disk on
2026-09-04, not targets.** The run prints its own; nothing is narrowed to match.

**v4 (PRIMARY).** 1,022 priced rows / 148 dates; the gate admits **995**; **in
scope 853 rows / 147 dates**. Exclusions: `no_direction` 109, `no_entry_session`
21, `no_trigger_text` 6, `no_level` 6. Bar tiers in scope: `ohlc` 804,
`price_tilde` 49.

**The E2 census at SHIPPED pricing reproduces exactly** (rows / dates, mean R).

| N | ENTERED | NOT ENTERED |
|---|---|---|
| 1 | 517 / 140, **+0.196** | 336 / 131, **+0.025** |
| 3 | 579 / 145, **+0.212** | 274 / 121, **−0.048** |
| 5 | 615 / 146, **+0.224** | 238 / 115, **−0.118** |

The N=3 line is `exit_from_text`'s published E2 figure to three decimals: **the
selection claim re-priced here is the one already on the record**.

**v3 (SECONDARY).** 795 priced rows / 118 dates; gate admits 702; in scope 593
rows / 117 dates; N=3 ENTERED 412 / 112 **+0.216** vs NOT ENTERED 181 / 91
**+0.043**.

**Every ARM T cell clears the power floor on the whole book** at plan time; the
floor is expected to bite on ARM C's bands, not the headline.

**Indexing is not exactly 1:1.** `underlying.entry_day` equals `t.grid[0]` on 825
of 853 v4 in-scope rows and 574 of 593 v3 rows. The rest resolve one or two grid
days later: `grid` is WEEKDAY-based and the bar series skips market holidays.

## What it compares

Four arms, frozen; no fifth is added.

| Arm | What it does | Kind |
|---|---|---|
| [ARM T](../../../arm-index.md#trigger_entry) | Fill at the CLOSE of the first crossing session within N; else NOT ENTERED | HEADLINE |
| ARM L | Fill every in-scope row at a FIXED session k, no gate | CONTROL |
| ARM C | ARM T's ΔR by entry-session conformity band | CONFOUND |
| ARM D | Shipped top-3/day ladder, with and without the gate | deployment read |

### ARM T — trigger-gated entry (HEADLINE)

- **Rule:** the first session **k ∈ [1..N]** whose underlying CLOSE crosses the
  stated level in the stated direction, INCLUSIVE (`>=` above, `<=` below, per
  `exit_from_text.trigger_met`, imported unchanged). Sessions are counted on the
  BAR SERIES from `underlying.entry_day` (`underlying.sessions_from`), so a
  market holiday does not consume one of the N.
- **Fill:** at that session's own CLOSE mark via
  `emission_timing.synth_trade(rec, lag)`: fill at `marks[lag]`, contracts
  **re-sized** by the production formula at the new price, `dte_entry` reduced
  by the calendar days the anchor moved, marks right-padded with EMPTY fields.
  The shipped profile then replays through the **unmodified frozen harness**.
- **Never crossing within N → NOT ENTERED:** dropped from the entered book,
  counted, and its slot freed in ARM D.
- **N ∈ {1, 3, 5}**, frozen.

### ARM L — unconditional lag (CONTROL)

Every in-scope row fills at a FIXED session k, **no trigger gate at all**,
k ∈ {1, 3}, frozen; same construction and replay. ARM T moves both WHEN and
WHICH; ARM L moves only WHEN. A ΔR that ARM L reproduces is a LAG finding, not a
trigger finding. `emission_timing` ARM L found the book LAG-TOLERANT within three sessions on
v3; this re-runs that control here.

### ARM C — conformity control (CONFOUND)

ARM T's ΔR stratified by **entry-session conformity band**, reusing
`next_day_move.DAY0_PNL_BANDS` and `MIN_CELL_N = 20` **verbatim**, the band read
off `next_day_move.day0_mark_pnl` at the SHIPPED entry session. Any ΔR REMAINING
inside a band is the trigger saying something the day-0 mark had not. **A band
thinner than `MIN_CELL_N` prints its n and is NOT READ**.

### ARM D — deployment read

`protocol.top_k_per_day(..., protocol.ladder_rank, k=3, eligible_fn=…)`, the
shipped top-3/day ladder, runs twice on the SAME book. Book 1 has the shipped picks at
shipped pricing. Book 2 has **NOT-ENTERED rows INELIGIBLE (the slot is freed to
the next-ranked play)** and every entered in-scope row at its trigger fill.
Out-of-scope rows stay eligible at shipped pricing in BOTH books. **R only. No
dollar figure.**

### Frozen grid

| knob | values | may not move |
|---|---|---|
| ARM T window `N` | 1, 3, 5 | frozen |
| ARM L fixed session `k` | 1, 3 | frozen |
| ARM C bands | `next_day_move.DAY0_PNL_BANDS`, `MIN_CELL_N = 20` | imported verbatim |
| ARM D ladder depth | `k = 3` | the shipped card |
| power floor | ≥ 25 dates AND ≥ 60 rows per cell | declared before any count |
| bootstrap | `BOOT_N = 10000`, α = .05 | `protocol` defaults |

### Session numbering

Session **k = 1** is `underlying.entry_day`, which is `t.grid[0]`:
`_weekday_grid` is "weekdays AFTER the signal date", so `marks[0]` is already the
fill session. A crossing at session k fills at `synth_trade(rec, k − 1)`.
Because the WEEKDAY grid and the BAR SERIES can differ by a market holiday, the
module resolves the lag as **the crossing session's own index in the trade's
grid**. That IS `k − 1` whenever `entry_day == grid[0]` and no holiday falls in
the window. **G2 prints how many rows differ.** If a crossing session lies beyond
the end of the trade's grid, it is a construction exclusion, counted, never
silently re-anchored.

## How it is judged

- **Unit = the signal DATE.** Every CI is `protocol.boot_ci_paired_by_date`,
  date-clustered, `BOOT_N = 10000`, α = .05.
- **Metric = R** (credit rows: R on the credit; `harness` denominates on
  `abs(entry_net)`).
- **NO DOLLAR FIGURE IS QUOTED ACROSS ARMS, ANYWHERE.** Contracts are RE-SIZED
  when the entry price moves (keeping the harness `dollar_stop` at the same
  effective R), so dollar totals compare different sizes. G4 makes this
  checkable.
- **No annualised figure, no Sharpe, no time-to-recover.** Worst-decile reads are
  FORBIDDEN as criteria (the 2026-08-13 nine-date decile wall) and not computed.

**Estimands, in order of authority:**

1. **HEADLINE — ARM T:** paired-by-date ΔR on the ENTERED rows, trigger-priced
   versus **the SAME rows' shipped replay** (stored trade, same profile).
2. **CENSUS — E2 shape:** ENTERED vs the full in-scope population at SHIPPED
   pricing, excluded share (rows and dates) beside every number. **NOT A
   CRITERION**, printed for reconciliation only.
   `Resolved at build (2026-09-04):` the census keys on "the trigger was MET",
   not on "ARM T could build a synthetic for it". A row meeting the level at a
   session with an unusable mark (`degenerate_zero_entry`: 13 of 853 on v4 at
   lag 0, 6 at the crossing session) is ENTERED here and a CONSTRUCTION
   exclusion in G2. ARM T's evaluated n prints beside each census row. So the
   N=3 census reproduces E2: **ENTERED 579 rows / 145 dates +0.212 vs NOT
   ENTERED 274 / 121 −0.048 on 853 in-scope rows / 147 dates.**
3. **ARM D deployed ΔR** under the shipped ladder.

## Gates, in order

In order; each blocks everything below it.

- **G0 — POWER.** ≥ 25 affected DATES **and** ≥ 60 affected ROWS per cell, else
  **UNDERPOWERED**: the census prints, no criterion is evaluated, nothing is
  refuted, and the cell is not re-run on these dates.
- **G1 — PARSE CENSUS.** Every exclusion bucket with its n and share of the
  admitted book, the conditional-trigger count and the SRC split. A
  prompt-robustness finding in its own right, published whatever happens.
- **G2 — CONSTRUCTION (G-SYNTH).** `synth_trade(rec, 0)` must reproduce the
  stored trade in `signal_date`, `dte_entry`, grid and mark path, differing ONLY
  in fill price and contract count. **Any `Trade` construction failure FAILS THE
  RUN.** The padded-row count and grid/session reconciliation count print.
  `Resolved at build (2026-09-04):`
  - A row with no usable day-0 mark (absent or a degenerate `0.00`) is a COUNTED
    G2 exclusion with its reason, not a G-SYNTH failure and never a pass. "Fails
    the run" binds on a row `synth_trade` tried to BUILD and could not. G-SYNTH
    is asserted on the rows that build.
  - The abort raises inside the IMPORTED `emission_timing.synth_trade`, whose
    message says "G1" (ITS gate number). It is this study's G2; the report notes
    this.
  - `first_cross` is asserted equal to `trigger_met` on every in-scope row ×
    every N. A single disagreement FAILS THE RUN.
- **G3 — LEAK GUARD.** Every row OUTSIDE the in-scope population must come back
  byte-identical to its shipped replay on `(exit_reason, days_held, round(pnl,
  10))`. The keying is evaluated INSIDE the outcome function, handed the whole
  admitted book (a pre-filtered list would make the gate vacuous). One changed
  row fails the run.
- **G4 — SIZING CENSUS.** Contract distribution per k against the stored count,
  printed beside the "no dollar figure across arms" statement.
- **G5 — DEADLINE DIAGNOSTIC.** The time exit recomputes from the NEW entry
  anchor, as production does (`scripts/journal/lib/exit_rules.py`). The
  absolute-from-signal alternative is a **printed diagnostic, not a second
  grid**: the report counts ARM T `time_exit` rows that would exit on a
  different session under it.

## Bar for a candidate

Per ARM T cell, all eight; failing any one is failing.

1. The paired date-clustered CI **excludes zero** (`BOOT_N = 10000`, α = .05).
2. **Every** LOO-by-date fold is on the point estimate's side
   (`protocol.loo_by_date`, read `min_gain`).
3. It survives `protocol.window_cuts` **AND the ex-BOTH cut added BY HAND**.
4. **Sign-stable per calendar year** (`protocol.sign_stable`). **DISCLOSED: with
   no 2026 dates on v4 this spans 2024/2025 only, and the report says so.**
5. Right-signed on **BOTH pricing tiers** (real and tweak).
   `Resolved at build (2026-09-04):` evaluated on the tiers PRESENT in a cell; a
   one-tier cell is graded on that tier, as `exit_from_text.evaluate_cell` does.
6. The floor re-checked on the EVALUATED set (≥ 25 dates, ≥ 60 rows).
7. **No sign flip across N ∈ {1, 3, 5}.** A knob artifact fails whatever its CI.
8. **ARM C:** the ΔR is right-signed in every `DAY0_PNL_BANDS` band holding ≥
   `MIN_CELL_N` entered rows. If NO band clears `MIN_CELL_N`, criterion 8 FAILS.

**L-SEP, the separation test** (used by the verdicts, not a ninth criterion).
ARM T at N **separates** from ARM L at the matched k when ARM T's ΔR exceeds ARM
L's ΔR at that k **and** ARM L's own ΔR does not itself clear criterion 1 in the
same direction. The **matched k** is `min(N, 3)`: N=1 → k=1, N=3 → k=3, N=5 →
k=3, the deepest registered lag. Both numbers print beside every ARM T cell.

## Verdicts, worded now

Per ARM T cell, **exactly one**, in this ORDER; first match wins. The grammar is
EXHAUSTIVE: no cell may be given a word that is not on this list.
The **criteria vector prints under every verdict**.

| # | Verdict | Condition and consequence |
|---|---|---|
| 1 | **UNDERPOWERED** | A floor was not met. Census published, nothing read, no re-run on these dates |
| 2 | **LATE-ENTRY** | ΔR ≤ 0 **and** the E2-shape census reproduces at shipped pricing on this N (ENTERED mean R above the in-scope mean R). The trigger sorts winners from losers, but the confirmed entry comes AFTER the move it selects on, so the confirmation costs at least as much as it is worth. The registered null-with-a-mechanism; it closes E2 as a shippable intake rule |
| 3 | **CONTRARY** | Criterion 1 holds with ΔR < 0 and the census does NOT reproduce: the trigger misleads. Fed to the PROMPT-ROBUSTNESS list |
| 4 | **CONFOUND-EXPLAINED** | ΔR > 0, criteria 1–7 hold, criterion 8 fails: the gain lives outside the conformity bands, i.e. it is the day-0 move `next_day_move` ARM C already owns |
| 5 | **LAG-EXPLAINED** | ΔR > 0, all eight hold, **L-SEP fails**: ARM L reproduces the effect without any gate, so this is about WHEN, not WHICH |
| 6 | **CANDIDATE** | All eight hold **and** L-SEP holds |
| 7 | **NULL** | Powered, nothing above matched. Recorded |

`LATE-ENTRY` replaced the label `PRICED-AWAY` on 2026-09-04, after the first run;
its definition is unchanged. The operator read "priced-away" as ambiguous
between "the edge was arbitraged out" and "the entry is late"; the registered
condition is the second. No gate, bar, arm, or verdict CONDITION changed.
Study-results sections recorded before the rename keep the old word.

ARM L, ARM C and ARM D carry **no verdict word of their own**. ARM L and ARM C feed criteria 8 and L-SEP;
ARM D prints its
ΔR and CI as a READ. The E2-shape census carries no verdict.

## Anti-tuning

The grid is frozen and **every cell is reported regardless of outcome**. Nothing
is added, moved, or dropped after a number is seen. Exit profiles, sizing,
structure universe, entry side, ladder depth and candidate population are NOT
swept. The study is **read-only and touches no config**. Structure × `mech_cell`
cells are NOT registered and not computed.

## What could ship

A `CANDIDATE` is **an INTAKE proposal, never an exit rule and never a ship**. It
becomes a written proposal with its own rollback trigger and an
independent-window confirmation before it may reach `docs/deployment-rules.md`.
