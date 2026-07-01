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

.PHONY: enrich-backfill
enrich-backfill:
	$(PY) scripts/enrich_oi.py --backfill $(ARGS)

# ── iv backfill ────────────────────────────────────────────────────────────────
.PHONY: backfill-iv
backfill-iv:
	$(PY) scripts/backfill_iv.py $(ARGS)

.PHONY: backfill-iv-all
backfill-iv-all:
	$(PY) scripts/backfill_iv.py --backfill $(ARGS)

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

.PHONY: backtest-dry
backtest-dry:
	$(PY) -m scripts.backtest --config config/backtest.yml --dry-run $(ARGS)

# ── baseline ───────────────────────────────────────────────────────────────────
.PHONY: baseline
baseline:
	$(PY) scripts/build_baseline.py $(ARGS)

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
	@echo "  make scrape        scrape flow + unusual activity (live)"
	@echo "  make scrape ARGS=\"--start 2026-02-01 --end 2026-02-28\"  historical range"
	@echo "  make scrape-flow   scrape flow only"
	@echo "  make scrape-unusual scrape unusual only"
	@echo ""
	@echo "  make compile       compile today's snapshots → Drive"
	@echo "  make gc            garbage-collect raw snapshots"
	@echo ""
	@echo "  make enrich        enrich today's compiled flow with OI change + EOD greeks"
	@echo "  make enrich-backfill  enrich all enrichable dates (idempotent)"
	@echo "  make enrich ARGS=\"--date 2026-06-09\"  (or --dry-run, --force)"
	@echo ""
	@echo "  make backfill-iv   backfill counterpart IV legs for today's date"
	@echo "  make backfill-iv-all  backfill counterpart IV legs for all compiled dates"
	@echo "  make backfill-iv ARGS=\"--date 2026-06-26\"  (or --dry-run, --force)"
	@echo ""
	@echo "  make analyze       run analysis pipeline (Claude)"
	@echo "  make analyze-gpt   run analysis pipeline (GPT)"
	@echo "  make analyze ARGS=\"--date 2026-02-14\"  (or --start/--end/--days/--dry-run/--model)"
	@echo ""
	@echo "  make backtest      run backtest"
	@echo "  make backtest-dry  dry-run backtest"
	@echo ""
	@echo "  make baseline      append today's baseline row"
	@echo "  make dashboard     start web dashboard"
	@echo ""
	@echo "  make daily         scrape + compile + analyze (full day)"
	@echo ""
