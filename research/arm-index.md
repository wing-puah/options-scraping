# ARM index — every label that looks like an arm, and what it actually is

**One rule, and every confusion below follows from it: a label is study-local.**
`ARM P` is not an identifier — `emission_timing ARM P` is. Nothing defines
labels globally, and that is by design, not an oversight: an arm belongs to the
study that registered it. The cost is that the same letter means four different
things four studies over, and a bare `grep "ARM P"` returns ~200 hits, most of
them one study *citing* another's arm.

This file is the one place every such label is written down, organised BY
STUDY so everything a study owns sits together. **Citing an arm outside its
own study, always qualify it with the study** — `emission_timing ARM P`, never
a bare `ARM P`.

## Collisions, up front

- **`P`** — **four** arms: `emission_timing`, `macro_event_study`,
  `bear_giveback`, `bear_rewrap` — plus `P1`/`P2` sub-parts in `bear_rewrap`
  (the arm's own two halves) and `calendar_hedge` (an unrelated `P1`, the
  hedge sleeve itself).
- **`D`** — three arms (`portfolio_delta`, `next_day_move`, `account_sim`) —
  and `bear_deploy`'s `D1`–`D5`, which are criteria, not `ARM D`.
- **`H`** — two arms (`account_sim`, `calendar_hedge`); `H1`–`H4` hypotheses
  in `macro_event_study`; `H0`–`H5` criteria in `calendar_hedge`, which
  *also* has its own `ARM H` — unrelated to its criteria of the same letter;
  and `H0`–`H4` arms in `hedge_timing`, which are neither of those — there
  they are the census plus four hypotheses, each run once per trigger family
  and suffixed with it (`ARM H3-CHOP`).
- **`B1` / `B2`** — `bear_arm`'s two criteria (selection conditioning, exit
  fit) vs `ml_combination`'s two regression baselines. Same document
  registered both on 2026-08-11, and they mean nothing alike.
- **`F1` / `F2`** — `financed_spread`'s financing structures vs
  `account_sim`'s 1-contract-floor question. Unrelated.
- **`C` `N` `R`** — two arms each, different studies.
- **`S`** — `ARM S` in two studies (`calendar_hedge`, `bear_giveback`) vs
  `calendar_hedge`'s own `S1`–`S6` sub-arms vs the printed prose
  `ARM SELECTION`.
- **Gates: `G0` `G1` `G2` `G3` `G4` `G5` `G6`** — hard pass/fail
  preconditions checked before any result prints ([`glossary.md`](glossary.md)
  §9). Every study numbers its OWN from scratch, so `G2` in two studies is
  two unrelated checks — not indexed per-study below. Numbers are never
  reused after a gate is retired — `account_sim` runs G2–G5 because its G1
  went in 2026-08-15, and the survivors were deliberately NOT renumbered.

## The index, by study

Grouped in `scripts/backtest_study/` family order (①–④), alphabetical within
a family, then the studies still queued with no module yet. A bullet that
DEFINES a label starts with the backticked label; cross-references to other
studies' labels appear mid-prose only.

### ① Selection — what to trade

#### `bear_arm` — [`pre-registrations/f1_selection/bear_arm.md`](pre-registrations/f1_selection/bear_arm.md), `f1_selection/bear_arm.py`

