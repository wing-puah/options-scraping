# Archive 11 — 2026-08-12: edge status, bear MFE give-back, be_after grid, day-0 conditioning

Covers the 2026-08-12 exit-conditioning thread: the edge-status
assessment (real, narrow, NOT selection-tunable), the bear MFE
give-back quantification below the ratchet threshold, the `be_after`
grid RUN (does NOT ship; the give-back pattern is in the underlying),
and the day-0 underlying-move study (ARM C does not clear, no rule
ships; sensitivity is structural).
See [../README.md](../README.md) for the full section index.

---

## 2026-08-12 — edge status after close-out: real, narrow, NOT selection-tunable

**Question (operator):** reading this log it looks like there is no measurable
edge — is it a matter of fine-tuning the selection, or is the whole engine not
worth pursuing?

No new run. This is a verdict entry over the existing record, written because
the same question was asked on 07-21 and the answer has since changed in one
direction (selection is now closed, not merely unpromising) and hardened in
another (the edge reproduced on a completed third year).

### 1. The premise is wrong: there is an edge, and it is one cell

Real+tweak, bs excluded, from the 08-11 exports:

    structure          n     E        R        $          every year?
    bull_call_spread   338  +0.672   +0.295   +$80,237   YES (+0.44/+0.66/+0.29)
    bull_put_spread    237  +0.183   -0.005    -$1,946   no
    bear_put_spread    468  -0.528   -0.081   -$44,000   negative every year
    bear_call_spread    43  -1.240   -0.518   -$11,221   intake-vetoed

Ladder tiers reproduce out of sample in all three years (A +0.708/+0.670/+0.305,
B +0.338/+0.644/+0.431, C and VETO negative throughout). Top-3/day replay
+$22.7k / +$44.8k / +$8.8k at 64–67% win.

**The load-bearing framing: taking every emitted play makes +$14.0k over three
years** (−$14.4k / +$47.9k / −$19.5k). The engine emits ~10 plays/day and the
ladder discards ~70% of them to capture 83% of the P&L. **The value is in the
triage, not the generation.** The honest claim remains 07-21's: *the analysis
picks good bull_calls in elevated-vol range markets.*

### 2. Selection tuning is closed — three independent nulls

This is the part of the question the log can now answer definitively, where on
07-21 it could only say "unpromising":

- **496 pre-registered bear subsets → 0 survivors** (~10 expected by chance),
  re-run under the new exit. Best subset still negative.
- **ML combination search, 15 model×strategy cells → 0 positive gains with a CI
  excluding zero.** Best cell +0.022, CI [−0.017, +0.071].
- **Full column sweep → only `delta`/`dte` (bull_put) and `iv_spread`
  (bear_put) are decision-relevant.** `cpir`, `oi_confirm_pct`, `iv_pct`,
  `score_total` all looked predictive pooled and vanished within structure —
  the same composition trap caught four separate times.

The ML ablations put the binding constraint in the **columns, not the
estimator**, and the full-sample tree's root split is `structure = bull_call` —
the model rediscovers the ladder unprompted. **Further selection work on this
feature set has a measured expected value of zero.** The standing gate holds:
re-open on new COLUMNS, never on new models or new tuning of old ones.

### 3. What is actually unresolved is execution, and it is not accruing

Latest live-loop mapping (`stage1_report_2026-08-12.md`): **EXACT 0 /
STRUCTURE 2 / SUBSTITUTED 1 / NONE 15.**

Zero exact matches. The mapped fills are NVDA/TSM short-call overlays, MU and
GOOG round-trips, and a GLD `bull_call_spread` expiring 2027-01-15 (~155 DTE —
outside the ≤60-DTE band the ladder is validated in). **The book being traded
and the book the engine emits are close to disjoint.**

This is why "confirmed in backtest, not proven live" has not moved since 07-21.
Not because the live evidence came back bad — because there is none. Recording
it plainly: with backtest tuning closed, the live loop is the *only* experiment
in the system, and it is currently not running. Either Tier A/B top-3 gets
traded as emitted for ~30–50 positions, or the ladder stays backtest-confirmed
permanently. No further analysis resolves this.

### 4. Verdict, and one question the log has never asked

**Worth pursuing — but as a narrower instrument than the build implies, and the
pursuit is no longer backtest tuning.** A triage rule that turns +$14.0k of raw
emission into +$76k of top-3 P&L across three years is real work.

