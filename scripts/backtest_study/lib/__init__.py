"""Shared research substrate — everything the studies LEAN on, and nothing that
argues.

This is the same split `scripts/journal/lib/` makes: a step (there) or a study
(here) is a thing with an OUTCOME; a lib module is a thing other modules import.
The rule is mechanical and checked by the test suite — a module in `lib/` has no
entry in `scripts/study_map/catalog.py::STUDIES` and therefore no verdict; a
module in a family folder MUST have one. So "does this file argue anything?"
is answered by which directory it is in, not by reading it.

    harness.py             FROZEN exit-replay engine — Trade / replay / _pct.
                           DO NOT EDIT: every recorded tuning conclusion was
                           produced by exactly this logic, and a behavioural
                           change would invalidate the log SILENTLY. Changing
                           the exit mechanism means COPYING this file.
    book.py                the pooled real + proxy loader (bs_options_hist rows
                           excluded by default — they are priced FROM the model
                           that scores them). Runnable for its `--validate`
                           diagnostics table, the standard study pre-flight.
    protocol.py            the four defences every conclusion rests on: date
                           clustering, purging + a 120-day embargo, same-dates
                           comparison, window-dominance re-cuts.
    underlying.py          daily stock bars — real OHLC, falling back to
                           close-only Price~.
    underlying_features.py as-of-entry price-STATE columns (rv20, Parkinson,
                           semivar, ATR%, efficiency ratio, VRP, beta).
    volume_features.py     as-of-entry VOLUME columns (unusual-O/S, relative-
                           volume z, Amihud).
    live_select.py         the `account_sim --live-select` arm: research tier
                           importing PRODUCTION, the one sanctioned direction.
                           Carries no verdict — it is not a study.

`book.py` is the only one of these the runner will run (`run book`); the rest are
import-only. See `scripts/backtest_study/run.py::RUNNABLE_LIB`.
"""
