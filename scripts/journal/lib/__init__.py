"""
Helpers for the daily trade journal — everything the numbered steps lean on but
that is not itself a step.

WHY IT EXISTS. `scripts/journal/` reads top-to-bottom as the pipeline: the files
named `stepN_*.py` ARE the flow, in order, and nothing else sits beside them.
Anything shared, or subordinate to one step, lives here instead:

    rawpull.py    the on-disk pull schema — the contract step1 writes and every
                  later step reads (dependency-free on purpose)
    flexparse.py  IBKR Flex export -> rawpull, plus the flat-book guards  (step1)
    greeks.py     Barchart EOD greeks for the open book, which Flex lacks  (step1)
    book.py       group the broker's flat legs into logical positions      (step3)
    analysis.py   load the AnalysisClaude book             (step2 AND step6 share it)
    prompt.py     prompt text + response parsing for the judgment pass     (step6)

NOT THE REPO-ROOT `lib/`. That one holds modules shared across the WHOLE repo
(Barchart scrapers, Drive/Sheets clients, `structure_names.py`). These are
journal-only, and putting them there is what made this package hard to follow.
Absolute imports (`from lib import sheets_client`) still resolve to the repo-root
package — this one is only ever reached relatively (`from .lib import rawpull`).

PRODUCTION TIER, same as the steps: `research/` may read these, never edit them
for a study's convenience.
"""
