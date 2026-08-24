## concurrency_correlation

_Registered 2026-08-22._

**Question.** Does the SIZE and INTERNAL SIMILARITY of the open book degrade
per-position outcome, independently of which plays were selected? Two effects,
deliberately separated:

- **Concurrency** — does a position opened while N others are already open do
  worse as N rises?
- **Correlation** — does a position opened alongside others pointing the same
  way (same direction, same sector, same underlying) do worse than one opened
  into an unlike book?

This is an EXPOSURE study, not a selection study. The ladder is FROZEN
(`protocol.top_k_per_day(book, ladder_rank, k=3, ladder_eligible)` — the
shipped operator card) and the exits are FROZEN (the shipped profiles). **No
column may be added to selection, no exit knob may be moved, and no tier rule
may be touched.** The only new machinery is a book-state annotation computed at
each position's ENTRY session.

**Why this study exists.** `DEPLOY_BUDGET`/`max_positions_per_day = 3` caps the
FLOW of new positions per day. Nothing anywhere caps the STOCK of open ones,
and no study has ever measured the stock against outcome. `account_sim`
computes `n_open` per session and prints it in the UTILISATION tables; no
report joins it to any outcome table. No same-ticker, same-sector or
same-direction clustering measure exists anywhere in the repo — every recorded
"correlation" figure is sleeve-vs-book, never two concurrently held plays
against each other.

---

### Plan-time observations, disclosed

Measured on 2026-08-22 while designing this study. The arms and grids below are
informed by them and that is stated rather than hidden. Nothing here is a
result; each line names its population.

**Concurrency census (never yet joined to outcome).** `account_sim`
plan-time record, v3, 220 picks / 90 dates: concurrent open positions
median 8, p90 29, max 48. v4 UTILISATION tables: monthly `open max` peaks at
21 (frozen) and 23 (compounding).

**The live book grew ~6× without a rule firing.** Reconstructed from the
2026-08-12 broker snapshot's fill stream: mean open LEGS by week ending
2026-05-17 → 2026-08-16 ran 3.0, 2.0, 2.6, 4.6, 5.6, 10.1, 9.3, **15.7**, 13.0,
13.9, **18.7**. Opening orders per week stepped rather than drifted — 2, 2, 3,
3, 3, 6, 2, 6, then **19**, 14, 7 — breaking the week of 2026-07-27.
Corroborated independently: live_loop snapshots 17 legs (07-22) → 19 (08-12);
Flex pulls 19 legs (08-15) → 20 (08-18).

**The operator's discretionary book shows monotone cadence dilution.**
`research/archive/08`, 468 closed trades 2025-02-03 → 2026-07-24, pre-engine
and human-executed: P&L per trade by same-day trade count 1/day +$119 (n=67) ·
2–3/day +$25 (n=160) · 4–6/day +$9 (n=109) · 7+/day −$18 (n=132), **win rate
flat at 51–59% across all four**. That file's own caveat stands and is
inherited here: it is a portrait of hand trading, NOT a test of the engine,
and it is directional rather than evidential. It is disclosed because it
motivated this study.

**The book is long-only by construction.** v4 deployed book: `present 168/168
positive 168 NEGATIVE 0 zero 0`, `net avg == gross avg` on every session,
`net-SHORT sessions 0`. Asserted from signs; never measured as covariance —
which is the gap ARM K exists to close.

**Rank depth inside the survivor set is FLAT on both eras** (so this study
must not be read as a top-N study). Deployed-order replay of Tier A/B
survivors, mean R by within-day rank:

| rank | v3 (795 rows / 118 dates) | v4 (517 rows / 78 dates) |
|---|---|---|
| 1 | +0.178 | +0.155 |
| 2 | +0.527 | +0.372 |
| 3 | +0.445 | +0.269 |
| 4–5 | +0.281 | +0.263 |
| 6+ | +0.323 | +0.257 |

**Two v3 day-level cuts that do NOT reproduce on v4, disclosed as dead ends so
this study does not re-find them and call them new.** Deployed top-3, mean R:

