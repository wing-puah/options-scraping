# Architecture reference

Detailed per-file responsibilities, data contracts, and resume/idempotency semantics.
`CLAUDE.md` keeps only the compact map — **read the relevant section here before editing
`lib/` or `scripts/` code**, and keep this file in sync when responsibilities move.

Sections: File layout · Research tier (studies) · Daily trade journal · Command variants ·
Analysis pipeline data contract.

## File layout (detailed)

```
lib/                        ← shared modules, imported by scripts, never run directly
  barchart/                 ← Barchart scrapers + feed parsers ONLY (scrape/parse, no logic).
                              `from lib.barchart import BarchartSession` re-exported from __init__
    session.py              — BarchartSession (Playwright login + CSV download). Also holds the
                              feed-interception fetchers: fetch_history_fast (ONE page navigation
                              captures the authenticated historical feed, later contracts re-issue
                              it with `symbol=` swapped — no per-contract page load) and
                              fetch_options_overview_history (IV history)
    options.py              — per-contract historical option prices (price-history URL + parse,
                              mark-to-mid)
    iv_history.py           — pure URL builder + feed-row parser for the options-overview IV
                              history (daily IV / IV rank / IV percentile, up to ~2yr)
    underlying.py           — underlying-stock price-history URL builder (reuses the option
                              price-history feed + options.parse_history_series)
    corporate_actions.py    — corporate-actions (earnings/dividend) feed URL + JSON parser
  parsing.py                — `to_float`: the single Barchart numeric-cell parser (strips , $ %
                              and sentinels); imported across barchart/, flow_summary, backtest
  baseline.py               — market-level daily baseline: per-date aggregate row schema,
                              staleness-aware trailing window, percentile context markdown
                              (pure; tab I/O in scripts/build_baseline.py)
  iv_history.py             — per-ticker IV-percentile enrichment (pure; consumes
                              lib/barchart/iv_history.py, kept OUT of the barchart package).
                              `IV_ENRICH_COLUMNS`/`IV_MARKER_COLUMN` = the iv/iv_rank/iv_pct +
                              `iv_pct_enriched_on` columns appended to the compiled flow file.
                              `as_of_iv_cells_with_status` picks a ticker's values AS OF trade
                              date D (most-recent on/before, staleness-windowed; rank/pct as
                              decimals, iv in points) plus WHY: ok | stale_fallback |
                              out_of_window | empty_series | fetch_error → `iv_pct_status`
                              (`out_of_window` = the feed's ~2yr window, measured from the RUN
                              date, starts after D — that date's IVpct is gone for good).
                              `iv_pct_from_flow_rows` / `iv_coverage_from_flow_rows` read the
                              enrichment back off the rows for the analysis
  csv_utils.py              — parse_csv (strips Barchart footer)
  counterpart_iv.py         — pure logic for the IV-spread counterpart fetch: which missing legs
                              to fetch (`needed_counterparts`), the per-date sidecar schema/name,
                              and the `build_iv_lookup` the rollup folds in. Shared by
                              scripts/collector/fetch_counterpart_iv.py (producer) and
                              lib/flow_summary/core.py (consumer) so keys + IV units agree
  price_catalyst.py         — pure logic for the price/earnings-catalyst enrichment grounding
                              the two pipeline-computed Step-5 score components: column
                              constants, `as_of_price_cells`/`as_of_earnings_cells` pickers
                              (NO LOOK-AHEAD: only bars/events on/before D), read-back reader,
                              and the `score_price`/`score_catalyst` scorers keyed off each
                              play's `key_level`/`direction`. I/O in fetch_price_catalyst.py
  structure_names.py        — the ONE canonicalisation of the structure name a play's text uses
                              (models write "bear put debit spread" etc., which the downstream
                              substring matchers don't key on — the silent-wrong case priced a
                              vertical as its naked long leg). Called by BOTH
                              scripts/backtest/classify.py and live_loop mapping's play parser,
                              so backtest and live match can never disagree about a play's name
  mech_regime.py            — mechanical market-regime label (`mech_cell`), a pure function of
                              signal date + the frozen SPY/VIX table
  drive_client.py           — DriveClient, StorageClient protocol, file naming helpers
  sheets_client.py          — read/write Google Sheets tabs; `_get_spreadsheet(id)` targets the
                              journal workbook, `_ensure_tab(min_cols=)` sizes new tabs

scripts/                    ← entry points, each maps to a workflow step
  collector/scrape_flow.py — scrape barchart → Drive; live (--mode) or historical (--date/--start)
  compile_flow.py           — compile a day's hourly etfs-flow + stocks-flow snapshots into one
                              deduped CSV per type (trade-identity dedup) →
                              {prefix}-{YYYYMMDD}-compiled.csv in Drive. NOTE: a compile re-run
                              regenerates the file and DROPS every enrichment column; the next
                              enrichment --backfill restores them
  gc_flow.py                — garbage-collect raw snapshots: re-verifies every raw trade is in
                              the compiled file, then trashes the raws (recoverable). --all
                              sweeps all compiled dates. Daily after compile (GitHub Actions)
  build_baseline.py         — one market-level aggregate row per trading date (lib/baseline.py)
                              → BaselineDaily tab. Idempotent by date; --backfill self-heals
  backfill_mech_cell.py     — fill `mech_cell` on analysis rows that predate the column or were
                              written with a missing/stale SPY/VIX table. Writes ONLY that
                              column (add_or_update_column). A stored label that no longer
                              reproduces is KEPT and logged as DRIFT (exit 2), never silently
                              replaced, unless --force. Needs a fresh table — `make mech-regime`
                              refreshes it. Daily after compile via Actions
  align_tab_headers.py      — realign an analysis tab's header row with config.ROW_COLUMNS
                              (append_rows writes POSITIONALLY, so a short header mislabels
                              every later column). Repairs only when drifted columns are empty
                              or are schema columns in the wrong position; else aborts that tab
                              untouched. --dry-run first
  collector/enrich_oi.py    — for every distinct contract in a day's compiled flow file, scrape
                              the per-contract price-history (fetch_history_fast) and APPEND:
                              `oi_d`, `oi_prev` (last trading day before D), `oi_change`
                              (open-confirmation signal), `vol_d`, EOD-settlement greeks
                              `eod_iv`/`eod_delta`/`eod_gamma`/`eod_vega` (prefixed to
                              distinguish from the intraday snapshot greeks), `oi_enriched_on`
                              (provenance + resume marker). NO separate cache — the compiled
                              file on Drive is the only store; checkpointed back every 50
                              contracts + on exit (incl. interrupt). Resume is per-contract via
                              the marker (empty results marked attempted); --force clears.
                              Needs D+1, so the newest date is skipped until it exists
  collector/fetch_iv_percentile.py
                            — for every distinct TICKER in a compiled flow file, scrape a small
                              window of its Barchart IV history around D and APPEND the
                              lib/iv_history.py columns (above). Same enrich-in-place /
                              checkpoint-every-50 / per-ticker-marker / --force pattern as
                              enrich_oi, but needs no D+1 (the latest date is enriched too).
                              Prints a DEPTH EXHAUSTED banner when `out_of_window` covers more
                              than DEPTH_EXHAUSTED_SHARE of a date's pending tickers. Needs
                              BARCHART_EMAIL/PASSWORD. One-shot backfill: `make
                              fetch-iv-percentile-all`
  collector/fetch_counterpart_iv.py
                            — the paper-faithful IV spread needs a matched call+put at the same
                              (strike, expiration); traded flow almost never carries both legs.
                              For each single-sided in-window (10–60 DTE) (strike, expiry),
                              scrape the MISSING opposite leg's history and store its settlement
                              IV/OI/volume/delta as-of D in a per-date Drive sidecar
                              `counterpart-iv-{YYYYMMDD}.csv` (lib/counterpart_iv.COUNTERPART_COLUMNS;
                              IV in points; `price` = day-D mark for the paper's min-price
                              filter). Paper filters applied at consumption (build_iv_lookup):
                              IV in [3, 200] pts, OI > 0, price ≥ $0.125 when known; sub-$5
                              underlyings skipped at selection. Idempotent via `fetched_on`;
                              --force clears. Date-keyed so backtest and live share one path
  collector/fetch_price_catalyst.py
                            — per TICKER, scrape underlying price history + earnings feed, pick
                              as-of-D cells (no look-ahead; yfinance forward-earnings fallback
                              only near-live) and APPEND the price/earnings columns. Same
                              checkpoint/resume/--force pattern (marker:
                              `price_catalyst_enriched_on`). Feeds score_price/score_catalyst.
                              `make price-catalyst` wraps it
  collector/fetch_underlying_ohlc.py
                            — underlying stock OHLC cache for studies that need real bars →
                              backtests/underlying_ohlc_cache/. Date flags select TICKERS and
                              drive the coverage gate; they do not window the feed.
                              Split-adjusted tickers land in rescaled_tickers.txt (a basis
                              warning — % moves stay valid, $ moves are withheld)
  collector/fetch_counterpart_history.py
                            — fetches the opposite-type same-strike mirror of every book entry
                              leg into the SAME backtests/option_history_cache/ under the SAME
                              filename convention, so the existing pricing path reads them with
                              no code change (makes VOL structures priceable). Resumable
                              (--limit N)
  analysis_pipeline/        — full pipeline (run via `python3 -m scripts.analysis_pipeline`):
                              fetch → headless engine call (isolated session) → expand to
                              per-ticker rows → append to the engine's tab.
                              · config.py    — ALL user-tunable settings: engine registry
                                (model/method/tab), retries, timeout, fetch defaults, sheet
                                schema, prompt contract
                              · fetch.py     — Drive → markdown: scored rollups, top-N raw
                                trades, cross-section, hedge pressure, baseline, persistence
                              · core.py      — implementation (fetch/analyze/write, engine
                                runners, row expansion, CLI)
                              · __main__.py  — entry point
  backtest.py               — analysis-driven: reads analysis plays → models each as signed legs
                              (`scripts/backtest/legs.py`: `TKR:exp:strike:C|P ±qty` per line,
                              serialized to the `legs` column; fully generic in leg count —
                              single/vertical/ratio/butterfly/condor/box/calendar/diagonal;
                              same-contract legs merged) → per-leg pricing (Barchart history →
                              flow reappearance → Black-Scholes), real-first at any leg count
                              (uniform-BS ONLY for *synthesized* iron condors at non-listed
                              strikes) → netted signed position value → unified P&L
                              `(V−entry_net)/abs(entry_net)` over the path to min(nearest-leg
                              DTE, cap); daily marks clamped to the arbitrage-free range for
                              single-expiration defined-risk structures (`_defined_risk_bounds`)
                              → realized exit + MFE/MAE; per-day series in `daily_price_csv`
                              (docs/backtest-reference.md). Shared internals (analysis load,
                              history fetch, results writer, classify_and_build) in
                              `scripts/backtest/shared/` — imported by core.py and proxy.py,
                              never cross-imported
  backtest/proxy.py         — proxy-backtests plays the real backtest never covered: diffs the
                              analysis tab against BacktestResults (identity =
                              signal_date+ticker+play-prefix), records WHY skipped
                              (`unsupported`/`no_strike`/`no_expiry`/`no_history`/`unpriced`),
                              then evaluates via a fallback chain — (1) snap legs to nearest
                              listed contract with history (bounded by proxy.max_strike_steps/
                              max_expiry_deviation_days, real-first), (2) Black-Scholes off a
                              donor's `Price~`/`IV` history (OFF by default, `proxy.bs_fallback`),
                              (3) direction-only trend verdict, (4) unevaluable — same exit
                              rules as the real backtest → BacktestProxy tab +
                              backtests/proxy_results.csv, idempotent; cache-first, scrapes
                              missing neighbors unless --cache-only
  journal/ · live_loop/     — PRODUCTION tier; journal/ steps are numbered sNN_*.py and its
                              helpers live in journal/lib/; see §Daily trade journal below
  backtest_study/ · study_review/ · study_map/ · study_charts/
                            — RESEARCH tier; see §Research tier below
  auth_drive.py             — one-time OAuth2 flow for Drive
```

