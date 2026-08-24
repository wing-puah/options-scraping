# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index.

**State of play (2026-08-15, THE BARE EXPORT NAME IS NOT A POPULATION — studies
are era-scoped now, and four stored checksums are gone).** A re-export at 19:01
rewrote `backtests/to_evaluate/analysis - {BacktestResults,BacktestProxy,
AnalysisClaude}.csv` from 1,926/4,533/11,836 rows to 142/404/1,306. Nothing was
lost — the v3 tabs were exported alongside at 19:03 under `v3_` names — but the
bare filenames had silently changed era, and with them the population every
study reads.

**The failure was not the five studies that stopped.** `make study-all` reported
`ml_combination` (an unguarded `IndexError`), `calendar_hedge` (R3),
`account_sim` and its compounding arm (G1), and `selection_order` (G2). Those
were gates refusing a book that had collapsed from 795 records over 118 dates
(2024-06-17 .. 2026-04-07) to 74 over 10 (2024-01-10 .. 2024-02-20) — the
system working. **Fourteen other studies ran to completion on that 74-row book
and promoted their `-latest.txt`**, so a report contradicting its own recorded
verdict was indistinguishable on disk from a current one. `backtests/` is
gitignored and no earlier stamped copies survived; `53b7167` folded what could
still be recovered into this file and `archive/13`–`14` and marked the rest
not-retained.

**Cause.** A `vN_` bump renames the LIVE tabs in place, so the bare export name
means *whatever the live tab held at export time* — it is not a stable
population, and `lib/book.py` had no era concept at all. It never chose v3; it
inherited v3 because that is what those filenames used to contain.
`archive/09-v3-closeout.md` recorded the assumption that broke — *"Study code is
unaffected — it reads CSV exports by filename, not tabs"* — which was true of
the filename and false of its contents. `run.py`'s provenance header already
carried row counts and mtimes; both moved, and both look like an ordinary
refresh.

**Fix — `scripts/backtest_study/lib/era.py`, the single encoding.** A study runs
on ONE era, names it in its header, and refuses if the exports are not it.
Detection is `score_flow` PRESENT AND POPULATED (v3 dropped it at the bump and
it is not coming back); presence alone is wrong, because `RESULT_COLUMNS`
deliberately keeps the column on v4 so loaders keep working — v3 results are
406/406 non-blank, v4 0/30. `load_book` resolves paths per era, refuses (exit 3)
on a requested-vs-actual mismatch or on exports that disagree with each other,
and refuses (exit 2) below a shared 30-date power floor. `--era v3` reruns a past
era. Both codes are inherited by EVERY study from the runner rather than
restated per module. A genuine failure now DELETES `-latest.txt` — safe only
because the common non-zero exit became a promoted refusal.

**Four stored checksums deleted, not repaired.** `account_sim` G1,
`selection_order` G1 and `calendar_hedge` R3 all compared the book against
`220 positions / 90 dates / $63,553`. That is a fingerprint of one export, not a
hypothesis: it breaks on every legitimate refresh, which teaches the operator to
edit it, which is what destroys it as a check. The property they were really
guarding — that the FROZEN `harness.py` still replays identically — is a CODE
claim and now lives in `tests/test_harness_replay.py`, 28 rows covering all nine
reachable exit reasons, both sides, the rounding clamp and seven exit-priority
collisions. Of eleven perturbations of `harness.py`, nine fail the test; the two
that do not are unreachable from v3 data and are recorded as gaps.
`calendar_hedge` R4 KEEPS its constants deliberately — it is a re-implementation
check against a cache snapshot, which is exactly what a fixed expectation should
catch. The calibration numbers G1 printed survive as descriptive provenance
under a banner that renders no verdict. **Gate ids were NOT renumbered**: G2–G5
are named in the pre-registrations and in recorded verdicts, and sliding them
down one would silently re-point that prose.

**Reading older entries.** Verdicts below that quote `G1: PASS` or
`expected (account-sim.yml gates.book_calibration): 220 / 90 / $63,553` are
quoted verbatim from runs where that gate existed. They stand as recorded; the
gate does not. Nothing in a shipped rule moved.

**What this means for v4.** Current-era-only is now the policy — prior eras'
results live here, in prose, with their population stated, rather than being
pooled into a live book. v4 today is 14 dates: 4 of ordinary 2026 cadence
(08-11 .. 08-14) and 10 backfilled neutral dates (2024-01-10 .. 02-20) from
`enrich_queue_pilot`, which are the only ones carrying backtest rows yet. So most
studies will REFUSE until v4 clears 30 dates. That is the honest output of a
young era, not a regression — and with queues a/b cleared to run, the backfill
will clear it far faster than the daily cadence would.

**State of play (2026-08-15, `enrich_queue_pilot` COMPLETE — kill switch NOT
FIRED, queues a/b are GO).** The first 10 neutral dates are scraped, enriched,
analysed and backtested; **9 of 10 produced ≥1 priceable A/B-tier row** against
the pre-declared stop at <4, so the neutral-date deployed yield (0.90) came in
*above* the 0.763 signal-rich assumption, not below it. Robust to the known
§1.3 research-ladder gap (no date's deployed status rests on a RANGE+L-VOL
credit row). Pilot progress carried into `enrich_queue_a.txt.done`; the
remaining 143 dates (queue_a + queue_b) are cleared to run. Entry below. Prior
state follows.

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
[`pre-registrations/f4_deployment/selection_order.md`](pre-registrations/f4_deployment/selection_order.md).
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

## 2026-08-15 — `enrich_queue_pilot` COMPLETE: kill switch NOT fired — neutral-date deployed yield **9/10**, above the 0.763 assumption. Queues a/b are GO

**Status: pre-declared criterion evaluated and PASSED. No threshold moved, no
rule changed.** The pilot (`backtests/enrich_queue_pilot.txt`, the first 10
dates of the neutral list in queue_a order) asked one question: does the
deployed-date yield survive on *neutral* (calendar-selected) dates, when the
0.763 it was measured at came from signal-rich ones? Stop rule, declared before
anything ran: **fewer than 4 deployed dates out of 10 → stop.**

*Run record.* All 10 dates (`2024-01-10 → 2024-02-20`) completed every stage —
scrape, compile, enrich, counterpart-iv, iv-percentile, price-catalyst,
analyze, backtest (`enrich_queue_pilot.txt.done`). Fresh tab exports pulled to
`backtests/to_evaluate/`; the pooled book loads **74 priceable records (30 real
/ 44 tweak; 2 proxy rows excluded by the exact-replay gate, 0 bs admitted)**
via `scripts/backtest_study/lib/book.py::load_book` defaults.

*Tier count (deployed = ≥1 priceable A/B row, `book.ladder_tier` — same
membership basis as the 90/118 = 0.763 measurement):*

| date | rows | A | B | deployed |
|---|---|---|---|---|
| 2024-01-10 | 3 | 0 | 1 | yes |
| 2024-01-16 | 8 | 2 | 0 | yes |
| 2024-01-19 | 10 | 0 | 4 | yes |
| 2024-01-24 | 9 | 0 | 6 | yes |
| 2024-01-29 | 10 | 3 | 3 | yes |
| 2024-02-01 | 9 | 0 | 2 | yes |
| 2024-02-06 | 7 | 0 | 4 | yes |
| 2024-02-09 | 6 | 0 | 1 | yes |
| 2024-02-14 | 4 | 0 | 0 | **no** |
| 2024-02-20 | 8 | 0 | 5 | yes |

**9/10 ≥ 4 → the kill switch does not fire.** Only 2024-02-14 yields nothing
(4 rows, all Tier C). Sensitivity to the §1.3 gap recorded in the entry below
(research ladder admits RANGE+L-VOL credit rows production vetoes): re-counting
with that veto applied changes **nothing** — no date's deployed status rests on
such a row, 9/10 either way. Zero VETO rows in the pilot at all.

*Caveats, so the yield is not over-read:* (a) several dates deploy on
tweak-priced rows only (01-10, 01-24, 02-01, 02-09) — standard pooled-book
basis, but the real-priced-only count would be 5/10, still ≥4; (b) Jan–Feb 2024
is one contiguous calm-bull stretch — the 143 remaining dates span the full
window and will re-measure the yield continuously; (c) this entry reads
NOTHING about outcomes (P&L/R untouched) — outcome reads wait for the full
expansion per the 08-14 pre-registration.

*Trap recorded:* `backtests/results.csv` / `proxy_results.csv` are **per-run
scratch** — each backtest run rewrites them with only that run's increment
(timestamped siblings accumulate). Reading them as the book showed "1 deployed
date"; the Sheets tab exports are the authority. Never evaluate a multi-run
campaign off the bare scratch files.

*Actions taken:* pilot progress carried forward per the pilot file's own
instruction (`cat enrich_queue_pilot.txt.done >> enrich_queue_a.txt.done`), so
queue_a resumes past the 10 done dates. **Next: run
`./scripts/scrape_and_enrich.sh backtests/enrich_queue_a.txt` and
`…enrich_queue_b.txt` (disjoint ranges, parallel-safe), then per-date analyze +
`make backtest-all` — 143 dates ≈ 143–215 h at the corrected 1–1.5 h/date.**

## 2026-08-15 — `account_sim --live-select` ARM ADDED: the shipped selector run under history. **150 ranked candidates were never priceable, 37 deploy slots were filled from below the selector's own top-3, and the research ladder is missing the §1.3 credit veto on 21 export rows**

**Status: ARM ADDED, nothing adopted. No pre-registered criterion is evaluated by
this arm, no threshold moved, and the frozen `account_sim` book is byte-identical
(verified by diff — only the provenance header and the already-committed verdict-
label amendment differ).** Run 2026-08-15 13:30:02, git ce9dcae (dirty), 08-11
v3 exports (1,926 / 4,533 / 11,836); positions export 566 rows. Report and
positions CSV not retained on disk — the excerpt at the end of this section IS
the record.

*What the arm is.* `account_sim` re-implements the deployment ladder in
`scripts/backtest_study/lib/book.py::ladder_tier`. The function that actually decides
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


<details>
<summary>Report excerpt, verbatim — run 2026-08-15 13:30:02, git ce9dcae (dirty), 08-11 v3 exports; header, then the arm's own sections from LIVE SELECT to CLOSE</summary>

```text
==============================================================================
STUDY: account_sim-live-select
==============================================================================
  run at    2026-08-15 13:30:02
  command   python -m scripts.backtest_study.account_sim --live-select --live-select-no-llm
  git       ce9dcae (main, working tree dirty)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
   4,533 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestProxy.csv
  11,836 rows  2026-08-11 17:24  backtests/to_evaluate/analysis - AnalysisClaude.csv
     805 rows  2026-08-15 12:38  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================

==============================================================================

[... lines 16-216 elided ...]

LIVE SELECT — the SHIPPED selector (recommend.rank + judge) under history
==============================================================================
  This arm replaces account_sim's own ladder (book.py::ladder_tier) with the
  function that actually decides what gets deployed: scripts/journal/recommend.py's
  rank() — which encodes config/deployment-rules.md §1-§3 exactly once, via
  scripts/live_loop/mapping.ladder_tier — followed by judge(), the single
  demote-only model call. Pricing, sizing, admission and exit replay are
  account_sim's frozen machinery, unchanged and unreachable from here.

  NOT the frozen basis and not a criterion. A1-A6 were pre-registered against the
  frozen selector and DO NOT TRANSFER to a different candidate set; none of them
  is evaluated here. What this arm reports is coverage, divergence, and the two
  books the selector produces — no verdict, no adoption.

  entry check   ibkr_verified
  judgment      NOT RUN (--live-select-no-llm) — deterministic rank() only
  budget check  recommend.DEPLOY_BUDGET=3 ==
                account.max_positions_per_day=3  OK

  analysis source: /Users/wing/claude_playground/options-trading/backtests/to_evaluate/analysis - AnalysisClaude.csv

==============================================================================
SELECTION COVERAGE — what the selector saw, and what it could never see
==============================================================================
  The frozen book only ever ranks rows the backtest could PRICE. This section
  asks the other question: of every play the analysis actually emitted, which
  ones reached selection at all. No P&L, no dollars, no ledger effect — a row
  counted here as unpriceable is never deployed and never assigned an outcome.

  analysis population   1,448 (date, ticker) pairs over 142 dates
                        1,465 play rows (17 extra rows on
                        pairs carrying more than one play)
  entry check           ibkr_verified: 765 of 1,465 play rows joined a
                        measured entry-side delta; 700 got none

--- every analysis pair, in exactly one bucket ------------------------------
     423  §4 hedge-sleeve candidate (never a selection play)
     283  ranked as a deploy candidate, priceable
     239  date never reached selection (no priceable row that session)
     184  Tier C (capital-constrained)
     169  §1 VETO
     150  ranked as a deploy candidate, UNPRICEABLE
   1,448  TOTAL          residual against the 1,448-pair population: 0

--- ranked but unpriceable, by cause ----------------------------------------
     107  bs_options_hist
      28  unevaluable
       8  no_evaluation_row
       4  structure_mismatch
       3  withheld_by_calibration_gate

  by year: 2024=30  2025=82  2026=38

--- displacement — deploy slots filled from below the selector's own top-3 --
  37 deploy slot(s) across 31 session(s) went to a play the selector
  itself ranked BELOW its own top-3, purely because a higher-ranked candidate had
  no priceable record. That is the honest size of the pricing bias in the frozen
  book's composition — a book selected on structure would not contain them.

--- composition against the frozen book's picks -----------------------------
  frozen picks 220   live-select offers 208   shared 182
  only frozen  38   only live-select 26
  by structure, frozen:      bull_call_spread=179  bull_put_spread=41
  by structure, live-select: bull_call_spread=175  bull_put_spread=33

--- §3 entry check — what the ladder can verify, in both modes --------------
  rank() outcome                      ibkr_verified  analysis_only
  deploy Tier A                                 231            231
  deploy Tier B                                 248            195
  deploy Tier B (partial)                        44            105
  hedge Tier C                                  524            524
  rejected C                                    218            210
  rejected VETO                                 200            200

  This run selected under: ibkr_verified

==============================================================================
LADDER DIVERGENCE — the research ladder against the shipped one
==============================================================================
  book.py::ladder_tier is a 2026-07 port of the deployment ladder; production
  encodes the same rules once, in scripts/live_loop/mapping.ladder_tier. The port
  has since fallen behind. Every disagreement below is a row the simulation and
  the live card would treat differently — itemised by cause, not asserted.

--- candidate universe: 795 book records ------------------------------------
    13  §1.3 credit veto (RANGE + L-VOL)
    13  TOTAL

  by tier transition (book -> shipped): B->VETO=3  C->VETO=10
  by source:    real=7  tweak=6
  by structure: bull_put_spread=13

--- §1.3 credit veto, counted on the RAW exports ----------------------------
  The clause the port is missing: a CREDIT play in a RANGE + L-VOL market is a
  §1 veto in production and a Tier-B deploy candidate in the port. Counted on the
  export rows themselves, before the book drops duplicates, bs_options_hist rows,
  and rows that fail the exact-replay gate.
     7  BacktestResults
    14  BacktestProxy
    21  TOTAL   by structure: bull_put_spread=21

==============================================================================
JUDGMENT LAYER — one model pass, two ledger walks, and what it moved
==============================================================================
  NOT RUN (--live-select-no-llm). Both ledger walks below are the deterministic
  rank() ordering, so demote_policy skip and ignore are identical BY CONSTRUCTION
  and their agreement says nothing about the judge layer. Re-run without the flag
  to measure it.

==============================================================================
BOOKS — frozen selector against the shipped selector, both demote policies
==============================================================================
  Same ledger, same sizing, same frozen exit replay. The only difference is who
  chose.
  judge() did not run, so the skip/ignore pair is identical by construction and
  bounds nothing. It is printed anyway rather than hidden — a section that
  appears only on some runs is a section a reader stops looking for.

  book                                  n  dates      dollars    mean R     win
  frozen ladder (book.py)             160     77       11,248    +0.159     56%
  live-select, demote=skip            153     75       15,183    +0.201     58%
  live-select, demote=ignore          153     75       15,183    +0.201     58%

--- demote_policy delta — the judge layer's whole effect --------------------
  positions only under skip: 0   only under ignore: 0   shared: 153
  dollars  skip $15,183   ignore $15,183   difference $+0

==============================================================================
GATES — G5 re-run with this arm's selector, plus G6 (G1-G4 stay pinned to the frozen basis)
==============================================================================

--- G5 (arm) — the SHIPPED selector is BLIND to how a position turned out ---
  Every record is re-wrapped so reading an outcome key raises, AND the outcome
  columns are deleted from the underlying trade row so a read cannot route
  around the wrapper. Both ledger walks must then complete and produce a
  byte-identical book.
  [skip] positions: sighted 153  blind 153  differing 0
  [ignore] positions: sighted 153  blind 153  differing 0
  G5 (arm): PASS

--- G6 — nothing reaches the ledger that rank() did not clear ---------------
  The never-promote invariant, enforced at the sim boundary as well as inside
  recommend.judge(). A ticker in the deploy set that was not a Part-A survivor on
  that date is a promotion, and a promotion is the one thing the model layer is
  structurally forbidden to do.
  sessions checked: 236 (2 ledger walks x 118 sessions)   violations: 0
  G6: PASS

==============================================================================
CLOSE
==============================================================================
  Nothing ships from this arm. It reports coverage and divergence; it evaluates
  no pre-registered criterion, and the frozen book above it is untouched.
  positions CSV: 566 rows -> backtests/study_output/account_sim-positions-live-select-latest.csv

==============================================================================
exit code 0 after 11.4s
==============================================================================
```