Standing caveats that keep "proven" out of it, unchanged: Tier A partly encodes
the RANGE/E-VOL cell that generated the profit (circularity mitigated by the
time split, not eliminated); rows within a date share a market path so the
p-values are optimistic; 25% proxy-priced; next-day-open on settlement-derived
pricing with no slippage model.

**Open question, flagged NOT tested:** does the LLM earn its keep? The ladder is
structure × regime × entry-geometry — entirely deterministic and computable
without a model. The ML study benchmarked estimators against the ladder *on the
plays the engine emitted*; it never tested engine-vs-no-engine. If the model's
real contribution is ticker/strike choice within a structure×regime cell, that
is testable against a mechanical baseline (e.g. bull_call spread on the
highest-flow-volume RANGE/E-VOL name). Logged as a candidate, with the warning
that it needs a pre-registration before anyone looks at a number — it is the
kind of question whose answer is easy to talk oneself out of.

---

## 2026-08-12 — bear MFE give-back: the shipped ratchet cannot reach 124 rows / −$77.2k

**Operator observation:** bear positions still show MFE, but most of it is
given back. **Confirmed, and larger than the log recorded.**

**Provenance.** Read-only scratch cut, same 08-11 exports as the bear arm
(`backtests/to_evaluate/`), `book.load_book(include_bs=False)` → **795 rows,
real 406 / tweak 389**. Bear debit = `bear_put_spread` + `long_put`, n=332 —
the same population the `be_after: 0.50` ratchet was measured on. No config,
prompt or ladder touched. Not run through `scripts/backtest_study/`, so this is
a scratch finding pending a proper study, not a shipped conclusion.

### 1. The give-back is the dominant bear failure mode

    population              n     rows ever green   full give-back   median capture
                                  (MFE > +1%)       (MFE>0, R<=0)    (R / MFE)
    bear debit             332    272  (82%)        152 of 272 (56%)     -0.55
    bull_call (comparator) 240    223  (93%)         80 of 223 (36%)     +0.42

**82% of bear rows go into profit at some point; 56% of those finish at or below
zero.** The median bear position that was ever green ends up losing *more than
half its peak, as a loss*. The comparator keeps +0.42 of its peak.

On the 152 full-give-back rows: realized **−$123.4k**, against **+$81.4k** if
each had been sold at its own MFE. That gap is not achievable — nobody sells at
the peak — but it sizes the pool the exit is fishing in.

### 2. The bleed sits entirely below the arming threshold

    MFE band                            n    mean R   win    $
    <= +1%  (never in profit)          60    -0.736    0%   -55,938
    +1% to +25%                        71    -0.585   15%   -45,289
    +25% to +50%  <- ratchet CANNOT arm 53    -0.545   17%   -31,916
    +50% to +90%  <- ratchet arms      46    -0.385   28%   -21,756
    >= +90%  (target zone)            102    +0.889   85%  +104,822

**124 rows peaked between +1% and +50% and lost −$77.2k. Every one is below
`be_after: 0.50`.** The shipped ratchet fires on 16 production rows; this band
is untouched by design.

Corroborated by the exit mix — `stop_loss` (n=109, mean R −0.786) carries mean
MFE **+0.217**, and `dollar_stop` (n=69, mean R −0.765) carries mean MFE
**+0.287**. **178 bear positions were up 20–30% and stopped out anyway.** That
is the operator's observation, stated as a number.

### 3. What this does NOT establish — read this before proposing a threshold

A lower threshold is the obvious move and it is **not yet supported**. What was
computed is a *census of peaks*, NOT a replay:

    peak >= X    rows arming   still finish negative   $ realized on those
      0.20           217              105                  -86,365
      0.25           201               92                  -75,102
      0.30           188               79                  -63,671
      0.40           162               58                  -46,707

**This table says only how many rows had a peak that high and lost anyway. It
does not say a ratchet would have saved them.** The missing half is the cost on
winners: the 102 rows in the ≥+90% band earning +$104.8k include an unknown
number that dipped back through entry *after* passing +0.25 and would have been
sold at breakeven. That is exactly the mechanism that made the identical config
destroy value on the non-bear debit book (+0.234 → +0.209). MFE/MAE cannot
resolve it — only a path replay can.

