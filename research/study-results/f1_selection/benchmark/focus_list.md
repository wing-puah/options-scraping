# focus_list — per-era record

**Question.** Would taking up to three Tier A/B picks a day from a fixed 14-ticker watchlist (semis, AI, GLD, QQQ and two traditional names) beat the card's own top three on the same dates, and beat random same-tier picks? The operator named the groups after trading these names, so only the forward read can confirm it.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v3 · inputs e66ed29 · sha abab7a3 — recorded 2026-11-15
<!-- key era=v3 sha=abab7a3 inputs=e66ed29 -->

population  406 results · 796 proxy · 1,607 analysis · 870 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-11-14 01:02)
run         2026-11-15 21:54:41 · git abab7a3 (main, working tree dirty) · exit 0 · 2.7s
command     python -m scripts.backtest_study.f1_selection.benchmark.focus_list
excerpt     verdict

```
VERDICT — v3 replication (same path)
  P1  gain -0.064  CI95 [-0.241, +0.096]  dates 64  ARM F positions 100
  criteria  1 n  2 n  3 Y  4 n  5 Y  6 n
>>> focus_list P1 v3 replication (same path; notes agreement, confirms nothing): NULL <<<
```


## era v4 · inputs 0984c38 · sha abab7a3 — recorded 2026-11-15
<!-- key era=v4 sha=abab7a3 inputs=0984c38 -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 870 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-11-14 01:02)
run         2026-11-15 21:54:32 · git abab7a3 (main, working tree dirty) · exit 0 · 6.4s
command     python -m scripts.backtest_study.f1_selection.benchmark.focus_list
excerpt     verdict

```
VERDICT
  P1  gain +0.140  CI95 [+0.061, +0.220]  dates 185  ARM F positions 289
  criteria  1 Y  2 Y  3 Y  4 Y  5 Y  6 Y
>>> focus_list P1 (ARM F minus ARM C, paired by date, in-sample v4): FOCUS-BEATS-CARD <<<
>>> focus_list FORWARD (one read from 2026-11-16): STILL-OPEN <<<
  In-sample only. The list was chosen after trading these names, so only the forward read can confirm it. Nothing ships.
```


## Graded by `study_review` — 2026-11-16

Two analysts and a validator graded the v4 in-sample report (sha abab7a3, tree dirty). They agree on every row. The review ran with `--skip-run`, so the one-shot forward read was not touched.

- **Verdict:** `FOCUS-BEATS-CARD` stands, in-sample only. GF0 to GF5 and criteria 1 to 6 are all met. The forward read is not evaluable and stays `STILL-OPEN`.
- **Fault in the report:** the second load prints `227 kept (include_pending)` and `1911 rows`, while the registration says pending rows are dropped at the loader. The report does not say which load built the arms. The arm totals match the registration's census.
- **Unmet expectation:** the registration expected `NULL` on v4.
