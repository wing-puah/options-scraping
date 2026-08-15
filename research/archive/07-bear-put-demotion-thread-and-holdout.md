# Archive 07 — bear_put demotion thread (addenda 11–14) and the Feb–Apr 2026 holdout

Covers 2026-07-22: addenda 11–14 (bear_put cancellation read, the
structure-keyed trail, the demotion pre-registration and its DEMOTE
verdict criteria) and the Feb–Apr 2026 bear-holdout coverage/backfill
status that the 2026-08-11 completed-book analysis later closed.
See [../README.md](../README.md) for the full section index.

---

## 2026-07-22 — bear_put demotion: the open thread

### 2026-07-22 addendum 11 — bear_put demotion CANCELLED: it is an exit-shape problem, not a selection problem (user challenge, correct)

**User challenge:** "we changed our exit and bear_put becomes profitable, why do
we demote it?" Prompted a structure × (MFE, MAE, realized) re-read of the 913-row
pooled export. The challenge was right and queue #4 is withdrawn.

**My error, retracted.** I argued bear_put had shallow upside and that "an exit
rule can only harvest MFE that already exists." The premise was false. The
asymmetry reads that seeded the demotion (bear_put × iv_spread MAE −0.197,
score_dealer MAE −0.320) are *correlations with* MFE/MAE, and I read them as
statements about bear_put's MFE *level*. They are not. Level, pooled: mean MFE
+0.713 (real-priced +0.788), median +0.398; 58% of rows reach +0.30, 29% reach
the +0.90 PT.

**Path shape is the finding** (real-priced):

| structure | MFE-first | mfe_day | mae_day | PT exit | stop exit |
|---|---|---|---|---|---|
| bear_put  | **77.3%** | 17.0 | 41.0 | 23.9% | **29.3%** |
| bull_call | 38.2%     | 37.9 | 25.1 | 42.0% | 13.5%     |

bear_put runs early then bleeds; bull_call dips then runs. Opposite exit
treatment. **Attempt 10 removed the debit trailing stop POOLED**, and the debit
pool is dominated by bull_call (n=312, the dollar weight) — the "21 trail exits
sold continuations" evidence is bull_call's signature. bear_put was never tested
on its own path shape.

**Give-back (conditions on MFE ≥ X — LOOKAHEAD, motivating only, does NOT price
the rule):** of 206 bear_puts reaching +0.30, 43.2% finished red; at +0.50,
32.5% of 157. bull_call at the same cuts: 23.2% / 16.9%.

**Ceiling test — settles the dead-money claim:**

```
bear_put   realized  −$38.6k   perfect-foresight exit +$296.9k   headroom $335.5k
bull_call  realized +$133.6k   perfect-foresight exit +$467.5k   headroom $333.9k
```

Same extractable headroom as the engine structure. "Half the debit book earning
nothing" (§addendum, line ~104) is wrong as a *selection* verdict — the emissions
are fine, the exit is mismatched.

**Queue change:** #4 bear_put emission demotion → **CANCELLED**. Replaced by
**structure-conditional trailing stop for bear_put**, to run through the existing
replay harness (`scripts/backtest_study/exit_mechanism_study.py`, `combined_exit_study.py`)
under the addendum-4 corrected LOO gate. Not run yet.

**New concern to test in the same pass — possible composition proxy.** The
SHIPPED BEAR+H/E trail .50/.50 (addendum 7, +$4.4k per-cell) may be this same
effect found through the wrong key: if BEAR+H/E dates emit disproportionately
more bear_puts, a regime-keyed override is a composition proxy for a
structure-keyed one — the trap that killed `oi_confirm` and `iv_pct` (rule 7).
Test structure-keying and regime-keying head to head, and check the bear_put
share of BEAR+H/E rows. If structure-keying dominates it is both simpler and
drops the runtime dependency on the SPY/VIX table (addenda 9/10).

No code changed. No re-run performed.

### 2026-07-22 addendum 12 — structure-keyed bear_put trail RUN: does NOT ship, and it exposes the shipped BEAR_HE clause as a bear_put proxy that is NEGATIVE outside one window

Ran the addendum-11 follow-up: `scripts/backtest_study/exit_switch_structure_study.py`
(output `backtests/exit_switch_structure_study_output.txt`). Data, calibration,
dedup, post-13c join and gate thresholds are IMPORTED from
`exit_switch_mech_study.py` — same 663-row pooled debit book (real 250 / tweak
247 / bs 166), same harness validation (250/250 real debit rows reproduce
DEBIT_PROD, replay total $27,648.70 = stored to the cent). Only the KEY differs,
so a difference in answer cannot come from a difference in setup. Treatment is
the SAME frozen variant the mech switch uses for BEAR_HE (trail .50 / trig .50).