Also: **60 rows (−$55.9k) were never in profit at all.** No exit rule reaches
them. That is D1's unfixable selection problem, and it caps what any exit work
can recover.

### 4. Proposed follow-up — bounded, and pre-registered before it runs

This is an **exit** question, the one dimension the log has not closed (B2 found
a fix of exactly this class). It is a grid extension, not a new mechanism:

- Add `be_after` at **0.20 / 0.25 / 0.30 / 0.40** to `bear_arm.py`'s
  `DEBIT_GRID`, bear-debit keyed, through the FROZEN harness. Four named
  configs, not a search.
- **Quote both baselines** — `DEBIT_PROD` *and* shipped production (with the
  BEAR_HE trail live). The 08-11 lesson is that the study framing overstated
  production impact 3× because the trail was already buying the same rows; at a
  lower threshold the overlap will be *larger*, not smaller.
  **[WRONG — corrected by the run entry above. The overlap does not grow: a
  ratchet below 0.50 arms on BEAR_HE rows the trail never reaches, so the
  like-for-like swap changes only 13 rows while the gain requires STACKING,
  which is a different rule than the one pre-registered here.]**
- Ship criteria, same as the 08-11 ratchet: pooled date-clustered CI excludes
  zero, ex-Mar–Apr-2025 positive, 2026 alone positive, every LOO-by-date fold
  positive, right-signed in both pricing tiers.
- **Leak guard is mandatory and is the likely killer** — the non-bear debit book
  must be unchanged. A threshold low enough to catch the +25–50% band is low
  enough to start cutting bull_call winners if the keying ever slips.
- Pre-commit: **if no threshold clears, the answer is that bear give-back is
  structural** — the mirrored |MAE|/MFE ≈ 1.25 path signature is what a bad
  selection looks like, and the correct response is the existing hedge-sleeve
  framing (≤ ½ size, `|delta|` descending), not a better stop.

Nothing shipped. `config/backtest.yml` and `deployment-rules.md` unchanged.

---

## 2026-08-12 — the `be_after` grid RUN: does NOT ship, and the give-back pattern is in the UNDERLYING

Study: `scripts/backtest_study/bear_giveback.py` (new, tracked) plus four
pre-registered entries added to `bear_arm.py`'s `DEBIT_GRID`. Reports:
`backtests/study_output/bear_arm-latest.txt`,
`bear_giveback-latest.txt`. Inputs: BacktestResults 1,926 / BacktestProxy 4,533 /
AnalysisClaude 11,836 rows, spy_vix 802 (git 470b95f, tree dirty). Book **795
rows, real 406 / tweak 389**, bs excluded. Bear debit n=332.

**Nothing shipped. No config changed.** The pre-committed null fired.

### 1. Against the STUDY baseline every threshold beats @.50 — and it means nothing

`bear_arm.py` grades against `DEBIT_PROD` (pt .90 / sl .75 / tef .75, no trail):

    variant              meanR    ΔPROD    CI95              LOOmin       $
    PROD                -0.133   +0.000                              -54,404
    BE ratchet @.50     -0.092   +0.041  [+0.016, +0.065]    +0.038   -37,961
    BE ratchet @.40     -0.084   +0.050  [+0.020, +0.079]    +0.046   -34,540
    BE ratchet @.30     -0.066   +0.068  [+0.030, +0.105]    +0.062   -27,494  <- best
    BE ratchet @.25     -0.066   +0.067  [+0.020, +0.112]    +0.061   -27,677
    BE ratchet @.20     -0.072   +0.062  [+0.009, +0.112]    +0.056   -29,317

@.30 clears CI, LOO, both pricing tiers (real +0.083 / tweak +0.052), all three
years positive (+0.133 / +0.065 / +0.036) and ex-Mar–Apr-2025 (+0.058, CI
excludes zero). On the study's own terms it is a better rule than the shipped
one, halving the bleed instead of cutting it 31%.

**It is still not shippable, because production does not run that baseline.**

### 2. Against SHIPPED PRODUCTION it collapses — and the CI includes zero

