# Study map — what each file in `scripts/backtest_study/` is trying to prove

> **There is a rendered version of this page**: [`site/study-map.html`](../site/study-map.html)
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

The four sections below are the same order the studies sit in on disk:
`f1_selection/` → `f2_management/` → `f3_structure/` → `f4_deployment/`
("pick it, manage it, wrap it, fund it"). The Infrastructure table at the
bottom — `run.py`, `harness.py`, `book.py`, `protocol.py`, the `underlying*`
and `volume_features` families — lives in `lib/`: import-only, and it argues
nothing, so it carries no verdict and no family of its own.

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
                    docs/deployment-rules.md
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
| `text_features.py` | Does the model's own prose (invalidation, trigger, specificity, thesis/alt shape, blind-labelled thesis type and confidence, citation faithfulness) separate outcome within structure × tier, or raise mean R and PF as a gate on the shipped ladder? | First run 2026-09-02 (era v4 PRIMARY, labels 100%, citations 148/148 dates): **every feature NULL or UNDERPOWERED in all three arms** — `PROMPT-ROBUSTNESS FINDINGS ... none`, `ENTRY-GATE CANDIDATES ... none`. Only 1.6% of cited flow figures are unmatched in the raw feed. v3 SECONDARY the same, with one `alt_ratio` veto that clears the conjunction but lowers mean R (caught by the catch-all). Text was the last untested column family and it nulls like the numeric ones. |
| `prompt_eval.py` | The loop step: does a CANDIDATE prompt beat the shipped one on the same dates under the shipped ladder (paired ΔR, PF, hallucination rate, zero bear_call leaks), with accumulated live dates as the primary evidence? | Harness built 2026-09-02; date sets declared by rule; PROD noise floor is the first scored step. No candidate scored yet — scoring needs a committed candidate directory. MET is a v5-bump proposal, never a ship. |
| `macro_event_study.py` | Do scheduled macro events (FOMC decisions, minutes, CPI, NFP, PCE) show up in the book — in entry IV (`vrp`), in outcomes (R/E), or in exits? Distance keys off the **entry session**, pre-open vs post-open decides day 0. | Era v3 (795/118): ONE powered cell — NFP AFTER w≤5 — null on `vrp` and R; every FOMC/minutes/CPI/PCE cell is underpowered. Context: NFP = VIX build-then-bleed + post-print SPY relief; FOMC = nothing (no pre-FOMC drift). ARM X's raw trigger **died under the survival control** → `macro_event_exit` DE-QUEUED. Nothing ships; no v5 bump; passive re-run as the book grows. |
| `trigger_entry.py` | Production enters every non-vetoed play unconditionally at the next open and ignores the stated trigger. Does entering only WHEN that trigger level is first crossed — at the crossing session's CLOSE, contracts re-sized, the whole trade re-priced through the frozen harness — beat it once the entry price PAYS for the confirmation? `exit_from_text` E2 censused the selection but kept the next-open fill, so the favourable move sat inside its ENTERED number. | First run 2026-09-04 (era v4 PRIMARY, 853 in scope / 147 dates): **`tally: {'NULL': 1, 'PRICED-AWAY': 2}`** — no CANDIDATE. E2's selection census reproduces exactly at shipped pricing (`N=3   579 rows/145d +0.212    274 rows/121d -0.048`) and the re-pricing eats it (`ARM T N=3 ... DeltaR -0.0137`, `N=5 ... -0.0257`, CIs spanning zero). ARM C localises it: waiting only helps rows the day-0 mark had already marked DOWN (`<= -25%` band +0.6256 vs `> +25%` band -0.4187) — `next_day_move`'s confound, not a text finding. The N grid flips sign, so criterion 7 fails everywhere; ARM D is flat on the shipped card. v3 SECONDARY: `tally: {'PRICED-AWAY': 3}`. **The trigger picks a better book and the confirmation costs what it is worth.** |
| `emission_timing.py` | Same signal, later entry: do repeat emissions of a persisting (ticker, structure) underperform first emissions, and does a fill delayed 1–3 sessions past the signal decay the edge — conditioned on the pre-signal price vector? | First run 2026-08-19 (era v3): ARM P **NULL** (+0.054, CI spans zero; positive lean = labelled watch for new dates). ARM L **LAG-TOLERANT** — the publishable finding: no lag in {1,2,3} sessions separates from the day-0 close fill. The signal does not decay within three sessions. |

