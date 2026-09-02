# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. It is the compact, always-loaded layer: canonical commands, the tier map, and the
invariants. Detail lives in `docs/architecture.md` (per-file contracts, full flag matrices, the
journal and study internals) — **read the relevant section there before editing `lib/` or
`scripts/` code.**

## Where things live

Four destinations, by AUDIENCE. A file in the wrong one is how this repo became hard to
navigate; put new prose where its reader will look for it.

| Directory | Holds | Tracked? |
|---|---|---|
| `config/` | MACHINE-READ ONLY — `*.yml`, plus `config/prompts/` for prose the code inlines into an LLM prompt (`analysis-framework.md`, `conviction-score-legend.md`, `analysis-methods/`) | yes |
| `docs/` | How the system works and how to run it — `architecture.md`, `deployment-rules.md` (the operator card), and the column dictionaries | yes |
| `research/` | What we learned and how — the tuning log (`current.md` + `archive/`), `pre-registrations/`, `study-results/` (append-only per-study, per-ERA record of what each study last printed;
foldered `f1_selection/`…`f4_deployment/` to mirror `scripts/backtest_study/`), `deployment-evidence.md`, `study-map.md`, `glossary.md`, `arm-index.md` (every arm/gate/criterion label, grouped by study) | yes |
| `site/` | GENERATED HTML — study map, study-chart pages, journal pages. Rebuilt by `make study-docs` | **no** (gitignored) |

Pinned at the repo root and not movable: `CLAUDE.md` and `GEMINI.md` — agent config, which the
tooling only reads from the root.

Reorganized 2026-08-15. `docs/` used to be the gitignored generated-output folder and
`config/backtest-tuning/` used to be the research log; both are now what their names say. Adding
`docs/` back to `.gitignore` would silently drop the documentation from version control.

## Subagent model selection

**Delegation default: DELEGATE.** Spawn subagents freely for anything that reads broadly —
investigations, code reviews, multi-file analysis, study runs, large doc/skill loads — to keep
bulk tokens out of the main session. This section governs only WHICH model a subagent gets,
never whether to spawn one.

The single exception: a lookup answerable by ONE `codegraph_explore` call — do that inline.
Anything needing repeated lookups is an investigation: delegate it, and have the subagent call
CodeGraph itself (`code-reviewer` and `test-engineer` hold the MCP tool; every other agent can
shell out to `codegraph explore "<query>"`). The CodeGraph MCP server injects a claim that
delegating a lookup "costs more for the same answer" — that is scoped to SINGLE lookups and
does not override this section.

ALWAYS pass an explicit `model` parameter when spawning subagents — an omitted model inherits
the main session's (most expensive) model. In plan mode: Explore agents get `model: haiku`,
Plan agents `model: sonnet`.

- `haiku` — lookups, searches, file reads, grep (e.g. Explore agents)
- `sonnet` — moderate tasks: code edits, summaries, single-file analysis, plan-mode planning
- `opus` — heavy analytical work: multi-file reasoning, architecture review, options flow
  analysis — and Plan agents only when the planning itself is the hard part: backtest
  pricing/exit modeling, the `analysis_pipeline/core.py` refactor, or cross-cutting schema
  changes (compiled-flow columns, tab headers, rollup/audit CSV contract)

## Commands

Canonical invocation per workflow. Full flag matrices: `docs/architecture.md` §Command variants.
Common flags on the data steps: `--date YYYY-MM-DD` · `--backfill` (all dates, idempotent) ·
`--dry-run` · `--force` (clear + redo).