## Pipeline health check — the collection-tier watchdog

`scripts/check_pipeline.py` + `.github/workflows/pipeline-health.yml` (cron `45 1 * * 2-6`).
Answers one question: **did every collection stage actually run, and produce enough?**

### Why it exists

GitHub emails the repo owner when a SCHEDULED WORKFLOW FAILS. That covers a job that ran and
crashed, and nothing else. The gaps it leaves:

- `enrich-oi.yml`, `fetch-counterpart-iv.yml` and `backfill-mech-cell.yml` have **no cron**.
  All three fire on `workflow_run` off Compile Flow, gated on its success. If Compile Flow
  fails or is skipped they never run — and **a job that never ran emails nobody.**
- GitHub silently DROPS scheduled runs under load.
- GitHub DISABLES every schedule in a repo after 60 days with no commits.
- A step exits 0 having done nothing (auth quietly returning empty).

So the checker asserts the EVIDENCE in Drive/Sheets, never an exit status. A gap exits
non-zero, and that failure is the alert. No `continue-on-error`, no `|| true`.

### The two traps it is built around

**The stale-calendar trap.** The obvious "was this a trading session?" source is
`spy-vix-daily.csv` — but Compile Flow WRITES that file. A dead pipeline leaves a stale
calendar, so a checker reading it concludes "no session, nothing expected, all clear"
*precisely when everything is broken*. `sessions_from_yfinance()` therefore queries SPY live
and never reads pipeline output; a failed fetch is `EXIT_UNGROUNDED` (3), never a pass. This
also keeps the repo's no-holiday-table rule (§Daily trade journal, `journal/lib/analysis.py`):
a live SPY bar IS the calendar, and asking SPY alone sidesteps that CSV's known one-legged
holiday rows.

**The GC trap.** `gc_flow.py --last 3` runs inside Compile Flow and TRASHES raw snapshots once
they are verified present in the compiled file. For any past session `snapshots == 0` is the
HEALTHY steady state, so the `flow_present` check accepts a compiled file in their place.
Counting snapshots would fail on every historical date.

### Structure

Pure verdict logic, I/O in a thin shell — the `align_tab_headers.py::plan()` split, so every
false-alarm case is a plain unit test in `tests/test_check_pipeline.py` with nothing mocked.

- `evaluate(state, stages, sessions) -> [Finding]` — pure; no I/O, no clock.
- `summarise(findings, ...) -> (exit_code, report)` — pure.
- `silence_gap(state, sessions)` — how many newest sessions hold no flow data at all.
- `collect_state(client, stages, sessions)` — all Drive/Sheets I/O; one bounded
  `flow_corpus()` sweep plus one download per (session, prefix).

Coverage is computed live by importing `update_enrich_logs.py`'s `_oi_fields` / `_iv_fields` /
`_price_fields` / `_check_cp`. It deliberately does **not** read the `EnrichLog` tab: nothing
schedules `update_enrich_logs.py`, so that tab is only as fresh as the last manual run —
trusting it would be the stale-state false-all-clear bug all over again. `_price_fields()` was
added for this caller and is **not** written to `EnrichLog` (leaving that tab's schema, and
its hand-anchored spill formula, untouched).

### Config — `config/pipeline-health.yml`

One block per stage: `kind`, `lag_sessions`, `min_complete` (decimal fraction), `prefixes`.
Plus `lookback_sessions`, `max_silence_sessions`, `commit_age_warn_days` and
`chain_complete_utc_hour`.

`chain_complete_utc_hour` (23) handles the IN-FLIGHT session. Compile Flow fires at 22:30 UTC
on the session it compiles, so before that hour the current day's downstream evidence
legitimately does not exist. `settled_sessions()` drops it, and lag then counts back from the
newest SETTLED session — if today is in flight, yesterday's OI is not due either, because it
needs today's open interest. This costs CI nothing (the watchdog runs at 01:45 UTC, when the
newest session is already the previous UTC date); it exists so a hand-run check during market
hours stays quiet instead of teaching the operator to ignore it.

`lag_sessions` is the false-alarm defence — the newest N sessions of a stage report `not-due`,
never `MISSING`. **`enrich_oi` has `lag_sessions: 1`** because it is structurally D+1: the OI
*change* for session D needs D+1's open interest, so `enrich_oi.py` holds the newest compiled
date back until its next trading day lands. Lag is counted in SESSIONS, not calendar days, so
a Monday check walks back to Friday rather than into the weekend.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | every due stage left its evidence |
| 1 | gaps — **this is the email** |
| 2 | bad config or arguments |
| 3 | could not ground the verdict (yfinance/Drive unreachable) — never a pass |

