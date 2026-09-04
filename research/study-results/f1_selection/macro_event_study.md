# macro_event_study — per-era record

**Question.** Do scheduled macro events — FOMC decisions, minutes, CPI, NFP, PCE — show up in the book: in entry IV (vrp), in outcomes (R/E), or in exits?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 · inputs cd647ce · sha 325964e — recorded 2026-08-19
<!-- key era=v3 sha=325964e inputs=cd647ce -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 807 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-08-19 11:10)
run         2026-08-19 14:48:14 · git 325964e (main, working tree dirty) · exit 0 · 4.3s
command     python -m scripts.backtest_study.f1_selection.macro_event_study
excerpt     verdict

```
ARM X — EXIT CENSUS (H4: ENDOGENOUS — a fast exit is why some holds contain no event. Census only; no verdict)
  hold spans >=1 macro event: 716 rows / 118 dates  mean R +0.027  mean days_held 29.5
    profit_target           288
    stop_loss               176
    time_exit                91
    dollar_stop              90
    cap_open                 51
    trailing_stop            12
    expired                   8
  hold spans none: 79 rows / 50 dates  mean R +0.099  mean days_held 3.5
    profit_target            33
    dollar_stop              30
```


## era v3 · inputs cd647ce · sha 5836365 — recorded 2026-08-19
<!-- key era=v3 sha=5836365 inputs=cd647ce -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 807 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-08-19 11:10)
run         2026-08-19 14:59:12 · git 5836365 (main, working tree dirty) · exit 0 · 5.5s
command     python -m scripts.backtest_study.f1_selection.macro_event_study
excerpt     verdict

```
ARM X — EXIT CENSUS (H4: ENDOGENOUS — a fast exit is why some holds contain no event. Census only; no verdict)
  hold spans >=1 macro event: 716 rows / 118 dates  mean R +0.027  mean days_held 29.5
    profit_target           288
    stop_loss               176
    time_exit                91
    dollar_stop              90
    cap_open                 51
    trailing_stop            12
    expired                   8
  hold spans none: 79 rows / 50 dates  mean R +0.099  mean days_held 3.5
    profit_target            33
    dollar_stop              30
```


## era v3 · inputs cd647ce · sha 384b4e2 — recorded 2026-08-19
<!-- key era=v3 sha=384b4e2 inputs=cd647ce -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 807 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-08-19 11:10)
run         2026-08-19 15:17:23 · git 384b4e2 (main, working tree dirty) · exit 0 · 9.4s
command     python -m scripts.backtest_study.f1_selection.macro_event_study
excerpt     verdict

```
ARM X — EXIT CENSUS (H4: ENDOGENOUS — a fast exit is why some holds contain no event. Census only; no verdict)
  hold spans >=1 macro event: 716 rows / 118 dates  mean R +0.027  mean days_held 29.5
    profit_target           288
    stop_loss               176
    time_exit                91
    dollar_stop              90
    cap_open                 51
    trailing_stop            12
    expired                   8
  hold spans none: 79 rows / 50 dates  mean R +0.099  mean days_held 3.5
    profit_target            33
    dollar_stop              30
```


## era v3 · inputs cd647ce · sha 6446506 — recorded 2026-08-19
<!-- key era=v3 sha=6446506 inputs=cd647ce -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 807 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-08-19 11:10)
run         2026-08-19 15:28:24 · git 6446506 (main, working tree dirty) · exit 0 · 12.5s
command     python -m scripts.backtest_study.f1_selection.macro_event_study
excerpt     verdict

```
ARM X — EXIT CENSUS (H4: ENDOGENOUS — a fast exit is why some holds contain no event. Census only; no verdict)
  hold spans >=1 macro event: 716 rows / 118 dates  mean R +0.027  mean days_held 29.5
    profit_target           288
    stop_loss               176
    time_exit                91
    dollar_stop              90
    cap_open                 51
    trailing_stop            12
    expired                   8
  hold spans none: 79 rows / 50 dates  mean R +0.099  mean days_held 3.5
    profit_target            33
    dollar_stop              30
```


## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 20:18:15 · git d47e227 (main, working tree dirty) · exit 0 · 5.5s
command     python -m scripts.backtest_study.f1_selection.macro_event_study
excerpt     verdict

```
ARM X — EXIT CENSUS (H4: ENDOGENOUS — a fast exit is why some holds contain no event. Census only; no verdict)
  hold spans >=1 macro event: 460 rows / 78 dates  mean R +0.104  mean days_held 34.0
    profit_target           198
    stop_loss                95
    dollar_stop              63
    cap_open                 48
    time_exit                38
    be_stop                  10
    expired                   7
    trailing_stop             1
  hold spans none: 57 rows / 38 dates  mean R +0.225  mean days_held 3.2
    profit_target            30
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:20:35 · git c841a01 (main, working tree dirty) · exit 0 · 3.6s
command     python -m scripts.backtest_study.f1_selection.macro_event_study
excerpt     verdict

```
ARM X — EXIT CENSUS (H4: ENDOGENOUS — a fast exit is why some holds contain no event. Census only; no verdict)
  hold spans >=1 macro event: 501 rows / 87 dates  mean R +0.093  mean days_held 34.0
    profit_target           210
    stop_loss               103
    dollar_stop              74
    cap_open                 50
    time_exit                43
    be_stop                  12
    expired                   8
    trailing_stop             1
  hold spans none: 66 rows / 44 dates  mean R +0.250  mean days_held 3.2
    profit_target            35
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:36:54 · git 25f3e27 (main, working tree dirty) · exit 0 · 17.8s
command     python -m scripts.backtest_study.f1_selection.macro_event_study
excerpt     verdict

```
ARM X — EXIT CENSUS (H4: ENDOGENOUS — a fast exit is why some holds contain no event. Census only; no verdict)
  hold spans >=1 macro event: 897 rows / 144 dates  mean R +0.080  mean days_held 35.7
    profit_target           376
    stop_loss               179
    dollar_stop             124
    cap_open                 99
    time_exit                92
    expired                  16
    be_stop                  10
    trailing_stop             1
  hold spans none: 99 rows / 76 dates  mean R +0.224  mean days_held 2.8
    profit_target            52
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:35:56 · git e59356f (main, working tree clean) · exit 0 · 26.5s
command     python -m scripts.backtest_study.f1_selection.macro_event_study
excerpt     verdict

```
ARM X — EXIT CENSUS (H4: ENDOGENOUS — a fast exit is why some holds contain no event. Census only; no verdict)
  hold spans >=1 macro event: 1034 rows / 166 dates  mean R +0.059  mean days_held 36.0
    profit_target           428
    stop_loss               202
    dollar_stop             149
    cap_open                116
    time_exit               107
    expired                  21
    be_stop                  10
    trailing_stop             1
  hold spans none: 109 rows / 82 dates  mean R +0.238  mean days_held 3.0
    profit_target            59
```

