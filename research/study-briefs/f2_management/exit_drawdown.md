# exit_drawdown — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f2_management/exit_drawdown.md); where the two differ, the registration wins.
> Latest outcome: `ARM U/a` and `ARM U/b` `REACTIVE-AGAIN`; `ARM O/vol` `NULL`; `ARM D` `SECONDARY-NULL`; `ARM W`, `ARM O/oi` and `ARM P` `UNDERPOWERED` — 2026-09-28 · [record](../../study-results/f2_management/exit_drawdown.md).
> Nothing else here is a result.

## The question

Can an exit rule, chosen without look-ahead, cut the account's
[mark-to-market](../../glossary.md#mark-to-market-basis) drawdown without giving
back the book's edge? The operator asked about max drawdown, not timing. No
study had judged an exit rule on the marked account curve. No exit setting in
this repo had ever been chosen out of sample.

## What it compares

Each arm changes only how an open position exits. `exit_drawdown ARM D` is the
exception: it changes the size of a new position. Every arm is paired against
the shipped exit profile ([§5](../../../docs/deployment-rules.md#s5)), never a
clean `DEBIT_PROD`. Credit rows keep `CREDIT_PROD` in every arm.

| Object | What it does | Kind |
|---|---|---|
| [exit_drawdown ARM W](../../arm-index.md#exit_drawdown-arm-w) | Re-picks `pt`/`sl`/`tef` from a 36-point grid on training dates. [PROD](../../glossary.md#prod) is one grid point. The honesty baseline: what out-of-sample selection of the shipped knobs earns | exit arm |
| [exit_drawdown ARM U/a](../../arm-index.md#exit_drawdown-arm-u) | Exits debit verticals when the underlying closes ≥ k · ATR14 against the position, from the entry close; adds the stop to `sl .75` | exit arm |
| exit_drawdown ARM U/b | The same stop, replacing `sl` | exit arm |
| [exit_drawdown ARM O/oi](../../arm-index.md#exit_drawdown-arm-o) | Exits debit verticals when the long leg's lagged open interest falls to ≤ (1 − X) · `OI_max` | exit arm |
| exit_drawdown ARM O/vol | Exits when leg volume is ≥ 3× its post-entry median and the mark closed against the position | exit arm |
| [exit_drawdown ARM P/half](../../arm-index.md#exit_drawdown-arm-p) | Half the contracts exit at `pt .90`; the other half run with `pt=None`. Nothing to fit | exit arm |
| [exit_drawdown ARM D/throttle](../../arm-index.md#exit_drawdown-arm-d) | New positions size at half the risk budget once marked equity falls d below its running peak, until it recovers to within d/2 of the peak | SECONDARY (sizing, not exit) |

The fitted values are `k ∈ {1.5, 2.0, 3.0}`, `X ∈ {0.25, 0.40}` and
`d ∈ {0.05, 0.10}`. ATR14 is frozen at entry.

## How it is judged

**Measure.** Two co-primaries: the marked max drawdown, in dollars, of the
stitched out-of-sample book, and the paired [ΔR](../../glossary.md#r) by date
versus the shipped profile.

**Population.** The v4 era, `account_sim`'s
[dense-episode](../../glossary.md#primary-dense-episodes-vs-secondary-full-book)
population, `real` and `strike_expiry_tweak` pricing tiers, test dates only after
burn-in. The study also runs v3 and the `all` population, but neither carries a
verdict.

**Fitting.** Each exit-arm threshold is chosen per
[walk-forward](../../glossary.md#purged-walk-forward--embargo) block on training
dates (15-date blocks, 120-day embargo, at least 40 training dates). A prefilter
keeps configurations whose training mean R is within 0.02 of the best. Of those, the configuration
with the smallest training drawdown wins. `ARM D`'s `d` is the exception: it
collapses to the earliest block's choice for the whole book.

**Gates.** A cell is one arm × variant × era × population.

- `G0`: refuses a cell with < 25 affected dates or < 60 affected rows, which
  then prints `UNDERPOWERED`.
- `G-FORK`: refuses the run if any overlay, with its rule off, fails to reproduce
  `harness.replay` exactly on all rows in both eras.
- `G-CAL`: refuses the run if `account_sim`'s gates G2–G5 fail on their default
  path.
- `G-MTM`: refuses the run if the marked value at exit and the overlay's dollars
  disagree beyond `TOL_DOLLARS`.
- `G1`: refuses the run if shifting bars, OI or volume one session forward
  changes no exit, or moves an exit earlier.
- `G-COV`: requires coverage and exclusion counts to print before any
  conditional number.

"Affected" means the arm changed that row's exit. For `ARM D`, it means a row
entered at the halved budget. `G1` has per-variant build rulings that are too
detailed to summarise here; see [Gates](../../pre-registrations/f2_management/exit_drawdown.md#gates).

**Bar.** A cell must clear every clause on the PRIMARY, out-of-sample book.

1. Max drawdown improves by ≥ 15% versus the shipped profile, with the block-bootstrap CI excluding zero.
2. The date-clustered paired ΔR CI has a lower bound > −0.02.
3. The improvement is same-signed in both halves of the window and in ≥ 2 of the 3 years present.
4. Both pricing tiers (`real`, `strike_expiry_tweak`) are same-signed.
5. SECONDARY v3 is not opposite-signed.
6. The cell has ≥ 25 affected dates.
7. Fewer than 50% of the arm's exits are followed by the mark recovering past the exit.

`ARM D` is judged on clauses 1–6 only. A half or tier with no sign fails its
clause; a v3 cell with no sign passes clause 5. See
[Bar for a candidate](../../pre-registrations/f2_management/exit_drawdown.md#bar-for-a-candidate)
for these edge cases.

## Possible verdicts

The tokens apply in this order, and the first match wins. A failed machinery gate
stops the run and prints no token for any arm.

| Token | What it means |
|---|---|
| `UNDERPOWERED` | Too few affected dates or rows. Nothing is concluded |
| `CONTRARY` | The rule hurts: drawdown worsens by ≥ 15% (CI excludes zero), or the ΔR CI lies entirely at or below −0.02 |
| `REACTIVE-AGAIN` | ΔR holds up, but ≥ 50% of exits sold positions that then recovered |
| `CANDIDATE-FOR-INDEPENDENT-WINDOW` | Clears all seven clauses. It joins a queue; it does not ship |
| `NULL` | Every other powered cell |
| `PROD-ROBUST` | `ARM W` only: its walk-forward pick was `NULL` or `CONTRARY`, so no selected configuration beat PROD |

`ARM D` prints the same tokens with a `SECONDARY-` prefix. It never prints
`SECONDARY-REACTIVE-AGAIN`.

## What could ship

Nothing ships from this run. A `CANDIDATE-FOR-INDEPENDENT-WINDOW` queues a check
on the live 2026-08/09 dates, once their options expire and are priced. Only then
may it be proposed for the deployment rules. `PROD-ROBUST` keeps the shipped
profile. `ARM D` can only queue a separate f4 registration.

## What this study cannot tell you

- Whether a hedge helps. It opens, sizes and times no hedge sleeve.
- Anything new about exit families already settled, such as trailing stops or
  `staged_exit`. It re-tests none of them.
- Whether a credit exit works. Credit rows keep `CREDIT_PROD` throughout.
- Whether a sizing rule should ship. `ARM D` is a comparator only.
- Anything from the v3 era or the `all` population on its own. Neither carries a
  verdict.
