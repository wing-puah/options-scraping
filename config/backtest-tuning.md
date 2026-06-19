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

## Attempt 4 — WORSE ❌ (trailing-on-profit-target)

**Config:** `profit_target=0.75` (activates trailing instead of exiting), `trailing_stop_trigger=1.00`, `trailing_stop_pct=0.50` — code change in `simulate.py`: when profit_target fires and trailing_stop_pct is set, set `trailing_active=True` instead of closing.

| Metric | Value | vs Attempt 3 |
|--------|-------|-------------|
| Win rate | 40.0% | −5.8pp |
| Avg PnL | −10.0% | **worse** |
| Avg win | +65.9% | worse |
| Avg loss | −60.6% | slightly better |

**Exit reason breakdown:**

| Reason | Count | Avg PnL |
|--------|-------|---------|
| time_exit | 41 | — |
| trailing_stop | 28 | — |
| stop_loss | 25 | — |
| dollar_stop | 19 | — |

**By regime:**

| Regime | Before P&L | After P&L | Δ |
|--------|-----------|-----------|---|
| RISK-OFF | +82% | +128% | **+46%** |
| BULL | −22% | −23% | −2% |
| BEAR | +15% | +2% | −14% |
| RANGE | −21% | −32% | −10% |
| (other) | +33% | +7% | −26% |

**Biggest losers (all profit_target → trailing_stop):**

| Ticker | Date | Before | After | Δ | MFE |
|--------|------|--------|-------|---|-----|
| EEM | 2025-03-18 | +302% | +80% | −222% | +302% |
| DAL | 2025-03-13 | +145% | −13% | −157% | +181% |
| HYG | 2025-03-17 | +100% | −30% | −130% | +620% |
| HYG | 2025-03-10 | +112% | −10% | −121% | +555% |
| NVDA | 2025-03-13 | +92% | −24% | −116% | +104% |

**Biggest winners (all profit_target → trailing_stop or time_exit):**

| Ticker | Date | Before | After | Δ | MFE |
|--------|------|--------|-------|---|-----|
| GLD | 2025-01-02 | +78% | +212% | +134% | +478% |
| NVDA | 2025-03-20 | +83% | +212% | +129% | +313% |
| GLD | 2025-03-18 | +88% | +186% | +98% | +198% |

**Why it failed:**

Same gap-day problem as Attempt 2, now at a lower activation level. Profit_target at +75% triggers trailing with peak_pnl ≈ 0.75–0.80 and a floor at +25–30%. A single bad day in the March 2025 panic/correction (options routinely gap ±50–100% intraday) blows through that floor. The hard profit_target was reliably locking in +75–160% in exactly that chaotic environment.

The 38 trades that previously exited cleanly at profit_target are converted to trailing. Many gave back gains — the trailing fires LOWER than the hard exit would have, turning winners into smaller wins or losses.

**RISK-OFF improved** (+46%) because gold (GLD, Jan 2025 and Mar 2025) was in a sustained trend where the trailing let profits compound. **BEAR/RANGE/other worsened** because those options whipsawed violently during the correction.

**Core lesson:** Trailing-on-profit-target only works in sustained trending moves. In panic/correction environments (which generate the most option premium and thus the most plays), it gives back reliable gains for speculative upside that may never materialize — the gap-day problem hits again.

**Next tried:** Keep hard `profit_target=0.75`, raise `trailing_stop_trigger` from 1.0 to 2.0 — see Attempt 5.

---

## Attempt 5 — IDENTICAL ❌ (trailing_stop_trigger=2.00, hard exit)

**Config:** `profit_target=0.75` (hard exit, code reverted), `trailing_stop_trigger=2.00`, `trailing_stop_pct=0.50`

Results byte-for-byte identical to Attempt 3 — trailing fired 0 times.

**Why:** With `profit_target=0.75` as a hard exit, no trade ever survives long enough to reach the trailing trigger at +200%. The trade closes at +75% and is gone. The only scenario where trailing could fire is a gap from below +75% to above +200% in a single daily mark — this never occurs in the dataset.

**Core lesson: `trailing_stop_trigger` is always dead code when `profit_target` is set below it.** The profit_target exit always fires first. The trailing was only reachable in Attempts 1–2 because `profit_target` was null in those runs.

