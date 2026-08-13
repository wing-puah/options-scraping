# Study map — what each file in `scripts/backtest_study/` is trying to prove

> **There is a rendered version of this page**: [`docs/study-map.html`](../../docs/study-map.html)
> — open it in a browser. It carries everything below *plus* what each study's
> last run actually printed, quoted out of `backtests/study_output/`, and the
> newest sections of [`current.md`](current.md). It rebuilds itself after every
> `python -m scripts.backtest_study run …` and every `make study-review`; to
> rebuild by hand, `make study-map` (or `make study-map-open`).
>
> Its per-study verdicts come from `scripts/study_map/catalog.py`, which is the
> file to edit when a verdict changes — a study whose entry is missing there
> fails the test suite. This markdown is the prose companion; keep the two
> saying the same thing.

One page, read top to bottom. `scripts/backtest/` **prices** the book;
`scripts/backtest_study/` **argues** about it. Nothing here is imported by
production, nothing runs on a schedule, and no study writes config — a study
ends in a plain-text report that becomes an addendum in [`current.md`](current.md),
and a human decides whether anything ships.

---

## The shape of the whole thing

```
                    ANALYSIS ENGINE  (v3 frozen · v4 live)
                              │  emits plays
                              ▼
        ┌─────────────────────────────────────────────────┐
        │  THE BOOK          book.py                      │
        │  real rows (BacktestResults) + proxy rows        │
        │  (BacktestProxy, strike/expiry tweak only)      │
        │  calibration gate: a row that doesn't replay     │
        │  to its stored outcome does not get in           │
        │                                                  │
        │  n is the ~118 SIGNAL DATES, not the ~1,100 rows │
        └─────────────────────────┬───────────────────────┘
                                  │  every study replays through
                                  ▼
        ┌─────────────────────────────────────────────────┐
        │  harness.py    FROZEN exit-replay engine         │
        │                (DO NOT EDIT — every recorded     │
        │                 conclusion rests on it)          │
        │  protocol.py   purged walk-forward · date-       │
        │                clustered CIs · LOO · window cuts │
        │  underlying*.py stock bars + as-of-entry price   │
        │                 features (no look-ahead)         │
        └─────────────────────────┬───────────────────────┘
                                  │
        ┌───────────────┬─────────┴────────┬───────────────┐
        ▼               ▼                  ▼               ▼
  ① SELECTION     ② MANAGEMENT       ③ STRUCTURE     ④ DEPLOYMENT
  what to trade   when to get out    what wrapper    can I run it
        │               │                  │               │
        │               │                  │               │
   mostly NULL     where the edge      one +0.085     $25k account
   0/496 subsets   actually lives      that dies      caps survive
   0/15 ML cells   (2 rules shipped)   out of sample  window doesn't
        │               │                  │               │
        └───────────────┴────────┬─────────┴───────────────┘
                                 ▼
                    config/deployment-rules.md
                    the operator card — top 3/day, tiers A/B
```

**The one-sentence result of the whole programme:** selection is not tunable
from the columns we have; the money is in the exit rules and in position
management. Every selection study returns a null; two exit studies shipped.

---

## ① SELECTION — "which plays are worth taking?"

| File | The question | Verdict |
|---|---|---|
| `regime_gap_reread.py` | Numbers only, no interpretation: build the pooled book and print the report. | Baseline snapshot other studies import verbatim. |
| `mech_regime_recut.py` | Does a *deterministic* regime label (pure function of SPY/VIX history at the signal date) beat the model's free-text regime? | Overlay adopted — `mech_cell` is now a column and keys the shipped BEAR_HE exit. |
| `bear_position_study.py` | Pre-registered cuts on `bear_put`: is it a **selection** problem (E<0) or an **exit** problem (E>0, R<0)? | DEMOTE criteria all fire (n=164). |
| `bear_arm.py` | B1 — is there *any* bear subset defined at decision time that isn't negative? B2 — is the exit just mis-tuned? | **B1 NO** (0 of 496 subsets). **B2 YES** → `be_after: 0.50` shipped. |
| `ml_combination.py` | Does any learned combination (structure × regime × geometry × enrichment) beat the score-free ladder out of sample? | **NULL** — 0 of 15 model × strategy cells. Re-open only on new **columns**, never new models. |
| `v4_bridge.py` | v4 dropped two prompt factors. Does the v3-derived ladder still apply to what v4 *emits*? | Written before the data existed. Waiting on v4 rows. |

## ② MANAGEMENT — "when do I get out?" ← where the edge is

