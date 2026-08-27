# portfolio_delta — per-era record

**Question.** Is there an optimal PORTFOLIO net delta to keep? account_sim showed delta-notional binds before cash; this asks whether the level itself is a lever — dose-response, a ceiling band, and a delta-TARGETED hedge sleeve, against a seeded random-admission null band.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 · inputs cd647ce · sha bfcd512 — recorded 2026-08-19
<!-- key era=v3 sha=bfcd512 inputs=cd647ce -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 807 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-08-19 11:10)
run         2026-08-19 17:13:34 · git bfcd512 (main, working tree dirty) · exit 0 · 15.5s
command     python -m scripts.backtest_study.f4_deployment.portfolio_delta
excerpt     verdict

```
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
  arms powered (G-INVENTORY): B ceiling 1.00
  arms clearing the whole bar:  none
  ARM D readable bands: [1.0,2.0)   shape: not monotone / not readable
  census: long-only book: True   negative-delta picks 1 of 220   per-date net/equity range [+0.00, +2.49]
  >>> NOISE — no arm exceeds ARM N's 95th percentile and ARM D's bands do not separate within their cells. Recorded; thread closed for these dates. <…
  QUALIFICATION on the label above (printed because the catch-all fired, not
  because the wording matched): B ceiling 1.00 DID clear criterion (7)
  — it sits above ARM N's 95th percentile — and then failed the rest of the
  conjunction. NOISE is carrying it as the catch-all rather than a fifth label
  being invented after the number was seen. Read the per-arm checklist above:
  it is the whole result, and nothing on it is adoption-eligible.
```


## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 20:17:52 · git d47e227 (main, working tree dirty) · exit 0 · 10.8s
command     python -m scripts.backtest_study.f4_deployment.portfolio_delta
excerpt     verdict

```
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
  arms powered (G-INVENTORY): B ceiling 1.00
  arms clearing the whole bar:  none
  ARM D readable bands: [1.0,2.0)   shape: not monotone / not readable
  census: long-only book: True   negative-delta picks 0 of 168   per-date net/equity range [+0.00, +2.43]
  >>> NOISE — no arm exceeds ARM N's 95th percentile and ARM D's bands do not separate within their cells. Recorded; thread closed for these dates. <…
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:23:13 · git c841a01 (main, working tree dirty) · exit 0 · 6.9s
command     python -m scripts.backtest_study.f4_deployment.portfolio_delta
excerpt     verdict

```
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
  arms powered (G-INVENTORY): B ceiling 1.00
  arms clearing the whole bar:  none
  ARM D readable bands: [1.0,2.0), [2.0,inf)   shape: not monotone / not readable
  census: long-only book: True   negative-delta picks 0 of 181   per-date net/equity range [+0.00, +2.50]
  >>> NOISE — no arm exceeds ARM N's 95th percentile and ARM D's bands do not separate within their cells. Recorded; thread closed for these dates. <…
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 21:13:17 · git 25f3e27 (main, working tree dirty) · exit 0 · 22.8s
command     python -m scripts.backtest_study.f4_deployment.portfolio_delta
excerpt     verdict

```
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
  arms powered (G-INVENTORY): B ceiling 1.00, B ceiling 1.50, B ceiling 2.00, H* target 2.00
  arms clearing the whole bar:  B ceiling 1.00, B ceiling 1.50
  ARM D readable bands: [0.0,0.5), [1.0,2.0), [2.0,inf)   shape: not monotone / not readable
  census: long-only book: True   negative-delta picks 0 of 317   per-date net/equity range [+0.00, +2.49]
  >>> CANDIDATE-FOR-INDEPENDENT-WINDOW — B ceiling 1.00, B ceiling 1.50 clear the full adoption-eligibility conjunction. Queued for an independent wi…
```

