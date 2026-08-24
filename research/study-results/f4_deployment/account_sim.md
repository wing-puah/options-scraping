# account_sim — per-era record

**Question.** The ladder assumes infinite capital. Does a real $25,000 account — paying for positions, holding reserve, respecting a delta cap — still produce a book?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:47:23 · git 53b7167 (main, working tree dirty) · exit 0 · 3.7s
command     python -m scripts.backtest_study.f4_deployment.account_sim
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
run         2026-08-22 18:16:43 · git d47e227 (main, working tree dirty) · exit 0 · 3.4s
command     python -m scripts.backtest_study.f4_deployment.account_sim
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

