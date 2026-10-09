# mechanical_benchmark — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha 167f963 — recorded 2026-10-09
<!-- key era=v4 sha=167f963 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-09 23:13:19 · git 167f963 (worktree-wf_c8ce3d2e-793-7, working tree dirty) · exit 0 · 152.4s
command     python -m scripts.backtest_study.f1_selection.mechanical_benchmark
excerpt     verdict

```
VERDICT: NOT BUILT — AWAITING SCRAPE
  The census is the recorded result. No outcome column was read.
  Operator-run steps, in order (each resumable; none runs from here):
    0. universe files for 4 dates: python3 -m scripts.analysis_pipeline --skip-llm --date <D> (no LLM, no Sheets write)
    1. stock bars for 1978 universe tickers: python3 scripts/collector/fetch_underlying_ohlc.py --tickers <list from python3 scripts/collector/fetch_…
    2. option legs: python3 scripts/collector/fetch_mechanical_legs.py --dry-run   (then --limit N)
    3. python3 scripts/backup_research_caches.py push
    4. re-run this study; a fetch can expose nearer strikes, so steps 2-4 repeat until nothing awaits
```