`bear_giveback.py` ARM P replays the real merge (base → `structure_exit` →
`regime_exit`, i.e. the BEAR_HE 0.50/0.50 trail with `be_after` nulled there).
**Calibration check first: the replay reproduces the shipped book exactly —
mean R −0.093, −$37,951, the same figures the 08-11 close-out measured.**

    variant                            meanR   Δshipped   CI95              LOOmin       $   rows chg
    SHIPPED  be .50, suppressed       -0.093    +0.000                              -37,951       0
    be .40, suppressed                -0.093    +0.001  [-0.010, +0.010]   -0.001   -37,565       6
    be .30, suppressed                -0.085    +0.009  [-0.006, +0.024]   +0.006   -34,535      13
    be .25, suppressed                -0.083    +0.010  [-0.008, +0.029]   +0.007   -34,190      18
    be .20, suppressed                -0.084    +0.009  [-0.014, +0.031]   +0.004   -34,329      22
    be .30, STACKED in BEAR_HE        -0.067    +0.026  [-0.003, +0.056]   +0.020   -27,607      43
    be .25, STACKED in BEAR_HE        -0.067    +0.026  [-0.015, +0.066]   +0.020   -27,930      62
    be .20, STACKED in BEAR_HE        -0.074    +0.019  [-0.030, +0.066]   +0.014   -29,899      82

**Not one variant clears. Every CI includes zero.** The best (be .30 stacked,
+0.026) is 38% of its study-basis delta, and its year split is
**2024 +0.097 / 2025 +0.009 / 2026 +0.007** — one year carries it, the
Mar–Apr-2025 failure pattern for the fourth time in this log.

**Leak guard PASSED** — non-bear debit (n=261) and credit (n=202) both **0 rows
changed**, as the structure keying requires.

**Verdict: the +0.068 was an artifact of grading against a baseline production
does not run.** The 08-11 lesson repeats, and this is now the *second* time it
has changed a decision. Quoting both baselines is not hygiene, it is the test.

### 3. A CORRECTION to the 08-12 proposal entry, and to A3's scope

The proposal above predicted *"the overlap will be larger, not smaller"* at a
lower threshold. **That was wrong, and backwards in an interesting way.**

- The like-for-like swap (threshold down, BEAR_HE **suppression kept**) changes
  only **13 rows** and is worth +0.009. Almost nothing, because outside BEAR_HE
  most bear rows that peak above +0.30 also peak above +0.50.
- The gain only appears when the ratchet is **STACKED** inside BEAR_HE (43 rows
  changed, 30 of them in that cell) — because a ratchet at 0.30 arms on rows
  peaking in [0.30, 0.50) where the trail never arms at all.

So **A3's suppression decision was correct for @.50 and does not generalise**:
@.50 is strictly dominated inside BEAR_HE, @.30 is not. Recorded because the
config comment currently states the domination as if it were a property of the
ratchet rather than of that specific threshold. **The stack is a genuinely
different rule from the one pre-registered**, its CI includes zero, and it is
2024-carried — so it is a CANDIDATE, not a finding, and it is post-hoc.

### 4. ARM U — the give-back IS separable, and the signal is the underlying

301 of 332 bear rows have cached underlying history; 245 ever green. Features
below are observable **in flight**; this is exit management, not selection.

    by DAYS TO PEAK (green rows)      n    give-back   meanR   meanPeak      $
      peak within 3d                 29        90%    -0.549    +0.33   -16,195
      peak 4-8d                      27        81%    -0.401    +0.58   -10,270
      peak 9-20d                     67        42%    +0.254    +1.09   +20,496
      peak >20d                     122        46%    +0.198    +1.10   +25,576

    by UNDERLYING MOVE AT PEAK        n    give-back   meanR   meanPeak      $
      stock -6% or worse            123        36%    +0.387    +1.22   +52,622
      stock -3% to -6%               38        58%    -0.064    +0.75      -953
      stock -1% to -3%               30        77%    -0.211    +0.98    -4,830
      stock flat/up                  54        80%    -0.452    +0.46   -27,232

**Both gradients are monotone.** The headline separation: rows that gave it all
back had the stock down **−4.7%** at their peak; rows that held a gain had it
down **−10.4%**. An early peak on a barely-moved stock is an IV pop, not a
directional move, and it does not survive.

**The confound was controlled, and the effect survives.** "Stock fell more" could
just be "spread is deeper ITM, of course it wins" — so the cut was repeated
inside fixed peak bands:

    [peak +25% to +75%]  n=78     give-back   meanR        $
      stock -6% or worse    28        54%     -0.220    -7,071
      stock -3% to -6%      18        83%     -0.503   -10,103
      stock -1% to -3%      14       100%     -0.692   -10,026
      stock flat/up         18        94%     -0.669   -14,444

