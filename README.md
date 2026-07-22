# Options Trading Toolkit

Automated options-flow intelligence: scrapes barchart.com on a schedule, stores raw
data in Google Drive, compiles and enriches it, then runs dual LLM analysis
(Claude + GPT Codex) and surfaces the results in Google Sheets and a Next.js dashboard.

## Architecture

```
Barchart.com
    │ (scrape_flow.py — Playwright, hourly flow + daily unusual via GitHub Actions)
    ▼
Google Drive (OAuth2 personal account)
    {GOOGLE_DRIVE_FOLDER_ID}/{YYYY-MM-DD}/{prefix}-{YYYYMMDD}-{HHMM}.csv
    │
    │ compile_flow.py   → one deduped {prefix}-{YYYYMMDD}-compiled.csv per day
    │ enrich_oi.py      → appends next-day OI change + EOD greeks per contract
    │ build_baseline.py → one market-aggregate row per date (regime baseline)
    │
    │ scripts/analysis_pipeline/fetch.py → markdown to the engine
    ▼
Claude Code  (/options analyze)              ──► AnalysisClaude tab
GPT Codex    (/options analyze --engine codex) ──► AnalysisGPT tab
    │
    ▼
Google Sheets (service account) ──► Next.js Dashboard (web/, localhost:3000)
```

**Two separate Google auth systems:**

- **Google Drive** — OAuth2 personal account; token at `credentials/drive_token.json`,
  configured via `GOOGLE_OAUTH_CLIENT_JSON` + `GOOGLE_OAUTH_TOKEN_JSON`. Holds all raw,
  compiled, and enriched CSV data.
- **Google Sheets** — service account JSON; configured via `GOOGLE_SERVICE_ACCOUNT_JSON`
  or `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`. Holds analysis results and the baseline,
  and feeds the dashboard.

## Quick Start

### 1. Python environment

```bash
cd options-trading
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Credentials

Copy `.env.example` → `.env` and fill in (see `.env.example` for the full list):

```
BARCHART_EMAIL=your@email.com
BARCHART_PASSWORD=yourpassword

# Google OAuth2 (Drive) — run scripts/auth_drive.py once to mint the token
GOOGLE_OAUTH_CLIENT_JSON=/path/to/oauth_client.json
GOOGLE_OAUTH_TOKEN_JSON=/path/to/drive_token.json
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id

# Google Sheets (analysis results + dashboard)
GOOGLE_SPREADSHEET_ID=your_sheet_id
```

Then authenticate Drive once:

```bash
python3 scripts/auth_drive.py
```

### 3. Test scraper locally

```bash
# Watch the browser (headless=false for debugging)
SCRAPE_HEADLESS=false python3 scripts/collector/scrape_flow.py --mode flow
SCRAPE_HEADLESS=false python3 scripts/collector/scrape_flow.py --mode unusual
```

### 4. GitHub Actions (free cloud hosting)

Push this folder to a (private) GitHub repo and add the secrets used by the workflows:
`BARCHART_EMAIL`, `BARCHART_PASSWORD`, `GOOGLE_OAUTH_TOKEN_JSON_CONTENT`,
`GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`, `GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_SPREADSHEET_ID`.

| Workflow           | Schedule (UTC)                    | Does                                             |
| ------------------ | --------------------------------- | ------------------------------------------------ |
| `scrape.yml`       | `:30` hourly 13:30–21:30, Mon–Fri | flow snapshots; `0 22` daily → unusual           |
| `compile-flow.yml` | `30 22` Mon–Fri                   | compile day's snapshots, GC raws, build baseline |
| `enrich-oi.yml`    | after compile                     | append next-day OI change + EOD greeks           |

The cron expressions target EDT (UTC-4). During EST (UTC-5) jobs fire one hour early;
the in-script market-hours guard exits cleanly if run before the open.

### 5. Dashboard

```bash
cd web
cp .env.local.example .env.local
# Fill in GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT and GOOGLE_SPREADSHEET_ID
npm run dev   # http://localhost:3000
```

> Before editing any Next.js code, read `web/AGENTS.md` — this version may have
> breaking API changes from training data.

## Skill commands

```bash
# Run analysis (fetch → headless engine → write Sheets). Claude by default.
/options analyze

# Same pipeline via GPT Codex → AnalysisGPT tab
/options analyze codex

