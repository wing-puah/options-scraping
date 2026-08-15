"""
Daily trade journal — pull the day's fills, reconcile them against the analysis
that proposed them, report the book's delta exposure, and recommend what to
deploy next session.

PRODUCTION TIER. Runs daily, writes a durable record. This is the counterpart to
`scripts/live_loop/`, which audits the same ground fortnightly and in more
depth; both share one encoding of the deployment ladder
(`scripts/live_loop/mapping.py`) so the two can never disagree about a tier.

Every step is a deterministic script. Exactly ONE step calls a model — the
judgment pass in `recommend.py`, which is shown only plays the rules have
already cleared and cannot promote anything the rules vetoed.

Run: `python3 -m scripts.journal`  (see __main__.py for the flag matrix)
"""
