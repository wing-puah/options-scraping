# Backtest exit rule tuning log

Running log of parameter experiments — what worked, what didn't, and why.
Original dataset: 119 trades across July 2024 (chop), Jan 2025 (bull), March 2025
(panic/correction), Feb 2026; later evaluations run on the pooled real + proxy book.

**Newest work lives in [`current.md`](current.md).** Everything older is split by
period under [`archive/`](archive/). Append new entries to `current.md`; when it
grows past ~400 lines, move its oldest sections into a new archive file and add a
row to the index below.

## Running a study

Study code lives in `scripts/backtest_study/` (tracked). `backtests/` is
disposable scratch and holds only data: the Sheets exports it reads from
`backtests/to_evaluate/`, and the reports it writes to `backtests/study_output/`.

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
write up backtests/study_output/bear_deploy-latest.txt
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
`docs/study-map.html`: what each of the 18 studies asks, what it concluded, and
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

One run writes two files. `backtests/study_output/account_sim-charts-latest.html`
is a bare fragment, which is what the Artifact publisher wants; `docs/account-sim-charts.html`
is the same page wrapped as a standalone document and is **tracked**, for the
same reason `docs/study-map.html` is — it has to open from a fresh checkout
without running anything first. The `--structure-universe` arm writes only the
scratch fragment and never a tracked page: the widened candidate set moves the
book by a handful of picks, so its page reads the same as the frozen book's
chart for chart, and a second tracked page would only cost a reader a diff to
learn there was nothing to learn. `--no-docs` writes only the scratch fragment;
`--standalone --open` views it off disk. `make study-docs` rebuilds every
tracked docs page — the map and the readouts — without running a study.

It renders, it never concludes. Every figure is either read out of the report
text or recomputed from `<study>-positions-latest.csv`, and the recomputed ones
are **reconciled against the report before the page is written** — a mismatch
exits non-zero rather than drawing a chart that disagrees with the study. That
check is what catches the easy mistake here: `account_sim-latest.txt` is
whichever ARM ran last, which is not necessarily the arm that wrote
`account_sim-positions-latest.csv`, so the report is chosen to match the
positions file's arm (pass `--positions .../account_sim-positions-structure-latest.csv`
for the `--structure-universe` arm). The renderer also may not introduce a
statistic the study refuses to print — no annualised figure, no Sharpe, no
time-to-recover.

### The regime breakdown page

`python3 -m scripts.study_charts.regime` (or `make study-chart-regime`) draws a
second page over the same run, `docs/account-sim-regime.html`: which structures
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

## Companion documents

| Document | What it holds |
|---|---|
| [`study-map.md`](study-map.md) | **Start here.** One-page map of `scripts/backtest_study/` — what each study asks and what it concluded. Rendered, with each study's last run quoted onto it, as [`docs/study-map.html`](../../docs/study-map.html) (`make study-map-open`). |
| [`../deployment-rules.md`](../deployment-rules.md) | The operator card — what to deploy, what to veto, how to exit. Instructions only. |
| [`deployment-evidence.md`](deployment-evidence.md) | Why each of those rules exists: derivation, validation tables, caveats, and the **open pre-registered rollback triggers**. |
| [`ml-plan.md`](ml-plan.md) | The ML combination-search plan (RUN 2026-08-11, null result). |
| [`replication-protocol.md`](replication-protocol.md) | The two-analyst independent-replication protocol (`research-analyst` × 2 + `research-validator`) for grading study reports and exploring train splits. |

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
| 2026-07-19 — Deployment ladder (`config/deployment-rules.md`) | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-20 — Next-25 backtest dates: regime-gap selection | [archive/04](archive/04-pooled-evals-and-ladder.md) |
| 2026-07-21 — ≥800-GATE EVALUATION at 762 pooled priced rows | [archive/05](archive/05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-21 — Edge status: honest assessment + priority queue | [archive/05](archive/05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-21 — Regime-label validation: 86 MARKET rows | [archive/05](archive/05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-22 — Regime-gap backfill: the 13 remaining dates | [archive/05](archive/05-pooled-evals-762-and-regime-labels.md) |
| 2026-07-22 — 25-date gate CLOSED at 913 pooled priced | [archive/06](archive/06-mech-regime-and-shipped-exits.md) |
| 2026-07-22 addenda 1–10 — mech_regime overlay, shipped BEAR_HE trail, `exit_basis`, `mech_cell`, SPY/VIX in Drive | [archive/06](archive/06-mech-regime-and-shipped-exits.md) |
| 2026-07-22 addenda 11–14 — bear_put: cancellation, structure-keyed trail, pre-registration, DEMOTE verdict | [current.md](current.md) |
| 2026-07-22 — Feb–Apr 2026 bear holdout: coverage + backfill status | [current.md](current.md) |
| 2026-08-11 — DEPLOY arm: hedge is real, `|delta| high` pick adopted | [current.md](current.md) |
| 2026-08-12 — edge status after close-out: real, narrow, NOT selection-tunable | [current.md](current.md) |
| 2026-08-12 — bear MFE give-back below the ratchet threshold (candidate, not run) | [current.md](current.md) |
| 2026-08-12 — `be_after` grid RUN: does NOT ship; give-back pattern is in the underlying | [current.md](current.md) |
| 2026-08-12 — day-0 underlying move: ARM C does not clear, no rule; sensitivity is structural | [current.md](current.md) |
| 2026-08-13 — `account_sim`: PRE-REGISTRATION ($25k feasibility, caps, nothing ships) | [current.md](current.md) |
| 2026-08-13 — `account_sim` RUN: caps survive, window doesn't; delta binds, not cash; grammar gap | [current.md](current.md) |
| 2026-08-13 — `calendar_hedge` RUN: R4 exact; H2 power-stopped at n=6, corr wrong-signed; needs new dates | [current.md](current.md) |
| 2026-08-13 — `calendar_hedge --arm S` RUN: 30/30 cells power-stopped; condor NOT EVALUABLE (39.9%); hedge programme blocked on new dates | [current.md](current.md) |
| 2026-08-13 — `calendar_hedge`: PRE-REGISTRATION (calendar candidate + gated ARM S sweep) | [current.md](current.md) |
