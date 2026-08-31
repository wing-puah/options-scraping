# OpenBook column reference

What every column and every flag of the **OpenBook** tab means.

The tab lives in `TRADE_JOURNAL_SPREADSHEET_ID` — the same workbook as
**TradeJournal** and **Recommendations**, because the three describe one loop:
what was *recommended*, what was *traded*, and what is *held*. It is written by
`scripts/journal/s05b_bookwriter.py` on every `python3 -m scripts.journal` run,
and mirrored to `journal/open_book.csv` (gitignored, written first, and the copy
that survives a Sheets outage).

Schema: `OPEN_BOOK_COLUMNS` in `scripts/journal/config.py`, 27 columns, ordered
"what do I need to know about this position" nearest first — the row's own
status and exposure, then what the cap binds on, then mark detail, then
identity/provenance last. A fact about the whole BOOK rather than one
position — the net cap block, the book counts, NetLiquidation, whether the
book was reconstructed, the pull's notes — is not a column here at all; it
lives in `journal/reports/<date>.md` and the generated page, and reaches this
tab only as a flag on the rows it concerns (`NET_CAP_NEAR`, `NET_CAP_BREACH`,
`CAPS_NOT_EVALUABLE`, `SPLIT_EXPIRY`, `MIXED_ENTRY_DATES`).

Columns are **append-at-end only** for growth — a new column means the tab
header must gain it too, or new rows write an unlabelled trailing cell. A
REORDER or a DROP is different: it migrates `journal/open_book.csv` by column
name (dropped columns discarded, new ones written blank, every row's
`book_id` recomputed under the new schema) but does not touch the Sheets tab —
if the tab's row-1 header is neither the current schema nor a strict prefix of
it, the writer refuses to append (reported as `sheets_error`, rows still safe
in the CSV) until the operator renames the old tab (e.g. `v1_OpenBook`) so the
next run recreates it, the repo's existing `vN_` convention for a shape
change.

---

## How to read it

**One row = one open position, as marked on one session.** Positions are the
(underlying, expiry) groups `scripts/journal/lib/book.py` reassembles from the
broker's flat leg list, so a vertical is one row and a calendar/diagonal is two
(flagged `SPLIT_EXPIRY`).

**The tab is append-only and generational, per POSITION.** Nothing is ever
overwritten. Marking the same position twice with the same numbers appends
nothing; a genuinely re-marked position appends its own row at
`generation = n+1` — and only that position, since `book_id`'s hash now covers
just this row's own columns rather than book-level totals that were repeated
on every row. **To see today's book, take the largest `as_of_date`, then the
largest `generation`, per position (per `conid_key`).**

**Scanning it:** sort or filter on `status`.

| `status` | Means |
|---|---|
| `ATTENTION` | Something is wrong or unknown NOW — an overdue exit, an unpriced position, a breached cap. |
| `WATCH` | It will be soon, or the picture is incomplete. |
| `OK` | No flag above INFO. |

**Flags are attention, never verdicts.** Nothing downstream reads one: the caps
still bind in `s03_risk.py`, the §5 deadline is still computed in
`lib/exit_rules.py`, and the ladder still ranks in `s06_recommend.py`. The
thresholds (`EXIT_DUE_SOON_DAYS`, `EXPIRING_SOON_DTE`, `CAP_NEAR_UTILISATION` in
`config.py`) change what gets *noticed*, never what is true — which is why they
are round numbers with nothing fitted behind them, unlike anything in
`docs/deployment-rules.md`.

**Never total `delta_notional` without filtering on `priced`.** A position whose
delta the feed did not return is not worth zero delta; it is worth an unknown
delta, is written with BLANK delta cells, and is excluded from every total on
its own row — `priced=False` is the one-cell version of "this row's numbers
are not in the total".

---

## When, and what is wrong

| Column | Meaning |
|---|---|
| `as_of_date` | The session the book is marked AT — not the day the row was written. A replay stamps the replayed session. |
| `status` | `ATTENTION` \| `WATCH` \| `OK` — the worst severity among `flags`. INFO flags never move it. |
| `flags` | `"; "`-joined tokens, worst-severity first. Defined below. Empty = nothing to report. |

## The position: exposure and deadline first

| Column | Meaning |
|---|---|
| `ticker` | Underlying symbol. |
| `structure` | Canonical structure name from the shared classifier (`mapping.classify_structure`); `unclassified` when it could not name the group. |
| `delta_notional` | `delta × 100 × contracts × underlying_price`, signed — the same formula `account_sim` uses, so a live book and a simulated one are comparable. BLANK when unpriced, never 0. |
| `pct_net_liq` | `delta_notional / net_liq`, as a decimal fraction. |
| `exit_by` | The §5 time-exit DEADLINE (`entry + fraction × (expiry − entry)`, `lib/exit_rules.py`). Debits only — credits carry no time exit — and blank whenever any input is unknown. Display-only. |
| `days_to_exit_by` | `exit_by − as_of_date`, signed. Negative = overdue. |
| `expiry` | The group's expiry. Blank if the legs disagree — reported as unambiguous or not at all. |
| `dte` | Calendar days from `as_of_date` to `expiry`. Negative = still in the book past expiry. |

## What the cap binds on: the ticker's signed total

