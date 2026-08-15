# Architecture reference

Detailed per-file responsibilities, data contracts, and resume/idempotency semantics.
`CLAUDE.md` keeps only the compact map — **read the relevant section here before editing
`lib/` or `scripts/` code**, and keep this file in sync when responsibilities move.

Sections: File layout · Research tier (studies) · Daily trade journal · Command variants ·
`/options analyze` data contract.

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
                              replaced, unless --force. Needs a fresh table (`make mech-regime`;
                              the make target does this). Daily after compile via Actions
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
  journal/ · live_loop/     — PRODUCTION tier; see §Daily trade journal below
  backtest_study/ · study_review/ · study_map/ · study_charts/
                            — RESEARCH tier; see §Research tier below
  auth_drive.py             — one-time OAuth2 flow for Drive
```

## Research tier — backtest tuning studies

Never imported by production, never scheduled. Reports land in `backtests/study_output/`
(scratch, gitignored); conclusions in `research/current.md`; metric definitions
in `research/glossary.md`; the replication protocol in
`research/replication-protocol.md`.

**`scripts/backtest_study/`** — run via `python3 -m scripts.backtest_study {list,run}`.

- `run.py` — runner; every report carries a provenance header (git sha + input row counts).
  Flags: `--date`, `--dry-run`, `--cache-only` (no scraping), `--redo` (re-evaluate frozen
  rows), `--all`.
- `harness.py` — FROZEN exit-replay engine. Do not edit: every recorded conclusion rests on
  it; changing it invalidates all prior tuning conclusions.
- `book.py` — pooled real+proxy book loader with dedup + the exact-replay calibration gate
  (bs-tier rows excluded by default).
- `underlying.py` — daily stock bars (real OHLC → `Price~` close-only fallback; the all-legs
  widening harness.py must not get). `underlying_features.py` — as-of-entry price-STATE
  columns (rv20/rv_parkinson/semivar_dn/atr14_pct/eff_ratio/vrp/beta; the OHLC-only two carry
  a smaller denominator — always print `coverage()`).
- `protocol.py` — purged walk-forward, date-clustered CIs, LOO.
- `live_select.py` — the ONE sanctioned research→production import (see account_sim below).

### account_sim

Config-driven and stateless: `config/account-sim.yml` is the whole parameter surface —
capital, risk %, positions/day, the two delta-notional caps, the cap/capital grids, hedge
fraction, dense-episode definition, A2/A3/A5 thresholds, G1's expected book line, and the
compounding arm's `mark_interval`/`budget_ceiling`. Copy it and pass `--config` to simulate a
different account; there are no per-parameter CLI flags.

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
  compounds too, so the ratio stops isolating the caps) — the report says so inline. G1–G4
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
  the SHIPPED decision function — `scripts/journal/recommend.py`'s `rank()` then `judge()` —
  instead of book.py's port of the ladder, so the simulated decision is the live decision and
  the drift between them is a measured number. Ledger, caps, sizing, and the frozen exit
  replay are unchanged (`live_select.py`; a `ranker` hook on `simulate()` that is None on
  every other path). Own report (`account_sim-live-select-latest.txt`) and CSV; treated as a
  SINGLE-arm run (never files under account_sim's stem, never drags the compounding arm
  along). G1–G4 stay pinned to the frozen basis; G5 is RE-RUN with the shipped selector in
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

**`scripts/study_map/`** — renders `site/study-map.html`: what each study asks (`catalog.py`,
hand-written — a study with no entry FAILS the test suite) + what its last run printed
(`summary.py`, quoted verbatim from the reports, never paraphrased; an excerpt with no
VERDICT block is labelled as the report's tail) + the newest current.md sections
(`tuning.py`). Rebuilt automatically after every study run and review; `make study-map` /
`make study-map-open` to force. `python3 -m scripts.study_map --check` prints per-study
last-run status.

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

PRODUCTION tier. Closes the analysis → trade → evidence loop daily. `scripts/live_loop/`
audits the same ground fortnightly and in more depth; both import
`scripts/live_loop/mapping.py`, so `ladder_tier()` (the sole encoding of
`docs/deployment-rules.md` §1–§3) has exactly one implementation.

**Pipeline and boundaries**

```
lib/ibkr/flex.py  ──►  pull.py  ──►  journal/raw/ibkr-<date>-<HHMM>.json  ──►  everything else
                       (only networked module)     (immutable, schema v1)
