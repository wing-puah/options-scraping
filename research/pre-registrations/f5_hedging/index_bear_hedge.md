## index_bear_hedge — do the book's index bear plays pay for themselves as crash insurance?

<!-- outcome:start -->
> Latest outcome: forward `STILL-OPEN`, 0 episodes graded — 2026-10-09. In-sample description only, no verdict: the sleeve cut drawdown in 5 of 5 v4 episodes, net −$43,947 · [record](../../study-results/f5_hedging/index_bear_hedge.md).
<!-- outcome:end -->

_Registered 2026-10-09. Drafted 2026-10-07._

**STATUS: ACCEPTED BY DEFAULT 2026-10-09 on the drafter's recommended defaults; the operator
may revisit (a revisit after a result is a NEW registration, never an edit).** OD4 was decided
by the main session: only future sell-offs are graded. Every open decision is answered beside
the text it amends, tagged _Resolved at build (2026-10-09)_. Every default was fixed before any
outcome column was read.

_Resolved at build (2026-10-09):_ accepted by default under the 2026-10-09 policy, so the study
was built and run that day. Its report files under the stem `index_bear_hedge`. Module:
`scripts/backtest_study/f5_hedging/index_bear_hedge.py`.

## The question

Graded as a hedge, do the book's index bear plays earn their keep? Three parts:

1. **Protection.** In sell-off episodes, do they reduce the deployed book's drawdown?
2. **Carry.** Between episodes, what do they cost?
3. **Net.** Over the whole span, does protection outweigh carry? At what episode frequency
   would it break even?

Only sell-off episodes that start after 2026-10-09 are graded. The five in-sample v4 episodes
print as a description and are never graded. Under the holdout seal
(`f4_deployment/holdout_seal.md`) this registration is not a sealed reader. So the forward read
stays STILL-OPEN until the seal lifts.

Why as insurance: [`ticker_class`](../f1_selection/benchmark/ticker_class.md) found no
standalone edge for index ETFs. The 2026-10-07 note in `research/current.md` blames the late
index-bear loss on a market with no sell-off from 2026-04-08 to 2026-08-10.

## What this study is not

