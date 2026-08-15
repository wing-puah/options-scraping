# Archive 13 — 2026-08-13: account_sim & calendar_hedge — pre-registrations, runs, caps

Covers the first half of the 2026-08-13 study day: the `account_sim` $25k
feasibility study (pre-registration pointer; the RUN — caps survive, window
doesn't, delta binds not cash; the same-day lookahead audit + G5 blindness
gate addendum), the `calendar_hedge` RUN (R4 exact, H2 power-stopped at n=6,
wrong-signed correlation) and its `--arm S` structure sweep (30/30 cells
power-stopped), the operator-chosen SIZING ARM, the move of the study's
parameters into `config/account-sim.yml`, and the 0.25x / 2.50x cap
reconfiguration. Ordering follows the log (newest first).
See [../README.md](../README.md) for the full section index.

---

## 2026-08-13 — `account_sim` caps reconfigured to 0.25x / 2.50x: the verdict does not move, and loosening the net cap made the adverse ordering WORSE

**Status: CONFIG CHANGE + INFRA FIX. Nothing ships. The verdict is unchanged.**

The operator raised `caps.net` 1.50x → 2.50x in `config/account-sim.yml`
(per-position stays 0.25x) and reported seeing no change in the results. The
results had changed; the **chart page had not been re-rendered**. See the infra
section below — that staleness is the more important item here.

**What the cap change did.** Both cells below are read off the SAME run's cap
grid, so they are directly comparable:

| configured cell | positions | dates | dollars | meanR |
|---|---|---|---|---|
| 0.25x / 1.50x | 51 | 28 | $7,860 | +0.278 |
| 0.25x / 2.50x | 72 | 37 | $11,399 | +0.290 |

**The verdict does not move:** A1–A4 MET, **A5 NOT MET, A6 NOT MET**, `NO
VERDICT MATCHES` — the same landing as at 1.50x. What moved inside the
checklist: A2 99% → 90% (a different and larger date set, not a like-for-like
worsening); A5's ex-2025-Mar/Apr swing +111pt → **+41pt** (still over the 15pt
bar); A6's debit-only CI [−0.093, +0.440] at n=39 → **[+0.021, +0.435] at
n=55**, now excluding zero, but still NOT MET because 2026 alone is −0.008 and
A1 must hold every year.

**The finding worth keeping: loosening the net cap did not relieve the binding
constraint, it raised the quality of what the constraint keeps out.**
`net_delta` is **still** the most binding constraint at 2.50x (40 of 76
exclusions; **cash binds zero times**, as it did at 1.50x), and the picks it
still excludes return meanR **+0.624** against +0.290 taken — a +0.333 gap. At
1.50x that gap was +0.431 vs +0.278, i.e. **+0.153**. Admitting 21 more
positions roughly doubled the adverse-ordering penalty on what remains excluded.

No cap value may be read off the P&L for this, and the reason is mechanical
rather than procedural: the grid is **monotone 4/4 in the net cap** by
construction — the book has positive mean R, so looser is always richer, all the
way to the uncapped cell at $17,622. The grid therefore cannot identify a cap;
that number has to come from what the account can actually carry (margin, delta
tolerance), and setting it to what is true of the account is simply making the
simulation more accurate. What **is** readable is the *ordering*: at both cap
settings the ladder-rank walk spends exposure on earlier-ranked picks that
underperform the ones the cap then excludes. That is a **selection-order**
problem, not a cap problem, and it is now the strongest open lead this study has
produced.

**Infra fixed in the same change (the actual bug).**

  * `scripts/backtest_study/run.py` auto-refreshed the study **map** after every
    run but never the **chart pages**, so `site/account-sim-charts.html` kept
    quoting the previous run's numbers with no warning. A study run now
    re-renders the charts too. `make study-docs` already did this; nothing
    prompted anyone to run it.
  * `scripts/study_charts/` hardcoded config-driven values into page prose —
    the standfirst's caps and positions/day, and the utilisation panel's net-cap
    reference line (pinned at `v: 1.5`). All now read out of the parsed report,
    so a config change can never again be contradicted by the page describing
    it. `report.py` gained a `max_per_day` parse and accepts `inf` in the
    headline cap cell (a legal value when a cap is `null`).
  * `scripts/study_charts/series.py` — two **pre-existing** reconciliation
    defects that the wider book exposed: a float-epsilon comparison (0.625
    against a report printing `62%` failed by 4e-18) and a flat $1 tolerance on
    a regime TOTAL summed from a dozen independently-rounded cells. Both now
    tolerate display rounding only; a real mismatch still fails the build.

