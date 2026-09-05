## exit_drawdown — walk-forward exit hypotheses judged on account-level drawdown

_Registered 2026-09-05._

An f2 MANAGEMENT study. The signal, the entry day, the structure, the ladder pick
order and the base sizing are all frozen. The only thing an arm changes is what
happens to an ALREADY-OPEN position — and, for ARM D alone, the size of a NEW
one. Every threshold any arm uses is chosen OUT OF SAMPLE, on training dates
only, and the headline is read off the stitched out-of-sample book.

## Question

Does any exit rule — chosen without look-ahead — reduce the **account-level
mark-to-market drawdown** of the deployed book, without giving back its edge?

The operator's queued question is "MAX DRAWDOWN, not timing". `account_sim`
deploys the ladder through a $25,000 ledger and reports what that book earns;
`lib/mtm_curve.py` can mark the same book to market and report what it went
through to earn it. No study has yet judged an exit rule on that curve, and no
exit knob in this repo has ever been chosen out of sample.

Five sub-questions, four of them about exits and one, labelled SECONDARY, about
sizing:

- **Out-of-sample selection of the knobs we already ship.** All pt/sl/tef tuning
  to date was full-window and in-sample. `protocol.walk_forward_splits` (purged,
  expanding, 120-day embargo) exists and has never been pointed at the exit grid.
- **An underlying-price stop for DEBITS.** Only credits were ever tried (the
  short-strike breach). `bear_giveback` located the give-back pattern in the
  UNDERLYING rather than in the mark.
- **A flow-unwind exit off the traded contract's OI PATH.**
  `backtests/option_history_cache/` holds per-session `Open Int` and `Volume`
  for every priced leg; no study has read the OI path.
- **Partial scale-out**, exactly computable from stored paths and never measured.
- **A deployment-level drawdown throttle** (sizing, not exit) — the most direct
  lever on the account curve, carried along only as a labelled comparator so the
  reader can see whether exits or sizing move the curve.

## What this is NOT

This is not a re-run of any exit thread the record has already closed. Every
family below is a STANDING NULL and none of it is re-tested here; each is named
so a later reader can check that no arm smuggles one back in.

| Family already settled | Standing verdict | Where |
|---|---|---|
| Mark-based trailing stops (Attempts 1 / 2 / 10) and loss-days | REJECTED — the "reactive null": all 21 debit trail exits sold continuations | `archive/01–02`, `exit_mechanism_study` |
| The pt/sl/tef grid on debits | PROD `pt .90 / sl .75 / tef .75` is the IN-SAMPLE plateau; every retune was measured in-sample with LOO, and the reactive null re-appeared 2026-09-04 | `exit_mechanism_study` |
| Credit profile `pt .65 / sl null` | SHIPPED (Attempt 13); its rollback trigger is UNDERPOWERED (0/15 fresh rows) | `next-steps.md` §2.6 |
| Time-staged day-X ± Y% switch | NULL — 0/40 powered cells, day-5 loss cuts significantly harmful, 50–79% continuation sales | `staged_exit`, §3 |
| Model-text invalidation / trigger / horizon stops | CONTRARY on `bull_call`/LVOL, NULL elsewhere | `exit_from_text`, §2.8 |
| Day-0 underlying move cuts | NULL — the confound control fails | `next_day_move` |
| Bear-debit `be_after 0.50` | SHIPPED 2026-08-11 → REVERTED 2026-08-24; three censuses gave three answers | §2.4 |
| Per-regime exit switch (mech `BEAR_HE` trail / LVOL tef-null) | STAYS GATED | `exit_switch_*`, §2.7 |
| Credit underlying short-strike breach | NOT VALIDATED (n-of-1 TSLA); the study is RETIRED | Attempts 9 / 11 |
| Signal-date volume conditioning | NULL / path-vol proxy | `volume_signal` |
| The operator's queued max-drawdown question | Open, and no sleeve policy touches it — every mechanical hedge TRIGGER is dead, the hedge INSTRUMENT is unmeasured | memory 2026-08-28, §2.1 |

The standing rules in [`../../next-steps.md`](../../next-steps.md) §3 bind this
study as written, and specifically:

- **The day-X / ±Y% / ±$Z exit formula is `staged_exit`, and it is null.** It
  may not be re-registered under another anchor — not days-since-entry, not
  DTE-remaining. **No arm here is anchored on a session index or a P&L band at a
  session index.** ARM U triggers on the UNDERLYING's distance from the entry
  close in ATR units; ARM O triggers on the traded contract's open-interest path;
  ARM P has no trigger at all.
- **Trigger-gated ENTRY is LATE-ENTRY** (`trigger_entry`, v4 + v3). Nothing here
  moves an entry: entry basis is next-open and the entry session is `t.grid[0]`
  in every arm.
- **No further text study.** No arm reads model prose, an invalidation line, a
  trigger line or a horizon.
- **`score_total` is decision-irrelevant** and the ML/selection search is closed:
  no arm re-cuts selection, and nothing here proposes a new selection clause.
- **`bear_call_spread` is intake-vetoed; bear debit is selection-vetoed at card
  §1.4** and lives in the §4 hedge sleeve only. This study does not deploy a bear
  position that the shipped ladder would not deploy — it inherits `account_sim`'s
  admissions unchanged.
- **v3 and v4 rows are never pooled**; only the `real` and `strike_expiry_tweak`
  pricing tiers are read (`include_bs=False`); the study is ERA-scoped through
  `lib/era.py` and its report header names the era it ran on.
- **`exit_basis` is never read to ask whether a row REPLAYS.** It is era-scoped
  and unreadable on v3; the replay question is answered mechanically through
  `lib/replay_basis.py`, as it is everywhere else.
- **ARM labels are study-local.** Cite these as `exit_drawdown ARM W`, never a
  bare `ARM W`.
- **Never read silence as "the trigger was not met"**, and **never hardcode a
  figure off one export** — including in report prose. Every count in this study
  comes from `len(records)` after filters at run time.

**Why this is admissible at all after that list.** Every verdict in the table
above was reached on a **per-row R** estimand under **in-sample** parameter
choice. This study's headline estimand is a different object in two independent
ways, and both must hold for it to be worth running:

1. **Account-level, mark-to-market, path-dependent.** The outcome is the maximum
   drawdown *in dollars* of one deployed $25,000 ledger whose open positions are
   MARKED (`lib/mtm_curve.py`), not the mean of a per-row distribution. A rule
   can leave mean R untouched and still change that curve — through *when* the
   reserve is released, *which* positions are concurrently open, and how deep the
   marked book goes between entry and exit. Conversely, `hedge_exposure` ARM M
   established that the close-bucketed curve UNDERSTATES this book's max drawdown
   by 40.2%, so a per-row read cannot stand in for it. Per-row R is therefore not
   a proxy for this metric in either direction, and the standing nulls above do
   not answer it.
2. **Out-of-sample selection.** Every threshold is fitted on TRAIN dates and
   applied to TEST dates. The in-sample plateau the pt/sl/tef grid already found
   is not the question; whether a plateau chosen blind survives on the dates it
   was not chosen on is.

Neither difference makes any arm exempt from the reactive diagnostic. **A rule
that cuts the drawdown by selling continuations has re-found the reactive null in
new clothes**, and the continuation diagnostic is registered below as a PASS
CRITERION (`REACTIVE-AGAIN`), exactly as `staged_exit` registered its G2 — not as
a footnote.