## ② MANAGEMENT — "when do I get out?" ← where the edge is

| File | The question | Verdict |
|---|---|---|
| `exit_mechanism_study.py` | The original grid: replay stored daily marks under alternative exit rules, real rows only. | **SHIPPED** the production debit profile — pt 0.90 / sl 0.75 / tef 0.75, no trail (Attempt 10). |
| `combined_exit_study.py` | Same grid, bigger tuning set (real + proxy-priced rows pooled). | **RETIRED 2026-08-14** — inputs are gitignored scratch, deleted and unrecoverable. Verdict (already recorded): PROD confirmed best *global* config — but exits are regime-conditional, which motivated the switch studies below. |
| `underlying_exit_study.py` | Credit spreads: stop on the **underlying** breaching a level instead of on the mark? | **RETIRED 2026-08-14** — inputs are gitignored scratch, deleted and unrecoverable. Verdict (already recorded): ❌ nothing shipped (Attempt 9). |
| `exit_switch_mech_study.py` | Per-regime exit switch keyed on the mechanical regime — stable where the model-keyed version failed LOO? | **BEAR_HE cell SHIPPED** (trail 0.50 / trigger 0.50). L-VOL and RANGE/BULL cells stay gated. |
| `exit_switch_structure_study.py` | Q1: does a bear_put-keyed trail pass the same ship gate? Q2: is BEAR_HE secretly just a *composition proxy* for that structure effect? | Guards the shipped rule against the trap that killed `oi_confirm_pct`. |
| `bear_giveback.py` | 82% of bear rows go green then give it back. Can a peak-triggered breakeven stop capture it, and does the underlying path explain it? | `be_after` grid does **NOT** ship beyond what's already live; the give-back pattern is in the **underlying**, not the mark. |
| `next_day_move.py` | Move the give-back question to day 0 (knowable at the close): cut positions the stock didn't confirm? | ARM C doesn't clear the confound → **no rule**. Sensitivity is structural. |
| `volume_signal.py` | Share volume — the one column on disk no study had read. Does unusual-O/S (flow contracts / share volume) condition exits, or anything? | **NULL** — no R separation on non-bear debit, and the one frozen exit variant is negative out-of-fold (LOO share 1%). Column closed; no version bump. Bear's monotone os_ratio read is a post-hoc carry-forward only. |
| `exit_from_text.py` | Do the model's own stated invalidation level (E1, underlying-close stop), trigger condition (E2, entry filter — a selection effect) and emitted horizon (E3, time exit) beat the shipped mechanical exits? | First run 2026-09-02 (era v4 PRIMARY): **no CANDIDATE** — `tally: {'UNDERPOWERED': 276, 'NOT A CRITERION (pooled)': 9, 'NULL': 19, 'CONTRARY': 5}`. The five CONTRARY cells are E1 on `bull_call_spread`/`LVOL` where the level is not a strike: the text stop cuts the engine's winners (`DeltaR -0.045 ... CI95 [-0.083, -0.008]`, every criterion true toward the negative sign). E3 fails its survival control. v3 SECONDARY: three `bear_put_spread` E1 CANDIDATEs at 1–2% buffer (dR +0.085, CI [+0.044,+0.126]) — a re-read item once 2026 dates reach v4, never a ship from a secondary era. |
| `staged_exit.py` | Evaluate ONCE at a fixed session X on P&L vs the ORIGINAL entry — exit, tighten the stop, or arm a trail — where the reactive drawdown-from-peak rules of Attempts 1/2/10 failed. | First run 2026-08-19 (era v3): **NULL** — 60/96 cells UNDERPOWERED, all 36 powered cells fail the CI outright; continuation shares 49–79% show time-staging bought no immunity from the reactive mechanism. The Attempt-1/2/10 null extends to scheduled switches. |

