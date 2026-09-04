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
    "text_features": Study(
        family="selection", state="null",
        question="Does the model's OWN PROSE — the stated invalidation, trigger, "
                 "specificity, thesis/alt shape, blind-labelled thesis type and confidence, "
                 "and whether its cited flow figures exist in the feed — separate outcome "
                 "within structure x tier, or raise mean R AND profit factor as a gate on "
                 "the shipped ladder?",
        verdict="First run 2026-09-02, era v4 PRIMARY (1,022 priced / 148 dates; ARM B "
                "label coverage 1022/1022 after the batch-10 top-up; citation check "
                "148/148 dates, 1.62% of cited flow figures unmatched): every feature "
                "`NULL` or `UNDERPOWERED` in all three arms — e.g. `ARM A ... "
                "invalidation_level NULL cells=15 powered=2 ... alt_ratio NULL cells=15 "
                "powered=2 ... hallucination_rate UNDERPOWERED cells=15 powered=0`, `ARM B "
                "... thesis_type NULL cells=75 powered=4`, `ARM C ... thesis_type NULL "
                "arms=10 powered=8`; `PROMPT-ROBUSTNESS FINDINGS ... none`, `ENTRY-GATE "
                "CANDIDATES ... none`. v3 SECONDARY (795 rows): the same, plus one ARM C "
                "`alt_ratio` VETO conjunction pass routed to `NO PRE-REGISTERED VERDICT "
                "MATCHES` because the gate LOWERS mean R (dR -0.0762) while PF rises. Text "
                "was the last untested column family and it nulls like the numeric ones; "
                "the model is not hallucinating prints. Nothing ships, nothing for "
                "`prompt_eval draft` to work from.",
    ),
    "prompt_eval": Study(
        family="selection", state="open",
        attention="2026-09-03 noise floor LANDED: `floor = 0.0419` on paired dR, but the "
                  "same prompt on the same date re-emits a different book (per-date "
                  "mean-R spread across 3 repeats `mean 0.4435 max 0.9479`, tier mix "
                  "A=7/3/2). Estimate: the 40-date backfill resolves only |dR| >= ~0.12 "
                  "per row. A candidate still needs a COMMITTED dir — operator decision.",
        question="Does a CANDIDATE analysis prompt beat the shipped one on the same dates "
                 "under the shipped top-3/day ladder — paired dR, profit factor, "
                 "hallucination rate, zero bear_call leaks — with the live dates, not the "
                 "backfill, as the primary evidence?",
        verdict="Harness only, no candidate scored yet (2026-09-02). It is the loop step: "
                "analysis re-run with `--output-dir` (never Sheets), priced through a "
                "derived backtest config with `sheet_tab: null`, compared with "
                "`boot_ci_paired_by_date` + `pf_paired_by_date`; MET is a v5-bump "
                "PROPOSAL, never a ship. Smoke on 2025-06-12 (haiku): four local files + "
                "manifest, tab row count identical before and after.",
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

    "trigger_entry": Study(
        family="selection", state="open",
        question="Does entering a play only WHEN its stated trigger level is first crossed, "
                 "at that session's CLOSE, beat the unconditional next-open entry once the "
                 "entry price pays for the confirmation?",
        verdict="First run 2026-09-04, era v4 PRIMARY (995 admitted of 1,022 priced, 27 "
                "HARD; 853 in scope / 147 dates): `tally: {'NULL': 1, 'LATE-ENTRY': 2}` — "
                "no CANDIDATE. The E2 selection census REPRODUCES exactly at shipped "
                "pricing (`N=3   579 rows/145d +0.212    274 rows/121d -0.048`), and then "
                "the re-pricing eats it: `ARM T  N=3 ... shipped meanR +0.2038   trigger "
                "meanR +0.1901   DeltaR -0.0137`, `N=5 ... DeltaR -0.0257`, both with a CI "
                "spanning zero. That is the registered LATE-ENTRY finding — the trigger "
                "picks a better book, and the confirmation costs at least what it is "
                "worth. ARM C says where the money went: `day-0 P&L <= -25%  n=53  DeltaR "
                "+0.6256` against `day-0 P&L > +25%  n=51  DeltaR -0.4187` — waiting only "
                "helps the rows the day-0 mark had ALREADY marked down, which is "
                "`next_day_move` ARM C's confound, not a text finding. The N grid flips "
                "sign (`N=1 +0.0145  N=3 -0.0137  N=5 -0.0257`), so criterion 7 fails "
                "everywhere. ARM D is flat on the shipped card (`N=3 ... paired DeltaR "
                "0.0019  [-0.0804, +0.0952]`). v3 SECONDARY is unanimous and stronger: "
                "`tally: {'LATE-ENTRY': 3}` (N=1 -0.0310, N=3 -0.0521, N=5 -0.0723). "
                "Nothing ships; E2 is closed as a shippable intake rule.",
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
        question="82% of bear rows go green and then give it back. Can a peak-triggered breakeven stop "
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

    "exit_from_text": Study(
        family="management", state="null",
        attention="2026-09-02 first run: the v3 replication carries three CANDIDATE cells "
                  "(bear_put_spread, invalidation-as-stop at 1-2% buffer, level != any "
                  "strike) that the PRIMARY v4 era cannot see — re-read when 2026 signal "
                  "dates land on v4; no ship from a SECONDARY era.",
        question="Do the model's OWN stated invalidation level, trigger condition and "
                 "horizon make better exits than the shipped mechanical profile — an "
                 "underlying-close stop at the invalidation level (E1), entering only "
                 "when the trigger was met (E2, a selection effect), and the emitted "
                 "horizon as the time exit (E3)?",
        verdict="First run 2026-09-02, era v4 PRIMARY (995 admitted of 1,022 priced, "
                "27 HARD): `tally: {'UNDERPOWERED': 276, 'NOT A CRITERION (pooled)': 9, "
                "'NULL': 19, 'CONTRARY': 5}` — no CANDIDATE. The five CONTRARY cells are "
                "all E1 on `bull_call_spread` / `LVOL` in the `level != any strike` "
                "split, e.g. `STRUCT bull_call_spread buf1%/ne_strike`: `affected 360 "
                "rows / 134 dates ... DeltaR -0.045 ... CI95 [-0.083, -0.008] PASS ... "
                "tiers: real -0.064 tweak -0.027`, `criteria vector: 1_ci=T 2_loo=T "
                "3_windows=T 4_years=T 5_tiers=T 6_power=T 7_no_buffer_flip=T` — the "
                "text-derived stop reliably CUTS the engine structure's winners. E2 pooled "
                "N=3 reads CANDIDATE but is `NOT A CRITERION (pooled)` and an INTAKE "
                "effect by registration. E3 `SURVIVAL CONTROL: FAIL`. v3 SECONDARY (702 "
                "admitted): three CANDIDATEs on `bear_put_spread` E1 at buf1%/buf2% "
                "(buf1%: 284 rows, 110 affected / 62 dates, dR +0.085 CI [+0.044,+0.126], "
                "LOO min +0.079) — the registered second cell, not an Attempt-9 "
                "restatement — plus five CONTRARY on bull_call_spread and E3 "
                "SURVIVAL-ARTIFACT. Nothing ships; the bear-put stop is a re-read item.",
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
    "hedge_exposure": Study(
        family="deployment", state="open",
        question="When the open book is CONCENTRATED in one correlated cluster, does adding "
                 "a long put on that cluster's proxy reduce the book's MARK-TO-MARKET "
                 "drawdown, versus carrying the same concentrated book unhedged?",
        verdict="UNDERPOWERED (the mechanism question) and MEASUREMENT-ONLY (ARM M) — "
                "two words over two different objects, both emitted, neither ordered "
                "ahead of the other. The population deadlock recorded as ERRATUM 1 was "
                "RATIFIED by the operator on 2026-08-31 (research/pre-registrations/"
                "f4_deployment/hedge_exposure.md, Population and basis, consolidated there "
                "2026-09-02): the population is the literal load_book(include_bs=False) "
                "call, because a strike_expiry_tweak row is a REAL Barchart price for a "
                "nearby strike and an operator who does not follow a proposed leg exactly "
                "is modelled better by a book that admits the substitution. `real` is kept "
                "as a REPORTED STRATUM, never a co-primary. On the ratified population "
                "`powered POOLED cells 0   POOLED cell words: UNDERPOWERED 9` in every "
                "stratum, so `VERDICT — the mechanism question, over the hedge cells: "
                "UNDERPOWERED` and NO DIRECTION is quoted from any cell. ARM M is not "
                "power-gated and is the sharper result: `ARM M curve gap: maxDD $-9,332   "
                "ulcer +1.96 pts   TUW +3.1 pts   (differ materially: YES)`, i.e. "
                "`the close-bucketed curve UNDERSTATES this book's max drawdown by 40.2%.` "
                "— hence `VERDICT — ARM M, the measurement, which is not power-gated: "
                "MEASUREMENT-ONLY`. Nothing ships. UNDERPOWERED leaves the queued "
                "max-drawdown question OPEN rather than closing it. bear_deploy D3, "
                "calendar_hedge H3 and hedge_timing H4 all STAND — but they were read on "
                "the close-bucketed curve, which understates this book's drawdown by 40%, "
                "and that is now a known limitation of theirs. ERRATUM 2 stands too: ARM P "
                "is INERT AS REGISTERED and has not been redefined, so the binding prose "
                "rule is unreachable; ARM RF prints as UNREGISTERED — ADDED AFTER COMMIT "
                "and no clause reads it. Read with the ratification's own limitation: the "
                "registration's PLAN-TIME observations (exposure table, concentration "
                "quantiles, 504-session universe) describe the `real` stratum and are NOT "
                "disclosures about the ratified book — the figures that describe it are the "
                "ones the run prints.",
        attention="ARM M's MEASUREMENT-ONLY finding is now RECORDED (2026-08-31): "
                  "research/deployment-evidence.md gained a section qualifying the "
                  "measurement basis of bear_deploy D3, calendar_hedge H3 and hedge_timing "
                  "ARM H4 — none overturned, no figure of theirs restated, and 40.2% is not "
                  "a correction factor transferable to their books. The dilution question "
                  "raised against the ratified population (admitting `tweak` rows made the "
                  "prices representative AND the book more diversified, and only the first "
                  "was argued) was ANSWERED FROM DISK the same day, not left open: "
                  "research/current.md 2026-08-31 (late) shows the deploy card admits only "
                  "221 of 458 ladder-eligible rows (at most 3 per day), so hedge_exposure's 996-row book is "
                  "about twice as diversified as what the operator actually holds, which "
                  "registered hedge_concentration to measure the admitted book directly.",
    ),
    "hedge_concentration": Study(
        family="deployment", state="open",
        question="On the ADMITTED book — the positions account_sim actually takes under the "
                 "operator's top-3-per-day rule and exposure caps — does a session's cluster "
                 "concentration PREDICT the book's subsequent mark-to-market drawdown, and "
                 "only then does a proxy put on that cluster cut it?",
        verdict="RUN 2026-08-31 (era v4, sha 9834563, exit 0, 24s). "
                "`VERDICT — Stage 1 (ARM K, the precondition): PRECONDITION-NULL` and "
                "`VERDICT — Stage 2 (ARM C, the mechanism): NOT RUN (Stage 1 "
                "PRECONDITION-NULL)`. This is a POWERED null, not an underpowered one — "
                "`usable sessions per concentration tercile   [162, 166, 152]   floor 60 "
                "EACH   PASS` / `dense episodes of admitted signal dates     3   floor 3   "
                "PASS` / `G-POWER-K: PASS` — which is what the whole two-stage design was "
                "for: `hedge_exposure` could not power a single hedge cell, and Stage 1 does "
                "not depend on triggers at all. The precondition every prior hedge verdict "
                "assumed is ABSENT on the book the operator runs: `CONTRAST (high - low)   "
                "$-691.92   CI95 [$-2,000.07, $419.99]   includes 0` and `SPEARMAN rho        "
                "    -0.1487   CI95 [-0.3829, +0.0978]   includes 0`, and the contrast does "
                "not clear the time-structure null either — `contrast       point -691.9172   "
                "null p05 -818.0281 ... beats p05 (more negative): no`. Four of six clauses "
                "fail (1, 2, 3, 5); the two that PASS are the controls — ARM KG keeps the "
                "sign in 2 of 3 gross terciles and both ex-window cuts retain it — so this "
                "is not a gross-exposure effect in disguise either, it is no effect. "
                "Directionally the sign is the registered one (concentrated sessions draw "
                "down more) and it is INSIDE the null band; nothing may be read from it. "
                "Population and admission, every count from the run: 996 ratified rows / 145 "
                "dates -> 458 ladder-eligible -> `ADMITTED (taken + taken_downsized)  221 / "
                "110 dates 2024-01-10 .. 2025-10-30`, skipped per_pos_delta 92 · net_delta 81 "
                "· day3_cap 64, partition EXACT. G-ADMIT PASS (signatures 221 vs 221, "
                "differing 0), G-MTM PASS on TARGET_POSITION (221/221, worst $0.0000) with "
                "the stored-target disclosure beside it (136 mismatches BECAUSE the sim "
                "re-sized 101 and re-exited 35), G-BLIND PASS. ARM M, a measurement and never "
                "a verdict here: `THE GAP ... maxDD $-2,428 (27.2% of the realized-on-close "
                "drawdown)   ulcer +2.49 pts   TUW +15.2 pts` on the admitted book — the same "
                "direction hedge_exposure found on the every-row book, smaller. Stage 2 was "
                "NOT run and no cell was evaluated; its census is on the record (episodes peak "
                "at 18 of 25 needed), as the registration predicted. SHIP-CRITERIA BRANCH, "
                "quoted: `record in research/deployment-evidence.md as closing the queued "
                "max-drawdown question for concentration-gated hedging; next-steps.md §2.1 "
                "closed`. Nothing ships. This does not overturn hedge_exposure — that study's "
                "UNDERPOWERED describes the every-row book — and it is not evidence about "
                "concurrency_correlation's clustering ceiling in either direction.",
        attention="The queued max-drawdown question for CONCENTRATION-GATED hedging is now "
                  "answerable and the answer is no: on the admitted book, how concentrated it "
                  "is says nothing about how far it draws down next, so a concentration gate "
                  "has no trigger to stand on. That is the operator's to record in "
                  "research/deployment-evidence.md and to close next-steps.md §2.1 with — "
                  "this study writes neither. It says NOTHING about hedging in general and "
                  "does not touch the §4 bear sleeve, which is operator policy.",
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
    "lib/basis_audit.py": "Coherence audit for the exit_basis COLUMN — reports, never "
                          "gates. Three one-directional checks (CREDIT<=>negative entry, "
                          "regime label vs the SPY/VIX cell re-derivation, stored exit "
                          "reason reachable under the claimed profile); an armed basis that "
                          "did not govern is NOT a conflict. Unreadable eras audit as "
                          "unlabelled, so v3 studies are untouched. Built 2026-09-02 so a "
                          "study can stratify by exit profile without trusting the label "
                          "blind. Contrast lib/replay_basis.py, which does gate.",
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
    "lib/sectors.py": "The ticker -> correlated-cluster map, the repo's SINGLE encoding: "
                   "11 clusters, one proxy each, residual BROAD -> SPY, and four clusters "
                   "(ENERGY/FINL/CRYPTO/INTL) marked UNHEDGEABLE with the reason carried as "
                   "DATA so a caller branches on the map rather than on a cluster name. "
                   "Transcribed verbatim from hedge_exposure's committed constant and shared "
                   "with concurrency_correlation's ARM K, which imports it rather than "
                   "restating it — two maps would let two studies disagree about what 'same "
                   "sector' means.",
    "lib/concentration.py": "The concentration trigger layer for hedge_exposure: per-session "
                   "open-book occupancy, each cluster's signed delta notional, the "
                   "largest-cluster share that IS the independent variable, the "
                   "DIRECT/CONSTITUENT stratum, the hedge-pressure parse, and the census "
                   "G-CENSUS prints. A missing greek is None and the position leaves BOTH "
                   "numerator and denominator — deliberately unlike account_sim.signed_dn's "
                   "0.0, which here would shrink the denominator and move the trigger.",
    "lib/mtm_curve.py": "The MARK-TO-MARKET book equity curve, built from daily_pnl_csv, "
                   "beside the close-bucketed one account_sim already produces — plus the "
                   "per-position G-MTM reconciliation between them and the path statistics "
                   "(max drawdown — this module's own function, which bear_deploy imports "
                   "back — Ulcer, time-under-water). Both bases come back from one call so "
                   "a caller cannot mix them.",
    "lib/forward_drawdown.py": "The Stage-1 statistics for a \"does book state PREDICT "
                   "forward drawdown\" read: the forward-drawdown series (min of "
                   "levels[t]-levels[s] over the next H sessions, None where no full window "
                   "exists), the rank-tercile contrast, Spearman rho, a bootstrap over "
                   "NON-OVERLAPPING blocks of H rows, and a circular-shift time-structure "
                   "null. Built 2026-08-31 for hedge_concentration's ARM K / KG / KN / K10. "
                   "The forward windows OVERLAP by construction, which is what the block "
                   "bootstrap and the shift null exist for — a row resample would treat H "
                   "nearly-identical outcomes as H independent ones, and a shuffle would "
                   "destroy the autocorrelation the null has to preserve. H, the group count, "
                   "the draw counts and every seed are PARAMETERS; nothing here knows what a "
                   "session, a cluster or a hedge is, and it carries no verdict.",
    "lib/hedge_instrument.py": "Hedge instrument selection and pricing for hedge_exposure: "
                   "the proxy put under the two committed fill rules (band 25-75 DTE / "
                   "+/-5%, nearest-available anchored at 45 DTE within 20-120), the "
                   "delta-equivalent underlying short, and the G-FILL coverage report. "
                   "Returns None rather than a fabricated fill; the rescaled-ticker "
                   "exclusion is a rescaled_tickers() call, not a name list.",
    "lib/protocol.py": "The four defences every conclusion rests on: date clustering, purging "
                   "plus a 120-day embargo, same-dates comparison, and window-dominance "
                   "re-cuts. Also the profit-factor helpers (pf / pf_ci_by_date / "
                   "pf_paired_by_date), which resample dates like every other CI here and "
                   "return None rather than infinity when a book has no losers — a PF "
                   "claim must clear the mean-R criterion too, since PF alone is gameable "
                   "by fewer, larger wins.",
    "lib/text_corpus.py": "The analysis model's PROSE re-attached to every priced row, "
                   "reusing book.py's own join helpers by identity so the text cannot "
                   "disagree with the numbers already joined onto the same row. Parses the "
                   "play cell back into intent / pattern / structure / thesis / Alt (pinned "
                   "against analysis_to_rows, the writer), splits the tagged signal stream, "
                   "and emits ten regex-only features — each of which had to have NO "
                   "numeric counterpart already tested null, which is why tag counts, "
                   "catalyst mentions and hedge language are deliberately absent and "
                   "evidence_n is a redundancy control rather than a candidate. Also "
                   "returns the UNPRICED analysis rows (market_row / no_play / bs_only / "
                   "not_backtested / excluded_by_book), because the book is a non-random "
                   "subset of what the model proposed. Carries no verdict — it is not a "
                   "study.",
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
