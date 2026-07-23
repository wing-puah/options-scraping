# Archive 06 — 25-date gate close, mechanical-regime overlay, shipped exit work

Covers 2026-07-22 up to addendum 10: the gated re-reads at 913 pooled priced
rows, the mech_regime spec and its re-cuts, the shipped BEAR+H/E trail
exception, `exit_basis`, `mech_cell` on the analysis row, and the SPY/VIX
table move into Drive + CI.
See [../README.md](../README.md) for the full section index.

---

## 2026-07-22 — 25-date gate CLOSED: gated re-reads at 913 pooled priced (531 post-13c)

Snapshot exported 07-22 16:40 (`backtests/to_evaluate/analysis - *.csv`):
344 real BacktestResults + 569 priced proxy (327 strike_expiry_tweak, 242
bs_options_hist) = **913 pooled priced**, real-priced tier 671 (73%).
All 13 remaining regime-gap dates landed with analysis + priced backtest rows
(coverage table clean, 9–12 priced rows each). **post-13c book: 531 rows**
(vs 312 at the 07-21 gate), 112 credit. Post-13c flag derived from the
JOINED AnalysisClaude `created_datetime` (BacktestResults `created_datetime`
is backtest-run time — min 07-17 — and would mislabel everything);
60-char-prefix join recovers 903/913. Script:
`backtests/regime_gap_reread.py` (+ `regime_gap_reread_output.txt`).
Caveat: 2026-03-06 was analyzed twice (30 backtest rows vs ~10 typical,
duplicate MARKET row in the tab) — its rows are double-weighted in pooled
stats; date-level reads unaffected.

### Queue item A — NOT TRIGGERED; score_flow AND score_dealer both KEPT

The pre-registered rule was "remove both if still null." Neither is null on
the enlarged post-13c book:

- **score_dealer's drawdown channel came BACK** (07-21 called it
  attenuating at n=172; wrong — small-n): post-13c bear_put realized
  −0.213 p=.001, MAE −0.320 p<.0001 (MFE flat — asymmetric); post-13c
  debit-wide realized −0.11 p=.023 / MAE −0.13 p=.008; full-book MAE
  −0.160 p<.0001 (5th confirmation). Higher dealer score → deeper bear_put
  drawdowns and worse realized — wrong-signed as a conviction component,
  but real information. Feeds the bear_put emission-demotion proposal.
- **score_flow: first right-signed credit read.** Post-13c credit realized
  +0.246 p=.009, MFE +0.289 p=.002, MAE flat (asymmetric, correct sign);
  within bull_put +0.240/.011. First appearance at this n — NEW watch
  item, not action. Debit side stays null on realized; bear_put MAE
  −0.255 p=.0001 (path channel, same family as score_dealer's).
- score_vol credit post-13c +0.14 p=.14 — right-signed, below
  significance; its own gate verdict stays open.

Prompt contract unchanged — the four touch points stay as they are. The
drop rule is retired (evaluated once, condition not met, both columns now
have confirmed channels).

### bull_put PROVISIONAL re-read — band rule STRENGTHENED

Real-priced bull_puts n=137 (was 118): shipped band
(0.08≤|delta|≤0.20, DTE≤59) post-13c **+0.478 mean / 89% win (n=36)** vs
violators −0.323 / 56% (n=41) — the strict cell nearly doubled its n and
improved (07-21: +0.15/80%). Bin structure intact: |delta| 0.08–0.12
→ +0.45/86% and 0.12–0.20 → +0.27/82% post-13c; >0.20 → −1.09/33%
(n=6; cap direction re-confirmed 5th time but still thin — stays
PROVISIONAL at n=11 all-rows); ≤0.08 still negative. DTE 45–59 still
carries the edge (+0.46/85%, n=55); 22–45 turned mildly positive
post-13c (+0.10, n=10) and 59–75's negative softened (−0.14, n=10) —
the 45–59 *preference* holds, the ≤59 cap looks more like a cliff at
59–75 than at 22. No doc change needed; deployment-rules.md wording
already matches.

### Ladder — pooled/real monotone AGAIN at 913; post-13c A-vs-B watch RESOLVED: MERGED

- Pooled +0.60/+0.28/−0.08/−0.42 and real-priced +0.70/+0.31/−0.08/−0.48:
  A>B>C>VETO monotone, third consecutive validation.
- **Post-13c: A +0.363 vs B +0.374 (MWU p=.65) — A no longer separates
  from OR orders above B.** The 07-19/07-21 open watch resolves as "A and
  B are one deployable pool post-13c"; the load-bearing boundaries are
  the vetoes and the B/C line (A+B ≈ +0.37 vs C −0.13, n=282). No
  mid-window rule change (walk-forward discipline): A-first ordering is
  harmless. Queue for next gate: consider folding A into B in
  deployment-rules.md or re-deriving what separates deployable rows.

### The 13 new dates — the honest out-of-sample read

New-date rows n=151, mean **−0.17, 36% win** — the falsification test did
its job. Election-week vol-crush cluster +0.15/54% (the bull_call edge
survived C-VOL crush); Mar-2026 BEAR stretch **−0.41/28%** (n=61) — the
edge does NOT extend to the recent BEAR regime. Crucially the ladder
routed 70% of new-date rows to C/VETO (C 62%, VETO 8%, A only 11%) —
triage worked as designed on exactly the dates chosen to stress it.
BULL+L-VOL debit cell post-13c: +0.11/40% win (n=55) — sizing-down
candidate stays dead; stop watching.

### Watch-item closures (post-13c re-reads)

- **bull_call price_vector: CLOSED, did not replicate** — post-13c n=166
  all three bases null (realized −0.04 p=.62). The 07-21 read was
  noise/pre-13c composition.
- **debit delta vs realized: CLOSED** — post-13c realized +0.01 p=.82 at
  n=419 (was +0.26 at half the n); the surviving MFE +0.20 / MAE −0.19
  mirror is the mechanical path-vol signature. Prior read was small-n.
- **bull_put iv_skew: CLOSED** — post-13c −0.10 p=.51, sign-unstable
  across snapshots; 4 marginal appearances, never confirmed.
- bear_put × iv_spread MAE −0.185 p=.002 pooled — 5th confirmation;
  Tier-C rule stands.

### Decisions + what's next

Shipped: nothing to code (queue item A evaluated, condition not met;
deployment rules frozen mid-window). Logged: A/B merge queued for next
gate; new watch = credit score_flow positive read. The priority queue
(§2026-07-21) advances: item 2 (regime-gap dates) is DONE — next in
order: **#1 close the live loop** (deploy_tier column + live entry
tagging + first live-vs-backtest eval at ~30–50 positions), #3 per-regime
exit switch study (with the mechanical-label robustness re-cut), #4
bear_put emission demotion proposal (now carrying the score_dealer
bear_put channel as supporting evidence).

