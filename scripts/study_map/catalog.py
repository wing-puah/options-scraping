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
                "not tunable from the columns we have — and both live candidates "
                "(emission_timing's lag and repeat cells) are about WHEN, not which.",
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
        "note": "Two unconfirmed candidates and no ship, both of them diagonals: the "
                "bear re-wrap keeps failing its year, and the financed one prints "
                "RE-WRAP, which means it is the same exposure again.",
    },
    "deployment": {
        "index": "④",
        "title": "Deployment",
        "question": "can I actually run this?",
        "note": "Feasibility, not edge. Delta-notional binds before cash does — and on "
                "the re-priced book the $25,000 account fails its drawdown bar, so "
                "the answer is NOT FEASIBLE rather than FEASIBLE.",
    },
    "hedging": {
        "index": "⑤",
        "title": "Hedging",
        "question": "what protects the book when the ladder is wrong?",
        "note": "One ship — bear is a hedge, not a selection. Everything after it is "
                "blocked on dates or underpowered, and the gap-up trigger came back "
                "CONTRARY.",
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
                "no verdict line at all. On the 2026-09-19 suite run (sha 8e9b6a7, `Pooled priced "
                "book: 1375`) the one line worth carrying forward is §5d, the continuity check on "
                "the Tier-C iv_spread rule: `iv_spread vs mae_pct | bear_put_spread, "
                "pooled          n=  446  rho=-0.0774  p= 0.1027`. v3 read -0.215 at p<.0001 on "
                "n=380, so the non-replication is confirmed at MORE than comparable n rather than "
                "excused as a power difference, and the correlation has not strengthened as the "
                "book grew.",
    ),
    "mech_regime_recut": Study(
        family="selection", state="shipped",
        question="Does a deterministic regime label — a pure function of SPY/VIX history at "
                 "the signal date — beat the model's free-text regime?",
        verdict="Overlay adopted. `mech_cell` is a column now, and it is what keys the shipped "
                "BEAR_HE exit override. The OR-veto extension stays rejected on the 2026-09-19 "
                "suite run (sha 8e9b6a7, `Pooled priced book: 1375`, `unique signal dates in "
                "pooled book: 208`): `VERDICT RULE: OR-VETO REJECTED "
                "(newly-vetoed subset net-positive)`. The rows the OR veto would newly cut are net "
                "POSITIVE — `newly-vetoed-by-OR subset                      n=  127  mean=  "
                "0.0170  total=   2.1598  win=0.4961  mae_mean= -0.7356` — and the subset has "
                "tripled in size without crossing zero, which is what settles the "
                "08-27 read's net-flat, worth-a-re-read caveat. The hand-coded Mar-2026 date "
                "table is no longer all zero: `2026-03-12` now carries 4 rows and `2026-03-20` "
                "carries 7, while `2026-03-06          "
                "0      0.0000         0.0000        0.0000      0.0000` and `2026-03-27` are in "
                "no export and were never in the neutral-date selection. Read those two rows as a "
                "stale date list, not a "
                "finding.",
    ),
    "bear_position_study": Study(
        family="selection", state="null",
        question="Pre-registered cuts on bear_put: is it a SELECTION problem (E<0) or an "
                 "EXIT problem (E>0 with R<0)?",
        verdict="`VERDICT: DEMOTE TO VETO` — re-confirmed on the 2026-09-19 suite run (sha "
                "b670ff5, `Rows with both E and R: 987`). All three pre-registered criteria "
                "fire on the ex-window bear_put population, now n=438 (it was 368 on 2026-09-04 "
                "and 177 on 2026-08-24), and the two halves have converged rather than drifted: "
                "`[PASS]  ex-window mean E < 0            (-0.256)`, `[PASS]  bootstrap 95% CI "
                "upper < 0      ([-0.369, -0.135])`, `[PASS]  both time halves negative       "
                "(early -0.285, late -0.220)`, with `CONSTRAIN candidates (n>=30, both halves "
                "positive, EX-W): NONE`. Read what the criteria are on: they are on E, the "
                "exit-free number, and that is the whole claim. On R the SAME 438 rows do not "
                "separate — `bear_put_spread   EX-W  R  n= 438  mean= -0.073  95% CI [-0.171, "
                "+0.028]   CI spans 0` — so this is a selection verdict and not an exit one. "
                "Implementation left to the operator; the finding is that the structure does not "
                "earn its emission share.",
    ),
    "bear_arm": Study(
        family="selection", state="shipped",
        question="B1 — is there any bear subset, definable at decision time, that is not "
                 "negative? B2 — or is the exit simply mis-tuned?",
        verdict="B1 is still NO and B2's ONE clear has been WITHDRAWN. On the 2026-09-19 suite "
                "run (sha b460c86, `book: 1325 priced rows (real+tweak), 485 bear, 199 bear "
                "dates`) B1 reads `combinations evaluated: 496  (with n>=40: 236)` / `survivors "
                "of the full pre-registered rule: 0` against `expected false survivors at a "
                "nominal 5% rate: ~11.8 — a survivor count`, and the verdict block says `B1 "
                "KEEP-CONDITIONED: NOT met — 0 subset(s) passed all criteria`. TWO things moved, "
                "both toward nothing. (1) B2's pre-registered EXIT FIX criteria went from MET "
                "back to `pre-registered EXIT FIX criteria (CI excludes zero AND every LOO fold "
                "positive): NOT met`, because the best variant's interval re-crossed zero: `best "
                "non-PROD variant: sl .50 (tighter)  Δ=+0.030 CI[-0.003, +0.061] LOO min gain "
                "+0.027`, where 09-04 read `Δ=+0.039 CI[+0.004, +0.071]`. The 09-04 FIRST CLEAR "
                "was a correlated-window read that promoted nothing, and it did not survive one "
                "more re-price. The bear-specificity control still holds beside it (`same variant "
                "on NON-bear debit rows (n=504): +0.145 -> +0.108 (-0.036) — a bear-keyed rule`). "
                "(2) The be_after-0.50 ROLLBACK-TRIGGER CENSUS now fires on ALL THREE clauses "
                "rather than only the year one, and the report prints a line it has not printed "
                "before: `REVERT CONDITION FIRED — surface to operator; production config change "
                "required.` The census is `CENSUS [bear-debit be_after 0.50 (arming rows)]: "
                "n_rows=242  n_dates=134  floor=60 rows  -> FLOOR MET`, and each clause reads "
                "`(a) total $ gain vs PROD, arming rows (n=242): $-1,416.00   [FIRE] revert if <= "
                "0`, `(b) mean-R delta, affected rows (n=56): -0.0070   [FIRE] revert if < 0`, "
                "`(c) per-year mean-R delta, ALL bear-debit rows: 2024:+0.0026  2025:-0.0002  "
                "2026:-0.0147   [FIRE] revert if any year < 0  (negative: [2025, 2026])`. Clauses "
                "(a) and (b) had PASSED on 09-04 at `$+2,535.50` and `+0.0600`. Nothing "
                "changes operationally: `structure_exit.enabled` has been false since the 08-24 "
                "revert, and the block's own header says so (`REVERTED 2026-08-24: "
                "structure_exit.enabled is false; nothing un-reverts without a fresh "
                "registration`), so the fired condition asks for no config change that is not "
                "already made. Across four exports the census has now read FIRED, HOLD, FIRED on "
                "one clause, FIRED on three — which is the argument that a 60-row floor on a "
                "backfilling book is not a decision procedure, not an argument about the stop.",
    ),
    "ml_combination": Study(
        family="selection", state="null",
        question="Does any learned combination of structure × regime × geometry × enrichment "
                 "beat the score-free ladder out of sample?",
        verdict="NULL — `VERDICT: NULL RESULT — the ladder is at/near the ceiling of this data`, "
                "on the 2026-09-19 suite run (sha 8e9b6a7, `rows=1325  dates=207`). The headline "
                "construct is a little further under water: `M3 out-of-fold paired "
                "R gain vs B0: -0.063 CI95 [-0.168, +0.042]  -> CI excludes zero: False` (08-22 "
                "read -0.012, 08-24 -0.103, 09-04 -0.045), and every other learned construct is "
                "now negative with a CI that spans zero — `M1  gain -0.055 CI [-0.159, +0.051]` "
                "and `M2  "
                "gain -0.072 CI [-0.178, +0.039]`, where 09-04 had M1 and M2 either side of "
                "zero. The registration's "
                "positive-in-at-least-two-of-three-years clause still runs as a real three-year "
                "test and still passes while the CI says nothing: `M3 per-year R  2024:+0.167  "
                "2025:+0.148  2026:-0.163   sign-stable=False (2 positive)` — it clears the "
                "clause on 2024 and 2025 and fails on the year the clause was written to catch. "
                "The unmodified ladder it is measured against is sign-stable where the models are "
                "not: `B0 per-year R  2024:+0.192  2025:+0.227  2026:+0.056   sign-stable=True (3 "
                "positive)`. Re-open on new COLUMNS only, never on new "
                "models; the ladder is at the ceiling of this feature set.",
    ),
    "v4_bridge": Study(
        family="selection", state="open",
        question="v4 dropped two prompt factors. Does the v3-derived ladder still apply to "
                 "what v4 actually emits?",
        verdict="The verdict holds and one test came back. `VERDICT: LADDER UNVALIDATED ON v4` "
                "has stood since 2026-08-22, and on the 2026-09-19 suite run (sha 8e9b6a7) it "
                "reads `Shifted: 1. structure mix, 3. plays per day, 4. bear share, 5. ladder "
                "tier mix` — FOUR of five, not the five 09-04 printed. Credit share is the one "
                "that moves about: `within noise` through 08-24, `*** SHIFT` on 09-04, and now "
                "`two-proportion z = -1.78, p = 0.0743   within noise` again on `raw           v3 "
                "  390/1465  =  26.6%    v4  613/2545 =  24.1%`. The comparison is `1465 plays / "
                "142 dates` of v3 against `2545 plays / 236 dates` of v4. The tier mix is still "
                "the widest gap: A 15.4% -> 11.1%, B 13.7% "
                "-> 24.8%, C 60.8% -> 62.7%, VETO 10.2% -> 1.4%, at `chi2 = 224.36, p = 0.0000   "
                "*** SHIFT` (percentages read off the report's two-column table, not a quoted "
                "line). One test dropping out does not change what to do, because the "
                "registration keys on ANY shift and four remain. Per the pre-registration: keep "
                "deploying under the v3 rules and do NOT "
                "re-derive the ladder on v4 rows yet.",
    ),
    "text_features": Study(
        family="selection", state="null",
        question="Does the model's OWN PROSE — the stated invalidation, trigger, "
                 "specificity, thesis/alt shape, blind-labelled thesis type and confidence, "
                 "and whether its cited flow figures exist in the feed — separate outcome "
                 "within structure x tier, or raise mean R AND profit factor as a gate on "
                 "the shipped ladder?",
        verdict="Every feature is `NULL` or `UNDERPOWERED` in all three arms, and it has said so "
                "on every run since the first (2026-09-02). On the 2026-09-19 suite run (sha "
                "8e9b6a7, `era=v4  priced rows=1325  dates=207`) both findings lists are still "
                "empty: `PROMPT-ROBUSTNESS FINDINGS ... none` and `ENTRY-GATE CANDIDATES ... "
                "none`. ONE caveat makes a third of the study unquotable at this population, and "
                "it got WORSE rather than better: the label cache does not cover the new rows "
                "and nothing re-labelled them, so "
                "`text_features ARM B` coverage fell to `ARM B label coverage: 992/1325 priced "
                "rows (74.9%)` (89.3% on 09-04) on `labeller: mode=cached  unique payloads=1325  "
                "cache hits=992  "
                "claude calls=0  retries=0  rows labelled=992  rows UNLABELLED=333  batch "
                "failures=0`. An UNLABELLED row is NOT EVALUABLE in ARM B, so no ARM B line may be "
                "quoted for this book until a live-label re-run. The citation check is on the "
                "same footing — `mode=cached  dates covered=183/207`, `cited tokens=9441  found "
                "on the tape=9265  overall unmatched rate=1.86%` — which still says the model is "
                "not inventing prints. Text was the last untested column "
                "family and it nulls like the numeric ones. "
                "Nothing ships, nothing for `prompt_eval draft` to work from. The v3 SECONDARY "
                "`alt_ratio` reading the earlier entry carried is not in this run at all: the "
                "PRIMARY era is v4, and a finding about v3 text is a finding about a dead "
                "prompt.",
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
                "It is a tool driven by subcommands, so `run --all` skips it (`BULK_RUN = False`, "
                "2026-09-17); any `-latest.txt` on disk is an older bare invocation's argparse "
                "refusal, not a result. The scored run of record is the PROD variance floor "
                "(2026-09-03).",
    ),
    "macro_event_study": Study(
        family="selection", state="open",
        question="Do scheduled macro events — FOMC decisions, minutes, CPI, NFP, PCE — show "
                 "up in the book: in entry IV (vrp), in outcomes (R/E), or in exits?",
        verdict="`macro_event_exit` stays DE-QUEUED, and the trigger that queued it no longer "
                "even fires. On the 2026-09-19 suite run (sha 8e9b6a7, `book: 1325 rows`) ARM X "
                "reads `RAW TRIGGER (monotone R across hold-position terciles AND >= 25 affected "
                "dates [207]): not fired`, so the de-queue now rests on the raw trigger failing "
                "rather than only on the survival control killing it. The control still prints "
                "its own verdict: `X-C1 verdict (203 affected dates vs floor 25): "
                "SURVIVAL-ARTIFACT — macro_event_exit DE-QUEUED; re-arms only on a future "
                "CONTROLLED trigger`. The exit census grew with the book — `hold spans >=1 macro "
                "event: 1195 rows / 207 dates  mean R +0.058  mean days_held 35.7` on `rows with "
                ">=1 "
                "macro event inside realized hold: 1195/1325` — and it stays a survival read, not "
                "an event effect. What the earlier entries said about power is now WRONG and must "
                "not be carried: this is no longer a one-powered-cell study, and only "
                "`fomc_minutes: every proximity cell UNDERPOWERED (census in G0; not read)` still "
                "holds across the board. Ten proximity contrasts are powered on the vrp arm and "
                "three reads are newly starred — `BEFORE w<=5 vs CONTROL       n= 153/ 27d  diff "
                "+0.034  CI[+0.007,+0.060] *` on cpi entry IV, and on R `BEFORE w<=3 vs CONTROL   "
                "    n= 203/ 28d  diff +0.185  CI[+0.033,+0.343] *` and `BEFORE w<=5 vs CONTROL  "
                "     n= 261/ 36d  diff +0.152  CI[+0.008,+0.300] *` on pce. None is a criterion "
                "and none is de-queueable evidence; they are the cells to re-read first when the "
                "book next grows. The two thin 2026 iv_spread cells the 09-04 entry flagged both "
                "lost their star, and the pce one flipped sign (`year 2026                    n=  "
                "23/  4d  diff -3.607  CI[-12.801,+2.503]`). "
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
        verdict="Both headlines hold and the candidate COUNT went back up. `ARM P: NULL (no "
                "persistence effect) — no cell separates repeats from firsts` and `ARM L: "
                "LAG-TOLERANT (PUBLISHABLE OPERATIONAL FINDING)` are unchanged on the 2026-09-19 "
                "suite run (sha 8e9b6a7, `rows=1325  dates=207`), but the report now prints TWO "
                "`** CANDIDATE` cells where 09-04 had one, and the new one sits under the ARM P "
                "NULL headline. `emission_timing ARM P` / `ohlc: repeats that moved AGAINST the "
                "play` clears all six criteria — `n=130 pairs / 130 dates   mean delta -0.2579   "
                "CI[-0.4455,-0.0784] EXCLUDES 0  ** CANDIDATE` — on the strength of the one "
                "criterion it failed last time: `4 sign stable by year   : PASS  2024 -0.2186  "
                "2025 -0.3447  2026 -0.0873`, where 09-04 read a 2026 term of +0.5415. The other "
                "ARM P sub-cut went the opposite way and is still not a candidate, for a "
                "different reason: `consecutive repeats` now passes the year criterion (`2026 "
                "-0.5210`) and FAILS criterion 1, at `n=91 pairs / 91 dates   mean delta -0.2191  "
                " CI[-0.4660,+0.0252] includes 0`. `emission_timing ARM L`'s survivor holds, "
                "weaker and wider: `T1_low L=3 vs L=0` at `n=408 pairs "
                "/ 156 dates   mean delta -0.0826   CI[-0.1542,-0.0085] EXCLUDES 0  ** CANDIDATE`, "
                "still clearing all six — `4 sign stable by year   : "
                "PASS  2024 -0.1405  2025 -0.0052  2026 -0.0983`. The internal contradiction the "
                "08-24 review noted is therefore worse rather than better: a NULL headline and a "
                "LAG-TOLERANT one now sit above two cells the report itself marks CANDIDATE. "
                "Neither is a rule. The 08-24 review RETRACTED the v4 stale-entry candidate as "
                "OFF-BASIS, because the registration pins PRIMARY to `--era v3` (795 rows / 118 "
                "dates) and declares v4 SECONDARY, and nothing in this run changes that basis. No "
                "intake rule is proposed; the v3 verdict stands.",
    ),

    "trigger_entry": Study(
        family="selection", state="open",
        question="Does entering a play only WHEN its stated trigger level is first crossed, "
                 "at that session's CLOSE, beat the unconditional next-open entry once the "
                 "entry price pays for the confirmation?",
        verdict="LATE-ENTRY on every cell now, and the finding is STRONGER rather than weaker. "
                "On the 2026-09-19 suite run (sha 8e9b6a7, `book: 1325 rows  era=v4  "
                "n_dates=207`; `1277 exact, 4 near, 0 "
                "superseded-basis, 1 boundary-tie, 43 HARD  of 1325` -> `ADMITTED: 1282 rows / "
                "206 dates (96.8% of the book)`) the tally moved from `{'NULL': 1, 'LATE-ENTRY': "
                "2}` to `tally: {'LATE-ENTRY': 3}` — the N=1 cell that used to read NULL is "
                "LATE-ENTRY too, because its delta turned negative. Still no CANDIDATE. The E2 "
                "selection census reproduces at shipped "
                "pricing (`N=3      773 rows/201d +0.189    351 rows/167d -0.073    31.2% rows, "
                "2.0% dates       767`), and the re-pricing eats it: `ARM T  N=3` reads `n=767 "
                "rows / 201 dates    shipped meanR +0.1823   trigger meanR +0.1500   DeltaR "
                "-0.0323`, and `ARM T  N=5` reads `DeltaR -0.0427` — and that N=5 cell is now the "
                "first whose interval EXCLUDES zero, at `1 CI95 date-clustered   : PASS  "
                "[-0.0800, -0.0033]`. It clears criteria 1 to 7 and is still printed LATE-ENTRY, "
                "because LATE-ENTRY precedes CONFOUND-EXPLAINED in the first-match-wins grammar. "
                "So the registered finding is measured rather than merely directional: the "
                "trigger picks a better book, and the "
                "confirmation costs more than it is worth. ARM C still says where the money "
                "went: `day-0 P&L <= -25%          n=  69  DeltaR +0.5081   WRONG SIGN` against "
                "`day-0 P&L > "
                "+25%           n=  62  DeltaR -0.5047   right-signed` — waiting only helps rows "
                "the day-0 mark "
                "had ALREADY marked down, which is `next_day_move` ARM C's confound and not a text "
                "finding. The N grid no longer flips sign (`N=1 -0.0039  N=3 -0.0323  N=5 "
                "-0.0427`), so `sign flip across the grid: no` and criterion 7 now PASSES in "
                "every cell — the grid is uniformly negative instead of straddling. ARM D is flat "
                "on the shipped card (`N=3         360    162    0.2442         0.0080        "
                "[-0.0641, +0.0842]`). Nothing ships; E2 is closed as a shippable intake rule.",
    ),

    # ② management
    "exit_mechanism_study": Study(
        family="management", state="shipped",
        question="The original grid: replay stored daily marks under alternative exit rules, "
                 "real-priced rows only.",
        verdict="SHIPPED the production debit profile — profit target 0.90, stop 0.75, time exit "
                "at 0.75 of DTE, no trailing stop (Attempt 10) — and the 2026-09-19 suite run "
                "(sha 8e9b6a7, `debit trades loaded ...: 461`) is the cleanest result the shipped "
                "profile has had: EVERY cell in the grid now loses to it, in sample and out. The "
                "calibration is `→ 438 exact, 1 near-rounding-tie, 21 superseded-basis, 1 "
                "boundary-tie, 0 HARD of 461` and PROD reads `PROD pt.90 sl.75 no-trail "
                "tef.75             total=$   +41934  $/ct=  +11708  win=214/461  med=$  -233  "
                "[v1 cmp: $   +58729]` (the `[v1 cmp: ...]` field is new on every debit line, "
                "beside a `v1 comparison set (NOT used for selection): 278 debit rows`). Two "
                "readings from 09-04 are now DEAD and must not be carried. The claim that a "
                "reactive cell had finally printed a positive out-of-fold delta is gone: `trail "
                ".40 trig .75` went from `Δ-LOO=$    +200` to `Δ=$   -6187  Δ-LOO=$   -8092`. And "
                "the two target/ratchet cells that led out of fold both turned negative — `BE "
                "ratchet @.75, no trail                    total=$   +40061  $/ct=  +10301  "
                "win=208/461  med=$  -211  Δ=$   -1873  Δ-LOO=$   -3017  [v1 cmp: $   +51506]`, "
                "and `pt 1.10 no trail` at `Δ=$   -6699  Δ-LOO=$   -8229`. The least-bad cell is "
                "now `pt .75 no trail` at `Δ=$    -967  Δ-LOO=$   -3587`, and the worst is no "
                "longer `trail .25 trig .50` but `trail .40 trig .50                           "
                "total=$   +16479  $/ct=   -1400  win=241/461  med=$   +60  Δ=$  -25455  Δ-LOO=$  "
                "-27589`. In-sample on 461 rows, selected on the same file they "
                "are scored on: observations, not candidates. The `--side credit` ARM runs in "
                "`--all` on its own stem (exit_mechanism_study-credit-latest.txt) against the "
                "SHIPPED profile: `→ 137 exact, 0 near-rounding-tie, 0 superseded-basis, 0 "
                "boundary-tie, 0 HARD of 137`, and its Attempt-13 rollback trigger is "
                "STRUCTURALLY unreachable rather than merely thin — `credit rows: 137   bull_put "
                "rows: 130   fresh bull_put rows (signal_date > 2026-07-13): 0` / `CENSUS [credit "
                "sl-none vs sl-1x (fresh bull_put)]: n_rows=0  n_dates=0  floor=15 rows  -> "
                "UNDERPOWERED`, and the book runs to 2026-05-07, so no export can populate that "
                "window until later signal dates exist. Thread parked. The standing comparator "
                "favours the shipped sl-none by MORE than it did on 09-04, back to roughly the "
                "08-24 margin: `PROD pt.65 "
                "sl none                           total=$    +2007  $/ct=   -2504  win=106/137  "
                "med=$  +159` against `sl 1x (pre-Attempt-13)                       total=$    "
                "-1237  $/ct=   -5005  win= 89/137  med=$  +148  Δ=$   -3244  Δ-LOO=$   -3966` "
                "(09-04: Δ=$-584, Δ-LOO=$-1306; 08-24: Δ=$-3468, Δ-LOO=$-3853).",
    ),
    "exit_switch_mech_study": Study(
        family="management", state="shipped",
        question="A per-regime exit switch keyed on the mechanical regime — is it stable "
                 "where the model-keyed version failed leave-one-out?",
        verdict="BEAR_HE cell SHIPPED (trail 0.50 at trigger 0.50), and on the 2026-09-19 suite "
                "run (sha 8e9b6a7, 461 real debit rows, `pooled debit trades = 987`, 206 dates) "
                "BOTH "
                "verdicts STAY GATED. The whole-book gate fails two of six: `VERDICT: "
                "mech-keyed per-regime exit switch STAYS GATED.` on `[FAIL]  LOO median > 0 "
                "(pooled)` and `[FAIL]  positive in BOTH time halves (fixed switch)`, with "
                "`time halves (fixed mech): early Δ=+5.2924  late Δ=-1.7554`. Calibration is "
                "clean — `row "
                "calibration (mech switch): 438/461 exact, 1 rounding-tie, 21 superseded-basis, 1 "
                "boundary-tie, 0 HARD` -> `PASS: every calibrated real debit row reproduces "
                "DEBIT_PROD, totals match to the cent, and no row is unreconcilable.` What moved "
                "is STEP 3(f), the pre-registered rollback-trigger census and the corrected gate "
                "evaluated at the floor. BEAR_HE still has no reading, on eight times the rows: "
                "`CENSUS [BEAR_HE trail "
                ".50/.50]: n_rows=8  n_dates=8  floor=25 dates  -> UNDERPOWERED`. LVOL is three "
                "times past its floor and now fails only ONE of the four corrected criteria, "
                "where 09-04 had it failing two: `CENSUS [LVOL tef null]: "
                "n_rows=106  n_dates=80  floor=25 dates  -> FLOOR MET`, then `per-affected-date "
                "summed pnl_pct delta (variant - PROD): median=-0.0110  total=+7.8770  (n=80 "
                "affected dates)` and `affected-date halves (restricted to this cell's affected "
                "rows, split at the pooled median date 2025-02-04): early Δ=+6.4971  late "
                "Δ=+1.3799` — so `[FAIL]  median among "
                "affected dates > 0` stands alone and `[PASS]  both time halves positive "
                "(restricted to this cell's affected rows)` has flipped in the gate's favour. "
                "`VERDICT: LVOL (tef null) STAYS GATED.` still, on the median. Do not read the "
                "halves flip as progress: the 08-24 run had LVOL CLEARED, 09-04 had it failing "
                "two criteria, and this run one — a cell that answers differently on three "
                "consecutive exports is not a rule waiting to ship. LVOL and RANGE/BULL "
                "stay commented out in config/backtest.yml. Perturbing the frozen VIX and SMA "
                "constants moves nothing: `SIGN FLIPS vs frozen: NONE`. One census artifact to "
                "know about: `FLAG 2026-03-06: no debit rows "
                "in book on this date.`",
    ),
    "exit_switch_structure_study": Study(
        family="management", state="reference",
        question="Q1 — does a bear_put-keyed trail pass the same ship gate? Q2 — is BEAR_HE "
                 "secretly just a composition proxy for that structure effect?",
        verdict="The guard held and it is now reporting something about the SHIPPED rule, not "
                "just about the candidate it was built to block. On the 2026-09-19 suite run (sha "
                "8e9b6a7, 461 real debit rows, `pooled = 987`, 206 dates) Q1 is unchanged in word "
                "— `VERDICT: structure-keyed bear_put "
                "trail STAYS GATED.` — and worse in substance, failing FOUR of six rather than "
                "two: `[FAIL]  LOO median > 0 (pooled)`, `[FAIL]  LOO total > 0 (pooled)`, "
                "`[FAIL]  positive in BOTH time halves (fixed switch)` and `[FAIL]  positive "
                "post-13c (LOO total > 0)`, on `pooled  LOO: median=+0.0000 total=-13.1162 "
                "nonneg=95.15%`. The candidate is dead on this book. Q2 is the line to carry "
                "forward, because the SHIPPED BEAR_HE clause is NEGATIVE on the re-priced book: "
                "`shipped "
                "BEAR_HE clause  Δ=-4.5205   on its complement (non-bear_put) Δ=-2.1440   "
                "retained 47%`, where 09-04 read `Δ=+0.7735` with nothing outside its own cell. "
                "That is the opposite of the clean key the earlier entries described, and it is "
                "an OBSERVATION rather than a rollback trigger — the registered trigger for the "
                "shipped trail is `exit_switch_mech_study`'s BEAR_HE census, which is still "
                "UNDERPOWERED at 8 dates of 25. The operator's call, not this study's. The "
                "structure-keyed trail meanwhile inverted too, and now loses inside its own cell "
                "while gaining outside it: `structure bear_put "
                "trail Δ=-1.0189   on its complement (outside BEAR_HE) Δ=+1.3575   retained "
                "-133%` (09-04: Δ=+4.6539, complement +3.8804, retained 83%). `[PASS]  survives "
                "the BEAR_HE complement (Δ>0 outside BEAR_HE)` therefore still prints PASS for a "
                "reason that is not support: the criterion reads the complement's sign, and the "
                "cell's own delta is negative. This is exactly the composition trap the study "
                "exists to catch, and it now catches both keys at once.",
    ),
    "bear_giveback": Study(
        family="management", state="null",
        question="82% of bear rows go green and then give it back. Can a peak-triggered breakeven stop "
                 "capture that, and does the underlying path explain it?",
        verdict="The `be_after` grid does NOT ship, and what stops it has CHANGED: it is now "
                "criterion 1, not the per-year cut. There is nothing live for it to add to "
                "either — `structure_exit.enabled` has been false since the 08-24 revert and "
                "bear_arm's rollback census fires again on the 2026-09-19 run. On that run (sha "
                "8e9b6a7, `book: 1325 rows`, `bear debit 483`) every variant's interval straddles "
                "zero and none carries a `**`: the widest is `be 0.20, STACKED in BEAR_HE        "
                "    -0.054   +0.026        [-0.008, +0.057]   +0.021     -27,449   118       "
                "21`, and every arm is still net negative in dollars against a shipped baseline "
                "of `-0.079   +0.000  (identical to shipped)        —     -41,166`. Rule 4, the "
                "per-year cut, no longer kills the leading candidates and must not be quoted as "
                "doing so: every STACKED variant is positive in all three years, as is `be 0.25, "
                "suppressed in BEAR_HE           2024 +0.019 (n=225)  2025 +0.019 (n=194)  2026 "
                "+0.003 (n=64)`, and only the suppressed 0.40, 0.30 and 0.20 variants still go "
                "negative in 2026 — `be 0.40, "
                "suppressed in BEAR_HE           2024 +0.007 (n=225)  2025 +0.010 (n=194)  2026 "
                "-0.025 (n=64)`. The leak guard holds (`non-bear debit       n= 504  rows changed "
                "by be .50 -> be .30: 0`). The give-back pattern "
                "still lives in the UNDERLYING rather than in the mark, and the days-to-peak "
                "gradient held again on more rows: `peak within 3d               "
                "n=  46  give-back  87%  meanR -0.415  meanPeak +0.40  $  -19,023` against `peak "
                ">20d                    n= 205  give-back  43%  meanR +0.288  meanPeak +1.45  $   "
                "72,175` (09-04: n=39 and n=176).",
    ),
    "volume_signal": Study(
        family="management", state="null",
        question="Share volume is the one column on disk no study has read. Does an "
                 "unusual-O/S ratio (flow contracts / share volume) condition exits — "
                 "or anything — or is it just liquidity in a costume?",
        verdict="NULL — `VERDICT: PATH-VOL-PROXY — MFE and MAE move together with no R "
                "separation.`, unchanged on the 2026-09-19 suite run (sha 8e9b6a7, `book: 1325 "
                "rows`): `components: H1a readable=True r_sep=+0.0025  exit_ok=False  "
                "amihud_collapse=False  mfe/mae mirrored=True`. The separation term flipped sign "
                "from -0.0290 and is still nothing, which is the point of the verdict. The one "
                "frozen exit variant is "
                "still negative out of fold and now measurably so, on `rows changed by the "
                "variant: 15 (in key 15, outside key 0)`: `paired CI95 (date-clustered): "
                "[-0.0163, -0.0021]` with `LOO by date: mean -0.0087  share>0 0%`. Two earlier "
                "readings are gone. The per-year table's 2026 row is no longer a structural zero "
                "— it reads `2026  n= 100  gain -0.0007` where 09-04 had `2026  n=  50  gain "
                "+0.0000` with no changed row in the year. And bear's os_ratio terciles are no "
                "longer monotone: `LOW      121   -0.100`, `MID      129   -0.053`, `HIGH     "
                "217   -0.118`, every interval straddling zero, so the monotone post-hoc "
                "carry-forward earlier entries mentioned has no referent. The column is closed; "
                "the live pipeline never pays the version bump.",
    ),
    "next_day_move": Study(
        family="management", state="null",
        question="Move the give-back question to day 0, where it is knowable at the close: "
                 "cut positions the stock did not confirm?",
        verdict="One bear-keyed cut has its `**` BACK and it still does not become a rule, "
                "because ARM C never clears the confound. On the 2026-09-19 suite run (sha "
                "8e9b6a7, `book: 1325 rows`, `ARM R population note: 1274 of 1325 book rows carry "
                "a day-0 move`) the whole-book picture is unchanged — every day-0 cut LOSES to "
                "SHIPPED, the mildest being "
                "`cut when wrong sign                     +0.018   -0.071        [-0.112, "
                "-0.030]   -0.078        5,381   652`. BEAR-KEYED (`bear debit  (n=483 with a "
                "day-0 sigma move)`) is where it moved: `cut when worse than "
                "-0.5 sigma          -0.039   +0.041        [+0.002, +0.082]   +0.033      "
                "-17,276   108  **` now excludes zero, where 09-04 read `[-0.003, +0.090]` and "
                "carried no marker, and its year cut passes as well (`years: 2024 +0.067 (n=225) "
                " 2025 +0.021 (n=194)  2026 +0.010 (n=64)`, against `2026 -0.153 (n=21)` on "
                "09-04). All six pre-registered criteria hold for that ONE cell. The other two "
                "cuts still straddle zero (`cut when wrong sign                     -0.030   "
                "+0.050        [-0.017, +0.114]   +0.042      -12,222   262` and `cut when inside "
                "the flat band (+0.5 sigma)  -0.016   +0.063        [-0.019, +0.139]   +0.055    "
                "   -8,208   375`). It is still not a rule, for the reason it never was: the "
                "gain is bear-only, the leak guard confirms nothing outside the key changes "
                "(`non-bear changed    0   OK` on all three cuts), and cutting bear rows is "
                "bear_position_study's DEMOTE TO VETO arriving through a second door. The cut "
                "also loses dollars while gaining R, which is what a selection effect on a "
                "negative-expectancy structure looks like. ARM C is the arm that would have to "
                "separate it from the day-0 mark and it does not. The sensitivity is structural; "
                "there is no exit knob here.",
    ),

    "exit_from_text": Study(
        family="management", state="open",
        attention="2026-09-19: a CANDIDATE appeared where there had never been one — `E2 MECH "
                  "LVOL N=3`, all seven criteria true. By the registration an E2 clear is an "
                  "INTAKE proposal needing an independent window, never an exit rule and never "
                  "a ship, so this is a decision the operator has to take rather than a change "
                  "that has happened. Read the cell before deciding.",
        question="Do the model's OWN stated invalidation level, trigger condition and "
                 "horizon make better exits than the shipped mechanical profile — an "
                 "underlying-close stop at the invalidation level (E1), entering only "
                 "when the trigger was met (E2, a selection effect), and the emitted "
                 "horizon as the time exit (E3)?",
        verdict="There is a CANDIDATE for the first time, and it is an INTAKE cell, not an exit "
                "rule. On the 2026-09-19 suite run (sha 8e9b6a7, `book: 1325 rows  era=v4 ... "
                "n_dates=207`) the tally reads `tally: {'UNDERPOWERED': 293, "
                "'NOT A CRITERION (pooled)': 9, 'NULL': 21, 'CONTRARY': 11, 'CANDIDATE': 1}`, "
                "where 09-04 had no CANDIDATE and two SURVIVAL-ARTIFACT cells. THE CANDIDATE is "
                "`E2  MECH   LVOL                                  N=3               CANDIDATE`: "
                "`population 154 rows   affected 275 rows / 127 dates`, `shipped meanR  +0.107   "
                "variant meanR  +0.178   DeltaR  +0.071`, `1 CI95 (date-clustered, n=10000) "
                "[+0.011, +0.128]   PASS` and `criteria vector: 1_ci=T  2_loo=T  3_windows=T  "
                "4_years=T  5_tiers=T  6_power=T  7_no_N_flip=T`. E2 is entry filtering, so the "
                "registration's ceiling for it is an intake PROPOSAL behind an independent "
                "window — it can never ship as an exit rule and it does not ship as anything "
                "here. Read it beside `trigger_entry`, which prices the same idea properly and "
                "says LATE-ENTRY on every cell. The pooled `ALL ALL N=3` cell also went back to "
                "CANDIDATE (`4 years: 2024 +0.074 (n=95)  2025 +0.094 (n=79)  2026 +0.058 "
                "(n=27)   PASS`, having read `2026 -0.043 (n=11)   FAIL` on 09-04) and is "
                "labelled `NOT A CRITERION (pooled)`, so it contributes nothing. Two older "
                "readings must not be carried. The v3 `bear_put_spread` E1 re-read is still NULL "
                "at all three buffers, but NOT on the year any more: `population 426 rows`, and "
                "each buffer now fails criterion 1 with an interval that straddles zero, while "
                "2026 is POSITIVE at the 1% and 2% buffers (`2026 +0.031 (n=54)`, `2026 +0.051 "
                "(n=54)`). And E1's CONTRARY cells are 11 rather than 8 and are no longer all "
                "`bull_call_spread` / `LVOL` at a non-strike level: two are eq_strike cells "
                "(`CROSS  bull_put_spread|LVOL                  buf2%/eq_strike   CONTRARY` and "
                "`MECH   LVOL                                  buf2%/eq_strike   CONTRARY`). The "
                "text-derived stop still reliably CUTS winners where it fires. E3 still fails "
                "its survival control (`SURVIVAL CONTROL: FAIL`), and SURVIVAL-ARTIFACT has left "
                "the tally because the raw horizon table was never monotone on this book, so "
                "there is no monotone claim for the control to kill.",
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
        verdict="Every PRIMARY cell is UNDERPOWERED, on the 2026-09-19 suite run (sha 8e9b6a7, "
                "`book: 1325 rows`, PRIMARY `baseline book: 104 positions / 47 dates   max DD "
                "$-7,698 (-30.8% of capital)`) exactly as on 09-05 and exactly as the "
                "registration named IN ADVANCE. The VERDICT SUMMARY is unchanged word for word: "
                "`population: PRIMARY  (PRIMARY — the cut the verdicts are read from)` "
                "`ARM W/wf         UNDERPOWERED` `ARM W/prod       UNDERPOWERED` "
                "`ARM U/a          UNDERPOWERED` `ARM U/b          UNDERPOWERED` "
                "`ARM O/oi         UNDERPOWERED` `ARM O/vol        UNDERPOWERED` "
                "`ARM P/half       UNDERPOWERED` `ARM D/throttle   SECONDARY-UNDERPOWERED` "
                "`ARM W arm-level token: UNDERPOWERED` `PROD-ROBUST is NOT claimed — too few "
                "dates to say whether PROD survived.` `tally: {'UNDERPOWERED': 7, "
                "'SECONDARY-UNDERPOWERED': 1}`. Every PRIMARY cell fails G0 on the "
                "OOS-stitched population before any drawdown or ΔR clause is evaluated — the "
                "walk-forward split leaves too few TEST dates behind the burn-in to clear the "
                "25-date / 60-row floor at any arm: `ARM W/wf` "
                "reached `27 rows / 23 dates`, `ARM W/prod` (the PROD grid point itself) "
                "changed `0 rows / 0 dates` at all, and the densest cell, `ARM D/throttle`, "
                "reached 49 rows over 20 dates. The "
                "DISCLOSED SECONDARY CUT on the `all` population is printed beside it and "
                "carries NO verdict; its tally MOVED, because a third cell now clears G0: "
                "SECONDARY CUT `all` tally: "
                "{'UNDERPOWERED': 5, 'NULL': 2, 'SECONDARY-NULL': 1}   (DISCLOSED, carries no "
                "verdict). The three are `ARM O/vol` at `VERDICT: NULL` (`affected 89 rows / 67 "
                "dates`), the newly powered `ARM U/b` at `VERDICT: NULL` (`affected 62 rows / 50 "
                "dates`, `1 max DD improvement $+2,940 = +17.5% of the shipped drawdown` PASS "
                "but `2 paired DeltaR by date -0.008   CI95 [-0.059, +0.038]` FAIL), and the "
                "sizing arm `ARM D/throttle` at `VERDICT: SECONDARY-NULL` "
                "(`affected 101 rows / 48 dates`); the two cuts are never pooled and the `all` "
                "NULLs are not read as a finding. The v3 referent has GONE: this run prints "
                "`clause 5 referent: no exit_drawdown-cells-v3.json on disk (the v3 run has not "
                "been recorded)`, so every powered cell reads `5 SECONDARY v3: VACUOUS ... A "
                "CANDIDATE resting on it carries the annotation: v3 did NOT corroborate, it was "
                "not asked.   PASS`. Clause 5 is vacuous for the absent-file reason now, not "
                "because the v3 cell was itself UNDERPOWERED. Two findings from 09-05 are WEAKER "
                "on this book and should be requoted rather than repeated. The in-family best is "
                "less unstable: on PRIMARY `ARM O/oi` and `ARM D` are unanimous across blocks "
                "(`selection tally: {'X 0.40': 4}`, `selection tally: {'d 0.10': 4}`) and only "
                "`ARM W/wf` and `ARM U` re-pick, while on the `all` cut the split survives "
                "(`selection tally: {'X 0.25': 4, 'X 0.40': 5}`). And the in-sample DISCLOSURE "
                "block, which sizes the tuning bias every earlier in-sample exit read carried, "
                "now spans $-4,531 to $-7,314 against a shipped $-7,698 on PRIMARY and $-10,603 "
                "to $-16,674 against $-16,758 on the `all` cut — no criterion is evaluated from "
                "it. The baseline basis line still reads "
                "`base -> BEAR_HE (the bear-debit be_after block is DISABLED in "
                "config/backtest.yml, so no breakeven stop is merged)`, and G-CAL still passes "
                "with account_sim's `GATES: ALL PASS` run in-process. The two-analyst grading on "
                "disk is the 2026-09-05 one and has NOT been redone for this run. Nothing ships "
                "from this "
                "study under any outcome, and per the registration's anti-tuning clause the "
                "grid is not re-cut for these dates: a CANDIDATE would still need an "
                "independent window, and an UNDERPOWERED cell publishes its census and stops. "
                "The registration is the whole authority: the build-time readings recorded "
                "while the module was written were folded into it on 2026-09-08, each tagged "
                "`Resolved at build` beside the text it amends, so a reader can tell a ruling "
                "taken during the build from a commitment made before it. study_review grades "
                "against that one file.",
    ),
    "staged_exit": Study(
        family="management", state="open",
        question="Does a time-STAGED exit — evaluate ONCE at fixed session X on P&L vs the "
                 "original entry, then exit / tighten / arm a trail — work where the "
                 "reactive drawdown-from-peak rules of Attempts 1/2/10 did not?",
        verdict="NULL in substance on both arms — on era v3 (2026-08-19, 795/118) and again on "
                "the 2026-09-19 suite run (sha 8e9b6a7, `book: 1325 rows  era=v4`), the "
                "best-powered "
                "run yet: `54 of 96 cells clear the floor; 42 are UNDERPOWERED.` — `tally: "
                "{'UNDERPOWERED': 42, '-': 54}` — and not ONE powered cell reaches CANDIDATE or "
                "REACTIVE-AGAIN. Know the report's vocabulary before quoting it: a cell that fails "
                "criterion 1 carries no verdict word and prints as a bare `-`, while `NULL` is "
                "reserved for a cell that clears the CI and then fails a stability check, and this "
                "run has none of the latter either — no powered cell passes criterion 1 at all. "
                "What the extra power bought is the opposite of "
                "a candidate — EIGHT cells now have a CI excluding zero, two more than on 09-04, "
                "and all eight are HARMFUL: ARM "
                "E X=5 (R <= -0.25 -> exit now) at `DeltaR  -0.042` / `1 CI95 (date-clustered, "
                "n=10000) [-0.070, -0.015]   FAIL`; ARM E X=5 (R <= -0.50) `[-0.048, -0.008]`; "
                "ARM E X=20 (R >= +0.50) `[-0.025, -0.001]`; ARM E X=20 (R >= +0.25) `[-0.042, "
                "-0.003]`; ARM T X=5 (R <= -0.25 -> tighten the stop to -0.40) `[-0.065, "
                "-0.012]`; ARM T X=5 (R <= -0.50 -> tighten) `[-0.048, -0.008]`; ARM T X=20 "
                "(R >= +0.25 -> arm the 0.50/0.50 trail) `[-0.044, -0.010]`; ARM T X=20 ($ >= "
                "+250 -> arm the trail) `[-0.032, -0.001]`. One cell left that list rather than "
                "joining it — ARM E X=15 (R >= +0.25) went from `[-0.046, -0.001]` to `[-0.035, "
                "+0.006]` — so the membership is not stable even while the direction is. The "
                "guards hold (`G1: PASS`, `G-FORK: PASS`), so this is a power "
                "result and not a plumbing one. The Attempt-1/2/10 null extends to scheduled "
                "switches, and the scheduled switch has a measured cost rather than merely no "
                "gain.",
    ),

    # ③ structure
    "bear_rewrap": Study(
        family="structure", state="null",
        question="A bear SPREAD sells the lower put, giving away the vol expansion that makes "
                 "a bear position pay. What if the short leg goes?",
        verdict="The two naive re-wraps are dead and the DIAGONAL is a candidate that keeps "
                "failing the year. On the 2026-09-19 suite run (sha 8e9b6a7), whose report is "
                "identical to the 09-19 17:28 one bar its timestamp: `bear debit rows: 483  "
                "(Counter({'tweak': 260, 'real': 223}))`, `reconstructed                483  "
                "(100.0%)`. `long_put` `dR -0.022 CI [-0.085, +0.040]` and `wider` `dR -0.064 CI "
                "[-0.139, +0.016]` are 0 of 5 criteria each. `long_diag` is 4 of 5, losing only "
                "the year: `[PASS] CI excludes zero          dR +0.159 CI [+0.035, +0.288]`, "
                "`[PASS] every LOO fold positive  MIN +0.134 over 156 folds (share+ 100%)`, "
                "`[PASS] both ex-window cuts       ex_2025_mar_apr +0.171  ex_2026_feb_apr "
                "+0.182`, `[PASS] right-signed both tiers   real n=112 dR +0.183 d$ +26,569  "
                "tweak n=149 dR +0.142 d$ +22,840`, against `[FAIL] sign-stable every year    "
                "2024 +0.220  2025 +0.153  2026 -0.069`. ARM P has REVERSED since 2026-09-04, "
                "when both portfolio checks read MET for the first time: now `P1 worst-decile: n= "
                "21  meanR +0.196  CI [-0.212, +0.547]  $+4,897   -> not met` and only `P2 "
                "correlation with deployed sleeve: -0.230 over 129 shared dates   -> MET`. So the "
                "candidate has now failed its year criterion on two consecutive exports and lost "
                "the portfolio support it briefly had — neither a ship nor a refutation. One "
                "thing bounds the reading: the YEAR clause is what tests 2026 here and the WINDOW "
                "cut is not, since `ex_2026_feb_apr` drops little (`ALL              n= 261  dR "
                "+0.159` against `ex_2026_feb_apr  n= 236  dR +0.182`), "
                "so a passing ex-2026 cut says nothing about the year. Still a candidate for an "
                "independent window, on a population bear_position_study says to VETO. Nothing "
                "changes in config/backtest.yml.",
    ),

    "financed_spread": Study(
        family="structure", state="open",
        question="Does financing a book debit vertical with a credit position pay — an "
                 "opposite-delta credit spread, a naked short leg, or a same-direction "
                 "credit vertical?",
        verdict="Nothing ships, and the RE-WRAP token has MOVED. On the 2026-09-19 suite run (sha "
                "8e9b6a7; `era v4   book 1325 rows / 207 dates   2024-01-10 .. 2026-05-07`, "
                "`kept 920  (bull 447 / bear 473)   of 1325 book rows`) every cell is `NULL` "
                "except one — and it is no longer `F3 off1`, which held the token on 2026-09-04 "
                "and now reads `F3 off1          NULL`. The cell that prints it is `F4-d20 $100  "
                "    RE-WRAP`, the diagonal at the |delta| 0.20 target closed at $100: it clears "
                "six of seven — `[PASS] 1 paired dR > 0, CI excludes zero        dR +0.369  CI "
                "[+0.019, +0.985]`, `[PASS] 2 every LOO fold positive                MIN +0.109 "
                "over 91 folds (share+ 100%)`, `[PASS] 3 window cuts + ex-BOTH                  "
                "ex_2025_mar_apr +0.384  ex_2026_feb_apr +0.367  ex_BOTH +0.383`, `[PASS] 4 "
                "sign-stable every year                 2024 +0.058  2025 +0.129  2026 +3.590`, "
                "`[PASS] 5 right-signed both pricing tiers        real n=35 dR +0.804  tweak n=79 "
                "dR +0.176`, `[PASS] 6 >= 25 affected dates (priced set)      91 dates` — and "
                "fails only the diversification test, `[FAIL] 7 E3 <= 0 (does not re-wrap the "
                "sleeve)  corr +0.180 over 83 shared dates`. That IS the token's registered "
                "meaning (`RE-WRAP        clears 1-6, fails 7 — the financing does not "
                "diversify`): a real gain that is the same exposure again, which the study is "
                "built to refuse. Two things bound it, and both cut harder than for the cell it "
                "replaced. Its criterion 4 passes on a 2026 term of `+3.590` — an order of "
                "magnitude above the other two years, on the thinnest leg of the book, so the "
                "year vector is sign-stable without being stable. And it is built from only 114 "
                "of 920 candidates (`F4-d20 $100      candidates  920  built  114`, "
                "`target_unreachable  440`), so the cell is a narrow and self-selected slice. "
                "Unlike `F3 off1` on 09-04, its FIXED-CONTRACTS control does NOT separate — `n= "
                "114   dR +0.369   CI [+0.019, +0.985]`, identical to the PROD-sized read — so "
                "the gain here is not contract sizing. Everything else is NULL, including "
                "`F2 off1`, still significantly HARMFUL and still labelled NULL because only a "
                "positive cell can be a candidate in this grammar.",
    ),

    "ladder_overlay": Study(
        family="structure", state="null",
        question="Does selling a shorter-dated short call against a long-dated bull call "
                 "spread — and rolling that short call as each one expires — beat simply "
                 "running the spread to the shipped §5 exits, and would a naked put beat "
                 "both?",
        verdict="No. Every graded cell prints `NULL`, unchanged across the 2026-09-10, 09-16 and "
                "2026-09-19 runs (latest the suite run at sha 8e9b6a7, `kept 447 cores of 447 "
                "bull_call_spread "
                "rows, out of 1325 book rows`). Selling the call at entry loses to the plain "
                "spread with the CI clear of zero: `L-T0` `PAIRED       n=  93 /  71 dates   ΔR "
                "-0.255   CI [-0.528, -0.011]`, `L-T0-TEF` `PAIRED       n=  93 /  71 dates   ΔR "
                "-0.310   CI [-0.591, -0.053]`. The trigger cells are positive but inside their "
                "intervals and re-wrap the deployed exposure: `L-GAP` `PAIRED       n= 199 / 122 "
                "dates   ΔR +0.078   CI [-0.012, +0.168]` with E3 `+0.378`, `L-RUN` `PAIRED       "
                "n= 205 / 121 dates   ΔR +0.045   CI [-0.048, +0.135]` with E3 `+0.258`. Neither "
                "naked put helps: `N-CORE` `PAIRED       n= 447 / 165 dates   ΔR -0.021   CI "
                "[-0.184, +0.141]`, `N-ROLL` `PAIRED       n= 360 / 154 dates   ΔR -0.007   CI "
                "[-0.157, +0.144]`. The v3 companion (2026-09-16, "
                "`ladder_overlay-v3-2026-09-16.txt`, not re-run since) prints `NULL` on seven "
                "cells and `UNDERPOWERED` on three — `L-F4`, `L-T0` and `L-T0-TEF`; its `N-ROLL` "
                "is `PAIRED       n= 124 /  69 "
                "dates   ΔR -0.274   CI [-0.478, -0.073]`. Nothing ships; the thread re-opens "
                "only on genuinely new dates.",
        attention="2026-09-16 CLOSED. Three build rulings folded into the registration "
                  "(NULL is the default token; E1/E2 read at the first sale day for trigger "
                  "cells; G1b's non-shared row categories). `S-D30` and `S-DTE60` UNDERPOWERED "
                  "on both eras.",
    ),

    # ④ deployment
    "account_sim": Study(
        family="deployment", state="open",
        question="The ladder assumes infinite capital. Does a real $25,000 account — paying "
                 "for positions, holding reserve, respecting a delta cap — still produce a book?",
        verdict="The edge survives the caps; the DRAWDOWN does not. The verdict MOVED on the "
                "2026-09-19 suite run (sha 8e9b6a7, `deployed signal dates: 174  (2024-01-10 .. "
                "2026-04-16)`, PRIMARY `total: 5 episodes, 127 dates, 320 deployed picks`): where "
                "2026-09-04 printed `>>> FEASIBLE <<<`, this run prints `>>> NOT FEASIBLE AT "
                "$25,000 — BLOWUP RISK (A1 holds, A3 fails) <<<`. Feasibility only — nothing ships "
                "from this study under any outcome. Two lines decide it: `A1 EDGE SURVIVAL  meanR "
                "+0.277  CI95 [+0.150,+0.395]  years 2024:+0.229  2025:+0.336` -> `MET`, and `A3 "
                "NO BLOWUP      maxDD $-8,755 = 35.0% of capital;  ledger violations 0` -> `NOT "
                "MET` against the registered 25% bar, where 09-04 read `maxDD $-3,750 = 15.0% of "
                "capital`. A2, A4, A5 and A6 still print `MET` and the gates still print `GATES: "
                "ALL PASS` (G2-G5), so this is a drawdown result rather than a plumbing one, and "
                "the label itself is the 2026-08-14 amendment's mapping of A1-holds/A3-fails, not "
                "a new criterion. The configured cell is `n=211  dates=107  $28,049  meanR "
                "+0.277`. The drawdown sits in a Jan-Apr 2025 cluster of one-contract bull call "
                "spreads, peak 2025-01-10 to trough 2025-04-09 — not in the March 2026 sessions "
                "the re-priced book added. The SECONDARY full book moved the OTHER way and now "
                "fails one criterion instead of two: `A1 EDGE SURVIVAL  meanR +0.214  CI95 "
                "[+0.105,+0.321]  years 2024:+0.206  2025:+0.269  2026:+0.024` -> `MET` (09-04 had "
                "it failing on a 2026 term of -0.062), leaving `A3 NO BLOWUP      maxDD $-10,210 = "
                "40.8% of capital;  ledger violations 0` -> `NOT MET`. No verdict reads from that "
                "population by registration, and PRIMARY still stops at `E5  2025-04-23 .. "
                "2025-09-26    37 dates over 112 sessions    99 deployed picks`, so its A1 still "
                "has no 2026 term. The POST-HOC compounding arm "
                "(account_sim-compounding-latest.txt, its own page) prints the same banner on `A3 "
                "NO BLOWUP      maxDD $-8,550 = 34.2% of capital;  ledger violations 0`, and now "
                "fails A5 too (`constrained/B2 ratio ALL 204% (n=253);  ex-2025_mar_apr 235% "
                "(+31pt, n=247)  ex-2026_feb_apr 204% (+0pt, n=253)`) — which its own warning "
                "paragraph says to discount, because under compounding A2 and A5 are ratios "
                "against a benchmark that is itself compounded.",
    ),
    "selection_order": Study(
        family="deployment", state="null",
        question="On v3, account_sim's rejected picks out-earned its taken ones — a read that "
                 "REVERSES on v4 (see the account_sim entry), so the premise this study was "
                 "registered under no longer holds on the current era. The pre-registered "
                 "question stands on its own: does a different BLIND entry-side ORDER of the "
                 "same candidate set spend the scarce delta budget better — or was that read "
                 "an artifact?",
        verdict="ORDERING-IS-NOISE, unchanged on the 2026-09-19 suite run (sha 8e9b6a7, "
                "`PRIMARY   dense episodes: 5 episodes, 127 dates`) — thread CLOSED. G0 clears "
                "more comfortably than it did on 09-04, with the census moving to `O1                 "
                "48             42         20%   ok`, `O2                 41             "
                "34         16%   ok`, `O3                 46             41         19%   ok`, "
                "`O1b                49             46         22%   ok` against the pre-declared "
                "floor of 25 affected dates, and then nothing clears the bar: `VERDICT: "
                "ORDERING-IS-NOISE — no arm separates from the O4 band. The adverse-ordering read "
                "from account_sim was an ARTIFACT of which picks the cap happened to exclude. "
                "Record it and CLOSE the thread.` Every arm sits inside the seeded random-order "
                "band — the best-placed is `(7) O4 band p95 +0.0292 (seed 20260814, 200 draws); "
                "this arm +0.0026 sits at pct 80%  -> FAIL`. The 2026 dates change nothing here "
                "and cannot: the PRIMARY dense episodes span two calendar years, so its "
                "criterion-4 line has no 2026 term at all, and on the SECONDARY full book 2026 is "
                "`(n=5)` dates for every arm — every arm fails criterion 4 on that population "
                "with or without it. "
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
        verdict="The NOISE banner is GONE and the thread re-opens. On the 2026-09-19 suite run "
                "(sha 8e9b6a7) the report prints `>>> RESTATEMENT — K 5 / "
                "same-direction-and-sector clears X2 and X3 but loses the gain under the delta "
                "control (X7). It is a restatement of portfolio_delta's ARM B / ARM D and does "
                "not ship. <<<` where 09-04 printed NOISE over all eleven powered arms. Nothing "
                "ships either way: `arms run (PRIMARY): 13   powered past X1: 12   clearing "
                "X2/X3/X6/X7: 0`. PRIMARY = `5 episodes, 127 dates` (`positions 320   dates 127   "
                "2024-01-10 .. 2025-09-26`); SECONDARY = the full `174 dates` book (`positions "
                "417   dates 174   2024-01-10 .. 2026-04-16`). The one arm that moved is `K 5 / "
                "same-direction-and-sector gain +0.0663 R   criteria met 236-`: it clears `X2 "
                "GAIN` at `paired mean gain +0.0663 R   CI95 [+0.0116, +0.1232]`, `X3 NOT NOISE` "
                "at `pct 98%` of ARM N's band, and `X6 LEAVE-ONE-OUT` at `MIN +0.0551`, then "
                "fails the delta control — `X7 NOT A DELTA CEILING: 1 readable bands   [2.0,inf) "
                "+0.0696` with `NOT DISCRIMINATING — one readable band is the whole sample "
                "re-labelled.` So the arm is not refuted; it is unseparable from a net-delta "
                "ceiling, which is `portfolio_delta`'s question. `K 3 / same-underlying` crossed "
                "its power floor (`gain +0.0141 R   criteria met ----`) and `K 5 / "
                "same-underlying        UNDERPOWERED (11 moved dates, 11 moved positions)` did "
                "not; ARM CK is still `NOT RUN. The registration runs ARM CK only if ARM C and "
                "ARM K each clear their criteria independently.` Three things the run establishes "
                "rather than assumes: the book is long-only (`direction signs in the book: {1: "
                "417}`, `positions whose same-direction count EQUALS their open count: 417 of "
                "417`), so ARM K / same-direction is ARM C on a different grid and is excluded "
                "from the conjunction; X7's control barely discriminates, at `X7 control — dates "
                "by |net delta-notional| / capital band at session open: [0.0,0.5) 3  [0.5,1.0) "
                "1  [1.0,2.0) 13  [2.0,inf) 110`; and ARM D0's DESCRIPTIVE shape is not flat "
                "(mean R `[0,3)          150    103   +0.3631` down to `[6,10)          91     "
                "69   -0.0540` by same-direction-and-sector count on SECONDARY) but is registered "
                "descriptive-only. X4 (era stability) is UNSETTLED AGAIN, and the 2026-09-04 "
                "settlement is withdrawn: it rested on no arm clearing X2 and X3 in either era, "
                "which is no longer true of v4. The registration's rule is printed in the run — "
                "`X4 is settled by reading the two reports side by side: same sign, both clearing "
                "X2 and X3, and point estimates within 0.15 R. Until that is done, no arm from "
                "this study is ADOPT-eligible.` — and there is no `--era v3` report on disk to "
                "read beside this one; the 09-04 v3 section in "
                "research/study-results/f4_deployment/concurrency_correlation.md was paired with "
                "a v4 report that has since been overwritten. Settling X4 needs a fresh `--era "
                "v3` companion. Nothing is ADOPT-eligible meanwhile, because X4 caps every arm at "
                "CANDIDATE-PENDING-X4. Twenty-two NOT PRE-REGISTERED choices are disclosed in the "
                "report's own block.",
    ),

    "portfolio_delta": Study(
        family="deployment", state="null",
        question="Is there an optimal PORTFOLIO net delta to keep? account_sim showed "
                 "delta-notional binds before cash; this asks whether the level itself is "
                 "a lever — dose-response, a ceiling band, and a delta-TARGETED hedge "
                 "sleeve, against a seeded random-admission null band.",
        verdict="The candidate is GONE. On the 2026-09-19 suite run (sha 8e9b6a7, `deployed picks "
                "417 over 174 dates  (2024-01-10 .. 2026-04-16)`, `PRIMARY   dense episodes: 5 "
                "episodes, 127 dates`) the label moved from CANDIDATE-FOR-INDEPENDENT-WINDOW to "
                "`>>> NOISE — no arm exceeds ARM N's 95th percentile and ARM D's bands do not "
                "separate within their cells. Recorded; thread closed for these dates. <<<`, on "
                "`arms clearing the whole bar:  none`. The word CANDIDATE is not printed anywhere "
                "in the report. `B ceiling 1.00` lost criterion 1 and nothing else: `(1) paired "
                "mean gain +0.0519 R   CI95 [-0.0333, +0.1407] (date-clustered, BOOT_N=10000)  -> "
                "FAIL` -> `=> B ceiling 1.00: FAILS c1`, where 09-04 read `+0.1081 R   CI95 "
                "[+0.0131, +0.2205]` and PASSED. Six of its seven parts still pass, criterion 7 "
                "among them (`ARM N band p95 +0.0275 (seed 20260819, 200 draws); this arm +0.0519 "
                "sits at pct 100%  -> PASS`), which is why the report's QUALIFICATION paragraph "
                "now names TWO arms as clearing (7) and then failing the conjunction. Read the "
                "size of the move before reading the label: the point estimate halved on a book "
                "that grew from 88 to 127 PRIMARY dates, so this is a weaker effect on more "
                "data rather than a power loss. `B ceiling 1.50` still `FAILS c1` on PRIMARY at "
                "`+0.0481 R   CI95 [-0.0205, +0.1175]`; on the SECONDARY full book it now PASSES "
                "c1 at `+0.0661 R   CI95 [+0.0161, +0.1181]` and fails only c4, on a much milder "
                "2026 term — `(4) by year: 2024 +0.0801 (n=55)  2025 +0.0764 (n=51)  2026 -0.0147 "
                "(n=16)  -> FAIL`. ARM D's PRIMARY shape is no longer even readable: `SHAPE: NOT "
                "READABLE — too few n-sufficient bands to call the relationship` monotone, flat "
                "or non-monotone, on `readable bands (n >= 20): [1.0,2.0), [2.0,inf)`; the "
                "`SHAPE: NON-MONOTONE / FLAT  (descriptive — NOT A CRITERION, and no band value "
                "may be adopted on it)` line is now the SECONDARY one. Nothing ships under any "
                "outcome and no ceiling value may be adopted on its P&L. The independent-window "
                "queue item this study fed comes off.",
    ),

    # ⑤ hedging
    "hedge_sizing": Study(
        family="hedging", state="shipped",
        attention="2026-08-24 grading PULLED the §4 closer-to-money pick line and "
                  "relabelled the hedge sleeve operator-policy — read the digest and "
                  "validator memo, and confirm the operator pre-commitment wording in "
                  "research/pre-registrations/f5_hedging/hedge_sizing.md says what you meant.",
        question="Bear selection is unfixable — but is bear worth holding as a HEDGE? Four "
                 "estimands: D1 joint selection×exit, D2 hedge contribution, D3 sizing, "
                 "D4 conditional pick.",
        verdict="The hedge case is still NOT MET and D1 has MOVED. On the 2026-09-19 suite run "
                "(sha 8e9b6a7, `book 1325 priced rows / 207 dates`, `bear 485 rows / 199 dates`, "
                "`deployed ladder sleeve 417 rows / 174 dates (top-3/day, tiers A/B)`) the block "
                "reads `D1 joint selection x exit : candidate(s) found — 4`, `D2 hedge is real   "
                "       : NOT MET`, `D3 always-on sizing       : NOT MET at any size`, `D4 "
                "conditional pick       : NOT MET`, `D5 gated sleeve (POST-HOC): 2 candidate "
                "gate(s)`. Read D1's four survivors against the report's own chance line before "
                "reading them as selection: `survivors of the pre-registered D1 rule: 4  (~11.8 "
                "expected by chance)`, so four out of 496 combinations is FEWER than chance "
                "predicts and the count argues nothing. They are also two cells counted twice — "
                "`mech_cell=LVOL AND model_vol=E-VOL` and `model_vol=E-VOL AND mech_vol=L-VOL` "
                "print identical rows, as do the two `|delta|<=0.20` pairs. D2 fails on a "
                "DIFFERENT clause than it did on 09-04, and the two swapped: the worst-decile "
                "condition now fails at `bear R on deployed worst-decile dates: -0.067 (row-level "
                "CI [-0.296, +0.318], n=41) — needs > 0: NO` while the year check it used to fail "
                "now passes at `tail positive in 2/3 evaluable years — needs >= 2: YES`, "
                "alongside `sleeve correlation -0.160 — needs < 0: YES`. D4 still loses the "
                "shipped ranker outright — `rankers tested: 10  adopted: 0  (~0.5 expected by "
                "chance)`. The largest gain is no longer the closer-to-money pick: `iv_pct high "
                "first           149   +0.048   -0.032   +0.080 [-0.025, +0.186]    +0.065` now "
                "leads `|delta| low first             152   +0.025   -0.035   +0.060 [-0.046, "
                "+0.169]    +0.041`. Both CIs span zero and neither is adopted, so nothing here "
                "contradicts the §4 far-OTM prohibition. D5 is POST-HOC and still narrows to two "
                "gates, the same cell at two sizes, but they have REVERSED in dollars: `mech vol "
                "H-VOL             f=0.50  Δtotal -1,247  ΔDD +310` and `mech vol H-VOL          "
                "   f=1.00  Δtotal -2,494  ΔDD +218` — they leave drawdown and worst date "
                "unharmed and now COST total, where 09-04 read `Δtotal +505` and `+253`. The "
                "report's reproduction check puts the whole gain in one year (`2024: n=  3  "
                "sleeve $      828  mean $     276`, `2025: n= 13  sleeve $     -488`, `2026: n= "
                "10  sleeve $   -1,587`) under its own printed caveat, `A gate that only pays in "
                "one year is the Mar-Apr-2025 failure again.` The §4 pick line stays PULLED and "
                "the sleeve stays operator policy (docs/deployment-rules.md §4), not a v4 "
                "evidence claim; the v3 D2 MET / D4 ADOPTED read is recorded in "
                "research/deployment-evidence.md.",
    ),

    "hedge_structure": Study(
        family="hedging", state="open",
        question="Re-derive that one survivor under a pre-registered pick rule and a strict "
                 "fill rule.",
        verdict="Gates pass; the primary stays unreadable; the FILL RATE is what binds. The "
                "2026-09-19 suite run (sha 8e9b6a7) reproduces the 17:26 run of the same evening "
                "figure for figure, and that pair is the first read since 2026-09-08 — the study "
                "was "
                "BLOCKED at R2 for eleven days on one row, HYG 2025-04-09, whose stored proxy "
                "entry had been fabricated into a credit by the liquidation mark. Re-pricing that "
                "row and fixing two drifts in `bear_rewrap`'s mirror (it DERIVED the entry day "
                "from a cache that had grown since, instead of reading the recorded `dte_entry`; "
                "and it applied `_zero_bid_mark` at entry after 09aa02c displaced it there) "
                "cleared it: `reconstructs: 1322 / 1322  (100.0%)` -> `R2 PASS`. Other gates: "
                "`debit_calib      n=461  exact=438  near-rounding-tie=1  superseded-basis=21  "
                "hard=0`, `deployed: 417 positions over 174 dates, $74,036   meanR +0.198  win "
                "61%`, `R4 PASS — the two constructions agree row for row`. The VERDICT block is "
                "unchanged — `H0 FILL           NOT MET`, `H2 (primary)      NOT EVALUABLE` — and "
                "the fill rate got WORSE on the bigger book: `P1 fillable on deployed dates      "
                "    58 / 174  =  33.3%   FAIL` and `P1 fillable on worst-decile dates       2 / "
                "17   =  11.8%   FAIL` (51.0% and 28.6% on 09-04). H2 reads what it can: (a) "
                "`corr(daily $)       -0.042  CI95 [-0.147, +0.061]   over 174 deployed dates "
                "(unfillable carried at 0)`; (b) `n=2  meanR -0.404` -> `UNDERPOWERED — n < 10`; "
                "(c) `tail positive in 1/3 evaluable years — needs >= 2: NO`. H3 is the line to "
                "handle carefully: both baselines read `-> DEPLOYABLE at f = 1.00`. That is the "
                "FOURTH consecutive export on which H3 has moved — NOT MET, DEPLOYABLE f=1.00, "
                "NOT MET, DEPLOYABLE f=1.00 — so it is an UNSTABLE MEASUREMENT, not a verdict, "
                "and none of the four is evidence. H4's paired read is `n=58 dates  dR -0.122  CI "
                "[-0.371, +0.048]`. H5 is labelled POST-HOC and its BEAR_HE cell is `8   +0.669    "
                "+0.266            [-1.114, +2.863]`, an interval that spans everything. Blocked "
                "on dates, not refuted.",
    ),

    "hedge_timing": Study(
        family="hedging", state="open",
        question="The bear hedge sleeve is deployed on discretionary triggers — chop, a SPY "
                 "gap-up, a 4-5-day SPY down-run. Does any of them, made mechanical, pick a "
                 "day on which the hedge earns more than the SAME day's ladder-eligible long?",
        verdict="The §4 gap-up prohibition now rests on the PRIMARY arm ALONE: its between-date "
                "mirror moved back to NULL because the beta control absorbed it. On the "
                "2026-09-19 suite run (sha 8e9b6a7, `era v4   book 1325 priced rows / 207 dates`, "
                "`bear sleeve 483 rows / 199 dates`, `deployed ladder 417 rows / 174 dates`) the "
                "headline holds at `TIMING-CANDIDATE survivors: 0  (~0.45 expected by chance at "
                "5%)`, and `hedge_timing ARM H3-GAP` is if anything firmer: `HEADLINE difference "
                "-0.510  CI95 [-0.820, -0.190]` -> `VERDICT H3-GAP: CONTRARY`, with its year "
                "vector, both window cuts and `LOO    min -0.561  share 0.00 over 39 folds` all "
                "`-> OK`. Two arms moved around it. `hedge_timing ARM H1-GAP` went CONTRARY back "
                "to `VERDICT H1-GAP: NULL` — its own interval now spans zero at `trigger -0.269 "
                "(n=48 dates)   non-trigger -0.078 (n=151 dates)   delta -0.191` / `CI95 "
                "(date-clustered, between) [-0.399, +0.023]`, AND the registered mirror rule "
                "fires: `h2_mirrors = True  (|H2 delta| >= 0.5 x |H1 delta|, opposite-signed)` -> "
                "`-> ARM H1-GAP re-read as NULL`. It fires because `hedge_timing ARM H2-GAP`, the "
                "beta control, went NULL to `VERDICT H2-GAP: TIMING-CANDIDATE   (control, not a "
                "headline)` on `trigger +0.407 (n=42 dates)   non-trigger +0.110 (n=132 dates)   "
                "delta +0.297` / `CI95 (date-clustered, between) [+0.064, +0.522]`: the DEPLOYED "
                "LADDER does better on gap-up days, so the bear sleeve's between-date "
                "underperformance there is directional beta rather than hedge timing. H2-GAP is a "
                "control and is excluded from the survivor count. Counting three v4 runs, H1-GAP "
                "has read NULL, CONTRARY, NULL while H3-GAP has read CONTRARY every time — so "
                "quote H3-GAP and stop. The dollars arm is unchanged at `criteria  unharmed=F "
                "sign=- loo_all_same_sign=T years_ok=T cuts_ok=F` -> `VERDICT H4-GAP: NULL`, and "
                "CHOP and DECLINE-BROAD stay `VERDICT H4-CHOP: NULL` and `VERDICT H4-DECLINE: "
                "NULL`. The operator's own 4-5-day streak stays UNDERPOWERED exactly as fixed in "
                "advance by the registration: `CENSUS [DECLINE-STRICT N=4 (verdict FIXED IN "
                "ADVANCE: UNDERPOWERED)]: n_rows=18  n_dates=6  floor=25 dates  -> UNDERPOWERED  "
                "bear-carrying=6  H3-paired=6` and the N=5 census at `n_rows=7  n_dates=2`. No "
                "direction is ever quoted from those. One report defect to know about: the "
                "paragraph under that census still says the book samples 2 strict-streak dates, "
                "which now matches the N=5 row rather than the N=4 one. Nothing ships; the "
                "prohibition is HELD for the operator per the registration, and the forward "
                "trigger is unchanged: >=25 strict-streak dates or >=25 post-2025-11-04 dates.",
    ),

    "hedge_portfolio": Study(
        family="hedging", state="open",
        question="When the open book is CONCENTRATED in one correlated cluster, does adding "
                 "a long put on that cluster's proxy reduce the book's MARK-TO-MARKET "
                 "drawdown, versus carrying the same concentrated book unhedged?",
        verdict="UNDERPOWERED (the mechanism question) and MEASUREMENT-ONLY (ARM M) — two words "
                "over two different objects, both emitted, neither ordered ahead of the other, and "
                "both unchanged on the 2026-09-19 suite run (sha 8e9b6a7). The population deadlock "
                "recorded as ERRATUM 1 was RATIFIED by the operator on 2026-08-31 "
                "(research/pre-registrations/f5_hedging/hedge_portfolio.md, Population and "
                "basis, consolidated there 2026-09-02): the population is the literal "
                "load_book(include_bs=False) call, because a strike_expiry_tweak row is a REAL "
                "Barchart price for a nearby strike and an operator who does not follow a proposed "
                "leg exactly is modelled better by a book that admits the substitution. `real` is "
                "kept as a REPORTED STRATUM, never a co-primary. On the ratified population — "
                "`population all — the literal load_book(include_bs=False) call (real + tweak)`, "
                "`1325 rows / 207 signal dates` — it still reads `powered POOLED cells 0   POOLED "
                "cell words: UNDERPOWERED 9`, so `VERDICT — the mechanism question, over the hedge "
                "cells: UNDERPOWERED` and NO DIRECTION is quoted from any cell. Reported rather "
                "than read, and now on its second run: the `real` stratum is past its power floor "
                "at `598 rows / 193 signal dates`, `powered POOLED cells 9   "
                "POOLED cell words: NULL 9`, with `DIRECT cell words: NULL 9` (it read `NULL 3  "
                "UNDERPOWERED 6` on 09-04) and "
                "`CONSTITUENT cell words: UNDERPOWERED 9`. That is the only powered hedge-cell "
                "reading this study has ever produced and it is a NULL — but the stratum is marked "
                "`REPORTED STRATUM — not a co-primary; no verdict is read from it`, so it changes "
                "no verdict here and may not be promoted into one. ARM M is not power-gated and is "
                "the sharper result, and its GAP SHRANK: `ARM M curve gap: maxDD $-7,541   ulcer "
                "+5.00 pts   TUW +3.5 pts   (differ materially: YES)`, i.e. `the close-bucketed "
                "curve UNDERSTATES this "
                "book's max drawdown by 27.0%.` against 40.2% on 09-04 — hence `VERDICT — ARM M, "
                "the measurement, which "
                "is not power-gated: MEASUREMENT-ONLY`. Nothing ships. UNDERPOWERED leaves the "
                "queued max-drawdown question OPEN rather than closing it. hedge_sizing D3, "
                "hedge_structure H3 and hedge_timing H4 all STAND — but they were read on the "
                "close-bucketed curve, which understates this book's drawdown by 27%, and that is "
                "now a known limitation of theirs. The two readings are also a warning against "
                "carrying either percentage as a constant: the gap is a property of the book on "
                "the day it was measured. ERRATUM 2 stands too: `hedge_portfolio ARM P` is "
                "INERT AS REGISTERED and has not been redefined, so the binding prose rule is "
                "unreachable; `hedge_portfolio ARM RF` prints as UNREGISTERED — ADDED AFTER COMMIT "
                "and no clause reads it. Read with the ratification's own limitation: the "
                "registration's PLAN-TIME observations (exposure table, concentration quantiles, "
                "504-session universe) describe the `real` stratum and are NOT disclosures about "
                "the ratified book — the figures that describe it are the ones the run prints. "
                "TWO ARMS SINCE 2026-09-07, and the verdict above is the WHOLE-BOOK one. `hedge_concentration` "
                "was merged in as this module's `--admitted` arm and deleted; it files as `hedge_portfolio-admitted` "
                "and asks the same question on the ADMITTED book — what account_sim actually takes under the "
                "top-3-per-day rule and the exposure caps. Its own two-stage verdict is unchanged by the merge "
                "and the report reconciles byte-identical: `VERDICT — Stage 1 (ARM K, the precondition): "
                "PRECONDITION-NULL` and `VERDICT — Stage 2 (ARM C, the mechanism): NOT RUN (Stage 1 "
                "PRECONDITION-NULL)`, a POWERED refusal (`G-POWER-K: PASS`) rather than a power stop. The two "
                "arms carry SEPARATE verdict vocabularies on purpose — a merged verdict would be a new claim — "
                "and neither overrides the other: UNDERPOWERED here describes the every-row book, "
                "PRECONDITION-NULL there describes the book the operator runs. The deleted module's full "
                "verdict is quoted verbatim in research/study-map.md and its frozen per-era print stands at "
                "git history (44bbfb2), its record having been deleted 2026-09-08.",
        attention="ARM M's MEASUREMENT-ONLY finding is now RECORDED (2026-08-31): "
                  "research/deployment-evidence.md gained a section qualifying the "
                  "measurement basis of hedge_sizing D3, hedge_structure H3 and hedge_timing "
                  "ARM H4 — none overturned, no figure of theirs restated, and the gap is not "
                  "a correction factor transferable to their books. It was 40.2% when that "
                  "section was written and reads 27.0% on the 2026-09-19 run, which is the "
                  "point. The dilution question "
                  "raised against the ratified population (admitting `tweak` rows made the "
                  "prices representative AND the book more diversified, and only the first "
                  "was argued) was ANSWERED FROM DISK the same day, not left open: "
                  "research/archive/18-hedge-programme-exit-basis-and-text-loop.md "
                  "2026-08-31 (late) shows the deploy card admits only 221 of 458 "
                  "ladder-eligible rows (at most 3 per day), so hedge_portfolio's 996-row book is "
                  "about twice as diversified as what the operator actually holds, which "
                  "registered hedge_concentration to measure the admitted book directly.",
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
    "lib/sleeve_synth.py": "`vol_sleeve`'s synthesis layer — the strike index, the "
                           "leg builder, the trade synthesizer and its statistics helpers — kept "
                           "byte-identical when that study was RETIRED AND DELETED on 2026-09-07. "
                           "hedge_structure's gate R4 builds the calendar cell twice in one process, "
                           "once through its own build_universe/evaluate and once through "
                           "synthesize() here, and requires the two equal row for row; a copy of the "
                           "entry rule inside hedge_structure is the exact copy R4 exists to refuse, "
                           "so the layer outlived the study. fetch_sweep_legs.py and "
                           "fetch_financing_legs.py read _strike_index/paired_strikes from here for "
                           "the same reason. daily() is NOT lib/hedge_criteria.py::daily_series: it "
                           "returns a mapping rather than a tuple and sums dollars over every row of "
                           "a date rather than only the rows carrying a return. The deleted study's "
                           "verdict is the DELETED row in research/study-map.md.",
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
    "lib/prefill_audit.py": "Did this stored row book its exit BEFORE it was filled? "
                            "Reports, never gates, beside lib/basis_audit.py. Until the "
                            "robustness fold's B2 landed 2026-09-08 the engine priced "
                            "pre-fill grid days by carry-forward, so an exit could fire "
                            "on a day the position did not exist — TLT 2025-04-01 booked "
                            "+100% two days before its own fill and re-prices to -754%. "
                            "The fill day is READ off dte_entry (anchor expiration minus "
                            "it), never re-derived from the option cache, which has grown "
                            "since those rows were priced. 14 rows of the v4 book are "
                            "flagged; a study pooling stored outcomes filters on "
                            "fill_trusted, one that re-replays from marks is unaffected. "
                            "Built 2026-09-19.",
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
                   "Transcribed verbatim from hedge_portfolio's committed constant and shared "
                   "with concurrency_correlation's ARM K, which imports it rather than "
                   "restating it — two maps would let two studies disagree about what 'same "
                   "sector' means.",
    "lib/concentration.py": "The concentration trigger layer for hedge_portfolio: per-session "
                   "open-book occupancy, each cluster's signed delta notional, the "
                   "largest-cluster share that IS the independent variable, the "
                   "DIRECT/CONSTITUENT stratum, the hedge-pressure parse, and the census "
                   "G-CENSUS prints. A missing greek is None and the position leaves BOTH "
                   "numerator and denominator — deliberately unlike account_sim.signed_dn's "
                   "0.0, which here would shrink the denominator and move the trigger.",
    "lib/mtm_curve.py": "The MARK-TO-MARKET book equity curve, built from daily_pnl_csv, "
                   "beside the close-bucketed one account_sim already produces — plus the "
                   "per-position G-MTM reconciliation between them and the path statistics "
                   "(max drawdown — this module's own function, which hedge_sizing imports "
                   "back — Ulcer, time-under-water). Both bases come back from one call so "
                   "a caller cannot mix them.",
    "lib/hedge_criteria.py": "The hedge programme's ONE contribution rule, ONE sizing "
                   "rule and one drawdown function (re-exported from lib/mtm_curve, "
                   "never a second body). Transcribed from hedge_sizing D2/D3, the "
                   "origin the other hedge studies name, with every threshold and "
                   "tie-break intact — the decile and quartile floors, the six-date "
                   "year minimum, the 1e-9 slack, max()'s first-wins. Returns "
                   "figures and PRINTS NOTHING, so each study keeps the report shape "
                   "its record quotes, and owns no fraction grid, because narrowing "
                   "one is a registered choice. Pinned by tests/test_hedge_criteria.py "
                   "against a hand-computed fixture, the way lib/harness.py is.",
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
    "lib/hedge_instrument.py": "Hedge instrument selection and pricing for hedge_portfolio: "
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
    "lib/ladder_targets.py": "The ONE owner of \"which contracts does a ladder campaign owe "
                         "a core\", imported by both the collector "
                         "(`fetch_ladder_legs.py`) and the campaign engine "
                         "(`overlay_campaign.py`) so the scrape targets and the simulation "
                         "can never disagree. `third_fridays`, `eligible_expiries`, "
                         "`roll_chain`, `ticker_ladder`, `target_strikes`, "
                         "`cached_strikes`, `CoreSpec` and `core_of` are defined ONCE, "
                         "here. The two callers differ only in their EXPIRY UNIVERSE — the "
                         "collector passes cached union third-Fridays, the campaign passes "
                         "cached-only — always an explicit argument, never re-derived. "
                         "`DIAG_MIN_DAYS`/`DIAG_MAX_DTE_FRAC` are imported from "
                         "financed_spread (F4's frozen near-expiry window), never "
                         "redefined. Pure, no network, no writes. Built for "
                         "ladder_overlay.",
    "lib/overlay_campaign.py": "The roll-capable tranche campaign for `ladder_overlay`, "
                         "composed AROUND the frozen harness — trigger, sale, breach "
                         "policy, settlement, roll — plus the multi-tranche net-mark "
                         "algebra (core clamped only on days with no live tranche, "
                         "realized costs outside the clamp) and the `[MODEL]` "
                         "Black-Scholes sensitivity tier that `assert_not_model` keeps out "
                         "of every criterion. Gate G1b's `f4_identity` proves it is a "
                         "SUPERSET of `financed_spread` ARM F4 rather than a second "
                         "simulator.",
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
