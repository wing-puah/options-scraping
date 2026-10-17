## portfolio_delta — net-delta bands, ceilings and targets on the deployed book

<!-- outcome:start -->
> Latest outcome: PRIMARY v3 `NOISE` (2026-08-19). SECONDARY v4, which carries nothing, `DELTA-DOSE-RESPONSE` (2026-09-28). No arm clears the whole bar in either · [record](../../study-results/f4_deployment/portfolio_delta.md).
<!-- outcome:end -->

_Registered 2026-08-19._

## The question

Two questions, both about exposure rather than selection.

1. Does the outcome of the positions opened in a session depend on how much net delta the book already carries at that session's open?
2. Can that net-delta level be steered at all?

The study reuses `account_sim`'s machinery **by import**, never by editing it. It has its own stem, registration and firewall.

## What this study is not

**It is not an `account_sim` arm.** Three reasons, all structural:

1. `account_sim`'s firewall says *"no cap value may be adopted, recommended, or carried into a conclusion on the basis of its P&L in this grid"*. A question about "which delta level is better" cannot be answered inside it.
2. A **signed net-delta band** is not what `admission()` implements. `NET_CAP` is a MAGNITUDE cap on |Σ signed delta-notional|.
3. `scripts/study_review/` keys on the bare study stem, so an `account_sim` arm would be graded against `account_sim`'s registration.

**It is not a selection study.** No arm changes WHICH signals are eligible. "Bear = hedge sleeve only" holds in every arm, including ARM H\*.

**It is not an exit study.** Every position replays under the shipped profiles.

**It is not a cap search.** Capital, risk %, per-position cap, net cap and positions-per-day come from `config/account-sim.yml` **as committed**. None is swept. Compounding is **OFF** (the frozen, path-independent book).

**It cannot say** which delta level is better, anything about selection or exits, whether an exposure rule holds out of sample, anything from the worst-decile cells, or anything from SECONDARY v4 on its own.

## Population and basis, fixed here

- **Era.** PRIMARY is `--era v3`: `load_book(include_bs=False)`, proxy calibration gate ON, the 795-row / 118-date basis. The deployed set is the shipped `top_k_per_day(ladder_rank, k=3, ladder_eligible)` walk. SECONDARY is `current` (v4); it is reported only and carries nothing. The two eras are **never pooled**.
- **Machinery.** Ledger, sizing, reserved-capital and exit machinery are `account_sim`'s, imported unchanged. This study adds no new ledger semantics.
- **Populations.** PRIMARY is the configured dense episodes. SECONDARY is the full sparse book; it is reported and carries nothing alone. `account_sim` and `selection_order` run under the same convention.

## Plan-time observations, disclosed

Measured on the v3 book while the study was designed, before any arm was written.

**The central constraint, stated FIRST: the deployed ladder is structurally LONG-ONLY.**

- 220 picks over 90 dates: **179 `bull_call` + 41 `bull_put`**.
- **219 of 220 have positive delta.**
- Per-date net delta-notional / equity: **min 0.00, median 0.33, max 1.17, never negative.**
- No session in this book has the deployed book net short.

The consequence is registered now, before any result. **Net delta can only be moved DOWN by not trading or by resizing the hedge sleeve.** A "delta band" with a lower bound is unreachable from below. An upper bound can only subtract positions. This is the finding most likely to BE the study, and it is publishable as such (**LONG-ONLY-BY-CONSTRUCTION**).

(Amendment 2026-08-27.) These per-date figures were measured on THAT DAY'S PICKS at 1 contract. The `G-INVENTORY` census measures the OPEN BOOK at session open under production sizing. The two are different quantities by definition. Both print with their definitions.

## What it compares

Four arms, frozen. No arm is added after any result is seen.

