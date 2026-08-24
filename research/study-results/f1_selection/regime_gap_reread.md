# regime_gap_reread — per-era record

**Question.** Numbers only, no interpretation: build the pooled book and print the report.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:45:44 · git 53b7167 (main, working tree dirty) · exit 0 · 1.8s
command     python -m scripts.backtest_study.f1_selection.regime_gap_reread
excerpt     tail

```
    |delta| vs mfe_pct | side=debit                         n=  566  rho= 0.1931  p= 0.0000
    |delta| vs mae_pct | side=debit                         n=  566  rho=-0.1794  p= 0.0000
5c. real-priced bull_put iv_skew vs realized — all rows
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, all n=   78  rho= 0.2321  p= 0.0409
5c. real-priced bull_put iv_skew vs realized — post-13c
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, post-13c n=   53  rho=-0.0219  p= 0.8761
5d. bear_put_spread x iv_spread vs mae_pct — pooled (continuity check of Tier-C rule)
    iv_spread vs mae_pct | bear_put_spread, pooled          n=  380  rho=-0.2149  p= 0.0000
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:10:31 · git d47e227 (main, working tree dirty) · exit 0 · 1.7s
command     python -m scripts.backtest_study.f1_selection.regime_gap_reread
excerpt     tail

```
    |delta| vs mfe_pct | side=debit                         n=  392  rho= 0.1305  p= 0.0097
    |delta| vs mae_pct | side=debit                         n=  392  rho=-0.1610  p= 0.0014
5c. real-priced bull_put iv_skew vs realized — all rows
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, all n=   63  rho=-0.0133  p= 0.9177
5c. real-priced bull_put iv_skew vs realized — post-13c
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, post-13c n=   63  rho=-0.0133  p= 0.9177
5d. bear_put_spread x iv_spread vs mae_pct — pooled (continuity check of Tier-C rule)
    iv_spread vs mae_pct | bear_put_spread, pooled          n=  169  rho=-0.0662  p= 0.3928
```

