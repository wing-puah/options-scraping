# hedge_exposure — per-era record

**Question.** When the open book is CONCENTRATED in one correlated cluster, does adding a long put on that cluster's proxy reduce the book's MARK-TO-MARKET drawdown, versus carrying the same concentrated book unhedged?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs ef2016f · sha 14db299 — recorded 2026-08-31
<!-- key era=v4 sha=14db299 inputs=ef2016f -->

population  485 results · 1,111 proxy · 1,893 analysis · 815 spy_vix_daily_full  (inputs dated 2026-08-27 20:34 … 2026-08-29 14:01)
run         2026-08-31 13:25:24 · git 14db299 (main, working tree dirty) · exit 0 · 28.7s
command     python -m scripts.backtest_study.f4_deployment.hedge_exposure
excerpt     verdict

```
RESULT — NO STUDY-LEVEL VERDICT IS EMITTED
  population real — the raw BacktestResults stratum (real pricing only)
    485 rows / 140 signal dates
    powered cells 3   cell words: NULL 3  UNDERPOWERED 6
    ARM M curves differ materially: YES
    clause 2's outcome survives the F5 estimator change: YES
  population all — the literal load_book(include_bs=False) call (real + tweak)
    996 rows / 145 signal dates
    powered cells 0   cell words: UNDERPOWERED 9
    ARM M curves differ materially: YES
  Both populations are reported. NEITHER is concluded from. Per ERRATUM 1 the
  population clause of the pre-registration is self-contradictory and the
```


## era v4 · inputs ef2016f · sha e826bd1 — recorded 2026-08-31
<!-- key era=v4 sha=e826bd1 inputs=ef2016f -->

population  485 results · 1,111 proxy · 1,893 analysis · 815 spy_vix_daily_full  (inputs dated 2026-08-27 20:34 … 2026-08-29 14:01)
run         2026-08-31 14:01:39 · git e826bd1 (main, working tree dirty) · exit 0 · 35.8s
command     python -m scripts.backtest_study.f4_deployment.hedge_exposure
excerpt     verdict

```
RESULT — NO STUDY-LEVEL VERDICT IS EMITTED
  population real — the raw BacktestResults stratum (real pricing only)
    485 rows / 140 signal dates
    powered POOLED cells 3   POOLED cell words: NULL 3  UNDERPOWERED 6
    DIRECT cell words: NULL 3  UNDERPOWERED 6
    CONSTITUENT cell words: UNDERPOWERED 9
    ARM M curve gap: maxDD $+702   ulcer +0.47 pts   TUW +2.0 pts   (differ materially: YES)
    clause 2's outcome survives the F5 estimator change: YES
    clause 3's outcome survives the registered ARM N match: YES
  population all — the literal load_book(include_bs=False) call (real + tweak)
    996 rows / 145 signal dates
    powered POOLED cells 0   POOLED cell words: UNDERPOWERED 9
```


## era v4 · inputs ef2016f · sha 7965db6 — recorded 2026-08-31
<!-- key era=v4 sha=7965db6 inputs=ef2016f -->

population  485 results · 1,111 proxy · 1,893 analysis · 815 spy_vix_daily_full  (inputs dated 2026-08-27 20:34 … 2026-08-29 14:01)
run         2026-08-31 14:52:01 · git 7965db6 (main, working tree dirty) · exit 0 · 60.0s
command     python -m scripts.backtest_study.f4_deployment.hedge_exposure
excerpt     verdict

```
CELL TALLY — population all   (no verdict is read from it)
  POOLED (not a stratum — the pooled trigger):
    UNDERPOWERED       9 cell(s)
  DIRECT:
    UNDERPOWERED       9 cell(s)
  CONSTITUENT:
    UNDERPOWERED       9 cell(s)
  Cell-level words only. The registration's study-level verdicts
  (MECHANISM-FOUND / NULL / CONTRARY / UNDERPOWERED / NOT EVALUABLE /
  MEASUREMENT-ONLY) are emitted ONCE, in the closing section, and only off the
  RATIFIED population — never from this tally and never per population.
```


## era v4 · inputs ef2016f · sha 45baa2d — recorded 2026-08-31
<!-- key era=v4 sha=45baa2d inputs=ef2016f -->

population  485 results · 1,111 proxy · 1,893 analysis · 815 spy_vix_daily_full  (inputs dated 2026-08-27 20:34 … 2026-08-29 14:01)
run         2026-08-31 15:00:50 · git 45baa2d (main, working tree dirty) · exit 0 · 60.7s
command     python -m scripts.backtest_study.f4_deployment.hedge_exposure
excerpt     verdict

```
CELL TALLY — population all   (no verdict is read from it)
  POOLED (not a stratum — the pooled trigger):
    UNDERPOWERED       9 cell(s)
  DIRECT:
    UNDERPOWERED       9 cell(s)
  CONSTITUENT:
    UNDERPOWERED       9 cell(s)
  Cell-level words only. The registration's study-level verdicts
  (MECHANISM-FOUND / NULL / CONTRARY / UNDERPOWERED / NOT EVALUABLE /
  MEASUREMENT-ONLY) are emitted ONCE, in the closing section, and only off the
  RATIFIED population — never from this tally and never per population.
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:45:35 · git e59356f (main, working tree dirty) · exit 0 · 78.7s
command     python -m scripts.backtest_study.f4_deployment.hedge_exposure
excerpt     verdict

```
CELL TALLY — population all   (no verdict is read from it)
  POOLED (not a stratum — the pooled trigger):
    UNDERPOWERED       9 cell(s)
  DIRECT:
    UNDERPOWERED       9 cell(s)
  CONSTITUENT:
    UNDERPOWERED       9 cell(s)
  Cell-level words only. The registration's study-level verdicts
  (MECHANISM-FOUND / NULL / CONTRARY / UNDERPOWERED / NOT EVALUABLE /
  MEASUREMENT-ONLY) are emitted ONCE, in the closing section, and only off the
  RATIFIED population — never from this tally and never per population.
```