**Config-file framing corrected.** The note in `config/account-sim.yml` saying
the pre-registered values were the record of "what the frozen study ran with"
is removed. The file is the simulation and is meant to be edited; the
`## account_sim: PRE-REGISTRATION` section below stays where it is, because
`scripts/study_review/core.py::load_pre_registration` locates it by heading.

---

## 2026-08-13 — `account_sim` made CONFIG-DRIVEN: the study's parameters move to `config/account-sim.yml`, the module holds no state, and no number moves

**Status: REFACTOR ONLY. No result changed.** The regression bar was that a
default run reproduce the previous one exactly, and it does:
`account_sim-positions-latest.csv` is **byte-identical** before and after, and
every data-bearing line of the report is unchanged. The only report differences
are three deliberate wording changes, listed below.

**What moved.** `scripts/backtest_study/account_sim.py` had accumulated a second
job on top of simulating: policing its own pre-registration. It carried two
parallel constant blocks (`PREREG_*` mirroring the editable sizing constants), a
module-level mutable `ARM` rebound with `global` inside `main()` and then read
implicitly from `Cfg`'s field defaults and four report functions, a second
module-level `_MEMO` cache, and self-labelling machinery (`is_preregistered`,
`Arm.tag`, a "SIZING ARM" banner, an arm-suffixed CSV stem). All of it is gone.

The parameter surface is now `config/account-sim.yml` — capital, risk %,
positions/day, the two delta-notional caps, the cap and capital grids, the hedge
fraction, the dense-episode definition, the A2/A3/A5 thresholds, and G1's
expected book line (220 / 90 / $63,553). It is read once into a frozen
`Settings` and passed explicitly wherever it is needed; `load_settings()` raises
on **any** missing key rather than half-reading a config and printing a full
report against sizing nobody chose. The four sizing flags
(`--capital`, `--risk-dollars`, `--per-pos-cap`, `--net-cap`) are replaced by a
single `--config PATH`.

**Two latent problems closed on the way.**

  * `top_k_per_day(..., k=3)` was hardcoded at the call site while
    `MAX_POSITIONS_PER_DAY = 3` lived separately. Changing one would have failed
    G4 for no visible reason. Both now come from
    `account.max_positions_per_day`.
  * `_MEMO` was module-global. It is now an explicit `cache` owned by the caller
    (`new_cache()`), and **G5's blind probe takes its own**. That is load-bearing:
    the memo is keyed on `id(rec)` precisely so a blind result can never be
    served from a sighted computation, which is what makes the gate mean
    anything. A global cache also let answers leak between runs in a process.

**Report wording changes** (paired with `scripts/study_charts/` in the same
change, since `report.py` is a strict parser):

  * cap-grid headline `(pre-registered, ...)` → `(the configured cell, ...)`
  * `NOT FEASIBLE AT $25k` → `NOT FEASIBLE AT $25,000`, formatted from the
    configured capital
  * `NO PRE-REGISTERED VERDICT MATCHES` → `NO VERDICT MATCHES`

**What this does NOT change.** Selection, exits, the harness, the book loader and
all five gates are untouched. The values pre-registered on 2026-08-13
($25,000 / 2% / 0.25x / 1.50x) are still the shipped defaults, and the
pre-registration itself is still recorded below — in this log, which is where a
pre-registration belongs, rather than mirrored in source where it was being
diffed against on every run.

**Reproducing the sizing arm below.** The arm recorded in the next section was
run with `--risk-dollars 1000 --per-pos-cap 0.40 --net-cap 2.50`. Those flags no
longer exist: copy `config/account-sim.yml`, set `risk_per_trade_pct: 0.04`,
`caps.per_position: 0.40`, `caps.net: 2.50`, and pass `--config`. Note the
export no longer gets an arm-suffixed stem — a non-default config **overwrites**
`account_sim-positions-latest.csv`, and the report's `config` line is what
records which simulation produced it. Only `--structure-universe` still writes a
separate artifact.

---

## 2026-08-13 — `account_sim` SIZING ARM ($1,000/position, per-pos 0.40x, net 2.50x) RUN: operator-chosen, NOT measured — and it exposed a memoisation bug that G5 caught

**Status: NOTHING SHIPS. This is an arm, not a result.** The three sizing
constants were chosen by the operator (risk $500 → $1,000; net delta cap
1.50x → 2.50x; per-position cap 0.25x → 0.40x, raised because doubling the
budget doubles contracts and would otherwise have been eaten by the old
per-position cap). They were **not** selected on any measurement here, and no
figure below may be read as evidence for them. The anti-tuning rule on the cap
grid binds harder on an arm than on the pre-registered cell, not softer.

