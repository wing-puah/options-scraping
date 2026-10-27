# regime_map — per-era record

**Question.** A descriptive map, not a selection rule: for each ladder tier (A, B, C, VETO) against each of six market labels (mech_cell, mech direction, mech vol, SPY vs its 50-day SMA, model direction, model vol), is meanR clearly above or below zero after BH, and does v3 give the same answer?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha 92d5bc8 — recorded 2026-10-12
<!-- key era=v4 sha=92d5bc8 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-12 21:14:54 · git 92d5bc8 (main, working tree dirty) · exit 0 · 2.1s
command     python -m scripts.backtest_study.f1_selection.regime.regime_map
excerpt     verdict

```
VERDICT
  v4 net, graded cells: POSITIVE 2, NEGATIVE 1, NULL 45, THIN 28
  v3 gross, graded cells: POSITIVE 17, NEGATIVE 8, NULL 19, THIN 32
  >>> regime_map REPLICATED cells (v4 net vs v3 gross): 2: A x RM-MDIR=BEAR POSITIVE, A x RM-SMA=below POSITIVE <<<
  forward: {'STILL-OPEN': 2}
  A descriptive map, not a selection rule. Nothing ships from this study.
```


## era v4 · inputs 61bda3a · sha 3dae88d — recorded 2026-10-26
<!-- key era=v4 sha=3dae88d inputs=61bda3a -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-26 01:06)
run         2026-10-26 19:30:55 · git 3dae88d (main, working tree dirty) · exit 0 · 21.3s
command     python -m scripts.backtest_study.f1_selection.regime.regime_map
excerpt     verdict

```
VERDICT
  v4 net, graded cells: POSITIVE 3, NEGATIVE 8, NULL 36, THIN 29
  v3 gross, graded cells: POSITIVE 17, NEGATIVE 8, NULL 19, THIN 32
  >>> regime_map REPLICATED cells (v4 net vs v3 gross): 3: A x RM-MDIR=BEAR POSITIVE, A x RM-SMA=below POSITIVE, B x RM-RVOL=C-VOL POSITIVE <<<
  forward: {'STILL-OPEN': 3}
  A descriptive map, not a selection rule. Nothing ships from this study.
```

