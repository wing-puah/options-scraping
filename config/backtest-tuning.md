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

> ⚠️ **STALE (2026-07-01):** the `IVSpread`/`IVspr` findings below were computed
> on the **old** IV-spread definition (premium-weighted `mean(call IV) −
> mean(put IV)` over *unmatched* strikes/maturities, all DTE). The formula was
> re-aligned to Lin/Lu/Driessen (2013) — **OI-weighted matched-pair** (same
> strike+expiry) diff, 10–60 DTE, on settlement IV — which has a different
> distribution. The `+0.47` correlation and the **≈ −25 BEAR veto threshold must
> be re-derived** from a fresh backtest before use. The `FinancingShare` findings
> are unaffected. See `config/conviction-score.md`.
>
> **Two follow-on corrections (2026-07-01), both of which change `IVSpread`'s
> value on every row and so must precede any re-derivation:**
> 1. **Column-name bug fixed.** The matched-pair key read non-existent columns
>    (`"Expiration Date"`/`"Open Interest"`; the flow feed uses `Expires`/`Open
>    Int`), collapsing all expiries at a strike into one key — inventing false
>    cross-expiry pairs (and mis-deduping the OI factor measures, ~19% of
>    contracts). With the fix, the sign of the mean flipped to the paper-expected
>    **negative** (−0.86 vs the buggy +0.68 on 2026-06-26).
> 2. **Counterpart backfill added.** Missing pair legs are now filled from
>    Barchart price-history (`scripts/collector/fetch_counterpart_iv.py` → per-date sidecar), so
>    `IVSpread` coverage is materially higher than the flow-only ~2%. Re-derive
>    the veto **after** running `fetch_counterpart_iv --backfill` across the test window
>    and re-running the analysis pipeline so the enriched `IVSpread` reaches the
>    rows.

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

**Lift from the two gates** (one-off post-hoc analysis: the `FinancingShare` /
`IVSpread` from the audit rollups joined to the *existing* backtested trades and
filtered — isolates the gate effect from LLM noise. To carry the gate through to
real P&L, re-run the pipeline with the financing penalty live, then the backtest):

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
   is buying panic-inflated puts. Recommend wiring into the analysis framework's
   Step-5 vol alignment (the `IVspr` column is already surfaced in the rollup).

**Caveats:** n=20, single regime (panic). The financing finding is the robust
one (large effect, mechanistic, matches refs 03/05, holds within intent). The
IVspr threshold is confounded with financing in this window (the extreme-IVspr
names are mostly also high-Fin%) — treat −25 as a starting point to re-validate
on chop/bull windows, not a tuned constant. **Next:** re-run the
pipeline+backtest on Jul-2024 / Jan-2025 with the financing penalty live to
confirm it self-corrects the chop/bull losses (where the tuning log showed
confidence, not regime, drove losses) — and combine with the confidence-based
sizing above.

---

## Attempt 7 — BETTER ✓ (profit_target=0.90 + trailing_stop active)

**Motivation:** MFE analysis on 275-play dataset showed profit_target=0.60 was
firing at avg day 14 while path MFE peaked at avg day 34. Median capture of MFE
was only 57.7%. Of 135 profit_target exits, 17 captured <30% of MFE (avg MFE
$4,182, realized $928). Hypothesis: raise the target to let winners run further,
pair with a trailing stop to protect against reversals.

**Variants tested** (265 common plays with results, inner-joined across all runs):

| Config | Win% | Mean $ | Median $ | Total $ | vs Baseline |
|--------|------|--------|----------|---------|-------------|
| Baseline (pt=0.60, tr=dead) | 57.4% | $135 | $445 | $35,706 | — |
| Opt A (pt=1.50, tr=0.25) | 55.8% | $131 | $195 | $34,814 | −$892 |
| Opt B (pt=1.50, tr=0.35) | 52.5% | $109 | $75 | $28,976 | −$6,730 |
| **Opt C (pt=0.90, tr=0.25)** | **57.7%** | **$145** | **$205** | **$38,431** | **+$2,726** |

**Config (Opt C — current):** `profit_target=0.90`, `stop_loss=0.75`,
`trailing_stop_trigger=0.50`, `trailing_stop_pct=0.25`

