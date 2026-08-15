VENV := .venv
PY   := $(VENV)/bin/python3


# ── scrape ─────────────────────────────────────────────────────────────────────
.PHONY: scrape
scrape:
ifeq ($(strip $(ARGS)),)
	$(PY) scripts/collector/scrape_flow.py --mode flow
	$(PY) scripts/collector/scrape_flow.py --mode unusual
else
	$(PY) scripts/collector/scrape_flow.py $(ARGS)
endif

.PHONY: scrape-flow
scrape-flow:
	$(PY) scripts/collector/scrape_flow.py --mode flow $(ARGS)

.PHONY: scrape-unusual
scrape-unusual:
	$(PY) scripts/collector/scrape_flow.py --mode unusual $(ARGS)

# ── compile & gc ───────────────────────────────────────────────────────────────
.PHONY: compile
compile:
	$(PY) scripts/compile_flow.py $(ARGS)

.PHONY: gc
gc:
	$(PY) scripts/gc_flow.py

# ── enrich ─────────────────────────────────────────────────────────────────────
.PHONY: enrich
enrich:
	$(PY) scripts/collector/enrich_oi.py $(ARGS)

# ── counterpart iv ───────────────────────────────────────────────────────────────
.PHONY: counterpart-iv
counterpart-iv:
	$(PY) scripts/collector/fetch_counterpart_iv.py $(ARGS)


# ── iv percentile ────────────────────────────────────────────────────────────────
.PHONY: iv-percentile
iv-percentile:
	$(PY) scripts/collector/fetch_iv_percentile.py $(ARGS)

# ── both iv enrichments, one after another ──────────────────────────────────────
.PHONY: iv-all
iv-all: counterpart-iv iv-percentile

# ── price catalyst ────────────────────────────────────────────────────────────────
.PHONY: price-catalyst
price-catalyst:
	$(PY) scripts/collector/fetch_price_catalyst.py $(ARGS)

# ── all enrichments: oi + counterpart-iv + iv-percentile + price-catalyst ────────
.PHONY: enrich-all
enrich-all: enrich counterpart-iv iv-percentile price-catalyst

# ── mech regime table ──────────────────────────────────────────────────────────
# SPY/VIX closes behind the BEAR_HE exit override. Refreshed nightly by the
# Compile Flow workflow (yfinance -> Drive); this pulls the current copy down.
# backtest/analyze depend on it so the table can never be silently stale — the
# Python stays offline and pure, the freshness step lives here in make.
.PHONY: mech-regime
mech-regime:
	$(PY) scripts/collector/fetch_mech_regime.py --download

# Fill `mech_cell` on rows written before the column shipped, or while the table
# was stale (NO_DATA). Pure function of the date, so it is safe to re-run; also
# runs nightly after Compile Flow (.github/workflows/backfill-mech-cell.yml).
.PHONY: backfill-mech-cell
backfill-mech-cell: mech-regime
	$(PY) scripts/backfill_mech_cell.py $(ARGS)

# Repair an analysis tab whose header drifted behind config.ROW_COLUMNS (appends
# are positional, so a short header mislabels every column after the gap).
.PHONY: align-headers
align-headers:
	$(PY) scripts/align_tab_headers.py $(ARGS)

# ── analysis ───────────────────────────────────────────────────────────────────
.PHONY: analyze
analyze: 
	$(PY) -m scripts.analysis_pipeline $(ARGS)

.PHONY: analyze-gpt
analyze-gpt: 
	$(PY) -m scripts.analysis_pipeline --engine codex $(ARGS)

# ── analyze then full backtest ───────────────────────────────────────────────────
.PHONY: analyze-bt
analyze-bt: analyze backtest-all

# ── backtest ───────────────────────────────────────────────────────────────────
.PHONY: backtest
backtest: 
	$(PY) -m scripts.backtest --config config/backtest.yml $(ARGS)

.PHONY: backtest-proxy
backtest-proxy: 
	$(PY) -m scripts.backtest.proxy --config config/backtest.yml $(ARGS)

