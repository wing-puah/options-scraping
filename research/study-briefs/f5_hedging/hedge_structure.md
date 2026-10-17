# hedge_structure — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f5_hedging/hedge_structure.md); where the two differ, the registration wins.
> Latest outcome: `H0 FILL NOT MET` (P1 fillable on 24.5% of deployed dates, 16.7% of worst-decile dates); `H2 NOT EVALUABLE` (parts a and c MET, part b n = 4) — 2026-09-28 · [record](../../study-results/f5_hedging/hedge_structure.md).
> Nothing else here is a result.

## The question

Does the calendar hedge survive a pre-registered pick rule, a fixed universe and a strict fill definition?

The 2026-08-12 `vol_sleeve` run left the calendar as its one candidate. This study re-derives that number on a smaller sample under rules written first. The number is expected to come out different.

## What it compares

The pick rules are decision-time only, and the list is closed. Each rule chooses one fillable calendar per day from the day's fillable calendars. [`hedge_structure ARM H`](../../arm-index.md#hedge_structure-arm-h) is `P1`; it runs first.

| Label | What it picks | Kind |
|---|---|---|
| `P1` | Nearest at-the-money: min \|K\*−S\|/S | THE RULE |
| `P2` | Longest near-leg DTE | robustness fan |
| `P3` | Shortest near-leg DTE | robustness fan |
| `P4` | Widest expiry gap | robustness fan |
| `P5` | Same ticker as the day's top-ranked deployed position (`P1` breaks ties) | robustness fan |
| `P6` | ETF underlyings only, then `P1` | robustness fan |

A `P2`–`P6` pass with `P1` failing is a candidate for a future window, never a ship.

[`hedge_structure ARM S`](../../arm-index.md#hedge_structure-arm-s) sweeps other structures. It runs only after `ARM H` has printed, in its own invocation and report.

| Label | Structure | Kind |
|---|---|---|
| `S1` | `put_calendar` | sweep |
| `S2` | `put_diagonal` | sweep |
| `S3` | `narrower`: bear vertical with the short pulled up | sweep |
| `S4` | `wider`, rerun unchanged | plumbing control |
| `S5` | `long_put`, rerun unchanged | plumbing control |
| `S6` | `iron_condor` | sweep, only if the leg scrape reaches ≥ 60% four-leg group coverage; otherwise NOT EVALUABLE |

A sweep cell is a CANDIDATE only if its worst-decile CI excludes zero at Bonferroni α = 0.05 / (n_structures × n_pick_rules). It must also be right-signed every year present and clear `H0`. Nothing in `ARM S` can ship from this run.

## How it is judged

**Population and basis.** The ladder's deployed book (`top_k_per_day`, k=3, A|B). Only dates where the ladder deployed count. A candidate must be fillable on the ladder's own entry session, with both legs cached on `grid[0]`. Candidates with `entry_net ≤ 0` or `far_exp ≤ near_exp` are excluded and counted.

**Sizing and exit.** One hedge per day, at most half a position, on the shipped $50k basis. The portfolio effect runs on a grid of sleeve fractions f, as in `hedge_sizing` D3. Exits are `DEBIT_PROD` (pt .90 / sl .75 / tef .75), with no calendar-specific exit. A hold-to-near-expiry table prints as a labelled sensitivity and may not change the verdict.

| Parameter | Values |
|---|---|
| Sleeve fraction f | 0, 0.25, 0.50, 1.0 |

**Baselines.** The calendar must beat both:

- the deployed ladder alone at $50k;
- the ladder plus the shipped bear hedge sleeve.

**Gates.** All must pass before any hedge number is read.

- `H0` FILL: `P1` produces a fillable hedge on ≥ 60% of deployed-book dates and on ≥ 60% of the book's worst-decile dates. Either failing fails the gate. Unfillable days count as f=0, never dropped.
- `H0b` FRESHNESS: the headline must survive `stale_at_cap ≤ 3` and `pct_real ≥ 0.5`.
- Reconstruction: `R1` is quoted; `R2` to `R4` must reproduce, and an `R4` failure exits non-zero. See [Gates](../../pre-registrations/f5_hedging/hedge_structure.md#gates) for `R1` and `R2`.

| Check | Must reproduce |
|---|---|
| `R3` | 220 positions, 90 dates, $63,553 |
| `R4` | With the pick rule off and the loose fill rule, the `vol_sleeve` calendar cell exactly: 183 rows, meanR +0.158, $28,059 |

**Bar.** Five criteria, `H1`–`H5`, mirror `hedge_sizing` D1–D5.

1. `H1` STANDALONE: context only, not a gate. A negative standalone figure does not fail a hedge.
2. `H2` HEDGE CONTRIBUTION is the primary gate. All three parts must hold:
   - date-level correlation of the two daily series < 0;
   - mean sleeve R on the book's worst-decile dates > 0, with the date-clustered CI excluding zero;
   - the worst-quartile tail is positive in ≥ 2 evaluable years.
3. `H3` SIZING: the largest f whose max drawdown and worst single date are both no worse than f=0.
4. `H4` CONDITIONAL PICK: within-date comparison of `P1` against the day's average fillable calendar and against each of `P2`–`P6`.
5. `H5` TIMING is post-hoc and labelled. It is candidate-only.

**Power stop.** If the `P1` worst-decile cell has fewer than 10 positions, the `H2` CI is not read. `H2` is then recorded NOT EVALUABLE, not failed.

## Possible verdicts

The registration prints gate outcomes and no single token. The tokens below are the ones it words.

| Token | What it means |
|---|---|
| `H0 FILL NOT MET` | `P1` fails the 60% fill floor on either date set |
| `H2 NOT EVALUABLE` | The worst-decile cell has fewer than 10 positions. The CI is not read |
| `H2 MET` | All three parts of `H2` hold |
| candidate | Anything short of the ship criteria below |

## What could ship

Nothing changes `config/backtest.yml`. The most this study can produce is an optional second hedge sleeve in [deployment rules §4](../../../docs/deployment-rules.md#s4). That needs `H0` MET, `H0b` not flipping the verdict, `H2` MET and `H3` deployable at f ≥ 0.25. Anything less is a candidate.

## What this study cannot tell you

- Whether any `ARM S` structure ships. Nothing there can ship from this run.
- Whether ratio spreads, straddles or strangles work. Ratio spreads are out of scope on a harness limit; straddles and strangles are closed.
- A verdict from `H5`. It is post-hoc and candidate-only.
- Whether the hold-to-near-expiry exit changes the verdict. It may not.
- A likely outcome of `H2`. The registration expects the worst-decile cell near 7–9 positions, so `H2 NOT EVALUABLE` is a correct result that means "needs new dates".
