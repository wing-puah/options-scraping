# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate Python environment (required before any script)
source .venv/bin/activate

# Run all tests
pytest

# Run a single test file
pytest tests/test_drive_client.py

# Scrape live data (run during/after market hours)
SCRAPE_HEADLESS=false python3 scripts/barchart_scrape.py --mode flow
SCRAPE_HEADLESS=false python3 scripts/barchart_scrape.py --mode unusual

# Compile a day's hourly flow snapshots into one deduped CSV per type (→ Drive)
python3 scripts/compile_flow.py                      # today (ET)
python3 scripts/compile_flow.py --date 2026-06-09
python3 scripts/compile_flow.py --date 2026-06-09 --dry-run   # report dup counts, no upload

# Garbage-collect raw snapshots once verified-present in their compiled file (→ Drive trash)
python3 scripts/gc_flow.py                            # today (ET)
python3 scripts/gc_flow.py --all                     # sweep every compiled date
python3 scripts/gc_flow.py --all --dry-run           # report what would be trashed

# Append daily market-baseline rows (regime baseline) to the BaselineDaily tab
python3 scripts/build_baseline.py                     # latest Drive date
python3 scripts/build_baseline.py --backfill          # every Drive date missing from the tab (idempotent)
python3 scripts/build_baseline.py --backfill --dry-run

# Full analysis pipeline: fetch → headless engine (claude/codex) → write Sheets
python3 -m scripts.analysis_pipeline                      # latest date, claude → AnalysisClaude
python3 -m scripts.analysis_pipeline --engine codex       # latest date, codex → AnalysisGPT
python3 -m scripts.analysis_pipeline --date 2026-04-21
python3 -m scripts.analysis_pipeline --start 2026-04-14 --end 2026-04-18 --days 5
python3 -m scripts.analysis_pipeline --date 2026-04-21 --dry-run   # fetch+analyze, no write
python3 -m scripts.analysis_pipeline --engine codex --model gpt-5  # override engine model
python3 -m scripts.analysis_pipeline --fetch-only                  # fetch + audit CSV only, no LLM
python3 -m scripts.analysis_pipeline --fetch-only --date 2026-06-09

# Scrape historical data to Google Drive
python3 scripts/barchart_scrape.py --date 2026-04-21
python3 scripts/barchart_scrape.py --start 2026-01-02 --end 2026-05-30 --skip-existing

# Backtest
python3 -m scripts.backtest --config config/backtest.yml
python3 -m scripts.backtest --config config/backtest.yml --dry-run

# Dashboard
cd web && npm run dev   # http://localhost:3000

# Authenticate Google Drive (OAuth2, run once)
python3 scripts/auth_drive.py
```

## Architecture

```
Barchart.com
    │ (barchart_scrape.py — 2×/day via GitHub Actions)
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
- **Google Drive** — OAuth2 personal account; token stored at `credentials/drive_token.json`; configured via `GOOGLE_OAUTH_CLIENT_JSON` + `GOOGLE_OAUTH_TOKEN_JSON`
- **Google Sheets** — service account JSON; configured via `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`

## File layout

```
lib/                        ← shared modules, imported by scripts, never run directly
  barchart.py               — BarchartSession (Playwright login + CSV download)
  barchart_options.py       — per-contract historical option prices (price-history URL + parse, mark-to-mid)
  baseline.py               — market-level daily baseline: per-date aggregate row schema, staleness-aware trailing window, percentile context markdown (pure functions; tab I/O lives in scripts/build_baseline.py)
  csv_utils.py              — parse_csv (strips Barchart footer)
  drive_client.py           — DriveClient, StorageClient protocol, file naming helpers
  sheets_client.py          — read/write Google Sheets tabs

scripts/                    ← entry points, each maps to a workflow step
  barchart_scrape.py        — scrape barchart → Drive; live (--mode) or historical (--date/--start)
  compile_flow.py           — compile a day's hourly etfs-flow + stocks-flow snapshots into one deduped CSV per type (trade-identity dedup) → {prefix}-{YYYYMMDD}-compiled.csv in Drive
  gc_flow.py                — garbage-collect raw snapshots: re-verifies every raw trade is present in the compiled file, then trashes the raws (recoverable). Separate from compile; --all sweeps all compiled dates. Daily after compile via .github/workflows/compile-flow.yml
  build_baseline.py         — compute one market-level aggregate row per trading date (lib/baseline.py) → append to BaselineDaily tab. Idempotent by date; --backfill self-heals missed days. Daily after compile via .github/workflows/compile-flow.yml
  analysis_pipeline/        — full pipeline package (run via `python3 -m scripts.analysis_pipeline`): fetch → headless engine call (isolated session; `--engine claude|codex`, `--model` overridable) → expand to per-ticker rows → append to the engine's tab (AnalysisClaude / AnalysisGPT). Source of truth for /options analyze; the skill just shells out here.
                              · config.py  — ALL user-tunable settings: engine registry (model/method/tab), retries, timeout, fetch defaults, sheet schema, prompt contract
                              · fetch.py   — Drive → markdown: scored rollups, top-N raw trades, cross-section, hedge pressure, baseline context, persistence
                              · core.py    — implementation (fetch/analyze/write, engine runners, row expansion, CLI)
                              · __main__.py — entry point
  backtest.py               — analysis-driven: reads analysis plays → models each as a list of signed legs (`scripts/backtest/legs.py`: `<±qty> TKR:exp:strike:C|P` per line, serialized to the `legs` column; existing structures map onto legs and an explicit leg-string in the play is parsed directly, enabling calendar/diagonal/ratio) → per-leg pricing (Barchart per-contract history → flow reappearance → Black-Scholes; uniform-BS for ≥`uniform_bs_min_legs` legs like iron condors) netted into a signed position value → unified P&L `(V−entry_net)/abs(entry_net)` over the path to min(nearest-leg DTE, cap) → realized exit + MFE/MAE; per-day series stored in `daily_price_csv` (see config/backtest-reference.md)
  auth_drive.py             — one-time OAuth2 flow for Drive
```