- `B1` `B2` (criterion) — Bear criteria, NOT arms and NOT `ml_combination`'s
  baselines of the same letters below: `B1` is selection conditioning ("is
  there a bear subset, definable at decision time, that is not negative"),
  `B2` is exit fit (is PROD mis-tuned for bear rows). `B2` shipped
  `be_after: 0.50` in 2026-08-11 and its own rollback trigger reverted it on
  2026-08-24.

#### `emission_timing` — [`pre-registrations/f1_selection/emission_timing.md`](pre-registrations/f1_selection/emission_timing.md)

- `ARM L` (arm) — Fill lag — does an entry filled 1, 2 or 3 sessions after
  the signal lose the edge?
- `ARM P` (arm) — Persistence — does a re-emitted play (2nd/3rd/4th+ of a
  ticker+structure) perform worse than the first emission? One of `ARM P`'s
  four owners repo-wide (see Collisions, above).

#### `macro_event_study` — [`pre-registrations/f1_selection/macro_event_study.md`](pre-registrations/f1_selection/macro_event_study.md)

- `H1` `H2` `H3` `H4` (hypothesis) — pre-registered claims, each mapped to
  an arm under a DIFFERENT letter: H1→`ARM I`, H2→`ARM P`, H3→`ARM V`,
  H4→`ARM X`. Reports cite both forms.
- `ARM I` (arm) — Entry IV behaviour (H1 PRIMARY) — `vrp` on sessions near
  a scheduled event vs control.
- `ARM P` (arm) — Outcomes (H2) — mean R and E by entry-proximity bucket,
  within structure. One of `ARM P`'s four owners repo-wide.
- `ARM V` (arm) — Market context (H3) — VIX level and 1-day change by
  event-relative session.
- `ARM V-price` (arm) — Amendment 1 (2026-08-19) — the SPY-price companion
  to `ARM V`. CONTEXT ONLY, same standing as the VIX table.
- `ARM X` (arm) — Exit census (H4) — `exit_reason` mix and R. ENDOGENOUS by
  construction, DESCRIPTIVE, no verdict.

#### `ml_combination` — [`pre-registrations/f1_selection/ml_combination.md`](pre-registrations/f1_selection/ml_combination.md), `f1_selection/ml_combination.py`

- `B0` (baseline) — The benchmark: the shipped score-free ladder's top-3/day
  A-then-B replay, out-of-fold. Everything else is scored against it.
- `B1` `B2` (baseline) — COLLIDES with `bear_arm`'s criteria above and means
  something unrelated: `B1` is logistic regression on E>0 with structure ×
  market-direction × vol only ("does the model rediscover the ladder?"), `B2`
  elastic-net on E with the full feature set ("is there anything linear left").
- `M1` `M2` `M3` (model) — Gradient boosting on E, the same on binary E>0, and
  a single depth-3 tree. Only `M3` may ship, "because only it reduces to a
  human checklist"; a black-box score may at most tie-break within a tier.

### ② Management — when to get out

#### `bear_giveback` — `f2_management/bear_giveback.py`

- `ARM P` (arm) — Production baseline — the `be_after` threshold measured
  against the SHIPPED production exit. One of `ARM P`'s four owners
  repo-wide.
- `ARM S` (arm) — Deployment reference stats — n / win rate / profit
  factor / mean R by cut. COLLIDES with `calendar_hedge`'s own `ARM S`
  (its structure sweep) — unrelated.
- `ARM U` (arm) — Underlying path — does the underlying's price path
  explain the give-back? Buckets pre-declared before any output.

#### `next_day_move` — `f2_management/next_day_move.py`

- `ARM C` (arm) — Confound control — `ARM U`'s method (see `bear_giveback`,
  above — a different study's unrelated arm despite the shared letter)
  moved to day 0; hold the day-0 mark fixed and repeat the conformity cut
  inside day-0 P&L bands.
- `ARM D` (arm) — Descriptive — conform vs non-conform, cut by regime,
  structure, side.
- `ARM R` (arm) — The rule — a pre-registered day-0 cut, graded against
  shipped production.

#### `staged_exit` — [`pre-registrations/f2_management/staged_exit.md`](pre-registrations/f2_management/staged_exit.md)

- `ARM E` (arm) — Terminal "exit now" — pure composition around the FROZEN
  `harness.replay`, no fork or copy.
- `ARM T` (arm) — Tighten / arm-trail — `harness.replay` is COPIED into the
  study for this arm (contrast `ARM E`, which composes around the frozen
  one).

### ③ Structure — which wrapper

#### `bear_rewrap` — `f3_structure/bear_rewrap.py`

- `ARM P` (arm) — Portfolio contribution — P1 worst-decile, P2 correlation.
  The merge this arm validated is what `financed_spread` and `account_sim`
  cite. One of `ARM P`'s four owners repo-wide.
  - `P1` `P2` (sub-arm) — `ARM P`'s own two halves (worst-decile,
    correlation), graded together with their parent, never alone. Not to be
    confused with `calendar_hedge`'s own `P1` below, which is unrelated.
- `ARM W` (arm) — The wrapper, replayed on the shipped production exit.

#### `calendar_hedge` — [`pre-registrations/f3_structure/calendar_hedge.md`](pre-registrations/f3_structure/calendar_hedge.md) + `f3_structure/calendar_hedge.py`