## ③ STRUCTURE — "am I expressing the signal in the wrong wrapper?"

| File | The question | Verdict |
|---|---|---|
| `bear_rewrap.py` | A bear *spread* sells the lower put — so it gives away the vol expansion that makes a bear position pay. Drop the short leg? | Wrapper is worth **+0.085** and it **does not hold in 2026**. Nothing ships; re-runnable as dates land. |
| `vol_sleeve.py` | Synthesize straddle / strangle / calendar on the dates the engine already signalled. Is there a vol sleeve? | **CLOSED** — the straddle clears its gate then dies out of sample, and it *doubles* existing exposure (wrong-signed correlation). Only the **calendar** survives. |
| `calendar_hedge.py` | Re-derive that one survivor under a pre-registered pick rule and a strict fill rule. | Gates all pass (R4 reproduces exactly), but H2 is **underpowered at n=6**. Blocked on new dates, not refuted. |
| `financed_spread.py` | Does wrapping a book debit vertical in a financing credit — an opposite-delta credit spread, a naked short leg, or a same-direction credit vertical — improve outcomes without re-wrapping the same exposure? | Two runs 2026-08-19 (era v3). Same-expiry shapes: all seven cells **NULL**, naked short significantly harmful, every shape re-wraps the sleeve. Post-scrape **F4-d20 hold is the one CANDIDATE** (ΔR +0.176, CI excl. zero, all seven criteria incl. E3 −0.134 — the only diversifying cell); the operator's close-at-50%/$100 management NULLs the same rows, and d10 far-OTM re-wraps. NOT a ship — queued for independent-window confirmation. |

## ④ DEPLOYMENT — "can I actually run this?"

