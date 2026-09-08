## exit_drawdown — walk-forward exit hypotheses judged on account-level drawdown

_Registered 2026-09-05._

An f2 MANAGEMENT study. Frozen: the signal, the entry day, the structure, the
ladder pick order and the base sizing. An arm changes only what happens to an
ALREADY-OPEN position — and, for ARM D alone, the size of a NEW one. Every
threshold any arm uses is chosen OUT OF SAMPLE, on training dates only, and the
headline is read off the stitched out-of-sample book.

## Question

Does any exit rule — chosen without look-ahead — reduce the **account-level
mark-to-market drawdown** of the deployed book, without giving back its edge?

The operator's queued question is "MAX DRAWDOWN, not timing". `account_sim`
deploys the ladder through a \$25,000 ledger and reports what that book earns;
`lib/mtm_curve.py` marks the same book to market and reports what it went
through to earn it. No study has yet judged an exit rule on that curve, and no
exit knob in this repo has ever been chosen out of sample.

Five sub-questions — four about exits, one labelled SECONDARY about sizing:

| Sub-question | Why it is open |
|---|---|
| Out-of-sample selection of the knobs we already ship | All pt/sl/tef tuning to date was full-window and in-sample. `protocol.walk_forward_splits` (purged, expanding, 120-day embargo) exists and has never been pointed at the exit grid. |
| An underlying-price stop for DEBITS | Only credits were ever tried (the short-strike breach). `bear_giveback` located the give-back pattern in the UNDERLYING rather than in the mark. |
| A flow-unwind exit off the traded contract's OI PATH | `backtests/option_history_cache/` holds per-session `Open Int` and `Volume` for every priced leg; no study has read the OI path. |
| Partial scale-out | Exactly computable from stored paths, and never measured. |
| A deployment-level drawdown throttle (sizing, not exit) | The most direct lever on the account curve. Carried along only as a labelled comparator, so the reader can see whether exits or sizing move the curve. |

## What this is NOT

Not a re-run of any exit thread the record has already closed. Every family
below is a STANDING NULL, none of it is re-tested here, and each is named so a
later reader can check that no arm smuggles one back in.

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

- **The day-X / ±Y% / ±\$Z exit formula is `staged_exit`, and it is null.** It
  may not be re-registered under another anchor — not days-since-entry, not
  DTE-remaining. **No arm here is anchored on a session index or a P&L band at a
  session index.** ARM U triggers on the UNDERLYING's distance from the entry
  close in ATR units; ARM O on the traded contract's open-interest path; ARM P
  has no trigger at all.
- **Trigger-gated ENTRY is LATE-ENTRY** (`trigger_entry`, v4 + v3). No arm moves
  an entry: entry basis is next-open and the entry session is `t.grid[0]`.
- **No further text study.** No arm reads model prose, an invalidation line, a
  trigger line or a horizon.
- **`score_total` is decision-irrelevant** and the ML/selection search is closed:
  no arm re-cuts selection, and nothing here proposes a new selection clause.
- **`bear_call_spread` is intake-vetoed; bear debit is selection-vetoed at card
  §1.4** and lives in the §4 hedge sleeve only. This study inherits
  `account_sim`'s admissions unchanged and deploys no bear position the shipped
  ladder would not deploy.
- **v3 and v4 rows are never pooled.** Only the `real` and `strike_expiry_tweak`
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

**Why this is admissible anyway.** Every verdict in the table above was reached
on a per-row R estimand under IN-SAMPLE parameter choice. This study's headline
estimand differs in two independent ways, and both must hold for it to be worth
running:

1. **Account-level, mark-to-market, path-dependent.** The outcome is the maximum
   drawdown *in dollars* of one deployed \$25,000 ledger whose open positions are
   MARKED (`lib/mtm_curve.py`), not the mean of a per-row distribution. A rule
   can leave mean R untouched and still change that curve — through *when* the
   reserve is released, *which* positions are concurrently open, and how deep the
   marked book goes between entry and exit. Conversely, `hedge_portfolio` ARM M
   established that the close-bucketed curve UNDERSTATES this book's max drawdown
   by 40.2%. Per-row R is a proxy for this metric in neither direction, so the
   standing nulls above do not answer it.
2. **Out-of-sample selection.** Every threshold is fitted on TRAIN dates and
   applied to TEST dates. The in-sample plateau the pt/sl/tef grid already found
   is not the question; whether a plateau chosen blind survives on the dates it
   was not chosen on is.

Neither difference exempts an arm from the reactive diagnostic. **A rule that
cuts the drawdown by selling continuations has re-found the reactive null in new
clothes**, so the continuation diagnostic is registered below as a PASS CRITERION
(`REACTIVE-AGAIN`), exactly as `staged_exit` registered its G2 — not as a
footnote.

Finally: this is **not a hedging study**. It does not open, size or time a
sleeve, and it says nothing about §2.1's instrument question. It changes the
management of positions the ladder already deployed.

## Population and basis, fixed here

| Fixed | Value |
|---|---|
| Era | PRIMARY `--era current` (v4 — the 166-date book, the first with 2026 signal dates). SECONDARY `--era v3` (795 rows / 118 dates) is RUN and REPORTED and carries no verdict of its own. **Never pooled.** |
| Book | `load_book(include_bs=False)` — `real` and `strike_expiry_tweak` tiers only — with the proxy CALIBRATION GATE ON, as every deployment study loads it. |
| Deployment population | `account_sim`'s `dense_episodes` population is PRIMARY. The `all` population is run as a DISCLOSED SECONDARY CUT and printed beside it; no verdict is read from `all`. This mirrors how `account_sim` itself states its own result: FEASIBLE is explicitly a two-year, dense-episode claim. |
| Baseline | ALWAYS paired against the **SHIPPED** profile as `account_sim.profile_for` resolves it per row, including the bear-keyed variants, and **never** against a clean `DEBIT_PROD`. Comparing against clean `DEBIT_PROD` changed a decision twice in this repo's history; it measures the shipped profile's own value rather than the arm's. |
| Credit rows | Keep `CREDIT_PROD` in every arm. There is no validated credit replay to overlay, and no arm proposes one. Credit rows are carried so the ledger and the curve are the real book, not so a credit exit is tested. |
| Entry basis | Next-open; the entry session is `t.grid[0]`. |
| Row exclusions | Counted, never silent. Rows excluded by an arm's data requirements (below) are reported per arm with their counts before any conditional number is quoted (G-COV). |