**Exit reason breakdown (Opt C, 265 plays):**

| Reason | N | Mean $ | Total $ | Win% |
|--------|---|--------|---------|------|
| profit_target | 69 | +$1,501 | +$103,586 | 100% |
| trailing_stop | 71 | +$292 | +$20,734 | 87% |
| time_exit | 29 | +$96 | +$2,790 | 66% |
| stop_loss | 50 | −$820 | −$41,005 | 0% |
| dollar_stop | 41 | −$1,160 | −$47,567 | 0% |

**Why Opt C works, Opt A/B don't:**

- **Opt A/B (pt=1.50):** trail fires too early on normal oscillation. 96 trades
  converted from clean profit_target exits to trailing_stop exits at −$413/trade
  average (−$39,675 total). The wider trail in Opt B (0.35) made this worse: 90
  trades at −$544/trade (−$48,965 total). The floor is so low relative to peak
  that reversal catches the position before a hard cap would have.

- **Opt C (pt=0.90):** the floor at 90% acts as a clean hard exit for trades that
  peak in the 60–90% zone and don't run further (previously the 60% target was
  killing these early; now they reach 90% and exit cleanly). For trades that
  exceed 90%, the trail activates at +50% and trails 25pts — parabolic movers
  get to run. Net: 69 hard exits at $1,501 mean + 71 trail exits at $292 mean,
  both profitable populations.

**Key losers (pt → trailing_stop flips, −$1,600 worst):** XLE 2024-07-18
(pt $1,628 → trail $16, −$1,612), SPY 2025-03-27 (pt $1,448 → trail $289,
−$1,160). These are fast-reversal trades in the 60–100% range that would have
been captured by the old 60% target but now overshoot 90% and reverse before
the trail locks in enough. Accepted cost.

**Key gainers vs baseline:** XLE 2024-06-17 (dollar_stop −$1,294 → pt +$3,539,
+$4,833), IWM 2024-06-17 (stop_loss −$937 → pt +$2,667, +$3,604), PDD
2024-08-19 (pt $917 → pt $2,772, +$1,855 from longer hold).

**Rules of thumb updated:**
- `profit_target=0.90` is the new floor — catches clean winners without
  cutting the early part of the move.
- `trailing_stop_trigger=0.50` + `trailing_stop_pct=0.25` is now live and
  meaningful (trail activates before profit_target fires on big movers).
- Widening the trail beyond 0.25 is counterproductive — gives back more than
  it saves (Opt B confirmed).

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

## 2026-07-08 — Framework evaluation: signal-quality study on MFE/MAE basis (not an exit experiment)

Audit of the analysis framework against `backtests/v1_20260625_results.csv`
(292 rows, signal_eod basis, pre-scoring-redesign labels) and
`backtests/results.csv` (116 rows, next_open basis). Because the exit rules are
still under tuning, the primary basis here is **exit-independent**: "worked" =
path MFE ≥ +30% of premium, "never moved" = MFE < +10%. These baselines don't
move when exit knobs do, so they're reusable for future exit studies.

**DTE gradient — replicates on both datasets, exit-independently.** Short-dated
plays are worse *signals*, not an exit artifact:

| DTE band | v1 n | v1 never<10% | v1 med MFE | v1 med MAE | cur n | cur never<10% | cur med MAE |
|---|---|---|---|---|---|---|---|
| 0–21 | 23 | 39% | +0.33 | −1.00 | 5 | 40% | −1.00 |
| 22–45 | 89 | 26% | +0.46 | −1.00 | 23 | 22% | −1.00 |
| 46–90 | 101 | 14% | +1.03 | −0.97 | 48 | 21% | −1.00 |
| 91–180 | 45 | 7% | +1.24 | −0.82 | 21 | 10% | −0.97 |
| 180+ | 34 | 6% | +0.75 | −0.49 | 19 | 5% | −0.58 |

Shipped as framework Step-4 "DTE discipline" (default ≥45 DTE; shorter only
with a named dated catalyst) + a prompt-contract discipline rule + a method-file
bullet in both engines.

