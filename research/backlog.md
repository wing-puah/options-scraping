# Backtest-engine backlog — triaged 2026-08-15

**This file is a historical record, not the live queue.** The live queue is
[`next-steps.md`](next-steps.md) §2; the design backlog for the *analysis*
pipeline (a different thing, despite the word) is
[`analysis-roadmap.md`](analysis-roadmap.md).

Everything below was written **2026-06-24/25**, against `results.csv` /
`analysis_-_BacktestResults.csv` on the **v1/v2 prompt versions** and the
**pre-2026-07-06 entry basis** (signal-day EOD, since replaced by next-day
OPEN — see [`archive/02`](archive/02-credit-debit-split-attempts-8-12.md)
§"Entry basis changed"). Two consequences, both load-bearing:

1. **Every P&L figure below is on a superseded basis and is not comparable to
   anything current.** Do not quote them.
2. The v1 exports store `pnl_pct` as `"1.64%"` **strings**; a naïve
   `to_numeric` on them fabricates a v1 edge that does not exist. Several
   percentage claims below are on that footing.

## Triage

| Item | Verdict (2026-08-15) | Where it went |
|---|---|---|
| **P0** — exit engine ignores per-play `invalidation` conditions | **STILL OPEN** — the only live item on this page | see below |
| P0 — `stop_loss` mislabelled at horizons past expiry (7 of 8 rows) | **FIXED** | `simulate.py` caps the path at `min(nearest_dte, path_cap)` and emits `expired` / `cap_open`; it can no longer run past expiry |
| P0 — mark to intrinsic at expiration, not a blanket −100% | **FIXED** | `backtest/helpers.py` computes the piecewise-linear expiration payoff `Σ qty·intrinsic(S, K, type)` |
| P0 — distinct terminal-status set | **PARTLY DONE** | `profit_target` / `trailing_stop` / `stop_loss` / `dollar_stop` / `time_exit` / `expired` / `cap_open` ship. `invalidation_exit` does not — it follows P0 above. (Note: the `exit_basis` column is separately known-corrupt; never key a study on it.) |
| P1 — entry faithfulness (executed strike/expiry ≠ documented play) | **SUPERSEDED by implementation** | this is the live loop's job now, not the backtest's: `scripts/live_loop/stage1_map_fills.py` with the `mapping.CONFIDENCES` vocabulary (`EXACT` / `STRUCTURE` / `CORE` / `OVERLAY`), and an ambiguous multi-leg group is reported undecidable rather than guessed |
| Claude 2026-06-25 — structure/direction/regime buckets | **REFUTED at scale** | see "the reversal" below |
| Claude 2026-06-25 — Attempt 7 Opt C (pt=0.90 + trail) | **SUPERSEDED** | Attempts 8–13 split credit/debit, removed the debit trail (Attempt 10), vetoed `bear_call` and removed the credit stop (Attempt 13). Current exits are in [`../docs/deployment-rules.md`](../docs/deployment-rules.md) §4 |
| ChatGPT P1 / Tests A, B — "raise minimum DTE to 90+, prefer 90–180" | **REFUTED, and the premise is a known blind spot** | the edge sits at **DTE 45–59** ([`deployment-evidence.md`](deployment-evidence.md)); the ladder is ≤60-DTE. `h ≥ 180` is *unpriceable* with real data and the BS proxy tier is OFF (`proxy.bs_fallback: false`), so a long-dated read cannot be produced at all — [`next-steps.md`](next-steps.md) §2.7 |
| ChatGPT P2 / Test C — force TF-S into `bull_put` / `bear_call` | **REFUTED** | `bear_call_spread` is the worst structure in the book (n=37, 32% win, PF **0.19**, −$11.2k) and was vetoed at Attempt 13. `bull_put_spread` survives only under the §3 geometry gate (`0.08 ≤ \|delta\| ≤ 0.20`, DTE ≤ 59) |
| ChatGPT P3 / Test B — `OIConfirm` hard-rejection filter | **DEAD** | `OIConfirm` was shipped as a ± score component in Jul 2026 and then **removed** on 2026-08-11: the ML full-column sweep measured `oi_confirm_pct` as decision-irrelevant ([`../docs/conviction-score.md`](../docs/conviction-score.md) §64–82). The rollup *column* survives as context only, so there is no penalty left to compare a hard filter against |
| ChatGPT P4 / Test D — wider stops, days-to-MFE-after-exit | **SUPERSEDED** | absorbed into the exit-conditioning work, [`archive/11`](archive/11-exit-conditioning.md); the surviving open piece is the bear sub-0.50 give-back, [`next-steps.md`](next-steps.md) §2.4 |
| ChatGPT P5 — hedge/directional leak | **DROPPED** | the item deferred itself behind the DTE and TF-S tests, both of which are now refuted |
| ChatGPT P6 — profit-taking | **NO ACTION**, as originally written | — |
| Test E — regime × structure × DTE | **DONE** | that is exactly the table in [`deployment-evidence.md`](deployment-evidence.md), and it produced the shipped ladder |