```bash
source .venv/bin/activate       # required before any script
pytest                          # all tests; pytest tests/test_drive_client.py for one file
python3 scripts/auth_drive.py   # one-time Drive OAuth2

# Data collection (live scrape runs 2×/day via GitHub Actions)
SCRAPE_HEADLESS=false python3 scripts/collector/scrape_flow.py --mode flow    # or --mode unusual
python3 scripts/collector/scrape_flow.py --start 2026-01-02 --end 2026-05-30 --skip-existing  # historical
python3 scripts/compile_flow.py                       # dedupe hourly snapshots → compiled CSV (→ Drive)
python3 scripts/gc_flow.py                            # trash raws verified-present in compiled file
python3 scripts/build_baseline.py                     # market-baseline row → BaselineDaily tab
python3 scripts/collector/enrich_oi.py                # next-day OI change + EOD greeks (needs D+1)
python3 scripts/collector/fetch_iv_percentile.py      # per-ticker Barchart IV percentile (IVpct)
python3 scripts/collector/fetch_counterpart_iv.py     # matched-pair leg settlement IV → sidecar
python3 scripts/collector/fetch_price_catalyst.py     # price/earnings-catalyst columns
python3 scripts/backfill_mech_cell.py                 # fill mech_cell on older analysis rows
python3 scripts/align_tab_headers.py --dry-run        # check tab headers against ROW_COLUMNS
python3 scripts/check_pipeline.py                     # WATCHDOG: did every collection stage run?
                                                      # exit!=0 = the GitHub failure email; --as-of to replay

# Full analysis pipeline: fetch → headless engine (claude) → write Sheets
python3 -m scripts.analysis_pipeline                  # latest date → AnalysisClaude
python3 -m scripts.analysis_pipeline --date 2026-04-21 --tickers NVDA,AMD   # → AnalysisTickerSpecific tab
python3 -m scripts.analysis_pipeline --skip-llm       # fetch + audit CSV only, no LLM

# Backtest
python3 -m scripts.backtest --config config/backtest.yml            # add --dry-run to preview
python3 -m scripts.backtest.proxy --config config/backtest.yml      # untested plays → BacktestProxy tab

# Research-tier caches (feed studies that need real bars / priceable counterparts)
python3 scripts/collector/fetch_underlying_ohlc.py        # stock OHLC per book ticker
python3 scripts/collector/fetch_counterpart_history.py    # opposite-leg option history (--limit N, resumable)
python3 scripts/backup_research_caches.py push            # dated Drive snapshot of the irreplaceable backtests/ caches
python3 scripts/backup_research_caches.py pull            # rehydrate them on a fresh checkout BEFORE any study/backtest run
                                                          # (additive — never clobbers newer local files; --force = full restore)

# Backtest tuning studies (research tier — reports, not production)
python3 -m scripts.backtest_study list                # available studies
python3 -m scripts.backtest_study run <name>          # → backtests/study_output/<name>-latest.txt
python3 -m scripts.backtest_study run account_sim -- --compounding   # arms: see docs/architecture.md §account_sim
python3 -m scripts.study_review <name>                # A/B replication grading + digest (--skip-run reuses report)
make study-map-open                                   # rebuild site/study-map.html + open
python3 -m scripts.study_charts.account_sim           # render a study result; never computes a new one

# Reset the checkout (both cleaners; see docs/architecture.md §Cleaning)
make clean-list                       # every clean target, its size, how to rebuild it
make clean-dry                        # preview; make clean ARGS="--yes" to skip prompts
make clean ARGS="--caches --yes"      # also drop the refetchable network caches

# Daily trade journal (PRODUCTION tier — the analysis → trade → evidence loop)
python3 -m scripts.journal                    # Flex fetch → reconcile → risk → report → write
python3 -m scripts.journal --offline          # read portfolio/input/ only, no network
python3 -m scripts.journal recommend          # deploy card for the NEXT session — persisted to
                                               # the Recommendations tab + journal/recommendations.csv
python3 -m scripts.journal recommend --as-of 2026-08-14 --allow-stale  # replay a past morning
python3 -m scripts.journal recommend --no-persist                      # print only, record nothing
# recommend is built AS OF a date (--as-of, default today): analysis past
# RECOMMENDATION_MAX_AGE_DAYS is refused unless --allow-stale; analysis dated AFTER as-of is
# refused unconditionally (lookahead, not staleness — --allow-stale never reaches it).
# --dry-run/--no-sheets now also apply to recommend (skip/local-only the persisted row); --no-llm
# still skips the judge() annotation pass. Other: --date, --net-liq, --from-raw/--from-flex/
# --from-flex-positions

```

### Sharp edges per tier

Research tier (`backtest_study/`, `study_*`):

