# macro_event_study — pre-registration

## 2026-08-19 — `macro_event_study`: PRE-REGISTRATION (written BEFORE the study was built or run)

**Question.** Do scheduled US macro events — FOMC decisions, FOMC minutes, CPI,
NFP, PCE — show up in this book: in the IV the plays are entered at (ARM I), in
what they earn (ARM P), or in when they exit (ARM X)? Plus market-level context
(ARM V). RESEARCH ONLY. **Nothing ships from this study under any outcome.**
Feeding an event feature to the analysis prompt is an INPUT change and
therefore a v5 version bump with new tabs; that is explicitly deferred and no
result here may authorise it. No pipeline column, no BaselineDaily change, no
prompt change, no harness edit.

**Data, fixed here.**
- Calendar: `config/macro-events.yml`, hand-authored from the official Fed /
  BLS / BEA schedules cited in its `meta.sources`. Five types
  (`fomc, fomc_minutes, cpi, nfp, pce`), 2023-06-01 onward, per-type
  `verified_through`.
- Loader: `scripts/backtest_study/lib/macro_calendar.py`. `next_event`
  strictly after `as_of`, `last_event` on or before, `count_between`
  start-exclusive / end-inclusive, `None` past `verified_through`,
  `unscheduled` events excluded from forward-looking features only.
- **Event distance is measured from the ENTRY SESSION (`t.grid[0]`), not the
  signal date** — the entry basis is the next session's open, so every event
  on the signal date is already in the entry price. On the entry session
  itself, `pre_open` (release before 09:30 ET) decides whether the position is
  in front of the event: 08:30 CPI/NFP/PCE are in the entry price; 14:00 FOMC
  statements and minutes are not, so a day-0 14:00 event counts as AHEAD of
  the position.
- Population: pooled real+tweak via `load_book` (bs excluded, proxy
  calibration gate ON), **era `v3`** — the 118-date 2024-06-17..2026-04-07
  book. The bare `current` exports hold ~34 dates and are NOT the population;
  the evidence run is `--era v3` and the report header must name it.
- Known limitation, disclosed: the calendar records the schedule as published
  at compile time (`meta.compiled`). A date announced after the fact would be
  a look-ahead the file cannot detect. Proximity windows are CALENDAR days.

**Scoping estimate, DISCLOSED.** Before this registration was written, a
read-only count was run against the v3 exports using RECALLED FOMC dates and a
first-Friday NFP proxy. It found: 1,088 of 1,118 pooled rows have an FOMC
decision inside `min(dte, 120)`; book dates within ±1 / ±3 / ±5 calendar days
of an FOMC decision were 16 / 24 / 32 of 118. Those are scoping numbers, not
results. Two commitments follow from having seen them, and both are made here
rather than after the run:

1. `n_*_in_dte` (event inside the DTE window) is PRE-DECLARED NON-READABLE —
   it is a near constant on this book (median dte_entry 70d vs an FOMC every
   ~6 weeks), and the realized-hold variant is endogenous (a fast
   profit-target exit is why some holds contain no event). Both are reported
   as census only. The discriminating ex-ante feature is ENTRY PROXIMITY.
2. `MIN_EVENT_DATES = 25` is `selection_order.MIN_AFFECTED_DATES`, the
   repo's standing date-level floor — NOT a number chosen against the counts
   above. On those counts the FOMC ±1 and ±3 cells are EXPECTED to be
   power-stopped, and that expectation is recorded here so a stop cannot later
   be read as a surprise, or the floor be lowered to clear it.

