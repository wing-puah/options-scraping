# vol_expansion_long_vol — per-era record

**Question.** After a SPY E-VOL onset, does a long ATM straddle or a 1x2 backspread, bought at the next close and sold five sessions later, make money net of commission, and more than the same structure opened on a calm week?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs e7318a6 · sha ab21a3a — recorded 2026-11-27
<!-- key era=v4 sha=ab21a3a inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-27 20:02:18 · git ab21a3a (main, working tree dirty) · exit 0 · 17.7s
command     python -m scripts.backtest_study.f3_structure.vol_expansion_long_vol
excerpt     verdict

```
VERDICT
  NOT BUILT — AWAITING SCRAPE — 498 headline arm-entries (onsets and ARM C) await a fetch.
  No outcome was computed for any arm: no R, no P&L, no CI.
>>> vol_expansion_long_vol ARM S (ATM straddle after E-VOL onset, D+1 close to D+6 close, monthly ~30 DTE, 2022-03-01 to 2026-09-22): NOT BUILT — AWA…
>>> vol_expansion_long_vol ARM BC (call 1x2 -1 ATM +2 at 1.05, same): NOT BUILT — AWAITING SCRAPE — VIX direction after 23 in-window onsets was print…
>>> vol_expansion_long_vol ARM BP (put 1x2 -1 ATM +2 at 0.95, same): NOT BUILT — AWAITING SCRAPE — VIX direction after 23 in-window onsets was printe…
>>> vol_expansion_long_vol PBO (12 cells, gates all three arms): not computed <<<
>>> vol_expansion_long_vol FORWARD (onsets from 2026-11-27): ARM S STILL-OPEN ARM BC STILL-OPEN ARM BP STILL-OPEN <<<
  forward: 0 forward onsets; floor 20 priced trades per arm and 60 calm weeks per column
  Operator-run steps, in order (none runs from here):
    1. python3 scripts/collector/study_legs/f3_structure/fetch_vol_expansion_legs.py --dry-run --list   (then the real fetch, --scope primary)
    2. python3 scripts/backup_research_caches.py push
    3. re-run this study; a fetch can prove a strike unlisted and expose the next,
       so steps 1-3 repeat until no headline entry awaits; then --scope all
  It does not run beside another option-cache writer: one writer.
  Nothing ships from this study.
```

**In plain words (2026-11-27).** The study is built but not yet graded. Its in-sample
window is onset dates 2022-03-01 to 2026-09-22.

- **The verdict.** Every arm prints `NOT BUILT — AWAITING SCRAPE`. The report says "No
  outcome was computed for any arm: no R, no P&L, no CI."
- **Why.** The strikes are walked on a fixed $1 step. The SPY cache mostly holds a $5
  grid, so most headline legs are not cached yet.
- **The census.** Both gates that read data passed: GE, and GL with 23 shared onsets
  identical in both label tables.

| Census item | Count |
|---|---|
| Onsets in the window, all candidate entries | 28 |
| Calm weeks, candidate entries | 175 |
| Headline arm-entries awaiting a fetch | 498 |
| Contracts to fetch, headline scope | 449 |
| Contracts to fetch, every cell | 489 |

- **Forward.** `ARM S STILL-OPEN ARM BC STILL-OPEN ARM BP STILL-OPEN`, with no forward onset
  yet.
- **What comes next.** The fetch is the operator's call. Nothing ships.


## era v4 · inputs e7318a6 · sha 402e850 — recorded 2026-11-27
<!-- key era=v4 sha=402e850 inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-27 22:29:22 · git 402e850 (main, working tree clean) · exit 0 · 83.8s
command     python -m scripts.backtest_study.f3_structure.vol_expansion_long_vol
excerpt     verdict

```
VERDICT
>>> vol_expansion_long_vol ARM S (ATM straddle after E-VOL onset, D+1 close to D+6 close, monthly ~30 DTE, 2022-03-01 to 2026-09-22): NULL (half-widt…
>>> vol_expansion_long_vol ARM BC (call 1x2 -1 ATM +2 at 1.05, same): NULL (half-width 0.067) — VIX direction after 23 in-window onsets was printed b…
>>> vol_expansion_long_vol ARM BP (put 1x2 -1 ATM +2 at 0.95, same): CONTRARY — VIX direction after 23 in-window onsets was printed before registrati…
>>> vol_expansion_long_vol PBO (12 cells, gates all three arms): 0.572 <<<
>>> vol_expansion_long_vol FORWARD (onsets from 2026-11-27): ARM S STILL-OPEN ARM BC STILL-OPEN ARM BP STILL-OPEN <<<
  A long-straddle `CONTRARY` is not evidence for selling straddles, because no short side is graded.
  A backspread result says nothing about tail loss beyond five sessions or about margin.
  Nothing ships from this study.
  trades -> backtests/study_output/vol_expansion_long_vol-trades.csv
```

