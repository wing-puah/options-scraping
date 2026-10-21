# regime_confirm — per-era record

**Question.** When SPY, QQQ, IWM or ^GSPC first turns mech BEAR after 20 quiet sessions, does waiting for a 3-session BEAR streak, with 2 of 4 stress conditions agreeing (RC1) or the index below its own 200-day SMA (RC-200), pick out the flips followed by a 10% fall within 60 sessions more often than every flip does?

**Data.** This study reads no book export. It reads yfinance daily closes cached in `backtests/regime_confirm/`. The era and population lines below are the runner's standard header, not this study's inputs.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 7bd1348 · sha a323040 — recorded 2026-10-21
<!-- key era=v4 sha=a323040 inputs=7bd1348 -->

population  1,093 results · 2,131 proxy · 3,546 analysis · 852 spy_vix_daily_full  (inputs dated 2026-10-21 10:51 … 2026-10-21 13:34)
run         2026-10-21 13:43:45 · git a323040 (main, working tree dirty) · exit 0 · 26.4s
command     python -m scripts.backtest_study.f1_selection.regime.regime_confirm
excerpt     verdict

```
VERDICT
  RC-IS (SPY 1993-2026) is spent: post hoc context, no token.
  events and clusters per graded arm and scope:
    RC1     on RC-H2   (co-primary) events= 35 clusters= 23  rate 34.3% vs RC0 21.2% (RC0 n=146)  diff +0.131 [-0.034, +0.327]
    RC-200  on RC-H1   (co-primary) events= 22 clusters= 19  rate 13.6% vs RC0 9.3% (RC0 n=118)  diff +0.043 [-0.074, +0.182]
    RC1     on RC-FWD  (forward   ) events=  0 clusters=  0  rate —% vs RC0 —% (RC0 n=0)  diff — [—, —]
    RC-P    on RC-H1   (secondary ) events= 80 clusters= 69  rate 6.2% vs RC0 9.3% (RC0 n=118)  diff -0.031 [-0.078, +0.010]
    RC-P    on RC-H2   (secondary ) events= 76 clusters= 37  rate 27.6% vs RC0 21.2% (RC0 n=146)  diff +0.064 [-0.006, +0.145]
    RC-C    on RC-H2   (secondary ) events= 56 clusters= 29  rate 32.1% vs RC0 21.2% (RC0 n=146)  diff +0.109 [+0.008, +0.226]
    RC-200  on RC-H2   (secondary ) events= 20 clusters= 13  rate 30.0% vs RC0 21.2% (RC0 n=146)  diff +0.088 [-0.100, +0.350]
  secondary family, BH at q < 0.05 (printed, no verdict; an UNDERPOWERED member enters at p = 1):
    RC-P    on RC-H1   token NULL         p=0.1476  BH q=0.1968  q >= 0.05
    RC-P    on RC-H2   token NULL         p=0.0758  BH q=0.1516  q >= 0.05
    RC-C    on RC-H2   token SUPPORTED    p=0.0312  BH q=0.1248  q >= 0.05
    RC-200  on RC-H2   token NULL         p=0.3960  BH q=0.3960  q >= 0.05
  >>> regime_confirm RC1 on RC-H2 (QQQ+IWM, co-primary): NULL <<<
  >>> regime_confirm RC-200 on RC-H1 (^GSPC 1950-1992, co-primary): NULL <<<
  >>> regime_confirm RETROSPECTIVE: RETRO-NULL <<<
  >>> regime_confirm FORWARD (RC1 on RC-FWD, flips after 2026-10-21): STILL-OPEN <<<
  The verdict of record is the first run printing a retrospective token, and the first forward run printing a token other than STILL-OPEN (regime_con…
  Nothing ships from this study.
```

