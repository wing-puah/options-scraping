# exit_mechanism_study — per-era record

**Question.** The original grid: replay stored daily marks under alternative exit rules, real-priced rows only.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:45:53 · git 53b7167 (main, working tree dirty) · exit 0 · 2.1s
command     python -m scripts.backtest_study.f2_management.exit_mechanism_study --side debit
excerpt     tail

```
    per-month Δ vs prod: 2024-06:-1137  2024-07:-330  2024-08:+887  2024-12:-1005  2025-03:+427  2025-04:-1472  2025-05:+1802  2025-08:+60  2025-11:+…
    biggest movers (41 rows changed):
         -1230  2024-06-17 AAPL  bull_call_spread   time_exit($+273 d32) → stop_loss($-957 d36)
          -844  2024-12-19 MSTR  bull_call_spread   time_exit($+223 d33) → time_exit($-621 d37)
          -749  2025-04-21 XLE   bear_put_spread    time_exit($-532 d32) → dollar_stop($-1281 d36)
          +638  2024-08-22 NU    bear_put_spread    time_exit($-600 d45) → time_exit($+38 d51)
          +775  2024-08-12 META  bull_call_spread   time_exit($-821 d20) → time_exit($-46 d24)
         +1227  2025-05-15 COIN  bull_call_spread   time_exit($+220 d22) → profit_target($+1447 d24)
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:10:38 · git d47e227 (main, working tree dirty) · exit 0 · 2.1s
command     python -m scripts.backtest_study.f2_management.exit_mechanism_study --side debit
excerpt     tail

```
    per-month Δ vs prod: 2024-01:+570  2024-02:-300  2024-03:-1493  2024-04:-680  2024-10:-90  2025-01:+356  2025-02:+1712  2025-05:-810  2025-06:-47…
    biggest movers (21 rows changed):
         -1292  2024-03-15 ADBE  bear_put_spread    time_exit($+548 d31) → time_exit($-744 d36)
         -1102  2024-04-11 AAPL  bear_put_spread    time_exit($+111 d15) → stop_loss($-991 d16)
          -675  2025-05-19 IBIT  bull_call_spread   time_exit($-321 d20) → stop_loss($-996 d22)
          +455  2025-08-14 QQQ   bull_call_spread   time_exit($+639 d33) → profit_target($+1095 d37)
          +570  2024-01-29 PDD   bear_put_spread    time_exit($+261 d25) → time_exit($+831 d28)
         +1712  2025-02-04 GLD   bull_call_spread   time_exit($-108 d24) → profit_target($+1603 d27)
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:20:53 · git c841a01 (main, working tree dirty) · exit 0 · 1.2s
command     python -m scripts.backtest_study.f2_management.exit_mechanism_study --side debit
excerpt     tail

```
    per-month Δ vs prod: 2024-01:+570  2024-02:-300  2024-03:-263  2024-04:-680  2024-10:-90  2025-01:+356  2025-02:+1712  2025-05:-810  2025-06:-474…
    biggest movers (22 rows changed):
         -1292  2024-03-15 ADBE  bear_put_spread    time_exit($+548 d31) → time_exit($-744 d36)
         -1102  2024-04-11 AAPL  bear_put_spread    time_exit($+111 d15) → stop_loss($-991 d16)
          -675  2025-05-19 IBIT  bull_call_spread   time_exit($-321 d20) → stop_loss($-996 d22)
          +570  2024-01-29 PDD   bear_put_spread    time_exit($+261 d25) → time_exit($+831 d28)
         +1230  2024-03-13 IWM   bear_put_spread    time_exit($-492 d19) → time_exit($+738 d22)
         +1712  2025-02-04 GLD   bull_call_spread   time_exit($-108 d24) → profit_target($+1603 d27)
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 23:00:00 · git 25f3e27 (main, working tree dirty) · exit 0 · 5.1s
command     python -m scripts.backtest_study.f2_management.exit_mechanism_study --side debit
excerpt     tail

```
    per-month Δ vs prod: 2024-01:+570  2024-02:-300  2024-03:-263  2024-04:-680  2024-05:-688  2024-06:+453  2024-07:-45  2024-08:-751  2024-09:-1641…
    biggest movers (46 rows changed):
         -1292  2024-03-15 ADBE  bear_put_spread    time_exit($+548 d31) → time_exit($-744 d36)
         -1102  2024-04-11 AAPL  bear_put_spread    time_exit($+111 d15) → stop_loss($-991 d16)
          -770  2025-10-17 TSLA  bear_put_spread    time_exit($-402 d31) → dollar_stop($-1171 d34)
          +570  2024-01-29 PDD   bear_put_spread    time_exit($+261 d25) → time_exit($+831 d28)
         +1230  2024-03-13 IWM   bear_put_spread    time_exit($-492 d19) → time_exit($+738 d22)
         +1712  2025-02-04 GLD   bull_call_spread   time_exit($-108 d24) → profit_target($+1603 d27)
```