| File | The question | Verdict |
|---|---|---|
| `exit_mechanism_study.py` | The original grid: replay stored daily marks under alternative exit rules, real rows only. | **SHIPPED** the production debit profile — pt 0.90 / sl 0.75 / tef 0.75, no trail (Attempt 10). |
| `combined_exit_study.py` | Same grid, bigger tuning set (real + proxy-priced rows pooled). | PROD confirmed best *global* config — but exits are regime-conditional, which motivated the switch studies below. |
| `underlying_exit_study.py` | Credit spreads: stop on the **underlying** breaching a level instead of on the mark? | ❌ Nothing shipped (Attempt 9). |
| `exit_switch_mech_study.py` | Per-regime exit switch keyed on the mechanical regime — stable where the model-keyed version failed LOO? | **BEAR_HE cell SHIPPED** (trail 0.50 / trigger 0.50). L-VOL and RANGE/BULL cells stay gated. |
| `exit_switch_structure_study.py` | Q1: does a bear_put-keyed trail pass the same ship gate? Q2: is BEAR_HE secretly just a *composition proxy* for that structure effect? | Guards the shipped rule against the trap that killed `oi_confirm_pct`. |
| `bear_giveback.py` | 82% of bear rows go green then give it back. Can a breakeven ratchet capture it, and does the underlying path explain it? | `be_after` grid does **NOT** ship beyond what's already live; the give-back pattern is in the **underlying**, not the mark. |
| `next_day_move.py` | Move the give-back question to day 0 (knowable at the close): cut positions the stock didn't confirm? | ARM C doesn't clear the confound → **no rule**. Sensitivity is structural. |
| `volume_signal.py` | Share volume — the one column on disk no study had read. Does unusual-O/S (flow contracts / share volume) condition exits, or anything? | **NULL** — no R separation on non-bear debit, and the one frozen exit variant is negative out-of-fold (LOO share 1%). Column closed; no version bump. Bear's monotone os_ratio read is a post-hoc carry-forward only. |

## ③ STRUCTURE — "am I expressing the signal in the wrong wrapper?"

| File | The question | Verdict |
|---|---|---|
| `bear_rewrap.py` | A bear *spread* sells the lower put — so it gives away the vol expansion that makes a bear position pay. Drop the short leg? | Wrapper is worth **+0.085** and it **does not hold in 2026**. Nothing ships; re-runnable as dates land. |
| `vol_sleeve.py` | Synthesize straddle / strangle / calendar on the dates the engine already signalled. Is there a vol sleeve? | **CLOSED** — the straddle clears its gate then dies out of sample, and it *doubles* existing exposure (wrong-signed correlation). Only the **calendar** survives. |
| `calendar_hedge.py` | Re-derive that one survivor under a pre-registered pick rule and a strict fill rule. | Gates all pass (R4 reproduces exactly), but H2 **power-stops at n=6**. Blocked on new dates, not refuted. |

## ④ DEPLOYMENT — "can I actually run this?"

| File | The question | Verdict |
|---|---|---|
| `bear_deploy.py` | Bear selection is unfixable — but is bear worth holding as a **hedge**? Four estimands: D1 joint selection×exit, D2 hedge contribution, D3 sizing, D4 conditional pick. | **D2 MET** (bear pays on the deployed book's worst dates, corr −0.13). **D4 ADOPTED** (pick bear by \|delta\| *descending*). D1/D3 not met. Bear = a hedge, not a selection. |
| `account_sim.py` | The ladder assumes infinite capital. Does a real **$25,000** account — paying for positions, holding reserve, respecting a delta cap — still produce a book? | Caps survive; the **window** doesn't. **Delta-notional binds, not cash.** Feasibility only, nothing ships. |

---

## Infrastructure (not studies — `run.py` lists these in `INFRA`)

| File | Role |
|---|---|
| `run.py` | The runner. Writes `backtests/study_output/<name>-latest.txt` with a provenance header (git sha, dirty flag, exact argv, input row counts + mtimes) so no write-up can attribute numbers to the wrong export. |
| `harness.py` | **FROZEN** `Trade`/`replay`. Prices nothing — it replays a stored mark series. Every recorded conclusion depends on its exact clamps and rounding. Changing the exit mechanism means *copying* this file, never editing it. |
| `book.py` | Pooled real + proxy loader. `bs_options_hist` rows are excluded by default — they're priced *from* the model that scores them. |
| `protocol.py` | The four things every conclusion rests on: date clustering, purging + embargo, same-dates comparison, window dominance re-cuts. |
| `underlying.py` | Daily stock bars — real OHLC, falling back to close-only `Price~`. The widening `harness.py` is frozen out of. |
| `underlying_features.py` | As-of-entry price-*state* columns (rv20, Parkinson, semivar, ATR%, efficiency ratio, VRP, beta). This family is the ML re-open — none of it existed when B1 searched 496 subsets. |
| `volume_features.py` | As-of-entry *volume* columns (unusual-O/S, relative-volume z, Amihud), split-guarded, rescaled tickers withheld from the window features. Built for `volume_signal` (NULL), kept for future pre-registered use. |

---

## How to read any one report

1. **Check the header.** Row counts and mtimes of the input exports. Two runs on different exports are not comparable — that has caused a wrong attribution before.
2. **Check the calibration gate.** Most studies open by proving production rules reproduce the stored `exit_reason` / `days_held` / `realized_pnl_pct`. A non-zero exit here is the gate *working* — don't route around it.
3. **Check the pre-registration.** Nearly every study names a `current.md` section written *before* it ran. If a number isn't covered by a pre-registered criterion, it's an observation, not a result.
4. **Metric definitions** live in [`glossary.md`](glossary.md). `E` = P&L at path cap (selection only). `R` = realized under the exit rules (selection + exit). `E<0` means no exit rule can rescue it.

## Recurring traps this log has actually fallen into

- **Composition, not signal.** A cut looks predictive because it changed the *mix* of structures, not because the variable matters. Killed `oi_confirm_pct`, `iv_pct`, and the `score_total` bands.
- **Grading against a baseline production doesn't run.** Changed a decision twice. Always compare against the *shipped merge*, not against a clean default.
- **One window carrying an effect.** Every headline is re-cut ex-Mar–Apr-2025 and ex-Feb–Apr-2026.
- **Row count ≠ sample size.** Rows inside a signal date share the tape. `n` is ~118.
