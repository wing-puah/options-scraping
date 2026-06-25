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

Tested three variants to fix early profit-target exits (see `config/backtest-tuning.md §Attempt 7`):

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
| P3 | Weak OI-confirmation trades are low quality | OIConfirm <40% bucket significantly underperforms. | Convert OIConfirm <40% from confidence penalty into hard rejection filter. | High | High |
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
| OI confirmation | OIConfirm <40% heavily underperforms | Strong candidate for hard filter |
| Bear put spreads | Perform well in BEAR + HP and RISK-OFF environments | Bearish structures are not the primary problem |
| Bull call spreads | Large contributor to poor performance in low-vol bullish regimes | Structure selection likely incorrect |
| Profit-taking | Only a handful of true round-trip cases | Not a major source of performance drag |

---

## Backtests To Run Next

| Test | Rule | Purpose |
|--------|--------|--------|
| A | DTE >= 90 only | Measure impact of removing short-duration trades |
| B | DTE >= 90 AND OIConfirm >= 40% | Test combined quality filter |
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