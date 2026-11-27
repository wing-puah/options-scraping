# spy_dip_forward — per-era record

**Question.** Do SPY entries at the close after a close below the 50-day SMA (the live dip flag) beat entries after other closes over the next 21 sessions, in excess of T-bills and net of 2 bps a side, on the 2010-2025 holdout?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs e7318a6 · sha e0b58d2 — recorded 2026-11-27
<!-- key era=v4 sha=e0b58d2 inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-27 23:56:21 · git e0b58d2 (main, working tree dirty) · exit 0 · 22.7s
command     python -m scripts.backtest_study.f1_selection.signal.spy_dip_forward --refresh
excerpt     verdict

```
VERDICT
  HOLDOUT: 4002 SMA50 entries (D 2010-01-04 -> 2025-11-28); SPY sessions to 2026-11-25; 10000 block draws (L 63), seed 20261127
  >>> spy_dip_forward P (SPY 21-session excess return, entry the close after a close below the 50-day SMA, vs other entries, holdout 2010-2025, Holm …
  >>> spy_dip_forward T (worst-decile 21-session drawdown, dip minus non-dip, holdout, Holm m=3): DEEPER-DRAWDOWN <<<
  >>> spy_dip_forward Z (dips above minus below the 200-day SMA, 21 sessions, holdout, Holm m=3): NULL <<<
  >>> spy_dip_forward DISCOVERY (to 2009-12-31): P +0.035% [-1.089%, +1.151%] T -4.652% [-8.764%, -1.373%] Z +1.716% [-0.271%, +3.629%] <<<
  >>> spy_dip_forward PRE-BOOK (2010-2023): P +1.288% [+0.420%, +2.090%] <<<
  >>> spy_dip_forward PBO (12 cells, S=16, 1993-2025): 0.0720 <<<
  >>> spy_dip_forward 2026 (contaminated, not graded): P +1.826% [+0.653%, +5.331%], 54 dip entries <<<
  >>> spy_dip_forward FORWARD (entries after the registration date): P STILL-OPEN T STILL-OPEN Z STILL-OPEN <<<
  SUPPORTED needs the HOLDOUT CI wholly above 0 with a Holm-adjusted p below 0.05,
  positive DISCOVERY and PRE-BOOK point estimates, and a PBO of at most 0.50.
  Levels are net of 4 bps round trip, in excess of T-bills. Nothing ships from this
  study (spy_dip_forward.md).
```


## era v4 · inputs e7318a6 · sha 5dc8afe — recorded 2026-11-28
<!-- key era=v4 sha=5dc8afe inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-28 01:01:53 · git 5dc8afe (main, working tree clean) · exit 0 · 18.8s
command     python -m scripts.backtest_study.f1_selection.signal.spy_dip_forward
excerpt     verdict

```
VERDICT
  HOLDOUT: 4002 SMA50 entries (D 2010-01-04 -> 2025-11-28); SPY sessions to 2026-11-25; 10000 block draws (L 63), seed 20261127
  >>> spy_dip_forward P (SPY 21-session excess return, entry the close after a close below the 50-day SMA, vs other entries, holdout 2010-2025, Holm …
  >>> spy_dip_forward T (worst-decile 21-session drawdown, dip minus non-dip, holdout, Holm m=3): DEEPER-DRAWDOWN <<<
  >>> spy_dip_forward Z (dips above minus below the 200-day SMA, 21 sessions, holdout, Holm m=3): NULL <<<
  >>> spy_dip_forward DISCOVERY (to 2009-12-31): P +0.035% [-1.089%, +1.151%] T -4.652% [-8.764%, -1.373%] Z +1.716% [-0.271%, +3.629%] <<<
  >>> spy_dip_forward PRE-BOOK (2010-2023): P +1.288% [+0.420%, +2.090%] <<<
  >>> spy_dip_forward PBO (12 cells, S=16, 1993-2025): 0.0720 <<<
  >>> spy_dip_forward 2026 (contaminated, not graded): P +1.826% [+0.653%, +5.331%], 54 dip entries <<<
  >>> spy_dip_forward FORWARD (entries after the registration date): P STILL-OPEN T STILL-OPEN Z STILL-OPEN <<<
  SUPPORTED needs the HOLDOUT CI wholly above 0 with a Holm-adjusted p below 0.05,
  positive DISCOVERY and PRE-BOOK point estimates, and a PBO of at most 0.50.
  Levels are net of 4 bps round trip, in excess of T-bills. Nothing ships from this
  study (spy_dip_forward.md).
```