Finally: this is **not a hedging study**. It does not open, size or time a
sleeve, and it says nothing about §2.1's instrument question. It changes the
management of positions the ladder already deployed.

## Population and basis, fixed here

- **Era.** PRIMARY `--era current` (v4 — the 166-date book, the first with 2026
  signal dates). SECONDARY `--era v3` (795 rows / 118 dates) is RUN and REPORTED
  and carries no verdict of its own. **Never pooled.**
- **Book.** `load_book(include_bs=False)` — `real` and `strike_expiry_tweak`
  tiers only — with the proxy CALIBRATION GATE ON, as every deployment study
  reads it.
- **Deployment population.** `account_sim`'s `dense_episodes` population is
  PRIMARY. The `all` population is run as a DISCLOSED SECONDARY CUT and printed
  beside it; no verdict is read from `all`. This mirrors `account_sim`'s own
  reading, in which FEASIBLE is explicitly a two-year, dense-episode claim.
- **Baseline.** The comparison is ALWAYS paired against the **SHIPPED** profile
  as `account_sim.profile_for` resolves it per row — including the bear-keyed
  variants — and **never** against a clean `DEBIT_PROD`. Comparing against clean
  `DEBIT_PROD` changed a decision twice in this repo's history; it measures the
  shipped profile's own value rather than the arm's.
- **Credit rows keep `CREDIT_PROD` in every arm.** There is no validated credit
  replay to overlay, and no arm proposes one. Credit rows are carried so the
  ledger and the curve are the real book, not so a credit exit is tested.
- **Entry basis** is next-open; the entry session is `t.grid[0]`.
- **Row exclusions are counted, never silent.** Rows excluded by an arm's data
  requirements (below) are reported per arm with their counts before any
  conditional number is quoted (G-COV).

### No-lookahead rules, binding

These are commitments, not implementation notes. A violation of any of them
invalidates the run.

- **Thresholds are chosen per walk-forward block on TRAIN dates only.** Splits
  come from
  `walk_forward_splits(dates, block=15, embargo_days=P.PATH_CAP_DAYS (=120), min_train_dates=40)`
  — purged, expanding, with the embargo equal to the path cap — and the chosen
  configuration is applied to that block's TEST dates.
- **The fit is two-stage per block.** (1) A cheap per-row prefilter: every grid
  configuration's TRAIN mean R via memoised `replay_sized`; keep the
  configurations within **0.02** of the best. (2) Among those survivors, run
  `simulate()` on the TRAIN `day_lists` only and pick the **smallest TRAIN MTM
  max drawdown** (`book_curves` → `path_stats`).
- **The tie order, made TOTAL and scoped per arm.** Ties break, in this order:
  (i) to **PROD** — which is a grid point in **ARM W ONLY**, so this step is live
  for ARM W and INERT for every other arm; (ii) to the configuration with **fewer
  active rules**; (iii) to the configuration whose overlay **FIRES ON THE FEWEST
  TRAIN ROWS** — the most conservative survivor, the one closest to leaving the
  shipped profile alone; (iv) if still tied, to the **LARGEST** parameter value
  (largest `k`, `X`, `d`), which is deterministic and points the same way as
  (iii). Steps (iii) and (iv) are **registration-time additions**, flagged as new
  binding content for the operator's review: the plan states the tie-break
  generically ("tie → PROD, then fewer active rules"), but only ARM W's grid
  contains a PROD point to tie back to, so for ARM U, ARM O and ARM D the plan's
  rule is not total on its own. Nothing here is decided at build time.
- **ARM U's, ARM O's and ARM D's grids contain NO "off" / no-overlay point, and
  that is deliberate.** The walk-forward fit selects among an arm's OWN
  configurations only; whether doing nothing would have been better is answered
  by the arm-versus-SHIPPED comparison that every criterion in "Bar for a
  candidate" is written against — not by letting the fit pick "no overlay". A
  block on which no configuration beats doing nothing therefore still dispatches
  a configuration onto its TEST dates, and that surfaces as a failed clause 1 or
  as `CONTRARY`. That is the honest reading of such a block, and the absence of
  an escape hatch is registered here rather than added later.
- **One shared `account_sim.new_cache()` per era-run**, and a `date → block` map
  dispatches each position's configuration inside **ONE stitched OOS
  `simulate()`**. The headline book is that stitched book.
- **Burn-in is EXCLUDED and reported.** Dates before the first TEST block — the
  dates that exist only to train the first fit — are excluded from the OOS
  headline population. The report prints a burn-in census (dates, rows, and the
  span they cover) as its own line. They are **never** silently replayed under
  the shipped profile and folded into the headline. The OOS population is exactly
  the union of the blocks' TEST dates.
- **In-sample bests are printed under a `DISCLOSURE, in-sample` header and carry
  NO verdict.** They exist so a reader can see the size of the in-sample/OOS gap;
  no criterion below may be evaluated on them.
- **Information set at the moment of decision.** An exit decided at the close of
  session `d` may read: spread marks ≤ `d`, underlying bars ≤ `d`, option
  `Volume` ≤ `d`, and option `Open Int` ≤ `d−1` — Barchart publishes open
  interest the next morning, so same-session OI is not knowable at that close.
- **ARM D reads only the ledger's MARKED equity as of the session's OPEN**, with
  exits processed before entries, exactly as `simulate` already orders the day.
- **G1 leak test (below) is the mechanical check on all of the above.**

## Plan-time observations, disclosed

Measured while the study was being designed, before any arm ran. They are
disclosed so no number here can be presented later as a result.

**The yardstick.** `account_sim`'s per-era record
([`../../study-results/f4_deployment/account_sim.md`](../../study-results/f4_deployment/account_sim.md))
carries, for era **v4** on the exports dated **2026-09-04 20:31** (inputs
`1b1ba3c`, sha `b007f95`, recorded 2026-09-04), the verdict `>>> FEASIBLE <<<`
on the PRIMARY dense-episode population. That run's headline cell is
**`n=148  dates=76  $22,217  meanR +0.348`**, with **`maxDD $-3,750`
(15.0% of $25,000 starting capital)** and **worst session `$-2,796`**. Those are
the figures this study is measured against, and they are read off that one
export — the arm-versus-shipped comparison below is computed inside each run,
never against these constants.

Two boundaries on that yardstick, disclosed with it:

- The SECONDARY full book on the same export (`n=260  dates=129  $21,855
  meanR +0.231`) FAILS A1 on 2026 and A3 at `maxDD $-8,920` = 35.7% of capital.
  FEASIBLE is a dense-episode claim; nothing in it has seen 2026.
- `account_sim`'s own `print_equity` states that **open positions are not marked
  to market** on the basis it reports. The marked curve this study reads is
  `lib/mtm_curve.py` (`book_curves` → `path_stats`), which is a different and
  deeper curve; `hedge_exposure` ARM M measured the close-bucketed
  understatement at 40.2%.

**Coverage — ESTIMATES, to be replaced by the run's own census.** These are
plan-time counts of files on disk, not measurements of the study's population,
and no criterion may be evaluated against them:

- `backtests/underlying_ohlc_cache/` holds bars for an ESTIMATED **105 tickers**.
  How many of the book's tickers that covers, and how many entry rows survive the
  ATR requirement, is unknown at registration and is printed by G-COV. Gaps are
  filled by `scripts/collector/fetch_underlying_ohlc.py --tickers … --skip-existing`
  BEFORE the run, never by imputation during it.
