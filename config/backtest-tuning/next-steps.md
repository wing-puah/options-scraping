# Next steps — session handoff

Written 2026-08-13 so a fresh session can pick up without re-deriving state.
Read this + the top state-of-play paragraphs of [`current.md`](current.md);
everything here has its evidence trail there or in
[`deployment-evidence.md`](deployment-evidence.md).

## 0. Repo state — READ FIRST

*(Rewritten 2026-08-14. The 08-13 §0 described work that has since merged.)*

Everything through 2026-08-13 is **MERGED to `main`** — method-config audit,
bear_put demotion §1.4, and the `volume_signal` study with its infra and tests
(merges `66cd01a`, `6ce3330`; latest `c5fc85b` adds the study-run chart
re-render and its tests).

Suite state **re-measured 2026-08-14: 1,093 passed, 2 errors in 15.5s.** The 2
errors are the same pre-existing `test_underlying_features.py` beta
`AttributeError: 'function' object has no attribute 'cache_clear'`
(`:211`) — **still open**, now confirmed to survive to 08-14 rather than merely
unverified. (Was 896 passed / 1 skipped on 08-13; `test_live_loop.py` no longer
self-skips here, the IBKR snapshot data is present.)

## 0b. `selection_order` — BUILT, RUN, CLOSED on this book (2026-08-14)

**Done. Verdict POWER-STOPPED. Do not re-run it on these dates.**
`scripts/backtest_study/selection_order.py` exists, all six arms ran, gates
G1–G5 pass, and G0 stopped every arm: each re-ordering changes only 7–14% of
the deployed book, so the best-powered arm reaches **11 affected dates on
PRIMARY** (20 at best on SECONDARY) against the pre-registered floor of **25**. No
arm was confirmed, none refuted, and the O4 band was never drawn. The full
entry is in [`current.md`](current.md); the report is
`backtests/study_output/selection_order-latest.txt`.

What this does and does not settle: `account_sim`'s adverse-ordering read is
**not refuted** — this book cannot adjudicate it. The census texture (the caps
excluding the same picks whatever the order) is the shape of
`CAP-BOUND-NOT-ORDER-BOUND`, but that label requires arms that CLEAR G0, so it
is a **carry-forward, not a verdict**.

Before any re-registration on a larger book, fix the one registration bug the
build exposed: **criterion (4) "positive in all three years" is unsatisfiable on
PRIMARY**, which spans two calendar years. It is implemented as "every year
present positive" with an inline disclosure; the wording, not the
implementation, is what needs correcting.

Optional 30-minute step, both already recorded as follow-ups: close the
`account_sim` verdict-grammar hole (A1 holds / A5-A6 fail matches no label, and
follow-up (1) says fix it before any re-run — four re-runs have happened since;
note SECONDARY now also fails A3 at 25.1% DD), and change ARM H's sizing floor
from `max(1, int(0.5×c))` to skipping when half-size is under one contract.

## 0c. Study suite — 6 FAILING, triaged 2026-08-14, NOTHING FIXED YET

`backtest_study run --all` reports six failures. They are **three unrelated
causes**, not one, and only the first is a real problem:

**(A) The DEBIT_PROD exact-replay gate can never pass again — 3 studies.**
`bear_position_study`, `exit_switch_mech_study`, `exit_switch_structure_study`
(exit 1). The gate demands every real debit row replay bit-exactly under
`DEBIT_PROD` (pt .90 / sl .75 / tef .75, **no trail**). It now gets 289/301
exact, **12 HARD**, replay $22,510.70 vs stored $27,655.70 (**−$5,145.00**, all
of it from those 12 rows).

The 12 are **12/12 mech cell BEAR_HE**, and `trailing_stop` appears in *no other
cell* (BEAR_HE 12, LVOL 0, RB_EVOL 0, unlabelled 0). Every one carries
`created_datetime` after `31cb935` (2026-07-22 21:28) landed — i.e. they were
produced by the **shipped `regime_exit.cells.BEAR_HE` trail**, not by legacy
pre-Attempt-10 drift. (The `be_after` ratchet shipped `470b95f`, 2026-08-12,
*after* the 2026-08-11 15:38 export — which is why the export shows zero
`be_stop` and why that is not evidence against the above.)

