# index_vrp — per-era record

**Question.** On the deployed ladder book's worst days and in its stress windows, does a monthly short SPY iron condor on real cached quotes lose money alongside the book?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs a5f1fab · sha 65e4d0d — recorded 2026-10-12
<!-- key era=v4 sha=65e4d0d inputs=a5f1fab -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 845 spy_vix_daily_full  (inputs dated 2026-10-06 23:39 … 2026-10-12 22:05)
run         2026-10-12 22:38:47 · git 65e4d0d (main, working tree dirty) · exit 0 · 68.6s
command     python -m scripts.backtest_study.f3_structure.index_vrp
excerpt     verdict

```
VERDICT
  M1 premium (context) SPY: NO-PREMIUM
  M1 premium (context) GLD: NO-PREMIUM
  book loses in 3 covered window(s) ['W2', 'W3', 'W4']; sleeve loses in 2 of them
  T1 -7.66 CI95 [-54.90, +44.31]; T4 max DD book 58.2% vs book+sleeve 55.7%
  >>> index_vrp NO-TAIL-LINK (SPY condor d0.16, mid fill, v4 deployed book) <<<
  secondary, GLD condor d0.16 mid vs deployed: NO-TAIL-LINK
  secondary, SPY condor d0.16 natural vs deployed: NO-TAIL-LINK
  secondary, SPY condor d0.30 mid vs deployed (contested delta): NO-TAIL-LINK
  secondary, SPY condor d0.16 mid vs stored book: NO-TAIL-LINK
  secondary, SPY condor d0.16 mid vs deployed at yml net 2.50 (NOT REGISTERED): NO-TAIL-LINK
  secondary, SPY condor d0.16 mid vs v3 deployed (replication): NO-TAIL-LINK
  secondary, graded read at T1 block 5: NO-TAIL-LINK
  secondary, graded read at T1 block 20: NO-TAIL-LINK
  Nothing ships.
```

