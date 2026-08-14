# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Subagent model selection

**Delegation default: DELEGATE.** Spawn subagents freely for anything that
reads broadly — investigations, code reviews, multi-file analysis, study runs,
large doc/skill loads. The point is to keep bulk tokens out of the main session.
This section governs only WHICH model a subagent gets, not whether to spawn one;
do not read it as a restriction on calling Agent.

The single exception: a lookup answerable by ONE `codegraph_explore` call — do
that inline. Anything needing repeated lookups is an investigation: delegate it,
and have the subagent call `codegraph_explore` itself (`code-reviewer` and
`test-engineer` hold the MCP tool; every other agent can shell out to
`codegraph explore "<query>"`).

NOTE: the CodeGraph MCP server injects a broader claim that delegating a lookup
to a subagent "costs more for the same answer." That is scoped to SINGLE lookups
and does NOT override this section. Delegation overhead is a fixed cost of a few
thousand tokens; it loses against one 5k `codegraph_explore` call and wins
decisively against five of them.

When spawning subagents via the Agent tool, ALWAYS pass an explicit `model`
parameter — never omit it. An omitted model makes the subagent inherit the main
session's model (the most expensive one). This applies especially in plan mode:
Explore agents MUST be spawned with `model: haiku`, and Plan agents with
`model: sonnet` by default.

Rationale: a Plan subagent mostly reads files and drafts an ordered step list;
the hard judgment on the returned plan happens in the main session (already the
most capable model), so Opus inside the subagent is usually redundant spend.

Use `model: opus` for a Plan agent only when the planning itself is the hard
part — the design space is genuinely open and a shallow plan can't be cheaply
caught after the fact. In this repo that means tasks touching:

- backtest pricing/exit modeling (`scripts/backtest.py`, leg pricing, clamps)
- the analysis-pipeline refactor (`scripts/analysis_pipeline/core.py` monolith)
- cross-cutting schema changes (compiled-flow columns, Sheets tab headers,
  rollup/audit CSV contract — anything with multiple touch points to keep in sync)

- `haiku` — lookups, searches, file reads, grep (e.g. Explore agents)
- `sonnet` — moderate tasks: code edits, summaries, single-file analysis, plan-mode planning
- `opus` — heavy analytical work: multi-file reasoning, architecture review, options flow
  analysis, open-ended design planning (cases above)

## Commands

