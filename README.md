# Options Trading Toolkit

Automated options-flow intelligence: scrapes barchart.com on a schedule, stores raw data in
Google Drive, compiles and enriches it, runs LLM analysis via Claude, backtests the plays it
produced, and closes the loop with a daily trade journal against the live broker book.

Prose lives in exactly two tracked places — `docs/` (how the system works, how to run it) and
`research/` (what we learned and how we learned it). `config/` holds only what code reads.
`site/` is generated HTML and is gitignored.

## Where do I look for X?

| Question you're actually asking                              | Go here                                                             |
| ------------------------------------------------------------ | ------------------------------------------------------------------- |
| How does the system work? What does this module do?          | `docs/architecture.md` — per-file contracts, flag matrices, journal + study internals |
| What should I deploy today?                                   | `docs/deployment-rules.md` — the operator card: VETOs, tier ladder, entry/exit         |
| Why does that deployment rule exist?                          | `research/deployment-evidence.md` — the numbers, CIs and rollback triggers behind each rule |
| What do these backtest output columns mean?                   | `docs/backtest-reference.md` (`BacktestResults` + `backtests/results.csv`)             |
| What does this Barchart flow column mean?                     | `docs/barchart-reference.md` — vendor help text, verbatim                              |
| What are the per-ticker rollup columns the LLM reads?         | `docs/rollup-reference.md`                                                             |
| How is the conviction score computed?                         | `docs/conviction-score.md` — full spec (the model-facing condensed copy is `config/prompts/conviction-score-legend.md`) |
| What did we try, and what happened?                           | `research/current.md` (newest), `research/archive/01..14` (older volumes)              |
| What does each backtest study ask?                            | `research/study-map.md`; the pre-run commitments are `research/pre-registrations/`     |
| What does this study metric mean?                             | `research/glossary.md`                                                                 |
| Where were we, what's next?                                   | `research/next-steps.md` (handoff), `research/analysis-roadmap.md` (design rationale)  |
| Was this old backtest-engine TODO ever done?                  | `research/backlog.md` — the 2026-06 list, triaged 2026-08-15 (mostly superseded or refuted; **not** the live queue) |
| What is the model actually prompted with?                     | `config/prompts/` — `analysis-framework.md`, `conviction-score-legend.md`, `analysis-methods/` |
| What settings can I change?                                   | `config/*.yml` (backtest, account-sim, positions) and `scripts/analysis_pipeline/config.py` |
| Where are the generated pages (study map, charts, journal)?   | `site/` — generated, gitignored; rebuild with `make study-docs`                        |
| What are the agent-facing rules and invariants?               | `CLAUDE.md`                                                                            |
| What's in `docs/` and why?                                    | `docs/README.md`                                                                       |
| What's in `research/` and why?                                | `research/README.md`                                                                   |

`site/` has no contents in a fresh checkout — the pages are build output, not source. Run
`make study-docs` (study map + study charts) or any study run to populate it.

## Architecture

```
Barchart.com
    │ (scrape_flow.py — Playwright, hourly flow + daily unusual via GitHub Actions)
    ▼
Google Drive (OAuth2 personal account)
    {GOOGLE_DRIVE_FOLDER_ID}/{YYYY-MM-DD}/{prefix}-{YYYYMMDD}-{HHMM}.csv
    │
    │ compile_flow.py            → one deduped {prefix}-{YYYYMMDD}-compiled.csv per day
    │ enrich_oi.py               → next-day OI change + EOD greeks per contract
    │ fetch_iv_percentile.py     → per-ticker IV percentile
    │ fetch_counterpart_iv.py    → matched-pair leg settlement IV (sidecar file)
    │ fetch_price_catalyst.py    → price / earnings-catalyst columns
    │ build_baseline.py          → one market-aggregate row per date (regime baseline)
    │
    │ scripts/analysis_pipeline/fetch.py → markdown to the engine
    ▼
Claude Code  (/options analyze)  ──► AnalysisClaude tab
    │
    ├─► Google Sheets (service account) ──► Next.js Dashboard (web/, localhost:3000)
    │
    ├─► scripts/backtest        ──► BacktestResults / BacktestProxy tabs
    │       └─► scripts/backtest_study (research tier) ──► research/current.md
    │
    └─► scripts/journal recommend ──► Recommendations tab   (what we said to trade)
            │  IBKR Flex statement ─┐
            ▼                       ▼
        scripts/journal          ──► TradeJournal tab       (what was actually traded)
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

`source .venv/bin/activate` is required before any script in this README. `pytest` runs the
whole suite; `pytest tests/test_drive_client.py` runs one file.

### 2. Credentials

Copy `.env.example` → `.env` and fill it in (that file lists every variable with notes):

```
BARCHART_EMAIL=your@email.com
BARCHART_PASSWORD=yourpassword

# Google OAuth2 (Drive) — run scripts/auth_drive.py once to mint the token
GOOGLE_OAUTH_CLIENT_JSON=/path/to/oauth_client.json
GOOGLE_OAUTH_TOKEN_JSON=/path/to/drive_token.json
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id

