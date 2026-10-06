"""Robustness fixes for the three ops findings in research/robustness-review.md.

    P6 — scrape_flow.py exited 0 on zero rows; a dead prefix passed silently
         until the nightly watchdog caught it a session later. Fixed with a
         distinct `_SKIPPED` sentinel (already-uploaded is not a failure) plus
         a `sys.exit(1)` when a live page genuinely returns nothing, and a
         per-prefix row floor in check_pipeline.py so a corpse-but-present
         file fails the watchdog too.
    A5 — two stale messages claimed OI enrichment needs D+1 and "holds back"
         the newest date; it needs only D's own settlement data and lands the
         same evening as D. Message-only fix (enrich_oi.py, enrich-oi.yml);
         nothing here to unit test beyond "the false phrase is gone".
    P8 — the journal had no schedule. `.github/workflows/journal.yml` adds
         one. The watchdog does NOT check the journal (removed 2026-10-06).

Everything below exercises PURE logic against hand-built inputs — no Drive, no
Sheets, no Barchart, no live event loop beyond what a mocked coroutine needs.
Same split as tests/test_check_pipeline.py and tests/test_scraper.py.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from check_pipeline import MISSING, OK, PARTIAL, StageSpec, _judge
from scrape_flow import _REJECTED, _SKIPPED, _dead_prefixes, run_live


# ── P6: scrape_flow — dead-prefix detection ────────────────────────────────

class TestDeadPrefixes:
    def test_empty_csv_is_dead(self):
        assert _dead_prefixes([("stocks-flow", 0)]) == ["stocks-flow"]

    def test_download_failure_is_dead(self):
        assert _dead_prefixes([("stocks-flow", -1)]) == ["stocks-flow"]

    def test_already_uploaded_is_not_dead(self):
        # The whole point of the _SKIPPED sentinel: an idempotent re-run that
        # finds every page already in Drive must never read as a failure.
        assert _dead_prefixes([("stocks-flow", _SKIPPED)]) == []

    def test_staleness_reject_is_not_dead(self):
        # A deliberate non-upload (the retention-probe veto), not a broken
        # scraper.
        assert _dead_prefixes([("stocks-flow", _REJECTED)]) == []

    def test_real_rows_are_not_dead(self):
        assert _dead_prefixes([("stocks-flow", 1500)]) == []

    def test_only_the_dead_one_is_named(self):
        results = [("stocks-flow", 1500), ("etfs-flow", 0)]
        assert _dead_prefixes(results) == ["etfs-flow"]


def _run(coro):
    return asyncio.run(coro)


def _mock_client():
    client = MagicMock()
    client.get_or_create_date_folder.return_value = "folder-id"
    return client


class TestRunLive:
    """`run_live` returns False iff `_dead_prefixes` would be non-empty for
    its pages — the fix that lets GitHub's failure email fire the same run a
    dead prefix happens, instead of a session later via the watchdog.
    """

    @patch("scrape_flow._download_and_upload", new_callable=AsyncMock)
    def test_all_pages_succeed(self, mock_dl):
        mock_dl.side_effect = [1500, 900]
        ok = _run(run_live(AsyncMock(), _mock_client(), "flow"))
        assert ok is True

    @patch("scrape_flow._download_and_upload", new_callable=AsyncMock)
    def test_one_dead_page_fails_the_run(self, mock_dl):
        mock_dl.side_effect = [1500, 0]   # etfs-flow came back empty
        ok = _run(run_live(AsyncMock(), _mock_client(), "flow"))
        assert ok is False

    @patch("scrape_flow._download_and_upload", new_callable=AsyncMock)
    def test_download_failure_fails_the_run(self, mock_dl):
        mock_dl.side_effect = [-1, 1500]
        ok = _run(run_live(AsyncMock(), _mock_client(), "flow"))
        assert ok is False

    @patch("scrape_flow._download_and_upload", new_callable=AsyncMock)
    def test_all_pages_already_uploaded_is_not_a_failure(self, mock_dl):
        # A same-hour re-run: nothing NEW, but nothing broken either.
        mock_dl.side_effect = [_SKIPPED, _SKIPPED]
        ok = _run(run_live(AsyncMock(), _mock_client(), "flow"))
        assert ok is True

    @patch("scrape_flow._download_and_upload", new_callable=AsyncMock)
    def test_staleness_reject_is_not_a_failure(self, mock_dl):
        mock_dl.side_effect = [_REJECTED, 1500]
        ok = _run(run_live(AsyncMock(), _mock_client(), "flow"))
        assert ok is True


# ── P6: check_pipeline — per-prefix row floor ──────────────────────────────

PREFIXES = ("etfs-flow", "stocks-flow")
SCRAPE = StageSpec("scrape", "flow_present", 0, 1.0, PREFIXES, "")
SESSION = "2026-08-19"


def _present_state(row_counts: dict[str, int] | None = None) -> dict:
    state = {
        "flow": {SESSION: {p: {"compiled": True, "snapshots": 6} for p in PREFIXES}},
    }
    if row_counts is not None:
        state["flow_rows"] = {SESSION: row_counts}
    return state


class TestRowFloor:
    def test_ok_when_both_prefixes_above_floor(self):
        state = _present_state({"etfs-flow": 500, "stocks-flow": 800})
        f = _judge(SCRAPE, SESSION, state)
        assert f.verdict == OK

    def test_partial_when_one_prefix_below_floor(self):
        state = _present_state({"etfs-flow": 3, "stocks-flow": 800})
        f = _judge(SCRAPE, SESSION, state)
        assert f.verdict == PARTIAL
        assert "etfs-flow" in f.detail
        assert "stocks-flow" not in f.detail  # only the thin one is named

    def test_partial_when_both_prefixes_below_floor(self):
        state = _present_state({"etfs-flow": 0, "stocks-flow": 1})
        f = _judge(SCRAPE, SESSION, state)
        assert f.verdict == PARTIAL

    def test_ok_when_row_data_was_not_gathered(self):
        # No `flow_rows` entry at all (e.g. this stage's session was never
        # fetched for row counts) — must not be treated as a floor breach.
        state = _present_state(row_counts=None)
        f = _judge(SCRAPE, SESSION, state)
        assert f.verdict == OK

    def test_missing_still_wins_over_row_floor(self):
        # A wholly-absent prefix is MISSING, not merely thin, even if
        # flow_rows somehow carried a (stale) count for it.
        state = {
            "flow": {SESSION: {"etfs-flow": {"compiled": False, "snapshots": 0},
                               "stocks-flow": {"compiled": True, "snapshots": 6}}},
            "flow_rows": {SESSION: {"etfs-flow": 500, "stocks-flow": 800}},
        }
        f = _judge(SCRAPE, SESSION, state)
        assert f.verdict == MISSING