**Workflows at a glance:**

```
# Live (runs 2×/day via GitHub Actions, then skill on demand)
scripts/barchart_scrape.py --mode flow
scripts/barchart_scrape.py --mode unusual
→ /options analyze  (Claude Code or GPT Codex)

# Historical
scripts/barchart_scrape.py --start … --end …
python3 -m scripts.analysis_pipeline --date …   (fetch + analyze + write)
```

**Google Sheets tabs:**

| Tab | Written by |
|-----|-----------|
| AnalysisClaude | `/options analyze` via Claude Code (appends one row per ticker/play per run) |
| AnalysisGPT | `/options analyze` via GPT Codex (appends one row per ticker/play per run) |
| BacktestResults | `backtest.py` (optional) |
| BaselineDaily | `build_baseline.py` (one market-aggregate row per trading date; regime baseline read back by `analysis_pipeline/fetch.py`) |
| _meta | `sheets_client.py` (dedup hashes) |

## Invariants (do not regress)

- **Per-play `regime` and `signal` are ticker-specific, never copies of the market read.** The MARKET row of an analysis carries the top-level `regime` + `signals` (+ folded `sector_focus`); each play row carries its OWN `regime` and `signal` taken from inside the play dict. Either play field may be empty, but they must NEVER fall back to the market values. See the invariant comment on `analysis_to_rows()` in `scripts/analysis_pipeline/core.py` and the per-play schema in `scripts/analysis_pipeline/config.py` (`ANALYSIS_PROMPT_CONTRACT`). This regression has happened before — keep the four touch points (JSON contract, row expansion, claude.md, codex.md) in sync.

## Skill modes

The `/options` skill routes as follows:
- `analyze` — shells out to `python3 -m scripts.analysis_pipeline` (does NOT analyze in-context). Runs fetch → headless engine call → write; the LLM step is an isolated session so the framework/method/raw data never enter the calling agent's context. The pipeline is model-agnostic via `--engine`: `claude` (default) uses `claude -p` + `claude.md` → AnalysisClaude; `codex` uses `codex exec` + `codex.md` → AnalysisGPT. All operator-tunable settings (engines, retries, timeout, fetch defaults, sheet schema, output contract) live in `scripts/analysis_pipeline/config.py`; the model is overridable via `--model` (default: claude→`opus`, codex→its configured model). The prepared rollup carries a direction-agnostic conviction `Score` (0–10) per ticker, ranked on **extrinsic premium** (intrinsic stripped so deep-ITM financing flow can't buy rank), plus pollution/exposure columns (`Ext$`/`Fin%`/`ΔNot$`/`Hzn`) and a market-level **Hedge pressure** score (0–100) — see `config/conviction-score.md`. Each play also declares `flow_intent` (DIRECTIONAL/VOLATILITY/HEDGE/SYNTHETIC STOCK — a classification of what the flow IS, **not** a confidence cap; confidence is scored separately on evidence quality via the framework's Step 5 rubric, which is intent-weighted: Price-heavy for DIRECTIONAL, Vol-heavy for VOLATILITY) and `horizon` (one of 14|60|180|720 — the DTE bucket boundary of the dominant expiry in the cited evidence), folded into the play cell's bracket line (flow_intent upper-cased). `--days N` (default 5) appends a multi-day persistence section tracking recurring names
- `modes/summary.md` — reads latest rows from AnalysisClaude + AnalysisGPT, formats for display
- `modes/positions.md` — fetches live positions from IBKR MCP and cross-references against latest flow data

The analysis framework (`config/analysis-framework.md`) defines the 5-step process: regime classification (BULL/BEAR/RANGE + volatility + sentiment labels, with macro **optional** — only assigned when corroborated by cross-asset evidence), signal tagging ([FLOW]/[PRICE]/[MACRO]/[VEGA]/[CAT]), sector narrowing, play proposals, and invalidation conditions. Output is a JSON object with keys: `regime`, `signals`, `sector_focus`, `plays`, `invalidation`.

Model-specific analysis judgment is documented in `config/analysis-methods/`.
Each model should apply the shared framework, then use its own method file to
weight evidence and resolve conflicting flow.

## Configuration files

- `.env` — credentials and paths (see `.env.example` for all required vars)
- `config/positions.yml` — open options positions for position review
- `config/backtest.yml` — backtest settings (analysis tab to test, entry match side, path cap, profit/stop, pricing fallbacks). No signal filter — the analysis is the filter.
- `config/barchart-reference.md` — column definitions for barchart CSV data
- `config/backtest-reference.md` — column definitions for the `BacktestResults` sheet (realized exit, MFE/MAE, the `daily_price_csv` path)

## Testing

Tests live in `tests/`. `conftest.py` adds the project root (for `lib.*`) and `scripts/` to `sys.path`. Tests use mock Drive services injected via `DriveClient(service, root_folder_id)` — no real credentials needed.

## Web dashboard

`web/` is a Next.js app. Before writing any Next.js code, read `web/AGENTS.md` — it notes that this version may have breaking API changes from training data. Use `npm run dev` to start; reads from Google Sheets via service account credentials in `web/.env.local`.
