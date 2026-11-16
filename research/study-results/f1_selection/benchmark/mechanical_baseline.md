# mechanical_baseline — per-era record

**Question.** Does a fixed rule with no model and no flow data make money on its own: one SPY ATM/+5% call vertical bought on the first session of each week, at the monthly expiry nearest 65 DTE, under the shipped debit exits? Graded against zero, against SPY's own drift (ARM H), a random flow ticker (ARM RND) and the v4 book (ARM BK).

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 61bda3a · sha 5ac1a8e — recorded 2026-11-11
<!-- key era=v4 sha=5ac1a8e inputs=61bda3a -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-26 01:06)
run         2026-11-11 14:36:38 · git 5ac1a8e (main, working tree clean) · exit 0 · 563.1s
command     python -m scripts.backtest_study.f1_selection.benchmark.mechanical_baseline
excerpt     verdict

```
VERDICT: NO-REPLACEMENT
  ARM X NULL  ·  ARM H NEGATIVE-ALPHA  ·  ARM RND NOT BUILT — AWAITING SCRAPE (not in the study token)  ·  ARM BK NULL
  BOOK-BETTER takes precedence. Nothing ships from the retrospective.
```


## Graded by `study_review` — 2026-11-16

Two analysts and a validator graded the 2026-11-11 report (v4, sha 5ac1a8e) against the registration. They agree on every row, and the validator found no transcription errors.

- **Verdict:** `NO-REPLACEMENT` stands. `ARM X` fails C1 only. `ARM H` and `ARM BK` v3 meet their criteria. `ARM BK` v4 fails C1.
- **Not graded:** `ARM RND`, the C5 overfitting check and the forward read. Each prints no figure to grade.
- **Fault in the report:** the study token reads `NO-REPLACEMENT` while a line says `BOOK-BETTER takes precedence`. The registration ties `BOOK-BETTER` to `ARM BK` printing `TRAILS-BOOK`, and v4 prints `NULL`. Both analysts declined to grade the token. The wording needs a ruling.
- **Count mismatch:** the v3 census drops 1 date and the graded block drops 2, and the v4 graded block prints `no_spot=1` where the census does not.
