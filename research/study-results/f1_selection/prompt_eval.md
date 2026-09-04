# prompt_eval — per-era record

**Question.** Does a CANDIDATE analysis prompt beat the shipped one on the same dates under the shipped top-3/day ladder — paired dR, profit factor, hallucination rate, zero bear_call leaks — with the live dates, not the backfill, as the primary evidence?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs b995259 · sha 6640b3d — recorded 2026-09-04
<!-- key era=v4 sha=6640b3d inputs=b995259 -->

population  494 results · 1,144 proxy · 1,975 analysis · 817 spy_vix_daily_full  (inputs dated 2026-09-02 12:00 … 2026-09-02 14:53)
run         2026-09-03 09:49:32 · git 6640b3d (main, working tree dirty) · exit 0 · 42358.5s
command     python -m scripts.backtest_study.f1_selection.prompt_eval variance --dates backtests/prompt_eval/variance-dates.txt --repeats 3 --run-dir backtests/prompt_eval/variance-20260903
excerpt     tail

```
  floor = 0.0419  (max |paired ΔR| over 3 PROD-vs-PROD pairs)
  BINDING CONSEQUENCE: no |ΔR| smaller than this may be called a difference,
  in this study or in any write-up that cites it.
  The floor is estimated from 5 dates by design. It is a FLOOR, not a
  distributional claim, and is re-estimated whenever the model or engine changes.
  variance.json -> /Users/wing/claude_playground/options-trading/backtests/prompt_eval/variance-20260903/variance.json
  model calls 10   wall 42356s
  report -> /Users/wing/claude_playground/options-trading/backtests/prompt_eval/variance-20260903/report.txt
```

