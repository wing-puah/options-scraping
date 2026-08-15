# Archive 14 — 2026-08-13: volume_signal, bear_put demotion, method audit, compounding arm

Covers the rest of 2026-08-13: the `account_sim` COMPOUNDING arm (costs money
on this book; A2/A5 do not transfer), the `volume_signal` RUN (NULL — the
volume column is CLOSED, the live pipeline never pays the version bump), the
bear_put demotion mechanism CHOSEN (card veto §1.4, hedge sleeve carved out),
and the method-config audit (−25 `IVspr` veto retired, `OIConfirm` dropped
from Score in-v4, codex engine retired). Ordering follows the log (newest
first). See [../README.md](../README.md) for the full section index.

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
[`pre-registrations/volume_signal.md`](../pre-registrations/volume_signal.md);
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
`config/prompts/analysis-framework.md`, `config/prompts/analysis-methods/claude.md`,
`docs/conviction-score.md`, and `scripts/analysis_pipeline/config.py`.
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
`config/prompts/analysis-methods/codex.md` deleted; `codex` removed from `ENGINES`;
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
