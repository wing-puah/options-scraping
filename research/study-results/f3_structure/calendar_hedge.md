# calendar_hedge — per-era record

**Question.** Re-derive that one survivor under a pre-registered pick rule and a strict fill rule.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:46:40 · git 53b7167 (main, working tree dirty) · exit 0 · 9.0s
command     python -m scripts.backtest_study.f3_structure.calendar_hedge
excerpt     verdict

```
VERDICT
  H0 FILL           MET
  H2 (primary)      NOT EVALUABLE
  H2 under hold     NOT EVALUABLE   (sensitivity — may not change the verdict)
  Ship ceiling per the pre-registration: an optional second hedge sleeve
  in docs/deployment-rules.md §4, requiring H0 MET and H0b not flipping
  the verdict and H2 MET and H3 deployable at f >= 0.25. Anything less is
  a candidate. Nothing here changes config/backtest.yml.
```

## era v4 · inputs 19941e0 · sha 6b6c652 — recorded 2026-08-19
<!-- key era=v4 sha=6b6c652 inputs=19941e0 -->

population  531 results · 1,326 proxy · 3,799 analysis · 807 spy_vix_daily_full  (inputs dated 2026-08-19 11:10 … 2026-08-19 11:15)
run         2026-08-19 13:03:40 · git 6b6c652 (main, working tree dirty) · exit 0 · 29.9s
command     python -m scripts.backtest_study.f3_structure.calendar_hedge
excerpt     verdict

```
VERDICT
  H0 FILL           NOT MET
  H2 (primary)      NOT EVALUABLE
  H2 under hold     NOT EVALUABLE   (sensitivity — may not change the verdict)
  Ship ceiling per the pre-registration: an optional second hedge sleeve
  in docs/deployment-rules.md §4, requiring H0 MET and H0b not flipping
  the verdict and H2 MET and H3 deployable at f >= 0.25. Anything less is
  a candidate. Nothing here changes config/backtest.yml.
```

