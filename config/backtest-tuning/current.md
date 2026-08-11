# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index.

**State of play (2026-08-08).** Year-split eval on the refreshed exports (below):
the raw book's profit is 2025H1-only, but the ladder separation reproduces in
2024/2025/2026 independently; bear_put DEMOTE criteria fire on the near-complete
2026 holdout (7 dates still to backfill). Shipped config is the source of truth —
`config/backtest.yml` (exits, `regime_exit.cells: BEAR_HE` only) and
`config/deployment-rules.md` (VETO / A / B / C ladder, top-3 per day,
bull_put band `0.08 ≤ |delta| ≤ 0.20` + `DTE ≤ 59`). The 25-date regime-gap
gate is CLOSED (archive/06). Open questions: (1) **bear_put** — the
pre-registered study returned DEMOTE, the verdict is deliberately *not*
implemented, and it now waits on the Feb–Apr 2026 holdout below; (2) **the
long-dated blind spot** — the ladder is in practice a ≤60-DTE ladder because
h≥180 plays cannot be priced (2026-07-27 below); (3) **live substitution** —
the operator sometimes trades naked where the engine emitted a spread, which
breaks the live walk-forward's attribution.

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
substitutions are silently dropped from the eval rather than labelled. Adding a
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
6. Re-run `backtests/bear_position_study.py` **unmodified** against the
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
