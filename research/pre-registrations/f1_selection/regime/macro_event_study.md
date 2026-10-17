## macro_event_study — do scheduled macro events show up in this book?

<!-- outcome:start -->
> Latest outcome: no PRIMARY v3 verdict is recorded. On v4, which is not PRIMARY: `X-C1` `SURVIVAL-ARTIFACT`, and the exit thread is `DE-QUEUED` — 2026-09-28 · [record](../../../study-results/f1_selection/regime/macro_event_study.md).
<!-- outcome:end -->

_Registered 2026-08-19._

## The question

Do scheduled US macro events — FOMC decisions, FOMC minutes, CPI, NFP, PCE —
show up in this book?

- in the IV the plays are entered at (ARM I),
- in what they earn (ARM P),
- or in when they exit (ARM X)?

Plus market-level context (ARM V).

## What this study is not

- **Not a source of any shipped change.** See "What could ship".
- **Not an exit study.** No exit variant is replayed here. ARM X is census only.
- **Not a read of the book's single-name IV by ARM V.** ARM V shows index vol and is CONTEXT ONLY.
- **Not a read of `n_*_in_dte`.** It is PRE-DECLARED NON-READABLE, reported as census only.

## Population and basis, fixed here

The calendar, the loader, the distance convention and the era are all fixed
before any number is read.

- **Calendar.** `config/macro-events.yml`, hand-authored from the official Fed /
  BLS / BEA schedules cited in its `meta.sources`. Five types
  (`fomc, fomc_minutes, cpi, nfp, pce`), 2023-06-01 onward, per-type
  `verified_through`.
- **Loader.** `scripts/backtest_study/lib/macro_calendar.py`.
  - `next_event` is strictly after `as_of`. `last_event` is on or before it.
  - `count_between` is start-exclusive and end-inclusive.
  - Past `verified_through` the loader returns `None`.
  - `unscheduled` events are excluded from forward-looking features only.
- **Event distance is measured from the ENTRY SESSION (`t.grid[0]`), not the
  signal date.** The entry basis is the next session's open, so every event on
  the signal date is already in the entry price. On the entry session itself,
  `pre_open` (release before 09:30 ET) decides whether the position is in front
  of the event. 08:30 CPI/NFP/PCE are in the entry price. 14:00 FOMC statements
  and minutes are not, so a day-0 14:00 event counts as AHEAD of the position.
- **Population.** Pooled real+tweak via `load_book` (bs excluded, proxy
  calibration gate ON), **era `v3`**: the 118-date 2024-06-17..2026-04-07 book.
  The bare `current` exports hold ~34 dates and are NOT the population. The
  evidence run is `--era v3`, and the report header must name it.
- **Known limitation, disclosed.** The calendar records the schedule as
  published at compile time (`meta.compiled`). A date announced after the fact
  would be a look-ahead the file cannot detect. Proximity windows are CALENDAR
  days.

## Plan-time observations, disclosed

Before this registration was written, a read-only count was run against the v3
exports using RECALLED FOMC dates and a first-Friday NFP proxy. It found:

- 1,088 of 1,118 pooled rows have an FOMC decision inside `min(dte, 120)`;
- book dates within ±1 / ±3 / ±5 calendar days of an FOMC decision were
  16 / 24 / 32 of 118.

Those are scoping numbers, not results. Two commitments follow from having seen
them, and both are made here rather than after the run:

1. `n_*_in_dte` (event inside the DTE window) is PRE-DECLARED NON-READABLE. It
   is a near constant on this book (median dte_entry 70d vs an FOMC every ~6
   weeks). The realized-hold variant is endogenous: a fast profit-target exit
   is why some holds contain no event. Both are reported as census only. The
   discriminating ex-ante feature is ENTRY PROXIMITY.
2. `MIN_EVENT_DATES = 25` is `selection_order.MIN_AFFECTED_DATES`, the repo's
   standing date-level floor. It is NOT a number chosen against the counts
   above. On those counts the FOMC ±1 and ±3 cells are EXPECTED to be
   power-stopped. That expectation is recorded here so a stop cannot later be
   read as a surprise, and the floor cannot be lowered to clear it.

