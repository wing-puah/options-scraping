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


## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 20:17:22 · git d47e227 (main, working tree dirty) · exit 0 · 20.2s
command     python -m scripts.backtest_study.f2_management.staged_exit
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid
  arm   X  condition    action                    aff rows  aff dates  verdict
  E     5  R >= +0.50   exit now                        24         20  UNDERPOWERED
  E     5  R >= +0.25   exit now                        83         51  -
  E     5  R <= -0.25   exit now                        94         50  -
  E     5  R <= -0.50   exit now                        34         23  UNDERPOWERED
  E     5  $ >= +250    exit now                        73         50  -
  E     5  $ >= +500    exit now                        29         24  UNDERPOWERED
  E     5  $ <= -250    exit now                        99         54  -
  E     5  $ <= -500    exit now                        35         23  UNDERPOWERED
  E    10  R >= +0.50   exit now                        31         27  UNDERPOWERED
  E    10  R >= +0.25   exit now                        90         54  -
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:21:03 · git c841a01 (main, working tree dirty) · exit 0 · 12.8s
command     python -m scripts.backtest_study.f2_management.staged_exit
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid
  arm   X  condition    action                    aff rows  aff dates  verdict
  E     5  R >= +0.50   exit now                        24         20  UNDERPOWERED
  E     5  R >= +0.25   exit now                        88         55  -
  E     5  R <= -0.25   exit now                       106         56  -
  E     5  R <= -0.50   exit now                        41         27  UNDERPOWERED
  E     5  $ >= +250    exit now                        79         54  -
  E     5  $ >= +500    exit now                        30         25  UNDERPOWERED
  E     5  $ <= -250    exit now                       111         60  -
  E     5  $ <= -500    exit now                        39         26  UNDERPOWERED
  E    10  R >= +0.50   exit now                        32         28  UNDERPOWERED
  E    10  R >= +0.25   exit now                        98         59  -
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:37:58 · git 25f3e27 (main, working tree dirty) · exit 0 · 38.7s
command     python -m scripts.backtest_study.f2_management.staged_exit
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid
  arm   X  condition    action                    aff rows  aff dates  verdict
  E     5  R >= +0.50   exit now                        44         33  UNDERPOWERED
  E     5  R >= +0.25   exit now                       162         98  -
  E     5  R <= -0.25   exit now                       175         95  -
  E     5  R <= -0.50   exit now                        62         42  -
  E     5  $ >= +250    exit now                       145         92  -
  E     5  $ >= +500    exit now                        60         47  -
  E     5  $ <= -250    exit now                       178         98  -
  E     5  $ <= -500    exit now                        62         42  -
  E    10  R >= +0.50   exit now                        55         45  UNDERPOWERED
  E    10  R >= +0.25   exit now                       175        101  -
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:39:03 · git e59356f (main, working tree dirty) · exit 0 · 52.9s
command     python -m scripts.backtest_study.f2_management.staged_exit
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid
  arm   X  condition    action                    aff rows  aff dates  verdict
  E     5  R >= +0.50   exit now                        51         40  UNDERPOWERED
  E     5  R >= +0.25   exit now                       189        114  -
  E     5  R <= -0.25   exit now                       210        110  -
  E     5  R <= -0.50   exit now                        75         49  -
  E     5  $ >= +250    exit now                       164        104  -
  E     5  $ >= +500    exit now                        69         53  -
  E     5  $ <= -250    exit now                       212        114  -
  E     5  $ <= -500    exit now                        73         50  -
  E    10  R >= +0.50   exit now                        65         55  -
  E    10  R >= +0.25   exit now                       202        119  -
