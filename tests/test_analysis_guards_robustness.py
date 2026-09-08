"""Robustness fixes for the analysis pipeline (research/robustness-review.md, items A1/A4).

A1 — the "no data" skip: `fetch_data`'s SCORED path (the one `core.main` actually
calls — never `--raw`/`--ticker`) renders a "_No data available._" marker only for
the two FLOW-kind sections (stocks-flow, etfs-flow); the unusual-kind sections feed
scoring only and never get a heading of their own here. So the ceiling this path
can ever produce is 2 markers, not 4 — requiring 4 meant a date whose Drive files
are entirely missing/empty never tripped the skip and got "analysed" on empty
tables instead. This file pins the corrected threshold, and that the check fires
BEFORE any LLM call.

A1 — the zero-plays refusal: writing a MARKET-only row (an analysis that returned
no plays) must be refused rather than written, because nothing distinguishes that
row later from "this date was genuinely, thinly analysed" — see the comment at the
refusal site in `core.main`. `--output-dir` is exempt (it never reaches Sheets at
all, and a zero-play result is itself useful prompt-evaluation evidence).

A4 — output validation: `_parse_and_validate` now checks the top-level contract
keys and every play's required keys + enum vocabulary (config.ANALYSIS_PROMPT_CONTRACT),
not just `regime`. A zero-length `plays` list is deliberately NOT a validation
failure (that would make retrying the only way to paper over a genuinely thin
day) — it is caught by the separate zero-plays refusal above instead. Also pinned:
the winning retry attempt is recorded in the `--output-dir` manifest.
"""
import json

import pytest

from analysis_pipeline import core


def _play(**overrides) -> dict:
    """A play dict that satisfies every required key + enum in the v4 contract."""
    base = {
        "ticker": "NVDA",
        "asset_class": "stock",
        "pattern": "TF",
        "regime": "",
        "signal": "[FLOW] sweeps",
        "structure": "bull call spread 120/130",
        "thesis": "momentum",
        "trigger": "break 118",
        "invalidation": "close < 112",
        "score": {"vol": 8},
        "key_level": 118,
        "direction": "bullish",
        "flow_intent": "DIRECTIONAL",
        "horizon": "60",
        "alternative_interpretation": "could be a covered-call sale",
    }
    base.update(overrides)
    return base


def _analysis(plays=None) -> dict:
    return {
        "regime": "BULL — dealers short gamma",
        "signals": "[FLOW] call sweeps in semis",
        "themes": [],
        "plays": plays if plays is not None else [_play()],
    }


# ── A4: _parse_and_validate ─────────────────────────────────────────────────────

def test_parse_and_validate_accepts_a_conforming_analysis():
    text = json.dumps(_analysis())
    parsed = core._parse_and_validate(text)
    assert parsed["plays"][0]["ticker"] == "NVDA"


def test_parse_and_validate_accepts_zero_plays():
    """A thin day can legitimately return none — that is NOT a parse failure,
    it is handled by core.main's separate zero-plays write refusal."""
    text = json.dumps(_analysis(plays=[]))
    parsed = core._parse_and_validate(text)
    assert parsed["plays"] == []


@pytest.mark.parametrize("key", ["regime", "signals", "themes", "plays"])
def test_parse_and_validate_rejects_missing_top_level_key(key):
    analysis = _analysis()
    del analysis[key]
    with pytest.raises(ValueError, match=key):
        core._parse_and_validate(json.dumps(analysis))


def test_parse_and_validate_rejects_play_missing_a_required_key():
    play = _play()
    del play["alternative_interpretation"]
    with pytest.raises(ValueError, match="alternative_interpretation"):
        core._parse_and_validate(json.dumps(_analysis(plays=[play])))


@pytest.mark.parametrize("field,bad_value", [
    ("asset_class", "bond"),
    ("pattern", "call sweep"),
    ("direction", "up"),
    ("flow_intent", "directional-ish"),
    ("horizon", "2-4 weeks"),
])
def test_parse_and_validate_rejects_off_vocabulary_enum(field, bad_value):
    play = _play(**{field: bad_value})
    with pytest.raises(ValueError, match=field):
        core._parse_and_validate(json.dumps(_analysis(plays=[play])))


def test_parse_and_validate_enum_check_is_case_insensitive_and_tolerates_int_horizon():
    """The model may return upper/lower-cased enum words or a numeric horizon —
    normalized before comparison, not rejected on incidental type/case."""
    play = _play(asset_class="STOCK", direction="Bullish", flow_intent="directional")
    play["horizon"] = 60  # int, not "60"
    parsed = core._parse_and_validate(json.dumps(_analysis(plays=[play])))
    assert parsed["plays"][0]["asset_class"] == "STOCK"  # stored verbatim, not rewritten


def test_parse_and_validate_rejects_non_dict_play():
    with pytest.raises(ValueError, match="play\\[0\\]"):
        core._parse_and_validate(json.dumps(_analysis(plays=["NVDA bull call spread"])))


