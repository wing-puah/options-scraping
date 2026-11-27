# structure_sweep — per-era record

**Question.** Holding the analysis's ticker, signal date and expiry fixed, would a different option structure (flipped, type-swapped, iron condor, iron butterfly, straddle, strangle or calendar) have made money on the same 2026 plays?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 61bda3a · sha 2bdbe13 — recorded 2026-10-26
<!-- key era=v4 sha=2bdbe13 inputs=61bda3a -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-26 01:06)
run         2026-10-26 01:06:15 · git 2bdbe13 (main, working tree dirty) · exit 0 · 61.7s
command     python -m scripts.backtest_study.f3_structure.structure_sweep
excerpt     verdict

```
VERDICT
  ARM F flipped                S1 n=306/82d  dR +0.078 [-0.039, +0.199]  Holm p 1.000  S2 n=  9  -> NULL
  ARM T type swap              S1 n= 38/30d  dR -0.093 [-0.442, +0.318]  Holm p 1.000  S2 n=248  -> NULL
  ARM C short iron condor      S1 n= 35/29d  dR +0.010 [-0.549, +0.349]  Holm p 1.000  S2 n=219  -> NULL
  ARM B short iron butterfly   S1 n= 62/40d  dR +0.724 [-0.022, +1.635]  Holm p 0.413  S2 n=247  -> NULL
  ARM D long straddle          S1 n= 97/53d  dR -0.015 [-0.182, +0.155]  Holm p 1.000  S2 n=221  -> NULL
  ARM G long strangle          S1 n= 82/47d  dR +0.016 [-0.208, +0.267]  Holm p 1.000  S2 n=208  -> NULL
  ARM K long ATM call calendar S1 n= 64/42d  dR -0.122 [-0.411, +0.137]  Holm p 1.000  S2 n=213  -> NULL
  PBO 0.159 (threshold < 0.5)   Holm family 7 arm(s), alpha 0.05
>>> structure_sweep WIDE-NET-NULL <<<
  Nothing ships whatever this prints; a CANDIDATE earns a forward registration.
```


## era v4 · inputs e7318a6 · sha f04686e — recorded 2026-11-27
<!-- key era=v4 sha=f04686e inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 12:12)
run         2026-11-27 14:40:50 · git f04686e (main, working tree clean) · exit 0 · 57.4s
command     python -m scripts.backtest_study.f3_structure.structure_sweep
excerpt     verdict

```
VERDICT
  ARM F flipped                S1 n=266/81d  dR +0.097 [-0.017, +0.215]  Holm p 0.633  S2 n=202  -> NULL
  ARM T type swap              S1 n= 34/28d  dR -0.076 [-0.459, +0.388]  Holm p 1.000  S2 n=260  -> NULL
  ARM C short iron condor      S1 n= 27/23d  dR +0.052 [-0.653, +0.465]  Holm p 1.000  S2 n=238  -> NULL
  ARM B short iron butterfly   S1 n= 52/35d  dR +0.791 [-0.101, +1.852]  Holm p 0.633  S2 n=283  -> NULL
  ARM D long straddle          S1 n= 83/44d  dR -0.004 [-0.180, +0.177]  Holm p 1.000  S2 n=269  -> NULL
  ARM G long strangle          S1 n= 64/38d  dR +0.027 [-0.212, +0.280]  Holm p 1.000  S2 n=274  -> NULL
  ARM K long ATM call calendar S1 n= 46/32d  dR -0.077 [-0.398, +0.205]  Holm p 1.000  S2 n=266  -> NULL
  PBO 0.180 (threshold < 0.5)   Holm family 7 arm(s), alpha 0.05
>>> structure_sweep WIDE-NET-NULL <<<
  Nothing ships whatever this prints; a CANDIDATE earns a forward registration.
```

