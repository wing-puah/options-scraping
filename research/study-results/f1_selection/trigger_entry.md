# trigger_entry — per-era record

**Question.** Does entering a play only WHEN its stated trigger level is first crossed, at that session's CLOSE, beat the unconditional next-open entry once the entry price pays for the confirmation?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 · inputs 8c64cab · sha 018be16 — recorded 2026-09-04
<!-- key era=v3 sha=018be16 inputs=8c64cab -->

population  406 results · 796 proxy · 1,607 analysis · 819 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-09-04 11:10)
run         2026-09-04 11:43:30 · git 018be16 (main, working tree dirty) · exit 0 · 11.1s
command     python -m scripts.backtest_study.f1_selection.trigger_entry
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid, regardless of outcome
  arm  cell        entered  dates    DeltaR  verdict
  T    N=1             363    111   -0.0310  PRICED-AWAY
  T    N=3             412    112   -0.0521  PRICED-AWAY
  T    N=5             441    113   -0.0723  PRICED-AWAY
  tally: {'PRICED-AWAY': 3}
  Verdict grammar (registration §"Verdicts, worded now"), EXHAUSTIVE and
  evaluated in this order, first match wins:
    UNDERPOWERED       a floor was not met; census published, nothing read.
    PRICED-AWAY        DeltaR <= 0 AND the E2-shape census reproduces at shipped
                       pricing: the selection is real on the tape and the
                       confirmation costs at least as much as it is worth.
```


## era v4 · inputs 88c8d65 · sha 018be16 — recorded 2026-09-04
<!-- key era=v4 sha=018be16 inputs=88c8d65 -->

population  494 results · 1,144 proxy · 1,975 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-02 14:53 … 2026-09-04 11:10)
run         2026-09-04 11:43:42 · git 018be16 (main, working tree dirty) · exit 0 · 18.1s
command     python -m scripts.backtest_study.f1_selection.trigger_entry
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid, regardless of outcome
  arm  cell        entered  dates    DeltaR  verdict
  T    N=1             511    140    0.0145  NULL
  T    N=3             573    145   -0.0137  PRICED-AWAY
  T    N=5             609    146   -0.0257  PRICED-AWAY
  tally: {'NULL': 1, 'PRICED-AWAY': 2}
  Verdict grammar (registration §"Verdicts, worded now"), EXHAUSTIVE and
  evaluated in this order, first match wins:
    UNDERPOWERED       a floor was not met; census published, nothing read.
    PRICED-AWAY        DeltaR <= 0 AND the E2-shape census reproduces at shipped
                       pricing: the selection is real on the tape and the
                       confirmation costs at least as much as it is worth.
```

