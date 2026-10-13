## earnings_vol — does a long straddle or a calendar across earnings pay, without re-wrapping the book?

_Registered 2026-10-12, before the study's first run and before its fetch._

**STATUS: ACCEPTED BY DEFAULT 2026-10-12 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Contested choices are parameters printed both
ways; only the defaults below carry a verdict.

**What this file says, in one paragraph.** The ladder is a direction bet, and
nothing at entry predicts direction. Earnings are the one scheduled event
where a single name's move is large and its timing known, so a
non-directional position can be placed on a calendar that never reads the
engine's signal dates. This study buys two structures five sessions before
each report on a fixed list of 25 liquid names and sells them the session
after: an ATM straddle, and an ATM calendar whose short leg expires just
after the report. It grades each on its mean return with CIs clustered by
earnings season, and it gates each on the correlation of its daily P&L with
the deployed book's.

## The motivating hint is post hoc

`vol_sleeve` (2026-08-12, archive/12 §4) found calendars with earnings inside
their DTE at +0.356 mean R against −0.035 without (difference CI
[+0.111, +0.664], n=42). That cut was found after the fact, inside a pooled
gate that failed, on the engine's own signal dates. Its one replication
attempt (archive/13) did not replicate (n=14, difference CI [−0.585, +0.382]).
It motivates this study. It is not evidence for it, and nothing here reads
those rows.

## Question

Across 11 earnings seasons on a fixed list of 25 names, does a long ATM
straddle or a long ATM calendar, entered 5 sessions before the report and
closed the session after, earn a positive mean return whose daily P&L does not
move with the deployed book?

## What this is NOT

- **Not the book's picks.** The names are fixed below, before any result, and
  the entry dates come from an earnings calendar. No signal date, play, or
  analysis row is read to choose a trade.
- **Not `vol_sleeve` again.** That sleeve was built on the engine's dates and
  re-wrapped the book. Lesson: a synthetic built on the engine's own dates
  re-wraps exposure already deployed. The correlation gate below exists for
  this.
- **Not a pre-announcement run-up trade.** Both structures are held through
  the report. A run-up-only exit (close the day before) is printed, not graded.
- **Nothing ships.** An `EDGE` token earns a sizing registration and a
  forward read, not a deployment.

## Literature, verified 2026-10-12

| Paper | What it found | Use here |
|---|---|---|
| Patell & Wolfson (1979), *J. Accounting & Economics* 1(2) 117–140 | Implied variance rises before an earnings release and falls after it | The run-up and the crush both exist |
| Dubinsky, Johannes, Kaeck & Seeger (2019), *RFS* 32(2) 646–687 | Anticipated earnings-day jump risk is large, time-varying and priced into the term structure | Why the front expiry carries the event premium, which the calendar sells |
| Gao, Xing & Zhang (2018), *JFQA* 53(6) 2587–2617 | ATM straddles bought about 3 days before the announcement and held through it earned about 3.34% on average; larger for small, volatile, illiquid firms | The long straddle's prior is positive, weakest on large liquid names like these |
| Goyal & Saretto (2009), *J. Financial Economics* 94(2) 310–326 | Straddles sorted on historical minus implied vol earn a significant long-short return | Context: the cross-section, not an event trade |

Gao, Xing & Zhang's effect is concentrated in the names this list excludes.
A `NULL` on 25 mega-caps would not contradict them.

## Universe, fixed now

25 US single stocks. The list is a judgment list fixed before any result: the
20 names agent-trading's earnings calendar already covers, chosen there for
option liquidity and independently of this book, minus BRK.B (thin options,
Saturday reports), plus six names among the most traded single-stock options
in 2023–2025.

| Group | Names |
|---|---|
| agent-trading list (19) | AAPL AMD AMZN ASML AVGO COST GOOGL INTC JPM LLY META MSFT MU NFLX NVDA QCOM TSLA TSM UNH |
| Added (6) | BA BAC COIN DIS PLTR UBER |

The list was not drawn from a published volume ranking; none was found that
could be verified on 2026-10-12. The disclosure stands in for one.

## Events

- **Calendar.** agent-trading's `data/earnings/<SYM>.csv` (Yahoo via
  `yfinance`), fetched for the six added names with the same tool. Columns
  used: `ann_date`, `session` (bmo, amc, dmh, unknown).
