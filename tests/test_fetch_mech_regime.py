"""fetch_mech_regime never writes a live, unsettled bar (2026-11-13 BEAR_HE drift)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.collector.daily.fetch_mech_regime import _drop_unsettled

ET = ZoneInfo("America/New_York")


def _table():
    return pd.DataFrame({"date": ["2026-11-12", "2026-11-13"],
                         "spy_close": [757.12, 749.79], "vix_close": [18.70, 20.35]})


def test_mid_session_drops_today():
    out = _drop_unsettled(_table(), now=datetime(2026, 11, 13, 12, 2, tzinfo=ET))
    assert list(out["date"]) == ["2026-11-12"]


def test_after_settle_keeps_today():
    out = _drop_unsettled(_table(), now=datetime(2026, 11, 13, 16, 30, tzinfo=ET))
    assert list(out["date"]) == ["2026-11-12", "2026-11-13"]


def test_next_morning_keeps_yesterday():
    out = _drop_unsettled(_table(), now=datetime(2026, 11, 14, 9, 0, tzinfo=ET))
    assert list(out["date"]) == ["2026-11-12", "2026-11-13"]
