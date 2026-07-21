# Architecture reference

Detailed per-file responsibilities, data contracts, and resume/idempotency semantics.
`CLAUDE.md` keeps only the compact map — **read the relevant section here before editing
`lib/` or `scripts/` code**, and keep this file in sync when responsibilities move.

## File layout (detailed)

```
lib/                        ← shared modules, imported by scripts, never run directly
  barchart/                 ← Barchart scrapers + feed parsers ONLY (scrape/parse, no logic).
                              `from lib.barchart import BarchartSession` re-exported from __init__
    session.py              — BarchartSession (Playwright login + CSV download)
    options.py              — per-contract historical option prices (price-history URL + parse,
                              mark-to-mid)
    iv_history.py           — pure URL builder + feed-row parser for Barchart's options-overview
                              IV history (daily IV / IV rank / IV percentile series, up to
                              ~2yr). Field mapping is a best guess to VERIFY against a live feed
                              capture. Fetch (feed interception) lives on
                              BarchartSession.fetch_options_overview_history
    underlying.py           — underlying-stock price-history URL builder (reuses the option
                              price-history feed + options.parse_history_series)
    corporate_actions.py    — Barchart corporate-actions (earnings/dividend) feed URL + JSON parser
  parsing.py                — `to_float`: the single Barchart numeric-cell parser (strips , $ %
                              and sentinels). Replaces the old per-module `_to_float` copies;
                              imported across the barchart package, flow_summary, and backtest
  baseline.py               — market-level daily baseline: per-date aggregate row schema,
                              staleness-aware trailing window, percentile context markdown (pure
                              functions; tab I/O lives in scripts/build_baseline.py)
  iv_history.py             — per-ticker IV-percentile enrichment (pure logic; consumes
                              lib/barchart/iv_history.py — kept OUT of the barchart package):
                              `IV_ENRICH_COLUMNS`/`IV_MARKER_COLUMN` (the iv/iv_rank/iv_pct +
                              `iv_pct_enriched_on` columns appended to the compiled flow file),
                              `as_of_iv_cells` (pick a ticker's iv/iv_rank/iv_pct AS OF trade
                              date D from a parsed Barchart series, most-recent-on/before within
                              a staleness window, formatted: rank/pct as decimals, iv in
                              points), `iv_pct_from_flow_rows` (read `{SYMBOL: iv_pct}` back off
                              the enriched rows — how the analysis consumes it). The per-name
                              "rich vs cheap" read (Barchart IV percentile) the framework's
                              Step-4 TF-vs-TF-S structure choice needs. Pure functions;
                              scrape/Drive I/O live in scripts/collector/fetch_iv_percentile.py. NO
                              separate cache tab — enriched in place like enrich_oi
  csv_utils.py              — parse_csv (strips Barchart footer)
  counterpart_iv.py         — pure logic for the IV-spread counterpart fetch: which missing legs
                              to fetch (`needed_counterparts`), the per-date sidecar
                              schema/name, and the `build_iv_lookup` the rollup folds in. Shared
                              by scripts/collector/fetch_counterpart_iv.py (producer) and
                              lib/flow_summary/core.py (consumer) so contract keys + IV units
                              always agree
  price_catalyst.py         — pure logic for the price/earnings-catalyst enrichment that grounds
                              the two pipeline-computed Step-5 score components: enrichment
                              column constants (`price_d`/`price_5d_ago`/20d+50d high-low-SMA/
                              `next_earnings`/`last_earnings` + marker), `as_of_price_cells` /
                              `as_of_earnings_cells` pickers (NO LOOK-AHEAD: only bars/events
                              on/before trade date D), read-back reader, and the
                              `score_price`/`score_catalyst` scorers keyed off each play's
                              `key_level`/`direction`. Shape mirrors lib/iv_history.py; scrape/
                              Drive I/O live in scripts/collector/fetch_price_catalyst.py
  drive_client.py           — DriveClient, StorageClient protocol, file naming helpers
  sheets_client.py          — read/write Google Sheets tabs

scripts/                    ← entry points, each maps to a workflow step
  collector/                ← data collectors (path-invoked; group the scrape/enrich/fetch step).
                              scrape_flow.py, enrich_oi.py, fetch_iv_percentile.py,
                              fetch_counterpart_iv.py, fetch_price_catalyst.py live here — run as
                              `python scripts/collector/<name>.py`
  collector/scrape_flow.py — scrape barchart → Drive; live (--mode) or historical (--date/--start)
  compile_flow.py           — compile a day's hourly etfs-flow + stocks-flow snapshots into one
                              deduped CSV per type (trade-identity dedup) →
                              {prefix}-{YYYYMMDD}-compiled.csv in Drive
  gc_flow.py                — garbage-collect raw snapshots: re-verifies every raw trade is
                              present in the compiled file, then trashes the raws (recoverable).
                              Separate from compile; --all sweeps all compiled dates. Daily
                              after compile via .github/workflows/compile-flow.yml
  build_baseline.py         — compute one market-level aggregate row per trading date
                              (lib/baseline.py) → append to BaselineDaily tab. Idempotent by
                              date; --backfill self-heals missed days. Daily after compile via
                              .github/workflows/compile-flow.yml
  fetch_iv_percentile.py    — for every distinct TICKER in a compiled flow file (trade date D
                              from the filename), scrape its Barchart options-overview IV
                              history for a small window around D
                              (BarchartSession.fetch_options_overview_history with
                              startDate/endDate — a handful of rows, not the full ~2yr series →
                              lib/barchart/iv_history.parse_iv_history), pick the values AS OF D
                              (lib/iv_history.as_of_iv_cells; exact date else most-recent within
                              a staleness window), and APPEND columns to every row of that
                              ticker: `iv` (points), `iv_rank`/`iv_pct` (decimals),
                              `iv_pct_enriched_on` (run date — provenance + resume marker). Same
                              enrich-in-place pattern as enrich_oi: NO separate cache tab — the
                              compiled file on Drive is the only store; checkpointed back every
                              50 tickers + on exit; resume is per-ticker via the marker (empty
                              ones marked attempted so they aren't re-fetched); --force clears.
                              Unlike enrich_oi it needs NO D+1 data, so the LATEST compiled date
                              is enriched too. --backfill = every compiled date (one-shot: `make
                              fetch-iv-percentile-all`). Daily after enrich_oi via
                              .github/workflows/enrich-oi.yml (latest date only). NOTE: a later
                              compile_flow re-run drops these columns; the next --backfill
                              re-enriches. Needs BARCHART_EMAIL/PASSWORD
  enrich_oi.py              — for every distinct contract in a day's compiled flow file (trade
                              date D from the filename), scrape the Barchart per-contract
                              price-history (via BarchartSession.fetch_history_fast: ONE page
                              navigation captures the authenticated historical feed, then every
                              other contract re-issues that feed directly with its `symbol=`
                              swapped — no per-contract page load; falls back to a full
                              navigation if a re-issue fails) and APPEND columns to each flow
                              row: `oi_d`, `oi_prev` (D-1, last trading day before D in the
                              series), `oi_change` (= oi_d − oi_prev, the OI change on trade day
                              D — the reference-03 open-confirmation signal), `vol_d`,
                              EOD-settlement greeks `eod_iv`/`eod_delta`/`eod_gamma`/`eod_vega`
                              (prefixed to distinguish from the intraday snapshot greeks already
                              in the row), and `oi_enriched_on` (the run date — provenance +
                              resume marker). All new columns are lowercase + underscore. NO
                              separate per-contract cache: each history is scraped, the fields
                              extracted, and the raw discarded — the compiled file on Drive is
                              the only store. The enriched CSV is checkpointed back to Drive
                              every 50 contracts and once more on exit (incl.
                              KeyboardInterrupt/error), so an interrupted run never loses
                              scraped work. Resume is per-contract: any contract whose rows
                              carry `oi_enriched_on` is skipped (incl. ones Barchart returned
                              nothing for — marked attempted so they aren't re-fetched forever);
                              --force clears the columns and re-scrapes. --backfill enriches all
                              compiled dates (D-1 is always available). Daily after compile via
                              .github/workflows/enrich-oi.yml. NOTE: a later compile_flow re-run
                              regenerates the compiled file and drops these columns; the next
                              --backfill re-enriches.
  fetch_counterpart_iv.py   — the paper-faithful IV spread needs a matched call+put at the SAME
                              (strike, expiration); the traded flow almost never carries both
                              legs (→ IVspr ~98% blank on flow alone). For each single-sided
                              in-window (10–60 DTE) (strike, expiry) that traded, scrape the
                              MISSING opposite leg's Barchart price-history (same
                              fetch_history_fast path as enrich_oi) and extract its settlement
                              IV / OI / volume / delta AS OF trade date D. Store one row per
                              fetched counterpart in a per-date Drive sidecar
                              `counterpart-iv-{YYYYMMDD}.csv` (schema
                              `lib/counterpart_iv.COUNTERPART_COLUMNS`; IV in points; `price` =
                              day-D mark for the paper's min-price filter, blank in older
                              sidecars). Counterpart legs are filtered at consumption
                              (`build_iv_lookup`) per the paper: IV in [3, 200] pts, OI > 0,
                              price ≥ $0.125 when known; sub-$5 underlyings are skipped at
                              selection (`needed_counterparts`). Idempotent/resumable (a
                              contract with a non-blank `fetched_on` is skipped, incl. empty
                              ones; --force clears). The pure logic (which counterparts to
                              fetch, the sidecar lookup, the shared contract key) lives in
                              `lib/counterpart_iv.py`; the rollup reads the sidecar via
                              `build_iv_lookup` and folds the counterpart legs into
                              `_flow_ticker_rows`' matched-pair + skew accumulators. Date-keyed
                              so backtest (historical D) and live (latest D) share one path. Run
                              daily after enrich_oi.
  fetch_price_catalyst.py   — for every distinct TICKER in a compiled flow file (trade date D
                              from the filename), scrape the underlying's Barchart price history
                              + corporate-actions/earnings feed, pick the as-of-D cells
                              (lib/price_catalyst pickers — no look-ahead; yfinance forward-
                              earnings fallback only for near-live dates), and APPEND the
                              price/earnings columns to every row of that ticker. Same
                              enrich-in-place/checkpoint/resume/--force pattern as
                              fetch_iv_percentile (marker: `price_catalyst_enriched_on`).
                              Feeds the pipeline's code-computed `score_price`/`score_catalyst`.
                              `make price-catalyst` wraps it
  analysis_pipeline/        — full pipeline package (run via `python3 -m
                              scripts.analysis_pipeline`): fetch → headless engine call
                              (isolated session; `--engine claude|codex`, `--model` overridable)
                              → expand to per-ticker rows → append to the engine's tab
                              (AnalysisClaude / AnalysisGPT). Source of truth for /options
                              analyze; the skill just shells out here.
                              · config.py    — ALL user-tunable settings: engine registry
                                (model/method/tab), retries, timeout, fetch defaults, sheet
                                schema, prompt contract
                              · fetch.py     — Drive → markdown: scored rollups, top-N raw
                                trades, cross-section, hedge pressure, baseline context,
                                persistence
                              · core.py      — implementation (fetch/analyze/write, engine
                                runners, row expansion, CLI)
                              · __main__.py  — entry point
  backtest.py               — analysis-driven: reads analysis plays → models each as a list of
                              signed legs (`scripts/backtest/legs.py`: `TKR:exp:strike:C|P
                              <±qty>` per line — qty last, sheet-safe — serialized to the `legs`
                              column; a play's leg-string is parsed directly and is fully
                              generic in leg count, so
                              single/vertical/ratio/butterfly/condor/box/iron-condor/calendar/diagonal
                              all map onto legs; same-contract legs are merged) → per-leg
                              pricing (Barchart per-contract history → flow reappearance →
                              Black-Scholes), real-first for every structure at any leg count —
                              uniform-BS applies ONLY to *synthesized* iron condors (wings at
                              non-listed strikes) — netted into a signed position value →
                              unified P&L `(V−entry_net)/abs(entry_net)` over the path to
                              min(nearest-leg DTE, cap); daily marks clamped to the
                              arbitrage-free range for any single-expiration defined-risk
                              structure (`_defined_risk_bounds`, generalizing the old
                              1:1-vertical clamp) → realized exit + MFE/MAE; per-day series
                              stored in `daily_price_csv` (see config/backtest-reference.md).
                              Shared internals (analysis load, history fetch, results writer,
                              classify_and_build) live in `scripts/backtest/shared/` — imported
                              by both core.py and proxy.py, never cross-imported
  backtest/proxy.py         — proxy-backtests plays the real backtest never covered: diffs the
                              analysis tab against BacktestResults (identity =
                              signal_date+ticker+play-prefix), records WHY each play was skipped
                              (`unsupported`/`no_strike`/`no_expiry`/`no_history`/`unpriced`),
                              then evaluates via a fallback chain — (1) snap legs to the nearest
                              listed contract WITH Barchart history (bounded by
                              `proxy.max_strike_steps`/`max_expiry_deviation_days`, real-first
                              pricing), (2) Black-Scholes off a donor contract's `Price~`/`IV`
                              history (per-day sigma; NO yfinance), (3) direction-only
                              underlying-trend verdict, (4) unevaluable — same
                              `simulation:`/`credit:` exit rules as the real backtest →
                              BacktestProxy tab + backtests/proxy_results.csv, idempotent;
                              cache-first discovery, scrapes missing neighbors unless
                              --cache-only (see config/backtest-reference.md §BacktestProxy)
  auth_drive.py             — one-time OAuth2 flow for Drive
```

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
python3 scripts/gc_flow.py --all                     # sweep every compiled date
python3 scripts/gc_flow.py --all --dry-run           # report what would be trashed