- **Seasons.** 11 calendar quarters of reports, 2024-Q1 through 2026-Q3 (the
  report dates 2024-01-01 → 2026-09-30). Each quarter is one season. These are
  the seasons the v4 book's daily MTM covers, which the gate needs.
- **Event session E.** The first session whose open reflects the report: the
  report date for `bmo`, the next session for `amc` and `dmh`. An `unknown`
  session is dropped and counted (printed beside it: treated as `amc`).
- **Entry.** The close of session E − 5. **Exit.** The close of session E,
  which is the session after the report. **Run-up exit, printed.** The close
  of session E − 1.
- **Seal.** An event with E on or after `era.SEAL_START` is forward and
  prints `STILL-OPEN`; it never enters the in-sample verdict.

## Structures

- **ATM strike.** The listed strike nearest the underlying's close at entry,
  ties to the lower strike, from the entry day's rows only.
- **Front expiry.** The first listed expiry dated after session E.
- **Back expiry.** The first listed expiry at least 28 calendar days after the
  front expiry.

| Arm | Legs |
|---|---|
| S — long straddle | buy call + put, ATM, front expiry |
| K — long calendar | sell front ATM call, buy back ATM call; and the same in puts (a double calendar, delta-neutral at entry) |

One unit per event. Return = P&L / entry debit. An event with any leg missing
on the entry or exit day is dropped and counted.

_Resolved at build (2026-10-12):_
- The entry close is put on the option chain's unadjusted basis. Stock bars
  are split-adjusted and strikes are not, so each of the five sessions up to
  entry votes a factor (median `Price~` over the adjusted close, snapped to 1
  or a split ratio within 5%). A rebased event counts `close_rebased`: 12
  events, on NFLX, NVDA and AVGO. A split-adjusted ticker with no `Price~` near
  entry drops as `no_unadjusted_close`.
- Candidate strikes are the multiples of 0.5, 1, 2.5, 5 and 10 nearest the
  close on each side, within 3%, ranked by distance (ties lower). ATM is the
  nearest candidate whose front call and put both have an entry-day row. A
  candidate with a failed, unlisted or unquoted leg is passed over. An
  unfetched one drops the event (`front_not_fetched`), and an event whose every
  candidate is passed over drops as `front_no_candidate`. A manifest `failed`
  contract counts as unlisted.
- The fetch probes candidates nearest first in front passes until none is
  pending, then fetches back legs at the confirmed ATM only. This replaces the
  first fetch's two bracketing strikes at an inferred step, which planned
  strikes from split-adjusted closes and a sparse cache. No outcome was read
  before the change.
- An `_unlisted.jsonl` key counts as unlisted whatever its age.
- Drops are per arm: a missing back leg drops ARM K only. A back file whose
  first row is after entry prints as `back_not_quoted_at_entry`.
- Return = net P&L / (entry debit × 100). Commission is in the P&L, charged on
  every leg at entry and at exit. Daily marks are at mid; the exit is at the
  fill's own basis. A natural close sells a long leg at the bid (0 with no
  bid) and buys back a short leg at the ask.
- MFE and MAE run over the marks from entry to exit inclusive. A missing row
  before the exit carries the last mid and is counted.
- A debit ≤ 0 at a fill's own basis refuses that fill's trade
  (`calendar_credit` for K, `no_debit` for S).

## Fills and costs

- **Default: mid**, plus $0.65 per contract per side. The operator fills
  spreads at mid (`operator_fills_spreads_at_mid`, 2026-09-24).
- **Printed beside it: natural** (bought legs at the ask, sold at the bid). A
  sold leg with no bid fills at 0, as production does.
- **Junk quote.** A leg wider than twice the Cboe maximum width falls back to
  `Latest` and is counted, using `scripts/backtest`'s shared function.
- A calendar priced to a credit at entry is refused and counted, as production
  refuses a debit priced to a credit.

## Measures

- **M1, per arm.** Mean return, median, win rate, profit factor, and MFE and
  MAE as a share of debit from the daily marks between entry and exit.
- **CI.** A cluster bootstrap over the 11 seasons: resample whole seasons with
  replacement, 10,000 draws, seed 20261012. With 11 clusters the CI is wide,
  and the report prints the cluster count beside it.
