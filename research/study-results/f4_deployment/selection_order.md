# selection_order — per-era record

**Question.** account_sim's rejected picks outperformed its taken ones. Does a different BLIND entry-side ORDER of the same candidate set spend the scarce delta budget better — or was that read an artifact?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:47:51 · git 53b7167 (main, working tree dirty) · exit 0 · 2.7s
command     python -m scripts.backtest_study.f4_deployment.selection_order
excerpt     verdict

```
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
  arms powered (G0):  none
  arms clearing all seven: none
  Best-powered arm reached 11 affected dates against a threshold of 25.
  CENSUS OBSERVATION, explicitly NOT a verdict upgrade: the reason the arms are
  under-powered is itself informative — each one changes only 7-14% of O0's
  taken positions, because on most contested dates the caps exclude the same
  picks whatever the order. That texture is what CAP-BOUND-NOT-ORDER-BOUND
  describes. It may NOT be recorded as that verdict: the label requires arms
  that CLEAR G0, and reading a blocked arm's shape as a conclusion is exactly
  the move the power stop exists to prevent. It is a carry-forward for a
  re-registration on a materially larger book, nothing more.
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 20:13:34 · git d47e227 (main, working tree dirty) · exit 0 · 3.3s
command     python -m scripts.backtest_study.f4_deployment.selection_order
excerpt     verdict

```
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
  arms powered (G0):  none
  arms clearing all seven: none
  Best-powered arm reached 17 affected dates against a threshold of 25.
  CENSUS OBSERVATION, explicitly NOT a verdict upgrade: the reason the arms are
  under-powered is itself informative — each one changes only 7-14% of O0's
  taken positions, because on most contested dates the caps exclude the same
  picks whatever the order. That texture is what CAP-BOUND-NOT-ORDER-BOUND
  describes. It may NOT be recorded as that verdict: the label requires arms
  that CLEAR G0, and reading a blocked arm's shape as a conclusion is exactly
  the move the power floor exists to prevent. It is a carry-forward for a
  re-registration on a materially larger book, nothing more.
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:23:20 · git c841a01 (main, working tree dirty) · exit 0 · 2.1s
command     python -m scripts.backtest_study.f4_deployment.selection_order
excerpt     verdict

```
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
  arms powered (G0):  none
  arms clearing all seven: none
  Best-powered arm reached 20 affected dates against a threshold of 25.
  CENSUS OBSERVATION, explicitly NOT a verdict upgrade: the reason the arms are
  under-powered is itself informative — each one changes only 18%-27% of O0's
  taken positions (this run's measured range across the 4 ordering
  arms), because on most contested dates the caps exclude the same picks
  whatever the order. That
  texture is what CAP-BOUND-NOT-ORDER-BOUND describes. It may NOT be recorded
  as that verdict: the label requires arms that CLEAR G0, and reading a
  blocked arm's shape as a conclusion is exactly the move the power floor
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:43:13 · git 25f3e27 (main, working tree dirty) · exit 0 · 4.5s
command     python -m scripts.backtest_study.f4_deployment.selection_order
excerpt     verdict

```
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
  arms powered (G0):  O1, O2, O3, O1b
  arms clearing all seven: none
  VERDICT: ORDERING-IS-NOISE — no arm separates from the O4 band. The adverse-ordering read from account_sim was an ARTIFACT of which picks the cap h…
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:47:13 · git e59356f (main, working tree dirty) · exit 0 · 4.5s
command     python -m scripts.backtest_study.f4_deployment.selection_order
excerpt     verdict

```
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
  arms powered (G0):  O1, O2, O3, O1b
  arms clearing all seven: none
  VERDICT: ORDERING-IS-NOISE — no arm separates from the O4 band. The adverse-ordering read from account_sim was an ARTIFACT of which picks the cap h…
```

