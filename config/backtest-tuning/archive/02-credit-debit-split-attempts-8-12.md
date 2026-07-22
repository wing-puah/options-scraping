# Archive 02 — Credit/debit split, Attempts 8–12 (2026-07-04 → 07-07)

Part of the [backtest tuning log](../README.md). Covers the credit/debit exit
split, the debit trailing-stop removal, the proxy backtest tool, the next-open
entry-basis change, and the combined real/proxy grouped exit study.

---

## Attempt 8 — Credit/debit split (2026-07-04)

**Motivation:** two compounding bugs shared one root cause — the backtest was
treating every position as if it were a debit. (1) **Oversizing:** contracts
were sized on `abs(entry_option_price)` — the credit *received* — not the
structure's max loss. A $0.50 credit on a $5-wide spread sized to ~26 contracts
against a $1,000 (2%) risk budget; true worst case ≈ $11,700. (2) **Wrong exit
profile for credits:** `trailing_stop_trigger=0.50` fires at 50% of the credit
captured and the 25pt trail whipsaws on noise-level mark moves; `stop_loss=0.75`
of a small credit is a rounding error relative to true max loss; and
`time_exit_dte_fraction=0.75` closes credit positions right before the
final-25%-of-DTE theta capture that is the whole point of selling premium.

**Change:**
- `_max_loss_per_unit(legs, entry_net)` (new, `scripts/backtest/helpers.py`):
  debit → premium paid (unchanged convention); credit → credit received minus
  the structure's worst expiration payoff (`_payoff_floor`); `None` when
  unbounded (net short calls, multi-expiration credit).
- `_size_contracts` (`scripts/backtest/simulate.py`) now sizes credit positions
  on `_max_loss_per_unit`, not `abs(entry_option_price)`. Unbounded/uncomputable
  → falls back to 1 contract + `log.warning`. Debit formula unchanged (verbatim).
- `_effective_sim_cfg` presence-merges a new `simulation.credit:` block
  (`config/backtest.yml`) over the base config when `entry_option_price < 0`:
  `profit_target=0.65`, `stop_loss=1.00` (mark doubles), no trailing stop, no
  time exit — a "theta harvest" profile that lets credits run toward expiry
  instead of exiting on premium-sized noise. Explicit `null` in the block
  disables that rule for credits specifically; debit config and all existing
  credit tests (`test_simulate_short_put_*`, `test_simulate_bull_put_spread_credit`,
  iron condor tests) are unaffected since none set a `credit:` block.
- Two new `BacktestResults` columns (physical end of the schema, after
  `daily_pnl_csv`, for sheet append-alignment): `max_loss_per_contract` (dollars,
  blank when unbounded) and `pnl_on_risk_pct` (decimal fraction of
  `max_loss_per_contract`, not of premium — puts credit and debit P&L on one
  risk-adjusted scale). See `config/backtest-reference.md`.

**Results (2025-03-13 → 03-14, `--cache-only`, vs the pre-change
`backtests/results.csv` over the same window — only 2 credit rows exist in it,
so this validates mechanics, not edge):**

| Credit row | Before | After |
|---|---|---|
| KWEB short straddle (unbounded risk) | 3 contracts, `time_exit` day 21, +20.0% ($255) | 1 contract + unbounded-sizing warning, `expired` day 30, +29.6% ($126); `max_loss_per_contract`/`pnl_on_risk_pct` blank as designed |
| TSLA bear_call_spread 270/300 | 1 contract, `trailing_stop` day 28, +27.8% ($245) | 1 contract, rode through and gapped to `dollar_stop` day 40, −132% of credit (−$1,165 ≈ the $1,000 budget + gap-through); `max_loss_per_contract`=2120, `pnl_on_risk_pct`=−0.55 |

All 8 debit rows byte-identical (excluding the two new trailing columns).