- `backtests/option_history_cache/` carries per-session `Open Int` and `Volume`
  on the priced legs. The share of entry legs with a usable OI path is an
  ESTIMATE of "most" and is NOT quantified at registration; G-COV prints it.
- Whether any cell clears the power floor is likewise unknown at registration.
  `staged_exit` had 0/40 powered cells on a comparable book; **the modal outcome
  here is UNDERPOWERED cells**, and that expectation is registered now so it
  cannot be narrated as a surprise later.

## Arms

Five, frozen. No arm is added after the first run.

**On the "(debit verticals only)" qualifiers.** The plan's Design section carries
that qualifier on ARM U's title alone. It is added here to ARM O's and ARM P's
titles too — a CLARIFYING addition made at registration time, not a change of
scope: it is a direct consequence of the already-stated "Credit rows keep
`CREDIT_PROD` in every arm" clause in "Population and basis", which each of those
arms then restates in its own DEBIT ROWS ONLY paragraph. Nothing about which rows
an arm touches differs from the plan; the title is flagged here only because this
file flags every word that is not verbatim plan text.

### ARM W — walk-forward knob control

The honesty baseline for every other arm. Grid: `pt ∈ {.60, .75, .90, 1.10}` ×
`sl ∈ {.50, .75, off}` × `tef ∈ {.60, .75, off}` — **36 configurations, of which
PROD is one grid point.**

Train objective, fixed now: among configurations whose TRAIN mean R is
≥ (train-best − 0.02), pick the smallest TRAIN MTM max drawdown; tie → PROD, then
fewer active rules. ARM W reports BOTH "WF-selected vs PROD" and "PROD itself",
so the reader can see how much of any arm's movement is walk-forward selection
rather than the rule under test.

**DEBIT ROWS ONLY.** The grid is searched and applied on debit rows alone;
CREDIT rows keep `CREDIT_PROD` unchanged, per "Population and basis" above — no
`pt`/`sl`/`tef` configuration from this grid is ever applied to a credit
spread's legs. Credit rows are in the book so the ledger and the curve are the
real book, not so a credit exit is selected.

### ARM U — underlying ATR stop (debit verticals only)

Exit at the CLOSE of the first session where the underlying close is against the
position by **≥ k · ATR14**, measured from the **ENTRY-session close**.

- **ATR14 is FROZEN AT ENTRY.** It is `underlying_features.atr14_pct` — a
  **simple 14-session mean of true range, NOT Wilder-smoothed** — multiplied by
  the entry close to give a dollar distance. This study uses that definition as
  it stands and does not re-implement or smooth it.
- A row whose `atr14_pct` is `None` because the series is below its minimum
  observation count is **EXCLUDED and counted**.
- `k ∈ {1.5, 2.0, 3.0}`. Two variants: **(a)** the ATR stop is ADDED to `sl .75`;
  **(b)** the ATR stop REPLACES `sl`.
- Direction comes from the structure (`bull_*` vs `bear_*`).
- Rows priced on the close-only `Price~` fallback (no high/low, so no true range)
  are **EXCLUDED and counted**. Split-rescaled tickers are fine — the ratio is
  taken within one bar series.
- **A missing bar on a grid day is "unpriced, skip", never a zero move.**
  `t.grid` is a WEEKDAY grid and holidays are unpriced sessions.

The trigger is measured from the ENTRY close and cannot re-arm on a new peak.
That entry-anchored, non-re-arming property is what distinguishes it from the
three rejected trails, and it does not exempt it from the continuation
diagnostic.

### ARM O — flow-unwind exit (debit verticals only)

Reads the traded contract's own flow, which no study has done.

**DEBIT ROWS ONLY.** "The entry LONG leg" below means the long leg of a DEBIT
vertical. CREDIT rows keep `CREDIT_PROD` unchanged, per "Population and basis"
above; the flow-unwind rule is never applied to a credit spread's short leg, and
no credit row is ever exited by this arm.

- A new reader `load_oi(leg)` is required — there is none today. It is modelled
  on `harness.Trade._load_underlying`, reading `Open Int` through
  `lib.parsing.to_float`.
- Let `OI_max` be the RUNNING MAX of the entry LONG leg's `Open Int` over the
  sessions since entry, read **LAGGED one session**: the value usable at session
  `grid[i-1]` is the one dated `grid[i-2]`.
- **Exit when the lagged OI ≤ (1 − X) · OI_max**, `X ∈ {0.25, 0.40}`.
- **One volume variant**, and only one: leg volume(`d`) ≥ 3× its post-entry
  median AND the mark closed against the position.
  - **The median is EXPANDING and as-of `d`.** It is taken over the leg's
    post-entry volumes on sessions **up to AND INCLUDING `d`** — never over the
    position's whole holding period, which would read volume dated AFTER `d`
    into `d`'s own trigger and is exactly the leak G1 exists to catch. Stating
    the window here puts it in the specification rather than leaving it to the
    build.
  - Same-session `Volume` IS admissible (see "Information set at the moment of
    decision": marks, bars and `Volume` are readable ≤ `d`; only `Open Int` is
    lagged to ≤ `d−1`). Sessions with a missing volume are SKIPPED, never read
    as zero, and the median is taken over the observed values only; a session
    whose expanding window holds too few observed volumes to form a median
    cannot fire the variant.
- **Blank OI is MISSING; OI literally 0 is a VALID full unwind.** The reader must
  distinguish the two — conflating them either fabricates exits or hides them.
  Rows with blank OI on **≥ 20% of their hold sessions are EXCLUDED and counted**.
- A missing OI value on a grid day is skipped exactly as an unpriced mark is; it
  is never read as a 100% drop.

### ARM P — partial scale-out (debit verticals only)

Exact; there is nothing to select and no threshold to fit.

**DEBIT ROWS ONLY.** "Half the contracts" splits a DEBIT vertical's position.
CREDIT rows keep `CREDIT_PROD` unchanged, per "Population and basis" above — a
credit row is never split, never scaled out, and never exited by this arm.

- Half the contracts exit at `pt .90` as shipped; the other half replays the
  shipped profile with `pt=None`.
- Modelled as **TWO synthetic `Pos` per rec** (half size each, each with its own
  exit session), so `book_curves` sees valid per-position windows and the ledger
  releases half the reserve at the FIRST exit.
- **Odd contract counts**, which "half the contracts" leaves open: the `pt .90`
  half takes `⌈n/2⌉` and the `pt=None` half `⌊n/2⌋`. A position scaled to **n = 1
  cannot be split** — one half would be zero contracts, which is not a position —
  so **n = 1 rows are EXCLUDED from ARM P and counted** in its census.
- **Traceability of the two rules above.** The `⌈n/2⌉`/`⌊n/2⌋` split and the
  `n = 1` exclusion are **NOT transcribed from the plan's Design section**, which
  says only "half the contracts". They resolve an edge case the plan left
  unspecified — a size-1 position cannot be halved into two positions — and are
  fixed HERE, before the run, rather than decided at build time. They are new
  binding content, flagged as such for the operator's review; a later reader must
  not mistake them for plan text. The exclusion is population-affecting, so its
  count is printed in G-COV like every other exclusion.
- **Paired R = the mean of the two halves.** R, not dollars, is quoted for ARM
  P's per-row comparison, because the contract counts differ from the shipped
  row's. The account-level drawdown co-primary is by construction a dollar
  figure of the deployment and is reported as such for ARM P too, with that
  non-comparability stated beside it.