- **Not bear selection.** [`bear_arm`](../../arm-index.md#bear_arm) B1 and
  [`hedge_sizing`](hedge_sizing.md) D1 are closed (`research/lessons.md`). No arm here screens
  which index bear to take. The sleeve is every index bear the analysis emitted.
- **Not a pick rule.** `hedge_sizing` D4 is closed. Several index bears on one date are scaled
  to one risk unit, never ranked against each other.
- **Not a timing study.** The episode windows come from the SPY/VIX path after the fact. They
  mark when insurance should have paid. They are not an entry trigger and can never become one.
  [`hedge_timing`](hedge_timing.md)'s triggers and `hedge_sizing` D5's regime gates are not
  re-tested.
- **Not a re-run of `hedge_sizing` D2/D3.** Those grade all-ticker bears on signal-date
  buckets, with the tail from the book's own worst dates. This study adds four things: index
  bears only, market-defined episodes, the [MTM](../../glossary.md#mark-to-market-basis) curve,
  and cost split inside and outside episodes.
- **Not a removal test for the §4 sleeve.** The bear sleeve in
  [deployment-rules §4](../../../docs/deployment-rules.md#s4) is operator policy. No verdict
  here removes it. A verdict files evidence only.
- **Not a re-grade of `ticker_class` or of the set-aside `ticker_class_regime` draft.**

## Definitions

### Index bear

A position whose ticker is in group G1 of the frozen `ticker_class` group table (SPY, QQQ, IWM,
DIA; sha256 GT3), and whose direction is bear under `ticker_class.direction()`. In the census
every such position is a `bear_put_spread` except two v3 `long_put`s. DIA appears in neither
book.

### Sell-off episode (PRIMARY, E-DD5)

Built from `backtests/mech_regime/spy_vix_daily_full.csv` alone. The definition was fixed on
2026-10-07 before any count was taken.

- `dd_t = spy_close_t / max(spy_close over the trailing 63 trading days, incl. t) − 1`.
- A trigger day has `dd_t ≤ −0.05`.
- The episode runs from the **peak** to the **trough**. The peak is the 63-day high that the
  first trigger day measures against. The trough is the minimum close, taken before `dd` first
  returns above −0.02, or within 42 trading days after the last trigger day, whichever comes
  first.
- Episodes less than 10 trading days apart are merged.
- The **window** is [peak, trough]. _Resolved at build (2026-10-09), OD6:_ (a), [peak, trough].
  Insurance is judged on the way down; the bounce is not credited.
- **Outside** is every session in no window and not within 10 trading days after a trough. That
  10-day **buffer** counts on neither side.

Readings fixed at the census (the census agent hit these ambiguities; the readings are adopted
here):

- The peak is measured from the first trigger day of the run. On ties the latest date wins.
- The rolling high needs a full 63 rows, so `dd` is undefined before 2023-08.
- The merge gap is counted in trading days of the SPY calendar. A merged episode keeps the
  earliest peak and the lowest close.
- _Resolved at build (2026-10-09):_ the trough is the lowest close from the first trigger day to
  the search end; ties go to the earliest date. The next episode is searched from the recovery
  day. An episode the data has not closed is listed and never read.

### Secondary definitions, for sensitivity only

These never yield a verdict on their own.

- **E-DD8:** E-DD5 with a −0.08 trigger.
- **E-VIX25:** a run of VIX closes ≥ 25, extended back to the start of the VIX ≥ 20 stretch, at
  most 21 rows.
- **E-20D5:** a 20-trading-day SPY return ≤ −0.05, taken as the union of the 20-day spans.
- _Resolved at build (2026-10-09):_ the E-VIX25 extension reaches back at most 21 rows from the
  first VIX ≥ 25 close. Both E-VIX25 and E-20D5 use the window's last day as the trough for the
  buffer. The 10-session merge rule applies to all four definitions.
- _Resolved at build (2026-10-09), G-HASH:_ the four definitions are stored as one dict,
  `EPISODE_DEFS`, in the module. Its sha256 over canonical JSON is `6320a5e3ddc2…` (full value
  in `EPISODE_DEFS_SHA256`). The build reproduces every episode and count in
  [Plan-time observations](#plan-time-observations-disclosed).

### Deployed book

`top_k_per_day(ladder_rank, k=3, A|B)` as `hedge_criteria` builds it, minus any index bear.
Index bears sit on the sleeve side only, so they are never counted twice.

- _Resolved at build (2026-10-09), OD1:_ "the book" being hedged is (a), the deployed A/B top-3
  ladder, because it is what the operator holds.
- _Resolved at build (2026-10-09):_ `hedge_criteria` does not build this book;
  `protocol.top_k_per_day` does. The top three are picked from the whole book, then any index
  bear among them is dropped. No fourth row is promoted into its place.

### Sleeve

Every index bear in the book. Each one's MTM dollars are scaled by `1 / n_indexbear(signal_date)`,
so each signal date carries at most one risk unit. _Resolved at build (2026-10-09), OD2:_ (a),
one risk unit per signal date; (b), recorded size, runs as RB3. The scaling builds one
`book_curves` call per distinct `n` and sums the scaled levels on one session axis.

## Dependencies

- `scripts/backtest_study/lib/book.py::load_book(include_bs=False)`: real rows plus
  `strike_expiry_tweak` rows, with the calibration gate ON.
- `scripts/backtest_study/lib/era.py`: one era per run.
- `lib/mtm_curve.py::book_curves(..., target=TARGET_STORED)` builds the MTM curves, net of
  `cost_total`. `max_drawdown`, `ulcer_index` and `path_stats` come from the same module.
- `lib/hedge_criteria.py`: the `unharmed` rule and `max_drawdown`, imported and never
  re-implemented. Its signal-date bucketing is NOT used; MTM sessions replace it, per
  next-steps §2.10.
- `scripts/backtest_study/f1_selection/benchmark/ticker_class.py`: `group_of` and `direction`,
  imported. The group-table hash is checked at load.
- _Resolved at build (2026-10-09):_ positions are built by `hedge_portfolio.book_positions`, at
  each row's own contract count and stored exit. A row with no `days_held` has no exit window;
  it is left out and counted. `fill_trusted` is not filtered, because the registration names no
  such filter; the count is printed.
- _Resolved at build (2026-10-09), holdout seal:_ the book comes from `load_book` with no
  `sealed_read`, so no signal date from 2026-09-23 on is read. The module repeats the guard on
  the returned rows.

## Population and basis, fixed here

- **Era.** v4 is PRIMARY. v3 is a separately labelled replication; it is not independent (see
  [Plan-time observations](#plan-time-observations-disclosed)). Eras are never pooled.
  _Resolved at build (2026-10-09), OD4:_ both eras are in-sample, so both print a description
  only. v3 runs with `STUDY_ERA=v3`.
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

These counts come from a replica of `load_book`'s row selection that read no outcome column.
They are close to, not identical to, the loader's own census, which the build prints.

**Sleeve shape.**

- Index plays are bear-heavy in calm months too. The v4 index-bear share is ≥ 0.83 in 21 of 33
  months, so the sleeve is close to always on rather than timed.
- Structure, median DTE (≈ 59) and median risk (≈ $1,100) barely differ inside and outside the
  windows.

**What the census means for power.**

1. **The power unit is episodes, and v4 has five.** No magnitude can be estimated from five.
   The strongest in-sample read is a sign: a one-sided sign-test p of 0.031 for 5 of 5
   protected. 4 of 5 gives 0.19. So the book can reach a verdict only if every episode agrees, and
   even then only PROVISIONALLY.
2. **One episode is far larger than the rest.** 2025-02/04 fell 19% with VIX at 52; no other
   reached 11%. Per `lessons.md`, one window can carry a whole effect. So leave-one-episode-out
   is a veto (RB2).
3. **v3 is not an independent replication.** The v4 tab was back-filled over 2024–2026, so both
   eras cover the same four market episodes. The v3 read can show a v4 result does not depend on
   the prompt version's plays. It cannot show the result holds in other markets. Its index bears are also concentrated: 50 of its 56 in-window positions fall in two
   episodes.
4. **Hindsight in the analysis.** An LLM generated both eras, over dates that may fall inside
   its training data. If the index-bear share rises inside episodes, that may be recall rather
   than reading the tape. Forward episodes are the only evidence free of this. This is why the
   in-sample verdict ceiling is PROVISIONAL (see [Forward confirmation](#forward-confirmation)).
5. **Modal expectation, written down now.** UNDERPOWERED or PROTECTS-BUT-COSTS-MORE. The four
   calm months alone carry a large loss, and five episodes are unlikely to agree unanimously.
   An all-NULL result changes nothing about the §4 sleeve.

## What it compares

| Arm | Book | Sleeve | Role |
|---|---|---|---|
| B | deployed book | none | base |
| H | deployed book | index bears, one unit per date | **graded** |
| H-raw | deployed book | index bears at recorded size | printed, never graded (OD2) |
| H-stock | deployed book | stock bears, one unit per date | printed, never graded: is any protection index-specific? |

Exactly one arm is graded. So no configuration is selected from many, and the primary needs no
PBO. A sizing grid (OD3) would be selected from, and CSCV would apply (see
[Overfitting](#overfitting)). _Resolved at build (2026-10-09), OD3:_ (a), no grid. Five episodes
cannot select a size, so no PBO runs.

_Resolved at build (2026-10-09):_ H-stock's "stock bears" are bear positions in the single-stock
groups G5, G6 and G7 of the `ticker_class` table, one unit per signal date.

## How it is judged

### M1, protection per episode

For each episode window, take the worst drawdown within the window on each curve, from the
window's own running high:
`DD_e(X) = min_t (L_X(t) − max_{s∈[peak,t]} L_X(s))`.
Then `ΔDD_e = DD_e(H) − DD_e(B)`, in dollars. A positive value means the sleeve reduced the
drawdown. The study also prints the sleeve's own MTM dollars inside the window (`G_e`).
_Resolved at build (2026-10-09):_ the drawdown is taken on per-session changes from the
window's first session, which equals the level formula for a contiguous window. `G_e` is the
sleeve's level change across the window.

### M2, carry outside episodes

The sum of the sleeve's MTM dollars over the outside sessions (`C`), and the same figure per 100
outside sessions. Buffer sessions print separately and count on neither side.
_Resolved at build (2026-10-09):_ a session the SPY file cannot label is "unclassified" and
counts on neither side. That covers sessions before the drawdown is defined, after the file
ends, and after the peak of an episode the data has not closed.

### M3, net

- `NET = ΣG_e + C + buffer`, which equals the sleeve's total MTM dollars over the span.
- The full-span drawdown of H against B uses `hedge_criteria.unharmed` on MTM maxDD and the
  worst day.
- **Break-even frequency** `f* = −(C per outside session) / mean(G_e)`, in episodes per 252
  sessions. It is set beside the observed E-DD5 rate in the SPY/VIX file (6 episodes in about
  3.3 years). It is meaningful only when `mean(G_e) > 0`; otherwise it prints "no break-even".
- _Resolved at build (2026-10-09), OD5:_ yes, base rate only. The 2023 episode is out of scope
  for every read. `--fetch-base-rate` writes a longer SPY history to
  `backtests/mech_regime/spy_base_rate_daily.csv`. Its E-DD5 rate prints beside the file rate as
  a declared secondary. The file rate stays the headline. Neither touches an outcome.
- _Resolved at build (2026-10-09):_ NET is printed as windows + C + buffer + unclassified, so
  the four parts add to the sleeve's total over the span.

### Diagnostics, printed and never graded

- the MTM Ulcer index of B and H;
- `corr(S, B)` on sessions outside episodes, since a positive value means re-wrap
  (`lessons.md`);
- M1–M3 under each secondary definition.

### Power floor

- An episode is **evaluable** when it has ≥ 3 sleeve positions open into the window, passes
  G-OPEN, and has ≥ 5 sessions.
- The primary verdict needs **≥ 5 evaluable E-DD5 episodes** in the era. Below that, the verdict
  is UNDERPOWERED.
- The floor counts episodes, not positions. It may not be met by loosening the definition or by
  pooling eras. v4 has exactly 5 candidates, so one non-evaluable episode makes it UNDERPOWERED.
- _Resolved at build (2026-10-09), OD4:_ (b), grade forward only. The floor of 5 counts forward
  episodes, those with a peak after 2026-10-09. The in-sample episodes print as a description
  with their full criterion vector and no verdict word. Below the floor the forward verdict
  reads STILL-OPEN until the sunset and UNDERPOWERED after it.

## Gates

A failed gate refuses the run (non-zero exit). It does not produce a verdict.

- **G-ERA.** One era, named in the header; `era.py` refuses a mismatch.
- **G-MTM.** The `book_curves` G-MTM reconciliation passes at the shipped tolerance, never
  widened.
- **G-HASH.** The episode-definition hash and the GT3 group-table hash match the values recorded
  at acceptance.
- **G-CENSUS.** The episode and position census prints before any outcome column is read.
- **G-OPEN.** ≤ 25% of the sleeve's in-window positions are still open at `path_data_end`, per
  episode. A failing episode is NOT EVALUABLE.
  _Resolved at build (2026-10-09), OD7:_ OD7 asked if 25% suits 2026-01/03, with DTE ≈ 59 and
  data running to 2026-09. Keep 25%. "In-window positions" are the sleeve
  positions open into the window by scheduled span. "Still open" means the row's `path_status`
  is `open_at_data_end`. Both are descriptors, so G-OPEN is settled in the census.

_Resolved at build (2026-10-09):_ G-MTM fails with exit 4 and G-HASH with exit 5. Both are
failures, not designed refusals.

## Overfitting

### Permutation read (calendar shift)

- The statistic is `T = Σ_e ΔDD_e`.
- The null shifts the whole set of episode windows circularly across the era's session span.
- Lengths and gaps are kept, every shift moves at least 21 sessions, and all shifts are
  enumerated.
- The windows are re-evaluated on the same curves. The one-sided p-value is the rank of the
  true T.

Shifted windows can overlap real episodes, which makes the test conservative. (Adapted
from the circular-shift test in `ticker_class_regime`.)

_Resolved at build (2026-10-09), permutation:_ T sums over evaluable episodes only. The span is
the session axis of the read. A window that wraps past the end continues from the start.
`p = (1 + #{T_k ≥ T}) / (1 + number of shifts)`.

### Robustness battery, veto only

A check can block a protective verdict. None can create one.

- **RB1:** primary on E-DD8 and E-20D5 keeps the sign of `ΣΔDD_e`.
- **RB2:** leave-one-episode-out keeps the sign of `ΣΔDD_e` and of NET for every left-out
  episode. _Resolved at build (2026-10-09):_ NET without an episode is NET minus that episode's
  `G_e`.
- **RB3:** H-raw keeps the sign of `ΣΔDD_e`.
- **RB4:** real-priced rows only (no tweak rows) keep the sign, when ≥ 3 episodes are still
  evaluable. _Resolved at build (2026-10-09):_ the filter applies to the book and the sleeve
  alike, and evaluability is recounted on the filtered sleeve.
- **RB5:** H-stock does not protect at least as well. If it does, the verdict is re-worded
  "bear protection, not index-specific".

### PBO/CSCV

PBO/CSCV applies only if OD3 adds a sizing grid. The blocks would be episodes plus the
inter-episode stretches between them. A PBO above 0.50 vetoes any recommended size.
_Resolved at build (2026-10-09), OD3:_ no grid, so no PBO runs.

## Possible verdicts

### Verdicts, worded now

The verdicts are checked in order, and the first match wins. n is the number of evaluable E-DD5
episodes.

| Verdict | Condition |
|---|---|
| UNDERPOWERED | n < 5. This is not a lean, and no direction is quoted. |
| EARNS ITS KEEP (PROVISIONAL) | `ΔDD_e > 0` in all n episodes; permutation p ≤ 0.05; NET > 0; H is `unharmed` against B on full-span MTM; RB1–RB4 hold |
| PROTECTS, COSTS MORE THAN IT SAVES | `ΔDD_e > 0` in ≥ n − 1 episodes, and NET ≤ 0. Prints `f*` against the observed rate. Read as: real insurance, priced too high at this sample's episode frequency. |
| DOES NOT PROTECT | `ΔDD_e ≤ 0` in ≥ 2 episodes, or median `ΔDD_e ≤ 0` |
| INDETERMINATE | anything else; prints the criterion vector (n, signs, p, NET, unharmed, RB flags) |

- If RB5 fires, the first two verdicts gain the suffix "— bear protection, not
  index-specific".
- **v3 replication.** The same rule runs on v3, labelled "same-episode replication". It can
  contradict v4 and block "EARNS ITS KEEP". It can never upgrade v4 on its own.

_Resolved at build (2026-10-09), OD4:_ this table grades forward episodes only, with n the number
of evaluable forward episodes. Forward episodes are free of the hindsight risk in observation 4, so the first verdict drops "(PROVISIONAL)" and reads EARNS ITS KEEP. Below the floor the first
row reads STILL-OPEN before the sunset and UNDERPOWERED after it. On the in-sample episodes the
study prints the criterion vector and no verdict word, on either era.

### Forward confirmation

- **What is graded.** Every E-DD5 episode whose peak falls after the acceptance date is graded
  once its buffer closes (trough + 10 sessions), on the then-current era. The study appends a
  line to `research/study-results/f5_hedging/`.
- **Confirmation.** A PROVISIONAL verdict becomes CONFIRMED after ≥ 2 forward episodes, all
  with `ΔDD_e > 0`, and forward carry per outside session no worse than `f*` implies at the
  observed rate.
- **Disconfirmation.** Any forward episode with `ΔDD_e ≤ 0` sends it back to INDETERMINATE.
- **Sunset.** 3 years from acceptance. At roughly 1.8 episodes a year, two episodes take about
  1–2 years.

_Resolved at build (2026-10-09), OD4:_ with no in-sample verdict there is nothing PROVISIONAL to
confirm. The two clauses above also disagree on how many forward episodes a result needs. The
choice is contested, so both print as declared lines:

| Line | Floor | Rule | Role |
|---|---|---|---|
| `FORWARD VERDICT` | 5 forward episodes | the [verdict table](#verdicts-worded-now) on forward episodes | headline, fixed now |
| `FORWARD EARLY READ` | 2 forward episodes | the confirmation and disconfirmation clauses above | declared secondary; never a verdict |

- The early read prints PROTECTING when every forward `ΔDD_e > 0` and forward carry per outside
  session is no worse than the break-even carry. That carry is the observed file rate per
  session times the in-sample mean `G_e`, negated.
- Any forward `ΔDD_e ≤ 0` prints the token `NOT PROTECTING`. Otherwise it prints `STILL-OPEN`.
- The sunset is 2029-10-09.

_Resolved at build (2026-10-09), holdout seal:_ this registration was accepted on 2026-10-09, so
it cannot join `era.SEALED_READERS`. Its forward window reads nothing until `era.SEAL_LIFTED` is
set. Until then both lines print STILL-OPEN with zero episodes graded. The SPY file is market
data and is read in full; the episode census is never scored against a play.

## Anti-tuning

- Every default was fixed before any outcome column was read.
- The episode definitions were fixed on 2026-10-07 before any count was taken. G-HASH pins them.
- Exactly one arm is graded; there is no sizing grid.
- A revisit after a result is a NEW registration, never an edit.

All seven open decisions, OD1–OD7, were resolved at build on 2026-10-09. Each answer sits
beside the text it amends.

## What could ship

Nothing ships from this study.

- **EARNS ITS KEEP (CONFIRMED)** files an entry in `research/deployment-evidence.md` under "to
  be tested": index bear spreads as the §4 sleeve's preferred vehicle.
- **PROTECTS, COSTS MORE** files `f*` as the price of the insurance.
- **No verdict removes the §4 sleeve.**