| Arm | What it does | Kind |
|---|---|---|
| [portfolio_delta ARM D](../../arm-index.md#portfolio_delta) | Labels each session by open-book net delta-notional / equity at session open, before that day's picks. Bands **[0, 0.5) · [0.5, 1) · [1, 2) · [2, ∞)**. Reports the outcome of positions opened in each band | descriptive, PRIMARY |
| portfolio_delta ARM B | Walks a net-delta ceiling of **{1.0, 1.5, 2.0, 2.5, ∞} × equity** through a local copy of `account_sim`'s admission | counterfactual |
| portfolio_delta ARM H\* | Resizes the shipped bear hedge sleeve to hold net delta at a target of **{1.0, 1.5, 2.0} × equity** | counterfactual |
| portfolio_delta ARM N | 200 seeded random admissions, matched on positions per date. Seed fixed and printed | null band |

### ARM D — dose-response (DESCRIPTIVE PRIMARY)

Label every session by the open-book net delta-notional / equity **at session open, BEFORE that day's picks are admitted** (read off `session_series`). Use the frozen bands above. Report the outcome of the positions **OPENED in each band**.

ARM D needs zero new ledger code and zero counterfactuals. It is a conditional read of the shipped book.

**`MIN_CELL_N = 20` positions.** A band under it prints its n and is not read.

### ARM B — ceiling band

Net-delta ceiling ∈ **{1.0, 1.5, 2.0, 2.5, ∞} × equity**, walked through a LOCAL `admission_banded` copy of `account_sim`'s admission. The copy stays in this module and is not promoted to `lib/`. `G-EQUIV` gates it.

### ARM H\* — delta-TARGETED hedge-sleeve resizing

The already-shipped bear hedge sleeve is re-sized to hold net delta at a TARGET ∈ **{1.0, 1.5, 2.0} × equity**, instead of the shipped fixed ½-risk size.

**Selection is untouched.** No new bear pick is admitted and no signal pick is displaced. Only the size of a sleeve position that the shipped rule already opened changes. ARM H\* is the ONLY arm that can push net delta DOWN.

### ARM N — the random null band

200 seeded random admissions, matched on positions-per-date to the shipped walk. Seed fixed and printed.

**An arm must beat ARM N's 95th percentile, not merely beat the shipped book.** An arm inside the band is noise, whatever its point estimate.

## How it is judged

The unit is the **session**, and everything is date-clustered.

- ARM D's metric is the mean [R](../../glossary.md#r) of positions opened per band, with `MIN_CELL_N = 20`.
- ARM B and ARM H\* are read as within-date paired differences versus the shipped walk (`boot_ci_paired_by_date`, `BOOT_N = 10000`, α = .05).
- Dollars print only inside the ledger census. **R is what is quoted**, because every arm that changes admission or sizing changes composition.

## Gates

Each gate exits non-zero on failure. They run in this order.

- **G-DELTA — source gate.** The row's stored signed net `delta` is PRIMARY. It is present **795/795** (disclosed plan-time measurement; the earlier "sparse delta" assumption was wrong and is corrected here). It is cross-checked against the per-leg `Delta` in the cached option-history CSVs via `scripts/backtest_study/lib/greeks.py`. Pre-declared thresholds: **≥ 90% of rows agree within 0.05**, and **≥ 95% per-leg availability** at the entry day. A missing leg greek is **`None`, never `0.0`** (repo invariant). Its row is excluded from the cross-check and counted, never silently zeroed.
- **G-EQUIV.** At the COMMITTED `caps.net`, ARM B's `admission_banded` must reproduce `account_sim.simulate()`'s book **EXACTLY** under `book_signature()` equality. A forked admission that has drifted is a finding about the fork.
- **G-INVENTORY — census with a PRE-DECLARED power rule.** Print, per arm, how many deployed DATES the arm moves into a **DIFFERENT** band than the shipped walk puts them in. **An arm that cannot move ≥ 25 deployed dates into a different band is POWER-STOPPED.** Its cells are not read and no criterion is evaluated on it. The rule was declared before the counts were known. Pre-run expectation: the long-only constraint makes this the likely outcome for ARM B.
- **Imported G3 — ledger identity** (`account_sim`'s). At every session, `cash + Σreserved == starting capital + Σrealized-to-date`. A violation FAILS the run.
- **Imported G5 — outcome blindness.** Every arm passes the `BlindRec` / `blind_records` probe: outcome keys raise, `LOOKAHEAD_ROW_COLUMNS` are deleted from the row, and the resulting book is identical to the sighted one.
- **No annualised figure, Sharpe, or time-to-recover anywhere** in the study or its write-up.

## Bar for a candidate

An arm's paired result may be described as a candidate ONLY under the full conjunction below. Failing any one clause is failing.

1. The date-clustered bootstrap CI excludes zero (`BOOT_N = 10000`).
2. **Every** leave-one-date-out ([LOO](../../glossary.md#loo--leave-one-date-out)) fold is positive (read `min_gain`).
3. The result survives `protocol.window_cuts` AND the ex-BOTH-windows cut added by hand.
4. The arm is positive in every calendar year present.
5. The arm is right-signed on both pricing tiers.
6. The arm has ≥ 25 affected dates.
7. The arm is **above ARM N's 95th percentile**.

Worst-decile cells print DESCRIPTIVELY with their n and are marked **NOT A CRITERION** (the 2026-08-13 nine-date decile wall).

Even a full pass is a CANDIDATE queued for an independent window. **Nothing ships from this study under any outcome.**

## Verdicts, worded now

| Token | When |
|---|---|
| `LONG-ONLY-BY-CONSTRUCTION` | The census and `G-INVENTORY` show the deployed ladder cannot be moved to a materially different net-delta level without not trading or resizing the sleeve. This is the LIKELY verdict. It is **publishable**, a result and not a null: "target a portfolio delta" is not an available lever on this book, and the sleeve is the only dial |
| `CANDIDATE-FOR-INDEPENDENT-WINDOW` | At least one arm clears the FULL conjunction of the Bar. The arm is queued for an independent window and NOTHING ELSE. No ceiling or target value may be adopted on its P&L |
| `DELTA-DOSE-RESPONSE` | ARM D shows a monotone, n-sufficient relationship between open-book delta at session open and the outcome of positions opened there. It is descriptive. It queues an independent-window confirmation, and may then be proposed as a context note, never as an automatic cap |
| `NOISE` | No arm exceeds ARM N's 95th percentile and ARM D's bands are flat within their cells. Recorded; thread closed for these dates |
| `POWER-STOPPED` | `G-INVENTORY` fails for an arm. The census is published for it, nothing is read, and there is no re-run on these dates |

**Grammar completion (amendment 2026-08-27; no criterion, threshold or arm definition moves).** `CANDIDATE-FOR-INDEPENDENT-WINDOW` is its own label, so a full-conjunction pass does not resolve to the `NOISE` catch-all.

**Precedence (amendment 2026-08-27).** `CANDIDATE-FOR-INDEPENDENT-WINDOW` fires only when a full-conjunction pass exists. It sits below `LONG-ONLY-BY-CONSTRUCTION` and `UNDERPOWERED` (unreachable there, because a pass requires a powered arm). It sits above `DELTA-DOSE-RESPONSE` and `NOISE`.

**The combination the labels leave unnamed.** An arm that clears clause 7 (beats ARM N's 95th percentile) but fails the rest of the conjunction resolves to **`NOISE` with a printed QUALIFICATION block naming the arms**, not to a further label. No criterion or threshold moves as a result. The grammar is fixed BEFORE a run, never after a number (the `account_sim` 2026-08-14 lesson).

## Anti-tuning

- Bands are frozen at four, ceilings at five, targets at three, and ARM N at 200 seeded draws.
- Capital, risk %, per-position cap, net cap, positions-per-day, `take_floor`, `downsize` and the exit profiles are NOT swept. They come from `config/account-sim.yml` at their committed values for every arm.
- Compounding is OFF. No new selection column is added.
- **Every arm and every cell is reported regardless of outcome**, including those that lose and those that power-stop.
- No threshold is moved after a number is seen.

## What could ship

**Nothing ships.**

### THE FIREWALL (imported from `account_sim`)

**No band value, ceiling value or delta target may be adopted, recommended, or carried into a conclusion on the basis of its P&L.** The grid is monotone by construction, as `account_sim`'s cap grid is.

The ONLY admissible readings from this study are:

1. **ARM D's dose-response SHAPE**: whether the relationship between open-book delta and the outcome of positions opened at that level is monotone, flat, or non-monotone.
2. **Whether any arm exceeds ARM N's 95th percentile**: a binary, not a ranking.
3. **The inventory census**: what the book actually is, and what it can and cannot be moved to.

Anything else in the output is descriptive and is labelled NOT A CRITERION.

### Standing caveat that must appear in the report

The ladder is itself in-sample (fitted on this book). Any exposure rule evaluated on the same book is second-order in-sample. The mitigations are that these rules are mechanical, entry-side, session-open rules with no fitted threshold, and that adoption requires out-of-fold survival. The caveat does not disappear if the numbers look good.
