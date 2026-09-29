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


## era v3 · inputs 8c64cab · sha 4fc17ac — recorded 2026-09-04
<!-- key era=v3 sha=4fc17ac inputs=8c64cab -->

population  406 results · 796 proxy · 1,607 analysis · 819 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-09-04 11:10)
run         2026-09-04 12:17:58 · git 4fc17ac (main, working tree dirty) · exit 0 · 13.9s
command     python -m scripts.backtest_study.f1_selection.trigger_entry
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid, regardless of outcome
  arm  cell        entered  dates    DeltaR  verdict
  T    N=1             363    111   -0.0310  LATE-ENTRY
  T    N=3             412    112   -0.0521  LATE-ENTRY
  T    N=5             441    113   -0.0723  LATE-ENTRY
  tally: {'LATE-ENTRY': 3}
  Verdict grammar (registration §"Verdicts, worded now"), EXHAUSTIVE and
  evaluated in this order, first match wins:
    UNDERPOWERED       a floor was not met; census published, nothing read.
    LATE-ENTRY         DeltaR <= 0 AND the E2-shape census reproduces at shipped
                       pricing: the signal works (the trigger sorts winners from
                       losers) but the confirmed entry comes AFTER the move it
```


## era v4 · inputs 88c8d65 · sha 4fc17ac — recorded 2026-09-04
<!-- key era=v4 sha=4fc17ac inputs=88c8d65 -->

population  494 results · 1,144 proxy · 1,975 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-02 14:53 … 2026-09-04 11:10)
run         2026-09-04 12:18:14 · git 4fc17ac (main, working tree dirty) · exit 0 · 26.5s
command     python -m scripts.backtest_study.f1_selection.trigger_entry
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid, regardless of outcome
  arm  cell        entered  dates    DeltaR  verdict
  T    N=1             511    140    0.0145  NULL
  T    N=3             573    145   -0.0137  LATE-ENTRY
  T    N=5             609    146   -0.0257  LATE-ENTRY
  tally: {'NULL': 1, 'LATE-ENTRY': 2}
  Verdict grammar (registration §"Verdicts, worded now"), EXHAUSTIVE and
  evaluated in this order, first match wins:
    UNDERPOWERED       a floor was not met; census published, nothing read.
    LATE-ENTRY         DeltaR <= 0 AND the E2-shape census reproduces at shipped
                       pricing: the signal works (the trigger sorts winners from
                       losers) but the confirmed entry comes AFTER the move it
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:37:40 · git e59356f (main, working tree dirty) · exit 0 · 11.8s
command     python -m scripts.backtest_study.f1_selection.trigger_entry
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid, regardless of outcome
  arm  cell        entered  dates    DeltaR  verdict
  T    N=1             578    158    0.0094  NULL
  T    N=3             645    162   -0.0121  LATE-ENTRY
  T    N=5             682    163   -0.0232  LATE-ENTRY
  tally: {'NULL': 1, 'LATE-ENTRY': 2}
  Verdict grammar (registration §"Verdicts, worded now"), EXHAUSTIVE and
  evaluated in this order, first match wins:
    UNDERPOWERED       a floor was not met; census published, nothing read.
    LATE-ENTRY         DeltaR <= 0 AND the E2-shape census reproduces at shipped
                       pricing: the signal works (the trigger sorts winners from
                       losers) but the confirmed entry comes AFTER the move it
```


## era v4 · inputs 271c4b5 · sha 8e9b6a7 — recorded 2026-09-20
<!-- key era=v4 sha=8e9b6a7 inputs=271c4b5 -->

population  598 results · 1,665 proxy · 2,781 analysis · 827 spy_vix_daily_full  (inputs dated 2026-09-16 11:32 … 2026-09-19 16:45)
run         2026-09-19 23:30:16 · git 8e9b6a7 (main, working tree clean) · exit 0 · 19.8s
command     python -m scripts.backtest_study.f1_selection.trigger_entry
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid, regardless of outcome
  arm  cell        entered  dates    DeltaR  verdict
  T    N=1             677    197   -0.0039  LATE-ENTRY
  T    N=3             767    201   -0.0323  LATE-ENTRY
  T    N=5             806    204   -0.0427  LATE-ENTRY
  tally: {'LATE-ENTRY': 3}
  Verdict grammar (registration §"Verdicts, worded now"), EXHAUSTIVE and
  evaluated in this order, first match wins:
    UNDERPOWERED       a floor was not met; census published, nothing read.
    LATE-ENTRY         DeltaR <= 0 AND the E2-shape census reproduces at shipped
                       pricing: the signal works (the trigger sorts winners from
                       losers) but the confirmed entry comes AFTER the move it
```


## era v4 · inputs 7373cdb · sha de5a6f3 — recorded 2026-09-28
<!-- key era=v4 sha=de5a6f3 inputs=7373cdb -->

population  1,012 results · 2,029 proxy · 3,346 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-27 15:57 … 2026-09-28 12:45)
run         2026-09-28 14:19:47 · git de5a6f3 (main, working tree dirty) · exit 0 · 25.7s
command     python -m scripts.backtest_study.f1_selection.trigger_entry
excerpt     verdict

```
VERDICT SUMMARY — every cell in the frozen grid, regardless of outcome
  arm  cell        entered  dates    DeltaR  verdict
  T    N=1             811    243   -0.0228  LATE-ENTRY
  T    N=3             931    248   -0.0348  LATE-ENTRY
  T    N=5             987    249   -0.0492  LATE-ENTRY
  tally: {'LATE-ENTRY': 3}
  Verdict grammar (registration §"Verdicts, worded now"), EXHAUSTIVE and
  evaluated in this order, first match wins:
    UNDERPOWERED       a floor was not met; census published, nothing read.
    LATE-ENTRY         DeltaR <= 0 AND the E2-shape census reproduces at shipped
                       pricing: the signal works (the trigger sorts winners from
                       losers) but the confirmed entry comes AFTER the move it
                       selects on — the confirmation costs what it is worth.
    CONTRARY           CI excludes zero with DeltaR < 0 and no reproducing
                       census: the trigger is actively misleading. Fed to the
                       PROMPT-ROBUSTNESS list.
    CONFOUND-EXPLAINED criteria 1-7 clear, criterion 8 fails: the gain lives
                       outside the conformity bands, i.e. it is the day-0 move
                       `next_day_move` ARM C already owns.
    LAG-EXPLAINED      all eight clear but L-SEP fails: ARM L reproduces it with
                       no gate at all, so it is about WHEN, not WHICH.
    CANDIDATE          all eight clear AND L-SEP holds. An INTAKE proposal,
                       NEVER an exit rule and NEVER a ship: it becomes a written
                       proposal with its own rollback trigger and an
                       independent-window confirmation first.
    NULL               powered, nothing above matched. Recorded.
  ARM L, ARM C and ARM D carry no verdict word of their own; the E2-shape census
  carries none at all. R is the unit of every conclusion; NO dollar figure is
  quoted across arms, and no annualised figure, Sharpe or time-to-recover is
  printed anywhere above, by design.
```