</details>
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

`scripts/backtest_study/f4_deployment/selection_order.py`, run via
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


<details>
<summary>Report excerpt, verbatim — run 2026-08-14 12:55:17, git 9c53244 (clean), 08-11 v3 exports; header, then G0 through CLOSE</summary>

```text
==============================================================================
STUDY: selection_order
==============================================================================
  run at    2026-08-14 12:55:17
  command   python -m scripts.backtest_study.selection_order
  git       9c53244 (main, working tree clean)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
   4,533 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestProxy.csv
  11,836 rows  2026-08-11 17:24  backtests/to_evaluate/analysis - AnalysisClaude.csv
     803 rows  2026-08-13 11:56  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================

==============================================================================

[... lines 16-178 elided ...]

[PRIMARY dense episodes] G0 — POWER PRE-CHECK (runs FIRST; blocks every read below)
==============================================================================
  Unit of observation = a CONTESTED DATE: >=2 eligible candidates and >=1
  exclusion in {day3_cap, net_delta, per_pos_delta}. Uncontested dates are identical
  across arms BY CONSTRUCTION and are excluded from the paired test — including
  them is the zero-inflation that failed exit_switch_mech's LOO median gate.

  An arm under 25 AFFECTED dates is POWER-STOPPED: its cells are not read
  and no criterion is evaluated on it. This threshold was declared in the
  pre-registration BEFORE the count was knowable, which is the whole point.

  deployed signal dates              46
  CONTESTED dates                    26  (57% of the population)
  exclusions in the contest buckets (population-wide): day3_cap 11  net_delta 40  per_pos_delta 25

  arm    affected dates  changed picks  of O0 taken   status
  O1                 10              8         11%   POWER-STOPPED
  O2                  7              5          7%   POWER-STOPPED
  O3                 11             10         14%   POWER-STOPPED
  O1b                10              9         12%   POWER-STOPPED

  arms cleared for reading: NONE — every arm power-stopped

==============================================================================
[SECONDARY full book] G0 — POWER PRE-CHECK (runs FIRST; blocks every read below)
==============================================================================
  Unit of observation = a CONTESTED DATE: >=2 eligible candidates and >=1
  exclusion in {day3_cap, net_delta, per_pos_delta}. Uncontested dates are identical
  across arms BY CONSTRUCTION and are excluded from the paired test — including
  them is the zero-inflation that failed exit_switch_mech's LOO median gate.

  An arm under 25 AFFECTED dates is POWER-STOPPED: its cells are not read
  and no criterion is evaluated on it. This threshold was declared in the
  pre-registration BEFORE the count was knowable, which is the whole point.

  deployed signal dates              90
  CONTESTED dates                    50  (56% of the population)
  exclusions in the contest buckets (population-wide): day3_cap 30  net_delta 55  per_pos_delta 50

  arm    affected dates  changed picks  of O0 taken   status
  O1                 18             18         11%   POWER-STOPPED
  O2                 12             12          8%   POWER-STOPPED
  O3                 15             16         10%   POWER-STOPPED
  O1b                20             20         12%   POWER-STOPPED

  arms cleared for reading: NONE — every arm power-stopped

==============================================================================
G1 — CALIBRATION: O0 reproduces the default account_sim run exactly
==============================================================================
  An ordering study whose BASELINE does not reproduce production is
  measuring its own bug. Two checks: the book line a prior account_sim report
  printed on these same exports, and a byte-identical book between O0 (built
  through this study's arm plumbing) and a walk built directly on
  protocol.ladder_rank — proving the plumbing is neutral.

  B1 (stored contracts, stored R): 220 positions / 90 dates / $63,553
  expected (account-sim.yml gates.book_calibration): 220 / 90 / $63,553
  book line: PASS
  [PRIMARY dense episodes] O0 vs direct ladder walk: 72 vs 72 positions, $11,399 vs $11,399  -> identical
  [SECONDARY full book] O0 vs direct ladder walk: 160 vs 160 positions, $11,248 vs $11,248  -> identical
  G1: PASS

==============================================================================
G2 — BLINDNESS: no arm's rank function may read an outcome
==============================================================================
  Every record is re-wrapped so reading an outcome key RAISES, and the
  outcome columns are DELETED from the underlying trade row so a read cannot
  route around the wrapper. Each arm must then produce a byte-identical book.
  A rank function that peeks is worthless, and the point of this study is a
  rule an agent could run live.
  row columns deleted from every Trade: days_held, exit_reason, mae_day, mae_pct, mfe_day, mfe_pct, pnl_at_cap_pct, realized_pnl_pct

  [PRIMARY dense episodes] tripwire live: True
    O0          sighted   72  blind   72  differing   0  -> identical
    O1          sighted   77  blind   77  differing   0  -> identical
    O2          sighted   77  blind   77  differing   0  -> identical
    O3          sighted   76  blind   76  differing   0  -> identical
    O1b         sighted   77  blind   77  differing   0  -> identical
    O4[draw 0]  sighted   72  blind   72  differing   0  -> identical

  [SECONDARY full book] tripwire live: True
    O0          sighted  160  blind  160  differing   0  -> identical
    O1          sighted  169  blind  169  differing   0  -> identical
    O2          sighted  166  blind  166  differing   0  -> identical
    O3          sighted  160  blind  160  differing   0  -> identical
    O1b         sighted  168  blind  168  differing   0  -> identical
    O4[draw 0]  sighted  167  blind  167  differing   0  -> identical

  G2: PASS

==============================================================================
PRIMARY DENSE EPISODES — arms, band, and the seven-part bar
==============================================================================

--- [PRIMARY dense episodes] the five deterministic arms — CENSUS ONLY (G0 power stop: no outcome column is printed) 
  arm   positions  dates   ordering
  O0           72     37  ladder_rank — tier, then score_total tie-break
  O1           77     38  delta-notional ASCENDING, within tier
  O2           77     39  reserved-$ per unit delta-notional, DESCENDING, within tier
  O3           76     38  |delta| DESCENDING, within tier
  O1b          77     38  delta-notional ASCENDING, TIER-BLIND across A u B

--- [PRIMARY dense episodes] O4 — NOT RUN  (seed 20260814, 200 draws, not taken) 
  The null band exists to serve criterion (7). Every arm is power-stopped, so there is no
  criterion to serve and the 200 draws are not taken. The seed is stated anyway (20260814) so the
  arm is reproducible by anyone re-running it on a larger book.

==============================================================================
SECONDARY FULL BOOK — arms, band, and the seven-part bar
==============================================================================

--- [SECONDARY full book] the five deterministic arms — CENSUS ONLY (G0 power stop: no outcome column is printed) 
  arm   positions  dates   ordering
  O0          160     77  ladder_rank — tier, then score_total tie-break
  O1          169     79  delta-notional ASCENDING, within tier
  O2          166     80  reserved-$ per unit delta-notional, DESCENDING, within tier
  O3          160     75  |delta| DESCENDING, within tier
  O1b         168     77  delta-notional ASCENDING, TIER-BLIND across A u B

--- [SECONDARY full book] O4 — NOT RUN  (seed 20260814, 200 draws, not taken) 
  The null band exists to serve criterion (7). Every arm is power-stopped, so there is no
  criterion to serve and the 200 draws are not taken. The seed is stated anyway (20260814) so the
  arm is reproducible by anyone re-running it on a larger book.

==============================================================================
G3 — ATTRIBUTION: candidates partition into taken + census buckets, per arm
==============================================================================
  The A4 identity, re-asserted per arm. A mismatch FAILS the run.

  [PRIMARY dense episodes] candidates offered per arm: 150
    O0    taken   72  exclusions   78  sum  150 vs candidates  150  -> OK
    O1    taken   77  exclusions   73  sum  150 vs candidates  150  -> OK
    O2    taken   77  exclusions   73  sum  150 vs candidates  150  -> OK
    O3    taken   76  exclusions   74  sum  150 vs candidates  150  -> OK
    O1b   taken   77  exclusions   73  sum  150 vs candidates  150  -> OK

  [SECONDARY full book] candidates offered per arm: 297
    O0    taken  160  exclusions  137  sum  297 vs candidates  297  -> OK
    O1    taken  169  exclusions  128  sum  297 vs candidates  297  -> OK
    O2    taken  166  exclusions  131  sum  297 vs candidates  297  -> OK
    O3    taken  160  exclusions  137  sum  297 vs candidates  297  -> OK
    O1b   taken  168  exclusions  129  sum  297 vs candidates  297  -> OK

  G3: PASS

==============================================================================
G4 — no annualised figure, Sharpe, or time-to-recover appears anywhere
==============================================================================
  By construction: this study prints mean R, a paired within-date
  difference, dollar sanity checks, and counts. It computes no return per unit
  time and no risk-adjusted ratio, so there is nothing to annualise.
  G4: PASS

==============================================================================
G5 — OUT-OF-FOLD DISCIPLINE: what on this page is adoption-eligible
==============================================================================
  In-sample tables are labelled as such. The ONLY adoption-eligible
  numbers are LOO folds and protocol.walk_forward_splits TEST rows.

  [PRIMARY dense episodes] every arm POWER-STOPPED at G0, so NO outcome number was printed at all —
    no arm mean R, no paired gain, no band, no LOO fold, no TEST row. There is nothing
    on this page that could be adopted, so the discipline is satisfied VACUOUSLY.

  [SECONDARY full book] every arm POWER-STOPPED at G0, so NO outcome number was printed at all —
    no arm mean R, no paired gain, no band, no LOO fold, no TEST row. There is nothing
    on this page that could be adopted, so the discipline is satisfied VACUOUSLY.

  G5: PASS

==============================================================================
VERDICT (PRIMARY dense episodes — grammar worded in the pre-registration)
==============================================================================
  arms powered (G0):  none
  arms clearing all seven: none

  Best-powered arm reached 11 affected dates against a threshold of 25.

  CENSUS OBSERVATION, explicitly NOT a verdict upgrade: the reason the arms are
  under-powered is itself informative — each one changes only 7-14% of O0's
  taken positions, because on most contested dates the caps exclude the same
  picks whatever the order. That texture is what CAP-BOUND-NOT-ORDER-BOUND
  describes. It may NOT be recorded as that verdict: the label requires arms
  that CLEAR G0, and reading a blocked arm's shape as a conclusion is exactly
  the move the power stop exists to prevent. It is a carry-forward for a
  re-registration on a materially larger book, nothing more.

  VERDICT: POWER-STOPPED — every arm fell under 25 affected dates. Census only; nothing read, and NO re-run on these dates.

==============================================================================
STANDING CAVEAT (required by the pre-registration to appear here)
==============================================================================
  The ladder is itself IN-SAMPLE (fitted on this book), so an ordering
  evaluated on the same book is SECOND-ORDER in-sample. The only mitigations are
  that these are mechanical entry-side rules with no fitted thresholds, and that
  adoption requires out-of-fold survival. That caveat does not disappear if the
  numbers look good, and it is why nothing ships from this study under any
  outcome.

  Anti-tuning: arms frozen at six. Caps, capital, risk %, positions/day,
  take_floor, downsize and the exit profile are NOT swept — they come from config
  and are held at their committed values for every arm. No new columns. Every
  arm's result is reported regardless of outcome, including the ones that lose.
  Random-control seed: 20260814 (fixed; draw i uses SEED + i over 200 draws). Stated here
  whether or not O4 was drawn, so the claim and the number never come apart.

==============================================================================
CLOSE
==============================================================================
  verdict: POWER-STOPPED — every arm fell under 25 affected dates. Census only; nothing read, and NO re-run on these dates.
  G1: PASS
  G2: PASS
  G3: PASS
  G4: PASS
  G5: PASS
  G0: POWER STOP FIRED on every arm

==============================================================================
exit code 0 after 2.9s
==============================================================================
```

</details>

<details>
<summary>Two-analyst replication — digest (verbatim, 2026-08-14)</summary>

````text
```markdown
# Plain-language digest: selection_order study (2026-08-14)

## Bottom line up front

**Nothing ships from this study — not because the ordering idea failed, but because there wasn't enough data to test it at all.** Every version of "try a different pick order" hit a data-size tripwire before any profit-and-loss number was even calculated. The report is honest about this: it prints zero win-rate or dollar numbers for any of the four alternate orderings it tried, on purpose, because printing them would have been misleading.

## What the study was asking

Right now, when more than one trade candidate wants a slot on a given day, the system picks in a specific order (tier first, then a score). This study asked: **if we instead sorted the queue a different way — e.g., smallest position-size-impact first — would the account's limited risk budget get spent on better trades?**

It is explicitly framed as research-only: "NOTHING SHIPS FROM THIS STUDY UNDER ANY OUTCOME." That's stated up front, not as a hedge after a disappointing result — win or lose, this study was never going to change how the system trades.

## The account being simulated

This reuses the exact account setup from the account-feasibility study, unchanged: $25,000 starting capital, $500 (2%) risked per position, up to 3 new positions per day, a cap of 25% of equity on any single position's market exposure, and a cap of 250% of equity on the whole book's net exposure. Exit rules (when to take profit, stop out, or time out of a trade) are also frozen at whatever's currently shipped — this study only reorders *which* trades get taken when the day's slots are full, never *when* to exit them.

## The trade population

The underlying book has 795 recorded trades spanning June 2024 to April 2026. Two views of it are used:
- **PRIMARY (dense episodes):** 3 unbroken stretches of active trading, 46 dates total. This is the "clean" dataset — continuous trading with no long gaps.
- **SECONDARY (full book):** all 118 dates including gaps. This view is only ever a sanity check, never a standalone basis for a conclusion — that's a standing rule in how these studies are read.

## G0 — the power check that ended the study (PRIMARY and SECONDARY)

This is the step that decided everything. The study only cares about days where the ordering *could possibly matter* — days with at least 2 competing candidates where at least one got excluded by a cap. It calls these "contested dates."

- PRIMARY: 26 of 46 dates (57%) were contested.
- SECONDARY: 50 of 90 dates (56%) were contested.

The rule, decided *before* the study ran (so it couldn't be gamed after seeing results): any ordering variant that changes the account's picks on fewer than 25 contested dates doesn't get its results read at all — there just isn't enough evidence to trust a conclusion.

None of the four alternate orderings came close:

| Arm (ordering rule) | PRIMARY affected dates | SECONDARY affected dates |
|---|---|---|
| O1 — smallest exposure-impact first | 10 | 18 |
| O2 — most reserved-$ per unit of exposure first | 7 | 12 |
| O3 — largest position-delta first | 11 | 15 |
| O1b — smallest exposure-impact first, ignoring tier | 10 | 20 |

All four fell well short of 25. Result: **every arm is "POWER-STOPPED"** — the study auto-blocked itself from printing any win-rate, average return, or dollar outcome for any of them, on both views of the data. This is the mechanism working as designed, not a bug.

## G1 — does the study's baseline match production?

Before trusting a study that reorders trades, you need to know its "no change" baseline (O0) actually reproduces what the real system does. It does: 220 positions across 90 dates worth $63,553 — matching the number a prior report already validated, exactly, and matching a second independently-built version of the same walk byte-for-byte. **Passed.**

## G2 — could the ordering rules cheat by peeking at outcomes?

Each ordering rule is only allowed to use information available *before* a trade's result is known (size, exposure, tier) — never its actual profit or loss, since that would be an unfair advantage no live trading system would have. The study rigged every trade record so that reading an outcome value raises an error, then re-ran every ordering rule under that trap. Every arm produced an identical book with the trap on vs. off. **Passed** — none of the orderings were secretly cheating.

## G3 — does every candidate get accounted for?

For each ordering, every candidate trade must land in exactly one bucket: taken, or excluded for a specific reason (cap-related). The counts must add up to the total candidate pool with nothing lost or double-counted. They did, for every arm, on both views. **Passed.**

## G4 — no fancy risk-adjusted metrics snuck in

This study never computes anything like an annualized return or a Sharpe ratio (metrics that can make thin or lucky data look more impressive than it is), so there's nothing to check here beyond confirming they don't appear. **Passed** (trivially, by construction).

## G5 — no in-sample number is being mistakenly relied on

Because the power-stop fired for every arm, literally zero outcome numbers were ever printed anywhere in this report — no arm's average return, no comparison between orderings, no dollar figures. So there's nothing that could accidentally be mistaken for a validated result. **Passed**, again by having nothing to check.

## The "census" tables — counts only, no performance

Since every arm was power-stopped, the report shows *only* how many positions/dates each ordering would have produced — never whether those trades made or lost money. Treat these as a shape check, not a performance comparison:

**PRIMARY:**
| Ordering | Positions | Dates |
|---|---|---|
| O0 (current/deployed) | 72 | 37 |
| O1 | 77 | 38 |
| O2 | 77 | 39 |
| O3 | 76 | 38 |
| O1b | 77 | 38 |

**SECONDARY:**
| Ordering | Positions | Dates |
|---|---|---|
| O0 (current/deployed) | 160 | 77 |
| O1 | 169 | 79 |
| O2 | 166 | 80 |
| O3 | 160 | 75 |
| O1b | 168 | 77 |

The counts are all in a similar ballpark — none of the reorderings dramatically inflates or shrinks the number of trades taken.

## O4 — the "is this better than random?" control, skipped

The study had planned a fifth arm: 200 random shuffles of the queue, to check whether any real ordering beats pure chance. Because there was no valid result to compare against (every real arm was power-stopped), this random-draw control was never run. The random seed (20260814) is published anyway, so if this study is re-run later on a bigger dataset, the random control is reproducible.

## Verdict

**POWER-STOPPED** on both the clean dataset and the full book. No ordering rule cleared the minimum evidence bar, so nothing was read and nothing is being recommended for a re-run on this same data.

One observation is flagged explicitly as *not* a finding: each alternate ordering only changed 7–14% of which trades actually got taken. That hints the account's caps — not the pick order — are usually what decides the day's trades regardless of how you sort the queue. The report is careful to say this texture **may not** be promoted to a real conclusion ("cap-bound, not order-bound") — that label specifically requires an arm that clears the power check, and none did. It's logged only as something worth re-testing if/when there's a bigger dataset.

## Standing caveat (carried forward, not to be dropped)

Two caveats apply regardless of outcome, and would apply even if the study *had* produced results:

1. **The trade-picking system (the "ladder") was itself built using this same historical book.** So testing a new ordering rule on the same book is testing something twice-fitted to the same data — a second layer of the classic "graded your own homework" problem. The only real check on that is testing on data the system has never seen, which this study didn't do.
2. **Anti-tuning discipline:** the study locked in exactly 6 ordering variants ahead of time and did not let itself sweep caps, capital, risk-per-trade, positions-per-day, or exit rules looking for a better combination — those all stayed at their currently-shipped values. Every arm's result was reported regardless of whether it looked good or bad (in this case, none produced a readable result at all).

## Close

All five structural gates (G1 baseline match, G2 no outcome-peeking, G3 full accounting, G4 no misleading risk metrics, G5 no stray in-sample numbers) **passed**. The one gate that actually governs whether any performance number gets read — G0, the power pre-check — **fired and blocked every arm**. Net effect: this run tells you the study's plumbing is trustworthy, but it does not tell you whether a different pick order would help or hurt. That question stays open until it can be tested on a materially larger dataset.
```
````

