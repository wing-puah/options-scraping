"""
Tests for `scripts/clean_generated.py`.

Most of these exercise the guards. The three hard guards are the whole reason
this script is allowed to call `shutil.rmtree`, so each is tested for the case
it uniquely catches — the case the other two would miss.
"""
from pathlib import Path

import pytest

from clean_generated import (
    KEEP_NAMES,
    TARGETS,
    Target,
    build_plan,
    cited_paths,
    delete,
    pin,
    resolve,
    safety_violations,
    _protecting_prefix,
    _walk_pycache,
)


def _touch(path: Path, body: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


# ── the target table itself ────────────────────────────────────────────────────

def test_target_names_are_unique():
    names = [t.name for t in TARGETS]
    assert len(names) == len(set(names))


def test_every_target_documents_how_to_rebuild_it():
    # The report prints `regen` as the answer to "how do I get this back". A
    # target with no answer to that does not belong in the table.
    for target in TARGETS:
        assert target.what.strip(), target.name
        assert target.regen.strip(), target.name


def test_no_target_reaches_into_a_protected_tree():
    # A static read of the globs, so a bad pattern fails the suite even on a
    # checkout where that tree happens to be empty and resolve() finds nothing.
    for target in TARGETS:
        for pattern in target.globs:
            assert _protecting_prefix(Path(pattern)) is None, (
                f"{target.name} glob {pattern!r} reaches into a protected tree")


def test_study_output_is_left_to_its_own_cleaner():
    # scripts/clean_study_output.py owns that directory; its pin scan protects
    # cited and gate-marker reports, and this script has no such scan.
    for target in TARGETS:
        for pattern in target.globs:
            assert "study_output" not in pattern, target.name


def test_rolling_result_csvs_are_not_matched_by_the_stamped_glob(tmp_path):
    # backtest/shared/results_io.py archives results.csv -> results_<stamp>.csv,
    # so only the stamped shape is history. `make chart-all` reads the rolling
    # pair, and the frozen v1_/v2_ evidence exports must not match either.
    for name in ("results.csv", "proxy_results.csv", "v1_20260625_results.csv",
                 "v2_results_nocreditdiff.csv", "results_20260815_082109.csv",
                 "proxy_results_20260815_084808.csv"):
        _touch(tmp_path / "backtests" / name)
    target = next(t for t in TARGETS if t.name == "backtest-runs")

    assert {p.name for p in resolve(target, tmp_path)} == {
        "results_20260815_082109.csv", "proxy_results_20260815_084808.csv"}


def test_journal_pages_are_excluded_from_the_site_target(tmp_path):
    # `make study-docs` rebuilds the map and chart pages but NOT journal-*.html,
    # which needs a real journal run against that date's broker pull. A deleted
    # page for a past date may be unrecoverable.
    for name in ("study-map.html", "account-sim-charts.html",
                 "journal-latest.html", "journal-2026-08-14.html"):
        _touch(tmp_path / "site" / name)
    target = next(t for t in TARGETS if t.name == "site")

    assert {p.name for p in resolve(target, tmp_path)} == {
        "study-map.html", "account-sim-charts.html"}


@pytest.mark.parametrize("rel", [
    "backtests/option_history_cache/AAPL/2026-01-02.json",
    "backtests/to_evaluate/v3_export.csv",
    "backtests/live_loop/ibkr_snapshot_2026-08-12.json",
])
def test_irreplaceable_backtest_subtrees_are_protected_not_merely_expensive(rel):
    # No flag deletes these: the scraped option history (the user's standing
    # instruction), the hand-exported study inputs, and point-in-time broker
    # snapshots that cannot be refetched for a past date.
    assert _protecting_prefix(Path(rel)) is not None


# ── guard 1: inside the repo ───────────────────────────────────────────────────

def test_path_outside_the_repo_is_refused(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = _touch(tmp_path / "elsewhere" / "victim.txt")

    violations = safety_violations([outside], root, frozenset())

    assert [why for _, why in violations] == ["resolves outside the repository"]


def test_symlink_escaping_the_repo_is_refused(tmp_path):
    root = tmp_path / "repo"
    (root / "logs").mkdir(parents=True)
    outside = _touch(tmp_path / "elsewhere" / "real.txt")
    link = root / "logs" / "link.log"
    link.symlink_to(outside)

    violations = safety_violations([link], root, frozenset())

    assert [why for _, why in violations] == ["resolves outside the repository"]


# ── guard 2: not git-tracked ───────────────────────────────────────────────────

def test_git_tracked_file_is_refused(tmp_path):
    # The case guards 1 and 3 both miss: inside the repo, not under a protected
    # prefix, but source all the same (backtests/__init__.py is the real one).
    tracked = _touch(tmp_path / "backtests" / "__init__.py", "")

    violations = safety_violations([tracked], tmp_path, frozenset({tracked}))

    assert [why for _, why in violations] == ["tracked by git"]


def test_untracked_sibling_of_a_tracked_file_is_allowed(tmp_path):
    tracked = _touch(tmp_path / "backtests" / "__init__.py", "")
    scratch = _touch(tmp_path / "backtests" / "results_20260815_082109.csv")

    assert safety_violations([scratch], tmp_path, frozenset({tracked})) == []


# ── guard 3: protected trees ───────────────────────────────────────────────────

@pytest.mark.parametrize("rel", [
    "journal/raw/ibkr-2026-08-15-0930.json",
    "portfolio/input/flex-export.csv",
    "credentials/drive_token.json",
    "cookies/barchart.json",
    "config/backtest.yml",
    "research/current.md",
    "backtests/option_history_cache/AAPL/2026-01-02.json",
    "backtests/to_evaluate/v3_export.csv",
    "backtests/live_loop/ibkr_snapshot_2026-08-12.json",
])
def test_protected_trees_are_refused(tmp_path, rel):
    # These are gitignored, so guard 2 sees nothing — this list is their only
    # protection. journal/ in particular is the irreplaceable trade record.
    victim = _touch(tmp_path / rel)

    violations = safety_violations([victim], tmp_path, frozenset())

    assert len(violations) == 1
    assert violations[0][1].startswith("under protected ")


def test_portfolio_output_is_derived_and_not_protected(tmp_path):
    # Only portfolio/input/ is protected: output/ is recomputed from it by
    # 01_cleanup.py + 02_analysis.py in seconds.
    derived = _touch(tmp_path / "portfolio" / "output" / "cleaned_trades.csv")

    assert safety_violations([derived], tmp_path, frozenset()) == []


def test_prefix_match_is_by_segment_not_string():
    # `backtests/option_history_cache` must not shadow a differently-named
    # sibling, and `journal` must not shadow `journalling-notes`.
    assert _protecting_prefix(Path("backtests/option_history_cache_v2/x.json")) is None
    assert _protecting_prefix(Path("journalling-notes/x.md")) is None
    assert _protecting_prefix(Path("journal/x.md")) == "journal"


def test_scripts_journal_source_is_not_confused_with_the_trade_record():
    # The same trap the .gitignore's leading slash exists for: `journal` must be
    # matched at the repo root, not at any depth.
    assert _protecting_prefix(Path("scripts/journal/s01_pull.py")) is None


# ── guard 4: the citation pin scan ─────────────────────────────────────────────

def test_cited_file_is_pinned_with_its_citation(tmp_path):
    research = tmp_path / "research"
    _touch(research / "current.md",
           "Provenance: `backtests/results_20260815_082109.csv`, git 470b95f.\n")
    candidate = _touch(tmp_path / "backtests" / "results_20260815_082109.csv")

    citations = cited_paths(tmp_path, dirs=("research",))
    deletable, pinned = pin([candidate], tmp_path, citations)

    assert deletable == []
    assert [(p.name, why) for p, why in pinned] == [
        ("results_20260815_082109.csv", "cited research/current.md:1")]


def test_citation_in_code_pins_too(tmp_path):
    # A study module that names its baseline export by path; that counts.
    _touch(tmp_path / "scripts" / "study.py",
           'BASE = ROOT / "backtests/v2_results_nocreditdiff.csv"\n')
    candidate = _touch(tmp_path / "backtests" / "v2_results_nocreditdiff.csv")

    _, pinned = pin([candidate], tmp_path,
                    cited_paths(tmp_path, dirs=("scripts",)))

    assert [p.name for p, _ in pinned] == ["v2_results_nocreditdiff.csv"]


def test_bare_directory_citation_does_not_pin_unrelated_files(tmp_path):
    # chart_backtest.py names `backtests/charts` as its OUTPUT dir. Indexing
    # that bare basename would pin every unrelated charts/ in the repo — and did,
    # for portfolio/output/charts/, before basenames needed a suffix.
    _touch(tmp_path / "scripts" / "chart_backtest.py",
           'parser.add_argument("--out", default="backtests/charts")\n')
    victim = _touch(tmp_path / "portfolio" / "output" / "charts" / "pnl.png")

    citations = cited_paths(tmp_path, dirs=("scripts",))
    deletable, pinned = pin([victim], tmp_path, citations)

    assert "charts" not in citations
    assert pinned == []
    assert deletable == [victim]


def test_uncited_file_is_deletable(tmp_path):
    _touch(tmp_path / "research" / "current.md", "no paths here\n")
    candidate = _touch(tmp_path / "backtests" / "results_20260815_082109.csv")

    deletable, pinned = pin([candidate], tmp_path,
                            cited_paths(tmp_path, dirs=("research",)))

    assert deletable == [candidate]
    assert pinned == []


def test_force_bypasses_the_pin_scan_by_emptying_the_index(tmp_path):
    # --force is implemented as "build no index", so pin() sees nothing to pin.
    candidate = _touch(tmp_path / "backtests" / "results_20260815_082109.csv")

    deletable, pinned = pin([candidate], tmp_path, {})

    assert deletable == [candidate]
    assert pinned == []


# ── resolution and planning ────────────────────────────────────────────────────

def test_anchor_files_are_never_resolved_as_candidates(tmp_path):
    for name in KEEP_NAMES:
        _touch(tmp_path / "backtests" / name, "")
    _touch(tmp_path / "backtests" / "results_20260815_082109.csv")
    target = Target(name="t", globs=("backtests/*",), what="w", regen="r")

    assert [p.name for p in resolve(target, tmp_path)] == [
        "results_20260815_082109.csv"]


def test_resolve_deduplicates_paths_matched_by_two_globs(tmp_path):
    _touch(tmp_path / "logs" / "options.2026-08-01.log")
    target = Target(name="t", globs=("logs/*.log", "logs/options.*"),
                    what="w", regen="r")

    assert len(resolve(target, tmp_path)) == 1


def test_expensive_targets_need_the_caches_flag(tmp_path):
    _touch(tmp_path / "cache" / "a.json")
    targets = (Target(name="c", globs=("cache/*",), what="w", regen="r",
                      expensive=True),)

    assert build_plan(targets, tmp_path, caches=False, only=None).entries == []
    assert build_plan(targets, tmp_path, caches=True, only=None).paths


def test_only_selects_a_single_target(tmp_path):
    _touch(tmp_path / "logs" / "a.log")
    _touch(tmp_path / "site" / "a.html")
    targets = (Target(name="logs", globs=("logs/*",), what="w", regen="r"),
               Target(name="site", globs=("site/*",), what="w", regen="r"))

    plan = build_plan(targets, tmp_path, caches=False, only={"logs"})

    assert [p.name for p in plan.paths] == ["a.log"]


def test_a_fully_pinned_target_drops_out_of_the_plan(tmp_path):
    _touch(tmp_path / "backtests" / "results_20260815_082109.csv")
    targets = (Target(name="r", globs=("backtests/results_*.csv",),
                      what="w", regen="r"),)
    citations = {"results_20260815_082109.csv": "research/current.md:1"}

    plan = build_plan(targets, tmp_path, caches=False, only=None,
                      citations=citations)

    assert plan.entries == []
    assert len(plan.pinned) == 1


def test_delete_removes_files_and_trees_but_not_their_parent(tmp_path):
    # The runtime dirs are gitignored and some scripts assume they exist, so
    # targets match a directory's CONTENTS and the directory itself survives.
    _touch(tmp_path / "logs" / "a.log")
    (tmp_path / "logs" / "sub").mkdir()
    _touch(tmp_path / "logs" / "sub" / "b.log")
    targets = (Target(name="logs", globs=("logs/*",), what="w", regen="r"),)
    plan = build_plan(targets, tmp_path, caches=False, only=None)

    assert delete(plan) == 0
    assert (tmp_path / "logs").is_dir()
    assert list((tmp_path / "logs").iterdir()) == []


def test_delete_unlinks_a_dangling_symlink_rather_than_recursing(tmp_path):
    # is_dir() follows symlinks, so a link to a directory must be unlinked, not
    # rmtree'd — otherwise clean would delete through it into the target.
    real = tmp_path / "outside"
    (real / "keep").mkdir(parents=True)
    _touch(real / "keep" / "precious.txt")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "link").symlink_to(real / "keep")
    targets = (Target(name="logs", globs=("logs/*",), what="w", regen="r"),)

    plan = build_plan(targets, tmp_path, caches=False, only=None)
    assert delete(plan) == 0

    assert not (tmp_path / "logs" / "link").exists()
    assert (real / "keep" / "precious.txt").is_file()


def test_pycache_walk_prunes_vendored_and_protected_trees(tmp_path):
    for rel in ("scripts/__pycache__", ".venv/lib/__pycache__",
                "web/node_modules/__pycache__", "journal/__pycache__",
                "research/__pycache__"):
        (tmp_path / rel).mkdir(parents=True)

    found = _walk_pycache(tmp_path)

    assert [p.relative_to(tmp_path).as_posix() for p in found] == [
        "scripts/__pycache__"]
