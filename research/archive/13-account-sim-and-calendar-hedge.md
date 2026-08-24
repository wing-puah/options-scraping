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

**Provenance.** Run 2026-08-13 18:41:39, git 309c564 (dirty), same 08-11 v3
exports (1,926 / 4,533 / 11,836) and same frozen book as the pre-registered run;
positions export 447 rows. The pre-registered run's numbers are **unchanged** —
verified by re-running the bare study after the code change and diffing: 656
lines, the only differences are two cosmetic GRANULARITY section titles. Report
and positions CSV not retained on disk — the excerpt at the end of this section
IS the record.

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


<details>
<summary>Report excerpt, verbatim — run 2026-08-13 18:41:39, git 309c564 (dirty); header, G1-G5, both populations' baselines + criteria, verdict</summary>

```text
==============================================================================
STUDY: account_sim
==============================================================================
  run at    2026-08-13 18:41:39
  command   python -m scripts.backtest_study.account_sim --risk-dollars 1000 --per-pos-cap 0.40 --net-cap 2.50
  git       309c564 (main, working tree dirty)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
   4,533 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestProxy.csv
  11,836 rows  2026-08-11 17:24  backtests/to_evaluate/analysis - AnalysisClaude.csv
     803 rows  2026-08-13 11:56  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================

==============================================================================

[... lines 16-42 elided ...]

GATES — G1..G5 (non-zero exit on any failure)
==============================================================================

--- G1 — book calibration quoted, B1 line reproduced ------------------------
  debit_calib      n=301  exact=289  near=0  hard=12
  n_credit_ungated 277  (admitted WITHOUT the exact-replay gate — book.py's credit caveat)
  B1 (stored contracts, stored R): 220 positions / 90 dates / $63,553
  expected (vol_sleeve 2026-08-12, same exports): 220 / 90 / $63,553
  G1: PASS

--- G2 — scaling identity calibrated at scale=1 against the stored rows -----
  The identity code path is run with factor 1 (stop = the harness's own
  $1,000) at the STORED contract count, under DEBIT_PROD — the profile that
  GENERATED the stored rows. It must reproduce (exit_reason, days_held,
  round(R,4)) exactly. Calibrating against the shipped be_after-0.50 merge
  instead would be testing an exit change, not the identity.
  calibrated debit picks re-replayed: 175  exact=175  mismatched=0
  credit picks (counted, NOT gated — book.py admits them ungated): 42
  debit picks failing book.py's own calibration (excluded from G2): 3
  G2: PASS

--- G3 — ledger accounting identity, checked after every event --------------
  events checked: 268   positions: 134
  final cash $42,865.50  reserved $0.00  realized $17,865.50  (capital $25,000.00)
  G3: PASS  (0 violations)

--- G4 — unconstrained walk reproduces top_k_per_day by set equality --------
  walk picks 220 (incl. 2 unsizable slot-burners)  vs top_k_per_day 220
  symmetric difference: 0
  G4: PASS

--- G5 — the simulator is BLIND to how a position turned out ----------------
  Every record is re-wrapped so that reading an outcome key raises, AND the
  outcome columns are DELETED from the underlying trade row so a read cannot
  route around the wrapper. The run must then complete and produce a
  byte-identical book. This is what makes the sim safe to hand to an agent
  proposing live positions: no ordering, sizing or admission decision can be
  standing on a number that would not exist yet in real time.
  tripwire live (reading a blinded outcome key raises): True
  row columns deleted from every Trade: days_held, exit_reason, mae_day, mae_pct, mfe_day, mfe_pct, pnl_at_cap_pct, realized_pnl_pct
  positions: sighted 134  blind 134  differing 0
  G5: PASS

  GATES: ALL PASS

==============================================================================

[... lines 89-105 elided ...]

[PRIMARY dense episodes] B1 / B2 BASELINES
==============================================================================
  B1  stored contracts, stored outcomes     n= 112  dates= 46  $    45,671  meanR +0.511
  B2  $25,000 max-loss sizing, unconstrained  n= 110  dates= 46  $    37,614  meanR +0.392

  B1 -> B2 isolates GRANULARITY (contract counts), B2 -> constrained isolates the CAPS.
  B2/B1 dollar ratio 0.82x — the small account holds fewer contracts, so the dollar book shrinks by SIZE before any
  constraint is applied. B1's stored counts are a $50k book's.

==============================================================================

[... lines 116-357 elided ...]

[PRIMARY dense episodes] CRITERIA A1-A6
==============================================================================
  A1 EDGE SURVIVAL  meanR +0.428  CI95 [+0.249,+0.594]  years 2025:+0.590  2026:+0.239
     MET  (needs mean>0, CI excluding zero, every year positive)
  A2 ATTRITION      constrained $20,217 vs B2 on the same 33 dates $15,017  = 135%
     MET  (needs >= 60%)
  A3 NO BLOWUP      maxDD $-2,851 = 11.4% of capital;  ledger violations 0
     MET  (needs no over-reservation and DD <= 25%)
  A4 ATTRIBUTION    150 candidates partition exactly into 63 taken + exclusions
     MET  (mismatch FAILS the run)
  A5 STABILITY      constrained/B2 ratio ALL 135% (n=63);  ex-2025_mar_apr 277% (+142pt, n=37)  ex-2026_feb_apr 120% (-15pt, n=34)
     NOT MET  (needs <= 15 points of movement on both cuts)
  A6 CREDIT SENS.   debit-only n=46  meanR +0.386  CI95 [+0.172,+0.594]  years 2025:+0.544  2026:+0.161
     MET  (A1 must hold on debit-only)

==============================================================================

[... lines 374-373 elided ...]

[SECONDARY full book] B1 / B2 BASELINES
==============================================================================
  B1  stored contracts, stored outcomes     n= 220  dates= 90  $    63,553  meanR +0.354
  B2  $25,000 max-loss sizing, unconstrained  n= 218  dates= 90  $    52,000  meanR +0.303

  B1 -> B2 isolates GRANULARITY (contract counts), B2 -> constrained isolates the CAPS.
  B2/B1 dollar ratio 0.82x — the small account holds fewer contracts, so the dollar book shrinks by SIZE before any
  constraint is applied. B1's stored counts are a $50k book's.

==============================================================================

[... lines 384-647 elided ...]

[SECONDARY full book] CRITERIA A1-A6
==============================================================================
  A1 EDGE SURVIVAL  meanR +0.264  CI95 [+0.115,+0.419]  years 2024:+0.178  2025:+0.352  2026:+0.220
     MET  (needs mean>0, CI excluding zero, every year positive)
  A2 ATTRITION      constrained $17,866 vs B2 on the same 68 dates $29,429  = 61%
     MET  (needs >= 60%)
  A3 NO BLOWUP      maxDD $-4,628 = 18.5% of capital;  ledger violations 0
     MET  (needs no over-reservation and DD <= 25%)
  A4 ATTRIBUTION    297 candidates partition exactly into 134 taken + exclusions
     MET  (mismatch FAILS the run)
  A5 STABILITY      constrained/B2 ratio ALL 61% (n=134);  ex-2025_mar_apr 50% (-10pt, n=110)  ex-2026_feb_apr 49% (-11pt, n=106)
     MET  (needs <= 15 points of movement on both cuts)
  A6 CREDIT SENS.   debit-only n=102  meanR +0.135  CI95 [-0.041,+0.325]  years 2024:-0.003  2025:+0.236  2026:+0.161
     NOT MET  (A1 must hold on debit-only)

==============================================================================
VERDICT (PRIMARY dense episodes population — the pre-registered primary)
==============================================================================
  A1  MET
  A2  MET
  A3  MET
  A4  MET
  A5  NOT MET
  A6  MET

  >>> NO PRE-REGISTERED VERDICT MATCHES — A1 holds but A5 fail(s) <<<

  The three pre-registered verdicts (FEASIBLE = A1^A2^A3^A5^A6;
  FEASIBLE-BUT-DEGRADED = A1^A3 with A2 failing; NOT FEASIBLE AT $25k = A1
  fails) do not partition the outcome space, and the run landed in the gap.
  Nothing is relabelled to fit: the checklist above is the result, and the
  verdict grammar is recorded as incomplete for whoever replicates this.

==============================================================================
CLOSE
==============================================================================
  verdict: NO PRE-REGISTERED VERDICT MATCHES — A1 holds but A5 fail(s)
  Nothing in this report is a shippable rule. The cap values are a friction model,
  not a tuned parameter; the pre-registration forbids adopting any of them on P&L.
  positions CSV: 447 rows -> backtests/study_output/account_sim-positions-risk4pct-pp0.4-net2.5-latest.csv

==============================================================================
exit code 0 after 3.4s
==============================================================================
```

