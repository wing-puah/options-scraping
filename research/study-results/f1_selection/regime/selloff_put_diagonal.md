# selloff_put_diagonal — per-era record

**Question.** On a SPY sell-off trigger (E-DD5: 5% below the 63-session high, disarmed on a close back above -2%), does a near ATM put plus a long-dated call diagonal, rolled three times, pay net of commission? Graded against zero, against the same package on calm weeks (ARM C), and for the put's own contribution.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 61bda3a · sha 102d6fb — recorded 2026-11-13
<!-- key era=v4 sha=102d6fb inputs=61bda3a -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-26 01:06)
run         2026-11-13 14:40:56 · git 102d6fb (main, working tree clean) · exit 0 · 35.3s
command     python -m scripts.backtest_study.f1_selection.regime.selloff_put_diagonal
excerpt     verdict

```
VERDICT
  ARM K vs zero          PAYS (PROVISIONAL)
  ARM K vs ARM C         NULL (PROVISIONAL)
  put contribution       NULL (PROVISIONAL)
  STUDY                  NO-EDGE (PROVISIONAL)
  FORWARD                STILL-OPEN  (0 forward triggers, 0 closed and priced; confirmation needs 3)
  Nothing ships from this study.
  trades -> backtests/study_output/selloff_put_diagonal-trades.csv
```


## Graded by `study_review` — 2026-11-16

Two analysts and a validator graded the 2026-11-13 report (v4, sha 102d6fb). They agree on every row. The validator found no transcription errors and no favourable rounding.

- **Verdict:** `NO-EDGE (PROVISIONAL)` stands. `ARM K` vs zero is met. `ARM K` vs `ARM C` (+0.119 [−0.004, +0.232]) and the put contribution are not met.
- **C4 (PBO) is not evaluable.** The registration asks for ten cells and the report built four. The PBO of 0.060 rests on those four.
- **Faults in the report:** secondary tokens such as `PAYS (SECONDARY)` print without the C2 and C3 inputs the registration requires. The registration says "eight non-primary cells" and lists nine.

## era v4 · inputs c4c967e · sha 52842b4 — recorded 2026-11-16
<!-- key era=v4 sha=52842b4 inputs=c4c967e -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 871 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-11-16 18:23)
run         2026-11-16 19:27:41 · git 52842b4 (main, working tree clean) · exit 0 · 35.6s
command     python -m scripts.backtest_study.f1_selection.regime.selloff_put_diagonal
excerpt     verdict

```
VERDICT
  ARM K vs zero          PAYS (PROVISIONAL)
  ARM K vs ARM C         NULL (PROVISIONAL)
  put contribution       NULL (PROVISIONAL)
  STUDY                  NO-EDGE (PROVISIONAL)
  FORWARD                STILL-OPEN  (1 forward triggers, 0 closed and priced; confirmation needs 3)
  Nothing ships from this study.
  trades -> backtests/study_output/selloff_put_diagonal-trades.csv
```


## era v4 · inputs 2f45ae6 · sha 436c8f7 — recorded 2026-11-26
<!-- key era=v4 sha=436c8f7 inputs=2f45ae6 -->

population  1,214 results · 2,286 proxy · 3,826 analysis · 878 spy_vix_daily_full · 703 BaselineDaily  (inputs dated 2026-11-26 11:38 … 2026-11-26 14:01)
run         2026-11-26 15:09:51 · git 436c8f7 (main, working tree clean) · exit 0 · 7.6s
command     python -m scripts.backtest_study.f1_selection.regime.selloff_put_diagonal
excerpt     verdict

```
VERDICT: NOT BUILT — AWAITING SCRAPE
  PRIMARY: NOT BUILT — AWAITING SCRAPE — 111 primary trades await a fetch.
  No outcome was computed for any arm: no R, no P&L, no CI.
  Operator-run steps, in order (none runs from here):
    1. python3 scripts/collector/study_legs/f1_selection/fetch_selloff_put_diagonal_legs.py --dry-run   (then --limit N)
    2. python3 scripts/backup_research_caches.py push
    3. re-run this study; a fetch can expose a nearer strike or prove an
       expiry unlisted, so steps 1-3 repeat until no primary trade awaits
  It does not run beside another option-cache writer: one writer.
```