**Retired high/medium/low labels did not discriminate** (v1, all rows predate
the numeric-score redesign): worked-rate high 68% / medium 72% / low 77%;
realized win 57% / 56% / 62%; mean realized $554 / $205 / $145 (the $ ordering
is exit-path-driven, not signal-driven). This is the baseline `score_total`
must beat. The `score_total`/`score_*` columns in results.csv are **entirely
empty** — no backtested row carries the new score yet — so score validation is
the standing follow-up (recipe in `config/analysis-roadmap.md`, alpha
attribution).

**Intent: HEDGE ≈ DIRECTIONAL on signal quality** (worked-rate ~75% vs ~73%;
v1 n=59 vs 200), but HEDGE's realized-dollar lead ($664 vs $181 mean) rode
median MAE ≈ −100% paths before recovering — entangled with the exit profile,
so documented in the framework as "first-class plays" with that caveat, not
promoted as a superior signal.

**Playbook distribution is degenerate:** TF = 73% of v1 plays; VC/DP ≈ zero on
both sets (expected — the per-name GEX gate that selects them isn't an input
yet; flagged UNEXERCISED in the framework). Current-window small-n reads:
GE weak (n=8, median MFE +0.07, 50% never moved), PU strong (n=11, median MFE
+1.85), MR strong on v1 (n=5, 100% worked). All small-n — log only.

**Path fact relevant to stops:** median MAE is ≈ −0.9 to −1.0 in nearly every
slice — a near-total drawdown is a *normal* excursion for these plays, which is
the zone `stop_loss=0.75` fires into. Consistent with Attempt 3's theta-decay
finding; worth remembering when tuning stop levels.

**Weak-signal correlations on the current 116-row set** (realized pnl_pct
basis, so exit-contaminated — retune flags, not conclusions): `oi_confirm_pct`
r ≈ −0.03 (vs +0.40 on the Mar-2025 n=20 that set the ±2/±1 bands — flagged in
`config/conviction-score.md`), `cpir` r ≈ −0.20, `iv_pct` r ≈ −0.16,
`iv_spread` r ≈ +0.09, `dte_entry` r ≈ +0.21.

---

## 2026-07-12 — Three-run evaluation of `backtests/to_evaluate/` (v1 / v2 / v3) — replaces the 2026-07-10 evaluation

Same backtest set as the 2026-07-10 study, which was written when v3 had only
53 evaluated trades in a single BULL+L-VOL month. v3 is now complete over the
shared window — **154 evaluated real trades (2024-06 → 2025-12)** plus a full
proxy sweep (235 rows / 211 evaluated) — so this section supersedes the old
one entirely. Two of its loudest reads are REVISED below (score_total
"inversion" → credit-composition confound; credit-pt-basis suspicion →
resolved, not a bug).

Runs: **v1** (`v1_BacktestResults_20260625`, 122 evaluated — signal_eod entry
basis, pre-credit-split analysis: 1 credit row in 122, and its months only
partially overlap (has 2025-02, lacks 2024-06/07) → reference only, NOT
decision-grade for the rollback question), **v2** (115 evaluated, next_open),
**v3** (`BacktestResults`, current pipeline, 154 evaluated, next_open).

### Headline (real backtest rows)

| run | n | win% | mean pnl% | median | total $ | mean MFE | capture* |
|---|---|---|---|---|---|---|---|
| v1 | 122 | 60.7% | +0.20 | +0.61 | +24,027 | +1.15 | 0.14 |
| v2 | 115 | 48.7% | +0.03 | −0.08 | +12,336 | +0.90 | 0.11 |
| v3 | 154 | 48.1% | −0.02 | −0.24 | +4,394 | +0.86 | 0.04 |

*capture = Σrealized$ / ΣMFE$ over MFE>0 rows.

### Rollback verdict: CANNOT BE DETERMINED — do not roll back on this evidence

No v2-vs-v3 P&L comparison clears significance, and the sign of the comparison
depends on which book you look at:

- **Pooled real book:** Mann-Whitney p = 0.365. **Debit-only p = 0.583**
  (mean +0.17 v2 vs +0.13 v3 — statistically identical). **Credit-only
  p = 0.249.** Version-unique picks p = 0.112.