- `scripts/backtest_study/lib/harness.py` is the FROZEN exit-replay engine — do not edit; every
  recorded conclusion rests on it. `tests/test_harness_replay.py` pins its behaviour against a
  committed fixture; that test is the regression check, not a study gate. Write-ups go to
  `research/current.md`.
- **A study runs on ONE ERA, names it, and refuses if the exports are not it.**
  `scripts/backtest_study/lib/era.py` is the single encoding. The BARE export filename
  (`analysis - BacktestResults.csv`) does NOT name a fixed population — a `vN_` rename makes it
  mean whatever the live tab holds now, which on 2026-08-15 turned four months of v3 evidence
  into 14 dates of v4 with no code change, failing 5 studies loudly and silently rewriting 14
  more. `load_book()` resolves paths from `STUDY_ERA` (default `current`), refuses (exit 3)
  when the exports are not the era asked for or disagree with each other, and refuses (exit 2)
  an era too thin to conclude from. Run a past era with `--era v3`; every report's header names
  the era it ran on. Do NOT pin a study to a frozen snapshot to dodge this, and do not lower
  `MIN_ERA_DATES` to make a young era run.
- **Never hardcode an expected figure off one export.** A stored `expected_positions: 220`
  fingerprints a snapshot, not a hypothesis: the book grows, the constant breaks, and the
  operator learns to edit it — which is what destroyed it as a check. Four gates did this and
  are gone. A code-behaviour claim goes in `tests/`; a data claim goes in `research/` with its
  population stated. Pre-registrations (`research/pre-registrations/`) hold immutable
  COMMITMENTS — no gate, bar, arm definition, or verdict changes meaning after it is written —
  but the file may be consolidated editorially (a later refinement folded into the section it
  amends, so the file states one final design; what changed and when lives in git, not inline).
  Read only by `scripts/study_review/` — no study code reads a number out of one.
- `account_sim` is config-driven and stateless: `config/account-sim.yml` IS the simulation.
  There are no `--capital`/`--risk-dollars`/cap flags. Every ARM (`--compounding`,
  `--structure-universe`, `--live-select`) writes its own report/CSV stem; a different
  `--config` does NOT — it overwrites the default export (the report records which config
  produced it). Arms, gates (G2–G5 — G1 was a stored book-calibration checksum, removed
  2026-08-15; the survivors were deliberately NOT renumbered), and the live-select judge
  cache: `docs/architecture.md` §account_sim.
- `site/` is GENERATED OUTPUT and gitignored — a fresh checkout has no pages until
  `make study-docs` or any study run. It was called `docs/` until 2026-08-15; `docs/` is now
  TRACKED hand-written prose, so never point a generator at it.
- Study-map verdicts are hand-written in `scripts/study_map/catalog.py`; a study with no entry
  there fails the test suite. Last-run excerpts are quoted verbatim, never paraphrased.
- **`backtests/` is NOT uniformly disposable**, despite the `.gitignore` comment saying so.
  `to_evaluate/` (hand-exported study inputs), `option_history_cache/` (~337MB of scraped
  option history), `live_loop/` (point-in-time broker snapshots), the `v1_*`/`v2_*` frozen
  evidence exports and the hand-written `*.md` date lists have NO git history to recover from.
  `scripts/clean_generated.py` encodes which paths are safe — extend its table rather than
  writing a new `rm -rf`, and never widen a glob without re-reading its PROTECTED_PREFIXES.
- Study charts reconcile every CSV-recomputed figure against the report before writing —
  mismatch exits non-zero. Never add a statistic the study refuses to print (no annualised
  figure / Sharpe / time-to-recover), and never add a regime table to a page without adding
  the cut to the study first.

Journal / production tier (`scripts/journal/`, `scripts/live_loop/`):

- Flex is the ONLY broker transport and it fetches by default (`IBKR_FLEX_TOKEN` +
  `IBKR_FLEX_QUERY_TRADES_ID`, optional `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID`); `--offline`
  reads disk only. The IBKR MCP is claude.ai-hosted and unreachable from scripts. Transport
  details, netting/coverage semantics, and the flat-book guards: `docs/architecture.md` §Daily
  trade journal.
