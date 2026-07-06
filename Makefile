VENV := .venv
PY   := $(VENV)/bin/python3


# ── scrape ─────────────────────────────────────────────────────────────────────
.PHONY: scrape
scrape:
ifeq ($(strip $(ARGS)),)
	$(PY) scripts/barchart_scrape.py --mode flow
	$(PY) scripts/barchart_scrape.py --mode unusual
else
	$(PY) scripts/barchart_scrape.py $(ARGS)
endif

.PHONY: scrape-flow
scrape-flow:
	$(PY) scripts/barchart_scrape.py --mode flow $(ARGS)

.PHONY: scrape-unusual
scrape-unusual:
	$(PY) scripts/barchart_scrape.py --mode unusual $(ARGS)

# ── compile & gc ───────────────────────────────────────────────────────────────
.PHONY: compile
compile:
	$(PY) scripts/compile_flow.py

.PHONY: gc
gc:
	$(PY) scripts/gc_flow.py

# ── enrich ─────────────────────────────────────────────────────────────────────
.PHONY: enrich
enrich:
	$(PY) scripts/enrich_oi.py $(ARGS)

# ── counterpart iv ───────────────────────────────────────────────────────────────
.PHONY: counterpart-iv
counterpart-iv:
	$(PY) scripts/fetch_counterpart_iv.py $(ARGS)


# ── iv percentile ────────────────────────────────────────────────────────────────
.PHONY: iv-percentile
iv-percentile:
	$(PY) scripts/fetch_iv_percentile.py $(ARGS)

# ── both iv enrichments, one after another ──────────────────────────────────────
.PHONY: iv-all
iv-all: counterpart-iv iv-percentile

# ── analysis ───────────────────────────────────────────────────────────────────
.PHONY: analyze
analyze:
	$(PY) -m scripts.analysis_pipeline $(ARGS)

.PHONY: analyze-gpt
analyze-gpt:
	$(PY) -m scripts.analysis_pipeline --engine codex $(ARGS)

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

# ── baseline ───────────────────────────────────────────────────────────────────
.PHONY: baseline
baseline:
	$(PY) scripts/build_baseline.py $(ARGS)

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
	@echo "  make analyze       run analysis pipeline (Claude)"
	@echo "  make analyze-gpt   run analysis pipeline (GPT)"
	@echo "  make analyze ARGS=\"--date 2026-02-14\"  (or --start/--end/--days/--dry-run/--model)"
	@echo ""
	@echo "  make backtest      run backtest"
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
	@echo "  make baseline      append today's baseline row"
	@echo "  make dashboard     start web dashboard"
	@echo ""
	@echo "  make daily         scrape + compile + analyze (full day)"
	@echo ""
