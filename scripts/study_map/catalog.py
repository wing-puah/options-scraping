"""The hand-written half of the map: what each study asks, and what it concluded.

This is the ONE file to edit when a study's verdict changes. Everything else in
the package is machinery that reads reports off disk. Keep entries in sync with
the prose companion, `research/study-map.md` — the tests assert
that every study module has an entry here and that every entry is named there,
so a new study file under `scripts/backtest_study/` fails the suite until it is
described.

`state` is the outcome of the argument, not of the last run:

    shipped    something in config/ changed because of this study
    null       ran, answered, and the answer was "no" — nothing shipped
    open       not refuted, blocked on data (usually new signal dates)
    reference  produces a baseline or a guard rather than a verdict

`retired` is an orthogonal axis: whether the study can be RUN at all, not what
it argued. `state` still records the outcome that was reached while its inputs
existed — retiring a study does not erase its verdict. A retired study is
`None` (the default, meaning "runnable") or a one-line reason-plus-date string
explaining why its inputs are gone and where its recorded verdict lives.
`scripts.backtest_study.run`'s `run --all` reads this to exclude retired
studies from the bulk run (they stay runnable by explicit name, with a printed
notice) — see the "Retired studies" note in that module's docstring.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── families ──────────────────────────────────────────────────────────────────
# Ordered. The numbering is real: it is the order a play moves through the
# system — pick it, manage it, wrap it, fund it.
FAMILIES: dict[str, dict[str, str]] = {
    "selection": {
        "index": "①",
        "title": "Selection",
        "question": "which plays are worth taking?",
        "note": "Mostly null. 0 of 496 bear subsets, 0 of 15 ML cells. "
                "Selection is not tunable from the columns we have.",
    },
    "management": {
        "index": "②",
        "title": "Management",
        "question": "when do I get out?",
        "note": "Where the edge actually is. Both shipped exit rules came from here.",
    },
    "structure": {
        "index": "③",
        "title": "Structure",
        "question": "am I expressing the signal in the wrong wrapper?",
        "note": "One +0.085 effect that does not hold out of sample, and one "
                "survivor that is power-stopped rather than refuted.",
    },
    "deployment": {
        "index": "④",
        "title": "Deployment",
        "question": "can I actually run this?",
        "note": "Feasibility, not edge. Delta-notional binds before cash does.",
    },
}

STATES: dict[str, str] = {
    "shipped": "shipped",
    "null": "null result",
    "open": "open · blocked on data",
    "reference": "reference",
}


@dataclass(frozen=True)
class Study:
    family: str
    state: str
    question: str
    verdict: str
    retired: str | None = None


# ── the twenty studies ────────────────────────────────────────────────────────
STUDIES: dict[str, Study] = {
    # ① selection
    "regime_gap_reread": Study(
        family="selection", state="reference",
        question="Numbers only, no interpretation: build the pooled book and print the report.",
        verdict="The baseline snapshot other studies import verbatim. It argues nothing "
                "on purpose — it exists so two studies can agree on what the book is.",
    ),
    "mech_regime_recut": Study(
        family="selection", state="shipped",
        question="Does a deterministic regime label — a pure function of SPY/VIX history at "
                 "the signal date — beat the model's free-text regime?",
        verdict="Overlay adopted. `mech_cell` is a column now, and it is what keys the "
                "shipped BEAR_HE exit override.",
    ),
    "bear_position_study": Study(
        family="selection", state="null",
        question="Pre-registered cuts on bear_put: is it a SELECTION problem (E<0) or an "
                 "EXIT problem (E>0 with R<0)?",
        verdict="DEMOTE criteria all fire at n=164. Implementation left to the operator; "
                "the finding is that the structure does not earn its emission share.",
    ),
    "bear_arm": Study(
        family="selection", state="shipped",
        question="B1 — is there any bear subset, definable at decision time, that is not "
                 "negative? B2 — or is the exit simply mis-tuned?",
        verdict="B1 NO: 0 of 496 subsets pass. B2 YES: `be_after: 0.50` keyed to bear debit "
                "clears every pre-registered criterion and shipped.",
    ),
    "ml_combination": Study(
        family="selection", state="null",
        question="Does any learned combination of structure × regime × geometry × enrichment "
                 "beat the score-free ladder out of sample?",
        verdict="NULL — 0 of 15 model × strategy cells. Re-open on new COLUMNS only, never "
                "on new models; the ladder is at the ceiling of this feature set.",
    ),
    "v4_bridge": Study(
        family="selection", state="open",
        question="v4 dropped two prompt factors. Does the v3-derived ladder still apply to "
                 "what v4 actually emits?",
        verdict="Written before the data existed. It refuses to compare a book against "
                "itself, so it aborts until a real v4 export lands.",
    ),
    "macro_event_study": Study(
        family="selection", state="open",
        question="Do scheduled macro events — FOMC decisions, minutes, CPI, NFP, PCE — show "
                 "up in the book: in entry IV (vrp), in outcomes (R/E), or in exits?",
        verdict="Registered 2026-08-19, not yet run. G0 prints the power census first; on "
                "the scoping counts the tight FOMC cells are expected to power-stop, and "
                "the readable answer to \"does IV run up / crush\" is the ~800-session "
                "VIX arm, which is context, never a verdict.",
    ),

    # ② management
    "exit_mechanism_study": Study(
        family="management", state="shipped",
        question="The original grid: replay stored daily marks under alternative exit rules, "
                 "real-priced rows only.",
        verdict="SHIPPED the production debit profile — profit target 0.90, stop 0.75, time "
                "exit at 0.75 of DTE, no trailing stop (Attempt 10).",
    ),
    "combined_exit_study": Study(
        family="management", state="reference",
        question="The same grid on a bigger tuning set — real rows and real-priced proxy "
                 "rows pooled.",
        verdict="Confirms production is the best GLOBAL config, and in doing so shows exits "
                "are regime-conditional. That is what motivated the two switch studies.",
        retired="RETIRED 2026-08-14 — its inputs (backtests/results_proxy.csv, an author "
                "transposition that never matched config/backtest.yml's actual "
                "proxy_results.csv name) are gitignored scratch, deleted long ago and "
                "unrecoverable. Verdict already recorded (Attempts 8, 9, 12) in "
                "research/archive/02-credit-debit-split-attempts-8-12.md; "
                "not repointed at a surviving file — see next-steps.md §0c(B) for why.",
    ),
    "underlying_exit_study": Study(
        family="management", state="null",
        question="Credit spreads: stop on the UNDERLYING breaching a level, instead of on "
                 "the option mark?",
        verdict="Nothing shipped (Attempt 9).",
        retired="RETIRED 2026-08-14 — its second input "
                "(backtests/v2_BacktestResults_nocreditdiff.csv) is gitignored scratch, "
                "deleted long ago and unrecoverable (the genuine rename, "
                "v2_results_nocreditdiff.csv, survives but has 0 credit rows today, so "
                "repointing would only emit a degenerate empty report). Verdict already "
                "recorded (Attempt 9) in "
                "research/archive/02-credit-debit-split-attempts-8-12.md — "
                "see next-steps.md §0c(B) for why it is not repointed.",
    ),
    "exit_switch_mech_study": Study(
        family="management", state="shipped",
        question="A per-regime exit switch keyed on the mechanical regime — is it stable "
                 "where the model-keyed version failed leave-one-out?",
        verdict="BEAR_HE cell SHIPPED (trail 0.50 at trigger 0.50). The L-VOL and RANGE/BULL "
                "cells stay gated and commented out in config/backtest.yml.",
    ),
    "exit_switch_structure_study": Study(
        family="management", state="reference",
        question="Q1 — does a bear_put-keyed trail pass the same ship gate? Q2 — is BEAR_HE "
                 "secretly just a composition proxy for that structure effect?",
        verdict="The guard on the shipped rule. It exists to catch the composition trap that "
                "killed oi_confirm_pct and iv_pct.",
    ),
    "bear_giveback": Study(
        family="management", state="null",
        question="82% of bear rows go green and then give it back. Can a breakeven ratchet "
                 "capture that, and does the underlying path explain it?",
        verdict="The `be_after` grid does NOT ship beyond what is already live. The give-back "
                "pattern lives in the UNDERLYING, not in the mark.",
    ),
    "volume_signal": Study(
        family="management", state="null",
        question="Share volume is the one column on disk no study has read. Does an "
                 "unusual-O/S ratio (flow contracts / share volume) condition exits — "
                 "or anything — or is it just liquidity in a costume?",
        verdict="NULL — no R separation on non-bear debit and the one frozen exit "
                "variant is negative out-of-fold (LOO share 1%). The column is closed; "
                "the live pipeline never pays the version bump. Bear's monotone "
                "os_ratio read is a post-hoc carry-forward, not a candidate.",
    ),
    "next_day_move": Study(
        family="management", state="null",
        question="Move the give-back question to day 0, where it is knowable at the close: "
                 "cut positions the stock did not confirm?",
        verdict="ARM C does not clear the confound, so no rule. The sensitivity is structural, "
                "not a tradeable signal.",
    ),

    # ③ structure
    "bear_rewrap": Study(
        family="structure", state="null",
        question="A bear SPREAD sells the lower put, giving away the vol expansion that makes "
                 "a bear position pay. What if the short leg goes?",
        verdict="The wrapper is worth +0.085 and it does NOT hold in 2026. Nothing ships; "
                "re-runnable as dates land.",
    ),
    "vol_sleeve": Study(
        family="structure", state="null",
        question="Synthesize straddle / strangle / calendar on the dates the engine already "
                 "signalled. Is there a vol sleeve in here?",
        verdict="CLOSED. The straddle clears its gate then dies ex-window, and its correlation "
                "with the deployed book is the WRONG SIGN — it re-wraps the same exposure. "
                "Only the calendar survives.",
    ),
    "calendar_hedge": Study(
        family="structure", state="open",
        question="Re-derive that one survivor under a pre-registered pick rule and a strict "
                 "fill rule.",
        verdict="Gates pass — R4 now compares two same-run builds instead of a 2026-08-12 "
                "checksum, so cache growth can no longer fail it. On v4 H0 FILL is NOT MET "
                "(12/31 deployed dates, 1/3 worst-decile) and H2 stays NOT EVALUABLE. "
                "Blocked on dates, not refuted.",
    ),

    # ④ deployment
    "bear_deploy": Study(
        family="deployment", state="shipped",
        question="Bear selection is unfixable — but is bear worth holding as a HEDGE? Four "
                 "estimands: D1 joint selection×exit, D2 hedge contribution, D3 sizing, "
                 "D4 conditional pick.",
        verdict="D2 MET — bear pays on the deployed book's worst dates, correlation −0.13. "
                "D4 ADOPTED — pick bear by |delta| DESCENDING. D1 and D3 not met. Bear is a "
                "hedge, not a selection.",
    ),
    "account_sim": Study(
        family="deployment", state="open",
        question="The ladder assumes infinite capital. Does a real $25,000 account — paying "
                 "for positions, holding reserve, respecting a delta cap — still produce a book?",
        verdict="The caps survive; the WINDOW does not. Delta-notional binds before cash does. "
                "Feasibility only — nothing ships from this study under any outcome. The run "
                "also prints a POST-HOC compounding arm (account_sim-compounding-latest.txt, "
                "its own page): on this book compounding COSTS money and the verdict is "
                "unmoved; A2/A5 do not transfer to it.",
    ),
    "selection_order": Study(
        family="deployment", state="open",
        question="account_sim's rejected picks outperformed its taken ones. Does a different "
                 "BLIND entry-side ORDER of the same candidate set spend the scarce delta "
                 "budget better — or was that read an artifact?",
        verdict="POWER-STOPPED at G0, on the pre-registered threshold. Each of the four "
                "re-orderings changes only 7-14% of the deployed book, so the best-powered "
                "arm reaches 11 affected dates (PRIMARY) against a floor of 25 declared "
                "before the count was knowable. Census only: no arm confirmed, none refuted, "
                "no O4 band drawn, and NO re-run on these dates.",
    ),
}

# ── infrastructure ────────────────────────────────────────────────────────────
# Mirrors run.INFRA plus lib/book.py, which the runner lists as a study for its
# --validate diagnostics but which carries no verdict of its own.
INFRA: dict[str, str] = {
    "run.py": "The runner. Writes backtests/study_output/<name>-latest.txt with a "
              "provenance header — git sha, dirty flag, exact argv, era, input row counts "
              "and mtimes — so no write-up can attribute numbers to the wrong export. A "
              "genuine failure DELETES -latest.txt rather than leaving a stale one.",
    "lib/era.py": "Which prompt-version ERA an export belongs to, and where that era's "
              "files live. The bare filename does not name a fixed population — a vN_ "
              "rename makes it mean whatever the live tab holds now, which on 2026-08-15 "
              "turned four months of v3 evidence into 14 dates of v4 with no code change. "
              "Detects the era (populated score_flow = v3), refuses a run whose exports "
              "are not the era asked for or disagree with each other, and refuses an era "
              "too thin to conclude from.",
    "lib/harness.py": "FROZEN. Trade / replay. It prices nothing; it replays a stored mark "
                  "series. Every recorded conclusion depends on its exact exit priority, "
                  "clamps and rounding, and a behavioural change would invalidate the log "
                  "SILENTLY. Changing the exit mechanism means copying this file.",
    "lib/book.py": "The pooled real + proxy loader. bs_options_hist rows are excluded by "
                   "default — they are priced FROM the model that scores them.",
    "lib/live_select.py": "The `account_sim --live-select` arm: research tier importing "
                      "PRODUCTION, so the simulated decision is the live decision. Runs "
                      "scripts/journal/recommend.py's rank() + judge() over history in "
                      "place of lib/book.py's port of the ladder, and reports selection "
                      "coverage, ladder divergence, and the judge layer's bounded effect. "
                      "Carries no verdict — it is not a study.",
    "lib/protocol.py": "The four defences every conclusion rests on: date clustering, purging "
                   "plus a 120-day embargo, same-dates comparison, and window-dominance "
                   "re-cuts.",
    "lib/underlying.py": "Daily stock bars — real OHLC, falling back to close-only Price~. The "
                         "widening that lib/harness.py is deliberately frozen out of.",
    "lib/underlying_features.py": "As-of-entry price-STATE columns: rv20, Parkinson, semivar, "
                                  "ATR%, efficiency ratio, VRP, beta. This family is the ML "
                                  "re-open condition — none of it existed when B1 searched "
                                  "496 subsets.",
    "lib/volume_features.py": "As-of-entry VOLUME columns: unusual-O/S (flow contracts / "
                          "share volume), relative-volume z, Amihud. Split-guarded, "
                          "rescaled tickers withheld from the window features. Built for "
                          "volume_signal (NULL) and kept for future pre-registered use.",
    "lib/macro_calendar.py": "Scheduled US macro events (FOMC decisions, minutes, CPI, NFP, "
                         "PCE) as as-of features, read from the hand-authored "
                         "config/macro-events.yml. next_event is strictly-after and "
                         "refuses to answer past each type's verified_through; "
                         "unscheduled events are excluded from forward-looking reads "
                         "only. Event distance keys off the ENTRY session, with "
                         "pre-open vs post-open deciding day-0. Built for "
                         "macro_event_study.",
}

# ── the traps, kept where the map is read ─────────────────────────────────────
TRAPS: list[tuple[str, str]] = [
    ("Composition, not signal",
     "A cut looks predictive because it changed the MIX of structures, not because the "
     "variable matters. Killed oi_confirm_pct, iv_pct, and the score_total bands."),
    ("Grading against a baseline production does not run",
     "Changed a decision twice. Always compare against the SHIPPED merge, never against a "
     "clean default."),
    ("One window carrying an effect",
     "Every headline is re-cut ex-Mar–Apr-2025 and ex-Feb–Apr-2026."),
    ("Row count is not sample size",
     "Rows inside a signal date share the tape. n is the ~118 dates, not the ~1,100 rows."),
]

# ── how to read a report ──────────────────────────────────────────────────────
READING: list[tuple[str, str]] = [
    ("Check the header",
     "Row counts and mtimes of the input exports. Two runs on different exports are not "
     "comparable — that has caused a wrong attribution before."),
    ("Check the calibration gate",
     "Most studies open by proving production rules reproduce the stored exit_reason / "
     "days_held / realized_pnl_pct. A non-zero exit here is the gate WORKING — do not "
     "route around it."),
    ("Check the pre-registration",
     "Nearly every study names a current.md section written BEFORE it ran. A number not "
     "covered by a pre-registered criterion is an observation, not a result."),
    ("Know which metric you are reading",
     "E is P&L at the path cap — selection only. R is realized under the exit rules — "
     "selection plus exit. E<0 means no exit rule can rescue it. Definitions live in "
     "glossary.md."),
]


def state_of(name: str) -> str:
    """`shipped` / `null` / `open` / `reference` for a study, or `unknown`."""
    study = STUDIES.get(name)
    return study.state if study else "unknown"


def retired_studies() -> dict[str, str]:
    """`{name: reason}` for every study marked retired. Empty for a study with
    no catalog entry — `run --all` falls back to treating it as runnable
    rather than silently dropping an undescribed study file."""
    return {n: s.retired for n, s in STUDIES.items() if s.retired}


def by_family() -> dict[str, list[tuple[str, Study]]]:
    """`{family_key: [(name, Study), ...]}` in FAMILIES order, then catalog order."""
    return {
        key: [(n, s) for n, s in STUDIES.items() if s.family == key]
        for key in FAMILIES
    }


def scoreboard() -> dict[str, int]:
    """`{state: count}` over every study, in STATES order."""
    return {
        state: sum(1 for s in STUDIES.values() if s.state == state)
        for state in STATES
    }
