# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index.

**State of play (2026-08-14, CORPUS REPRESENTATIVENESS — a defect found, an
expansion PRE-REGISTERED, no conclusion moved).** Prompted by the question
"2026 was mainly bear and the algorithm does badly in bear — should we scrape
more?". **The premise is inverted and the answer to it is no**, but the
investigation surfaced a real defect that is not about bear at all.

*What the premise gets wrong.* The corpus is neither mainly-2026 nor
mainly-bear: `AnalysisClaude` spans 2024-06-17 → 2026-08-10, 142 dates, 1,607
rows, `mech_cell` BEAR_HE 758 / LVOL 728 / NONE 78 / RB_EVOL 43. And the
**shipped** system is bear-*strong*, not bear-weak: the awful pooled bear cells
(§7.4 BEAR+H-VOL n=64, win 30%, PF 0.39, −$20,632; mech BEAR_HE
`bear_put_spread` n=218, −$40,300) are **already vetoed** by deployment-rules
§1.2/§1.4, and in the deployed book BEAR_HE is the **best** mechanical cell
(PRIMARY n=44, +$10,399, meanR +0.366, win 0.659). The worst deployed cell is
**BULL/L-VOL — n=34, −$4,727, meanR −0.325, win 0.353**, and it is unvetoed.
More bear data cannot help regardless: `bear_deploy` already searched **496
conditioned subsets at n=164 and found 0 positive** (best −0.231).

