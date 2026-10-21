"""lib/regime_watch.py on synthetic frames. No network."""
import csv
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from lib import regime_watch as rw

UTC = timezone.utc
AFTER_CLOSE = datetime(2030, 1, 1, 23, 0, tzinfo=UTC)


def frame(vals, end="2025-06-30", adj=None):
    idx = pd.bdate_range(end=end, periods=len(vals))
    return pd.DataFrame({"Close": vals, "Adj Close": adj if adj is not None else vals},
                        index=idx, dtype=float)


def table(dirs, end="2025-06-30"):
    idx = pd.bdate_range(end=end, periods=len(dirs))
    return [{"date": d.strftime("%Y-%m-%d"), "mech_direction": x, "mech_vol": "L-VOL"}
            for d, x in zip(idx, dirs)]


def flat(n=260, v=100.0):
    return [v] * n


def frames(spy=None, iwm=None, hyg=None, ief=None, vix=None, vix3m=None, n=260):
    return {"SPY": frame(spy or flat(n)), "IWM": frame(iwm or flat(n)),
            "HYG": frame(hyg or flat(n)), "IEF": frame(ief or flat(n)),
            "^VIX": frame(vix or flat(n, 15.0)), "^VIX3M": frame(vix3m or flat(n, 18.0))}


def run(fr, dirs, **kw):
    return rw.evaluate(fr, table(dirs), now=AFTER_CLOSE, **kw)


# streak ------------------------------------------------------------------
def test_streak_counts_trailing_bear_only():
    s, recent, row = rw.bear_streak(table(["BEAR", "RANGE", "BEAR", "BEAR", "BEAR"]), "2030-01-01")
    assert (s, recent) == (3, True) and row["mech_direction"] == "BEAR"


def test_streak_zero_and_recent_window():
    s, recent, _ = rw.bear_streak(table(["BEAR"] + ["BULL"] * 5), "2030-01-01")
    assert (s, recent) == (0, False)  # the BEAR is 6 sessions back
    s, recent, _ = rw.bear_streak(table(["BEAR"] + ["BULL"] * 4), "2030-01-01")
    assert (s, recent) == (0, True)


def test_streak_empty():
    assert rw.bear_streak([], "2030-01-01") == (0, False, None)


# conditions --------------------------------------------------------------
def test_spy_below_200_boundary():
    below = flat(259) + [99.0]          # sma200 just under 100, close below it
    assert run(frames(spy=below), ["BULL"] * 260)["c2_spy_below_200"] is True
    equal = flat(260)                    # close == sma: not below
    assert run(frames(spy=equal), ["BULL"] * 260)["c2_spy_below_200"] is False


def test_iwm_below_200():
    r = run(frames(iwm=flat(259) + [50.0]), ["BULL"] * 260)
    assert r["c4_iwm_below_200"] is True and r["c2_spy_below_200"] is False


def test_credit_weak_uses_adj_close_and_threshold():
    hyg = frame(flat(260), adj=flat(240) + [100.0] * 19 + [98.9])   # -1.1% vs 20 sessions ago
    fr = frames()
    fr["HYG"] = hyg
    r = run(fr, ["BULL"] * 260)
    assert r["c3_credit_weak"] is True and r["credit_chg20"] == pytest.approx(-0.011)
    fr["HYG"] = frame(flat(260), adj=flat(259) + [99.1])            # -0.9%
    assert run(fr, ["BULL"] * 260)["c3_credit_weak"] is False


def test_credit_exactly_minus_one_pct_is_not_weak():
    fr = frames()
    fr["HYG"] = frame(flat(260), adj=flat(259) + [99.0])
    assert run(fr, ["BULL"] * 260)["c3_credit_weak"] is False


def test_vix_threshold():
    assert run(frames(vix=flat(259, 15.0) + [20.0]), ["BULL"] * 260)["c5_vix_ge_20"] is True
    assert run(frames(vix=flat(259, 15.0) + [19.99]), ["BULL"] * 260)["c5_vix_ge_20"] is False


def test_short_history_gives_none_not_false():
    r = run(frames(n=100), ["BULL"] * 100)
    assert r["c2_spy_below_200"] is None and r["c4_iwm_below_200"] is None
    assert r["n_confirm"] == 0


def test_info_fields():
    r = run(frames(vix=flat(259, 15.0) + [18.0], vix3m=flat(260, 20.0)), ["BULL"] * 260)
    assert r["vix_vix3m"] == pytest.approx(0.9)
    assert r["spy_vs_sma50"] == pytest.approx(0.0)
    assert len(r["last10"]) == 10


