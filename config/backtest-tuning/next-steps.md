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

Suite state **re-measured 2026-08-14 after the study-suite repair: 1,149 passed,
0 errors.** The two long-standing `test_underlying_features.py` beta
`cache_clear` teardown errors are **CLOSED** — `_market`'s finalizer cleared the
cache while the monkeypatched lambda was still installed (`monkeypatch` is a
dependency of that fixture, so it tears down *after*); undo first, then clear.
The tests always passed, but the synthetic SPY series was leaking into later
tests through the `lru_cache`. (Was 1,093/2 earlier on 08-14; 896 passed / 1
skipped on 08-13.)

`backtest_study run --all` **exits 0** as of 2026-08-14 — see §0c.

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

The one registration bug the build exposed is **FIXED 2026-08-14**: criterion
(4)'s "positive in all three years" was unsatisfiable on a PRIMARY spanning two
calendar years. Only the WORDING was wrong — the implementation already did
"every year present positive" with an inline disclosure — so the printed string
and the pre-registration now read "positive in every calendar year present in the
arm's population", under a dated wording-correction note. Implementation
untouched, study not re-run.

Both of the carried 30-minute follow-ups are **DONE 2026-08-14**: the
`account_sim` verdict-grammar hole is closed (grammar is now total, enforced by a
test over all 32 criterion combinations; PRIMARY prints `FEASIBILITY NOT
CONFIRMED`, and the SECONDARY A3 blowup at 25.1% DD has its own label), and ARM
H's sizing floor now skips when half-size is under one contract instead of
rounding up to a full one. Details in [`current.md`](current.md).

## 0c. Study suite — was 6 FAILING, **ALL RESOLVED 2026-08-14**; `run --all` exits 0

The six failures were **three unrelated causes**. All three are fixed; the full
write-up is in [`current.md`](current.md) §2026-08-14 (two entries: the gate
correction and the runner/retirement work). Kept here in short form because the
*reasoning* behind two of the choices should not be re-derived.

**(A) The DEBIT_PROD exact-replay gate — FIXED by classifying, not by asserting.**
`bear_position_study`, `exit_switch_mech_study`, `exit_switch_structure_study`
all stopped on a gate demanding every real debit row replay bit-exactly under
`DEBIT_PROD`. Production stopped having that property on 2026-07-22, when
`31cb935` shipped `regime_exit.cells.BEAR_HE` (trail .50/.50): it resolves a
per-row effective config (`simulate.py:150-165`) while the frozen harness takes
flat call args and never sees the signal date. No export could ever satisfy it.

`harness_gate()` in `exit_switch_mech_study.py` is now the **single**
implementation, called by all three studies. It classifies each row **exact /
near-rounding-tie / superseded-basis / HARD** and stops only on HARD.
Superseded-basis is identified mechanically, not by date heuristic:
`unreachable_reasons(prod)` computes the exit reasons `replay()` cannot emit
under a profile (for `DEBIT_PROD`: `trailing_stop`, `underlying_stop`,
`be_stop`), so a stored row carrying one of those was by construction written
under a different config. Measured: **289 exact / 0 near / 12 superseded / 0
HARD**, calibrated totals matching to the cent, the whole −$5,145.00 isolated and
reported. The 12 rows are **kept and re-replayed** — they are precisely the rows
where the shipped rule changed the outcome, so dropping them would bias the cell
under test. Proxy admission is unchanged (exact-only): a pre-registered
POPULATION choice, not part of the gate.

`bear_position_study.py`'s `R` is now `replay(t, **DEBIT_PROD)["pnl_pct"]`
instead of the stored `realized_pnl_pct`. Contamination measured on the same
book both ways: **12 rows, −$5,145.06**; bear_put mean R −0.1016 → −0.1069,
`long_put` −0.570 → −0.627 (n=7). It made the bear book look *better* than it
was, so the correction **strengthens** the demote reading — re-run verdict is
still **DEMOTE TO VETO** and card veto §1.4 stands. (A naive row-level diff
reports "95.7% of rows changed" — that is 4-decimal CSV round-trip noise; at a
`NEAR_MISS_TOL` threshold it is 12 rows.) 15 tests in
`tests/test_exit_replay_gate.py` pin all of this, including that a **true HARD
row still exits 1**.