Failures also emit `::error` annotations, capped at `MAX_ANNOTATIONS` (GitHub renders only 10
per step) with an explicit line naming how many were dropped — a silent truncation would read
as "that was all of it", which is the exact lie this script exists to catch.

### The 60-day trap, and its accepted limit

The checker fails when the newest commit is older than `commit_age_warn_days` (45), giving
~2 weeks of warning before GitHub's 60-day rule disables every schedule here. Actions activity
does NOT reset that clock; only commits do. **Stated limit:** this warns *before* the cutoff
but cannot help *after* it — once the schedules are disabled, this workflow is disabled too.
Recovery is re-enabling them in the Actions tab. An external dead-man's-switch is the only
thing that would survive that, and it was deliberately not built (new secret, new third-party
dependency).

### Secrets

`GOOGLE_OAUTH_TOKEN_JSON_CONTENT`, `GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_SPREADSHEET_ID`. **Not**
`GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT` — Sheets authenticates with the same OAuth2 token as
Drive (`lib/sheets_client.py::_get_client`), and no Python in this repo reads a
service-account variable, despite several older workflows still passing one.

The workflow installs the FULL `requirements.txt`, not `requirements-compile.txt`: importing
the coverage helpers transitively pulls `playwright` (via `lib/barchart`) and `scipy` (via
`backtest.helpers`) even though this job never scrapes. The pip packages satisfy the imports;
there is deliberately no `playwright install`, since no browser is ever launched.

## Research tier — backtest tuning studies

Never imported by production, never scheduled. Reports land in `backtests/study_output/`
(scratch, gitignored); conclusions in `research/current.md`; metric definitions
in `research/glossary.md`; the replication protocol in
`research/replication-protocol.md`.

**`scripts/backtest_study/`** — run via `python3 -m scripts.backtest_study {list,run}`. The studies
themselves sit in four family folders, `f1_selection/` → `f2_management/` → `f3_structure/` →
`f4_deployment/` (pick it, manage it, wrap it, fund it) — the same taxonomy `scripts/study_map/
catalog.py::FAMILIES` renders onto the study map, and the test suite asserts a module's folder
equals its catalog `family`. `lib/` holds the shared substrate: import-only (except `book.py
--validate`) and carries no verdict of its own — see `research/study-map.md` for what each study
in the family folders concluded.

- `run.py` — runner; every report carries a provenance header (git sha + era + input row
  counts). Flags: `--date`, `--dry-run`, `--cache-only` (no scraping), `--redo` (re-evaluate
  frozen rows), `--all`, `--era`. A designed refusal is PROMOTED to `-latest.txt`; a genuine
  failure DELETES it, so a study never has a report that no longer reproduces.
- `lib/era.py` — **which export era a study runs on.** The single encoding; read its module
  docstring before touching any input path.

  A `vN_` prompt bump renames the LIVE Sheets tabs in place, so the bare export name
  `analysis - BacktestResults.csv` does not name a fixed population — it names whatever the
  live tab held when it was exported. On 2026-08-15 a refresh turned four months of v3
  evidence into 14 dates of v4 with no code change: five studies refused on calibration gates
  and fourteen silently promoted reports computed on a 74-row book.

  | era | prefix | detection |
  |---|---|---|
  | `current` (default) | none — the bare exports | whatever `detect_era` reports |
  | `v3` | `analysis - v3_*.csv` | `score_flow` present AND populated |
  | v4 | — | `score_flow` absent (analysis) or present-but-blank (results/proxy) |

  Presence alone is NOT the test: `RESULT_COLUMNS` deliberately keeps `score_flow` /
  `score_dealer` on v4 so loaders keep working, so the results exports carry the column in
  both eras and only the values separate them. A future v5 also lacks a populated
  `score_flow` and would report here as "v4" — add its discriminator at that bump.

  Two designed refusals, inherited by every study from the runner rather than restated per
  module: **exit 3** when the exports are not the era asked for, or disagree with each other
  (a half-finished re-export); **exit 2** when the era holds fewer than `MIN_ERA_DATES` (30)
  distinct signal dates. The floor is a POWER floor — permanently satisfied once an era
  reaches it — not a stored figure that rots on the next refresh. Studies needing more check
  again with their own number (`ml_combination` needs 31 and says so).

  Selected via `STUDY_ERA`, set for a whole run by `run --era v3`. `load_book(check_era=False)`
  is the escape hatch for a caller deliberately mixing eras (`v4_bridge`, and the studies that
  pin a v1/v2 comparison export); it must say why.
- `lib/harness.py` — FROZEN exit-replay engine. Do not edit: every recorded conclusion rests on
  it; changing it invalidates all prior tuning conclusions.
- `lib/book.py` — pooled real+proxy book loader with dedup + the exact-replay calibration gate
  (bs-tier rows excluded by default). Era-scoped: resolves its three exports from `lib/era.py`,
  enforces the era, and applies the date floor. `diag` carries `era`, `n_dates`, `date_range`.
  `--validate` passes `min_dates=0` — the diagnostic's job is to describe whatever book is
  there, including one too thin to study.
- `lib/underlying.py` — daily stock bars (real OHLC → `Price~` close-only fallback; the all-legs
  widening harness.py must not get). `lib/underlying_features.py` — as-of-entry price-STATE
  columns (rv20/rv_parkinson/semivar_dn/atr14_pct/eff_ratio/vrp/beta; the OHLC-only two carry
  a smaller denominator — always print `coverage()`).
- `lib/protocol.py` — purged walk-forward, date-clustered CIs, LOO.
- `lib/macro_calendar.py` — scheduled macro events (FOMC/minutes/CPI/NFP/PCE) as as-of
  features, from the hand-authored `config/macro-events.yml`; `next_event` is strictly-after
  and refuses past each type's `verified_through` (an unpublished schedule is never "nothing
  ahead"). Event distance keys off the ENTRY session; pre-open vs post-open decides day 0.
- `lib/live_select.py` — the ONE sanctioned research→production import (see account_sim below).

### account_sim

Config-driven and stateless: `config/account-sim.yml` is the whole parameter surface —
capital, risk %, positions/day, the two delta-notional caps, the cap/capital grids, hedge
fraction, dense-episode definition, A2/A3/A5 thresholds, and the compounding arm's
`mark_interval`/`budget_ceiling`. Copy it and pass `--config` to simulate a different account;
there are no per-parameter CLI flags. Nothing under `gates:` — the gates are logic checks with
nothing to configure.

The gates are **G2–G5**, and there is deliberately no G1. It was a checksum of the deployed
book line (`220 positions / 90 dates / $63,553`) against constants in
`config/account-sim.yml`; removed 2026-08-15 because those constants fingerprinted ONE export
and so fired on every legitimate data refresh, whose only fix was to re-type them. The
property it stood in for — the FROZEN `lib/harness.py` replay still behaving identically — is
a code property and moved to the pytest suite. The calibration numbers it printed
(`debit_calib`, `n_credit_ungated`, the B1 line) are still reported, in a **BOOK CALIBRATION**
section that renders no verdict; quote them as the provenance of the book, never as evidence
the book is unchanged. The survivors were NOT renumbered — G2–G5 name specific checks in the
pre-registration and in every recorded verdict.

ONE `run account_sim` produces BOTH BASES as two arms of the same run:

- `account_sim-latest.txt` — the FROZEN, pre-registered, path-INDEPENDENT book: the basis
  every recorded conclusion rests on. Still the default report.
- `account_sim-compounding-latest.txt` — the COMPOUNDING sensitivity (`--compounding` alone
  runs just that arm). Re-marks SIZING to realized equity at fixed calendar intervals
  (`mark_interval`): both delta caps scale with marked equity; the per-position risk budget
  scales but is ceilinged by `budget_ceiling`. The arm is a FLAG, not a config file — the
  yml's `compounding:` block only parameterises it. `marked_equity` counts only positions
  CLOSED BEFORE the mark session (open positions are never marked to market) and is a sizing
  number only, so G3 still balances against STARTING capital. Post-hoc: A1–A6 were
  pre-registered against the path-independent sim; A2/A5 DO NOT TRANSFER (their B2 benchmark
  compounds too, so the ratio stops isolating the caps) — the report says so inline. G2–G4
  stay pinned to the frozen basis; G5 runs sighted-vs-blind on BOTH bases and must match on
  each.

