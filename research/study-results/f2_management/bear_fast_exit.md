# bear_fast_exit — per-era record

**Question.** Does a bear debit closed within a few sessions, or at a small profit, pay net of trading costs, and does it beat the shipped bear-debit exit?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha 4699bd9 — recorded 2026-10-10
<!-- key era=v4 sha=4699bd9 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-09 22:58:53 · git 4699bd9 (worktree-wf_c8ce3d2e-793-4, working tree clean) · exit 0 · 366.5s
command     python -m scripts.backtest_study.f2_management.bear_fast_exit
excerpt     verdict

```
VERDICT
--- criteria — HEADLINE -----------------------------------------------------
  arm                     C1  C2  C3  C4 C5 lvl C6 lvl  C5 Δ  C6 Δ       C7
  TP 0.10                 no  no yes  no     no     no   yes   yes  PENDING
  TP 0.20                 no  no yes  no     no     no   yes    no  PENDING
  TP 0.30                 no  no yes  no     no     no   yes    no  PENDING
  TS 1                    no  no yes yes     no     no   yes   yes  PENDING
  TS 2                    no  no yes  no     no     no   yes   yes  PENDING
  TS 3                    no  no yes  no     no     no   yes   yes  PENDING
  TS 5                    no  no yes  no     no     no   yes   yes  PENDING
  OP 0.25 or session 5    no  no yes  no     no     no   yes   yes  PENDING
  VERDICT (headline, $0.65/contract, slippage 0): BLEED-CUT (C7 PENDING)
    TS 1
--- criteria — SECONDARY ----------------------------------------------------
  arm                     C1  C2  C3  C4 C5 lvl C6 lvl  C5 Δ  C6 Δ       C7
  TP 0.10                 no  no yes  no     no     no   yes   yes  PENDING
  TP 0.20                 no  no yes  no     no     no   yes    no  PENDING
  TP 0.30                 no  no yes  no     no     no   yes    no  PENDING
  TS 1                    no  no yes yes     no     no   yes   yes  PENDING
  TS 2                    no  no yes  no     no     no   yes   yes  PENDING
  TS 3                    no  no yes  no     no     no   yes   yes  PENDING
  TS 5                    no  no yes  no     no     no   yes   yes  PENDING
  OP 0.25 or session 5    no  no yes  no     no     no   yes   yes  PENDING
  VERDICT (secondary, + 0.25 of spread, declared): BLEED-CUT (C7 PENDING)
    TS 1
  C7 FORWARD is PENDING: a registration accepted on or after 2026-10-09 is not a
  sealed reader, so its forward window opens only when the holdout seal lifts
  (floor 15 dates and 30 rows). A pending C7 ships nothing.
```