```bash
# Activate Python environment (required before any script)
source .venv/bin/activate

# Run all tests
pytest

# Run a single test file
pytest tests/test_drive_client.py

# Scrape live data (run during/after market hours)
SCRAPE_HEADLESS=false python3 scripts/collector/scrape_flow.py --mode flow
SCRAPE_HEADLESS=false python3 scripts/collector/scrape_flow.py --mode unusual

# Scrape historical data to Google Drive
python3 scripts/collector/scrape_flow.py --date 2026-04-21
python3 scripts/collector/scrape_flow.py --start 2026-01-02 --end 2026-05-30 --skip-existing

# Daily data steps (each defaults to the latest date; full flag matrix in ARCHITECTURE.md)
python3 scripts/compile_flow.py                       # dedupe hourly snapshots → compiled CSV (→ Drive)
python3 scripts/gc_flow.py                            # trash raws verified-present in compiled file
python3 scripts/build_baseline.py                     # market-baseline row → BaselineDaily tab
python3 scripts/collector/enrich_oi.py                # next-day OI change + EOD greeks (needs D+1)
python3 scripts/collector/fetch_iv_percentile.py      # per-ticker Barchart IV percentile (IVpct)
python3 scripts/collector/fetch_counterpart_iv.py     # matched-pair leg settlement IV → sidecar
python3 scripts/collector/fetch_price_catalyst.py     # price/earnings-catalyst columns
python3 scripts/backfill_mech_cell.py                 # fill mech_cell on older analysis rows
python3 scripts/align_tab_headers.py --dry-run        # check tab headers against ROW_COLUMNS
# Common flags: --date YYYY-MM-DD · --backfill (all dates, idempotent) · --dry-run ·
# --force (clear + re-scrape). compile_flow takes --start/--end; gc_flow uses --all.

# Full analysis pipeline: fetch → headless engine (claude) → write Sheets
python3 -m scripts.analysis_pipeline                      # latest date, claude → AnalysisClaude
python3 -m scripts.analysis_pipeline --date 2026-04-21 --tickers NVDA,AMD,SPY  # → AnalysisTickerSpecific tab
python3 -m scripts.analysis_pipeline --fetch-only         # fetch + audit CSV only, no LLM
# Also: --start/--end, --days N, --dry-run, --model <id> (full matrix in ARCHITECTURE.md)

# Backtest
python3 -m scripts.backtest --config config/backtest.yml
python3 -m scripts.backtest --config config/backtest.yml --dry-run

# Proxy-backtest untested plays (AnalysisClaude minus BacktestResults → BacktestProxy tab)
python3 -m scripts.backtest.proxy --config config/backtest.yml   # all dates, idempotent

# Underlying stock OHLC cache (research tier — feeds studies that need real bars)
python3 scripts/collector/fetch_underlying_ohlc.py     # every book ticker, one request each
python3 scripts/collector/fetch_underlying_ohlc.py --date 2026-04-07 --dry-run
# Date flags select TICKERS and drive the coverage gate; they do not window the feed.
# Flags split-adjusted tickers into backtests/underlying_ohlc_cache/rescaled_tickers.txt
# (a basis warning — their % moves stay valid, only $ moves are withheld).

# Counterpart option history (research tier — makes VOL structures priceable)
python3 scripts/collector/fetch_counterpart_history.py --dry-run
python3 scripts/collector/fetch_counterpart_history.py --limit 200   # resumable
# Fetches the opposite-type, same-strike mirror of every book entry leg into the
# SAME backtests/option_history_cache/ under the SAME filename convention, so the
# existing pricing path reads them with no code change. ~1,250 contracts; takes
# straddle-ability from 15/481 (ticker,expiry) groups to 481/481.

# Backtest tuning studies (research tier — reports, not production)
python3 -m scripts.backtest_study list                 # available studies
python3 -m scripts.backtest_study run bear_deploy      # → backtests/study_output/<name>-latest.txt
python3 -m scripts.backtest_study run --all
# Reports carry a provenance header (git sha + input row counts); write-ups go to
# config/backtest-tuning/current.md. See config/backtest-tuning/README.md.
# Also: --date, --dry-run, --cache-only (no scraping), --redo (re-evaluate frozen rows)
# account_sim is CONFIG-DRIVEN and holds no state: config/account-sim.yml is the
# simulation (capital, risk %, positions/day, the two delta-notional caps, the
# grids, the population and criteria thresholds, and G1's expected book line).
# Edit that file, or copy it and pass --config, to simulate a different account;
# there is no --capital/--risk-dollars/--per-pos-cap/--net-cap flag any more.
python3 -m scripts.backtest_study run account_sim -- --config config/my-account.yml
# ONE `run account_sim` produces BOTH BASES, as two arms of the same run:
#   account_sim-latest.txt              the FROZEN, pre-registered, path-INDEPENDENT
#                                       book — the basis every recorded conclusion
#                                       rests on. Unchanged; still the default report.
#   account_sim-compounding-latest.txt  the COMPOUNDING sensitivity (--compounding),
#                                       which re-marks SIZING to realized equity at
#                                       fixed calendar intervals (month/quarter/year):
#                                       both delta caps scale with marked equity, the
#                                       per-position risk budget scales but is
#                                       ceilinged by `budget_ceiling`.
# The arm is a FLAG, not a config file (config/account-sim-compounding.yml is gone).
# config/account-sim.yml's `compounding:` block now parameterises the arm only
# (mark_interval, budget_ceiling); whether it runs is the flag's job.
# Each arm writes its OWN report, positions CSV and page — the compounding arm can
# no longer overwrite the frozen book's artifacts.
# marked_equity counts only positions CLOSED BEFORE the mark session — open positions
# are never marked to market — and is a sizing number only, so G3 still balances
# against the STARTING capital. Post-hoc: A1-A6 were pre-registered against a
# path-independent sim, and A2/A5 DO NOT TRANSFER (their B2 benchmark compounds too,
# so the ratio stops isolating the caps); the report says so inline. G1-G4 stay
# pinned to the frozen basis; G5 runs sighted-vs-blind on BOTH bases and must match
# on each.
python3 -m scripts.backtest_study run account_sim -- --compounding   # that arm alone
# It also exports its deployed/skipped positions (incl. the market/ticker/
# mechanical regime block) to backtests/study_output/account_sim-positions-latest.csv
# (the compounding arm: account_sim-positions-compounding-latest.csv).
# Its G5 gate ENFORCES that selection/sizing never read an outcome field —
# keep it passing; it is what makes the sim safe to drive a live-position agent.
python3 -m scripts.backtest_study run account_sim -- --structure-universe
# ^ arm: admits proxy debit rows the exact-replay gate withheld (stale
#   trailing_stop exports, not unpriceable rows). Widens the CANDIDATE SET only;
#   bs rows stay dropped, gates still run on the frozen book, and it writes a
#   SEPARATE artifact (account_sim-positions-structure-latest.csv).
# Every ARM gets its own CSV stem; a different --config does NOT — it overwrites the
# default export, and the report records which config produced it.

# Study review pipeline (research tier — two-analyst replication grading + digest)
python3 -m scripts.study_review account_sim              # run study, then A/B + validator + digest
python3 -m scripts.study_review account_sim --skip-run   # reuse <name>-latest.txt
python3 -m scripts.study_review account_sim --skip-run --dry-run  # exercise pipeline, no LLM calls
# Outputs: backtests/study_output/<name>-review-{analyst-a,analyst-b,validator}-latest.md + <name>-digest-latest.md
# Metric definitions for study reports: config/backtest-tuning/glossary.md

# Study map (research tier — the readable one-pager over the whole study package)
make study-map-open                                    # rebuild docs/study-map.html + open it
python3 -m scripts.study_map --check                   # per-study last-run status as a table
# Auto-rebuilt after every `backtest_study run` and every `study_review`, so it
# always quotes the newest reports. Per-study VERDICTS are hand-written in
# scripts/study_map/catalog.py (a study with no entry there FAILS the test suite);
# the last-run blocks are quoted verbatim from backtests/study_output/ and never
# paraphrased — an excerpt with no VERDICT block is labelled as the report's tail.

# Study charts (research tier — renders a study result, never computes a new one)
python3 -m scripts.study_charts.account_sim              # → account_sim-charts-latest.html
python3 -m scripts.study_charts.account_sim --standalone --open   # view off disk
python3 -m scripts.study_charts.account_sim --positions backtests/study_output/account_sim-positions-structure-latest.csv
make study-docs                                          # rebuild every docs/ page
# docs/ IS GENERATED OUTPUT AND GITIGNORED. Nothing there is tracked, so a fresh
# checkout has no pages until `make study-docs` (or any study run) builds them.
# The hand-written architecture doc that used to live there is now ARCHITECTURE.md
# at the repo root.
# Each run writes two files: the study_output FRAGMENT (no doctype/head/body —
# what the Artifact publisher wants; --standalone wraps it for a browser) and a
# standalone docs/account-sim-charts.html, the same deal as docs/study-map.html.
# The structure arm writes ONLY the fragment — its page reads the same as the
# frozen book's chart for chart, so there is one charts page for that arm and an
# explicit --docs on it is refused. --no-docs skips the docs copy.
# The report is auto-paired to the positions file's ARM on BOTH axes (structure and
# compounding), and every CSV-recomputed figure is reconciled against the report
# before writing — a mismatch exits non-zero. Do not add a statistic the study
# refuses to print (no annualised figure / Sharpe / time-to-recover).

python3 -m scripts.study_charts.compounding              # → docs/account-sim-compounding.html
make study-chart-compounding-open                        # rebuild it and open it
# THIRD page: the COMPOUNDING arm's own readout, drawn from
# account_sim-compounding-latest.txt + account_sim-positions-compounding-latest.csv.
# Same page shape as the frozen book's charts page plus the EQUITY MARKS re-mark
# series, which exists only on this arm. It is a POST-HOC, NOT-pre-registered
# sensitivity — the page says so, and A2/A5 do not transfer to it.

python3 -m scripts.study_charts.regime                   # → docs/account-sim-regime.html
make study-chart-regime-open                             # rebuild it and open it
# SECOND page over the same run: what the deployed book was, by market regime —
# mech_cell (lib/mech_regime.py) and the model read (market_regime), side by side,
# plus what the caps skipped per cell and where the two readings disagree.
# account_sim pre-registers NO regime cut, so the study prints this cut ITSELF
# (its `DEPLOYED BOOK BY REGIME` section, flagged post-hoc, thin cells marked) and
# the page reconciles against it like every other figure. Adding a regime table to
# the page WITHOUT adding it to the study first is the thing not to do.
# Shared page shell: scripts/study_charts/cli.py (pipeline), assets/kit.js (chart
# primitives, inlined ahead of each page's own script).

# Dashboard
cd web && npm run dev   # http://localhost:3000

# Authenticate Google Drive (OAuth2, run once)
python3 scripts/auth_drive.py
```