- **The dollars ban is scoped, deliberately and by sanction.** The planning
  rule "quote R, not dollars, for ARM P" binds ARM P's PER-ROW and PAIRED
  comparison ONLY — that is where contract counts differ and a dollar figure
  would be meaningless. It does **not** reach the mandatory account-level MTM
  max-drawdown co-primary, which is a WHOLE-BOOK dollar figure of one $25,000
  ledger, is required for EVERY arm, and is this study's headline metric; it is
  reported in dollars for ARM P exactly as for every other arm. A grader must
  not read the ARM P dollar drawdown line as a breach of that rule. The tension
  is in the plan itself and is not resolved there: its "Traps to encode" list
  says "Quote R, not dollars, for ARM P (contracts change)", while its "Unit and
  metric" section makes the dollar MTM max drawdown a co-primary reported "for
  every arm and cell". The scoping above is this registration's INTERPRETIVE
  resolution of those two clauses, recorded as such so a grader weighs it as a
  registered decision rather than discovering it as a discrepancy.
- **This one resolution needs an explicit operator ACK before the module is
  built.** Everywhere else in this file, added text ELABORATES an unambiguous
  plan clause; here alone the registration DECIDES between two plan clauses that
  contradict each other, and the workflow's phase-1 instruction ("approving this
  plan IS the operator's review of the commitments; the agent transcribes, it
  does not redesign") reserves that choice for the operator. So it is carried as
  an OPEN ITEM, not a settled one: the operator acknowledges the scoping above
  explicitly — an ack, not merely the absence of an objection to a documented
  interpretation — before `f2_management/exit_drawdown.py` is written against it.
  If the operator instead reads the dollars ban as unscoped, ARM P reports NO
  dollar drawdown figure and its co-primary 1 is quoted in R and as a percentage
  of starting capital; that alternative is stated here so the choice is between
  two written options rather than a re-litigation after a number is seen. The
  resolution actually taken is recorded as a dated wording correction appended to
  this file if it differs from the scoping above.

### ARM D — drawdown throttle (SECONDARY; sizing, not exit)

Carried so the reader can see whether exits or SIZING move the account curve.

In `simulate`, when marked equity ≤ (1 − d) · running peak, new positions size at
**half** the risk budget until equity ≥ (1 − d/2) · peak. `d ∈ {0.05, 0.10}`,
chosen walk-forward exactly as every other threshold here is. It reads only the
ledger's marked equity as of the session's open.

**What "affected" means for ARM D, fixed here.** ARM D is a SIZING rule. It has
no overlay and no exit reason of its own: it never changes an already-open row's
exit, so G0's general definition of "affected" ("the arm changed that row's
exit") is EMPTY for it. Read literally, every ARM D cell would then hold zero
affected dates and zero affected rows and be **vacuously UNDERPOWERED** whatever
the throttle did to the account curve. That is a defect of the general
definition, not a finding about sizing. For ARM D, and for ARM D only:

- An **affected ROW** is a position ENTERED while the throttle was ACTIVE — i.e.
  one actually sized at HALF the risk budget because marked equity at that
  session's open was ≤ (1 − d) · running peak. A position entered at the full
  budget is not affected, and neither is a position merely HELD through a
  throttled stretch.
- An **affected DATE** is a signal date on which at least one affected row was
  entered.
- G0's floors (**≥ 25 affected DATES and ≥ 60 affected ROWS**) and clause 6 are
  evaluated on exactly those counts, and ARM D's census prints them like every
  other arm's. **No other arm may use this definition** — for the four exit arms,
  "affected" stays "the arm changed that row's exit".

**CONT (clause 7) is DROPPED from ARM D's conjunction.** A sizing rule cannot
re-find the reactive null: it moves no exit, so every position in its book exits
on the shipped profile's own rules and the continuation rate ARM D would report
is the baseline's by construction — it would print the shipped profile's number
under an arm's name and could neither confirm nor refute anything about ARM D.
**ARM D's conjunction is clauses 1–6.**

**Traceability of the three rules above.** The SIZING definition of "affected",
the CONT drop from ARM D's conjunction, and the `SECONDARY-`prefixed token set
(below, under "ARM D's tokens") are **NOT transcribed from the plan's Design
section**, which says only that ARM D is "reported beside the exit arms only …
Can never ship from this study" — it defines no "affected" semantics for a sizing
arm, no conjunction restriction and no ARM-D token vocabulary. They resolve what
the plan left unspecified: G0 and the verdict grammar are both written in terms
of an arm CHANGING A ROW'S EXIT, and a sizing arm changes none, so read literally
every ARM D cell would be vacuously UNDERPOWERED and V3 would have no referent.
They are fixed HERE, before the run, rather than decided at build time. They are
**new binding content, flagged as such for the operator's review** — exactly as
ARM P's `⌈n/2⌉`/`⌊n/2⌋` split and `n = 1` exclusion are — and a later reader must
not mistake them for plan text. Each is population- or verdict-affecting, so ARM
D's counts print in G-COV and its token prints with its `SECONDARY-` prefix like
every other reported figure.

ARM D is **labelled SECONDARY everywhere it is printed** and **can never ship
from this study**, whatever it prints. It is a sizing rule and this is an f2
management registration; the most it can ever do is queue an f4 registration of
its own.

## Unit and metric

**Unit = the signal DATE.** Every confidence interval is date-clustered.

**Co-primaries**, both reported for every arm and cell:

1. **MTM max drawdown, in DOLLARS, of the OOS-stitched deployment** —
   `book_curves(target=TARGET_POSITION)` → `path_stats`. **Ulcer index** and
   **time-under-water** are printed beside it as path-shape context.
2. **Paired ΔR by DATE versus the shipped profile** — `boot_ci_paired_by_date`.

The drawdown-improvement CI uses the block-bootstrap `improvement()` pattern
already registered and used in `hedge_exposure`.

**Never annualised. No Sharpe. No time-to-recover.** ARM P's per-row comparison
is quoted in R, never in dollars.

## Gates

Every gate is evaluated and printed. The machinery gates (G-FORK, G-CAL, G-MTM,
G1, G-COV) are RUN-LEVEL: a failure stops the run non-zero and **no verdict is
read for any arm**, because a failure there is a finding about the machinery and
not about exits.

- **G0 — POWER. Runs first and blocks every criterion.** Per (arm × cell):
  **≥ 25 affected DATES and ≥ 60 affected ROWS**, where **"affected" means the
  arm changed that row's exit**. Below either floor, the cell is UNDERPOWERED:
  its census is printed, and no criterion is evaluated on it. Counts come from
  `len(records)` after filters at run time — never from a stored expected figure.
  **G0 is evaluated on the OOS-STITCHED EVALUATED POPULATION** — the union of the
  blocks' TEST dates, AFTER the burn-in exclusion and AFTER that arm's own data
  exclusions — which is the same population every clause in "Bar for a candidate"
  reads. BOTH floors are therefore measured on the evaluated set from the start;
  neither is ever taken on a pre-burn-in or full-book population. Clause 6 is a
  RESTATEMENT of the date floor for readability, not a second and different
  check, and the ROW floor needs no restatement because it was never measured
  anywhere else.
  **ARM D is the one exception, and it is defined, not left to the build.** ARM D
  changes no row's exit, so this definition is empty for it and would make every
  ARM D cell vacuously UNDERPOWERED; G0 counts ARM D's cells on the SIZING
  definition of "affected" fixed in ARM D's section above (a row entered at the
  halved budget; a date on which such a row was entered). That definition is ARM
  D's alone.
