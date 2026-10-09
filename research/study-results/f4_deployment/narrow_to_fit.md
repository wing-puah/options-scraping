# narrow_to_fit — per-era record

**Question.** When a pick's one-contract max loss is over budget, is it better to narrow the spread until it fits, or to refuse it? Headline (R, F3, $1,000); F4 splits the $1,000 stop from the $1,000 budget.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha 89bf4e4 — recorded 2026-10-07
<!-- key era=v4 sha=89bf4e4 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-07 20:00:53 · git 89bf4e4 (main, working tree dirty) · exit 0 · 34.5s
command     python -m scripts.backtest_study.f4_deployment.narrow_to_fit
excerpt     matched

```
  N4  meanR +0.110  CI95 [-0.117,+0.338]  (date-clustered, BOOT_N 10000)  -> NOT MET
  N5  -> NOT MET
  N4  meanR +0.248  CI95 [+0.113,+0.383]  (date-clustered, BOOT_N 10000)  -> MET
  N5  -> MET
```


## era v4 · inputs 4b1c61f · sha d81af9d — recorded 2026-10-10
<!-- key era=v4 sha=d81af9d inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-09 22:58:12 · git d81af9d (worktree-wf_c8ce3d2e-793-2, working tree dirty) · exit 0 · 171.9s
command     python -m scripts.backtest_study.f4_deployment.narrow_to_fit
excerpt     matched

```
  N4  meanR +0.084  CI95 [-0.153,+0.322]  (date-clustered, BOOT_N 10000)  -> NOT MET
  N5  -> NOT MET
  N4  meanR +0.248  CI95 [+0.113,+0.383]  (date-clustered, BOOT_N 10000)  -> MET
  N5  -> MET
  N4  meanR +0.249  CI95 [+0.110,+0.388]  (date-clustered, BOOT_N 10000)  -> MET
  N5  -> MET
```

