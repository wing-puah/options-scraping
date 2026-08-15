"""
Daily trade journal — pull the day's fills, reconcile them against the analysis
that proposed them, report the book's delta exposure, and recommend what to
deploy next session.

PRODUCTION TIER. Runs daily, writes a durable record. This is the counterpart to
`scripts/live_loop/`, which audits the same ground fortnightly and in more
depth; both share one encoding of the deployment ladder
(`scripts/live_loop/mapping.py`) so the two can never disagree about a tier.

THE PACKAGE LISTING IS THE FLOW. Files are named `sNN_<what it does>.py` and run
in that order — `ls` reads top-to-bottom as the pipeline, so no one has to
reconstruct the sequence from the imports:

    s01_pull.py       broker  -> journal/raw/<date>.json      (the only network)
    s02_reconcile.py  fills   -> PositionEvents, matched to the analysis
    s03_risk.py       open book -> delta exposure vs the deployment caps
    s04a_report.py    -> journal/reports/<date>.md
    s04b_page.py      -> site/journal-<date>.html
    s05_writer.py     -> TradeJournal tab + journal/trades.csv
    s06_recommend.py  analysis + open book -> the deploy card
    s07_recwriter.py  -> Recommendations tab + journal/recommendations.csv

Only two unnumbered files sit beside them: `config.py` (the data contract every
step reads) and `lib/`, which holds everything the steps LEAN on but that is not
itself a step — the raw-pull schema, the Flex parser, the Barchart greek
fallback, leg grouping, the analysis loader, the judgment prompt. `sNN_` is a
prefix, not a package boundary; `s` is there only because a Python module name
may not begin with a digit.

Every step is a deterministic script. Exactly ONE step calls a model — the
judgment pass in `s06_recommend.py`, which is shown only plays the rules have
already cleared and cannot promote anything the rules vetoed.

Run: `python3 -m scripts.journal`  (see __main__.py for the flag matrix)
"""
