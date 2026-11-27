# tier_contrast_forward — per-era record

**Question.** On signal dates after 2026-11-27, do Tier A and Tier B plays earn more R per position than Tier C plays (one date-clustered contrast on the same dates, v4, forward only)?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs e7318a6 · sha 26f696f — recorded 2026-11-28
<!-- key era=v4 sha=26f696f inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-28 03:26:38 · git 26f696f (main, working tree clean) · exit 0 · 1.1s
command     python -m scripts.backtest_study.f4_deployment.tier_contrast_forward
excerpt     tail

```
book outcomes: 2264 rows; 247 open_at_data_end (cap_open marks at the data end, not closes), 190 carried, 55 deferred exit fills (calibration skipped…
forward rows from 2026-11-28: 0; vetoed (in neither arm) 0; other census {}
proxy rows (never graded) per tier: {'A': 0, 'B': 0, 'C': 0}
complete prefix: 0 dates
closed rows with no R (dropped): 0
arm AB: 0 closed positions on 0 signal dates (floor 377 on 120)
arm C: 0 closed positions on 0 signal dates (floor 377 on 120)
>>> tier_contrast_forward STILL-OPEN <<<
```