# ── full backtest: real + proxy, then combined chart ────────────────────────────
.PHONY: backtest-all
backtest-all: backtest backtest-proxy
	$(PY) scripts/chart_backtest.py --csv backtests/results.csv --csv backtests/proxy_results.csv

# ── chart ──────────────────────────────────────────────────────────────────────
.PHONY: chart
chart:
	$(PY) scripts/chart_backtest.py $(ARGS)

# ── chart both real + proxy results (no re-run) ─────────────────────────────────
.PHONY: chart-all
chart-all:
	$(PY) scripts/chart_backtest.py --csv backtests/results.csv --csv backtests/proxy_results.csv $(ARGS)

# ── baseline ───────────────────────────────────────────────────────────────────
.PHONY: baseline
baseline:
	$(PY) scripts/build_baseline.py $(ARGS)

# ── backtest tuning studies (research tier) ────────────────────────────────────
# Reports land in backtests/study_output/<name>-latest.txt with a provenance
# header; conclusions go to research/current.md. Never scheduled.
.PHONY: studies
studies:
	$(PY) -m scripts.backtest_study list

.PHONY: study
study:
	$(PY) -m scripts.backtest_study run $(ARGS)

.PHONY: study-all
study-all:
	$(PY) -m scripts.backtest_study run --all $(ARGS)

# ── study map ──────────────────────────────────────────────────────────────────
# The readable one-pager: what each study asks, what it concluded, and what its
# last run printed. `make study` and `make study-review` refresh it themselves,
# so this target is only for a manual rebuild (or after editing catalog.py).
.PHONY: study-map
study-map:
	$(PY) -m scripts.study_map $(ARGS)

.PHONY: study-map-open
study-map-open:
	$(PY) -m scripts.study_map --open

# ── clean study output ─────────────────────────────────────────────────────────
# Clear the study runner's scratch reports. Prompts before deleting, and pins
# any report the tuning log cites or a study's gate greps for (--force to
# override). Default keeps each study's -latest.txt; ARGS="--all" wipes the lot.
.PHONY: clean-studies
clean-studies:
ifeq ($(strip $(ARGS)),)
	$(PY) scripts/clean_study_output.py --keep-latest
else
	$(PY) scripts/clean_study_output.py $(ARGS)
endif

# ── clean everything regenerable ───────────────────────────────────────────────
# Two cleaners, because the two halves have different safety rules:
#   clean_generated.py    logs, site/, chart PNGs, stamped exports, bytecode —
#                         guarded by "never delete a git-tracked file" plus a
#                         protected-tree list (journal/, portfolio/input/,
#                         credentials/, backtests/option_history_cache/,
#                         to_evaluate/, live_loop/).
#   clean_study_output.py backtests/study_output/, which needs its own pin scan
#                         for reports the tuning log cites or a study's gate greps.
# Both prompt before deleting, and both pin files that are cited elsewhere
# (--force drops the pins in either). The shared flags --dry-run/--yes/--force
# in ARGS reach BOTH halves; every other flag goes to clean_generated.py alone,
# so `--caches` never reaches the study cleaner's argparse. Point the study half
# somewhere else with CLEAN_STUDY_ARGS="--all".
#
#   make clean ARGS="--dry-run"        preview both halves
#   make clean ARGS="--yes"            no prompts
#   make clean ARGS="--caches --yes"   also drop the refetchable network caches
#   make clean CLEAN_STUDY_ARGS="--all"  wipe study_output too (still keeps pinned)
CLEAN_STUDY_ARGS ?= --keep-latest
.PHONY: clean
clean:
	$(PY) scripts/clean_generated.py $(ARGS)
	$(PY) scripts/clean_study_output.py $(CLEAN_STUDY_ARGS) \
	  $(filter --dry-run --yes -y --force,$(ARGS))

# What `make clean` would delete, touching nothing.
.PHONY: clean-dry
clean-dry:
	$(MAKE) clean ARGS="--dry-run $(ARGS)"

# Every target and its rebuild command, with current sizes.
.PHONY: clean-list
clean-list:
	$(PY) scripts/clean_generated.py --list

