# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index.

**State of play (2026-08-13).** Two studies pre-registered AND RUN the same day,
each graded through the new two-analyst replication protocol
(`replication-protocol.md`, agents in `.claude/agents/`). **Nothing ships from
either.** `account_sim`: all gates pass; at $25k the dense-episode edge survives
its caps (99% of the $25k-sized book) but **the binding constraint is delta
exposure, not cash**, the cap ordering is adverse (rejected picks outperform
taken), and A5/A6 fail — the pre-registered verdict grammar had a hole (A1
holds, A5/A6 fail matches no label); feasibility NOT CONFIRMABLE on this
window. **Same-day addendum:** `account_sim` audited for lookahead ahead of the
live-agent step — no per-row foresight in selection or sizing, now ENFORCED by a
new **G5 blindness gate** (outcome keys raise, outcome columns deleted from the
trade row, book must come out identical: 124/124, 0 differing); the remaining
lookaheads are rule-level (in-sample ladder) and universe-level, the latter
addressed by `--structure-universe`, which admits 19 stale-`trailing_stop` proxy
rows the calibration gate wrongly withheld (+3 deployed picks, 0 displaced,
**verdict unchanged**; bs still dropped). `calendar_hedge`: R1–R4 all pass (R4 reproduces vol_sleeve's calendar
cell EXACTLY), H0 fill 75.6%/66.7% MET, but **H2 is NOT EVALUABLE — the power
stop fired at n=6 exactly as pre-committed — and the readable correlation
component is wrong-signed (+0.075)**; H3 blocked by the worst-date criterion by
$17–67 while maxDD improves at every f. The candidate is neither promoted nor
killed: **needs new dates.** Carry-forwards: RANGE+C/L-VOL calendar cell (n=15,
diff CI [+0.111,+2.422], post-hoc) and the H2 clause amendment (power stop
should suspend only (b)). The 08-13 sweep-leg scrape (857 contracts) feeds ARM
S, which RAN on the grown cache (~1,418 contracts added): **all 30 sweep cells
power-stopped, zero candidates; iron condor NOT EVALUABLE at 39.9% four-leg
coverage** — the whole hedge programme (calendar, put calendar, diagonal,
narrower) now terminates at one wall: 9 worst-decile dates cannot power a
worst-decile criterion under a 1/day sleeve. **New dates are the only path.**
R4 is re-keyed to the pre-scrape cache snapshot (labelled amendment). The
2026-08-12 open-queue audit stands: bear ratchet blocked on a harness
mechanism, flat-band cut waits for new bear rows, rollback triggers
accumulating. Prior state follows.

**State of play (2026-08-12, vol arm).** The counterpart-leg scrape is DONE
(1,322/1,337 mirrors cached; straddle-able groups 15/481 → 481/481) and
**`vol_sleeve` has RUN**. **Nothing ships.** The straddle clears its
pre-registered Q1 gate and then dies on the log's standard both-window cut
(+0.106 → +0.029, CI crosses zero). Q2 is not merely null — it comes back with
the **wrong sign**: the sleeve is POSITIVELY correlated with the deployed book
(+0.268, CI [+0.081, +0.440]), because synthesizing vol on the engine's own
signal dates buys more of the same event. The one survivor is the **calendar**,
which is uncorrelated (+0.088, CI spans zero) and pays on the deployed book's
worst decile (+0.336, CI [+0.124, +0.486]) — a post-hoc subgroup of a pooled
gate, so it is a CANDIDATE needing its own pre-registration, not a finding.
Entry and pre-registration below. Prior state follows.

**State of play (2026-08-12, newest).** A new research programme opened after
the operator's read that the reference PDFs "do not have much impact" —
**correct, and structurally so**. Two things ran: a new underlying price-STATE
feature layer (`underlying_features.py`), and `bear_rewrap`, which asks whether
the bear VERTICAL is the wrong wrapper for a bear signal. Result: **`long_put`
clears four of five pre-registered gates and FAILS the fifth (2026 alone is
−0.026), and the chosen portfolio criterion P1 is NOT MET on 9 worst-decile
dates.** Nothing ships. Entry below. Prior state follows.

**State of play (2026-08-12, latest).** The §5 follow-on from the `be_after`
entry has RUN: the underlying-conditioned exit, moved from the MFE peak (which
cannot be seen in flight) to the ENTRY SESSION (which can). **Nothing ships.**
ARM C — the confound control that decides whether ARM D is real — does NOT hold
its sign across day-0 P&L bands, and the best ARM R variant misses the CI
criterion by 0.002 with 2024 carrying it. Two things came out of it anyway: real
stock OHLC is now cached for the whole book (new collector), and the day-0 move
turns out to separate structures rather than the book — `bull_call_spread` is
nearly INDIFFERENT to whether the stock confirmed while `bull_put_spread` swings
+0.387 → −0.130 on it. Entry below. Prior state follows.

**State of play (2026-08-12, late).** Operator asked whether the engine has any
measurable edge at all, or whether selection needs more tuning. **Verdict: the
edge is real, narrow, and not selection-tunable** — see the edge-status entry
below. The same conversation reopened ONE bounded exit question: bear MFE
give-back below the `be_after: 0.50` arming threshold, quantified below as
**−$77.2k across 124 rows the shipped ratchet cannot reach**. That is a
pre-registerable grid extension, not a re-opening of selection. Prior state
follows.

**State of play (2026-08-12).** The deployment rules are now split in two:
[`config/deployment-rules.md`](../deployment-rules.md) is an instructions-only
operator card, and [`deployment-evidence.md`](deployment-evidence.md) holds the
derivation, the caveats and the **open rollback triggers** that used to be
interleaved with them. Entry below. Prior state follows.

**State of play (2026-08-11, CLOSE-OUT).** **v3 is closed and shipped.** Backtest
tuning stops here: the ML search was a null result across all 15 cells and its
ablations put the ceiling in the columns, not the estimator, so no further run on
this book can answer anything. Three things shipped — the `be_after: 0.50` bear-debit
ratchet (suppressed inside BEAR_HE, where the trail dominates it), the bear
hedge-sleeve rules (`|delta|` descending, ≤ ½ size), and the live-loop
`SUBSTITUTED` fix. **The shipped ratchet is worth +0.015 mean R, not the study's
+0.041** — production already carried the BEAR_HE trail, which was buying the same
rows. The evidence source now moves from the backtest to live fills. v4 (prompt
trimmed of `score_flow`/`score_dealer`) starts on fresh tabs with a
pre-registered composition bridge before its rows are read against v3-derived
rules. Details in the close-out entry below. Prior state follows.

**State of play (2026-08-11, late).** The ML combination search has RUN and is a
NULL RESULT (no model beats the ladder in any of 15 model×strategy cells); the
bear arm run alongside it found that bear structures are an EXIT problem after
all — `be_after: 0.50` keyed to bear debit spreads clears every pre-registered
criterion including the 2026 window on its own, which is the "second sustained
bear drawdown" addendum 12 said would settle it. Recommended, not shipped —
awaiting the operator. Bear SELECTION remains unfixable from these columns
(0 of 496 conditioned subsets survive). Details in the entry below.

**Earlier that day.** The Feb–Apr 2026 holdout backfill is COMPLETE
(33 window dates priced, incl. the 7 late dates and 02-17/02-19) and the
completed-book analysis (below) has all three pre-registered bear_put DEMOTE
criteria firing at n=164 with the real-tier discordance resolved downward —
the demotion is decision-eligible; implementation choice (intake veto vs
ladder VETO vs Tier-C-never-deploy) is the user's. Shipped config is the
source of truth — `config/backtest.yml` (exits, `regime_exit.cells: BEAR_HE`
only) and `config/deployment-rules.md` (VETO / A / B / C ladder, top-3 per
day, bull_put band `0.08 ≤ |delta| ≤ 0.20` + `DTE ≤ 59`). Open questions:
(1) **bear_put implementation** — verdict reached, mechanism not chosen;
(2) **the long-dated blind spot** — h≥180 still unpriceable with real data,
and the bs tier — measured as attenuating (tail-compressed marks shrink every
effect toward zero) AND selection-contaminating (64 rows inside the top-3/day
replay) — is now OFF (`proxy.bs_fallback: false`); evaluate real+tweak only,
and filter the 301 legacy bs rows out by `proxy_method` at read time;
(3) **live substitution** — the
operator sometimes trades naked where the engine emitted a spread, which
breaks the live walk-forward's attribution. Next study queued: the ML
combination search — plan pre-written in [`ml-plan.md`](ml-plan.md), NOT run.

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

## 2026-08-13 — `account_sim`: PRE-REGISTRATION (written BEFORE the study was built or run)

**Question.** Does the shipped ladder's paper edge survive a **$25,000** account
with real opening constraints? This is a FEASIBILITY study, not an edge search.
The selection rule is FROZEN (`protocol.top_k_per_day(book, ladder_rank, k=3,
ladder_eligible)` — the shipped operator card) and the exits are FROZEN (the
shipped profiles via `bear_giveback.prod_profile_for`). No column may be added
to selection and no exit knob may be moved. The only new machinery is an
account ledger. **Nothing ships from this study under any outcome.**

**Plan-time observations (disclosed).** These distributions were measured on the
pooled book (795 rows real+tweak, 08-11 exports) while DESIGNING this study; the
cap values below are informed by them and that is stated rather than hidden.
Ladder picks: 220 over 90 dates (218 with usable max_loss). At $25k / 2%
($500 budget): **170/218 picks floor at 1 contract; 133 breach the budget at one
contract** (worst single-position risk $3,321 = 13.3% of equity). Per-position
|delta-notional|/equity: p10 0.05, median 0.14, p75 0.22, p90 0.32, max 0.94.
Daily |net| delta-notional/equity: median 1.28×, p90 4.73×, max 8.38×; only
1/218 deployed picks is negative-delta, so net ≈ gross until a hedge sleeve is
added. Reserved-capital/equity: median 0.27, p90 0.83, max 1.80. Concurrent
open positions: median 8, p90 29, max 48. The 118 signal dates cluster hard
(2026-03: 124 rows; nine months have ≤4 dates) — not a trading calendar.

**Constants, fixed here.**
- `STARTING_CAPITAL = 25_000`, fixed base (matching production's fixed
  `portfolio_value`); a compounding-equity run is a labelled sensitivity only.
- `RISK_PER_TRADE_PCT = 0.02` → $500; `contracts = max(1, int(500 /
  max_loss_per_contract))` — a MAX-LOSS basis, deliberately more conservative
  than production's risk-to-stop basis (`budget / (premium × 0.75 × 100)`),
  because a real small account cannot assume the stop fills; the difference is
  disclosed here, not discovered later. Verified `max_loss_per_contract ==
  entry_net×100` on 593/593 debit rows; it is also the broker-margin basis for
  credits.
- `MAX_POSITIONS_PER_DAY = 3`; within-day order = `ladder_rank` descending (the
  shipped ordering, not a knob).
- Reserved capital = `max_loss_per_contract × contracts`, held from entry
  session `t.grid[0]` through exit session `t.grid[days_held-1]` inclusive,
  released with realized P&L booked at exit.
- Delta-notional per position = `|delta| × 100 × contracts × entry_underlying`,
  computed at entry, constant for the position's life. `delta` is the row's
  signed NET per-spread delta (`simulate.py:496-501`; one market anchor leg +
  BS for the rest — decision-time, never drifting). Portfolio net = |Σ signed|;
  gross = Σ|·|; both reported.
- **PER_POSITION_CAP = 0.25 × equity** ($6,250) — just above the observed p75,
  bites the tail without reshaping the book (a cap below the median would be a
  different strategy, not a friction).
- **NET_CAP = 1.50 × equity** ($37,500) — binds on roughly the upper half of
  occupied sessions, which is the point.
- The $500 dollar stop is applied through the exact scaling identity: replay at
  `contracts × 2` under the frozen harness ($1,000 stop) and divide dollars by
  2; integrality asserted; calibrated at scale=1 against stored rows (G2).

**Arms (all reported, none adopted).**
- R (REJECT): a position breaching any cap at risk-sized contracts is skipped,
  logged with counterfactual R / R_dol. D (DOWNSIZE): contracts reduced to the
  largest integer satisfying every cap, then **re-replayed at the reduced
  size** (never rescaled arithmetically); 0 → reject.
- F1 (TAKE the 1-contract floor even when its max loss exceeds $500 — what
  production does) vs F2 (REFUSE those picks). Known before registration: F1 vs
  F2 divides 133/218 of the book; this is the study's central object.
- ARM H: the SHIPPED bear hedge sleeve (1/day, `|delta|` descending, ≤½ size)
  added to the constrained run — the only way net-vs-gross becomes measurable.

**Cap grid, and the anti-tuning rule.** Per-position ∈ {0.15, 0.25, 0.40, ∞} ×
net ∈ {1.00, 1.50, 2.50, ∞}. The HEADLINE is the single pre-registered
(0.25, 1.50) cell, quoted first and alone. **No cap value may be adopted,
recommended, or carried into a conclusion on the basis of its P&L in this
grid.** The only admissible reading is qualitative monotonicity; a non-monotone
surface is evidence of a ledger bug, not an opportunity.

**Population.** PRIMARY = dense episodes: maximal runs of signal dates with no
internal gap > 5 trading sessions and ≥ 10 dates; the episode list prints
before any result. SECONDARY = the full sparse book, labelled as an
availability upper bound / concurrency lower bound; it may not carry a
conclusion alone. No annualised return, Sharpe, or time-to-recover may be
quoted anywhere in the write-up.

**Baselines.** B1 = same ladder, unconstrained, STORED contract counts and
stored outcomes — must reproduce the deployed-book line the 08-12 `vol_sleeve`
report printed on the same exports (**220 positions / 90 dates / $63,553**).
B2 = same ladder, unconstrained, $25k max-loss sizing. B1→B2 isolates
granularity; B2→constrained isolates the caps.

**Criteria.**
- A1 EDGE SURVIVAL — constrained mean R over taken positions > 0, 95%
  date-clustered CI excluding zero, positive every year present.
- A2 ATTRITION — constrained total $ ≥ 60% of B2 on the same dates.
- A3 NO BLOWUP — ledger never over-reserves (violation FAILS the run) and
  constrained max drawdown ≤ 25% of starting capital.
- A4 ATTRIBUTION — every rejection/downsize attributes to exactly ONE binding
  constraint (cash / per-pos delta / net delta / min-1 refusal / day-3 cap)
  and the counts sum exactly (self-check; mismatch FAILS the run).
- A5 STABILITY — constrained/B2 dollar ratio moves ≤ 15 points across both
  mandatory window cuts.
- A6 CREDIT SENSITIVITY — A1 must also hold on the debit-only subset (credit
  rows are admitted ungated by `book.py`).

**Verdicts, worded now.** FEASIBLE = A1∧A2∧A3∧A5∧A6. FEASIBLE-BUT-DEGRADED =
A1∧A3 with A2 failing. NOT FEASIBLE AT $25k = A1 fails. On NOT FEASIBLE, and
only after the primary verdict prints, the report prints the smallest capital
in {25k, 35k, 50k} at which A1∧A2 pass — an operator note under the same
anti-tuning rule.

**Gates (non-zero exit on failure).** G1 book calibration quoted
(`debit_calib`, `n_credit_ungated`). G2 replay identity: every deployed pick
re-replayed at stored contracts, scale=1, must match stored
`(exit_reason, days_held, round(R,4))` for calibrated debit rows. G3 ledger
self-check: at every session `cash + Σreserved == 25,000 + Σrealized-to-date`.
G4 selection identity: the unconstrained pick set equals `top_k_per_day(...)`
by set equality (proves no silent re-selection).

---

## 2026-08-13 — `calendar_hedge`: PRE-REGISTRATION (written BEFORE the study was built or run)

**Question.** The 2026-08-12 `vol_sleeve` run left one CANDIDATE: the calendar
is uncorrelated with the deployed book (+0.088, CI spans zero) and returns
+0.336 CI [+0.124, +0.486] on its worst decile — a per-structure subgroup of a
POOLED gate, n=13 rows over 7 dates. This study re-derives that number under a
pre-registered pick rule, a fixed universe, and a strict fill definition. It
will be a different number on a smaller n; that is the point. A bounded sweep
of untried wrappers runs SEPARATELY behind it (ARM S below).

**Frozen inputs.** `book.load_book(include_bs=False)`; deployed book =
`top_k_per_day(ladder_rank, k=3, A|B)`; synthesis/pricing =
`vol_sleeve.build_legs` + `_strike_index` and `bear_rewrap.{entry_date_for,
net_entry, net_marks, leg_details, size_contracts, reconstructs}` UNCHANGED;
exits = frozen `harness.replay` under `DEBIT_PROD`. Nothing in `harness.py`,
`vol_sleeve.py`, `bear_rewrap.py`, `config/backtest.yml`, or
`config/deployment-rules.md` is edited.

**Universe.** Only dates where the ladder actually deployed, and a candidate
must be **fillable on the ladder's own entry session** — both legs cached on
`grid[0]`, NOT the loose ≤5-day entry-lag rule `vol_sleeve` used (you cannot
decide to hedge Monday and be filled Friday). The lag distribution under the
loose rule prints as a sensitivity. Excluded and counted: `entry_net ≤ 0`
(crossed/stale market — vol_sleeve saw 2/183) and `far_exp ≤ near_exp`.

**Pick rules (decision-time only; the list is CLOSED here).**
P1 nearest-ATM (min |K*−S|/S among the day's fillable calendars); P2 longest
near-leg DTE; P3 shortest near-leg DTE; P4 widest expiry gap; P5 same ticker as
the day's top-ranked deployed position (P1 tie-break); P6 ETF underlyings only,
then P1. **THE RULE IS P1** — geometry not score, the closest analogue of the
shipped bear-hedge convention, and implicitly what produced the vol_sleeve
number. P2–P6 print as a robustness fan; a P2–P6 pass with P1 failing is a
candidate for a future window, never a ship.

**Sizing.** One hedge per day, ≤½ position: `bear_rewrap.size_contracts` × 0.5
on the shipped $50k basis (directly comparable with the shipped bear sleeve).
Portfolio effect at sleeve fractions f ∈ {0, 0.25, 0.50, 1.0}, exactly as
`bear_deploy` D3.

**Gates that must pass before any hedge number is read.**
- **H0 FILL:** P1 produces a fillable hedge on ≥60% of deployed-book dates AND
  ≥60% of the deployed book's worst-decile dates (both print side by side; the
  gate fails on either). Unfillable days are carried as f=0 in every portfolio
  line, never dropped from the denominator. A hedge unavailable exactly when
  needed is not a hedge.
- **H0b FRESHNESS:** the headline must survive `stale_at_cap ≤ 3` and
  `pct_real ≥ 0.5` (`vol_sleeve.mark_quality`).

**Exit.** `DEBIT_PROD` (pt .90 / sl .75 / tef .75) — the profile the candidate
was measured under; no calendar-specific exit (that would stack a second free
parameter on the pick rule). The frozen harness already handles calendars: the
grid ends at the SHORT leg's expiry, `_price_asof` never carries a leg past its
own expiration, and multi-expiry net marks are deliberately unclamped. As a
LABELLED SENSITIVITY only: the same table under hold-to-near-expiry
(pt/sl/tef all None) — it may not change the verdict; it exists so the
write-up can say whether the verdict is exit-shape-dependent.

**Criteria (H1–H5, mirroring bear_deploy D1–D5, renamed to avoid confusion).**
- H1 STANDALONE (context, NOT a gate): mean E and R of the P1 sleeve,
  date-clustered CI, per-year signs. Negative standalone does not fail a hedge.
