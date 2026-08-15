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
                              points), `as_of_iv_cells_with_status` (the same pick plus WHY:
                              ok | stale_fallback | out_of_window | empty_series | fetch_error,
                              written to the `iv_pct_status` column — `out_of_window` means the
                              feed answered but its ~2yr window, measured from the RUN date,
                              starts after the trade date, so that date's IVpct is gone for good;
                              `as_of_iv_cells` is now a thin wrapper dropping the status),
                              `iv_pct_from_flow_rows` (read `{SYMBOL: iv_pct}` back off
                              the enriched rows — how the analysis consumes it) and its sibling
                              `iv_coverage_from_flow_rows` (`{SYMBOL: iv_pct_status}`). The per-name
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
  backfill_mech_cell.py     — fill `mech_cell` (lib/mech_regime.py) on every analysis tab for rows
                              that predate the column (blank) or were written while the SPY/VIX
                              table was missing/stale (NO_DATA). The label is a pure function of
                              the signal date + the frozen table, so it is backfillable and
                              re-runnable; only that one column is written
                              (sheets_client.add_or_update_column), so user formulas and every
                              other column are untouched. A stored label that no longer reproduces
                              is KEPT and logged as DRIFT (exit 2) — never silently replaced —
                              unless --force. Requires a fresh table: `make mech-regime` first
                              (the make target does this). Daily after compile via
                              .github/workflows/backfill-mech-cell.yml (chained on Compile Flow,
                              which refreshes the table at 22:30 UTC)
  studies/                  — TRACKED offline tuning studies (the `backtests/` tree is
                              gitignored in full, so studies that lived there existed on one
                              laptop only — 07-22 addendum 10). Read-only w.r.t. config: a study
                              may never write production settings. `harness.py` = Trade/replay
                              port (exit simulation; changing it invalidates every prior tuning
                              conclusion), `book.py` = pooled real+tweak book loader with the
                              dedup + exact-replay calibration gate (`--validate` prints the
                              diagnostics; bs_options_hist excluded by default),
                              `protocol.py` = purged walk-forward + date-clustered bootstrap +
                              top-k/day replay + the mandatory window cuts,
                              `ml_combination.py` / `bear_arm.py` = the 08-11 studies.
                              Extra deps: `pip install -r requirements-study.txt`.
                              Outputs go to backtests/…/output/ (untracked)
  align_tab_headers.py      — realign an analysis tab's header row with config.ROW_COLUMNS.
                              append_rows writes POSITIONALLY, so a header that stopped short of
                              the schema mislabels every column after the gap and misplaces any
                              column-keyed write. Repairs only when the drifted columns are empty
                              or are schema columns in the wrong position (those are relocated);
                              anything else aborts that tab untouched. --dry-run first
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
                              `iv_pct_enriched_on` (run date — provenance + resume marker),
                              `iv_pct_status` (why those cells look the way they do — the run
                              prints a DEPTH EXHAUSTED banner when `out_of_window` covers more
                              than `DEPTH_EXHAUSTED_SHARE` of a date's pending tickers, i.e. the
                              date has fallen off the far end of the rolling window). Same
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
                              (isolated session; `--engine claude` — currently the only
                              registered engine, `--model` overridable)
                              → expand to per-ticker rows → append to the engine's tab
                              (AnalysisClaude; the codex engine and its AnalysisGPT tab were
                              retired 2026-08-13 — AnalysisGPT keeps its historical rows but
                              nothing writes to it anymore). Source of truth for /options
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
                              history (per-day sigma; NO yfinance) — OFF by default since
                              2026-08-11, `proxy.bs_fallback`, (3) direction-only
                              underlying-trend verdict, (4) unevaluable — same
                              `simulation:`/`credit:` exit rules as the real backtest →
                              BacktestProxy tab + backtests/proxy_results.csv, idempotent;
                              cache-first discovery, scrapes missing neighbors unless
                              --cache-only (see config/backtest-reference.md §BacktestProxy)
  auth_drive.py             — one-time OAuth2 flow for Drive
