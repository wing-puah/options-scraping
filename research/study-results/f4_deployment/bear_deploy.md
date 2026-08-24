# bear_deploy — per-era record

**Question.** Bear selection is unfixable — but is bear worth holding as a HEDGE? Four estimands: D1 joint selection×exit, D2 hedge contribution, D3 sizing, D4 conditional pick.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:47:31 · git 53b7167 (main, working tree dirty) · exit 0 · 19.4s
command     python -m scripts.backtest_study.f4_deployment.bear_deploy
excerpt     verdict

```
VERDICT (pre-registered rules, ml-plan.md §addendum 2)
  D1 joint selection x exit : NOT MET
  D2 hedge is real          : MET
  D3 always-on sizing       : NOT MET at any size
  D4 conditional pick       : adopted — |delta| high first
  D5 gated sleeve (POST-HOC): 4 candidate gate(s)
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:13:59 · git d47e227 (main, working tree dirty) · exit 0 · 10.4s
command     python -m scripts.backtest_study.f4_deployment.bear_deploy
excerpt     verdict

```
VERDICT (pre-registered rules, ml-plan.md §addendum 2)
  D1 joint selection x exit : NOT MET
  D2 hedge is real          : MET
  D3 always-on sizing       : MET
  D4 conditional pick       : NOT MET
  D5 gated sleeve (POST-HOC): 2 candidate gate(s)
```

