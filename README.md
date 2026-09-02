# Options Trading Toolkit

Automated options-flow intelligence: scrapes barchart.com on a schedule, stores raw data in
Google Drive, compiles and enriches it, runs LLM analysis via Claude, backtests the plays it
produced, and closes the loop with a daily trade journal against the live broker book plus a
fortnightly live-vs-ladder audit.

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
| What did we try, and what happened?                           | `research/current.md` (newest), `research/archive/01..17` (older volumes)              |
| What does each backtest study ask?                            | `research/study-map.md`; the pre-run commitments are `research/pre-registrations/`     |
| What did study X actually print, on which population?         | `research/study-results/<family>/<study>.md` — append-only, one section per (era, sha) |
| How is a study result graded before it's believed?            | `research/replication-protocol.md` — the two-analyst A/B procedure                     |
| What does this study metric mean?                             | `research/glossary.md`                                                                 |
| Where were we, what's next?                                   | `research/next-steps.md` (handoff), `research/analysis-roadmap.md` (design rationale)  |
| What was the ML combination search, and what came of it?      | `research/pre-registrations/f1_selection/ml_combination.md` — pre-registered and executed 2026-08-11, NULL RESULT |
| Was this old backtest-engine TODO ever done?                  | `research/archive/00-backtest-engine-backlog-2026-06.md` — the 2026-06 list, triaged 2026-08-15, archived 2026-08-31 (mostly superseded or refuted; **not** the live queue) |
| What is the model actually prompted with?                     | `config/prompts/` — `analysis-framework.md`, `conviction-score-legend.md`, `analysis-methods/` |
| What settings can I change?                                   | `config/*.yml` (backtest, account-sim, positions) and `scripts/analysis_pipeline/config.py` |
| Where are the generated pages (study map, charts, journal)?   | `site/` — generated, gitignored; rebuild with `make study-docs`                        |
| What can I safely delete, and how do I rebuild it?            | `make clean-list` — every regenerable target, its size, and its rebuild command         |
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
    │ fetch_mech_regime.py       → SPY/^VIX daily closes (the mech_cell regime table)
    │ build_baseline.py          → one market-aggregate row per date (regime baseline)
    │
    │ scripts/analysis_pipeline/fetch.py → markdown to the engine
    ▼
scripts/analysis_pipeline (headless LLM step) ──► AnalysisClaude tab   (Google Sheets, same OAuth2 token)
    │
    ├─► scripts/backtest        ──► BacktestResults / BacktestProxy tabs
    │       └─► CSV exports in backtests/to_evaluate/ (era-scoped)
    │               └─► scripts/backtest_study (research tier)
    │                       ──► research/current.md + research/study-results/
    │
    ├─► scripts/journal recommend ──► Recommendations tab   (what we said to trade)
    │       │  IBKR Flex statement ─┐
    │       ▼                       ▼
    │   scripts/journal          ──► TradeJournal tab       (what was actually traded)
    │
    └─► scripts/live_loop         ──► fortnightly audit: did the fills match the ladder?
```

**One Google auth, two scopes.** Drive and Sheets both authorise from the *same* OAuth2
personal-account token — `lib/drive_client.py` and `lib/sheets_client.py` each read
`GOOGLE_OAUTH_TOKEN_JSON_CONTENT`, else the file at `GOOGLE_OAUTH_TOKEN_JSON` (default
`credentials/drive_token.json`), against scopes `drive` + `spreadsheets`. Mint it once with
`python3 scripts/auth_drive.py`, which needs `GOOGLE_OAUTH_CLIENT_JSON`.

- **Drive** (`GOOGLE_DRIVE_FOLDER_ID`) — all raw, compiled and enriched CSV data.
- **Sheets** (`GOOGLE_SPREADSHEET_ID`, `TRADE_JOURNAL_SPREADSHEET_ID`) — analysis results,
  the baseline, the backtest tabs and the trade journal.

> There is no service account. `GOOGLE_SERVICE_ACCOUNT_JSON` / `..._CONTENT` are read by no
> code in this repo, and no workflow exports the secret any more.
> If Sheets auth fails, refresh the OAuth token — do not go looking for a service-account key.

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

Two extra requirement sets exist and are deliberately *not* part of `requirements.txt`:

| File                       | Install it when                                                          |
| -------------------------- | ------------------------------------------------------------------------ |
| `requirements-compile.txt` | You only need the daily compile job (Drive + pandas + gspread + yfinance, no Playwright/scipy) — this is what the Compile Flow workflow installs |
| `requirements-study.txt`   | You run the research-tier studies (scikit-learn and friends); no production script or workflow needs it |

### 2. Credentials

Copy `.env.example` → `.env` and fill it in (that file lists every variable with notes):

```
BARCHART_EMAIL=your@email.com
BARCHART_PASSWORD=yourpassword

