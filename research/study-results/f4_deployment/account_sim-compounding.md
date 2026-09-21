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


## era v4 · inputs 271c4b5 · sha 8e9b6a7 — recorded 2026-09-20
<!-- key era=v4 sha=8e9b6a7 inputs=271c4b5 -->

population  598 results · 1,665 proxy · 2,781 analysis · 827 spy_vix_daily_full  (inputs dated 2026-09-16 11:32 … 2026-09-19 16:45)
run         2026-09-19 23:50:29 · git 8e9b6a7 (main, working tree clean) · exit 0 · 6.0s
command     python -m scripts.backtest_study.f4_deployment.account_sim --compounding
excerpt     verdict

```
VERDICT (PRIMARY dense episodes population — the primary)
  A1  MET
  A2  MET
  A3  NOT MET
  A4  MET
  A5  NOT MET
  A6  MET
  >>> NOT FEASIBLE AT $25,000 — BLOWUP RISK (A1 holds, A3 fails) <<<
  2026-08-14 AMENDMENT (labelled, not a redefinition — see the comment above
  print_verdict): the pre-registered grammar (FEASIBLE = A1^A2^A3^A5^A6;
  FEASIBLE-BUT-DEGRADED = A1^A3 with A2 failing; NOT FEASIBLE AT $25,000 = A1 fails)
  did not name this combination and previously printed "NO VERDICT MATCHES"
```


## era v4 · inputs 271c4b5 · sha 1c163c5 — recorded 2026-09-20
<!-- key era=v4 sha=1c163c5 inputs=271c4b5 -->

population  598 results · 1,665 proxy · 2,781 analysis · 827 spy_vix_daily_full  (inputs dated 2026-09-16 11:32 … 2026-09-19 16:45)
run         2026-09-20 12:15:53 · git 1c163c5 (main, working tree clean) · exit 0 · 9.7s
command     python -m scripts.backtest_study.f4_deployment.account_sim --compounding
excerpt     verdict

```
CAPITAL LADDER — operator note, printed because the verdict is NOT FEASIBLE
  Same anti-tuning rule: this is the smallest capital in {$25k, $35k, $50k} at
  which A1 AND A2 pass, not a recommendation to trade any of them. A rung whose
  dollar stop does not divide the frozen $1,000 harness stop evenly (e.g. $700
  on a $35k rung at 2%) is rounded UP to a TIGHTER stop, the conservative
  direction, and the affected position count is printed.
  The maxDD and A3 columns and the A3 summary line below are DISCLOSED
  ADDITIONS (2026-09-20), not part of the registered operator note: the
  registration names A1 AND A2 only, and a verdict can be NOT FEASIBLE on A3
  alone. No threshold moved — A3 here is `a3_no_blowup`, the clause
  `evaluate()` scores, measured against the RUNG's capital. Read a rung that
  passes A1 AND A2 while failing A3 as an account size that keeps the edge and
  still breaches the drawdown bar, never as a feasible one.
  $ 25,000  n= 253  $    35,233  meanR +0.281 CI-lo +0.170  attrition  204%  maxDD 34.2%  A1 MET  A2 MET  A3 no   [241 inexact-stop positions]
  $ 35,000  n= 266  $    28,010  meanR +0.241 CI-lo +0.129  attrition  109%  maxDD 31.0%  A1 MET  A2 MET  A3 no   [265 inexact-stop positions]
  $ 50,000  n= 276  $    63,442  meanR +0.285 CI-lo +0.157  attrition   94%  maxDD 24.3%  A1 MET  A2 MET  A3 MET
  smallest capital passing A1 AND A2: $25,000
  smallest capital passing A1 AND A2 AND A3 (disclosed addition): $50,000
```