### No-lookahead rules, binding

These are pre-registered. A violation of any of them invalidates the run.

**Splits.** Thresholds are chosen per walk-forward block on TRAIN dates only.
Splits come from
`walk_forward_splits(dates, block=15, embargo_days=P.PATH_CAP_DAYS (=120), min_train_dates=40)`
— purged, expanding, with the embargo equal to the path cap — and the chosen
configuration is applied to that block's TEST dates.

**The fit is two-stage per block.**

1. A cheap per-row prefilter: every grid configuration's TRAIN mean R via
   memoised `replay_sized`; keep the configurations within **0.02** of the best.
2. Among those survivors, run `simulate()` on the TRAIN `day_lists` only and pick
   the **smallest TRAIN MTM max drawdown** (`book_curves` → `path_stats`).

**The tie order, made TOTAL and fixed per arm.** Ties break in this order:

| Step | Break to | Live where |
|---|---|---|
| (i) | **PROD** | ARM W only — PROD is a grid point there and in no other arm's grid, so this step is INERT for every other arm |
| (ii) | the configuration with **fewer active rules** | every arm |
| (iii) | the configuration whose overlay **FIRES ON THE FEWEST TRAIN ROWS** — the most conservative survivor, the one closest to leaving the shipped profile alone | every arm |
| (iv) | the **LARGEST** parameter value (largest `k`, `X`, `d`) — deterministic, and points the same way as (iii) | every arm |

Steps (iii) and (iv) are **registration-time additions**, flagged as new binding
content for the operator's review: the plan states the tie-break generically
("tie → PROD, then fewer active rules"), but only ARM W's grid contains a PROD
point to tie back to, so for ARM U, ARM O and ARM D the plan's rule is not total
on its own. Nothing here is decided at build time.

**ARM U's, ARM O's and ARM D's grids contain NO "off" / no-overlay point, and
that is deliberate.** The walk-forward fit selects among an arm's OWN
configurations only; whether doing nothing would have been better is answered
by the arm-versus-SHIPPED comparison that every criterion in "Bar for a
candidate" is written against — not by letting the fit pick "no overlay". A
block on which no configuration beats doing nothing therefore still dispatches
a configuration onto its TEST dates, and that surfaces as a failed clause 1 or
as `CONTRARY`.
That is the honest reading of such a block, and the absence of an escape hatch is
registered here rather than added later.

**One stitched book.** One shared `account_sim.new_cache()` per era-run, and a
`date → block` map dispatches each position's configuration inside **ONE stitched
OOS `simulate()`**. The headline book is that stitched book.

**Burn-in is EXCLUDED and reported.** Dates before the first TEST block — the
dates that exist only to train the first fit — are excluded from the OOS headline
population, and the report prints a burn-in census (dates, rows, and the span
they cover) as its own line. They are **never** silently replayed under the
shipped profile and folded into the headline. The OOS population is exactly the
union of the blocks' TEST dates.

**In-sample bests are printed under a `DISCLOSURE, in-sample` header and carry
NO verdict.** They exist so a reader can see the size of the in-sample/OOS gap;
no criterion below may be evaluated on them.

**Information set at the moment of decision.** An exit decided at the close of
session `d` may read: spread marks ≤ `d`, underlying bars ≤ `d`, option `Volume`
≤ `d`, and option `Open Int` ≤ `d−1` — Barchart publishes open interest the next
morning, so same-session OI is not knowable at that close.

**ARM D reads only the ledger's MARKED equity as of the session's OPEN**, with
exits processed before entries, exactly as `simulate` already orders the day.

**G1 leak test (below) is the mechanical check on all of the above.**

## Plan-time observations, disclosed

Measured while the study was being designed, before any arm ran. They are
disclosed so no number here can be presented later as a result.

**The yardstick.** `account_sim`'s per-era record
([`../../study-results/f4_deployment/account_sim.md`](../../study-results/f4_deployment/account_sim.md))
carries, for era **v4** on the exports dated **2026-09-04 20:31** (inputs
`1b1ba3c`, sha `b007f95`, recorded 2026-09-04), the verdict `>>> FEASIBLE <<<`
on the PRIMARY dense-episode population. That run's headline cell:

```
n=148  dates=76  $22,217  meanR +0.348
maxDD $-3,750        worst session $-2,796
```

The drawdown is 15.0% of the \$25,000 starting capital. Those are the figures
this study is measured against, and they are read off that one export; the
arm-versus-shipped comparison below is computed inside each run, never against
these constants.

Two boundaries on that yardstick, disclosed with it:

- The SECONDARY full book on the same export FAILS A1 on 2026, and its A3
  drawdown is 35.7% of capital:

  ```
  n=260  dates=129  $21,855  meanR +0.231   maxDD $-8,920
  ```

  FEASIBLE is a dense-episode claim; nothing in it has seen 2026.
- `account_sim`'s own `print_equity` states that **open positions are not marked
  to market** on the basis it reports. The marked curve this study reads is
  `lib/mtm_curve.py` (`book_curves` → `path_stats`), which is a different and
  deeper curve; `hedge_portfolio` ARM M measured the close-bucketed
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
scope. It follows directly from the "Credit rows keep `CREDIT_PROD` in every arm"
clause in "Population and basis", which each of those arms then restates in its
own DEBIT ROWS ONLY paragraph. Nothing about which rows an arm touches differs
from the plan; the title is flagged here only because this file flags every word
that is not verbatim plan text.

### ARM W — walk-forward knob control

**What it does.** Re-picks the shipped exit knobs out of sample, and is the
honesty baseline for every other arm. Grid:
`pt ∈ {.60, .75, .90, 1.10}` × `sl ∈ {.50, .75, off}` × `tef ∈ {.60, .75, off}` —
**36 configurations, of which PROD is one grid point.** Train objective exactly
as fixed under "No-lookahead rules, binding". Because PROD is a grid point, tie
step (i) is live and the full four-step order applies; this is the one arm for
which it does. ARM W reports BOTH "WF-selected vs PROD" and "PROD itself", so the
reader can see how much of any arm's movement is walk-forward selection rather
than the rule under test.

