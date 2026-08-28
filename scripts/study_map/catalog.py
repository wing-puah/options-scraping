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
        "note": "Mostly null. 0 of 496 bear subsets, 0 of 15 ML cells. Selection is "
                "not tunable from the columns we have — the one live candidate "
                "(emission_timing's stale-entry penalty) is about WHEN, not which.",
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
        "note": "Two unconfirmed candidates and no ship. The v4 refresh promoted a "
                "bear diagonal and demoted the financed diagonal to underpowered.",
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
    # Hand-written operator-attention flag, like `verdict`: one line saying why
    # the OPERATOR should personally read this study's review artifacts NOW
    # (a card line changed, a candidate was retracted, a decision is pending).
    # Set it during the recording pass that created the need; clear it back to
    # None once the operator has read/decided. The map's "Reading queue"
    # renders every flagged study under "read first"; unflagged studies whose
    # digest exists on disk render as "good to know" with dates only. The flag
    # is a POINTER to artifacts, never a conclusion of its own.
    attention: str | None = None


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
        verdict="`VERDICT: DEMOTE TO VETO` — re-confirmed on the refreshed v4 export "
                "(2026-08-24). All three criteria fire on the ex-window bear_put population, "
                "now n=177: `[PASS]  ex-window mean E < 0            (-0.288)`, "
                "`[PASS]  bootstrap 95% CI upper < 0      ([-0.473, -0.076])`, "
                "`[PASS]  both time halves negative       (early -0.495, late -0.033)`, and "
                "`CONSTRAIN candidates (n>=30, both halves positive, EX-W): NONE`. Slightly "
                "more negative than the 2026-08-22 read (-0.269). Implementation left to the "
                "operator; the finding is that the structure does not earn its emission share.",
    ),
    "bear_arm": Study(
        family="selection", state="shipped",
        question="B1 — is there any bear subset, definable at decision time, that is not "
                 "negative? B2 — or is the exit simply mis-tuned?",
        verdict="B1 NO: `combinations evaluated: 496  (with n>=40: 132)` / "
                "`survivors of the full pre-registered rule: 0` — unchanged on v4. B2 shipped "
                "`be_after: 0.50` keyed to bear debit in 2026-08-11, and on 2026-08-24 its "
                "own pre-registered ROLLBACK TRIGGER reached the floor and FIRED: "
                "`CENSUS [bear-debit be_after 0.50 (arming rows)]: n_rows=92  n_dates=53  "
                "floor=60 rows  -> FLOOR MET`, then `(c) per-year mean-R delta, ALL "
                "bear-debit rows: 2024:+0.0217  2025:-0.0335   [FIRE] revert if any year < 0` "
                "against passes on (a) `$+58.00` and (b) `+0.0071`. One of three conditions "
                "is enough — `structure_exit.enabled` REVERTED to false (commit 1e36dba). "
                "B2's own grid stays null besides: `best non-PROD variant: BE ratchet @.20  "
                "Δ=+0.043 CI[-0.021, +0.106] LOO min gain +0.036` / `pre-registered EXIT FIX "
                "criteria (CI excludes zero AND every LOO fold positive): NOT met`.",
    ),
    "ml_combination": Study(
        family="selection", state="null",
        question="Does any learned combination of structure × regime × geometry × enrichment "
                 "beat the score-free ladder out of sample?",
        verdict="NULL — 0 of 15 model × strategy cells. `VERDICT: NULL RESULT — the ladder "
                "is at/near the ceiling of this data`. On the refreshed v4 export the gap "
                "WIDENED against the models rather than closing: `M3 out-of-fold paired R "
                "gain vs B0: -0.103 CI95 [-0.239, +0.023]  -> CI excludes zero: False` "
                "(2026-08-22 read -0.012), and every other construct is negative too — "
                "`B1  gain -0.045`, `B2  gain -0.097`, `M1  gain -0.078`, `M2  gain -0.004`. "
                "Re-open on new COLUMNS only, never on new models; the ladder is at the "
                "ceiling of this feature set.",
    ),
    "v4_bridge": Study(
        family="selection", state="open",
        question="v4 dropped two prompt factors. Does the v3-derived ladder still apply to "
                 "what v4 actually emits?",
        verdict="It no longer aborts — a real v4 export landed, and the answer is "
                "`VERDICT: LADDER UNVALIDATED ON v4`, standing since 2026-08-22 and "
                "re-confirmed 2026-08-24 on `1465 plays / 142 dates` of v3 against "
                "`1050 plays / 96 dates` of v4. Four of the five pre-registered tests shift: "
                "`Shifted: 1. structure mix, 3. plays per day, 4. bear share, 5. ladder tier "
                "mix`; only credit share holds (`two-proportion z = -1.43, p = 0.1521   "
                "within noise`). Bear share standardised 36.0% -> 34.8% but raw 44.4% -> "
                "34.8%, and VETO collapses `149 (10.2%)` -> `14 ( 1.3%)`. Per the "
                "pre-registration: keep deploying under the v3 rules and do NOT re-derive "
                "the ladder on v4 rows yet.",
    ),
    "macro_event_study": Study(
        family="selection", state="open",
        question="Do scheduled macro events — FOMC decisions, minutes, CPI, NFP, PCE — show "
                 "up in the book: in entry IV (vrp), in outcomes (R/E), or in exits?",
        verdict="First run (era v3, 795/118): the side-split census leaves ONE powered "
                "cell — NFP AFTER w<=5 — and it is null on vrp (+0.022, CI spans 0) and "
                "R (-0.144, CI spans 0); every FOMC/minutes/CPI/PCE cell is underpowered. "
                "Context arms: NFP shows VIX build-then-bleed with post-print SPY relief; "
                "FOMC shows nothing (no pre-FOMC drift at n=26). ARM X's raw trigger fired "
                "and DIED under the amendment-2 survival control (in holds >=20 sessions "
                "the LATE bucket is empty; within fixed length EARLY wins) -> "
                "macro_event_exit DE-QUEUED as SURVIVAL-ARTIFACT. Nothing ships; no v5 "
                "bump; passive re-run when the book grows. Re-run on v4 (2026-08-24, 567 "
                "rows / 87 dates) reaches the same place from a different book: every event "
                "type still prints `ARM VERDICT INPUT: UNDERPOWERED — no cell cleared the "
                "floor.`, the tercile trigger is `not fired`, and the survival control "
                "holds — `X-C1 verdict (86 affected dates vs floor 25): SURVIVAL-ARTIFACT — "
                "macro_event_exit DE-QUEUED; re-arms only on a future CONTROLLED trigger`. "
                "The exit census is the one thing that grew: `hold spans >=1 macro event: "
                "501 rows / 87 dates  mean R +0.093  mean days_held 34.0` against "
                "`hold spans none: 66 rows / 44 dates  mean R +0.250  mean days_held 3.2` — "
                "a survival read, not an event effect.",
    ),

    "emission_timing": Study(
        family="selection", state="open",
        attention="2026-08-24 review RETRACTED the ARM P stale-entry candidate as "
                  "off-basis — the digest + validator memo carry the why, and the same "
                  "pass queued a wrong-PRIMARY warning that touches every v3-registered "
                  "study graded on a v4 run.",
        question="Does entry TIMING carry risk the columns never saw: the same (ticker, "
                 "structure) re-emitted across consecutive analysis dates (am I late?), and "
                 "a fill delayed 1-3 sessions past the signal (does the edge decay?)?",
        verdict="ARM P's v4 read is OFF-BASIS and carries nothing (two-analyst review, "
                "2026-08-24): the registration pins PRIMARY to `--era v3` (795 rows / 118 "
                "dates) and declares v4 SECONDARY — and the 08-19 watch said re-test on NEW "
                "dates only. The v4 re-run (`n=73 pairs / 73 dates   mean delta -0.2050   "
                "CI[-0.3792,-0.0306] EXCLUDES 0  ** CANDIDATE`) is therefore recorded as an "
                "off-basis OBSERVATION — a sign flip against the v3 null (+0.054, CI "
                "spanning zero) on overlapping dates, which if anything argues the effect "
                "is era-composition, not timing. Both analysts also flagged that the "
                "report's `ex_2026_feb_apr` cut is a silent no-op (this book ends "
                "2025-08-19). No intake rule is proposed; the v3 verdict stands. ARM L is "
                "unmoved and remains the publishable finding: `ARM L: LAG-TOLERANT` — "
                "L=1/2/3 all include zero against L=0, though the review noted the "
                "report's own two tercile L=3 cells print `** CANDIDATE` against that "
                "headline (internal contradiction, same off-basis caveat).",
    ),

    # ② management
    "exit_mechanism_study": Study(
        family="management", state="shipped",
        question="The original grid: replay stored daily marks under alternative exit rules, "
                 "real-priced rows only.",
        verdict="SHIPPED the production debit profile — profit target 0.90, stop 0.75, time "
                "exit at 0.75 of DTE, no trailing stop (Attempt 10). CALIBRATION REPAIRED "
                "2026-08-24: it classifies via lib/replay_basis.py instead of printing a "
                "false failure on rows stored under a shipped override — debit now reads "
                "`191 exact, 0 near-rounding-tie, 16 superseded-basis, 0 HARD of 207` (all "
                "16 are be_stop/trailing_stop bear_put rows). A `--side credit` ARM runs in "
                "`--all` on its own stem (exit_mechanism_study-credit-latest.txt) against "
                "the SHIPPED profile (sl=None), not the stale pre-Attempt-13 sl=1.00: "
                "`73 exact, 0 near-rounding-tie, 0 superseded-basis, 0 HARD of 73`, and "
                "Attempt 13 re-confirms hard — `PROD pt.65 sl none  total=$    +2593` vs "
                "`sl 1x (pre-Attempt-13)  total=$     -876  $/ct=   -2067  win= 50/73  "
                "med=$  +153  Δ=$   -3468  Δ-LOO=$   -3853`. "
                "Its Attempt-13 rollback trigger is a census only: `fresh bull_put rows "
                "(signal_date > 2026-07-13): 0` -> UNDERPOWERED, thread parked. On the thin "
                "v4 debit book PROD itself is `total=$     -959` and no REACTIVE variant "
                "beats it out of fold — the trailing grid is negative everywhere "
                "(`trail .25 trig .50` at `Δ=$   -4152  Δ-LOO=$   -6332`), and the two variants with a "
                "positive Δ-LOO are both target/ratchet, not reactive: `pt .75 no trail` at `"
                "Δ=$   +4354  Δ-LOO=$   +1734` and `BE ratchet @.75, no trail` at `Δ=$   "
                "+1950  Δ-LOO=$    +806`. In-sample on 207 rows, selected on the same file "
                "they are scored on — an observation, not a candidate.",
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
        verdict="BEAR_HE cell SHIPPED (trail 0.50 at trigger 0.50). The ORIGINAL whole-book "
                "gate still fails on one of six and so `VERDICT: mech-keyed per-regime exit "
                "switch STAYS GATED.` — `[FAIL]  LOO median > 0 (pooled)` against passes on "
                "nonneg 82.76%, total +5.6986, both halves (+3.9892 / +2.4829), post-13c, "
                "and `SIGN FLIPS vs frozen: NONE`. What is new on 2026-08-24 is STEP 3(f), "
                "the pre-registered rollback-trigger power census, and the corrected "
                "gate evaluated only at the floor. BEAR_HE has no reading: "
                "`CENSUS [BEAR_HE trail .50/.50]: n_rows=1  n_dates=1  floor=25 dates  -> "
                "UNDERPOWERED`. LVOL does, and it passes all four: `CENSUS [LVOL tef null]: "
                "n_rows=40  n_dates=31  floor=25 dates  -> FLOOR MET` / `per-affected-date "
                "summed pnl_pct delta (variant - PROD): median=+0.0230  total=+5.6986  "
                "(n=31 affected dates)` -> `VERDICT: LVOL (tef null) CLEARED.` The operator "
                "HELD the ship: v4 is new plays on the SAME historical signal dates the "
                "cell was gated on, so clearing here is a re-read of the fitting window, "
                "not a fresh confirmation. LVOL and RANGE/BULL stay commented out in "
                "config/backtest.yml pending genuinely new dates.",
    ),
    "exit_switch_structure_study": Study(
        family="management", state="reference",
        question="Q1 — does a bear_put-keyed trail pass the same ship gate? Q2 — is BEAR_HE "
                 "secretly just a composition proxy for that structure effect?",
        verdict="The guard on the shipped rule. It exists to catch the composition trap that "
                "killed oi_confirm_pct and iv_pct, and on v4 (2026-08-24, n=415 debit / 87 "
                "dates) it still holds the line both ways. Q1: `VERDICT: structure-keyed "
                "bear_put trail STAYS GATED.` on five of six — `structure-keyed [pnl_pct] "
                "dates=  87  median=  +0.0000  total=    -5.2794  >0= 0.00%` against the "
                "mech comparator's `total=    +5.6986  >0=18.39%`, plus a failed time-half "
                "split (early +2.8541, late -3.7462). Q2: the shipped key is NOT a "
                "composition proxy — `shipped BEAR_HE clause  Δ=+0.7735   on its complement "
                "(non-bear_put) Δ=+0.0000   retained 0%` vs `structure bear_put trail "
                "Δ=-0.8920   on its complement (outside BEAR_HE) Δ=-1.6656   retained 187%`. "
                "The structure key keeps its (negative) effect off BEAR_HE; the mech key's "
                "gain lives entirely inside its own cell.",
    ),
    "bear_giveback": Study(
        family="management", state="null",
        question="82% of bear rows go green and then give it back. Can a breakeven ratchet "
                 "capture that, and does the underlying path explain it?",
        verdict="The `be_after` grid does NOT ship, and as of 2026-08-24 there is nothing "
                "live for it to add to: bear_arm's rollback trigger fired and "
                "`structure_exit.enabled` went back to false, so the SHIPPED baseline this "
                "study grades against is on its way out. Nothing in the grid clears the "
                "report's own `**` bar against it either. The give-back pattern lives in the "
                "UNDERLYING, not in the mark, and the days-to-peak gradient is where to see "
                "it: `peak within 3d               n=  18  give-back  89%  meanR -0.374` "
                "against `peak >20d                    n=  83  give-back  51%  meanR "
                "+0.203`.",
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
                "not a tradeable signal. Read the two arms together on v4 (2026-08-24): "
                "whole-book, every day-0 cut LOSES to SHIPPED (`cut when wrong sign  "
                "+0.010   -0.101        [-0.159, -0.041]`); BEAR-KEYED, all three cuts carry "
                "`**` and clear criteria 3-6 as well (`cut when wrong sign  -0.047   +0.134  "
                "[+0.045, +0.228]   +0.120`, both years and both pricing tiers positive, "
                "leak guard `non-bear changed    0`). That is not a new exit knob — it is "
                "bear_position_study's standing DEMOTE TO VETO arriving through a second "
                "door: the cut only pays where it removes bear rows, and inside ARM C's "
                "day-0-P&L bands the ordering flattens or reverses (`day-0 P&L -25% to 0         221            "
                "+0.034        +0.050    -0.016`, `day-0 P&L 0 to +25%         177  "
                "          +0.070        +0.218    -0.148`).",
    ),

    "staged_exit": Study(
        family="management", state="open",
        question="Does a time-STAGED exit — evaluate ONCE at fixed session X on P&L vs the "
                 "original entry, then exit / tighten / arm a trail — work where the "
                 "reactive drawdown-from-peak rules of Attempts 1/2/10 did not?",
        verdict="NULL both arms of the grid, on era v3 (2026-08-19, 795/118) and again on v4 "
                "(2026-08-24, 567 rows / 87 dates). The v4 run is if anything thinner: "
                "`24 of 96 cells clear the floor; 72 are UNDERPOWERED.` — `tally: "
                "{'UNDERPOWERED': 72, '-': 24}` — and not one powered cell reaches "
                "CANDIDATE, REACTIVE-AGAIN or NULL; every one is a bare `-`. The guards "
                "hold (`G1: PASS — 0 rows changed outside the population, in every cell.`, "
                "`G-FORK: PASS — 0 disagreements.`), so this is a power result, not a "
                "plumbing one. The Attempt-1/2/10 null extends to staged switches; thread "
                "closed on these dates.",
    ),

    # ③ structure
    "bear_rewrap": Study(
        family="structure", state="null",
        question="A bear SPREAD sells the lower put, giving away the vol expansion that makes "
                 "a bear position pay. What if the short leg goes?",
        verdict="The original read — the wrapper is worth +0.085 and does NOT hold in 2026 — "
                "is now the smaller half of the story. On v4 (2026-08-24, 196 bear debit "
                "rows) the two naive re-wraps stay dead (`long_put` at `[FAIL] CI excludes zero          dR -0.044 CI "
                "[-0.156, "
                "+0.058]`, `wider` at `[FAIL] CI excludes zero          dR "
                "-0.030 CI [-0.147, +0.078]`, five [FAIL]s each), "
                "but the DIAGONAL passes everything: `[PASS] CI excludes zero          dR "
                "+0.353 CI [+0.121, +0.613]`, `MIN +0.275 over 61 folds (share+ 100%)`, both "
                "ex-window cuts, both years, both pricing tiers — and it is the only cut "
                "whose portfolio checks both land: `P1 worst-decile: n= 10  meanR +0.902  "
                "CI [+0.275, +1.498]  $+12,004   -> MET` with `P2 correlation with deployed "
                "sleeve: -0.275 over 54 shared dates   -> MET`. It takes the bear sleeve from "
                "`meanR -0.168` to `meanR -0.003`. TWO caveats gate the celebration: n=96 "
                "rows / 61 folds sit on the same dates the book was fitted on, and — the "
                "sharper one — this book contains NO 2026 dates (ends 2025-08-19), so the "
                "\"both years\" and ex-2026-window criteria are vacuous, and 2026-alone is "
                "exactly the cut that killed long_put in the original run. A wrapper swap "
                "on a population bear_position_study says to VETO — a candidate for an "
                "independent window that actually contains 2026, not a ship. Nothing "
                "changes in config/backtest.yml.",
    ),
    "vol_sleeve": Study(
        family="structure", state="null",
        question="Synthesize straddle / strangle / calendar on the dates the engine already "
                 "signalled. Is there a vol sleeve in here?",
        verdict="CLOSED. The straddle clears its gate then dies ex-window, and its correlation "
                "with the deployed book is the WRONG SIGN — it re-wraps the same exposure. "
                "Only the calendar survives. v4 (2026-08-24) says the same in the same "
                "shape: `Q1 NON-NULL cells: straddle/ALL, straddle/>90, calendar/ALL` but "
                "`Q2 IS NULL — the sleeve is neither reliably anti-correlated with the "
                "deployed book nor reliably positive on its worst dates.` The sign check is "
                "the whole argument — straddle `corr(daily mean R)   +0.312   CI95 [+0.091, "
                "+0.493]` and strangle `+0.320   CI95 [+0.093, +0.502]` against calendar "
                "`-0.344   CI95 [-0.545, -0.078]`, on straddle `meanR -0.066  $   "
                "-68,837` vs calendar `n=  50  win   56%  PF  1.33  meanR +0.461  "
                "$     6,292`. The "
                "calendar's worst-decile numbers are printed as POST-HOC, not as the gate, "
                "and go on to calendar_hedge.",
    ),
    "calendar_hedge": Study(
        family="structure", state="open",
        question="Re-derive that one survivor under a pre-registered pick rule and a strict "
                 "fill rule.",
        verdict="Gates pass — `R4 PASS — the two constructions agree row for row`; R4 now "
                "compares two same-run builds instead of a 2026-08-12 checksum, so cache "
                "growth can no longer fail it. On the refreshed v4 book (2026-08-24, 181 "
                "deployed positions over 77 dates) the fill rate is still the binding "
                "constraint: `P1 fillable on deployed dates          29 / 77   =  37.7%   "
                "FAIL` and `P1 fillable on worst-decile dates       2 / 7    =  28.6%   "
                "FAIL` -> `H0 FILL           NOT MET`, with `H2 = NOT EVALUABLE — the "
                "primary gate cannot be read on this window.` and H3 `NOT MET at any size` "
                "against the ladder+bear baseline. Blocked on dates, not refuted.",
    ),

    "financed_spread": Study(
        family="structure", state="open",
        question="Does financing a book debit vertical with a credit position pay — an "
                 "opposite-delta credit spread, a naked short leg, or a same-direction "
                 "credit vertical?",
        verdict="On era v3 (2026-08-19) same-expiry financing (F0-F3) came back all NULL, "
                "naked short significantly HARMFUL, and the post-scrape F4 diagonal held "
                "the study's one CANDIDATE — F4-d20 HOLD at dR +0.176 CI[+0.015,+0.354]. "
                "The refreshed v4 book (2026-08-24, 567 rows / 87 dates, `kept 387  (bull "
                "195 / bear 192)`) does NOT reproduce it and does not refute it either: "
                "`F1 off1          NULL` … `F3 off2          NULL`, `F4-d10 hold      "
                "NULL`, and the whole d20 family drops below the floor — `F4-d20 hold      "
                "UNDERPOWERED`, `n=20 rows / 19 dates — under the G0 floor, no criterion "
                "evaluated.` The candidate is therefore UNCONFIRMED on v4 rather than "
                "carried forward; the independent-window confirmation it was queued for "
                "has not yet been run on a book that can hold it. (`UNDERPOWERED` is what "
                "reports before 2026-08-22 called POWER-STOPPED — same token.)",
    ),

    # ④ deployment
    "bear_deploy": Study(
        family="deployment", state="shipped",
        attention="2026-08-24 grading PULLED the §4 closer-to-money pick line and "
                  "relabelled the hedge sleeve operator-policy — read the digest and "
                  "validator memo, and confirm the operator pre-commitment wording in "
                  "research/pre-registrations/f4_deployment/bear_deploy.md says what you meant.",
        question="Bear selection is unfixable — but is bear worth holding as a HEDGE? Four "
                 "estimands: D1 joint selection×exit, D2 hedge contribution, D3 sizing, "
                 "D4 conditional pick.",
        verdict="Bear is a hedge, not a selection — that half is unmoved (D1: `survivors of "
                "the pre-registered D1 rule: 0`). But the hedge case itself REVERSED on the "
                "refreshed v4 export (2026-08-24), and every estimand now reads NOT MET: "
                "`D2 hedge is real          : NOT MET`, `D3 always-on sizing       : NOT MET "
                "at any size`, `D4 conditional pick       : NOT MET`, `D5 gated sleeve "
                "(POST-HOC): no gate survives`. D2 fails on the year check alone — "
                "`bear R on deployed worst-decile dates: +0.033 (row-level CI "
                "[-0.375, +0.531], n=18) — needs > 0: YES` and "
                "`sleeve correlation -0.087 — needs < 0: YES` still pass, then "
                "`tail positive in 0/2 evaluable years — needs >= 2: NO`. D4 loses the "
                "shipped ranker outright — `|delta| high first             62   -0.119   "
                "-0.115   -0.004 [-0.166, +0.166]    -0.045`, i.e. the |delta|-DESCENDING "
                "pick is now indistinguishable from taking the day's average bear, and "
                "`rankers tested: 10  adopted: 0  (~0.5 expected by chance)`. That rule sits "
                "in docs/deployment-rules.md on v3 evidence; v4 does not carry it, and "
                "`none — the hedge cannot be timed by any gate tested, at either size.` "
                "Needs a replication pass before the rule is re-affirmed or pulled.",
    ),
    "account_sim": Study(
        family="deployment", state="open",
        question="The ladder assumes infinite capital. Does a real $25,000 account — paying "
                 "for positions, holding reserve, respecting a delta cap — still produce a book?",
        verdict="The caps survive; the WINDOW does not. Delta-notional binds before cash does. "
                "Feasibility only — nothing ships from this study under any outcome. "
                "`>>> FEASIBLE <<<` on A1-A6, unchanged since 2026-08-22. On v3 the cap "
                "ordering read adverse — rejected picks out-earning the ones taken; on the "
                "refreshed v4 era (2026-08-24: 567 rows / 87 dates, 181 deployed picks, "
                "`total: 2 episodes, 51 dates, 119 deployed picks` in the primary) this "
                "REVERSES and now does so in ALL EIGHT frozen/compounding x "
                "PRIMARY/SECONDARY cells — the n=9 compounding-SECONDARY holdout is gone. "
                "PRIMARY frozen prints `  taken                n=  78  meanR +0.355` against "
                "`  rejected [net_delta     ] n=  39  meanR +0.186  delta vs taken -0.170` "
                "and `  rejected [per_pos_delta ] n=  34  meanR +0.107  delta vs taken "
                "-0.248`; the compounding arm's per-position cell is the widest of the eight "
                "at `delta vs taken -0.413`. The POST-HOC compounding arm "
                "(account_sim-compounding-latest.txt, its own page) is also FEASIBLE and "
                "still costs money — `B2  compounded max-loss sizing (from $25,000), "
                "unconstrained  n= 119  dates= 51  $     9,464  meanR +0.235` against the "
                "frozen arm's `$     9,863  meanR +0.246` — and its A2/A5 stay ratios "
                "against a moving benchmark, which the report itself flags.",
    ),
    "selection_order": Study(
        family="deployment", state="open",
        question="On v3, account_sim's rejected picks out-earned its taken ones — a read that "
                 "REVERSES on v4 (see the account_sim entry), so the premise this study was "
                 "registered under no longer holds on the current era. The pre-registered "
                 "question stands on its own: does a different BLIND entry-side ORDER of the "
                 "same candidate set spend the scarce delta budget better — or was that read "
                 "an artifact?",
        verdict="UNDERPOWERED at G0, on the pre-registered threshold, on BOTH eras and on "
                "every refresh so far. On the 2026-08-24 v4 book: `arms powered (G0):  "
                "none`, `arms clearing all seven: none`, `Best-powered arm reached 20 "
                "affected dates against a threshold of 25.` — up from 17 on 2026-08-22 and "
                "still short of a floor declared before the count was knowable. Each "
                "re-ordering `changes only 18%-27% of O0's taken positions` (PRIMARY: O1 "
                "24%, O2 18%, O3 21%, O1b 27%; 12-22% SECONDARY, where O1b alone reaches "
                "`ok` at 26 dates), because on most contested dates the caps exclude the "
                "same picks whatever the order. Census only: no arm confirmed, none "
                "refuted, no O4 band drawn, and NO re-run on these dates. The earlier "
                "`7-14%` figure quoted here was a hardcoded prose literal in the study, "
                "corrected 2026-08-22 to print the run's own measured census.",
    ),

    "portfolio_delta": Study(
        family="deployment", state="open",
        question="Is there an optimal PORTFOLIO net delta to keep? account_sim showed "
                 "delta-notional binds before cash; this asks whether the level itself is "
                 "a lever — dose-response, a ceiling band, and a delta-TARGETED hedge "
                 "sleeve, against a seeded random-admission null band.",
        verdict="NOISE on the primary population — era v3 (2026-08-19) and again on v4 "
                "(2026-08-24, 567 rows / 87 dates, 181 deployed picks): `>>> NOISE — no arm "
                "exceeds ARM N's 95th percentile and ARM D's bands do not separate within "
                "their cells. Recorded; thread closed for these dates. <<<` "
                "LONG-ONLY-BY-CONSTRUCTION is the operating fact and got sharper, not "
                "softer: `census: long-only book: True   negative-delta picks 0 of 181   "
                "per-date net/equity range [+0.00, +2.50]` — not one short-delta pick in the "
                "whole book. Exactly one arm clears the moved-dates floor, and it fails five "
                "of the seven parts: `arms powered (G-INVENTORY): B ceiling 1.00` / "
                "`=> B ceiling 1.00: FAILS c1, c2, c4, c5, c7` on a paired mean gain of "
                "`+0.0071 R   CI95 [-0.2258, +0.2070]` sitting at `pct 94%` of the ARM N "
                "null band. Every H* delta-target hedge arm is UNDERPOWERED (9/14/15 moved "
                "dates against 25) and none is read. Net delta is not a free lever of this "
                "book; no band value read off P&L per the firewall.",
    ),

    "hedge_timing": Study(
        family="deployment", state="open",
        question="The bear hedge sleeve is deployed on discretionary triggers — chop, a SPY "
                 "gap-up, a 4-5-day SPY down-run. Does any of them, made mechanical, pick a "
                 "day on which the hedge earns more than the SAME day's ladder-eligible long?",
        verdict="RUN 2026-08-28 (era v4 sha 1fe4923; v3 replication beside it), graded. "
                "TIMING-CANDIDATE survivors: 0 of 9 (~0.45 expected by chance). GAP-UP is "
                "CONTRARY on both money arms — report: 'HEADLINE difference -0.408  CI95 "
                "[-0.749, -0.057]' (H3, every LOO fold, both years, all cuts) and 'best "
                "gated policy f=0.50  delta total $-5,893' with max DD/worst date identical "
                "to never hedging (H4) — so the drafted §4 prohibition ('do not open the "
                "hedge on a gap-up day') is HELD for the operator per the registration. "
                "CHOP: NULL/NULL/UNSTABLE. DECLINE-BROAD: NULL on all three arms, which the "
                "pre-registered asymmetric rule reads AGAINST the strict habit. The "
                "operator's own 4-5-day streak stays UNDERPOWERED as fixed in advance "
                "(2 book dates; ~3,000 more trading days to a floor). v3: H3-GAP "
                "underpowered by ONE date (24 vs 25), H4-GAP NULL but directionally "
                "consistent incl. 2026 (-$2,640). Nothing ships; forward trigger: >=25 "
                "strict-streak dates or >=25 post-2025-11-04 dates.",
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
    "lib/replay_basis.py": "ONE classifier for stored-row-vs-replay disagreement: exact / "
                           "near-rounding-tie / superseded-basis / HARD. Extracted 2026-08-24 "
                           "from exit_switch_mech_study so its harness gate, "
                           "exit_mechanism_study's calibrate() and book.py's debit_calib "
                           "cannot drift. Interprets lib/harness.py's output; never replays.",
    "lib/triggers.py": "The rollback-trigger power census: is_affected/affected (outcome-"
                       "triple disagreement), peak_pnl/arming_rows (trigger 3's literal "
                       "'reach peak >= threshold'), and census_line (n rows/dates, the "
                       "registered floor, FLOOR MET/UNDERPOWERED). Built 2026-08-24 for "
                       "research/pre-registrations/f2_management/rollback_triggers.md; never ships or "
                       "reverts a rule itself — exit_switch_mech_study STEP 3(f), "
                       "bear_arm's be_after census, and exit_mechanism_study --side credit "
                       "own that.",
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
    "lib/greeks.py": "Per-leg greeks read from the option-history cache at a given day, "
                     "signed and qty-scaled, with net-position sums that are all-or-nothing "
                     "per greek (a missing leg makes the greek None, never 0 and never a "
                     "partial sum). Built for financed_spread's exposure reads and "
                     "portfolio_delta's G-DELTA cross-check.",
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
