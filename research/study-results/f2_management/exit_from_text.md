# exit_from_text — per-era record

**Question.** Do the model's OWN stated invalidation level, trigger condition and horizon make better exits than the shipped mechanical profile — an underlying-close stop at the invalidation level (E1), entering only when the trigger was met (E2, a selection effect), and the emitted horizon as the time exit (E3)?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs b995259 · sha 01dcb97 — recorded 2026-09-03
<!-- key era=v4 sha=01dcb97 inputs=b995259 -->

population  494 results · 1,144 proxy · 1,975 analysis · 817 spy_vix_daily_full  (inputs dated 2026-09-02 12:00 … 2026-09-02 14:53)
run         2026-09-03 11:41:32 · git 01dcb97 (main, working tree dirty) · exit 0 · 81.8s
command     python -m scripts.backtest_study.f2_management.exit_from_text
excerpt     verdict

```
VERDICT SUMMARY — every cell, every arm, regardless of outcome
  arm family cell                                  grid              verdict
  E1  ALL    ALL                                   buf0%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf0%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf0%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf1%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf1%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf1%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf2%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf2%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf2%/ne_strike   NOT A CRITERION (pooled): NULL
  E1  CROSS  bear_put_spread|BEAR_HE               buf0%/ne_strike   UNDERPOWERED
```


## era v4 · inputs 1b1ba3c · sha e59356f — recorded 2026-09-04
<!-- key era=v4 sha=e59356f inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 20:37:57 · git e59356f (main, working tree dirty) · exit 0 · 50.8s
command     python -m scripts.backtest_study.f2_management.exit_from_text
excerpt     verdict

```
VERDICT SUMMARY — every cell, every arm, regardless of outcome
  arm family cell                                  grid              verdict
  E1  ALL    ALL                                   buf0%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf0%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf0%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf1%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf1%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf1%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf2%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf2%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf2%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  CROSS  bear_put_spread|BEAR_HE               buf0%/ne_strike   UNDERPOWERED
```


## era v4 · inputs 1b1ba3c · sha b007f95 — recorded 2026-09-04
<!-- key era=v4 sha=b007f95 inputs=1b1ba3c -->

population  535 results · 1,303 proxy · 2,212 analysis · 819 spy_vix_daily_full  (inputs dated 2026-09-04 11:10 … 2026-09-04 20:31)
run         2026-09-04 22:27:02 · git b007f95 (main, working tree clean) · exit 0 · 86.7s
command     python -m scripts.backtest_study.f2_management.exit_from_text
excerpt     verdict

```
VERDICT SUMMARY — every cell, every arm, regardless of outcome
  arm family cell                                  grid              verdict
  E1  ALL    ALL                                   buf0%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf0%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf0%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf1%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf1%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf1%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf2%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf2%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf2%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  CROSS  bear_put_spread|BEAR_HE               buf0%/ne_strike   UNDERPOWERED
```


## era v4 · inputs 271c4b5 · sha 8e9b6a7 — recorded 2026-09-20
<!-- key era=v4 sha=8e9b6a7 inputs=271c4b5 -->

population  598 results · 1,665 proxy · 2,781 analysis · 827 spy_vix_daily_full  (inputs dated 2026-09-16 11:32 … 2026-09-19 16:45)
run         2026-09-19 23:31:08 · git 8e9b6a7 (main, working tree clean) · exit 0 · 98.4s
command     python -m scripts.backtest_study.f2_management.exit_from_text
excerpt     verdict

```
VERDICT SUMMARY — every cell, every arm, regardless of outcome
  arm family cell                                  grid              verdict
  E1  ALL    ALL                                   buf0%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf0%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf0%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf1%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf1%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf1%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf2%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf2%/eq_strike   NOT A CRITERION (pooled): NULL
  E1  ALL    ALL                                   buf2%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  CROSS  bear_put_spread|BEAR_HE               buf0%/eq_strike   UNDERPOWERED
```


## era v4 · inputs 7373cdb · sha de5a6f3 — recorded 2026-09-28
<!-- key era=v4 sha=de5a6f3 inputs=7373cdb -->

population  1,012 results · 2,029 proxy · 3,346 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-27 15:57 … 2026-09-28 12:45)
run         2026-09-28 12:56:10 · git de5a6f3 (main, working tree dirty) · exit 0 · 148.8s
command     python -m scripts.backtest_study.f2_management.exit_from_text
excerpt     verdict  (40 of 367 block lines; 327 not quoted)
tally       UNDERPOWERED 302, CONTRARY 26, NULL 21, CANDIDATE 1  (350 of 367 lines carried a token)

```
VERDICT SUMMARY — every cell, every arm, regardless of outcome
  arm family cell                                  grid              verdict
  E1  ALL    ALL                                   buf0%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf0%/eq_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf0%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf1%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf1%/eq_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf1%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf2%/breakeven   UNDERPOWERED
  E1  ALL    ALL                                   buf2%/eq_strike   NOT A CRITERION (pooled): CONTRARY
  E1  ALL    ALL                                   buf2%/ne_strike   NOT A CRITERION (pooled): CONTRARY
  E1  CROSS  bear_put_spread|BEAR_HE               buf0%/ne_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|BEAR_HE               buf1%/ne_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|BEAR_HE               buf2%/ne_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|LVOL                  buf0%/eq_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|LVOL                  buf0%/ne_strike   NULL
  E1  CROSS  bear_put_spread|LVOL                  buf1%/eq_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|LVOL                  buf1%/ne_strike   NULL
  E1  CROSS  bear_put_spread|LVOL                  buf2%/eq_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|LVOL                  buf2%/ne_strike   NULL
  E1  CROSS  bear_put_spread|PROD                  buf0%/ne_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|PROD                  buf1%/ne_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|PROD                  buf2%/ne_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|RB_EVOL               buf0%/ne_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|RB_EVOL               buf1%/ne_strike   UNDERPOWERED
  E1  CROSS  bear_put_spread|RB_EVOL               buf2%/ne_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|BEAR_HE              buf0%/ne_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|BEAR_HE              buf1%/ne_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|BEAR_HE              buf2%/ne_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|LVOL                 buf0%/eq_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|LVOL                 buf0%/ne_strike   CONTRARY
  E1  CROSS  bull_call_spread|LVOL                 buf1%/eq_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|LVOL                 buf1%/ne_strike   CONTRARY
  E1  CROSS  bull_call_spread|LVOL                 buf2%/eq_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|LVOL                 buf2%/ne_strike   CONTRARY
  E1  CROSS  bull_call_spread|PROD                 buf0%/ne_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|PROD                 buf1%/ne_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|PROD                 buf2%/ne_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|RB_EVOL              buf0%/ne_strike   UNDERPOWERED
  E1  CROSS  bull_call_spread|RB_EVOL              buf1%/ne_strike   UNDERPOWERED
```

