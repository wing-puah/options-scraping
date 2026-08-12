# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index.

**State of play (2026-08-12, late).** Operator asked whether the engine has any
measurable edge at all, or whether selection needs more tuning. **Verdict: the
edge is real, narrow, and not selection-tunable** — see the edge-status entry
below. The same conversation reopened ONE bounded exit question: bear MFE
give-back below the `be_after: 0.50` arming threshold, quantified below as
**−$77.2k across 124 rows the shipped ratchet cannot reach**. That is a
pre-registerable grid extension, not a re-opening of selection. Prior state
follows.

**State of play (2026-08-12).** The deployment rules are now split in two:
[`config/deployment-rules.md`](../deployment-rules.md) is an instructions-only
operator card, and [`deployment-evidence.md`](deployment-evidence.md) holds the
derivation, the caveats and the **open rollback triggers** that used to be
interleaved with them. Entry below. Prior state follows.

**State of play (2026-08-11, CLOSE-OUT).** **v3 is closed and shipped.** Backtest
tuning stops here: the ML search was a null result across all 15 cells and its
ablations put the ceiling in the columns, not the estimator, so no further run on
this book can answer anything. Three things shipped — the `be_after: 0.50` bear-debit
ratchet (suppressed inside BEAR_HE, where the trail dominates it), the bear
hedge-sleeve rules (`|delta|` descending, ≤ ½ size), and the live-loop
`SUBSTITUTED` fix. **The shipped ratchet is worth +0.015 mean R, not the study's
+0.041** — production already carried the BEAR_HE trail, which was buying the same
rows. The evidence source now moves from the backtest to live fills. v4 (prompt
trimmed of `score_flow`/`score_dealer`) starts on fresh tabs with a
pre-registered composition bridge before its rows are read against v3-derived
rules. Details in the close-out entry below. Prior state follows.

**State of play (2026-08-11, late).** The ML combination search has RUN and is a
NULL RESULT (no model beats the ladder in any of 15 model×strategy cells); the
bear arm run alongside it found that bear structures are an EXIT problem after
all — `be_after: 0.50` keyed to bear debit spreads clears every pre-registered
criterion including the 2026 window on its own, which is the "second sustained
bear drawdown" addendum 12 said would settle it. Recommended, not shipped —
awaiting the operator. Bear SELECTION remains unfixable from these columns
(0 of 496 conditioned subsets survive). Details in the entry below.

**Earlier that day.** The Feb–Apr 2026 holdout backfill is COMPLETE
(33 window dates priced, incl. the 7 late dates and 02-17/02-19) and the
completed-book analysis (below) has all three pre-registered bear_put DEMOTE
criteria firing at n=164 with the real-tier discordance resolved downward —
the demotion is decision-eligible; implementation choice (intake veto vs
ladder VETO vs Tier-C-never-deploy) is the user's. Shipped config is the
source of truth — `config/backtest.yml` (exits, `regime_exit.cells: BEAR_HE`
only) and `config/deployment-rules.md` (VETO / A / B / C ladder, top-3 per
day, bull_put band `0.08 ≤ |delta| ≤ 0.20` + `DTE ≤ 59`). Open questions:
(1) **bear_put implementation** — verdict reached, mechanism not chosen;
(2) **the long-dated blind spot** — h≥180 still unpriceable with real data,
and the bs tier — measured as attenuating (tail-compressed marks shrink every
effect toward zero) AND selection-contaminating (64 rows inside the top-3/day
replay) — is now OFF (`proxy.bs_fallback: false`); evaluate real+tweak only,
and filter the 301 legacy bs rows out by `proxy_method` at read time;
(3) **live substitution** — the
operator sometimes trades naked where the engine emitted a spread, which
breaks the live walk-forward's attribution. Next study queued: the ML
combination search — plan pre-written in [`ml-plan.md`](ml-plan.md), NOT run.

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

## 2026-08-12 — live loop promoted to tracked code, and its fill mapper put under test

The close-out entry left this open as a known gap: **`backtests/live_loop/` is
UNTRACKED.** `.gitignore` excludes `backtests/*` and its own comment calls that
tree disposable scratch that "gets deleted periodically" — yet
`stage1_map_fills.py` was 33KB of real code and, with backtest tuning closed, the
**only source of new evidence in the system.** Exactly the mistake the 08-11
refactor fixed for study code by moving it to `scripts/backtest_study/`.

Moved to **`scripts/live_loop/stage1_map_fills.py`**; runs as
`python3 -m scripts.live_loop.stage1_map_fills`. `ROOT = parents[2]` still
resolves to the repo root at the new depth (the stale-ROOT bug that broke 7
studies in the 08-11 move does not recur here — checked, not assumed). Data stays
under `backtests/live_loop/`, which is the correct split: tracked code, disposable
data. Output reproduces exactly — **EXACT 0 / STRUCTURE 2 / SUBSTITUTED 1 /
NONE 15**.

**`tests/test_live_loop.py` — 38 tests**, with the IBKR snapshot copied to
`tests/fixtures/` so it survives a `backtests/` wipe. The 08-11 mis-labelling bug
(`long_call` and `bull_call_spread` both mapping to `debit`, so naked fills were
tallied as STRUCTURE matches) was found **by reading, not by a test**, and its
failure mode is silent — a mislabelled fill does not raise, it quietly corrupts
the evidence base. Now pinned: the `DIRECTION` gate, the
`EXACT ≺ STRUCTURE ≺ SUBSTITUTED` ranking (both row orders), and the ladder port.

**Writing the tests surfaced a seam worth recording.** `classify_structure()`
emits `"single long call"` (spaces) for naked legs but `"bull_call_spread"`
(underscores) for verticals, and `_live_to_canonical()` matches on the spaced
form. Any label that canonicalises to `"unknown"` matches no play and drops to
**NONE — indistinguishable from "no play that day"**, which is precisely the
silent-drop failure the 07-27 entry described and the 08-11 entry corrected for a
different branch. The vocabulary is now pinned by a parametrised test rather than
trusted, including that genuinely unpinnable round-trip closes stay `"unknown"`
instead of guessing.

Still open from the close-out list: `scripts/chart_backtest.py:55-76` re-derives
exit config and knows about neither `regime_exit` nor `structure_exit`.

---

## 2026-08-12 — v4 bridge: RECORDED DEVIATION from the pre-registration (written BEFORE the run)