### 2026-07-22 addendum — deploy_tier column DROPPED; mechanical-regime overlay proposed

- **deploy_tier pipeline column is dead (user decision)**: live tier will
  be reconstructed at eval time from IBKR trade history + the analysis
  row — the tier is a pure function of structure × regime × delta/DTE, so
  nothing needs recording at emission. Priority-queue #1 reduces to: pull
  IBKR fills, map each to its analysis row + tier, run the
  live-vs-backtest eval at ~30–50 positions. No schema change.
- **Regime-tagging improvement — proposed as a deterministic overlay,
  NOT a model relabel.** Motivation: ladder Tier A ("RANGE or E-VOL")
  and the BEAR+H veto key off the MODEL's label, and §2026-07-21
  validation showed 22/85 mechanical-BEAR days labeled RANGE — drawdown
  days can promote into Tier A while the veto sleeps (Mar-2026 −0.41
  despite triage is the suspect). Relabeling the model = input change =
  version bump = resets the 531-row post-13c book, and the model label
  carries forward-looking value (early-right Apr-2025 call, hedging-flow
  E-VOL) — so keep it, add `mech_regime` (SPY 50-SMA/20d + VIX
  level/change, same rule family as the gap-date selection) joined at
  row-expansion time like the rollup columns: no prompt change, no
  version bump, backfills the whole book. GATED on a decisive test:
  re-cut ladder + regime cells on mechanical labels over the existing
  913-row export — ship only if the mechanical BEAR+H veto catches the
  Mar-2026 losses the labeled veto missed and/or Tier A sharpens. The
  same re-cut is the prerequisite for the per-regime exit switch study
  (#3), so it's not wasted work if the answer is "cosmetic".

### 2026-07-22 addendum 2 — mech_regime no-lookahead spec + re-ranked improvement queue

**Objective clarified (user question 07-22): mech_regime is NOT a check
on whether the model read SPY/VIX correctly — the model sees that data.
It exists because the ladder's gates (BEAR+H veto, Tier-A regime cell)
currently consume the model's free-text label, which classifies the same
state inconsistently (22/85 mech-BEAR days labeled RANGE). The fix is
gate reliability: deterministic label in, same state → same gate, every
time. Same rationale as computing rollup columns deterministically
instead of asking the model to report them. Disagreement days (model
RANGE / mech BEAR) are the diagnostic cut for whether model deviations
are informative or noise.**

**Second-order effects + conflict rule (user question 07-22):**
- Conflict resolution is a FIXED rule decided in advance, never an
  operator judgment call — a discretionary tie-break would land on
  exactly the days (drawdowns) where discipline is weakest, making two
  labels worse than one. Proposed asymmetry: risk gates take the OR
  (veto if EITHER label says BEAR+H), promotions take the AND (Tier A
  only if BOTH say RANGE/E-VOL). Disagreement always narrows deployment,
  never widens it.
- Cost of that conservatism = the biggest second-order risk: trailing
  indicators lag at turning points (V-bottom: SPY still under 50-SMA,
  20d return negative, model correctly reads recovery flow — e.g. the
  Apr-2025 early-right call). The OR-veto would have blocked those
  winners. The re-cut must price BOTH sides of the disagreement cell:
  losses avoided (Mar-2026) vs winners forgone (Apr-2025). KILL
  CRITERION: if model-RANGE/mech-BEAR days are net-positive P&L, the
  OR-veto is wrong — don't ship it as a gate (mech_regime could still
  ship as an eval-only column for the exit study).