</details>

<details>
<summary>Two-analyst replication — review-analyst-a (verbatim, 2026-08-14)</summary>

```text
==============================================================================
STUDY: selection_order
==============================================================================
  run at    2026-08-14 12:07:03
  command   python -m scripts.backtest_study.selection_order
  git       beb1219 (main, working tree dirty)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
   4,533 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestProxy.csv
  11,836 rows  2026-08-11 17:24  backtests/to_evaluate/analysis - AnalysisClaude.csv
     803 rows  2026-08-13 11:56  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================

| Criterion/Gate | Verdict | Exact number(s) read from report | What would change the verdict |
|---|---|---|---|
| G0 — power pre-check (≥25 affected dates per arm) | NOT MET | PRIMARY: `deployed signal dates 46`, `CONTESTED dates 26  (57% of the population)`; `O1 10 8 11% POWER-STOPPED`, `O2 7 5 7% POWER-STOPPED`, `O3 11 10 14% POWER-STOPPED`, `O1b 10 9 12% POWER-STOPPED`; `arms cleared for reading: NONE — every arm power-stopped`. SECONDARY: `deployed signal dates 90`, `CONTESTED dates 50  (56% of the population)`; `O1 18 18 11%`, `O2 12 12 8%`, `O3 15 16 10%`, `O1b 20 20 12%`, all `POWER-STOPPED`. `Best-powered arm reached 11 affected dates against a threshold of 25.` | A rerun on a materially larger book in which at least one arm's affected-date count reaches 25 would flip this row. |
| G1 — calibration (O0 reproduces default `account_sim`) | MET | `B1 (stored contracts, stored R): 220 positions / 90 dates / $63,553`; `expected (account-sim.yml gates.book_calibration): 220 / 90 / $63,553`; PRIMARY `72 vs 72 positions, $11,399 vs $11,399  -> identical`; SECONDARY `160 vs 160 positions, $11,248 vs $11,248  -> identical`; `G1: PASS` | New backtest/proxy exports that move the `220 / 90 / $63,553` book line without a matching gate update would flip this row. |
| G2 — blindness (`BlindRec` / `blind_records` probe) | MET | `tripwire live: True`; PRIMARY `O0 sighted 72 blind 72 differing 0`, `O1 77/77/0`, `O2 77/77/0`, `O3 76/76/0`, `O1b 77/77/0`, `O4[draw 0] 72/72/0`; SECONDARY `O0 160/160/0`, `O1 169/169/0`, `O2 166/166/0`, `O3 160/160/0`, `O1b 168/168/0`, `O4[draw 0] 167/167/0`; `G2: PASS` | A rank function reading a column outside the deleted set `days_held, exit_reason, mae_day, mae_pct, mfe_day, mfe_pct, pnl_at_cap_pct, realized_pnl_pct`, producing a non-zero `differing` count, would flip this row. |
| G3 — attribution (taken + census buckets = candidates, per arm) | MET | PRIMARY `candidates offered per arm: 150`; `O0 taken 72 exclusions 78 sum 150 vs candidates 150 -> OK`, `O1 77/73/150`, `O2 77/73/150`, `O3 76/74/150`, `O1b 77/73/150`. SECONDARY `candidates offered per arm: 297`; `O0 160/137/297`, `O1 169/128/297`, `O2 166/131/297`, `O3 160/137/297`, `O1b 168/129/297`; `G3: PASS` | A rerun in which any arm's taken + exclusions sum diverged from the candidates offered would flip this row. |
| G4 — no annualised figure, Sharpe, or time-to-recover | MET | `G4: PASS`; report states it prints `mean R, a paired within-date difference, dollar sanity checks, and counts` and `computes no return per unit time and no risk-adjusted ratio` | A future version of the report printing any per-unit-time or risk-adjusted figure would flip this row. |
| G5 — out-of-fold discipline | MET (vacuously, as the report itself states) | PRIMARY and SECONDARY both: `every arm POWER-STOPPED at G0, so NO outcome number was printed at all — no arm mean R, no paired gain, no band, no LOO fold, no TEST row`; `G5: PASS` | A rerun that clears G0 and prints outcome numbers would make this row substantive rather than vacuous and could flip it if in-sample tables were unlabelled. |
| Bar (1) — paired mean gain vs O0 > 0, date-clustered bootstrap CI excluding zero (`BOOT_N = 10000`) | NOT EVALUABLE | No number printed; PRIMARY/SECONDARY arm tables are `CENSUS ONLY (G0 power stop: no outcome column is printed)`; `arms clearing all seven: none` | A rerun on a larger book where at least one arm clears the 25-affected-date threshold and the paired bootstrap CI is printed would flip this row. |
| Bar (2) — median gain positive among AFFECTED dates and ≥25 affected dates | NOT EVALUABLE | No median printed; affected-date counts are PRIMARY `10, 7, 11, 10` and SECONDARY `18, 12, 15, 20`, all below the registered `25`; `Best-powered arm reached 11 affected dates against a threshold of 25.` | A rerun producing ≥25 affected dates for an arm together with a printed affected-date median gain would flip this row. |
| Bar (3) — every LOO fold positive | NOT EVALUABLE | No number printed; `no LOO fold` (G5 section, both populations) | A rerun that clears G0 and prints per-fold LOO gains would flip this row. |
| Bar (4) — positive in all three years | NOT EVALUABLE | No number printed; no per-year table appears in the report | A rerun that clears G0 and prints per-year paired gains would flip this row. |
| Bar (5) — holds on the SHIPPED exit config, not only a variant | NOT EVALUABLE | Exit profile printed (`take profit +90% · stop -75% · time exit at 75% of DTE`, credit `+65%`, `hard dollar stop at $500`) but no outcome number is attached to it under any arm | A rerun that clears G0 and prints arm outcomes under the shipped exit profile would flip this row. |
| Bar (6) — survives `protocol.window_cuts` AND the ex-BOTH-windows cut added by hand | NOT EVALUABLE | No number printed; no window-cut table appears in the report | A rerun that clears G0 and prints both the `window_cuts` rows and the hand-added ex-both-windows cut would flip this row. |
| Bar (7) — exceeds the O4 random band (above the 95th percentile of 200 draws) | NOT EVALUABLE | `O4 — NOT RUN  (seed 20260814, 200 draws, not taken)` in both populations; `Random-control seed: 20260814 (fixed; draw i uses SEED + i over 200 draws)` | A rerun that clears G0 and actually draws the 200-permutation band with seed `20260814` would flip this row. |

## Deviations

- The pre-registration freezes **six** arms (O0, O1, O2, O3, O1b, O4) and G0 requires the per-arm count of dates whose pick set differs from O0. The G0 census tables list only **four** arms (O1, O2, O3, O1b). O0 is the baseline (zero by construction), but **O4 has no G0 row in either population**, so its power status is unstated rather than reported; the report justifies this at the "O4 — NOT RUN" block. I grade this as an omission, not an error, and do not infer O4's affected-date count.
- The pre-registration's G0/criteria do not say whether the 25-affected-date threshold applies to PRIMARY, SECONDARY, or both. The report applies it to both and both fail on all four evaluated arms, so the ambiguity does not change any verdict here; I have quoted both populations.
- Criteria (1)–(7) are graded `NOT EVALUABLE` rather than `NOT MET` because the pre-registered power stop fired first and the report prints no outcome column at all ("its cells are not read and no criterion is evaluated on it"). This is the pre-registration operating as written, not a shortfall in the report.
- The task prompt named `backtests/study_output/selection_order-latest.txt`; the artifact supplied is that file's inlined contents, with no separate `-<stamp>` file available to cross-check.
- G5 is graded `MET` on the report's own vacuous-satisfaction reasoning; the pre-registration does not state how G5 resolves when no adoption-eligible number exists, so this is my interpretation and is flagged as such.
```

</details>

<details>
<summary>Two-analyst replication — review-analyst-b (verbatim, 2026-08-14)</summary>

```text
==============================================================================
STUDY: selection_order
==============================================================================
  run at    2026-08-14 12:07:03
  command   python -m scripts.backtest_study.selection_order
  git       beb1219 (main, working tree dirty)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
   4,533 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestProxy.csv
  11,836 rows  2026-08-11 17:24  backtests/to_evaluate/analysis - AnalysisClaude.csv
     803 rows  2026-08-13 11:56  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================

| Criterion/Gate | Verdict | Exact number(s) read from report | What would change the verdict |
|---|---|---|---|
| **G0 — power pre-check (≥25 affected dates per arm)** | NOT MET | PRIMARY: `deployed signal dates 46`, `CONTESTED dates 26  (57% of the population)`, `day3_cap 11  net_delta 40  per_pos_delta 25`; affected dates `O1 10`, `O2 7`, `O3 11`, `O1b 10`; `arms cleared for reading: NONE — every arm power-stopped`. SECONDARY: `deployed signal dates 90`, `CONTESTED dates 50  (56% of the population)`; `O1 18`, `O2 12`, `O3 15`, `O1b 20`; `arms cleared for reading: NONE`. | A rerun on a materially larger book in which at least one arm's affected-date count reaches 25. |
| **G1 — calibration (O0 reproduces production)** | MET | `B1 (stored contracts, stored R): 220 positions / 90 dates / $63,553`; `expected (account-sim.yml gates.book_calibration): 220 / 90 / $63,553`; PRIMARY `72 vs 72 positions, $11,399 vs $11,399  -> identical`; SECONDARY `160 vs 160 positions, $11,248 vs $11,248  -> identical`; `G1: PASS`. | New backtest/proxy exports that move the book line off `220 / 90 / $63,553`, or an arm-plumbing change that makes O0 differ from the direct ladder walk. |
| **G2 — blindness (`BlindRec` / `blind_records` probe)** | MET | `tripwire live: True` on both populations; PRIMARY `O0 72/72`, `O1 77/77`, `O2 77/77`, `O3 76/76`, `O1b 77/77`, `O4[draw 0] 72/72`, all `differing 0  -> identical`; SECONDARY `O0 160/160`, `O1 169/169`, `O2 166/166`, `O3 160/160`, `O1b 168/168`, `O4[draw 0] 167/167`, all `differing 0`; deleted columns `days_held, exit_reason, mae_day, mae_pct, mfe_day, mfe_pct, pnl_at_cap_pct, realized_pnl_pct`; `G2: PASS`. | A rank function reading a field outside `delta`, `entry_underlying`, `max_loss_per_contract`, `tier`, `ladder_rank`, producing a non-zero `differing` count. |
| **G3 — attribution (candidates = taken + census buckets)** | MET | PRIMARY `candidates offered per arm: 150`; `O0 72+78=150`, `O1 77+73=150`, `O2 77+73=150`, `O3 76+74=150`, `O1b 77+73=150`, all `-> OK`. SECONDARY `candidates offered per arm: 297`; `O0 160+137=297`, `O1 169+128=297`, `O2 166+131=297`, `O3 160+137=297`, `O1b 168+129=297`, all `-> OK`; `G3: PASS`. | A census bucket that drops or double-counts a candidate so an arm's taken + exclusions no longer sums to 150 (PRIMARY) / 297 (SECONDARY). |
| **G4 — no annualised figure, Sharpe, or time-to-recover** | MET | `G4: PASS`; report states it prints `mean R, a paired within-date difference, dollar sanity checks, and counts` and `computes no return per unit time and no risk-adjusted ratio`. | A future revision printing any per-unit-time or risk-adjusted statistic anywhere on the page. |
| **G5 — out-of-fold discipline** | MET | `G5: PASS`; PRIMARY and SECONDARY both: `every arm POWER-STOPPED at G0, so NO outcome number was printed at all — no arm mean R, no paired gain, no band, no LOO fold, no TEST row`, satisfied `VACUOUSLY`. | A powered rerun that prints in-sample arm outcomes without labelling them, or presents a non-LOO / non-TEST number as adoption-eligible. |
| **Criterion 1 — paired mean gain vs O0 > 0, date-clustered bootstrap CI excluding zero (BOOT_N = 10000)** | NOT EVALUABLE | No paired mean gain, CI bound, or `BOOT_N` value is printed; PRIMARY arms table is `CENSUS ONLY (G0 power stop: no outcome column is printed)` — `O0 72 / 37`, `O1 77 / 38`, `O2 77 / 39`, `O3 76 / 38`, `O1b 77 / 38`. | A rerun on a book where an arm clears G0, so the paired gain and its bootstrap CI are actually printed. |
| **Criterion 2 — median gain positive among AFFECTED dates and ≥25 affected dates** | NOT EVALUABLE | No median gain is printed; affected-date counts are `O1 10`, `O2 7`, `O3 11`, `O1b 10` (PRIMARY) and `O1 18`, `O2 12`, `O3 15`, `O1b 20` (SECONDARY), against `Best-powered arm reached 11 affected dates against a threshold of 25`. | More dates in the affected sets lifting an arm to ≥25 so a median over affected dates can be computed and read. |
| **Criterion 3 — every LOO fold positive** | NOT EVALUABLE | Report prints `no LOO fold` on both populations. | A powered rerun that produces LOO fold values for at least one arm. |
| **Criterion 4 — positive in all three years** | NOT EVALUABLE | No per-year figures are printed; book `date_range=('2024-06-17', '2026-04-07')`. | A powered rerun that prints the per-year breakdown of paired gain for an arm. |
| **Criterion 5 — holds on the SHIPPED exit config, not only a variant** | NOT EVALUABLE | Shipped exits are printed (`take profit +90% · stop -75% · time exit at 75% of DTE`; credit `take profit +65%`; `hard dollar stop at $500`), but there is no arm result to hold or fail on them — `no arm mean R, no paired gain`. | A powered rerun producing a positive result under the shipped exit profile that can then be checked against variants. |
| **Criterion 6 — survives `protocol.window_cuts` AND the ex-BOTH-windows cut** | NOT EVALUABLE | No window-cut table or ex-both-windows figure appears anywhere in the report. | A powered rerun that prints window-cut and ex-both-windows results for a surviving arm. |
| **Criterion 7 — exceeds the O4 random band (above the 95th percentile of 200 draws)** | NOT EVALUABLE | `O4 — NOT RUN  (seed 20260814, 200 draws, not taken)`; `Every arm is power-stopped, so there is no criterion to serve and the 200 draws are not taken.` | An arm clearing G0 on a larger book, which makes the 200-draw band worth taking and comparable. |

## Deviations

- **O4 not run.** The pre-registration freezes six arms and states "Every arm's result is reported regardless of outcome"; the report does not draw O4's 200 permutations (`O4 — NOT RUN`), justifying this by the universal power stop. The seed `20260814` is printed as registered, and `O4[draw 0]` does appear in G2. I record the non-execution as a deviation from the six-arm reporting rule without judging whether the power stop licenses it.
- **Working tree dirty.** Provenance reads `git beb1219 (main, working tree dirty)`, so this report is not byte-reproducible from sha `beb1219` alone. The pre-registration states no cleanliness requirement, so this is flagged, not graded.
- **PRIMARY vs SECONDARY.** The report applies the 25-affected-date G0 threshold separately to both populations. The pre-registration names PRIMARY (dense episodes) as the basis and SECONDARY as carrying nothing; I graded against PRIMARY and quoted SECONDARY only alongside. Both fail G0 regardless, so the interpretation does not change any row.
- **Standing caveat.** The pre-registration requires the standing in-sample caveat to appear in the report; it does (`STANDING CAVEAT` section). It is neither a gate nor a criterion, so it has no table row.
```