def test_parse_and_validate_still_requires_regime_key_at_all():
    """Pre-existing behaviour (the ONE key the old code checked) survives the rewrite."""
    with pytest.raises(ValueError, match="regime"):
        core._parse_and_validate(json.dumps({"signals": "", "themes": [], "plays": []}))


def test_validate_play_never_needs_market_fallback():
    """A play's `regime`/`signal` are validated for PRESENCE only, not non-empty
    content — the contract explicitly allows a blank per-play `regime`, and a
    non-empty bar would invite "fixing" a blank one from the MARKET-level
    fields, which is the exact regression analysis_to_rows guards against
    (CLAUDE.md Invariants)."""
    play = _play(regime="", signal="")
    core._validate_play(play, 0)  # must not raise


# ── run_engine: retries on a validation failure, tracks the winning attempt ────

def test_run_engine_retries_a_play_that_fails_validation(monkeypatch):
    bad = json.dumps(_analysis(plays=[_play(pattern="not-a-pattern")]))
    good = json.dumps(_analysis())
    calls = {"n": 0}

    def fake_invoke(prompt, model, cwd):
        calls["n"] += 1
        text = bad if calls["n"] == 1 else good
        return core._parse_and_validate(text), text

    monkeypatch.setattr(core, "_RUNNERS", {"claude": fake_invoke})
    analysis, raw = core.run_engine("claude", "prompt", None)
    assert calls["n"] == 2
    assert analysis["plays"][0]["ticker"] == "NVDA"
    assert core._last_attempt == 2


def test_run_engine_records_the_first_attempt_when_it_wins(monkeypatch):
    def fake_invoke(prompt, model, cwd):
        text = json.dumps(_analysis())
        return core._parse_and_validate(text), text

    monkeypatch.setattr(core, "_RUNNERS", {"claude": fake_invoke})
    core.run_engine("claude", "prompt", None)
    assert core._last_attempt == 1


def test_run_engine_exhausts_attempts_and_resets_last_attempt(monkeypatch):
    def always_bad(prompt, model, cwd):
        raise ValueError("never parses")

    monkeypatch.setattr(core, "_RUNNERS", {"claude": always_bad})
    with pytest.raises(RuntimeError):
        core.run_engine("claude", "prompt", None)
    assert core._last_attempt is None


# ── A1: the no-data skip ────────────────────────────────────────────────────────

