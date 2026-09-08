# Robustness review

Can the analysis, the backtest and the production loop be trusted, and what
beyond the queue would most improve returns and risk? Written 2026-09-07 for
the operator. One page, plain words, numbers in tables.

How it was made: four reviewers read one tier each (analysis, backtest,
production, research method). Every finding that could change a decision was
then handed to an independent skeptic told to refute it from the code. The
**Checked** column is that skeptic's verdict. Line numbers were read on the
date above and will drift; the file names will not.

How to maintain it: when an item is fixed, change its row to `FIXED <date>` and
link the commit. Do not add prose. A new review replaces this file.

<a id="short-answer"></a>
## The short answer

1. **The edge has never been measured net of costs.** No commission or
   slippage term exists anywhere in the backtest, the studies or their configs.
   Every leg is filled at mid, in and out. The rules that shipped rest on gains
   of +0.02 to +0.04 [R](glossary.md#r); a realistic cost per round trip is of
   that order. This is the first thing to fix, and it changes every number.
2. **The backtest can book P&L on days before the position exists.** A small,
   real bug. Fix it before the study suite is re-run, or the re-run bakes it in.
3. **Nothing yet separates "the model picks well" from "long calls worked in
   2024 to 2025".** No same-date mechanical benchmark and no beta decomposition
   has ever been run. Both are cheap and need no new data.
4. **The live loop does not close.** The journal labels a closing bull call
   spread as a bear call spread and tiers it VETO. No live-versus-backtest P&L
   comparison exists. The journal is not scheduled and last ran on 2026-09-03.
5. **Three cheap guards are missing in the analysis pipeline.** The "no data"
   skip can never fire, the tab header is never checked before a write, and no
   row records which prompt produced it.
6. **A lot is solid**: time-bounding of the deploy card, the None-versus-zero
   greek rule, the judge that cannot promote a play, era scoping, the
   date-clustered statistics, and the two already-run guards. See
   [What is already solid](#solid).

<a id="findings"></a>
## Findings

Size is my read of how much the item could move a P&L figure or a verdict.
Effort: S is hours, M is a day, L is more.

<a id="backtest"></a>
### Backtest

| # | What actually happens | Checked | Size | Fix | Effort |
|---|---|---|---|---|---|
| B1 | No cost model. Zero hits for commission, slippage or fee in `scripts/backtest/`, `scripts/backtest_study/`, `config/backtest.yml`, `config/account-sim.yml`. Marks are bid/ask mid (`lib/barchart/options.py`). | BUILT 2026-09-07 in worktree `.claude/worktrees/wf_129cdac5-757-5`, reviewer-approved, UNMERGED until the queue C/E campaign ends ([log](current.md#2026-09-07-later--robustness-review-twelve-items-built-six-landed-in-the-tree-six-wait-in-two-worktrees-for-the-campaign-to-end)) | High | Add `commission_per_contract` and `slippage_frac_of_spread` to `simulation:`; charge at entry and exit in `scripts/backtest/simulate.py`. Then run the cost-sensitivity study below. | S code, M study |
| B2 | The price grid starts the weekday after the signal, but the fill can land up to 5 days later. Days before the fill are priced by carry-forward and compared to an entry price struck later. A reproduction fired a +100% profit-target exit on a day before the position existed. About 4% of positions carry at least one such day. | BUILT 2026-09-07 in worktree `.claude/worktrees/wf_129cdac5-757-5`, reviewer-approved, UNMERGED until the queue C/E campaign ends ([log](current.md#2026-09-07-later--robustness-review-twelve-items-built-six-landed-in-the-tree-six-wait-in-two-worktrees-for-the-campaign-to-end)) | Med | Start the grid at the entry date, not signal date + 1 (`simulate.py` grid build, `classify.py::_entry_row_from_history`). Re-run and diff `results.csv`. | S |
| B3 | A contract that stops being quoted is marked at its last price to the end of the path, tagged `barchart`, and `pct_real_days` reads 1.0. Rare in general, but one v4 row (2024-05-15 NVDA 950/1050, strikes vanished at the split) exits `cap_open` at +72% on 70 frozen days. | BUILT 2026-09-07 in worktree `.claude/worktrees/wf_129cdac5-757-5`, reviewer-approved, UNMERGED until the queue C/E campaign ends ([log](current.md#2026-09-07-later--robustness-review-twelve-items-built-six-landed-in-the-tree-six-wait-in-two-worktrees-for-the-campaign-to-end)) | Med | Bound the carry to N days and emit a `barchart_stale` tag; make `pct_real_days` count leg-days. | S |
| B4 | Exits realise at the closing mark, so a gap books more than the target and less than the stop. This is symmetric by construction, and the frozen replay harness applies it the same way. The same close-only grid also misses intraday touches. | Partial: symmetric | Low | Note only. Fold into the cost study as a sensitivity. | – |
| B5 | A zero bid falls through to the last trade, usually the more conservative mark. But in a tail of about 5 to 8% of zero-bid rows the leg stays valued when its liquidation value is near zero. | BUILT 2026-09-07 in worktree `.claude/worktrees/wf_129cdac5-757-5`, reviewer-approved, UNMERGED until the queue C/E campaign ends ([log](current.md#2026-09-07-later--robustness-review-twelve-items-built-six-landed-in-the-tree-six-wait-in-two-worktrees-for-the-campaign-to-end)) | Low | Mark a zero-bid long leg at 0 when the ask is also 0; otherwise `ask/2`. | S |
| B6 | Underlying bars for the BS fallback are dividend-adjusted (`auto_adjust=True`) while strikes are not. Split rescaling survives either flag. This is bounded to BS-priced legs, which are OFF for the proxy tier. | Partial: bounded | Low | Set `auto_adjust=False`; keep `rescaled_tickers.txt` as the guard. | S |
| B7 | `pct_real_days` calls a day real if any leg is real. Affects 2 of 524 v4 rows. No study reads the exported column. | Partial: doc gap | Low | Say so in `docs/backtest-reference.md`. | S |
| B8 | The backtest had no already-run guard; the 2025-12-22 SPY duplicate came from a re-run. | In progress | – | `scripts/backtest/shared/identity.py` and `_drop_already_backtested` are in the working tree today, uncommitted. Commit them. | – |

<a id="analysis"></a>
### Analysis pipeline

| # | What actually happens | Checked | Size | Fix | Effort |
|---|---|---|---|---|---|
| A1 | The "no data" skip requires four markers; the scored path can emit at most two. A date whose Drive files are missing is analysed on empty tables, the row is written, and the duplicate guard then locks the date. | BUILT 2026-09-07 in worktree `.claude/worktrees/wf_129cdac5-757-6`, reviewer-approved, UNMERGED until the queue C/E campaign ends ([log](current.md#2026-09-07-later--robustness-review-twelve-items-built-six-landed-in-the-tree-six-wait-in-two-worktrees-for-the-campaign-to-end)) | Med | Skip when both flow sections are empty; refuse a write with zero plays (`scripts/analysis_pipeline/core.py`). | S |
| A2 | `append_rows` writes a header only into an empty tab and never compares the live header to the row keys. Four production writers rely on it. A drifted header mislabels every row silently. | Confirmed | Med | Assert header equals `list(rows[0].keys())` before appending (`lib/sheets_client.py`). | S |
| A3 | No row records the prompt or model that produced it. The framework and method digests are logged and written to `manifest.jsonl` on `--output-dir` runs only. | Confirmed | Med | Append `framework_sha256`, `method_sha256`, `model` to `ROW_COLUMNS` (append at end; align the tab header). | S |
| A4 | Output validation checks one key (`regime`). No per-play required keys or enums. Zero plays is logged, not refused. The retry loop logs which attempt won but persists nothing. | BUILT 2026-09-07 in worktree `.claude/worktrees/wf_129cdac5-757-6`, reviewer-approved, UNMERGED until the queue C/E campaign ends ([log](current.md#2026-09-07-later--robustness-review-twelve-items-built-six-landed-in-the-tree-six-wait-in-two-worktrees-for-the-campaign-to-end)) | Med | Validate `plays` and per-play enums; persist attempt count in the manifest. | S |
| A5 | The docs claim backfilled dates get day-after enrichment that a live run cannot. In fact enrichment is D versus D-1 and lands the same evening as D. Live rows since 2026-08-11 carry `oi_confirm_pct` on 202 of 203 rows. Only an intraday run reads an unenriched file. | FIXED 2026-09-07, uncommitted (messages only) | – | Fix two stale messages that say the newest date is "held back" (`enrich_oi.py`, `enrich-oi.yml`). | S |

<a id="production"></a>
### Production loop

| # | What actually happens | Checked | Size | Fix | Effort |
|---|---|---|---|---|---|
| P1 | Closing a spread inverts its label. The journal classifies on the fill's sign, not the resulting position. Reproduced: closing an NVDA 170/180 bull call spread journals `bear_call_spread`, confidence `NONE`, tier `VETO`. Every closed spread in `TradeJournal` since the journal shipped carries this. | FIXED 2026-09-07, uncommitted; 18 past CLOSE rows still inverted, repair needs a Sheets write | Med | Classify on the position after the fill, or skip classification on `CLOSE` (`scripts/journal/s02_reconcile.py`, `scripts/live_loop/mapping.py`). Re-derive past rows. | M |
| P2 | A missing NetLiquidation builds the book without `assess()`, so exposure prints 0.0 with real positions. The page reconciler catches it and raises before the fills and open book are written. | FIXED 2026-09-07, uncommitted | Med | Route the no-NetLiq path through `assess()` the way `s05b_bookwriter.py` already does. | S |
| P3 | After one failed Sheets write the rows are in the CSV, so every later run finds nothing fresh and never sends them. Same shape in the recommendations writer. | FIXED 2026-09-07, uncommitted | Med | Diff the sheet's own ids against all local rows, not against the fresh set (`s05_writer.py`, `s07_recwriter.py`). | S |
| P4 | Legs filled on different days become two events with contradictory tiers; a 1x2 ratio reads as a 1-lot vertical. | Partial: effect real | Med | Label unequal quantities as `ratio`; reassemble day-apart legs from `journal/open_book.csv`. | M |
| P5 | No closed live-to-P&L loop. Stage 2 of the fill mapping is named and unbuilt. Contract identity is recoverable from Flex (`Conid`) and the `legs` column, so the data is not lost. | Partial: data recoverable | High | Build Stage 2 off `TradeJournal` plus `open_book.csv`. See [Beyond the queue](#beyond). | L |
| P6 | The scrape exits 0 on zero rows and the watchdog catches it about one session later. A single dead prefix passes the watchdog green. | FIXED 2026-09-07, uncommitted | Low | `sys.exit(1)` on zero rows; a per-prefix row floor in `check_pipeline.py`. | S |
| P7 | `recommend` falls back to the research-tier CSV export when Sheets fails. Disclosed on the card and bounded to 10 days by the freshness check. | Partial: disclosed | Low | Make the fallback a warning that needs a flag. | S |
| P8 | The journal is not scheduled. Reports exist for 08-25, 08-26, 08-28, 08-31 and 09-03. Time exits and cap breaches surface only when someone runs it. | FIXED 2026-09-07, uncommitted; needs the `TRADE_JOURNAL_SPREADSHEET_ID` secret in CI | Med | A weekday cron for `python3 -m scripts.journal`, with the watchdog covering it. | S |

<a id="method"></a>
### Research method

| # | What actually happens | Source | Size |
|---|---|---|---|
| M1 | One structure in one cell carries the book. `bull_call_spread` is +$79.4k against a whole book of +$12.3k ([§7.2](../docs/deployment-rules.md#s7-2)). The docs say the ladder's in-sample circularity is "mitigated, not eliminated" ([evidence](deployment-evidence.md#why-the-tiers)). No same-date benchmark exists; `ml_combination`'s benchmark is the ladder itself. | docs, grep | High |
| M2 | No programme-level control for multiple testing, no sealed holdout, no stopping rule. `v4_bridge` runs five tests at 0.05 with no correction, by design. The one holdout (Feb to Apr 2026) was absorbed into the book. Candidates now held on the correlated window: `bear_arm` B2, `financed_spread` F3, `portfolio_delta` B, plus two provisional rules. | `v4_bridge.py`, [state of play](current.md#state-of-play) | High |
| M3 | The tier ordering's own core claim is tested unpaired. A versus B is p = .98 ([evidence](deployment-evidence.md#why-the-tiers)). The within-date paired test exists in `protocol.py` and has never been turned on the ladder. | docs | Med |
| M4 | The deploy card carries delta notional, a same-ticker duplicate flag and cap headroom. No SPY beta, no book correlation, no vol state. For a long-only bull call book, delta notional is a beta bet. | `scripts/journal/config.py` | Med |
| M5 | Three hedge verdicts were read on a drawdown curve the docs say understates drawdown by 40.2% ([evidence](deployment-evidence.md#the-curve-d3-was-read-on-understates-drawdown-2026-08-31-hedge_portfolio-arm-m)). `lib/mtm_curve.py` exists; nothing drawdown-shaped should use anything else. | docs | Med |
| M6 | The documentation load has produced real errors the docs admit: the era rename rewrote 14 reports, a study hard-coded "zero 2026 dates", two date tables are no-ops, two studies collided on the label `H3`. Three files restate the state of play. | [next-steps §0](next-steps.md#s0) | Med |

<a id="beyond"></a>
## Beyond the queue

What would most improve alpha and beta, and is not already in
[`next-steps.md`](next-steps.md). None of it needs new dates.

| # | Question | Data | Pass rule to pre-register | Why it comes first |
|---|---|---|---|---|
| N1 | **Cost sensitivity.** At what cost per leg does the Tier A/B edge vanish? | DRAFT registration 2026-09-07: [`cost_sensitivity.md`](pre-registrations/f2_management/cost_sensitivity.md). Have: entry and exit prices, leg counts, bid/ask in the option cache. | Tier A and B [meanR](glossary.md#meanr) > 0 with a date-clustered [CI](glossary.md#ci95-date-clustered-bootstrap) excluding zero at $0.65 per contract plus 25% of the quoted spread per leg. | Every queued item assumes an edge that may be a cost artefact. |
| N2 | **Base rate.** Do the picks beat mechanical bull call spreads on the same dates and tickers? | DRAFT registration 2026-09-07: [`mechanical_benchmark.md`](pre-registrations/f1_selection/mechanical_benchmark.md). Have: the flow CSVs give the universe, the option cache prices it. | Paired-by-date mean R against matched-geometry mechanical picks; CI excludes zero; every leave-one-date-out fold positive. | The only test that separates selection from "long calls worked". |
| N3 | **Beta decomposition.** How much of deployed P&L is SPY exposure? | Have: `underlying_ohlc_cache`, entry delta, SPY bars. | Regress position R on the underlying's and SPY's return over the hold; selection needs a positive intercept with CI excluding zero. | No study has asked whether this is stock-picking or beta. Also gives the card a beta figure (M4). |
| N4 | **Live slippage.** Realised live R minus backtest R on matched fills. | Partly: journal fills exist; needs P1 fixed and Stage 2 built. | At least 25 matched positions; paired mean difference with date-clustered CI. Declare in advance that a gap worse than −0.10 R invalidates every shipped delta smaller than that. | Sets how precisely the whole programme can measure its own edge. Shipped deltas are +0.02 to +0.04 R. |
| N5 | **Seal a holdout.** A commitment, not a study: dates after 2026-08-11 are untouchable until a named count. | DRAFT registration 2026-09-07: [`holdout_seal.md`](pre-registrations/f4_deployment/holdout_seal.md). Have: the live dates as they price. | One read of Tier A/B mean R and [PF](glossary.md#pf-profit-factor) on unseal; no re-cut. | Everything "waits on new dates" and will consume them as an in-sample refresh, which is what happened to the last holdout. |
| N6 | **Join attrition.** Which emitted plays never get a real backtest row, and are they missing at random? | Have: 2,325 analysis rows against 524 real rows. | Tier and structure mix of priced versus unpriced; a gap above 5 points in Tier A share means the book is liquidity-selected. | If the unpriceable plays are the wide ones, every headline is on a favourable subsample. |
| N7 | **Programme-wide null.** How many `MET` criteria would the current arm inventory produce on shuffled dates? | Have: `arm-index.md` is the inventory. | A candidate must clear its own alpha and sit outside the permuted null. | Prices every held candidate at once instead of one more study each. |

Two items already in the queue matter more than their position suggests and
are not repeated here: the written regime-label rule
([§2.9](next-steps.md#s2-9)), because the label flipping on 2 of 5 dates moves
rows across tiers; and the operator-read test ([§2.5](next-steps.md#s2-5)).

<a id="order"></a>
## Suggested order

1. Fix B2 and add the cost knobs (B1). Commit B8. Then re-run the suite once,
   so the stale-suite re-run in [next-steps §0](next-steps.md#s0) answers
   both at the same time.
2. Run N1 and N2 on that book. If the edge survives costs and beats the
   mechanical benchmark, the programme has a floor. If not, stop tuning exits.
3. Guards A1 to A3 and P2, P3. Half a day in total. Schedule the journal (P8).
4. Fix P1, then build Stage 2 (P5) and run N4. This is the only path to the
   live evidence the queue has waited on since 2026-08-11.
5. Seal the holdout (N5) in writing before the next live date prices.
6. N3, N6, N7 as one f4 registration each.

<a id="solid"></a>
## What is already solid

- The deploy card cannot see the future. `latest_date_on_or_before`,
  `_raw_on_or_before` and the two freshness refusals are correct and covered
  by tests.
- The judge cannot promote a play. Non-survivors are dropped, annotations
  are applied in place, retries are bounded, failure degrades to no annotation.
- A missing greek is `None`. Enforced at three layers, no `or 0` on the
  exposure path.
- The already-analysed guard is one Sheets read before any spend, with tests.
  The backtest guard is landing today (B8).
- Era scoping refuses a wrong or thin export, and the study statistics are
  date-clustered with purged walk-forward and mandatory ex-window cuts.
- Journal dedup keys off the durable CSV, and `gc_flow` re-reads both sides
  from Drive before trashing anything.
- The analysis input reads are backward-looking: baseline, `mech_cell`, price
  and earnings cells, and the OI enrichment (A5).

<a id="provenance"></a>
## Provenance

- **Commit:** `7b9b71c`, plus the uncommitted backtest guard.
- **Exports:** `BacktestResults` 2026-09-06 (524 rows), `AnalysisClaude`
  2026-09-07 (2,325 rows).
- **Reviewers:** four reading agents, one per tier, ran twenty independent
  refutation checks on the decision-relevant findings. The author added grep
  and direct reads for B1, P3, P8, M1 to M3.
