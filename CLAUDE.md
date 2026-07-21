# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Subagent model selection

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

# Daily data steps (each defaults to the latest date; full flag matrix in docs/architecture.md)
python3 scripts/compile_flow.py                       # dedupe hourly snapshots → compiled CSV (→ Drive)
python3 scripts/gc_flow.py                            # trash raws verified-present in compiled file
python3 scripts/build_baseline.py                     # market-baseline row → BaselineDaily tab
python3 scripts/collector/enrich_oi.py                # next-day OI change + EOD greeks (needs D+1)
python3 scripts/collector/fetch_iv_percentile.py      # per-ticker Barchart IV percentile (IVpct)
python3 scripts/collector/fetch_counterpart_iv.py     # matched-pair leg settlement IV → sidecar
python3 scripts/collector/fetch_price_catalyst.py     # price/earnings-catalyst columns
# Common flags: --date YYYY-MM-DD · --backfill (all dates, idempotent) · --dry-run ·
# --force (clear + re-scrape). compile_flow takes --start/--end; gc_flow uses --all.

# Full analysis pipeline: fetch → headless engine (claude/codex) → write Sheets
python3 -m scripts.analysis_pipeline                      # latest date, claude → AnalysisClaude
python3 -m scripts.analysis_pipeline --engine codex       # latest date, codex → AnalysisGPT
python3 -m scripts.analysis_pipeline --date 2026-04-21 --tickers NVDA,AMD,SPY  # → AnalysisTickerSpecific tab
python3 -m scripts.analysis_pipeline --fetch-only         # fetch + audit CSV only, no LLM
# Also: --start/--end, --days N, --dry-run, --model <id> (full matrix in docs/architecture.md)

# Backtest
python3 -m scripts.backtest --config config/backtest.yml
python3 -m scripts.backtest --config config/backtest.yml --dry-run

# Proxy-backtest untested plays (AnalysisClaude minus BacktestResults → BacktestProxy tab)
python3 -m scripts.backtest.proxy --config config/backtest.yml   # all dates, idempotent
# Also: --date, --dry-run, --cache-only (no scraping), --redo (re-evaluate frozen rows)

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
GPT Codex:   /options analyze ──► AnalysisGPT tab
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
`docs/architecture.md`** — it holds the per-file data contracts, column schemas, and
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
  auth_drive.py             — one-time OAuth2 flow for Drive
```

**Workflows at a glance:**

```
# Live (runs 2×/day via GitHub Actions, then skill on demand)
scripts/collector/scrape_flow.py --mode flow
scripts/collector/scrape_flow.py --mode unusual
→ /options analyze  (Claude Code or GPT Codex)

# Historical
scripts/collector/scrape_flow.py --start … --end …
python3 -m scripts.analysis_pipeline --date …   (fetch + analyze + write)
```

**Google Sheets tabs:**

- **AnalysisClaude** — `/options analyze` via Claude Code (appends one row per ticker/play per
  run)
- **AnalysisGPT** — `/options analyze` via GPT Codex (appends one row per ticker/play per run)
- **_(both above)_** — each play row also carries deterministic per-ticker rollup context
  (`oi_confirm_pct`/`cpir`/`iv_spread`/`iv_skew`/`iv_pct`), joined from that date's
  `audit/<date>-rollup.csv` at row-expansion time (NOT model-produced) — appended at the end of
  `ROW_COLUMNS`, kept separate from the model's `signal`. The backtest reads these straight off
  the row (audit CSV is a fallback for older rows). NOTE: adding a column (e.g. `iv_pct`/`IVPct`)
  means the AnalysisClaude/AnalysisGPT/AnalysisTickerSpecific tab HEADER must gain that column
  too, or new rows write an unlabelled trailing column.
- **AnalysisTickerSpecific** — `analysis_pipeline --tickers …` (ticker-focused runs; same row
  schema, kept separate from the daily full-market tabs)
- **BacktestResults** — `backtest.py` (optional)
- **BacktestProxy** — `backtest/proxy.py` (one row per analysis play missing from
  BacktestResults: skip_reason + fallback-chain proxy verdict; result columns mirror
  BacktestResults)
- **BaselineDaily** — `build_baseline.py` (one market-aggregate row per trading date; regime
  baseline read back by `analysis_pipeline/fetch.py`)
- **\_meta** — `sheets_client.py` (dedup hashes)

## Invariants (do not regress)

- **Per-play `regime` and `signal` are ticker-specific, never copies of the market read.** The
  MARKET row of an analysis carries the top-level `regime` + `signals` (+ folded `themes`);
  each play row carries its OWN `regime` and `signal` taken from inside the play dict. Either play
  field may be empty, but they must NEVER fall back to the market values. See the invariant
  comment on `analysis_to_rows()` in `scripts/analysis_pipeline/core.py` and the per-play schema
  in `scripts/analysis_pipeline/config.py` (`ANALYSIS_PROMPT_CONTRACT`). This regression has
  happened before — keep the four touch points (JSON contract, row expansion, claude.md, codex.md)
  in sync.

## Skill modes

The `/options` skill routes as follows:

- `analyze` — shells out to `python3 -m scripts.analysis_pipeline` (does NOT analyze in-context).
  Runs fetch → headless engine call → write; the LLM step is an isolated session so the
  framework/method/raw data never enter the calling agent's context. Model-agnostic via
  `--engine`: `claude` (default) uses `claude -p` + `claude.md` → AnalysisClaude; `codex` uses
  `codex exec` + `codex.md` → AnalysisGPT. All operator-tunable settings live in
  `scripts/analysis_pipeline/config.py`; `--model` overrides the engine model. The full data
  contract — rollup conviction `Score`/`OIConfirm`/pollution columns, `IVspr`/`IVskew`/`IVpct`,
  hedge pressure, per-play `flow_intent`/`horizon`/`key_level`/`direction`, the five
  `score_*` components + `score_total` bands, and the `themes` array — is documented in
  `docs/architecture.md` §"/options analyze" and `config/conviction-score.md`; read those only
  when changing the pipeline or its schema, not to run it
- `modes/summary.md` — reads latest rows from AnalysisClaude + AnalysisGPT, formats for display
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
- `config/barchart-reference.md` — column definitions for barchart CSV data
- `config/backtest-reference.md` — column definitions for the `BacktestResults` sheet (realized
  exit, MFE/MAE, the `daily_price_csv` path)

## Testing

Tests live in `tests/`. `conftest.py` adds the project root (for `lib.*`) and `scripts/` to
`sys.path`. Tests use mock Drive services injected via `DriveClient(service, root_folder_id)` — no
real credentials needed.
