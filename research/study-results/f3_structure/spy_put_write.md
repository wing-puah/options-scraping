# spy_put_write — per-era record

**Question.** Does a mechanical SPY put credit spread, sold every week (short at spot, width 10% of spot, monthly nearest 37 DTE, held to expiry), earn a net return per expiry cycle above zero, and a monthly return that SPY's own beta does not explain?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs e7318a6 · sha ab21a3a — recorded 2026-11-27
<!-- key era=v4 sha=ab21a3a inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-27 19:58:32 · git ab21a3a (main, working tree dirty) · exit 0 · 129.4s
command     python -m scripts.backtest_study.f3_structure.spy_put_write
excerpt     verdict

```
VERDICT: NULL
  window   signal weeks 2022-01-31 -> 2026-10-26; era none (option cache only)
  >>> spy_put_write PRIMARY (at spot   w10% hold): NULL <<<  (first failed criterion C1 (ARM Z); ARM H NO-ALPHA)
  ARM Z NULL: cycle-mean R +0.019 CI95 [-0.072, +0.095] on 232 trades, 55 cycles
  ARM H NO-ALPHA: alpha/month -0.03410 CI95 [-0.06864, +0.00043], beta +4.4910 CI95 [+3.7564, +5.4183], 54 months
  C4 PBO 0.829  ·  C0a PASS  ·  FORWARD STILL-OPEN
  Descriptive cells (no verdict): [at spot   w 5% hold: Z NULL H NEGATIVE-ALPHA]  [at spot   w 5% target: Z NULL H NO-ALPHA]  [at spot   w10% target:…
  Nothing ships from the retrospective.
```


## Note 2026-11-27 · first run, in plain words

**`NULL`: the weekly SPY put credit spread earns a small positive mean that cannot be told from zero, and it earns no return beyond its SPY beta.** Nothing ships.

The machine header says era v4 because the runner names the book's era. This study reads no book. Its era is "none (option cache only)". The window is the signal weeks from 2022-01-31 to 2026-10-26, 248 weeks on 57 monthly expiry cycles. The SPY closes come from `backtests/mech_regime/spy_base_rate_daily.csv`, extended by `spy_vix_daily_full.csv`. They are unadjusted: on the 247 weeks with an option spot, the close sits within 0.08% of the options' own `Price~`.

The verdict lines in full, verbatim from `backtests/study_output/spy_put_write-latest.txt`:

```
>>> spy_put_write PRIMARY (at spot   w10% hold): NULL <<<  (first failed criterion C1 (ARM Z); ARM H NO-ALPHA)
ARM Z NULL: cycle-mean R +0.019 CI95 [-0.072, +0.095] on 232 trades, 55 cycles
ARM H NO-ALPHA: alpha/month -0.03410 CI95 [-0.06864, +0.00043], beta +4.4910 CI95 [+3.7564, +5.4183], 54 months
C4 PBO 0.829  ·  C0a PASS  ·  FORWARD STILL-OPEN
```

- **Coverage passed.** The primary cell is built on 93.5% of weeks, and on 70% in 2026, the thinnest year.
- **The mean is not shown.** The cycle-mean interval spans zero. Dropping 2024 flips the sign.
- **The beta does the work.** One lot per week holds about five spreads at once, so the account carries about 4.5 times SPY's monthly move on $25,000.
- **The alpha point estimate is negative.** The interval's top is +0.0004 a month, so `NEGATIVE-ALPHA` misses by a hair and the token is `NO-ALPHA`.
- **No other cell does better on the grid.** All eleven print `NULL` or `UNDERPOWERED` on `ARM Z`. PBO is 0.829, so the best in-sample cell would mostly rank below the median out of sample.
- **Exits give back most of the move.** The primary's MFE averages +0.163 R and its MAE −0.215 R. Capture is 0.263.
- **One lot never fits the $1,000 stop.** The primary's median max loss is $4,398 a lot. Its worst close breached −$1,000 on 34% of trades.

**The sample misses a sell-off.** The October and November 2026 expiries hold too few cached strikes, so their nine signal weeks are `UNCACHED`. The selection print shows the unbuilt 2026 weeks lost. On them SPY fell 2.4% on average from fill to expiry. On the built 2026 weeks it rose 1.1%. The holes sit on losing weeks, so the graded mean leans favourable.

Six build rulings, each made before any number was priced, sit beside their rules in the [registration](../../pre-registrations/f3_structure/spy_put_write.md) as `Resolved at build (2026-11-27)`.
