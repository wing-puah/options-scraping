# Archive 21 — 2026-09-09 to 09-17: `ladder_overlay` closed, the journal walk-forward, and the pricer mirror

_Status: historical (covers 2026-09-09 to 2026-09-17). Conclusions stand as of 2026-09-19. Live record: [current.md](../current.md)._

Covers 2026-09-09 to 2026-09-17. `ladder_overlay` closed NULL on both eras, so
nothing about selling a short call against a long-dated spread ships. The
journal became the live walk-forward's Stage 1 in earnest — July to mid-August
fills journalled, 55 mapped rows over 20 signal dates — and `scripts/live_loop/`
was folded into `scripts/journal/lib/mapping.py`. The last entry mirrors
production's B5 zero-bid re-mark into `bear_rewrap`'s reconstruction, taking
`hedge_structure`'s R2 to 1,320 / 1,321; the single remaining failure, HYG
2025-04-09, turned out to be an entry-DAY problem and is resolved in
[current.md](../current.md#2026-09-19-later-still--the-2025-04-09-re-price-and-the-two-mirror-drifts-it-exposed-hedge_structure-unblocked).

Sections run newest first, as they did in `current.md`.

---

## 2026-09-17 — bear_rewrap pricer — B5 zero-bid re-mark mirrored, R2 at 1,320 / 1,321

**The research pricer now marks a zero-bid leg the way production does, and
`hedge_structure`'s R2 drops from five failures to one.** Nothing ships. The one
remaining failure is not a B5 row: it is the HYG 2025-04-09 row already filed as
a fabricated credit, and it fails on its entry day. `hedge_structure` stays
blocked at R2 until that row is decided.

_Population: v4, the 2026-09-08 22:38 exports (598 results rows, 1,665 proxy
rows); `hedge_structure` R2 over 1,321 ticker-dates._

**The rule.** Production (`scripts/backtest/simulate.py::_zero_bid_mark`, the
B5 fix merged in 3e5c2dc) marks a leg quoted bid 0 at ask/2, or at 0 when
nothing is offered. It applies to the daily marks, to a carried-forward snap,
and to a zero-volume entry day. A row with no mid and no Latest is never
re-marked, because production never loads it.

**The implementation.** `bear_rewrap.py` imports `_zero_bid_mark` rather than
restating it, through one helper, `row_mark`. `leg_series`, `entry_price_of`,
`net_entry` and `net_marks` all go through it. Research importing production is
the existing direction; production still imports nothing from research.

**Why the basis follows the stored row.** B5 on every row broke rows that were
priced before the fold. No column records which rule a row was priced under:
`cost_basis` is blank on all rows and the cost columns are blank on every proxy
row. The write time does. Rows stamped at or after the merge, 2026-09-08
15:05:25, get B5. Older rows keep the plain mark. On this export no row was
written between 10:31:15 and 15:21:14 that day, so the cut decides no real row.

| R2 on 1,321 ticker-dates | Pass | Fail |
|---|---|---|
| Old mirror, no B5 | 1,316 | 5 (4 mark, 1 entry) |
| B5 applied to every row | 1,143 | 178 (177 pre-fold rows now fail) |
| B5 on rows written after the merge | 1,320 | 1 (HYG entry) |

**Variants share the baseline's basis.** A study that prices a substitute,
overlay or financed leg against a stored row prices it on that row's basis
(`bear_rewrap.basis_of`; `financed_spread` and `ladder_overlay` wrap their row
loops). A first run without this marked substitutes with B5 against pre-fold
baselines. It moved `bear_rewrap`'s `long_diag` dR from +0.154 to +0.119 and
its CI across zero. That move came from mixing two mark rules in one comparison,
not from the structure, so it was discarded. A price with no stored row behind it,
such as a `hedge_structure` sleeve, takes the production rule.

**The residual failure.** Production filled HYG on 04-14, the long leg's first
bar, and carried the short 72P's 04-10 snap (bid 0 / ask 2.68, re-marked to
1.34). The net was −0.37 on a bear put spread. `entry_date_for` needs a bar on
every leg, so it picks 04-16 and gets 0.47. On 04-14 the mirror reproduces −0.37
and 35 / 35 marks. Mirroring production's entry day would pass R2 by admitting
the fabricated credit, so it was not done.

**What the re-runs moved.** Each study's verdicts are unchanged. The only
movement is the rows the fixed gate now admits.

| Study | Rows admitted before → after | Verdict lines |
|---|---|---|
| `bear_rewrap` | 480 → 481 (XLF 2025-04-09) | unchanged; `long_diag` dR +0.154 → +0.153, CI [+0.025, +0.281] |
| `financed_spread` | 916 → 918 | unchanged; F0 dR −0.155 → −0.140 |
| `ladder_overlay` | 446 → 447 cores | unchanged; G1 and G1b PASS |
| `hedge_structure` | R2 1,316 → 1,320 | still R2 FAIL; H0 not printed |

