# Deployment rules — which analysis plays get real capital

Derived 2026-07-19 from the 607-row pooled book; **re-validated 2026-07-21
at the ≥800 gate** (762 pooled priced rows — tier ordering monotone in every
cut incl. post-13c-only; see `config/backtest-tuning.md` §"2026-07-21 —
≥800-gate evaluation"). The analysis
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
  E-VOL. (pooled n=147, 67% win, mean +0.64; real-priced +0.77)
- **Tier B — deploy if capital remains**:
  - other `bull_call_spread`;
  - `bull_put_spread` with short-leg **0.08 ≤ |delta| ≤ 0.20 AND DTE ≤ 59,
    prefer 45–59 DTE** (derived at the ≥800 gate, n=118 real-priced: the
    qualifying |d|≥0.08/DTE≤59 cell is 80% win / +0.25 mean vs 60% / −0.08
    violated, and holds post-13c at +0.15/80%. Delta is a BAND: >0.20 runs
    −0.39 and <0.08 runs −0.28; DTE 45–59 carries the whole edge (+0.47,
    87% win) while ≤22 produced the post-13c dollar_stop losers. The ≤0.20
    cap and 45-DTE preference are thin-n — PROVISIONAL). Check delta/DTE at
    order entry in IBKR, they are not on the analysis row.
  (pooled n=168, 60% win, mean +0.28)
- **Tier C — skip when capital-constrained**: `bear_put_spread` with
  `iv_spread` > 0 (3×-confirmed MAE penalty), low-delta/long-DTE bull_puts,
  everything else. (pooled n=262, 51% win, mean +0.09 — dead money, not
  poison; fine to paper-track.)
- Tie-break **within** a tier: higher `score_total` — a deterministic
  ordering only, it carries no signal (replay ≈ random tie-break).

> **Note (2026-07-21):** two former `score_total` ≥ 70 membership clauses
> (bull_call → A; any other debit → B) were removed after marginal-value
> tests — the first promoted rows that perform like Tier B, the second was
> a bear_put leak. Tier membership is now structure × regime ×
> entry-geometry only. Details: backtest-tuning.md §2026-07-21 addendum.

## Validation (2026-07-21, 762 pooled priced rows — the ≥800-gate run)

Numbers below are for the score-free ladder (post-clause-removal).

- Tier means monotone pooled (+0.64/+0.28/−0.02/−0.39), real-priced
  (+0.77/+0.31/−0.01/−0.45), pre-13c, post-13c, and both time halves:
  A > B > C > VETO never inverts.
- Post-13c-only: A vs C MWU p=.0001, B vs C p<.0001 (A vs B ordered but
  not separated: +0.50 vs +0.40, p=.98 — watch item stays open).
- Post-13c capped replay: top-1/day 76% win / +0.35 mean; top-3/day 69%
  win, $30.3k from 97 rows — better than the with-score-clauses ladder
  ($19.1k, 61% win) on the same dates.
- 2026-07-19 book (607 rows, derivation sample): top-1/day +0.82, top-3
  +0.45 vs +0.14 take-everything; top-3/day = 28% of positions, 83% of
  book P&L.

## Caveats + revision triggers

- Tier A partly encodes the RANGE/E-VOL cell that drove the book's profit —
  in-sample circularity is mitigated by the time-split + post-13c holdout,
  not eliminated.
- The bull_put delta ≤0.20 cap and 45–59-DTE preference are thin-n
  (PROVISIONAL); re-read after the 25 regime-gap dates land.
- The ladder is validated as a triage rule on backtest data; it has never
  been walked forward live.
