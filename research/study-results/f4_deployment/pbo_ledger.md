# pbo_ledger — per-era record

**Question.** The feasibility plan's trial ledger scored more than 70 account-sizing configurations against the 25% drawdown bar on one path. How likely is it that the one chosen as best, in particular (R, F2, $500), was luck?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha 89bf4e4 — recorded 2026-10-07
<!-- key era=v4 sha=89bf4e4 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-07 20:04:24 · git 89bf4e4 (main, working tree dirty) · exit 0 · 188.7s
command     python -m scripts.backtest_study.f4_deployment.pbo_ledger
excerpt     tail

```
  PRIMARY | ledger + ticker-cap + F3   N=63  PBO[total] 47.0%  PBO[maxdd] 0.2%  PBO[meanR] 33.6%  PBO[bar] 23.8%
  SECONDARY | ledger                   N=51  PBO[total] 71.5%  PBO[maxdd] 0.0%  PBO[meanR] 58.2%  PBO[bar] 40.6%
  SECONDARY | ledger + ticker-cap      N=59  PBO[total] 55.7%  PBO[maxdd] 0.0%  PBO[meanR] 47.5%  PBO[bar] 29.0%
  SECONDARY | ledger + ticker-cap + F3 N=63  PBO[total] 35.0%  PBO[maxdd] 0.0%  PBO[meanR] 33.9%  PBO[bar] 15.5%
  Caveats: one market path; CSCV assumes the S blocks are exchangeable,
  which serial dependence in open positions strains; many configurations
  differ by one knob, so their series are correlated and the effective N is
  smaller than the count. Nothing in this report is a shippable rule.
```