- `ARM H` (arm) — The hedge programme (`calendar_hedge`'s own `P1` sleeve,
  below) — runs first; `ARM S` runs only behind it. This study also uses
  `H0`–`H5` as criteria (below); the two are unrelated despite the shared
  letter.
- `ARM S` (arm) — Structure sweep of untried wrappers, with sub-arms `S1`
  put mirror, `S2` short-near-put, `S3` short-pulled-up bear vertical, `S6`
  bull-put + bear-call wings. Runs only AFTER `ARM H` prints; nothing in it
  can ship on its own. COLLIDES with `bear_giveback`'s own `ARM S` above —
  unrelated.
- `H0` `H0b` `H1` `H2` `H3` `H4` `H5` (criterion) — criteria, NOT
  hypotheses and NOT `ARM H`: `H0` FILL, `H0b` FRESHNESS, `H1`–`H5`
  mirroring `bear_deploy`'s `D1`–`D5` (below). COLLIDES in letter only with
  `macro_event_study`'s `H1`–`H4` hypotheses above — unrelated forms.
- `P1` (sub-arm) — this study's own hedge sleeve itself, NOT `bear_rewrap`'s
  `P1`/`P2` above (which are that study's `ARM P` halves) — same letter,
  unrelated meaning.

#### `financed_spread` — [`pre-registrations/f3_structure/financed_spread.md`](pre-registrations/f3_structure/financed_spread.md)

- `F0` `F1` `F2` `F3` `F4` (arm) — Financing structures. `F0` strike-aligned
  control (machinery pilot, runs first); `F1` opposite-delta credit spread;
  `F2` naked short leg; `F3` same-direction financed vertical; `F4`
  diagonal financing (amendment 1, 2026-08-19). `F1`/`F2` COLLIDE with
  `account_sim`'s unrelated 1-contract-floor `F1`/`F2` below.

### ④ Deployment — can I run it

#### `account_sim` — [`pre-registrations/f4_deployment/account_sim.md`](pre-registrations/f4_deployment/account_sim.md), `f4_deployment/account_sim.py`

- `ARM D` (arm) — Downsize on admission failure (vs `ARM R` reject) — take
  the largest contract count that still fits.
- `ARM H` (arm) — The shipped bear hedge sleeve — 1/day, `|delta|`
  descending, ≤ ½ size.
- `ARM R` (arm) — Reject on admission failure (vs `ARM D` downsize) — drop
  a candidate a cap would breach.
- `F1` `F2` (arm) — COLLIDES with `financed_spread`'s F1/F2 above and means
  something unrelated: the 1-contract-floor question — `F1` takes a
  position at 1 contract even when its max loss exceeds budget (production
  behaviour, the headline cell), `F2` refuses it.
- `--compounding` `--live-select` `--structure-universe` (run) — CLI
  arms — alternative RUNS of one study, not separate questions. Each
  writes its own report/CSV stem ([`glossary.md`](glossary.md) §7).

#### `bear_deploy` — `f4_deployment/bear_deploy.py`, [`pre-registrations/f4_deployment/bear_deploy.md`](pre-registrations/f4_deployment/bear_deploy.md)

- `D1` `D2` `D3` `D4` `D5` (criterion) — Deployment criteria, NOT `ARM D` —
  `D1` is joint selection × exit, and the four that follow it. Mirrored by
  `calendar_hedge`'s `H1`–`H5` above.

#### `hedge_timing` — `f4_deployment/hedge_timing.py`, [`pre-registrations/f4_deployment/hedge_timing.md`](pre-registrations/f4_deployment/hedge_timing.md)

Each arm is run once per TRIGGER FAMILY and printed suffixed with it —
`ARM H1-CHOP`, `ARM H1-GAP`, `ARM H1-DECLINE`, and likewise for `H2`/`H3`/`H4`.
The bare `H0`–`H4` below are the arms themselves; the suffix names which
trigger the arm was run on, not a different question. NOT `calendar_hedge`'s
`H0`–`H5` (criteria) and NOT `macro_event_study`'s `H1`–`H4` (hypotheses).

- `ARM H0` (arm) — POWER CENSUS. Runs first and returns BEFORE any outcome
  column is read: trigger dates, bear-carrying dates, bear rows, H3-paired
  dates, and the same four on non-trigger dates. Every arm below early-returns
  UNDERPOWERED off it without computing a statistic.
- `ARM H1` (arm) — Between-date separation of bear R, trigger vs non-trigger,
  date-clustered. NOT the primary: a date either fires or does not, so no
  within-date pairing exists and a positive is confounded with "the market
  fell". Printed as `ARM H1-CHOP` `ARM H1-GAP` `ARM H1-DECLINE`.
- `ARM H2` (arm) — Beta control: the SAME separation on the DEPLOYED LADDER.
  `h2_mirrors` (|H2 delta| ≥ 0.5 × |H1 delta|, opposite-signed) turns a
  positive into MARKET-TIMING-PROXY. Printed as `ARM H2-CHOP` `ARM H2-GAP`
  `ARM H2-DECLINE`.
- `ARM H3` (arm) — **PRIMARY.** Within-date paired (`bear_deploy` D4's
  method): date-mean bear R minus date-mean tier-A/B long R, headline = the
  DIFFERENCE of that paired mean on trigger vs non-trigger dates. Printed as
  `ARM H3-CHOP` `ARM H3-GAP` `ARM H3-DECLINE`.
- `ARM H4` (arm) — Do-nothing baseline in DOLLARS (the only arm that may quote
  `$`): sleeve policies over the deployed ladder's daily dollars, judged by
  `bear_deploy` D3's criterion. Printed as `ARM H4-CHOP` `ARM H4-GAP`
  `ARM H4-DECLINE`.

#### `hedge_exposure` — [`pre-registrations/f4_deployment/hedge_exposure.md`](pre-registrations/f4_deployment/hedge_exposure.md), `f4_deployment/hedge_exposure.py`

Grid: 3 τ × 3 f = 9 cells per arm, fixed at registration and never expanded.
`ARM C` here is NOT `concurrency_correlation`'s `ARM C` (a concurrency
ceiling) and `ARM N` is the third `ARM N` in this family — same random-null
role, different study.