*Why the hedge worst-decile wall is not worth buying out.* `bear_rewrap`'s P1 is
computed over the worst **10% of deployed dates** (`bear_rewrap.py:570`) with a
**date-clustered** bootstrap (`protocol.py:81`), so the effective sample is **9
clusters, not the 21 rows it prints**. Modelling half-width ~1/√(tail dates)
from `long_put` (meanR +0.262, CI [−0.273, +0.730]): the criterion first clears
at **~33 tail dates ≈ +394 newly analysed dates — 81% of the 484 that remain
fetchable — and then clears by ~+0.001**, only if the point estimate holds
exactly (the baseline's +0.108 never clears at any attainable sample). Under
ARM S's 30-cell multiplicity the requirement is **W≈85 ≈ +996 dates, more than
the data universe contains**, and 6 of the 30 cells (`P5 top-pick ticker`) fill
0% and are dead at any N. **The wall is half a multiplicity problem, and that
half is free to fix** by pre-registering one structure × one pick rule. Recorded
so the standing "the only path forward is NEW DATES" framing is not over-read:
new dates alone do not open the 30-cell sweep.

*The defect actually found.* The book was assembled from three dense crash
episodes, and it is **not a representative sample of the tape**:

| | n dates | VIX mean | VIX median |
|---|---|---|---|
| full path-completable window (2024-02-15 → 2026-04-16) | 543 | 17.93 | 16.65 |
| **currently analysed, in that window** | 117 | **21.93** | **21.65** |
| after the +139 expansion below | 256 | 19.07 | 17.53 |

**~4 VIX points of stress over-representation.** This is a validity issue for
every conclusion drawn on the book, independent of any power question, and it is
the structural reason BULL/L-VOL is thin — calm regimes are under-sampled by
construction, so the cell that looks worst is also the cell least observed.

*Pre-registered, before any of it is run.* A **neutral** date expansion:
`backtests/neutral_dates_v1.md` — every 3rd session by calendar index over
`[2024-02-15, 2026-04-16]`, **k=3 chosen because it must be coprime with 5** or
the sample locks to one weekday (verified: Mon 27 / Tue 27 / Wed 28 / Thu 28 /
Fri 29). 543 sessions → 181 selected → **139 new**. Selection reads **only the
calendar** — never an outcome, price, or VIX field — which is what keeps it from
reshaping the loss distribution the decile is defined against. Cherry-picking
stress dates would have done exactly that, which is why
`backtests/next_25_dates.md` (2026-07-20, regime-gap selected, never executed)
is **not** reused here.

Declared now rather than discovered later: (a) the existing 117 dates are **not**
neutral, so the pooled book is a **mixture** — the mech_cell composition of old
vs new deployed dates gets printed, and a move beyond a declared band labels the
pooled result non-comparable to the 08-14 print; (b) **the decile re-anchors** —
old-W and new-W get printed side by side with the worst-date overlap, and every
pre-expansion P1 number becomes a legacy reference, not a comparator;
(c) guard-rejected or failed dates are **recorded with a reason, never silently
skipped**; (d) `WORST_DECILE = 0.10` and `POWER_STOP_MIN_N = 10` are **not to be
touched** — widening to the already-defined `WORST_QUARTILE` would take W from 9
to 22 for free, but doing so after seeing the decile fail is precisely the
post-hoc criterion change the anti-tuning rule forbids.

**Nothing has been scraped and no number below moves.** A **pre-declared kill
switch** governs: the first 10 neutral dates measure the deployed-date yield on
*neutral* (not cherry-picked) dates — the 0.763 the arithmetic assumes was
measured on signal-rich dates — and **if 10 dates add fewer than 4 deployed
dates, stop.** Corrected cost estimate: ~**1–1.5 h/date**, driven by `enrich_oi`
being per-*contract*, so 139 dates ≈ **175 h**; the scrape step is ~2% of it.

Two data-integrity guards ship first, and are worth having even if the backfill
never runs: a **flow-staleness guard** (the `options-flow` feed silently serves
~500 rows of run-date-anchored junk past its retention window — HTTP 200,
correct schema; the TODO from archive/06 was never implemented) and an explicit
**IV-depth signal** (blank `IVpct` does not merely drop a column, it **changes
which structure the model picks** per analysis-framework §"TF vs TF-S", so
backfilled rows would differ from existing rows on the debit/credit axis for a
non-market reason). Both are now **shipped**, with `iv_pct_status` appended to
`ROW_COLUMNS` (25 → 26, append-at-end, **not** a version bump — the prompt
contract is untouched and the column is deterministic rollup context like
`oi_confirm_pct`/`cpir`).

**Both floors were then RE-PROBED live (2026-08-14), and both prior assumptions
were wrong — in opposite directions.**

*Flow floor is EARLIER than believed: `2024-01-02`, not 2024-02-15.* Every
probed date from 2023-11-01 through 2023-12-27 returned the **byte-identical**
fallback — sha256 prefix `26fc63189d6d182f` on all six, exactly 500 rows, median
DTE ~1000–1060, and SPY `Price~` **777.86** (that day's SPY) against real closes
of 422.66 / 459.10. Every date from 2024-01-02 on came back genuine (median DTE
38–51, SPY drift ≤0.004), and the 2024-06-17 control (already in the corpus)
passed at median DTE 32 / drift 0.001. The guard caught the junk independently
on all four checks, so the probe validated the guard and the guard defined the
floor, as intended. **Both flow feeds share that floor** — `stocks-flow` was
probed separately and rejects 2023-12-15 (under its own distinct fallback hash
`bef2fdd5730f89a5`, so each feed caches its own junk) while returning genuine
data from 2024-01-02 on, so there is no window in which a date would yield
usable ETF flow but unusable stock flow. Net effect: the window gains 31
sessions and the list is regenerated at **574 sessions → 192 selected → 155
new** (was 139). The
regeneration is **outcome-blind** — nothing has been scraped, no outcome exists
for any candidate date, and the trigger was a data-availability probe.

Of those 155, **2 are excluded and 153 are queued**: `2024-01-02` and
`2024-01-05` sit at session index 0 and 3 of the window, so with
`DEFAULT_DAYS = 5` their trailing persistence window falls in the December-2023
junk range and cannot be built. Analysing them on a truncated window would make
their model input structurally different from the other 153 — the same
non-comparability class `iv_pct_status` exists to catch. Recorded with the
reason in `neutral_dates_v1.md` rather than silently skipped, and dropped in
preference to a third regeneration that would reshuffle the phase for all 153
others to fix a 1.3% edge effect. First fully-windowed session: `2024-01-08`.
Queues written to `backtests/enrich_queue_{a,b}.txt` (73 + 80, disjoint date
ranges so they run in parallel) plus `enrich_queue_pilot.txt` (the first 10,
carrying the kill switch).

*IV floor is FAR deeper than believed, and Trap B does not materialise here.*
The options-overview feed returned **n=1000 bars spanning 2022-08-17 →
2026-08-13, identical across SPY/AAPL/NVDA/XOM/KO** — so retention is a
market-wide rolling ~1000-bar window, and **~1000 trading days is ~4 CALENDAR
years, not the "~2 years" claimed throughout the code** (corrected in
`lib/barchart/iv_history.py`, `session.py`, `lib/iv_history.py`,
`fetch_iv_percentile.py`). The earliest expansion date sits **503 days above**
that floor, so **no date in this list can come back `out_of_window`** and
`iv_pct` should resolve for all 155. The debit/credit provenance confound is
therefore a *latent* risk the guard now covers, not an active one for this
expansion. Separately, the `startDate`/`endDate` param names — flagged in-code
as "a best guess to VERIFY" — are now **verified honoured** (a
2025-06-02..2025-06-13 request returned 10/10 rows inside the window).

**State of play (2026-08-14, study suite REPAIRED — `run --all` exits 0, suite
1,149 passed / 0 errors).** Infrastructure and one contamination fix; **no
pre-registered criterion changed and no verdict moved.** The six `--all` failures
are gone: the DEBIT_PROD exact-replay gate now **classifies** rows (exact / near
/ superseded-basis / HARD) and stops only on HARD, so the three studies it had
permanently disabled run again — 289 exact / 12 superseded / **0 HARD**, with the
whole −$5,145.00 isolated to the 12 BEAR_HE rows the shipped trail produced and
the calibrated totals matching to the cent. Superseded rows are **kept and
re-replayed**, never dropped. `bear_position_study`'s `R` is now re-replayed
instead of read off `realized_pnl_pct` (the contamination was **12 rows,
−$5,145.06**; bear_put mean R −0.1016 → −0.1069, so it made the bear book look
*better* than it was — verdict still **DEMOTE TO VETO**, card veto §1.4 stands).
`combined_exit_study` / `underlying_exit_study` are **RETIRED** (inputs
unrecoverable, verdicts already archived), and `v4_bridge`'s exit 3 is now a
first-class **DESIGNED REFUSAL** status rather than a failure. Three carried
follow-ups closed: `account_sim`'s verdict grammar is **total** (test-enforced
over all 32 combinations; PRIMARY now prints `FEASIBILITY NOT CONFIRMED` instead
of `NO VERDICT MATCHES`), ARM H's sizing floor skips instead of rounding a
half-size hedge up to a full contract, and `selection_order` criterion (4) is
reworded. **NEW STANDING HAZARD: the `exit_basis` column is unusable on the
current export** — unlabelled and scrambled; do not key anything on it (details
in the entry below). Frozen `account_sim` book re-verified unmoved (72 positions
/ $11,398 / meanR +0.290); `calendar_hedge` H0 re-verified unmoved (75.6% /
66.7% MET). Prior state follows.

**State of play (2026-08-14, `account_sim` COMPOUNDING arm FOLDED IN — no number
moves).** Infrastructure only; **no evidence changes and no conclusion moves.**
The compounding sensitivity is no longer a copied config file
(`config/account-sim-compounding.yml` is **deleted**) but a `--compounding` FLAG,
and one bare `run account_sim` now prints **both bases**: the frozen,
path-independent book (`account_sim-latest.txt`, unchanged) and the arm
(`account_sim-compounding-latest.txt`). Each arm writes its **own** report,
positions CSV (`account_sim-positions-compounding-latest.csv`) and page
(`site/account-sim-compounding.html`, `scripts.study_charts.compounding`), and
the chart layer now pairs a report to a positions file on **both** axes
(structure AND compounding) — so the failure that prompted this, an arm silently
rebuilding the frozen book's page from its own numbers, is now structurally
impossible in either direction. Verified on re-run: the frozen book reproduces
(G1 passes, PRIMARY 72 positions / $11,398 / meanR +0.290) and the arm reproduces
the figures recorded in the 2026-08-13 entry (now in
[`archive/14-volume-signal-demotion-and-audit.md`](archive/14-volume-signal-demotion-and-audit.md);
70 positions, **$9,852**).
`compounding:` in `config/account-sim.yml` now holds only what the arm is
parameterised BY (`mark_interval`, `budget_ceiling`); a leftover `enabled:` key
is a hard `ConfigError` rather than a silent frozen-book-under-an-arm's-name.
The arm remains **post-hoc and not pre-registered**, and **A2/A5 still do not
transfer** to it. Prior state follows.

**State of play (2026-08-14, `selection_order` RUN — POWER-STOPPED).** The
ordering study is **built, run and closed on this book**. Verdict
**POWER-STOPPED** at G0: every arm changes only **7–14%** of the deployed book,
so the best-powered one reaches **11 affected dates on PRIMARY (20 at best on
SECONDARY) against a floor of 25** declared before the count was knowable.
Gates G1–G5 all pass — B1 reproduces `220 / 90 / $63,553`, O0 is byte-identical
to a direct `ladder_rank` walk, and all six arms **including an O4 draw** survive
both blindness layers. Nothing was read: under a total stop the arm table drops
its outcome columns and the 200-draw band is **not drawn at all**, because a
number on the page gets quoted eventually whatever the caveat says. So
`account_sim`'s adverse-ordering read is neither confirmed nor refuted — **this
book cannot adjudicate it**, and the census texture that would make it
`CAP-BOUND-NOT-ORDER-BOUND` is a carry-forward, not a verdict. **Do not re-run on
these dates.** One registration bug to fix before any re-registration: criterion
(4)'s "all three years" is unsatisfiable on a two-year PRIMARY. Entry below.
Prior state follows.

**State of play (2026-08-14, `selection_order` PRE-REGISTERED).** The one
follow-up `account_sim` left as pre-registerable — the delta-cap **ordering**
question — is **PRE-REGISTERED, not built and not run**:
[`pre-registrations/selection_order.md`](pre-registrations/selection_order.md).
Six frozen arms, each only a different `rank_fn` into
`protocol.ordered_by_day`, with tier membership, universe, sizing, caps and
exits held exactly as `account_sim` runs them — this is an ORDERING study, not
a selection study, and selection stays closed (new COLUMNS only). The decisive
arm is **O4, a seeded random control**: an arm must beat the random band, not
merely beat `ladder_rank`, and if `ladder_rank` itself sits inside that band the
adverse-ordering read (+0.624 rejected vs +0.290 taken) was an artifact and the
thread closes. **G0 is a blocking power pre-check** — under 25 affected dates an
arm is power-stopped and never read, declared before the contested-date count is
known. Nothing ships under any outcome; the ladder is itself in-sample, so an
ordering evaluated on this book is second-order in-sample. Also recorded from
reading `simulate()`: the `day3_cap` / `unsizable` / `ruined` census buckets
append a `None` counterfactual, so the existing "rejected picks returned +X"
description covers only the `net_delta` / `per_pos_delta` / `min1_refusal`
exclusions. Prior state follows.

Prior state (2026-08-13 and older) is archived — see [`archive/`](archive/) files 07–14 and the [README](README.md) section index.

---

## 2026-08-15 — `account_sim --live-select` ARM ADDED: the shipped selector run under history. **150 ranked candidates were never priceable, 37 deploy slots were filled from below the selector's own top-3, and the research ladder is missing the §1.3 credit veto on 21 export rows**

**Status: ARM ADDED, nothing adopted. No pre-registered criterion is evaluated by
this arm, no threshold moved, and the frozen `account_sim` book is byte-identical
(verified by diff — only the provenance header and the already-committed verdict-
label amendment differ).** Report:
`backtests/study_output/account_sim-live-select-latest.txt`; positions:
`account_sim-positions-live-select-latest.csv`.

*What the arm is.* `account_sim` re-implements the deployment ladder in
`scripts/backtest_study/book.py::ladder_tier`. The function that actually decides
what gets deployed is `scripts/journal/s06_recommend.py` — `rank()` (which encodes
`deployment-rules.md` §1–§3 exactly once, via
`scripts/live_loop/mapping.ladder_tier`) then `judge()` (the one demote-only model
call). `--live-select` swaps the first for the second and changes nothing else:
ledger, caps, sizing and the frozen exit replay are untouched, reached through a
`ranker` hook on `simulate()` that is `None` on every other path.
`s06_recommend.py` gained no sim-specific branch.

*Finding 1 — the frozen book is partly a pricing artifact, and the size of it is
now a number.* Of **1,448 (date, ticker) analysis pairs** (residual zero; every
pair lands in exactly one bucket): 283 ranked as a priceable deploy candidate,
**150 ranked as a deploy candidate and had no priceable record**, 423 were §4
hedge-sleeve candidates, 184 Tier C, 169 §1 VETO, and **239 sat on a session the
walk never reached at all** because that date had no priceable row anywhere. The
150 split **107 `bs_options_hist` · 28 `unevaluable` · 8 no evaluation row · 4
structure mismatch · 3 withheld by the exact-replay gate**, and by year
2024=30 / 2025=82 / 2026=38. **37 deploy slots across 31 sessions went to a play
the selector itself ranked below its own top-3**, purely because a higher-ranked
candidate could not be priced. Composition against the frozen book's 220 picks:
208 offers, 182 shared, 38 only-frozen, 26 only-live-select.

*Finding 2 — the research ladder is behind production on §1.3.* Counted on the
raw exports, **21 rows** (7 `BacktestResults` + 14 `BacktestProxy`, all
`bull_put_spread`) are credit plays in a RANGE + L-VOL market that production
VETOES and `book.py` admits — **not the 23 (8 + 15) the plan predicted**; no
credit definition (`mapping.SIDE`, or `entry_option_price` sign) reproduces 23,
and the 21 are stable across both. Inside the frozen 795-record candidate
universe the same clause accounts for **13 rows** (10 C→VETO, 3 B→VETO; real 7 /
tweak 6). Under `ibkr_verified` that is the ONLY divergence class; withholding
the delta (`analysis_only`) moves rows into a §3 availability bucket instead —
Tier B falls 248→195 with `partial` rising 44→105.

*Finding 3 — `rank()` reads the open book but does not filter on it.* The plan
expected selection to differ because `rank()` sees live positions before
ordering. It does read them, for `duplicate_exposure` and cap headroom, and
records both as text — **nothing downstream reads them back**. So `rank()`'s
order and membership are independent of the book handed to it. The synthetic
`risk.BookRisk` is still built from the sim's genuinely-open positions (it is
what makes the printed reasons true, and it keeps the missing/zero invariant: a
record with no delta lands in `unpriced`, never in the totals as a zero), but no
one should expect ledger state to move a pick.