## Architecture

```
Barchart.com
    │ (scrape_flow.py — 2×/day via GitHub Actions)
    ▼
Google Drive (OAuth2 personal account)
    {GOOGLE_DRIVE_FOLDER_ID}/
      {YYYY-MM-DD}/
        {prefix}-{YYYYMMDD}-{HHMM}.csv
    │
    │ scripts/analysis_pipeline/fetch.py → markdown to LLM
    ▼
Claude Code: /options analyze ──► AnalysisClaude tab
    │
    ▼
Google Sheets (service account) ──► Next.js Dashboard (web/)
```

**Two separate Google auth systems:**

- **Google Drive** — OAuth2 personal account; token stored at `credentials/drive_token.json`;
  configured via `GOOGLE_OAUTH_CLIENT_JSON` + `GOOGLE_OAUTH_TOKEN_JSON`
- **Google Sheets** — service account JSON; configured via `GOOGLE_SERVICE_ACCOUNT_JSON` or
  `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`

## File layout

Compact map only. **Before editing `lib/` or `scripts/` code, read the matching section of
`ARCHITECTURE.md`** — it holds the per-file data contracts, column schemas, and
resume/idempotency semantics that used to live here.

```
lib/                        ← shared modules, imported by scripts, never run directly
  barchart/                 — Barchart scrapers + feed parsers ONLY (no logic): session.py
                              (BarchartSession), options.py, iv_history.py, underlying.py,
                              corporate_actions.py
  parsing.py                — to_float: the single Barchart numeric-cell parser
  baseline.py               — market-level daily baseline (pure; tab I/O in build_baseline.py)
  iv_history.py             — per-ticker IV-percentile enrichment logic (pure; kept OUT of barchart/)
  csv_utils.py              — parse_csv (strips Barchart footer)
  counterpart_iv.py         — IV-spread counterpart-fetch logic (pure; shared producer/consumer)
  price_catalyst.py         — price/earnings-catalyst enrichment + score_price/score_catalyst (pure)
  drive_client.py           — DriveClient, StorageClient protocol, file naming helpers
  sheets_client.py          — read/write Google Sheets tabs

scripts/                    ← entry points, each maps to a workflow step
  collector/                — scrape_flow.py, enrich_oi.py, fetch_iv_percentile.py,
                              fetch_counterpart_iv.py, fetch_price_catalyst.py
                              fetch_underlying_ohlc.py, fetch_counterpart_history.py
                              (run as `python scripts/collector/<name>.py`)
  compile_flow.py           — dedupe a day's hourly snapshots → compiled CSV in Drive
  gc_flow.py                — trash raw snapshots verified-present in the compiled file
  build_baseline.py         — one market-aggregate row per trading date → BaselineDaily
  analysis_pipeline/        — fetch → headless engine → Sheets; source of truth for /options
                              analyze. config.py = ALL user-tunable settings; fetch.py = Drive →
                              markdown; core.py = implementation; __main__.py = entry point
  backtest.py               — leg-based backtest of analysis plays (shared internals in
                              scripts/backtest/shared/, used by core.py and proxy.py)
  backtest/proxy.py         — fallback-chain proxy backtest for plays the real backtest skipped
  backtest_study/           — RESEARCH tier, never imported by production and never scheduled.
                              Tuning studies that argue about the book: run.py = runner
                              (`python -m scripts.backtest_study`); harness.py = FROZEN exit-replay
                              engine (do not edit — every recorded conclusion rests on it);
                              book.py = pooled real+proxy book loader; underlying.py = daily
                              stock bars (real OHLC → `Price~` close-only fallback; the
                              all-legs widening harness.py must not get);
                              underlying_features.py = as-of-entry price-STATE columns
                              (rv20/rv_parkinson/semivar_dn/atr14_pct/eff_ratio/vrp/beta —
                              the OHLC-only two carry a smaller denominator, always print
                              `coverage()`); protocol.py = purged
                              walk-forward / date-clustered CIs / LOO. Reports land in
                              backtests/study_output/ (scratch); conclusions in
                              config/backtest-tuning/current.md
  study_map/                — RESEARCH tier. Renders docs/study-map.html: what each study
                              asks (catalog.py, hand-written) + what its last run printed
                              (summary.py, quoted from the reports) + the newest current.md
                              sections (tuning.py). Rebuilt automatically by the study
                              runner and by study_review; `make study-map` to force it.
  study_charts/             — RESEARCH tier. Renders a study's result as
                              self-contained HTML pages; adds no conclusion.
                              report.py = strict parser for the fixed-width report
                              (a changed section raises, never a half-drawn chart);
                              series.py = positions-CSV series + `reconcile()`, which
                              must agree with the report or the build fails;
                              cli.py = the pipeline every page shares (arm pairing on
                              both the structure and compounding axes,
                              reconcile-or-write-nothing, docs copy rules);
                              account_sim.py + render.py + assets/page.js = the
                              account feasibility readout (capital read from the
                              report, not hardcoded); regime.py + render_regime.py +
                              assets/regime.js = the deployed book by market regime;
                              compounding.py = the same readout for the compounding
                              arm, plus its EQUITY MARKS series;
                              assets/kit.js = chart primitives shared by all;
                              assets/page.css = the tokens the pages draw from
  auth_drive.py             — one-time OAuth2 flow for Drive
```

