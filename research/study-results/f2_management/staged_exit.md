# staged_exit — per-era record

**Question.** Does a time-STAGED exit — evaluate ONCE at fixed session X on P&L vs the original entry, then exit / tighten / arm a trail — work where the reactive drawdown-from-peak rules of Attempts 1/2/10 did not?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 · inputs cd647ce · sha bfcd512 — recorded 2026-08-19
<!-- key era=v3 sha=bfcd512 inputs=cd647ce -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 807 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-08-19 11:10)
run         2026-08-19 17:10:09 · git bfcd512 (main, working tree dirty) · exit 0 · 43.3s
command     python -m scripts.backtest_study.f2_management.staged_exit
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid
  arm   X  condition    action                    aff rows  aff dates  verdict
  E     5  R >= +0.50   exit now                        41         31  POWER-STOPPED
  E     5  R >= +0.25   exit now                       141         81  -
  E     5  R <= -0.25   exit now                       169         82  -
  E     5  R <= -0.50   exit now                        62         39  -
  E     5  $ >= +250    exit now                       120         75  -
  E     5  $ >= +500    exit now                        47         36  POWER-STOPPED
  E     5  $ <= -250    exit now                       157         82  -
  E     5  $ <= -500    exit now                        52         36  POWER-STOPPED
  E    10  R >= +0.50   exit now                        45         33  POWER-STOPPED
  E    10  R >= +0.25   exit now                       130         79  -
```