- **G-FORK — the overlay is a composition, not a fork.** Every overlay, with its
  own rule DISABLED, must reproduce `harness.replay` EXACTLY — on ALL rows, in
  BOTH eras. `lib/harness.py` is FROZEN and is not edited. One disagreement fails
  the run.
- **G-CAL — the host simulation is unchanged.** `account_sim`'s own gates
  **G2–G5** must still pass with the DEFAULT replayer
  (`account_sim --selftest-gates`). The replayer hook must be a no-op when it is
  not used.
- **G-MTM — the curve and the ledger agree.** The mark-to-market value at exit
  must equal the overlay's own dollars for that position, within `TOL_DOLLARS`.
- **G1 — LEAK GUARD.** Shift every auxiliary series (bars, OI, volume) ONE
  SESSION FORWARD and assert that **at least one exit changes** AND that **no
  exit moves EARLIER** than the original. The first half proves the series is
  actually being read; the second proves the rule is not reading the future.
- **G-COV — COVERAGE, printed BEFORE any conditional number.** Per arm: bar
  coverage (tickers with and without a cached series; rows dropped for `Price~`
  close-only fallback; rows dropped for a `None` `atr14_pct`), OI coverage (entry
  legs with a usable path; rows dropped at the ≥20%-blank threshold), and ARM P's
  n = 1 exclusions. A conditional figure printed above its coverage line is a
  reporting defect.

## Bar for a candidate

A candidate must clear the WHOLE conjunction, on the **PRIMARY** population, on
the **OOS-stitched** book. Failing any one clause is failing.

1. **Max drawdown improves by ≥ 15%** versus the shipped profile, with the
   block-bootstrap CI **excluding zero**.
2. **Paired ΔR non-inferiority**: the date-clustered CI's LOWER BOUND is
   **> −0.02**.
3. **Stability**: the improvement is **same-signed in both halves** of the window
   **and in ≥ 2 of the 3 years** present.
   - **The denominator is the EVALUATED population, not the full book.** "The
     window" and "the years present" both mean the OOS-STITCHED evaluated set —
     the union of the blocks' TEST dates, AFTER the burn-in exclusion — never
     the full era book. The v4 book spans three calendar years, but the
     post-burn-in evaluated set need not: early dates can fall entirely inside
     burn-in or a purged train set and belong to no TEST block. If the evaluated
     set spans only two calendar years, "≥ 2 of the 3 years" is read against the
     years actually present in it (i.e. all of them must be same-signed); the
     report prints the evaluated set's per-year date counts beside this clause so
     the denominator is visible rather than inferred.
   - **Halves, and what makes the clause TOTAL.** The window is split
     CHRONOLOGICALLY at the median evaluated date. The clause asks for the
     improvement to be SAME-SIGNED in both halves, so a half in which the
     improvement has **NO SIGN** — no affected dates fall in it, so there is
     nothing to compute — cannot be same-signed and the clause CANNOT be cleared:
     the cell fails clause 3 and, having failed a stability clause, is `NULL`
     under (V5) — unless G0 or clause 6 already made it `UNDERPOWERED`, which
     takes precedence. A signless half is never read as agreeing by default and is
     never dropped to let the surviving half decide. That is the whole rule, and
     it is total without a numeric floor.
   - **No thinness floor is committed here.** This registration sets **NO minimum
     affected-date count for a half**, and none may be applied at run time. The
     plan's Design section states this clause as "improvement same-signed in both
     halves and in ≥ 2 of 3 years" and names no such floor; a power-style floor
     that can flip a cell straight to `NULL` is a binding commitment, and this
     registration transcribes the Design section rather than adding one. What the
     run does instead: the report PRINTS each half's affected-date and
     affected-row counts beside this clause as a **DISCLOSED, NON-GATING
     observation**, so a reader can see when a cleared sign rests on a thin half.
     If a floor is wanted, it is registered separately, before any number from
     this run is seen, and binds a later run — never this one.
4. **Both pricing tiers same-signed** (`real` and `strike_expiry_tweak`).
5. **SECONDARY v3 is not opposite-signed.**
   - **A v3 cell with NO SIGN satisfies this clause VACUOUSLY**, and that is
     fixed here rather than left to the build. v3 is a SEPARATELY POWERED
     population (795 rows / 118 dates), so a v3 cell can be UNDERPOWERED on its
     own dates, or have no affected dates at all; in either case its improvement
     has no sign, it is therefore **not opposite-signed**, and clause 5 PASSES.
   - **This is deliberately NOT clause 3's treatment of a signless half, and the
     asymmetry is the point.** Clause 3 is a STABILITY clause: it asks the
     PRIMARY evaluated set to agree with ITSELF, so a half that cannot agree
     fails it. Clause 5 is a CORROBORATION clause: it asks a second,
     independently powered population not to CONTRADICT the primary, and a
     population that says nothing contradicts nothing. v3 "carries no verdict of
     its own" (see "Population and basis"); letting a thin v3 cell veto a primary
     candidate would hand it one.
   - **Vacuous is DISCLOSED, never silent.** When clause 5 is cleared this way
     the report prints it as `clause 5: VACUOUS (v3 cell UNDERPOWERED / no
     affected dates)` with the v3 census beside it, and any
     `CANDIDATE-FOR-INDEPENDENT-WINDOW` that rests on a vacuous clause 5 carries
     that annotation into the write-up, so the independent window is told what
     was NOT corroborated.
   - The plan's Design section states this clause as "SECONDARY v3 not
     opposite-signed" and names no signless case; the reading above is a
     registration-time resolution of that gap, flagged as such and fixed BEFORE
     the module is built, since the two readings give opposite verdicts
     (CANDIDATE vs NULL) on the same run output.
6. **≥ 25 affected DATES** — G0's date floor, RESTATED here. G0 already runs on
   the OOS-stitched evaluated set (see G0), so this clause restates rather than
   re-checks on a different population, and **G0's ≥ 60 affected-ROW floor binds
   on that same evaluated set even though only the date floor is restated in this
   clause.** Neither floor is ever evaluated on a pre-burn-in population.
7. **Not reactive**: **fewer than 50%** of the arm's exits are followed by the
   mark recovering past the exit. This is the `staged_exit` G2 continuation
   diagnostic, **reused here as a PASS CRITERION** — a cell that cuts drawdown by
   selling continuations has re-found the reactive null and does not pass,
   whatever its ΔR or its CI says.
   - **CONT is NOT part of ARM D's conjunction.** ARM D has no exits of its own —
     every position in its book exits on the shipped profile's rules — so "the
     arm's exits" has no referent for it and its continuation rate is the
     baseline's by construction. A sizing rule cannot re-find the reactive null,
     and evaluating CONT on it would print the shipped profile's number under an
     arm's name. **ARM D's conjunction is clauses 1–6**; see ARM D's section above
     and "ARM D's tokens" below for the token set that follows from that.

## Verdicts, worded now

The grammar is **TOTAL**: applied in the order below, first match wins, so every
combination of gate outcomes maps to **exactly one** token.

Let, for an evaluated cell: **DD** = clause 1; **R** = clause 2; **STAB** =
clauses 3, 4, 5; **DATES** = clause 6; **CONT** = clause 7. The ladder below is
written for the four EXIT arms; ARM D, which has no exits and for which CONT is
undefined, runs the same ladder with V3 skipped — see "ARM D's tokens" below.

