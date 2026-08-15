# Backtest exit rule tuning log

Running log of parameter experiments — what worked, what didn't, and why.
Original dataset: 119 trades across July 2024 (chop), Jan 2025 (bull), March 2025
(panic/correction), Feb 2026; later evaluations run on the pooled real + proxy book.

**Newest work lives in [`current.md`](current.md).** Everything older is split by
period under [`archive/`](archive/). Append new entries to `current.md`; when it
grows past ~400 lines, move its oldest sections into a new archive file and add a
row to the index below.

## Running a study

Study code lives in `scripts/backtest_study/` (tracked), split into four family
folders — `f1_selection/` → `f2_management/` → `f3_structure/` →
`f4_deployment/` (pick it, manage it, wrap it, fund it) — plus a `lib/` of
shared, verdict-free substrate; a study's bare name (`bear_deploy`,
`exit_mechanism_study`, …) is unaffected by which folder it sits in.
`backtests/` is disposable scratch and holds only data: the Sheets exports it
reads from `backtests/to_evaluate/`, and the reports it writes to
`backtests/study_output/`.

```bash
source .venv/bin/activate
python3 -m scripts.backtest_study list                 # what's available
python3 -m scripts.backtest_study run bear_deploy      # run one
python3 -m scripts.backtest_study run exit_mechanism_study --side credit
python3 -m scripts.backtest_study run --all            # every study
```

Each run tees the report to `backtests/study_output/<name>-<stamp>.txt` and a
stable `<name>-latest.txt`, prefixed with a provenance header — git sha, working-tree
state, exact argv, and the row counts and mtimes of the input exports. The runner
finishes by printing the line to hand to Claude for the write-up:

```
write up backtests/study_output/<name>-latest.txt
```

The write-up is appended here as a new `current.md` section. Quote the header's
input inventory in it — two studies run against different exports are not
comparable, and attributing numbers to the wrong book has happened before.

**A non-zero exit is often the correct answer.** Several studies open with a
pre-registered calibration gate (production rules must reproduce the stored
`exit_reason`/`days_held`/`realized_pnl_pct` exactly) and stop rather than print
numbers they cannot vouch for. That is the gate working; do not route around it.

Paths in `archive/` predate 2026-08-11 and still say `backtests/study/`; the code
they name is now under `scripts/backtest_study/`.

## Running a study review

`make study-review ARGS="<study>"` (or `python3 -m scripts.study_review
<study>`) runs the two-analyst replication protocol headlessly: it runs the
study, then grades the resulting report with analyst A + B and a validator,
then writes a plain-language digest. Four outputs land in
`backtests/study_output/`: `<study>-review-analyst-a-latest.md`,
`<study>-review-analyst-b-latest.md`, `<study>-review-validator-latest.md`,
and `<study>-digest-latest.md`. `--skip-run` reuses the existing
`<study>-latest.txt` instead of re-running the study; `--dry-run` exercises
the pipeline with placeholder outputs and makes no `claude` calls. See
[`replication-protocol.md`](replication-protocol.md) § Automated invocation
for the full flag list and how this relates to the manual, interactive path.

Reading a study report cold? Start with [`glossary.md`](glossary.md) for
metric definitions.

## The map page

Every study run — and every `make study-review` — re-renders
`site/study-map.html`: what each of the 18 studies asks, what it concluded, and
what its own last run printed, alongside the newest sections of `current.md`.
Open it in a browser (`make study-map-open`); rebuild it alone with `make
study-map`, and `python3 -m scripts.study_map --check` prints the same
last-run status as a table.

Two kinds of claim live on that page and the markup keeps them apart. The
**verdict** lines are hand-written in `scripts/study_map/catalog.py` — edit
them there when a conclusion changes, and note that a study with no entry
fails the test suite. The **last run** blocks are quoted verbatim out of
`backtests/study_output/` and are only as fresh as the last run; where a report
has no verdict block, the excerpt is labelled as the tail of the report so it
cannot be misread as a conclusion the study drew.