**Q1 — structure-keyed bear_put trail: right-signed, but it is ONE WINDOW.**

    bear_put (n=343)  PROD mean −0.1242, win 35.6%
    + V_TRAIL         mean −0.0925, win 38.8%   Δ +10.87 pnl_pct / +$11,781

Concentration check (the Attempt-13 July-2024 discipline):

    ALL                n=343   Δ +10.866   +$11,781   win 35.6%→38.8%
    Mar+Apr 2025       n=102   Δ +10.183   +$11,037   win 40.2%→48.0%
    EX Mar+Apr 2025    n=241   Δ  +0.683      +$744   win 33.6%→34.9%

**94% of the gain is Mar–Apr 2025** (the tariff drawdown — precisely the regime
where a bear_put runs then bleeds). Dates are diffuse (top-5 dates = 11.7% of
total, 10/17 months positive), so this is not a single-trade artefact; it is a
single *market window*, which is worse for a rule meant to generalise. Ex-window
the effect is +$744 over 241 rows ≈ nothing. **Structure-keyed trail: NO SHIP.**

Gate for the record: 5/6 PASS, failing only "LOO median > 0" — which fails **by
construction** for every sparse-cell switch (most dates have no rows in the cell,
so the fold gain is exactly 0 and the median is 0). The mech switch failed the
identical criterion in addendum 4. The criterion is uninformative here and should
be replaced by "median over AFFECTED dates" in any future exit-switch gate.

**Q2 — the shipped BEAR_HE clause is a composition proxy, and a lossy one.**

Composition: bear_put is 51.7% of the debit book but **63.9% of BEAR_HE rows**
(+12.1pp lift); 53% of all bear_puts sit inside BEAR_HE. Decomposition, each key
run on the other's complement (pooled; BEAR_HE clause alone, LVOL/RB_EVOL
excluded so this matches what is actually in `config/backtest.yml`):

    slice                              n_changed    Δpnl_pct        Δ$
    BEAR_HE clause, all rows                 285      +3.657     +4,416
    BEAR_HE clause, NON-bear_put only        103      −4.676     −4,929
    bear_put trail, all rows                 343     +10.866    +11,781
    bear_put trail, OUTSIDE BEAR_HE          161      +2.534     +2,436
    overlap only (bear_put AND BEAR_HE)      182      +8.333     +9,345

The shipped clause retains **−128%** of its gain on its own complement; the
structure key retains +23% of its. The overlap alone (+$9,345) is larger than the
whole BEAR_HE cell (+$4,416) — the non-bear_put two-fifths of the cell actively
**lose** $4,929. So BEAR_HE is not merely a proxy for bear_put: it is bear_put
plus a money-losing tail the regime key drags in.

**And the shipped clause has the same window dependence:**

    BEAR_HE clause  ALL           n=285   Δ +3.657   +$4,416
                    Mar+Apr 2025  n=121   Δ +5.624   +$6,426
                    EX Mar+Apr    n=164   Δ −1.967   −$2,010

**The one rule currently in production off this line of work is negative outside
Mar–Apr 2025.** That is not the pre-registered rollback trigger (which asks for
≥25 affected BEAR+H/E dates of NEW data and is untouched by a re-cut of old
rows), so this is NOT an automatic revert — but it is a live warning, and it is
the same window that carries the structure result, so the two findings are one
finding: **trail .50/.50 helps debit trades during a sustained bear drawdown, and
the key — regime or structure — is mostly picking out how much of that window a
slice contains.**

**Decisions.**
1. Structure-keyed bear_put trail: **NOT SHIPPED.** Stays a candidate.
2. BEAR_HE clause: **left in production, rollback trigger UNCHANGED** — the
   trigger is pre-registered on new data and re-cutting old rows must not be
   allowed to relitigate it (that is exactly the discipline addendum 7 bought).
   But its evidence is now known to be window-bound; **if the trigger evaluation
   is ambiguous, revert** rather than extend.
3. Exit-gate criterion "LOO median > 0" is retired for sparse-cell switches —
   replace with median over affected dates when this is next run.