**Hypotheses.**
- **H1 (PRIMARY — IV, ARM I).** Entry `vrp` is higher on entry sessions within
  k days BEFORE an event than on control sessions (no event of that type
  within ±5), and lower within k days AFTER (run-up / crush). Primary metric
  `vrp` (it nets out the underlying's realized-vol level); secondary:
  ticker-demeaned `iv_entry` (demeaned against that ticker's book median,
  tickers with ≥5 appearances only), `iv_spread`, `iv_pct`. Every headline is
  re-cut within `mech_vol` — macro events cluster with vol regime, and a
  separation that lives only in the E-VOL cell is a regime read, not an event
  read.
- **H2 (outcomes, ARM P).** Mean R and E by entry-proximity bucket per type,
  date-clustered, WITHIN STRUCTURE from the first look (the standing rule:
  `cpir`/`oi_confirm_pct`/`iv_pct` all looked predictive pooled and vanished
  within structure). A pooled cross-structure table may print but carries no
  conclusion.
- **H3 (market context, ARM V).** VIX level and 1-day change by event-relative
  day t−5..t+5 over EVERY session in the book span (~500 sessions from
  `backtests/mech_regime/spy_vix_daily_full.csv`). Index vol, not the book's
  single-name IV: CONTEXT ONLY. No verdict may rest on it.
- **H4 (exit, ARM X — DESCRIPTIVE, no verdict).** `exit_reason` mix and R for
  rows whose realized hold spans an event vs not, and exit position relative
  to the nearest event. ENDOGENOUS by construction; census only. Its sole
  output is the pre-declared TRIGGER below.

**Gates (non-zero exit on failure).**
- **G0 POWER + COVERAGE, runs FIRST and blocks every read.** Refuses (exit 4)
  if the calendar does not span the book's `date_range` for every type.
  Prints per (type, window) affected DATES and rows; a cell under
  `MIN_EVENT_DATES = 25` affected dates prints its n and is NOT READ — no
  mean, no CI, no verdict.
- **G1** coverage before numbers: `UF.coverage()` (OHLC-only denominator for
  `vrp`), real/tweak source split, `diag["debit_calib"]`, ticker-demean
  eligibility counts.
- **G2** every mean carries a date-clustered CI (`protocol.boot_ci_by_date`);
  every headline is re-cut by `protocol.window_cuts` AND by a hand ex-BOTH cut
  of the two dominant windows (`window_cuts` drops one at a time); every
  headline is year-split (`protocol.by_year` / sign stability) and split real
  vs tweak.
- **G3** units: `iv_entry_pct` is a DECIMAL FRACTION (0.3295 = 33% IV); no
  conversion anywhere; the report prints a one-line units note.
- **G4** no annualised figure, no Sharpe, no time-to-recover. R, never $, on
  any comparison that changes composition.
- **Anti-tuning:** proximity windows are `{0, ±1, ±2, ±3, ±5}` calendar days
  and the control cell is "no event of that type within ±5". Neither set may
  grow after any result is seen. Event types are the five named here; none may
  be added or dropped. Day-0 assignment: a `pre_open` day-0 event buckets as
  "after" (the print is in the entry fill); a post-open day-0 event buckets as
  "before" (the position sits in front of it).

**Verdict grammar, worded now.**
- **EVENT-PRICES-IV** — H1 clears its floor, holds sign in both window cuts
  and in every year, and survives the `mech_vol` re-cut. A characterisation of
  the book, not a rule. Queues an independent-window confirmation; ships
  nothing.
- **REGIME-PROXY** — H1's separation is absorbed by the `mech_vol` re-cut.
- **POWER-STOPPED** — every cell of an arm falls under `MIN_EVENT_DATES`.
  Census only; nothing read, nothing refuted, no verdict drawn from that arm.
- **NULL** — cells are powered and no arm separates. The macro-event layer is
  CLOSED for this book and the live pipeline never pays the version bump.
- **EXIT-TRIGGER (H4, conditional).** If and only if ARM X shows a monotone R
  pattern in event position within the hold across ≥ `MIN_EVENT_DATES`
  affected dates, a SEPARATE study `macro_event_exit` (f2_management) is
  queued with its own pre-registration. No exit variant is replayed in THIS
  study.

A study may earn one verdict per arm (e.g. ARM I REGIME-PROXY + ARM P
POWER-STOPPED); the catalog verdict summarises them without averaging.

## 2026-08-19 — AMENDMENT 1 (after the first run): ARM V gains an SPY-PRICE companion table

Written AFTER the first run and its replication review; the VIX results had
been seen when this was added, the SPY-return numbers had NOT. Operator asked
"how about the relationship with index price?" — the honest home for that is
the same context arm, not a scratch read.

**ARM V-price (H3 extension, CONTEXT ONLY — same standing as the VIX table:
no verdict may rest on it).** From the same `spy_vix_daily_full.csv` series
and the SAME event anchors as the VIX table (session 0 = the session the
release lands on or first after):
- per event-relative session t−5..t+5: mean SPY close-to-close return (%),
  with the same by-event bootstrap CI;
- per type, two pre-declared cumulative windows: PRE drift t−3→t0 close and
  POST drift t0→t+3 close (the pre-FOMC-drift literature window; three
  sessions either side, fixed here before computing).
No book join, no new proximity windows, no change to any gate, floor, or
readable cell. The five event types and the t−5..t+5 range are unchanged.