## What it compares

The study runs four arms, one per hypothesis: H1, H2, H3, H4.

| Arm | Hypothesis | What it does | Kind |
|---|---|---|---|
| ARM I | H1 | Entry `vrp` before and after events, against control sessions | PRIMARY |
| ARM P | H2 | Mean R and E by entry-proximity bucket per type, within structure | arm |
| ARM V (with V-price) | H3 | VIX and SPY by event-relative day t−5..t+5 | CONTEXT ONLY |
| ARM X | H4 | `exit_reason` mix and R, by whether the hold spans an event | DESCRIPTIVE, no verdict |

### H1 — the IV arm (PRIMARY, ARM I)

The hypothesis: entry `vrp` is higher on entry sessions within k days BEFORE an
event than on control sessions (no event of that type within ±5), and lower
within k days AFTER (run-up / crush).

- Primary metric: `vrp`, because it nets out the underlying's realized-vol
  level.
- Secondary metrics: ticker-demeaned `iv_entry` (demeaned against that ticker's
  book median, tickers with ≥5 appearances only), `iv_spread`, `iv_pct`.
- Every headline is re-cut within `mech_vol`. Macro events cluster with vol
  regime, so a separation that lives only in the E-VOL cell is a regime read,
  not an event read.

### H2 — the outcome arm (ARM P)

Mean R and E by entry-proximity bucket per type, date-clustered, and WITHIN
STRUCTURE from the first look. This is the standing rule, because
`cpir`/`oi_confirm_pct`/`iv_pct` all looked predictive pooled and vanished
within structure. A pooled cross-structure table may print but carries no
conclusion.

### H3 — the market-context arm (ARM V)

VIX level and 1-day change by event-relative day t−5..t+5, over EVERY session in
the book span (~500 sessions from
`backtests/mech_regime/spy_vix_daily_full.csv`). This is index vol, not the
book's single-name IV: CONTEXT ONLY. No verdict may rest on it.

**ARM V-price (H3 extension, CONTEXT ONLY — same standing as the VIX table: no
verdict may rest on it).** It reads the same `spy_vix_daily_full.csv` series and
the SAME event anchors as the VIX table (session 0 = the session the release
lands on or first after). It prints two things:

- per event-relative session t−5..t+5, mean SPY close-to-close return (%) with
  the same by-event bootstrap CI;
- per type, two pre-declared cumulative windows: PRE drift t−3→t0 close and
  POST drift t0→t+3 close (the pre-FOMC-drift literature window; three sessions
  either side, fixed here before computing).

ARM V-price adds no book join, no new proximity windows, and no change to any
gate, floor, or readable cell. The five event types and the t−5..t+5 range are
unchanged.

### H4 — the exit arm (ARM X, DESCRIPTIVE, no verdict)

`exit_reason` mix and R for rows whose realized hold spans an event vs not, plus
exit position relative to the nearest event. It is ENDOGENOUS by construction,
so it is census only. Its sole output is the pre-declared TRIGGER below.

## How it is judged

- **Metric.** Per arm, as set out under each arm above. Gates G2 to G4 set the CI, units and R-only rules.
- **Day-0 assignment.** A `pre_open` day-0 event buckets as "after" (the print
  is in the entry fill). A post-open day-0 event buckets as "before" (the
  position sits in front of it).
- **Proximity windows.** `{0, ±1, ±2, ±3, ±5}` calendar days. The control cell
  is "no event of that type within ±5".

## Gates

Each gate exits non-zero on failure.

- **G0 POWER + COVERAGE, runs FIRST and blocks every read.** It refuses (exit 4)
  if the calendar does not span the book's `date_range` for every type. It
  prints per (type, window) affected DATES and rows. A cell under
  `MIN_EVENT_DATES = 25` affected dates prints its n and is NOT READ: no mean,
  no CI, no verdict.