4. The exploratory grid says trail **.25/.50** dominates .50/.50 on bear_put
   (+13.50 / +$16,196 vs +10.87 / +$11,781) and BE@.50 is close (+12.05 /
   +$13,438). NOT ship-eligible off this run (chosen post-hoc from the grid, and
   subject to the same Mar–Apr concentration). Recorded so the next credit- or
   bear-heavy window tests the right knob first.

**What would settle it:** a second sustained bear drawdown in the book. Until
then, both the shipped clause and the structure candidate rest on one window.

No production config changed. New file: `scripts/backtest_study/exit_switch_structure_study.py`
(read-only study, imports the mech harness).

### 2026-07-22 addendum 13 — PRE-REGISTRATION: bear-position study (written BEFORE the run)

Reason this is pre-registered rather than another cut: addenda 11–12 produced
three different verdicts on bear_put in one session (demote → don't demote →
maybe demote) because each was a post-hoc slice of the SAME 663-row book,
reported as a verdict. On a book this dominated by one window, post-hoc slicing
will keep generating verdicts. Everything below is fixed before running.

**Population.** All bear-direction plays in the pooled priced debit book
(real + proxy tweak + proxy bs, same loader/calibration as addenda 4/12).
Primary: `bear_put_spread`. Comparator: `bull_call_spread`. Any
`bear_call_spread`/`long_put` rows counted and reported, not analysed.

**Two outcome measures, both reported on every cut.**
- **E = `pnl_at_cap_pct`** — P&L at the last priced path day, computed
  independently of any exit rule (`simulate.py:267`). This is the SELECTION
  measure: no exit rule can rescue a structure whose E is negative.
- **R = `realized_pnl_pct`** under PROD — SELECTION + EXIT.
Discriminator: E<0 ⇒ selection problem. E>0 with R<0 ⇒ exit problem. This
replaces MFE, which addendum 11 leaned on and which only bounds the upside a
perfect exit could have reached.

**Window control.** W = Mar+Apr 2025 (declared now, from addendum 12: it
carries 94% of the structure-trail gain and flips the shipped BEAR_HE clause).
Every headline is reported ALL / IN-W / EX-W. Pricing tier (real / tweak /
bs-model) reported alongside per the standing split rule.

**Cuts — fixed, complete, no additions after the run.**
- C1 levels by structure × window, on E and R
- C2 date-clustered bootstrap (10k, cluster = signal_date) 95% CI on mean E and
  mean R for ex-window bear_put
- C3 time halves + per-month sign count, on E
- C4 mech cell × structure, on E
- C5 entry geometry — |delta| bands, DTE bands, `iv_entry_pct`, `iv_spread`
  sign — on E, ex-window decision-eligible, in-window reported only
- C6 deployment ladder (docs/deployment-rules.md): do the existing vetoes /
  tiers already screen the bear_put losers?
- C7 path shape: mfe_day vs mae_day, and the MFE→E give-back

**Decision rule — fixed now.**
- **DEMOTE to veto** iff ex-window mean E < 0 AND the C2 bootstrap 95% CI upper
  bound < 0 AND both C3 halves negative.
- **CONSTRAIN** (Tier-C→B style entry-geometry rule) iff some C5 cut is positive
  ex-window in BOTH halves with n ≥ 30.
- **NO ACTION** otherwise. Explicitly: no decision may rest on in-window
  numbers, and no cut invented after seeing the output is decision-eligible.

**This is the last cut of this book on the bear_put question.** Any further
change to bear_put's treatment requires new data, not a new slice.

### 2026-07-22 addendum 14 — bear-position study RUN: DEMOTE fires on all three pre-registered criteria; bear_put is a SELECTION problem, not an exit problem

`scripts/backtest_study/bear_position_study.py` → `backtests/bear_position_study_output.txt`.
Cuts, window control and decision rule were fixed in addendum 13 before the run;
nothing was added after seeing output. Same 663-row pooled debit book, same
harness validation (250/250 real rows reproduce DEBIT_PROD to the cent).

**The number that settles it — E, hold-to-cap, EXIT-FREE (`pnl_at_cap_pct`):**

    bear_put   ALL   n=343  mean −0.414  median −0.928  win 27.7%   −$160,256
               IN-W  n=102  mean −0.674  median −0.988  win 15.7%    −$76,329
               EX-W  n=241  mean −0.304  median −0.670  win 32.8%    −$83,927
    bull_call  EX-W  n=228  mean +0.423  median +0.265  win 57.0%   +$101,380