# Google Sheets (analysis results + dashboard)
GOOGLE_SPREADSHEET_ID=your_sheet_id

# Trade journal — a SEPARATE workbook from the one above
TRADE_JOURNAL_SPREADSHEET_ID=your_journal_sheet_id

# IBKR Flex (trade journal) — Flex is the only broker transport
IBKR_FLEX_TOKEN=
IBKR_FLEX_QUERY_TRADES_ID=
IBKR_FLEX_OPEN_POSITIONS_QUERY_ID=
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

| Workflow                  | Trigger (UTC)                          | Does                                                        |
| ------------------------- | -------------------------------------- | ----------------------------------------------------------- |
| `scrape.yml`              | `30 13-21` Mon–Fri; `0 22` Mon–Fri     | hourly flow snapshots; the 22:00 run downloads unusual      |
| `compile-flow.yml`        | `30 22` Mon–Fri                        | compile the day's snapshots, GC raws, refresh SPY/VIX table, append baseline |
| `enrich-oi.yml`           | chained off Compile Flow               | next-day OI change + EOD greeks, then IV percentile and price/earnings catalyst |
| `fetch-counterpart-iv.yml`| chained off Compile Flow               | matched-pair counterpart IV → per-date sidecar CSV          |
| `backfill-mech-cell.yml`  | chained off Compile Flow               | fill `mech_cell` on analysis rows; fails loudly on label drift |

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
/options analyze     # fetch → headless engine → write Sheets
/options summary     # display latest stored analysis (no token cost)
/options positions   # cross-reference open positions against latest flow
```

`/options analyze` shells out to `python3 -m scripts.analysis_pipeline`; the LLM step runs in
an isolated headless session so the framework/raw data never enter the calling agent's
context. `--engine claude` is the only registered engine; `--model` overrides the default.
Operator-tunable settings live in `scripts/analysis_pipeline/config.py`; the prompt itself is
assembled from `config/prompts/`.

`/options positions` syncs the open book from the trade journal workbook's `OpenPositions`
tab, falling back to whatever is in `config/positions.yml`.

### Scheduled analysis

```
/schedule options-analyze-morning: run /options analyze every weekday at 11:00 AM ET
/schedule options-analyze-eod: run /options analyze every weekday at 4:30 PM ET
```

These use your Claude Code subscription (no Anthropic API billing).

## Data pipeline (manual / backfill)

Common flags on the data steps: `--date YYYY-MM-DD` · `--backfill` (all dates, idempotent) ·
`--dry-run` · `--force` (clear + redo).

```bash
# Compile a day's hourly flow snapshots into one deduped CSV per type (→ Drive)
python3 scripts/compile_flow.py                       # today (ET)
python3 scripts/compile_flow.py --date 2026-06-09

# GC raw snapshots once verified present in the compiled file (→ Drive trash)
python3 scripts/gc_flow.py --all --dry-run

# Append daily market-baseline rows to the BaselineDaily tab
python3 scripts/build_baseline.py --backfill

# Enrichments (each writes back to the compiled file, except counterpart IV → sidecar)
python3 scripts/collector/enrich_oi.py --backfill
python3 scripts/collector/fetch_iv_percentile.py
python3 scripts/collector/fetch_counterpart_iv.py
python3 scripts/collector/fetch_price_catalyst.py

# Schema maintenance
python3 scripts/backfill_mech_cell.py                 # fill mech_cell on older analysis rows
python3 scripts/align_tab_headers.py --dry-run        # check tab headers against ROW_COLUMNS

