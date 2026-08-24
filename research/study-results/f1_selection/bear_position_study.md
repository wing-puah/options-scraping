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

