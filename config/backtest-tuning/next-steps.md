# Next steps — session handoff

Written 2026-08-13 so a fresh session can pick up without re-deriving state.
Read this + the top state-of-play paragraphs of [`current.md`](current.md);
everything here has its evidence trail there or in
[`deployment-evidence.md`](deployment-evidence.md).

## 0. Repo state — READ FIRST

*(Rewritten 2026-08-13 evening; the original §0 described the morning's
then-uncommitted work, which has since landed.)*

The morning change sets are **MERGED to `main`**: method-config audit
(`51746ac`) and bear_put demotion §1.4 (`8a786f2`), via merge `66cd01a`.

The evening session's work — the `volume_signal` study (§2.1, NULL), its
pre-registration + run entry + amendment + replication grading in
`current.md`, the `Bar.v`/`volume_features.py` infra, 42 new tests, and the
worktree-pytest fix — is committed on the branch
**`worktree-refactored-coalescing-hamster`**. If `git log main` does not show
it, the merge is the first action:

    git merge worktree-refactored-coalescing-hamster   # from the main checkout

Suite state: 896 passed, 1 skipped (`test_live_loop.py` self-skips where the
IBKR snapshot data is absent — the `--ignore` workaround is gone), 2
pre-existing `test_underlying_features.py` beta AttributeErrors (reproduced
on the main checkout, still open).

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
Do not lower the gate.

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