⚠️ **NEW STANDING HAZARD — do NOT key anything on the `exit_basis` column.** This
section previously recommended identifying superseded rows by that column. It
exists in `_KEY_ORDER` (`scripts/backtest/core.py:61`) and the writer
(`simulate.py:_exit_basis`) is correct, but it reaches the export as an
**unlabelled 47th column** (the Sheets tab header was never given the name) and
its values are **scrambled relative to their rows**. Measured 2026-08-14: of 67
`BacktestResults` rows created after the trail shipped — every one of which should
carry a basis — **65 are blank**, while **55 `BEAR_HE` and 11 `CREDIT` labels sit
on rows created *before* the column existed**; **7 of 13 `CREDIT`-tagged rows have
a positive entry price**, which `_exit_basis` cannot produce; and no
`BEAR_HE`-tagged row has a `trailing_stop` exit. Root cause is the hazard
CLAUDE.md warns about: `scripts/align_tab_headers.py` checks only the **analysis**
tabs against `config.ROW_COLUMNS` and does **not** cover
`BacktestResults`/`BacktestProxy` against `core._KEY_ORDER`.
`config/backtest-reference.md`'s "blank = PROD-basis by definition" is **false on
this export**; both that file and `simulate.py` now carry the warning.

- [ ] **Operator action (a Sheets write, NOT taken):** extend
      `align_tab_headers.py` to cover the two backtest tabs against
      `core._KEY_ORDER`, fix the header, then re-verify the values against
      entry-price sign before any study reads the column.
- [ ] **Minor follow-up:** `book.py`'s `diag["debit_calib"]` still counts those
      12 as `hard`, using the old vocabulary. Harmless there (it never gates and
      always keeps real debit rows) but misleading in the three reports that
      print it (`account_sim.py:1062`, `calendar_hedge.py:634`,
      `volume_signal.py:97`). Aligning it to the four-way split changes no
      admission decision and no study's numbers — three print sites. Its
      docstring already carries the correction.

**(B) `combined_exit_study` and `underlying_exit_study` — RETIRED.** Inputs are
deleted gitignored scratch and were never recoverable. `catalog.py`'s `Study`
gained a `retired` field (orthogonal to `state`: retirement is about whether a
study can be RUN, not what it argued) plus `retired_studies()`; `--all` skips
them with the reason printed, `run <name>` still runs one explicitly after a
notice, and the study-map page renders a `retired` pill and caveat. **Do not
repoint them at surviving files** — `results.csv` is 4 rows on 2 dates today
(Attempt 12 ran on 94 real debit + 22 credit), `results_proxy.csv` was always an
author transposition of the writer's `proxy_results.csv`, and although
`v2_results_nocreditdiff.csv` IS the genuine rename, `underlying_exit_study`'s
other input has 0 credit rows so it would emit an empty report anyway. Numbers
off a 4-row wrong-vintage book would read as a fresh confirmation. Porting
`combined_exit_study` to `book.py` stays a design decision, not a loader swap
(it imports `Trade`/`replay` from the older `exit_mechanism_study.py`, not the
frozen `harness.py`). Count rows with `csv.DictReader`, never `wc -l`.

**(C) `v4_bridge` exit 3 — now a first-class DESIGNED REFUSAL.** It was never a
defect: it is the pre-registered refusal to compare a v3 book against itself.
A study may now declare `DESIGNED_REFUSAL_EXIT_CODES = {…}` as a module constant,
read by `run.py` via `ast` (never imported, same as `discover()`); such an exit
promotes `-latest.txt`, prints under **DESIGNED REFUSALS (not failures)**, and is
excluded from the return code. `v4_bridge` declares `{2, 3}`. Other studies stop
on their own pre-registered calibration or power gates and are equally correct to
do so. `MIN_V4_DATES` was NOT lowered and `--v4-csv` was NOT pointed at a v3
export. `study_map` was taught the same two words (it was still printing
`exit 3 [failure]` and `never run`), importing `run.py`'s `_refusal_codes` and
`catalog`'s retired set rather than re-deriving either — `--check` now reads
`refused (exit 3)` and `retired`. **An undeclared non-zero exit on a
refusal-capable study still classifies as `failure`**, and that is pinned by a
test: the refusal path must never swallow a real failure.

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
