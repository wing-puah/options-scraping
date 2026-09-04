# concurrency_correlation — per-era record

**Question.** max_positions_per_day caps the FLOW of new positions; nothing caps the STOCK of open ones. Does the SIZE and internal SIMILARITY of the open book degrade per-position outcome, independently of what was selected?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 88c8d65 · sha 64689d0 — recorded 2026-09-04
<!-- key era=v4 sha=64689d0 inputs=88c8d65 -->

population  494 results · 1,144 proxy · 1,975 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-02 14:53 … 2026-09-04 11:10)
run         2026-09-04 17:14:18 · git 64689d0 (main, working tree dirty) · exit 0 · 38.5s
command     python -m scripts.backtest_study.f4_deployment.concurrency_correlation
excerpt     verdict

```
VERDICT
  arms run (PRIMARY): 13   powered past X1: 11   clearing X2/X3/X6/X7: 0
    C ceiling 5                  gain +0.0006 R   criteria met ----
    C ceiling 8                  gain +0.0345 R   criteria met --6-
    C ceiling 12                 gain -0.0430 R   criteria met ----
    C ceiling 20                 gain +0.0292 R   criteria met --6-
    K 2 / same-direction         gain -0.2174 R   criteria met ----
    K 3 / same-direction         gain -0.0255 R   criteria met ----
    K 5 / same-direction         gain +0.0006 R   criteria met ----
    K 2 / same-direction-and-sector gain +0.0190 R   criteria met ----
    K 3 / same-direction-and-sector gain +0.0054 R   criteria met ----
    K 5 / same-direction-and-sector gain +0.0031 R   criteria met ----
```


## era v3 · inputs 8c64cab · sha e59356f — recorded 2026-09-04
<!-- key era=v3 sha=e59356f inputs=8c64cab -->

population  406 results · 796 proxy · 1,607 analysis · 819 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-09-04 11:10)
run         2026-09-04 21:55:33 · git e59356f (main, working tree dirty) · exit 0 · 13.1s
command     python -m scripts.backtest_study.f4_deployment.concurrency_correlation
excerpt     verdict

```
VERDICT
  arms run (PRIMARY): 13   powered past X1: 8   clearing X2/X3/X6/X7: 0
    C ceiling 5                  gain -0.1546 R   criteria met ----
    C ceiling 8                  gain -0.1182 R   criteria met ----
    C ceiling 12                 gain -0.1141 R   criteria met ----
    C ceiling 20                 UNDERPOWERED (19 moved dates, 41 moved positions)
    K 2 / same-direction         gain -0.0729 R   criteria met ----
    K 3 / same-direction         gain -0.0001 R   criteria met ----
    K 5 / same-direction         gain -0.1546 R   criteria met ----
    K 2 / same-direction-and-sector gain +0.0864 R   criteria met ----
    K 3 / same-direction-and-sector gain -0.0478 R   criteria met ----
    K 5 / same-direction-and-sector UNDERPOWERED (19 moved dates, 25 moved positions)
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 21:55:49 · git e59356f (main, working tree dirty) · exit 0 · 36.0s
command     python -m scripts.backtest_study.f4_deployment.concurrency_correlation
excerpt     verdict

```
VERDICT
  arms run (PRIMARY): 13   powered past X1: 11   clearing X2/X3/X6/X7: 0
    C ceiling 5                  gain +0.0006 R   criteria met ----
    C ceiling 8                  gain +0.0155 R   criteria met ----
    C ceiling 12                 gain -0.0564 R   criteria met ----
    C ceiling 20                 gain +0.0174 R   criteria met ----
    K 2 / same-direction         gain -0.2174 R   criteria met ----
    K 3 / same-direction         gain -0.0255 R   criteria met ----
    K 5 / same-direction         gain +0.0006 R   criteria met ----
    K 2 / same-direction-and-sector gain +0.0250 R   criteria met ----
    K 3 / same-direction-and-sector gain +0.0109 R   criteria met ----
    K 5 / same-direction-and-sector gain +0.0080 R   criteria met ----
```