_TWO_MARKERS_MD = (
    "## Stocks flow\n\n_No data available._\n\n"
    "## ETFs flow\n\n_No data available._\n"
)
_ONE_MARKER_MD = (
    "## Stocks flow\n\n_No data available._\n\n"
    "## ETFs flow\n\n_3 trades across 2 symbols._\n| Symbol |\n| --- |\n| NVDA |\n"
)


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Stub every side-effecting edge of core.main except the piece under test."""
    monkeypatch.setattr(core, "get_drive_client", lambda: object())
    monkeypatch.setattr(core, "_compute_play_scores", lambda analysis, d: {})
    monkeypatch.setattr(core, "_load_rollup_metrics", lambda p: {})
    monkeypatch.setattr(core, "_mech_cell", lambda d: "NEUTRAL")
    seen = {"appended": []}
    monkeypatch.setattr(core.sheets_client, "append_rows",
                        lambda tab, rows, *a, **kw: seen["appended"].append((tab, len(rows))))
    monkeypatch.setattr(core.sheets_client, "get_all_rows", lambda *a, **kw: [])
    return seen


def test_both_flow_sections_empty_skips_before_the_llm_call(stub_pipeline, monkeypatch):
    monkeypatch.setattr(core, "fetch_data", lambda **kw: _TWO_MARKERS_MD)

    def explode(*a, **kw):
        raise AssertionError("run_engine must not be reached when both flow sections are empty")

    monkeypatch.setattr(core, "run_engine", explode)

    with pytest.raises(SystemExit) as exc:
        core.main(["--date", "2026-06-01"])
    assert exc.value.code == 1
    assert stub_pipeline["appended"] == []


def test_one_flow_section_empty_does_not_skip(stub_pipeline, monkeypatch):
    """Partial data (one section present) is real evidence, not a missing-data day."""
    monkeypatch.setattr(core, "fetch_data", lambda **kw: _ONE_MARKER_MD)
    monkeypatch.setattr(core, "run_engine",
                        lambda engine, prompt, model: (_analysis(), "{}"))

    core.main(["--date", "2026-06-01"])
    assert stub_pipeline["appended"] == [("AnalysisClaude", 2)]  # MARKET + 1 play


def test_focus_narrowing_to_zero_matches_is_not_treated_as_no_data(stub_pipeline, monkeypatch):
    """A focus run with real market data but no flow for the requested tickers emits
    a DIFFERENT message ("None of the focus tickers..."), never the no-data marker —
    it must not be conflated with Drive files being missing, so the run must still
    reach the engine (and be refused afterwards on its own, separate zero-plays
    merits, not short-circuited as a no-data skip)."""
    md = ("## Stocks flow\n\n_3 trades across 2 symbols._\n\n"
          "_None of the focus tickers had flow in Stocks flow._\n")
    monkeypatch.setattr(core, "fetch_data", lambda **kw: md)
    engine_calls = {"n": 0}

    def fake_run_engine(engine, prompt, model):
        engine_calls["n"] += 1
        return _analysis(plays=[]), "{}"

    monkeypatch.setattr(core, "run_engine", fake_run_engine)

    with pytest.raises(SystemExit):  # zero plays still refuses the write, separately
        core.main(["--date", "2026-06-01", "--tickers", "ZZZZ"])
    assert engine_calls["n"] == 1, "the no-data skip must not have fired here"
    assert stub_pipeline["appended"] == []


# ── A1: the zero-plays write refusal ────────────────────────────────────────────

def test_zero_plays_refuses_the_write(stub_pipeline, monkeypatch):
    monkeypatch.setattr(core, "fetch_data", lambda **kw: _ONE_MARKER_MD)
    monkeypatch.setattr(core, "run_engine",
                        lambda engine, prompt, model: (_analysis(plays=[]), "{}"))

    with pytest.raises(SystemExit) as exc:
        core.main(["--date", "2026-06-01"])
    assert exc.value.code == 1
    assert stub_pipeline["appended"] == []


def test_zero_plays_is_reported_separately_from_a_generic_skip(stub_pipeline, monkeypatch, capsys):
    monkeypatch.setattr(core, "fetch_data", lambda **kw: _ONE_MARKER_MD)
    monkeypatch.setattr(core, "run_engine",
                        lambda engine, prompt, model: (_analysis(plays=[]), "{}"))

    with pytest.raises(SystemExit):
        core.main(["--date", "2026-06-01"])
    out = capsys.readouterr().out
    assert "Refused (zero plays)" in out
    assert "2026-06-01" in out


def test_zero_plays_does_not_block_a_dry_run_report_but_still_refuses(stub_pipeline, monkeypatch):
    """--dry-run never writes anyway, but the zero-play analysis must still be
    reported as a refusal rather than a normal (silent) dry-run skip."""
    monkeypatch.setattr(core, "fetch_data", lambda **kw: _ONE_MARKER_MD)
    monkeypatch.setattr(core, "run_engine",
                        lambda engine, prompt, model: (_analysis(plays=[]), "{}"))

    with pytest.raises(SystemExit):
        core.main(["--date", "2026-06-01", "--dry-run"])
    assert stub_pipeline["appended"] == []


def test_output_dir_writes_a_zero_play_result_instead_of_refusing(stub_pipeline, monkeypatch, tmp_path):
    """--output-dir is prompt evaluation: a zero-play result is itself evidence
    about the candidate prompt, so it is written locally rather than refused —
    and Sheets is never touched regardless."""
    monkeypatch.setattr(core, "fetch_data", lambda **kw: _ONE_MARKER_MD)
    monkeypatch.setattr(core, "run_engine",
                        lambda engine, prompt, model: (_analysis(plays=[]), "{}"))

    out = tmp_path / "run"
    core.main(["--date", "2026-06-01", "--output-dir", str(out)])

    assert (out / "2026-06-01.json").exists()
    assert stub_pipeline["appended"] == []
    entry = json.loads((out / "manifest.jsonl").read_text().strip().splitlines()[0])
    assert entry["n_plays"] == 0


# ── A4: attempt count persisted in the --output-dir manifest ───────────────────

def test_output_dir_manifest_records_which_attempt_won(stub_pipeline, monkeypatch, tmp_path):
    monkeypatch.setattr(core, "fetch_data", lambda **kw: _ONE_MARKER_MD)
    bad = json.dumps(_analysis(plays=[_play(direction="sideways")]))
    good = json.dumps(_analysis())
    calls = {"n": 0}

    def fake_invoke(prompt, model, cwd):
        calls["n"] += 1
        text = bad if calls["n"] == 1 else good
        return core._parse_and_validate(text), text

    monkeypatch.setattr(core, "_RUNNERS", {"claude": fake_invoke})

    out = tmp_path / "run"
    core.main(["--date", "2026-06-01", "--output-dir", str(out)])

    entry = json.loads((out / "manifest.jsonl").read_text().strip().splitlines()[0])
    assert entry["analysis_attempt"] == 2
    assert entry["analysis_max_attempts"] == core.config.MAX_ATTEMPTS


def test_skip_llm_manifest_carries_no_attempt_info(stub_pipeline, monkeypatch, tmp_path):
    """--skip-llm never calls the engine at all, so there is no attempt to record."""
    monkeypatch.setattr(core, "fetch_data", lambda **kw: _ONE_MARKER_MD)

    def explode(*a, **kw):
        raise AssertionError("--skip-llm must not call the engine")

    monkeypatch.setattr(core, "run_engine", explode)

    out = tmp_path / "run"
    core.main(["--date", "2026-06-01", "--output-dir", str(out), "--skip-llm"])

    entry = json.loads((out / "manifest.jsonl").read_text().strip().splitlines()[0])
    assert "analysis_attempt" not in entry