- **(V0) Machinery.** Any of G-FORK, G-CAL, G-MTM, G1, G-COV fails → the run
  stops non-zero and **NO token is emitted for any arm**. A machinery failure is
  not a verdict about exits.
- **(V1) `UNDERPOWERED`.** G0 fails for the cell on the evaluated set (< 25
  affected dates OR < 60 affected rows) — equivalently, clause 6, which restates
  G0's date floor on that same population. Census printed, nothing
  concluded, no re-run on these dates. (Older reports call this token
  "POWER-STOPPED"; it is read as UNDERPOWERED.)
- **(V2) `CONTRARY`.** The cell is powered AND the arm is signed AGAINST itself
  beyond noise: the drawdown WORSENS by ≥ 15% with the bootstrap CI excluding
  zero, **or** the paired ΔR CI lies ENTIRELY at or below −0.02. The rule is
  harmful on these dates, and that is recorded as a finding.
- **(V3) `REACTIVE-AGAIN`.** The cell is powered, is not CONTRARY, **clears R**
  (ΔR CI lower bound > −0.02), and **fails CONT** (≥ 50% of its exits are
  followed by the mark recovering past the exit). Whatever DD and STAB say, the
  cell sold continuations; the thread is closed for these dates. This is the
  outcome the prior evidence predicts, and naming it now is the point of
  registering CONT as a criterion.
- **(V4) `CANDIDATE-FOR-INDEPENDENT-WINDOW`.** The cell is powered, is not
  CONTRARY, and clears **all** of DD, R, STAB, DATES and CONT. Not a ship — a
  queue.
- **(V5) `NULL`.** Every remaining evaluated cell. This is the catch-all that
  makes the grammar total, and it explicitly covers: DD fails; STAB fails; R
  fails without being CONTRARY; and a cell that fails CONT while its R clause had
  already failed (which is NOT REACTIVE-AGAIN, because REACTIVE-AGAIN is reserved
  for a cell whose R clause CLEARED).

### ARM W's control token

ARM W emits a cell verdict under the ladder above, and additionally ONE
arm-level token, also total:

- **`PROD-ROBUST`** — the WF-selected OOS book's cell verdict is `NULL` or
  `CONTRARY`. It was powered, it was evaluated, and **no walk-forward-selected
  configuration beat PROD out of sample.** That is the affirmative reading of a
  null here, and it is the result the rest of the study is measured against.
- `UNDERPOWERED` — the WF cell is UNDERPOWERED. **PROD-ROBUST is NOT claimed**;
  too few dates to say whether PROD survived.
- `REACTIVE-AGAIN` — the WF cell is REACTIVE-AGAIN. Selection did move the curve,
  by selling continuations. Not PROD-ROBUST.
- `CANDIDATE-FOR-INDEPENDENT-WINDOW` — the WF cell clears the full conjunction.
  PROD-ROBUST is refuted, and the candidate is queued like any other.

### ARM D's tokens

ARM D takes **FOUR** of the five tokens, each printed with a **`SECONDARY-`
prefix**: `SECONDARY-UNDERPOWERED` (V1), `SECONDARY-CONTRARY` (V2),
`SECONDARY-CANDIDATE-FOR-INDEPENDENT-WINDOW` (V4, on clauses 1–6) and
`SECONDARY-NULL` (V5, still the catch-all).

**`SECONDARY-REACTIVE-AGAIN` (V3) is never emitted.** CONT is dropped from ARM
D's conjunction — a sizing rule moves no exit and so cannot re-find the reactive
null — and the ladder is therefore applied to ARM D with **V3 SKIPPED**. V5
remains the catch-all, so the grammar stays **TOTAL** for ARM D: every gate
vector still maps to exactly one token.

ARM D's G0 and clause-6 counts use ARM D's own SIZING definition of "affected",
fixed in its arm section above; clauses 1–6 are otherwise evaluated exactly as
for the exit arms. No ARM D token is an exit finding and none may be quoted as
one. The most a `SECONDARY-CANDIDATE` can do is queue an f4 registration.

## Anti-tuning

- **The grids above are FINAL.** `pt`/`sl`/`tef` at 36 configurations; `k` at
  three values; `X` at two, plus exactly ONE volume variant; ARM U at two
  variants (added to `sl .75`, replacing `sl`); `d` at two values. ARM P has no
  grid.
- **Nothing is added after the first run**, and **a cell that fails is not
  re-cut** — not on a sub-population, not on a different window, not with a
  moved threshold.
- **Every cell is reported regardless of outcome**, including the ones that lose
  and the ones that power-stop.
- No threshold is moved after a number is seen. The train objective, the 0.02
  tolerance, the tie order, the block size, the embargo and the power floors are
  all fixed by this document.
- **Any build-time deviation is appended to this file as a dated "wording
  correction"** and never made as a silent change.
- `protocol.walk_forward_splits` (SELECTION) and `year_epoch_split` /
  `sign_stable` (STABILITY cuts) are different cuts over the same dates. They are
  separate calls and are never interchanged.

## Ship criteria

**Nothing ships from this run.** A `CANDIDATE-FOR-INDEPENDENT-WINDOW` queues an
independent-window confirmation — the live 2026-08/09 dates, once their options
have expired and been priced — before it may be proposed for
`docs/deployment-rules.md`.

**ARM D can only ever queue an f4 registration.** It cannot ship a sizing rule,
and it cannot be cited as an exit result.

A `PROD-ROBUST` outcome ships nothing either; it RETAINS the shipped profile and
records that its knobs survived out-of-sample selection on these dates.

## Build notes

*Not part of the registration — implementation, not commitment. The binding
design is above; the file inventory is the plan's own "Files" section
(`melodic-weaving-lynx.md`), which this section points at rather than restates.*

- New: `scripts/backtest_study/lib/exit_overlays.py` (composition wrappers around
  the FROZEN harness — `atr_stop`, `oi_unwind`, `vol_climax`, `partial_scaleout`,
  `knob_profile`, `compose`, `make_replayer` / `make_blockwise_replayer`, plus
  the `load_oi` reader) and
  `scripts/backtest_study/f2_management/exit_drawdown.py` (the study; args
  `--era`, `--population primary|all`, `--arms`;
  `DESIGNED_REFUSAL_EXIT_CODES = {2, 3}`).
- Edited: `scripts/backtest_study/f4_deployment/account_sim.py` gains a
  `replayer=None` kwarg on `simulate()` and the `Cfg.dd_throttle` hook — both
  no-ops on the default path, byte-identical output required.
  `scripts/study_map/catalog.py` gains the `Study(family="management",
  state="open", …)` entry (the test suite fails without one).
- Tests: `tests/test_exit_overlays.py` (G-FORK identity against the committed
  `tests/test_harness_replay.py` fixture; ATR / OI / partial unit cases; the leak
  test) and `tests/test_exit_drawdown.py` (walk-forward stitching uses only train
  dates; the verdict grammar has no hole — every gate vector maps to exactly one
  token).
- Traps to encode rather than rediscover: memo-key collisions between overlay
  parameters (the 2026-08-13 G5 bug class — the memo key must be EXTENDED with
  the overlay parameters, and the wrapper must re-do `replay_sized`'s scaling
  block rather than call it as a black box); `t.grid` is a weekday grid;
  `study_review --dry-run` clobbers artifacts and a bare `make backtest` doubles
  rows — neither is run.