- `ARM M` (arm) — MEASUREMENT. The SAME unhedged book on both equity curves,
  mark-to-market (from `daily_pnl_csv`) versus realized-on-close
  (`account_sim.equity_curve`). Runs first and gates nothing. No arm in this
  study returns a finding or a verdict in this run — every cell is NULL or
  UNDERPOWERED; see `research/hedge-exposure-errata.md`.
- `ARM C` (arm) — Concentration-gated proxy put: hedge while the largest
  cluster's share of book gross delta notional is ≥ τ ∈ {0.30, 0.35, 0.40},
  sized at f ∈ {0.25, 0.50, 1.00} of a standard position's risk. Carries no
  prose.
- `ARM CS` (arm) — `ARM C` plus the analysis prose's `hedge-pressure ≥ 50`.
  PROSE-CONDITIONED; a date with no parse is NO SIGNAL.
- `ARM P` (arm) — The prose-free counterpart on exactly `ARM CS`'s session set.
  Written `**ARM P**` in `lib/hedge_instrument.py`, so the emphasis markers
  travel with the token: `P**` is this same arm.
- `ARM N` (arm) — Random-admission null, 200 seeds, matched on episode COUNT,
  episode LENGTHS and PROXY mix. An arm must beat its 95th percentile, not
  merely beat the unhedged book. COLLIDES with `portfolio_delta`'s and
  `concurrency_correlation`'s own `ARM N` — same role, different study.
- `ARM B` (arm) — Instrument comparison: the book's own bear row instead of the
  put. It cannot remove the §4 sleeve, which is operator policy.
- `ARM R` (arm) — Always-fillable reference: a delta-equivalent SHORT in the
  proxy underlying. Clause 7's control — a put arm that merely matches it is
  A RESTATEMENT OF DELTA REDUCTION. NOT `account_sim`'s `ARM R` (reject on
  admission failure). Written `**ARM R**` in `lib/hedge_instrument.py`, so
  `R**` is this same arm.
- `ARM RF` (arm) — Not pre-registered: `ARM R`'s fill-INDEPENDENT floor, sized
  off fraction f of the concentrated cluster's own signed delta notional rather
  than off `ARM C`'s put. It exists because the registration's `ARM R` is
  delta-matched to a put and so depends on the option cache it was introduced
  to be free of. Reference only; no verdict is read from it.

#### `portfolio_delta` — [`pre-registrations/f4_deployment/portfolio_delta.md`](pre-registrations/f4_deployment/portfolio_delta.md)