## The one item still open

**The exit engine does not evaluate per-play invalidation conditions.** The
backtest exits on fixed horizons, profit targets, stops and trails, and
otherwise holds to expiry. Each analysis row carries an `invalidation` string
(e.g. *"AAPL close < 290"*, *"SMH reclaims 570"*), and
`backtest/shared/analysis_io.py` reads it — but only as a passthrough field.
Nothing parses it, and no exit fires on it.

Implementing it means parsing the condition, evaluating it against daily
underlying closes, exiting at that day's spread mark, and adding an
`invalidation_exit` terminal status. Two cautions before anyone starts:

- The strings are free-form model output. A parser that silently fails to
  match must record *that*, not fall through to "condition never met" — the
  latter would understate exits and flatter the book.
- `scripts/backtest_study/lib/harness.py` is the **frozen** exit-replay engine.
  Every recorded conclusion rests on it; a new exit reason belongs in the
  backtest engine, not there.

## The reversal — why the 2026-06 structure findings are inverted, not merely stale

The June read (275 plays) concluded that **bear put spreads drive nearly all
profit** (+$28,893, 59% win) while **bull call spreads are essentially flat**
(+$505). At 772+ pooled priced rows on the corrected entry basis, that is
backwards:

| Structure | n | Win | PF | Total |
|---|---|---|---|---|
| `bull_call_spread` | 242 | 60% | **2.05** | **+$79.4k** |
| `bull_put_spread` | 166 | 68% | 0.94 | −$2.2k |
| `bear_put_spread` | 327 | 37% | 0.74 | **−$44.8k** |
| `bear_call_spread` | 37 | 32% | 0.19 | −$11.2k |

`bull_call_spread` in RANGE or E-VOL is now **Tier A** of the deployment
ladder; `bear_put` was demoted (a *selection* problem, not an exit problem —
[`archive/07`](archive/07-bear-put-demotion-thread-and-holdout.md) addenda
11–14). The June sample was small, on the old entry basis, and drawn from a
window whose bear performance did not generalise.

Read this as a warning about the whole page: these were the best available
reads at n≈275 on a basis that no longer exists, and the ones that survived
contact with more data are the exceptions.

---

# Original content, 2026-06-24/25 — kept as a record, superseded above

*Numbers below are on the pre-2026-07-06 entry basis and the v1/v2 prompt
versions. See the triage table for what became of each item. Do not quote
these figures.*

TODO — Backtest engine fixes (/options)
Source of issues: analysis\_-_BacktestResults.csv review (39 trades, 13 entry days).
P0 — Exit engine does not implement the documented invalidation rules
The backtest exits on fixed horizons + a fixed profit-target %, and otherwise holds to
expiry. It does NOT evaluate the invalidation conditions in AnalysisClaude
(e.g. "AAPL close < 290", "SMH reclaims 570", "BTC drops >10%").