- **Combined real + proxy `strike_expiry_tweak` book** (both real-priced) the
  sign FLIPS: v3 +$51,772 (n=282, mean +0.13) vs v2 +$14,654 (n=168, mean
  +0.05), p = 0.494. The v3 edge is concentrated in its 128 tweak rows
  (+$47,378, half in 2025-03) — coverage/selection evidence per the proxy
  caveat, not exit-grade P&L, but it blocks any "v3 is worse" conclusion.
- **The ONLY statistically significant v2→v3 difference is behavioral, not
  quality: credit-structure emission share 19% → 34%** (chi² p = 0.012;
  combined books 18% → 33%). Credit trades lose in BOTH runs under the
  still-unvalidated credit exit profile (v2 −0.52 mean / 36% win, n=22;
  v3 −0.30 / 46%, n=52). v3's aggregate drag vs v2 is structure MIX feeding a
  known-broken exit profile, not worse per-trade signal quality.

Practical read: rolling back to v2 would mostly be rolling back the credit
emission rate. The cheaper, better-targeted moves are the credit-side items in
the queue below — and v3's book finally provides the credit-heavy,
multi-cluster window (52 real credit rows across 2024-07/08 + 2025-03/04) that
Attempts 8/9/11 were blocked on.

### Factors that predict outcome (analysis-tab columns only)

1. **Structure (from the play text) is the dominant factor.**
   `bear_call_spread` is toxic in BOTH versions — v2: −0.95 mean, 11% win,
   −$4,363 (n=9); v3: −0.82, 17% win, −$8,632 (n=18). Dropping bear_call alone
   turns v3's book +$4,394 → +$13,026 and v2's +$12,336 → +$16,699.
   Version-independent → a structure gate, not a rollback, addresses it.
   Debit vs credit overall: v3 debit +0.13 / credit −0.30.
2. **score_total pooled ρ −0.27 (p=0.001, n=154) — but it is a
   credit-composition confound, NOT a per-trade inversion.** REVISES 07-10:
   the scorer rates credit plays higher (mean 66.8 vs 55.8 debit), and credit
   loses. Within-side ρ: debit **−0.01** (p=0.95), credit −0.13 (n.s.). The
   ≥70 band still fails overall (n=38, 34% win, −0.40 mean; its worst cell is
   score≥70 ∧ credit: n=22, 32% win, −$6,768). Bottom line: score_total has no
   positive predictive value anywhere yet (flat within side, anti-selects via
   structure channel). The fix target is the score→structure-choice channel,
   not the rubric weights per se.
3. **score_vol is the only component negative WITHIN side** (debit-only
   ρ −0.20, p=0.047; pooled −0.31). 07-10's `score_price ρ −0.41` driver
   softens to +0.02 within debit — it was regime/composition, as suspected.
4. **iv_pct: third consecutive negative read (ρ −0.24, p=0.005; v2 −0.20,
   p=0.054) — but the hard >0.6 veto FAILS on dollars** and is rejected as a
   gate: the dropped set totals +$5.8–5.9k in BOTH runs (mean ≈ 0, 49% win —
   big winners live in the high-iv bucket too). Keep iv_pct as a sizing/flag
   input, not a filter.
5. **horizon** weakly positive (v2 ρ +0.20 p=0.034; v3 +0.10 n.s.) —
   consistent with the standing ≥45-DTE discipline, nothing new to ship.
6. **oi_confirm_pct, cpir, iv_spread, iv_skew: still ~flat** on realized basis
   (|ρ| ≤ 0.15, all n.s., both runs) — third dataset where the rollup signals
   don't discriminate realized P&L.
7. **Regime (market_regime label): BULL+L-VOL again the worst big bucket**
   (v3 n=40, −0.21) vs RANGE+E-VOL +0.49 (n=27) and BEAR+E-VOL +0.48 (n=9).
   New wrinkles vs the pooled 07-10 table: BEAR+H-VOL flips negative on v3
   (−0.53, n=15) and RANGE+L-VOL is bad (−0.34, n=17) — the "every BEAR bucket
   positive" pooled read does not survive on v3 alone.
