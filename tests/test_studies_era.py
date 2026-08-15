"""Unit tests for scripts/backtest_study/lib/era.py — the "which prompt-version
population is this study reading" guard.

See the module docstring for why this exists: a bare export's filename does not
name a fixed population (the live Sheets tab it mirrors gets renamed in place at
every prompt-version bump), and reading it as if it did silently pooled four
months of v3 evidence with 14 dates of v4 on 2026-08-15. These tests pin the
three moving parts separately: era DETECTION (what's actually in a CSV),
enforcement (refusing a mismatch/disagreement/indeterminate export), and the
date-floor refusal — plus the path-resolution rule the loader depends on.
"""
import csv

import pytest

from scripts.backtest_study.lib import era


def _write_csv(path, fieldnames, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _write_v3_shaped(path, n_rows=2):
    """score_flow present AND populated on at least one row -> v3."""
    rows = [{"ticker": "AAA", "score_flow": "5"}] + \
        [{"ticker": "BBB", "score_flow": ""} for _ in range(n_rows - 1)]
    _write_csv(path, ["ticker", "score_flow"], rows)


def _write_v4_shaped_column_absent(path, n_rows=2):
    """No score_flow column at all -> v4."""
    _write_csv(path, ["ticker"], [{"ticker": f"T{i}"} for i in range(n_rows)])


def _write_v4_shaped_column_blank(path, n_rows=2):
    """score_flow column present but every value blank -> v4 (RESULT_COLUMNS
    keeps the column across both eras; only the values separate them)."""
    _write_csv(path, ["ticker", "score_flow"],
               [{"ticker": f"T{i}", "score_flow": ""} for i in range(n_rows)])


def _write_header_only(path):
    """Header row, zero data rows -> indeterminate."""
    _write_csv(path, ["ticker", "score_flow"], [])


# ── detect_era ───────────────────────────────────────────────────────────────

class TestDetectEra:
    def test_populated_score_flow_column_is_v3(self, tmp_path):
        p = tmp_path / "results.csv"
        _write_v3_shaped(p)
        assert era.detect_era(p) == "v3"

    def test_absent_score_flow_column_is_v4(self, tmp_path):
        p = tmp_path / "results.csv"
        _write_v4_shaped_column_absent(p)
        assert era.detect_era(p) == "v4"

    def test_present_but_entirely_blank_score_flow_column_is_v4(self, tmp_path):
        """The v4 shape RESULT_COLUMNS actually produces: the column survives,
        every value is blank. Presence alone must NOT read this as v3."""
        p = tmp_path / "results.csv"
        _write_v4_shaped_column_blank(p)
        assert era.detect_era(p) == "v4"

    def test_zero_data_rows_raises_value_error(self, tmp_path):
        p = tmp_path / "results.csv"
        _write_header_only(p)
        with pytest.raises(ValueError, match="no data rows"):
            era.detect_era(p)


# ── enforce ──────────────────────────────────────────────────────────────────

class TestEnforce:
    def test_requested_era_matches_actual_returns_it(self, tmp_path):
        p = tmp_path / "results.csv"
        _write_v3_shaped(p)
        assert era.enforce("v3", {"results": p}) == "v3"

    def test_exits_3_on_requested_vs_actual_mismatch(self, tmp_path):
        p = tmp_path / "results.csv"
        _write_v4_shaped_column_absent(p)  # actually v4

        with pytest.raises(SystemExit) as exc_info:
            era.enforce("v3", {"results": p})  # asked for v3
        assert exc_info.value.code == era.EXIT_ERA_MISMATCH

    def test_exits_3_when_exports_disagree_with_each_other(self, tmp_path):
        v3_path = tmp_path / "results.csv"
        v4_path = tmp_path / "proxy.csv"
        _write_v3_shaped(v3_path)
        _write_v4_shaped_column_absent(v4_path)

        # era="current" so the disagreement check fires before any
        # requested-vs-actual comparison would.
        with pytest.raises(SystemExit) as exc_info:
            era.enforce("current", {"results": v3_path, "proxy": v4_path})
        assert exc_info.value.code == era.EXIT_ERA_MISMATCH

    def test_exits_3_when_no_export_in_paths_exists(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            era.enforce("current", {"results": tmp_path / "missing.csv"})
        assert exc_info.value.code == era.EXIT_ERA_MISMATCH

    def test_current_resolves_to_whatever_was_actually_detected(self, tmp_path):
        """era="current" never mismatches on its own — it reports what "current"
        currently means rather than pinning a value."""
        p = tmp_path / "results.csv"
        _write_v3_shaped(p)
        assert era.enforce("current", {"results": p}) == "v3"


# ── require_dates ────────────────────────────────────────────────────────────

class TestRequireDates:
    def test_below_the_floor_exits_2(self):
        with pytest.raises(SystemExit) as exc_info:
            era.require_dates(10, "v3", minimum=30)
        assert exc_info.value.code == era.EXIT_THIN_ERA

    def test_at_the_floor_returns_none_without_exiting(self):
        assert era.require_dates(30, "v3", minimum=30) is None

    def test_above_the_floor_returns_none_without_exiting(self):
        assert era.require_dates(45, "v3", minimum=30) is None


# ── resolve_paths ────────────────────────────────────────────────────────────

class TestResolvePaths:
    def test_current_uses_bare_filenames(self):
        paths = era.resolve_paths("current")
        assert paths["results"] == era.EVAL_DIR / "analysis - BacktestResults.csv"
        assert paths["proxy"] == era.EVAL_DIR / "analysis - BacktestProxy.csv"
        assert paths["analysis"] == era.EVAL_DIR / "analysis - AnalysisClaude.csv"

    def test_v3_uses_prefixed_filenames(self):
        paths = era.resolve_paths("v3")
        assert paths["results"] == era.EVAL_DIR / "analysis - v3_BacktestResults.csv"
        assert paths["proxy"] == era.EVAL_DIR / "analysis - v3_BacktestProxy.csv"
        assert paths["analysis"] == era.EVAL_DIR / "analysis - v3_AnalysisClaude.csv"

    def test_default_argument_resolves_the_requested_era(self, monkeypatch):
        monkeypatch.setenv("STUDY_ERA", "v3")
        assert era.resolve_paths() == era.resolve_paths("v3")