Each run exports deployed/skipped positions (incl. the market/ticker/mechanical regime block)
to `account_sim-positions-latest.csv` (compounding arm:
`account_sim-positions-compounding-latest.csv`). **G5 ENFORCES that selection/sizing never
read an outcome field — keep it passing; it is what makes the sim safe to drive a
live-position agent.** Every ARM gets its own CSV stem; a different `--config` does NOT — it
overwrites the default export (the report records which config produced it), and any
non-default `--config` run also rebuilds `site/account-sim-charts.html` from that arm.

Other arms:

- `--structure-universe` — admits proxy debit rows the exact-replay gate withheld (stale
  trailing_stop exports, not unpriceable rows). Widens the CANDIDATE SET only; bs rows stay
  dropped, gates still run on the frozen book; separate artifact
  (`account_sim-positions-structure-latest.csv`).
- `--live-select` — an arm of a different kind: it changes WHO CHOOSES. Selection runs through
  the SHIPPED decision function — `scripts/journal/s06_recommend.py`'s `rank()` then `judge()` —
  instead of book.py's port of the ladder, so the simulated decision is the live decision and
  the drift between them is a measured number. Ledger, caps, sizing, and the frozen exit
  replay are unchanged (`live_select.py`; a `ranker` hook on `simulate()` that is None on
  every other path). Own report (`account_sim-live-select-latest.txt`) and CSV; treated as a
  SINGLE-arm run (never files under account_sim's stem, never drags the compounding arm
  along). G2–G4 stay pinned to the frozen basis; G5 is RE-RUN with the shipped selector in
  the loop; G6 (nothing reaches the ledger that rank() did not clear) runs on the arm. It
  evaluates NO pre-registered criterion — A1–A6 were registered against the frozen selector's
  candidate set and do not transfer.
  - `--live-select-entry-check {ibkr_verified,analysis_only}` — deployment-rules §3 reads the
    short-leg delta in IBKR at order entry and the analysis row does not carry it, so the
    default joins the book row's measured delta; the other supplies nothing. Both counts
    print either way.
  - `--live-select-no-llm` skips `judge()` entirely (fully offline). With judge() on, every
    prompt is cached by sha256 in `live-select-judgments.jsonl` — a re-run replays free, and
    the cache is the auditable record of what the model said. JUDGMENT_MODEL's cutoff
    OVERLAPS the analysis dates and G5 blinds record FIELDS, not a model's weights — it
    cannot detect a model that remembers an outcome. The arm bounds that with two ledger
    walks off one model pass (demote_policy skip vs ignore) and prints the delta; read that
    before reading anything the judge layer touched.

### Study review, map, charts

**`scripts/study_review/`** — two-analyst replication grading + digest:
`python3 -m scripts.study_review <name>` runs the study then analyst A/B + validator + digest
(`--skip-run` reuses `<name>-latest.txt`; `--dry-run` exercises the pipeline, no LLM).
Outputs `<name>-review-{analyst-a,analyst-b,validator}-latest.md` + `<name>-digest-latest.md`.

The analysts and the validator are ISOLATED — no filesystem, no tools — so they grade only
what the prompt inlines. Three artifacts go in: the pre-registration
(`research/pre-registrations/<family>/<name>.md`, read whole), the ERRATA file
(`research/<name>-errata.md`, `_` also tried as `-`) when one exists, and the report, in that
order. The errata is inlined as AUTHORITY, not commentary: a registration is immutable, so a
defect found in it after commit — a self-contradictory clause, a degenerate arm, an operator's
ratification of a population — is recorded there instead of being edited in, and a grader
shown only the registration is blind to the document that decides those clauses. That gap was
real: the 2026-08-31 `hedge_exposure` grading had all three graders disclose they could not
see the errata and grade the report's own quoted RATIFICATION text instead. The block says
explicitly that the errata never RELAXES a commitment — anything it does not resolve is still
graded against the registration as written. `--errata <path>` overrides discovery; `--no-errata`
skips it (only to reproduce a pre-errata grading run); a missing errata is the normal case and
warns on stderr, while an EMPTY one is fatal, so a run cannot look like it graded against one.

**`scripts/study_results.py`** — the per-ERA record: `make study-record` reads each
`<name>-latest.txt` and appends a section to `research/study-results/<family>/<name>.md`,
tracked and append-only, keyed on `(era, git sha)` so an unchanged re-run appends nothing.
The folder MIRRORS `scripts/backtest_study/`'s `f1_selection/` → `f4_deployment/` layout, and
derives it from the module's real parent directory rather than a table, so the two cannot
drift. Fields come from `study_map.summary.summarize()` — the same extractor the map uses, so
excerpts stay verbatim and there is no second header parser to go stale.

Necessary because a study runs on the CURRENT era only: the moment v4 matures and the suite is
re-run, v3's reports are overwritten and the v3-vs-v4 comparison would have nothing on the v3
side. `backtests/study_output/` is gitignored scratch; this is where a result survives. The
tuning log holds the reasoning, this holds the index.

