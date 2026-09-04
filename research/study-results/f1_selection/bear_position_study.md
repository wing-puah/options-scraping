# bear_position_study — per-era record

**Question.** Pre-registered cuts on bear_put: is it a SELECTION problem (E<0) or an EXIT problem (E>0 with R<0)?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:44:53 · git 53b7167 (main, working tree dirty) · exit 0 · 20.5s
command     python -m scripts.backtest_study.f1_selection.bear_position_study
excerpt     verdict

```
DECISION (pre-registered rule, addendum 13)
    DEMOTE requires all three:
      [PASS]  ex-window mean E < 0            (-0.330)
      [PASS]  bootstrap 95% CI upper < 0      ([-0.429, -0.228])
      [PASS]  both time halves negative       (early -0.289, late -0.358)
    CONSTRAIN candidates (n>=30, both halves positive, EX-W): ['|delta| 0.30-0.45']
    VERDICT: DEMOTE TO VETO
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:09:55 · git d47e227 (main, working tree dirty) · exit 0 · 13.2s
command     python -m scripts.backtest_study.f1_selection.bear_position_study
excerpt     verdict

```
DECISION (pre-registered rule, addendum 13)
    DEMOTE requires all three:
      [PASS]  ex-window mean E < 0            (-0.269)
      [PASS]  bootstrap 95% CI upper < 0      ([-0.465, -0.037])
      [PASS]  both time halves negative       (early -0.448, late -0.037)
    CONSTRAIN candidates (n>=30, both halves positive, EX-W): NONE
    VERDICT: DEMOTE TO VETO
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:20:19 · git c841a01 (main, working tree dirty) · exit 0 · 8.3s
command     python -m scripts.backtest_study.f1_selection.bear_position_study
excerpt     verdict

```
DECISION (pre-registered rule, addendum 13)
    DEMOTE requires all three:
      [PASS]  ex-window mean E < 0            (-0.288)
      [PASS]  bootstrap 95% CI upper < 0      ([-0.473, -0.076])
      [PASS]  both time halves negative       (early -0.495, late -0.033)
    CONSTRAIN candidates (n>=30, both halves positive, EX-W): NONE
    VERDICT: DEMOTE TO VETO
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 23:00:28 · git 25f3e27 (main, working tree dirty) · exit 0 · 49.9s
command     python -m scripts.backtest_study.f1_selection.bear_position_study
excerpt     verdict

```
DECISION (pre-registered rule, addendum 13)
    DEMOTE requires all three:
      [PASS]  ex-window mean E < 0            (-0.284)
      [PASS]  bootstrap 95% CI upper < 0      ([-0.413, -0.140])
      [PASS]  both time halves negative       (early -0.446, late -0.087)
    CONSTRAIN candidates (n>=30, both halves positive, EX-W): NONE
    VERDICT: DEMOTE TO VETO
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:35:28 · git e59356f (main, working tree dirty) · exit 0 · 14.5s
command     python -m scripts.backtest_study.f1_selection.bear_position_study
excerpt     verdict

```
DECISION (pre-registered rule, addendum 13)
    DEMOTE requires all three:
      [PASS]  ex-window mean E < 0            (-0.222)
      [PASS]  bootstrap 95% CI upper < 0      ([-0.349, -0.087])
      [PASS]  both time halves negative       (early -0.388, late -0.045)
    CONSTRAIN candidates (n>=30, both halves positive, EX-W): NONE
    VERDICT: DEMOTE TO VETO
```