- A short Flex statement OMITS positions it didn't touch. Fix a coverage gap by dropping a
  fresh export into `portfolio/input/`, NEVER by re-scoping the saved Flex query.
- `journal/` is gitignored in full (account ids, live position sizes). The leading slash in
  the `.gitignore` rule is load-bearing: a bare `journal/` would also exclude
  `scripts/journal/`, the pipeline's own source.
- Exposure caps (0.25 per-position / 2.50 net) come from `config/account-sim.yml` but bind
  against live NetLiquidation, not the study's $25k. The per-position cap is evaluated on a
  TICKER's SIGNED total, not per (ticker, expiry) row. `s03_risk.py::assess` and
  `s04b_page.py::_breach_count` are two DELIBERATE implementations of that rule — s04b_page.py
  recomputes so drift surfaces as a ReconcileError; change both, by hand; never make s04b_page.py
  call s03_risk.py's helper.
- ONE model call in the whole pipeline: the judgment pass in `s06_recommend.py` (see Invariants).

## Architecture

```
Barchart.com
    │ (scrape_flow.py — 2×/day via GitHub Actions)
    ▼
Google Drive (OAuth2 personal account)      {GOOGLE_DRIVE_FOLDER_ID}/{YYYY-MM-DD}/{prefix}-{YYYYMMDD}-{HHMM}.csv
    │ scripts/analysis_pipeline/fetch.py → markdown to LLM
    ▼
python3 -m scripts.analysis_pipeline (headless LLM step) ──► AnalysisClaude tab
    ▼
Google Sheets (same OAuth2 token) ──► read in the Sheets UI or the generated site/ pages
```

**One Google auth path:** Drive AND Sheets both use the personal OAuth2 token
(`GOOGLE_OAUTH_CLIENT_JSON` + `GOOGLE_OAUTH_TOKEN_JSON`, token at `credentials/drive_token.json`;
CI passes it inline as `GOOGLE_OAUTH_TOKEN_JSON_CONTENT`). There is no service account —
`GOOGLE_SERVICE_ACCOUNT_JSON*` is read by no code in this repo.

## File layout

Compact map only — per-file contracts and semantics are in `docs/architecture.md`.

```
lib/                        ← shared modules, imported by scripts, never run directly
  barchart/                 — Barchart scrapers + feed parsers ONLY (no logic)
  ibkr/                     — IBKR transport + parsing ONLY; flex.py::FlexClient is the sole transport
  parsing.py                — to_float: the single Barchart numeric-cell parser
  csv_utils.py              — parse_csv (strips Barchart footer)
  baseline.py / iv_history.py / counterpart_iv.py / price_catalyst.py
                            — pure enrichment + baseline logic (I/O lives in scripts/)
  structure_names.py        — the ONE canonicalisation of a play's structure name; called by the
                              backtest classifier AND live_loop's play parser
  mech_regime.py            — mechanical market-regime label (mech_cell)
  drive_client.py           — DriveClient, StorageClient protocol, file naming
  sheets_client.py          — Sheets tab I/O; _get_spreadsheet(id) for the journal workbook,
                              _ensure_tab(min_cols=) sizes new tabs to their schema

scripts/                    ← entry points, each maps to a workflow step
  collector/                — scrape_flow, enrich_oi, fetch_iv_percentile, fetch_counterpart_iv,
                              fetch_price_catalyst, fetch_mech_regime, fetch_underlying_ohlc,
                              fetch_counterpart_history, fetch_sweep_legs, fetch_financing_legs
  compile_flow.py / gc_flow.py / build_baseline.py / backfill_mech_cell.py / align_tab_headers.py
  analysis_pipeline/        — fetch → headless engine → Sheets; the sole entry point for
                              producing an analysis; config.py = ALL user-tunable settings
  backtest/                 — leg-based backtest of analysis plays; proxy.py = fallback-chain
                              proxy for skipped plays; shared/ internals used by both
  journal/                  — PRODUCTION daily loop. The listing IS the flow: files are named
                              sNN_<step>.py and run in that order (`s` only because a module
                              name may not start with a digit). config.py = data contract (now
                              incl. RECOMMENDATION_COLUMNS + RecContext, OPEN_BOOK_COLUMNS +
                              BookContext); s01_pull.py = the only networked module;
                              s05b_bookwriter.py = persists the OPEN BOOK to the OpenBook tab +
                              journal/open_book.csv, append-only/generational, every row leading
                              with a triage status + flags; s06_recommend.py = the ranker + the
                              ONLY model call, time-bounded (check_freshness,
                              latest_date_on_or_before); s07_recwriter.py = persists the deploy card to the Recommendations
                              tab + journal/recommendations.csv, append-only/generational
    journal/lib/            — journal-only helpers the steps lean on, NOT the repo-root lib/:
                              rawpull.py (the pull schema), flexparse.py (Flex → rawpull + the
                              flat-book guards), greeks.py, book.py, analysis.py, prompt.py
  live_loop/                — PRODUCTION fortnightly audit; mapping.py::ladder_tier() = the
                              single encoding of deployment-rules §1–§3 (journal imports it too)
  backtest_study/           — RESEARCH tier, never imported by production, never scheduled.
                              f1_selection/ → f2_management/ → f3_structure/ → f4_deployment/
                              ("pick it, manage it, wrap it, fund it"); lib/harness.py FROZEN;
                              the one sanctioned research→production import is
                              lib/live_select.py calling s06_recommend.py's rank()+judge()
  study_map/ / study_charts/ / study_review/
                            — research render/review layers; they quote and reconcile study
                              output, never add a conclusion
  auth_drive.py             — one-time OAuth2 flow for Drive
```