The TSLA row is the honest cost of the profile: the trailing stop *had* banked
+27.8% there, and without it the spread rode into the March-2025 TSLA rally and
took the full stop. The KWEB row is the intended win: theta ran to expiry
instead of being cut at 75% DTE, and the naked-straddle sizing dropped 3→1.
Two rows decide nothing — needs a credit-heavy window (run the analysis
pipeline over more dates, ideally with `structure_override` on) before tuning
`profit_target`/`stop_loss` inside the credit block. Note the credit
`stop_loss=1.00` only fires if a *daily mark* crosses −100% of credit; a gap
lands on `dollar_stop` first (exit priority 3 vs 4), which is what capped TSLA.

### Attempt 8 — full-window evaluation (2026-07-04)

Full comparison over 2024-06-17 → 2025-03-18: `backtests/v2_BacktestResults_nocreditdiff.csv`
(66 rows, pre-change) vs `backtests/results.csv` (69 rows, credit split live).

**Headline (dollar totals):** all trades −$13,126 → −$10,346 (+$2,780); credit
subset (11 trades both runs) −$6,858 → −$4,375 (+$2,483); debit subset
essentially unchanged (55/55 matched rows byte-identical except the KWEB
straddle, which the credit profile now owns). Worst credit loss −$1,372 →
−$1,165; median credit loss −$1,010 → −$305.

**But the improvement is 100% sizing, 0% exits.** Per-contract (sizing-neutral)
the 9 matched credit trades went −$962 → −$3,637 (−$2,675). Decomposition:

- **Sizing (the win):** structural-max-loss sizing collapsed contracts on the
  July losers (GLD 26→2, XOM 9→2, AMD 4→1, SMH 4→1). Same per-contract loss,
  far fewer contracts — this is where the whole +$2.5k came from, and it's the
  part that generalizes (it mechanically caps tail risk).
- **Exit profile (net negative on this window):** profit target 0.65 beat the
  old trailing stop on XOM (+$41/ct) and PLTR (+$140/ct), but the two
  near-identical March TSLA 270/300 bear call spreads flipped from
  trailing-stop winners (+$250/ct each) to dollar-stop losers (−$1,160/ct
  each): MFE peaked at 0.59× credit — 6pts short of the 0.65 target — then
  TSLA rallied through both stops. That single (double-counted, correlated)
  event is −$2,820/ct, i.e. the entire per-contract deterioration.
- Credit win rate 4/11 → 2/11; exit mix dollar_stop 6/trailing 4/stop 1 →
  stop_loss(1×credit) 7/profit_target 2/dollar_stop 2. The 1×credit stop fires
  fast on the July losers at the same per-contract cost as the old dollar stop
  — behaving as designed, no edge either way.

**Verdict: keep the sizing change (clear, mechanical risk reduction); the
credit exit profile is NOT validated.** n=11 with the decisive swing being one
TSLA event counted twice — no statistical significance in either direction.
Possible knobs if the pattern repeats on a credit-heavy window: pt 0.50–0.55
(both TSLA trades would have banked), or re-introduce a wide trail for credits
only after ≥0.5× credit captured. Do not tune off this window alone.

---

## Attempt 9 — underlying-price exit study for credits (2026-07-04) — NOT validated ❌

**Motivation:** the operator trades credit spreads off the UNDERLYING price
(exit when it breaches a level such as the short strike), not off % of the
credit lost. Attempt 8 showed the mark-based credit exits (pt 0.65 /
stop 1×credit) rode the March TSLA pair to dollar stops. Question: would an
underlying-breach stop have exited better?