| File | The question | Verdict |
|---|---|---|
| `bear_deploy.py` | Bear selection is unfixable — but is bear worth holding as a **hedge**? Four estimands: D1 joint selection×exit, D2 hedge contribution, D3 sizing, D4 conditional pick. | **D2 MET** (bear pays on the deployed book's worst dates, corr −0.13). **D4 ADOPTED** (pick bear by \|delta\| *descending*). D1/D3 not met. Bear = a hedge, not a selection. |
| `account_sim.py` | The ladder assumes infinite capital. Does a real **$25,000** account — paying for positions, holding reserve, respecting a delta cap — still produce a book? | Caps survive; the **window** doesn't. **Delta-notional binds, not cash.** Feasibility only, nothing ships. |
| `selection_order.py` | `account_sim`'s *rejected* picks outperformed its taken ones. Does a different **blind entry-side order** of the same candidate set spend the scarce delta budget better — or was that read an artifact? | **UNDERPOWERED** at G0. Each re-ordering changes only 7–14% of the deployed book, so the best-powered arm reaches 11 affected dates vs a floor of **25** declared before the count was knowable. Census only — nothing confirmed, nothing refuted, no O4 band drawn. |
| `hedge_timing.py` | The bear hedge sleeve is deployed on discretionary triggers — chop, a SPY gap-up, a 4–5-day SPY down-run. Does any of them, made mechanical, pick a day the hedge beats the **same day's** ladder-eligible long? | **NOT YET RUN** — registered 2026-08-28, committed before the first run on purpose. One verdict is already fixed by the registration rather than by a number: the operator's own 4–5-day streak rule is **UNDERPOWERED** in advance (such a run occurs on ~11 of the era's ~457 trading days; this book samples **2**), and no direction is ever quoted from n=2. Nothing ships under any outcome. |
| `hedge_exposure.py` | When the open book is **concentrated** in one correlated cluster, does a long put on that cluster's proxy cut the book's **mark-to-market** drawdown, versus carrying the same concentrated book unhedged? | **UNDERPOWERED (the mechanism question) + MEASUREMENT-ONLY (ARM M).** Two words over two different objects; the registration defines both and orders neither, so both are emitted. The **ERRATUM 1** population deadlock was **ratified by the operator on 2026-08-31** (consolidated into [`pre-registrations/f4_deployment/hedge_exposure.md`](pre-registrations/f4_deployment/hedge_exposure.md) §Population and basis): the population is the literal `load_book(include_bs=False)` call, because a `strike_expiry_tweak` row is a **real** Barchart price for a nearby strike and an operator who does not follow a proposed leg exactly is modelled better by a book that admits the substitution. `real` is kept as a **reported stratum**, never a co-primary. On the ratified population `powered POOLED cells 0   POOLED cell words: UNDERPOWERED 9` in every stratum — `VERDICT — the mechanism question, over the hedge cells: UNDERPOWERED`, and **no direction is quoted from any cell**. ARM M is not power-gated and is the sharper result: `ARM M curve gap: maxDD $-9,332   ulcer +1.96 pts   TUW +3.1 pts   (differ materially: YES)` — `the close-bucketed curve UNDERSTATES this book's max drawdown by 40.2%.`, hence `VERDICT — ARM M, the measurement, which is not power-gated: MEASUREMENT-ONLY`. **Nothing ships.** UNDERPOWERED leaves the queued max-drawdown question **open**, it does not close it. `bear_deploy` D3, `calendar_hedge` H3 and `hedge_timing` H4 all **stand** — but they were read on the close-bucketed curve, which understates this book's drawdown by 40%, now a known limitation of theirs. **ERRATUM 2** stands: ARM P is **inert as registered** and has not been redefined, so the binding prose rule is unreachable; ARM RF prints as **UNREGISTERED — ADDED AFTER COMMIT** and no clause reads it. Read with the ratification's own limitation: the registration's **plan-time observations** (exposure table, concentration quantiles, 504-session universe) describe the `real` stratum and are **not** disclosures about the ratified book — the figures that describe it are the ones the run itself prints. |
| `hedge_concentration.py` | On the **admitted** book — the positions `account_sim` actually takes under the operator's top-3-per-day rule and exposure caps — does a session's cluster **concentration predict** the book's subsequent mark-to-market drawdown, and only then does a proxy put on that cluster cut it? | **PRECONDITION-NULL — a POWERED null**, which is the whole point of the two-stage design: `hedge_exposure` could not power one hedge cell, and Stage 1 does not depend on triggers at all. `usable sessions per concentration tercile   [162, 166, 152]   floor 60 EACH   PASS` / `dense episodes of admitted signal dates     3   floor 3   PASS` / `G-POWER-K: PASS`, then `CONTRAST (high - low)   $-691.92   CI95 [$-2,000.07, $419.99]   includes 0` and `SPEARMAN rho            -0.1487   CI95 [-0.3829, +0.0978]   includes 0`, with the contrast inside the circular-shift null (`null p05 -818.0281 ... beats p05 (more negative): no`). Clauses 1, 2, 3 and 5 fail; the two that PASS are the **controls** (ARM KG keeps the sign in 2 of 3 gross terciles, both ex-window cuts retain it), so it is not a gross-exposure effect in disguise either — it is no effect. `VERDICT — Stage 1 (ARM K, the precondition): PRECONDITION-NULL`, so `VERDICT — Stage 2 (ARM C, the mechanism): NOT RUN (Stage 1 PRECONDITION-NULL)` and **no cell was evaluated** (its census is on the record: episodes peak at 18 against a floor of 25, as the registration predicted). Book: 996 ratified rows → 458 ladder-eligible → `ADMITTED (taken + taken_downsized)  221 / 110 dates`, skipped per_pos_delta 92 · net_delta 81 · day3_cap 64. G-ADMIT, G-MTM (on `TARGET_POSITION`; the stored-target check mismatches 136 **because** the sim re-sized 101 and re-exited 35) and G-BLIND all pass. ARM M is a measurement and never a verdict here: `THE GAP … maxDD $-2,428 (27.2% of the realized-on-close drawdown)   ulcer +2.49 pts   TUW +15.2 pts`. **Nothing ships.** `SHIP-CRITERIA BRANCH: record in research/deployment-evidence.md as closing the queued max-drawdown question for concentration-gated hedging; next-steps.md §2.1 closed` — the operator's to write, not this study's. Says nothing about hedging in general and does not touch the §4 sleeve. |
| `portfolio_delta.py` | Is the book's net delta LEVEL a lever? Dose-response by exposure band, a ceiling-band admission, and a delta-TARGETED hedge sleeve, all against a seeded random-admission null band. | First run 2026-08-19 (era v3): **NOISE**, and long-only-by-construction confirmed (219/220 positive delta, 0 net-short sessions); every delta-target hedge arm UNDERPOWERED on the primary population (on the secondary — which carries nothing alone — H* 1.50 is the one arm anywhere whose CI excludes zero, and it fails the year-sign and null-band criteria). Net delta is not a free lever of this book. |

---

## Infrastructure (not studies — `run.py` lists these in `INFRA`)

| File | Role |
|---|---|
| `run.py` | The runner. Writes `backtests/study_output/<name>-latest.txt` with a provenance header (git sha, dirty flag, exact argv, input row counts + mtimes) so no write-up can attribute numbers to the wrong export. |
| `harness.py` | **FROZEN** `Trade`/`replay`. Prices nothing — it replays a stored mark series. Every recorded conclusion depends on its exact clamps and rounding. Changing the exit mechanism means *copying* this file, never editing it. |
| `book.py` | Pooled real + proxy loader. `bs_options_hist` rows are excluded by default — they're priced *from* the model that scores them. |
| `protocol.py` | The four things every conclusion rests on: date clustering, purging + embargo, same-dates comparison, window dominance re-cuts. Plus the profit-factor helpers (`pf`, `pf_ci_by_date`, `pf_paired_by_date`) — never printed without mean R beside them. |
| `text_corpus.py` | The model's own prose (thesis, Alt, signal items, trigger, invalidation) joined to every priced row through `book.py`'s join, parsed back into the writer's fields, and reduced to the regex features with no numeric twin already tested null. Also returns the *unpriced* analysis rows by reason and a citation check against the raw flow feed. Built for `text_features`, `exit_from_text`, `prompt_eval`. |
| `underlying.py` | Daily stock bars — real OHLC, falling back to close-only `Price~`. The widening `harness.py` is frozen out of. |
| `underlying_features.py` | As-of-entry price-*state* columns (rv20, Parkinson, semivar, ATR%, efficiency ratio, VRP, beta). This family is the ML re-open — none of it existed when B1 searched 496 subsets. |
| `volume_features.py` | As-of-entry *volume* columns (unusual-O/S, relative-volume z, Amihud), split-guarded, rescaled tickers withheld from the window features. Built for `volume_signal` (NULL), kept for future pre-registered use. |
| `macro_calendar.py` | Scheduled macro events (FOMC, minutes, CPI, NFP, PCE) as as-of features, read from the hand-authored `config/macro-events.yml`. `next_event` is strictly-after and refuses past each type's `verified_through`; unscheduled events excluded from forward reads only. Built for `macro_event_study`. |
| `greeks.py` | Per-leg greeks from the option-history cache at a given day, signed and qty-scaled; net sums are all-or-nothing per greek (a missing leg makes the greek `None`, never 0). Built for `financed_spread`'s exposure reads and `portfolio_delta`'s G-DELTA cross-check. |

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
