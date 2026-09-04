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


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:23:05 · git c841a01 (main, working tree dirty) · exit 0 · 7.4s
command     python -m scripts.backtest_study.f4_deployment.bear_deploy
excerpt     verdict

```
VERDICT (pre-registered rules, ml-plan.md §addendum 2)
  D1 joint selection x exit : NOT MET
  D2 hedge is real          : NOT MET
  D3 always-on sizing       : NOT MET at any size
  D4 conditional pick       : NOT MET
  D5 gated sleeve (POST-HOC): no gate survives
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:42:46 · git 25f3e27 (main, working tree dirty) · exit 0 · 13.4s
command     python -m scripts.backtest_study.f4_deployment.bear_deploy
excerpt     verdict

```
VERDICT (pre-registered rules, pre-registrations/f4_deployment/bear_deploy.md)
  D1 joint selection x exit : NOT MET
  D2 hedge is real          : NOT MET
  D3 always-on sizing       : NOT MET at any size
  D4 conditional pick       : NOT MET
  D5 gated sleeve (POST-HOC): 8 candidate gate(s)
```


## era v4 · inputs ef2016f · sha 665956d — recorded 2026-09-04
<!-- key era=v4 sha=665956d inputs=ef2016f -->

population  485 results · 1,111 proxy · 1,893 analysis · 815 spy_vix_daily_full  (inputs dated 2026-08-27 20:34 … 2026-08-29 14:01)
run         2026-08-29 16:34:03 · git 665956d (main, working tree dirty) · exit 0 · 22.1s
command     python -m scripts.backtest_study.f4_deployment.bear_deploy
excerpt     verdict

```
VERDICT (pre-registered rules, pre-registrations/f4_deployment/bear_deploy.md)
  D1 joint selection x exit : NOT MET
  D2 hedge is real          : NOT MET
  D3 always-on sizing       : NOT MET at any size
  D4 conditional pick       : NOT MET
  D5 gated sleeve (POST-HOC): 8 candidate gate(s)
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:44:48 · git e59356f (main, working tree dirty) · exit 0 · 14.7s
command     python -m scripts.backtest_study.f4_deployment.bear_deploy
excerpt     verdict

```
VERDICT (pre-registered rules, pre-registrations/f4_deployment/bear_deploy.md)
  D1 joint selection x exit : NOT MET
  D2 hedge is real          : NOT MET
  D3 always-on sizing       : NOT MET at any size
  D4 conditional pick       : NOT MET
  D5 gated sleeve (POST-HOC): 2 candidate gate(s)
```