Parse each trade's invalidation rule and evaluate it against daily underlying closes, exiting on the first day the condition is met (at that day's spread mark).
Stop relabeling expiry as stop_loss. 7 of 8 current stop_loss rows occur at a horizon past the option's expiration (NVDA 235/265, MSTR 180/210, GLD, SMH 555/520, NVDA 215/195, TSLA, IBIT). These are expired-worthless, not stops.
At expiration, mark to intrinsic value, not a blanket -100% / $0.
Add a distinct terminal status set: invalidation_exit, expired_intrinsic, profit_target, time_stop — drop the misused stop_loss.

P1 — Entry faithfulness (executed trade ≠ documented play)
Strikes/expiries drift between the play and the traded row.

ARM: play = 220/250 Aug-21, traded = 170/250 (0.80-delta long leg — different instrument).
SOXX: play = 525/600, traded = 515/600.
AAPL: play = "300/325 Dec-18", analysis says Jan-27, traded = Jan-2028 expiry.
Add a reconciliation check that fails loudly when executed strike/expiry ≠ play.


# Claude backtest analysis (2026-06-25)

## Backtest Findings & Proposed Changes

275 plays from `results.csv` (2024-06-17 → 2025-12-11), primary metric `realized_pnl_abs`.

### Bucketed Results

| Bucket | Key Finding |
|--------|-------------|
| Structure | Bear put spreads drive nearly all profit (+$28,893, 59% win) vs bull call spreads essentially flat (+$505 total) |
| Direction | Bears +$296 mean / 60% win vs bulls +$1 mean / 54% win |
| DTE | Sweet spot 46–90d (64% win, +$333 mean); sub-45d loses money (29–46% win) |
| Regime | RANGE regimes outperform across all vol levels; BULL+L-VOL is the biggest money loser (−$9,854 total) |
| Regime × Direction | RANGE+L-VOL+HP · bear: 94% win, +$14,713 total (18 plays) — strongest bucket |
| Alignment | Counter-regime trades (61% win) outperform regime-aligned (48%) — flow signal better at dislocations than trend-following |
| Ticker | HYG (+$17,921), GLD (+$8,669), META (+$5,745) best; NVDA (−$7,001), TSLA (−$5,977), COIN (−$4,258) worst |
| Quarter | Q3 2024 and Q1 2025 drove all gains; Q2 2025 worst (22% win, −$9,415) |

### MFE / Exit Analysis

| Exit | Diagnosis |
|------|-----------|
| profit_target | Exiting too early — target fires avg day 14, MFE peaks avg day 34, only 57.7% of MFE captured |
| stop_loss / dollar_stop (64%) | Bad entry — position never moved in favour; stop working correctly |
| stop_loss / dollar_stop (36%) | Genuine round-trips — reached +$916 MFE avg then reversed to −$989; $1,905 given back |
| time_exit | Slow drift back from MFE — not round-trips; need earlier profit exit when ahead |

### Exit Rule Tuning (Attempt 7)

Tested three variants to fix early profit-target exits (see `research/archive/01-exit-rules-attempts-1-7.md §Attempt 7`):

| Variant | Config | vs Baseline |
|---------|--------|-------------|
| Opt A | pt=1.50, trail=0.25 | −$892 |
| Opt B | pt=1.50, trail=0.35 | −$6,730 |
| **Opt C** | **pt=0.90, trail=0.25** | **+$2,726 ✓** |

**Opt C adopted** — raises profit target from 0.60 → 0.90 as a floor for clean winners; trailing stop (trigger=0.50, trail=0.25) handles big movers that exceed 90%. Config updated in `config/backtest.yml`.

---

# CHATGPT backtest analysis (2026-06-24)
## Backtest Findings & Proposed Changes