**What it must not do. DEBIT ROWS ONLY.** The grid is searched and applied on
debit rows alone; CREDIT rows keep `CREDIT_PROD` unchanged, per "Population and
basis" above — no `pt`/`sl`/`tef` configuration from this grid is ever applied to
a credit spread's legs, and no credit exit is selected.

### ARM U — underlying ATR stop (debit verticals only)

**What it does.** Exits at the CLOSE of the first session where the underlying
close is against the position by **≥ k · ATR14**, measured from the
**ENTRY-session close**. `k ∈ {1.5, 2.0, 3.0}`, in two variants: **(a)** the ATR
stop is ADDED to `sl .75`; **(b)** the ATR stop REPLACES `sl`. Direction comes
from the structure (`bull_*` vs `bear_*`).

**What it triggers on.** **ATR14 is FROZEN AT ENTRY.** It is
`underlying_features.atr14_pct` — a **simple 14-session mean of true range, NOT
Wilder-smoothed** — multiplied by the entry close to give a dollar distance. This
study uses that definition as it stands and does not re-implement or smooth it.
The trigger is measured from the ENTRY close and cannot re-arm on a new peak.
That entry-anchored, non-re-arming property is what distinguishes it from the
three rejected trails, and it does not exempt it from the continuation
diagnostic.

**What it must not do.** Rows it cannot measure are excluded and counted, never
guessed:

| EXCLUDED and counted | Why |
|---|---|
| `atr14_pct` is `None` | the series is below its minimum observation count |
| rows priced on the close-only `Price~` fallback | no high/low, so no true range |

Split-rescaled tickers are fine — the ratio is taken within one bar series. **A
missing bar on a grid day is "unpriced, skip", never a zero move**: `t.grid` is a
WEEKDAY grid and holidays are unpriced sessions.

### ARM O — flow-unwind exit (debit verticals only)

**What it does.** Reads the traded contract's own flow, which no study has done.
Two variants, and only two:

| Variant | Exits when |
|---|---|
| OI drop | the lagged OI ≤ (1 − X) · `OI_max`, `X ∈ {0.25, 0.40}` |
| volume climax | leg volume(`d`) ≥ 3× its post-entry median AND the mark closed against the position |

`OI_max` is the RUNNING MAX of the entry LONG leg's `Open Int` over the sessions
since entry, read **LAGGED one session**: the value usable at session `grid[i-1]`
is the one dated `grid[i-2]`. There is exactly **One volume variant**.

**What it triggers on.** A new reader `load_oi(leg)` is required — there is none
today. It is modelled on `harness.Trade._load_underlying`, reading `Open Int`
through `lib.parsing.to_float`. **The volume median is EXPANDING and as-of `d`.**
It is taken over the leg's post-entry volumes on sessions **up to AND INCLUDING
`d`** — never over the position's whole holding period, which would read volume
dated AFTER `d` into `d`'s own trigger and is exactly the leak G1 exists to
catch. Stating the window here puts it in the specification rather than leaving
it to the build. Same-session `Volume` IS admissible (see "Information set at the
moment of decision": marks, bars and `Volume` are readable ≤ `d`; only `Open Int`
is lagged to ≤ `d−1`).

**What it must not do.**

- **DEBIT ROWS ONLY.** "The entry LONG leg" above means the long leg of a DEBIT
  vertical. CREDIT rows keep `CREDIT_PROD` unchanged, per "Population and basis"
  above; the flow-unwind rule is never applied to a credit spread's short leg,
  and no credit row is ever exited by this arm.
- **Blank OI is MISSING; OI literally 0 is a VALID full unwind.** The reader must
  distinguish the two — conflating them either fabricates exits or hides them.
  Rows with blank OI on **≥ 20% of their hold sessions are EXCLUDED and counted**.
- A missing OI value on a grid day is skipped exactly as an unpriced mark is; it
  is never read as a 100% drop.
- Sessions with a missing volume are SKIPPED, never read as zero: the median is
  taken over the observed values only, and a session whose expanding window holds
  too few observed volumes to form a median cannot fire the volume variant.

### ARM P — partial scale-out (debit verticals only)

**What it does.** Exact; there is nothing to select and no threshold to fit. Half
the contracts exit at `pt .90` as shipped; the other half replays the shipped
profile with `pt=None`. It is modelled as **TWO synthetic `Pos` per rec** (half
size each, each with its own exit session), so `book_curves` sees valid
per-position windows and the ledger releases half the reserve at the FIRST exit.

**`Resolved at build (2026-09-05):` the ledger holds the WHOLE reserve until the
LATER half exits.** `account_sim.simulate()` carries ONE exit session per
position and cannot release half a reserve, and `simulate()` is not forked for
this study — the whole module is a composition around frozen machinery. So the
LEDGER-facing blend (`partial_replayer`) reports `days_held` as the LATER of the
two halves and the reserve is released then. This is CONSERVATIVE against the
registered release: holding a reserve longer can only ever admit FEWER later
positions, never more, so no ARM P number is flattered by it. The CURVE is
unaffected and sees the registered shape — `split_positions()` re-splits every
ARM P position into its two halves, each with its own contract count and its own
exit session, before `book_curves` is called. The deviation is printed in ARM P's
census. The registered sentence stands as written; this records that the ledger
does not implement it and what it does instead.

**What it must not do. DEBIT ROWS ONLY.** "Half the contracts" splits a DEBIT
vertical's position. CREDIT rows keep `CREDIT_PROD` unchanged, per "Population
and basis" above — a credit row is never split, never scaled out, and never
exited by this arm.

**Odd contract counts**, which "half the contracts" leaves open: the `pt .90`
half takes `⌈n/2⌉` and the `pt=None` half `⌊n/2⌋`. A position scaled to **n = 1
cannot be split** — one half would be zero contracts, which is not a position —
so **n = 1 rows are EXCLUDED from ARM P and counted** in its census.

