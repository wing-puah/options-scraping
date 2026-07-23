# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index.

**State of play (2026-07-22).** Shipped config is the source of truth —
`config/backtest.yml` (exits, `regime_exit.cells: BEAR_HE` only) and
`config/deployment-rules.md` (VETO / A / B / C ladder, top-3 per day,
bull_put band `0.08 ≤ |delta| ≤ 0.20` + `DTE ≤ 59`). The 25-date regime-gap
gate is CLOSED (archive/06). The one open question is **bear_put**: the
pre-registered study returned DEMOTE, the verdict is deliberately *not*
implemented, and it now waits on the Feb–Apr 2026 holdout below.

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
replay harness (`backtests/exit_mechanism_study.py`, `combined_exit_study.py`)
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

Ran the addendum-11 follow-up: `backtests/exit_switch_structure_study.py`
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

No production config changed. New file: `backtests/exit_switch_structure_study.py`
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
- C6 deployment ladder (config/deployment-rules.md): do the existing vetoes /
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

`backtests/bear_position_study.py` → `backtests/bear_position_study_output.txt`.
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
| 3  | 2026-02-13 | yes | — | 0% | 0% | 0% | 0 | 🚧 full chain → analyze |
| 4  | 2026-02-17 | yes | — | 0% | 0% | 0% | 0 | 🚧 full chain → analyze |
| 5  | 2026-02-19 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 6  | 2026-02-23 | yes | ✅ | **0%** | 100% | 100% | 260 | ⚠ in book WITHOUT eod_iv — see flaw note |
| 7  | 2026-03-02 | yes | ✅ | **0%** | **0%** | **0%** | **0** | ⚠ in book with NO enrichment at all |
| 8  | 2026-03-03 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 9  | 2026-03-04 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 10 | 2026-03-05 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 11 | 2026-03-06 | yes | ✅ | 100% | 100% | 100% | 278 | in book, complete |
| 12 | 2026-03-09 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 13 | 2026-03-10 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 14 | 2026-03-11 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 15 | 2026-03-12 | yes | ✅ | 100% | 100% | 100% | 84 | in book, complete |
| 16 | 2026-03-13 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 17 | 2026-03-16 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 18 | 2026-03-17 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 19 | 2026-03-18 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze (etfs compiled absent) |
| 20 | 2026-03-19 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 21 | 2026-03-20 | yes | ✅ | 100% | 100% | 100% | **0** | ⚠ in book with BLANK iv_spread |
| 22 | 2026-03-23 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 23 | 2026-03-24 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 24 | 2026-03-25 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 25 | 2026-03-26 | yes | — | 0% | 0% | 0% | 0 | full chain → analyze |
| 26 | 2026-03-27 | yes | ✅ | 100% | 100% | 100% | 253 | in book, complete |
| 27 | 2026-03-30 | yes | — | — | — | — | — | ✅ scrape → ✅ compile → full chain → analyze |
| 28 | 2026-03-31 | yes | — | — | — | — | — | ✅ scrape → ✅ compile → full chain → analyze |
| 29 | 2026-04-01 | yes | — | — | — | — | — | ✅ scrape → ✅ compile → full chain → analyze |
| 30 | 2026-04-02 | yes | — | — | — | — | — | ✅ scrape → ✅ compile → full chain → analyze |
| 31 | 2026-04-06 | yes | — | — | — | — | — | ✅ scrape → ✅ compile → full chain → analyze |
| 32 | 2026-04-07 | yes | — | — | — | — | — | ✅ scrape → ✅ compile → full chain → analyze |

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
6. Re-run `backtests/bear_position_study.py` **unmodified** against the
   Feb–Apr 2026 rows only. The pre-registered decision rule from addendum 13
   applies as written: DEMOTE iff mean E < 0 AND bootstrap CI upper < 0 AND
   both halves negative.

If the holdout agrees, the demotion ships and the "sample was a bull market"
caveat in addendum 14 is answered by a second independent drawdown. If it
disagrees, bear_put stays at Tier C and the 2024-06 → 2026-03 result is
recorded as window-bound. Either way the decision is made once, on the
holdout, and not by re-cutting the 663-row book again.
