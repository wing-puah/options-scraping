## index_bear_hedge — do the book's index bear plays pay for themselves as crash insurance?

_Registered ____-__-__ (DRAFT — not registered; becomes immutable in substance when the operator accepts it)._

**STATUS: DRAFT, drafted 2026-10-07.** Nothing here has been run. No outcome column has been read
for this design. The only numbers below come from a census of descriptor columns (dates,
tickers, structures, DTE, risk dollars) and from SPY/VIX closes. Seven decisions are
left open for the operator (see [Open decisions](#open-decisions)).

## Question

[`ticker_class`](../f1_selection/ticker_class.md) graded index ETFs on standalone R and found
no reliability edge. The 2026-10-07 root-cause note in `research/current.md` explains the
late index-bear loss as the market: no sell-off happened from 2026-04-08 to 2026-08-10. A bear
spread that pays only in a sell-off is insurance, so it should be graded as insurance.

Graded as a hedge, do the book's index bear plays earn their keep? That has three parts:

1. **Protection.** In sell-off episodes, do they reduce the deployed book's drawdown?
2. **Carry.** Between episodes, what do they cost?
3. **Net.** Over the whole span, does protection outweigh carry? At what episode frequency
   would it break even?

## What this is NOT

- **Not bear selection.** [`bear_arm`](../../arm-index.md#bear_arm) B1 and
  [`hedge_sizing`](hedge_sizing.md) D1 are closed: bear debit has no standalone selection edge
  (`research/lessons.md`). No arm here screens which index bear to take. The sleeve is every
  index bear the analysis emitted.
- **Not a pick rule.** `hedge_sizing` D4 is closed. Several index bears on one date are
  scaled to one risk unit, never ranked against each other.
- **Not a timing study.** The episode windows come from the SPY/VIX path after the fact. They
  mark when insurance should have paid. They are not an entry trigger and can never become
  one. [`hedge_timing`](hedge_timing.md)'s triggers and `hedge_sizing` D5's regime gates are
  not re-tested.
- **Not a re-run of `hedge_sizing` D2/D3.** Those grade all-ticker bears on signal-date
  buckets, with the tail taken from the book's own worst dates. This study keeps index bears
  only, uses market-defined episodes, works on the [MTM](../../glossary.md#mark-to-market-basis) curve, and
  splits cost inside and outside episodes. Those four gaps are what it adds.
- **Not a removal test for the §4 sleeve.** The bear sleeve in
  [deployment-rules §4](../../../docs/deployment-rules.md#s4) is operator policy. No verdict
  here removes it. A verdict files evidence only.
- **Not a re-grade of `ticker_class` or of the set-aside `ticker_class_regime` draft.**

## Definitions

- **Index bear.** A position whose ticker is in group G1 of the frozen `ticker_class` group
  table (SPY, QQQ, IWM, DIA; sha256 GT3) and whose direction is bear under
  `ticker_class.direction()`. In the census every such position is a `bear_put_spread` except
  two v3 `long_put`s. DIA appears in neither book.
- **Sell-off episode (PRIMARY, E-DD5).** Built from `backtests/mech_regime/spy_vix_daily_full.csv`
  alone. The definition was fixed on 2026-10-07 before any count was taken:
  - `dd_t = spy_close_t / max(spy_close over the trailing 63 trading days, incl. t) − 1`.
  - A trigger day has `dd_t ≤ −0.05`.
  - The episode runs from the 63-day high that the first trigger day measures against (the
    **peak**) to the minimum close (the **trough**). The trough is taken before `dd` first
    returns above −0.02, or within 42 trading days after the last trigger day, whichever
    comes first.
  - Episodes less than 10 trading days apart are merged.
  - The **window** is [peak, trough].
  - **Outside** is every session in no window and not within 10 trading days after a trough.
    That 10-day **buffer** counts on neither side.
- **Readings fixed at the census** (_the census agent hit these ambiguities; the readings are
  adopted here_):
  - The peak is measured from the first trigger day of the run; on ties the latest date wins.
  - The rolling high needs a full 63 rows, so `dd` is undefined before 2023-08.
  - The merge gap is counted in trading days of the SPY calendar. A merged episode keeps the
    earliest peak and the lowest close.
- **Secondary definitions, for sensitivity only.** These never yield a verdict on their own:
  - **E-DD8:** E-DD5 with a −0.08 trigger.
  - **E-VIX25:** a run of VIX closes ≥ 25, extended back to the start of the VIX ≥ 20
    stretch, at most 21 rows.
  - **E-20D5:** a 20-trading-day SPY return ≤ −0.05, taken as the union of the 20-day spans.
- **Deployed book.** `top_k_per_day(ladder_rank, k=3, A|B)` as `hedge_criteria` builds it,
  minus any index bear. Index bears sit on the sleeve side only, so they are never counted
  twice.
- **Sleeve.** Every index bear in the book. Each one's MTM dollars are scaled by
  `1 / n_indexbear(signal_date)`, so each signal date carries at most one risk unit.
  _(Open decision OD2.)_

## Dependencies

- `scripts/backtest_study/lib/book.py::load_book(include_bs=False)`: real rows plus
  `strike_expiry_tweak` rows, with the calibration gate ON.
- `scripts/backtest_study/lib/era.py`: one era per run.
- `lib/mtm_curve.py::book_curves(..., target=TARGET_STORED)` builds the MTM curves, net of
  `cost_total`. `max_drawdown`, `ulcer_index` and `path_stats` come from the same module.
- `lib/hedge_criteria.py`: the `unharmed` rule and `max_drawdown`, imported and never
  re-implemented. Its signal-date bucketing is NOT used; MTM sessions replace it, per
  next-steps §2.10.
- `scripts/backtest_study/f1_selection/ticker_class.py`: `group_of` and `direction`, imported.
  The group-table hash is checked at load.

## Population and basis, fixed here

- **Era.** v4 is PRIMARY. v3 is a separately labelled replication (see
  [Plan-time observations](#plan-time-observations-disclosed) for why it is not independent).
  Eras are never pooled.
- **Outcome basis.** MTM dollars, net of costs, under the shipped PROD exits as the loader
  carries them. No `be_after` variant.
- **Curve.** One daily MTM dollar series for the deployed book (B) and one for the sleeve (S).
  The hedged book is B + S.
- **Statistics never printed:** no annualised figure, Sharpe or time-to-recover.

## Plan-time observations, disclosed

Every figure here is a descriptor. None is an outcome.

**Episodes.** The SPY/VIX file runs from 2023-06-01 to 2026-09-25.

| # | Peak | Trough | SPY peak→trough | Max VIX | Sessions | In v4 span | In v3 span |
|---|---|---|---|---|---|---|---|
| 1 | 2023-07-31 | 2023-10-27 | −10.3% | 21.7 | 64 | no | no |
| 2 | 2024-03-27 | 2024-04-19 | −5.4% | 19.2 | 17 | yes | no |
| 3 | 2024-07-16 | 2024-08-05 | −8.4% | 38.6 | 15 | yes | yes |
| 4 | 2025-02-19 | 2025-04-08 | −19.0% | 52.3 | 35 | yes | yes |
| 5 | 2025-10-29 | 2025-11-20 | −5.1% | 26.4 | 17 | yes | yes |
| 6 | 2026-01-27 | 2026-03-30 | −9.1% | 31.0 | 44 | yes | yes |

**Episode counts per era.**

| Definition | v4 | v3 |
|---|---|---|
| E-DD5 (primary) | 5 | 4 |
| E-DD8 | 3 | 3 |
| E-VIX25 | 7 (several of 1–4 sessions) | 7 |
| E-20D5 | 4 | 3 |

**Index bears per v4 episode (E-DD5).** "Entered" means the signal date falls in the window.
"Open into" means the scheduled span [signal, signal + DTE] overlaps it.

| Episode | Index bears entered | Index bears open into | Book positions open into |
|---|---|---|---|
| 2024-03/04 | 9 | 30 | 238 |
| 2024-07/08 | 7 | 33 | 288 |
| 2025-02/04 | 11 | 25 | 225 |
| 2025-10/11 | 5 | 18 | 209 |
| 2026-01/03 | 12 | 26 | 260 |
| Outside (501 of 679 sessions) | 145 | — | — |

These counts come from a replica of `load_book`'s row selection that read no outcome column,
so they are close to the loader's counts but not identical. The build prints the loader's own
census.

**Sleeve shape.**

- Index plays are bear-heavy in calm months too. The v4 index-bear share is ≥ 0.83 in 21 of 33
  months, so the sleeve is close to always on rather than timed.
- Structure, median DTE (≈ 59) and median risk (≈ $1,100) barely differ between inside and
  outside the windows.

**What the census means for power.**

1. **The power unit is episodes, and v4 has five.** No magnitude can be estimated from five.
   The strongest possible in-sample read is a sign: 5 of 5 episodes protected has a one-sided
   sign-test p of 0.031, while 4 of 5 has 0.19. The book can therefore reach a verdict only
   if every episode agrees, and even then only PROVISIONALLY.
2. **One episode is far larger than the rest.** 2025-02/04 fell 19% with VIX at 52; no other
   reached 11%. Per `lessons.md`, one window can carry a whole effect. Leave-one-episode-out
   is therefore a veto (RB2).
3. **v3 is not an independent replication.** The v4 tab was back-filled over 2024–2026, so v4
   and v3 cover the same four market episodes. v3 can show that a v4 result does not depend
   on which plays the prompt version emitted. It cannot show that the result holds in other
   markets. v3's index bears are also concentrated: 50 of its 56 in-window positions fall in
   two episodes.
4. **Hindsight in the analysis.** Both eras were generated by an LLM over dates that may fall
   inside its training data. If the index-bear share rises inside episodes, that may be recall
   rather than reading the tape. Forward episodes are the only evidence free of this. This is
   why the in-sample verdict ceiling is PROVISIONAL (see [Forward confirmation](#forward-confirmation)).
5. **Modal expectation, written down now.** UNDERPOWERED or PROTECTS-BUT-COSTS-MORE. The four
   calm months alone carry a large loss, and five episodes are unlikely to agree unanimously.
   An all-NULL result changes nothing about the §4 sleeve.

## Arms

| Arm | Book | Sleeve | Role |
|---|---|---|---|
| B | deployed book | none | base |
| H | deployed book | index bears, one unit per date | **graded** |
| H-raw | deployed book | index bears at recorded size | printed, never graded (OD2) |
| H-stock | deployed book | stock bears, one unit per date | printed, never graded: is any protection index-specific? |

Exactly one arm is graded, so no configuration is selected from many and the primary needs no
PBO. If the operator adds a sizing grid (OD3), the grid is selected from and CSCV applies (see
[Overfitting](#overfitting)).

## Unit and metric

**M1, protection per episode.** For each episode window, take the worst drawdown within the
window on each curve, measured from the window's own running high:
`DD_e(X) = min_t (L_X(t) − max_{s∈[peak,t]} L_X(s))`.
Then `ΔDD_e = DD_e(H) − DD_e(B)`, in dollars. A positive value means the sleeve reduced the
drawdown. The study also prints the sleeve's own MTM dollars inside the window (`G_e`).

**M2, carry outside episodes.** The sum of the sleeve's MTM dollars over the outside sessions
(`C`), and the same figure per 100 outside sessions. Buffer sessions are printed separately
and counted on neither side.

**M3, net.**

- `NET = ΣG_e + C + buffer`, which equals the sleeve's total MTM dollars over the span.
- The full-span drawdown of H against B uses `hedge_criteria.unharmed` on MTM maxDD and the
  worst day.
- **Break-even frequency** `f* = −(C per outside session) / mean(G_e)`, in episodes per 252
  sessions. It is set beside the observed E-DD5 rate in the SPY/VIX file (6 episodes in about
  3.3 years). It is only meaningful when `mean(G_e) > 0`; otherwise it prints "no break-even".

**Diagnostics, printed and never graded:**

- the MTM Ulcer index of B and H;
- `corr(S, B)` on sessions outside episodes, since a positive value means re-wrap (`lessons.md`);
- M1–M3 under each secondary definition.

## Gates

A failed gate refuses the run (non-zero exit). It does not produce a verdict.

| Gate | Condition |
|---|---|
| G-ERA | One era, named in the header; `era.py` refuses a mismatch |
| G-MTM | `book_curves` G-MTM reconciliation passes at the shipped tolerance, never widened |
| G-HASH | The episode-definition hash and the GT3 group-table hash match the values recorded at acceptance |
| G-CENSUS | The episode and position census prints before any outcome column is read |
| G-OPEN | ≤ 25% of the sleeve's in-window positions are still open at `path_data_end`, per episode; a failing episode is NOT EVALUABLE |

## Power floor

- An episode is **evaluable** when it has ≥ 3 sleeve positions open into the window, passes
  G-OPEN, and has ≥ 5 sessions.
- The primary verdict needs **≥ 5 evaluable E-DD5 episodes** in the era. Below that, the
  verdict is UNDERPOWERED.
- The floor counts episodes, not positions. It may not be met by loosening the definition or
  by pooling eras. v4 has exactly 5 candidates, so one non-evaluable episode makes it
  UNDERPOWERED.

## Overfitting

- **Permutation read (calendar shift).** The statistic is `T = Σ_e ΔDD_e`. The null shifts
  the whole set of episode windows circularly across the era's session span. Lengths and gaps
  are kept, every shift moves at least 21 sessions, all shifts are enumerated, and the
  windows are re-evaluated on the same curves. The one-sided p-value is the rank of the true
  T. This asks whether the sleeve helps more in real sell-offs than in random windows of the
  same shape. Shifted windows can overlap real episodes, which makes the test conservative.
  _(Adapted from the circular-shift test in `ticker_class_regime`.)_
- **Robustness battery, veto only.** A check can block a protective verdict. None can create
  one.
  - **RB1:** primary on E-DD8 and E-20D5 keeps the sign of `ΣΔDD_e`.
  - **RB2:** leave-one-episode-out keeps the sign of `ΣΔDD_e` and of NET for every left-out
    episode.
  - **RB3:** H-raw keeps the sign of `ΣΔDD_e`.
  - **RB4:** real-priced rows only (no tweak rows) keep the sign, when ≥ 3 episodes are still
    evaluable.
  - **RB5:** H-stock does not protect at least as well. If it does, the verdict is re-worded
    "bear protection, not index-specific".
- **PBO/CSCV** applies only if OD3 adds a sizing grid. The blocks would be episodes plus the
  inter-episode stretches between them. A PBO above 0.50 vetoes any recommended size.

## Verdicts, worded now

The verdicts are checked in order, and the first match wins. n is the number of evaluable
E-DD5 episodes.

| Verdict | Condition |
|---|---|
| UNDERPOWERED | n < 5. This is not a lean, and no direction is quoted. |
| EARNS ITS KEEP (PROVISIONAL) | `ΔDD_e > 0` in all n episodes; permutation p ≤ 0.05; NET > 0; H is `unharmed` against B on full-span MTM; RB1–RB4 hold |
| PROTECTS, COSTS MORE THAN IT SAVES | `ΔDD_e > 0` in ≥ n − 1 episodes, and NET ≤ 0. Prints `f*` against the observed rate. Read as: real insurance, priced too high at this sample's episode frequency. |
| DOES NOT PROTECT | `ΔDD_e ≤ 0` in ≥ 2 episodes, or median `ΔDD_e ≤ 0` |
| INDETERMINATE | anything else; prints the criterion vector (n, signs, p, NET, unharmed, RB flags) |

- If RB5 fires, the first two verdicts gain the suffix "— bear protection, not
  index-specific".
- **v3 replication.** The same rule runs on v3 and is labelled "same-episode replication". It
  can contradict v4 and block "EARNS ITS KEEP". It can never upgrade v4 on its own.

## Forward confirmation

- **What is graded.** Every E-DD5 episode whose peak falls after the acceptance date is graded
  once its buffer closes (trough + 10 sessions), on the then-current era. The study appends a
  line to `research/study-results/f5_hedging/`.
- **Confirmation.** A PROVISIONAL verdict becomes CONFIRMED after ≥ 2 forward episodes, all
  with `ΔDD_e > 0`, and forward carry per outside session no worse than `f*` implies at the
  observed rate.
- **Disconfirmation.** Any forward episode with `ΔDD_e ≤ 0` sends it back to INDETERMINATE.
- **Sunset.** 3 years from acceptance. At roughly 1.8 episodes a year, two episodes take
  about 1–2 years. That wait is the honest cost of this sample size.

## Ship criteria

Nothing ships from this study.

- **EARNS ITS KEEP (CONFIRMED)** files an entry in `research/deployment-evidence.md` under "to
  be tested": index bear spreads as the §4 sleeve's preferred vehicle.
- **PROTECTS, COSTS MORE** files `f*` as the price of the insurance.
- **No verdict removes the §4 sleeve.**

## Open decisions

The operator settles these before acceptance. Each is written as a choice, with the drafter's
recommendation in the last column.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| OD1 | What is "the book" being hedged? | (a) deployed A/B top-3 ladder; (b) every priced row | (a): it is what the operator holds |
| OD2 | Sleeve sizing | (a) one risk unit per signal date; (b) recorded size, which makes the sleeve as large as the book | (a), with (b) as RB3 |
| OD3 | Sizing grid f ∈ {¼, ½, 1}? | (a) no grid; (b) grid, with CSCV | (a): five episodes cannot select a size |
| OD4 | Is the 5-episode floor right, given v4 has exactly 5? | (a) keep 5 and accept that an UNDERPOWERED result is likely; (b) grade forward only and print the in-sample read as exploratory | Operator's call. (b) is the cleaner design given the hindsight risk in observation 4. |
| OD5 | Is the 2023 episode out of scope? | No book covers it. Fetch older SPY/VIX only to estimate the base rate for `f*`? | Yes, base rate only. It touches no outcome. |
| OD6 | Primary window | (a) [peak, trough]; (b) [peak, trough + buffer], which credits the bounce | (a): insurance is judged on the way down |
| OD7 | Is G-OPEN at 25% per episode right for 2026-01/03, with DTE ≈ 59 and data running to 2026-09? | Likely fine; check at build | Keep 25% |

## Build notes

- Module: `scripts/backtest_study/f5_hedging/index_bear_hedge.py`.
- On acceptance it also needs a catalog entry, an `arm-index.md` section and a row in the
  pre-registrations README. All three are shared files: check `git status` before editing.
- Do not run the study until the operator has accepted this registration, because a run
  overwrites `-latest.txt` and `site/`.
