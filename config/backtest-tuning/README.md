# Backtest exit rule tuning log

Running log of parameter experiments — what worked, what didn't, and why.
Original dataset: 119 trades across July 2024 (chop), Jan 2025 (bull), March 2025
(panic/correction), Feb 2026; later evaluations run on the pooled real + proxy book.

**Newest work lives in [`current.md`](current.md).** Everything older is split by
period under [`archive/`](archive/). Append new entries to `current.md`; when it
grows past ~400 lines, move its oldest sections into a new archive file and add a
row to the index below.

## Section index

| Section | File |
|---------|------|
| Baseline | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 1 — WORSE ❌ | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 2 — WORSE ❌ | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 3 — BETTER, exit config now stable ✓ | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 4 — WORSE ❌ (trailing-on-profit-target) | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 5 — IDENTICAL ❌ | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 6 — BETTER ✓ (profit_target 0.60) | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Rules of thumb learned so far | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| What actually drives losses — confidence, not regime | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| The real next step: confidence-based position sizing | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Financing & IVSpread gates (2026-06-19) | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 7 — BETTER ✓ (profit_target=0.90 + trailing stop) | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 8 — Credit/debit split (2026-07-04) | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Attempt 9 — underlying-price exit study for credits ❌ | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Attempt 10 — BETTER ✓ (debit trailing stop removed) | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Attempt 11 — credit re-check on 18 rows ❌ | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Proxy backtest for untested plays (2026-07-06) | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Entry basis changed: EOD → next-day OPEN (2026-07-06) | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Attempt 12 — next_open re-baseline + grouped exit study | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| 2026-07-08 — Framework evaluation on MFE/MAE basis | [archive/03](archive/03-evaluations-attempt-13.md) |
| 2026-07-12 — Three-run evaluation (v1 / v2 / v3) | [archive/03](archive/03-evaluations-attempt-13.md) |
| Attempt 13 — bear_call vetoed + credit stop removed ✓ | [archive/03](archive/03-evaluations-attempt-13.md) |
| 2026-07-17 — Power check; scoring-column keep/drop | [archive/03](archive/03-evaluations-attempt-13.md) |
| 2026-07-19 — Final evaluation at 607 pooled rows | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-18 — Early pooled power check at 523 rows | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-19 — Deployment ladder (`config/deployment-rules.md`) | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-20 — Next-25 backtest dates: regime-gap selection | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-21 — ≥800-GATE EVALUATION at 762 pooled priced rows | [current.md](current.md) |
| 2026-07-21 — Edge status: honest assessment + priority queue | [current.md](current.md) |
| 2026-07-21 — Regime-label validation: 86 MARKET rows | [current.md](current.md) |
