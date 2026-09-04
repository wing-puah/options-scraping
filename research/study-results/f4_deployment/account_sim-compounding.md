# account_sim-compounding — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:47:27 · git 53b7167 (main, working tree dirty) · exit 0 · 3.8s
command     python -m scripts.backtest_study.f4_deployment.account_sim --compounding
excerpt     verdict

```
VERDICT (PRIMARY dense episodes population — the primary)
  A1  MET
  A2  MET
  A3  MET
  A4  MET
  A5  NOT MET
  A6  NOT MET
  >>> FEASIBILITY NOT CONFIRMED (A1-A3 hold; A5 and/or A6 fail; stability/robustness not established on this window) <<<
  2026-08-14 AMENDMENT (labelled, not a redefinition — see the comment above
  print_verdict): the pre-registered grammar (FEASIBLE = A1^A2^A3^A5^A6;
  FEASIBLE-BUT-DEGRADED = A1^A3 with A2 failing; NOT FEASIBLE AT $25,000 = A1 fails)
  did not name this combination and previously printed "NO VERDICT MATCHES"
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:16:47 · git d47e227 (main, working tree dirty) · exit 0 · 3.6s
command     python -m scripts.backtest_study.f4_deployment.account_sim --compounding
excerpt     verdict

```
VERDICT (PRIMARY dense episodes population — the primary)
  A1  MET
  A2  MET
  A3  MET
  A4  MET
  A5  MET
  A6  MET
  >>> FEASIBLE <<<
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:23:03 · git c841a01 (main, working tree dirty) · exit 0 · 2.3s
command     python -m scripts.backtest_study.f4_deployment.account_sim --compounding
excerpt     verdict

```
VERDICT (PRIMARY dense episodes population — the primary)
  A1  MET
  A2  MET
  A3  MET
  A4  MET
  A5  MET
  A6  MET
  >>> FEASIBLE <<<
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:42:43 · git 25f3e27 (main, working tree dirty) · exit 0 · 3.2s
command     python -m scripts.backtest_study.f4_deployment.account_sim --compounding
excerpt     verdict

```
VERDICT (PRIMARY dense episodes population — the primary)
  A1  MET
  A2  MET
  A3  NOT MET
  A4  MET
  A5  MET
  A6  MET
  >>> NOT FEASIBLE AT $25,000 — BLOWUP RISK (A1 holds, A3 fails) <<<
  2026-08-14 AMENDMENT (labelled, not a redefinition — see the comment above
  print_verdict): the pre-registered grammar (FEASIBLE = A1^A2^A3^A5^A6;
  FEASIBLE-BUT-DEGRADED = A1^A3 with A2 failing; NOT FEASIBLE AT $25,000 = A1 fails)
  did not name this combination and previously printed "NO VERDICT MATCHES"
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:44:45 · git e59356f (main, working tree dirty) · exit 0 · 3.1s
command     python -m scripts.backtest_study.f4_deployment.account_sim --compounding
excerpt     verdict

```
VERDICT (PRIMARY dense episodes population — the primary)
  A1  MET
  A2  MET
  A3  NOT MET
  A4  MET
  A5  MET
  A6  MET
  >>> NOT FEASIBLE AT $25,000 — BLOWUP RISK (A1 holds, A3 fails) <<<
  2026-08-14 AMENDMENT (labelled, not a redefinition — see the comment above
  print_verdict): the pre-registered grammar (FEASIBLE = A1^A2^A3^A5^A6;
  FEASIBLE-BUT-DEGRADED = A1^A3 with A2 failing; NOT FEASIBLE AT $25,000 = A1 fails)
  did not name this combination and previously printed "NO VERDICT MATCHES"
```


## era v4 · inputs 1b1ba3c · sha b007f95 — recorded 2026-09-04
<!-- key era=v4 sha=b007f95 inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 22:26:47 · git b007f95 (main, working tree clean) · exit 0 · 5.5s
command     python -m scripts.backtest_study.f4_deployment.account_sim --compounding
excerpt     verdict

```
VERDICT (PRIMARY dense episodes population — the primary)
  A1  MET
  A2  MET
  A3  NOT MET
  A4  MET
  A5  MET
  A6  MET
  >>> NOT FEASIBLE AT $25,000 — BLOWUP RISK (A1 holds, A3 fails) <<<
  2026-08-14 AMENDMENT (labelled, not a redefinition — see the comment above
  print_verdict): the pre-registered grammar (FEASIBLE = A1^A2^A3^A5^A6;
  FEASIBLE-BUT-DEGRADED = A1^A3 with A2 failing; NOT FEASIBLE AT $25,000 = A1 fails)
  did not name this combination and previously printed "NO VERDICT MATCHES"
```

