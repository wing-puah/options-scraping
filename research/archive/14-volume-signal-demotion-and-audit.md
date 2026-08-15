# Archive 14 — 2026-08-13: volume_signal, bear_put demotion, method audit, compounding arm

Covers the rest of 2026-08-13: the `account_sim` COMPOUNDING arm (costs money
on this book; A2/A5 do not transfer), the `volume_signal` RUN (NULL — the
volume column is CLOSED, the live pipeline never pays the version bump), the
bear_put demotion mechanism CHOSEN (card veto §1.4, hedge sleeve carved out),
and the method-config audit (−25 `IVspr` veto retired, `OIConfirm` dropped
from Score in-v4, codex engine retired). Ordering follows the log (newest
first). See [../README.md](../README.md) for the full section index.

---

## 2026-08-13 — `account_sim` COMPOUNDING arm: sizing re-marked to realized equity monthly, budget ceilinged at $1,000 — it COSTS money on this book, and it breaks A2/A5

**Status: NEW OPT-IN ARM. Nothing ships. Post-hoc — compounding is NOT
pre-registered, and the mark interval and the $1,000 ceiling are a FRICTION
MODEL that may not be adopted on P&L.**

The operator asked for sizing to track the account rather than the configured
starting capital. Until now `account_sim` sized everything off a static
`cfg.capital`: both delta caps and the risk budget were fixed for the whole
three-year run, so the simulated book was completely **path-independent** —
identical whether the strategy was up $11k or down it.

**What was added.** A `compounding:` block in `config/account-sim.yml`
(`enabled: false`, so the frozen pre-registered book is untouched) and an arm
config `config/account-sim-compounding.yml`. When on:

```
marked_equity = starting capital + realized P&L of positions CLOSED STRICTLY
                BEFORE the mark session      (re-marked monthly; open positions
                                              are NOT marked to market)
budget        = min(risk_pct * marked_equity, 1000)   # ceilinged
per_pos_cap_$ = per_pos_cap * marked_equity           # scales, no ceiling
net_cap_$     = net_cap     * marked_equity           # scales, no ceiling
```

`marked_equity` is a **sizing** number only — the ledger's own `capital` is
untouched, which is why G3's identity still balances against the STARTING
capital.

**It is not lookahead, and G5 proves it.** `release_before()` already runs at
the top of each session, so at the moment of a re-mark `led.realized` contains
only positions whose `exit_sess` is strictly earlier — an operator would know
that number. G5 now runs sighted-vs-blind on **both** bases; the compounding
basis reproduces a byte-identical book (155 sighted / 155 blind, 0 differing)
because `blind_records()` deletes the outcome *columns* but keeps the price
path, and `replay_sized()` recomputes each closed position's P&L from that
path. G1–G4 stay pinned to the frozen basis: book calibration is an identity
against a prior report and selection identity is about ordering, so neither may
move because an arm changed sizing.

**Compounding costs money on this book** (PRIMARY dense episodes):

| arm | positions | dates | dollars | meanR | maxDD |
|---|---|---|---|---|---|
| frozen (static $25,000) | 72 | 37 | $11,399 | +0.290 | −$4,354 |
| compounding (monthly) | 70 | 35 | $9,852 | +0.264 | −$4,700 |

The mark trajectory says why: $25,000 → **$21,113 by May 2025** → $32,817 by Feb
2026 → $29,997 final. The account draws down first and therefore **de-levers
into its own recovery**, sizing smallest exactly where the recovery pays. That
is ordinary compounding drag on a choppy equity path, not a defect.

**The $1,000 ceiling never binds** — 0 of 6 marks (0 of 18 on SECONDARY). At 2%
it only engages above $50,000 of equity, which this book never reaches. It is
inert on this account and exists as a friction model for a larger one. The ruin
guard also fired 0 times.

**Binding constraint is unchanged: `net_delta`, and `cash` still binds zero
times** — 39 of 78 exclusions (frozen: 40 of 76). What did move is
`per_pos_delta`, 25 → 28, which is a **granularity** effect rather than a cap
effect: budget and cap both scale with equity, but `risk_contracts()` floors to
an integer, so contract counts jump in steps while the cap rises continuously,
and a position can cross its own cap on the step. The A4 partition still
balances exactly (150 candidates both arms).

**A2 and A5 DO NOT SURVIVE THIS ARM — do not read them here.** They are ratios
against B2, and B2 is compounded too. The tell is that B2 is the **same 110
positions over the same 46 dates in both arms** and its dollar total still moves
**$23,157 → $18,424**: the denominator changes without the numerator's position
set changing at all.

To be precise about what breaks — a ratio over 100% is *not* itself the anomaly.
A2 is not bounded by 100% even on the frozen book, because the caps remove
positions and removing a net-*losing* pick adds money; the frozen SECONDARY
population already prints **173%**. What breaks under compounding is
**attribution**. On the frozen basis B2 and the constrained book are sized off
the same static capital, so the ratio moves only with *which* positions the caps
removed — it isolates the caps. Under compounding B2 holds 110 positions against
the constrained 70, draws down harder, and throttles its own future budgets
differently, so the ratio mixes the caps' selection effect with a divergent
equity path. PRIMARY A2 goes 90% → **145%** across the arms on identical caps and
identical selection, and nearly all of that is the denominator collapsing
($12,675 → $6,786 on the shared dates). Neither number can be read as attrition
or stability. Both criteria were pre-registered against a path-independent
simulation and do not transfer; the report now carries that warning inline.

**The verdict does not move.** A1 MET (meanR +0.264, CI [+0.075, +0.438], both
years positive), A3 MET, A4 MET, A5/A6 NOT MET → `NO VERDICT MATCHES — A1 holds
but A5, A6 fail(s)`, the same landing as the frozen book. A6 is if anything
slightly worse: debit-only CI [−0.005, +0.427] at n=55, back to including zero
(frozen: [+0.021, +0.435]).

**Open item.** Compounding makes the whole book path-dependent, which means
every figure in the arm is now sensitive to the exit model in a way the frozen
book was not. Before any of this could inform a live account, the A-criteria
would need re-registering against a path-dependent basis — A2/A5 in particular
need a benchmark that is *not* compounded, or they need replacing. Not started.

## 2026-08-13 — `volume_signal` RUN: NULL — the volume column is closed

Run 2026-08-13 (stamped `volume_signal-20260813-202006.txt` first run,
`-202122.txt` amended-label rerun; the diff between them is the timestamp and
the verdict lines ONLY — every number is identical). **No report is retained on
disk.** The `-latest.txt` that carried this run was overwritten on 2026-08-15
19:11 by a re-run against the truncated v4 exports (142 / 404 / 1,306 rows), so
the file that stood here reproduced none of the figures below; the prose in this
section, and the replication grading folded in at the end of it, are the record.
Pre-registration:
[`pre-registrations/volume_signal.md`](../pre-registrations/volume_signal.md);
inputs are the 08-11 exports (795 pooled rows real+tweak, bs excluded).

### Gates

- **G1 PASS** — book debit calibration `{n: 301, exact: 289, near: 0, hard:
  12}` (the 12 hard rows are the known uncalibrated real rows, excluded from
  the exit arm by the `calibrated` flag); replay identity re-check 581/581
  exact on the exit-arm population. Credit rows ungated: 277.
