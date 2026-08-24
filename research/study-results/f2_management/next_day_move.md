# next_day_move — per-era record

**Question.** Move the give-back question to day 0, where it is knowable at the close: cut positions the stock did not confirm?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:46:01 · git 53b7167 (main, working tree dirty) · exit 0 · 8.6s
command     python -m scripts.backtest_study.f2_management.next_day_move
excerpt     tail

```
  inside apply_day0_cut, not by pre-filtering the row list. Pre-filtering would
  make this vacuous — the rule could not touch a row it was never handed. Here
  it could, and must not.
  cut when wrong sign                         bear rows changed  170   non-bear changed    0   OK
  cut when worse than -0.5 sigma              bear rows changed   90   non-bear changed    0   OK
  cut when inside the flat band (+0.5 sigma)  bear rows changed  234   non-bear changed    0   OK
  0 in the non-bear column is the only acceptable number.
  ARM R population note: 787 of 795 book rows carry a day-0 move; the rest are counted in the coverage table above.
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:10:45 · git d47e227 (main, working tree dirty) · exit 0 · 7.0s
command     python -m scripts.backtest_study.f2_management.next_day_move
excerpt     tail

```
  inside apply_day0_cut, not by pre-filtering the row list. Pre-filtering would
  make this vacuous — the rule could not touch a row it was never handed. Here
  it could, and must not.
  cut when wrong sign                         bear rows changed   89   non-bear changed    0   OK
  cut when worse than -0.5 sigma              bear rows changed   39   non-bear changed    0   OK
  cut when inside the flat band (+0.5 sigma)  bear rows changed  126   non-bear changed    0   OK
  0 in the non-bear column is the only acceptable number.
  ARM R population note: 479 of 517 book rows carry a day-0 move; the rest are counted in the coverage table above.
```