# Append daily market-baseline rows (regime baseline) to the BaselineDaily tab
python3 scripts/build_baseline.py                     # latest Drive date
python3 scripts/build_baseline.py --backfill          # every Drive date missing from the tab (idempotent)
python3 scripts/build_baseline.py --backfill --dry-run

# Enrich a compiled flow file with each ticker's Barchart IV percentile (IVpct source: iv/iv_rank/iv_pct columns)
python3 scripts/collector/fetch_iv_percentile.py                   # latest compiled date
python3 scripts/collector/fetch_iv_percentile.py --date 2026-06-10
python3 scripts/collector/fetch_iv_percentile.py --backfill        # every compiled date (idempotent; one-shot: make fetch-iv-percentile-all)
python3 scripts/collector/fetch_iv_percentile.py --backfill --dry-run
python3 scripts/collector/fetch_iv_percentile.py --date 2026-06-10 --force   # clear columns and re-scrape

# Enrich a compiled flow file with next-day OI change + EOD greeks (scrapes per-contract price-history)
python3 scripts/collector/enrich_oi.py                          # latest enrichable date (newest date skipped until D+1 exists)
python3 scripts/collector/enrich_oi.py --date 2026-06-09
python3 scripts/collector/enrich_oi.py --backfill               # every enrichable date (idempotent; skips already-enriched)
python3 scripts/collector/enrich_oi.py --backfill --dry-run     # report, no scrape/upload
python3 scripts/collector/enrich_oi.py --date 2026-06-09 --force        # clear columns and re-scrape from scratch