# ── study review ────────────────────────────────────────────────────────────────
# Deterministic two-analyst replication protocol wrapper (headless `claude -p`
# calls, isolated sessions). ARGS="<study> [flags]" — see
# research/replication-protocol.md § Automated invocation.
# The study name defaults to $(STUDY_REVIEW_STUDY) when ARGS starts with a flag
# (or is empty), so `make study-review` and `make study-review ARGS="--skip-run"`
# both work; naming another study in ARGS overrides it.
STUDY_REVIEW_STUDY ?= account_sim
.PHONY: study-review
study-review:
	$(PY) -m scripts.study_review \
	  $(if $(filter-out -%,$(firstword $(ARGS))),,$(STUDY_REVIEW_STUDY)) $(ARGS)

# ── study charts (research tier) ───────────────────────────────────────────────
# Renders a study's EXISTING result as one self-contained HTML page; it never
# computes a new conclusion — every CSV-recomputed figure is reconciled against
# the report, and a mismatch exits non-zero. Run the study FIRST.
# Each run writes TWO files: the scratch HTML FRAGMENT under
# backtests/study_output/ (what the Artifact publisher wants) and the standalone
# site/account-sim-charts.html — generated output, rebuilt by `make study-docs`,
# that opens on a double-click the way site/study-map.html does. ARGS="--no-site"
# writes only the scratch one.
# The report is auto-paired to the positions CSV's arm on BOTH arm axes
# (--structure-universe and --compounding), so chart another arm by pointing
# --positions at its own export. The structure arm writes ONLY the scratch
# fragment: its page reads the same as the frozen book's chart for chart, so a
# second page would just cost a reader a diff. The compounding arm has a page of
# its own (below), and no arm may be written onto another arm's page.
.PHONY: study-chart
study-chart:
	$(PY) -m scripts.study_charts.account_sim $(ARGS)

.PHONY: study-chart-open
study-chart-open:
	$(PY) -m scripts.study_charts.account_sim --standalone --open $(ARGS)

# Fragment only, by design — see the note above. Add ARGS="--standalone --open"
# to look at it.
.PHONY: study-chart-structure
study-chart-structure:
	$(PY) -m scripts.study_charts.account_sim \
	  --positions backtests/study_output/account_sim-positions-structure-latest.csv $(ARGS)

# The regime page: the same account_sim run, re-grouped by the two regime
# readings the book carries. It draws a cut the study does NOT pre-register —
# the study prints that cut itself, flagged, and this reconciles against it.
.PHONY: study-chart-regime
study-chart-regime:
	$(PY) -m scripts.study_charts.regime $(ARGS)

.PHONY: study-chart-regime-open
study-chart-regime-open:
	$(PY) -m scripts.study_charts.regime --standalone --open $(ARGS)

# The compounding arm's own page. That arm is a POST-HOC sensitivity (sizing
# re-marked to realized equity), not the pre-registered book, so it gets a page
# of its own — site/account-sim-compounding.html — and cli.site_dest refuses
# either arm on the other's page. Run the compounding arm of the study first.
.PHONY: study-chart-compounding
study-chart-compounding:
	$(PY) -m scripts.study_charts.compounding $(ARGS)

.PHONY: study-chart-compounding-open
study-chart-compounding-open:
	$(PY) -m scripts.study_charts.compounding --standalone --open $(ARGS)

# Every generated site page in one command: the study map, the account_sim
# readout, the regime breakdown, the compounding arm. None runs a study — they
# only read what the last run left behind. site/ is generated output; this is
# the command that rebuilds it.
.PHONY: study-docs
study-docs:
	$(PY) -m scripts.study_map
	$(PY) -m scripts.study_charts.account_sim
	$(PY) -m scripts.study_charts.regime
	@# The compounding arm is opt-in: skip its page rather than fail the whole
	@# rebuild when that arm has not been run in this checkout.
	@if [ -f backtests/study_output/account_sim-positions-compounding-latest.csv ]; then \
	  $(PY) -m scripts.study_charts.compounding; \
	else \
	  echo "skipped scripts.study_charts.compounding — no compounding arm export yet"; \
	fi

