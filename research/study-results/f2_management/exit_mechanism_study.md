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