**Parabolic moves (GLD +478%, HYG +620%) cannot be captured without either:**
1. Removing profit_target and accepting the gap-day risk (Attempt 2 — worse), or
2. Accepting the MFE gap as structural — those are recoveries from temporary extreme moves that reverse before the daily mark can be locked in.

**Trailing stop experiments are closed.** No further trailing configuration can improve on Attempt 3 while profit_target is in play.

---

## Attempt 6 — BETTER ✓ (profit_target lowered to 0.60)

**Config:** `profit_target=0.60`, `stop_loss=0.75`, `time_exit_dte_fraction=0.75`, `trailing_stop_trigger=1.00`, `trailing_stop_pct=0.50`

| Metric | PT=75% (Attempt 3) | PT=60% (Attempt 6) | Δ |
|--------|-------------------|-------------------|---|
| Win rate | 45.8% | **51.7%** | +5.9pp |
| Avg PnL % | +0.8% | **+5.0%** | +4.2pp |
| Avg win | +79.1% | +70.2% | −8.9pp |
| Avg loss | −65.5% | −64.8% | +0.7pp |
| Total $ | −$442 | **+$4,378** | +$4,820 |

**Exit reason shift:**

| Reason | Old n | Old total | New n | New total | Δ |
|--------|-------|-----------|-------|-----------|---|
| profit_target | 38 | +$44,879 | **50** | +$46,612 | +$1,733 |
| stop_loss | 25 | −$21,324 | 23 | −$19,941 | +$1,383 |
| dollar_stop | 19 | −$20,841 | 16 | −$17,554 | +$3,287 |
| time_exit | 33 | −$2,042 | 27 | −$3,294 | −$1,252 |

**By period:**

| Period | PT=75% | PT=60% | Δ |
|--------|--------|--------|---|
| Jul 2024 | −$5,075 | −$1,635 | **+$3,440** |
| Jan 2025 | −$5,312 | −$4,455 | **+$857** |
| Mar 2025 | +$12,497 | +$11,214 | −$1,283 |
| Feb 2026 | +$750 | +$2,556 | **+$1,806** |
| Jun 2026 | −$3,302 | −$3,302 | $0 |

**Mechanism confirmed:** 10 trades flipped from loss→profit_target (+$12,134 total). These were Type-B reversals — trades that had peaked above 60% but reversed before reaching 75%, ending at stop_loss/dollar_stop/time_exit. Catching them at 60% on the way up saved the trade. 14 trades gave up upside by exiting earlier (−$7,314), all already profit_target exits at a lower mark.

**EEM 2025-03-18 (largest cost, −$3,140):** path gapped 42%→58%→66%→74%→302%. PT=60% exits day 2 at +66%; PT=75% holds to the 302% gap-day. This is the canonical gap-day risk of a lower profit target.

**Jun 2026 zero delta confirmed:** 15/17 trades had MFE <10% — no exit rule helps straight-down trades. Signal-quality problem, not exit timing.

Path replay had projected +$5,833; actual result was +$4,820 (close; small gap from time_exit approximation in the replay model).

---

## Rules of thumb learned so far

- **Don't use trailing stops tighter than 50pts** — option spread daily vol easily exceeds 20–30%, so anything tighter fires on noise.
- **Trailing stop has a gap-day problem** — options can move 50-100pts in a single day, bypassing the theoretical floor. Trailing alone (no profit_target) is unreliable for capping winners.
- **Trailing stop is unreachable when profit_target is set below the trigger** — profit_target always fires first. In practice, `trailing_stop_trigger` is dead code alongside `profit_target=0.75`. The only way to activate trailing on parabolic moves is to remove profit_target, which makes average results worse (Attempts 2, 4).
- **Don't use loss-day cutoffs shorter than ~25 days** — directional option plays take weeks to develop; mid-trade losing streaks are normal.
- **Time exit at 50% DTE is too early; 75% is better** — many of the biggest moves (GLD, HYG, SPY) happened in the final 25–30% of the DTE window.
- **Exit rules can only help on ~55% of losers** — ~45% are straight directional failures (MFE <10%). Those require better signal quality, not better exit mechanics.
- **Stop loss at 75% is correct** — tighter stops (40–60%) make every combination worse; they fire on mid-trade dips before the trade develops.
- **Profit target at 60% beats 75%** — catches Type-B reversals (peaked 60–75%, then reversed) before they flip. Cost: exits gap-day movers 15% earlier (EEM 3×-in-a-day is the canonical risk). Net real-run improvement: +$4,820 / +5.9pp win rate (Attempt 6 confirmed).

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

