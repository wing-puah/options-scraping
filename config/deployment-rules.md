# Deployment rules — the deploy-day card

Which analysis plays get real capital. Read this on a deploy morning, do what it
says. Every rule here is a confirmed backtest finding — the numbers, CIs and
rollback triggers behind them live in
[`backtest-tuning/deployment-evidence.md`](backtest-tuning/deployment-evidence.md).

> **Derived on v3 rows; v4 transfer is not yet validated.** The pre-registered
> composition bridge has not fired. Until it does, deploy under these rules
> unchanged and expect them to be re-confirmed, not re-derived.

---

## 0. Before you deploy

- `make analyze` — it already depends on the `mech-regime` target, so the
  SPY/VIX table behind `mech_cell` is refreshed for you.
- Read **`mech_cell`** off the analysis row. Do not hand-compute SPY vs its
  50-day SMA; the column is on every row and backfilled.
- Budget: the analysis emits ~10 plays/day. **Deploy 1–3.**
- Entry basis: the **next trading day's OPEN**. Same-day fills were never
  modeled and are not covered by any rule here.

## 1. VETO — never deploy, regardless of score

1. **`bear_call_spread`** — intake-vetoed. If one appears it is a pipeline bug,
   not a trade.
2. **Any play when the model regime is BEAR + H-VOL.**
3. **Any credit play when the model regime is RANGE + L-VOL.**

## 2. Tier the survivors, deploy top-3/day in tier order

| Tier | What qualifies |
|---|---|
| **A** — deploy first | `bull_call_spread` when the model regime is **RANGE or E-VOL** |
| **B** — deploy if capital remains | any other `bull_call_spread`; `bull_put_spread` meeting the §3 geometry |
| **C** — skip when capital-constrained | everything else |

Tie-break **within** a tier: higher `score_total`. That is a deterministic
ordering only — it carries no signal (see §6).

Tier membership is **structure × model regime × entry geometry**. Nothing else.

## 3. Check at order entry in IBKR — not on the analysis row

**`bull_put_spread` short leg: `0.08 ≤ |delta| ≤ 0.20` AND `DTE ≤ 59`.**

- Delta is a **band, not a floor** — too close to the money is as bad as too far.
- Prefer **45–59 DTE**; that sub-band carries the whole edge.
- Miss either condition and the play drops to Tier C.

`|delta|` and DTE are not columns on the analysis row — read them in IBKR.

## 4. Bear positions — hedge sleeve only (optional)

Bear is a **hedge, not a selection**. The ladder never puts a bear play in the
deployed top-3, so this only applies to a position you take deliberately for
drawdown protection.

- **Pick:** rank the day's bear candidates by **`|delta|` DESCENDING** and take
  the closer-to-money one.
- **Size:** **≤ ½ a normal position.** Treat it as insurance, not a trade.
- **Do not** rank the sleeve by `score_total`, and **do not** buy the cheap
  far-OTM put — those are the two worst rankers tested.
- The sleeve loses money on balance. That is the price of the protection.

## 5. Exit management

Set these at order entry. `mech_cell` on the signal-date row picks the row of the
table; the **mechanical** regime governs exits, while the **model** regime
governs selection in §1–2.

| Position | Profit target | Stop | Trailing stop | Time exit |
|---|---|---|---|---|
| Debit — normal | 90% of premium paid | −75% | none | 75% of DTE elapsed |
| Debit — signal date is mech **BEAR + H-VOL or E-VOL** | 90% | −75% | **arm at +50%, then trail 50pts from peak** | 75% of DTE |
| **Bear** debit (`bear_put_spread` / `long_put`), any other date | 90% | **move to breakeven once peak P&L ≥ +50%** | none | 75% of DTE |
| Credit (`bull_put_spread`) | 65% of credit captured | **none** — risk is defined by wing width | none | none (ride toward expiry) |

Two clauses that keep the table consistent:

- **Credits are never regime-switched.** A `bull_put_spread` keeps row 4 in every
  regime.
- **The BEAR_HE trail replaces the breakeven ratchet, never stacks with it.** On
  a mech BEAR + H/E-VOL signal date you trail from the peak (row 2); everywhere
  else a bear debit ratchets to breakeven (row 3). The trail arms at the same
  +50% peak and its floor is already at or above breakeven, so nothing is lost.

## 6. What not to use

- **`score_total` is a within-tier tie-break only.** It is decision-irrelevant —
  never use it to promote a play into a tier, and never to pick the hedge sleeve.
- **Never rank a v3 row against a v4 row.** The scales differ (v3 0–100; v4 0–50,
  or 0–55 for VOLATILITY intent) and are deliberately incomparable.
- **Never use scores from rows emitted before 2026-07-13** — they anti-select.
  All live rows qualify.

---

**Why these rules, what they were measured on, and what would revert them:**
[`backtest-tuning/deployment-evidence.md`](backtest-tuning/deployment-evidence.md).
Config that implements the exits: `simulation.regime_exit` and
`simulation.structure_exit` in [`backtest.yml`](backtest.yml).
