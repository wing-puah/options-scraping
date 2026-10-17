# portfolio_delta — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f4_deployment/portfolio_delta.md); where the two differ, the registration wins.
> Latest outcome: PRIMARY v3 `NOISE` (2026-08-19). SECONDARY v4, which carries nothing, `DELTA-DOSE-RESPONSE` (2026-09-28). No arm clears the whole bar in either · [record](../../study-results/f4_deployment/portfolio_delta.md).
> Nothing else here is a result.

## The question

Do positions opened in a session do worse when the book already carries high net delta? And can an operator steer that net-delta level at all? Both questions concern exposure, not selection. The study reuses `account_sim` machinery by import and keeps its own registration.

## What it compares

Four arms, frozen at registration. No arm changes which signals are eligible, and none changes an exit. Every position replays under the shipped profiles. "Bear = hedge sleeve only" holds in every arm.

| Object | What it does | Kind |
|---|---|---|
| [portfolio_delta ARM D](../../arm-index.md#portfolio_delta) | Labels each session by open-book net delta-notional over equity at session open, before that day's picks. Bands: [0, 0.5), [0.5, 1), [1, 2), [2, ∞). Reports the outcome of positions opened in each band | descriptive, PRIMARY |
| portfolio_delta ARM B | Walks a net-delta ceiling of {1.0, 1.5, 2.0, 2.5, ∞} × equity through a local copy of `account_sim`'s admission | counterfactual arm |
| portfolio_delta ARM H\* | Resizes the shipped bear hedge sleeve to hold net delta at a target of {1.0, 1.5, 2.0} × equity. No pick is added or displaced | counterfactual arm |
| portfolio_delta ARM N | 200 seeded random admissions, matched on positions per date. Seed fixed and printed | null band |

The registration records one plan-time finding first. The deployed ladder is long-only: 219 of 220 picks have positive delta. Net delta can fall only by not trading or by resizing the sleeve.

## How it is judged

**Population.** PRIMARY is `--era v3`, the proxy-calibrated book of 795 rows over 118 dates, with the shipped `top_k_per_day` walk. SECONDARY is `current` (v4). It is reported only and carries nothing. The two eras are never pooled. PRIMARY episodes are dense; the full sparse book carries nothing alone.

**Fixed settings.** Capital, risk %, caps, positions per day, `take_floor`, `downsize` and exits come from `config/account-sim.yml` as committed. None is swept. Compounding is off.

**Measure.** The unit is the session, and every interval is date-clustered. ARM D reports mean [R](../../glossary.md#r) per band. ARM B and ARM H\* are within-date paired differences against the shipped walk (`BOOT_N = 10000`, α = .05). R is quoted, not dollars.

**Gates.** Each gate exits non-zero on failure, in this order.

- `G-DELTA`: the row's stored signed net `delta` is checked against per-leg cache greeks. At least 90% of rows must agree within 0.05, and at least 95% per-leg availability. A missing greek is `None`, never `0.0`.
- `G-EQUIV`: at the committed `caps.net`, ARM B's banded walk reproduces `account_sim.simulate()` exactly under `book_signature()` equality.
- `G-INVENTORY`: counts how many deployed dates each arm moves into a different band. An arm that moves fewer than 25 dates is `POWER-STOPPED`. Its cells are not read.
- `G3` (imported): the ledger identity holds at every session.
- `G5` (imported): every arm passes the outcome-blindness probe, and the resulting book matches the sighted one.

ARM D bands under `MIN_CELL_N = 20` positions print their n and are not read. No annualised figure, Sharpe or time-to-recover appears anywhere.

**Bar.** An arm is a candidate only if it meets all seven clauses.

1. The date-clustered bootstrap CI excludes zero.
2. Every [leave-one-date-out](../../glossary.md#loo--leave-one-date-out) fold is positive.
3. The sign survives `protocol.window_cuts` and the ex-both-windows cut added by hand.
4. The arm is positive in every calendar year present.
5. The arm is right-signed on both pricing tiers.
6. The arm has at least 25 affected dates.
7. The arm is above ARM N's 95th percentile.

Worst-decile cells print their n and are marked NOT A CRITERION.

## Possible verdicts

| Token | What it means |
|---|---|
| `LONG-ONLY-BY-CONSTRUCTION` | The ladder cannot reach a materially different net-delta level without not trading or resizing the sleeve. Registered as the likely verdict |
| `CANDIDATE-FOR-INDEPENDENT-WINDOW` | At least one arm clears the whole bar. It is queued for an independent window and nothing else |
| `DELTA-DOSE-RESPONSE` | ARM D shows a monotone, n-sufficient link between open-book delta at session open and the outcome of positions opened there |
| `NOISE` | No arm exceeds ARM N's 95th percentile and ARM D's bands are flat within their cells |
| `POWER-STOPPED` | `G-INVENTORY` fails for an arm. The census prints and nothing is read |

An arm that clears only clause 7 resolves to `NOISE` with a printed QUALIFICATION block naming the arms. `CANDIDATE-FOR-INDEPENDENT-WINDOW` sits below `LONG-ONLY-BY-CONSTRUCTION` and `UNDERPOWERED`. It sits above `DELTA-DOSE-RESPONSE` and `NOISE`.

## What could ship

Nothing ships. `DELTA-DOSE-RESPONSE` queues an independent-window check. It may then become a context note, never an automatic cap. No band, ceiling or target value may be adopted on its P&L.

## What this study cannot tell you

- Which delta level is better. The firewall bars reading a winner off the grid.
- Anything about selection or exits. Neither moves.
- Whether the exposure rule holds out of sample. The ladder is itself in-sample on this book, so any exposure rule is second-order in-sample.
- Anything from the worst-decile cells. They are descriptive only.
- Anything from SECONDARY v4 on its own.