8. **(Observation, not an analysis-tab column:) consensus names lose.** Picks
   appearing in BOTH v2 and v3 (same signal_date+ticker, 48 rows each, 79%
   same structure): ~34% win, −0.30/−0.34 mean in both runs. Version-unique
   picks: 55–58% win, +0.13/+0.27. The obvious/crowded flow names are the bad
   trades regardless of which pipeline version reads them.

### 07-10 queue item resolved: credit profit-target basis is NOT broken

All 10 v3 credit rows with path MFE ≥ +0.90 that exited `stop_loss` have
**mfe_day > days_held (10 of 10)** — the peak came AFTER the exit; MFE/MAE are
full-path-to-cap metrics, so no pt-basis bug. The real pattern: the 1×credit
stop fired (mean realized −1.32), then every one of these positions recovered
to ~full credit by expiry (9 of 10 are July-2024 bull_puts — the same whipsaw
cluster Attempt 9 flagged). This is now the single biggest quantified credit
pain point (10 trades × ~2.3 swing), but "no stop" was still worse in
aggregate in Attempt 11 — it goes to the credit exit study, not straight to a
config change.

### Actionable queue (in value order)

1. ~~**Re-run the credit exit study on v3's credit book**~~ — **DONE
   2026-07-13, see §Attempt 13.** Structure split resolved it: credit
   `stop_loss` removed (1× → null; pt 0.65 kept), the 10 whipsaws priced at
   +$3,646 on the bull_put book.
2. ~~**bear_call gate**~~ — **DONE 2026-07-13, see §Attempt 13.** Shipped as
   `entry.structure_veto: [bear_call_spread]` in config/backtest.yml (intake
   veto, honored by backtest + proxy); the credit study confirmed no exit rule
   redeems it (best variant still −$4.9k on n=37 combined).
3. ~~**Score→structure channel**~~ — **DONE 2026-07-13, see §Attempt 13c.**
   Root cause was the reverse arrow (structure→score via the self-fulfilling
   Vol-alignment rubric row); rubric + prompt contract rewritten, Step-4
   decoupling rule added. Within-side ρ re-test pends post-change emissions.