- Other second-order effects: (a) cross-label cut space doubles →
  more spurious cells at small n — pre-registered cuts only, no mining
  model×mech cross-cells; (b) ladder checklist gains a condition —
  acceptable only because the column lands on the row automatically;
  (c) pipeline touch points: SPY/VIX history dependency at
  row-expansion + tab header addition (CLAUDE.md header invariant).
- NOT an operator-verification tool: computed deterministically at
  row-expansion like the rollup columns; the operator never computes or
  adjudicates it, the ladder just reads the column. If it required
  manual verification it would fail its own purpose (removing judgment
  from the gate).

**No-lookahead spec for `mech_regime` (user requirement: every component
computable as-of D, no future data).** The rule family is causal by
construction — trailing 50-SMA, trailing 20d return, VIX close, trailing
5d VIX change, all from data ≤ D close, ahead of the D+1-open entry.
"Accuracy" = decision utility under point-in-time discipline (no
ground-truth regime exists). Four leak doors, each guarded:
1. Threshold mining — thresholds FROZEN a priori from convention
   (VIX 20, 50-SMA, 20d-return sign), never iterated against P&L.
2. Full-sample normalization — banned; fixed constants or
   expanding-window only.
3. Label revision — label for D written once from data ≤ D, never
   recomputed with later data.
4. Validation-as-fitting — nothing is fitted; pre-registered cuts only
   (mech BEAR+H veto separation, Tier-A sharpening), time-split +
   post-13c holdout, plus threshold perturbation (VIX 18/22, 40/60-SMA):
   if conclusions flip, the rule is fragile → don't ship.
Division of labor kept: model label = forward-looking view (hedging
flow/VVIX), mech label = trailing state; "veto if EITHER says BEAR+H"
remains fully causal.

**Improvement queue re-ranked (protects-live-capital × evidence ÷ cost,
version-bump tax counted):**
1. Close the live loop — IBKR fills → analysis-row + tier mapping →
   live-vs-backtest eval at ~30–50 positions. Only item that turns
   "confirmed in backtest" into "proven".
2. Mechanical regime overlay — gated re-cut on the 913-row book, ship
   `mech_regime` column only if the veto/Tier-A cuts sharpen.
3. Credit tail cap — max-risk-per-underlying sizing rule (bull_put
   dollar-negative purely from ORCL/SMH-style concentration); one-line
   deployment-doc change, queues for next gate (mid-window freeze).
4. Per-regime exit switch study — after #2, on mechanical cuts (failed
   LOO twice on model-label cuts; biggest non-selection lever).
5. Eval-harness statistical hygiene — date-clustered inference (same-date
   rows share one path; current p-values optimistic) + dedup guard for
   double-analyzed dates (2026-03-06).
6. Version-bump batch (all at once, never piecemeal): bear_put emission
   demotion + E-VOL definition tightening + prompt wording cleanups.
NOT worth improving: score_total, lean scrape profile,
oi_confirm/cpir/iv_pct as predictors.

### 2026-07-22 addendum 3 — mech_regime re-cut RUN: gates NO-SHIP, hypothesis rejected

Ran the gated re-cut (subagent; script `backtests/mech_regime_recut.py`,
full output `backtests/mech_regime_recut_output.txt`, SPY/^VIX daily via
yfinance in `backtests/mech_regime/spy_vix_daily.csv`). Frozen spec as
per addendum 2 (SPY 50-SMA + 20d-return sign; VIX 20 H-bound, E = ≥30 or
+25%/5d). 913-row pooled book; 149 rows (15 early dates, insufficient
50d lookback in the fetched window) excluded from label cuts, flagged
not defaulted.