# Backfill missing matched-pair legs' settlement IV for the IV spread/skew (→ per-date Drive sidecar)
python3 scripts/collector/fetch_counterpart_iv.py                       # latest compiled date
python3 scripts/collector/fetch_counterpart_iv.py --date 2026-06-26
python3 scripts/collector/fetch_counterpart_iv.py --backfill            # every compiled date (idempotent)
python3 scripts/collector/fetch_counterpart_iv.py --backfill --dry-run  # report scope, no scrape/upload
python3 scripts/collector/fetch_counterpart_iv.py --date 2026-06-26 --force      # clear sidecar and re-fetch

# Enrich a compiled flow file with price/earnings-catalyst data (grounds score_price/score_catalyst)
python3 scripts/collector/fetch_price_catalyst.py                       # latest compiled date (make price-catalyst)
python3 scripts/collector/fetch_price_catalyst.py --date 2026-06-10
python3 scripts/collector/fetch_price_catalyst.py --backfill            # every compiled date (idempotent)
python3 scripts/collector/fetch_price_catalyst.py --backfill --dry-run
python3 scripts/collector/fetch_price_catalyst.py --date 2026-06-10 --force   # clear columns and re-scrape

# Full analysis pipeline: fetch → headless engine (claude/codex) → write Sheets
python3 -m scripts.analysis_pipeline                      # latest date, claude → AnalysisClaude
python3 -m scripts.analysis_pipeline --engine codex       # latest date, codex → AnalysisGPT
python3 -m scripts.analysis_pipeline --date 2026-04-21
python3 -m scripts.analysis_pipeline --date 2026-04-21 --tickers NVDA,AMD,SPY  # ticker-focused → AnalysisTickerSpecific tab
python3 -m scripts.analysis_pipeline --start 2026-04-14 --end 2026-04-18 --days 5
python3 -m scripts.analysis_pipeline --date 2026-04-21 --dry-run   # fetch+analyze, no write
python3 -m scripts.analysis_pipeline --engine codex --model gpt-5  # override engine model
python3 -m scripts.analysis_pipeline --fetch-only                  # fetch + audit CSV only, no LLM
python3 -m scripts.analysis_pipeline --fetch-only --date 2026-06-09