# Google OAuth2 — covers BOTH Drive and Sheets; run scripts/auth_drive.py once
GOOGLE_OAUTH_CLIENT_JSON=/path/to/oauth_client.json
GOOGLE_OAUTH_TOKEN_JSON=/path/to/drive_token.json
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id

# Google Sheets — analysis, baseline, backtest tabs
GOOGLE_SPREADSHEET_ID=your_sheet_id

# Trade journal — a SEPARATE workbook from the one above
TRADE_JOURNAL_SPREADSHEET_ID=your_journal_sheet_id

# IBKR Flex (trade journal) — Flex is the only broker transport
IBKR_FLEX_TOKEN=
IBKR_FLEX_QUERY_TRADES_ID=
IBKR_FLEX_OPEN_POSITIONS_QUERY_ID=   # optional; may repeat the trades id if that
                                     # query was saved with BOTH sections
# A Flex trades query reports no account equity, and every exposure cap is a
# fraction of it. Unset (and no --net-liq), the risk section reports
# "not evaluable" rather than guessing.
JOURNAL_NET_LIQUIDATION=
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
`GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_SPREADSHEET_ID`. (Three workflows also export
`GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`; nothing reads it — see the auth note above.)

| Workflow                  | Trigger (UTC)                          | Does                                                        |
| ------------------------- | -------------------------------------- | ----------------------------------------------------------- |
| `scrape.yml`              | `30 13-21` Mon–Fri; `0 22` Mon–Fri     | hourly flow snapshots; the 22:00 run downloads unusual      |
| `compile-flow.yml`        | `30 22` Mon–Fri                        | compile the day's snapshots, GC raws, refresh SPY/VIX table, append baseline |
| `enrich-oi.yml`           | chained off Compile Flow               | next-day OI change + EOD greeks, then IV percentile and price/earnings catalyst |
| `fetch-counterpart-iv.yml`| chained off Compile Flow               | matched-pair counterpart IV → per-date sidecar CSV          |
| `backfill-mech-cell.yml`  | chained off Compile Flow               | fill `mech_cell` on analysis rows; fails loudly on label drift |

The cron expressions target EDT (UTC-4). During EST (UTC-5) jobs fire one hour early;
the in-script market-hours guard exits cleanly if run before the open.

> **There is no `web/` dashboard.** Earlier revisions of this README documented a Next.js app
> at `web/` served on `localhost:3000`. That directory is not in the repo and not in git
> history, and nothing in the tree references it any more. Read results out
> of the Sheets tabs, or out of the generated pages in `site/`.

> **There is no `/options` skill.** This repo used to double as a Claude Code skill
> (`SKILL.md` + `modes/`, symlinked from `~/.claude/skills/options`) exposing
> `/options analyze | summary | positions`. That layer was removed — the repo is now a plain
> Python project. Run the pipeline directly (see below) or via `make analyze`. The `summary`
> and `positions` modes are gone entirely: read stored analyses out of the Sheets tabs, and
> the live book out of `python3 -m scripts.journal`.

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

# Regime table (PRODUCTION input — lib/mech_regime.py labels mech_cell from it)
python3 scripts/collector/fetch_mech_regime.py

# Schema maintenance
python3 scripts/backfill_mech_cell.py                 # fill mech_cell on older analysis rows
python3 scripts/align_tab_headers.py --dry-run        # check tab headers against ROW_COLUMNS