- **G1.** Coverage before numbers: `UF.coverage()` (OHLC-only denominator for
  `vrp`), real/tweak source split, `diag["debit_calib"]`, ticker-demean
  eligibility counts.
- **G2.** Every mean carries a date-clustered CI (`protocol.boot_ci_by_date`).
  Every headline is re-cut by `protocol.window_cuts` AND by a hand ex-BOTH cut
  of the two dominant windows (`window_cuts` drops one at a time). Every
  headline is year-split (`protocol.by_year` / sign stability) and split real
  vs tweak.
- **G3.** Units: `iv_entry_pct` is a DECIMAL FRACTION (0.3295 = 33% IV); no
  conversion anywhere; the report prints a one-line units note.
- **G4.** No annualised figure, no Sharpe, no time-to-recover. R, never $, on
  any comparison that changes composition.

## Verdicts, worded now

A study may earn one verdict per arm (e.g. ARM I REGIME-PROXY + ARM P
POWER-STOPPED). The catalog verdict summarises them without averaging.

| Token | When |
|---|---|
| `EVENT-PRICES-IV` | H1 clears its floor, holds sign in both window cuts and in every year, and survives the `mech_vol` re-cut. A characterisation of the book, not a rule. Queues an independent-window confirmation; ships nothing |
| `REGIME-PROXY` | H1's separation is absorbed by the `mech_vol` re-cut |
| `POWER-STOPPED` | Every cell of an arm falls under `MIN_EVENT_DATES`. Census only; nothing read, nothing refuted, no verdict drawn from that arm |
| `NULL` | Cells are powered and no arm separates. The macro-event layer is CLOSED for this book and the live pipeline never pays the version bump |

### EXIT-TRIGGER (H4, conditional)

ARM X's raw monotone-R-in-event-position read has an obvious artifact
mechanism. A hold only CONTAINS a late event if the position already survived
that long, so event position is mechanically coupled to hold length. The
trigger is therefore read only under a survival control, fixed here:

- **X-C1 (long-hold subset).** Rows whose realized hold spans >=1 event AND
  `days_held >= 20` sessions (one trading month — long enough that
  EARLY/MID/LATE, the first-event-position tercile, are all mechanically
  reachable inside the hold; the boundary does not move once chosen). Within
  that subset, recompute the EARLY/MID/LATE mean-R table.
- **X-C2 (within hold-length terciles).** Split spanning rows by `days_held`
  terciles (boundaries computed on the spanning population, disclosed
  in-sample). Print the 3x3 position-by-length census.

The three readings of that control, worded now:

| Token | When |
|---|---|
| **TRIGGER STANDS** | X-C1 is monotone in the same direction with >= `MIN_EVENT_DATES` (25) affected dates. A SEPARATE study `macro_event_exit` (f2_management) is queued with its own pre-registration. No exit variant is replayed in THIS study |
| **SURVIVAL-ARTIFACT** | X-C1 is non-monotone, or flat within every X-C2 length tercile. The trigger is reclassified as an artifact of hold length, and `macro_event_exit` is NOT queued. It re-arms only if a future run fires the CONTROLLED trigger (X-C1), never the raw one |
| **POWER-STOPPED** | X-C1 has < 25 affected dates. The control is unreadable, the follow-up stays queued but BLOCKED on data, and no exit study may be built until the controlled read exists |

Everything stays census-labelled. No gate, floor, window, or readable cell of
ARMs I/P/V changes.

## Anti-tuning

- Proximity windows are `{0, ±1, ±2, ±3, ±5}` calendar days, and the control
  cell is "no event of that type within ±5". Neither set may grow after any
  result is seen.
- Event types are the five named here. None may be added or dropped.
- `MIN_EVENT_DATES = 25` is not lowered to clear a power stop.

## What could ship

RESEARCH ONLY. **Nothing ships from this study under any outcome.**
Feeding an event feature to the analysis prompt is an INPUT change and
therefore a v5 version bump with new tabs. That change is explicitly deferred,
and no result here may authorise it. No pipeline column, no BaselineDaily
change, no prompt change, no harness edit.