**`scripts/study_map/`** — renders `site/study-map.html`: what each study asks (`catalog.py`,
hand-written — a study with no entry FAILS the test suite) + what its last run printed
(`summary.py`, quoted verbatim from the reports, never paraphrased; an excerpt with no
VERDICT block is labelled as the report's tail) + the newest current.md sections
(`tuning.py`). Rebuilt automatically after every study run and review; `make study-map` /
`make study-map-open` to force. `python3 -m scripts.study_map --check` (or `make
study-check`) prints per-study last-run status, no HTML.

The page opens with a **Reading queue** for the operator: `catalog.Study.attention` is a
hand-written one-liner (same authority tier as `verdict`) saying why the operator should
personally open a study's review artifacts NOW — set during the recording pass that changed
a card line, retracted a candidate, or left a decision pending; cleared back to `None` once
the operator has read/decided. Flagged studies render under "read first"; unflagged studies
whose `study_review` artifacts (digest/validator/analyst memos) exist in
`backtests/study_output/` render as "good to know" with mtime dates only. The flag points at
artifacts, never summarises them — the render layer stays conclusion-free.

**`scripts/study_charts/`** — renders a study's result as self-contained HTML; adds no
conclusion.

- `report.py` — strict parser for the fixed-width report (a changed section raises, never a
  half-drawn chart). `series.py` — positions-CSV series + `reconcile()`, which must agree
  with the report or the build fails. `cli.py` — the shared pipeline: arm auto-pairing on
  BOTH axes (structure and compounding), reconcile-or-write-nothing, docs copy rules.
  `assets/kit.js` = shared chart primitives, `assets/page.css` = tokens.
- Each run writes the study_output FRAGMENT (no doctype — what the Artifact publisher wants;
  `--standalone` wraps it) and a standalone `docs/<page>.html` (`--no-docs` skips). `docs/`
  is generated output and gitignored in full.
- Pages: `account_sim.py` (feasibility readout; capital read from the report, not hardcoded);
  `regime.py` (deployed book by market regime — mech_cell vs the model's market_regime, plus
  what the caps skipped per cell; account_sim pre-registers NO regime cut, so the study
  prints the cut ITSELF, flagged post-hoc, and the page reconciles against it — never add a
  regime table to the page without adding it to the study first); `compounding.py` (the
  compounding arm's readout + its EQUITY MARKS series; post-hoc, not pre-registered, and the
  page says so). The structure arm writes ONLY the fragment (chart-identical to the frozen
  book's page); an explicit `--docs` on it is refused.
- Do not add a statistic the study refuses to print: no annualised figure, no Sharpe, no
  time-to-recover.

## Daily trade journal — data contracts

**Package layout — the listing IS the flow.** Files are named `sNN_<step>.py` and run in that
order, so `ls scripts/journal/` reads top-to-bottom as the pipeline instead of having to be
reconstructed from the imports. The `s` prefix carries no meaning beyond legality: a Python
module name may not begin with a digit, so `01_pull.py` would be unimportable.

```
scripts/journal/
  __main__.py       CLI + the three commands (run / pull / recommend)
  config.py         the data contract every step reads — records, column orders, env names
  s01_pull.py       broker  -> journal/raw/<date>.json           (the only networked module)
  s02_reconcile.py  fills   -> PositionEvents, matched to the analysis that proposed them
  s03_risk.py       open book -> delta exposure vs the deployment caps
  s04a_report.py    -> journal/reports/<date>.md
  s04b_page.py      -> site/journal-<date>.html
  s05_writer.py     -> TradeJournal tab + journal/trades.csv
  s05b_bookwriter.py -> OpenBook tab + journal/open_book.csv   (the held book, triaged)
  s06_recommend.py  analysis + open book -> the deploy card   (the ONE model call)
  s07_recwriter.py  -> Recommendations tab + journal/recommendations.csv
  lib/              journal-only helpers the steps lean on — NOT the repo-root lib/
    rawpull.py      the on-disk pull schema; dependency-free, the boundary below
    flexparse.py    Flex export -> rawpull, plus the flat-book guards        (s01)
    greeks.py       Barchart EOD greeks for the open book, which Flex lacks  (s01)
    book.py         group the broker's flat legs into logical positions      (s03)
    analysis.py     the shared AnalysisClaude loader              (s02 AND s06)
    prompt.py       prompt text + response parsing for the judgment pass     (s06)
```

`scripts/journal/lib/` and the repo-root `lib/` never collide: the former is only ever reached
relatively (`from .lib import rawpull`), so an absolute `from lib import sheets_client` inside a
journal module still resolves to the repo-root package. Anything that outgrows journal-only use
moves UP to the repo-root `lib/`; nothing moves the other way.

PRODUCTION tier. Closes the analysis → trade → evidence loop daily. `scripts/live_loop/`
audits the same ground fortnightly and in more depth; both import
`scripts/live_loop/mapping.py`, so `ladder_tier()` (the sole encoding of
`docs/deployment-rules.md` §1–§3) has exactly one implementation.

**Pipeline and boundaries**

```
lib/ibkr/flex.py  ──►  s01_pull.py  ──►  journal/raw/ibkr-<date>-<HHMM>.json  ──►  everything else
                       (only networked module)     (immutable, schema v1)
```

`lib/rawpull.py` defines that file and is dependency-free — the boundary that keeps `lib.ibkr`
out of every later step (`s02`–`s07`); swapping broker transport is a change to
`s01_pull.py` alone. Pulls are written once and never overwritten (`rawpull.save()` raises on an
existing path) — a pull is the primary evidence for every journal row.

**One transport.** `s01_pull.py` holds `pull_flex()` — a Flex statement, fetched by default with
`IBKR_FLEX_TOKEN` (`--offline`/`--no-flex-web` reads only what is on disk). The Client Portal
Gateway transport was deleted 2026-08-15 (its native greeks and NetLiquidation are now
supplied by Barchart and `--net-liq`); pulls it wrote (`source: ibkr-cpapi`, greek
`source: ibkr`) still replay unchanged through `--from-raw` — the v1 schema didn't move —
which is why `DELTA_SOURCE_IBKR`/`DELTA_SOURCES_REAL` stay in `config.py`. The IBKR MCP is
**not** an alternative: it is claude.ai-hosted and absent from a CLI session's registry.
Every gap Flex does not close is filled from elsewhere, never silently — surfaced in the
report's §1 SOURCE LIMITS block (four gaps without the positions query configured, three
with it):

| Gap | Filled from |
|---|---|
| Greeks | Barchart EOD Delta/Gamma/Theta/Vega/IV per contract (`lib/greeks.py`), latest row **on or before** the session date — never after (lookahead) |
| Open positions | the declared `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID` query, else reconstructed by netting fills (`lib/flexparse.py`) |
| NetLiquidation | a NAV/Account-Information section on the positions query if it carries one (detected, never assumed), else `--net-liq` / `JOURNAL_NET_LIQUIDATION`, else the caps report "not evaluable" |
| Commission | nothing — recorded as `None`, never `0.0`; `net_cash` excludes it. `PositionEvent.commission` is all-or-nothing across a group's legs (same rule s03_risk.py applies to delta) |

**Two saved queries, one token — or one query carrying both sections.** A Flex query is
scoped to the sections it was saved with, so trades and open positions are normally separate
queries (`IBKR_FLEX_QUERY_TRADES_ID` + optional `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID`). Point
BOTH vars at ONE query saved with BOTH sections and the pull costs ONE handshake: `s01_pull.py`
fetches once and hands the same statement to both readers, and `flexparse._csv_sections`
splits on each section's own header line (delimited statements carry no section marker).
This matters because two handshakes on one token is what trips IBKR's 1018 rate limit.

**Raw-pull schema (v1)** — `trades[]` (exec_id, conid, side, size, price, commission,
realized_pnl, trade_time, order_id, open_close), `positions[]` (conid, signed position,
avg_cost), `contracts{conid}` (symbol, strike, expiry, right, multiplier), `greeks{conid}`
(delta/gamma/theta/vega/iv + `source`), `underlying_prices{symbol}`, `net_liquidation`.
`validate()` refuses a pull whose fill conid has no contract detail (identity would be a
guess) or whose greek claims a `source` in `DELTA_SOURCES_REAL` with a null delta.
`DELTA_SOURCES_REAL` is a frozenset (`ibkr`, `barchart`) — membership, not equality, is what
everything downstream tests, so a third feed can never be added by mistyping
`== DELTA_SOURCE_IBKR` and silently dropping positions out of the net delta. The Flex pull's
extra keys are additive and optional: `trade_time_tz`, `commissions_included`,
`book_reconstructed`, `book_warnings`, `flex_sources`, `flex_span`.

A `PositionRisk.delta_source` is **derived from the legs** (`risk.delta_source`), never
assumed from the transport (a Flex pull marks every position from Barchart EOD; `ibkr` only
appears replaying old pulls). It is written to the permanent TradeJournal row — the only
thing telling a later reader how far to trust the exposure figure. Legs marked from
different feeds are reported joined (`barchart+ibkr`), never collapsed — a half-marked
spread is the case worth noticing, not averaging over.

**Flex path specifics** (`lib/flexparse.py`, `lib/greeks.py`, `lib/ibkr/flex.py`)

- *Contract identity stays exact.* A Flex trades export carries `Conid` (16 fields), so
  nothing is price-inferred. `TradeID` becomes `exec_id` — what the journal dedupes on. Flex
  carries no `OrderID`, so fill grouping falls back to exact `trade_time` equality (a combo
  order fills every leg at the same instant), which `reconcile._group_key()` supports.
- *Netted book (no positions query).* `pull_flex()` takes MULTIPLE trades files (default:
  every `portfolio/input/trades_*.csv`) and nets signed quantity per conid across all of
  them — pass EVERY year you still hold positions from. `_provenance_warnings()` names two
  failure modes rather than let a partial book pass: a conid whose rows begin with a CLOSE
  (entry predates the oldest export → net understated) and a contract already expired as of
  the session (netting has no concept of expiry/assignment; named AND dropped).
- *Declared book (positions query configured).* `parse_positions()` reads the OpenPositions
  section directly (`book_reconstructed=False`); the netted book is still computed as a
  cross-check. Each conid where they disagree is SORTED into one of three buckets by
  `_book_diff_warnings` — because a saved trades query's period is far shorter than a
  position's life, most disagreements only say "the export cannot see back that far":
  `not_cross_checkable` (no fill for that conid AT ALL in the export — test
  `conid not in by_conid`, NOT "netting gives absent"; a conid whose rows net to zero is a
  real contradiction), `coverage_explained` (declared-absent/netted-present with uncovered
  time after the last fill), and `unexplained` — a missing fill or a corporate action, the
  ACTUAL finding. Only `unexplained` is loud; all three are counted in §6 via
  `raw["book_diagnostics"]`. The check is DEMOTED, never removed:
  `_refuse_a_contradicted_flat_book` and both exit-2 guards are untouched.
  LevelOfDetail trap: SUMMARY rows win when present, LOT rows are summed only when no
  SUMMARY row exists, and an unlabelled duplicate conid raises rather than guessing.
- *Two guards against a book that reads flat when it is not — both exit 2.* An OpenPositions
  statement with no OpenPositions section at all raises naming
  `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID` (a query saved without that section), rather than
  reading as an empty book. A DECLARED book that comes back empty while netting the trades
  export still finds unexpired positions raises instead of journalling a flat book (the
  2026-08-15 shipping bug: zero rows returned while 18 contracts were open, and the report
  printed "No open positions" with nothing to contradict it). Every fetched statement is
  kept verbatim at `journal/raw/flex-<date>-<HHMM>-{trades,positions}.{csv,xml}` (skipped
  on `--dry-run`) so a bad parse is diagnosable afterwards.
- *Timestamps are not UTC.* Flex writes `DateTime` as `YYYY-MM-DD;HHMMSS` in the account's
  configured timezone with no offset. `flexparse` emits a naive ISO-8601 string and sets
  `trade_time_tz` on the pull; nothing downstream compares across zones (grouping keys on
  equality, the journal on calendar date).
- *Two wire formats.* A saved query is defined as delimited text OR XML and the web service
  returns whichever it specifies. `flexparse._read_rows` detects the format from content
  (a fetched statement has no filename) and `XML_TRADE_ATTRS` renames the camelCase
  `<Trade>` attributes to the CSV column names — two renames are not case changes:
  `cost` → `CostBasis`, `assetCategory` → `AssetClass`.
- *Short statement windows.* `pull._web_sources` nets a fetched statement TOGETHER with the
  on-disk exports, not instead of them — a saved query's period ("Last Business Day") is far
  shorter than a position's life, and a contract untouched in the window leaves NO row at
  all, so the netted book would be short by a whole position with nothing anomalous to point
  at. `_window_warning` reads the `<FlexStatement>` window and says so — unless another
  export supplied fills predating it.
- *Coverage gaps between sources.* Earlier coverage is not contiguous coverage: a
  hand-export ending 07-24 plus a LastBusinessDay statement for 08-13 leaves 19 uncovered
  days, and a position CLOSED inside that span leaves no closing fill anywhere — it still
  nets non-zero and is presented as open (exactly how AMD/META/MU were mis-reported open on
  2026-08-15). `_coverage_gap_warnings` merges a per-source coverage interval (the declared
  statement window where there is one, else the observed min/max fill date across ALL rows
  read — any fill proves the day was covered) and names each uncovered span plus the
  tickers whose last fill precedes it. Weekend-only steps are not gaps; no holiday calendar
  is consulted, so a spurious one-day gap is possible — the safe direction to be wrong in.
  The remedy is always a fresh export in `portfolio/input/`, never re-scoping the saved
  query.
- `lib/ibkr/flex.py::FlexClient` — the token-authenticated Flex Web Service transport:
  `SendRequest` → ReferenceCode → `GetStatement`, polling through IBKR error 1019
  ("generation in progress" — the only retryable code). Transport and parsing only, no
  business logic. The token is a secret and is redacted from every log line.

**Records** (`config.py`) — `Leg` (signed qty; `leg_string()` emits the
`TICKER:YYYY-MM-DD:STRIKE:C +N` grammar `scripts/backtest/legs.py` parses, so a journal row
feeds straight back into the backtest), `Greeks`, `PositionEvent` (one order group = one
journal row), `PositionRisk`.

**Reconciliation** — fills group by order_id, falling back to identical trade_time. Identity
is the broker conid. Signal date = the nearest prior date the analysis book HAS (no holiday
calendar needed), bounded BOTH by `SIGNAL_LOOKBACK_DAYS` (3 book dates) and
`MAX_SIGNAL_AGE_DAYS` (10 calendar days) — the second bound stops a gap in the book (e.g.
the v4 cut-over) reaching back years and stamping a fill with another prompt version's
signal date. Market regime always comes from the date's MARKET row, never a play row.
`lib/analysis.py` is the shared AnalysisClaude loader (Sheets → CSV fallback).

**Open book** (`lib/book.py`) — legs group by (underlying, expiry). A vertical reassembles; a
calendar/diagonal is reported as two positions and the report says so. Grouping by
underlying alone would fuse a core long and a hedge overlay into a fictional structure.
Delta-notional is additive across legs, so the split changes position COUNT only, never net
exposure.

**Risk** — `signed_dn = delta × 100 × contracts × underlying`, identical to
`scripts/backtest_study/f4_deployment/account_sim.py::signed_dn`, so a live book and a simulated one
compare directly. Caps `per_position` 0.25 / `net` 2.50 are read from
`config/account-sim.yml` (that study calls them "a friction model, NOT a tuned parameter" —
why they transfer) but bind against the broker's NetLiquidation, not the study's $25k. The
per-position cap is evaluated on a TICKER's SIGNED total, not per (ticker, expiry) row —
lib/book.py splits a core vertical and the shorter-dated short leg financing it into two
positions, and that leg exists to cut the ticker's directional exposure. A position's delta
is all-or-nothing across legs: a spread priced on one leg would report the naked long's
delta, since the unpriced leg is precisely the hedge.

**Output** — `journal/reports/<date>.md` and `docs/journal-<date>.html`. The page recomputes
each figure from the records and reconciles against the report, writing nothing on a
mismatch (`s03_risk.py::assess` and `s04b_page.py::_breach_count` are two DELIBERATE
implementations of the cap rule — change both by hand, never share a helper). The charts are Cap utilisation
and Match confidence side by side, then Delta-notional by position full-width beneath, plus a
Recent recommendations panel — the last `PAGE_RECENT_REC_SESSIONS` analysis sessions'
current-generation rows, read back via `recwriter.recent_rows()` and filtered to
`session_date <=` the page's own session so a rebuilt historical page never shows a
recommendation that did not exist yet. That panel is DELIBERATELY OUTSIDE the reconciled set
`compute_figures()`/`reconcile()` cover: it reads back a different artefact
(`journal/recommendations.csv`) answering a different question, has no counterpart in the
markdown report, and is rendered only after the reconcile gate has already passed, so an
unreadable recommendations record degrades to an empty-state sentence rather than blocking
the page or raising `ReconcileError`. Rows go to the TradeJournal tab in
`TRADE_JOURNAL_SPREADSHEET_ID` and `journal/trades.csv`, deduped per-row on `source_ref`
(broker exec ids). The CSV is written first and its failure is fatal; a Sheets failure is
reported but never loses a row.

**Recommender** — `rank()` applies §1 VETO, §2 tiers, §3 geometry and cap headroom
deterministically; §1.4 routes bear debit to the hedge sleeve only. Its duplicate-exposure
and cap-headroom checks are ADVISORY — printed, filtered on neither. `judge()` then makes
the pipeline's ONLY model call, sees only survivors, and applies verdicts as annotations
onto that ordering — it never sorts, filters, or rebuilds the list, and a returned ticker
outside the survivor set is dropped.

The card is built AS OF a date (`--as-of`, default today) and three lookahead leaks are
closed against it. The analysis session comes from `analysis.latest_date_on_or_before()`,
never the unbounded `latest_date()` (which stays correct for `s02_reconcile.py`'s
backward-looking match — a fill has already happened, so ranking off the newest book date is
fine there and wrong here). The broker book comes from `__main__._raw_on_or_before()` — the
newest pull whose `trade_date` is ≤ the session, the filename prefiltering cheaply but
`raw["trade_date"]` confirming each candidate — and is marked AT the session, not
`date.today()` (which would stamp a replayed past card with today's DTE). With no qualifying
pull, `rank()` is handed an EMPTY `BookRisk` rather than the newest one on disk, so cap
headroom and duplicate exposure report NOT EVALUABLE instead of reading as clear.
`recommend.check_freshness()` enforces two refusals, both `StaleAnalysis`, only one
overridable: analysis past `RECOMMENDATION_MAX_AGE_DAYS` (aliased to `MAX_SIGNAL_AGE_DAYS`)
is refused unless `--allow-stale`; analysis dated after as-of is refused unconditionally —
that is lookahead, not staleness, and `--allow-stale` cannot reach it. `judge()` itself stays
unbounded: `JUDGMENT_MODEL`'s training cutoff overlaps the analysis dates, so every row is
stamped `judge_status`/`judge_lookahead_risk` (`config.JUDGE_LOOKAHEAD_NOTE`) rather than
treated as clean — the same concern `scripts/backtest_study/lib/live_select.py` documents for its
own judge layer.

**Recommendation record** (`s07_recwriter.py`) — every evaluated candidate (role
`deploy`/`hedge`/`veto`/`tier_c`) is flattened to `RECOMMENDATION_COLUMNS` (column-by-column
definitions: [`recommendations-reference.md`](recommendations-reference.md)) and written to the
Recommendations tab in `TRADE_JOURNAL_SPREADSHEET_ID` (the same workbook as TradeJournal) and
to `journal/recommendations.csv`, mirroring `s05_writer.py`'s CSV-first/CSV-fatal,
Sheets-non-fatal split. The two are DELIBERATELY not shared code: `s05_writer.py`'s failure loses
the day's trades, so generalising its helpers over (key, tab, columns) to also serve a
non-trade record would risk that module for a feature that isn't one — `s07_recwriter.py` mirrors
its structure instead and stays independent. `rec_id` ends in a sha256 of the row's content
(`REC_IDENTITY_EXCLUDED` drops `rec_id`/`generation`/`generated_at_utc` from the hash before
hashing), so an unchanged re-run of the same card appends nothing at all — even on a later
day — while a card whose judge verdict or cap headroom changed appends a new row at
`generation = n+1`. APPEND-ONLY was chosen over REPLACE-ON-CHANGE deliberately: if the 07:00
card said DEPLOY and a 15:00 re-run says RESERVE, both are true statements about their own
moment, and overwriting the first would destroy the only record of what was actually acted
on. `book_evaluable=False` resolves the blank-vs-false seam at serialisation:
`duplicate_exposure`/`headroom_ok` write as an empty cell, never `False`, when the book that
would have proven them wasn't available — the same missing/zero discipline the greeks get,
applied one layer up.

**Open-book record** (`s05b_bookwriter.py`) — one row per OPEN POSITION per marked session,
flattened to `OPEN_BOOK_COLUMNS` (column-by-column definitions, and the full flag vocabulary:
[`open-book-reference.md`](open-book-reference.md)) and written to the OpenBook tab in
`TRADE_JOURNAL_SPREADSHEET_ID` and `journal/open_book.csv`. It answers the question the other
two tabs structurally cannot: TradeJournal describes a trade at the instant it happened and is
never revisited, so nothing in it says that a position opened five weeks ago is now past its §5
exit date, sitting on an unpriced leg, or carrying the ticker that just breached its cap. Until
this step that only existed in `journal/reports/<date>.md` and the generated page — both local.

Same CSV-first/CSV-fatal, Sheets-non-fatal split as the other two writers, and the same
deliberate NON-sharing of their helpers, for the reason `s07_recwriter.py` states. Rows lead
with `status` (ATTENTION / WATCH / OK) and `flags`, derived by `flags_for()` from the numbers
beside them; the vocabulary and its three thresholds live in `config.BOOK_FLAG_SEVERITY` /
`EXIT_DUE_SOON_DAYS` / `EXPIRING_SOON_DTE` / `CAP_NEAR_UTILISATION`. FLAGS ARE ATTENTION, NEVER
VERDICTS — nothing downstream reads one, the caps still bind in `s03_risk.py` and the §5
deadline is still computed in `lib/exit_rules.py`, which is why those thresholds are allowed to
be round numbers with nothing fitted behind them.

`book_id` ends in a sha256 of the row's content, covering only the 27 `OPEN_BOOK_COLUMNS` —
identity and wall clock still excluded (`book_id`, `generation`, `snapshot_utc`) — so re-marking
an unchanged POSITION appends nothing while a genuinely re-marked one appends its own row at
`generation = n+1`. That is narrower than it used to be: the book-level facts (the net cap
block, the book counts, NetLiquidation, whether the book was reconstructed, the pull's notes)
were dropped from the row rather than hashed, so a position moving no longer re-appends the
WHOLE book the way it did when every row carried those totals identically — only the position
that actually changed appends a new generation. A net-cap flag flipping on a row still changes
that row's hash and re-appends it. Read the current book as "largest `as_of_date`, then largest
`generation` per position" (`latest_snapshot()` does exactly that, bounded by `on_or_before` the
same way `recwriter.recent_rows()` is — this read rule is unchanged by the trim). The
missing/zero discipline holds at this seam too: an unpriced position is written with BLANK delta
cells and `priced=False`, never a zero — `_net_delta_notional()` also recomputes the net when
`__main__._build_book` skipped `assess()` for want of NetLiquidation, so a 0.0 dataclass default
can never be recorded as a flat book.

**Privacy** — `/journal/` is gitignored in full (raw pulls carry account identifiers,
trades.csv carries live sizes and P&L; the TradeJournal tab is the only copy that leaves the
machine). The leading slash is load-bearing: a bare `journal/` would also exclude
`scripts/journal/`, the pipeline's own source.

## Command variants (full)

`CLAUDE.md` lists the canonical invocation per workflow; the full flag matrix is here.

```bash
# Compile a day's hourly flow snapshots into one deduped CSV per type (→ Drive)
python3 scripts/compile_flow.py                      # today (ET)
python3 scripts/compile_flow.py --date 2026-06-09
python3 scripts/compile_flow.py --start 2026-06-09 --end 2026-06-13   # weekdays in range
python3 scripts/compile_flow.py --date 2026-06-09 --dry-run   # report dup counts, no upload

# Garbage-collect raw snapshots once verified-present in their compiled file (→ Drive trash)
python3 scripts/gc_flow.py                            # today (ET)
python3 scripts/gc_flow.py --last 3                  # the 3 most recent compiled dates (what CI runs)
python3 scripts/gc_flow.py --all                     # sweep every compiled date
python3 scripts/gc_flow.py --all --dry-run           # report what would be trashed

# Append daily market-baseline rows to the BaselineDaily tab
python3 scripts/build_baseline.py                     # latest Drive date
python3 scripts/build_baseline.py --backfill          # every missing date (idempotent)
python3 scripts/build_baseline.py --backfill --dry-run

# Enrichments — all share: bare = latest date · --date · --backfill (idempotent) ·
# --dry-run · --force (clear columns/sidecar and re-scrape)
python3 scripts/collector/fetch_iv_percentile.py      # one-shot backfill: make iv-percentile ARGS="--backfill"
python3 scripts/collector/enrich_oi.py                # latest ENRICHABLE date (needs D+1)
python3 scripts/collector/fetch_counterpart_iv.py
python3 scripts/collector/fetch_price_catalyst.py     # make price-catalyst

# Full analysis pipeline
python3 -m scripts.analysis_pipeline                      # latest date, claude → AnalysisClaude
python3 -m scripts.analysis_pipeline --date 2026-04-21
python3 -m scripts.analysis_pipeline --date 2026-04-21 --tickers NVDA,AMD,SPY  # → AnalysisTickerSpecific
python3 -m scripts.analysis_pipeline --start 2026-04-14 --end 2026-04-18 --days 5
python3 -m scripts.analysis_pipeline --date 2026-04-21 --dry-run   # fetch+analyze, no write
python3 -m scripts.analysis_pipeline --model claude-opus-5         # override engine model
python3 -m scripts.analysis_pipeline --fetch-only                  # fetch + audit CSV only, no LLM

# Scrape historical data to Google Drive
python3 scripts/collector/scrape_flow.py --date 2026-04-21
python3 scripts/collector/scrape_flow.py --start 2026-01-02 --end 2026-05-30 --skip-existing

# Proxy-backtest untested plays
python3 -m scripts.backtest.proxy --config config/backtest.yml               # all dates, idempotent
python3 -m scripts.backtest.proxy --config config/backtest.yml --date 2026-04-21
python3 -m scripts.backtest.proxy --config config/backtest.yml --dry-run     # no sheet/CSV write
python3 -m scripts.backtest.proxy --config config/backtest.yml --cache-only  # no Barchart scraping
python3 -m scripts.backtest.proxy --config config/backtest.yml --date 2026-04-21 --redo

# Research-tier caches
python3 scripts/collector/fetch_underlying_ohlc.py     # every book ticker; --date/--dry-run
python3 scripts/collector/fetch_counterpart_history.py --dry-run
python3 scripts/collector/fetch_counterpart_history.py --limit 200   # resumable

# Studies (see §Research tier for the account_sim arms)
python3 -m scripts.backtest_study list
python3 -m scripts.backtest_study run bear_deploy      # also: --all, --date, --dry-run, --cache-only, --redo
python3 -m scripts.backtest_study run account_sim -- --config config/my-account.yml
python3 -m scripts.backtest_study run account_sim -- --compounding
python3 -m scripts.backtest_study run account_sim -- --structure-universe
python3 -m scripts.backtest_study run account_sim -- --live-select [--live-select-no-llm]
python3 -m scripts.study_review account_sim            # --skip-run reuses report; --dry-run no LLM
python3 -m scripts.study_review hedge_exposure        # auto-inlines research/hedge-exposure-errata.md
                                                      # --errata <path> · --no-errata to override
python3 -m scripts.study_map --check                  # or: make study-check
make study-map-open · make study-docs · make study-check
make study-chart CHART=regime OPEN=1 · make study-chart CHART=compounding OPEN=1 · make study-chart ARM=structure
python3 -m scripts.study_charts.account_sim [--standalone --open] [--positions <csv>] [--no-docs]
python3 -m scripts.study_charts.regime
python3 -m scripts.study_charts.compounding

# Daily trade journal
python3 -m scripts.journal                        # fetch → reconcile → risk → report → write
python3 -m scripts.journal --date 2026-08-14
python3 -m scripts.journal --offline              # read portfolio/input/ only, no network (alias --no-flex-web)
python3 -m scripts.journal pull                   # broker pull only
python3 -m scripts.journal --from-raw journal/raw/ibkr-2026-08-14-1615.json   # offline replay
python3 -m scripts.journal --dry-run              # no Sheets/CSV write, no LLM
python3 -m scripts.journal --no-llm               # deterministic only
python3 -m scripts.journal recommend              # deploy card for the NEXT session
python3 -m scripts.journal --from-flex portfolio/input/trades_*.csv       # offline (naming files implies it)
python3 -m scripts.journal --from-flex-positions portfolio/input/positions_*.csv
python3 -m scripts.journal --from-flex portfolio/input/trades_*.csv --flex-web  # named files, still fetch
python3 -m scripts.journal --net-liq 52000        # Flex reports no account equity
python3 -m scripts.journal --no-greeks            # skip the Barchart fetch

# Cleaning
python3 scripts/clean_generated.py --list         # targets, sizes, rebuild commands
python3 scripts/clean_generated.py --dry-run
python3 scripts/clean_generated.py --caches --yes # + the refetchable network caches
python3 scripts/clean_generated.py --only logs,site
python3 scripts/clean_generated.py --force        # ignore the citation pin scan
```

## Cleaning — what `make clean` may delete

`make clean` runs TWO cleaners, because the two halves need different rules:
`scripts/clean_generated.py` for the repo's scratch, and
`scripts/clean_study_output.py` for `backtests/study_output/` (whose pin scan protects
reports the tuning log cites or a study's gate greps for). The shared flags
`--dry-run` / `--yes` / `--force` in `ARGS` reach both; anything else goes to the first
alone, so `--caches` never hits the study cleaner's argparse.

`scripts/clean_generated.py` is a declarative table — one `Target` per class of output,
each recording `what` it is and the `regen` command that rebuilds it. The report prints
`regen` because that is the only question worth asking before deleting generated output.
**A target with no answer to "how do I get this back" does not belong in the table**, and
a test enforces it.

Two tiers: the default (local recompute — logs, `site/`, chart PNGs, stamped backtest
exports, bytecode, `portfolio/output/`) and `--caches` (needs the network to restore —
`audit/`, the OHLC cache, the sweep checkpoint, the regime table).

Four guards stand between a glob and an `unlink`. The first three run on EVERY candidate
on every run, dry or not, and a violation is a hard error that deletes nothing — not a
path quietly filtered out, because a glob matching a protected path is a bug in the table:

1. **inside the repo** — must resolve under the root; blocks `..` and symlink escape.
2. **not git-tracked** — `git ls-files` is the authority; a tracked file is source,
   whatever a glob thinks. Self-maintaining: it keeps `backtests/__init__.py` and
   `portfolio/*.py` safe without naming them.
3. **not protected** — `PROTECTED_PREFIXES`, matched by whole path SEGMENTS so root
   `journal` never shadows `scripts/journal`. These trees are all gitignored, so guard 2
   is blind to them; this list is their only protection.
4. **not cited** — the one soft guard. Files referenced by path in `research/`, `docs/`,
   `scripts/` or `config/` are PINNED and reported instead of deleted, because
   `backtests/` has no git history and a provenance line in the tuning log is the only
   thing marking an export as evidence. `--force` turns this off; nothing turns off 1–3.

**`backtests/` is not uniformly disposable**, whatever its `.gitignore` comment says. Held
out of the cleaner entirely, at no flag: `option_history_cache/` (~337MB of scraped option
history, hours to refetch), `to_evaluate/` (hand-exported Sheets CSVs that every study
loader reads by filename — an input, not a cache), and `live_loop/` (point-in-time IBKR
snapshots that cannot be refetched for a past date). The frozen `v1_*`/`v2_*` evidence
exports and the hand-written date-list `*.md`s are not matched by any glob, and the pin
scan is the backstop if one ever is.

Two exclusions worth knowing:

- `site/journal-*.html` is excluded from the `site` target. `make study-docs` rebuilds the
  study map and chart pages but NOT the journal pages — those need a real journal run
  against that date's broker pull, so a deleted page for a past date may be unrecoverable.
- `__pycache__` under a protected tree is PRUNED during the walk rather than collected and
  then refused. The bytecode there is genuinely disposable, but the guard is blunt by
  design; skipping a few KB is cheaper than carving an exception into a rule whose whole
  value is having none.

## Analysis pipeline — full data-contract detail

`python3 -m scripts.analysis_pipeline` (or `make analyze`) is the only way an analysis is
produced — it is never done in-context. The LLM step is an isolated headless session, so the
framework/method/raw data never enter the calling agent's context. Model-agnostic via
`--engine`: `claude` is the only registered engine and uses `claude -p` + `claude.md` →
AnalysisClaude. All operator-tunable settings live in
`scripts/analysis_pipeline/config.py`; `--model` overrides (default claude→`claude-opus-5`).

The prepared rollup carries, per ticker:

- a direction-agnostic conviction `Score` (0–12 raw), ranked on **extrinsic premium**
  (intrinsic stripped so deep-ITM financing flow can't buy rank) with an `otm` component
  crediting OTM-probability-weighted extrinsic flow
- pollution/exposure columns `Ext$`/`Fin%`/`ΔNot$`/`Hzn`/`OTM$`
- direction-bearing vol columns `IVspr`/`IVskew` (not scored)
- `IVpct` (Barchart options-overview IV percentile, 0–100 — the rich/cheap read that picks
  TF debit vs TF-S credit in framework Step 4; not scored, not directional) with its
  `iv_pct_status` provenance marker riding beside it (`IVPctStatus` in the rollup CSV) onto
  the analysis row
- a market-level **Hedge pressure** score (0–100) — see `docs/conviction-score.md`

Each play declares `flow_intent` (DIRECTIONAL/VOLATILITY/HEDGE/SYNTHETIC STOCK — a
classification of what the flow IS, **not** a confidence cap; folded upper-cased into the
play cell's bracket line) and emits `horizon` (14|60|180|720 — the DTE bucket of the
dominant expiry in the cited evidence) as its own column. Confidence is a `score` object
carrying the ONE model-scored Step-5 component (`{vol}`, intent-weighted: max 15 for
DIRECTIONAL/HEDGE/SYNTHETIC STOCK, 25 for VOLATILITY) plus required `key_level` +
`direction`; `price` and `catalyst` are pipeline-computed from fetched price-history and
earnings data grounded by those fields (`lib/price_catalyst.py`). All three land as
`score_price`/`score_vol`/`score_catalyst` beside `score_total` (0–50, 0–55 for VOLATILITY;
≥35 strong, 20–34 moderate, <20 weak — bands read, never emitted; decision-irrelevant, a
deterministic tie-break only).

**v4 trim (2026-08-11):** `score_flow` and `score_dealer` were dropped from the prompt AND
`ROW_COLUMNS` — the ML combination study found the score block adds nothing reproducible,
and `score_dealer` was judged off a vol-snapshot proxy rather than real per-name dealer
gamma. The cut-over is the standard `vN_` rename (see CLAUDE.md §Prompt versions): tabs
renamed in place, empty ones recreated with headers written fresh from `ROW_COLUMNS`, no
positional migration, `BaselineDaily` deliberately not versioned. The two names are KEPT in
`RESULT_COLUMNS` (`scripts/backtest/core.py`) so study loaders work on pooled v3+v4 exports
(blank on v4 rows). v4's 0–50 `score_total` is not comparable to v3's 0–100 — deliberate.

The analysis also emits a market-level `themes` array (`{theme, tickers, breadth, read}`)
grouping the day's flow into narrative clusters — presentation-only, never a multiplier on
any play's score. `--days N` (default 5) appends a multi-day persistence section tracking
recurring names.