# ── Daily trade journal (PRODUCTION) ─────────────────────────────────────────
# Fetches the Flex statement with IBKR_FLEX_TOKEN — no gateway, no login — and
# nets it TOGETHER with the exports in portfolio/input/: a saved query's period
# is usually far shorter than the life of an open position, and the book is
# netted from fills, so the statement alone would omit every position it did not
# touch. Pass your account equity, which a Flex trades query does not carry:
# without it the exposure caps report "not evaluable" rather than guessing.
#   make journal ARGS="--net-liq 52000"
# `ARGS="--offline"` reads portfolio/input/ only and touches no network.
.PHONY: journal
journal:
	$(PY) -m scripts.journal $(ARGS)

.PHONY: journal-dry
journal-dry:
	$(PY) -m scripts.journal --dry-run $(ARGS)

# Replay a past broker pull with no network — the offline path for every
# downstream step. Pass ARGS="--from-raw journal/raw/ibkr-<date>-<HHMM>.json".
.PHONY: journal-replay
journal-replay:
	$(PY) -m scripts.journal $(ARGS)

# The deploy card for the next session. --no-llm gives the deterministic card alone.
.PHONY: journal-recommend
journal-recommend:
	$(PY) -m scripts.journal recommend $(ARGS)

.PHONY: journal-page-open
journal-page-open:
	$(PY) -m scripts.journal --page-only $(ARGS)
	@open site/journal-latest.html 2>/dev/null || echo "built site/journal-latest.html"

