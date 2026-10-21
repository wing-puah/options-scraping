# mechanical_benchmark — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha 167f963 — recorded 2026-10-09
<!-- key era=v4 sha=167f963 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-09 23:13:19 · git 167f963 (worktree-wf_c8ce3d2e-793-7, working tree dirty) · exit 0 · 152.4s
command     python -m scripts.backtest_study.f1_selection.benchmark.mechanical_benchmark
excerpt     verdict

```
VERDICT: NOT BUILT — AWAITING SCRAPE
  The census is the recorded result. No outcome column was read.
  Operator-run steps, in order (each resumable; none runs from here):
    0. universe files for 4 dates: python3 -m scripts.analysis_pipeline --skip-llm --date <D> (no LLM, no Sheets write)
    1. stock bars for 1978 universe tickers: python3 scripts/collector/history/fetch_underlying_ohlc.py --tickers <list from python3 scripts/collector/fetch_…
    2. option legs: python3 scripts/collector/study_legs/fetch_mechanical_legs.py --dry-run   (then --limit N)
    3. python3 scripts/backup_research_caches.py push
    4. re-run this study; a fetch can expose nearer strikes, so steps 2-4 repeat until nothing awaits
```


## era v4 · inputs a5f1fab · sha 4536515 — recorded 2026-10-14
<!-- key era=v4 sha=4536515 inputs=a5f1fab -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 845 spy_vix_daily_full  (inputs dated 2026-10-06 23:39 … 2026-10-12 22:05)
run         2026-10-14 13:44:28 · git 4536515 (main, working tree dirty) · exit 0 · 58.9s
command     python -m scripts.backtest_study.f1_selection.benchmark.mechanical_benchmark
excerpt     verdict

```
VERDICT (headline basis): SAME-TICKER READ — ARM U NOT BUILT
  ARM M1  C0 Y  C1 n  C2 n  clears C0-C2 n  CONTRARY Y
  ARM M2  C0 Y  C1 n  C2 n  clears C0-C2 n  CONTRARY n
  ARM U is not built, so no study-level verdict prints: every one of them
  also says something about ARM U. C3, C4 and C5 are graded on ARM U and
  are not read.
  CONTRARY condition met on ARM M1: surface to the operator before any further study runs.
  M2L is a declared secondary and carries no verdict.
  pairs written to backtests/study_output/mechanical_benchmark-pairs.csv (no ARM U rows)
```


## era v4 · inputs a5f1fab · sha c8b1f4e — recorded 2026-10-15
<!-- key era=v4 sha=c8b1f4e inputs=a5f1fab -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 845 spy_vix_daily_full  (inputs dated 2026-10-06 23:39 … 2026-10-12 22:05)
run         2026-10-15 12:14:07 · git c8b1f4e (main, working tree dirty) · exit 0 · 69.6s
command     python -m scripts.backtest_study.f1_selection.benchmark.mechanical_benchmark
excerpt     verdict

```
VERDICT (headline basis): SAME-TICKER READ — ARM U NOT BUILT
  ARM M1  C0 Y  C1 n  C2 n  clears C0-C2 n  CONTRARY Y
  ARM M2  C0 Y  C1 n  C2 n  clears C0-C2 n  CONTRARY n
  ARM U is not built, so no study-level verdict prints: every one of them
  also says something about ARM U. C3, C4 and C5 are graded on ARM U and
  are not read.
  CONTRARY condition met on ARM M1: surface to the operator before any further study runs.
  M2L is a declared secondary and carries no verdict.
  pairs written to backtests/study_output/mechanical_benchmark-pairs.csv (no ARM U rows)
```


## era v4 · inputs 75061b4 · sha d55d1cb — recorded 2026-10-21
<!-- key era=v4 sha=d55d1cb inputs=75061b4 -->

population  1,103 results · 2,142 proxy · 3,546 analysis · 852 spy_vix_daily_full  (inputs dated 2026-10-21 14:30 … 2026-10-21 14:48)
run         2026-10-21 14:48:15 · git d55d1cb (main, working tree clean) · exit 0 · 152.0s
command     python -m scripts.backtest_study.f1_selection.benchmark.mechanical_benchmark
excerpt     verdict

```
VERDICT: NOT BUILT — AWAITING SCRAPE
  The census is the recorded result. No outcome column was read.
  Operator-run steps, in order (each resumable; none runs from here):
    0. universe files for 2 dates: python3 -m scripts.analysis_pipeline --skip-llm --date <D> (no LLM, no Sheets write)
    1. stock bars for 70 universe tickers: python3 scripts/collector/history/fetch_underlying_ohlc.py --tickers <list from python3 scripts/collector/…
    2. option legs: python3 scripts/collector/study_legs/fetch_mechanical_legs.py --dry-run   (then --limit N)
    3. python3 scripts/backup_research_caches.py push
    4. re-run this study; a fetch can expose nearer strikes, so steps 2-4 repeat until nothing awaits
```


## era v4 · inputs 75061b4 · sha 87c5dbd — recorded 2026-10-21
<!-- key era=v4 sha=87c5dbd inputs=75061b4 -->

population  1,103 results · 2,142 proxy · 3,546 analysis · 852 spy_vix_daily_full  (inputs dated 2026-10-21 14:30 … 2026-10-21 14:48)
run         2026-10-21 15:50:01 · git 87c5dbd (main, working tree clean) · exit 0 · 127.0s
command     python -m scripts.backtest_study.f1_selection.benchmark.mechanical_benchmark
excerpt     verdict

```
VERDICT: NOT BUILT — AWAITING SCRAPE
  The census is the recorded result. No outcome column was read.
  Operator-run steps, in order (each resumable; none runs from here):
    0. universe files for 2 dates: python3 -m scripts.analysis_pipeline --skip-llm --date <D> (no LLM, no Sheets write)
    1. stock bars for 70 universe tickers: python3 scripts/collector/history/fetch_underlying_ohlc.py --tickers <list from python3 scripts/collector/…
    2. option legs: python3 scripts/collector/study_legs/fetch_mechanical_legs.py --dry-run   (then --limit N)
    3. python3 scripts/backup_research_caches.py push
    4. re-run this study; a fetch can expose nearer strikes, so steps 2-4 repeat until nothing awaits
```


## era v4 · inputs 75061b4 · sha 2820565 — recorded 2026-10-21
<!-- key era=v4 sha=2820565 inputs=75061b4 -->

population  1,103 results · 2,142 proxy · 3,546 analysis · 852 spy_vix_daily_full  (inputs dated 2026-10-21 14:30 … 2026-10-21 16:32)
run         2026-10-21 16:43:01 · git 2820565 (main, working tree clean) · exit 0 · 84.8s
command     python -m scripts.backtest_study.f1_selection.benchmark.mechanical_benchmark
excerpt     verdict

```
VERDICT: NOT BUILT — AWAITING SCRAPE
  The census is the recorded result. No outcome column was read.
  Operator-run steps, in order (each resumable; none runs from here):
    0. universe files for 2 dates: python3 -m scripts.analysis_pipeline --skip-llm --date <D> (no LLM, no Sheets write)
    1. stock bars for 70 universe tickers: python3 scripts/collector/history/fetch_underlying_ohlc.py --tickers <list from python3 scripts/collector/…
    2. option legs: python3 scripts/collector/study_legs/fetch_mechanical_legs.py --dry-run   (then --limit N)
    3. python3 scripts/backup_research_caches.py push
    4. re-run this study; a fetch can expose nearer strikes, so steps 2-4 repeat until nothing awaits
```