*The judgment layer, and its bound.* `judge()`'s prompts are cached by
`sha256(prompt)` into `backtests/study_output/live-select-judgments.jsonl`
(prompt hash, model id, session, raw response, timestamp), so a re-run replays
and the arm is reproducible — **verified: a second run makes zero model calls and
produces an identical book**. `JUDGMENT_MODEL` is `claude-opus-5`, whose cutoff
overlaps these analysis dates, so it can "remember" outcomes and **G5 cannot
detect that** — G5 blinds record fields, not model weights. The arm therefore
bounds rather than assures: two ledger walks off ONE model pass,
`demote_policy=skip` against `ignore`, whose difference IS the judge layer's
whole effect. The real pass has **not been run** (104 opus-5 calls, deliberately
not spent); the path is exercised end-to-end against a stub, which demoted 190
candidates and moved the book by $8,250 — that is a property of the stub, **not
evidence about the model**.

*Two mechanisms worth keeping.* §2e: `judge()` keys verdicts by ticker, so two
plays on one ticker on one date would have the second silently take the first's
verdict — **2 sessions carry that** (2026-02-19, 2026-03-06, five tickers each),
and the arm blanks the annotation on both rather than letting one read annotate
two plays. §2d: `recommend.DEPLOY_BUDGET` and `account.max_positions_per_day`
agree today in two files by coincidence; the arm asserts it at startup and
refuses to run on drift. **G5 is re-run with the shipped selector in the loop**
(G1–G4 stay pinned to the frozen basis) and PASSES on both walks, sighted vs
blind, 153 = 153, 0 differing — but note what it cannot reach: it blinds record
FIELDS, and a model's weights are not a record field. **G6** (nothing reaches the
ledger that `rank()` did not clear) PASSES on both walks.