**Unresolved.**
- HYG 2025-04-09 blocks `hedge_structure`. The default is to leave R2
  all-or-nothing and the row as stored. Re-pricing it after the §2.11 carried-snap
  fix would clear R2. Choosing that is the operator's call.
- `hedge_structure`'s checkpoint store (`synth_results.csv`) is keyed on the
  cache, not on the mark rule. Rows it built before today used the plain mark.
  When R2 clears, run the study with `--redo` so no sleeve mixes the two rules.
- `lib/hedge_instrument.py` restates the plain mark for the hedge puts, and its
  pre-registration names that rule. It prices no stored row and was left alone.

**Queue.** [`next-steps.md` §2.11](../next-steps.md#s2-11): the B5-mirror row is
resolved, and the HYG row now also names the R2 block.

---

## 2026-09-09 — journal — the July to mid-August fills are journalled; the live walk-forward has 55 mapped rows over 20 signal dates

**The journal is the live walk-forward's Stage 1 collector, and it now covers
every session since analysis coverage began.** Nothing ships. The 26 sessions
from 2026-07-01 to 2026-08-13 were never journalled, because the daily loop
started on 2026-08-14. They were replayed offline today from the Flex exports in
`portfolio/input/` through the journal's own parse, reconcile and trade-writer
steps, and 107 rows were appended to `journal/trades.csv` and the TradeJournal
tab. Dedup is on the broker execution id, so re-running appends nothing.

_Sources: `trades_2025.csv`, `trades_2026.csv`, `trades_ytd_fetched.csv`, netted
together. Sessions before 2026-08-11 matched against `v3_AnalysisClaude` only;
2026-08-11 onward against `AnalysisClaude`. No greek enrichment, so
`delta_source` is unavailable on the replayed rows and tier §3 is unverified on 3
of them._

**Why the split by tab.** The v4 tab holds re-runs back to 2024 that were produced
after August. A July fill matched against one of those would be matched to an
analysis the operator never saw. The v3 tab is what was live until 2026-08-10.

**The strike and expiry point.** The operator often opens a different strike or
expiry from the emitted play. The matcher already handles that: a same-family
structure with other strikes is STRUCTURE, a naked leg where a spread was emitted
is SUBSTITUTED, and expiry is not part of the match at all. Strike differences
are recorded in `notes`, never used to reject a match.

| Journal after the replay | Count |
|---|---|
| Rows | 145 over 34 sessions, 2026-07-01 to 2026-09-04 |
| Mapped rows (EXACT, STRUCTURE, CORE, SUBSTITUTED) | 55 over 20 signal dates |
| Mapped opens / closes | 32 / 22 |
| NONE | 67, of which 12 predate the first v3 analysis date 2026-07-08 |
| OVERLAY | 23 |

| Tier | Mapped rows | Opens | Closed with realized P&L | Realized $ |
|---|---|---|---|---|
| A | 3 | 3 | 0 | 0 |
| B | 21 | 11 | 9 | +626 |
| C | 29 | 16 | 13 | +388 |
| VETO | 2 | 2 | 0 | 0 |

**This decides nothing.** No tier-A position has closed, so the A > B > C question
cannot be posed. Stage 2, the live-vs-tier P&L reading, is not written; the old
stage1 caveat put its gate at 30 to 50 closed positions and the mapped book has
22 closes. The `operator_read` floor in §2.5 of 25 dates is at 20.

**What stays unmapped.** Most of the 67 NONE rows are short-dated MU options,
straddle-shaped mixed C/P verticals, and closes of positions opened before
coverage. None of those are the analysis's plays. One label reads oddly: a CRWV
short put is labelled `(overlay)` by structure but matched SUBSTITUTED, and the
two vocabularies should agree.

**Queue.** [`next-steps.md` §2.5](../next-steps.md#s2-5) loses its "no recorded
movement" warning and gains the census. The replay script is a one-off in the
session scratchpad, not in the repo; if a second Flex gap appears, a `backfill`
command on `scripts.journal` is the right home for it.

## 2026-09-09 — journal — `scripts/live_loop/` is gone; its rules module is `scripts/journal/lib/mapping.py` and speaks the journal's own types

The live-loop package is deleted. Its rules module, the one encoding of
[deployment-rules §1–§3](../../docs/deployment-rules.md#s1) plus the structure
classifier and the play matcher, now lives inside the journal at
`scripts/journal/lib/mapping.py`. `stage1_map_fills.py` is retired: its data
source was a hand-pasted IBKR snapshot, the newest is dated 2026-08-12, and the
daily journal reads Flex with strike and expiry on every fill, so the reconcile
step already does what the fortnightly script did. The two snapshots and their
reports stay under `backtests/live_loop/` as protected data.

The move also removed the adapter layer. Mapping was written against the
snapshot script's hand-built dict shape, so the reconcile step, the book
grouper and the relabel diagnostic each carried code whose only job was to
dress the journal's `Leg` objects up as that shape. Mapping now takes `Leg`s
directly and the adapters are deleted. The closing-fill sign inversion, the
P1 fix from the robustness review, is a named function
`mapping.position_legs(legs, closing=True)` instead of a side effect inside an
adapter. Two dead branches went with it: the classifier's "identity could not
be pinned" path, unreachable when every leg carries a contract id, and the
unused `leg_desc` helper.

Behaviour is unchanged, checked two ways:

| Check | Result |
|---|---|
| Every raw pull in `journal/raw/` re-reconciled before and after, journal row fields keyed on `source_ref` | 159 events compared, 0 differ |
| Test suite | 3527 passed (3520 before; the seven new tests pin `position_legs`, `net_price` and classifier labels the old fixtures never reached) |

The research tier's live-select arm still imports `ladder_tier()`; it is the
one sanctioned research-to-production import, now stated as "the arm imports
from `scripts/journal/`". The evaluation half of the walk-forward, live P&L
by tier and taken versus not taken, was never in the deleted script in a
usable form and is still not written. It belongs to the f4 study queued in
[next-steps §2.5](../next-steps.md#s2-5), after its registration.

Provenance: working tree on main after commit 2226888, uncommitted;
`make check-doc-links` 0 broken.

## 2026-09-16 — ladder_overlay — nothing ships; no ladder or naked-put cell beats the plain spread on v4 or v3

Wrapping a bull call spread in a rolled short-call ladder does not beat running
the spread to the shipped [§5](../../docs/deployment-rules.md#s5) exits, and
neither naked-put substitute does either. All ten graded cells print `NULL` on
v4, and on v3 the six powered cells print `NULL` and the four sell-at-entry
cells are `UNDERPOWERED`
([record](../study-results/f3_structure/ladder_overlay.md)). The one confidence
interval clear of zero is on the wrong side: selling the call on the entry day
and rolling it costs about a quarter of an R against the plain spread.

_Era v4 · exports 2026-09-08 22:38 · 598 real / 1,665 proxy rows · 447
bull-call cores over 165 dates · report
`backtests/study_output/ladder_overlay-latest.txt` (run 2026-09-10 22:17, sha
8aed569, after the 11,551-contract scrape finished at 22:15 and the cache
snapshot was pushed at 22:16) · v3 companion run 2026-09-16, 242 cores over 89
dates, filed as `ladder_overlay-v3-2026-09-16.txt` · review 2026-09-10: two
analysts and the validator agreed on every number and every verdict._

**In production.** Nothing changes. The §5 debit exits stay and no overlay
enters the deploy card. The
[pre-registration](../pre-registrations/f3_structure/ladder_overlay.md) allowed at
most a CANDIDATE queued for confirmation, and none appeared.

**Evidence.** [ΔR](../glossary.md#paired-ci) is the cell's R minus the plain
spread's R on the same row, with a date-clustered
[CI95](../glossary.md#ci95-date-clustered-bootstrap). Criteria are the
registration's eight; cell labels are in
[`arm-index.md`](../arm-index.md#ladder_overlay).

| Cell (v4) | What it does | ΔR | CI95 | Dates | Criteria failed | Verdict |
|---|---|---|---|---|---|---|
| L-F4 | one call sold at entry, never rolled | −0.225 | [−0.477, +0.001] | 71 | 1, 2, 3, 4, 5, 7, 8 | NULL |
| L-T0 | sold at entry, rolled each slot | −0.255 | [−0.528, −0.011] | 71 | 1, 2, 3, 4, 5, 7, 8 | NULL |
| L-T0-TEF | L-T0 with no profit target | −0.310 | [−0.591, −0.053] | 71 | 1, 2, 3, 4, 5, 7, 8 | NULL |
| L-GAP | sold after a gap-up, rolled | +0.078 | [−0.012, +0.168] | 122 | 1, 4, 7 | NULL |
| L-RUN | sold after a sustained rise, rolled | +0.045 | [−0.048, +0.135] | 121 | 1, 4, 7 | NULL |
| L-GAP-TEF | L-GAP with no profit target | +0.102 | [−0.038, +0.234] | 122 | 1, 4, 7 | NULL |
| L-RUN-TEF | L-RUN with no profit target | +0.071 | [−0.074, +0.203] | 121 | 1, 4, 7 | NULL |
| N-CORE | short put at the long strike, in place of the core | −0.018 | [−0.181, +0.144] | 165 | 1, 2, 3, 4, 5, 7, 8 | NULL |
| N-ROLL | rolled short-dated put, in place of the core | −0.007 | [−0.157, +0.144] | 154 | 1, 2, 3, 4, 5, 7, 8 | NULL |

| Cell (v3) | ΔR | CI95 | Dates | Verdict |
|---|---|---|---|---|
| L-F4, L-T0, L-T0-TEF | — | — | 33 (41 rows) | UNDERPOWERED |
| L-GAP | −0.042 | [−0.245, +0.099] | 62 | NULL |
| L-RUN | −0.065 | [−0.199, +0.044] | 58 | NULL |
| L-GAP-TEF | +0.090 | [−0.141, +0.273] | 62 | NULL |
| L-RUN-TEF | +0.047 | [−0.122, +0.201] | 58 | NULL |
| N-CORE | +0.008 | [−0.228, +0.253] | 89 | NULL |
| N-ROLL | −0.274 | [−0.478, −0.073] | 69 | NULL |

**What the two eras agree on.** Selling the call on the entry day hurts. On v4
the three sell-at-entry cells are negative with the CI clear of zero for two of
them; on v3 the same cells are too thin to read. Waiting for a gap-up or a run
before selling is the only pattern that is positive on v4, and those four cells
clear the leave-one-date-out, window, pricing-tier and breach-stress criteria.
They still fail three: the CI includes zero, 2026 is a negative year, and
their P&L is positively correlated with the deployed book (E3 between +0.16 and
+0.38), which is the re-wrap pattern `financed_spread` printed before. A larger
book that pushed the CI clear of zero would therefore print RE-WRAP, not
CANDIDATE, and RE-WRAP closes the thread. On v3 the same four cells split two
positive, two negative, all inside their intervals. The rolled naked put is the
one cell with a CI wholly below zero on v3 and it is flat on v4.

**Costs.** The book runs at zero commission and zero slippage. The report's
sensitivity line re-costs every cell at $0.65 a contract and half the quoted
spread; it turns N-ROLL's 2,062 opens and closes from +$69k gross to −$15k net,
and takes the trigger cells down by a fifth to a quarter. It is printed with n
and changes no verdict.

**Registration gaps, folded in as build rulings.** The review found three
places where the report resolved something the registration did not say.
Each was decided in code on 2026-09-10 before any cell had a verdict, so each
is now in the registration tagged `Resolved at build`.

- `NULL` in the registration meant "clears the CI but fails stability". The
  code's `verdict_of()` makes NULL the total default: it also covers a CI that
  includes zero or lies below it, a criterion 5 or 6 failure, an E3 that is
  NOT EVALUABLE, and the corner where 1–6 pass and both 7 and 8 fail. There is
  no CONTRARY token, so a cell that loses with a clear CI prints NULL and the
  write-up says so in words, as above.
- E1/E2 are registered "at the common entry day". A trigger cell holds no
  tranche on that day, so the report gates its geometry at the first sale day
  and prints both columns. Naked-put cells replace the core, so their direction
  is printed and not gated.
- G1b compares "the shared rows". The report names what is not shared and lists
  each separately: rows where F4 had no leg (353), rows F4 excluded and the
  campaign sold (7), rows the campaign opened after entry (4), and 8 pre-fill
  grid days. The 82 rows both sides priced match to $0.0000 a day.

**Two review questions, answered from the code.** The scrape's target set grew
from the registered 11,502 to 11,551 because `ladder_targets.py` reads the
ticker's strike ladder and expiry list off the option cache, so targets appear
as the scrape lands; every graded cell was still AWAITING SCRAPE until the
manifest's last write, so no target was added after an outcome was seen. The
criterion-5 labels `real` and `tweak` are the export file a row came from,
which is the same thing as its pricing tier in this book: every
`BacktestResults` row is real-priced and `bs` proxy rows are dropped before the
study runs.

**Caveats.** `S-D30` (the 0.30-delta ladder) is underpowered on both eras, so
the delta target was tested at 0.20 only. `S-DTE60` is underpowered too, so
the ≥60-DTE question stays with the
[long-dated blind spot](../next-steps.md#s2). The 2026 column is the same
correlated backfill window every other study reads; nothing here has seen a
genuinely new date.

**Next.** [`next-steps.md` §2.13](../next-steps.md#s2-13) closes. No new item.
The ladder thread re-opens only on genuinely new dates, and only if the
trigger cells' re-wrap correlation has moved.

Provenance: working tree on main after commit 2d72047, uncommitted; the v3
report is filed under its own name because `run.py` gives both eras one
`-latest.txt`, and the v4 report was restored as the current one.