- **Agreement is LOW**: date-level direction 51%, vol 43%, both-match
  23%. The model and the mechanical read genuinely describe different
  things.
- **Mar-2026 catch (the motivating case): CONFIRMED** — mech/OR veto
  catches 100% of the −25.2 Mar-2026 cluster loss vs 66% for the model
  veto (03-06's −13.1 was the miss).
- **KILL CRITERION: TRIPPED.** The subset the OR-veto would newly
  remove (mech BEAR+H/E, not model) is n=202, mean +0.33, **net +66.2**
  — the model's overrides of the mechanical read are systematically
  RIGHT, exactly the Apr-2025 early-right shape (Apr-2025 breakout:
  n=70, +12.2). Net-positive in BOTH time-split halves (+50.1/+16.2)
  and under all 4 threshold perturbations (VIX 18/22, 40/60-SMA; range
  +10.9..+88.3). No sign flips anywhere → the rejection is robust, not
  threshold luck.
- **AND-promote for Tier A: fails worse** — AND-A mean +0.26 vs current
  A +0.60; the rows it demotes average **+0.76** (it demotes the best
  performers); n retained 32%. Robust across perturbations.
- **Ladder replay (top-3/day)**: current model-label ladder dominates —
  pooled +100.9 vs hybrid +44.5 vs mech-only +42.6; post-13c +50.5 vs
  +41.0/+41.7.

**Decisions:** OR-veto NO-SHIP, AND-promote NO-SHIP, `mech_regime`
pipeline column NOT added — the ladder stays on model labels, and the
07-21 "22/85 mech-BEAR days labeled RANGE" observation is now
understood as informative disagreement, not label noise. Queue item #2
is CLOSED (answer: cosmetic-negative). The artifact is NOT wasted: mech
labels + fetch script are the prerequisite for the per-regime exit
switch study (queue #4), which now moves up behind #1 (live loop).
Caveats: 149-row lookback exclusion (extend the SPY fetch window before
reusing labels for the exit study); 2026-03-06 double-analysis rows
flagged throughout; subagent noted a possible narrower, event-scoped
mech-veto — NOT pre-registered, treat as idea only, no P&L peeking
follow-ups this window.

### 2026-07-22 addendum 4 — per-regime exit switch on MECH labels: stays GATED (5/6 criteria pass, median criterion fails by construction)

Ran queue #4 (subagent; `backtests/exit_switch_mech_study.py`, output
`backtests/exit_switch_mech_study_output.txt`; SPY/VIX refetched from
2023-06-01 → `backtests/mech_regime/spy_vix_daily_full.csv`, 663/663
debit rows labeled, prior 149-row gap closed). Harness validated first:
250/250 real debit rows reproduce DEBIT_PROD exactly ($27,648.70, diff
$0.00). Scope note: the pre-registered switch only alters DEBIT exits
(credit PROD already has no time-exit), so this was run as a debit-side
study; also surfaced that BacktestResults mixes pre/post-Attempt-13
credit exit configs — no single credit PROD reproduces the whole credit
book (remember for any future credit replay).

- **Fixed switch, pooled**: PROD +65.8 → model-keyed +75.1 → mech-keyed
  +76.3 pnl_pct ($75.1k → $88.6k). Post-13c: PROD +10.2 vs mech +20.3
  ($8.8k → $22.6k) — mech keying clearly best, and strongest on current
  emissions.
- **Per-cell**: BEAR+H/E trail .50/.50 +$4.4k, L-VOL tef-null +$9.9k
  both right-signed; RANGE/BULL+E pt-1.10 clause is a net LOSER (−$0.8k)
  — the Attempt-13 pt-1.10 candidate is dead, LOO correctly rejects it.
- **LOO by date**: mech total +10.4, 76% of dates non-negative, both
  time halves positive, post-13c positive, no perturbation flips (VIX
  18/22, SMA 40/60). Model-keyed switch: total +8.1, only 21.5% dates
  strictly positive. Mech keying ≈2× the strictly-positive-date rate.
- **BUT ship gate fails on "LOO median > 0"**: median fold-gain is
  exactly 0 — the exit variants are a no-op on most paths (trades that
  hit PT early exit identically), so the delta is zero-inflated and the
  median criterion can never trip. 5/6 criteria pass.

**Decision: stays GATED — no post-hoc criterion relaxation.** The
median>0 bar was pre-registered; loosening it after seeing the data is
criterion-shopping. But the criterion is now understood to be
mis-specified for a zero-inflated delta, so the corrected gate is
PRE-REGISTERED NOW for the next evaluation window (new data only):
median fold-gain > 0 **among affected dates** (dates where the switch
changes ≥1 exit) AND affected-date count ≥ 25 AND total > 0 AND both
halves positive AND no perturbation flip. If that passes on the next
window, ship the mech-keyed debit switch (trail .50/.50 in mech
BEAR+H/E; tef-null in mech L-VOL; NO pt-1.10 clause).

**Division-of-labor picture is now coherent and evidence-backed**:
model labels win for SELECTION gates (addendum 3 — forward-looking
overrides are right), mech labels win for EXIT conditioning (trailing
path environment). Same-day symmetry, opposite winners, both robust.
Queue state: #2 CLOSED, #4 re-gated with corrected criterion, #5
partially absorbed (both new scripts report date-clustered stats +
03-06 flag), #3/#6 wait for next gate/version bump, #1 ON HOLD until
user initiates.

### 2026-07-22 addendum 5 — live loop STAGE 1 built (queue #1, user-initiated): mapping plumbing works, slippage blocked, compliance clean post-ladder

User green-lit stage 1 only (harness + audits at small n; the live-vs-tier
performance eval stays gated on ~30–50 closed positions). Inputs: IBKR
DAYS_30 trades + open positions snapshotted to
`backtests/live_loop/ibkr_snapshot_2026-07-22.json`; harness =
`backtests/live_loop/stage1_map_fills.py` → `stage1_report.md` /
`stage1_output.txt` (Opus subagent build; idempotent, local-only).

- **Inventory:** 18 combo entries (9 open, 9 closed round-trips), 21 closing
  fills, 2 calendar-overlay short calls (AMD Jul31 620C over Oct 540/640;
  TSM Jul31 470C over Sep 470/590 — flagged, not force-matched), 15 legs
  identity-UNKNOWN (closed positions can't join against open-position
  average_price; open ones all pinned <$0.02/share).
- **Mapping:** EXACT 0 / STRUCTURE 3 / NONE 15. The 15 NONEs are June/early-
  July fills before daily analysis coverage (export has no dates 2026-06-23
  →07-07). The 3 mapped: QQQ bear_put (signal 07-17), TSM bull_put (07-14,
  live 370/390 vs analysis 400/385), META short put (07-16, family-match to
  a bull_put play — weak).
- **Compliance — corrected from the subagent's headline.** Subagent flagged
  TSM (fill 07-15) + META (fill 07-17) as Veto-#3 hits (credit in
  RANGE+L-VOL). Both fills PREDATE the ladder (deployment-rules.md derived
  07-19) — they are not violations, they're pre-ladder trades the ladder
  would now veto (which is the ladder doing its job, and consistent with
  Wing's own account of starting ladder deployment ~07-19/21). The only
  post-ladder mapped entry, QQQ bear_put (fill 07-20), was top available
  tier that date (Tier C) → post-ladder compliance 1/1. Keep the pre/post-
  07-19 split in ALL future compliance reads.
- **Slippage: BLOCKED, n=0.** BacktestResults/BacktestProxy stop at
  2026-03-27 — no modeled next-open entry exists for any July date. Unblock
  path: run the real backtest over the 2026-07 window once its inputs are
  enriched, then stage1_map_fills.py picks the comparison up automatically.
  (Also noted: the exports' `daily_price_csv` column carries inline mark
  data, not a file path — harness handles it.)
- **n status:** 3 mapped entries, 9 closed round-trips vs the ~30–50 stage-2
  threshold. Stage 2 remains accumulation-gated.
- Caveats: bull_put tier checks PARTIAL (short-leg entry delta not on
  analysis rows — DTE proxy only; check delta in IBKR at order entry per
  deployment-rules); META map is short-put-vs-spread family, not exact;
  closed-leg identities rest on net-sign inference.

### 2026-07-22 addendum 6 — Barchart historical coverage floor PROBED: the pre-2024 data branch is CLOSED

Context: user observed bear-regime MFE looks positive while exit capture
looks bad — i.e. the addendum-4 BEAR+H/E trail .50/.50 cell (+$4.4k,
right-signed). That switch stays GATED behind a corrected criterion that
needs NEW data. Problem with the gate as written: its value concentrates
in BEAR/H-VOL dates, which only accumulate forward *during* the regime it
protects against. So the branch tested here was "get unfitted bear/high-vol
data from history instead of waiting."

Probe (read-only, no Drive writes; `BarchartSession.download_csv` against
`?type=historical&historicalDate=`). Dates 2022-06-13, 2022-10-13,
2023-06-01, 2023-09-15, 2023-10-20, 2024-02-15, 2024-08-05, 2025-04-04,
2026-04-21, on `options-flow/stocks` + `unusual-activity/stocks`.

- **`options-flow` silently serves a FALLBACK payload past its retention
  window.** It accepts `historicalDate`, returns HTTP 200, correct 19-col
  schema, and exactly 500 rows — but the content is junk: every stale date
  is topped by `SNDK @ 1589.4, strike 2270, exp 2027-01-15`. Two 2022 dates
  returned byte-identical files (`sha 45747e39`). **A naive
  `--start 2022-01-01 --end 2022-12-31` backfill would have "succeeded"
  with no errors and poisoned every date with duplicated fake flow.**
  Worth a guard in `scrape_flow.py` (see below).
- **Flow coverage floor is between 2023-10-20 and 2024-02-15.** Junk:
  2022-06-13, 2022-10-13, 2023-06-01, 2023-09-15, 2023-10-20. Real:
  2024-02-15 (META 485, CVNA 55.97, SMCI 1004 — all era-correct),
  2024-08-05, 2025-04-04, 2026-04-21.
- **`unusual-activity` DOES reach back to 2022** with genuine per-date
  content (2022-06-13: CHPT 12.08, NKLA 5.23; 2022-10-13: LAZR 7.38,
  CAT 183.14; distinct hashes, 1,395–1,603 rows/day).

**Verdict — branch CLOSED, twice over:**

1. *2022* — unusual-activity only. The missing flow file is where
   `Premium`/`Side`/`IV`/`Delta` live, i.e. the entire `[FLOW]` signal.
   A flow-less backfill is structurally different input from the fitted
   book, so any gate evaluated on it is confounded by input composition —
   the same confound class that killed `score_total`. Not acceptable.
2. *Aug–Oct 2023* (the only untouched stretch that would mech-label
   BEAR/H-VOL — SPX ~-10%, VIX low-20s) — **below the flow floor, not
   fetchable.** The one pre-2024 window that would have exercised the
   BEAR+H/E clause on unfitted data does not exist.

Everything actually fetchable-but-unfitted before 2024 reduces to roughly
Nov 2023 – Feb 2024: a low-vol melt-up. Wrong regime for this clause, and
not worth the full enrichment chain (enrich_oi D+1 + counterpart IV + IV
pct + price catalyst + compile + analysis + backtest + proxy).

**Consequence:** the addendum-4 corrected gate can now ONLY be satisfied by
forward live/backfill dates in BEAR/H-VOL. The exit switch cannot be
de-gated on historical data. Remaining choice is binary and is a user
decision: (a) keep waiting and accept degraded exit capture through the
next bear leg, or (b) ship the BEAR+H/E trail .50/.50 clause ALONE (NOT the
L-VOL tef-null clause, which has no urgency) as a documented pre-gate
exception with a pre-registered rollback trigger — the pattern used for the
Attempt-13 credit stop removal, which was later tested on a fresh 51-row
window and held. DECISION PENDING.

**Spun-off TODO (independent of the above):** add a staleness guard to
`scripts/collector/scrape_flow.py` historical mode — reject a downloaded
flow CSV whose rows don't correspond to the requested `historicalDate`
(cheap check: fallback payload is recognisable by its fixed 500-row count
plus a first-row symbol/price that repeats across dates; a stricter check
is that no `Exp Date` should precede the requested date). Without it every
future out-of-range backfill fails silently.

### 2026-07-22 addendum 7 — SHIPPED: BEAR+H/E trail .50/.50 as a pre-gate exception

Decision taken (user: "we ship") after addendum 6 closed the historical-data
route. Shipping ONE cell of the addendum-4 mech-keyed switch.

**What shipped**

- `lib/mech_regime.py` — NEW. Frozen spec promoted out of the study scripts
  into a pure, dependency-light module (`csv` + `bisect`, no pandas):
  `compute_mech_table()` + `MechLabeler.label()/.cell()`. Verified against
  `backtests/exit_switch_mech_study.compute_mech_table` — **786/786 rows exact
  match, 0 mismatches.** Thresholds are module constants; changing any of them
  invalidates addendum 4 and everything resting on it.
- `config/backtest.yml` → `simulation.regime_exit` — enabled, cells =
  `{BEAR_HE: {trailing_stop_trigger: 0.50, trailing_stop_pct: 0.50}}`.
  LVOL tef-null is NOT shipped (right-signed +$9.9k but no urgency — stays
  behind the corrected gate). RB_EVOL pt-1.10 stays dead.
- `scripts/backtest/simulate.py` — `_effective_sim_cfg` gains an optional
  `signal_date` and a debit-only regime merge, same presence-based semantics
  as the credit block, applied at the single existing merge point. **Credits
  are never regime-switched** (credit PROD has no time exit and was outside
  the study's scope). Legacy 2-arg calls keep PROD behaviour.
- `config/deployment-rules.md` — new §"Exit management" with the manual live
  rule (this is the surface that actually protects the book; the backtest
  change exists to keep future evaluations measuring what is traded).
- `backtests/mech_regime/fetch_spy_vix.py` — gained `--full`, which refreshes
  the PRODUCTION table (`spy_vix_daily_full.csv`, start 2023-06-01) through
  today. Previously the script only wrote the short study csv with a
  hardcoded end date, so the production table had no refresh path at all.
- `tests/test_mech_regime.py` — 12 tests (label spec, as-of lookup, the
  dropped-VIX-only-row trap, debit switch, credit non-switch, disabled flag,
  missing csv, no signal date, legacy call). Full suite: **453 passed.**

**Safety behaviours, deliberate:** a missing SPY/VIX table disables the
override with a warning rather than failing the run (every pre-override result
stays reproducible without it); `dir_ok=False` (pre-50-SMA) is never treated as
a regime; a signal date past the table's end logs a staleness warning naming
the refresh command — the addendum-6 lesson about inputs that fail silently.

**Status: PRE-GATE EXCEPTION.** Not a cleared rule. The addendum-4 corrected
gate is unchanged and still pending.

**ROLLBACK TRIGGER (pre-registered):** evaluate at ≥25 affected BEAR+H/E dates
of NEW data. Revert `regime_exit.enabled` to false if the cell's total gain vs
PROD is ≤ 0, OR if the affected-date median gain is < 0. Passing promotes the
cell from exception to cleared, and re-opens the LVOL cell for its own gate.

**NOT re-run:** the existing backtest book was not re-simulated under the new
config. Every BacktestResults/BacktestProxy row currently on file is PROD-basis.
The next full run will mix bases unless it re-runs everything — decide that
before the next evaluation, and record which basis each row used.

### Addendum 8 — `exit_basis` column (2026-07-22, same day)

Closes the open item above. **One column, no new tab, no archiving.**

Correction to a claim made in addendum 7's discussion: there is no
"forward-only" run. `core.py` has NO already-tested filter — a bare
`python3 -m scripts.backtest` loads the entire analysis tab and re-simulates
every play, and `sheets_client.append_rows` is a blind append with no dedup
(the `_meta` hash dedup is analysis-pipeline only). So every default run is a
full re-run that appends a second copy of the whole book.

That is fine once each row says which basis produced it:

- `exit_basis` ∈ {`PROD`, `CREDIT`, `BEAR_HE`, `NONE`}, set in
  `simulate._exit_basis` from the same `_regime_override` call that drives the
  merge (which now returns `(cell, override)` so the label can never disagree
  with the config actually applied — there is a test asserting exactly that).
- **Blank = pre-2026-07-22 = PROD-basis by definition.** No backfill needed.
- Appended LAST in both `_KEY_ORDER` and `_PROXY_KEY_ORDER` (positional Sheets
  append; a test pins it to the last position in both).
- `NONE` is reserved for the proxy `underlying_trend` tier, where no exit rules
  run at all — distinct from blank on purpose.

Because a full re-run writes a COMPLETE book, an evaluation just reads the
latest run's rows (non-blank `exit_basis` + `created_datetime`) and ignores
everything older. The duplicate rows are inert history, not double-counting.
Documented in `config/backtest-reference.md` §"Exit basis", including the
warning that the tabs are append-only.

Rejected as over-engineering: a versioned `BacktestResults_v4` tab, and a
`regime_exit.effective_from` date. The column subsumes both, and
`effective_from` would have put two exit regimes inside one book.

Full suite: **459 passed.**

### 2026-07-22 addendum 9 — SHIPPED: `mech_cell` on the analysis row (live read)

**Why.** Addendum 7 shipped the BEAR+H/E exit override into the *backtest*, and
`config/deployment-rules.md` §"Exit management" states the matching live rule as
prose thresholds (SPY vs 50-SMA, 20d return, VIX ≥ 20) to be eyeballed at deploy
time. Nothing computed it. User: *"if you don't store it anywhere, when it's
live, i can't use it to make decision on exit."* Correct — and it bit twice: at
entry (which exit profile applies to today's play) and at the addendum-7
rollback gate, which needs a count of affected BEAR+H/E dates of NEW data that
no surface was recording.

Earlier argument against storing it (it's recomputable from the date, so join it
on demand) was right about *computation* and wrong about *access*. Recomputable
only helps if something actually runs the computation at decision time.

**What shipped**

- `lib/mech_regime.py` — `MechLabeler.covers(d)` + `cell_for_date(csv, d)`
  returning `(value, warning)`. Deliberately STRICTER than `.cell()`: `.cell()`
  is as-of (most recent trading day ≤ D), which is right for a historical
  backtest date but wrong for a live one — it will happily label 2029 off a 2026
  close and say nothing. `cell_for_date` returns `NO_DATA` past the table end.
  Test pins the divergence.
- `scripts/analysis_pipeline/config.py` — `mech_cell` appended LAST in
  `ROW_COLUMNS` (positional append; test pins last position) + `MECH_REGIME_CSV`.
- `core.py` — `_mech_cell(date_str)` logs a WARNING when unavailable and never
  raises; passed into `analysis_to_rows(..., mech_cell=)` rather than read inside
  it, so tests stay independent of the local SPY/VIX table.
- Values: `BEAR_HE` / `LVOL` / `RB_EVOL` / `NONE` (labelled, no cell) / `NO_DATA`
  (table missing or ends before D). No blank — blank would be indistinguishable
  from a pre-column row, the same trap `exit_basis` avoids.
- Market-level, so the SAME on every row including MARKET, unlike the per-ticker
  rollup blocks that blank there.

**NOT read by the backtest** — `simulate.py` keeps recomputing from `signal_date`
at run time. One label source, two surfaces; the analysis column is for the human
at deploy time only.

**REQUIRED before the next analysis run:** extend the header of AnalysisClaude,
AnalysisGPT and AnalysisTickerSpecific by one cell (`mech_cell`), or new rows
write an unlabelled trailing column. Header-only — append-at-end needs no row
shift.

**Open fragility (not fixed here).** `backtests/mech_regime/spy_vix_daily_full.csv`
is the production table behind a SHIPPED exit rule, and it is: fetched by hand
from yfinance (`fetch_spy_vix.py --full`), gitignored under `backtests/*`, absent
from Drive, and local to one machine. It was already one day stale at the time of
writing (ends 2026-07-21) — so today's live call returns `NO_DATA` rather than a
silent stale answer, which is the guard working as intended, but the refresh is
still manual and unscheduled. Options if this recurs: fold `--full` into the
existing scrape workflow, or commit the CSV.

Full suite: **465 passed.**

### 2026-07-22 addendum 10 — SHIPPED: SPY/VIX table into Drive + CI (was one-laptop)

**The finding that forced this.** Chasing "can we scrape it on GitHub" surfaced
that `backtests/` is untracked in its entirety (`.gitignore`: `backtests/*`;
`git ls-files backtests/` = `.gitkeep` and nothing else). So
`fetch_spy_vix.py` — the producer of the production table behind the SHIPPED
BEAR_HE override — was not in the repo either. Not just the data on one laptop:
the code too. CI could not have run it.

**What shipped**

- `scripts/collector/fetch_mech_regime.py` — tracked, collector convention.
  Default direction = yfinance → local CSV → Drive; `--download` = Drive →
  local. Two directions kept separate and neither implicit.
- Drive layout: single file `spy-vix-daily.csv` at the ROOT, not under a
  `{YYYY-MM-DD}/` folder — one continuous series replaced wholesale, not a
  per-date snapshot. `DriveClient.root` added to expose the root folder id.
- `compile-flow.yml` — refresh step appended (22:30 UTC cron, already post-close
  and already Drive-authed). `requirements-compile.txt` gained `yfinance>=0.2`;
  its header explicitly said "no yfinance", so the step would have failed on
  import otherwise.
- Makefile — `mech-regime` target (download only). `backtest`, `backtest-proxy`,
  `analyze`, `analyze-gpt` all depend on it. **The freshness step lives in make,
  not in Python**: `lib/mech_regime.py` is called per-row inside the backtest
  and stays pure/offline, and a backtest should reproduce against a fixed table
  rather than silently re-fetch mid-run.

**Verified end to end**: upload → delete local → `make mech-regime` → restored
(36,729 bytes, 788 rows, 2023-06-01 .. 2026-07-22).

**Two behaviours worth knowing**

- An in-progress trading day is NOT labelled. On 2026-07-22 the fetch wrote a
  row with a VIX print and no SPY close (US market still open); `compute_mech_table`
  drops SPY-less rows, so `cell_for_date` returns NO_DATA. Correct — a label off
  a partial bar is worse than no label — but it means an analysis run before the
  US close writes `mech_cell=NO_DATA`. Test added.
- `lib/logger.py`: a script logger not listed in `_OWN_LOGGERS` inherits root
  (WARNING), so its `log.info` is silently dropped — the script works and prints
  nothing. Hit this on the new collector. Added `fetch_mech_regime` and left a
  NOTE: `enrich_oi`, `fetch_counterpart_iv`, `fetch_iv_percentile` and
  `fetch_price_catalyst` are all still in that state (pre-existing, untouched).

Full suite: **466 passed.**