**Workflows at a glance:**

```
# Live (runs 2×/day via GitHub Actions, then skill on demand)
scripts/collector/scrape_flow.py --mode flow
scripts/collector/scrape_flow.py --mode unusual
→ /options analyze  (Claude Code)

# Historical
scripts/collector/scrape_flow.py --start … --end …
python3 -m scripts.analysis_pipeline --date …   (fetch + analyze + write)
```

**Google Sheets tabs:**

- **AnalysisClaude** — `/options analyze` via Claude Code (appends one row per ticker/play per
  run)
- **AnalysisGPT** — retired (historical only); was written by `/options analyze --engine codex`
  via GPT Codex until the codex engine was removed 2026-08-13. Old rows stay in the tab and are
  still readable by anything that reads the schema below, but nothing writes new rows to it.
- **AnalysisClaude** also carries deterministic per-ticker rollup context
  (`oi_confirm_pct`/`cpir`/`iv_spread`/`iv_skew`/`iv_pct`), joined from that date's
  `audit/<date>-rollup.csv` at row-expansion time (NOT model-produced) — appended at the end of
  `ROW_COLUMNS`, kept separate from the model's `signal`. The backtest reads these straight off
  the row (audit CSV is a fallback for older rows). NOTE: adding a column (e.g. `iv_pct`/`IVPct`)
  means the AnalysisClaude/AnalysisTickerSpecific tab HEADER must gain that column
  too, or new rows write an unlabelled trailing column.
