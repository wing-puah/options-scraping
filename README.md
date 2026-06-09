# Options Trading Toolkit

Automated options flow intelligence: scrapes barchart.com twice daily, stores data in Google Sheets, and runs dual LLM analysis (Claude + GPT-4o) on demand.

## Architecture

```
Barchart.com
    │ (Playwright, 2×/day via GitHub Actions)
    ▼
Google Sheets  ──────────────────────────────►  Next.js Dashboard
    │                                            (localhost:3000)
    │ (fetch_for_analysis.py)
    ▼
Claude (in-context via /options analyze)
GPT-4o (OpenAI API via analyze_gpt.py)
    │
    ▼
Google Sheets (AnalysisClaude, AnalysisGPT tabs)
```

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

Copy `.env.example` → `.env` and fill in:

```
BARCHART_EMAIL=your@email.com
BARCHART_PASSWORD=yourpassword
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service-account.json
GOOGLE_SPREADSHEET_ID=your_sheet_id
OPENAI_API_KEY=sk-...
```

**Google service account setup:**
1. Go to Google Cloud Console → IAM & Admin → Service Accounts
2. Create a service account, download the JSON key
3. Open your Google Sheet, click Share, and share it with the service account email (Editor)
4. The sheet needs these tabs created automatically on first run:
   `UnusualStocks`, `UnusualETFs`, `OptionsFlow`, `AnalysisClaude`, `AnalysisGPT`, `_meta`

### 3. Test scraper locally

```bash
# Watch browser (headless=false for debugging)
SCRAPE_HEADLESS=false python3 scripts/scraper.py
```

### 4. GitHub Actions (free cloud hosting)

1. Push this folder to a GitHub repo (private recommended)
2. Add GitHub Secrets (Settings → Secrets → Actions):
   - `BARCHART_EMAIL`
   - `BARCHART_PASSWORD`
   - `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT` — paste the entire service account JSON as one line
   - `GOOGLE_SPREADSHEET_ID`
3. The workflow `.github/workflows/scrape.yml` runs automatically:
   - **10:30 AM ET** — 1 hour after market open
   - **4:30 PM ET** — after market close
4. Test manually: Actions tab → Options Scraper → Run workflow

### 5. Dashboard

```bash
cd web
cp .env.local.example .env.local
# Fill in GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT and GOOGLE_SPREADSHEET_ID
npm run dev
# Open http://localhost:3000
```

## Skill commands

```bash
# Run Claude + GPT-4o analysis (uses Claude subscription + OpenAI API)
/options analyze

# Display latest stored analysis (no token cost)
/options summary

# Cross-reference open positions against latest flow
/options positions
```

### Scheduled analysis via /schedule

After setup, run these in Claude Code to create automatic analysis routines:

```
/schedule options-analyze-morning: run /options analyze every weekday at 11:00 AM ET
/schedule options-analyze-eod: run /options analyze every weekday at 4:30 PM ET
```

These use your Claude Code subscription (no Anthropic API billing).

## Positions tracking

Edit `config/positions.yml` manually:

```yaml
positions:
  - symbol: TSLA
    type: Call
    strike: 250
    expiry: 2026-07-18
    qty: 5
    entry_price: 8.20
```

Or import from a broker CSV:

```bash
python3 scripts/import_positions.py /path/to/broker_export.csv
```

## Backtesting

### 1. Collect historical data (requires Barchart Premier)

```bash
# Single date
python3 scripts/barchart_scrape.py --date 2026-04-21

# Date range
python3 scripts/barchart_scrape.py --start 2026-01-02 --end 2026-05-30 --skip-existing
```

Data is stored in `HistUnusualStocks`, `HistUnusualETFs`, `HistOptionsFlow` tabs in Google Sheets.
Barchart historical flow goes back to 2024-01-02.

### 2. Configure signal filter

Edit `config/backtest.yml` to define what counts as a tradeable signal:
- `min_premium`: minimum trade size ($100K default)
- `side`: Ask (buyer-initiated), Bid, Mid, or any
- `special_label`: BuyToOpen, SellToOpen, ToOpen, or any
- `trade_code_group`: sweep (ISOI), block, regular, cross, or any
- `delta_min/max`, `dte_min/max`: option characteristics

### 3. Run backtest

```bash
# Default config
python3 scripts/backtest.py --config config/backtest.yml

# Override source and date range
python3 scripts/backtest.py --source flow --start 2026-01-01 --end 2026-04-30

# Dry run (no output files written)
python3 scripts/backtest.py --dry-run
```

Results written to `backtests/results.csv` and optionally the `BacktestResults` Google Sheets tab.

The engine:
- Applies your signal filter to the historical data
- Simulates the configured structure (long_call, bull_call_spread, etc.)
- Uses Black-Scholes with the signal's IV to price entry and exit
- Fetches historical underlying prices via yfinance
- Measures P&L at day 1, 3, 5, 10, 21 (configurable)
- Prints win rate, avg P&L, best/worst trade at each exit checkpoint

---

## Data flow

| Tab | Updated by | When |
|-----|------------|------|
| UnusualStocks | `scraper.py` | 2×/day via GitHub Actions |
| UnusualETFs | `scraper.py` | 2×/day via GitHub Actions |
| OptionsFlow | `scraper.py` | 2×/day via GitHub Actions |
| AnalysisClaude | `python3 -m scripts.analysis_pipeline` (`--engine claude`) | On `/options analyze` (Claude Code) |
| AnalysisGPT | `python3 -m scripts.analysis_pipeline --engine codex` | On `/options analyze codex` (GPT Codex) |
| _meta | `sheets_client.py` | After each scrape (dedup hashes) |

## Notes

- The scraper logs into barchart and saves cookies to `cookies/barchart_session.json` locally. On GitHub Actions, cookies don't persist between runs (acceptable for 2 logins/day).
- The market hours guard in `scraper.py` uses `America/New_York` timezone regardless of system timezone. GitHub Actions runs in UTC.
- The `AnalysisClaude` and `AnalysisGPT` tabs are **append-only** across `/options analyze` runs — each run adds one MARKET row plus one row per ticker/play for the date analyzed. Never clear the tabs without explicit confirmation; doing so destroys the historical analysis the backtest depends on.
- EDT vs EST: the GitHub Actions cron uses UTC. The cron expressions target EDT times (UTC-4). During EST (UTC-5), the scraper fires 1 hour early — the in-script guard exits cleanly if run before market open.