**Traceability of those two rules.** The `⌈n/2⌉`/`⌊n/2⌋` split and the `n = 1`
exclusion are **NOT transcribed from the plan's Design section**, which says only
"half the contracts". They resolve an edge case it left unspecified — a size-1
position cannot be halved into two positions — and are fixed HERE, before the
run, not at build time: new binding content for the operator's review, not plan
text. The exclusion is population-affecting, so its count prints in G-COV like
every other exclusion.

**Units.** Paired R = the mean of the two halves. R, not dollars, is quoted for
ARM P's per-row comparison, because the contract counts differ from the shipped
row's. The account-level drawdown co-primary is by construction a dollar figure
of the deployment and is reported as such for ARM P too, with that
non-comparability stated beside it.

**The dollars ban covers the per-row comparison only.** Two plan clauses
conflict: "Traps to encode" says "Quote R, not dollars, for ARM P (contracts
change)", while "Unit and metric" makes the dollar MTM max drawdown a co-primary
reported "for every arm and cell". This registration reads the trap as binding
ARM P's per-row and paired numbers only, where the contract counts differ; the
account-level drawdown is a whole-book figure of one \$25,000 ledger and is
reported in dollars for ARM P as for every other arm. Under the alternative
reading ARM P reports no dollar drawdown figure and quotes co-primary 1 in R and
as a percentage of starting capital. Because this chooses between two clauses
that contradict rather than elaborating one, it needed an explicit operator ACK
before the module was built — an ack, not merely the absence of an objection to a
documented interpretation — since the workflow's phase-1 instruction ("approving
this plan IS the operator's review of the commitments; the agent transcribes, it
does not redesign") reserves that choice for the operator. Whichever reading is
taken is recorded in this section, never left to report prose.

**STATUS: ACK RECORDED 2026-09-08 — the SCOPED reading above is the one in
force.** The operator chose dollars as the more representative way to show a
whole-book figure.

| Period | What the module prints for ARM P |
|---|---|
| After the ACK (now) | The account-level drawdown, its improvement and the improvement's CI bounds in dollars by default; `--arm-p-share` prints them as a share of starting capital instead |
| 2026-09-05 build until the ACK | The ALTERNATIVE reading as the default: those three figures printed as a SHARE OF STARTING CAPITAL, behind a banner naming the open item, with `--arm-p-dollars` (since removed) printing the dollar levels. The CI there is the improvement's block-bootstrap CI |

No graded run displayed either presentation: every ARM P cell on the 2026-09-05
runs of both eras was UNDERPOWERED and printed its census only, so the graded
artefacts are unchanged by the ACK. Clause 1 is evaluated on the improvement
RATIO, which is scale-free, so the verdict is identical either way — this settled
the PRESENTATION only, and the ack is recorded here rather than added later by
report prose.

### ARM D — drawdown throttle (SECONDARY; sizing, not exit)

**What it does.** Carried so the reader can see whether exits or SIZING move the
account curve. In `simulate`, when marked equity ≤ (1 − d) · running peak, new
positions size at **half** the risk budget until equity ≥ (1 − d/2) · peak.
`d ∈ {0.05, 0.10}`, chosen walk-forward exactly as every other threshold here is.

**What it triggers on.** Only the ledger's marked equity as of the session's
open.

**What it must not do.** ARM D is **labelled SECONDARY everywhere it is printed**
and **can never ship from this study**, whatever it prints. It is a sizing rule
and this is an f2 management registration; the most it can ever do is queue an f4
registration of its own.

**Per-block dispatch cannot apply to it.** ARM D's per-block choices must
collapse to a single value, and that collapse is an EXCEPTION to the per-block
dispatch rule above. The dispatch rule's own text is untouched; ARM D alone runs
one collapsed value, and no exit arm does.

**`Resolved at build (2026-09-05):` the collapse is to the EARLIEST block's
choice.** The registration's binding rule is "Thresholds are chosen per
walk-forward block on TRAIN dates only … then applied to that block's TEST
dates", with a `date → block` map dispatching each position's configuration.
`Cfg.dd_throttle` is ONE value for a whole simulation, so ARM D provably cannot
do that, and its per-block selection must collapse before a stitched book can be
run at all. The EARLIEST block's choice uses no information after its own TRAIN
window and gives the stitched ARM D book the same out-of-sample guarantee every
exit arm's per-block dispatch gives. Block indices are unique, so there is no tie
to break. The disclosure is kept in full: the per-block selection table prints
what each block picked, the collapse is printed with the collapsed value named,
and **every grid value's own stitched OOS book is printed beside it**. The
collapse rule lives in one function (`collapse_choice()`, called by `run_book()`),
so no caller can perform a different one while the report's prose describes this
one. ARM D remains SECONDARY and unshippable from this family.

**A superseded reading, recorded because the report argues by contrast with it.**
The first build-time resolution collapsed to the MODAL block choice, framing that
as "a property of the ledger, not a tuning choice". Both the framing and the
resolution were wrong: WHICH value the collapse lands on is a choice, and the
modal one is LOOKAHEAD — it replays block 0's TEST dates under a `d` selected
using blocks 1..n's fits, whose TRAIN sets contain dates at or after those very
test dates, so the stitched book would not be out of sample. It is not cosmetic
either: on the v4 primary population one grid value throttles sessions and
changes the book while the other never fires, so the collapse decides the whole
ARM D cell.

**What "affected" means for ARM D, fixed here.** ARM D is a SIZING rule. It has
no overlay and no exit reason of its own: it never changes an already-open row's
exit, so G0's general definition of "affected" ("the arm changed that row's
exit") is EMPTY for it. Read literally, every ARM D cell would then hold zero
affected dates and zero affected rows and be **vacuously UNDERPOWERED** whatever
the throttle did to the account curve. That is a defect of the general
definition, not a finding about sizing. For ARM D, and for ARM D only:

| Term | ARM D's definition |
|---|---|
| affected ROW | a position ENTERED while the throttle was ACTIVE — one actually sized at HALF the risk budget because marked equity at that session's open was ≤ (1 − d) · running peak. A position entered at the full budget is not affected, and neither is a position merely HELD through a throttled stretch |
| affected DATE | a signal date on which at least one affected row was entered |