---

## Financing & IVSpread gates — signal-quality filters (2026-06-19)

Analysis of the Mar-2025 panic re-run (`backtests/results.csv`, 20 trades, Mar
10–13 2025) joined to the conviction-score audit rollups (`audit/*-rollup.csv`).
This confirmed that **two signals the framework already computes but did not act
on** — `FinancingShare` (Fin%) and `IVSpread` (IVspr) — are the strongest
discriminators within the window, validating references 03/05 (financing
pollution) and 04 (IV spread predicts returns).

**Signal correlations with realized P&L (n=20):**

| Signal | Corr | Read |
|--------|------|------|
| `FinancingShare` | **−0.48** | High deep-ITM financing share → directional read fails |
| `IVSpread` | **+0.47** | Extreme-negative spread (panic put-IV inflation) → bear puts lose |
| `OIConfirmPct` | +0.40 | OI-change confirmation (ref 03) works |
| `Otm` | +0.36 | OTM-extrinsic component earns its keep |
| `Score` (raw) | +0.31 | Weak — 18/20 trades scored ≥9, no discrimination |

**Financing is an independent killer (holds inside DIRECTIONAL too):**

| FinancingShare | n | win% | avg PnL |
|----------------|---|------|---------|
| ≤ 0.5 | 14 | 85.7% | +56.9% |
| > 0.5 | 6 | 33.3% | −27.6% |

**Lift from the two gates** (deterministic replay,
`scripts/backtest/audit_gate_replay.py`; this is a filter over the *existing*
backtested trades, NOT a fresh LLM run — the reproducible way to isolate the
gate effect):

| Book | n | win% | avg PnL | total $ |
|------|---|------|---------|---------|
| Baseline (trade all) | 20 | 70.0% | +31.5% | +$7,168 |
| Financing gate (Fin% ≤ 0.6) | 16 | 81.2% | +51.5% | +$8,621 |
| Combined (Fin% ≤ 0.6 **and** not bear-with-IVspr<−25) | 15 | **86.7%** | **+57.3%** | **+$9,025** |

The two gates are **complementary**: the financing gate drops AMD/QQQ/TSLA/COIN
(3 losers + COIN's tiny +$205); the IVSpread gate additionally catches TSLA
(2025-03-12) whose Fin% (0.50) was just under threshold but whose IVspr (−39)
exposed the same put-IV inflation. Net: drop 5 trades (−$1,857 of losers, give
up +$205), book quality jumps from 70% → 87% win.

**What shipped:**
1. **Financing penalty baked into the conviction score** (`score_flow_rollup`
   in `lib/flow_summary/core.py`, `FinPenalty` column): −2 above Fin% 0.60, −3
   above 0.75, −4 above 0.90; direction-agnostic; total clamped ≥0. The 0.60
   floor spares borderline real bets (GLD 0.53 won). Documented in
   `config/conviction-score.md`. This demotes financing-dominated names out of
   `high-conv` so the LLM down-weights them at the source.
2. **IVSpread directional gate documented** as a Step-5 / backtest veto (NOT in
   the agnostic score — it is direction-bearing): a BEAR play with IVspr < ~−25
   is buying panic-inflated puts. Measured via the replay tool; recommend wiring
   into the analysis framework's Step-5 vol alignment.

**Caveats:** n=20, single regime (panic). The financing finding is the robust
one (large effect, mechanistic, matches refs 03/05, holds within intent). The
IVspr threshold is confounded with financing in this window (the extreme-IVspr
names are mostly also high-Fin%) — treat −25 as a starting point to re-validate
on chop/bull windows, not a tuned constant. **Next:** re-run the
pipeline+backtest on Jul-2024 / Jan-2025 with the financing penalty live to
confirm it self-corrects the chop/bull losses (where the tuning log showed
confidence, not regime, drove losses) — and combine with the confidence-based
sizing above.