At a *held-constant* peak level the gradient is still there, so it is the
underlying and not the moneyness. Two positions both up 50% are not the same
position. The +75–150% band agrees (24% → 75% give-back) on thin cells; above
+150% it flattens, but everything wins there.

**A second, blunter read of that same table: the entire +25–75% peak band is
negative in all four buckets, −$41.6k over 78 rows.** A bear debit whose peak
tops out in that band is a loser regardless of what the stock did. That is not
directly actionable — at +40% you do not know it is the peak — but it is the
cleanest statement yet of *where* the bleed lives.

### 5. What would make this a rule — and why it was NOT built

The candidate is an **underlying-conditioned ratchet**: tighten to breakeven when
green but the stock has not confirmed; leave it alone when the stock has moved
≥6%. It is better-motivated than a flat lower threshold because it targets the
mechanism instead of the symptom.

**It requires a new mechanism in `harness.py`, which is FROZEN**, and the frozen
grid exists precisely so B2 cannot become a parameter hunt. Building it is an
operator decision, not a study decision. If it is taken:

1. Pre-register before implementing: threshold on underlying move, ratchet level,
   and the standing criteria (CI vs **SHIPPED PRODUCTION**, ex-Mar–Apr-2025,
   2026 alone, every LOO fold, both pricing tiers, leak guard).
2. Note in advance that the confound-controlled cells are **n=14–28**. This is
   powered to see a large effect and nothing else.
3. The 2024-carried year split on the stacked variant is a warning that this
   region of the book is where one window can dominate.

Pre-committed reading if it does not clear: **bear give-back is structural** —
the mirrored |MAE|/MFE ≈ 1.25 signature is what a bad selection looks like from
the exit side, and the answer stays the hedge sleeve (≤ ½ size, `|delta|`
descending), not a better stop.

### 6. ARM S — deployment reference stats

Descriptive in-sample summaries added for the operator card; moved to
[`deployment-evidence.md`](../deployment-evidence.md) §"Deployment reference stats".
Profit factor = gross winning $ / |gross losing $| on realized R. Headline: the
ladder is **monotone in profit factor** (A 2.29 / B 1.78 / C 0.79 / VETO 0.34),
and `bull_put_spread` posts **68% win at PF 0.94** — the fat-left-tail problem
in one number, and the reason win rate alone must never be the deploy criterion.

---

## 2026-08-12 — day-0 underlying move: ARM C does NOT clear, no rule ships; the sensitivity is STRUCTURAL

Study: `scripts/backtest_study/next_day_move.py` (new, tracked), on new data
infrastructure (`scripts/collector/fetch_underlying_ohlc.py`,
`scripts/backtest_study/underlying.py`, `tests/test_underlying_ohlc.py`).
Report: `backtests/study_output/next_day_move-latest.txt`. Inputs, quoted from
its header: BacktestResults 1,926 / BacktestProxy 4,533 / AnalysisClaude 11,836
rows (all 2026-08-11), spy_vix 802 (2026-08-12), git 470b95f, tree dirty. Book
**795 rows, real 406 / tweak 389**, bs excluded.

**Nothing shipped. No config changed.** The pre-committed null fired again.

### 0. What this asked, and the pushback it was given first

Operator's question: does the underlying's next-day move, and whether it goes
the play's way, separate structure and profits — reported by market regime,
structure and stock regime, with absolute and percentage moves and OHLC.

Pushback recorded before building, and it shaped the design:

- **The headline is partly tautological.** For a directional spread the
  underlying move IS the P&L driver. ARM C exists to test whether anything
  survives that, and ARM D is explicitly not read until it does.
- **This can never be a selection rule** — the move is unobservable at entry.
  D1 is not re-opened.
- **Absolute $ cannot be a bucket key.** $5 on a $600 stock and on a $20 stock
  are different events. Buckets key on % and on a **sigma-normalised** move
  (move ÷ the one-session move entry IV was pricing); $ is reported only.
- **`harness.py` is FROZEN**, so the rule is applied by COMPOSITION around
  `replay`, never by adding an exit mechanism.

### 1. Pre-registration status — a RECORDED DEVIATION

