# tail_rebound — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 0984c38 · sha d273f1a — recorded 2026-11-15
<!-- key era=v4 sha=d273f1a inputs=0984c38 -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 870 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-11-14 01:02)
run         2026-11-15 20:02:23 · git d273f1a (main, working tree dirty) · exit 0 · 11.7s
command     python -m scripts.backtest_study.f1_selection.regime.tail_rebound
excerpt     verdict

```
VERDICT
  sample 1993-01-29 -> 2026-11-15; 10000 cluster draws, seed 20261115
  >>> tail_rebound A21 (SPY 21-session total return after an intraday 2x-VIX breach, first of each episode, vs unconditional, 1993 on): NO-EDGE <<<
  >>> tail_rebound B21 (SPY 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 1993 on): NO-EDGE <<<
  >>> tail_rebound SECONDARY (h = 5 and 63, Holm m=4): A5 NO-EDGE A63 NO-EDGE B5 NO-EDGE B63 NO-EDGE <<<
  >>> tail_rebound FORWARD (entries after the registration date): A21 STILL-OPEN B21 STILL-OPEN <<<
  REBOUND needs the 95% cluster-bootstrap CI on the excess wholly above 0 and a Holm p
  below 0.05 (A21/B21 m=2; secondaries m=4); CONTINUATION the mirror. It prices no option.
  Nothing ships from this study (tail_rebound.md).
```


## era v4 · inputs 2f45ae6 · sha 436c8f7 — recorded 2026-11-26
<!-- key era=v4 sha=436c8f7 inputs=2f45ae6 -->

population  1,214 results · 2,286 proxy · 3,826 analysis · 878 spy_vix_daily_full · 703 BaselineDaily  (inputs dated 2026-11-26 11:38 … 2026-11-26 14:01)
run         2026-11-26 15:10:25 · git 436c8f7 (main, working tree clean) · exit 0 · 2.3s
command     python -m scripts.backtest_study.f1_selection.regime.tail_rebound
excerpt     verdict

```
VERDICT
  sample 1993-01-29 -> 2026-11-15; 10000 cluster draws, seed 20261115
  >>> tail_rebound A21 (SPY 21-session total return after an intraday 2x-VIX breach, first of each episode, vs unconditional, 1993 on): NO-EDGE <<<
  >>> tail_rebound B21 (SPY 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 1993 on): NO-EDGE <<<
  >>> tail_rebound SECONDARY (h = 5 and 63, Holm m=4): A5 NO-EDGE A63 NO-EDGE B5 NO-EDGE B63 NO-EDGE <<<
  >>> tail_rebound FORWARD (entries after the registration date): A21 STILL-OPEN B21 STILL-OPEN <<<
  REBOUND needs the 95% cluster-bootstrap CI on the excess wholly above 0 and a Holm p
  below 0.05 (A21/B21 m=2; secondaries m=4); CONTINUATION the mirror. It prices no option.
  Nothing ships from this study (tail_rebound.md).
```


## era v4 · inputs e7318a6 · sha f04686e — recorded 2026-11-27
<!-- key era=v4 sha=f04686e inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 12:12)
run         2026-11-27 14:20:48 · git f04686e (main, working tree clean) · exit 0 · 2.6s
command     python -m scripts.backtest_study.f1_selection.regime.tail_rebound
excerpt     verdict

```
VERDICT
  sample 1993-01-29 -> 2026-11-15; 10000 cluster draws, seed 20261115
  >>> tail_rebound A21 (SPY 21-session total return after an intraday 2x-VIX breach, first of each episode, vs unconditional, 1993 on): NO-EDGE <<<
  >>> tail_rebound B21 (SPY 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 1993 on): NO-EDGE <<<
  >>> tail_rebound SECONDARY (h = 5 and 63, Holm m=4): A5 NO-EDGE A63 NO-EDGE B5 NO-EDGE B63 NO-EDGE <<<
  >>> tail_rebound FORWARD (entries after the registration date): A21 STILL-OPEN B21 STILL-OPEN <<<
  REBOUND needs the 95% cluster-bootstrap CI on the excess wholly above 0 and a Holm p
  below 0.05 (A21/B21 m=2; secondaries m=4); CONTINUATION the mirror. It prices no option.
  Nothing ships from this study (tail_rebound.md).
```

