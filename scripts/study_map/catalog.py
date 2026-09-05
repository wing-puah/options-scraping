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
        verdict="The baseline snapshot other studies import verbatim. It argues nothing on "
                "purpose — it exists so two studies can agree on what the book is, and it prints "
                "no verdict line at all. On the 2026-09-04 v4 export (sha e59356f, 1,143 rows / "
                "166 dates) the one line worth carrying forward is §5d, the continuity check on "
                "the Tier-C iv_spread rule: `iv_spread vs mae_pct | bear_put_spread, "
                "pooled          n=  365  rho=-0.0686  p= 0.1912`. v3 read -0.215 at p<.0001 on "
                "n=380, so the non-replication is now confirmed at COMPARABLE n rather than "
                "excused as a power difference.",
    ),
    "mech_regime_recut": Study(
        family="selection", state="shipped",
        question="Does a deterministic regime label — a pure function of SPY/VIX history at "
                 "the signal date — beat the model's free-text regime?",
        verdict="Overlay adopted. `mech_cell` is a column now, and it is what keys the shipped "
                "BEAR_HE exit override. The OR-veto extension stays rejected on the 2026-09-04 v4 "
                "export (sha e59356f, 1,143 rows / 166 dates): `VERDICT RULE: OR-VETO REJECTED "
                "(newly-vetoed subset net-positive)`. The rows the OR veto would newly cut are net "
                "POSITIVE — `newly-vetoed-by-OR subset                      n=   41  mean=  "
                "0.0526  total=   2.1550  win=0.5122  mae_mean= -0.7721` — which relieves the "
                "08-27 read's net-flat, worth-a-re-read caveat: at n=41 the subset is now clearly "
                "on the wrong side of zero to be cutting. One thing in the report to read past: "
                "the hand-coded Mar-2026 date table prints all-zero rows (`2026-03-06          "
                "0      0.0000         0.0000        0.0000      0.0000`) because this export's "
                "2026 dates are January, February and April, not March — a stale date list, not a "
                "finding.",
    ),
    "bear_position_study": Study(
        family="selection", state="null",
        question="Pre-registered cuts on bear_put: is it a SELECTION problem (E<0) or an "
                 "EXIT problem (E>0 with R<0)?",
        verdict="`VERDICT: DEMOTE TO VETO` — re-confirmed on the 2026-09-04 v4 export (sha "
                "e59356f, 1,143 pooled rows / 166 signal dates). All three pre-registered criteria "
                "fire on the ex-window bear_put population, now n=368 (it was 177 on 2026-08-24): "
                "`[PASS]  ex-window mean E < 0            (-0.222)`, `[PASS]  bootstrap 95% CI "
                "upper < 0      ([-0.349, -0.087])`, `[PASS]  both time halves negative       "
                "(early -0.388, late -0.045)`, with `CONSTRAIN candidates (n>=30, both halves "
                "positive, EX-W): NONE`. Read what the criteria are on: they are on E, the "
                "exit-free number, and that is the whole claim. On R the SAME 368 rows no longer "
                "separate — `bear_put_spread   EX-W  R  n= 368  mean= -0.087  95% CI [-0.197, "
                "+0.026]   CI spans 0` — so this is a selection verdict and not an exit one. "
                "Implementation left to the operator; the finding is that the structure does not "
                "earn its emission share.",
    ),
    "bear_arm": Study(
        family="selection", state="shipped",
        question="B1 — is there any bear subset, definable at decision time, that is not "
                 "negative? B2 — or is the exit simply mis-tuned?",
        verdict="B1 NO: `combinations evaluated: 496  (with n>=40: 194)` / `survivors of the full "
                "pre-registered rule: 0` against `expected false survivors at a nominal 5% rate: "
                "~9.7` — unchanged on the 2026-09-04 v4 export (sha e59356f, `book: 1143 priced "
                "rows (real+tweak), 392 bear, 159 bear dates`). TWO things moved. (1) The "
                "be_after-0.50 ROLLBACK-TRIGGER CENSUS is on its THIRD export and its THIRD answer "
                "— 08-24 FIRED (92 arming rows / 53 dates), 08-27 HOLD (165 / 96), and 09-04 fires "
                "again: `CENSUS [bear-debit be_after 0.50 (arming rows)]: n_rows=199  n_dates=110  "
                "floor=60 rows  -> FLOOR MET`, where (a) and (b) PASS (`$+2,535.50   [PASS]`, "
                "`+0.0600   [PASS]`) and (c) fires on the column this export only just grew — `(c) "
                "per-year mean-R delta, ALL bear-debit rows: 2024:+0.0148  2025:+0.0047  "
                "2026:-0.0431   [FIRE] revert if any year < 0  (negative: [2026])`. Nothing "
                "changes operationally: `structure_exit.enabled` has been false since the 08-24 "
                "revert, and the block's own header now says so (`REVERTED 2026-08-24: "
                "structure_exit.enabled is false; nothing un-reverts without a fresh "
                "registration`). (2) B2's pre-registered EXIT FIX criteria are MET for the first "
                "time — `best non-PROD variant: sl .50 (tighter)  Δ=+0.039 CI[+0.004, +0.071] LOO "
                "min gain +0.035` / `pre-registered EXIT FIX criteria (CI excludes zero AND every "
                "LOO fold positive): MET` — and the bear-specificity control holds beside it "
                "(`same variant on NON-bear debit rows (n=463): +0.140 -> +0.113 (-0.027) — a "
                "bear-keyed rule`). Record it as a FIRST CLEAR, not a ship: the 2026 cut is thin "
                "and spans zero (`year 2026          Δ=+0.022 (n=23) CI[-0.042, +0.095]`), and "
                "this run is the CORRELATED-WINDOW RE-READ the registration provides for — a PASS "
                "there holds the rule and promotes nothing.",
    ),
    "ml_combination": Study(
        family="selection", state="null",
        question="Does any learned combination of structure × regime × geometry × enrichment "
                 "beat the score-free ladder out of sample?",
        verdict="NULL — `VERDICT: NULL RESULT — the ladder is at/near the ceiling of this data`, "
                "on the 2026-09-04 v4 export (sha e59356f, 1,143 rows / 166 dates). The headline "
                "construct is back to barely negative rather than widening: `M3 out-of-fold paired "
                "R gain vs B0: -0.045 CI95 [-0.160, +0.074]  -> CI excludes zero: False` (08-22 "
                "read -0.012, 08-24 read -0.103), and the other learned constructs sit either side "
                "of zero with CIs that span it — `M1  gain +0.027 CI [-0.096, +0.147]` and `M2  "
                "gain +0.002 CI [-0.113, +0.115]`. What is new is that the registration's "
                "positive-in-at-least-two-of-three-years clause is a REAL three-year test for the "
                "first time, now that the export carries 2026 dates: `M3 per-year R  2024:+0.300  "
                "2025:+0.070  2026:-0.251   sign-stable=False (2 positive)` — it passes the clause "
                "on 2024 and 2025 and fails on the year the clause was written to catch, which is "
                "the same shape the CI already says. Re-open on new COLUMNS only, never on new "
                "models; the ladder is at the ceiling of this feature set.",
    ),
    "v4_bridge": Study(
        family="selection", state="open",
        question="v4 dropped two prompt factors. Does the v3-derived ladder still apply to "
                 "what v4 actually emits?",
        verdict="It no longer aborts — a real v4 export landed, the answer is `VERDICT: LADDER "
                "UNVALIDATED ON v4`, standing since 2026-08-22, and on the 2026-09-04 export (sha "
                "e59356f) it hardens: ALL FIVE pre-registered tests now shift, `Shifted: 1. "
                "structure mix, 2. credit share, 3. plays per day, 4. bear share, 5. ladder tier "
                "mix`. Credit share was the one that held through 08-24 (`z = -1.43, p = 0.1521   "
                "within noise`) and no longer does — `two-proportion z = -2.10, p = 0.0355   *** "
                "SHIFT`. The comparison is `1465 plays / 142 dates` of v3 against `2025 plays / "
                "184 dates` of v4. The tier mix is still the widest gap: A 15.4% -> 11.1%, B 13.7% "
                "-> 26.8%, C 60.8% -> 61.0%, VETO 10.2% -> 1.1%, at `chi2 = 222.54, p = 0.0000   "
                "*** SHIFT` (percentages read off the report's two-column table, not a quoted "
                "line). Per the pre-registration: keep deploying under the v3 rules and do NOT "
                "re-derive the ladder on v4 rows yet.",
    ),
    "text_features": Study(
        family="selection", state="null",
        question="Does the model's OWN PROSE — the stated invalidation, trigger, "
                 "specificity, thesis/alt shape, blind-labelled thesis type and confidence, "
                 "and whether its cited flow figures exist in the feed — separate outcome "
                 "within structure x tier, or raise mean R AND profit factor as a gate on "
                 "the shipped ladder?",
        verdict="First run 2026-09-02, era v4 PRIMARY (1,022 priced / 148 dates; ARM B label "
                "coverage 1022/1022 after the batch-10 top-up; citation check 148/148 dates, 1.62% "
                "of cited flow figures unmatched): every feature `NULL` or `UNDERPOWERED` in all "
                "three arms, `PROMPT-ROBUSTNESS FINDINGS ... none`, `ENTRY-GATE CANDIDATES ... "
                "none`. v3 SECONDARY (795 rows): the same, plus one ARM C `alt_ratio` VETO "
                "conjunction pass routed to `NO PRE-REGISTERED VERDICT MATCHES` because the gate "
                "LOWERS mean R (dR -0.0762) while PF rises. The 2026-09-04 re-run on the refreshed "
                "export (sha e59356f, 1,143 priced rows / 166 dates) says the same at the top — "
                "`PROMPT-ROBUSTNESS FINDINGS ... none` / `ENTRY-GATE CANDIDATES ... none` — with "
                "ONE caveat that makes a third of the study unquotable at this population: the "
                "label cache does not cover the new rows and nothing re-labelled them, so "
                "`text_features ARM B` coverage fell to `ARM B label coverage: 1021/1143 priced "
                "rows (89.3%)` on `labeller: mode=cached  unique payloads=1130  cache hits=1008  "
                "claude calls=0  retries=0  rows labelled=1021  rows UNLABELLED=122  batch "
                "failures=0`. An UNLABELLED row is NOT EVALUABLE in ARM B, so no ARM B line may be "
                "quoted for this book until a live-label re-run. Text was the last untested column "
                "family and it nulls like the numeric ones; the model is not hallucinating prints. "
                "Nothing ships, nothing for `prompt_eval draft` to work from.",
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
                "analysis re-run with `--output-dir` (never Sheets), priced through a derived "
                "backtest config with `sheet_tab: null`, compared with `boot_ci_paired_by_date` + "
                "`pf_paired_by_date`; MET is a v5-bump PROPOSAL, never a ship. Smoke on 2025-06-12 "
                "(haiku): four local files + manifest, tab row count identical before and after. "
                "Read the `-latest.txt` on disk knowing what it is: `prompt_eval` takes a "
                "subcommand, so the bulk `run --all` invocation is a DESIGNED refusal — "
                "`prompt_eval: error: the following arguments are required: cmd`, `exit code 2 "
                "after 1.4s` — and not a failed study. The scored run of record is the PROD "
                "variance floor (2026-09-03), which is not this artifact.",
    ),
    "macro_event_study": Study(
        family="selection", state="open",
        question="Do scheduled macro events — FOMC decisions, minutes, CPI, NFP, PCE — show "
                 "up in the book: in entry IV (vrp), in outcomes (R/E), or in exits?",
        verdict="First run (era v3, 795/118): the side-split census leaves ONE powered cell — NFP "
                "AFTER w<=5 — and it is null on vrp (+0.022, CI spans 0) and R (-0.144, CI spans "
                "0); every FOMC/minutes/CPI/PCE cell is underpowered. Context arms: NFP shows VIX "
                "build-then-bleed with post-print SPY relief; FOMC shows nothing (no pre-FOMC "
                "drift at n=26). ARM X's raw trigger fired and DIED under the amendment-2 survival "
                "control -> macro_event_exit DE-QUEUED as SURVIVAL-ARTIFACT. Re-run on the "
                "2026-09-04 v4 export (sha e59356f, 1,143 rows / 166 dates) reaches the same place "
                "from a book twice the size: `X-C1 verdict (164 affected dates vs floor 25): "
                "SURVIVAL-ARTIFACT — macro_event_exit DE-QUEUED; re-arms only on a future "
                "CONTROLLED trigger`. The exit census is what grew — `hold spans >=1 macro event: "
                "1034 rows / 166 dates  mean R +0.059  mean days_held 36.0` on `rows with >=1 "
                "macro event inside realized hold: 1034/1143` — and it stays a survival read, not "
                "an event effect. The export's first 2026 dates put two starred cells on the "
                "primary iv_spread read (`nfp BEFORE w<=5` at `year 2026                    n=  "
                "12/  2d  diff -9.609  CI[-18.321,-2.403] *` and `pce BEFORE w<=5` at `year "
                "2026                    n=  10/  1d  diff +3.135  CI[+0.643,+8.022] *`); 10-12 "
                "rows on one or two dates is not a reading and nothing is quoted from them. "
                "Nothing ships; no v5 bump; passive re-run when the book grows.",
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
        verdict="ARM P NULL / ARM L LAG-TOLERANT, both unchanged as headlines — `ARM P: NULL (no "
                "persistence effect) — no cell separates repeats from firsts` and `ARM L: "
                "LAG-TOLERANT (PUBLISHABLE OPERATIONAL FINDING)` — but the 2026-09-04 v4 run (sha "
                "e59356f, 1,143 rows / 166 dates) is the first one whose ex-window cuts are real. "
                "History: the 08-24 two-analyst review RETRACTED the v4 `emission_timing ARM P` "
                "stale-entry candidate as OFF-BASIS (the registration pins PRIMARY to `--era v3`, "
                "795 rows / 118 dates, and declares v4 SECONDARY), and both analysts flagged that "
                "the report's `ex_2026_feb_apr` cut was a silent no-op on a book ending "
                "2025-08-19. That cut now bites, and the `**` candidates collapse from three to "
                "ONE. The survivor is `emission_timing ARM L`: `T1_low L=3 vs L=0` at `n=349 pairs "
                "/ 128 dates   mean delta -0.1330   CI[-0.2046,-0.0588] EXCLUDES 0  ** CANDIDATE`, "
                "clearing all six criteria including the new year — `4 sign stable by year   : "
                "PASS  2024 -0.1456  2025 -0.1108  2026 -0.1488`. It is the same internal "
                "contradiction the review noted (a tercile L=3 cell printing CANDIDATE under a "
                "LAG-TOLERANT headline), now down to one cell. The two `emission_timing ARM P` "
                "sub-cuts that used to clear both FAIL criterion 4 on a 2026 SIGN FLIP: "
                "`consecutive repeats` reads `4 sign stable by year   : FAIL  2024 -0.3121  2025 "
                "-0.3211  2026 +0.2948`, and `ohlc: repeats that moved AGAINST the play` reads `4 "
                "sign stable by year   : FAIL  2024 -0.2185  2025 -0.5515  2026 +0.5415`. No "
                "intake rule is proposed; the v3 verdict stands.",
    ),

    "trigger_entry": Study(
        family="selection", state="open",
        question="Does entering a play only WHEN its stated trigger level is first crossed, "
                 "at that session's CLOSE, beat the unconditional next-open entry once the "
                 "entry price pays for the confirmation?",
        verdict="First run 2026-09-04, era v4 PRIMARY, re-run the same evening on the refreshed "
                "export (sha e59356f, 1,143 rows / 166 dates; `1105 exact, 2 near, 0 "
                "superseded-basis, 1 boundary-tie, 35 HARD  of 1143` -> `ADMITTED: 1108 rows / 166 "
                "dates (96.9% of the book)`). The verdict is unchanged: `tally: {'NULL': 1, "
                "'LATE-ENTRY': 2}`, no CANDIDATE. The E2 selection census reproduces at shipped "
                "pricing (`N=3      651 rows/162d +0.178    301 rows/136d -0.053    31.6% rows, "
                "1.2% dates       645`), and the re-pricing eats it: `ARM T  N=3` reads `n=645 "
                "rows / 162 dates    shipped meanR +0.1702   trigger meanR +0.1581   DeltaR "
                "-0.0121`, `ARM T  N=5` reads `DeltaR -0.0232`, both with CIs spanning zero. That "
                "is the registered LATE-ENTRY finding — the trigger picks a better book, and the "
                "confirmation costs at least what it is worth. ARM C still says where the money "
                "went: `day-0 P&L <= -25%          n=  61  DeltaR +0.6297` against `day-0 P&L > "
                "+25%           n=  56  DeltaR -0.4151` — waiting only helps rows the day-0 mark "
                "had ALREADY marked down, which is `next_day_move` ARM C's confound and not a text "
                "finding. The N grid flips sign (`N=1 +0.0094  N=3 -0.0121  N=5 -0.0232`), so "
                "`sign flip across the grid: YES — criterion 7 FAILS every cell`. ARM D is flat on "
                "the shipped card (`N=3         312    136    0.2497         0.0100        "
                "[-0.0654, +0.0938]`). Nothing ships; E2 is closed as a shippable intake rule.",
    ),

    # ② management
    "exit_mechanism_study": Study(
        family="management", state="shipped",
        question="The original grid: replay stored daily marks under alternative exit rules, "
                 "real-priced rows only.",
        verdict="SHIPPED the production debit profile — profit target 0.90, stop 0.75, time exit "
                "at 0.75 of DTE, no trailing stop (Attempt 10). On the 2026-09-04 v4 export (sha "
                "e59356f, `debit trades loaded ...: 408`) it classifies via lib/replay_basis.py "
                "and reads `→ 392 exact, 1 near-rounding-tie, 14 superseded-basis, 1 boundary-tie, "
                "0 HARD of 408`, and PROD is solidly positive on a debit book four times the size "
                "of the one the previous record quoted: `PROD pt.90 sl.75 no-trail "
                "tef.75             total=$   +25363  $/ct=  +10266  win=187/408  med=$  -236` "
                "(the `$-959` in the 08-24 entry was the then 280-row v4 debit book — a different "
                "population, not a reversal). Nothing ships from the grid. The two best "
                "out-of-fold cells are still target/ratchet rather than reactive — `BE ratchet "
                "@.75, no trail                    total=$   +28649  $/ct=   +9867  win=185/408  "
                "med=$  -168  Δ=$   +3286  Δ-LOO=$   +2142` and `pt 1.10 no trail` at `Δ-LOO=$    "
                "+475` — and the one genuinely new thing is that a REACTIVE cell finally prints a "
                "positive out-of-fold delta at all, `trail .40 trig .75` at `Δ-LOO=$    +200`, a "
                "rounding error beside the worst cell in the grid, `trail .25 trig .50` at `Δ=$  "
                "-10014  Δ-LOO=$  -12642`. In-sample on 408 rows, selected on the same file they "
                "are scored on: observations, not candidates. The `--side credit` ARM runs in "
                "`--all` on its own stem (exit_mechanism_study-credit-latest.txt) against the "
                "SHIPPED profile: `→ 127 exact, 0 near-rounding-tie, 0 superseded-basis, 0 "
                "boundary-tie, 0 HARD of 127`, and its Attempt-13 rollback trigger is now "
                "STRUCTURALLY unreachable rather than merely thin — `credit rows: 127   bull_put "
                "rows: 120   fresh bull_put rows (signal_date > 2026-07-13): 0` / `CENSUS [credit "
                "sl-none vs sl-1x (fresh bull_put)]: n_rows=0  n_dates=0  floor=15 rows  -> "
                "UNDERPOWERED`, and this book ends 2026-04-16, so no export can populate that "
                "window until later signal dates exist. Thread parked. The standing comparator "
                "still favours the shipped sl-none, but by a fraction of what it did: `PROD pt.65 "
                "sl none                           total=$    +1442  $/ct=   -3122  win=100/127  "
                "med=$  +159` against `sl 1x (pre-Attempt-13)                       total=$     "
                "+858  $/ct=   -3116  win= 88/127  med=$  +151  Δ=$    -584  Δ-LOO=$   -1306` "
                "(08-24: Δ=$-3468, Δ-LOO=$-3853).",
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
        verdict="BEAR_HE cell SHIPPED (trail 0.50 at trigger 0.50), and on the 2026-09-04 v4 "
                "export (sha e59356f, 408 debit rows out of a 1,143-row book / 166 dates) BOTH "
                "verdicts STAY GATED. The whole-book gate still fails on one of six: `VERDICT: "
                "mech-keyed per-regime exit switch STAYS GATED.` Calibration is clean — `row "
                "calibration (mech switch): 392/408 exact, 1 rounding-tie, 14 superseded-basis, 1 "
                "boundary-tie, 0 HARD` -> `PASS: every calibrated real debit row reproduces "
                "DEBIT_PROD, totals match to the cent, and no row is unreconcilable.` What moved "
                "is STEP 3(f), the pre-registered rollback-trigger census and the corrected gate "
                "evaluated at the floor. BEAR_HE still has no reading: `CENSUS [BEAR_HE trail "
                ".50/.50]: n_rows=1  n_dates=1  floor=25 dates  -> UNDERPOWERED`. LVOL is now four "
                "times past its floor and, where the 08-24 run had it CLEARED and the operator "
                "HELD the ship, it now FAILS on its own numbers: `CENSUS [LVOL tef null]: "
                "n_rows=100  n_dates=73  floor=25 dates  -> FLOOR MET`, then `per-affected-date "
                "summed pnl_pct delta (variant - PROD): median=-0.0330  total=+9.8643  (n=73 "
                "affected dates)` and `affected-date halves (restricted to this cell's affected "
                "rows, split at the pooled median date 2024-12-02): early Δ=+10.0657  late "
                "Δ=-0.2015` — two of the four corrected criteria fail (`[FAIL]  median among "
                "affected dates > 0` and `[FAIL]  both time halves positive (restricted to this "
                "cell's affected rows)`), so `VERDICT: LVOL (tef null) STAYS GATED.` The whole "
                "gain is one early window and the median date is negative. LVOL and RANGE/BULL "
                "stay commented out in config/backtest.yml; the 08-24 CLEARED read is superseded, "
                "not re-argued. One census artifact to know about: `FLAG 2026-03-06: no debit rows "
                "in book on this date.`",
    ),
    "exit_switch_structure_study": Study(
        family="management", state="reference",
        question="Q1 — does a bear_put-keyed trail pass the same ship gate? Q2 — is BEAR_HE "
                 "secretly just a composition proxy for that structure effect?",
        verdict="The guard on the shipped rule. It exists to catch the composition trap that "
                "killed oi_confirm_pct and iv_pct, and on the 2026-09-04 v4 export (sha e59356f, "
                "408 debit rows / 166 dates) Q1 still holds: `VERDICT: structure-keyed bear_put "
                "trail STAYS GATED.` on four of six, failing `[FAIL]  LOO median > 0 (pooled)` and "
                "`[FAIL]  positive in BOTH time halves (fixed switch)`. Q2 is where this export "
                "changed the reading, and it INVERTED. The structure-keyed trail is no longer "
                "negative and no longer leaks negatively outside its cell — `structure bear_put "
                "trail Δ=+4.6539   on its complement (outside BEAR_HE) Δ=+3.8804   retained 83%` "
                "(08-24: Δ=-0.8920, complement -1.6656, retained 187%) — so `[PASS]  survives the "
                "BEAR_HE complement (Δ>0 outside BEAR_HE)` now PASSES, where that criterion used "
                "to be the study's sharpest evidence against the structure key. Read it as the "
                "trap it guards for rather than as support: a structure effect that pays 83% of "
                "its delta OUTSIDE the cell it is keyed on is not a key, and Q1's gate is what "
                "keeps it gated. The shipped key is unmoved and still the cleaner one: `shipped "
                "BEAR_HE clause  Δ=+0.7735   on its complement (non-bear_put) Δ=+0.0000   retained "
                "0%` — the mech key's gain lives entirely inside its own cell.",
    ),
    "bear_giveback": Study(
        family="management", state="null",
        question="82% of bear rows go green and then give it back. Can a peak-triggered breakeven stop "
                 "capture that, and does the underlying path explain it?",
        verdict="The `be_after` grid does NOT ship, and there is nothing live for it to add to: "
                "bear_arm's rollback trigger fired again on 2026-09-04 and "
                "`structure_exit.enabled` has been false since the 08-24 revert. On this export "
                "(sha e59356f, 1,143 rows / 166 dates) it is rule 4, the per-year cut, that kills "
                "every leading candidate, and it kills them all on the same year — `be 0.40, "
                "suppressed in BEAR_HE           2024 +0.008 (n=207)  2025 +0.009 (n=161)  2026 "
                "-0.069 (n=23)`, with be 0.30, be 0.25 and be 0.20 reading -0.034, -0.034 and "
                "-0.038 on those same 23 rows, suppressed or STACKED alike. The give-back pattern "
                "still lives in the UNDERLYING rather than in the mark, and the days-to-peak "
                "gradient both held and roughly doubled in power: `peak within 3d               "
                "n=  39  give-back  87%  meanR -0.445  meanPeak +0.39  $  -17,523` against `peak "
                ">20d                    n= 176  give-back  47%  meanR +0.236  meanPeak +1.45  $   "
                "53,410` (08-24: n=18 and n=83).",
    ),
    "volume_signal": Study(
        family="management", state="null",
        question="Share volume is the one column on disk no study has read. Does an "
                 "unusual-O/S ratio (flow contracts / share volume) condition exits — "
                 "or anything — or is it just liquidity in a costume?",
        verdict="NULL — `VERDICT: PATH-VOL-PROXY — MFE and MAE move together with no R "
                "separation.`, unchanged on the 2026-09-04 v4 export (sha e59356f, 1,143 rows / "
                "166 dates): `components: H1a readable=True r_sep=-0.0290  exit_ok=False  "
                "amihud_collapse=False  mfe/mae mirrored=True`. The one frozen exit variant is "
                "still negative out of fold and now barely exists — `rows changed by the variant: "
                "9 (in key 9, outside key 0)` — which is why the per-year table's 2026 row is a "
                "STRUCTURAL zero rather than a null: `2026  n=  50  gain +0.0000`, because none of "
                "the nine changed rows falls in 2026. The column is closed; the live pipeline "
                "never pays the version bump. Bear's monotone os_ratio read is a post-hoc "
                "carry-forward, not a candidate.",
    ),
    "next_day_move": Study(
        family="management", state="null",
        question="Move the give-back question to day 0, where it is knowable at the close: "
                 "cut positions the stock did not confirm?",
        verdict="ARM C does not clear the confound, so no rule — and on the 2026-09-04 v4 export "
                "(sha e59356f, 1,143 rows / 166 dates) the bear-keyed read that used to be the "
                "exception has gone with it. Whole-book, every day-0 cut still LOSES to SHIPPED "
                "(`cut when wrong sign                     +0.009   -0.079        [-0.127, "
                "-0.030]   -0.088         -430   525`). BEAR-KEYED (`bear debit  (n=361 with a "
                "day-0 sigma move)`), all three cuts LOSE the `**` they carried on 08-24 and every "
                "CI now straddles zero: `cut when wrong sign                     -0.031   "
                "+0.074        [-0.005, +0.148]   +0.064       -7,348   196`, `cut when worse than "
                "-0.5 sigma          -0.062   +0.043        [-0.003, +0.090]   +0.033      "
                "-18,884    83`, `cut when inside the flat band (+0.5 sigma)  -0.018   "
                "+0.087        [-0.011, +0.177]   +0.077       -5,909   285`. Criterion 4 fails "
                "underneath that on the export's first 2026 rows — `years: 2024 +0.091 (n=192)  "
                "2025 +0.083 (n=148)  2026 -0.153 (n=21)`, with -0.143 and -0.258 on the same 21 "
                "rows for the other two cuts. The 08-24 reading stands in kind — the cut only paid "
                "where it removed bear rows, which is bear_position_study's DEMOTE TO VETO "
                "arriving through a second door — and is now unsupported on its own numbers as "
                "well. The sensitivity is structural; there is no exit knob here.",
    ),

    "exit_from_text": Study(
        family="management", state="null",
        attention="2026-09-04: the queued re-read is ANSWERED and needs no decision — the v3 "
                  "bear_put_spread E1 candidates do NOT reproduce on v4 now that 2026 dates exist "
                  "(powered at 336 rows, NULL at all three buffers, each failing on 2026). The "
                  "item comes off the queue.",
        question="Do the model's OWN stated invalidation level, trigger condition and "
                 "horizon make better exits than the shipped mechanical profile — an "
                 "underlying-close stop at the invalidation level (E1), entering only "
                 "when the trigger was met (E2, a selection effect), and the emitted "
                 "horizon as the time exit (E3)?",
        verdict="First run 2026-09-02, era v4 PRIMARY; re-run 2026-09-04 on the refreshed export "
                "(sha e59356f, 1,143 rows / 166 dates), where the answer holds and TWO cells move, "
                "both because 2026 rows exist for the first time. `tally: {'UNDERPOWERED': 278, "
                "'NOT A CRITERION (pooled)': 8, 'NULL': 22, 'CONTRARY': 8, 'SURVIVAL-ARTIFACT': "
                "2}` — still no CANDIDATE. (1) The E2 pooled `ALL ALL N=3` cell that read "
                "CANDIDATE (and was never a criterion — pooled, an intake effect by registration) "
                "now reads `VERDICT: NULL`, failing criterion 4: `4 years: 2024 +0.080 (n=87)  "
                "2025 +0.091 (n=64)  2026 -0.043 (n=11)   FAIL`. (2) The queued re-read item is "
                "ANSWERED: the v3 SECONDARY `bear_put_spread` E1 candidates at 1-2% buffer do NOT "
                "reproduce on v4 now that the era can see them. The cell is powered (`population "
                "336 rows   affected 199 rows / 122 dates`) and NULL at all three buffers, each "
                "failing on the same year — `2026 -0.302 (n=16)`, `2026 -0.134 (n=16)`, `2026 "
                "-0.039 (n=16)`. E1 is still CONTRARY where the text level is not a strike, now 8 "
                "cells, all `bull_call_spread` / `LVOL`, with `criteria vector: 1_ci=T  2_loo=T  "
                "3_windows=T  4_years=T  5_tiers=T  6_power=T  7_no_buffer_flip=T` — every "
                "criterion true toward the NEGATIVE sign: the text-derived stop reliably CUTS that "
                "structure's winners. E3 still fails its survival control. Nothing ships, and the "
                "re-read item comes off the queue answered rather than carried.",
    ),
    "exit_drawdown": Study(
        family="management", state="open",
        question="Does any exit rule — chosen WITHOUT look-ahead, on TRAIN dates only — "
                 "reduce the ACCOUNT-LEVEL mark-to-market drawdown of the deployed "
                 "account_sim book without giving back its edge? Five arms: W "
                 "(walk-forward selection over the shipped pt x sl x tef grid, the honesty "
                 "baseline), U (an underlying ATR stop with ATR14 FROZEN at entry), O (a "
                 "flow-unwind exit off the entry long leg's own Open Int path, read LAGGED "
                 "one session, plus one volume-climax variant), P (partial scale-out, "
                 "exact), and D (a SECONDARY drawdown THROTTLE on sizing, which can never "
                 "ship from an f2 study).",
        verdict="RE-RUN 2026-09-05 (era v4, 1,143-row book / 166 dates; SECONDARY era v3 run "
                "and recorded the same day, 795 rows / 118 dates) after the two-analyst "
                "grading reopened the MODULE — never the registration — on three REPORTING "
                "defects: ARM P's split census printed BELOW the G0 cell table that already "
                "carried its own affected counts (ARM P's and ARM D's censuses now print in "
                "G-COV above every cell table), G-CAL asserted account_sim's G2-G5 without "
                "carrying their outcome (they are now run IN-PROCESS and printed: "
                "`G2: PASS` `G3: PASS  (0 violations)` `G4: PASS` `G5: PASS` "
                "`GATES: ALL PASS`), and one invocation printed one population (it now "
                "carries the PRIMARY headline AND the disclosed `all` cut). The verdicts did "
                "not move. PRIMARY (dense-episode) is UNDERPOWERED across the board, the "
                "modal outcome the registration named IN ADVANCE. Quoted verbatim from the v4 "
                "report's own VERDICT SUMMARY, which is PRIMARY's alone: "
                "`population: PRIMARY  (PRIMARY — the cut the verdicts are read from)` "
                "`ARM W/wf         UNDERPOWERED` `ARM W/prod       UNDERPOWERED` "
                "`ARM U/a          UNDERPOWERED` `ARM U/b          UNDERPOWERED` "
                "`ARM O/oi         UNDERPOWERED` `ARM O/vol        UNDERPOWERED` "
                "`ARM P/half       UNDERPOWERED` `ARM D/throttle   SECONDARY-UNDERPOWERED` "
                "`ARM W arm-level token: UNDERPOWERED` `PROD-ROBUST is NOT claimed — too few "
                "dates to say whether PROD survived.` `tally: {'UNDERPOWERED': 7, "
                "'SECONDARY-UNDERPOWERED': 1}`. Every PRIMARY cell failed G0 on the "
                "OOS-stitched population before any drawdown or ΔR clause was evaluated — the "
                "walk-forward split leaves too few TEST dates behind the burn-in to clear the "
                "25-date / 60-row floor at any arm, not just the harder ones: `ARM W/wf` "
                "cleared only `19 rows / 16 dates`, `ARM W/prod` (the PROD grid point itself) "
                "changed `0 rows / 0 dates` at all, and even the best-populated cell, "
                "`ARM O/vol`, reached only `35 rows / 28 dates` against the 60-row floor. The "
                "DISCLOSED SECONDARY CUT on the `all` population is printed beside it and "
                "carries NO verdict; its own tally line, verbatim: SECONDARY CUT `all` tally: "
                "{'UNDERPOWERED': 6, 'NULL': 1, 'SECONDARY-NULL': 1}   (DISCLOSED, carries no "
                "verdict). On that wider cut two cells clear G0 and both land on the "
                "catch-all: `ARM O/vol` at `VERDICT: NULL` (`77 rows / 58 dates`) and the "
                "sizing arm `ARM D/throttle` at `VERDICT: SECONDARY-NULL` "
                "(`88 rows / 39 dates`); the two cuts are never pooled and the `all` NULLs "
                "are not read as a finding. The v3 SECONDARY run has no OOS dates on its "
                "PRIMARY population — every arm reads `(no OOS dates)` — and now RECORDS that "
                "all-UNDERPOWERED cell set as the v4 run's clause 5 referent "
                "(`clause 5 referent: exit_drawdown-cells-v3.json written 2026-09-05 on the "
                "primary population`), which every powered cell reads as "
                "`VACUOUS (v3 cell UNDERPOWERED — no sign to contradict with)`: v3 neither "
                "corroborates nor contradicts v4. Nothing ships from this "
                "study under any outcome, and per the registration's anti-tuning clause the "
                "grid is not re-cut for these dates: a CANDIDATE would still need an "
                "independent window, and an UNDERPOWERED cell publishes its census and stops.",
    ),
    "staged_exit": Study(
        family="management", state="open",
        question="Does a time-STAGED exit — evaluate ONCE at fixed session X on P&L vs the "
                 "original entry, then exit / tighten / arm a trail — work where the "
                 "reactive drawdown-from-peak rules of Attempts 1/2/10 did not?",
        verdict="NULL in substance on both arms — on era v3 (2026-08-19, 795/118) and again on "
                "the 2026-09-04 v4 export (sha e59356f, 1,143 rows / 166 dates), the best-powered "
                "run yet: `51 of 96 cells clear the floor; 45 are UNDERPOWERED.` — `tally: "
                "{'UNDERPOWERED': 45, '-': 51}` — and not ONE powered cell reaches CANDIDATE or "
                "REACTIVE-AGAIN. Know the report's vocabulary before quoting it: a cell that fails "
                "criterion 1 carries no verdict word and prints as a bare `-`, while `NULL` is "
                "reserved for a cell that clears the CI and then fails a stability check, and this "
                "run has none of the latter either. What the extra power bought is the opposite of "
                "a candidate — SIX cells now have a CI excluding zero and all six are HARMFUL: ARM "
                "E X=5 (R <= -0.25 -> exit now) at `DeltaR  -0.033` / `1 CI95 (date-clustered, "
                "n=10000) [-0.061, -0.006]   FAIL`; ARM E X=15 (R >= +0.25) `[-0.046, -0.001]`; "
                "ARM E X=20 (R >= +0.50) `[-0.030, -0.005]`; ARM E X=20 (R >= +0.25) `[-0.054, "
                "-0.011]`; ARM T X=5 (tighten the stop to -0.40) `[-0.057, -0.004]`; ARM T X=20 "
                "(arm the 0.50/0.50 trail) `[-0.053, -0.013]`. The guards hold, so this is a power "
                "result and not a plumbing one. The Attempt-1/2/10 null extends to scheduled "
                "switches, and the scheduled switch now has a measured cost rather than merely no "
                "gain.",
    ),

    # ③ structure
    "bear_rewrap": Study(
        family="structure", state="null",
        question="A bear SPREAD sells the lower put, giving away the vol expansion that makes "
                 "a bear position pay. What if the short leg goes?",
        verdict="The original read — the wrapper is worth +0.085 and does NOT hold in 2026 — and "
                "the 08-24 read that promoted the DIAGONAL are both superseded by the 2026-09-04 "
                "re-run (sha e59356f, run 21:43, after the `entry_price_of` fix), which is the "
                "first bear_rewrap run on a book that CONTAINS 2026 dates. The 08-24 entry's two "
                "caveats are therefore spent: the book no longer ends 2025-08-19 and the year "
                "criterion is no longer vacuous. Population: `bear debit rows: 391  "
                "(Counter({'tweak': 213, 'real': 178}))`, `reconstructed                391  "
                "(100.0%)`. The two naive re-wraps stay dead at 0 of 5 — `long_put` at `dR -0.042 "
                "CI [-0.111, +0.025]` and `wider` at `dR -0.084 CI [-0.155, -0.015]`, five [FAIL]s "
                "each. The diagonal is now 4 of 5, and the one it loses is exactly the criterion "
                "that could not be tested before: `[FAIL] sign-stable every year    2024 +0.195  "
                "2025 +0.259  2026 -0.106`, against `[PASS] CI excludes zero          dR +0.205 CI "
                "[+0.059, +0.360]`, `[PASS] every LOO fold positive  MIN +0.171 over 119 folds "
                "(share+ 100%)`, `[PASS] both ex-window cuts       ex_2025_mar_apr +0.203  "
                "ex_2026_feb_apr +0.211` and `[PASS] right-signed both tiers   real n=68 dR +0.169 "
                "d$ +13,578  tweak n=121 dR +0.225 d$ +29,761`. In the SAME run its portfolio "
                "checks are MET for the first time: `P1 worst-decile: n= 16  meanR +0.499  CI "
                "[+0.202, +0.743]  $+9,681   -> MET` and `P2 correlation with deployed sleeve: "
                "-0.326 over 106 shared dates   -> MET`. Record it as precisely that — the "
                "candidate LOST its year criterion and GAINED its portfolio checks in one run, "
                "which is neither a ship nor a refutation. Two things bound the reading. The YEAR "
                "clause is what tests 2026 here and the WINDOW cut is not: `ex_2026_feb_apr` drops "
                "one long_diag row of 189 (`ALL              n= 189  dR +0.205` against "
                "`ex_2026_feb_apr  n= 188  dR +0.211`), so a passing ex-2026 cut says nothing "
                "about the year. And the 2026 leg is thin — 79 rows of the 1,143-row pooled book — "
                "which is also why P2's own by-year line stops at `by year: 2024 -0.354  2025 "
                "-0.191`, with no 2026 term to check. Still a candidate for an independent window, "
                "on a population bear_position_study says to VETO. Nothing changes in "
                "config/backtest.yml.",
    ),
    "vol_sleeve": Study(
        family="structure", state="null",
        question="Synthesize straddle / strangle / calendar on the dates the engine already "
                 "signalled. Is there a vol sleeve in here?",
        verdict="CLOSED — that word is this catalog's label for the argument, not a token the "
                "study prints. What the run prints is `Q1 non-null: True   Q2 non-null: False` and "
                "`Q2 IS NULL — the sleeve is neither reliably anti-correlated with the deployed "
                "book nor reliably positive on its worst dates.`, unchanged on the 2026-09-04 "
                "re-run (sha e59356f, run 21:45; the book's new year is `2026  n=   61  dates=  "
                "11`). The sign check is still the whole argument, same signs and all three "
                "weaker: straddle `corr(daily mean R)   +0.220   CI95 [+0.063, +0.384]` and "
                "strangle `+0.187   CI95 [+0.036, +0.354]` against calendar `-0.211   CI95 "
                "[-0.384, -0.026]` — the straddle and strangle re-wrap the same exposure, the "
                "calendar does not. WHICH cells clear Q1 moved with the new rows: `Q1 NON-NULL "
                "cells: straddle/>90, strangle/>90, calendar/ALL, calendar/>90` where 08-24 read "
                "straddle/ALL, straddle/>90, calendar/ALL — the ALL-tenor straddle dropped out and "
                "the >90 strangle joined, which is composition rather than a finding, and Q2 fails "
                "either way. The calendar remains the one survivor and reads stronger than before "
                "on the numbers the study prints POST-HOC rather than as a gate: "
                "`calendar                       n= 133  win   57%  PF  1.39  meanR +0.303  $    "
                "17,583` and `calendar   ex_BOTH_windows    n= 123  E +0.337  CI [+0.111, "
                "+0.637]`. The two structures split hard on the new year (straddle `2026:-0.31`, "
                "calendar `2026:+0.67`, on 61 rows over 11 dates — too thin to lean on). Those "
                "worst-decile numbers go on to calendar_hedge, which is where the fill rule bites.",
    ),
    "calendar_hedge": Study(
        family="structure", state="open",
        question="Re-derive that one survivor under a pre-registered pick rule and a strict "
                 "fill rule.",
        verdict="Gates pass; the primary stays unreadable. The 2026-09-04 re-run (sha e59356f, "
                "run 21:55) is the one that matters twice over. First, the reconstruction gate "
                "that stopped the evening's FIRST suite pass now clears completely — "
                "`reconstructs: 1122 / 1122  (100.0%)` -> `R2 PASS` — where that pass stopped at "
                "1121 / 1122 on a single `entry_unpriced` row (UTHR 2025-12-17): "
                "`bear_rewrap.entry_price_of` had no branch for an entry day with no open and no "
                "mark, and it now carries a prior mark forward, mirroring production's third "
                "branch. The other gates: `debit_calib      n=408  exact=392  near-rounding-tie=1  "
                "superseded-basis=14  hard=0`, `deployed: 362 positions over 147 dates, $74,001   "
                "meanR +0.216  win 63%`, and `R4 PASS — the two constructions agree row for row`. "
                "Second, the VERDICT block is unchanged — `H0 FILL           NOT MET`, `H2 "
                "(primary)      NOT EVALUABLE`, `H2 under hold     NOT EVALUABLE   (sensitivity — "
                "may not change the verdict)` — with the fill rate still binding on a book twice "
                "the size: `P1 fillable on deployed dates          75 / 147  =  51.0%   FAIL` and "
                "`P1 fillable on worst-decile dates       4 / 14   =  28.6%   FAIL`. H2 reads what "
                "it can: (a) `corr(daily $)       -0.100  CI95 [-0.228, +0.017]   over 147 "
                "deployed dates (unfillable carried at 0)`; (b) `n=4` -> `UNDERPOWERED — n < 10. "
                "The CI is NOT read and (b) is recorded NOT EVALUABLE, not failed.`; (c) `tail "
                "positive in 3/3 evaluable years — needs >= 2: YES`, but carried on the new year "
                "by ONE position over two dates (`2026: worst-quartile dates   2  deployed     "
                "-1,184  sleeve n=  1 meanR +0.944  -> positive`). H3 is the line to handle "
                "carefully: both baselines now read `-> NOT MET at any size — no fraction leaves "
                "both drawdown and worst-date unharmed.` with `bound by: drawdown fails; "
                "worst-date ok at every f`, on baselines that themselves moved (max DD `-12,529` "
                "on the ladder alone and `-15,425` on ladder + shipped bear sleeve, against "
                "-10,968 and -11,467 on 08-27). Over three consecutive exports H3 has read NOT "
                "MET, then DEPLOYABLE at f=1.00, then NOT MET again — record it as an UNSTABLE "
                "MEASUREMENT, not a verdict, and carry none of the three as evidence. H4's paired "
                "read went flat rather than negative: `n=75 dates  dR +0.001  CI [-0.071, +0.073]` "
                "(08-27: -0.036). H5 is labelled POST-HOC and its one eye-catching cell is "
                "degenerate at n=1 — `mech_cell == BEAR_HE              1   -0.104    "
                "+0.166            [-0.440, -0.099]  <- excludes 0`. Blocked on dates, not refuted.",
    ),

    "financed_spread": Study(
        family="structure", state="open",
        question="Does financing a book debit vertical with a credit position pay — an "
                 "opposite-delta credit spread, a naked short leg, or a same-direction "
                 "credit vertical?",
        verdict="On era v3 (2026-08-19) same-expiry financing (F0-F3) came back all NULL, naked "
                "short significantly HARMFUL, and the post-scrape F4 diagonal held the study's one "
                "CANDIDATE — F4-d20 HOLD at dR +0.176 CI[+0.015,+0.354]. The 2026-09-04 v4 re-run "
                "(sha e59356f, run 21:48; `era v4   book 1143 rows / 166 dates   2024-01-10 .. "
                "2026-04-16`, `kept 797  (bull 414 / bear 383)   of 1143 book rows`) does two new "
                "things. (1) `F3 off1`, the same-direction financed vertical, is the first cell in "
                "this study ever to print the RE-WRAP token: `F3 off1          RE-WRAP`. It clears "
                "six of seven criteria — `[PASS] 1 paired dR > 0, CI excludes zero        dR "
                "+0.217  CI [+0.056, +0.401]`, `[PASS] 2 every LOO fold positive                "
                "MIN +0.173 over 124 folds (share+ 100%)`, `[PASS] 3 window cuts + "
                "ex-BOTH                  ex_2025_mar_apr +0.233  ex_2026_feb_apr +0.220  ex_BOTH "
                "+0.237`, `[PASS] 4 sign-stable every year                 2024 +0.264  2025 "
                "+0.113  2026 +0.353`, `[PASS] 5 right-signed both pricing tiers        real n=135 "
                "dR +0.294  tweak n=98 dR +0.110`, `[PASS] 6 >= 25 affected dates (priced "
                "set)      124 dates` — and fails only the diversification test, `[FAIL] 7 E3 <= 0 "
                "(does not re-wrap the sleeve)  corr +0.159 over 112 shared dates`. That IS the "
                "token's registered meaning (`RE-WRAP        clears 1-6, fails 7 — the financing "
                "does not diversify`): a real gain that is the same exposure again, which the "
                "study is built to refuse. Read it with its own control, which does not separate: "
                "`FIXED-CONTRACTS control (contracts held at the baseline's count)` reads `n= "
                "233   dR +0.102   CI [-0.102, +0.301]`, so part of the PROD-sized gain is "
                "contract SIZING rather than the financing. (2) The v3 candidate goes unconfirmed "
                "a THIRD time, and for the same reason as on 08-24: `F4-d20 hold      "
                "UNDERPOWERED` at `n=36 rows / 33 dates — under the G0 floor, no criterion "
                "evaluated.` (the floor is fewer than 25 dates or fewer than 60 rows), with the "
                "constructibility census naming `target_unreachable=179` as the biggest single "
                "loss. Everything else is NULL — including `F2 off1` at `[FAIL] 1 paired dR > 0, "
                "CI excludes zero        dR -0.497  CI [-1.084, -0.085]`, significantly HARMFUL "
                "and still labelled NULL because only a positive cell can be a candidate in this "
                "grammar. Two cells fail criterion 4 on a mixed-sign year vector, and NOT on the "
                "new year as a quick read suggests: `F1 off1`'s negative year is 2025 (`2024 "
                "+0.085  2025 -0.015  2026 +0.025`) and `F4-d10 hold`'s is 2024 (`2024 -0.123  "
                "2025 +0.064  2026 +0.462`). Nothing ships.",
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
        verdict="Bear is a hedge, not a selection — that half is unmoved. The hedge case itself "
                "REVERSED on the 2026-08-24 v4 refresh and stays reversed on the 2026-09-04 export "
                "(sha e59356f, 1,143 rows / 166 dates): `D1 joint selection x exit : NOT MET`, `D2 "
                "hedge is real          : NOT MET`, `D3 always-on sizing       : NOT MET at any "
                "size`, `D4 conditional pick       : NOT MET`. D2 again fails on the year check "
                "alone, and the year check is a real three-year one now — its two hedge conditions "
                "pass (`bear R on deployed worst-decile dates: +0.032 (row-level CI [-0.218, "
                "+0.403], n=37) — needs > 0: YES` and `sleeve correlation -0.141 — needs < 0: "
                "YES`) and then `tail positive in 1/3 evaluable years — needs >= 2: NO`, where the "
                "one positive year is `2026: worst-quartile dates n=  2  deployed -1.868  bear "
                "+0.724  $    6,537`, which is two dates and not a year. D4 still loses the "
                "shipped ranker outright — `rankers tested: 10  adopted: 0  (~0.5 expected by "
                "chance)` — and the direction that matters for the card is intact: the best of the "
                "ten is `|delta| low first             120   +0.024   -0.060   +0.084 [-0.028, "
                "+0.197]    +0.066`, a CLOSER-to-money pick with a CI spanning zero, so nothing "
                "here contradicts the §4 far-OTM prohibition. D5 is POST-HOC and narrowed hard on "
                "this export, from eight candidate gates to two, both the same cell at two sizes: "
                "`D5 gated sleeve (POST-HOC): 2 candidate gate(s)` — `mech vol H-VOL             "
                "f=1.00  Δtotal +505  ΔDD +770` and `mech vol H-VOL             f=0.50  Δtotal "
                "+253  ΔDD +500`. The §4 pick line stays PULLED and the sleeve stays operator "
                "policy (docs/deployment-rules.md §4), not a v4 evidence claim; the v3 D2 MET / D4 "
                "ADOPTED read is recorded in research/deployment-evidence.md.",
    ),
    "account_sim": Study(
        family="deployment", state="open",
        question="The ladder assumes infinite capital. Does a real $25,000 account — paying "
                 "for positions, holding reserve, respecting a delta cap — still produce a book?",
        verdict="The caps survive; the WINDOW does not. Delta-notional binds before cash does. "
                "Feasibility only — nothing ships from this study under any outcome. On the "
                "2026-09-04 v4 export (sha e59356f, 1,143 rows / `deployed signal dates: 147  "
                "(2024-01-10 .. 2026-04-16)`) the PRIMARY population is `total: 3 episodes, 88 "
                "dates, 221 deployed picks` and the verdict is unchanged — A1 through A6 each "
                "printing `MET`, then `>>> FEASIBLE <<<`, with `GATES: ALL PASS` (G2-G5). The "
                "constrained book there is the configured cell, quoted first and alone, `n=148  "
                "dates=76  $22,217  meanR +0.348` and the drawdown is `A3 NO BLOWUP      maxDD "
                "$-3,750 = 15.0% of capital;  ledger violations 0`. What the export's first 2026 "
                "dates add is a boundary on that claim, and it must be stated with it: the "
                "SECONDARY full book (`n=260  dates=129  $21,855  meanR +0.231`) now fails TWO "
                "criteria — `A1 EDGE SURVIVAL  meanR +0.231  CI95 [+0.120,+0.341]  years "
                "2024:+0.259  2025:+0.263  2026:-0.062` -> `NOT MET`, and `A3 NO BLOWUP      maxDD "
                "$-8,920 = 35.7% of capital;  ledger violations 0` -> `NOT MET`. No verdict reads "
                "from the secondary population by registration — but FEASIBLE is now explicitly a "
                "TWO-YEAR, DENSE-EPISODE claim, because the episodes stop before the new dates "
                "begin: `E3  2025-05-19 .. 2025-09-26    31 dates over  94 sessions    83 deployed "
                "picks`. Nothing in the FEASIBLE read has seen 2026. The POST-HOC compounding arm "
                "(account_sim-compounding-latest.txt, its own page) is `>>> NOT FEASIBLE AT "
                "$25,000 — BLOWUP RISK (A1 holds, A3 fails) <<<` on `A3 NO BLOWUP      maxDD "
                "$-6,424 = 25.7% of capital;  ledger violations 0`, with `B2  compounded max-loss "
                "sizing (from $25,000), unconstrained  n= 221  dates= 88  $    18,778  meanR "
                "+0.238` — the same conclusion it reached before, from the same inputs.",
    ),
    "selection_order": Study(
        family="deployment", state="null",
        question="On v3, account_sim's rejected picks out-earned its taken ones — a read that "
                 "REVERSES on v4 (see the account_sim entry), so the premise this study was "
                 "registered under no longer holds on the current era. The pre-registered "
                 "question stands on its own: does a different BLIND entry-side ORDER of the "
                 "same candidate set spend the scarce delta budget better — or was that read "
                 "an artifact?",
        verdict="ORDERING-IS-NOISE, unchanged on the 2026-09-04 v4 export (sha e59356f, "
                "`PRIMARY   dense episodes: 3 episodes, 88 dates`) — thread CLOSED. G0 clears more "
                "comfortably than it did on 08-27, with the census moving to `O1                 "
                "30             30         20%   ok`, `O2                 27             "
                "23         16%   ok`, `O3                 32             30         20%   ok`, "
                "`O1b                32             32         22%   ok` against the pre-declared "
                "floor of 25 affected dates, and then nothing clears the bar: `VERDICT: "
                "ORDERING-IS-NOISE — no arm separates from the O4 band. The adverse-ordering read "
                "from account_sim was an ARTIFACT of which picks the cap happened to exclude. "
                "Record it and CLOSE the thread.` Every arm sits inside the seeded random-order "
                "band (`O4 band p95 +0.0524 (seed 20260814, 200 draws); this arm +0.0158 sits at "
                "pct 76%  -> FAIL`). The export's first 2026 dates change nothing here and cannot: "
                "the PRIMARY dense episodes span two calendar years, so its criterion-4 line has "
                "no 2026 term at all, and on the SECONDARY full book 2026 is `(n=3)` dates for "
                "every arm — every arm fails criterion 4 on that population with or without it. "
                "Earlier runs (v3, and v4 through 2026-08-24) were UNDERPOWERED at G0 — best arm "
                "20 affected dates against 25 — and read nothing. The `7-14%` figure those runs "
                "quoted was a hardcoded prose literal in the study, corrected 2026-08-22 to print "
                "the run's own measured census.",
    ),

    "concurrency_correlation": Study(
        family="deployment", state="open",
        question="max_positions_per_day caps the FLOW of new positions; nothing caps the "
                 "STOCK of open ones. Does the SIZE and internal SIMILARITY of the open "
                 "book degrade per-position outcome, independently of what was selected?",
        verdict="NOISE (first run 2026-09-04, era v4; the numbers below are that evening's re-run "
                "on the refreshed export, sha e59356f). `>>> NOISE — all 11 powered arms sit "
                "inside ARM N's band. Neither the SIZE of the open book nor its internal "
                "similarity degrades per-position outcome on this era's deployed book, at any "
                "ceiling on either grid. <<<` PRIMARY = `3 episodes, 88 dates` (`positions 221   "
                "dates 88   2024-01-10 .. 2025-09-26`); SECONDARY = the full `147 dates` book "
                "(`positions 362   dates 147   2024-01-10 .. 2026-04-16`). On the bigger book two "
                "arms that used to hold one criterion lost it — `C ceiling 8                  gain "
                "+0.0155 R   criteria met ----` and `C ceiling 20                 gain +0.0174 R   "
                "criteria met ----`, both of which read `--6-` on the preceding v4 run, so X6 is "
                "gone and no ceiling arm holds anything now. `K 3 / same-underlying        "
                "UNDERPOWERED (21 moved dates, 22 moved positions)` and `K 5 / "
                "same-underlying        UNDERPOWERED (7 moved dates, 7 moved positions)` against "
                "the pre-declared floor of 25 dates, and ARM CK is `NOT RUN. The registration runs "
                "ARM CK only if ARM C and ARM K each clear their criteria independently.` Three "
                "things the run established rather than assumed: (1) the book is long-only "
                "(`direction signs in the book: {1: 362}`, `positions whose same-direction count "
                "EQUALS their open count: 362 of 362`), so ARM K / same-direction IS ARM C on a "
                "different grid and is excluded from the conjunction; (2) X7's delta control "
                "barely discriminates — `X7 control — dates by |net delta-notional| / capital band "
                "at session open: [0.0,0.5) 3  [0.5,1.0) 1  [1.0,2.0) 22  [2.0,inf) 121` leaves "
                "ONE readable band, and one band is the whole sample re-labelled, not a control; "
                "(3) ARM D0's DESCRIPTIVE shape is not flat (mean R `[0,3)          143     96   "
                "+0.4317` down to `[6,10)          66     49   -0.0305` by "
                "same-direction-and-sector count on SECONDARY) but it is registered DESCRIPTIVE "
                "ONLY and every ceiling arm that would act on it is inside the null band. X4 (era "
                "stability) is now SETTLED — by hand, from two reports, exactly as the "
                "registration intends. The run itself still prints `X4 ERA STABILITY: PENDING — "
                "one run, one era. See the X4 note.` on every arm, because `lib/era.py` binds one "
                "run to one era, and the rule for settling it is printed beside that: `X4 is "
                "settled by reading the two reports side by side: same sign, both clearing X2 and "
                "X3, and point estimates within 0.15 R. Until that is done, no arm from this study "
                "is ADOPT-eligible.` The `--era v3` companion ran at 21:55 on 2026-09-04 and is "
                "recorded in research/study-results/f4_deployment/concurrency_correlation.md "
                "(its `era v3` section, sha e59356f): on the v3 era book (795 rows / 118 dates) it "
                "powers fewer arms and lands in the same place — `arms run (PRIMARY): 13   powered "
                "past X1: 8   clearing X2/X3/X6/X7: 0`. THE SETTLEMENT: no arm clears X2/X3 in "
                "EITHER era, so no arm is or can be ADOPT-eligible, and the VERDICT is era-stable "
                "(NOISE on both). The per-arm GAINS are not era-stable: of the 8 arms powered in "
                "both eras, 4 keep their sign and 4 flip (`C ceiling 5` v3 -0.1546 / v4 +0.0006, "
                "`C ceiling 8` -0.1182 / +0.0155, `K 5 / same-direction` -0.1546 / +0.0006, `K 3 / "
                "same-direction-and-sector` -0.0478 / +0.0109), two of them 0.155 R apart, outside "
                "the 0.15 R band the rule names. Thread CLOSED on both eras; nothing ships and "
                "nothing is ADOPT-eligible. One limitation of the record: -latest.txt now holds "
                "the v4 re-run, so the per-era file's verdict excerpt is the only v3 evidence left "
                "on disk and anything finer than it — an ARM D0 shape comparison, say — is not "
                "re-checkable without re-running the companion. Twenty-two NOT PRE-REGISTERED "
                "choices are disclosed in the report's own block.",
    ),

    "portfolio_delta": Study(
        family="deployment", state="open",
        question="Is there an optimal PORTFOLIO net delta to keep? account_sim showed "
                 "delta-notional binds before cash; this asks whether the level itself is "
                 "a lever — dose-response, a ceiling band, and a delta-TARGETED hedge "
                 "sleeve, against a seeded random-admission null band.",
        verdict="CANDIDATE-FOR-INDEPENDENT-WINDOW, the label unchanged from the 2026-08-27 run "
                "and re-earned on the 2026-09-04 v4 export (sha e59356f, `deployed picks 362 over "
                "147 dates  (2024-01-10 .. 2026-04-16)`, `PRIMARY   dense episodes: 3 episodes, 88 "
                "dates`) — but the survivor set HALVED, so the catalog no longer names two "
                "ceilings. Only `B ceiling 1.00` clears the full seven-part conjunction: `(1) "
                "paired mean gain +0.1081 R   CI95 [+0.0131, +0.2205] (date-clustered, "
                "BOOT_N=10000)  -> PASS`, `=> B ceiling 1.00: CANDIDATE (all seven) — queued for "
                "an INDEPENDENT window, nothing ships`. `B ceiling 1.50`, which cleared on BOTH "
                "populations on 08-27, now fails on both — on PRIMARY dense episodes at criterion "
                "1 (`(1) paired mean gain +0.0681 R   CI95 [-0.0120, +0.1527] (date-clustered, "
                "BOOT_N=10000)  -> FAIL` -> `=> B ceiling 1.50: FAILS c1`), and on the SECONDARY "
                "full book at criterion 4, on the export's first 2026 rows (`(4) by year: 2024 "
                "+0.0995 (n=53)  2025 +0.0758 (n=42)  2026 -0.0878 (n=11)  -> FAIL`). ARM D is "
                "still not a shape: `SHAPE: NON-MONOTONE / FLAT  (descriptive — NOT A CRITERION, "
                "and no band value may be adopted on it)`. NOTHING SHIPS UNDER ANY OUTCOME and no "
                "ceiling value may be adopted on its P&L (the registration's firewall): the label "
                "queues an INDEPENDENT WINDOW and nothing else.",
    ),

    "hedge_timing": Study(
        family="deployment", state="open",
        question="The bear hedge sleeve is deployed on discretionary triggers — chop, a SPY "
                 "gap-up, a 4-5-day SPY down-run. Does any of them, made mechanical, pick a "
                 "day on which the hedge earns more than the SAME day's ladder-eligible long?",
        verdict="RUN 2026-09-04 (era v4, sha e59356f, 1,143 rows / 166 dates), re-graded after "
                "the 08-28 run. The headline is unchanged — `TIMING-CANDIDATE survivors: 0  (~0.45 "
                "expected by chance at 5%)` — but WHICH arm carries the gap-up finding moved, so "
                "quote the current one. `hedge_timing ARM H1-GAP` went from NULL to `VERDICT "
                "H1-GAP: CONTRARY` (`trigger -0.327 (n=36 dates)   non-trigger -0.082 (n=123 "
                "dates)   delta -0.245`, `CI95 (date-clustered, between) [-0.458, -0.026]`); the "
                "PRIMARY within-date arm is CONTRARY and stronger than it was, `HEADLINE "
                "difference -0.506  CI95 [-0.844, -0.157]` -> `VERDICT H3-GAP: CONTRARY`; and the "
                "dollars arm went the other way, `criteria  unharmed=F sign=- loo_all_same_sign=T "
                "years_ok=T cuts_ok=F` -> `VERDICT H4-GAP: NULL`. The drafted §4 gap-up "
                "prohibition (do not open the hedge on a gap-up day) therefore now rests on H3-GAP "
                "with H1-GAP mirroring it between dates, and NOT on H4 — which the 08-28 record "
                "had carrying it. CHOP and DECLINE-BROAD are `VERDICT H4-CHOP: NULL` and `VERDICT "
                "H4-DECLINE: NULL` where 08-28 read them UNSTABLE. The operator's own 4-5-day "
                "streak stays UNDERPOWERED exactly as fixed in advance by the registration: "
                "`CENSUS [DECLINE-STRICT N=4 (verdict FIXED IN ADVANCE: UNDERPOWERED)]: n_rows=13  "
                "n_dates=4  floor=25 dates  -> UNDERPOWERED  bear-carrying=4  H3-paired=4` and the "
                "N=5 census at `n_rows=7  n_dates=2`. No direction is ever quoted from those. "
                "Nothing ships; the prohibition is HELD for the operator per the registration, and "
                "the forward trigger is unchanged: >=25 strict-streak dates or >=25 "
                "post-2025-11-04 dates.",
    ),
    "hedge_exposure": Study(
        family="deployment", state="open",
        question="When the open book is CONCENTRATED in one correlated cluster, does adding "
                 "a long put on that cluster's proxy reduce the book's MARK-TO-MARKET "
                 "drawdown, versus carrying the same concentrated book unhedged?",
        verdict="UNDERPOWERED (the mechanism question) and MEASUREMENT-ONLY (ARM M) — two words "
                "over two different objects, both emitted, neither ordered ahead of the other, and "
                "both unchanged on the 2026-09-04 v4 export (sha e59356f). The population deadlock "
                "recorded as ERRATUM 1 was RATIFIED by the operator on 2026-08-31 "
                "(research/pre-registrations/f4_deployment/hedge_exposure.md, Population and "
                "basis, consolidated there 2026-09-02): the population is the literal "
                "load_book(include_bs=False) call, because a strike_expiry_tweak row is a REAL "
                "Barchart price for a nearby strike and an operator who does not follow a proposed "
                "leg exactly is modelled better by a book that admits the substitution. `real` is "
                "kept as a REPORTED STRATUM, never a co-primary. On the ratified population — "
                "`population all — the literal load_book(include_bs=False) call (real + tweak)`, "
                "`1143 rows / 166 signal dates` — it still reads `powered POOLED cells 0   POOLED "
                "cell words: UNDERPOWERED 9`, so `VERDICT — the mechanism question, over the hedge "
                "cells: UNDERPOWERED` and NO DIRECTION is quoted from any cell. NEW on this "
                "export, and reported rather than read: the `real` stratum crossed its power floor "
                "for the first time — `535 rows / 158 signal dates`, `powered POOLED cells 9   "
                "POOLED cell words: NULL 9`, with `DIRECT cell words: NULL 3  UNDERPOWERED 6` and "
                "`CONSTITUENT cell words: UNDERPOWERED 9`. That is the first hedge-cell reading "
                "this study has ever powered and it is a NULL — but the stratum is marked "
                "`REPORTED STRATUM — not a co-primary; no verdict is read from it`, so it changes "
                "no verdict here and may not be promoted into one. ARM M is not power-gated and is "
                "the sharper result: `ARM M curve gap: maxDD $-9,332   ulcer +2.81 pts   TUW +2.1 "
                "pts   (differ materially: YES)`, i.e. `the close-bucketed curve UNDERSTATES this "
                "book's max drawdown by 40.2%.` — hence `VERDICT — ARM M, the measurement, which "
                "is not power-gated: MEASUREMENT-ONLY`. Nothing ships. UNDERPOWERED leaves the "
                "queued max-drawdown question OPEN rather than closing it. bear_deploy D3, "
                "calendar_hedge H3 and hedge_timing H4 all STAND — but they were read on the "
                "close-bucketed curve, which understates this book's drawdown by 40%, and that is "
                "now a known limitation of theirs. ERRATUM 2 stands too: `hedge_exposure ARM P` is "
                "INERT AS REGISTERED and has not been redefined, so the binding prose rule is "
                "unreachable; `hedge_exposure ARM RF` prints as UNREGISTERED — ADDED AFTER COMMIT "
                "and no clause reads it. Read with the ratification's own limitation: the "
                "registration's PLAN-TIME observations (exposure table, concentration quantiles, "
                "504-session universe) describe the `real` stratum and are NOT disclosures about "
                "the ratified book — the figures that describe it are the ones the run prints.",
        attention="ARM M's MEASUREMENT-ONLY finding is now RECORDED (2026-08-31): "
                  "research/deployment-evidence.md gained a section qualifying the "
                  "measurement basis of bear_deploy D3, calendar_hedge H3 and hedge_timing "
                  "ARM H4 — none overturned, no figure of theirs restated, and 40.2% is not "
                  "a correction factor transferable to their books. The dilution question "
                  "raised against the ratified population (admitting `tweak` rows made the "
                  "prices representative AND the book more diversified, and only the first "
                  "was argued) was ANSWERED FROM DISK the same day, not left open: "
                  "research/archive/18-hedge-programme-exit-basis-and-text-loop.md "
                  "2026-08-31 (late) shows the deploy card admits only 221 of 458 "
                  "ladder-eligible rows (at most 3 per day), so hedge_exposure's 996-row book is "
                  "about twice as diversified as what the operator actually holds, which "
                  "registered hedge_concentration to measure the admitted book directly.",
    ),
    "hedge_concentration": Study(
        family="deployment", state="open",
        question="On the ADMITTED book — the positions account_sim actually takes under the "
                 "operator's top-3-per-day rule and exposure caps — does a session's cluster "
                 "concentration PREDICT the book's subsequent mark-to-market drawdown, and "
                 "only then does a proxy put on that cluster cut it?",
        verdict="RUN 2026-09-04 (era v4, sha e59356f), re-run of the 08-31 first pass on the "
                "refreshed export and unchanged in verdict: `VERDICT — Stage 1 (ARM K, the "
                "precondition): PRECONDITION-NULL` and `VERDICT — Stage 2 (ARM C, the mechanism): "
                "NOT RUN (Stage 1 PRECONDITION-NULL)`. This is a POWERED null, not an underpowered "
                "one — `usable sessions per concentration tercile   [216, 215, 195]   floor 60 "
                "EACH   PASS` / `dense episodes of admitted signal dates     3   floor 3   PASS` / "
                "`G-POWER-K: PASS` — which is what the two-stage design was for: `hedge_exposure` "
                "could not power a single hedge cell, and Stage 1 does not depend on triggers at "
                "all. The precondition every prior hedge verdict assumed is ABSENT on the book the "
                "operator runs, and on this export the point estimate is not merely inside the "
                "band but AT zero: `1 contrast negative, block-bootstrap CI excludes 0   FAIL   "
                "contrast $-173.65  CI95 [$-1,205.66, $893.81]` and `2 Spearman rho negative, CI "
                "excludes 0              FAIL   rho +0.0000  CI95 [-0.2198, +0.2231]`, with the "
                "contrast well inside the circular-shift null (`contrast       point -173.6548   "
                "null p05 -635.5211   p95 +648.0933   min shift 20 rows   beats p05 (more "
                "negative): no`). Four of six clauses fail (1, 2, 3, 5); the two that PASS are the "
                "CONTROLS — `4 not a gross effect: sign kept in >= 2 of 3          PASS   2 of 3` "
                "and `6 sign kept under BOTH ex-window cuts               PASS   2 of 2` — so it "
                "is not a gross-exposure effect in disguise either, it is no effect. The second of "
                "those controls is real for the first time: `ex_2026_feb_apr    rows  584  usable  "
                "564  contrast       $-164.28   sign kept` is now a genuine cut rather than the "
                "no-op it was on a book that ended in 2025. Population and admission, every count "
                "from this run: `candidate rows (ratified population)          1143   / 166 signal "
                "dates` -> `ladder-eligible rows (tier A/B)                513   / 147 dates` -> "
                "`ADMITTED (taken + taken_downsized)             260   / 129 dates   2024-01-10 .. "
                "2026-04-16`, skipped per_pos_delta 101 · net_delta 84 · day3_cap 68, `partition "
                "check: admitted 260 + skipped 253 = 513  vs ladder-eligible candidates 513   -> "
                "EXACT`. G-ADMIT PASS, G-MTM PASS on TARGET_POSITION (`positions 260   reconciled "
                "260   tolerance $0.01 per contract   worst mismatch $0.0000`) with the "
                "stored-target reconciliation printed beside it as a disclosure, G-BLIND PASS. ARM "
                "M is a measurement and never a verdict here, and it grew with the book: `THE GAP, "
                "printed rather than asserted: maxDD $-5,318 (59.6% of the realized-on-close "
                "drawdown)   ulcer +3.71 pts   TUW +11.4 pts` on the admitted book — the same "
                "direction hedge_exposure found on the every-row book. Stage 2 was NOT run and no "
                "cell was evaluated; its census is on the record (episodes peak at 18 against a "
                "floor of 25), as the registration predicted. SHIP-CRITERIA BRANCH, quoted: "
                "`record in research/deployment-evidence.md as closing the queued max-drawdown "
                "question for concentration-gated hedging; next-steps.md §2.1 closed`. Nothing "
                "ships. This does not overturn hedge_exposure — that study's UNDERPOWERED "
                "describes the every-row book — and it is not evidence about "
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
    "lib/exit_overlays.py": "COMPOSITION wrappers around the frozen harness, for "
                      "exit_drawdown. Each rule (ATR stop, OI unwind, volume climax) answers "
                      "only 'which session do I first fire on?' and compose_earlier takes the "
                      "EARLIER of that and harness.replay's own exit — so no copy of the exit "
                      "loop exists, unlike staged_exit's fork. Carries load_oi (the repo's "
                      "only Open Int reader; blank is MISSING, a literal 0 is a full unwind), "
                      "the ONE encoding of the OI one-session lag, and drop-in replacements "
                      "for account_sim.replay_sized whose memo key is EXTENDED with the "
                      "overlay params (the 2026-08-13 G5 bug class). Disabled, it reproduces "
                      "replay_sized exactly — the G-FORK gate, pinned in tests against the "
                      "same committed fixture as the frozen engine.",
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