- Data: the coverage census runs BEFORE the study; gaps are filled with
  `scripts/collector/fetch_underlying_ohlc.py --tickers … --skip-existing`,
  followed by `scripts/backup_research_caches.py push`.
- Run as `python -m scripts.backtest_study run exit_drawdown` (v4) and
  `… --era v3`; record with `make study-record`; grade with
  `python -m scripts.study_review exit_drawdown` (never `--dry-run`).

---

## Wording correction — 2026-09-05 (build)

_Appended at build time, per "Anti-tuning": "Any build-time deviation is
appended to this file as a dated 'wording correction' and never made as a
silent change." Nothing above is edited; this section records two build-time
readings of **G1**, both of them narrowing an implementation detail of the
GATE, neither of them touching an arm, a grid, a threshold, a population, a
criterion or a verdict._

**1. "ONE SESSION FORWARD" is one session of the RULE'S OWN GRID, not one row
of the cached file.** G1 says "shift every auxiliary series (bars, OI, volume)
ONE SESSION FORWARD". An option-history or OHLC file carries dates the
position's grid never reads — before the signal date, after the exit, and any
session the WEEKDAY grid skips — so shifting on the file's key order can pull a
value the rule never saw onto a grid session, which is not "one session later"
and makes the gate fire on rows that leak nothing. The shift is therefore
applied on `t.grid`: session `i` carries what session `i-1` carried, MISSING
stays MISSING, and keys off the grid are untouched. Measured on the v4 PRIMARY
population, this is the difference between 57 spurious "moved earlier" rows and
zero. ARM U additionally holds bars at or before the ENTRY session fixed, so
the entry-frozen ATR14 — a SCALAR computed off bars `<= entry` by construction
— is not re-estimated; the gate then measures the information set rather than
the ATR.

**2. G1's DIRECTION half is read on ARM O's volume LEG, not on its
conjunction.** ARM O's volume variant fires on a volume spike **AND** a mark
that closed against the position. Only the volume half is governed by the
series G1 shifts, so delaying the volume while the mark stays put RE-PAIRS the
two legs: a spike that missed an adverse mark on its own session can land on
one a session later, ahead of the original firing. That is an artifact of
shifting one leg of a conjunction, not a rule reading the future, and a literal
reading of G1 would fail a correct rule for it. So for that variant alone, "no
exit moves EARLIER" is evaluated on the volume leg in isolation, and the
conjunction's own earlier-firings are PRINTED as a disclosed, non-gating count
beside it. The probe is pinned to the rule by a coherence check — the
conjunction can only ever fire at or after its own volume leg — and a non-zero
coherence failure FAILS G1, so the two cannot drift apart silently. The
"at least one exit CHANGES" half is unchanged and is still read on the rule
itself.

Both readings tighten what the gate measures; neither weakens what it would
refuse. The ATR stop and the OI unwind are gated on both halves of G1 exactly
as registered.

---

## Wording correction — 2026-09-05 (build, second)

_Appended at build time, per "Anti-tuning": "Any build-time deviation is
appended to this file as a dated 'wording correction' and never made as a
silent change." Nothing above is edited. The first correction of this date
recorded two readings of **G1**; this one records the deviations found by the
build review of the module. **(a)–(c) are genuine deviations from the text
above; (d)–(e) are readings of a gate's implementation, recorded here rather
than left in report prose. None of them changes an arm, a grid, a threshold, a
population, a criterion, a verdict token or the ladder.**_

**(a) ARM P: the ledger holds the WHOLE reserve until the LATER half exits.**
ARM P above says the two synthetic positions are modelled "so `book_curves` sees
valid per-position windows and **the ledger releases half the reserve at the
FIRST exit**". `account_sim.simulate()` carries ONE exit session per position and
cannot release half a reserve, and `simulate()` is not forked for this study —
the whole module is a composition around frozen machinery. So the LEDGER-facing
blend (`partial_replayer`) reports `days_held` as the LATER of the two halves and
the reserve is released then. This is CONSERVATIVE against the registered
release: holding a reserve longer can only ever admit FEWER later positions,
never more, so no ARM P number is flattered by it. The CURVE is unaffected and
sees the registered shape — `split_positions()` re-splits every ARM P position
into its two halves, each with its own contract count and its own exit session,
before `book_curves` is called. The deviation is printed in ARM P's census.

**(b) ARM D: the walk-forward selection COLLAPSES to the modal block choice.**
ARM D above says `d` is "chosen walk-forward exactly as every other threshold
here is". `Cfg.dd_throttle` is ONE value for a whole simulation — a ledger
cannot carry a different `d` per block — so the stitched OOS book runs the MODAL
block choice and the blocks whose TRAIN fit chose the other value are run under
it. This is a property of the ledger, not a tuning choice, and it is disclosed
three ways: the per-block selection table prints what each block picked, the
collapse itself is printed with the modal value named, and **every grid value's
own stitched OOS book is printed beside it** so a reader can see what the
collapse cost. ARM D remains SECONDARY and unshippable from this family.

**(c) ARM P's account-level drawdown is WITHHELD in dollars by default.** The
"dollars ban is scoped" section above requires "an explicit operator ACK before
the module is built", and states the ALTERNATIVE reading — no dollar drawdown
figure for ARM P, the co-primary quoted in R and as a percentage of starting
capital — for the case where the operator reads the ban as unscoped. **No ACK
has been recorded.** The module was therefore built to the ALTERNATIVE reading
as its DEFAULT: ARM P's account-level max drawdown, its improvement and the
improvement's block-bootstrap CI bounds are all printed as a share of starting
capital, with a banner naming the open item; `--arm-p-dollars` prints the dollar
levels for whoever holds the ack. **The verdict is identical either way** —
clause 1 is evaluated on the improvement RATIO, which is scale-free — so this
resolves the presentation and defers, rather than pre-empts, the operator's
choice. If the ack is given for the SCOPED reading, the flag becomes the default
and this paragraph is superseded by a further dated correction; the ack is not
retro-fitted by report prose.

**(d) Clause 5's referent is the sibling era's RECORDED cells, and its absence
is VACUOUS.** The two eras are two separate processes, so each run records its
own cells (verdict, improvement ratio, power) in a per-era sidecar under
`backtests/study_output/` and reads the SECONDARY era's if one is on disk; the
sidecar names its own era and one that says otherwise is refused, so the eras
cannot be crossed. When the v3 run has not been recorded, the clause is VACUOUS
and printed as such — the same disclosure the registration fixes for a v3 cell
with no sign, and for the same reason (a population that has not spoken
contradicts nothing). A recorded, POWERED, opposite-signed v3 cell FAILS the
clause and blocks the candidate, which is the behaviour the clause was written
for and which a hardcoded pass could not deliver.

**(e) G1's "at least one exit CHANGED" half is tallied PER VARIANT.** The gate's
stated purpose for that half is per-series — "the first half proves the series
is actually being read". One counter aggregated over every exercised variant
lets a series that is in fact never read (a wiring bug returning an empty map)
hide behind a variant whose series does change, so each EXERCISED variant must
change at least one firing session on its own and the per-variant table is
printed. This tightens what the gate refuses; it weakens nothing. The gate's
series are also read through the SAME loaders the arms are wired to, so it
probes what the run reads rather than a parallel read of the same files.

---

## Wording correction — 2026-09-05 (build, third)