# Full analysis pipeline: fetch → headless engine → write Sheets
python3 -m scripts.analysis_pipeline --date 2026-04-21
python3 -m scripts.analysis_pipeline --date 2026-04-21 --tickers NVDA,AMD   # → AnalysisTickerSpecific
python3 -m scripts.analysis_pipeline --skip-llm       # fetch + audit CSV only, no LLM
```

The analysis pipeline runs its LLM step in an isolated headless session, so the framework and
raw flow data never enter the calling agent's context. `--engine claude` is the only registered
engine; `--model` overrides its default. Operator-tunable settings live in
`scripts/analysis_pipeline/config.py`; the prompt itself is assembled from `config/prompts/`.

`make help` lists the Makefile wrappers for all of the above (`make analyze`, `make enrich-all`,
`make compile ARGS="--date …"`, and so on).

### Research-tier caches

Not part of the daily pipeline — these back the studies that need real bars or a priceable
opposite leg. Both are resumable and write under `backtests/`.

```bash
python3 scripts/collector/fetch_underlying_ohlc.py        # stock OHLC per book ticker
python3 scripts/collector/fetch_counterpart_history.py    # opposite-leg option history (--limit N)
python3 scripts/collector/fetch_sweep_legs.py             # the legs calendar_hedge --arm S needs
```

`backtests/option_history_cache/` is ~337MB of scraped option history with no git history to
recover from. It is refetchable but slow — `make clean` leaves it alone unless you pass
`ARGS="--caches"`.

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
tabs are renamed in place (`v3_AnalysisClaude`, …) and the pipeline recreates empty ones. It is
a rename, not a new spreadsheet — ids and tab names in code are unchanged. Rows from two prompt
versions are never pooled.

- **v4 is current** (2026-08-11). `score_flow` and `score_dealer` were dropped, so `score_total`
  now runs 0–50 (0–55 for VOLATILITY) and is **not comparable to v3's 0–100**.
- **v3 is frozen** as the evidence base for every shipped rule in `docs/deployment-rules.md`.
  Pass `--tab v3_AnalysisClaude` to backtest against it; a bare backtest reads the (empty) v4 tab.
- `RESULT_COLUMNS` (`scripts/backtest/core.py`) deliberately **keeps** `score_flow` /
  `score_dealer`, blank on v4, so study loaders work on pooled exports. That is also what makes
  them a durable era discriminator — see the era section below.

## Daily trade journal (production tier)

The analysis → trade → evidence loop. Fetches the IBKR Flex statement, reconciles fills
against the emitted plays, computes book risk, writes the `TradeJournal` tab, and produces
the next session's deploy card.

```bash
python3 -m scripts.journal                    # Flex fetch → reconcile → risk → report → write
python3 -m scripts.journal --offline          # read portfolio/input/ only, no network
python3 -m scripts.journal recommend          # deploy card → Recommendations tab + journal/recommendations.csv
python3 -m scripts.journal recommend --as-of 2026-08-14 --allow-stale   # replay a past morning
python3 -m scripts.journal recommend --no-persist   # print the card, record nothing
python3 -m scripts.journal recommend --no-llm       # skip the judge() annotation pass
```

Flex is the only broker transport (`IBKR_FLEX_TOKEN` + `IBKR_FLEX_QUERY_TRADES_ID`). A short
Flex statement omits positions it didn't touch — fix a coverage gap by dropping a fresh export
into `portfolio/input/`, never by re-scoping the saved query. `journal/` is gitignored in full
(account ids, live position sizes), so a fresh checkout simply has no journal until the first
run. Transport, netting/coverage semantics and the flat-book guards: `docs/architecture.md`
§Daily trade journal.

Two properties of `recommend` worth knowing before you trust a card:

- **Ranking is deterministic** from `docs/deployment-rules.md` via `ladder_tier()`. The model
  sees only the survivors and annotates them; it never re-sorts, rebuilds, or promotes.
- **Nothing dated after the as-of date reaches it.** Analysis older than
  `RECOMMENDATION_MAX_AGE_DAYS` is refused unless `--allow-stale`; analysis dated *after*
  as-of is refused unconditionally, and `--allow-stale` cannot override that — it's lookahead,
  not staleness. The one thing that can't be bounded this way is the judge's own training
  cutoff, so every persisted row carries `judge_status` and `judge_lookahead_risk`.

The card is written to `journal/recommendations.csv` first (that failure is fatal), then to
the Recommendations tab (a Sheets failure is reported but never loses the row). Rows are
append-only and generational: an unchanged re-run appends nothing, a changed verdict appends
`generation = n+1` rather than overwriting.

## Live loop (production tier)

The fortnightly counterpart to the daily journal: take the real fills, map each back to the
analysis play that predicted it, and reconstruct which ladder tier that play would have been
given — so live behaviour can be graded against the rules rather than against memory.

```bash
python3 -m scripts.live_loop.stage1_map_fills
```

`scripts/live_loop/mapping.py::ladder_tier()` is the **only** encoding of
`docs/deployment-rules.md` §1–§3, and `scripts/journal/` imports it from there. Two copies
would let the daily card and the fortnightly audit disagree about the same structure. The
match vocabulary (`EXACT` / `STRUCTURE` / `CORE` / `OVERLAY`) is likewise defined once, in
`mapping.CONFIDENCES`.

## Research / backtest-study tier

Research code (`scripts/backtest_study/`, `study_map/`, `study_charts/`, `study_review/`) is
never imported by production and never scheduled. It produces reports, not trades. Studies sit
in four family folders under `backtest_study/` — `f1_selection/` → `f2_management/` →
`f3_structure/` → `f4_deployment/` (pick it, manage it, wrap it, fund it) — with the shared,
verdict-free substrate in `lib/`.

```bash
python3 -m scripts.backtest_study list               # available studies
python3 -m scripts.backtest_study run <name>         # → backtests/study_output/<name>-latest.txt
python3 -m scripts.backtest_study run <name> --era v3   # run against a PAST export era
python3 -m scripts.study_review <name>               # A/B replication grading + digest
make study-record                                    # append each report → research/study-results/
make study-docs                                      # rebuild every generated page in site/
```

### A study runs on one era, names it, and refuses if the exports aren't it

The bare export filename (`backtests/to_evaluate/analysis - AnalysisClaude.csv`) does **not**
name a fixed population — it names whatever the live tab held when it was exported. On
2026-08-15 a re-export turned four months of v3 evidence into 14 dates of v4 with no code
change: five studies failed loudly and fourteen succeeded quietly, promoting reports whose
numbers no longer matched the verdicts written against them.

`scripts/backtest_study/lib/era.py` is the single fix and the single encoding. `load_book()`
resolves paths from `STUDY_ERA` (default `current`), exits 3 when the exports on disk are not
the era asked for or disagree with each other, and exits 2 when an era is too thin to conclude
from. Every report header names the era it ran on. Do not pin a study to a frozen snapshot to
dodge this, and do not lower `MIN_ERA_DATES` to make a young era run.

Two related rules, both learned the hard way:

- **Never hardcode an expected figure off one export.** A stored `expected_positions: 220`
  fingerprints a snapshot, not a hypothesis — the book grows, the constant breaks, and the
  operator learns to edit it. Code-behaviour claims go in `tests/`; data claims go in
  `research/` with their population stated.
- **`backtests/` is not uniformly disposable**, despite what the `.gitignore` comment says.
  `to_evaluate/`, `option_history_cache/`, `live_loop/`, the `v1_*`/`v2_*` frozen exports and
  the hand-written date lists have no git history to recover from. `scripts/clean_generated.py`
  encodes what is safe to delete — extend its table rather than writing a new `rm -rf`.

`scripts/backtest_study/lib/harness.py` is the frozen exit-replay engine — every recorded
conclusion rests on it, and `tests/test_harness_replay.py` pins it against a committed fixture.
Write-ups go to `research/current.md`; each study's pre-run commitment goes to
`research/pre-registrations/` *before* the run and stays immutable; what a study actually
printed, per era and per sha, is appended to `research/study-results/`; the two-analyst grading
procedure is `research/replication-protocol.md`.

Study reports under `backtests/study_output/` are scratch that a later `run --all` can silently
overwrite — which is exactly what happened in the 2026-08-15 incident. `research/study-results/`
exists so a write-up carries its own evidence instead of pointing at gitignored scratch.

## Resetting the checkout

```bash
make clean-list                      # every clean target, its size, and how to rebuild it
make clean-dry                       # preview; make clean ARGS="--yes" skips the prompts
make clean ARGS="--caches --yes"     # also drop the refetchable network caches
make clean-studies                   # clear backtests/study_output/, keeping each -latest.txt
```

`scripts/clean_generated.py` is the safe list; `scripts/clean_study_output.py` handles study
reports and will not delete one that a tracked `research/*.md` file cites.

## Google Sheets tabs

Two separate workbooks, so the trade record can be shared (or kept unshared) independently of
the flow data.

**`GOOGLE_SPREADSHEET_ID`** — flow, analysis and backtest:

| Tab                   | Written by                                                                    |
| --------------------- | ----------------------------------------------------------------------------- |
| AnalysisClaude        | `scripts/analysis_pipeline` — one MARKET row plus one row per ticker/play per run |
| AnalysisTickerSpecific| `--tickers` runs; same row schema, kept separate                              |
| BaselineDaily         | `build_baseline.py` — one market-aggregate row per trading date; not versioned |
| BacktestResults       | `scripts/backtest` (optional)                                                 |
| BacktestProxy         | `scripts/backtest/proxy.py` — skipped plays, with skip_reason + fallback verdict |
| \_meta                | `sheets_client.py` (dedup hashes)                                             |

The analysis tabs carry per-ticker rollup context (`oi_confirm_pct`, `cpir`, `iv_spread`,
`iv_skew`, `iv_pct`) joined from that date's audit rollup CSV at row-expansion time — these are
deterministic, appended at the end of `ROW_COLUMNS`, and are **not** model-produced.

**`TRADE_JOURNAL_SPREADSHEET_ID`** — the trade record (a *different* spreadsheet):

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
- `site/`, `journal/`, `audit/` and `portfolio/input|output/` are gitignored build output or
  live data. A fresh checkout has none of them; they appear on first run. `backtests/` is
  gitignored too but is **not** all disposable — see the research-tier section above.
- The `.gitignore` rule for the journal is anchored (`/journal/`) on purpose: a bare
  `journal/` would also exclude `scripts/journal/`, the pipeline's own source.
- The `AnalysisGPT` tab still exists in the spreadsheet with historical v3/v4 rows, but the
  `codex` engine that wrote it was retired 2026-08-13 and every reference to it has been
  removed from the code and docs. `claude` is the only registered engine.
