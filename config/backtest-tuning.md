# Backtest exit rule tuning log

Running log of parameter experiments — what worked, what didn't, and why.
Dataset: 119 trades across July 2024 (chop), Jan 2025 (bull), March 2025 (panic/correction), Feb 2026.

---

## Baseline

**Config:** `profit_target=0.75`, `stop_loss=0.75`

| Metric | Value |
|--------|-------|
| Win rate | 42.0% |
| Avg PnL | -4.5% |
| Avg win | +87.7% |
| Avg loss | -71.3% |
| Win/loss ratio | 1.23 |
| MFE capture (winners) | 63.1% |

**Problems diagnosed:**

1. **Profit target too low** — winners exited at avg 98.5% but path MFE averaged 204%. 26 exits left 50–520% on the table (HYG left 520%, GLD left 400%, SPY left 162%).

2. **Type-B reversals** (30 of 69 losers) — trade peaked at 30–70% MFE then fully reversed to −75%+ stop. No mechanism to lock in the unrealized gain.

3. **10 early stop-outs** (of 69 losers) — hard stop triggered during a temporary dip; the trade hit MFE 4–49 days *after* exit. AVGO: stopped day 11 at −77%, MFE +139% on day 60. HYG: stopped day 7 at −75%, MFE +209% on day 18.

4. **Directional failures** (32 of 69 losers, 46%) — MFE <10%, straight-down wrong direction calls. Exit rules cannot fix these; they require better analysis.

---

## Attempt 1 — WORSE ❌

**Config:** `profit_target=null`, `time_exit_dte_fraction=0.5`, `trailing_stop_trigger=0.50`, `trailing_stop_pct=0.30`, `loss_days_exit=10`

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| Win rate | 35.3% | −6.7pp |
| Avg PnL | −8.2% | worse |
| Avg win | +58.9% | worse |
| Avg loss | −44.7% | better |
| Win/loss ratio | 1.32 | slightly better |

**Why it failed:**

**Trailing stop (trigger=0.50, trail=0.30) fired on normal option noise.**
Options swing ±20–40% around their trend routinely. A 30pt drawdown from peak is NOT a reversal signal in this asset class.
- HYG: exited day 2 at −30% → ran to **+620%** on day 14.
- GLD: exited day 7 at +87% → ran to **+295%** on day 25.
- QQQ: exited day 3 at +20% → ran to **+291%** on day 33.
- CSCO: exited day 17 at +1% → ran to **+247%** on day 35.
- 34 trailing_stop exits at avg only **+23.4% realized**.

**Loss days (10 trading days) cut trades that hadn't finished developing.**
These plays need 3–6 weeks to play out. Looking bad for 10 days mid-trade is normal.
- 21 of 28 loss_days exits had path MFE >50pts higher than the exit price.
- NVDA (Mar 14): cut at −36%, path MFE +154%. DAL: cut at −24%, MFE +162%. AVGO: cut at −38%, MFE +131%.
- The rule did reduce avg loss (−35.6% vs −71% before), but killed too many recoveries.

**Time exit at 50% DTE too early.**
The biggest moves often occur in the *back half* of the option's life.
- GLD (29 DTE): exited day 10 at +39% → MFE **+403%** on day 21.
- GLD (Jan, 55 DTE): exited day 27 at +251% → MFE **+478%** on day 55.

**Core lesson:** reactive exit rules (trailing stop, loss streak) assume option prices mean-revert around a signal. They don't — option spread prices are very noisy around a directional trend. Any rule based on short-term price drawdown from peak will misfire constantly.

---

## Attempt 2 — WORSE ❌

**Config:** `profit_target=null`, `stop_loss=0.75`, `time_exit_dte_fraction=0.75`, `trailing_stop_trigger=1.00`, `trailing_stop_pct=0.50`, `loss_days_exit=null`

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| Win rate | 41.2% | −0.8pp |
| Avg PnL | −9.6% | **worse** |
| Avg win | +68.1% | worse |
| Avg loss | −64.0% | slightly better |
| Win/loss ratio | 1.06 | worse |

**Exit reason breakdown:**

| Reason | Count | Avg PnL | W/L |
|--------|-------|---------|-----|
| time_exit | 44 | +25.2% | 27W/17L |
| stop_loss | 26 | −79.1% | 0W/26L |
| trailing_stop | 22 | +55.7% | 19W/3L |
| dollar_stop | 20 | −82.1% | 0W/20L |
| cap_open | 6 | +45.0% | 3W/3L |

**Why it failed:**

**Gap-day problem on trailing stop.** 12 of 22 trailing exits landed BELOW the theoretical floor of +50% (trigger=1.00 → peak+100%, trail=0.50 → floor+50%). Options can gap from +100% to −44% in a single trading day — the simulation only sees end-of-day marks and catches the close price after the gap, not the floor. Examples:
- HYG 2025-03-17: peak hit 100%+, then gapped to −44% in one day. Trailing fired at −44% (floor was +50%). MFE later +620%.
- MSTR 2025-03-18: realized +8%, MFE +116%. Trail floor was +50%, but gap blew through.
- 12 of 22 trailing exits below the nominal +50% floor (avg of those 12: +20%).

**Removing profit_target made average wins worse.** Baseline profit_target exits averaged +87.7% realized. Trailing stop (meant to replace it) averaged +68.1%. The trailing is theoretically better for parabolic moves, but the gap-day problem and early reversals mean it delivers less on average than the fixed exit. Specifically: 14 of 22 trailing exits were below 75% (avg +24.8%) — these would have held longer in baseline and potentially recovered.