---

## 2026-08-14 — study-suite triage FIXED: the exact-replay gate now classifies instead of asserting, `bear_position_study`'s R is re-replayed, and the `exit_basis` column turns out to be UNUSABLE

**Status: IMPLEMENTED. No pre-registered criterion changed, no exit grid
changed, no shipped rule moved.** This entry closes
[`next-steps.md`](next-steps.md) §0c(A) — the diagnosis in the section
immediately below. All three blocked studies run again and exit 0.

**The fix — one predicate, three callers.** The gate demanded that every real
debit row replay bit-exactly under `DEBIT_PROD`. It now classifies each row
**exact / near-rounding-tie / superseded-basis / HARD** and stops only on HARD.
`harness_gate()` in `exit_switch_mech_study.py` is the single implementation;
`exit_switch_structure_study.py` and `bear_position_study.py` call it instead of
re-implementing the predicate, so the correction cannot drift between the three.

**How superseded-basis is identified — mechanically, not by date heuristic.**
`replay()` can only emit an exit reason whose governing knob is set in the
profile it is called with (`harness.py:119-170`), so the set of reasons a
profile CANNOT produce is a property of the profile. Under `DEBIT_PROD` that is
`{trailing_stop, underlying_stop, be_stop}`. A stored row whose `exit_reason`
falls in that set was, by construction, written under a different exit config.
New `unreachable_reasons(prod)` computes it; `_classify()` applies it. Measured
on the current export: **289 exact / 0 near / 12 superseded / 0 HARD**, and the
calibrated-row totals now match **to the cent** ($27,216.20 both sides), with the
whole **−$5,145.00** isolated to the 12 superseded rows and reported rather than
asserted away. All 12 carry stored `trailing_stop`.

The 12 rows are **KEPT and re-replayed**, not dropped — they are not a random 6%
of BEAR_HE (12/203) but exactly the rows where the shipped rule changed the
outcome, i.e. maximum-signal rows in the cell under test. `enrich()` already
re-replays every row under PROD and each variant, so nothing downstream needed to
change. Proxy admission is **deliberately unchanged** (exact-only): that is a
pre-registered POPULATION choice, and widening it would move every number these
studies print. The proxy exclusion census is now broken out by class for honesty
— 48 excluded = 25 near / 22 superseded / 1 hard.

**`bear_position_study`'s R is now re-replayed** (`replay(t, **DEBIT_PROD)`),
never read off `realized_pnl_pct`. Size of the contamination, measured on the
same book both ways: **12 rows move (all real; 8 `bear_put_spread`, 3
`bull_call_spread`, 1 `long_put`), −$5,145.06.** Headline effect
`bear_put_spread` mean R **−0.1016 → −0.1069**; `long_put` −0.570 → −0.627 (n=7,
one row); pooled −0.0045. The stored column made the bear book look *better*
than it was, so the correction **strengthens** the demote reading rather than
reversing it — re-run verdict is still **DEMOTE TO VETO**, and card veto §1.4
stands unchanged. `E` (`pnl_at_cap_pct`) is exit-rule-independent by construction
and untouched. NOTE for anyone comparing: a naive row-level diff reports "95.7%
of rows changed" — that is 4-decimal CSV round-trip noise. At a `NEAR_MISS_TOL`
threshold it is 12 rows, 1.5%.

Re-run verdicts, all unchanged: `exit_switch_mech_study` **STAYS GATED**,
`exit_switch_structure_study` completes, `bear_position_study` **DEMOTE TO
VETO**. 15 new tests in `tests/test_exit_replay_gate.py` pin the four buckets,
that superseded rows are kept and tagged `calibrated=False`, that the dollar
check ignores them, that proxy admission did not widen, that a **true HARD row
still exits 1**, and that `bear_position_study`'s R cannot regress to the stored
column.

**NEW FINDING — `exit_basis` is present in the export but UNUSABLE, so do not
re-key anything on it.** §0c's recommended route was "identify superseded-basis
by the `exit_basis` column when present". It is present — as an **unlabelled
47th column** (the Sheets tab header was never given the name, exactly the hazard
CLAUDE.md warns about) — and its values are **scrambled relative to their rows**:

- Rows created AFTER the trail shipped (67, every one of which should carry a
  basis): **65 blank**, 2 `CREDIT`.
- Rows created BEFORE the column existed (339, none of which should carry one):
  **55 `BEAR_HE`, 11 `CREDIT`**.
- 7 of 13 `CREDIT`-tagged rows have a **positive** entry price, impossible per
  `simulate.py:_exit_basis` (which returns `CREDIT` only when `entry_net < 0`);
  6 of those 7 were created 2026-07-09/07-10, *before* `exit_basis` shipped.
- No `BEAR_HE`-tagged row has a `trailing_stop` exit, while all 12 rows that
  provably ran the BEAR_HE trail are blank.