```

## Daily trade journal — data contracts

PRODUCTION tier. Closes the analysis → trade → evidence loop daily.
`scripts/live_loop/` audits the same ground fortnightly and in more depth; both
import `scripts/live_loop/mapping.py`, so `ladder_tier()` (the sole encoding of
`config/deployment-rules.md` §1–§3) has exactly one implementation.

**Pipeline and boundaries**

```
lib/ibkr/flex.py  ──►  pull.py  ──►  journal/raw/ibkr-<date>-<HHMM>.json  ──►  everything else
                        (only networked module)     (immutable, schema v1)
```

`rawpull.py` defines that file and is dependency-free. It is the boundary that
keeps `lib.ibkr` out of `reconcile`/`risk`/`report`/`writer`: swapping broker
transport is a change to `pull.py` alone. Pulls are written once and never
overwritten — `rawpull.save()` raises on an existing path, because a pull is
the primary evidence for every journal row.

**One transport.** `pull.py` holds `pull_flex()` — a Flex statement, fetched
by default with `IBKR_FLEX_TOKEN` or read off disk with `--offline`. The
Client Portal Gateway transport (`pull()`, `--cpapi`, `lib/ibkr/client.py` +
`endpoints.py` + `contracts.py`) was deleted on 2026-08-15: what it bought —
native greeks and a native NetLiquidation — Barchart and `--net-liq` now
supply, and a locally-run, browser-logged-in gateway was the one daily
friction this pipeline otherwise has none of. Every gap Flex itself does not
close is filled from elsewhere, never silently:

| Gap | Filled from |
|---|---|
| Greeks | Barchart EOD Delta/Gamma/Theta/Vega/IV, per contract (`greeks.py`) |
| Open positions | the declared `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID` query, else reconstructed by netting fills (`flexparse.py`) |
| NetLiquidation | a NAV section on the positions query if it carries one, else `--net-liq` / `JOURNAL_NET_LIQUIDATION`, else the caps report "not evaluable" |
| Commission | nothing — recorded as `None`, never `0.0`; `net_cash` excludes it |

Pulls the old Client Portal transport wrote (`source: ibkr-cpapi`, greek
`source: ibkr`) are unaffected — they still replay through `--from-raw`
unchanged, since nothing about the v1 schema moved. `DELTA_SOURCE_IBKR` and
`DELTA_SOURCES_REAL` stay in `config.py` for exactly that reason; see below.

The IBKR MCP is **not** an alternative: it is claude.ai-hosted, its tools are
absent from a Claude Code CLI session's registry, and no script can call it.

**Raw-pull schema (v1)** — `trades[]` (exec_id, conid, side, size, price,
commission, realized_pnl, trade_time, order_id, open_close), `positions[]`
(conid, signed position, avg_cost), `contracts{conid}` (symbol, strike, expiry,
right, multiplier), `greeks{conid}` (delta/gamma/theta/vega/iv + `source`),
`underlying_prices{symbol}`, `net_liquidation`. `validate()` refuses a pull whose
fill conid has no contract detail (identity would be a guess) or whose greek
claims a `source` in `DELTA_SOURCES_REAL` with a null delta. `DELTA_SOURCES_REAL`
is a frozenset (`ibkr`, `barchart`), not one named source — membership, not
equality, is what everything downstream tests, so a third feed can never be
added by mistyping `== DELTA_SOURCE_IBKR` and silently dropping positions out
of the net delta total. `schema_version` stays 1 whether the pull came from
Flex or from a Client Portal transport kept only for `--from-raw` replay; the
Flex pull's extra keys (below) are additive and optional.

A `PositionRisk.delta_source` is **derived from the legs** (`risk.delta_source`),
never assumed from the transport: a Flex pull marks every position from
Barchart EOD; the `ibkr` label only ever appears when replaying a pull the
retired Client Portal transport wrote. That label is written to the permanent
`TradeJournal` row, where it is the only thing telling a later reader how far to
trust the exposure figure. Legs marked from different feeds are reported joined
(`barchart+ibkr`) rather than collapsed to one name — a half-marked spread is
the case worth noticing, not averaging over.

**Flex path specifics** (`flexparse.py`, `greeks.py`, `lib/ibkr/flex.py`)

- *Contract identity stays exact.* A Flex trades export carries `Conid`, so
  nothing is price-inferred the way the old hand-pasted MCP snapshots had to
  be. `TradeID` becomes `exec_id` — what the journal dedupes on. Flex carries
  no `OrderID`, so fill grouping falls back to exact `trade_time` equality,
  which `reconcile._group_key()` already supported (a combo order fills every
  leg at the same instant).
- *Open-positions section — conditional.* Without a second, separately-saved
  Flex query (`IBKR_FLEX_OPEN_POSITIONS_QUERY_ID` / `--from-flex-positions`),
  `pull_flex()` takes MULTIPLE trades files (default: every
  `portfolio/input/trades_*.csv`) and nets signed quantity per conid across
  all of them — a position opened before the earliest file given is invisible
  to a single-year export. `flexparse._provenance_warnings()` names two
  distinct failure modes rather than let a partial book pass as real: a conid
  whose rows begin with a CLOSE (its entry predates the oldest export, so the
  net is understated) and a contract already expired as of the session
  (netting has no concept of expiry or assignment, so an expired position
  would otherwise net to a permanent phantom non-zero) — the latter is both
  named AND dropped from the reconstructed book. With the positions query
  configured, `flexparse.parse_positions()` reads the OpenPositions section
  DIRECTLY (a declared book, `book_reconstructed=False`) — the netted book is
  still computed but only as a cross-check, diffed against the declared one
  by `_book_diff_warnings()`; a conid where they disagree (present in one
  only, or a different net size) becomes a `book_warnings` entry naming both
  counts. `parse_positions()` also handles the LevelOfDetail correctness trap:
  an OpenPositions query saved at both SUMMARY and LOT granularity would
  double-count a position if every row were summed, so SUMMARY rows win when
  present, LOT rows are summed only when no SUMMARY row exists, and an
  unlabelled duplicate conid (no LevelOfDetail column at all, more than one
  row) raises rather than guessing which row is real.
- *Two guards against a book that reads flat when it is not.* An OpenPositions
  statement with no `<OpenPositions>` section at all — `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID`
  pointing at a query saved without that part — raises naming the variable,
  rather than being read as an empty (flat) book. And a *declared* OpenPositions
  book that comes back EMPTY while netting the trades export still finds one or
  more unexpired positions raises too, refusing to journal the flat one — this
  is the 2026-08-15 failure: the statement came back with zero rows while 18
  contracts were open, and the report printed "No open positions" and "Book is
  complete" with nothing to contradict it. Both exit non-zero (`EXIT_USAGE = 2`)
  rather than let a plausible-looking empty day pass. Every fetched statement
  is also now kept verbatim at
  `journal/raw/flex-<date>-<HHMM>-{trades,positions}.{csv,xml}` (skipped on
  `--dry-run`), so a parse that goes wrong is diagnosable after the fact instead
  of leaving only the derived pull to look at.
- *No greeks.* `greeks.py` fetches per-contract EOD Delta/Gamma/Theta/Vega/IV
  plus underlying spot from Barchart's settlement history (the same feed
  `fetch_counterpart_iv.py` scrapes for a different reason) — one row per open
  conid, choosing the latest row **on or before** the session date; a row
  after it is never selected, the same no-lookahead posture
  `scripts/backtest_study/harness.py` takes on entry pricing.
- *No commission.* Recorded as `None`, never `0.0` — `PositionEvent.commission`
  is all-or-nothing across a group's legs (the same rule `risk.py` applies to
  delta), and `net_cash` excludes an unreported commission rather than
  understating cost.
- *No NetLiquidation.* `--net-liq` or `$JOURNAL_NET_LIQUIDATION`; left unset,
  the exposure caps report "not evaluable" instead of dividing by a guess.
- *Timestamps are not UTC.* Flex writes `DateTime` as `YYYY-MM-DD;HHMMSS` in
  the account's configured timezone with no offset recorded anywhere in the
  file. Rather than stamp a false `Z` on a local time, `flexparse` emits a
  naive ISO-8601 string and sets `trade_time_tz` on the pull instead — nothing
  downstream compares these across zones (grouping keys on equality, the
  journal keys on calendar date).
- *Additive pull keys* the report reads and a replayed Client Portal pull never
  set: `trade_time_tz`, `commissions_included`, `book_reconstructed`,
  `book_warnings`, `flex_sources`, `flex_span`. The gaps above surface in the
  report's §1 "SOURCE LIMITS" block rather than being absorbed silently — four
  without the positions query configured, three with it (the open-positions
  gap drops out, and `book_reconstructed` flips to `False`).
- `lib/ibkr/flex.py::FlexClient` is the token-authenticated Flex Web Service
  transport, fetched by default (`--offline`/`--no-flex-web` turns it off): a
  two-step `SendRequest` → `GetStatement` handshake, polling through IBKR
  error code 1019 ("statement generation in progress") — the only retryable
  code, since a report can take several seconds to assemble on IBKR's side.
  Transport and parsing only, no business logic, the same role the deleted
  `IBKRClient` played for the Client Portal Gateway.
- *Two wire formats.* A Flex query is saved as delimited text **or** XML in
  Account Management, and the web service returns whichever that query
  specifies — a caller cannot assume one. `flexparse._read_rows` detects the
  format from the content (not the filename; a fetched statement has none) and
  `XML_TRADE_ATTRS` renames the camelCase `<Trade>` attributes to the CSV
  column names, so every function below the reader sees exactly one shape.
  Two of the renames are not simple case changes: `cost` → `CostBasis` and
  `assetCategory` → `AssetClass`.
- *Short statement windows.* `pull._web_sources` nets a `--flex-web` statement
  together with the on-disk exports rather than instead of them. This is the
  one gap `_provenance_warnings` structurally cannot catch: those checks
  inspect positions present in the rows, but a contract opened last month and
  untouched since leaves **no row at all** in a "Last Business Day" statement,
  so the netted book is short by a whole position with nothing anomalous to
  point at. `flexparse._window_warning` reads the `<FlexStatement>` window and
  says so — unless another export supplied fills predating that window, in
  which case the netting is fed from those and the warning would be noise.
- *Coverage gaps between sources.* That suppression assumes earlier coverage
  means **contiguous** coverage, and it does not. A hand-exported
  `trades_2026.csv` ending 2026-07-24 plus a `LastBusinessDay` statement for
  2026-08-13 leaves 19 days no source covers at all — and a position CLOSED
  inside that span leaves no closing fill anywhere, so it still nets non-zero
  and is presented as open (this is exactly how AMD/META/MU were reported open
  on 2026-08-15 when all three were closed). `_coverage_gap_warnings` merges a
  per-source coverage interval — the declared `<FlexStatement>` window where
  there is one, otherwise the observed min/max fill date across **all** rows
  read, options and not, since any fill proves the day was covered — and names
  each uncovered span plus the tickers whose last fill precedes it. Weekend-only
  steps are not gaps; no holiday calendar is consulted, so a spurious one-day
  gap is possible and is the safe direction to be wrong in. The remedy is always
  a fresh export dropped into `portfolio/input/`, never a change to the saved
  Flex query — see the IBKR-configuration constraint.

**Records** (`config.py`) — `Leg` (signed qty; `leg_string()` emits the
`TICKER:YYYY-MM-DD:STRIKE:C +N` grammar `scripts/backtest/legs.py` parses, so a
journal row feeds straight back into the backtest), `Greeks`, `PositionEvent`
(one order group = one journal row), `PositionRisk`.

**Reconciliation** — fills group by order_id, falling back to identical
trade_time. Identity is the broker `conid`, so the price-matching inference
`stage1_map_fills.reconstruct()` needs is gone, along with its "identity is only
recoverable while the position is open" caveat. Signal date = the nearest prior
date the analysis book HAS (holidays need no calendar table), bounded BOTH by
`SIGNAL_LOOKBACK_DAYS` (3 book dates) and `MAX_SIGNAL_AGE_DAYS` (10 calendar
days) — the second bound matters because a gap in the book, such as the v4
cut-over, would otherwise reach back years and stamp a fill with a signal date
from another prompt version. Market regime always comes from the date's MARKET
row, never a play row.

**Open book** (`book.py`) — legs group by (underlying, expiry). A vertical
reassembles; a calendar/diagonal is reported as two positions and the report says
so. Grouping by underlying alone would fuse a core long and a hedge overlay into
a fictional structure. Delta-notional is additive across legs, so the split
changes position COUNT only, never net exposure.

**Risk** — `signed_dn = delta x 100 x contracts x underlying`, identical to
`scripts/backtest_study/account_sim.py::signed_dn`, so a live book and a
simulated one compare directly. Caps `per_position` 0.25 / `net` 2.50 are read
from `config/account-sim.yml` (that study calls them "a friction model, NOT a
tuned parameter", which is why they transfer) but bind against the broker's
NetLiquidation, not the study's $25k. A position's delta is all-or-nothing across
legs: a spread priced on one leg would report the naked long's delta, since the
unpriced leg is precisely the hedge.

**Output** — `journal/reports/<date>.md` and `docs/journal-<date>.html`. The page
recomputes each figure from the records and reconciles it against the report,
writing nothing on a mismatch (same discipline as `scripts/study_charts/`).
Rows go to the `TradeJournal` tab in `TRADE_JOURNAL_SPREADSHEET_ID` and to
`journal/trades.csv`, deduped per-row on `source_ref` (broker exec ids) rather
than by batch hash, so a re-run appends only genuinely new fills. The CSV is
written first and its failure is fatal; a Sheets failure is reported but never
loses a row.

**Recommender** — `rank()` applies §1 VETO, §2 tiers, §3 geometry and cap
headroom deterministically; §1.4 routes bear debit to the hedge sleeve only.
`judge()` then makes the pipeline's ONLY model call, sees only survivors, and
applies verdicts as annotations onto that ordering — it never sorts, filters or
rebuilds the list, and a returned ticker outside the survivor set is dropped.

**Privacy** — `/journal/` is gitignored in full. The leading slash is
load-bearing: a bare `journal/` also matches `scripts/journal/` and would exclude
the pipeline's own source from version control.

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

# Full analysis pipeline: fetch → headless engine (claude) → write Sheets
python3 -m scripts.analysis_pipeline                      # latest date, claude → AnalysisClaude
python3 -m scripts.analysis_pipeline --date 2026-04-21
python3 -m scripts.analysis_pipeline --date 2026-04-21 --tickers NVDA,AMD,SPY  # ticker-focused → AnalysisTickerSpecific tab
python3 -m scripts.analysis_pipeline --start 2026-04-14 --end 2026-04-18 --days 5
python3 -m scripts.analysis_pipeline --date 2026-04-21 --dry-run   # fetch+analyze, no write
python3 -m scripts.analysis_pipeline --model claude-opus-5  # override engine model
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
model-agnostic via `--engine`: `claude` (default, currently the only registered engine) uses
`claude -p` + `claude.md` → AnalysisClaude. (The `codex` engine — `codex exec` + `codex.md` →
AnalysisGPT — was retired 2026-08-13; the operator stopped running analysis with it, and
AnalysisGPT keeps its historical rows but nothing writes to it anymore.) All operator-tunable
settings (engines, retries, timeout, fetch defaults, sheet schema, output contract) live in
`scripts/analysis_pipeline/config.py`; the model is overridable via `--model` (default:
claude→`claude-opus-5`). The prepared rollup carries a
direction-agnostic conviction `Score` (0–12 raw) per ticker, ranked on **extrinsic premium**
(intrinsic stripped so deep-ITM financing flow can't buy rank) with an `otm` component crediting
OTM-probability-weighted extrinsic flow, plus
pollution/exposure columns (`Ext$`/`Fin%`/`ΔNot$`/`Hzn`/`OTM$`),
direction-bearing vol columns (`IVspr`/`IVskew`, not scored), a per-ticker `IVpct` column
(Barchart's options-overview IV percentile — share of the prior-1yr days with IV below today's,
0–100 — scraped by `fetch_iv_percentile.py` and enriched as `iv_pct` onto the compiled flow
file; the rich/cheap read that picks TF debit vs TF-S credit in framework Step 4; not scored,
not directional) with its `iv_pct_status` provenance marker riding beside it through the rollup
CSV (`IVPctStatus`) onto the analysis row, and a market-level **Hedge pressure** score (0–100) — see
`config/conviction-score.md`. Each play also declares `flow_intent`
(DIRECTIONAL/VOLATILITY/HEDGE/SYNTHETIC STOCK — a classification of what the flow IS, **not** a
confidence cap — folded into the play cell's bracket line, upper-cased, e.g. `[DIRECTIONAL]`)
and emits `horizon` (one of 14|60|180|720 — the DTE bucket boundary of the dominant expiry in
the cited evidence) as its own column beside `play`. Confidence is no longer a single label:
each play emits a `score` object carrying the ONE model-scored Step-5 rubric component
(`{vol}` integer points, intent-weighted: max 15 for DIRECTIONAL/HEDGE/SYNTHETIC STOCK, 25 for
VOLATILITY) plus required `key_level` + `direction` fields; the other two components,
`price` and `catalyst`, are pipeline-computed from fetched price-history and earnings-date
data grounded by `key_level`/`direction` (`lib/price_catalyst.py`, enriched onto the compiled
flow file by `scripts/collector/fetch_price_catalyst.py`). All three land on the row as
`score_price`/`score_vol`/`score_catalyst` alongside the summed
`score_total` (0–50, or 0–55 for VOLATILITY intent; ≥35 strong, 20–34 moderate, <20 weak —
bands read, never emitted).
**v4 trim (2026-08-11):** `score_flow` and `score_dealer` were dropped from the prompt AND from
`ROW_COLUMNS` — the ML combination study found the score block adds nothing reproducible to
decisions, and `score_dealer` was judged off a vol-snapshot proxy rather than real per-name
dealer gamma (`score_vol` is explicitly exempt). The cut-over is the repo's standard \*\*`vN*`
rename**: the live tabs were renamed in place (`v3_AnalysisClaude`, `v3_BacktestResults`,
`v3_BacktestProxy`) and the pipeline recreates empty ones, so every v4 tab header is written
fresh from `ROW_COLUMNS`— no positional migration, no blank placeholder columns, and no change
to`GOOGLE_SPREADSHEET_ID`or to any tab name in code.`BaselineDaily`is deliberately NOT
versioned, so the regime history carries across the bump. To run against the frozen v3 book,
pass`--tab v3_AnalysisClaude`.
The two names are **kept in `RESULT_COLUMNS`** (`scripts/backtest/core.py`)
so the study loaders that name them keep working on pooled v3+v4 exports — blank on v4 rows.
v4's 0–50 `score_total`is **not comparable to v3's 0–100**; the incomparability is deliberate,
and`score_total`is in any case decision-irrelevant (a deterministic tie-break only).
The analysis also emits a
market-level`themes` array (`{theme, tickers, breadth, read}`) grouping the day's flow into
narrative clusters — presentation-only, never a multiplier on any play's score. `--days N`
(default 5) appends a multi-day persistence section tracking recurring names.