- **G2** — coverage was NOT the binding constraint, unusually: O/S join
  788/795 (99%), `rvolz20`/`amihud20` 743/795 (93%), 51 rows on the rescaled
  basis with window features withheld as registered.
- G3/G4/G5 held (thin cells printed unread; no annualised figure anywhere;
  descriptive tables labelled in-sample).

### H1 — NOT SUPPORTED, both halves

(a) Non-bear debit os_ratio terciles: meanR **+0.205 / +0.255 / +0.232**
(LOW/MID/HIGH), give-back share **22% / 21% / 21%**. There is nothing there:
HIGH-O/S rows do not give back more; they peak HIGHER (MFE +1.15 vs +0.98)
with SHALLOWER drawdowns (MAE −0.52 vs −0.62) and identical realized R.

(b) The frozen exit variant (`be_after: 0.50` on HIGH-os_ratio non-bear
debit, stacked on the shipped merge) touched only **5 rows** and is
**negative**: Δ meanR −0.0032, Δ$ −2,266, paired date-clustered CI
**[−0.0126, +0.0032]**, LOO by date share>0 **1%** (min −0.0043, 115 folds),
and the gain flips sign across the mandatory window cuts (ex-2025-window
+0.0009 vs ALL −0.0032). Leak guard OK (0 rows outside the key changed). The
give-back mechanism has no non-bear home findable through volume.

### H2 / H3

- `rvolz20` (exploratory): non-monotone hump on non-bear debit (MID best,
  +0.342); nothing directional. No adoption path existed by registration.
- H3 evaluability is weak and DISCLOSED: os_ratio and amihud20 share the
  volume denominator, so HIGH-O/S rows pile into the illiquid tercile
  (n(HIGH-os)=38 in HIGH-amihud vs 4 in LOW-amihud) — only ONE 3×3 cell was
  evaluable (it kept the pooled sign → "not collapsed", read with that
  caveat). Any future volume feature must expect this dependence.

### Labelled amendment (verdict operationalization)

The first run's mechanical verdict printed **PATH-VOL-PROXY**. That fired on
a coding defect: the mirrored-path check compared SIGNED MFE/MAE separations,
so "peaks higher AND draws down shallower" (what the data shows) counted as
"MFE and MAE move together". The registered wording means path WIDTH moving
together (higher peaks WITH deeper drawdowns). Fixed in
`volume_signal.verdict()` with the amendment comment, rerun same-day; **no
number changed** (seeded bootstrap; diff = verdict lines only). Per the
registered grammar the verdict is **NULL**. Precedent: `account_sim`'s
grammar hole, same handling — disclose, don't absorb.

### Carry-forwards (POST-HOC observations, not candidates, nothing adopted)