This is why the classifier keys on unreachable exit reasons instead. Operator
action, NOT taken here (it is a Sheets write): `scripts/align_tab_headers.py`
covers only the **analysis** tabs (`config.ROW_COLUMNS`) and does **not** check
`BacktestResults`/`BacktestProxy` against `scripts/backtest/core._KEY_ORDER` —
that gap is what let the column land nameless. Re-key any study on `exit_basis`
only after the header is fixed AND the values are re-verified against entry-price
sign. `docs/backtest-reference.md:130`'s claim that **blank = PROD-basis by
definition** is **false on this export** and should not be relied on.

---

## 2026-08-14 — `run --all` is GREEN: two dead studies RETIRED, and "designed refusal" is now a status the runner understands rather than a failure

**Status: IMPLEMENTED, infrastructure only. No study re-run to a conclusion, no
number moved.** With the gate correction above, `backtest_study run --all` goes
from **6 failures to exit 0**. The six were three unrelated causes, and only the
gate was a real problem; these are the other two.

**(B) `combined_exit_study` and `underlying_exit_study` are RETIRED.** Both crash
on scratch CSVs under `backtests/` that were deleted long ago — a gitignored,
periodically-deleted tree, so the inputs were never recoverable. Their verdicts
are already recorded (Attempts 8, 9, 12 in
[`archive/02-credit-debit-split-attempts-8-12.md`](archive/02-credit-debit-split-attempts-8-12.md))
and neither is named in this file. `catalog.py`'s `Study` gains a `retired`
field — deliberately **orthogonal to `state`**, because retirement is about
whether a study can be RUN, not about what it argued — plus a
`retired_studies()` helper. `--all` skips them with the reason printed;
`run <name>` still runs one explicitly after a notice. The study-map page renders
them with a `retired` pill and their reason as a caveat.

**Why they were not simply repointed at surviving files** — this is the part
worth not re-deriving. `backtests/results.csv` is **4 rows on 2 dates** today (a
rolling file every `backtest.py` run stomps) against the 94 real debit + 22
credit rows Attempt 12 actually ran on. `combined_exit_study`'s
`results_proxy.csv` is an **author transposition that never matched the writer**
(`config/backtest.yml` has said `proxy_results.csv` since the block existed).
`v2_results_nocreditdiff.csv` IS the genuine rename of the file
`underlying_exit_study` wants — but that study's *other* input has **0 credit
rows** today, so `load_credit_rows` returns `[]` and it would emit a degenerate
empty report regardless. Numbers off a 4-row wrong-vintage book could be
mistaken for a fresh confirmation of the reference verdict. Porting
`combined_exit_study` to `book.py` remains possible but is a **design decision,
not a loader swap** — it imports `Trade`/`replay` from `exit_mechanism_study.py`,
a separate older implementation from the FROZEN `harness.py` — and is not wanted
now. Count rows in these exports with `csv.DictReader`, **never `wc -l`**:
embedded newlines in `daily_price_csv` inflate line counts ~4×.

**(C) A non-zero exit is often CORRECT, and the runner now knows it.** `v4_bridge`
exit 3 was never a defect — it is the pre-registered refusal to compare a v3 book
against itself when no v4 export exists (gate `MIN_V4_DATES = 20`, v4 accruing
~1 date/day). Rather than special-casing the name, a study may now declare
`DESIGNED_REFUSAL_EXIT_CODES = {…}` as a module constant, read by `run.py` via
`ast` (never imported, same reasoning as `discover()`). Such an exit promotes
`-latest.txt` like a clean run, prints under **DESIGNED REFUSALS (not failures)**,
and is excluded from the return code — so a refusal-only run exits 0. `v4_bridge`
declares `{2, 3}`. Several other studies stop on their own pre-registered
calibration or power gates and are equally correct to do so; the convention is
documented where `--all` is read. `MIN_V4_DATES` was NOT lowered and `--v4-csv`
was NOT pointed at a v3 export.

**And the study MAP had to learn the same two words**, or the fix would only have
moved the misreport to a second tool: `study_map --check` was still printing
`v4_bridge … exit 3 [failure]` and labelling both retired studies `never run`.
`summary.py` now imports `run.py`'s `_refusal_codes` and `catalog`'s retired set
rather than re-deriving either, so there is one source of truth; status reads
`refused (exit 3)` / `retired`, with a fifth excerpt kind `refusal` whose gloss
says **BY DESIGN**. The kind is applied whether or not the report happens to
carry an ABORT-shaped line, so a plain "gate not met" message can't fall through
to `matched`/`tail`. The load-bearing safety property is tested: **an UNDECLARED
non-zero exit on a refusal-capable study still classifies as `failure`** — the
refusal path must never swallow a real failure. Suite ends at **1,149 passed / 0
errors**.

**Unrelated but now closed:** the two long-standing `test_underlying_features.py`
teardown errors. `_market`'s finalizer called `.cache_clear()` on
`uf.market_closes` while the monkeypatched lambda was still installed —
`monkeypatch` is a dependency of that fixture, so pytest tears it down *after*.
Undo first, then clear. The tests always passed; only teardown errored, but the
synthetic SPY series was surviving in the `lru_cache` and leaking into later
tests, which is the exact contamination the fixture exists to prevent. **Suite is
now 1,139 passed / 0 errors.**

---

## 2026-08-14 — three recorded follow-ups closed: `account_sim`'s verdict grammar is now TOTAL, ARM H's sizing floor skips instead of rounding up, `selection_order` criterion (4) reworded

**Status: IMPLEMENTED. No criterion threshold, no measured number, and no
verdict moved.** Three small items that had been carried for days, done together.

**(1) `account_sim` verdict grammar closed to TOTAL.** The pre-registered
grammar named `FEASIBLE` (A1^A2^A3^A5^A6), `FEASIBLE-BUT-DEGRADED` (A1^A3, A2
fails) and `NOT FEASIBLE AT $25,000` (A1 fails) — and nothing for **A1 holds
while A5/A6 fail**, which is what this book actually produces. The study printed
`NO VERDICT MATCHES` on four consecutive re-runs. Two labels added, both checked
after the original three and neither readable as a pass:

- `NOT FEASIBLE AT $X — BLOWUP RISK (A1 holds, A3 fails)` — the case the
  SECONDARY arm now hits at 25.1% drawdown against a 25% limit.
- `FEASIBILITY NOT CONFIRMED (A1-A3 hold; A5 and/or A6 fail; stability/
  robustness not established on this window)` — the flagged gap, which now fires
  on PRIMARY.

