VENV := .venv
PY   := $(VENV)/bin/python3

# ── venv ───────────────────────────────────────────────────────────────────────
.PHONY: venv
venv:
	python3 -m venv $(VENV)
	$(PY) -m pip install -q -r requirements.txt
	@echo "Virtual env ready. All make targets use it automatically."

# ── scrape ─────────────────────────────────────────────────────────────────────
.PHONY: scrape
scrape:
	SCRAPE_HEADLESS=false $(PY) scripts/barchart_scrape.py --mode flow
	SCRAPE_HEADLESS=false $(PY) scripts/barchart_scrape.py --mode unusual

.PHONY: scrape-flow
scrape-flow:
	SCRAPE_HEADLESS=false $(PY) scripts/barchart_scrape.py --mode flow

.PHONY: scrape-unusual
scrape-unusual:
	SCRAPE_HEADLESS=false $(PY) scripts/barchart_scrape.py --mode unusual

# ── compile & gc ───────────────────────────────────────────────────────────────
.PHONY: compile
compile:
	$(PY) scripts/compile_flow.py

.PHONY: gc
gc:
	$(PY) scripts/gc_flow.py

# ── analysis ───────────────────────────────────────────────────────────────────
.PHONY: analyze
analyze:
	$(PY) -m scripts.analysis_pipeline

.PHONY: analyze-gpt
analyze-gpt:
	$(PY) -m scripts.analysis_pipeline --engine codex

# ── backtest ───────────────────────────────────────────────────────────────────
.PHONY: backtest
backtest:
	$(PY) scripts/backtest.py --config config/backtest.yml

.PHONY: backtest-dry
backtest-dry:
	$(PY) scripts/backtest.py --config config/backtest.yml --dry-run

# ── baseline ───────────────────────────────────────────────────────────────────
.PHONY: baseline
baseline:
	$(PY) scripts/build_baseline.py

# ── dashboard ──────────────────────────────────────────────────────────────────
.PHONY: dashboard
dashboard:
	cd web && npm run dev

# ── daily workflow shortcut ────────────────────────────────────────────────────
.PHONY: daily
daily: scrape compile analyze

.PHONY: help
help:
	@echo ""
	@echo "  make venv          create/refresh virtual env"
	@echo ""
	@echo "  make scrape        scrape flow + unusual activity"
	@echo "  make scrape-flow   scrape flow only"
	@echo "  make scrape-unusual scrape unusual only"
	@echo ""
	@echo "  make compile       compile today's snapshots → Drive"
	@echo "  make gc            garbage-collect raw snapshots"
	@echo ""
	@echo "  make analyze       run analysis pipeline (Claude)"
	@echo "  make analyze-gpt   run analysis pipeline (GPT)"
	@echo ""
	@echo "  make backtest      run backtest"
	@echo "  make backtest-dry  dry-run backtest"
	@echo ""
	@echo "  make baseline      append today's baseline row"
	@echo "  make dashboard     start web dashboard"
	@echo ""
	@echo "  make daily         scrape + compile + analyze (full day)"
	@echo ""