| Priority | Hypothesis | Supporting Evidence | Proposed Change | Confidence | Expected Impact |
|-----------|-----------|-----------|-----------|-----------|-----------|
| P1 | DTE mismatch | 15-30 DTE: -35% avg return. 120+ DTE: +13% avg return. Many trades achieve MFE after exit. | Raise minimum DTE for directional trades to 90+ days. Prefer 90-180 DTE for TF/PU setups. | High | High |
| P2 | TF-S structure mismatch | BULL + L-VOL + RISK-ON environments underperform despite being favorable market conditions. Framework recommends credit spreads in positive gamma regimes. | Force TF-S setups to use bull put spreads (or bear call spreads) instead of debit spreads. | High | High |
| P3 | Weak OI-confirmation trades are low quality | OIConfirm <40% bucket significantly underperforms. | **PARTLY DONE (Jul 2026):** `OIConfirm` now feeds the conviction score as a ±component (+2/+1 confirmed, −1/−2 weak; neutral when absent/thin `oi_n<3`) and flat ΔOI is excluded from the confirm-pct denominator — see `docs/conviction-score.md`. **Remaining:** backtest whether the softer score-penalty is enough or the stricter *hard rejection filter* (drop `OIConfirm<40%` entirely) does better — Test B below. | High | High |
| P4 | Some trades are stopped before thesis matures | 57% of trades reached MFE after exit. | Test wider stops and/or longer holding horizons. Analyze days_to_MFE_after_exit before changing stop rules. | Medium | Medium |
| P5 | Hedge vs directional classification may still leak | Earlier evidence suggested bearish hedge flow may be misread as directional flow, but regime breakdown weakened this thesis. | Revisit only after DTE and TF-S tests are complete. | Medium | Medium |
| P6 | Profit-taking problem | Very few genuine round-trip trades found after controlling for MFE occurring after exit. | No action currently. | High | Low |

---

## Key Findings

| Finding | Observation | Conclusion |
|-----------|-----------|-----------|
| Overall expectancy | Win rate 56%, average trade -2.2% | Losses larger than winners |
| DTE effect | 15-30 DTE: -35%, 31-60 DTE: -1.6%, 120+ DTE: +13% | Longer-duration positioning works materially better |
| MFE analysis | Average MFE +21.8% vs realized -2.2% | Signals have edge, but implementation may not capture full move |
| Post-exit MFE | 57% of trades hit MFE after exit | Many trades may be exiting before thesis fully develops |
| OI confirmation | OIConfirm <40% heavily underperforms | Now a ±component of the conviction score (Jul 2026); hard-filter variant still worth testing (Test B) |
| Bear put spreads | Perform well in BEAR + HP and RISK-OFF environments | Bearish structures are not the primary problem |
| Bull call spreads | Large contributor to poor performance in low-vol bullish regimes | Structure selection likely incorrect |
| Profit-taking | Only a handful of true round-trip cases | Not a major source of performance drag |

---

## Backtests To Run Next

| Test | Rule | Purpose |
|--------|--------|--------|
| A | DTE >= 90 only | Measure impact of removing short-duration trades |
| B | DTE >= 90 AND OIConfirm >= 40% | Test combined quality filter — and compare the new `OIConfirm` score-penalty (shipped Jul 2026) vs a hard `OIConfirm<40%` rejection filter (P3) |
| C | Force TF-S -> bull put spread | Validate structure selection hypothesis |
| D | Measure days_to_MFE_after_exit | Determine whether stops are too tight or thesis horizon is too long |
| E | Compare market_regime × structure × DTE | Identify strongest regime-specific structures |

---

## Current Leading Thesis

1. Signal generation is probably better than headline P&L suggests.
2. Institutional flow often expresses a multi-month thesis.
3. Short-dated structures cannot reliably express that thesis.
4. Positive-gamma bullish environments are being traded with debit spreads instead of credit spreads.
5. DTE selection and structure selection appear more important than conviction-score tuning.
