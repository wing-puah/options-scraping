## bear_fast_exit — does a fast exit make a bear debit pay?

_Registered ____-__-__ (DRAFT — NOT REGISTERED; becomes immutable in substance when the operator accepts it)._

**STATUS: DRAFT — NOT REGISTERED.** Until acceptance every number, arm, gate
and verdict below may be edited. After acceptance none of them may. The
registration date is filled in on acceptance and is the only date this file
then carries. No module exists and none may be written before acceptance.

## Question

Is there a bear-debit exit, fixed at order entry, that holds only a few
sessions or takes a small profit, and is positive net of trading costs?

The operator, 2026-09-22: *"i think bear debit spreads still work, i deploy
some of them but i close them out very quickly. i think continue testing the
scenario."*

Two things are asked, in this order. The first is the operator's claim; the
second is what the book has already hinted at.

1. **Level.** Under a fast exit, is bear-debit [net R](../../glossary.md#net-r)
   above zero, with a date-clustered [CI](../../glossary.md#ci) excluding zero?
2. **Delta.** Is the fast exit better than the shipped bear-debit exit, paired
   by row, net of costs?

A fast exit that only passes the delta question cuts a loss. It does not make
bear debits "work", and it ships nothing on its own (see
[Verdicts](#verdicts-worded-now)).

## What this is NOT

Each line names an exit already tested on bear debits, so this study does not
re-test a closed question under a new name.

| Already tested | Where | Verdict | Why this study differs |
|---|---|---|---|
| Profit targets 0.75, 1.10, 1.25; trails; breakeven stops at 0.20–0.75; `tef` null/0.85; `sl .50` | [`bear_arm` B2](../../arm-index.md#bear_arm), [record](../../study-results/f1_selection/bear_arm.md) | `NOT met`; best is `sl .50` at Δ +0.030, CI [−0.003, +0.061] (2026-09-19) | No target below 0.75 and no stop measured in sessions |
| Breakeven stop at 0.20–0.40 against the shipped merge | [`bear_giveback` ARM P](../../arm-index.md#bear_giveback), [record](../../study-results/f2_management/bear_giveback.md) | No CI excludes zero | Same: nothing below one week |
| Profit target 0.60 and up × stop × `tef`, walk-forward, whole book | [`exit_drawdown` ARM W](../../arm-index.md#exit_drawdown), [record](../../study-results/f2_management/exit_drawdown.md) | `UNDERPOWERED` | Account drawdown metric, not bear-keyed |
| "At session X, if R is past ±Y, exit"; X ∈ {5, 10, 15, 20} | [`staged_exit` ARM E](../../arm-index.md#staged_exit), [pre-registration](staged_exit.md) | 0 of 40 powered cells clear; day-5 loss cuts harmful | Whole book, conditional on a band, never sessions 1–3 |
| Day-0 cut when the stock did not confirm | [`next_day_move` ARM R](../../arm-index.md#next_day_move), [record](../../study-results/f2_management/next_day_move.md) | `worse than -0.5 sigma` clears all six criteria, bear-only; no rule made | Conditional on the day-0 move; still negative afterwards (−0.039) |
| The model's `horizon` as a time exit | [`exit_from_text` E3](../../arm-index.md#exit_from_text) | Fails its survival control | Text-derived, not a fixed session count |

Also not:

- **Not a selection study.** [`bear_arm` B1](../../arm-index.md#bear_arm)
  found 0 of 496 decision-time subsets positive. No clause is added to
  selection here, and [§1.4](../../../docs/deployment-rules.md#s1) is not
  touched by any verdict below.
- **Not a hedging study.** This measures bear debits standalone. The hedge
  sleeve's value is protection on drawdown days, which a fast exit removes by
  design. That trade-off belongs to
  [`hedge_portfolio`](../../arm-index.md#hedge_portfolio).
- **Not an intraday study.** Marks are daily closes. The operator's same-day
  exits at a better price than the close cannot be replayed (see
  [Harness](#harness)).

## Population and basis, fixed here

- **Structures.** `bear_put_spread` and `long_put`, entry net > 0 (debit).
  `long_put` is ≈2% of these rows, so the result is about bear put spreads.
- **Rows.** `lib/book.py::load_book(include_bs=False)`: real and
  `strike_expiry_tweak` tiers only. `bs_options_hist` is never admitted.
  Rows with `fill_trusted` False are excluded.
- **Eras.** v4 (`current`) is PRIMARY. v3 is the replication era, run with
  `--era v3`. The two are never pooled. Every report header names its era.
- **The date count is not fixed here.** It is every signal date the era
  resolves at run time with at least one row in scope. No count is written into
  this file or the module.
- **Sealed dates are excluded while
  [`holdout_seal`](../f4_deployment/holdout_seal.md) stands.** They are read
  once, by the forward clause C7, after the seal releases them. If the
  operator declines the seal, C7 reads signal dates on or after 2026-08-11 as
  soon as the C7 floor is met.

### The baseline is the shipped exit

The comparison is paired against the exit production runs today
([§5](../../../docs/deployment-rules.md#s5)), never against a clean profile.

| Position | Baseline profile |
|---|---|
| Bear debit, signal date mech `BEAR_HE` | pt 0.90, sl 0.75, `tef` 0.75, trail 0.50 armed at +0.50 |
| Bear debit, any other date | pt 0.90, sl 0.75, `tef` 0.75, no trail |

The breakeven stop was reverted 2026-08-24, so the baseline carries none.
`bear_giveback.prod_profile_for(rec, 0.50, True)` still adds it and must not
be used. The module reads `structure_exit.enabled` and the `regime_exit`
cells from `config/backtest.yml` at run time and prints the profile it built
(gate G2).

### Cost is charged on every arm

Cost is a requirement, not a sensitivity. Stored rows are gross:
`commission_per_contract` and `slippage_frac_of_spread` are 0 in
`config/backtest.yml`, so `cost_total` is 0.0 on every row. The study
therefore charges cost itself, per arm, because each arm exits on a different
day and pays a different exit spread.

- **The cost point** is the one
  [`cost_sensitivity`](cost_sensitivity.md) registers as its `ARM X`: $0.65
  per contract plus 25% of the quoted spread, per leg, per side
  ([cost point](../../glossary.md#cost-point)).
- **The formula** is `scripts/backtest/simulate.py::_apply_costs`, applied to
  the arm's own exit day. The study reimplements it only if it cannot call
  it, and a test then pins the two against each other.
- **Missing or degenerate quotes** follow `cost_sensitivity` `ARM Q`'s
  three-step fallback. A position with no usable quote is UNCOSTABLE and
  excluded, never charged zero.
- **An expired leg is charged at entry only.**
- **Wide quotes are reported, never dropped.** Positions whose entry quoted
  spread exceeds 50% of the debit are counted and their figures printed
  separately. They stay in the primary metric.

## Plan-time observations, disclosed

Read on 2026-09-22 while drafting, from the 2026-09-19 exports. **Every arm
below was computed on both eras before this file was written.** The existing
book can therefore fail to refute an arm but cannot confirm one. C7 is what
separates this study from a post-hoc story.

### Exploratory replay

The shipped baseline, the frozen harness and a scratch cost model. Nothing
here is a result. Full cost is on the quote-sane subset only: positions whose
entry quoted spread is at most half the debit (v4 360 of 483, v3 245 of 332).

| Arm | Era | Δ gross vs shipped | CI | Gross meanR | Net meanR, full cost | CI |
|---|---|---|---|---|---|---|
| Shipped | v4 | — | — | −0.082 | −0.207 | [−0.301, −0.114] |
| TP +0.10 | v4 | +0.094 | [+0.031, +0.156] | +0.011 | −0.111 | [−0.170, −0.052] |
| Session 3 | v4 | +0.112 | [+0.034, +0.191] | +0.030 | −0.061 | [−0.098, −0.021] |
| Session 5 | v4 | +0.116 | [+0.044, +0.186] | +0.034 | −0.050 | [−0.099, +0.001] |
| TP +0.20 or session 3 | v4 | +0.116 | [+0.035, +0.199] | +0.034 | −0.066 | [−0.099, −0.032] |
| Shipped | v3 | — | — | −0.109 | −0.172 | [−0.299, −0.038] |
| Session 3 | v3 | +0.090 | [−0.018, +0.194] | −0.019 | −0.093 | [−0.143, −0.039] |
| TP +0.20 or session 3 | v3 | +0.111 | [−0.003, +0.220] | +0.003 | −0.087 | [−0.134, −0.041] |

What it says:

- **Every fast exit cuts the loss on v4**, and for the six arms checked the
  cut survives every leave-one-date-out fold (min +0.06 to +0.11).
- **None is positive net of cost, on either era.** Gross meanR sits near
  zero. On quote-sane rows the median round trip costs 0.03–0.04 R and the
  mean 0.05–0.07 R, which is larger than any gross level.
- **Most stored rows are gross.** 584 of 598 results rows and 1,661 of 1,665
  proxy rows have a blank `cost_total`, because they predate the cost model.
- **On v3 real rows nothing separates from the shipped exit.** The v3 cut is
  carried by the tweak tier.
- **The cut comes from both tails.** Shipped winners above +0.50 R (v4 n=146)
  average +1.17 R; under session 3 or TP +0.20 they average +0.29 R. Shipped
  losers at −0.50 R or worse (n=259) go from −0.79 R to −0.11 R.
- **The gross-positive rows are the wide-quote rows.** On the quote-sane
  subset gross meanR falls to about zero for every fast arm.

### Path census

Share of bear-debit rows whose close reached the level within the first N
sessions (session 1 is the entry-day close).

| Era | Level | N = 1 | N = 3 | N = 5 | N = 10 |
|---|---|---|---|---|---|
| v4 | +0.20 | 11% | 28% | 36% | 47% |
| v4 | +0.30 | 7% | 18% | 27% | 38% |
| v3 | +0.20 | 16% | 30% | 38% | 49% |
| v3 | +0.30 | 10% | 20% | 29% | 37% |

The unmanaged path peaks late: median session 13 on v4 and 11 on v3, with
42% (v4) and 27% (v3) of peaks after session 20. This agrees with
[`bear_giveback` ARM U](../../arm-index.md#bear_giveback): the rows that end
profitable peak late, and the rows that peak inside three sessions give back
87%.

### The operator's live bear debits

From the broker fills, classified from opening fills only, because the
journal's stored labels mislabel some closing bull call spreads. Aggregate
only.

| Cut | Opened | Closed | Median hold | Closed ≤ 7 days | Realized | Per dollar of debit |
|---|---|---|---|---|---|---|
| All, 2025-02 → 2026-09 | 31 | 29 | 5 calendar days | 23 | +$761 | +0.061 |
| 2025 | 15 | 15 | 4 days | 13 | +$1,759 | +0.395 |
| 2026 | 16 | 14 | 5.5 days | 10 | −$998 | −0.124 |

The winners' median gain is +0.26 of the debit. Twenty-nine closes over 13
underlyings is far below any floor here, and two cheap spreads returning 5–7×
the debit carry the 2025 total. It shows the operator's habit, not an edge.

The operator also opened 130 naked long puts (median hold 2 days, −$2,011
realized). The book holds 10 `long_put` rows, so that instrument cannot be
tested here.

## Arms

Frozen at three families and eight arms. Nothing is added after a cell is read.

- **`ARM TP` — small profit target.** The shipped profile with `pt` replaced
  by 0.10, 0.20 or 0.30. Stop, `tef` and the BEAR_HE trail are unchanged.
- **`ARM TS` — time stop in sessions.** The shipped exit, plus: if the
  position is still open after session N, exit at the close of session N.
  N ∈ {1, 2, 3, 5}. Session 1 is the entry-day close.
- **`ARM OP` — the operator's rule, as inferred.** Profit target 0.25 or the
  close of session 5, whichever comes first. The two numbers come from the
  live census above: the winners' median gain (+0.26) and 23 of 29 closes
  within 7 calendar days, which is about five sessions.

The baseline is the shipped book, not an arm.

## Harness

Every arm replays through the frozen `scripts/backtest_study/lib/harness.py`,
which is not edited, copied or forked.

- **`ARM TP`** passes `pt` to `harness.replay`, which already supports it.
- **`ARM TS`** composes around `harness.replay`, as
  [`staged_exit` ARM E](../../arm-index.md#staged_exit) does. Replay the
  shipped profile. If `days_held > N`, replace the result with the mark at
  session N, or the last priced mark before it. If no mark is priced at or
  before N, the row keeps its shipped result.
- **`ARM OP`** applies the `ARM TS` composition to the `ARM TP` replay.

The harness grid starts at the first weekday after the signal date, which is
the entry session. A session-1 exit is therefore the close of the day the
position opened. An exit inside that session, at a price other than the close,
cannot be replayed from daily marks. The live habit of closing within hours is
approximated by the entry-day close, and the report says so.

## Unit and metric

- **Unit** is the signal date. Every CI is date-clustered, `BOOT_N = 10000`,
  α = 0.05.
- **Metric** is net R: the arm's replayed R minus that arm's round-trip cost
  in R. Gross R prints beside it and grades nothing.
- **Level** (question 1): net [meanR](../../glossary.md#meanr) with
  `protocol.boot_ci_by_date`.
- **Delta** (question 2): paired net ΔR against the shipped book with
  `protocol.boot_ci_paired_by_date`.
- [PF](../../glossary.md#pf) prints with its date-clustered CI and is never
  quoted without meanR.

## Gates

Each gate exits non-zero on failure, except G4, which prints a verdict.

- **G0 POWER.** Per arm and era, at least 25 affected dates and 60 affected
  rows. An arm below either prints `UNDERPOWERED` and its census, and no
  outcome number.
- **G1 LEAK GUARD.** The arms run over the whole book with the bear keying
  inside the arm. Every non-bear row must come back unchanged
  `(exit_reason, days_held, round(pnl, 10))`. One changed row fails the run.
- **G2 BASELINE IS PRODUCTION.** The baseline profile is built from
  `config/backtest.yml` at run time and printed. `ARM TP` at pt 0.90 and
  `ARM TS` at N beyond the path must each reproduce the baseline exactly on
  every row.
- **G3 EXPORT IS POST-RE-PRICE.** On v4, every row in scope must carry a
  `cost_total` value, which only rows written after the B1/B2 fold do. This
  forces the run after the whole-book re-price
  ([next-steps §0](../../next-steps.md#s0), item 8). v3 is frozen and will not
  be re-priced, so G3 does not apply there. On v3 the `fill_trusted` filter is
  the guard.
- **G4 QUOTE PROVENANCE — prints, does not refuse.** If more than 25% of an
  era's charged legs use fallback 2 or are UNCOSTABLE, that era prints its
  quote census and the verdict `UNCOSTABLE`, and no criterion is graded.
- **G5 NO NEW STATISTIC.** No annualised figure, Sharpe or time-to-recover.
- **G6 NO HARDCODED CENSUS.** Every count in the report is computed by the run.

## Bar for a candidate

An arm is graded on both questions. Failing any criterion of a question fails
that question.

**Question 1 — level (does it pay):**

- **C1** net meanR > 0 on v4, CI excluding zero.
- **C2** the same on v3.

**Question 2 — delta (does it beat the shipped exit):**

- **C3** paired net ΔR > 0 on v4, CI excluding zero.
- **C4** the same on v3.

**Robustness, applied to every question an arm passes:**

- **C5** every [LOO](../../glossary.md#loo) fold by date keeps the sign.
- **C6** the sign holds ex-Mar–Apr-2025, ex-Feb–Apr-2026 and ex-both
  (`protocol.window_cuts` plus the ex-both cut by hand), in every calendar
  year present, and in both pricing tiers.
- **C7 FORWARD.** On sealed or post-registration signal dates, read once: the
  same sign as on v4, on at least 15 dates and 30 rows. No CI is required,
  because that window cannot power one. Below the floor C7 is PENDING, and a
  pending C7 means nothing ships.

Eight arms on two questions and two eras will produce about one false
positive by chance at α = 0.05. That is why every question needs both eras,
C5, C6 and C7 together.

## Verdicts, worded now

- **PAYS** — an arm clears C1–C7. Bear debits are positive net of cost under
  that exit. The operator is asked to sign a new
  [§5](../../../docs/deployment-rules.md#s5) row for bear debits. Its rollback
  trigger is registered in the same commit. §1.4 is not changed by this
  verdict. Re-opening bear debits as a selection needs its own registration.
- **BLEED-CUT** — an arm clears C3–C7 but fails C1 or C2. The exit loses less
  than the shipped one, and still loses. Nothing ships. Changing the §4 hedge
  sleeve's exit goes to the operator with this conflict stated: a fast exit
  removes the protection the sleeve is held for, and only
  [`hedge_portfolio`](../../arm-index.md#hedge_portfolio) can price that.
- **NULL** — no arm clears C3 and C4. The shipped exit stands. The bear-debit
  exit question is closed on these dates.
- **UNDERPOWERED** — G0 stops every arm. Census only.
- **UNCOSTABLE** — G4 fires on v4. The quote census is the result; the fix is
  a quote backfill, not a lower gate.

## Anti-tuning

- **Expected outcome, written now:** BLEED-CUT on v4, NULL or BLEED-CUT on
  v3, and PAYS nowhere. The exploratory read above puts every arm's net level
  below zero with a CI clear of it on both eras. A PAYS would be a surprise
  and needs C7 before anyone reads it.
- The eight arms, the cost point, the fallback ladder, the floors and the
  windows are fixed here. None moves after a cell is read.
- No arm is conditioned on regime, mech cell, DTE, `|delta|` or the day-0 move.
  A conditioned fast exit is a new registration.
- The `ARM OP` numbers are fixed from the live census above. They are not
  re-derived from later fills.

## What ships if it passes

Only a PAYS verdict can ship, and only as a [§5](../../../docs/deployment-rules.md#s5)
row for bear debits that the operator signs. It carries a rollback trigger,
registered before it ships, keyed to new bear-debit closes. The evidence goes
into [`deployment-evidence.md`](../../deployment-evidence.md) in the same
commit.

## Dependencies

| Prerequisite | Why it binds |
|---|---|
| The whole-book re-price ([next-steps §0](../../next-steps.md#s0), item 8) and a fresh export | G3; the stored book mixes pricing regimes |
| The option-history cache pulled (`backup_research_caches.py pull`) | The cost model reads `Bid`/`Ask` from it |
| Operator acceptance of this file | No module before acceptance |
| [`holdout_seal`](../f4_deployment/holdout_seal.md) decided | C7 reads sealed dates only after release |
