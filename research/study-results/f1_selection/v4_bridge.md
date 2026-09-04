# v4_bridge — per-era record

**Question.** v4 dropped two prompt factors. Does the v3-derived ladder still apply to what v4 actually emits?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:45:46 · git 53b7167 (main, working tree dirty) · exit 2 (designed refusal) · 1.4s
command     python -m scripts.backtest_study.f1_selection.v4_bridge
excerpt     refusal

```
GATE NOT MET — v4 has 14 of 20 required dates.
  6 more to go; v4 accrues ~1 date/day from the normal cadence,
  so roughly 6 trading days (~4 weeks from a standing start).
  This is the pre-registered gate working, not a failure. Do not
  lower MIN_V4_DATES to make it run — the threshold was fixed
  before any v4 result existed.
  Interim posture (also pre-registered): deploy under the v3
  rules in docs/deployment-rules.md, unchanged.
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:10:32 · git d47e227 (main, working tree dirty) · exit 0 · 1.5s
command     python -m scripts.backtest_study.f1_selection.v4_bridge
excerpt     matched

```
VERDICT: LADDER UNVALIDATED ON v4
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:20:50 · git c841a01 (main, working tree dirty) · exit 0 · 0.9s
command     python -m scripts.backtest_study.f1_selection.v4_bridge
excerpt     matched

```
VERDICT: LADDER UNVALIDATED ON v4
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:37:39 · git 25f3e27 (main, working tree dirty) · exit 0 · 1.2s
command     python -m scripts.backtest_study.f1_selection.v4_bridge
excerpt     matched

```
VERDICT: LADDER UNVALIDATED ON v4
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:37:52 · git e59356f (main, working tree dirty) · exit 0 · 1.0s
command     python -m scripts.backtest_study.f1_selection.v4_bridge
excerpt     matched

```
VERDICT: LADDER UNVALIDATED ON v4
```