With no exit rule at all, the median bear_put is a −93% loss. R (realized under
PROD) is −0.124 — i.e. **the current exit rule is already rescuing ~0.29 of
mean P&L**, and the thing underneath it is far worse than realized P&L showed.
That is the reverse of addendum 11's conclusion and it is the direct test
addendum 11 lacked: MFE bounds what a perfect exit *could* reach; E measures
what the position is worth without one.

**Decision-rule evaluation (pre-registered):**

    [PASS]  ex-window mean E < 0                  (−0.304)
    [PASS]  date-clustered bootstrap 95% CI < 0   ([−0.433, −0.175], 10k, cluster=date)
    [PASS]  both time halves negative             (early −0.289, late −0.322)
    VERDICT: DEMOTE TO VETO

**It is not the window, and not the pricing tier.** Negative in 14/17 months;
negative in every mech cell (BEAR_HE −0.281, LVOL −0.301, RB_EVOL −0.497,
PROD −0.254 — all EX-W); negative in every pricing tier (real −0.431, tweak
−0.383, bs −0.045). Every prior explanation I offered for bear_put — exit shape,
regime key, Mar–Apr window — was a local slice of a structure that loses
everywhere on this book.

**Path shape, reinterpreted.** bear_put MFE +0.691 with give-back to E of
**1.105** and MFE-first 72.0%; bull_call MFE +1.281, give-back 0.566, MFE-first
40.2%. bear_put reliably runs and then round-trips *past zero*. Addendum 11 read
the excursion as harvestable edge; with E on the table it reads as volatility,
not direction. A trailing stop harvests some of it (addendum 12: +$11.8k, 94%
in-window) but cannot make a −0.414 expectancy positive.

**Ladder interaction (C6): the operational change is smaller than it sounds.**
Every bear_put already lands in VETO (n=36, mean E −0.894) or Tier C (n=307,
mean E −0.358); none ever reach Tier A or B. Under the shipped top-3/day
ladder, bear_puts are already largely not deployed. Whole-book tier means on E
stay monotone (A +0.907, B +0.482, C −0.355, VETO −0.510), and hold EX-W
(A +0.414, B +0.445, C −0.285, VETO −0.785) — A/B invert slightly EX-W, worth
noting but not a ladder failure.

**CONSTRAIN candidate, reported and NOT taken.** `|delta| 0.30–0.45` was the one
cut passing the pre-registered n≥30 / both-halves-positive filter (n=36 EX-W,
mean +0.097, halves +0.065 / +0.129). Its median is **−0.767** and its total is
+$2,465 — a mean carried by a couple of tails on 36 rows. The pre-registered
rule puts DEMOTE first and it fired; recording the cut so it is not re-discovered
as a novelty later.

**The honest caveat, which is a portfolio question and not a statistical one.**
The book spans 2024-06 → 2026-03, a period with exactly one sustained drawdown.
bull_call beat bear_put even *inside* mechanical BEAR cells (EX-W +0.326 vs
−0.281). So this may be measuring "the sample was a bull market" as much as
"the model is bad at bearish calls" — the two are not separable on this data.
A structure veto on bear_put removes essentially all downside exposure from the
system. That is a deliberate choice to make, not a mechanical consequence of a
p-value.

**Status: verdict reached, NOT yet implemented.** Implementation options (intake
structure_veto like bear_call vs ladder VETO tier vs leave at Tier C and simply
never deploy) are a user decision. Per addendum 13 this is the last cut of this
book on the bear_put question — any revision needs new data.

---

## 2026-07-22 — Feb–Apr 2026 bear holdout: coverage + backfill status

The addendum-13 pre-registration ends "this is the last cut of this book" —
so the DEMOTE verdict needs **new** data, not another slice. The only genuine
holdout available is the second sustained drawdown: **2026-02-05 → 2026-04-07**,
32 trading days, all of them mechanical `BEAR_HE` (BEAR + H/E-VOL), VIX peak
31.0, SPY −7.9%. The current book samples it with **6 dates**.

Why not the Iran window instead: checked against the frozen `lib/mech_regime.py`
labels, 2025-06-02 → 2025-07-15 is **BULL on every single day** (26 L-VOL /
3 H-VOL / 1 E-VOL), SPY 592.71 → 622.14, VIX peak 21.6. A vol blip inside an
uptrend — it would add the cell the book already has most of, not a bear cell.

### Status table

