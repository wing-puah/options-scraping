# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. It is the compact, always-loaded layer: canonical commands, the tier map, and one
line per invariant. Detail lives in `docs/architecture.md`. Its last section, §Agent rules in
full, holds the complete text, the reasons and the incidents behind every rule below. **Read the
relevant section there before editing `lib/` or `scripts/` code.**

## Where things live

Put new prose where its reader will look for it.

| Directory | Holds | Tracked? |
|---|---|---|
| `config/` | MACHINE-READ ONLY: `*.yml`, plus `config/prompts/` (prose the code inlines into an LLM prompt) | yes |
| `docs/` | How the system works and how to run it: `architecture.md`, `deployment-rules.md` (the operator card), the column dictionaries | yes |
| `research/` | What we learned: `current.md` + `archive/` (tuning log), `lessons.md` (rewritten weekly by the dream; read before writing a lesson), `pre-registrations/`, `study-results/` (append-only, per study and era), `deployment-evidence.md`, `study-map.md`, `glossary.md`, `arm-index.md`. **Prose follows `research/writing-guide.md`**; `make check-doc-links` (run by pytest) and `scripts/check_prose.py` (a PostToolUse hook, or `make check-prose`) enforce it | yes |
| `dreams/` | The weekly dream's proposals, one folder per date. Not doctrine until `dream adopt` copies it in; manifest is `DREAM.md` | yes (digests and findings are not) |
| `site/` | GENERATED HTML, rebuilt by `make study-docs`. Never point a generator at `docs/` | **no** |

`CLAUDE.md` and `GEMINI.md` are pinned at the root. Never add `docs/` to `.gitignore`.

## Subagent model selection

**Delegation default: DELEGATE.** Spawn subagents freely for anything that reads broadly
(investigations, reviews, multi-file analysis, study runs, large doc loads). The one exception: a
lookup answerable by ONE `codegraph_explore` call is done inline. Anything needing repeated
lookups is delegated, and the subagent calls CodeGraph itself (`code-reviewer` and
`test-engineer` hold the MCP tool; others shell out to `codegraph explore "<query>"`). The
CodeGraph server's "delegating costs more" claim covers single lookups only.

