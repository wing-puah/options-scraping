## 2026-08-12 — `vol_sleeve`: PRE-REGISTRATION (written BEFORE the run)

**Operator framing**, carried over from the `bear_rewrap` entry: *"bearish or
volatility plays should be added to diversify."* The bear arm answered its half
(bear is deployable as a HEDGE, not as selection). This is the vol half, and it
is asked in the same order: **does the structure pay at all → does it
diversify → and only then, when do you put it on.**

**Why it can be asked now.** It could not be before: the book is 96% directional
verticals, 21 of 1,607 plays classify as straddle/strangle, 3 ever reached
`BacktestResults`, and ZERO calendars have ever been priced. The blocker was
data, not analysis — a straddle needs a call AND a put at one strike/expiry, and
the cache was built from directional legs only, so it held a same-strike pair on
**15 of the 481 (ticker, expiry) groups the book entered (3%)**. The counterpart
scrape (`scripts/collector/fetch_counterpart_history.py`) closed that:
**1,322/1,337 mirrors cached, 481/481 groups (100%)**, all REAL Barchart marks
under the existing filename convention, so the same pricing path reads them.

### What is synthesized, and how (fixed before the run)

At every `(ticker, signal_date, expiry)` the pooled book (real + tweak, no `bs`)
actually entered, using `entry_underlying` as spot `S`:

| structure  | legs |
|---|---|
| `straddle` | long call + long put at `K*` = the cached strike nearest `S` |
| `strangle` | long put at the nearest cached strike **below** `S`, long call at the nearest **above** |
| `calendar` | short near-expiry call + long next-expiry call, both at `K*` |

Pricing is the production basis, not a new one: entry at the next session's
**Open** (falling back to that day's mark, then carry-forward), daily marks
carried forward per leg over `_weekday_grid` to `min(nearest DTE, 120)`, sizing
via `_size_contracts` on the shipped 50k/2% budget, and exits replayed through
the **frozen** `harness.replay` under `DEBIT_PROD` (pt .90 / sl .75 / tef .75).
Nothing about the exit engine is tuned in this study.

**Known basis caveat, stated up front:** the strike grid is *what the book
traded*, so "nearest strike to spot" is the nearest strike **flow touched**, not
the nearest listed. It biases toward strikes with real interest. The report
quotes the |K−S|/S distribution so the reader can see how ATM these actually are.

### The three questions, in order, with the gates

**Q1 — unconditional E by structure × DTE.** Mean `E` (held to cap) and `R`
(shipped exits) per structure and per DTE bucket (≤21 / 22–45 / 46–90 / >90),
with date-clustered bootstrap CIs and the per-year sign split.
*Non-null* = a cell with **n ≥ 30** whose mean E has a 95% date-clustered CI
excluding zero **and** the same sign in every year present.

**Q2 — date-level correlation with the DEPLOYED ladder.** The actual
diversification test, and the one that matters even if Q1 is negative: the
deployed book is `top_k_per_day(ladder_rank, k=3, eligible=A|B)` — the shipped
operator card — reduced to a daily series, against the sleeve's daily series on
overlapping dates.
*Non-null* = pooled daily correlation **< 0 with its bootstrap CI excluding
zero**, OR mean sleeve R on the deployed book's worst-decile dates **> 0** with
a date-clustered CI excluding zero. (This is the D2 test from `bear_deploy`,
applied to the vol sleeve.)

**Q3 — entry conditions. Runs ONLY if Q1 or Q2 is non-null**, and the conditions
are named here so they cannot be chosen after seeing the table: `vrp < 0`
(implied cheap against realized — the only time-series result in the reference
set), **earnings inside the DTE**, and **low `iv_pct`** (bottom tercile). If both
gates fail, the study prints the gate outcome and stops; that is a result, not a
failed run.

**Nothing in this study can ship on its own.** A vol sleeve that clears Q1 or Q2
becomes a candidate for the same treatment the bear sleeve got — a sized,
rules-bounded addition to the operator card — and would need its own deployment
arm first.