</details>
---

## 2026-08-13 — `calendar_hedge --arm S` RUN: the structure sweep is uniformly POWER-STOPPED — zero candidates, and that is a power fact, not evidence against any structure

**Provenance.** ARM S run 2026-08-13, git 470b95f
(dirty), 08-11 exports, grown option cache (**19,382 contracts** after the
sweep-leg scrape: 1,418 of 1,452 manifest targets fetched;
`scripts/collector/fetch_sweep_legs.py`, resumable, manifest in
`backtests/sweep_cache/legs_manifest.csv`). Nothing ships. The two-analyst
replication was NOT run on this report (uniform power stops leave nothing to
grade); it can be requested.

**Report not retained on disk — the prose in this section is the record.** The
`calendar_hedge-latest.txt` that carried this ARM S run was overwritten on
2026-08-14 12:54 by a plain H-arm re-run (`python -m
scripts.backtest_study.calendar_hedge`, git 9c53244), which prints no ARM S
sweep at all. That file is still on disk, but only because it carries the
`"H2 (primary)"` marker that arms the ARM S precondition in
`f3_structure/calendar_hedge.py` — it is a gate token, not this section's
evidence, and none of the coverage or sweep figures below can be checked
against it.

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

**Provenance.** Run 2026-08-13 13:04:12, git 470b95f (dirty), the 08-11 v3
exports (1,926 / 4,533 / 11,836), `load_book(include_bs=False)` → 795
rows. This was the stamped R4-PASS run; the `-latest.txt` beside it was later
overwritten by a post-scrape gate run that fails R4 by construction (see the R4
note below). **The report is not retained on disk and CANNOT be regenerated** —
R4 keys to the pre-scrape option cache, which the 08-13 sweep-leg scrape grew
past recovery. The full report is folded verbatim at the end of this section and
is now the only copy. Checkpoint store `backtests/sweep_cache/synth_results.csv` (967 rows,
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


<details>
<summary>Full report, verbatim — run 2026-08-13 13:04:12, git 470b95f (this run is NOT reproducible: R4 keys to the pre-scrape option cache)</summary>

```text
==============================================================================
STUDY: calendar_hedge
==============================================================================
  run at    2026-08-13 13:04:12
  command   python -m scripts.backtest_study.calendar_hedge
  git       470b95f (main, working tree dirty)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
   4,533 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestProxy.csv
  11,836 rows  2026-08-11 17:24  backtests/to_evaluate/analysis - AnalysisClaude.csv
     803 rows  2026-08-13 11:56  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================

==============================================================================
PROVENANCE — inputs, store, and the frozen pieces this rests on
==============================================================================
  checkpoint store   backtests/sweep_cache/synth_results.csv — 969 rows, mtime 2026-08-13 13:03:00
  exit profiles      DEBIT_PROD=606f5246 {'pt': 0.9, 'sl': 0.75, 'trig': None, 'trail': None, 'tef': 0.75}   HOLD=be626961 {'pt': None, 'sl': None, 'trig': None, 'trail': None, 'tef': None}
  pre-registration   config/backtest-tuning/current.md §2026-08-13 calendar_hedge
  P6 ETF list (30): SPY QQQ IWM DIA XLE XLF XLK XLI XLV XLY XLP XLU XLB XLRE XBI SMH GLD SLV USO TLT HYG EEM EFA FXI KWEB ARKK VXX UVXY SQQQ TQQQ

==============================================================================
R1 — book calibration, quoted before anything is built on it
==============================================================================
  pooled book (real+tweak, bs excluded)      795 rows over 118 dates  2024-06-17 .. 2026-04-07
  by source: real=406  tweak=389
  debit_calib      n=301  exact=289  near-rounding-tie=0  hard=12
  n_credit_ungated 277   (admitted WITHOUT the exact-replay gate — see book.py docstring)
  proxy debit rows excluded (non-exact) 48

==============================================================================
R2 — reconstruction gate on every source row feeding the universe
==============================================================================
  A (date, ticker) is used only if THIS code, re-pricing the ORIGINAL
  book row from the same cache, reproduces its stored entry and marks.

  reconstructs: 786 / 786  (100.0%)
  signal ticker-dates usable: 786   (vol_sleeve 2026-08-12: 786 / 786)
  R2 PASS

==============================================================================
R3 — the deployed ladder line reproduces the 08-12 vol_sleeve print
==============================================================================
  deployed: 220 positions over 90 dates, $63,553   meanR +0.354  win 65%
  expected: 220 positions over 90 dates, $63,553
  R3 PASS

==============================================================================
SYNTHESIS — building every candidate the universe can carry
==============================================================================
  Results are checkpointed to the store keyed (structure, ticker, date,
  expiry, profile_hash); an interrupted run resumes.
  candidate groups walked 786  (cached 786)

==============================================================================
R4 — vol_sleeve's calendar cell, rebuilt EXACTLY (the critical gate)
==============================================================================
  Pick rule DISABLED, LOOSE fill (entry lag <= U.MAX_ENTRY_LAG_DAYS = 5),
  full size, DEBIT_PROD. If this does not reproduce, the gap between
  vol_sleeve's +0.336 and whatever H2 prints cannot be attributed to
  the pick rule rather than to re-implementation drift.

  metric                 expected            got   verdict
  rows                        183            183   OK
  meanR (3dp)              +0.158         +0.158   OK
  $R                       28,059         28,059   OK
  exit mix        
    cap_open             expected    5   got    5   OK
    dollar_stop          expected   22   got   22   OK
    profit_target        expected   28   got   28   OK
    stop_loss            expected    4   got    4   OK
    time_exit            expected  124   got  124   OK

  R4 PASS — the rebuild is faithful

==============================================================================
H ARM UNIVERSE — deployed dates only, STRICT fill
==============================================================================
  FILLABLE means both legs cached on the ladder's OWN entry session
  (entry_date == grid[0]) — you cannot decide to hedge on Monday and be
  filled on Friday. The loose <= 5-day rule vol_sleeve used prints below
  as the pre-registered sensitivity.

  deployed dates                            90
  worst-decile deployed dates                9  (by deployed daily dollars; deployed $-20,268)
  loose-priced calendars on those dates    143
  ... STRICT-fillable (entry on grid[0])   134
  ... excluded, entry_net <= 0               2
  ... excluded, far_exp <= near_exp          0
  candidate calendars retained             132  over 68 dates, 26 tickers

--- entry-lag distribution under the LOOSE rule (sensitivity, not the universe) 
  STRICT is not a single lag bucket: grid[0] is the first WEEKDAY after
  the signal, so a Mon-Thu signal fills strict at lag 1 and a Friday
  signal fills strict at lag 3. The split is printed per bucket.

     lag   rows   share   of which STRICT
     1d    122   85.3%               122
     2d      3    2.1%                 0
     3d     15   10.5%                12
     4d      2    1.4%                 0
     5d      1    0.7%                 0
  strict share of loose-priced rows: 134/143 = 93.7%

==============================================================================
H0 — FILL gate: is the hedge available when it is needed?
==============================================================================
  A hedge unavailable exactly when needed is not a hedge. The gate is
  >= 60% of deployed dates AND >= 60% of the deployed book's worst
  decile; it fails on either. Unfillable days are carried at 0 in every
  portfolio line below, never dropped from a denominator.

  P1 fillable on deployed dates          68 / 90   =  75.6%   PASS
  P1 fillable on worst-decile dates       6 / 9    =  66.7%   PASS
  (any strict-fillable calendar exists on 68 / 90 deployed dates — P1 always picks when one does)

  H0 MET

==============================================================================
H1 — STANDALONE expectancy of the P1 sleeve (CONTEXT, not a gate)
==============================================================================
  A hedge is allowed to lose money standalone; the shipped bear sleeve
  does. This is here so the write-up can say what it costs.

  n=68 positions over 68 dates
  meanR +0.228  CI [-0.016, +0.590]   win 62%   $ (1/2 size) +13,252
  meanE +0.034  CI [-0.160, +0.218]
  years R: 2024 +0.062  2025 +0.369  2026 +0.220   (3/3 positive)
  years E: 2024 +0.159  2025 -0.243  2026 +0.370   (2/3 positive)
  exits: time_exit=49  profit_target=10  dollar_stop=8  cap_open=1
  P1                             n=  68  win   62%  PF  2.35  meanR +0.228  $    20,131  MFE  +0.99  MAE  -0.63  gb  0.64  cap  +0.23

==============================================================================
H2 — HEDGE CONTRIBUTION (P1) — THE PRIMARY GATE
==============================================================================
  D2's rule verbatim: (a) date-level correlation < 0, (b) mean sleeve R
  on the deployed book's worst-decile dates > 0 with a date-clustered CI
  excluding zero, (c) worst-quartile tail positive in >= 2 evaluable
  years. All three. POWER STOP: fewer than 10 positions in the
  worst-decile cell and (b) is NOT EVALUABLE — not 'failed'.

--- (a) date-level correlation with the deployed book -----------------------
  corr(daily $)       +0.075  CI95 [-0.095, +0.187]   over 90 deployed dates (unfillable carried at 0)
  corr(daily mean R)  +0.065  CI95 [-0.106, +0.272]   (context)
  needs < 0: NO

--- (b) the sleeve on the deployed book's worst-decile dates ----------------
  worst decile = 9 dates, deployed $-20,268
  sleeve positions on those dates: n=6  meanR +0.163  $ (1/2) +836
  POWER STOP — n < 10. The CI is NOT read and (b) is
  recorded NOT EVALUABLE, not failed. This was the pre-registered
  expectation for a 1/day rule; the honest conclusion is 'needs new dates'.

--- (c) worst-quartile tail, by year ----------------------------------------
  2024: worst-quartile dates   7  deployed     -1,524  sleeve n=  5 meanR +0.118  -> positive
  2025: worst-quartile dates  10  deployed     -1,650  sleeve n=  8 meanR -0.086  -> not positive
  2026: worst-quartile dates   4  deployed       -823  sleeve n=  3 meanR +0.472  -> positive
  tail positive in 2/3 evaluable years — needs >= 2: YES

--- H2 verdict --------------------------------------------------------------
  (a) not met   (b) NOT EVALUABLE (power stop)   (c) MET
  H2 = NOT EVALUABLE — the primary gate cannot be read on this window.

==============================================================================
H0b — FRESHNESS: does the headline survive a fresh-marks cut?
==============================================================================
  Long premium is the one structure a carried-forward mark flatters.
  Cut to stale_at_cap <= 3 AND pct_real >= 0.5,
  then RE-PICK (the cut can change which calendar P1 selects) and
  recompute the headline.

  fill after the cut: 66/90 deployed dates (73.3%), 6/9 worst-decile
  meanR +0.274  CI [+0.016, +0.642]  n=66   meanE +0.093
  worst-decile cell: n=6  meanR +0.163   (below the power stop — no CI read)

==============================================================================
H3 — SIZING: the largest f that harms neither drawdown nor the worst date
==============================================================================
  Two baselines, a deliberate change from vol_sleeve: the calendar must
  beat the hedge the operator ALREADY HAS, not just the empty seat.
  (i) the deployed ladder alone; (ii) ladder + the SHIPPED bear sleeve
  (|delta| descending, 1/day, <= 1/2 size, config/deployment-rules.md §4).

  calendar sleeve: 68 positions; bear sleeve: 84 positions; both over 90 deployed dates

  baseline: (i) deployed ladder alone
      f      total $     max DD $  worst date $  neg dates
   0.00       63,553       -7,609        -3,212         31
   0.25       66,866       -6,917        -3,229         31
   0.50       70,179       -6,448        -3,245         31
   1.00       76,805       -5,561        -3,279         32
  -> NOT MET at any size — no fraction leaves both drawdown and worst-date unharmed.
     bound by: drawdown ok at every f; worst-date fails  (f=1.00 moves DD +2,048, worst date -67, total +13,252)

  (shipped bear sleeve alone contributes $+1,446 over 84 dates)

  baseline: (ii) ladder + SHIPPED bear sleeve
      f      total $     max DD $  worst date $  neg dates
   0.00       64,999       -6,606        -3,298         36
   0.25       68,312       -5,978        -3,315         36
   0.50       71,625       -5,349        -3,332         35
   1.00       78,251       -5,187        -3,365         33
  -> NOT MET at any size — no fraction leaves both drawdown and worst-date unharmed.
     bound by: drawdown ok at every f; worst-date fails  (f=1.00 moves DD +1,418, worst date -67, total +13,252)

==============================================================================
H4 — CONDITIONAL PICK: is P1 the right rule, within the day?
==============================================================================
  Same-date pairing throughout, so the day is its own control and the
  level problem that sinks every cross-sectional comparison does not
  apply. A P2-P6 pass with P1 failing is a candidate for a future
  window, never a ship — the pre-registration fixes P1 as THE rule.

--- coverage and standalone mean of each rule -------------------------------
  rule                      dates    meanR      $ (1/2)
  P1 nearest-ATM               68   +0.228       13,252
  P2 longest near DTE          68   +0.309       15,639
  P3 shortest near DTE         68   +0.247       12,668
  P4 widest expiry gap         68   +0.192       11,508
  P5 top-pick ticker           17   +0.299        2,256
  P6 ETF only                  47   +0.215        6,784

--- P1 vs the day's MEAN fillable calendar (paired by date) -----------------
  n=68 dates  dR -0.029  CI [-0.131, +0.064]
  (mean day carries 1.9 fillable calendars)

--- P1 vs P2 longest near DTE (same-date pairs only) ------------------------
  n=68 dates (46 identical picks)  dR -0.081  CI [-0.206, +0.042]

--- P1 vs P3 shortest near DTE (same-date pairs only) -----------------------
  n=68 dates (46 identical picks)  dR -0.019  CI [-0.198, +0.127]

--- P1 vs P4 widest expiry gap (same-date pairs only) -----------------------
  n=68 dates (49 identical picks)  dR +0.036  CI [-0.068, +0.140]

--- P1 vs P5 top-pick ticker (same-date pairs only) -------------------------
  n=17 dates (10 identical picks)  dR -0.258  CI [-0.906, +0.175]

--- P1 vs P6 ETF only (same-date pairs only) --------------------------------
  n=47 dates (36 identical picks)  dR +0.021  CI [-0.120, +0.162]

==============================================================================
H5 — TIMING (POST-HOC, labelled): when is the calendar worth carrying?
==============================================================================
  NOT pre-registered as a gate. Every cell here was chosen AFTER seeing
  vol_sleeve, including the one CI-clearing conditional it found
  (calendar x earnings-inside-DTE, +0.356 vs -0.035, n=42). Read as a
  CANDIDATE for an independent window; nothing here can ship.

  condition                         n    meanR   vs rest  diff CI95 (date-clustered)
  mech_cell == BEAR_HE             31   +0.295    +0.172            [-0.420, +0.893]
  mech_vol H-VOL                   21   -0.020    +0.339            [-0.907, +0.083]
  model RANGE + C/L-VOL            15   +0.981    +0.015            [+0.111, +2.422]  <- excludes 0
  earnings inside DTE              14   +0.184    +0.239            [-0.585, +0.382]

==============================================================================
EXIT SENSITIVITY (LABELLED) — the same tables held to near-leg expiry
==============================================================================
  pt / sl / tef all None. It MAY NOT change the verdict; it exists so the
  write-up can say whether the verdict is exit-shape-dependent.

==============================================================================
H1 — STANDALONE expectancy of the P1 (hold to near expiry) sleeve (CONTEXT, not a gate)
==============================================================================
  A hedge is allowed to lose money standalone; the shipped bear sleeve
  does. This is here so the write-up can say what it costs.

  n=68 positions over 68 dates
  meanR -0.193  CI [-0.466, +0.039]   win 44%   $ (1/2 size) -3,341
  meanE +0.034  CI [-0.160, +0.218]
  years R: 2024 +0.019  2025 -0.491  2026 +0.044   (2/3 positive)
  years E: 2024 +0.159  2025 -0.243  2026 +0.370   (2/3 positive)
  exits: expired=51  dollar_stop=13  cap_open=4
  P1 (hold to near expiry)       n=  68  win   44%  PF  0.58  meanR -0.193  $   -15,891  MFE  +0.99  MAE  -0.63  gb  0.64  cap  -0.20

==============================================================================
H2 — HEDGE CONTRIBUTION (P1 hold-to-expiry) — THE PRIMARY GATE
==============================================================================
  D2's rule verbatim: (a) date-level correlation < 0, (b) mean sleeve R
  on the deployed book's worst-decile dates > 0 with a date-clustered CI
  excluding zero, (c) worst-quartile tail positive in >= 2 evaluable
  years. All three. POWER STOP: fewer than 10 positions in the
  worst-decile cell and (b) is NOT EVALUABLE — not 'failed'.

--- (a) date-level correlation with the deployed book -----------------------
  corr(daily $)       -0.049  CI95 [-0.227, +0.148]   over 90 deployed dates (unfillable carried at 0)
  corr(daily mean R)  +0.012  CI95 [-0.144, +0.177]   (context)
  needs < 0: YES

--- (b) the sleeve on the deployed book's worst-decile dates ----------------
  worst decile = 9 dates, deployed $-20,268
  sleeve positions on those dates: n=6  meanR +0.142  $ (1/2) +1,087
  POWER STOP — n < 10. The CI is NOT read and (b) is
  recorded NOT EVALUABLE, not failed. This was the pre-registered
  expectation for a 1/day rule; the honest conclusion is 'needs new dates'.

--- (c) worst-quartile tail, by year ----------------------------------------
  2024: worst-quartile dates   7  deployed     -1,524  sleeve n=  5 meanR +0.227  -> positive
  2025: worst-quartile dates  10  deployed     -1,650  sleeve n=  8 meanR -0.121  -> not positive
  2026: worst-quartile dates   4  deployed       -823  sleeve n=  3 meanR -0.100  -> not positive
  tail positive in 1/3 evaluable years — needs >= 2: NO

--- H2 verdict --------------------------------------------------------------
  (a) MET   (b) NOT EVALUABLE (power stop)   (c) not met
  H2 = NOT EVALUABLE — the primary gate cannot be read on this window.

==============================================================================
VERDICT
==============================================================================
  H0 FILL           MET
  H2 (primary)      NOT EVALUABLE
  H2 under hold     NOT EVALUABLE   (sensitivity — may not change the verdict)

  Ship ceiling per the pre-registration: an optional second hedge sleeve
  in config/deployment-rules.md §4, requiring H0 MET and H0b not flipping
  the verdict and H2 MET and H3 deployable at f >= 0.25. Anything less is
  a candidate. Nothing here changes config/backtest.yml.

==============================================================================
exit code 0 after 5.5s
==============================================================================
```

</details>
---

## 2026-08-13 — `account_sim` RUN: the $25k edge survives its caps but not its window; the verdict grammar had a hole

**Provenance.** Run 2026-08-13, git 470b95f (dirty), the 08-11 v3 exports
(BacktestResults 1,926 / BacktestProxy 4,533 / AnalysisClaude
11,836 rows), `load_book(include_bs=False)` → 795 rows; mech table 803 rows
2026-08-13 (book.py boilerplate — not used by any printed account_sim output;
validator-checked). Nothing ships from this study by pre-registration.

`backtests/study_output/account_sim-latest.txt` is RETAINED on disk, but only
because `scripts/study_charts/cli.py` raises without it and `make study-docs`
calls the chart build unguarded — not as this write-up's evidence. The file
there today is a LATER re-run (2026-08-15 19:01:23, git 7708a92) against the
same 08-11 v3 exports; it was checked against this section before the excerpt
below was folded and reproduces every gate figure asserted here — G1
`n=301 exact=289`, `n_credit_ungated 277`, B1 `220 / 90 / $63,553`, G2
`175 exact=175`. Read the folded excerpt, not the file, as the record.

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


<details>
<summary>Report excerpt, verbatim — run 2026-08-15 19:01:23, git 7708a92 (dirty), same 08-11 v3 exports; header, G1-G5, both populations' baselines + criteria, verdict</summary>

```text
==============================================================================
STUDY: account_sim
==============================================================================
  run at    2026-08-15 19:01:23
  command   python -m scripts.backtest_study.f4_deployment.account_sim
  git       7708a92 (main, working tree dirty)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
   4,533 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestProxy.csv
  11,836 rows  2026-08-11 17:24  backtests/to_evaluate/analysis - AnalysisClaude.csv
     805 rows  2026-08-15 12:38  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================

==============================================================================

[... lines 16-170 elided ...]

GATES — G1..G5 (non-zero exit on any failure)
==============================================================================

--- G1 — book calibration quoted, B1 line reproduced ------------------------
  debit_calib      n=301  exact=289  near=0  hard=12
  n_credit_ungated 277  (admitted WITHOUT the exact-replay gate — book.py's credit caveat)
  B1 (stored contracts, stored R): 220 positions / 90 dates / $63,553
  expected (account-sim.yml, gates.book_calibration): 220 / 90 / $63,553
  G1: PASS

--- G2 — scaling identity calibrated at scale=1 against the stored rows -----
  The identity code path is run with factor 1 (stop = the harness's own
  $1,000) at the STORED contract count, under DEBIT_PROD — the profile that
  GENERATED the stored rows. It must reproduce (exit_reason, days_held,
  round(R,4)) exactly. Calibrating against the shipped be_after-0.50 merge
  instead would be testing an exit change, not the identity.
  calibrated debit picks re-replayed: 175  exact=175  mismatched=0
  credit picks (counted, NOT gated — book.py admits them ungated): 42
  debit picks failing book.py's own calibration (excluded from G2): 3
  G2: PASS

--- G3 — ledger accounting identity, checked after every event --------------
  events checked: 320   positions: 160
  final cash $36,248.00  reserved $0.00  realized $11,248.00  (capital $25,000.00)
  G3: PASS  (0 violations)

--- G4 — unconstrained walk reproduces top_k_per_day by set equality --------
  walk picks 220 (incl. 2 unsizable slot-burners)  vs top_k_per_day 220
  symmetric difference: 0
  G4: PASS

--- G5 — the simulator is BLIND to how a position turned out ----------------
  Every record is re-wrapped so that reading an outcome key raises, AND the
  outcome columns are DELETED from the underlying trade row so a read cannot
  route around the wrapper. The run must then complete and produce a
  byte-identical book. This is what makes the sim safe to hand to an agent
  proposing live positions: no ordering, sizing or admission decision can be
  standing on a number that would not exist yet in real time.
  tripwire live (reading a blinded outcome key raises): True
  row columns deleted from every Trade: days_held, exit_reason, mae_day, mae_pct, mfe_day, mfe_pct, pnl_at_cap_pct, realized_pnl_pct
  positions: sighted 160  blind 160  differing 0
  G5: PASS

  GATES: ALL PASS

==============================================================================

[... lines 217-233 elided ...]

[PRIMARY dense episodes] B1 / B2 BASELINES
==============================================================================
  B1  stored contracts, stored outcomes     n= 112  dates= 46  $    45,671  meanR +0.511
  B2  $25,000 max-loss sizing, unconstrained  n= 110  dates= 46  $    23,157  meanR +0.298

  B1 -> B2 isolates GRANULARITY (contract counts), B2 -> constrained isolates the CAPS.
  B2/B1 dollar ratio 0.51x — the small account holds fewer contracts, so the dollar book shrinks by SIZE before any
  constraint is applied. B1's stored counts are a $50k book's.

==============================================================================

[... lines 244-485 elided ...]

[PRIMARY dense episodes] CRITERIA A1-A6
==============================================================================
  A1 EDGE SURVIVAL  meanR +0.290  CI95 [+0.113,+0.457]  years 2025:+0.445  2026:+0.097
     MET  (needs mean>0, CI excluding zero, every year positive)
  A2 ATTRITION      constrained $11,399 vs B2 on the same 37 dates $12,675  = 90%
     MET  (needs >= 60%)
  A3 NO BLOWUP      maxDD $-4,354 = 17.4% of capital;  ledger violations 0
     MET  (needs no over-reservation and DD <= 25%)
  A4 ATTRIBUTION    150 candidates partition exactly into 72 taken + exclusions
     MET  (mismatch FAILS the run)
  A5 STABILITY      constrained/B2 ratio ALL 90% (n=72);  ex-2025_mar_apr 131% (+41pt, n=37)  ex-2026_feb_apr 83% (-7pt, n=40)
     NOT MET  (needs <= 15 points of movement on both cuts)
  A6 CREDIT SENS.   debit-only n=55  meanR +0.231  CI95 [+0.021,+0.435]  years 2025:+0.379  2026:-0.008
     NOT MET  (A1 must hold on debit-only)

==============================================================================

[... lines 502-501 elided ...]

[SECONDARY full book] B1 / B2 BASELINES
==============================================================================
  B1  stored contracts, stored outcomes     n= 220  dates= 90  $    63,553  meanR +0.354
  B2  $25,000 max-loss sizing, unconstrained  n= 218  dates= 90  $    18,895  meanR +0.187

  B1 -> B2 isolates GRANULARITY (contract counts), B2 -> constrained isolates the CAPS.
  B2/B1 dollar ratio 0.30x — the small account holds fewer contracts, so the dollar book shrinks by SIZE before any
  constraint is applied. B1's stored counts are a $50k book's.

==============================================================================

[... lines 512-775 elided ...]

[SECONDARY full book] CRITERIA A1-A6
==============================================================================
  A1 EDGE SURVIVAL  meanR +0.159  CI95 [+0.019,+0.300]  years 2024:+0.037  2025:+0.295  2026:+0.077
     MET  (needs mean>0, CI excluding zero, every year positive)
  A2 ATTRITION      constrained $11,248 vs B2 on the same 77 dates $6,508  = 173%
     MET  (needs >= 60%)
  A3 NO BLOWUP      maxDD $-6,284 = 25.1% of capital;  ledger violations 0
     NOT MET  (needs no over-reservation and DD <= 25%)
  A4 ATTRIBUTION    297 candidates partition exactly into 160 taken + exclusions
     MET  (mismatch FAILS the run)
  A5 STABILITY      constrained/B2 ratio ALL 173% (n=160);  ex-2025_mar_apr -164% (-337pt, n=125)  ex-2026_feb_apr 179% (+6pt, n=129)
     NOT MET  (needs <= 15 points of movement on both cuts)
  A6 CREDIT SENS.   debit-only n=123  meanR +0.137  CI95 [+0.001,+0.277]  years 2024:+0.143  2025:+0.185  2026:-0.008
     NOT MET  (A1 must hold on debit-only)

==============================================================================
VERDICT (PRIMARY dense episodes population — the primary)
==============================================================================
  A1  MET
  A2  MET
  A3  MET
  A4  MET
  A5  NOT MET
  A6  NOT MET

  >>> FEASIBILITY NOT CONFIRMED (A1-A3 hold; A5 and/or A6 fail; stability/robustness not established on this window) <<<

  2026-08-14 AMENDMENT (labelled, not a redefinition — see the comment above
  print_verdict): the pre-registered grammar (FEASIBLE = A1^A2^A3^A5^A6;
  FEASIBLE-BUT-DEGRADED = A1^A3 with A2 failing; NOT FEASIBLE AT $25,000 = A1 fails)
  did not name this combination and previously printed "NO VERDICT MATCHES"
  here. No criterion threshold, measured number, or meaning of A1-A6 moved —
  only the outcome-to-label mapping was completed. The checklist above is
  the whole result; this label states what it means, nothing more.

==============================================================================
CLOSE
==============================================================================
  verdict: FEASIBILITY NOT CONFIRMED (A1-A3 hold; A5 and/or A6 fail; stability/robustness not established on this window)
  Nothing in this report is a shippable rule. The cap values are a friction model,
  not a tuned parameter, and none of them may be adopted on P&L.
  positions CSV: 447 rows -> backtests/study_output/account_sim-positions-latest.csv

==============================================================================
exit code 0 after 3.8s
==============================================================================
```

</details>
---

## 2026-08-13 — `account_sim`: PRE-REGISTRATION → [`pre-registrations/f4_deployment/account_sim.md`](../pre-registrations/f4_deployment/account_sim.md)

Moved out of this log: a pre-registration is an immutable artifact and this
file is pruned into `archive/`. The section is unchanged, just relocated.

---

## 2026-08-13 — `calendar_hedge`: PRE-REGISTRATION → [`pre-registrations/f3_structure/calendar_hedge.md`](../pre-registrations/f3_structure/calendar_hedge.md)

Moved out of this log: a pre-registration is an immutable artifact and this
file is pruned into `archive/`. The section is unchanged, just relocated.

---