</details>

<details>
<summary>Two-analyst replication — review-validator (verbatim, 2026-08-14)</summary>

```text
## Provenance/header check

Both analysts open their outputs with the report's provenance block reproduced verbatim (`STUDY: selection_order`, `run at 2026-08-14 12:07:03`, `command`, `git beb1219 (main, working tree dirty)`, `python 3.11.2`, and all four input-file lines with exact row counts/timestamps/paths). This satisfies the Mode 1 methodology requirement. Confirmed against the inlined report header — no discrepancies.

## Adjudication table

| Criterion/Gate | Analyst A verdict | Analyst B verdict | Source-check result | Adjudication |
|---|---|---|---|---|
| G0 — power pre-check (≥25 affected dates) | NOT MET | NOT MET | confirmed — PRIMARY (46 dates, 26 contested/57%, O1 10/8/11%, O2 7/5/7%, O3 11/10/14%, O1b 10/9/12%, all POWER-STOPPED) and SECONDARY (90 dates, 50 contested/56%, O1 18/18/11%, O2 12/12/8%, O3 15/16/10%, O1b 20/20/12%) match report exactly | agree |
| G1 — calibration | MET | MET | confirmed — B1 220/90/$63,553 matches gate expectation; PRIMARY 72 vs 72, $11,399 vs $11,399; SECONDARY 160 vs 160, $11,248 vs $11,248; both match report | agree |
| G2 — blindness | MET | MET | confirmed — tripwire live True; all sighted/blind/differing-0 pairs (PRIMARY O0 72/72, O1 77/77, O2 77/77, O3 76/76, O1b 77/77, O4 72/72; SECONDARY O0 160/160, O1 169/169, O2 166/166, O3 160/160, O1b 168/168, O4 167/167) and deleted-column list match report | agree |
| G3 — attribution | MET | MET | confirmed — PRIMARY 150 candidates (O0 72+78, O1 77+73, O2 77+73, O3 76+74, O1b 77+73); SECONDARY 297 candidates (O0 160+137, O1 169+128, O2 166+131, O3 160+137, O1b 168+129); all match report | agree |
| G4 — no annualised/Sharpe/time-to-recover | MET | MET | confirmed — `G4: PASS` and supporting prose match report verbatim | agree |
| G5 — out-of-fold discipline | MET (vacuous) | MET (vacuous) | confirmed — both populations' "no outcome number was printed... satisfied VACUOUSLY" text matches report | agree |
| Bar (1) — paired mean gain vs O0, bootstrap CI | NOT EVALUABLE | NOT EVALUABLE | confirmed — no paired gain/CI printed anywhere; arm tables labelled CENSUS ONLY | agree |
| Bar (2) — median gain among affected dates, ≥25 affected | NOT EVALUABLE | NOT EVALUABLE | confirmed — affected-date counts (PRIMARY 10/7/11/10, SECONDARY 18/12/15/20) all below 25; no median printed | agree |
| Bar (3) — every LOO fold positive | NOT EVALUABLE | NOT EVALUABLE | confirmed — report states "no LOO fold" both populations | agree |
| Bar (4) — positive in all three years | NOT EVALUABLE | NOT EVALUABLE | confirmed — no per-year table in report | agree |
| Bar (5) — holds on shipped exit config | NOT EVALUABLE | NOT EVALUABLE | confirmed — exit profile printed but no arm outcome attached | agree |
| Bar (6) — survives window_cuts + ex-both-windows cut | NOT EVALUABLE | NOT EVALUABLE | confirmed — no window-cut table anywhere | agree |
| Bar (7) — exceeds O4 random band | NOT EVALUABLE | NOT EVALUABLE | confirmed — "O4 — NOT RUN (seed 20260814, 200 draws, not taken)" in both populations | agree |

## Violations list

No violations found. Both analysts: opened with the verbatim provenance header; transcribed every quoted number correctly against the inlined report (checked character-for-character, including whitespace-normalized reformatting that changed no values); correctly left the power-stopped bars as `NOT EVALUABLE` rather than rounding or answering them; disclosed their interpretive choices (G5's vacuous-satisfaction reading, O4's non-execution, the PRIMARY/SECONDARY threshold ambiguity) as explicit deviations rather than silently assuming them; and contained no prose ship/no-ship recommendations.

## Validator observations

(Separate from adjudication, per protocol — neither analyst flagged this, and it does not change any verdict.) Analyst B's Bar (1) row additionally quotes the PRIMARY census table (positions/dates, e.g. `O0 72/37`, `O3 76/38`) as supporting context; Analyst A's corresponding row omits this detail. Both are correct — the census figures are position/date counts, not outcome numbers, so their presence or absence doesn't affect the `NOT EVALUABLE` verdict — but B's row is marginally more complete as a source-check trail.
```

</details>
---

## 2026-08-14 — `selection_order`: PRE-REGISTRATION → [`pre-registrations/f4_deployment/selection_order.md`](pre-registrations/f4_deployment/selection_order.md)

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

---

## 2026-08-19 — `account_sim` on v4: the date floor is not a density floor

**No result. The study refuses on v4, and that refusal is the finding.**

The v4 export set crossed `MIN_ERA_DATES` (31 deployed signal dates, 34 in
`BacktestResults`) and `load_book` admitted it. `account_sim` then produced
**zero dense episodes** — not one run of ≥10 dates whose every internal gap is
≤5 trading sessions — because the v4 book is a BACKFILL: its signal dates are
scattered from 2024-01-10 to 2025-01-07, roughly a fortnight apart, plus a few
live sessions (2026-08-11 … 08-18) that have no backtest rows yet.

PRIMARY is the population this study concludes from, and on v4 it is empty.
SECONDARY (the full sparse book) is an availability upper bound and may not
carry a conclusion alone, so there is nothing to report and nothing to grade —
`make study-review` now stops on the refusal instead of spending three headless
model calls replicating it.

**What this says about the era floor.** `MIN_ERA_DATES` counts dates; it does
not ask whether any of them are CONSECUTIVE. Those are different questions, and
a backfilled era can satisfy the first while failing the second completely. Up
to 2026-08-18 the floor was masking this: v4 had 26 dates and refused as thin,
so the empty-PRIMARY path had never been reached. It was reached the day the
26th date became the 31st, and the study died in `statistics.median` on an
empty contract list rather than saying any of the above. That is now a designed
refusal (exit 2) stated at the population boundary — see `primary_refusal()`.

**Not a reason to loosen `episode_min_dates` / `episode_max_gap`.** They define
what this study is allowed to conclude from; the v3 evidence base was built
under them. The way to a v4 `account_sim` result is consecutive v4 sessions —
either accrued live, or backfilled DENSELY over a contiguous window rather than
sampled across a year.

---

## 2026-08-19 — `calendar_hedge` R4: a gate keyed to a snapshot is not a gate

**Method change, no new result.** R4 — the gate that decides whether the H arm
is allowed to run at all — was converted from a transcribed checksum to a
same-run comparison. Nothing about the hedge hypothesis changed.

**What R4 was.** It rebuilt `vol_sleeve`'s calendar cell and required it to
reproduce `R4_EXPECT = dict(n=183, mean_r=0.158, dollars=28059.0, exits={...})`,
transcribed by hand from `vol_sleeve-latest.txt` (2026-08-12, git 470b95f). The
stated purpose was to catch RE-IMPLEMENTATION drift: `calendar_hedge` builds its
own universe (`build_universe`) rather than importing `vol_sleeve.synthesize`'s
inline one, and two copies of an entry rule eventually disagree.

**Why it could not work.** The comparison had two free variables and one
equation. `vol_sleeve` picks K\* as "the cached strike nearest spot" and the far
leg as "the next cached expiry", so the option-history cache is an INPUT to leg
selection, not just storage — adding contracts re-picks legs and moves the cell
with no code change. A mismatch therefore could not be read as drift rather than
as cache growth, which is why the FAIL path carried an entire `_r4_attribute()`
bisect whose job was to guess which had happened.

The 2026-08-13 amendment tried to remove the second variable by SUBTRACTION:
withhold the contracts the ARM S sweep added (`legs_manifest.csv`) and rebuild
on the reconstructed pre-scrape grid. That inverse is valid only while every
LATER addition is manifested too. Measured 2026-08-19: 6,240 cache files
postdate the keyed run, the manifest covers 1,452. The remaining ~4,800 came
from routine `fetch_counterpart_history.py` runs that write no manifest, so the
"pre-scrape grid" had stopped being one. Worse, a rescrape that OVERWRITES an
existing contract changes leg PRICING with the same legs selected, and no index
filter can undo that — `snapshot_index()` explicitly filters selection only, on
the assumption that surviving files are byte-unchanged. Hence the study's own
FAIL text: "Once the cache grows, R4 can never pass again."

**Why re-baselining was not the fix either.** Re-keying the constants to a fresh
run would define "no drift" as "whatever this run printed" — circular, and
across an era boundary it is worse than circular: you would be baking v4's
characteristics into the definition of correct while v4 is the thing under test.
A constant that fails on legitimate data and cannot be corrected without
begging the question is not repairable. It has to go.

**What R4 is now.** Both sides are built in ONE process from the SAME book and
the SAME strike index — side A through this study's `build_universe`/`evaluate`,
side B through `vol_sleeve.synthesize(..., structures=("calendar",))` — and
required equal row for row on (entry_net, contracts, exit_reason, days_held, R),
keyed (ticker, date, expiry). Rounding is the checkpoint store's own round-trip
precision (6dp / 10dp), not a tolerance. Cache growth now moves both sides
together, so a mismatch has exactly one possible cause, which is the one the
gate was always about. First run under the new form: **R4 PASS**, 20 rows,
meanR +0.628, $62, exit mix identical on both sides.

**A second snapshot was hiding underneath it.** The checkpoint store
(`backtests/sweep_cache/synth_results.csv`) is keyed
`(structure, ticker, date, expiry, profile_hash)` — no input generation. So
after a scrape, `evaluate` would skip a cached row while `vol_sleeve.synthesize`
recomputed a fresh one, and the converted R4 would fail on the next scrape for a
reason that is still not drift. The key now carries a per-TICKER cache signature
(`ticker_cache_sig()`: file count @ newest mtime), so a row built against one
cache generation is never reused as, or compared against, a row built against
another. Per-ticker rather than whole-cache: a scrape touches some names, and
invalidating the other ~1,100 would empty the store without making one number
more correct. Rows written before the column existed carry `""`, match no live
signature, and are recomputed rather than trusted.

**The rule both R3 and R4 arrived at the hard way.** A gate compares two things
computed THIS run from the SAME input, or it is a fingerprint of one snapshot
wearing a gate's clothes. R3 became a print on 2026-08-15 for the same reason;
four `account_sim` gates with stored `expected_positions` were deleted the same
day. R4 was the last transcribed expectation in `scripts/backtest_study/` and it
survived on the argument that a RE-IMPLEMENTATION checksum is different from a
POPULATION checksum. That argument holds only while the code's inputs are fixed,
and a 24k-file scraped cache is not fixed. Where a code-behaviour claim genuinely
needs a fixed expectation, it belongs in `tests/` against a COMMITTED fixture —
version-controlled beside the code, changed only in a deliberate commit — which
is what `tests/test_harness_replay.py` already does for the frozen harness.

**Study outcome on v4 (unchanged conclusion).** With the gates passing, the H arm
runs to completion for the first time since the cache grew: exit 0, **H0 FILL NOT
MET** (was MET on v3), **H2 NOT EVALUABLE**, H2-under-hold NOT EVALUABLE. That is
the thin v4 book, not a refutation — the hedge programme was already
power-stopped. Blocked on dates, as before.

## 2026-08-19 — `macro_event_study` first run (era v3): tight event windows are UNDERPOWERED on this book; NFP is the only readable cell (null on vrp/R); ARM X trigger FIRED

New layer, built study-first (no pipeline/prompt change — a macro input into the
analysis prompt would be a v5 bump, and nothing here authorises it).
Pre-registration: `research/pre-registrations/f1_selection/macro_event_study.md`, committed at
325964e BEFORE the study was built. Infrastructure: `config/macro-events.yml`
(188 events, FOMC decisions/minutes + CPI + NFP + PCE, 2023-06 → 2027-12,
hand-transcribed 2026-08-19 from the official Fed/BLS/BEA schedules — the 2025
shutdown gaps are REAL and pinned by test: no Oct-2025-reference CPI/NFP, Sep-2025
releases delayed, PCE Oct+Nov 2025 combined, three 10:00 ET PCE deviations) and
`scripts/backtest_study/lib/macro_calendar.py` (strictly-after `next_event`,
`verified_through` refusal, unscheduled events excluded from forward reads only;
distance keys off the ENTRY session, `pre_open` decides day 0).

**Population: pooled real+tweak, era v3 — 795 rows / 118 dates (2024-06-17..
2026-04-07), bs excluded.**

- **G0 (the headline): the book cannot power tight event windows.** Splitting
  sides (before/after — the hypotheses are directional) leaves ONE cell at the
  pre-registered 25-affected-dates floor: **NFP AFTER w<=5 (25 dates / 162
  rows)**. Every FOMC, minutes, CPI and PCE proximity cell power-stops (best:
  FOMC BEFORE w<=5 at 15 dates). The pre-registration predicted the FOMC stops
  from the scoping counts; the side-split cost — roughly halving each window's
  dates — is the part the scoping estimate missed. Census confirmed the other
  pre-declaration: 795/795 rows carry >=1 macro event inside the DTE window
  (`n_*_in_dte` is a constant, not a feature), 716/795 inside the realized hold.
- **ARM I (H1 PRIMARY): null where readable.** vrp NFP-AFTER vs control +0.022
  CI[-0.019,+0.060]. Secondary watches, NOT claims: ticker-demeaned iv_entry
  +0.031 CI[+0.013,+0.051] and iv_pct +0.154 CI[+0.084,+0.220] both star, but
  the pre-registered REGIME-PROXY re-cut is power-stopped at every mech_vol
  label (8/14/3 dates), so EVENT-PRICES-IV cannot be evaluated — and iv_pct has
  been killed twice as a composition proxy. Verdict inputs: POWER-STOPPED
  everywhere except one null cell.
- **ARM P (H2): null.** R NFP-AFTER -0.144 CI[-0.331,+0.056]; every
  within-structure cell power-stops (bear_put 23d is the closest). The year-2026
  cut alone stars (-0.339) — a cut, not a headline, logged as such.
- **ARM V (H3, CONTEXT ONLY — index vol, never a verdict):** NFP shows the
  textbook build-then-bleed: dVIX +0.493 CI[+0.005,+1.169] at t-1, mean VIX
  peaks 18.9 the session after the print, then -1.069 CI[-2.336,-0.303] at t+3.
  FOMC shows NO significant pattern anywhere in t-5..t+5 — consistent with
  2023-2026 decisions being mostly telegraphed. 7 of 55 cells star against
  ~2.75 expected by chance; only the NFP pair is a coherent shape.
- **ARM X (H4, census): TRIGGER FIRED.** Mean R by position of the first event
  inside the hold is monotone — EARLY +0.014 (541 rows) / MID +0.042 (121) /
  LATE +0.122 (54) — across 118 affected dates. Per the pre-registration this
  queues **`macro_event_exit` (f2_management) with its own pre-registration**,
  and nothing else: the pattern is endogenous on its face (an event landing
  LATE in a hold means the position already survived that long).

Traps hit and fixed during the run (both now in code comments):
(1) `iv_spread`/`iv_pct` are pandas-sourced and carry **NaN, not None** — the
same trap `underlying_features.terciles()` fixed on 08-12; the study's
bootstrap now filters `v == v`. (2) `DESIGNED_REFUSAL_EXIT_CODES` must be a
PLAIN SET LITERAL — run.py finds it by `ast.literal_eval`, and a
`frozenset({4})` call is invisible, which silently demoted the tested exit-4
coverage refusal from DESIGNED REFUSAL to failure (deleting -latest.txt).
Negative test now verified: a truncated calendar (via `STUDY_MACRO_CALENDAR`,
test-only env) refuses exit 4 and the report is promoted, not deleted.

**Nothing ships. The macro layer's readable answer so far:** on THIS book,
entry proximity to scheduled macro events is mostly unmeasurable (the analysis
dates cluster away from event days), and where measurable (NFP) it moves
neither entry vrp nor outcomes. The live pipeline does not pay the v5 version
bump on this evidence. Re-run when new dates land; the calendar extends to
2027 so the layer is ready for the deploy card if evidence ever earns it.

### 2026-08-19 addendum — replication review graded; three report-completeness gaps closed

