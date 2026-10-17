## macro_event_study — do scheduled macro events show up in this book?

<!-- brief:start -->
## In brief

> Plain-language brief for readers. The registration below is the binding text; where the two differ, the registration wins. `study_review` cuts this brief out before grading, so the blind graders never see it.
> Latest outcome: no PRIMARY v3 verdict is recorded. On v4, which is not PRIMARY: `X-C1` `SURVIVAL-ARTIFACT`, and the exit thread is `DE-QUEUED` — 2026-09-28 · [record](../../../study-results/f1_selection/regime/macro_event_study.md).
> Nothing else in this brief is a result.

**The question**

Do scheduled US macro events show up in this book? The events are FOMC decisions, FOMC minutes, CPI, NFP and PCE. The study looks in three places: the implied volatility a play is entered at, what the play earns, and when it exits. It also records market-level context.

**What it compares**

The study has four hypotheses. Each maps to one arm under a different letter. Reports cite both forms.

| Object | What it does | Kind |
|---|---|---|
| [macro_event_study ARM I](../../../arm-index.md#macro_event_study) (H1) | Tests whether entry `vrp` is higher within k days before an event than on control sessions, and lower within k days after | PRIMARY arm |
| [macro_event_study ARM P](../../../arm-index.md#macro_event_study-arm-p) (H2) | Reports mean [R](../../../glossary.md#r) and E by entry-proximity bucket per event type, within structure. A pooled cross-structure table may print but carries no conclusion | arm |
| macro_event_study ARM V (H3) | Reports VIX level and 1-day change by event-relative day t−5..t+5. `ARM V-price` adds the SPY return for the same days, plus PRE drift t−3→t0 and POST drift t0→t+3 | CONTEXT ONLY |
| macro_event_study ARM X (H4) | Reports `exit_reason` mix and R for rows whose hold spans an event, and exit position relative to the nearest event | DESCRIPTIVE, no verdict |

The frozen proximity windows, in calendar days:

| Window | Values |
|---|---|
| Same day | 0 |
| Either side | ±1, ±2, ±3, ±5 |

The control cell is "no event of that type within ±5".
Neither set may grow after a result is seen. No event type may be added or dropped.

**How it is judged**

**Calendar.** `config/macro-events.yml` holds the schedule. The loader refuses any date past an event type's `verified_through`.

**Distance.** Event distance is measured from the entry session, not the signal date. A day-0 event released before 09:30 ET counts as "after", because the print is in the entry fill. A day-0 event released after the open counts as "before".

**Population.** Pooled real and tweak pricing tiers, no Black-Scholes rows, era `v3` (118 dates). The report header must name the era.

**Metric.** `vrp` is primary for `ARM I`. Ticker-demeaned `iv_entry` (tickers with at least 5 appearances), `iv_spread` and `iv_pct` are secondary. Every headline is re-cut within `mech_vol`, so a regime effect is not read as an event effect.

**Pre-declared non-readable.** `n_*_in_dte` is census only. It is near constant on this book, and the realized-hold variant is endogenous.

**Gates.** Each gate exits non-zero on failure.

- `G0`: runs first and blocks every read. It exits 4 if the calendar does not span the book for every type. A cell under `MIN_EVENT_DATES = 25` prints its n and is not read.
- `G1`: coverage prints before any number.
- `G2`: every mean carries a date-clustered CI. Every headline is cut by `window_cuts`, by a hand cut that drops both dominant windows, by year, and by real versus tweak.
- `G3`: `iv_entry_pct` is a decimal fraction, with no conversion anywhere.
- `G4`: no annualised figure, no Sharpe, no time-to-recover. R, never dollars, on any comparison that changes composition.

The registration expects the FOMC ±1 and ±3 cells to hit the `G0` floor. A stop there is no surprise, and the floor does not move.

**The exit trigger.** `ARM X` can queue a separate study, `macro_event_exit`, only through a survival control. A late event can sit inside a hold only if the position survived that long. The control has two parts.

- `X-C1`: rows whose hold spans at least 1 event and has `days_held` ≥ 20 sessions. The EARLY/MID/LATE mean-R table is recomputed there.
- `X-C2`: spanning rows split into `days_held` terciles, with a 3×3 position-by-length census.

**Possible verdicts**

One verdict per arm is possible. The catalog verdict summarises them without averaging.

| Token | What it means |
|---|---|
| `EVENT-PRICES-IV` | `ARM I` clears its floor, holds sign in both window cuts and every year, and survives the `mech_vol` re-cut. A characterisation, not a rule |
| `REGIME-PROXY` | The `mech_vol` re-cut absorbs `ARM I`'s separation |
| `POWER-STOPPED` | Every cell of an arm is under `MIN_EVENT_DATES`. Census only |
| `NULL` | Cells are powered and no arm separates. The macro-event layer is closed for this book |
| `TRIGGER STANDS` | `X-C1` is monotone in the same direction with at least 25 affected dates. `macro_event_exit` is queued with its own registration |
| `SURVIVAL-ARTIFACT` | `X-C1` is non-monotone, or flat within every `X-C2` length tercile. `macro_event_exit` is not queued |
| `POWER-STOPPED` (`X-C1`) | `X-C1` has under 25 affected dates. The follow-up stays queued but blocked on data |

`SURVIVAL-ARTIFACT` re-arms only if a future run fires the controlled trigger `X-C1`, never the raw one.

**What could ship**

Nothing ships under any outcome. Feeding an event feature to the analysis prompt is an input change. That change is a v5 version bump with new tabs, and no result here may authorise it. The study changes no pipeline column, no `BaselineDaily`, no prompt and no harness code.

**What this study cannot tell you**

- Anything from `ARM V` or `ARM V-price`. They show index volatility, not the book's single-name IV.
- Whether a macro-event exit rule works. No exit variant is replayed here.
- Whether the calendar was complete when compiled. A date announced after the fact is a look-ahead the file cannot detect.
- Anything from `ARM X` on its own. A hold contains a late event only if it survived.
- Anything about event proximity beyond calendar days, because the proximity windows are calendar days.

---
<!-- brief:end -->

_Registered 2026-08-19._

## Question

Do scheduled US macro events — FOMC decisions, FOMC minutes, CPI, NFP, PCE —
show up in this book?

- in the IV the plays are entered at (ARM I),
- in what they earn (ARM P),
- or in when they exit (ARM X)?

Plus market-level context (ARM V).

## Population and basis, fixed here

The calendar, the loader, the distance convention and the era are all fixed
before any number is read.

- Calendar: `config/macro-events.yml`, hand-authored from the official Fed /
  BLS / BEA schedules cited in its `meta.sources`. Five types
  (`fomc, fomc_minutes, cpi, nfp, pce`), 2023-06-01 onward, per-type
  `verified_through`.
- Loader: `scripts/backtest_study/lib/macro_calendar.py`. `next_event` is
  strictly after `as_of`, `last_event` on or before; `count_between` is
  start-exclusive / end-inclusive; `None` past `verified_through`;
  `unscheduled` events are excluded from forward-looking features only.
- **Event distance is measured from the ENTRY SESSION (`t.grid[0]`), not the
  signal date.** The entry basis is the next session's open, so every event on
  the signal date is already in the entry price. On the entry session itself,
  `pre_open` (release before 09:30 ET) decides whether the position is in front
  of the event: 08:30 CPI/NFP/PCE are in the entry price, while 14:00 FOMC
  statements and minutes are not — so a day-0 14:00 event counts as AHEAD of the
  position.
- Population: pooled real+tweak via `load_book` (bs excluded, proxy calibration
  gate ON), **era `v3`** — the 118-date 2024-06-17..2026-04-07 book. The bare
  `current` exports hold ~34 dates and are NOT the population; the evidence run
  is `--era v3` and the report header must name it.
- Known limitation, disclosed: the calendar records the schedule as published at
  compile time (`meta.compiled`), so a date announced after the fact would be a
  look-ahead the file cannot detect. Proximity windows are CALENDAR days.

## Plan-time observations, disclosed

Before this registration was written, a read-only count was run against the v3
exports using RECALLED FOMC dates and a first-Friday NFP proxy. It found:

- 1,088 of 1,118 pooled rows have an FOMC decision inside `min(dte, 120)`;
- book dates within ±1 / ±3 / ±5 calendar days of an FOMC decision were
  16 / 24 / 32 of 118.

Those are scoping numbers, not results. Two commitments follow from having seen
them, and both are made here rather than after the run:

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

## Arms

The study runs four arms, one per hypothesis: H1, H2, H3, H4.

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
STRUCTURE from the first look — the standing rule, because
`cpir`/`oi_confirm_pct`/`iv_pct` all looked predictive pooled and vanished
within structure. A pooled cross-structure table may print but carries no
conclusion.

### H3 — the market-context arm (ARM V)

VIX level and 1-day change by event-relative day t−5..t+5, over EVERY session in
the book span (~500 sessions from
`backtests/mech_regime/spy_vix_daily_full.csv`). This is index vol, not the
book's single-name IV: CONTEXT ONLY. No verdict may rest on it.

- **ARM V-price (H3 extension, CONTEXT ONLY — same standing as the VIX
  table: no verdict may rest on it).** It reads the same
  `spy_vix_daily_full.csv` series and the SAME event anchors as the VIX table
  (session 0 = the session the release lands on or first after), and prints two
  things:
  - per event-relative session t−5..t+5, mean SPY close-to-close return (%)
    with the same by-event bootstrap CI;
  - per type, two pre-declared cumulative windows — PRE drift t−3→t0 close and
    POST drift t0→t+3 close (the pre-FOMC-drift literature window; three
    sessions either side, fixed here before computing).

  No book join, no new proximity windows, no change to any gate, floor, or
  readable cell. The five event types and the t−5..t+5 range are unchanged.

### H4 — the exit arm (ARM X, DESCRIPTIVE, no verdict)

`exit_reason` mix and R for rows whose realized hold spans an event vs not, plus
exit position relative to the nearest event. ENDOGENOUS by construction, so it
is census only, and its sole output is the pre-declared TRIGGER below.

## Gates

Each gate exits non-zero on failure.

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

## Verdicts, worded now

A study may earn one verdict per arm (e.g. ARM I REGIME-PROXY + ARM P
POWER-STOPPED); the catalog verdict summarises them without averaging.

- **EVENT-PRICES-IV** — H1 clears its floor, holds sign in both window cuts
  and in every year, and survives the `mech_vol` re-cut. A characterisation of
  the book, not a rule. Queues an independent-window confirmation; ships
  nothing.
- **REGIME-PROXY** — H1's separation is absorbed by the `mech_vol` re-cut.
- **POWER-STOPPED** — every cell of an arm falls under `MIN_EVENT_DATES`.
  Census only; nothing read, nothing refuted, no verdict drawn from that arm.
- **NULL** — cells are powered and no arm separates. The macro-event layer is
  CLOSED for this book and the live pipeline never pays the version bump.

### EXIT-TRIGGER (H4, conditional)

ARM X's raw monotone-R-in-event-position read has an obvious artifact
mechanism: a hold only CONTAINS a late event if the position already survived
that long, so event position is mechanically coupled to hold length. The
trigger is therefore read only under a survival control, fixed here:

- **X-C1 (long-hold subset):** rows whose realized hold spans >=1 event AND
  `days_held >= 20` sessions (one trading month — long enough that
  EARLY/MID/LATE, the first-event-position tercile, are all mechanically
  reachable inside the hold; the boundary does not move once chosen).
  Within that subset, recompute the EARLY/MID/LATE mean-R table.
- **X-C2 (within hold-length terciles):** split spanning rows by
  `days_held` terciles (boundaries computed on the spanning population,
  disclosed in-sample); print the 3x3 position-by-length census.

The three readings of that control, worded now:

- **TRIGGER STANDS** only if X-C1 is monotone in the same direction with >=
  `MIN_EVENT_DATES` (25) affected dates — a SEPARATE study `macro_event_exit`
  (f2_management) is queued with its own pre-registration. No exit variant is
  replayed in THIS study.
- **SURVIVAL-ARTIFACT** — X-C1 is non-monotone, or flat within every X-C2
  length tercile: the trigger is reclassified as an artifact of hold length,
  and `macro_event_exit` is NOT queued. It re-arms only if a future run fires
  the CONTROLLED trigger (X-C1), never the raw one.
- **POWER-STOPPED** — X-C1 has < 25 affected dates: the control is
  unreadable, the follow-up stays queued but BLOCKED on data, and no exit
  study may be built until the controlled read exists.

Everything stays census-labelled; no gate, floor, window, or readable cell
of ARMs I/P/V changes.

## Ship criteria

RESEARCH ONLY. **Nothing ships from this study under any outcome.**
Feeding an event feature to the analysis prompt is an INPUT change and
therefore a v5 version bump with new tabs; that is explicitly deferred and no
result here may authorise it. No pipeline column, no BaselineDaily change, no
prompt change, no harness edit.