Production resolves a per-row effective config (`simulate.py:150-165`,
`base → structure → regime`); the frozen harness takes flat call args and never
sees the signal date (`harness.py:113`, `DEBIT_PROD` at `book.py:113`). **So the
gate asserts a property production stopped having on 2026-07-22, and no future
export can satisfy it** unless the overrides were disabled at simulation time.
`BacktestResults` is append-only with no dedup (`core.py:58`), so a re-run adds
beside the offending rows rather than replacing them.

`exit_switch_mech_study.py:26-28` ("every DEBIT row reproduces DEBIT_PROD
exactly") is now **factually false** and must be corrected in any fix.

The gate is one predicate over one loader, **duplicated verbatim three times** —
fixing `load_debit_trades` fixes all three; fixing only the mech study's print
does not:
- origin: `exit_switch_mech_study.py:245-260` (`_calib` at `:222-228`), print +
  `sys.exit(1)` at `:519-529`
- `bear_position_study.py:136-140` (re-implemented, no detail print)
- `exit_switch_structure_study.py:230-234` (same)

**The asymmetry that decides the fix.** The two exit-switch studies read stored
outcomes *only inside the gate* and re-`replay()` everything they report — their
estimands are clean, they are merely blocked. **`bear_position_study.py:77` reads
`realized_pnl_pct` straight off the row as `R`**, and 9 of the 12 bad rows are
`bear_put_spread`/`long_put`, squarely its population. Its docstring line 13
("R = realized_pnl_pct under PROD") is false for those rows. **That study is
contaminated, not just blocked** — and it feeds `deployment-rules.md`
§"Bear positions — hedge sleeve".

TODO (recommended route — precedent-following, not a new licence):
- [ ] Change `load_debit_trades` (`exit_switch_mech_study.py:245-260`) to tally
      `exact / near / superseded-basis / hard` separately, and `sys.exit(1)`
      only on a *true* hard mismatch (a row the harness cannot price at all).
      Identify superseded-basis by the `exit_basis` column (`simulate.py:107-135`,
      `backtest-reference.md:130`) when present, else mech-cell + `created_datetime`.
      Keep the rows in the book tagged `calibrated=False` and let the variant
      tables re-replay them as they already do. **This is exactly the case
      `book.py:24-51` already argues and `account_sim` already runs on.**
- [ ] Fix `bear_position_study.py:77` to derive `R` from
      `replay(t, **DEBIT_PROD)["pnl_pct"]` instead of the stored column.
- [ ] Correct `exit_switch_mech_study.py:26-28`; restate the `stored` total check
      as "over calibrated rows only"; record the amendment in `current.md`.
- [ ] Do **not** simply drop the 12 rows. They are not a random 6% of BEAR_HE
      (12/203) — they are precisely the rows where the shipped rule changed the
      outcome, i.e. maximum-signal rows in the exact cell under test. Dropping
      them biases the estimate and *would* violate the pre-registration; keeping
      and re-replaying them does not.
- [ ] Alternative held in reserve, deliberately NOT chosen: re-export with
      `regime_exit`/`structure_exit` disabled. Restores the literal frozen basis,
      but yields a book that no longer reflects production, needs a `v5_` tab
      (append-only), and re-simulates ~406 rows against drifted pricing caches —
      big, drift-prone, and its only unique benefit is already achievable per-row
      by re-replaying.

**(B) Two studies point at scratch CSVs that no longer exist — retire them.**
`combined_exit_study` (`:75-76`) and `underlying_exit_study` (`:31-32`) crash on
`FileNotFoundError`. `backtests/*` is gitignored, disposable, periodically
deleted (`.gitignore:15-19`), so these inputs were never recoverable.
**Repointing the constants is NOT a fix** — count rows with `csv.DictReader`, not
`wc -l`; embedded newlines in `daily_price_csv` inflate line counts ~4×:
- `results.csv` is **4 rows on 2 dates** (Attempt 12 ran on 94 real debit + 22
  credit). It is a rolling file every `backtest.py` run stomps
  (`config/backtest.yml:361`).
- `proxy_results.csv` is **15 rows**. `combined_exit_study`'s
  `results_proxy.csv` is an **author transposition that never matched the
  writer** — `config/backtest.yml:374` has said `proxy_results.csv` since that
  block was introduced.
- `v2_results_nocreditdiff.csv` **is** the genuine rename of
  `v2_BacktestResults_nocreditdiff.csv` (66 rows, 12 credit, same window as
  `archive/02-…-attempts-8-12.md:65-68` cites) — but `underlying_exit_study`'s
  *other* input has **0 credit rows** today, so `load_credit_rows` returns `[]`
  and the study emits a degenerate empty report regardless of the rename.

TODO:
- [ ] Mark both **archival/retired** in `scripts/study_map/catalog.py` (a study
      with no catalog entry fails the suite) and stop running them in `--all`.
      Their verdicts are already recorded and their write-ups live in
      `archive/02-credit-debit-split-attempts-8-12.md` (Attempts 8, 9, 12);
      neither is named in `current.md`. `exit_switch_mech_study.py:516-530`
      already carries the equivalent validation against the live book.
- [ ] Do **not** repoint and re-run: numbers off a 4-row wrong-vintage book
      could be mistaken for a fresh confirmation of the "reference" verdict.
- [ ] Porting `combined_exit_study` to `book.py` is possible but is a **design
      decision, not a loader swap** — it imports `Trade`/`replay` from
      `exit_mechanism_study.py:66-145`, a separate older implementation from the
      FROZEN `harness.py` that `book.py` uses (`book.py:104`). Only do this if
      the study is wanted live again.

**(C) `v4_bridge` exit 3 — WORKING AS DESIGNED, no action.** Not a failure.
`_resolve()` (`v4_bridge.py:266-267`) falls back to the bare
`analysis - AnalysisClaude.csv` when the `v3_`/`v4_` names are absent, both
sides resolve to the same file, `detect_era()` (`:133-134`) finds
`score_flow`/`score_dealer` on both, and `:284-289` aborts rather than compare a
book against itself. Matches `pre-registrations/v4_bridge.md`. See §2.2 — the
runner should stop reporting this as a failure, or the expectation should be
documented where `--all` is read.

## 1. Decisions made 2026-08-13 (done, no action)

- bear_put demotion = **card veto §1.4**, hedge sleeve preserved. Intake veto
  explicitly rejected (would empty the sleeve's candidate pool).
- OIConfirm out of the Score, in-v4; −25 IVspr veto retired; codex retired.

## 2. Open queue, in rough priority order

### 2.1 Underlying-volume signal study — DONE 2026-08-13, NULL
Pre-registered and RUN the same day (`volume_signal`; entry + amendment note
in `current.md`). **NULL — the volume column is closed, no version bump.**
No R separation on non-bear debit; the frozen exit variant negative
out-of-fold. Infra kept (`Bar.v`, `volume_features.py`). Post-hoc
carry-forwards recorded (bear os_ratio monotonicity → only conceivable home
is the §4 hedge-sleeve pick rule, own pre-registration required; credit
monotonicity on ungated replays). Original plan follows for the record.

#### (original plan, superseded)
Operator asked for it (2026-08-13). Satisfies the ML-search reopen condition
("new COLUMNS only"). **The data is already on disk**: the Barchart history
CSV schema (`lib/barchart/options.py` docstring) carries `Volume`, and
`fetch_underlying_ohlc.py` uses the same feed — every file in
`backtests/underlying_ohlc_cache/` has it. The study loader just ignores it
(`scripts/backtest_study/underlying.py`, `Bar` has no volume field).

Plan sketch (pre-register before running, per house rules):
- Extend `Bar` + `_load_ohlc_cache` with volume; **no volume on the `Price~`
  tilde fallback path** — coverage = OHLC-cache tickers only, same smaller
  denominator the rv20/beta columns carry; always print `coverage()`.
- Headline feature: **O/S ratio** (option volume from the flow scrape /
  underlying share volume — Johnson & So 2012, informed-trading signal;
  literature grounding is a standing requirement). Secondary: relative-volume
  z-score at signal date (Gervais/Kaniel/Mingelgrin; Lee & Swaminathan),
  Amihud illiquidity as a $-move damper.
- **Primary hypothesis = exit/path conditioning, not selection** (selection is
  structure×regime and the column sweep killed everything else; bear was
  diagnosed as an exit problem). Any selection read must be **within
  structure from the first look** (closed-threads rule — `cpir`/`oi_confirm`/
  `iv_pct` all looked predictive pooled and vanished within structure).
- Route through `scripts/backtest_study/` + `protocol.py` walk-forward; log in
  `current.md`. Only a surviving result justifies feeding volume to the live
  pipeline (that is an input change → version bump → new tabs; do not pay
  that for an untested column).

### 2.2 v4 composition bridge — WAITING ON DATA, do not force
`scripts/backtest_study/v4_bridge.py`, gate `MIN_V4_DATES = 20`; v4 accrues
~1 date/day. Until it fires, deploy under the v3-derived rules unchanged.
Do not lower the gate. Its **exit 3 in `--all` is the designed refusal, not a
defect** (§0c(C)) — do not "fix" it by pointing `--v4-csv` at a v3 export.

### 2.3 Calendar-as-hedge — BLOCKED ON NEW DATES
The whole hedge programme (calendar / put calendar / diagonal / sweep
structures) terminates at one wall: 9 worst-decile dates cannot power a
worst-decile criterion under a 1/day sleeve (all 30 ARM S cells
power-stopped; H2 power-stopped at n=6). Carry-forwards recorded in
`current.md`: RANGE+C/L-VOL calendar cell (n=15, post-hoc) and the H2 clause
amendment (power stop should suspend only (b)). Nothing to run until the
book has materially more dates.

### 2.4 Bear sub-0.50 give-back — CANDIDATE, blocked on a harness mechanism
124 bear-debit rows peaked between +1% and +50% and lost −$77.2k entirely
below the ratchet's arming threshold. A lower `be_after` is a candidate, NOT
a finding — the census does not price the cost on winners that dip through
entry (that cost is what made the same config lose on non-bear debits).
Per the 08-12 open-queue audit it is blocked on a harness mechanism; the
flat-band cut waits for new bear rows.

### 2.5 Live walk-forward — the actual evidence source now
v3 tuning is closed; live fills are the evidence source. `SUBSTITUTED` match
category shipped 08-11. Open: Stage 1/2 fill-mapping and the live-vs-tier
feedback eval (does realized live P&L order A > B > C?). Also the standing
operator behavior to track: naked-leg substitution where a spread was emitted
(untested instrument — see the hedge-sleeve limits list).

### 2.6 Rollback triggers — accumulating, check at gates, never read silence as "not met"
Table in `deployment-evidence.md` §"Open pre-registered rollback triggers":
BEAR_HE trail (≥25 new affected dates), bear-debit `be_after` (≥60 new
arming rows), bull_put band re-read on the next independent window.

### 2.7 Parked / blocked long-term
- **Credit exit knobs** — unvalidated; needs a credit-heavy window (every
  historical winner is the Mar-TSLA cluster).
- **Long-dated blind spot** — h ≥ 180 unpriceable with real data; bs proxy
  tier is OFF (`proxy.bs_fallback: false`); blocked on real long-dated
  history.
- **Per-regime exit switch** — still gated (candidate: pt 1.10+ in
  E-VOL/RANGE).
- **Prompt/infra**: pipeline `core.py` refactor deferred; PostToolUse hook
  never runs pytest. (The worktree pytest wart is FIXED 2026-08-13:
  `test_live_loop.py` self-skips when the snapshot data is absent.)
  The delegation-nudge PreToolUse hook is FIXED 2026-08-14: `is_read_bash` was
  blind to `source .venv/bin/activate && <read>` and `echo "==="; <read>` — the
  two dominant idioms here — so it undercounted ~60% and first fired at true-read
  14. It now skips setup/banner segments, and thresholds tightened to
  `FIRST=4 / REPEAT=3`. Still **advisory by design**: `systemMessage` only, no
  `permissionDecision`, so it can nudge but never enforce delegation.

## 3. Standing rules the next session must not re-litigate

- `score_total` is decision-irrelevant (tie-break only); selection =
  structure × regime × entry geometry.
- ML/selection search closed — re-open on **new columns only**, tested within
  structure from the first look.
- `bear_call_spread` intake-vetoed; bear debit §1.4 selection-vetoed, hedge
  sleeve §4 only.
- v3/v4 rows never pooled; v4 score scale 0–50 (0–55 VOLATILITY), not
  comparable to v3.
- Real+tweak pricing tiers only; filter legacy `bs` rows by `proxy_method`.
