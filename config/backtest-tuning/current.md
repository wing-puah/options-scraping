# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index.

**State of play (2026-08-14, `selection_order` PRE-REGISTERED).** The one
follow-up `account_sim` left as pre-registerable — the delta-cap **ordering**
question — is **PRE-REGISTERED, not built and not run**:
[`pre-registrations/selection_order.md`](pre-registrations/selection_order.md).
Six frozen arms, each only a different `rank_fn` into
`protocol.ordered_by_day`, with tier membership, universe, sizing, caps and
exits held exactly as `account_sim` runs them — this is an ORDERING study, not
a selection study, and selection stays closed (new COLUMNS only). The decisive
arm is **O4, a seeded random control**: an arm must beat the random band, not
merely beat `ladder_rank`, and if `ladder_rank` itself sits inside that band the
adverse-ordering read (+0.624 rejected vs +0.290 taken) was an artifact and the
thread closes. **G0 is a blocking power pre-check** — under 25 affected dates an
arm is power-stopped and never read, declared before the contested-date count is
known. Nothing ships under any outcome; the ladder is itself in-sample, so an
ordering evaluated on this book is second-order in-sample. Also recorded from
reading `simulate()`: the `day3_cap` / `unsizable` / `ruined` census buckets
append a `None` counterfactual, so the existing "rejected picks returned +X"
description covers only the `net_delta` / `per_pos_delta` / `min1_refusal`
exclusions. Prior state follows.

**State of play (2026-08-13, `account_sim` COMPOUNDING arm added).** Sizing can
now be re-marked to realized equity at fixed calendar intervals
(`compounding:` in `config/account-sim.yml`, off by default; the arm lives in
`config/account-sim-compounding.yml`). Both delta caps scale with marked equity;
the per-position risk budget scales but is ceilinged at **$1,000**. On this book
compounding **costs money** — 72 → 70 positions, $11,399 → $9,852 — because the
account draws to $21,113 by May 2025 and de-levers into its own recovery. The
$1,000 ceiling never binds (2% only reaches it above $50k). Verdict unmoved.
**A2/A5 do not survive this arm**: their benchmark is compounded too, so the
ratio stops isolating the caps (B2 is the same 110 positions and still moves
$23,157 → $18,424). Entry below. Prior state follows.

**State of play (2026-08-13, `account_sim` caps at 0.25x / 2.50x).** The
configured net delta-notional cap is now **2.50x** (per-position unchanged at
0.25x). The verdict is unchanged (`NO VERDICT MATCHES`; A5, A6 still fail), but
the book grows 51 → 72 positions and the **adverse ordering roughly doubles** —
the picks the net cap still excludes return +0.624 against +0.290 taken. Net
delta remains the binding constraint at the looser cap and cash still binds zero
times, so the open lead is **selection order, not the cap**. Also fixed: a study
run now re-renders the chart pages (it previously refreshed only the study map,
so `docs/account-sim-charts.html` silently quoted a stale run). Entry below.
Prior state follows.

