# Research

This folder holds what we learned and how we learned it. The study code that
produced it lives in `scripts/backtest_study/`. The rules it produced live in
[`../docs/deployment-rules.md`](../docs/deployment-rules.md).

## Start here

1. [`overview.md`](overview.md) if you have lost the thread. One dated page: what shipped, what was tried and did not survive, what is open.
2. [`current.md`](current.md) for the newest entries and the state of play.
3. [`next-steps.md`](next-steps.md) for the queue.
4. [`deployment-evidence.md`](deployment-evidence.md) for why each shipped rule exists.
5. [`glossary.md`](glossary.md) for metrics, [`arm-index.md`](arm-index.md) for study-local labels such as `ARM P`.
6. [`writing-guide.md`](writing-guide.md) before you write anything here.

## What lives where

| File or folder | What it holds | Written by |
|---|---|---|
| [`overview.md`](overview.md) | The dated one-page state of the research programme. A summary of the three files below it. | agent |
| [`current.md`](current.md) | The running tuning log. New entries are appended here. | agent |
| [`next-steps.md`](next-steps.md) | The open queue, numbered by section. | agent |
| [`deployment-evidence.md`](deployment-evidence.md) | Why each operator-card rule exists: derivation, validation tables, caveats, and the open rollback triggers. | agent |
| [`study-map.md`](study-map.md) | One-page map of `scripts/backtest_study/`: what each study asks and what it concluded. | agent |
| [`glossary.md`](glossary.md) | Metric and term definitions (`R`, `meanR`, `CI`, `LOO`, `MWU`). | agent |
| [`arm-index.md`](arm-index.md) | Every arm, gate, and criterion label, grouped by study. Labels are study-local. | agent |
| [`replication-protocol.md`](replication-protocol.md) | The two-analyst replication protocol for grading a study report. | agent |
| [`analysis-roadmap.md`](analysis-roadmap.md) | The longer-range plan for the analysis pipeline itself. | agent |
| [`robustness-review.md`](robustness-review.md) | One-page audit of what can be trusted in the analysis, backtest and production loop, and what beyond the queue would improve returns and risk. Rows flip to `FIXED <date>`; a new review replaces the file. | agent |
| [`writing-guide.md`](writing-guide.md) | How to write in this folder. Adopted 2026-09-05. | agent |
| [`pre-registrations/`](pre-registrations/) | One file per study: the plan written before the run. Foldered `f1_selection/` to `f5_hedging/`. | agent, then frozen |
| [`study-results/`](study-results/) | One append-only file per study: what it last printed, per export era, quoted verbatim. | `make study-review` |
| [`archive/`](archive/) | The tuning log by period, 19 volumes. Old entries move here when `current.md` passes about 400 lines. | agent, status lines only |

An agent writes everything in this folder, under
[`writing-guide.md`](writing-guide.md); the operator directs and corrects it.
So the column says what the WRITING is, not who typed it. `agent` means prose
someone reasoned out and may revise. `agent, then frozen` means a plan that
must not change meaning after it is committed. `make study-review` means
generated text — a study's own output, quoted verbatim, that no one edits by
hand.

`deployment-evidence.md` is a summary of the tuning log, not a second source.
When the two disagree, the log wins.

Every archive volume carries a status line, and that line is the only thing in
`archive/` meant to change. [`archive/README.md`](archive/README.md) states the
rule, indexes the 19 volumes, and holds the full section index of what is in
each one.

## Running a study

Study code sits in five family folders under `scripts/backtest_study/`:
`f1_selection/`, then `f2_management/`, then `f3_structure/`, then
`f4_deployment/`, then `f5_hedging/`. Pick it, manage it, wrap it, fund it,
protect it. A study's bare name is
unaffected by which folder it sits in. `backtests/` holds only data: the Sheets
exports a study reads from `backtests/to_evaluate/`, and the reports it writes
to `backtests/study_output/`.

```bash
source .venv/bin/activate
python3 -m scripts.backtest_study list                 # what's available
python3 -m scripts.backtest_study run hedge_sizing      # run one
python3 -m scripts.backtest_study run exit_mechanism_study --side credit
python3 -m scripts.backtest_study run --all            # every study
```

Each run tees its report to `backtests/study_output/<name>-<stamp>.txt` and to a
stable `<name>-latest.txt`. The report opens with a provenance header: git sha,
working-tree state, exact argv, and the row counts and mtimes of the input
exports. The runner then prints the line to hand to Claude for the write-up,
`write up backtests/study_output/<name>-latest.txt`.

**Quote the provenance header's input inventory in the write-up.** Two studies
run against different exports are not comparable. Attributing numbers to the
wrong book has happened here before.

**A non-zero exit is often the correct answer.** Several studies open with a
pre-registered calibration gate, which requires the production rules to
reproduce the stored `exit_reason`, `days_held` and `realized_pnl_pct` exactly.
Such a study stops rather than print numbers it cannot vouch for. That is the
gate working, so do not route around it.

## Reviewing and charting a study

**Reviewing.** `make study-review ARGS="<study>"` (or `python3 -m
scripts.study_review <study>`) is the one command. It runs the study, records
the report, grades it with analyst A, analyst B and a validator, writes a
plain-language digest, and rebuilds the map. Four files land in
`backtests/study_output/`; the digest is also rendered to
`site/<study>-digest.html` and linked from that study's card on the map. See
[`replication-protocol.md`](replication-protocol.md) for the manual path and the
full flag list.

The record is part of the review because the two were never separately useful:
a review grades exactly the report worth keeping. It appends a section to
[`study-results/`](study-results/) keyed on era and git sha, which matters
because a study runs on the current era only — the next era's re-run overwrites
the gitignored report and the record is then the only copy. `current.md` holds
the reasoning, `study-results/` holds the index. Recording is idempotent, so
re-running a review costs nothing; `--no-record` skips it, and `--dry-run` never
records.

`make study-record` still exists for the bulk case — it records every study
with a report on disk, which is what you want after `make study-all`. Reach for
it when you ran studies without reviewing them, not as a step after a review.

**Charting.** `python3 -m scripts.study_charts.account_sim` renders a result as
one self-contained HTML page, and `make study-chart CHART=regime` or
`CHART=compounding` draws the other two. `make study-map-open` rebuilds and
opens `site/study-map.html`, which carries hand-written verdicts and verbatim
last-run excerpts as two separate kinds of claim. `site/` is generated output
and is gitignored, so a fresh checkout has no pages until something builds them.
The rules these renderers obey, including reconcile-before-write, the ban on
statistics the study refuses to print, and why the compounding arm gets its own
page, are in
[`../docs/architecture.md`](../docs/architecture.md#study-review-map-charts)
§ Study review, map, charts.