`study_review` (analyst A/B opus + validator sonnet) source-checked every quoted
number clean, and every hypothesis verdict stands as written above (H1 NOT MET
where powered, else NOT EVALUABLE; EXIT-TRIGGER MET both analysts). Validator
surfaced two real gaps, both closed the same day as REPORT-COMPLETENESS fixes
(no window, control, type, or floor changed): (1) ARM X now prints H4's
LITERAL census — exit position relative to the NEAREST event — which the first
report omitted in favour of the trigger's hold-position terciles: exits land
disproportionately just before/at events (−5..−1: 320 rows R +0.084; day 0:
+0.082) vs just after (+1..+5: −0.054); census only, feeds nothing. (2) The
starred ARM I secondaries now carry full G2 cuts (analyst B's stricter reading
of "headline"): `iv_entry_dm` survives ex-window/ex-BOTH and both pricing
tiers but its significance is 2024-carried (2025 and 2026 CIs span zero) —
confirming watch-not-claim. Also added a G0 day-0 audit table so the pre_open
assignment rule is checkable from the report (the 11 post-open PCE
entry-session rows are the 10:00 ET deviations, bucketing BEFORE as designed).
Grading-grammar note for future runs: the validator sided with bundling
UNBUNDLED — grade each anti-tuning clause separately rather than letting one
unevaluable clause downgrade a row.

### 2026-08-19 addendum 2 — ARM V-price (amendment 1): index PRICE around events

Operator follow-up ("how about the relationship with index price?") →
pre-registration AMENDMENT 1 (dated, after the first run; SPY numbers unseen
when written): the VIX context arm gains SPY close-to-close returns per
event-relative session plus two pre-declared cumulative windows (PRE t−3→t0,
POST t0→t+3). Same anchors, same event-clustered bootstrap, CONTEXT ONLY.

- **FOMC: the Lucca-Moench pre-announcement drift does NOT reproduce** at this
  n (26 events): PRE +0.371% CI[−0.202,+1.020]. Positive point estimate,
  unpowered; only t−2 stars (+0.442%).
- **CPI is the strongest price pattern in the table**: PRE +0.769%
  CI[+0.266,+1.236]* AND POST +0.642% CI[+0.213,+1.101]* — SPY rose into and
  out of CPI prints throughout this window. Read with the obvious caveat: the
  2023–2026 sample IS the disinflation regime; a market that rallies every
  time inflation prints soft produces exactly this table without any
  structural drift. Not separable at n=37.
- **NFP: price confirms the vol story.** POST +0.794% CI[+0.162,+1.546]* with
  the single-day star at t+3 (+0.621%*) landing the same session VIX bleeds
  (−1.069*). Build-then-relief in both moments — the one coherent
  cross-measure shape in the table.
- **PCE and minutes: noise-shaped** (scattered alternating-sign stars
  pre-event; nothing cumulative).
- Star accounting kept honest: 110 daily cells × 5% ≈ 5.5 expected, 9
  observed, plus 3/10 drift windows — only NFP (and CPI's paired drift) form
  coherent shapes.

Infra fix found by the run: `spy_vix_daily_full.csv` carries HOLIDAY rows with
one leg populated (2026-05-25: VIX close, empty SPY) — ARM V now requires BOTH
closes to parse before a date counts as a session; a one-legged session
poisons the return chain. Still CONTEXT: none of this touches a gate, floor,
readable cell, or the book itself. Nothing ships.

### 2026-08-19 addendum 3 — survival control kills the ARM X trigger; `macro_event_exit` DE-QUEUED; study goes passive

Amendment 2 (pre-declared before computing: X-C1 = same position table within
holds >= 20 sessions, X-C2 = position x hold-length terciles, consequence
grammar fixed in the pre-registration) came back unambiguous:

- **X-C1: the LATE bucket is EMPTY in long holds** (369 EARLY / 20 MID / 0
  LATE of 389 rows, 111 affected dates). With an event every ~2 weeks, a
  20+-session hold's first event lands early almost surely — the coupling is
  mechanical, exactly as suspected. Non-monotone by construction →
  **SURVIVAL-ARTIFACT** per the pre-declared grammar.
- **X-C2 shows what the raw trigger was actually reading**: within SHORT
  holds EARLY is the BEST bucket (+0.154 vs LATE +0.127, non-monotone);
  within MID holds EARLY wins (+0.147); LONG holds are negative everywhere
  (-0.184/-0.412). The raw EARLY +0.014 / MID +0.042 / LATE +0.122 monotone
  was composition: 50 of 54 LATE-position rows are SHORT holds (winners
  taking profit near an event they were about to span), while EARLY absorbs
  every long grinding loser. Exit-rule composition, not an event effect.
- **Consequence taken: `macro_event_exit` (f2) is DE-QUEUED.** It re-arms
  only if a future run fires the CONTROLLED trigger (X-C1), never the raw
  one. No new exit study will be built on this book's macro layer.

**Study disposition (operator: "do what you have to do"):** macro_event_study
goes PASSIVE — re-run at the next evaluation gate / when the enrich-queue
expansion lands (one command, `--era` as appropriate; G0 says whether any cell
crossed the floor), calendar gets an annual top-up (2028 dates), and no
active session is spent on this layer absent a powered cell. The v5 prompt
bump stays unpaid. Reusable lesson, again: a monotone table whose bucketing
variable is mechanically coupled to hold length is a composition read until
proven otherwise — condition on the coupling variable BEFORE queueing
follow-ups.

---

## 2026-08-19 — `staged_exit` first run (era v3): the reactive-exit null EXTENDS to scheduled switches — 60 of 96 cells UNDERPOWERED, and **0 of 36** powered cells clears the CI

**Nothing ships, nothing is queued. No CANDIDATE and no REACTIVE-AGAIN was
reached, because no cell got past criterion 1.**
Pre-registration: `research/pre-registrations/f2_management/staged_exit.md`, written before
the module existed. Report: `backtests/study_output/staged_exit-latest.txt`
(run 2026-08-19 17:10:09, git bfcd512, exit 0 after 43.3s).

**Population: pooled real+tweak, era v3 — 795 rows / 118 dates (2024-06-17 ..
2026-04-07), bs excluded** (`counts_by_source` real 406 / tweak 389 / bs 272).
`debit_calib` n=301 exact=289 near=0 hard=12; `n_credit_ungated` 277 — every
credit-side exit number below is unvalidated until the book is split per
credit-stop era (Attempt 13 removed the credit stop mid-book), and that caveat
bites hardest on ARM T, whose "tighten stop to −0.40" action INTRODUCES a stop
on rows whose shipped profile carries `sl=None`.

- **G0 — the grid does not power itself.** The frozen grid is 96 cells
  (2 arms × X ∈ {5,10,15,20} × 8 conditions × the arm's actions). At the
  pre-declared floor of 25 affected dates / 60 affected rows, **36 cells clear
  and 60 are UNDERPOWERED** (the report prints the older token
  `POWER-STOPPED`; the tally line reads `{'POWER-STOPPED': 60, '-': 36}`).
  The kill is structural, not incidental: **all 32 `arm trail 0.50/0.50` cells
  are UNDERPOWERED** — the largest is 27 rows / 22 dates — so ARM T's transfer
  test is carried entirely by the tighten-stop action, exactly as the build-time
  wording correction predicted.
- **Both integrity gates PASS and they are the reason to believe the nulls.**
  G1 (leak guard) checked 96 cells × 795 rows and found **0 rows changed
  outside the population**, with the keying evaluated INSIDE the rule so the
  check cannot be vacuous. G-FORK — the local `replay_staged` fork reproducing
  the FROZEN harness on (exit_reason, days_held, round(pnl, 10)) — ran
  **3,180 comparisons, 0 disagreements**.
- **The result: 0/36 on criterion 1.** Not one powered cell's date-clustered
  CI95 excludes zero. Best ΔR in the whole grid is **+0.011** (ARM E X=5
  R ≤ −0.25, CI [−0.036, +0.065], and ARM T X=10 $ ≤ −500, +0.011); worst is
  **−0.113** (ARM E X=15 R ≤ −0.25). Criterion 4 (sign-stable every year)
  passes **0/36** cells; criterion 7 passes 1/36; criterion 6 passes 36/36 by
  construction. The whole verdict column is `-` or UNDERPOWERED.
- **Criterion 7 is the same wall the trail attempts hit.** Across the 36
  powered cells the G2 continuation share — early exits followed by a post-exit
  max > realized + 0.30 — runs **49–79%** (ARM E 55–79%, ARM T 49–68%). The
  worst offenders are the profit-taking cells the operator instinct wants most:
  ARM E X=5 R ≥ +0.25 sells **112/141 (79%)** continuations, X=10 R ≥ +0.25
  sells **99/130 (76%)**. Cutting a winner at a scheduled checkpoint is the same
  trade as cutting it reactively.

**What this closes.** The Attempts 1/2/10 finding — a reactive exit switch on
this book sells continuation — was about triggers that fire whenever a
threshold is touched. `staged_exit` asked whether making the switch SCHEDULED
(evaluated once, at session X, then never again) buys immunity from that. It
does not: the same continuation share appears at every X, and no scheduled
switch separates from the shipped merge on any horizon between session 5 and
session 20. **The null now covers both reactive and time-staged exit switching
on these dates.**

**Build-time wording correction, recorded (part of the scientific record).**
The registration disclosed plan-time survivor counts (513 rows/114 dates past
session 5; 415/110; 333/109; 265/102). Those reproduce EXACTLY on the **debit
slice** (593 of 795 rows) — measured there, mislabelled as the whole book. The
registered POPULATION WORDING is unrestricted, and the wording governs: the
build runs credits in every population under CREDIT_PROD, and G0 now prints
debit and credit columns side by side with a reconciliation paragraph
(whole-book survivors **702/118, 583/117, 473/116, 385/111**). No population,
threshold or criterion moved — only a label on a disclosed number. Two
consequences were stated in place rather than quietly absorbed: the ARM T
tighten action introduces a stop on credit rows, and the trail action is
near-inert on this book.

**What re-arms it.** New dates only — 60 UNDERPOWERED cells need affected-date
counts to grow, and the powered 36 are recorded as read on these dates and are
not re-run on them. A v4 book large enough to power the grid would also be the
first honest test of whether the continuation share is a v3 selection artifact.

---

## 2026-08-19 — `emission_timing` first run (era v3): **the signal does not decay within three sessions** (ARM L LAG-TOLERANT — a publishable operational finding); repeat emissions are NULL (ARM P)

**The headline is ARM L, and it is a finding rather than a null: a missed
same-day fill is not a lost trade.**
Pre-registration: `research/pre-registrations/f1_selection/emission_timing.md`, written
before the module existed. Report:
`backtests/study_output/emission_timing-latest.txt` (run 2026-08-19 17:10:53,
git bfcd512, exit 0 after 15.0s).

**Population: pooled real+tweak, era v3 — 795 rows / 118 dates (2024-06-17 ..
2026-04-07), bs excluded.** `debit_calib` n=301 exact=289 hard=12;
`n_credit_ungated` 277 with the standing credit caveat. The ladder runs on ONE
population — **783/795 rows constructible at ALL of L ∈ {0,1,2,3}** (12
excluded and counted: 5 `degenerate_zero_entry`, the rest `no_mark_at_lag`) —
so no rung is compared against a different book.

### ARM L — LAG-TOLERANT

L=0 is a day-0 CLOSE fill built IDENTICALLY to L=1..3, so the close-vs-open
basis change cancels and the estimand is LAG-ONLY. The stored book prints as a
REFERENCE line (+0.0416) and is not the comparator.

- **The ladder is flat:** L=0 **+0.0051**, L=1 **+0.0180**, L=2 **+0.0158**,
  L=3 **+0.0168** mean R, all n=783 / 118 dates. If anything the lagged rungs
  are marginally *better*, which is itself evidence against decay.
- **Paired against L=0, every rung's CI includes zero:** L=1 **+0.0129
  CI[−0.0335, +0.0568]**, L=2 **+0.0107 CI[−0.0480, +0.0689]**, L=3 **+0.0117
  CI[−0.0574, +0.0772]**. All three clear criterion 2 (LOO every fold signed,
  share_positive 1.000) and criterion 6, and fail 3/4/5 — i.e. there is no
  stable effect in EITHER direction.
- **Verdict, in the registration's vocabulary: LAG-TOLERANT (PUBLISHABLE
  OPERATIONAL FINDING).** Worth stating precisely, because it is easy to
  over-read: the study did not find that waiting helps. It found that no lag in
  {1,2,3} separates from L=0 under the full conjunction, on a population where
  a real decay of the size the sizing rules care about would have shown. The
  operational consequence — the one the deploy card actually needs — is that
  the same-day fill is not load-bearing, so a missed morning is a deferred
  trade rather than a dead one.
- **The terciles argue with each other, and neither wins.** Cut on the
  pre-signal `price_vector` (frozen on the FULL book before any lag result was
  read): **T1_low** (the signal already moved against the play) improves with
  lag — L=3 **+0.0947 CI[−0.0187, +0.2040]**, clearing criteria 2–6 and
  failing only the CI, the single closest near-miss in the study — while
  **T3_high** decays with lag, L=3 **−0.0495 CI[−0.2031, +0.0851]**. T2_mid is
  inert. Opposite-signed sub-cuts that both fail the CI are exactly what a flat
  pooled result looks like when it is genuinely flat, and neither may be
  promoted. `MISSING` (73 rows / 16 dates) is its own cell by registration,
  UNDERPOWERED (the report prints the older token `POWER-STOPPED`), never
  imputed.
- **INTRADAY FILLS REMAIN UNTESTABLE.** Daily marks cannot represent a fill
  inside the session; nothing here is evidence about intraday timing.

### ARM P — NULL

Within-date paired Δ(mean R), repeats (ordinal ≥ 2) minus firsts, aggregated
over dates. 82 of 118 dates carry BOTH and are POWERED.

- **Headline: +0.0537 CI[−0.1149, +0.2243]**, n=82 pairs / 82 dates —
  criterion 1 FAIL. Criterion 4 (sign stable by year) also FAILs: **2024
  +0.1303, 2025 −0.0323, 2026 +0.1336**.
- Both frozen sub-cuts land in the same place: **consecutive repeats +0.0695
  CI[−0.1511, +0.2894]** (LOO clean, year sign FAIL), **gapped repeats +0.0390
  CI[−0.1548, +0.2354]** (LOO FAIL at share_positive 0.988). The
  already-moved-with-the-play cut is +0.0848, the moved-against cut +0.0211 —
  neither separates.
- **Verdict: NULL (no persistence effect).** A repeat emission is neither a
  stale signal nor a confirmation on these dates.
- **Recorded as a WATCH, explicitly post-hoc:** every ARM P cell's point
  estimate is positive, and the headline's LOO folds are 82/82 positive with
  min gain +0.0148. That is a LEAN toward "confirmation, not staleness", and it
  is written down only so a future run on new dates can be checked against a
  direction stated in advance. It is not a result, it did not clear the
  conjunction, and 2025 is wrong-signed inside it. Nothing may be built on it.

**G3 held throughout.** Every conditioning key routes through
`assert_conditioning()` against the frozen allowlist and every bar-derived
value through `close_asof()`, which FAILS the run if it resolves a session
after the signal date — so the day-0 underlying move is unreachable, not merely
unused, and `next_day_move` ARM C stands untouched.

**Build-time wording corrections, recorded (four, all before the run).**
(1) **ARM L anchoring was off by one** — the harness grid is weekdays AFTER
signal_date, so grid[0] is already the fill session; the synthetic anchors at
grid[L−1], which makes L=0 reproduce the stored trade except for the fill
price, as "L=0 is the baseline" requires. (2) **price_vector coverage** — the
disclosed 785/795 measured JOIN failure only; 63 further rows join with a blank
cell, so the true conditioned population is 722/795 and all 73 form the MISSING
cell. (3) **Consecutive repeats** — disclosed as 150; the frozen definition
(previous emission on the immediately preceding date present in the era book)
counts **151**, with the stricter calendar-next-weekday diagnostic (106)
printed alongside. (4) **Degenerate entries** — lag priceability now excludes
`marks[L] == 0.0` as well as None (5 rows, counted, never silently dropped).
Also recorded for the grader: contracts are re-sized by the production formula
at EVERY lag including L=0, because the harness `dollar_stop` fires on a
contract-dependent threshold and holding the stored count would turn the ladder
into a sizing artifact.

**What re-arms it.** New dates. ARM P's watch-lean and T1_low's near-miss are
both one powered re-run away from being checkable against a direction stated
here first; nothing about either is actionable until then. ARM L's finding is
already usable as an operational fact and needs no re-run to be relied on for
what it says.

---

## 2026-08-19 — `financed_spread` first run (era v3): **all seven cells NULL**, the naked short is significantly HARMFUL, and E3 says every shape re-wraps the sleeve it was supposed to diversify

**Financing a book debit vertical at a strike offset does not improve it, and
one shape actively destroys it.** Pre-registration:
`research/pre-registrations/f3_structure/financed_spread.md`. Report:
`backtests/study_output/financed_spread-latest.txt` (run 2026-08-19 17:11:08,
git bfcd512, exit 0 after 144.8s).

**Population: era v3 — 795 rows / 118 dates (2024-06-17 .. 2026-04-07),
real 406 / tweak 389.** The financed population is read off **LEG GEOMETRY, not
the `structure` label** (the label is a classifier output; the strike ladder is
not): **570 two-leg single-expiry debit verticals kept** (bull 240 / bear 330)
of 795 — excluded credit_signed 201, not_a_debit_vertical 9, not_two_leg 15,
plus 48 non-exact proxy debit rows. All seven cells clear the G0 floor
(≥25 dates / ≥60 rows). Baseline: n=570, win 46%, PF 1.16, **meanR +0.062**.

**Gates all PASS, so the nulls are about the structures and not the pricing.**
G1 reconstruction rebuilt **570/570 (100.0%)** rows within the pre-registered
tolerances (entry ±$0.005, per-day mark ±$0.01, ≥95% of priced days agreeing).
G2 clamp attribution PASS. E1 (the geometry gate) PASS at 96–100% row-sign
agreement on every gated shape.

### The cells

| cell | n / dates | ΔR (prod-sized) | CI95 |
|---|---|---|---|
| F0 own | 470 / 109 | −0.192 | [−0.422, +0.027] |
| F1 off1 | 173 / 85 | **+0.105** | [−0.019, +0.246] |
| F1 off2 | 107 / 66 | +0.002 | [−0.086, +0.079] |
| F2 off1 | 278 / 104 | **−0.290** | **[−0.559, −0.045]** |
| F2 off2 | 187 / 87 | **−0.456** | **[−0.819, −0.126]** |
| F3 off1 | 205 / 95 | −0.155 | [−0.429, +0.089] |
| F3 off2 | 160 / 87 | +0.016 | [−0.232, +0.250] |

- **F2 — the naked short leg beyond the outer strike — is the only cell whose
  CI excludes zero, and it excludes it on the WRONG SIDE.** off1 **ΔR −0.290
  CI[−0.559, −0.045]**, off2 **ΔR −0.456 CI[−0.819, −0.126]**; LOO share+ 0%
  at both offsets; every year negative at off2 (2024 −0.550, 2025 −0.488, 2026
  −0.314). The financed cell's own path tells the story: gb (|mean MAE| / mean
  MFE) blows out to **1.45 / 1.62** against the baseline's 0.75, and the
  fixed-contracts control at off2 is worse still (−0.650 CI[−1.149, −0.240]),
  so this is not a sizing artifact. Selling an unbounded short to finance a
  defined-risk debit is **significantly harmful on this book** — the strongest
  signed result the study produced, and it points the opposite way to the
  operator instinct that motivated the arm.