Every bucket, threshold, population and pass criterion was fixed in the module
header **before the first execution** and is visible there. **This log entry was
not written before the run**, which the standing convention asks for. The
constants are therefore pre-registered in code but not in prose; recorded rather
than glossed, because the whole value of the convention is that it is checkable.
Nothing was added to `RULE_THETAS` or the bucket lists after seeing output.

Two definitional errors WERE found and fixed mid-build, both before any verdict
was read, and both worth recording because they are the kind that silently
produce a clean-looking wrong answer:

1. **`iv_entry_pct` holds a decimal fraction, not IV points** (0.3295 = 33% IV;
   `simulate.py` writes the same sigma it feeds Black-Scholes). Treating it as
   points understated sigma 100x and put 579 of 764 rows in the two outermost
   buckets. Fixed and asserted in `test_sigma_1d_treats_iv_as_a_decimal_fraction`.
2. **The entry session was resolving to market holidays.** `_weekday_grid` is
   weekday-based and option marks carry forward, so Juneteenth 2024, the
   2025-01-09 mourning closure, Presidents' Day 2026 and Good Friday 2026 all
   looked like valid entry days — 23 of 795 rows. The repo has no holiday
   calendar (`trading_days` in scrape_flow is weekdays only), so the scraped bar
   series is now used as the calendar, bounded by `MAX_ENTRY_LAG_DAYS = 5` so a
   HOLE in the bars cannot silently anchor a fill a week late.

### 2. The data that did not exist before

Underlying OHLC was not on disk in any form — the `Open/High/Low` columns in the
option history cache are the OPTION's, and the only underlying series was a
single `Price~` per day read off SHORT legs only (blind to all 22 long-only
rows). `fetch_underlying_ohlc.py` now caches real stock bars per ticker, 104
tickers, ~999 daily bars each covering 2022-08 → present.

**The split gate is the part worth reading.** Barchart serves stock history
currently-adjusted; cached `Price~` was captured unadjusted. 6 of 104 tickers
disagree — and they disagree by *exactly* 2.000 (XLE), 5.000 (CVNA) and 10.000
(AVGO, MSTR, NFLX, SMCI), with AVGO and MSTR stepping 10 → 1 precisely at their
ex-dates. **A constant exact ratio is an adjustment; a wrong symbol could not
produce one.** That distinction is load-bearing: every window this study
measures is a RATIO off ONE series, so a constant factor cancels and those
tickers' percentage moves are perfectly valid. Only absolute dollars and
cross-series comparisons break, so the $ move is withheld on those 51 rows and
nothing else is. The initial design would have quarantined them — wrong, and
would have cost 51 rows for no reason.

Coverage: **787 of 795 rows usable**, 100% on real OHLC, the only exclusions
being the 8 vol structures (straddle/strangle) that have no direction to conform
to.

### 3. ARM D — the descriptive answer, and the finding that is NOT mechanics

Signed to the play, W0 = entry open → entry close:

    W0 (entry session)      n     win    PF    meanR        $     move
      stock CONFIRMED     349     54%   1.31   +0.161   +38,725   +1.79%  +0.66sig
      stock did NOT       415     47%   0.89   -0.046   -20,412   -1.69%  -0.62sig

Monotone in the sigma buckets too (−0.104 / −0.152 / +0.090 / +0.189 / +0.085
across against-1.5σ → confirmed-1.5σ). Taken alone this is exactly the
tautology warned about above.

**What is not tautological is that structures differ enormously in how much they
care**, which pure mechanics cannot explain — if the move were only driving the
mark, every directional structure would respond alike:

    structure            confirmed meanR   did NOT   spread
      bull_call_spread        +0.349        +0.308    0.041   <- nearly indifferent
      bull_put_spread         +0.387        -0.130    0.517   <- swings on it
      bear_put_spread         -0.044        -0.172    0.128
      bear_call_spread        -0.516        -0.608    0.092   (vetoed anyway, n=37)

`bull_call_spread` earns +0.308 mean R and a 60% win rate **on days the stock
went against it**. `bull_put_spread` — the 68%-win / PF-0.94 fat-left-tail
structure from the 08-12 reference stats — is where day-0 non-confirmation
actually costs money. Same pattern in the stock-regime cut: `stock_dir = BEAR`
is indifferent (−0.180 vs −0.213) while `stock_dir = RANGE` swings +0.310 →
−0.163.

