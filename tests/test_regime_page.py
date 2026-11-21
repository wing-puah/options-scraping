"""scripts/regime_page: the dashboard's regime-watch table. Synthetic fixtures only."""
import csv

from scripts import dashboard as d
from scripts.regime_page import build as rp


def hist(path, pairs):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "status", "n_confirm", "vix_close", "mech_direction", "mech_vol"])
        for dt, st in pairs:
            w.writerow([dt, st, 2, 18.5, "BULL", "L-VOL"])


def rows(pairs):
    return [{"date": a, "status": b} for a, b in pairs]


DAYS = [f"2026-01-{i:02d}" for i in range(5, 31)]


def px(start=100.0, step=1.0, days=DAYS):
    return {dt: start + step * i for i, dt in enumerate(days)}


def prices(**over):
    p = {s: px() for s in rp.ETFS}
    p.update(over)
    return p


def test_run_grouping_and_one_day_run():
    runs = rp.status_runs(rows([("a", "CLEAR"), ("b", "CLEAR"), ("c", "WATCH"), ("d", "CLEAR")]))
    assert [(r["status"], r["start"], r["end"], r["rows"]) for r in runs] == [
        ("CLEAR", "a", "b", 2), ("WATCH", "c", "c", 1), ("CLEAR", "d", "d", 1)]


def test_run_pct_change_and_sessions_on_calendar():
    r = rows([(DAYS[0], "CLEAR"), (DAYS[4], "CLEAR")])   # a gap of 3 days inside the run
    out = rp.build_runs(r, prices())[0]
    assert out["sessions"] == 5 and out["rows"] == 2
    spy = out["prices"]["SPY"]
    assert spy["start"] == 100.0 and spy["end"] == 104.0
    assert abs(spy["chg"] - 0.04) < 1e-12


def test_onset_detection_first_row_of_each_confirmed_run():
    r = rows([(DAYS[0], "CLEAR"), (DAYS[1], "CONFIRMED"), (DAYS[2], "CONFIRMED"), (DAYS[3], "WATCH"),
              (DAYS[4], "CONFIRMED")])
    ons = rp.onsets(r, prices())
    assert [o["date"] for o in ons] == [DAYS[4], DAYS[1]]   # newest first


def test_forward_return_counts_sessions_across_history_gap():
    # history has rows only on day 0 and day 12; the calendar has every day between
    r = rows([(DAYS[0], "CONFIRMED"), (DAYS[12], "CLEAR")])
    o = rp.onsets(r, prices())[0]
    p = px()
    want = p[DAYS[5]] / p[DAYS[0]] - 1
    assert abs(o["fwd"]["SPY"][5] - want) < 1e-12
    assert abs(o["fwd"]["SPY"][10] - (p[DAYS[10]] / p[DAYS[0]] - 1)) < 1e-12


def test_unelapsed_horizon_is_not_yet_and_missing_price_is_none():
    r = rows([(DAYS[-8], "CONFIRMED")])
    smh = px()
    del smh[DAYS[-3]]                                      # the 5-session target has no SMH close
    o = rp.onsets(r, prices(SMH=smh))[0]
    assert o["fwd"]["SPY"][5] is not None and o["fwd"]["SPY"][21] == rp.NOT_YET
    assert o["fwd"]["SMH"][5] is None


def test_missing_price_renders_dash_never_zero():
    smh = px()
    del smh[DAYS[0]]
    out = rp.build_runs(rows([(DAYS[0], "CLEAR"), (DAYS[2], "CLEAR")]), prices(SMH=smh))[0]
    assert out["prices"]["SMH"]["start"] is None and out["prices"]["SMH"]["chg"] is None
    assert rp.fmt_pct(None) == rp.DASH and rp.fmt_px(None) == rp.DASH
    html = rp.render_runs([out])
    assert html.count(rp.DASH) == 2 and "+0.0%" not in html and "$0" not in html


def test_gap_count_note_and_price_ends():
    smh = px(days=DAYS[:-5])
    r = rows([(DAYS[0], "CLEAR"), (DAYS[1], "CLEAR"), (DAYS[4], "WATCH")])
    n = rp.data_note(r, prices(SMH=smh))
    assert n["n_missing"] == len(DAYS) - 3 - 0 and n["last_missing"] == DAYS[-1]
    assert n["ends"]["SMH"] == DAYS[-6] and n["ends"]["SPY"] == DAYS[-1]


def test_gather_degrades_without_files(tmp_path):
    assert rp.gather(tmp_path / "nope.csv", loader=lambda s: px())["ok"] is False
    hist(tmp_path / "h.csv", [(DAYS[0], "CLEAR")])
    assert rp.gather(tmp_path / "h.csv", loader=lambda s: {})["ok"] is False


def test_section_in_built_html(tmp_path, monkeypatch):
    h = tmp_path / "h.csv"
    hist(h, [(DAYS[0], "CLEAR"), (DAYS[1], "CONFIRMED"), (DAYS[2], "CONFIRMED")])
    monkeypatch.setattr(rp, "default_loader", lambda s: px())
    monkeypatch.setattr(rp, "gather", lambda path=h, loader=None, _g=rp.gather: _g(h, lambda s: px()))
    monkeypatch.setattr(d, "WATCH_CSV", h)
    html = d.regime_watch_section()
    assert 'id="regime-watch"' in html and "CONFIRMED marks a fall already under way" in html
    assert "have no status row" in html or "has a status row" in html
    page, _ = d.build("2026-01-30")
    assert 'id="regime-watch"' in page