- **Bear debit is monotone in os_ratio** and it is the LOW tercile that is
  toxic: meanR −0.321 (CI [−0.481, −0.134]) / −0.140 / −0.002, give-back 44%
  / 27% / 26%. The walk-forward selection arm (boundaries fitted on train)
  keeps the direction on TEST rows: `bear_put_spread` LOW −0.267 (n=36) vs
  MID −0.039 / HIGH −0.026. Bear is §1.4 selection-vetoed, so the only place
  this could ever matter is the **§4 hedge-sleeve pick rule** (currently
  |delta| descending) — that would need its own pre-registration on new
  dates, and the 08-12 rule stands: within-structure reads that survive one
  look have died here before (`cpir`/`oi_confirm`/`iv_pct`).
  **Post-hoc diagnostic (same day, operator question, disclosed):** os_ratio
  is NOT a |delta| proxy (Spearman os_ratio×|delta| +0.166 on 329 bear rows)
  and the pooled rank relation with R is n.s. (+0.078, p=0.16 — the tercile
  table's monotonicity is carried by the LOW-cell toxicity, not a smooth
  gradient). Within |delta| terciles the effect concentrates EXACTLY where
  the §4 sleeve lives: high-|delta| bears show rho +0.274 (p=0.004,
  n=110), low/mid show nothing. So a sleeve-pick refinement ("among
  high-|delta| candidates, prefer high os_ratio / avoid thin-flow") is the
  precise pre-registerable question — one look spent, needs new dates.
- **Credit rows are monotone the other way** (HIGH +0.337, win 75%, n=51) —
  descriptive only, on UNGATED replays, inside the Mar-TSLA-cluster caveat
  domain. Recorded, not pursued.

### Replication grading (two-analyst protocol, same day)

Digest + A/B + validator are folded in verbatim at the end of this section —
they were not retained on disk. Digest concurs: NULL, machinery trustworthy,
nothing actionable. Validator's
disagreement log, answered here where the answer is knowable:

- **G1 population arithmetic (disagree-unresolved for the analysts, resolved
  here):** the report prints 301 book-debit calibration rows (12 hard) and
  separately 581/581 exit-arm exact, without reconciling them. The
  reconciliation: 301 = REAL debit rows; the 12 hard rows carry
  `calibrated=False` and are excluded from the exit arm by flag; 581 =
  calibrated real debit (289) + calibrated tweak debit (292, tweak rows are
  exact-by-admission per `book.py`'s proxy gate). `-> PASS` covers the
  581-row arm, not the 12 hard rows. A future report should print this
  bridge itself.
- **H1(b) footprint (both analysts, valid):** the frozen variant changed only
  5 rows — below MIN_CELL_N. The paired CI/LOO ran over all 581 rows, but the
  information is those 5. The honest reading stands and is narrow: the key
  almost never fires, and where it fired it lost; that is a NULL by absence
  of footprint as much as by sign.
- **LIQUIDITY-PROXY evaluability (disagree-unresolved):** with only 1 of 3
  amihud cells evaluable, `amihud_collapse=False` is weak evidence — already
  caveated in the H3 section above; the verdict does not rest on it (NULL
  fires regardless).
- Minor: `gb%` column = sub-arming give-back share (defined in the
  pre-registration; the report should carry the definition inline).

### What this closes

The §2.1 queue item. The ML reopen condition was satisfied (a genuinely new
column), the column was tested within structure from the first look, and it
is a null: **share volume / unusual-O/S does not feed the live pipeline, no
version bump is paid.** Infra kept: `Bar.v`, `volume_features.py` (os_ratio /
rvolz20 / amihud20, split-guarded, coverage-printing) — reusable by any
future pre-registered study without touching the frozen harness.


<details>
<summary>Two-analyst replication — digest (verbatim, 2026-08-13)</summary>

````text
```markdown
# Volume Signal Study — Plain-Language Digest

## Bottom line

**Verdict: NULL.** The "volume column" — the os_ratio signal this whole study is built around — stays **closed**. Nothing here earns a change to the live trading rules; "the live pipeline never pays the version bump" means the production code keeps running exactly as it does today. Some individual numbers below look encouraging on their own, but the study's own pre-registered logic says that isn't enough to ship anything, and it says so explicitly. Treat every positive-looking cell below as "interesting, not actionable" — that's the report's own framing, not a hedge I'm adding.

## Where the numbers come from (provenance)

Run on 2026-08-13, against a slightly modified ("dirty") copy of the codebase at a specific saved version (git commit 66cd01a). It pulled four input files — three backtest result exports (1,926 / 4,533 / 11,836 rows) and one market data file (803 rows), all last updated between 2026-08-11 and 2026-08-13. This header exists so that if two reports ever look different, you can check whether they actually ran on the same data — nothing to act on here.

## The book (the trades actually studied)

795 trades ("rows") make up the population this study scores, spanning 2024-06-17 through 2026-04-07. They come from three sources: 406 "real" trades, 389 "tweak" trades, and 272 from a source labeled "bs" — that third group was **excluded entirely** from this study, so nothing below reflects it.

## G1 — Calibration check (PASS)

Before trusting any of the numbers, the study re-simulates trades and checks the replay engine reproduces what's already on record. Of 301 debit trades checked, 289 matched exactly, 0 were "near," and 12 didn't match cleanly ("hard" mismatches) — those 12 are a small crack but didn't block the study. A separate check re-ran 581 trades' exits and got 581/581 exact matches. This is a go/no-go gate, and it passed — meaning the machinery producing every number below is trustworthy, not necessarily that the strategy is good.

## G2 — Coverage (how much of the book each number is actually built on)

Of the 795 trades, 788 (99%) could be matched to the volume-flow data needed to compute os_ratio. Two other features used later in the study — rvolz20 and amihud20 (illiquidity) — could only be computed for 743 trades (93%) each, because they need at least 15 clean trading days of volume history first. So most tables below are quoting against ~788 or ~743 trades, not the full 795 — a small but real shrinkage to keep in mind when a table's "n" looks lower than expected.

## H1(a) — Does os_ratio (the volume signal) separate winners from losers?

**Important caveat that applies to every table in this section:** the "LOW/MID/HIGH" cutoffs were calculated from this same data ("in-sample" boundaries, tagged G5 in the report) rather than fixed in advance. That can make patterns look cleaner than they'd be on new data — treat this whole section as descriptive, not proof.

**Non-bear debit trades (the primary group of interest):**
| Group | Trades | Avg return | Win rate | Total $ | Statistically distinguishable from zero? |
|---|---|---|---|---|---|
| LOW volume signal | 81 | +20.5% | 56% | +$16,540 | No — confidence range touches zero |
| MID volume signal | 108 | +25.5% | 56% | +$27,204 | Yes — range stays positive |
| HIGH volume signal | 68 | +23.2% | 57% | +$19,293 | Yes — range stays positive |

All three groups made money on average, but the pattern isn't a clean "more volume signal = more return" — MID actually beats HIGH slightly, and only MID and HIGH clear the bar for "probably a real effect, not noise."

**Bear-side debit trades** (same signal, but trades built for a falling market):
| Group | Trades | Avg return | Win rate | Total $ | Real effect? |
|---|---|---|---|---|---|
| LOW | 89 | −32.1% | 28% | −$32,768 | Yes — confidently negative |
| MID | 96 | −14.0% | 34% | −$16,318 | No — touches zero |
| HIGH | 144 | −0.2% | 42% | −$2,124 | No — touches zero, essentially flat |

These bear trades lose money overall, and lose the most when the volume signal is LOW — the only cell here that's confidently non-zero.

**Credit trades** (the report flags this table as "ungated" — meaning the replay wasn't run through the same verification gate as the debit numbers, so read it as descriptive only, not as reliable as the tables above):
| Group | Trades | Avg return | Win rate | Real effect? |
|---|---|---|---|---|
| LOW | 92 | −16.7% | 54% | No |
| MID | 59 | +8.1% | 68% | No |
| HIGH | 51 | +33.7% | 75% | No — barely touches zero |

HIGH looks the best here (75% win rate!), but none of the three cells clears the "confidently not zero" bar, so this table can't be used to draw a conclusion on its own.

**Bear "give-back" tally** (bear-side trades that ran up a gain and then gave some of it back before exiting): LOW volume signal had 39 give-backs out of 89 bear trades (−$33,402), MID had 26 of 96 (−$20,211), HIGH had 38 of 144 (−$31,224). This is raw bookkeeping feeding into a different report, not a conclusion in itself.

## H1(b) — Testing one specific exit-rule tweak

This section asks a narrower, more decision-relevant question: if we loosen the breakeven-ratchet trigger (the point where a winning trade's stop tightens to breakeven) to 0.50 for HIGH-volume-signal non-bear debit trades, does it beat what's actually running in production today? Only **one** variant was tested — deliberately, not a grid of many variants, specifically to avoid the multiple-comparisons trap (testing many variants and cherry-picking the best-looking one).

The tweak only touched 5 trades, all inside its intended target group (a "leak guard" confirmed zero trades outside that group were affected — exactly as it should be).

- **Production (current) rule:** average return +4.56%, total +$23,253
- **Tweaked rule:** average return +4.24%, total +$20,987
- **Difference:** −0.32 percentage points, −$2,266 — the tweak is worse.

The difference's confidence range is [−1.26%, +0.32%] — it touches zero, so on its own this isn't "proven" worse. But the deeper check is more damning: when the study drops one trading date at a time and recomputes the tweak's edge on what's left (115 different folds), the tweak comes out ahead in only **1%** of those folds — essentially never. For a rule to be trusted, per this study's own bar, it needs to win in *100%* of folds, not 1%. That's a decisive fail, not a coin-flip.

Breaking it down further:
- Excluding the Mar–Apr 2025 window: the tweak flips to slightly positive (+0.09%) — meaning some of its apparent badness is tied to that one window.
- Excluding the Feb–Apr 2026 window: still negative (−0.42%).
- By year: flat in 2024 (+0.03%), clearly negative in 2025 (−0.70%), flat in 2026 (0.00%).
- By pricing source: negative for "real" trades (−0.64%), flat for "tweak" trades (0.00%).

Net: this specific exit tweak does not hold up and should not be adopted.

## H2 — rvolz20 (a second volume-related signal), exploratory only

The report is explicit up front: **this section has no path to adoption this run**, regardless of what it shows — it's exploratory. Same in-sample-boundary caveat as H1(a) applies.

Non-bear debit: LOW 74 trades +15.4% (touches zero), MID 86 trades **+34.2%, 64% win rate, +$33,993 — the strongest, statistically real cell in the whole report**, HIGH 71 trades +14.3% (touches zero). Same non-monotonic shape as os_ratio — the middle bucket outperforms both extremes.

Bear debit: LOW 106 trades −11.7%, MID 104 trades −6.3%, HIGH 106 trades −18.0% — all three touch zero, none confidently real.

## H3 — Controlling for stock illiquidity (Amihud)

This asks: is the os_ratio pattern from H1(a) actually just an illiquidity effect in disguise? The pooled "HIGH minus LOW" gap in H1(a) was +2.71 percentage points. Splitting that by illiquidity level:

- **Low illiquidity stocks:** only 35 LOW-signal and 4 HIGH-signal trades — too few to trust, printed but not usable.
- **Mid illiquidity stocks:** 24 LOW-signal (+18.1%) vs 20 HIGH-signal (+31.7%) — a +13.6 point gap, same direction as the pooled number.
- **High illiquidity stocks:** only 12 LOW-signal and 38 HIGH-signal — again too thin to trust.

Only one of three illiquidity buckets had enough data to read at all, and in that one bucket the os_ratio effect held its sign (didn't flip or disappear). That's a mild point in the signal's favor, but it rests on a single small cell — not a robust confirmation.

## Selection (secondary, exploratory) — walk-forward by trade structure

The report flags this section as **secondary** and warns that "a pooled cross-structure read may not carry a conclusion" — i.e., don't treat this as a finding, just as a look. It splits results by trade type and by data the model hadn't seen yet ("walk-forward," 3 rolling test periods).

Only one trade structure had enough data across all three signal buckets to be readable: **bear put spreads**. By os_ratio: LOW −26.7% (36 trades), MID −3.9% (42 trades), HIGH −2.6% (54 trades) — losing across the board, worst at LOW. By rvolz20: LOW −23.5% (44), MID +7.3% (39), HIGH −8.4% (46) — mixed, no clean pattern.

Every other trade type (bull call spreads, bull put spreads, long calls, long puts, strangles) had too few trades per cell ("thin") to read at all in this split.

## The verdict, and why it's NULL despite some good-looking numbers

The report scores itself against four pre-registered checks:
- **H1a readable:** Yes — the descriptive tables could be computed.
- **os_ratio separation (r_sep):** +0.0271 — a real, positive gap exists in the raw description.
- **exit_ok:** **No** — the one concrete exit-rule change tested (H1b) failed its robustness check (1% of folds positive).
- **amihud_collapse:** No — the separation didn't disappear under the one illiquidity control cell that had enough data.

Even with the signal separation present and surviving the one illiquidity check, the fact that the *only tested, concrete change to the actual exit rule* failed decisively is what closes this thread. **VERDICT: NULL — the volume column is CLOSED; the live pipeline never pays the version bump.** Nothing in production changes as a result of this study.

One more deliberate omission: the report prints no annualized return, no Sharpe ratio, and no time-to-recover figure anywhere — by design, not oversight. Those metrics tend to oversell noisy small-n results, so this study sticks to the mean-return-plus-confidence-interval approach throughout.

## Caveats worth remembering

- **Multiple comparisons:** several tercile tables (os_ratio × 3 trade groups, rvolz20 × 2 trade groups) were computed and eyeballed for patterns — that's exactly the kind of scan where something is bound to look interesting by chance. The study limited itself to testing exactly *one* concrete exit-rule change (H1b) rather than grid-searching many, specifically to guard against this.
- **Small-n warnings:** several cells throughout (the Amihud LOW/HIGH illiquidity buckets, most walk-forward trade-structure cells outside bear put spreads) were too thin to trust and were explicitly marked "printed, not read" — don't infer anything from those numbers even though they're shown.
- **In-sample boundaries:** every tercile cut point in H1(a) and H2 was fit on the same data being scored, which can flatter the apparent pattern — the report tags these "G5" throughout as a standing caveat.
- **Closed-threads rule:** the report twice invokes a rule that a pooled/secondary read (like the walk-forward-by-structure section) "may not carry a conclusion alone" — this keeps exploratory-looking wins from being smuggled into a decision.
- **This finding is now closed:** per the verdict, this line of investigation into the volume/os_ratio signal is done — re-litigating it without new data or a new angle isn't expected to change the outcome.
```
````

</details>

<details>
<summary>Two-analyst replication — review-analyst-a (verbatim, 2026-08-13)</summary>

```text
==============================================================================
STUDY: volume_signal
==============================================================================
  run at    2026-08-13 20:21:22
  command   python -m scripts.backtest_study.volume_signal
  git       66cd01a (worktree-refactored-coalescing-hamster, working tree dirty)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
   4,533 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestProxy.csv
  11,836 rows  2026-08-11 17:24  backtests/to_evaluate/analysis - AnalysisClaude.csv
     803 rows  2026-08-13 11:56  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================

| Criterion/Gate | Verdict | Exact number(s) read from report | What would change the verdict |
|---|---|---|---|
| G1 calibration — `replay(DEBIT_PROD)` reproduces stored `(exit_reason, days_held, round(R,4))` on every calibrated debit row; `debit_calib` / `n_credit_ungated` quoted | NOT EVALUABLE | `book debit calibration: {'n': 301, 'exact': 289, 'near': 0, 'hard': 12}   credit rows ungated: 277`; `replay identity re-check on the exit-arm population: 581/581 exact`; `-> PASS` | A rerun that prints whether the 12 `hard` rows are inside or outside the calibrated debit population, and reconciles the exit-arm n=581 against the calibration n=301, would settle whether "every calibrated debit row" reproduced. |
| G2 coverage BEFORE any conditional number: volume-feature hit-rates, `by_source` split, O/S join hit-rate, rescaled-withheld counts | MET | `book rows 795`; `O/S join hit (rollup match) 788`; `rescaled basis (window feats 51   rvolz20/amihud20 withheld)`; `os_ratio usable 788 (99%)`; `rvolz20 usable 743 (93%)`; `amihud20 usable 743 (93%)`; `pricing tiers: {'real': 406, 'tweak': 389}`; header `counts_by_source={'real': 406, 'tweak': 389, 'bs': 272}` | A rerun that printed any conditional number ahead of the coverage block, or omitted one of the four required coverage items, would flip this. |
| G3 `MIN_CELL_N = 20`; thinner cells print n and are not read | MET | H3: `LOW 35 4 (< MIN_CELL_N — printed, not read)`, `HIGH 12 38 (< MIN_CELL_N — printed, not read)`, `MID 24 20 +0.181 +0.317 +0.136`; selection: `bull_call_spread LOW n=14(thin) MID n=13(thin) HIGH n=6(thin)` | A cell with n below 20 being carried into a read or a verdict component would flip this. |
| G4 no annualised return, Sharpe, or time-to-recover anywhere | MET | `G4 note: no annualised return, Sharpe, or time-to-recover is printed anywhere above, by design.` | Any such statistic appearing in the report body would flip this. |
| G5 out-of-fold discipline: descriptive tables in-sample and labelled; only LOO folds and walk-forward TEST rows adoption-eligible | MET | Every descriptive header carries `[IN-SAMPLE boundaries, G5]`; `LOO by date: mean -0.0032  share>0 1%  min -0.0043  folds 115`; `walk-forward TEST rows — os_ratio (boundaries fitted on TRAIN only)` | An in-sample tercile number being quoted as adoption-eligible, or TEST boundaries fitted on pooled dates, would flip this. |
| Anti-tuning: exit-variant set is `{be_after: 0.50}`, no growth after results; tercile boundaries and 20-session windows not swept | MET | `One variant, no grid.`; `rows changed by the variant: 5 (in key 5, outside key 0)`; `LEAK GUARD: OK (0 outside the key is the only acceptable number)`; single boundary set `LOW < 0.1087 <= MID < 0.4255 <= HIGH` | A second exit variant, a swept window length, or a second tercile boundary set appearing in the report would flip this. |
| H1(a) PRIMARY — within structure, HIGH `os_ratio` tercile shows lower exit capture AND a larger sub-arming give-back share vs LOW | NOT MET | NON-BEAR DEBIT `cap`: `LOW -0.18`, `HIGH -0.65`; `gb%`: `LOW 22%`, `MID 21%`, `HIGH 21%`; BEAR DEBIT `gb%`: `LOW 44%`, `MID 27%`, `HIGH 26%`; bear census `LOW bear rows 89 give-backs 39 $ -33,402` / `HIGH bear rows 144 give-backs 38 $ -31,224`; verdict line `exit_ok=False` | A cut in which HIGH's give-back share exceeds LOW's (rather than 21% vs 22% non-bear and 26% vs 44% bear) would flip this. |
| H1(b) PRIMARY mechanism — frozen variant `be_after: 0.50` on HIGH-`os_ratio` non-bear debit beats PROD, LOO / both-window | NOT MET | `SHIPPED baseline: meanR +0.0456   $      23,253`; `variant: meanR +0.0424   $      20,987   Delta meanR -0.0032   Delta$ -2,266`; `paired CI95 (date-clustered): [-0.0126, +0.0032]`; `LOO by date: mean -0.0032  share>0 1%  min -0.0043  folds 115`; `ALL n= 581  gain -0.0032`, `ex_2025_mar_apr n= 434  gain +0.0009`, `ex_2026_feb_apr n= 433  gain -0.0042` | A rerun with more dates in which the LOO summary and both window cuts are positive rather than `-0.0032` / `+0.0009` / `-0.0042` would flip this. |
| H2 `rvolz20` (exploratory) — descriptive tercile cut within structure, MIN_CELL_N enforced, date-clustered | MET (delivered as pre-registered; no direction pre-committed, so no directional verdict is available) | NON-BEAR DEBIT `LOW 74 +0.154 [-0.044, +0.354]`, `MID 86 +0.342 [+0.148, +0.524]`, `HIGH 71 +0.143 [-0.079, +0.384]`; BEAR DEBIT `LOW 106 -0.117 [-0.312, +0.090]`, `MID 104 -0.063 [-0.224, +0.097]`, `HIGH 106 -0.180 [-0.385, +0.040]`; boundaries `LOW < -0.2764 <= MID < 0.8018 <= HIGH` | A missing structure cut, a cell read below MIN_CELL_N, or non-date-clustered CIs would flip this; no future observation makes it a directional MET, since the pre-registration commits no direction. |
| H3 `amihud20` CONTROL — is the `os_ratio` separation absorbed by illiquidity? | NOT EVALUABLE | `pooled HIGH-minus-LOW meanR (non-bear debit): +0.0271`; `LOW 35 4 (< MIN_CELL_N — printed, not read)`; `MID 24 20 +0.181 +0.317 +0.136`; `HIGH 12 38 (< MIN_CELL_N — printed, not read)`; `evaluable cells 1, keeping the pooled sign 1 -> not collapsed` | More dates filling the LOW-amihud and HIGH-amihud cells to n>=20 on both sides, so the collapse test rests on more than the single MID cell, would make this readable. |
| Selection (SECONDARY) — mean R / total $ by tercile within structure, must survive `walk_forward_splits` with TRAIN-fitted boundaries to be called a CANDIDATE | NOT EVALUABLE | os_ratio TEST: `bear_put_spread LOW -0.267 (n=36)  MID -0.039 (n=42)  HIGH -0.026 (n=54)`; all other structures `n=14(thin)`, `n=13(thin)`, `n=6(thin)`, `n=1(thin)`, `n=2(thin)`, `n=4(thin)`, `-`; rvolz20 TEST: `bear_put_spread LOW -0.235 (n=44)  MID +0.073 (n=39)  HIGH -0.084 (n=46)`, all others thin or `-`; `folds: 3` | More dates lifting a NON-bear structure's TEST cells above MIN_CELL_N would make this readable; the only non-thin structure printed is `bear_put_spread`, whose selection tuning is a closed thread and cannot carry a conclusion. |
| VERDICT VOLUME-CONDITIONS-EXITS — H1 LOO median AND total positive, sign holds both windows, H3 does not collapse | NOT MET | `Delta$ -2,266`; `LOO by date: mean -0.0032` (no median printed); `ex_2025_mar_apr gain +0.0009` vs `ex_2026_feb_apr gain -0.0042`; `exit_ok=False` | A rerun printing a positive LOO median together with a positive total and a consistent sign across both window cuts would flip this. |
| VERDICT LIQUIDITY-PROXY — separation absorbed by `amihud20` (H3 fires) | NOT EVALUABLE | `amihud_collapse=False`; `evaluable cells 1, keeping the pooled sign 1 -> not collapsed`; illiquid cell `HIGH 12 38 (< MIN_CELL_N — printed, not read)` | Enough dates for all three amihud terciles to be read at n>=20 per side, showing separation confined to the illiquid tercile, would flip this. |
| VERDICT PATH-VOL-PROXY — MFE and MAE move together with no R separation | NOT MET | NON-BEAR DEBIT `MFE`: `+0.98`, `+1.26`, `+1.15`; `MAE`: `-0.62`, `-0.52`, `-0.52`; `mfe/mae mirrored=False`; `r_sep=+0.0271` | A cut where MFE and MAE scale together across terciles while mean R stays flat would flip this. |
| VERDICT NULL — none of the above survives its gate; volume column CLOSED | MET | `components: H1a readable=True r_sep=+0.0271  exit_ok=False  amihud_collapse=False  mfe/mae mirrored=False`; `VERDICT: NULL — the volume column is CLOSED; the live pipeline never pays the version bump.` | Any one of the three other verdict branches clearing its gate on a rerun with more dates would flip this. |

## Deviations

1. **G1 internal inconsistency.** The report prints `n: 301` for book debit calibration but `581/581 exact` for the exit-arm replay re-check, and `credit rows ungated: 277` against `book: 795 rows`. No reconciliation of 301 vs 581 vs 795−277 is printed, and the gate's population ("every calibrated debit row") is therefore undefined in the report while `hard: 12` and `-> PASS` coexist. I graded G1 `NOT EVALUABLE` rather than assume the 12 `hard` rows fall outside the gated population.
2. **`gb%` column is not defined in the report.** I read it as the pre-registered "share of rows that peak below the `be_after` arming threshold and finish ≤ 0". If it means something else, the H1(a) row must be regraded.
3. **H1 descriptive tables are cut by NON-BEAR DEBIT / BEAR DEBIT / CREDIT groups, not by individual structure.** The pre-registration requires "within structure from the first look". Only the walk-forward selection tables are per-structure. I graded at the granularity printed.
4. **LOO median is not printed.** The VOLUME-CONDITIONS-EXITS wording requires "LOO median AND total positive"; the report prints `LOO by date: mean -0.0032`. That row is `NOT MET` on the printed total (`Delta$ -2,266`) regardless, but the median itself is unavailable.
5. **The frozen variant changed only 5 rows** (`rows changed by the variant: 5`), below the study's own `MIN_CELL_N = 20`. The pre-registration states no minimum changed-row count for the variant arm, so I graded H1(b) on the printed LOO and window numbers rather than declaring it `NOT EVALUABLE`; flagging for the validator, since the entire `Delta$ -2,266` rests on those 5 rows.
6. **Provenance shows `working tree dirty`** at `git 66cd01a`, so the run is not reproducible from a committed sha alone.
```

</details>

<details>
<summary>Two-analyst replication — review-analyst-b (verbatim, 2026-08-13)</summary>

````text
```
==============================================================================
STUDY: volume_signal
==============================================================================
  run at    2026-08-13 20:21:22
  command   python -m scripts.backtest_study.volume_signal
  git       66cd01a (worktree-refactored-coalescing-hamster, working tree dirty)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
   4,533 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestProxy.csv
  11,836 rows  2026-08-11 17:24  backtests/to_evaluate/analysis - AnalysisClaude.csv
     803 rows  2026-08-13 11:56  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================
book: 795 rows  counts_by_source={'real': 406, 'tweak': 389, 'bs': 272}  date_range=('2024-06-17', '2026-04-07')  (bs excluded)
```

| Criterion/Gate | Verdict | Exact number(s) read from report | What would change the verdict |
|---|---|---|---|
| G1 calibration — replay reproduces stored `(exit_reason, days_held, round(R,4))`; `debit_calib`/`n_credit_ungated` quoted | MET | `book debit calibration: {'n': 301, 'exact': 289, 'near': 0, 'hard': 12}   credit rows ungated: 277`; `replay identity re-check on the exit-arm population: 581/581 exact`; `-> PASS` | A rerun that either reconciles the 12 `hard` rows against the 581-row exit-arm population or shows any exit-arm row failing identity would flip this. |
| G2 coverage printed BEFORE any conditional number (feature hit-rates, `by_source`, O/S join, rescaled-withheld) | MET | `book rows 795`; `O/S join hit (rollup match) 788`; `rescaled basis (window feats 51   rvolz20/amihud20 withheld)`; `os_ratio usable 788 (99%)`; `rvolz20 usable 743 (93%)`; `amihud20 usable 743 (93%)`; `pricing tiers: {'real': 406, 'tweak': 389}` | A rerun in which any coverage line is missing, or is printed after a conditional table, would flip this. |
| G3 `MIN_CELL_N = 20`; thinner cells print n and are not read | MET | H3 `LOW n(LOW) 35 n(HIGH) 4 (< MIN_CELL_N — printed, not read)`, `HIGH n(LOW) 12 n(HIGH) 38 (< MIN_CELL_N — printed, not read)`; walk-forward `bull_call_spread LOW n=14(thin) MID n=13(thin) HIGH n=6(thin)`; smallest read tercile cell n=51 | A rerun that draws a conclusion from a cell printed as thin, or that reads a cell with n<20, would flip this. |
| G4 no annualised return, Sharpe, or time-to-recover anywhere | MET | `G4 note: no annualised return, Sharpe, or time-to-recover is printed anywhere above, by design.` (none appears in the report body) | Any such statistic appearing in the report body would flip this. |
| G5 out-of-fold discipline — descriptive tables labelled in-sample; adoption-eligible numbers only LOO folds / walk-forward TEST | MET | `[IN-SAMPLE boundaries, G5]` on all six tercile tables; `LOO by date: mean -0.0032  share>0 1%  min -0.0043  folds 115`; `walk-forward TEST rows — os_ratio (boundaries fitted on TRAIN only)   folds: 3` | An in-sample tercile number being used as an adoption-eligible read, or TEST boundaries fitted on pooled dates, would flip this. |
| Anti-tuning — exit-variant set is exactly `{be_after: 0.50}`, no grid; boundaries/windows not swept | MET | `H1(b) — FROZEN EXIT VARIANT: be_after 0.50 on HIGH-os_ratio non-bear debit`; `One variant, no grid.`; `rows changed by the variant: 5 (in key 5, outside key 0)`; `LEAK GUARD: OK` | A second variant, an alternative `be_after` value, or a swept tercile boundary/window length appearing in the report would flip this. |
| H1 PRIMARY (a) — HIGH `os_ratio` tercile shows LOWER exit capture (R against MFE) than LOW, within structure | NOT MET | NON-BEAR DEBIT `cap`: LOW `-0.18`, MID `-0.48`, HIGH `-0.65`; BEAR DEBIT `cap`: LOW `-2.35`, MID `-0.83`, HIGH `-0.83` | A rerun in which HIGH capture is below LOW in bear as well as non-bear debit (rather than −0.83 vs −2.35) would flip this. |
| H1 PRIMARY (b) — HIGH tercile shows a LARGER share of rows peaking below the `be_after` arming threshold and finishing ≤ 0 | NOT MET | NON-BEAR DEBIT `gb%`: LOW `22%`, MID `21%`, HIGH `21%`; BEAR DEBIT `gb%`: LOW `44%`, MID `27%`, HIGH `26%`; bear census `LOW bear rows 89 give-backs 39 $ -33,402`, `MID 96 / 26 / $ -20,211`, `HIGH 144 / 38 / $ -31,224` | More dates producing a HIGH-tercile give-back share above the LOW tercile's (rather than 21% vs 22% non-bear and 26% vs 44% bear) would flip this. |
| H1 mechanism test — frozen variant `be_after: 0.50` on HIGH-`os_ratio` non-bear debit vs PROD, leave-one-date-out | NOT MET | `SHIPPED baseline: meanR +0.0456   $ 23,253`; `variant: meanR +0.0424   $ 20,987   Delta meanR -0.0032   Delta$ -2,266`; `paired CI95 (date-clustered): [-0.0126, +0.0032]`; `LOO by date: mean -0.0032  share>0 1%  min -0.0043  folds 115` | A rerun with the variant touching ≥MIN_CELL_N rows (it changed 5) and returning a positive Delta$ with a CI excluding zero would flip this. |
| H2 `rvolz20` — descriptive tercile cut within structure, MIN_CELL_N enforced, date-clustered, no adoption path | MET | NON-BEAR DEBIT `LOW n 74 meanR +0.154 CI [-0.044, +0.354]`, `MID n 86 +0.342 [+0.148, +0.524]`, `HIGH n 71 +0.143 [-0.079, +0.384]`; BEAR DEBIT `LOW n 106 -0.117 [-0.312, +0.090]`, `MID n 104 -0.063 [-0.224, +0.097]`, `HIGH n 106 -0.180 [-0.385, +0.040]` | A cut pooled across structures, a cell read below n=20, or an adoption claim made from these numbers would flip this. |
| H3 `amihud20` CONTROL — is the H1 `os_ratio` separation absorbed by illiquidity terciles? | NOT EVALUABLE | `pooled HIGH-minus-LOW meanR (non-bear debit): +0.0271`; `LOW n(LOW) 35 n(HIGH) 4 (< MIN_CELL_N — printed, not read)`; `MID n(LOW) 24 n(HIGH) 20 meanR LOW +0.181 meanR HIGH +0.317 sep +0.136`; `HIGH n(LOW) 12 n(HIGH) 38 (< MIN_CELL_N — printed, not read)`; `evaluable cells 1, keeping the pooled sign 1 -> not collapsed` | More dates lifting the illiquid (amihud HIGH) and liquid (amihud LOW) cells above MIN_CELL_N=20 on both sides would make the collapse test readable. |
| SELECTION (SECONDARY) — within-structure tercile separation surviving `protocol.walk_forward_splits` with TRAIN-fitted boundaries | NOT EVALUABLE | os_ratio TEST `bear_put_spread LOW -0.267 (n=36)  MID -0.039 (n=42)  HIGH -0.026 (n=54)`; all other structures `n=14(thin)`/`n=13(thin)`/`n=6(thin)`/`n=1(thin)`/`n=2(thin)`/`n=4(thin)`/`-`; rvolz20 TEST `bear_put_spread LOW -0.235 (n=44)  MID +0.073 (n=39)  HIGH -0.084 (n=46)`, all other structures thin; `folds: 3` | More dates raising non-bear structures' TEST cells above MIN_CELL_N would make a within-structure selection read possible; the only readable structure here is bear, whose SELECTION tuning is a closed thread and may not carry a conclusion. |
| VERDICT clause VOLUME-CONDITIONS-EXITS — LOO median AND total positive, sign holds on both-window cut, H3 does not collapse | NOT MET | `Delta$ -2,266`; `LOO by date: mean -0.0032  share>0 1%`; window cuts `ALL n= 581 gain -0.0032`, `ex_2025_mar_apr n= 434 gain +0.0009`, `ex_2026_feb_apr n= 433 gain -0.0042` | A rerun with a positive LOO median and a positive Delta$ and the same sign on both `ex_` window cuts would flip this. |
| VERDICT clause LIQUIDITY-PROXY — separation absorbed by `amihud20` (H3 fires) | NOT MET | `evaluable cells 1, keeping the pooled sign 1 -> not collapsed`; verdict components `amihud_collapse=False` | Readable amihud LOW and HIGH cells showing the +0.0271 pooled separation confined to the illiquid tercile would flip this. |
| VERDICT clause PATH-VOL-PROXY — MFE and MAE move together with no R separation | NOT MET | NON-BEAR DEBIT `MFE +0.98 / +1.26 / +1.15`, `MAE -0.62 / -0.52 / -0.52`; components `r_sep=+0.0271`, `mfe/mae mirrored=False` | A tercile ordering in which MFE and MAE magnitudes rise together with no mean-R separation would flip this. |
| VERDICT clause NULL — none of the above survives its gate; volume column CLOSED | MET | `components: H1a readable=True r_sep=+0.0271  exit_ok=False  amihud_collapse=False  mfe/mae mirrored=False`; `VERDICT: NULL — the volume column is CLOSED; the live pipeline never pays the version bump.` | Any one of the three preceding verdict clauses being satisfied on a rerun would flip this. |

### Deviations

1. **G1 population mismatch.** The gate prints `{'n': 301, ... 'hard': 12}` for book debit calibration but `581/581 exact` for the exit-arm population, and the descriptive tables sum to 257 non-bear + 329 bear = 586 debit rows. The report does not reconcile 301 vs 581 vs 586, nor state whether the 12 `hard` rows are inside the exit arm. I graded G1 on the printed `-> PASS`.
2. **Section labelling.** The report's `H1(a)` is the descriptive block and its `H1(b)` is the frozen variant; the pre-registration's H1 (a)/(b) are the two descriptive claims (exit capture, sub-arming share) with the variant as a separate "Mechanism test". I graded against the pre-registration's lettering, not the report's.
3. **LOO median not printed.** VOLUME-CONDITIONS-EXITS requires "LOO median AND total positive". The report prints LOO `mean -0.0032`, `share>0 1%`, `min -0.0043` — no median. I graded that clause on the printed `Delta$ -2,266` and LOO mean, which fail the conjunction independently of the median.
4. **Variant arm below MIN_CELL_N.** `rows changed by the variant: 5`, against a pre-registered `MIN_CELL_N = 20`. The pre-registration does not state whether G3 applies to the variant arm, so I graded the mechanism row `NOT MET` on the printed sign rather than `NOT EVALUABLE`; the validator may reasonably reclassify it.
5. **`gb%` definition.** The pre-registration defines H1(b) as "rows that peak below the `be_after` arming threshold and finish ≤ 0". The report prints a `gb%` column with no definition line. I read `gb%` as that quantity.
6. **G2 `by_source`.** The pre-registration requires a `by_source` split inside G2. G2 prints `pricing tiers: {'real': 406, 'tweak': 389}`; `counts_by_source={'real': 406, 'tweak': 389, 'bs': 272}` appears in the book header above G1. I treated the pair as satisfying the requirement.
7. **Dirty working tree.** Provenance reads `git 66cd01a (... working tree dirty)`, so this run is not exactly reproducible from the recorded sha.
````

</details>

<details>
<summary>Two-analyst replication — review-validator (verbatim, 2026-08-13)</summary>

```text
## Validator adjudication — `volume_signal` (Mode 1)

Mode 1 (pre-registration + stamped report); no TRAIN-split CSV artifact involved, so the split-provenance confirmation line does not apply.

| Criterion/Candidate | Analyst A verdict | Analyst B verdict | Source-check result | Adjudication |
|---|---|---|---|---|
| G1 calibration (replay reproduces stored values on every calibrated debit row) | NOT EVALUABLE | MET | confirmed (both quote `{'n':301,'exact':289,'near':0,'hard':12}`, `credit rows ungated: 277`, `581/581 exact`, `-> PASS` verbatim) | disagree-unresolved — genuine judgment call: the report never reconciles the 301-row book-debit-calibration population (12 of which land in an undefined "hard" bucket) against the 581-row exit-arm population it separately reports as 581/581 exact; the source doesn't say whether "-> PASS" covers the "hard" rows |
| G2 coverage before any conditional number | MET | MET | confirmed | agree |
| G3 `MIN_CELL_N=20` enforced, thin cells not read | MET | MET | A: confirmed. B: number mismatch — B's supporting claim "smallest read tercile cell n=51" is contradicted by other non-thin/read cells printed in the same report that are smaller (H3 MID `n(HIGH)=20`; walk-forward TEST `bear_put_spread` cells n=36/39/42/44/46 for os_ratio and rvolz20) | agree (verdict itself unaffected — MET either way) |
| G4 no annualised return/Sharpe/time-to-recover | MET | MET | confirmed | agree |
| G5 out-of-fold discipline | MET | MET | confirmed | agree |
| Anti-tuning (single frozen variant, no swept boundaries/windows) | MET | MET | confirmed | agree |
| H1(a) — HIGH os_ratio shows lower exit capture than LOW | NOT MET (combined with H1(b) in A's single row) | NOT MET | confirmed | agree |
| H1(b) — HIGH os_ratio shows larger sub-arming give-back share than LOW | NOT MET (combined with H1(a) in A's single row) | NOT MET | confirmed | agree |
| H1 mechanism test — frozen `be_after:0.50` variant beats PROD (LOO, both-window) | NOT MET | NOT MET | confirmed | agree |
| H2 `rvolz20` descriptive (exploratory, no adoption path) | MET (caveated: no directional verdict claimed) | MET | confirmed | agree |
| H3 `amihud20` control — separation absorbed by illiquidity? | NOT EVALUABLE | NOT EVALUABLE | confirmed | agree |
| Selection (secondary) — within-structure, walk-forward TRAIN-fitted boundaries | NOT EVALUABLE | NOT EVALUABLE | confirmed | agree |
| VERDICT: VOLUME-CONDITIONS-EXITS | NOT MET | NOT MET | confirmed | agree |
| VERDICT: LIQUIDITY-PROXY | NOT EVALUABLE | NOT MET | confirmed (both quote `amihud_collapse=False`, "evaluable cells 1 ... not collapsed" accurately) | disagree-unresolved — judgment call: whether the report's own printed `amihud_collapse=False` is a definitive computed result usable for this clause, or whether it inherits H3's own NOT EVALUABLE status (which both analysts assigned) since only 1 of 3 amihud terciles has both sides ≥ MIN_CELL_N |
| VERDICT: PATH-VOL-PROXY | NOT MET | NOT MET | confirmed | agree |
| VERDICT: NULL | MET | MET | confirmed | agree |

## Violations list

- **Analyst B, G1 row**: grades calibration a clean MET on the strength of the report's self-printed `-> PASS`, without reconciling the undefined "hard: 12" bucket (12 of 301 book-debit-calibration rows not in the "exact" bucket) against the separately-printed 581/581 exit-arm figure. Both analysts disclosed the same underlying numeric inconsistency as a Deviation, but B is the one who resolved that disclosed ambiguity into an unqualified MET — this is the kind of favorable rounding the protocol asks to be flagged.
- **Analyst B, VERDICT LIQUIDITY-PROXY row**: grades this clause NOT MET using the identical H3 evidence (`amihud_collapse=False`, "evaluable cells 1") that B itself grades NOT EVALUABLE on the H3 row, with no disclosure of or reconciliation for this internal-consistency gap between the two rows.
- **Analyst B, G3 row**: the supporting claim "smallest read tercile cell n=51" mischaracterizes the report — smaller non-thin cells are printed elsewhere (H3 MID `n(HIGH)=20`; walk-forward `bear_put_spread` TEST cells at n=36/39/42/44/46). Does not change the G3 verdict.
- **Analyst B, H1(a)/H1(b)/H2 rows**: grades these using the report's NON-BEAR DEBIT / BEAR DEBIT / CREDIT groupings without disclosing that these are not per-option-structure cuts, though the pre-registration explicitly requires "within structure from the first look" as an inherited closed-thread rule. Analyst A disclosed this exact gap as Deviation #3; Analyst B's Deviations list omits it.
- Both analysts flag `git 66cd01a (... working tree dirty)` — correctly noted by both, not a violation, but repeated here since it bears on reproducibility of every row above.

## Validator observations

- Both analysts independently and identically surfaced the G1 population inconsistency (301 vs 581 vs the 586 implied by summing the debit descriptive tables), the missing LOO median for the VOLUME-CONDITIONS-EXITS wording, the undefined `gb%` column, and the H1(b) variant's "5 rows changed" falling below the study's own `MIN_CELL_N=20` — strong convergent evidence these are report-level gaps rather than analyst transcription error, independent of the G1/LIQUIDITY-PROXY disagreements above.
- Neither analyst's underlying numbers conflict with the report anywhere I did not already flag; the disagreements above are both interpretive (how to read an internally ambiguous or underpowered report result), not transcription errors.
```

</details>
---


## 2026-08-13 — bear_put demotion mechanism CHOSEN: card-level selection veto (§1.4), hedge sleeve carved out

Operator decision, not a new study. No backtest run; no numbers change.

**The verdict being implemented** (2026-08-11, `bear_deploy` +
completed-book holdout): all pre-registered DEMOTE criteria fired at n=164
out-of-sample; bear SELECTION is unfixable (0 of 496 conditioned subsets
positive, best subset still −0.231); bear as a HEDGE is real (pays on the
deployed book's worst decile, date-level corr −0.13, D2 met on all three
criteria; D4 pick rule `|delta|` DESCENDING; ≤ ½ size).

**Mechanism chosen: card veto, not intake veto, not Tier-C-status-quo.**
The three candidates and why the middle one won:

1. **Intake veto** (bear_call treatment) — REJECTED. §4's hedge sleeve picks
   from "the day's bear candidates", i.e. analysis emissions; an intake veto
   would remove the only instrument that pays on the book's worst dates. The
   operator's constraint was explicit: bear_put must survive as a hedge.
2. **Card rule §1.4** — CHOSEN. `bear_put_spread` / `long_put` never deploy as
   a selection play, however thin the day's A/B supply; the §4 sleeve is
   carved out by name. Emissions, rows, and the sleeve's candidate pool are
   untouched.
3. **Tier-C status quo** (the 08-11 closed-thread position: "resolved WITHOUT
   a mechanism") — SUPERSEDED. Empirically equivalent on the historical book
   (all 370 bear rows were already Tier C or VETO; zero deployments change),
   but Tier C is "skip when capital-constrained", which left a thin-day path
   for a bear_put into the top-3. The card rule closes it and gives the deploy
   morning a one-line rule instead of a soft expectation.

**Files:** `deployment-rules.md` §1.4 (new) + §4 lead paragraph;
`deployment-evidence.md` closed-threads "bear_put DEMOTION question" updated
with the supersession. The `long_put` inclusion follows the demote family as
studied (bear debit = `bear_put_spread` + `long_put`, the ratchet's own
definition); `bear_call_spread` stays intake-vetoed, unchanged.

---

## 2026-08-13 — method-config audit: −25 veto RETIRED, OIConfirm dropped from Score (in-v4), codex engine retired

Not a data study — a cross-read of this log + `deployment-rules.md` against
`config/prompts/analysis-framework.md`, `config/prompts/analysis-methods/claude.md`,
`docs/conviction-score.md`, and `scripts/analysis_pipeline/config.py`.
No backtest run.

### 1. Already aligned — nothing to fix
The v4 trim (`score_flow`/`score_dealer` dropped, `iv_pct` sizing flag not a
gate, `bear_call_spread` intake veto, `score_total` decision-irrelevant
tie-break) is correctly stated everywhere it is referenced (framework Step 5,
method docs, architecture.md, deployment-rules §6).

### 2. `conviction-score.md` — ≈−25 `IVspr` veto RETIRED
Carried a STALE tag since the matched-pair redefinition + 2026-07-02 paper
filters; never re-derived. Now RETIRED outright — no fixed `IVspr` threshold
as a play-level veto. The column stays: one of only two decision-relevant
enrichment columns (`deployment-evidence.md`, `ml-plan.md`), through
`bear_put_spread × iv_spread` (confirmed archive/04 §3, archive/05 §2,
archive/06; 6th read in this file's 2026-08-11 close-out).

### 3. `OIConfirm` REMOVED from the deterministic conviction `Score` — in v4
Input `oi_confirm_pct` was killed in the 2026-08-11 ML full-column sweep
(r ≈ −0.03 vs realized P&L, composition artifact; long annotated
"placeholder only"). The derived −2/−1/+1/+2 component
(`lib/flow_summary/core.py` `_oi_confirm_points` → `score_flow_rollup`) is
deleted; single-day Score ceiling 14 → 12 (17 → 15 with persistence).
`Score`/`ScoreLabel` are LLM-visible inputs, so by the letter of the `vN_`
convention this is a version bump; **operator decision 2026-08-13: fold into
v4, no tab rename** — v4 was 2 days old. Discontinuity marker: v4 rows dated
≤2026-08-12 scored with the old composition. The `oi_confirm_pct` column,
`OIConfirmPct` rollup field, and the `enrich_oi` chain all STAY (eod_iv
feeds `iv_spread`; the column remains study-readable).

### 4. Codex engine retired
`config/prompts/analysis-methods/codex.md` deleted; `codex` removed from `ENGINES`;
AnalysisGPT tabs (v3_ and v4-era) stay in the spreadsheet as historical,
nothing writes to them; `/options summary` reads AnalysisClaude only. This
also disposes of the two contradictions the audit found in codex.md (§299
score-band promotion language vs the tie-break-only rule; §180 "two to four
plays" vs the 8-play coverage floor) — moot with the file.

### 5. No rollup-column removal
`ROW_COLUMNS`/`ROLLUP_METRIC_COLS` unchanged. Era-stable schemas for the
study loaders, and the ML-search reopen condition is "new columns" — the
non-decision-relevant columns (oi_confirm_pct, cpir, iv_skew, iv_pct) are
cheap provenance, not clutter.

---
