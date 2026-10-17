## portfolio_delta — net-delta bands, ceilings and targets on the deployed book

<!-- brief:start -->
## In brief

> Plain-language brief for readers. The registration below is the binding text; where the two differ, the registration wins. `study_review` cuts this brief out before grading, so the blind graders never see it.
> Latest outcome: PRIMARY v3 `NOISE` (2026-08-19). SECONDARY v4, which carries nothing, `DELTA-DOSE-RESPONSE` (2026-09-28). No arm clears the whole bar in either · [record](../../study-results/f4_deployment/portfolio_delta.md).
> Nothing else in this brief is a result.

**The question**

Do positions opened in a session do worse when the book already carries high net delta? And can an operator steer that net-delta level at all? Both questions concern exposure, not selection. The study reuses `account_sim` machinery by import and keeps its own registration.

**What it compares**

Four arms, frozen at registration. No arm changes which signals are eligible, and none changes an exit. Every position replays under the shipped profiles. "Bear = hedge sleeve only" holds in every arm.

| Object | What it does | Kind |
|---|---|---|
| [portfolio_delta ARM D](../../arm-index.md#portfolio_delta) | Labels each session by open-book net delta-notional over equity at session open, before that day's picks. Bands: [0, 0.5), [0.5, 1), [1, 2), [2, ∞). Reports the outcome of positions opened in each band | descriptive, PRIMARY |
| portfolio_delta ARM B | Walks a net-delta ceiling of {1.0, 1.5, 2.0, 2.5, ∞} × equity through a local copy of `account_sim`'s admission | counterfactual arm |
| portfolio_delta ARM H\* | Resizes the shipped bear hedge sleeve to hold net delta at a target of {1.0, 1.5, 2.0} × equity. No pick is added or displaced | counterfactual arm |
| portfolio_delta ARM N | 200 seeded random admissions, matched on positions per date. Seed fixed and printed | null band |

The registration records one plan-time finding first. The deployed ladder is long-only: 219 of 220 picks have positive delta. Net delta can fall only by not trading or by resizing the sleeve.

**How it is judged**

**Population.** PRIMARY is `--era v3`, the proxy-calibrated book of 795 rows over 118 dates, with the shipped `top_k_per_day` walk. SECONDARY is `current` (v4). It is reported only and carries nothing. The two eras are never pooled. PRIMARY episodes are dense; the full sparse book carries nothing alone.

**Fixed settings.** Capital, risk %, caps, positions per day, `take_floor`, `downsize` and exits come from `config/account-sim.yml` as committed. None is swept. Compounding is off.

**Measure.** The unit is the session, and every interval is date-clustered. ARM D reports mean [R](../../glossary.md#r) per band. ARM B and ARM H\* are within-date paired differences against the shipped walk (`BOOT_N = 10000`, α = .05). R is quoted, not dollars.

**Gates.** Each gate exits non-zero on failure, in this order.

- `G-DELTA`: the row's stored signed net `delta` is checked against per-leg cache greeks. At least 90% of rows must agree within 0.05, and at least 95% per-leg availability. A missing greek is `None`, never `0.0`.
- `G-EQUIV`: at the committed `caps.net`, ARM B's banded walk reproduces `account_sim.simulate()` exactly under `book_signature()` equality.
- `G-INVENTORY`: counts how many deployed dates each arm moves into a different band. An arm that moves fewer than 25 dates is `POWER-STOPPED`. Its cells are not read.
- `G3` (imported): the ledger identity holds at every session.
- `G5` (imported): every arm passes the outcome-blindness probe, and the resulting book matches the sighted one.

ARM D bands under `MIN_CELL_N = 20` positions print their n and are not read. No annualised figure, Sharpe or time-to-recover appears anywhere.

**Bar.** An arm is a candidate only if it meets all seven clauses.

1. The date-clustered bootstrap CI excludes zero.
2. Every [leave-one-date-out](../../glossary.md#loo--leave-one-date-out) fold is positive.
3. The sign survives `protocol.window_cuts` and the ex-both-windows cut added by hand.
4. The arm is positive in every calendar year present.
5. The arm is right-signed on both pricing tiers.
6. The arm has at least 25 affected dates.
7. The arm is above ARM N's 95th percentile.

Worst-decile cells print their n and are marked NOT A CRITERION.

**Possible verdicts**

| Token | What it means |
|---|---|
| `LONG-ONLY-BY-CONSTRUCTION` | The ladder cannot reach a materially different net-delta level without not trading or resizing the sleeve. Registered as the likely verdict |
| `CANDIDATE-FOR-INDEPENDENT-WINDOW` | At least one arm clears the whole bar. It is queued for an independent window and nothing else |
| `DELTA-DOSE-RESPONSE` | ARM D shows a monotone, n-sufficient link between open-book delta at session open and the outcome of positions opened there |
| `NOISE` | No arm exceeds ARM N's 95th percentile and ARM D's bands are flat within their cells |
| `POWER-STOPPED` | `G-INVENTORY` fails for an arm. The census prints and nothing is read |

An arm that clears only clause 7 resolves to `NOISE` with a printed QUALIFICATION block naming the arms. `CANDIDATE-FOR-INDEPENDENT-WINDOW` sits below `LONG-ONLY-BY-CONSTRUCTION` and `UNDERPOWERED`. It sits above `DELTA-DOSE-RESPONSE` and `NOISE`.

**What could ship**

Nothing ships. `DELTA-DOSE-RESPONSE` queues an independent-window check. It may then become a context note, never an automatic cap. No band, ceiling or target value may be adopted on its P&L.

**What this study cannot tell you**

- Which delta level is better. The firewall bars reading a winner off the grid.
- Anything about selection or exits. Neither moves.
- Whether the exposure rule holds out of sample. The ladder is itself in-sample on this book, so any exposure rule is second-order in-sample.
- Anything from the worst-decile cells. They are descriptive only.
- Anything from SECONDARY v4 on its own.

---
<!-- brief:end -->

_Registered 2026-08-19._

The study reuses `account_sim`'s machinery **by import**, never by editing it,
and carries its own stem, its own registration and its own firewall.

## Question

Two questions, both about exposure rather than selection. Does the outcome of
the positions opened in a session depend on how much net delta the book already
carries at that session's open? And can that net-delta level be steered at all?

## What this is NOT

**Not an `account_sim` arm.** Three reasons, all structural:

1. `account_sim`'s registration contains an explicit firewall — *"no cap value
   may be adopted, recommended, or carried into a conclusion on the basis of its
   P&L in this grid"* — so a question whose whole content is "which delta level
   is better" cannot be answered inside it without violating the commitment that
   makes its own results readable.
2. A **signed net-delta band** is not the object `admission()` implements:
   `account_sim`'s `NET_CAP` is a MAGNITUDE cap on |Σ signed delta-notional|,
   and a band with a floor and a ceiling on a signed quantity is different
   machinery, not a different value of the same one.
3. `scripts/study_review/` keys on the bare study stem, so a question folded
   into `account_sim` as an arm would be graded against `account_sim`'s
   registration rather than against this one.

**Not a selection study.** No arm changes WHICH signals are eligible, and "bear
= hedge sleeve only" is respected by every arm including ARM H\*.

**Not an exit study.** Every position replays under the shipped profiles.

**Not a cap search.** Capital, risk %, per-position cap, net cap and
positions-per-day come from `config/account-sim.yml` **as committed** and are
NOT swept, and compounding is **OFF** (the frozen, path-independent book).

## Population and basis, fixed here

- **Era.** PRIMARY `--era v3` — `load_book(include_bs=False)`, proxy calibration
  gate ON, the 795-row / 118-date basis; deployed set = the shipped
  `top_k_per_day(ladder_rank, k=3, ladder_eligible)` walk. SECONDARY = `current`
  (v4), reported only, carries nothing. **Never pooled.**
- **Machinery.** Ledger, sizing, reserved-capital and exit machinery are
  `account_sim`'s, imported unchanged. This study adds no new ledger semantics.
- **Populations.** PRIMARY = the configured dense episodes; SECONDARY = the full
  sparse book, reported, carries nothing alone — the same convention
  `account_sim` and `selection_order` run under.

## Plan-time observations, disclosed

**The central measured constraint, stated FIRST (disclosed).** Measured on the
v3 book while designing this study, before any arm was written: **the deployed
ladder is structurally LONG-ONLY.** 220 picks over 90 dates — **179 `bull_call`
+ 41 `bull_put`** — and **219 of 220 have positive delta**. Per-date net
delta-notional / equity: **min 0.00, median 0.33, max 1.17, and never
negative.** There is no session in this book at which the deployed book is net
short.

The consequence is registered now, before any result: **net delta can only be
moved DOWN by not trading or by resizing the hedge sleeve.** A "delta band" with
a lower bound is unreachable from below and an upper bound can only ever
subtract positions. That is not a limitation discovered by the study — it is the
finding most likely to BE the study, and it is publishable as such
(**LONG-ONLY-BY-CONSTRUCTION**). Registering it up front is what stops it being
narrated later as a disappointing null.

## Arms

The arms are frozen at four; no additions after any result is seen.

### ARM D — dose-response (DESCRIPTIVE PRIMARY)

Label every session by the open-book net delta-notional / equity **at session
open, BEFORE that day's picks are admitted** (read off `session_series`), into
frozen bands **[0, 0.5) · [0.5, 1) · [1, 2) · [2, ∞)**. Then report the outcome
of the positions **OPENED in each band**.

Zero new ledger code and zero counterfactuals: this is a conditional read of the
shipped book, and it is the arm the study is really about — it asks whether
adding exposure onto an already long book pays worse, which is the actual
operator question. **MIN_CELL_N = 20 positions**; a band under it prints its n
and is not read.

### ARM B — ceiling band

Net-delta ceiling ∈ **{1.0, 1.5, 2.0, 2.5, ∞} × equity**, walked through a LOCAL
`admission_banded` copy of `account_sim`'s admission, kept in this module and
not promoted to `lib/`.

**G-EQUIV** gates it: at the COMMITTED `caps.net`, the banded walk must
reproduce `account_sim.simulate()`'s book **EXACTLY** under `book_signature()`
equality. A forked admission that has drifted is a finding about the fork.

### ARM H\* — delta-TARGETED hedge-sleeve resizing

The already-shipped bear hedge sleeve is re-sized to hold net delta at a TARGET
∈ **{1.0, 1.5, 2.0} × equity**, instead of the shipped fixed ½-risk size.
**Selection is untouched** — no new bear pick is admitted, no signal pick is
displaced; only the size of a sleeve position the shipped rule already opened
changes. This is the ONLY arm that can push net delta DOWN, which follows
directly from the long-only constraint above, and it respects "bear = hedge
sleeve only" by construction.

### ARM N — the random null band

200 seeded random admissions, matched on positions-per-date to the shipped walk.
The registered reading is explicit: **an arm must beat ARM N's 95th percentile,
not merely beat the shipped book.** An arm inside the band is noise, whatever
its point estimate. Seed fixed and printed.

## Unit and metric

The unit is the **session**, and everything is date-clustered.

- ARM D's metric is the mean R of positions opened per band, with
  `MIN_CELL_N = 20`.
- ARM B and ARM H\* are read as within-date paired differences vs the shipped
  walk (`boot_ci_paired_by_date`, `BOOT_N = 10000`, α = .05).
- Dollars print only inside the ledger census; **R is what is quoted**, because
  every arm that changes admission or sizing changes composition.

## Gates

Each gate exits non-zero on failure, and they run in the order below.

- **G-DELTA — source gate.** The row's stored signed net `delta` is PRIMARY, and
  is present **795/795** (disclosed plan-time measurement; the earlier
  "sparse delta" assumption was wrong and is corrected here). It is cross-checked
  against the per-leg `Delta` in the cached option-history CSVs via the new
  `scripts/backtest_study/lib/greeks.py`. Pre-declared thresholds:
  **≥ 90% of rows agree within 0.05** and **≥ 95% per-leg availability** at the
  entry day. A missing leg greek is **`None`, never `0.0`** (repo invariant) and
  its row is excluded from the cross-check and counted, never silently zeroed.
- **G-EQUIV** — ARM B's `admission_banded` reproduces `account_sim.simulate()`
  exactly under `book_signature()` at the committed `caps.net`, as above.
- **G-INVENTORY — census with a PRE-DECLARED power rule.** Print, per arm, how
  many deployed DATES the arm moves into a **DIFFERENT** band than the shipped
  walk puts them in. **An arm that cannot move ≥ 25 deployed dates into a
  different band is POWER-STOPPED**, its cells are not read, and no criterion is
  evaluated on it. Declared before the counts are known — this is the wall the
  entire hedge programme hit, and the long-only constraint makes it the likely
  outcome for ARM B.
- **Imported G3 — ledger identity** (`account_sim`'s): at every session
  `cash + Σreserved == starting capital + Σrealized-to-date`. A violation FAILS
  the run.
- **Imported G5 — outcome blindness**: every arm passes the
  `BlindRec` / `blind_records` probe — outcome keys raise,
  `LOOKAHEAD_ROW_COLUMNS` deleted from the row, resulting book identical to the
  sighted one. A band rule that peeks at the outcome is worthless; the whole
  point is a rule an operator could run live at session open.
- **No annualised figure, Sharpe, or time-to-recover anywhere** in the study or
  its write-up.

## Bar for a candidate

An arm's paired result may be described as a candidate ONLY under the full
conjunction below. Failing any one is failing.

- date-clustered bootstrap CI excluding zero (`BOOT_N = 10000`);
- **every** LOO fold positive (read `min_gain`);
- survives `protocol.window_cuts` AND the ex-BOTH-windows cut added by hand;
- positive in every calendar year present;
- right-signed on both pricing tiers;
- ≥ 25 affected dates;
- and, as criterion (7), **above ARM N's 95th percentile.**

Worst-decile cells print DESCRIPTIVELY with their n and are marked **NOT A
CRITERION** (the 2026-08-13 nine-date decile wall). Even a full pass is a
CANDIDATE queued for an independent window — **nothing ships from this study
under any outcome.**

## Verdicts, worded now

Four labels were registered at the outset; a fifth was added by the 2026-08-27
amendment below, which also states the precedence between them.

- **LONG-ONLY-BY-CONSTRUCTION** — the census and G-INVENTORY show the deployed
  ladder cannot be moved to a materially different net-delta level without
  either not trading or resizing the sleeve. This is the LIKELY verdict, it is
  **publishable**, and it is registered as a result rather than a null: it tells
  the operator that "target a portfolio delta" is not an available lever on this
  book, and that the sleeve is the only dial.
- **DELTA-DOSE-RESPONSE** — ARM D shows a monotone, n-sufficient relationship
  between open-book delta at session open and the outcome of positions opened
  there. Descriptive; queues an independent-window confirmation; may then be
  proposed as a context note, never as an automatic cap.
- **NOISE** — no arm exceeds ARM N's 95th percentile and ARM D's bands are flat
  within their cells. Recorded, thread closed for these dates.
- **POWER-STOPPED** — G-INVENTORY fails for an arm → census published for it,
  nothing read, no re-run on these dates.

**The combination the registered labels leave unnamed.** An arm that clears
criterion (7) (beats ARM N's 95th percentile) while failing the rest of the
conjunction matches none of the four labels above. Per the account_sim
2026-08-14 lesson (fix the grammar BEFORE a run, never after a number), that
case resolves to **NOISE with a printed QUALIFICATION block naming the arms**,
rather than a fifth label. No criterion or threshold moves as a result.

**Amendment 2026-08-27 (grammar completion — no criterion, threshold, or arm
definition moves).** The mapping above resolves an arm that clears the FULL
§Bar conjunction to the NOISE catch-all — printing a headline ("no arm exceeds
ARM N's 95th percentile") that the same report's checklist line contradicts.
That combination was already
worded in §Bar ("Even a full pass is a CANDIDATE queued for an independent
window — nothing ships from this study under any outcome"); this amendment only
wires that existing wording into the verdict grammar **as its own label**:

- **CANDIDATE-FOR-INDEPENDENT-WINDOW** — at least one arm clears the full
  adoption-eligibility conjunction of §Bar. The arm is queued for an
  independent window and NOTHING ELSE; nothing ships from this study under
  any outcome, and no ceiling or target value may be adopted on its P&L.

**Precedence.** CANDIDATE-FOR-INDEPENDENT-WINDOW fires only when a
full-conjunction pass exists. It sits below LONG-ONLY-BY-CONSTRUCTION and
UNDERPOWERED (unreachable there — a pass requires a powered arm) and above
DELTA-DOSE-RESPONSE and NOISE.
**The criterion-(7)-only case continues to resolve to NOISE + QUALIFICATION,
unchanged.**

**Also recorded:** the disclosed per-date net-delta figures (median 0.33, max
1.17) were measured on THAT DAY'S PICKS at 1 contract; the study's G-INVENTORY
census measures the OPEN BOOK at session open under production sizing.
Different quantities by definition, both printed with their definitions.

## Anti-tuning

Bands frozen at four, ceilings at five, targets at three, ARM N at 200 seeded
draws. Capital, risk %, per-position cap, net cap, positions-per-day,
`take_floor`, `downsize` and the exit profiles are NOT swept — they come from
`config/account-sim.yml` at their committed values for every arm. Compounding
OFF. No new selection column. **Every arm and every cell is reported regardless
of outcome**, including the ones that lose and the ones that power-stop, and no
threshold is moved after a number is seen.

## Ship criteria

Nothing ships.

### THE FIREWALL — verbatim discipline, imported from `account_sim`

**No band value, ceiling value or delta target may be adopted, recommended, or
carried into a conclusion on the basis of its P&L.** The grid is monotone by
construction in the same way `account_sim`'s cap grid is, and reading a winner
off it would be reading the construction.

The ONLY admissible readings from this study are:

1. **ARM D's dose-response SHAPE** — is the relationship between open-book delta
   and the outcome of positions opened at that level monotone, flat, or
   non-monotone;
2. **whether any arm exceeds ARM N's 95th percentile** — a binary, not a ranking;
3. **the inventory census** — what the book actually is, and what it can and
   cannot be moved to.

Anything else in the output is descriptive and is labelled NOT A CRITERION.

### Standing caveat that must appear in the report

The ladder is itself in-sample (fitted on this book), so any exposure rule
evaluated on the same book is second-order in-sample. The mitigations are that
these are mechanical, entry-side, session-open rules with no fitted threshold,
and that adoption requires out-of-fold survival. The caveat does not disappear
if the numbers look good.

## Build notes

_Not part of the registration._

- Module `scripts/backtest_study/f4_deployment/portfolio_delta.py`; run via
  `python -m scripts.backtest_study run portfolio_delta --era v3`; report to
  `backtests/study_output/portfolio_delta-latest.txt`.
- `account_sim` is imported, never refactored; `admission_banded` is a
  deliberate LOCAL copy behind G-EQUIV and is not promoted to `lib/`.
- `scripts/backtest_study/lib/greeks.py` (per-leg greeks from the cache; missing
  leg → `None`, never `0`) serves G-DELTA here and E1/E2 in `financed_spread`.
- `tests/test_portfolio_delta.py` must cover the degenerate-band equality and
  the `book_signature()` reproduction.
- `lib/harness.py` untouched. A `scripts/study_map/catalog.py` entry with a
  hand-written VERDICT is REQUIRED (a study with no entry fails the test suite),
  plus a `research/study-map.md` prose mention (test-enforced).