**Provenance.** `backtests/study_output/account_sim-arm-risk1000-latest.txt`
(+ positions export
`account_sim-positions-risk4pct-pp0.4-net2.5-latest.csv`, 447 rows), git
309c564 (dirty), same 08-11 exports and same frozen book as the pre-registered
run. The pre-registered report stays at `account_sim-latest.txt` and its
numbers are **unchanged** — verified by re-running the bare study after the
code change and diffing: 656 lines, the only differences are two cosmetic
GRANULARITY section titles.

**How the arm is expressed.** An `Arm` overlay (`account_sim.ARM`) carries the
run's four sizing values; `main()` rebinds it once from the command line and
every `Cfg` defaults to it. Left alone it equals the pre-registered baseline,
so a bare run reproduces the frozen study bit-for-bit; an arm run is
banner-flagged in the report, tagged in the CSV `arm` column, and written to
its own CSV stem — the `--structure-universe` precedent:

    python -m scripts.backtest_study run account_sim -- \
        --risk-dollars 1000 --per-pos-cap 0.40 --net-cap 2.50

> **SUPERSEDED later the same day** by the config-driven refactor at the top of
> this file. The `PREREG_*` literals, `Arm`, `Arm.is_preregistered`, `Arm.tag`,
> the arm banner, the arm-suffixed CSV stem and the four sizing flags described
> in the next two paragraphs no longer exist, and the four tests that pinned
> them are gone. The parameters now live in `config/account-sim.yml`; to
> reproduce this arm, copy it with `risk_per_trade_pct: 0.04`,
> `caps.per_position: 0.40`, `caps.net: 2.50` and pass `--config`. Everything
> else in this section — the numbers, the G5 bug and its fix — stands unchanged,
> and its two cited artifacts are still on disk.

