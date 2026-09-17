# Archive 21 — 2026-09-09: journal replay and the live-loop fold

_Status: historical (covers 2026-09-09). Conclusions stand as of 2026-09-17. Live record: [current.md](../current.md)._

Covers 2026-09-09. The July–August 2026 Flex fills were replayed offline
through the journal's own parse, reconcile and trade-writer steps: 107 rows
were appended, bringing the live walk-forward's mapped book to 55 rows over
20 signal dates, with no tier-A position closed yet, so Stage 2 (live P&L by
tier) still cannot be read. `scripts/live_loop/` was then retired: its rules
module, the one encoding of deployment-rules §1–§3 plus the structure
classifier and the play matcher, now lives in
`scripts/journal/lib/mapping.py` and takes the journal's own `Leg` objects
directly. Behaviour was checked unchanged two ways: every raw pull
re-reconciled before and after (159 events, 0 differ) and the test suite
(3527 passed, up from 3520).

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

