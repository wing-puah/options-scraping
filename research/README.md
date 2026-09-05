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

| File or folder | What it holds | Maintained by |
|---|---|---|
| [`overview.md`](overview.md) | The dated one-page state of the research programme. A summary of the three files below it. | hand |
| [`current.md`](current.md) | The running tuning log. New entries are appended here. | hand |
| [`next-steps.md`](next-steps.md) | The open queue, numbered by section. | hand |
| [`deployment-evidence.md`](deployment-evidence.md) | Why each operator-card rule exists: derivation, validation tables, caveats, and the open rollback triggers. | hand |
| [`study-map.md`](study-map.md) | One-page map of `scripts/backtest_study/`: what each study asks and what it concluded. | hand |
| [`glossary.md`](glossary.md) | Metric and term definitions (`R`, `meanR`, `CI`, `LOO`, `MWU`). | hand |
| [`arm-index.md`](arm-index.md) | Every arm, gate, and criterion label, grouped by study. Labels are study-local. | hand |
| [`replication-protocol.md`](replication-protocol.md) | The two-analyst replication protocol for grading a study report. | hand |
| [`analysis-roadmap.md`](analysis-roadmap.md) | The longer-range plan for the analysis pipeline itself. | hand |
| [`writing-guide.md`](writing-guide.md) | How to write in this folder. Adopted 2026-09-05. | hand |
| [`pre-registrations/`](pre-registrations/) | One file per study: the plan written before the run. Foldered `f1_selection/` to `f4_deployment/`. | immutable |
| [`study-results/`](study-results/) | One append-only file per study: what it last printed, per export era, quoted verbatim. | machine (`make study-record`) |
| [`archive/`](archive/) | The tuning log by period, 19 volumes. Old entries move here when `current.md` passes about 400 lines. | hand, status lines only |

`deployment-evidence.md` is a summary of the tuning log, not a second source.
When the two disagree, the log wins.

Every archive volume carries a status line, and that line is the only thing in
`archive/` meant to change. [`archive/README.md`](archive/README.md) states the
rule, indexes the 19 volumes, and holds the full section index of what is in
each one.

## Running a study

Study code sits in four family folders under `scripts/backtest_study/`:
`f1_selection/`, then `f2_management/`, then `f3_structure/`, then
`f4_deployment/`. Pick it, manage it, wrap it, fund it. A study's bare name is
unaffected by which folder it sits in. `backtests/` holds only data: the Sheets
exports a study reads from `backtests/to_evaluate/`, and the reports it writes
to `backtests/study_output/`.

```bash
source .venv/bin/activate
python3 -m scripts.backtest_study list                 # what's available
python3 -m scripts.backtest_study run bear_deploy      # run one
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

## Recording, reviewing, charting a study

**Recording.** `make study-record` reads each `<name>-latest.txt` and appends a
section to [`study-results/`](study-results/), keyed on era and git sha. This
matters because a study runs on the current era only, so the next era's re-run
overwrites the gitignored report. `current.md` holds the reasoning and
`study-results/` holds the index.

**Reviewing.** `make study-review ARGS="<study>"` (or `python3 -m
scripts.study_review <study>`) runs the study, grades the report with analyst A,
analyst B and a validator, then writes a plain-language digest. Four files land
in `backtests/study_output/`, and the digest is also rendered to
`site/<study>-digest.html` and linked from that study's card on the map. See
[`replication-protocol.md`](replication-protocol.md) for the manual path and the
full flag list.

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