Amends the [pre-registration below](#2026-08-11--v4-emission-composition-bridge-pre-registration-written-before-the-run).
**Nothing has been run.** Written now, while no v4 result exists, because a
deviation decided after seeing numbers is not a deviation, it is a choice.

**What changes: the ~20 re-runs are dropped.** The pre-registration called for
running the v4 prompt over ~20 dates already covered by v3, writing to a scratch
tab. Those are ~20 headless analysis calls, and analysis is the expensive step in
this system. They are also avoidable.

Measured state of the v4 tabs today: **`AnalysisClaude` = 10 rows on one date
(2026-08-11); `AnalysisGPT` = 0.** v4 accrues ~10 rows/day from the normal daily
cadence at no marginal cost, so **~20 dates arrives in roughly four weeks of
changing nothing.**

Checked first, for the record: nothing cached would let a v4 row be reconstructed
for an old date. The pipeline persists the deterministic rollup
(`audit/<date>-rollup.csv`) but sends LLM output straight to Sheets, so a v4 row
on a v3 date genuinely costs a fresh run. There is no copy-paste shortcut.

**What this costs, stated in advance.** Accumulated v4 dates will not overlap v3
dates, so the five tests lose their **date pairing**. Substitute: match on
**`mech_cell`**, a `ROW_COLUMNS` field backfilled across both eras, which encodes
the tape conditions date-pairing was buying.

**Pre-committed caveat, stronger than the original's.** mech_cell matching is
coarser than date matching — it controls for regime, not for the specific day's
flow. Combined with the original's own admission that ~20 dates is thin for a
five-way composition test, this is powered to catch a shift the size of the
v2→v3 credit jump (19% → 34%) and **nothing subtler**. A null result here means
"no large shift detected", never "the populations are the same". Do not let a
null be quoted later as validation.

**Unchanged, and not renegotiable after the numbers land:** the five tests
(structure mix, credit share, plays/day, bear share, ladder tier mix) and the
decision rule — within noise → the v3-derived ladder carries forward; any of the
five shifts → the ladder is UNVALIDATED on v4, keep deploying under v3 rules and
flag every v4 row here.

**Escape hatch, bounded.** If four weeks of tape produces no BEAR or H/E-VOL
date, re-run **≤5** v3-covered dates chosen to fill that specific empty cell —
targeted, and only on evidence the cell is missing. Running `--engine codex`
daily would also double the accrual rate but samples a different engine
population; noted, not recommended.

Interim posture is already what the pre-registration says: deploy under v3 rules.
This is now stated on the operator card itself rather than only here.

**The study is written and gated: `scripts/backtest_study/v4_bridge.py`.** Written
today, while v4 had 10 rows on one date — so nothing in it can have been tuned to
a result. It refuses to produce numbers until the gate is met:

- `MIN_V4_DATES = 20` → exits **rc=2** with the shortfall and the interim posture.
- **Era guard** → exits **rc=3** if the two exports are not v3-then-v4. Era is
  detected from the *schema* (`score_flow`/`score_dealer` present = v3), never
  the filename, because the in-place `vN_` rename leaves both eras exporting as
  "AnalysisClaude" and they are trivially swapped. Run today it correctly aborts
  with *"refusing to compare a book against itself and call the null a
  validation"*.
- v3 is **reweighted to v4's mech_cell mix** (direct standardisation), so a
  difference in regime composition cannot masquerade as a difference in
  behaviour — the specific hazard the date-pairing deviation introduces.

`tests/test_v4_bridge.py` (16 tests) proves the machinery before it ever runs on
real data: both gates fire, `MIN_V4_DATES`/`ALPHA` are pinned at their
pre-registered values, **a v2→v3-sized credit jump (20% → 35%) is detected**, and
standardisation collapses a deliberately confounded 90%-LVOL-vs-50/50 pair to
identical shares while the raw shares differ by >10pts. A study that cannot see
the shift it was built for is not worth waiting a month for.

One divergence from `book.ladder_tier()`, documented in the module: |delta| and
DTE are not columns on an analysis row, so the Tier-B bull_put geometry clause
cannot be evaluated and every bull_put falls to C. That biases the tier mix
**identically in both eras**, which is all a composition comparison needs — but
these tier shares must never be quoted as deployment shares.

---

## 2026-08-12 — deployment rules split: operator card vs evidence

`config/deployment-rules.md` had grown to 284 lines by accretion — every study
that shipped a rule appended its derivation, CIs, LOO folds, limits and rollback
trigger to the same file, so the ~15 things an operator actually does at deploy
time were interleaved with ~200 lines of research record. With v3 tuning closed,
the rules have stopped churning and the doc is stable enough to freeze.

- **`config/deployment-rules.md`** → instructions only, ~110 lines, as a
  deploy-day sequence: before-you-deploy → VETO → tier → order-entry geometry →
  hedge sleeve → exits → what not to use.
- **`config/backtest-tuning/deployment-evidence.md`** (new) → everything else,
  moved with the numbers intact. Nothing was dropped; the diff is a move.

**Three defects fixed in passing, all found by reading the doc against the code:**

1. **Stale command.** The card told the operator to run
   `python3 backtests/mech_regime/fetch_spy_vix.py --full`. That path is
   untracked scratch — the tracked fetcher has been
   `scripts/collector/fetch_mech_regime.py` since the mech-regime move, and
   `make analyze` already depends on the `mech-regime` target. Now just
   `make analyze`.
2. **Hand-computed regime label.** The card still spelled out "SPY < 50-day SMA
   and 20-day return < 0" as an operator step. `mech_cell` has been a
   `ROW_COLUMNS` field and backfilled across the analysis tabs since the 08-11
   addendum — the card now says *read the column*, and the definition moves to
   the evidence file as reference. This was a live opportunity to mislabel a
   date by hand.
3. **Exit rules split across three sections.** "Preconditions", "Exit
   management" and "Bear debit spreads — breakeven ratchet" each held part of
   the exit config, so setting up an order meant reading all three and
   reconciling the BEAR_HE suppression clause yourself. Now one four-row table
   (debit normal / debit BEAR_HE / bear debit / credit) with the suppression as
   an explicit footnote.

The `## Exit management` heading is **preserved verbatim** — six places link to
`deployment-rules.md §"Exit management"` (`config/backtest-reference.md`,
`scripts/backfill_mech_cell.py`, `scripts/collector/fetch_mech_regime.py`,
`scripts/analysis_pipeline/config.py`, `scripts/analysis_pipeline/core.py`,
`.github/workflows/backfill-mech-cell.yml`), and keeping the heading is cheaper
than updating six references.

**The three open rollback triggers are now in one table** in the evidence file
rather than scattered across three sections — BEAR_HE trail (≥25 new affected
dates), bear-debit `be_after` (≥60 new rows that arm it), bull_put band
(PROVISIONAL). They are live pre-registered commitments and were the easiest
thing in the old doc to lose. **Silence is not "not met" — check the numbers.**

No rule changed. No config changed. This is a documentation move.

---

## 2026-08-11 — v3 CLOSE-OUT: three findings SHIPPED, and the production delta is a third of the study's

v3 is closed. The trigger was not fatigue — it is that **no question left in the
queue is answerable from this book**. The ML combination search returned a null
result in all 15 model×strategy cells and its ablations put the binding
constraint in the *columns*, not the estimator; the Feb–Apr 2026 holdout is
complete; the ladder is monotone in every cut. What remained was shipping.

### 1. SHIPPED — `be_after: 0.50`, bear debit only (`simulation.structure_exit`)

Implemented in `scripts/backtest/simulate.py`: a `be_stop` branch in
`_summarize_path` between `dollar_stop` and `stop_loss` (ported from the frozen
harness ordering), plus `_structure_override()` keyed on
`bear_put_spread`/`long_put` with `entry_net >= 0`. Merge order for debits is
**base → structure → regime**.

**A3 — the pre-registered interaction check, and a recorded deviation from the
frozen grid.** One entry was added to `bear_arm.py`'s `DEBIT_GRID`:
`"BE @.50 + trail .50 trig .50"`. One named config, not a search.

    trail .50 trig .50            -0.098  +0.036  [+0.006,+0.063]  LOO +0.032
    BE ratchet @.50               -0.092  +0.041  [+0.016,+0.065]  LOO +0.038
    BE @.50 + trail .50 trig .50  -0.098  +0.036  [+0.006,+0.063]  LOO +0.032

The stacked cell is **bit-identical to the trail alone, with zero `be_stop`
exits**, and below BE alone. The cause is structural, not sampling: the trail
arms at peak ≥ 0.50 and its floor (peak − 0.50) is then ≥ 0 — at or above the
ratchet's threshold — and the trail is checked first. The ratchet is strictly
dominated inside BEAR_HE. Decision rule fires **SUPPRESS**, implemented as
`be_after: null` on the `BEAR_HE` cell (which is why regime merges last).
Confirmed in production: suppress vs stack over the 224 BEAR_HE bear-debit rows
differ on **0 rows**.

**The production delta is NOT the study delta — record this, it will recur.**
The study measured against `DEBIT_PROD` (pt .90 / sl .75 / tef .75, **no
trail**). Production has shipped the BEAR_HE trail since 07-22, so the study's
baseline is not production's:

    bear debit (n=332)          mean R              total $            rows changed
    study framing            -0.133 → -0.092                              —
    production, measured     -0.109 → -0.093    -43,806 → -37,951         16
      on BEAR_HE (suppressed) -0.152 → -0.152    unchanged                 0
      elsewhere (n=108)       -0.019 → +0.028     -4,916 → +939           16

So the shipped rule is worth **+0.015 mean R / +$5.9k**, not +0.041 / +$16.4k,
and `be_stop` fires on **16 rows, not ~44**. The two rules were largely buying
the same rows and the trail got there first on 224 of 332. The generalisable
lesson: **a study delta measured against `DEBIT_PROD` overstates production
impact wherever a regime cell already ships a rule that converts the same
rows.** Every future exit study should quote both baselines.

`stop_loss` 92 reproduces exactly; the *baseline* is 100, not the study's 110,
for the same reason.

**Leak guard — PASSED.** Non-bear debits (n=261): 0 rows changed, mean R and
dollars identical. Credits (n=202): 0 rows changed. The narrowness is the
finding (+0.234 → +0.209 on non-bear debits), and it is now enforced by tests.

### 2. SHIPPED — bear hedge sleeve (`deployment-rules.md`)

D2/D4/D3 written up as an operator section: bear is a **hedge, not a
selection**; rank the day's candidates by `|delta|` DESCENDING; size at ≤ ½.
Limits travel with the rule (D3 formally NOT MET by $86, worst-decile CI
includes zero, naked puts unrepresented, D5 does not reproduce). The bear_put
**DEMOTION thread (open since 07-22) is CLOSED without a demotion mechanism** —
bear rows are already C/VETO and never enter the deployed top-3, so the answer
was an exit profile, not an intake veto.

### 3. SHIPPED — live-loop `SUBSTITUTED`, and a CORRECTION to the 07-27 entry

The 07-27 §4 entry states that a naked leg filled against a spread play "falls
to **NONE**, indistinguishable from 'no play that day'", i.e. silently dropped.
**That is wrong, and the truth is worse.** `SIDE` maps `long_call` and
`bull_call_spread` both to `debit`, so the family branch labelled such fills
**STRUCTURE** — pooled into the eval as if the emitted play had been traded.
A second defect: that branch matched on credit/debit only, so a `long_put` fill
against a `bull_call_spread` play (opposite directions, both debit) was also
labelled STRUCTURE.

Fixed in `stage1_map_fills.py`: a `DIRECTION` map now gates the family branch,
substitutions get their own `SUBSTITUTED` confidence, and candidate selection is
rank-based (EXACT ≺ STRUCTURE ≺ SUBSTITUTED) so a true match always outranks a
substitution. Tally on the checked-in snapshot moves **0/3/15 → EXACT 0 /
STRUCTURE 2 / SUBSTITUTED 1 / NONE 15**; the reclassified row is the META
short-put-vs-`bull_put_spread` entry the report's own prose had already flagged
as weak while the tally counted it as a match.

### 4. SHIPPED — the v4 prompt trim (`score_flow` / `score_dealer` dropped)

`score_vol` stays (exempt); `score_price`/`score_catalyst` were always
pipeline-computed. `ROW_COLUMNS` goes 27 → 25 and the columns are dropped from
the schema outright rather than blanked, because v4 writes fresh tabs.
`RESULT_COLUMNS` KEEPS them so the results schema stays stable across eras and
the four study loaders that name them keep working on pooled exports. Reader
audit found no `KeyError` risk — every analysis-row consumer uses
`.get(col, "")`.

**The queued trigger did NOT fire.** The 07-21 queue said "drop if still null
after the 25-date backfill". They are not null — 366 of the last 400 rows carry
both. The justification is instead the 08-11 ML ablations (nothing beyond
structure × regime × geometry is reproducible) and the framework's own admission
that `score_dealer` was judged off a vol-snapshot proxy, never real dealer data.
Recording this because the trim now rests on a *different* argument than the one
that queued it.

**Correction to the plan: the new scale is 0–50 for DIRECTIONAL/HEDGE/SYNTHETIC
but 0–55 for VOLATILITY.** VOLATILITY's dropped `flow` max was 20, not 25, so
its survivors are 10 + 25 + 20 = 55. Documented as such everywhere rather than
rounding the claim down; flattening it to 50 would be a rubric change, not a doc
change. Either way v4's `score_total` is NOT comparable to v3's 0–100 and must
never be ranked across the two eras — it survives only as a deterministic
tie-break within a tier.

**A live prompt bug found and fixed in passing.** The contract told the model
"NEVER emit a bear call spread" and then, ~45 lines later, instructed it to use
one for the bearish high-IVpct TF-S case; `claude.md` and `codex.md` carried the
same contradiction. Only the framework's Step-4 table was correct. This could
emit the single most toxic structure in the book (−0.82 mean, 17% win,
intake-vetoed since Attempt 13) — the backtest would have refused it at intake,
so the cost was wasted plays rather than bad fills, but it was live. All three
now route bearish TF-S to a bear put debit spread or a pass. Folded into this
version bump because it is a prompt change and needed one.

Also fixed: the guardrails told the model to "zero the price and catalyst
components" to hold a total down — impossible since both became
pipeline-computed. It now withholds `vol`, the only lever it still has.

### 5. The cut-over mechanics — in-place `vN_` renaming, NOT a new spreadsheet

Worth recording because the close-out plan assumed a new spreadsheet and a
`GOOGLE_SPREADSHEET_ID` change, and that is **not** what this repo does. The
sheet already carries `v1_AnalysisClaude_20260625`, `v2_AnalysisClaude`,
`v3_AnalysisClaude` — the established convention is to rename the live tabs with
a `vN_` prefix in place and let the pipeline recreate fresh ones. The v3 rename
is done (`v3_AnalysisClaude` 1,608 rows / 27 cols, `v3_BacktestResults`,
`v3_BacktestProxy`), and an empty `AnalysisClaude` is waiting with 0 columns, so
the first v4 append writes a clean 25-column header.

Two consequences, both good, that the plan got wrong in the cautious direction:

- **`BaselineDaily` is untouched** (214 rows, continuous). The plan's warning
  that v4 would start with no regime-baseline history — the one real risk it
  flagged — is moot under in-place renaming. No `build_baseline --backfill`
  needed.
- **No env change, and no code change.** `config/backtest.yml`'s
  `analysis.tab: AnalysisClaude` and `output.sheet_tab: BacktestResults` already
  point at the v4 tabs by virtue of the rename.

The live cost is that `python -m scripts.backtest` now reads 0 rows until v4
accumulates; v3 work must pass `--tab v3_AnalysisClaude`. Study code is
unaffected — it reads CSV exports by filename, not tabs.

### 6. Tests

`tests/test_mech_regime.py` gains the structure-override suite (bear debit gets
the ratchet, non-bear debit and credits never do, BEAR_HE suppression, merge
order, disabled/default no-ops). `tests/test_backtest.py` gains five ladder
tests pinning `be_stop` between `dollar_stop` and `stop_loss` — the position is
load-bearing and was previously unguarded.

### 7. `exit_basis` widened — `BEAR_DEBIT` (fixed in the same change)

Shipping the ratchet initially broke the column's guarantee: a bear debit that
ran `be_after` reported `PROD`, so `exit_basis == "PROD"` stopped meaning "base
config only" — the exact ambiguity the column was added to prevent. The
vocabulary is now `{PROD, CREDIT, BEAR_DEBIT, <regime cell>}`, reported in
merge-precedence order: a regime cell outranks `BEAR_DEBIT` because regime
merges last and, on BEAR_HE, genuinely governs (it nulls `be_after`). Pinned by
tests that assert the label never claims a profile the merge did not apply.

### 8. Known gaps left open, deliberately

- **`scripts/chart_backtest.py:55-76`** re-derives exit config for chart
  reference lines and knows about neither `regime_exit` nor `structure_exit`;
  bear-debit charts draw a −75% stop line for positions that exited at
  breakeven. Pre-existing, now one rule wider.
- **`backtests/live_loop/` is UNTRACKED.** `.gitignore` excludes `backtests/*`
  and its own comment calls that directory disposable scratch that "gets deleted
  periodically" — yet `stage1_map_fills.py` is 30KB of real code and is now the
  only source of new evidence. This is the same mistake the 08-11 refactor fixed
  for study code by moving it to `scripts/backtest_study/`; the live loop was
  missed.

---

## 2026-08-11 — v4 emission-composition bridge: PRE-REGISTRATION (written BEFORE the run)

**Status: pre-registered, NOT run.** Everything below is fixed in advance. If
the numbers land differently from what the operator hopes, the decision rule
stands as written — that is the entire purpose of writing it first.

**What is changing.** v3 is being closed out (see the close-out entry above once
written) and the analysis prompt is being trimmed: `score_flow` and
`score_dealer` come out of the per-play `score` object; `score_vol` stays. v4
runs on a NEW spreadsheet, so the tabs are fresh and the schema drops both
columns rather than blanking them.

**Why a bridge test is needed at all.** The columns themselves are established
as decision-irrelevant — the 07-21 sweep found only `delta`/`dte` (bull_put) and
`iv_spread` (bear_put) decision-relevant, and the 08-11 ML ablations found
nothing beyond structure × regime × geometry adds anything reproducible. That is
NOT the risk here. The risk is **behavioral**: removing two of five Step-5
factors may change *what plays the model emits*. The only statistically
significant v2→v3 difference in this entire log was exactly that — credit
emission 19% → 34% — and it was not predicted in advance either.

If the emission profile shifts, every rule in `config/deployment-rules.md` was
derived on a population v4 no longer draws from, and the ladder's validation
does not transfer. That is worth ~20 headless runs to find out.

**Test.** Run the v4 prompt over ~20 dates already covered by v3, writing to a
scratch tab. Compare against the v3 rows on the same dates (exported from the
old sheet before the switch). Date-paired, two-proportion tests on:

1. structure mix (bull_call / bull_put / bear_put / other)
2. credit share of emitted plays
3. plays per day
4. bear share
5. ladder tier mix (A / B / C / VETO)

**Decision rule, fixed now:**

- **Composition within noise** → the v3-derived ladder CARRIES FORWARD to v4
  rows. Record it and deploy unchanged.
- **Composition shifts on any of the five** → the ladder is UNVALIDATED on v4.
  Keep deploying under the v3 rules, flag every v4 row as such here, and let the
  live eval arbitrate. Do NOT quietly assume the tiers transfer, and do not
  re-derive the ladder on v4 rows until there are enough of them to mean
  anything.

**Pre-committed caveat.** ~20 dates is thin for a five-way composition test;
this is powered to catch a shift the size of the v2→v3 credit jump, not a subtle
one. A null result here is "no large shift detected", never "the populations are
the same".

---

## 2026-08-11 — DEPLOY arm: the hedge caveat was TESTABLE, and bear deployment has a rule

The 08-11 bear arm closed by calling the chop hedge "a *portfolio* decision the
book cannot price". **That was too strong** — 84 of the bear dates also carry a
deployed ladder sleeve, so the concurrent book exists and the portfolio question
is answerable on it. The operator's instruction (bear positions stay deployable)
made the gap worth closing. Pre-registered as
[`ml-plan.md` §addendum 2](ml-plan.md) BEFORE running; code
`scripts/backtest_study/bear_deploy.py`, output `backtests/study_output/bear_deploy.txt`.
Same 795-row book, same protocol, no new columns.

**What B1/B2 had actually left open.** Three distinct estimands, not a second
bite at the same one: B1 asked an *absolute level* question and B2 an *exit*
question, and neither asked (a) the two jointly, (b) what bear does to a
concurrent long book, or (c) *which* bear to take on a day one is taken anyway.

### 1. D1 — joint selection × exit: NOT MET (B1's verdict survives)

B1 screened E under the PROD exit; B2 then changed the exit; the pair had never
been run together. Re-screening the identical 496-subset vocabulary on R under
`be_after: 0.50`: **0 survivors, ~10 expected by chance.** Pooled bear
E −0.601 / R(PROD) −0.168 / R(bear exit) −0.203. The best subset is
`mech LVOL AND dte 31-59` at R +0.287, CI [−0.034, +0.593] — still includes
zero at n=49. **Bear selection remains unfixable; the new exit does not rescue
it.** Worth noting the exit lowers pooled R slightly (−0.168 → −0.203) across
ALL bear rows including credit — B2's +0.041 gain was measured on bear *debit*
rows only, and that scoping is load-bearing.

### 2. D2 — the hedge is REAL (all three pre-registered criteria fire)

Deployed sleeve = shipped ladder (top-3/day, tiers A/B, 220 rows / 90 dates).
Bear sleeve = that date's bear candidates. 84 overlapping dates.

    deployed-book bucket   dates   deployed R    bear R     bear $   bear win%
    worst decile               8       -0.795    +0.252     +6,669      75.0%
    worst quartile            21       -0.457    +0.184    +16,824      66.7%
    negative dates            25       -0.390    +0.109    +16,985      60.0%
    positive dates            59       +0.706    -0.281    -41,895      32.2%
    ALL                       84       +0.380    -0.165    -24,910      40.5%

Sleeve correlation −0.132; tail positive in 2 of 3 evaluable years
(2024 +0.129 / 2025 −0.048 / 2026 +0.405). **HEDGE IS REAL: MET.** The shape is
textbook insurance: it pays where the book bleeds and bleeds where the book
pays. Honest limits — the worst-decile row-level CI is [−0.113, +0.639] (n=28,
includes zero), 2025's tail is mildly negative, and D2 approximates a hedge as
equal-weighted concurrent dollars, which is a *proxy* for, not a measurement of,
a held hedge.

This is the first evidence in the log that supports carrying bear risk at all,
and it exists only because the question was asked at the book level. Every prior
bear verdict measured the standalone play and was correct to be negative.

### 3. D4 — the operator's real question, and the one actionable rule

Not "is bear good" but **"given I take a bear position today, which one?"** —
a *within-date paired* test on 93 dates with ≥2 bear candidates (3.8/day). The
day is its own control, so the −0.5 level that sinks every B1/D1 subset cancels.
This test had never been run, on any structure.

    ranker                    dates    pick R   day avg      gain   CI95              LOO min
    |delta| HIGH first           93    +0.051    -0.181    +0.232  [+0.091,+0.370]     +0.204  **
    iv_spread low first          92    -0.094    -0.180    +0.086  [-0.056,+0.236]     +0.065
    dte short first              93    -0.176    -0.181    +0.004  [-0.203,+0.185]     -0.015
    |delta| low first            93    -0.393    -0.181    -0.212  [-0.370,-0.062]     -0.233
    score_total high first       93    -0.436    -0.181    -0.255  [-0.417,-0.098]     -0.276
    widest max_loss first        93    -0.526    -0.181    -0.345  [-0.580,-0.147]     -0.368

**`|delta| high first` is ADOPTED** — 1 survivor of 10 tested (~0.5 expected),
CI excludes zero, every LOO fold positive, positive in all three years
(+0.285 / +0.312 / +0.083). It is **not exit-dependent**: on R under the
SHIPPED PROD exit it still holds (+0.159, CI [+0.028, +0.280], LOO +0.144, all
three years positive). On E alone it fails (+0.059, CI includes zero) — so this
is a *realized-return* effect, partly exit-mediated, and must be quoted that way.

Read: **the losing bear trade is the cheap far-OTM one.** Buying the
closer-to-money bear spread turns a −0.181 average day into +0.051. Two
corroborations from elsewhere in the log: D1's best subsets pair `LVOL` with
`|delta|>0.20`, and `score_total high first` anti-selecting (−0.255) is the
07-21 "score is decision-irrelevant / pre-13c scores anti-select" finding
reappearing inside a structure.

### 4. D3 — always-on sizing: NOT MET, but by $86

**Deviation, recorded:** the pre-registration fixed the sizing rule but not
which bear is taken daily. The first cut used the day's widest `max_loss` —
which D4 then measured as the single *worst* available pick. Both are reported.

    sleeve = 1/day by |delta| high (D4-adopted)
        f      total $    max DD $   worst date $
     0.00       63,553      -7,609         -3,212
     0.25       64,268      -7,255         -3,255
     0.50       64,982      -7,037         -3,298
     1.00       66,412      -7,780         -3,501

    sleeve = 1/day by widest max_loss (lower bound on a bad pick)
     0.50       42,167     -11,291         -3,877
     1.00       20,780     -18,127         -4,542

At f = 0.50 with the right pick, **max drawdown IMPROVES** (−7,609 → −7,037) and
total rises +$1,430. The pre-registered rule still returns NOT MET because
worst-date slips $86 on a $63.5k book — the rule's worst-date clause is doing
all the work at a magnitude that is noise. Reported as NOT MET per the letter of
the pre-registration; read as *the sleeve is roughly free at half size, and
expensive at full size or with a bad pick.* The picker matters more than the
size: same sleeve, same days, −$42.8k swing between the two.

### 5. D5 — timing the hedge: POST-HOC, and it does NOT reproduce

D2+D3 jointly imply a gate (pays in the tail, bleeds in the body). Seven
deploy-time gates tested; `mech H-VOL` and `mech BEAR_HE` leave drawdown and
worst-date unharmed while adding $2–3k. **But the year check kills it:** the
leading gate is 2024 −$2,655 / 2025 +$5,179 / 2026 +$813 — one year carries it,
which is the Mar–Apr-2025 failure mode for the third time in this log.
**Candidate only, not a finding, chosen after seeing D2.**

### 6. What this changes

- **Bear positions are deployable — as a hedge, not as a selection.** D1
  reconfirms there is no bear edge standalone. D2 shows the sleeve pays in the
  deployed book's tail. These are consistent, not contradictory, and the
  distinction is the whole answer.
- **Recommended (NOT shipped — operator decision):** add to
  `deployment-rules.md` — *when you take a bear position, take the
  closer-to-money one; rank the day's bear candidates by |delta| descending.
  Size the sleeve at ≤ ½ a normal position and treat it as insurance, not as a
  play.* This is the first bear rule in the log that reproduces in all three
  years on the SHIPPED exit.
- **The `bear_arm.py` caveat is amended:** "the book cannot price a hedge" is
  retired and replaced with the measured version — it *can* price a
  concurrent-dollar proxy for one, and did.
- **Still unanswered, and honestly so:** 88% of bear rows are `bear_put_spread`
  and only 6 are naked `long_put`, so none of this speaks to the naked-put
  hedge the operator sometimes substitutes (see the SUBSTITUTED item in the
  live walk-forward). Margin, assignment and real position sizing remain
  outside the book. D5's gate needs an independent window.
- Unchanged: no production config, prompt or ladder was modified by this run.

---

## 2026-08-11 — ML combination search RUN: NULL RESULT; and the bear arm finds an EXIT fix, not a selection one

Both arms of [`ml-plan.md`](ml-plan.md) executed against the same 08-11 exports.
Code is now TRACKED under `scripts/backtest_study/` (`book.py` loader, `harness.py`
replay port, `protocol.py` validation, `ml_combination.py`, `bear_arm.py`);
outputs in `backtests/study_output/`. Book: **795 priced rows,
118 dates, real 406 / tweak 389** (bs excluded per the 08-11 decision; the
loader's exact-replay gate drops 48 non-reproducing proxy debit rows and 3 real
dups, which is why 795 and not the 08-11 scratch cut's 817).

Deviations from the plan, both recorded before the run: GBM is sklearn
HistGradientBoosting rather than LightGBM (same family, no libomp), and a
third replay variant (**abstain** — the model may sit out a day) was added so
the ladder's right to trade nothing is not an unfair advantage.

### 1. ML arm — nothing beats the ladder, in any form

Purged expanding walk-forward, 10-date blocks, 120-day embargo → 58 of 118
dates ever tested (the embargo is expensive at this sample size). Every model
ranked against the ladder on the SAME dates, paired at date level.

    model            forced        abstain       tie-break in A/B
    B1 logistic      -0.173        -0.073        -0.074
    B2 elastic net   -0.180 *      -0.095        -0.062
    M1 GBM (E)       -0.096        -0.057        -0.006
    M2 GBM (E>0)     -0.113        -0.097        +0.022  CI[-0.017,+0.071]
    M3 depth-3 tree  -0.155 *      -0.102        -0.027
    (* CI excludes zero — i.e. significantly WORSE than the ladder)

**Not one positive gain with a CI excluding zero, in 15 model×strategy cells.**
The best cell in the whole study is M2 as a within-tier tie-break at +0.022,
CI [−0.017, +0.071] — includes zero, so ADOPT-AS-TIE-BREAK is also not met.
M3 additionally fails the year-sign criterion (2025 +0.361 / 2026 −0.121).

**Phase-5 verdict: NULL RESULT — the ladder is at or near the information
ceiling of these columns.** This was the plan's stated modal outcome.

Supporting reads, all consistent with the 07-21 column sweep:
- The full-sample M3 tree's root split is `structure = bull_call` — the model
  rediscovers "structure is the signal" unprompted.
- Ablations (top-3/day $ out-of-fold): ladder-only +$6.1k → +regime +$1.9k →
  +geometry +$11.9k → +enrichment +$2.5k → +scores +$4.0k → +calendar +$10.3k.
  Non-monotone and inside the noise: **nothing beyond structure × regime ×
  geometry adds anything reproducible.**
- Composition-proxy test (rule 6) catches `cpir` red-handed: pooled Spearman
  vs E **+0.27**, but within structure +0.04 / −0.03 / −0.10. Same trap as
  oi_confirm/iv_pct. `iv_pct` repeats its own failure (pooled −0.17, within
  structure −0.12 / +0.05 / +0.12, sign-flipping).

### 2. Bear arm B1 — selection: NOT MET, decisively

370 bear rows (bear_put 327 / bear_call 37 / long_put 6), 111 dates. Pooled
E −0.601, CI [−0.726, −0.477], negative every year (−0.815 / −0.660 / −0.386).

496 pre-declared 1- and 2-clause subsets evaluated, 203 with n ≥ 40.
**0 survivors** of the pre-registered rule, against ~10 expected by chance at a
nominal 5% rate. The best subset in the entire search is E −0.231
(`mech BEAR AND iv_pct<0.5`, n=43) — still negative. There is no conditioning
of bear entries, on any decision-time variable in the book, that is not a
losing selection.

**The operator's chop hypothesis, tested directly.** The closest thing to
support is the RANGE + calm/choppy slice, and it is an EXIT story:

    slice                    n    dates   E        R        $        |MAE|/MFE
    model RANGE + C/L-VOL    55   16     -0.370   +0.182   +$10,119   0.76
    model C-VOL              53   20     -0.596   +0.128    +$7,095   0.92
    mech L-VOL               97   38     -0.581   +0.002    +$3,586   0.99
    model H-VOL              78   17     -1.157   -0.682   -$50,482   4.01

RANGE+C/L-VOL is the only bear slice that makes money (R positive in 2 of 3
years: −0.247 / +0.320 / +0.284), and its |MAE|/MFE of 0.76 is the only
non-mirrored bear number in the book. But **E is −0.370 with CI [−0.697,
−0.045] and the R CI [−0.117, +0.463] includes zero**: the plays are still
wrong, the exit is what collects. Directionally consistent with the operator's
instinct; not a selection edge, and n=55 over 16 dates.

The mirror image is decisive and already shipped: bear in H-VOL is −$50.5k at
a 9% win rate and |MAE|/MFE 4.01 — the ladder's BEAR+H-VOL VETO earns its keep.

### 3. Bear arm B2 — exit: **CRITERIA MET**, and it is the knob addendum 12 pre-nominated

Frozen grid only (18 debit configs, no new mechanism). Bear debit n=332:
mean E −0.534 vs mean R(PROD) −0.133 — the exit is ALREADY rescuing ~0.40 of a
bad selection, and six configs rescue more. Ranked by robustness, not by size:

    config              Δ pooled   CI95            ex-25MarApr   2026 alone      LOO min
    BE ratchet @.50     +0.041   [+0.015,+0.065]   +0.020        +0.028 [+0.009,+0.053]  +0.038
    trail .40/.50       +0.042   [+0.007,+0.073]   +0.023        +0.037 [-0.002,+0.077]  +0.038
    trail .25/.50       +0.043   [+0.003,+0.081]   +0.020        +0.025 [-0.032,+0.078]  +0.038
    trail .50/.50       +0.036   [+0.005,+0.064]   +0.014        +0.031 [-0.002,+0.066]  +0.032

**Why this is not addendum 12 again.** Addendum 12 killed the structure-keyed
bear trail because 94% of its gain sat in Mar–Apr 2025 (ex-window +$744 over
241 rows ≈ 0). It closed with two statements that this run tests exactly:
"trail .25/.50 dominates .50/.50 … recorded so the next bear-heavy window tests
the right knob first", and "what would settle it: a second sustained bear
drawdown in the book." Feb–Apr 2026 is that drawdown, and the backfill is now
complete. On the completed book:

- ex-Mar–Apr-2025 Δ is **+0.020** (was ≈ +0.003 in July) — the effect no longer
  lives in one window;
- **2026 alone is +0.028 with CI [+0.009, +0.053]**, i.e. the new, independent
  bear window confirms it on its own;
- positive in all three years (+0.036 / +0.055 / +0.028) and in both pricing
  tiers (real +0.054 / tweak +0.027);
- LOO-by-date: every fold positive (min +0.038) — the test that killed the
  per-regime switch twice.

BE ratchet @.50 is preferred over the trails on robustness, not on pooled size:
it is the only config whose 2026-alone CI excludes zero and its pooled CI is
the tightest. Mechanically it converts 44 rows into `be_stop` and cuts
stop_loss 110 → 92 — it stops giving back excursions, which is precisely the
|MAE|/MFE ≈ 1.1–1.4 mirrored-path signature of bear rows.

**It must be bear-KEYED.** The same config on the non-bear debit book is
+0.234 → +0.209 (−0.026); this is why Attempt 10 was right to remove the global
debit trail and why the correct scope is the structure, not the whole side.

**Honest size.** −0.133 → −0.092 mean R: it cuts the bleed by ~31%, it does not
create an edge, and −$54.4k → −$38.0k over 332 rows. Every bear row in the book
is ladder tier C (299) or VETO (71) — **none are deployed by the shipped
ladder**, so this rule only bites on positions the operator takes deliberately.
That is exactly the stated use case (the chop hedge), which is what makes it
worth shipping despite the modest size.

Credit side (bear_call, n=38): `pt .50` clears CI+LOO (+0.344) but the best
config `sl 1x` does not (CI [−0.012, +1.252]), the population is one year deep,
and bear_call is already structure-vetoed at intake with 0 emissions since. **No
credit-side change** — nothing to apply it to.

### 4. What this changes

- **The bear_put implementation question (open since 07-22) now has a
  non-demotion answer**: keep bear structures selectable, keep them out of the
  deployed top-3 (they are already C/VETO), and give them their own exit
  profile. Selection stays unfixed because it is unfixable from these columns.
- **Recommended (NOT shipped — operator decision):** a structure-keyed exit
  clause for bear debit spreads, `be_after: 0.50`, alongside the existing
  `regime_exit` block in `config/backtest.yml`, plus the matching line in
  `deployment-rules.md` §"Exit management": *if you are holding a bear debit
  spread, move the stop to breakeven once it has made 0.5× the debit.*
- **The ML question is closed** for this feature set. Re-open only on new
  columns, not on new models — the ablations say the columns, not the
  estimator, are the binding constraint.
- Unchanged: no production config, prompt or ladder was modified by this run.

---

## 2026-08-11 addendum — `mech_cell` BACKFILLED across the analysis tabs + nightly job

Plumbing, no tuning conclusion. `mech_cell` shipped 2026-07-22 (archive/06
addendum 9) but only stamps rows written after it, so the deploy-time surface
was blank for the whole history and `NO_DATA` wherever the SPY/VIX table had
been stale. Both are recoverable: the label is a pure function of the signal
date and the frozen table.

- `scripts/backfill_mech_cell.py` — recomputes every row, fills blanks and
  `NO_DATA`, and KEEPS a stored label that no longer reproduces (logged as
  DRIFT, exit 2) rather than overwriting it; `--force` overwrites, `--dry-run`
  reports. Writes only that one column, so formulas and every other column are
  untouched. `make backfill-mech-cell` (depends on `mech-regime`).
- `.github/workflows/backfill-mech-cell.yml` — chained on Compile Flow
  (`workflow_run`), which refreshes the SPY/VIX table at 22:30 UTC, so the job
  can never label off a stale close. Idempotent; nothing to fill = no write.
- Run 2026-08-11: **1,284 cells filled across 1,620 rows / 3 tabs, 0 DRIFT** —
  every one of the 336 previously-stored labels reproduced exactly, which is the
  first end-to-end check that the stored column and `lib/mech_regime.py` agree.
  AnalysisClaude now reads 142 dates, 2024-06-17 → 2026-08-10: BEAR_HE 758 /
  LVOL 728 / RB_EVOL 43 / NONE 78, no blanks, no NO_DATA.

**Header drift found while doing it (fix written, NOT yet applied).**
AnalysisGPT and AnalysisTickerSpecific headers had stopped at 24 columns
against a 27-column `ROW_COLUMNS` — GPT missing `iv_pct`/`price_vector`/
`days_to_earnings` plus pre-rename `ConvictionScore`/`ConvictionScoreLabel`,
TickerSpecific missing `iv_skew`/`iv_pct`/`score_catalyst`. Because
`append_rows` writes POSITIONALLY, every column past the gap is mislabelled on
those tabs, and a column-keyed write lands in the wrong place. Data loss: none —
all 13 rows on those two tabs are empty past `created_datetime` (both tabs are
near-unused). `scripts/align_tab_headers.py` repairs it (relocating a
schema column that is merely misplaced, aborting the tab if a drifted column
holds data that is not in the schema); dry run is clean, the write is pending
operator approval. AnalysisClaude — the tab everything reads — was already
correct.

---

## 2026-08-11 addendum — `bs_options_hist` DROPPED: measured as effect-diluting and replay-contaminating; tier now off behind `proxy.bs_fallback`

Scratch cut on the same 08-11 exports (`bs_tier_decision.py`, read-only, no
config changed). Question from the operator: keep BS, or evaluate on
real+tweak only.

**Calibration is impossible and the tier knows it.** 0 same-key overlap rows
(no play is priced both real and bs — the chain is strictly ordered, so BS is
never checked against a real mark), and `pct_real_days = 0.00` on **all 301**
bs rows. There is no bs row anywhere in the book with a single real price day.

**What is actually lost by dropping it:** 301 rows (27% of the pooled book)
but **0 dates** — every bs date also carries real/tweak rows. The tier is
overwhelmingly the long-dated filler: 69% of the DTE≥180 band is bs (208 of
302 rows), vs 5% of ≤30 DTE and 5% of 31–59. Dropping bs therefore removes
almost nothing from the ≤60-DTE band the ladder actually deploys in.

**The dilution finding (this is the real reason, not the $).** BS marks are
tail-compressed: E sd 0.86 vs real 1.38 / tweak 1.24, `|E|>2` at **2.3% vs
12.1% real**. Flat-ish donor vol, no spread, no gaps — so every bs row sits
nearer zero than a real one, and pooling shrinks **every** effect toward zero
in the same direction:

    bucket            r+t E     pooled E   (bs pulls toward 0)
    bull_call        +0.672  →  +0.540
    tier A           +0.688  →  +0.590
    tier B           +0.601  →  +0.495
    bear_put         −0.528  →  −0.394
    bear_call        −1.240  →  −1.054
    tier VETO        −0.548  →  −0.432

That is attenuation bias against exactly the separations the ladder is built
on. No sign flips and no shipped conclusion reverses (year signs, structure
ranking, ladder monotonicity, bear_put DEMOTE all hold either way — holdout
r+t is E −0.406 CI [−0.517, −0.295] vs pooled −0.358), so bs has **never been
load-bearing for a decision**; it has only ever made true effects look weaker.
Where bs *can* be compared like-for-like (DTE≤59, n=20) it does not track
real: E −0.220 vs real +0.026, sd 1.83.

**It is not merely a headline-$ problem — it enters the replay.** bs supplies
**64 of the top-3/day A-then-B picks**, worth +$8.5k of model-priced P&L, and
inflates the 2026 replay from **+$3.3k (r+t) to +$8.8k (pooled)**. The 08-11
"quote real+tweak only" rule was framed as reporting hygiene; it is actually
a selection problem. Total bs $ is +$51.6k of the +$65.7k pooled, +$48.9k of
that in DTE≥180 (single SNDK 04-06 long_call DTE 182 = +$27.5k).

**Decision — SHIPPED same day (operator approved).**

1. *Evidence layer:* real+tweak is the ONLY population for E, R, $, MFE/MAE,
   ladder tiers, holdouts, and the replay. bs is coverage bookkeeping, never
   evidence. Same standing as the 07-27 §3 long-dated rule.
2. *Chain layer:* `_method2` is now opt-in behind **`proxy.bs_fallback`
   (default `false`)** in `config/backtest.yml`, gated in `_evaluate`
   (`scripts/backtest/proxy.py`). Directional plays fall to `underlying_trend`,
   which answers the same question honestly (direction verdict, blank P&L,
   `exit_basis=NONE`) instead of minting a P&L number that reads as data. Only
   2 rows in the whole book (1 straddle, 1 strangle) would go from bs to
   `unevaluable`; existing bs rows stay frozen unless `--redo`. Cost: no
   path/MFE estimate for long-dated — but a tail-compressed BS path was never
   a usable one. Kept as a flag rather than deleted so the tier can be revived
   for a deliberate study; two tests pin both branches of the chain
   (`test_evaluate_skips_bs_tier_by_default_and_falls_to_underlying_trend`,
   `test_evaluate_uses_bs_tier_when_bs_fallback_enabled`). Docs synced:
   `config/backtest-reference.md` fallback-chain section + `proxy_method` row,
   `docs/architecture.md` proxy map, proxy.py module docstring.
3. *Historical rows are NOT purged.* The 301 existing `bs_options_hist` rows
   stay in BacktestProxy — filter them out at read time by `proxy_method`
   (equivalently `pct_real_days == 0`); the flag only stops NEW ones.
4. What this does NOT fix: the long-dated blind spot itself. Removing bs makes
   the gap visible instead of papered over; the fix is still real long-dated
   price history.

---

## 2026-08-11 — completed-book analysis: holdout coverage FULL, DEMOTE fires at n=164; bs long-dated rows contaminate pooled $ totals

Source: fresh exports `backtests/to_evaluate/analysis - BacktestResults.csv`
(406 rows) / `- BacktestProxy.csv` (796), stamped 08-11 15:38. Pooled priced
book after dedup: **1,118 rows** (real 406 / tweak 411 / bs 301), 118 dates,
2024-06-17 → 2026-04-07. Scratch cut (read-only), no config changed. Operator
instruction: treat the run as complete even though some analyses are flagged
for rerun. Housekeeping: 0 within-real dups (03-06 fix held); all 7
previously-missing holdout dates present; 02-17/02-19 present in both tabs.

### 1. Year breakdown — 2025H1-only profit confirmed; 2026 is the only year with CI fully below zero

    year   n     mean E   CI95 (date-clust)     R        $ (real+tweak)
    2024   295   −0.018   [−0.195, +0.152]      −0.059   −$14,355
    2025   499   +0.091   [−0.037, +0.213]      +0.145   +$47,893
    2026   324   −0.196   [−0.287, −0.101]      −0.055   −$19,503

    halves: 2024H1 −0.198 · 2024H2 +0.009 · 2025H1 +0.136 (+$78.0k pooled) ·
            2025H2 −0.181 · 2026H1 −0.196
    MFE/MAE by year: |MAE|/MFE 1.13 / 0.79 / 1.18, R-capture −0.08 / +0.16 /
    −0.09 — only 2025 has upside asymmetry; 2024/2026 mirrored = path-vol.

**⚠ Pooled-$ contamination (new standing hazard).** Pooled realized $ reads
+$65.7k, but **+$48.9k of it is DTE≥180 `bs_options_hist` rows with
`pct_real_days = 0.0`** — pure flat-vol BS marks on exactly the contracts the
2026-07-27 §3 rule says carry no evidence. One row (04-06 SNDK long_call,
DTE 182) is +$27.5k by itself; the 04-06 NVDA/MRVL long_calls (DTE 722/725)
add +$9.6k. The honest book is **real+tweak: +$14.0k total** (−$14.4k / +$47.9k
/ −$19.5k by year). Any headline $ from these exports must be quoted
real+tweak; the pooled figure is not a portfolio number.

### 2. Structure breakdown (pooled / real+tweak E)

    structure          n(pooled)  E pooled  E r+t    R       $ r+t
    bear_put_spread    468        −0.394    −0.528   −0.081  −$44,000
    bull_call_spread   338        +0.540    +0.672   +0.295  +$80,237
    bull_put_spread    237        +0.101    +0.183   −0.005   −$1,946
    bear_call_spread    43        −1.054    −1.240   −0.518  −$11,221

    year × structure (E): bear_put −0.41/−0.43/−0.35 (negative every year);
    bull_call +0.44/+0.66/+0.29 (positive every year — still the only
    reproducing positive); bull_put +0.24/+0.25/−0.17 (2026 out-of-band
    DTE-driven as before); bear_call −1.97/−0.70/— (0 emissions 2026 —
    intake veto holding).

### 3. Ladder reproduces on the completed book

    tier    2024            2025            2026
    A       +0.708 (n=37)   +0.670 (n=105)  +0.305 (n=45)
    B       +0.338 (n=88)   +0.644 (n=98)   +0.431 (n=13)
    C       −0.294 (n=131)  −0.299 (n=207)  −0.278 (n=249)
    VETO    −0.586 (n=39)   −0.294 (n=89)   −0.803 (n=17)

A/B positive, C/VETO negative every year. Top-3/day A-then-B replay:
2024 +$22.7k (64% win) · 2025 +$44.8k (67%) · 2026 **+$8.8k** (66%, mean R
+0.364). 2026 Tier A improved +0.210 → +0.305 with the late dates added —
the 08-08 "genuinely weaker Tier A" worry softened. bull_put band in-window:
in-band E +0.431 / R +0.337 (n=13) vs out-of-band −0.139 / −0.211 (n=59) —
second independent window, band holds.

### 4. bear_put holdout at FULL coverage — all three pre-registered criteria fire

    n=164 priced (was 82 at the 08-04 mid-stop)
    mean E −0.358   date-clustered bootstrap CI95 [−0.460, −0.256]
    halves: early −0.207 (n=87) / late −0.529 (n=77)  ← late worse, as predicted
    ex-flawed-dates (02-23/03-02/03-20): −0.380 (n=154)
    → mean E < 0 PASS · CI upper < 0 PASS · both halves < 0 PASS → DEMOTE

The 08-04 real-tier discordance is **resolved downward**: real E −0.169
(n=51; was +0.201 at 08-04, −0.178 at 08-08) vs tweak −0.569 / bs −0.204.
Real R +0.047 — the "negative unmanaged, ~breakeven only under active risk
control" framing survives verbatim. Measure-dependence caveat stands: R-based
read is −0.086 CI [−0.215, +0.042] (includes zero), halves +0.042 / −0.232
deteriorating into the bottom. Comparator bull_call in-window: E +0.293 /
R +0.315 (n=43), |MAE|/MFE 0.51 vs bear_put 1.25 — same discriminator as
addenda 14/07-29.

**Status.** The addendum-13 criteria are now satisfied on the completed
second drawdown via this scratch cut. The formal decision run remains
`bear_position_study.py` unmodified on the window (its `AC_PATH`/`BR_PATH`/
`BP_PATH` need repointing to these exports first — the 08-04 flag #2 is
still true). Given the operator's "treat as fully run", the demotion is
decision-eligible NOW; what remains is the implementation choice (intake
`structure_veto` like bear_call vs ladder VETO tier vs leave-at-C-never-
deploy) — a user decision, deliberately not taken here.

### 5. Next study: ML combination search — plan written, NOT run

Pre-written plan at [`ml-plan.md`](ml-plan.md): learn which structure ×
regime × entry-geometry × enrichment combination best predicts play outcome,
benchmark = the shipped score-free ladder's top-3/day replay, purged
walk-forward CV clustered by date, real+tweak training only, pre-registered
ship criteria. Nothing executed as of this entry.

---

## 2026-08-08 — year-split evaluation on refreshed exports: 2025 IS the outlier for the raw book; the ladder separation is what reproduces per year

Source: fresh unversioned exports in `backtests/to_evaluate/` (`analysis -
BacktestResults.csv` 384 rows / `- BacktestProxy.csv` 738). Pooled priced book
after dedup (date|ticker|structure|play): **1,043 rows** (real 384 / tweak 381 /
bs 278), 2024-06-17 → 2026-04-02. Read-only scratch cut; no config changed.
Housekeeping vs the 08-04 mid-stop flags: **#1 the 2026-03-06 wholesale
duplication is GONE from this export** (0 within-real dups found), **#2 the
stale-export problem is resolved by this drop**, **#4 02-17 and 02-19 are now
present in both tabs**. Still missing from the holdout window: 03-18,
03-23→03-26, 04-06/04-07 (7 of 32 dates, the block nearest the episode bottom).

### 1. The unfiltered book has no standalone edge — 2025H1 is the only positive half-year of five

    year   n    mean E   E CI95 (date-clust)   R       $ realized
    2024   295  −0.018   [−0.193, +0.149]      −0.059   −$11,391
    2025   499  +0.091   [−0.036, +0.214]      +0.145   +$63,669
    2026   249  −0.243   [−0.344, −0.140]      −0.051   −$11,505

    half-years: 2024H1 −0.198 · 2024H2 +0.009 · 2025H1 +0.136 (+$78.0k) ·
                2025H2 −0.181 (−$14.4k) · 2026H1 −0.243 (−$11.5k)

Net book +$40.8k, all of it 2025. **Answer to "is 2025 an outlier": for the
take-everything book, yes** — and it is NOT the Mar–Apr window doing it (2025
ex-window E +0.184 beats in-window +0.001; the window has fat realized dollars
+$42.6k but flat expectancy on huge n=254). MFE/MAE agrees: 2024 and 2026 are
mirrored (|MAE|/MFE 1.13 / 1.26, R-capture −0.08 / −0.09 — path-vol by the
asymmetry rule); only 2025 shows upside asymmetry (0.79, capture +0.16).

### 2. What DOES reproduce in all three years: the ladder separation

Tier means on E (deployment-rules.md ladder recomputed from row fields):

    tier    2024            2025            2026
    A       +0.708 (n=37)   +0.670 (n=105)  +0.210 (n=34)
    B       +0.338 (n=88)   +0.660 (n=103)  +0.431 (n=13)
    C       −0.275 (n=135)  −0.291 (n=215)  −0.322 (n=185)
    VETO    −0.691 (n=35)   −0.402 (n=76)   −0.803 (n=17)

A/B positive and C/VETO negative in **every** year (A<B inversion in 2026 is
within thin-n noise; both positive). Top-3/day A-then-B replay is positive every
year: 2024 +$22.7k (64% win) · 2025 +$44.9k (67%) · 2026 +$5.9k (65%, mean R
+0.374). The bull_put band separates every year (in-band vs out E: 2024 +0.51 /
+0.10 · 2025 +0.83 / −0.08 · 2026 +0.34 / −0.44 — 2026 out-of-band is again
DTE>59-driven, −0.456 over 40 rows). bear_put E is negative with CI upper < 0
in each year separately (−0.41 / −0.43 / −0.32); bear_call is disastrous in
both years it appears (−1.97 / −0.70).

**So "is there proven edge": not in the analysis-as-emitted — the edge that
survives a year split is entirely SELECTION.** The system's claim is "the
ladder finds the deployable 20%", not "the plays make money" — 2024 proves it
(book −$11.4k take-everything, +$22.7k top-3 replay, and the −$36.6k of 2024
bear-structure losses are exactly what the ladder screens). Standing caveat
unchanged: the ladder was derived on this same pooled book, so per-year
consistency is robustness, not out-of-sample proof — the live walk-forward
remains the only true test.

### 3. The 2026 read: mostly composition, partly a genuinely weaker Tier A

2026 = the Feb–Apr bear episode, nothing else (29 dates, 02-02 → 04-02). It is
**57% bear_put by row count** (141/249) — the model answered a bear tape by
emitting its known-worst structure in size. Ex-bear_put 2026 is −0.138 (n=108,
median +0.002) — weak, not disastrous; the deployable A/B slice is +$6.6k. The
genuine warning is **Tier A at +0.21 vs +0.71/+0.67 in prior years** (n=34,
median +0.18): the flagship bull_call cell is much thinner in a bear episode,
as it should be directionally, but it has not yet been negative.

### 4. bear_put holdout: all three pre-registered criteria fire again at near-full coverage

Feb–Apr 2026 window, n=141 priced over 27 dates (08-04: 82/16):

    mean E −0.324   CI95 [−0.448, −0.202]   halves −0.154 / −0.496   → DEMOTE
    R −0.033 (exit rules still rescuing ~0.29 of E)

Late half twice as negative as early — deterioration into the episode bottom,
the wrong direction for a bear structure in a bear market. The 08-04 real-tier
discordance has **softened**: real is now E −0.178 (n=40) vs tweak −0.474 —
no longer positive, though real R is +0.135 (+$9.3k), keeping the addendum-14
framing "negative unmanaged, breakeven only under active risk control" alive.
Formal decision still waits on `bear_position_study.py` unmodified over the
completed window (7 dates outstanding), but this is the third consecutive read
where every criterion fires, now at 141 rows.

### 2026-08-08 addendum — year × regime × structure screens: the only reproducing POSITIVE cell family is bull_call; everything else that reproduces is a negative

Same pooled 1,043-row book, grouped by year × market_regime (direction / vol /
cell), year × stock (per-play) regime (leading BULL/BEAR/RANGE token of the free
text), and year × structure crosses. Screens required n≥8–10 per year present
and same-sign mean E every year; 24 cells tested across the three screens (few
enough that the consistent ones are not a multiplicity artifact — and they
cohere into one factor rather than scattering).

**Positive, every year present (the entire list):**

    bull_call × market-RANGE   +0.71 / +0.60 / +0.15   CI[+0.31,+0.81]  (= Tier A)
    bull_call × stock-BULL     +0.24 / +0.74 / +0.05
    bull_call × BULL (mkt)     +0.30 / +0.60 / — (no 2026 BULL dates)
    bull_put  × BULL (mkt)     +0.19 / +0.59 / — (thin, no 2026 test)
    bull_call × BEAR+E-VOL     — / +1.04(n=17) / +0.38(n=9)  (new, thin, contrarian)

Every one is long-delta. The 2026 magnitudes shrink toward zero (+0.15/+0.05):
the cell survives sign-wise through the bear episode but the edge is thin there.

**Negative, every year present:** bear_put × {BEAR, BULL, RANGE} market,
bear_put × {stock-BEAR, stock-RANGE}, bear_put × four market cells,
bear_call × stock-BEAR, bull_put × {BEAR+E-VOL, RANGE+E-VOL},
market H-VOL pooled (−0.69/−0.33/−0.10), market BEAR pooled
(−0.73/−0.23/−0.29), stock-BEAR pooled (−0.51/−0.55/−0.26).

**Reads.** (1) The "proven edge" grouped this way is ONE positive factor —
long-delta debit structures in non-bear-labelled conditions — surrounded by
reproducing negative knowledge; the ladder is close to the best available
partition of this book. (2) bear_put is negative in every year × every market
direction × every stock regime — the demotion needs no regime qualifier.
(3) H-VOL is negative all three years *unconditionally*, suggesting the shipped
BEAR+H-VOL veto may be the narrow version of a vol-only veto (H-VOL 2026 is
only −0.10, so not actionable without the missing dates). (4) bull_put ×
RANGE+E-VOL is negative all three years (−0.20/−0.04/−0.03) — the current
Tier-B band admits these; a regime qualifier is a candidate, not a rule.
(5) Alignment cut (structure direction vs stock regime) adds nothing: "with"
flips sign by year; "against" is positive every year on comedy n (10/20/6).
(6) stock-RANGE rows are E-negative but R-positive all three years — exits
extracting from chop; composition unexamined, not evidence. No 2026 data
exists for market-BULL or C-VOL, so the strongest 2024/2025 cells are simply
untested in 2026. Standing circularity caveat applies — these crosses are
re-derivations on the derivation book, now with per-year sign checks.

### 2026-08-08 addendum — bear_put MFE re-check on the refreshed book: addendum-14's "volatility, not direction" read reproduces; exit is already rescuing ~0.32

User asked whether the ten-cell demotion read means bear_put *never* went into
profit, or whether the exit is the fixable part. Recomputed on the refreshed
1,034-row deduped pool (bear_put n=424: 146 real / 160 tweak / 118 bs):

    MFE  mean +0.692  median +0.392  reach+0.30 57%  reach+0.90 29%  never>0 16%
    E    mean −0.392  median −0.897        R  mean −0.069
    give-back MFE→E +1.084   exit rescue R−E +0.323
    mfe_day 20 vs mae_day 40, MFE-first 71%
    of 241 rows reaching MFE +0.30: 61% end E<0 (held to cap), 38% end R<0

Same shape in each year separately (2026 holdout n=132: MFE +0.585, E −0.325,
rescue +0.29) and worst in the REAL tier (E −0.517, give-back 1.36) — the bs
tier is the only benign one (E −0.02), so real pricing makes it worse, not
better. bull_call comparator: give-back only 0.541, E +0.538. Answer stands as
addendum 14 ruled: the excursion is round-trip volatility, not harvestable
edge — the shipped exits already extract ~0.32 of E, the structure-keyed trail
was tested (addendum 12) and was one-window. No new cut type, no config change;
per addendum 13 the next move on bear_put is the completed holdout, not
another exit variant.

Follow-up cut, same session — "was bear_put a good choice IN the Feb–Apr 2026
bear episode": no, even there. In-window bear_put (n=132) E −0.325 / R −0.035 /
−$1.9k vs in-window bull_call (n=36) E +0.193 / R +0.312 / +$4.7k — the
long-delta structure beat the bear structure inside the bear episode itself
(rhymes with addendum 14's "bull_call beats bear_put inside mechanical BEAR
cells"). Timing decomposition: Feb entries R +0.125 (60% win, +$6.7k), Mar flat,
Apr catastrophic (R −0.700, 9% win, −$8.2k); early/late halves split at 03-06:
+$10.0k / −$11.9k. Even the February winners are exit-manufactured — Feb E is
still −0.205, the rescue is the early-run harvest before the rebound. Real tier
in-window R +0.131 (+$8.9k) keeps the addendum-14/08-04 framing "negative
unmanaged, breakeven-to-positive only under active risk control". Caveat the
right way: the 7 missing holdout dates are the block NEAREST the bottom
(03-18, 03-23→26, 04-06/07) — i.e. more late-window rows, the worst slice, so
completion should make the window read worse, not better.

Full path re-read of the same window (user flagged the cut above used only
E/R — asymmetry rule applied): bear_put in-window |MAE|/MFE **1.13** (mirrored
= path-vol by the standing rule), capture R/MFE −0.06, 59% of MFE≥+0.30 rows
round-trip to E<0 (exits recover about half: 32% still end R<0). bull_call
in-window is genuinely asymmetric — |MAE|/MFE **0.56**, capture +0.36, only
17% round-trip — so the bear-window inversion is not two flavors of noise; one
structure has real upside asymmetry there and the other doesn't. Month
asymmetry marches 0.89 (Feb) → 1.11 (Mar) → **4.34** (Apr: MFE +0.215,
mfe_day 8.5, MAE −0.934 late = bought the bottom, small pop, rebound ran them
to −100%). Even Feb's positive R (+0.125) sits on 64% round-trip — exits
harvesting path-vol, not direction. bull_put's in-window failure is the
opposite shape: |MAE|/MFE 2.21, capture −0.53, LOW round-trip (23%) — genuine
adverse direction (E-VOL short-put), not path-vol; different problem, different
cell (the RANGE/BEAR+E-VOL screen). Real-tier bear_put is the most favorable
path read (0.82, MFE med +0.70, mfe_day 13) and still E −0.134 with 48%
round-trip.

Qualifier sweep, same session (user hypothesis: "bear_put feels safer in bear
markets — maybe it's the qualification step"). Both bear windows cut
(Feb–Apr 2026 n=132 / Mar–Apr 2025 n=105); only the two pre-registered
qualifiers are decision-relevant, the rest is post-hoc:

- **"Safer" is TRUE as a tail claim** — in-window managed bear_put loses
  $14.6/row with 1% of rows at R≤−0.90 (min −$1.6k) vs bull_put −$141.8/row
  with **23%** at R≤−0.90 (min −$5.0k). Defined-risk debit + early MFE +
  shipped exits = small bounded losses. Safety yes; expectancy no — no
  qualifier cell is E-positive in both windows.
- **iv_spread ≤ 0 (shipped Tier-C rule): 6th right-signed confirmation** —
  2026 keeps R +0.089/+$3.9k (n=27) vs skips R −0.219 (n=6); 2025 same sign.
  But **99/132 window rows have iv_spread MISSING** (unenriched holdout
  dates) — the shipped qualifier is blind on 75% of the window; the action
  item is the existing 7-date backfill, nothing new.
- **|delta| 0.30–0.45 recorded cut: DEAD** — right-signed 2026 (E +0.142,
  n=17), sign-flips 2025 (E −0.972, R −0.161 vs outside +0.067). The
  addendum-14 "mean carried by tails" suspicion confirmed on the other window.
- **New post-hoc candidate, motivating only: LOW entry IV** — iv_entry_pct
  below-median is R-positive in BOTH windows (+0.051/+$6.0k · +0.347/+$20.5k,
  asym 0.57) and above-median negative in both (−0.120 · −0.298, asym
  1.39/1.89). Textbook mechanism (don't pay elevated vol for a debit spread
  late in a selloff) but confounded with episode age (IV rises into the
  bottom, and the timing split is the same shape), and E is negative in both
  low-IV halves (−0.481/−0.686) — it selects which bear_puts the exits can
  rescue, not an edge population. Park next to the early/late finding as
  probably one factor.
- score_total ≥ 70 anti-selects in both windows again (R −0.096/−0.301).

Net: qualification can move managed bear_put from ~breakeven to modestly
positive (early-episode ∧ low-IV ∧ iv_spread≤0 slices) but uncovers no
positive-E sub-population; the demotion question is expectancy, and stands.
Per addendum 13 none of this is decision-eligible — finish the backfill,
run the pre-registered study.

---

## 2026-07-27 — the pre-engine discretionary book, and the long-dated blind spot

Source: `portfolio/` (IBKR flex exports, 468 closed trades, 2025-02-03 →
2026-07-24, +$10,634). **This is pre-engine and mostly pre-June-2026** — it is
a portrait of how the operator trades by hand, NOT a test of the engine and not
a holdout. Treat every comparison below as directional, not evidential: n per
structure is 7–26, unconditioned by regime, and discretionary in sizing/timing.

### 1. What the discretionary book independently confirms

- **Cadence.** P&L per trade by same-day trade count is monotone decreasing:
  1/day +$119 (n=67) · 2–3/day +$25 (n=160) · 4–6/day +$9 (n=109) · 7+/day
  **−$18** (n=132). Win rate is flat (51–59%) across all four, so this is
  dilution, not worse reads on busy days. The ladder's 1–3 positions/day cap
  came from capital constraints, not this data, and it lands on the knee.
- **Concentration.** Top-3 trades = the entire book: ex-top-3 the book is
  **−$5,004** over 465 trades; ex-top-10 it is −$20,478. Compare the ladder's
  derivation finding (top-3/day = 28% of positions, 83% of book P&L).
- **DTE.** 0DTE −$541 · 1–14d −$1,857 · 15–45d +$5,940 · 45d+ +$7,093.
- **The bull_put DTE band reproduces out-of-sample.** His 26 bull put spreads,
  never seen by the engine: DTE ≤22 → n=14, **−$1,805**; 45–59 → n=4, **+$443**.
  That is the PROVISIONAL 45–59 preference in `deployment-rules.md` landing on
  independent, real-fill, human-executed data. Weak n, right sign.

### 2. What it contradicts (noted, NOT actioned)

The four engine verticals total **−$1,952** over 58 trades in his book; all
+$10,072 of profit came from naked/single-leg and calendars, which the engine
does not emit. Tier ordering also inverts: bull_call (Tier A) 36% win /
−$1,652 (n=14, one TSM trade = −$2,101 of it); bear_call (hard VETO) 86% win /
+$479 (n=7). **Not evidence against the ladder** — no regime conditioning, no
delta/DTE gating, tiny n, and discretionary entry timing. Recorded so it is not
rediscovered as novel later.

### 3. The long-dated blind spot (the real finding)

`deployment-rules.md` is **in practice a ≤60-DTE ladder, and not by design.**

Pooled across all `backtests/results*.csv` + `proxy_results*.csv` (203 unique
plays), 36% of what the engine emits is horizon ≥180:

| horizon | 14 | 60 | 180 | 720 |
|---|---|---|---|---|
| real-priced | 4 | 42 | 8 | 1 |
| proxy (skipped by real backtest) | 2 | 73 | 54 | 19 |

53 of 54 h=180 rows and **19 of 19** h=720 rows were skipped with
`skip_reason = no_history`. Barchart's options history does not carry those
contracts, so they never got real prices and never entered the ladder's
evidence base. Nothing in `ANALYSIS_PROMPT_CONTRACT` blocks long-dated —
`structure` already lists "long call", `horizon` already has 180/720 buckets,
and the DTE-discipline rule already says default ≥45 DTE. The pipeline has been
dropping the rows, not the prompt.

**The BS proxy cannot substitute here** (user challenge, correct — my first
suggestion, "fix `path_cap_days` and 73 rows become readable", was wrong):

- All 45 long-dated `bs_options_hist` rows have **`pct_real_days = 0.0`**. Not
  partially modeled — zero days of those paths came from a real quote.
- `_method2` (`scripts/backtest/proxy.py:450-478`) prices the target leg off a
  **donor contract at a different expiry**. For a 500-DTE leg the donor is
  necessarily far shorter-dated — that is why the real leg had no history. Term
  structure is unmodeled at the horizon where vega dominates. Worst possible
  place for flat-vol BS.

So the real evidence base is 21 rows, not 73:

| | n | mean | win | MFE | MAE |
|---|---|---|---|---|---|
| `strike_expiry_tweak` (real-priced), h≥180 | 21 | −0.46 | 24% | +0.41 | −0.96 |
| of which h=180 / h=720 | 20 / **1** | | | | |

**At h=720 there is no evidence either way (n=1).** The 21-row negative also
does not settle it: those are spreads (MAE −0.96 = defined-risk structures
going to near-total loss), and all are still scored under `path_cap_days: 120`
and `time_exit_dte_fraction: 0.75` — 23/49 h=180 and 14/17 h=720 rows exit
`cap_open`, i.e. marked at an arbitrary date rather than a real exit.

**Shape note.** The operator's three book-carrying trades were long-dated
*instruments* on **short holds**, not hold-to-expiry: TSM 276 DTE held 69d
(25% of DTE), GLD 246 DTE held 82d (33%), GOOG 205 DTE held 121d (59%). Buying
convexity with theta off, then leaving on the move. The current exit config
would hold that TSM call 207 days. Any future long-dated test must model this
shape, not hold-to-expiry.

**Status: BLOCKED, not queued.** The blocker is real long-dated option price
history, and no re-read of existing rows fixes it. Only lead is IBKR
(`get_price_history` / `get_option_data` over the connected MCP) — unprobed,
user deferred 2026-07-27. If IBKR has no depth on 180+ DTE contracts, the only
route is paper-forwarding long-dated plays live. Do NOT ship a long-dated tier
off BS rows.

### 4. Live substitution — the operator sometimes trades naked where the engine said spread

Reported by the user 2026-07-27. When the analysis emits e.g. a bull call
spread, he sometimes buys the naked long call instead.

**Why it matters:** it silently breaks the live walk-forward's attribution. A
naked long call and its debit spread share direction and entry but not payoff,
max loss, vega, or exit behaviour — the spread caps upside where the naked leg
carries the convexity that produced 100% of this book's profit. Any live-vs-tier
comparison that assumes the deployed position matches the emitted `structure`
will mis-attribute both wins and losses, in the direction of making the ladder
look wrong when the substitution was the variable.

**Action:** the live walk-forward eval must record the **structure actually
traded** alongside the emitted one and split on divergence, before any live
result is read against tier means.

`backtests/live_loop/stage1_map_fills.py` already derives both sides —
`classify_structure()` from the IBKR fill and `play_structure()` from the play
text — but its match confidence is only `EXACT` / `STRUCTURE` / `NONE`, with no
substitution category. A naked long call filled against a `bull_call_spread`
play therefore falls to **`NONE`, indistinguishable from "no play that day"**:
substitutions are silently dropped from the eval rather than labelled.

> **CORRECTED 2026-08-11 (v3 close-out §3): the paragraph above is wrong.** Such
> a fill did NOT fall to `NONE` — `SIDE` maps `long_call` and `bull_call_spread`
> both to `debit`, so the family branch labelled it `STRUCTURE` and pooled it in
> as a match. Not dropped: *miscounted*, which is worse. A second defect (the
> branch ignored direction entirely) is fixed in the same change. Read the
> close-out entry, not this paragraph.

Adding a
`SUBSTITUTED` confidence (same ticker, same direction, different structure) is a
precondition for the eval, not a nice-to-have — otherwise the deployed book
being read is exactly the subset where he followed instructions, which biases
the live-vs-tier comparison in an unknown direction.
This is also the one channel through which the long-dated question could get
answered by accident: if he substitutes naked long-dated calls for h≥180
spreads, those fills are real prices on exactly the contracts the backtest
cannot reach.

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

## 2026-08-12 — v1 → v2 → v3 prompt-version comparison, and June-2026 live-vs-analysis audit

Run at operator request. Two questions: (1) did the prompt improve across
versions, (2) how did the June-2026 live book line up with what the analysis
actually emitted. Inputs are the CSV exports in `backtests/to_evaluate/`.
**Real + `strike_expiry_tweak` tiers only** — `bs_options_hist`,
`underlying_trend` and `unevaluable` excluded throughout, per the shipped
`proxy.bs_fallback` off decision.

### 0. Two data traps found on the way in — both would have flipped the answer

**`realized_pnl_pct` changes dtype across versions.** v1 stores it as a
percent STRING (`"1.64%"`, `"-100.00%"`); v2/v3 store decimal fractions
(`0.9994`). A naive `to_numeric` silently drops 153 of 255 v1 rows and leaves
a survivor subset whose median reads +0.60 — i.e. it manufactures a large fake
v1 edge. Any future cross-version pull MUST strip `%` and divide by 100 for v1.
This is the pre-`feedback_percentages_decimal` era leaking into the exports.

**v1 has no BacktestProxy export**, so v1 = 255 real rows with zero tweak tier,
while v2/v3 carry 53/411 tweak rows. Every table below is therefore reported
BOTH as real+tweak and real-only.

### 1. Version comparison — no improvement is measurable

Only **22 signal dates are common to all three** versions (2024-06-17 ..
2025-12-10). v1 covers 56 dates, v2 22, v3 118 (to 2026-04-07), so the
full-window numbers compare different market windows and are not a version
read. On the common window, real+tweak:

    ver    n    win    med E    mean E    total $    PF    med MFE   med MAE
    v1   101   0.554   +0.164   +0.091      8194    1.20    0.70     -0.99
    v2   168   0.488   -0.137   +0.054     14654    1.22    0.91     -0.97
    v3   162   0.481   -0.215   -0.043      4534    1.07    0.82     -0.99

Real-only is worse for v3 (n=101, win 0.455, mean E −0.107, total −$1,100, PF 0.97).

Date-clustered bootstrap on paired per-date mean E, 22 dates, real+tweak:

    v3 - v1   -0.183  [-0.367, +0.002]   n.s.
    v3 - v2   -0.154  [-0.305, -0.008]   SIG (does not survive real-only)
    v2 - v1   -0.029  [-0.268, +0.213]   n.s.

**Verdict: there is no evidence that v2 improved on v1 or that v3 improved on
either.** The single significant result points the wrong way and is
tier-fragile. Emission volume is flat across versions (10.9 / 10.9 / 11.5
analysis rows per common date), so v3 is not buying breadth either.

### 2. Why the comparison cannot be attributed to the prompt anyway

`created_datetime` shows the three books were priced by three different
backtest engines:

    v1 rows created 2026-06-21..06-25    entry_source real+barchart
    v2 rows created 2026-07-06..07-07    entry_source barchart_open+barchart_open
    v3 rows created 2026-07-09..08-10    entry_source barchart_open+barchart_open

The next-day-OPEN entry re-baseline (2026-07-06) lands exactly between v1 and
v2; the DEBIT trailing-stop removal (07-04) and credit `stop_loss` removal
(07-13) also fall inside this span — v1 has 0 `trailing_stop` exits, v3 has 31.
**Engine version is perfectly confounded with prompt version in these exports.**
Exit capture moves the same way (share of MFE>+25% rows that still close red:
v1 0.21, v2 0.37, v3 0.35), which is an exit-rule signature, not a selection one.

Nothing here should be read as "the prompt got worse". The correct statement is
that these exports **cannot answer the question**. To answer it, v1 and v2
analysis rows must be re-run through the CURRENT engine.

### 3. What the gap actually decomposes into (composition, not selection)

Common dates, <180 DTE, medians reweighted to v1's structure mix:

    v1   raw -0.074   v1-mix-weighted -0.079    (n=85)
    v2   raw -0.307   v1-mix-weighted -0.193    (n=141)
    v3   raw -0.488   v1-mix-weighted -0.228    (n=129)

Roughly half of v3's raw deficit is structure composition. Per-structure medians
on common dates:

    structure           v1(n)        v2(n)        v3(n)
    bull_call_spread   +0.528(52)   -0.285(74)   +0.383(56)
    bear_put_spread    +0.116(43)   +0.908(60)   -0.648(51)
    bull_put_spread    -0.803(1)    +0.666(20)   +0.668(35)
    bear_call_spread   -1.517(1)    -1.100(10)   -1.099(16)

Two things line up with already-recorded conclusions and one is new:

- **bear_call is toxic in all three versions** (−1.1 to −1.5). Consistent with
  the 2026-07-13 intake veto; the residual rows here are pre-veto.
- **bull_put is the one genuine v2→v3 gain**: emission share 12% → 20% at a
  stable +0.67 median. That is the shipped `deployment-rules.md` constraint
  showing up in composition.
- **bear_put swings +0.91 (v2) → −0.65 (v3)** on overlapping dates. This is a
  third independent sighting of the bear_put problem and it is NOT explained by
  the engine change alone, since bull_call recovers over the same span.

### 4. The whole book's dollars are long-dated, in every version

Common dates, real+tweak, total $ split at 180 DTE:

    ver     <180d      >=180d
    v1      +23       +8,170
    v2   +10,133      +4,522
    v3    -5,998     +10,533

v3's entire positive dollar result comes from DTE≥180 rows, and its <180d book —
the band the deployment ladder actually trades — is **negative**. These are
real-priced rows, not the bs tier, so this is a different observation from the
2026-08-11 "+$49k of DTE≥180 bs rows" contamination note. It sharpens
`project_longdated_blind_spot`: the ladder is ≤60 DTE by accident, and the
money in the backtest is somewhere the ladder does not go.

### 5. June-2026 live book vs the analysis — coverage gap first

**The v3 AnalysisClaude export contains ZERO June-2026 rows** (v3 months present:
Feb 110, Mar 251, Apr 44, Jul 198, Aug 64). June analysis lives in the v1 export
(107 rows, 06-10..06-24) and the v2 export (45 rows, 06-25..06-30), and there is
no coverage at all before 06-10. So June cannot be evaluated against v3, and no
June row carries `score_total` — **the deployment ladder was not applicable to
anything traded in June.**

Backtest coverage also stops at 2026-04-07, so there are no backtest rows for
June either. The audit below is live-trade vs emitted-play only.

IBKR trades carry no strike/expiry/right, so entries were reconstructed by
grouping fills on order timestamp and matching `average_price` against open
positions. 12 option entry events in June:

    date   tkr   live structure                  analysis that day        verdict
    06-05  NVDA  bull call spread Jun'27 LEAP    (none - no coverage)     UNCOVERED
    06-05  QQQ   debit spread                    (none - no coverage)     UNCOVERED
    06-10  MSFT  LONG CALL naked @41.37          bull call spd 410/480    SUBSTITUTED
    06-12  QQQ   debit spread                    bull call spd 725/760    MATCH
    06-15  NVDA  short call (overwrite)          bull call spd 185/210    OVERWRITE
    06-15  TSM   short call (overwrite)          (none that day)          UNCOVERED
    06-16  MU    bull put 920/940 (SOLD vol)     long strangle, VOL       CONTRADICTED
    06-22  INTC  bull put 115/130 (credit)       bull call spd 145/180    SUBSTITUTED
    06-23  AMD   debit spread                    bull call spd 600/720    MATCH
    06-23  SMH   bear put 470/440                bear put spd 600/540     MATCH
    06-30  NVDA  short call (overwrite)          (none that day)          UNCOVERED
    06-30  TSM   bull call spd 450/530 Dec       bull call spd 460/500    MATCH

4 clean matches, 2 substitutions, 1 direct contradiction, 2 overwrites,
4 uncovered (3 by date-gap, 1 by ticker-gap).

**The `SUBSTITUTED` category from `project_live_walkforward_in_progress` is now
observed twice and in two distinct forms**, which matters because they have
opposite sign:

- **06-10 MSFT — naked long leg where a spread was emitted.** Analysis said
  bull call spread 410/480 163DTE; the live trade was the long call alone at
  41.37, closed 06-22 at 29.63 for **−$1,176**. The emitted short 480 leg would
  have financed part of that. Substitution cost money.
- **06-22 INTC — credit structure where a debit was emitted.** Analysis said
  bull call spread 145/180 and explicitly flagged IV ~95% as "very rich",
  choosing a debit "to neutralize" it; the live trade was a bull PUT credit
  spread 115/130 — same direction, opposite vega. INTC then fell. Both reads
  were wrong on direction, but the emitted 145/180 debit spread would have been
  a near-total loss while the credit spread is at **−$793** unrealized.
  Substitution saved money, and did so by taking the side the analysis's own
  IV comment argued for.

**06-16 MU is the one outright contradiction**: the analysis called RANGE + E-VOL
into earnings and emitted a long strangle (buy vol, IV 99-120%); the live trade
sold vol via a 920/940 put credit spread. Worth logging because the analysis
itself hedged — its Alt clause said the two-sided flow "could be dealers/funds
selling earnings vol", which is the side actually traded.

**Attribution caveat — do not compute June-entry P&L from the current book.**
July is a wall of rolls (50 MU fills, 21 TSM fills between 07-01 and 08-11), so
`average_price` on most surviving positions no longer reflects the June entry.
Only two June entries are untouched: INTC 115/130 (avg 9.3576/15.9720 vs fills
9.35/15.98) at −$793, and NVDA Jun17'27 220C (avg 38.5614 vs fill 38.55) at
−$346. SMH, TSM and MU were all re-struck in July and their marks are NOT June
attribution. Likewise the +$4,966 realized inside June is mostly the 06-22 TSM
close (+$6,159) of an APRIL entry — it is not a June-selection result.

### 6. Actions

- **No rule change.** Nothing here clears a promotion bar.
- **Blocked:** the v1/v2/v3 question cannot be answered from these exports.
  Re-running v1+v2 analysis rows through the current engine is the only clean
  path; until then, treat "v3 is better" as unevidenced in either direction.
- **New watch:** v3 <180d real+tweak book is negative on common dates while
  >=180d carries all the dollars. Check this again on the full v3 window.
- **bear_put:** third sighting, now cross-version. Strengthens the standing
  DEMOTE candidate.
- **Live process:** June ran on v1/v2 prompts with no `score_total`, so the
  ladder was untested in live use. The first genuine live-vs-tier eval needs a
  month where the traded book and a scored analysis tab overlap — July is the
  first candidate (198 v3 rows).

---

## 2026-08-12 (same day, second run) — Stage 1 live-vs-tier eval on July

Follow-up to the section above: July was the first month where the traded book
overlaps a scored v3 analysis tab, so the live-vs-tier eval was finally runnable.
Re-ran `scripts/live_loop/stage1_map_fills.py` on a fresh **2026-08-12** IBKR
snapshot (206 trades vs the old snapshot's 53; 19 open option positions vs 17).

### 0. Four code fixes the wider snapshot forced

The module had only ever seen a 53-trade window. Widening it broke it:

1. **Crash on a non-business-day fill.** `np.busday_offset(fill, -1)` raises on a
   weekend date; IBKR stamped two rows 2026-08-08 (Saturday). Now
   `roll="forward"`, so a Saturday fill resolves to the prior Friday.
2. **Zero-price settlement rows became phantom entries.** A `price == 0` /
   `realized_pnl == 0` row is expiry/assignment bookkeeping, not a fill. They are
   now dropped before entry reconstruction and reported in the header. Zero-price
   rows WITH realized_pnl stay in the closing ledger — those are real expiry P&L.
3. **NONE reasons were collapsed into one misleading label.** Every unmapped
   entry rendered as "no same-ticker play", which reads as "the analysis never
   covered this". False for 21 of them — see §2. Now split four ways.
4. **Snapshot path was hardcoded**; now defaults to the newest
   `ibkr_snapshot_*.json`, with `--snapshot` to re-run an older one, and the
   report name carries the snapshot date so re-runs never clobber.

Two assertions in the generated caveats were also stale and are now computed
rather than asserted.

### 1. The July result — selection compliance

Pooling the mapped entries from BOTH snapshots (see §2 for why pooling is
mandatory) gives **8 mapped live entries**, 2026-07-14 → 2026-08-10:

    signal date  tkr   live structure       confidence    tier   top avail
    2026-07-14   TSM   bull_put_spread      STRUCTURE     VETO   C
    2026-07-16   META  single short put     SUBSTITUTED   VETO   A
    2026-07-17   QQQ   bear_put_spread      STRUCTURE     C      C
    2026-07-28   SMH   bear_put_spread      STRUCTURE     C      A
    2026-07-30   HYG   single long put      SUBSTITUTED   C      C
    2026-08-04   IWM   bear_put_spread      EXACT         C      B
    2026-08-05   TSM   bull_call_spread     STRUCTURE     B      B
    2026-08-07   GLD   bull_call_spread     STRUCTURE     B      B

**4 of 8 were in the top available tier. 2 landed in a VETO cell. Zero Tier-A
plays were ever deployed** — including 07-16 and 07-28, where an A was on the
board and a VETO / C was taken instead.

Both VETO hits are the same cell: **a credit play in RANGE + L-VOL**. That is one
rule, violated twice, and it is the single highest-value thing to fix in live
process. Note 07-16 META is also a SUBSTITUTED row — a naked short put where a
bull_put_spread 620/580 was emitted — so it violates the veto by a route the
analysis never proposed.

### 2. Methodological finding — mapping decays, snapshots are not supersets

Contract identity is inferred by joining a fill price to an open-position
`average_price`; the trades payload has no strike/expiry/right. **Once a
round-trip closes, its identity is unrecoverable.** So the 2026-07-22 snapshot
maps the 07-15 TSM bull_put and 07-20 QQQ bear_put that the 2026-08-12 snapshot
reads as UNKNOWN — those positions have since closed.

**A later snapshot is not a superset of an earlier one.** On the 08-12 snapshot,
21 of 59 unmapped entries fall on dates that DID carry a same-ticker play but
whose live structure could no longer be resolved. Snapshots must be taken on a
regular cadence and their mapped sets pooled. Both facts are now written into
the module's caveats so the next run cannot forget them.

This also relocates the Stage-2 bottleneck. Closed round-trips are no longer
scarce (54, vs the ~30–50 threshold) — **mappability** is the constraint: only 8
entries map at all, across two snapshots.

### 3. P&L, with the attribution caveat that matters

The June audit could not attribute P&L because July rolls had moved every
`average_price` off its entry fill. For the mapped entries this problem solves
itself: **the price-join only matches when `average_price` ≈ the entry fill, so
mapped-and-open entries are by construction un-rolled.** All six open mapped
entries check out (largest gap $0.011/share). Unrealized, as of 2026-08-12:

    tier B     n=2    -$65     (GLD +82, TSM -146)
    tier C     n=3   -$733     (IWM -28, HYG -29, SMH -676)
    tier VETO  n=1   +$726     (META)
    ALL        n=6    -$72

**This does not validate or refute the ladder** and must not be quoted as
evidence: n=6, all unrealized marks on open positions, no exits taken, and the
single VETO row is the best performer. It is recorded so the next snapshot has a
baseline to move against. The ordering is currently the reverse of what the
ladder predicts, on a sample far too small to mean anything.

### 4. Actions

- **No rule change.** n=8 mapped entries decides nothing.
- **Live process, actionable now:** the RANGE + L-VOL credit veto was breached
  twice, and Tier A was passed over twice when available. Both are checkable off
  the analysis row on a deploy morning at zero cost.
- **Snapshot cadence:** take an IBKR snapshot at least fortnightly, keep every
  one, pool the mapped sets. Mappings are lost permanently otherwise.
- **Next gate:** Stage 2 needs mapped entries, not fills. At the current rate
  (~8 per 4 weeks of overlap) a 30-entry mapped book is roughly 3–4 months out —
  unless snapshot cadence rises, which directly raises the mapping yield.