- **AnalysisTickerSpecific** — `analysis_pipeline --tickers …` (ticker-focused runs; same row
  schema, kept separate from the daily full-market tabs)
- **BacktestResults** — `backtest.py` (optional)
- **BacktestProxy** — `backtest/proxy.py` (one row per analysis play missing from
  BacktestResults: skip_reason + fallback-chain proxy verdict; result columns mirror
  BacktestResults)
- **BaselineDaily** — `build_baseline.py` (one market-aggregate row per trading date; regime
  baseline read back by `analysis_pipeline/fetch.py`). NOT versioned — it carries across
  prompt versions, so a version bump never resets the regime history.
- **\_meta** — `sheets_client.py` (dedup hashes)

**Prompt versions and the `vN_` tabs.** Any change to the analysis prompt or its inputs is a
**version bump**: the live tabs are renamed in place with a `vN_` prefix (`v3_AnalysisClaude`,
`v3_BacktestResults`, `v3_BacktestProxy`) and the pipeline recreates empty ones on next append.
This is a rename, NOT a new spreadsheet — `GOOGLE_SPREADSHEET_ID` and every tab name in code
stay unchanged. The point is that rows from two prompt versions are never pooled: a backtest
conclusion derived on vN does not automatically transfer to vN+1.

- **v4 is current** (2026-08-11): `score_flow`/`score_dealer` dropped from the prompt, so
  `score_total` runs 0–50 (0–55 for VOLATILITY intent) — **not** comparable to v3's 0–100.
  `ROW_COLUMNS` was 25 at the v4 cut-over and is 26 since `iv_pct_status` was appended
  (append-at-end; not a version bump — no prompt or input changed).