Drive coverage + enrichment fill read 07-22. "Analyzed" = has rows in the
AnalysisClaude tab (the only source of truth for analysis state — see the
queue-file drift note in archive/05). Enrichment columns are the **fill rate of
each collector's marker column** on `stocks-flow-*-compiled.csv`
(`oi_enriched_on`, `iv_pct_enriched_on`, `price_catalyst_enriched_on`) and the
row count of the `counterpart-iv-*.csv` sidecar — measured, not inferred from
the `.done` queue files. Every date is either 0% or 100%: enrichment is
all-or-nothing per date, so there is no partial-fill case to handle.

Row counts are 498–501 on all 26 compiled stocks files; etfs compiled is
present everywhere except 2026-03-18. Nothing here is a dropped stage — the
lean-enrichment profile was SHELVED on 2026-07-21 (archive/05, "NO scraper is
droppable"), so these are gaps to fill, not decisions to honour.

| # | Date | In Drive | Analyzed | oi/eod_iv | iv_pct | p/cat | cpart | Next step |
|---|------|----------|----------|-----------|--------|-------|-------|-----------|
| 1  | 2026-02-05 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ iv-pct + ✅ p/cat + ✅ counterpart → ✅ analyze |
| 2  | 2026-02-12 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 3  | 2026-02-13 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 4  | 2026-02-17 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 5  | 2026-02-19 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 6  | 2026-02-23 | yes | ✅ | **0%** | 100% | 100% | 260 | ⚠ in book WITHOUT eod_iv — see flaw note |
| 7  | 2026-03-02 | yes | ✅ | **0%** | **0%** | **0%** | **0** | ⚠ in book with NO enrichment at all |
| 8  | 2026-03-03 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 9  | 2026-03-04 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 10 | 2026-03-05 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 11 | 2026-03-06 | yes | ✅ | 100% | 100% | 100% | 278 | in book, complete |
| 12 | 2026-03-09 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 13 | 2026-03-10 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 14 | 2026-03-11 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 15 | 2026-03-12 | yes | ✅ | 100% | 100% | 100% | 84 | in book, complete |
| 16 | 2026-03-13 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 17 | 2026-03-16 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 18 | 2026-03-17 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 19 | 2026-03-18 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze (etfs compiled absent) |
| 20 | 2026-03-19 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 21 | 2026-03-20 | yes | ✅ | 100% | 100% | 100% | **0** | ⚠ in book with BLANK iv_spread |
| 22 | 2026-03-23 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 23 | 2026-03-24 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 24 | 2026-03-25 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 25 | 2026-03-26 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 26 | 2026-03-27 | yes | ✅ | 100% | 100% | 100% | 253 | in book, complete |
| 27 | 2026-03-30 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 28 | 2026-03-31 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 29 | 2026-04-01 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 30 | 2026-04-02 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 31 | 2026-04-06 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 32 | 2026-04-07 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |

**26/32 in Drive · 6/32 analyzed · 3 of those 6 input-incomplete · 6 need
scraping.** (2026-04-03 is Good Friday, so 03-30 → 04-07 is 6 trading days.)
Wider Drive audit: 26 weekdays are missing in 2026-02-01 → 2026-07-22, and
**all 22 weekdays of 2026-04 are absent** — the 6 above are the subset inside
the bear episode; the rest of April is a separate gap.

Stage totals to fill across the 26 in-Drive dates: `enrich_oi` 21 ·
`fetch_iv_percentile` 21 · `fetch_price_catalyst` 21 · `fetch_counterpart_iv` 22.

**Scrape 2026-04-08 as well.** `enrich_oi` reads D+1 open interest, so the last
episode date (04-07) cannot be enriched without it, and 04-08 is inside the
missing-April block. It is not itself a holdout date — it is an input.

### The three flawed in-book dates (decision needed)

The existing 6-date sample of this episode is **not** input-consistent, and the
inconsistency lands on `iv_spread` — the bear_put Tier-C column, i.e. the exact
variable the holdout is meant to test:

- **2026-03-02** — analyzed with zero enrichment. No `oi_confirm_pct`, no
  `iv_pct`, no `iv_spread`.
- **2026-02-23** — counterpart sidecar present (260 legs) but traded-leg
  `eod_iv` absent. This is the failure mode the shelving note names: counterpart
  legs are *always* EOD, so without `eod_iv` the matched pair compares intraday
  against EOD IV. `iv_spread` here is **silently wrong**, not missing — worse
  than a blank, because nothing downstream flags it.
- **2026-03-20** — traded-leg enrichment complete but no counterpart sidecar, so
  `iv_spread` is blank. Honest gap, at least.

Re-running `analysis_pipeline` on these **appends** rows rather than replacing
them, so fixing them is a duplicate-row decision, not just a re-run. Open
options: (a) leave them and note the holdout's 6 pre-existing dates are mixed
quality; (b) enrich, re-analyze, and delete the original rows. Unresolved —
does not block enriching the other 20.

### Sequence

1. **Scrape the 6 + 04-08** (user is running this):
   `python3 scripts/collector/scrape_flow.py --start 2026-03-30 --end 2026-04-08 --skip-existing`
2. `compile_flow.py` on the newly scraped dates.
3. Enrichment chain, batched by stage over the gap lists above —
   `enrich_oi`, `fetch_iv_percentile`, `fetch_counterpart_iv`,
   `fetch_price_catalyst`. All four stay in (archive/05); none is optional.
4. `python3 -m scripts.analysis_pipeline --date <D>` for the 26 unanalyzed
   dates — **config unchanged**, or the holdout stops being a holdout.
5. `python3 -m scripts.backtest` + `python3 -m scripts.backtest.proxy`.
6. Re-run `scripts/backtest_study/bear_position_study.py` **unmodified** against the
   Feb–Apr 2026 rows only. The pre-registered decision rule from addendum 13
   applies as written: DEMOTE iff mean E < 0 AND bootstrap CI upper < 0 AND
   both halves negative.

If the holdout agrees, the demotion ships and the "sample was a bull market"
caveat in addendum 14 is answered by a second independent drawdown. If it
disagrees, bear_put stays at Tier C and the 2024-06 → 2026-03 result is
recorded as window-bound. Either way the decision is made once, on the
holdout, and not by re-cutting the 663-row book again.

### 2026-07-29 — PRELIMINARY holdout read (backfill incomplete — NOT the decision run)

Backfill in progress; read taken from the Sheets tab exports
(`backtests/analysis - BacktestResults.csv` / `- BacktestProxy.csv`, pulled
07-29), holdout window rows only. Coverage: **12 dates priced** (02-05 → 03-27;
02-24/02-25 now analyzed beyond the status table above), 115 priced rows, 5
unpriced (3 no_history / 2 unsupported). Scratch script only — the decision run
stays `bear_position_study.py` unmodified once the window is fully backfilled.

**bear_put_spread, n=67 priced — all three pre-registered criteria fire on the
partial sample:**

    mean E −0.242   date-clustered bootstrap 95% CI [−0.370, −0.077]  (12 dates)
    halves: early −0.205 (n=28) · late −0.268 (n=39)
    ex-flawed-dates (02-23/03-02/03-20 excluded): mean E −0.214 (n=51), still negative

R (PROD) −0.073 — the exit rule is again rescuing ~0.17 of mean E, same
signature as addendum 14. Path shape repeats too: MFE +0.609 / MAE −0.621,
run-then-round-trip. And this window IS a bear drawdown — the most favourable
conditions bear_put will ever see — so the addendum-14 "maybe the sample was a
bull market" caveat is, preliminarily, not holding up. Comparator bull_call:
mean E +0.150 (n=18, but ex-flawed only n=6 at −0.138 — too thin to read).

**One discordant cut to watch: the pure-real tier is POSITIVE** — real n=16
mean E +0.177 (win 62.5%) vs strike_expiry_tweak n=34 mean −0.471 and bs n=17
mean −0.177. Real+tweak pooled is still −0.26, and tweak rows are real-priced
(only bs is model-priced), but if the final run still shows real-tier-positive /
tweak-tier-negative, the tweak fallback itself (strike/expiry substitution on
bear_puts in a fast tape) needs a look before the verdict is read as clean.

**MFE/MAE cut (standing rule — realized alone is not a read):**

    structure   n   MFE     MAE     |MAE|/MFE  MFE-first  give-back  R-capture
    bear_put    67  +0.609  −0.621    1.02       59.7%      0.851      −0.12
    bull_call   18  +1.108  −0.574    0.52       55.6%      0.958      +0.40
    bull_put    27  +0.559  −1.347    2.41       44.4%      0.738      −0.41

- bear_put's excursions are **perfectly mirrored** (ratio 1.02) — by the
  asymmetry rule that is path-vol, not harvestable edge; 58% of rows reaching
  +0.30 still end E<0 (old book: 43%). bull_call keeps upside asymmetry (0.52)
  *inside the drawdown*, and its exit capture is +0.40 of MFE vs bear_put's
  −0.12 — same discriminator as addendum 14: exit harvesting works on
  bull_call, nothing on bear_put rescues a negative-E selection.
- The addendum-14 bear_put signature (MFE-first 72%, give-back 1.105) lives in
  the **tweak tier** here (70.6% / 1.095, MAE med −0.926); the real tier looks
  different in kind: MFE +0.885 / MAE −0.546 (ratio 0.62), mfe_day 12.4, 44%
  reach the +0.90 PT, E +0.177. Reinforces the real-vs-tweak discordance above —
  on the final run, check whether tweak's strike/expiry substitution is
  manufacturing the round-trip shape before reading the pooled number.
- bull_put side note (thin): ratio 2.41 with 59% reaching +0.30 and only 6% of
  those ending E<0 — deep-MAE-then-recover, the Attempt-13 whipsaw shape; its
  real-tier R (−0.304) undershoots E (+0.009) via dollar_stop exits. Watch, not
  actionable.

Loose ends for the backfill: **2026-02-17 is analyzed but absent from BOTH
backtest tabs** (0 rows in Results and Proxy — backtest apparently never run on
it); late dates are the most negative (03-20 −0.53, 03-27 −0.52), and the
still-missing late-March/April dates sit closest to the episode bottom, so
completing coverage is more likely to strengthen than soften this read.
No config changed. No decision taken — waits on the full window.

### 2026-08-04 — MID-STOP check (backfill still incomplete — NOT the decision run)

Read off the refreshed `backtests/results.csv` (364 rows) + `proxy_results.csv`
(675), window rows only, deduped on date|ticker|play|structure. Scratch script,
read-only, no config changed. Purpose is to catch problems before the decision
run, not to decide.

**Coverage: 16 dates / 137 priced rows** (07-29: 12 / 115). 14 of the status
table's 32 dates, plus 02-24 and 02-25 which are not on it. Still missing 18,
including the whole late-March block (03-11 → 03-26 except 03-20) and all of
03-30 → 04-07 — i.e. everything nearest the episode bottom. 6 unpriced
(5 no_history / 1 unsupported).

**bear_put: DEMOTE fires again, and harder.** n=82 (was 67).

    mean E −0.254   bootstrap 95% CI [−0.392, −0.091]  (16 dates, cluster=date)
    halves: early −0.100 (n=29) · late −0.338 (n=53)
    ex-flawed-dates n=66, mean E −0.235
    R (PROD) −0.040 → exit rule still rescuing ~0.21 of mean E

All three pre-registered criteria pass on the partial sample, second time
running, with the late half more negative than the early — the added dates
moved the read away from zero. Comparator bull_call n=20: E +0.187, R +0.463,
|MAE|/MFE 0.51, R-capture +0.43 vs bear_put's −0.06. Same discriminator as
addendum 14; bear_put excursions still mirrored (0.97).

**Four things to fix before the decision run — all mechanical, none of them
change the verdict, but two would corrupt it:**

1. **`2026-03-06` is duplicated wholesale in BOTH tabs** — in BacktestResults,
   10 plays each appearing twice with identical legs/play/P&L (it is the only
   20-row date in the window; every other is ≤11), and separately in
   BacktestProxy (GLD/MU/USO bull_puts, same doubling). The study loader
   (`exit_switch_mech_study.load_debit_trades`) dedups proxy-against-real via
   `real_keys` but has **no within-real dedup**, so an unmodified re-run
   double-weights that date. My numbers above dedup it; the decision run will
   not unless the loader is patched.
2. **The study scripts read the wrong files.** `AC_PATH`/`BR_PATH`/`BP_PATH`
   point at `backtests/to_evaluate/analysis - *.csv`, exports dated **07-22**
   holding only 8 window dates. `bear_position_study.py` re-run "unmodified"
   would read stale data. Refresh those exports (or repoint the paths) as step 0
   of the decision run.
3. **The real-vs-tweak discordance flagged on 07-29 has grown, not resolved:**
   real n=22 mean E **+0.201** (win 63.6%) · tweak n=39 **−0.514** · bs n=21
   −0.246. Real+tweak pooled −0.256. The whole demotion currently rests on the
   proxy tiers being trustworthy on bear_puts in a fast tape. Caveat in the
   other direction: 6 of those 22 real rows are the duplicated 03-06 IWM/TSLA
   pairs, so the real tier is effectively n=18. This needs settling before the
   verdict is called clean — it is now the largest open risk on the demotion.
4. **02-17 and 02-19 are still absent from both backtest tabs** (07-29 flagged
   02-17 only). The status table marks both analyzed with the full chain. Either
   the backtest was never run on them or the analysis rows are not actually
   there — worth a direct Sheets check, not another export.

**New, unrelated to bear_put: the shipped bull_put band gets its first
out-of-sample look, and it holds.** Pooled window bull_put is bad (n=33,
E −0.450, R −0.451, |MAE|/MFE 2.75, late half −0.733) — but split on the rule
actually in `deployment-rules.md`:

    0.08 ≤ |delta| ≤ 0.20 AND DTE ≤ 59    n= 9   E +0.180   R +0.152
    out of band                           n=24   E −0.686   R −0.677

Out-of-band is DTE-driven, not delta-driven: DTE>59 n=18 E −0.898, |delta|<0.08
n=11 E −0.632, |delta|>0.20 n=2 E −0.048 (rows can fail both legs). 6 of the 9
in-band rows finish positive (median E +1.00); the mean is dragged by one
SMH −2.66. Thin and one-window, so not a promotion — but it is the first
independent window where the constraint separates the book, and it separates it
by 0.87 of mean E. Do NOT read the pooled bull_put number as evidence against
the structure; it is an out-of-band number.

**Lead worth chasing on the long-dated blind spot (2026-07-27 §3).** Five rows
in this window are real-priced at DTE ≥ 180 with `pct_real_days = 1.0` —
TLT 707/689/687 (two bull_call spreads + a long_call) and HYG 197/191. So
Barchart history at 180–700 DTE is not universally absent; it appears to be
ticker-dependent (bond/credit ETFs have it). n=5 does not unblock anything, but
"h≥180 cannot be priced" is too strong as stated — the cheap next step is a
coverage probe by ticker before assuming IBKR is the only route.

#### Same-day addendum — does E survive "we never hold to expiry"?

Operator objection (2026-08-04): positions are closed early in practice, and
credits especially are closed before terminal gamma. E is a hold-to-cap mark, so
does it measure a counterfactual we would never trade? Checked both reads:

**bull_put band: survives.** 30% of window bull_put rows sit at E = +1.00
(structural max = expired worthless), and 5 of the 9 in-band rows are among them
— so the E-based band number IS partly a hold-through-gamma artifact. But R
already prices the early close (credit PROD = `profit_target 0.65`, no stop, no
time exit; only 2 of 33 rows exit `expired`), and the split holds under R alone:
in-band R +0.152 (median +0.666) vs out-of-band R −0.677. Conclusion unchanged.

**bear_put DEMOTE: the verdict is measure-dependent. Recorded, not resolved.**

    criterion          mean      CI 95%             halves           verdict
    E (hold-to-cap)   −0.254   [−0.392, −0.091]   −0.100 / −0.338   DEMOTE
    R (PROD exits)    −0.040   [−0.218, +0.177]   +0.221 / −0.183   NO ACTION

Pre-registration picked E deliberately, and three things still argue for it
here: (a) R's rescue is exit-driven — 32 of 82 bear_put rows (39%) exit on a
risk control (`stop_loss` 14, `dollar_stop` 10, `trailing_stop` 8), i.e. the
structure reaches breakeven only by being cut fast; (b) **no transaction cost is
modelled anywhere** — `spread_width_pct` is the synthetic short-strike width,
not bid/ask, and fills are the Barchart Open, so realistic two-leg fills in a
fast tape push R below zero; (c) R's halves run +0.221 → −0.183, deteriorating
as the bear episode deepens, which is the wrong direction for a bear structure.
Still: the demotion should be stated as "negative unmanaged, breakeven only
under active risk control", not "loses money". Re-check on the full window.

**Real gap this exposes (new candidate).** `simulation.credit.time_exit_dte_fraction`
is explicitly `null` ("ride toward expiry within path_cap") while debits carry
0.75 — the credit profile does exactly the thing we would never do live, and
11 of 33 bull_put rows exit `cap_open`, i.e. ran to the 120-day path cap. A
gamma-motivated DTE-floor exit for credits (close at ~21 DTE) is untested and
cheap to sweep. Do it on the credit book AFTER the window completes; it is not
part of the pre-registered bear decision run.

---