Only the outcome→label mapping was completed; A1–A6 keep their thresholds and
meanings, and the amendment prints inline wherever a new label fires. Totality
is now a TEST, not a claim: `test_verdict_grammar_is_total` enumerates all 32
A1/A2/A3/A5/A6 combinations and asserts each maps to exactly one of the five
labels, pinning the partition at 16/1/4/8/3. Frozen book re-verified unmoved —
G1 PASS, B1 220 positions / 90 dates / $63,553, taken n=72 meanR **+0.290**,
rejected-`net_delta` **+0.624**.

**(2) ARM H sizing floor now SKIPS a sub-one-contract hedge** instead of
`max(1, int(0.5 × c))` rounding it back up to a FULL-size hedge — the opposite
of what the arm specifies. `hedge_contracts`/`H_dol` are `None` when half-size
rounds under one, at both sites (`_typed`, and a second latent copy in ARM S's
`rec_substitutions`). The floor fires on **34 of the 68 picked sleeve
positions** (every `contracts == 1` row), moving H1's half-size dollar total
**$13,252 → $7,154 (−$6,098)**. The programme is POWER-STOPPED
([`next-steps.md`](next-steps.md) §2.3), so this changes no conclusion — but the
figure is different and is recorded here rather than left to be re-quoted.

**Caught in review and reverted — the floor must bite at SIZING, not on the
UNIVERSE.** The first implementation filtered the candidate set on
`hedge_contracts`, which dropped 61 of 132 strict-fillable candidates and flipped
**H0 from the recorded MET (75.6% deployed / 66.7% worst-decile) to NOT MET
(51.1% / 33.3%)**. H0 asks whether the hedge is AVAILABLE when needed — a fill
question — and "fillable but too small to half-size" is not "unfillable".
Conflating them silently redefines the gate. The universe is restored (130
retained over 68 dates, H0 **MET** at the recorded numbers); an unsizable
candidate stays in it, is counted by H0, and contributes **$0**, disclosed on its
own line. Regression test pins that H0's counts do not move when the floor fires.

**(3) `selection_order` criterion (4) reworded.** "Positive in all three years"
was unsatisfiable on a PRIMARY spanning two calendar years. The implementation
was already correct (`all(v > 0 for v in ymeans.values())`, every year present,
with an inline disclosure); only the WORDING was wrong, in the printed string and
in the pre-registration. Both now read "positive in every calendar year present
in the arm's population", with a dated wording-correction note. Implementation
untouched, study NOT re-run — it is POWER-STOPPED and closed on this book.

---

## 2026-08-15 — structure-name defect FIXED: `bear put debit spread` was backtested as a **single long option**, silently. v4 book re-run; v3 left frozen and quantified

**Status: SHIPPED (parser + prompt + tests), v4 BOOK RE-RUN, no verdict re-read.**
This is a data-integrity fix, not a tuning result. Nothing was concluded from the
corrected rows — they are reported so the size of the contamination is on record.

**The defect.** The model periodically writes the debit/credit qualifier INSIDE
the structure name — `bear put debit spread 350/320`, `bull put credit spread
62/57`, `call debit spread 87/92` — because the framework's own Step-4 table
labels those columns "Debit spread" / "Credit spread" and three prose clauses
said, verbatim, "take a bear put debit spread or pass". Neither `bear put
spread` nor `put spread` is a substring of `bear put debit spread`, so the
phrase matched **no** spread branch in `scripts/backtest/classify.py` and fell
through to the single-leg branch. **It did not skip — it wrote a row**, with a
`structure`/`legs` contradicting the row's own `play` text:

| tab | row | stored | correct |
|---|---|---|---|
| `BacktestProxy` | 2024-02-06 META / KRE / SMH, all `[HEDGE] PU` | `structure` **blank**, `unevaluable` | `bear_put_spread` |
| `BacktestProxy` | 2024-02-06 TSLA `[SYNTHETIC STOCK] PU` | `long_put`, **+97.9% `profit_target`** | `bear_put_spread` (unpriceable — short leg has no history) |
| `BacktestResults` | 2024-01-19 BABA `[SYNTHETIC STOCK] PU` | `short_put` — **sign-flipped**, a credit structure standing in for a debit one | `bear_put_spread` |

The TSLA row is the instructive one: a 185/165 vertical caps at
(185−165)/debit, so a **+97.9%** print is not a mis-estimate, it is a payoff the
structure cannot produce. Priced as a naked 185 put it is perfectly reachable.

**A second, independent gate had the same shape.** `_UNSUPPORTED_PATTERNS` held
the bare substring `"covered"`, so rationale prose — *"the downside deserves to
be covered"* — rejected a priceable `bear put spread 470/440` (2025-03-14 QQQ,
`[HEDGE] TF`) as `unsupported`. Now matched as structures (`covered call`,
`covered-call`, `buy-write`, …), not as a word.

**Blast radius beyond the backtest.** `scripts/live_loop/mapping.py::play_structure`
— the PRODUCTION path both `scripts/journal/` and the fortnightly audit read —
had the identical blind spot and returned `"unknown"`, so a play the operator
actually *traded* could not be matched to its fill at all. That is why the
defect surfaced as "it happens on the HEDGE and PU" rather than as a backtest
anomaly: `[HEDGE] PU` plays are exactly the ones being traded and reconciled.

**The fix.** `lib/structure_names.py::canonical_spread_names` — ONE encoding of
the rewrite, imported by both the backtest classifier and the live-loop play
parser, so the two can never disagree about what a play's text named. The
(option type, debit|credit) pair determines the vertical completely; an explicit
`bull`/`bear` word that contradicts it is a model slip and loses. Prompt side:
`scripts/analysis_pipeline/config.py` now pins an explicit structure vocabulary
and forbids the qualifier inside the name, and the three prose clauses in
`config/prompts/analysis-framework.md` + `config/prompts/analysis-methods/claude.md` that
modelled the bad phrasing were reworded. `tests/test_structure_names.py` (21
cases) locks both parsers.

**v4 book re-run** (`--date 2024-01-19`, `--date 2024-02-06`, real then proxy
`--redo`). `BacktestResults` 29 → 30 rows: SMH enters as a real
`bear_put_spread` (−82.4%, `stop_loss`), BABA leaves it for the proxy (a
vertical needs both legs priced; as `short_put` it only ever needed one).
`BacktestProxy` 77 → 76. Two ORPHANS were also swept: `--redo` deletes only rows
still in the untested set, so a play that graduates proxy→real leaves its stale
proxy row behind (2024-01-19 ARM, 2024-02-06 SMH). Post-run overlap between the
two tabs is **0**, and structure-vs-play mismatches on both live tabs are **0**.

