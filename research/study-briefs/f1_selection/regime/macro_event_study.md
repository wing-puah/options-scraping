# macro_event_study — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/regime/macro_event_study.md); where the two differ, the registration wins.
> Latest outcome: no PRIMARY v3 verdict is recorded. On v4, which is not PRIMARY: `X-C1` `SURVIVAL-ARTIFACT`, and the exit thread is `DE-QUEUED` — 2026-09-28 · [record](../../../study-results/f1_selection/regime/macro_event_study.md).
> Nothing else here is a result.

## The question

Do scheduled US macro events show up in this book? The events are FOMC decisions, FOMC minutes, CPI, NFP and PCE. The study looks in three places: the implied volatility a play is entered at, what the play earns, and when it exits. It also records market-level context.

## What it compares

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

## How it is judged

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

## Possible verdicts

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

## What could ship

Nothing ships under any outcome. Feeding an event feature to the analysis prompt is an input change. That change is a v5 version bump with new tabs, and no result here may authorise it. The study changes no pipeline column, no `BaselineDaily`, no prompt and no harness code.

## What this study cannot tell you

- Anything from `ARM V` or `ARM V-price`. They show index volatility, not the book's single-name IV.
- Whether a macro-event exit rule works. No exit variant is replayed here.
- Whether the calendar was complete when compiled. A date announced after the fact is a look-ahead the file cannot detect.
- Anything from `ARM X` on its own. A hold contains a late event only if it survived.
- Anything about event proximity beyond calendar days, because the proximity windows are calendar days.