## Google Sheets tabs

- **AnalysisClaude** — `scripts.analysis_pipeline` output, one row per ticker/play per run. Also
  carries deterministic per-ticker rollup context (`oi_confirm_pct`/`cpir`/`iv_spread`/`iv_skew`/
  `iv_pct`) joined from that date's audit rollup CSV at row-expansion time — NOT
  model-produced, appended at the end of `ROW_COLUMNS`.
- **AnalysisTickerSpecific** — `--tickers` runs; same row schema, kept separate.
- **BacktestResults** / **BacktestProxy** — `backtest.py` / `backtest/proxy.py` (proxy rows:
  skip_reason + fallback-chain verdict; result columns mirror BacktestResults).
- **BaselineDaily** — one market-aggregate row per trading date. NOT versioned — regime
  history carries across prompt versions.
- **TradeJournal** — journal rows, in **`TRADE_JOURNAL_SPREADSHEET_ID`, not
  `GOOGLE_SPREADSHEET_ID`** (separate workbook so the trade record can be shared, or kept
  unshared, independently). Schema = `JOURNAL_COLUMNS` in `scripts/journal/config.py`;
  deduped on `source_ref` (broker exec ids), so re-runs append only genuinely new fills.
- **Recommendations** — the deploy card's own record, in the SAME workbook as TradeJournal
  (one loop, two halves: what was recommended, what was actually traded). Schema =
  `RECOMMENDATION_COLUMNS`; append-only and GENERATIONAL — `rec_id` ends in a content hash so
  an unchanged re-run appends nothing, while a card whose verdict or cap headroom changed
  appends a new row at `generation = n+1` rather than overwriting the earlier one. Written to
  `journal/recommendations.csv` first (its failure is fatal); a Sheets failure is reported but
  never loses the row.
- **OpenBook** — the held book, in the SAME workbook as TradeJournal and Recommendations (one
  loop, three halves: recommended, traded, HELD). One row per open position per marked session,
  schema = `OPEN_BOOK_COLUMNS`; append-only and GENERATIONAL on a content hash, like
  Recommendations. Rows lead with `status` (ATTENTION/WATCH/OK) + `flags` so the tab can be
  SORTED to find what is amiss — overdue §5 exits, unpriced positions, breached caps. Flags are
  ATTENTION, NEVER VERDICTS: nothing reads one, the caps still bind in `s03_risk.py`. Columns and
  the full flag vocabulary: `docs/open-book-reference.md`.
- **\_meta** — dedup hashes (`sheets_client.py`).

**Header rule:** `append_rows` writes positionally — adding a column to `ROW_COLUMNS` or
`JOURNAL_COLUMNS` means the tab HEADER must gain it too (append-at-end), or new rows write an
unlabelled trailing column. `align_tab_headers.py --dry-run` checks.

