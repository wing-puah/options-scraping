# exit_mark_clock — per-era record

**Question.** On a junk-quote day, does marking a two-sided leg at its closing mid, instead of its last trade or a carried mark, make exits that earn more on new data?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 2f45ae6 · sha 436c8f7 — recorded 2026-11-26
<!-- key era=v4 sha=436c8f7 inputs=2f45ae6 -->

population  1,214 results · 2,286 proxy · 3,826 analysis · 878 spy_vix_daily_full · 703 BaselineDaily  (inputs dated 2026-11-26 11:38 … 2026-11-26 14:01)
run         2026-11-26 15:17:51 · git 436c8f7 (main, working tree clean) · exit 0 · 4.3s
command     python -m scripts.backtest_study.f2_management.exit_mark_clock
excerpt     verdict

```
VERDICT
  PRIMARY   UNDERPOWERED  — G-THIN not met: 11 affected dates (need 25)
  SECONDARY UNDERPOWERED  — G-THIN not met: 0 affected dates (need 25)
  The SECONDARY verdict never moves the PRIMARY one. Nothing ships by itself;
  CANDIDATE lets the operator rule on the junk-day mark.
  positions CSV: backtests/study_output/exit_mark_clock-latest.csv
```

