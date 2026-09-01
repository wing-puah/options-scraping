# Deployment rules — evidence

Why every rule in [`docs/deployment-rules.md`](../docs/deployment-rules.md) exists,
what it was measured on, and what would make it revert.

The card is the operator's document; this is the research record behind it. It is
a **summary of** the tuning log ([`current.md`](current.md) + [`archive/`](archive/)),
not a second source — when the two disagree, the log wins and this file is stale.

Split out of `deployment-rules.md` on 2026-08-12, when v3 tuning closed and the
rules stopped churning. Nothing was dropped in the split.

---

## Provenance of the ladder

Derived **2026-07-19** from the 607-row pooled book; **re-validated 2026-07-21
at the ≥800 gate** (762 pooled priced rows). See
[`archive/04`](archive/04-pooled-evals-and-ladder.md) §"Deployment ladder" for the
derivation and [`archive/05`](archive/05-pooled-evals-762-and-regime-labels.md)
§"≥800-GATE EVALUATION" for the re-validation.

The analysis emits a median 10 plays/day and live capital supports 1–3
positions — the ladder exists because something has to choose.

Every rule on the card is a **≥2-snapshot-confirmed** backtest finding except
where marked PROVISIONAL.

### Validation at 762 pooled priced rows (score-free ladder)

Numbers are for the ladder after the `score_total` membership clauses were
removed (see "Closed threads" below).

- Tier means **monotone in every cut**: pooled (+0.64 / +0.28 / −0.02 / −0.39),
  real-priced (+0.77 / +0.31 / −0.01 / −0.45), pre-13c, post-13c, and both time
  halves. A > B > C > VETO never inverts.
- Post-13c only: A vs C MWU **p = .0001**, B vs C **p < .0001**. A vs B is
  ordered but not separated (+0.50 vs +0.40, p = .98) — **watch item, still open**.
- Post-13c capped replay: top-1/day **76% win / +0.41 mean**; top-3/day **69%
  win, $30.3k from 97 rows** — better than the with-score-clauses ladder
  ($19.1k, 61% win) on the same dates.
- 2026-07-19 book (607 rows, the derivation sample): top-1/day +0.82, top-3
  +0.45 vs +0.14 take-everything; top-3/day = 28% of positions but **83% of book
  P&L**.

### Why the vetoes

Vetoed rows lost **−$21k** on the pooled book (n=96, 38% win). The vetoes are
the most reliable part of the ladder.

| Veto | Evidence |
|---|---|
| `bear_call_spread` | −0.82 mean, 17% win. Intake-vetoed since Attempt 13; 0 emissions since. An emission is a pipeline bug, not a trade. |
| Any play, regime BEAR + H-VOL | n=47, 30% win, mean −0.34 — worst cell in every snapshot since 07-12. The bear arm re-confirmed it independently: bear in model H-VOL is **−$50.5k at a 9% win rate, \|MAE\|/MFE 4.01**. |
| Any credit play, regime RANGE + L-VOL | n=20, mean −0.49. |

### Why the tiers

- **Tier A** — `bull_call_spread` in RANGE or E-VOL: pooled n=147, 67% win,
  mean +0.64; real-priced +0.77.
- **Tier B** — pooled n=168, 60% win, mean +0.28.
- **Tier C** — pooled n=262, 51% win, mean +0.09. **Dead money, not poison** —
  fine to paper-track. Its named residents: `bear_put_spread` with
  `iv_spread` > 0 (a **3×-confirmed** MAE penalty), low-delta/long-DTE
  `bull_put_spread`s that miss the §3 band, and everything else.

The 08-11 ML search independently rediscovered the structure: the full-sample
depth-3 tree's root split is `structure = bull_call`, unprompted.

### The bull_put geometry band

Derived at the ≥800 gate, **n=118 real-priced**. The qualifying
`|d| ≥ 0.08 / DTE ≤ 59` cell runs **80% win / +0.25 mean** vs **60% / −0.08**
violated, and holds post-13c at **+0.15 / 80%**.

Delta is a **band, not a floor**: `> 0.20` runs **−0.39** and `< 0.08` runs
**−0.28**. DTE 45–59 carries the whole edge (**+0.47, 87% win**); DTE ≤ 22
produced the post-13c `dollar_stop` losers.

**The ≤ 0.20 cap and the 45–59 preference are thin-n — PROVISIONAL.**

---

## Exit rules — why each one ships

### The BEAR_HE trail (shipped 2026-07-22)

Keyed on the **mechanical** regime of the signal date, not the model's label.
Model labels win for selection, mech labels win for exit conditioning — opposite
jobs, both evidenced. See [`archive/06`](archive/06-mech-regime-and-shipped-exits.md)
§2026-07-22 addendum 4.