**State of play (2026-08-13, `volume_signal` RUN — NULL).** The
underlying-volume study pre-registered earlier today has **RUN. Verdict: NULL
— the volume column is CLOSED and the live pipeline never pays the version
bump.** Coverage was not the problem (O/S join 788/795, window features 93%):
unusual-O/S simply does not separate non-bear debit outcomes (terciles +0.205
/ +0.255 / +0.232, give-back share flat), and the frozen exit variant is
**negative out-of-fold** (LOO share>0 = 1%, paired CI [−0.013, +0.003], sign
flips on a window cut). One disclosed **labelled amendment**: the first run's
mechanical verdict printed PATH-VOL-PROXY off a signed-separation coding
defect (HIGH rows peak higher AND draw down *shallower*, which is not "path
width moving together"); the fix changes no number, only the label, and both
stamped reports are kept. Two POST-HOC carry-forwards recorded in the entry
(bear-debit os_ratio monotonicity incl. a same-direction walk-forward read;
credit monotonicity on ungated replays) — observations, not candidates.
Entry below; pre-registration in
[`pre-registrations/volume_signal.md`](pre-registrations/volume_signal.md).
Prior state follows.

**State of play (2026-08-13, volume study pre-registered).** The
underlying-volume signal study (`volume_signal`) — the §2.1 item the operator
queued, and the first study to satisfy the ML-search reopen condition ("new
COLUMNS only") — is **PRE-REGISTERED below, not yet run**. Data is already on
disk: share `Volume` in every `backtests/underlying_ohlc_cache/` file (loader
currently ignores it) and flow-scrape contract volume in
`audit/<date>-rollup.csv` (`Contracts`). Headline feature = unusual-O/S
(Johnson & So 2012); primary hypothesis = **exit/path conditioning, not
selection**; frozen exit-variant set = exactly one (`be_after: 0.50` on
non-bear debit HIGH-tercile rows, out-of-fold). Nothing ships from this study
under any outcome. Prior state follows.

**State of play (2026-08-13, bear_put demotion mechanism CHOSEN).** The one
decision the 08-11 holdout left with the operator is made: the bear_put
demotion ships as **card rule §1.4 in `deployment-rules.md`** — bear debit
(`bear_put_spread` / `long_put`) is vetoed **as a selection play**, with the §4
hedge sleeve explicitly carved out. Intake veto rejected (it would empty the
sleeve's candidate pool); zero historical deployments change (every bear row
was already Tier C or VETO). This supersedes the 08-11 closed-thread note
"resolved WITHOUT a demotion mechanism" — same substance, now explicit on the
card, closing the thin-day loophole by which Tier C could still deploy a bear
play. `deployment-evidence.md` closed-threads updated. The open queue for the
next session now lives in [`next-steps.md`](next-steps.md). Entry below.
Prior state follows.

**State of play (2026-08-13, method-config audit).** A cross-check of the v4
method docs against this log and `deployment-rules.md` closed three loose
ends: the `conviction-score.md` **≈ −25** `IVspr` directional-veto threshold
is **RETIRED** (stale on the matched-pair spread definition; `iv_spread`
itself stays decision-relevant via the bear_put demotion read), the
deterministic conviction `Score`'s `OIConfirm` component (built on the
already-killed `oi_confirm_pct`) is **REMOVED — folded into v4 by operator
decision, no tab bump** (rows ≤2026-08-12 carry the old composition), and the
**codex engine is retired** (codex.md deleted, AnalysisGPT tabs go
historical). No rollup/schema columns removed. Entry below. Prior state
follows.

**State of play (2026-08-13).** Two studies pre-registered AND RUN the same day,
each graded through the new two-analyst replication protocol
(`replication-protocol.md`, agents in `.claude/agents/`). **Nothing ships from
either.** `account_sim`: all gates pass; at $25k the dense-episode edge survives
its caps (99% of the $25k-sized book) but **the binding constraint is delta
exposure, not cash**, the cap ordering is adverse (rejected picks outperform
taken), and A5/A6 fail — the pre-registered verdict grammar had a hole (A1
holds, A5/A6 fail matches no label); feasibility NOT CONFIRMABLE on this
window. **Same-day addendum:** `account_sim` audited for lookahead ahead of the
live-agent step — no per-row foresight in selection or sizing, now ENFORCED by a
new **G5 blindness gate** (outcome keys raise, outcome columns deleted from the
trade row, book must come out identical: 124/124, 0 differing); the remaining
lookaheads are rule-level (in-sample ladder) and universe-level, the latter
addressed by `--structure-universe`, which admits 19 stale-`trailing_stop` proxy
rows the calibration gate wrongly withheld (+3 deployed picks, 0 displaced,
**verdict unchanged**; bs still dropped). `calendar_hedge`: R1–R4 all pass (R4 reproduces vol_sleeve's calendar
cell EXACTLY), H0 fill 75.6%/66.7% MET, but **H2 is NOT EVALUABLE — the power
stop fired at n=6 exactly as pre-committed — and the readable correlation
component is wrong-signed (+0.075)**; H3 blocked by the worst-date criterion by
$17–67 while maxDD improves at every f. The candidate is neither promoted nor
killed: **needs new dates.** Carry-forwards: RANGE+C/L-VOL calendar cell (n=15,
diff CI [+0.111,+2.422], post-hoc) and the H2 clause amendment (power stop
should suspend only (b)). The 08-13 sweep-leg scrape (857 contracts) feeds ARM
S, which RAN on the grown cache (~1,418 contracts added): **all 30 sweep cells
power-stopped, zero candidates; iron condor NOT EVALUABLE at 39.9% four-leg
coverage** — the whole hedge programme (calendar, put calendar, diagonal,
narrower) now terminates at one wall: 9 worst-decile dates cannot power a
worst-decile criterion under a 1/day sleeve. **New dates are the only path.**
R4 is re-keyed to the pre-scrape cache snapshot (labelled amendment). The
2026-08-12 open-queue audit stands: bear ratchet blocked on a harness
mechanism, flat-band cut waits for new bear rows, rollback triggers
accumulating. Prior state (2026-08-12 and older) is archived — see
[`archive/`](archive/) files 07–12 and the [README](README.md) section index.

---

## 2026-08-14 — `selection_order`: PRE-REGISTRATION → [`pre-registrations/selection_order.md`](pre-registrations/selection_order.md)

**Status: PRE-REGISTERED ONLY. Not built, not run, nothing shipped.**

`account_sim` follow-up (2) recorded the adverse cap ordering as **post-hoc**:
the picks the net delta cap excludes returned meanR +0.624 against +0.290 taken
at 0.25x/2.50x (+0.431 vs +0.278 at 1.50x), and loosening the cap doubled the
gap rather than relieving it. Cash binds zero times at both settings. This
registration is what makes a test of that observation admissible.

Six arms, frozen: `ladder_rank` (baseline), delta-notional ascending, reserved-$
per delta-notional, `|delta|` descending (the `bear_deploy` D4 transfer, never
run outside bear), one TIER-BLIND arm across A∪B (admissible only because A vs B
is statistically merged, p=.65), and a seeded random control. Unit is a
**contested date**, tested within-date paired against the baseline (the D4 method
— it cancels the date's level). The candidate bar is the full seven-part
conjunction: CI excluding zero, median positive among AFFECTED dates with ≥25 of
them, every LOO fold positive, all three years, the shipped exit config, the
ex-BOTH-windows cut added by hand, and above the random band.

Read the registration for the arm table, gates G0–G5 and the verdict grammar.

---

## 2026-08-13 — `account_sim` COMPOUNDING arm: sizing re-marked to realized equity monthly, budget ceilinged at $1,000 — it COSTS money on this book, and it breaks A2/A5

**Status: NEW OPT-IN ARM. Nothing ships. Post-hoc — compounding is NOT
pre-registered, and the mark interval and the $1,000 ceiling are a FRICTION
MODEL that may not be adopted on P&L.**

The operator asked for sizing to track the account rather than the configured
starting capital. Until now `account_sim` sized everything off a static
`cfg.capital`: both delta caps and the risk budget were fixed for the whole
three-year run, so the simulated book was completely **path-independent** —
identical whether the strategy was up $11k or down it.

**What was added.** A `compounding:` block in `config/account-sim.yml`
(`enabled: false`, so the frozen pre-registered book is untouched) and an arm
config `config/account-sim-compounding.yml`. When on:

```
marked_equity = starting capital + realized P&L of positions CLOSED STRICTLY
                BEFORE the mark session      (re-marked monthly; open positions
                                              are NOT marked to market)
budget        = min(risk_pct * marked_equity, 1000)   # ceilinged
per_pos_cap_$ = per_pos_cap * marked_equity           # scales, no ceiling
net_cap_$     = net_cap     * marked_equity           # scales, no ceiling
```

`marked_equity` is a **sizing** number only — the ledger's own `capital` is
untouched, which is why G3's identity still balances against the STARTING
capital.

**It is not lookahead, and G5 proves it.** `release_before()` already runs at
the top of each session, so at the moment of a re-mark `led.realized` contains
only positions whose `exit_sess` is strictly earlier — an operator would know
that number. G5 now runs sighted-vs-blind on **both** bases; the compounding
basis reproduces a byte-identical book (155 sighted / 155 blind, 0 differing)
because `blind_records()` deletes the outcome *columns* but keeps the price
path, and `replay_sized()` recomputes each closed position's P&L from that
path. G1–G4 stay pinned to the frozen basis: book calibration is an identity
against a prior report and selection identity is about ordering, so neither may
move because an arm changed sizing.

**Compounding costs money on this book** (PRIMARY dense episodes):

| arm | positions | dates | dollars | meanR | maxDD |
|---|---|---|---|---|---|
| frozen (static $25,000) | 72 | 37 | $11,399 | +0.290 | −$4,354 |
| compounding (monthly) | 70 | 35 | $9,852 | +0.264 | −$4,700 |

The mark trajectory says why: $25,000 → **$21,113 by May 2025** → $32,817 by Feb
2026 → $29,997 final. The account draws down first and therefore **de-levers
into its own recovery**, sizing smallest exactly where the recovery pays. That
is ordinary compounding drag on a choppy equity path, not a defect.

**The $1,000 ceiling never binds** — 0 of 6 marks (0 of 18 on SECONDARY). At 2%
it only engages above $50,000 of equity, which this book never reaches. It is
inert on this account and exists as a friction model for a larger one. The ruin
guard also fired 0 times.

**Binding constraint is unchanged: `net_delta`, and `cash` still binds zero
times** — 39 of 78 exclusions (frozen: 40 of 76). What did move is
`per_pos_delta`, 25 → 28, which is a **granularity** effect rather than a cap
effect: budget and cap both scale with equity, but `risk_contracts()` floors to
an integer, so contract counts jump in steps while the cap rises continuously,
and a position can cross its own cap on the step. The A4 partition still
balances exactly (150 candidates both arms).

**A2 and A5 DO NOT SURVIVE THIS ARM — do not read them here.** They are ratios
against B2, and B2 is compounded too. The tell is that B2 is the **same 110
positions over the same 46 dates in both arms** and its dollar total still moves
**$23,157 → $18,424**: the denominator changes without the numerator's position
set changing at all.

To be precise about what breaks — a ratio over 100% is *not* itself the anomaly.
A2 is not bounded by 100% even on the frozen book, because the caps remove
positions and removing a net-*losing* pick adds money; the frozen SECONDARY
population already prints **173%**. What breaks under compounding is
**attribution**. On the frozen basis B2 and the constrained book are sized off
the same static capital, so the ratio moves only with *which* positions the caps
removed — it isolates the caps. Under compounding B2 holds 110 positions against
the constrained 70, draws down harder, and throttles its own future budgets
differently, so the ratio mixes the caps' selection effect with a divergent
equity path. PRIMARY A2 goes 90% → **145%** across the arms on identical caps and
identical selection, and nearly all of that is the denominator collapsing
($12,675 → $6,786 on the shared dates). Neither number can be read as attrition
or stability. Both criteria were pre-registered against a path-independent
simulation and do not transfer; the report now carries that warning inline.

**The verdict does not move.** A1 MET (meanR +0.264, CI [+0.075, +0.438], both
years positive), A3 MET, A4 MET, A5/A6 NOT MET → `NO VERDICT MATCHES — A1 holds
but A5, A6 fail(s)`, the same landing as the frozen book. A6 is if anything
slightly worse: debit-only CI [−0.005, +0.427] at n=55, back to including zero
(frozen: [+0.021, +0.435]).

**Open item.** Compounding makes the whole book path-dependent, which means
every figure in the arm is now sensitive to the exit model in a way the frozen
book was not. Before any of this could inform a live account, the A-criteria
would need re-registering against a path-dependent basis — A2/A5 in particular
need a benchmark that is *not* compounded, or they need replacing. Not started.

## 2026-08-13 — `volume_signal` RUN: NULL — the volume column is closed

Report: `backtests/study_output/volume_signal-latest.txt` (stamped runs
`volume_signal-20260813-202006.txt` first run, `-202122.txt` amended-label
rerun; the diff between them is the timestamp and the verdict lines ONLY —
every number is identical). Pre-registration:
[`pre-registrations/volume_signal.md`](pre-registrations/volume_signal.md);
inputs are the 08-11 exports (795 pooled rows real+tweak, bs excluded).

### Gates

- **G1 PASS** — book debit calibration `{n: 301, exact: 289, near: 0, hard:
  12}` (the 12 hard rows are the known uncalibrated real rows, excluded from
  the exit arm by the `calibrated` flag); replay identity re-check 581/581
  exact on the exit-arm population. Credit rows ungated: 277.
- **G2** — coverage was NOT the binding constraint, unusually: O/S join
  788/795 (99%), `rvolz20`/`amihud20` 743/795 (93%), 51 rows on the rescaled
  basis with window features withheld as registered.
- G3/G4/G5 held (thin cells printed unread; no annualised figure anywhere;
  descriptive tables labelled in-sample).

### H1 — NOT SUPPORTED, both halves

(a) Non-bear debit os_ratio terciles: meanR **+0.205 / +0.255 / +0.232**
(LOW/MID/HIGH), give-back share **22% / 21% / 21%**. There is nothing there:
HIGH-O/S rows do not give back more; they peak HIGHER (MFE +1.15 vs +0.98)
with SHALLOWER drawdowns (MAE −0.52 vs −0.62) and identical realized R.

(b) The frozen exit variant (`be_after: 0.50` on HIGH-os_ratio non-bear
debit, stacked on the shipped merge) touched only **5 rows** and is
**negative**: Δ meanR −0.0032, Δ$ −2,266, paired date-clustered CI
**[−0.0126, +0.0032]**, LOO by date share>0 **1%** (min −0.0043, 115 folds),
and the gain flips sign across the mandatory window cuts (ex-2025-window
+0.0009 vs ALL −0.0032). Leak guard OK (0 rows outside the key changed). The
give-back mechanism has no non-bear home findable through volume.

### H2 / H3

- `rvolz20` (exploratory): non-monotone hump on non-bear debit (MID best,
  +0.342); nothing directional. No adoption path existed by registration.
- H3 evaluability is weak and DISCLOSED: os_ratio and amihud20 share the
  volume denominator, so HIGH-O/S rows pile into the illiquid tercile
  (n(HIGH-os)=38 in HIGH-amihud vs 4 in LOW-amihud) — only ONE 3×3 cell was
  evaluable (it kept the pooled sign → "not collapsed", read with that
  caveat). Any future volume feature must expect this dependence.

### Labelled amendment (verdict operationalization)

The first run's mechanical verdict printed **PATH-VOL-PROXY**. That fired on
a coding defect: the mirrored-path check compared SIGNED MFE/MAE separations,
so "peaks higher AND draws down shallower" (what the data shows) counted as
"MFE and MAE move together". The registered wording means path WIDTH moving
together (higher peaks WITH deeper drawdowns). Fixed in
`volume_signal.verdict()` with the amendment comment, rerun same-day; **no
number changed** (seeded bootstrap; diff = verdict lines only). Per the
registered grammar the verdict is **NULL**. Precedent: `account_sim`'s
grammar hole, same handling — disclose, don't absorb.

### Carry-forwards (POST-HOC observations, not candidates, nothing adopted)

- **Bear debit is monotone in os_ratio** and it is the LOW tercile that is
  toxic: meanR −0.321 (CI [−0.481, −0.134]) / −0.140 / −0.002, give-back 44%
  / 27% / 26%. The walk-forward selection arm (boundaries fitted on train)
  keeps the direction on TEST rows: `bear_put_spread` LOW −0.267 (n=36) vs
  MID −0.039 / HIGH −0.026. Bear is §1.4 selection-vetoed, so the only place
  this could ever matter is the **§4 hedge-sleeve pick rule** (currently
  |delta| descending) — that would need its own pre-registration on new
  dates, and the 08-12 rule stands: within-structure reads that survive one
  look have died here before (`cpir`/`oi_confirm`/`iv_pct`).
  **Post-hoc diagnostic (same day, operator question, disclosed):** os_ratio
  is NOT a |delta| proxy (Spearman os_ratio×|delta| +0.166 on 329 bear rows)
  and the pooled rank relation with R is n.s. (+0.078, p=0.16 — the tercile
  table's monotonicity is carried by the LOW-cell toxicity, not a smooth
  gradient). Within |delta| terciles the effect concentrates EXACTLY where
  the §4 sleeve lives: high-|delta| bears show rho +0.274 (p=0.004,
  n=110), low/mid show nothing. So a sleeve-pick refinement ("among
  high-|delta| candidates, prefer high os_ratio / avoid thin-flow") is the
  precise pre-registerable question — one look spent, needs new dates.
- **Credit rows are monotone the other way** (HIGH +0.337, win 75%, n=51) —
  descriptive only, on UNGATED replays, inside the Mar-TSLA-cluster caveat
  domain. Recorded, not pursued.

### Replication grading (two-analyst protocol, same day)

Digest + A/B + validator in `backtests/study_output/volume_signal-review-*`.
Digest concurs: NULL, machinery trustworthy, nothing actionable. Validator's
disagreement log, answered here where the answer is knowable:

- **G1 population arithmetic (disagree-unresolved for the analysts, resolved
  here):** the report prints 301 book-debit calibration rows (12 hard) and
  separately 581/581 exit-arm exact, without reconciling them. The
  reconciliation: 301 = REAL debit rows; the 12 hard rows carry
  `calibrated=False` and are excluded from the exit arm by flag; 581 =
  calibrated real debit (289) + calibrated tweak debit (292, tweak rows are
  exact-by-admission per `book.py`'s proxy gate). `-> PASS` covers the
  581-row arm, not the 12 hard rows. A future report should print this
  bridge itself.
- **H1(b) footprint (both analysts, valid):** the frozen variant changed only
  5 rows — below MIN_CELL_N. The paired CI/LOO ran over all 581 rows, but the
  information is those 5. The honest reading stands and is narrow: the key
  almost never fires, and where it fired it lost; that is a NULL by absence
  of footprint as much as by sign.
- **LIQUIDITY-PROXY evaluability (disagree-unresolved):** with only 1 of 3
  amihud cells evaluable, `amihud_collapse=False` is weak evidence — already
  caveated in the H3 section above; the verdict does not rest on it (NULL
  fires regardless).
- Minor: `gb%` column = sub-arming give-back share (defined in the
  pre-registration; the report should carry the definition inline).

### What this closes

The §2.1 queue item. The ML reopen condition was satisfied (a genuinely new
column), the column was tested within structure from the first look, and it
is a null: **share volume / unusual-O/S does not feed the live pipeline, no
version bump is paid.** Infra kept: `Bar.v`, `volume_features.py` (os_ratio /
rvolz20 / amihud20, split-guarded, coverage-printing) — reusable by any
future pre-registered study without touching the frozen harness.

---


## 2026-08-13 — bear_put demotion mechanism CHOSEN: card-level selection veto (§1.4), hedge sleeve carved out

Operator decision, not a new study. No backtest run; no numbers change.

**The verdict being implemented** (2026-08-11, `bear_deploy` +
completed-book holdout): all pre-registered DEMOTE criteria fired at n=164
out-of-sample; bear SELECTION is unfixable (0 of 496 conditioned subsets
positive, best subset still −0.231); bear as a HEDGE is real (pays on the
deployed book's worst decile, date-level corr −0.13, D2 met on all three
criteria; D4 pick rule `|delta|` DESCENDING; ≤ ½ size).

**Mechanism chosen: card veto, not intake veto, not Tier-C-status-quo.**
The three candidates and why the middle one won:

1. **Intake veto** (bear_call treatment) — REJECTED. §4's hedge sleeve picks
   from "the day's bear candidates", i.e. analysis emissions; an intake veto
   would remove the only instrument that pays on the book's worst dates. The
   operator's constraint was explicit: bear_put must survive as a hedge.
2. **Card rule §1.4** — CHOSEN. `bear_put_spread` / `long_put` never deploy as
   a selection play, however thin the day's A/B supply; the §4 sleeve is
   carved out by name. Emissions, rows, and the sleeve's candidate pool are
   untouched.
3. **Tier-C status quo** (the 08-11 closed-thread position: "resolved WITHOUT
   a mechanism") — SUPERSEDED. Empirically equivalent on the historical book
   (all 370 bear rows were already Tier C or VETO; zero deployments change),
   but Tier C is "skip when capital-constrained", which left a thin-day path
   for a bear_put into the top-3. The card rule closes it and gives the deploy
   morning a one-line rule instead of a soft expectation.

**Files:** `deployment-rules.md` §1.4 (new) + §4 lead paragraph;
`deployment-evidence.md` closed-threads "bear_put DEMOTION question" updated
with the supersession. The `long_put` inclusion follows the demote family as
studied (bear debit = `bear_put_spread` + `long_put`, the ratchet's own
definition); `bear_call_spread` stays intake-vetoed, unchanged.

---

## 2026-08-13 — method-config audit: −25 veto RETIRED, OIConfirm dropped from Score (in-v4), codex engine retired

Not a data study — a cross-read of this log + `deployment-rules.md` against
`config/analysis-framework.md`, `config/analysis-methods/claude.md`,
`config/conviction-score.md`, and `scripts/analysis_pipeline/config.py`.
No backtest run.

### 1. Already aligned — nothing to fix
The v4 trim (`score_flow`/`score_dealer` dropped, `iv_pct` sizing flag not a
gate, `bear_call_spread` intake veto, `score_total` decision-irrelevant
tie-break) is correctly stated everywhere it is referenced (framework Step 5,
method docs, architecture.md, deployment-rules §6).

### 2. `conviction-score.md` — ≈−25 `IVspr` veto RETIRED
Carried a STALE tag since the matched-pair redefinition + 2026-07-02 paper
filters; never re-derived. Now RETIRED outright — no fixed `IVspr` threshold
as a play-level veto. The column stays: one of only two decision-relevant
enrichment columns (`deployment-evidence.md`, `ml-plan.md`), through
`bear_put_spread × iv_spread` (confirmed archive/04 §3, archive/05 §2,
archive/06; 6th read in this file's 2026-08-11 close-out).

### 3. `OIConfirm` REMOVED from the deterministic conviction `Score` — in v4
Input `oi_confirm_pct` was killed in the 2026-08-11 ML full-column sweep
(r ≈ −0.03 vs realized P&L, composition artifact; long annotated
"placeholder only"). The derived −2/−1/+1/+2 component
(`lib/flow_summary/core.py` `_oi_confirm_points` → `score_flow_rollup`) is
deleted; single-day Score ceiling 14 → 12 (17 → 15 with persistence).
`Score`/`ScoreLabel` are LLM-visible inputs, so by the letter of the `vN_`
convention this is a version bump; **operator decision 2026-08-13: fold into
v4, no tab rename** — v4 was 2 days old. Discontinuity marker: v4 rows dated
≤2026-08-12 scored with the old composition. The `oi_confirm_pct` column,
`OIConfirmPct` rollup field, and the `enrich_oi` chain all STAY (eod_iv
feeds `iv_spread`; the column remains study-readable).

### 4. Codex engine retired
`config/analysis-methods/codex.md` deleted; `codex` removed from `ENGINES`;
AnalysisGPT tabs (v3_ and v4-era) stay in the spreadsheet as historical,
nothing writes to them; `/options summary` reads AnalysisClaude only. This
also disposes of the two contradictions the audit found in codex.md (§299
score-band promotion language vs the tie-break-only rule; §180 "two to four
plays" vs the 8-play coverage floor) — moot with the file.

### 5. No rollup-column removal
`ROW_COLUMNS`/`ROLLUP_METRIC_COLS` unchanged. Era-stable schemas for the
study loaders, and the ML-search reopen condition is "new columns" — the
non-decision-relevant columns (oi_confirm_pct, cpir, iv_skew, iv_pct) are
cheap provenance, not clutter.

---

## 2026-08-13 — `account_sim` caps reconfigured to 0.25x / 2.50x: the verdict does not move, and loosening the net cap made the adverse ordering WORSE

**Status: CONFIG CHANGE + INFRA FIX. Nothing ships. The verdict is unchanged.**

The operator raised `caps.net` 1.50x → 2.50x in `config/account-sim.yml`
(per-position stays 0.25x) and reported seeing no change in the results. The
results had changed; the **chart page had not been re-rendered**. See the infra
section below — that staleness is the more important item here.

**What the cap change did.** Both cells below are read off the SAME run's cap
grid, so they are directly comparable:

| configured cell | positions | dates | dollars | meanR |
|---|---|---|---|---|
| 0.25x / 1.50x | 51 | 28 | $7,860 | +0.278 |
| 0.25x / 2.50x | 72 | 37 | $11,399 | +0.290 |

**The verdict does not move:** A1–A4 MET, **A5 NOT MET, A6 NOT MET**, `NO
VERDICT MATCHES` — the same landing as at 1.50x. What moved inside the
checklist: A2 99% → 90% (a different and larger date set, not a like-for-like
worsening); A5's ex-2025-Mar/Apr swing +111pt → **+41pt** (still over the 15pt
bar); A6's debit-only CI [−0.093, +0.440] at n=39 → **[+0.021, +0.435] at
n=55**, now excluding zero, but still NOT MET because 2026 alone is −0.008 and
A1 must hold every year.

**The finding worth keeping: loosening the net cap did not relieve the binding
constraint, it raised the quality of what the constraint keeps out.**
`net_delta` is **still** the most binding constraint at 2.50x (40 of 76
exclusions; **cash binds zero times**, as it did at 1.50x), and the picks it
still excludes return meanR **+0.624** against +0.290 taken — a +0.333 gap. At
1.50x that gap was +0.431 vs +0.278, i.e. **+0.153**. Admitting 21 more
positions roughly doubled the adverse-ordering penalty on what remains excluded.

No cap value may be read off the P&L for this, and the reason is mechanical
rather than procedural: the grid is **monotone 4/4 in the net cap** by
construction — the book has positive mean R, so looser is always richer, all the
way to the uncapped cell at $17,622. The grid therefore cannot identify a cap;
that number has to come from what the account can actually carry (margin, delta
tolerance), and setting it to what is true of the account is simply making the
simulation more accurate. What **is** readable is the *ordering*: at both cap
settings the ladder-rank walk spends exposure on earlier-ranked picks that
underperform the ones the cap then excludes. That is a **selection-order**
problem, not a cap problem, and it is now the strongest open lead this study has
produced.

**Infra fixed in the same change (the actual bug).**

  * `scripts/backtest_study/run.py` auto-refreshed the study **map** after every
    run but never the **chart pages**, so `docs/account-sim-charts.html` kept
    quoting the previous run's numbers with no warning. A study run now
    re-renders the charts too. `make study-docs` already did this; nothing
    prompted anyone to run it.
  * `scripts/study_charts/` hardcoded config-driven values into page prose —
    the standfirst's caps and positions/day, and the utilisation panel's net-cap
    reference line (pinned at `v: 1.5`). All now read out of the parsed report,
    so a config change can never again be contradicted by the page describing
    it. `report.py` gained a `max_per_day` parse and accepts `inf` in the
    headline cap cell (a legal value when a cap is `null`).
  * `scripts/study_charts/series.py` — two **pre-existing** reconciliation
    defects that the wider book exposed: a float-epsilon comparison (0.625
    against a report printing `62%` failed by 4e-18) and a flat $1 tolerance on
    a regime TOTAL summed from a dozen independently-rounded cells. Both now
    tolerate display rounding only; a real mismatch still fails the build.

**Config-file framing corrected.** The note in `config/account-sim.yml` saying
the pre-registered values were the record of "what the frozen study ran with"
is removed. The file is the simulation and is meant to be edited; the
`## account_sim: PRE-REGISTRATION` section below stays where it is, because
`scripts/study_review/core.py::load_pre_registration` locates it by heading.

---

## 2026-08-13 — `account_sim` made CONFIG-DRIVEN: the study's parameters move to `config/account-sim.yml`, the module holds no state, and no number moves

**Status: REFACTOR ONLY. No result changed.** The regression bar was that a
default run reproduce the previous one exactly, and it does:
`account_sim-positions-latest.csv` is **byte-identical** before and after, and
every data-bearing line of the report is unchanged. The only report differences
are three deliberate wording changes, listed below.

**What moved.** `scripts/backtest_study/account_sim.py` had accumulated a second
job on top of simulating: policing its own pre-registration. It carried two
parallel constant blocks (`PREREG_*` mirroring the editable sizing constants), a
module-level mutable `ARM` rebound with `global` inside `main()` and then read
implicitly from `Cfg`'s field defaults and four report functions, a second
module-level `_MEMO` cache, and self-labelling machinery (`is_preregistered`,
`Arm.tag`, a "SIZING ARM" banner, an arm-suffixed CSV stem). All of it is gone.

The parameter surface is now `config/account-sim.yml` — capital, risk %,
positions/day, the two delta-notional caps, the cap and capital grids, the hedge
fraction, the dense-episode definition, the A2/A3/A5 thresholds, and G1's
expected book line (220 / 90 / $63,553). It is read once into a frozen
`Settings` and passed explicitly wherever it is needed; `load_settings()` raises
on **any** missing key rather than half-reading a config and printing a full
report against sizing nobody chose. The four sizing flags
(`--capital`, `--risk-dollars`, `--per-pos-cap`, `--net-cap`) are replaced by a
single `--config PATH`.

**Two latent problems closed on the way.**

  * `top_k_per_day(..., k=3)` was hardcoded at the call site while
    `MAX_POSITIONS_PER_DAY = 3` lived separately. Changing one would have failed
    G4 for no visible reason. Both now come from
    `account.max_positions_per_day`.
  * `_MEMO` was module-global. It is now an explicit `cache` owned by the caller
    (`new_cache()`), and **G5's blind probe takes its own**. That is load-bearing:
    the memo is keyed on `id(rec)` precisely so a blind result can never be
    served from a sighted computation, which is what makes the gate mean
    anything. A global cache also let answers leak between runs in a process.

**Report wording changes** (paired with `scripts/study_charts/` in the same
change, since `report.py` is a strict parser):

  * cap-grid headline `(pre-registered, ...)` → `(the configured cell, ...)`
  * `NOT FEASIBLE AT $25k` → `NOT FEASIBLE AT $25,000`, formatted from the
    configured capital
  * `NO PRE-REGISTERED VERDICT MATCHES` → `NO VERDICT MATCHES`

**What this does NOT change.** Selection, exits, the harness, the book loader and
all five gates are untouched. The values pre-registered on 2026-08-13
($25,000 / 2% / 0.25x / 1.50x) are still the shipped defaults, and the
pre-registration itself is still recorded below — in this log, which is where a
pre-registration belongs, rather than mirrored in source where it was being
diffed against on every run.

**Reproducing the sizing arm below.** The arm recorded in the next section was
run with `--risk-dollars 1000 --per-pos-cap 0.40 --net-cap 2.50`. Those flags no
longer exist: copy `config/account-sim.yml`, set `risk_per_trade_pct: 0.04`,
`caps.per_position: 0.40`, `caps.net: 2.50`, and pass `--config`. Note the
export no longer gets an arm-suffixed stem — a non-default config **overwrites**
`account_sim-positions-latest.csv`, and the report's `config` line is what
records which simulation produced it. Only `--structure-universe` still writes a
separate artifact.

---

## 2026-08-13 — `account_sim` SIZING ARM ($1,000/position, per-pos 0.40x, net 2.50x) RUN: operator-chosen, NOT measured — and it exposed a memoisation bug that G5 caught

**Status: NOTHING SHIPS. This is an arm, not a result.** The three sizing
constants were chosen by the operator (risk $500 → $1,000; net delta cap
1.50x → 2.50x; per-position cap 0.25x → 0.40x, raised because doubling the
budget doubles contracts and would otherwise have been eaten by the old
per-position cap). They were **not** selected on any measurement here, and no
figure below may be read as evidence for them. The anti-tuning rule on the cap
grid binds harder on an arm than on the pre-registered cell, not softer.

**Provenance.** `backtests/study_output/account_sim-arm-risk1000-latest.txt`
(+ positions export
`account_sim-positions-risk4pct-pp0.4-net2.5-latest.csv`, 447 rows), git
309c564 (dirty), same 08-11 exports and same frozen book as the pre-registered
run. The pre-registered report stays at `account_sim-latest.txt` and its
numbers are **unchanged** — verified by re-running the bare study after the
code change and diffing: 656 lines, the only differences are two cosmetic
GRANULARITY section titles.

**How the arm is expressed.** An `Arm` overlay (`account_sim.ARM`) carries the
run's four sizing values; `main()` rebinds it once from the command line and
every `Cfg` defaults to it. Left alone it equals the pre-registered baseline,
so a bare run reproduces the frozen study bit-for-bit; an arm run is
banner-flagged in the report, tagged in the CSV `arm` column, and written to
its own CSV stem — the `--structure-universe` precedent:

    python -m scripts.backtest_study run account_sim -- \
        --risk-dollars 1000 --per-pos-cap 0.40 --net-cap 2.50

> **SUPERSEDED later the same day** by the config-driven refactor at the top of
> this file. The `PREREG_*` literals, `Arm`, `Arm.is_preregistered`, `Arm.tag`,
> the arm banner, the arm-suffixed CSV stem and the four sizing flags described
> in the next two paragraphs no longer exist, and the four tests that pinned
> them are gone. The parameters now live in `config/account-sim.yml`; to
> reproduce this arm, copy it with `risk_per_trade_pct: 0.04`,
> `caps.per_position: 0.40`, `caps.net: 2.50` and pass `--config`. Everything
> else in this section — the numbers, the G5 bug and its fix — stands unchanged,
> and its two cited artifacts are still on disk.

**Amended same day — the sizing constants are now EDITABLE** (operator's call).
The module previously said it "may not change them after the run"; that
sentence is gone, along with `--capital` being missing. Simulating a different
account is a normal use of a research-tier study, so `STARTING_CAPITAL` /
`RISK_PER_TRADE_PCT` / `PER_POSITION_CAP` / `NET_CAP` may be edited in source
or moved per-run with `--capital` / `--risk-dollars` / `--per-pos-cap` /
`--net-cap`. What is preserved is the LABEL, not the values: the
pre-registered numbers are recorded separately as the `PREREG_*` literals, and
`Arm.is_preregistered` compares against **those**, so an edited constant
cannot silently produce a report that claims to be the pre-registered study —
it flags, tags and re-stems exactly like a flag would. `Arm.tag` names only
the knobs that moved (`cap50k`, `risk4pct-pp0.4-net2.5`). Four tests pin this.
The verdict grammar still says "NOT FEASIBLE AT $25k" verbatim, because
`scripts/study_charts/render.py` matches those strings exactly — on a
changed-capital run read it as the arm's label, not a claim about $25k.

**A REAL BUG, found by G5 and fixed.** The arm's first run FAILED G5
(outcome-blindness): sighted 132 positions vs blind 134, 13 differing.
`replay_sized`'s memo key was `(id(rec), contracts, stop)` — it did **not**
include the exit profile. G2 calls that function with an explicit `DEBIT_PROD`
profile (the one that generated the stored rows) at the stored contract count
and stop `MAX_LOSS_ABS` = $1,000. Any `simulate()` whose own stop is also
$1,000 then asks for the same key and gets **G2's calibration answer back
instead of the shipped `be_after`-0.50 merge**. Blinded records are distinct
objects, so they missed the poisoned entries — which is exactly why the two
books diverged and why the gate fired. Fixed: the profile is now part of the
key. The gate is doing more than its stated job; it caught a cache-collision
bug, not a lookahead.

Two stops reach $1,000: **a $25k book at 4%** (this arm) and **a $50k book at
2%** (the top rung of `CAPITAL_LADDER`). The pre-registered report is
unaffected — its stop is $500, keys never collided, and the capital ladder
only prints when A1 fails, which it did not. **No published pre-registered
figure ever stood on the bug.**

**What the arm printed (PRIMARY dense episodes, descriptive only).**

| | pre-registered ($500 / 0.25x / 1.50x) | arm ($1,000 / 0.40x / 2.50x) |
|---|---|---|
| positions taken | 51 | 63 |
| realized $ | $7,860 | $20,217 |
| meanR | +0.278 CI [+0.055,+0.483] | +0.428 CI [+0.249,+0.594] |
| maxDD | −$3,673 (14.7% of capital) | −$2,851 (11.4%) |
| attrition vs B2 (A2) | 99% | 135% |
| most binding constraint | net_delta (66 of 97) | net_delta (62 of 85) |
| per_pos_delta exclusions | 25 | 14 |
| A5 stability | NOT MET | NOT MET |
| A6 credit sensitivity | NOT MET | MET |
| verdict | A1 holds, A5+A6 fail | A1 holds, A5 fails |

**Reading, with the caveats that matter more than the numbers:**

1. **Net delta is STILL the binding constraint** (62 of 85 exclusions) even at
   2.50x. Raising the cap did not relieve it; it moved the frontier out and
   the book refilled against it. Peak sessions run 2.45–2.48x net — pinned to
   the new ceiling, the same way they were pinned to the old one. Cash never
   binds once (0 of 85, peak reserve 0.78x).
2. **The per-position cap change did what it was for.** per_pos_delta
   exclusions fall 25 → 14 despite contracts doubling, so 0.40x roughly
   absorbs the doubled budget rather than eating it.
3. **The adverse-ordering finding SURVIVES and its two halves separate.**
   net_delta-rejected picks still out-perform taken (+0.482 vs +0.428, delta
   +0.053 — narrower than the frozen cell but the same sign), while
   per_pos_delta-rejected picks now under-perform (+0.126, delta −0.302). The
   net cap is still adversely selecting; the per-position cap is not.
4. **A5 still fails, and by MORE.** Ex-2025_mar_apr moves +142pt (frozen:
   +111pt). The bigger book is *more* concentrated in that window, not less.
   The A5 failure is the reason feasibility is not confirmable, and the arm
   does not fix it — it worsens it.
5. **A6 flipping to MET is not a finding.** Debit-only n=46 meanR +0.386 CI
   [+0.172,+0.594] clears where the frozen cell's n=39 CI included zero. This
   is the same rows at different sizes with a wider net cap admitting more of
   them; treating a criterion flip produced by an operator-chosen knob as
   evidence is precisely what the anti-tuning rule forbids.
6. **Per-position risk is now materially larger.** Realized per-position risk
   is median 3.6%, p90 6.0%, **max 12.2%** of capital (frozen: 1.8 / 3.0 /
   6.1%). The 1-contract floor share is 28%, so on more than a quarter of
   picks the account cannot express the budget at all and takes a single
   contract whose max loss exceeds it — at $1,000 that floor breach is twice
   the dollars it was.

**Verdict grammar hole is unchanged.** "A1 holds but A5 fail(s)" still matches
no pre-registered label, same as the frozen run. Not relabelled.

**Carry-forward.** The memo-key fix is a correctness fix to research
infrastructure and applies to every future `account_sim` run at a $1,000 stop
— including the $50k rung of the capital ladder, which would have been
silently contaminated the first time A1 failed and the ladder printed.

---

## 2026-08-13 — `calendar_hedge --arm S` RUN: the structure sweep is uniformly POWER-STOPPED — zero candidates, and that is a power fact, not evidence against any structure

**Provenance.** `backtests/study_output/calendar_hedge-latest.txt` (ARM S run;
the H arm stays preserved at `calendar_hedge-20260813-130412.txt`), git 470b95f
(dirty), 08-11 exports, grown option cache (**19,382 contracts** after the
sweep-leg scrape: 1,418 of 1,452 manifest targets fetched;
`scripts/collector/fetch_sweep_legs.py`, resumable, manifest in
`backtests/sweep_cache/legs_manifest.csv`). Nothing ships. The two-analyst
replication was NOT run on this report (uniform power stops leave nothing to
grade); it can be requested.

**DEVIATION (labelled, post-first-run module amendment).** R4 is re-keyed to
the **pre-scrape cache snapshot**: the sweep manifest's fetched contracts are
withheld from leg SELECTION (pricing unfiltered — legs picked from the
filtered grid point at byte-unchanged files), because vol_sleeve's "nearest
cached strike / next cached expiry" definitions re-pick legs on a grown cache.
Under the snapshot, **R4 reproduces the vol_sleeve cell EXACTLY again (183 /
+0.158 / $28,059 / 124-28-22-5-4)** — confirming the earlier post-scrape R4
failure was 100% cache movement, zero re-implementation drift. The snapshot
cell is stored under its own label (`calendar@snapshot`) so it can never mix
with grown-cache rows. Second small fix: the ARM S precondition now scans all
stamped reports for an H2 verdict (the runner's `-latest.txt` overwrite had
erased the marker).

**Coverage on the grown cache.** put_calendar 109 built (52/90 deployed dates),
put_diagonal 58 (36/90), narrower 246 (80/90), wider 200 (74/90), long_put 326
(84/90). **S6 iron_condor: four-leg coverage 314/786 = 39.9%** vs the
pre-registered 60% gate (plan-time cache-only was 27.2%; the scrape halved the
gap, didn't close it) → **NOT EVALUABLE**, excluded from the sweep and from
the multiplicity count.

**Controls (the plumbing check).** baseline −0.093 vs published −0.093
(REPRODUCES), long_put +0.002 vs +0.002 (REPRODUCES, touches no grid), wider
−0.055 vs −0.056 (+0.001, expected — it re-selects the lowest cached put and
895 puts were added; grid-selecting structures move with the cache by
construction). S3/S4/S5 run through bear_rewrap's own path (base-row grid +
`prod_profile_for`), with a hard guard against sending rec-based structures
down the synth path.

**Sweep: 5 structures × 6 pick rules = 30 cells, Bonferroni α = 0.05/30.**
**Zero CANDIDATEs — all 30 cells POWER-STOPPED** (worst-decile tail n = 0–6
against the ≥10 threshold; a 1/day rule over 9 worst-decile dates cannot fill
a readable cell, the same arithmetic that stopped the H arm's H2). Standalone
means printed for context only (narrower +0.24..+0.42, put_calendar
+0.09..+0.39, long_put ≈0, put_diagonal mixed) — ungated, quote nothing from
them. One structural finding: **P5 (same ticker as the day's top deployed
pick) fills 0% on every bear_rewrap structure** — verified real: across all 90
deployed dates the top-ranked pick's ticker never also carries a bear debit
row. P5 is inapplicable to bear substitutions in this book.

**Decision (main session).** The bear-structure sweep is CLOSED for this
window with the same conclusion as the H arm: **every hedge-shaped question on
this book now terminates at the same wall — 9 worst-decile dates cannot power
a worst-decile criterion under a 1/day sleeve.** No structure is promoted, none
is killed. The only path forward for the entire hedge programme (calendar,
put calendar, diagonal, narrower — all of it) is NEW DATES. Iron condor
becomes evaluable only if a future scrape lifts four-leg coverage ≥60%. Do not
re-run this sweep on the same 118 dates with different knobs.

---

## 2026-08-13 — `calendar_hedge` RUN: gates all pass (R4 exact), but the hedge claim cannot be read — power stop fires at n=6 and the readable correlation is wrong-signed

**Provenance.** `backtests/study_output/calendar_hedge-20260813-130412.txt`
(the stamped R4-PASS run — `-latest.txt` was later overwritten by a
post-scrape gate run that fails R4 by construction; see the R4 note below),
git 470b95f (dirty), the 08-11 exports, `load_book(include_bs=False)` → 795
rows. Checkpoint store `backtests/sweep_cache/synth_results.csv` (967 rows,
resumable, `--redo` verified). Nothing ships; the pre-registered ship ceiling
is NOT reachable on this window.

**Gates.** R1 quoted (289/301 exact, 277 credit ungated). R2 **786/786**. R3
deployed line exact (220 / 90 / $63,553). **R4 EXACT on every field** — 183
rows, meanR +0.158, $28,059, exit mix 124/28/22/5/4, and the unpriceable census
reproduced — so the H-arm numbers are attributable to the pick rule and fill
discipline, not re-implementation drift. NOTE: R4 is now **frozen to the
pre-scrape cache**: the 08-13 sweep-leg scrape grows the option cache, and
vol_sleeve's "nearest cached strike / next cached expiry" definitions re-pick
legs on a grown cache (observed live: AAPL cell moved first). The delivered
report is the R4-PASS run; the module prints a cache fingerprint and an
R4-failure attribution block so future drift is diagnosable in one line.

**H arm (strict fill, P1 nearest-ATM, ½ size, 1/day).** Universe: 143 loose →
132 strict candidates over 68 dates / 26 tickers (2 excluded entry_net ≤ 0).
- **H0 FILL MET:** 68/90 deployed dates (75.6%), 6/9 worst-decile (66.7%).
- **H1 (context):** n=68, meanR +0.228 CI [−0.016, +0.590], win 62%, **all 3
  years positive** (+0.062/+0.369/+0.220); $13.3k at ½ size; meanE +0.034.
- **H2 (primary) NOT EVALUABLE.** (a) corr(daily $) **+0.075** CI [−0.095,
  +0.187] — needs < 0, NOT MET; (b) worst-decile cell **n=6 → POWER STOP fired,
  CI not read** (the pre-registration's expected outcome); (c) 2/3 years MET.
  Substantively: the one readable component is **wrong-signed** — the same
  direction vol_sleeve found for straddles (synthesizing on the engine's own
  dates re-wraps the same exposure), weaker but not the hedge sign.
- **H0b:** headline strengthens under the freshness cut (+0.274, CI [+0.016,
  +0.642], n=66) — not a stale-mark artifact. (Report defect: no explicit
  MET/NOT MET line printed; graded NOT EVALUABLE by both analysts since the
  headline it must preserve is itself unreadable.)
- **H3 NOT MET on both baselines** — but read the mechanism: maxDD improves
  monotonically at every f (ladder alone −7,609 → −5,561 at f=1.0; ladder+bear
  −6,606 → −5,187) and totals +$13.3k; the block is the worst-single-date
  criterion failing by **$17–67 per f step** (−3,212 → −3,229 at f=0.25). The
  pre-registered rule did exactly what it was written to do; the margin is
  noise-sized and is recorded as such, not argued away.
- **H4:** P1 never separates from the day's mean fillable calendar (dR −0.029,
  CI spans zero) nor from any of P2–P6 — the simplest rule stands by default.
- **H5 (post-hoc, candidate-only):** `model RANGE + C/L-VOL` n=15, diff +0.966
  CI [+0.111, +2.422] — the only cell excluding zero; **vol_sleeve's
  earnings-inside-DTE conditional does NOT reproduce** under the strict-fill
  1/day sleeve (n=14, CI spans zero).
- **Exit sensitivity (labelled):** hold-to-near-expiry flips standalone to
  −0.193 and flips (a) to MET / (c) to NOT — the verdict is exit-shape-sensitive
  in components but H2 stays NOT EVALUABLE either way. H3/H4/H5 were not rerun
  under HOLD (deviation, recorded).

**Decision (main session).** The calendar-hedge CANDIDATE is **not promoted and
not killed**: H2 was pre-registered as the primary gate, the power stop fired
exactly as written, and the honest conclusion is the one the pre-registration
pre-committed to — **needs new dates** (worst-decile n ≥ 10). Until then the
worst-decile +0.336 from vol_sleeve should not be quoted as a hedge property;
under the strict fill rule it is n=6 / +0.163 / unreadable. The RANGE+C/L-VOL
cell is the only carry-forward, as a next-window candidate with its own
pre-registration. ARM S (structure sweep) runs separately on the grown cache.

**Report defects found by replication (for the next runner):**
1. The `$ (1/2 size)` headline vs the `fmt_row` detail line mix half-size
   (`H_dol`) and FULL-SIZE (`R_dol`) dollars without labels — verified in source
   (`calendar_hedge.py:262,274`): a labelling defect, not a numeric error
   (signed sums explain the odd ratios 1.52×/4.76×).
2. H5's `vs rest` column prints the REST group's mean, not the difference
   (validator-resolved mechanically); header mislabelled.
3. Hedge sizing floors at `max(1, int(0.5×contracts))` — full size whenever the
   risk size is 1 contract; same unlabelled "≤½ size" deviation as account_sim's
   ARM H. Fix both together if the sleeve is ever re-run.

### Disagreement log
- H5 column characterization: A read it as an internally inconsistent diff
  column, B as a mislabelled rest-mean column — **resolved in B's favor** by
  validator arithmetic (all four rows consistent with rest-mean).
- H0b emphasis: A flagged out-of-order printing, B flagged absence from the
  VERDICT block — complementary, both true, no verdict conflict.
- H2(a)-vs-power-stop tension (B-only): (a) fails on its own, so a literal
  "all three" reading could argue NOT MET; the power-stop clause is written
  unconditionally, so NOT EVALUABLE stands. Main-session note: on the NEXT
  window, if (a) fails again with (b) readable, H2 is NOT MET — the clause
  should be amended to say the stop only suspends (b), not (a)/(c).
- Protocol violations (validator): Analyst B added an out-of-schema synthesis
  paragraph and silently reordered the gates — both recorded; verdicts
  unaffected. First real run of the protocol otherwise clean.

---

## 2026-08-13 — `account_sim` RUN: the $25k edge survives its caps but not its window; the verdict grammar had a hole

**Provenance.** `backtests/study_output/account_sim-latest.txt`, git 470b95f (dirty),
the 08-11 exports (BacktestResults 1,926 / BacktestProxy 4,533 / AnalysisClaude
11,836 rows), `load_book(include_bs=False)` → 795 rows; mech table 803 rows
2026-08-13 (book.py boilerplate — not used by any printed account_sim output;
validator-checked). Nothing ships from this study by pre-registration.

**Gates: all four PASS.** G1 debit_calib 289/301 exact (12 hard, excluded),
n_credit_ungated 277; **B1 reproduces the vol_sleeve deployed line exactly (220 /
90 / $63,553)**. G2: 175/175 calibrated debit picks replay exactly through the
scaling-identity code path at scale=1 (42 credit picks counted, ungated). G3: 248
ledger events, 0 violations. G4: pick-set symmetric difference 0. Failure paths
demonstrated via `--selftest-gates` (all four gates flip to FAIL, exit 1).

**Headline — PRIMARY dense episodes (3 episodes, 46 dates, 112 picks), (R, F1)
cell at caps (0.25, 1.50).** 51 positions / 28 dates / **$7,860, meanR +0.278 CI
[+0.055, +0.483]**, maxDD −$3,673 (14.7%). B1 $45,671 → B2 (at $25k sizing)
$23,157 — **granularity alone halves the paper book** — → constrained $7,860 =
99% of B2 on the same dates.

**What the ledger actually says (the operative findings):**
- **The binding constraint is delta exposure, not cash.** 66 of 97 exclusions hit
  the net delta-notional cap, 25 the per-position cap, 6 the day-3 cap; **cash
  binds zero times**. The capital number is almost irrelevant at these caps.
- **The cap ordering is adverse:** rejected picks would have returned meanR
  +0.431 vs +0.278 taken — the ladder-rank walk consumes exposure on
  earlier-ranked picks that underperform the ones the cap then excludes.
- **Min-1 granularity dominates:** 133/218 picks (61%) both floor at one contract
  AND breach the $500 risk budget (worst 13.3% of equity). F1 vs F2 flips sign by
  population (dense: refusing costs $4.2k; sparse full book: refusing GAINS
  $4.2k) — no rule is readable from this window.
- **ARM H (shipped bear sleeve) works as exposure headroom, not P&L:** the sleeve
  itself loses $832 but reduces |net|, admitting 25 more signal positions
  ($7,860 → $10,615).

**Verdict (pre-registered grammar): NO LABEL MATCHES.** A1 MET, A2 MET (99%), A3
MET (14.7%), A4 MET (partition exact), **A5 NOT MET** (ex-2025-Mar/Apr ratio
210%, +111pt swing), **A6 NOT MET** (debit-only CI [−0.093, +0.440] spans zero,
n=39). FEASIBLE required A5∧A6; NOT FEASIBLE required A1 failing; the run landed
in the gap and the report says so rather than relabelling. **Recorded outcome:
feasibility NOT CONFIRMABLE on this window** — the surviving edge is
window-concentrated and credit-carried at this account size. The capital ladder
correctly did not print (A1 held). SECONDARY full book is weaker everywhere
(124 positions, $5,021, CI spans zero) and carries nothing per pre-registration.

**Replication protocol (Mode 1, DRY RUN — first use).** Two `research-analyst`
agents graded the report independently; `research-validator` source-checked
every quoted number. **All verdict rows agree; zero numeric mismatches; no
methodology violations.** Reconciled deviations (all real, none verdict-moving):
the A4 census adds two unregistered buckets (`taken_downsized`, `unsizable`);
G1–G4 print full-book counts rather than per-population; the "floor share"
label differs from the plan-time disclosure (same data); A5's window cuts were
not named in the pre-registration (report used the two standard cuts); A2's
denominator reads "same dates" as the 28 taken dates, not the 46 dense dates
(a ×3 difference — literal wording supports the report); **ARM H's `int(0.5×c)
floor 1` sizing exceeds "≤½ size" whenever risk size is 1 contract (unlabelled
deviation, B-only catch)**; G2 calibrates against DEBIT_PROD not the shipped
merge (labelled, correct — identity test, not exit test).

### Disagreement log
No disagreements: every criterion row adjudicated `agree`. Single-analyst
catches (A: A2 denominator; B: ARM H sizing floor, mech-table input) were
confirmed real by the validator, not contested.

**Follow-ups recorded (not shipped, not promises):** (1) the verdict grammar
must cover A1-holds/A5-or-A6-fails before any re-run; (2) if a $25k deployment
is ever considered, the delta-cap ordering question (rank-walk vs
exposure-efficient selection) is the pre-registerable item — the adverse
ordering read is post-hoc here; (3) ARM H sizing floor should be `max(1, …)`
only when ½-size ≥ 1 contract, else skip, if the sleeve is ever re-run.

### 2026-08-13 addendum — lookahead audit, G5 blindness gate, and the structure universe

Prompted by the operator question "does the sim see the backtest result before
picking a tier?", asked because the next step is an agent proposing positions
against the live portfolio. **Verdict: no per-row lookahead** — `ladder_eligible`
reads `tier`; `ladder_tier` reads `structure` + `market_regime` + `delta` +
`dte`; `ladder_rank` adds a `score_total` tie-break; sizing reads
`max_loss_per_contract`; exposure reads `delta` × `entry_underlying`; the exit
profile keys off `structure`/`credit`/`mech_cell` (as-of-date). No outcome field
is read before a pick. Three lookaheads DO exist above the row level and are
recorded, not fixed: **(a)** the ladder and exit profile are in-sample (fitted on
this book), **(b)** within-day ties resolve by file order for pre-13c rows, and
**(c)** the candidate universe was outcome-filtered — addressed below.

**G5 — outcome blindness, now GATED.** Auditing the path by eye is not a
guarantee for a downstream agent, so blindness is enforced in two layers:
`BlindRec` raises `LookaheadError` on any read of `R`/`E`/`R_dol`/`E_dol`/
`mfe`/`mae`/`mfe_day`/`mae_day`/`exit_reason`/`days_held`, AND the equivalent
columns are DELETED from the underlying `Trade` row so a read cannot route
around the wrapper via `rec["t"].row`. G5 requires the resulting book to be
**identical** to the sighted run: 124/124 positions, 0 differing. `Trade`
construction touches only entry-side fields and the price path, so stripped rows
still price. `--selftest-gates` flips all five gates to FAIL.

**Structure universe (`--structure-universe`), NOT the default.** The frozen
book withholds 19 `strike_expiry_tweak` debit rows that fail book.py's
exact-replay gate. The gate's stated rationale — "priced or dated in a way the
harness can't reconstruct" — is **wrong for these rows**: all 19 carry a stored
`exit_reason` of `trailing_stop`, a rule removed from `DEBIT_PROD` by Attempt 10
(2026-07-04). They are stale-exit-config exports whose price paths replay fine.
Since this study never reads a stored outcome (G5 proves it), admitting them is
sound *here and only here* — `load_book(require_proxy_calibration=False)` keeps
`calibrated=False` on them, so `calibrated`-keyed logic (G2) still skips them,
and it does **not** re-admit `bs_options_hist` rows (orthogonal filters, tested).

Effect: candidate universe 795 → 814 (+19, all 2026, tier A=3 / C=14 / VETO=2);
deployed book 220 → 223 picks over 90 → 91 dates, 3 gained (NVDA 03-11, GOOGL
03-23, NVDA 04-02, all `bull_call_spread`), **0 displaced**. PRIMARY moves
$7,860 → $8,357, meanR +0.278 → +0.280. **Verdict is UNCHANGED** (A1 MET, A5/A6
NOT MET, same gap in the grammar) — the arm does not rescue feasibility and
nothing is adopted from it. Gates always run on the FROZEN book so G1's B1
reproduction and G4's selection identity cannot move because an arm widened the
universe; the arm writes a separate artifact
(`account_sim-positions-structure-latest.csv`, arm `RF1-structure`) so a
consumer can never confuse the two books.

**Positions CSV** now also carries the regime block —
`market_regime`/`model_dir`/`model_vol` (what the tier keys off) kept SEPARATE
from the per-play `regime` (per the repo invariant), plus
`mech_direction`/`mech_vol`/`mech_cell`. Tier is now reproducible from the CSV
alone. Export remains a debugging artifact: not pre-registered, adopts nothing.

**Same-day addendum 2 — a `DEPLOYED BOOK BY REGIME` section was added to the
report, and it is NOT a deviation from the pre-registration.** It adds no
decision, changes no printed number and touches neither selection, sizing nor
exits — it re-groups the book the walk already produced, so the gates and the
A1–A6 verdict are bit-for-bit what they were. It is labelled post-hoc in the
report itself, cells under 10 positions are marked `thin`, and it exists because
the obvious next question about a deployed book ("which structures, in which
regimes") was being answered by hand-crosstabbing the positions export, which
is how a number nobody re-derives becomes a quoted finding. Anyone grading this
report should read that section as a description, not a result.

Worth recording from it, as description only: on PRIMARY the model's direction
and the mechanical one **agree on 14 of 51 deployed positions** — the model
reads RANGE on 34 positions the SPY/VIX label calls BEAR. The two are read off
different things so this is not an error rate, but it does mean the tier (keyed
on the model read) and the exit profile (keyed on the mechanical cell) are
routinely disagreeing about the same position. Not a finding, and no cut here
was pre-registered; flagged as a candidate question for a study that would be.

---

## 2026-08-13 — `account_sim`: PRE-REGISTRATION → [`pre-registrations/account_sim.md`](pre-registrations/account_sim.md)

Moved out of this log: a pre-registration is an immutable artifact and this
file is pruned into `archive/`. The section is unchanged, just relocated.

---

## 2026-08-13 — `calendar_hedge`: PRE-REGISTRATION → [`pre-registrations/calendar_hedge.md`](pre-registrations/calendar_hedge.md)

Moved out of this log: a pre-registration is an immutable artifact and this
file is pruned into `archive/`. The section is unchanged, just relocated.

---