| cut | v3 | v4 |
|---|---|---|
| day had Tier A supply | +0.475 | +0.247 |
| Tier-B-only day | +0.182 | +0.257 |
| model BULL + L-VOL | −0.050 | +0.224 |
| all other regimes | +0.465 | +0.299 |

Tier A share collapsed across the bump (v3 131 A / 166 B; v4 58 A / 172 B), so
Tier-B-only days went from 24% of dates to 62%. This is `v4_bridge`'s recorded
`LADDER UNVALIDATED ON v4 — ladder tier mix shifted, chi2 p = 0.0000`. Neither
cut is an arm of this study.

**Prior tests of "deploy less", both negative.** `portfolio_delta` ARM B
ceiling 1.00 cut the book 128 → 68 positions for a paired mean gain of
−0.0164 R, CI95 [−0.0847, +0.0500], failing six criteria; ARM D (net-delta band
at session open, the closest existing proxy for "adding onto an already-long
book") printed `SHAPE: NON-MONOTONE / FLAT` and the study verdict was
`NOISE`. Both cut on DELTA CEILINGS. Neither cut on position COUNT or on
similarity between concurrently held positions, which is why those axes remain
open rather than already refuted. **If this study's arms merely re-express a
delta ceiling, that is a null result, not a finding.**

---

### Population and basis, fixed here

- **Population.** The pooled book from `lib/book.py::load_book()`, era-scoped
  (`lib/era.py`), `include_bs=False`. PRIMARY = dense episodes
  (`episode_max_gap = 5`, `episode_min_dates = 10`); SECONDARY = the full
  sparse book. Both eras must be run and both reported.
- **Deployed set.** `top_k_per_day(..., k=3)` — the shipped card. This study
  never re-selects.
- **Book state is computed at ENTRY, from ENTRY-DATED information only.** A
  position's annotation uses positions open at the START of its entry session,
  before that session's own picks are admitted. No look-ahead: a position may
  never be annotated with anything about its own outcome, its own exit, or any
  later session. This mirrors `portfolio_delta` ARM D's banding rule and is
  gated (G2).
- **Open-position accounting.** A position is open on session *s* if
  `entry_date <= s < exit_date`. Positions are counted at the POSITION level,
  not the leg level, so the figure is comparable to `account_sim`'s `n_open`
  and NOT to the live leg counts quoted above.
- **Direction** = sign of the position's delta-notional, from the same field
  `s03_risk` uses. A position with no delta is UNKNOWN and is excluded from
  every direction total, never counted as zero (the missing-greek invariant).
- **Sector** = a static ticker→sector map committed with the study. It must be
  written from a source outside this book (no clustering may be induced from
  outcomes), committed in full, and quoted in the report's census. Tickers with
  no mapping are `UNMAPPED` and are their own bucket — never folded into a
  named sector.

### Arms

- **ARM N — NULL CONTROL (required).** Random book-state labels drawn to match
  each real arm's affected-position count, ≥1,000 draws, date-clustered. Every
  arm's gain is reported against ARM N's [p5, p95] band. An arm inside the band
  is NOISE regardless of its own CI.
- **ARM D0 — DESCRIPTIVE.** Mean R by concurrency band at entry
  `[0,3) [3,6) [6,10) [10,20) [20,inf)`, date-clustered CI per band, plus the
  same table by same-direction count and by same-sector count. **Descriptive
  only, never a criterion** — the shape is reported, no band is adopted.
- **ARM C — CONCURRENCY CEILING.** Refuse a pick whose entry session already
  has ≥ C open positions. Grid `C ∈ {5, 8, 12, 20}`. Refused picks are
  reported with their stored outcome (this study CAN do what `account_sim`
  cannot: it replays the full survivor book, so a refused pick keeps its
  counterfactual instead of appending `None`).
- **ARM K — CLUSTERING CEILING.** Refuse a pick when the open book already
  holds ≥ K positions sharing its DIRECTION, run separately for
  same-direction, same-direction-and-sector, and same-underlying. Grid
  `K ∈ {2, 3, 5}`.
- **ARM CK — the conjunction**, run only if ARM C and ARM K each clear their
  criteria independently. A conjunction that clears while neither component
  does is a fitting artefact and is refused.

### Bar for a candidate (all must hold; a failure is a failure, not a footnote)

- **X1 POWER FLOOR.** An arm is read only if it changes ≥ 25 dates and ≥
  `MIN_N_TO_READ` positions. Below either, the arm prints **UNDERPOWERED** —
  census only, no outcome number printed at all, nothing concluded. The floor
  may not be lowered to make an arm readable.
- **X2 GAIN.** Paired within-date mean gain in R vs the unmodified deployed
  book, 95% date-clustered CI excluding zero.
- **X3 NOT NOISE.** The arm's gain exceeds ARM N's p95.
- **X4 ERA STABILITY.** X2 and X3 hold on BOTH eras (v3 and current), same
  sign, and the point estimates lie within 0.15 R of each other. A rule that
  works only on the era it was found on does not ship. Given
  `v4_bridge`'s recorded ladder-mix shift, this criterion is expected to be the
  binding one.
- **X5 POPULATION STABILITY.** Same sign on PRIMARY and SECONDARY.
- **X6 LEAVE-ONE-OUT.** Dropping any single date, and separately any single
  ticker, leaves the gain positive.
- **X7 NOT A DELTA CEILING IN DISGUISE.** The arm's gain must survive
  controlling for net delta-notional at entry — i.e. it must still clear X2
  within `portfolio_delta`'s own bands. An arm that loses its gain under that
  control is reported as A RESTATEMENT OF ARM B/ARM D, which already failed,
  and does not ship.
- **X8 DOLLAR HONESTY.** Every dollar figure is quoted real+tweak, never
  pooled with `bs_options_hist` rows, per the standing DTE≥180 contamination
  hazard.

### Verdicts, worded now

- **ADOPT** — one arm clears X1–X8 on both eras. The report proposes the
  ceiling as a card rule; the operator decides.
- **ADVISORY ONLY** — clears X1, X2, X3 but fails X4 or X5. The census goes on
  the deploy card as a printed line (it already does, as of 2026-08-22); no
  rule ships.
- **NOISE** — any arm powered but inside ARM N's band.
- **UNDERPOWERED** — no arm clears X1. Census printed, nothing concluded.
- **RESTATEMENT** — clears X2/X3 but fails X7.

**Nothing ships from this study on the basis of a dollar total.** No ceiling
value may be adopted, recommended, or carried into a conclusion because it made
more money in the grid. The only admissible reading of the grid is qualitative
monotonicity, and the grid is a shape, not a menu.

### Gates (non-zero exit on failure)

- **G1 ERA IDENTITY.** The report header names the era it ran on and the
  export fingerprint; a mismatch or a thin era refuses (`lib/era.py`, exits 2
  and 3). No study-local snapshot pin is permitted to dodge this.
- **G2 NO LOOK-AHEAD.** Every position's book-state annotation is recomputed
  from entry-dated information only and re-verified against an independent
  recomputation; any position whose annotation reads a field dated after its
  entry session FAILS the run.
- **G3 SELECTION IDENTITY.** The unmodified pick set equals
  `top_k_per_day(...)` by set equality, proving no silent re-selection.
- **G4 REFUSAL ATTRIBUTION.** Every refused pick attributes to exactly ONE
  binding arm rule and the counts sum exactly; a mismatch FAILS the run.
- **G5 NO NEW STATISTIC.** No annualised figure, no Sharpe, no
  time-to-recover, per the standing research-tier rule.
- **G6 NO HARDCODED CENSUS.** Every count, percentage and range printed in
  prose is computed from the run. A measured quantity frozen into a string
  literal FAILS review.

### What this is NOT

The picks displaced by the 3/day cap carry no counterfactual in `account_sim`
(`day3_cap skips carry no counterfactual replay`). This study sidesteps that by
replaying the full survivor book rather than the account walk — but it
therefore says nothing about CAPITAL feasibility, and its arms must never be
compared against `account_sim`'s dollar totals. It also cannot separate
concurrency from calendar clustering: the signal dates cluster hard (118 v3
dates with nine months at ≤4 dates), so a high-concurrency session is often
also a dense-episode session. ARM D0 reports the cross-tab; no criterion rests
on it.
