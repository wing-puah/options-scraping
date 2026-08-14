"""Study map — one page that says what every backtest study is for, and what its last run said.

`scripts/backtest_study/` holds nineteen studies whose reports are long,
fixed-width and written for one careful reading. The map is the opposite: a
single self-contained HTML page, opened straight off disk, that answers "what
is this file even asking?" at a glance and then — for whichever studies have
actually been run — appends what the report printed.

    python -m scripts.study_map            # -> docs/study-map.html
    python -m scripts.study_map --open     # ...and open it in a browser

Two kinds of statement live on that page and they are never mixed:

  * The **standing verdict** is human-written, taken from the write-ups in
    `config/backtest-tuning/current.md`. It is what the programme concluded.
    It lives in `catalog.py` and only changes when someone edits it.

  * The **last run** block is machine-extracted from
    `backtests/study_output/<name>-latest.txt` by `summary.py`. It quotes the
    report; it never paraphrases one, never scores one, and never fills a gap
    with a guess. A study that has not been run says so, a study whose last run
    exited non-zero says that instead of a number, and an excerpt that is only
    the tail of the report is labelled as the tail.

The rule that makes the page safe to trust: nothing here may state a
conclusion the study did not print. Where the two-analyst review pipeline has
produced a `<name>-digest-latest.md`, its title line is quoted as such and
attributed; where it has not, the page stays silent rather than inventing a
plain-language gloss.

The runner regenerates the page after every study run, so it is only ever as
stale as the last thing you ran.
"""