- **F1 off1 is the only near-miss, and it still fails twice.** It clears
  criteria **2–6** (LOO min +0.071 over 85 folds, share+ 100%; ex_BOTH +0.140;
  every year positive; both pricing tiers right-signed real +0.205 / tweak
  +0.031; 85 dates) and fails **1** (CI [−0.019, +0.246] includes zero) and
  **7** (E3 **+0.067** over 69 shared dates). Under the registered grammar a
  cell clearing 1–6 and failing 7 would be RE-WRAP; this one never cleared 1,
  so it is **NULL**.
- **E3 is positive on every single shape** — F0 +0.135, F1 +0.067/+0.278,
  F2 +0.061/+0.017, F3 +0.265/+0.115 — and the registered reading was fixed
  before the run: **POSITIVE correlation = RE-WRAP, REGARDLESS of ΔR.** That is
  the deepest finding here and it is not about any one shape: these synthetics
  are built on the ENGINE'S OWN signal dates, so financing does not add a new
  exposure, it **re-wraps the exposure already deployed**. This is the
  `vol_sleeve` lesson arriving again in a different costume.
- **The exit rule moves underneath F0 and F2 and is printed before any ΔR.**
  Exits are assigned by the SIGN of the synthetic net entry, so F0 flips
  **83.0%** of its rows to CREDIT_PROD and F2 flips 32.0% / 28.9% — those cells
  changed the exit rule as well as the wrapper, and their ΔR is not a pure
  structure read. F1 flips 1.2% / 0.0%, which is why F1 is the cleanest arm in
  the table.
- Worst-decile behaviour is printed and **refused as evidence** (9 dates), as
  the 2026-08-13 hedge-programme wall requires. F2 off1 shows +0.824 there on
  16 rows. It licenses nothing.

**Verdict: NULL on all seven cells.** No CANDIDATE, no RE-WRAP verdict issued
(RE-WRAP requires clearing 1–6 first), nothing queued from F0–F3.

**Build-time wording corrections, recorded.** Two registration statements the
geometry made unsatisfiable as written, corrected before the run with no
threshold or criterion changed: (1) **G2 on F2** — "100% UNclamped" is true
only of a naked short CALL; a naked short PUT (F2 on a bear base) is
structurally bounded at S=0 and `_defined_risk_bounds` clamps it CORRECTLY, so
the gate is evaluated on the naked-CALL subset (0 clamped of 102 / 59) with the
put-side count printed beside it. (2) **F0's offset axis is degenerate** — F0
sits at the debit's own strikes, so "four shapes × two offsets" yields **seven
cells, not eight**.

**Collector census discrepancy, recorded because it is part of the trail.**
The implemented target derivation reads **1,775 targets / 607 cached / 1,168
missing** (93 tickers, 462 groups) against the plan-time estimate of
**2,522 / 925 / 1,597**. The plan-time figure exceeded the rule's own
4-per-group cap and came from a looser derivation; the RULE that was registered
(2 nearest cached-ladder strikes strictly beyond each side) is what the
collector implements. No target was added or removed after any outcome was
seen. The gap shows up in the build census as `no_cached_ladder` (229–411 rows
per cell), which is why F1/F3 run on 107–205 rows rather than the full 570.

**A post-scrape re-run of F1–F3 is judged LOW VALUE, and this is the decision.**
Filling the 1,168 missing ladder strikes would raise n on cells whose verdicts
do not hinge on n: F2 is significantly HARMFUL (more rows make it more
harmful, not less), and **E3 is positive on every shape**, so criterion 7 fails
for a structural reason a bigger cache cannot fix. Only F1 off1 would benefit,
and it needs the CI to move a full 0.019 in the right direction while criterion
7 stays broken. **The live thread is F4.**

**AMENDMENT 1 (registered the same day, after this run and before F4 is built —
being built now).** The operator's intended financing is a structure these arms
never priced: a **short-dated, delta-targeted naked short leg** sold "not to be
reached", expiring while the debit thesis is still developing. Frozen in the
amendment: one short leg strictly beyond the debit's furthest OTM leg; expiry =
the nearest cached expiry ≥7 calendar days after entry AND ≤½ the debit's DTE
(else `no_near_expiry`); two cells at |Δ| ∈ {0.10, 0.20} picked from the 4
nearest cached-ladder strikes (never an invented strike; off-target by >0.10
⇒ `target_unreachable`); single tranche, no roll; the single-expiry clamp is
inapplicable so G2's F4 clause is "unclamped while the short leg lives" with
the segment boundary printed; **same gates, same floor, same 7-part
conjunction including E3 ≤ 0**. Nothing in the amendment reopens F0–F3 on
these dates. Note that F2's result is the relevant prior for F4 and it is a
bad one — the amendment's differences (short-dated, delta-targeted, expiring
inside the hold) are precisely what has to overcome it.

**Terminology, registered in the same amendment and adopted from here on:**
"POWER-STOPPED" is read as **UNDERPOWERED — too few dates to judge; census
printed, nothing concluded.** Existing reports and registrations keep the
original token for traceability; new code prints UNDERPOWERED.

---

## 2026-08-19 — `portfolio_delta` first run (era v3): **NOISE** on the primary — and the census is the real finding: the deployed ladder is **LONG-ONLY BY CONSTRUCTION** (219/220 positive delta, 0 net-short sessions)

**No band, ceiling or delta target is adoption-eligible, and the operating
constraint the study set out to test turns out to be a constraint on the study
itself.** Pre-registration: `research/pre-registrations/f4_deployment/portfolio_delta.md`.
Report: `backtests/study_output/portfolio_delta-latest.txt` (run 2026-08-19
17:13, git bfcd512, exit 0 after 15.5s). THE FIREWALL is printed at the top of
the report and holds: nothing ships from this study under any outcome.

**Population: era v3 book 795 rows; deployed picks 220 over 90 dates
(2024-06-17 .. 2026-04-07). PRIMARY = 3 dense episodes / 46 dates; SECONDARY =
the full 118-date book**, which by the same convention `account_sim` and
`selection_order` run under is an availability upper bound and carries nothing
alone. B1 provenance (descriptive, never a gate since the 2026-08-15 constant
purge): 220 positions / 90 dates / $63,553.

- **G-DELTA PASS, and it matters more here than any other gate** — every band
  in this study is a statement about signed delta-notional. Stored signed
  `delta` present on **795/795 (100.0%)**; per-leg greeks available at the entry
  day **795/795**; of those **732 (92.1%)** agree within 0.05 (threshold 90%);
  |leg-sum − stored| median 0.0140, p90 0.0457, max 0.1695. **0 rows excluded
  for a None leg greek** — and the repo invariant held: a missing leg greek is
  None, never 0.0, and such a row would have been excluded and COUNTED rather
  than silently zeroed.
- **G-INVENTORY — the census, and the finding most likely to BE the study.**
  Of 220 deployed picks: **179 bull_call_spread + 41 bull_put_spread**;
  **219 positive delta, 1 NEGATIVE, 0 zero, 0 missing** — and the report names
  the entire short side, a single row (2024-11-06, X, bull_put_spread, delta
  −0.097). Per-date net delta-notional / equity at session open: PRIMARY median
  **+1.703**, range [+0.000, +2.494]; SECONDARY median +1.316, range [+0.000,
  +2.498]. **net-SHORT sessions: 0 in both populations. OUT-OF-BANDS: 0.** The
  registration's central claim is therefore confirmed as measured, not assumed:
  **a band with a LOWER bound is unreachable from below on this book**, and net
  delta can only be moved DOWN by not trading or by re-sizing the hedge sleeve.
- **ARM D (dose-response, descriptive primary) does not separate.** On PRIMARY
  only one band reaches MIN_CELL_N=20 — [1.0,2.0) n=29, meanR +0.325
  CI[+0.090, +0.546] — so **SHAPE: NOT READABLE** (≥3 n-sufficient bands are
  needed before "monotone" means anything), recorded as such and explicitly not
  as a null. On SECONDARY all four bands are readable and the shape is
  **NON-MONOTONE / FLAT**: +0.069 / +0.079 / +0.234 / +0.201. Adding exposure
  onto an already-long book does not visibly pay worse — descriptive only, and
  no band value may be adopted on it.
- **Power, stated precisely because it differs by population.** On **PRIMARY**,
  **only `B ceiling 1.00` clears the ≥25-moved-dates floor** (32 of 46);
  everything else is **UNDERPOWERED** (the report prints the older token
  `POWER-STOPPED`) — B 1.50 at 22, B 2.00 at 19, B 2.50 and B inf at 0, and
  **all three H\* delta-target arms** at 16 / 19 / 20. On **SECONDARY** five
  arms clear (B 1.00 at 58, B 1.50 at 36, B 2.00 at 30, H\* 1.50 at 29, H\*
  2.00 at 31) and are read — but SECONDARY carries nothing on its own, so
  **the delta-target hedge programme is UNDERPOWERED where it counts.**
- **ARM N decides the meaning of everything else**, per the registration: an
  arm must beat the null band's 95th percentile, not merely beat the shipped
  book. PRIMARY draws 200, seed 20260819, p95 **−0.0104**; SECONDARY p95
  **+0.0245**; SECONDARY sleeve-basis p95 +0.1085.
- **The single powered PRIMARY arm fails the bar.** `B ceiling 1.00`: paired
  mean gain **+0.0374 R CI95 [−0.0766, +0.1680] → FAIL c1**; LOO share>0 95%
  with MIN −0.0087 → FAIL c2; by year 2025 +0.0984 / 2026 −0.0298 → FAIL c4;
  it PASSES c3, c5, c6 and — notably — **c7 at pct 100%**, sitting above ARM
  N's p95. On SECONDARY the read arms fail too: B 1.00 fails c1 and c5
  (tweak −0.0062); B 1.50 fails six of seven; B 2.00 fails six of seven;
  **H\* 1.50 is the only arm anywhere whose CI excludes zero (+0.0841
  CI[+0.0102, +0.1683])** and it fails c4 (2024 −0.0199) and c7 (pct 76%,
  inside the sleeve-basis null band) — i.e. it does not beat random admission,
  which is the whole point of ARM N.
- **Verdict, in the registration's vocabulary: NOISE** — no arm exceeds ARM N's
  95th percentile and ARM D's bands do not separate within their cells.
  Recorded; thread closed for these dates.

**Verdict-grammar note, recorded (build-time, labelled, not a
re-registration).** The registered labels left one combination unnamed: an arm
clearing criterion (7) while failing the rest matches none of NOISE /
DELTA-DOSE-RESPONSE / LONG-ONLY-BY-CONSTRUCTION / UNDERPOWERED. Per the
`account_sim` 2026-08-14 lesson — fix the grammar BEFORE a run, never after a
number — the build assigned that case to **NOISE with a printed QUALIFICATION
block naming the arm**, rather than inventing a fifth label after the fact.
That block duly fired for `B ceiling 1.00`, and the report says so in plain
words: NOISE is carrying it as the catch-all, the per-arm checklist is the
whole result, and nothing on it is adoption-eligible. Also recorded in the same
note: the registration's disclosed per-date net-delta figures (median 0.33, max
1.17) were measured on THAT DAY'S PICKS at 1 contract, while G-INVENTORY
measures the OPEN BOOK at session open under production sizing (median +1.70,
max +2.49). Different quantities by definition, both now printed with their
definitions — and the long-only fact (0 net-short sessions) holds under both.

**The standing caveat is not discharged by a null.** The ladder is itself
in-sample, so any exposure rule evaluated on the same book is SECOND-ORDER
in-sample. That does not disappear if the numbers look good, and it is why
adoption would have required out-of-fold survival even had an arm cleared.

**What re-arms it.** New dates, and specifically DENSE ones: PRIMARY is 46
dates across 3 episodes, which is what starves the ceiling and delta-target
arms of moved dates. Note the same trap `account_sim` hit on v4 the same day —
a date floor is not a density floor — so a backfilled v4 era will not re-arm
this study however many dates it accumulates; consecutive sessions will.
Until then the usable output is the census, not a rule: **the book is
structurally long, and any delta-management proposal has to start from that
rather than from a band.**

## 2026-08-19 — Disagreement logs, four-study replication reviews (protocol step 4)

All four studies graded via `scripts.study_review` (analyst A/B + validator; digests
in `backtests/study_output/<name>-digest-latest.md`). Main-session decision: **all
four recorded verdicts ACCEPTED as written.** Per-study log:

- **staged_exit** — one disagreement, RESOLVED mechanically by the validator:
  analyst A graded G2 "NOT MET" while applying the opposite aggregation rule two
  rows later on the same facts; resolves to B's reading (1 of 36 cells passes the
  continuation diagnostic). Verdict unaffected — that cell fails criterion 1
  regardless. Zero number mismatches.
- **emission_timing** — disagreement UNRESOLVED but verdict-neutral: A and B split
  on how to collapse 17 per-cell criterion results into one table row
  (all-must-pass vs any-passes); the registration states a per-cell conjunction and
  never defines a collapsed row, so both readings are defensible and the per-cell
  grading in the report stands. One confirmed transcription slip in B (window-cut
  pass count 10 → 9; changes nothing under B's own rule). A alone flagged a REAL
  coverage gap, logged below.
- **financed_spread** — zero verdict disagreements, zero number mismatches across
  54 shared rows.
- **portfolio_delta** — agreement; B additionally caught that the registration
  gives two readings of "SECONDARY" (v4-era vs sparse-book) and the report
  implements the sparse-book one. Accepted as the operative reading; noted for the
  next amendment if the study re-arms.

**Build-wide gap (logged, deferred):** every registration names era `current`/v4 as
a reported-only SECONDARY; none of the four first-run reports prints such a
section (single-era invocation). Deliberately NOT patched by re-running on
`--era current` now — that would overwrite each `-latest.txt` the reviews just
graded, and the v4 era (34 backfill dates) would underpower nearly every cell
exactly as the registrations predict. The secondary section lands at the next
scheduled re-run of each study (F4 post-scrape for financed_spread; new-dates
gates for the rest).

## 2026-08-19 — `financed_spread` post-scrape run: F4-d20 HOLD is the study's one CANDIDATE — and the operator's own management rule is what was hiding it

Second run, era v3, after the fin_diag scrape (897 fetched + 10 on retry; 171
residual failures are unlisted/expired contracts; F4 coverage ~86% of the
1,256-target census). F0–F3 verdicts unchanged (all NULL). The six F4 cells
(amendment 2): **F4-d20 hold clears the full 7-part conjunction** — paired dR
+0.176 CI [+0.015, +0.354], LOO min +0.143 over 74 folds (100% positive),
windows ex_2025_mar_apr +0.259 / ex_2026_feb_apr +0.073 / ex_BOTH +0.148,
years 2024 +0.019 / 2025 +0.098 / 2026 +0.374, tiers real +0.060 / tweak
+0.259, 74 dates, **E3 −0.134** — the only negative sleeve correlation in all
13 cells. This survives amendment 2's honest residual costing (108/1284
cell-rows that amendment 1 would have forgiven are PAID at their last real
mark; d20-hold residual cost mean 1.240 vs median 0.010 — the tail is in the
number).