### 4. ARM C — the confound control, which does NOT clear

Holding day-0 mark P&L roughly constant and re-running the conformity cut:

    band                       n    confirmed meanR   did NOT   gap
      day-0 P&L <= -25%       93        +0.033        -0.335   +0.368
      day-0 P&L -25% to 0    311        -0.133        -0.109   -0.024
      day-0 P&L 0 to +25%    292        +0.215        +0.019   +0.196
      day-0 P&L > +25%        91        +0.253        +0.824   -0.570

**The sign flips twice.** ARM U's peak-time gradient survived this test inside
fixed peak bands; the day-0 version does not. In the largest band (−25% to 0,
n=311) the readable cells are flat (−0.121 / −0.079 / −0.104), and in the
most-green band the FLAT bucket (+0.714, n=31) beats the confirmed one (+0.206,
n=40). Per the pre-committed reading in the module docstring, that is **no
rule**, and ARM D is not promoted past "description".

### 5. ARM R — the rule, measured anyway, and it misses

Baseline is the SHIPPED merge. It reproduces bear debit at **mean R −0.093 /
−$37,951** — bit-identical to `bear_giveback` ARM P's published calibration, so
the replay is anchored. Credits were routed to `CREDIT_PROD` (pt 0.65, no stop)
after checking `config/backtest.yml`, which states the structure_exit and
regime_exit merges are debit-only: a first cut had them on debit knobs, which
would have been exactly the "baseline production does not run" error this log
has recorded twice.

    bear debit (n=332)                      meanR   Dship   CI95              LOOmin       $   chg
      SHIPPED                              -0.093   +0.000                          -37,951      0
      cut when wrong sign                  -0.031   +0.062  [-0.016, +0.139]  +0.055  -14,910    170
      cut when worse than -0.5 sigma       -0.075   +0.018  [-0.033, +0.068]  +0.010  -32,910     90
      cut inside the flat band (+0.5 sigma) -0.002   +0.091  [-0.002, +0.184]  +0.081   -2,961    234

The flat-band variant nearly erases the bear bleed (−$37.9k → −$3.0k) and passes
criteria 2–6: every LOO fold positive, ex-Mar–Apr-2025 +0.156, ex-Feb–Apr-2026
+0.105, all three years positive, both pricing tiers positive, leak guard 0.

**It fails criterion 1 by 0.002** — the CI lower bound is −0.002. And its year
split is **2024 +0.258 / 2025 +0.029 / 2026 +0.069**: 20% of the rows carry the
majority of the effect, the same one-window signature that has killed candidates
four times in this log. **Whole book and all-debit are negative on every
variant**, so the effect does not generalise past bear either.

Leak guard was made non-vacuous deliberately: the bear-keyed cut is run over the
WHOLE book with the keying evaluated INSIDE the wrapper, not by pre-filtering
the row list — pre-filtering would make it impossible to fail. 0 non-bear rows
changed on all three thresholds.

### 6. A clean null worth keeping: the next-open entry basis costs nothing

WG (signal close → entry open) is not tradeable — it is already inside the fill
— but nobody had priced it. Gaps split 391 the play's way / 396 against, at
+1.36% and −1.22%, for an **overall mean of +0.06% (−0.01 sigma)**. Outcomes
barely separate (+0.056 vs +0.004 mean R). The `entry_timing: next_open` basis
adopted on 2026-07-06 is not systematically feeding the book a worse price.

### 7. Actions

- **No rule change**, no config touched. ARM C failing is the gate working.
- **The flat-band bear cut is a CANDIDATE, not a finding** — post-hoc favoured,
  CI includes zero, 2024-carried. Re-evaluate only on new bear rows, and only
  against SHIPPED production.
- **New watch: `bull_put_spread` day-0 sensitivity.** The 0.517 spread is the
  largest structure effect in the table and lands on the structure already known
  to carry a fat left tail. It is exit-side and unproven; it is NOT a licence to
  re-open selection.
- **`bull_call_spread` earning +0.308 on non-confirming days** is worth
  remembering the next time a directional read is used to justify holding or
  cutting one — that structure's P&L is not primarily riding day-0 direction.
- **Infrastructure is reusable:** `underlying.py` gives any future study real
  OHLC with a documented fallback, and recovers the long-only rows
  `harness.Trade._load_underlying` cannot see. `harness.py` was NOT touched.

---