## Charting a study report

`python3 -m scripts.study_charts.account_sim` renders the account_sim result as
one self-contained HTML page — equity and drawdown, the attrition waterfall, the
binding-constraint census, the adverse-ordering check, sizing, exits, monthly
utilisation, the cap grid, the four arms, and the A1–A6 checklist — with a
PRIMARY/SECONDARY population switch scoping everything below it.

One run writes two files. `backtests/study_output/<name>-charts-latest.html`
is a bare fragment, which is what the Artifact publisher wants;
`site/account-sim-charts.html` is the same page wrapped as a standalone document.
`site/` is **generated output and gitignored** — a fresh checkout has no pages
until something builds them. The `--structure-universe` arm writes only the
scratch fragment and never a `site/` page: the widened candidate set moves the
book by a handful of picks, so its page reads the same as the frozen book's
chart for chart, and a second page would only cost a reader a diff to learn
there was nothing to learn. The `--compounding` arm, by contrast, DOES get its
own page — it is a different sizing basis, not a slightly different candidate
set, and it must never be confused with the frozen book. `--no-site` (still
accepted as `--no-docs`) writes only the scratch fragment; `--standalone --open`
views it off disk. `make study-docs` rebuilds every `site/` page — the map and
the readouts — without running a study.

It renders, it never concludes. Every figure is either read out of the report
text or recomputed from `<study>-positions-latest.csv`, and the recomputed ones
are **reconciled against the report before the page is written** — a mismatch
exits non-zero rather than drawing a chart that disagrees with the study. That
check is what catches the easy mistake here: the report is chosen to match the
positions file's ARM on both axes — structure and compounding — rather than
assumed (pass `--positions .../account_sim-positions-structure-latest.csv` for
the `--structure-universe` arm; the compounding arm has its own page and its own
default). The renderer also may not introduce a
statistic the study refuses to print — no annualised figure, no Sharpe, no
time-to-recover.

### The regime breakdown page

`python3 -m scripts.study_charts.regime` (or `make study-chart-regime`) draws a
second page over the same run, `site/account-sim-regime.html`: which structures
the account actually deployed under each of the two regime readings the book
carries — the mechanical cell from `lib/mech_regime.py`, which selects the exit
profile, and the model read parsed out of `market_regime`, which the deployment
ladder keys the tier off — what each cell cost in reserved capital and
delta-notional, what the caps refused there, and how far the two readings
disagree (on the frozen book's primary population, on 37 of 51 deployed
positions).

**account_sim pre-registers no cut by regime**, and that governs how this was
built. The study prints the cut itself, in a `DEPLOYED BOOK BY REGIME` section
flagged post-hoc with cells under ten positions marked `thin`; the page then
recomputes it from the positions export and reconciles against that section like
every other figure. So the rule for extending it is: **a regime table goes into
the study first, never into the page alone.** A descriptive table nobody
re-derives is where a quiet disagreement would sit forever, and a regime split
drawn as charts is exactly the kind of thing that starts getting quoted as an
edge the study never tested.

### The compounding arm's page

`python3 -m scripts.study_charts.compounding` (or `make study-chart-compounding`)
draws `site/account-sim-compounding.html`, the same readout for the **compounding
sensitivity** arm rather than the frozen book, plus the `EQUITY MARKS` re-mark
series, which exists only on that arm. It reads that arm's own artifacts
(`account_sim-compounding-latest.txt` + `account_sim-positions-compounding-latest.csv`),
both written by the same `run account_sim` that writes the frozen ones.

The separation is the point. The compounding arm is **post-hoc and not
pre-registered**: A1–A6 were registered against a path-INDEPENDENT sim, and
**A2/A5 do not transfer** to it, because their B2 benchmark compounds too, so the
ratio stops isolating the caps. A reader who lands on a page must be able to tell
which basis they are holding without checking a filename, so the page says so in
its own banner and the arms never share an artifact.