ALWAYS pass an explicit `model` (an omitted one inherits the main session's). Plan mode: Explore
gets `haiku`, Plan gets `sonnet`.
- `haiku`: lookups, searches, file reads, grep
- `sonnet`: code edits, summaries, single-file analysis, plan-mode planning
- `opus`: multi-file reasoning, architecture review, options-flow analysis, and Plan agents when
  planning is the hard part (backtest pricing/exits, the `analysis_pipeline/core.py` refactor,
  cross-cutting schema changes)

## Commands

Notes on each: §Agent rules in full → Commands, with notes. Full flag matrices: §Command variants.
Common data-step flags: `--date YYYY-MM-DD` · `--backfill` · `--dry-run` · `--force`.

```bash
source .venv/bin/activate                     # required before any script
pytest                                        # all tests
python3 scripts/auth_drive.py                 # one-time Drive OAuth2

# Data collection (Actions: flow-pacemaker.yml; scrape.yml is the backup)
make pacemaker                                # laptop twin when Actions is down (DRY=1 previews)
python3 scripts/collector/daily/scrape_flow.py --mode flow   # or --mode unusual
python3 scripts/compile_flow.py               # hourly snapshots -> compiled CSV
python3 scripts/gc_flow.py                    # trash raws already in the compiled file
python3 scripts/build_baseline.py             # BaselineDaily row
python3 scripts/collector/daily/{enrich_oi,fetch_iv_percentile,fetch_counterpart_iv,fetch_price_catalyst}.py
python3 scripts/regime_watch.py               # daily report, changes nothing
python3 scripts/align_tab_headers.py --dry-run
python3 scripts/check_pipeline.py             # WATCHDOG: did every stage run?

# Analysis: fetch -> headless engine -> Sheets
python3 -m scripts.analysis_pipeline          # latest date -> AnalysisClaude
python3 -m scripts.analysis_pipeline --date D --tickers NVDA,AMD   # -> AnalysisTickerSpecific
python3 -m scripts.analysis_pipeline --skip-llm

# Backtest (idempotent; --redo deletes and re-simulates, needs a date bound)
python3 -m scripts.backtest --config config/backtest.yml
python3 -m scripts.backtest.proxy --config config/backtest.yml

# Research caches and studies
python3 scripts/backup_research_caches.py push|pull   # pull BEFORE any study on a fresh checkout
python3 scripts/export_tabs.py                # Sheets tabs -> backtests/to_evaluate/
python3 -m scripts.backtest_study list|run <name>
python3 -m scripts.study_review <name>
make dashboard                                # site/dashboard.html

# Cleaning (see §Cleaning)
make clean-list ; make clean-dry ; make clean ARGS="--yes"

# Production loop and journal
make daily-loop                               # regime -> backtest+proxy -> journal -> recommend -> backup
python3 -m scripts.journal                    # Flex fetch -> reconcile -> risk -> report -> write
python3 -m scripts.journal --offline|--quiet
python3 -m scripts.journal recommend          # deploy card for the next session (--as-of D)
```

### Sharp edges per tier

Full text: §Agent rules in full → Sharp edges per tier.

Research tier (`backtest_study/`, `study_*`):
- `scripts/backtest_study/lib/harness.py` is FROZEN; `tests/test_harness_replay.py` pins it.
- A study runs on ONE era (`lib/era.py`, `STUDY_ERA`), names it, and refuses a mismatched
  export. Never pin to a snapshot or lower `MIN_ERA_DATES` to dodge it.
- Never hardcode an expected figure off one export. Code claims go in `tests/`, data claims in
  `research/`. Pre-registrations are immutable in substance; build-time rulings are folded in
  as `Resolved at build (date)`, never a separate errata file.
- `account_sim` is config-driven (`config/account-sim.yml`); a different `--config` overwrites
  the default export.
- Study-map verdicts live in `scripts/study_map/catalog.py`; last-run excerpts are quoted
  verbatim, never paraphrased.
- **`backtests/` is NOT disposable**: `to_evaluate/`, the option-history and OHLC caches,
  `live_loop/` and the frozen exports have no git history. Use `scripts/clean_generated.py`,
  never a new `rm -rf`. Run `backup_research_caches.py push` after every scrape.
- Study charts reconcile against the report and never add a statistic the study refuses to print.
- `lib/mtm_curve.py` and `account_sim.equity_curve` are two INDEPENDENT implementations on
  purpose; one must never call the other, and the tolerance is never widened.

Journal / production tier (`scripts/journal/`):
- Flex is the ONLY broker transport. Fix a coverage gap by dropping an export into
  `portfolio/input/`, never by re-scoping the Flex query.
- `/journal/` is gitignored in full (account ids, positions). The leading slash is
  load-bearing. Nothing from it may enter a tracked fixture.
- Exposure caps bind on a ticker's signed total against live NetLiquidation;
  `s03_risk.py::assess` and `s04b_page.py::_breach_count` are deliberate twins. Change both by hand.
- ONE model call in the pipeline: `judge()` in `s06_recommend.py`.
- `JOURNAL_DRIVE_FOLDER_ID` is the journal's own private folder, never `GOOGLE_DRIVE_FOLDER_ID`.
  Its archives round-trip (pull before, push after). `--quiet` refuses to run without it.

## Architecture

```
Barchart.com --(scrape_flow.py, paced by GitHub Actions)--> Google Drive {GOOGLE_DRIVE_FOLDER_ID}/{date}/
  --(analysis_pipeline/fetch.py -> headless LLM)--> AnalysisClaude tab --> Sheets UI / site/ pages
```

**One Google auth path:** Drive and Sheets both use the personal OAuth2 token
(`credentials/drive_token.json`; CI passes `GOOGLE_OAUTH_TOKEN_JSON_CONTENT`). There is no
service account. File layout: `docs/architecture.md` §File layout (detailed).

## Google Sheets tabs

Full descriptions: §Agent rules in full → Google Sheets tabs.
- `AnalysisClaude`, `AnalysisTickerSpecific`, `BacktestResults`, `BacktestProxy`,
  `BaselineDaily` (not versioned), `_meta`.
- `TradeJournal`, `Recommendations` (append-only, generational) and `OpenBook` (a MIRROR,
  replaced each run) live in `TRADE_JOURNAL_SPREADSHEET_ID`, not `GOOGLE_SPREADSHEET_ID`.
- **Header rule:** `append_rows` writes positionally. A new column in `ROW_COLUMNS` or
  `JOURNAL_COLUMNS` must be appended to the tab header too; a mismatch raises `HeaderMismatch`.
- **Prompt versions:** a prompt or input change renames live tabs to `vN_*`; versions are never
  pooled. v4 is current (`score_total` 0–50, not comparable to v3). v3 is frozen as the evidence
  for `docs/deployment-rules.md`.

## Invariants (do not regress)

Full text with incidents: §Agent rules in full → Invariants.
- **Per-play `regime` and `signal` are ticker-specific**, never copies of the MARKET row's.
- **An analysis is written ONCE per date** (`_drop_already_analysed`). Delete the unwanted
  run's rows by `created_datetime` rather than using `--allow-duplicate-date`.
- **A play is backtested ONCE per results tab**, keyed by the single
  `scripts/backtest/shared/identity.py`. `core.py` never imports `proxy.py`.
- **A missing greek is `None`, never `0.0`.** Never sum `delta_notional` without filtering on
  `PositionRisk.priced`; test sources by membership in `DELTA_SOURCES_REAL`.
- **The model may annotate the deploy card; it may never promote a play.**
- **A deploy card never sees anything dated after its as-of date.** `--allow-stale` never
  overrides lookahead.
- **`ladder_tier()` (`scripts/journal/lib/mapping.py`) is the ONLY encoding of
  `docs/deployment-rules.md` §1–§3.** Never inline a tier rule elsewhere.
- **The match vocabulary is defined once, in `mapping.CONFIDENCES`.**

## Analysis pipeline

Analysis is produced ONLY by `python3 -m scripts.analysis_pipeline` (or `make analyze`), never
in-context. The LLM step is an isolated headless session. The framework
(`config/prompts/analysis-framework.md`) outputs `regime`, `signals`, `themes`, `plays`,
`invalidation`; per-model judgment is in `config/prompts/analysis-methods/`. Data contract:
`docs/architecture.md` §"Analysis pipeline" and `docs/conviction-score.md`.

## Configuration files

- `.env`: credentials and paths (`.env.example` lists them)
- `config/backtest.yml`: backtest settings. `config/account-sim.yml`: the `account_sim` study.
- `config/prompts/`: code inputs, not documentation. Moving one breaks the pipeline.
- `docs/*-reference.md`: column definitions

## Testing

Tests live in `tests/`. `conftest.py` puts the root and `scripts/` on `sys.path`. Drive is mocked
via `DriveClient(service, root_folder_id)`; no credentials needed.
