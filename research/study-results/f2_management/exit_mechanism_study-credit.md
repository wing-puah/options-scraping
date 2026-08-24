# exit_mechanism_study-credit — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:20:55 · git c841a01 (main, working tree dirty) · exit 0 · 1.2s
command     python -m scripts.backtest_study.f2_management.exit_mechanism_study --side credit
excerpt     tail

```
    per-month Δ vs prod: 2024-02:-326  2024-03:-651  2024-04:-471  2024-07:-408  2024-10:-907  2024-11:+937  2025-06:-87  2025-08:-1143
    biggest movers (17 rows changed):
         -1143  2025-08-14 ETHA  bull_put_spread    profit_target($+1436 d37) → underlying_stop($+292 d3)
          -800  2024-10-07 TSLA  bull_put_spread    profit_target($+376 d13) → underlying_stop($-424 d12)
          -758  2024-03-15 SMH   bull_put_spread    profit_target($+290 d36) → underlying_stop($-467 d25)
          +621  2024-03-14 BITO  bull_put_spread    expired($-846 d46) → underlying_stop($-225 d3)
          +857  2024-03-25 IWM   bear_put_spread    expired($-933 d24) → underlying_stop($-76 d1)
          +937  2024-11-21 TSLA  bull_put_spread    dollar_stop($-1363 d77) → underlying_stop($-425 d69)
```