## Companion documents

| Document | What it holds |
|---|---|
| [`study-map.md`](study-map.md) | **Start here.** One-page map of `scripts/backtest_study/` — what each study asks and what it concluded. Rendered, with each study's last run quoted onto it, as [`site/study-map.html`](../site/study-map.html) (`make study-map-open`). |
| [`../docs/deployment-rules.md`](../docs/deployment-rules.md) | The operator card — what to deploy, what to veto, how to exit. Instructions only. |
| [`deployment-evidence.md`](deployment-evidence.md) | Why each of those rules exists: derivation, validation tables, caveats, and the **open pre-registered rollback triggers**. |
| [`ml-plan.md`](ml-plan.md) | The ML combination-search plan (RUN 2026-08-11, null result). |
| [`replication-protocol.md`](replication-protocol.md) | The two-analyst independent-replication protocol (`research-analyst` × 2 + `research-validator`) for grading study reports and exploring train splits. |
| [`pre-registrations/`](pre-registrations/) | One immutable file per study: the plan written *before* the run. Kept out of `current.md` so it survives pruning. |
| [`study-results/`](study-results/) | One append-only file per study: what it last printed, per export ERA, quoted verbatim. Foldered `f1_selection/` → `f4_deployment/`, mirroring `scripts/backtest_study/`. Written by `make study-record` from the gitignored reports, so a result survives the scratch being overwritten — which is exactly what cost ~15 reports on 2026-08-15. `current.md` holds the reasoning; this holds the index. |
| [`backlog.md`](backlog.md) | The 2026-06 backtest-engine backlog, **triaged 2026-08-15**. Historical: one item is still open (per-play `invalidation` exits), the rest is fixed, superseded, or *refuted* — including the structure read, which inverted. Not the live queue; that is [`next-steps.md`](next-steps.md) §2. |

The evidence file is a *summary of* this log, not a second source — when the two
disagree, the log wins.

## Section index

