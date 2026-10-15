# spy_benchmark — per-era record

**Question.** Do the deployed picks beat a SPY call spread on the same dates: the ARM M1 wrap (ATM/+5%, the pick's own expiry, same entry day, same exit profile) on SPY instead of the pick's ticker? P2 of the 2026-10-13 plan; post hoc, and not a programme_gate input.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs a5f1fab · sha c8b1f4e — recorded 2026-10-15
<!-- key era=v4 sha=c8b1f4e inputs=a5f1fab -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 845 spy_vix_daily_full  (inputs dated 2026-10-06 23:39 … 2026-10-12 22:05)
run         2026-10-15 12:15:18 · git c8b1f4e (main, working tree dirty) · exit 0 · 16.5s
command     python -m scripts.backtest_study.f1_selection.benchmark.spy_benchmark
excerpt     verdict

```
VERDICT (headline basis, SB-UNIT = pick): DOES-NOT-BEAT
  Not a programme_gate input: recorded beside the gate, never changing it.
  pairs written to backtests/study_output/spy_benchmark-pairs.csv
```

