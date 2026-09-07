"""The already-analysed guard — `scripts.analysis_pipeline` refuses a date the
target tab already holds, unless `--allow-duplicate-date` is passed.

The invariant under test: a second run on an analysed date must not append. The
tab has no upsert and no undo, and two runs of a non-deterministic LLM propose
DIFFERENT plays rather than copies — so the result is not a duplicate that can
be deduped later, it is two populations pooled into one, reaching every study
that loads the export. That happened on 2024-09-16, 2025-09-10 and 2025-09-18
before this guard existed; on 2025-09-18 the two runs disagreed about the
MARKET regime itself.

The second half of the guard matters as much as the first: it must not FIRE on
a genuinely new date, or the daily pipeline stops working.
"""
import pytest

from analysis_pipeline import core


_ANALYSIS = {
    "regime": "BULL — dealers short gamma",
    "signals": ["[FLOW] call sweeps in semis"],
    "plays": [
        {"ticker": "NVDA", "asset_class": "stock", "flow_intent": "directional",
         "pattern": "call sweep", "structure": "bull call spread 120/130",
         "thesis": "momentum", "trigger": "break 118", "invalidation": "close < 112",
         "horizon": "2-4 weeks", "regime": "BULL", "signal": "[FLOW] sweeps"},
    ],
}

# What the tab already holds: one full analysis of 2026-06-01.
_TAB_ROWS = [
    {"date": "2026-06-01", "ticker": "MARKET", "created_datetime": "2026-06-02 09:00:00"},
    {"date": "2026-06-01", "ticker": "NVDA", "created_datetime": "2026-06-02 09:00:00"},
    {"date": "2026-05-29", "ticker": "MARKET", "created_datetime": "2026-05-30 09:00:00"},
]


@pytest.fixture
def pipeline(monkeypatch):
    """Stub every side-effecting edge of ``core.main``; record appends and reads."""
    monkeypatch.setattr(core, "get_drive_client", lambda: object())
    monkeypatch.setattr(core, "fetch_data", lambda **kw: "## stocks-flow\n\nmarkdown\n")
    monkeypatch.setattr(core, "_compute_play_scores", lambda analysis, d: {})
    monkeypatch.setattr(core, "_load_rollup_metrics", lambda p: {})
    monkeypatch.setattr(core, "_mech_cell", lambda d: "NEUTRAL")
    monkeypatch.setattr(core, "run_engine",
                        lambda engine, prompt, model: (_ANALYSIS, "{}"))

    seen = {"appended": [], "read_tabs": []}

    def fake_get_all_rows(tab, spreadsheet_id=None):
        seen["read_tabs"].append(tab)
        return list(_TAB_ROWS)

    def fake_append_rows(tab, rows, *a, **kw):
        seen["appended"].append((tab, len(rows)))

    monkeypatch.setattr(core.sheets_client, "get_all_rows", fake_get_all_rows)
    monkeypatch.setattr(core.sheets_client, "append_rows", fake_append_rows)
    return seen


# ── 1. The refusal ─────────────────────────────────────────────────────────────

def test_analysed_date_is_refused_and_nothing_is_appended(pipeline):
    with pytest.raises(SystemExit) as exc:
        core.main(["--date", "2026-06-01"])
    assert exc.value.code == 1
    assert pipeline["appended"] == []


def test_refusal_happens_before_the_llm_call(pipeline, monkeypatch):
    """The guard is worthless if it costs an LLM run to reach it."""
    def explode(*a, **kw):
        raise AssertionError("run_engine must not be reached for a refused date")

    monkeypatch.setattr(core, "run_engine", explode)
    monkeypatch.setattr(core, "fetch_data", explode)
    with pytest.raises(SystemExit):
        core.main(["--date", "2026-06-01"])


def test_range_runs_the_new_dates_and_refuses_only_the_analysed_one(pipeline):
    core.main(["--start", "2026-06-01", "--end", "2026-06-03"])
    # 06-01 is on the tab; 06-02 and 06-03 are new and each append their rows.
    assert len(pipeline["appended"]) == 2
    assert {t for t, _ in pipeline["appended"]} == {"AnalysisClaude"}


# ── 2. It must not fire on a new date ──────────────────────────────────────────

def test_unanalysed_date_runs_normally(pipeline):
    core.main(["--date", "2026-06-05"])
    assert len(pipeline["appended"]) == 1


def test_the_tab_is_read_once_not_once_per_date(pipeline):
    core.main(["--start", "2026-06-02", "--end", "2026-06-05"])
    assert pipeline["read_tabs"] == ["AnalysisClaude"]


# ── 3. The override ────────────────────────────────────────────────────────────

def test_allow_duplicate_date_appends_anyway(pipeline):
    core.main(["--date", "2026-06-01", "--allow-duplicate-date"])
    assert pipeline["appended"] == [("AnalysisClaude", 2)]


# ── 4. Runs that cannot write are not gated ────────────────────────────────────

def test_output_dir_run_never_reads_the_tab(pipeline, tmp_path):
    """A prompt-evaluation run never reaches append_rows, so it needs no guard —
    and must not demand Sheets credentials to be told about a tab it won't touch."""
    core.main(["--date", "2026-06-01", "--output-dir", str(tmp_path / "run")])
    assert pipeline["read_tabs"] == []
    assert pipeline["appended"] == []


def test_skip_llm_run_never_reads_the_tab(pipeline):
    core.main(["--date", "2026-06-01", "--skip-llm"])
    assert pipeline["read_tabs"] == []


def test_dry_run_warns_but_still_runs(pipeline, caplog):
    """--dry-run writes nothing, so it cannot double anything — but the warning
    lands before the LLM call rather than after it."""
    with caplog.at_level("WARNING", logger="analysis_pipeline"):
        core.main(["--date", "2026-06-01", "--dry-run"])
    assert pipeline["appended"] == []
    assert any("ALREADY holds rows" in r.getMessage() for r in caplog.records)


# ── 5. Ticker-focused runs are keyed on (date, ticker) ─────────────────────────

def test_ticker_run_is_refused_only_for_a_ticker_already_on_that_date(pipeline):
    with pytest.raises(SystemExit):
        core.main(["--date", "2026-06-01", "--tickers", "NVDA"])
    assert pipeline["appended"] == []
    assert pipeline["read_tabs"] == ["AnalysisTickerSpecific"]


def test_ticker_run_proceeds_for_a_name_not_yet_on_that_date(pipeline):
    core.main(["--date", "2026-06-01", "--tickers", "AMD"])
    assert [t for t, _ in pipeline["appended"]] == ["AnalysisTickerSpecific"]