**Method:** `backtests/underlying_exit_study.py` — path replay of the 12
credit rows in `backtests/results.csv` (2024-06→2025-03) using the STORED
daily marks; underlying daily price taken from the short leg's cached Barchart
history `Price~` column (same scrapes that produced the marks — exact date
alignment, no yfinance). Close-basis rules only (no intraday underlying data,
so no touch variants; exits price at that day's stored close mark).
**Calibration gate passed 12/12:** replaying the exact production credit rules
reproduced every row's exit_reason/days_held/realized_pnl_pct.

**Rules tested** (× profit target 0.65 / 0.50 / none): close beyond short
strike; beyond strike ±1% / ±2% buffer; beyond breakeven (strike ± credit);
each both as a full REPLACEMENT for the mark stops and as an ADDITIONAL rule
ahead of them (the way it would ship).

| Variant (pt=0.65) | total $/ct (12 trades) | Δ vs actual −$4,293 | TSLA-Mar pair |
|---|---|---|---|
| actual new run (mark stops) | −$4,293 | — | −$2,322 |
| strike±1% replacing mark stops | −$3,222 | +$1,071 | −$868 |
| strike±1% + mark stops kept | **−$3,030** | **+$1,262** | −$868 |
| pt 0.50 + mark stops (no underlying rule) | −$948 | +$3,345 | +$1,044 |

**What the underlying stop actually did, per trade:**

- **March TSLA pair (the driver):** underlying closed above the 270 short
  strike on day 6/8 (S=278.39) → exit −0.48/−0.50× credit (−$430/−$438 per
  contract) instead of riding to the dollar stop (−$1,157/−$1,165). This is
  the mechanism working exactly as intended — but it's the SAME correlated
  event counted twice, and TSLA then round-tripped to 227 (MFE day) before
  the real breakout, so a plain strike stop was also 20 days early.
- **July-2024 whipsaws (TSLA ×3, AMD): NOT rescued.** The underlying breached
  the short put strike within a day of the mark stop firing, at the same
  −0.9…−1.6× credit — both mechanisms exit these equally badly. (All four
  later recovered to full profit; only "no stop at all" kept them, which is
  window luck, not a rule.)
- **GLD (the qualitative win for underlying-basis):** the 1×credit mark stop
  fired on day 3 on pure mark noise on a thin $0.50 credit — the underlying
  NEVER came within 2% of the 215 short strike, and the spread expired at
  full profit. An underlying-basis rule correctly holds it (−$52 → +$50/ct).
- **XOM:** plain strike stop clipped it on a marginal touch (109.72 vs 110
  strike, day 41, −$63) that the ±1% buffer correctly ignored (→ held to the
  +$95 profit target). Buffer matters.
- **SMH:** mark stop was BETTER (−$305 day 4) than waiting for the strike
  breach (−$455 day 6) — in a fast selloff the mark moves before the spot
  level does.
- **KWEB short straddle:** strike-basis is nonsense for straddles (short
  strike ≈ ATM → fires day 1). Breakeven basis fired day 16 at −$240 on a
  move that mean-reverted to +$126 by expiry. Any underlying stop must use
  breakeven levels (not strikes) for straddles/strangles — or skip them.

**Verdict: NOT validated — do not ship.** The best variant's +$1,262/ct is
more than 100% explained by the TSLA pair (+$1,454); the rest of the book is
net −$192/ct. Same failure of significance as Attempt 8: one correlated event,
counted twice, decides the sign. The profit-target lever (0.50 vs 0.65,
+$3,345 on this window) is ALSO entirely the TSLA pair (both peaked at 0.59×).
What survives as genuine, transferable observations: (1) an underlying stop
needs a ≥1% buffer or it clips marginal touches (XOM); (2) it must be
breakeven-based for straddles; (3) it does not save gap/whipsaw losers — it
exits them at the same place the mark stop does; (4) its real edge over mark
stops is ignoring mark noise on thin credits (GLD). Revisit with a
credit-heavy window (the config `simulation.credit` block gains an
`underlying_stop` knob only if it survives one).

---

## Attempt 10 — BETTER ✓ (debit trailing stop removed; 2026-07-04)

**Motivation:** the trades in `backtests/results.csv` (83 rows, 2024-06-17 →
2025-04-22, credit/debit split live) were still net negative (debit −$4,481,
credit −$3,478) with a suspect exit mix. Post-exit path diagnostics (replay of
the stored `daily_price_csv` marks) split the exit rules cleanly:

- **Loss-side rules are fine.** After `stop_loss`/`dollar_stop`/`time_exit`
  fire, the path keeps falling (post-exit path-end avg below realized on all
  three). No change.
- **The trailing stop was systematically selling continuations.** All 21 of 21
  debit `trailing_stop` exits later recovered past +30%; realized +19.8% avg vs
  +117.8% post-exit max avg (mfe_day ≈ 40 vs exit day ≈ 22). Spread across 13
  tickers / 5 months — not one correlated event.

**Method:** `backtests/exit_mechanism_study.py` (new, reusable; pattern of
Attempt 9's path replay). Replay engine mirrors `_summarize_path` exit priority
exactly, incl. `time_exit_day = int(dte_entry × tef)`. **Calibration gate
65/65** debit rows (exit_reason + days_held + realized_pnl_pct). Variants
selected on results.csv ONLY; `backtests/v1_20260625_results.csv` (278 debit
rows, 2024-06 → 2026-02) replayed as a comparison column, never a selection
criterion. Δ-LOO = improvement minus its single biggest contributing trade.

| Variant (debit) | total $ | win | Δ vs prod | Δ-LOO | v1 cmp total |
|---|---|---|---|---|---|
| PROD pt.90 trig.50 trail.25 | −$4,481 | 31/65 | — | — | +$53,240 |
| **no trail (pt .90)** | **+$7,088** | **33/65** | **+$11,570** | **+$9,362** | **+$58,729** |
| pt .75 no trail | +$7,368 | 36/65 | +$11,849 | +$10,325 | +$58,356 |
| trail .50 trig .75 (loosest trail tried) | +$2,304 | 32/65 | +$6,785 | +$5,582 | +$48,799 |
| BE ratchet @.75, no trail | +$1,946 | 29/65 | +$6,426 | +$5,224 | +$51,506 |
| no trail, tef null | +$4,876 | 31/65 | +$9,357 | +$7,149 | +$66,129 |

**Decision: remove the trailing stop, change nothing else**
(`trailing_stop_trigger/pct → null` in `config/backtest.yml`; debit block only —
credits never had a trail).

- Every trail width/trigger tried (.25/.40/.50 × .50/.75) was worse than no
  trail at all; the breakeven ratchet (stop→0 once peaked) is a milder version
  of the same mistake — it also sells the mid-path dip.
- pt was NOT moved: the pt sweep .70–1.00 (no trail) is a plateau (+$10.8k to
  +$13.5k Δ) with non-monotonic wiggle (0.80 peaks, 0.85 dips) — no supported
  gradient, and pt .75 vs .90 differ by $280 on 65 trades. Keeping 0.90 is the
  minimal, diagnosed-mechanism change. Same for tef: 0.75 beat null/0.85.
- Robustness: Δ-LOO +$9,362; Δ minus the biggest ticker-structure cluster (the
  two March-2025 HYG bear put spreads, +$4,089) still +$7,480; only one
  negative month (2024-08, −$2,350: TLT/COIN reversals the trail had banked —
  the honest cost, those flips now ride to stop_loss).

**Verification:** full `--cache-only` re-run with the new config reproduced the
study exactly — all 65 debit rows match the predicted
exit_reason/days_held/realized_pnl_pct; all 18 credit rows unchanged. Book
total −$8,085 → **+$3,611** (win 40/83, exit mix profit_target=34 stop_loss=27
dollar_stop=11 time_exit=6 cap_open=4 expired=1).

**Rules of thumb updated:**
- Attempt 7's "trailing stop is live and meaningful" is REVERSED on the current
  window: with pt=0.90 doing the exit work, the trail only ever converted
  future winners into +20% scratches. Attempt 7 never tested pt=0.90 *without*
  the trail — its Opt C win was vs the pt=0.60 baseline.
- The correct comparison for any new exit rule is post-exit path behavior
  (does the path keep going against the exited position?), not just totals.

---

## Attempt 11 — credit re-check on 18 rows (2026-07-04) — nothing ships ❌

**Motivation:** re-run the Attempt 8/9 credit knobs on the enlarged credit set
(18 rows incl. the KWEB short straddle, vs 12 in Attempt 9) via
`backtests/exit_mechanism_study.py --side credit`. **Calibration gate 18/18.**

| Variant (credit) | total $ | Δ vs prod | Δ excl. Mar-TSLA pair |
|---|---|---|---|
| PROD pt.65 sl 1×credit | −$3,478 | — | — |
| pt .50 | −$378 | +$3,099 | **−$268** |
| pt .55 | −$143 | +$3,335 | **−$32** |
| trail .50 trig .50 | −$1,212 | +$2,266 | **−$179** |
| sl none (dollar stop only) | −$5,992 | −$2,514 | — |
| sl 1.5× | −$4,396 | −$919 | — |
| und ±1% + mark stops | −$3,491 | −$14 | — |
| und ±2% + mark stops | −$3,784 | −$306 | — |

**Verdict: unchanged from Attempts 8/9 — no credit exit change is supported.**
Every apparent winner (pt .50/.55, the wide trail) is 100% the same correlated
March-2025 TSLA 270/300 bear-call pair (+$1,683 ×2, both peaked at 0.59×
credit); excluding those two rows, every variant is flat-to-negative. New
counter-evidence against the underlying-breach stop: it clips the LLY
2025-04-21 bear call spread on a marginal day-3 breach (−$393) that pt .65
banked at +$830 — the ±1% buffer wasn't enough, ±2% was worse elsewhere. The
credit profile (pt 0.65, sl 1×credit, no trail, no time exit, structural
sizing) stays as-is until a credit-heavy window exists; the study script is
ready to re-run against it.

## Proxy backtest for untested plays — new coverage tool (2026-07-06)

Not an exit experiment — new instrumentation. `python3 -m scripts.backtest.proxy`
diffs the analysis tab against BacktestResults, persists WHY each uncovered play
was skipped (`unsupported`/`no_strike`/`no_expiry`/`no_history`/`unpriced`), and
proxy-evaluates it via a fallback chain (nearest-listed-contract tweak → BS off a
donor contract's Price~/IV history → direction-only trend) using the SAME
`simulation:`/`credit:` exit rules → `BacktestProxy` tab +
`backtests/proxy_results.csv` (see backtest-reference.md §BacktestProxy).

First cache-only sweep (all dates, dry-run): **161 untested plays** vs 273
analysis rows — 66 bs_options_hist, 10 strike_expiry_tweak, 1 underlying_trend,
84 unevaluable (cache-only; Barchart probing should convert most), win rate of
the 76 priced = 50.0%. Caveat for any future tuning use: proxy rows are
model-priced (donor-IV BS) — treat their P&L as coverage/selection evidence,
not as exits to tune against.

### 2026-07-06 — proxy classification fixes invalidate 6 pre-fix rows

Not a tuning change — a correctness fix in the shared classifier + proxy snap.
Three defects fixed (`scripts/backtest/classify.py`, `scripts/backtest/proxy.py`):

1. The `Alt:` line fed classification: "covered" in the alternative-interpretation
   text hit the `_UNSUPPORTED_PATTERNS` gate and killed plainly-named spreads.
   Affected rows (all falsely `unsupported`/`unevaluable`): SLV 2024-06-17,
   IWM 2024-07-18, GLD 2024-07-17, GLD 2024-07-15, VLO 2024-07-15.
2. An explicit month-day in the play text was trusted as the expiry even when it
   contradicted the declared horizon bucket — MU 2024-06-17 (hzn 180) was priced
   at the June 26 *earnings* date (9 DTE). Now an explicit date outside
   [H/4, 4·H] loses to the horizon-derived expiry.
3. Method-1 snapped each leg independently, so MU's vertical landed on two
   different expiries (an accidental diagonal). Same-expiration legs now pin to
   one snapped expiration or the method fails over to BS.

Any pre-fix BacktestProxy numbers for those 6 rows are invalid — they were
re-evaluated with `--redo` (new flag: deletes the frozen rows in the bounded date
window and re-appends). Do not mix pre-fix and post-fix proxy P&L for these rows.

## Entry basis changed: signal-day EOD → next-day OPEN (2026-07-06)

Not an exit-knob attempt — a fill-realism fix to the entry price itself. The
backtest had been filling every play at the SIGNAL day's EOD mark (mid bid/ask
on-or-before D via `_price_asof`), a price you cannot actually get: the analysis
is produced after the close, so the realistic fill is the NEXT trading day's
open. New `simulation.entry_timing` knob (`config/backtest.yml`):

- `next_open` (default) — entry day = first history day strictly after D
  (5-day staleness window unchanged); per-leg fill = that day's real `Open`
  from the Barchart history cache (`entry_source: barchart_open`), falling
  back to that day's EOD mark when Open is blank (zero-volume), or to the
  signal-day EOD mark when no later day exists in the window (play kept, not
  dropped). All legs fill on ONE shared entry day (the anchor's).
- `signal_eod` — the legacy basis, kept for reproducing old runs.

Cache-only A/B over the full AnalysisClaude tab (96 plays, 2026-07-06):

| | signal_eod (old) | next_open (new) |
|---|---|---|
| rows priced | 95 | 96 (+1: 2025-03-13 TLT — history starts D+1, now fillable) |
| entry price moved | — | 95/95 shared rows; median ±9.7%, max ±109% |
| dte_entry | — | −1 typical (−2/−3 across weekends) |
| total realized P&L | +$2,860 | **+$240** |

Read: ~$2.6k of the old book's edge was **overnight gap**, not capturable
edge — plays whose signal leaked into the next open (e.g. AVGO 1800C
2024-06-17: EOD mark 156.1 → next open 157.8; TSLA/SPY Mar-2025 puts gapped
hard). All prior tuning attempts (7–11) were measured on the signal_eod basis;
future exit tuning should re-baseline on next_open since entry level shifts
every profit-target/stop distance. Proxy method-1 inherits the new basis
automatically; method-2 (BS off donor) stays entry@signal_eod — the donor
series is EOD closes, there is no open to price (noted in its detail string).

---

## Attempt 12 — next_open re-baseline + combined real/proxy grouped exit study (2026-07-07)

**Motivation:** every exit knob in `config/backtest.yml` (debit pt 0.90 / sl 0.75 /
no trail / tef 0.75; credit pt 0.65 / sl 1×credit / no trail / no tef) was tuned
in Attempts 1–11 on the **signal-day-EOD** entry basis. `results.csv` has since
been regenerated on **next-day-OPEN** entry (the fill-realism fix above), which
shifts every profit-target/stop distance — so all prior tuning is off-basis and
had to be re-derived. This is also the first study to (a) fold in the
proxy-backtested plays and (b) break the book down by group (structure family /
regime trend / vol regime / play intent) instead of one pooled total.

Run with `.venv/bin/python3 backtests/combined_exit_study.py --side debit` and
`--side credit` (harness built on Attempt 10's `exit_mechanism_study.py` replay
engine; replays the stored `daily_price_csv` marks, mirrors `_summarize_path`
exit priority incl. `time_exit_day = int(dte_entry × tef)`).

### Method — combined tuning set + proxy segmentation

- **Tuning set = real rows + proxy `strike_expiry_tweak` rows** (both priced from
  real Barchart marks), deduped against the real rows on
  signal_date+ticker+play-prefix. 18 proxy rows duplicated a real row and were
  dropped (real wins): **14 debit + 4 credit**. Result: debit 94 real + 35 tweak
  = **129**; credit 22 real + 4 tweak = **26**.
- **Proxy `bs_options_hist` rows are a CONSISTENCY COLUMN ONLY** — fully
  model-priced (donor-IV Black-Scholes) and still on the old signal-EOD basis, so
  their Δ is printed beside each variant but **never decides a winner** (26 debit /
  14 credit eligible). `unevaluable` proxy rows are excluded (no marks).
- Because only some tweak rows are next-open basis (`tweak(open)`) and the rest are
  old close basis (`tweak(close)`), every Δ is split
  `real / tweak(open) / tweak(close)` so old-basis rows can't silently swing a
  verdict.
- **Winner discipline per group:** N ≥ 15, Δ-LOO > 0 (Δ minus its single biggest
  contributing trade), per-month Δ not >80% concentrated in one month, and the
  improvement survives excluding the `tweak(close)` rows.

**Calibration gates (production rules replayed vs stored actuals):** debit real
93/94 (one benign CSV round-trip rounding tie, pnl off ≤0.0001, same
exit_reason/days — kept), credit real 22/22, tweak 35/35 + 4/4; bs 23/26 + 13/14
(the 3+1 rounding mismatches excluded from all tables). SANITY prod-replay totals
reproduced the stored `realized_pnl_abs` exactly on both sides (debit
+$15,736.50, credit −$5,008.50).

**Process fix (grid correctness).** The harness's `DEBIT_PROD` constant still
carried the Attempt-10-removed trailing stop; after syncing it to the real
production config (no trail), three single-knob trail variants became silent
no-ops (a lone `trail` override inherited `trig=None` and never armed). The grid
was corrected so every trail variant sets **both** `trig` and `trail` explicitly.
All trail numbers below are post-fix.

### Debit re-baseline (94 real rows, next_open) — no global winner

| Variant | total $ | win | Δ vs prod | Δ-LOO |
|---|---|---|---|---|
| **PROD** pt.90 sl.75 no-trail tef.75 | **+15,736** | 48/94 | — | — |
| trail .50 trig .50 | +6,548 | 45/94 | −9,189 | −10,480 |
| trail .50 trig .75 | +14,206 | 49/94 | −1,530 | −2,821 |
| pt 1.10 no trail | +15,860 | 45/94 | +124 | −1,099 |
| pt .75 no trail | +17,862 | 52/94 | +2,126 | −34 |
| no trail, tef null | +15,746 | 49/94 | +9 | −1,198 |

Every trig-.50 trail is a big loser (real Δ −$9.2k to −$12.2k; −$16k to −$20k on
the combined 129-row set — the trail sells continuations exactly as Attempt 10
found). On the **combined** set the best variant is `no trail, tef null` at
Δ-LOO **+$624** (total +$22,923, Δ +$2,394) — but that is below any reasonable
bar, and on **real rows alone** the same variant is Δ-LOO **−$1,198** (it clears
prod only because the tweak rows are folded in). **Verdict: keep PROD; no global
debit change is supported.**

### Debit group findings — exits are regime-conditional, not global

| Group | N | WINNER | Δ-LOO | months | Δ ex-tweak(close) |
|---|---|---|---|---|---|
| BEAR | 16 | **trail .50 trig .50** | +2,521 | ok (2 mo) | +2,521 |
| H-VOL | 24 | **trail .50 trig .50** | +2,214 | ok | +3,226 |
| L-VOL | 77 | **no trail, tef null** | +1,635 | ok | +3,405 |
| DIRECTIONAL | 89 | **no trail, tef null** | +2,084 | ok | +3,854 |
| RANGE | 61 | none (best +1,179, pt 1.10) | — | — | — |
| BULL | 48 | none (best −155) | — | — | — |
| E-VOL | 22 | none (best +18) | — | — | — |
| HEDGE | 37 | none (best +0) | — | — | — |
| by side / structure | 129/126 | none (best +624/+638) | — | — | — |

The two surviving tweaks pull in **opposite** global directions — add a trail in
stressed tape, drop the time exit in calm tape — which is why neither can be a
global rule and why the pooled book shows no winner. HEDGE (N=37) is flat at the
prod setting (best Δ-LOO $0), so the market-hedge book needs no change.

**Root cause — why a trail helps in BEAR/H-VOL:** in stressed tape debit spreads
spike then round-trip hard, so the trail banks the spike and, more importantly,
rescues would-be stop-outs. In the March–April selloff:
`2025-03-13 NVDA bear_put_spread` goes `stop_loss(−$897, d72) → trailing_stop(+$115, d19)`;
`2024-07-18 HYG bear_put_spread` `dollar_stop(−$1,029, d21) → trailing_stop(+$262, d14)`;
`2025-04-22 HYG` `dollar_stop(−$1,020, d5) → trailing_stop(−$150, d3)`. Within the
BEAR/H-VOL names these rescues outweigh the winners the trail cuts short (e.g.
`2025-03-20 HYG` `profit_target(+$2,754) → trailing_stop(+$81)`), netting
Δ-LOO ≈ +$2.2–2.5k — the reverse sign of the same trail's global −$9k.

**Root cause — why dropping tef helps in L-VOL/DIRECTIONAL:** the 75%-DTE time
exit sells grinding winners that are still compounding. Flips from `tef null`:
`2024-06-20 META bull_call_spread` `time_exit(+$271, d48) → profit_target(+$1,478, d65)`;
`2024-07-15 KRE bull_call_spread` `time_exit(+$882, d35) → profit_target(+$1,676, d48)`;
`2024-06-20 TLT bull_call_spread` `time_exit(+$371, d30) → profit_target(+$1,169, d31)`.
The cost is a few losers that ride longer (`2025-03-19 TSLA`
`time_exit(−$68) → dollar_stop(−$1,017)`), but the grind-winners dominate in calm
tape.

**Month-span caveat — treat BEAR/H-VOL as a hypothesis, not a rule.** The whole
dataset spans only ~6 distinct months (2024-06/07/08, 2025-03/04, 2025-12), and
BEAR ≈ H-VOL ≈ the single **March–April 2025 selloff** episode. BEAR's "months
ok" is really two adjacent months of one episode (per-month Δ 2025-03 +$2,688 /
2025-04 +$870, no other months present); H-VOL is marginally better distributed
(adds 2024-08 +$704) but still selloff-dominated. Another stressed episode is
needed before the trail finding can be trusted.

### Credit (22 real + 4 tweak) — no robust winner (same single-cluster trap)

| Variant | total $ (real) | Δ vs prod (real) | Δ-LOO (combined) | bs Δ |
|---|---|---|---|---|
| **PROD** pt.65 sl 1×credit | **−5,008** | — | — | — |
| **pt .50** | −1,924 | **+3,084** | +1,232 | −457 |
| pt .55 | −3,114 | +1,894 | +185 | −236 |
| pt .50 sl none | −3,164 | +1,844 | −8 | −1,064 |
| trail .50 trig .50, pt none | −3,310 | +1,698 | +250 | −966 |
| sl none (dollar stop only) | −6,765 | −1,756 | −2,900 | −606 |

`pt .50` posts the biggest real Δ (+$3,084) but fails the discipline test on two
counts: **>80% single-month concentration** (real per-month 2025-03 +$2,955 vs a
+$3,084 total — the same March-2025 TSLA bear-call cluster that decided Attempts
8/9/11), and its **bs consistency Δ is negative** (−$457). Every apparent credit
winner is the same correlated cluster; excluding it, all variants are
flat-to-negative. Trend/vol/intent subgroups are all N<15 or single-intent
(DIRECTIONAL = the whole set). **Verdict: keep PROD; credit pt .50 remains
unvalidated pending a genuinely credit-heavy, multi-cluster window.**

### Verdict / Recommendation

**No `config/backtest.yml` change was applied.** Production exits are kept
unchanged globally on both sides — the re-baseline on the next_open basis
confirms the current debit and credit profiles as the best-supported pooled
settings, and no global variant clears the robustness bar.

Two candidate follow-ups, both explicitly **not shipped**:

1. **Regime-conditional debit exits** — add `trail .50 trig .50` when
   `market_regime` is BEAR or H-VOL, and drop/loosen the time exit (`tef null`) in
   L-VOL — the only tweaks that survived per-group discipline, and they point in
   opposite global directions (hence no single rule). Gated on another stressed
   (bear/high-vol) episode or more calendar months, since BEAR/H-VOL collapse to
   the one March–April 2025 selloff today. Implementation would need the sim to
   read the play's regime/vol label at exit time (not currently a knob).
2. **Credit `pt .50`** — still unvalidated; every edge is the recurring
   single-cluster March-2025 TSLA trap. Hold until a credit-heavy window with
   independent clusters exists.

The study harness (`backtests/combined_exit_study.py`) is idempotent and ready to
re-run against any new window.

---