**Amended same day — the sizing constants are now EDITABLE** (operator's call).
The module previously said it "may not change them after the run"; that
sentence is gone, along with `--capital` being missing. Simulating a different
account is a normal use of a research-tier study, so `STARTING_CAPITAL` /
`RISK_PER_TRADE_PCT` / `PER_POSITION_CAP` / `NET_CAP` may be edited in source
or moved per-run with `--capital` / `--risk-dollars` / `--per-pos-cap` /
`--net-cap`. What is preserved is the LABEL, not the values: the
pre-registered numbers are recorded separately as the `PREREG_*` literals, and
`Arm.is_preregistered` compares against **those**, so an edited constant
cannot silently produce a report that claims to be the pre-registered study —
it flags, tags and re-stems exactly like a flag would. `Arm.tag` names only
the knobs that moved (`cap50k`, `risk4pct-pp0.4-net2.5`). Four tests pin this.
The verdict grammar still says "NOT FEASIBLE AT $25k" verbatim, because
`scripts/study_charts/render.py` matches those strings exactly — on a
changed-capital run read it as the arm's label, not a claim about $25k.

**A REAL BUG, found by G5 and fixed.** The arm's first run FAILED G5
(outcome-blindness): sighted 132 positions vs blind 134, 13 differing.
`replay_sized`'s memo key was `(id(rec), contracts, stop)` — it did **not**
include the exit profile. G2 calls that function with an explicit `DEBIT_PROD`
profile (the one that generated the stored rows) at the stored contract count
and stop `MAX_LOSS_ABS` = $1,000. Any `simulate()` whose own stop is also
$1,000 then asks for the same key and gets **G2's calibration answer back
instead of the shipped `be_after`-0.50 merge**. Blinded records are distinct
objects, so they missed the poisoned entries — which is exactly why the two
books diverged and why the gate fired. Fixed: the profile is now part of the
key. The gate is doing more than its stated job; it caught a cache-collision
bug, not a lookahead.

Two stops reach $1,000: **a $25k book at 4%** (this arm) and **a $50k book at
2%** (the top rung of `CAPITAL_LADDER`). The pre-registered report is
unaffected — its stop is $500, keys never collided, and the capital ladder
only prints when A1 fails, which it did not. **No published pre-registered
figure ever stood on the bug.**

**What the arm printed (PRIMARY dense episodes, descriptive only).**

| | pre-registered ($500 / 0.25x / 1.50x) | arm ($1,000 / 0.40x / 2.50x) |
|---|---|---|
| positions taken | 51 | 63 |
| realized $ | $7,860 | $20,217 |
| meanR | +0.278 CI [+0.055,+0.483] | +0.428 CI [+0.249,+0.594] |
| maxDD | −$3,673 (14.7% of capital) | −$2,851 (11.4%) |
| attrition vs B2 (A2) | 99% | 135% |
| most binding constraint | net_delta (66 of 97) | net_delta (62 of 85) |
| per_pos_delta exclusions | 25 | 14 |
| A5 stability | NOT MET | NOT MET |
| A6 credit sensitivity | NOT MET | MET |
| verdict | A1 holds, A5+A6 fail | A1 holds, A5 fails |

**Reading, with the caveats that matter more than the numbers:**

1. **Net delta is STILL the binding constraint** (62 of 85 exclusions) even at
   2.50x. Raising the cap did not relieve it; it moved the frontier out and
   the book refilled against it. Peak sessions run 2.45–2.48x net — pinned to
   the new ceiling, the same way they were pinned to the old one. Cash never
   binds once (0 of 85, peak reserve 0.78x).
2. **The per-position cap change did what it was for.** per_pos_delta
   exclusions fall 25 → 14 despite contracts doubling, so 0.40x roughly
   absorbs the doubled budget rather than eating it.
3. **The adverse-ordering finding SURVIVES and its two halves separate.**
   net_delta-rejected picks still out-perform taken (+0.482 vs +0.428, delta
   +0.053 — narrower than the frozen cell but the same sign), while
   per_pos_delta-rejected picks now under-perform (+0.126, delta −0.302). The
   net cap is still adversely selecting; the per-position cap is not.
4. **A5 still fails, and by MORE.** Ex-2025_mar_apr moves +142pt (frozen:
   +111pt). The bigger book is *more* concentrated in that window, not less.
   The A5 failure is the reason feasibility is not confirmable, and the arm
   does not fix it — it worsens it.
5. **A6 flipping to MET is not a finding.** Debit-only n=46 meanR +0.386 CI
   [+0.172,+0.594] clears where the frozen cell's n=39 CI included zero. This
   is the same rows at different sizes with a wider net cap admitting more of
   them; treating a criterion flip produced by an operator-chosen knob as
   evidence is precisely what the anti-tuning rule forbids.
6. **Per-position risk is now materially larger.** Realized per-position risk
   is median 3.6%, p90 6.0%, **max 12.2%** of capital (frozen: 1.8 / 3.0 /
   6.1%). The 1-contract floor share is 28%, so on more than a quarter of
   picks the account cannot express the budget at all and takes a single
   contract whose max loss exceeds it — at $1,000 that floor breach is twice
   the dollars it was.

**Verdict grammar hole is unchanged.** "A1 holds but A5 fail(s)" still matches
no pre-registered label, same as the frozen run. Not relabelled.

**Carry-forward.** The memo-key fix is a correctness fix to research
infrastructure and applies to every future `account_sim` run at a $1,000 stop
— including the $50k rung of the capital ladder, which would have been
silently contaminated the first time A1 failed and the ladder printed.

---

## 2026-08-13 — `calendar_hedge --arm S` RUN: the structure sweep is uniformly POWER-STOPPED — zero candidates, and that is a power fact, not evidence against any structure

**Provenance.** `backtests/study_output/calendar_hedge-latest.txt` (ARM S run;
the H arm stays preserved at `calendar_hedge-20260813-130412.txt`), git 470b95f
(dirty), 08-11 exports, grown option cache (**19,382 contracts** after the
sweep-leg scrape: 1,418 of 1,452 manifest targets fetched;
`scripts/collector/fetch_sweep_legs.py`, resumable, manifest in
`backtests/sweep_cache/legs_manifest.csv`). Nothing ships. The two-analyst
replication was NOT run on this report (uniform power stops leave nothing to
grade); it can be requested.

**DEVIATION (labelled, post-first-run module amendment).** R4 is re-keyed to
the **pre-scrape cache snapshot**: the sweep manifest's fetched contracts are
withheld from leg SELECTION (pricing unfiltered — legs picked from the
filtered grid point at byte-unchanged files), because vol_sleeve's "nearest
cached strike / next cached expiry" definitions re-pick legs on a grown cache.
Under the snapshot, **R4 reproduces the vol_sleeve cell EXACTLY again (183 /
+0.158 / $28,059 / 124-28-22-5-4)** — confirming the earlier post-scrape R4
failure was 100% cache movement, zero re-implementation drift. The snapshot
cell is stored under its own label (`calendar@snapshot`) so it can never mix
with grown-cache rows. Second small fix: the ARM S precondition now scans all
stamped reports for an H2 verdict (the runner's `-latest.txt` overwrite had
erased the marker).

**Coverage on the grown cache.** put_calendar 109 built (52/90 deployed dates),
put_diagonal 58 (36/90), narrower 246 (80/90), wider 200 (74/90), long_put 326
(84/90). **S6 iron_condor: four-leg coverage 314/786 = 39.9%** vs the
pre-registered 60% gate (plan-time cache-only was 27.2%; the scrape halved the
gap, didn't close it) → **NOT EVALUABLE**, excluded from the sweep and from
the multiplicity count.

**Controls (the plumbing check).** baseline −0.093 vs published −0.093
(REPRODUCES), long_put +0.002 vs +0.002 (REPRODUCES, touches no grid), wider
−0.055 vs −0.056 (+0.001, expected — it re-selects the lowest cached put and
895 puts were added; grid-selecting structures move with the cache by
construction). S3/S4/S5 run through bear_rewrap's own path (base-row grid +
`prod_profile_for`), with a hard guard against sending rec-based structures
down the synth path.

**Sweep: 5 structures × 6 pick rules = 30 cells, Bonferroni α = 0.05/30.**
**Zero CANDIDATEs — all 30 cells POWER-STOPPED** (worst-decile tail n = 0–6
against the ≥10 threshold; a 1/day rule over 9 worst-decile dates cannot fill
a readable cell, the same arithmetic that stopped the H arm's H2). Standalone
means printed for context only (narrower +0.24..+0.42, put_calendar
+0.09..+0.39, long_put ≈0, put_diagonal mixed) — ungated, quote nothing from
them. One structural finding: **P5 (same ticker as the day's top deployed
pick) fills 0% on every bear_rewrap structure** — verified real: across all 90
deployed dates the top-ranked pick's ticker never also carries a bear debit
row. P5 is inapplicable to bear substitutions in this book.

**Decision (main session).** The bear-structure sweep is CLOSED for this
window with the same conclusion as the H arm: **every hedge-shaped question on
this book now terminates at the same wall — 9 worst-decile dates cannot power
a worst-decile criterion under a 1/day sleeve.** No structure is promoted, none
is killed. The only path forward for the entire hedge programme (calendar,
put calendar, diagonal, narrower — all of it) is NEW DATES. Iron condor
becomes evaluable only if a future scrape lifts four-leg coverage ≥60%. Do not
re-run this sweep on the same 118 dates with different knobs.

---

## 2026-08-13 — `calendar_hedge` RUN: gates all pass (R4 exact), but the hedge claim cannot be read — power stop fires at n=6 and the readable correlation is wrong-signed

**Provenance.** `backtests/study_output/calendar_hedge-20260813-130412.txt`
(the stamped R4-PASS run — `-latest.txt` was later overwritten by a
post-scrape gate run that fails R4 by construction; see the R4 note below),
git 470b95f (dirty), the 08-11 exports, `load_book(include_bs=False)` → 795
rows. Checkpoint store `backtests/sweep_cache/synth_results.csv` (967 rows,
resumable, `--redo` verified). Nothing ships; the pre-registered ship ceiling
is NOT reachable on this window.

**Gates.** R1 quoted (289/301 exact, 277 credit ungated). R2 **786/786**. R3
deployed line exact (220 / 90 / $63,553). **R4 EXACT on every field** — 183
rows, meanR +0.158, $28,059, exit mix 124/28/22/5/4, and the unpriceable census
reproduced — so the H-arm numbers are attributable to the pick rule and fill
discipline, not re-implementation drift. NOTE: R4 is now **frozen to the
pre-scrape cache**: the 08-13 sweep-leg scrape grows the option cache, and
vol_sleeve's "nearest cached strike / next cached expiry" definitions re-pick
legs on a grown cache (observed live: AAPL cell moved first). The delivered
report is the R4-PASS run; the module prints a cache fingerprint and an
R4-failure attribution block so future drift is diagnosable in one line.

**H arm (strict fill, P1 nearest-ATM, ½ size, 1/day).** Universe: 143 loose →
132 strict candidates over 68 dates / 26 tickers (2 excluded entry_net ≤ 0).
- **H0 FILL MET:** 68/90 deployed dates (75.6%), 6/9 worst-decile (66.7%).
- **H1 (context):** n=68, meanR +0.228 CI [−0.016, +0.590], win 62%, **all 3
  years positive** (+0.062/+0.369/+0.220); $13.3k at ½ size; meanE +0.034.
- **H2 (primary) NOT EVALUABLE.** (a) corr(daily $) **+0.075** CI [−0.095,
  +0.187] — needs < 0, NOT MET; (b) worst-decile cell **n=6 → POWER STOP fired,
  CI not read** (the pre-registration's expected outcome); (c) 2/3 years MET.
  Substantively: the one readable component is **wrong-signed** — the same
  direction vol_sleeve found for straddles (synthesizing on the engine's own
  dates re-wraps the same exposure), weaker but not the hedge sign.
- **H0b:** headline strengthens under the freshness cut (+0.274, CI [+0.016,
  +0.642], n=66) — not a stale-mark artifact. (Report defect: no explicit
  MET/NOT MET line printed; graded NOT EVALUABLE by both analysts since the
  headline it must preserve is itself unreadable.)
- **H3 NOT MET on both baselines** — but read the mechanism: maxDD improves
  monotonically at every f (ladder alone −7,609 → −5,561 at f=1.0; ladder+bear
  −6,606 → −5,187) and totals +$13.3k; the block is the worst-single-date
  criterion failing by **$17–67 per f step** (−3,212 → −3,229 at f=0.25). The
  pre-registered rule did exactly what it was written to do; the margin is
  noise-sized and is recorded as such, not argued away.
- **H4:** P1 never separates from the day's mean fillable calendar (dR −0.029,
  CI spans zero) nor from any of P2–P6 — the simplest rule stands by default.
- **H5 (post-hoc, candidate-only):** `model RANGE + C/L-VOL` n=15, diff +0.966
  CI [+0.111, +2.422] — the only cell excluding zero; **vol_sleeve's
  earnings-inside-DTE conditional does NOT reproduce** under the strict-fill
  1/day sleeve (n=14, CI spans zero).
- **Exit sensitivity (labelled):** hold-to-near-expiry flips standalone to
  −0.193 and flips (a) to MET / (c) to NOT — the verdict is exit-shape-sensitive
  in components but H2 stays NOT EVALUABLE either way. H3/H4/H5 were not rerun
  under HOLD (deviation, recorded).

**Decision (main session).** The calendar-hedge CANDIDATE is **not promoted and
not killed**: H2 was pre-registered as the primary gate, the power stop fired
exactly as written, and the honest conclusion is the one the pre-registration
pre-committed to — **needs new dates** (worst-decile n ≥ 10). Until then the
worst-decile +0.336 from vol_sleeve should not be quoted as a hedge property;
under the strict fill rule it is n=6 / +0.163 / unreadable. The RANGE+C/L-VOL
cell is the only carry-forward, as a next-window candidate with its own
pre-registration. ARM S (structure sweep) runs separately on the grown cache.

**Report defects found by replication (for the next runner):**
1. The `$ (1/2 size)` headline vs the `fmt_row` detail line mix half-size
   (`H_dol`) and FULL-SIZE (`R_dol`) dollars without labels — verified in source
   (`calendar_hedge.py:262,274`): a labelling defect, not a numeric error
   (signed sums explain the odd ratios 1.52×/4.76×).
2. H5's `vs rest` column prints the REST group's mean, not the difference
   (validator-resolved mechanically); header mislabelled.
3. Hedge sizing floors at `max(1, int(0.5×contracts))` — full size whenever the
   risk size is 1 contract; same unlabelled "≤½ size" deviation as account_sim's
   ARM H. Fix both together if the sleeve is ever re-run.

### Disagreement log
- H5 column characterization: A read it as an internally inconsistent diff
  column, B as a mislabelled rest-mean column — **resolved in B's favor** by
  validator arithmetic (all four rows consistent with rest-mean).
- H0b emphasis: A flagged out-of-order printing, B flagged absence from the
  VERDICT block — complementary, both true, no verdict conflict.
- H2(a)-vs-power-stop tension (B-only): (a) fails on its own, so a literal
  "all three" reading could argue NOT MET; the power-stop clause is written
  unconditionally, so NOT EVALUABLE stands. Main-session note: on the NEXT
  window, if (a) fails again with (b) readable, H2 is NOT MET — the clause
  should be amended to say the stop only suspends (b), not (a)/(c).
- Protocol violations (validator): Analyst B added an out-of-schema synthesis
  paragraph and silently reordered the gates — both recorded; verdicts
  unaffected. First real run of the protocol otherwise clean.

---

## 2026-08-13 — `account_sim` RUN: the $25k edge survives its caps but not its window; the verdict grammar had a hole

**Provenance.** `backtests/study_output/account_sim-latest.txt`, git 470b95f (dirty),
the 08-11 exports (BacktestResults 1,926 / BacktestProxy 4,533 / AnalysisClaude
11,836 rows), `load_book(include_bs=False)` → 795 rows; mech table 803 rows
2026-08-13 (book.py boilerplate — not used by any printed account_sim output;
validator-checked). Nothing ships from this study by pre-registration.

**Gates: all four PASS.** G1 debit_calib 289/301 exact (12 hard, excluded),
n_credit_ungated 277; **B1 reproduces the vol_sleeve deployed line exactly (220 /
90 / $63,553)**. G2: 175/175 calibrated debit picks replay exactly through the
scaling-identity code path at scale=1 (42 credit picks counted, ungated). G3: 248
ledger events, 0 violations. G4: pick-set symmetric difference 0. Failure paths
demonstrated via `--selftest-gates` (all four gates flip to FAIL, exit 1).

**Headline — PRIMARY dense episodes (3 episodes, 46 dates, 112 picks), (R, F1)
cell at caps (0.25, 1.50).** 51 positions / 28 dates / **$7,860, meanR +0.278 CI
[+0.055, +0.483]**, maxDD −$3,673 (14.7%). B1 $45,671 → B2 (at $25k sizing)
$23,157 — **granularity alone halves the paper book** — → constrained $7,860 =
99% of B2 on the same dates.

**What the ledger actually says (the operative findings):**
- **The binding constraint is delta exposure, not cash.** 66 of 97 exclusions hit
  the net delta-notional cap, 25 the per-position cap, 6 the day-3 cap; **cash
  binds zero times**. The capital number is almost irrelevant at these caps.
- **The cap ordering is adverse:** rejected picks would have returned meanR
  +0.431 vs +0.278 taken — the ladder-rank walk consumes exposure on
  earlier-ranked picks that underperform the ones the cap then excludes.
- **Min-1 granularity dominates:** 133/218 picks (61%) both floor at one contract
  AND breach the $500 risk budget (worst 13.3% of equity). F1 vs F2 flips sign by
  population (dense: refusing costs $4.2k; sparse full book: refusing GAINS
  $4.2k) — no rule is readable from this window.
- **ARM H (shipped bear sleeve) works as exposure headroom, not P&L:** the sleeve
  itself loses $832 but reduces |net|, admitting 25 more signal positions
  ($7,860 → $10,615).

**Verdict (pre-registered grammar): NO LABEL MATCHES.** A1 MET, A2 MET (99%), A3
MET (14.7%), A4 MET (partition exact), **A5 NOT MET** (ex-2025-Mar/Apr ratio
210%, +111pt swing), **A6 NOT MET** (debit-only CI [−0.093, +0.440] spans zero,
n=39). FEASIBLE required A5∧A6; NOT FEASIBLE required A1 failing; the run landed
in the gap and the report says so rather than relabelling. **Recorded outcome:
feasibility NOT CONFIRMABLE on this window** — the surviving edge is
window-concentrated and credit-carried at this account size. The capital ladder
correctly did not print (A1 held). SECONDARY full book is weaker everywhere
(124 positions, $5,021, CI spans zero) and carries nothing per pre-registration.

**Replication protocol (Mode 1, DRY RUN — first use).** Two `research-analyst`
agents graded the report independently; `research-validator` source-checked
every quoted number. **All verdict rows agree; zero numeric mismatches; no
methodology violations.** Reconciled deviations (all real, none verdict-moving):
the A4 census adds two unregistered buckets (`taken_downsized`, `unsizable`);
G1–G4 print full-book counts rather than per-population; the "floor share"
label differs from the plan-time disclosure (same data); A5's window cuts were
not named in the pre-registration (report used the two standard cuts); A2's
denominator reads "same dates" as the 28 taken dates, not the 46 dense dates
(a ×3 difference — literal wording supports the report); **ARM H's `int(0.5×c)
floor 1` sizing exceeds "≤½ size" whenever risk size is 1 contract (unlabelled
deviation, B-only catch)**; G2 calibrates against DEBIT_PROD not the shipped
merge (labelled, correct — identity test, not exit test).

### Disagreement log
No disagreements: every criterion row adjudicated `agree`. Single-analyst
catches (A: A2 denominator; B: ARM H sizing floor, mech-table input) were
confirmed real by the validator, not contested.

**Follow-ups recorded (not shipped, not promises):** (1) the verdict grammar
must cover A1-holds/A5-or-A6-fails before any re-run; (2) if a $25k deployment
is ever considered, the delta-cap ordering question (rank-walk vs
exposure-efficient selection) is the pre-registerable item — the adverse
ordering read is post-hoc here; (3) ARM H sizing floor should be `max(1, …)`
only when ½-size ≥ 1 contract, else skip, if the sleeve is ever re-run.

### 2026-08-13 addendum — lookahead audit, G5 blindness gate, and the structure universe

Prompted by the operator question "does the sim see the backtest result before
picking a tier?", asked because the next step is an agent proposing positions
against the live portfolio. **Verdict: no per-row lookahead** — `ladder_eligible`
reads `tier`; `ladder_tier` reads `structure` + `market_regime` + `delta` +
`dte`; `ladder_rank` adds a `score_total` tie-break; sizing reads
`max_loss_per_contract`; exposure reads `delta` × `entry_underlying`; the exit
profile keys off `structure`/`credit`/`mech_cell` (as-of-date). No outcome field
is read before a pick. Three lookaheads DO exist above the row level and are
recorded, not fixed: **(a)** the ladder and exit profile are in-sample (fitted on
this book), **(b)** within-day ties resolve by file order for pre-13c rows, and
**(c)** the candidate universe was outcome-filtered — addressed below.

**G5 — outcome blindness, now GATED.** Auditing the path by eye is not a
guarantee for a downstream agent, so blindness is enforced in two layers:
`BlindRec` raises `LookaheadError` on any read of `R`/`E`/`R_dol`/`E_dol`/
`mfe`/`mae`/`mfe_day`/`mae_day`/`exit_reason`/`days_held`, AND the equivalent
columns are DELETED from the underlying `Trade` row so a read cannot route
around the wrapper via `rec["t"].row`. G5 requires the resulting book to be
**identical** to the sighted run: 124/124 positions, 0 differing. `Trade`
construction touches only entry-side fields and the price path, so stripped rows
still price. `--selftest-gates` flips all five gates to FAIL.

**Structure universe (`--structure-universe`), NOT the default.** The frozen
book withholds 19 `strike_expiry_tweak` debit rows that fail book.py's
exact-replay gate. The gate's stated rationale — "priced or dated in a way the
harness can't reconstruct" — is **wrong for these rows**: all 19 carry a stored
`exit_reason` of `trailing_stop`, a rule removed from `DEBIT_PROD` by Attempt 10
(2026-07-04). They are stale-exit-config exports whose price paths replay fine.
Since this study never reads a stored outcome (G5 proves it), admitting them is
sound *here and only here* — `load_book(require_proxy_calibration=False)` keeps
`calibrated=False` on them, so `calibrated`-keyed logic (G2) still skips them,
and it does **not** re-admit `bs_options_hist` rows (orthogonal filters, tested).

Effect: candidate universe 795 → 814 (+19, all 2026, tier A=3 / C=14 / VETO=2);
deployed book 220 → 223 picks over 90 → 91 dates, 3 gained (NVDA 03-11, GOOGL
03-23, NVDA 04-02, all `bull_call_spread`), **0 displaced**. PRIMARY moves
$7,860 → $8,357, meanR +0.278 → +0.280. **Verdict is UNCHANGED** (A1 MET, A5/A6
NOT MET, same gap in the grammar) — the arm does not rescue feasibility and
nothing is adopted from it. Gates always run on the FROZEN book so G1's B1
reproduction and G4's selection identity cannot move because an arm widened the
universe; the arm writes a separate artifact
(`account_sim-positions-structure-latest.csv`, arm `RF1-structure`) so a
consumer can never confuse the two books.

**Positions CSV** now also carries the regime block —
`market_regime`/`model_dir`/`model_vol` (what the tier keys off) kept SEPARATE
from the per-play `regime` (per the repo invariant), plus
`mech_direction`/`mech_vol`/`mech_cell`. Tier is now reproducible from the CSV
alone. Export remains a debugging artifact: not pre-registered, adopts nothing.

**Same-day addendum 2 — a `DEPLOYED BOOK BY REGIME` section was added to the
report, and it is NOT a deviation from the pre-registration.** It adds no
decision, changes no printed number and touches neither selection, sizing nor
exits — it re-groups the book the walk already produced, so the gates and the
A1–A6 verdict are bit-for-bit what they were. It is labelled post-hoc in the
report itself, cells under 10 positions are marked `thin`, and it exists because
the obvious next question about a deployed book ("which structures, in which
regimes") was being answered by hand-crosstabbing the positions export, which
is how a number nobody re-derives becomes a quoted finding. Anyone grading this
report should read that section as a description, not a result.

Worth recording from it, as description only: on PRIMARY the model's direction
and the mechanical one **agree on 14 of 51 deployed positions** — the model
reads RANGE on 34 positions the SPY/VIX label calls BEAR. The two are read off
different things so this is not an error rate, but it does mean the tier (keyed
on the model read) and the exit profile (keyed on the mechanical cell) are
routinely disagreeing about the same position. Not a finding, and no cut here
was pre-registered; flagged as a candidate question for a study that would be.

---

## 2026-08-13 — `account_sim`: PRE-REGISTRATION → [`pre-registrations/account_sim.md`](../pre-registrations/account_sim.md)

Moved out of this log: a pre-registration is an immutable artifact and this
file is pruned into `archive/`. The section is unchanged, just relocated.

---

## 2026-08-13 — `calendar_hedge`: PRE-REGISTRATION → [`pre-registrations/calendar_hedge.md`](../pre-registrations/calendar_hedge.md)

Moved out of this log: a pre-registration is an immutable artifact and this
file is pruned into `archive/`. The section is unchanged, just relocated.

---

