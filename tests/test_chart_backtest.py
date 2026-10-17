"""chart_backtest: date filter and tier aggregation (synthetic frames, no rendering)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chart_backtest as cb  # noqa: E402


def _df():
    return pd.DataFrame({
        "signal_date": pd.to_datetime(["2026-01-01", "2026-01-15", "2026-02-01", "2025-12-31"]),
        "structure": ["bull_call_spread", "bull_call_spread", "bear_call_spread", "bear_put_spread"],
        "market_regime": ["RANGE + L-VOL", "BULL + L-VOL", "BULL + L-VOL", ""],
        "dte_entry": [30, 30, 30, 30],
        "delta": [np.nan] * 4,
        "realized_pnl": [50.0, -20.0, -10.0, 5.0],
        "realized_abs": [100.0, -40.0, -20.0, 10.0],
        "mfe_abs": [150.0, 10.0, 5.0, 12.0],
        "mae_abs": [-10.0, -60.0, -30.0, -1.0],
    })


def test_filter_bounds_inclusive():
    out = cb.filter_dates(_df(), "2026-01-01", "2026-01-15")
    assert sorted(out["signal_date"].dt.strftime("%Y-%m-%d")) == ["2026-01-01", "2026-01-15"]
    assert "filtered" in out.attrs["date_filter"]


def test_filter_open_ended_and_none():
    assert len(cb.filter_dates(_df(), "2026-01-15", None)) == 2
    assert len(cb.filter_dates(_df(), None, "2026-01-01")) == 2
    full = cb.filter_dates(_df(), None, None)
    assert len(full) == 4 and "date_filter" not in full.attrs


def test_filter_refuses_start_after_end_and_bad_date():
    with pytest.raises(ValueError, match="after --end"):
        cb.filter_dates(_df(), "2026-02-01", "2026-01-01")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        cb.filter_dates(_df(), "01/02/2026", None)


def test_filter_empty_result_graceful():
    out = cb.filter_dates(_df(), "2030-01-01", None)
    assert out.empty
    assert cb.range_label(out).startswith("0 rows")
    assert cb.build_tier(out, Path("unused")) is None


def test_tier_assignment_and_summary():
    df = cb.add_tier(_df())
    assert list(df["tier"]) == ["A", "B", "VETO", "untiered"]
    s = cb.tier_summary(df).set_index("tier")
    assert s.loc["A", "n"] == 1 and s.loc["A", "win_rate"] == 100.0
    assert s.loc["B", "mean_pct"] == -20.0 and s.loc["B", "win_rate"] == 0.0
    assert s.loc["untiered", "n"] == 1
    assert "C" not in s.index


def test_quartile_stats_splits_wins_and_losses():
    s = cb.quartile_stats(pd.Series([-300.0, -100.0, 0.0, 100.0, 200.0, 300.0, np.nan]))
    assert s["n"] == 6 and s["win_rate"] == 0.5
    assert s["win_q"][1] == 200.0          # median of the wins only
    assert s["loss_q"][1] == -100.0        # 0 counts as a loss
    empty = cb.quartile_stats(pd.Series([50.0]))
    assert np.isnan(empty["loss_q"][1])


def test_tier_groups_splits_tier_b_by_structure():
    df = pd.DataFrame({"tier": ["A", "B", "B", "C"],
                       "structure": ["bull_call_spread", "bull_call_spread",
                                     "bull_put_spread", "bear_put_spread"]})
    assert list(cb.tier_groups(df)["tier_group"]) == ["A", "B·call", "B·put", "C"]


def test_tier_quartiles_drops_sealed_dates(tmp_path):
    from scripts.backtest_study.lib import era
    if era.SEAL_LIFTED:
        pytest.skip("seal lifted")
    df = _df()
    df["signal_date"] = pd.to_datetime([era.SEAL_START] * 4)   # every row sealed
    assert cb.build_tier_quartiles(df, tmp_path) is None
    assert not (tmp_path / "backtest_tier_quartiles.png").exists()
