"""Backtest tuning studies — the research tier, kept apart from production.

`scripts/backtest/` prices the book. This package ARGUES about it: replays the
stored paths under alternative exit rules, screens selection subsets, and
validates the deployment ladder. Nothing here is imported by production code or
run on a schedule; every module ends in a plain-text report that becomes an
addendum in `research/current.md`.

THE PACKAGE LISTING IS THE ARGUMENT. `scripts/journal/` names its files `sNN_`
because it is a pipeline and the listing is its FLOW. Studies are not a
sequence — twenty of them argue past each other about four different questions —
so the folders carry the ordering instead, and the order is real: it is the
order a play moves through the system.

    f1_selection/    ① which plays are worth taking?
                        Mostly null. 0 of 496 bear subsets, 0 of 15 ML cells.
    f2_management/   ② when do I get out?
                        Where the edge actually is. Both shipped exit rules.
    f3_structure/    ③ am I expressing the signal in the wrong wrapper?
                        One effect that does not hold out of sample, one
                        survivor that is power-stopped rather than refuted.
    f4_deployment/   ④ can I actually run this?
                        Feasibility, not edge. Nothing ships from here.

    lib/             the shared substrate — the FROZEN harness, the pooled book
                     loader, the validation protocol, the underlying/volume
                     feature families, the live-select arm. Import-only (except
                     `book --validate`), and it argues NOTHING.

    run.py           the runner: `python -m scripts.backtest_study list | run <name>`
    __main__.py      → run.main

Each folder's own `__init__.py` names its studies and their verdicts in one
line each, so `cat scripts/backtest_study/*/__init__.py` is the whole package in
about a screenful.

THE DIRECTORY IS CHECKED AGAINST THE CATALOG. `scripts/study_map/catalog.py`
holds the hand-written verdicts, each tagged with a `family`; the test suite
asserts that a module's family EQUALS its folder and that everything in `lib/`
has no verdict at all. So the split above cannot rot into decoration: put a
study in the wrong folder and the suite says so.

Two things the folders deliberately do NOT change. A study's NAME is its stem,
never its dotted path — `run account_sim`, `account_sim-latest.txt`, and every
citation in `research/` are unaffected by which folder it sits in. And moving a
study between families is a navigation change, never a rename; the report stem
is identity, the folder is a signpost.

Layout history: this code lived under `backtests/study/` until 2026-08-11 and
needed a gitignore exemption to survive there, since `backtests/*` is disposable
scratch. It is source, so it moved to `scripts/`; the scratch tree keeps only
data — inputs in `backtests/to_evaluate/`, reports in `backtests/study_output/`.
The four family folders and `lib/` landed 2026-08-15; before that all thirty
modules sat flat in this directory and the taxonomy existed only on the rendered
study map.
"""