```

`rawpull.py` defines that file and is dependency-free — the boundary that keeps `lib.ibkr`
out of `reconcile`/`risk`/`report`/`writer`; swapping broker transport is a change to
`pull.py` alone. Pulls are written once and never overwritten (`rawpull.save()` raises on an
existing path) — a pull is the primary evidence for every journal row.

**One transport.** `pull.py` holds `pull_flex()` — a Flex statement, fetched by default with
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
| Greeks | Barchart EOD Delta/Gamma/Theta/Vega/IV per contract (`greeks.py`), latest row **on or before** the session date — never after (lookahead) |
| Open positions | the declared `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID` query, else reconstructed by netting fills (`flexparse.py`) |
| NetLiquidation | a NAV/Account-Information section on the positions query if it carries one (detected, never assumed), else `--net-liq` / `JOURNAL_NET_LIQUIDATION`, else the caps report "not evaluable" |
| Commission | nothing — recorded as `None`, never `0.0`; `net_cash` excludes it. `PositionEvent.commission` is all-or-nothing across a group's legs (same rule risk.py applies to delta) |

**Two saved queries, one token — or one query carrying both sections.** A Flex query is
scoped to the sections it was saved with, so trades and open positions are normally separate
queries (`IBKR_FLEX_QUERY_TRADES_ID` + optional `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID`). Point
BOTH vars at ONE query saved with BOTH sections and the pull costs ONE handshake: `pull.py`
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

**Flex path specifics** (`flexparse.py`, `greeks.py`, `lib/ibkr/flex.py`)

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
`analysis.py` is the shared AnalysisClaude loader (Sheets → CSV fallback).

**Open book** (`book.py`) — legs group by (underlying, expiry). A vertical reassembles; a
calendar/diagonal is reported as two positions and the report says so. Grouping by
underlying alone would fuse a core long and a hedge overlay into a fictional structure.
Delta-notional is additive across legs, so the split changes position COUNT only, never net
exposure.

**Risk** — `signed_dn = delta × 100 × contracts × underlying`, identical to
`scripts/backtest_study/account_sim.py::signed_dn`, so a live book and a simulated one
compare directly. Caps `per_position` 0.25 / `net` 2.50 are read from
`config/account-sim.yml` (that study calls them "a friction model, NOT a tuned parameter" —
why they transfer) but bind against the broker's NetLiquidation, not the study's $25k. The
per-position cap is evaluated on a TICKER's SIGNED total, not per (ticker, expiry) row —
book.py splits a core vertical and the shorter-dated short leg financing it into two
positions, and that leg exists to cut the ticker's directional exposure. A position's delta
is all-or-nothing across legs: a spread priced on one leg would report the naked long's
delta, since the unpriced leg is precisely the hedge.

**Output** — `journal/reports/<date>.md` and `docs/journal-<date>.html`. The page recomputes
each figure from the records and reconciles against the report, writing nothing on a
mismatch (`risk.py::assess` and `page.py::_breach_count` are two DELIBERATE implementations
of the cap rule — change both by hand, never share a helper). The charts are Cap utilisation
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
never the unbounded `latest_date()` (which stays correct for `reconcile.py`'s
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
treated as clean — the same concern `scripts/backtest_study/live_select.py` documents for its
own judge layer.

**Recommendation record** (`recwriter.py`) — every evaluated candidate (role
`deploy`/`hedge`/`veto`/`tier_c`) is flattened to `RECOMMENDATION_COLUMNS` and written to the
Recommendations tab in `TRADE_JOURNAL_SPREADSHEET_ID` (the same workbook as TradeJournal) and
to `journal/recommendations.csv`, mirroring `writer.py`'s CSV-first/CSV-fatal,
Sheets-non-fatal split. The two are DELIBERATELY not shared code: `writer.py`'s failure loses
the day's trades, so generalising its helpers over (key, tab, columns) to also serve a
non-trade record would risk that module for a feature that isn't one — `recwriter.py` mirrors
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
python3 scripts/gc_flow.py --all                     # sweep every compiled date
python3 scripts/gc_flow.py --all --dry-run           # report what would be trashed

# Append daily market-baseline rows to the BaselineDaily tab
python3 scripts/build_baseline.py                     # latest Drive date
python3 scripts/build_baseline.py --backfill          # every missing date (idempotent)
python3 scripts/build_baseline.py --backfill --dry-run

# Enrichments — all share: bare = latest date · --date · --backfill (idempotent) ·
# --dry-run · --force (clear columns/sidecar and re-scrape)
python3 scripts/collector/fetch_iv_percentile.py      # one-shot backfill: make fetch-iv-percentile-all
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
python3 -m scripts.study_map --check
make study-map-open · make study-docs · make study-chart-regime-open · make study-chart-compounding-open
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
```

## `/options analyze` — full data-contract detail

`analyze` shells out to `python3 -m scripts.analysis_pipeline` (does NOT analyze
in-context). The LLM step is an isolated session so the framework/method/raw data never
enter the calling agent's context. Model-agnostic via `--engine`: `claude` (default, the
only registered engine; the `codex` engine → AnalysisGPT was retired 2026-08-13) uses
`claude -p` + `claude.md` → AnalysisClaude. All operator-tunable settings live in
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