The two reads that matter:
1. **The management rule kills the edge on the same rows**: F4-d20 pt50
   +0.052 (NULL), $100 +0.022 (NULL), hold +0.176 (CANDIDATE). The 50%/$100
   buyback fires at mean 3.9/2.8 grid days and returns the remaining decay;
   hold keeps the leg live 17.8 days. The operator's stated close-early
   practice is, for THIS financing leg, the expensive half of the idea.
2. **d10 far-OTM is the losing version**: all three d10 cells NULL-to-negative
   AND re-wrapping (E3 +0.21 to +0.29) — the bear_deploy "cheap far-OTM is the
   losing trade" shape, now on the financing side.

Caveats stated with the candidate: built 117/570 rows / 74 dates
(target_unreachable 237 — the cached ladder often has no strike within 0.10 of
the 0.20 target at the near expiry; no_near_expiry 149), so the cell is a
candidate ON THE BUILDABLE SUBSET; the naked-short tail is real (residual mean
vs median above); assignment mechanics beyond mark-costing (pin risk, early
exercise) remain unmodelled. **CANDIDATE is not a ship**: per the registration
it queues an independent-window confirmation before it may even be proposed
for docs/deployment-rules.md. Re-arms on new dates; the d20 scrape gap
(target_unreachable) could be narrowed by a wider near-expiry strike scrape if
the confirmation window ever needs it.

## 2026-08-19 — Disagreement log, `financed_spread` post-scrape review (protocol step 4)

Second review, on the post-scrape report with the F4 cells priced (the first
review graded the pre-scrape report, where F4 was ungradable). Validator
re-checked all G0–G3, E1–E3 and all 91 C1–C7 cells: **zero numeric
mismatches**, and both analysts independently confirm the VERDICTS block —
NULL ×12, **CANDIDATE for F4-d20 hold**. Two disagreements, both resolved as
cosmetic: (1) analyst A graded the descriptive E2 vega read as a MET row where
B excluded it — the registration gates nothing on E2, so B's omission is the
literal reading and A's label was harmless; (2) A graded the E3 ≥8-shared-dates
precondition as its own row where B folded it into each cell's criterion 7 —
same fact, two presentations. Main-session decision: **CANDIDATE grading
ACCEPTED.** Status unchanged: not a ship; queued for the independent-window
confirmation the registration requires.

## 2026-08-22 — "POWER STOP" RETIRED in favour of **UNDERPOWERED**, and `ml_combination`'s v4 debut FIXED: it died on two columns the v4 bump had already dropped

**Terminology.** The under-the-floor state is now printed as **UNDERPOWERED**
everywhere code prints it, and the mechanism that produces it is a **power
floor** — vocabulary five modules (`book.py`, `macro_event_study`,
`mech_regime_recut`, `bear_position_study`, `regime_gap_reread`) were already
using. `calendar_hedge.POWER_STOP_MIN_N` is now `MIN_N_TO_READ`, which says
what the constant does: below it, the cell is not read.

This finishes a migration `financed_spread` amendment 1 had started for F4
alone while F0–F3 kept the older token "their published reports already
quote". `underpowered_token(shape)` is gone with the split it encoded; the
module exports a single `UNDERPOWERED` constant, and `VERDICTS` no longer
carries the same state twice.

**What was deliberately NOT rewritten.** Every verbatim record — this log,
`research/study-results/`, `research/pre-registrations/`, `research/archive/`,
the dated index rows in `README.md` — still says POWER STOP / POWER-STOPPED,
because those quote reports that literally printed that word. Rewriting them
would have falsified the quote for a change in wording only. `glossary.md`
carries the mapping: same state, retired name, older documents quoted as they
printed. Living prose (`glossary.md`, `next-steps.md`, `study-map.md`,
`catalog.py`) moved to the new wording.

Seven studies re-run to confirm the change is only wording: `calendar_hedge`,
`selection_order`, `financed_spread`, `staged_exit`, `portfolio_delta`,
`emission_timing`, `macro_event_study` — all exit 0, no verdict changed, no
number changed. 2,120 tests pass.

**`ml_combination` on v4: the first genuine casualty of the v4 column drop.**
The study had NO `-latest.txt` at all after the 2026-08-22 18:08 suite run —
it crashed, and the runner correctly refuses to promote a failed report, so
its absence was silent. The crash:

```
ValueError: window shape cannot be larger than input array shape
  sklearn HistGradientBoostingRegressor._bin_data -> sliding_window_view(distinct_values, 2)
  ml_combination.py:424  phase2_models -> M1
```

`NUM_SCORES` names `score_flow` and `score_dealer`. Those were dropped at the
v4 bump — `lib/era.py::V3_ONLY_COLS` already treats their absence as the
DEFINITION of the era — and they arrive 100.0% blank on every v4 row. The
study's own Phase-0 census printed exactly that (`score_dealer 100.0%`,
`score_flow 100.0%`) and the median imputer said so too (`Skipping features
without any observed values: [57 58]`); the elastic net tolerated the all-NaN
columns, HistGBM's binner did not — zero distinct values, and a 2-wide window
over zero values raises.

Not a thin-era refusal: the era is fine (78 book dates, 517 rows, 4 test
blocks). An era-blind feature list, in the one study that hardcodes the two
columns the era is detected BY.

Fix: `design_matrix` drops columns with no observed value ONCE, on the whole
book — never per fold, so every fold and the permutation-importance pass keep
the same columns, and emptiness is a property of the export rather than of any
label. The Phase-0 census builds the undropped matrix so it can still NAME
what it dropped, and now prints `era-absent features (2, ...): score_dealer,
score_flow` above the missingness table. The fold-local case (a merely-sparse
column absent from ONE training fold) is REFUSED with a diagnosis rather than
patched: dropping per fold would leave the ablation and importance numbers
built on feature sets that are not the same set, which is what this study
compares.

`ml_combination` now exits 0 on era v4. Its first v4 numbers are NOT read here
— B0 $34,744 / meanR +0.257 over 168 positions is the benchmark, and the
model arms are for the write-up, not for this note.

**Carry-forward, not run today: the `analyze_bt_queue.sh` backfill has 20
dates stuck as permanently-skipped partials.** Five of them (2025-02-07,
2025-05-19, 2025-06-05, 2025-08-01, 2025-08-19) ALREADY have their analysis
rows in the tab — 11–13 each — so `RETRY_PARTIAL=1` on queue b would duplicate
them, which the tab has no dedup to catch. The other fifteen wrote nothing and
are safe to retry. Verified today: 87 dates in the export, one run timestamp
per date, no duplicates yet.

## 2026-08-22 (late) — operator read "more deployed = works less": the ladder's DEPTH is not the problem, the book's SIZE is unmeasured. v3 day-level cuts DIED on v4; `concurrency_correlation` pre-registered

Operator observation, unprompted: *"the more that is being deployed, the less
it seems to be working."* Three passes — an inventory of what actually gates a
deployment today, a sweep of the existing record, and fresh cuts on both eras.
Populations named per figure; nothing here is a shipped rule.

**What gates a deployment today (inventory).** BINDING: the three §1 vetoes,
the §1.4 bear-debit redirect to the hedge sleeve, the A/B/C tier bucket (Tier C
is rejected), the §3 bull_put geometry (nominally binding, practically
unverified — `short_leg_delta` is not a `ROW_COLUMNS` column), and the
freshness/lookahead bound. ADVISORY ONLY: `DEPLOY_BUDGET = 3` (a LABEL — `rank()`
returns every survivor and `render()` printed all of them), the 0.25/2.50
exposure caps, duplicate-ticker exposure, and `judge()`. **No gate anywhere
counts concurrent open positions, and no gate raises the bar for the Nth play
of a day over the 1st.**

**Depth into the survivor list is FLAT, on both eras.** Deployed-order replay
of Tier A/B survivors, mean R by within-day rank:

| rank | v3 (795 rows / 118 dates) | v4 (517 rows / 78 dates) |
|---|---|---|
| 1 | +0.178 | +0.155 |
| 2 | +0.527 | +0.372 |
| 3 | +0.445 | +0.269 |
| 4-5 | +0.281 | +0.263 |
| 6+ | +0.323 | +0.257 |

Cumulative top-K on v3 plateaus at +0.364 (K=3) and is still +0.344 at K=8.
This does NOT contradict the recorded `top-1 +0.82 / top-3 +0.45 / all +0.14`
(607-row pooled book, 2026-07-19): that measures depth into the whole EMISSION
list, whose tail is Tier C and VETO, both negative every year (n=587 / n=145).
The tier gate does the work; the count cap inside the survivors does almost
none. **A tighter top-N is not the missing gate.**

**DEAD END, recorded so it is not re-found: two v3 day-level cuts that do not
survive the v4 bump.** Deployed top-3, mean R:

| cut | v3 | v4 |
|---|---|---|
| day had Tier A supply | +0.475 (n=137, 57 dates) | +0.247 (n=56, 27 dates) |
| Tier-B-only day | +0.182 (n=83, 33 dates) CI[-0.005,+0.369] | +0.257 (n=112, 45 dates) |
| model BULL + L-VOL | -0.050 (n=43, 15 dates) | +0.224 (n=102, 40 dates) |
| all other regimes | +0.465 (n=177, 75 dates) | +0.299 (n=66, 32 dates) |

On v3 the BULL+L-VOL cell held its sign in EVERY robustness cut (both halves,
2024 and 2025, real and tweak pricing, pre- and post-13c; date-clustered
p=0.0042), and all 15 such dates carried ZERO Tier A supply while emitting 4.87
Tier B per date against 1.24 elsewhere — i.e. the days with no A-tier flooded
the card with B-tier. It was a clean story and it is gone on v4: the gap is
+0.257 vs +0.247, and B-only days are now the MAJORITY (45 of 72 dates, vs 24%
on v3) because Tier A share collapsed across the bump (v3 131 A / 166 B; v4
58 A / 172 B). This is `v4_bridge`'s `LADDER UNVALIDATED ON v4 — ladder tier
mix shifted, chi2 p = 0.0000` claiming a victim. **No gate was built on it.**

**What the record already had, and what it never measured.** Established: tier
depth is monotone and C/VETO are negative every year; taking every emitted play
makes +$14.0k over three years against +$76k for the top-3 replay — the value
is in the triage, not the generation. Directional and independent:
`archive/08`'s discretionary book (468 closed trades) shows P&L per trade
falling monotonically with same-day trade count — 1/day +$119 · 2-3/day +$25 ·
4-6/day +$9 · 7+/day -$18 — with win rate FLAT at 51-59%, which is dilution
rather than worse reads on busy days. Already refuted: `portfolio_delta` ARM B
(128 -> 68 positions, paired gain -0.0164 R, FAIL) and ARM D (NON-MONOTONE /
FLAT, verdict NOISE) — both cut on DELTA CEILINGS. **Never studied at all:
concurrency vs outcome (census only — v3 median 8 concurrent, p90 29, max 48;
`account_sim` computes `n_open` and no report joins it to anything), and
correlation between concurrently held plays (every "correlation" in the repo is
sleeve-vs-book).**

**The live book, for context, not as evidence.** Open legs 3 -> 19 since May;
opening orders per week stepped rather than drifted, breaking the week of
2026-07-27 (19 in that week). Win rate rose over the ramp; average win / average
loss collapsed 1.53 -> 0.25. One TSM close is 48.8% of gross wins in the record
— strip it and the before/after profit factor is 0.76 vs 0.59, same direction,
much weaker. Both persisted deploy cards (08-14, 08-17) emitted 8 candidates,
100% Tier B, 100% `bull_call_spread`, in a BULL regime, with SNDK/MU/AMD on
both. The v4 book is long-only by construction (`positive 168 / NEGATIVE 0`,
`net-SHORT sessions 0`).

**Shipped today (production tier).** `render()` now treats the budget as a CUT
rather than a label: budgeted picks keep the full block, reserves collapse to
one line each under `### Reserve — N NOT for deployment` with prose saying a
reserve REPLACES an untradeable pick and is never a fourth position. `rank()`
is UNCHANGED — every survivor is still returned and still persisted, so the
record loses nothing; this is presentational, and it is presentational because
the card showed eight fully-specified plays under a 1-3/day rule. Also added:
an ADVISORY `**Book concentration:**` block (open positions, distinct tickers,
long/short/unpriced split, a warning when every priced position points the same
way, and a warning naming a budgeted pick whose ticker is already open). It
filters nothing and says so — no concurrency rule has been backtested.

**Registered, not run.** `research/pre-registrations/f4_deployment/concurrency_correlation.md`
— ARM N null band, ARM D0 descriptive, ARM C concurrency ceiling {5,8,12,20},
ARM K clustering ceiling {2,3,5} on direction / direction+sector / underlying,
ARM CK only if C and K clear independently. X4 (both eras, same sign, within
0.15 R) is expected to be the binding criterion, and X7 refuses any arm that is
a delta ceiling in disguise — ARM B and ARM D already failed that axis. The
module is NOT written; the plan exists before the code on purpose, and it
carries the dead-end table above so the study cannot re-find those cuts and
call them new.

**Three stale figures corrected.** (1) `deployment-evidence.md:39` quoted
`top-1/day 76% win / +0.35 mean`; the log says `+0.41` and by that file's own
precedence rule the log wins. (2) `selection_order.py` printed `changes only
7-14% of O0's taken positions` as a HARDCODED prose literal — the measured
census is 15%-24% (PRIMARY) / 11%-21% (SECONDARY); it now interpolates the
run's own `g0[n]["share"]` values, and the study-map verdict quoting the old
number was rewritten against the current report. Verdict, gates and every
numeric table are byte-identical to the pre-edit run. (3) The v3 claim that
`account_sim`'s rejected picks out-earn its taken ones REVERSES on v4 — the
sign flips in 7 of 8 frozen/compounding x PRIMARY/SECONDARY cells (PRIMARY:
taken +0.338 vs rejected +0.134 / +0.130); only one n=9 cell still favours
rejected. Corrected in the `account_sim` verdict, the `selection_order` verdict
and question, and `selection_order.py`'s docstring, which cited it as live
motivation.


## 2026-08-24 — v4 refresh evaluated: first rollback-trigger census (be_after REVERTED, LVOL cleared-but-held), the credit book calibrates for the first time, `exit_mechanism_study` repaired

Bare exports refreshed 2026-08-24 17:09; full suite re-run (25 reports, era v4,
git `c841a01`, exit 0, all recorded via `study-record`). Pooled book **567 rows
(real+tweak) / 87 dates** — up from 517/78 on 08-22. The provenance headers'
apparent shrink (results "1,212 rows" → "280 rows") is NOT a population change:
every header before today was a LINE count over `daily_price_csv`'s embedded
newlines — the exact `wc -l` hazard the 08-14 method note warned about, sitting
in the runner itself. `run.py` now counts CSV rows; every report recorded in
`research/study-results/` before 2026-08-24 overstates its input counts ~4×.

**Rollback-trigger census — the four shipped-rule forward triggers evaluated
for the FIRST time** (they were prose only; nothing computed "affected dates").
Pre-registered before the runs in `research/pre-registrations/f2_management/rollback_triggers.md`;
one definition of affected/arming in `scripts/backtest_study/lib/triggers.py`;
all census blocks additive. v4 is a CORRELATED-WINDOW re-read (new plays from a
new prompt version on the same historical signal dates) — registered as such,
with the operator's act-only-if-decisive reading committed before any number
was read.

| Trigger | Census | Outcome |
|---|---|---|
| bear-debit `be_after 0.50` | 92 arming rows / 53 dates ≥ floor 60 | condition three **FIRED** → **REVERTED** |
| LVOL tef-null (corrected gate) | 31 affected dates ≥ floor 25 | all four criteria PASS — **CLEARED, operator HELD the ship** |
| BEAR_HE trail | 1 affected date of 25 | decisively UNDERPOWERED — census is the result |
| credit sl-none | 0 fresh bull_put rows of 15 | UNDERPOWERED — comparator now printed by every credit run |

- **be_after REVERTED** (`structure_exit.enabled: false`, commit `1e36dba`).
  The trigger's three conditions on the arming rows: (a) total gain vs PROD
  **+$58** — pass, but ~zero against the −$54.4k → −$38.0k the rule shipped on;
  (b) mean-R on affected rows +0.0071 — pass; (c) per-year mean-R delta
  2024 +0.022 / **2025 −0.034 → FIRE**. Operator decision per the registration:
  revert. Block and evidence kept verbatim in config; re-entry only through a
  fresh registration. `docs/deployment-rules.md` loses the ratchet row.
