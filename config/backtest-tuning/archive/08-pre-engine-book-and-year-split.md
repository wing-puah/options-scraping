# Archive 08 — pre-engine discretionary book, year-split evaluation

Covers 2026-07-27 (the pre-engine discretionary book and the long-dated
blind spot) and 2026-08-08 (the year-split evaluation on refreshed
exports: 2025 as the outlier year).
See [../README.md](../README.md) for the full section index.

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

