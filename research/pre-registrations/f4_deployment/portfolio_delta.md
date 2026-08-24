## 2026-08-19 — `portfolio_delta`: PRE-REGISTRATION (written BEFORE the study was built or run)

**Why this is a NEW study and not an `account_sim` arm.** Three reasons, all
structural. (1) `account_sim`'s registration contains an explicit firewall —
*"no cap value may be adopted, recommended, or carried into a conclusion on the
basis of its P&L in this grid"* — so a question whose whole content is "which
delta level is better" cannot be answered inside it without violating the
commitment that makes its own results readable. (2) A **signed net-delta band**
is not the object `admission()` implements: `account_sim`'s `NET_CAP` is a
MAGNITUDE cap on |Σ signed delta-notional|, and a band with a floor and a
ceiling on a signed quantity is different machinery, not a different value of
the same one. (3) `scripts/study_review/` keys on the bare study stem, so a
question folded into `account_sim` as an arm would be graded against
`account_sim`'s registration rather than against this one. This study therefore
gets its own stem, its own registration, and its own firewall — and it reuses
`account_sim`'s machinery **by import**, never by editing it.

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

**What this is NOT.** It is not a selection study — no arm changes WHICH signals
are eligible, and "bear = hedge sleeve only" is respected by every arm
including ARM H\*. It is not an exit study — every position replays under the
shipped profiles. It is not a cap search: capital, risk %, per-position cap,
net cap and positions-per-day come from `config/account-sim.yml` **as
committed** and are NOT swept, and compounding is **OFF** (the frozen,
path-independent book).

---

### Population and basis, fixed here

- Era: PRIMARY `--era v3` — `load_book(include_bs=False)`, proxy calibration
  gate ON, the 795-row / 118-date basis; deployed set = the shipped
  `top_k_per_day(ladder_rank, k=3, ladder_eligible)` walk. SECONDARY = `current`
  (v4), reported only, carries nothing. **Never pooled.**
- Ledger, sizing, reserved-capital and exit machinery: `account_sim`'s, imported
  unchanged. This study adds no new ledger semantics.
- PRIMARY = the configured dense episodes; SECONDARY = the full sparse book,
  reported, carries nothing alone — the same convention `account_sim` and
  `selection_order` run under.

### Arms — frozen at four, no additions after any result is seen

**ARM D — dose-response (DESCRIPTIVE PRIMARY).** Label every session by the
open-book net delta-notional / equity **at session open, BEFORE that day's picks
are admitted** (read off `session_series`), into frozen bands
**[0, 0.5) · [0.5, 1) · [1, 2) · [2, ∞)**. Then report the outcome of the
positions **OPENED in each band**. Zero new ledger code and zero
counterfactuals: this is a conditional read of the shipped book, and it is the
arm the study is really about — it asks whether adding exposure onto an already
long book pays worse, which is the actual operator question. **MIN_CELL_N = 20
positions**; a band under it prints its n and is not read.

**ARM B — ceiling band.** Net-delta ceiling ∈ **{1.0, 1.5, 2.0, 2.5, ∞} ×
equity**, walked through a LOCAL `admission_banded` copy of `account_sim`'s
admission, kept in this module and not promoted to `lib/`.
**G-EQUIV** gates it: at the COMMITTED `caps.net`, the banded walk must
reproduce `account_sim.simulate()`'s book **EXACTLY** under `book_signature()`
equality. A forked admission that has drifted is a finding about the fork.

**ARM H\* — delta-TARGETED hedge-sleeve resizing.** The already-shipped bear
hedge sleeve is re-sized to hold net delta at a TARGET ∈ **{1.0, 1.5, 2.0} ×
equity**, instead of the shipped fixed ½-risk size. **Selection is untouched** —
no new bear pick is admitted, no signal pick is displaced; only the size of a
sleeve position the shipped rule already opened changes. This is the ONLY arm
that can push net delta DOWN, which follows directly from the long-only
constraint above, and it respects "bear = hedge sleeve only" by construction.

**ARM N — the random null band.** 200 seeded random admissions, matched on
positions-per-date to the shipped walk. The registered reading is explicit:
**an arm must beat ARM N's 95th percentile, not merely beat the shipped book.**
An arm inside the band is noise, whatever its point estimate. Seed fixed and
printed.

### Unit and metric

Unit = the **session** (date-clustered everything). ARM D's metric is the mean R
of positions opened per band, with `MIN_CELL_N = 20`. ARM B / ARM H\* are read
as within-date paired differences vs the shipped walk (`boot_ci_paired_by_date`,
`BOOT_N = 10000`, α = .05). Dollars print only inside the ledger census;
**R is what is quoted**, because every arm that changes admission or sizing
changes composition.

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

### Gates (non-zero exit on failure, in order)

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

### Bar for a reading to be adoption-eligible

An arm's paired result may be described as a candidate ONLY under the full
conjunction: date-clustered bootstrap CI excluding zero (`BOOT_N = 10000`);
**every** LOO fold positive (read `min_gain`); survives `protocol.window_cuts`
AND the ex-BOTH-windows cut added by hand; positive in every calendar year
present; right-signed on both pricing tiers; ≥ 25 affected dates; and **above
ARM N's 95th percentile.** Failing any one is failing. Worst-decile cells print
DESCRIPTIVELY with their n and are marked **NOT A CRITERION** (the 2026-08-13
nine-date decile wall). Even a full pass is a CANDIDATE queued for an
independent window — **nothing ships from this study under any outcome.**

### Verdicts, worded now

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

### Anti-tuning

Bands frozen at four, ceilings at five, targets at three, ARM N at 200 seeded
draws. Capital, risk %, per-position cap, net cap, positions-per-day,
`take_floor`, `downsize` and the exit profiles are NOT swept — they come from
`config/account-sim.yml` at their committed values for every arm. Compounding
OFF. No new selection column. **Every arm and every cell is reported regardless
of outcome**, including the ones that lose and the ones that power-stop, and no
threshold is moved after a number is seen.

### Standing caveat that must appear in the report

The ladder is itself in-sample (fitted on this book), so any exposure rule
evaluated on the same book is second-order in-sample. The mitigations are that
these are mechanical, entry-side, session-open rules with no fitted threshold,
and that adoption requires out-of-fold survival. The caveat does not disappear
if the numbers look good.

### Build notes (not part of the registration)

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

### Verdict-grammar note (2026-08-19, at build time — labelled, not a re-registration)

The registered labels leave one combination unnamed: an arm that clears
criterion (7) (beats ARM N's 95th percentile) while failing the rest of the
conjunction matches none of NOISE / DELTA-DOSE-RESPONSE /
LONG-ONLY-BY-CONSTRUCTION / POWER-STOPPED. Per the account_sim 2026-08-14
lesson (fix the grammar BEFORE a run, never after a number), the build assigns
that case to **NOISE with a printed QUALIFICATION block naming the arms**,
rather than inventing a fifth label. No criterion or threshold changed.

Also recorded: the disclosed per-date net-delta figures (median 0.33, max
1.17) were measured on THAT DAY'S PICKS at 1 contract; the study's
G-INVENTORY census measures the OPEN BOOK at session open under production
sizing (median +1.70, max +2.49 on the primary population). Different
quantities by definition, both printed with their definitions; the long-only
fact (0 net-short sessions) holds under both.
