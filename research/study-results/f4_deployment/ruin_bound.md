# ruin_bound — per-era record

**Question.** The operator will accept a deeper drawdown for more return if a guardrail prevents ruin. Among six cap cells x four guardrails, which earns the most while P(ruin of half the account), the p95 and p99 marked drawdown and a total-loss day stay under bounds fixed first? $500 headline, $1,000 declared secondary.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 27a655c · sha 167f963 — recorded 2026-10-10
<!-- key era=v4 sha=167f963 inputs=27a655c -->

population  1,020 results · 2,021 proxy · 3,417 analysis  (inputs dated 2026-10-06 23:39)
run         2026-10-09 23:51:40 · git 167f963 (worktree-wf_c8ce3d2e-793-5, working tree dirty) · exit 0 · 621.1s
command     python -m scripts.backtest_study.f4_deployment.ruin_bound
missing     backtests/mech_regime/spy_vix_daily_full.csv
excerpt     verdict

```
VERDICT
  HEADLINE ($500 budget and stop): >>> SAFEST ELIGIBLE CELL: N250-F2 G-none <<<
  DECLARED SECONDARY ($1,000 budget and stop): NO CELL MEETS THE BOUNDS
  A reading for the operator. The tracked cap in config/account-sim.yml
  is unchanged whatever these lines say.
  run time 620s
```