| Section | File |
|---------|------|
| Baseline | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 1 — WORSE ❌ | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 2 — WORSE ❌ | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 3 — BETTER, exit config now stable ✓ | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 4 — WORSE ❌ (trailing-on-profit-target) | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 5 — IDENTICAL ❌ | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 6 — BETTER ✓ (profit_target 0.60) | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Rules of thumb learned so far | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| What actually drives losses — confidence, not regime | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| The real next step: confidence-based position sizing | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Financing & IVSpread gates (2026-06-19) | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 7 — BETTER ✓ (profit_target=0.90 + trailing stop) | [archive/01](archive/01-exit-rules-attempts-1-7.md) |
| Attempt 8 — Credit/debit split (2026-07-04) | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Attempt 9 — underlying-price exit study for credits ❌ | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Attempt 10 — BETTER ✓ (debit trailing stop removed) | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Attempt 11 — credit re-check on 18 rows ❌ | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Proxy backtest for untested plays (2026-07-06) | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Entry basis changed: EOD → next-day OPEN (2026-07-06) | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| Attempt 12 — next_open re-baseline + grouped exit study | [archive/02](archive/02-credit-debit-split-attempts-8-12.md) |
| 2026-07-08 — Framework evaluation on MFE/MAE basis | [archive/03](archive/03-evaluations-attempt-13.md) |
| 2026-07-12 — Three-run evaluation (v1 / v2 / v3) | [archive/03](archive/03-evaluations-attempt-13.md) |
| Attempt 13 — bear_call vetoed + credit stop removed ✓ | [archive/03](archive/03-evaluations-attempt-13.md) |
| 2026-07-17 — Power check; scoring-column keep/drop | [archive/03](archive/03-evaluations-attempt-13.md) |
| 2026-07-19 — Final evaluation at 607 pooled rows | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-18 — Early pooled power check at 523 rows | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-19 — Deployment ladder (`docs/deployment-rules.md`) | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-20 — Next-25 backtest dates: regime-gap selection | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-21 — ≥800-GATE EVALUATION at 762 pooled priced rows | [archive/05](archive/05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-21 — Edge status: honest assessment + priority queue | [archive/05](archive/05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-21 — Regime-label validation: 86 MARKET rows | [archive/05](archive/05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-22 — Regime-gap backfill: the 13 remaining dates | [archive/05](archive/05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-22 — 25-date gate CLOSED at 913 pooled priced | [archive/06](archive/06-mech-regime-and-shipped-exits.md) |
| 2026-07-22 addenda 1–10 — mech_regime overlay, shipped BEAR_HE trail, `exit_basis`, `mech_cell`, SPY/VIX in Drive | [archive/06](archive/06-mech-regime-and-shipped-exits.md) |
| 2026-07-22 addenda 11–14 — bear_put: cancellation, structure-keyed trail, pre-registration, DEMOTE verdict | [archive/07](archive/07-bear-put-demotion-thread-and-holdout.md) |
| 2026-07-22 — Feb–Apr 2026 bear holdout: coverage + backfill status | [archive/07](archive/07-bear-put-demotion-thread-and-holdout.md) |
| 2026-07-27 — the pre-engine discretionary book, and the long-dated blind spot | [archive/08](archive/08-pre-engine-book-and-year-split.md) |
| 2026-08-08 — year-split evaluation on refreshed exports: 2025 IS the outlier | [archive/08](archive/08-pre-engine-book-and-year-split.md) |
| 2026-08-11 — completed-book analysis: holdout coverage FULL, DEMOTE fires at n=164 | [archive/09](archive/09-v3-closeout.md) |
| 2026-08-11 addendum — `bs_options_hist` DROPPED: attenuating + replay-contaminating | [archive/09](archive/09-v3-closeout.md) |
| 2026-08-11 addendum — `mech_cell` BACKFILLED across the analysis tabs | [archive/09](archive/09-v3-closeout.md) |
| 2026-08-11 — ML combination search RUN: NULL RESULT; bear `be_after` finding | [archive/09](archive/09-v3-closeout.md) |
| 2026-08-11 — DEPLOY arm: hedge is real, `|delta| high` pick adopted | [archive/09](archive/09-v3-closeout.md) |
| 2026-08-11 — v4 emission-composition bridge: PRE-REGISTRATION | [pre-registrations/v4_bridge.md](pre-registrations/v4_bridge.md) |
| 2026-08-11 — v3 CLOSE-OUT: three findings SHIPPED, production delta measured | [archive/09](archive/09-v3-closeout.md) |
| 2026-08-12 — deployment rules split: operator card vs evidence | [archive/10](archive/10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — v4 bridge: RECORDED DEVIATION from the pre-registration | [archive/10](archive/10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — live loop promoted to tracked code + fill mapper | [archive/10](archive/10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — v1 → v2 → v3 prompt-version comparison + June live-vs-analysis audit | [archive/10](archive/10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — Stage 1 live-vs-tier eval on July | [archive/10](archive/10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — deployment reference stats added to the operator card | [archive/10](archive/10-post-closeout-ops-and-live-evals.md) |
| 2026-08-12 — edge status after close-out: real, narrow, NOT selection-tunable | [archive/11](archive/11-exit-conditioning.md) |
| 2026-08-12 — bear MFE give-back below the ratchet threshold (candidate, not run) | [archive/11](archive/11-exit-conditioning.md) |
| 2026-08-12 — `be_after` grid RUN: does NOT ship; give-back pattern is in the underlying | [archive/11](archive/11-exit-conditioning.md) |
| 2026-08-12 — day-0 underlying move: ARM C does not clear, no rule; sensitivity is structural | [archive/11](archive/11-exit-conditioning.md) |
| 2026-08-12 — `bear_rewrap`: the WRAPPER is worth +0.085 but does not hold up | [archive/12](archive/12-wrappers-and-vol-sleeve.md) |
| 2026-08-12 — `vol_sleeve`: PRE-REGISTRATION | [pre-registrations/vol_sleeve.md](pre-registrations/vol_sleeve.md) |
| 2026-08-12 — `vol_sleeve` RUN: the sleeve DOUBLES DOWN; the calendar is the only survivor | [archive/12](archive/12-wrappers-and-vol-sleeve.md) |
| 2026-08-13 — `account_sim`: PRE-REGISTRATION ($25k feasibility, caps, nothing ships) | [pre-registrations/account_sim.md](pre-registrations/account_sim.md) |
| 2026-08-13 — `account_sim` RUN: caps survive, window doesn't; delta binds, not cash; grammar gap | [archive/13](archive/13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `calendar_hedge` RUN: R4 exact; H2 power-stopped at n=6, corr wrong-signed; needs new dates | [archive/13](archive/13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `calendar_hedge --arm S` RUN: 30/30 cells power-stopped; condor NOT EVALUABLE (39.9%); hedge programme blocked on new dates | [archive/13](archive/13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `calendar_hedge`: PRE-REGISTRATION (calendar candidate + gated ARM S sweep) | [pre-registrations/calendar_hedge.md](pre-registrations/calendar_hedge.md) |
| 2026-08-13 — `account_sim` SIZING ARM ($1,000/position, per-pos 0.40x, net 3.00x) | [archive/13](archive/13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `account_sim` made CONFIG-DRIVEN (`config/account-sim.yml`) | [archive/13](archive/13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — `account_sim` caps reconfigured to 0.25x / 2.50x | [archive/13](archive/13-account-sim-and-calendar-hedge.md) |
| 2026-08-13 — method-config audit: −25 veto RETIRED, OIConfirm dropped, codex engine retired | [archive/14](archive/14-volume-signal-demotion-and-audit.md) |
| 2026-08-13 — bear_put demotion mechanism CHOSEN: card veto §1.4, hedge sleeve carved out | [archive/14](archive/14-volume-signal-demotion-and-audit.md) |
| 2026-08-13 — `volume_signal`: PRE-REGISTRATION | [pre-registrations/volume_signal.md](pre-registrations/volume_signal.md) |
| 2026-08-13 — `volume_signal` RUN: NULL — the volume column is closed | [archive/14](archive/14-volume-signal-demotion-and-audit.md) |
| 2026-08-13 — `account_sim` COMPOUNDING arm: costs money on this book; A2/A5 do not transfer | [archive/14](archive/14-volume-signal-demotion-and-audit.md) |
| 2026-08-14 — `selection_order`: PRE-REGISTRATION (six ordering arms, O4 random control, G0 power pre-check) | [pre-registrations/selection_order.md](pre-registrations/selection_order.md) |
| 2026-08-14 — `selection_order` RUN: POWER-STOPPED at G0 — 7–14% of the book moves, nothing read, nothing refuted | [current.md](current.md) |
| 2026-08-14 — study-suite triage: DEBIT_PROD exact-replay gate unsatisfiable; `bear_position_study` R partly contaminated | [current.md](current.md) |
| 2026-08-15 — structure-name defect FIXED: `bear put debit spread` backtested as a single long option; v4 re-run, v3 frozen | [current.md](current.md) |
| 2026-08-14 — three carried follow-ups closed: verdict grammar TOTAL, ARM H sizing floor skips, criterion (4) reworded | [current.md](current.md) |
| 2026-08-14 — `run --all` GREEN: two dead studies RETIRED, designed refusal now a runner status | [current.md](current.md) |
| 2026-08-14 — study-suite triage FIXED: gate classifies instead of asserting; `exit_basis` column UNUSABLE | [current.md](current.md) |
| 2026-08-15 — `account_sim --live-select` ARM ADDED: shipped selector run under history; 150 unpriceable candidates, 37 below-top-3 slots, §1.3 veto gap | [current.md](current.md) |
