# tail_rebound_etf — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 0984c38 · sha d273f1a — recorded 2026-11-15
<!-- key era=v4 sha=d273f1a inputs=0984c38 -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 870 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-11-14 01:02)
run         2026-11-15 20:27:20 · git d273f1a (main, working tree dirty) · exit 0 · 17.0s
command     python -m scripts.backtest_study.f1_selection.regime.tail_rebound_etf
excerpt     verdict

```
VERDICT
  sample to 2026-11-15; 10000 cluster draws, seed 20261115
  >>> tail_rebound_etf QQQ-A21 (QQQ 21-session total return after an intraday 2x-VXN breach, first of each episode, vs unconditional, 2001 on): NO-ED…
  >>> tail_rebound_etf QQQ-B21 (QQQ 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 1999 on): NO-EDGE <<<
  >>> tail_rebound_etf SMH-A21 (SMH 21-session total return after an intraday 2x-VXN breach, first of each episode, vs unconditional, 2001 on): NO-ED…
  >>> tail_rebound_etf SMH-B21 (SMH 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 2000 on): NO-EDGE <<<
  >>> tail_rebound_etf SECONDARY (h = 5 and 63, Holm m=8): QQQ-A5 NO-EDGE QQQ-A63 NO-EDGE QQQ-B5 NO-EDGE QQQ-B63 NO-EDGE SMH-A5 NO-EDGE SMH-A63 UNDER…
  >>> tail_rebound_etf FORWARD (entries after the registration date): QQQ-A21 STILL-OPEN QQQ-B21 STILL-OPEN SMH-A21 STILL-OPEN SMH-B21 STILL-OPEN <<<
  REBOUND needs the 95% cluster-bootstrap CI on the excess wholly above 0 and a Holm p
  below 0.05 (co-primaries m=4; secondaries m=8); CONTINUATION the mirror. It prices no option.
  Nothing ships from this study (tail_rebound_etf.md).
```


## era v4 · inputs 2f45ae6 · sha 436c8f7 — recorded 2026-11-26
<!-- key era=v4 sha=436c8f7 inputs=2f45ae6 -->

population  1,214 results · 2,286 proxy · 3,826 analysis · 878 spy_vix_daily_full · 703 BaselineDaily  (inputs dated 2026-11-26 11:38 … 2026-11-26 14:01)
run         2026-11-26 15:10:29 · git 436c8f7 (main, working tree clean) · exit 0 · 3.7s
command     python -m scripts.backtest_study.f1_selection.regime.tail_rebound_etf
excerpt     verdict

```
VERDICT
  sample to 2026-11-15; 10000 cluster draws, seed 20261115
  >>> tail_rebound_etf QQQ-A21 (QQQ 21-session total return after an intraday 2x-VXN breach, first of each episode, vs unconditional, 2001 on): NO-ED…
  >>> tail_rebound_etf QQQ-B21 (QQQ 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 1999 on): NO-EDGE <<<
  >>> tail_rebound_etf SMH-A21 (SMH 21-session total return after an intraday 2x-VXN breach, first of each episode, vs unconditional, 2001 on): NO-ED…
  >>> tail_rebound_etf SMH-B21 (SMH 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 2000 on): NO-EDGE <<<
  >>> tail_rebound_etf SECONDARY (h = 5 and 63, Holm m=8): QQQ-A5 NO-EDGE QQQ-A63 NO-EDGE QQQ-B5 NO-EDGE QQQ-B63 NO-EDGE SMH-A5 NO-EDGE SMH-A63 UNDER…
  >>> tail_rebound_etf FORWARD (entries after the registration date): QQQ-A21 STILL-OPEN QQQ-B21 STILL-OPEN SMH-A21 STILL-OPEN SMH-B21 STILL-OPEN <<<
  REBOUND needs the 95% cluster-bootstrap CI on the excess wholly above 0 and a Holm p
  below 0.05 (co-primaries m=4; secondaries m=8); CONTINUATION the mirror. It prices no option.
  Nothing ships from this study (tail_rebound_etf.md).
```