- **H2 HEDGE CONTRIBUTION (the primary gate, D2's rule verbatim):** on
  deployed-book dates, (a) date-level correlation of the two daily series < 0;
  (b) mean sleeve R on the deployed book's worst-decile dates > 0 with
  date-clustered CI excluding zero; (c) worst-quartile tail positive in ≥2
  evaluable years. All three.
- H3 SIZING (D3 verbatim): the largest f whose max drawdown AND worst single
  date are both no worse than f=0.
- H4 CONDITIONAL PICK: within-date paired comparison of P1 vs the day's average
  fillable calendar and vs each of P2–P6.
- H5 TIMING (POST-HOC, labelled): gates on `mech_cell == BEAR_HE`, H-VOL,
  RANGE+C/L-VOL, and earnings-inside-DTE (vol_sleeve's one CI-clearing
  conditional: +0.356 vs −0.035, CI [+0.111, +0.664], n=42). Candidate-only.
- **POWER STOP:** if the P1 worst-decile cell has fewer than 10 positions,
  H2(b)'s CI is NOT read and H2 is recorded **NOT EVALUABLE** — not "failed".
  Expected: the cell will be ≈7–9 under a 1/day rule; NOT EVALUABLE is a
  likely and correct outcome, and the honest conclusion is "needs new dates".

**Baselines (two — a change from vol_sleeve, which compared vs no hedge
only).** (i) the deployed ladder alone at $50k; (ii) the ladder PLUS the
SHIPPED bear hedge sleeve (`|delta|` descending, ½ size, 1/day). The calendar
must beat the hedge the operator already has, not just the empty seat.

**Reconstruction gates.** R1 book calibration quoted. R2
`bear_rewrap.reconstructs` on every source row feeding the universe. R3 the
deployed-book replay reproduces the deployed line the 08-12 `vol_sleeve` report
printed on the same exports (220 positions / 90 dates / $63,553). **R4
(the critical one):** with the pick rule disabled and the LOOSE fill rule, this
study must reproduce vol_sleeve's calendar cell EXACTLY — 183 rows, meanR
+0.158, $28,059, exit mix time_exit 124 / pt 28 / dollar_stop 22 / cap_open 5
/ sl 4 — otherwise the gap between +0.336 and whatever H2 prints cannot be
attributed (pick rule vs re-implementation drift). Non-zero exit on failure.

**ARM S — the structure sweep. Runs only AFTER the H arm has printed, only
under `--arm S`, in a separate invocation and report file.**
- S1 `put_calendar` (short near put + long next-cached-expiry put at K*;
  plan-time cache feasibility 577/786 groups). S2 `put_diagonal` (short near
  put at K*, long next-expiry put at nearest cached strike BELOW; 561/786).
  S3 `narrower` (bear vertical, short pulled UP to the highest cached strike
  below the long — mirror of `sub_wider`). S4 `wider` and S5 `long_put` rerun
  UNCHANGED from `bear_rewrap` as internal plumbing controls with known
  answers (wider −0.056; long_put +0.002 failing 2026). S6 `iron_condor`
  (bull-put + bear-call wings at nearest cached-or-scraped strikes around K*,
  same expiry) — included ONLY if the leg scrape reaches ≥60% four-leg group
  coverage (plan-time cache-only feasibility is 214/786, far short); otherwise
  NOT EVALUABLE with the coverage number printed.
- Missing legs are scraped FIRST by `scripts/collector/fetch_sweep_legs.py`
  (resumable: one cache file per contract, `--limit` chunks, skip-existing,
  manifest CSV) into the same cache under the same naming; synthesis results
  are checkpointed to `backtests/sweep_cache/synth_results.csv` so an
  interrupted run resumes instead of restarting.
- MULTIPLICITY: a sweep cell is a CANDIDATE only if its worst-decile CI
  excludes zero at Bonferroni α = 0.05 / (n_structures × n_pick_rules), is
  right-signed every year present, and clears H0. **Nothing in ARM S can ship
  from this run**; the maximum verdict is carry-to-next-window.
- OUT OF SCOPE, so it is not re-litigated: ratio spreads (frozen harness
  `_defined_risk_bounds` is None for unbounded net quantities — a harness
  constraint); straddle/strangle (CLOSED 2026-08-12).

**Ship ceiling.** Nothing changes `config/backtest.yml`. The maximum outcome is
an optional second hedge sleeve added to `config/deployment-rules.md` §4,
requiring H0 MET ∧ H0b not flipping the verdict ∧ H2 MET ∧ H3 deployable at
f ≥ 0.25. Anything less is a candidate.

---

## 2026-08-12 — `vol_sleeve` RUN: the sleeve does not diversify, it DOUBLES DOWN; the calendar is the only survivor

**Provenance.** `backtests/study_output/vol_sleeve-latest.txt`, git 470b95f
(dirty), the 08-11 exports, `book.load_book(include_bs=False)` → 795 rows.
**1,293 synthetic positions** (758 straddle / 352 strangle / 183 calendar) over
**118 dates, 101 tickers**, every leg REAL-priced from
`backtests/option_history_cache/`. Read-only: no config, prompt, ladder or tab
touched. Pre-registration is the entry immediately below this one and was
written before the study was run; the two additions to it are labelled.

### 0. The gates that ran BEFORE any result was read

- **Reconstruction: 786 / 786 (100%).** A ticker-date is used only if this
  study's pricing code, re-pricing the ORIGINAL book row from the same cache,
  reproduces its stored entry and marks. The synthetics are priced by code
  verified against the real book on the same dates.
- **Freshness.** Long premium is the one structure a carried-forward mark
  flatters — a dying option stops trading and gets frozen at its last print. Cut
  to rows whose final mark is ≤3 days stale: straddle **+0.106 → +0.105**
  (n 758 → 740), strangle +0.095 → +0.107, calendar +0.054 → +0.042. **The
  marks are real.** This was the most likely way for the study to be wrong and
  it isn't the way it's wrong.
- Coverage is not a caveat here: median path coverage 1.00, p10 1.00, median
  |K−S|/S **0.019** — these are genuinely ATM structures, not a strike grid
  scraped from whatever was lying around.

### 1. Q1 — the straddle clears the pre-registered gate and fails the standard screen

    structure   n     meanE    CI95 (E)            meanR   win     $R      years(E)
    straddle   758   +0.106   [+0.039, +0.172]    +0.075   36%   158,565   +0.01/+0.12/+0.18
    strangle   352   +0.095   [-0.029, +0.226]    +0.096   39%    62,597   +0.01/+0.19/+0.01
    calendar   183   +0.054   [-0.094, +0.214]    +0.158   55%    28,059   +0.04/-0.06/+0.24

On the pre-registered terms the straddle **passes**: n ≥ 30, date-clustered CI
excluding zero, same sign in all three years. Then the concentration screen —
**an ADDITION to the pre-registration, and it is the log's standard screen**, so
it is recorded as an addition rather than smuggled in:

    straddle   ALL               n=758   E +0.106   CI [+0.039, +0.172]
               ex_2025_mar_apr   n=559   E +0.081   CI [+0.004, +0.156]
               ex_2026_feb_apr   n=563   E +0.081   CI [+0.014, +0.147]
               ex_BOTH windows   n=364   E +0.029   CI [-0.044, +0.101]   <- dead

**Dropping either dominant window leaves it alive; dropping both kills it.** The
single-window cuts, which is all `window_cuts()` does by default, were never
going to catch this — the carrying dates *span* both windows (top-5 dates =
2026-04-02, 2026-03-18, 2025-03-28, 2025-04-03, 2026-03-24, **61% of $R**). A
long-vol book that only pays in the two volatility events in the sample is the
textbook window artifact, and the fact that it survives a single-window cut is
precisely what makes it look like a finding.

**Strangle is worse and clearer:** ex-2025-Mar/Apr takes it to −0.004, and
**97% of its $62.6k is 5 dates**. Not a sleeve, a lottery ticket on two months.

**Long-dated caveat on the `>90` cell** (straddle +0.130, and $133.8k of the
$158.6k): with `path_cap_days: 120` a >90-DTE straddle is closed at a
**mark-to-market at the cap** with substantial time value left, not at a
realized exit — `tef 0.75` on a 200-DTE position lands past the cap and never
fires. That cell is a valuation, not an outcome. Same blind spot recorded on
2026-07-27, now with real marks instead of BS ones.

### 2. Q2 — NULL, and the sign is the finding

    cell        corr(daily mean R)   CI95                worst-decile sleeve R
    POOLED           +0.268          [+0.081, +0.440]    +0.061  CI [-0.115, +0.248]
    straddle         +0.225          [+0.004, +0.446]    +0.093  CI [-0.122, +0.308]
    strangle         +0.258          [+0.060, +0.461]    -0.090  CI [-0.341, +0.192]
    calendar         +0.088          [-0.153, +0.248]    +0.336  CI [+0.124, +0.486]

The pre-registered gate wanted correlation **< 0**. It came back **positive with
a CI excluding zero** — the sleeve moves WITH the deployed ladder. Mechanically
this should have been predictable and is worth stating plainly so it is not
re-tested: **the sleeve is synthesized at the engine's own signal dates**, and
the engine signals on unusual flow, which is the same event that moves the
underlying. Buying a straddle there is not a different exposure from buying the
vertical the engine emitted — it is a **less efficient wrapper on the same
exposure**, which is exactly the 08-12 `bear_rewrap` result read from the other
side. On the deployed book's worst decile the pooled sleeve returns +0.061 with
a CI spanning zero: it is not there when the book needs it.

**Sizing note.** The mixing lines normalise the sleeve to ONE AVERAGE POSITION
per date (the date's mean $, not its sum). The synthesizer emits ~6× as many
rows per day as the ladder deploys, and summing them would compare a 14-position
sleeve to a 3-position book and call the size difference a hedge. Averaging is
choice-free; picking *which* structure to hold each day is a selection rule and
none is pre-registered. Per-structure "book alone" totals differ because each
structure covers a different subset of dates.

### 3. The calendar — the only thing that survives, and what it is not

Uncorrelated (+0.088, CI spans zero; on $ it is −0.020), positive on the
deployed book's worst decile (**+0.336, CI [+0.124, +0.486]**, n=13) and worst
quartile (**+0.287, CI [+0.102, +0.457]**, n=30), and it is the only cell in the
study that **reduces drawdown while adding return**:

    calendar dates (72 overlapping)     total        maxDD
    book alone                        $ 50,889     $ -7,878
    + 0.5 avg calendar position       $ 63,482     $ -6,860
    + 1   avg calendar position       $ 76,076     $ -5,979

**This is a CANDIDATE, not a finding, and the reasons are not decoration.**
(a) It is a **per-structure subgroup of a POOLED pre-registered gate** — the
exact post-hoc move this log has been burned by. (b) n=13 rows across 7 dates
carries the worst-decile number. (c) Its unconditional E is null (+0.054, CI
spans zero), so the claim would be "a structure with no measurable edge is worth
holding for its correlation" — plausible for a hedge, and precisely what the
2026-08-11 bear DEPLOY arm concluded about bear verticals, but it needs the same
treatment: a **pre-registered pick rule** (which calendar, which day, what size)
before any number is believed. (d) The calendar is also the structure the
synthesizer fails most often — 338 unpriceable, 191 of them because the far leg
has no bar on the shared entry day. A rule that can only be filled on the liquid
half of its candidates has a selection problem before it has an edge.

### 4. Q3 — the gate opened, and all three pre-registered conditions fail

Gate opened on Q1's pre-registered pass (correctly — the concentration screen
that kills Q1 is an addition, and letting it retro-close the gate would be
exactly the post-hoc reasoning the gate exists to prevent). Differences are
tested with a **date-clustered bootstrap of mean(selected) − mean(rest)**, added
because reading two overlapping one-sided CIs and calling the gap a difference
is not a test:

    POOLED (n=1293)                  n    meanE   vs rest   diff CI95
    vrp < 0 (implied cheap)         593   +0.134   +0.062   [-0.048, +0.191]
    earnings inside DTE             429   +0.161   +0.063   [-0.020, +0.212]
    iv_pct bottom tercile (<0.56)   380   +0.073   +0.105   [-0.148, +0.087]   wrong sign

**None of the three clears.** `vrp < 0` is right-signed in every structure but
calendar and never separates; `iv_pct` low is **backwards** — the pre-registered
direction is contradicted, which retires the "buy vol when it's cheap in its own
range" idea for this book rather than leaving it open. The one difference that
excludes zero is **calendar × earnings-inside-DTE: +0.356 vs −0.035, diff CI
[+0.111, +0.664], n=42** — same subgroup as §3, same status, and now the second
independent hint that the calendar deserves its own pre-registered study.

### 5. Infrastructure defect found and fixed (affects other studies)

`underlying_features.terciles()` filtered `None` but not `NaN`, and the book's
numeric columns come off pandas — **71 `iv_pct` cells arrive as `float('nan')`**.
Sorting them corrupted both cut points: the "bottom tercile" cut printed as
**0.92** and swept **69% of the population** into the "bottom third". Fixed to
filter non-finite values (cut is now 0.56, n=380 of 1,293). Any earlier read of
a tercile table on a NaN-bearing column is suspect; `vrp`/`rv20` and the other
OHLC-derived features are computed in-module and never NaN, so the exposure is
`iv_pct`-shaped.

### 6. What this closes and what it leaves open

- **CLOSED: the vol sleeve as a source of EDGE.** Straddle and strangle are
  two-window artifacts; the direction of the Q2 correlation says synthesizing
  vol on engine signal dates is a re-wrapping of the existing exposure, not a
  new one. Do not re-run this with more structures or more columns — the
  2026-08-11 ML null and this share a cause (the ceiling is in what the signal
  dates ARE, not in what is traded on them).
- **CLOSED: the "no evidence at all" state.** The counterpart scrape did its
  job — 481/481 groups, 100% reconstruction, real marks. The question was
  answerable and got answered.
- **OPEN, and the only thing worth running next: the calendar as a HEDGE**,
  pre-registered like the bear DEPLOY arm — a pick rule, a size, the D1–D5
  criteria, and the fill-rate problem in §3(d) treated as part of the test
  rather than a footnote.
- Unchanged: `config/backtest.yml`, `config/deployment-rules.md`, the prompt,
  every tab.

---

## 2026-08-12 — `vol_sleeve`: PRE-REGISTRATION (written BEFORE the run)

**Operator framing**, carried over from the `bear_rewrap` entry: *"bearish or
volatility plays should be added to diversify."* The bear arm answered its half
(bear is deployable as a HEDGE, not as selection). This is the vol half, and it
is asked in the same order: **does the structure pay at all → does it
diversify → and only then, when do you put it on.**

**Why it can be asked now.** It could not be before: the book is 96% directional
verticals, 21 of 1,607 plays classify as straddle/strangle, 3 ever reached
`BacktestResults`, and ZERO calendars have ever been priced. The blocker was
data, not analysis — a straddle needs a call AND a put at one strike/expiry, and
the cache was built from directional legs only, so it held a same-strike pair on
**15 of the 481 (ticker, expiry) groups the book entered (3%)**. The counterpart
scrape (`scripts/collector/fetch_counterpart_history.py`) closed that:
**1,322/1,337 mirrors cached, 481/481 groups (100%)**, all REAL Barchart marks
under the existing filename convention, so the same pricing path reads them.

### What is synthesized, and how (fixed before the run)

At every `(ticker, signal_date, expiry)` the pooled book (real + tweak, no `bs`)
actually entered, using `entry_underlying` as spot `S`:

| structure  | legs |
|---|---|
| `straddle` | long call + long put at `K*` = the cached strike nearest `S` |
| `strangle` | long put at the nearest cached strike **below** `S`, long call at the nearest **above** |
| `calendar` | short near-expiry call + long next-expiry call, both at `K*` |

Pricing is the production basis, not a new one: entry at the next session's
**Open** (falling back to that day's mark, then carry-forward), daily marks
carried forward per leg over `_weekday_grid` to `min(nearest DTE, 120)`, sizing
via `_size_contracts` on the shipped 50k/2% budget, and exits replayed through
the **frozen** `harness.replay` under `DEBIT_PROD` (pt .90 / sl .75 / tef .75).
Nothing about the exit engine is tuned in this study.

**Known basis caveat, stated up front:** the strike grid is *what the book
traded*, so "nearest strike to spot" is the nearest strike **flow touched**, not
the nearest listed. It biases toward strikes with real interest. The report
quotes the |K−S|/S distribution so the reader can see how ATM these actually are.

### The three questions, in order, with the gates

**Q1 — unconditional E by structure × DTE.** Mean `E` (held to cap) and `R`
(shipped exits) per structure and per DTE bucket (≤21 / 22–45 / 46–90 / >90),
with date-clustered bootstrap CIs and the per-year sign split.
*Non-null* = a cell with **n ≥ 30** whose mean E has a 95% date-clustered CI
excluding zero **and** the same sign in every year present.

**Q2 — date-level correlation with the DEPLOYED ladder.** The actual
diversification test, and the one that matters even if Q1 is negative: the
deployed book is `top_k_per_day(ladder_rank, k=3, eligible=A|B)` — the shipped
operator card — reduced to a daily series, against the sleeve's daily series on
overlapping dates.
*Non-null* = pooled daily correlation **< 0 with its bootstrap CI excluding
zero**, OR mean sleeve R on the deployed book's worst-decile dates **> 0** with
a date-clustered CI excluding zero. (This is the D2 test from `bear_deploy`,
applied to the vol sleeve.)

**Q3 — entry conditions. Runs ONLY if Q1 or Q2 is non-null**, and the conditions
are named here so they cannot be chosen after seeing the table: `vrp < 0`
(implied cheap against realized — the only time-series result in the reference
set), **earnings inside the DTE**, and **low `iv_pct`** (bottom tercile). If both
gates fail, the study prints the gate outcome and stops; that is a result, not a
failed run.

**Nothing in this study can ship on its own.** A vol sleeve that clears Q1 or Q2
becomes a candidate for the same treatment the bear sleeve got — a sized,
rules-bounded addition to the operator card — and would need its own deployment
arm first.

---

## 2026-08-12 — `bear_rewrap`: the WRAPPER is worth +0.085 and it does not hold in 2026; nothing ships

**Operator framing.** "The reference PDF study file does not have much impact.
Plan for testing more research/scenarios that make bear positions profitable —
and don't rely only on bullish movement; bearish or volatility plays should be
added to diversify." Scoping answers taken before the run: bear is judged on
**portfolio contribution**, not standalone E; counterpart-leg scraping is
authorised for the vol arm; new columns are **OHLC-derived only**.

**RECORDED DEVIATION.** The ship criteria were fixed in the approved plan
before the study was written or run, and are unchanged below — but this
`current.md` entry was written AFTER the run, not before it. Per the
pre-registration discipline that is a deviation and is recorded as one. No
criterion was added, dropped, or reworded post-hoc; the 2026 and tier cuts that
kill the headline are the ones the plan named.

**Provenance.** `backtests/study_output/bear_rewrap-latest.txt`, git 470b95f
(dirty), the 08-11 exports, `book.load_book(include_bs=False)` → 795 rows,
bear debit (`bear_put_spread` + `long_put`, non-credit) **n=332, real 168 /
tweak 164**. Read-only: no config, prompt, ladder or tab touched.

### 0. Why the PDFs underdelivered — it is not bad luck

Ten of the eleven reference papers are **cross-sectional** predictors validated
on decile sorts over thousands of names and decades. This book's effective
sample is the DATE count (~118). Of the three paper-derived column families
only `iv_spread` survived the 07-21 sweep; `price_vector` and `iv_pct` died as
composition. Paper 11 (forecasting volatility) is the only **time-series**
result in the set — the only kind a 118-date sample can test — and is the one
that was never implemented. It is now `vrp`, and that closes the reference set.
**Adding more columns of the first kind will keep producing nulls.** Recorded
so this is not re-litigated.

### 1. The composition problem, stated as a number

Classifying all 1,607 AnalysisClaude plays through `classify.py` on PRIMARY
text (Alt: sections stripped):

    bear_put_spread   596     straddle    12
    bull_call_spread  438     strangle     9
    bull_put_spread   328     calendar     0
    bear_call_spread   52     diagonal     0
    unsupported       152     butterfly / condor / iron_condor  0

**21 vol rows out of 1,607 (1.3%), of which 3 ever reached BacktestResults.**
The volatility sleeve is not underperforming — it has never been measured, and
no conclusion about diversification can be drawn from the current book. That is
what the counterpart-leg scrape is for.

### 2. The reconstruction gate — 332/332

Every substitution is a DIFFERENCE against a baseline replay, so the baseline
must be rebuildable from the cache by the same pricing code, or the difference
measures the re-pricer. Re-deriving each row's entry price and full daily mark
series from `option_history_cache` and comparing against the stored
`entry_option_price` / `daily_price_csv`: **332 of 332 reconstruct** (entry
within $0.005, ≥95% of days within $0.01). The baseline replays production
exactly — n=332, mean R −0.093, **−$37,951** — matching the 08-11 close-out
figure to the dollar.

Per-leg cache coverage is total: 165/165 bear_put, 128/128 bull_call, 85/85
bull_put real rows have BOTH legs cached. `long_put` needed no new data.

### 3. ARM W — the wrapper result

Same signal, same entry day, same shipped exit (base → structure_exit →
regime_exit, via `bear_giveback.prod_profile_for`). Only the structure differs.

    label        n     win   PF     meanR      $         MFE     MAE    gb    cap
    baseline    332    36%  0.76   -0.093   -37,951    +0.73   -0.82  1.13  -0.13
    long_put    326    33%  0.85   +0.002   -31,547    +0.87   -0.83  0.96  +0.00
    wider       200    38%  0.75   -0.056   -27,093    +0.88   -0.81  0.93  -0.06
    long_diag   153    34%  0.83   -0.050   -10,513    +0.70   -0.67  0.96  -0.07

**The mechanism reads exactly as predicted.** Dropping the short leg raises MFE
(+0.73 → +0.87) and drops give-back (1.13 → 0.96): the spread WAS selling away
the vol expansion that a down move brings. Mean R goes −0.093 → +0.002, paired
**dR +0.085**.

### 4. The gates — four pass, one fails, and the failure is broad

    long_put
      [PASS] CI excludes zero        dR +0.085  CI [+0.030, +0.139]
      [PASS] every LOO fold positive MIN +0.077 over 107 folds (share+ 100%)
      [PASS] both ex-window cuts     ex-2025-Mar-Apr +0.059  ex-2026-Feb-Apr +0.150
      [FAIL] sign-stable every year  2024 +0.135  2025 +0.158  2026 -0.026
      [PASS] right-signed both tiers real n=164 +0.073   tweak n=162 +0.098

`wider` and `long_diag` fail on four of five each and are dead.

**The 2026 failure is NOT one window**, which is what would normally rescue a
candidate here. Monthly: 2026-02 −0.061, 2026-03 −0.026, 2026-04 +0.088, and
dropping any single month leaves it negative (ex-Feb −0.010, ex-Mar −0.026,
ex-Apr −0.039). This is a broad regime change in the most recent year, not a
carrying date. Under the standing screen standard an effect that loses its sign
in a year present is a window artifact until proven otherwise — and here the
losing year is the CURRENT one, which is the worst possible year to lose.

**Dollars must not be quoted on this.** The tiers agree on R and disagree on
dollars (real +$14,837, tweak −$13,317). A substitution changes premium, hence
contracts under the production sizing formula, so $ carries a sizing effect
that R does not. Quote R.

### 5. ARM P — the chosen criterion, and it is NOT MET

P1 (worst-decile deployed dates) and P2 (correlation), the D2 tests:

    label       P1 n   meanR    CI              $         P2 corr   by year
    baseline     21   +0.108  [-0.335,+0.479]  +2,092     -0.109   -0.340/+0.019/-0.145
    long_put     21   +0.262  [-0.273,+0.730]  +9,450     -0.089   -0.228/+0.070/-0.505
    wider        13   +0.160  [-0.306,+0.527]  +2,505     -0.127
    long_diag    11   -0.121  [-0.689,+0.352]  -1,828     -0.084

**P1 is NOT MET for any wrapper, including the baseline.** The deployed ladder
has 90 dates, so the worst decile is **9 dates / 21 rows** — the CI is wide
because the sample is tiny, not because the point estimate is small. `long_put`
more than doubles the baseline's worst-date rescue (+0.108 → +0.262, $2,092 →
$9,450) and cannot demonstrate it. P2 passes pooled for every variant but is
not sign-stable by year (2025 positive for both baseline and `long_put`).

### 6. What this changes

- **Nothing ships.** `config/backtest.yml` and `deployment-rules.md` unchanged.
- **The wrapper hypothesis is CONFIRMED as a mechanism and REFUSED as a rule.**
  The vega story is real and visible in MFE and give-back; it stopped paying in
  2026. Those are both findings and the second one blocks the first.
- **B1's null is untouched** — this study never changed which signals were
  taken, only how they were expressed, so bear SELECTION remains closed.
- The 2026 breakdown is the open question, and it is a genuinely new one: what
  changed in 2026 such that buying the naked put stopped beating the spread?
  The `underlying_features` layer exists to ask that (a vol-regime shift would
  show in `rv20` / `vrp`), and it is the natural next arm.
- **`bear_rewrap` is re-runnable** as more 2026 dates land. If 2026 turns
  positive on a fresh window the candidate is back with all five gates clear;
  if it stays negative the wrapper question is closed for good.

### 7. New infrastructure landed with this

`scripts/backtest_study/underlying_features.py` (+ 25 tests) — pure functions
over `underlying.py` bars: `rv20`, `rv_parkinson`, `semivar_dn`, `atr14_pct`,
`eff_ratio`, `vrp`, `beta_spy60` / `corr_spy60`. Strictly as-of-entry.
**100% coverage on all 406 real book rows, all OHLC source.** Sanity: median
`rv20` 0.329, `vrp` **+0.011** — a small positive vol premium is the textbook
value and is the check that the decimal-fraction units were handled (a
points/fraction mixup reads ~+32 there).

`rv_parkinson` and `atr14_pct` are OHLC-only and carry a different denominator
from the rest; `coverage()` prints the split and every study using them must
quote it.

---

## 2026-08-12 — day-0 underlying move: ARM C does NOT clear, no rule ships; the sensitivity is STRUCTURAL

Study: `scripts/backtest_study/next_day_move.py` (new, tracked), on new data
infrastructure (`scripts/collector/fetch_underlying_ohlc.py`,
`scripts/backtest_study/underlying.py`, `tests/test_underlying_ohlc.py`).
Report: `backtests/study_output/next_day_move-latest.txt`. Inputs, quoted from
its header: BacktestResults 1,926 / BacktestProxy 4,533 / AnalysisClaude 11,836
rows (all 2026-08-11), spy_vix 802 (2026-08-12), git 470b95f, tree dirty. Book
**795 rows, real 406 / tweak 389**, bs excluded.

**Nothing shipped. No config changed.** The pre-committed null fired again.

### 0. What this asked, and the pushback it was given first

Operator's question: does the underlying's next-day move, and whether it goes
the play's way, separate structure and profits — reported by market regime,
structure and stock regime, with absolute and percentage moves and OHLC.

Pushback recorded before building, and it shaped the design:

- **The headline is partly tautological.** For a directional spread the
  underlying move IS the P&L driver. ARM C exists to test whether anything
  survives that, and ARM D is explicitly not read until it does.
- **This can never be a selection rule** — the move is unobservable at entry.
  D1 is not re-opened.
- **Absolute $ cannot be a bucket key.** $5 on a $600 stock and on a $20 stock
  are different events. Buckets key on % and on a **sigma-normalised** move
  (move ÷ the one-session move entry IV was pricing); $ is reported only.
- **`harness.py` is FROZEN**, so the rule is applied by COMPOSITION around
  `replay`, never by adding an exit mechanism.

### 1. Pre-registration status — a RECORDED DEVIATION

Every bucket, threshold, population and pass criterion was fixed in the module
header **before the first execution** and is visible there. **This log entry was
not written before the run**, which the standing convention asks for. The
constants are therefore pre-registered in code but not in prose; recorded rather
than glossed, because the whole value of the convention is that it is checkable.
Nothing was added to `RULE_THETAS` or the bucket lists after seeing output.

Two definitional errors WERE found and fixed mid-build, both before any verdict
was read, and both worth recording because they are the kind that silently
produce a clean-looking wrong answer:

1. **`iv_entry_pct` holds a decimal fraction, not IV points** (0.3295 = 33% IV;
   `simulate.py` writes the same sigma it feeds Black-Scholes). Treating it as
   points understated sigma 100x and put 579 of 764 rows in the two outermost
   buckets. Fixed and asserted in `test_sigma_1d_treats_iv_as_a_decimal_fraction`.
2. **The entry session was resolving to market holidays.** `_weekday_grid` is
   weekday-based and option marks carry forward, so Juneteenth 2024, the
   2025-01-09 mourning closure, Presidents' Day 2026 and Good Friday 2026 all
   looked like valid entry days — 23 of 795 rows. The repo has no holiday
   calendar (`trading_days` in scrape_flow is weekdays only), so the scraped bar
   series is now used as the calendar, bounded by `MAX_ENTRY_LAG_DAYS = 5` so a
   HOLE in the bars cannot silently anchor a fill a week late.

### 2. The data that did not exist before

Underlying OHLC was not on disk in any form — the `Open/High/Low` columns in the
option history cache are the OPTION's, and the only underlying series was a
single `Price~` per day read off SHORT legs only (blind to all 22 long-only
rows). `fetch_underlying_ohlc.py` now caches real stock bars per ticker, 104
tickers, ~999 daily bars each covering 2022-08 → present.

**The split gate is the part worth reading.** Barchart serves stock history
currently-adjusted; cached `Price~` was captured unadjusted. 6 of 104 tickers
disagree — and they disagree by *exactly* 2.000 (XLE), 5.000 (CVNA) and 10.000
(AVGO, MSTR, NFLX, SMCI), with AVGO and MSTR stepping 10 → 1 precisely at their
ex-dates. **A constant exact ratio is an adjustment; a wrong symbol could not
produce one.** That distinction is load-bearing: every window this study
measures is a RATIO off ONE series, so a constant factor cancels and those
tickers' percentage moves are perfectly valid. Only absolute dollars and
cross-series comparisons break, so the $ move is withheld on those 51 rows and
nothing else is. The initial design would have quarantined them — wrong, and
would have cost 51 rows for no reason.

Coverage: **787 of 795 rows usable**, 100% on real OHLC, the only exclusions
being the 8 vol structures (straddle/strangle) that have no direction to conform
to.

### 3. ARM D — the descriptive answer, and the finding that is NOT mechanics

Signed to the play, W0 = entry open → entry close:

    W0 (entry session)      n     win    PF    meanR        $     move
      stock CONFIRMED     349     54%   1.31   +0.161   +38,725   +1.79%  +0.66sig
      stock did NOT       415     47%   0.89   -0.046   -20,412   -1.69%  -0.62sig

Monotone in the sigma buckets too (−0.104 / −0.152 / +0.090 / +0.189 / +0.085
across against-1.5σ → confirmed-1.5σ). Taken alone this is exactly the
tautology warned about above.

**What is not tautological is that structures differ enormously in how much they
care**, which pure mechanics cannot explain — if the move were only driving the
mark, every directional structure would respond alike:

    structure            confirmed meanR   did NOT   spread
      bull_call_spread        +0.349        +0.308    0.041   <- nearly indifferent
      bull_put_spread         +0.387        -0.130    0.517   <- swings on it
      bear_put_spread         -0.044        -0.172    0.128
      bear_call_spread        -0.516        -0.608    0.092   (vetoed anyway, n=37)

`bull_call_spread` earns +0.308 mean R and a 60% win rate **on days the stock
went against it**. `bull_put_spread` — the 68%-win / PF-0.94 fat-left-tail
structure from the 08-12 reference stats — is where day-0 non-confirmation
actually costs money. Same pattern in the stock-regime cut: `stock_dir = BEAR`
is indifferent (−0.180 vs −0.213) while `stock_dir = RANGE` swings +0.310 →
−0.163.

### 4. ARM C — the confound control, which does NOT clear

Holding day-0 mark P&L roughly constant and re-running the conformity cut:

    band                       n    confirmed meanR   did NOT   gap
      day-0 P&L <= -25%       93        +0.033        -0.335   +0.368
      day-0 P&L -25% to 0    311        -0.133        -0.109   -0.024
      day-0 P&L 0 to +25%    292        +0.215        +0.019   +0.196
      day-0 P&L > +25%        91        +0.253        +0.824   -0.570

**The sign flips twice.** ARM U's peak-time gradient survived this test inside
fixed peak bands; the day-0 version does not. In the largest band (−25% to 0,
n=311) the readable cells are flat (−0.121 / −0.079 / −0.104), and in the
most-green band the FLAT bucket (+0.714, n=31) beats the confirmed one (+0.206,
n=40). Per the pre-committed reading in the module docstring, that is **no
rule**, and ARM D is not promoted past "description".

### 5. ARM R — the rule, measured anyway, and it misses

Baseline is the SHIPPED merge. It reproduces bear debit at **mean R −0.093 /
−$37,951** — bit-identical to `bear_giveback` ARM P's published calibration, so
the replay is anchored. Credits were routed to `CREDIT_PROD` (pt 0.65, no stop)
after checking `config/backtest.yml`, which states the structure_exit and
regime_exit merges are debit-only: a first cut had them on debit knobs, which
would have been exactly the "baseline production does not run" error this log
has recorded twice.

    bear debit (n=332)                      meanR   Dship   CI95              LOOmin       $   chg
      SHIPPED                              -0.093   +0.000                          -37,951      0
      cut when wrong sign                  -0.031   +0.062  [-0.016, +0.139]  +0.055  -14,910    170
      cut when worse than -0.5 sigma       -0.075   +0.018  [-0.033, +0.068]  +0.010  -32,910     90
      cut inside the flat band (+0.5 sigma) -0.002   +0.091  [-0.002, +0.184]  +0.081   -2,961    234

The flat-band variant nearly erases the bear bleed (−$37.9k → −$3.0k) and passes
criteria 2–6: every LOO fold positive, ex-Mar–Apr-2025 +0.156, ex-Feb–Apr-2026
+0.105, all three years positive, both pricing tiers positive, leak guard 0.

**It fails criterion 1 by 0.002** — the CI lower bound is −0.002. And its year
split is **2024 +0.258 / 2025 +0.029 / 2026 +0.069**: 20% of the rows carry the
majority of the effect, the same one-window signature that has killed candidates
four times in this log. **Whole book and all-debit are negative on every
variant**, so the effect does not generalise past bear either.

Leak guard was made non-vacuous deliberately: the bear-keyed cut is run over the
WHOLE book with the keying evaluated INSIDE the wrapper, not by pre-filtering
the row list — pre-filtering would make it impossible to fail. 0 non-bear rows
changed on all three thresholds.

### 6. A clean null worth keeping: the next-open entry basis costs nothing

WG (signal close → entry open) is not tradeable — it is already inside the fill
— but nobody had priced it. Gaps split 391 the play's way / 396 against, at
+1.36% and −1.22%, for an **overall mean of +0.06% (−0.01 sigma)**. Outcomes
barely separate (+0.056 vs +0.004 mean R). The `entry_timing: next_open` basis
adopted on 2026-07-06 is not systematically feeding the book a worse price.

### 7. Actions

- **No rule change**, no config touched. ARM C failing is the gate working.
- **The flat-band bear cut is a CANDIDATE, not a finding** — post-hoc favoured,
  CI includes zero, 2024-carried. Re-evaluate only on new bear rows, and only
  against SHIPPED production.
- **New watch: `bull_put_spread` day-0 sensitivity.** The 0.517 spread is the
  largest structure effect in the table and lands on the structure already known
  to carry a fat left tail. It is exit-side and unproven; it is NOT a licence to
  re-open selection.
- **`bull_call_spread` earning +0.308 on non-confirming days** is worth
  remembering the next time a directional read is used to justify holding or
  cutting one — that structure's P&L is not primarily riding day-0 direction.
- **Infrastructure is reusable:** `underlying.py` gives any future study real
  OHLC with a documented fallback, and recovers the long-only rows
  `harness.Trade._load_underlying` cannot see. `harness.py` was NOT touched.

---

## 2026-08-12 — the `be_after` grid RUN: does NOT ship, and the give-back pattern is in the UNDERLYING

Study: `scripts/backtest_study/bear_giveback.py` (new, tracked) plus four
pre-registered entries added to `bear_arm.py`'s `DEBIT_GRID`. Reports:
`backtests/study_output/bear_arm-latest.txt`,
`bear_giveback-latest.txt`. Inputs: BacktestResults 1,926 / BacktestProxy 4,533 /
AnalysisClaude 11,836 rows, spy_vix 802 (git 470b95f, tree dirty). Book **795
rows, real 406 / tweak 389**, bs excluded. Bear debit n=332.

**Nothing shipped. No config changed.** The pre-committed null fired.

### 1. Against the STUDY baseline every threshold beats @.50 — and it means nothing

`bear_arm.py` grades against `DEBIT_PROD` (pt .90 / sl .75 / tef .75, no trail):

    variant              meanR    ΔPROD    CI95              LOOmin       $
    PROD                -0.133   +0.000                              -54,404
    BE ratchet @.50     -0.092   +0.041  [+0.016, +0.065]    +0.038   -37,961
    BE ratchet @.40     -0.084   +0.050  [+0.020, +0.079]    +0.046   -34,540
    BE ratchet @.30     -0.066   +0.068  [+0.030, +0.105]    +0.062   -27,494  <- best
    BE ratchet @.25     -0.066   +0.067  [+0.020, +0.112]    +0.061   -27,677
    BE ratchet @.20     -0.072   +0.062  [+0.009, +0.112]    +0.056   -29,317

@.30 clears CI, LOO, both pricing tiers (real +0.083 / tweak +0.052), all three
years positive (+0.133 / +0.065 / +0.036) and ex-Mar–Apr-2025 (+0.058, CI
excludes zero). On the study's own terms it is a better rule than the shipped
one, halving the bleed instead of cutting it 31%.

**It is still not shippable, because production does not run that baseline.**

### 2. Against SHIPPED PRODUCTION it collapses — and the CI includes zero

`bear_giveback.py` ARM P replays the real merge (base → `structure_exit` →
`regime_exit`, i.e. the BEAR_HE 0.50/0.50 trail with `be_after` nulled there).
**Calibration check first: the replay reproduces the shipped book exactly —
mean R −0.093, −$37,951, the same figures the 08-11 close-out measured.**

    variant                            meanR   Δshipped   CI95              LOOmin       $   rows chg
    SHIPPED  be .50, suppressed       -0.093    +0.000                              -37,951       0
    be .40, suppressed                -0.093    +0.001  [-0.010, +0.010]   -0.001   -37,565       6
    be .30, suppressed                -0.085    +0.009  [-0.006, +0.024]   +0.006   -34,535      13
    be .25, suppressed                -0.083    +0.010  [-0.008, +0.029]   +0.007   -34,190      18
    be .20, suppressed                -0.084    +0.009  [-0.014, +0.031]   +0.004   -34,329      22
    be .30, STACKED in BEAR_HE        -0.067    +0.026  [-0.003, +0.056]   +0.020   -27,607      43
    be .25, STACKED in BEAR_HE        -0.067    +0.026  [-0.015, +0.066]   +0.020   -27,930      62
    be .20, STACKED in BEAR_HE        -0.074    +0.019  [-0.030, +0.066]   +0.014   -29,899      82

**Not one variant clears. Every CI includes zero.** The best (be .30 stacked,
+0.026) is 38% of its study-basis delta, and its year split is
**2024 +0.097 / 2025 +0.009 / 2026 +0.007** — one year carries it, the
Mar–Apr-2025 failure pattern for the fourth time in this log.

**Leak guard PASSED** — non-bear debit (n=261) and credit (n=202) both **0 rows
changed**, as the structure keying requires.

**Verdict: the +0.068 was an artifact of grading against a baseline production
does not run.** The 08-11 lesson repeats, and this is now the *second* time it
has changed a decision. Quoting both baselines is not hygiene, it is the test.

### 3. A CORRECTION to the 08-12 proposal entry, and to A3's scope

The proposal above predicted *"the overlap will be larger, not smaller"* at a
lower threshold. **That was wrong, and backwards in an interesting way.**

- The like-for-like swap (threshold down, BEAR_HE **suppression kept**) changes
  only **13 rows** and is worth +0.009. Almost nothing, because outside BEAR_HE
  most bear rows that peak above +0.30 also peak above +0.50.
- The gain only appears when the ratchet is **STACKED** inside BEAR_HE (43 rows
  changed, 30 of them in that cell) — because a ratchet at 0.30 arms on rows
  peaking in [0.30, 0.50) where the trail never arms at all.

So **A3's suppression decision was correct for @.50 and does not generalise**:
@.50 is strictly dominated inside BEAR_HE, @.30 is not. Recorded because the
config comment currently states the domination as if it were a property of the
ratchet rather than of that specific threshold. **The stack is a genuinely
different rule from the one pre-registered**, its CI includes zero, and it is
2024-carried — so it is a CANDIDATE, not a finding, and it is post-hoc.

### 4. ARM U — the give-back IS separable, and the signal is the underlying

301 of 332 bear rows have cached underlying history; 245 ever green. Features
below are observable **in flight**; this is exit management, not selection.

    by DAYS TO PEAK (green rows)      n    give-back   meanR   meanPeak      $
      peak within 3d                 29        90%    -0.549    +0.33   -16,195
      peak 4-8d                      27        81%    -0.401    +0.58   -10,270
      peak 9-20d                     67        42%    +0.254    +1.09   +20,496
      peak >20d                     122        46%    +0.198    +1.10   +25,576

    by UNDERLYING MOVE AT PEAK        n    give-back   meanR   meanPeak      $
      stock -6% or worse            123        36%    +0.387    +1.22   +52,622
      stock -3% to -6%               38        58%    -0.064    +0.75      -953
      stock -1% to -3%               30        77%    -0.211    +0.98    -4,830
      stock flat/up                  54        80%    -0.452    +0.46   -27,232

**Both gradients are monotone.** The headline separation: rows that gave it all
back had the stock down **−4.7%** at their peak; rows that held a gain had it
down **−10.4%**. An early peak on a barely-moved stock is an IV pop, not a
directional move, and it does not survive.

**The confound was controlled, and the effect survives.** "Stock fell more" could
just be "spread is deeper ITM, of course it wins" — so the cut was repeated
inside fixed peak bands:

    [peak +25% to +75%]  n=78     give-back   meanR        $
      stock -6% or worse    28        54%     -0.220    -7,071
      stock -3% to -6%      18        83%     -0.503   -10,103
      stock -1% to -3%      14       100%     -0.692   -10,026
      stock flat/up         18        94%     -0.669   -14,444

At a *held-constant* peak level the gradient is still there, so it is the
underlying and not the moneyness. Two positions both up 50% are not the same
position. The +75–150% band agrees (24% → 75% give-back) on thin cells; above
+150% it flattens, but everything wins there.

**A second, blunter read of that same table: the entire +25–75% peak band is
negative in all four buckets, −$41.6k over 78 rows.** A bear debit whose peak
tops out in that band is a loser regardless of what the stock did. That is not
directly actionable — at +40% you do not know it is the peak — but it is the
cleanest statement yet of *where* the bleed lives.

### 5. What would make this a rule — and why it was NOT built

The candidate is an **underlying-conditioned ratchet**: tighten to breakeven when
green but the stock has not confirmed; leave it alone when the stock has moved
≥6%. It is better-motivated than a flat lower threshold because it targets the
mechanism instead of the symptom.

**It requires a new mechanism in `harness.py`, which is FROZEN**, and the frozen
grid exists precisely so B2 cannot become a parameter hunt. Building it is an
operator decision, not a study decision. If it is taken:

1. Pre-register before implementing: threshold on underlying move, ratchet level,
   and the standing criteria (CI vs **SHIPPED PRODUCTION**, ex-Mar–Apr-2025,
   2026 alone, every LOO fold, both pricing tiers, leak guard).
2. Note in advance that the confound-controlled cells are **n=14–28**. This is
   powered to see a large effect and nothing else.
3. The 2024-carried year split on the stacked variant is a warning that this
   region of the book is where one window can dominate.

Pre-committed reading if it does not clear: **bear give-back is structural** —
the mirrored |MAE|/MFE ≈ 1.25 signature is what a bad selection looks like from
the exit side, and the answer stays the hedge sleeve (≤ ½ size, `|delta|`
descending), not a better stop.

### 6. ARM S — deployment reference stats

Descriptive in-sample summaries added for the operator card; moved to
[`deployment-evidence.md`](deployment-evidence.md) §"Deployment reference stats".
Profit factor = gross winning $ / |gross losing $| on realized R. Headline: the
ladder is **monotone in profit factor** (A 2.29 / B 1.78 / C 0.79 / VETO 0.34),
and `bull_put_spread` posts **68% win at PF 0.94** — the fat-left-tail problem
in one number, and the reason win rate alone must never be the deploy criterion.

---

## 2026-08-12 — edge status after close-out: real, narrow, NOT selection-tunable

**Question (operator):** reading this log it looks like there is no measurable
edge — is it a matter of fine-tuning the selection, or is the whole engine not
worth pursuing?

No new run. This is a verdict entry over the existing record, written because
the same question was asked on 07-21 and the answer has since changed in one
direction (selection is now closed, not merely unpromising) and hardened in
another (the edge reproduced on a completed third year).

### 1. The premise is wrong: there is an edge, and it is one cell

Real+tweak, bs excluded, from the 08-11 exports:

    structure          n     E        R        $          every year?
    bull_call_spread   338  +0.672   +0.295   +$80,237   YES (+0.44/+0.66/+0.29)
    bull_put_spread    237  +0.183   -0.005    -$1,946   no
    bear_put_spread    468  -0.528   -0.081   -$44,000   negative every year
    bear_call_spread    43  -1.240   -0.518   -$11,221   intake-vetoed

Ladder tiers reproduce out of sample in all three years (A +0.708/+0.670/+0.305,
B +0.338/+0.644/+0.431, C and VETO negative throughout). Top-3/day replay
+$22.7k / +$44.8k / +$8.8k at 64–67% win.

**The load-bearing framing: taking every emitted play makes +$14.0k over three
years** (−$14.4k / +$47.9k / −$19.5k). The engine emits ~10 plays/day and the
ladder discards ~70% of them to capture 83% of the P&L. **The value is in the
triage, not the generation.** The honest claim remains 07-21's: *the analysis
picks good bull_calls in elevated-vol range markets.*

### 2. Selection tuning is closed — three independent nulls

This is the part of the question the log can now answer definitively, where on
07-21 it could only say "unpromising":

- **496 pre-registered bear subsets → 0 survivors** (~10 expected by chance),
  re-run under the new exit. Best subset still negative.
- **ML combination search, 15 model×strategy cells → 0 positive gains with a CI
  excluding zero.** Best cell +0.022, CI [−0.017, +0.071].
- **Full column sweep → only `delta`/`dte` (bull_put) and `iv_spread`
  (bear_put) are decision-relevant.** `cpir`, `oi_confirm_pct`, `iv_pct`,
  `score_total` all looked predictive pooled and vanished within structure —
  the same composition trap caught four separate times.

The ML ablations put the binding constraint in the **columns, not the
estimator**, and the full-sample tree's root split is `structure = bull_call` —
the model rediscovers the ladder unprompted. **Further selection work on this
feature set has a measured expected value of zero.** The standing gate holds:
re-open on new COLUMNS, never on new models or new tuning of old ones.

### 3. What is actually unresolved is execution, and it is not accruing

Latest live-loop mapping (`stage1_report_2026-08-12.md`): **EXACT 0 /
STRUCTURE 2 / SUBSTITUTED 1 / NONE 15.**

Zero exact matches. The mapped fills are NVDA/TSM short-call overlays, MU and
GOOG round-trips, and a GLD `bull_call_spread` expiring 2027-01-15 (~155 DTE —
outside the ≤60-DTE band the ladder is validated in). **The book being traded
and the book the engine emits are close to disjoint.**

This is why "confirmed in backtest, not proven live" has not moved since 07-21.
Not because the live evidence came back bad — because there is none. Recording
it plainly: with backtest tuning closed, the live loop is the *only* experiment
in the system, and it is currently not running. Either Tier A/B top-3 gets
traded as emitted for ~30–50 positions, or the ladder stays backtest-confirmed
permanently. No further analysis resolves this.

### 4. Verdict, and one question the log has never asked

**Worth pursuing — but as a narrower instrument than the build implies, and the
pursuit is no longer backtest tuning.** A triage rule that turns +$14.0k of raw
emission into +$76k of top-3 P&L across three years is real work.

Standing caveats that keep "proven" out of it, unchanged: Tier A partly encodes
the RANGE/E-VOL cell that generated the profit (circularity mitigated by the
time split, not eliminated); rows within a date share a market path so the
p-values are optimistic; 25% proxy-priced; next-day-open on settlement-derived
pricing with no slippage model.

**Open question, flagged NOT tested:** does the LLM earn its keep? The ladder is
structure × regime × entry-geometry — entirely deterministic and computable
without a model. The ML study benchmarked estimators against the ladder *on the
plays the engine emitted*; it never tested engine-vs-no-engine. If the model's
real contribution is ticker/strike choice within a structure×regime cell, that
is testable against a mechanical baseline (e.g. bull_call spread on the
highest-flow-volume RANGE/E-VOL name). Logged as a candidate, with the warning
that it needs a pre-registration before anyone looks at a number — it is the
kind of question whose answer is easy to talk oneself out of.

---

## 2026-08-12 — bear MFE give-back: the shipped ratchet cannot reach 124 rows / −$77.2k

**Operator observation:** bear positions still show MFE, but most of it is
given back. **Confirmed, and larger than the log recorded.**

**Provenance.** Read-only scratch cut, same 08-11 exports as the bear arm
(`backtests/to_evaluate/`), `book.load_book(include_bs=False)` → **795 rows,
real 406 / tweak 389**. Bear debit = `bear_put_spread` + `long_put`, n=332 —
the same population the `be_after: 0.50` ratchet was measured on. No config,
prompt or ladder touched. Not run through `scripts/backtest_study/`, so this is
a scratch finding pending a proper study, not a shipped conclusion.

### 1. The give-back is the dominant bear failure mode

    population              n     rows ever green   full give-back   median capture
                                  (MFE > +1%)       (MFE>0, R<=0)    (R / MFE)
    bear debit             332    272  (82%)        152 of 272 (56%)     -0.55
    bull_call (comparator) 240    223  (93%)         80 of 223 (36%)     +0.42

**82% of bear rows go into profit at some point; 56% of those finish at or below
zero.** The median bear position that was ever green ends up losing *more than
half its peak, as a loss*. The comparator keeps +0.42 of its peak.

On the 152 full-give-back rows: realized **−$123.4k**, against **+$81.4k** if
each had been sold at its own MFE. That gap is not achievable — nobody sells at
the peak — but it sizes the pool the exit is fishing in.

### 2. The bleed sits entirely below the arming threshold

    MFE band                            n    mean R   win    $
    <= +1%  (never in profit)          60    -0.736    0%   -55,938
    +1% to +25%                        71    -0.585   15%   -45,289
    +25% to +50%  <- ratchet CANNOT arm 53    -0.545   17%   -31,916
    +50% to +90%  <- ratchet arms      46    -0.385   28%   -21,756
    >= +90%  (target zone)            102    +0.889   85%  +104,822

**124 rows peaked between +1% and +50% and lost −$77.2k. Every one is below
`be_after: 0.50`.** The shipped ratchet fires on 16 production rows; this band
is untouched by design.

Corroborated by the exit mix — `stop_loss` (n=109, mean R −0.786) carries mean
MFE **+0.217**, and `dollar_stop` (n=69, mean R −0.765) carries mean MFE
**+0.287**. **178 bear positions were up 20–30% and stopped out anyway.** That
is the operator's observation, stated as a number.

### 3. What this does NOT establish — read this before proposing a threshold

A lower threshold is the obvious move and it is **not yet supported**. What was
computed is a *census of peaks*, NOT a replay:

    peak >= X    rows arming   still finish negative   $ realized on those
      0.20           217              105                  -86,365
      0.25           201               92                  -75,102
      0.30           188               79                  -63,671
      0.40           162               58                  -46,707

**This table says only how many rows had a peak that high and lost anyway. It
does not say a ratchet would have saved them.** The missing half is the cost on
winners: the 102 rows in the ≥+90% band earning +$104.8k include an unknown
number that dipped back through entry *after* passing +0.25 and would have been
sold at breakeven. That is exactly the mechanism that made the identical config
destroy value on the non-bear debit book (+0.234 → +0.209). MFE/MAE cannot
resolve it — only a path replay can.

Also: **60 rows (−$55.9k) were never in profit at all.** No exit rule reaches
them. That is D1's unfixable selection problem, and it caps what any exit work
can recover.

### 4. Proposed follow-up — bounded, and pre-registered before it runs

This is an **exit** question, the one dimension the log has not closed (B2 found
a fix of exactly this class). It is a grid extension, not a new mechanism:

- Add `be_after` at **0.20 / 0.25 / 0.30 / 0.40** to `bear_arm.py`'s
  `DEBIT_GRID`, bear-debit keyed, through the FROZEN harness. Four named
  configs, not a search.
- **Quote both baselines** — `DEBIT_PROD` *and* shipped production (with the
  BEAR_HE trail live). The 08-11 lesson is that the study framing overstated
  production impact 3× because the trail was already buying the same rows; at a
  lower threshold the overlap will be *larger*, not smaller.
  **[WRONG — corrected by the run entry above. The overlap does not grow: a
  ratchet below 0.50 arms on BEAR_HE rows the trail never reaches, so the
  like-for-like swap changes only 13 rows while the gain requires STACKING,
  which is a different rule than the one pre-registered here.]**
- Ship criteria, same as the 08-11 ratchet: pooled date-clustered CI excludes
  zero, ex-Mar–Apr-2025 positive, 2026 alone positive, every LOO-by-date fold
  positive, right-signed in both pricing tiers.
- **Leak guard is mandatory and is the likely killer** — the non-bear debit book
  must be unchanged. A threshold low enough to catch the +25–50% band is low
  enough to start cutting bull_call winners if the keying ever slips.
- Pre-commit: **if no threshold clears, the answer is that bear give-back is
  structural** — the mirrored |MAE|/MFE ≈ 1.25 path signature is what a bad
  selection looks like, and the correct response is the existing hedge-sleeve
  framing (≤ ½ size, `|delta|` descending), not a better stop.

Nothing shipped. `config/backtest.yml` and `deployment-rules.md` unchanged.

---

## 2026-08-12 — live loop promoted to tracked code, and its fill mapper put under test

The close-out entry left this open as a known gap: **`backtests/live_loop/` is
UNTRACKED.** `.gitignore` excludes `backtests/*` and its own comment calls that
tree disposable scratch that "gets deleted periodically" — yet
`stage1_map_fills.py` was 33KB of real code and, with backtest tuning closed, the
**only source of new evidence in the system.** Exactly the mistake the 08-11
refactor fixed for study code by moving it to `scripts/backtest_study/`.

Moved to **`scripts/live_loop/stage1_map_fills.py`**; runs as
`python3 -m scripts.live_loop.stage1_map_fills`. `ROOT = parents[2]` still
resolves to the repo root at the new depth (the stale-ROOT bug that broke 7
studies in the 08-11 move does not recur here — checked, not assumed). Data stays
under `backtests/live_loop/`, which is the correct split: tracked code, disposable
data. Output reproduces exactly — **EXACT 0 / STRUCTURE 2 / SUBSTITUTED 1 /
NONE 15**.

**`tests/test_live_loop.py` — 38 tests**, with the IBKR snapshot copied to
`tests/fixtures/` so it survives a `backtests/` wipe. The 08-11 mis-labelling bug
(`long_call` and `bull_call_spread` both mapping to `debit`, so naked fills were
tallied as STRUCTURE matches) was found **by reading, not by a test**, and its
failure mode is silent — a mislabelled fill does not raise, it quietly corrupts
the evidence base. Now pinned: the `DIRECTION` gate, the
`EXACT ≺ STRUCTURE ≺ SUBSTITUTED` ranking (both row orders), and the ladder port.

**Writing the tests surfaced a seam worth recording.** `classify_structure()`
emits `"single long call"` (spaces) for naked legs but `"bull_call_spread"`
(underscores) for verticals, and `_live_to_canonical()` matches on the spaced
form. Any label that canonicalises to `"unknown"` matches no play and drops to
**NONE — indistinguishable from "no play that day"**, which is precisely the
silent-drop failure the 07-27 entry described and the 08-11 entry corrected for a
different branch. The vocabulary is now pinned by a parametrised test rather than
trusted, including that genuinely unpinnable round-trip closes stay `"unknown"`
instead of guessing.

Still open from the close-out list: `scripts/chart_backtest.py:55-76` re-derives
exit config and knows about neither `regime_exit` nor `structure_exit`.

---

## 2026-08-12 — v4 bridge: RECORDED DEVIATION from the pre-registration (written BEFORE the run)

Amends the [pre-registration below](#2026-08-11--v4-emission-composition-bridge-pre-registration-written-before-the-run).
**Nothing has been run.** Written now, while no v4 result exists, because a
deviation decided after seeing numbers is not a deviation, it is a choice.

**What changes: the ~20 re-runs are dropped.** The pre-registration called for
running the v4 prompt over ~20 dates already covered by v3, writing to a scratch
tab. Those are ~20 headless analysis calls, and analysis is the expensive step in
this system. They are also avoidable.

Measured state of the v4 tabs today: **`AnalysisClaude` = 10 rows on one date
(2026-08-11); `AnalysisGPT` = 0.** v4 accrues ~10 rows/day from the normal daily
cadence at no marginal cost, so **~20 dates arrives in roughly four weeks of
changing nothing.**

Checked first, for the record: nothing cached would let a v4 row be reconstructed
for an old date. The pipeline persists the deterministic rollup
(`audit/<date>-rollup.csv`) but sends LLM output straight to Sheets, so a v4 row
on a v3 date genuinely costs a fresh run. There is no copy-paste shortcut.

**What this costs, stated in advance.** Accumulated v4 dates will not overlap v3
dates, so the five tests lose their **date pairing**. Substitute: match on
**`mech_cell`**, a `ROW_COLUMNS` field backfilled across both eras, which encodes
the tape conditions date-pairing was buying.

**Pre-committed caveat, stronger than the original's.** mech_cell matching is
coarser than date matching — it controls for regime, not for the specific day's
flow. Combined with the original's own admission that ~20 dates is thin for a
five-way composition test, this is powered to catch a shift the size of the
v2→v3 credit jump (19% → 34%) and **nothing subtler**. A null result here means
"no large shift detected", never "the populations are the same". Do not let a
null be quoted later as validation.

**Unchanged, and not renegotiable after the numbers land:** the five tests
(structure mix, credit share, plays/day, bear share, ladder tier mix) and the
decision rule — within noise → the v3-derived ladder carries forward; any of the
five shifts → the ladder is UNVALIDATED on v4, keep deploying under v3 rules and
flag every v4 row here.

**Escape hatch, bounded.** If four weeks of tape produces no BEAR or H/E-VOL
date, re-run **≤5** v3-covered dates chosen to fill that specific empty cell —
targeted, and only on evidence the cell is missing. Running `--engine codex`
daily would also double the accrual rate but samples a different engine
population; noted, not recommended.

Interim posture is already what the pre-registration says: deploy under v3 rules.
This is now stated on the operator card itself rather than only here.

**The study is written and gated: `scripts/backtest_study/v4_bridge.py`.** Written
today, while v4 had 10 rows on one date — so nothing in it can have been tuned to
a result. It refuses to produce numbers until the gate is met:

- `MIN_V4_DATES = 20` → exits **rc=2** with the shortfall and the interim posture.
- **Era guard** → exits **rc=3** if the two exports are not v3-then-v4. Era is
  detected from the *schema* (`score_flow`/`score_dealer` present = v3), never
  the filename, because the in-place `vN_` rename leaves both eras exporting as
  "AnalysisClaude" and they are trivially swapped. Run today it correctly aborts
  with *"refusing to compare a book against itself and call the null a
  validation"*.
- v3 is **reweighted to v4's mech_cell mix** (direct standardisation), so a
  difference in regime composition cannot masquerade as a difference in
  behaviour — the specific hazard the date-pairing deviation introduces.

`tests/test_v4_bridge.py` (16 tests) proves the machinery before it ever runs on
real data: both gates fire, `MIN_V4_DATES`/`ALPHA` are pinned at their
pre-registered values, **a v2→v3-sized credit jump (20% → 35%) is detected**, and
standardisation collapses a deliberately confounded 90%-LVOL-vs-50/50 pair to
identical shares while the raw shares differ by >10pts. A study that cannot see
the shift it was built for is not worth waiting a month for.

One divergence from `book.ladder_tier()`, documented in the module: |delta| and
DTE are not columns on an analysis row, so the Tier-B bull_put geometry clause
cannot be evaluated and every bull_put falls to C. That biases the tier mix
**identically in both eras**, which is all a composition comparison needs — but
these tier shares must never be quoted as deployment shares.

---

## 2026-08-12 — deployment rules split: operator card vs evidence

`config/deployment-rules.md` had grown to 284 lines by accretion — every study
that shipped a rule appended its derivation, CIs, LOO folds, limits and rollback
trigger to the same file, so the ~15 things an operator actually does at deploy
time were interleaved with ~200 lines of research record. With v3 tuning closed,
the rules have stopped churning and the doc is stable enough to freeze.

- **`config/deployment-rules.md`** → instructions only, ~110 lines, as a
  deploy-day sequence: before-you-deploy → VETO → tier → order-entry geometry →
  hedge sleeve → exits → what not to use.
- **`config/backtest-tuning/deployment-evidence.md`** (new) → everything else,
  moved with the numbers intact. Nothing was dropped; the diff is a move.

**Three defects fixed in passing, all found by reading the doc against the code:**

1. **Stale command.** The card told the operator to run
   `python3 backtests/mech_regime/fetch_spy_vix.py --full`. That path is
   untracked scratch — the tracked fetcher has been
   `scripts/collector/fetch_mech_regime.py` since the mech-regime move, and
   `make analyze` already depends on the `mech-regime` target. Now just
   `make analyze`.
2. **Hand-computed regime label.** The card still spelled out "SPY < 50-day SMA
   and 20-day return < 0" as an operator step. `mech_cell` has been a
   `ROW_COLUMNS` field and backfilled across the analysis tabs since the 08-11
   addendum — the card now says *read the column*, and the definition moves to
   the evidence file as reference. This was a live opportunity to mislabel a
   date by hand.
3. **Exit rules split across three sections.** "Preconditions", "Exit
   management" and "Bear debit spreads — breakeven ratchet" each held part of
   the exit config, so setting up an order meant reading all three and
   reconciling the BEAR_HE suppression clause yourself. Now one four-row table
   (debit normal / debit BEAR_HE / bear debit / credit) with the suppression as
   an explicit footnote.

The `## Exit management` heading is **preserved verbatim** — six places link to
`deployment-rules.md §"Exit management"` (`config/backtest-reference.md`,
`scripts/backfill_mech_cell.py`, `scripts/collector/fetch_mech_regime.py`,
`scripts/analysis_pipeline/config.py`, `scripts/analysis_pipeline/core.py`,
`.github/workflows/backfill-mech-cell.yml`), and keeping the heading is cheaper
than updating six references.

**The three open rollback triggers are now in one table** in the evidence file
rather than scattered across three sections — BEAR_HE trail (≥25 new affected
dates), bear-debit `be_after` (≥60 new rows that arm it), bull_put band
(PROVISIONAL). They are live pre-registered commitments and were the easiest
thing in the old doc to lose. **Silence is not "not met" — check the numbers.**

No rule changed. No config changed. This is a documentation move.

---

## 2026-08-11 — v3 CLOSE-OUT: three findings SHIPPED, and the production delta is a third of the study's

v3 is closed. The trigger was not fatigue — it is that **no question left in the
queue is answerable from this book**. The ML combination search returned a null
result in all 15 model×strategy cells and its ablations put the binding
constraint in the *columns*, not the estimator; the Feb–Apr 2026 holdout is
complete; the ladder is monotone in every cut. What remained was shipping.

### 1. SHIPPED — `be_after: 0.50`, bear debit only (`simulation.structure_exit`)

Implemented in `scripts/backtest/simulate.py`: a `be_stop` branch in
`_summarize_path` between `dollar_stop` and `stop_loss` (ported from the frozen
harness ordering), plus `_structure_override()` keyed on
`bear_put_spread`/`long_put` with `entry_net >= 0`. Merge order for debits is
**base → structure → regime**.

**A3 — the pre-registered interaction check, and a recorded deviation from the
frozen grid.** One entry was added to `bear_arm.py`'s `DEBIT_GRID`:
`"BE @.50 + trail .50 trig .50"`. One named config, not a search.

    trail .50 trig .50            -0.098  +0.036  [+0.006,+0.063]  LOO +0.032
    BE ratchet @.50               -0.092  +0.041  [+0.016,+0.065]  LOO +0.038
    BE @.50 + trail .50 trig .50  -0.098  +0.036  [+0.006,+0.063]  LOO +0.032

The stacked cell is **bit-identical to the trail alone, with zero `be_stop`
exits**, and below BE alone. The cause is structural, not sampling: the trail
arms at peak ≥ 0.50 and its floor (peak − 0.50) is then ≥ 0 — at or above the
ratchet's threshold — and the trail is checked first. The ratchet is strictly
dominated inside BEAR_HE. Decision rule fires **SUPPRESS**, implemented as
`be_after: null` on the `BEAR_HE` cell (which is why regime merges last).
Confirmed in production: suppress vs stack over the 224 BEAR_HE bear-debit rows
differ on **0 rows**.

**The production delta is NOT the study delta — record this, it will recur.**
The study measured against `DEBIT_PROD` (pt .90 / sl .75 / tef .75, **no
trail**). Production has shipped the BEAR_HE trail since 07-22, so the study's
baseline is not production's:

    bear debit (n=332)          mean R              total $            rows changed
    study framing            -0.133 → -0.092                              —
    production, measured     -0.109 → -0.093    -43,806 → -37,951         16
      on BEAR_HE (suppressed) -0.152 → -0.152    unchanged                 0
      elsewhere (n=108)       -0.019 → +0.028     -4,916 → +939           16

So the shipped rule is worth **+0.015 mean R / +$5.9k**, not +0.041 / +$16.4k,
and `be_stop` fires on **16 rows, not ~44**. The two rules were largely buying
the same rows and the trail got there first on 224 of 332. The generalisable
lesson: **a study delta measured against `DEBIT_PROD` overstates production
impact wherever a regime cell already ships a rule that converts the same
rows.** Every future exit study should quote both baselines.

`stop_loss` 92 reproduces exactly; the *baseline* is 100, not the study's 110,
for the same reason.

**Leak guard — PASSED.** Non-bear debits (n=261): 0 rows changed, mean R and
dollars identical. Credits (n=202): 0 rows changed. The narrowness is the
finding (+0.234 → +0.209 on non-bear debits), and it is now enforced by tests.

### 2. SHIPPED — bear hedge sleeve (`deployment-rules.md`)

D2/D4/D3 written up as an operator section: bear is a **hedge, not a
selection**; rank the day's candidates by `|delta|` DESCENDING; size at ≤ ½.
Limits travel with the rule (D3 formally NOT MET by $86, worst-decile CI
includes zero, naked puts unrepresented, D5 does not reproduce). The bear_put
**DEMOTION thread (open since 07-22) is CLOSED without a demotion mechanism** —
bear rows are already C/VETO and never enter the deployed top-3, so the answer
was an exit profile, not an intake veto.

### 3. SHIPPED — live-loop `SUBSTITUTED`, and a CORRECTION to the 07-27 entry

The 07-27 §4 entry states that a naked leg filled against a spread play "falls
to **NONE**, indistinguishable from 'no play that day'", i.e. silently dropped.
**That is wrong, and the truth is worse.** `SIDE` maps `long_call` and
`bull_call_spread` both to `debit`, so the family branch labelled such fills
**STRUCTURE** — pooled into the eval as if the emitted play had been traded.
A second defect: that branch matched on credit/debit only, so a `long_put` fill
against a `bull_call_spread` play (opposite directions, both debit) was also
labelled STRUCTURE.

Fixed in `stage1_map_fills.py`: a `DIRECTION` map now gates the family branch,
substitutions get their own `SUBSTITUTED` confidence, and candidate selection is
rank-based (EXACT ≺ STRUCTURE ≺ SUBSTITUTED) so a true match always outranks a
substitution. Tally on the checked-in snapshot moves **0/3/15 → EXACT 0 /
STRUCTURE 2 / SUBSTITUTED 1 / NONE 15**; the reclassified row is the META
short-put-vs-`bull_put_spread` entry the report's own prose had already flagged
as weak while the tally counted it as a match.

### 4. SHIPPED — the v4 prompt trim (`score_flow` / `score_dealer` dropped)

`score_vol` stays (exempt); `score_price`/`score_catalyst` were always
pipeline-computed. `ROW_COLUMNS` goes 27 → 25 and the columns are dropped from
the schema outright rather than blanked, because v4 writes fresh tabs.
`RESULT_COLUMNS` KEEPS them so the results schema stays stable across eras and
the four study loaders that name them keep working on pooled exports. Reader
audit found no `KeyError` risk — every analysis-row consumer uses
`.get(col, "")`.

**The queued trigger did NOT fire.** The 07-21 queue said "drop if still null
after the 25-date backfill". They are not null — 366 of the last 400 rows carry
both. The justification is instead the 08-11 ML ablations (nothing beyond
structure × regime × geometry is reproducible) and the framework's own admission
that `score_dealer` was judged off a vol-snapshot proxy, never real dealer data.
Recording this because the trim now rests on a *different* argument than the one
that queued it.

**Correction to the plan: the new scale is 0–50 for DIRECTIONAL/HEDGE/SYNTHETIC
but 0–55 for VOLATILITY.** VOLATILITY's dropped `flow` max was 20, not 25, so
its survivors are 10 + 25 + 20 = 55. Documented as such everywhere rather than
rounding the claim down; flattening it to 50 would be a rubric change, not a doc
change. Either way v4's `score_total` is NOT comparable to v3's 0–100 and must
never be ranked across the two eras — it survives only as a deterministic
tie-break within a tier.

**A live prompt bug found and fixed in passing.** The contract told the model
"NEVER emit a bear call spread" and then, ~45 lines later, instructed it to use
one for the bearish high-IVpct TF-S case; `claude.md` and `codex.md` carried the
same contradiction. Only the framework's Step-4 table was correct. This could
emit the single most toxic structure in the book (−0.82 mean, 17% win,
intake-vetoed since Attempt 13) — the backtest would have refused it at intake,
so the cost was wasted plays rather than bad fills, but it was live. All three
now route bearish TF-S to a bear put debit spread or a pass. Folded into this
version bump because it is a prompt change and needed one.

Also fixed: the guardrails told the model to "zero the price and catalyst
components" to hold a total down — impossible since both became
pipeline-computed. It now withholds `vol`, the only lever it still has.

### 5. The cut-over mechanics — in-place `vN_` renaming, NOT a new spreadsheet

Worth recording because the close-out plan assumed a new spreadsheet and a
`GOOGLE_SPREADSHEET_ID` change, and that is **not** what this repo does. The
sheet already carries `v1_AnalysisClaude_20260625`, `v2_AnalysisClaude`,
`v3_AnalysisClaude` — the established convention is to rename the live tabs with
a `vN_` prefix in place and let the pipeline recreate fresh ones. The v3 rename
is done (`v3_AnalysisClaude` 1,608 rows / 27 cols, `v3_BacktestResults`,
`v3_BacktestProxy`), and an empty `AnalysisClaude` is waiting with 0 columns, so
the first v4 append writes a clean 25-column header.

Two consequences, both good, that the plan got wrong in the cautious direction:

- **`BaselineDaily` is untouched** (214 rows, continuous). The plan's warning
  that v4 would start with no regime-baseline history — the one real risk it
  flagged — is moot under in-place renaming. No `build_baseline --backfill`
  needed.
- **No env change, and no code change.** `config/backtest.yml`'s
  `analysis.tab: AnalysisClaude` and `output.sheet_tab: BacktestResults` already
  point at the v4 tabs by virtue of the rename.

The live cost is that `python -m scripts.backtest` now reads 0 rows until v4
accumulates; v3 work must pass `--tab v3_AnalysisClaude`. Study code is
unaffected — it reads CSV exports by filename, not tabs.

### 6. Tests

`tests/test_mech_regime.py` gains the structure-override suite (bear debit gets
the ratchet, non-bear debit and credits never do, BEAR_HE suppression, merge
order, disabled/default no-ops). `tests/test_backtest.py` gains five ladder
tests pinning `be_stop` between `dollar_stop` and `stop_loss` — the position is
load-bearing and was previously unguarded.

### 7. `exit_basis` widened — `BEAR_DEBIT` (fixed in the same change)

Shipping the ratchet initially broke the column's guarantee: a bear debit that
ran `be_after` reported `PROD`, so `exit_basis == "PROD"` stopped meaning "base
config only" — the exact ambiguity the column was added to prevent. The
vocabulary is now `{PROD, CREDIT, BEAR_DEBIT, <regime cell>}`, reported in
merge-precedence order: a regime cell outranks `BEAR_DEBIT` because regime
merges last and, on BEAR_HE, genuinely governs (it nulls `be_after`). Pinned by
tests that assert the label never claims a profile the merge did not apply.

### 8. Known gaps left open, deliberately

- **`scripts/chart_backtest.py:55-76`** re-derives exit config for chart
  reference lines and knows about neither `regime_exit` nor `structure_exit`;
  bear-debit charts draw a −75% stop line for positions that exited at
  breakeven. Pre-existing, now one rule wider.
- **`backtests/live_loop/` is UNTRACKED.** `.gitignore` excludes `backtests/*`
  and its own comment calls that directory disposable scratch that "gets deleted
  periodically" — yet `stage1_map_fills.py` is 30KB of real code and is now the
  only source of new evidence. This is the same mistake the 08-11 refactor fixed
  for study code by moving it to `scripts/backtest_study/`; the live loop was
  missed.

---

## 2026-08-11 — v4 emission-composition bridge: PRE-REGISTRATION (written BEFORE the run)

**Status: pre-registered, NOT run.** Everything below is fixed in advance. If
the numbers land differently from what the operator hopes, the decision rule
stands as written — that is the entire purpose of writing it first.

**What is changing.** v3 is being closed out (see the close-out entry above once
written) and the analysis prompt is being trimmed: `score_flow` and
`score_dealer` come out of the per-play `score` object; `score_vol` stays. v4
runs on a NEW spreadsheet, so the tabs are fresh and the schema drops both
columns rather than blanking them.

**Why a bridge test is needed at all.** The columns themselves are established
as decision-irrelevant — the 07-21 sweep found only `delta`/`dte` (bull_put) and
`iv_spread` (bear_put) decision-relevant, and the 08-11 ML ablations found
nothing beyond structure × regime × geometry adds anything reproducible. That is
NOT the risk here. The risk is **behavioral**: removing two of five Step-5
factors may change *what plays the model emits*. The only statistically
significant v2→v3 difference in this entire log was exactly that — credit
emission 19% → 34% — and it was not predicted in advance either.

If the emission profile shifts, every rule in `config/deployment-rules.md` was
derived on a population v4 no longer draws from, and the ladder's validation
does not transfer. That is worth ~20 headless runs to find out.

**Test.** Run the v4 prompt over ~20 dates already covered by v3, writing to a
scratch tab. Compare against the v3 rows on the same dates (exported from the
old sheet before the switch). Date-paired, two-proportion tests on:

1. structure mix (bull_call / bull_put / bear_put / other)
2. credit share of emitted plays
3. plays per day
4. bear share
5. ladder tier mix (A / B / C / VETO)

**Decision rule, fixed now:**

- **Composition within noise** → the v3-derived ladder CARRIES FORWARD to v4
  rows. Record it and deploy unchanged.
- **Composition shifts on any of the five** → the ladder is UNVALIDATED on v4.
  Keep deploying under the v3 rules, flag every v4 row as such here, and let the
  live eval arbitrate. Do NOT quietly assume the tiers transfer, and do not
  re-derive the ladder on v4 rows until there are enough of them to mean
  anything.

**Pre-committed caveat.** ~20 dates is thin for a five-way composition test;
this is powered to catch a shift the size of the v2→v3 credit jump, not a subtle
one. A null result here is "no large shift detected", never "the populations are
the same".

---

## 2026-08-11 — DEPLOY arm: the hedge caveat was TESTABLE, and bear deployment has a rule

The 08-11 bear arm closed by calling the chop hedge "a *portfolio* decision the
book cannot price". **That was too strong** — 84 of the bear dates also carry a
deployed ladder sleeve, so the concurrent book exists and the portfolio question
is answerable on it. The operator's instruction (bear positions stay deployable)
made the gap worth closing. Pre-registered as
[`ml-plan.md` §addendum 2](ml-plan.md) BEFORE running; code
`scripts/backtest_study/bear_deploy.py`, output `backtests/study_output/bear_deploy.txt`.
Same 795-row book, same protocol, no new columns.

**What B1/B2 had actually left open.** Three distinct estimands, not a second
bite at the same one: B1 asked an *absolute level* question and B2 an *exit*
question, and neither asked (a) the two jointly, (b) what bear does to a
concurrent long book, or (c) *which* bear to take on a day one is taken anyway.

### 1. D1 — joint selection × exit: NOT MET (B1's verdict survives)

B1 screened E under the PROD exit; B2 then changed the exit; the pair had never
been run together. Re-screening the identical 496-subset vocabulary on R under
`be_after: 0.50`: **0 survivors, ~10 expected by chance.** Pooled bear
E −0.601 / R(PROD) −0.168 / R(bear exit) −0.203. The best subset is
`mech LVOL AND dte 31-59` at R +0.287, CI [−0.034, +0.593] — still includes
zero at n=49. **Bear selection remains unfixable; the new exit does not rescue
it.** Worth noting the exit lowers pooled R slightly (−0.168 → −0.203) across
ALL bear rows including credit — B2's +0.041 gain was measured on bear *debit*
rows only, and that scoping is load-bearing.

### 2. D2 — the hedge is REAL (all three pre-registered criteria fire)

Deployed sleeve = shipped ladder (top-3/day, tiers A/B, 220 rows / 90 dates).
Bear sleeve = that date's bear candidates. 84 overlapping dates.

    deployed-book bucket   dates   deployed R    bear R     bear $   bear win%
    worst decile               8       -0.795    +0.252     +6,669      75.0%
    worst quartile            21       -0.457    +0.184    +16,824      66.7%
    negative dates            25       -0.390    +0.109    +16,985      60.0%
    positive dates            59       +0.706    -0.281    -41,895      32.2%
    ALL                       84       +0.380    -0.165    -24,910      40.5%

Sleeve correlation −0.132; tail positive in 2 of 3 evaluable years
(2024 +0.129 / 2025 −0.048 / 2026 +0.405). **HEDGE IS REAL: MET.** The shape is
textbook insurance: it pays where the book bleeds and bleeds where the book
pays. Honest limits — the worst-decile row-level CI is [−0.113, +0.639] (n=28,
includes zero), 2025's tail is mildly negative, and D2 approximates a hedge as
equal-weighted concurrent dollars, which is a *proxy* for, not a measurement of,
a held hedge.

This is the first evidence in the log that supports carrying bear risk at all,
and it exists only because the question was asked at the book level. Every prior
bear verdict measured the standalone play and was correct to be negative.

### 3. D4 — the operator's real question, and the one actionable rule

Not "is bear good" but **"given I take a bear position today, which one?"** —
a *within-date paired* test on 93 dates with ≥2 bear candidates (3.8/day). The
day is its own control, so the −0.5 level that sinks every B1/D1 subset cancels.
This test had never been run, on any structure.

    ranker                    dates    pick R   day avg      gain   CI95              LOO min
    |delta| HIGH first           93    +0.051    -0.181    +0.232  [+0.091,+0.370]     +0.204  **
    iv_spread low first          92    -0.094    -0.180    +0.086  [-0.056,+0.236]     +0.065
    dte short first              93    -0.176    -0.181    +0.004  [-0.203,+0.185]     -0.015
    |delta| low first            93    -0.393    -0.181    -0.212  [-0.370,-0.062]     -0.233
    score_total high first       93    -0.436    -0.181    -0.255  [-0.417,-0.098]     -0.276
    widest max_loss first        93    -0.526    -0.181    -0.345  [-0.580,-0.147]     -0.368

**`|delta| high first` is ADOPTED** — 1 survivor of 10 tested (~0.5 expected),
CI excludes zero, every LOO fold positive, positive in all three years
(+0.285 / +0.312 / +0.083). It is **not exit-dependent**: on R under the
SHIPPED PROD exit it still holds (+0.159, CI [+0.028, +0.280], LOO +0.144, all
three years positive). On E alone it fails (+0.059, CI includes zero) — so this
is a *realized-return* effect, partly exit-mediated, and must be quoted that way.

Read: **the losing bear trade is the cheap far-OTM one.** Buying the
closer-to-money bear spread turns a −0.181 average day into +0.051. Two
corroborations from elsewhere in the log: D1's best subsets pair `LVOL` with
`|delta|>0.20`, and `score_total high first` anti-selecting (−0.255) is the
07-21 "score is decision-irrelevant / pre-13c scores anti-select" finding
reappearing inside a structure.

### 4. D3 — always-on sizing: NOT MET, but by $86

**Deviation, recorded:** the pre-registration fixed the sizing rule but not
which bear is taken daily. The first cut used the day's widest `max_loss` —
which D4 then measured as the single *worst* available pick. Both are reported.

    sleeve = 1/day by |delta| high (D4-adopted)
        f      total $    max DD $   worst date $
     0.00       63,553      -7,609         -3,212
     0.25       64,268      -7,255         -3,255
     0.50       64,982      -7,037         -3,298
     1.00       66,412      -7,780         -3,501

    sleeve = 1/day by widest max_loss (lower bound on a bad pick)
     0.50       42,167     -11,291         -3,877
     1.00       20,780     -18,127         -4,542

At f = 0.50 with the right pick, **max drawdown IMPROVES** (−7,609 → −7,037) and
total rises +$1,430. The pre-registered rule still returns NOT MET because
worst-date slips $86 on a $63.5k book — the rule's worst-date clause is doing
all the work at a magnitude that is noise. Reported as NOT MET per the letter of
the pre-registration; read as *the sleeve is roughly free at half size, and
expensive at full size or with a bad pick.* The picker matters more than the
size: same sleeve, same days, −$42.8k swing between the two.

### 5. D5 — timing the hedge: POST-HOC, and it does NOT reproduce

D2+D3 jointly imply a gate (pays in the tail, bleeds in the body). Seven
deploy-time gates tested; `mech H-VOL` and `mech BEAR_HE` leave drawdown and
worst-date unharmed while adding $2–3k. **But the year check kills it:** the
leading gate is 2024 −$2,655 / 2025 +$5,179 / 2026 +$813 — one year carries it,
which is the Mar–Apr-2025 failure mode for the third time in this log.
**Candidate only, not a finding, chosen after seeing D2.**

### 6. What this changes

- **Bear positions are deployable — as a hedge, not as a selection.** D1
  reconfirms there is no bear edge standalone. D2 shows the sleeve pays in the
  deployed book's tail. These are consistent, not contradictory, and the
  distinction is the whole answer.
- **Recommended (NOT shipped — operator decision):** add to
  `deployment-rules.md` — *when you take a bear position, take the
  closer-to-money one; rank the day's bear candidates by |delta| descending.
  Size the sleeve at ≤ ½ a normal position and treat it as insurance, not as a
  play.* This is the first bear rule in the log that reproduces in all three
  years on the SHIPPED exit.
- **The `bear_arm.py` caveat is amended:** "the book cannot price a hedge" is
  retired and replaced with the measured version — it *can* price a
  concurrent-dollar proxy for one, and did.
- **Still unanswered, and honestly so:** 88% of bear rows are `bear_put_spread`
  and only 6 are naked `long_put`, so none of this speaks to the naked-put
  hedge the operator sometimes substitutes (see the SUBSTITUTED item in the
  live walk-forward). Margin, assignment and real position sizing remain
  outside the book. D5's gate needs an independent window.
- Unchanged: no production config, prompt or ladder was modified by this run.

---

## 2026-08-11 — ML combination search RUN: NULL RESULT; and the bear arm finds an EXIT fix, not a selection one

Both arms of [`ml-plan.md`](ml-plan.md) executed against the same 08-11 exports.
Code is now TRACKED under `scripts/backtest_study/` (`book.py` loader, `harness.py`
replay port, `protocol.py` validation, `ml_combination.py`, `bear_arm.py`);
outputs in `backtests/study_output/`. Book: **795 priced rows,
118 dates, real 406 / tweak 389** (bs excluded per the 08-11 decision; the
loader's exact-replay gate drops 48 non-reproducing proxy debit rows and 3 real
dups, which is why 795 and not the 08-11 scratch cut's 817).

Deviations from the plan, both recorded before the run: GBM is sklearn
HistGradientBoosting rather than LightGBM (same family, no libomp), and a
third replay variant (**abstain** — the model may sit out a day) was added so
the ladder's right to trade nothing is not an unfair advantage.

### 1. ML arm — nothing beats the ladder, in any form

Purged expanding walk-forward, 10-date blocks, 120-day embargo → 58 of 118
dates ever tested (the embargo is expensive at this sample size). Every model
ranked against the ladder on the SAME dates, paired at date level.

    model            forced        abstain       tie-break in A/B
    B1 logistic      -0.173        -0.073        -0.074
    B2 elastic net   -0.180 *      -0.095        -0.062
    M1 GBM (E)       -0.096        -0.057        -0.006
    M2 GBM (E>0)     -0.113        -0.097        +0.022  CI[-0.017,+0.071]
    M3 depth-3 tree  -0.155 *      -0.102        -0.027
    (* CI excludes zero — i.e. significantly WORSE than the ladder)

**Not one positive gain with a CI excluding zero, in 15 model×strategy cells.**
The best cell in the whole study is M2 as a within-tier tie-break at +0.022,
CI [−0.017, +0.071] — includes zero, so ADOPT-AS-TIE-BREAK is also not met.
M3 additionally fails the year-sign criterion (2025 +0.361 / 2026 −0.121).

**Phase-5 verdict: NULL RESULT — the ladder is at or near the information
ceiling of these columns.** This was the plan's stated modal outcome.

Supporting reads, all consistent with the 07-21 column sweep:
- The full-sample M3 tree's root split is `structure = bull_call` — the model
  rediscovers "structure is the signal" unprompted.
- Ablations (top-3/day $ out-of-fold): ladder-only +$6.1k → +regime +$1.9k →
  +geometry +$11.9k → +enrichment +$2.5k → +scores +$4.0k → +calendar +$10.3k.
  Non-monotone and inside the noise: **nothing beyond structure × regime ×
  geometry adds anything reproducible.**
- Composition-proxy test (rule 6) catches `cpir` red-handed: pooled Spearman
  vs E **+0.27**, but within structure +0.04 / −0.03 / −0.10. Same trap as
  oi_confirm/iv_pct. `iv_pct` repeats its own failure (pooled −0.17, within
  structure −0.12 / +0.05 / +0.12, sign-flipping).

### 2. Bear arm B1 — selection: NOT MET, decisively

370 bear rows (bear_put 327 / bear_call 37 / long_put 6), 111 dates. Pooled
E −0.601, CI [−0.726, −0.477], negative every year (−0.815 / −0.660 / −0.386).

496 pre-declared 1- and 2-clause subsets evaluated, 203 with n ≥ 40.
**0 survivors** of the pre-registered rule, against ~10 expected by chance at a
nominal 5% rate. The best subset in the entire search is E −0.231
(`mech BEAR AND iv_pct<0.5`, n=43) — still negative. There is no conditioning
of bear entries, on any decision-time variable in the book, that is not a
losing selection.

**The operator's chop hypothesis, tested directly.** The closest thing to
support is the RANGE + calm/choppy slice, and it is an EXIT story:

    slice                    n    dates   E        R        $        |MAE|/MFE
    model RANGE + C/L-VOL    55   16     -0.370   +0.182   +$10,119   0.76
    model C-VOL              53   20     -0.596   +0.128    +$7,095   0.92
    mech L-VOL               97   38     -0.581   +0.002    +$3,586   0.99
    model H-VOL              78   17     -1.157   -0.682   -$50,482   4.01

RANGE+C/L-VOL is the only bear slice that makes money (R positive in 2 of 3
years: −0.247 / +0.320 / +0.284), and its |MAE|/MFE of 0.76 is the only
non-mirrored bear number in the book. But **E is −0.370 with CI [−0.697,
−0.045] and the R CI [−0.117, +0.463] includes zero**: the plays are still
wrong, the exit is what collects. Directionally consistent with the operator's
instinct; not a selection edge, and n=55 over 16 dates.

The mirror image is decisive and already shipped: bear in H-VOL is −$50.5k at
a 9% win rate and |MAE|/MFE 4.01 — the ladder's BEAR+H-VOL VETO earns its keep.

### 3. Bear arm B2 — exit: **CRITERIA MET**, and it is the knob addendum 12 pre-nominated

Frozen grid only (18 debit configs, no new mechanism). Bear debit n=332:
mean E −0.534 vs mean R(PROD) −0.133 — the exit is ALREADY rescuing ~0.40 of a
bad selection, and six configs rescue more. Ranked by robustness, not by size:

    config              Δ pooled   CI95            ex-25MarApr   2026 alone      LOO min
    BE ratchet @.50     +0.041   [+0.015,+0.065]   +0.020        +0.028 [+0.009,+0.053]  +0.038
    trail .40/.50       +0.042   [+0.007,+0.073]   +0.023        +0.037 [-0.002,+0.077]  +0.038
    trail .25/.50       +0.043   [+0.003,+0.081]   +0.020        +0.025 [-0.032,+0.078]  +0.038
    trail .50/.50       +0.036   [+0.005,+0.064]   +0.014        +0.031 [-0.002,+0.066]  +0.032

**Why this is not addendum 12 again.** Addendum 12 killed the structure-keyed
bear trail because 94% of its gain sat in Mar–Apr 2025 (ex-window +$744 over
241 rows ≈ 0). It closed with two statements that this run tests exactly:
"trail .25/.50 dominates .50/.50 … recorded so the next bear-heavy window tests
the right knob first", and "what would settle it: a second sustained bear
drawdown in the book." Feb–Apr 2026 is that drawdown, and the backfill is now
complete. On the completed book:

- ex-Mar–Apr-2025 Δ is **+0.020** (was ≈ +0.003 in July) — the effect no longer
  lives in one window;
- **2026 alone is +0.028 with CI [+0.009, +0.053]**, i.e. the new, independent
  bear window confirms it on its own;
- positive in all three years (+0.036 / +0.055 / +0.028) and in both pricing
  tiers (real +0.054 / tweak +0.027);
- LOO-by-date: every fold positive (min +0.038) — the test that killed the
  per-regime switch twice.

BE ratchet @.50 is preferred over the trails on robustness, not on pooled size:
it is the only config whose 2026-alone CI excludes zero and its pooled CI is
the tightest. Mechanically it converts 44 rows into `be_stop` and cuts
stop_loss 110 → 92 — it stops giving back excursions, which is precisely the
|MAE|/MFE ≈ 1.1–1.4 mirrored-path signature of bear rows.

**It must be bear-KEYED.** The same config on the non-bear debit book is
+0.234 → +0.209 (−0.026); this is why Attempt 10 was right to remove the global
debit trail and why the correct scope is the structure, not the whole side.

**Honest size.** −0.133 → −0.092 mean R: it cuts the bleed by ~31%, it does not
create an edge, and −$54.4k → −$38.0k over 332 rows. Every bear row in the book
is ladder tier C (299) or VETO (71) — **none are deployed by the shipped
ladder**, so this rule only bites on positions the operator takes deliberately.
That is exactly the stated use case (the chop hedge), which is what makes it
worth shipping despite the modest size.

Credit side (bear_call, n=38): `pt .50` clears CI+LOO (+0.344) but the best
config `sl 1x` does not (CI [−0.012, +1.252]), the population is one year deep,
and bear_call is already structure-vetoed at intake with 0 emissions since. **No
credit-side change** — nothing to apply it to.

### 4. What this changes

- **The bear_put implementation question (open since 07-22) now has a
  non-demotion answer**: keep bear structures selectable, keep them out of the
  deployed top-3 (they are already C/VETO), and give them their own exit
  profile. Selection stays unfixed because it is unfixable from these columns.
- **Recommended (NOT shipped — operator decision):** a structure-keyed exit
  clause for bear debit spreads, `be_after: 0.50`, alongside the existing
  `regime_exit` block in `config/backtest.yml`, plus the matching line in
  `deployment-rules.md` §"Exit management": *if you are holding a bear debit
  spread, move the stop to breakeven once it has made 0.5× the debit.*
- **The ML question is closed** for this feature set. Re-open only on new
  columns, not on new models — the ablations say the columns, not the
  estimator, are the binding constraint.
- Unchanged: no production config, prompt or ladder was modified by this run.

---

## 2026-08-11 addendum — `mech_cell` BACKFILLED across the analysis tabs + nightly job

Plumbing, no tuning conclusion. `mech_cell` shipped 2026-07-22 (archive/06
addendum 9) but only stamps rows written after it, so the deploy-time surface
was blank for the whole history and `NO_DATA` wherever the SPY/VIX table had
been stale. Both are recoverable: the label is a pure function of the signal
date and the frozen table.

- `scripts/backfill_mech_cell.py` — recomputes every row, fills blanks and
  `NO_DATA`, and KEEPS a stored label that no longer reproduces (logged as
  DRIFT, exit 2) rather than overwriting it; `--force` overwrites, `--dry-run`
  reports. Writes only that one column, so formulas and every other column are
  untouched. `make backfill-mech-cell` (depends on `mech-regime`).
- `.github/workflows/backfill-mech-cell.yml` — chained on Compile Flow
  (`workflow_run`), which refreshes the SPY/VIX table at 22:30 UTC, so the job
  can never label off a stale close. Idempotent; nothing to fill = no write.
- Run 2026-08-11: **1,284 cells filled across 1,620 rows / 3 tabs, 0 DRIFT** —
  every one of the 336 previously-stored labels reproduced exactly, which is the
  first end-to-end check that the stored column and `lib/mech_regime.py` agree.
  AnalysisClaude now reads 142 dates, 2024-06-17 → 2026-08-10: BEAR_HE 758 /
  LVOL 728 / RB_EVOL 43 / NONE 78, no blanks, no NO_DATA.

**Header drift found while doing it (fix written, NOT yet applied).**
AnalysisGPT and AnalysisTickerSpecific headers had stopped at 24 columns
against a 27-column `ROW_COLUMNS` — GPT missing `iv_pct`/`price_vector`/
`days_to_earnings` plus pre-rename `ConvictionScore`/`ConvictionScoreLabel`,
TickerSpecific missing `iv_skew`/`iv_pct`/`score_catalyst`. Because
`append_rows` writes POSITIONALLY, every column past the gap is mislabelled on
those tabs, and a column-keyed write lands in the wrong place. Data loss: none —
all 13 rows on those two tabs are empty past `created_datetime` (both tabs are
near-unused). `scripts/align_tab_headers.py` repairs it (relocating a
schema column that is merely misplaced, aborting the tab if a drifted column
holds data that is not in the schema); dry run is clean, the write is pending
operator approval. AnalysisClaude — the tab everything reads — was already
correct.

---

## 2026-08-11 addendum — `bs_options_hist` DROPPED: measured as effect-diluting and replay-contaminating; tier now off behind `proxy.bs_fallback`

Scratch cut on the same 08-11 exports (`bs_tier_decision.py`, read-only, no
config changed). Question from the operator: keep BS, or evaluate on
real+tweak only.

**Calibration is impossible and the tier knows it.** 0 same-key overlap rows
(no play is priced both real and bs — the chain is strictly ordered, so BS is
never checked against a real mark), and `pct_real_days = 0.00` on **all 301**
bs rows. There is no bs row anywhere in the book with a single real price day.

**What is actually lost by dropping it:** 301 rows (27% of the pooled book)
but **0 dates** — every bs date also carries real/tweak rows. The tier is
overwhelmingly the long-dated filler: 69% of the DTE≥180 band is bs (208 of
302 rows), vs 5% of ≤30 DTE and 5% of 31–59. Dropping bs therefore removes
almost nothing from the ≤60-DTE band the ladder actually deploys in.

**The dilution finding (this is the real reason, not the $).** BS marks are
tail-compressed: E sd 0.86 vs real 1.38 / tweak 1.24, `|E|>2` at **2.3% vs
12.1% real**. Flat-ish donor vol, no spread, no gaps — so every bs row sits
nearer zero than a real one, and pooling shrinks **every** effect toward zero
in the same direction:

    bucket            r+t E     pooled E   (bs pulls toward 0)
    bull_call        +0.672  →  +0.540
    tier A           +0.688  →  +0.590
    tier B           +0.601  →  +0.495
    bear_put         −0.528  →  −0.394
    bear_call        −1.240  →  −1.054
    tier VETO        −0.548  →  −0.432

That is attenuation bias against exactly the separations the ladder is built
on. No sign flips and no shipped conclusion reverses (year signs, structure
ranking, ladder monotonicity, bear_put DEMOTE all hold either way — holdout
r+t is E −0.406 CI [−0.517, −0.295] vs pooled −0.358), so bs has **never been
load-bearing for a decision**; it has only ever made true effects look weaker.
Where bs *can* be compared like-for-like (DTE≤59, n=20) it does not track
real: E −0.220 vs real +0.026, sd 1.83.

**It is not merely a headline-$ problem — it enters the replay.** bs supplies
**64 of the top-3/day A-then-B picks**, worth +$8.5k of model-priced P&L, and
inflates the 2026 replay from **+$3.3k (r+t) to +$8.8k (pooled)**. The 08-11
"quote real+tweak only" rule was framed as reporting hygiene; it is actually
a selection problem. Total bs $ is +$51.6k of the +$65.7k pooled, +$48.9k of
that in DTE≥180 (single SNDK 04-06 long_call DTE 182 = +$27.5k).

**Decision — SHIPPED same day (operator approved).**

1. *Evidence layer:* real+tweak is the ONLY population for E, R, $, MFE/MAE,
   ladder tiers, holdouts, and the replay. bs is coverage bookkeeping, never
   evidence. Same standing as the 07-27 §3 long-dated rule.
2. *Chain layer:* `_method2` is now opt-in behind **`proxy.bs_fallback`
   (default `false`)** in `config/backtest.yml`, gated in `_evaluate`
   (`scripts/backtest/proxy.py`). Directional plays fall to `underlying_trend`,
   which answers the same question honestly (direction verdict, blank P&L,
   `exit_basis=NONE`) instead of minting a P&L number that reads as data. Only
   2 rows in the whole book (1 straddle, 1 strangle) would go from bs to
   `unevaluable`; existing bs rows stay frozen unless `--redo`. Cost: no
   path/MFE estimate for long-dated — but a tail-compressed BS path was never
   a usable one. Kept as a flag rather than deleted so the tier can be revived
   for a deliberate study; two tests pin both branches of the chain
   (`test_evaluate_skips_bs_tier_by_default_and_falls_to_underlying_trend`,
   `test_evaluate_uses_bs_tier_when_bs_fallback_enabled`). Docs synced:
   `config/backtest-reference.md` fallback-chain section + `proxy_method` row,
   `docs/architecture.md` proxy map, proxy.py module docstring.
3. *Historical rows are NOT purged.* The 301 existing `bs_options_hist` rows
   stay in BacktestProxy — filter them out at read time by `proxy_method`
   (equivalently `pct_real_days == 0`); the flag only stops NEW ones.
4. What this does NOT fix: the long-dated blind spot itself. Removing bs makes
   the gap visible instead of papered over; the fix is still real long-dated
   price history.

---

## 2026-08-11 — completed-book analysis: holdout coverage FULL, DEMOTE fires at n=164; bs long-dated rows contaminate pooled $ totals

Source: fresh exports `backtests/to_evaluate/analysis - BacktestResults.csv`
(406 rows) / `- BacktestProxy.csv` (796), stamped 08-11 15:38. Pooled priced
book after dedup: **1,118 rows** (real 406 / tweak 411 / bs 301), 118 dates,
2024-06-17 → 2026-04-07. Scratch cut (read-only), no config changed. Operator
instruction: treat the run as complete even though some analyses are flagged
for rerun. Housekeeping: 0 within-real dups (03-06 fix held); all 7
previously-missing holdout dates present; 02-17/02-19 present in both tabs.

### 1. Year breakdown — 2025H1-only profit confirmed; 2026 is the only year with CI fully below zero

    year   n     mean E   CI95 (date-clust)     R        $ (real+tweak)
    2024   295   −0.018   [−0.195, +0.152]      −0.059   −$14,355
    2025   499   +0.091   [−0.037, +0.213]      +0.145   +$47,893
    2026   324   −0.196   [−0.287, −0.101]      −0.055   −$19,503

    halves: 2024H1 −0.198 · 2024H2 +0.009 · 2025H1 +0.136 (+$78.0k pooled) ·
            2025H2 −0.181 · 2026H1 −0.196
    MFE/MAE by year: |MAE|/MFE 1.13 / 0.79 / 1.18, R-capture −0.08 / +0.16 /
    −0.09 — only 2025 has upside asymmetry; 2024/2026 mirrored = path-vol.

**⚠ Pooled-$ contamination (new standing hazard).** Pooled realized $ reads
+$65.7k, but **+$48.9k of it is DTE≥180 `bs_options_hist` rows with
`pct_real_days = 0.0`** — pure flat-vol BS marks on exactly the contracts the
2026-07-27 §3 rule says carry no evidence. One row (04-06 SNDK long_call,
DTE 182) is +$27.5k by itself; the 04-06 NVDA/MRVL long_calls (DTE 722/725)
add +$9.6k. The honest book is **real+tweak: +$14.0k total** (−$14.4k / +$47.9k
/ −$19.5k by year). Any headline $ from these exports must be quoted
real+tweak; the pooled figure is not a portfolio number.

### 2. Structure breakdown (pooled / real+tweak E)

    structure          n(pooled)  E pooled  E r+t    R       $ r+t
    bear_put_spread    468        −0.394    −0.528   −0.081  −$44,000
    bull_call_spread   338        +0.540    +0.672   +0.295  +$80,237
    bull_put_spread    237        +0.101    +0.183   −0.005   −$1,946
    bear_call_spread    43        −1.054    −1.240   −0.518  −$11,221

    year × structure (E): bear_put −0.41/−0.43/−0.35 (negative every year);
    bull_call +0.44/+0.66/+0.29 (positive every year — still the only
    reproducing positive); bull_put +0.24/+0.25/−0.17 (2026 out-of-band
    DTE-driven as before); bear_call −1.97/−0.70/— (0 emissions 2026 —
    intake veto holding).

### 3. Ladder reproduces on the completed book

    tier    2024            2025            2026
    A       +0.708 (n=37)   +0.670 (n=105)  +0.305 (n=45)
    B       +0.338 (n=88)   +0.644 (n=98)   +0.431 (n=13)
    C       −0.294 (n=131)  −0.299 (n=207)  −0.278 (n=249)
    VETO    −0.586 (n=39)   −0.294 (n=89)   −0.803 (n=17)

A/B positive, C/VETO negative every year. Top-3/day A-then-B replay:
2024 +$22.7k (64% win) · 2025 +$44.8k (67%) · 2026 **+$8.8k** (66%, mean R
+0.364). 2026 Tier A improved +0.210 → +0.305 with the late dates added —
the 08-08 "genuinely weaker Tier A" worry softened. bull_put band in-window:
in-band E +0.431 / R +0.337 (n=13) vs out-of-band −0.139 / −0.211 (n=59) —
second independent window, band holds.

### 4. bear_put holdout at FULL coverage — all three pre-registered criteria fire

    n=164 priced (was 82 at the 08-04 mid-stop)
    mean E −0.358   date-clustered bootstrap CI95 [−0.460, −0.256]
    halves: early −0.207 (n=87) / late −0.529 (n=77)  ← late worse, as predicted
    ex-flawed-dates (02-23/03-02/03-20): −0.380 (n=154)
    → mean E < 0 PASS · CI upper < 0 PASS · both halves < 0 PASS → DEMOTE

The 08-04 real-tier discordance is **resolved downward**: real E −0.169
(n=51; was +0.201 at 08-04, −0.178 at 08-08) vs tweak −0.569 / bs −0.204.
Real R +0.047 — the "negative unmanaged, ~breakeven only under active risk
control" framing survives verbatim. Measure-dependence caveat stands: R-based
read is −0.086 CI [−0.215, +0.042] (includes zero), halves +0.042 / −0.232
deteriorating into the bottom. Comparator bull_call in-window: E +0.293 /
R +0.315 (n=43), |MAE|/MFE 0.51 vs bear_put 1.25 — same discriminator as
addenda 14/07-29.

**Status.** The addendum-13 criteria are now satisfied on the completed
second drawdown via this scratch cut. The formal decision run remains
`bear_position_study.py` unmodified on the window (its `AC_PATH`/`BR_PATH`/
`BP_PATH` need repointing to these exports first — the 08-04 flag #2 is
still true). Given the operator's "treat as fully run", the demotion is
decision-eligible NOW; what remains is the implementation choice (intake
`structure_veto` like bear_call vs ladder VETO tier vs leave-at-C-never-
deploy) — a user decision, deliberately not taken here.

### 5. Next study: ML combination search — plan written, NOT run

Pre-written plan at [`ml-plan.md`](ml-plan.md): learn which structure ×
regime × entry-geometry × enrichment combination best predicts play outcome,
benchmark = the shipped score-free ladder's top-3/day replay, purged
walk-forward CV clustered by date, real+tweak training only, pre-registered
ship criteria. Nothing executed as of this entry.

---

## 2026-08-08 — year-split evaluation on refreshed exports: 2025 IS the outlier for the raw book; the ladder separation is what reproduces per year

Source: fresh unversioned exports in `backtests/to_evaluate/` (`analysis -
BacktestResults.csv` 384 rows / `- BacktestProxy.csv` 738). Pooled priced book
after dedup (date|ticker|structure|play): **1,043 rows** (real 384 / tweak 381 /
bs 278), 2024-06-17 → 2026-04-02. Read-only scratch cut; no config changed.
Housekeeping vs the 08-04 mid-stop flags: **#1 the 2026-03-06 wholesale
duplication is GONE from this export** (0 within-real dups found), **#2 the
stale-export problem is resolved by this drop**, **#4 02-17 and 02-19 are now
present in both tabs**. Still missing from the holdout window: 03-18,
03-23→03-26, 04-06/04-07 (7 of 32 dates, the block nearest the episode bottom).

### 1. The unfiltered book has no standalone edge — 2025H1 is the only positive half-year of five

    year   n    mean E   E CI95 (date-clust)   R       $ realized
    2024   295  −0.018   [−0.193, +0.149]      −0.059   −$11,391
    2025   499  +0.091   [−0.036, +0.214]      +0.145   +$63,669
    2026   249  −0.243   [−0.344, −0.140]      −0.051   −$11,505

    half-years: 2024H1 −0.198 · 2024H2 +0.009 · 2025H1 +0.136 (+$78.0k) ·
                2025H2 −0.181 (−$14.4k) · 2026H1 −0.243 (−$11.5k)

Net book +$40.8k, all of it 2025. **Answer to "is 2025 an outlier": for the
take-everything book, yes** — and it is NOT the Mar–Apr window doing it (2025
ex-window E +0.184 beats in-window +0.001; the window has fat realized dollars
+$42.6k but flat expectancy on huge n=254). MFE/MAE agrees: 2024 and 2026 are
mirrored (|MAE|/MFE 1.13 / 1.26, R-capture −0.08 / −0.09 — path-vol by the
asymmetry rule); only 2025 shows upside asymmetry (0.79, capture +0.16).

### 2. What DOES reproduce in all three years: the ladder separation

Tier means on E (deployment-rules.md ladder recomputed from row fields):

    tier    2024            2025            2026
    A       +0.708 (n=37)   +0.670 (n=105)  +0.210 (n=34)
    B       +0.338 (n=88)   +0.660 (n=103)  +0.431 (n=13)
    C       −0.275 (n=135)  −0.291 (n=215)  −0.322 (n=185)
    VETO    −0.691 (n=35)   −0.402 (n=76)   −0.803 (n=17)

A/B positive and C/VETO negative in **every** year (A<B inversion in 2026 is
within thin-n noise; both positive). Top-3/day A-then-B replay is positive every
year: 2024 +$22.7k (64% win) · 2025 +$44.9k (67%) · 2026 +$5.9k (65%, mean R
+0.374). The bull_put band separates every year (in-band vs out E: 2024 +0.51 /
+0.10 · 2025 +0.83 / −0.08 · 2026 +0.34 / −0.44 — 2026 out-of-band is again
DTE>59-driven, −0.456 over 40 rows). bear_put E is negative with CI upper < 0
in each year separately (−0.41 / −0.43 / −0.32); bear_call is disastrous in
both years it appears (−1.97 / −0.70).

**So "is there proven edge": not in the analysis-as-emitted — the edge that
survives a year split is entirely SELECTION.** The system's claim is "the
ladder finds the deployable 20%", not "the plays make money" — 2024 proves it
(book −$11.4k take-everything, +$22.7k top-3 replay, and the −$36.6k of 2024
bear-structure losses are exactly what the ladder screens). Standing caveat
unchanged: the ladder was derived on this same pooled book, so per-year
consistency is robustness, not out-of-sample proof — the live walk-forward
remains the only true test.

### 3. The 2026 read: mostly composition, partly a genuinely weaker Tier A

2026 = the Feb–Apr bear episode, nothing else (29 dates, 02-02 → 04-02). It is
**57% bear_put by row count** (141/249) — the model answered a bear tape by
emitting its known-worst structure in size. Ex-bear_put 2026 is −0.138 (n=108,
median +0.002) — weak, not disastrous; the deployable A/B slice is +$6.6k. The
genuine warning is **Tier A at +0.21 vs +0.71/+0.67 in prior years** (n=34,
median +0.18): the flagship bull_call cell is much thinner in a bear episode,
as it should be directionally, but it has not yet been negative.

### 4. bear_put holdout: all three pre-registered criteria fire again at near-full coverage

Feb–Apr 2026 window, n=141 priced over 27 dates (08-04: 82/16):

    mean E −0.324   CI95 [−0.448, −0.202]   halves −0.154 / −0.496   → DEMOTE
    R −0.033 (exit rules still rescuing ~0.29 of E)

Late half twice as negative as early — deterioration into the episode bottom,
the wrong direction for a bear structure in a bear market. The 08-04 real-tier
discordance has **softened**: real is now E −0.178 (n=40) vs tweak −0.474 —
no longer positive, though real R is +0.135 (+$9.3k), keeping the addendum-14
framing "negative unmanaged, breakeven only under active risk control" alive.
Formal decision still waits on `bear_position_study.py` unmodified over the
completed window (7 dates outstanding), but this is the third consecutive read
where every criterion fires, now at 141 rows.

### 2026-08-08 addendum — year × regime × structure screens: the only reproducing POSITIVE cell family is bull_call; everything else that reproduces is a negative

Same pooled 1,043-row book, grouped by year × market_regime (direction / vol /
cell), year × stock (per-play) regime (leading BULL/BEAR/RANGE token of the free
text), and year × structure crosses. Screens required n≥8–10 per year present
and same-sign mean E every year; 24 cells tested across the three screens (few
enough that the consistent ones are not a multiplicity artifact — and they
cohere into one factor rather than scattering).

**Positive, every year present (the entire list):**

    bull_call × market-RANGE   +0.71 / +0.60 / +0.15   CI[+0.31,+0.81]  (= Tier A)
    bull_call × stock-BULL     +0.24 / +0.74 / +0.05
    bull_call × BULL (mkt)     +0.30 / +0.60 / — (no 2026 BULL dates)
    bull_put  × BULL (mkt)     +0.19 / +0.59 / — (thin, no 2026 test)
    bull_call × BEAR+E-VOL     — / +1.04(n=17) / +0.38(n=9)  (new, thin, contrarian)

Every one is long-delta. The 2026 magnitudes shrink toward zero (+0.15/+0.05):
the cell survives sign-wise through the bear episode but the edge is thin there.

**Negative, every year present:** bear_put × {BEAR, BULL, RANGE} market,
bear_put × {stock-BEAR, stock-RANGE}, bear_put × four market cells,
bear_call × stock-BEAR, bull_put × {BEAR+E-VOL, RANGE+E-VOL},
market H-VOL pooled (−0.69/−0.33/−0.10), market BEAR pooled
(−0.73/−0.23/−0.29), stock-BEAR pooled (−0.51/−0.55/−0.26).

**Reads.** (1) The "proven edge" grouped this way is ONE positive factor —
long-delta debit structures in non-bear-labelled conditions — surrounded by
reproducing negative knowledge; the ladder is close to the best available
partition of this book. (2) bear_put is negative in every year × every market
direction × every stock regime — the demotion needs no regime qualifier.
(3) H-VOL is negative all three years *unconditionally*, suggesting the shipped
BEAR+H-VOL veto may be the narrow version of a vol-only veto (H-VOL 2026 is
only −0.10, so not actionable without the missing dates). (4) bull_put ×
RANGE+E-VOL is negative all three years (−0.20/−0.04/−0.03) — the current
Tier-B band admits these; a regime qualifier is a candidate, not a rule.
(5) Alignment cut (structure direction vs stock regime) adds nothing: "with"
flips sign by year; "against" is positive every year on comedy n (10/20/6).
(6) stock-RANGE rows are E-negative but R-positive all three years — exits
extracting from chop; composition unexamined, not evidence. No 2026 data
exists for market-BULL or C-VOL, so the strongest 2024/2025 cells are simply
untested in 2026. Standing circularity caveat applies — these crosses are
re-derivations on the derivation book, now with per-year sign checks.

### 2026-08-08 addendum — bear_put MFE re-check on the refreshed book: addendum-14's "volatility, not direction" read reproduces; exit is already rescuing ~0.32

User asked whether the ten-cell demotion read means bear_put *never* went into
profit, or whether the exit is the fixable part. Recomputed on the refreshed
1,034-row deduped pool (bear_put n=424: 146 real / 160 tweak / 118 bs):

    MFE  mean +0.692  median +0.392  reach+0.30 57%  reach+0.90 29%  never>0 16%
    E    mean −0.392  median −0.897        R  mean −0.069
    give-back MFE→E +1.084   exit rescue R−E +0.323
    mfe_day 20 vs mae_day 40, MFE-first 71%
    of 241 rows reaching MFE +0.30: 61% end E<0 (held to cap), 38% end R<0

Same shape in each year separately (2026 holdout n=132: MFE +0.585, E −0.325,
rescue +0.29) and worst in the REAL tier (E −0.517, give-back 1.36) — the bs
tier is the only benign one (E −0.02), so real pricing makes it worse, not
better. bull_call comparator: give-back only 0.541, E +0.538. Answer stands as
addendum 14 ruled: the excursion is round-trip volatility, not harvestable
edge — the shipped exits already extract ~0.32 of E, the structure-keyed trail
was tested (addendum 12) and was one-window. No new cut type, no config change;
per addendum 13 the next move on bear_put is the completed holdout, not
another exit variant.

Follow-up cut, same session — "was bear_put a good choice IN the Feb–Apr 2026
bear episode": no, even there. In-window bear_put (n=132) E −0.325 / R −0.035 /
−$1.9k vs in-window bull_call (n=36) E +0.193 / R +0.312 / +$4.7k — the
long-delta structure beat the bear structure inside the bear episode itself
(rhymes with addendum 14's "bull_call beats bear_put inside mechanical BEAR
cells"). Timing decomposition: Feb entries R +0.125 (60% win, +$6.7k), Mar flat,
Apr catastrophic (R −0.700, 9% win, −$8.2k); early/late halves split at 03-06:
+$10.0k / −$11.9k. Even the February winners are exit-manufactured — Feb E is
still −0.205, the rescue is the early-run harvest before the rebound. Real tier
in-window R +0.131 (+$8.9k) keeps the addendum-14/08-04 framing "negative
unmanaged, breakeven-to-positive only under active risk control". Caveat the
right way: the 7 missing holdout dates are the block NEAREST the bottom
(03-18, 03-23→26, 04-06/07) — i.e. more late-window rows, the worst slice, so
completion should make the window read worse, not better.

Full path re-read of the same window (user flagged the cut above used only
E/R — asymmetry rule applied): bear_put in-window |MAE|/MFE **1.13** (mirrored
= path-vol by the standing rule), capture R/MFE −0.06, 59% of MFE≥+0.30 rows
round-trip to E<0 (exits recover about half: 32% still end R<0). bull_call
in-window is genuinely asymmetric — |MAE|/MFE **0.56**, capture +0.36, only
17% round-trip — so the bear-window inversion is not two flavors of noise; one
structure has real upside asymmetry there and the other doesn't. Month
asymmetry marches 0.89 (Feb) → 1.11 (Mar) → **4.34** (Apr: MFE +0.215,
mfe_day 8.5, MAE −0.934 late = bought the bottom, small pop, rebound ran them
to −100%). Even Feb's positive R (+0.125) sits on 64% round-trip — exits
harvesting path-vol, not direction. bull_put's in-window failure is the
opposite shape: |MAE|/MFE 2.21, capture −0.53, LOW round-trip (23%) — genuine
adverse direction (E-VOL short-put), not path-vol; different problem, different
cell (the RANGE/BEAR+E-VOL screen). Real-tier bear_put is the most favorable
path read (0.82, MFE med +0.70, mfe_day 13) and still E −0.134 with 48%
round-trip.

Qualifier sweep, same session (user hypothesis: "bear_put feels safer in bear
markets — maybe it's the qualification step"). Both bear windows cut
(Feb–Apr 2026 n=132 / Mar–Apr 2025 n=105); only the two pre-registered
qualifiers are decision-relevant, the rest is post-hoc:

- **"Safer" is TRUE as a tail claim** — in-window managed bear_put loses
  $14.6/row with 1% of rows at R≤−0.90 (min −$1.6k) vs bull_put −$141.8/row
  with **23%** at R≤−0.90 (min −$5.0k). Defined-risk debit + early MFE +
  shipped exits = small bounded losses. Safety yes; expectancy no — no
  qualifier cell is E-positive in both windows.
- **iv_spread ≤ 0 (shipped Tier-C rule): 6th right-signed confirmation** —
  2026 keeps R +0.089/+$3.9k (n=27) vs skips R −0.219 (n=6); 2025 same sign.
  But **99/132 window rows have iv_spread MISSING** (unenriched holdout
  dates) — the shipped qualifier is blind on 75% of the window; the action
  item is the existing 7-date backfill, nothing new.
- **|delta| 0.30–0.45 recorded cut: DEAD** — right-signed 2026 (E +0.142,
  n=17), sign-flips 2025 (E −0.972, R −0.161 vs outside +0.067). The
  addendum-14 "mean carried by tails" suspicion confirmed on the other window.
- **New post-hoc candidate, motivating only: LOW entry IV** — iv_entry_pct
  below-median is R-positive in BOTH windows (+0.051/+$6.0k · +0.347/+$20.5k,
  asym 0.57) and above-median negative in both (−0.120 · −0.298, asym
  1.39/1.89). Textbook mechanism (don't pay elevated vol for a debit spread
  late in a selloff) but confounded with episode age (IV rises into the
  bottom, and the timing split is the same shape), and E is negative in both
  low-IV halves (−0.481/−0.686) — it selects which bear_puts the exits can
  rescue, not an edge population. Park next to the early/late finding as
  probably one factor.
- score_total ≥ 70 anti-selects in both windows again (R −0.096/−0.301).

Net: qualification can move managed bear_put from ~breakeven to modestly
positive (early-episode ∧ low-IV ∧ iv_spread≤0 slices) but uncovers no
positive-E sub-population; the demotion question is expectancy, and stands.
Per addendum 13 none of this is decision-eligible — finish the backfill,
run the pre-registered study.

---

## 2026-07-27 — the pre-engine discretionary book, and the long-dated blind spot

Source: `portfolio/` (IBKR flex exports, 468 closed trades, 2025-02-03 →
2026-07-24, +$10,634). **This is pre-engine and mostly pre-June-2026** — it is
a portrait of how the operator trades by hand, NOT a test of the engine and not
a holdout. Treat every comparison below as directional, not evidential: n per
structure is 7–26, unconditioned by regime, and discretionary in sizing/timing.

### 1. What the discretionary book independently confirms

- **Cadence.** P&L per trade by same-day trade count is monotone decreasing:
  1/day +$119 (n=67) · 2–3/day +$25 (n=160) · 4–6/day +$9 (n=109) · 7+/day
  **−$18** (n=132). Win rate is flat (51–59%) across all four, so this is
  dilution, not worse reads on busy days. The ladder's 1–3 positions/day cap
  came from capital constraints, not this data, and it lands on the knee.
- **Concentration.** Top-3 trades = the entire book: ex-top-3 the book is
  **−$5,004** over 465 trades; ex-top-10 it is −$20,478. Compare the ladder's
  derivation finding (top-3/day = 28% of positions, 83% of book P&L).
- **DTE.** 0DTE −$541 · 1–14d −$1,857 · 15–45d +$5,940 · 45d+ +$7,093.
- **The bull_put DTE band reproduces out-of-sample.** His 26 bull put spreads,
  never seen by the engine: DTE ≤22 → n=14, **−$1,805**; 45–59 → n=4, **+$443**.
  That is the PROVISIONAL 45–59 preference in `deployment-rules.md` landing on
  independent, real-fill, human-executed data. Weak n, right sign.

### 2. What it contradicts (noted, NOT actioned)

The four engine verticals total **−$1,952** over 58 trades in his book; all
+$10,072 of profit came from naked/single-leg and calendars, which the engine
does not emit. Tier ordering also inverts: bull_call (Tier A) 36% win /
−$1,652 (n=14, one TSM trade = −$2,101 of it); bear_call (hard VETO) 86% win /
+$479 (n=7). **Not evidence against the ladder** — no regime conditioning, no
delta/DTE gating, tiny n, and discretionary entry timing. Recorded so it is not
rediscovered as novel later.

### 3. The long-dated blind spot (the real finding)

`deployment-rules.md` is **in practice a ≤60-DTE ladder, and not by design.**

Pooled across all `backtests/results*.csv` + `proxy_results*.csv` (203 unique
plays), 36% of what the engine emits is horizon ≥180:

| horizon | 14 | 60 | 180 | 720 |
|---|---|---|---|---|
| real-priced | 4 | 42 | 8 | 1 |
| proxy (skipped by real backtest) | 2 | 73 | 54 | 19 |

53 of 54 h=180 rows and **19 of 19** h=720 rows were skipped with
`skip_reason = no_history`. Barchart's options history does not carry those
contracts, so they never got real prices and never entered the ladder's
evidence base. Nothing in `ANALYSIS_PROMPT_CONTRACT` blocks long-dated —
`structure` already lists "long call", `horizon` already has 180/720 buckets,
and the DTE-discipline rule already says default ≥45 DTE. The pipeline has been
dropping the rows, not the prompt.

**The BS proxy cannot substitute here** (user challenge, correct — my first
suggestion, "fix `path_cap_days` and 73 rows become readable", was wrong):

- All 45 long-dated `bs_options_hist` rows have **`pct_real_days = 0.0`**. Not
  partially modeled — zero days of those paths came from a real quote.
- `_method2` (`scripts/backtest/proxy.py:450-478`) prices the target leg off a
  **donor contract at a different expiry**. For a 500-DTE leg the donor is
  necessarily far shorter-dated — that is why the real leg had no history. Term
  structure is unmodeled at the horizon where vega dominates. Worst possible
  place for flat-vol BS.

So the real evidence base is 21 rows, not 73:

| | n | mean | win | MFE | MAE |
|---|---|---|---|---|---|
| `strike_expiry_tweak` (real-priced), h≥180 | 21 | −0.46 | 24% | +0.41 | −0.96 |
| of which h=180 / h=720 | 20 / **1** | | | | |

**At h=720 there is no evidence either way (n=1).** The 21-row negative also
does not settle it: those are spreads (MAE −0.96 = defined-risk structures
going to near-total loss), and all are still scored under `path_cap_days: 120`
and `time_exit_dte_fraction: 0.75` — 23/49 h=180 and 14/17 h=720 rows exit
`cap_open`, i.e. marked at an arbitrary date rather than a real exit.

**Shape note.** The operator's three book-carrying trades were long-dated
*instruments* on **short holds**, not hold-to-expiry: TSM 276 DTE held 69d
(25% of DTE), GLD 246 DTE held 82d (33%), GOOG 205 DTE held 121d (59%). Buying
convexity with theta off, then leaving on the move. The current exit config
would hold that TSM call 207 days. Any future long-dated test must model this
shape, not hold-to-expiry.

**Status: BLOCKED, not queued.** The blocker is real long-dated option price
history, and no re-read of existing rows fixes it. Only lead is IBKR
(`get_price_history` / `get_option_data` over the connected MCP) — unprobed,
user deferred 2026-07-27. If IBKR has no depth on 180+ DTE contracts, the only
route is paper-forwarding long-dated plays live. Do NOT ship a long-dated tier
off BS rows.

### 4. Live substitution — the operator sometimes trades naked where the engine said spread

Reported by the user 2026-07-27. When the analysis emits e.g. a bull call
spread, he sometimes buys the naked long call instead.

**Why it matters:** it silently breaks the live walk-forward's attribution. A
naked long call and its debit spread share direction and entry but not payoff,
max loss, vega, or exit behaviour — the spread caps upside where the naked leg
carries the convexity that produced 100% of this book's profit. Any live-vs-tier
comparison that assumes the deployed position matches the emitted `structure`
will mis-attribute both wins and losses, in the direction of making the ladder
look wrong when the substitution was the variable.

**Action:** the live walk-forward eval must record the **structure actually
traded** alongside the emitted one and split on divergence, before any live
result is read against tier means.

`backtests/live_loop/stage1_map_fills.py` already derives both sides —
`classify_structure()` from the IBKR fill and `play_structure()` from the play
text — but its match confidence is only `EXACT` / `STRUCTURE` / `NONE`, with no
substitution category. A naked long call filled against a `bull_call_spread`
play therefore falls to **`NONE`, indistinguishable from "no play that day"**:
substitutions are silently dropped from the eval rather than labelled.

> **CORRECTED 2026-08-11 (v3 close-out §3): the paragraph above is wrong.** Such
> a fill did NOT fall to `NONE` — `SIDE` maps `long_call` and `bull_call_spread`
> both to `debit`, so the family branch labelled it `STRUCTURE` and pooled it in
> as a match. Not dropped: *miscounted*, which is worse. A second defect (the
> branch ignored direction entirely) is fixed in the same change. Read the
> close-out entry, not this paragraph.

Adding a
`SUBSTITUTED` confidence (same ticker, same direction, different structure) is a
precondition for the eval, not a nice-to-have — otherwise the deployed book
being read is exactly the subset where he followed instructions, which biases
the live-vs-tier comparison in an unknown direction.
This is also the one channel through which the long-dated question could get
answered by accident: if he substitutes naked long-dated calls for h≥180
spreads, those fills are real prices on exactly the contracts the backtest
cannot reach.

---

## 2026-07-22 — bear_put demotion: the open thread

### 2026-07-22 addendum 11 — bear_put demotion CANCELLED: it is an exit-shape problem, not a selection problem (user challenge, correct)

**User challenge:** "we changed our exit and bear_put becomes profitable, why do
we demote it?" Prompted a structure × (MFE, MAE, realized) re-read of the 913-row
pooled export. The challenge was right and queue #4 is withdrawn.

**My error, retracted.** I argued bear_put had shallow upside and that "an exit
rule can only harvest MFE that already exists." The premise was false. The
asymmetry reads that seeded the demotion (bear_put × iv_spread MAE −0.197,
score_dealer MAE −0.320) are *correlations with* MFE/MAE, and I read them as
statements about bear_put's MFE *level*. They are not. Level, pooled: mean MFE
+0.713 (real-priced +0.788), median +0.398; 58% of rows reach +0.30, 29% reach
the +0.90 PT.

**Path shape is the finding** (real-priced):

| structure | MFE-first | mfe_day | mae_day | PT exit | stop exit |
|---|---|---|---|---|---|
| bear_put  | **77.3%** | 17.0 | 41.0 | 23.9% | **29.3%** |
| bull_call | 38.2%     | 37.9 | 25.1 | 42.0% | 13.5%     |

bear_put runs early then bleeds; bull_call dips then runs. Opposite exit
treatment. **Attempt 10 removed the debit trailing stop POOLED**, and the debit
pool is dominated by bull_call (n=312, the dollar weight) — the "21 trail exits
sold continuations" evidence is bull_call's signature. bear_put was never tested
on its own path shape.

**Give-back (conditions on MFE ≥ X — LOOKAHEAD, motivating only, does NOT price
the rule):** of 206 bear_puts reaching +0.30, 43.2% finished red; at +0.50,
32.5% of 157. bull_call at the same cuts: 23.2% / 16.9%.

**Ceiling test — settles the dead-money claim:**

```
bear_put   realized  −$38.6k   perfect-foresight exit +$296.9k   headroom $335.5k
bull_call  realized +$133.6k   perfect-foresight exit +$467.5k   headroom $333.9k
```

Same extractable headroom as the engine structure. "Half the debit book earning
nothing" (§addendum, line ~104) is wrong as a *selection* verdict — the emissions
are fine, the exit is mismatched.

**Queue change:** #4 bear_put emission demotion → **CANCELLED**. Replaced by
**structure-conditional trailing stop for bear_put**, to run through the existing
replay harness (`scripts/backtest_study/exit_mechanism_study.py`, `combined_exit_study.py`)
under the addendum-4 corrected LOO gate. Not run yet.

**New concern to test in the same pass — possible composition proxy.** The
SHIPPED BEAR+H/E trail .50/.50 (addendum 7, +$4.4k per-cell) may be this same
effect found through the wrong key: if BEAR+H/E dates emit disproportionately
more bear_puts, a regime-keyed override is a composition proxy for a
structure-keyed one — the trap that killed `oi_confirm` and `iv_pct` (rule 7).
Test structure-keying and regime-keying head to head, and check the bear_put
share of BEAR+H/E rows. If structure-keying dominates it is both simpler and
drops the runtime dependency on the SPY/VIX table (addenda 9/10).

No code changed. No re-run performed.

### 2026-07-22 addendum 12 — structure-keyed bear_put trail RUN: does NOT ship, and it exposes the shipped BEAR_HE clause as a bear_put proxy that is NEGATIVE outside one window

Ran the addendum-11 follow-up: `scripts/backtest_study/exit_switch_structure_study.py`
(output `backtests/exit_switch_structure_study_output.txt`). Data, calibration,
dedup, post-13c join and gate thresholds are IMPORTED from
`exit_switch_mech_study.py` — same 663-row pooled debit book (real 250 / tweak
247 / bs 166), same harness validation (250/250 real debit rows reproduce
DEBIT_PROD, replay total $27,648.70 = stored to the cent). Only the KEY differs,
so a difference in answer cannot come from a difference in setup. Treatment is
the SAME frozen variant the mech switch uses for BEAR_HE (trail .50 / trig .50).

**Q1 — structure-keyed bear_put trail: right-signed, but it is ONE WINDOW.**

    bear_put (n=343)  PROD mean −0.1242, win 35.6%
    + V_TRAIL         mean −0.0925, win 38.8%   Δ +10.87 pnl_pct / +$11,781

Concentration check (the Attempt-13 July-2024 discipline):

    ALL                n=343   Δ +10.866   +$11,781   win 35.6%→38.8%
    Mar+Apr 2025       n=102   Δ +10.183   +$11,037   win 40.2%→48.0%
    EX Mar+Apr 2025    n=241   Δ  +0.683      +$744   win 33.6%→34.9%

**94% of the gain is Mar–Apr 2025** (the tariff drawdown — precisely the regime
where a bear_put runs then bleeds). Dates are diffuse (top-5 dates = 11.7% of
total, 10/17 months positive), so this is not a single-trade artefact; it is a
single *market window*, which is worse for a rule meant to generalise. Ex-window
the effect is +$744 over 241 rows ≈ nothing. **Structure-keyed trail: NO SHIP.**

Gate for the record: 5/6 PASS, failing only "LOO median > 0" — which fails **by
construction** for every sparse-cell switch (most dates have no rows in the cell,
so the fold gain is exactly 0 and the median is 0). The mech switch failed the
identical criterion in addendum 4. The criterion is uninformative here and should
be replaced by "median over AFFECTED dates" in any future exit-switch gate.

**Q2 — the shipped BEAR_HE clause is a composition proxy, and a lossy one.**

Composition: bear_put is 51.7% of the debit book but **63.9% of BEAR_HE rows**
(+12.1pp lift); 53% of all bear_puts sit inside BEAR_HE. Decomposition, each key
run on the other's complement (pooled; BEAR_HE clause alone, LVOL/RB_EVOL
excluded so this matches what is actually in `config/backtest.yml`):

    slice                              n_changed    Δpnl_pct        Δ$
    BEAR_HE clause, all rows                 285      +3.657     +4,416
    BEAR_HE clause, NON-bear_put only        103      −4.676     −4,929
    bear_put trail, all rows                 343     +10.866    +11,781
    bear_put trail, OUTSIDE BEAR_HE          161      +2.534     +2,436
    overlap only (bear_put AND BEAR_HE)      182      +8.333     +9,345

The shipped clause retains **−128%** of its gain on its own complement; the
structure key retains +23% of its. The overlap alone (+$9,345) is larger than the
whole BEAR_HE cell (+$4,416) — the non-bear_put two-fifths of the cell actively
**lose** $4,929. So BEAR_HE is not merely a proxy for bear_put: it is bear_put
plus a money-losing tail the regime key drags in.

**And the shipped clause has the same window dependence:**

    BEAR_HE clause  ALL           n=285   Δ +3.657   +$4,416
                    Mar+Apr 2025  n=121   Δ +5.624   +$6,426
                    EX Mar+Apr    n=164   Δ −1.967   −$2,010

**The one rule currently in production off this line of work is negative outside
Mar–Apr 2025.** That is not the pre-registered rollback trigger (which asks for
≥25 affected BEAR+H/E dates of NEW data and is untouched by a re-cut of old
rows), so this is NOT an automatic revert — but it is a live warning, and it is
the same window that carries the structure result, so the two findings are one
finding: **trail .50/.50 helps debit trades during a sustained bear drawdown, and
the key — regime or structure — is mostly picking out how much of that window a
slice contains.**

**Decisions.**
1. Structure-keyed bear_put trail: **NOT SHIPPED.** Stays a candidate.
2. BEAR_HE clause: **left in production, rollback trigger UNCHANGED** — the
   trigger is pre-registered on new data and re-cutting old rows must not be
   allowed to relitigate it (that is exactly the discipline addendum 7 bought).
   But its evidence is now known to be window-bound; **if the trigger evaluation
   is ambiguous, revert** rather than extend.
3. Exit-gate criterion "LOO median > 0" is retired for sparse-cell switches —
   replace with median over affected dates when this is next run.
4. The exploratory grid says trail **.25/.50** dominates .50/.50 on bear_put
   (+13.50 / +$16,196 vs +10.87 / +$11,781) and BE@.50 is close (+12.05 /
   +$13,438). NOT ship-eligible off this run (chosen post-hoc from the grid, and
   subject to the same Mar–Apr concentration). Recorded so the next credit- or
   bear-heavy window tests the right knob first.

**What would settle it:** a second sustained bear drawdown in the book. Until
then, both the shipped clause and the structure candidate rest on one window.

No production config changed. New file: `scripts/backtest_study/exit_switch_structure_study.py`
(read-only study, imports the mech harness).

### 2026-07-22 addendum 13 — PRE-REGISTRATION: bear-position study (written BEFORE the run)

Reason this is pre-registered rather than another cut: addenda 11–12 produced
three different verdicts on bear_put in one session (demote → don't demote →
maybe demote) because each was a post-hoc slice of the SAME 663-row book,
reported as a verdict. On a book this dominated by one window, post-hoc slicing
will keep generating verdicts. Everything below is fixed before running.

**Population.** All bear-direction plays in the pooled priced debit book
(real + proxy tweak + proxy bs, same loader/calibration as addenda 4/12).
Primary: `bear_put_spread`. Comparator: `bull_call_spread`. Any
`bear_call_spread`/`long_put` rows counted and reported, not analysed.

**Two outcome measures, both reported on every cut.**
- **E = `pnl_at_cap_pct`** — P&L at the last priced path day, computed
  independently of any exit rule (`simulate.py:267`). This is the SELECTION
  measure: no exit rule can rescue a structure whose E is negative.
- **R = `realized_pnl_pct`** under PROD — SELECTION + EXIT.
Discriminator: E<0 ⇒ selection problem. E>0 with R<0 ⇒ exit problem. This
replaces MFE, which addendum 11 leaned on and which only bounds the upside a
perfect exit could have reached.

**Window control.** W = Mar+Apr 2025 (declared now, from addendum 12: it
carries 94% of the structure-trail gain and flips the shipped BEAR_HE clause).
Every headline is reported ALL / IN-W / EX-W. Pricing tier (real / tweak /
bs-model) reported alongside per the standing split rule.

**Cuts — fixed, complete, no additions after the run.**
- C1 levels by structure × window, on E and R
- C2 date-clustered bootstrap (10k, cluster = signal_date) 95% CI on mean E and
  mean R for ex-window bear_put
- C3 time halves + per-month sign count, on E
- C4 mech cell × structure, on E
- C5 entry geometry — |delta| bands, DTE bands, `iv_entry_pct`, `iv_spread`
  sign — on E, ex-window decision-eligible, in-window reported only
- C6 deployment ladder (config/deployment-rules.md): do the existing vetoes /
  tiers already screen the bear_put losers?
- C7 path shape: mfe_day vs mae_day, and the MFE→E give-back

**Decision rule — fixed now.**
- **DEMOTE to veto** iff ex-window mean E < 0 AND the C2 bootstrap 95% CI upper
  bound < 0 AND both C3 halves negative.
- **CONSTRAIN** (Tier-C→B style entry-geometry rule) iff some C5 cut is positive
  ex-window in BOTH halves with n ≥ 30.
- **NO ACTION** otherwise. Explicitly: no decision may rest on in-window
  numbers, and no cut invented after seeing the output is decision-eligible.

**This is the last cut of this book on the bear_put question.** Any further
change to bear_put's treatment requires new data, not a new slice.

### 2026-07-22 addendum 14 — bear-position study RUN: DEMOTE fires on all three pre-registered criteria; bear_put is a SELECTION problem, not an exit problem

`scripts/backtest_study/bear_position_study.py` → `backtests/bear_position_study_output.txt`.
Cuts, window control and decision rule were fixed in addendum 13 before the run;
nothing was added after seeing output. Same 663-row pooled debit book, same
harness validation (250/250 real rows reproduce DEBIT_PROD to the cent).

**The number that settles it — E, hold-to-cap, EXIT-FREE (`pnl_at_cap_pct`):**

    bear_put   ALL   n=343  mean −0.414  median −0.928  win 27.7%   −$160,256
               IN-W  n=102  mean −0.674  median −0.988  win 15.7%    −$76,329
               EX-W  n=241  mean −0.304  median −0.670  win 32.8%    −$83,927
    bull_call  EX-W  n=228  mean +0.423  median +0.265  win 57.0%   +$101,380

With no exit rule at all, the median bear_put is a −93% loss. R (realized under
PROD) is −0.124 — i.e. **the current exit rule is already rescuing ~0.29 of
mean P&L**, and the thing underneath it is far worse than realized P&L showed.
That is the reverse of addendum 11's conclusion and it is the direct test
addendum 11 lacked: MFE bounds what a perfect exit *could* reach; E measures
what the position is worth without one.

**Decision-rule evaluation (pre-registered):**

    [PASS]  ex-window mean E < 0                  (−0.304)
    [PASS]  date-clustered bootstrap 95% CI < 0   ([−0.433, −0.175], 10k, cluster=date)
    [PASS]  both time halves negative             (early −0.289, late −0.322)
    VERDICT: DEMOTE TO VETO

**It is not the window, and not the pricing tier.** Negative in 14/17 months;
negative in every mech cell (BEAR_HE −0.281, LVOL −0.301, RB_EVOL −0.497,
PROD −0.254 — all EX-W); negative in every pricing tier (real −0.431, tweak
−0.383, bs −0.045). Every prior explanation I offered for bear_put — exit shape,
regime key, Mar–Apr window — was a local slice of a structure that loses
everywhere on this book.

**Path shape, reinterpreted.** bear_put MFE +0.691 with give-back to E of
**1.105** and MFE-first 72.0%; bull_call MFE +1.281, give-back 0.566, MFE-first
40.2%. bear_put reliably runs and then round-trips *past zero*. Addendum 11 read
the excursion as harvestable edge; with E on the table it reads as volatility,
not direction. A trailing stop harvests some of it (addendum 12: +$11.8k, 94%
in-window) but cannot make a −0.414 expectancy positive.

**Ladder interaction (C6): the operational change is smaller than it sounds.**
Every bear_put already lands in VETO (n=36, mean E −0.894) or Tier C (n=307,
mean E −0.358); none ever reach Tier A or B. Under the shipped top-3/day
ladder, bear_puts are already largely not deployed. Whole-book tier means on E
stay monotone (A +0.907, B +0.482, C −0.355, VETO −0.510), and hold EX-W
(A +0.414, B +0.445, C −0.285, VETO −0.785) — A/B invert slightly EX-W, worth
noting but not a ladder failure.

**CONSTRAIN candidate, reported and NOT taken.** `|delta| 0.30–0.45` was the one
cut passing the pre-registered n≥30 / both-halves-positive filter (n=36 EX-W,
mean +0.097, halves +0.065 / +0.129). Its median is **−0.767** and its total is
+$2,465 — a mean carried by a couple of tails on 36 rows. The pre-registered
rule puts DEMOTE first and it fired; recording the cut so it is not re-discovered
as a novelty later.

**The honest caveat, which is a portfolio question and not a statistical one.**
The book spans 2024-06 → 2026-03, a period with exactly one sustained drawdown.
bull_call beat bear_put even *inside* mechanical BEAR cells (EX-W +0.326 vs
−0.281). So this may be measuring "the sample was a bull market" as much as
"the model is bad at bearish calls" — the two are not separable on this data.
A structure veto on bear_put removes essentially all downside exposure from the
system. That is a deliberate choice to make, not a mechanical consequence of a
p-value.

**Status: verdict reached, NOT yet implemented.** Implementation options (intake
structure_veto like bear_call vs ladder VETO tier vs leave at Tier C and simply
never deploy) are a user decision. Per addendum 13 this is the last cut of this
book on the bear_put question — any revision needs new data.

---

## 2026-07-22 — Feb–Apr 2026 bear holdout: coverage + backfill status

The addendum-13 pre-registration ends "this is the last cut of this book" —
so the DEMOTE verdict needs **new** data, not another slice. The only genuine
holdout available is the second sustained drawdown: **2026-02-05 → 2026-04-07**,
32 trading days, all of them mechanical `BEAR_HE` (BEAR + H/E-VOL), VIX peak
31.0, SPY −7.9%. The current book samples it with **6 dates**.

Why not the Iran window instead: checked against the frozen `lib/mech_regime.py`
labels, 2025-06-02 → 2025-07-15 is **BULL on every single day** (26 L-VOL /
3 H-VOL / 1 E-VOL), SPY 592.71 → 622.14, VIX peak 21.6. A vol blip inside an
uptrend — it would add the cell the book already has most of, not a bear cell.

### Status table

Drive coverage + enrichment fill read 07-22. "Analyzed" = has rows in the
AnalysisClaude tab (the only source of truth for analysis state — see the
queue-file drift note in archive/05). Enrichment columns are the **fill rate of
each collector's marker column** on `stocks-flow-*-compiled.csv`
(`oi_enriched_on`, `iv_pct_enriched_on`, `price_catalyst_enriched_on`) and the
row count of the `counterpart-iv-*.csv` sidecar — measured, not inferred from
the `.done` queue files. Every date is either 0% or 100%: enrichment is
all-or-nothing per date, so there is no partial-fill case to handle.

Row counts are 498–501 on all 26 compiled stocks files; etfs compiled is
present everywhere except 2026-03-18. Nothing here is a dropped stage — the
lean-enrichment profile was SHELVED on 2026-07-21 (archive/05, "NO scraper is
droppable"), so these are gaps to fill, not decisions to honour.

| # | Date | In Drive | Analyzed | oi/eod_iv | iv_pct | p/cat | cpart | Next step |
|---|------|----------|----------|-----------|--------|-------|-------|-----------|
| 1  | 2026-02-05 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ iv-pct + ✅ p/cat + ✅ counterpart → ✅ analyze |
| 2  | 2026-02-12 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 3  | 2026-02-13 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 4  | 2026-02-17 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 5  | 2026-02-19 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 6  | 2026-02-23 | yes | ✅ | **0%** | 100% | 100% | 260 | ⚠ in book WITHOUT eod_iv — see flaw note |
| 7  | 2026-03-02 | yes | ✅ | **0%** | **0%** | **0%** | **0** | ⚠ in book with NO enrichment at all |
| 8  | 2026-03-03 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 9  | 2026-03-04 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 10 | 2026-03-05 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 11 | 2026-03-06 | yes | ✅ | 100% | 100% | 100% | 278 | in book, complete |
| 12 | 2026-03-09 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 13 | 2026-03-10 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 14 | 2026-03-11 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ full chain → ✅ analyze |
| 15 | 2026-03-12 | yes | ✅ | 100% | 100% | 100% | 84 | in book, complete |
| 16 | 2026-03-13 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 17 | 2026-03-16 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 18 | 2026-03-17 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 19 | 2026-03-18 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze (etfs compiled absent) |
| 20 | 2026-03-19 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 21 | 2026-03-20 | yes | ✅ | 100% | 100% | 100% | **0** | ⚠ in book with BLANK iv_spread |
| 22 | 2026-03-23 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 23 | 2026-03-24 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 24 | 2026-03-25 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 25 | 2026-03-26 | yes | ✅ | 100% | 100% | 100% | 100% | full chain → analyze |
| 26 | 2026-03-27 | yes | ✅ | 100% | 100% | 100% | 253 | in book, complete |
| 27 | 2026-03-30 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 28 | 2026-03-31 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 29 | 2026-04-01 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 30 | 2026-04-02 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 31 | 2026-04-06 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |
| 32 | 2026-04-07 | yes | ✅ | 100% | 100% | 100% | 100% | ✅ scrape → ✅ compile → full chain → analyze |

**26/32 in Drive · 6/32 analyzed · 3 of those 6 input-incomplete · 6 need
scraping.** (2026-04-03 is Good Friday, so 03-30 → 04-07 is 6 trading days.)
Wider Drive audit: 26 weekdays are missing in 2026-02-01 → 2026-07-22, and
**all 22 weekdays of 2026-04 are absent** — the 6 above are the subset inside
the bear episode; the rest of April is a separate gap.

Stage totals to fill across the 26 in-Drive dates: `enrich_oi` 21 ·
`fetch_iv_percentile` 21 · `fetch_price_catalyst` 21 · `fetch_counterpart_iv` 22.

**Scrape 2026-04-08 as well.** `enrich_oi` reads D+1 open interest, so the last
episode date (04-07) cannot be enriched without it, and 04-08 is inside the
missing-April block. It is not itself a holdout date — it is an input.

### The three flawed in-book dates (decision needed)

The existing 6-date sample of this episode is **not** input-consistent, and the
inconsistency lands on `iv_spread` — the bear_put Tier-C column, i.e. the exact
variable the holdout is meant to test:

- **2026-03-02** — analyzed with zero enrichment. No `oi_confirm_pct`, no
  `iv_pct`, no `iv_spread`.
- **2026-02-23** — counterpart sidecar present (260 legs) but traded-leg
  `eod_iv` absent. This is the failure mode the shelving note names: counterpart
  legs are *always* EOD, so without `eod_iv` the matched pair compares intraday
  against EOD IV. `iv_spread` here is **silently wrong**, not missing — worse
  than a blank, because nothing downstream flags it.
- **2026-03-20** — traded-leg enrichment complete but no counterpart sidecar, so
  `iv_spread` is blank. Honest gap, at least.

Re-running `analysis_pipeline` on these **appends** rows rather than replacing
them, so fixing them is a duplicate-row decision, not just a re-run. Open
options: (a) leave them and note the holdout's 6 pre-existing dates are mixed
quality; (b) enrich, re-analyze, and delete the original rows. Unresolved —
does not block enriching the other 20.

### Sequence

1. **Scrape the 6 + 04-08** (user is running this):
   `python3 scripts/collector/scrape_flow.py --start 2026-03-30 --end 2026-04-08 --skip-existing`
2. `compile_flow.py` on the newly scraped dates.
3. Enrichment chain, batched by stage over the gap lists above —
   `enrich_oi`, `fetch_iv_percentile`, `fetch_counterpart_iv`,
   `fetch_price_catalyst`. All four stay in (archive/05); none is optional.
4. `python3 -m scripts.analysis_pipeline --date <D>` for the 26 unanalyzed
   dates — **config unchanged**, or the holdout stops being a holdout.
5. `python3 -m scripts.backtest` + `python3 -m scripts.backtest.proxy`.
6. Re-run `scripts/backtest_study/bear_position_study.py` **unmodified** against the
   Feb–Apr 2026 rows only. The pre-registered decision rule from addendum 13
   applies as written: DEMOTE iff mean E < 0 AND bootstrap CI upper < 0 AND
   both halves negative.

If the holdout agrees, the demotion ships and the "sample was a bull market"
caveat in addendum 14 is answered by a second independent drawdown. If it
disagrees, bear_put stays at Tier C and the 2024-06 → 2026-03 result is
recorded as window-bound. Either way the decision is made once, on the
holdout, and not by re-cutting the 663-row book again.

### 2026-07-29 — PRELIMINARY holdout read (backfill incomplete — NOT the decision run)

Backfill in progress; read taken from the Sheets tab exports
(`backtests/analysis - BacktestResults.csv` / `- BacktestProxy.csv`, pulled
07-29), holdout window rows only. Coverage: **12 dates priced** (02-05 → 03-27;
02-24/02-25 now analyzed beyond the status table above), 115 priced rows, 5
unpriced (3 no_history / 2 unsupported). Scratch script only — the decision run
stays `bear_position_study.py` unmodified once the window is fully backfilled.

**bear_put_spread, n=67 priced — all three pre-registered criteria fire on the
partial sample:**

    mean E −0.242   date-clustered bootstrap 95% CI [−0.370, −0.077]  (12 dates)
    halves: early −0.205 (n=28) · late −0.268 (n=39)
    ex-flawed-dates (02-23/03-02/03-20 excluded): mean E −0.214 (n=51), still negative

R (PROD) −0.073 — the exit rule is again rescuing ~0.17 of mean E, same
signature as addendum 14. Path shape repeats too: MFE +0.609 / MAE −0.621,
run-then-round-trip. And this window IS a bear drawdown — the most favourable
conditions bear_put will ever see — so the addendum-14 "maybe the sample was a
bull market" caveat is, preliminarily, not holding up. Comparator bull_call:
mean E +0.150 (n=18, but ex-flawed only n=6 at −0.138 — too thin to read).

**One discordant cut to watch: the pure-real tier is POSITIVE** — real n=16
mean E +0.177 (win 62.5%) vs strike_expiry_tweak n=34 mean −0.471 and bs n=17
mean −0.177. Real+tweak pooled is still −0.26, and tweak rows are real-priced
(only bs is model-priced), but if the final run still shows real-tier-positive /
tweak-tier-negative, the tweak fallback itself (strike/expiry substitution on
bear_puts in a fast tape) needs a look before the verdict is read as clean.

**MFE/MAE cut (standing rule — realized alone is not a read):**

    structure   n   MFE     MAE     |MAE|/MFE  MFE-first  give-back  R-capture
    bear_put    67  +0.609  −0.621    1.02       59.7%      0.851      −0.12
    bull_call   18  +1.108  −0.574    0.52       55.6%      0.958      +0.40
    bull_put    27  +0.559  −1.347    2.41       44.4%      0.738      −0.41

- bear_put's excursions are **perfectly mirrored** (ratio 1.02) — by the
  asymmetry rule that is path-vol, not harvestable edge; 58% of rows reaching
  +0.30 still end E<0 (old book: 43%). bull_call keeps upside asymmetry (0.52)
  *inside the drawdown*, and its exit capture is +0.40 of MFE vs bear_put's
  −0.12 — same discriminator as addendum 14: exit harvesting works on
  bull_call, nothing on bear_put rescues a negative-E selection.
- The addendum-14 bear_put signature (MFE-first 72%, give-back 1.105) lives in
  the **tweak tier** here (70.6% / 1.095, MAE med −0.926); the real tier looks
  different in kind: MFE +0.885 / MAE −0.546 (ratio 0.62), mfe_day 12.4, 44%
  reach the +0.90 PT, E +0.177. Reinforces the real-vs-tweak discordance above —
  on the final run, check whether tweak's strike/expiry substitution is
  manufacturing the round-trip shape before reading the pooled number.
- bull_put side note (thin): ratio 2.41 with 59% reaching +0.30 and only 6% of
  those ending E<0 — deep-MAE-then-recover, the Attempt-13 whipsaw shape; its
  real-tier R (−0.304) undershoots E (+0.009) via dollar_stop exits. Watch, not
  actionable.

Loose ends for the backfill: **2026-02-17 is analyzed but absent from BOTH
backtest tabs** (0 rows in Results and Proxy — backtest apparently never run on
it); late dates are the most negative (03-20 −0.53, 03-27 −0.52), and the
still-missing late-March/April dates sit closest to the episode bottom, so
completing coverage is more likely to strengthen than soften this read.
No config changed. No decision taken — waits on the full window.

### 2026-08-04 — MID-STOP check (backfill still incomplete — NOT the decision run)

Read off the refreshed `backtests/results.csv` (364 rows) + `proxy_results.csv`
(675), window rows only, deduped on date|ticker|play|structure. Scratch script,
read-only, no config changed. Purpose is to catch problems before the decision
run, not to decide.

**Coverage: 16 dates / 137 priced rows** (07-29: 12 / 115). 14 of the status
table's 32 dates, plus 02-24 and 02-25 which are not on it. Still missing 18,
including the whole late-March block (03-11 → 03-26 except 03-20) and all of
03-30 → 04-07 — i.e. everything nearest the episode bottom. 6 unpriced
(5 no_history / 1 unsupported).

**bear_put: DEMOTE fires again, and harder.** n=82 (was 67).

    mean E −0.254   bootstrap 95% CI [−0.392, −0.091]  (16 dates, cluster=date)
    halves: early −0.100 (n=29) · late −0.338 (n=53)
    ex-flawed-dates n=66, mean E −0.235
    R (PROD) −0.040 → exit rule still rescuing ~0.21 of mean E

All three pre-registered criteria pass on the partial sample, second time
running, with the late half more negative than the early — the added dates
moved the read away from zero. Comparator bull_call n=20: E +0.187, R +0.463,
|MAE|/MFE 0.51, R-capture +0.43 vs bear_put's −0.06. Same discriminator as
addendum 14; bear_put excursions still mirrored (0.97).

**Four things to fix before the decision run — all mechanical, none of them
change the verdict, but two would corrupt it:**

1. **`2026-03-06` is duplicated wholesale in BOTH tabs** — in BacktestResults,
   10 plays each appearing twice with identical legs/play/P&L (it is the only
   20-row date in the window; every other is ≤11), and separately in
   BacktestProxy (GLD/MU/USO bull_puts, same doubling). The study loader
   (`exit_switch_mech_study.load_debit_trades`) dedups proxy-against-real via
   `real_keys` but has **no within-real dedup**, so an unmodified re-run
   double-weights that date. My numbers above dedup it; the decision run will
   not unless the loader is patched.
2. **The study scripts read the wrong files.** `AC_PATH`/`BR_PATH`/`BP_PATH`
   point at `backtests/to_evaluate/analysis - *.csv`, exports dated **07-22**
   holding only 8 window dates. `bear_position_study.py` re-run "unmodified"
   would read stale data. Refresh those exports (or repoint the paths) as step 0
   of the decision run.
3. **The real-vs-tweak discordance flagged on 07-29 has grown, not resolved:**
   real n=22 mean E **+0.201** (win 63.6%) · tweak n=39 **−0.514** · bs n=21
   −0.246. Real+tweak pooled −0.256. The whole demotion currently rests on the
   proxy tiers being trustworthy on bear_puts in a fast tape. Caveat in the
   other direction: 6 of those 22 real rows are the duplicated 03-06 IWM/TSLA
   pairs, so the real tier is effectively n=18. This needs settling before the
   verdict is called clean — it is now the largest open risk on the demotion.
4. **02-17 and 02-19 are still absent from both backtest tabs** (07-29 flagged
   02-17 only). The status table marks both analyzed with the full chain. Either
   the backtest was never run on them or the analysis rows are not actually
   there — worth a direct Sheets check, not another export.

**New, unrelated to bear_put: the shipped bull_put band gets its first
out-of-sample look, and it holds.** Pooled window bull_put is bad (n=33,
E −0.450, R −0.451, |MAE|/MFE 2.75, late half −0.733) — but split on the rule
actually in `deployment-rules.md`:

    0.08 ≤ |delta| ≤ 0.20 AND DTE ≤ 59    n= 9   E +0.180   R +0.152
    out of band                           n=24   E −0.686   R −0.677

Out-of-band is DTE-driven, not delta-driven: DTE>59 n=18 E −0.898, |delta|<0.08
n=11 E −0.632, |delta|>0.20 n=2 E −0.048 (rows can fail both legs). 6 of the 9
in-band rows finish positive (median E +1.00); the mean is dragged by one
SMH −2.66. Thin and one-window, so not a promotion — but it is the first
independent window where the constraint separates the book, and it separates it
by 0.87 of mean E. Do NOT read the pooled bull_put number as evidence against
the structure; it is an out-of-band number.

**Lead worth chasing on the long-dated blind spot (2026-07-27 §3).** Five rows
in this window are real-priced at DTE ≥ 180 with `pct_real_days = 1.0` —
TLT 707/689/687 (two bull_call spreads + a long_call) and HYG 197/191. So
Barchart history at 180–700 DTE is not universally absent; it appears to be
ticker-dependent (bond/credit ETFs have it). n=5 does not unblock anything, but
"h≥180 cannot be priced" is too strong as stated — the cheap next step is a
coverage probe by ticker before assuming IBKR is the only route.

#### Same-day addendum — does E survive "we never hold to expiry"?

Operator objection (2026-08-04): positions are closed early in practice, and
credits especially are closed before terminal gamma. E is a hold-to-cap mark, so
does it measure a counterfactual we would never trade? Checked both reads:

**bull_put band: survives.** 30% of window bull_put rows sit at E = +1.00
(structural max = expired worthless), and 5 of the 9 in-band rows are among them
— so the E-based band number IS partly a hold-through-gamma artifact. But R
already prices the early close (credit PROD = `profit_target 0.65`, no stop, no
time exit; only 2 of 33 rows exit `expired`), and the split holds under R alone:
in-band R +0.152 (median +0.666) vs out-of-band R −0.677. Conclusion unchanged.

**bear_put DEMOTE: the verdict is measure-dependent. Recorded, not resolved.**

    criterion          mean      CI 95%             halves           verdict
    E (hold-to-cap)   −0.254   [−0.392, −0.091]   −0.100 / −0.338   DEMOTE
    R (PROD exits)    −0.040   [−0.218, +0.177]   +0.221 / −0.183   NO ACTION

Pre-registration picked E deliberately, and three things still argue for it
here: (a) R's rescue is exit-driven — 32 of 82 bear_put rows (39%) exit on a
risk control (`stop_loss` 14, `dollar_stop` 10, `trailing_stop` 8), i.e. the
structure reaches breakeven only by being cut fast; (b) **no transaction cost is
modelled anywhere** — `spread_width_pct` is the synthetic short-strike width,
not bid/ask, and fills are the Barchart Open, so realistic two-leg fills in a
fast tape push R below zero; (c) R's halves run +0.221 → −0.183, deteriorating
as the bear episode deepens, which is the wrong direction for a bear structure.
Still: the demotion should be stated as "negative unmanaged, breakeven only
under active risk control", not "loses money". Re-check on the full window.

**Real gap this exposes (new candidate).** `simulation.credit.time_exit_dte_fraction`
is explicitly `null` ("ride toward expiry within path_cap") while debits carry
0.75 — the credit profile does exactly the thing we would never do live, and
11 of 33 bull_put rows exit `cap_open`, i.e. ran to the 120-day path cap. A
gamma-motivated DTE-floor exit for credits (close at ~21 DTE) is untested and
cheap to sweep. Do it on the credit book AFTER the window completes; it is not
part of the pre-registered bear decision run.

---

## 2026-08-12 — v1 → v2 → v3 prompt-version comparison, and June-2026 live-vs-analysis audit

Run at operator request. Two questions: (1) did the prompt improve across
versions, (2) how did the June-2026 live book line up with what the analysis
actually emitted. Inputs are the CSV exports in `backtests/to_evaluate/`.
**Real + `strike_expiry_tweak` tiers only** — `bs_options_hist`,
`underlying_trend` and `unevaluable` excluded throughout, per the shipped
`proxy.bs_fallback` off decision.

### 0. Two data traps found on the way in — both would have flipped the answer

**`realized_pnl_pct` changes dtype across versions.** v1 stores it as a
percent STRING (`"1.64%"`, `"-100.00%"`); v2/v3 store decimal fractions
(`0.9994`). A naive `to_numeric` silently drops 153 of 255 v1 rows and leaves
a survivor subset whose median reads +0.60 — i.e. it manufactures a large fake
v1 edge. Any future cross-version pull MUST strip `%` and divide by 100 for v1.
This is the pre-`feedback_percentages_decimal` era leaking into the exports.

**v1 has no BacktestProxy export**, so v1 = 255 real rows with zero tweak tier,
while v2/v3 carry 53/411 tweak rows. Every table below is therefore reported
BOTH as real+tweak and real-only.

### 1. Version comparison — no improvement is measurable

Only **22 signal dates are common to all three** versions (2024-06-17 ..
2025-12-10). v1 covers 56 dates, v2 22, v3 118 (to 2026-04-07), so the
full-window numbers compare different market windows and are not a version
read. On the common window, real+tweak:

    ver    n    win    med E    mean E    total $    PF    med MFE   med MAE
    v1   101   0.554   +0.164   +0.091      8194    1.20    0.70     -0.99
    v2   168   0.488   -0.137   +0.054     14654    1.22    0.91     -0.97
    v3   162   0.481   -0.215   -0.043      4534    1.07    0.82     -0.99

Real-only is worse for v3 (n=101, win 0.455, mean E −0.107, total −$1,100, PF 0.97).

Date-clustered bootstrap on paired per-date mean E, 22 dates, real+tweak:

    v3 - v1   -0.183  [-0.367, +0.002]   n.s.
    v3 - v2   -0.154  [-0.305, -0.008]   SIG (does not survive real-only)
    v2 - v1   -0.029  [-0.268, +0.213]   n.s.

**Verdict: there is no evidence that v2 improved on v1 or that v3 improved on
either.** The single significant result points the wrong way and is
tier-fragile. Emission volume is flat across versions (10.9 / 10.9 / 11.5
analysis rows per common date), so v3 is not buying breadth either.

### 2. Why the comparison cannot be attributed to the prompt anyway

`created_datetime` shows the three books were priced by three different
backtest engines:

    v1 rows created 2026-06-21..06-25    entry_source real+barchart
    v2 rows created 2026-07-06..07-07    entry_source barchart_open+barchart_open
    v3 rows created 2026-07-09..08-10    entry_source barchart_open+barchart_open

The next-day-OPEN entry re-baseline (2026-07-06) lands exactly between v1 and
v2; the DEBIT trailing-stop removal (07-04) and credit `stop_loss` removal
(07-13) also fall inside this span — v1 has 0 `trailing_stop` exits, v3 has 31.
**Engine version is perfectly confounded with prompt version in these exports.**
Exit capture moves the same way (share of MFE>+25% rows that still close red:
v1 0.21, v2 0.37, v3 0.35), which is an exit-rule signature, not a selection one.

Nothing here should be read as "the prompt got worse". The correct statement is
that these exports **cannot answer the question**. To answer it, v1 and v2
analysis rows must be re-run through the CURRENT engine.

### 3. What the gap actually decomposes into (composition, not selection)

Common dates, <180 DTE, medians reweighted to v1's structure mix:

    v1   raw -0.074   v1-mix-weighted -0.079    (n=85)
    v2   raw -0.307   v1-mix-weighted -0.193    (n=141)
    v3   raw -0.488   v1-mix-weighted -0.228    (n=129)

Roughly half of v3's raw deficit is structure composition. Per-structure medians
on common dates:

    structure           v1(n)        v2(n)        v3(n)
    bull_call_spread   +0.528(52)   -0.285(74)   +0.383(56)
    bear_put_spread    +0.116(43)   +0.908(60)   -0.648(51)
    bull_put_spread    -0.803(1)    +0.666(20)   +0.668(35)
    bear_call_spread   -1.517(1)    -1.100(10)   -1.099(16)

Two things line up with already-recorded conclusions and one is new:

- **bear_call is toxic in all three versions** (−1.1 to −1.5). Consistent with
  the 2026-07-13 intake veto; the residual rows here are pre-veto.
- **bull_put is the one genuine v2→v3 gain**: emission share 12% → 20% at a
  stable +0.67 median. That is the shipped `deployment-rules.md` constraint
  showing up in composition.
- **bear_put swings +0.91 (v2) → −0.65 (v3)** on overlapping dates. This is a
  third independent sighting of the bear_put problem and it is NOT explained by
  the engine change alone, since bull_call recovers over the same span.

### 4. The whole book's dollars are long-dated, in every version

Common dates, real+tweak, total $ split at 180 DTE:

    ver     <180d      >=180d
    v1      +23       +8,170
    v2   +10,133      +4,522
    v3    -5,998     +10,533

v3's entire positive dollar result comes from DTE≥180 rows, and its <180d book —
the band the deployment ladder actually trades — is **negative**. These are
real-priced rows, not the bs tier, so this is a different observation from the
2026-08-11 "+$49k of DTE≥180 bs rows" contamination note. It sharpens
`project_longdated_blind_spot`: the ladder is ≤60 DTE by accident, and the
money in the backtest is somewhere the ladder does not go.

### 5. June-2026 live book vs the analysis — coverage gap first

**The v3 AnalysisClaude export contains ZERO June-2026 rows** (v3 months present:
Feb 110, Mar 251, Apr 44, Jul 198, Aug 64). June analysis lives in the v1 export
(107 rows, 06-10..06-24) and the v2 export (45 rows, 06-25..06-30), and there is
no coverage at all before 06-10. So June cannot be evaluated against v3, and no
June row carries `score_total` — **the deployment ladder was not applicable to
anything traded in June.**

Backtest coverage also stops at 2026-04-07, so there are no backtest rows for
June either. The audit below is live-trade vs emitted-play only.

IBKR trades carry no strike/expiry/right, so entries were reconstructed by
grouping fills on order timestamp and matching `average_price` against open
positions. 12 option entry events in June:

    date   tkr   live structure                  analysis that day        verdict
    06-05  NVDA  bull call spread Jun'27 LEAP    (none - no coverage)     UNCOVERED
    06-05  QQQ   debit spread                    (none - no coverage)     UNCOVERED
    06-10  MSFT  LONG CALL naked @41.37          bull call spd 410/480    SUBSTITUTED
    06-12  QQQ   debit spread                    bull call spd 725/760    MATCH
    06-15  NVDA  short call (overwrite)          bull call spd 185/210    OVERWRITE
    06-15  TSM   short call (overwrite)          (none that day)          UNCOVERED
    06-16  MU    bull put 920/940 (SOLD vol)     long strangle, VOL       CONTRADICTED
    06-22  INTC  bull put 115/130 (credit)       bull call spd 145/180    SUBSTITUTED
    06-23  AMD   debit spread                    bull call spd 600/720    MATCH
    06-23  SMH   bear put 470/440                bear put spd 600/540     MATCH
    06-30  NVDA  short call (overwrite)          (none that day)          UNCOVERED
    06-30  TSM   bull call spd 450/530 Dec       bull call spd 460/500    MATCH

4 clean matches, 2 substitutions, 1 direct contradiction, 2 overwrites,
4 uncovered (3 by date-gap, 1 by ticker-gap).

**The `SUBSTITUTED` category from `project_live_walkforward_in_progress` is now
observed twice and in two distinct forms**, which matters because they have
opposite sign:

- **06-10 MSFT — naked long leg where a spread was emitted.** Analysis said
  bull call spread 410/480 163DTE; the live trade was the long call alone at
  41.37, closed 06-22 at 29.63 for **−$1,176**. The emitted short 480 leg would
  have financed part of that. Substitution cost money.
- **06-22 INTC — credit structure where a debit was emitted.** Analysis said
  bull call spread 145/180 and explicitly flagged IV ~95% as "very rich",
  choosing a debit "to neutralize" it; the live trade was a bull PUT credit
  spread 115/130 — same direction, opposite vega. INTC then fell. Both reads
  were wrong on direction, but the emitted 145/180 debit spread would have been
  a near-total loss while the credit spread is at **−$793** unrealized.
  Substitution saved money, and did so by taking the side the analysis's own
  IV comment argued for.

**06-16 MU is the one outright contradiction**: the analysis called RANGE + E-VOL
into earnings and emitted a long strangle (buy vol, IV 99-120%); the live trade
sold vol via a 920/940 put credit spread. Worth logging because the analysis
itself hedged — its Alt clause said the two-sided flow "could be dealers/funds
selling earnings vol", which is the side actually traded.

**Attribution caveat — do not compute June-entry P&L from the current book.**
July is a wall of rolls (50 MU fills, 21 TSM fills between 07-01 and 08-11), so
`average_price` on most surviving positions no longer reflects the June entry.
Only two June entries are untouched: INTC 115/130 (avg 9.3576/15.9720 vs fills
9.35/15.98) at −$793, and NVDA Jun17'27 220C (avg 38.5614 vs fill 38.55) at
−$346. SMH, TSM and MU were all re-struck in July and their marks are NOT June
attribution. Likewise the +$4,966 realized inside June is mostly the 06-22 TSM
close (+$6,159) of an APRIL entry — it is not a June-selection result.

### 6. Actions

- **No rule change.** Nothing here clears a promotion bar.
- **Blocked:** the v1/v2/v3 question cannot be answered from these exports.
  Re-running v1+v2 analysis rows through the current engine is the only clean
  path; until then, treat "v3 is better" as unevidenced in either direction.
- **New watch:** v3 <180d real+tweak book is negative on common dates while
  >=180d carries all the dollars. Check this again on the full v3 window.
- **bear_put:** third sighting, now cross-version. Strengthens the standing
  DEMOTE candidate.
- **Live process:** June ran on v1/v2 prompts with no `score_total`, so the
  ladder was untested in live use. The first genuine live-vs-tier eval needs a
  month where the traded book and a scored analysis tab overlap — July is the
  first candidate (198 v3 rows).

---

## 2026-08-12 (same day, second run) — Stage 1 live-vs-tier eval on July

Follow-up to the section above: July was the first month where the traded book
overlaps a scored v3 analysis tab, so the live-vs-tier eval was finally runnable.
Re-ran `scripts/live_loop/stage1_map_fills.py` on a fresh **2026-08-12** IBKR
snapshot (206 trades vs the old snapshot's 53; 19 open option positions vs 17).

### 0. Four code fixes the wider snapshot forced

The module had only ever seen a 53-trade window. Widening it broke it:

1. **Crash on a non-business-day fill.** `np.busday_offset(fill, -1)` raises on a
   weekend date; IBKR stamped two rows 2026-08-08 (Saturday). Now
   `roll="forward"`, so a Saturday fill resolves to the prior Friday.
2. **Zero-price settlement rows became phantom entries.** A `price == 0` /
   `realized_pnl == 0` row is expiry/assignment bookkeeping, not a fill. They are
   now dropped before entry reconstruction and reported in the header. Zero-price
   rows WITH realized_pnl stay in the closing ledger — those are real expiry P&L.
3. **NONE reasons were collapsed into one misleading label.** Every unmapped
   entry rendered as "no same-ticker play", which reads as "the analysis never
   covered this". False for 21 of them — see §2. Now split four ways.
4. **Snapshot path was hardcoded**; now defaults to the newest
   `ibkr_snapshot_*.json`, with `--snapshot` to re-run an older one, and the
   report name carries the snapshot date so re-runs never clobber.

Two assertions in the generated caveats were also stale and are now computed
rather than asserted.

### 1. The July result — selection compliance

Pooling the mapped entries from BOTH snapshots (see §2 for why pooling is
mandatory) gives **8 mapped live entries**, 2026-07-14 → 2026-08-10:

    signal date  tkr   live structure       confidence    tier   top avail
    2026-07-14   TSM   bull_put_spread      STRUCTURE     VETO   C
    2026-07-16   META  single short put     SUBSTITUTED   VETO   A
    2026-07-17   QQQ   bear_put_spread      STRUCTURE     C      C
    2026-07-28   SMH   bear_put_spread      STRUCTURE     C      A
    2026-07-30   HYG   single long put      SUBSTITUTED   C      C
    2026-08-04   IWM   bear_put_spread      EXACT         C      B
    2026-08-05   TSM   bull_call_spread     STRUCTURE     B      B
    2026-08-07   GLD   bull_call_spread     STRUCTURE     B      B

**4 of 8 were in the top available tier. 2 landed in a VETO cell. Zero Tier-A
plays were ever deployed** — including 07-16 and 07-28, where an A was on the
board and a VETO / C was taken instead.

Both VETO hits are the same cell: **a credit play in RANGE + L-VOL**. That is one
rule, violated twice, and it is the single highest-value thing to fix in live
process. Note 07-16 META is also a SUBSTITUTED row — a naked short put where a
bull_put_spread 620/580 was emitted — so it violates the veto by a route the
analysis never proposed.

### 2. Methodological finding — mapping decays, snapshots are not supersets

Contract identity is inferred by joining a fill price to an open-position
`average_price`; the trades payload has no strike/expiry/right. **Once a
round-trip closes, its identity is unrecoverable.** So the 2026-07-22 snapshot
maps the 07-15 TSM bull_put and 07-20 QQQ bear_put that the 2026-08-12 snapshot
reads as UNKNOWN — those positions have since closed.

**A later snapshot is not a superset of an earlier one.** On the 08-12 snapshot,
21 of 59 unmapped entries fall on dates that DID carry a same-ticker play but
whose live structure could no longer be resolved. Snapshots must be taken on a
regular cadence and their mapped sets pooled. Both facts are now written into
the module's caveats so the next run cannot forget them.

This also relocates the Stage-2 bottleneck. Closed round-trips are no longer
scarce (54, vs the ~30–50 threshold) — **mappability** is the constraint: only 8
entries map at all, across two snapshots.

### 3. P&L, with the attribution caveat that matters

The June audit could not attribute P&L because July rolls had moved every
`average_price` off its entry fill. For the mapped entries this problem solves
itself: **the price-join only matches when `average_price` ≈ the entry fill, so
mapped-and-open entries are by construction un-rolled.** All six open mapped
entries check out (largest gap $0.011/share). Unrealized, as of 2026-08-12:

    tier B     n=2    -$65     (GLD +82, TSM -146)
    tier C     n=3   -$733     (IWM -28, HYG -29, SMH -676)
    tier VETO  n=1   +$726     (META)
    ALL        n=6    -$72

**This does not validate or refute the ladder** and must not be quoted as
evidence: n=6, all unrealized marks on open positions, no exits taken, and the
single VETO row is the best performer. It is recorded so the next snapshot has a
baseline to move against. The ordering is currently the reverse of what the
ladder predicts, on a sample far too small to mean anything.

### 4. Actions

- **No rule change.** n=8 mapped entries decides nothing.
- **Live process, actionable now:** the RANGE + L-VOL credit veto was breached
  twice, and Tier A was passed over twice when available. Both are checkable off
  the analysis row on a deploy morning at zero cost.
- **Snapshot cadence:** take an IBKR snapshot at least fortnightly, keep every
  one, pool the mapped sets. Mappings are lost permanently otherwise.
- **Next gate:** Stage 2 needs mapped entries, not fills. At the current rate
  (~8 per 4 weeks of overlap) a 30-entry mapped book is roughly 3–4 months out —
  unless snapshot cadence rises, which directly raises the mapping yield.

---

## 2026-08-12 — Deployment reference stats added to the operator card (descriptive, no rule change)

**Request:** put win rate / profit factor / MFE / MAE and the regime × structure
breakdown somewhere referable on a deploy morning.

**What was done:** `bear_giveback` ARM S extended and its output written up as
**§7 of `config/deployment-rules.md`**. ARM S previously printed n / win / PF /
meanR / $; it now also carries `MFE`, `MAE`, and two derived ratios per cell:

    gb  (give-back) = |mean MAE| / mean MFE   — path asymmetry
    cap (capture)   = mean R / mean MFE       — how much of the shown profit
                                                the exit actually banked

These exist because of the standing rule that a results cell is never read on
realized P&L alone: `cap` low with `MFE` high is an EXIT problem, low `MFE` is a
SELECTION problem, and the two demand different fixes. Three new cuts were added
alongside: whole-book debit/credit split, model regime × vol pooled across
structures (so the §1 veto cells can be read directly), and the §3 `bull_put_spread`
geometry gate in-band vs out.

Population: pooled real+tweak, **795 rows**, bs excluded. In-sample throughout.

**Nothing was tuned and no rule changed.** These are summaries of the book the
rules were already fitted on. Four things worth recording anyway:

1. **The ladder is monotone on every new column, not just $.** A/B/C/VETO run
   PF 2.29 / 1.78 / 0.79 / 0.34 and `gb` 0.38 / 0.77 / 1.22 / 2.28. The
   path-asymmetry ordering was never checked before and it agrees. VETO rows go
   2.3× deeper under water than they ever show green.

2. **`bear_put_spread` in mech BEAR_HE is the largest single loss cell in the
   book** — n=218, −$40.3k — with `MFE +0.67` but `cap −0.25`. It confirms from a
   third direction that bear is an exit problem, not a selection one (the 08-11
   bear-arm conclusion). §5 rows 2–3 are what manage it.

3. **`win` and `PF` disagree routinely and the card now says so.**
   `bull_put_spread` is 68% win / PF 0.94; `bull_call_spread` is 60% win / PF 2.05.
   Anyone reading win rate alone would rank those backwards.

4. **Two override temptations are now documented in place, with the reason not
   to take them.** BULL + C-VOL `bull_call_spread` (PF 5.01, n=40) outperforms
   most of Tier A but stays B — A-vs-B was validated at tier level, not cell by
   cell. BEAR + H-VOL `bull_call_spread` (n=9) looks positive but the pooled
   regime cell is −$20.6k at a 30% win rate, which is what §1.2 vetoes.

**Caveats written into §7.8:** in-sample; small-n cells are directional at best;
`$` is size-weighted so it can disagree with `meanR`; v3-derived, not re-confirmed
on v4; bs rows excluded.

**Regenerate with** `python -m scripts.backtest_study run bear_giveback --arms S`
— the command is in an HTML comment at the top of §7 so the snapshot can be
refreshed without hunting for it.