_Appended at build time, per "Anti-tuning": "Any build-time deviation is
appended to this file as a dated 'wording correction' and never made as a
silent change." Nothing above is edited. The build review of the module found
one of the SECOND correction's own resolutions to be wrong, and one gap in the
"Bar for a candidate" conjunction that the registration never resolved. **(f)
SUPERSEDES paragraph (b) of the second correction of this date; (g) fixes a
reading the registration left open on a verdict-affecting clause. Neither
changes an arm, a grid, a threshold, a population, a criterion or a verdict
token.**_

**(f) ARM D's collapse is to the EARLIEST block's choice, not the MODAL one.
This supersedes (b).** Paragraph (b) of the second correction recorded that
`Cfg.dd_throttle` is ONE value for a whole simulation — true, and the reason a
sizing arm's per-block selection must collapse at all — and then resolved the
collapse to the MODAL block choice, framing that as "a property of the ledger,
not a tuning choice". **That framing was wrong, and the resolution with it.**
WHICH value the collapse lands on is not a property of the ledger; it is a
choice, and the modal one is LOOKAHEAD. This registration's binding rule is
"Thresholds are chosen per walk-forward block on TRAIN dates only … then
applied to that block's TEST dates". A modal collapse replays block 0's TEST
dates under a `d` selected using blocks 1..n's fits, whose TRAIN sets contain
dates at or after those very test dates — so the stitched book would not be out
of sample, and (b) neither said so nor labelled the cell. It is not cosmetic
either: on the v4 primary population one grid value throttles sessions and
changes the book while the other never fires, so the collapse decides the whole
ARM D cell.

The collapse is therefore to the **EARLIEST block's choice**, which uses no
information after its own TRAIN window and gives the stitched ARM D book the
same out-of-sample guarantee every exit arm's per-block dispatch gives. Block
indices are unique, so there is no tie to break. The disclosure (b) committed is
kept in full and unchanged: the per-block selection table prints what each block
picked, the collapse is printed with the collapsed value named, and **every grid
value's own stitched OOS book is printed beside it**. The collapse rule lives in
one function (`collapse_choice()`, called by `run_book()`), so no caller can
perform a different one while the report's prose describes this one. ARM D
remains SECONDARY and unshippable from this family.

**(g) Clause 4's SIGNLESS case is read STRICTLY, as clause 3's is.** "Bar for a
candidate" clause 4 asks for the improvement to be same-signed in BOTH pricing
tiers (`real` and `strike_expiry_tweak`). The registration spells out the
signless case for clause 3 (a half with no sign cannot be same-signed, so the
clause FAILS) and for clause 5 (a v3 cell with no sign contradicts nothing, so
the clause PASSES vacuously), and says nothing for clause 4 — leaving a
verdict-affecting reading to be inferred from `nan` propagation. It is fixed
here: a tier with NO SIGN — no positions in one of the two books, so there is no
improvement to compute — **cannot be same-signed and the clause is NOT
cleared**, exactly as for clause 3 and for the same reason. Clause 4, like
clause 3, is a STABILITY clause: it asks the PRIMARY evaluated population to
agree with ITSELF across a cut of its own rows, and a cut that cannot agree
fails it. Clause 5's vacuous pass is the CORROBORATION case and stays the
asymmetry the registration already argues for. The reading is PRINTED on the
clause-4 line of every cell, so a grader reads it rather than infers it.

---

## Wording correction — 2026-09-05 (build, fourth)

_Appended at build time, per "Anti-tuning": "Any build-time deviation is
appended to this file as a dated 'wording correction' and never made as a
silent change." Nothing above is edited. The two-analyst grading of the first
run reopened the MODULE on REPORTING defects — a grading defect reopens the
module, never the registration — and two of the repairs turned on readings this
file left ambiguous. **(h) resolves a mis-citation inside G-CAL; (i) fixes the
scope of clause 5's referent. Neither changes an arm, a grid, a threshold, a
population, a criterion or a verdict token.**_

**Not recorded here, because neither needed a reading of this file:** ARM P's
and ARM D's censuses now print in the G-COV block with ARM U's and ARM O's,
above every cell table (the registration's "a conditional figure printed above
its coverage line is a reporting defect" is unqualified, and the first run
printed ARM P's census BELOW the G0 cell table that already carried ARM P's
affected-row and affected-date counts); and one invocation now carries the
PRIMARY headline AND the `all` cut, which is what "run as a DISCLOSED SECONDARY
CUT and printed beside it" already says. Both were module defects against text
that was already correct.

**(h) G-CAL's parenthetical names the SELF-TEST invocation, which is the
opposite of the check.** G-CAL reads: "`account_sim`'s own gates **G2–G5** must
still pass with the DEFAULT replayer (`account_sim --selftest-gates`)." The
requirement — G2–G5 passing under the default replayer — is exactly right; the
parenthetical is not the command that shows it. `--selftest-gates` deliberately
INVERTS every one of those gates' expectations (it adds 1 to `days_held` in G2,
injects a $1 leak into G3's identity, and inverts G4's and G5's comparisons) so
that a healthy build must print `GATES: FAILED`. It is a check on the CHECKER,
not the check, and a run of it that PASSED would mean the gates were broken.

The registered gate is therefore read as: **`account_sim.run_gates` under its
DEFAULT (non-self-test) path, on the population this study deploys through, run
IN THIS PROCESS, with its per-gate PASS/FAIL lines printed inside this study's
own report; a failure fails G-CAL exactly as a `book_signature` mismatch does.**
The first build delegated the half to a separate `--selftest-gates` invocation
"outside this process" and printed no G2–G5 result at all, so the report
ASSERTED a gate whose outcome it did not carry — the two analysts split on it
precisely there (one graded G-CAL MET on the narrower printed claim, one
declined to grade it at all), which is what an un-carried sub-check does to a
reader. `run_gates` is CALLED, never copied: G2's calibration identity, G3's
ledger accounting, G4's selection identity and G5's outcome-blindness are
`account_sim`'s properties, and a second implementation of them here is how a
study and its host come to certify different things.

**(i) Clause 5's referent is the SECONDARY era's PRIMARY cell, never its `all`
cut.** "Population and basis" fixes two independent axes — the ERA (v4 PRIMARY,
v3 SECONDARY, never pooled) and the deployment POPULATION (`dense_episodes`
PRIMARY, `all` a disclosed secondary cut from which **no verdict is read**) —
and clause 5 is written on the first axis only ("SECONDARY v3 is not
opposite-signed"). Because `all` carries no verdict, an `all` cell is not a
verdict-carrying cell and cannot contradict one; this is a strict reading of
text already here, not new content. It is recorded because it is
VERDICT-AFFECTING and because the first build could violate it silently: the
cells sidecar the two eras exchange recorded only its ERA, so a v3 `all` run's
sidecar would have been read as v4 PRIMARY's clause-5 referent, crossing two
cuts exactly as a stale filename would cross two eras.

The sidecar therefore records its POPULATION beside its era, only the PRIMARY
cut writes one, and a sidecar that names any other population — or names none,
as the pre-correction files do — is REFUSED and clause 5 prints VACUOUS with the
reason, which is the same disclosure this registration already fixes for a v3
cell with no sign. One further consequence, and it is a repair rather than a
reading: the no-OOS path now records its cells before returning. A v3 primary
population with no surviving test block used to leave NO sidecar at all, so the
v4 clause 5 read VACUOUS for a reason that had nothing to do with v3's evidence;
an all-UNDERPOWERED sidecar is the honest referent there — cells with no sign,
read as vacuous-but-disclosed, with the file named rather than absent.