**v3 IS NOT FIXED, DELIBERATELY.** The frozen evidence base carries **31**
rows of this defect — `v3_BacktestResults` 4, `v3_BacktestProxy` 27 — and
re-running them would rewrite the basis every shipped rule in
`docs/deployment-rules.md` rests on. The affected rows cluster in
2026-02-17 → 2026-04-06 (plus 2025-03-14, 2026-07-29) and are almost all
`long_put`-for-`bear_put_spread` / `long_call`-for-`bull_call_spread`, i.e. the
**naked leg of a debit vertical**: unhedged downside, uncapped upside, and a
denominator (premium at risk) roughly 2–3× too large. Direction is right in
every case, so the sign of a per-structure effect is unlikely to flip; the
magnitudes on those 31 rows are not usable. Any study that reads a v3 structure
cut at n small enough for 31 rows to matter should say so. **Re-running v3 is an
operator decision, not a maintenance one** — recorded here, not taken.

**Two unrelated `no_strike` gaps found in passing, NOT fixed:**
`_extract_strikes` requires the keyword BEFORE the number, so `long 135 straddle`
(2024-01-29 XOP) and `~500-strike call` (2024-02-09 NVDA) yield no strikes and
go `unevaluable`. Different cause, different fix, left alone.

---

## 2026-08-14 — study-suite triage: the DEBIT_PROD exact-replay gate is **permanently unsatisfiable**, and `bear_position_study`'s R column is **partly contaminated**

**Status: DIAGNOSED, NOTHING FIXED, NO VERDICT CHANGED.** No study was re-run to
a conclusion and no shipped rule moves on this. The actionable list is
[`next-steps.md`](next-steps.md) §0c; only the two findings that bear on the
evidence base are recorded here.

`backtest_study run --all` fails six studies. Three (`bear_position_study`,
`exit_switch_mech_study`, `exit_switch_structure_study`) stop on the shared
DEBIT_PROD calibration gate: 289/301 exact, **12 HARD**, replay $22,510.70 vs
stored $27,655.70 (**−$5,145.00**, entirely from those 12).

**Finding 1 — the gate cannot pass again, and that is a consequence of shipping,
not a bug.** The 12 HARD rows are **12/12 mech cell BEAR_HE**, `trailing_stop`
occurs in no other cell (LVOL 0, RB_EVOL 0), and every one has
`created_datetime` after `31cb935` (2026-07-22 21:28). They are the **shipped
`regime_exit.cells.BEAR_HE` trail's own output**. Production resolves a per-row
effective config (`simulate.py:150-165`); the frozen harness replays one flat
profile and never sees the signal date (`harness.py:113`, `book.py:113`). The
gate therefore asserts a property production stopped having on 2026-07-22.
`exit_switch_mech_study.py:26-28` — "every DEBIT row reproduces DEBIT_PROD
exactly" — is now **false**. This does not disturb the BEAR_HE ship: its
pre-registered rollback trigger (≥25 new affected BEAR+H/E dates,
`deployment-evidence.md`) was always the forward mechanism and is untouched.

**Finding 2 — `bear_position_study`'s evidence base is contaminated, not merely
blocked.** The two exit-switch studies read stored outcomes *only* inside the
gate and re-`replay()` every reported table, so their estimands are clean.
**`bear_position_study.py:77` reads `realized_pnl_pct` off the row as `R`**, and
9 of the 12 affected rows are `bear_put_spread`/`long_put` — its exact
population. Its docstring line 13 ("R = realized_pnl_pct under PROD") is false
for those rows. **Its DEMOTE-criteria result at n=164 should not be re-quoted
until `R` is re-derived from `replay(t, **DEBIT_PROD)`.** The demotion itself
already shipped as card veto §1.4 on separate evidence (2026-08-13) and is not
withdrawn here; what is flagged is the study's own numbers.

**Method note for anyone re-checking this:** count rows in these exports with
`csv.DictReader`, **never `wc -l`** — embedded newlines inside `daily_price_csv`
inflate line counts roughly 4× (`results.csv` reads as 16 lines, 4 rows). Two
of the six failures were misjudged on `wc -l` counts before this was caught.

The other three failures carry no finding: `combined_exit_study` and
`underlying_exit_study` crash on deleted gitignored scratch inputs (retire
them — verdicts already recorded in `archive/02-credit-debit-split-attempts-8-12.md`),
and `v4_bridge` exit 3 is its designed refusal to compare a v3 book against
itself.

---

## 2026-08-14 — `selection_order` RUN: **POWER-STOPPED** at G0. Every re-ordering moves 7–14% of the book, so no arm reaches the pre-registered floor — nothing read, nothing refuted

**Status: BUILT AND RUN, same day as its registration. Verdict POWER-STOPPED.
Gates G1–G5 all PASS. No arm confirmed, no arm refuted, no O4 band drawn, and
NO re-run on these dates. Nothing ships — nothing could have.**

`scripts/backtest_study/selection_order.py`, run via
`python -m scripts.backtest_study run selection_order`. Six arms exactly as
registered; `simulate()`, caps, sizing and exits are `account_sim`'s, untouched.
ARM H off for every arm, compounding off (the study refuses to start if
`account-sim.yml` has it on).

**G0, which is the whole result.** The contested-date census, printed before
anything else:

| population | dates | contested | O1 | O2 | O3 | O1b |
|---|---|---|---|---|---|---|
| PRIMARY dense episodes | 46 | 26 (57%) | **10** | **7** | **11** | **10** |
| SECONDARY full book | 90 | 50 (56%) | 18 | 12 | 15 | 20 |

Affected dates, against a floor of **25** declared before the count was
knowable. Every arm is power-stopped on both populations; the best-powered arm
on PRIMARY is O3 at 11. PRIMARY exclusions run day3_cap 11 / net_delta 40 /
per_pos_delta 25, so contested dates are not scarce — 26 of 46 — but re-ordering
them barely moves the book: each arm changes only **7–14%** of O0's taken
positions (O2 the least at 7%, O3 the most at 14%).

