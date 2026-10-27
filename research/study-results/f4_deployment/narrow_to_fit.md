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


## era v4 · inputs 61bda3a · sha 3dae88d — recorded 2026-10-26
<!-- key era=v4 sha=3dae88d inputs=61bda3a -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-26 01:06)
run         2026-10-26 19:14:57 · git 3dae88d (main, working tree dirty) · exit 0 · 252.6s
command     python -m scripts.backtest_study.f4_deployment.narrow_to_fit
excerpt     tail

```
  cells scored by this run: 36 (7 registered cells + 2 floored F3 lines, x 2 cap cells x 2 populations, F3 only where GN5 lets it grade)
CLOSE
  headline (R, F3, $1,000): AWAITING SCRAPE
  declared secondary (R, F3, $1,000) + 20% net floor: AWAITING SCRAPE
  secondary (R, F3, $500): AWAITING SCRAPE
  declared secondary (R, F3, $500) + 20% net floor: AWAITING SCRAPE
  gates: G2-G5 PASS  GN1 PASS  GN2 PASS  GN3 PASS  GN4 PASS
  Nothing in this report is a shippable rule.
```