4. ~~**Per-regime exit switch** (standing, gated)~~ — **RE-CHECKED 2026-07-13,
   see §Attempt 13b: stays gated.** BEAR/H-VOL trail survives only weakly (no
   longer either group's winner), L-VOL tef-null fails LOO; new lead candidate
   for the eventual switch is `pt 1.10+` in E-VOL/RANGE (2025-03-concentrated,
   needs out-of-window validation).
5. ~~**iv_pct veto: rejected as a hard gate**~~ — **DONE 2026-07-13.**
   Downgrade recorded where operators read the column:
   config/conviction-score.md §IV percentile now states the veto was
   dollar-tested and rejected (dropped set +$5.8–5.9k both runs) and that high
   `iv_pct` is a sizing haircut / monitoring flag only. No veto was ever
   implemented in config/code, so nothing to remove. (Distinct from the stale
   IVspread ≈ −25 BEAR veto note in backtest-reference.md — that one still
   awaits re-derivation on the matched-pair definition.)

Roll-back re-check trigger: revisit only if the credit-side fixes (1–3) fail
to close the gap on a fresh window, or if a debit-only regression vs v2 ever
reaches significance (today p = 0.583, wrong direction to worry).

## Attempt 13 — credit exit study on v3's credit book: bear_call vetoed + credit stop removed (2026-07-13) ✓

**Motivation:** queue items 1+2 from the 2026-07-12 evaluation. v3's 52 real
credit rows (2024-06→2025-12, 6 months incl. the 2024-07/08 and 2025-03/04
clusters) finally break the March-TSLA single-cluster trap that froze Attempts
8/9/11. Inputs rebuilt from the v3 sheet exports (`backtests/to_evaluate/` →
`backtests/results.csv` + `results_proxy.csv`); study scripts' imports updated
for the `lib.barchart` refactor. **Calibration gates: real 52/52, tweak 42/42;
4 bs rows excluded as the documented ±0.0001 precision ties.**

**The decisive cut Attempts 8–12 never made: split the credit book by
STRUCTURE before tuning.** The global variant table is two opposite books
averaged together:

| Variant | bull_put real (n=34) | bull_put real+tweak (n=56) | bear_call real (n=18) | bear_call real+tweak (n=37) |
|---|---|---|---|---|
| PROD pt.65 sl 1× | +$1,836 (21/34) | +$2,814 (37/56) | −$8,632 (3/18) | −$11,221 (12/37) |
| **sl none (dollar stop only)** | **+$5,482 (31/34)** | **+$6,573 (48/56)** | −$14,574 | −$17,656 |
| pt .50 | +$132 (Δ −$1,704) | +$2,108 (Δ −$706) | −$4,608 (best) | −$4,912 (best) |
| sl 1.5× | +$3,356 (Δ-LOO2 −$286) | +$3,978 (LOO2 −$641) | −$11,193 | −$14,903 |
| trail .50/.50 | +$1,224 (Δ −$612) | +$2,863 (Δ +$50) | −$6,209 | −$7,990 |

**Shipped 1 — `entry.structure_veto: [bear_call_spread]` (config/backtest.yml,
new intake veto honored by both backtest.py and proxy.py; skip category
`vetoed`, proxy records vetoed plays as unevaluable instead of pricing them).**
bear_call is unredeemable by exit rules: PROD −$8.6k real / −$11.2k combined at
12–17% win, and the BEST variant on the combined set still loses $4.9k. Add
v2's −$4.4k (11% win, n=9) → version-independent, month-spread. The 2026-07-12
"pt .50 Δ-LOO +$452" tease was 100% bear_call rows (the same March-2025 TSLA
pair again, +$1,684/+$1,868); within bull_puts pt .50 is *negative*. Every
global credit-variant verdict in Attempts 8–12 was distorted by this mix.

**Shipped 2 — `simulation.credit.stop_loss: 1.00 → null`** (premium-based stop
removed; dollar_stop from risk sizing + defined-risk structural max loss remain
the backstop). This directly prices the 07-12 finding that 10/10 credit
stop_loss exits with path-MFE ≥ +0.90 recovered to ~full credit after the stop
fired. On the post-veto book (bull_puts): real +$1,836 → +$5,482 (win 21/34 →
31/34, Δ +$3,646, Δ-LOO +$2,652, Δ-LOO2 +$1,840); combined real+tweak n=56
agrees (+$2,814 → +$6,573, LOO2 +$1,954). Worst movers are bounded: TSLA rides
to dollar_stop −$1,166, KWEB expires −$892. `sl 1.5×` (halfway house) does NOT
survive LOO2 — the recovery is to ~full credit, so only full removal captures
it. pt stays 0.65 (`pt .50 sl none` is worse than `sl none` alone within
bull_puts, LOO2 −$26).

**Honesty caveat (selection discipline):** ~80% of the sl-none dollar gain
(+$2,995 of +$3,646 real) is the correlated July-2024 whipsaw week (9 same-week
bull_puts stopped in the drawdown, all recovered by expiry). Per-trade LOO
can't see that correlation. What keeps it shippable: the behavioral read is
10/10 (not a P&L accident), the non-July months are still net +$651 real /
+$764 combined with only −$46 against, the combined set agrees in sign and
magnitude, and the downside of being wrong is bounded by dollar_stop +
defined-risk sizing. **Rollback trigger:** if the next credit-heavy window
(≥15 fresh bull_put rows) shows sl-none losing to sl-1× there, restore the 1×
stop and log it here.

Not shipped: pt .50 (bear_call artifact, hurts bull_puts), underlying-breach
stops (still negative on bull_puts: und ±1% Δ −$2,032 combined — Attempt 9/11's
conclusion stands), trail variants (flat-to-negative within bull_puts).

### Attempt 13b — per-regime exit switch re-check on v3 (queue item 4): stays GATED ❌

`combined_exit_study.py --side debit` re-run on the v3 book (real 102 —
calibration 102/102 after fixing a 1-ulp float tie in the replay boundary
check (XLF 2024-06-21 sat exactly on sl=0.75; replay now rounds pnl to 10
decimals) — plus 86 tweak). The Attempt-12 group hypotheses, re-checked:

- **BEAR trail .50/.50** — still positive (Δ +$1,359, Δ-LOO +$493, n=34) but
  no longer the group winner: `pt 1.25 no trail` dominates BEAR (Δ-LOO
  +$2,282). Weakened.
- **H-VOL trail .50/.50** — still positive (Δ +$2,296, Δ-LOO +$1,135, n=45);
  group winner shifted to `BE ratchet @.50 + trail .50/.75` (Δ-LOO +$2,356).
  Direction (some giveback protection in H-VOL) persists; the specific variant
  doesn't.
- **L-VOL tef null** — Δ +$1,249 collapses to Δ-LOO +$42: "no robust winner".
  NOT confirmed on v3.
- **DIRECTIONAL tef null** — not checkable: v3 play cells don't parse into the
  `[…|intent|…]` bracket the study's intent tag expects (all rows land in
  `[?]`); fix the intent regex before the next re-check.