**The power stop is enforced, not just announced.** The registration says a
stopped arm's "cells are not read", and an arm's mean R *is* its cell — so under
a total stop the arm table degrades to a census (positions and dates, both
knowable at entry) and the outcome columns are **withheld rather than printed
with a caveat beside them**. The O4 band is not drawn either: 200 draws exist to
serve criterion (7), and with no criterion to serve the distribution would be an
unregistered number with nothing attached to it. A number that is on the page
gets quoted eventually, whatever the caveat says.

**Gates.** G1 — B1 reproduces `220 / 90 / $63,553` exactly, and O0 built through
this study's arm plumbing is byte-identical to a walk built directly on
`protocol.ladder_rank` on both populations (72 / $11,399 and 160 / $11,248), so
the plumbing is neutral. G2 — all six arms **including an O4 draw** produce a
byte-identical book under both blindness layers; the rank functions read
`delta` / `entry_underlying` / `max_loss_per_contract` / `tier` and nothing else.
G3 — candidates partition exactly (150 PRIMARY, 297 SECONDARY) for every arm.
G4 — no annualised figure, Sharpe or time-to-recover, by construction. G5 —
satisfied **vacuously**, and it says so on the page: under a total power stop no
outcome number is printed at all, so nothing on the report could be adopted.
(G5 originally printed only inside a powered arm's block, which meant "no G5
line" and "G5 passed" looked identical from the outside; analyst A flagged it
and the gate now reports under every outcome.)

**The replication protocol earned its keep on this run.** Analysts A and B
agreed on all 13 rows (G0–G5, bars 1–7) on every pass — but between them they
caught **three** real defects in the first report, all now fixed and the report
regenerated. None of them moves a number; all three are the class of defect that
makes a report un-checkable by its next reader, which is what the two-analyst
pass is for.

1. **G5 never printed** (above). Graded `NOT EVALUABLE` rather than assumed
   passed, which is exactly the right call and the reason it got fixed.
2. **The anti-tuning block claimed "the random-control seed is fixed and
   printed" while no seed appeared anywhere** — because O4 never ran. The claim
   and the number had come apart. The seed (`20260814`, draw *i* uses `SEED + i`)
   now prints unconditionally, drawn or not.
3. **G0 printed *after* G1/G2**, while the registration says it "runs FIRST and
   blocks everything". The validator declined to call it a violation (logical
   precedence was satisfied — nothing readable was printed before it), but it
   required taking execution order on trust. All arms' books are now built
   first, G0 runs and prints for both populations before any other gate, and the
   two orders agree on the page.

Final grading: **no violations**, both analysts agree on every row, G0 NOT MET
(the power stop), G1–G5 MET, bars 1–7 NOT EVALUABLE. Also fixed on a code read
the analysts could not do (they see the report, not the source): the O4 band's
lower edge was computed at `alpha/2` while labelled `p5` — latent, never fired
here, and corrected to a true `[p5, p95]`.

**CARRY-FORWARD, explicitly NOT a verdict.** The reason the arms are
under-powered is itself the shape of `CAP-BOUND-NOT-ORDER-BOUND`: the caps
exclude the same picks whatever the order. It may **not** be recorded as that
verdict — the label requires arms that CLEAR G0, and reading a blocked arm's
shape as a conclusion is precisely the move a power stop exists to prevent. It
is a carry-forward for a re-registration on a materially larger book. Note also
that this does **not** refute `account_sim`'s post-hoc adverse-ordering
observation; it says this book cannot adjudicate it.

**Three implementation decisions, all coded before the first run:**

1. **Delta-notional is taken at the size the position would be OPENED**, not per
   contract — the resource the net cap meters is `|delta| × 100 × contracts ×
   underlying`, so ranking on the per-contract figure would rank on a quantity
   the constraint never sees. O2's ratio is size-INVARIANT (the count cancels),
   so it is computed per contract and means the same thing at any size.
   Degenerate rows are decided in the module, not at read time: no usable max
   loss → sorts last within tier (no reserved dollars to spend); zero
   delta-notional → sorts first (consumes none of the scarce resource). An
   unsizable row still holds its place in the order at one contract, because
   dropping it would change the candidate set, which this study may not do.
2. **`CAP-BOUND-NOT-ORDER-BOUND` needed two descriptive thresholds** the
   registration did not supply (|mean gain| < 0.05 R, < 10% of O0's taken picks
   changed). Coded before the first run and not moved. They label a verdict; they
   gate no adoption, and nothing ships under any label here.
3. **Registration-wording note: criterion (4) is unsatisfiable as written on
   PRIMARY.** "Positive in all three years" describes the full book
   (2024-06-17 .. 2026-04-07); the dense episodes span **two** calendar years, so
   requiring three would fail the criterion by construction rather than on
   evidence. Implemented as *every year present positive*, with an inline
   disclosure that prints whenever fewer than three years are in the cut. Never
   exercised this run — no arm was evaluated. **Fix the wording before any
   re-registration.**

**Do not re-run this on these dates.** The registered stop covers it. The only
thing that changes the answer is a materially larger book, and the same wall is
already blocking the whole hedge programme (all 30 ARM S cells, H2 at n=6).

---

## 2026-08-14 — `selection_order`: PRE-REGISTRATION → [`pre-registrations/selection_order.md`](pre-registrations/selection_order.md)

**Status: PRE-REGISTERED ONLY. Not built, not run, nothing shipped.**

`account_sim` follow-up (2) recorded the adverse cap ordering as **post-hoc**:
the picks the net delta cap excludes returned meanR +0.624 against +0.290 taken
at 0.25x/2.50x (+0.431 vs +0.278 at 1.50x), and loosening the cap doubled the
gap rather than relieving it. Cash binds zero times at both settings. This
registration is what makes a test of that observation admissible.

Six arms, frozen: `ladder_rank` (baseline), delta-notional ascending, reserved-$
per delta-notional, `|delta|` descending (the `bear_deploy` D4 transfer, never
run outside bear), one TIER-BLIND arm across A∪B (admissible only because A vs B
is statistically merged, p=.65), and a seeded random control. Unit is a
**contested date**, tested within-date paired against the baseline (the D4 method
— it cancels the date's level). The candidate bar is the full seven-part
conjunction: CI excluding zero, median positive among AFFECTED dates with ≥25 of
them, every LOO fold positive, all three years, the shipped exit config, the
ex-BOTH-windows cut added by hand, and above the random band.

Read the registration for the arm table, gates G0–G5 and the verdict grammar.

---