# Display latest stored analysis (no token cost)
/options summary

# Cross-reference live IBKR positions against latest flow
/options positions
```

`/options analyze` shells out to `python3 -m scripts.analysis_pipeline`; the LLM step
runs in an isolated headless session so the framework/raw data never enter the calling
agent's context. The engine is model-agnostic via `--engine` (`claude` → `claude -p`,
`codex` → `codex exec`); `--model` overrides the default. All operator-tunable settings
live in `scripts/analysis_pipeline/config.py`.

### Scheduled analysis

```
/schedule options-analyze-morning: run /options analyze every weekday at 11:00 AM ET
/schedule options-analyze-eod: run /options analyze every weekday at 4:30 PM ET
```

These use your Claude Code subscription (no Anthropic API billing).

## Data pipeline (manual / backfill)

```bash
# Compile a day's hourly flow snapshots into one deduped CSV per type (→ Drive)
python3 scripts/compile_flow.py                       # today (ET)
python3 scripts/compile_flow.py --date 2026-06-09

# GC raw snapshots once verified present in the compiled file (→ Drive trash)
python3 scripts/gc_flow.py --all --dry-run

# Append daily market-baseline rows to the BaselineDaily tab
python3 scripts/build_baseline.py --backfill

# Enrich a compiled file with next-day OI change + EOD greeks
python3 scripts/collector/enrich_oi.py                          # latest enrichable date
python3 scripts/collector/enrich_oi.py --backfill               # idempotent; skips enriched
python3 scripts/collector/enrich_oi.py --date 2026-06-09 --force

# Full analysis pipeline directly (without the skill)
python3 -m scripts.analysis_pipeline --date 2026-04-21
python3 -m scripts.analysis_pipeline --engine codex
python3 -m scripts.analysis_pipeline --skip-llm --dry-run
```

## Positions tracking

`/options positions` pulls live positions from the IBKR MCP and cross-references them
against the latest flow. `config/positions.yml` holds a manual fallback / example
positions (single-leg and multi-leg structures); see the comments in that file.

## Backtesting

The backtest is **analysis-driven**: it reads the plays written to the analysis tab,
models each as signed legs, prices each leg (Barchart per-contract history → flow
reappearance → Black-Scholes), and computes unified P&L over the path to expiry/cap with
realized exit + MFE/MAE. There is no separate signal filter — the stored analysis is the
filter.

### 1. Collect historical data

```bash
python3 scripts/collector/scrape_flow.py --date 2026-04-21
python3 scripts/collector/scrape_flow.py --start 2026-01-02 --end 2026-05-30 --skip-existing
```

Raw CSVs land in Google Drive under `{YYYY-MM-DD}/`.

### 2. Configure and run

```bash
python3 -m scripts.backtest --config config/backtest.yml
python3 -m scripts.backtest --config config/backtest.yml --dry-run
```

Settings live in `config/backtest.yml` (analysis tab to test, entry match side, path cap,
profit/stop, pricing fallbacks). Column definitions for the output are in
`config/backtest-reference.md`; tuning history is in `config/backtest-tuning/`. Results
are written to `BacktestResults` (optional) plus the per-day `daily_price_csv` series.

## Google Sheets tabs

| Tab             | Written by                                                           |
| --------------- | -------------------------------------------------------------------- |
| AnalysisClaude  | `/options analyze` via Claude Code (one row per ticker/play per run) |
| AnalysisGPT     | `/options analyze --engine codex` via GPT Codex                      |
| BaselineDaily   | `build_baseline.py` (one market-aggregate row per trading date)      |
| BacktestResults | `backtest.py` (optional)                                             |
| \_meta          | `sheets_client.py` (dedup hashes)                                    |

## Notes

- The scraper logs into barchart via Playwright and reuses session cookies. On GitHub
  Actions cookies don't persist between runs (acceptable for the scheduled cadence).
- The market-hours guard uses `America/New_York` regardless of system timezone; GitHub
  Actions runs in UTC.
- The `AnalysisClaude` / `AnalysisGPT` tabs are **append-only** — each run adds one MARKET
  row plus one row per ticker/play. Never clear them without explicit confirmation; the
  backtest depends on the stored history.
- A later `compile_flow` re-run regenerates the compiled file and drops the enrichment
  columns; the next `enrich_oi --backfill` re-adds them.
  </content>
  </invoke>