- **v3 is frozen** as the evidence base for every shipped rule in
  `config/deployment-rules.md`. To run anything against it, pass
  `--tab v3_AnalysisClaude`; a bare `python3 -m scripts.backtest` reads the empty v4 tab.
- Studies under `scripts/backtest_study/` read CSV exports in `backtests/to_evaluate/` by
  filename, so they are unaffected by the rename.
- `RESULT_COLUMNS` (`scripts/backtest/core.py`) deliberately KEEPS `score_flow`/`score_dealer`
  even though v4 never populates them — the results schema must stay stable across eras or the
  study loaders break on pooled exports.

## Invariants (do not regress)

- **Per-play `regime` and `signal` are ticker-specific, never copies of the market read.** The
  MARKET row of an analysis carries the top-level `regime` + `signals` (+ folded `themes`);
  each play row carries its OWN `regime` and `signal` taken from inside the play dict. Either play
  field may be empty, but they must NEVER fall back to the market values. See the invariant
  comment on `analysis_to_rows()` in `scripts/analysis_pipeline/core.py` and the per-play schema
  in `scripts/analysis_pipeline/config.py` (`ANALYSIS_PROMPT_CONTRACT`). This regression has
  happened before — keep the touch points (JSON contract, row expansion, claude.md) in sync.

## Skill modes

The `/options` skill routes as follows:

