# hedge_concentration — per-era record

**Question.** On the ADMITTED book — the positions account_sim actually takes under the operator's top-3-per-day rule and exposure caps — does a session's cluster concentration PREDICT the book's subsequent mark-to-market drawdown, and only then does a proxy put on that cluster cut it?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs ef2016f · sha 9834563 — recorded 2026-08-31
<!-- key era=v4 sha=9834563 inputs=ef2016f -->

population  485 results · 1,111 proxy · 1,893 analysis · 815 spy_vix_daily_full  (inputs dated 2026-08-27 20:34 … 2026-08-29 14:01)
run         2026-08-31 22:24:48 · git 9834563 (main, working tree dirty) · exit 0 · 23.2s
command     python -m scripts.backtest_study.f4_deployment.hedge_concentration
excerpt     matched

```
  VERDICT — Stage 1 (ARM K, the precondition): PRECONDITION-NULL
  VERDICT — Stage 1 (ARM K, the precondition): PRECONDITION-NULL
  VERDICT — Stage 2 (ARM C, the mechanism): NOT RUN (Stage 1 PRECONDITION-NULL)
```

