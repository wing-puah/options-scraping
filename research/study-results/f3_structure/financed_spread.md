# financed_spread — per-era record

**Question.** Does financing a book debit vertical with a credit position pay — an opposite-delta credit spread, a naked short leg, or a same-direction credit vertical?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 · inputs cd647ce · sha bfcd512 — recorded 2026-08-19
<!-- key era=v3 sha=bfcd512 inputs=cd647ce -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 807 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-08-19 11:10)
run         2026-08-19 17:11:08 · git bfcd512 (main, working tree dirty) · exit 0 · 144.8s
command     python -m scripts.backtest_study.f3_structure.financed_spread
excerpt     matched

```
  POWER-STOPPED — its n is printed and NO criterion is evaluated on it. This
  POWER-STOPPED, and nothing below quotes its mean.
    POWER-STOPPED  G0 stopped the cell; census published, no re-run
```


## era v3 · inputs cd647ce · sha bfcd512 (2nd run, post-scrape) — hand-recorded 2026-08-19
<!-- key era=v3 sha=bfcd512 inputs=cd647ce run=2 hand-recorded: the recorder's
     (era, sha) dedup key collides with the same-day pre-scrape run on the same
     dirty tree; this section is appended by hand in the tool's format so the
     post-scrape F4 result is not silently unrecorded. -->

run         2026-08-19 ~22:15 · git bfcd512 (main, working tree dirty) · exit 0
command     python -m scripts.backtest_study run financed_spread --era v3
difference  fin_diag scrape landed between runs (897+10 contracts fetched,
            171 unlisted/expired); F0–F3 unchanged, F4 cells now priced.

```
VERDICTS

  F0 own           NULL
  F1 off1          NULL
  F1 off2          NULL
  F2 off1          NULL
  F2 off2          NULL
  F3 off1          NULL
  F3 off2          NULL
  F4-d10 pt50      NULL
  F4-d10 $100      NULL
  F4-d10 hold      NULL
  F4-d20 pt50      NULL
  F4-d20 $100      NULL
  F4-d20 hold      CANDIDATE

--- F4-d20 hold  —  CANDIDATE -----------------------------------------------
  [PASS] 1 paired dR > 0, CI excludes zero        dR +0.176  CI [+0.015, +0.354]
  [PASS] 2 every LOO fold positive                MIN +0.143 over 74 folds (share+ 100%)
  [PASS] 3 window cuts + ex-BOTH                  ex_2025_mar_apr +0.259  ex_2026_feb_apr +0.073  ex_BOTH +0.148
  [PASS] 4 sign-stable every year                 2024 +0.019  2025 +0.098  2026 +0.374
  [PASS] 5 right-signed both pricing tiers        real n=49 dR +0.060  tweak n=68 dR +0.259
  [PASS] 6 >= 25 affected dates (priced set)      74 dates
  [PASS] 7 E3 <= 0 (does not re-wrap the sleeve)  corr -0.134 over 59 shared dates

  CANDIDATE is not a ship. Nothing ships from a research-tier study.
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 20:15:31 · git d47e227 (main, working tree dirty) · exit 0 · 110.2s
command     python -m scripts.backtest_study.f3_structure.financed_spread
excerpt     matched

```
  token; reports published before 2026-08-22 say POWER-STOPPED and mean the
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:21:37 · git c841a01 (main, working tree dirty) · exit 0 · 73.2s
command     python -m scripts.backtest_study.f3_structure.financed_spread
excerpt     matched

```
  token; reports published before 2026-08-22 say POWER-STOPPED and mean the
```