- `analyze` — shells out to `python3 -m scripts.analysis_pipeline` (does NOT analyze in-context).
  Runs fetch → headless engine call → write; the LLM step is an isolated session so the
  framework/method/raw data never enter the calling agent's context. Model-agnostic via
  `--engine`: `claude` (default, currently the only registered engine) uses `claude -p` +
  `claude.md` → AnalysisClaude. All operator-tunable settings live in
  `scripts/analysis_pipeline/config.py`; `--model` overrides the engine model. The full data
  contract — rollup conviction `Score`/`OIConfirmPct`/pollution columns, `IVspr`/`IVskew`/`IVpct`,
  hedge pressure, per-play `flow_intent`/`horizon`/`key_level`/`direction`, the three
  `score_*` components (v4 dropped `score_flow`/`score_dealer`; only `score_vol` is
  model-emitted, `score_price`/`score_catalyst` are pipeline-computed) + `score_total`
  bands (v4: 0–50, NOT comparable to v3's 0–100), and the `themes` array — is documented in
  `ARCHITECTURE.md` §"/options analyze" and `config/conviction-score.md`; read those only
  when changing the pipeline or its schema, not to run it
- `modes/summary.md` — reads latest rows from AnalysisClaude, formats for display
- `modes/positions.md` — fetches live positions from IBKR MCP and cross-references against latest
  flow data

The analysis framework (`config/analysis-framework.md`) defines the 5-step process: regime
classification (BULL/BEAR/RANGE + volatility + sentiment labels, with macro **optional** — only
assigned when corroborated by cross-asset evidence), signal tagging
([FLOW]/[PRICE]/[MACRO]/[VEGA]/[CAT]), sector narrowing, play proposals, and invalidation
conditions. Output is a JSON object with keys: `regime`, `signals`, `themes`, `plays`,
`invalidation`.

Model-specific analysis judgment is documented in `config/analysis-methods/`.
Each model should apply the shared framework, then use its own method file to
weight evidence and resolve conflicting flow.

## Configuration files

- `.env` — credentials and paths (see `.env.example` for all required vars)
- `config/positions.yml` — open options positions for position review
- `config/backtest.yml` — backtest settings (analysis tab to test, entry match side, path cap,
  profit/stop, pricing fallbacks). No signal filter — the analysis is the filter.
- `config/account-sim.yml` — RESEARCH tier. The `account_sim` study's whole parameter surface:
  capital, risk %, positions/day, the two delta-notional caps, the cap/capital grids, the hedge
  fraction, the dense-episode definition, the A2/A3/A5 thresholds, G1's expected book line, and
  the compounding arm's `mark_interval`/`budget_ceiling` (the arm itself is the `--compounding`
  flag, not a config switch). `scripts/backtest_study/account_sim.py` reads it and holds no
  state of its own.
- `config/barchart-reference.md` — column definitions for barchart CSV data
- `config/backtest-reference.md` — column definitions for the `BacktestResults` sheet (realized
  exit, MFE/MAE, the `daily_price_csv` path)

## Testing

Tests live in `tests/`. `conftest.py` adds the project root (for `lib.*`) and `scripts/` to
`sys.path`. Tests use mock Drive services injected via `DriveClient(service, root_folder_id)` — no
real credentials needed.

<!-- rtk-instructions v2 (trimmed 2026-08-13; full reference: ~/.claude/rtk-reference.md) -->
# RTK (Rust Token Killer)

**Always prefix shell commands with `rtk`** — dedicated filters cut 60–99% of
output; unfiltered commands pass through unchanged, so it is always safe. Use it
inside `&&` chains too (`rtk git add . && rtk git commit -m "msg"`). A hook also
rewrites plain commands automatically. `rtk proxy <cmd>` runs unfiltered
(debugging); `rtk gain` shows savings. Full per-command reference:
`~/.claude/rtk-reference.md` (open on demand, not auto-loaded).