```


## era v4 · inputs 271c4b5 · sha 8e9b6a7 — recorded 2026-09-20
<!-- key era=v4 sha=8e9b6a7 inputs=271c4b5 -->

population  598 results · 1,665 proxy · 2,781 analysis · 827 spy_vix_daily_full  (inputs dated 2026-09-16 11:32 … 2026-09-19 16:45)
run         2026-09-19 23:33:11 · git 8e9b6a7 (main, working tree clean) · exit 0 · 110.9s
command     python -m scripts.backtest_study.f2_management.staged_exit
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid
  arm   X  condition    action                    aff rows  aff dates  verdict
  E     5  R >= +0.50   exit now                        54         45  UNDERPOWERED
  E     5  R >= +0.25   exit now                       211        133  -
  E     5  R <= -0.25   exit now                       252        136  -
  E     5  R <= -0.50   exit now                        85         61  -
  E     5  $ >= +250    exit now                       183        118  -
  E     5  $ >= +500    exit now                        77         60  -
  E     5  $ <= -250    exit now                       250        139  -
  E     5  $ <= -500    exit now                        84         62  -
  E    10  R >= +0.50   exit now                        73         62  -
  E    10  R >= +0.25   exit now                       224        138  -
```


## era v4 · inputs 7373cdb · sha de5a6f3 — recorded 2026-09-28
<!-- key era=v4 sha=de5a6f3 inputs=7373cdb -->

population  1,012 results · 2,029 proxy · 3,346 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-27 15:57 … 2026-09-28 12:45)
run         2026-09-28 12:59:09 · git de5a6f3 (main, working tree dirty) · exit 0 · 183.6s
command     python -m scripts.backtest_study.f2_management.staged_exit
excerpt     verdict  (40 of 106 block lines; 66 not quoted)
tally       UNDERPOWERED 41, CANDIDATE 1  (42 of 106 lines carried a token)

```
VERDICT SUMMARY — every cell in the frozen grid
  arm   X  condition    action                    aff rows  aff dates  verdict
  E     5  R >= +0.50   exit now                        63         51  REACTIVE-AGAIN
  E     5  R >= +0.25   exit now                       290        171  -
  E     5  R <= -0.25   exit now                       342        181  -
  E     5  R <= -0.50   exit now                       106         74  -
  E     5  $ >= +250    exit now                       268        166  -
  E     5  $ >= +500    exit now                       103         78  -
  E     5  $ <= -250    exit now                       356        188  -
  E     5  $ <= -500    exit now                       126         93  -
  E    10  R >= +0.50   exit now                        99         84  -
  E    10  R >= +0.25   exit now                       302        182  -
  E    10  R <= -0.25   exit now                       374        196  -
  E    10  R <= -0.50   exit now                       162        112  -
  E    10  $ >= +250    exit now                       271        169  -
  E    10  $ >= +500    exit now                       123         95  -
  E    10  $ <= -250    exit now                       374        199  -
  E    10  $ <= -500    exit now                       163        114  -
  E    15  R >= +0.50   exit now                        86         68  -
  E    15  R >= +0.25   exit now                       258        162  -
  E    15  R <= -0.25   exit now                       375        201  -
  E    15  R <= -0.50   exit now                       165        120  -
  E    15  $ >= +250    exit now                       223        154  -
  E    15  $ >= +500    exit now                        96         79  -
  E    15  $ <= -250    exit now                       370        201  -
  E    15  $ <= -500    exit now                       161        120  -
  E    20  R >= +0.50   exit now                        80         66  -
  E    20  R >= +0.25   exit now                       224        144  -
  E    20  R <= -0.25   exit now                       323        192  -
  E    20  R <= -0.50   exit now                       152        116  -
  E    20  $ >= +250    exit now                       195        138  -
  E    20  $ >= +500    exit now                        88         73  -
  E    20  $ <= -250    exit now                       311        189  -
  E    20  $ <= -500    exit now                       138        109  -
  T     5  R >= +0.50   tighten stop to -0.40            7          7  UNDERPOWERED
  T     5  R >= +0.50   arm trail 0.50/0.50             30         26  UNDERPOWERED
  T     5  R >= +0.25   tighten stop to -0.40           65         57  -
  T     5  R >= +0.25   arm trail 0.50/0.50            100         75  -
  T     5  R <= -0.25   tighten stop to -0.40          313        170  -
  T     5  R <= -0.25   arm trail 0.50/0.50             23         23  UNDERPOWERED
```