- **Halves.** Seasons 2024-Q1 → 2025-Q2 (6) and 2025-Q3 → 2026-Q3 (5); means
  printed per half.
- **Leave-one-season-out.** The mean with each season removed; its minimum is
  printed.

  _Resolved at build (2026-10-12):_ a season is the calendar quarter of the
  report date, not of E. The cluster CI is the pooled event mean over the
  resampled seasons. Profit factor is in dollars.
- **Per name.** Mean and n, printed; no per-name verdict.

## The gate — correlation with the book

- **G1.** The sleeve's daily mark-to-market P&L (all open events summed, one
  unit each) against the deployed book's daily MTM change, over the sessions
  where at least one event is open and the book has a session.
- **Book.** As in `index_vrp`: `account_sim`'s registered cell, `simulate()`,
  `mtm_curve.book_curves(..., target=TARGET_POSITION)`, era v4 via
  `load_book()` with the seal applied.
- **CI.** Stationary block bootstrap over sessions
  (`ruin_walk.stationary_indices`), mean block 10, 10,000 paths, seed
  20261012.
- **Pass** when the correlation's point is ≤ 0, the anti-re-wrap bar
  `financed_spread` E3 uses. **Printed beside it:** pass at ≤ 0.10.
- **Also printed.** The sleeve's mean daily P&L on the book's worst 5% of
  sessions, with the same CI.

  _Resolved at build (2026-10-12):_ an event is open on sessions entry ≤ d ≤
  exit. A G1 with fewer than 3 common sessions is `NOT EVALUABLE` and the
  token is `NULL`. Each secondary recomputes G1 on its own sleeve; the
  unknown-as-amc secondary pools the in-sample events with the unknown events
  planned as amc.

## Verdicts, worded now

Per arm, at mid fill, on in-sample events.

| Token | When |
|---|---|
| `EDGE` | Season-clustered CI95 lower bound > 0, both halves' means > 0, and G1 passes |
| `RE-WRAP` | The CI and halves clauses hold, and G1 fails |
| `CONTRARY` | CI95 upper bound < 0 |
| `NULL` | Anything else |

The natural fill, the `unknown`-as-`amc` events, the run-up exit and the
0.10 gate print their own tokens, labelled secondary.

## Overfitting

Two arms, fixed now, are graded, so nothing is picked from a grid. The
printed variants form a grid of 2 arms × 2 fills × 2 exits = 8 configs. Their
PBO is printed from `lib/pbo.py::cscv` on the per-season return matrix, padded
or trimmed to S = 10 rows as `cscv` requires, labelled context. Any later
registration that picks one variant owes that read as its own gate.

_Resolved at build (2026-10-12):_ PBO rows are the 11 registered seasons;
each cell is that season's mean return, 0 when the config kept no event. Rows
are trimmed from the head (2024-Q1) to 10, or zero-padded at the head.
Sealed events are listed, not priced, and print `STILL-OPEN`.

## The fetch

- Contracts not in `backtests/option_history_cache/` are fetched from Barchart
  once: per event, the two listed strikes bracketing the entry close, call and
  put, front and back expiry (8 contracts), less what is cached.
  _Resolved at build (2026-10-12): replaced by the candidate walk under
  Structures; the operator approved the second fetch it needs._
- The planner prints its contract count in a dry run first. The operator
  approves the fetch before it runs.
- The run keeps `caffeinate` on, and `scripts/backup_research_caches.py push`
  runs after it.
- A contract Barchart does not list goes to `_unlisted.jsonl` and its event is
  dropped and counted.

## No-lookahead rules, tested

- The ATM strike and both expiries come from data on or before the entry day.
- Event dates come from the calendar file. The study treats a report date as
  known five sessions ahead; a moved report is a risk the data cannot
  show, and the report says so.
- The book's MTM and the sleeve's marks are aligned by session; no sleeve
  mark uses a later day's row.
- Seasons, halves and the PBO matrix are fixed by report date, never by
  outcome.

## Output

`backtests/study_output/earnings_vol-latest.txt`, a per-event CSV
`earnings_vol-latest.csv`, and the study-results record. The header names the
era, the registration, the seed, the seal line and the fetch manifest's
timestamp.