# status ------------------------------------------------------------------
@pytest.mark.parametrize("streak,recent,n,want", [
    (3, True, 2, "CONFIRMED"), (3, True, 1, "WATCH"), (2, True, 3, "WATCH"),
    (0, True, 0, "WATCH"), (0, False, 2, "WATCH"), (0, False, 1, "CLEAR"),
    (5, True, 4, "CONFIRMED"), (0, False, 0, "CLEAR"),
])
def test_classify(streak, recent, n, want):
    assert rw.classify(streak, recent, n) == want


def test_status_end_to_end_confirmed():
    spy = flat(259) + [90.0]
    r = run(frames(spy=spy, vix=flat(259, 15.0) + [25.0]), ["BULL"] * 257 + ["BEAR"] * 3)
    assert r["bear_streak"] == 3 and r["n_confirm"] == 2 and r["status"] == "CONFIRMED"


# causality / partial bar ---------------------------------------------------
def test_as_of_ignores_future_data():
    spy = flat(250) + [50.0] * 10       # crash only in the last 10 sessions
    fr = frames(spy=spy)
    tbl = table(["BULL"] * 250 + ["BEAR"] * 10)
    idx = fr["SPY"].index
    as_of = idx[249].strftime("%Y-%m-%d")
    replay = rw.evaluate(fr, tbl, as_of=as_of, now=AFTER_CLOSE)
    # identical to a run on frames that never contained the future
    cut = {k: v.iloc[:250] for k, v in fr.items()}
    base = rw.evaluate(cut, tbl[:250], now=AFTER_CLOSE)
    assert replay == base
    assert replay["date"] == as_of and replay["bear_streak"] == 0
    assert replay["c2_spy_below_200"] is False


def test_as_of_on_non_session_uses_prior_session():
    fr = frames()
    sat = (fr["SPY"].index[-1] + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    assert run(fr, ["BULL"] * 260, as_of=sat)["date"] == fr["SPY"].index[-1].strftime("%Y-%m-%d")


def test_partial_bar_dropped_during_session():
    fr = frames()
    today = fr["SPY"].index[-1]
    during = datetime(today.year, today.month, today.day, 15, 0, tzinfo=UTC)
    out = rw.drop_partial(fr["SPY"], during)
    assert len(out) == 259 and out.index[-1] < today
    after = datetime(today.year, today.month, today.day, 22, 0, tzinfo=UTC)
    assert len(rw.drop_partial(fr["SPY"], after)) == 260


def test_partial_bar_never_labels_today():
    fr = frames(spy=flat(259) + [10.0])      # today's partial print would trip c2
    today = fr["SPY"].index[-1]
    during = datetime(today.year, today.month, today.day, 15, 0, tzinfo=UTC)
    r = rw.evaluate(fr, table(["BULL"] * 260), now=during)
    assert r["date"] < today.strftime("%Y-%m-%d") and r["c2_spy_below_200"] is False


def test_nan_close_dropped():
    df = frame(flat(10))
    df.iloc[-1, df.columns.get_loc("Close")] = np.nan
    assert len(rw.drop_partial(df, AFTER_CLOSE)) == 9


# history -----------------------------------------------------------------
def test_history_dedupes_on_date_and_sorts(tmp_path):
    p = tmp_path / "sub" / "history.csv"
    base = {"status": "CLEAR", "bear_streak": 0}
    rw.upsert_history(p, {**base, "date": "2025-06-30"})
    rw.upsert_history(p, {**base, "date": "2025-06-27"})
    n = rw.upsert_history(p, {**base, "date": "2025-06-30", "status": "WATCH"})
    rows = list(csv.DictReader(open(p)))
    assert n == 2 and [r["date"] for r in rows] == ["2025-06-27", "2025-06-30"]
    assert rows[1]["status"] == "WATCH"
    assert list(rows[0].keys()) == rw.HISTORY_COLUMNS


def test_backfill_replays_each_session_causally(tmp_path):
    from scripts import regime_watch as script
    vix = flat(258, 15.0) + [25.0, 25.0]          # VIX crosses 20 on the last two sessions
    fr = frames(vix=vix)
    tab = table(["BULL"] * 260)
    p = tmp_path / "h.csv"
    assert script.backfill(fr, tab, 4, str(p)) == 4
    rows = list(csv.DictReader(open(p)))
    assert [r["c5_vix_ge_20"] for r in rows] == ["False", "False", "True", "True"]
    assert rows[0]["date"] == rw.evaluate(fr, tab, as_of=rows[0]["date"])["date"]