G0's floors (**≥ 25 affected DATES and ≥ 60 affected ROWS**) and clause 6 are
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
the CONT drop, and the `SECONDARY-`prefixed token set (below, under "ARM D's
tokens") are **NOT transcribed from the plan's Design section**, which says only
that ARM D is "reported beside the exit arms only … Can never ship from this
study" — it defines no "affected" semantics for a sizing arm, no conjunction
restriction and no ARM-D token vocabulary. They resolve what it left
unspecified: G0 and the verdict grammar are both written in terms of an arm
CHANGING A ROW'S EXIT, and a sizing arm changes none, so read literally every
ARM D cell would be vacuously
UNDERPOWERED and V3 would have no referent. They are fixed HERE, before the run,
not at build time: **new binding content, flagged as such for the operator's
review** — exactly as ARM P's `⌈n/2⌉`/`⌊n/2⌋` split and `n = 1` exclusion are —
and not plan text. Each is population- or verdict-affecting, so ARM D's counts
print in G-COV and its token prints with its `SECONDARY-` prefix.

## Unit and metric

**Unit = the signal DATE.** Every confidence interval is date-clustered.

**A CELL** — the thing G0 powers, every clause in "Bar for a candidate" reads,
and the verdict ladder assigns exactly one token to — is one
**arm × variant × era × deployment population**:

| Arm | Variants |
|---|---|
| ARM U | added to `sl .75`; replacing `sl` |
| ARM O | OI drop; volume climax |
| ARM W, ARM P, ARM D | one each |

Walk-forward-SELECTED parameters (`pt`/`sl`/`tef`, `k`, `X`, `d`) are NOT cell
axes — they are chosen per block inside a cell, which is why a cell's report
names the per-block selections rather than a single value. ARM D is the exception
noted in its own section: its `d` cannot be dispatched per block and collapses to
one value for the whole simulation, so its report names both the per-block
choices and the collapsed value.

**Co-primaries**, both reported for every arm and cell (with ARM P's co-primary 1
quoted in dollars under the 2026-09-08 ACK — see ARM P's STATUS above):

1. **MTM max drawdown, in DOLLARS, of the OOS-stitched deployment** —
   `book_curves(target=TARGET_POSITION)` → `path_stats`. **Ulcer index** and
   **time-under-water** are printed beside it as path-shape context.
2. **Paired ΔR by DATE versus the shipped profile** — `boot_ci_paired_by_date`.

The drawdown-improvement CI uses the block-bootstrap `improvement()` pattern
already registered and used in `hedge_portfolio`.

**Never annualised. No Sharpe. No time-to-recover.** ARM P's per-row comparison
is quoted in R, never in dollars.

## Gates

Every gate is evaluated and printed. The machinery gates (G-FORK, G-CAL, G-MTM,
G1, G-COV) are RUN-LEVEL: a failure stops the run non-zero and **no verdict is
read for any arm**, because a failure there is a finding about the machinery and
not about exits.

**G0 — POWER. Runs first and blocks every criterion.** Per (arm × cell): **≥ 25
affected DATES and ≥ 60 affected ROWS**, where **"affected" means the arm changed
that row's exit**. Below either floor, the cell is UNDERPOWERED: its census is
printed, and no criterion is evaluated on it. Counts come from `len(records)`
after filters at run time — never from a stored expected figure.

- **G0 is evaluated on the OOS-STITCHED EVALUATED POPULATION** — the union of the
  blocks' TEST dates, AFTER the burn-in exclusion and AFTER that arm's own data
  exclusions — the same population every clause in "Bar for a candidate" reads.
  BOTH floors are measured on it from the start; neither is ever taken on a
  pre-burn-in or full-book population. Clause 6 is a RESTATEMENT of the date
  floor for readability, not a second and different check; the ROW floor needs no
  restatement because it was never measured anywhere else.
- **ARM D is the one exception, and it is defined here, not left to the build.**
  ARM D changes no row's exit, so this definition is empty for it and would make
  every ARM D cell vacuously UNDERPOWERED. G0 counts ARM D's cells on the SIZING
  definition of "affected" fixed in ARM D's section above (a row entered at the
  halved budget; a date on which such a row was entered). That definition is ARM
  D's alone.

**G-FORK — the overlay is a composition, not a fork.** Every overlay, with its
own rule DISABLED, must reproduce `harness.replay` EXACTLY — on ALL rows, in BOTH
eras. `lib/harness.py` is FROZEN and is not edited. One disagreement fails the
run.

**G-CAL — the host simulation is unchanged.** `account_sim`'s own gates
**G2–G5** must still pass with the DEFAULT replayer
(`account_sim --selftest-gates`). The replayer hook must be a no-op when it is
not used.

**`Resolved at build (2026-09-05):` the parenthetical names the SELF-TEST
invocation, which is the opposite of the check.** The requirement — G2–G5 passing
under the default replayer — is exactly right; the parenthetical is not the
command that shows it, and it stands above as the erroneous citation it is.
`--selftest-gates` deliberately INVERTS every one of those gates' expectations
(it adds 1 to `days_held` in G2, injects a \$1 leak into G3's identity, and
inverts G4's and G5's comparisons) so that a healthy build must print
`GATES: FAILED`. It is a check on the CHECKER, not the check, and a run of it
that PASSED would mean the gates were broken. The registered gate is therefore
read as: **`account_sim.run_gates` under its DEFAULT (non-self-test) path, on the
population this study deploys through, run IN THIS PROCESS, with its per-gate
PASS/FAIL lines printed inside this study's own report; a failure fails G-CAL
exactly as a `book_signature` mismatch does.** `run_gates` is CALLED, never
copied: G2's calibration identity, G3's ledger accounting, G4's selection
identity and G5's outcome-blindness are `account_sim`'s properties, and a second
implementation here is how a study and its host come to certify different things.
**The printing requirement is this reading's addition, not the registered
gate's.** The first build delegated that half to a separate `--selftest-gates`
invocation "outside this process" and printed no G2–G5 result at all, so the
report ASSERTED a gate whose outcome it did not carry; the two analysts then
split on it, one grading G-CAL MET on the narrower printed claim and one
declining to grade it at all.

**G-MTM — the curve and the ledger agree.** The mark-to-market value at exit must
equal the overlay's own dollars for that position, within `TOL_DOLLARS`.

**G1 — LEAK GUARD.** Shift every auxiliary series (bars, OI, volume) ONE SESSION
FORWARD and assert that **at least one exit changes** AND that **no exit moves
EARLIER** than the original. The first half proves the series is actually being
read; the second proves the rule is not reading the future.

- **"ONE SESSION FORWARD" means one session of the RULE'S OWN GRID, not one row
  of the cached file.** An option-history or OHLC file carries dates the
  position's grid never reads — before the signal date, after the exit, and any
  session the WEEKDAY grid skips — so shifting on the file's key order pulls a
  value the rule never saw onto a grid session, which is not "one session later"
  and fires the gate on rows that leak nothing. The shift is applied on `t.grid`:
  session `i` carries what session `i-1` carried, MISSING stays MISSING, and keys
  off the grid are untouched. ARM U additionally holds bars at or before the
  ENTRY session fixed, so the entry-frozen ATR14 — a SCALAR computed off bars
  `<= entry` — is not re-estimated, and the gate measures the information set
  rather than the ATR.
- **`Resolved at build (2026-09-05):` the DIRECTION half is read on ARM O's
  volume LEG, not on its conjunction.** ARM O's volume variant fires on a volume
  spike **AND** a mark that closed against the position. Only the volume half is
  governed by the series G1 shifts, so delaying the volume while the mark stays
  put RE-PAIRS the two legs: a spike that missed an adverse mark on its own
  session can land on one a session later, ahead of the original firing. That is
  an artifact of shifting one leg of a conjunction, not a rule reading the future,
  and a literal reading of G1 would fail a correct rule for it. So for that
  variant alone, "no exit moves EARLIER" is evaluated on the volume leg in
  isolation, and the conjunction's own earlier-firings are PRINTED as a
  disclosed, non-gating count beside it. A coherence check pins the probe to the
  rule — the conjunction can only ever fire at or after its own volume leg — and
  a non-zero coherence failure FAILS G1, so the two cannot drift apart silently.
  **This is a SCOPING of the registered gate and it is outcome-bearing.** G1 as
  registered asks that no exit moves EARLIER, with no variant carve-out, and a G1
  failure is (V0): the run stops non-zero and NO token is emitted for any arm.
  Read literally, the conjunction's earlier-firings on the graded run would have
  voided it; they are disclosed as a count instead, and the coherence check
  replaces the literal reading. The ATR stop and the OI unwind are gated on both
  halves of G1 as registered.
- **`Resolved at build (2026-09-05):` the "at least one exit CHANGED" half is
  tallied PER VARIANT.** The gate's stated purpose for that half is per-series —
  "the first half proves the series is actually being read". One counter
  aggregated over every exercised variant lets a series that is in fact never
  read (a wiring bug returning an empty map) hide behind a variant whose series
  does change, so each EXERCISED variant must change at least one firing session
  on its own and the per-variant table is printed. The gate reads its series
  through the SAME loaders the arms are wired to, so it probes what the run reads
  rather than a parallel read of the same files. **This is STRICTER than the
  registered gate**, which asks for one run-level assertion that at least one exit
  changes. It tightens what G1 refuses and weakens nothing, but it was decided
  while the module was built and is not a pre-commitment: a variant that exercises
  no rows is reported NOT EXERCISED rather than failing the gate.

**G-COV — COVERAGE, printed BEFORE any conditional number.** Per arm: bar
coverage (tickers with and without a cached series; rows dropped for `Price~`
close-only fallback; rows dropped for a `None` `atr14_pct`), OI coverage (entry
legs with a usable path; rows dropped at the ≥20%-blank threshold), and ARM P's
n = 1 exclusions. A conditional figure printed above its coverage line is a
reporting defect.

## Bar for a candidate

A candidate must clear the WHOLE conjunction, on the **PRIMARY** population, on
the **OOS-stitched** book. Failing any one clause is failing.

| # | Clause | The bar |
|---|---|---|
| 1 | Max drawdown improves | by **≥ 15%** versus the shipped profile, with the block-bootstrap CI **excluding zero** |
| 2 | Paired ΔR non-inferiority | the date-clustered CI's LOWER BOUND is **> −0.02** |
| 3 | Stability over time | the improvement is **same-signed in both halves** of the window **and in ≥ 2 of the 3 years** present |
| 4 | Stability across pricing tiers | **Both pricing tiers same-signed** (`real` and `strike_expiry_tweak`) |
| 5 | Corroboration | **SECONDARY v3 is not opposite-signed** |
| 6 | Dates | **≥ 25 affected DATES** — G0's date floor, RESTATED |
| 7 | Not reactive | **fewer than 50%** of the arm's exits are followed by the mark recovering past the exit |

**Clause 3 — the denominator is the EVALUATED population, not the full book.**
"The window" and "the years present" both mean the OOS-STITCHED evaluated set —
the union of the blocks' TEST dates, AFTER the burn-in exclusion — never the full
era book. The v4 book spans three calendar years; the post-burn-in evaluated set
need not, because early dates can fall entirely inside burn-in or a purged train
set and belong to no TEST block. If it spans only two calendar years, "≥ 2 of the
3 years" is read against the years actually present in it, so all of them must be
same-signed. The report prints the evaluated set's per-year date counts beside
this clause, so the denominator is visible rather than inferred.

**Clause 3 — halves, and what makes the clause TOTAL.** The window is split
CHRONOLOGICALLY at the median evaluated date. A half in which the improvement has
**NO SIGN** — no affected dates fall in it, so there is nothing to compute —
cannot be SAME-SIGNED, so the clause CANNOT be cleared: the cell fails clause 3
and, having failed a stability clause, is `NULL` under (V5), unless G0 or clause 6
already made it `UNDERPOWERED`, which takes precedence. A signless half is never
read as agreeing by default and never dropped to let the surviving half decide.
That is the whole rule, and it is total without a numeric floor.

**Clause 3 — no thinness floor is committed here.** This registration sets **NO
minimum affected-date count for a half**, and none may be applied at run time.
The plan's Design section states the clause as "improvement same-signed in both
halves and in ≥ 2 of 3 years" and names no such floor; a power-style floor that
can flip a cell straight to `NULL` must be registered in advance. Instead the
report PRINTS each half's affected-date and affected-row counts beside the clause
as a **DISCLOSED, NON-GATING observation**, so a reader can see when a cleared
sign rests on a thin half. A floor, if wanted, is registered separately before any
number from this run is seen and binds a later run — never this one.

**Clause 4 — a tier with NO SIGN cannot be same-signed, and the clause is NOT
cleared.** A tier with no
positions in one of the two books has no improvement to compute, cannot agree
with the other, and so FAILS the clause — as in clause 3 and for the same reason.
Clause 4 is a STABILITY clause: it asks the PRIMARY evaluated population to agree
with ITSELF across a cut of its own rows, and a cut that cannot agree fails it.
Clause 5's vacuous pass is the CORROBORATION case and stays the asymmetry argued
for there. The reading is PRINTED on the clause-4 line of every cell, so a grader
reads it rather than infers it.

**Clause 5 — a v3 cell with NO SIGN satisfies this clause VACUOUSLY**, fixed here
rather than left to the build. v3 is a SEPARATELY POWERED population (795 rows /
118 dates), so a v3 cell can be UNDERPOWERED on its own dates or have no affected
dates at all; either way its improvement has no sign, it is therefore **not
opposite-signed**, and clause 5 PASSES. This is deliberately NOT clause 3's
treatment of a signless half. Clause 3 asks the PRIMARY evaluated set to agree
with ITSELF, so a half that cannot agree fails it; clause 5 asks a second,
independently powered population not to CONTRADICT the primary, and a population
that says nothing contradicts nothing. v3 "carries no verdict of its own" (see
"Population and basis"), and letting a thin v3 cell veto a primary candidate
would hand it one.

**Clause 5 — vacuous is DISCLOSED, never silent.** The report prints `clause 5:
VACUOUS (v3 cell UNDERPOWERED / no affected dates)` with the v3 census beside it,
and any `CANDIDATE-FOR-INDEPENDENT-WINDOW` resting on a vacuous clause 5 carries
that annotation into the write-up, so the independent window is told what was NOT
corroborated.

**`Resolved at build (2026-09-05):` clause 5's mechanism is a sidecar the two
eras exchange, and an absent or refused referent is VACUOUS too.** The two eras
are two separate processes, so each run records its own cells (verdict,
improvement ratio, power) in a per-era sidecar under `backtests/study_output/`
and reads the SECONDARY era's if one is on disk. The sidecar names BOTH its era
and its population, only the PRIMARY cut writes one, and a sidecar naming another
era, another population, or none at all is REFUSED — a v3 `all` run's sidecar
read as v4 PRIMARY's clause-5 referent would cross two cuts exactly as a stale
filename would cross two eras. When the v3 run has not been recorded, or its
sidecar is refused, clause 5 is VACUOUS and printed with the reason: a population
that has not spoken contradicts nothing. A recorded, POWERED, opposite-signed v3
PRIMARY cell FAILS the clause and blocks the candidate, which is what the clause
was written for and what a hardcoded pass could not deliver. **Note the widening,
and read it as such**: the registered vacuous case is a v3 cell that RAN and had
no sign — the registration commits that v3 "is RUN and REPORTED" — so treating an
unrun or refused sidecar as vacuous extends a criterion pass to an artifact-level
failure the registered grammar would otherwise route through machinery. The
no-OOS path therefore records its cells BEFORE returning: a v3 primary population
with no surviving test block must not leave NO sidecar, or v4's clause 5 would
read VACUOUS for a reason that had nothing to do with v3's evidence. An
all-UNDERPOWERED sidecar is the honest referent there — cells with no sign, read
as vacuous-but-disclosed, with the file named rather than absent.

**The referent is the SECONDARY era's PRIMARY cell, never its `all` cut.** "Population and basis" fixes two independent axes —
the ERA (v4 PRIMARY, v3 SECONDARY, never pooled) and the deployment POPULATION
(`dense_episodes` PRIMARY, `all` a disclosed secondary cut from which **no
verdict is read**) — and this clause is written on the first axis only. Because
`all` carries no verdict, an `all` cell cannot contradict a verdict-carrying one.
That is a strict reading of text already here rather than new content, and it is
stated because it is VERDICT-AFFECTING.

**Clause 5 — where those readings come from.** The plan's Design section states
the clause as "SECONDARY v3 not opposite-signed" and names no signless case. The
readings above resolve that gap, flagged as such and fixed BEFORE the module is
built, since the two readings give opposite verdicts (CANDIDATE vs NULL) on the
same run output.

**Clause 6 — why it restates rather than re-checks.** G0 already runs on the
OOS-stitched evaluated set (see G0), so this clause restates rather than
re-checks on a different population, and **G0's ≥ 60 affected-ROW floor binds on
that same evaluated set even though only the date floor is restated in this
clause.** Neither floor is ever evaluated on a pre-burn-in population.

**Clause 7 — this is the `staged_exit` G2 continuation diagnostic, reused here as
a PASS CRITERION.** A cell that cuts drawdown by selling continuations has
re-found the reactive null and does not pass, whatever its ΔR or its CI says.

**Clause 7 — CONT is NOT part of ARM D's conjunction.** ARM D has no exits of its
own, so "the arm's exits" has no referent for it and its continuation rate is the
baseline's by construction. **ARM D's conjunction is clauses 1–6**; see ARM D's
section above and "ARM D's tokens" below for the token set that follows.

## Verdicts, worded now

The grammar is **TOTAL**: applied in the order below, first match wins, so every
combination of gate outcomes maps to **exactly one** token.

Let, for an evaluated cell: **DD** = clause 1; **R** = clause 2; **STAB** =
clauses 3, 4, 5; **DATES** = clause 6; **CONT** = clause 7. The ladder below is
written for the four EXIT arms; ARM D, which has no exits and for which CONT is
undefined, runs the same ladder with V3 skipped — see "ARM D's tokens" below.

| Order | Token | When |
|---|---|---|
| (V0) | Machinery — **NO token is emitted for any arm** | Any of G-FORK, G-CAL, G-MTM, G1, G-COV fails: the run stops non-zero. A machinery failure is not a verdict about exits |
| (V1) | `UNDERPOWERED` | G0 fails for the cell on the evaluated set (< 25 affected dates OR < 60 affected rows) — equivalently, clause 6, which restates G0's date floor on that same population. Census printed, nothing concluded, no re-run on these dates. (Older reports call this token "POWER-STOPPED"; it is read as UNDERPOWERED.) |
| (V2) | `CONTRARY` | The cell is powered AND the arm is signed AGAINST itself beyond noise: the drawdown WORSENS by ≥ 15% with the bootstrap CI excluding zero, **or** the paired ΔR CI lies ENTIRELY at or below −0.02. The rule is harmful on these dates, and that is recorded as a finding |
| (V3) | `REACTIVE-AGAIN` | The cell is powered, is not CONTRARY, **clears R** (ΔR CI lower bound > −0.02), and **fails CONT** (≥ 50% of its exits are followed by the mark recovering past the exit). Whatever DD and STAB say, the cell sold continuations; the thread is closed for these dates. This is the outcome the prior evidence predicts, and naming it now is the point of registering CONT as a criterion |
| (V4) | `CANDIDATE-FOR-INDEPENDENT-WINDOW` | The cell is powered, is not CONTRARY, and clears **all** of DD, R, STAB, DATES and CONT. Not a ship — a queue |
| (V5) | `NULL` | Every remaining evaluated cell. This is the catch-all that makes the grammar total, and it explicitly covers: DD fails; STAB fails; R fails without being CONTRARY; and a cell that fails CONT while its R clause had already failed (which is NOT REACTIVE-AGAIN, because REACTIVE-AGAIN is reserved for a cell whose R clause CLEARED) |

### ARM W's control token

ARM W emits a cell verdict under the ladder above, and additionally ONE
arm-level token, also total:

| Arm-level token | When |
|---|---|
| **`PROD-ROBUST`** | The WF-selected OOS book's cell verdict is `NULL` or `CONTRARY`. It was powered, it was evaluated, and **no walk-forward-selected configuration beat PROD out of sample.** That is the affirmative reading of a null here, and it is the result the rest of the study is measured against |
| `UNDERPOWERED` | The WF cell is UNDERPOWERED. **PROD-ROBUST is NOT claimed**; too few dates to say whether PROD survived |
| `REACTIVE-AGAIN` | The WF cell is REACTIVE-AGAIN. Selection did move the curve, by selling continuations. Not PROD-ROBUST |
| `CANDIDATE-FOR-INDEPENDENT-WINDOW` | The WF cell clears the full conjunction. PROD-ROBUST is refuted, and the candidate is queued like any other |

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
- **No deviation is silent.** A build-time deviation from this document is folded
  into the section it amends, so the file keeps stating ONE final design rather
  than a change log; what changed, when and why lives in git. The run's own report
  additionally PRINTS every deviation where it bites, so a reader of the report
  sees it without reading this file. A deviation that would change what a gate
  REFUSES, what an arm DOES, or how a clause is READ is folded in too, but never
  silently: it sits beside the text it amends under a bold
  `Resolved at build (date)` tag, so a reader can tell a ruling taken while the
  module was built from a commitment made before it, and it never relaxes a
  commitment. `scripts/study_review/` grades against THIS FILE alone.
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
- What the build measured, and why G1's shift is specified on `t.grid`
  (implementation evidence, not a study result, and no criterion is evaluated on
  it): shifting an auxiliary series on the cached file's key order instead of on
  `t.grid` produces **57** spurious "moved earlier" rows on the v4 PRIMARY
  population where the grid-relative shift produces zero.
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

### Build-time resolutions, by recorded label

The module, the graded report and the two analyst gradings cite the build-time
readings by these labels. Every label resolves to a section of this file.

| Recorded as | What it fixes | Where it lives now |
|---|---|---|
| 2026-09-05 (build), reading 1 | G1's shift is one session of the rule's own grid | The G1 bullet under "Gates"; its 57-row measurement is in "Build notes" above |
| 2026-09-05 (build), reading 2 — cited as "correction 2" | G1's DIRECTION half is read on ARM O's volume leg | The G1 bullet under "Gates", first `Resolved at build` paragraph |
| (a) of 2026-09-05 (build, second) | ARM P's ledger releases the reserve at the LATER half | ARM P, the "TWO synthetic `Pos`" bullet |
| (b) of 2026-09-05 (build, second) | ARM D collapses to the MODAL block choice | ARM D, "A superseded reading" — **SUPERSEDED by (f), recorded but not live** |
| (c) of 2026-09-05 (build, second) | ARM P's dollar drawdown is withheld by default — **CLOSED 2026-09-08**, dollars are the default | ARM P's STATUS bullet |
| (d) of 2026-09-05 (build, second) | clause 5 reads the sibling era's RECORDED cells | Clause 5's sidecar `Resolved at build` paragraph, narrowed by (i) |
| (e) of 2026-09-05 (build, second) | G1's CHANGE half is tallied per variant | The G1 bullet under "Gates", second `Resolved at build` paragraph |
| (f) of 2026-09-05 (build, third) | ARM D collapses to the EARLIEST block's choice | ARM D, the `Resolved at build` collapse paragraph |
| (g) of 2026-09-05 (build, third) | clause 4's signless tier is read strictly | Clause 4 under "Bar for a candidate" |
| (h) of 2026-09-05 (build, fourth) | G-CAL's parenthetical names the self-test | The G-CAL bullet under "Gates" |
| (i) of 2026-09-05 (build, fourth) | clause 5's referent is the SECONDARY era's PRIMARY cell | Clause 5, "The referent is the SECONDARY era's PRIMARY cell" |

Each of these readings was recorded while the module was built, and each is
tagged `Resolved at build` inline beside the text it amends, so a reader can
tell it from a commitment made before the build. The sequence of changes lives
in git — these readings were carried in a companion file,
`research/exit_drawdown-errata.md`, from 2026-09-05 until they were folded in
here on 2026-09-08.