# Full analysis pipeline directly (without the skill)
python3 -m scripts.analysis_pipeline --date 2026-04-21
python3 -m scripts.analysis_pipeline --date 2026-04-21 --tickers NVDA,AMD   # → AnalysisTickerSpecific
python3 -m scripts.analysis_pipeline --fetch-only     # fetch + audit CSV only, no LLM
```

`make help` lists the Makefile wrappers for all of the above (`make enrich-all`,
`make compile ARGS="--date …"`, and so on).

## Backtesting

The backtest is **analysis-driven**: it reads the plays written to the analysis tab, models
each as signed legs, prices each leg (Barchart per-contract history → flow reappearance →
Black-Scholes), and computes unified P&L over the path to expiry/cap with realized exit +
MFE/MAE. There is no separate signal filter — the stored analysis is the filter.

### 1. Collect historical data

```bash
python3 scripts/collector/scrape_flow.py --date 2026-04-21
python3 scripts/collector/scrape_flow.py --start 2026-01-02 --end 2026-05-30 --skip-existing
```

Raw CSVs land in Google Drive under `{YYYY-MM-DD}/`.

### 2. Configure and run

```bash
python3 -m scripts.backtest --config config/backtest.yml               # --dry-run to preview
python3 -m scripts.backtest.proxy --config config/backtest.yml         # untested plays → BacktestProxy
```

Settings live in `config/backtest.yml` (analysis tab to test, entry match side, path cap,
profit/stop, pricing fallbacks). Output column definitions: `docs/backtest-reference.md`.
Tuning history and conclusions: `research/current.md`.

**Prompt versions.** Any change to the analysis prompt or its inputs is a version bump; live
tabs are renamed in place (`v3_AnalysisClaude`, …). v4 is current; **v3 is frozen** as the
evidence base for every shipped deployment rule — pass `--tab v3_AnalysisClaude` to backtest
against it. Rows from two prompt versions are never pooled.

## Daily trade journal (production tier)

The analysis → trade → evidence loop. Fetches the IBKR Flex statement, reconciles fills
against the emitted plays, computes book risk, writes the `TradeJournal` tab, and produces
the next session's deploy card.

```bash
python3 -m scripts.journal                    # Flex fetch → reconcile → risk → report → write
python3 -m scripts.journal --offline          # read portfolio/input/ only, no network
python3 -m scripts.journal recommend          # deploy card → Recommendations tab + journal/recommendations.csv
python3 -m scripts.journal recommend --as-of 2026-08-14 --allow-stale   # replay a past morning
```

Flex is the only broker transport (`IBKR_FLEX_TOKEN` + `IBKR_FLEX_QUERY_TRADES_ID`). A short
Flex statement omits positions it didn't touch — fix a coverage gap by dropping a fresh export
into `portfolio/input/`, never by re-scoping the saved query. `journal/` is gitignored in full
(account ids, live position sizes), so a fresh checkout simply has no journal until the first
run. Ranking is deterministic from `docs/deployment-rules.md`; the model only annotates.
Transport, netting/coverage semantics and the flat-book guards: `docs/architecture.md`
§Daily trade journal.

## Research / backtest-study tier

Research code (`scripts/backtest_study/`, `study_map/`, `study_charts/`, `study_review/`) is
never imported by production and never scheduled. It produces reports, not trades. Studies sit
in four family folders under `backtest_study/` — `f1_selection/` → `f2_management/` →
`f3_structure/` → `f4_deployment/` (pick it, manage it, wrap it, fund it) — with the shared,
verdict-free substrate in `lib/`.

```bash
python3 -m scripts.backtest_study list               # available studies
python3 -m scripts.backtest_study run <name>         # → backtests/study_output/<name>-latest.txt
python3 -m scripts.study_review <name>               # A/B replication grading + digest
make study-docs                                      # rebuild every generated page in site/
```

`scripts/backtest_study/lib/harness.py` is the frozen exit-replay engine — every recorded
conclusion rests on it. Write-ups go to `research/current.md`; each study's pre-run commitment
goes to `research/pre-registrations/` *before* the run; the two-analyst grading procedure is
`research/replication-protocol.md`.

## Google Sheets tabs

Two separate workbooks, so the trade record can be shared (or kept unshared) independently of
the flow data.

**`GOOGLE_SPREADSHEET_ID`** — flow, analysis and backtest:

| Tab                   | Written by                                                                    |
| --------------------- | ----------------------------------------------------------------------------- |
| AnalysisClaude        | `/options analyze` — one MARKET row plus one row per ticker/play per run       |
| AnalysisTickerSpecific| `--tickers` runs; same row schema, kept separate                              |
| AnalysisGPT           | retired 2026-08-13 — historical rows only; nothing writes to it               |
| BaselineDaily         | `build_baseline.py` — one market-aggregate row per trading date; not versioned |
| BacktestResults       | `scripts/backtest` (optional)                                                 |
| BacktestProxy         | `scripts/backtest/proxy.py` — skipped plays, with skip_reason + fallback verdict |
| \_meta                | `sheets_client.py` (dedup hashes)                                             |

**`TRADE_JOURNAL_SPREADSHEET_ID`** — the live loop (a *different* spreadsheet):

| Tab             | Written by                                                                           |
| --------------- | ------------------------------------------------------------------------------------ |
| TradeJournal    | `scripts/journal` — deduped on `source_ref` (broker exec ids), so re-runs append only new fills |
| Recommendations | `scripts/journal recommend` — append-only and generational; an unchanged re-run appends nothing |

**Header rule:** `append_rows` writes positionally, so adding a column to `ROW_COLUMNS` or
`JOURNAL_COLUMNS` means the tab header must gain it too (append-at-end), or new rows write an
unlabelled trailing column. `python3 scripts/align_tab_headers.py --dry-run` checks.

## Notes

- The scraper logs into barchart via Playwright and reuses session cookies. On GitHub Actions
  cookies don't persist between runs (acceptable for the scheduled cadence).
- The market-hours guard uses `America/New_York` regardless of system timezone; GitHub Actions
  runs in UTC.
- The analysis tabs are **append-only**. Never clear them without explicit confirmation — the
  backtest depends on the stored history.
- A later `compile_flow` re-run regenerates the compiled file and drops the enrichment
  columns; the next `enrich_oi --backfill` re-adds them.
- `site/`, `backtests/`, `journal/`, `audit/` and `portfolio/input|output/` are all gitignored
  build output or live data. A fresh checkout has none of them; they appear on first run.
