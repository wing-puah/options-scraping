# dip_buy — per-era record

**Question.** Among non-vetoed Tier A/B positions, is meanR higher when SPY closed below its 50-day SMA on the signal date than when it closed above? Picked post hoc from 28 rules, so only signal dates from the holdout seal's start are graded.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha f59b776 — recorded 2026-10-12
<!-- key era=v4 sha=f59b776 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-12 20:26:14 · git f59b776 (main, working tree dirty) · exit 0 · 3.0s
command     python -m scripts.backtest_study.f1_selection.dip_buy
excerpt     verdict

```
VERDICT
  In-sample v4 and v3: post hoc context only. They carry no verdict.
  forward below arm: 0 of 30 dates, 0 of 60 positions
  forward above arm: 0 of 30 dates, 0 of 60 positions
  >>> dip_buy PRIMARY (forward, Tier A+B, below - above): STILL-OPEN <<<
  STILL-OPEN because the forward dates are sealed and no arm has reached its floor.
  The verdict of record is the first run printing a token other than STILL-OPEN; later runs are descriptive (dip_buy.md).
  Nothing ships from this study. A forward SUPPORTED lets the operator consider a deployment-rules change.
```

