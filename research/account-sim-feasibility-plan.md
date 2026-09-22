# account_sim — plan to investigate the drawdown and reach feasibility at $25,000

**Most of the 35.0% drawdown comes from how a $25,000 account sizes one
contract, not from the market or from concentration.** Nothing ships. This
file is a plan: it orders the work, names what is ruled out, and leaves the
choice of route to the operator.

**Phase 0 ran on 2026-09-21.** So did steps 1, 3 and 5. The registered cap
cell prints `FEASIBLE` and the verdict on record belongs to the cell the
tracked config carries. What each step printed is in the
[entry](current.md#2026-09-21--account_sim--the-registered-cap-cell-prints-feasible-the-run-on-record-does-not);
this file keeps the design and the queue.

_Era v4 · exports 2026-09-19 · report `backtests/study_output/account_sim-latest.txt`
(re-run 2026-09-21 16:51 with the disclosure blocks; the figures below are
unchanged from the 2026-09-08 print) ·
[pre-registration](pre-registrations/f4_deployment/account_sim.md) · evidence
folders `backtests/feasibility_plan_20260920/` and
`backtests/feasibility_plan_20260921/` (both gitignored)._

Written 2026-09-20 from a nine-agent workflow: five investigators, three
planners, one critic. Every figure marked _exploratory_ came from a scratch
script over the positions CSV. None of them is a verdict, and none was written
into a study report.

## What the investigation found

**The one-contract floor carries the drawdown.** The study sizes a position as
`max(1, int(budget / max_loss_per_contract))`. Most picks cost more than the
budget for one contract, and the floor buys the contract anyway.

| Floor, PRIMARY taken positions at $25,000 | Value |
|---|---|
| Risk budget per position | $500 |
| Positions whose one contract exceeds the budget | 124 of 211 |
| Median reserved on those positions | $902 |
| Largest reserved | $4,318, or 17.3% of capital |

| Sizing, PRIMARY population, 2% risk | Max drawdown | Note |
|---|---|---|
| Exact fractional contracts | 23.9% | _exploratory_; identical at every capital from $25,000 to $250,000 |
| One-contract floor, dollar stop disabled | 38.2% | _exploratory_ |
| One-contract floor with the $500 stop (the report) | 35.0% | the stop recovers 3.2 points |

So the floor adds about 11 points, and the strategy's own drawdown at 2% risk
is about 24%. That is just under the bar, not comfortably under it.

**Inside the January–April 2025 window the loss is diffuse.** Floor positions
carried nine tenths of it, and no single loss is large. Dropping the three
worst positions in the whole book leaves the drawdown at 35.0%
(_exploratory_).

| Window exits | n | Dollars |
|---|---|---|
| All exits | 28 | −$8,755 |
| Floor positions (one contract over budget) | 17 | −$7,880 |
| Positions the budget could afford | 11 | −$875 |
| Worst single position (COIN) | 1 | −$878 |

**It is not one episode.** [A3](arm-index.md#account_sim) is read on the
single deepest drawdown, but the book has others close to the bar.

| Population | Peak → trough | Depth | Note |
|---|---|---|---|
| PRIMARY | 2025-01-10 → 2025-04-09 | 35.0% | the A3 failure |
| PRIMARY | 2024-07-10 → 2024-08-26 | 22.4% | August 2024 volatility spike |
| PRIMARY | 2024-10-14 → 2024-10-29 | 11.2% | a single position |
| SECONDARY | 2025-01 → 2025-04-09 | 40.8% | same window, 35 positions |
| SECONDARY | 2025-11-03 → 2026-03-30 | 38.4% | never recovered; invisible to PRIMARY |
| SECONDARY | 2024-07 → 2024-08-07 | 21.9% | |

The [PRIMARY](glossary.md#primary-dense-episodes-vs-secondary-full-book)
population's last dense episode ends 2025-09-26. A fix graded on PRIMARY alone
has never met the book's second-deepest drawdown.

**A registered arm already clears the bar and has never been graded.** Arm F2
refuses any pick whose one-contract max loss exceeds the budget. The
registration calls the F1-against-F2 contrast "the study's central object".
The report printed F2's row on every run and scored it against nothing.

Step 0b-iii scored it on 2026-09-21, and F2 is weaker than this plan hoped. On
the tracked cap cell it meets every criterion on PRIMARY and fails A1, A5 and
A6 on SECONDARY. On the registered cell it fails A2 at 53% of B2. The graded
table is in the [entry](current.md#2026-09-21--account_sim--the-registered-cap-cell-prints-feasible-the-run-on-record-does-not).

| Arm | n | Dates | Total | meanR | Max drawdown |
|---|---|---|---|---|---|
| (R, F1) headline | 211 | 107 | $28,049 | +0.277 | 35.0% |
| (R, F2) refuse the floor | 137 | 82 | $17,125 | +0.319 | 8.7% |
| (D, F1) | 224 | 111 | $23,272 | +0.246 | 35.7% |
| (D, F2) | 154 | 93 | $16,972 | +0.273 | 7.7% |

F2 costs 39% of the dollars and 25 trading dates. An _exploratory_ scoring has
it meeting A1, A2, A3 and A6 on PRIMARY. A4 and A5 were not computed. On
SECONDARY it prints 10.1%, but A1 fails there because the thin 2026 slice goes
slightly negative.

**The run does not use the registered headline cell.** The registration fixes
the net cap at 1.50 × equity and names (0.25, 1.50) as the headline. The
operator raised `caps.net` to 2.50 on 2026-08-13
([record](archive/13-account-sim-and-calendar-hedge.md)). The registration
carries no note of that change. The 1.50 cell is already known to print 20.3%
on 142 positions, so it must be handled as conformance, never as a fix.

Step 1 ran that cell on 2026-09-21. It prints `>>> FEASIBLE <<<`, meeting
every criterion on both populations. That figure was already in the cap grid,
so it is not new evidence — what is new is that the verdict on record belongs
to an unregistered cap cell. Which cell the tracked config should carry is
step 2, and it is the operator's.

**Other findings.**

- The book is 100% long delta: 167 bull call spreads and 44 bull put spreads.
  Megacap tech, semiconductors and crypto carried 99.8% of the window loss.
- The window was less concentrated and smaller than the rest of the book.
  The table below the list has the figures.
- An entry gate on the mechanical regime does not fix it. Only one window
  position was opened after the regime flipped to bear on 2025-02-24. Refusing
  bear-day entries leaves 32.3% (_exploratory_).
- The risk knob is mostly a stop. Lowering `risk_per_trade_pct` barely cuts
  contracts, because most positions are already at one contract. It cuts the
  dollar stop in full. The 18.0% in the
  [knob table](current.md#2026-09-20-fourth--account_sim--the-capital-ladder-prints-again-no-registered-rung-passes-a3)
  is therefore an exit-rule change, not "smaller positions".
- All 37 dollar-stop exits lost more than $500. The mean is −$659 and the
  worst −$2,796, because the stop is checked on daily marks.
- The 2026-09-05 → 09-08 flip was not new losing rows. Of the 28 window
  positions, 27 were priced in August 2026. The one new row is COIN
  2025-02-26, and without it the window still prints 31.5%.
- None of the 28 rows is among the 14 pre-fill rows or the six wrong-strike
  rows. Four of them (NVDA ×3, TLT) can no longer be re-priced offline.

| Measure | Inside the window | Rest of the book |
|---|---|---|
| Top-cluster share of gross delta-notional | 0.38 | 0.50 |
| Open positions, average | 11.9 | 14.6 |
| Net delta-notional, average | 1.42× | 1.68× |

| `risk_per_trade_pct` | Total contracts | Dollar stop |
|---|---|---|
| 2% (configured) | 288 | $500 |
| 1.5% | 253 | $375 |
| 1.25% | 239 | about $312 |

## What is ruled out, and why

| Idea | Why it is out |
|---|---|
| Pick a value from the knob table | Every value was seen against the bar. The registration forbids adopting a cap value on P&L grounds. |
| Derive the risk budget from Kelly, or scale it by volatility | At $25,000 the budget mostly moves the dollar stop. That is an exit rule on dates [`exit_drawdown`](arm-index.md#exit_drawdown) already closed. |
| A portfolio-heat or effective-bets cap | The window was less concentrated than the book. `concurrency_correlation` and `portfolio_delta` both closed as noise. |
| A de-risk trigger near the net-cap ceiling | It would be a fifth trigger study over the same dates. [§2.1](next-steps.md#21-the-max-drawdown-hedge-question--closed-2026-09-04) says not to register a fourth. |
| Swap single names for cheaper ETFs | It changes what is traded. The edge would have to be re-established, and the change is a prompt version bump. |
| A size grid for the bear sleeve | The sleeve is refused by the caps on 50 dates. Availability binds, not size. |
| An entry-side regime gate | The losing positions were opened while the regime read bull. |
| A drawdown-keyed sizing throttle, Turtle-ladder or [`exit_drawdown` ARM D](arm-index.md#exit_drawdown) shape | Eighteen exploratory configurations closed 2026-09-22: PRIMARY realized maxDD moves 35.0–35.7% against a 35.0% baseline, SECONDARY flips sign by basis, and the faithful contracts-only version is nearly inert at this capital ([entry](current.md#2026-09-22--account_sim--a-turtle-drawdown-throttle-is-inert-at-25000-closed-unregistered)). |

## The plan

Steps run in order. A step marked _registration_ does not start until its
pre-registration is committed.

**What has run.** Every row below is DONE, on 2026-09-21, and recorded in the
[entry](current.md#2026-09-21--account_sim--the-registered-cap-cell-prints-feasible-the-run-on-record-does-not).
The step tables that follow keep the design; this one says what came back.

| Step | Result |
|---|---|
| 0a | No window row is a pre-fill or wrong-strike row. Four DD1 exits still cannot be re-priced offline, and a cache pull added no files. _exploratory_ |
| 0b-i | Marked to market, PRIMARY reads 42.1% against the realized 35.0%. Every position reconciles |
| 0b-ii | Four PRIMARY drawdowns past 5%, five on SECONDARY, one of which never recovers |
| 0b-iii | F2's first graded read. It meets every criterion on PRIMARY and fails A1, A5 and A6 on SECONDARY |
| 0b-iv | Availability binds the sleeve, not size: 9 fills against 15 cap refusals inside SECONDARY's second drawdown |
| 0b-v | Every dollar-stop exit lost more than the stop, on both populations. `cost_total` covers 4 of 211 rows |
| 0c | At $25,000 one contract fits 39% of ladder-eligible candidates. Half fit at $34,600 |
| 0d | `selection_order` prints `ORDERING-IS-NOISE` on the current era |
| 1 | The registered (0.25, 1.50) cell prints `>>> FEASIBLE <<<`, meeting every criterion on both populations |
| 3 | The realized 35.0% sits at the 71st–82nd percentile of its own resampled paths. No decision rule attaches |
| 5 | v3 prints `FEASIBILITY NOT CONFIRMED`, A3 met at 17.4%. It does not reproduce the v4 failure |

### Phase 0 — print what the study already knows

No new simulation and no new parameter. Each item is a disclosed addition to
the report, like the 2026-09-20 ladder columns.

| Step | Work | Output |
|---|---|---|
| 0a | Join the three drawdown windows against `backtests/reprice_census_20260920/`, including the 49 open-fill and 80 offline-unpriceable rows. Try a cache pull for the four unpriceable window rows. | Whether 35.0% stands on rows that can be verified |
| 0b-i | Print the mark-to-market curve beside the realized one, from `lib/mtm_curve.py::book_curves` with `TARGET_POSITION`. | A3 on both bases |
| 0b-ii | Print A3 per peak-to-trough drawdown (DD1…DDn) on both populations. Do not key it on the population's E1–E5 episodes: both large drawdowns straddle a gap between them. | The episode table above, in the report |
| 0b-iii | Score A1–A6 for all four arm cells. `print_arms` already returns the four simulations and `evaluate()` is pure. | F2's first graded read, with A4 and A5 |
| 0b-iv | Print ARM H's max drawdown and its fill and refusal counts per drawdown, and export the sleeve rows. | The first look at the only negative-delta instrument |
| 0b-v | Print the dollar-stop overshoot block and the count of rows carrying `cost_total`. | Disclosure only |
| 0c | Per-contract cost census and a capital-adequacy curve: the share of emitted plays one contract of which fits 2% of capital, by capital. | The one outcome-blind answer to "what capital does this book need" |
| 0d | Quote `selection_order`'s current-era verdict on adverse ordering. | Known before any cap changes |

The cost-applied A3 is blocked: `cost_total` is filled on 4 of 211 rows. It
waits on the whole-book re-price in *Waiting on the operator* items 6–9.

### Phase 1 — conform to the registration

| Step | Work | Gate |
|---|---|---|
| 1 | Run the registered (0.25, 1.50) cell on F1 and F2 and score all of A1–A6. The open question is A2 and A5 at about 142 positions, not the drawdown. | Copy `-latest.txt`, the positions CSV and the site page aside first; a `--config` run overwrites them |
| 2 | Fold two rulings into the registration as `Resolved at build` tags: the 2026-08-14 verdict wording and the cap-cell change. | Operator. Written as what was decided and when, never as "this passes A3" |

### Phase 2 — measure, without a decision rule

| Step | Work | Note |
|---|---|---|
| 3 | Block-bootstrap the exit-session P&L at block lengths 5, 10 and 20, seeds printed, both populations. Report where 35.0% and 25.0% sit in the distribution. | New adapter code; `lib/forward_drawdown.py::block_bootstrap` is a paired-row tool. A wide band never licenses a pass: 25% is the operator's tolerance, not an estimate |
| 4 | Add a one-contract affordability line to the deploy card, and tally it on live fills. | An attention flag, never a verdict. Needs `RECOMMENDATION_COLUMNS`, the tab header and `docs/recommendations-reference.md` |
| 5 | Run `python3 -m scripts.backtest_study run account_sim --era v3`, artifacts copied aside. | A composition control, not out-of-sample: same market path, different plays. v3's dense episodes miss the January–February 2025 entries |

### Phase 3 — candidate rules, one registration

| Step | Work | Gate |
|---|---|---|
| 6 | Write one pre-registration for whatever survives Phases 0–2. | _registration_ |
| 7 | Re-strike coverage census, read-only. Coverage means both substituted legs price across the whole held window. | No scrape until item 8 of *Waiting on the operator* is decided |
| 8 | Arm W: cap the spread width so one contract fits the budget, every re-strike priced, A1 re-established on the substituted book. A DTE ceiling is a conditional clause inside it. | Step 7 clears, and the operator funds the scrape. In production the rule would live in the prompt or the deploy card |

The step 6 registration carries three guards:

- **A trial ledger.** More than 70 configurations have now been scored
  against the 25% bar on this one path: four knob values, seven capital rungs,
  the 16-cell cap grid, four arm cells on two populations, this
  investigation's sweeps, and the 18 Turtle-throttle reads closed 2026-09-22
  ([entry](current.md#2026-09-22--account_sim--a-turtle-drawdown-throttle-is-inert-at-25000-closed-unregistered)).
  Each is listed and marked as seen. New arms on this era are capped at
  three.
- **A deflated bar.** A candidate must put its drawdown under 25% at the median
  of its own block-bootstrap paths, not only on the realized path (Bailey and
  López de Prado, [SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)).
- **A transfer requirement.** DD1, DD2 and the SECONDARY 2025-11 drawdown must
  all improve, and the v3 control must not point the other way. These are three
  correlated readings of one path, so passing is necessary and not sufficient.

The post-2026-08-11 live dates are the only unspent population. The re-score
criterion and its minimum date count are written before those rows exist, and
a thin live cut is reported as underpowered.

### Phase 4 — the operator card

Step 9 puts one card in front of the operator for
[item 5](next-steps.md#waiting-on-the-operator): A3 on both bases, the
drawdown table, the bootstrap band, the four arm grades, the capital-adequacy
curve and the corrected reading of the risk knob.

## The routes to feasible at $25,000

None is recommended yet. Phase 0 and Phase 1 decide which are real.

| Route | What it means | Evidence today | Cost or risk |
|---|---|---|---|
| A. Trade only what the budget affords (F2) | Skip a pick whose one contract risks more than 2% | Registered arm, graded 2026-09-21: every criterion met on PRIMARY at the tracked cap cell; 8.7% there, 10.1% SECONDARY | −39% dollars, 107 → 82 dates; A4 and A5 now known and A5 is met; A1, A5 and A6 fail on SECONDARY; A2 fails at 53% on the registered cell |
| B. Return to the registered net cap | `caps.net` 2.50 → 1.50 | Run 2026-09-21: `>>> FEASIBLE <<<`, every criterion met on both populations, 20.3% on 142 positions | Marked to market it reads 25.9% PRIMARY and 44.8% SECONDARY; 8–12% of resampled PRIMARY paths pass 25%; it is the operator's 2026-08-13 choice to reverse |
| C. Re-strike to fit the budget (Arm W) | Narrower spreads, same tickers | None yet | Needs a scrape and a prompt or deploy-card change |
| D. More capital | Removes the floor | Fractional limit 23.9% PRIMARY, 26.6% SECONDARY. Outcome-blind adequacy: 39% of ladder-eligible candidates fit at $25,000, half at $34,600, 90% at $87,750 | The full book still fails at any capital, and the adequacy shares are a floor |
| E. Lower risk or accept the drawdown | `risk_per_trade_pct` down, or A3 accepted | 18.0% at 1.25% | The knob is a tighter stop the study never tested as an exit rule |

## What is unresolved

- **F2's A2 denominator.** The unconstrained baseline B2 keeps the one-contract
  floor, so F2 is compared with a book that still takes the picks it refuses.
  Whether that makes A2 too easy or too hard is not settled. The default is
  the registered clause, unchanged. The 2026-09-21 grading did not settle it
  either, and it now matters more: A2 is the clause F2 fails on the registered
  cap cell.
- **Running a new arm is not cheap.** `take_floor` and `downsize` are reachable
  only through the arms table. There is no flag or config key, and a
  non-default `--config` overwrites the default export and the site page.
- **The 2026-09-05 export is gone.** The flip reads as a selection effect: the
  same rows existed, and the walk took different ones as the book grew. It
  cannot be proved.
- **The scratch ladder disagrees with the report** at capitals whose dollar stop
  does not divide $1,000. At $35,000 the report prints 26.7% and the scratch
  script 29.4%. The two agree exactly where the stop divides evenly. The report
  is the authority.

## Literature the plan leans on

| Use in the plan | Source |
|---|---|
| A single max drawdown is a noisy order statistic (step 3) | Magdon-Ismail, Atiya, Pratap, Abu-Mostafa (2004), [J. Appl. Probab. 41](https://www.cs.rpi.edu/~magdon/ps/journal/drawdown_journal.pdf) |
| Many trials against one bar inflate a pass (step 6) | Bailey, Borwein, López de Prado, Zhu, [SSRN 2326253](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253); Harvey, Liu, Zhu (2016), [RFS 29(1)](https://www.nber.org/system/files/working_papers/w20592/w20592.pdf) |
| Integer lots bias a small account's realized risk upward (route A) | Optimal rounding under integer constraints, [arXiv:1501.00014](https://arxiv.org/pdf/1501.00014) |
| Drawdown-constrained and fractional-Kelly sizing — read, not used, because the budget is a stop here | Grossman and Zhou (1993), [Math. Finance 3(3)](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9965.1993.tb00044.x); Busseti, Ryu, Boyd (2016), [arXiv:1603.06183](https://arxiv.org/abs/1603.06183) |
| Volatility targeting — read, not used, for the same reason | Moreira and Muir (2017), [NBER w22208](https://www.nber.org/papers/w22208); Harvey et al. (2018), [SSRN 3175538](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538) |

## Next

[Item 5](next-steps.md#waiting-on-the-operator) stays open and still points
here. Four things remain.

**Step 2 — the operator's.** Fold the 2026-08-13 cap change and the 2026-08-14
verdict wording into the registration as `Resolved at build` tags, and decide
which cap cell the tracked config carries. Nothing below starts cleanly until
that is settled, because it fixes which cell the study's verdict describes.

**Step 4 — not done.** The deploy card still has no one-contract affordability
line. It is a code change on the production tier: a new column in
`RECOMMENDATION_COLUMNS`, a matching header on the live Recommendations tab,
and an entry in `docs/recommendations-reference.md`. An attention flag, never a
verdict.

**Phase 3 — still registration-gated, and its first question has changed.**
With the registered cell meeting every criterion on its registered basis, the
first question is whether any new arm is needed at all. Answer that before
writing step 6's pre-registration. The three guards below it are unchanged, and
the trial ledger still binds. More than 70 configurations have been scored
against the 25% bar on this one path: the 2026-09-21 run added the
registered cap cell and the four arm cells, and the 2026-09-22
Turtle-throttle exploratory added 18 more, all closed unregistered
([entry](current.md#2026-09-22--account_sim--a-turtle-drawdown-throttle-is-inert-at-25000-closed-unregistered)).

**Phase 4 — served.** The operator card is this file plus the
[2026-09-21 entry](current.md#2026-09-21--account_sim--the-registered-cap-cell-prints-feasible-the-run-on-record-does-not),
which together carry A3 on both bases, the drawdown table, the bootstrap band,
the four arm grades, the capital-adequacy curve and the corrected reading of
the risk knob. No separate card is owed.
