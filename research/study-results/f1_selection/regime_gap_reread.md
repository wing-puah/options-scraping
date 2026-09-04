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


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:20:49 · git c841a01 (main, working tree dirty) · exit 0 · 1.1s
command     python -m scripts.backtest_study.f1_selection.regime_gap_reread
excerpt     tail

```
    |delta| vs mfe_pct | side=debit                         n=  436  rho= 0.1341  p= 0.0050
    |delta| vs mae_pct | side=debit                         n=  436  rho=-0.1642  p= 0.0006
5c. real-priced bull_put iv_skew vs realized — all rows
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, all n=   66  rho= 0.0108  p= 0.9313
5c. real-priced bull_put iv_skew vs realized — post-13c
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, post-13c n=   66  rho= 0.0108  p= 0.9313
5d. bear_put_spread x iv_spread vs mae_pct — pooled (continuity check of Tier-C rule)
    iv_spread vs mae_pct | bear_put_spread, pooled          n=  196  rho=-0.0820  p= 0.2533
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:37:37 · git 25f3e27 (main, working tree dirty) · exit 0 · 1.2s
command     python -m scripts.backtest_study.f1_selection.regime_gap_reread
excerpt     tail

```
    |delta| vs mfe_pct | side=debit                         n=  772  rho= 0.0975  p= 0.0067
    |delta| vs mae_pct | side=debit                         n=  772  rho=-0.1964  p= 0.0000
5c. real-priced bull_put iv_skew vs realized — all rows
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, all n=  101  rho= 0.0944  p= 0.3476
5c. real-priced bull_put iv_skew vs realized — post-13c
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, post-13c n=  101  rho= 0.0944  p= 0.3476
5d. bear_put_spread x iv_spread vs mae_pct — pooled (continuity check of Tier-C rule)
    iv_spread vs mae_pct | bear_put_spread, pooled          n=  322  rho=-0.0550  p= 0.3250
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:36:46 · git e59356f (main, working tree dirty) · exit 0 · 1.1s
command     python -m scripts.backtest_study.f1_selection.regime_gap_reread
excerpt     tail

```
    |delta| vs mfe_pct | side=debit                         n=  877  rho= 0.0804  p= 0.0172
    |delta| vs mae_pct | side=debit                         n=  877  rho=-0.2038  p= 0.0000
5c. real-priced bull_put iv_skew vs realized — all rows
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, all n=  118  rho= 0.0960  p= 0.3012
5c. real-priced bull_put iv_skew vs realized — post-13c
    iv_skew vs realized_pnl_pct | real-priced bull_put_spread, post-13c n=  118  rho= 0.0960  p= 0.3012
5d. bear_put_spread x iv_spread vs mae_pct — pooled (continuity check of Tier-C rule)
    iv_spread vs mae_pct | bear_put_spread, pooled          n=  365  rho=-0.0686  p= 0.1912
```