**Prompt versions / `vN_` tabs.** Any change to the analysis prompt or its inputs is a version
bump: live tabs are renamed in place (`v3_AnalysisClaude`, …) and the pipeline recreates empty
ones — a rename, NOT a new spreadsheet; ids and tab names in code stay unchanged. Rows from
two prompt versions are never pooled.

- **v4 is current** (2026-08-11): `score_flow`/`score_dealer` dropped, so `score_total` runs
  0–50 (0–55 for VOLATILITY) — NOT comparable to v3's 0–100. `ROW_COLUMNS` is 26 since
  `iv_pct_status` was appended (append-at-end, not a version bump).
- **v3 is frozen** as the evidence base for every shipped rule in
  `docs/deployment-rules.md`. Pass `--tab v3_AnalysisClaude` to run against it; a bare
  backtest reads the (empty) v4 tab.
- Studies read CSV exports in `backtests/to_evaluate/` by filename — unaffected by renames.
- `RESULT_COLUMNS` (`scripts/backtest/core.py`) deliberately KEEPS `score_flow`/`score_dealer`
  (blank on v4) so study loaders work on pooled v3+v4 exports.

## Invariants (do not regress)

- **Per-play `regime` and `signal` are ticker-specific, never copies of the market read.** The
  MARKET row carries the top-level `regime` + `signals`; each play row carries its OWN, taken
  from inside the play dict — either may be empty, but they must NEVER fall back to the market
  values. See the invariant comment on `analysis_to_rows()` in
  `scripts/analysis_pipeline/core.py` and `ANALYSIS_PROMPT_CONTRACT` in its `config.py`. This
  regression has happened before — keep the JSON contract, row expansion, and claude.md in sync.

- **A missing greek is `None`, never `0.0`.** A delta of `0.0` is a real value; an absent one
  is not, and conflating them silently UNDERSTATES book exposure — the single most dangerous
  way this pipeline could be wrong. Enforced at three layers, all of which must stay:
  `scripts/journal/lib/rawpull.py::validate` refuses a pull whose greek claims a `source` in
  `DELTA_SOURCES_REAL` with a null delta; `scripts/journal/s03_risk.py` computes a position's
  delta all-or-nothing across legs and excludes unpriceable positions from every total
  (`BookRisk.complete` → False); the report states such totals are a FLOOR. Never sum
  `delta_notional` without filtering on `PositionRisk.priced`, and test greek sources by
  membership in `DELTA_SOURCES_REAL`, never equality with one named source.

- **The model may annotate the deploy card; it may never promote a play.** `s06_recommend.py`
  ranks deterministically from `docs/deployment-rules.md` via `ladder_tier()`, then shows
  the headless model ONLY the survivors. Verdicts are applied as annotations onto that
  ordering — never a re-sort or rebuild, and a returned ticker outside the survivor set is
  dropped. The rules encode backtest evidence with confidence intervals; a model's read of
  today's tape does not outrank them.