.PHONY: help
help:
	@echo ""
	@echo "  make venv          create/refresh virtual env"
	@echo ""
	@echo "  make scrape        scrape flow + unusual activity (live)"
	@echo "  make scrape ARGS=\"--start 2026-02-01 --end 2026-02-28\"  historical range"
	@echo "  make scrape-flow   scrape flow only"
	@echo "  make scrape-unusual scrape unusual only"
	@echo ""
	@echo "  make compile       compile today's snapshots → Drive"
	@echo "  make compile ARGS=\"--date 2026-06-09\"  (or --start/--end for a range, --dry-run)"
	@echo "  make gc            garbage-collect raw snapshots"
	@echo ""
	@echo "  make enrich        enrich today's compiled flow with OI change + EOD greeks"
	@echo "  make enrich ARGS=\"--date 2026-06-09\"  (or --backfill, --dry-run, --force)"
	@echo ""
	@echo "  make counterpart-iv   fetch counterpart IV legs for today's date"
	@echo "  make counterpart-iv ARGS=\"--date 2026-06-26\"  (or --backfill, --dry-run, --force)"
	@echo ""
	@echo "  make iv-percentile   enrich today's compiled flow with per-ticker IV percentile"
	@echo "  make iv-percentile ARGS=\"--date 2026-06-10\"  (or --backfill, --dry-run, --force)"
	@echo ""
	@echo "  make iv-all        counterpart-iv + iv-percentile, one after another"
	@echo "  make iv-all ARGS=\"--date 2026-06-10\"  (same ARGS passed to both)"
	@echo ""
	@echo "  make price-catalyst   enrich today's compiled flow with price/earnings catalyst data"
	@echo "  make price-catalyst ARGS=\"--date 2026-06-10\"  (or --backfill, --dry-run, --force)"
	@echo ""
	@echo "  make enrich-all    enrich + counterpart-iv + iv-percentile + price-catalyst"
	@echo "  make enrich-all ARGS=\"--date 2026-06-10\"  (same ARGS passed to all four)"
	@echo ""
	@echo "  make analyze       run analysis pipeline (Claude)"
	@echo "  make analyze-gpt   run analysis pipeline (GPT)"
	@echo "  make analyze ARGS=\"--date 2026-02-14\"  (or --start/--end/--days/--dry-run/--model)"
	@echo ""
	@echo "  make analyze-bt    analyze, then backtest-all (real + proxy + chart)"
	@echo "  make analyze-bt ARGS=\"--date 2026-04-21\"  (ARGS passed to analyze and both backtest steps)"
	@echo ""
	@echo "  make mech-regime   pull the SPY/VIX regime table from Drive"
	@echo "  make backfill-mech-cell   fill mech_cell on older analysis rows (add ARGS=\"--dry-run\")"
	@echo "  make align-headers        realign analysis tab headers with ROW_COLUMNS (ARGS=\"--dry-run\")"
	@echo ""
	@echo "  make backtest      run backtest (pulls the regime table first)"
	@echo "  make backtest-dry  dry-run backtest"
	@echo ""
	@echo "  make backtest-proxy   proxy-backtest untested plays → BacktestProxy tab"
	@echo "  make backtest-proxy ARGS=\"--date 2026-04-21\"  (or --dry-run, --cache-only)"
	@echo ""
	@echo "  make backtest-all  backtest + backtest-proxy, then chart the combined results"
	@echo "  make backtest-all ARGS=\"--date 2026-04-21\"  (ARGS passed to both backtest steps)"
	@echo ""
	@echo "  make chart         render backtest charts → backtests/charts/"
	@echo "  make chart ARGS=\"--csv backtests/results.csv --csv backtests/proxy_results.csv\"  combine multiple CSVs"
	@echo ""
	@echo "  make chart-all     chart results.csv + proxy_results.csv together (no re-run)"
	@echo ""
	@echo "  make studies       list available backtest tuning studies"
	@echo "  make study ARGS=\"account_sim\"  run one study → backtests/study_output/<name>-latest.txt"
	@echo "  make study ARGS=\"account_sim --dry-run\"  (also --cache-only, --redo, --date)"
	@echo "  make study-all     run every study with its default args"
	@echo ""
	@echo "  make study-map     rebuild site/study-map.html (what each study asks + its last run)"
	@echo "  make study-map-open  rebuild it and open it in a browser"
	@echo ""
	@echo "  make clean        delete every regenerable file (scratch + study output)"
	@echo "  make clean-dry    preview it, delete nothing"
	@echo "  make clean-list   every clean target, its size, and how to rebuild it"
	@echo "  make clean ARGS=\"--caches --yes\"  also drop the refetchable scrape caches"
	@echo ""
	@echo "  make clean-studies clear backtests/study_output/, keeping each -latest.txt"
	@echo "  make clean-studies ARGS=\"--all\"  wipe it (add --force to drop cited/gate-marked reports, --dry-run to preview)"
	@echo ""
	@echo "  make study-review  run account_sim, then two-analyst replication grading + digest"
	@echo "  make study-review ARGS=\"--skip-run --dry-run\"  reuse existing report, no LLM calls"
	@echo "  make study-review ARGS=\"bear_arm\"  grade another study (see: make studies)"
	@echo ""
	@echo "  make study-chart   render the account_sim result → study_output fragment + site/account-sim-charts.html"
	@echo "  make study-chart-open   same, wrapped as a full page and opened in a browser"
	@echo "  make study-chart-structure  chart the --structure-universe arm's export (fragment only)"
	@echo "  make study-chart-regime  render the deployed book by market regime → site/account-sim-regime.html"
	@echo "  make study-chart-regime-open  same, wrapped as a full page and opened in a browser"
	@echo "  make study-chart-compounding  render the POST-HOC compounding arm → site/account-sim-compounding.html"
	@echo "  make study-chart-compounding-open  same, wrapped as a full page and opened in a browser"
	@echo "  make study-chart ARGS=\"--out /tmp/page.html\"  (also --report, --positions, --capital, --no-site)"
	@echo "  make study-docs    rebuild every generated site page (map + readout + regime + compounding)"
	@echo ""
	@echo "  make baseline      append today's baseline row"
	@echo "  make dashboard     start web dashboard"
	@echo ""
	@echo "  make daily         scrape + compile + analyze (full day)"
	@echo ""
	@echo "  make journal       fetch today's IBKR fills (Flex) → reconcile vs analysis → report + Sheets"
	@echo "  make journal-dry   same, but write nothing (shows the rows it would append)"
	@echo "  make journal ARGS=\"--offline\"  read portfolio/input/ only, no network"
	@echo "  make journal-replay ARGS=\"--from-raw journal/raw/ibkr-<date>-<HHMM>.json\"  offline replay"
	@echo "  make journal-recommend  deploy card for the next session (add ARGS=\"--no-llm\")"
	@echo "  make journal-page-open  rebuild site/journal-latest.html and open it"
	@echo ""