# Scrape historical data to Google Drive
python3 scripts/collector/scrape_flow.py --date 2026-04-21
python3 scripts/collector/scrape_flow.py --start 2026-01-02 --end 2026-05-30 --skip-existing

# Proxy-backtest untested plays (AnalysisClaude minus BacktestResults → BacktestProxy tab)
python3 -m scripts.backtest.proxy --config config/backtest.yml               # all dates, idempotent
python3 -m scripts.backtest.proxy --config config/backtest.yml --date 2026-04-21
python3 -m scripts.backtest.proxy --config config/backtest.yml --dry-run     # no sheet/CSV write
python3 -m scripts.backtest.proxy --config config/backtest.yml --cache-only  # no Barchart scraping
python3 -m scripts.backtest.proxy --config config/backtest.yml --date 2026-04-21 --redo  # re-evaluate frozen rows in window
```

## `/options analyze` — full data-contract detail

`analyze` shells out to `python3 -m scripts.analysis_pipeline` (does NOT analyze in-context).
Runs fetch → headless engine call → write; the LLM step is an isolated session so the
framework/method/raw data never enter the calling agent's context. The pipeline is
model-agnostic via `--engine`: `claude` (default) uses `claude -p` + `claude.md` →
AnalysisClaude; `codex` uses `codex exec` + `codex.md` → AnalysisGPT. All operator-tunable
settings (engines, retries, timeout, fetch defaults, sheet schema, output contract) live in
`scripts/analysis_pipeline/config.py`; the model is overridable via `--model` (default:
claude→`claude-opus-4-8`, codex→its configured model). The prepared rollup carries a
direction-agnostic conviction `Score` (0–14 raw) per ticker, ranked on **extrinsic premium**
(intrinsic stripped so deep-ITM financing flow can't buy rank) with an `otm` component crediting
OTM-probability-weighted extrinsic flow and an `OIConfirm` component (±) crediting/demoting
next-day OI open-confirmation (ref-03; neutral-on-missing, but in practice live runs happen on
D+1 after enrich_oi has landed, so live rows DO carry it — measured 91% populated), plus
pollution/exposure columns (`Ext$`/`Fin%`/`ΔNot$`/`Hzn`/`OTM$`),
direction-bearing vol columns (`IVspr`/`IVskew`, not scored), a per-ticker `IVpct` column
(Barchart's options-overview IV percentile — share of the prior-1yr days with IV below today's,
0–100 — scraped by `fetch_iv_percentile.py` and enriched as `iv_pct` onto the compiled flow
file; the rich/cheap read that picks TF debit vs TF-S credit in framework Step 4; not scored,
not directional), and a market-level **Hedge pressure** score (0–100) — see
`config/conviction-score.md`. Each play also declares `flow_intent`
(DIRECTIONAL/VOLATILITY/HEDGE/SYNTHETIC STOCK — a classification of what the flow IS, **not** a
confidence cap — folded into the play cell's bracket line, upper-cased, e.g. `[DIRECTIONAL]`)
and emits `horizon` (one of 14|60|180|720 — the DTE bucket boundary of the dominant expiry in
the cited evidence) as its own column beside `play`. Confidence is no longer a single label:
each play emits a `score` object of THREE model-scored Step-5 rubric components
(`{flow, dealer, vol}` integer points, intent-weighted: Price-heavy for DIRECTIONAL, Vol-heavy
for VOLATILITY) plus required `key_level` + `direction` fields; the other two components,
`price` and `catalyst`, are pipeline-computed from fetched price-history and earnings-date
data grounded by `key_level`/`direction` (`lib/price_catalyst.py`, enriched onto the compiled
flow file by `scripts/collector/fetch_price_catalyst.py`). All five land on the row as
`score_flow`/`score_dealer`/`score_price`/`score_vol`/`score_catalyst` alongside the summed
`score_total` (0–100; ≥70 strong, 40–69 moderate, <40 weak — bands read, never emitted). The analysis also emits a
market-level `themes` array (`{theme, tickers, breadth, read}`) grouping the day's flow into
narrative clusters — presentation-only, never a multiplier on any play's score. `--days N`
(default 5) appends a multi-day persistence section tracking recurring names.