- **LVOL tef-null cleared its corrected gate** (median among affected dates
  +0.023 > 0, total +5.70 > 0, halves +3.99/+1.71, no perturbation flip) — the
  first time the 07-22 corrected gate has been computable at all. Operator HELD:
  no urgency asymmetry (unlike BEAR_HE's bear-leg protection) justifies an
  in-window ship. Re-gate when the affected-date count includes genuinely new
  dates. The original six-criterion gate still reads 5/6 (`LOO median > 0`
  fails by construction) — `STAYS GATED` on that axis, unchanged.

**`exit_mechanism_study` repaired — its v4 "CALIBRATION FAILED" was false, and
its credit baseline was a retired rule** (commit `038cdc6`). The 08-22 banner's
14 mismatches were exactly the shipped overrides' own output (13 `be_stop` +
1 `trailing_stop`) — the failure mode diagnosed 08-14 and repaired in the three
gate-sharing studies, which this study never received. `calibrate()` now
classifies via the shared `lib/replay_basis.py` (extracted verbatim from
`exit_switch_mech_study`): debit **191 exact / 0 near / 16 superseded-basis /
0 HARD of 207**, banner reserved for HARD, `main()` stops on it. The worse
find: its local `CREDIT_PROD` still carried the pre-Attempt-13 `sl=1.00` —
every credit Δ since 07-13 was measured against a stop production had removed,
and the variant named "sl none" WAS production. Profiles now import from
`lib/book.py`, test-pinned against `config/backtest.yml`. The study's duplicated
replay engine (byte-identical to frozen `lib/harness.py`) is deleted in favour
of the import, so the whole f2 import chain sits under the pinned fixture. A
new `-credit` ARM joins `run --all`: **73/73 exact** — the v4 credit book is
single-basis and calibrates against shipped PROD for the first time
(`book.py`'s standing "no single credit PROD" caveat is not true of this era).

**Debit variant grid = the reactive null, re-confirmed on 207 rows.** Best
trail variant `trail .25 trig .75` Δ=+$1,679 but **Δ-LOO −$501** (one trade);
every other trail negative on both. Two non-reactive in-sample positives worth
recording as observations, NOT candidates (selected on the file they score):
`pt .75 no trail` Δ=+$4,354 / Δ-LOO +$1,734 — the second era in which a lower
profit target has looked good on debit — and `BE ratchet @.75` Δ-LOO +$806.
Credit side: `sl 1x (pre-Attempt-13)` Δ=−$3,468 / Δ-LOO −$3,853 vs PROD —
Attempt 13 re-confirmed hard, though on the correlated window, not the fresh
one the trigger names.

**Suite movers** (catalog verdicts refreshed for 20 studies, quoted verbatim):
- **`bear_deploy` REVERSED on v4**: D2 (hedge is real), D3, D4 all NOT MET —
  the shipped "take the closer-to-money bear" pick reads −0.004 vs the day
  average (CI [−0.166,+0.166]). That line sits in `docs/deployment-rules.md`
  on v3 evidence and now has no v4 support. No prereg file exists, so it
  cannot go through `study_review` as-is. **QUEUED (operator): register a
  re-read before re-affirming or pulling the card line.** Not acted on today.
- **`bear_rewrap` promoted `long_diag`**: all five criteria pass on v4
  (dR +0.353 CI [+0.121,+0.613], LOO min +0.275 over 61 folds, worst-decile
  meanR +0.902 CI [+0.275,+1.498] → P1 MET, P2 MET; bear sleeve −0.168 →
  −0.003). First full-conjunction pass for a bear wrapper — on a population
  `bear_position_study` still DEMOTEs on E (−0.288 at n=177, re-confirmed
  today). Candidate for independent-window confirmation, NOT shipped.
- **`emission_timing` ARM P sign-flipped**: v3 +0.054 (CI spans 0, null) →
  v4 **−0.205 CI [−0.379,−0.031] EXCLUDES 0**, reported as
  `STALE-ENTRY-PENALTY (CANDIDATE, NOT A SHIP)`. Two-analyst review run today
  (Disagreement log below).
- **`financed_spread` F4-d20**: the graded v3 candidate is UNDERPOWERED on v4
  (20 rows / 19 dates, under the G0 floor — no criterion evaluated). Review
  run today to decide carry/re-scope/shelve (Disagreement log below).
- `ml_combination` NULL again, gap wider (M3 out-of-fold −0.103 vs B0).
  `account_sim` FEASIBLE, and the v3 "rejected out-earn taken" reversal is now
  complete in all 8 cells. `staged_exit` null again, thinner (24/96 powered).
  `v4_bridge` unchanged (`LADDER UNVALIDATED ON v4`) — its catalog entry was
  two runs stale and factually wrong (claimed the study still aborts); fixed.
- `exit_switch_structure_study` STAYS GATED (1/6); new Q2 retention detail:
  the shipped BEAR_HE clause retains 0% of its gain outside its cell, the
  rejected bear_put trail 187% — the composition guard is doing its job.

**Infra shipped today** (all committed): the calibration repair + shared
classifier (`038cdc6`), `lib/triggers.py` + census blocks (`e54b4cd`), the
credit ARM + `make study-record` footer (`c841a01`), the be_after revert
(`1e36dba`), the Makefile study-surface consolidation (`d9f2853` — ONE
parameterized `study-chart CHART=account_sim|regime|compounding [ARM=structure]
[OPEN=1]` replacing seven targets, `study-check`, `RECORD=1` chaining,
`tests/test_makefile_targets.py` pinning every documented target), and
`lib/gex_snapshot.py` retired (`f3a7b2e`, zero importers, operator-confirmed).

### Same-day addendum — two-analyst review pass: the ARM P "candidate" is OFF-BASIS, and a new standing hazard

`study_review` ran on the two verdict-movers (`emission_timing`,
`financed_spread`; analyst A + B in parallel, validator, digest — artifacts in
`backtests/study_output/*-review-*-latest.md`). The pass earned its cost twice
over:

**CORRECTION — `emission_timing` ARM P is retracted from mover status.** Both
analysts, independently: the registration pins PRIMARY to `--era v3` (795 rows
/ 118 dates) and declares the v4 basis SECONDARY ("carries nothing… never
pooled"), and the report ran bare-era (v4) with no `--era v3` anywhere in its
command line. The 08-19 log had additionally marked ARM P a post-hoc watch for
NEW DATES ONLY. So the "STALE-ENTRY-PENALTY (CANDIDATE)" printed above is an
off-basis observation on overlapping dates — if anything, a sign flip between
eras on the same dates argues era-composition, not timing. The v3 NULL stands;
the catalog verdict is corrected. Analyst A also caught an internal
contradiction the study should fix: the ARM L headline says LAG-TOLERANT while
the report's own two tercile L=3 cells print `** CANDIDATE`.

**NEW STANDING HAZARD — the v4 book contains NO 2026 dates (BacktestResults
signal_dates end 2025-08-19), so every 2026-keyed robustness cut is a silent
no-op on it.** Analyst B proved it mechanically: all 17 `ex_2026_feb_apr`
values in `financed_spread` (and every one in `emission_timing`) are
numerically identical to their `ALL` column. Consequences: "positive every
calendar year" on v4 means 2024+2025 only; window-cut conjunctions collapse
from three cuts to two; and **`bear_rewrap`'s long_diag "passes all five" is
partly vacuous — 2026-alone is exactly the cut that killed `long_put` in the
original run, and this book cannot ask it.** Catalog caveated. Any v4
conjunction pass that cites year-stability inherits this until 2026 dates
land in the results export.

**Both underlying reports also violated their registrations in smaller ways**,
now on record: `financed_spread` prints `$` on substitution cell lines
("Dollars are never quoted on a substitution" — its own registration; queue a
report-format fix), and `emission_timing`'s G0/G3 headers both claim to run
first. Validator scope call left to this session: analyst A graded the
harness gates (G1/G2/G3) MET as code properties, B graded everything NOT
EVALUABLE on the wrong basis — resolved here as A's reading for CODE claims
(the gates are tested in `tests/`), B's for POPULATION claims (no criterion
verdict from an off-basis run is quotable).

**Disagreement log** (protocol requirement): `emission_timing` — G1/G2/G3
MET (A) vs NOT EVALUABLE (B), resolved as scoped above; A-only catches: the
ARM L internal contradiction, the G0/G3 header contradiction; B-only catch:
the `ex_2026` no-op. `financed_spread` — E2 MET (A) vs NOT EVALUABLE (B),
resolved for B (E2 is descriptive, "nothing is gated on it" — A answered a
non-evaluable item); B-only catches: the `$`-on-substitution violation, the
`ex_2026` no-op; A missed both, neither analyst wrong on any number
(validator source-checked every quoted figure; all matched).

**QUEUE updates from the pass:** (a) graded v3-registered studies re-run on
era v4 print criteria against the wrong PRIMARY — for a GRADED read, run
`--era v3`, or amend the registration with a dated v4-basis section first;
(b) `financed_spread` F4-d20 carry-question resolved as CARRY, UNCHANGED:
UNDERPOWERED on v4 (20 rows / 19 dates) is a census, not a refutation — the
graded v3 candidate still waits on its independent-window confirmation;
(c) fix the `financed_spread` $-print and `emission_timing` header/headline
contradictions (report-format, no numbers move).


## 2026-08-24 (late) — `bear_deploy` registered and graded: pick line PULLED, sleeve relabelled operator policy, far-OTM prohibition retained

The 08-24 suite refresh left `bear_deploy` REVERSED (D1–D4 all NOT MET) with
no way to grade it — its original registration is `ml-plan.md` §addendum 2
(2026-08-11), which predates `research/pre-registrations/`, so `study_review`
had no file to hand the analysts. Written today, before grading and before any
card edit: `research/pre-registrations/f4_deployment/bear_deploy.md` — the original D-rules
quoted verbatim, plus a v4 re-read section pinning the decisive read, the
binding basis (R under the SHIPPED PROD exit, since `be_after 0.50` was
reverted this morning), RE-1…RE-4 card-edit decision rules, and the operator
pre-commitment (stated 2026-08-24: *"i still want bear positions as hedge"*)
that the §4 sleeve is policy and EXEMPT from data-driven removal. The file's
honesty note names the three already-seen runs — this registration pins
decision rules, not blindness; only its forward trigger (≥20 multi-candidate
bear dates on post-2026-08-11 signals) is blind.

**Graded** (`study_review bear_deploy`, analysts opus ×2, validator sonnet;
fresh run 19:15 reproduced the 18:23 verdicts exactly — same inputs `46cc19b`):

- **D1–D4 all NOT MET — unanimous, every quoted number source-checked.** D4:
  0 of 10 rankers adopted (~0.5 expected by chance).
- **RE-1 FAIL → the §4 pick line is PULLED.** `|delta| high first` (the
  shipped "closer-to-money" rule) gain −0.004, CI [−0.166, +0.166], LOO min
  −0.045. §4 now reads "pick is operator discretion"; a null does not flip
  the preference, and no new ranker may be adopted from this correlated
  window (`iv_spread high first` +0.148 and `iv_pct high first` +0.110 are
  the eye-catchers the window rule exists for — CIs span zero anyway).
- **RE-2 MET → far-OTM prohibition RETAINED** with a v3-era citation:
  `|delta| low first` gain +0.017, CI [−0.133, +0.168] spans zero — v4 does
  not contradict the prohibition.
- **RE-3: size line unchanged** (policy-held; D3 has never been MET at any
  size — the one analyst disagreement, MET vs NOT EVALUABLE on how to grade a
  policy-fixed line, is vocabulary, not numbers; both confirmed the same D3
  figures).
- **RE-4 → sleeve relabelled OPERATOR POLICY** in §4: D2 NOT MET (tail R on
  worst-decile dates negative, correlation −0.087, tail positive in 0/2
  years) and within-era UNSTABLE (D2/D3 flipped MET → NOT MET between 08-22
  and 08-24 on +50 rows / +9 dates).

**Report defects the review surfaced** (analyst A catches, validator-confirmed;
queued, no numbers move): (a) D3's DEVIATION prose hardcodes "−0.345 vs day
average" for the widest-max_loss picker — a v3-era figure sitting in the
STUDY'S OWN PROSE while the same report's D4 table prints −0.083; the
never-hardcode rule, in prose form; (b) D2's pass rule evaluates worst-DECILE
dates but its ≥2-years reproduction check evaluates worst-QUARTILE dates —
two different cuts feeding one criterion, silently; (c) the D4 table doesn't
name its basis (Rb) in its header, which is what let the binding-basis gate
go NOT EVALUABLE. All three are report-format/prose fixes in
`bear_deploy.py`, none touch a computed number.

Card edits applied to `docs/deployment-rules.md` §4 exactly per the
registration. Artifacts: `backtests/study_output/bear_deploy-review-{analyst-a,
analyst-b,validator}-latest.md` + `bear_deploy-digest-latest.md`. The
study-results record for era v4 · inputs 46cc19b (18:23 run) stands — the
19:15 grading run reproduced it bit-for-bit, no new append.

---

## 2026-08-24 (docs) — ARM labels are STUDY-LOCAL and STAY single letters; `research/arm-index.md` indexes every one, BY STUDY

**The problem, stated precisely.** It is not that arms are letters — it is that
looking one up costs a repo-wide grep. `ARM P` has FOUR owners: `emission_timing`
(persistence — repeat vs first emission), `macro_event_study` (H2 outcomes by
event proximity), `bear_giveback` (the `be_after` production baseline) and
`bear_rewrap` (portfolio contribution, P1/P2). `grep "ARM P"` returns ~200 hits
across `scripts/`, `research/` and `backtests/study_output/`, and the majority
are not definitions at all — they are one study CITING another's arm without
naming it: `emission_timing`'s `ARM C` mentions all mean `next_day_move`'s;
`financed_spread` and `selection_order` cite `calendar_hedge`'s `ARM S`;
`concurrency_correlation` cites `portfolio_delta`'s `ARM B`/`ARM D` while its
own arms are C/K/CK/D0/N. Resolving a cited letter against the file you are
reading gives the WRONG arm.

**Renaming was considered and rejected.** Letters stay. A pre-registration is
immutable; `scripts/study_review/`'s analysts grade against the label strings
the reports printed; `current.md`, `archive/`, `study-results/` and the
committed `*-review-*.md` gradings all quote them. The audit chain is worth more
than label prettiness, and the actual need was lookup speed, not new names.

**What shipped:**

1. **`research/arm-index.md`** (new) — every arm label with its owning study,
   grouped BY STUDY in the four family folders' order (①–④, then studies still
   queued with no module yet) with an up-front collisions note, so everything
   a study owns reads in one place. Covers the `ARM <letter>` arms, the
   non-`ARM`-form arms (`selection_order` O0–O4/O1b, `financed_spread` F0–F4
   and its F1/F2 collision with `account_sim`'s unrelated 1-contract-floor
   F1/F2), and the labels that only look like arms (G* gates, `calendar_hedge`'s
   H0–H5 criteria vs `macro_event_study`'s H1–H4 hypotheses, `bear_deploy`'s
   D1–D5).
2. **`tests/test_arm_index.py`** — every `ARM <label>` token in a live study
   module or pre-registration must be in the index (a newly registered arm
   cannot skip it), and the four `ARM P` owners are pinned; descriptions are
   NOT tested — operator's own words.
3. **Digest pages** — `scripts.study_map.build` now renders each
   `backtests/study_output/<study>-digest-latest.md` to
   `site/<study>-digest.html` (hyphenated) and the study's card on
   `site/study-map.html` links it — the plain-language write-up was
   previously stranded in a gitignored directory no reader visits.
4. **Doc touch-ups** — `glossary.md` §9 ARM entry + §11 see-alsos,
   `pre-registrations/README.md`'s "Arm labels" section (the one forward
   rule: qualify every citation with its study), `research/README.md`'s
   pointer, and the `CLAUDE.md` `research/` row — none mention any lookup
   tooling; the index is for reading, and the reader's surfaces are
   `site/study-map.html` and `research/`.

## 2026-08-24 — Pre-registrations consolidated to one template; study_review dry-run clobbered two reviews' artifacts

All 14 files under `research/pre-registrations/` reformatted to a single
template (editorial only — no gate, bar, arm, or verdict changed meaning):
`## <slug>` heading + `_Registered <date>._` line, canonical section names,
and every dated AMENDMENT / wording-correction section folded into the section
it amends (superseded rules removed as live text; git history carries what
changed and when). README gained the template spec + two legend rows
(Ship criteria; POWER-STOPPED→UNDERPOWERED, re-homed from financed_spread);
CLAUDE.md's immutability sentence now reads commitments-immutable /
file-consolidatable. `load_pre_registration` verified on the amended studies;
the macro_event_study and rollback_triggers filename-fallback extractions are
incidentally fixed.

INCIDENT: the verification step `study_review <s> --skip-run --dry-run`
OVERWRITES the `-review-*/-digest-latest.md` artifacts with 51-byte
placeholders (--dry-run does not guard those writes). Recovered byte-exact
from session transcripts: `financed_spread-digest-latest.md`,
`macro_event_study-review-validator-latest.md`. LOST (now carrying dated
loss notes in place): financed_spread analysts A/B + validator,
macro_event_study analysts A/B + digest. Verdicts survive in this log's
2026-08-19 disagreement-log entry (all ACCEPTED as written); reports intact.
Follow-up candidates: make --dry-run write to a scratch stem, and regrade via
`study_review <s> --skip-run` only if the full artifacts are wanted again.