**Dollar stop is noisy.** 20 trades at avg −82.1%, including a 95-contract FXI and 19-contract INTC. Portfolio sizing can put many contracts into cheap options — a single bad day blows through the $1000 budget before stop_loss even fires.

**Core lesson:** Trailing stop replaces the one thing that was working (profit_target's reliable +75–100% winner capture) with an exit that's vulnerable to gap days. The parabolic runs it was supposed to capture (GLD +400%, HYG +620%) are exactly the cases where gap-days kill it on the way back.

---

## Attempt 3 — BETTER, exit config now stable ✓

**Config:** `profit_target=0.75`, `stop_loss=0.75`, `time_exit_dte_fraction=0.75`, `trailing_stop_trigger=1.00`, `trailing_stop_pct=0.50`, `loss_days_exit=null`

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| Win rate | 45.4% | +3.4pp |
| Avg PnL | −1.5% | better |
| Avg win | +75.3% | slightly worse |
| Avg loss | −65.3% | better |
| Win/loss ratio | 1.15 | slightly worse |
| Total abs PnL | −$3,838 | much better |

**Exit reason breakdown:**

| Reason | Count | Avg PnL | W/L |
|--------|-------|---------|-----|
| profit_target | 37 | +98.1% | 37W/0L |
| time_exit | 33 | −5.6% | 16W/17L |
| stop_loss | 25 | −79.3% | 0W/25L |
| dollar_stop | 19 | −81.7% | 0W/19L |
| trailing_stop | 0 | — | — |

**Key finding:** trailing_stop fired 0 times — profit_target at 75% always fires before the 100% trigger is reached. The trailing is effectively dormant safety-net dead code in the current setup.

**Period breakdown reveals the real problem:**

| Period | Trades | Win rate | Avg PnL | Total PnL |
|--------|--------|---------|---------|-----------|
| Jul 2024 chop | 12 | 33% | −30.9% | −$4,759 |
| Jan 2025 bull | 15 | 33% | −32.5% | −$5,312 |
| Mar 2025 panic | 61 | 56% | +14.3% | +$8,784 |
| Feb 2026 | 14 | 50% | +4.0% | +$750 |

The strategy is **profitable in directional/panic markets and structurally losing in chop**. The exit config is not the cause — 67-73% of chop/bull trades had MAE ≈ -100% at some point (option decayed to near-zero due to theta). Dollar_stop fired on 33-50% of chop trades vs 8-10% in panic. This is theta decay, not exit timing.

**MFE distribution is identical** between chop and panic (52% vs 53% of trades hit MFE >50%). The potential was there — the underlying just didn't move fast enough for the option to realize it before decaying.

---

## Rules of thumb learned so far

- **Don't use trailing stops tighter than 50pts** — option spread daily vol easily exceeds 20–30%, so anything tighter fires on noise.
- **Trailing stop has a gap-day problem** — options can move 50-100pts in a single day, bypassing the theoretical floor. Trailing alone (no profit_target) is unreliable for capping winners.
- **Trailing stop is ADDITIVE to profit_target, not a replacement** — use profit_target as the base exit, trailing as secondary catch for parabolic moves.
- **Don't use loss-day cutoffs shorter than ~25 days** — directional option plays take weeks to develop; mid-trade losing streaks are normal.
- **Time exit at 50% DTE is too early; 75% is better** — many of the biggest moves (GLD, HYG, SPY) happened in the final 25–30% of the DTE window.
- **Exit rules can only help on ~55% of losers** — ~45% are straight directional failures (MFE <10%). Those require better signal quality, not better exit mechanics.
- **Profit target at 75% is correct** — avg win of +98.1% at 75% target. Don't remove it.
- **The exit config is now at its ceiling** — avg PnL −1.5%. Further exit tuning is marginal. The remaining gap is driven by entry quality.

## What actually drives losses — confidence level, not regime

Analysis of AnalysisClaude data cross-referenced against backtest results reveals:

**The "chop" losses were NOT a regime problem.** Jul 2024 was BULL regime, Jan 2025 was BULL/RANGE — the analysis was correct about market direction. The plays failed because:
1. 0–2 baseline sessions → no percentile context to grade whether flow was unusual vs normal. The analysis explicitly flagged this ("baseline window is empty, levels read raw"). Plays on those dates are structurally lower quality.
2. Market was near a cyclical top in both cases (Jul 16 before Aug 2024 correction; Jan 6 before Feb 2025 selloff) — the options decayed when the market reversed.

**Confidence level predicts outcome far better than regime label:**

| Confidence | Jul+Jan trades | Win rate | Avg PnL |
|------------|---------------|---------|---------|
| HIGH | 1 (IWM Jul 16) | 100% | +108% |
| MEDIUM | 20 | 30% | −39% |
| LOW | 6 | 33% | −30% |

March 2025 worked because: BEAR + HP + full baseline window = most plays were HIGH confidence. The regime label correlates with confidence (panic = more certain signal), but it's the confidence, not the regime, that actually matters.

**Regime-specific exits = overfitting AND wrong lever.** The losing trades had MAE ≈ −100% (options decayed to near-zero). No exit rule saves a theta-decay death. And with only 27 chop/bull trades, any special rules would be tailored to exactly those 27 dates.

## The real next step: confidence-based position sizing

The analysis framework already grades plays as high/medium/low. Use this:
- HIGH confidence → full 2% risk per trade
- MEDIUM confidence → 1% risk (or skip)
- LOW confidence → skip
- 0 baseline sessions → cap position size or skip entirely

This is principle-driven (signal quality → position size), not curve-fitting. It would have avoided most of the losing trades in Jul 2024 and Jan 2025 without touching the exit logic.