The per-position cap binds on a **ticker's signed total**, not on one row — a
financing short leg at another expiry is a separate row but the same directional
risk. Both caps come from `config/account-sim.yml` as fractions of equity and
bind against live NetLiquidation.

| Column | Meaning |
|---|---|
| `ticker_delta_notional` | The TICKER's signed delta-notional across every priced position — the unit the per-position cap binds on. |
| `ticker_cap_utilisation` | `\|ticker_delta_notional\|` divided by the per-position cap (`caps.per_position × net_liq`, from `config/account-sim.yml`), as a decimal fraction. >1 is a breach. |

## The detail behind the mark

| Column | Meaning |
|---|---|
| `contracts` | Size in STRUCTURES, not legs — the smallest \|qty\| across legs. |
| `legs` | `TICKER:YYYY-MM-DD:STRIKE:C +N`, the repo's canonical grammar (same as `TradeJournal.legs`; parseable by `scripts/backtest/legs.py`). |
| `entry_date` | Earliest opening fill across the legs, when provable from an export we hold. Blank = unknown, never assumed. Legs opened on different dates raise `MIXED_ENTRY_DATES`; the §5 clock starts at the earliest. |
| `position_delta` | Net delta across legs, per contract. All-or-nothing: one leg without a delta leaves the whole position unpriced. |
| `underlying_price` | Spot used to value the exposure. |
| `short_leg_delta` | \|delta\| of the binding short leg (the largest, when several are short) — the input to `deployment-rules.md` §3. |
| `iv` | Implied vol from the first leg that carries one. |
| `priced` | FALSE = this position entered NO total on this row. Filter on it before summing anything. |
| `delta_source` | Where the delta came from: `barchart` (EOD history, the Flex path), `ibkr` (historical Client Portal model greeks), `unavailable`, or `a+b` when the legs disagree. |

## Identity and provenance, last

| Column | Meaning |
|---|---|
| `book_id` | `as_of_date\|ticker\|expiry\|structure\|<12 hex>` — readable at the front, a hash of the row's own 27-column content at the back (identity and wall clock excluded: `book_id`, `generation`, `snapshot_utc`). The dedup key: an unchanged re-mark of this position collides with itself and is dropped before the append. |
| `generation` | Nth distinct mark of this position on this `as_of_date`. Excluded from the hash, so it can never make a duplicate look new. |
| `conid_key` | Sorted leg conids — the stable position identity across marks, and the same key `JOURNAL_COLUMNS`-shaped rows are risk-joined on. |
| `book_source` | Basename of the broker pull this book was marked from. Blank on a dry run. |
| `snapshot_utc` | Wall clock of the write. Excluded from the hash — a re-run at a different hour is not a new snapshot. |

---

## Flags

Severity is declared in `BOOK_FLAG_SEVERITY` (`scripts/journal/config.py`).

### ATTENTION — wrong or unknown now

| Flag | Raised when |
|---|---|
| `EXPIRED` | `dte < 0` — the contract is past expiry and still in the book. |
| `EXIT_OVERDUE` | `exit_by` is before `as_of_date`. §5 states a deadline: exit on or before it. |
| `UNPRICED_NO_DELTA` | No delta for at least one leg — the position is excluded from every exposure total. |
| `UNPRICED_NO_SPOT` | The delta is known but there is no underlying price, so it cannot be valued. |
| `TICKER_CAP_BREACH` | `ticker_cap_utilisation > 1`. |
| `NET_CAP_BREACH` | The book's net utilisation exceeds 1. A fact about the BOOK, so it lands on every row of the snapshot. |

### WATCH — soon, or incomplete

| Flag | Raised when |
|---|---|
| `EXIT_DUE_SOON` | `0 ≤ days_to_exit_by ≤ EXIT_DUE_SOON_DAYS` (5). |
| `EXPIRING_SOON` | `0 ≤ dte ≤ EXPIRING_SOON_DTE` (7). |
| `TICKER_CAP_NEAR` | `ticker_cap_utilisation ≥ CAP_NEAR_UTILISATION` (0.80) but not yet a breach. |
| `NET_CAP_NEAR` | Same threshold, on the net cap. |
| `CAPS_NOT_EVALUABLE` | No NetLiquidation, so neither cap could be evaluated — the dollar totals carry no cap context. |
| `MIXED_ENTRY_DATES` | The legs were opened on different dates; `exit_by` uses the earliest. |
| `UNCLASSIFIED_STRUCTURE` | The classifier could not name the leg group, so its tier and side are unknown. |

### INFO — worth knowing, not a problem

These never move `status`.

| Flag | Raised when |
|---|---|
| `SPLIT_EXPIRY` | The ticker holds legs in more than one expiry, so a calendar/diagonal is shown as two rows. Presentational only: delta-notional is additive and the cap is evaluated per ticker, so the split changes neither a total nor a verdict. |
| `EXIT_DATE_UNKNOWN` | A debit whose §5 deadline could not be computed while the rule is enabled — the entry date is not provable from any export we hold. A gap in the record, not a fact about the position. |

---

## Related

- `docs/architecture.md` §Daily trade journal — how the step fits the pipeline.
- `docs/recommendations-reference.md` — the Recommendations tab's column dictionary.
- `docs/deployment-rules.md` — §3 (delta geometry) and §5 (time exit), the rules
  `short_leg_delta` and `exit_by` are read against.
