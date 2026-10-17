## exit_drawdown — walk-forward exit hypotheses judged on account-level drawdown

<!-- outcome:start -->
> Latest outcome: `ARM U/a` and `ARM U/b` `REACTIVE-AGAIN`; `ARM O/vol` `NULL`; `ARM D` `SECONDARY-NULL`; `ARM W`, `ARM O/oi` and `ARM P` `UNDERPOWERED` — 2026-09-28 · [record](../../study-results/f2_management/exit_drawdown.md).
<!-- outcome:end -->

_Registered 2026-09-05._

## The question

Does any exit rule, chosen without look-ahead, reduce the **account-level
[mark-to-market](../../glossary.md#mark-to-market-basis) drawdown** of the
deployed book, without giving back its edge?

This is an f2 MANAGEMENT study. The signal, the entry day, the structure, the
ladder pick order and the base sizing are frozen. An arm changes only what
happens to an ALREADY-OPEN position; ARM D alone changes the size of a NEW one.
Every threshold is chosen OUT OF SAMPLE, on training dates only. The headline is
read off the stitched out-of-sample book.

The operator's queued question is "MAX DRAWDOWN, not timing". `account_sim`
deploys the ladder through a \$25,000 ledger; `lib/mtm_curve.py` marks the same
book to market. No study has yet judged an exit rule on that curve, and no exit
knob here has ever been chosen out of sample. All pt/sl/tef tuning to date was
full-window and in-sample, and `protocol.walk_forward_splits` (purged,
expanding, 120-day embargo) has never been pointed at the exit grid. No
underlying-price stop for DEBITS was ever tried, only for credits. Yet
`bear_giveback` located the give-back pattern in the UNDERLYING rather than in
the mark. No study has read the OI PATH
in `backtests/option_history_cache/`, or measured partial scale-out.

### Why this is admissible after the standing nulls

Every standing null below was reached on a per-row R estimand, with parameters
chosen IN-SAMPLE. Here the outcome is the dollar max drawdown of one MARKED
\$25,000 ledger, which a rule can change without moving mean R; `hedge_portfolio`
ARM M found the close-bucketed curve UNDERSTATES it by 40.2%. And every
threshold is fitted on TRAIN dates and judged on TEST dates. Neither difference
exempts an arm from the reactive diagnostic: a rule that cuts drawdown by selling
continuations has re-found the reactive null, so that diagnostic is a PASS
CRITERION (`REACTIVE-AGAIN`, clause 7), as `staged_exit` registered its G2.

## What this study is not

**It is not a hedging study.** It opens, sizes and times no sleeve, and says
nothing about §2.1's instrument question.

**It re-tests no settled exit family.** Each is a STANDING NULL or settled rule. Each is named so a reader can check that
no arm smuggles one back in.

| Family already settled | Standing verdict |
|---|---|
| Mark-based trailing stops (Attempts 1 / 2 / 10) and loss-days | REJECTED — the "reactive null" (21 of 21 debit trail exits sold continuations) |
| The pt/sl/tef grid on debits | PROD `pt .90 / sl .75 / tef .75` is the IN-SAMPLE plateau (LOO); reactive null re-appeared 2026-09-04 |
| Credit profile `pt .65 / sl null` | SHIPPED (Attempt 13); rollback trigger UNDERPOWERED (0/15) |
| Time-staged day-X ± Y% switch (`staged_exit`) | NULL (0/40 powered; 50–79% continuation sales) |
| Model-text stops (`exit_from_text`) | CONTRARY on `bull_call`/LVOL, NULL elsewhere |
| Day-0 underlying move cuts (`next_day_move`) | NULL |
| Bear-debit `be_after 0.50` | SHIPPED 2026-08-11 → REVERTED 2026-08-24 |
| Per-regime exit switch (mech `BEAR_HE` trail / LVOL tef-null) | STAYS GATED |
| Credit underlying short-strike breach (Attempts 9 / 11) | NOT VALIDATED (n-of-1 TSLA); RETIRED |
| Signal-date volume conditioning (`volume_signal`) | NULL |
| The operator's queued max-drawdown question (memory 2026-08-28, §2.1) | Open; no sleeve policy touches it — every hedge TRIGGER dead, the hedge INSTRUMENT unmeasured |

Sources: `archive/01–02`, `exit_mechanism_study`, `next-steps.md` §2.4, §2.6,
§2.7, §2.8, §3; `exit_switch_*`.

**The standing rules in [`../../next-steps.md`](../../next-steps.md) §3 bind
this study.** In particular:

- **The day-X / ±Y% / ±\$Z exit formula is `staged_exit`, and it is null.** No
  arm is anchored on a session index or a P&L band at one, under any anchor
  (days-since-entry, DTE-remaining). ARM U triggers on the UNDERLYING's ATR
  distance from the entry close, ARM O on the contract's open-interest path, and
  ARM P has no trigger.
- **Trigger-gated ENTRY is LATE-ENTRY** (`trigger_entry`, v4 + v3); no arm moves
  an entry.
- **No further text study**: no arm reads model prose, an invalidation line, a
  trigger line or a horizon.
- **`score_total` is decision-irrelevant**; no arm re-cuts selection, and nothing here proposes a new selection clause.
- **`bear_call_spread` is intake-vetoed; bear debit is selection-vetoed at card
  §1.4** and lives in the §4 hedge sleeve. The study inherits `account_sim`'s
  admissions unchanged.
- **`exit_basis` is never read to ask whether a row REPLAYS**;
  `lib/replay_basis.py` answers that.
- **ARM labels are study-local**: cite `exit_drawdown ARM W`, never a bare
  `ARM W`.
- **Never read silence as "the trigger was not met"**, and **never hardcode a
  figure off one export**, report prose included. Every count is
  `len(records)` after filters at run time.

## Population and basis, fixed here

| Fixed | Value |
|---|---|
| Era | PRIMARY `--era current` (v4, the 166-date book, the first with 2026 signal dates). SECONDARY `--era v3` (795 rows / 118 dates) is RUN and REPORTED, carries no verdict of its own. **Never pooled.** ERA-scoped through `lib/era.py`; the report header names the era |
| Book | `load_book(include_bs=False)`: `real` and `strike_expiry_tweak` tiers only (`include_bs=False`), proxy CALIBRATION GATE ON |
| Deployment population | PRIMARY: `account_sim`'s `dense_episodes` ([dense episodes](../../glossary.md#primary-dense-episodes-vs-secondary-full-book)). `all` is a DISCLOSED SECONDARY CUT printed beside it; no verdict is read from it. (FEASIBLE is a two-year, dense-episode claim) |
| Baseline | ALWAYS the **SHIPPED** profile as `account_sim.profile_for` resolves it per row ([§5](../../../docs/deployment-rules.md#s5)), bear-keyed variants included. **Never** a clean `DEBIT_PROD` |
| Credit rows | Keep `CREDIT_PROD` in every arm, so the ledger is the real book; no credit exit is tested |
| Entry basis | Next-open; the entry session is `t.grid[0]` |
| Row exclusions | Counted per arm and printed before any conditional number (G-COV) |

### No-lookahead rules, binding

A violation of any of these invalidates the run. G1 checks them mechanically.

**Splits.** Thresholds are chosen per
[walk-forward](../../glossary.md#purged-walk-forward--embargo) block on TRAIN
dates only, from
`walk_forward_splits(dates, block=15, embargo_days=P.PATH_CAP_DAYS (=120), min_train_dates=40)`,
and applied to that block's TEST dates.

**The fit has two stages per block.**

1. Prefilter: each configuration's TRAIN mean R via memoised `replay_sized`;
   keep those within **0.02** of the best.
2. Among survivors, `simulate()` on the TRAIN `day_lists` only; the **smallest
   TRAIN MTM max drawdown** (`book_curves` → `path_stats`) wins.

**The tie order is TOTAL and fixed per arm:**

| Step | Break to | Live where |
|---|---|---|
| (i) | **PROD** | ARM W only; INERT for every other arm |
| (ii) | **fewer active rules** | every arm |
| (iii) | the overlay that **FIRES ON THE FEWEST TRAIN ROWS** | every arm |
| (iv) | the **LARGEST** parameter value (largest `k`, `X`, `d`) | every arm |

Steps (iii) and (iv) are **registration-time additions**, new binding content
flagged for the operator's review. The plan's rule ("tie → PROD, then fewer
active rules") is not total for arms without a PROD point. Nothing here is
decided at build time.

**ARM U's, ARM O's and ARM D's grids contain NO "off" / no-overlay point.** The
arm-versus-SHIPPED comparison answers whether doing nothing is better. A block
where no configuration beats doing nothing still dispatches one, which surfaces
as a failed clause 1 or as `CONTRARY`.

**One stitched book.** Each era-run uses one shared `account_sim.new_cache()`. A
`date → block` map dispatches each position's configuration inside **ONE
stitched OOS `simulate()`**: the headline book.

**Burn-in is EXCLUDED and reported.** Dates before the first TEST block are
excluded from the headline, with a burn-in census (dates, rows, span) on its own
line. They are **never** replayed under the shipped profile and folded in. The
OOS population is exactly the union of the blocks' TEST dates.

**In-sample bests carry NO verdict.** They print under a `DISCLOSURE, in-sample`
header; no clause is evaluated on them.

**Information set.** An exit decided at the close of session `d` may read spread
marks, underlying bars and option `Volume` ≤ `d`, and option `Open Int` ≤ `d−1`
(Barchart publishes OI the next morning).

**ARM D reads only the ledger's MARKED equity as of the session's OPEN**, with
exits processed before entries, as `simulate` already orders the day.

## Plan-time observations, disclosed

Measured while the study was designed, before any arm ran. No number here is a
result.

**The yardstick.** `account_sim`'s per-era record
([`../../study-results/f4_deployment/account_sim.md`](../../study-results/f4_deployment/account_sim.md))
carries `>>> FEASIBLE <<<` on the PRIMARY dense-episode population, for era
**v4** on the exports dated **2026-09-04 20:31** (inputs `1b1ba3c`, sha
`b007f95`, recorded 2026-09-04):

```
n=148  dates=76  $22,217  meanR +0.348
maxDD $-3,750        worst session $-2,796
```

The drawdown is 15.0% of the \$25,000 capital. The arm-versus-shipped comparison
is computed inside each run, never against these constants.

- The SECONDARY full book on that export FAILS A1 on 2026, and its A3 drawdown
  is 35.7% of capital; nothing in FEASIBLE has seen 2026.

  ```
  n=260  dates=129  $21,855  meanR +0.231   maxDD $-8,920
  ```

- `account_sim`'s `print_equity` states **open positions are not marked to
  market**. This study reads the deeper `lib/mtm_curve.py` curve.

**Coverage: ESTIMATES, replaced by the run's census.** These are plan-time
counts of files on disk; no clause is evaluated against them.

- `backtests/underlying_ohlc_cache/` holds bars for an ESTIMATED **105
  tickers**; book coverage is printed by G-COV. Gaps are filled BEFORE the run by
  `scripts/collector/fetch_underlying_ohlc.py --tickers … --skip-existing`,
  never imputed.
- `backtests/option_history_cache/` carries per-session `Open Int` and `Volume`;
  the usable-OI-path share is an ESTIMATE of "most", NOT quantified; G-COV
  prints it.
- **Pre-run expectation: the modal outcome is UNDERPOWERED cells**
  (`staged_exit` had 0/40 powered cells on a comparable book).

## What it compares

Five arms, frozen; no arm is added after the first run.

| Arm | What it does | Fitted | Kind |
|---|---|---|---|
| [exit_drawdown ARM W](../../arm-index.md#exit_drawdown-arm-w) | Re-picks `pt`/`sl`/`tef` from a 36-point grid; [PROD](../../glossary.md#prod) is one point | the grid | exit arm, honesty baseline |
| [exit_drawdown ARM U](../../arm-index.md#exit_drawdown-arm-u) | Underlying ATR stop from the entry close; (a) added to `sl .75`, (b) replaces `sl` | `k ∈ {1.5, 2.0, 3.0}` | exit arm |
| [exit_drawdown ARM O](../../arm-index.md#exit_drawdown-arm-o) | Flow unwind: OI drop, or volume climax | `X ∈ {0.25, 0.40}`, OI drop only | exit arm |
| [exit_drawdown ARM P](../../arm-index.md#exit_drawdown-arm-p) | Half exits at `pt .90`, half runs with `pt=None` | nothing | exit arm |
| [exit_drawdown ARM D](../../arm-index.md#exit_drawdown-arm-d) | Half risk budget for new positions while marked equity is in drawdown | `d ∈ {0.05, 0.10}` | SECONDARY (sizing, not exit) |

**The four exit arms touch DEBIT ROWS ONLY.** CREDIT rows keep `CREDIT_PROD`:
no ARM W configuration is applied to a credit spread, ARM O never reads a credit
short leg, and ARM P never splits a credit row. The "(debit verticals only)"
qualifier on ARM O's and ARM P's titles is a CLARIFYING addition at registration
time, not a change of scope.

### ARM W — walk-forward knob control

Grid: `pt ∈ {.60, .75, .90, 1.10}` × `sl ∈ {.50, .75, off}` × `tef ∈ {.60, .75, off}`.
That is **36 configurations, of which PROD is one grid point**, so tie step (i)
is live for this arm alone. ARM W reports BOTH "WF-selected vs PROD" and "PROD
itself", to separate selection from the rule under test.

### ARM U — underlying ATR stop (debit verticals only)

**The rule.** Exit at the CLOSE of the first session where the underlying close
is against the position by **≥ k · ATR14**, measured from the **ENTRY-session
close**. In variant **(a)** the ATR stop is ADDED to `sl .75`; in variant
**(b)** it REPLACES `sl`. Direction comes from the structure (`bull_*` vs
`bear_*`).

**ATR14 is FROZEN AT ENTRY.** It is `underlying_features.atr14_pct`, a **simple
14-session mean of true range, NOT Wilder-smoothed**, times the entry close; it
is not re-implemented. The trigger cannot re-arm on a new peak, which is what
distinguishes it from the rejected trails.

**Exclusions, counted:**

| EXCLUDED and counted | Why |
|---|---|
| `atr14_pct` is `None` | below its minimum observation count |
| rows priced on the close-only `Price~` fallback | no true range |

Split-rescaled tickers are fine. **A missing bar on a grid day is "unpriced,
skip", never a zero move**; `t.grid` is a WEEKDAY grid.

### ARM O — flow-unwind exit (debit verticals only)

| Variant | Exits when |
|---|---|
| OI drop | the lagged OI ≤ (1 − X) · `OI_max`, `X ∈ {0.25, 0.40}` |
| volume climax | leg volume(`d`) ≥ 3× its post-entry median AND the mark closed against the position |

There is exactly **One volume variant**.

- "The entry LONG leg" means the long leg of a DEBIT vertical. `OI_max` is the
  RUNNING MAX of its `Open Int` since entry, read **LAGGED one session**: the
  value usable at `grid[i-1]` is the one dated `grid[i-2]`.
- A new reader `load_oi(leg)`, modelled on `harness.Trade._load_underlying`,
  reads `Open Int` through `lib.parsing.to_float`.
- **The volume median is EXPANDING and as-of `d`**: sessions **up to AND
  INCLUDING `d`**, never the whole hold. Same-session `Volume` IS admissible.
- **Blank OI is MISSING; OI literally 0 is a VALID full unwind.**
- If a row has blank OI on **≥ 20% of its hold sessions, it is EXCLUDED and
  counted**. A missing OI value on a grid day is skipped, never read as a 100%
  drop.
- A missing volume is SKIPPED, never zero. A session whose window has too few
  observed volumes to form a median cannot fire.

### ARM P — partial scale-out (debit verticals only)

**The rule.** Half the contracts exit at `pt .90` as shipped; the other half
replays the shipped profile with `pt=None`. It is modelled as **TWO synthetic
`Pos` per rec**, each with its own exit session, and the ledger releases half the
reserve at the FIRST exit.

**`Resolved at build (2026-09-05):` (a) the ledger holds the WHOLE reserve until
the LATER half exits.** `account_sim.simulate()` holds one exit session per
position and is not forked, so the LEDGER-facing blend (`partial_replayer`)
reports `days_held` as the LATER half's. This is CONSERVATIVE: it can only admit
FEWER later positions. The CURVE keeps the registered shape via
`split_positions()` before `book_curves`. ARM P's census prints the deviation.

**Odd counts.** "Half the contracts" splits a DEBIT vertical's position. The
`pt .90` half takes `⌈n/2⌉`, the `pt=None` half `⌊n/2⌋`. A position of
**`n = 1` cannot be split**, so **n = 1 rows are EXCLUDED from ARM P and
counted** (census and G-COV). Both rules are NOT plan text, which says only "half
the contracts"; they were fixed HERE, before the run, as new binding content for
the operator's review.

**Units.** Paired R = the mean of the two halves. ARM P's per-row and paired
numbers are quoted in R, not dollars. Its account-level drawdown co-primary is
reported in dollars like every arm's, with the non-comparability stated beside
it. This scopes the plan's "Traps to encode" line ("Quote R, not dollars, for
ARM P (contracts change)") against "Unit and metric" ("for every arm and cell").
The phase-1 instruction ("approving this plan IS the operator's review of the
commitments; the agent transcribes, it does not redesign") reserved that choice
for the operator.

**STATUS: ACK RECORDED 2026-09-08 — the SCOPED reading is in force.** The
operator chose dollars. This closes build reading (c):
`Resolved at build (2026-09-05):` (c) had made share-of-capital the default.

| Period | What the module prints for ARM P |
|---|---|
| After the ACK (now) | Drawdown, improvement and its CI bounds in dollars; `--arm-p-share` prints them as a share of starting capital |
| 2026-09-05 build until the ACK | The ALTERNATIVE reading: those three as a SHARE OF STARTING CAPITAL behind a banner naming the open item; `--arm-p-dollars` (since removed) printed dollars; the CI is the improvement's block-bootstrap CI |

Clause 1 reads the scale-free improvement RATIO, so the ACK settled the
PRESENTATION only.

### ARM D — drawdown throttle (SECONDARY; sizing, not exit)

**The rule.** In `simulate`, when marked equity ≤ (1 − d) · running peak, new
positions size at **half** the risk budget until equity ≥ (1 − d/2) · peak.
`d ∈ {0.05, 0.10}`, chosen walk-forward, read from marked equity at the open.

**Its limits.** ARM D is **labelled SECONDARY everywhere it is printed** and
**can never ship from this study**. The most a `SECONDARY-CANDIDATE` can do is
queue an f4 registration.

**One collapsed value.** `Cfg.dd_throttle` is ONE value per simulation, so ARM
D's per-block choices collapse to one. This EXCEPTION is ARM D's alone.

**`Resolved at build (2026-09-05):` (f) the collapse is to the EARLIEST block's
choice.** It uses nothing after its own TRAIN window, so the book stays out of
sample; block indices are unique, so no tie. `collapse_choice()` (called by
`run_book()`) holds the rule. The report prints the per-block table, the
collapsed value, and **every grid value's own stitched OOS book**. Superseded:
"A superseded reading", build reading (b), collapsed to the MODAL choice ("a
property of the ledger, not a tuning choice"). It is SUPERSEDED and not live: WHICH value
the collapse lands on is a choice, and the modal one is LOOKAHEAD.

**What "affected" means for ARM D, and for ARM D only.** G0 and the verdict grammar
speak of an arm CHANGING A ROW'S EXIT, so G0's general definition ("the arm
changed that row's exit") is EMPTY for a sizing rule:

| Term | ARM D's definition |
|---|---|
| affected ROW | a position ENTERED while the throttle was ACTIVE, i.e. sized at HALF the risk budget. Not a position entered at the full budget, nor one merely HELD through a throttled stretch |
| affected DATE | a signal date on which at least one affected row was entered |

G0's floors (**≥ 25 affected DATES and ≥ 60 affected ROWS**) and clause 6 use
these counts. **No other arm may use this definition.**

**CONT (clause 7) is DROPPED; ARM D's conjunction is clauses 1–6.** For it
"the arm's exits" has no referent; its continuation rate would be the
baseline's by construction.

These three rules (SIZING "affected", the CONT drop, the `SECONDARY-` tokens)
are **NOT plan text**, which says only that ARM D is "reported beside the exit
arms only … Can never ship from this study" and gives no ARM-D token
vocabulary. They were fixed HERE, before the
run, as **new binding content, flagged as such for the operator's review**, and
ARM D's counts print in G-COV.

## How it is judged

**Unit = the signal DATE.** Every confidence interval is date-clustered.

**A CELL is one arm × variant × era × deployment population.** G0 powers it,
every clause reads it, and it gets exactly one token.

| Arm | Variants |
|---|---|
| ARM U | added to `sl .75`; replacing `sl` |
| ARM O | OI drop; volume climax |
| ARM W, ARM P, ARM D | one each |

Walk-forward-SELECTED parameters (`pt`/`sl`/`tef`, `k`, `X`, `d`) are NOT cell
axes; the report names the per-block selections (and ARM D's collapsed value).

**Co-primaries**, for every arm and cell (ARM P's co-primary 1 in dollars, per
ARM P's STATUS):

1. **MTM max drawdown, in DOLLARS, of the OOS-stitched deployment**:
   `book_curves(target=TARGET_POSITION)` → `path_stats`, with **Ulcer index**
   and **time-under-water** beside it.
2. **Paired [ΔR](../../glossary.md#r) by DATE versus the shipped profile**:
   `boot_ci_paired_by_date`.

The drawdown-improvement CI uses the block-bootstrap `improvement()` pattern
from `hedge_portfolio`. **Never annualised. No Sharpe. No time-to-recover.**

## Gates

Every gate is evaluated and printed. The machinery gates (G-FORK, G-CAL, G-MTM,
G1, G-COV) are RUN-LEVEL: if one fails, the run stops non-zero and **no verdict
is read for any arm**.

- **G0 — POWER. Runs first and blocks every clause.** Per (arm × cell): **≥ 25
  affected DATES and ≥ 60 affected ROWS**. **"Affected" means the arm changed
  that row's exit** (ARM D: its own SIZING definition). Below either floor the
  cell is UNDERPOWERED: census printed, no clause evaluated. Counts come from
  `len(records)` at run time. Both floors are measured on the **OOS-STITCHED
  EVALUATED POPULATION** (TEST dates, AFTER burn-in and the arm's data
  exclusions), never on a pre-burn-in or full-book population.
- **G-FORK — composition, not a fork.** Every overlay with its rule DISABLED
  reproduces `harness.replay` EXACTLY, on ALL rows, in BOTH eras.
  `lib/harness.py` is FROZEN. One disagreement fails the run.
- **G-CAL — the host is unchanged.** `account_sim`'s gates **G2–G5** pass with
  the DEFAULT replayer (`account_sim --selftest-gates`); the replayer hook is a
  no-op when unused.
  - **`Resolved at build (2026-09-05):` (h) the parenthetical names the
    SELF-TEST, the opposite of the check.** `--selftest-gates` INVERTS every
    gate (it adds 1 to `days_held` in G2, a \$1 leak into G3, and inverts G4 and
    G5), so a healthy build prints `GATES: FAILED`; it tests the CHECKER, and a
    run that PASSED would mean broken gates. The gate is read as
    **`account_sim.run_gates` on its DEFAULT path, on this study's population,
    IN THIS PROCESS, with per-gate PASS/FAIL lines in this report**. A failure
    fails G-CAL as a `book_signature` mismatch does. `run_gates` is CALLED,
    never copied. **The printing requirement is this reading's addition**: a run
    "outside this process" ASSERTED a gate it did not carry.
- **G-MTM — curve and ledger agree.** The mark at exit equals the overlay's
  dollars for that position, within `TOL_DOLLARS`.
- **G1 — LEAK GUARD.** Shift every auxiliary series (bars, OI, volume) ONE
  SESSION FORWARD. Assert that **at least one exit changes** AND **no exit moves
  EARLIER**.
  - **`Resolved at build (2026-09-05):` reading 1 — "ONE SESSION FORWARD" is one
    session of the RULE'S OWN GRID, not one row of the cached file.** An
    option-history or OHLC file holds off-grid dates, so a file-order shift is
    not "one session later". On `t.grid`, session `i` carries session `i-1`'s
    value, MISSING stays MISSING, off-grid keys are untouched. Build evidence,
    not a result: a file-order shift gives **57** spurious "moved earlier" rows
    on v4 PRIMARY, the grid shift zero. ARM U holds bars `<= entry` fixed, so the
    frozen ATR14 SCALAR is not re-estimated.
  - **`Resolved at build (2026-09-05):` reading 2 ("correction 2") — the
    DIRECTION half is read on ARM O's volume LEG, not its conjunction.** Shifting
    only volume RE-PAIRS it with the unshifted mark, which can fire earlier
    without any leak. The conjunction's earlier-firings are PRINTED as a
    non-gating count. A coherence check (the conjunction fires at or after its
    volume leg) FAILS G1 if non-zero. **This SCOPING is outcome-bearing**: read
    literally, it was a (V0) failure. The ATR stop and OI unwind are gated on
    both halves as registered.
  - **`Resolved at build (2026-09-05):` (e) the "at least one exit CHANGED" half
    is tallied PER VARIANT**, so a never-read series cannot hide behind one that
    changes. Each EXERCISED variant must change a firing session, through the
    SAME loaders the arms use; a variant with no rows prints NOT EXERCISED.
    **This is STRICTER than the registered gate**, and was decided at build.
- **G-COV — COVERAGE, printed BEFORE any conditional number.** Per arm: bar
  coverage (tickers with and without a series; `Price~` close-only drops; `None`
  `atr14_pct` drops); OI coverage (entry legs with a usable path; ≥20%-blank
  drops); ARM P's `n = 1` exclusions. A conditional figure above its coverage
  line is a reporting defect.

## Bar for a candidate

A candidate must clear the WHOLE conjunction, on the **PRIMARY** population, on
the **OOS-stitched** book. ARM D is judged on clauses 1–6 only.

1. **Max drawdown improves** by **≥ 15%** versus the shipped profile, with the
   block-bootstrap CI **excluding zero**.
2. **Paired ΔR non-inferiority:** the date-clustered CI's LOWER BOUND is
   **> −0.02**.
3. **Stability over time:** **same-signed in both halves** of the window **and
   in ≥ 2 of the 3 years** present.
4. **Stability across pricing tiers:** **Both pricing tiers same-signed**
   (`real` and `strike_expiry_tweak`).
5. **Corroboration:** **SECONDARY v3 is not opposite-signed**.
6. **Dates:** **≥ 25 affected DATES**, G0's date floor RESTATED.
7. **Not reactive:** **fewer than 50%** of the arm's exits are followed by the
   mark recovering past the exit (the `staged_exit` G2 diagnostic).

### Edge cases

**Clause 3, denominator.** "The window" and "the years present" mean the
OOS-STITCHED evaluated set, never the full era book. If that set spans only two
calendar years, all years present must be same-signed. The report prints its
per-year date counts.

**Clause 3, halves.** The window splits CHRONOLOGICALLY at the median evaluated
date. If a half has **NO SIGN** (no affected dates), it cannot be SAME-SIGNED: the cell fails clause 3 and
is `NULL` under (V5), unless already `UNDERPOWERED`. A signless half is never
read as agreeing or dropped.

**Clause 3, no thinness floor.** There is **NO minimum affected-date count for a
half**, and none may be applied at run time. The report PRINTS each half's
affected-date and affected-row counts as a **DISCLOSED, NON-GATING
observation**. A floor, if wanted, is registered separately before any number from this
run is seen, and binds a later run — never this one.

**Clause 4, signless tier.** `Resolved at build (2026-09-05):` (g). A tier with
no positions in one book has no sign, CANNOT be same-signed, and the clause is
NOT cleared: the PRIMARY population must agree with ITSELF across its own
rows. The reading prints on every cell's clause-4 line.

**Clause 5, signless v3 cell.** The plan says only "SECONDARY v3 not
opposite-signed"; this reading was fixed before the build. v3 is a SEPARATELY
POWERED population (795 rows / 118 dates). A v3 cell that is UNDERPOWERED or has
no affected dates has no sign, so it is **not opposite-signed** and clause 5
PASSES VACUOUSLY: as CORROBORATION, a silent population cannot CONTRADICT the
primary. The report prints `clause 5: VACUOUS (v3 cell UNDERPOWERED / no
affected dates)` with the v3 census. A `CANDIDATE-FOR-INDEPENDENT-WINDOW` resting
on it carries that annotation into the write-up.

**Clause 5, sidecar.** `Resolved at build (2026-09-05):` (d). Each era-run
records its cells (verdict, improvement ratio, power) in a per-era sidecar under
`backtests/study_output/` and reads the SECONDARY era's.

- The sidecar names BOTH its era and its population; only the PRIMARY cut writes
  one. A sidecar naming another era, another population, or none is REFUSED.
- An unrecorded or refused v3 sidecar makes clause 5 VACUOUS, with the reason
  printed. **Note the widening**: this extends the vacuous case beyond a v3 cell
  that RAN with no sign.
- A recorded, POWERED, opposite-signed v3 PRIMARY cell FAILS the clause.
- The no-OOS path records its cells BEFORE returning: an all-UNDERPOWERED
  sidecar, never none.

**Clause 5, referent.** `Resolved at build (2026-09-05):` (i). "The referent is
the SECONDARY era's PRIMARY cell", never its `all` cut, which carries no verdict
(VERDICT-AFFECTING).

**Clause 6** is a RESTATEMENT of G0's date floor on the same set; G0's **≥ 60
affected-ROW floor binds on that set** too.

## Verdicts, worded now

The grammar is **TOTAL**: in this order, first match wins. For an evaluated
cell: **DD** = clause 1; **R** = clause 2; **STAB** = clauses 3, 4, 5;
**DATES** = clause 6; **CONT** = clause 7. ARM D: see "ARM D's tokens".

| Order | Token | When |
|---|---|---|
| (V0) | Machinery — **NO token is emitted for any arm** | Any of G-FORK, G-CAL, G-MTM, G1, G-COV fails; the run stops non-zero |
| (V1) | `UNDERPOWERED` | G0 fails on the evaluated set (< 25 affected dates OR < 60 affected rows), equivalently clause 6. Census printed, no re-run on these dates. ("POWER-STOPPED" in older reports reads as UNDERPOWERED) |
| (V2) | `CONTRARY` | Powered, and the arm is signed AGAINST itself beyond noise: drawdown WORSENS by ≥ 15% with the bootstrap CI excluding zero, **or** the paired ΔR CI lies ENTIRELY at or below −0.02 |
| (V3) | `REACTIVE-AGAIN` | Powered, not CONTRARY, **clears R** (ΔR CI lower bound > −0.02), **fails CONT** (≥ 50% of exits followed by the mark recovering past the exit), whatever DD and STAB say; the thread is closed for these dates. Pre-run expectation: the outcome the prior evidence predicts |
| (V4) | `CANDIDATE-FOR-INDEPENDENT-WINDOW` | Powered, not CONTRARY, clears **all** of DD, R, STAB, DATES and CONT. A queue, not a ship |
| (V5) | `NULL` | Every remaining evaluated cell: DD fails; STAB fails; R fails without CONTRARY; or CONT fails with R also failed (NOT REACTIVE-AGAIN, which needs R CLEARED) |

### ARM W's control token

ARM W also gets ONE arm-level token, also total:

| Arm-level token | When |
|---|---|
| **`PROD-ROBUST`** | The WF cell is `NULL` or `CONTRARY`: **no walk-forward-selected configuration beat PROD out of sample** |
| `UNDERPOWERED` | The WF cell is UNDERPOWERED; **PROD-ROBUST is NOT claimed** |
| `REACTIVE-AGAIN` | The WF cell is REACTIVE-AGAIN; not PROD-ROBUST |
| `CANDIDATE-FOR-INDEPENDENT-WINDOW` | The WF cell clears the conjunction; PROD-ROBUST is refuted |

### ARM D's tokens

ARM D takes **FOUR** tokens, each with a **`SECONDARY-` prefix**:
`SECONDARY-UNDERPOWERED` (V1), `SECONDARY-CONTRARY` (V2),
`SECONDARY-CANDIDATE-FOR-INDEPENDENT-WINDOW` (V4, on clauses 1–6) and
`SECONDARY-NULL` (V5, the catch-all). **`SECONDARY-REACTIVE-AGAIN` (V3) is never
emitted**: the ladder runs with **V3 SKIPPED** and stays **TOTAL**. No ARM D
token is an exit finding.

## Anti-tuning

- **The grids above are FINAL**: `pt`/`sl`/`tef` 36 configurations; `k` three
  values; `X` two, plus exactly ONE volume variant; ARM U two variants; `d` two
  values; ARM P none.
- **Nothing is added after the first run**; **a failed cell is not re-cut** (no
  sub-population, other window or moved threshold).
- **Every cell is reported regardless of outcome**.
- The train objective, the 0.02 tolerance, the tie order, the block size, the
  embargo and the power floors are fixed by this document.
- **No deviation is silent.** Every build-time deviation is folded into the
  section it amends and printed by the report where it bites. One that changes
  what a gate REFUSES, what an arm DOES, or how a clause is READ also sits beside
  its text under a `Resolved at build (date)` tag. It never relaxes a
  commitment. `scripts/study_review/` grades against THIS FILE
  alone. Each `Resolved at build` tag carries the label (reading 1, reading 2,
  (a)–(i)) the module and gradings cite; (c) is closed by ARM P's STATUS.
- `protocol.walk_forward_splits` (SELECTION) and `year_epoch_split` /
  `sign_stable` (STABILITY cuts) are separate calls, never interchanged.

## What could ship

**Nothing ships from this run.** A `CANDIDATE-FOR-INDEPENDENT-WINDOW` queues a
confirmation on the live 2026-08/09 dates, once their options expire and are
priced. Only then may it be proposed for `docs/deployment-rules.md`. ARM D can
only queue an f4 registration and cannot be cited as an exit result. A
`PROD-ROBUST` outcome RETAINS the shipped profile and records that its knobs
survived out-of-sample selection on these dates.