- `ARM B` (arm) — Net-delta ceiling band ∈ {1.0, 1.5, 2.0, 2.5, ∞} × equity.
- `ARM D` (arm) — Dose-response (DESCRIPTIVE PRIMARY) — mean R by the open
  book's delta at entry.
- `ARM H*` (arm) — Delta-TARGETED hedge-sleeve resizing — adjacent to
  `account_sim`'s hedge sleeve above, NOT the same arm.
- `ARM N` (arm) — The random null band — 200 seeded random admissions.
  COLLIDES with `concurrency_correlation`'s own `ARM N` below — same role,
  different study.

#### `selection_order` — [`pre-registrations/f4_deployment/selection_order.md`](pre-registrations/f4_deployment/selection_order.md)

- `O0` `O1` `O1b` `O2` `O3` `O4` (arm) — Ordering arms. `O0` = production
  `ladder_rank` baseline; `O1` delta-notional ascending; `O2` reserved-$
  per unit delta-notional descending; `O3` `|delta|` descending; `O1b`
  tier-blind across A∪B; `O4` = the seeded random null band that decides
  the meaning of the others.

### Queued — pre-registered, no module yet

#### `concurrency_correlation` — [`pre-registrations/f4_deployment/concurrency_correlation.md`](pre-registrations/f4_deployment/concurrency_correlation.md)

Registered 2026-08-22; the module is not written yet, so it has no
`scripts/backtest_study/` family folder to cite — this is the plan as
pre-registered, not a run.

- `ARM C` (arm) — Concurrency ceiling — refuse a pick whose entry session
  already holds ≥ C open positions; grid C ∈ {5, 8, 12, 20}.
- `ARM CK` (arm) — The conjunction of `ARM C` and `ARM K`, run only if each
  clears independently.
- `ARM D0` (arm) — Descriptive only — mean R by concurrency band at entry;
  the shape is reported, no band is adopted.
- `ARM K` (arm) — Clustering ceiling — refuse a pick when the open book
  already holds ≥ K sharing its direction (also run same-direction-and-
  sector, same-underlying); grid K ∈ {2, 3, 5}.
- `ARM N` (arm) — Null control (required) — random book-state labels
  matched on affected count; an arm inside its [p5, p95] band is NOISE
  regardless of its own CI. COLLIDES with `portfolio_delta`'s own `ARM N`
  above — same role, different study.

## Not labels

`ARM SELECTION` `ARM UNIVERSE` `ARM VERDICT` — printed report text or code
comments that read like labels but are not: `"ARM VERDICT INPUT:
UNDERPOWERED"` is a printed report line; `ARM SELECTION` marks
`account_sim`'s `--compounding` switch in a code comment; `H ARM UNIVERSE`
is a `calendar_hedge` table header.

### Kinds

The kind noted in parentheses after each label:

- **arm** — one independently-verdicted question inside a study; a study may
  earn one verdict per arm ([`glossary.md`](glossary.md) §9). Most use the
  `ARM <letter>` form; `financed_spread` and `selection_order` do not, and so
  never turn up in an `ARM` search at all.
- **sub-arm** — a named half of an arm. Graded with its parent, never alone.
- **run** — an alternative RUN of one study (a CLI flag), not a separate
  question ([`glossary.md`](glossary.md) §7).
- **gate** — a hard pass/fail precondition checked before any result prints.
- **criterion** — a feasibility question graded once gates pass.
- **hypothesis** — a pre-registered claim; in this repo always ALSO an arm,
  under a different letter.
- **prose** — printed report text or a code comment that reads like a label.

## Keeping this file honest

`tests/test_arm_index.py` fails if any `ARM <label>` token appears in a study
module or a pre-registration without a mention here — so a newly registered
arm cannot be added without landing in this index — and pins the four `ARM P`
owners.

What it does NOT check: the descriptions, which are the operator's own words,
same as [`study-map.md`](study-map.md)'s verdicts. It also cannot enforce
coverage of the non-`ARM` labels — gates, criteria and hypotheses have no
identifying token shape, so those bullets are hand-maintained and can go
stale; where this file disagrees with the code, the code is right.

## See also

- [`glossary.md`](glossary.md) §9 — what an ARM is, and the verdict grammar
  arms are graded under. §7 — CLI arms.
- [`pre-registrations/`](pre-registrations/) — the arms' actual definitions,
  in full, immutable.
- [`study-map.md`](study-map.md) — what each study asked and concluded.
