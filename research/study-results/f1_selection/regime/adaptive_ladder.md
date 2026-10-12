# adaptive_ladder — per-era record

**Question.** Does a fixed procedure that re-picks one of six selection rules from trailing results known before each monthly rebalance beat the shipped ladder (M0), walk-forward, in R per budget slot per date?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha f59b776 — recorded 2026-10-12
<!-- key era=v4 sha=f59b776 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-12 20:41:50 · git f59b776 (main, working tree dirty) · exit 0 · 2.3s
command     python -m scripts.backtest_study.f1_selection.regime.adaptive_ladder
excerpt     verdict

```
VERDICT
  >>> adaptive_ladder WALK-FORWARD (in-sample dates, v4, adapter - M0): ADAPTS <<<
  oracle (hindsight): M5; switches 1; PBO 0.161
  >>> adaptive_ladder FORWARD (adapter - M0): STILL-OPEN <<<
  The forward verdict of record is the first run printing a token other than STILL-OPEN.
  Nothing ships from this study. An ADAPTS lets the operator consider a deployment-rules change.
```