New wrinkle worth watching, NOT shipped: **raising the debit profit target
(pt 1.10–1.25, no other change) is the loudest global signal on v3**
(combined Δ-LOO +$5,650/+$6,791; real-only Δ +$7,585/+$5,570) — but on the
real book ~88% of it is 2025-03 (panic month, V-shaped recoveries blowing
through +90%), and it's actively bad in L-VOL (Δ-LOO −$1,772/−$4,343) and BULL.
Same story as every exit read since Attempt 12: the knob is regime-conditional
(E-VOL/RANGE/BEAR want to let winners run; L-VOL/BULL don't), which is exactly
the per-regime switch — and a switch fitted on the same window that motivated
it still needs out-of-window validation before it ships. Gate unchanged;
`pt 1.10 in E-VOL` is now the lead candidate cell when that validation window
exists.

### Attempt 13c — score→structure channel decoupled (queue item 3) ✓ (validation pending)

The 07-12 framing had the arrow backwards. It is not that high scores select
into credit structures — it is that **choosing a credit structure mechanically
raised the score**, via Step 5's Vol-alignment row, whose rubric was "IV/term
structure/skew fit the chosen structure (cheap-or-rising for debit,
rich-or-falling for credit)". Step 4's ladder already forces the structure to
match IV, so every ladder-consistent play banked those points automatically:
the component was consistency-with-your-own-rules dressed as evidence.
Measured on v3: score_vol mean 11.3 credit vs 9.6 debit; iv_pct mean 0.89
credit vs 0.61 debit; within credits score_vol tracks iv_pct (ρ +0.36) — i.e.
the vol row paid MORE for RICHER IV credits, exactly the losing bucket (iv_pct
ρ −0.24 on P&L). And score_vol is now negative within BOTH sides on v3
(ρ −0.20 debit p≈0.05, −0.21 credit), confirming 07-12 factor #3.

Shipped (all four analysis touch points kept in sync):
- **`config/analysis-framework.md` Step 5** — Vol-alignment rubric rewritten:
  score whether vol conditions support the *thesis* (realized-vs-implied gap,
  term structure, skew/IVspr/IVskew, expected IV path), never whether the
  structure matches the IV level (that consistency is Step 4's job; a mismatch
  invalidates the play instead of scoring low). Rationale note added beside
  the rubric so the old wording doesn't creep back.
- **`config/analysis-framework.md` Step 4** — explicit decoupling rule:
  conviction level never picks the structure in either direction (no
  de-risking high conviction into credits, no leverage-reaching on weak
  ideas); structure comes only from playbook + IV ladder. Plus the Attempt-13
  bear_call suspension callout (TF-S bearish now expresses as bear put debit
  or passes; table + bullets updated).
- **`scripts/analysis_pipeline/config.py`** (`ANALYSIS_PROMPT_CONTRACT`) —
  `score.vol` and `structure` field descriptions synced to the above (bear
  call spread: NEVER emit).

**Validation (open):** re-test within-side ρ (score_total and score_vol vs
realized) on rows emitted AFTER 2026-07-13 once a decent post-change sample
exists; also check the credit-emission share drops back toward v2's ~19% now
that bear_call is suspended and the vol row no longer subsidizes rich-IV
credits. Rubric *weights* deliberately untouched — per the 07-12 read, fix
the channel first, then re-measure.
