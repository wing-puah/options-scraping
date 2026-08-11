"""Tests for the study validation protocol.

These functions gate every tuning conclusion, so the properties pinned here are
the methodological ones (purging actually purges, CIs resample dates not rows,
replay takes at most k per day in tier order), not just return shapes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_study.protocol import (  # noqa: E402
    boot_ci_by_date, boot_ci_paired_by_date, ladder_eligible, ladder_rank,
    loo_by_date, replay_stats, sign_stable, top_k_per_day, walk_forward_splits,
    window_cuts, year_epoch_split,
)


def _dates(n, start_month=1):
    """n consecutive-ish dates spread over 2025 so blocks span the embargo."""
    out = []
    for i in range(n):
        month = start_month + i // 28
        day = i % 28 + 1
        out.append(f"2025-{month:02d}-{day:02d}")
    return out


# ── splits ──────────────────────────────────────────────────────────────────

def test_walk_forward_embargoes_the_training_end():
    dates = _dates(200)
    splits = list(walk_forward_splits(dates, block=15, embargo_days=120,
                                      min_train_dates=40))
    assert splits, "expected at least one usable block"
    from datetime import date, timedelta
    for train, test in splits:
        assert max(train) < min(test)
        gap = date.fromisoformat(min(test)) - date.fromisoformat(max(train))
        assert gap >= timedelta(days=120), "a training label could still be open"


def test_walk_forward_test_blocks_are_disjoint_and_cover_late_dates():
    dates = _dates(200)
    tested = [d for _, test in walk_forward_splits(dates, block=15) for d in test]
    assert len(tested) == len(set(tested))
    assert max(tested) == max(dates)


def test_walk_forward_skips_blocks_with_too_little_purged_history():
    # 40 dates total can never leave 40 training dates after the embargo.
    assert list(walk_forward_splits(_dates(40), block=15, min_train_dates=40)) == []


def test_year_epoch_split_purges_the_boundary():
    dates = ["2025-11-01", "2025-12-15", "2026-01-05", "2026-02-01"]
    train, test = year_epoch_split(dates, "2026", embargo_days=120)
    assert test == ["2026-01-05", "2026-02-01"]
    assert train == ["2025-09-07"] if False else all(d <= "2025-09-07" for d in train)


# ── uncertainty ─────────────────────────────────────────────────────────────

def test_boot_ci_treats_one_date_as_one_observation():
    """200 rows on 2 dates must NOT give a tight CI — that is the whole point."""
    rows = ([{"date": "2025-01-02", "E": 1.0}] * 100
            + [{"date": "2025-01-03", "E": -1.0}] * 100)
    lo, hi = boot_ci_by_date(rows, "E", n=2000)
    assert hi - lo > 1.0, "date clustering collapsed into row clustering"


def test_boot_ci_narrows_when_the_dates_agree():
    rows = [{"date": f"2025-01-{i:02d}", "E": 0.5} for i in range(1, 29)]
    lo, hi = boot_ci_by_date(rows, "E", n=2000)
    assert abs(hi - lo) < 1e-9 and abs(lo - 0.5) < 1e-9


def test_paired_ci_of_a_constant_edge_excludes_zero():
    rows = [{"date": f"2025-01-{i:02d}", "a": 0.4, "b": 0.1} for i in range(1, 29)]
    lo, hi = boot_ci_paired_by_date(rows, "a", "b", n=2000)
    assert lo > 0 and abs(hi - 0.3) < 1e-9


def test_loo_flags_a_gain_carried_by_one_date():
    """A one-date effect fails the ONE fold that drops the carrying date.

    Most folds still look good — that is exactly why the survival test is "every
    fold positive", read off min_gain, not the average fold.
    """
    rows = [{"date": "2025-01-02", "v": 50.0, "base": 0.0}]
    rows += [{"date": f"2025-02-{i:02d}", "v": -1.0, "base": 0.0} for i in range(1, 21)]
    mean_gain, share_pos, min_gain, n = loo_by_date(rows, lambda r: r["v"],
                                                    lambda r: r["base"])
    assert n == 21
    assert mean_gain > 0, "the pooled effect looks positive"
    assert share_pos < 1.0 and min_gain < 0, "the carrying date's fold must flip"


def test_loo_passes_a_broad_effect():
    rows = [{"date": f"2025-0{1 + i // 20}-{i % 20 + 1:02d}", "v": 1.0, "base": 0.0}
            for i in range(40)]
    _, share_pos, min_gain, n = loo_by_date(rows, lambda r: r["v"], lambda r: r["base"])
    assert n == 40 and share_pos == 1.0 and min_gain > 0


# ── replay ──────────────────────────────────────────────────────────────────

def _row(d, tier, score=None, post13c=True, R=0.0):
    return dict(date=d, tier=tier, score_total=score, post13c=post13c,
                R=R, R_dol=R * 1000, E=R)


def test_top_k_takes_at_most_k_per_day_in_tier_order():
    rows = [_row("2025-01-02", "A", R=1), _row("2025-01-02", "B", R=2),
            _row("2025-01-02", "A", R=3), _row("2025-01-02", "B", R=4),
            _row("2025-01-03", "C", R=9)]
    picked = top_k_per_day(rows, ladder_rank, k=3, eligible_fn=ladder_eligible)
    assert len(picked) == 3
    assert [p["tier"] for p in picked] == ["A", "A", "B"]
    assert all(p["date"] == "2025-01-02" for p in picked), "C-only day contributes nothing"


def test_score_tie_break_applies_within_a_tier_only():
    rows = [_row("2025-01-02", "B", score=90), _row("2025-01-02", "A", score=10)]
    picked = top_k_per_day(rows, ladder_rank, k=1, eligible_fn=ladder_eligible)
    assert picked[0]["tier"] == "A", "score must never outrank a tier"


def test_pre_13c_scores_do_not_tie_break():
    a = _row("2025-01-02", "A", score=90, post13c=False)
    b = _row("2025-01-02", "A", score=10, post13c=True)
    assert ladder_rank(a)[1] == 0.0 and ladder_rank(b)[1] == 10.0


def test_replay_stats_counts_dollars_dates_and_wins():
    picked = [_row("2025-01-02", "A", R=1.0), _row("2025-01-02", "A", R=-1.0),
              _row("2025-01-03", "B", R=2.0)]
    s = replay_stats(picked)
    assert s["n"] == 3 and s["dates"] == 2
    assert s["dollars"] == 2000.0
    assert abs(s["win"] - 2 / 3) < 1e-9


# ── cuts ────────────────────────────────────────────────────────────────────

def test_window_cuts_remove_the_two_dominant_windows():
    rows = [{"date": "2025-03-14"}, {"date": "2026-02-10"}, {"date": "2024-09-01"}]
    cuts = window_cuts(rows)
    assert len(cuts["ALL"]) == 3
    assert [r["date"] for r in cuts["ex_2025_mar_apr"]] == ["2026-02-10", "2024-09-01"]
    assert [r["date"] for r in cuts["ex_2026_feb_apr"]] == ["2025-03-14", "2024-09-01"]


def test_sign_stability_reports_per_year_means():
    rows = [{"date": "2024-01-02", "E": 0.5}, {"date": "2025-01-02", "E": 0.4},
            {"date": "2026-01-02", "E": -0.2}]
    stable, pos, means = sign_stable(rows)
    assert stable is False and pos == 2
    assert set(means) == {"2024", "2025", "2026"}
