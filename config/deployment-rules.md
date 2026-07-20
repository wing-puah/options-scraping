# Deployment rules — which analysis plays get real capital

Derived 2026-07-19 from the 607-row pooled book (see
`config/backtest-tuning.md` §"2026-07-19 — Deployment ladder"). The analysis
emits a median 10 plays/day; live capital supports 1–3 positions. This is the
operator checklist for choosing which plays to actually deploy. Every rule
below is a ≥2-snapshot-confirmed backtest finding — nothing here is a fresh
single-read cut except where marked PROVISIONAL.

## Preconditions (apply to every deployed play)

- Entry basis: **next trading day's OPEN** (the backtest's entry basis since
  2026-07-06 — same-day fills were never modeled).
- Exit config: the PROD profile — debit pt 0.90, no trailing stop; credit
  pt 0.65, **no stop-loss** (Attempt 13), structural sizing on credits
  (risk defined by wing width, not a stop).
- `score_total` is only meaningful on rows emitted after 2026-07-13 (the 13c
  rubric fix). All live rows qualify; never mix in older rows when ranking.

## Step 1 — Vetoes (never deploy, regardless of score)

1. **bear_call_spread** — intake-vetoed since Attempt 13; if one ever appears
   it is a pipeline bug, not a trade.
2. **Any play when the market regime is BEAR + H-VOL** — n=47, 30% win,
   mean −0.34; worst cell in every snapshot since 07-12.
3. **Any credit play when the regime is RANGE + L-VOL** — n=20, mean −0.49.

Vetoed rows lost −$21k on the pooled book (n=96, 38% win). The vetoes are the
most reliable part of this ladder.

## Step 2 — Tier the survivors

- **Tier A — deploy first**: `bull_call_spread` when the regime is RANGE or
  E-VOL, or its `score_total` ≥ 70.
  (pooled n=132, 61% win, mean +0.51; real-priced +0.60)
- **Tier B — deploy if capital remains**:
  - other `bull_call_spread`;
  - `bull_put_spread` with short-leg **|delta| ≥ 0.12 AND DTE ≤ 59**
    (PROVISIONAL median-split cuts — direction 3×-confirmed, exact numbers
    pending the ≥800-row derivation; the joint cell wins 88% at n=26, vs 59%
    win / −0.15 mean when both are violated). Check delta/DTE at order entry
    in IBKR, they are not on the analysis row;
  - any other debit structure with `score_total` ≥ 70.
  (pooled n=117, 63% win, mean +0.27)
- **Tier C — skip when capital-constrained**: `bear_put_spread` with
  `iv_spread` > 0 (3×-confirmed MAE penalty), low-delta/long-DTE bull_puts,
  everything else. (pooled n=262, 51% win, mean +0.09 — dead money, not
  poison; fine to paper-track.)
- Tie-break **within** a tier: higher `score_total` (post-13c bands are
  monotone: 70+ → 70% win, 40–69 → 57%, <40 → 54%).

## Validation (2026-07-19 book)

- Tier means monotone pooled AND real-priced AND in both time halves
  (H1 ≤ 2025-03-17 < H2): A > B > C > VETO ordering never inverts.
- Capped-selection replay (score-free tie-break): top-1/day mean +0.82,
  top-2 +0.51, top-3 +0.45 vs +0.14 take-everything. **Top-3/day = 28% of
  positions, 83% of book P&L (+$88k of +$106k).**
- Post-13c-only dates, score tie-break: top-1/day 82% win (n=17, small).

## Caveats + revision triggers

- Tier A partly encodes the RANGE/E-VOL cell that drove the book's profit —
  in-sample circularity is mitigated by the time-split, not eliminated.
- The bull_put 0.12/59 cuts are provisional; re-derive at ≥800 pooled rows.
- Post-13c sample shows B ≥ A (n=23 vs 58) — small-n; if A < B persists at
  ≥800, re-order or merge the tiers.
- Re-validate the whole ladder at the ≥800-row run before treating it as
  more than a triage heuristic.