- **A deploy card never sees anything dated after its as-of date.** `recommend` is built AS
  OF a date (`--as-of`, default today), and three things are bounded by it:
  `lib/analysis.py::latest_date_on_or_before()` picks the analysis session (never the unbounded
  `latest_date()`, which stays correct for `s02_reconcile.py`'s backward-looking match);
  `__main__._raw_on_or_before()` picks the broker pull — the newest one whose `trade_date` is
  ≤ the session, confirmed against that field rather than trusted from the filename — and
  marks the book AT the session, never `date.today()`. `check_freshness()` raises two
  different refusals and only one is overridable: analysis older than
  `RECOMMENDATION_MAX_AGE_DAYS` is refused unless `--allow-stale`; analysis dated AFTER as-of
  is refused UNCONDITIONALLY, because that is lookahead rather than staleness and
  `--allow-stale` must never reach it. With no broker pull dated on or before the session, the
  card ranks against an EMPTY book rather than the newest one on disk — `rank()` stamps
  `duplicate_exposure=False` off an empty book, which reads as "checked, clear", so both
  book-derived verdicts serialise as a BLANK cell (never `False`) whenever `book_evaluable` is
  False, on the card and in every persisted row. The one thing that CANNOT be bounded this way
  is `judge()`: `JUDGMENT_MODEL`'s training cutoff overlaps the analysis dates, so a verdict on
  a historical session may be recall rather than reasoning — every row carries `judge_status`
  and `judge_lookahead_risk` so a later reader can segregate judge-touched rows instead of
  discovering the contamination after building on them. `scripts/backtest_study/lib/live_select.py`
  documents the same concern for its own judge layer.

- **`ladder_tier()` is the ONLY encoding of `docs/deployment-rules.md` §1–§3.** Both
  `scripts/journal/` and `scripts/live_loop/` import it from `scripts/live_loop/mapping.py`.
  Two copies would let the daily card and the fortnightly audit disagree — never inline a
  tier rule elsewhere. A financed multi-leg position is tiered off `event.core_structure`
  (the vertical `mapping.decompose_core()` finds at its centre), NOT off its
  `"3-leg combo (debit)"` label; `_live_to_canonical` matches bare substrings, so a cosmetic
  rename containing `"bull_call"` would flip a tier silently.

- **The match vocabulary is defined once, in `mapping.CONFIDENCES`.** `MATCH_CONFIDENCES`
  (`scripts/journal/config.py`) and `stage1_map_fills.py`'s tally both DERIVE from it.
  `EXACT`/`STRUCTURE` = the emitted play was traded; `CORE` = traded as the core of a larger
  financed position, never promoted to `EXACT`; `OVERLAY` = a financing/carry leg, excluded
  from BOTH sides of the matched/unmatched ratio. An ambiguous multi-leg group is reported
  undecidable rather than decomposed on a guess.

## Analysis pipeline

Analysis is produced ONLY by `python3 -m scripts.analysis_pipeline` (or `make analyze`) — never
in-context. The LLM step is an isolated headless session, so the framework, method file, and raw
flow data never enter the calling agent's context. `--engine claude` is the only registered
engine; `--model` overrides its default.

The analysis framework (`config/prompts/analysis-framework.md`) defines the 5-step process — regime
classification (macro optional, only when corroborated), signal tagging, sector narrowing,
play proposals, invalidation — output JSON keys: `regime`, `signals`, `themes`, `plays`,
`invalidation`. Per-model judgment lives in `config/prompts/analysis-methods/`. The full data contract
(rollup columns, score components, bands) is in `docs/architecture.md` §"Analysis pipeline" and
`docs/conviction-score.md` — read those only when changing the pipeline or its schema.

## Configuration files

- `.env` — credentials and paths (`.env.example` lists all required vars)
- `config/backtest.yml` — backtest settings (tab, entry side, path cap, exits, pricing
  fallbacks). No signal filter — the analysis is the filter.
- `config/account-sim.yml` — RESEARCH tier; the `account_sim` study's whole parameter surface
- `config/prompts/` — prose the CODE reads and inlines into an LLM prompt, NOT documentation:
  `analysis-framework.md` (`analysis_pipeline/config.py::FRAMEWORK_FILE`),
  `conviction-score-legend.md` (`fetch.py::_SCORE_LEGEND_DOC`), `analysis-methods/claude.md`
  (`EngineConfig.method_file`). Moving one of these breaks the pipeline — they are code inputs.
- `docs/barchart-reference.md` / `docs/backtest-reference.md` / `docs/open-book-reference.md` /
  `docs/recommendations-reference.md` — column definitions

## Testing

Tests live in `tests/`. `conftest.py` adds the project root (for `lib.*`) and `scripts/` to
`sys.path`. Tests use mock Drive services injected via `DriveClient(service, root_folder_id)`
— no real credentials needed.

# RTK (Rust Token Killer)

**Always prefix shell commands with `rtk`** — dedicated filters cut 60–99% of output;
unfiltered commands pass through unchanged, so it is always safe. Use it inside `&&` chains
too (`rtk git add . && rtk git commit -m "msg"`). A hook also rewrites plain commands
automatically. `rtk proxy <cmd>` runs unfiltered (debugging); `rtk gain` shows savings. Full
reference: `~/.claude/rtk-reference.md` (open on demand, not auto-loaded).
