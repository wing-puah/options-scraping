"""Study map — what every backtest study is for, and what its last run said.

`scripts/backtest_study/` holds dozens of studies whose reports are long,
fixed-width and written for one careful reading. The map is the opposite: the
"What have the studies found?" section of the project dashboard
(`site/dashboard.html`, built by `scripts/dashboard.py`), which answers "what is
this file even asking?" at a glance and then — for whichever studies have
actually been run — shows what the report printed. It was a page of its own,
`site/study-map.html`, until 2026-10-29.

    python -m scripts.study_map            # rebuild site/dashboard.html
    python -m scripts.study_map --open     # ...and open it in a browser
    python -m scripts.study_map --check    # last-run status per study, no HTML

Two kinds of statement live in that section and they are never mixed:

  * The **standing verdict** is human-written, taken from the write-ups in
    `research/current.md`. It is what the programme concluded.
    It lives in `catalog.py` and only changes when someone edits it.

  * The **last run** block is machine-extracted from
    `backtests/study_output/<name>-latest.txt` by `summary.py`. It quotes the
    report; it never paraphrases one, never scores one, and never fills a gap
    with a guess. A study that has not been run says so, a study whose last run
    exited non-zero says that instead of a number, and an excerpt that is only
    the tail of the report is labelled as the tail.

The rule that makes the section safe to trust: nothing in it may state a
conclusion the study did not print. Where the two-analyst review pipeline has
produced a `<name>-digest-latest.md`, its title line is quoted as such and
attributed; where it has not, the section stays silent rather than inventing a
plain-language gloss.

The runner rebuilds the dashboard after every study run, so the section is
only ever as stale as the last thing you ran.
"""
