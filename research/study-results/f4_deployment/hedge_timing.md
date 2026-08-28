# hedge_timing — per-era record

**Question.** The bear hedge sleeve is deployed on discretionary triggers — chop, a SPY gap-up, a 4-5-day SPY down-run. Does any of them, made mechanical, pick a day on which the hedge earns more than the SAME day's ladder-eligible long?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 3c7de59 · sha 1d9b40c — recorded 2026-08-28
<!-- key era=v4 sha=1d9b40c inputs=3c7de59 -->

population  485 results · 1,111 proxy · 1,893 analysis · 814 spy_vix_daily_full  (inputs dated 2026-08-27 20:34 … 2026-08-28 10:40)
run         2026-08-28 11:41:06 · git 1d9b40c (main, working tree dirty) · exit 0 · 11.7s
command     python -m scripts.backtest_study.f4_deployment.hedge_timing
excerpt     verdict

```
VERDICT (pre-registered grammar, pre-registrations/f4_deployment/hedge_timing.md)
  ARM H1-CHOP        : NULL
  ARM H3-CHOP        : NULL
  ARM H4-CHOP        : UNSTABLE
  ARM H2-CHOP        : NULL   (control, not a headline)
  ARM H1-GAP         : NULL
  ARM H3-GAP         : CONTRARY
  ARM H4-GAP         : CONTRARY
  ARM H2-GAP         : NULL   (control, not a headline)
  ARM H1-DECLINE     : NULL
  ARM H3-DECLINE     : NULL
  ARM H4-DECLINE     : UNSTABLE
```


## era v3 · inputs aadab56 · sha 1d9b40c — recorded 2026-08-28
<!-- key era=v3 sha=1d9b40c inputs=aadab56 -->

population  406 results · 796 proxy · 1,607 analysis · 814 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-08-28 10:40)
run         2026-08-28 11:41:54 · git 1d9b40c (main, working tree dirty) · exit 0 · 8.9s
command     python -m scripts.backtest_study.f4_deployment.hedge_timing
excerpt     verdict

```
VERDICT (pre-registered grammar, pre-registrations/f4_deployment/hedge_timing.md)
  ARM H1-CHOP        : NULL
  ARM H3-CHOP        : NULL
  ARM H4-CHOP        : NULL
  ARM H2-CHOP        : NULL   (control, not a headline)
  ARM H1-GAP         : NULL
  ARM H3-GAP         : UNDERPOWERED
  ARM H4-GAP         : NULL
  ARM H2-GAP         : NULL   (control, not a headline)
  ARM H1-DECLINE     : NULL
  ARM H3-DECLINE     : NULL
  ARM H4-DECLINE     : NULL
```


## era v4 · inputs 3c7de59 · sha 1fe4923 — recorded 2026-08-28
<!-- key era=v4 sha=1fe4923 inputs=3c7de59 -->

population  485 results · 1,111 proxy · 1,893 analysis · 814 spy_vix_daily_full  (inputs dated 2026-08-27 20:34 … 2026-08-28 10:40)
run         2026-08-28 11:54:06 · git 1fe4923 (main, working tree dirty) · exit 0 · 4.4s
command     python -m scripts.backtest_study.f4_deployment.hedge_timing
excerpt     verdict

```
VERDICT (pre-registered grammar, pre-registrations/f4_deployment/hedge_timing.md)
  ARM H1-CHOP        : NULL
  ARM H3-CHOP        : NULL
  ARM H4-CHOP        : UNSTABLE
  ARM H2-CHOP        : NULL   (control, not a headline)
  ARM H1-GAP         : NULL
  ARM H3-GAP         : CONTRARY
  ARM H4-GAP         : CONTRARY
  ARM H2-GAP         : NULL   (control, not a headline)
  ARM H1-DECLINE     : NULL
  ARM H3-DECLINE     : NULL
  ARM H4-DECLINE     : UNSTABLE
```


## era v3 · inputs aadab56 · sha 1fe4923 — recorded 2026-08-28
<!-- key era=v3 sha=1fe4923 inputs=aadab56 -->

population  406 results · 796 proxy · 1,607 analysis · 814 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-08-28 10:40)
run         2026-08-28 11:54:11 · git 1fe4923 (main, working tree dirty) · exit 0 · 3.6s
command     python -m scripts.backtest_study.f4_deployment.hedge_timing
excerpt     verdict

```
VERDICT (pre-registered grammar, pre-registrations/f4_deployment/hedge_timing.md)
  ARM H1-CHOP        : NULL
  ARM H3-CHOP        : NULL
  ARM H4-CHOP        : NULL
  ARM H2-CHOP        : NULL   (control, not a headline)
  ARM H1-GAP         : NULL
  ARM H3-GAP         : UNDERPOWERED
  ARM H4-GAP         : NULL
  ARM H2-GAP         : NULL   (control, not a headline)
  ARM H1-DECLINE     : NULL
  ARM H3-DECLINE     : NULL
  ARM H4-DECLINE     : NULL
```

