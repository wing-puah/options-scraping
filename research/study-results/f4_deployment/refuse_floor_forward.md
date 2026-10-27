# refuse_floor_forward — per-era record

**Question.** On signal dates from 2026-10-08 onward only, do account_sim's F2 (refuse an unaffordable pick) and narrow_to_fit's (R, F3, $500) (narrow it to fit) keep a positive mean R and a survivable drawdown? A confidence sequence, valid under any number of looks, graded on every suite run.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha d81af9d — recorded 2026-10-10
<!-- key era=v4 sha=d81af9d inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-09 22:58:17 · git d81af9d (worktree-wf_c8ce3d2e-793-2, working tree dirty) · exit 4 (designed refusal) · 5.4s
command     python -m scripts.backtest_study.f4_deployment.refuse_floor_forward
excerpt     verdict

```
VERDICTS
  No forward signal date has a loaded row. Every sequence holds t=0.
  >>> (R, F2, $500): STILL-OPEN <<<  (both cap cells)
  >>> (R, F3, $500): STILL-OPEN <<<  (both cap cells)
  >>> (R, F3, $500) + 20% net floor: STILL-OPEN <<<  (both cap cells)  DECLARED SECONDARY
  Look logged to research/study-results/f4_deployment/refuse_floor_forward-looks.jsonl.
  REFUSED (designed, exit 4): nothing to grade until the exports hold a signal date on or after 2026-10-08.
```


## era v4 · inputs 61bda3a · sha 2664ebd — recorded 2026-10-26
<!-- key era=v4 sha=2664ebd inputs=61bda3a -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-26 01:06)
run         2026-10-26 19:46:57 · git 2664ebd (main, working tree clean) · exit 0 · 72.5s
command     python -m scripts.backtest_study.f4_deployment.refuse_floor_forward
excerpt     tail

```
  b264cfd holdout_seal: accept by default, seal from 2026-09-23, build the guard
CLOSE
  (R, F2, $500): STILL-OPEN
  (R, F3, $500): STILL-OPEN
  declared secondary (R, F3, $500) + 20% net floor: STILL-OPEN
  gates: G2-G5 PASS  FW2 PASS  FW4 PASS  GN5 clear
  look logged to research/study-results/f4_deployment/refuse_floor_forward-looks.jsonl
  Nothing in this report is a shippable rule.
```

