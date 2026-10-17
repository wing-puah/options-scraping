# refuse_floor_forward — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f4_deployment/refuse_floor_forward.md); where the two differ, the registration wins.
> Latest outcome: `(R, F2, $500)`, `(R, F3, $500)` and the declared secondary `(R, F3, $500) + 20% net floor` all `STILL-OPEN` on both cap cells; no forward signal date had a loaded row — 2026-10-10 · [record](../../study-results/f4_deployment/refuse_floor_forward.md).
> Nothing else here is a result.

## The question

On signal dates from 2026-10-08 onward, do two cells keep a positive mean R and a survivable drawdown? Both cells looked good on the existing book, but both were seen before anyone named them candidates. Only new dates can confirm them.

- `account_sim`'s [F2](../../glossary.md#f1-vs-f2) refuses any pick whose one-contract max loss exceeds the budget.
- `narrow_to_fit`'s `(R, F3, $500)` narrows such a pick to the widest listed spread that fits, and refuses it if none fits.

The grade is a [confidence sequence](../../glossary.md#confidence-sequence). It stays valid however often the suite looks at it. It has no end date.

## What it compares

Both cells run unchanged from their own registrations. Selection, exits and the replay harness are frozen. A refused pick does not use one of the day's three slots, in both cells. The account starts fresh at $25,000 on the first forward date.

| Object | What it does | Kind |
|---|---|---|
| [refuse_floor_forward (R, F2, $500)](../../arm-index.md#refuse_floor_forward) | Refuses an unaffordable pick. Cap cells (0.25, 1.50) and (0.25, 2.50) | **HEADLINE** cell |
| refuse_floor_forward (R, F3, $500) | Narrows an unaffordable pick. Both cap cells | **HEADLINE** cell |
| refuse_floor_forward (R, F1, $500) | `account_sim`'s headline. The transfer comparator | control |
| refuse_floor_forward (R, F2, $1,000) | Printed, not graded | control |
| refuse_floor_forward (R, F3, $500) + 20% net floor | The same walk. A narrowed debit spread with net debit under 20% of width is refused. Credit spreads are never floored | declared secondary |

F2 and F3 each get their own verdict line, and neither moves the other. The floored line has its own sequence and look-log entry. It sits outside the four-sequence family and never moves F3's verdict.

## How it is judged

**Population.** Every v4 signal date from 2026-10-08 onward, in PRIMARY and SECONDARY, with real and `strike_expiry_tweak` rows only. A prompt version bump freezes the grade at the last v4 date. Earlier dates print as "seen — context only" and never enter the statistic.

**Statistic.** One observation per forward signal date on which the cell took at least one position. The value is that date's mean R. Observations run in signal-date order. The sequence stops before the first forward date that still holds an open position.

**Boundary.** The asymptotic confidence sequence of Waudby-Smith et al. (2024). The graded interval is the running intersection of the sequence from its start.

| Constant | Value |
|---|---|
| α | 0.0125 per sequence, two-sided. Four graded sequences, 0.05 split four ways |
| `t*` | 150 dates |
| `ρ` | 0.27133 |

**Minimum counts.** No interval verdict reads until a sequence holds at least 30 dates and 60 taken positions, both in PRIMARY. Below either, the cell reads `STILL-OPEN`. The drawdown breach is the exception: it fires at any count.

**Gates.** Each exits non-zero on failure, except `GN5`.

- `G2`–`G5`: `account_sim`'s own, run on the forward book.
- `GN5`: prints. If more than 10% of over-budget PRIMARY picks end `narrow_unpriced`, both F3 cap cells print `AWAITING SCRAPE` for that look. F2 is still graded.
- `FW2`: refuses if any forward-sequence date precedes 2026-10-08.
- `FW3`: no hardcoded count, no annualised figure, Sharpe or time-to-recover.
- `FW4`: the interval at the previous look's `t` must reproduce from current data unless a changed observation explains the difference.

**Context.** Every look prints `A2-reg`, `A2-all`, `A2-cap`, `FW5`, `A6`, `FWD`, `FWT`, MTM maxDD and the SECONDARY sequence. None sets a verdict. Some gate a ship proposal.

## Possible verdicts

Each cap cell gets the first matching row, from the top. A cell's line is the worse of its two cap cells, so `FORWARD-CONFIRMED` needs both.

| Token | What it means |
|---|---|
| `AWAITING SCRAPE` | F3 only. `GN5` fired on this look. Census only |
| `FORWARD-REFUTED (drawdown)` | Realized-on-close maxDD on the forward account exceeds 25% of $25,000, on PRIMARY or SECONDARY. Permanent |
| `FORWARD-REFUTED (edge)` | Minimum counts met and the interval's upper bound is below +0.10 R. Permanent |
| `FORWARD-CONFIRMED` | Minimum counts met and the interval's lower bound is above zero. Permanent unless a drawdown breach follows |
| `STILL-OPEN` | Anything else. The normal state for months |

If the running intersection ever empties, the look prints `CS EMPTY`. The cell reads `STILL-OPEN` and the operator is told.

## What could ship

Nothing ships directly. A `FORWARD-CONFIRMED` line lets the operator consider one [§2](../../../docs/deployment-rules.md#s2) change for that cell.

- F2: skip a survivor whose one-contract max loss exceeds 2% of capital, and the next survivor takes its slot.
- F3: narrow an unaffordable survivor to the widest spread that fits 2% of capital, refuse it if none fits, and the next survivor takes its slot.

The proposal also needs, at the confirming look and on both cap cells: `A2-reg` and `A2-all` at least 60%, the largest `FW5` move at most 15 points, and `FWD`'s median maxDD at most 25%. The operator chooses at most one of the two changes. A `FORWARD-REFUTED` line closes that cell as a candidate.

## What this study cannot tell you

- Whether either rule works on dates already read. The statistic never pools a date before 2026-10-08.
- Whether a rule that later stops working is caught. A rollback trigger written when the rule ships does that.
- Whether any sub-population works. No regime, structure, tier, DTE or month cut is graded.
- Anything about the floored line as a ship candidate. A ship of F3 needs the headline line.
- Anything soon. The registration expects `STILL-OPEN` for a long time.