**The mechanical label, for reference** (the card says read `mech_cell` off the
row; this is what that column computes, from SPY/^VIX closes as of the signal
date):

- direction = **BEAR** if SPY < its 50-day SMA **and** the 20-day return < 0
- vol = **E-VOL** if VIX ≥ 30 or the 5-day VIX change ≥ +25%; **H-VOL** if
  VIX ≥ 20; else L-VOL

Rationale: in bear/high-vol tape, debit winners reach a high MFE and give it
back before the 0.90 target fires. The trail converts that unrealized peak into a
realized exit. **Worth +$4.4k in the study**; the effect is confined to this
cell, which is why no other cell is switched.

**Status: PRE-GATE EXCEPTION, not a cleared rule.** 5 of 6 pre-registered
criteria passed; the 6th is mis-specified for a zero-inflated delta and can only
be re-tested on new BEAR/H-VOL data. Historical escape routes are closed
(Barchart options-flow doesn't reach back past ~2024-02 — addendum 6), so it
shipped ahead of its gate deliberately.

### The bear-debit peak-triggered breakeven stop (shipped 2026-08-11 — REVERTED 2026-08-24)

**REVERTED 2026-08-24.** First floor evaluation of the pre-registered rollback
trigger (below, and `research/pre-registrations/f2_management/rollback_triggers.md` — a
correlated-window re-read on the v4 exports, registered as such before the
numbers were read): 92 arming rows / 53 dates ≥ the 60-row floor; total gain
vs PROD **+$58** (pass, but ~zero), mean-R on affected rows +0.0071 (pass),
per-year mean-R delta **2024 +0.022 / 2025 −0.034 → condition three FIRED**.
Operator decision: revert `simulation.structure_exit.enabled → false`. The
original shipping evidence below is kept verbatim as the record of what the
rule looked like on v3.


**This is not an edge. It reduces a loss.** On 332 bear debit rows (real+tweak,
`bear_put_spread` + `long_put`), on the study's basis: mean R **−0.133 → −0.092**
(~**31% less bleed**), **−$54.4k → −$38.0k**. Bear selection stays negative
afterwards; the breakeven stop only stops giving back a peak that was already there.

Evidence (`bear_arm` study, 2026-08-11, git 470b95f, 08-11 v3 exports; report
not retained on disk — the figures here are the record): paired date-clustered CI
**[+0.015, +0.065]**, **every LOO fold positive** (min +0.038), right-signed in
all three years (2024 +0.036 / 2025 +0.055 / 2026 +0.028, the last with its own
CI [+0.009, +0.053]) and in both pricing tiers (real +0.054 / tweak +0.027).
Exit mix on the study basis: `be_stop` 0 → 44, `stop_loss` 110 → 92.

Chosen over the competing trails on **robustness, not pooled size** — it is the
only config whose 2026-alone CI excludes zero, and its pooled CI is the tightest:

    config              Δ pooled   CI95            ex-25MarApr   2026 alone              LOO min
    BE ratchet @.50     +0.041   [+0.015,+0.065]   +0.020        +0.028 [+0.009,+0.053]  +0.038
    trail .40/.50       +0.042   [+0.007,+0.073]   +0.023        +0.037 [-0.002,+0.077]  +0.038
    trail .25/.50       +0.043   [+0.003,+0.081]   +0.020        +0.025 [-0.032,+0.078]  +0.038
    trail .50/.50       +0.036   [+0.005,+0.064]   +0.014        +0.031 [-0.002,+0.066]  +0.032

**It is bear-KEYED, and the keying is the finding.** The identical config on the
NON-bear debit book measures **+0.234 → +0.209 — a loss of 0.026**. Applying a
peak-triggered breakeven stop to bull_calls actively destroys value: those positions
routinely dip back through entry on the way to the 0.90 target, and the breakeven stop
sells them there. Credits get nothing — no reproducible credit-side change, and
the only bear credit structure (`bear_call_spread`) has been intake-vetoed with
0 emissions since Attempt 13. On the credit side (bear_call, n=38), `pt .50`
clears CI+LOO (+0.344) but the best config `sl 1x` does not
(CI [−0.012, +1.252]), the population is one year deep, and there is nothing to
apply it to.

Leak guard **PASSED**: non-bear debits (n=261) 0 rows changed; credits (n=202)
0 rows changed. Now enforced by tests.

**Known reach limitation — the breakeven stop does not address most bear give-back.**
Measured 2026-08-12 (scratch cut, `current.md` §"bear MFE give-back"): 82% of
bear debit rows go into profit at some point and 56% of those finish ≤ 0, but
**124 rows peaked between +1% and +50% and lost −$77.2k entirely below the +0.50
arming threshold**. `stop_loss` and `dollar_stop` rows carry mean MFE +0.217 and
+0.287 — 178 positions were up 20–30% and stopped out anyway. A lower threshold
is a **candidate, not a finding**: the census of peaks does not price the cost on
winners that dip back through entry, and that cost is what made the identical
config lose value on the non-bear debit book. Do not read the shipped breakeven stop as
covering this.

### Why the trail suppresses the breakeven stop (interaction check A3)

The breakeven stop was measured against a no-trail profile, but a bear debit opened on a
BEAR_HE date also gets the 0.50/0.50 trail — a stack the frozen grid never
evaluated. One confirming config was run:

**"BE @.50 + trail .50 trig .50" scores Δ+0.036 with zero `be_stop` exits,
bit-identical to the trail alone**, and below the breakeven stop alone (+0.041). The
cause is structural, not sampling: the trail arms at peak ≥ 0.50 and its floor
(peak − 0.50) is then ≥ 0 — at or above the breakeven stop's threshold — and
the trail
is checked first. The breakeven stop is **strictly dominated** inside BEAR_HE.

So the breakeven stop is suppressed there, at **zero measured cost**: suppress vs stack
over the 224 BEAR_HE bear-debit rows differ on **0 rows**. Each rule stays inside
the envelope it was measured in.

### The production delta is a third of the study delta — record this

The study measured against `DEBIT_PROD` (pt .90 / sl .75 / tef .75, **no
trail**). Production has shipped the BEAR_HE trail since 07-22, so the study's
baseline was never production's:

    bear debit (n=332)          mean R              total $            rows changed
    study framing            -0.133 → -0.092                              —
    production, measured     -0.109 → -0.093    -43,806 → -37,951         16
      on BEAR_HE (suppressed) -0.152 → -0.152    unchanged                 0
      elsewhere (n=108)       -0.019 → +0.028     -4,916 → +939           16

The shipped rule is worth **+0.015 mean R / +$5.9k**, not +0.041 / +$16.4k, and
`be_stop` fires on **16 rows, not ~44**. The two rules were largely buying the
same rows and the trail got there first on 224 of 332.

**Generalisable lesson: a study delta measured against `DEBIT_PROD` overstates
production impact wherever a regime cell already ships a rule that converts the
same rows. Every future exit study should quote both baselines.**

### Preconditions behind the exit table

- **Entry basis: next trading day's OPEN** — the backtest's basis since
  2026-07-06. Same-day fills were never modeled.
- Credit structural sizing: risk is defined by wing width, not a stop. The
  Attempt-13 removal of the credit stop-loss (1× → null) priced 10/10
  stop-recovery whipsaws; the bull_put book went **+$1.8k → +$5.5k**. Its
  rollback trigger was tested 2026-07-21 and **NOT MET** (sl-none still beats
  sl-1× on a fresh 51-row window).
- Implementation: `simulation.regime_exit` / `simulation.structure_exit` in
  `config/backtest.yml`; labels from `lib/mech_regime.py`. Merge order is
  **base → structure → regime**, which is what lets the regime cell switch the
  breakeven stop off.

**The card's exit table, as config values** — each row maps to a block in
`config/backtest.yml`:

| Card row | Config |
|---|---|
| Debit, normal | `simulation:` — `profit_target: 0.90`, `stop_loss: 0.75`, `time_exit_dte_fraction: 0.75`, no trail |
| Debit, mech BEAR + H/E-VOL | `simulation.regime_exit.cells.BEAR_HE` — `trailing_stop_trigger: 0.50`, `trailing_stop_pct: 0.50`, `be_after: null` |
| Bear debit, other dates | (reverted 2026-08-24 — falls back to the normal debit row; the `structure_exit` block is kept in config with `enabled: false`) |
| Credit | `simulation.credit` — `profit_target: 0.65`, `stop_loss: null`, `time_exit_dte_fraction: null` |

The `exit_basis` column on a result row records which of these actually governed
it: `{PROD, CREDIT, BEAR_DEBIT, <regime cell>}`, reported in merge-precedence
order. See `docs/backtest-reference.md`.

---

## The bear hedge sleeve, in full

**Bear is deployable as a HEDGE, not as a selection.** This is the resolution of
the bear_put thread and it is not a compromise position — both halves were
tested (`bear_deploy` study, 2026-08-11, git 470b95f, 08-11 v3 exports; report
not retained on disk — D1/D2 below are the record).

### D1 — why not a selection

**0 of 496** pre-registered conditioned subsets survive — mech cell, mech/model
direction, vol label, delta band, DTE band, `iv_spread`, `iv_pct`, singles and
pairs — re-run **under the new breakeven exit**, not just the old one. ~10 false
survivors were expected by chance at a nominal 5% rate, so zero is a clean
negative.

370 bear rows (bear_put 327 / bear_call 37 / long_put 6), 111 dates. Pooled
E **−0.601**, CI [−0.726, −0.477], negative every year (−0.815 / −0.660 / −0.386).
The best subset in the entire search is E −0.231 (`mech BEAR AND iv_pct<0.5`,
n=43) — still negative. **There is no rule that tells you a bear play will be a
winner. Stop looking for one.**

The operator's chop hypothesis, tested directly, turns out to be an exit story:

    slice                    n    dates   E        R        $        |MAE|/MFE
    model RANGE + C/L-VOL    55   16     -0.370   +0.182   +$10,119   0.76
    model C-VOL              53   20     -0.596   +0.128    +$7,095   0.92
    mech L-VOL               97   38     -0.581   +0.002    +$3,586   0.99
    model H-VOL              78   17     -1.157   -0.682   -$50,482   4.01

RANGE+C/L-VOL is the only bear slice that makes money (R positive in 2 of 3
years: −0.247 / +0.320 / +0.284) and its |MAE|/MFE of 0.76 is the only
non-mirrored bear number in the book. But **E is −0.370 with CI
[−0.697, −0.045]** and the R CI [−0.117, +0.463] includes zero: the plays are
still wrong, the exit is what collects. Directionally consistent with the
instinct; **not a selection edge**, and n=55 over 16 dates.

### D2 — why a hedge

The bear sleeve pays exactly where the deployed book hurts. On the deployed
ladder's own dates:

| Deployed-book dates | n | deployed R | bear R | bear $ | bear win% |
|---|---|---|---|---|---|
| Worst decile | 8 | −0.795 | **+0.252** | +6,669 | 75% |
| Worst quartile | 21 | −0.457 | +0.184 | +16,824 | 67% |
| All negative dates | 25 | −0.390 | +0.109 | +16,985 | 60% |
| Positive dates | 59 | +0.706 | −0.281 | −41,895 | 32% |

Date-level correlation between the two sleeves is **−0.13**, and the tail is
positive in **2 of 3 years** (2024 +0.129, 2026 +0.405; 2025 −0.048).
Pre-registered D2 criteria: **MET on all three.** The sleeve loses money on
balance and buys drawdown protection with it — that is what insurance is.

This closes the "the book can't price a hedge" caveat from the bear arm, which
was too strong: 84 of the bear dates also carry a deployed ladder sleeve, so the
concurrent book exists and the portfolio question is answerable on it.

### D4 — the pick rule

Rank by **`|delta|` DESCENDING** (closer-to-money). Within-date paired gain
**+0.232**, CI **[+0.091, +0.370]**, **every LOO fold positive** (min +0.204),
positive in all three years (2024 +0.285 / 2025 +0.312 / 2026 +0.083), across 93
dates with ≥2 bear candidates. It **holds on the SHIPPED exit** too (+0.159, CI
[+0.028, +0.280]) — not an artifact of the new breakeven stop.

The worst things you can do, from the same ten-ranker test:

| Ranker | Paired gain |
|---|---|
| `\|delta\|` DESCENDING | **+0.232** |
| `\|delta\|` low first | −0.212 |
| `score_total` high first | −0.255 |
| widest max-loss first | **−0.345** (worst of ten) |

`|delta|` is **not on the analysis row** — read it in IBKR at order entry, the
same caveat the bull_put band carries.

### D3 — sizing, and the formal failure

At **f = 0.50** the book's max drawdown **improves, −7,609 → −7,037**, with total
P&L also up (+$1,429). At f = 1.00 drawdown gets worse again (−7,780). Half size
or less is the whole recommendation.

**D3 is formally NOT MET, by $86.** The pre-registered sizing rule required both
drawdown *and* worst single date to be no worse than carrying no sleeve. At
f = 0.50 drawdown improves by $571 but the worst date degrades from −3,212 to
−3,298. The rule fails on a rounding-scale margin; it is reported as failed, not
waved through.

### The curve D3 was read on understates drawdown (2026-08-31, `hedge_exposure` ARM M)

ARM M put the SAME unhedged book on both equity curves — mark-to-market from
`daily_pnl_csv` against the realized-on-close curve `account_sim.equity_curve`
already produces — and they do not agree:

| population | MTM max DD | close-bucketed max DD | gap |
|---|---|---|---|
| `real` stratum (485 rows) | −$21,890 | −$22,592 | MTM **better** by $702 (3.1%) |
| **`all`, the ratified book (996 rows)** | **−$32,571** | **−$23,239** | **close UNDERSTATES by $9,332 (40.2%)** |

Verdict **MEASUREMENT-ONLY**. The mechanism question in that same study is
**UNDERPOWERED** — every cell of the τ × f grid is power-stopped on the ratified
population — so nothing there says a hedge works, and no direction is quoted
from any cell. See [`current.md`](current.md) 2026-08-31 and
[`hedge-exposure-errata.md`](hedge-exposure-errata.md) §RATIFICATION.

**Why it lands on D3.** D3 is judged on a series of daily REALIZED dollars
bucketed to the date each position closed (`_sweep`'s `daily` in
`f4_deployment/bear_deploy.py`), never on a path that marks open positions. Two
other rules read that same criterion off that same kind of curve:

- **`calendar_hedge` H3** — "D3 verbatim" by its own registration (the largest
  f whose max drawdown AND worst single date are both no worse than f = 0). It
  sits inside a ship ceiling never reached (v4: H0 FILL NOT MET, H2 NOT
  EVALUABLE), so nothing here changes a verdict — it qualifies the basis on
  which H3 *would* be judged.
- **`hedge_timing` ARM H4** — judged by D3's criterion verbatim, and the dollars
  column behind the GAP-UP row in §"Hedge-timing triggers" below ("gating
  −$5,893, drawdown unimproved"). NOT the same label as that study's ARM H3,
  which is a paired-R arm quoting no dollars — see
  [`arm-index.md`](arm-index.md) on the H-label collisions.

**What this does NOT do.** All three verdicts STAND, and no number in this file
is restated. ARM M measured `hedge_exposure`'s own 996-row concentrated book on
its own session axis — NOT D3's bear-sleeve book, NOT H4's deployed-ladder
dollars — so **40.2% is not a correction factor to apply to their figures**, and
the `real` stratum shows the gap can run the other way and be small. What
transfers is the basis, not the number.

**What it does.** Quote it with the rule. The drawdown leg of D3 / `calendar_hedge`
H3 / `hedge_timing` H4 is measured on an instrument that, on a book measured the
same way, missed 40% of the drawdown. D3's own margins are $571 of drawdown
improvement and an $86 formal failure on the worst date — margins a measurement
basis carrying a double-digit-percent question mark cannot support in either
direction. Any future re-read that wants to CONCLUDE about drawdown should
compute the mark-to-market curve (`backtest_study/lib/mtm_curve.py` returns both
bases from one call, so a caller cannot mix them) rather than re-reading the
close-bucketed one.

### Remaining limits — quote these with the rule, they are not footnotes

- The **worst-decile row-level CI includes zero** ([−0.113, +0.639], n=28). The
  tail effect is directionally consistent and reproduces by year, but 8 dates is
  8 dates.
- **88% of bear rows are `bear_put_spread` and only 6 are naked `long_put`**, so
  **none of this covers the naked-put substitution** the operator sometimes makes
  at order entry. A naked put is a different instrument with different path
  behaviour; it is untested here.
- **D5's timing gate does not reproduce across years.** Carrying the sleeve only
  on selected dates looked like the best of both — mech H-VOL at f=1.00 is
  **+$3,336 with drawdown improved (+768)**, mech BEAR_HE at f=1.00 **+$2,243**
  on the same terms. But the leading gate (H-VOL, 46 days) splits by year into
  **−$2,655 / +$5,179 / +$813**: one good year and two near-zero ones, the
  Mar–Apr-2025 failure pattern. D5 was also **post-hoc** — chosen after seeing
  D2. **PROVISIONAL, not a rule**; re-read on the next independent window before
  gating the sleeve on anything.
- **The drawdown leg is measured on the close-bucketed curve**, which
  `hedge_exposure`'s ARM M found understates max drawdown by **40.2%** on its own
  ratified book (§"The curve D3 was read on understates drawdown" above). D3
  stands; its measurement basis is qualified, and the same qualification travels
  to `calendar_hedge` H3 and `hedge_timing` ARM H4.
- **This rule barely fires by design.** Every bear row in the book is ladder
  **Tier C (299) or VETO (71)**; none is Tier A or B, so the shipped ladder never
  deploys one. The sleeve only bites on bear positions the operator takes
  *deliberately*.

---

## Deployment reference stats

Look-up table for deploy time. Source: `bear_giveback` study ARM S, 2026-08-12,
git 470b95f, 08-11 v3 exports; report not retained on disk — this table is the
record. Book = **795 rows, real+tweak
only** (bs excluded — attenuating). **Profit factor (PF) = gross winning $ /
|gross losing $|** on realized R. **PF < 1.0 means the cell lost money however
good its win rate looks.**

**Read these as in-sample descriptions of the book, not predictions.** They do
not override the ladder — the ladder is the decision rule and these are the
numbers behind it. Cells below n≈20 move a lot.

### By ladder tier — monotone in PF, which is the point

| Tier | n | Win | PF | mean R | $ |
|---|---|---|---|---|---|
| **A** | 131 | 63% | **2.29** | +0.400 | +50,017 |
| **B** | 166 | 67% | **1.78** | +0.303 | +32,141 |
| C | 408 | 43% | 0.79 | −0.098 | −41,516 |
| VETO | 90 | 32% | 0.34 | −0.394 | −28,311 |

### By structure

| Structure | n | Win | PF | mean R | $ |
|---|---|---|---|---|---|
| `bull_call_spread` | 242 | 60% | **2.05** | +0.329 | +79,392 |
| `bull_put_spread` | 166 | **68%** | **0.94** | +0.063 | −2,163 |
| `bear_put_spread` | 327 | 37% | 0.74 | −0.114 | −44,774 |
| `bear_call_spread` | 37 | 32% | 0.19 | −0.578 | −11,221 |
| `long_put` | 6 | 17% | 0.01 | −0.613 | −4,884 |
| `long_call` | 8 | 0% | 0.00 | −0.522 | −8,221 |

**`bull_put_spread` is the entry to read twice: 68% win — the highest of any
structure — at PF 0.94 and −$2.2k.** Two-thirds of them win and the book still
loses money, because the losers are far bigger than the winners. **Win rate is
not a deploy criterion.** This is the fat-left-tail problem the §3 geometry band
exists to manage.

### The deploy cell: `bull_call_spread` by model regime × vol

| Regime + vol | n | Win | PF | mean R | $ |
|---|---|---|---|---|---|
| RANGE + H-VOL | 13 | 77% | 9.80 | +0.644 | +10,425 |
| **RANGE + E-VOL** | **50** | 66% | **2.99** | +0.543 | +25,423 |
| BULL + C-VOL | 40 | 75% | 5.01 | +0.544 | +24,507 |
| BEAR + E-VOL | 20 | 65% | 2.37 | +0.446 | +6,760 |
| RANGE + L-VOL | 15 | 53% | 1.81 | +0.197 | +3,700 |
| RANGE + C-VOL | 32 | 56% | 1.35 | +0.179 | +4,926 |
| BULL + L-VOL | 60 | 43% | 1.07 | +0.033 | +1,919 |

RANGE + E-VOL at n=50 is the only large, high-PF cell — this is the Tier A
engine. RANGE + H-VOL's PF 9.80 is **n=13; do not read it as a better cell**.
BULL + L-VOL is where bull_calls go to do nothing (PF 1.07 on 60 rows).

### By mech cell × structure (mech = the exit-conditioning label)

| Mech cell | Structure | n | Win | PF | mean R | $ |
|---|---|---|---|---|---|---|
| BEAR_HE | `bull_call_spread` | 95 | 64% | 2.58 | +0.463 | +38,787 |
| BEAR_HE | `bull_put_spread` | 90 | 67% | 1.25 | +0.063 | +5,083 |
| BEAR_HE | `bear_put_spread` | 218 | 35% | 0.66 | −0.164 | −40,277 |
| BEAR_HE | `bear_call_spread` | 31 | 35% | 0.27 | −0.440 | −7,461 |
| LVOL | `bull_call_spread` | 125 | 54% | 1.58 | +0.192 | +26,912 |
| LVOL | `bear_put_spread` | 91 | 46% | 1.18 | +0.088 | +7,347 |
| LVOL | `bull_put_spread` | 61 | 67% | 0.63 | +0.027 | −5,689 |
| RB_EVOL | all | 17 | — | <1 | negative | −7,289 |

Two things worth carrying to deploy time: **bull_call in BEAR_HE is the single
best large cell in the book** (PF 2.58, n=95) — buying calls into mechanical
bear/high-vol tape is where the engine earns, which is counter-intuitive enough
to state plainly; and **`bear_put_spread` in LVOL is the only bear cell with
PF > 1** (1.18, n=91), consistent with the chop-hedge slice in D1.

---

## Open pre-registered rollback triggers

Live commitments. Each was written **before** its rule shipped and must be
evaluated when its gate is reached — passing promotes the rule from
shipped-on-one-study to **cleared**; failing reverts it.

| Rule | Re-evaluate at | Revert if | Implementation to revert |
|---|---|---|---|
| **BEAR_HE trail** (07-22) | ≥25 affected BEAR + H/E-VOL dates of **new** data | the cell's total gain vs PROD is ≤ 0, **or** the affected-date median gain is < 0 | `simulation.regime_exit.cells.BEAR_HE` → no trail |
| **Bear-debit `be_after: 0.50`** (08-11) | ≥60 **new** bear-debit rows that actually **arm** the breakeven stop (peak P&L ≥ +0.50) | total gain vs PROD on those rows is ≤ 0, **or** the mean-R delta on affected rows is < 0, **or** any single year of the pooled book flips negative | `simulation.structure_exit.enabled` → `false` |
| **bull_put delta/DTE band** | the next independent window (the ≤0.20 cap and 45–59 preference are the thin-n parts) | — PROVISIONAL, re-read rather than a hard revert | the band clause in the card's §3 |

Progress toward the first two accumulates from live fills plus new backtest
rows. **Never read silence as "not met"** — check the numbers.

**First census + evaluations (2026-08-24, v4 exports, correlated-window
re-read — `research/pre-registrations/f2_management/rollback_triggers.md`):**

| Trigger | Census | Outcome |
|---|---|---|
| BEAR_HE trail | **1** affected date of 25 | UNDERPOWERED — no reading; census is the recorded result |
| LVOL tef-null (corrected gate) | **31** affected dates ≥ 25 | all four criteria PASS (median +0.023, total +5.70, both halves +, no flip) — **CLEARED on the correlated window; operator HELD the ship** pending genuinely new dates |
| Bear-debit `be_after` | **92** arming rows ≥ 60 | condition three FIRED (2025 −0.034) → **REVERTED** |
| Credit sl-none | **0** fresh bull_put rows of 15 | UNDERPOWERED — `sl 1x (pre-Attempt-13)` comparator now printed by every credit run |

---

## Hedge-timing triggers (2026-08-28 — one drafted-and-held prohibition, one closed question, one untestable habit)

`hedge_timing` (f4, registered 2026-08-28, era v4 decisive + v3 replication,
graded) tested the operator's three discretionary hedge-deploy triggers.
Nothing shipped — the study's registration forbids shipping from this
correlated window under every outcome.

| Trigger | Verdict (v4) | What it means for §4 |
|---|---|---|
| **GAP-UP** (SPY open ≥ prior close ×1.003) | **CONTRARY** on H3 (paired excess −0.408, CI [−0.749, −0.057], every LOO fold, both years, all cuts) AND on H4 (gating −$5,893, drawdown unimproved) | A §4 prohibition is **DRAFTED AND HELD** (operator pre-chose draft-and-hold): *"Do not open the hedge on a gap-up day — the same-day A/B long out-earned the bear by 0.67 R on those days, an excess of +0.41 R over ordinary days, and gating the sleeve on them bought no drawdown protection."* v3 read: H3 underpowered by one date, H4 directionally consistent (−$6,293, negative all three years incl. 2026). Accepting or rejecting the draft is the operator's decision. |
| **CHOP** (eff_ratio bottom tercile) | NULL / NULL / UNSTABLE | No support, no contradiction. Timing stays discretion. |
| **DECLINE ≥3-of-5** (powered substitute) | NULL on all three arms | Per the pre-registered asymmetric rule, this NULL speaks AGAINST the strict 4–5-day habit: even the broad construct cannot separate hedge value. |
| **DECLINE strict 4–5 days** (the operator's actual rule) | UNDERPOWERED, fixed in advance (2 book dates) | **Untestable at this emission density** (~3,000 more trading days to a floor). The habit stays discretionary because it cannot be evidenced, not because it passed. |

**Forward trigger (blind, from the registration):** re-run when ≥25 book dates
carry a live strict N≥4 SPY down-run, or when ≥25 signal dates exist after
2025-11-04.

**Open question, queued by the operator (2026-08-28): can any hedge mechanism
reduce MAX DRAWDOWN at all?** H4's tables say the current sleeve cannot: max
DD is untouched by every gated policy on v4 and made WORSE by always-on
hedging on v3 (−$7,609 → −$18,278 at f=1.0). A dedicated study — mechanism,
not timing — is deliberately deferred; it must design around the known
worst-decile power wall (~9 dates).

**Measurement basis (recorded 2026-08-31):** ARM H4's dollars — including the
"gating −$5,893, drawdown unimproved" read behind the drafted GAP-UP prohibition
— come off the close-bucketed realized curve, judged by `bear_deploy` D3's
criterion verbatim. `hedge_exposure`'s ARM M shows that curve understating max
drawdown by 40.2% on its own ratified book, so H4's verdicts STAND on a
qualified basis; see §"The curve D3 was read on understates drawdown" above for
what does and does not transfer. Label note: that is ARM H4, the do-nothing
DOLLARS arm. The `H3` in the table above is `hedge_timing`'s paired-R arm and is
NOT `calendar_hedge`'s `H3` sizing criterion, which is the other rule the
measurement finding touches.

**Scope note on the operator's actual practice (2026-08-28):** the operator
hedges on EXPOSURE — a concentrated correlated book (semis → SMH, tech →
QQQ), a specific perceived risk, plus the analysis flagging hedge flow —
not on a calendar trigger. `hedge_timing` did not test that hypothesis: no
arm conditioned on book concentration or a hedge-flow signal, and the
instrument was the book's bear row, not a sector proxy. Exposure-conditional
hedging is therefore UNTESTED (neither supported nor contradicted here), and
the drafted GAP prohibition, if accepted, prohibits the gap AS the reason to
hedge — it does not speak to hedging concentrated exposure on a day that
happens to gap. The queued drawdown study is where that practice gets
tested: trigger = concentration × hedge-flow signal, counterfactual =
unhedged concentrated book, outcome = drawdown.

---

## Caveats on the ladder as a whole

- **Tier A partly encodes the RANGE/E-VOL cell that drove the book's profit.**
  In-sample circularity is mitigated by the time-split + post-13c holdout, **not
  eliminated**.
- **The ladder has never been walked forward live.** It is validated as a triage
  rule on backtest data only. Live fills are now the evidence source; see
  [`current.md`](current.md).
- **A vs B is ordered but not statistically separated** (p = .98 post-13c). Open
  watch item.
- **The ladder is a ≤60-DTE ladder by accident, not by design** — h ≥ 180 plays
  are unpriceable with real data and the `bs` proxy tier is now off
  (`proxy.bs_fallback: false`). See [`current.md`](current.md) §2026-07-27.
- **`score_total` is decision-irrelevant** (confirmed 2026-07-21). The 07-19
  monotone score bands were noise — selection is structure × regime. It survives
  only as a deterministic tie-break, which is why the v3→v4 scale change
  (0–100 → 0–50, or 0–55 for VOLATILITY intent) costs nothing beyond the
  incomparability itself.
- **`score_total` is only meaningful on rows emitted after 2026-07-13** (the 13c
  rubric fix). Pre-13c scores anti-select. All live rows qualify.
- **The v4 transfer is unvalidated.** Every rule here was derived on the v3
  population; the pre-registered composition bridge (`current.md` §"v4
  emission-composition bridge") has not fired yet.

---

## Closed threads

Recorded so they are not re-opened by someone reading only the card.

**The `score_total` ≥ 70 membership clauses (removed 2026-07-21).** Two clauses
promoted rows into tiers by score: `bull_call → A` and `any other debit → B`.
Marginal-value tests killed both — the first promoted rows that perform like
Tier B, the second was a bear_put leak. The score-free ladder's post-13c top-3
runs **$19.1k → $30.3k**. Tier membership is now structure × regime ×
entry-geometry only.

**The `bear_put` DEMOTION question (opened 2026-07-22, closed 2026-08-11) —
resolved WITHOUT a demotion mechanism.** All four pre-registered demote criteria
fired on the n=164 holdout, but demotion has nothing to act on: bear rows are
already Tier C or VETO and never enter the deployed top-3, so an intake veto
would remove positions the ladder does not deploy anyway — while also removing
the only instrument that pays on the book's worst dates. The answer to "bear
loses money" is **its own exit profile plus a pick rule**, not an intake veto.

**Superseded 2026-08-13 — a mechanism was chosen after all (operator
decision).** The demotion is now explicit as card rule **§1.4**: bear debit
(`bear_put_spread` / `long_put`) is vetoed **as a selection play**, with the §4
hedge sleeve carved out. Same substance as the 08-11 resolution — the intake
veto stays rejected (it would empty the sleeve's candidate pool), and zero
historical deployments change (all 370 bear rows were already Tier C or VETO).
What the card rule adds is closing the thin-day loophole: Tier C is
"skip when capital-constrained", so a bear_put could in principle have reached
the top-3 on a day with fewer than three A/B survivors. Now it cannot.
Decision logged in [`current.md`](current.md) §2026-08-13.

**The ML/selection question (closed 2026-08-11) — NULL RESULT.** Not one
positive gain with a CI excluding zero, in 15 model × strategy cells. Ablations
were non-monotone and inside the noise beyond structure × regime × geometry.
**Do not re-open this on new estimators — only on new COLUMNS.** Three columns
(`cpir`, `oi_confirm`, `iv_pct`) have already been caught looking predictive
pooled and vanishing within structure, so any new column is tested **within
structure** from the first look.

**The full column sweep (2026-07-21).** Only `delta`/`dte` (bull_put) and
`iv_spread` (bear_put) are decision-relevant. `oi_confirm`/`iv_pct` were killed
as composition artifacts; `score_catalyst`/`score_flow` are path-vol proxies.
